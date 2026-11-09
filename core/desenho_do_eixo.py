"""Desenho do eixo com trechos: os diâmetros em escala, os mancais, as forças e as seções conferidas.

O perfil sai das duas tabelas do bloco, e por isso muda na mesma hora que elas. A altura de cada
trecho segue a relação dele com d; com a resposta pronta, cada trecho ganha o diâmetro em milímetros.
A seção que manda fica em vermelho, as outras em cinza.
"""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core import elementos_eixos as ee
from core import montador_eixo as me
from core.beam_charts import ImagemDiagrama, _fonte, desenho_dispensado, figura_final

ESC = dg.ESC
_FUNDO = "#ffffff"
_TEXTO = "#172033"
_SUAVE = "#64748b"
_EIXO = "#e2e8f0"
_EIXO_LINHA = "#334155"
_MANCAL = "#0f766e"
_FORCA = "#b45309"
_HORIZONTAL = "#2563eb"
_SECAO = "#94a3b8"
_MANDA = "#c2415d"
_LARGURA = 820
_ESQUERDA = 60
_DIREITA = 760
_CENTRO = 170
_MEIA_ALTURA_MAXIMA = 46.0
_MEIA_ALTURA_MINIMA = 12.0


def _n(valor: float, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{valor:.0f}"
    return "0" if texto in ("-0", "") else texto.replace(".", ",")


def _texto(
    d: ImageDraw.ImageDraw,
    posicao: tuple[float, float],
    texto: str,
    *,
    cor: str = _TEXTO,
    tamanho: int = 12,
    ancora: str = "mm",
) -> None:
    d.text(
        (posicao[0] * ESC, posicao[1] * ESC),
        texto,
        fill=cor,
        font=_fonte(tamanho * ESC),
        anchor=ancora,
    )


def _linha(
    d: ImageDraw.ImageDraw,
    pontos: Sequence[tuple[float, float]],
    cor: str,
    largura: float = 1.5,
) -> None:
    d.line([(x * ESC, y * ESC) for x, y in pontos], fill=cor, width=max(1, round(largura * ESC)))


def _tracejada(d: ImageDraw.ImageDraw, x: float, y0: float, y1: float, cor: str) -> None:
    y = y0
    while y < y1:
        _linha(d, ((x, y), (x, min(y + 5, y1))), cor, 1.2)
        y += 9


def _seta_vertical(d: ImageDraw.ImageDraw, x: float, ponta: float, para_baixo: bool) -> None:
    comprimento = 44
    inicio = ponta - comprimento if para_baixo else ponta + comprimento
    _linha(d, ((x, inicio), (x, ponta)), _FORCA, 2.2)
    sentido = 1 if para_baixo else -1
    cabeca = [(x, ponta), (x - 6, ponta - 11 * sentido), (x + 6, ponta - 11 * sentido)]
    d.polygon([(a * ESC, b * ESC) for a, b in cabeca], fill=_FORCA)


def _horizontal(d: ImageDraw.ImageDraw, x: float, y: float, saindo: bool) -> None:
    """Força no outro plano, de frente: ponto saindo do papel, xis entrando."""
    raio = 8
    caixa = [(x - raio) * ESC, (y - raio) * ESC, (x + raio) * ESC, (y + raio) * ESC]
    d.ellipse(caixa, outline=_HORIZONTAL, width=round(1.8 * ESC), fill=_FUNDO)
    if saindo:
        d.ellipse(
            [(x - 2.4) * ESC, (y - 2.4) * ESC, (x + 2.4) * ESC, (y + 2.4) * ESC], fill=_HORIZONTAL
        )
    else:
        _linha(d, ((x - 4.5, y - 4.5), (x + 4.5, y + 4.5)), _HORIZONTAL, 1.8)
        _linha(d, ((x - 4.5, y + 4.5), (x + 4.5, y - 4.5)), _HORIZONTAL, 1.8)


def desenhar_eixo(
    arranjo: me.Arranjo,
    secoes: Sequence[me.Secao] = (),
    *,
    d: float | None = None,
    manda: str | None = None,
    comprimento: tuple[str, float] = ("mm", 1.0),
    medida: tuple[str, float] = ("mm", 1.0),
) -> ImagemDiagrama:
    """``comprimento`` e ``medida``: rótulo e fator da unidade da tela, como em ``Unidades.par``."""
    titulo = "Eixo com trechos"
    legenda = (
        "Diâmetros em escala com a relação de cada trecho. Setas laranja: força no plano vertical; "
        "círculos azuis: força no plano horizontal, saindo (ponto) ou entrando (xis). Em vermelho, a "
        "seção que manda."
    )
    if desenho_dispensado() or not arranjo.trechos or arranjo.comprimento <= 0:
        return ImagemDiagrama(titulo, legenda, b"", 0, 0)
    altura = 360
    imagem = Image.new("RGB", (_LARGURA * ESC, altura * ESC), _FUNDO)
    desenho = ImageDraw.Draw(imagem)
    total = arranjo.comprimento
    escala = (_DIREITA - _ESQUERDA) / total
    maior = max(t.relacao for t in arranjo.trechos)
    rotulo_c, fator_c = comprimento
    rotulo_m, fator_m = medida

    def px(x: float) -> float:
        return _ESQUERDA + x * escala

    def meia(relacao: float) -> float:
        return max(_MEIA_ALTURA_MINIMA, _MEIA_ALTURA_MAXIMA * relacao / maior)

    # Perfil do eixo e as cotas de cada trecho embaixo. A linha de centro fica por baixo do eixo.
    _linha(desenho, ((_ESQUERDA - 14, _CENTRO), (_DIREITA + 14, _CENTRO)), _SUAVE, 0.8)
    for (x0, x1), trecho in zip(arranjo.bordas(), arranjo.trechos, strict=True):
        h = meia(trecho.relacao)
        caixa = [px(x0) * ESC, (_CENTRO - h) * ESC, px(x1) * ESC, (_CENTRO + h) * ESC]
        desenho.rectangle(caixa, fill=_EIXO, outline=_EIXO_LINHA, width=round(1.4 * ESC))
        if trecho.entalhe == ee.ENTALHE_CHAVETA:
            largura = min(px(x1) - px(x0) - 6, 0.7 * (px(x1) - px(x0)))
            meio = (px(x0) + px(x1)) / 2
            desenho.rectangle(
                [
                    (meio - largura / 2) * ESC,
                    (_CENTRO - h) * ESC,
                    (meio + largura / 2) * ESC,
                    (_CENTRO - h + 5) * ESC,
                ],
                fill=_SUAVE,
            )
        diametro = f"{_n(trecho.relacao, 2)}·d"
        if d is not None:
            diametro = f"{_n(trecho.relacao * d / fator_m, 1)} {rotulo_m}"
        if px(x1) - px(x0) >= 34:
            _texto(desenho, ((px(x0) + px(x1)) / 2, _CENTRO), diametro, tamanho=10)
        y_cota = _CENTRO + _MEIA_ALTURA_MAXIMA + 66
        _linha(desenho, ((px(x0), y_cota - 5), (px(x0), y_cota + 5)), _SUAVE, 1.0)
        _linha(desenho, ((px(x1), y_cota - 5), (px(x1), y_cota + 5)), _SUAVE, 1.0)
        _linha(desenho, ((px(x0), y_cota), (px(x1), y_cota)), _SUAVE, 1.0)
        if px(x1) - px(x0) >= 30:
            _texto(
                desenho,
                ((px(x0) + px(x1)) / 2, y_cota + 12),
                _n(trecho.comprimento / fator_c, 3 if fator_c >= 100 else 1),
                cor=_SUAVE,
                tamanho=10,
            )
    _texto(
        desenho,
        (_DIREITA + 16, _CENTRO + _MEIA_ALTURA_MAXIMA + 66),
        rotulo_c,
        cor=_SUAVE,
        tamanho=10,
        ancora="lm",
    )

    # Mancais embaixo e cargas em cima.
    for elemento in arranjo.elementos:
        x = px(elemento.x)
        h = meia(me.relacao_em(arranjo, elemento.x))
        if elemento.funcao in (me.MANCAL_A, me.MANCAL_B):
            base = _CENTRO + h
            triangulo = [(x, base), (x - 11, base + 18), (x + 11, base + 18)]
            desenho.polygon([(a * ESC, b * ESC) for a, b in triangulo], fill=_MANCAL)
            _texto(desenho, (x, base + 30), elemento.funcao[-1], cor=_MANCAL, tamanho=12)
            continue
        topo = _CENTRO - h
        if elemento.vertical != me.NENHUMA:
            _seta_vertical(desenho, x, topo - 2, elemento.vertical == me.MAIS)
        if elemento.horizontal != me.NENHUMA:
            _horizontal(desenho, x + 16, topo - 26, elemento.horizontal == me.MAIS)
        rotulo = elemento.nome
        if elemento.torque == me.ENTRA:
            rotulo += " · T entra"
        elif elemento.torque == me.SAI:
            rotulo += " · T sai"
        _texto(desenho, (x, topo - 58), rotulo, tamanho=11)

    # Seções conferidas, com a que manda em destaque. Os dois lados de um ponto ficam numa linha só.
    no_ponto: dict[float, list[str]] = {}
    for secao in secoes:
        no_ponto.setdefault(round(secao.x, 6), []).append(secao.rotulo)
    for x_mm, rotulos in no_ponto.items():
        x = px(x_mm)
        cor = _MANDA if manda in rotulos else _SECAO
        _tracejada(
            desenho, x, _CENTRO - _MEIA_ALTURA_MAXIMA - 4, _CENTRO + _MEIA_ALTURA_MAXIMA + 34, cor
        )
        _texto(
            desenho, (x, _CENTRO + _MEIA_ALTURA_MAXIMA + 44), "/".join(rotulos), cor=cor, tamanho=10
        )
    return figura_final(imagem, titulo, legenda)
