"""Desenhos dos casos de estática do Assistente de cargas, na escala dos dados, sem Streamlit.

Cada função devolve um PNG (:class:`core.beam_charts.ImagemDiagrama`), que serve para a tela e para
o Word. O desenho é feito no dobro do tamanho e reduzido no fim, para o traço sair suavizado.

Cores: vermelho para tração e azul para compressão em todos os desenhos, as mesmas que as tabelas
descrevem. Cada barra e cada parafuso também levam o valor escrito, para a cor nunca ser a única
informação.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from core import beam_model as bm
from core import equilibrio_corpo as eq
from core.beam_charts import ImagemDiagrama, _fonte, desenho_dispensado

_ESC = 2
_FUNDO = "#ffffff"
_TEXTO = "#172033"
_TEXTO_FRACO = "#64748b"
_CORPO = "#cbd5e1"
_CONTORNO = "#334155"
_TRACAO = "#c2415d"
_COMPRESSAO = "#0b6e99"
_NEUTRO = "#94a3b8"
_CARGA = "#b45309"
_REACAO = "#16836f"

Ponto = tuple[float, float]


def _n(valor: float, casas: int = 2) -> str:
    """Número em pt-BR sem zeros sobrando: 1,5; 12; 0,25."""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto.replace(".", ",")


def _nova(largura: int, altura: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    imagem = Image.new("RGB", (largura * _ESC, altura * _ESC), _FUNDO)
    return imagem, ImageDraw.Draw(imagem)


def _fechar(imagem: Image.Image, titulo: str, legenda: str) -> ImagemDiagrama:
    if desenho_dispensado():
        return ImagemDiagrama(titulo, legenda, b"", 0, 0)
    final = imagem.resize((imagem.width // _ESC, imagem.height // _ESC), Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    final.save(saida, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, saida.getvalue(), final.width, final.height)


def _texto(
    d: ImageDraw.ImageDraw,
    posicao: Ponto,
    texto: str,
    *,
    cor: str = _TEXTO,
    tamanho: int = 13,
    ancora: str = "mm",
) -> None:
    d.text(posicao, texto, fill=cor, font=_fonte(tamanho * _ESC), anchor=ancora)


def _seta(
    d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, cor: str, *, largura: int = 2, ponta: float = 11
) -> None:
    """Seta de ``a`` para ``b``, com a ponta em ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    comprimento = math.hypot(dx, dy)
    if comprimento < 1e-6:
        return
    ux, uy = dx / comprimento, dy / comprimento
    p = ponta * _ESC
    base = (b[0] - ux * p, b[1] - uy * p)
    d.line([a, base], fill=cor, width=largura * _ESC)
    esquerda = (base[0] - uy * p * 0.45, base[1] + ux * p * 0.45)
    direita = (base[0] + uy * p * 0.45, base[1] - ux * p * 0.45)
    d.polygon([b, esquerda, direita], fill=cor)


@dataclass(frozen=True)
class _Escala:
    """Mundo para pixels, com a mesma escala nos dois eixos: o desenho não deforma."""

    x_min: float
    y_min: float
    escala: float
    x0: float
    y0: float
    altura: float

    def px(self, x: float, y: float) -> Ponto:
        return (
            self.x0 + (x - self.x_min) * self.escala,
            self.altura - self.y0 - (y - self.y_min) * self.escala,
        )


def _escala(
    pontos: Sequence[Ponto], largura: int, altura: int, margem: float, *, topo: float = 0.0
) -> _Escala:
    """Cabe os pontos na área útil e centra o que sobrar."""
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    largura_px, altura_px = largura * _ESC, altura * _ESC
    util_x = largura_px - 2.0 * margem * _ESC
    util_y = altura_px - 2.0 * margem * _ESC - topo * _ESC
    dx = max(x_max - x_min, 1e-9)
    dy = max(y_max - y_min, 1e-9)
    if x_max - x_min < 1e-9 and y_max - y_min < 1e-9:
        escala = 1.0
    elif x_max - x_min < 1e-9:
        escala = util_y / dy
    elif y_max - y_min < 1e-9:
        escala = util_x / dx
    else:
        escala = min(util_x / dx, util_y / dy)
    sobra_x = (largura_px - (x_max - x_min) * escala) / 2.0
    sobra_y = (altura_px - topo * _ESC - (y_max - y_min) * escala) / 2.0
    return _Escala(x_min, y_min, escala, sobra_x, sobra_y, altura_px)


def _eixos(d: ImageDraw.ImageDraw, origem: Ponto) -> None:
    """Triedro pequeno no canto, para dizer de que lado fica +x e +y."""
    tamanho = 42 * _ESC
    x, y = origem
    _seta(d, (x, y), (x + tamanho, y), _TEXTO_FRACO, ponta=8)
    _seta(d, (x, y), (x, y - tamanho), _TEXTO_FRACO, ponta=8)
    _texto(d, (x + tamanho + 10 * _ESC, y), "x", cor=_TEXTO_FRACO, tamanho=12)
    _texto(d, (x, y - tamanho - 10 * _ESC), "y", cor=_TEXTO_FRACO, tamanho=12)


# ---------------------------------------------------------------------------
# Grupo de parafusos
# ---------------------------------------------------------------------------


def figura_do_grupo_de_parafusos(
    pontos: Sequence[Ponto], tracoes_kN: Sequence[float], designacao: str
) -> ImagemDiagrama:
    """Planta do grupo: cada parafuso com o número e a força, na posição real."""
    largura, altura = 720, 520
    imagem, d = _nova(largura, altura)
    escala = _escala(pontos, largura, altura, 74, topo=20)
    maior = max([abs(t) for t in tracoes_kN] + [1e-9])
    raio = 19 * _ESC
    x_centro, y_centro = escala.px(
        sum(p[0] for p in pontos) / len(pontos), sum(p[1] for p in pontos) / len(pontos)
    )
    tamanho = 12 * _ESC
    d.line(
        [(x_centro - tamanho, y_centro), (x_centro + tamanho, y_centro)],
        fill=_TEXTO_FRACO,
        width=2,
    )
    d.line(
        [(x_centro, y_centro - tamanho), (x_centro, y_centro + tamanho)],
        fill=_TEXTO_FRACO,
        width=2,
    )
    for i, ((x, y), tracao) in enumerate(zip(pontos, tracoes_kN, strict=True), start=1):
        cx, cy = escala.px(x, y)
        forca = abs(tracao) / maior
        base = _TRACAO if tracao >= 0 else _COMPRESSAO
        cor = _mistura("#ffffff", base, 0.25 + 0.75 * forca)
        d.ellipse(
            [cx - raio, cy - raio, cx + raio, cy + raio], fill=cor, outline=_CONTORNO, width=2
        )
        tinta = "#ffffff" if forca > 0.55 else _TEXTO
        _texto(d, (cx, cy), str(i), cor=tinta, tamanho=13)
        _texto(d, (cx, cy + raio + 13 * _ESC), f"{_n(tracao)} kN", tamanho=12)
    _eixos(d, (28 * _ESC, (altura - 28) * _ESC))
    _texto(
        d,
        ((largura - 16) * _ESC, 18 * _ESC),
        f"{len(pontos)} parafusos {designacao}",
        cor=_TEXTO_FRACO,
        tamanho=13,
        ancora="rm",
    )
    return _fechar(imagem, "Grupo de parafusos", "Tração de cada parafuso, em planta.")


