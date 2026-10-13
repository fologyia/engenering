"""Cargas do esqueleto: o que não está no modelo vira carga característica nas barras do esqueleto.

O modelo do SolidWorks leva só o esqueleto — pilares, vigas e contraventamento. Piso, guarda-corpo,
escadas, equipamentos, tubulações, ligações e a sobrecarga não estão nele: aqui eles viram cargas
**características**, caso a caso, nas barras do esqueleto, e vão para o Plano de cargas, que as
exporta para o SolidWorks (Fx, Fy e Fz já com sinal).

* **Piso e sobrecarga** — o piso (grade, chapa) vence o vão entre as vigas paralelas a uma direção;
  cada uma recebe q × largura de influência (metade da distância às vizinhas de cada lado). As
  vigas perpendiculares recebem as reações das paralelas pelo próprio modelo.
* **Vigas secundárias** — em cada vão entre eixos, o programa põe as vigas paralelas que o vão
  máximo do piso pede, com espaçamento igual; elas fazem parte do esqueleto a modelar.
* **Guarda-corpo** — peso por metro nas vigas das bordas que o têm. A força horizontal no topo
  (NBR 6120 / NBR 14718) é verificação local do guarda-corpo, não carga do esqueleto.
* **Escadas** — o apoio de cima numa viga de borda leva metade do peso e da sobrecarga da escada,
  em duas forças (as longarinas); o apoio de baixo vai à fundação.
* **Equipamentos** — peso vazio (EQ), conteúdo em operação (EO) e impacto (IM, critério Anglo 5.3)
  em forças iguais nos apoios.
* **Tubulações e bandejas** — kN/m nas vigas de uma linha de eixos (PE ou EO).
* **Ligações, chapas e parafusos não modelados** — fator na gravidade do caso PP.
* **Temperatura** — ΔT de ±10 °C nas barras (critério Anglo 5.8).

A **conferência** soma o que foi aplicado em cada caso e compara com o que entrou (área × q,
perímetro × q, pesos): as larguras de influência fecham a área do piso por construção.

Os eixos: as linhas x = constante levam números (1, 2, 3…) e as y = constante, letras (A, B…), como
nas plantas. Nesta primeira forma o esqueleto sai da grade; a leitura do esqueleto do SolidWorks
entra depois pelo mesmo cálculo.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from core import criterio_anglo as ca
from core import plano_de_cargas as pc
from core.technical_records import criar_registro_tecnico

MODULO_ID = "cargas_esqueleto"
ORIGEM = "Cargas do esqueleto"
DIRECAO_X = "X"
DIRECAO_Y = "Y"
DIRECOES = (DIRECAO_X, DIRECAO_Y)
BORDA_X_MENOS = "X−"
BORDA_X_MAIS = "X+"
BORDA_Y_MENOS = "Y−"
BORDA_Y_MAIS = "Y+"
BORDAS = (BORDA_X_MENOS, BORDA_X_MAIS, BORDA_Y_MENOS, BORDA_Y_MAIS)
TIPO_PILAR = "Pilar"
TIPO_VIGA = "Viga"
TIPO_SECUNDARIA = "Viga secundária"
CASOS_DE_LINHA = ("PE", "EO")
VERTICAL = "Z (vertical)"
TOLERANCIA_CONFERENCIA = 1e-6
GRAVIDADE = 9.81

#: Valores usuais para preencher (confira no catálogo do fabricante).
PISO_TIPICO = (
    "grade eletrofundida 25 × 3 a 30 × 3 mm: 0,25 a 0,35 kN/m²; 40 × 5 mm: cerca de 0,55 kN/m²; "
    'chapa xadrez 1/4": cerca de 0,53 kN/m²'
)


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Nivel:
    cota_m: float = 3.0
    #: O piso apoia nas vigas paralelas a esta direção (e vence o vão na outra).
    vigas_paralelas_a: str = DIRECAO_X
    vao_maximo_piso_m: float = 1.20
    piso_kN_m2: float = 0.30
    sobrecarga_kN_m2: float = 5.0
    bordas_com_guarda_corpo: tuple[str, ...] = BORDAS


@dataclass(frozen=True)
class Escada:
    nome: str = "Escada 1"
    nivel: int = 1  # nível de chegada
    borda: str = BORDA_X_MENOS
    trecho: int = 1  # trecho da borda entre eixos (1 = entre os dois primeiros)
    largura_m: float = 0.80
    projecao_m: float = 4.0  # comprimento da escada em planta
    peso_kN_m2: float = 0.70  # longarinas, degraus e guarda-corpo, por área em planta
    sobrecarga_kN_m2: float = 3.0  # critério Anglo, Tabela 2: escadas e passadiços


@dataclass(frozen=True)
class Equipamento:
    nome: str = "Equipamento 1"
    nivel: int = 1
    peso_vazio_kN: float = 10.0
    conteudo_kN: float = 0.0  # o que entra em operação (produto, água)
    apoios: int = 4
    impacto_vertical: float = 0.0  # fração do peso em operação (Anglo 5.3: 0,20 rotativas)
    impacto_horizontal: float = 0.0  # fração do peso em operação (Anglo 5.3: 0,25 vibratórios)
    local: str = ""  # onde estão os apoios (texto livre, ex.: "eixo B, entre 1 e 2")


@dataclass(frozen=True)
class CargaLinear:
    nome: str = "Tubulação"
    nivel: int = 1
    eixo: str = "A"  # linha de eixos (letra ou número)
    valor_kN_m: float = 0.50
    caso: str = "PE"  # PE (vazia) ou EO (com o conteúdo)


@dataclass(frozen=True)
class EntradaEsqueleto:
    eixos_x_m: tuple[float, ...] = (0.0, 6.0, 12.0)
    eixos_y_m: tuple[float, ...] = (0.0, 3.0)
    niveis: tuple[Nivel, ...] = (Nivel(),)
    guarda_corpo_kN_m: float = 0.25
    acrescimo_ligacoes_pct: float = 7.0
    temperatura: bool = False
    escadas: tuple[Escada, ...] = ()
    equipamentos: tuple[Equipamento, ...] = ()
    cargas_lineares: tuple[CargaLinear, ...] = ()

    @property
    def fator_peso_proprio(self) -> float:
        return 1.0 + self.acrescimo_ligacoes_pct / 100.0

    @property
    def area_planta_m2(self) -> float:
        return (self.eixos_x_m[-1] - self.eixos_x_m[0]) * (self.eixos_y_m[-1] - self.eixos_y_m[0])


def letra(indice: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    texto = ""
    n = indice + 1
    while n:
        n, resto = divmod(n - 1, 26)
        texto = chr(65 + resto) + texto
    return texto


def nomes_dos_eixos(e: EntradaEsqueleto) -> tuple[list[str], list[str]]:
    return [str(i + 1) for i in range(len(e.eixos_x_m))], [
        letra(j) for j in range(len(e.eixos_y_m))
    ]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _cota(z: float) -> str:
    return f"{'+' if z >= 0 else '−'}{_n(abs(z))}"


def validar(e: EntradaEsqueleto) -> list[str]:
    erros: list[str] = []
    for nome, eixos in (("X", e.eixos_x_m), ("Y", e.eixos_y_m)):
        if len(eixos) < 2:
            erros.append(f"Informe pelo menos dois eixos em {nome}.")
        elif any(not math.isfinite(v) for v in eixos) or any(
            b - a <= 0.05 for a, b in zip(eixos, eixos[1:], strict=False)
        ):
            erros.append(f"Os eixos em {nome} precisam crescer, com mais de 5 cm entre eles.")
    if not e.niveis:
        erros.append("Informe pelo menos um nível de piso.")
    cotas = [n.cota_m for n in e.niveis]
    if any(not math.isfinite(c) or c <= 0 for c in cotas) or cotas != sorted(set(cotas)):
        erros.append("As cotas dos níveis precisam ser positivas e crescentes, sem repetir.")
    for k, n in enumerate(e.niveis, 1):
        if n.vigas_paralelas_a not in DIRECOES:
            erros.append(f"Nível {k}: direção das vigas desconhecida.")
        if not (0.2 <= n.vao_maximo_piso_m <= 10.0):
            erros.append(f"Nível {k}: o vão máximo do piso precisa estar entre 0,2 e 10 m.")
        if min(n.piso_kN_m2, n.sobrecarga_kN_m2) < 0:
            erros.append(f"Nível {k}: piso e sobrecarga não podem ser negativos.")
        if any(b not in BORDAS for b in n.bordas_com_guarda_corpo):
            erros.append(f"Nível {k}: borda de guarda-corpo desconhecida.")
    if not (0 <= e.acrescimo_ligacoes_pct <= 30):
        erros.append("O acréscimo de ligações precisa estar entre 0 e 30 %.")
    if e.guarda_corpo_kN_m < 0:
        erros.append("O peso do guarda-corpo não pode ser negativo.")
    nx, ny = nomes_dos_eixos(e)
    for s in e.escadas:
        if not 1 <= s.nivel <= len(e.niveis):
            erros.append(f"{s.nome}: nível de chegada inexistente.")
        if s.borda not in BORDAS:
            erros.append(f"{s.nome}: borda desconhecida.")
        trechos = (
            len(e.eixos_y_m) - 1
            if s.borda in (BORDA_X_MENOS, BORDA_X_MAIS)
            else len(e.eixos_x_m) - 1
        )
        if not 1 <= s.trecho <= max(trechos, 1):
            erros.append(f"{s.nome}: trecho da borda inexistente (de 1 a {trechos}).")
        if min(s.largura_m, s.projecao_m) <= 0 or min(s.peso_kN_m2, s.sobrecarga_kN_m2) < 0:
            erros.append(f"{s.nome}: largura e projeção positivas; cargas não negativas.")
    for q in e.equipamentos:
        if not 1 <= q.nivel <= len(e.niveis):
            erros.append(f"{q.nome}: nível inexistente.")
        if q.apoios < 1 or min(q.peso_vazio_kN, q.conteudo_kN) < 0:
            erros.append(f"{q.nome}: pelo menos 1 apoio e pesos não negativos.")
        if not (0 <= q.impacto_vertical <= 2 and 0 <= q.impacto_horizontal <= 1):
            erros.append(f"{q.nome}: impacto fora da faixa (vertical até 2, horizontal até 1).")
    for c in e.cargas_lineares:
        if not 1 <= c.nivel <= len(e.niveis):
            erros.append(f"{c.nome}: nível inexistente.")
        if c.eixo not in (*nx, *ny):
            erros.append(f"{c.nome}: eixo {c.eixo!r} não existe (use {nx[0]}… ou {ny[0]}…).")
        if c.caso not in CASOS_DE_LINHA:
            erros.append(f"{c.nome}: caso precisa ser PE ou EO.")
        if c.valor_kN_m < 0:
            erros.append(f"{c.nome}: valor não pode ser negativo.")
    return erros


class EsqueletoInvalido(ValueError):
    """Entrada que o cálculo não aceita; a mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------------------------
