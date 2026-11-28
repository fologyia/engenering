"""Elevação local de uma força transversal aplicada a perfil I."""

from __future__ import annotations

from core import cena_3d as c3
from core import desenho_2d as d2
from core import forcas_localizadas as fl
from core import perfil_i as pi


def detalhe(e: fl.EntradaForcas, f: fl.ForcaLocalizada) -> c3.Desenho2D:
    """Seção longitudinal; a distância à extremidade é informativa, não desenhada."""
    v = fl.obter_perfil(e)
    metade = max(v.d * 0.9, f.ln * 0.85, 100.0)
    enq = c3.Enquadramento([(-metade, -v.d / 2 - 120), (metade, v.d / 2 + 120)], (50, 65, 650, 300))

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    def ret(x0: float, y0: float, x1: float, y1: float, cor: str) -> c3.Poligono2D:
        return c3.Poligono2D((p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1)), cor, "#496271", 1.1)

    h, tf = v.d / 2, v.tf
    itens: list[d2.Item] = [
        ret(-metade, -h, metade, h, "#e3edf1"),
        ret(-metade, h - tf, metade, h, "#718d9d"),
        ret(-metade, -h, metade, -h + tf, "#718d9d"),
    ]
    if e.usar_enrijecedor and e.enrijecedor.altura_total:
        t = e.enrijecedor.ts
        itens.append(ret(-t / 2, -h + tf, t / 2, h - tf, "#6aa8c9"))
    # A força atua centrada no trecho, mas não há posição x global na entrada.
    x, y = p(0, h)
    if f.F > 0:
        if f.tipo == fl.TRACAO:
            itens.append(c3.Seta2D((x, y - 8), (x, y - 50), "#b45309", 2.2, 8))
        else:
            itens.append(c3.Seta2D((x, y - 50), (x, y - 8), "#b45309", 2.2, 8))
        if f.tipo == fl.PAR:
            bx, by = p(0, -h)
            itens.append(c3.Seta2D((bx, by + 50), (bx, by + 8), "#b45309", 2.2, 8))
    if f.ln > 0:
        itens += d2.cota(p(-f.ln / 2, h + 90), p(f.ln / 2, h + 90), f"ℓ_n = {pi.numero(f.ln)} mm")
    itens.append(d2.texto(350, 337, f"{f.tipo} · F = {pi.numero(f.F)} kN", tamanho=11))
    itens.append(
        d2.texto(
            350,
            357,
            f"Distância informada à ponta: {pi.numero(f.distancia)} mm (ponta não representada)",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    nota = (
        "Enrijecedor de altura parcial: geometria não especificada; não representado."
        if e.usar_enrijecedor and not e.enrijecedor.altura_total
        else "Vista local esquemática; enrijecedores, quando mostrados, estão na seção da força."
    )
    itens.append(d2.texto(350, 377, nota, tamanho=10, cor=d2.COR_SUAVE))
    return c3.Desenho2D(700, 395, tuple(itens), titulo=f"{f.nome} — detalhe local")
