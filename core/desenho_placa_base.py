"""Desenho da base de pilar (página Placas de base): planta, corte e legenda.

* **Planta**: a placa ℓx × ℓy, o perfil I ou H do pilar (mesas paralelas a y), os chumbadores com o
  furo e a arruela especial (externos, internos, rotulada ou internos e externos), as cotas ℓx, ℓy,
  a₁ (ou 2a₁), a e a₂ e, se houver, a placa de cisalhamento por baixo (tracejada).
* **Corte** pelo plano do momento: o bloco de concreto, a argamassa de assentamento (e_n), a placa
  (t_p), o pilar, os chumbadores com arruela e porca em cima, a porca de nivelamento com arruela
  embaixo da placa (Tabela 18, nota d) e a ponta de cada tipo (porca e chapa,
  guarda-chuva em J, resina do químico ou bucha do parabolt) com o embutimento, a pressão de contato
  no trecho ℓ_c (C1 a C3, T3), a força nos chumbadores tracionados e N, M e V de cálculo.

O momento comprime o lado direito (x > 0) e traciona os chumbadores da esquerda, como no cálculo.
Na flexão oblíqua (M_y, que comprime o lado de cima da planta), a planta mostra a zona comprimida
além da linha neutra inclinada (LN) e o corte, a força do chumbador mais tracionado de cada linha.
"""

from __future__ import annotations

import math
from typing import Any

from PIL import Image, ImageDraw

from core import base_de_pilar as bp
from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, figura_final

ESC = dg.ESC
_PLACA = "#bfdbfe"
_PILAR = "#cbd5e1"
_CONCRETO = "#e7e5e4"
_AGREGADO = "#a8a29e"
_ARGAMASSA = "#d6d3d1"
_CHUMBADOR = "#475569"
_ARRUELA = "#94a3b8"
_PRESSAO = "#1d4ed8"
_TRACAO = "#b91c1c"
_FORCA = "#b45309"
_CISALHAMENTO = "#7c3aed"
_RESINA = "#fbbf24"
_HACHURA = "#60a5fa"
_CONE = "#dc2626"
_ARMADURA = "#6b7280"
_SOLDA = "#334155"
Caixa = tuple[float, float, float, float]
_LARGURA_PX, _ALTURA_PX = 1100, 660

Ponto = tuple[float, float]


def _n(valor: float, casas: int = 0) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _retangulo(
    dr: ImageDraw.ImageDraw, tela: dg.Tela, x0: float, y0: float, x1: float, y1: float, **kw: Any
) -> None:
    """Retângulo em mm (y para cima) como polígono na tela."""
    pontos = [tela(x0, -y0), tela(x1, -y0), tela(x1, -y1), tela(x0, -y1)]
    dr.polygon(pontos, **kw)


def _caixa_do_rotulo(
    dr: ImageDraw.ImageDraw, ponto: Ponto, direcao: Ponto, distancia: float, texto: str, fonte: Any
) -> tuple[float, float, float, float]:
    """Onde :func:`dg.rotulo` poria o texto (px), para testar sobreposição antes de escrever."""
    lugar = dg.mais(ponto, direcao, distancia)
    x0, y0, x1, y1 = dr.textbbox(lugar, texto, font=fonte, anchor=dg.ancora(direcao))
    return x0 - 2 * ESC, y0 - 2 * ESC, x1 + 2 * ESC, y1 + 2 * ESC


def _cruzam(a: Caixa, b: Caixa) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _hachura(
    dr: ImageDraw.ImageDraw, tela: dg.Tela, x0: float, y0: float, x1: float, y1: float, passo: float
) -> None:
    """Linhas a 45° dentro do retângulo [x0, x1] × [y0, y1] (mm, y para cima)."""
    k = x0 - y1
    while k <= x1 - y0:
        xa, xb = max(x0, y0 + k), min(x1, y1 + k)
        if xb > xa:
            dr.line([tela(xa, -(xa - k)), tela(xb, -(xb - k))], fill=_HACHURA, width=ESC)
        k += passo


def _hachura_no_poligono(
    dr: ImageDraw.ImageDraw, tela: dg.Tela, poligono: tuple[Ponto, ...], passo: float
) -> None:
    """Linhas a 45° dentro de um polígono convexo (mm, y para cima)."""
    ks = [x - y for x, y in poligono]
    k = min(ks)
    while k <= max(ks):
        xs: list[float] = []
        for i, (xa, ya) in enumerate(poligono):
            xb, yb = poligono[(i + 1) % len(poligono)]
            fa, fb = ya - xa + k, yb - xb + k  # zero sobre a reta y = x − k
            if (fa <= 0 <= fb or fb <= 0 <= fa) and fa != fb:
                xs.append(xa + fa / (fa - fb) * (xb - xa))
        if len(xs) >= 2 and max(xs) - min(xs) > 1e-6:
            dr.line([tela(min(xs), -(min(xs) - k)), tela(max(xs), -(max(xs) - k))], fill=_HACHURA, width=ESC)  # fmt: skip
        k += passo


