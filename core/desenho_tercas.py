"""Seção nominal de perfil U enrijecido, com cotas do cálculo."""

from __future__ import annotations

from core import cena_3d as c3
from core import desenho_2d as d2
from core import perfil_i as pi
from core import tercas as tc


def secao(e: tc.EntradaTerca) -> c3.Desenho2D:
    """Mesmo modelo de cinco retângulos usado nas propriedades, sem raios de dobra."""
    tc.secao(e)  # valida as medidas antes de desenhar
    h, b, aba, t = e.bw, e.bf, e.D, e.t
    enq = c3.Enquadramento([(-70, -50), (b + 110, h + 55)], (45, 50, 555, 375))

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, h - y))

    def ret(x0: float, y0: float, x1: float, y1: float) -> c3.Poligono2D:
        return c3.Poligono2D(
            (p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), "#7c9bac", "#345568", 1.0
        )

    itens: list[d2.Item] = [
        ret(0, 0, t, h),
        ret(t, 0, b, t),
        ret(t, h - t, b, h),
        ret(b - t, t, b, t + aba),
        ret(b - t, h - t - aba, b, h - t),
    ]
    itens += d2.cota(p(-25, 0), p(-25, h), f"b_w = {pi.numero(h)} mm")
    itens += d2.cota(p(0, -22), p(b, -22), f"b_f = {pi.numero(b)} mm")
    itens += d2.cota(p(b + 25, t), p(b + 25, t + aba), f"D = {pi.numero(aba)} mm")
    itens.append(
        d2.texto(300, 407, f"Espessura t = {pi.numero(t, 2)} mm · aço {e.aco}", tamanho=11)
    )
    itens.append(
        d2.texto(
            300, 426, "Seção nominal idealizada: sem raios de dobra.", tamanho=10, cor=d2.COR_SUAVE
        )
    )
    return c3.Desenho2D(600, 445, tuple(itens), titulo="Perfil U enrijecido — seção transversal")
