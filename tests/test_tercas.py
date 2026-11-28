"""Terças e travessas (NBR 14762:2010): tabelas, momento, sucção, flechas e a página."""

from __future__ import annotations

import math

import pytest

from components.tercas_help import AJUDA
from core import tercas as tc
from tests import apoio_paginas as ap

PAGINA = "app_pages/tercas.py"
P = tc.EntradaTerca()


def linha(r, nome):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def test_tabela_13_e_14():
    assert tc.k_local(0.4, 0.2) == pytest.approx(24.8)
    assert tc.k_local(0.35, 0.2) == pytest.approx((29.3 + 24.8) / 2)
    assert tc.k_local(0.5, 0.3) == pytest.approx(16.0)
    assert tc.d_bw_minimo(0.4, 100.0) == pytest.approx(0.12)
    assert tc.d_bw_minimo(0.4, 75.0) == pytest.approx((0.25 + 0.12) / 2)
    assert tc.d_bw_minimo(1.0, 300.0) == pytest.approx(0.05)


def test_fatores():
    assert tc.chi_flt(0.5) == 1.0
    assert tc.chi_flt(1.0) == pytest.approx(1.11 * (1 - 0.278))
    assert tc.chi_flt(2.0) == pytest.approx(0.25)
    assert tc.fator_reducao_local(1.0) == pytest.approx(0.78)


def test_seção_efetiva_pelo_mse():
    r = tc.calcular(P)
    p = tc.secao(P)
    W = p.ix_mm4 / 100
    Ml = tc.k_local(0.375, 0.1) * math.pi**2 * 200_000 / (12 * 0.91 * (200 / 2.65) ** 2) * W
    lam = math.sqrt(W * 345 / Ml)
    v = linha(r, "Gravidade: escoamento da seção efetiva")
    assert v.resistente == pytest.approx(W * tc.fator_reducao_local(lam) * 345 / 1.10 / 1e6)


def test_cargas_por_combinacao():
    r = tc.calcular(P)
    p = tc.secao(P)
    peso = p.massa_kg_m * 9.80665e-3
    a = math.radians(10)
    gn = (0.15 * 1.5 + peso) * math.cos(a)
    assert r.numeros["q_grav"] == pytest.approx(
        1.25 * gn + max(1.5 * 0.25 * 1.5 * math.cos(a), 1.4 * 0.3 * 1.5)
    )
    assert r.numeros["q_succ"] == pytest.approx(abs(gn - 1.4 * 0.6 * 1.5))


def test_distorcional_pendente_dispensada_ou_informada():
    r = tc.calcular(P)
    assert linha(r, "Flambagem distorcional").status == "ALERTA"
    assert r.situacao == "ATENDE COM RESSALVAS"
    r = tc.calcular(tc.com(P, D=40.0))
    assert linha(r, "Flambagem distorcional (dispensa)").status == "OK"
    r = tc.calcular(tc.com(P, M_dist=15.0))
    v = linha(r, "Flambagem distorcional")
    assert v.status == "OK" and r.situacao == "ATENDE"


def test_succao_com_fator_r():
    e = tc.com(P, bw=200.0, bf=60.0, D=20.0, t=2.0, M_dist=10.0)
    r = tc.calcular(e)
    assert tc.fator_r(e, 345.0)[0] == pytest.approx(0.65)
    assert "Sucção: mesa comprimida livre (fator R)" in {v.nome for v in r.linhas}


def test_travessa_sem_sobrecarga():
    r = tc.calcular(tc.com(P, uso=tc.TRAVESSA, M_dist=15.0))
    assert "Pressão do vento: escoamento da seção efetiva" in {v.nome for v in r.linhas}


def test_validacao():
    assert tc.validar(tc.com(P, D=150.0))
    assert tc.validar(tc.com(P, inclinacao=70.0))
    assert not tc.validar(P)


def test_registro_e_memorial():
    reg = tc.registro(tc.calcular(P))
    ap.conferir_registro_e_memorial(reg, tc.MODULO_ID)
    ap.conferir_entradas_curadas(reg, tc.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE COM RESSALVAS"
    t = ap.abrir(PAGINA, tc_uso=tc.TRAVESSA)
    assert not ap.sem_ajuda(t)


def test_secao_desenhada_reflete_dimensoes_do_perfil():
    from dataclasses import replace

    from core import cena_3d as c3
    from core import desenho_tercas as desenho

    e = replace(P, bw=180, bf=60, D=15, t=3)
    figura = desenho.secao(e)
    assert len([i for i in figura.itens if isinstance(i, c3.Poligono2D)]) == 5
    textos = " ".join(i.texto for i in figura.itens if isinstance(i, c3.Etiqueta2D))
    assert "180 mm" in textos and "60 mm" in textos and "15 mm" in textos
    assert "sem raios de dobra" in textos
