"""Do desenho da peça para o pórtico plano: nós, barras, apoios e cargas tirados dos trechos.

O desenho do equilíbrio (:mod:`core.equilibrio_corpo`) trata a peça como um corpo rígido: dá as
reações quando a estática basta. Aqui os mesmos trechos viram barras de um pórtico
(:mod:`core.portico_plano`), e saem N, V e M ao longo de cada barra, a deformada e as reações mesmo
quando há apoio de sobra (peça hiperestática), que dependem da rigidez das barras.

Dois caminhos:

* **Pelos apoios** (o normal): cada apoio do desenho vira uma restrição do pórtico. Apoio simples,
  cabo e apoio com atrito só trabalham de um lado: se a conta pede o outro lado, o apoio sai e a
  conta é refeita.
* **Pelas reações**: com apoio distribuído, a pressão ao longo do trecho só vale para a peça
  rígida. Se a estática já deu as reações, elas entram como cargas e a estrutura fica presa em
  três movimentos só para não correr (as reações desses três dão zero).

Os trechos se ligam onde uma ponta toca outra barra, e a ligação é rígida, salvo rótula marcada.
Dois trechos que só se cruzam pelo meio não se ligam. Forças em newtons e medidas em metros na
entrada; o pórtico sai na unidade de força pedida.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import equilibrio_corpo as eq
from core import portico_plano as pp

PELOS_APOIOS = "apoios"
PELAS_REACOES = "reacoes"

#: Seção usada quando o usuário não escolhe: só pesa nas peças hiperestáticas e na deformada.
E_ACO_N_M2 = 200e9
AREA_PADRAO_M2 = 2.0e-3
INERCIA_PADRAO_M4 = 8.0e-6


class SemDiagramas(ValueError):
    """O desenho não vira pórtico; a mensagem diz o que falta."""


@dataclass(frozen=True)
class Rigidez:
    """Seção de um trecho, em SI: E em N/m², A em m² e I em m⁴."""

    nome: str = "Seção padrão"
    area_m2: float = AREA_PADRAO_M2
    inercia_m4: float = INERCIA_PADRAO_M4
    e_N_m2: float = E_ACO_N_M2
    rotula_inicio: bool = False
    rotula_fim: bool = False


@dataclass(frozen=True)
class ReacaoDoApoio:
    """A força que o apoio faz na peça, em N e N·m. ``solto``: apoio de um lado só que saiu."""

    apoio: eq.Apoio
    no: str
    fx: float
    fy: float
    m: float
    solto: bool = False

    @property
    def modulo(self) -> float:
        return math.hypot(self.fx, self.fy)


@dataclass(frozen=True)
class Analise:
    resultado: pp.ResultadoPortico
    caminho: str
    newton: float  # quantos newtons vale a unidade de força do pórtico
    trecho_da_barra: dict[str, int]  # nome da barra → número do trecho (a partir de 1)
    reacoes: tuple[ReacaoDoApoio, ...]
    avisos: tuple[str, ...] = ()

    @property
    def nos(self) -> tuple[pp.No, ...]:
        return self.resultado.portico.nos


# ---------------------------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------------------------
class _Nos:
    def __init__(self, tolerancia: float) -> None:
        self.tolerancia = tolerancia
        self.pontos: list[tuple[float, float]] = []

    def de(self, x: float, y: float) -> int:
        for i, (px, py) in enumerate(self.pontos):
            if math.hypot(px - x, py - y) <= self.tolerancia:
                return i
        self.pontos.append((x, y))
        return len(self.pontos) - 1

    def nome(self, indice: int) -> str:
        return f"N{indice + 1}"


def _no_trecho(ponto: tuple[float, float], t: eq.Trecho, tolerancia: float) -> float | None:
    """Posição do ponto ao longo do trecho (0 a 1), ou ``None`` se ele está fora."""
    dx, dy = t.x2 - t.x1, t.y2 - t.y1
    comprimento = math.hypot(dx, dy)
    if comprimento <= tolerancia:
        return None
    s = ((ponto[0] - t.x1) * dx + (ponto[1] - t.y1) * dy) / comprimento**2
    afastamento = abs((ponto[0] - t.x1) * dy - (ponto[1] - t.y1) * dx) / comprimento
    folga = tolerancia / comprimento
    if afastamento > tolerancia or s < -folga or s > 1.0 + folga:
        return None
    return min(1.0, max(0.0, s))


def _pontos_do_apoio(a: eq.Apoio) -> list[tuple[float, float]]:
    if a.distribuido:
        return [(a.x, a.y), (a.x2 or 0.0, a.y2 or 0.0)]
    return [(a.x, a.y)]


def _pontos_da_carga(c: eq.Carga) -> list[tuple[float, float]]:
    if c.tipo == eq.DISTRIBUIDA:
        return [(c.x, c.y), (c.x2, c.y2)]
    return [(c.x, c.y)]


@dataclass
class _Malha:
    nos: _Nos
    barras: list[pp.Barra]
    trecho_da_barra: dict[str, int]
    pontas: dict[str, tuple[int, int]]  # barra → (nó i, nó j)
    usados: set[int]

    def no_da_peca(self, ponto: tuple[float, float], quem: str) -> str:
        indice = self.nos.de(*ponto)
        if indice not in self.usados:
            raise SemDiagramas(
                f"{quem} não está sobre nenhum trecho da peça. Para ver os esforços nas barras, "
                "ligue esse ponto à peça com um trecho."
            )
        return self.nos.nome(indice)


def _malha(
    problema: eq.Problema,
    extras: Sequence[tuple[float, float]],
    secoes: Sequence[pp.Secao],
    rotulas: Sequence[tuple[bool, bool]],
) -> _Malha:
    trechos = problema.trechos
    if not trechos:
        raise SemDiagramas(
            "Desenhe a peça com trechos (as barras) para ver N, V e M ao longo dela."
        )
    xs = [v for t in trechos for v in (t.x1, t.x2)]
    ys = [v for t in trechos for v in (t.y1, t.y2)]
    tamanho = max(max(xs) - min(xs), max(ys) - min(ys))
    if tamanho <= 0.0:
        raise SemDiagramas("Os trechos da peça têm comprimento zero.")
    tolerancia = 1e-6 * tamanho
    nos = _Nos(tolerancia)

    interesse: list[tuple[float, float]] = [
        p for t in trechos for p in ((t.x1, t.y1), (t.x2, t.y2))
    ]
    for a in problema.apoios:
        interesse += _pontos_do_apoio(a)
    for c in problema.cargas:
        interesse += _pontos_da_carga(c)
    interesse += list(extras)

    barras: list[pp.Barra] = []
    trecho_da_barra: dict[str, int] = {}
    pontas: dict[str, tuple[int, int]] = {}
    feitas: set[frozenset[int]] = set()
    usados: set[int] = set()
    for k, t in enumerate(trechos):
        if math.hypot(t.x2 - t.x1, t.y2 - t.y1) <= tolerancia:
            continue
        cortes: dict[int, float] = {}
        for ponto in interesse:
            s = _no_trecho(ponto, t, tolerancia)
            if s is not None:
                cortes.setdefault(nos.de(*ponto), s)
        ordem = sorted(cortes, key=lambda i: cortes[i])
        pares = [
            (i, j)
            for i, j in zip(ordem, ordem[1:], strict=False)
            if frozenset((i, j)) not in feitas
        ]
        letras = len(pares) > 1
        for parte, (i, j) in enumerate(pares):
            feitas.add(frozenset((i, j)))
            nome = f"B{k + 1}" + (chr(ord("a") + parte % 26) if letras else "")
            if letras and parte >= 26:
                nome += str(parte // 26)
            barras.append(
                pp.Barra(
                    nome,
                    nos.nome(i),
                    nos.nome(j),
                    secoes[k],
                    rotula_i=rotulas[k][0] and i == ordem[0],
                    rotula_j=rotulas[k][1] and j == ordem[-1],
                )
            )
            trecho_da_barra[nome] = k + 1
            pontas[nome] = (i, j)
            usados.update((i, j))
    if not barras:
        raise SemDiagramas("Os trechos da peça têm comprimento zero.")

    # As barras precisam formar uma peça só.
    grupo = list(range(len(nos.pontos)))

    def raiz(i: int) -> int:
        while grupo[i] != i:
            grupo[i] = grupo[grupo[i]]
            i = grupo[i]
        return i

    for i, j in pontas.values():
        grupo[raiz(i)] = raiz(j)
    pecas = len({raiz(i) for i in usados})
    if pecas > 1:
        raise SemDiagramas(
            f"Os trechos formam {pecas} partes que não se tocam. Para os esforços nas barras, a "
            "peça precisa ser uma só: encoste a ponta de um trecho no outro."
        )
    return _Malha(nos, barras, trecho_da_barra, pontas, usados)


# ---------------------------------------------------------------------------------------------
# Cargas
# ---------------------------------------------------------------------------------------------
def _distribuidas(
    malha: _Malha, c: eq.Carga, newton: float, nome: str
) -> list[pp.CargaDistribuida]:
    """A carga distribuída repartida pelas barras que ficam debaixo dela."""
    dx, dy = c.x2 - c.x, c.y2 - c.y
    comprimento = math.hypot(dx, dy)
    tolerancia = malha.nos.tolerancia
    alvo = eq.Trecho(c.x, c.y, c.x2, c.y2)
    ux, uy = eq.eixo(c.angulo)
    cargas: list[pp.CargaDistribuida] = []
    coberto = 0.0
    for barra in malha.barras:
        i, j = malha.pontas[barra.nome]
        si = _no_trecho(malha.nos.pontos[i], alvo, tolerancia)
        sj = _no_trecho(malha.nos.pontos[j], alvo, tolerancia)
        if si is None or sj is None:
            continue
        coberto += abs(sj - si) * comprimento
        qi = (c.valor + (c.valor2 - c.valor) * si) / newton
        qj = (c.valor + (c.valor2 - c.valor) * sj) / newton
        for direcao, fator in ((pp.GLOBAL_X, ux), (pp.GLOBAL_Y, uy)):
            if abs(fator) > 1e-12 and (qi or qj):
                cargas.append(
                    pp.CargaDistribuida(barra.nome, qi * fator, qj * fator, direcao, nome)
                )
    if coberto < comprimento * (1.0 - 1e-6):
        raise SemDiagramas(
            f"{nome}: parte da carga distribuída fica fora dos trechos da peça. Para os esforços "
            "nas barras, a carga precisa correr em cima de um trecho."
        )
    return cargas


def _cargas(
    malha: _Malha, cargas: Sequence[eq.Carga], newton: float
) -> tuple[list[pp.CargaNodal], list[pp.CargaDistribuida]]:
    nodais: list[pp.CargaNodal] = []
    distribuidas: list[pp.CargaDistribuida] = []
    for c in cargas:
        if c.tipo == eq.DISTRIBUIDA:
            malha.no_da_peca((c.x, c.y), f"O começo da carga {c.nome}")
            malha.no_da_peca((c.x2, c.y2), f"O fim da carga {c.nome}")
            distribuidas += _distribuidas(malha, c, newton, c.nome)
            continue
        a = eq.acao_da_carga(c)
        no = malha.no_da_peca((c.x, c.y), f"A carga {c.nome}")
        nodais.append(pp.CargaNodal(no, a.fx / newton, a.fy / newton, a.m / newton))
    return nodais, distribuidas


# ---------------------------------------------------------------------------------------------
# Apoios
# ---------------------------------------------------------------------------------------------
def _restricao(a: eq.Apoio, no: str) -> pp.Apoio:
    giro = eq.angulo_de(*a.direcao)
    if a.tipo == eq.PINO:
        return pp.Apoio(no, True, True, False)
    if a.tipo == eq.ENGASTE:
        return pp.Apoio(no, True, True, True)
    if a.tipo == eq.GUIA:
        return pp.Apoio(no, True, False, True, giro)
    if a.tipo == eq.ATRITO:
        return pp.Apoio(no, True, True, False, giro)
    return pp.Apoio(no, True, False, False, giro)


_DE_UMA_DIRECAO = (eq.ROLETE, eq.BIELA, eq.SIMPLES, eq.CABO)


def _mesmo_ponto(apoios: Sequence[eq.Apoio]) -> SemDiagramas:
    nomes = " e ".join(a.nome for a in apoios)
    return SemDiagramas(
        f"Os apoios {nomes} estão no mesmo ponto. Para os esforços nas barras, troque por um só: "
        "dois apoios de uma direção, em direções diferentes, já fazem um pino."
    )


def _par(apoios: Sequence[eq.Apoio]) -> float:
    """Determinante das duas direções: zero quando os dois apoios são paralelos."""
    (ax, ay), (bx, by) = apoios[0].direcao, apoios[1].direcao
    return ax * by - ay * bx


def _restricao_do_no(no: str, apoios: Sequence[eq.Apoio]) -> pp.Apoio:
    if len(apoios) == 1:
        return _restricao(apoios[0], no)
    if (
        len(apoios) != 2
        or any(a.tipo not in _DE_UMA_DIRECAO for a in apoios)
        or abs(_par(apoios)) < 1e-6
    ):
        raise _mesmo_ponto(apoios)
    return pp.Apoio(no, True, True, False)


def _parte_de_cada_um(r: pp.Reacao, apoios: Sequence[eq.Apoio]) -> list[tuple[float, float, float]]:
    """A reação do nó repartida entre os apoios que estão nele: (fx, fy, m) de cada um."""
    if len(apoios) == 1:
        return [(r.rx, r.ry, r.mz)]
    (ax, ay), (bx, by) = apoios[0].direcao, apoios[1].direcao
    det = _par(apoios)
    na = (r.rx * by - r.ry * bx) / det
    nb = (ax * r.ry - ay * r.rx) / det
    return [(na * ax, na * ay, 0.0), (nb * bx, nb * by, 0.0)]


def _pelos_apoios(
    problema: eq.Problema,
    malha: _Malha,
    nodais: list[pp.CargaNodal],
    distribuidas: list[pp.CargaDistribuida],
    newton: float,
) -> tuple[pp.ResultadoPortico, tuple[ReacaoDoApoio, ...], list[str]]:
    nos_do_pp = tuple(
        pp.No(malha.nos.nome(i), x, y)
        for i, (x, y) in enumerate(malha.nos.pontos)
        if i in malha.usados
    )
    apoios = problema.apoios
    onde = [malha.no_da_peca((a.x, a.y), f"O apoio {a.nome}") for a in apoios]
    de_um_lado = [i for i, a in enumerate(apoios) if a.tipo in eq.SO_UM_LADO]
    ativos = set(range(len(apoios)))
    avisos: list[str] = []

    def no_no(no: str) -> list[int]:
        return [i for i in sorted(ativos) if onde[i] == no]

    def resolver() -> pp.ResultadoPortico:
        nos_com_apoio = list(dict.fromkeys(onde[i] for i in sorted(ativos)))
        return pp.resolver(
            pp.Portico(
                nos_do_pp,
                tuple(malha.barras),
                tuple(_restricao_do_no(no, [apoios[i] for i in no_no(no)]) for no in nos_com_apoio),
                tuple(nodais),
                tuple(distribuidas),
            )
        )

    def forcas(resultado: pp.ResultadoPortico) -> dict[int, tuple[float, float, float]]:
        partes: dict[int, tuple[float, float, float]] = {}
        for no in dict.fromkeys(onde[i] for i in sorted(ativos)):
            indices = no_no(no)
            repartida = _parte_de_cada_um(resultado.reacao(no), [apoios[i] for i in indices])
            partes.update(zip(indices, repartida, strict=True))
        return partes

    referencia = max(
        [math.hypot(c.fx, c.fy) for c in nodais]
        + [abs(c.mz) for c in nodais]
        + [abs(c.qi) + abs(c.qj or 0.0) for c in distribuidas]
        + [1e-12]
    )
    resultado = None
    partes: dict[int, tuple[float, float, float]] = {}
    for _ in range(2 * len(de_um_lado) + 2):
        try:
            resultado = resolver()
        except pp.PorticoInvalido as erro:
            soltos = [apoios[i].nome for i in de_um_lado if i not in ativos]
            if soltos:
                raise SemDiagramas(
                    f"O apoio {', '.join(soltos)} descola (só trabalha de um lado) e, sem ele, a "
                    "peça não fica parada."
                ) from erro
            raise SemDiagramas(str(erro)) from erro
        partes = forcas(resultado)
        mudou = False
        for i in de_um_lado:
            cx, cy = apoios[i].direcao
            if i in ativos:
                fx, fy, _m = partes[i]
                if fx * cx + fy * cy < -1e-9 * referencia:
                    ativos.discard(i)
                    mudou = True
            else:
                dx, dy, _giro = resultado.deslocamentos[onde[i]]
                if dx * cx + dy * cy < -1e-12:
                    ativos.add(i)
                    mudou = True
        if not mudou:
            break
    else:
        avisos.append(
            "Os apoios que só trabalham de um lado não chegaram a uma situação estável: confira "
            "o desenho."
        )
    assert resultado is not None

    reacoes = []
    for i, (a, no) in enumerate(zip(apoios, onde, strict=True)):
        if i not in ativos:
            reacoes.append(ReacaoDoApoio(a, no, 0.0, 0.0, 0.0, solto=True))
            avisos.append(
                f"O apoio {a.nome} ({a.tipo.lower()}) não trabalha com esta carga: a peça se "
                "afasta dele."
            )
            continue
        fx, fy, m = partes[i]
        reacoes.append(ReacaoDoApoio(a, no, fx * newton, fy * newton, m * newton))
        if a.tipo == eq.ATRITO:
            cx, cy = a.direcao
            normal = fx * cx + fy * cy
            atrito = abs(-fx * cy + fy * cx)
            if atrito > a.mu * normal * (1.0 + 1e-9) + 1e-9 * referencia:
                avisos.append(
                    f"O apoio {a.nome} precisaria de atrito de {atrito / max(normal, 1e-300):.2f} "
                    f"vezes a força normal, e μ = {a.mu:g}: ele escorrega, e estes esforços "
                    "valem só se algo mais segurar a peça."
                )
    return resultado, tuple(reacoes), avisos


def _pelas_reacoes(
    solucao: eq.Solucao,
    malha: _Malha,
    nodais: list[pp.CargaNodal],
    distribuidas: list[pp.CargaDistribuida],
    newton: float,
) -> tuple[pp.ResultadoPortico, tuple[ReacaoDoApoio, ...], list[str]]:
    reacoes = []
    for r in solucao.reacoes:
        a = r.apoio
        if a.distribuido:
            for parte in eq.cargas_da_reacao(r):
                distribuidas += _distribuidas(malha, parte, newton, f"Apoio {a.nome}")
            no = malha.no_da_peca((a.x, a.y), f"O apoio {a.nome}")
        else:
            no = malha.no_da_peca((a.x, a.y), f"O apoio {a.nome}")
            nodais.append(pp.CargaNodal(no, r.fx / newton, r.fy / newton, r.m / newton))
        reacoes.append(ReacaoDoApoio(a, no, r.fx, r.fy, r.m))

    usados = sorted(malha.usados)
    primeiro = usados[0]
    x0, y0 = malha.nos.pontos[primeiro]
    longe = max(
        usados, key=lambda i: math.hypot(malha.nos.pontos[i][0] - x0, malha.nos.pontos[i][1] - y0)
    )
    x1, y1 = malha.nos.pontos[longe]
    giro = eq.angulo_de(x1 - x0, y1 - y0) + 90.0
    portico = pp.Portico(
        tuple(pp.No(malha.nos.nome(i), *malha.nos.pontos[i]) for i in usados),
        tuple(malha.barras),
        (
            pp.Apoio(malha.nos.nome(primeiro), True, True, False),
            pp.Apoio(malha.nos.nome(longe), True, False, False, giro),
        ),
        tuple(nodais),
        tuple(distribuidas),
    )
    try:
        resultado = pp.resolver(portico)
    except pp.PorticoInvalido as erro:
        raise SemDiagramas(str(erro)) from erro
    avisos = []
    sobra = max(math.hypot(r.rx, r.ry) for r in resultado.reacoes) * newton
    if sobra > 1e-6 * max(solucao.referencia, 1e-12):
        avisos.append(
            "As cargas e as reações não fecham sobre as barras: confira se tudo está sobre a peça."
        )
    return resultado, tuple(reacoes), avisos


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------
def analisar(
    problema: eq.Problema,
    solucao: eq.Solucao | None = None,
    *,
    rigidezes: Sequence[Rigidez | None] = (),
    padrao: Rigidez | None = None,
    newton: float = 1000.0,
) -> Analise:
    """Esforços nas barras do desenho. ``rigidezes`` segue a ordem dos trechos (``None`` = padrão).

    ``solucao`` é a do corpo rígido, usada quando há apoio distribuído. ``newton`` é o valor da
    unidade de força em que o pórtico sai (1000 = kN).
    """
    if not problema.apoios:
        raise SemDiagramas("Coloque ao menos um apoio na peça.")
    if not problema.cargas:
        raise SemDiagramas("Coloque ao menos uma carga na peça.")
    padrao = padrao or Rigidez()
    escolhidas = [
        (rigidezes[k] if k < len(rigidezes) else None) or padrao
        for k in range(len(problema.trechos))
    ]
    for r in escolhidas:
        if r.area_m2 <= 0.0 or r.inercia_m4 <= 0.0 or r.e_N_m2 <= 0.0:
            raise SemDiagramas(f"A seção {r.nome} precisa de E, A e I maiores que zero.")
    secoes = [
        pp.Secao(r.nome, r.area_m2, r.inercia_m4, None, r.e_N_m2 / newton) for r in escolhidas
    ]
    rotulas = [(r.rotula_inicio, r.rotula_fim) for r in escolhidas]

    com_distribuido = any(a.distribuido for a in problema.apoios)
    extras: list[tuple[float, float]] = []
    if com_distribuido:
        if solucao is None or not solucao.para:
            raise SemDiagramas(
                "Com apoio distribuído, os esforços nas barras saem depois que a peça fica parada."
            )
        if not all(r.determinada for r in solucao.reacoes):
            raise SemDiagramas(
                "Com apoio distribuído e apoio de sobra, a divisão das reações depende de quanto a "
                "base cede, e o programa não tem esse dado. Troque o apoio distribuído por apoios "
                "nos pontos de contato para ver os esforços nas barras."
            )
        for reacao in solucao.reacoes:
            if not reacao.apoio.distribuido:
                continue
            pressao = eq.pressao_do_apoio(reacao)
            if pressao.tomba:
                raise SemDiagramas(
                    f"A peça tomba ou descola no apoio {reacao.apoio.nome}: não há esforços a "
                    "mostrar."
                )
            extras += [(pressao.x1, pressao.y1), (pressao.x2, pressao.y2)]

    malha = _malha(problema, extras, secoes, rotulas)
    nodais, distribuidas = _cargas(malha, problema.cargas, newton)
    if com_distribuido:
        assert solucao is not None
        resultado, reacoes, avisos = _pelas_reacoes(solucao, malha, nodais, distribuidas, newton)
        caminho = PELAS_REACOES
    else:
        resultado, reacoes, avisos = _pelos_apoios(problema, malha, nodais, distribuidas, newton)
        caminho = PELOS_APOIOS
    avisos = [*avisos, *resultado.avisos]
    return Analise(resultado, caminho, newton, malha.trecho_da_barra, reacoes, tuple(avisos))


def hiperestatica(analise: Analise) -> int:
    """Grau de hiperestaticidade do pórtico: incógnitas a mais que as equações da estática."""
    p = analise.resultado.portico
    if analise.caminho == PELAS_REACOES:
        return 0
    vinculos = sum(int(a.ux) + int(a.uy) + int(a.rz) for a in p.apoios)
    rotulas = sum(int(b.rotula_i) + int(b.rotula_j) for b in p.barras)
    return 3 * len(p.barras) + vinculos - 3 * len(p.nos) - rotulas
