"""Desenhos esquemáticos da emenda de pilar: vista da mesa e vista da alma, com talas, furos e cotas.

Mesmo padrão dos outros desenhos do núcleo (:class:`core.cena_3d.Desenho2D` + :mod:`core.desenho_2d`):
a página mostra em SVG. Sem Streamlit. Coordenadas em mm, com y crescendo para baixo (como na tela);
a linha da emenda fica em y = 0, o pilar superior acima. As talas internas, atrás da mesa, ficam
tracejadas. No U, x = 0 é o dorso da alma (à esquerda na vista da mesa).
"""

from __future__ import annotations

from collections.abc import Sequence

from core import cena_3d as c3
from core import desenho_2d as d2
from core import emenda_pilar as ep

COR_PILAR = "#d9dde3"
COR_TALA = "#9cc3e6"
COR_INTERNA = "#c2410c"
COR_FURO = "#ffffff"
LARGURA, ALTURA = 460.0, 560.0
Faixa = tuple[float, float]


def _retangulo(p, x0: float, y0: float, x1: float, y1: float, cor: str, opacidade: float = 1.0):
    pontos = (p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1))
    return c3.Poligono2D(pontos, cor, d2.COR_ESTRUTURA, 1.0, opacidade)


def _tracejado(p, x0: float, y0: float, x1: float, y1: float) -> list[d2.Item]:
    cantos = [p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)]
    return [
        d2.linha(a, b, COR_INTERNA, 1.4, "5 3")
        for a, b in zip(cantos, cantos[1:] + cantos[:1], strict=True)
    ]


def _vista(
    titulo: str,
    pilar_sup: Faixa,
    pilar_inf: Faixa,
    tala: Faixa,
    xs: Sequence[float],
    n_fileiras: int,
    passo_v: float,
    e_pilar: float,
    e_tala: float,
    gap: float,
    d_h: float,
    nomes: tuple[str, str, str, str],
    internas: Sequence[Faixa] = (),
    cota_x1: float | None = None,
) -> c3.Desenho2D:
    """Uma vista: pilares, tala, furos dos dois lados e as cotas (passo_h, passo_v, e_pilar, e_tala)."""
    meia = gap / 2 + e_pilar + (n_fileiras - 1) * passo_v + e_tala
    altura_pilar = meia + 60
    x_min = min(pilar_sup[0], pilar_inf[0], tala[0])
    x_max = max(pilar_sup[1], pilar_inf[1], tala[1])
    enq = c3.Enquadramento(
        [(x_min - 90, -altura_pilar), (x_max + 90, altura_pilar)],
        (20, 40, LARGURA - 20, ALTURA - 20),
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, y))

    itens: list[d2.Item] = [
        _retangulo(p, pilar_sup[0], -altura_pilar, pilar_sup[1], -gap / 2, COR_PILAR),
        _retangulo(p, pilar_inf[0], gap / 2, pilar_inf[1], altura_pilar, COR_PILAR),
        _retangulo(p, tala[0], -meia, tala[1], meia, COR_TALA, 0.85),
    ]
    for x0, x1 in internas:
        itens += _tracejado(p, x0, -meia, x1, meia)
    itens += [
        d2.linha(p(x_min - 30, 0), p(x_max + 30, 0), d2.COR_SUAVE, 1.0, "6 4"),
        d2.texto(
            p(x_max + 32, 0)[0],
            p(0, 0)[1] - 6,
            "emenda",
            tamanho=10,
            cor=d2.COR_SUAVE,
            ancora="start",
        ),  # fmt: skip
    ]
    raio = d_h / 2 * enq.escala
    for lado in (-1, 1):
        for j in range(n_fileiras):
            y = lado * (gap / 2 + e_pilar + j * passo_v)
            for x in xs:
                itens.append(c3.circulo(p(x, y), raio, preenchimento=COR_FURO,
                                        contorno=d2.COR_ESTRUTURA))  # fmt: skip
    # cotas, no lado de baixo (pilar inferior): e e s à esquerda, a ponta da tala à direita
    y1 = gap / 2 + e_pilar
    x_esq = x_min - 30
    itens += d2.cota(p(x_esq, gap / 2), p(x_esq, y1), f"{nomes[2]} = {d2.n(e_pilar, 0)}")
    if n_fileiras > 1:
        itens += d2.cota(p(x_esq, y1), p(x_esq, y1 + passo_v), f"{nomes[1]} = {d2.n(passo_v, 0)}")
    y_ult = y1 + (n_fileiras - 1) * passo_v
    x_dir = x_max + 45
    itens += d2.cota(p(x_dir, y_ult), p(x_dir, meia), f"{nomes[3]} = {d2.n(e_tala, 0)}")
    if len(xs) > 1:
        y_c = meia + 25
        itens += d2.cota(p(xs[0], y_c), p(xs[1], y_c), f"{nomes[0]} = {d2.n(xs[1] - xs[0], 0)}")
    if cota_x1 is not None:  # U: do dorso da alma (x = 0) à primeira linha de furos
        y_c = meia + 45  # abaixo da cota de g
        itens += d2.cota(p(0.0, y_c), p(cota_x1, y_c), f"x1 = {d2.n(cota_x1, 0)}")
    return c3.Desenho2D(LARGURA, ALTURA, tuple(itens), titulo=titulo)


