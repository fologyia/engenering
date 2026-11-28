"""Elevação frontal da chapa da ligação 4E a partir dos dados de cálculo."""

from __future__ import annotations

from core import bolted_connection as bc
from core import cena_3d as c3
from core import desenho_2d as d2
from core import ligacao_rigida as lr


def vista_chapa(e: lr.EntradaRigida, *, esp_enrijecedor: float | None = None) -> c3.Desenho2D:
    """Mostra as duas fileiras tracionadas 4E; demais parafusos não são posicionados no modelo."""
    v = e.viga.perfil()
    sup = v.d / 2 + e.pfo + e.de
    inf = -v.d / 2 - (e.pfo + e.de if e.simetrica else 0)
    limite = max(e.bp, v.bf) / 2
    enquadramento = c3.Enquadramento(
        [(-limite - 80, -sup - 50), (limite + 110, -inf + 50)], (40, 45, 510, 420)
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return enquadramento((x, -y))

    def ret(x0: float, y0: float, x1: float, y1: float, cor: str) -> c3.Poligono2D:
        return c3.Poligono2D(
            (p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), cor, d2.COR_ESTRUTURA, 1.0
        )

    itens: list[d2.Item] = [
        ret(-e.bp / 2, inf, e.bp / 2, sup, "#d9e8ef"),
        ret(-v.tw / 2, -v.d / 2, v.tw / 2, v.d / 2, "#7b96a5"),
        ret(-v.bf / 2, v.d / 2 - v.tf, v.bf / 2, v.d / 2, "#526d7c"),
        ret(-v.bf / 2, -v.d / 2, v.bf / 2, -v.d / 2 + v.tf, "#526d7c"),
    ]
    if esp_enrijecedor is not None:
        itens.append(ret(-esp_enrijecedor / 2, v.d / 2, esp_enrijecedor / 2, sup, "#8bbbd2"))
    y_exterior = v.d / 2 + e.pfo
    y_interior = v.d / 2 - v.tf - e.pfi
    raio = bc.dados_parafuso(e.diametro)["d_h"] * enquadramento.escala / 2
    for y in (y_exterior, y_interior):
        for x in (-e.g / 2, e.g / 2):
            cx, cy = p(x, y)
            itens.append(c3.circulo((cx, cy), raio, preenchimento="#ffffff", contorno="#334155"))
            itens.append(d2.linha((cx - 4, cy), (cx + 4, cy), d2.COR_SUAVE, 0.7))
            itens.append(d2.linha((cx, cy - 4), (cx, cy + 4), d2.COR_SUAVE, 0.7))
    itens += d2.cota(p(-e.g / 2, sup + 22), p(e.g / 2, sup + 22), f"g = {lr._n(e.g)} mm")
    itens += d2.cota(p(limite + 28, v.d / 2), p(limite + 28, y_exterior), f"pfo = {lr._n(e.pfo)}")
    itens += d2.cota(
        p(-limite - 28, y_interior), p(-limite - 28, v.d / 2 - v.tf), f"pfi = {lr._n(e.pfi)}"
    )
    itens.append(
        d2.texto(
            275,
            458,
            f"Chapa {lr._n(e.bp)} × {lr._n(e.tp)} mm · furo Ø {lr._n(bc.dados_parafuso(e.diametro)['d_h'])} mm",
            tamanho=11,
        )
    )
    itens.append(
        d2.texto(
            275,
            479,
            "Fileiras comprimidas não representadas: posições não informadas no cálculo.",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    configuracao = "4ES" if esp_enrijecedor is not None else "4E"
    return c3.Desenho2D(
        550, 500, tuple(itens), titulo=f"Chapa de extremidade {configuracao} — vista frontal"
    )