# Esqueleto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Barra:
    nome: str
    tipo: str
    nivel: int  # andar (pilar) ou nível (viga), a partir de 1
    inicio: tuple[float, float, float]
    fim: tuple[float, float, float]

    @property
    def comprimento_m(self) -> float:
        return math.dist(self.inicio, self.fim)

    @property
    def direcao(self) -> str:
        dx, dy, dz = (abs(b - a) for a, b in zip(self.inicio, self.fim, strict=True))
        return DIRECAO_X if dx >= max(dy, dz) else DIRECAO_Y if dy >= dz else "Z"


def _posicoes_internas(a: float, b: float, vao_maximo: float) -> list[float]:
    """Posições das vigas secundárias entre a e b para o vão do piso não passar do máximo."""
    partes = max(1, math.ceil((b - a) / vao_maximo - 1e-9))
    return [a + (b - a) * k / partes for k in range(1, partes)]


def esqueleto(e: EntradaEsqueleto) -> tuple[Barra, ...]:
    """Pilares em cada cruzamento de eixos (um por andar), vigas nos eixos e as secundárias."""
    nx, ny = nomes_dos_eixos(e)
    xs, ys = e.eixos_x_m, e.eixos_y_m
    cotas = (0.0, *(n.cota_m for n in e.niveis))
    barras: list[Barra] = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            for k in range(1, len(cotas)):
                barras.append(
                    Barra(
                        f"Pilar {ny[j]}{nx[i]} · {_cota(cotas[k - 1])} a {_cota(cotas[k])}",
                        TIPO_PILAR,
                        k,
                        (x, y, cotas[k - 1]),
                        (x, y, cotas[k]),
                    )
                )
    for k, nivel in enumerate(e.niveis, 1):
        z = nivel.cota_m
        for j, y in enumerate(ys):
            for i in range(len(xs) - 1):
                barras.append(
                    Barra(
                        f"N{k} · eixo {ny[j]} · {nx[i]}–{nx[i + 1]}",
                        TIPO_VIGA,
                        k,
                        (xs[i], y, z),
                        (xs[i + 1], y, z),
                    )
                )
        for i, x in enumerate(xs):
            for j in range(len(ys) - 1):
                barras.append(
                    Barra(
                        f"N{k} · eixo {nx[i]} · {ny[j]}–{ny[j + 1]}",
                        TIPO_VIGA,
                        k,
                        (x, ys[j], z),
                        (x, ys[j + 1], z),
                    )
                )
        barras += _secundarias(k, nivel, xs, ys, nx, ny)
    return tuple(barras)


