"""Seção da monovia e pontos de contato das rodas com a mesa inferior."""

from __future__ import annotations

from core import cena_3d as c3
from core import desenho_2d as d2
from core import monovia as mo
from core import perfil_i as pi


def secao(e: mo.EntradaMonovia) -> c3.Desenho2D:
    """Seção proporcional do perfil; diâmetro das rodas é simbólico e não é entrada."""
    v = mo.obter_perfil(e)
    d, bf, tf, tw = v.d, v.bf, v.tf, v.tw
    enq = c3.Enquadramento(
        [(-bf / 2 - 95, -d / 2 - 70), (bf / 2 + 95, d / 2 + 70)], (40, 55, 550, 375)
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    def ret(x0: float, y0: float, x1: float, y1: float) -> c3.Poligono2D:
        return c3.Poligono2D(
            (p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), "#a8c0cf", "#344e5e", 1.4
        )

    itens: list[d2.Item] = [
        ret(-tw / 2, -d / 2, tw / 2, d / 2),
        ret(-bf / 2, d / 2 - tf, bf / 2, d / 2),
        ret(-bf / 2, -d / 2, bf / 2, -d / 2 + tf),
    ]
    contato = bf / 2 - e.n_roda
    for x in [contato] if e.rodas_por_eixo == 1 else [-contato, contato]:
        cx, cy = p(x, -d / 2 + tf)
        # Ponto de contato: marca independente da dimensão desconhecida da roda.
        itens.append(c3.circulo((cx, cy), 4.5, preenchimento="#b45309", contorno="#b45309"))
        itens.append(d2.linha((cx, cy - 28), (cx, cy - 6), "#b45309", 2.0))
        itens.append(c3.Seta2D((cx, cy - 28), (cx, cy - 6), "#b45309", 2.0, 6.0))
    itens += d2.cota(p(-bf / 2, -d / 2 - 25), p(bf / 2, -d / 2 - 25), f"b_f = {pi.numero(bf)} mm")
    itens += d2.cota(p(bf / 2 + 32, -d / 2), p(bf / 2 + 32, d / 2), f"d = {pi.numero(d)} mm")
    itens += d2.cota(
        p(contato, -d / 2 - 48), p(bf / 2, -d / 2 - 48), f"n = {pi.numero(e.n_roda)} mm"
    )
    itens.append(
        d2.texto(
            295, 413, f"{e.rodas_por_eixo} roda(s) por eixo · contato na mesa inferior", tamanho=11
        )
    )
    itens.append(
        d2.texto(
            295,
            433,
            "Roda única à direita por convenção; a forma das rodas não é modelada."
            if e.rodas_por_eixo == 1
            else "Setas indicam contatos; forma e dimensão das rodas não são modeladas.",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    return c3.Desenho2D(590, 455, tuple(itens), titulo=f"Seção da monovia — {v.nome}")
