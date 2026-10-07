"""Coeficientes aerodinâmicos de edificações paralelepipédicas — ABNT NBR 6123:2023, seção 6.

Reúne, sem Streamlit e sem geometria da obra, os números que a norma publica:

* ``C_e`` das paredes (Tabela 6) e dos telhados de duas águas (Tabela 7) e de uma água
  (Tabela 8), com o ``c_pe`` médio das zonas de altas sucções;
* o coeficiente de pressão interna ``c_pi`` (6.3.2 e 6.3.3);
* o coeficiente de arrasto ``C_a`` (Figuras 4 e 5, lidas por :mod:`core.vento_arrasto_dados`);
* o fator de vizinhança ``f_v`` (6.4.4), a força de atrito (6.1.5) e as excentricidades (6.1.4).

Sinal: positivo é sobrepressão (empurra a superfície para dentro); negativo é sucção (puxa para
fora). O ângulo de incidência ``α`` é o da norma: 0° é o vento ao longo da maior dimensão ``a``
(bate na parede de largura ``b``); 90° é o vento ao longo de ``b`` (bate na parede de comprimento
``a``). Nas Tabelas 6 e 7 a cumeeira é paralela a ``a`` e ``a ≥ b``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

from core.vento_arrasto_dados import (
    COLUNAS_L1_SOBRE_L2,
    FIGURA_4_BAIXA_TURBULENCIA,
    FIGURA_5_ALTA_TURBULENCIA,
)
from core.vento_nbr6123 import numero_ptbr

REFERENCIA_PAREDES = "NBR 6123:2023, Tabela 6"
REFERENCIA_DUAS_AGUAS = "NBR 6123:2023, Tabela 7"
REFERENCIA_UMA_AGUA = "NBR 6123:2023, Tabela 8"


def _pt(valor: float, casas: int = 2) -> str:
    """Número com vírgula decimal e, quando negativo, o sinal de menos tipográfico."""
    return numero_ptbr(valor, casas).replace("-", "−")


def _g(valor: float) -> str:
    """Número sem zeros à direita e com vírgula decimal (``0,5``; ``4``)."""
    return f"{valor:g}".replace(".", ",").replace("-", "−")


def _sinal(valor: float, casas: int = 2) -> str:
    """Com sinal explícito: ``+0,55`` e ``−0,30``."""
    return ("+" if valor > 0 else "") + _pt(valor, casas)


def _fracao(x: float, x0: float, x1: float) -> float:
    return 0.0 if x1 == x0 else (x - x0) / (x1 - x0)


def _entre(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Tabela 6 — paredes
# ---------------------------------------------------------------------------


class LinhaParede(NamedTuple):
    """Uma linha da Tabela 6: ``C_e`` por zona e o ``c_pe`` médio."""

    a1_b1: float
    a2_b2: float
    c: float
    d: float
    a: float
    b: float
    c1_d1: float
    c2_d2: float
    cpe_medio: float


#: faixas de h/b: (limite superior, rótulo)
FAIXAS_H_SOBRE_B_PAREDES: tuple[tuple[float, str], ...] = (
    (0.5, "h/b ≤ 1/2"),
    (1.5, "1/2 < h/b ≤ 3/2"),
    (6.0, "3/2 < h/b ≤ 6"),
)

#: Tabela 6: por faixa de h/b, a linha de 1 ≤ a/b ≤ 3/2 e a de 2 ≤ a/b ≤ 4.
TABELA_6: tuple[tuple[LinhaParede, LinhaParede], ...] = (
    (
        LinhaParede(-0.8, -0.5, 0.7, -0.4, 0.7, -0.4, -0.8, -0.4, -0.9),
        LinhaParede(-0.8, -0.4, 0.7, -0.3, 0.7, -0.5, -0.9, -0.5, -1.0),
    ),
    (
        LinhaParede(-0.9, -0.5, 0.7, -0.5, 0.7, -0.5, -0.9, -0.5, -1.1),
        LinhaParede(-0.9, -0.4, 0.7, -0.3, 0.7, -0.6, -0.9, -0.5, -1.1),
    ),
    (
        LinhaParede(-1.0, -0.6, 0.8, -0.6, 0.8, -0.6, -1.0, -0.6, -1.2),
        LinhaParede(-1.0, -0.5, 0.8, -0.3, 0.8, -0.6, -1.0, -0.6, -1.2),
    ),
)

#: Nota 3 da Tabela 6: A3 e B3 (vento a 0°) valem A2/B2 se a/b = 1 e −0,2 se a/b ≥ 2.
CE_A3_B3_A_SOBRE_B_2 = -0.2


@dataclass(frozen=True, slots=True)
class CoefParedes:
    """``C_e`` das paredes da edificação a × b × h (Tabela 6)."""

    faixa_h_b: str
    h_sobre_b: float
    a_sobre_b: float
    # vento a 0°: paredes paralelas ao vento, de barlavento (C) e de sotavento (D)
    a1_b1_0: float
    a2_b2_0: float
    a3_b3_0: float
    c_0: float
    d_0: float
    # vento a 90°
    a_90: float
    b_90: float
    c1_d1_90: float
    c2_d2_90: float
    cpe_medio: float
    avisos: tuple[str, ...] = ()


def _faixa_h_b(h_sobre_b: float, rotulos: Sequence[tuple[float, str]]) -> tuple[int, bool]:
    for indice, (limite, _rotulo) in enumerate(rotulos):
        if h_sobre_b <= limite:
            return indice, False
    return len(rotulos) - 1, True


def coeficientes_paredes(a_m: float, b_m: float, h_m: float) -> CoefParedes:
    """``C_e`` das paredes pela Tabela 6, com a interpolação da Nota 2 (3/2 < a/b < 2)."""
    a, b, h = float(a_m), float(b_m), float(h_m)
    if not (a > 0 and b > 0 and h > 0):
        raise ValueError("As dimensões a, b e h devem ser positivas.")
    if a < b:
        raise ValueError("Na Tabela 6, a é a maior dimensão em planta (a ≥ b).")
    h_sobre_b, a_sobre_b = h / b, a / b
    avisos: list[str] = []
    faixa, passou = _faixa_h_b(h_sobre_b, FAIXAS_H_SOBRE_B_PAREDES)
    if passou:
        avisos.append(
            f"h/b = {_pt(h_sobre_b)} > 6: fora da Tabela 6; usados os valores da última faixa."
        )
    curta, longa = TABELA_6[faixa]
    if a_sobre_b <= 1.5:
        linha = curta
    elif a_sobre_b >= 2.0:
        linha = longa
        if a_sobre_b > 4.0:
            avisos.append(f"a/b = {_pt(a_sobre_b)} > 4: fora da Tabela 6; usados os de a/b = 4.")
    else:
        t = _fracao(a_sobre_b, 1.5, 2.0)
        linha = LinhaParede(*(_entre(x, y, t) for x, y in zip(curta, longa, strict=True)))
    if a_sobre_b <= 1.0 + 1e-9:
        a3 = linha.a2_b2
    elif a_sobre_b >= 2.0:
        a3 = CE_A3_B3_A_SOBRE_B_2
    else:
        a3 = _entre(linha.a2_b2, CE_A3_B3_A_SOBRE_B_2, _fracao(a_sobre_b, 1.0, 2.0))
    return CoefParedes(
        faixa_h_b=FAIXAS_H_SOBRE_B_PAREDES[faixa][1],
        h_sobre_b=h_sobre_b,
        a_sobre_b=a_sobre_b,
        a1_b1_0=linha.a1_b1,
        a2_b2_0=linha.a2_b2,
        a3_b3_0=a3,
        c_0=linha.c,
        d_0=linha.d,
        a_90=linha.a,
        b_90=linha.b,
        c1_d1_90=linha.c1_d1,
        c2_d2_90=linha.c2_d2,
        cpe_medio=linha.cpe_medio,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# Tabela 7 — telhados de duas águas simétricos
# ---------------------------------------------------------------------------


class LinhaTelhado(NamedTuple):
    """Tabela 7 numa inclinação: ``C_e`` por zona e ``c_pe`` médio (``None`` = sem valor)."""

    theta: float
    efi: float  # vento a 90°, água de barlavento
    ghj: float  # vento a 90°, água de sotavento
    eg: float  # vento a 0°, do início até x
    fh: float  # vento a 0°, de x até a/2
    empena: float | None  # c_pe médio — faixa de largura y nas empenas
    canto: float | None  # c_pe médio — cantos do beiral
    beiral: float | None  # c_pe médio — beiral entre os cantos
    cumeeira: float | None  # c_pe médio — faixas ao longo da cumeeira


_N = None
TABELA_7: tuple[tuple[LinhaTelhado, ...], ...] = (
    (  # h/b ≤ 1/2
        LinhaTelhado(0, -0.8, -0.4, -0.8, -0.4, -2.0, -2.0, -2.0, _N),
        LinhaTelhado(5, -0.9, -0.4, -0.8, -0.4, -1.4, -1.2, -1.2, -1.0),
        LinhaTelhado(10, -1.2, -0.4, -0.8, -0.6, -1.4, -1.4, _N, -1.2),
        LinhaTelhado(15, -1.0, -0.4, -0.8, -0.6, -1.4, -1.2, _N, -1.2),
        LinhaTelhado(20, -0.4, -0.4, -0.7, -0.6, -1.0, _N, _N, -1.2),
        LinhaTelhado(30, 0.0, -0.4, -0.7, -0.6, -0.8, _N, _N, -1.1),
        LinhaTelhado(45, 0.3, -0.5, -0.7, -0.6, _N, _N, _N, -1.1),
        LinhaTelhado(60, 0.7, -0.6, -0.7, -0.6, _N, _N, _N, -1.1),
    ),
    (  # 1/2 < h/b ≤ 3/2
        LinhaTelhado(0, -0.8, -0.6, -1.0, -0.6, -2.0, -2.0, -2.0, _N),
        LinhaTelhado(5, -0.9, -0.6, -0.9, -0.6, -2.0, -2.0, -1.5, -1.0),
        LinhaTelhado(10, -1.1, -0.6, -0.8, -0.6, -2.0, -2.0, -1.5, -1.2),
        LinhaTelhado(15, -1.0, -0.6, -0.8, -0.6, -1.8, -1.5, -1.5, -1.2),
        LinhaTelhado(20, -0.7, -0.5, -0.8, -0.6, -1.5, -1.5, -1.5, -1.0),
        LinhaTelhado(30, -0.2, -0.5, -0.8, -0.8, -1.0, _N, _N, -1.0),
        LinhaTelhado(45, 0.2, -0.5, -0.8, -0.8, _N, _N, _N, _N),
        LinhaTelhado(60, 0.6, -0.5, -0.8, -0.8, _N, _N, _N, _N),
    ),
    (  # 3/2 < h/b ≤ 6
        LinhaTelhado(0, -0.8, -0.6, -0.9, -0.7, -2.0, -2.0, -2.0, _N),
        LinhaTelhado(5, -0.8, -0.6, -0.8, -0.8, -2.0, -2.0, -1.5, -1.0),
        LinhaTelhado(10, -0.8, -0.6, -0.8, -0.8, -2.0, -2.0, -1.5, -1.2),
        LinhaTelhado(15, -0.8, -0.6, -0.8, -0.8, -1.8, -1.8, -1.5, -1.2),
        LinhaTelhado(20, -0.8, -0.6, -0.8, -0.8, -1.5, -1.5, -1.5, -1.2),
        LinhaTelhado(30, -1.0, -0.5, -0.8, -0.7, -1.5, _N, _N, _N),
        LinhaTelhado(40, -0.2, -0.5, -0.8, -0.7, -1.0, _N, _N, _N),
        LinhaTelhado(50, 0.2, -0.5, -0.8, -0.7, _N, _N, _N, _N),
        LinhaTelhado(60, 0.5, -0.5, -0.8, -0.7, _N, _N, _N, _N),
    ),
)

#: Nota 3 das Tabelas 7 e 8: nas partes I e J (vento a 0°) vale o de F e H se a/b = 1 e −0,2 se
#: a/b ≥ 2, com interpolação linear entre os dois.
CE_IJ_A_SOBRE_B_2 = -0.2

#: Nas zonas em torno de partes salientes ao telhado (chaminés, reservatórios, torres) e, na
#: Tabela 7, em volta delas até a metade da diagonal da saliência: C_e = −1,2.
CE_AO_REDOR_DE_SALIENCIAS = -1.2
#: Cobertura de lanternins (Nota 2 da Tabela 7).
CPE_MEDIO_LANTERNIM = -2.0


@dataclass(frozen=True, slots=True)
class CoefTelhadoDuasAguas:
    faixa_h_b: str
    theta_graus: float
    efi_90: float
    ghj_90: float
    eg_0: float
    fh_0: float
    ij_0: float
    empena: float | None
    canto: float | None
    beiral: float | None
    cumeeira: float | None
    avisos: tuple[str, ...] = ()


def _interpolar_campo(a: float | None, b: float | None, t: float) -> float | None:
    if a is None or b is None:
        return None
    return _entre(a, b, t)


def _linha_interpolada(linhas: Sequence[LinhaTelhado], theta: float) -> LinhaTelhado:
    if theta <= linhas[0].theta:
        return linhas[0]._replace(theta=theta)
    if theta >= linhas[-1].theta:
        return linhas[-1]._replace(theta=theta)
    for baixa, alta in zip(linhas, linhas[1:], strict=False):
        if baixa.theta <= theta <= alta.theta:
            t = _fracao(theta, baixa.theta, alta.theta)
            return LinhaTelhado(
                theta,
                *(_interpolar_campo(x, y, t) for x, y in zip(baixa[1:], alta[1:], strict=True)),  # type: ignore[arg-type]
            )
    return linhas[-1]  # pragma: no cover


def coeficientes_telhado_duas_aguas(
    a_m: float, b_m: float, h_m: float, theta_graus: float
) -> CoefTelhadoDuasAguas:
    """``C_e`` do telhado de duas águas simétrico (Tabela 7); θ = 0 vale para telhado plano."""
    a, b, h, theta = float(a_m), float(b_m), float(h_m), float(theta_graus)
    if not (a > 0 and b > 0 and h > 0):
        raise ValueError("As dimensões a, b e h devem ser positivas.")
    if a < b:
        raise ValueError("Na Tabela 7, a é a maior dimensão em planta (a ≥ b).")
    if not 0.0 <= theta <= 90.0:
        raise ValueError("A inclinação do telhado deve estar entre 0° e 90°.")
    avisos: list[str] = []
    h_sobre_b = h / b
    faixa, passou = _faixa_h_b(h_sobre_b, FAIXAS_H_SOBRE_B_PAREDES)
    if passou:
        avisos.append(f"h/b = {_pt(h_sobre_b)} > 6: fora da Tabela 7; usados os da última faixa.")
    linhas = TABELA_7[faixa]
    if theta > linhas[-1].theta:
        avisos.append(f"θ = {_pt(theta, 0)}° > 60°: fora da Tabela 7; usados os valores de 60°.")
    linha = _linha_interpolada(linhas, theta)
    a_sobre_b = a / b
    if a_sobre_b <= 1.0 + 1e-9:
        ij = linha.fh
    elif a_sobre_b >= 2.0:
        ij = CE_IJ_A_SOBRE_B_2
    else:
        ij = _entre(linha.fh, CE_IJ_A_SOBRE_B_2, _fracao(a_sobre_b, 1.0, 2.0))
    return CoefTelhadoDuasAguas(
        faixa_h_b=FAIXAS_H_SOBRE_B_PAREDES[faixa][1],
        theta_graus=theta,
        efi_90=linha.efi,
        ghj_90=linha.ghj,
        eg_0=linha.eg,
        fh_0=linha.fh,
        ij_0=ij,
        empena=linha.empena,
        canto=linha.canto,
        beiral=linha.beiral,
        cumeeira=linha.cumeeira,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# Tabela 8 — telhados de uma água (h/b < 2)
# ---------------------------------------------------------------------------


class LinhaUmaAgua(NamedTuple):
    """Tabela 8 numa inclinação, nos ângulos de incidência 90°, 45°, 0°, −45° e −90°."""

    theta: float
    hi_90: float
    lj_90: float
    h_45: float
    l_45: float
    hl_0_ate_b2: float  # H e L, até a profundidade b/2
    hl_0_de_b2_a_a2: float  # H e L, de b/2 até a/2
    h_m45: float
    l_m45: float
    hi_m90: float
    lj_m90: float
    # c_pe médio (zonas H1, H2, L1, L2, He, Le da figura da tabela)
    h1: float
    h2: float
    l1: float
    l2: float
    he: float
    le: float


TABELA_8: tuple[LinhaUmaAgua, ...] = (
    LinhaUmaAgua(5, -1.0, -0.5, -1.0, -0.9, -1.0, -0.5, -0.9, -1.0, -0.5, -1.0, -2.0, -1.5, -2.0, -1.5, -2.0, -2.0),
    LinhaUmaAgua(10, -1.0, -0.5, -1.0, -0.8, -1.0, -0.5, -0.8, -1.0, -0.4, -1.0, -2.0, -1.5, -2.0, -1.5, -2.0, -2.0),
    LinhaUmaAgua(15, -0.9, -0.5, -1.0, -0.7, -1.0, -0.5, -0.6, -1.0, -0.3, -1.0, -1.8, -0.9, -1.8, -1.4, -2.0, -2.0),
    LinhaUmaAgua(20, -0.8, -0.5, -1.0, -0.6, -0.9, -0.5, -0.5, -1.0, -0.2, -1.0, -1.8, -0.8, -1.8, -1.4, -2.0, -2.0),
    LinhaUmaAgua(25, -0.7, -0.5, -1.0, -0.6, -0.8, -0.5, -0.3, -0.9, -0.1, -0.9, -1.8, -0.7, -0.9, -0.9, -2.0, -2.0),
    LinhaUmaAgua(30, -0.5, -0.5, -1.0, -0.6, -0.8, -0.5, -0.1, -0.6, 0.0, -0.6, -1.8, -0.5, -0.5, -0.5, -2.0, -2.0),
)  # fmt: skip

#: Limite de h/b da Tabela 8 ("com h/b < 2").
H_SOBRE_B_MAXIMO_UMA_AGUA = 2.0


@dataclass(frozen=True, slots=True)
class CoefTelhadoUmaAgua:
    """``C_e`` do telhado de uma água. ``α`` positivo sopra do lado alto (H, I) para o baixo (L, J)."""

    theta_graus: float
    hi_90: float
    lj_90: float
    h_45: float
    l_45: float
    hl_0_ate_b2: float
    hl_0_de_b2_a_a2: float
    ij_0: float
    h_m45: float
    l_m45: float
    hi_m90: float
    lj_m90: float
    h1: float
    h2: float
    l1: float
    l2: float
    he: float
    le: float
    avisos: tuple[str, ...] = ()


def coeficientes_telhado_uma_agua(
    a_m: float, b_m: float, h_m: float, theta_graus: float
) -> CoefTelhadoUmaAgua:
    """``C_e`` do telhado de uma água (Tabela 8), com interpolação entre as inclinações."""
    a, b, h, theta = float(a_m), float(b_m), float(h_m), float(theta_graus)
    if not (a > 0 and b > 0 and h > 0):
        raise ValueError("As dimensões a, b e h devem ser positivas.")
    if a < b:
        raise ValueError("Na Tabela 8, a é a maior dimensão em planta (a ≥ b).")
    if not 0.0 <= theta <= 90.0:
        raise ValueError("A inclinação do telhado deve estar entre 0° e 90°.")
    avisos: list[str] = []
    if h / b >= H_SOBRE_B_MAXIMO_UMA_AGUA:
        avisos.append(
            f"h/b = {_pt(h / b)} ≥ 2: a Tabela 8 vale para h/b < 2; use com cautela ou estudo "
            "específico."
        )
    primeira, ultima = TABELA_8[0], TABELA_8[-1]
    if theta < primeira.theta:
        avisos.append(
            f"θ = {_pt(theta, 1)}° < 5°: usados os valores de 5° (a Nota 2 manda tomar θ = 0 da "
            "Tabela 7, pela relação h/b)."
        )
    if theta > ultima.theta:
        avisos.append(f"θ = {_pt(theta, 0)}° > 30°: fora da Tabela 8; usados os valores de 30°.")
    if theta <= primeira.theta:
        linha = primeira
    elif theta >= ultima.theta:
        linha = ultima
    else:
        linha = primeira
        for baixa, alta in zip(TABELA_8, TABELA_8[1:], strict=False):
            if baixa.theta <= theta <= alta.theta:
                t = _fracao(theta, baixa.theta, alta.theta)
                linha = LinhaUmaAgua(
                    theta, *(_entre(x, y, t) for x, y in zip(baixa[1:], alta[1:], strict=True))
                )
                break
    a_sobre_b = a / b
    # Nota 1: nas partes I e J, a/b = 1 repete H e L (num quadrado só existe a faixa até b/2) e
    # a/b ≥ 2 vale −0,2; entre os dois, interpolação linear.
    if a_sobre_b <= 1.0 + 1e-9:
        ij = linha.hl_0_ate_b2
    elif a_sobre_b >= 2.0:
        ij = CE_IJ_A_SOBRE_B_2
    else:
        ij = _entre(linha.hl_0_ate_b2, CE_IJ_A_SOBRE_B_2, _fracao(a_sobre_b, 1.0, 2.0))
    return CoefTelhadoUmaAgua(
        theta_graus=theta,
        hi_90=linha.hi_90,
        lj_90=linha.lj_90,
        h_45=linha.h_45,
        l_45=linha.l_45,
        hl_0_ate_b2=linha.hl_0_ate_b2,
        hl_0_de_b2_a_a2=linha.hl_0_de_b2_a_a2,
        ij_0=ij,
        h_m45=linha.h_m45,
        l_m45=linha.l_m45,
        hi_m90=linha.hi_m90,
        lj_m90=linha.lj_m90,
        h1=linha.h1,
        h2=linha.h2,
        l1=linha.l1,
        l2=linha.l2,
        he=linha.he,
        le=linha.le,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# Pressão interna — 6.3
# ---------------------------------------------------------------------------

#: abertura dominante em face de barlavento: (razão entre a área da abertura e a das demais
#: aberturas das faces sob sucção externa, c_pi) — 6.3.2.1-c
CPI_ABERTURA_DOMINANTE_BARLAVENTO: tuple[tuple[float, float], ...] = (
    (1.0, 0.1),
    (1.5, 0.3),
    (2.0, 0.5),
    (3.0, 0.6),
    (6.0, 0.8),
)
#: abertura dominante em zona de alta sucção de face paralela ao vento — 6.3.2.1-c
CPI_ABERTURA_DOMINANTE_ALTA_SUCCAO: tuple[tuple[float, float], ...] = (
    (0.25, -0.4),
    (0.50, -0.5),
    (0.75, -0.6),
    (1.00, -0.7),
    (1.50, -0.8),
    (3.00, -0.9),
)


def _tabela_linear(pontos: Sequence[tuple[float, float]], x: float) -> float:
    """Interpolação linear com os extremos mantidos (sem extrapolar)."""
    if x <= pontos[0][0]:
        return pontos[0][1]
    if x >= pontos[-1][0]:
        return pontos[-1][1]
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:], strict=False):
        if x0 <= x <= x1:
            return _entre(y0, y1, _fracao(x, x0, x1))
    return pontos[-1][1]  # pragma: no cover


@dataclass(frozen=True, slots=True)
class SugestaoCpi:
    """Um valor de ``c_pi`` que a norma manda considerar, com o motivo."""

    valor: float
    rotulo: str
    referencia: str


CENARIOS_PERMEABILIDADE: dict[str, str] = {
    "quatro_faces": (
        "Quatro faces igualmente permeáveis (frestas de telhas e esquadrias, portas e janelas "
        "fechadas, sem aberturas grandes)"
    ),
    "duas_faces_longas": (
        "Duas faces opostas igualmente permeáveis — as paredes longas (a); as outras duas "
        "impermeáveis"
    ),
    "duas_faces_curtas": (
        "Duas faces opostas igualmente permeáveis — as paredes curtas (b); as outras duas "
        "impermeáveis"
    ),
    "estanque": "Edificação estanque, com janelas fixas que não se rompem por acidente",
    "informado": "Valores de c_pi informados pelo projetista",
}


def sugerir_cpi(cenario: str, alpha_graus: int) -> list[SugestaoCpi]:
    """Valores de ``c_pi`` da norma (6.3.2) para o cenário de permeabilidade e a direção do vento.

    ``alpha_graus`` é 0 (vento ao longo de ``a``, contra as paredes curtas) ou 90 (ao longo de
    ``b``, contra as paredes longas). Quando a norma pede o "mais nocivo" de dois valores, devolve
    os dois — cada um vira um caso de carga.
    """
    if alpha_graus not in (0, 90):
        raise ValueError("O ângulo de incidência é 0° ou 90°.")
    if cenario == "quatro_faces":
        return [
            SugestaoCpi(-0.3, "c_pi = −0,3 (considerar o mais nocivo)", "NBR 6123:2023, 6.3.2.1-b"),
            SugestaoCpi(0.0, "c_pi = 0 (considerar o mais nocivo)", "NBR 6123:2023, 6.3.2.1-b"),
        ]
    if cenario in ("duas_faces_longas", "duas_faces_curtas"):
        permeaveis_sao_as_longas = cenario == "duas_faces_longas"
        # α = 90° sopra contra as paredes longas; α = 0° contra as curtas.
        vento_contra_face_permeavel = (alpha_graus == 90) == permeaveis_sao_as_longas
        if vento_contra_face_permeavel:
            return [
                SugestaoCpi(
                    0.2, "c_pi = +0,2 (vento contra face permeável)", "NBR 6123:2023, 6.3.2.1-a"
                )
            ]
        return [
            SugestaoCpi(
                -0.3, "c_pi = −0,3 (vento contra face impermeável)", "NBR 6123:2023, 6.3.2.1-a"
            )
        ]
    if cenario == "estanque":
        return [
            SugestaoCpi(-0.2, "c_pi = −0,2 (edificação estanque)", "NBR 6123:2023, 6.3.2.2"),
            SugestaoCpi(0.0, "c_pi = 0 (edificação estanque)", "NBR 6123:2023, 6.3.2.2"),
        ]
    raise ValueError(f"Cenário de permeabilidade desconhecido: {cenario!r}.")


def interpretar_cpis(texto: str) -> tuple[float, ...]:
    """Valores de ``c_pi`` digitados: ``"-0,3; 0,2"`` ou ``"-0.3, 0.2"`` → ``(-0.3, 0.2)``.

    Separa por ponto e vírgula, barra ou quebra de linha. Sem esses, a vírgula é o decimal
    (``-0,3``) e só separa quando vem seguida de espaço (``-0,3, 0,2``) ou quando os decimais usam
    ponto (``-0.3, 0.2``). Cada valor fica entre −2 e +2, como nas tabelas.
    """
    bruto = str(texto).replace("−", "-").strip()
    if ";" in bruto or "\n" in bruto or "/" in bruto:
        pedacos = re.split(r"[;\n/]", bruto)
    elif "." in bruto:
        pedacos = re.split(r"[,\s]+", bruto)
    else:
        pedacos = re.split(r",\s+|\s+", bruto)
    valores: list[float] = []
    for pedaco in pedacos:
        limpo = pedaco.strip().replace(",", ".")
        if not limpo:
            continue
        try:
            valor = float(limpo)
        except ValueError as erro:
            raise ValueError(f"c_pi inválido: {pedaco.strip()!r}.") from erro
        if not -2.0 <= valor <= 2.0:
            raise ValueError(f"c_pi = {pedaco.strip()} fora do campo usual (−2 a +2).")
        if all(abs(valor - v) > 1e-9 for v in valores):
            valores.append(valor)
    if not valores:
        raise ValueError("Informe ao menos um valor de c_pi.")
    return tuple(valores)


def cpi_abertura_dominante(
    posicao: str, *, razao_aberturas: float | None = None, ce_da_zona: float | None = None
) -> SugestaoCpi:
    """``c_pi`` com uma abertura dominante (6.3.2.1-c).

    * ``barlavento``: depende da razão entre a área da abertura e a das demais aberturas das faces
      sob sucção externa (1 → +0,1 … 6 ou mais → +0,8; interpolação linear entre os pontos).
    * ``sotavento``: o ``C_e`` da própria face (``ce_da_zona``).
    * ``paralela``: ``C_e`` do local da abertura, se fora de zona de alta sucção (``ce_da_zona``);
      em zona de alta sucção, pela razão entre a abertura e as outras (0,25 → −0,4 … 3 → −0,9).
    * ``paralela_alta_succao`` é o caso da zona hachurada; informe ``razao_aberturas``.
    """
    referencia = "NBR 6123:2023, 6.3.2.1-c"
    if posicao == "barlavento":
        if razao_aberturas is None or razao_aberturas <= 0:
            raise ValueError("Informe a razão entre a abertura dominante e as demais (> 0).")
        valor = _tabela_linear(CPI_ABERTURA_DOMINANTE_BARLAVENTO, float(razao_aberturas))
        return SugestaoCpi(
            valor,
            f"c_pi = {_sinal(valor)} (abertura dominante a barlavento, razão {_g(razao_aberturas)})",
            referencia,
        )
    if posicao in ("sotavento", "paralela"):
        if ce_da_zona is None:
            raise ValueError("Informe o C_e da face ou da zona em que está a abertura.")
        local = "a sotavento" if posicao == "sotavento" else "em face paralela ao vento"
        return SugestaoCpi(
            float(ce_da_zona),
            f"c_pi = {_sinal(ce_da_zona)} (= C_e da zona; abertura dominante {local})",
            referencia,
        )
    if posicao == "paralela_alta_succao":
        if razao_aberturas is None or razao_aberturas <= 0:
            raise ValueError("Informe a razão entre a abertura dominante e as demais (> 0).")
        valor = _tabela_linear(CPI_ABERTURA_DOMINANTE_ALTA_SUCCAO, float(razao_aberturas))
        return SugestaoCpi(
            valor,
            f"c_pi = {_sinal(valor)} (abertura dominante em zona de alta sucção, razão "
            f"{_g(razao_aberturas)})",
            referencia,
        )
    raise ValueError(f"Posição da abertura dominante desconhecida: {posicao!r}.")


# ---------------------------------------------------------------------------
# Vento de alta turbulência — 6.1.3
# ---------------------------------------------------------------------------

#: extensão mínima a barlavento (m) e altura máxima da edificação (m) — 6.1.3.1-b
EXTENSAO_VIZINHANCA_ALTA_TURBULENCIA: tuple[tuple[float, float], ...] = (
    (40.0, 500.0),
    (55.0, 1000.0),
    (70.0, 2000.0),
    (80.0, 3000.0),
)


def verificar_alta_turbulencia(
    h_m: float,
    largura_m: float,
    profundidade_m: float,
    *,
    altura_media_vizinhanca_m: float,
    extensao_vizinhanca_m: float,
) -> tuple[bool, list[str]]:
    """Diz se a edificação pode ser tratada em vento de alta turbulência (6.1.3.1) e por quê não."""
    h = float(h_m)
    motivos: list[str] = []
    if h > 80.0:
        motivos.append("altura acima de 80 m: o critério de alta turbulência não se aplica")
    if not float(profundidade_m) / float(largura_m) > 1.0 / 3.0:
        motivos.append("a relação profundidade/largura não é maior do que 1/3")
    if h > 2.0 * float(altura_media_vizinhanca_m):
        motivos.append(
            "a altura da edificação excede duas vezes a altura média das vizinhas a barlavento"
        )
    for altura_limite, extensao in EXTENSAO_VIZINHANCA_ALTA_TURBULENCIA:
        if h <= altura_limite:
            if float(extensao_vizinhanca_m) < extensao:
                motivos.append(
                    f"as vizinhas a barlavento se estendem por {_pt(extensao_vizinhanca_m, 0)} m; "
                    f"para h ≤ {_pt(altura_limite, 0)} m a norma pede pelo menos {_pt(extensao, 0)} m"
                )
            break
    return (not motivos), motivos


#: Redução do C_e da parede de sotavento em vento de alta turbulência (6.1.3.2-a).
FATOR_SOTAVENTO_ALTA_TURBULENCIA = 2.0 / 3.0


# ---------------------------------------------------------------------------
# Coeficiente de arrasto — 6.1.2 (Figuras 4 e 5)
# ---------------------------------------------------------------------------

LINHAS_FIGURA_4 = tuple(sorted(FIGURA_4_BAIXA_TURBULENCIA))
LINHAS_FIGURA_5 = tuple(sorted(FIGURA_5_ALTA_TURBULENCIA))
COLUNAS_DECRESCENTES = COLUNAS_L1_SOBRE_L2  # 4,0 … 0,2


@dataclass(frozen=True, slots=True)
class ArrastoCa:
    valor: float
    h_sobre_l1: float
    l1_sobre_l2: float
    alta_turbulencia: bool
    avisos: tuple[str, ...] = ()

    @property
    def figura(self) -> str:
        return (
            "Figura 5 (alta turbulência)"
            if self.alta_turbulencia
            else "Figura 4 (baixa turbulência)"
        )


def coeficiente_arrasto_paralelepipedo(
    h_m: float, l1_m: float, l2_m: float, *, alta_turbulencia: bool = False
) -> ArrastoCa:
    """``C_a`` das Figuras 4 (baixa turbulência) e 5 (alta), em função de h/ℓ₁ e ℓ₁/ℓ₂.

    ``ℓ₁`` é a dimensão horizontal perpendicular ao vento e ``ℓ₂``, a paralela. Os valores foram
    lidos do próprio gráfico (``scripts/digitalizar_arrasto_nbr6123.py``), com incerteza de leitura
    de ±0,03, e interpolados bilinearmente no logaritmo das duas relações. Fora do gráfico
    (h/ℓ₁ < 0,5; h/ℓ₁ acima de 40 na Figura 4 ou de 6 na Figura 5; ℓ₁/ℓ₂ fora de 0,2 a 4) vale o
    valor do contorno, com aviso.
    """
    h, l1, l2 = float(h_m), float(l1_m), float(l2_m)
    if not (h > 0 and l1 > 0 and l2 > 0):
        raise ValueError("h, ℓ₁ e ℓ₂ devem ser positivos.")
    tabela = FIGURA_5_ALTA_TURBULENCIA if alta_turbulencia else FIGURA_4_BAIXA_TURBULENCIA
    linhas = LINHAS_FIGURA_5 if alta_turbulencia else LINHAS_FIGURA_4
    razao_h, razao_l = h / l1, l1 / l2
    avisos: list[str] = []
    h_usado = min(max(razao_h, linhas[0]), linhas[-1])
    if razao_h < linhas[0]:
        avisos.append(
            f"h/ℓ₁ = {_pt(razao_h)} < {_g(linhas[0])}: abaixo do gráfico; usado o valor de "
            f"h/ℓ₁ = {_g(linhas[0])}."
        )
    if razao_h > linhas[-1]:
        avisos.append(
            f"h/ℓ₁ = {_pt(razao_h, 1)} > {_g(linhas[-1])}: acima do gráfico; usado o valor de "
            f"h/ℓ₁ = {_g(linhas[-1])}."
        )
    colunas = tuple(reversed(COLUNAS_DECRESCENTES))  # crescente
    l_usado = min(max(razao_l, colunas[0]), colunas[-1])
    if razao_l < colunas[0] or razao_l > colunas[-1]:
        avisos.append(
            f"ℓ₁/ℓ₂ = {_pt(razao_l)} fora de 0,2 a 4: usado o valor do contorno do gráfico."
        )

    def valor_na_linha(linha: float) -> float:
        valores = tabela[linha]  # na ordem de COLUNAS_DECRESCENTES
        pares = sorted(zip(COLUNAS_DECRESCENTES, valores, strict=True))
        for (x0, y0), (x1, y1) in zip(pares, pares[1:], strict=False):
            if x0 <= l_usado <= x1:
                t = _fracao(math.log(l_usado), math.log(x0), math.log(x1))
                return _entre(y0, y1, t)
        return pares[-1][1]

    for baixa, alta in zip(linhas, linhas[1:], strict=False):
        if baixa <= h_usado <= alta:
            t = _fracao(math.log(h_usado), math.log(baixa), math.log(alta))
            valor = _entre(valor_na_linha(baixa), valor_na_linha(alta), t)
            break
    else:  # pragma: no cover - h_usado está dentro das linhas
        valor = valor_na_linha(linhas[-1])
    return ArrastoCa(valor, razao_h, razao_l, alta_turbulencia, tuple(avisos))


# ---------------------------------------------------------------------------
# Fator de vizinhança — 6.4.4
# ---------------------------------------------------------------------------


def fator_de_vizinhanca(
    afastamento_m: float, a_m: float, b_m: float, *, na_cobertura: bool = False
) -> float:
    """``f_v`` de duas edificações altas vizinhas (6.4.4).

    ``s`` é o afastamento entre os planos das faces confrontantes e ``d*`` o menor entre o lado
    menor ``b`` e a semidiagonal ``½·√(a² + b²)``. Para ``C_a``, ``C_e`` e ``c_pe`` médio das
    paredes confrontantes: 1,3 se ``s/d* ≤ 1,0`` e 1,0 se ``s/d* ≥ 3,0``; na cobertura, 1,3 se
    ``s/d* ≤ 0,5``. Linear entre os extremos. Vale só até a altura do topo da vizinha.
    """
    s, a, b = float(afastamento_m), float(a_m), float(b_m)
    if s < 0 or not (a > 0 and b > 0):
        raise ValueError("Afastamento ≥ 0 e dimensões em planta positivas.")
    d_estrela = min(b, 0.5 * math.hypot(a, b))
    razao = s / d_estrela
    inicio = 0.5 if na_cobertura else 1.0
    if razao <= inicio:
        return 1.3
    if razao >= 3.0:
        return 1.0
    return _entre(1.3, 1.0, _fracao(razao, inicio, 3.0))


# ---------------------------------------------------------------------------
# Força de atrito e excentricidade — 6.1.4 e 6.1.5
# ---------------------------------------------------------------------------

#: Ct por tipo de superfície (6.1.5).
COEFICIENTES_ATRITO: dict[str, float] = {
    "Superfície sem nervuras transversais ao vento": 0.01,
    "Nervuras arredondadas (ondulações) transversais ao vento": 0.02,
    "Nervuras retangulares transversais ao vento": 0.04,
}


@dataclass(frozen=True, slots=True)
class ForcaAtrito:
    """Força de atrito sobre o telhado e sobre as paredes (6.1.5), em kN."""

    aplica: bool
    telhado_kN: float
    paredes_kN: float
    ct: float

    @property
    def total_kN(self) -> float:
        return self.telhado_kN + self.paredes_kN


def forca_de_atrito(q_N_m2: float, ct: float, h_m: float, l1_m: float, l2_m: float) -> ForcaAtrito:
    """``F_t = C_t·q·ℓ₁·(ℓ₂ − 4m) + C_t·q·2h·(ℓ₂ − 4m)`` com ``m = min(h, ℓ₁)`` (6.1.5).

    Só vale quando ``ℓ₂ > 4·m`` (ℓ₂/h ou ℓ₂/ℓ₁ maior do que 4); caso contrário a força é nula. O
    primeiro termo é o do telhado; o segundo, o das duas paredes paralelas ao vento.
    """
    h, l1, l2 = float(h_m), float(l1_m), float(l2_m)
    menor = min(h, l1)
    comprimento_util = l2 - 4.0 * menor
    if comprimento_util <= 0.0:
        return ForcaAtrito(False, 0.0, 0.0, float(ct))
    q = float(q_N_m2) / 1e3  # kN/m²
    return ForcaAtrito(
        True,
        ct * q * l1 * comprimento_util,
        ct * q * 2.0 * h * comprimento_util,
        float(ct),
    )


def excentricidades(a_m: float, b_m: float, *, com_vizinhanca: bool) -> tuple[float, float]:
    """``(e_a, e_b)`` da força de arrasto em relação ao eixo vertical (6.1.4).

    ``0,075·a`` e ``0,075·b`` sem efeito de vizinhança; ``0,15·a`` e ``0,15·b`` com ele. ``e_a`` vale
    para o vento ao longo de ``b`` (α = 90°) e ``e_b``, para o vento ao longo de ``a`` (α = 0°).
    """
    fator = 0.15 if com_vizinhanca else 0.075
    return fator * float(a_m), fator * float(b_m)