def _secundarias(
    k: int,
    nivel: Nivel,
    xs: Sequence[float],
    ys: Sequence[float],
    nx: Sequence[str],
    ny: Sequence[str],
) -> list[Barra]:
    z = nivel.cota_m
    barras: list[Barra] = []
    if nivel.vigas_paralelas_a == DIRECAO_X:
        for j in range(len(ys) - 1):
            for m, y in enumerate(_posicoes_internas(ys[j], ys[j + 1], nivel.vao_maximo_piso_m), 1):
                for i in range(len(xs) - 1):
                    barras.append(
                        Barra(
                            f"N{k} · secundária {ny[j]}–{ny[j + 1]} nº {m} · {nx[i]}–{nx[i + 1]}",
                            TIPO_SECUNDARIA,
                            k,
                            (xs[i], y, z),
                            (xs[i + 1], y, z),
                        )
                    )
    else:
        for i in range(len(xs) - 1):
            for m, x in enumerate(_posicoes_internas(xs[i], xs[i + 1], nivel.vao_maximo_piso_m), 1):
                for j in range(len(ys) - 1):
                    barras.append(
                        Barra(
                            f"N{k} · secundária {nx[i]}–{nx[i + 1]} nº {m} · {ny[j]}–{ny[j + 1]}",
                            TIPO_SECUNDARIA,
                            k,
                            (x, ys[j], z),
                            (x, ys[j + 1], z),
                        )
                    )
    return barras


# ---------------------------------------------------------------------------------------------
# Cargas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CargaNaBarra:
    """Parcela de carga distribuída (kN/m, para baixo) numa barra."""

    barra: str
    caso: str
    valor_kN_m: float
    origem: str  # "piso 0,30 kN/m² × 1,20 m", "guarda-corpo"…
    comprimento_m: float


@dataclass(frozen=True)
class Forca:
    """Força concentrada característica (kN), em ``quantidade`` pontos iguais."""

    caso: str
    onde: str
    valor_kN: float
    quantidade: int = 1
    direcao: str = VERTICAL
    observacao: str = ""

    @property
    def total_kN(self) -> float:
        return self.valor_kN * self.quantidade


@dataclass(frozen=True)
class LinhaDeConferencia:
    caso: str
    item: str
    esperado_kN: float
    aplicado_kN: float

    @property
    def confere(self) -> bool:
        return abs(self.aplicado_kN - self.esperado_kN) <= max(
            TOLERANCIA_CONFERENCIA, 1e-6 * abs(self.esperado_kN)
        )


@dataclass(frozen=True)
class ResultadoEsqueleto:
    entrada: EntradaEsqueleto
    barras: tuple[Barra, ...]
    distribuidas: tuple[CargaNaBarra, ...]
    forcas: tuple[Forca, ...]
    conferencia: tuple[LinhaDeConferencia, ...]
    fundacao: tuple[str, ...] = field(default=())  # o que vai direto à fundação (pé das escadas)

    def barra(self, nome: str) -> Barra:
        return next(b for b in self.barras if b.nome == nome)

    @property
    def casos(self) -> tuple[str, ...]:
        ordem = ("PE", "SC", "EQ", "EO", "IM")
        presentes = {c.caso for c in self.distribuidas} | {f.caso for f in self.forcas}
        return tuple(c for c in ordem if c in presentes)


def larguras_de_influencia(posicoes: Sequence[float]) -> list[float]:
    """Metade da distância às vizinhas de cada lado; nas pontas, só a do lado de dentro."""
    larguras = []
    for k, p in enumerate(posicoes):
        antes = (p - posicoes[k - 1]) / 2 if k > 0 else 0.0
        depois = (posicoes[k + 1] - p) / 2 if k + 1 < len(posicoes) else 0.0
        larguras.append(antes + depois)
    return larguras


def _vigas_do_piso(k: int, nivel: Nivel, barras: Sequence[Barra]) -> list[tuple[Barra, float]]:
    """As vigas do nível paralelas à direção do piso, com a posição perpendicular de cada uma."""
    eixo = 1 if nivel.vigas_paralelas_a == DIRECAO_X else 0
    return [
        (b, b.inicio[eixo])
        for b in barras
        if b.nivel == k and b.tipo != TIPO_PILAR and b.direcao == nivel.vigas_paralelas_a
    ]


def _vigas_da_linha(e: EntradaEsqueleto, barras: Sequence[Barra], k: int, eixo: str) -> list[Barra]:
    nx, ny = nomes_dos_eixos(e)
    if eixo in ny:
        y = e.eixos_y_m[ny.index(eixo)]
        return [
            b
            for b in barras
            if b.nivel == k and b.tipo == TIPO_VIGA and b.direcao == DIRECAO_X and b.inicio[1] == y
        ]
    x = e.eixos_x_m[nx.index(eixo)]
    return [
        b
        for b in barras
        if b.nivel == k and b.tipo == TIPO_VIGA and b.direcao == DIRECAO_Y and b.inicio[0] == x
    ]


def _eixo_da_borda(e: EntradaEsqueleto, borda: str) -> str:
    nx, ny = nomes_dos_eixos(e)
    return {
        BORDA_X_MENOS: nx[0],
        BORDA_X_MAIS: nx[-1],
        BORDA_Y_MENOS: ny[0],
        BORDA_Y_MAIS: ny[-1],
    }[borda]


