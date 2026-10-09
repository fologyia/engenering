"""Cantoneiras laminadas de abas iguais — propriedades geométricas da seção idealizada.

A seção é a união de dois retângulos ``b × t`` (sem o raio de concordância da raiz nem o
arredondamento das pontas). Comparada às tabelas dos fabricantes, a área e as inércias ficam
ligeiramente menores — o que é a favor da segurança nas verificações de tração e compressão. A série
de bitolas é a usual no mercado brasileiro (polegadas, ASTM A36).

Eixos: ``x`` e ``y`` passam pelo centro geométrico paralelos às abas (iguais, por simetria); ``w``
é o eixo principal de maior inércia (ao longo da bissetriz) e ``z`` o de menor inércia.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

POLEGADA_MM = 25.4
DENSIDADE_ACO_KG_MM3 = 7.85e-6

#: (aba em polegadas, espessura em polegadas) — série usual de cantoneiras de abas iguais.
SERIE_POLEGADAS: tuple[tuple[str, str], ...] = (
    ("1", "1/8"),
    ("1", "3/16"),
    ("1", "1/4"),
    ("1 1/4", "1/8"),
    ("1 1/4", "3/16"),
    ("1 1/4", "1/4"),
    ("1 1/2", "1/8"),
    ("1 1/2", "3/16"),
    ("1 1/2", "1/4"),
    ("1 3/4", "1/8"),
    ("1 3/4", "3/16"),
    ("1 3/4", "1/4"),
    ("2", "1/8"),
    ("2", "3/16"),
    ("2", "1/4"),
    ("2", "5/16"),
    ("2", "3/8"),
    ("2 1/2", "3/16"),
    ("2 1/2", "1/4"),
    ("2 1/2", "5/16"),
    ("2 1/2", "3/8"),
    ("3", "1/4"),
    ("3", "5/16"),
    ("3", "3/8"),
    ("3", "1/2"),
    ("4", "1/4"),
    ("4", "5/16"),
    ("4", "3/8"),
    ("4", "1/2"),
    ("5", "3/8"),
    ("5", "1/2"),
    ("6", "3/8"),
    ("6", "1/2"),
    ("6", "5/8"),
    ("6", "3/4"),
)


@dataclass(frozen=True)
class Cantoneira:
    nome: str
    b_mm: float
    t_mm: float
    area_mm2: float
    x_barra_mm: float  # do dorso (face externa da aba) ao centro geométrico
    i_x_mm4: float  # = i_y: eixo pelo centro, paralelo a uma aba
    i_w_mm4: float  # principal, maior
    i_z_mm4: float  # principal, menor
    j_mm4: float

    @property
    def r_x_mm(self) -> float:
        return math.sqrt(self.i_x_mm4 / self.area_mm2)

    @property
    def r_z_mm(self) -> float:
        return math.sqrt(self.i_z_mm4 / self.area_mm2)

    @property
    def b_sobre_t(self) -> float:
        return self.b_mm / self.t_mm

    @property
    def massa_kg_m(self) -> float:
        return self.area_mm2 * DENSIDADE_ACO_KG_MM3 * 1000.0

    @property
    def area_aba_mm2(self) -> float:
        """Área bruta de uma aba inteira (``A_c`` da aba ligada, 5.2.5)."""
        return self.b_mm * self.t_mm


def _polegadas(texto: str) -> float:
    return float(sum(Fraction(parte) for parte in texto.split()))


def propriedades(b_mm: float, t_mm: float, nome: str = "") -> Cantoneira:
    """Propriedades da cantoneira de abas iguais ``b × t`` (dois retângulos, sem raios)."""
    b, t = float(b_mm), float(t_mm)
    if not (b > 0 and 0 < t < b):
        raise ValueError("A cantoneira precisa de aba b > 0 e espessura 0 < t < b.")
    a1, x1, y1 = b * t, t / 2.0, b / 2.0  # aba vertical inteira
    a2, x2, y2 = (b - t) * t, t + (b - t) / 2.0, t / 2.0  # aba horizontal sem o canto
    area = a1 + a2
    xb = (a1 * x1 + a2 * x2) / area
    yb = (a1 * y1 + a2 * y2) / area  # = xb
    ix = t * b**3 / 12.0 + a1 * (y1 - yb) ** 2 + (b - t) * t**3 / 12.0 + a2 * (y2 - yb) ** 2
    ixy = a1 * (x1 - xb) * (y1 - yb) + a2 * (x2 - xb) * (y2 - yb)
    j = t**3 * (2.0 * b - t) / 3.0
    return Cantoneira(
        nome=nome or f"L {b:g}×{t:g}",
        b_mm=b,
        t_mm=t,
        area_mm2=area,
        x_barra_mm=xb,
        i_x_mm4=ix,
        i_w_mm4=ix + abs(ixy),
        i_z_mm4=ix - abs(ixy),
        j_mm4=j,
    )


def _criar_catalogo() -> dict[str, Cantoneira]:
    catalogo: dict[str, Cantoneira] = {}
    for aba, espessura in SERIE_POLEGADAS:
        b = _polegadas(aba) * POLEGADA_MM
        t = _polegadas(espessura) * POLEGADA_MM
        nome = f'L {aba}" × {espessura}"'
        catalogo[nome] = propriedades(b, t, nome)
    return catalogo


CATALOGO_CANTONEIRAS: dict[str, Cantoneira] = _criar_catalogo()


def obter_cantoneira(nome: str) -> Cantoneira:
    try:
        return CATALOGO_CANTONEIRAS[nome]
    except KeyError as erro:
        raise ValueError(f"Cantoneira fora do catálogo: {nome!r}.") from erro


def gabarito_usual_mm(b_mm: float) -> float:
    """Distância usual do dorso à linha de furação: ~55 % da aba, arredondada a 5 mm."""
    return max(5.0, 5.0 * round(0.55 * float(b_mm) / 5.0))
