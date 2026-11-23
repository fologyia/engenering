"""A seção do esboço com letras: o teste do desenho e os números que o Montador pede.

Um ``Modelo`` é o esboço resolvido nas medidas de agora, com as letras das cotas soltas. Para cada
conjunto de valores das letras, ele refaz o desenho pelo solver, confere se a forma continua a mesma
(o furo dentro da chapa, nada encostando) e calcula a seção:

* ``faixa(letra)``: de quanto a quanto a letra pode ir sem o desenho deixar de existir, e por quê;
* ``numero(codigo, valores)``: área, inércias, fibra, e quanto cada esforço vale em cada ponto que
  pode mandar, os mesmos pontos da seção desenhada sem letras (fibra externa, junções, linha
  neutra, cantos). J e a tensão de torção saem da malha, só quando a conta pede.

No Montador, a seção é escrita com ``DoDesenho(indice, codigo, d, ...)``: para a sympy é uma letra
positiva; na hora do número, vem daqui. É o mesmo caminho do fator de atrito e das propriedades dos
fluidos. Os resultados de cada conjunto de valores ficam guardados: a busca volta muitas vezes aos
mesmos números.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import sympy as sp

from core import esboco as eb
from core import esboco_regioes as er
from core import geometria_da_secao as gs

# Códigos das contas. Até 99: da seção inteira; 100·p + c: do ponto p.
AREA = 1
IX = 2
IY = 3
IMIN = 4
FIBRA = 5
J = 6
WT = 7  # J/(τ máximo por T): o módulo de torção
FOLGA = 8  # ≥ 0 quando o desenho existe; −1 quando não
Y = 1  # |y| do ponto, do centro de gravidade
X = 2  # |x| do ponto
TVY = 3  # τ por unidade de V_y
TVX = 4  # τ por unidade de V_x
SX = 5  # σ por unidade de M_x no ponto, com o Ixy: |y·I_y − x·I_xy| / (I_x·I_y − I_xy²)
SY = 6  # σ por unidade de M_y no ponto: |x·I_x − y·I_xy| / (I_x·I_y − I_xy²)
#: As medidas com nome (cotas de referência): código MEDIDA + j, da j-ésima delas.
MEDIDA = 20
MAX_MEDIDAS = 60

_POSITIVOS = frozenset({AREA, IX, IY, IMIN, FIBRA, J, WT})
_DA_MALHA = frozenset({J, WT})
_LOTE = 400  # desenhos resolvidos de uma vez
ESCALA_MINIMA = 1e-6  # medida, vezes o tamanho do desenho, abaixo da qual nem se resolve
ESCALA_MAXIMA = 1e2
_GUARDADOS = 20000
_VIZINHOS = 512  # desenhos recentes de onde o próximo pode partir
_TEXTOS = {AREA: "A", IX: "I_x", IY: "I_y", IMIN: "I_{min}", FIBRA: "c", J: "J", WT: "W_t"}
_TEXTOS_DO_PONTO = {Y: "y", X: "x", TVY: "q_y", TVX: "q_x", SX: "W^{-1}_{x", SY: "W^{-1}_{y"}
#: Abaixo disso, vezes I_x + I_y, o I_xy é zero: a seção é simétrica em algum eixo.
SIMETRIA = 1e-6
MARCADO = "marcado"


@dataclass(frozen=True)
class PontoDaSecao:
    """Um ponto que pode mandar. ``vertice``: o vértice do contorno que ele acompanha; no ponto de
    análise (``marcado``), o índice dele em ``esboco.analises``."""

    nome: str
    tipo: str  # fibra, juncao, neutra, fibra_yy, neutra_yy, canto, marcado
    vertice: int = -1
    exige: tuple[str, ...] = ()
    torque: bool = True


def _coeficientes(
    x: np.ndarray, y: np.ndarray, ix: float, iy: float, ixy: float
) -> tuple[np.ndarray, np.ndarray]:
    """σ por unidade de M_x e de M_y em (x, y), do centro de gravidade, em módulo.

    É a flexão em torno de eixos que não são os principais: σ = x·(M_y·I_x − M_x·I_xy)/D +
    y·(M_x·I_y − M_y·I_xy)/D, com D = I_x·I_y − I_xy². Com I_xy = 0, fica y/I_x e x/I_y.
    """
    d = ix * iy - ixy * ixy
    return np.abs(y * iy - x * ixy) / d, np.abs(x * ix - y * ixy) / d


@dataclass(frozen=True)
class FaixaDaLetra:
    """Onde a letra pode andar com as outras paradas. ``None``: sem limite pela forma."""

    letra: str
    valor: float
    minimo: float | None
    maximo: float | None
    motivo_minimo: str
    motivo_maximo: str

    def texto(self) -> str:
        def numero(v: float) -> str:
            return f"{v:.4g}".replace(".", ",")

        partes = []
        if self.minimo is not None and self.minimo > 0.0:
            partes.append(f"de {numero(self.minimo)} mm ({er.motivo_em_texto(self.motivo_minimo)})")
        else:
            partes.append("de quase zero")
        if self.maximo is not None:
            partes.append(
                f"até {numero(self.maximo)} mm ({er.motivo_em_texto(self.motivo_maximo)})"
            )
        else:
            partes.append("sem limite para cima pela forma")
        return f"{self.letra}: " + ", ".join(partes)


@dataclass(frozen=True)
class Medicao:
    q: np.ndarray
    avaliacao: er.Avaliacao


class Modelo:
    """O esboço resolvido nas medidas de agora, pronto para ser refeito com outras medidas."""

    def __init__(self, esboco: eb.Esboco) -> None:
        sistema = eb.Sistema(esboco)
        solucao = eb.resolver(sistema)
        if not bool(solucao.convergiu[0]):
            raise eb.ErroDeEsboco(
                eb._mensagem_de_conflito(esboco, eb.conflitantes(sistema, solucao.q[0]))
            )
        self.esboco = eb.com_q(esboco, sistema, solucao.q[0])
        self.sistema = eb.Sistema(self.esboco)
        self.regioes = er.Regioes(self.sistema)
        self.regioes.exigir()
        tipos = {v.nome: v.tipo for v in self.esboco.variaveis}
        self.tipos = tipos
        self.letras = tuple(
            letra for letra in self.esboco.letras_usadas() if tipos.get(letra) != "angulo"
        )
        self.base = {letra: float(self.esboco.valores()[letra]) for letra in self.letras}
        self.regras = tuple(eb.ler_regra(r) for r in self.esboco.regras)
        self._faixas: dict[str, FaixaDaLetra] = {}
        self.graus = eb.graus_de_liberdade(self.sistema)
        self._guardados: OrderedDict[tuple[float, ...], dict[Any, Any]] = OrderedDict()
        self._pares = self._ligacoes()
        self._memoria_valores: list[np.ndarray] = []
        self._memoria_qs: list[np.ndarray] = []
        self._memoria_suja = False
        self.medidas = self.esboco.medidas_com_nome()[:MAX_MEDIDAS]
        self.simetrica = True
        self.pontos = self._pontos_da_secao()

    # -- desenhos ----------------------------------------------------------------------------------

    def _vetores(self, valores: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], int]:
        brutos = {
            letra: np.asarray(valores.get(letra, self.base[letra]), float) for letra in self.letras
        }
        if not brutos:
            return {}, 1
        vetores = np.broadcast_arrays(*brutos.values())
        k = int(vetores[0].size)
        return {letra: v.reshape(-1) for letra, v in zip(brutos, vetores, strict=True)}, k

    def medir(self, valores: Mapping[str, Any]) -> Medicao:
        """Refaz os k desenhos e confere cada um.

        Medida zero, negativa ou fora da escala do desenho (cem vezes maior que ele, ou um
        milionésimo) nem é resolvida: não forma a mesma seção, e a grade do Montador passa por
        valores assim.
        """
        vetores, k = self._vetores(valores)
        tamanho = self.sistema.tamanho
        serve = np.ones(k, dtype=bool)
        for letra, vetor in vetores.items():
            if self.tipos.get(letra) != "angulo":
                serve &= (vetor > ESCALA_MINIMA * tamanho) & (vetor < ESCALA_MAXIMA * tamanho)
        q = np.tile(self.sistema.q0, (k, 1))
        convergiu = np.zeros(k, dtype=bool)
        indices = np.flatnonzero(serve)
        if len(indices):
            parte = {letra: vetor[indices] for letra, vetor in vetores.items()}
            q_inicial, valores_iniciais = self._partida(parte)
            solucao = eb.resolver(
                self.sistema,
                parte,
                k=len(indices),
                q_inicial=q_inicial,
                valores_iniciais=valores_iniciais,
            )
            q[indices] = solucao.q
            convergiu[indices] = solucao.convergiu
            self._lembrar(parte, solucao)
        return Medicao(q, self._com_regras(self.regioes.avaliar(q, convergiu), vetores, k))

    def _com_regras(
        self, avaliacao: er.Avaliacao, vetores: Mapping[str, np.ndarray], k: int
    ) -> er.Avaliacao:
        """As regras de projeto: o desenho que fura uma delas não existe para o teste."""
        if not self.regras:
            return avaliacao
        e = avaliacao.exatas
        valores: dict[str, Any] = {**self.esboco.valores(), **vetores}
        valores.update(
            parede=avaliacao.folga,
            area=e.area,
            largura=e.x_max - e.x_min,
            altura=e.y_max - e.y_min,
        )
        valido = avaliacao.valido.copy()
        motivo = list(avaliacao.motivo)
        folga = avaliacao.folga.copy()
        for regra in self.regras:
            with np.errstate(all="ignore"):
                margem = np.broadcast_to(np.asarray(eb.folga_da_regra(regra, valores), float), (k,))
            furou = valido & ~(margem >= -1e-9 * self.sistema.tamanho)
            for i in np.flatnonzero(furou):
                motivo[i] = er.REGRA + regra.texto
            valido &= ~furou
        folga = np.where(valido, folga, -1.0)
        return replace(avaliacao, valido=valido, motivo=tuple(motivo), folga=folga)

    def _partida(
        self, parte: Mapping[str, np.ndarray]
    ) -> tuple[np.ndarray | None, dict[str, np.ndarray] | None]:
        """De onde cada desenho parte: do vizinho já resolvido mais perto, se for mais perto que a
        base. Só com o esboço totalmente definido: aí a solução é uma só, e o caminho não muda o
        resultado. Com graus livres, todos partem da base, para o livre andar sempre igual."""
        if not self.graus.definido or not self._memoria_valores or not self.letras:
            return None, None
        if self._memoria_suja:
            self._memoria_k = np.concatenate(self._memoria_valores)
            self._memoria_q = np.concatenate(self._memoria_qs)
            self._memoria_valores, self._memoria_qs = [self._memoria_k], [self._memoria_q]
            self._memoria_suja = False
        conhecidos, qs = self._memoria_k, self._memoria_q
        alvo = np.stack([parte[letra] for letra in self.letras], axis=1)
        base = np.array([self.base[letra] for letra in self.letras])
        escala = np.where(np.abs(base) > 0, np.abs(base), 1.0)
        distancia = np.sum(((alvo[:, None, :] - conhecidos[None, :, :]) / escala) ** 2, axis=2)
        perto = np.argmin(distancia, axis=1)
        da_base = np.sum(((alvo - base) / escala) ** 2, axis=1)
        usar = distancia[np.arange(len(alvo)), perto] < da_base
        q_inicial = np.where(usar[:, None], qs[perto], self.sistema.q0[None, :])
        iniciais = {
            letra: np.where(usar, conhecidos[perto, j], self.base[letra])
            for j, letra in enumerate(self.letras)
        }
        return q_inicial, iniciais

    def _lembrar(self, parte: Mapping[str, np.ndarray], solucao: eb.Solucao) -> None:
        if not self.graus.definido or not self.letras:
            return
        ok = solucao.convergiu
        if not ok.any():
            return
        # Só os mais recentes: na bisseção e no refino, o vizinho útil acabou de ser resolvido.
        self._memoria_valores.append(np.stack([parte[l][ok] for l in self.letras], axis=1))
        self._memoria_qs.append(solucao.q[ok])
        self._memoria_suja = True
        total = sum(len(v) for v in self._memoria_valores)
        if total > 2 * _VIZINHOS:
            k = np.concatenate(self._memoria_valores)[-_VIZINHOS:]
            q = np.concatenate(self._memoria_qs)[-_VIZINHOS:]
            self._memoria_valores, self._memoria_qs = [k], [q]

    def faixa(self, letra: str, valores: Mapping[str, float] | None = None) -> FaixaDaLetra:
        """De quanto a quanto ``letra`` pode ir, com as outras letras em ``valores`` (ou como estão)."""
        if valores is None and letra in self._faixas:
            return self._faixas[letra]
        faixa = self._faixa(letra, valores)
        if valores is None:
            self._faixas[letra] = faixa
        return faixa

    def _faixa(self, letra: str, valores: Mapping[str, float] | None) -> FaixaDaLetra:
        fixos = {**self.base, **(valores or {})}
        v0 = float(fixos[letra])

        def existe(lista: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
            medicao = self.medir({**fixos, letra: lista})
            return medicao.avaliacao.valido, medicao.avaliacao.motivo

        def fronteira(bom: float, ruim: float) -> float:
            for _ in range(6):
                meio = np.linspace(bom, ruim, 18)[1:-1]
                valido, _ = existe(meio)
                ruins = np.flatnonzero(~valido)
                if not len(ruins):
                    bom = float(meio[-1])
                    continue
                primeiro = int(ruins[0])
                ruim = float(meio[primeiro])
                if primeiro > 0:
                    bom = float(meio[primeiro - 1])
            return bom

        subida = v0 * (1.0 + 0.02 * 2.0 ** np.arange(13))
        valido, motivo = existe(subida)
        maximo, motivo_max = None, ""
        ruins = np.flatnonzero(~valido)
        if len(ruins):
            i = int(ruins[0])
            motivo_max = motivo[i]
            maximo = fronteira(v0 if i == 0 else float(subida[i - 1]), float(subida[i]))
        descida = v0 * 0.5 ** (np.arange(1, 31) / 3.0)
        valido, motivo = existe(descida)
        minimo, motivo_min = None, ""
        ruins = np.flatnonzero(~valido)
        if len(ruins):
            i = int(ruins[0])
            motivo_min = motivo[i]
            minimo = fronteira(v0 if i == 0 else float(descida[i - 1]), float(descida[i]))
        return FaixaDaLetra(letra, v0, minimo, maximo, motivo_min, motivo_max)

    # -- números da seção --------------------------------------------------------------------------

    def faixa_de_teste(self, letra: str) -> tuple[float, float, float]:
        """De, até e passo para testar a letra: os do esboço, ou a faixa em que o desenho existe."""
        variavel = next(v for v in self.esboco.variaveis if v.nome == letra)
        v0 = self.base[letra]
        if variavel.de is not None and variavel.ate is not None and variavel.ate > variavel.de:
            de, ate = variavel.de, variavel.ate
        else:
            existe = self.faixa(letra)
            de = max(v0 / 4.0, (existe.minimo or 0.0) * 1.001)
            ate = min(v0 * 3.0, existe.maximo * 0.999) if existe.maximo else v0 * 3.0
            if ate <= de:
                de, ate = v0 * 0.9, v0 * 1.1
        passo = variavel.passo if variavel.passo and variavel.passo > 0 else (ate - de) / 20.0
        return float(de), float(ate), float(passo)

    def _vertices(self, q: np.ndarray) -> np.ndarray:
        return np.concatenate(self.regioes.poligonos(q), axis=1)

    def _ligacoes(self) -> list[tuple[int, int]]:
        """Vértices seguidos de um mesmo contorno, como índices de ``_vertices``."""
        pares, inicio = [], 0
        for poligono in self.regioes.poligonos(self.sistema.q0[None, :]):
            n = poligono.shape[1]
            pares += [(inicio + i, inicio + (i + 1) % n) for i in range(n)]
            inicio += n
        return pares

    def _pontos_da_secao(self) -> tuple[PontoDaSecao, ...]:
        q = self.sistema.q0[None, :]
        medicao = self.regioes.avaliar(q, np.ones(1, dtype=bool)).exatas
        xc, yc = float(medicao.xc[0]), float(medicao.yc[0])
        ix, iy, ixy = float(medicao.ix[0]), float(medicao.iy[0]), float(medicao.ixy[0])
        self.simetrica = abs(ixy) <= SIMETRIA * (ix + iy)
        fx = gs.faixas_da_secao(self.regioes.geometria(q, 0, xc, yc))
        vertices = self._vertices(q)[0] - np.array([xc, yc])
        pontos = [PontoDaSecao("fibra externa", "fibra")]
        marcados = [
            PontoDaSecao(f"ponto {a.nome}", MARCADO, j) for j, a in enumerate(self.esboco.analises)
        ]
        vistos: set[float] = set()
        for i in gs.niveis_de_juncao(fx.y, fx.b):
            y = float(fx.y[i])
            if round(abs(y), 6) in vistos or abs(y) < 1e-9:
                continue
            vistos.add(round(abs(y), 6))
            vertice = int(np.argmin(np.abs(vertices[:, 1] - y)))
            nome = f"junção em y = {y:.4g} mm".replace(".", ",")
            pontos.append(PontoDaSecao(nome, "juncao", vertice))
        pontos.append(PontoDaSecao("linha neutra", "neutra"))
        pontos.append(PontoDaSecao("fibra externa em YY", "fibra_yy", exige=("my",)))
        pontos.append(PontoDaSecao("linha neutra de YY", "neutra_yy", exige=("vx",)))
        if self.simetrica:
            absolutos = np.abs(vertices)
            pesos = (absolutos[:, 0], absolutos[:, 1])
        else:
            # Sem simetria, quem manda com M_x e M_y juntos é quem tem mais σ por unidade de cada
            # um, com o I_xy: num L, a ponta de uma aba, e não o canto do retângulo que a envolve.
            sx, sy = _coeficientes(vertices[:, 0], vertices[:, 1], ix, iy, ixy)
            pesos = (sy, sx)
        if float(pesos[0].max()) > 0.0 and float(pesos[1].max()) > 0.0:
            for k, i in enumerate(gs.cantos_que_mandam(*pesos), start=1):
                pontos.append(PontoDaSecao(f"canto {k}", "canto", i, ("mx", "my"), False))
        return (*pontos, *marcados)

    def _na_fibra(self, rel: np.ndarray, eixo: int, fibra: float) -> float:
        """No nível da fibra, a menor distância ao centro na outra direção (zero se a borda cruza)."""
        outro = 1 - eixo
        folga = 1e-6 * self.sistema.tamanho
        na = np.abs(rel[:, eixo]) >= fibra - folga
        if not na.any():
            na = np.abs(rel[:, eixo]) >= np.abs(rel[:, eixo]).max() - folga
        menor = float(np.abs(rel[na, outro]).min())
        for a, b in self._pares:
            if na[a] and na[b] and rel[a, outro] * rel[b, outro] <= 0.0:
                return 0.0
        return menor

    def _calcular(self, valores: Mapping[str, np.ndarray], k: int) -> list[dict[Any, Any]]:
        """O que sai barato do contorno: área, inércias, fibra e a posição de cada ponto.

        O cortante (faixas) e a torção (malha) ficam para quando a conta pede: na flexão pura,
        a busca nem chega a montar as faixas.
        """
        medicao = self.medir(valores)
        av, q = medicao.avaliacao, medicao.q
        e = av.exatas
        saida: list[dict[Any, Any]] = []
        vertices = self._vertices(q) if av.valido.any() else np.zeros((k, 0, 2))
        marcados = [eb.posicao_da_analise(self.sistema, a, q) for a in self.esboco.analises]
        with np.errstate(all="ignore"):
            medidas = [
                eb.medida_da_cota(self.sistema, cota, q, (e.xc, e.yc)) for cota in self.medidas
            ]
        for i in range(k):
            if not bool(av.valido[i]):
                saida.append({FOLGA: -1.0})
                continue
            xc, yc = float(e.xc[i]), float(e.yc[i])
            ix, iy, ixy = float(e.ix[i]), float(e.iy[i]), float(e.ixy[i])
            rel = vertices[i] - np.array([xc, yc])
            y_fibra = max(float(e.y_max[i]) - yc, yc - float(e.y_min[i]))
            x_fibra = max(float(e.x_max[i]) - xc, xc - float(e.x_min[i]))
            x_na_fibra = self._na_fibra(rel, 1, y_fibra)
            y_na_fibra = self._na_fibra(rel, 0, x_fibra)
            sx_v, sy_v = _coeficientes(rel[:, 0], rel[:, 1], ix, iy, ixy)
            numeros: dict[Any, Any] = {
                AREA: float(e.area[i]),
                IX: ix,
                IY: iy,
                IMIN: float(e.i2[i]),
                FIBRA: y_fibra,
                FOLGA: float(av.folga[i]),
                "_q": q[i].copy(),
                "_centro": (xc, yc),
                "_na_fibra": (x_na_fibra, y_na_fibra),
            }
            for j, medida in enumerate(medidas):
                numeros[MEDIDA + j] = float(medida[i])
            for p, ponto in enumerate(self.pontos, start=1):
                y = x = 0.0
                # Na seção simétrica, os pontos são os de sempre, em módulo; o σ por unidade de
                # momento leva o I_xy no pior sinal, para o caso de uma letra tirar a simetria.
                if ponto.tipo == MARCADO:
                    px, py = marcados[ponto.vertice]
                    x_rel, y_rel = float(px[i]) - xc, float(py[i]) - yc
                    sx, sy = _coeficientes(np.array(x_rel), np.array(y_rel), ix, iy, ixy)
                    numeros[100 * p + SX], numeros[100 * p + SY] = float(sx), float(sy)
                    numeros[("_xy", p)] = (x_rel, y_rel)
                    numeros[100 * p + Y] = abs(y_rel)
                    numeros[100 * p + X] = abs(x_rel)
                    continue
                if not self.simetrica and ponto.tipo in ("fibra", "fibra_yy"):
                    v = int(np.argmax(sx_v if ponto.tipo == "fibra" else sy_v))
                    numeros[100 * p + SX], numeros[100 * p + SY] = float(sx_v[v]), float(sy_v[v])
                if ponto.tipo == "fibra":
                    y, x = y_fibra, x_na_fibra
                elif ponto.tipo == "juncao":
                    y = abs(float(rel[ponto.vertice, 1]))
                    numeros[("_nivel", p)] = float(rel[ponto.vertice, 1])
                elif ponto.tipo == "fibra_yy":
                    y, x = y_na_fibra, x_fibra
                elif ponto.tipo == "canto":
                    x, y = abs(float(rel[ponto.vertice, 0])), abs(float(rel[ponto.vertice, 1]))
                    if not self.simetrica:
                        sx, sy = sx_v[ponto.vertice], sy_v[ponto.vertice]
                        numeros[100 * p + SX], numeros[100 * p + SY] = float(sx), float(sy)
                if ponto.tipo == "juncao" and not self.simetrica:
                    sx, sy = sx_v[ponto.vertice], sy_v[ponto.vertice]
                    numeros[100 * p + SX], numeros[100 * p + SY] = float(sx), float(sy)
                numeros.setdefault(100 * p + SX, _pior(x, y, ix, iy, ixy)[0])
                numeros.setdefault(100 * p + SY, _pior(x, y, ix, iy, ixy)[1])
                numeros[100 * p + Y] = y
                numeros[100 * p + X] = x
            saida.append(numeros)
        return saida

    def _cortante(self, guardado: dict[Any, Any]) -> None:
        """τ por unidade de cortante em cada ponto, pelas faixas da seção."""
        q = guardado["_q"][None, :]
        xc, yc = guardado["_centro"]
        x_na_fibra, y_na_fibra = guardado["_na_fibra"]
        ix, iy = guardado[IX], guardado[IY]
        geometria = self.regioes.geometria(q, 0, xc, yc)
        fx = gs.faixas_da_secao(geometria)
        fy = gs.faixas_da_secao(geometria.deitada())
        for p, ponto in enumerate(self.pontos, start=1):
            tvy = tvx = 0.0
            if ponto.tipo == "fibra":
                tvx = gs.tau_no_nivel(fy, x_na_fibra, iy)
            elif ponto.tipo == "juncao":
                tvy = _tau_na_juncao(fx, guardado[("_nivel", p)], ix)
            elif ponto.tipo == "neutra":
                tvy = gs.tau_no_nivel(fx, 0.0, ix)
            elif ponto.tipo == "fibra_yy":
                tvy = gs.tau_no_nivel(fx, y_na_fibra, ix)
            elif ponto.tipo == "neutra_yy":
                tvx = gs.tau_no_nivel(fy, 0.0, iy)
            elif ponto.tipo == MARCADO:
                x_rel, y_rel = guardado[("_xy", p)]
                tvy = gs.tau_no_nivel(fx, y_rel, ix)
                tvx = gs.tau_no_nivel(fy, x_rel, iy)
            guardado[100 * p + TVY] = tvy
            guardado[100 * p + TVX] = tvx

    def _torcao(self, guardado: dict[Any, Any]) -> None:
        from core import secao_desenhada as sd

        try:
            prop = sd.analisar(self.regioes.partes(guardado["_q"][None, :])).prop
        except sd.ErroDeSecao:
            guardado[J] = guardado[WT] = math.nan
            return
        guardado[J] = prop.j
        guardado[WT] = prop.w_torcao

    def numeros(self, valores: Mapping[str, Any], codigos: Sequence[int]) -> dict[int, np.ndarray]:
        """Os números pedidos para cada conjunto de valores (vetores do mesmo tamanho)."""
        vetores, k = self._vetores(valores)
        chaves = [tuple(float(vetores[letra][i]) for letra in self.letras) for i in range(k)]
        faltam = [i for i, chave in enumerate(chaves) if chave not in self._guardados]
        unicos = list(dict.fromkeys(chaves[i] for i in faltam))
        for inicio in range(0, len(unicos), _LOTE):
            lote = unicos[inicio : inicio + _LOTE]
            lote_valores = {
                letra: np.array([chave[j] for chave in lote]) for j, letra in enumerate(self.letras)
            }
            for chave, numeros in zip(lote, self._calcular(lote_valores, len(lote)), strict=True):
                self._guardados[chave] = numeros
        for chave in dict.fromkeys(chaves):
            self._guardados.move_to_end(chave)  # usado agora: é dos últimos a sair
        saida: dict[int, np.ndarray] = {}
        for codigo in codigos:
            coluna = np.empty(k)
            de_cortante = codigo >= 100 and codigo % 100 in (TVY, TVX)
            for i, chave in enumerate(chaves):
                guardado = self._guardados[chave]
                if codigo not in guardado and guardado.get(FOLGA, -1.0) >= 0.0:
                    if codigo in _DA_MALHA:
                        self._torcao(guardado)
                    elif de_cortante:
                        self._cortante(guardado)
                coluna[i] = guardado.get(codigo, math.nan)
            saida[codigo] = coluna
        # Só depois da resposta: antes, a limpeza podia levar um número desta mesma chamada.
        while len(self._guardados) > max(_GUARDADOS, len(chaves)):
            self._guardados.popitem(last=False)
        return saida

    def numero(self, codigo: int, valores: Mapping[str, Any]) -> np.ndarray:
        return self.numeros(valores, (codigo,))[codigo]


def _pior(x: float, y: float, ix: float, iy: float, ixy: float) -> tuple[float, float]:
    """σ por unidade de M_x e de M_y no pior dos quatro pontos (±x, ±y), com o I_xy."""
    d = ix * iy - ixy * ixy
    return (abs(y) * iy + abs(x) * abs(ixy)) / d, (abs(x) * ix + abs(y) * abs(ixy)) / d


def _tau_na_juncao(faixas: gs.Faixas, nivel: float, inercia: float) -> float:
    """τ por unidade de cortante logo ao lado da junção, no lado estreito (o maior dos dois)."""
    distancia = np.abs(faixas.y - nivel)
    altura = abs(faixas.y_topo - faixas.y_base)
    perto = np.flatnonzero(distancia <= distancia.min() + 3e-7 * max(altura, 1.0))
    valores = [
        abs(float(faixas.q[i])) / (inercia * float(faixas.b[i]))
        for i in perto.tolist()
        if faixas.b[i] > 0
    ]
    return max(valores) if valores else 0.0


# ---------------------------------------------------------------------------
# Registro dos modelos (o Montador fala com eles por um número)
# ---------------------------------------------------------------------------

_MODELOS: dict[int, Modelo] = {}
_POR_IMPRESSAO: dict[str, int] = {}
_NOMES: dict[int, str] = {}


def impressao(esboco: Mapping[str, Any]) -> str:
    return json.dumps(esboco, sort_keys=True, ensure_ascii=False)


def registrar(esboco: Mapping[str, Any], nome: str = "") -> tuple[Modelo, int]:
    """O modelo do esboço, criado uma vez por processo. O índice é o que vai na fórmula."""
    chave = impressao(esboco)
    indice = _POR_IMPRESSAO.get(chave)
    if indice is None:
        modelo = Modelo(eb.esboco_de_dicionario(esboco))
        indice = len(_MODELOS) + 1
        _MODELOS[indice] = modelo
        _POR_IMPRESSAO[chave] = indice
    if nome:
        _NOMES[indice] = nome
    return _MODELOS[indice], indice


def modelo(indice: int) -> Modelo:
    return _MODELOS[int(indice)]


def numero(indice: Any, codigo: Any, *valores: Any) -> Any:
    """O número de ``DoDesenho`` para a conta compilada: aceita números ou vetores."""
    m = _MODELOS.get(int(indice))
    if m is None:
        return math.nan
    arrays = [np.asarray(v, float) for v in valores]
    escalar = all(a.ndim == 0 for a in arrays)
    forma = np.broadcast_shapes(*(a.shape for a in arrays)) if arrays else ()
    resposta = m.numero(int(codigo), dict(zip(m.letras, arrays, strict=False)))
    if escalar:
        return float(resposta[0])
    return resposta.reshape(forma)


def por_que_acaba(expressao: sp.Expr, valores: Mapping[sp.Symbol, float]) -> str:
    """Por que o desenho da expressão deixa de existir com estes valores (vazio se existe)."""
    for atomo in expressao.atoms(DoDesenho):
        m = _MODELOS.get(int(atomo.args[0]))
        if m is None:
            continue
        letras = {str(s): float(valores[s]) for s in atomo.args[2:] if s in valores}
        motivo = m.medir(letras).avaliacao.motivo[0]
        if motivo:
            return er.motivo_em_texto(motivo)
    return ""


def _nome_da_medida(indice: int, j: int) -> str:
    m = _MODELOS.get(indice)
    if m is None or j >= len(m.medidas):
        return "m"
    nome = m.medidas[j].nome
    return nome if len(nome) == 1 else f"\\mathrm{{{nome}}}"


class DoDesenho(sp.Function):
    """Uma conta da seção desenhada com letras: ``DoDesenho(modelo, código, d, ...)``."""

    is_real = True

    @classmethod
    def eval(cls, *args: Any) -> None:
        return None

    def _codigo(self) -> int:
        return int(self.args[1])

    def _eval_is_positive(self) -> bool | None:
        codigo = self._codigo()
        medida = MEDIDA <= codigo < MEDIDA + MAX_MEDIDAS
        return True if codigo in _POSITIVOS or medida else None

    def _eval_is_nonnegative(self) -> bool | None:
        return None if self._codigo() == FOLGA else True

    def _eval_evalf(self, prec: int) -> sp.Float | None:
        if not all(a.is_number for a in self.args):
            return None
        valor = numero(int(self.args[0]), int(self.args[1]), *(float(a) for a in self.args[2:]))
        return sp.Float(valor, prec) if math.isfinite(valor) else None

    def _latex(self, printer: Any, exp: Any = None) -> str:
        codigo = self._codigo()
        if codigo >= 100 and codigo % 100 in (SX, SY):
            texto = f"{_TEXTOS_DO_PONTO[codigo % 100]},{codigo // 100}}}"
        elif codigo >= 100:
            texto = f"{_TEXTOS_DO_PONTO.get(codigo % 100, '?')}_{{{codigo // 100}}}"
        elif MEDIDA <= codigo < MEDIDA + MAX_MEDIDAS:
            texto = _nome_da_medida(int(self.args[0]), codigo - MEDIDA)
        elif codigo == FOLGA:
            texto = r"\mathrm{folga}"
        else:
            texto = _TEXTOS.get(codigo, "?")
        letras = ",\\,".join(printer.doprint(a) for a in self.args[2:])
        texto = f"{texto}\\left({letras}\\right)" if letras else texto
        return f"{texto}^{{{printer.doprint(exp)}}}" if exp is not None else texto
