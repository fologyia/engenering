"""Rede de tubos com ramais e malhas: a vazão de cada trecho e a pressão de cada nó.

A linha do Montador de fluidos é em série, com a mesma vazão em todos os trechos. Numa rede, a água
se divide nos ramais e as malhas se fecham, e a vazão de cada trecho é incógnita. Aqui a rede é dada
por duas tabelas: os **nós** (reservatórios, com o nível fixo, e pontos de consumo, com a vazão que
sai) e os **trechos** (de que nó a que nó, comprimento, diâmetro, material e perdas localizadas).

As equações são as de sempre:

* em cada trecho, a energia: H_de − H_para + H_bomba = (f·L/D + ΣK)·v·|v|/(2g), com f de
  Darcy-Weisbach pela mesma conta do Montador (64/Re no laminar, Colebrook no turbulento);
* em cada nó de consumo, a continuidade: o que entra menos o que sai é a retirada.

O sistema inteiro é resolvido de uma vez pelo método de Newton nas vazões e nas cargas (o método do
gradiente, de Todini e Pilati, o mesmo do EPANET). Na resposta, a soma das perdas em cada malha dá
zero, que é a condição de Hardy Cross: a solução é a mesma, sem precisar achar as malhas.

Sem Streamlit.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from core.montador_funcoes import RE_LAMINAR, RE_TURBULENTO, fator_de_atrito
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

GRAVIDADE = 9.81
MODULO_ID = "rede_de_tubos"
MODULO_TITULO = "Rede de tubos"
_ITERACOES = 200
_TOLERANCIA_VAZAO = 1e-10  # m³/s
_TOLERANCIA_CARGA = 1e-8  # m
_REFERENCIA = "Darcy-Weisbach e Colebrook; continuidade nos nós; Newton (Todini e Pilati, 1988)"


class ErroDaRede(ValueError):
    """O que está errado na rede, em palavras de quem montou as tabelas."""


@dataclass(frozen=True)
class No:
    nome: str
    cota_m: float = 0.0
    retirada_L_s: float = 0.0  # consumo; negativo é água que entra na rede ali
    reservatorio: bool = False
    nivel_m: float | None = None  # reservatório: o nível da água (carga fixa); vazio = a cota
    x_m: float | None = None  # posição só para o desenho
    y_m: float | None = None

    @property
    def carga_fixa_m(self) -> float:
        return self.nivel_m if self.nivel_m is not None else self.cota_m


@dataclass(frozen=True)
class Trecho:
    nome: str
    de: str
    para: str
    comprimento_m: float
    diametro_mm: float  # interno
    rugosidade_mm: float
    k_local: float = 0.0  # soma dos K das peças do trecho
    bomba_m: float = 0.0  # altura que uma bomba no trecho dá, no sentido de → para

    @property
    def area_m2(self) -> float:
        return math.pi * (self.diametro_mm / 1000.0) ** 2 / 4.0


@dataclass(frozen=True)
class Fluido:
    nome: str
    massa_especifica: float  # kg/m³
    viscosidade: float  # Pa·s


@dataclass(frozen=True)
class Limites:
    pressao_min_m: float = 10.0  # metros de coluna do fluido
    pressao_max_m: float = 40.0
    velocidade_max: float = 3.0  # m/s
    velocidade_min: float = 0.0  # m/s; 0 = não confere


@dataclass(frozen=True)
class ResultadoDoNo:
    nome: str
    reservatorio: bool
    cota_m: float
    carga_m: float
    pressao_m: float  # metros de coluna do fluido
    pressao_kPa: float
    pressao_estatica_m: float
    vazao_L_s: float  # consumo; no reservatório, o que ele manda para a rede


@dataclass(frozen=True)
class ResultadoDoTrecho:
    nome: str
    de: str
    para: str
    vazao_L_s: float  # positiva de → para
    velocidade: float  # m/s, em módulo
    perda_m: float  # perda de carga, em módulo
    reynolds: float
    atrito: float | None
    regime: str

    @property
    def sentido(self) -> str:
        return f"{self.de} → {self.para}" if self.vazao_L_s >= 0 else f"{self.para} → {self.de}"


@dataclass(frozen=True)
class ResultadoDaRede:
    nos: tuple[ResultadoDoNo, ...]
    trechos: tuple[ResultadoDoTrecho, ...]
    verificacoes: tuple[Verificacao, ...]
    avisos: tuple[str, ...]
    iteracoes: int
    fluido: Fluido
    limites: Limites

    @property
    def status(self) -> str:
        return status_geral(self.verificacoes)

    @property
    def consumo_L_s(self) -> float:
        return sum(n.vazao_L_s for n in self.nos if not n.reservatorio)

    @property
    def fornecido_L_s(self) -> float:
        return sum(n.vazao_L_s for n in self.nos if n.reservatorio)


# ---------------------------------------------------------------------------------------------
# Conferência das tabelas
# ---------------------------------------------------------------------------------------------
def problemas(nos: Sequence[No], trechos: Sequence[Trecho]) -> list[str]:
    """Tudo o que impede a conta, para a página mostrar de uma vez."""
    erros: list[str] = []
    nomes = [n.nome for n in nos]
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    if repetidos:
        erros.append(f"Nó com o mesmo nome: {', '.join(repetidos)}. Cada nó precisa de um nome só.")
    if any(not n.strip() for n in nomes):
        erros.append("Há nó sem nome.")
    for n in nos:
        valores = [n.cota_m, n.retirada_L_s, *(v for v in (n.nivel_m,) if v is not None)]
        if not all(math.isfinite(v) for v in valores):
            erros.append(f"O nó {n.nome} tem um valor que não é número.")
    if not any(n.reservatorio for n in nos):
        erros.append(
            "A rede precisa de pelo menos um reservatório (ou caixa d'água): é ele que dá a carga."
        )
    existentes = set(nomes)
    nomes_t = [t.nome for t in trechos]
    repetidos = sorted({n for n in nomes_t if nomes_t.count(n) > 1})
    if repetidos:
        erros.append(f"Trecho com o mesmo nome: {', '.join(repetidos)}.")
    for t in trechos:
        if t.de not in existentes or t.para not in existentes:
            erros.append(f"O trecho {t.nome} liga um nó que não está na tabela dos nós.")
        elif t.de == t.para:
            erros.append(f"O trecho {t.nome} começa e termina no mesmo nó.")
        medidas = (t.comprimento_m, t.diametro_mm)
        if not all(math.isfinite(v) and v > 0 for v in medidas):
            erros.append(f"O trecho {t.nome} precisa de comprimento e diâmetro maiores que zero.")
        if not (math.isfinite(t.rugosidade_mm) and t.rugosidade_mm >= 0):
            erros.append(f"A rugosidade do trecho {t.nome} não pode ser negativa.")
        if not (math.isfinite(t.k_local) and t.k_local >= 0):
            erros.append(f"O K das peças do trecho {t.nome} não pode ser negativo.")
        if not math.isfinite(t.bomba_m):
            erros.append(f"A altura da bomba do trecho {t.nome} não é número.")
    if erros:
        return erros
    vizinhos: dict[str, set[str]] = {n: set() for n in existentes}
    for t in trechos:
        vizinhos[t.de].add(t.para)
        vizinhos[t.para].add(t.de)
    alcancados = {n.nome for n in nos if n.reservatorio}
    fila = list(alcancados)
    while fila:
        atual = fila.pop()
        for outro in vizinhos[atual] - alcancados:
            alcancados.add(outro)
            fila.append(outro)
    soltos = [n for n in nomes if n not in alcancados]
    if soltos:
        erros.append(
            f"Sem caminho até um reservatório: {', '.join(soltos)}. Ligue esses nós à rede por "
            "algum trecho."
        )
    return erros


# ---------------------------------------------------------------------------------------------
# A perda num trecho
# ---------------------------------------------------------------------------------------------
def _perda(t: Trecho, vazao: float, fluido: Fluido) -> tuple[float, float, float | None]:
    """Perda de carga com sinal (m), Reynolds e f, para a vazão ``vazao`` (m³/s, de → para)."""
    d = t.diametro_mm / 1000.0
    velocidade = vazao / t.area_m2
    re = fluido.massa_especifica * abs(velocidade) * d / fluido.viscosidade
    if re < 1e-9:
        # Hagen-Poiseuille: no limite de vazão zero, a perda é linear na vazão.
        linear = 32.0 * fluido.viscosidade * t.comprimento_m / (fluido.massa_especifica * d**2)
        return linear * velocidade / GRAVIDADE, re, None
    f = float(fator_de_atrito(re, t.rugosidade_mm / t.diametro_mm))
    perda = (f * t.comprimento_m / d + t.k_local) * velocidade * abs(velocidade) / (2 * GRAVIDADE)
    return perda, re, f


def _derivada(t: Trecho, vazao: float, fluido: Fluido) -> float:
    passo = max(1e-9, 1e-6 * abs(vazao))
    acima, _, _ = _perda(t, vazao + passo, fluido)
    abaixo, _, _ = _perda(t, vazao - passo, fluido)
    return max((acima - abaixo) / (2 * passo), 1e-9)


def _regime(re: float) -> str:
    if re < RE_LAMINAR:
        return "laminar"
    if re < RE_TURBULENTO:
        return "transição"
    return "turbulento"


# ---------------------------------------------------------------------------------------------
# A solução
# ---------------------------------------------------------------------------------------------
def resolver(
    nos: Sequence[No],
    trechos: Sequence[Trecho],
    fluido: Fluido,
    limites: Limites = Limites(),
) -> ResultadoDaRede:
    erros = problemas(nos, trechos)
    if erros:
        raise ErroDaRede(" ".join(erros))
    if not trechos:
        raise ErroDaRede("A rede precisa de pelo menos um trecho.")
    juncoes = [n for n in nos if not n.reservatorio]
    indice = {n.nome: i for i, n in enumerate(juncoes)}
    fixas = {n.nome: n.carga_fixa_m for n in nos if n.reservatorio}
    m, k = len(trechos), len(juncoes)
    vazoes = np.array([t.area_m2 * 1.0 for t in trechos])  # 1 m/s de → para, para começar
    cargas = np.full(k, float(np.mean(list(fixas.values()))))
    retiradas = np.array([n.retirada_L_s / 1000.0 for n in juncoes])

    def residuos(q: np.ndarray, h: np.ndarray) -> np.ndarray:
        r = np.zeros(m + k)
        for p, t in enumerate(trechos):
            h_de = h[indice[t.de]] if t.de in indice else fixas[t.de]
            h_para = h[indice[t.para]] if t.para in indice else fixas[t.para]
            r[p] = h_de - h_para + t.bomba_m - _perda(t, q[p], fluido)[0]
            if t.para in indice:
                r[m + indice[t.para]] += q[p]
            if t.de in indice:
                r[m + indice[t.de]] -= q[p]
        r[m:] -= retiradas
        return r

    def norma(r: np.ndarray) -> float:
        return max(
            float(np.max(np.abs(r[:m]))) / 1.0, float(np.max(np.abs(r[m:]), initial=0.0)) * 1e3
        )

    atual = residuos(vazoes, cargas)
    iteracoes = 0
    for volta in range(1, _ITERACOES + 1):
        iteracoes = volta
        jacobiana = np.zeros((m + k, m + k))
        for p, t in enumerate(trechos):
            jacobiana[p, p] = -_derivada(t, vazoes[p], fluido)
            if t.de in indice:
                jacobiana[p, m + indice[t.de]] = 1.0
                jacobiana[m + indice[t.de], p] = -1.0
            if t.para in indice:
                jacobiana[p, m + indice[t.para]] = -1.0
                jacobiana[m + indice[t.para], p] = 1.0
        try:
            passo = np.linalg.solve(jacobiana, -atual)
        except np.linalg.LinAlgError as erro:
            raise ErroDaRede(
                "A rede não tem solução única: confira se há nó que só se liga por trecho fechado."
            ) from erro
        fator = 1.0
        for _ in range(30):  # passo de Newton encurtado até o resíduo cair
            q_novo = vazoes + fator * passo[:m]
            h_novo = cargas + fator * passo[m:]
            novo = residuos(q_novo, h_novo)
            if norma(novo) < norma(atual) or fator < 1e-6:
                break
            fator /= 2.0
        vazoes, cargas, atual = q_novo, h_novo, novo
        pequeno = np.max(np.abs(fator * passo[:m])) < _TOLERANCIA_VAZAO
        if pequeno and np.max(np.abs(atual[:m])) < _TOLERANCIA_CARGA:
            break
    else:
        raise ErroDaRede(
            "A conta não convergiu. Confira os dados: diâmetros muito diferentes, bomba que empurra "
            "contra outra ou vazão retirada maior do que a rede consegue levar."
        )
    if not np.all(np.isfinite(vazoes)) or not np.all(np.isfinite(cargas)):
        raise ErroDaRede("A conta deu um valor que não é número: confira os dados da rede.")
    return _resultado(nos, trechos, fluido, limites, vazoes, cargas, iteracoes, indice, fixas)


def _resultado(
    nos: Sequence[No],
    trechos: Sequence[Trecho],
    fluido: Fluido,
    limites: Limites,
    vazoes: np.ndarray,
    cargas: np.ndarray,
    iteracoes: int,
    indice: Mapping[str, int],
    fixas: Mapping[str, float],
) -> ResultadoDaRede:
    peso = fluido.massa_especifica * GRAVIDADE / 1000.0  # kPa por metro de coluna
    maior_nivel = max(fixas.values())
    saida: dict[str, float] = {n.nome: 0.0 for n in nos}
    resultado_trechos = []
    for p, t in enumerate(trechos):
        q = float(vazoes[p])
        perda, re, f = _perda(t, q, fluido)
        saida[t.de] += q
        saida[t.para] -= q
        resultado_trechos.append(
            ResultadoDoTrecho(
                t.nome,
                t.de,
                t.para,
                q * 1000.0,
                abs(q) / t.area_m2,
                abs(perda),
                re,
                f,
                _regime(re),
            )
        )
    resultado_nos = []
    for n in nos:
        carga = fixas[n.nome] if n.reservatorio else float(cargas[indice[n.nome]])
        pressao = carga - n.cota_m
        vazao = saida[n.nome] * 1000.0 if n.reservatorio else n.retirada_L_s
        resultado_nos.append(
            ResultadoDoNo(
                n.nome,
                n.reservatorio,
                n.cota_m,
                carga,
                pressao,
                pressao * peso,
                maior_nivel - n.cota_m,
                vazao,
            )
        )
    verificacoes, avisos = _verificar(resultado_nos, resultado_trechos, trechos, limites)
    return ResultadoDaRede(
        tuple(resultado_nos),
        tuple(resultado_trechos),
        tuple(verificacoes),
        tuple(avisos),
        iteracoes,
        fluido,
        limites,
    )


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _verificar(
    nos: Sequence[ResultadoDoNo],
    trechos: Sequence[ResultadoDoTrecho],
    dados: Sequence[Trecho],
    limites: Limites,
) -> tuple[list[Verificacao], list[str]]:
    linhas: list[Verificacao] = []
    avisos: list[str] = []
    for n in nos:
        if n.reservatorio:
            continue
        linhas.append(
            Verificacao(
                f"Pressão mínima no nó {n.nome}",
                limites.pressao_min_m,
                n.pressao_m,
                "m",
                "Pressão dinâmica com a rede em uso",
                f"p = H − z = {_n(n.carga_m)} − {_n(n.cota_m)} = {_n(n.pressao_m)} m "
                f"({_n(n.pressao_kPa, 1)} kPa) ≥ {_n(limites.pressao_min_m, 1)} m",
                status="NÃO OK" if n.pressao_m < limites.pressao_min_m else "OK",
                tipo="limite",
            )
        )
        if limites.pressao_max_m > 0:
            maior = max(n.pressao_m, n.pressao_estatica_m)
            linhas.append(
                Verificacao(
                    f"Pressão máxima no nó {n.nome}",
                    maior,
                    limites.pressao_max_m,
                    "m",
                    "A maior entre a estática (rede parada) e a dinâmica",
                    f"estática {_n(n.pressao_estatica_m)} m, dinâmica {_n(n.pressao_m)} m "
                    f"≤ {_n(limites.pressao_max_m, 1)} m",
                    tipo="limite",
                )
            )
    for t in trechos:
        linhas.append(
            Verificacao(
                f"Velocidade no trecho {t.nome}",
                t.velocidade,
                limites.velocidade_max,
                "m/s",
                "Velocidade máxima: ruído, erosão e golpe de aríete",
                f"v = Q/A = {_n(abs(t.vazao_L_s), 2)} L/s ÷ A = {_n(t.velocidade)} m/s",
                tipo="limite",
            )
        )
        if limites.velocidade_min > 0 and t.velocidade < limites.velocidade_min:
            avisos.append(
                f"No trecho {t.nome} a água anda a {_n(t.velocidade)} m/s, abaixo de "
                f"{_n(limites.velocidade_min)} m/s: com pouca velocidade a água para e deposita. "
                "Um diâmetro menor resolve, se a pressão deixar."
            )
        if t.regime == "transição":
            avisos.append(
                f"O trecho {t.nome} está na transição entre laminar e turbulento (Re = "
                f"{t.reynolds:.0f}): ali o f não é bem definido."
            )
    for t, d in zip(trechos, dados, strict=True):
        if d.bomba_m > 0 and t.vazao_L_s < 0:
            avisos.append(
                f"No trecho {t.nome} a água corre de {d.para} para {d.de}, contra a bomba: a bomba "
                "não vence a diferença de carga. Confira a altura dela ou ponha uma retenção."
            )
    return linhas, avisos


# ---------------------------------------------------------------------------------------------
# Tabelas, CSV, desenho e registro
# ---------------------------------------------------------------------------------------------
COLUNAS_NOS = (
    "Nó",
    "Tipo",
    "Cota (m)",
    "Carga H (m)",
    "Pressão (m)",
    "Pressão (kPa)",
    "Vazão (L/s)",
)
COLUNAS_TRECHOS = (
    "Trecho",
    "Sentido",
    "Vazão (L/s)",
    "Velocidade (m/s)",
    "Perda (m)",
    "Re",
    "f",
    "Regime",
)


def linhas_dos_nos(r: ResultadoDaRede) -> list[list[object]]:
    return [
        [
            n.nome,
            "Reservatório" if n.reservatorio else "Consumo",
            round(n.cota_m, 3),
            round(n.carga_m, 3),
            round(n.pressao_m, 3),
            round(n.pressao_kPa, 2),
            round(n.vazao_L_s, 3),
        ]
        for n in r.nos
    ]


def linhas_dos_trechos(r: ResultadoDaRede) -> list[list[object]]:
    return [
        [
            t.nome,
            t.sentido,
            round(abs(t.vazao_L_s), 3),
            round(t.velocidade, 3),
            round(t.perda_m, 4),
            round(t.reynolds),
            None if t.atrito is None else round(t.atrito, 5),
            t.regime,
        ]
        for t in r.trechos
    ]


def csv_da_rede(r: ResultadoDaRede) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(COLUNAS_NOS)
    escritor.writerows(linhas_dos_nos(r))
    escritor.writerow(())
    escritor.writerow(COLUNAS_TRECHOS)
    escritor.writerows(linhas_dos_trechos(r))
    return saida.getvalue().encode("utf-8-sig")


def soma_nas_malhas(trechos: Sequence[Trecho], r: ResultadoDaRede) -> float:
    """O maior |Σ perdas com sinal| nas malhas independentes: zero na solução (Hardy Cross)."""
    if not trechos:
        return 0.0
    nomes = sorted({t.de for t in trechos} | {t.para for t in trechos})
    pos = {n: i for i, n in enumerate(nomes)}
    incidencia = np.zeros((len(trechos), len(nomes)))
    for p, t in enumerate(trechos):
        incidencia[p, pos[t.de]] = 1.0
        incidencia[p, pos[t.para]] = -1.0
    # As malhas são o espaço nulo da incidência transposta: combinações de trechos sem pontas.
    _, valores, vt = np.linalg.svd(incidencia.T)
    posto = int(np.sum(valores > 1e-9))
    malhas = vt[posto:]
    if not len(malhas):
        return 0.0
    perdas = np.array(
        [
            math.copysign(t.perda_m, t.vazao_L_s) - d.bomba_m
            for t, d in zip(r.trechos, trechos, strict=True)
        ]
    )
    return float(np.max(np.abs(malhas @ perdas)))


def registro_da_rede(
    nos: Sequence[No], trechos: Sequence[Trecho], r: ResultadoDaRede, responsavel: str = ""
) -> dict[str, Any]:
    geral = r.status
    pior_pressao = min(
        (n for n in r.nos if not n.reservatorio), key=lambda n: n.pressao_m, default=None
    )
    maior_v = max(r.trechos, key=lambda t: t.velocidade, default=None)
    destaque = (
        f"Rede com {len(r.nos)} nós e {len(r.trechos)} trechos: consumo de {_n(r.consumo_L_s)} L/s."
        + (
            f" Menor pressão: {_n(pior_pressao.pressao_m)} m no nó {pior_pressao.nome}."
            if pior_pressao is not None
            else ""
        )
        + (
            f" Maior velocidade: {_n(maior_v.velocidade)} m/s no trecho {maior_v.nome}."
            if maior_v is not None
            else ""
        )
    )
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Rede de tubos — {len(r.nos)} nós e {len(r.trechos)} trechos",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas={
            "fluido": r.fluido.nome,
            "massa_especifica_kg_m3": numero_json(r.fluido.massa_especifica, 4),
            "viscosidade_Pa_s": numero_json(r.fluido.viscosidade, 8),
            "pressao_minima_m": numero_json(r.limites.pressao_min_m, 3),
            "pressao_maxima_m": numero_json(r.limites.pressao_max_m, 3),
            "velocidade_maxima_m_s": numero_json(r.limites.velocidade_max, 3),
            "nos": [
                {
                    "nome": n.nome,
                    "reservatorio": n.reservatorio,
                    "cota_m": numero_json(n.cota_m, 4),
                    "nivel_m": None if n.nivel_m is None else numero_json(n.nivel_m, 4),
                    "retirada_L_s": numero_json(n.retirada_L_s, 5),
                }
                for n in nos
            ],
            "trechos": [
                {
                    "nome": t.nome,
                    "de": t.de,
                    "para": t.para,
                    "comprimento_m": numero_json(t.comprimento_m, 4),
                    "diametro_mm": numero_json(t.diametro_mm, 3),
                    "rugosidade_mm": numero_json(t.rugosidade_mm, 5),
                    "k_local": numero_json(t.k_local, 4),
                    "bomba_m": numero_json(t.bomba_m, 4),
                }
                for t in trechos
            ],
        },
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "destaque_memorial": destaque,
            "tabelas_memorial": [
                {
                    "legenda": "Nós da rede: carga e pressão.",
                    "cabecalhos": list(COLUNAS_NOS),
                    "linhas": [[str(c) for c in linha] for linha in linhas_dos_nos(r)],
                    "fonte": 7.5,
                },
                {
                    "legenda": "Trechos da rede: vazão, velocidade e perda de carga.",
                    "cabecalhos": list(COLUNAS_TRECHOS),
                    "linhas": [
                        ["—" if c is None else str(c) for c in linha]
                        for linha in linhas_dos_trechos(r)
                    ],
                    "fonte": 7.0,
                },
            ],
        },
        metodo=(
            "Energia em cada trecho (Darcy-Weisbach, com f por Colebrook no turbulento e 64/Re no "
            "laminar, mais as perdas localizadas ΣK·v²/2g) e continuidade em cada nó, resolvidas "
            "juntas pelo método de Newton nas vazões e nas cargas (método do gradiente de Todini "
            "e Pilati, o do EPANET). A soma das perdas em cada malha fecha em zero, como em Hardy "
            "Cross."
        ),
        premissas=[
            "Escoamento permanente e incompressível; reservatórios com nível fixo.",
            "Bomba como altura constante no trecho, no sentido de → para.",
            "Rugosidade de tubo novo; com o tempo ela cresce e a perda aumenta.",
        ],
        referencias=[_REFERENCIA],
        conclusao=destaque,
        responsavel=responsavel,
    )


# ---------------------------------------------------------------------------------------------
# A rede desenhada na prancheta
# ---------------------------------------------------------------------------------------------
#: O tipo de cada nó na prancheta.
RESERVATORIO = "reservatorio"
CONSUMO = "consumo"
#: Material que não está na tabela: vale a rugosidade informada no trecho.
OUTRO_MATERIAL = "Outro"


def _numero(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _texto(valor: Any) -> str:
    return "" if valor is None or valor != valor else str(valor).strip()


def comprimento_desenhado(desenho: Mapping[str, Any], trecho: Mapping[str, Any]) -> float:
    """O comprimento do tubo na planta, em metros: a distância entre os dois nós."""
    nos = {str(n.get("id")): n for n in desenho.get("nos") or ()}
    a, b = nos.get(str(trecho.get("de"))), nos.get(str(trecho.get("para")))
    if a is None or b is None:
        return 0.0
    dx = (_numero(b.get("x")) or 0.0) - (_numero(a.get("x")) or 0.0)
    dy = (_numero(b.get("y")) or 0.0) - (_numero(a.get("y")) or 0.0)
    return math.hypot(dx, dy)


def rugosidade_mm(trecho: Mapping[str, Any], rugosidades: Mapping[str, float]) -> float | None:
    """Pelo material (tabela em metros) ou, com o material Outro, a informada em milímetros."""
    material = _texto(trecho.get("material"))
    if material in rugosidades:
        return rugosidades[material] * 1000.0
    return _numero(trecho.get("rugosidade"))


def rede_do_desenho(
    desenho: Mapping[str, Any], rugosidades: Mapping[str, float]
) -> tuple[list[No], list[Trecho], list[str]]:
    """Os nós e os trechos da conta, e o que falta preencher para ela rodar.

    O comprimento do trecho é o desenhado, a não ser que o comprimento real esteja informado (um
    desenho em esquema, fora de escala, ou um tubo que sobe e desce e não aparece na planta).
    """
    faltas: list[str] = []
    nos: list[No] = []
    nomes: dict[str, str] = {}
    for bruto in desenho.get("nos") or ():
        nome = _texto(bruto.get("nome")) or str(bruto.get("id"))
        nomes[str(bruto.get("id"))] = nome
        reservatorio = bruto.get("tipo") == RESERVATORIO
        nos.append(
            No(
                nome,
                _numero(bruto.get("cota")) or 0.0,
                0.0 if reservatorio else (_numero(bruto.get("retirada")) or 0.0),
                reservatorio,
                _numero(bruto.get("nivel")) if reservatorio else None,
                _numero(bruto.get("x")),
                _numero(bruto.get("y")),
            )
        )
    trechos: list[Trecho] = []
    for bruto in desenho.get("trechos") or ():
        nome = _texto(bruto.get("nome")) or str(bruto.get("id"))
        diametro = _numero(bruto.get("diametro"))
        if diametro is None or diametro <= 0:
            faltas.append(f"O tubo {nome} não tem diâmetro: preencha ao lado ou na tabela.")
        rugosidade = rugosidade_mm(bruto, rugosidades)
        if rugosidade is None:
            faltas.append(
                f"O tubo {nome} é de material Outro e não tem a rugosidade: preencha na tabela."
            )
        real = _numero(bruto.get("comprimento"))
        comprimento = (
            real if real is not None and real > 0 else comprimento_desenhado(desenho, bruto)
        )
        if comprimento <= 0:
            faltas.append(
                f"O tubo {nome} tem as duas pontas no mesmo lugar: afaste os nós ou informe o "
                "comprimento real."
            )
        trechos.append(
            Trecho(
                nome,
                nomes.get(str(bruto.get("de")), ""),
                nomes.get(str(bruto.get("para")), ""),
                comprimento,
                diametro or 0.0,
                rugosidade or 0.0,
                _numero(bruto.get("k")) or 0.0,
                _numero(bruto.get("bomba")) or 0.0,
            )
        )
    return nos, trechos, faltas


def marcas_para_o_desenho(desenho: Mapping[str, Any], r: ResultadoDaRede) -> dict[str, Any]:
    """O resultado sobre a prancheta: vazão e velocidade de cada tubo, pressão de cada nó, e o
    que não passa em vermelho. As chaves são os ids do desenho."""
    lim = r.limites
    por_nome_no = {n.nome: n for n in r.nos}
    por_nome_trecho = {t.nome: t for t in r.trechos}
    marcas: dict[str, Any] = {"nos": {}, "trechos": {}}
    for bruto in desenho.get("nos") or ():
        n = por_nome_no.get(_texto(bruto.get("nome")) or str(bruto.get("id")))
        if n is None:
            continue
        if n.reservatorio:
            texto = f"NA {_n(n.carga_m)} m · {_n(n.vazao_L_s)} L/s"
            ruim = False
        else:
            texto = f"p = {_n(n.pressao_m, 1)} m"
            alta = (
                lim.pressao_max_m > 0 and max(n.pressao_m, n.pressao_estatica_m) > lim.pressao_max_m
            )
            ruim = n.pressao_m < lim.pressao_min_m or alta
        marcas["nos"][str(bruto.get("id"))] = {"texto": texto, "ruim": ruim}
    for bruto in desenho.get("trechos") or ():
        t = por_nome_trecho.get(_texto(bruto.get("nome")) or str(bruto.get("id")))
        if t is None:
            continue
        marcas["trechos"][str(bruto.get("id"))] = {
            "texto": f"{_n(abs(t.vazao_L_s))} L/s · {_n(t.velocidade)} m/s",
            "ruim": t.velocidade > lim.velocidade_max,
            "sentido": 1 if t.vazao_L_s >= 0 else -1,
        }
    return marcas


def _no_desenhado(
    id_: str, nome: str, tipo: str, x: float, y: float, **valores: Any
) -> dict[str, Any]:
    reservatorio = tipo == RESERVATORIO
    return {
        "id": id_,
        "nome": nome,
        "tipo": tipo,
        "x": x,
        "y": y,
        "cota": valores.get("cota", 0.0),
        "nivel": valores.get("nivel") if reservatorio else None,
        "retirada": None if reservatorio else valores.get("retirada", 0.0),
    }


def _tubo_desenhado(
    id_: str, nome: str, de: str, para: str, diametro: float, comprimento: float | None = None
) -> dict[str, Any]:
    return {
        "id": id_,
        "nome": nome,
        "de": de,
        "para": para,
        "comprimento": comprimento,
        "diametro": diametro,
        "material": "Aço comercial",
        "rugosidade": None,
        "k": 0.0,
        "bomba": 0.0,
    }


def exemplo_desenhado() -> dict[str, Any]:
    """Duas malhas e dois reservatórios: a caixa principal R1 e a caixa R2, mais baixa.

    O desenho está em escala (metros), e os comprimentos saem dele; o tubo 1 tem o comprimento
    real informado, porque dá voltas que a planta não mostra.
    """
    return {
        "nos": [
            _no_desenhado("n1", "R1", RESERVATORIO, 0.0, 300.0, cota=0.0, nivel=46.0),
            _no_desenhado("n2", "R2", RESERVATORIO, 900.0, 0.0, cota=10.0, nivel=44.0),
            _no_desenhado("n3", "A", CONSUMO, 300.0, 300.0, cota=10.0, retirada=5.0),
            _no_desenhado("n4", "B", CONSUMO, 600.0, 300.0, cota=12.0, retirada=8.0),
            _no_desenhado("n5", "C", CONSUMO, 600.0, 0.0, cota=8.0, retirada=6.0),
            _no_desenhado("n6", "D", CONSUMO, 300.0, 0.0, cota=9.0, retirada=4.0),
        ],
        "trechos": [
            _tubo_desenhado("t1", "1", "n1", "n3", 202.7, comprimento=500.0),
            _tubo_desenhado("t2", "2", "n3", "n4", 154.1),
            _tubo_desenhado("t3", "3", "n4", "n5", 102.3),
            _tubo_desenhado("t4", "4", "n3", "n6", 154.1),
            _tubo_desenhado("t5", "5", "n6", "n5", 102.3),
            _tubo_desenhado("t6", "6", "n4", "n6", 77.9),
            _tubo_desenhado("t7", "7", "n2", "n5", 102.3),
        ],
    }
