"""Contenção lateral (NBR 8800:2025, 4.12): exigências, barra de travamento, torção e a página."""

from __future__ import annotations

import math

import pytest

from components.contencao_lateral_help import AJUDA
from core import contencao_lateral as cl
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/contencao_lateral.py"
P = cl.EntradaContencao()
W410 = pi.perfil("W 410 x 46,1")


def linha(r, nome):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def test_pilar_4_12_2_2():
    F, S = cl.exigencia_pilar(800e3, 2000.0, 2)
    assert F == pytest.approx(8000.0)
    assert S == pytest.approx(2 * (4 - 1) * 1.35 * 800e3 / 2000)


def test_translacao_4_12_3_3_e_curvatura_reversa():
    ho = W410.d - W410.tf
    F, S = cl.exigencia_translacao(180e6, ho, 2000.0, 1.0)
    assert F == pytest.approx(0.02 * 180e6 / ho)
    assert S == pytest.approx(10 * 1.35 * 180e6 / (2000 * ho))
    r = cl.calcular(cl.com(P, curvatura_reversa=True))
    assert r.exigencias["F_br_kN"] == pytest.approx(2 * F / 1000)


def test_barra_inclinada_e_ligacao_em_serie():
    r = cl.calcular(cl.com(P, angulo=30.0, k_ligacao=20.0))
    c = math.cos(math.radians(30))
    k_barra = 200_000 * 480 / 1500 * c**2
    k = 1 / (1 / k_barra + 1 / (20_000 * c**2))
    assert linha(r, "Rigidez da barra de contenção").resistente == pytest.approx(k / 1000)
    assert linha(r, "Resistência da barra de contenção").solicitante == pytest.approx(
        r.exigencias["F_br_kN"] / c
    )


def test_tirante_so_tracao():
    r = cl.calcular(cl.com(P, trabalho=cl.TRACAO))
    assert linha(r, "Resistência da barra de contenção").resistente == pytest.approx(
        480 * 250 / 1.10 / 1000
    )
    assert "Esbeltez da barra de contenção" not in {v.nome for g in r.grupos for v in g.linhas}


def test_varias_barras_somam_e_l_q():
    r1 = cl.calcular(cl.com(P, caso=cl.PILAR))
    r3 = cl.calcular(cl.com(P, caso=cl.PILAR, barras=3))
    assert r3.exigencias["F_br_kN"] == pytest.approx(3 * r1.exigencias["F_br_kN"])
    rq = cl.calcular(cl.com(P, caso=cl.PILAR, L_q=4000.0))
    assert rq.exigencias["S_br_kN_mm"] == pytest.approx(r1.exigencias["S_br_kN_mm"] / 2)
    assert rq.avisos


def test_torcao_nodal_conta_de_mao():
    r = cl.calcular(cl.com(P, caso=cl.VIGA_TORCAO))
    ho = W410.d - W410.tf
    assert r.exigencias["M_br"] == pytest.approx(0.024 * 180e6 * 6000 / (2 * 1 * 2000) / 1e6)
    ST = 2.4 * 1.35 * 6000 * 180e6**2 / (2 * 200_000 * W410.Iy)
    Ssec = 3.3 * 200_000 / ho * (1.5 * ho * W410.tw**3 / 12 + 8 * 120**3 / 12)
    assert r.exigencias["S_T"] == pytest.approx(ST / 1e6)
    assert r.exigencias["S_sec"] == pytest.approx(Ssec / 1e6)
    v = linha(r, "Rigidez da contenção de torção")
    assert v.solicitante == pytest.approx(ST / (1 - ST / Ssec) / 1e6)
    assert v.resistente == pytest.approx(6 * 200_000 * 10e6 / 2000 / 1e6)
    assert r.situacao == "ATENDE"


def test_sem_enrijecedor_a_alma_distorce():
    r = cl.calcular(cl.com(P, caso=cl.VIGA_TORCAO, t_st=0.0))
    assert linha(r, "Distorção da alma").status == "NÃO OK"


def test_torcao_continua_por_metro():
    r = cl.calcular(cl.com(P, caso=cl.VIGA_TORCAO_CONTINUA))
    ho = W410.d - W410.tf
    assert r.exigencias["S_sec"] == pytest.approx(3.3 * 200_000 * W410.tw**3 / (12 * ho) / 1e3)
    assert r.exigencias["M_br"] == pytest.approx(0.024 * 180e6 / 2000 / 1e3)


def test_validacao():
    assert cl.validar(cl.com(P, angulo=95.0))
    assert cl.validar(cl.com(P, caso=cl.PILAR, N_Sd=0.0))
    assert not cl.validar(P)


def test_registro_e_memorial():
    for caso in cl.CASOS:
        reg = cl.registro(cl.calcular(cl.com(P, caso=caso)))
        ap.conferir_entradas_curadas(reg, cl.MODULO_ID)
    ap.conferir_registro_e_memorial(cl.registro(cl.calcular(P)), cl.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    for caso in cl.CASOS:
        t = ap.abrir(PAGINA, cl_caso=caso)
        assert not ap.sem_ajuda(t), (caso, ap.sem_ajuda(t))
    t = ap.abrir(PAGINA, cl_caso=cl.VIGA_TORCAO, cl_beta_tipo=cl.BETA_INFORMADO)
    assert not ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
