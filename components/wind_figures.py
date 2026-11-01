"""Desenhos em planta (SVG) da página Vento nas estruturas: as zonas de pressão de um caso e as
faixas de altas sucções das vedações.

* :func:`svg_planta` — para um caso de vento (direção e ``c_pi``), como a norma divide o telhado
  (dentro do retângulo) e as paredes (faixas em volta), com o ``C_e`` e a pressão líquida ``Δp`` de
  cada zona, a seta do vento e as cotas das faixas (``x``, ``a/2``, ``c₁``);
* :func:`svg_vedacoes` — onde ficam as zonas de ``c_pe`` médio (figuras das Tabelas 6, 7 e 8), com
  a largura delas e a pior pressão de cada uma, para telhas, painéis, terças e fixações.

Cores: azul = sucção (``C_e`` < 0), vermelho = sobrepressão — as mesmas da vista 3D
(:mod:`core.vento_edificio_desenho`). A geometria vem do cálculo. Sem Streamlit.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from components import desenho_svg as ds
from core import vento_edificio_desenho as vd
from core.vento_edificio import COBERTURA_UMA_AGUA, CasoDeVento, ResultadoEdificio

LARGURA = 760
ESPESSURA_PAREDE = 20.0
MARGEM = 96.0
COR_TEXTO = "#1a1a1a"
COR_FUNDO = "#fbfbfd"

#: Mesmas cores da vista 3D (o C_e de −2 a +1 vai do azul ao vermelho, passando pelo branco).
cor_do_ce = vd.cor_do_ce


def _n(valor: float, casas: int = 1) -> str:
    """Com sinal explícito e vírgula: ``+0,7`` e ``−0,8``."""
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:+.{casas}f}".replace(".", ",").replace("-", "−")


def _m(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",").rstrip("0").rstrip(",") + " m"


def _texto(
    x: float,
    y: float,
    conteudo: str,
    *,
    tamanho: float = 11.0,
    giro: float = 0.0,
    peso: str = "normal",
    cor: str = COR_TEXTO,
) -> str:
    return ds.texto(x, y, conteudo, tamanho=tamanho, giro=giro, peso=peso, cor=cor)


def _rect(
    x: float,
    y: float,
    w: float,
    h: float,
    ce: float | None,
    titulo: str = "",
    *,
    borda: str = "#555",
) -> str:
    preenchimento = cor_do_ce(ce) if ce is not None else "#f1f3f6"
    dica = f"<title>{escape(titulo)}</title>" if titulo else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" '
        f'fill="{preenchimento}" stroke="{borda}" stroke-width="1">{dica}</rect>'
    )


def _escala_de_ce(x: float, y: float) -> str:
    partes = [_texto(x + 84, y - 9, "C_e (azul: sucção; vermelho: pressão)", tamanho=9.5)]
    for i, valor in enumerate((-2.0, -1.0, -0.5, 0.0, 0.5, 1.0)):
        partes.append(_rect(x + i * 28, y, 28, 10, valor))
        partes.append(_texto(x + i * 28 + 14, y + 20, _n(valor), tamanho=8.5))
    return "".join(partes)


def _cadeia_de_cotas(
    pontos: list[float], fixo: float, *, horizontal: bool, origem: float, escala: float
) -> str:
    """Cotas encadeadas (a medida de cada trecho) ao longo de x (``horizontal``) ou de y."""
    partes = []
    for inicio, fim in zip(pontos, pontos[1:], strict=False):
        if fim - inicio < 1e-6:
            continue
        rotulo = _m(fim - inicio)
        if horizontal:
            a, b = origem + inicio * escala, origem + fim * escala
            if b - a < 30:
                rotulo = ""
            partes.append(ds.cota(a, fixo, b, fixo, rotulo, tamanho=9.5))
        else:  # y cresce para cima no desenho
            a, b = origem - inicio * escala, origem - fim * escala
            if a - b < 30:
                rotulo = ""
            partes.append(ds.cota(fixo, a, fixo, b, rotulo, tamanho=9.5))
    return "".join(partes)


def svg_planta(resultado: ResultadoEdificio, alpha: int, caso: CasoDeVento | None = None) -> str:
    """SVG da planta com as zonas do vento a ``alpha`` (0, 90 ou −90). Com ``caso`` (o mesmo
    ``alpha``), cada zona mostra também a pressão líquida ``Δp = q·(f_v·C_e − c_pi)`` dele."""
    casos = resultado.casos_do_angulo(alpha)
    if not casos:
        raise ValueError(f"Não há caso de vento a {alpha}°.")
    if caso is None or caso.alpha != alpha:
        caso = casos[0]
    ce = {p.zona.id: p.zona.ce for p in caso.pressoes}
    dp = {p.zona.id: p.pressao_liquida_kN_m2 for p in caso.pressoes}
    nome = {p.zona.id: p.zona.nome for p in caso.pressoes}
    g = resultado.geometria
    a, b = g.a_m, g.b_m
    uma_agua = resultado.entrada.cobertura == COBERTURA_UMA_AGUA
    escala = min(540.0 / a, 300.0 / b)
    pa, pb = a * escala, b * escala
    x0 = MARGEM + ESPESSURA_PAREDE
    y0 = MARGEM / 2 + ESPESSURA_PAREDE + 52.0
    altura = pb + 2 * ESPESSURA_PAREDE + MARGEM + 112.0
    x1, meio_a, meio_b = g.x_m * escala, pa / 2.0, pb / 2.0
    c1 = g.c1_m * escala
    t = ESPESSURA_PAREDE

    def px(x: float) -> float:
        return x0 + x

    def py(y: float) -> float:  # y da edificação cresce para cima
        return y0 + pb - y

    partes: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGURA} {altura:.0f}" '
        f'width="100%" role="img" aria-label="Zonas de pressão do vento a {alpha} graus">',
        f'<rect x="0.5" y="0.5" width="{LARGURA - 1}" height="{altura - 1:.0f}" rx="10" '
        f'fill="{COR_FUNDO}" stroke="{ds.COR_BORDA}"/>',
    ]

    def celula_telhado(xa: float, xb: float, ya: float, yb: float, id_: str) -> None:
        valor = ce.get(id_)
        partes.append(_rect(px(xa), py(yb), xb - xa, yb - ya, valor, nome.get(id_, id_)))
        largura, alto = xb - xa, yb - ya
        if valor is None or largura <= 34 or alto <= 26:
            return
        cx, cy = px((xa + xb) / 2), py((ya + yb) / 2)
        linhas = [(nome.get(id_, id_).split(" (")[0], "bold"), (f"C_e {_n(valor)}", "normal")]
        if alto > 50 and largura > 70:
            linhas.append((f"Δp {_n(dp[id_], 2)} kN/m²", "normal"))
        topo = cy - 7.5 * (len(linhas) - 1)
        for k, (conteudo, peso) in enumerate(linhas):
            partes.append(_texto(cx, topo + 15 * k, conteudo, tamanho=10.5, peso=peso))

    # ---- telhado
    if alpha == 0:
        if uma_agua:
            cortes = [(0.0, meio_b, "HL_ate_b2"), (meio_b, meio_a, "HL_de_b2"), (meio_a, pa, "IJ")]
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
    if not uma_agua and g.theta_graus > 0:  # a cumeeira
        partes.append(ds.linha(px(0), py(meio_b), px(pa), py(meio_b), cor="#555", largura=1.0,
                               tracejado="6 4"))  # fmt: skip

    # ---- paredes (faixas externas); y = 0 embaixo, y = b em cima, x = 0 à esquerda
    def faixa(
        x: float, y: float, w: float, h: float, id_: str, rotulo: str, girar: bool = False
    ) -> None:
        valor = ce.get(id_)
        partes.append(_rect(x, y, w, h, valor, nome.get(id_, id_)))
        comprimento = h if girar else w
        if valor is None or comprimento <= 24:
            return
        etiqueta = f"{rotulo} {_n(valor)}"
        if comprimento > 120 + 6 * len(rotulo):
            etiqueta += f" · Δp {_n(dp[id_], 2)}"
        partes.append(
            _texto(x + w / 2, y + h / 2, etiqueta, tamanho=9.5, giro=-90.0 if girar else 0.0)
        )

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

    # ---- cotas: a, b e as faixas onde o C_e muda
    partes.append(ds.cota(x0 - t, y0 - t - 16, x0 + pa + t, y0 - t - 16, f"a = {_m(a)}"))
    partes.append(ds.cota(x0 + pa + t + 18, y0 + pb + t, x0 + pa + t + 18, y0 - t, f"b = {_m(b)}"))
    if alpha == 0:
        quebras = [0.0, b / 2.0, a / 2.0, a] if uma_agua else [0.0, g.x_m, a / 2.0, a]
        partes.append(
            _cadeia_de_cotas(quebras, y0 + pb + t + 16, horizontal=True, origem=x0, escala=escala)
        )
    else:
        quebras = [0.0, g.c1_m, b] if alpha == 90 else [0.0, b - g.c1_m, b]
        partes.append(
            _cadeia_de_cotas(quebras, x0 - t - 16, horizontal=False, origem=y0 + pb, escala=escala)
        )
    legenda = {
        0: "Vento a 0° (ao longo de a)",
        90: "Vento a 90° (ao longo de b)",
        -90: "Vento a −90° (contra a inclinação)",
    }[alpha]
    partes.append(ds.texto(22, 24, legenda, tamanho=15, ancora="start", peso="bold"))
    partes.append(
        ds.texto(
            22,
            44,
            f"Classe {caso.classe}, q = {ds.n(caso.vento.q_kN_m2, 3)} kN/m² · {caso.cpi.rotulo} · "
            "Δp = q·(f_v·C_e − c_pi) em kN/m² (+ empurra, − puxa)",
            tamanho=11,
            ancora="start",
            cor=ds.COR_SUAVE,
        )
    )

    # ---- seta do vento
    if alpha == 0:
        ya = y0 + pb / 2
        partes.append(ds.seta_de_vento(12.0, ya, x0 - t - 8, ya, espessura=14))
        partes.append(
            ds.etiqueta(
                16,
                ya - 22,
                "Vento",
                tamanho=11,
                cor=ds.COR_VENTO_ESCURO,
                peso="bold",
                ancora="start",
            )  # fmt: skip
        )
    else:
        xa = 34.0
        meio = y0 + pb / 2
        if alpha == 90:  # sopra de baixo para cima
            partes.append(ds.seta_de_vento(xa, y0 + pb + t, xa, meio - 30, espessura=14))
        else:  # sopra de cima para baixo
            partes.append(ds.seta_de_vento(xa, y0 - t, xa, meio + 30, espessura=14))
        partes.append(
            ds.texto(
                xa + 20, meio, "Vento", tamanho=11, giro=-90.0, cor=ds.COR_VENTO_ESCURO, peso="bold"
            )  # fmt: skip
        )
    partes.append(_escala_de_ce(LARGURA - 190, altura - 34))
    partes.append("</svg>")
    return "".join(partes)


# ---------------------------------------------------------------------------------------------
# Vedações: zonas de c_pe médio
# ---------------------------------------------------------------------------------------------
def svg_vedacoes(resultado: ResultadoEdificio) -> str:
    """SVG da planta com as zonas de altas sucções (``c_pe`` médio) do telhado e das paredes,
    numeradas, e a lista com o ``c_pe`` e a pior pressão líquida de cada uma."""
    g = resultado.geometria
    a, b = g.a_m, g.b_m
    faixas = vd.faixas_de_vedacao(resultado)
    escala = min(500.0 / a, 270.0 / b)
    pa, pb = a * escala, b * escala
    t = 16.0
    x0 = 70.0 + t
    y0 = 92.0 + t
    altura_da_lista = 26 + 19 * len(faixas)
    altura = y0 + pb + t + 64 + altura_da_lista

    def px(x: float) -> float:
        return x0 + x * escala

    def py(y: float) -> float:
        return y0 + pb - y * escala

    partes: list[str] = []
    # Paredes (faixa em volta) e telhado (retângulo), claros: fora das faixas vale o C_e da zona.
    partes.append(_rect(x0 - t, y0 - t, pa + 2 * t, pb + 2 * t, None, borda="#9aa3ad"))
    partes.append(_rect(x0, y0, pa, pb, None, "Telhado", borda="#555"))
    if g.cobertura != COBERTURA_UMA_AGUA and g.theta_graus > 0:
        partes.append(ds.linha(px(0), py(b / 2), px(a), py(b / 2), cor="#555", largura=1.0,
                               tracejado="6 4"))  # fmt: skip
    bolhas: list[str] = []
    for numero, f in enumerate(faixas, start=1):
        rotulo = str(numero)
        for xa, xb, ya, yb in f.retangulos:
            if xb - xa <= 1e-9 or yb - ya <= 1e-9:
                continue
            partes.append(_rect(px(xa), py(yb), (xb - xa) * escala, (yb - ya) * escala, f.cpe,
                                f"{f.rotulo}: c_pe médio {_n(f.cpe)}"))  # fmt: skip
            bolhas.append(ds.bolha(px((xa + xb) / 2), py((ya + yb) / 2), rotulo, raio=8.5))
        for parede, s0, s1 in f.trechos_de_parede:
            if s1 - s0 <= 1e-9:
                continue
            if parede in ("y0", "yb"):
                x, w = px(s0), (s1 - s0) * escala
                y = y0 + pb if parede == "y0" else y0 - t
                h = t
            else:
                y, h = py(s1), (s1 - s0) * escala
                x = x0 - t if parede == "x0" else x0 + pa
                w = t
            partes.append(_rect(x, y, w, h, f.cpe, f"{f.rotulo}: c_pe médio {_n(f.cpe)}"))
            if w >= 14 and h >= 14:
                bolhas.append(ds.bolha(x + w / 2, y + h / 2, rotulo, raio=7.0))
    partes.extend(bolhas)
    # Cotas: a, b, a largura y das faixas do telhado, o x dos cantos e a faixa das paredes.
    partes.append(ds.cota(x0 - t, y0 - t - 14, x0 + pa + t, y0 - t - 14, f"a = {_m(a)}"))
    partes.append(ds.cota(x0 + pa + t + 16, y0 + pb + t, x0 + pa + t + 16, y0 - t, f"b = {_m(b)}"))
    resumo = [f"y = mín(h; 0,15·b) = {_m(g.y_telhado_m)}"]
    if g.cobertura != COBERTURA_UMA_AGUA:
        resumo.append(f"x = máx(b/3; a/4) ≤ 2h = {_m(g.x_m)}")
    resumo.append(f"paredes: mín(0,2·b; h) = {_m(g.faixa_cpe_medio_parede_m)} de cada canto")
    partes.append(
        ds.texto(
            x0 - t,
            y0 + pb + t + 22,
            " · ".join(resumo),
            tamanho=10.5,
            ancora="start",
            cor=ds.COR_SUAVE,
        )  # fmt: skip
    )
    # A lista: número, onde, c_pe médio e a pior pressão líquida entre os c_pi.
    y_lista = y0 + pb + t + 52
    partes.append(
        ds.texto(
            x0 - t,
            y_lista,
            "Zona · c_pe médio · pior Δp = q·(c_pe − c_pi) (kN/m²)",
            tamanho=11,
            ancora="start",
            peso="bold",
        )  # fmt: skip
    )
    for numero, f in enumerate(faixas, start=1):
        yy = y_lista + 19 * numero
        partes.append(_rect(x0 - t, yy - 6, 18, 12, f.cpe))
        partes.append(
            ds.texto(
                x0 - t + 26,
                yy,
                f"{numero}  {f.rotulo}: c_pe {_n(f.cpe)} → Δp {_n(f.pior_kN_m2, 2)} kN/m²",
                tamanho=10.5,
                ancora="start",
            )  # fmt: skip
        )
    q = resultado.vento_vedacoes.q_kN_m2
    corpo = "".join(partes)
    return ds.documento(
        LARGURA,
        altura,
        [corpo],
        "Vedações — zonas de altas sucções (c_pe médio)",
        subtitulo=(
            f"q das vedações = {ds.n(q, 3)} kN/m² (classe A, topo). Fora das zonas numeradas vale "
            "o C_e da zona (aba Pressões por zona)."
        ),
    )
