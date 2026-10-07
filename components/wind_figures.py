"""Desenho em planta das zonas de pressão (SVG), para a página Vento nas estruturas.

O desenho mostra, para um ângulo de incidência, como a norma divide o telhado (dentro do
retângulo) e as paredes (faixas em volta), com o coeficiente ``C_e`` de cada zona e uma seta do
vento. Cores: azul = sucção (``C_e`` < 0), vermelho = sobrepressão (``C_e`` > 0). Não tem
dependências: devolve texto SVG, que a página mostra com ``st.image`` ou ``st.markdown``.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

from core.vento_edificio import COBERTURA_UMA_AGUA, CasoDeVento, ResultadoEdificio

LARGURA = 760
ESPESSURA_PAREDE = 20.0
MARGEM = 96.0
COR_TEXTO = "#1a1a1a"
COR_FUNDO = "#fbfbfd"


def cor_do_ce(ce: float) -> str:
    """Azul para sucção e vermelho para sobrepressão, em tons claros que deixam o texto legível."""
    if ce >= 0:
        t = min(ce / 1.0, 1.0)
        return f"rgb(255,{round(255 - 150 * t)},{round(255 - 150 * t)})"
    t = min(-ce / 2.0, 1.0)
    return f"rgb({round(255 - 175 * t)},{round(255 - 120 * t)},255)"


def _texto(
    x: float,
    y: float,
    conteudo: str,
    *,
    tamanho: float = 11.0,
    ancora: str = "middle",
    giro: float = 0.0,
    peso: str = "normal",
) -> str:
    transforma = f' transform="rotate({giro} {x:.1f} {y:.1f})"' if giro else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tamanho}" text-anchor="{ancora}" '
        f'dominant-baseline="middle" font-family="sans-serif" font-weight="{peso}" '
        f'fill="{COR_TEXTO}"{transforma}>{escape(conteudo)}</text>'
    )


def _seta(x1: float, y1: float, x2: float, y2: float) -> str:
    """Linha de (x1, y1) a (x2, y2) com uma ponta triangular em (x2, y2)."""
    comprimento = max(math.hypot(x2 - x1, y2 - y1), 1e-9)
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    base_x, base_y = x2 - 11 * ux, y2 - 11 * uy
    px_, py_ = -uy, ux  # perpendicular
    ponta = (
        f"{x2:.1f},{y2:.1f} {base_x + 5 * px_:.1f},{base_y + 5 * py_:.1f} "
        f"{base_x - 5 * px_:.1f},{base_y - 5 * py_:.1f}"
    )
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{base_x:.1f}" y2="{base_y:.1f}" '
        f'stroke="{COR_TEXTO}" stroke-width="3"/>'
        f'<polygon points="{ponta}" fill="{COR_TEXTO}"/>'
    )


def _rect(x: float, y: float, w: float, h: float, ce: float | None, titulo: str = "") -> str:
    preenchimento = cor_do_ce(ce) if ce is not None else "#eeeeee"
    dica = f"<title>{escape(titulo)}</title>" if titulo else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" '
        f'fill="{preenchimento}" stroke="#555" stroke-width="1">{dica}</rect>'
    )


def _numero(valor: float) -> str:
    return f"{valor:+.1f}".replace(".", ",").replace("-", "−")


def svg_planta(resultado: ResultadoEdificio, alpha: int) -> str:
    """SVG da planta com as zonas do vento a ``alpha`` (0, 90 ou −90)."""
    casos = resultado.casos_do_angulo(alpha)
    if not casos:
        raise ValueError(f"Não há caso de vento a {alpha}°.")
    caso: CasoDeVento = casos[0]
    ce = {p.zona.id: p.zona.ce for p in caso.pressoes}
    nome = {p.zona.id: p.zona.nome for p in caso.pressoes}
    g = resultado.geometria
    a, b = g.a_m, g.b_m
    uma_agua = resultado.entrada.cobertura == COBERTURA_UMA_AGUA
    escala = min(540.0 / a, 300.0 / b)
    pa, pb = a * escala, b * escala
    x0 = MARGEM + ESPESSURA_PAREDE
    y0 = MARGEM / 2 + ESPESSURA_PAREDE + 20.0
    altura = pb + 2 * ESPESSURA_PAREDE + MARGEM + 40.0
    x1, meio_a, meio_b = g.x_m * escala, pa / 2.0, pb / 2.0
    c1 = g.c1_m * escala

    def px(x: float) -> float:
        return x0 + x

    def py(y: float) -> float:  # y da edificação cresce para cima
        return y0 + pb - y

    partes: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGURA} {altura:.0f}" '
        f'width="100%" role="img" aria-label="Zonas de pressão do vento a {alpha} graus">',
        f'<rect x="0" y="0" width="{LARGURA}" height="{altura:.0f}" rx="8" fill="{COR_FUNDO}"/>',
    ]

    def celula_telhado(xa: float, xb: float, ya: float, yb: float, id_: str) -> None:
        valor = ce.get(id_)
        partes.append(_rect(px(xa), py(yb), xb - xa, yb - ya, valor, nome.get(id_, id_)))
        if valor is not None and xb - xa > 34 and yb - ya > 26:
            partes.append(
                _texto(
                    px((xa + xb) / 2),
                    py((ya + yb) / 2) - 7,
                    nome.get(id_, id_).split(" (")[0],
                    tamanho=10.5,
                    peso="bold",
                )
            )
            partes.append(
                _texto(
                    px((xa + xb) / 2), py((ya + yb) / 2) + 8, "C_e " + _numero(valor), tamanho=10.5
                )
            )

    # ---- telhado
    if alpha == 0:
        if uma_agua:
            cortes = [
                (0.0, g.b_m * escala / 2.0, "HL_ate_b2"),
                (g.b_m * escala / 2.0, meio_a, "HL_de_b2"),
                (meio_a, pa, "IJ"),
            ]
            for xa, xb, id_ in cortes:
                celula_telhado(xa, xb, 0.0, pb, id_)
        else:
            cortes = [(0.0, x1, "EG"), (x1, meio_a, "FH"), (meio_a, pa, "IJ")]
            for xa, xb, id_ in cortes:
                celula_telhado(xa, xb, 0.0, meio_b, id_)
                celula_telhado(xa, xb, meio_b, pb, id_)
    else:
        # Metade de baixo da planta = y de 0 a b/2 (vento a 90° vem de lá); a de cima, o resto.
        baixo, alto = ("HI", "LJ") if uma_agua else ("EFI", "GHJ")
        celula_telhado(0.0, pa, 0.0, meio_b, baixo)
        celula_telhado(0.0, pa, meio_b, pb, alto)

    # ---- paredes (faixas externas); y = 0 embaixo, y = b em cima, x = 0 à esquerda
    def faixa(
        x: float, y: float, w: float, h: float, id_: str, rotulo: str, girar: bool = False
    ) -> None:
        valor = ce.get(id_)
        partes.append(_rect(x, y, w, h, valor, nome.get(id_, id_)))
        if w > 24 and h > 14 or girar and h > 24:
            etiqueta = f"{rotulo} {_numero(valor)}" if valor is not None else rotulo
            partes.append(
                _texto(x + w / 2, y + h / 2, etiqueta, tamanho=9.5, giro=-90.0 if girar else 0.0)
            )

    t = ESPESSURA_PAREDE
    if alpha == 0:
        faixa(x0 - t, y0, t, pb, "C", "C", girar=True)  # barlavento, à esquerda
        faixa(x0 + pa, y0, t, pb, "D", "D", girar=True)
        for xa, xb, id_, rotulo in (
            (0.0, x1, "A1B1", "A1/B1"),
            (x1, meio_a, "A2B2", "A2/B2"),
            (meio_a, pa, "A3B3", "A3/B3"),
        ):
            faixa(px(xa), y0 + pb, xb - xa, t, id_, rotulo)  # parede y = 0 (embaixo)
            faixa(px(xa), y0 - t, xb - xa, t, id_, rotulo)  # parede y = b (em cima)
    else:
        barlavento_embaixo = alpha == 90  # o vento a 90° sopra de y = 0 (embaixo) para y = b
        embaixo, em_cima = ("A", "B") if barlavento_embaixo else ("B", "A")
        faixa(x0, y0 + pb, pa, t, embaixo, embaixo)  # parede y = 0
        faixa(x0, y0 - t, pa, t, em_cima, em_cima)  # parede y = b
        # Paredes curtas: C1/D1 junto à parede de barlavento, C2/D2 no resto.
        if barlavento_embaixo:
            trechos = [(y0 + pb - c1, c1, "C1D1", "C1/D1"), (y0, pb - c1, "C2D2", "C2/D2")]
        else:
            trechos = [(y0, c1, "C1D1", "C1/D1"), (y0 + c1, pb - c1, "C2D2", "C2/D2")]
        for ya, hh, id_, rotulo in trechos:
            faixa(x0 - t, ya, t, hh, id_, rotulo, girar=True)
            faixa(x0 + pa, ya, t, hh, id_, rotulo, girar=True)

    # ---- cotas e título
    partes.append(
        _texto(x0 + pa / 2, y0 - t - 14, f"a = {g.a_m:g} m".replace(".", ","), tamanho=11)
    )
    partes.append(
        _texto(
            x0 + pa + t + 16,
            y0 + pb / 2,
            f"b = {g.b_m:g} m".replace(".", ","),
            tamanho=11,
            giro=-90.0,
        )
    )
    legenda = {
        0: "Vento a 0° (ao longo de a)",
        90: "Vento a 90° (ao longo de b)",
        -90: "Vento a −90° (contra a inclinação)",
    }[alpha]
    partes.append(
        _texto(
            LARGURA / 2,
            altura - 14,
            legenda
            + f" — classe {caso.classe}, q = {caso.vento.q_kN_m2:.3f} kN/m²".replace(".", ","),
            tamanho=12,
            peso="bold",
        )
    )

    # ---- seta do vento
    if alpha == 0:
        ya = y0 + pb / 2
        partes.append(_seta(14.0, ya, x0 - t - 8, ya))
        partes.append(_texto(48, ya - 14, "vento", tamanho=11))
    else:
        xa = 40.0
        meio = y0 + pb / 2
        if alpha == 90:  # sopra de baixo para cima
            partes.append(_seta(xa, y0 + pb + t, xa, meio - 30))
        else:  # sopra de cima para baixo
            partes.append(_seta(xa, y0 - t, xa, meio + 30))
        partes.append(_texto(xa + 16, meio, "vento", tamanho=11, giro=-90.0))
    # ---- escala de cores
    xl = LARGURA - 190
    yl = altura - 54
    for i, valor in enumerate((-2.0, -1.0, -0.5, 0.0, 0.5, 1.0)):
        partes.append(_rect(xl + i * 28, yl, 28, 10, valor))
        partes.append(_texto(xl + i * 28 + 14, yl + 20, _numero(valor), tamanho=8.5))
    partes.append(_texto(xl + 84, yl - 9, "C_e (azul: sucção; vermelho: pressão)", tamanho=9.5))
    partes.append("</svg>")
    return "".join(partes)
