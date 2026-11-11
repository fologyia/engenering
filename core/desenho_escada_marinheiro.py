"""Desenhos da escada marinheiro: a vista de frente (lances, plataformas de descanso, barras,
gaiola e as cotas da NR-12) e a planta (a escada junto da estrutura, a gaiola e as distâncias).

Cada função devolve um :class:`core.cena_3d.Desenho2D`, que a página mostra em SVG e o memorial
desenha em PNG. Sem Streamlit.
"""

from __future__ import annotations

import math

from core import cena_3d as c3
from core import desenho_2d as d2
from core import escada_marinheiro as em
from core.desenho_2d import Item, Ponto

COR_MONTANTE = "#3f4652"
COR_BARRA = "#5b6470"
COR_GAIOLA = "#1f5fbf"
COR_PISO = "#8a7f72"
COR_PLATAFORMA = "#9aa3ad"
COR_ESTRUTURA_FIXA = "#b8bfc8"


def _x_do_lance(e: em.EntradaMarinheiro, i: int) -> float:
    """Eixo do lance i (m): os lances se alternam, afastados entre si."""
    return (i % 2) * e.afastamento_entre_lances_mm / 1000 if e.lances > 1 else 0.0


def frente(r: em.ResultadoMarinheiro) -> c3.Desenho2D:
    """A escada vista de frente, com os lances, as plataformas, a gaiola e as cotas."""
    e = r.entrada
    h_lance = r.altura_do_lance_m
    w, d_g = e.largura_mm / 1000, e.diametro_gaiola_mm / 1000
    acima = max(e.ultrapassa_mm, e.gaiola_ultrapassa_mm if e.gaiola else 0.0) / 1000
    meia = max(w / 2 + e.montante_t_mm / 1000, d_g / 2 if e.gaiola else 0.0)
    xs = [_x_do_lance(e, i) for i in range(e.lances)]
    x_min, x_max = min(xs) - meia, max(xs) + meia
    largura, altura = 960.0, 660.0
    rotulos = ["piso de chegada", "plataforma de descanso"]
    largura_rotulo = max(
        c3.largura_do_texto(f"{rotulo} +{d2.n(e.altura_m, 2)} m", 10) for rotulo in rotulos
    )
    enq = c3.Enquadramento(
        [(x_min - 0.4, 0.0), (x_max + 0.4, -(e.altura_m + acima + 0.2))],
        (190, 80, largura - 150 - largura_rotulo, altura - 100),
    )

    def p(x: float, z: float) -> Ponto:
        return enq((x, -z))

    itens: list[Item] = []
    y0 = p(0, 0)[1]
    xa, xb = p(x_min - 0.6, 0)[0], p(x_max + 0.6, 0)[0]
    itens += d2.terreno(xa, xb, y0 + 1)
    # plataformas de descanso e o piso de chegada
    for k in range(1, e.lances + 1):
        z = k * h_lance
        ya = p(0, z)[1]
        itens.append(
            d2.linha((xa, ya), (xb, ya), COR_PLATAFORMA if k < e.lances else COR_PISO, 4.0)
        )
        rotulo = "piso de chegada" if k == e.lances else "plataforma de descanso"
        itens.append(d2.texto(xb + 6, ya - 9, f"{rotulo} +{d2.n(z, 2)} m", tamanho=10,
                              cor=d2.COR_SUAVE, ancora="start"))  # fmt: skip
    itens.append(d2.texto(xb + 6, y0 - 9, "piso ±0,00", tamanho=10, cor=d2.COR_SUAVE,
                          ancora="start"))  # fmt: skip
    for i, xc in enumerate(xs):
        z0, z1 = i * h_lance, (i + 1) * h_lance
        topo = z1 + e.ultrapassa_mm / 1000
        # gaiola (atrás das barras)
        if e.gaiola:
            zi, zf = z0 + e.inicio_gaiola_mm / 1000, z1 + e.gaiola_ultrapassa_mm / 1000
            if zf > zi:
                canto_a, canto_b = p(xc - d_g / 2, zf), p(xc + d_g / 2, zi)
                itens.append(c3.Poligono2D(
                    (canto_a, (canto_b[0], canto_a[1]), canto_b, (canto_a[0], canto_b[1])),
                    "#eaf1fb", COR_GAIOLA, 1.0, 0.6,
                ))  # fmt: skip
                passo = e.arcos_mm / 1000
                z = zi
                while z <= zf + 1e-9:
                    itens.append(d2.linha(p(xc - d_g / 2, z), p(xc + d_g / 2, z), COR_GAIOLA, 1.4))
                    z += passo
                for k in range(1, 6):  # barras verticais vistas de frente (meia volta)
                    xv = xc + d_g / 2 * math.cos(math.pi * k / 6)
                    itens.append(d2.linha(p(xv, zi), p(xv, zf), COR_GAIOLA, 0.8))
        # montantes e barras
        for lado in (-1, 1):
            xm = xc + lado * (w / 2 + e.montante_t_mm / 2000)
            itens.append(d2.linha(p(xm, z0), p(xm, topo), COR_MONTANTE, 3.2))
        for k in range(r.barras_por_lance):
            z = z0 + (e.primeira_barra_mm + k * e.passo_mm) / 1000
            itens.append(d2.linha(p(xc - w / 2, z), p(xc + w / 2, z), COR_BARRA, 2.0))
    # cotas à esquerda do primeiro lance
    x_esq = p(min(xs) - meia, 0)[0] - 30
    primeira = e.primeira_barra_mm / 1000
    itens += d2.cota((x_esq, p(0, 0)[1]), (x_esq, p(0, primeira)[1]),
                     f"{d2.n(e.primeira_barra_mm, 0)}", tamanho=10)  # fmt: skip
    if r.barras_por_lance > 1:  # o espaçamento numa linha de cota mais para fora
        itens += d2.cota((x_esq - 26, p(0, primeira)[1]),
                         (x_esq - 26, p(0, primeira + e.passo_mm / 1000)[1]),
                         f"{d2.n(e.passo_mm, 0)}", tamanho=10)  # fmt: skip
    x_topo = p(xs[-1] - meia, 0)[0] - 30
    itens += d2.cota((x_topo, p(0, e.altura_m)[1]),
                     (x_topo, p(0, e.altura_m + e.ultrapassa_mm / 1000)[1]),
                     f"{d2.n(e.ultrapassa_mm, 0)}", tamanho=10)  # fmt: skip
    # cotas à direita, depois dos nomes dos pisos: altura total, lances e gaiola
    x_dir = xb + 6 + largura_rotulo + 24
    itens += d2.cota((x_dir + 26, p(0, 0)[1]), (x_dir + 26, p(0, e.altura_m)[1]),
                     f"H = {d2.n(e.altura_m, 2)} m")  # fmt: skip
    if e.lances > 1:
        for i in range(e.lances):
            itens += d2.cota((x_dir, p(0, i * h_lance)[1]), (x_dir, p(0, (i + 1) * h_lance)[1]),
                             f"{d2.n(h_lance, 2)} m", tamanho=10)  # fmt: skip
    if e.gaiola:
        x_g = p(xs[0] + d_g / 2, 0)[0] + 18
        itens += d2.cota((x_g, p(0, 0)[1]), (x_g, p(0, e.inicio_gaiola_mm / 1000)[1]),
                         f"{d2.n(e.inicio_gaiola_mm, 0)}", tamanho=10, cor=COR_GAIOLA)  # fmt: skip
        x_gt = p(xs[-1] + d_g / 2, 0)[0] + 18
        itens += d2.cota((x_gt, p(0, e.altura_m)[1]),
                         (x_gt, p(0, e.altura_m + e.gaiola_ultrapassa_mm / 1000)[1]),
                         f"{d2.n(e.gaiola_ultrapassa_mm, 0)}", tamanho=10, cor=COR_GAIOLA)  # fmt: skip
    # largura e afastamento entre lances, embaixo
    y_baixo = y0 + 30
    xc0 = xs[0]
    itens += d2.cota((p(xc0 - w / 2, 0)[0], y_baixo), (p(xc0 + w / 2, 0)[0], y_baixo),
                     f"{d2.n(e.largura_mm, 0)}", tamanho=10)  # fmt: skip
    if e.lances > 1:
        itens += d2.cota((p(xs[0], 0)[0], y_baixo + 22), (p(xs[1], 0)[0], y_baixo + 22),
                         f"{d2.n(e.afastamento_entre_lances_mm, 0)}", tamanho=10)  # fmt: skip
    legenda: list[tuple[str, str]] = [(COR_MONTANTE, "montante"), (COR_BARRA, "barra (degrau)")]
    if e.gaiola:
        legenda.append((COR_GAIOLA, "gaiola"))
    return c3.Desenho2D(
        largura,
        altura,
        tuple(itens),
        "Escada marinheiro — vista de frente",
        f"{e.lances} lance(s) de {d2.n(h_lance, 2)} m, {r.barras_por_lance} barras por lance; "
        "cotas em mm, alturas em m.",
        legenda=tuple(legenda),
    )


