"""Como as figuras aparecem na tela: no tamanho em que foram desenhadas, nunca esticadas.

``width="stretch"`` encolhia o texto numa coluna estreita e inchava o desenho numa tela grande, e
figuras feitas com o mesmo tamanho de letra saíam, lado a lado, com letras diferentes. Aqui a figura
vale pelo tamanho de tela dela e só encolhe se a coluna for menor. As figuras vetoriais não têm
tamanho próprio: a largura sai da proporção, para não passarem da altura de uma tela.
"""

from __future__ import annotations

import io
import re
from typing import Any

import streamlit as st
from PIL import Image

from core.beam_charts import DPI_DE_TELA, ImagemDiagrama
from core.elementos_base import Figura as FiguraDoCaso

#: Largura de uma figura vetorial, em pixels, quando a altura deixa.
LARGURA_VETORIAL = 1000
#: Maior altura de uma figura vetorial: cabe numa tela comum sem rolar.
ALTURA_VETORIAL = 640

#: Para ``.properties(autosize=...)`` nos gráficos com legenda. No ajuste padrão, de largura e altura,
#: a legenda deixa o gráfico sem lugar para o eixo vertical: os números saem cortados e a área do
#: desenho fica esmagada. Ajustando só a largura, ``height`` vale para a área e o quadro cresce.
SO_NA_LARGURA = {"type": "fit-x", "contains": "padding"}

Figura = ImagemDiagrama | FiguraDoCaso | bytes | str

_VIEWBOX = re.compile(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)')


def largura_do_svg(svg: str) -> int:
    """A largura em pixels que faz o SVG caber em :data:`ALTURA_VETORIAL`."""
    achado = _VIEWBOX.search(svg)
    if achado is None:
        return LARGURA_VETORIAL
    largura, altura = float(achado.group(1)), float(achado.group(2))
    if largura <= 0 or altura <= 0:
        return LARGURA_VETORIAL
    return min(LARGURA_VETORIAL, round(ALTURA_VETORIAL * largura / altura))


def largura_do_png(png: bytes) -> int:
    """A largura de tela do PNG: o DPI gravado por :func:`core.beam_charts.figura_final`."""
    with Image.open(io.BytesIO(png)) as imagem:
        dpi = imagem.info.get("dpi", (DPI_DE_TELA, DPI_DE_TELA))[0] or DPI_DE_TELA
        return round(imagem.width * DPI_DE_TELA / dpi)


def mostrar_figura(
    figura: Figura,
    legenda: str | None = None,
    *,
    alvo: Any = None,
    largura: int | str | None = None,
) -> None:
    """Mostra um PNG, um SVG ou uma figura pronta, centralizados e no tamanho deles.

    Uma figura pronta (:class:`ImagemDiagrama` ou a ``Figura`` do Assistente) traz a própria legenda.
    ``largura`` é só para quem precisa de outro tamanho.
    """
    if isinstance(figura, bytes | str):
        imagem = figura
    else:
        imagem = figura.png
        legenda = figura.legenda if legenda is None else legenda
    if not imagem:
        return
    if largura is None:
        largura = largura_do_svg(imagem) if isinstance(imagem, str) else largura_do_png(imagem)
    lugar = st if alvo is None else alvo
    # O tamanho fica no bloco, não na imagem: com largura em pixels, o Streamlit reduz o arquivo para
    # essa largura no servidor e a figura perde o dobro de pixels.
    with lugar.container(horizontal_alignment="center"), st.container(width=largura):
        st.image(imagem, caption=legenda, width="stretch")