def calcular(e: EntradaEsqueleto) -> ResultadoEsqueleto:
    erros = validar(e)
    if erros:
        raise EsqueletoInvalido(" ".join(erros))
    barras = esqueleto(e)
    distribuidas: list[CargaNaBarra] = []
    forcas: list[Forca] = []
    conferencia: list[LinhaDeConferencia] = []
    fundacao: list[str] = []
    vao_em_x = e.eixos_x_m[-1] - e.eixos_x_m[0]
    vao_em_y = e.eixos_y_m[-1] - e.eixos_y_m[0]
    #: Comprimento de cada borda: as X± correm ao longo de Y; as Y±, ao longo de X.
    comprimento_da_borda = {
        BORDA_X_MENOS: vao_em_y,
        BORDA_X_MAIS: vao_em_y,
        BORDA_Y_MENOS: vao_em_x,
        BORDA_Y_MAIS: vao_em_x,
    }
    for k, nivel in enumerate(e.niveis, 1):
        rotulo = f"Nível {k} ({_cota(nivel.cota_m)})"
        vigas = _vigas_do_piso(k, nivel, barras)
        posicoes = sorted({p for _, p in vigas})
        larguras = dict(zip(posicoes, larguras_de_influencia(posicoes), strict=True))
        area = e.area_planta_m2
        aplicado = {"PE": 0.0, "SC": 0.0}
        for b, p in vigas:
            w = larguras[p]
            for caso, q, nome in (
                ("PE", nivel.piso_kN_m2, "piso"),
                ("SC", nivel.sobrecarga_kN_m2, "sobrecarga"),
            ):
                if q > 0 and w > 0:
                    distribuidas.append(
                        CargaNaBarra(
                            b.nome,
                            caso,
                            q * w,
                            f"{nome} {_n(q)} kN/m² × {_n(w)} m",
                            b.comprimento_m,
                        )
                    )
                    aplicado[caso] += q * w * b.comprimento_m
        conferencia.append(
            LinhaDeConferencia("PE", f"{rotulo}: piso", nivel.piso_kN_m2 * area, aplicado["PE"])
        )
        conferencia.append(
            LinhaDeConferencia(
                "SC", f"{rotulo}: sobrecarga", nivel.sobrecarga_kN_m2 * area, aplicado["SC"]
            )
        )
        if e.guarda_corpo_kN_m > 0 and nivel.bordas_com_guarda_corpo:
            perimetro = 0.0
            aplicado_gc = 0.0
            for borda in nivel.bordas_com_guarda_corpo:
                for b in _vigas_da_linha(e, barras, k, _eixo_da_borda(e, borda)):
                    distribuidas.append(
                        CargaNaBarra(
                            b.nome, "PE", e.guarda_corpo_kN_m, "guarda-corpo", b.comprimento_m
                        )
                    )
                    aplicado_gc += e.guarda_corpo_kN_m * b.comprimento_m
                perimetro += comprimento_da_borda[borda]
            conferencia.append(
                LinhaDeConferencia(
                    "PE", f"{rotulo}: guarda-corpo", e.guarda_corpo_kN_m * perimetro, aplicado_gc
                )
            )
    for c in e.cargas_lineares:
        da_linha = _vigas_da_linha(e, barras, c.nivel, c.eixo)
        for b in da_linha:
            distribuidas.append(
                CargaNaBarra(b.nome, c.caso, c.valor_kN_m, c.nome.lower(), b.comprimento_m)
            )
        comprimento = sum(b.comprimento_m for b in da_linha)
        conferencia.append(
            LinhaDeConferencia(
                c.caso,
                f"{c.nome} (nível {c.nivel}, eixo {c.eixo})",
                c.valor_kN_m * comprimento,
                c.valor_kN_m * comprimento,
            )
        )
    for s in e.escadas:
        forcas_da_escada, no_pe = _escada(e, barras, s)
        forcas += forcas_da_escada
        fundacao.append(no_pe)
        for caso, por_area in (("PE", s.peso_kN_m2), ("SC", s.sobrecarga_kN_m2)):
            esperado = por_area * s.largura_m * s.projecao_m / 2
            aplicado_esc = sum(f.total_kN for f in forcas_da_escada if f.caso == caso)
            if esperado > 0:
                conferencia.append(
                    LinhaDeConferencia(caso, f"{s.nome}: apoio de cima", esperado, aplicado_esc)
                )
    for equipamento in e.equipamentos:
        forcas_eq = _equipamento(equipamento)
        forcas += forcas_eq
        operacao = equipamento.peso_vazio_kN + equipamento.conteudo_kN
        impacto = equipamento.impacto_vertical + equipamento.impacto_horizontal
        for caso, esperado in (
            ("EQ", equipamento.peso_vazio_kN),
            ("EO", equipamento.conteudo_kN),
            ("IM", impacto * operacao),
        ):
            if esperado > 0:
                aplicado_q = sum(f.total_kN for f in forcas_eq if f.caso == caso)
                conferencia.append(LinhaDeConferencia(caso, equipamento.nome, esperado, aplicado_q))
    return ResultadoEsqueleto(
        e, barras, tuple(distribuidas), tuple(forcas), tuple(conferencia), tuple(fundacao)
    )


def _escada(e: EntradaEsqueleto, barras: Sequence[Barra], s: Escada) -> tuple[list[Forca], str]:
    vigas = sorted(
        _vigas_da_linha(e, barras, s.nivel, _eixo_da_borda(e, s.borda)),
        key=lambda b: (b.inicio[0], b.inicio[1]),
    )
    viga = vigas[s.trecho - 1]
    forcas = []
    for caso, q in (("PE", s.peso_kN_m2), ("SC", s.sobrecarga_kN_m2)):
        reacao = q * s.largura_m * s.projecao_m / 2
        if reacao > 0:
            forcas.append(
                Forca(
                    caso,
                    f"{viga.nome}: {s.nome}, nas 2 longarinas (afastadas {_n(s.largura_m)} m, no "
                    "meio do trecho)",
                    reacao / 2,
                    2,
                    observacao=f"{_n(q)} kN/m² × {_n(s.largura_m)} × {_n(s.projecao_m)} m ÷ 2; "
                    f"ou {_n(reacao / s.largura_m)} kN/m na largura da escada",
                )
            )
    total_pe = s.peso_kN_m2 * s.largura_m * s.projecao_m / 2
    total_sc = s.sobrecarga_kN_m2 * s.largura_m * s.projecao_m / 2
    no_pe = (
        f"{s.nome}: o apoio de baixo vai direto à fundação — PE {_n(total_pe)} kN e SC "
        f"{_n(total_sc)} kN (característicos)."
    )
    return forcas, no_pe


