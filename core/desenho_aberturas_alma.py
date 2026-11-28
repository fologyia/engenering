"""Detalhes proporcionais das aberturas informadas, em milímetros."""

from __future__ import annotations

from core import aberturas_alma as ab
from core import cena_3d as c3
from core import desenho_2d as d2


def detalhe(e: ab.EntradaAberturas, abertura: ab.Abertura) -> c3.Desenho2D:
    """Vista lateral do trecho junto à abertura; eixo vertical positivo para cima.

    A largura mostrada é um recorte local e não representa o vão inteiro. A abertura,
    as mesas e a excentricidade usam uma escala única nas duas direções.
    """
    perfil = ab.obter_perfil(e)
    altura = abertura.largura if abertura.forma == ab.CIRCULAR else abertura.altura
    metade = max(perfil.d * 1.1, abertura.largura * 0.8)
    enq = c3.Enquadramento([(-metade, -perfil.d / 2), (metade, perfil.d / 2)], (95, 80, 535, 325))

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    def ret(x0: float, y0: float, x1: float, y1: float, cor: str) -> c3.Poligono2D:
        return c3.Poligono2D(
            (p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), cor, d2.COR_ESTRUTURA, 1.3
        )

    d, tf = perfil.d, perfil.tf
    itens: list[d2.Item] = [
        ret(-metade, -d / 2, metade, d / 2, "#e7eef2"),
        ret(-metade, d / 2 - tf, metade, d / 2, "#7893a2"),
        ret(-metade, -d / 2, metade, -d / 2 + tf, "#7893a2"),
        d2.linha(p(-metade, 0), p(metade, 0), d2.COR_SUAVE, 0.8, "6 4"),
    ]
    if abertura.forma == ab.CIRCULAR:
        itens.append(
            c3.circulo(
                p(0, abertura.e),
                abertura.largura / 2 * enq.escala,
                preenchimento="#ffffff",
                contorno="#334e5e",
                largura=1.8,
            )
        )
    else:
        itens.append(
            ret(
                -abertura.largura / 2,
                abertura.e - altura / 2,
                abertura.largura / 2,
                abertura.e + altura / 2,
                "#ffffff",
            )
        )
    centro = p(0, abertura.e)
    itens += [
        d2.linha((centro[0] - 9, centro[1]), (centro[0] + 9, centro[1]), "#64748b", 0.8),
        d2.linha((centro[0], centro[1] - 9), (centro[0], centro[1] + 9), "#64748b", 0.8),
    ]
    itens += d2.cota(
        p(-abertura.largura / 2, -d / 2 - d * 0.13),
        p(abertura.largura / 2, -d / 2 - d * 0.13),
        f"largura = {ab._n(abertura.largura)} mm",
    )
    if abertura.forma != ab.CIRCULAR:
        itens += d2.cota(
            p(metade * 0.75, abertura.e - altura / 2),
            p(metade * 0.75, abertura.e + altura / 2),
            f"altura = {ab._n(altura)} mm",
        )
    itens.append(
        d2.texto(
            315,
            390,
            f"Centro: x = {ab._n(abertura.x)} mm do apoio esquerdo · e = {ab._n(abertura.e)} mm",
            tamanho=11,
            cor=d2.COR_SUAVE,
        )
    )
    itens.append(
        d2.texto(
            315,
            411,
            "Linha tracejada: eixo médio da viga · trecho local, não o vão inteiro",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    return c3.Desenho2D(
        630, 430, tuple(itens), titulo=f"{abertura.nome} — {abertura.forma.lower()}"
    )
