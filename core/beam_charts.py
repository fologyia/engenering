"""Diagramas de viga desenhados como imagem, para entrar no memorial.

A interface desenha com Altair, que é interativo e vive no navegador. O
memorial em Word e PDF precisa de imagem, e converter Vega-Lite exigiria um
navegador embutido. Aqui os mesmos diagramas são desenhados diretamente com
o Pillow, que já vem junto do Streamlit: sem dependência nova, sem processo
externo e com o resultado reprodutível byte a byte, o que torna o desenho
testável.

O desenho é feito no dobro do tamanho e reduzido no fim: é uma forma barata
de conseguir traço suavizado sem uma biblioteca vetorial.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

# Mesma paleta usada nos gráficos da página, para o memorial não parecer
# outro programa.
COR_NORMAL = "#0f766e"
COR_CORTANTE = "#2563eb"
COR_MOMENTO = "#dc2626"
COR_FLECHA = "#7c3aed"
COR_TORQUE = "#ea580c"

_FUNDO = "#ffffff"
_EIXO = "#334155"
_GRADE = "#e2e8f0"
_ZERO = "#94a3b8"
_TEXTO = "#0f172a"
_TEXTO_FRACO = "#64748b"

_SUPERAMOSTRAGEM = 2


@dataclass(frozen=True, slots=True)
class SerieDiagrama:
    """Uma curva (ou faixa) a desenhar contra a posição ao longo da barra."""

    titulo: str
    unidade: str
    pontos: tuple[tuple[float, float], ...]
    cor: str = COR_CORTANTE
    pontos_inferiores: tuple[tuple[float, float], ...] = ()
    descricao: str = ""

    @property
    def e_faixa(self) -> bool:
        return bool(self.pontos_inferiores)


@dataclass(frozen=True, slots=True)
class ImagemDiagrama:
    """PNG pronto para ser embutido, com a legenda que o acompanha."""

    titulo: str
    legenda: str
    png: bytes
    largura_px: int
    altura_px: int


def _fonte(tamanho: int) -> ImageFont.ImageFont:
    """Fonte escalável sem depender de arquivo do sistema.

    ``load_default(size=...)`` existe desde o Pillow 10.1 e devolve a fonte
    embutida em qualquer plataforma — importante porque o memorial pode ser
    gerado tanto no Windows do usuário quanto no Linux do CI.
    """
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:  # pragma: no cover - Pillow antigo
        return ImageFont.load_default()


def _passo_agradavel(intervalo: float, alvo: int = 6) -> float:
    """Espaçamento de marcação em 1, 2, 2,5 ou 5 vezes uma potência de dez."""
    if intervalo <= 0:
        return 1.0
    bruto = intervalo / max(alvo, 1)
    expoente = math.floor(math.log10(bruto))
    base = 10.0**expoente
    for multiplo in (1.0, 2.0, 2.5, 5.0, 10.0):
        if bruto <= multiplo * base:
            return multiplo * base
    return 10.0 * base  # pragma: no cover - coberto pelo laço acima


def _formatar(valor: float, passo: float) -> str:
    """Casas decimais suficientes para distinguir marcações vizinhas."""
    if abs(valor) < passo * 1e-6:
        return "0"
    casas = max(0, -math.floor(math.log10(passo)) if passo < 1 else 0)
    texto = f"{valor:,.{casas}f}".replace(",", " ")
    return texto


def _limites_y(valores: Sequence[float]) -> tuple[float, float]:
    """Faixa vertical incluindo sempre o zero, com folga para o rótulo."""
    minimo = min([*valores, 0.0])
    maximo = max([*valores, 0.0])
    if minimo == maximo:
        return -1.0, 1.0
    folga = (maximo - minimo) * 0.12
    return minimo - folga, maximo + folga


def renderizar_diagrama(
    serie: SerieDiagrama,
    *,
    largura_px: int = 1000,
    altura_px: int = 300,
) -> ImagemDiagrama:
    """Desenha uma série (ou faixa) e devolve o PNG."""
    if not serie.pontos:
        raise ValueError("A série do diagrama está vazia.")

    escala = _SUPERAMOSTRAGEM
    largura, altura = largura_px * escala, altura_px * escala
    imagem = Image.new("RGB", (largura, altura), _FUNDO)
    desenho = ImageDraw.Draw(imagem)

    fonte_titulo = _fonte(15 * escala)
    fonte_eixo = _fonte(11 * escala)
    fonte_nota = _fonte(11 * escala)

    margem_esq = 78 * escala
    margem_dir = 18 * escala
    margem_topo = 34 * escala
    margem_base = 34 * escala
    area_l = largura - margem_esq - margem_dir
    area_a = altura - margem_topo - margem_base

    xs = [ponto[0] for ponto in serie.pontos]
    ys = [ponto[1] for ponto in serie.pontos]
    if serie.e_faixa:
        ys += [ponto[1] for ponto in serie.pontos_inferiores]
    x_min, x_max = min(xs), max(xs)
    if x_max <= x_min:
        x_max = x_min + 1.0
    y_min, y_max = _limites_y(ys)

    def px(x: float) -> float:
        return margem_esq + (x - x_min) / (x_max - x_min) * area_l

    def py(y: float) -> float:
        return margem_topo + (y_max - y) / (y_max - y_min) * area_a

    # -- grade e marcações --------------------------------------------------
    passo_x = _passo_agradavel(x_max - x_min)
    marca = math.ceil(x_min / passo_x) * passo_x
    while marca <= x_max + passo_x * 1e-9:
        coluna = px(marca)
        desenho.line([(coluna, margem_topo), (coluna, margem_topo + area_a)], fill=_GRADE, width=escala)
        rotulo = _formatar(marca, passo_x)
        largura_rotulo = desenho.textlength(rotulo, font=fonte_eixo)
        desenho.text(
            (coluna - largura_rotulo / 2, margem_topo + area_a + 6 * escala),
            rotulo,
            fill=_TEXTO_FRACO,
            font=fonte_eixo,
        )
        marca += passo_x

    passo_y = _passo_agradavel(y_max - y_min, alvo=4)
    marca = math.ceil(y_min / passo_y) * passo_y
    while marca <= y_max + passo_y * 1e-9:
        linha = py(marca)
        desenho.line([(margem_esq, linha), (margem_esq + area_l, linha)], fill=_GRADE, width=escala)
        rotulo = _formatar(marca, passo_y)
        largura_rotulo = desenho.textlength(rotulo, font=fonte_eixo)
        desenho.text(
            (margem_esq - 8 * escala - largura_rotulo, linha - 7 * escala),
            rotulo,
            fill=_TEXTO_FRACO,
            font=fonte_eixo,
        )
        marca += passo_y

    # -- preenchimento ------------------------------------------------------
    superior = [(px(x), py(y)) for x, y in serie.pontos]
    if serie.e_faixa:
        inferior = [(px(x), py(y)) for x, y in serie.pontos_inferiores]
        poligono = superior + list(reversed(inferior))
    else:
        poligono = [(superior[0][0], py(0.0)), *superior, (superior[-1][0], py(0.0))]
    if len(poligono) >= 3:
        preenchimento = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        ImageDraw.Draw(preenchimento).polygon(
            poligono, fill=_rgba(serie.cor, 60)
        )
        imagem.paste(
            Image.alpha_composite(imagem.convert("RGBA"), preenchimento).convert("RGB"),
            (0, 0),
        )
        desenho = ImageDraw.Draw(imagem)

    # -- eixos e linha de zero ----------------------------------------------
    linha_zero = py(0.0)
    desenho.line(
        [(margem_esq, linha_zero), (margem_esq + area_l, linha_zero)],
        fill=_ZERO,
        width=escala,
    )
    desenho.line(
        [(margem_esq, margem_topo), (margem_esq, margem_topo + area_a)],
        fill=_EIXO,
        width=escala,
    )
    desenho.line(
        [
            (margem_esq, margem_topo + area_a),
            (margem_esq + area_l, margem_topo + area_a),
        ],
        fill=_EIXO,
        width=escala,
    )

    # -- curvas -------------------------------------------------------------
    desenho.line(superior, fill=serie.cor, width=2 * escala, joint="curve")
    if serie.e_faixa:
        # Tracejado manual: o Pillow não tem estilo de linha.
        for inicio, fim in zip(inferior, inferior[1:], strict=False):
            meio = ((inicio[0] + fim[0]) / 2, (inicio[1] + fim[1]) / 2)
            desenho.line([inicio, meio], fill=serie.cor, width=2 * escala)

    # -- extremo destacado ---------------------------------------------------
    indice = max(range(len(serie.pontos)), key=lambda i: abs(serie.pontos[i][1]))
    x_extremo, y_extremo = serie.pontos[indice]
    ponto = (px(x_extremo), py(y_extremo))
    raio = 4 * escala
    desenho.ellipse(
        [ponto[0] - raio, ponto[1] - raio, ponto[0] + raio, ponto[1] + raio],
        fill=serie.cor,
        outline=_FUNDO,
        width=escala,
    )
    anotacao = f"{_formatar(y_extremo, passo_y / 100)} {serie.unidade} em x = {x_extremo:.3g} m"
    largura_anotacao = desenho.textlength(anotacao, font=fonte_nota)
    destino_x = min(max(ponto[0] - largura_anotacao / 2, margem_esq), margem_esq + area_l - largura_anotacao)
    acima = y_extremo >= 0
    destino_y = ponto[1] - 20 * escala if acima else ponto[1] + 8 * escala
    destino_y = min(max(destino_y, margem_topo), margem_topo + area_a - 14 * escala)
    desenho.text((destino_x, destino_y), anotacao, fill=_TEXTO, font=fonte_nota)

    # -- títulos -------------------------------------------------------------
    desenho.text((margem_esq, 8 * escala), serie.titulo, fill=_TEXTO, font=fonte_titulo)
    rotulo_x = "x (m)"
    desenho.text(
        (
            margem_esq + area_l - desenho.textlength(rotulo_x, font=fonte_eixo),
            altura - 16 * escala,
        ),
        rotulo_x,
        fill=_TEXTO_FRACO,
        font=fonte_eixo,
    )

    final = imagem.resize((largura_px, altura_px), Image.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(
        titulo=serie.titulo,
        legenda=serie.descricao or serie.titulo,
        png=buffer.getvalue(),
        largura_px=largura_px,
        altura_px=altura_px,
    )


def _rgba(cor_hex: str, alfa: int) -> tuple[int, int, int, int]:
    texto = cor_hex.lstrip("#")
    return (
        int(texto[0:2], 16),
        int(texto[2:4], 16),
        int(texto[4:6], 16),
        alfa,
    )


def _serie(resultado, atributo: str, escala: float) -> tuple[tuple[float, float], ...]:
    return tuple(
        (ponto.x_mm / 1_000.0, getattr(ponto, atributo) * escala)
        for ponto in resultado.pontos
    )


def series_do_resultado(resultado) -> list[SerieDiagrama]:
    """Diagramas que valem a pena imprimir para esta barra.

    Esforço normal e torque só entram quando existem: um diagrama de torque
    reto no zero ocupa meia página do memorial sem dizer nada.
    """
    series = [
        SerieDiagrama(
            titulo="Esforço cortante V (kN)",
            unidade="kN",
            pontos=_serie(resultado, "cortante_N", 1 / 1_000.0),
            cor=COR_CORTANTE,
            descricao="Diagrama de esforço cortante ao longo da barra.",
        ),
        SerieDiagrama(
            titulo="Momento fletor M (kN·m)",
            unidade="kN·m",
            pontos=_serie(resultado, "momento_Nmm", 1 / 1e6),
            cor=COR_MOMENTO,
            descricao=(
                "Diagrama de momento fletor; positivo comprime a fibra superior."
            ),
        ),
        SerieDiagrama(
            titulo="Linha elástica — flecha (mm)",
            unidade="mm",
            pontos=_serie(resultado, "deslocamento_mm", 1.0),
            cor=COR_FLECHA,
            descricao="Linha elástica; flecha negativa é deslocamento para baixo.",
        ),
    ]
    if any(abs(ponto.normal_N) > 1e-9 for ponto in resultado.pontos):
        series.append(
            SerieDiagrama(
                titulo="Esforço normal N (kN)",
                unidade="kN",
                pontos=_serie(resultado, "normal_N", 1 / 1_000.0),
                cor=COR_NORMAL,
                descricao="Esforço normal; positivo traciona a seção.",
            )
        )
    if any(abs(ponto.torque_Nmm) > 1e-9 for ponto in resultado.pontos):
        series.append(
            SerieDiagrama(
                titulo="Torque T (kN·m)",
                unidade="kN·m",
                pontos=_serie(resultado, "torque_Nmm", 1 / 1e6),
                cor=COR_TORQUE,
                descricao="Torque interno ao longo da barra.",
            )
        )
    return series


def series_da_envoltoria(envoltoria) -> list[SerieDiagrama]:
    """Faixas envelopadas de cortante, momento e flecha."""
    def faixa(atributo_max: str, atributo_min: str, escala: float):
        superior = tuple(
            (ponto.x_mm / 1_000.0, getattr(ponto, atributo_max) * escala)
            for ponto in envoltoria.pontos
        )
        inferior = tuple(
            (ponto.x_mm / 1_000.0, getattr(ponto, atributo_min) * escala)
            for ponto in envoltoria.pontos
        )
        return superior, inferior

    definicoes = (
        ("Envoltória de cortante V (kN)", "kN", "cortante_max_N", "cortante_min_N", 1 / 1_000.0, COR_CORTANTE),
        ("Envoltória de momento M (kN·m)", "kN·m", "momento_max_Nmm", "momento_min_Nmm", 1 / 1e6, COR_MOMENTO),
        ("Envoltória de flecha (mm)", "mm", "flecha_max_mm", "flecha_min_mm", 1.0, COR_FLECHA),
    )
    series = []
    for titulo, unidade, atributo_max, atributo_min, escala, cor in definicoes:
        superior, inferior = faixa(atributo_max, atributo_min, escala)
        series.append(
            SerieDiagrama(
                titulo=titulo,
                unidade=unidade,
                pontos=superior,
                pontos_inferiores=inferior,
                cor=cor,
                descricao=(
                    f"{titulo}: faixa entre o máximo e o mínimo de todas as "
                    "combinações declaradas."
                ),
            )
        )
    return series


def imagens_do_resultado(
    resultado,
    *,
    envoltoria=None,
    largura_px: int = 1000,
    altura_px: int = 280,
) -> list[ImagemDiagrama]:
    """Conjunto de diagramas de uma barra, prontos para o memorial."""
    series = list(series_do_resultado(resultado))
    if envoltoria is not None:
        series.extend(series_da_envoltoria(envoltoria))
    return [
        renderizar_diagrama(serie, largura_px=largura_px, altura_px=altura_px)
        for serie in series
    ]