def _equipamento(q: Equipamento) -> list[Forca]:
    onde = f"{q.nome}: cada um dos {q.apoios} apoios (nível {q.nivel})" + (
        f" — {q.local}" if q.local else ""
    )
    operacao = q.peso_vazio_kN + q.conteudo_kN
    forcas = []
    if q.peso_vazio_kN > 0:
        forcas.append(Forca("EQ", onde, q.peso_vazio_kN / q.apoios, q.apoios))
    if q.conteudo_kN > 0:
        forcas.append(Forca("EO", onde, q.conteudo_kN / q.apoios, q.apoios))
    if q.impacto_vertical > 0:
        forcas.append(
            Forca(
                "IM",
                onde,
                q.impacto_vertical * operacao / q.apoios,
                q.apoios,
                observacao=f"impacto vertical: {_n(100 * q.impacto_vertical, 0)} % do peso em "
                "operação (critério Anglo 5.3)",
            )
        )
    if q.impacto_horizontal > 0:
        forcas.append(
            Forca(
                "IM",
                onde,
                q.impacto_horizontal * operacao / q.apoios,
                q.apoios,
                direcao="X",
                observacao=f"impacto horizontal: {_n(100 * q.impacto_horizontal, 0)} % do peso "
                "em operação, na direção do movimento do equipamento (troque para Y se for o caso)",
            )
        )
    return forcas


# ---------------------------------------------------------------------------------------------
# Por barra e para o plano de cargas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CargaDaBarraNoCaso:
    """A soma das parcelas de um caso numa barra: é o que se aplica no SolidWorks."""

    barra: str
    caso: str
    valor_kN_m: float
    comprimento_m: float
    composicao: str


def por_barra(r: ResultadoEsqueleto) -> list[CargaDaBarraNoCaso]:
    somas: dict[tuple[str, str], list[CargaNaBarra]] = {}
    for c in r.distribuidas:
        somas.setdefault((c.barra, c.caso), []).append(c)
    saida = []
    for (barra, caso), partes in somas.items():
        saida.append(
            CargaDaBarraNoCaso(
                barra,
                caso,
                sum(p.valor_kN_m for p in partes),
                partes[0].comprimento_m,
                " + ".join(
                    p.origem if len(partes) == 1 else f"{p.origem} ({_n(p.valor_kN_m, 3)})"
                    for p in partes
                ),
            )
        )
    return saida


def agrupadas(r: ResultadoEsqueleto, caso: str) -> list[tuple[float, list[CargaDaBarraNoCaso]]]:
    """As barras do caso com o mesmo valor juntas (uma carga no SolidWorks com várias barras)."""
    grupos: dict[float, list[CargaDaBarraNoCaso]] = {}
    for c in por_barra(r):
        if c.caso == caso:
            grupos.setdefault(round(c.valor_kN_m, 4), []).append(c)
    return sorted(grupos.items(), key=lambda g: -g[0])


def cargas_do_caso(r: ResultadoEsqueleto, caso: str) -> list[pc.CargaDoModelo]:
    cargas: list[pc.CargaDoModelo] = []
    for valor, grupo in agrupadas(r, caso):
        comprimento = sum(c.comprimento_m for c in grupo)
        composicoes = sorted({c.composicao for c in grupo})
        cargas.append(
            pc.CargaDoModelo(
                elemento="; ".join(c.barra for c in grupo),
                valor=valor,
                unidade="kN/m",
                direcao=VERTICAL,
                observacao=f"{len(grupo)} barra(s), {_n(comprimento)} m: "
                + " | ".join(composicoes),
                quantidade=len(grupo),
                comprimento_m=comprimento / len(grupo),
            )
        )
    for f in r.forcas:
        if f.caso == caso:
            cargas.append(
                pc.CargaDoModelo(
                    elemento=f.onde,
                    valor=f.valor_kN,
                    unidade="kN",
                    direcao=f.direcao,
                    observacao=f.observacao,
                    quantidade=f.quantidade,
                )
            )
    return cargas


def resumo_do_caso(r: ResultadoEsqueleto, caso: str) -> float:
    """Resultante (kN) do caso: distribuídas × comprimento + forças."""
    return sum(c.valor_kN_m * c.comprimento_m for c in r.distribuidas if c.caso == caso) + sum(
        f.total_kN for f in r.forcas if f.caso == caso
    )


def acoes_para_o_plano(r: ResultadoEsqueleto) -> list[pc.Acao]:
    """As ações que o esqueleto gera; substituem as de mesmo código no plano."""
    resumo_de = {
        "PE": "Piso, guarda-corpo, escadas e tubulações que não estão no modelo do esqueleto.",
        "SC": "Sobrecarga do piso e das escadas sobre as vigas do esqueleto.",
        "EQ": "Peso vazio dos equipamentos, nos apoios.",
        "EO": "Conteúdo dos equipamentos e tubulações em operação.",
        "IM": "Impacto dos equipamentos (critério Anglo 5.3).",
    }
    acoes = [
        pc.nova_acao(
            caso,
            origem=ORIGEM,
            resumo=f"{resumo_de[caso]} Resultante: {_n(resumo_do_caso(r, caso))} kN.",
            cargas=cargas_do_caso(r, caso),
        )
        for caso in r.casos
    ]
    if r.entrada.temperatura:
        for codigo, sinal in (("T+", 1.0), ("T−", -1.0)):
            acoes.append(
                pc.nova_acao(
                    codigo,
                    origem=ORIGEM,
                    resumo="Variação de temperatura do critério Anglo (5.8).",
                    cargas=[
                        pc.CargaDoModelo(
                            "Todas as barras do esqueleto",
                            sinal * ca.TEMPERATURA_VARIACAO_C,
                            "°C",
                            "—",
                        )
                    ],
                )
            )
    return acoes


def aplicar_no_plano(r: ResultadoEsqueleto, plano: pc.PlanoDeCargas) -> pc.PlanoDeCargas:
    """O plano com as ações do esqueleto (e o fator do peso próprio das ligações).

    As ações que uma aplicação anterior gerou e esta não gera mais (um equipamento retirado, a
    temperatura desligada) saem do plano; as informadas à mão ficam.
    """
    novas = acoes_para_o_plano(r)
    codigos = {a.codigo for a in novas}
    for antiga in plano.acoes:
        if antiga.origem == ORIGEM and antiga.codigo not in codigos and antiga.codigo != "PP":
            plano = pc.sem_acao(plano, antiga.codigo)
    for acao in novas:
        plano = pc.com_acao(plano, acao)
    if "PP" not in plano.codigos:
        plano = pc.com_acao(plano, pc.nova_acao("PP", origem=ORIGEM))
    return pc.com_fator_peso_proprio(plano, r.entrada.fator_peso_proprio)


# ---------------------------------------------------------------------------------------------
# Projeto
# ---------------------------------------------------------------------------------------------
def para_dicionario(e: EntradaEsqueleto) -> dict[str, Any]:
    return asdict(e)