def _mistura(a: str, b: str, fracao: float) -> str:
    fa = tuple(int(a[i : i + 2], 16) for i in (1, 3, 5))
    fb = tuple(int(b[i : i + 2], 16) for i in (1, 3, 5))
    misturado = [round(x + (y - x) * fracao) for x, y in zip(fa, fb, strict=True)]
    return "#{:02x}{:02x}{:02x}".format(*misturado)


# ---------------------------------------------------------------------------
# Barra em trechos
# ---------------------------------------------------------------------------


def _parede(d: ImageDraw.ImageDraw, x: float, y: float, meia: float, lado: float) -> None:
    """Engaste: traço vertical e hachura para o lado de fora."""
    d.line([(x, y - meia), (x, y + meia)], fill=_CONTORNO, width=3 * _ESC)
    passo = 13 * _ESC
    atual = y - meia
    while atual < y + meia:
        d.line([(x, atual), (x + lado * 13 * _ESC, atual + 13 * _ESC)], fill=_CONTORNO, width=_ESC)
        atual += passo


def figura_da_barra(
    comprimentos: Sequence[float],
    espessuras: Sequence[float],
    esforcos: Sequence[float],
    cargas: Sequence[float],
    *,
    presa_nas_duas: bool,
    unidade_esforco: str,
    unidade_carga: str,
    titulo: str,
    legenda: str = "Vermelho é tração e azul é compressão.",
    torque: bool = False,
) -> ImagemDiagrama:
    """Barra em trechos: largura real dos trechos, altura pela raiz do tamanho da seção.

    ``cargas`` são as forças (ou torques) no fim de cada trecho.
    """
    largura, altura = 720, 330
    imagem, d = _nova(largura, altura)
    x0, x1 = 60 * _ESC, (largura - 76) * _ESC
    y = 180 * _ESC
    total = sum(comprimentos)
    maior = max(espessuras)
    posicao = float(x0)
    extremos = [posicao]
    for comprimento, espessura, esforco in zip(comprimentos, espessuras, esforcos, strict=True):
        fim = posicao + (x1 - x0) * comprimento / total
        meia = (16 + 62 * math.sqrt(espessura / maior)) / 2.0 * _ESC
        if abs(esforco) < 1e-9:
            cor = _CORPO
        else:
            cor = _mistura("#ffffff", _TRACAO if esforco > 0 else _COMPRESSAO, 0.35)
        d.rectangle([posicao, y - meia, fim, y + meia], fill=cor, outline=_CONTORNO, width=2)
        _texto(
            d,
            ((posicao + fim) / 2.0, y),
            f"{_n(esforco)} {unidade_esforco}",
            tamanho=13,
        )
        posicao = fim
        extremos.append(fim)
    _parede(d, x0, y, 72 * _ESC, -1.0)
    if presa_nas_duas:
        _parede(d, x1, y, 72 * _ESC, 1.0)
    for xp, carga in zip(extremos[1:], cargas, strict=True):
        if abs(carga) < 1e-9:
            continue
        tamanho = 48 * _ESC
        sentido = 1.0 if carga > 0 else -1.0
        linha = 92 * _ESC
        if torque:
            raio = 22 * _ESC
            d.arc(
                [xp - raio, y - linha - raio + 8 * _ESC, xp + raio, y - linha + raio + 8 * _ESC],
                200,
                340,
                fill=_CARGA,
                width=2 * _ESC,
            )
            lado = 1.0 if sentido > 0 else -1.0
            chegada = (xp + lado * raio * 0.94, y - linha + 8 * _ESC - raio * 0.34)
            _seta(
                d,
                (chegada[0] - lado * 8 * _ESC, chegada[1] - 8 * _ESC),
                (chegada[0] + lado * 2 * _ESC, chegada[1] + 3 * _ESC),
                _CARGA,
                ponta=9,
            )
        else:
            inicio = (xp - sentido * tamanho / 2.0 + sentido * 12 * _ESC, y - linha)
            fim_seta = (xp + sentido * tamanho / 2.0 + sentido * 12 * _ESC, y - linha)
            _seta(d, inicio, fim_seta, _CARGA)
        d.line([(xp, y - linha + 6 * _ESC), (xp, y - 40 * _ESC)], fill=_NEUTRO, width=_ESC)
        _texto(
            d,
            (xp, y - linha - (32 if torque else 18) * _ESC),
            f"{_n(abs(carga))} {unidade_carga}",
            cor=_CARGA,
            tamanho=13,
        )
    posicao = float(x0)
    for comprimento in comprimentos:
        fim = posicao + (x1 - x0) * comprimento / total
        y_cota = y + 78 * _ESC
        d.line([(posicao, y_cota), (fim, y_cota)], fill=_NEUTRO, width=_ESC)
        for marca in (posicao, fim):
            d.line(
                [(marca, y_cota - 6 * _ESC), (marca, y_cota + 6 * _ESC)], fill=_NEUTRO, width=_ESC
            )
        _texto(
            d,
            ((posicao + fim) / 2.0, y_cota + 14 * _ESC),
            f"{_n(comprimento, 1)} mm",
            cor=_TEXTO_FRACO,
            tamanho=12,
        )
        posicao = fim
    return _fechar(imagem, titulo, legenda)


# ---------------------------------------------------------------------------
# Treliça
# ---------------------------------------------------------------------------


def _apoio_triangulo(d: ImageDraw.ImageDraw, x: float, y: float, *, com_rolo: bool) -> None:
    lado = 14 * _ESC
    d.polygon(
        [(x, y), (x - lado, y + lado * 1.4), (x + lado, y + lado * 1.4)],
        fill=_CORPO,
        outline=_CONTORNO,
    )
    base = y + lado * 1.4
    if com_rolo:
        r = 4 * _ESC
        for deslocamento in (-lado * 0.6, lado * 0.6):
            d.ellipse(
                [x + deslocamento - r, base, x + deslocamento + r, base + 2 * r],
                fill=_FUNDO,
                outline=_CONTORNO,
                width=_ESC,
            )
        base += 2 * r
    d.line([(x - lado * 1.5, base), (x + lado * 1.5, base)], fill=_CONTORNO, width=2 * _ESC)


