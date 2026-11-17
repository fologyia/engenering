"""Gráficos de leitura do memorial: o aproveitamento das verificações e o das combinações.

Barras horizontais, da maior para a menor, com a linha tracejada de 100 %: quem lê o memorial vê
num relance o que está perto do limite e o que passou dele. Feitos para o papel em preto e branco:
as barras que passam são cinza claro com contorno; as que não passam, pretas e com o rótulo em
negrito — a diferença não depende de cor. Pillow, como os outros desenhos do programa.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from core.beam_charts import DENSIDADE, ImagemDiagrama, _fonte, figura_final

ESC = DENSIDADE
_FUNDO = "#ffffff"
_PASSA = "#d1d5db"
_CONTORNO = "#374151"
_REPROVA = "#111827"
_GRADE = "#e5e7eb"
_TEXTO = "#111827"
_FRACO = "#6b7280"
#: Mais que isto e o gráfico mostra só as maiores (o resto está na tabela).
MAXIMO_DE_BARRAS = 30


@dataclass(frozen=True)
class Barra:
    """Uma barra: o rótulo, o valor em %, se reprova e uma nota curta à direita do valor."""

    rotulo: str
    valor: float
    reprova: bool = False
    nota: str = ""
    destaque: bool = False


def _cortar(desenho: ImageDraw.ImageDraw, texto: str, fonte: Any, largura: float) -> str:
    """O texto cabendo em ``largura`` px, com reticências quando precisa."""
    if desenho.textlength(texto, font=fonte) <= largura:
        return texto
    while texto and desenho.textlength(texto + "…", font=fonte) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _valor_texto(valor: float) -> str:
    if math.isinf(valor):
        return "∞"
    return f"{valor:.0f} %"


def grafico_de_barras(
    barras: Sequence[Barra], *, titulo: str, legenda: str, largura_px: int = 900
) -> ImagemDiagrama | None:
    """As barras de aproveitamento (em %), da maior para a menor; None com menos de duas."""
    itens = [b for b in barras if b.valor == b.valor]  # sem NaN
    if len(itens) < 2:
        return None
    itens = sorted(itens, key=lambda b: b.valor if math.isfinite(b.valor) else 1e9, reverse=True)
    cortados = len(itens) > MAXIMO_DE_BARRAS
    itens = itens[:MAXIMO_DE_BARRAS]
    finitos = [b.valor for b in itens if math.isfinite(b.valor)]
    escala_max = min(max(100.0, *finitos, 0.0) * 1.05, 300.0) if finitos else 110.0
    passo_marcas = 25.0 if escala_max <= 150 else 50.0

    fonte = _fonte(12 * ESC)
    fonte_negrito = fonte_em_negrito(12 * ESC)
    fonte_pequena = _fonte(10 * ESC)
    linha_px = 24
    topo_px, base_px = 34, 30
    altura_px = topo_px + linha_px * len(itens) + base_px
    largura = largura_px * ESC
    imagem = Image.new("RGB", (largura, altura_px * ESC), _FUNDO)
    d = ImageDraw.Draw(imagem)

    x_rotulo = 10 * ESC
    x0 = 330 * ESC  # início das barras
    x1 = (largura_px - 150) * ESC  # fim da escala
    y_topo = topo_px * ESC
    y_base = (topo_px + linha_px * len(itens)) * ESC

    def x_de(valor: float) -> float:
        return x0 + (x1 - x0) * min(max(valor, 0.0), escala_max) / escala_max

    # grade e marcas
    marca = 0.0
    while marca <= escala_max + 1e-9:
        x = x_de(marca)
        d.line([(x, y_topo - 4 * ESC), (x, y_base)], fill=_GRADE, width=ESC)
        d.text(
            (x, y_base + 4 * ESC), f"{marca:.0f} %", fill=_FRACO, font=fonte_pequena, anchor="mt"
        )
        marca += passo_marcas
    # a linha de 100 %
    x100 = x_de(100.0)
    y = y_topo - 8 * ESC
    while y < y_base:
        d.line([(x100, y), (x100, min(y + 6 * ESC, y_base))], fill=_CONTORNO, width=2 * ESC)
        y += 11 * ESC
    d.text((x100, y_topo - 10 * ESC), "100 %", fill=_TEXTO, font=fonte_pequena, anchor="mb")

    for k, barra in enumerate(itens):
        meio = y_topo + (k + 0.5) * linha_px * ESC
        alto = 7 * ESC
        fonte_da_linha = fonte_negrito if (barra.reprova or barra.destaque) else fonte
        rotulo = _cortar(d, barra.rotulo, fonte_da_linha, x0 - x_rotulo - 12 * ESC)
        d.text((x0 - 10 * ESC, meio), rotulo, fill=_TEXTO, font=fonte_da_linha, anchor="rm")
        fim = x_de(barra.valor if math.isfinite(barra.valor) else escala_max)
        preenchimento = _REPROVA if barra.reprova else _PASSA
        d.rectangle(
            [x0, meio - alto, max(fim, x0 + ESC), meio + alto],
            fill=preenchimento,
            outline=_CONTORNO,
            width=ESC,
        )
        if barra.valor > escala_max:  # passou da escala: a ponta em seta
            d.polygon(
                [(fim, meio - alto), (fim + 8 * ESC, meio), (fim, meio + alto)], fill=_REPROVA
            )
        texto = _valor_texto(barra.valor) + (f"  {barra.nota}" if barra.nota else "")
        lugar = (max(fim, x0) + 12 * ESC, meio)
        texto = _cortar(d, texto, fonte_da_linha, largura - lugar[0] - 4 * ESC)
        caixa = d.textbbox(lugar, texto, font=fonte_da_linha, anchor="lm")
        d.rectangle(  # fundo branco: o texto passa por cima da linha de 100 % sem se misturar
            [caixa[0] - 3 * ESC, caixa[1] - 2 * ESC, caixa[2] + 3 * ESC, caixa[3] + 2 * ESC],
            fill=_FUNDO,
        )
        d.text(lugar, texto, fill=_TEXTO, font=fonte_da_linha, anchor="lm")
    d.line([(x0, y_topo - 4 * ESC), (x0, y_base)], fill=_CONTORNO, width=ESC)
    if cortados:
        legenda += f" Mostradas as {MAXIMO_DE_BARRAS} maiores; as demais estão na tabela."
    return figura_final(imagem, titulo, legenda)


_NEGRITOS = (
    "segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf",
)  # fmt: skip


@functools.lru_cache(maxsize=16)
def fonte_em_negrito(tamanho: int) -> Any:
    """A versão em negrito da fonte do sistema; sem ela, a regular (o rótulo continua legível)."""
    for nome in _NEGRITOS:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return _fonte(tamanho)


def grafico_das_verificacoes(
    itens: Sequence[tuple[str, float | None, str]],
    *,
    titulo: str = "Aproveitamento das verificações",
) -> ImagemDiagrama | None:
    """(nome, aproveitamento em %, status) das verificações com critério."""
    barras = [
        Barra(nome, float(valor), reprova=status == "NÃO OK")
        for nome, valor, status in itens
        if valor is not None and status in ("OK", "NÃO OK", "ALERTA")
    ]
    return grafico_de_barras(
        barras,
        titulo=titulo,
        legenda=(
            "Aproveitamento (solicitante ÷ resistente) de cada verificação, da maior para a "
            "menor; a linha tracejada marca 100 %. Em preto, as que não atendem."
        ),
    )


def grafico_das_combinacoes(
    itens: Sequence[tuple[str, float | None, str, str]], governante: str = ""
) -> ImagemDiagrama | None:
    """(combinação, aproveitamento máximo em %, verificação que governa nela, status)."""
    barras = [
        Barra(
            nome + ("  (governa)" if nome == governante else ""),
            float(valor),
            reprova=status == "NÃO OK",
            nota=governa,
            destaque=nome == governante,
        )
        for nome, valor, governa, status in itens
        if valor is not None
    ]
    return grafico_de_barras(
        barras,
        titulo="Aproveitamento máximo de cada combinação",
        legenda=(
            "Maior aproveitamento de cada combinação de cálculo e a verificação que o dá; a "
            "combinação que governa a base vem em negrito."
        ),
    )
