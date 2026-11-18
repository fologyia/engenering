"""Rede de tubos ao longo do dia (simulação estendida, como no EPANET).

A cada passo (10 min, por padrão) a rede é resolvida em regime permanente pela mesma conta da
página Rede de tubos (:func:`core.rede_de_tubos.resolver`), com o consumo de cada nó multiplicado
pelo fator daquela hora e cada tanque de nível variável no nível daquele instante. Entre um passo e
outro o nível do tanque anda pelo balanço de volume, A·dh/dt = −Q (Q é o que o tanque manda para a
rede). É o método da simulação estendida do EPANET (Rossman, manual do EPANET 2, cap. 3).

Quando um tanque esvazia ou transborda, a simulação para ali e diz quando: na rede real alguém
precisaria fechar uma válvula ou ligar uma bomba, e esta conta não decide isso.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from core import figuras_no_tempo as fnt
from core import rede_de_tubos as rt
from core.animacao import AGUA, Cena, tempo_em_texto, unidade_de_tempo
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

#: Padrão de consumo de EXEMPLO, ilustrativo (média 1,0): pouco de madrugada, picos de manhã e à
#: noite. Não é dado de norma: troque pelo padrão medido ou adotado no projeto.
_BRUTO = (
    0.45, 0.40, 0.38, 0.38, 0.45, 0.70, 1.10, 1.45, 1.40, 1.20, 1.10, 1.10,
    1.20, 1.10, 1.00, 1.00, 1.05, 1.25, 1.50, 1.45, 1.25, 0.95, 0.70, 0.54,
)  # fmt: skip
PADRAO_DE_EXEMPLO = tuple(round(v * len(_BRUTO) / sum(_BRUTO), 3) for v in _BRUTO)
PADRAO_PLANO = tuple(1.0 for _ in range(24))


class ErroDaSimulacao(ValueError):
    """Dado que impede a simulação; a mensagem diz o que corrigir."""


@dataclass(frozen=True, slots=True)
class TanqueDaRede:
    no: str  # nome do reservatório que vira tanque
    area_m2: float
    nivel_min_m: float  # cota da água
    nivel_max_m: float


@dataclass(frozen=True)
class ResultadoNoTempo:
    tempos: np.ndarray  # s
    nomes_nos: tuple[str, ...]
    nomes_trechos: tuple[str, ...]
    tanques: tuple[TanqueDaRede, ...]
    niveis: np.ndarray  # passos × tanques, m
    pressoes: np.ndarray  # passos × nós, m
    vazoes: np.ndarray  # passos × trechos, L/s (positiva de → para)
    velocidades: np.ndarray  # passos × trechos, m/s
    consumo: np.ndarray  # L/s
    multiplicador: np.ndarray
    limites: rt.Limites
    reservatorio: tuple[bool, ...]  # por nó
    evento: str  # o que parou a simulação antes do fim ("" se chegou ao fim)
    verificacoes: tuple[Verificacao, ...]

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    def pior_pressao(self) -> tuple[str, float, float] | None:
        """Nó, pressão (m) e instante (s) da menor pressão do dia nos nós de consumo."""
        consumo = [k for k, r in enumerate(self.reservatorio) if not r]
        if not consumo:
            return None
        bloco = self.pressoes[:, consumo]
        i, j = np.unravel_index(int(np.argmin(bloco)), bloco.shape)
        return self.nomes_nos[consumo[j]], float(bloco[i, j]), float(self.tempos[i])

    def maior_velocidade(self) -> tuple[str, float, float]:
        i, j = np.unravel_index(int(np.argmax(self.velocidades)), self.velocidades.shape)
        return self.nomes_trechos[j], float(self.velocidades[i, j]), float(self.tempos[i])


def _n(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def problemas(
    nos: Sequence[rt.No],
    tanques: Sequence[TanqueDaRede],
    padrao: Sequence[float],
    horas: float,
    passo_min: float,
) -> list[str]:
    erros: list[str] = []
    reservatorios = {n.nome: n for n in nos if n.reservatorio}
    for tanque in tanques:
        no = reservatorios.get(tanque.no)
        if no is None:
            erros.append(f"O tanque {tanque.no} não é um reservatório da rede.")
            continue
        if not tanque.area_m2 > 0:
            erros.append(f"Tanque {tanque.no}: informe a área, maior que zero.")
        if not tanque.nivel_min_m < tanque.nivel_max_m:
            erros.append(f"Tanque {tanque.no}: o nível mínimo precisa ficar abaixo do máximo.")
        elif not tanque.nivel_min_m <= no.carga_fixa_m <= tanque.nivel_max_m:
            erros.append(
                f"Tanque {tanque.no}: o nível de agora ({_n(no.carga_fixa_m)} m) precisa ficar "
                "entre o mínimo e o máximo."
            )
    if not padrao or any(not (math.isfinite(m) and m >= 0) for m in padrao):
        erros.append("O padrão de consumo precisa de multiplicadores maiores ou iguais a zero.")
    if not (math.isfinite(horas) and horas > 0):
        erros.append("Informe a duração em horas, maior que zero.")
    if not (math.isfinite(passo_min) and passo_min > 0):
        erros.append("Informe o passo da conta, maior que zero.")
    return erros


def simular(
    nos: Sequence[rt.No],
    trechos: Sequence[rt.Trecho],
    fluido: rt.Fluido,
    limites: rt.Limites,
    tanques: Sequence[TanqueDaRede],
    padrao: Sequence[float],
    horas: float = 24.0,
    passo_min: float = 10.0,
) -> ResultadoNoTempo:
    erros = problemas(nos, tanques, padrao, horas, passo_min)
    if erros:
        raise ErroDaSimulacao(" ".join(erros))
    dt = passo_min * 60.0
    passos = max(1, math.ceil(horas * 3600.0 / dt))
    nivel = {t.no: next(n.carga_fixa_m for n in nos if n.nome == t.no) for t in tanques}
    nomes_nos = tuple(n.nome for n in nos)
    nomes_trechos = tuple(t.nome for t in trechos)
    tempos, niveis, pressoes, vazoes, velocidades, consumo, mult = [], [], [], [], [], [], []
    evento = ""
    for passo in range(passos + 1):
        t = passo * dt
        fator = float(padrao[int(t // 3600.0) % len(padrao)])
        agora = [
            replace(n, nivel_m=nivel[n.nome])
            if n.nome in nivel
            else (replace(n, retirada_L_s=n.retirada_L_s * fator) if not n.reservatorio else n)
            for n in nos
        ]
        try:
            r = rt.resolver(agora, trechos, fluido, limites)
        except rt.ErroDaRede as erro:
            if passo == 0:
                raise ErroDaSimulacao(str(erro)) from erro
            evento = f"A conta da rede não fechou às {tempo_em_texto(t, unidade_de_tempo(3600 * 24))}: {erro}"
            break
        tempos.append(t)
        niveis.append([nivel[tq.no] for tq in tanques])
        pressoes.append([n.pressao_m for n in r.nos])
        vazoes.append([tr.vazao_L_s for tr in r.trechos])
        velocidades.append([tr.velocidade for tr in r.trechos])
        consumo.append(r.consumo_L_s)
        mult.append(fator)
        if passo == passos:
            break
        por_nome = {n.nome: n for n in r.nos}
        parou = ""
        for tanque in tanques:
            q = por_nome[tanque.no].vazao_L_s / 1000.0  # o que o tanque manda para a rede
            novo = nivel[tanque.no] - q * dt / tanque.area_m2
            if novo < tanque.nivel_min_m:
                parou = f"O tanque {tanque.no} chega ao nível mínimo ({_n(tanque.nivel_min_m)} m)"
                fracao = (nivel[tanque.no] - tanque.nivel_min_m) / max(
                    nivel[tanque.no] - novo, 1e-12
                )
                novo = tanque.nivel_min_m
            elif novo > tanque.nivel_max_m:
                parou = f"O tanque {tanque.no} chega ao nível máximo ({_n(tanque.nivel_max_m)} m) e transborda"
                fracao = (tanque.nivel_max_m - nivel[tanque.no]) / max(
                    novo - nivel[tanque.no], 1e-12
                )
                novo = tanque.nivel_max_m
            nivel[tanque.no] = novo
            if parou:
                quando = t + fracao * dt
                evento = f"{parou} perto de {hora_em_texto(quando)}: a simulação para aí."
                break
        if parou:
            # um último quadro no instante em que o tanque bate no limite
            tempos.append(t + fracao * dt)
            niveis.append([nivel[tq.no] for tq in tanques])
            pressoes.append(pressoes[-1])
            vazoes.append(vazoes[-1])
            velocidades.append(velocidades[-1])
            consumo.append(consumo[-1])
            mult.append(fator)
            break
    resultado_pressoes = np.array(pressoes)
    resultado_velocidades = np.array(velocidades)
    reservatorio = tuple(n.reservatorio for n in nos)
    verificacoes = _verificar(
        nomes_nos,
        reservatorio,
        nomes_trechos,
        resultado_pressoes,
        resultado_velocidades,
        np.array(tempos),
        limites,
        evento,
    )
    return ResultadoNoTempo(
        tempos=np.array(tempos),
        nomes_nos=nomes_nos,
        nomes_trechos=nomes_trechos,
        tanques=tuple(tanques),
        niveis=np.array(niveis).reshape(len(tempos), len(tanques)),
        pressoes=resultado_pressoes,
        vazoes=np.array(vazoes),
        velocidades=resultado_velocidades,
        consumo=np.array(consumo),
        multiplicador=np.array(mult),
        limites=limites,
        reservatorio=reservatorio,
        evento=evento,
        verificacoes=tuple(verificacoes),
    )


def hora_em_texto(segundos: float) -> str:
    total = int(round(segundos / 60.0))
    dias, minutos = divmod(total, 24 * 60)
    h, m = divmod(minutos, 60)
    texto = f"{h:02d}h{m:02d}"
    return texto if dias == 0 else f"{texto} do dia {dias + 1}"


def _verificar(
    nomes_nos: Sequence[str],
    reservatorio: Sequence[bool],
    nomes_trechos: Sequence[str],
    pressoes: np.ndarray,
    velocidades: np.ndarray,
    tempos: np.ndarray,
    limites: rt.Limites,
    evento: str,
) -> list[Verificacao]:
    linhas: list[Verificacao] = []
    for k, nome in enumerate(nomes_nos):
        if reservatorio[k]:
            continue
        i = int(np.argmin(pressoes[:, k]))
        menor = float(pressoes[i, k])
        linhas.append(
            Verificacao(
                f"Pressão mínima no nó {nome} ao longo do dia",
                limites.pressao_min_m,
                menor,
                "m",
                "Pressão dinâmica com o consumo de cada hora",
                f"menor pressão {_n(menor)} m às {hora_em_texto(float(tempos[i]))} ≥ {_n(limites.pressao_min_m, 1)} m",
                status="NÃO OK" if menor < limites.pressao_min_m else "OK",
                tipo="limite",
            )
        )
        if limites.pressao_max_m > 0:
            j = int(np.argmax(pressoes[:, k]))
            maior = float(pressoes[j, k])
            linhas.append(
                Verificacao(
                    f"Pressão máxima no nó {nome} ao longo do dia",
                    maior,
                    limites.pressao_max_m,
                    "m",
                    "Pressão dinâmica com o consumo de cada hora (a estática está na Rede de tubos)",
                    f"maior pressão {_n(maior)} m às {hora_em_texto(float(tempos[j]))} ≤ {_n(limites.pressao_max_m, 1)} m",
                    tipo="limite",
                )
            )
    for k, nome in enumerate(nomes_trechos):
        i = int(np.argmax(velocidades[:, k]))
        linhas.append(
            Verificacao(
                f"Velocidade no trecho {nome} ao longo do dia",
                float(velocidades[i, k]),
                limites.velocidade_max,
                "m/s",
                "Velocidade máxima: ruído, erosão e golpe de aríete",
                f"maior velocidade {_n(float(velocidades[i, k]))} m/s às {hora_em_texto(float(tempos[i]))}",
                tipo="limite",
            )
        )
    if evento:
        linhas.append(
            Verificacao(
                "Tanques dentro dos níveis o tempo todo",
                None,
                None,
                "",
                "Nível de cada tanque entre o mínimo e o máximo",
                evento,
                status="NÃO OK",
                tipo="limite",
            )
        )
    return linhas


# ---------------------------------------------------------------------------------------------
# Cena e registro
# ---------------------------------------------------------------------------------------------
def cena_da_rede(desenho: Mapping[str, Any], r: ResultadoNoTempo) -> dict[str, Any]:
    posicoes: dict[str, tuple[float, float]] = {}
    for bruto in desenho.get("nos") or ():
        nome = str(bruto.get("nome") or bruto.get("id"))
        posicoes[nome] = (float(bruto.get("x") or 0.0), float(bruto.get("y") or 0.0))
    xs = [p[0] for p in posicoes.values()] or [0.0, 1.0]
    ys = [p[1] for p in posicoes.values()] or [0.0, 1.0]
    extensao = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    cena = Cena(
        r.tempos,
        id=f"rede-{hash((r.nomes_nos, r.nomes_trechos, r.tempos.tobytes())) & 0xFFFFFFFF:x}",
        altura=430,
    )
    v_max = max(float(r.velocidades.max(initial=0.0)), 1e-6)
    esc = cena.escala("Velocidade", "m/s", 0.0, v_max, cores=AGUA, casas=2)
    trechos_desenho = {str(t.get("nome") or t.get("id")): t for t in desenho.get("trechos") or ()}
    nomes_por_id = {
        str(n.get("id")): str(n.get("nome") or n.get("id")) for n in desenho.get("nos") or ()
    }
    for k, nome in enumerate(r.nomes_trechos):
        bruto = trechos_desenho.get(nome)
        if bruto is None:
            continue
        a = posicoes.get(nomes_por_id.get(str(bruto.get("de")), ""))
        b = posicoes.get(nomes_por_id.get(str(bruto.get("para")), ""))
        if a is None or b is None:
            continue
        sinal = np.sign(r.vazoes[:, k])
        canal_v = cena.canal(r.velocidades[:, k] * np.where(sinal == 0, 1.0, sinal))
        canal_cor = cena.canal(r.velocidades[:, k])
        cena.linha(
            [a, b],
            largura=9,
            escala=esc,
            canal=canal_cor,
            fluxo=canal_v,
            fluxo_ref=v_max,
            nome=f"Tubo {nome}",
            setas=True,
            espaco_setas=70,
            cor_setas="#ffffff",
            contorno_setas="#0d366b",
        )
        meio = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        cena.texto(meio[0], meio[1], f"{nome}", tamanho=10, dy=-10, cor="#475569")
    lado = 0.06 * extensao
    tanques = {t.no: k for k, t in enumerate(r.tanques)}
    for k, nome in enumerate(r.nomes_nos):
        x, y = posicoes.get(nome, (0.0, 0.0))
        if r.reservatorio[k]:
            caixa = (x - lado / 2, y - lado / 2, x + lado / 2, y + lado / 2)
            if nome in tanques:
                tq = r.tanques[tanques[nome]]
                faixa = tq.nivel_max_m - tq.nivel_min_m
                altura = (r.niveis[:, tanques[nome]] - tq.nivel_min_m) / faixa * lado
                cena.nivel(caixa, cena.canal(altura), cor="#3987e5")
                texto_nivel = cena.canal(r.niveis[:, tanques[nome]])
                cena.texto(
                    x,
                    y + lado * 0.75,
                    f"{nome} · NA {{}} m",
                    canal=texto_nivel,
                    casas=2,
                    tamanho=11,
                    negrito=True,
                    base="bottom",
                )
            else:
                cena.retangulo(*caixa, cor="#3987e5")
                cena.texto(
                    x,
                    y + lado * 0.75,
                    f"{nome} (nível fixo)",
                    tamanho=11,
                    negrito=True,
                    base="bottom",
                )
            cena.retangulo(*caixa, vazio=True, contorno="texto", espessura=1.5)
        else:
            cena.circulo(x, y, raio_px=7, cor="#ffffff", contorno="texto")
            canal_p = cena.canal(r.pressoes[:, k])
            cena.texto(
                x, y, f"{nome}: {{}} m", canal=canal_p, casas=1, tamanho=11, dy=-14, negrito=True
            )
    folga = 0.12 * extensao
    cena.vista = (min(xs) - folga, min(ys) - folga, max(xs) + folga, max(ys) + folga)
    if r.tanques:
        cena.grafico_no_tempo(
            "Nível dos tanques", "m",
            [(t.no, cena.canal(r.niveis[:, k])) for k, t in enumerate(r.tanques[:8])],
            casas=2,
        )  # fmt: skip
    consumo_nos = [k for k, e in enumerate(r.reservatorio) if not e]
    piores = sorted(consumo_nos, key=lambda k: float(r.pressoes[:, k].min()))[:4]
    if piores:
        cena.grafico_no_tempo(
            "Pressão nos nós mais baixos", "m",
            [(r.nomes_nos[k], cena.canal(r.pressoes[:, k])) for k in piores],
            casas=1, limites=[("pressão mínima", r.limites.pressao_min_m)],
            marcos=[("menor pressão", (r.pior_pressao() or ("", 0.0, None))[2])],
        )  # fmt: skip
    cena.grafico_no_tempo("Consumo da rede", "L/s", [("Consumo", cena.canal(r.consumo))], casas=2)
    cena.nota = "Cor dos tubos: a velocidade da água; setas brancas: o sentido em que ela corre, andando com ela."
    return cena.como_dados()


def registro(
    r: ResultadoNoTempo, padrao: Sequence[float], horas: float, passo_min: float
) -> dict[str, Any]:
    u = unidade_de_tempo(float(r.tempos[-1]) if len(r.tempos) else 3600.0)
    pior = r.pior_pressao()
    veloz = r.maior_velocidade()
    destaque = f"Rede ao longo de {_n(horas, 1)} h, passo de {_n(passo_min, 0)} min:"
    if pior is not None:
        destaque += (
            f" menor pressão de {_n(pior[1])} m no nó {pior[0]} às {hora_em_texto(pior[2])};"
        )
    destaque += f" maior velocidade de {_n(veloz[1])} m/s no trecho {veloz[0]} às {hora_em_texto(veloz[2])}."
    if r.evento:
        destaque += f" {r.evento}"
    figuras = []
    if r.tanques:
        figuras.append(
            fnt.linhas_para_o_registro(
                "Nível dos tanques",
                "Nível da água de cada tanque ao longo do dia.",
                f"tempo ({u.rotulo})",
                "m",
                [
                    fnt.Serie(t.no, tuple(r.tempos / u.fator), tuple(r.niveis[:, k]))
                    for k, t in enumerate(r.tanques)
                ],
            )  # fmt: skip
        )
    consumo_nos = [k for k, e in enumerate(r.reservatorio) if not e]
    piores = sorted(consumo_nos, key=lambda k: float(r.pressoes[:, k].min()))[:4]
    if piores:
        figuras.append(
            fnt.linhas_para_o_registro(
                "Pressão nos nós mais baixos",
                "Pressão dos nós de menor pressão ao longo do dia.",
                f"tempo ({u.rotulo})",
                "m",
                [
                    fnt.Serie(r.nomes_nos[k], tuple(r.tempos / u.fator), tuple(r.pressoes[:, k]))
                    for k in piores
                ],
                [("pressão mínima", r.limites.pressao_min_m)],
            )  # fmt: skip
        )
    linhas_tabela = [
        [
            hora_em_texto(float(r.tempos[i])),
            _n(float(r.consumo[i]), 2),
            *[_n(float(r.niveis[i, k]), 2) for k in range(len(r.tanques))],
        ]
        for i in np.linspace(0, len(r.tempos) - 1, min(len(r.tempos), 13)).round().astype(int)
    ]
    geral = r.status
    return criar_registro_tecnico(
        modulo="Rede de tubos",
        modulo_id=rt.MODULO_ID,
        titulo=f"Rede de tubos ao longo do dia — {len(r.nomes_nos)} nós",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas={
            "horas": numero_json(horas, 3),
            "passo_min": numero_json(passo_min, 3),
            "padrao_de_consumo": [numero_json(m, 4) for m in padrao],
            "tanques": [
                {
                    "no": t.no,
                    "area_m2": numero_json(t.area_m2, 4),
                    "nivel_min_m": numero_json(t.nivel_min_m, 4),
                    "nivel_max_m": numero_json(t.nivel_max_m, 4),
                }
                for t in r.tanques
            ],
        },
        resultados={
            "status_geral": geral,
            "destaque_memorial": destaque,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "tabelas_memorial": [
                {
                    "legenda": "Consumo da rede e nível dos tanques ao longo do dia.",
                    "cabecalhos": ["Hora", "Consumo (L/s)", *[f"NA {t.no} (m)" for t in r.tanques]],
                    "linhas": linhas_tabela,
                    "fonte": 8.0,
                }
            ],
            fnt.CHAVE: figuras,
        },
        metodo=(
            "Simulação estendida: a cada passo, a rede em regime permanente (Darcy-Weisbach e "
            "Colebrook, Newton nas vazões e cargas) com o consumo daquela hora e o nível de cada "
            "tanque naquele instante; entre os passos, o nível anda por A·dh/dt = −Q."
        ),
        premissas=[
            "Em cada passo a rede está em regime permanente: sem inércia da água nem golpe de "
            "aríete entre um passo e outro.",
            "Consumo de cada nó multiplicado pelo fator da hora; fator constante dentro da hora.",
            "Tanque de parede vertical (área constante); reservatório sem tanque marcado fica com o "
            "nível fixo.",
            "Bomba como altura constante no trecho, sem curva nem liga e desliga.",
        ],
        referencias=[
            "Rossman, L. A. EPANET 2 Users Manual. U.S. EPA, 2000 (cap. 3: simulação estendida).",
            "Darcy-Weisbach e Colebrook; Newton (Todini e Pilati, 1988).",
        ],
        conclusao=destaque,
    )
