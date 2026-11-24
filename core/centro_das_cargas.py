"""Onde a carga de cada caso atua: no plano de cargas e no estudo do SolidWorks, pelo equilíbrio.

A soma das reações diz **quanto** o modelo recebeu; ela não diz **onde**. Uma carga com a soma
certa pode estar no lugar errado: o vento todo no topo dos pilares em vez de ao longo da altura, o
peso do equipamento numa viga do outro lado. Com a reação e a posição de cada pé (o -apoios.csv da
macro dos casos de carga), o equilíbrio dá a resultante das cargas do estudo inteira — força **e
momento** —, sem modelo de rigidez:

    F_aplicada = −Σ R_i        M_aplicado = −Σ (r_i × R_i + M_i)

e daí a linha onde ela atua (o eixo central: o ponto ``q = F × M / |F|²``). O plano de cargas dá a
mesma coisa pelas barras onde cada carga está (as do Modelo em 3D). Comparando:

* carga **vertical** (PP, PE, SC…): o centro dela na planta — x e y;
* carga **horizontal** (vento): a altura em que a resultante atua, acima das bases.

O que o equilíbrio NÃO dá é a divisão da reação entre os pés: com quatro pés a estrutura é
hiperestática e a divisão depende da rigidez das barras e das bases. Por isso a comparação é da
resultante, não pé a pé.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import apoios_do_modelo as am
from core import cena_do_modelo as cm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_por_barras as vpb

Vetor = tuple[float, float, float]

TIPO_VERTICAL = "vertical"
TIPO_HORIZONTAL = "horizontal"
DOMINA = 0.9  # a componente vertical (ou a horizontal) é pelo menos 90 % da força
FOLGA_DA_ALTURA_M = 0.15
FOLGA_DA_ALTURA = 0.10  # 10 % da altura do plano
FOLGA_NA_PLANTA_M = 0.10
FOLGA_NA_PLANTA = 0.05  # 5 % da maior medida da planta
FORA_DO_PLANO_MAXIMO = 0.05  # cargas do plano que não estão em barra do esqueleto: até 5 %
SOMA_DOS_APOIOS = 0.02  # os pés somam a reação total do caso até 2 %


def _mais(a: Vetor, b: Vetor) -> Vetor:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vezes(a: Vetor, k: float) -> Vetor:
    return (a[0] * k, a[1] * k, a[2] * k)


def _vetorial(a: Vetor, b: Vetor) -> Vetor:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norma(a: Vetor) -> float:
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


@dataclass(frozen=True)
class Resultante:
    """Força (kN) e momento (kN·m) em relação à origem da planta."""

    forca: Vetor
    momento: Vetor

    @property
    def eixo_central(self) -> Vetor | None:
        """O ponto da linha de ação mais perto da origem: ``F × M / |F|²``."""
        f2 = _norma(self.forca) ** 2
        if f2 <= 1e-12:
            return None
        return _vezes(_vetorial(self.forca, self.momento), 1.0 / f2)

    @property
    def tipo(self) -> str:
        f = _norma(self.forca)
        if f <= em.REACAO_NULA_kN:
            return ""
        if abs(self.forca[2]) >= DOMINA * f:
            return TIPO_VERTICAL
        if math.hypot(self.forca[0], self.forca[1]) >= DOMINA * f:
            return TIPO_HORIZONTAL
        return ""

    def centro_na_planta(self) -> tuple[float, float] | None:
        """Carga vertical: onde ela atua na planta (x, y)."""
        if abs(self.forca[2]) <= 1e-9:
            return None
        fz = self.forca[2]
        return (-self.momento[1] / fz, self.momento[0] / fz)

    def altura(self) -> float | None:
        """Carga horizontal: a altura (z) em que a resultante atua."""
        fx, fy = self.forca[0], self.forca[1]
        h2 = fx * fx + fy * fy
        if h2 <= 1e-12:
            return None
        return (self.momento[1] * fx - self.momento[0] * fy) / h2


@dataclass(frozen=True)
class ResultanteDoPlano:
    resultante: Resultante
    fora_kN: float  # o que o plano tem e não está numa barra do esqueleto (não entra na conta)
    total_kN: float  # a soma de tudo o que o plano manda


def do_plano(
    plano: pc.PlanoDeCargas,
    codigo: str,
    g: ld.GeometriaDoModelo,
    dados: em.EsforcosDoModelo,
) -> ResultanteDoPlano | None:
    """A resultante das cargas do plano do caso, nas barras do esqueleto onde cada uma está.

    A carga por metro atua no meio do trecho carregado; a concentrada ("kN"), no meio da barra."""
    acao = plano.acao(codigo)
    if acao is None or not g.corpos:
        return None
    corpos = cm._corpos(g)
    nomes = cm.Nomes.do_projeto(g, dados)
    forca: Vetor = (0.0, 0.0, 0.0)
    momento: Vetor = (0.0, 0.0, 0.0)
    fora = total = 0.0
    for carga in acao.cargas:
        vetor = cm._vetor_da_carga(carga)
        if vetor is None or carga.unidade not in ("kN/m", "kN"):
            continue
        nome = nomes.corpo_do_elemento(carga.elemento, corpos)
        if carga.unidade == "kN/m":
            comprimento = carga.comprimento_m if carga.comprimento_m > 0 else None
        else:
            comprimento = 1.0
        if not nome:
            if comprimento is not None:
                valor = _norma(vetor) * comprimento * carga.quantidade
                fora += valor
                total += valor
            continue
        corpo = corpos[nome]
        a = cm._planta(corpo.inicio, dados.eixo_vertical)
        b = cm._planta(corpo.fim, dados.eixo_vertical)
        if carga.unidade == "kN/m":
            a, b, trecho = cm._trecho_da_carga(carga, corpo, a, b)
            f = _vezes(vetor, trecho * carga.quantidade)
        else:
            f = _vezes(vetor, carga.quantidade)
        meio: Vetor = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        forca = _mais(forca, f)
        momento = _mais(momento, _vetorial(meio, f))
        total += _norma(f)
    if total <= 0:
        return None
    return ResultanteDoPlano(Resultante(forca, momento), fora, total)


def do_estudo(
    apoios: am.ApoiosDoModelo,
    codigo: str,
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
) -> Resultante | None:
    """A resultante das cargas que o estudo aplicou, pelas reações e posições dos pés."""
    caso = apoios.casos.get(codigo)
    if caso is None:
        return None
    nos = [n for n in caso.nos if n.ponto is not None]
    if len(nos) < 2:
        return None
    distintos = {tuple(round(v, 6) for v in n.ponto) for n in nos if n.ponto is not None}
    if len(distintos) < len(nos):
        return None  # a macro v12 gravou 0, 0, 0 em todos: sem posição
    escala = am._escala([n.ponto for n in nos if n.ponto is not None], am._pontas(g))
    forca: Vetor = (0.0, 0.0, 0.0)
    momento: Vetor = (0.0, 0.0, 0.0)
    for n in nos:
        assert n.ponto is not None
        r = vpb.para_a_planta([c * escala for c in n.ponto], eixo_vertical)
        f = vpb.para_a_planta([c / 1e3 for c in n.forca_N], eixo_vertical)
        m = vpb.para_a_planta([c / 1e3 for c in n.momento_Nm], eixo_vertical)
        forca = _mais(forca, f)
        momento = _mais(momento, _mais(_vetorial(r, f), m))
    # As reações com o sinal trocado: o que foi aplicado.
    return Resultante(_vezes(forca, -1.0), _vezes(momento, -1.0))


def _nivel_das_bases(apoios: am.ApoiosDoModelo, g: ld.GeometriaDoModelo, eixo: str) -> float:
    alturas = []
    for caso in apoios.casos.values():
        pontos = [n.ponto for n in caso.nos if n.ponto is not None]
        if not pontos:
            continue
        escala = am._escala(pontos, am._pontas(g))
        alturas += [vpb.para_a_planta([c * escala for c in p], eixo)[2] for p in pontos]
    return min(alturas) if alturas else 0.0


def _tamanho_da_planta(g: ld.GeometriaDoModelo, eixo: str) -> float:
    xs, ys = [], []
    for c in g.corpos:
        for p in (c.inicio, c.fim):
            q = vpb.para_a_planta(p, eixo)
            xs.append(q[0])
            ys.append(q[1])
    if not xs:
        return 0.0
    return max(max(xs) - min(xs), max(ys) - min(ys))


@dataclass(frozen=True)
class CentroDoCaso:
    codigo: str
    tipo: str  # TIPO_VERTICAL ou TIPO_HORIZONTAL
    #: vertical: (x, y) na planta; horizontal: (altura acima das bases,)
    plano: tuple[float, ...]
    estudo: tuple[float, ...]
    texto: str
    nivel: str  # pc.NIVEL_OK ou pc.NIVEL_ATENCAO


def comparar(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    apoios: am.ApoiosDoModelo,
    g: ld.GeometriaDoModelo,
    codigos: Sequence[str] | None = None,
) -> list[CentroDoCaso]:
    """Cada caso com reações nos pés e cargas do plano localizadas nas barras: onde a carga atua
    no plano e no estudo. Fica de fora o caso sem posição dos pés, com apoios de outra rodada ou
    com mais de 5 % das cargas do plano fora das barras do esqueleto."""
    if not g.corpos or not apoios.casos:
        return []
    eixo = dados.eixo_vertical
    base = _nivel_das_bases(apoios, g, eixo)
    tamanho = _tamanho_da_planta(g, eixo)
    saida = []
    for codigo in codigos or [a.codigo for a in plano.acoes]:
        caso = dados.casos.get(codigo)
        if caso is None or caso.reacoes is None:
            continue
        do_p = do_plano(plano, codigo, g, dados)
        do_e = do_estudo(apoios, codigo, g, eixo)
        if do_p is None or do_e is None or do_p.fora_kN > FORA_DO_PLANO_MAXIMO * do_p.total_kN:
            continue
        # Os pés somam a reação total do caso? Senão os apoios são de outra rodada.
        total = em.para_o_plano(caso.reacoes.modelo, eixo)
        if _norma(_mais(do_e.forca, total)) > SOMA_DOS_APOIOS * max(_norma(total), 1e-6) + 0.01:
            continue
        tipo_p, tipo_e = do_p.resultante.tipo, do_e.tipo
        if not tipo_p or tipo_p != tipo_e:
            continue
        if tipo_p == TIPO_VERTICAL:
            cp, ce = do_p.resultante.centro_na_planta(), do_e.centro_na_planta()
            if cp is None or ce is None:
                continue
            distancia = math.dist(cp, ce)
            folga = max(FOLGA_NA_PLANTA_M, FOLGA_NA_PLANTA * tamanho)
            onde = (
                f"{codigo}: no plano, o centro da carga fica em x = {_n(cp[0])}, y = {_n(cp[1])} m "
                f"da planta; no estudo, em x = {_n(ce[0])}, y = {_n(ce[1])} m"
            )
            if distancia <= folga:
                saida.append(
                    CentroDoCaso(
                        codigo,
                        tipo_p,
                        cp,
                        ce,
                        f"{onde} — a carga está no lugar do plano.",
                        pc.NIVEL_OK,
                    )
                )
            else:
                saida.append(
                    CentroDoCaso(
                        codigo,
                        tipo_p,
                        cp,
                        ce,
                        f"{onde} — {_n(distancia)} m de diferença: no modelo, a carga está em outro "
                        "lugar (outra viga, outra borda, um equipamento noutra posição), mesmo que "
                        "a soma bata. Confira onde cada carga do caso foi aplicada.",
                        pc.NIVEL_ATENCAO,
                    )
                )
        else:
            hp, he = do_p.resultante.altura(), do_e.altura()
            if hp is None or he is None:
                continue
            hp, he = hp - base, he - base
            folga = max(FOLGA_DA_ALTURA_M, FOLGA_DA_ALTURA * abs(hp))
            onde = (
                f"{codigo}: no plano, a resultante atua a {_n(hp)} m acima das bases; no estudo, a "
                f"{_n(he)} m"
            )
            if abs(hp - he) <= folga:
                texto, nivel = f"{onde} — a carga está na altura do plano.", pc.NIVEL_OK
            else:
                lado = "mais alta" if he > hp else "mais baixa"
                texto = (
                    f"{onde} — no modelo a carga está {lado} ({_n(abs(he - hp))} m): o momento "
                    "nas bases (e o arrancamento dos pés) sai diferente do plano mesmo com a soma "
                    "certa. Confira em que barras a força foi aplicada (só no topo? só num nível?)."
                )
                nivel = pc.NIVEL_ATENCAO
            saida.append(CentroDoCaso(codigo, tipo_p, (hp,), (he,), texto, nivel))
    return saida
