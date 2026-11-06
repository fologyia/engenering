"""Desenhos dos pinos e parafusos, com os números do cálculo: mudam com o caso e com os planos.

O corte mostra as chapas na escala do comprimento do pino, para cima as que puxam para um lado e
para baixo as que puxam para o outro. Embaixo, os diagramas de cortante e de momento ficam alinhados
com o pino, para se ver em que chapa está cada pico.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, desenho_dispensado, figura_final
from core.esforcos_no_pino import Chapa, Diagrama, PinoEmBalanco, planos_de_corte

ESC = dg.ESC
_FUNDO = "#ffffff"
_TEXTO = "#172033"
_CHAPA_A = "#cbd5e1"
_CHAPA_B = "#bfdbfe"
_LINHA = "#334155"
_PINO = "#fde7cf"
_PINO_LINHA = "#b45309"
_FORCA = "#b45309"
_CORTE = "#c2415d"
_CORTANTE = "#2563eb"
_MOMENTO = "#c2415d"
_BLOCO = "#e2e8f0"
_PRESSAO = "#0f766e"

_LARGURA = 600
_ESQUERDA = 70
_DIREITA = 530


def _n(valor: float, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{valor:.0f}"
    return "0" if texto in ("-0", "") else texto.replace(".", ",")


def _forca_kN(valor_N: float) -> str:
    return f"{_n(abs(valor_N) / 1000.0, 2)} kN"


def _momento_Nm(valor_Nmm: float) -> str:
    return f"{_n(abs(valor_Nmm) / 1000.0, 1)} N·m"


def _quadro(altura: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    imagem = Image.new("RGB", (_LARGURA * ESC, altura * ESC), _FUNDO)
    return imagem, ImageDraw.Draw(imagem)


def _texto(
    d: ImageDraw.ImageDraw,
    posicao: tuple[float, float],
    texto: str,
    *,
    cor: str = _TEXTO,
    tamanho: int = 12,
    ancora: str = "mm",
) -> None:
    d.text(posicao, texto, fill=cor, font=_fonte(tamanho * ESC), anchor=ancora)


def _diagrama(
    d: ImageDraw.ImageDraw,
    px: list[float],
    valores: Sequence[float],
    y_base: float,
    cor: str,
    rotulo: str,
    texto_max: str,
    meia_altura: float = 36 * ESC,
) -> None:
    """Um diagrama alinhado ao pino: área, linha, nome à esquerda e o valor no pico."""
    maior = max(abs(v) for v in valores) or 1.0
    pontos = [(x, y_base - v / maior * meia_altura) for x, v in zip(px, valores, strict=True)]
    d.polygon([(px[0], y_base), *pontos, (px[-1], y_base)], fill=_claro(cor))
    d.line(pontos, fill=cor, width=2 * ESC, joint="curve")
    d.line([(px[0], y_base), (px[-1], y_base)], fill="#94a3b8", width=ESC)
    _texto(d, (px[0] - 12 * ESC, y_base), rotulo, cor=cor, tamanho=13, ancora="rm")
    x_pico, y_pico = max(pontos, key=lambda p: abs(p[1] - y_base))
    acima = y_pico <= y_base
    limite_x = (px[0] + 34 * ESC, px[-1] - 34 * ESC)
    _texto(
        d,
        (min(max(x_pico, limite_x[0]), limite_x[1]), y_pico + (-9 if acima else 9) * ESC),
        texto_max,
        cor=cor,
        tamanho=11,
    )


def _claro(cor: str, fracao: float = 0.82) -> str:
    """A cor misturada com branco: a área do diagrama não pode brigar com a linha."""
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c + (255 - c) * fracao):02x}" for c in (r, g, b))


def _extremos_do_pino(
    d: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    y: float,
    meia: float,
    *,
    parafuso: bool,
) -> None:
    """Cabeça e porca, no parafuso; no pino, a ponta chanfrada."""
    if parafuso:
        for inicio, fim in ((x0 - 13 * ESC, x0), (x1, x1 + 13 * ESC)):
            d.rectangle(
                [inicio, y - 1.8 * meia, fim, y + 1.8 * meia],
                fill="#e5e7eb",
                outline=_LINHA,
                width=2 * ESC,
            )


def figura_das_chapas(
    chapas: Sequence[Chapa],
    diagrama: Diagrama,
    d_mm: float,
    *,
    parafuso: bool = False,
    vazado: bool = False,
    rosca_no_corte: bool = False,
    titulo: str = "Pino nas chapas",
    legenda: str = "",
) -> ImagemDiagrama:
    """As chapas, o pino, os planos de corte e os diagramas de cortante e momento."""
    if desenho_dispensado():
        return ImagemDiagrama(titulo, legenda, b"", 0, 0)
    imagem, d = _quadro(430)
    comprimento = chapas[-1].fim - chapas[0].inicio
    escala = (_DIREITA - _ESQUERDA) * ESC / comprimento

    def px(x_mm: float) -> float:
        return _ESQUERDA * ESC + (x_mm - chapas[0].inicio) * escala

    y = 132 * ESC
    meia = min(max(d_mm / 2.0 * escala, 7 * ESC), 22 * ESC)
    fundo, topo = 78 * ESC, 78 * ESC
    entrada = 30 * ESC
    for chapa in chapas:
        puxa_para_cima = chapa.forca > 0
        cor = _CHAPA_A if puxa_para_cima else _CHAPA_B
        y0 = y - topo if puxa_para_cima else y - entrada
        y1 = y + entrada if puxa_para_cima else y + fundo
        d.rectangle(
            [px(chapa.inicio), y0, px(chapa.fim), y1], fill=cor, outline=_LINHA, width=2 * ESC
        )
        x_meio = px(chapa.inicio + chapa.espessura / 2.0)
        if puxa_para_cima:
            dg.seta(
                d, (x_meio, y0), (x_meio, y0 - 22 * ESC), _FORCA, largura=2 * ESC, ponta_px=9 * ESC
            )
            _texto(d, (x_meio, y0 - 32 * ESC), _forca_kN(chapa.forca), cor=_FORCA, tamanho=11)
        else:
            dg.seta(
                d, (x_meio, y1), (x_meio, y1 + 22 * ESC), _FORCA, largura=2 * ESC, ponta_px=9 * ESC
            )
            _texto(d, (x_meio, y1 + 32 * ESC), _forca_kN(chapa.forca), cor=_FORCA, tamanho=11)

    x_ini, x_fim = px(chapas[0].inicio) - 14 * ESC, px(chapas[-1].fim) + 14 * ESC
    d.rectangle([x_ini, y - meia, x_fim, y + meia], fill=_PINO, outline=_PINO_LINHA, width=2 * ESC)
    if vazado:
        dg.tracejado(
            d,
            (x_ini, y - meia * 0.5),
            (x_fim, y - meia * 0.5),
            _PINO_LINHA,
            largura=ESC,
            traco=4 * ESC,
        )
        dg.tracejado(
            d,
            (x_ini, y + meia * 0.5),
            (x_fim, y + meia * 0.5),
            _PINO_LINHA,
            largura=ESC,
            traco=4 * ESC,
        )
    if rosca_no_corte:
        x = (x_ini + x_fim) / 2.0
        while x < x_fim:
            d.line([(x, y - meia), (x + 3 * ESC, y + meia)], fill=_PINO_LINHA, width=ESC)
            x += 6 * ESC
    _extremos_do_pino(d, x_ini, x_fim, y, meia, parafuso=parafuso)

    for numero, x_mm in enumerate(planos_de_corte(chapas), start=1):
        x = px(x_mm)
        dg.tracejado(
            d,
            (x, y - meia - 13 * ESC),
            (x, y + meia + 13 * ESC),
            _CORTE,
            largura=2 * ESC,
            traco=4 * ESC,
        )
        raio = 8 * ESC
        d.ellipse([x - raio, y - raio, x + raio, y + raio], fill=_CORTE)
        _texto(d, (x, y), str(numero), cor="#ffffff", tamanho=10)

    xs = [px(valor) for valor in diagrama.x]
    _diagrama(
        d,
        xs,
        diagrama.cortante,
        284 * ESC,
        _CORTANTE,
        "V",
        f"V = {_forca_kN(diagrama.cortante_max)}",
    )
    _diagrama(
        d,
        xs,
        diagrama.momento,
        370 * ESC,
        _MOMENTO,
        "M",
        f"M = {_momento_Nm(diagrama.momento_max)}",
    )
    return figura_final(imagem, titulo, legenda)


def figura_do_balanco(
    pino: PinoEmBalanco, t_chapa: float, *, titulo: str, legenda: str
) -> ImagemDiagrama:
    """O pino preso no bloco, a chapa que carrega, a pressão no furo e os diagramas."""
    if desenho_dispensado():
        return ImagemDiagrama(titulo, legenda, b"", 0, 0)
    imagem, d = _quadro(430)
    diagrama = pino.diagrama()
    meia_chapa = t_chapa / 2.0
    comprimento = meia_chapa + pino.braco + pino.engaste
    escala = (_DIREITA - _ESQUERDA) * ESC / comprimento

    def px(x_mm: float) -> float:
        """x vale zero na linha da força e cresce para dentro do bloco."""
        return _ESQUERDA * ESC + (x_mm + meia_chapa) * escala

    y = 132 * ESC
    meia = min(max(pino.d / 2.0 * escala, 7 * ESC), 26 * ESC)
    face = px(pino.braco)
    fim = px(pino.braco + pino.engaste)
    d.rectangle(
        [face, y - 74 * ESC, fim + 14 * ESC, y + 74 * ESC],
        fill=_BLOCO,
        outline=_LINHA,
        width=2 * ESC,
    )
    passo = 12 * ESC
    hachura = face
    while hachura < fim + 14 * ESC:
        d.line(
            [(hachura, y - 74 * ESC), (min(hachura + 8 * ESC, fim + 14 * ESC), y - 66 * ESC)],
            fill="#94a3b8",
            width=ESC,
        )
        hachura += passo
    x_chapa_0, x_chapa_1 = px(-meia_chapa), px(meia_chapa)
    d.rectangle(
        [x_chapa_0, y - 66 * ESC, x_chapa_1, y + 30 * ESC],
        fill=_CHAPA_B,
        outline=_LINHA,
        width=2 * ESC,
    )
    x_forca = px(0.0)
    dg.seta(
        d,
        (x_forca, y - 66 * ESC),
        (x_forca, y - 90 * ESC),
        _FORCA,
        largura=2 * ESC,
        ponta_px=9 * ESC,
    )
    _texto(
        d,
        (x_forca + 8 * ESC, y - 92 * ESC),
        f"F = {_forca_kN(pino.forca)}",
        cor=_FORCA,
        tamanho=11,
        ancora="lm",
    )
    d.rectangle(
        [px(-meia_chapa) - 8 * ESC, y - meia, fim, y + meia],
        fill=_PINO,
        outline=_PINO_LINHA,
        width=2 * ESC,
    )

    # A pressão no furo: linear, de um lado do pino na boca e do outro no fundo.
    p_boca, p_fundo = pino.pressao_max, pino.pressao_no_fundo
    maior = max(p_boca, p_fundo)
    alcance = 24 * ESC
    zero = face + (fim - face) * p_boca / (p_boca + p_fundo)
    baixo = y + meia
    alto = y - meia
    # A força sobe, e o pino se apoia embaixo na boca e em cima no fundo.
    d.polygon(
        [(face, alto), (zero, alto), (face, alto - p_boca / maior * alcance)],
        fill=_claro(_PRESSAO, 0.55),
    )
    d.polygon(
        [(fim, baixo), (zero, baixo), (fim, baixo + p_fundo / maior * alcance)],
        fill=_claro(_PRESSAO, 0.55),
    )
    _texto(
        d,
        (face + 6 * ESC, alto - alcance - 9 * ESC),
        f"p = {_n(p_boca, 0)} MPa",
        cor=_PRESSAO,
        tamanho=11,
        ancora="lm",
    )

    dg.tracejado(
        d,
        (face, y - meia - 12 * ESC),
        (face, y + meia + 12 * ESC),
        _CORTE,
        largura=2 * ESC,
        traco=4 * ESC,
    )
    xs = [px(x) for x in diagrama.x]
    _diagrama(
        d,
        xs,
        diagrama.cortante,
        284 * ESC,
        _CORTANTE,
        "V",
        f"V = {_forca_kN(diagrama.cortante_max)}",
    )
    _diagrama(
        d,
        xs,
        diagrama.momento,
        370 * ESC,
        _MOMENTO,
        "M",
        f"M = {_momento_Nm(diagrama.momento_max)}",
    )
    return figura_final(imagem, titulo, legenda)


def figura_do_transversal(
    d_eixo: float,
    d_cubo: float,
    d_pino: float,
    forca_no_plano: float,
    torque_Nm: float,
    p_eixo: float,
    p_cubo: float,
    *,
    titulo: str,
    legenda: str,
) -> ImagemDiagrama:
    """Corte do eixo e do cubo, com o pino atravessando e a pressão de cada lado."""
    if desenho_dispensado():
        return ImagemDiagrama(titulo, legenda, b"", 0, 0)
    imagem, d = _quadro(330)
    cx, cy = 300 * ESC, 165 * ESC
    escala = 135 * ESC / (d_cubo / 2.0)
    raio_cubo = d_cubo / 2.0 * escala
    raio_eixo = d_eixo / 2.0 * escala
    meia = max(d_pino / 2.0 * escala, 6 * ESC)
    d.ellipse(
        [cx - raio_cubo, cy - raio_cubo, cx + raio_cubo, cy + raio_cubo],
        fill=_CHAPA_B,
        outline=_LINHA,
        width=2 * ESC,
    )
    d.ellipse(
        [cx - raio_eixo, cy - raio_eixo, cx + raio_eixo, cy + raio_eixo],
        fill=_CHAPA_A,
        outline=_LINHA,
        width=2 * ESC,
    )
    d.rectangle(
        [cx - raio_cubo, cy - meia, cx + raio_cubo, cy + meia],
        fill=_PINO,
        outline=_PINO_LINHA,
        width=2 * ESC,
    )
    for lado in (-1.0, 1.0):
        x = cx + lado * raio_eixo
        dg.tracejado(
            d,
            (x, cy - meia - 14 * ESC),
            (x, cy + meia + 14 * ESC),
            _CORTE,
            largura=2 * ESC,
            traco=4 * ESC,
        )

    # Pressão no pino, vista por cima: triângulo no eixo e retângulo no cubo.
    altura = 34 * ESC
    maior = max(p_eixo, p_cubo)
    topo = cy - meia
    fator_eixo = p_eixo / maior * altura
    fator_cubo = p_cubo / maior * altura
    d.polygon(
        [(cx, topo), (cx + raio_eixo, topo), (cx + raio_eixo, topo - fator_eixo)],
        fill=_claro(_PRESSAO, 0.5),
    )
    d.rectangle([cx + raio_eixo, topo - fator_cubo, cx + raio_cubo, topo], fill=_claro(_FORCA, 0.6))
    _texto(
        d,
        (cx + raio_eixo * 0.6, topo - fator_eixo - 10 * ESC),
        f"p = {_n(p_eixo, 0)} MPa",
        cor=_PRESSAO,
        tamanho=11,
    )
    _texto(
        d,
        (cx + raio_cubo + 8 * ESC, topo - fator_cubo / 2),
        f"p = {_n(p_cubo, 0)} MPa",
        cor=_FORCA,
        tamanho=11,
        ancora="lm",
    )

    # O torque do eixo: embaixo do pino, para a seta não cruzar com ele.
    raio = raio_eixo * 0.62
    d.arc([cx - raio, cy - raio, cx + raio, cy + raio], 35, 145, fill=_FORCA, width=2 * ESC)
    angulo = math.radians(35)
    ponta = (cx + raio * math.cos(angulo), cy + raio * math.sin(angulo))
    dg.seta(
        d,
        (ponta[0] - 8 * ESC, ponta[1] + 5 * ESC),
        ponta,
        _FORCA,
        largura=2 * ESC,
        ponta_px=9 * ESC,
    )
    _texto(d, (cx, cy + raio + 12 * ESC), f"T = {_n(torque_Nm, 0)} N·m", cor=_FORCA, tamanho=11)
    _texto(
        d,
        (cx - raio_cubo - 10 * ESC, cy),
        f"F = {_forca_kN(forca_no_plano)}",
        cor=_CORTE,
        tamanho=11,
        ancora="rm",
    )
    return figura_final(imagem, titulo, legenda)
