"""Figuras das contas no tempo para o memorial (Word e PDF não animam).

Duas formas, desenhadas com o Pillow na densidade de :func:`core.beam_charts.figura_final`:

* :func:`grafico_de_linhas` — curvas contra o tempo (ou contra uma medida, nos perfis), um eixo y
  só, cores das séries em ordem fixa, legenda sempre que houver mais de uma série;
* :func:`mapas_de_calor` — a seção colorida em alguns instantes, lado a lado, com a escala.

O registro guarda os dados de cada figura (:func:`para_o_registro`); o memorial redesenha
(:func:`figuras_do_registro`), como as outras figuras gravadas.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from core.beam_charts import DENSIDADE, ImagemDiagrama, _fonte, _passo_agradavel, figura_final

CORES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
CALOR = ("#fff1e6", "#fdd0b1", "#f9a878", "#f07d45", "#de5524", "#b93a13", "#8a270c", "#5c1a08")
_TEXTO = (15, 23, 42)
_FRACO = (100, 116, 139)
_GRADE = (226, 232, 240)
_EIXO = (51, 65, 85)
CHAVE = "graficos_no_tempo"
Numeros = Sequence[float] | np.ndarray


def _n(valor: float, casas: int) -> str:
    texto = f"{valor:,.{max(0, casas)}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def _casas(passo: float) -> int:
    return 0 if passo >= 1 else min(4, math.ceil(-math.log10(passo) - 1e-9))


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def cor_do_calor(fracao: float) -> tuple[int, int, int]:
    f = min(1.0, max(0.0, fracao if math.isfinite(fracao) else 0.0))
    pos = f * (len(CALOR) - 1)
    i = min(len(CALOR) - 2, int(pos))
    a, b = _rgb(CALOR[i]), _rgb(CALOR[i + 1])
    resto = pos - i
    return tuple(round(a[k] + (b[k] - a[k]) * resto) for k in range(3))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Serie:
    nome: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    tracejada: bool = False


def grafico_de_linhas(
    titulo: str,
    legenda: str,
    rotulo_x: str,
    unidade_y: str,
    series: Sequence[Serie],
    *,
    limites: Sequence[tuple[str, float]] = (),
    marcos: Sequence[tuple[str, float]] = (),
    largura: int = 760,
    altura: int = 300,
) -> ImagemDiagrama:
    """``marcos``: instantes marcados com uma reta vertical tracejada e o nome (estabiliza,
    equaliza, chega ao alvo), na unidade do eixo x."""
    s = DENSIDADE
    imagem = Image.new("RGB", (largura * s, altura * s), (255, 255, 255))
    d = ImageDraw.Draw(imagem)
    fonte = _fonte(11 * s)
    fonte_titulo = _fonte(13 * s)
    xs = [v for serie in series for v in serie.x if math.isfinite(v)]
    ys = [v for serie in series for v in serie.y if math.isfinite(v)]
    ys += [v for _, v in limites]
    if not xs or not ys:
        return figura_final(imagem, titulo, legenda)
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0:
        x1 = x0 + 1.0
    if y1 - y0 < 1e-9 * max(1.0, abs(y1)):
        y0, y1 = y0 - 1.0, y1 + 1.0
    folga = (y1 - y0) * 0.06
    y0, y1 = y0 - folga, y1 + folga
    esq, dir_, topo = 64 * s, 16 * s, 30 * s
    base = 44 * s
    altura_legenda = 18 * s if len(series) > 1 else 0
    area = (esq, topo + altura_legenda, largura * s - dir_, altura * s - base)

    def px(x: float) -> float:
        return area[0] + (x - x0) / (x1 - x0) * (area[2] - area[0])

    def py(y: float) -> float:
        return area[3] - (y - y0) / (y1 - y0) * (area[3] - area[1])

    d.text((esq, 6 * s), f"{titulo} ({unidade_y})", fill=_TEXTO, font=fonte_titulo)
    passo_y = _passo_agradavel(y1 - y0, 4)
    marca = math.ceil(y0 / passo_y) * passo_y
    while marca <= y1 + 1e-9 * passo_y:
        y = py(marca)
        d.line([(area[0], y), (area[2], y)], fill=_GRADE, width=s)
        texto = _n(marca, _casas(passo_y))
        d.text(
            (area[0] - 6 * s - d.textlength(texto, font=fonte), y - 7 * s),
            texto,
            fill=_FRACO,
            font=fonte,
        )
        marca += passo_y
    passo_x = _passo_agradavel(x1 - x0, 6)
    marca = math.ceil(x0 / passo_x) * passo_x
    while marca <= x1 + 1e-9 * passo_x:
        x = px(marca)
        texto = _n(marca, _casas(passo_x))
        d.text(
            (x - d.textlength(texto, font=fonte) / 2, area[3] + 5 * s),
            texto,
            fill=_FRACO,
            font=fonte,
        )
        marca += passo_x
    d.text(
        ((area[0] + area[2]) / 2 - d.textlength(rotulo_x, font=fonte) / 2, area[3] + 22 * s),
        rotulo_x,
        fill=_FRACO,
        font=fonte,
    )
    d.line([(area[0], area[3]), (area[2], area[3])], fill=_EIXO, width=s)
    d.line([(area[0], area[1]), (area[0], area[3])], fill=_EIXO, width=s)
    for nome, valor in limites:
        y = py(valor)
        for k in range(int(area[0]), int(area[2]), 8 * s):
            d.line([(k, y), (min(k + 4 * s, area[2]), y)], fill=_EIXO, width=s)
        d.text((area[0] + 4 * s, y - 15 * s), nome, fill=_EIXO, font=fonte)
    for k, (nome, valor) in enumerate(marcos):
        if not (math.isfinite(valor) and x0 <= valor <= x1):
            continue
        x = px(valor)
        for j in range(int(area[1]), int(area[3]), 8 * s):
            d.line([(x, j), (x, min(j + 4 * s, area[3]))], fill=_EIXO, width=s)
        texto = f"{nome}: {_n(valor, 2 if x1 - x0 < 10 else 1)}"
        largura_texto = d.textlength(texto, font=fonte)
        direita = x > (area[0] + area[2]) / 2
        d.text(
            (
                x - largura_texto - 4 * s if direita else x + 4 * s,
                area[1] + 2 * s + 13 * s * (k % 3),
            ),
            texto,
            fill=_EIXO,
            font=fonte,
        )
    for k, serie in enumerate(series):
        cor = _rgb(CORES[k % len(CORES)])
        pontos = [(px(a), py(b)) for a, b in zip(serie.x, serie.y, strict=True) if math.isfinite(b)]
        if len(pontos) < 2:
            continue
        if serie.tracejada:
            for a, b in zip(pontos[::2], pontos[1::2], strict=False):
                d.line([a, b], fill=cor, width=2 * s)
        else:
            d.line(pontos, fill=cor, width=2 * s, joint="curve")
    if len(series) > 1:
        x = esq
        for k, serie in enumerate(series):
            cor = _rgb(CORES[k % len(CORES)])
            y = topo + 4 * s
            d.line([(x, y + 6 * s), (x + 16 * s, y + 6 * s)], fill=cor, width=3 * s)
            d.text((x + 20 * s, y), serie.nome, fill=_TEXTO, font=fonte)
            x += 30 * s + d.textlength(serie.nome, font=fonte)
    return figura_final(imagem, titulo, legenda)


def mapas_de_calor(
    titulo: str,
    legenda: str,
    xs: Numeros,
    ys: Numeros,
    ativas: Sequence[int] | np.ndarray,
    quadros: Sequence[tuple[str, Numeros]],
    minimo: float,
    maximo: float,
    unidade: str,
    *,
    largura_de_cada: int = 180,
) -> ImagemDiagrama:
    """A seção em alguns instantes: ``ativas`` são os índices i·ny + j das células com material."""
    s = DENSIDADE
    nx, ny = len(xs) - 1, len(ys) - 1
    largura_mm = xs[-1] - xs[0]
    altura_mm = ys[-1] - ys[0]
    escala = largura_de_cada * s / max(largura_mm, altura_mm, 1e-9)
    w = math.ceil(largura_mm * escala)
    h = math.ceil(altura_mm * escala)
    vao = 18 * s
    topo = 26 * s
    total_w = len(quadros) * w + (len(quadros) - 1) * vao + 2 * vao
    total_h = topo + h + 22 * s + 40 * s
    imagem = Image.new("RGB", (max(total_w, 420 * s), total_h), (255, 255, 255))
    d = ImageDraw.Draw(imagem)
    fonte = _fonte(11 * s)
    faixa = maximo - minimo if maximo > minimo else 1.0
    for k, (rotulo, valores) in enumerate(quadros):
        ox = vao + k * (w + vao)
        for indice, valor in zip(ativas, valores, strict=True):
            i, j = divmod(int(indice), ny)
            if not (0 <= i < nx and 0 <= j < ny):
                continue
            a = ox + (xs[i] - xs[0]) * escala
            b = ox + (xs[i + 1] - xs[0]) * escala
            c = topo + h - (ys[j + 1] - ys[0]) * escala
            e = topo + h - (ys[j] - ys[0]) * escala
            d.rectangle(
                [a, c, max(a, b - 0.01), max(c, e - 0.01)],
                fill=cor_do_calor((valor - minimo) / faixa),
            )
        d.text(
            (ox + w / 2 - d.textlength(rotulo, font=fonte) / 2, topo - 18 * s),
            rotulo,
            fill=_TEXTO,
            font=fonte,
        )
    # escala de cores
    y = topo + h + 22 * s
    x0, x1 = vao + 60 * s, vao + 300 * s
    for k in range(int(x1 - x0)):
        d.line([(x0 + k, y), (x0 + k, y + 10 * s)], fill=cor_do_calor(k / (x1 - x0)))
    d.rectangle([x0, y, x1, y + 10 * s], outline=_GRADE, width=s)
    d.text((vao, y - 1 * s), unidade, fill=_FRACO, font=fonte)
    d.text(
        (x0 - d.textlength(_n(minimo, 1), font=fonte) - 4 * s, y + 12 * s),
        _n(minimo, 1),
        fill=_FRACO,
        font=fonte,
    )
    d.text((x1 + 4 * s, y + 12 * s), _n(maximo, 1), fill=_FRACO, font=fonte)
    return figura_final(imagem, titulo, legenda)


# ---------------------------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------------------------
def linhas_para_o_registro(
    titulo: str,
    legenda: str,
    rotulo_x: str,
    unidade_y: str,
    series: Sequence[Serie],
    limites: Sequence[tuple[str, float]] = (),
    marcos: Sequence[tuple[str, float | None]] = (),
) -> dict[str, Any]:
    return {
        "tipo": "linhas",
        "marcos": [
            [nome, float(valor)]
            for nome, valor in marcos
            if valor is not None and math.isfinite(valor)
        ],
        "titulo": titulo,
        "legenda": legenda,
        "rotulo_x": rotulo_x,
        "unidade_y": unidade_y,
        "series": [
            {
                "nome": serie.nome,
                "x": [round(float(v), 6) for v in serie.x],
                "y": [round(float(v), 5) for v in serie.y],
                "tracejada": serie.tracejada,
            }
            for serie in series
        ],
        "limites": [[nome, float(valor)] for nome, valor in limites],
    }


def mapas_para_o_registro(
    titulo: str,
    legenda: str,
    xs: Numeros,
    ys: Numeros,
    ativas: Sequence[int] | np.ndarray,
    quadros: Sequence[tuple[str, Numeros]],
    minimo: float,
    maximo: float,
    unidade: str,
) -> dict[str, Any]:
    return {
        "tipo": "mapas",
        "titulo": titulo,
        "legenda": legenda,
        "xs": [round(float(v), 5) for v in xs],
        "ys": [round(float(v), 5) for v in ys],
        "ativas": [int(v) for v in ativas],
        "quadros": [[rotulo, [round(float(v), 2) for v in valores]] for rotulo, valores in quadros],
        "minimo": float(minimo),
        "maximo": float(maximo),
        "unidade": unidade,
    }


def _numeros(valor: Any) -> tuple[float, ...]:
    if not isinstance(valor, list):
        return ()
    saida = []
    for v in valor:
        try:
            saida.append(float(v))
        except (TypeError, ValueError):
            saida.append(math.nan)
    return tuple(saida)


def figuras_do_registro(resultados: Mapping[str, Any]) -> list[ImagemDiagrama]:
    """As figuras gravadas em ``resultados["graficos_no_tempo"]``, redesenhadas. Dado estragado é
    pulado: a figura não sai, o resto do memorial sai."""
    brutas = resultados.get(CHAVE)
    figuras: list[ImagemDiagrama] = []
    for item in brutas if isinstance(brutas, list) else []:
        if not isinstance(item, Mapping):
            continue
        try:
            if item.get("tipo") == "linhas":
                series = []
                for serie in item.get("series") or []:
                    if not isinstance(serie, Mapping):
                        continue
                    x, y = _numeros(serie.get("x")), _numeros(serie.get("y"))
                    if len(x) == len(y) and len(x) > 1:
                        series.append(
                            Serie(str(serie.get("nome") or ""), x, y, bool(serie.get("tracejada")))
                        )
                if not series:
                    continue
                limites = [
                    (str(lim[0]), float(lim[1]))
                    for lim in item.get("limites") or []
                    if isinstance(lim, list) and len(lim) == 2
                ]
                marcos = [
                    (str(m[0]), float(m[1]))
                    for m in item.get("marcos") or []
                    if isinstance(m, list) and len(m) == 2
                ]
                figuras.append(
                    grafico_de_linhas(
                        str(item.get("titulo") or ""),
                        str(item.get("legenda") or ""),
                        str(item.get("rotulo_x") or ""),
                        str(item.get("unidade_y") or ""),
                        series,
                        limites=limites,
                        marcos=marcos,
                    )
                )
            elif item.get("tipo") == "mapas":
                xs, ys = _numeros(item.get("xs")), _numeros(item.get("ys"))
                ativas = [int(v) for v in item.get("ativas") or []]
                quadros = [
                    (str(q[0]), _numeros(q[1]))
                    for q in item.get("quadros") or []
                    if isinstance(q, list) and len(q) == 2 and len(_numeros(q[1])) == len(ativas)
                ]
                if len(xs) < 2 or len(ys) < 2 or not quadros:
                    continue
                figuras.append(
                    mapas_de_calor(
                        str(item.get("titulo") or ""),
                        str(item.get("legenda") or ""),
                        xs,
                        ys,
                        ativas,
                        quadros,
                        float(item.get("minimo", math.nan)),
                        float(item.get("maximo", math.nan)),
                        str(item.get("unidade") or ""),
                    )
                )
        except (TypeError, ValueError, IndexError, ZeroDivisionError):
            continue
    return figuras