def _folga(vizinhos: Sequence[Ponto], no: Ponto, sentido: Ponto) -> float:
    """Quanto a seta, nesse sentido a partir do nó, fica longe das barras que chegam nele."""
    maior = -1.0
    for vx, vy in vizinhos:
        dx, dy = vx - no[0], vy - no[1]
        comprimento = math.hypot(dx, dy) or 1.0
        maior = max(maior, (dx * sentido[0] + dy * sentido[1]) / comprimento)
    return -maior


def figura_da_trelica(
    nos: Sequence[tuple[str, float, float]],
    barras: Sequence[tuple[str, str, float]],
    apoios: dict[str, str],
    cargas: dict[str, tuple[float, float]],
) -> ImagemDiagrama:
    """Treliça com a força de cada barra. ``apoios`` guarda "pino" ou "rolete" por nó."""
    largura, altura = 760, 480
    imagem, d = _nova(largura, altura)
    posicoes = {nome: (x, y) for nome, x, y in nos}
    escala = _escala([(x, y) for _, x, y in nos], largura, altura, 84, topo=24)
    tela = {nome: escala.px(x, y) for nome, (x, y) in posicoes.items()}
    maior = max([abs(f) for _, _, f in barras] + [1e-9])
    for no_i, no_j, forca in barras:
        a, b = tela[no_i], tela[no_j]
        if abs(forca) < 1e-6 * maior:
            cor = _NEUTRO
        else:
            cor = _TRACAO if forca > 0 else _COMPRESSAO
        d.line([a, b], fill=cor, width=round((2 + 4 * abs(forca) / maior) * _ESC))
    for no_i, no_j, forca in barras:
        a, b = tela[no_i], tela[no_j]
        meio = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        rotulo = _n(forca, 1)
        caixa = d.textbbox(meio, rotulo, font=_fonte(11 * _ESC), anchor="mm")
        folga = 3 * _ESC
        d.rectangle(
            [caixa[0] - folga, caixa[1] - folga, caixa[2] + folga, caixa[3] + folga], fill=_FUNDO
        )
        _texto(d, meio, rotulo, tamanho=11)
    for nome, (x, y) in tela.items():
        tipo = apoios.get(nome)
        if tipo:
            _apoio_triangulo(d, x, y + 6 * _ESC, com_rolo=tipo == "rolete")
        r = 6 * _ESC
        d.ellipse([x - r, y - r, x + r, y + r], fill=_FUNDO, outline=_CONTORNO, width=2 * _ESC)
        _texto(d, (x + 12 * _ESC, y - 14 * _ESC), nome, cor=_TEXTO_FRACO, tamanho=12)
    for nome, (fx, fy) in cargas.items():
        x, y = tela[nome]
        modulo = math.hypot(fx, fy)
        if modulo < 1e-9:
            continue
        ux, uy = fx / modulo, -fy / modulo  # na tela, y cresce para baixo
        tamanho = 54 * _ESC
        vizinhos = [tela[j if i == nome else i] for i, j, _ in barras if nome in (i, j)]
        if _folga(vizinhos, (x, y), (ux, uy)) >= _folga(vizinhos, (x, y), (-ux, -uy)):
            # A seta sai do nó, no sentido da força.
            cauda = (x + ux * 10 * _ESC, y + uy * 10 * _ESC)
            ponta = (cauda[0] + ux * tamanho, cauda[1] + uy * tamanho)
            lugar = (ponta[0] + ux * 16 * _ESC, ponta[1] + uy * 16 * _ESC)
        else:
            # A seta chega ao nó, vindo do lado livre.
            ponta = (x - ux * 10 * _ESC, y - uy * 10 * _ESC)
            cauda = (ponta[0] - ux * tamanho, ponta[1] - uy * tamanho)
            lugar = (cauda[0] - ux * 16 * _ESC, cauda[1] - uy * 16 * _ESC)
        _seta(d, cauda, ponta, _CARGA)
        _texto(d, lugar, f"{_n(modulo, 1)} kN", cor=_CARGA, tamanho=12)
    return _fechar(imagem, "Treliça", "Força em kN. Vermelho é tração, azul é compressão.")


# ---------------------------------------------------------------------------
# Seção montada com retângulos
# ---------------------------------------------------------------------------


def figura_da_secao(
    retangulos: Sequence[tuple[float, float, float, float, bool, bool]],
    centroide: Ponto,
) -> ImagemDiagrama:
    """Seção em escala: cada parte é (b, h, x do centro, y do centro, é furo, é círculo)."""
    largura, altura = 640, 500
    imagem, d = _nova(largura, altura)
    cantos = [
        (x + sx * b / 2.0, y + sy * h / 2.0)
        for b, h, x, y, _, _ in retangulos
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
    ]
    escala = _escala(cantos, largura, altura, 70)

    def caixa(b: float, h: float, x: float, y: float) -> list[float]:
        p1 = escala.px(x - b / 2.0, y + h / 2.0)
        p2 = escala.px(x + b / 2.0, y - h / 2.0)
        return [p1[0], p1[1], p2[0], p2[1]]

    for vazado in (False, True):
        for b, h, x, y, furo, circulo in retangulos:
            if furo != vazado:
                continue
            cor = _FUNDO if furo else _CORPO
            linha = _TRACAO if furo else _CONTORNO
            desenhar = d.ellipse if circulo else d.rectangle
            desenhar(caixa(b, h, x, y), fill=cor, outline=linha, width=2)
    cx, cy = escala.px(*centroide)
    extensao = 300 * _ESC
    d.line([(cx - extensao, cy), (cx + extensao, cy)], fill=_COMPRESSAO, width=_ESC)
    d.line([(cx, cy - extensao), (cx, cy + extensao)], fill=_COMPRESSAO, width=_ESC)
    r = 6 * _ESC
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_COMPRESSAO)
    _texto(
        d,
        (cx + 12 * _ESC, cy - 14 * _ESC),
        f"CG ({_n(centroide[0], 1)}; {_n(centroide[1], 1)})",
        cor=_COMPRESSAO,
        tamanho=13,
        ancora="lm",
    )
    return _fechar(imagem, "Seção", "Seção em escala, com o centro de gravidade.")


