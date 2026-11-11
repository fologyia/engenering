"""Centro instantâneo de rotação: o equilíbrio que acha o centro e o fator de capacidade do grupo.

Vale para qualquer grupo que gire em torno de um ponto, com a força de cada elemento dada pela
deformação dele: os filetes de solda (NBR 8800 6.2.5.2 b e AISC 360 J2.4, :mod:`core.soldas`) e
os parafusos (AISC Manual, Parte 7, :mod:`core.bolted_connection`). Quem chama dá a lei dos seus
elementos numa função ``forcas(x0, y0, sentido) → (ΣR·dx, ΣR·dy, ΣR·ρ, ΣR)``: a soma das forças
dos elementos girando em torno de (x0, y0) — com o elemento mais afastado na deformação última —,
o momento delas em torno do centro e a soma dos módulos.

A carga é (P_x, P_y) pelo centro geométrico do grupo mais o momento M (anti-horário positivo). O
centro (x0, y0) sai do equilíbrio: ΣR·d = λ·P e ΣR·ρ = λ·M_CI, com M_CI o momento da carga em
torno do centro; λ é quantas vezes a carga cabe no grupo (o aproveitamento é 1/λ). Newton nas
duas coordenadas, amortecido (só aceita o passo que reduz o resíduo). Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

Forcas = Callable[[float, float, float], tuple[float, float, float, float]]


@dataclass(frozen=True)
class Equilibrio:
    """``fator``: quantas vezes a carga cabe no grupo; (x, y): o centro, medido do centro
    geométrico, nas unidades das coordenadas."""

    fator: float
    x: float
    y: float
    convergiu: bool


def resolver(
    forcas: Forcas,
    px: float,
    py: float,
    m: float,
    *,
    escala: float,
    inicio: tuple[float, float],
    limite: float | None = None,
) -> Equilibrio:
    """Acha o centro instantâneo. ``m`` nas unidades de força × coordenada (kN·mm), ``escala``
    a ordem de grandeza das distâncias (adimensionaliza a busca) e ``inicio`` o ponto de partida
    (o centro pelo método elástico).

    ``limite`` (em escalas): a busca para se o centro passa dessa distância. Longe do grupo o
    resíduo das forças cai para zero sozinho (todos os elementos iguais, como na carga pelo
    centro) sem ser o equilíbrio do momento: sem o limite, a busca pode correr para lá."""

    def residuo(xi: float, eta: float) -> tuple[float, float, float]:
        x0, y0 = xi * escala, eta * escala
        m_ci = m - x0 * py + y0 * px
        if abs(m_ci) < 1e-12:
            return 1e6, 1e6, 0.0
        sentido = 1.0 if m_ci > 0 else -1.0
        sx, sy, sm, st = forcas(x0, y0, sentido)
        lam = sm / abs(m_ci)
        norma = max(st, 1e-12)  # a soma das forças dos elementos: vale também sem P
        return (sx - lam * px) / norma, (sy - lam * py) / norma, lam

    xi, eta = inicio[0] / escala, inicio[1] / escala
    r1, r2, lam = residuo(xi, eta)
    convergiu = False
    for _ in range(80):
        erro = math.hypot(r1, r2)
        if erro < 1e-7:
            convergiu = True
            break
        h = 1e-6
        a1, a2, _ = residuo(xi + h, eta)
        b1, b2, _ = residuo(xi, eta + h)
        j11, j21 = (a1 - r1) / h, (a2 - r2) / h
        j12, j22 = (b1 - r1) / h, (b2 - r2) / h
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-14:
            break
        dxi = -(r1 * j22 - r2 * j12) / det
        deta = -(j11 * r2 - j21 * r1) / det
        passo = 1.0
        for _ in range(30):  # Newton amortecido: só aceita o passo que reduz o resíduo
            n1, n2, nlam = residuo(xi + passo * dxi, eta + passo * deta)
            if math.hypot(n1, n2) < erro:
                xi, eta, r1, r2, lam = xi + passo * dxi, eta + passo * deta, n1, n2, nlam
                break
            passo /= 2
        else:
            break
        if limite is not None and math.hypot(xi, eta) > limite:
            break  # correu para longe: não é o equilíbrio
    return Equilibrio(lam, xi * escala, eta * escala, convergiu)
