"""Peças dos desenhos 2D do núcleo (:class:`core.cena_3d.Desenho2D`): linha, texto, etiqueta,
cota, terreno, apoio e a bolha do eixo, no estilo das páginas (estrutura em grafite, cotas em
cinza, texto com fundo branco onde cruza linhas). A página mostra o desenho em SVG e o memorial em
PNG, os dois iguais. Sem Streamlit.
"""

from __future__ import annotations

import math

from core import cena_3d as c3

COR_TEXTO = "#1f2328"
COR_SUAVE = "#6b7280"
COR_ESTRUTURA = "#3f4652"
COR_TERRENO = "#8a7f72"

Item = c3.Poligono2D | c3.Linha2D | c3.Seta2D | c3.Etiqueta2D
Ponto = tuple[float, float]


def n(valor: float, casas: int = 1) -> str:
    """Número em pt-BR, sem "−0,0"; "∞" quando não é finito."""
    if not math.isfinite(valor):
        return "∞"
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def linha(a: Ponto, b: Ponto, cor: str = COR_ESTRUTURA, largura: float = 2.0,
          tracejado: str = "") -> c3.Linha2D:  # fmt: skip
    return c3.Linha2D(a, b, cor, largura, tracejado)


def texto(x: float, y: float, conteudo: str, *, tamanho: float = 11.0, cor: str = COR_TEXTO,
          peso: str = "normal", ancora: str = "middle", giro: float = 0.0) -> c3.Etiqueta2D:  # fmt: skip
    return c3.Etiqueta2D(x, y, conteudo, cor, tamanho, peso, False, ancora, giro)


def etiqueta(x: float, y: float, conteudo: str, *, tamanho: float = 11.0, cor: str = COR_TEXTO,
             peso: str = "normal", ancora: str = "middle") -> c3.Etiqueta2D:  # fmt: skip
    """Texto sobre fundo branco (não some em cima das linhas)."""
    return c3.Etiqueta2D(x, y, conteudo, cor, tamanho, peso, True, ancora)


def cota(a: Ponto, b: Ponto, conteudo: str, *, tamanho: float = 11.0,
         cor: str = COR_SUAVE) -> list[Item]:  # fmt: skip
    """Linha de cota com traços inclinados nas pontas e o texto ao lado, paralelo à cota (em
    cima na horizontal, à esquerda na vertical)."""
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    if comprimento <= 1e-9:
        return []
    ux, uy = (b[0] - a[0]) / comprimento, (b[1] - a[1]) / comprimento
    partes: list[Item] = [linha(a, b, cor, 1.0)]
    for cx, cy in (a, b):
        partes.append(
            linha(
                (cx - 4 * (ux - uy), cy - 4 * (uy + ux)),
                (cx + 4 * (ux - uy), cy + 4 * (uy + ux)),
                cor,
                1.2,
            )
        )
    giro = math.degrees(math.atan2(uy, ux))
    if giro > 90:
        giro -= 180
    elif giro < -90:
        giro += 180
    nx, ny = math.sin(math.radians(giro)), -math.cos(math.radians(giro))
    mx, my = (a[0] + b[0]) / 2 + 9 * nx, (a[1] + b[1]) / 2 + 9 * ny
    partes.append(texto(mx, my, conteudo, tamanho=tamanho, cor=cor, giro=giro))
    return partes


def terreno(x1: float, x2: float, y: float, passo: float = 9.0) -> list[Item]:
    """Linha do terreno (ou do piso) com hachura embaixo."""
    partes: list[Item] = [linha((x1, y), (x2, y), COR_TERRENO, 1.6)]
    x = x1
    while x < x2:
        partes.append(linha((x, y), (x - 6, y + 7), COR_TERRENO, 0.8))
        x += passo
    return partes


def apoio(x: float, y: float, tamanho: float = 8.0) -> list[Item]:
    """Triângulo de apoio com a hachura embaixo."""
    return [
        c3.Poligono2D(
            ((x, y), (x - tamanho, y + tamanho * 1.1), (x + tamanho, y + tamanho * 1.1)),
            "#ffffff",
            COR_ESTRUTURA,
            1.4,
        ),
        *terreno(x - tamanho - 3, x + tamanho + 3, y + tamanho * 1.1 + 0.5, passo=5),
    ]


def bolha(x: float, y: float, rotulo: str, raio: float = 11.0) -> list[Item]:
    """Círculo com o nome do eixo (1, 2, 3 / A, B, C)."""
    return [
        c3.circulo((x, y), raio, contorno=COR_SUAVE, largura=1.2),
        texto(x, y + 0.5, rotulo, tamanho=raio, cor=COR_SUAVE, peso="bold"),
    ]
