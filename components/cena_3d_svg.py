"""A cena 3D (:mod:`core.cena_3d`) como SVG, para ``st.image`` nas páginas. Sem Streamlit."""

from __future__ import annotations

from components import desenho_svg as d
from core import cena_3d as c3


def svg_da_cena(desenho: c3.Desenho2D) -> str:
    largura, altura = desenho.largura, desenho.altura
    corpo: list[str] = []
    for item in desenho.itens:
        if isinstance(item, c3.Poligono2D):
            corpo.append(
                d.poligono(
                    item.pontos,
                    preenchimento=item.preenchimento,
                    contorno=item.contorno,
                    largura=item.largura,
                    opacidade=item.opacidade,
                )
            )
        elif isinstance(item, c3.Linha2D):
            corpo.append(
                d.linha(
                    *item.a,
                    *item.b,
                    cor=item.cor,
                    largura=item.largura,
                    tracejado=item.tracejado,
                    opacidade=item.opacidade,
                )
            )
        elif isinstance(item, c3.Seta2D) and item.larga:
            corpo.append(d.seta_de_vento(*item.a, *item.b, espessura=16, cor=item.cor))
        elif isinstance(item, c3.Seta2D):
            corpo.append(d.seta(*item.a, *item.b, cor=item.cor, largura=item.largura,
                                cabeca=item.cabeca))  # fmt: skip
        elif isinstance(item, c3.Etiqueta2D):
            if item.fundo:
                corpo.append(
                    d.etiqueta(
                        item.x,
                        item.y,
                        item.texto,
                        tamanho=item.tamanho,
                        cor=item.cor,
                        peso=item.peso,
                    )  # fmt: skip
                )
            else:
                corpo.append(d.texto(item.x, item.y, item.texto, tamanho=item.tamanho,
                                     cor=item.cor, peso=item.peso))  # fmt: skip
    # triedro com os eixos do SolidWorks
    origem = (58.0, altura - 58.0)
    for nome, (ux, uy) in desenho.eixos:
        fim = (origem[0] + 28 * ux, origem[1] + 28 * uy)
        corpo.append(d.seta(*origem, *fim, cor=d.COR_SUAVE, largura=1.4, cabeca=6))
        corpo.append(d.texto(fim[0] + 9 * ux, fim[1] + 9 * uy, nome, tamanho=10.5,
                             cor=d.COR_SUAVE, peso="bold"))  # fmt: skip
    if desenho.eixos:
        corpo.append(d.texto(22, altura - 16, "eixos do SolidWorks", tamanho=9.5, ancora="start",
                             cor=d.COR_SUAVE))  # fmt: skip
    if desenho.legenda:
        corpo.append(
            d.legenda(130, altura - 18, [(cor, "", texto) for cor, texto in desenho.legenda])
        )
    if desenho.escala is not None:
        e = desenho.escala
        corpo.append(
            d.escala_de_cor(
                largura - 270,
                altura - 44,
                230,
                e.minimo,
                e.maximo,
                e.unidade,
                titulo=e.titulo,
                escala=e.paleta,
            )  # fmt: skip
        )
    return d.documento(largura, altura, corpo, desenho.titulo or "Modelo em 3D",
                       subtitulo=desenho.subtitulo)  # fmt: skip
