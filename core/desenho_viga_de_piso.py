"""O esquema da viga de piso: biapoiada, com a carga distribuída, a concentrada no meio, a
deformada, as reações e o vão.

Devolve um :class:`core.cena_3d.Desenho2D`: a página Vigas de piso o mostra em SVG e o memorial o
grava no registro e o desenha em PNG, os dois iguais. Sem Streamlit.
"""

from __future__ import annotations

import math

from core import cena_3d as c3

COR_TEXTO = "#1f2328"
COR_ESTRUTURA = "#5b6470"
COR_DEFORMADA = "#1f6feb"
COR_CARGA = "#cf222e"
COR_CONCENTRADA = "#d4760a"

Item = c3.Poligono2D | c3.Linha2D | c3.Seta2D | c3.Etiqueta2D


def _n(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _texto(x: float, y: float, conteudo: str, *, tamanho: float = 11.0, cor: str = COR_TEXTO,
           peso: str = "normal", ancora: str = "middle") -> c3.Etiqueta2D:  # fmt: skip
    return c3.Etiqueta2D(x, y, conteudo, cor, tamanho, peso, False, ancora)


def _deformada(x0: float, x1: float, y: float, flecha_px: float) -> list[Item]:
    """A curva tracejada (parábola de x0 a x1, descendo ``flecha_px`` no meio)."""
    partes: list[Item] = []
    passos = 40
    pontos = [
        (x0 + (x1 - x0) * k / passos, y + 4 * flecha_px * (k / passos) * (1 - k / passos))
        for k in range(passos + 1)
    ]
    for k in range(0, passos, 2):  # um traço sim, outro não
        partes.append(c3.Linha2D(pontos[k], pontos[k + 1], COR_DEFORMADA, 1.8))
    return partes


def esquema(
    vao_m: float, q_kN_m: float, p_kN: float, flecha_mm: float, reacao_kN: float
) -> c3.Desenho2D:
    """Viga biapoiada com a carga distribuída, a concentrada no meio, a deformada e as reações
    (valores característicos, como a página mostra)."""
    # Sem carga concentrada, não precisa do espaço da seta do P em cima.
    x0, x1, y = 90.0, 550.0, 190.0 if p_kN > 0 else 150.0
    meio = (x0 + x1) / 2
    topo_q = y - 52
    itens: list[Item] = [
        # pino à esquerda, rolete à direita
        c3.Poligono2D(((x0, y + 2), (x0 - 12, y + 22), (x0 + 12, y + 22)), "#ffffff",
                      COR_ESTRUTURA, 1.6),
        c3.Poligono2D(((x1, y + 2), (x1 - 12, y + 18), (x1 + 12, y + 18)), "#ffffff",
                      COR_ESTRUTURA, 1.6),
        c3.circulo((x1, y + 22), 3.5, contorno=COR_ESTRUTURA, largura=1.0, lados=16),
        c3.Linha2D((x0 - 20, y + 26), (x0 + 20, y + 26), COR_ESTRUTURA, 1.2),
        c3.Linha2D((x1 - 20, y + 26), (x1 + 20, y + 26), COR_ESTRUTURA, 1.2),
        *_deformada(x0, x1, y, 24.0),
        c3.Linha2D((x0, y), (x1, y), COR_ESTRUTURA, 5.0),
        c3.Linha2D((x0, topo_q), (x1, topo_q), COR_CARGA, 1.2),
        _texto(x0, topo_q - 14, f"q = {_n(q_kN_m, 2)} kN/m (total)", cor=COR_CARGA,
               ancora="start"),
    ]  # fmt: skip
    passo = (x1 - x0) / 10
    for i in range(11):
        if p_kN > 0 and i == 5:
            continue  # o meio do vão fica para a carga concentrada
        x = x0 + i * passo
        itens.append(c3.Seta2D((x, topo_q), (x, y - 4), COR_CARGA, 1.3, 8.0))
    if p_kN > 0:
        itens.append(c3.Seta2D((meio, topo_q - 48), (meio, y - 4), COR_CONCENTRADA, 2.6, 10.0))
        itens.append(
            _texto(meio + 10, topo_q - 40, f"P = {_n(p_kN, 1)} kN", tamanho=12,
                   cor=COR_CONCENTRADA, peso="bold", ancora="start")
        )  # fmt: skip
    esbeltez = vao_m * 1000 / flecha_mm if flecha_mm > 0 else math.inf
    relacao = f" (L/{esbeltez:.0f})" if math.isfinite(esbeltez) else ""
    itens += [
        _texto(meio, y + 40, f"δ = {_n(flecha_mm, 1)} mm{relacao}", cor=COR_DEFORMADA,
               peso="bold"),
        c3.Seta2D((x0, y + 72), (x0, y + 32), COR_ESTRUTURA, 1.8, 9.0),
        c3.Seta2D((x1, y + 72), (x1, y + 32), COR_ESTRUTURA, 1.8, 9.0),
        _texto(x0 + 8, y + 64, f"R = {_n(reacao_kN, 1)} kN", ancora="start"),
        _texto(x1 - 8, y + 64, f"R = {_n(reacao_kN, 1)} kN", ancora="end"),
        c3.Linha2D((x0, y + 92), (x1, y + 92), COR_TEXTO, 1.0),
        c3.Linha2D((x0, y + 86), (x0, y + 98), COR_TEXTO, 1.0),
        c3.Linha2D((x1, y + 86), (x1, y + 98), COR_TEXTO, 1.0),
        _texto(meio, y + 108, f"L = {_n(vao_m, 2)} m", tamanho=12, peso="bold"),
    ]  # fmt: skip
    return c3.Desenho2D(
        640.0,
        y + 124,
        tuple(itens),
        "Viga de piso biapoiada",
        "Cargas características; a deformada é a da flecha calculada.",
    )
