"""A cena 3D (:mod:`core.cena_3d`) como PNG, pelo Pillow — para o memorial (PDF e Word), no mesmo
estilo do SVG das páginas. Sem Streamlit."""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw

from core import cena_3d as c3
from core.beam_charts import _fonte

FUNDO = (251, 251, 253)
COR_TEXTO = (31, 35, 40)


def _rgba(cor: str, opacidade: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = c3._rgb(cor)
    return (r, g, b, max(0, min(255, round(255 * opacidade))))


def png_da_cena(desenho: c3.Desenho2D, *, escala: float = 2.0) -> bytes:
    """O desenho em PNG, ``escala`` vezes o tamanho nominal (2 = boa leitura no A4)."""
    k = max(0.5, min(4.0, escala))
    largura, altura = round(desenho.largura * k), round(desenho.altura * k)
    # Imagem RGB e caneta RGBA: o Pillow mistura a transparência (numa RGBA ele substituiria).
    imagem = Image.new("RGB", (largura, altura), FUNDO)
    caneta = ImageDraw.Draw(imagem, "RGBA")

    def p(ponto: tuple[float, float]) -> tuple[float, float]:
        return (ponto[0] * k, ponto[1] * k)

    def texto(x: float, y: float, conteudo: str, tamanho: float, cor: str, negrito: bool = False,
              fundo: bool = False, ancora: str = "mm") -> None:  # fmt: skip
        del negrito  # a fonte do sistema não tem o negrito separado
        fonte = _fonte(max(8, round(tamanho * k)))
        if fundo:
            caixa = caneta.textbbox((x * k, y * k), conteudo, font=fonte, anchor=ancora)
            folga = 4 * k
            caneta.rounded_rectangle(
                (caixa[0] - folga, caixa[1] - folga / 2, caixa[2] + folga, caixa[3] + folga / 2),
                radius=6 * k,
                fill=(255, 255, 255, 235),
                outline=(229, 231, 235, 255),
            )
        caneta.text((x * k, y * k), conteudo, font=fonte, fill=_rgba(cor), anchor=ancora)

    def seta(a: tuple[float, float], b: tuple[float, float], cor: str, largura_px: float,
             cabeca: float) -> None:  # fmt: skip
        comprimento = math.dist(a, b)
        if comprimento <= 1e-9:
            return
        ux, uy = (b[0] - a[0]) / comprimento, (b[1] - a[1]) / comprimento
        cab = min(cabeca, comprimento * 0.6)
        bx, by = b[0] - cab * ux, b[1] - cab * uy
        meia = cab * 0.45
        caneta.line([p(a), p((bx, by))], fill=_rgba(cor), width=max(1, round(largura_px * k)))
        caneta.polygon(
            [p(b), p((bx - meia * uy, by + meia * ux)), p((bx + meia * uy, by - meia * ux))],
            fill=_rgba(cor),
        )

    for item in desenho.itens:
        if isinstance(item, c3.Poligono2D):
            pontos = [p(q) for q in item.pontos]
            if len(pontos) >= 3:
                caneta.polygon(pontos, fill=_rgba(item.preenchimento, item.opacidade),
                               outline=_rgba(item.contorno, min(1.0, item.opacidade + 0.2)))  # fmt: skip
        elif isinstance(item, c3.Linha2D):
            caneta.line([p(item.a), p(item.b)], fill=_rgba(item.cor, item.opacidade),
                        width=max(1, round(item.largura * k)))  # fmt: skip
        elif isinstance(item, c3.Seta2D):
            seta(item.a, item.b, item.cor, 6.0 if item.larga else item.largura,
                 26.0 if item.larga else item.cabeca)  # fmt: skip
        elif isinstance(item, c3.Etiqueta2D):
            texto(item.x, item.y, item.texto, item.tamanho, item.cor, item.peso == "bold",
                  item.fundo)  # fmt: skip
    origem = (58.0, desenho.altura - 58.0)
    for nome, (ux, uy) in desenho.eixos:
        fim = (origem[0] + 28 * ux, origem[1] + 28 * uy)
        seta(origem, fim, "#6b7280", 1.4, 6)
        texto(fim[0] + 9 * ux, fim[1] + 9 * uy, nome, 10.5, "#6b7280", True)
    if desenho.escala is not None:
        e = desenho.escala
        x0, y0, w = desenho.largura - 270, desenho.altura - 44, 230
        for i in range(48):
            cor = c3.cor_da_escala(i / 47, e.paleta)
            caneta.rectangle(
                (p((x0 + w * i / 48, y0))[0], p((0, y0))[1], p((x0 + w * (i + 1) / 48, 0))[0] + 1,
                 p((0, y0 + 9))[1]),
                fill=_rgba(cor),
            )  # fmt: skip
        texto(x0, y0 - 9, e.titulo, 10.5, "#6b7280", ancora="ls")
        texto(x0, y0 + 20, f"{e.minimo:.2f}".replace(".", ","), 10, "#6b7280", ancora="ls")
        texto(x0 + w, y0 + 20, f"{e.maximo:.2f} {e.unidade}".replace(".", ","), 10, "#6b7280",
              ancora="rs")  # fmt: skip
    x = 130.0
    for cor, rotulo in desenho.legenda:
        caneta.line([p((x, desenho.altura - 18)), p((x + 20, desenho.altura - 18))],
                    fill=_rgba(cor), width=max(1, round(3 * k)))  # fmt: skip
        texto(x + 26, desenho.altura - 18, rotulo, 11, "#6b7280", ancora="lm")
        x += 34 + 6.1 * len(rotulo)
    if desenho.titulo:
        texto(22, 24, desenho.titulo, 15, "#1f2328", True, ancora="lm")
    if desenho.subtitulo:
        texto(22, 44, desenho.subtitulo, 11, "#6b7280", ancora="lm")
    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()