def figura_das_partes(partes: Sequence[Any], prop: Any) -> ImagemDiagrama:
    """Seção desenhada em escala, com as medidas totais, o G e o centro de cisalhamento."""
    largura, altura = 640, 500
    imagem, d = _nova(largura, altura)
    x0, y0 = prop.x0, prop.y0
    x1, y1 = x0 + prop.largura, y0 + prop.altura
    escala = _escala([(x0, y0), (x1, y1)], largura, altura, 80)

    def contorno(parte: Any, cor: str, linha: str) -> None:
        if parte.forma == "circ":
            r = parte.b / 2.0
            a = escala.px(parte.x - r, parte.y + r)
            b = escala.px(parte.x + r, parte.y - r)
            d.ellipse([a[0], a[1], b[0], b[1]], fill=cor, outline=linha, width=2 * _ESC)
            return
        pontos = [escala.px(x, y) for x, y in parte.cantos]
        d.polygon(pontos, fill=cor, outline=linha, width=2 * _ESC)

    for parte in partes:
        if not parte.furo:
            contorno(parte, _CORPO, _CONTORNO)
    for parte in partes:
        if parte.furo:
            contorno(parte, _FUNDO, _TRACAO)

    base = escala.px(x0, y0)
    topo = escala.px(x1, y1)
    y_cota = base[1] + 26 * _ESC
    x_cota = base[0] - 26 * _ESC
    d.line([(base[0], y_cota), (topo[0], y_cota)], fill=_TEXTO_FRACO, width=_ESC)
    d.line([(x_cota, base[1]), (x_cota, topo[1])], fill=_TEXTO_FRACO, width=_ESC)
    for x in (base[0], topo[0]):
        d.line([(x, y_cota - 6 * _ESC), (x, y_cota + 6 * _ESC)], fill=_TEXTO_FRACO, width=_ESC)
    for y in (base[1], topo[1]):
        d.line([(x_cota - 6 * _ESC, y), (x_cota + 6 * _ESC, y)], fill=_TEXTO_FRACO, width=_ESC)
    _texto(
        d,
        ((base[0] + topo[0]) / 2, y_cota + 16 * _ESC),
        f"{_n(prop.largura, 1)} mm",
        cor=_TEXTO,
        tamanho=13,
    )
    _texto(
        d,
        (x_cota - 8 * _ESC, (base[1] + topo[1]) / 2),
        f"{_n(prop.altura, 1)} mm",
        cor=_TEXTO,
        tamanho=13,
        ancora="rm",
    )

    cx, cy = escala.px(prop.xc, prop.yc)
    r = 6 * _ESC
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_COMPRESSAO, width=2 * _ESC)
    d.line([(cx - 2 * r, cy), (cx + 2 * r, cy)], fill=_COMPRESSAO, width=_ESC)
    d.line([(cx, cy - 2 * r), (cx, cy + 2 * r)], fill=_COMPRESSAO, width=_ESC)
    _texto(d, (cx + 12 * _ESC, cy - 14 * _ESC), "G", cor=_COMPRESSAO, tamanho=14, ancora="lm")
    tamanho = max(prop.largura, prop.altura)
    if prop.pedacos == 1 and abs(prop.x_s) + abs(prop.y_s) > 0.01 * tamanho:
        sx, sy = escala.px(prop.xc + prop.x_s, prop.yc + prop.y_s)
        d.polygon(
            [(sx, sy - r), (sx + r, sy), (sx, sy + r), (sx - r, sy)], outline=_CARGA, width=2 * _ESC
        )
        _texto(d, (sx + 12 * _ESC, sy - 14 * _ESC), "CC", cor=_CARGA, tamanho=14, ancora="lm")
    return _fechar(
        imagem, "Seção", "Seção em escala. G: centro de gravidade. CC: centro de cisalhamento."
    )


_BRANCO = np.array([255.0, 255.0, 255.0])
_QUENTE = np.array([194.0, 65.0, 93.0])
_FRIO = np.array([11.0, 110.0, 153.0])


def _valores_por_celula(m: Any, x: np.ndarray, y: np.ndarray, valores: np.ndarray) -> np.ndarray:
    """Média dos pontos de cada célula. Um nó entra em todas as células que encostam nele."""
    nx, ny = len(m.xs) - 1, len(m.ys) - 1
    soma, conta = np.zeros((nx, ny)), np.zeros((nx, ny))
    folga = 1e-9 * float(m.xs[-1] - m.xs[0])
    for sx in (-folga, folga):
        for sy in (-folga, folga):
            i = np.clip(np.searchsorted(m.xs, x + sx) - 1, 0, nx - 1)
            j = np.clip(np.searchsorted(m.ys, y + sy) - 1, 0, ny - 1)
            np.add.at(soma, (i, j), valores)
            np.add.at(conta, (i, j), 1.0)
    return np.divide(soma, conta, out=np.zeros_like(soma), where=conta > 0)


def _linha_neutra(mapa: Any, p: Any) -> tuple[Ponto, Ponto] | None:
    """Onde σ = 0 corta a caixa da seção. Sem troca de sinal, a linha não existe."""
    if not (mapa.sigma_max > 0.0 > mapa.sigma_min) or not (mapa.b or mapa.c):
        return None
    achados: list[Ponto] = []
    for x in (p.x0, p.x0 + p.largura):
        if mapa.c:
            y = p.yc - (mapa.a + mapa.b * (x - p.xc)) / mapa.c
            if p.y0 <= y <= p.y0 + p.altura:
                achados.append((x, y))
    for y in (p.y0, p.y0 + p.altura):
        if mapa.b:
            x = p.xc - (mapa.a + mapa.c * (y - p.yc)) / mapa.b
            if p.x0 <= x <= p.x0 + p.largura:
                achados.append((x, y))
    return (achados[0], achados[1]) if len(achados) >= 2 else None


def _tracejado(d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, cor: str) -> None:
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    passo = 9.0 * _ESC
    for k in range(int(comprimento / passo) + 1):
        if k % 2:
            continue
        i0, i1 = k * passo / comprimento, min((k + 1) * passo / comprimento, 1.0)
        d.line(
            [
                (a[0] + (b[0] - a[0]) * i0, a[1] + (b[1] - a[1]) * i0),
                (a[0] + (b[0] - a[0]) * i1, a[1] + (b[1] - a[1]) * i1),
            ],
            fill=cor,
            width=2 * _ESC,
        )