def planta(r: em.ResultadoMarinheiro) -> c3.Desenho2D:
    """A planta: a estrutura, os suportes, os montantes, a barra e a gaiola."""
    e = r.entrada
    w, t, b = e.largura_mm, e.montante_t_mm, e.montante_b_mm
    a = e.afastamento_mm
    d_g = e.diametro_gaiola_mm
    externa = w / 2 + t
    y_c = a + math.sqrt(max((d_g / 2) ** 2 - externa**2, 0.0)) if e.gaiola else a
    fundo = (y_c + d_g / 2) if e.gaiola else a + b
    largura, altura = 640.0, 480.0
    enq = c3.Enquadramento(
        [(-max(d_g / 2, externa) - 80, 0.0), (max(d_g / 2, externa) + 80, fundo + 40)],
        (90, 90, largura - 120, altura - 70),
    )

    def p(x: float, y: float) -> Ponto:
        return enq((x, y))

    itens: list[Item] = []
    # a estrutura em que a escada é fixada (em cima), com hachura
    xa, xb = p(-max(d_g / 2, externa) - 80, 0)[0], p(max(d_g / 2, externa) + 80, 0)[0]
    y_parede = p(0, 0)[1]
    itens.append(d2.linha((xa, y_parede), (xb, y_parede), COR_ESTRUTURA_FIXA, 3.0))
    x = xa
    while x < xb:
        itens.append(d2.linha((x, y_parede), (x + 7, y_parede - 8), COR_ESTRUTURA_FIXA, 0.8))
        x += 9
    itens.append(d2.texto(xa + 4, y_parede - 16, "estrutura", tamanho=10, cor=d2.COR_SUAVE,
                          ancora="start"))  # fmt: skip
    # gaiola: o arco do lado de fora e as barras verticais
    if e.gaiola:
        inicio = math.atan2(a - y_c, externa)
        fim = math.atan2(a - y_c, -externa)
        if fim < inicio:
            fim += 2 * math.pi
        arco = [
            p(d_g / 2 * math.cos(ang), y_c + d_g / 2 * math.sin(ang))
            for ang in (inicio + (fim - inicio) * k / 48 for k in range(49))
        ]
        for q1, q2 in zip(arco, arco[1:], strict=False):
            itens.append(d2.linha(q1, q2, COR_GAIOLA, 2.4))
        n_v = em.barras_verticais_da_gaiola(e)
        for k in range(n_v + 1):
            ang = inicio + (fim - inicio) * k / n_v
            itens.append(c3.circulo(p(d_g / 2 * math.cos(ang), y_c + d_g / 2 * math.sin(ang)),
                                    3.0, preenchimento=COR_GAIOLA, contorno=COR_GAIOLA))  # fmt: skip
        itens += d2.cota(p(-d_g / 2, y_c), p(d_g / 2, y_c), f"Ø {d2.n(d_g, 0)}", cor=COR_GAIOLA)
    # suportes, montantes e a barra
    for lado in (-1, 1):
        xm = lado * (w / 2 + t / 2)
        itens.append(d2.linha(p(xm, 0), p(xm, a - b / 2), COR_PLATAFORMA, 3.0))
        itens.append(c3.Poligono2D(
            (p(xm - t / 2, a - b / 2), p(xm + t / 2, a - b / 2), p(xm + t / 2, a + b / 2),
             p(xm - t / 2, a + b / 2)),
            COR_MONTANTE, COR_MONTANTE,
        ))  # fmt: skip
    itens.append(d2.linha(p(-w / 2, a), p(w / 2, a), COR_BARRA, 3.0))
    # cotas
    itens += d2.cota(p(-externa - 50, 0), p(-externa - 50, a), f"{d2.n(a, 0)}", tamanho=10)
    itens += d2.cota(p(-w / 2, a + b / 2 + 30), p(w / 2, a + b / 2 + 30), f"{d2.n(w, 0)}",
                     tamanho=10)  # fmt: skip
    legenda: list[tuple[str, str]] = [
        (COR_MONTANTE, "montante"),
        (COR_BARRA, "barra"),
        (COR_PLATAFORMA, "suporte"),
    ]
    if e.gaiola:
        legenda.append((COR_GAIOLA, "gaiola"))
    return c3.Desenho2D(
        largura,
        altura,
        tuple(itens),
        "Escada marinheiro — planta",
        "Distância das barras à estrutura, largura entre os montantes e diâmetro da gaiola (mm).",
        legenda=tuple(legenda),
    )


def figuras_para_o_registro(r: em.ResultadoMarinheiro) -> list[dict[str, object]]:
    """A vista de frente e a planta, prontas para o memorial desenhar."""
    return [
        c3.desenho_para_dicionario(
            frente(r),
            legenda="Escada marinheiro vista de frente, com as cotas da NR-12, Anexo III, item 13.",
        ),
        c3.desenho_para_dicionario(
            planta(r),
            legenda="Planta da escada marinheiro: estrutura, suportes, montantes e gaiola.",
        ),
    ]