def _linha_neutra(g: bp.Geometria, zona: tuple[Ponto, ...]) -> tuple[Ponto, Ponto] | None:
    """O lado da zona comprimida que corta a placa (não fica sobre uma borda dela)."""

    def na_borda(a: Ponto, b: Ponto) -> bool:
        return any(
            abs(a[i] - lado) < 1e-6 and abs(b[i] - lado) < 1e-6
            for i, meio in ((0, g.lx / 2), (1, g.ly / 2))
            for lado in (-meio, meio)
        )

    for i, a in enumerate(zona):
        b = zona[(i + 1) % len(zona)]
        if not na_borda(a, b) and math.dist(a, b) > 1e-6:
            return a, b
    return None


# ------------------------------------------------------------------ planta
def _planta(dr: ImageDraw.ImageDraw, r: bp.ResultadoBase, caixa: tuple[int, int, int, int]) -> None:
    e, g = r.entrada, r.geometria
    tab = bp.TABELA_18[e.chumbador]
    sobra = 0.28 * max(g.lx, g.ly)
    tela = dg.Tela(
        [(-g.lx / 2 - sobra, -(g.ly / 2 + sobra)), (g.lx / 2 + sobra, g.ly / 2 + sobra)], caixa
    )

    def p(x: float, y: float) -> Ponto:
        return tela(x, -y)

    _retangulo(
        dr,
        tela,
        -g.lx / 2,
        -g.ly / 2,
        g.lx / 2,
        g.ly / 2,
        fill=_PLACA,
        outline=dg.COR_LINHA,
        width=2 * ESC,
    )
    # o trecho da placa que aperta o concreto (ℓ_c, na borda comprimida), hachurado
    if r.zona_comprimida:  # flexão oblíqua: a zona além da linha neutra inclinada
        _hachura_no_poligono(dr, tela, r.zona_comprimida, 0.035 * max(g.lx, g.ly))
    elif r.l_c is not None and r.caso in ("C2", "C3", "T3"):
        _hachura(dr, tela, g.lx / 2 - r.l_c, -g.ly / 2, g.lx / 2, g.ly / 2, 0.035 * max(g.lx, g.ly))  # fmt: skip
    # placa de cisalhamento por baixo (tracejada), perpendicular à cortante (ao longo de y)
    if e.cortante == bp.CORTANTE_PLACA:
        x0, x1 = -e.t_pv_mm / 2, e.t_pv_mm / 2
        y0, y1 = -e.b_h_mm / 2, e.b_h_mm / 2
        cantos = [p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)]
        for a, b in zip(cantos, cantos[1:] + cantos[:1], strict=True):
            dg.tracejado(dr, a, b, _CISALHAMENTO, largura=2 * ESC, traco=4 * ESC)
    # o pilar: mesas paralelas a y, alma ao longo de x
    d, bf, tf, tw = g.d, g.b_f, g.t_f, g.t_w
    perfil = [
        (-d / 2, -bf / 2), (-d / 2 + tf, -bf / 2), (-d / 2 + tf, -tw / 2), (d / 2 - tf, -tw / 2),
        (d / 2 - tf, -bf / 2), (d / 2, -bf / 2), (d / 2, bf / 2), (d / 2 - tf, bf / 2),
        (d / 2 - tf, tw / 2), (-d / 2 + tf, tw / 2), (-d / 2 + tf, bf / 2), (-d / 2, bf / 2),
    ]  # fmt: skip
    dr.polygon([p(*q) for q in perfil], fill=_PILAR, outline=dg.COR_LINHA, width=2 * ESC)
    # chumbadores: arruela especial, furo e o chumbador
    lado = tab.lado_da_arruela / 2
    tracionados = {i for i, f in enumerate(r.forcas_nos_chumbadores) if f > 0}
    for i, (x, y) in enumerate(g.posicoes):
        _retangulo(dr, tela, x - lado, y - lado, x + lado, y + lado, fill=_ARRUELA, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        c = p(x, y)
        raio_furo = tab.d_f / 2 * tela.esc
        raio = tab.d_b / 2 * tela.esc
        dr.ellipse([c[0] - raio_furo, c[1] - raio_furo, c[0] + raio_furo, c[1] + raio_furo], fill="#ffffff", outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        cor = _TRACAO if i in tracionados else _CHUMBADOR
        dr.ellipse([c[0] - raio, c[1] - raio, c[0] + raio, c[1] + raio], fill=cor)
    # a linha neutra da flexão oblíqua, tracejada sobre a placa
    neutra = _linha_neutra(g, r.zona_comprimida) if r.zona_comprimida else None
    if neutra is not None:
        a, b = p(*neutra[0]), p(*neutra[1])
        dg.tracejado(dr, a, b, _PRESSAO, largura=2 * ESC, traco=6 * ESC)
        fim = a if a[0] < b[0] else b  # o rótulo na ponta da esquerda, fora da placa
        dg.rotulo(dr, fim, (-0.7, 0.7), 6 * ESC, "LN", _PRESSAO, _fonte(11 * ESC), fundo=True)
    # eixos
    dg.traco_ponto(dr, p(-g.lx / 2 - 0.12 * sobra, 0), p(g.lx / 2 + 0.6 * sobra, 0), dg.COR_COTA)
    dg.traco_ponto(dr, p(0, -g.ly / 2 - 0.12 * sobra), p(0, g.ly / 2 + 0.6 * sobra), dg.COR_COTA)
    fonte = _fonte(11 * ESC)
    dg.rotulo(dr, p(g.lx / 2 + 0.6 * sobra, 0), (1.0, 0.0), 4 * ESC, "x", dg.COR_COTA, fonte)
    if e.tipo != bp.TIPO_INTERNOS_E_EXTERNOS:  # lá, a cota dos internos ocupa esse lugar
        dg.rotulo(dr, p(0, g.ly / 2 + 0.6 * sobra), (0.0, -1.0), 4 * ESC, "y", dg.COR_COTA, fonte)
    # cotas
    baixo, esquerda, cima, direita = (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)
    # a cota d fica entre a mesa e a borda da placa; se não couber, logo abaixo da placa
    folga = (g.ly / 2 - bf / 2) * tela.esc
    cabe = folga >= 26 * ESC
    afastamento_d = 12 * ESC if cabe else folga + 12 * ESC
    afastamento_lx = 34 * ESC if cabe else 40 * ESC
    dg.cota_alinhada(dr, p(-g.lx / 2, -g.ly / 2), p(g.lx / 2, -g.ly / 2), baixo, f"ℓx = {_n(g.lx)}", afastamento_lx, fundo=True)  # fmt: skip
    dg.cota_alinhada(dr, p(-g.lx / 2, -g.ly / 2), p(-g.lx / 2, g.ly / 2), esquerda, f"ℓy = {_n(g.ly)}", 34 * ESC, fundo=True)  # fmt: skip
    x_linha = g.posicoes[0][0]  # a linha mais à esquerda
    externos = e.tipo in (bp.TIPO_1, bp.TIPO_INTERNOS_E_EXTERNOS)
    if externos:  # a₁ da borda ao furo
        dg.cota_alinhada(dr, p(-g.lx / 2, g.ly / 2), p(x_linha, g.ly / 2), cima, f"a₁ = {_n(g.a1)}", 14 * ESC, fundo=True)  # fmt: skip
    else:  # internos: 2·a₁ da borda à face da mesa (Figura 21)
        dg.cota_alinhada(dr, p(-g.lx / 2, g.ly / 2), p(-d / 2, g.ly / 2), cima, f"2a₁ = {_n(2 * g.a1_x)}", 14 * ESC, fundo=True)  # fmt: skip
    if x_linha < 0:  # a rotulada não tem braço: os chumbadores ficam no eixo
        dg.cota_alinhada(dr, p(x_linha, g.ly / 2), p(0, g.ly / 2), cima, f"a = {_n(g.a)}", 14 * ESC, fundo=True)  # fmt: skip
    if e.tipo == bp.TIPO_INTERNOS_E_EXTERNOS:  # o passo dos internos, acima das outras cotas
        dg.cota_alinhada(dr, p(-g.a2 / 2, g.ly / 2), p(g.a2 / 2, g.ly / 2), cima, f"internos a₂ = {_n(g.a2)}", 34 * ESC, fundo=True)  # fmt: skip
    ys = sorted({y for _, y in g.posicoes})
    if len(ys) >= 2:
        dg.cota_alinhada(dr, p(g.lx / 2, ys[0]), p(g.lx / 2, ys[1]), direita, f"a₂ = {_n(ys[1] - ys[0])}", 14 * ESC, fundo=True)  # fmt: skip
    dg.cota_alinhada(dr, p(-d / 2, -bf / 2), p(d / 2, -bf / 2), baixo, f"d = {_n(d)}", afastamento_d, fundo=True)  # fmt: skip
    canto = p(-g.lx / 2, g.ly / 2)
    dr.text(
        (canto[0], canto[1] - 40 * ESC),
        "Planta",
        fill=dg.COR_TEXTO,
        font=_fonte(13 * ESC),
        anchor="lb",
    )


# ------------------------------------------------------------------ corte
def _concreto(
    dr: ImageDraw.ImageDraw, tela: dg.Tela, x0: float, z0: float, x1: float, z1: float
) -> None:
    """O bloco de concreto com os agregados (triângulos e pontos, sempre no mesmo lugar)."""
    _retangulo(dr, tela, x0, z0, x1, z1, fill=_CONCRETO, outline=dg.COR_LINHA, width=2 * ESC)
    largura, altura = x1 - x0, z1 - z0
    passo = max(largura, altura) / 14
    k = 0
    zz = z0 + passo * 0.6
    while zz < z1 - passo * 0.3:
        xx = x0 + passo * (0.5 + 0.37 * (k % 3))
        while xx < x1 - passo * 0.3:
            c = tela(xx, -zz)
            r = 3 * ESC
            if (k % 2) == 0:
                dr.polygon([(c[0], c[1] - r), (c[0] - r, c[1] + r), (c[0] + r, c[1] + r)], outline=_AGREGADO, width=ESC)  # fmt: skip
            else:
                dr.ellipse([c[0] - ESC, c[1] - ESC, c[0] + ESC, c[1] + ESC], fill=_AGREGADO)
            xx += passo * 1.13
            k += 1
        zz += passo * 0.9
        k += 1


def _ponta_do_chumbador(
    dr: ImageDraw.ImageDraw,
    tela: dg.Tela,
    e: bp.EntradaBase,
    tab: bp.LinhaTabela18,
    x: float,
    h: float,
) -> None:
    """O que fica no concreto, antes da haste: o gancho, a resina ou a bucha de expansão."""
    d_b = tab.d_b
    if e.ancoragem == bp.ANCORAGEM_GANCHO:  # guarda-chuva: J virado para o centro do bloco
        sentido = 1.0 if x <= 0 else -1.0
        e_h = e.e_h_mm or 4.5 * d_b
        ponta = x + sentido * e_h
        _retangulo(dr, tela, min(x, ponta) - d_b / 2, -h, max(x, ponta) + d_b / 2, -h + d_b, fill=_CHUMBADOR, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        _retangulo(dr, tela, ponta - d_b / 2, -h, ponta + d_b / 2, -h + 2.5 * d_b, fill=_CHUMBADOR, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    elif e.ancoragem == bp.ANCORAGEM_QUIMICO:  # furo cheio de resina
        meio_furo = max(0.5 * d_b + 3.0, 0.95 * d_b)  # exagerado, para aparecer
        _retangulo(dr, tela, x - meio_furo, -h, x + meio_furo, 0.0, fill=_RESINA, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    elif e.ancoragem == bp.ANCORAGEM_EXPANSAO:  # bucha e cone de expansão na ponta
        meio = 0.7 * d_b
        _retangulo(dr, tela, x - meio, -h, x + meio, -h + 3 * d_b, fill=_ARRUELA, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        cone = [tela(x - meio * 1.25, h), tela(x + meio * 1.25, h), tela(x + meio * 0.6, h - 1.2 * d_b), tela(x - meio * 0.6, h - 1.2 * d_b)]  # fmt: skip
        dr.polygon(cone, fill=_CHUMBADOR, outline=dg.COR_LINHA, width=ESC)


def _corte(dr: ImageDraw.ImageDraw, r: bp.ResultadoBase, caixa: tuple[int, int, int, int]) -> None:
    e, g = r.entrada, r.geometria
    tab = bp.TABELA_18[e.chumbador]
    t_p, e_n = e.t_placa_mm, g.e_n
    bloco = bp.bloco_para_o_cone(e, g, tab)[0]  # o mesmo bloco da verificação do cone
    h = bp.embutimento(e, tab)
    fundo = -1.25 * max(h, tab.h1 * 0.6)
    topo_placa = e_n + t_p
    altura_pilar = 0.45 * g.lx
    topo = topo_placa + altura_pilar
    seta = 0.5 * g.lx  # espaço para N e M em cima do pilar
    tela = dg.Tela(
        [(-bloco / 2 - 0.18 * bloco, -(topo + seta)), (bloco / 2 + 0.22 * bloco, -fundo)], caixa
    )

    def p(x: float, z: float) -> Ponto:
        return tela(x, -z)

    fonte = _fonte(11 * ESC)
    _concreto(dr, tela, -bloco / 2, fundo, bloco / 2, 0.0)
    if e.armadura_de_ancoragem:  # estribos do bloco (Tabela 18), a 60 mm das faces
        cobrimento = 60.0
        cantos = [p(-bloco / 2 + cobrimento, -cobrimento), p(bloco / 2 - cobrimento, -cobrimento), p(bloco / 2 - cobrimento, fundo + cobrimento), p(-bloco / 2 + cobrimento, fundo + cobrimento)]  # fmt: skip
        for a, b in zip(cantos, cantos[1:] + cantos[:1], strict=True):
            dg.tracejado(dr, a, b, _ARMADURA, largura=2 * ESC, traco=5 * ESC)
        for c in cantos:
            dr.ellipse(
                [c[0] - 3 * ESC, c[1] - 3 * ESC, c[0] + 3 * ESC, c[1] + 3 * ESC], fill=_ARMADURA
            )
    tracionados_x = sorted(
        {x for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True) if f > 0}
    )
    mostra_cone = bool(tracionados_x) and (
        e.verificar_concreto or e.ancoragem != bp.ANCORAGEM_PORCA
    )
    if mostra_cone:  # o prisma do cone (ACI 318-19 17.6.2): 1,5·h_ef para cada lado, até a face
        x_esq, x_dir = tracionados_x[0], tracionados_x[-1]

        def _ate_a_face(x_base: float, sentido: float) -> Ponto:
            x_fim = x_base + sentido * 1.5 * h
            if abs(x_fim) <= bloco / 2:
                return p(x_fim, 0.0)
            return p(sentido * bloco / 2, -h + (bloco / 2 - sentido * x_base) / 1.5)

        trechos = [_ate_a_face(x_esq, -1.0), p(x_esq, -h), p(x_dir, -h), _ate_a_face(x_dir, 1.0)]
        for a, b in zip(trechos, trechos[1:], strict=False):
            dg.tracejado(dr, a, b, _CONE, largura=2 * ESC, traco=5 * ESC)
    _retangulo(
        dr, tela, -g.lx / 2, 0.0, g.lx / 2, e_n, fill=_ARGAMASSA, outline=dg.COR_LINHA, width=ESC
    )
    # placa de cisalhamento (abaixo da placa de base, no centro)
    if e.cortante == bp.CORTANTE_PLACA:
        _retangulo(dr, tela, -e.t_pv_mm / 2, e_n - e.b_v_mm, e.t_pv_mm / 2, e_n, fill=_PLACA, outline=_CISALHAMENTO, width=2 * ESC)  # fmt: skip
    _retangulo(dr, tela, -g.lx / 2, e_n, g.lx / 2, topo_placa, fill=_PLACA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
    # o pilar, cortado pela alma, com a interrupção em cima
    d, tf = g.d, g.t_f
    _retangulo(dr, tela, -d / 2 + tf, topo_placa, d / 2 - tf, topo, fill="#f1f5f9", outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    for x0 in (-d / 2, d / 2 - tf):
        _retangulo(dr, tela, x0, topo_placa, x0 + tf, topo, fill=_PILAR, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
    perna = max(0.03 * g.lx, 8.0)  # filete do pilar na placa (desenho, fora de escala)
    for lado in (-1.0, 1.0):
        face = lado * d / 2
        filete = [
            p(face, topo_placa),
            p(face + lado * perna, topo_placa),
            p(face, topo_placa + perna),
        ]
        dr.polygon(filete, fill=_SOLDA)
    k = 0.04 * d
    dr.line([p(-d / 2 - 6, topo), p(-k, topo), p(0, topo + k), p(k, topo - k), p(d / 2 + 6, topo)], fill=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
    # chumbadores: haste, arruela + porca em cima, porca + chapinha embaixo
    raio = tab.d_b / 2
    xs = sorted({x for x, _ in g.posicoes})
    tracionado = {
        x for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True) if f > 0
    }
    setas: list[tuple[Ponto, float]] = []  # ponta da seta e força de cada linha tracionada
    porca = 0.85 * tab.d_b
    for x in xs:
        _ponta_do_chumbador(dr, tela, e, tab, x, h)
        _retangulo(dr, tela, x - raio, -h, x + raio, topo_placa + g.t_arruela + 1.3 * tab.d_b, fill=_CHUMBADOR, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        largura_arruela = tab.lado_da_arruela / 2
        _retangulo(dr, tela, x - largura_arruela, topo_placa, x + largura_arruela, topo_placa + g.t_arruela, fill=_ARRUELA, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
        _retangulo(dr, tela, x - porca, topo_placa + g.t_arruela, x + porca, topo_placa + g.t_arruela + 0.9 * tab.d_b, fill=_ARRUELA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
        nivel = e_n - g.t_arruela  # porca de nivelamento com arruela sob a placa (nota d)
        if nivel - 0.9 * tab.d_b > 2.0:
            _retangulo(dr, tela, x - largura_arruela, nivel, x + largura_arruela, e_n, fill=_ARRUELA, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
            _retangulo(dr, tela, x - porca, nivel - 0.9 * tab.d_b, x + porca, nivel, fill=_ARRUELA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
        if e.ancoragem == bp.ANCORAGEM_PORCA:
            lado_chapa = max(e.chapa_na_ponta_mm / 2, porca)
            _retangulo(dr, tela, x - lado_chapa, -h, x + lado_chapa, -h + 0.9 * tab.d_b, fill=_ARRUELA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
        if x in tracionado:
            forca = max(
                f
                for (xx, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True)
                if xx == x
            )
            base = p(x, topo_placa + g.t_arruela + 1.3 * tab.d_b + 4)
            dg.seta(
                dr, base, (base[0], base[1] - 46 * ESC), _TRACAO, largura=3 * ESC, ponta_px=11 * ESC
            )
            setas.append(((base[0], base[1] - 46 * ESC), forca))
    # o que já ocupa o alto do corte: a seta e o rótulo de N, o arco de M e o topo do pilar
    meio_topo = p(0.0, topo)
    ocupados: list[Caixa] = []
    if e.n_sd_kN:
        ocupados.append((meio_topo[0] - 7 * ESC, meio_topo[1] - 74 * ESC, meio_topo[0] + 7 * ESC, meio_topo[1] - 4 * ESC))  # fmt: skip
        ocupados.append(_caixa_do_rotulo(dr, (meio_topo[0], meio_topo[1] - 70 * ESC), (1.0, -0.4), 6 * ESC, f"N = {_n(abs(e.n_sd_kN), 1)} kN", fonte))  # fmt: skip
    if e.m_sd_kNm:
        centro_m = (meio_topo[0] + 70 * ESC, meio_topo[1] - 36 * ESC)
        ocupados.append((centro_m[0] - 28 * ESC, centro_m[1] - 28 * ESC, centro_m[0] + 28 * ESC, centro_m[1] + 14 * ESC))  # fmt: skip
    canto_esq, canto_dir = p(-d / 2 - 6, topo), p(d / 2 + 6, topo)
    ocupados.append((canto_esq[0], canto_esq[1] - 4 * ESC, canto_dir[0], canto_dir[1] + 4 * ESC))
    # rótulos de F_t: o primeiro lugar (em cima, ao lado, mais acima) que não cruza nada disso,
    # outra seta ou outro rótulo; com 3 ou mais linhas, só o valor
    # no corte, uma haste é a linha inteira: “cada” quando a linha toda tem a mesma força; na
    # flexão oblíqua elas diferem e o rótulo é o do mais tracionado
    forcas_da_linha: dict[float, set[float]] = {}
    for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True):
        forcas_da_linha.setdefault(x, set()).add(round(f, 3))
    iguais = all(len(v) == 1 for v in forcas_da_linha.values())
    cada = (" cada" if iguais else " (o maior)") if len(g.posicoes) > len(xs) else ""
    hastes = [(ponta[0] - 2 * ESC, ponta[1], ponta[0] + 2 * ESC, ponta[1] + 46 * ESC) for ponta, _ in setas]  # fmt: skip
    rotular = list(enumerate(setas))
    if len(setas) > 1 and len({round(f, 3) for _, f in setas}) == 1:
        rotular = rotular[-1:]  # todas iguais (tração centrada): um rótulo só, “cada”
        cada = " cada"
    curto = len(rotular) >= 3
    for i, (ponta, forca) in rotular:
        texto = f"{_n(forca / 1e3, 1)} kN" if curto else f"F_t = {_n(forca / 1e3, 1)} kN{cada}"
        outras = hastes[:i] + hastes[i + 1 :]
        lugares = [((0.0, -1.0), 5.0), ((-1.0, 0.0), 5.0), ((1.0, 0.0), 5.0)]
        lugares += [((0.0, -1.0), 5.0 + 17.0 * k) for k in range(1, 6)]
        if curto:  # em cima primeiro, em níveis, antes de ir para o lado
            lugares = [lugares[0], *lugares[3:6], *lugares[1:3], *lugares[6:]]
        escolhido = lugares[-1]
        for direcao, distancia in lugares:
            caixa_r = _caixa_do_rotulo(dr, ponta, direcao, distancia * ESC, texto, fonte)
            if not any(_cruzam(caixa_r, c) for c in ocupados + outras):
                escolhido = (direcao, distancia)
                break
        direcao, distancia = escolhido
        if distancia > 5.0:  # mais acima: um fio liga o rótulo à seta
            dr.line([ponta, (ponta[0], ponta[1] - distancia * ESC)], fill=_TRACAO, width=ESC)
        ocupados.append(_caixa_do_rotulo(dr, ponta, direcao, distancia * ESC, texto, fonte))
        dg.rotulo(dr, ponta, direcao, distancia * ESC, texto, _TRACAO, fonte, fundo=True)
    # a pressão de contato sob a placa
    if r.l_c is not None and r.caso != "T1" and r.caso != "T2":
        if r.caso == "C1":
            x0, x1 = -g.lx / 2, g.lx / 2
        else:
            x1 = g.lx / 2
            x0 = x1 - r.l_c
        sigma = r.sigma_c_sd if r.sigma_c_sd is not None else r.sigma_c_rd
        altura_px = 22 * ESC
        passos = max(int((x1 - x0) / (g.lx / 14)), 2)
        for k_ in range(passos + 1):
            xx = x0 + (x1 - x0) * k_ / passos
            fim = p(xx, 0.0)
            dg.seta(dr, (fim[0], fim[1] + altura_px), fim, _PRESSAO, largura=ESC, ponta_px=6 * ESC)
        dr.line([(p(x0, 0)[0], p(x0, 0)[1] + altura_px), (p(x1, 0)[0], p(x1, 0)[1] + altura_px)], fill=_PRESSAO, width=2 * ESC)  # fmt: skip
        nome = "σ_c,Sd" if r.sigma_c_sd is not None else "σ_c,Rd"
        texto = f"{nome} = {_n(sigma, 2)} MPa"
        if r.zona_comprimida:
            texto += "\nna zona da planta"
        elif r.caso != "C1":
            texto += f"\nem ℓ_c = {_n(r.l_c)} mm"
        # embaixo das setas: no meio do trecho, ou logo ao lado da haste que atrapalha (dentro do
        # bloco); senão, mais abaixo no meio do trecho, com um fio até as setas
        y_setas = p(x0, 0.0)[1] + altura_px
        centro_zona = (p(x0, 0.0)[0] + p(x1, 0.0)[0]) / 2
        esq, topo_txt, dir_, base_txt = dr.multiline_textbbox((0, 0), texto, font=fonte, anchor="ma", align="center")  # fmt: skip
        meia = (dir_ - esq) / 2
        folga = raio * tela.esc + 5 * ESC
        hastes_x = [p(x, 0.0)[0] for x in xs]
        limite_esq, limite_dir = p(-bloco / 2, 0.0)[0] + 4 * ESC, p(bloco / 2, 0.0)[0] - 4 * ESC

        def _livre(centro: float) -> bool:
            dentro = limite_esq <= centro - meia and centro + meia <= limite_dir
            return dentro and all(abs(hx - centro) >= meia + folga for hx in hastes_x)

        perto = [hx for hx in hastes_x if abs(hx - centro_zona) < meia + folga]
        candidatos = [centro_zona]
        if perto:
            candidatos += [min(perto) - folga - meia, max(perto) + folga + meia]
        centro = next((c for c in candidatos if _livre(c)), None)
        y_texto = y_setas + 5 * ESC
        if centro is None:
            centro = min(max(centro_zona, limite_esq + meia), limite_dir - meia)
            y_texto = y_setas + 34 * ESC
            dr.line([(centro_zona, y_setas), (centro, y_texto)], fill=_PRESSAO, width=ESC)
        caixa_txt = [centro + esq - 2 * ESC, y_texto + topo_txt - 2 * ESC, centro + dir_ + 2 * ESC, y_texto + base_txt + 2 * ESC]  # fmt: skip
        dr.rectangle(caixa_txt, fill="#ffffff")
        dr.multiline_text((centro, y_texto), texto, fill=_PRESSAO, font=fonte, anchor="ma", align="center")  # fmt: skip
    # N, M e V
    if e.n_sd_kN:
        if e.n_sd_kN > 0:
            a, b = (meio_topo[0], meio_topo[1] - 70 * ESC), (meio_topo[0], meio_topo[1] - 8 * ESC)
        else:
            a, b = (meio_topo[0], meio_topo[1] - 8 * ESC), (meio_topo[0], meio_topo[1] - 70 * ESC)
        dg.seta(dr, a, b, _FORCA, largura=3 * ESC, ponta_px=12 * ESC)
        dg.rotulo(dr, (meio_topo[0], meio_topo[1] - 70 * ESC), (1.0, -0.4), 6 * ESC, f"N = {_n(abs(e.n_sd_kN), 1)} kN", _FORCA, fonte, fundo=True)  # fmt: skip
    if e.m_sd_kNm:
        c = (meio_topo[0] + 70 * ESC, meio_topo[1] - 36 * ESC)  # ao lado do N, sem cruzar a seta
        raio_m = 24 * ESC
        dr.arc(
            [c[0] - raio_m, c[1] - raio_m, c[0] + raio_m, c[1] + raio_m],
            160,
            380,
            fill=_FORCA,
            width=3 * ESC,
        )
        t = math.radians(20)
        ponta = (c[0] + raio_m * math.cos(t), c[1] + raio_m * math.sin(t))
        dg.seta(dr, dg.mais(ponta, (math.sin(t), -math.cos(t)), 10 * ESC), ponta, _FORCA, largura=3 * ESC, ponta_px=11 * ESC)  # fmt: skip
        dg.rotulo(dr, c, (1.0, 0.0), raio_m + 8 * ESC, f"M = {_n(abs(e.m_sd_kNm), 1)} kN·m", _FORCA, fonte, fundo=True)  # fmt: skip
    if e.v_sd_kN:
        y_v = p(-g.lx / 2, e_n + t_p / 2)
        dg.seta(dr, (y_v[0] - 60 * ESC, y_v[1]), (y_v[0] - 4 * ESC, y_v[1]), _FORCA, largura=3 * ESC, ponta_px=12 * ESC)  # fmt: skip
        dg.rotulo(dr, (y_v[0] - 60 * ESC, y_v[1]), (0.0, -1.0), 6 * ESC, f"V = {_n(e.v_sd_kN, 1)} kN", _FORCA, fonte, fundo=True)  # fmt: skip
    # cotas do corte
    direita = (1.0, 0.0)
    dg.cota_alinhada(dr, p(g.lx / 2, e_n), p(g.lx / 2, topo_placa), direita, f"t_p = {_n(t_p, 1)}", 16 * ESC, fundo=True)  # fmt: skip
    dg.cota_alinhada(dr, p(g.lx / 2, 0.0), p(g.lx / 2, e_n), direita, f"e_n = {_n(e_n)}", 16 * ESC, posicao=0.5, fundo=True)  # fmt: skip
    nome_h = "h₁" if e.ancoragem == bp.ANCORAGEM_PORCA and not e.h_ef_mm else "h_ef"
    dg.cota_alinhada(dr, p(bloco / 2, -h), p(bloco / 2, 0.0), direita, f"{nome_h} = {_n(h)}", 14 * ESC, fundo=True)  # fmt: skip
    dr.text((caixa[0] * ESC, (caixa[1] - 14) * ESC), "Corte no plano do momento", fill=dg.COR_TEXTO, font=_fonte(13 * ESC), anchor="lb")  # fmt: skip


def _texto_do_bloco(e: bp.EntradaBase, g: bp.Geometria) -> str:
    bx, by, informado = bp.bloco_para_o_cone(e, g, bp.TABELA_18[e.chumbador])
    origem = "" if informado else " (mín. da Tabela 18)"
    return f"Bloco {_n(bx)} × {_n(by)} mm{origem}, f_ck = {_n(e.fck_MPa)} MPa"


def figura_da_base(r: bp.ResultadoBase) -> ImagemDiagrama:
    """A planta, o corte e a legenda da base de pilar."""
    e, g = r.entrada, r.geometria
    tab = bp.TABELA_18[e.chumbador]
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    _planta(dr, r, (40, 110, 470, 520))
    _corte(dr, r, (520, 96, 1080, 540))
    itens: list[tuple[str, str, str]] = [
        (
            "area",
            _PLACA,
            f"Placa {_n(g.lx)} × {_n(g.ly)} × {_n(e.t_placa_mm, 1)} mm ({e.aco_placa})",
        ),
        ("area", _PILAR, f"Pilar {e.perfil}"),
        (
            "area",
            _CHUMBADOR,
            f"{e.n_chumbadores} chumbadores Ø {tab.polegada} {e.aco_chumbador}, "
            f"{bp.ANCORAGENS_CURTAS[e.ancoragem]}",
        ),
        ("area", _ARGAMASSA, f"Argamassa expansiva (e_n = {_n(g.e_n)} mm)"),
        ("area", _CONCRETO, _texto_do_bloco(e, g)),
    ]
    itens2: list[tuple[str, str, str]] = [
        ("seta", _PRESSAO, "Pressão de contato no concreto"),
        ("seta", _TRACAO, "Força nos chumbadores tracionados (em vermelho)"),
        ("seta", _FORCA, "Esforços de cálculo N, M e V"),
    ]
    if e.cortante == bp.CORTANTE_PLACA:
        itens2.append(("tracejado", _CISALHAMENTO, f"Placa de cisalhamento {_n(e.b_h_mm)} × {_n(e.t_pv_mm, 1)} mm, b_v = {_n(e.b_v_mm)} mm"))  # fmt: skip
    if e.ancoragem == bp.ANCORAGEM_QUIMICO:
        itens2.append(("area", _RESINA, "Resina no furo (químico; furo exagerado no desenho)"))
    tracionado = any(f > 0 for f in r.forcas_nos_chumbadores)
    if tracionado and (e.verificar_concreto or e.ancoragem != bp.ANCORAGEM_PORCA):
        itens2.append(("tracejado", _CONE, "Cone de concreto dos tracionados (ACI 318-19)"))
    if e.armadura_de_ancoragem:
        itens2.append(("tracejado", _ARMADURA, "Armadura de ancoragem do bloco"))
    if r.zona_comprimida:
        area = bp._area_e_centro(list(r.zona_comprimida))[0]
        itens.append(
            ("tracejado", _HACHURA, f"Zona comprimida A_c = {_n(area / 100)} cm² (hachura)")
        )
        itens.append(("tracejado", _PRESSAO, "LN: linha neutra da flexão oblíqua"))
    elif r.l_c is not None and r.caso in ("C2", "C3", "T3"):
        itens.append(("tracejado", _HACHURA, f"Placa sob pressão: ℓ_c = {_n(r.l_c)} mm (hachura)"))
    # três colunas de 4 linhas (5 quando há muitos itens; cabem até 15)
    todos = itens[:3] + itens[5:] + itens[3:5] + itens2
    por_coluna = max(4, -(-len(todos) // 3))
    colunas = [todos[k * por_coluna : (k + 1) * por_coluna] for k in range(3)]
    for x_coluna, coluna in zip((40, 420, 760), colunas, strict=True):
        if coluna:
            dg.legenda(dr, x_coluna * ESC, 556 * ESC, coluna)
    caso = {
        "C1": "C1: compressão centrada",
        "C2": "C2: compressão com pequena excentricidade",
        "C3": "C3: compressão com grande excentricidade (chumbadores tracionados)",
        "T1": "T1: tração centrada",
        "T2": "T2: tração com pequena excentricidade",
        "T3": "T3: tração com grande excentricidade",
    }[r.caso]
    titulo = f"Base de pilar — {e.perfil}, {bp.NOMES_CURTOS[e.tipo]}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    obliqua = (
        f" Flexão oblíqua: M_y = {_n(abs(e.m_sd_y_kNm), 1)} kN·m comprime o lado de cima da planta."
        if e.m_sd_y_kNm
        else ""
    )
    dr.text(
        (18 * ESC, 38 * ESC),
        f"Caso {caso} (NBR 8800:2025, 6.7).{obliqua} Cotas em mm.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"Base {bp.NOMES_CURTOS[e.tipo]} do {e.perfil}: placa {_n(g.lx)} × "
        f"{_n(g.ly)} × {_n(e.t_placa_mm, 1)} mm, {e.n_chumbadores} chumbadores Ø {tab.polegada}; caso "
        f"{r.caso}" + (" com flexão oblíqua." if e.m_sd_y_kNm else ".")
    )
    return figura_final(imagem, titulo, legenda)
