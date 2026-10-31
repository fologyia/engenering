"""Quadro de massa da Lista de material: barras por perfil e por espessura de chapa.

Uma grandeza só (a massa, em kg), numa cor só e num eixo só: cada barra traz o valor e a parte
do total, e a de perfil diz quantas barras de comprimento comercial ela consome. Os maiores vêm
primeiro; passando de :data:`MAXIMO_DE_LINHAS`, o resto vira "Outros".
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core import lista_de_material as lm
from core.beam_charts import ImagemDiagrama, _fonte

ESC = dg.ESC
_BARRA = "#3b82f6"
_GRADE = "#e2e8f0"
_LARGURA_PX = 1000
MAXIMO_DE_LINHAS = 12


@dataclass(frozen=True)
class Linha:
    rotulo: str
    massa_kg: float
    detalhe: str = ""


def _kg(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".") + " kg"


def _passo_bonito(maximo: float) -> float:
    """O passo das linhas de grade: 1, 2 ou 5 × 10ⁿ, com 4 a 6 divisões."""
    bruto = maximo / 5
    potencia = 10 ** math.floor(math.log10(bruto)) if bruto > 0 else 1.0
    for fator in (1, 2, 5, 10):
        if bruto <= fator * potencia:
            return fator * potencia
    return 10 * potencia


def _dobrar(linhas: Sequence[Linha]) -> list[Linha]:
    ordenadas = sorted(linhas, key=lambda x: -x.massa_kg)
    if len(ordenadas) <= MAXIMO_DE_LINHAS:
        return ordenadas
    resto = ordenadas[MAXIMO_DE_LINHAS - 1 :]
    return [
        *ordenadas[: MAXIMO_DE_LINHAS - 1],
        Linha(f"Outros ({len(resto)})", sum(x.massa_kg for x in resto)),
    ]


def _painel(
    dr: ImageDraw.ImageDraw,
    titulo: str,
    linhas: Sequence[Linha],
    total: float,
    topo: float,
    maximo: float,
) -> float:
    """Um painel de barras horizontais a partir de ``topo`` (px); devolve onde ele termina.

    ``maximo`` é o mesmo nos dois painéis: a mesma escala, para comparar perfil com chapa.
    """
    fonte = _fonte(11 * ESC)
    pequena = _fonte(10 * ESC)
    dr.text((24 * ESC, topo), titulo, fill=dg.COR_TEXTO, font=_fonte(13 * ESC))
    x0, x1 = 250 * ESC, 760 * ESC  # a área das barras
    altura_linha = 30 * ESC
    espessura = 14 * ESC
    inicio = topo + 30 * ESC
    passo = _passo_bonito(maximo)
    limite = math.ceil(maximo / passo) * passo
    fim = inicio + altura_linha * len(linhas)
    # grade recessiva, atrás das barras
    k = 0
    while k * passo <= limite + 1e-9:
        x = x0 + (x1 - x0) * k * passo / limite
        dr.line([(x, inicio - 4 * ESC), (x, fim)], fill=_GRADE, width=ESC)
        dr.text((x, fim + 4 * ESC), _kg(k * passo), fill=dg.COR_COTA, font=pequena, anchor="mt")
        k += 1
    dr.line([(x0, inicio - 4 * ESC), (x0, fim)], fill=dg.COR_COTA, width=ESC)
    for i, linha in enumerate(linhas):
        meio = inicio + i * altura_linha + altura_linha / 2
        dr.text((x0 - 10 * ESC, meio), linha.rotulo, fill=dg.COR_TEXTO, font=fonte, anchor="rm")
        comprimento = (x1 - x0) * linha.massa_kg / limite
        if comprimento > 0:
            caixa = [x0, meio - espessura / 2, x0 + max(comprimento, 2 * ESC), meio + espessura / 2]
            dr.rounded_rectangle(caixa, radius=4 * ESC, fill=_BARRA)
            dr.rectangle([x0, caixa[1], x0 + min(4 * ESC, comprimento), caixa[3]], fill=_BARRA)
        parte = f"{100 * linha.massa_kg / total:.0f} %" if total > 0 else ""
        texto = f"{_kg(linha.massa_kg)} · {parte}" + (
            f" · {linha.detalhe}" if linha.detalhe else ""
        )
        dr.text(
            (x0 + comprimento + 8 * ESC, meio), texto, fill=dg.COR_TEXTO, font=pequena, anchor="lm"
        )
    return fim + 26 * ESC


def figura_da_massa(resumo: lm.ResumoDaLista) -> ImagemDiagrama | None:
    """O quadro de massa por perfil e por espessura de chapa; ``None`` se não há nenhum dos dois."""
    perfis = [
        Linha(
            p.perfil,
            p.massa_kg,
            f"{p.barras} barra{'s' if p.barras != 1 else ''} de {resumo.comprimento_barra_m:g} m"
            if p.barras
            else "",
        )
        for p in resumo.perfis
        if p.massa_kg > 0
    ]
    chapas = [
        Linha(f"Chapa {c.espessura_mm:g} mm".replace(".", ","), c.massa_kg, f"{c.pecas} peças")
        for c in resumo.chapas
        if c.massa_kg > 0
    ]
    if not perfis and not chapas:
        return None
    paineis = [
        ("Massa por perfil", _dobrar(perfis)),
        ("Massa das chapas, por espessura", _dobrar(chapas)),
    ]
    paineis = [(t, linhas) for t, linhas in paineis if linhas]
    altura_px = 80 + sum(70 + 30 * len(linhas) for _, linhas in paineis) + 30
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, altura_px * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    total = resumo.massa_itens_kg
    titulo = "Quadro de massa"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        f"Massa dos itens: {_kg(total)} (sem o acréscimo de {resumo.acrescimo_pct:g} % para "
        "soldas, parafusos e perdas). A porcentagem é da massa dos itens.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    topo: float = 76 * ESC
    maximo = max(x.massa_kg for _, linhas in paineis for x in linhas) or 1.0
    for titulo_painel, linhas in paineis:
        topo = _painel(dr, titulo_painel, linhas, total, topo, maximo)
    legenda = (
        f"Massa por perfil ({len(perfis)}) e por espessura de chapa ({len(chapas)}); "
        f"massa dos itens {_kg(total)}."
    )
    final = imagem.resize((_LARGURA_PX, altura_px), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, buffer.getvalue(), _LARGURA_PX, altura_px)
