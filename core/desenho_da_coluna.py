"""A coluna em pé (Flambagem de colunas): duas vistas, os apoios, os travamentos e a mão-francesa.

* **Vista frontal — plano x–z**: o perfil visto de frente, com a largura ao longo de x da seção;
  é o plano da flexão em torno de y (apoio, K_y e L_y).
* **Vista lateral — plano y–z**: o perfil visto de lado, com a largura ao longo de y; é o plano da
  flexão em torno de x (apoio, K_x e L_x).

As arestas do perfil saem da forma da seção (:func:`core.desenho_da_secao.forma_da_secao`): cada
canto vira uma linha vertical, cheia se dá para vê-la e tracejada se fica escondida atrás do aço
(olhando de y negativo na frontal e de x negativo na lateral). Os travamentos aparecem a cada
comprimento destravado e a mão-francesa entra na vista do plano em que ela age (o que flete o eixo
x está no plano y–z). A altura está em escala; a largura também, salvo quando o perfil ficaria fino
demais para ler — aí ela é aumentada e a legenda diz isso.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte
from core.column_design import Secao
from core.desenho_da_secao import FormaDaSecao, forma_da_secao

ESC = dg.ESC
_ACO = "#dbe3ee"
_EIXO = "#1d4ed8"
_BARRA_MF = "#9ca3af"  # a mão-francesa
_FORCA = "#b45309"
_TRAVA = "#0f766e"  # travamentos
_LARGURA_PX, _ALTURA_PX = 980, 640
_LARGURA_MINIMA_PX = 26.0  # abaixo disto a largura do perfil é aumentada no desenho

Ponto = tuple[float, float]

#: O que cada condição de apoio da Tabela E.1 põe na base e no topo da coluna.
APOIOS_NAS_PONTAS: dict[str, tuple[str, str]] = {
    "Biapoiada (pino-pino)": ("pino", "pino"),
    "Engastada-livre (em balanço)": ("engaste", "livre"),
    "Engastada-pino": ("engaste", "pino"),
    "Biengastada": ("engaste", "engaste"),
    "Biengastada com translação (deslocável)": ("engaste", "engaste deslocável"),
    "Engastada-pino com translação (deslocável)": ("engaste", "pino deslocável"),
}


@dataclass(frozen=True)
class MaoFrancesaNoDesenho:
    """A mão-francesa como a página informa: força de cálculo, ângulo com a coluna, altura do nó
    (da base), o eixo que ela flete e a excentricidade da ligação."""

    forca_kN: float
    angulo_graus: float
    altura_mm: float
    eixo: str
    excentricidade_mm: float = 0.0


@dataclass(frozen=True)
class ColunaEmPe:
    secao: Secao
    comprimento_mm: float
    lx_mm: float
    ly_mm: float
    kx: float
    ky: float
    apoio_x: str
    apoio_y: str
    mao_francesa: MaoFrancesaNoDesenho | None = None


@dataclass(frozen=True)
class Aresta:
    """Uma aresta vertical do perfil na vista: a posição (mm, a partir de G) e se é vista."""

    posicao: float
    vista: bool


def _n(valor: float, casas: int = 0) -> str:
    if abs(valor - round(valor)) < 1e-6:
        return f"{round(valor):d}"
    return f"{valor:.{casas}f}".replace(".", ",")


def _material_em(forma: FormaDaSecao, x: float, y: float) -> bool:
    """O ponto (mm, y para cima) está no aço da seção?"""
    if any(dg.dentro((x, y), c) for c in forma.vazados):
        return False
    if any(dg.dentro((x, y), c) for c in forma.cheios):
        return True
    raio = math.hypot(x, y)
    return any(interno < raio < externo for externo, interno in forma.aneis)


def na_vista(horizontal: str, x: float, y: float) -> Ponto:
    """(u, w) de um ponto da seção na vista: u para a direita de quem olha, w para longe dele.

    Frontal (``horizontal`` = "x"): olha de y negativo, u = x, w = y. Lateral ("y"): olha de x
    negativo, e a direita de quem olha é o y negativo: u = −y, w = x (sem espelhar o perfil).
    """
    return (x, y) if horizontal == "x" else (-y, x)


def _na_secao(horizontal: str, u: float, w: float) -> Ponto:
    return (u, w) if horizontal == "x" else (w, -u)


def arestas_na_vista(forma: FormaDaSecao, horizontal: str) -> list[Aresta]:
    """As arestas verticais do perfil na vista frontal (``horizontal`` = "x") ou lateral ("y"),
    sem repetidas e na ordem da esquerda para a direita de quem olha.

    Uma aresta é vista quando, logo ao lado do canto que a gera, o raio até quem olha não passa
    pelo aço; senão fica tracejada (escondida).
    """
    xmin, xmax, ymin, ymax = forma.extremos()
    tamanho = max(xmax - xmin, ymax - ymin, 1.0)
    delta = 0.004 * tamanho
    passo = tamanho / 300.0
    cantos: list[Ponto] = [q for c in (*forma.cheios, *forma.vazados) for q in c]
    perto = (ymin if horizontal == "x" else xmin) - delta  # o lado de quem olha

    def livre(u: float, w: float) -> bool:
        # anda de (u, w) na direção de quem olha (w diminuindo) e vê se passa pelo aço
        andado = delta
        while w - andado > perto:
            if _material_em(forma, *_na_secao(horizontal, u, w - andado)):
                return False
            andado += passo
        return True

    achadas: dict[float, bool] = {}
    for x, y in cantos:
        u, w = na_vista(horizontal, x, y)
        vista = livre(u - delta, w) or livre(u + delta, w)
        chave = round(u, 3)
        achadas[chave] = achadas.get(chave, False) or vista
    for externo, interno in forma.aneis:
        for raio, vista in ((externo, True), (interno, False)):
            if raio > 0:
                for u in (-raio, raio):
                    chave = round(u, 3)
                    achadas[chave] = achadas.get(chave, False) or vista
    return [Aresta(u, v) for u, v in sorted(achadas.items())]


def _hachura(dr: ImageDraw.ImageDraw, a: Ponto, b: Ponto, lado: Ponto, cor: str) -> None:
    """Hachura de apoio ao longo de a–b, com os traços inclinados para ``lado``."""
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    passos = max(int(comprimento / (7 * ESC)), 2)
    for k in range(passos + 1):
        p = (a[0] + (b[0] - a[0]) * k / passos, a[1] + (b[1] - a[1]) * k / passos)
        dr.line(
            [p, (p[0] + lado[0] * 7 * ESC - 5 * ESC, p[1] + lado[1] * 7 * ESC)], fill=cor, width=ESC
        )


def _apoio(
    dr: ImageDraw.ImageDraw, centro: Ponto, meia_px: float, tipo: str, embaixo: bool
) -> None:
    """O símbolo do apoio na base (``embaixo``) ou no topo."""
    s = 1.0 if embaixo else -1.0  # para fora da coluna
    cx, cy = centro
    if tipo.startswith("pino"):
        altura, base = 16 * ESC, 13 * ESC
        triangulo = [(cx, cy), (cx - base, cy + s * altura), (cx + base, cy + s * altura)]
        dr.polygon(triangulo, fill="#ffffff", outline=dg.COR_LINHA, width=2 * ESC)
        y_chao = cy + s * altura
        dr.line(
            [(cx - base - 6 * ESC, y_chao), (cx + base + 6 * ESC, y_chao)],
            fill=dg.COR_LINHA,
            width=2 * ESC,
        )
        _hachura(
            dr, (cx - base - 4 * ESC, y_chao), (cx + base + 6 * ESC, y_chao), (0.0, s), dg.COR_LINHA
        )
    elif tipo.startswith("engaste"):
        meia = meia_px + 14 * ESC
        dr.line([(cx - meia, cy), (cx + meia, cy)], fill=dg.COR_LINHA, width=3 * ESC)
        _hachura(dr, (cx - meia + 2 * ESC, cy), (cx + meia, cy), (0.0, s), dg.COR_LINHA)
    if tipo.endswith("deslocável"):  # o topo anda de lado: seta dupla
        y = cy - s * 14 * ESC if not embaixo else cy
        esquerda, direita = (cx - meia_px - 30 * ESC, y), (cx - meia_px - 8 * ESC, y)
        dg.seta(dr, direita, esquerda, dg.COR_COTA, largura=ESC, ponta_px=7 * ESC)
        dg.seta(dr, esquerda, direita, dg.COR_COTA, largura=ESC, ponta_px=7 * ESC)


def _travamento(dr: ImageDraw.ImageDraw, ponto: Ponto, meia_px: float) -> None:
    """Travamento lateral no lado esquerdo da coluna: um traço até a coluna e a hachura."""
    x, y = ponto[0] - meia_px, ponto[1]
    fim = x - 22 * ESC
    dr.line([(fim, y), (x, y)], fill=_TRAVA, width=2 * ESC)
    dr.line([(fim, y - 8 * ESC), (fim, y + 8 * ESC)], fill=_TRAVA, width=2 * ESC)
    for k in range(-1, 2):
        dr.line(
            [(fim, y + k * 6 * ESC), (fim - 6 * ESC, y + k * 6 * ESC + 5 * ESC)],
            fill=_TRAVA,
            width=ESC,
        )


def _planta(
    dr: ImageDraw.ImageDraw, forma: FormaDaSecao, horizontal: str, centro: Ponto, lado_px: float
) -> None:
    """A seção vista de cima, pequena, como quem olha a vista a vê, e a seta de onde se olha."""
    pontos = [na_vista(horizontal, x, y) for c in forma.cheios for x, y in c] + [
        (s * r, t * r) for r, _ in forma.aneis for s in (-1, 1) for t in (-1, 1)
    ]
    if not pontos:
        return
    us, ws = [p[0] for p in pontos], [p[1] for p in pontos]
    esc = lado_px / max(max(us) - min(us), max(ws) - min(ws), 1e-6)
    uc, wc = (max(us) + min(us)) / 2, (max(ws) + min(ws)) / 2

    def px(u: float, w: float) -> Ponto:
        return (centro[0] + (u - uc) * esc, centro[1] - (w - wc) * esc)

    for contorno in forma.cheios:
        dr.polygon(
            [px(*na_vista(horizontal, x, y)) for x, y in contorno],
            fill=_ACO, outline=dg.COR_LINHA, width=ESC,
        )  # fmt: skip
    for contorno in forma.vazados:
        dr.polygon(
            [px(*na_vista(horizontal, x, y)) for x, y in contorno],
            fill="#ffffff", outline=dg.COR_LINHA, width=ESC,
        )  # fmt: skip
    g = px(0.0, 0.0)
    for externo, interno in forma.aneis:
        for raio, cor in ((externo, _ACO), (interno, "#ffffff")):
            if raio > 0:
                r = raio * esc
                dr.ellipse([g[0] - r, g[1] - r, g[0] + r, g[1] + r], fill=cor, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    dr.ellipse([g[0] - 2 * ESC, g[1] - 2 * ESC, g[0] + 2 * ESC, g[1] + 2 * ESC], fill=_EIXO)
    # os eixos da seção na planta, para saber qual é qual
    fonte = _fonte(10 * ESC)
    for nome, (dx, dy) in (("x", (1.0, 0.0)), ("y", (0.0, 1.0))):
        du, dw = na_vista(horizontal, dx, dy)
        ponta = (g[0] + du * (lado_px / 2 + 6 * ESC), g[1] - dw * (lado_px / 2 + 6 * ESC))
        dg.seta(dr, g, ponta, _EIXO, largura=ESC, ponta_px=6 * ESC)
        dg.rotulo(dr, ponta, (du, -dw), 3 * ESC, nome, _EIXO, fonte)
    # quem olha fica embaixo
    olho = (centro[0], centro[1] + lado_px / 2 + 22 * ESC)
    dg.seta(dr, olho, (olho[0], olho[1] - 12 * ESC), dg.COR_COTA, largura=2 * ESC, ponta_px=8 * ESC)


def _uma_vista(
    dr: ImageDraw.ImageDraw,
    c: ColunaEmPe,
    forma: FormaDaSecao,
    horizontal: str,
    centro_x: float,
    topo: float,
    altura_px: float,
    largura_util: float,
) -> tuple[float, bool]:
    """Desenha uma vista; devolve a escala vertical (px/mm) e se a largura foi aumentada."""
    fonte = _fonte(11 * ESC)
    esc_v = altura_px / c.comprimento_mm
    if forma.conhecida:
        arestas = arestas_na_vista(forma, horizontal)
    else:  # sem forma: a largura do retângulo de mesmo raio de giração
        r = c.secao.ry if horizontal == "x" else c.secao.rx
        meia = math.sqrt(3.0) * r
        arestas = [Aresta(-meia, True), Aresta(meia, True)]
    umin, umax = arestas[0].posicao, arestas[-1].posicao
    largura_mm = max(umax - umin, 1e-6)
    esc_h = esc_v
    aumentada = largura_mm * esc_h < _LARGURA_MINIMA_PX * ESC
    if aumentada:
        esc_h = _LARGURA_MINIMA_PX * ESC / largura_mm
    esc_h = min(esc_h, largura_util / largura_mm)
    base = topo + altura_px

    def px(u: float, z: float) -> Ponto:
        return (centro_x + u * esc_h, base - z * esc_v)

    meia_px = max(abs(umin), abs(umax)) * esc_h
    # ------------------------------------------------------------------ o perfil em pé
    dr.rectangle([px(umin, c.comprimento_mm), px(umax, 0.0)], fill=_ACO)
    for aresta in arestas:
        a, b = px(aresta.posicao, 0.0), px(aresta.posicao, c.comprimento_mm)
        if aresta.posicao in (umin, umax):
            dr.line([a, b], fill=dg.COR_LINHA, width=2 * ESC)
        elif aresta.vista:
            dr.line([a, b], fill=dg.COR_LINHA, width=ESC)
        else:
            dg.tracejado(dr, a, b, dg.COR_LINHA, largura=ESC, traco=5 * ESC)
    dr.line(
        [px(umin, c.comprimento_mm), px(umax, c.comprimento_mm)], fill=dg.COR_LINHA, width=2 * ESC
    )
    dr.line([px(umin, 0.0), px(umax, 0.0)], fill=dg.COR_LINHA, width=2 * ESC)
    dg.traco_ponto(dr, px(0.0, -0.04 * c.comprimento_mm), px(0.0, 1.04 * c.comprimento_mm), _EIXO)
    # ------------------------------------------------------------------ apoios e travamentos
    apoio = c.apoio_y if horizontal == "x" else c.apoio_x
    na_base, no_topo = APOIOS_NAS_PONTAS.get(apoio, ("pino", "pino"))
    _apoio(dr, px(0.0, 0.0), meia_px, na_base, True)
    _apoio(dr, px(0.0, c.comprimento_mm), meia_px, no_topo, False)
    destravado = c.ly_mm if horizontal == "x" else c.lx_mm
    if destravado > 0:
        z = destravado
        while z < c.comprimento_mm - 1e-6 and z > 0:
            _travamento(dr, px(0.0, z), meia_px)
            z += destravado
    # ------------------------------------------------------------------ a mão-francesa, no plano dela
    mf = c.mao_francesa
    plano_da_mf = mf is not None and (mf.eixo == "x") == (horizontal == "y")
    if mf is not None and plano_da_mf:
        theta = math.radians(mf.angulo_graus)
        no = px(umax, mf.altura_mm)
        comprimento = 0.30 * altura_px
        ponta = (no[0] + comprimento * math.sin(theta), no[1] - comprimento * math.cos(theta))
        dr.line([no, ponta], fill=dg.COR_LINHA, width=11 * ESC)
        dr.line([no, ponta], fill=_BARRA_MF, width=8 * ESC)
        normal = (math.cos(theta), math.sin(theta))  # para fora da barra, à direita
        inicio = dg.mais(
            (no[0] + 0.62 * (ponta[0] - no[0]), no[1] + 0.62 * (ponta[1] - no[1])), normal, 14 * ESC
        )
        fim = dg.mais(
            (no[0] + 0.22 * (ponta[0] - no[0]), no[1] + 0.22 * (ponta[1] - no[1])), normal, 14 * ESC
        )
        dg.seta(dr, inicio, fim, _FORCA, largura=2 * ESC, ponta_px=10 * ESC)
        dg.rotulo(dr, inicio, normal, 6 * ESC, "F", _FORCA, _fonte(12 * ESC), fundo=True)
        vertical = (0.0, -1.0)
        meio = dg.arco_entre(
            dr, no, 30 * ESC, vertical, (math.sin(theta), -math.cos(theta)), _FORCA
        )
        # o θ à direita do arco, sem cobrir a coluna
        dg.rotulo(
            dr, dg.mais(no, meio, 30 * ESC), (1.0, -0.15), 5 * ESC, f"θ = {_n(mf.angulo_graus)}°",
            _FORCA, fonte, fundo=True,
        )  # fmt: skip
        dr.ellipse(
            [no[0] - 4 * ESC, no[1] - 4 * ESC, no[0] + 4 * ESC, no[1] + 4 * ESC], fill=_FORCA
        )
        dg.cota_alinhada(
            dr, px(umax, 0.0), px(umax, mf.altura_mm), (1.0, 0.0), f"a = {_n(mf.altura_mm)}",
            16 * ESC, posicao=0.5, fundo=True,
        )  # fmt: skip
    return esc_v, aumentada


def _texto_do_apoio(apoio: str, k: float, destravado: float, eixo: str) -> list[str]:
    nome = apoio if apoio in APOIOS_NAS_PONTAS else "K informado"
    return [
        f"flexão em torno de {eixo}",
        nome,
        f"K_{eixo} = {k:.2f}".replace(".", ",") + f" · L_{eixo} = {_n(destravado)} mm",
    ]


def _legenda(dr: ImageDraw.ImageDraw, x: float, y: float, itens: Sequence[tuple[str, str]]) -> None:
    """Legenda com os símbolos desta figura: (forma, texto)."""
    fonte = _fonte(11 * ESC)
    passo = 24 * ESC
    for k, (forma, texto) in enumerate(itens):
        yy = y + k * passo
        x1, x2 = x, x + 26 * ESC
        cx = (x1 + x2) / 2
        if forma == "area":
            dr.rectangle(
                [x1 + 6 * ESC, yy - 9 * ESC, x2 - 6 * ESC, yy + 9 * ESC],
                fill=_ACO,
                outline=dg.COR_LINHA,
                width=2 * ESC,
            )
        elif forma == "vista":
            dr.line([(cx, yy - 9 * ESC), (cx, yy + 9 * ESC)], fill=dg.COR_LINHA, width=ESC)
        elif forma == "escondida":
            dg.tracejado(
                dr, (cx, yy - 9 * ESC), (cx, yy + 9 * ESC), dg.COR_LINHA, largura=ESC, traco=4 * ESC
            )
        elif forma == "eixo":
            dg.traco_ponto(dr, (x1, yy), (x2, yy), _EIXO, largura=2 * ESC)
        elif forma == "pino":
            _apoio(dr, (cx, yy - 8 * ESC), 0.0, "pino", True)
        elif forma == "engaste":
            _apoio(dr, (cx, yy - 2 * ESC), 6 * ESC, "engaste", True)
        elif forma == "trava":
            _travamento(dr, (x2 + 2 * ESC, yy), 0.0)
        elif forma == "mf":
            dr.line(
                [(x1 + 4 * ESC, yy + 7 * ESC), (x2 - 4 * ESC, yy - 7 * ESC)],
                fill=dg.COR_LINHA,
                width=9 * ESC,
            )
            dr.line(
                [(x1 + 4 * ESC, yy + 7 * ESC), (x2 - 4 * ESC, yy - 7 * ESC)],
                fill=_BARRA_MF,
                width=6 * ESC,
            )
        dr.text((x2 + 10 * ESC, yy), texto, fill=dg.COR_TEXTO, font=fonte, anchor="lm")


def figura_da_coluna(c: ColunaEmPe) -> ImagemDiagrama:
    """As duas vistas da coluna em pé, lado a lado, com a legenda."""
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    forma = forma_da_secao(c.secao)
    topo, altura_px = 196 * ESC, 340 * ESC
    vistas = (
        (
            "x",
            205 * ESC,
            "Vista frontal — plano x–z",
            _texto_do_apoio(c.apoio_y, c.ky, c.ly_mm, "y"),
        ),
        (
            "y",
            485 * ESC,
            "Vista lateral — plano y–z",
            _texto_do_apoio(c.apoio_x, c.kx, c.lx_mm, "x"),
        ),
    )
    fonte = _fonte(12 * ESC)
    pequena = _fonte(10 * ESC)
    aumentada = False
    for horizontal, centro_x, titulo, linhas in vistas:
        _, maior = _uma_vista(dr, c, forma, horizontal, centro_x, topo, altura_px, 150 * ESC)
        aumentada = aumentada or maior
        dr.text((centro_x, 64 * ESC), titulo, fill=dg.COR_TEXTO, font=fonte, anchor="mm")
        if forma.conhecida:
            _planta(dr, forma, horizontal, (centro_x, 126 * ESC), 44 * ESC)
        for k, linha in enumerate(linhas):
            dr.text(
                (centro_x, topo + altura_px + 38 * ESC + k * 16 * ESC),
                linha, fill=dg.COR_COTA, font=pequena, anchor="mm",
            )  # fmt: skip
    # a altura da coluna, à esquerda da primeira vista
    dg.cota_alinhada(
        dr, (88 * ESC, topo + altura_px), (88 * ESC, topo), (-1.0, 0.0),
        f"L = {_n(c.comprimento_mm)}", 0.0, posicao=0.5, fundo=True,
    )  # fmt: skip
    itens: list[tuple[str, str]] = [
        ("area", f"{c.secao.nome} em pé"),
        ("vista", "aresta vista"),
        ("escondida", "aresta escondida (atrás do aço)"),
        ("eixo", "eixo da coluna (por G)"),
        ("pino", "apoio de pino (impede o deslocamento)"),
        ("engaste", "engaste (impede também o giro)"),
        ("trava", "travamento lateral (a cada L destravado)"),
    ]
    if forma.conhecida:
        itens += [
            ("", "em cima de cada vista: a seção e, embaixo dela,"),
            ("", "a seta de onde se olha"),
        ]
    mf = c.mao_francesa
    if mf is not None:
        plano = "y–z (lateral)" if mf.eixo == "x" else "x–z (frontal)"
        itens += [
            ("mf", f"mão-francesa: F_Sd = {_n(mf.forca_kN, 1)} kN, θ = {_n(mf.angulo_graus)}°"),
            ("", f"nó a {_n(mf.altura_mm)} mm da base; flete o eixo {mf.eixo},"),
            ("", f"por isso está no plano {plano}"),
        ]
    if aumentada:
        itens.append(("", "largura do perfil aumentada para ser lida"))
    if not forma.conhecida:
        itens.append(("", "seção sem forma: largura do retângulo de mesmo r"))
    _legenda(dr, 650 * ESC, 96 * ESC, itens)
    titulo = f"Coluna em pé — {c.secao.nome}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        "As duas vistas da coluna, com os apoios, os travamentos e a mão-francesa. Cotas em mm.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"{c.secao.nome} em pé, L = {_n(c.comprimento_mm)} mm: vista frontal (plano x–z, "
        f"{c.apoio_y if c.apoio_y in APOIOS_NAS_PONTAS else 'K informado'}) e lateral "
        f"(plano y–z, {c.apoio_x if c.apoio_x in APOIOS_NAS_PONTAS else 'K informado'})"
        + (f"; mão-francesa a {_n(mf.altura_mm)} mm da base" if mf is not None else "")
        + "."
    )
    final = imagem.resize((_LARGURA_PX, _ALTURA_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, buffer.getvalue(), _LARGURA_PX, _ALTURA_PX)
