"""Desenhos do contraventamento: a planta com as linhas contraventadas e a elevação da linha mais
carregada com a força em cada diagonal.

Cada função devolve um :class:`core.cena_3d.Desenho2D`: a página o mostra em SVG
(:func:`components.cena_3d_svg.svg_da_cena`) e o memorial o grava no registro
(:func:`core.cena_3d.desenho_para_dicionario`) e o desenha em PNG
(:func:`core.cena_3d_png.png_da_cena`) — os dois lados desenham a mesma coisa. Sem Streamlit.

Cores: azul = tração, vermelho = compressão, cinza = peça sem esforço ou desprezada, laranja =
vento.
"""

from __future__ import annotations

from collections.abc import Sequence

from core import cena_3d as c3
from core import contraventamento_plataforma as cp
from core import desenho_2d as d2
from core.desenho_2d import Item, Ponto

COR_SUAVE = "#6b7280"
COR_ESTRUTURA = "#3f4652"
COR_VIGA = "#9aa3ad"
COR_EIXO = "#b8bfc8"
COR_CONTRAVENTADO = "#1f5fbf"
COR_TRACAO = "#1f6feb"
COR_COMPRESSAO = "#cf222e"
COR_DESPREZADA = "#9aa1a9"
COR_DIAGONAL_SIMPLES = "#7b3fb5"
COR_VENTO = "#d4760a"
COR_VENTO_ESCURO = "#a14f00"


def linhas_contraventadas(n_linhas_de_pilares: int, contraventadas: int) -> list[int]:
    """As linhas de pilares que levam contraventamento: as das pontas primeiro, para dentro."""
    ordem = sorted(
        range(n_linhas_de_pilares), key=lambda k: (min(k, n_linhas_de_pilares - 1 - k), k)
    )
    return sorted(ordem[:contraventadas])


def letra_do_eixo(indice: int) -> str:
    letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return letras[indice] if indice < len(letras) else f"A{indice}"


# ---------------------------------------------------------------------------------------------
# Peças próprias da planta
# ---------------------------------------------------------------------------------------------
def _pilar_h(x: float, y: float, tamanho: float = 13.0) -> list[Item]:
    meia, mesa = tamanho / 2, 2.6
    return [
        c3.Poligono2D(
            ((x - meia, y - meia), (x + meia, y - meia), (x + meia, y - meia + mesa),
             (x - meia, y - meia + mesa)),
            COR_ESTRUTURA, COR_ESTRUTURA,
        ),
        c3.Poligono2D(
            ((x - meia, y + meia - mesa), (x + meia, y + meia - mesa), (x + meia, y + meia),
             (x - meia, y + meia)),
            COR_ESTRUTURA, COR_ESTRUTURA,
        ),
        c3.Poligono2D(
            ((x - 1.1, y - meia), (x + 1.1, y - meia), (x + 1.1, y + meia), (x - 1.1, y + meia)),
            COR_ESTRUTURA, COR_ESTRUTURA,
        ),
    ]  # fmt: skip


def _marca_painel(a: float, b: float, c: float, *, horizontal: bool, tipo: str,
                  lado: int = -1) -> list[Item]:  # fmt: skip
    """Símbolo do contraventamento ao lado do painel: a elevação do painel rebatida (um retângulo
    pequeno com o X, a diagonal ou o V), do lado de fora da planta."""
    meio = (a + b) / 2
    comprimento = min(abs(b - a) * 0.55, 70.0)
    alto = 20.0
    if horizontal:
        x0, x1 = meio - comprimento / 2, meio + comprimento / 2
        y0, y1 = (c + 8, c + 8 + alto) if lado > 0 else (c - 8 - alto, c - 8)
        cantos = ((x0, y1), (x1, y1), (x1, y0), (x0, y0))  # base embaixo, topo em cima
    else:
        y0, y1 = meio - comprimento / 2, meio + comprimento / 2
        x0, x1 = (c + 8, c + 8 + alto) if lado > 0 else (c - 8 - alto, c - 8)
        cantos = ((x0, y1), (x0, y0), (x1, y0), (x1, y1))
    pa, pb, pc, pd = cantos  # pé esquerdo, pé direito, topo direito, topo esquerdo
    partes: list[Item] = [c3.Poligono2D(cantos, "#ffffff", COR_VIGA, 0.8)]
    if tipo == cp.TIPO_V_INVERTIDO:
        topo = ((pc[0] + pd[0]) / 2, (pc[1] + pd[1]) / 2)
        partes.append(d2.linha(pa, topo, COR_CONTRAVENTADO, 1.8))
        partes.append(d2.linha(pb, topo, COR_CONTRAVENTADO, 1.8))
    else:
        partes.append(d2.linha(pa, pc, COR_CONTRAVENTADO, 1.8))
        if tipo != cp.TIPO_DIAGONAL_SIMPLES:
            partes.append(d2.linha(pb, pd, COR_CONTRAVENTADO, 1.8))
    return partes


