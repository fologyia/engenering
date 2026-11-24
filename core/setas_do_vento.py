"""O desenho das setas de cada vento: a força do plano e a que o estudo aplicou, sobre a planta.

Um quadro por caso de vento, na vista Superior do SolidWorks (X para a direita, Z para baixo — o
+Y da planta do programa para cima): as barras do esqueleto em cinza e, saindo do centro, a seta do
plano (azul, cheia) e a do estudo (laranja, tracejada) — a reação com o sinal trocado. O tamanho
das setas é proporcional à força, na mesma escala em todos os quadros. Sentido trocado, valor
menor ou direção de outro caso ficam visíveis num relance.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from html import escape

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_por_barras as vpb

LADO = 210  # px de cada quadro
MARGEM = 26
SETA_MAXIMA = 78  # px da maior força
COR_PLANO = "#2f6fb3"
COR_ESTUDO = "#d4760a"
COR_BARRA = "#9aa3ad"
COR_TEXTO = "#2b2f33"


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _seta(x0: float, y0: float, dx: float, dy: float, cor: str, tracejada: bool) -> str:
    comprimento = math.hypot(dx, dy)
    if comprimento < 1.0:
        return ""
    x1, y1 = x0 + dx, y0 + dy
    ux, uy = dx / comprimento, dy / comprimento
    ponta = 9.0
    largura = 4.5
    bx, by = x1 - ux * ponta, y1 - uy * ponta
    p1 = (bx - uy * largura, by + ux * largura)
    p2 = (bx + uy * largura, by - ux * largura)
    traco = ' stroke-dasharray="6 4"' if tracejada else ""
    return (
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{cor}" '
        f'stroke-width="3"{traco}/>'
        f'<polygon points="{x1:.1f},{y1:.1f} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" '
        f'fill="{cor}"/>'
    )


def svg(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    g: ld.GeometriaDoModelo,
    ventos: Sequence[em.VentoComparado] | None = None,
) -> str | None:
    """O SVG com um quadro por caso de vento; ``None`` sem vento comparável."""
    comparados = list(ventos) if ventos is not None else em.ventos_comparados(dados, plano)
    if not comparados:
        return None
    eixo = dados.eixo_vertical
    segmentos = []
    for c in g.corpos:
        if c.forma == ld.FORMA_CHAPA or c.comprimento_m <= 0:
            continue
        a, b = vpb.para_a_planta(c.inicio, eixo), vpb.para_a_planta(c.fim, eixo)
        segmentos.append(((a[0], a[1]), (b[0], b[1])))
    pontos = [p for s in segmentos for p in s]
    if pontos:
        xmin, xmax = min(p[0] for p in pontos), max(p[0] for p in pontos)
        ymin, ymax = min(p[1] for p in pontos), max(p[1] for p in pontos)
    else:
        xmin = xmax = ymin = ymax = 0.0
    largura_m = max(xmax - xmin, ymax - ymin, 1e-6)
    util = LADO - 2 * MARGEM
    escala = util / largura_m
    cx_m, cy_m = (xmin + xmax) / 2, (ymin + ymax) / 2
    maior = max(max(math.hypot(*v.estudo), math.hypot(*v.plano)) for v in comparados) or 1.0
    por_kN = SETA_MAXIMA / maior
    colunas = min(len(comparados), 4)
    linhas = math.ceil(len(comparados) / colunas)
    largura = colunas * LADO
    altura = linhas * (LADO + 34) + 70
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" '
        f'width="{largura}" height="{altura}" font-family="DejaVu Sans, Arial, sans-serif">',
        f'<rect width="{largura}" height="{altura}" fill="#ffffff"/>',
    ]
    for i, v in enumerate(comparados):
        ox = (i % colunas) * LADO
        oy = (i // colunas) * (LADO + 34)
        centro_x, centro_y = ox + LADO / 2, oy + 22 + LADO / 2

        def tela(p: tuple[float, float], centro_x: float = centro_x, centro_y: float = centro_y):
            return (centro_x + (p[0] - cx_m) * escala, centro_y - (p[1] - cy_m) * escala)

        partes.append(
            f'<rect x="{ox + 4}" y="{oy + 22}" width="{LADO - 8}" height="{LADO - 4}" '
            'fill="#f7f8fa" stroke="#dde1e6"/>'
        )
        partes.append(
            f'<text x="{ox + LADO / 2}" y="{oy + 16}" text-anchor="middle" font-size="14" '
            f'font-weight="bold" fill="{COR_TEXTO}">{escape(v.codigo)}'
            + (" — ao contrário" if v.ao_contrario else "")
            + "</text>"
        )
        for a, b in segmentos:
            (x1, y1), (x2, y2) = tela(a), tela(b)
            partes.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{COR_BARRA}" stroke-width="1.6"/>'
            )
        partes.append(
            _seta(centro_x, centro_y, v.plano[0] * por_kN, -v.plano[1] * por_kN, COR_PLANO, False)
        )
        partes.append(
            _seta(centro_x, centro_y, v.estudo[0] * por_kN, -v.estudo[1] * por_kN, COR_ESTUDO, True)
        )
        partes.append(
            f'<text x="{ox + 10}" y="{oy + LADO + 10}" font-size="11" fill="{COR_PLANO}">'
            f"plano {_n(math.hypot(*v.plano))} kN</text>"
            f'<text x="{ox + LADO - 10}" y="{oy + LADO + 10}" font-size="11" text-anchor="end" '
            f'fill="{COR_ESTUDO}">estudo {_n(math.hypot(*v.estudo))} kN</text>'
        )
    topo = linhas * (LADO + 34) + 8
    eixos = (
        "+X para a direita, −Z para cima (vista Superior)" if eixo == "Y" else "+X; +Y para cima"
    )
    partes.append(
        f'<line x1="12" y1="{topo + 8}" x2="40" y2="{topo + 8}" stroke="{COR_PLANO}" '
        'stroke-width="3"/>'
        f'<text x="46" y="{topo + 12}" font-size="12" fill="{COR_TEXTO}">plano de cargas</text>'
        f'<line x1="12" y1="{topo + 28}" x2="40" y2="{topo + 28}" stroke="{COR_ESTUDO}" '
        'stroke-width="3" stroke-dasharray="6 4"/>'
        f'<text x="46" y="{topo + 32}" font-size="12" fill="{COR_TEXTO}">o que o estudo '
        "aplicou</text>"
        f'<text x="12" y="{topo + 52}" font-size="11" fill="{COR_TEXTO}">{escape(eixos)}</text>'
    )
    partes.append("</svg>")
    return "".join(partes)
