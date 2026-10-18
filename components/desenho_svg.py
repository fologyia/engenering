"""Peças de desenho em SVG com um estilo só: setas de vento, cotas, etiquetas, terreno, escala de cor.

Os desenhos das páginas de vento e de contraventamento usam estas peças para ficarem com a mesma
cara: fundo claro, estrutura em grafite, contraventamento em azul, vento em laranja, textos com
fundo branco para não brigarem com as linhas. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from xml.sax.saxutils import escape

# A câmera, o enquadramento e os rótulos são do núcleo da cena 3D (reexportados aqui).
from core.cena_3d import Camera as Camera
from core.cena_3d import Enquadramento as Enquadramento
from core.cena_3d import Rotulos as Rotulos
from core.cena_3d import largura_do_texto as largura_do_texto

FONTE = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
COR_TEXTO = "#1f2328"
COR_SUAVE = "#6b7280"
COR_FUNDO = "#fbfbfd"
COR_BORDA = "#e5e7eb"
COR_ESTRUTURA = "#3f4652"
COR_ESTRUTURA_CLARA = "#aab1bb"
COR_CONTRAVENTADO = "#1f5fbf"
COR_VENTO = "#d4760a"
COR_VENTO_ESCURO = "#a14f00"
COR_TERRENO = "#8a7f72"
COR_PAINEL = "#7c9cc4"

#: Escala da carga: do claro (pouca) ao escuro (muita).
ESCALA_DE_CARGA: tuple[str, ...] = ("#fde7c8", "#f8b46a", "#e5781c", "#b54708", "#7a2e0e")


def n(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    if round(valor, casas) == 0:
        valor = 0.0  # sem "−0,0"
    return f"{valor:.{casas}f}".replace(".", ",")


def _rgb(cor: str) -> tuple[int, int, int]:
    cor = cor.lstrip("#")
    return int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16)


def cor_da_escala(fracao: float, escala: Sequence[str] = ESCALA_DE_CARGA) -> str:
    """Cor da escala para uma fração de 0 a 1 (interpolação linear entre as cores)."""
    f = max(0.0, min(1.0, fracao if math.isfinite(fracao) else 0.0))
    posicao = f * (len(escala) - 1)
    i = min(int(posicao), len(escala) - 2)
    t = posicao - i
    a, b = _rgb(escala[i]), _rgb(escala[i + 1])
    return "#" + "".join(f"{round(a[k] + (b[k] - a[k]) * t):02x}" for k in range(3))


def texto(
    x: float,
    y: float,
    conteudo: str,
    *,
    tamanho: float = 12.0,
    ancora: str = "middle",
    cor: str = COR_TEXTO,
    peso: str = "normal",
    giro: float = 0.0,
    italico: bool = False,
) -> str:
    transforma = f' transform="rotate({giro:.1f} {x:.1f} {y:.1f})"' if giro else ""
    estilo = ' font-style="italic"' if italico else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tamanho}" text-anchor="{ancora}" '
        f'dominant-baseline="middle" font-family="{FONTE}" font-weight="{peso}" fill="{cor}"'
        f"{estilo}{transforma}>{escape(conteudo)}</text>"
    )


def linha(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    cor: str = COR_ESTRUTURA,
    largura: float = 2.0,
    tracejado: str = "",
    opacidade: float = 1.0,
    ponta: str = "round",
) -> str:
    traco = f' stroke-dasharray="{tracejado}"' if tracejado else ""
    alfa = f' stroke-opacity="{opacidade:.2f}"' if opacidade < 1 else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{cor}" '
        f'stroke-width="{largura:.2f}" stroke-linecap="{ponta}"{traco}{alfa}/>'
    )


def poligono(
    pontos: Sequence[tuple[float, float]],
    *,
    preenchimento: str = "none",
    contorno: str = "none",
    largura: float = 1.0,
    opacidade: float = 1.0,
    tracejado: str = "",
) -> str:
    texto_pontos = " ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    traco = f' stroke-dasharray="{tracejado}"' if tracejado else ""
    return (
        f'<polygon points="{texto_pontos}" fill="{preenchimento}" fill-opacity="{opacidade:.2f}" '
        f'stroke="{contorno}" stroke-width="{largura:.2f}" stroke-linejoin="round"{traco}/>'
    )


def seta(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    cor: str = COR_VENTO,
    largura: float = 2.0,
    cabeca: float = 9.0,
) -> str:
    """Seta fina (força): haste e ponta triangular em (x2, y2)."""
    comprimento = math.hypot(x2 - x1, y2 - y1)
    if comprimento <= 1e-9:
        return ""
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    cab = min(cabeca, comprimento * 0.6)
    bx, by = x2 - cab * ux, y2 - cab * uy
    px, py = -uy, ux
    meia = cab * 0.45
    return linha(x1, y1, bx, by, cor=cor, largura=largura) + poligono(
        ((x2, y2), (bx + meia * px, by + meia * py), (bx - meia * px, by - meia * py)),
        preenchimento=cor,
    )


def seta_de_vento(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    espessura: float = 14.0,
    cor: str = COR_VENTO,
) -> str:
    """Seta larga e cheia, com contorno, para a direção do vento."""
    comprimento = math.hypot(x2 - x1, y2 - y1)
    if comprimento <= 1e-9:
        return ""
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    px, py = -uy, ux
    cabeca = min(espessura * 1.6, comprimento * 0.5)
    meia, aba = espessura / 2.0, espessura * 1.05
    bx, by = x2 - cabeca * ux, y2 - cabeca * uy
    pontos = (
        (x1 + meia * px, y1 + meia * py),
        (bx + meia * px, by + meia * py),
        (bx + aba * px, by + aba * py),
        (x2, y2),
        (bx - aba * px, by - aba * py),
        (bx - meia * px, by - meia * py),
        (x1 - meia * px, y1 - meia * py),
    )
    return poligono(pontos, preenchimento=cor, contorno=COR_VENTO_ESCURO, largura=1.0)


def etiqueta(
    x: float,
    y: float,
    conteudo: str,
    *,
    tamanho: float = 11.0,
    cor: str = COR_TEXTO,
    fundo: str = "#ffffff",
    borda: str = COR_BORDA,
    peso: str = "normal",
    ancora: str = "middle",
) -> str:
    """Texto sobre uma pílula branca (não some em cima das linhas)."""
    largura = largura_do_texto(conteudo, tamanho) + 10
    altura = tamanho + 7
    if ancora == "start":
        x0 = x - 5
    elif ancora == "end":
        x0 = x - largura + 5
    else:
        x0 = x - largura / 2
    return (
        f'<rect x="{x0:.1f}" y="{y - altura / 2:.1f}" width="{largura:.1f}" height="{altura:.1f}" '
        f'rx="{altura / 2:.1f}" fill="{fundo}" fill-opacity="0.92" stroke="{borda}" '
        f'stroke-width="0.8"/>'
        + texto(x, y + 0.5, conteudo, tamanho=tamanho, cor=cor, peso=peso, ancora=ancora)
    )


def cota(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    conteudo: str,
    *,
    afastamento: float = 0.0,
    cor: str = COR_SUAVE,
    tamanho: float = 11.0,
) -> str:
    """Linha de cota com traços inclinados nas pontas e o texto no meio (paralelo à cota)."""
    comprimento = math.hypot(x2 - x1, y2 - y1)
    if comprimento <= 1e-9:
        return ""
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    px, py = -uy * afastamento, ux * afastamento
    a = (x1 + px, y1 + py)
    b = (x2 + px, y2 + py)
    partes = [linha(*a, *b, cor=cor, largura=1.0)]
    if afastamento:
        partes.append(linha(x1, y1, a[0], a[1], cor=cor, largura=0.6, tracejado="2 2"))
        partes.append(linha(x2, y2, b[0], b[1], cor=cor, largura=0.6, tracejado="2 2"))
    for cx, cy in (a, b):
        partes.append(
            linha(
                cx - 4 * (ux - uy),
                cy - 4 * (uy + ux),
                cx + 4 * (ux - uy),
                cy + 4 * (uy + ux),
                cor=cor,
                largura=1.2,
            )
        )
    giro = math.degrees(math.atan2(uy, ux))
    if giro > 90:
        giro -= 180
    elif giro < -90:
        giro += 180
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    partes.append(
        f'<g transform="rotate({giro:.1f} {mx:.1f} {my:.1f})">'
        + etiqueta(mx, my, conteudo, tamanho=tamanho, cor=cor, borda="none")
        + "</g>"
    )
    return "".join(partes)


def terreno(x1: float, x2: float, y: float, *, passo: float = 9.0) -> str:
    """Linha do terreno com hachura."""
    partes = [linha(x1, y, x2, y, cor=COR_TERRENO, largura=1.6)]
    x = x1
    while x < x2:
        partes.append(linha(x, y, x - 6, y + 7, cor=COR_TERRENO, largura=0.8))
        x += passo
    return "".join(partes)


def apoio(x: float, y: float, *, tamanho: float = 8.0, cor: str = COR_ESTRUTURA) -> str:
    """Triângulo de apoio com a hachura embaixo."""
    return poligono(
        ((x, y), (x - tamanho, y + tamanho * 1.1), (x + tamanho, y + tamanho * 1.1)),
        preenchimento="#ffffff",
        contorno=cor,
        largura=1.4,
    ) + terreno(x - tamanho - 3, x + tamanho + 3, y + tamanho * 1.1 + 0.5, passo=5)


def bolha(x: float, y: float, rotulo: str, *, raio: float = 11.0, cor: str = COR_SUAVE) -> str:
    """Círculo com o nome do eixo (1, 2, 3 / A, B, C)."""
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{raio:.1f}" fill="#ffffff" stroke="{cor}" '
        f'stroke-width="1.2"/>' + texto(x, y + 0.5, rotulo, tamanho=raio, cor=cor, peso="bold")
    )


def escala_de_cor(
    x: float,
    y: float,
    largura: float,
    minimo: float,
    maximo: float,
    unidade: str,
    *,
    titulo: str = "",
    escala: Sequence[str] = ESCALA_DE_CARGA,
) -> str:
    """Barra de cores com os valores nas pontas."""
    passos = 24
    partes = []
    for i in range(passos):
        partes.append(
            f'<rect x="{x + largura * i / passos:.1f}" y="{y:.1f}" '
            f'width="{largura / passos + 0.6:.1f}" height="9" '
            f'fill="{cor_da_escala(i / (passos - 1), escala)}"/>'
        )
    partes.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{largura:.1f}" height="9" fill="none" '
        f'stroke="{COR_BORDA}" stroke-width="0.8"/>'
    )
    partes.append(texto(x, y + 19, n(minimo, 2), tamanho=10, ancora="start", cor=COR_SUAVE))
    partes.append(
        texto(
            x + largura,
            y + 19,
            f"{n(maximo, 2)} {unidade}",
            tamanho=10,
            ancora="end",
            cor=COR_SUAVE,
        )
    )
    if titulo:
        partes.append(texto(x, y - 8, titulo, tamanho=10.5, ancora="start", cor=COR_SUAVE))
    return "".join(partes)


def legenda(x: float, y: float, itens: Sequence[tuple[str, str, str]], *, passo: float = 0) -> str:
    """Itens (cor, tracejado, texto) numa linha a partir de (x, y)."""
    partes = []
    for cor, tracejado, rotulo in itens:
        partes.append(linha(x, y, x + 20, y, cor=cor, largura=3, tracejado=tracejado))
        partes.append(texto(x + 26, y, rotulo, tamanho=11, ancora="start", cor=COR_SUAVE))
        x += passo or (34 + 6.1 * len(rotulo))
    return "".join(partes)


def documento(
    largura: float,
    altura: float,
    corpo: Sequence[str],
    titulo: str,
    *,
    subtitulo: str = "",
    mostrar_titulo: bool = True,
) -> str:
    """O SVG com fundo, borda arredondada e o título no canto."""
    cabecalho = ""
    if mostrar_titulo:
        cabecalho = texto(22, 24, titulo, tamanho=15, ancora="start", peso="bold")
        if subtitulo:
            cabecalho += texto(22, 44, subtitulo, tamanho=11, ancora="start", cor=COR_SUAVE)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.0f} {altura:.0f}" '
        f'width="{largura:.0f}" height="{altura:.0f}" role="img">'
        f"<title>{escape(titulo)}</title>"
        f'<rect x="0.5" y="0.5" width="{largura - 1:.0f}" height="{altura - 1:.0f}" rx="10" '
        f'fill="{COR_FUNDO}" stroke="{COR_BORDA}"/>' + cabecalho + "".join(corpo) + "</svg>"
    )
