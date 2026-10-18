"""Planta das bordas do piso: chapas, vigas e os trechos de guarda-corpo, acesso e borda sem viga.

Devolve texto SVG para ``st.image``. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from components import desenho_svg as d
from core import cargas_pelo_modelo as cpm
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import vento_por_barras as vpb

COR_GUARDA_CORPO = "#1f5fbf"
COR_ACESSO = "#d4760a"
COR_SEM_VIGA = "#c62828"
COR_DESMARCADO = "#9aa3ad"
COR_A_MAO = "#7c3aed"
COR_PISO = "#e9eef5"
COR_LANCE = "#f3efe6"


def _planta(p: Sequence[float], eixo_vertical: str) -> tuple[float, float]:
    x, y, _ = vpb.para_a_planta(p, eixo_vertical)
    return x, y


def svg_bordas_do_piso(
    bordas: gm.BordasDoPiso,
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    escolha: Mapping[str, bool] | None = None,
) -> str:
    """A planta (de cima) com o que o programa achou: guarda-corpo (azul, com os montantes),
    acesso da escada (laranja), borda sem viga (vermelho) e o que o engenheiro desmarcou (cinza)."""
    largura, altura = 900.0, 600.0
    escolha = escolha or {}
    try:
        chapas, _ = cpm.chapas_do_piso(g, eixo_vertical)
    except (ArithmeticError, ValueError, IndexError):
        chapas = []
    poligonos = []
    for c in chapas:
        pontos = [_planta(gm._no_espaco(c, q), eixo_vertical) for q in c.poligono]
        buracos = [[_planta(gm._no_espaco(c, q), eixo_vertical) for q in a] for a in c.aberturas]
        poligonos.append((c, pontos, buracos))
    barras = [
        (c, _planta(c.inicio, eixo_vertical), _planta(c.fim, eixo_vertical))
        for c in g.corpos
        if c.e_barra and gm._corpo_valido(c)
    ]
    todos = [p for _, pts, _ in poligonos for p in pts]
    todos += [p for _, a, b in barras for p in (a, b)]
    todos += [_planta(p, eixo_vertical) for t in bordas.trechos for p in (t.inicio, t.fim)]
    if not todos:
        todos = [(0.0, 0.0), (1.0, 1.0)]
    enq = d.Enquadramento([(x, -y) for x, y in todos], (60, 90, largura - 60, altura - 70))

    def t(p: tuple[float, float]) -> tuple[float, float]:
        return enq((p[0], -p[1]))

    corpo: list[str] = []
    for c, pontos, buracos in poligonos:
        cor = COR_LANCE if c.inclinacao_graus > gm.INCLINACAO_DE_ESCADA_GRAUS else COR_PISO
        corpo.append(
            d.poligono([t(p) for p in pontos], preenchimento=cor, contorno="#c3ccd8", largura=0.8)
        )
        for b in buracos:
            corpo.append(
                d.poligono(
                    [t(p) for p in b], preenchimento=d.COR_FUNDO, contorno="#c3ccd8", largura=0.8
                )
            )
        if c.inclinacao_graus > gm.INCLINACAO_DE_ESCADA_GRAUS and len(pontos) >= 3:
            # degraus sugeridos: linhas paralelas ao lado mais curto
            xs = [p[0] for p in pontos]
            ys = [p[1] for p in pontos]
            corpo.append(
                d.texto(
                    *t((sum(xs) / len(xs), sum(ys) / len(ys))),
                    f"lance {c.inclinacao_graus:.0f}°",
                    tamanho=9.5,
                    cor=d.COR_SUAVE,
                )
            )
    for _c, a, b in barras:
        corpo.append(d.linha(*t(a), *t(b), cor="#b8c0ca", largura=1.6))
    rotulos = d.Rotulos((10, 60, largura - 10, altura - 40))
    for trecho in bordas.trechos:
        a, b = _planta(trecho.inicio, eixo_vertical), _planta(trecho.fim, eixo_vertical)
        pa, pb = t(a), t(b)
        marcado = bordas.marcado(trecho, escolha)
        if trecho.situacao == gm.SITUACAO_ACESSO_MAO:
            cor, tracejado, espessura = COR_A_MAO, "2 3", 3.0
        elif trecho.situacao == gm.SITUACAO_MAO:
            cor, tracejado, espessura = COR_A_MAO, "", 4.0
        elif trecho.situacao == gm.SITUACAO_ACESSO:
            cor, tracejado, espessura = COR_ACESSO, "6 4", 3.0
        elif trecho.situacao == gm.SITUACAO_SEM_VIGA:
            cor, tracejado, espessura = COR_SEM_VIGA, "3 3", 3.0
        elif not marcado:
            cor, tracejado, espessura = COR_DESMARCADO, "2 3", 2.6
        else:
            cor = COR_GUARDA_CORPO
            tracejado = "8 3" if trecho.situacao == gm.SITUACAO_ESCADA else ""
            espessura = 4.0
        corpo.append(d.linha(*pa, *pb, cor=cor, largura=espessura, tracejado=tracejado))
        if marcado and trecho.situacao in gm.COM_GUARDA_CORPO:
            # montantes a cada ~1 m
            comprimento = math.dist(pa, pb)
            if comprimento > 0:
                n = max(1, round(trecho.comprimento_m))
                ux, uy = (pb[0] - pa[0]) / comprimento, (pb[1] - pa[1]) / comprimento
                for k in range(n + 1):
                    x = pa[0] + (pb[0] - pa[0]) * k / n
                    y = pa[1] + (pb[1] - pa[1]) * k / n
                    corpo.append(
                        d.linha(
                            x - 4 * uy, y + 4 * ux, x + 4 * uy, y - 4 * ux, cor=cor, largura=1.4
                        )
                    )
        meio = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
        if trecho.situacao in gm.COM_GUARDA_CORPO:
            rotulo = trecho.id
        elif trecho.situacao in (gm.SITUACAO_ACESSO, gm.SITUACAO_ACESSO_MAO):
            rotulo = f"{trecho.id} acesso"
        else:
            rotulo = f"{trecho.id} ?"
        corpo.append(d.etiqueta(*rotulos.lugar(*meio, rotulo, 9.5), rotulo, tamanho=9.5, cor=cor))
    marcados = bordas.marcados(escolha)
    total = sum(x.comprimento_m for x in marcados)
    corpo.append(
        d.legenda(
            22,
            altura - 18,
            (
                (COR_GUARDA_CORPO, "", "guarda-corpo (montantes)"),
                (COR_GUARDA_CORPO, "8 3", "da escada (na longarina)"),
                (COR_ACESSO, "6 4", "acesso da escada"),
                (COR_SEM_VIGA, "3 3", "borda sem viga"),
                (COR_A_MAO, "", "à mão"),
                (COR_DESMARCADO, "2 3", "desmarcado"),
            ),
        )
    )
    origem = (largura - 60.0, altura - 46.0)
    corpo.append(d.seta(*origem, origem[0] + 28, origem[1], cor=d.COR_SUAVE, largura=1.3, cabeca=6))
    corpo.append(d.seta(*origem, origem[0], origem[1] - 28, cor=d.COR_SUAVE, largura=1.3, cabeca=6))
    corpo.append(d.texto(origem[0] + 37, origem[1], "X", tamanho=10, cor=d.COR_SUAVE, peso="bold"))
    corpo.append(d.texto(origem[0], origem[1] - 37, "Y", tamanho=10, cor=d.COR_SUAVE, peso="bold"))
    return d.documento(
        largura,
        altura,
        corpo,
        "Guarda-corpo nas bordas do piso",
        subtitulo=(
            f"{d.n(total, 2)} m de guarda-corpo em {len({x.viga for x in marcados})} vigas · "
            f"bordas {bordas.metodo} · eixos da planta (no SolidWorks com Y para cima: Y = −Z)"
        ),
    )