def vista_da_mesa(r: ep.ResultadoEmenda) -> c3.Desenho2D:
    e, p = r.entrada, r.propriedades
    sup, inf = r.superior, r.inferior
    internas: list[Faixa] = []
    if sup.familia == ep.FAMILIA_U:
        # x a partir do dorso da alma; a tala externa encosta no dorso
        pilar_s, pilar_i, tala = (0.0, sup.bf), (0.0, inf.bf), (0.0, e.bp)
        xs = [e.x1_u + i * e.g for i in range(e.nl)]
        if e.talas_internas:
            internas = [(p["bf_min"] - e.bi, p["bf_min"])]
    else:
        pilar_s, pilar_i = (-sup.bf / 2, sup.bf / 2), (-inf.bf / 2, inf.bf / 2)
        tala = (-e.bp / 2, e.bp / 2)
        xs = ep.posicoes_dos_furos(e.nl, e.g)
        if e.talas_internas:
            b = p["bf_min"] / 2
            internas = [(-b, -b + e.bi), (b - e.bi, b)]
    titulo = f"Vista da mesa — tala {ep._n(e.bp)} × {ep._n(e.tp)} × {ep._n(p['Lp'])}"
    if e.talas_internas:
        titulo += f" + {p['n_int']} internas {ep._n(e.bi)} × {ep._n(e.ti)}"
    return _vista(
        titulo, pilar_s, pilar_i, tala, xs, e.nr, e.s, e.ec, e.ep, e.gap, p["dh"],
        ("g", "s", "e_c", "e_p"), internas,
        e.x1_u if sup.familia == ep.FAMILIA_U else None,
    )  # fmt: skip


def vista_da_alma(r: ep.ResultadoEmenda) -> c3.Desenho2D:
    e, p = r.entrada, r.propriedades
    sup, inf = r.superior, r.inferior
    larg_s = sup.h - 2 * p["R"] if sup.familia == ep.FAMILIA_U else sup.d_linha
    larg_i = inf.h - 2 * p["R"] if inf.familia == ep.FAMILIA_U else inf.d_linha
    return _vista(
        f"Vista da alma — 2 talas {ep._n(e.bw)} × {ep._n(e.twp)} × {ep._n(p['Lw'])} mm",
        (-larg_s / 2, larg_s / 2), (-larg_i / 2, larg_i / 2), (-e.bw / 2, e.bw / 2),
        ep.posicoes_dos_furos(e.nc, e.sh), e.m, e.sv, e.ewc, e.ewv, e.gap, p["dh"],
        ("s_h", "s_v", "e_wc", "e_wv"),
    )  # fmt: skip


def figuras_para_o_registro(r: ep.ResultadoEmenda) -> list[dict[str, object]]:
    """A vista da mesa e a da alma, prontas para o memorial desenhar."""
    return [
        c3.desenho_para_dicionario(
            vista_da_mesa(r),
            legenda="Emenda de pilar: vista da mesa, com a tala externa, os furos e as cotas"
            + (" (talas internas tracejadas)." if r.entrada.talas_internas else "."),
        ),
        c3.desenho_para_dicionario(
            vista_da_alma(r), legenda="Emenda de pilar: vista da alma, com as talas e os furos."
        ),
    ]