def _numero(valor: Any, padrao: float) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) else padrao


def _inteiro(valor: Any, padrao: int) -> int:
    return int(_numero(valor, float(padrao)))


def _texto(valor: Any, padrao: str) -> str:
    return valor if isinstance(valor, str) else padrao


def _lista(valor: Any) -> list[Any]:
    return list(valor) if isinstance(valor, list | tuple) else []


def _objetos(valor: Any) -> list[Mapping[str, Any]]:
    return [v for v in _lista(valor) if isinstance(v, Mapping)]


def de_dicionario(dados: Mapping[str, Any] | None) -> EntradaEsqueleto:
    """Lê o que está gravado no projeto; o que estiver fora do formato volta ao padrão."""
    padrao = EntradaEsqueleto()
    if not isinstance(dados, Mapping):
        return padrao

    def eixos(chave: str, inicial: tuple[float, ...]) -> tuple[float, ...]:
        valores = [_numero(v, math.nan) for v in _lista(dados.get(chave))]
        return tuple(valores) if valores and all(math.isfinite(v) for v in valores) else inicial

    nivel_padrao = Nivel()
    niveis = tuple(
        Nivel(
            cota_m=_numero(n.get("cota_m"), nivel_padrao.cota_m),
            vigas_paralelas_a=_texto(n.get("vigas_paralelas_a"), DIRECAO_X),
            vao_maximo_piso_m=_numero(n.get("vao_maximo_piso_m"), nivel_padrao.vao_maximo_piso_m),
            piso_kN_m2=_numero(n.get("piso_kN_m2"), nivel_padrao.piso_kN_m2),
            sobrecarga_kN_m2=_numero(n.get("sobrecarga_kN_m2"), nivel_padrao.sobrecarga_kN_m2),
            bordas_com_guarda_corpo=tuple(
                b for b in _lista(n.get("bordas_com_guarda_corpo", BORDAS)) if b in BORDAS
            ),
        )
        for n in _objetos(dados.get("niveis"))
    )
    escada_padrao, equip_padrao, linear_padrao = Escada(), Equipamento(), CargaLinear()
    return EntradaEsqueleto(
        eixos_x_m=eixos("eixos_x_m", padrao.eixos_x_m),
        eixos_y_m=eixos("eixos_y_m", padrao.eixos_y_m),
        niveis=niveis or padrao.niveis,
        guarda_corpo_kN_m=_numero(dados.get("guarda_corpo_kN_m"), padrao.guarda_corpo_kN_m),
        acrescimo_ligacoes_pct=_numero(
            dados.get("acrescimo_ligacoes_pct"), padrao.acrescimo_ligacoes_pct
        ),
        temperatura=bool(dados.get("temperatura", padrao.temperatura)),
        escadas=tuple(
            Escada(
                nome=_texto(s.get("nome"), escada_padrao.nome),
                nivel=_inteiro(s.get("nivel"), 1),
                borda=_texto(s.get("borda"), escada_padrao.borda),
                trecho=_inteiro(s.get("trecho"), 1),
                largura_m=_numero(s.get("largura_m"), escada_padrao.largura_m),
                projecao_m=_numero(s.get("projecao_m"), escada_padrao.projecao_m),
                peso_kN_m2=_numero(s.get("peso_kN_m2"), escada_padrao.peso_kN_m2),
                sobrecarga_kN_m2=_numero(s.get("sobrecarga_kN_m2"), escada_padrao.sobrecarga_kN_m2),
            )
            for s in _objetos(dados.get("escadas"))
        ),
        equipamentos=tuple(
            Equipamento(
                nome=_texto(q.get("nome"), equip_padrao.nome),
                nivel=_inteiro(q.get("nivel"), 1),
                peso_vazio_kN=_numero(q.get("peso_vazio_kN"), equip_padrao.peso_vazio_kN),
                conteudo_kN=_numero(q.get("conteudo_kN"), 0.0),
                apoios=_inteiro(q.get("apoios"), equip_padrao.apoios),
                impacto_vertical=_numero(q.get("impacto_vertical"), 0.0),
                impacto_horizontal=_numero(q.get("impacto_horizontal"), 0.0),
                local=_texto(q.get("local"), ""),
            )
            for q in _objetos(dados.get("equipamentos"))
        ),
        cargas_lineares=tuple(
            CargaLinear(
                nome=_texto(c.get("nome"), linear_padrao.nome),
                nivel=_inteiro(c.get("nivel"), 1),
                eixo=_texto(c.get("eixo"), linear_padrao.eixo),
                valor_kN_m=_numero(c.get("valor_kN_m"), linear_padrao.valor_kN_m),
                caso=_texto(c.get("caso"), "PE"),
            )
            for c in _objetos(dados.get("cargas_lineares"))
        ),
    )


def entrada_do_projeto(projeto: Mapping[str, Any] | None) -> EntradaEsqueleto | None:
    """A entrada gravada no projeto, ou ``None`` se ainda não há uma."""
    if not isinstance(projeto, Mapping) or not isinstance(
        projeto.get("cargas_do_esqueleto"), Mapping
    ):
        return None
    return de_dicionario(projeto["cargas_do_esqueleto"])


# ---------------------------------------------------------------------------------------------
# Tabelas e registro
# ---------------------------------------------------------------------------------------------
COLUNAS_POR_BARRA = ("Caso", "Barra", "kN/m", "Comprimento (m)", "Resultante (kN)", "Composição")
COLUNAS_FORCAS = ("Caso", "Onde", "kN (cada)", "Quantidade", "Direção", "Observação")
COLUNAS_CONFERENCIA = ("Caso", "Item", "Entrou (kN)", "Aplicado (kN)", "Confere")


def linhas_por_barra(r: ResultadoEsqueleto, caso: str | None = None) -> list[list[object]]:
    return [
        [
            c.caso,
            c.barra,
            c.valor_kN_m,
            c.comprimento_m,
            c.valor_kN_m * c.comprimento_m,
            c.composicao,
        ]
        for c in por_barra(r)
        if caso is None or c.caso == caso
    ]


def linhas_das_forcas(r: ResultadoEsqueleto, caso: str | None = None) -> list[list[object]]:
    return [
        [f.caso, f.onde, f.valor_kN, f.quantidade, f.direcao, f.observacao]
        for f in r.forcas
        if caso is None or f.caso == caso
    ]


def linhas_da_conferencia(r: ResultadoEsqueleto) -> list[list[object]]:
    return [
        [c.caso, c.item, c.esperado_kN, c.aplicado_kN, "sim" if c.confere else "NÃO"]
        for c in r.conferencia
    ]