# ---------------------------------------------------------------------------------------------
# Planta
# ---------------------------------------------------------------------------------------------
def planta(e: cp.EntradaContraventamento) -> c3.Desenho2D:
    """Planta com os eixos, os pilares, as linhas contraventadas (com o símbolo do contraventamento
    nos painéis), as cotas e o vento nas duas direções."""
    largura, altura = 900.0, 560.0
    enq = c3.Enquadramento(
        [(0.0, 0.0), (e.comprimento_x_m, -e.largura_y_m)], (150, 110, largura - 150, altura - 160)
    )

    def p(x_m: float, y_m: float) -> Ponto:
        return enq((x_m, -y_m))

    ax = e.comprimento_x_m / e.vaos_x
    ay = e.largura_y_m / e.vaos_y
    itens: list[Item] = []
    x_esq, y_base = p(0.0, 0.0)
    x_dir, y_topo = p(e.comprimento_x_m, e.largura_y_m)
    # eixos (traço e ponto) com as bolhas
    for i in range(e.vaos_x + 1):
        x, _ = p(i * ax, 0.0)
        itens.append(d2.linha((x, y_topo - 26), (x, y_base + 26), COR_EIXO, 0.8, "10 3 2 3"))
        itens += d2.bolha(x, y_topo - 40, str(i + 1))
    for j in range(e.vaos_y + 1):
        _, y = p(0.0, j * ay)
        itens.append(d2.linha((x_esq - 26, y), (x_dir + 26, y), COR_EIXO, 0.8, "10 3 2 3"))
        itens += d2.bolha(x_esq - 40, y, letra_do_eixo(j))
    # vigas
    for j in range(e.vaos_y + 1):
        itens.append(d2.linha(p(0, j * ay), p(e.comprimento_x_m, j * ay), COR_VIGA, 2.4))
    for i in range(e.vaos_x + 1):
        itens.append(d2.linha(p(i * ax, 0), p(i * ax, e.largura_y_m), COR_VIGA, 2.4))
    # linhas contraventadas
    sx, sy = e.contraventamento_x, e.contraventamento_y
    for j in linhas_contraventadas(e.vaos_y + 1, sx.linhas):
        itens.append(d2.linha(p(0, j * ay), p(e.comprimento_x_m, j * ay), COR_CONTRAVENTADO, 4.5))
        lado = 1 if j * ay >= e.largura_y_m / 2 else -1
        for painel in range(min(sx.paineis_por_linha, e.vaos_x)):
            xa, ya = p(painel * ax, j * ay)
            xb, _ = p((painel + 1) * ax, j * ay)
            itens += _marca_painel(xa, xb, ya, horizontal=True, tipo=sx.tipo, lado=-lado)
    for i in linhas_contraventadas(e.vaos_x + 1, sy.linhas):
        itens.append(d2.linha(p(i * ax, 0), p(i * ax, e.largura_y_m), COR_CONTRAVENTADO, 4.5))
        lado = 1 if i * ax >= e.comprimento_x_m / 2 else -1
        for painel in range(min(sy.paineis_por_linha, e.vaos_y)):
            xa, ya = p(i * ax, painel * ay)
            _, yb = p(i * ax, (painel + 1) * ay)
            itens += _marca_painel(ya, yb, xa, horizontal=False, tipo=sy.tipo, lado=lado)
    # pilares (H)
    for i in range(e.vaos_x + 1):
        for j in range(e.vaos_y + 1):
            itens += _pilar_h(*p(i * ax, j * ay))
    # cotas: vãos e total
    y_cota = y_base + 46
    for i in range(e.vaos_x):
        itens += d2.cota(
            (p(i * ax, 0)[0], y_cota), (p((i + 1) * ax, 0)[0], y_cota), f"{d2.n(ax, 2)} m"
        )
    itens += d2.cota(
        (x_esq, y_cota + 30),
        (x_dir, y_cota + 30),
        f"L_x = {d2.n(e.comprimento_x_m, 2)} m ({e.vaos_x} vão(s))",
    )
    x_cota = x_dir + 46
    for j in range(e.vaos_y):
        itens += d2.cota(
            (x_cota, p(0, j * ay)[1]), (x_cota, p(0, (j + 1) * ay)[1]), f"{d2.n(ay, 2)} m"
        )
    itens += d2.cota(
        (x_cota + 34, y_base), (x_cota + 34, y_topo), f"L_y = {d2.n(e.largura_y_m, 2)} m"
    )
    # vento
    ym = (y_base + y_topo) / 2
    itens.append(c3.Seta2D((24, ym), (x_esq - 60, ym), COR_VENTO, larga=True))
    itens.append(
        d2.etiqueta(30, ym - 24, "Vento X", cor=COR_VENTO_ESCURO, peso="bold", ancora="start")
    )
    xm = x_esq + (x_dir - x_esq) * 0.3
    itens.append(c3.Seta2D((xm, altura - 22), (xm, y_base + 92), COR_VENTO, larga=True))
    itens.append(
        d2.etiqueta(
            xm + 18, altura - 34, "Vento Y", cor=COR_VENTO_ESCURO, peso="bold", ancora="start"
        )
    )
    return c3.Desenho2D(
        largura,
        altura,
        tuple(itens),
        "Planta — linhas contraventadas",
        "Símbolo do contraventamento no painel da ponta da linha só para ilustrar: a posição é a "
        "do seu desenho.",
        legenda=(
            (COR_CONTRAVENTADO, "linha contraventada"),
            (COR_VIGA, "viga"),
            (COR_EIXO, "eixo"),
        ),
    )


