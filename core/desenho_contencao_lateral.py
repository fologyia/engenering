"""Esquema conceitual da contenção lateral conforme o caso selecionado."""

from __future__ import annotations

from core import cena_3d as c3
from core import contencao_lateral as cl
from core import desenho_2d as d2
from core import perfil_i as pi


def esquema(e: cl.EntradaContencao) -> c3.Desenho2D:
    """Desenha a grandeza restringida; não presume a geometria real do travamento."""
    itens: list[d2.Item] = []
    if e.caso == cl.PILAR:
        itens.append(
            c3.Poligono2D(((275, 80), (325, 80), (325, 310), (275, 310)), "#a8c8db", "#345568", 1.5)
        )
        itens.append(d2.linha((325, 195), (445, 195), "#b45309", 4))
        itens.append(d2.texto(300, 63, "Pilar", tamanho=13))
        itens.append(d2.texto(440, 178, "contenção lateral", tamanho=11))
    else:
        itens.append(
            c3.Poligono2D(
                ((100, 165), (500, 165), (500, 215), (100, 215)), "#a8c8db", "#345568", 1.5
            )
        )
        itens.append(d2.texto(300, 145, "Viga", tamanho=13))
        if e.caso == cl.VIGA_TRANSLACAO:
            itens.append(d2.linha((300, 165), (300, 85), "#b45309", 4))
            itens.append(d2.texto(425, 85, "contenção lateral", tamanho=11))
        else:
            itens.append(
                c3.circulo((300, 190), 42, preenchimento="none", contorno="#b45309", largura=2)
            )
            itens.append(d2.texto(440, 110, "restrição à torção", tamanho=11))
    itens.append(d2.texto(300, 343, f"{e.caso}", tamanho=11))
    itens.append(
        d2.texto(300, 364, f"Distância entre contenções L_b = {pi.numero(e.L_b)} mm", tamanho=10)
    )
    itens.append(
        d2.texto(
            300,
            384,
            "Esquema funcional: geometria e ligações reais não representadas.",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    return c3.Desenho2D(600, 405, tuple(itens), titulo="Contenção lateral — conceito")