def _setas_de_tau(d: ImageDraw.ImageDraw, escala: _Escala, mapa: Any) -> None:
    """Uma seta por trecho do desenho, no ponto mais perto do meio dele."""
    maior = float(mapa.tau_max)
    if maior <= 0.0:
        return
    passo = 30.0 * _ESC
    melhores: dict[tuple[int, int], tuple[float, int]] = {}
    for k in range(len(mapa.no_x)):
        x, y = escala.px(float(mapa.no_x[k]), float(mapa.no_y[k]))
        chave = (int(x // passo), int(y // passo))
        distancia = math.hypot((x % passo) - passo / 2.0, (y % passo) - passo / 2.0)
        if chave not in melhores or distancia < melhores[chave][0]:
            melhores[chave] = (distancia, k)
    for _, k in melhores.values():
        tx, ty = float(mapa.no_tau_x[k]), float(mapa.no_tau_y[k])
        modulo = math.hypot(tx, ty)
        if modulo < 0.05 * maior:
            continue
        tamanho = (7.0 + 15.0 * min(modulo / maior, 1.0)) * _ESC
        x, y = escala.px(float(mapa.no_x[k]), float(mapa.no_y[k]))
        ux, uy = tx / modulo, -ty / modulo
        a = (x - ux * tamanho / 2.0, y - uy * tamanho / 2.0)
        b = (x + ux * tamanho / 2.0, y + uy * tamanho / 2.0)
        _seta(d, a, b, _TEXTO, largura=1, ponta=6)


def _marca_de_maximo(d: ImageDraw.ImageDraw, escala: _Escala, ponto: tuple[float, float]) -> None:
    x, y = escala.px(*ponto)
    r = 9 * _ESC
    d.ellipse([x - r, y - r, x + r, y + r], outline=_TEXTO, width=2 * _ESC)
    d.line([(x - r * 1.5, y), (x + r * 1.5, y)], fill=_TEXTO, width=_ESC)
    d.line([(x, y - r * 1.5), (x, y + r * 1.5)], fill=_TEXTO, width=_ESC)


def figura_de_tensoes(analise: Any, mapa: Any, campo: str = "sigma") -> ImagemDiagrama:
    """Mapa da seção. ``campo``: "sigma", "tau" ou "mises".

    σ em vermelho e azul, porque tem sinal; τ e von Mises em um tom só, do branco ao forte. Em τ, as
    setas mostram o caminho do cisalhamento; a marca em cruz é o ponto de maior valor.
    """
    largura, altura = 640, 460
    imagem, d = _nova(largura, altura)
    p = analise.prop
    m = analise.malha
    escala = _escala([(p.x0, p.y0), (p.x0 + p.largura, p.y0 + p.altura)], largura, altura, 50)
    x_a, y_a = escala.px(p.x0, p.y0 + p.altura)
    x_b, y_b = escala.px(p.x0 + p.largura, p.y0)
    nx, ny = max(int(x_b - x_a), 1), max(int(y_b - y_a), 1)
    xs = p.x0 + (np.arange(nx) + 0.5) / nx * p.largura
    ys = p.y0 + p.altura - (np.arange(ny) + 0.5) / ny * p.altura
    ix = np.clip(np.searchsorted(m.xs, xs) - 1, 0, len(m.xs) - 2)
    iy = np.clip(np.searchsorted(m.ys, ys) - 1, 0, len(m.ys) - 2)
    if campo == "sigma":
        grade_x, grade_y = np.meshgrid(xs, ys)
        sigma = mapa.a + mapa.b * (grade_x - p.xc) + mapa.c * (grade_y - p.yc)
        maior = max(abs(mapa.sigma_max), abs(mapa.sigma_min), 1e-9)
        r = np.clip(sigma / maior, -1.0, 1.0)[..., None]
        cor = np.where(
            r >= 0.0, _BRANCO + (_QUENTE - _BRANCO) * r, _BRANCO + (_FRIO - _BRANCO) * -r
        )
    else:
        valores = np.hypot(mapa.no_tau_x, mapa.no_tau_y) if campo == "tau" else mapa.no_mises
        teto = max(mapa.tau_max if campo == "tau" else mapa.mises, 1e-9)
        celulas = _valores_por_celula(m, mapa.no_x, mapa.no_y, valores)
        r = np.clip(celulas[np.ix_(ix, iy)].T / teto, 0.0, 1.0)[..., None]
        cor = _BRANCO + ((_FRIO if campo == "tau" else _QUENTE) - _BRANCO) * r
    tem_aco = m.ativo[np.ix_(ix, iy)].T[..., None]
    pixels = np.where(tem_aco, cor, 255.0).astype(np.uint8)
    imagem.paste(Image.fromarray(pixels, "RGB"), (int(x_a), int(y_a)))
    if campo == "sigma":
        linha = _linha_neutra(mapa, p)
        if linha is not None:
            _tracejado(d, escala.px(*linha[0]), escala.px(*linha[1]), _CONTORNO)
        rodape = (
            f"tração máx. {_n(mapa.sigma_max, 1)} MPa · compressão máx. {_n(mapa.sigma_min, 1)} MPa"
        )
        legenda = "Tensão normal: tração em vermelho, compressão em azul, linha neutra tracejada."
    elif campo == "tau":
        _setas_de_tau(d, escala, mapa)
        if mapa.tau_max > 0.0:
            _marca_de_maximo(d, escala, mapa.ponto_tau)
        rodape = f"τ máx. {_n(mapa.tau_max, 1)} MPa"
        legenda = "Cisalhamento de V e T somados: as setas mostram o caminho, a cruz o maior valor."
    else:
        if mapa.mises > 0.0:
            _marca_de_maximo(d, escala, mapa.ponto_mises)
        rodape = f"von Mises máx. {_n(mapa.mises, 1)} MPa"
        legenda = "Tensão combinada √(σ² + 3τ²) em cada ponto: a cruz marca o ponto crítico."
    _texto(d, (largura * _ESC / 2, (altura - 18) * _ESC), rodape, cor=_TEXTO, tamanho=13)
    return _fechar(imagem, "Tensões", legenda)


# ---------------------------------------------------------------------------
# Peça em equilíbrio
# ---------------------------------------------------------------------------


def _hachura(d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, atras: Ponto) -> None:
    """Risquinhos atrás da linha de a até b: a marca de que ali é fixo."""
    for k in range(5):
        s = k / 4.0
        x, y = a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s
        d.line(
            [(x, y), (x + atras[0] + (b[0] - a[0]) * 0.12, y + atras[1] + (b[1] - a[1]) * 0.12)],
            fill=_CONTORNO,
            width=_ESC,
        )


def _simbolo_do_apoio(
    d: ImageDraw.ImageDraw, p: Ponto, tipo: str, direcao: tuple[float, float]
) -> None:
    """O símbolo fica atrás da reação: num apoio que empurra para cima, ele fica embaixo do ponto."""
    ux, uy = direcao[0], -direcao[1]
    vx, vy = -uy, ux
    e = float(_ESC)

    def pt(lado: float, atras: float) -> Ponto:
        return (p[0] + (vx * lado - ux * atras) * e, p[1] + (vy * lado - uy * atras) * e)

    atras_h = (-ux * 8 * e, -uy * 8 * e)
    if tipo == eq.ENGASTE:
        a, b = pt(-24, 0), pt(24, 0)
        d.line([a, b], fill=_CONTORNO, width=3 * _ESC)
        _hachura(d, a, b, atras_h)
        return
    if tipo == eq.GUIA:
        # O trilho corre de lado, perpendicular à reação.
        for atras in (-9, 9):
            d.line([pt(-22, atras), pt(22, atras)], fill=_CONTORNO, width=2 * _ESC)
        d.rectangle([p[0] - 6 * e, p[1] - 6 * e, p[0] + 6 * e, p[1] + 6 * e], outline=_CONTORNO)
        return
    if tipo in (eq.SIMPLES, eq.ATRITO):
        a, b = pt(-24, 7), pt(24, 7)
        d.line([a, b], fill=_CONTORNO, width=2 * _ESC)
        _hachura(d, a, b, atras_h)
        if tipo == eq.ATRITO:
            _texto(d, pt(32, 12), "μ", cor=_CONTORNO, tamanho=12)
        return
    d.polygon([p, pt(-13, 22), pt(13, 22)], outline=_CONTORNO, fill="#ffffff", width=2 * _ESC)
    if tipo == eq.ROLETE:
        for lado in (-8, 8):
            x, y = pt(lado, 27)
            r = 4 * e
            d.ellipse([x - r, y - r, x + r, y + r], outline=_CONTORNO, width=_ESC)
        a, b = pt(-20, 32), pt(20, 32)
    else:
        a, b = pt(-20, 22), pt(20, 22)
    d.line([a, b], fill=_CONTORNO, width=2 * _ESC)
    _hachura(d, a, b, atras_h)
    r = 4 * e
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill="#ffffff", outline=_CONTORNO)


def _arco_de_momento(
    d: ImageDraw.ImageDraw, p: Ponto, momento: float, cor: str, rotulo: str, raio: float = 24
) -> None:
    r = raio * _ESC
    d.arc([p[0] - r, p[1] - r, p[0] + r, p[1] + r], 30, 300, fill=cor, width=2 * _ESC)
    # O arco vai de 30° a 300° no sentido da tela; a ponta mostra o sentido do momento.
    grau = 300 if momento < 0 else 30
    x = p[0] + r * math.cos(math.radians(grau))
    y = p[1] + r * math.sin(math.radians(grau))
    tangente = grau + (90 if momento < 0 else -90)
    k = 9 * _ESC
    dx, dy = math.cos(math.radians(tangente)), math.sin(math.radians(tangente))
    _seta(d, (x - dx * k, y - dy * k), (x, y), cor, ponta=8)
    _texto(d, (p[0], p[1] - r - 12 * _ESC), rotulo, cor=cor, tamanho=12)


def _carga_distribuida(
    d: ImageDraw.ImageDraw, escala: _Escala, carga: eq.Carga, u: eq.Unidades
) -> None:
    ux, uy = eq.eixo(carga.angulo)
    maior = max(abs(carga.valor), abs(carga.valor2), 1e-12)
    alto = 46 * _ESC
    pontos = []
    for k in range(9):
        s = k / 8.0
        x = carga.x + (carga.x2 - carga.x) * s
        y = carga.y + (carga.y2 - carga.y) * s
        w = carga.valor + (carga.valor2 - carga.valor) * s
        ponta = escala.px(x, y)
        comprimento = abs(w) / maior * alto
        sinal = 1.0 if w >= 0.0 else -1.0
        cauda = (ponta[0] - sinal * ux * comprimento, ponta[1] + sinal * uy * comprimento)
        pontos.append(cauda)
        if comprimento > 6 * _ESC:
            _seta(d, cauda, ponta, _CARGA, ponta=8)
    d.line(pontos, fill=_CARGA, width=2 * _ESC)
    meio = pontos[len(pontos) // 2]
    fator = u.newton / u.metro
    texto = f"{_n(carga.valor / fator)} {u.distribuida}"
    if abs(carga.valor - carga.valor2) > 1e-12 * maior:
        texto = f"{_n(carga.valor / fator)} a {_n(carga.valor2 / fator)} {u.distribuida}"
    _texto(d, (meio[0] - ux * 14 * _ESC, meio[1] + uy * 14 * _ESC), texto, cor=_CARGA, tamanho=12)


def _ponta_da_barra(d: ImageDraw.ImageDraw, escala: _Escala, apoio: eq.Apoio) -> None:
    """Cabo e biela: a linha até a outra ponta, onde fica o pino fixo."""
    p = escala.px(apoio.x, apoio.y)
    cx, cy = apoio.direcao
    if apoio.x2 is not None and apoio.y2 is not None:
        fim = escala.px(apoio.x2, apoio.y2)
    else:
        fim = (p[0] + cx * 90 * _ESC, p[1] - cy * 90 * _ESC)
    d.line([p, fim], fill=_CONTORNO, width=(1 if apoio.tipo == eq.CABO else 4) * _ESC)
    _simbolo_do_apoio(d, fim, eq.PINO, (-cx, -cy))
    r = 4 * _ESC
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill="#ffffff", outline=_CONTORNO)


def _seta_de_carga(
    d: ImageDraw.ImageDraw, escala: _Escala, carga: eq.Carga, u: eq.Unidades
) -> None:
    p = escala.px(carga.x, carga.y)
    acao = eq.acao_da_carga(carga)
    modulo = math.hypot(acao.fx, acao.fy)
    if modulo <= 0.0:
        return
    ux, uy = acao.fx / modulo, acao.fy / modulo
    cauda = (p[0] - ux * 66 * _ESC, p[1] + uy * 66 * _ESC)
    _seta(d, cauda, p, _CARGA)
    rotulo = f"{carga.nome} = {_n(modulo / u.newton)} {u.forca}"
    folga = (16 + 40 * abs(ux)) * _ESC  # texto largo na seta deitada
    posicao = (cauda[0] - ux * folga, cauda[1] + uy * 16 * _ESC)
    _texto(d, posicao, rotulo, cor=_CARGA, tamanho=12)


def _seta_de_reacao(
    d: ImageDraw.ImageDraw, escala: _Escala, r: eq.Reacao, solucao: eq.Solucao, u: eq.Unidades
) -> None:
    p = escala.px(r.apoio.x, r.apoio.y)
    if r.modulo > 1e-9 * solucao.referencia:
        ux, uy = r.fx / r.modulo, r.fy / r.modulo
        longe = (p[0] + ux * 62 * _ESC, p[1] - uy * 62 * _ESC)
        perto = (p[0] - ux * 62 * _ESC, p[1] + uy * 62 * _ESC)
        puxa = r.apoio.tipo == eq.CABO
        cauda, ponta = (p, longe) if puxa else (perto, p)
        _seta(d, cauda, ponta, _REACAO, largura=3)
        fora = longe if puxa else perto
        _texto(
            d,
            (fora[0] + (fora[0] - p[0]) * 0.28, fora[1] + (fora[1] - p[1]) * 0.28),
            f"{r.apoio.nome} = {_n(r.modulo / u.newton)} {u.forca}",
            cor=_REACAO,
            tamanho=12,
        )
    if abs(r.m) > 1e-9 * solucao.referencia:
        rotulo = f"M{r.apoio.nome} = {_n(abs(r.m) / u.newton)} {u.momento}"
        _arco_de_momento(d, p, r.m, _REACAO, rotulo, raio=34)


def _marca_do_corte(d: ImageDraw.ImageDraw, escala: _Escala, corte: eq.Corte) -> None:
    p = escala.px(corte.x, corte.y)
    tx, ty = eq.eixo_do_corte(corte.angulo)
    nx, ny = -ty, tx
    a = (p[0] + nx * 26 * _ESC, p[1] - ny * 26 * _ESC)
    b = (p[0] - nx * 26 * _ESC, p[1] + ny * 26 * _ESC)
    for k in range(0, 8, 2):
        s0, s1 = k / 7.0, (k + 1) / 7.0
        d.line(
            [
                (a[0] + (b[0] - a[0]) * s0, a[1] + (b[1] - a[1]) * s0),
                (a[0] + (b[0] - a[0]) * s1, a[1] + (b[1] - a[1]) * s1),
            ],
            fill=_TRACAO,
            width=2 * _ESC,
        )
    _texto(d, (a[0], a[1] - 9 * _ESC), corte.nome, cor=_TRACAO, tamanho=12)


def figura_do_equilibrio(solucao: eq.Solucao, u: eq.Unidades) -> ImagemDiagrama:
    """A peça, os apoios, as cargas em laranja e as reações em verde, na proporção real."""
    problema = solucao.problema
    pontos: list[Ponto] = [(a.x, a.y) for a in problema.apoios]
    pontos += [(a.x2, a.y2) for a in problema.apoios if a.x2 is not None and a.y2 is not None]
    pontos += [(c.x, c.y) for c in problema.cargas]
    pontos += [(c.x2, c.y2) for c in problema.cargas if c.tipo == eq.DISTRIBUIDA]
    for t in problema.trechos:
        pontos += [(t.x1, t.y1), (t.x2, t.y2)]
    largura, altura = 760, 500
    imagem, d = _nova(largura, altura)
    escala = _escala(pontos, largura, altura, 110)

    for t in problema.trechos:
        a, b = escala.px(t.x1, t.y1), escala.px(t.x2, t.y2)
        d.line([a, b], fill=_CORPO, width=11 * _ESC)
        for x, y in (a, b):
            raio = 5.5 * _ESC
            d.ellipse([x - raio, y - raio, x + raio, y + raio], fill=_CORPO)

    for apoio in problema.apoios:
        if apoio.tipo in eq.COM_PONTA:
            _ponta_da_barra(d, escala, apoio)
        else:
            _simbolo_do_apoio(d, escala.px(apoio.x, apoio.y), apoio.tipo, apoio.direcao)

    for carga in problema.cargas:
        if carga.tipo == eq.DISTRIBUIDA:
            _carga_distribuida(d, escala, carga, u)
        elif carga.tipo == eq.MOMENTO:
            rotulo = f"{carga.nome} = {_n(abs(carga.valor) / u.newton)} {u.momento}"
            _arco_de_momento(d, escala.px(carga.x, carga.y), carga.valor, _CARGA, rotulo)
        else:
            _seta_de_carga(d, escala, carga, u)

    for r in solucao.reacoes:
        if solucao.para:
            _seta_de_reacao(d, escala, r, solucao, u)
        x, y = escala.px(r.apoio.x, r.apoio.y)
        lado = 14 * _ESC
        _texto(d, (x + lado, y - lado), r.apoio.nome, tamanho=14)

    for corte in problema.cortes:
        _marca_do_corte(d, escala, corte)

    if solucao.movimento is not None and not solucao.para:
        _texto(
            d, (largura * _ESC / 2, 20 * _ESC), "A peça não fica parada", cor=_TRACAO, tamanho=14
        )
        if solucao.movimento.giro:
            x, y = escala.px(solucao.movimento.x, solucao.movimento.y)
            r_px = 9 * _ESC
            if 0 <= x <= largura * _ESC and 0 <= y <= altura * _ESC:
                d.ellipse([x - r_px, y - r_px, x + r_px, y + r_px], outline=_TRACAO, width=3 * _ESC)
                _texto(d, (x, y + 22 * _ESC), "centro do giro", cor=_TRACAO, tamanho=12)
    return _fechar(imagem, "Peça", "Em laranja as cargas e em verde as reações dos apoios.")


# ---------------------------------------------------------------------------
# Viga
# ---------------------------------------------------------------------------


def _sobrepoe(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def figura_da_viga_compacta(
    viga: bm.Viga, reacoes: Sequence[tuple[float, float, float]]
) -> ImagemDiagrama:
    """A viga com as cargas e as reações, com letra grande, para caber ao lado do formulário.

    ``reacoes`` traz, para cada apoio, (x em mm, força para cima em kN, momento em kN·m). Escala só
    no comprimento: as alturas das cargas dizem o tamanho relativo, não o valor.
    """
    largura, altura = 680, 390
    imagem, d = _nova(largura, altura)
    comprimento = viga.comprimento_mm
    x0, x1 = 60 * _ESC, (largura - 60) * _ESC
    y = 210 * _ESC
    meia = 7 * _ESC

    def px(x_mm: float) -> float:
        return x0 + (x1 - x0) * x_mm / comprimento

    d.rectangle([x0, y - meia, x1, y + meia], fill=_CORPO, outline=_CONTORNO, width=2 * _ESC)

    # Distribuídas: quem se cruza no comprimento sobe um andar.
    andares: list[list[tuple[float, float]]] = []
    maior_w = max(
        [abs(c.w_inicial_N_mm) for c in viga.cargas_distribuidas]
        + [abs(c.w_final) for c in viga.cargas_distribuidas]
        + [1e-9]
    )
    topo_das_distribuidas = float(y - meia)
    for distribuida in viga.cargas_distribuidas:
        faixa = (distribuida.x_inicial_mm, distribuida.x_final_mm)
        andar = next(
            (i for i, faixas in enumerate(andares) if not any(_sobrepoe(faixa, f) for f in faixas)),
            None,
        )
        if andar is None:
            andares.append([])
            andar = len(andares) - 1
        andares[andar].append(faixa)
        base = y - meia - 6 * _ESC - andar * 74 * _ESC
        xa, xb = px(distribuida.x_inicial_mm), px(distribuida.x_final_mm)
        alta = (18 + 34 * abs(distribuida.w_inicial_N_mm) / maior_w) * _ESC
        baixa = (18 + 34 * abs(distribuida.w_final) / maior_w) * _ESC
        para_baixo = distribuida.w_inicial_N_mm + distribuida.w_final <= 0
        d.line([(xa, base - alta), (xb, base - baixa)], fill=_CARGA, width=2 * _ESC)
        quantas = max(2, int((xb - xa) / (34 * _ESC)))
        for i in range(quantas + 1):
            fracao = i / quantas
            xs = xa + (xb - xa) * fracao
            topo = base - (alta + (baixa - alta) * fracao)
            if para_baixo:
                _seta(d, (xs, topo), (xs, base), _CARGA, ponta=8)
            else:
                _seta(d, (xs, base), (xs, topo), _CARGA, ponta=8)
        inicio, fim = abs(distribuida.w_inicial_N_mm), abs(distribuida.w_final)
        texto = (
            f"{_n(inicio)} kN/m" if abs(inicio - fim) < 1e-9 else f"{_n(inicio)} a {_n(fim)} kN/m"
        )
        # O valor sai do meio se ali passa a seta de uma carga concentrada.
        setas = [px(c.x_mm) for c in viga.cargas_pontuais]
        posicoes = (0.5, 0.25, 0.75, 0.12, 0.88)
        fracao_texto = next(
            (f for f in posicoes if all(abs(xa + (xb - xa) * f - s) > 56 * _ESC for s in setas)),
            0.5,
        )
        _texto(
            d,
            (xa + (xb - xa) * fracao_texto, base - max(alta, baixa) - 13 * _ESC),
            texto,
            cor=_CARGA,
            tamanho=14,
        )
        topo_das_distribuidas = min(topo_das_distribuidas, base - max(alta, baixa) - 22 * _ESC)

    # Concentradas: acima de tudo, em dois níveis para os textos não se encostarem.
    ultimo_x = -1e9
    nivel = 0
    for pontual in sorted(viga.cargas_pontuais, key=lambda c: c.x_mm):
        xp = px(pontual.x_mm)
        nivel = (nivel + 1) % 2 if xp - ultimo_x < 90 * _ESC else 0
        ultimo_x = xp
        topo = min(y - 86 * _ESC, topo_das_distribuidas) - nivel * 26 * _ESC
        if pontual.fy_N <= 0:
            _seta(d, (xp, topo), (xp, y - meia - 2 * _ESC), _CARGA, largura=3, ponta=13)
        else:
            _seta(d, (xp, y - meia - 2 * _ESC), (xp, topo), _CARGA, largura=3, ponta=13)
        _texto(
            d,
            (xp, topo - 13 * _ESC),
            f"{_n(abs(pontual.fy_N) / 1000.0)} kN",
            cor=_CARGA,
            tamanho=14,
        )

    for aplicado in viga.momentos:
        xp = px(aplicado.x_mm)
        r = 22 * _ESC
        d.arc([xp - r, y - r, xp + r, y + r], 200, 340, fill=_CARGA, width=2 * _ESC)
        lado = -1.0 if aplicado.mz_Nmm >= 0 else 1.0
        cabeca = (xp + lado * r * 0.94, y - r * 0.34)
        _seta(
            d,
            (cabeca[0] - lado * 7 * _ESC, cabeca[1] - 8 * _ESC),
            (cabeca[0] + lado * 2 * _ESC, cabeca[1] + 3 * _ESC),
            _CARGA,
            ponta=9,
        )
        _texto(
            d,
            (xp, y - r - 13 * _ESC),
            f"{_n(abs(aplicado.mz_Nmm) / 1e6)} kN·m",
            cor=_CARGA,
            tamanho=14,
        )

    # Apoios e reações.
    por_posicao = {round(x, 3): (f, m) for x, f, m in reacoes}
    letras = "ABCDEF"
    for indice, apoio in enumerate(sorted(viga.apoios, key=lambda a: a.x_mm)):
        xp = px(apoio.x_mm)
        forca, momento = por_posicao.get(round(apoio.x_mm, 3), (0.0, 0.0))
        if apoio.tipo == "engaste":
            lado = -1.0 if apoio.x_mm < comprimento / 2.0 else 1.0
            _parede(d, xp, y, 54 * _ESC, lado)
            base = y + 58 * _ESC
        else:
            _apoio_triangulo(d, xp, y + meia, com_rolo=apoio.tipo == "rolete")
            base = y + meia + 36 * _ESC
        tamanho = 46 * _ESC
        if forca >= 0:
            _seta(
                d,
                (xp, base + tamanho + 8 * _ESC),
                (xp, base + 8 * _ESC),
                _REACAO,
                largura=3,
                ponta=13,
            )
        else:
            _seta(
                d,
                (xp, base + 8 * _ESC),
                (xp, base + tamanho + 8 * _ESC),
                _REACAO,
                largura=3,
                ponta=13,
            )
        texto = f"{letras[indice]} = {_n(abs(forca))} kN"
        if abs(momento) > 1e-9:
            texto += f"; {_n(abs(momento))} kN·m"
        ancora = "lm" if xp < (x0 + x1) / 2.0 else "rm"
        deslocado = 12 * _ESC if ancora == "lm" else -12 * _ESC
        _texto(d, (xp + deslocado, base + tamanho), texto, cor=_REACAO, tamanho=14, ancora=ancora)

    y_cota = (altura - 18) * _ESC
    pontos = sorted({0.0, comprimento, *(a.x_mm for a in viga.apoios)})
    d.line([(x0, y_cota), (x1, y_cota)], fill=_NEUTRO, width=_ESC)
    for inicio, fim in zip(pontos, pontos[1:], strict=False):
        for marca in (inicio, fim):
            d.line(
                [(px(marca), y_cota - 6 * _ESC), (px(marca), y_cota + 6 * _ESC)],
                fill=_NEUTRO,
                width=_ESC,
            )
        caixa = ((px(inicio) + px(fim)) / 2.0, y_cota)
        rotulo = f"{_n((fim - inicio) / 1000.0)} m"
        limites = d.textbbox(caixa, rotulo, font=_fonte(13 * _ESC), anchor="mm")
        d.rectangle(
            [limites[0] - 4 * _ESC, limites[1], limites[2] + 4 * _ESC, limites[3]], fill=_FUNDO
        )
        _texto(d, caixa, rotulo, cor=_TEXTO_FRACO, tamanho=13)
    return _fechar(imagem, "Viga", "Cargas em laranja e reações em verde.")
