"""Seção local ilustrativa de viga mista, baseada nas dimensões informadas."""

from __future__ import annotations

from core import cena_3d as c3
from core import desenho_2d as d2
from core import perfil_i as pi
from core import viga_mista as vm


def secao_local(e: vm.EntradaMista) -> c3.Desenho2D:
    """Perfil e alturas proporcionais; conector e limites laterais são apenas indicativos."""
    perfil = vm.obter_perfil(e)
    d, bf, tf, tw = perfil.d, perfil.bf, perfil.tf, perfil.tw
    # A largura efetiva é indicada no texto: este é um recorte, não a largura total da laje.
    corte = max(1.1 * bf, d * 0.48)
    topo = d / 2 + e.hF + e.tc
    enq = c3.Enquadramento(
        [(-corte - 50, -topo - 35), (corte + 100, d / 2 + 40)], (40, 50, 680, 330)
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    def ret(x0: float, y0: float, x1: float, y1: float, cor: str) -> c3.Poligono2D:
        return c3.Poligono2D((p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), cor, "#496271", 1)

    itens: list[d2.Item] = [
        ret(-tw / 2, -d / 2, tw / 2, d / 2, "#8da4b1"),
        ret(-bf / 2, d / 2 - tf, bf / 2, d / 2, "#657f8d"),
        ret(-bf / 2, -d / 2, bf / 2, -d / 2 + tf, "#657f8d"),
        ret(-corte, d / 2 + e.hF, corte, topo, "#e2ded6"),
    ]
    if e.hF > 0:
        # Sem geometria das nervuras: só a faixa correspondente à altura informada.
        itens.append(ret(-corte, d / 2, corte, d / 2 + e.hF, "#d0dce2"))
    # O tamanho e o número de conectores na seção não são inferidos: marca simbólica.
    x, y = p(0, d / 2)
    itens += [
        d2.linha((x, y), (x, y - 22), "#a85b2f", 3),
        d2.linha((x - 6, y - 22), (x + 6, y - 22), "#a85b2f", 3),
    ]
    itens += d2.cota(
        p(corte + 28, d / 2 + e.hF), p(corte + 28, topo), f"t_c = {pi.numero(e.tc)} mm"
    )
    if e.hF > 0:
        itens += d2.cota(
            p(corte + 28, d / 2), p(corte + 28, d / 2 + e.hF), f"h_F = {pi.numero(e.hF)} mm"
        )
    b, _ = vm.largura_efetiva(e)
    itens.append(
        d2.texto(
            360,
            360,
            f"Largura efetiva calculada = {pi.numero(b)} mm · recorte local sem largura total",
            tamanho=10,
        )
    )
    itens.append(
        d2.texto(
            360,
            380,
            f"Conector Ø {pi.numero(e.diametro_conector)} mm: símbolo sem altura ou quantidade na seção",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    if e.hF > 0:
        itens.append(
            d2.texto(
                360,
                400,
                "Faixa azul: altura da fôrma; formato das nervuras não informado.",
                tamanho=10,
                cor=d2.COR_SUAVE,
            )
        )
    return c3.Desenho2D(720, 420, tuple(itens), titulo="Viga mista — seção local esquemática")
