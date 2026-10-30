"""Desenho 2D que gira: a tela (mm → px, com giro), texto de pé, cotas alinhadas, setas e eixos.

Usado pelos desenhos das ligações soldadas (:mod:`core.ligacoes`, :mod:`core.ligacoes_soldadas`)
e pelo desenho da seção da coluna (:mod:`core.desenho_da_secao`). O giro é só do desenho:
anti-horário para valores positivos. O texto fica sempre de pé, com a âncora escolhida pelo lado
para onde ele sai, e as cotas acompanham a peça. As medidas em px já estão na escala ``ESC`` (o
desenho é feito no dobro do tamanho e reduzido no fim, para sair liso).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from PIL import ImageDraw

from core.beam_charts import _fonte

ESC = 2
COR_COTA = "#475569"
COR_LINHA = "#1e293b"
COR_TEXTO = "#0f172a"

Ponto = tuple[float, float]


def angulo_do_giro(giro_graus: float) -> float:
    """O giro do desenho levado a (−180°, 180°]."""
    giro = math.fmod(float(giro_graus), 360.0)
    if giro > 180.0:
        giro -= 360.0
    elif giro <= -180.0:
        giro += 360.0
    return giro


def texto_do_giro(giro_graus: float) -> str:
    """O giro para a legenda: "45° no sentido anti-horário"."""
    giro = angulo_do_giro(giro_graus)
    graus = f"{abs(giro):.0f}"
    return f"{graus}° no sentido {'anti-horário' if giro > 0 else 'horário'}"


class Tela:
    """Leva pontos em mm (x para a direita, y para baixo) para a área de desenho, em px.

    ``giro_graus`` gira o desenho em torno dele mesmo, no sentido anti-horário (horário se
    negativo); a escala é a que faz o desenho já girado caber na área. O texto não gira: quem
    escreve usa :func:`rotulo`, que põe o texto de pé do lado certo.
    """

    def __init__(
        self,
        pontos: Sequence[Ponto],
        caixa: tuple[int, int, int, int],
        giro_graus: float = 0.0,
    ) -> None:
        giro = math.radians(giro_graus)
        self._cos, self._sin = math.cos(giro), math.sin(giro)
        girados = [self._girar(x, y) for x, y in pontos]
        x0, y0, x1, y1 = caixa
        xs, ys = [p[0] for p in girados], [p[1] for p in girados]
        largura, altura = max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0)
        self.esc = min((x1 - x0) / largura, (y1 - y0) / altura) * ESC
        self.ox = x0 * ESC + ((x1 - x0) * ESC - largura * self.esc) / 2 - min(xs) * self.esc
        self.oy = y0 * ESC + ((y1 - y0) * ESC - altura * self.esc) / 2 - min(ys) * self.esc

    def _girar(self, x: float, y: float) -> Ponto:
        # anti-horário na tela, onde y cresce para baixo
        return (x * self._cos + y * self._sin, -x * self._sin + y * self._cos)

    def __call__(self, x: float, y: float) -> Ponto:
        gx, gy = self._girar(x, y)
        return (self.ox + gx * self.esc, self.oy + gy * self.esc)

    def direcao(self, dx: float, dy: float) -> Ponto:
        """A direção (dx, dy) do desenho em mm, já girada, com comprimento 1 (px)."""
        gx, gy = self._girar(dx, dy)
        comprimento = math.hypot(gx, gy) or 1.0
        return (gx / comprimento, gy / comprimento)


def mais(ponto: Ponto, direcao: Ponto, distancia_px: float) -> Ponto:
    """O ponto a ``distancia_px`` de ``ponto`` na direção dada (px; a direção é normalizada)."""
    comprimento = math.hypot(*direcao) or 1.0
    return (
        ponto[0] + direcao[0] / comprimento * distancia_px,
        ponto[1] + direcao[1] / comprimento * distancia_px,
    )


def ancora(direcao: Ponto, *, varias_linhas: bool = False) -> str:
    """A âncora do PIL para um texto que sai do ponto na direção dada (px, y para baixo)."""
    dx, dy = direcao
    comprimento = math.hypot(dx, dy) or 1.0
    dx, dy = dx / comprimento, dy / comprimento
    horizontal = "l" if dx > 0.38 else ("r" if dx < -0.38 else "m")
    vertical = "t" if dy > 0.38 else ("b" if dy < -0.38 else "m")
    if varias_linhas:  # o PIL não aceita "t" e "b" em texto de várias linhas
        vertical = {"t": "a", "b": "d"}.get(vertical, vertical)
    return horizontal + vertical


def rotulo(
    d: ImageDraw.ImageDraw,
    ponto: Ponto,
    direcao: Ponto,
    distancia_px: float,
    texto: str,
    cor: str,
    fonte: Any,
    *,
    fundo: bool = False,
) -> None:
    """Texto de pé a ``distancia_px`` do ponto, todo do lado da direção dada (não cobre o ponto).

    Com ``fundo``, um retângulo branco atrás do texto esconde as linhas que passam por ali.
    """
    lugar = mais(ponto, direcao, distancia_px)
    a = ancora(direcao, varias_linhas="\n" in texto)
    if fundo:
        x0, y0, x1, y1 = d.textbbox(lugar, texto, font=fonte, anchor=a)
        folga = 2 * ESC
        d.rectangle([x0 - folga, y0 - folga, x1 + folga, y1 + folga], fill="#ffffff")
    d.text(lugar, texto, fill=cor, font=fonte, anchor=a)


def cota_alinhada(
    d: ImageDraw.ImageDraw,
    a: Ponto,
    b: Ponto,
    lado: Ponto,
    texto: str,
    afastamento_px: float = 0.0,
    *,
    cor: str = COR_COTA,
    posicao: float = 0.5,
    fundo: bool = False,
) -> None:
    """Cota de a até b (px), afastada para ``lado`` (direção px), com o texto de pé por fora.

    ``posicao`` diz onde o texto fica ao longo da cota (0 em a, 1 em b); ``fundo`` põe um
    retângulo branco atrás dele (para não brigar com eixos que cruzem a cota).
    """
    a2, b2 = mais(a, lado, afastamento_px), mais(b, lado, afastamento_px)
    if afastamento_px > 0:  # linhas de chamada da cota
        for p, q in ((a, a2), (b, b2)):
            d.line([p, mais(q, lado, 4 * ESC)], fill=cor, width=1)
    d.line([a2, b2], fill=cor, width=ESC)
    for p in (a2, b2):
        d.line([mais(p, lado, -5 * ESC), mais(p, lado, 5 * ESC)], fill=cor, width=ESC)
    lugar = (a2[0] + (b2[0] - a2[0]) * posicao, a2[1] + (b2[1] - a2[1]) * posicao)
    rotulo(d, lugar, lado, 7 * ESC, texto, cor, _fonte(11 * ESC), fundo=fundo)


def dentro(ponto: Ponto, poligono: Sequence[Ponto]) -> bool:
    """O ponto está dentro do polígono (px)? Pelo número de cruzamentos de um raio."""
    x, y = ponto
    achou = False
    for i in range(len(poligono)):
        (x1, y1), (x2, y2) = poligono[i], poligono[i - 1]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            achou = not achou
    return achou


def fora_de(
    ponto: Ponto,
    direcao: Ponto,
    obstaculos: Sequence[Sequence[Ponto]],
    distancia_px: float,
) -> Ponto:
    """Andando de ``ponto`` na direção dada, o lugar a ``distancia_px`` depois de sair das peças.

    Serve para as chamadas numeradas: o círculo fica logo fora da chapa (e do apoio), qualquer
    que seja o giro do desenho.
    """
    andado = 0.0
    while andado < 3000 * ESC and any(
        dentro(mais(ponto, direcao, andado), poligono) for poligono in obstaculos
    ):
        andado += 3 * ESC
    return mais(ponto, direcao, andado + distancia_px)


def traco_ponto(d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, cor: str, largura: int = ESC) -> None:
    """Linha de traço e ponto (eixo) de a até b (px)."""
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    if comprimento <= 0:
        return
    direcao = (b[0] - a[0], b[1] - a[1])
    padrao = ((16, True), (4, False), (3, True), (4, False))
    andado, k = 0.0, 0
    while andado < comprimento:
        passo, desenha = padrao[k % len(padrao)]
        fim = min(andado + passo * ESC, comprimento)
        if desenha:
            d.line([mais(a, direcao, andado), mais(a, direcao, fim)], fill=cor, width=largura)
        andado, k = fim, k + 1


def arco_entre(
    d: ImageDraw.ImageDraw, centro: Ponto, raio: float, d1: Ponto, d2: Ponto, cor: str
) -> Ponto:
    """O menor arco entre as direções d1 e d2 (px); devolve a direção do meio dele."""
    a1 = math.degrees(math.atan2(d1[1], d1[0]))
    a2 = math.degrees(math.atan2(d2[1], d2[0]))
    varre = (a2 - a1) % 360.0
    if varre > 180.0:
        a1, varre = a2, 360.0 - varre
    cx, cy = centro
    d.arc([cx - raio, cy - raio, cx + raio, cy + raio], a1, a1 + varre, fill=cor, width=2 * ESC)
    meio = math.radians(a1 + varre / 2)
    return (math.cos(meio), math.sin(meio))


def seta(
    d: ImageDraw.ImageDraw,
    a: Ponto,
    b: Ponto,
    cor: str,
    *,
    largura: int = 3 * ESC,
    ponta_px: float = 13 * ESC,
) -> None:
    """Seta de a para b (px), com a ponta cheia."""
    d.line([a, b], fill=cor, width=largura)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    d.polygon(
        [
            b,
            (b[0] - ponta_px * math.cos(ang - 0.4), b[1] - ponta_px * math.sin(ang - 0.4)),
            (b[0] - ponta_px * math.cos(ang + 0.4), b[1] - ponta_px * math.sin(ang + 0.4)),
        ],
        fill=cor,
    )


def eixos_da_peca(
    d: ImageDraw.ImageDraw, origem: Ponto, tela: Tela, nomes: tuple[str, str] = ("x", "y")
) -> None:
    """Os eixos x e y da peça num canto, para ler as direções quando o desenho está girado."""
    fonte = _fonte(11 * ESC)
    for nome, direcao in ((nomes[0], tela.direcao(1.0, 0.0)), (nomes[1], tela.direcao(0.0, -1.0))):
        ponta = mais(origem, direcao, 30 * ESC)
        seta(d, origem, ponta, COR_COTA, largura=2 * ESC, ponta_px=9 * ESC)
        rotulo(d, ponta, direcao, 4 * ESC, nome, COR_COTA, fonte)


def tracejado(
    d: ImageDraw.ImageDraw,
    a: tuple[float, float],
    b: tuple[float, float],
    cor: str,
    largura: int = 2 * ESC,
    traco: float = 9 * ESC,
) -> None:
    """Linha tracejada de a até b (px)."""
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    if comprimento <= 0:
        return
    ux, uy = (b[0] - a[0]) / comprimento, (b[1] - a[1]) / comprimento
    s = 0.0
    while s < comprimento:
        fim = min(s + traco, comprimento)
        d.line(
            [(a[0] + ux * s, a[1] + uy * s), (a[0] + ux * fim, a[1] + uy * fim)],
            fill=cor,
            width=largura,
        )
        s += 2 * traco


def legenda(
    d: ImageDraw.ImageDraw, x: float, y: float, itens: Sequence[tuple[str, str, str]]
) -> None:
    """Quadro de legenda a partir de (x, y) px: cada item é (forma, cor, texto).

    Formas: "linha" (cordão de solda), "area" (chapa, barra, apoio), "tracejado" (seção de
    Whitmore), "eixo" (traço e ponto), "seta" (força), "ponto" (centro geométrico) e
    "numero:<n>" (chamada do desenho).
    """
    fonte = _fonte(11 * ESC)
    passo = 22 * ESC
    for k, (forma, cor, texto) in enumerate(itens):
        yy = y + k * passo
        x1, x2 = x, x + 26 * ESC
        if forma == "linha":
            d.line([(x1, yy), (x2, yy)], fill=cor, width=6 * ESC)
        elif forma == "area":
            d.rectangle(
                [x1, yy - 7 * ESC, x2, yy + 7 * ESC], fill=cor, outline=COR_LINHA, width=ESC
            )
        elif forma == "tracejado":
            tracejado(d, (x1, yy), (x2, yy), cor, traco=5 * ESC)
        elif forma == "eixo":
            traco_ponto(d, (x1, yy), (x2, yy), cor, largura=2 * ESC)
        elif forma == "seta":
            d.line([(x1, yy), (x2 - 4 * ESC, yy)], fill=cor, width=3 * ESC)
            d.polygon(
                [(x2, yy), (x2 - 9 * ESC, yy - 5 * ESC), (x2 - 9 * ESC, yy + 5 * ESC)], fill=cor
            )
        elif forma == "ponto":
            cx = (x1 + x2) / 2
            d.ellipse(
                [cx - 6 * ESC, yy - 6 * ESC, cx + 6 * ESC, yy + 6 * ESC],
                outline=cor,
                width=2 * ESC,
            )
            d.line([(cx - 9 * ESC, yy), (cx + 9 * ESC, yy)], fill=cor, width=ESC)
            d.line([(cx, yy - 9 * ESC), (cx, yy + 9 * ESC)], fill=cor, width=ESC)
        elif forma.startswith("numero:"):
            cx, raio = (x1 + x2) / 2, 10 * ESC
            d.ellipse(
                [cx - raio, yy - raio, cx + raio, yy + raio],
                fill="#ffffff",
                outline=cor,
                width=2 * ESC,
            )
            d.text((cx, yy), forma.split(":", 1)[1], fill=cor, font=_fonte(12 * ESC), anchor="mm")
        d.text((x2 + 8 * ESC, yy), texto, fill=COR_TEXTO, font=fonte, anchor="lm")
