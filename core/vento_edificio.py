"""Ação do vento numa edificação paralelepipédica (galpão, edifício) — ABNT NBR 6123:2023, seção 6.

Dado o local (``V_0``, relevo, rugosidade, grupo) e a geometria (planta ``a × b``, altura ``h`` do
beiral, cobertura plana, de uma ou de duas águas), o módulo devolve:

* ``V_k`` e ``q`` do vento sobre a estrutura (classe A, B ou C pela superfície frontal de cada
  direção) e sobre as vedações (classe A, topo da edificação);
* ``C_e`` e as pressões ``q·(C_e − c_pi)`` de cada zona das paredes e do telhado, nas direções do
  vento e em cada valor de ``c_pi`` que a norma manda considerar;
* as zonas de altas sucções (``c_pe`` médio) e a pressão de projeto de telhas, painéis, terças,
  travessas e fixações;
* as forças resultantes por direção, a força de arrasto global ``F_a = q·C_a·A_e·f_v``, a torção
  pela excentricidade (6.1.4) e a força de atrito (6.1.5);
* as verificações de aplicabilidade das tabelas e do regime estático (período fundamental ≤ 1 s,
  esbeltez que pede o desprendimento de vórtices).

As cargas por metro nos pórticos ficam em :mod:`core.vento_portico`, que usa este resultado.

Eixos: x ao longo de ``a`` (o vento a 0° sopra para +x), y ao longo de ``b`` (o vento a 90° sopra
para +y), z vertical. A cumeeira é paralela a x (Tabelas 7 e 8). Na cobertura de uma água o lado
alto fica em y = 0 e o baixo em y = b, como na figura da Tabela 8; o vento a −90° sopra para −y.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import vento_coeficientes as coef
from core.vento_nbr6123 import (
    ALTURA_GRADIENTE_M,
    LIMITE_ANEXO_A_M,
    VentoNoLocal,
    calcular_vento_no_local,
    classe_da_edificacao,
    intervalo_de_tempo_anexo_a,
    numero_ptbr,
)
from core.verificacao import Verificacao

COBERTURA_PLANA = "plana"
COBERTURA_DUAS_AGUAS = "duas_aguas"
COBERTURA_UMA_AGUA = "uma_agua"
COBERTURAS: dict[str, str] = {
    COBERTURA_PLANA: "Plana (laje ou telhado sem inclinação, θ = 0°)",
    COBERTURA_DUAS_AGUAS: "Duas águas simétricas (cumeeira no meio do vão)",
    COBERTURA_UMA_AGUA: "Uma água (lado alto de um lado, lado baixo do outro)",
}

REFERENCIA_ALTURA_TOPO = "topo"
REFERENCIA_ALTURA_BEIRAL = "beiral"
REFERENCIAS_DE_ALTURA: dict[str, str] = {
    REFERENCIA_ALTURA_TOPO: "Topo da edificação (cumeeira ou ponto mais alto) — recomendado pela norma",
    REFERENCIA_ALTURA_BEIRAL: "Altura h do beiral",
}

#: Período fundamental acima do qual a norma pede análise dinâmica (4.1 e seção 9).
PERIODO_LIMITE_ESTATICO_S = 1.0
#: Esbeltez h/b a partir da qual o desprendimento de vórtices deve ser investigado (10.2).
ESBELTEZ_VORTICES = 6.0
#: Balanço máximo do beiral admitido no Detalhe I da Tabela 7 (0,1·b).
FRACAO_BEIRAL_MAXIMA = 0.1

Vetor = tuple[float, float, float]


# ---------------------------------------------------------------------------
# Dados de entrada
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaEdificio:
    """Tudo o que o cálculo precisa; as unidades estão nos nomes."""

    v0_m_s: float
    comprimento_a_m: float
    largura_b_m: float
    altura_h_m: float
    cobertura: str = COBERTURA_DUAS_AGUAS
    theta_graus: float = 0.0
    s1: float = 1.0
    categoria: str = "II"
    grupo_s3: int = 3
    s3: float | None = None
    classe: str | None = None
    referencia_altura: str = REFERENCIA_ALTURA_TOPO
    vedacoes_com_092: bool = False
    cenario_permeabilidade: str = "quatro_faces"
    cpis_informados: tuple[float, ...] | None = None
    alta_turbulencia: bool = False
    altura_media_vizinhanca_m: float = 0.0
    extensao_vizinhanca_m: float = 0.0
    com_vizinhanca: bool = False
    afastamento_vizinha_m: float | None = None
    ct_atrito: float = 0.01
    espacamento_porticos_m: float = 6.0
    beiral_m: float = 0.0
    periodo_fundamental_s: float | None = None

    def validar(self) -> None:
        for nome, valor in (
            ("O comprimento a", self.comprimento_a_m),
            ("A largura b", self.largura_b_m),
            ("A altura h", self.altura_h_m),
            ("V₀", self.v0_m_s),
            ("O espaçamento dos pórticos", self.espacamento_porticos_m),
        ):
            if not (math.isfinite(valor) and valor > 0):
                raise ValueError(f"{nome} deve ser um número positivo.")
        if self.comprimento_a_m < self.largura_b_m:
            raise ValueError(
                "O comprimento a (ao longo da cumeeira) deve ser maior ou igual à largura b: as "
                "Tabelas 6, 7 e 8 da NBR 6123 só cobrem a cumeeira paralela ao lado maior da planta."
            )
        if self.cobertura not in COBERTURAS:
            raise ValueError("Cobertura: plana, duas águas ou uma água.")
        if not (math.isfinite(self.theta_graus) and 0.0 <= self.theta_graus < 90.0):
            raise ValueError("A inclinação θ do telhado deve estar entre 0° e 90°.")
        if self.cobertura == COBERTURA_PLANA and self.theta_graus != 0.0:
            raise ValueError("Cobertura plana tem θ = 0°; escolha duas águas ou uma água.")
        if self.referencia_altura not in REFERENCIAS_DE_ALTURA:
            raise ValueError("Referência de altura: topo da edificação ou beiral.")
        if self.com_vizinhanca and (
            self.afastamento_vizinha_m is None or self.afastamento_vizinha_m < 0
        ):
            raise ValueError("Informe o afastamento s da edificação vizinha (≥ 0).")
        if self.classe is not None and self.classe not in ("A", "B", "C"):
            raise ValueError("Classe A, B ou C (ou automática).")
        if self.periodo_fundamental_s is not None and not self.periodo_fundamental_s > 0:
            raise ValueError("O período fundamental deve ser positivo.")
        if self.beiral_m < 0:
            raise ValueError("O balanço do beiral não pode ser negativo.")
        if self.cpis_informados is not None and not self.cpis_informados:
            raise ValueError("Informe ao menos um valor de c_pi.")

    @property
    def theta_efetivo_graus(self) -> float:
        return 0.0 if self.cobertura == COBERTURA_PLANA else self.theta_graus


# ---------------------------------------------------------------------------
# Geometria derivada
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GeometriaEdificio:
    a_m: float
    b_m: float
    h_m: float
    theta_graus: float
    cobertura: str
    #: altura do ponto mais alto da edificação
    h_topo_m: float
    #: altura da parede longa do lado alto (y = 0) e do lado baixo (y = b)
    h_parede_y0_m: float
    h_parede_yb_m: float
    #: altura h das faixas de h/b dos coeficientes das paredes e do arrasto
    h_tabela_m: float
    #: comprimento da faixa de altas sucções: x = min(max(b/3, a/4), 2h)
    x_m: float
    #: largura y = min(h, 0,15·b) das faixas de c_pe médio do telhado
    y_telhado_m: float
    #: faixa de c_pe médio das paredes paralelas ao vento: min(0,2·b, h)
    faixa_cpe_medio_parede_m: float
    #: comprimento da zona C1/D1 das paredes curtas para vento a ±90°: min(2h, b/2)
    c1_m: float

    @property
    def cos_theta(self) -> float:
        return math.cos(math.radians(self.theta_graus))

    @property
    def sin_theta(self) -> float:
        return math.sin(math.radians(self.theta_graus))

    @property
    def tan_theta(self) -> float:
        return math.tan(math.radians(self.theta_graus))

    @property
    def area_da_agua_m2(self) -> float:
        """Área real de uma metade do telhado (a × b/2, medida no plano da água)."""
        return self.a_m * (self.b_m / 2.0) / self.cos_theta

    def altura_da_parede_curta_m(self, y_m: float) -> float:
        """Altura da parede curta (empena) na posição y ao longo de b."""
        if self.cobertura == COBERTURA_DUAS_AGUAS:
            return self.h_m + self.tan_theta * min(y_m, self.b_m - y_m)
        if self.cobertura == COBERTURA_UMA_AGUA:
            return self.h_parede_y0_m - self.tan_theta * y_m
        return self.h_m

    def area_da_parede_curta_m2(self, y0_m: float, y1_m: float) -> float:
        """Área da parede curta entre y0 e y1: integral exata da altura (que é linear por trechos)."""
        y0, y1 = sorted((max(0.0, y0_m), min(self.b_m, y1_m)))
        if y1 <= y0:
            return 0.0
        pontos = [y0, y1]
        if self.cobertura == COBERTURA_DUAS_AGUAS and y0 < self.b_m / 2.0 < y1:
            pontos.insert(1, self.b_m / 2.0)
        area = 0.0
        for inicio, fim in zip(pontos, pontos[1:], strict=False):
            area += (
                (fim - inicio)
                * 0.5
                * (self.altura_da_parede_curta_m(inicio) + self.altura_da_parede_curta_m(fim))
            )
        return area


def geometria_da_edificacao(entrada: EntradaEdificio) -> GeometriaEdificio:
    a, b, h = entrada.comprimento_a_m, entrada.largura_b_m, entrada.altura_h_m
    theta = entrada.theta_efetivo_graus
    tan = math.tan(math.radians(theta))
    if entrada.cobertura == COBERTURA_DUAS_AGUAS:
        topo = h + (b / 2.0) * tan
        y0 = yb = h
        h_tabela = h
    elif entrada.cobertura == COBERTURA_UMA_AGUA:
        topo = h + b * tan
        y0, yb = h + b * tan, h
        # A norma não diz que h tomar para as paredes de uma edificação de uma água: a altura média
        # das paredes é a escolha coerente com a faixa de h/b da Tabela 6.
        h_tabela = h + (b / 2.0) * tan
    else:
        topo = y0 = yb = h
        h_tabela = h
    return GeometriaEdificio(
        a_m=a,
        b_m=b,
        h_m=h,
        theta_graus=theta,
        cobertura=entrada.cobertura,
        h_topo_m=topo,
        h_parede_y0_m=y0,
        h_parede_yb_m=yb,
        h_tabela_m=h_tabela,
        x_m=min(max(b / 3.0, a / 4.0), 2.0 * h),
        y_telhado_m=min(h, 0.15 * b),
        faixa_cpe_medio_parede_m=min(0.2 * b, h),
        c1_m=min(2.0 * h, b / 2.0),
    )


# ---------------------------------------------------------------------------
# Zonas, pressões e forças
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Parte:
    """Um pedaço plano de uma zona: a área e a normal externa unitária (nos eixos da edificação)."""

    area_m2: float
    normal: Vetor


@dataclass(frozen=True, slots=True)
class Zona:
    """Região da superfície com um mesmo ``C_e`` para um ângulo de incidência."""

    id: str
    superficie: str  # "parede" | "telhado"
    nome: str
    descricao: str
    alpha: int
    ce: float
    partes: tuple[Parte, ...]
    referencia: str

    @property
    def area_m2(self) -> float:
        return sum(parte.area_m2 for parte in self.partes)


@dataclass(frozen=True, slots=True)
class PressaoDaZona:
    zona: Zona
    q_kN_m2: float
    cpi: float
    #: q·f_v·C_e
    pressao_externa_kN_m2: float
    #: q·(f_v·C_e − c_pi): positiva empurra a superfície para dentro; negativa, para fora
    pressao_liquida_kN_m2: float
    #: pressão líquida × área (kN), com o sinal da pressão
    forca_liquida_kN: float


@dataclass(frozen=True, slots=True)
class CasoDeVento:
    """Uma direção do vento com um valor de ``c_pi``: o carregamento completo da edificação."""

    alpha: int
    cpi: coef.SugestaoCpi
    classe: str
    vento: VentoNoLocal
    pressoes: tuple[PressaoDaZona, ...]
    #: resultante horizontal sobre a edificação (a pressão interna se anula nela), kN
    fx_kN: float
    fy_kN: float
    #: resultante vertical sobre o telhado, com a pressão interna (positivo = para cima), kN
    fz_telhado_kN: float

    @property
    def nome(self) -> str:
        return f"Vento a {self.alpha}° · {self.cpi.rotulo}"


@dataclass(frozen=True, slots=True)
class ArrastoGlobal:
    alpha: int
    classe: str
    q_kN_m2: float
    l1_m: float
    l2_m: float
    h_m: float
    area_frontal_m2: float
    ca: coef.ArrastoCa
    fv: float
    forca_kN: float
    excentricidade_m: float
    torsor_kNm: float
    atrito: coef.ForcaAtrito
    soma_das_zonas_kN: float


@dataclass(frozen=True, slots=True)
class LinhaVedacao:
    """Pressão de projeto de uma zona de vedação (telhas, painéis, terças, fixações)."""

    id: str
    superficie: str
    zona: str
    descricao: str
    cpe: float
    fonte_cpe: str  # "C_e" ou "c_pe médio"
    pressao_externa_kN_m2: float
    #: (c_pi, pressão líquida em kN/m²)
    liquida_por_cpi: tuple[tuple[float, float], ...]
    referencia: str

    @property
    def mais_desfavoravel_kN_m2(self) -> float:
        return max((p for _c, p in self.liquida_por_cpi), key=abs)


@dataclass(frozen=True, slots=True)
class ResultadoEdificio:
    entrada: EntradaEdificio
    geometria: GeometriaEdificio
    vento_por_alpha: dict[int, VentoNoLocal]
    classe_por_alpha: dict[int, str]
    vento_vedacoes: VentoNoLocal
    coef_paredes: coef.CoefParedes
    coef_telhado: coef.CoefTelhadoDuasAguas | coef.CoefTelhadoUmaAgua
    alta_turbulencia_por_alpha: dict[int, bool]
    fv_paredes: float
    fv_cobertura: float
    cpis_por_alpha: dict[int, tuple[coef.SugestaoCpi, ...]]
    casos: tuple[CasoDeVento, ...]
    arrasto: dict[int, ArrastoGlobal]
    vedacoes: tuple[LinhaVedacao, ...]
    verificacoes: tuple[Verificacao, ...]
    avisos: tuple[str, ...]
    memoria: tuple[str, ...] = field(default=())

    @property
    def alphas(self) -> tuple[int, ...]:
        return tuple(self.vento_por_alpha)

    def casos_do_angulo(self, alpha: int) -> tuple[CasoDeVento, ...]:
        return tuple(caso for caso in self.casos if caso.alpha == alpha)

    def caso(self, alpha: int, cpi: float) -> CasoDeVento:
        for caso in self.casos:
            if caso.alpha == alpha and abs(caso.cpi.valor - cpi) < 1e-9:
                return caso
        raise KeyError((alpha, cpi))


def _zona(
    id_: str,
    superficie: str,
    nome: str,
    descricao: str,
    alpha: int,
    ce: float,
    partes: list[tuple[float, Vetor]],
    referencia: str,
) -> Zona:
    return Zona(
        id_,
        superficie,
        nome,
        descricao,
        alpha,
        ce,
        tuple(Parte(area, normal) for area, normal in partes if area > 1e-12),
        referencia,
    )


def zonas_das_paredes(
    g: GeometriaEdificio, c: coef.CoefParedes, alpha: int, *, sotavento_reduzido: bool = False
) -> list[Zona]:
    """Zonas das paredes para o vento a 0°, 90° ou −90° (Tabela 6).

    Nas paredes curtas a altura segue o telhado (a empena entra na área). ``sotavento_reduzido``
    aplica 2/3 ao ``C_e`` da parede de sotavento (vento de alta turbulência, 6.1.3.2).
    """
    if alpha not in (0, 90, -90):
        raise ValueError("Paredes: vento a 0°, 90° ou −90°.")
    a, b = g.a_m, g.b_m
    ref = coef.REFERENCIA_PAREDES
    fator = coef.FATOR_SOTAVENTO_ALTA_TURBULENCIA if sotavento_reduzido else 1.0
    h_y0, h_yb = g.h_parede_y0_m, g.h_parede_yb_m
    x1 = g.x_m
    if alpha == 0:
        area_curta = g.area_da_parede_curta_m2(0.0, b)
        return [
            _zona(
                "C",
                "parede",
                "C (barlavento)",
                "Parede curta de barlavento (x = 0), com a empena",
                0,
                c.c_0,
                [(area_curta, (-1.0, 0.0, 0.0))],
                ref,
            ),
            _zona(
                "D",
                "parede",
                "D (sotavento)",
                "Parede curta de sotavento (x = a), com a empena",
                0,
                c.d_0 * fator,
                [(area_curta, (1.0, 0.0, 0.0))],
                ref,
            ),
            _zona(
                "A1B1",
                "parede",
                "A1 e B1",
                f"Paredes longas, nos primeiros {numero_ptbr(x1, 2)} m a partir da empena de barlavento",
                0,
                c.a1_b1_0,
                [(x1 * h_y0, (0.0, -1.0, 0.0)), (x1 * h_yb, (0.0, 1.0, 0.0))],
                ref,
            ),
            _zona(
                "A2B2",
                "parede",
                "A2 e B2",
                f"Paredes longas, de {numero_ptbr(x1, 2)} m até a/2 = {numero_ptbr(a / 2, 2)} m",
                0,
                c.a2_b2_0,
                [((a / 2 - x1) * h_y0, (0.0, -1.0, 0.0)), ((a / 2 - x1) * h_yb, (0.0, 1.0, 0.0))],
                ref,
            ),
            _zona(
                "A3B3",
                "parede",
                "A3 e B3",
                f"Paredes longas, de a/2 = {numero_ptbr(a / 2, 2)} m até a empena de sotavento",
                0,
                c.a3_b3_0,
                [(a / 2 * h_y0, (0.0, -1.0, 0.0)), (a / 2 * h_yb, (0.0, 1.0, 0.0))],
                ref,
            ),
        ]
    c1 = g.c1_m
    if alpha == 90:  # sopra de y = 0 para y = b: barlavento é a parede do lado y = 0
        barlavento = ("A", a * h_y0, (0.0, -1.0, 0.0), "y = 0")
        sotavento = ("B", a * h_yb, (0.0, 1.0, 0.0), "y = b")
        c1_area = g.area_da_parede_curta_m2(0.0, c1)
        c2_area = g.area_da_parede_curta_m2(c1, b)
    else:  # −90: sopra de y = b para y = 0
        barlavento = ("A", a * h_yb, (0.0, 1.0, 0.0), "y = b")
        sotavento = ("B", a * h_y0, (0.0, -1.0, 0.0), "y = 0")
        c1_area = g.area_da_parede_curta_m2(b - c1, b)
        c2_area = g.area_da_parede_curta_m2(0.0, b - c1)
    return [
        _zona(
            "A",
            "parede",
            "A (barlavento)",
            f"Parede longa de barlavento ({barlavento[3]})",
            alpha,
            c.a_90,
            [(barlavento[1], barlavento[2])],
            ref,
        ),
        _zona(
            "B",
            "parede",
            "B (sotavento)",
            f"Parede longa de sotavento ({sotavento[3]})",
            alpha,
            c.b_90 * fator,
            [(sotavento[1], sotavento[2])],
            ref,
        ),
        _zona(
            "C1D1",
            "parede",
            "C1 e D1",
            f"Paredes curtas, primeiros {numero_ptbr(c1, 2)} m a partir da parede longa de barlavento",
            alpha,
            c.c1_d1_90,
            [(c1_area, (-1.0, 0.0, 0.0)), (c1_area, (1.0, 0.0, 0.0))],
            ref,
        ),
        _zona(
            "C2D2",
            "parede",
            "C2 e D2",
            "Paredes curtas, restante da largura, com a empena",
            alpha,
            c.c2_d2_90,
            [(c2_area, (-1.0, 0.0, 0.0)), (c2_area, (1.0, 0.0, 0.0))],
            ref,
        ),
    ]


def zonas_do_telhado(
    g: GeometriaEdificio, c: coef.CoefTelhadoDuasAguas | coef.CoefTelhadoUmaAgua
) -> dict[int, list[Zona]]:
    """Zonas do telhado por ângulo de incidência (Tabelas 7 e 8)."""
    a, b = g.a_m, g.b_m
    cos, sin = g.cos_theta, g.sin_theta
    x1 = g.x_m
    meia = g.area_da_agua_m2

    if isinstance(c, coef.CoefTelhadoDuasAguas):
        ref = coef.REFERENCIA_DUAS_AGUAS
        n_y0 = (0.0, -sin, cos)  # água do lado y = 0
        n_yb = (0.0, sin, cos)  # água do lado y = b

        def faixa(comprimento: float) -> float:
            return comprimento * (b / 2.0) / cos

        return {
            0: [
                _zona(
                    "EG",
                    "telhado",
                    "E e G",
                    f"Duas águas, primeiros {numero_ptbr(x1, 2)} m a partir da empena de barlavento",
                    0,
                    c.eg_0,
                    [(faixa(x1), n_y0), (faixa(x1), n_yb)],
                    ref,
                ),
                _zona(
                    "FH",
                    "telhado",
                    "F e H",
                    f"Duas águas, de {numero_ptbr(x1, 2)} m até a/2 = {numero_ptbr(a / 2, 2)} m",
                    0,
                    c.fh_0,
                    [(faixa(a / 2 - x1), n_y0), (faixa(a / 2 - x1), n_yb)],
                    ref,
                ),
                _zona(
                    "IJ",
                    "telhado",
                    "I e J",
                    "Duas águas, de a/2 até a empena de sotavento (Nota 3)",
                    0,
                    c.ij_0,
                    [(faixa(a / 2), n_y0), (faixa(a / 2), n_yb)],
                    ref,
                ),
            ],
            90: [
                _zona(
                    "EFI",
                    "telhado",
                    "E, F e I (barlavento)",
                    "Água de barlavento, vento perpendicular à cumeeira",
                    90,
                    c.efi_90,
                    [(meia, n_y0)],
                    ref,
                ),
                _zona(
                    "GHJ",
                    "telhado",
                    "G, H e J (sotavento)",
                    "Água de sotavento, vento perpendicular à cumeeira",
                    90,
                    c.ghj_90,
                    [(meia, n_yb)],
                    ref,
                ),
            ],
        }

    ref = coef.REFERENCIA_UMA_AGUA
    normal = (0.0, sin, cos)  # a água inteira desce para +y

    def faixa_uma(comprimento: float) -> float:
        return comprimento * b / cos

    return {
        0: [
            _zona(
                "HL_ate_b2",
                "telhado",
                "H e L (até b/2)",
                f"Primeiros {numero_ptbr(b / 2, 2)} m a partir da empena de barlavento",
                0,
                c.hl_0_ate_b2,
                [(faixa_uma(b / 2), normal)],
                ref,
            ),
            _zona(
                "HL_de_b2",
                "telhado",
                "H e L (de b/2 até a/2)",
                f"De b/2 = {numero_ptbr(b / 2, 2)} m até a/2 = {numero_ptbr(a / 2, 2)} m",
                0,
                c.hl_0_de_b2_a_a2,
                [(faixa_uma((a - b) / 2), normal)],
                ref,
            ),
            _zona(
                "IJ",
                "telhado",
                "I e J",
                "Metade de sotavento, de a/2 até a (Nota 1)",
                0,
                c.ij_0,
                [(faixa_uma(a / 2), normal)],
                ref,
            ),
        ],
        90: [
            _zona(
                "HI",
                "telhado",
                "H e I (lado alto, barlavento)",
                "Metade do lado alto: o vento sopra a favor da inclinação",
                90,
                c.hi_90,
                [(meia, normal)],
                ref,
            ),
            _zona(
                "LJ",
                "telhado",
                "L e J (lado baixo, sotavento)",
                "Metade do lado baixo",
                90,
                c.lj_90,
                [(meia, normal)],
                ref,
            ),
        ],
        -90: [
            _zona(
                "LJ",
                "telhado",
                "L e J (lado baixo, barlavento)",
                "Metade do lado baixo: o vento sopra contra a inclinação",
                -90,
                c.lj_m90,
                [(meia, normal)],
                ref,
            ),
            _zona(
                "HI",
                "telhado",
                "H e I (lado alto, sotavento)",
                "Metade do lado alto",
                -90,
                c.hi_m90,
                [(meia, normal)],
                ref,
            ),
        ],
    }


def zonas_do_telhado_obliquo(
    g: GeometriaEdificio, c: coef.CoefTelhadoUmaAgua
) -> dict[int, list[Zona]]:
    """Quadrantes H e L da cobertura de uma água para o vento oblíquo (±45°), só informativos."""
    normal = (0.0, g.sin_theta, g.cos_theta)
    quadrante = (g.a_m / 2.0) * (g.b_m / 2.0) / g.cos_theta
    ref = coef.REFERENCIA_UMA_AGUA
    return {
        45: [
            _zona(
                "H",
                "telhado",
                "H",
                "Quadrante H, vento oblíquo a 45°",
                45,
                c.h_45,
                [(quadrante, normal)],
                ref,
            ),
            _zona(
                "L",
                "telhado",
                "L",
                "Quadrante L, vento oblíquo a 45°",
                45,
                c.l_45,
                [(quadrante, normal)],
                ref,
            ),
        ],
        -45: [
            _zona(
                "H",
                "telhado",
                "H",
                "Quadrante H, vento oblíquo a −45°",
                -45,
                c.h_m45,
                [(quadrante, normal)],
                ref,
            ),
            _zona(
                "L",
                "telhado",
                "L",
                "Quadrante L, vento oblíquo a −45°",
                -45,
                c.l_m45,
                [(quadrante, normal)],
                ref,
            ),
        ],
    }


def _soma(partes: tuple[Parte, ...], pressao_kN_m2: float) -> Vetor:
    """Força sobre a estrutura de uma zona sob pressão uniforme: ``−p·A·n`` (kN)."""
    fx = fy = fz = 0.0
    for parte in partes:
        nx, ny, nz = parte.normal
        f = -pressao_kN_m2 * parte.area_m2
        fx += f * nx
        fy += f * ny
        fz += f * nz
    return fx, fy, fz


def _pressao_da_zona(zona: Zona, q_kN_m2: float, cpi: float, fv: float) -> PressaoDaZona:
    externa = q_kN_m2 * fv * zona.ce
    liquida = q_kN_m2 * (fv * zona.ce - cpi)
    return PressaoDaZona(zona, q_kN_m2, cpi, externa, liquida, liquida * zona.area_m2)


def _caso(
    alpha: int,
    cpi: coef.SugestaoCpi,
    classe: str,
    vento: VentoNoLocal,
    zonas: list[Zona],
    fv_por_superficie: dict[str, float],
) -> CasoDeVento:
    pressoes = tuple(
        _pressao_da_zona(z, vento.q_kN_m2, cpi.valor, fv_por_superficie[z.superficie])
        for z in zonas
    )
    fx = fy = fz_telhado = 0.0
    for p in pressoes:
        x, y, z = _soma(p.zona.partes, p.pressao_liquida_kN_m2)
        fx += x
        fy += y
        if p.zona.superficie == "telhado":
            fz_telhado += z
    return CasoDeVento(alpha, cpi, classe, vento, pressoes, fx, fy, fz_telhado)


# ---------------------------------------------------------------------------
# Vedações e elementos locais (c_pe médio)
# ---------------------------------------------------------------------------


def _linhas_de_vedacao(
    g: GeometriaEdificio,
    cp: coef.CoefParedes,
    ct: coef.CoefTelhadoDuasAguas | coef.CoefTelhadoUmaAgua,
    zonas: dict[int, list[Zona]],
    q_ved_kN_m2: float,
    cpis_por_alpha: dict[int, tuple[coef.SugestaoCpi, ...]],
    fv_paredes: float,
    fv_cobertura: float,
) -> list[LinhaVedacao]:
    todos_cpis = _cpis_unicos(cpis_por_alpha)

    def liquida(cpe: float, fv: float, cpis: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
        return tuple((cpi, q_ved_kN_m2 * (fv * cpe - cpi)) for cpi in cpis)

    linhas: list[LinhaVedacao] = []
    for alpha, lista in zonas.items():
        if alpha not in cpis_por_alpha:
            continue
        cpis = tuple(s.valor for s in cpis_por_alpha[alpha])
        for z in lista:
            fv = fv_paredes if z.superficie == "parede" else fv_cobertura
            linhas.append(
                LinhaVedacao(
                    f"{z.superficie}-{alpha}-{z.id}",
                    z.superficie,
                    f"{z.nome} (vento a {alpha}°)",
                    z.descricao,
                    z.ce,
                    "C_e",
                    q_ved_kN_m2 * fv * z.ce,
                    liquida(z.ce, fv, cpis),
                    z.referencia,
                )
            )
    faixa = numero_ptbr(g.faixa_cpe_medio_parede_m, 2)
    linhas.append(
        LinhaVedacao(
            "parede-cpe-medio",
            "parede",
            "Paredes paralelas ao vento — faixa de altas sucções",
            f"Faixa de {faixa} m (= menor entre 0,2·b e h) junto à aresta de barlavento",
            cp.cpe_medio,
            "c_pe médio",
            q_ved_kN_m2 * fv_paredes * cp.cpe_medio,
            liquida(cp.cpe_medio, fv_paredes, todos_cpis),
            coef.REFERENCIA_PAREDES + ", c_pe médio",
        )
    )
    y = numero_ptbr(g.y_telhado_m, 2)
    x = numero_ptbr(g.x_m, 2)
    if isinstance(ct, coef.CoefTelhadoDuasAguas):
        zonas_cpe = (
            (
                "telhado-empena",
                "Telhado — faixas das empenas",
                f"Faixa de largura y = {y} m em cada empena",
                ct.empena,
            ),
            (
                "telhado-canto",
                "Telhado — cantos do beiral",
                f"Blocos de x = {x} m ao longo do beiral, ao lado da faixa da empena, com largura y = {y} m",
                ct.canto,
            ),
            (
                "telhado-beiral",
                "Telhado — beiral entre os cantos",
                f"Faixa de largura y = {y} m ao longo do beiral",
                ct.beiral,
            ),
            (
                "telhado-cumeeira",
                "Telhado — cumeeira",
                f"Faixa de largura y = {y} m de cada lado da cumeeira",
                ct.cumeeira,
            ),
        )
        referencia = coef.REFERENCIA_DUAS_AGUAS + ", c_pe médio"
        for id_, nome, descricao, valor in zonas_cpe:
            if valor is None:
                continue
            linhas.append(
                LinhaVedacao(
                    id_,
                    "telhado",
                    nome,
                    descricao,
                    valor,
                    "c_pe médio",
                    q_ved_kN_m2 * fv_cobertura * valor,
                    liquida(valor, fv_cobertura, todos_cpis),
                    referencia,
                )
            )
    else:
        referencia = coef.REFERENCIA_UMA_AGUA + ", c_pe médio"
        for id_, nome, valor in (
            ("telhado-h1", "Telhado — zona H1", ct.h1),
            ("telhado-h2", "Telhado — zona H2", ct.h2),
            ("telhado-l1", "Telhado — zona L1", ct.l1),
            ("telhado-l2", "Telhado — zona L2", ct.l2),
            ("telhado-he", "Telhado — beiral do lado alto (He)", ct.he),
            ("telhado-le", "Telhado — beiral do lado baixo (Le)", ct.le),
        ):
            linhas.append(
                LinhaVedacao(
                    id_,
                    "telhado",
                    nome,
                    f"Faixas H e L da figura da Tabela 8 (y = {y} m)",
                    valor,
                    "c_pe médio",
                    q_ved_kN_m2 * fv_cobertura * valor,
                    liquida(valor, fv_cobertura, todos_cpis),
                    referencia,
                )
            )
    return linhas


def _cpis_unicos(cpis_por_alpha: dict[int, tuple[coef.SugestaoCpi, ...]]) -> tuple[float, ...]:
    vistos: list[float] = []
    for lista in cpis_por_alpha.values():
        for sugestao in lista:
            if all(abs(sugestao.valor - v) > 1e-9 for v in vistos):
                vistos.append(sugestao.valor)
    return tuple(sorted(vistos))


# ---------------------------------------------------------------------------
# O cálculo
# ---------------------------------------------------------------------------


def _vento_da_direcao(
    entrada: EntradaEdificio, g: GeometriaEdificio, alpha: int
) -> tuple[VentoNoLocal, str, list[str]]:
    """Vento sobre a estrutura na direção ``alpha``: a classe vem da superfície frontal."""
    l1 = g.b_m if alpha == 0 else g.a_m
    dimensao_frontal = max(l1, g.h_topo_m)
    classe = entrada.classe or classe_da_edificacao(dimensao_frontal)
    z = g.h_topo_m if entrada.referencia_altura == REFERENCIA_ALTURA_TOPO else g.h_m
    notas: list[str] = []
    if dimensao_frontal > LIMITE_ANEXO_A_M and entrada.classe is None:
        tempo = intervalo_de_tempo_anexo_a(
            dimensao_frontal, entrada.v0_m_s, entrada.s1, entrada.categoria, g.h_topo_m
        )
        vento = calcular_vento_no_local(
            entrada.v0_m_s,
            s1=entrada.s1,
            categoria=entrada.categoria,
            classe=None,
            t_s=tempo,
            altura_m=z,
            grupo_s3=entrada.grupo_s3,
            s3=entrada.s3,
        )
        notas.append(
            f"Superfície frontal de {numero_ptbr(dimensao_frontal, 1)} m (> 80 m): intervalo de "
            f"tempo t = 7,5·L_t/V_t(h) = {numero_ptbr(tempo, 1)} s (Anexo A, A.2)."
        )
        return vento, "C", notas
    vento = calcular_vento_no_local(
        entrada.v0_m_s,
        s1=entrada.s1,
        categoria=entrada.categoria,
        classe=classe,
        altura_m=z,
        grupo_s3=entrada.grupo_s3,
        s3=entrada.s3,
    )
    return vento, classe, notas


def _cpis_do_cenario(
    entrada: EntradaEdificio, alphas: tuple[int, ...]
) -> dict[int, tuple[coef.SugestaoCpi, ...]]:
    saida: dict[int, tuple[coef.SugestaoCpi, ...]] = {}
    for alpha in alphas:
        if entrada.cpis_informados is not None:
            saida[alpha] = tuple(
                coef.SugestaoCpi(
                    float(valor),
                    f"c_pi = {numero_ptbr(valor, 2)} (informado)",
                    "informado pelo projetista",
                )
                for valor in entrada.cpis_informados
            )
        else:
            base = 90 if alpha == -90 else alpha
            saida[alpha] = tuple(coef.sugerir_cpi(entrada.cenario_permeabilidade, base))
    return saida


def calcular_edificacao(entrada: EntradaEdificio) -> ResultadoEdificio:
    """Calcula a ação do vento na edificação inteira (ver o docstring do módulo)."""
    entrada.validar()
    g = geometria_da_edificacao(entrada)
    a, b, h = g.a_m, g.b_m, g.h_m
    avisos: list[str] = []
    memoria: list[str] = []
    uma_agua = entrada.cobertura == COBERTURA_UMA_AGUA

    cp = coef.coeficientes_paredes(a, b, g.h_tabela_m)
    if uma_agua:
        ct: coef.CoefTelhadoDuasAguas | coef.CoefTelhadoUmaAgua = (
            coef.coeficientes_telhado_uma_agua(a, b, h, g.theta_graus)
        )
    else:
        ct = coef.coeficientes_telhado_duas_aguas(a, b, h, g.theta_graus)
    avisos.extend(cp.avisos)
    avisos.extend(ct.avisos)

    alphas: tuple[int, ...] = (0, 90, -90) if uma_agua else (0, 90)
    vento_por_alpha: dict[int, VentoNoLocal] = {}
    classe_por_alpha: dict[int, str] = {}
    for alpha in alphas:
        if alpha == -90:
            vento_por_alpha[alpha] = vento_por_alpha[90]
            classe_por_alpha[alpha] = classe_por_alpha[90]
            continue
        vento, classe, notas = _vento_da_direcao(entrada, g, alpha)
        vento_por_alpha[alpha], classe_por_alpha[alpha] = vento, classe
        avisos.extend(notas)
        avisos.extend(vento.avisos)
    avisos = list(dict.fromkeys(avisos))

    z_ved = g.h_topo_m
    vento_ved = calcular_vento_no_local(
        entrada.v0_m_s,
        s1=entrada.s1,
        categoria=entrada.categoria,
        classe="A",
        altura_m=z_ved,
        grupo_s3=entrada.grupo_s3,
        s3=entrada.s3,
        vedacao=entrada.vedacoes_com_092 and entrada.s3 is None,
    )
    avisos.extend(aviso for aviso in vento_ved.avisos if aviso not in avisos)

    # ------------------------------------------------------------ turbulência e vizinhança
    alta_por_alpha: dict[int, bool] = {}
    motivos_alta: dict[int, list[str]] = {}
    for alpha in alphas:
        if not entrada.alta_turbulencia:
            alta_por_alpha[alpha] = False
            continue
        largura, profundidade = (b, a) if alpha == 0 else (a, b)
        ok, motivos = coef.verificar_alta_turbulencia(
            g.h_topo_m,
            largura,
            profundidade,
            altura_media_vizinhanca_m=entrada.altura_media_vizinhanca_m,
            extensao_vizinhanca_m=entrada.extensao_vizinhanca_m,
        )
        alta_por_alpha[alpha] = ok
        motivos_alta[alpha] = motivos
    if entrada.com_vizinhanca:
        assert entrada.afastamento_vizinha_m is not None
        fv_paredes = coef.fator_de_vizinhanca(
            entrada.afastamento_vizinha_m, a, b, na_cobertura=False
        )
        fv_cobertura = coef.fator_de_vizinhanca(
            entrada.afastamento_vizinha_m, a, b, na_cobertura=True
        )
    else:
        fv_paredes = fv_cobertura = 1.0
    fv_por_superficie = {"parede": fv_paredes, "telhado": fv_cobertura}

    # ------------------------------------------------------------ zonas
    cpis = _cpis_do_cenario(entrada, alphas)
    zonas_telhado = zonas_do_telhado(g, ct)
    zonas_por_alpha: dict[int, list[Zona]] = {}
    for alpha in alphas:
        paredes = zonas_das_paredes(g, cp, alpha, sotavento_reduzido=alta_por_alpha[alpha])
        zonas_por_alpha[alpha] = paredes + zonas_telhado.get(alpha, [])
    casos: list[CasoDeVento] = []
    for alpha in alphas:
        for cpi in cpis[alpha]:
            casos.append(
                _caso(
                    alpha,
                    cpi,
                    classe_por_alpha[alpha],
                    vento_por_alpha[alpha],
                    zonas_por_alpha[alpha],
                    fv_por_superficie,
                )
            )

    # ------------------------------------------------------------ arrasto global, torção e atrito
    e_a, e_b = coef.excentricidades(a, b, com_vizinhanca=entrada.com_vizinhanca)
    arrasto: dict[int, ArrastoGlobal] = {}
    for alpha in (0, 90):
        l1, l2 = (b, a) if alpha == 0 else (a, b)
        h_ca = g.h_tabela_m
        q = vento_por_alpha[alpha].q_kN_m2
        ca = coef.coeficiente_arrasto_paralelepipedo(
            h_ca, l1, l2, alta_turbulencia=alta_por_alpha[alpha]
        )
        a_e = l1 * h_ca
        forca = q * ca.valor * a_e * fv_paredes
        excentricidade = e_b if alpha == 0 else e_a
        primeiro = next(c for c in casos if c.alpha == alpha)
        componente = abs(primeiro.fx_kN) if alpha == 0 else abs(primeiro.fy_kN)
        arrasto[alpha] = ArrastoGlobal(
            alpha=alpha,
            classe=classe_por_alpha[alpha],
            q_kN_m2=q,
            l1_m=l1,
            l2_m=l2,
            h_m=h_ca,
            area_frontal_m2=a_e,
            ca=ca,
            fv=fv_paredes,
            forca_kN=forca,
            excentricidade_m=excentricidade,
            torsor_kNm=forca * excentricidade,
            atrito=coef.forca_de_atrito(q * 1e3, entrada.ct_atrito, h_ca, l1, l2),
            soma_das_zonas_kN=componente,
        )
        avisos.extend(aviso for aviso in ca.avisos if aviso not in avisos)

    # ------------------------------------------------------------ vedações
    todas_zonas_para_vedacao = {alpha: zonas_por_alpha[alpha] for alpha in alphas}
    vedacoes = _linhas_de_vedacao(
        g, cp, ct, todas_zonas_para_vedacao, vento_ved.q_kN_m2, cpis, fv_paredes, fv_cobertura
    )

    verificacoes = _verificacoes(
        entrada, g, cp, ct, vento_por_alpha, classe_por_alpha, vento_ved, arrasto, alta_por_alpha,
        motivos_alta, fv_paredes, fv_cobertura, cpis, casos,
    )  # fmt: skip
    memoria.extend(_memoria(entrada, g, vento_por_alpha, classe_por_alpha, vento_ved, arrasto))
    return ResultadoEdificio(
        entrada=entrada,
        geometria=g,
        vento_por_alpha=vento_por_alpha,
        classe_por_alpha=classe_por_alpha,
        vento_vedacoes=vento_ved,
        coef_paredes=cp,
        coef_telhado=ct,
        alta_turbulencia_por_alpha=alta_por_alpha,
        fv_paredes=fv_paredes,
        fv_cobertura=fv_cobertura,
        cpis_por_alpha=cpis,
        casos=tuple(casos),
        arrasto=arrasto,
        vedacoes=tuple(vedacoes),
        verificacoes=tuple(verificacoes),
        avisos=tuple(avisos),
        memoria=tuple(memoria),
    )


# ---------------------------------------------------------------------------
# Verificações de aplicabilidade e de regime estático
# ---------------------------------------------------------------------------

REF_6123 = "NBR 6123:2023"


def _limite(
    nome: str, atende: bool, referencia: str, texto: str, *, alerta: bool = True
) -> Verificacao:
    """Linha de limite: OK quando o campo da norma é respeitado; ALERTA (ou NÃO OK) quando não."""
    status = "OK" if atende else ("ALERTA" if alerta else "NÃO OK")
    return Verificacao(nome, None, None, "—", referencia, texto, status=status, tipo="limite")


def _info(
    nome: str, valor: float | None, unidade: str, referencia: str, formula: str = ""
) -> Verificacao:
    return Verificacao(
        nome, None, valor, unidade, referencia, formula, status="INFO", tipo="informativo"
    )


def estimar_periodo_edificio_aco_s(h_m: float) -> float:
    """``T₁ = 0,29·√h − 0,4`` (h em m), edifícios com estrutura de aço soldada — Tabela 31 da norma."""
    return max(0.29 * math.sqrt(float(h_m)) - 0.4, 0.0)


def _verificacoes(
    entrada: EntradaEdificio,
    g: GeometriaEdificio,
    cp: coef.CoefParedes,
    ct: coef.CoefTelhadoDuasAguas | coef.CoefTelhadoUmaAgua,
    vento_por_alpha: dict[int, VentoNoLocal],
    classe_por_alpha: dict[int, str],
    vento_ved: VentoNoLocal,
    arrasto: dict[int, ArrastoGlobal],
    alta_por_alpha: dict[int, bool],
    motivos_alta: dict[int, list[str]],
    fv_paredes: float,
    fv_cobertura: float,
    cpis: dict[int, tuple[coef.SugestaoCpi, ...]],
    casos: list[CasoDeVento],
) -> list[Verificacao]:
    a, b, h = g.a_m, g.b_m, g.h_m
    linhas: list[Verificacao] = []

    # --- aplicabilidade das tabelas
    razao_ab, razao_hb = a / b, g.h_tabela_m / b
    linhas.append(
        _limite(
            "Planta: 1 ≤ a/b ≤ 4 (Tabela 6)",
            razao_ab <= 4.0 + 1e-9,
            f"{REF_6123}, Tabela 6",
            f"a/b = {numero_ptbr(a, 2)}/{numero_ptbr(b, 2)} = {numero_ptbr(razao_ab, 2)}"
            + (
                ""
                if razao_ab <= 4.0 + 1e-9
                else "; acima de 4 usam-se os valores de a/b = 4, sem respaldo da tabela"
            ),
        )
    )
    linhas.append(
        _limite(
            "Altura: h/b ≤ 6 (Tabelas 6 e 7)",
            razao_hb <= 6.0 + 1e-9,
            f"{REF_6123}, Tabelas 6 e 7",
            f"h/b = {numero_ptbr(g.h_tabela_m, 2)}/{numero_ptbr(b, 2)} = {numero_ptbr(razao_hb, 2)}",
        )
    )
    theta = g.theta_graus
    if entrada.cobertura == COBERTURA_DUAS_AGUAS:
        linhas.append(
            _limite(
                "Telhado de duas águas: θ ≤ 60° (Tabela 7)",
                theta <= 60.0 + 1e-9,
                f"{REF_6123}, Tabela 7",
                f"θ = {numero_ptbr(theta, 1)}°",
            )
        )
    elif entrada.cobertura == COBERTURA_UMA_AGUA:
        linhas.append(
            _limite(
                "Telhado de uma água: 5° ≤ θ ≤ 30° (Tabela 8)",
                5.0 - 1e-9 <= theta <= 30.0 + 1e-9,
                f"{REF_6123}, Tabela 8",
                f"θ = {numero_ptbr(theta, 1)}°",
            )
        )
        linhas.append(
            _limite(
                "Telhado de uma água: h/b < 2 (Tabela 8)",
                h / b < coef.H_SOBRE_B_MAXIMO_UMA_AGUA,
                f"{REF_6123}, Tabela 8",
                f"h/b = {numero_ptbr(h / b, 2)}",
            )
        )
    if entrada.beiral_m > 0:
        limite = FRACAO_BEIRAL_MAXIMA * b
        linhas.append(
            _limite(
                "Balanço do beiral ≤ 0,1·b (Detalhe I da Tabela 7)",
                entrada.beiral_m <= limite + 1e-9,
                f"{REF_6123}, Tabela 7, Detalhe I",
                f"balanço = {numero_ptbr(entrada.beiral_m, 2)} m; 0,1·b = {numero_ptbr(limite, 2)} m",
            )
        )
    zg = ALTURA_GRADIENTE_M[entrada.categoria]
    linhas.append(
        _limite(
            f"Altura abaixo da camada limite z_g = {numero_ptbr(zg, 0)} m",
            g.h_topo_m <= zg,
            f"{REF_6123}, 5.3.3",
            f"altura da edificação = {numero_ptbr(g.h_topo_m, 1)} m (categoria {entrada.categoria})",
        )
    )

    # --- regime estático
    t1 = entrada.periodo_fundamental_s
    origem_t = "informado"
    if t1 is None:
        t1 = estimar_periodo_edificio_aco_s(g.h_topo_m)
        origem_t = "estimado por T₁ = 0,29·√h − 0,4 (Tabela 31, aço soldado)"
    linhas.append(
        _limite(
            "Período fundamental T₁ ≤ 1 s: regime estático",
            t1 <= PERIODO_LIMITE_ESTATICO_S,
            f"{REF_6123}, 4.1 e Seção 9",
            f"T₁ = {numero_ptbr(t1, 2)} s ({origem_t}); acima de 1 s a resposta flutuante pode ser "
            "importante e a norma pede análise dinâmica (Seção 9)",
        )
    )
    esbeltez = g.h_topo_m / b
    linhas.append(
        _limite(
            "Esbeltez h/b < 6: sem verificação de vórtices",
            esbeltez < ESBELTEZ_VORTICES,
            f"{REF_6123}, 10.2",
            f"h/b = {numero_ptbr(esbeltez, 2)}; a partir de 6 o desprendimento de vórtices deve "
            "ser investigado (Seção 10)",
        )
    )

    # --- turbulência e vizinhança
    if entrada.alta_turbulencia:
        for alpha, ok in alta_por_alpha.items():
            if alpha == -90:
                continue
            linhas.append(
                _limite(
                    f"Alta turbulência (vento a {alpha}°)",
                    ok,
                    f"{REF_6123}, 6.1.3.1",
                    "critérios atendidos: C_e de sotavento × 2/3 e C_a da Figura 5"
                    if ok
                    else "não aplicada, porque " + "; ".join(motivos_alta.get(alpha, [])),
                )
            )
    if entrada.com_vizinhanca:
        linhas.append(
            _info(
                "Fator de vizinhança f_v (paredes, C_a e c_pe médio)",
                fv_paredes,
                "—",
                f"{REF_6123}, 6.4.4",
                f"s = {numero_ptbr(entrada.afastamento_vizinha_m or 0.0, 2)} m",
            )
        )
        linhas.append(
            _info(
                "Fator de vizinhança f_v (cobertura)",
                fv_cobertura,
                "—",
                f"{REF_6123}, 6.4.4",
            )
        )

    # --- valores de apoio
    for alpha in (0, 90):
        vento = vento_por_alpha[alpha]
        linhas.append(
            _info(
                f"V_k do vento a {alpha}° (classe {classe_por_alpha[alpha]})",
                vento.vk_m_s,
                "m/s",
                f"{REF_6123}, 4.2 e 5",
                "; ".join(vento.memoria[2:5]),
            )
        )
        linhas.append(
            _info(
                f"q do vento a {alpha}° (estrutura)",
                vento.q_kN_m2,
                "kN/m²",
                f"{REF_6123}, 4.2",
                vento.memoria[5],
            )
        )
    linhas.append(
        _info(
            "q das vedações (classe A, topo da edificação)",
            vento_ved.q_kN_m2,
            "kN/m²",
            f"{REF_6123}, 6.1.1 e Tabela 4",
            "; ".join(vento_ved.memoria[2:6]),
        )
    )
    for alpha in (0, 90):
        r = arrasto[alpha]
        linhas.append(
            _info(
                f"C_a do vento a {alpha}° ({r.ca.figura})",
                r.ca.valor,
                "—",
                f"{REF_6123}, 6.1.2",
                f"h/ℓ₁ = {numero_ptbr(r.ca.h_sobre_l1, 2)}; ℓ₁/ℓ₂ = {numero_ptbr(r.ca.l1_sobre_l2, 2)}",
            )
        )
        linhas.append(
            _info(
                f"Força de arrasto F_a do vento a {alpha}°",
                r.forca_kN,
                "kN",
                f"{REF_6123}, 4.3.3",
                f"F_a = q·C_a·A_e·f_v = {numero_ptbr(r.q_kN_m2, 3)} × {numero_ptbr(r.ca.valor, 2)} × "
                f"{numero_ptbr(r.area_frontal_m2, 1)} × {numero_ptbr(r.fv, 2)} = "
                f"{numero_ptbr(r.forca_kN, 1)} kN",
            )
        )
        linhas.append(
            _info(
                f"Momento de torção do vento a {alpha}°",
                r.torsor_kNm,
                "kN·m",
                f"{REF_6123}, 6.1.4",
                f"M_t = F_a·e = {numero_ptbr(r.forca_kN, 1)} × {numero_ptbr(r.excentricidade_m, 2)} = "
                f"{numero_ptbr(r.torsor_kNm, 1)} kN·m",
            )
        )
        if r.atrito.aplica:
            linhas.append(
                _info(
                    f"Força de atrito do vento a {alpha}°",
                    r.atrito.total_kN,
                    "kN",
                    f"{REF_6123}, 6.1.5",
                    f"telhado {numero_ptbr(r.atrito.telhado_kN, 1)} kN + paredes "
                    f"{numero_ptbr(r.atrito.paredes_kN, 1)} kN (C_t = {numero_ptbr(r.atrito.ct, 2)})",
                )
            )
    horizontais_ja_listadas: set[int] = set()
    for caso in casos:
        if caso.alpha not in horizontais_ja_listadas:
            # A pressão interna não muda a resultante horizontal: uma linha por direção basta.
            horizontais_ja_listadas.add(caso.alpha)
            linhas.append(
                _info(
                    f"Resultante horizontal do vento a {caso.alpha}°",
                    math.hypot(caso.fx_kN, caso.fy_kN),
                    "kN",
                    f"{REF_6123}, 6.1.1",
                    f"soma das pressões nas paredes e no telhado: F_x = "
                    f"{numero_ptbr(caso.fx_kN, 1)} kN; F_y = {numero_ptbr(caso.fy_kN, 1)} kN "
                    "(a pressão interna se anula)",
                )
            )
        linhas.append(
            _info(
                f"Empuxo vertical no telhado, vento a {caso.alpha}°, {caso.cpi.rotulo}",
                caso.fz_telhado_kN,
                "kN",
                f"{REF_6123}, 6.1.1 e 6.3",
                "positivo = para cima; com a pressão interna sobre a face de baixo do telhado",
            )
        )
    return linhas


def _memoria(
    entrada: EntradaEdificio,
    g: GeometriaEdificio,
    vento_por_alpha: dict[int, VentoNoLocal],
    classe_por_alpha: dict[int, str],
    vento_ved: VentoNoLocal,
    arrasto: dict[int, ArrastoGlobal],
) -> list[str]:
    linhas = [
        "Geometria: a = "
        f"{numero_ptbr(g.a_m, 2)} m, b = {numero_ptbr(g.b_m, 2)} m, h = {numero_ptbr(g.h_m, 2)} m, "
        f"θ = {numero_ptbr(g.theta_graus, 1)}°, altura do topo = {numero_ptbr(g.h_topo_m, 2)} m; "
        f"x = máx(b/3; a/4) ≤ 2h = {numero_ptbr(g.x_m, 2)} m; y = mín(h; 0,15·b) = "
        f"{numero_ptbr(g.y_telhado_m, 2)} m"
    ]
    for alpha in (0, 90):
        vento = vento_por_alpha[alpha]
        linhas.append(
            f"Vento a {alpha}° — estrutura, classe {classe_por_alpha[alpha]}: "
            + "; ".join(vento.memoria[2:])
        )
    linhas.append("Vento nas vedações — classe A, topo: " + "; ".join(vento_ved.memoria[2:]))
    for alpha in (0, 90):
        r = arrasto[alpha]
        linhas.append(
            f"Arrasto a {alpha}°: C_a = {numero_ptbr(r.ca.valor, 2)} ({r.ca.figura}); "
            f"A_e = ℓ₁·h = {numero_ptbr(r.l1_m, 2)} × {numero_ptbr(r.h_m, 2)} = "
            f"{numero_ptbr(r.area_frontal_m2, 1)} m²; F_a = q·C_a·A_e·f_v = "
            f"{numero_ptbr(r.forca_kN, 1)} kN; M_t = F_a·e = {numero_ptbr(r.torsor_kNm, 1)} kN·m"
        )
    return linhas


# ---------------------------------------------------------------------------
# Tabelas para a tela e o memorial
# ---------------------------------------------------------------------------


def tabela_de_pressoes(caso: CasoDeVento) -> list[dict[str, object]]:
    """Uma linha por zona: coeficiente, área e pressões de um caso de vento."""
    return [
        {
            "Zona": p.zona.nome,
            "Onde": p.zona.descricao,
            "Superfície": "Parede" if p.zona.superficie == "parede" else "Telhado",
            "C_e": p.zona.ce,
            "Área (m²)": p.zona.area_m2,
            "q·C_e (kN/m²)": p.pressao_externa_kN_m2,
            "Δp = q·(C_e − c_pi) (kN/m²)": p.pressao_liquida_kN_m2,
            "Força (kN)": p.forca_liquida_kN,
        }
        for p in caso.pressoes
    ]