def csv_das_cargas(r: ResultadoEsqueleto) -> bytes:
    linhas = [
        [c.caso, c.barra, c.valor_kN_m, "kN/m", c.comprimento_m, 1, VERTICAL, c.composicao]
        for c in por_barra(r)
    ] + [
        [f.caso, f.onde, f.valor_kN, "kN", "", f.quantidade, f.direcao, f.observacao]
        for f in r.forcas
    ]
    return pc._csv(
        (
            "Caso",
            "Onde aplicar",
            "Valor",
            "Unidade",
            "Comprimento (m)",
            "Quantidade",
            "Direção",
            "Composição / observação",
        ),
        linhas,
    )


def registro_esqueleto(
    r: ResultadoEsqueleto,
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    e = r.entrada
    nx, ny = nomes_dos_eixos(e)
    destaque = (
        f"Cargas características sobre o esqueleto ({len(e.niveis)} nível(is), eixos {nx[0]}–"
        f"{nx[-1]} × {ny[0]}–{ny[-1]}): "
        + "; ".join(f"{caso} {_n(resumo_do_caso(r, caso))} kN" for caso in r.casos)
        + f". Peso próprio do modelo × {_n(e.fator_peso_proprio)} (ligações não modeladas)."
    )
    tabela_niveis = {
        "legenda": "Níveis de piso: vigas que recebem o piso, vão máximo, piso e sobrecarga.",
        "cabecalhos": [
            "Nível",
            "Cota (m)",
            "Vigas paralelas a",
            "Vão máx. (m)",
            "Piso (kN/m²)",
            "Sobrecarga (kN/m²)",
            "Guarda-corpo",
        ],
        "linhas": [
            [
                str(k),
                _n(n.cota_m),
                n.vigas_paralelas_a,
                _n(n.vao_maximo_piso_m),
                _n(n.piso_kN_m2),
                _n(n.sobrecarga_kN_m2),
                ", ".join(n.bordas_com_guarda_corpo) or "—",
            ]
            for k, n in enumerate(e.niveis, 1)
        ],
    }
    tabela_barras = {
        "legenda": "Cargas distribuídas características nas barras do esqueleto (kN/m, para baixo).",
        "cabecalhos": ["Caso", "Barra", "kN/m", "Composição"],
        "linhas": [[c.caso, c.barra, _n(c.valor_kN_m, 3), c.composicao] for c in por_barra(r)],
        "fonte": 7.0,
    }
    tabelas = [tabela_niveis, tabela_barras]
    if r.forcas:
        tabelas.append(
            {
                "legenda": "Forças concentradas características.",
                "cabecalhos": ["Caso", "Onde", "kN (cada)", "Quantidade"],
                "linhas": [[f.caso, f.onde, _n(f.valor_kN), str(f.quantidade)] for f in r.forcas],
                "fonte": 7.0,
            }
        )
    entradas: dict[str, Any] = {
        "eixos_x_m": ", ".join(_n(v) for v in e.eixos_x_m),
        "eixos_y_m": ", ".join(_n(v) for v in e.eixos_y_m),
        "niveis": len(e.niveis),
        "guarda_corpo_kN_m": e.guarda_corpo_kN_m,
        "acrescimo_de_ligacoes_pct": e.acrescimo_ligacoes_pct,
        "escadas": len(e.escadas) or None,
        "equipamentos": len(e.equipamentos) or None,
        "temperatura": "±10 °C" if e.temperatura else None,
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    return criar_registro_tecnico(
        modulo="Cargas do esqueleto",
        modulo_id=MODULO_ID,
        titulo=f"Cargas sobre o esqueleto — {len(e.niveis)} nível(is)",
        status="Calculado",
        resumo=destaque,
        entradas=entradas,
        resultados={"destaque_memorial": destaque, "tabelas_memorial": tabelas},
        metodo=(
            "O modelo leva só o esqueleto (pilares, vigas e contraventamento). O piso vence o vão "
            "entre as vigas paralelas à direção de cada nível; cada uma recebe q × largura de "
            "influência. Guarda-corpo por metro nas vigas de borda, escadas e equipamentos em "
            "forças nos apoios; as ligações não modeladas entram multiplicando a gravidade."
        ),
        premissas=[
            "Valores característicos: os coeficientes de ponderação estão nas combinações.",
            "A força horizontal do guarda-corpo é verificação local, não carga do esqueleto.",
            *r.fundacao,
        ],
        referencias=["NBR 8800; NBR 6120; " + ca.REFERENCIA + " (Tabela 2, 5.3 e 5.8)."],
        conclusao=destaque,
        responsavel=responsavel,
    )


def resumo_numerico(r: ResultadoEsqueleto) -> dict[str, float | int]:
    return {
        "barras": len(r.barras),
        "secundarias": sum(b.tipo == TIPO_SECUNDARIA for b in r.barras),
        **{caso: resumo_do_caso(r, caso) for caso in r.casos},
    }


def niveis_padrao(cotas: Iterable[float], sobrecarga: float) -> tuple[Nivel, ...]:
    return tuple(Nivel(cota_m=c, sobrecarga_kN_m2=sobrecarga) for c in cotas)


# ---------------------------------------------------------------------------------------------
# Tabelas editáveis da página
# ---------------------------------------------------------------------------------------------
def ler_eixos(texto: str) -> tuple[float, ...]:
    """'0; 6; 12' ou '0 6 12' (vírgula decimal aceita) → (0.0, 6.0, 12.0)."""
    valores: list[float] = []
    for parte in texto.replace(";", " ").split():
        try:
            valores.append(float(parte.replace(",", ".")))
        except ValueError:
            raise EsqueletoInvalido(f"{parte!r} não é um número de eixo.") from None
    return tuple(valores)


def texto_dos_eixos(eixos: Iterable[float]) -> str:
    return "; ".join(f"{v:g}".replace(".", ",") for v in eixos)


def _vazia(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float):
        return math.isnan(valor)
    return type(valor).__name__ in ("NAType", "NaTType")


def _limpa(linha: Mapping[str, Any]) -> dict[str, Any]:
    return {chave: None if _vazia(valor) else valor for chave, valor in linha.items()}


COLUNAS_NIVEIS = (
    "Cota (m)",
    "Vigas paralelas a",
    "Vão máx. do piso (m)",
    "Piso (kN/m²)",
    "Sobrecarga (kN/m²)",
    *(f"GC {b}" for b in BORDAS),
)
COLUNAS_ESCADAS = (
    "Nome",
    "Nível",
    "Borda",
    "Trecho",
    "Largura (m)",
    "Projeção (m)",
    "Peso (kN/m²)",
    "Sobrecarga (kN/m²)",
)
COLUNAS_EQUIPAMENTOS = (
    "Nome",
    "Nível",
    "Peso vazio (kN)",
    "Conteúdo (kN)",
    "Apoios",
    "Impacto vertical (%)",
    "Impacto horizontal (%)",
    "Local",
)
COLUNAS_TUBULACOES = ("Nome", "Nível", "Eixo", "kN/m", "Caso")


def tabela_dos_niveis(e: EntradaEsqueleto) -> list[dict[str, Any]]:
    return [
        {
            "Cota (m)": n.cota_m,
            "Vigas paralelas a": n.vigas_paralelas_a,
            "Vão máx. do piso (m)": n.vao_maximo_piso_m,
            "Piso (kN/m²)": n.piso_kN_m2,
            "Sobrecarga (kN/m²)": n.sobrecarga_kN_m2,
            **{f"GC {b}": b in n.bordas_com_guarda_corpo for b in BORDAS},
        }
        for n in e.niveis
    ]


def niveis_da_tabela(linhas: Iterable[Mapping[str, Any]]) -> tuple[Nivel, ...]:
    padrao = Nivel()
    niveis = []
    for bruta in linhas:
        linha = _limpa(bruta)
        if linha.get("Cota (m)") is None:
            continue
        niveis.append(
            Nivel(
                cota_m=_numero(linha.get("Cota (m)"), padrao.cota_m),
                vigas_paralelas_a=_texto(linha.get("Vigas paralelas a"), DIRECAO_X),
                vao_maximo_piso_m=_numero(
                    linha.get("Vão máx. do piso (m)"), padrao.vao_maximo_piso_m
                ),
                piso_kN_m2=_numero(linha.get("Piso (kN/m²)"), padrao.piso_kN_m2),
                sobrecarga_kN_m2=_numero(linha.get("Sobrecarga (kN/m²)"), padrao.sobrecarga_kN_m2),
                bordas_com_guarda_corpo=tuple(b for b in BORDAS if bool(linha.get(f"GC {b}"))),
            )
        )
    return tuple(niveis)


def tabela_das_escadas(e: EntradaEsqueleto) -> list[dict[str, Any]]:
    return [
        {
            "Nome": s.nome,
            "Nível": s.nivel,
            "Borda": s.borda,
            "Trecho": s.trecho,
            "Largura (m)": s.largura_m,
            "Projeção (m)": s.projecao_m,
            "Peso (kN/m²)": s.peso_kN_m2,
            "Sobrecarga (kN/m²)": s.sobrecarga_kN_m2,
        }
        for s in e.escadas
    ]


def escadas_da_tabela(linhas: Iterable[Mapping[str, Any]]) -> tuple[Escada, ...]:
    padrao = Escada()
    escadas = []
    for bruta in linhas:
        linha = _limpa(bruta)
        if not linha.get("Nome") and linha.get("Projeção (m)") is None:
            continue
        escadas.append(
            Escada(
                nome=str(linha.get("Nome") or padrao.nome),
                nivel=_inteiro(linha.get("Nível"), 1),
                borda=_texto(linha.get("Borda"), padrao.borda),
                trecho=_inteiro(linha.get("Trecho"), 1),
                largura_m=_numero(linha.get("Largura (m)"), padrao.largura_m),
                projecao_m=_numero(linha.get("Projeção (m)"), padrao.projecao_m),
                peso_kN_m2=_numero(linha.get("Peso (kN/m²)"), padrao.peso_kN_m2),
                sobrecarga_kN_m2=_numero(linha.get("Sobrecarga (kN/m²)"), padrao.sobrecarga_kN_m2),
            )
        )
    return tuple(escadas)


def tabela_dos_equipamentos(e: EntradaEsqueleto) -> list[dict[str, Any]]:
    return [
        {
            "Nome": q.nome,
            "Nível": q.nivel,
            "Peso vazio (kN)": q.peso_vazio_kN,
            "Conteúdo (kN)": q.conteudo_kN,
            "Apoios": q.apoios,
            "Impacto vertical (%)": 100 * q.impacto_vertical,
            "Impacto horizontal (%)": 100 * q.impacto_horizontal,
            "Local": q.local,
        }
        for q in e.equipamentos
    ]


def equipamentos_da_tabela(linhas: Iterable[Mapping[str, Any]]) -> tuple[Equipamento, ...]:
    padrao = Equipamento()
    equipamentos = []
    for bruta in linhas:
        linha = _limpa(bruta)
        if not linha.get("Nome") and linha.get("Peso vazio (kN)") is None:
            continue
        equipamentos.append(
            Equipamento(
                nome=str(linha.get("Nome") or padrao.nome),
                nivel=_inteiro(linha.get("Nível"), 1),
                peso_vazio_kN=_numero(linha.get("Peso vazio (kN)"), 0.0),
                conteudo_kN=_numero(linha.get("Conteúdo (kN)"), 0.0),
                apoios=_inteiro(linha.get("Apoios"), padrao.apoios),
                impacto_vertical=_numero(linha.get("Impacto vertical (%)"), 0.0) / 100,
                impacto_horizontal=_numero(linha.get("Impacto horizontal (%)"), 0.0) / 100,
                local=str(linha.get("Local") or ""),
            )
        )
    return tuple(equipamentos)


def tabela_das_tubulacoes(e: EntradaEsqueleto) -> list[dict[str, Any]]:
    return [
        {"Nome": c.nome, "Nível": c.nivel, "Eixo": c.eixo, "kN/m": c.valor_kN_m, "Caso": c.caso}
        for c in e.cargas_lineares
    ]


def tubulacoes_da_tabela(linhas: Iterable[Mapping[str, Any]]) -> tuple[CargaLinear, ...]:
    padrao = CargaLinear()
    cargas = []
    for bruta in linhas:
        linha = _limpa(bruta)
        if not linha.get("Nome") and linha.get("kN/m") is None:
            continue
        cargas.append(
            CargaLinear(
                nome=str(linha.get("Nome") or padrao.nome),
                nivel=_inteiro(linha.get("Nível"), 1),
                eixo=str(linha.get("Eixo") or padrao.eixo).strip().upper(),
                valor_kN_m=_numero(linha.get("kN/m"), 0.0),
                caso=_texto(linha.get("Caso"), "PE"),
            )
        )
    return tuple(cargas)
