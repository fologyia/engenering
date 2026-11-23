"""Estrutura em incêndio (NBR 14323): curva-padrão, aquecimento, resistências e a página."""

from __future__ import annotations

import math

import pytest

from components.incendio_help import AJUDA
from core import incendio as inc
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/incendio.py"
P = inc.EntradaIncendio()


def linha(r, nome):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def test_curva_padrao_iso_834():
    assert inc.temperatura_dos_gases(30) == pytest.approx(841.8, abs=0.5)
    assert inc.temperatura_dos_gases(60) == pytest.approx(945.3, abs=0.5)
    assert inc.temperatura_dos_gases(120) == pytest.approx(1049.0, abs=0.5)


def test_tabela_1_e_calor_especifico():
    assert inc.fatores(400) == (1.0, 0.7)
    ky, kE = inc.fatores(550)
    assert ky == pytest.approx((0.78 + 0.47) / 2) and kE == pytest.approx((0.6 + 0.31) / 2)
    assert inc.calor_especifico(20) == pytest.approx(
        425 + 0.773 * 20 - 1.69e-3 * 400 + 2.22e-6 * 8000
    )
    assert inc.calor_especifico(1000) == 650.0


def test_sem_protecao_segue_os_gases_e_protegido_esquenta_menos():
    sem, _ = inc.temperatura_do_aco(200.0, 60)
    com, curva = inc.temperatura_do_aco(200.0, 60, protegido=True, tm=0.02, lam=0.12,
                                        rho_m=350.0, c_m=1200.0)  # fmt: skip
    assert inc.temperatura_dos_gases(60) - 30 < sem < inc.temperatura_dos_gases(60)
    assert 300 < com < 600
    assert len(curva) == 61 and curva[-1][2] == pytest.approx(com)


def test_mais_massivo_esquenta_menos():
    leve, _ = inc.temperatura_do_aco(250.0, 15)
    pesado, _ = inc.temperatura_do_aco(60.0, 15)
    assert pesado < leve


def test_fator_de_massividade():
    p = pi.perfil(P.perfil)
    r = inc.calcular(P)
    assert r.u_A == pytest.approx((2 * p.d + 4 * p.bf - 2 * p.tw) / p.A * 1000)


def test_compressao_8_4_2_2():
    r = inc.calcular(inc.com(P, temperatura_informada=550.0))
    p = pi.perfil(P.perfil)
    ky, kE = inc.fatores(550)
    lam0 = math.sqrt(p.A * 345 / (math.pi**2 * 200_000 * p.Iy / 4000**2))
    lt = lam0 * math.sqrt(ky / kE)
    a = 0.022 * math.sqrt(200_000 / 345)
    b = 0.5 * (1 + a * lt + lt**2)
    chi = 1 / (b + math.sqrt(b**2 - lt**2))
    assert linha(r, "Compressão em incêndio").resistente == pytest.approx(
        chi * ky * p.A * 345 / 1000
    )


def test_tracao_e_combinacao():
    r = inc.calcular(inc.com(P, elemento=inc.TIRANTE, temperatura_informada=600.0))
    v = linha(r, "Tração em incêndio")
    assert v.resistente == pytest.approx(0.47 * pi.perfil(P.perfil).A * 345 / 1000)
    assert v.solicitante == pytest.approx(1.2 * 400 + 0.42 * 300)


def test_viga_kappa_e_flt():
    e = inc.com(P, elemento=inc.VIGA, perfil="W 410 x 46,1", exposicao=inc.CONTORNO_3,
                G_k=80.0, Q_k=60.0, L=500.0, temperatura_informada=500.0)  # fmt: skip
    r = inc.calcular(e)
    p = pi.perfil("W 410 x 46,1")
    assert linha(r, "Flexão em incêndio").resistente == pytest.approx(
        1.40 * 0.78 * p.Zx * 345 / 1e6
    )


def test_sem_protecao_reprova():
    assert inc.calcular(inc.com(P, protecao="Sem proteção")).situacao == "NÃO ATENDE"
    assert inc.calcular(P).situacao == "ATENDE"


def test_validacao():
    assert inc.validar(inc.com(P, trrf=0.0))
    assert inc.validar(inc.com(P, tm=0.0))
    assert not inc.validar(P)


def test_registro_e_memorial():
    for elemento in inc.ELEMENTOS:
        reg = inc.registro(inc.calcular(inc.com(P, elemento=elemento)))
        ap.conferir_entradas_curadas(reg, inc.MODULO_ID)
    ap.conferir_registro_e_memorial(inc.registro(inc.calcular(P)), inc.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    for elemento in inc.ELEMENTOS:
        t = ap.abrir(PAGINA, inc_elemento=elemento)
        assert not ap.sem_ajuda(t), (elemento, ap.sem_ajuda(t))
    t = ap.abrir(PAGINA, inc_protecao="Sem proteção")
    assert ap.metricas(t)["Situação"] == "NÃO ATENDE"
