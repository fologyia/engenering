"""Elevação esquemática de nós tubulares planos T/Y, X e K/N."""

from __future__ import annotations

import math

from core import cena_3d as c3
from core import desenho_2d as d2
from core import nos_tubulares as nt


def elevacao(e: nt.EntradaNo) -> c3.Desenho2D:
    """Contornos projetados no plano, sem espessura, recortes reais ou cordões de solda."""
    if nt.validar(e):
        raise ValueError("Geometria do nó inválida.")
    h0 = e.banzo.b if e.forma == nt.CIRCULAR else e.banzo.h
    h1 = e.diagonal1.b if e.forma == nt.CIRCULAR else e.diagonal1.h
    h2 = e.diagonal2.b if e.forma == nt.CIRCULAR else e.diagonal2.h
    comprimento = 2.3 * h0
    w1 = h1 / math.sin(math.radians(e.theta1))
    w2 = h2 / math.sin(math.radians(e.theta2))
    lado_banzo = max(2.4 * h0, e.g / 2 + w1 + comprimento, e.g / 2 + w2 + comprimento)
    ysuper = h0 / 2
    ramos: list[tuple[list[tuple[float, float]], str]] = []

    def ramo(esquerda: float, largura: float, angulo: float, dx: int, dy: int, nome: str) -> None:
        y = dy * ysuper
        avanco_x = dx * comprimento * math.cos(math.radians(angulo))
        avanco_y = dy * comprimento * math.sin(math.radians(angulo))
        a, b = esquerda, esquerda + largura
        ramos.append(
            ([(a, y), (b, y), (b + avanco_x, y + avanco_y), (a + avanco_x, y + avanco_y)], nome)
        )

    if e.tipo == nt.NO_K:
        ramo(-e.g / 2 - w1, w1, e.theta1, -1, 1, "Diagonal 1")
        ramo(e.g / 2, w2, e.theta2, 1, 1, "Diagonal 2")
    else:
        ramo(-w1 / 2, w1, e.theta1, 1, 1, "Diagonal 1")
        if e.tipo == nt.NO_X:
            ramo(-w1 / 2, w1, e.theta1, -1, -1, "Diagonal oposta")
    pontos = [(-lado_banzo, -h0 / 2), (lado_banzo, h0 / 2)] + [
        p for ramo_, _ in ramos for p in ramo_
    ]

    # O enquadramento considera o mesmo sinal vertical da projeção.
    enq = c3.Enquadramento([(x, -y) for x, y in pontos], (50, 75, 670, 300))

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    itens: list[d2.Item] = [
        c3.Poligono2D(
            (
                p(-lado_banzo, -h0 / 2),
                p(lado_banzo, -h0 / 2),
                p(lado_banzo, h0 / 2),
                p(-lado_banzo, h0 / 2),
            ),
            "#bdcbd3",
            "#415e6c",
            1.2,
        )
    ]
    for pts, _ in ramos:
        itens.append(c3.Poligono2D(tuple(p(x, y) for x, y in pts), "#dbeaf0", "#426a7c", 1.5))
    if e.tipo == nt.NO_K:
        itens += d2.cota(p(-e.g / 2, ysuper), p(e.g / 2, ysuper), f"g = {nt._n(e.g)} mm")
    itens.append(d2.texto(360, 340, f"{e.tipo} · {e.forma}", tamanho=11))
    itens.append(
        d2.texto(
            360,
            359,
            f"θ₁ = {nt._n(e.theta1)}°"
            + (f" · θ₂ = {nt._n(e.theta2)}°" if e.tipo == nt.NO_K else ""),
            tamanho=11,
        )
    )
    itens.append(
        d2.texto(
            360,
            379,
            "Elevação esquemática: sem recortes de encaixe, soldas ou terminações reais.",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    return c3.Desenho2D(720, 400, tuple(itens), titulo="Nó tubular — elevação no plano")