# ---------------------------------------------------------------------------------------------
# Elevação de uma linha
# ---------------------------------------------------------------------------------------------
def elevacao_da_linha(
    e: cp.EntradaContraventamento, andares: Sequence[cp.AndarNaDirecao], direcao: str
) -> c3.Desenho2D:
    """A linha contraventada mais carregada vista de frente, com a força em cada diagonal e o
    cortante de cada andar."""
    s = e.sistema(direcao)
    comprimento = e.comprimento_x_m if direcao == "X" else e.largura_y_m
    vaos = e.vaos_x if direcao == "X" else e.vaos_y
    painel = comprimento / vaos
    largura, altura = 900.0, 540.0
    h_total = e.cotas_m[-1]
    enq = c3.Enquadramento(
        [(0.0, 0.0), (comprimento, -h_total)], (110, 90, largura - 240, altura - 90)
    )

    def p(x_m: float, z_m: float) -> Ponto:
        return enq((x_m, -z_m))

    x0, y0 = p(0.0, 0.0)
    xf, _ = p(comprimento, 0.0)
    itens: list[Item] = [*d2.terreno(x0 - 40, xf + 40, y0 + 10.5)]
    cotas = (0.0, *e.cotas_m)
    por_andar = {a.andar: a for a in andares}
    # diagonais primeiro (pilares e vigas por cima)
    for i in range(1, len(cotas)):
        andar = por_andar.get(i)
        if andar is None:
            continue
        zb, zt = cotas[i - 1], cotas[i]
        for k in range(min(s.paineis_por_linha, vaos)):
            (xa, yb_), (xb, yt) = p(k * painel, zb), p((k + 1) * painel, zt)
            n_t, n_c = d2.n(andar.tracao_kN), d2.n(andar.compressao_kN)
            if s.tipo == cp.TIPO_V_INVERTIDO:
                xm = (xa + xb) / 2
                itens.append(d2.linha((xa, yb_), (xm, yt), COR_TRACAO, 3.2))
                itens.append(d2.linha((xb, yb_), (xm, yt), COR_COMPRESSAO, 3.2))
                itens.append(d2.etiqueta((xa + xm) / 2, (yb_ + yt) / 2, f"+{n_t}", tamanho=10.5,
                                       cor=COR_TRACAO, peso="bold"))  # fmt: skip
                itens.append(d2.etiqueta((xb + xm) / 2, (yb_ + yt) / 2, f"−{n_c}", tamanho=10.5,
                                       cor=COR_COMPRESSAO, peso="bold"))  # fmt: skip
            elif s.tipo == cp.TIPO_DIAGONAL_SIMPLES:
                itens.append(d2.linha((xa, yb_), (xb, yt), COR_DIAGONAL_SIMPLES, 3.2))
                itens.append(d2.etiqueta((xa + xb) / 2, (yb_ + yt) / 2, f"±{n_t}", tamanho=10.5,
                                       cor=COR_DIAGONAL_SIMPLES, peso="bold"))  # fmt: skip
            else:
                itens.append(d2.linha((xa, yb_), (xb, yt), COR_TRACAO, 3.2))
                if s.tipo == cp.TIPO_X_TRACAO:
                    itens.append(d2.linha((xa, yt), (xb, yb_), COR_DESPREZADA, 2, "6 5"))
                    rotulo_c, cor_c = "0 (desprezada)", COR_DESPREZADA
                else:
                    itens.append(d2.linha((xa, yt), (xb, yb_), COR_COMPRESSAO, 3.2))
                    rotulo_c, cor_c = f"−{n_c}", COR_COMPRESSAO
                xm, ym = (xa + xb) / 2, (yb_ + yt) / 2
                itens.append(d2.etiqueta(xm, ym - 17, f"+{n_t}", tamanho=10.5, cor=COR_TRACAO,
                                       peso="bold"))  # fmt: skip
                itens.append(d2.etiqueta(xm, ym + 17, rotulo_c, tamanho=10, cor=cor_c))
        # cortante do andar à direita
        _, ym = p(0.0, (zb + zt) / 2)
        itens.append(c3.Seta2D((xf + 120, ym), (xf + 14, ym), COR_VENTO, 2.6, 10.0))
        itens.append(
            d2.etiqueta(xf + 70, ym - 16, f"V{i} = {d2.n(andar.forca_na_linha_kN)} kN", tamanho=10.5,
                      cor=COR_VENTO_ESCURO, peso="bold")
        )  # fmt: skip
    for k in range(vaos + 1):
        x, _ = p(k * painel, 0.0)
        itens.append(d2.linha((x, y0), (x, p(0.0, h_total)[1]), COR_ESTRUTURA, 3.6))
        itens += d2.apoio(x, y0 + 0.5, tamanho=7)
    for z in e.cotas_m:
        _, y = p(0.0, z)
        itens.append(d2.linha((x0, y), (xf, y), COR_ESTRUTURA, 3.6))
        itens.append(
            c3.Poligono2D(((x0 - 24, y), (x0 - 32, y - 7), (x0 - 16, y - 7)), COR_SUAVE, COR_SUAVE)
        )
        itens.append(
            d2.texto(x0 - 38, y - 3, f"+{d2.n(z, 2)} m", tamanho=10.5, ancora="end", cor=COR_SUAVE)
        )
    for k in range(vaos):
        xa, _ = p(k * painel, 0.0)
        xb, _ = p((k + 1) * painel, 0.0)
        itens += d2.cota((xa, y0 + 34), (xb, y0 + 34), f"{d2.n(painel, 2)} m")
    return c3.Desenho2D(
        largura,
        altura,
        tuple(itens),
        f"Elevação da linha mais carregada — direção {direcao}",
        f"{cp.TIPOS[s.tipo]}; forças de cálculo nas diagonais (ELU, com B₂).",
        legenda=(
            (COR_TRACAO, "tração (kN)"),
            (COR_COMPRESSAO, "compressão (kN)"),
            (COR_DESPREZADA, "desprezada"),
            (COR_VENTO, "cortante na linha (ELU, com B₂)"),
        ),
    )


def figuras_para_o_registro(r: cp.ResultadoContraventamento) -> list[dict[str, object]]:
    """A planta e a elevação de cada direção, prontas para o memorial desenhar."""
    e = r.entrada
    figuras = [
        c3.desenho_para_dicionario(
            planta(e), legenda="Planta com as linhas contraventadas nas duas direções."
        )
    ]
    for direcao in cp.DIRECOES:
        figuras.append(
            c3.desenho_para_dicionario(
                elevacao_da_linha(e, r.andares_da_direcao(direcao), direcao),
                legenda=(
                    f"Linha contraventada mais carregada na direção {direcao}: força de cálculo "
                    "em cada diagonal e cortante de cada andar (ELU, com B₂)."
                ),
            )
        )
    return figuras
