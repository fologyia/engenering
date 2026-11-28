"""Aberturas na alma (NBR 8800:2025, Anexo F; AISC Design Guide 2) e a página."""

from __future__ import annotations

import math

import pytest

from components.aberturas_alma_help import AJUDA
from core import aberturas_alma as ab
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/aberturas_alma.py"
P = ab.EntradaAberturas()
W410 = pi.perfil("W 410 x 46,1")


def grupo(r, nome):
    return next(g for g in r.grupos if g.nome == nome)


def linha(g, nome):
    return next(v for v in g.linhas if v.nome == nome)


def test_momento_e_cortante_dg2():
    Mm = ab.momento_maximo_na_abertura(W410, 345.0, 150.0, 0.0)
    assert Mm == pytest.approx(W410.Zx * 345 * (1 - 150 * 7 * (150 / 4) / W410.Zx))
    Vm, s1, s2 = ab.cortante_maximo_na_abertura(W410, 345.0, 300.0, 120.0, 0.0)
    s = 403 / 2 - 60
    Vp = 345 * 7 * s / math.sqrt(3)
    assert s1 == s2 == pytest.approx(s)
    assert Vm == pytest.approx(2 * min(Vp * math.sqrt(6) / (300 / s + math.sqrt(3)), Vp))


def test_excentricidade_reduz_o_momento():
    centrado = ab.momento_maximo_na_abertura(W410, 345.0, 150.0, 0.0)
    fora = ab.momento_maximo_na_abertura(W410, 345.0, 150.0, 40.0)
    assert fora < centrado


def test_padrao_nao_dispensa_e_verifica_pelo_dg2():
    r = ab.calcular(P)
    assert not r.dispensa and r.situacao == "ATENDE"
    inter = linha(grupo(r, "Abertura: Eletrocalha"), "Interação momento × cortante")
    assert inter.status == "OK" and inter.solicitante < 1


def test_circulares_bem_postas_dispensam_f3():
    e = ab.com(P, aberturas=(ab.Abertura("A", ab.CIRCULAR, 120, 120, 2500, 0),
                             ab.Abertura("B", ab.CIRCULAR, 120, 120, 4500, 0)))  # fmt: skip
    r = ab.calcular(e)
    assert r.dispensa and r.situacao == "ATENDE"
    assert all(v.status == "INFO" for v in grupo(r, "Abertura: A").linhas)


def test_perto_do_apoio_nao_dispensa():
    e = ab.com(P, aberturas=(ab.Abertura("A", ab.CIRCULAR, 120, 120, 1000, 0),))
    r = ab.calcular(e)
    assert not r.dispensa


def test_abertura_grande_reprova():
    e = ab.com(P, aberturas=(ab.Abertura("Grande", ab.RETANGULAR, 900, 260, 1200, 0),))
    r = ab.calcular(e)
    assert r.situacao == "NÃO ATENDE"


def test_validacao_e_tabela():
    assert ab.validar(ab.com(P, aberturas=(ab.Abertura("X", ab.CIRCULAR, 400, 400, 3000, 0),)))
    assert ab.aberturas_de_tabela(ab.tabela_das_aberturas(P.aberturas)) == P.aberturas


def test_registro_e_memorial():
    reg = ab.registro(ab.calcular(P))
    ap.conferir_registro_e_memorial(reg, ab.MODULO_ID)
    ap.conferir_entradas_curadas(reg, ab.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"


def test_desenho_detalha_forma_e_excentricidade():
    from dataclasses import replace

    from core import cena_3d as c3
    from core import desenho_aberturas_alma as desenho

    entrada = ab.EntradaAberturas()
    furo = entrada.aberturas[1]
    central = desenho.detalhe(entrada, furo)
    deslocado = desenho.detalhe(entrada, replace(furo, e=30))

    # A abertura branca se move para cima sem mudar as dimensões do retângulo.
    def branco(d):
        return next(
            x for x in d.itens if isinstance(x, c3.Poligono2D) and x.preenchimento == "#ffffff"
        )

    pontos1, pontos2 = branco(central).pontos, branco(deslocado).pontos
    assert pontos2[0][1] < pontos1[0][1]
    assert pontos2[1][0] - pontos2[0][0] == pytest.approx(pontos1[1][0] - pontos1[0][0])
    assert "300" in " ".join(x.texto for x in central.itens if isinstance(x, c3.Etiqueta2D))
