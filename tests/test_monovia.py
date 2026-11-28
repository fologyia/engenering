"""Viga de monovia: esforços pela posição das rodas, mesa inferior (EN 1993-6) e a página."""

from __future__ import annotations

import math

import pytest

from components.monovia_help import AJUDA
from core import monovia as mo
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/monovia.py"
P = mo.EntradaMonovia()
W310 = pi.perfil("W 310 x 38,7")


def linha(r: mo.ResultadoMonovia, nome: str):
    return next(v for v in r.linhas + [x for g in r.grupos for x in g.linhas] if v.nome == nome)


def test_cargas_por_eixo_com_impacto_e_majoracao():
    r = mo.calcular(P)
    # (20·1,20 + 3·1,10)·1,50/2
    assert r.esforcos["P_eixo_calculo_kN"] == pytest.approx((24 + 3.3) * 1.5 / 2)
    assert r.esforcos["P_eixo_servico_kN"] == pytest.approx(11.5)


def test_momento_de_dois_eixos_e_peso_proprio():
    r = mo.calcular(P)
    Pd = (24 + 3.3) * 1.5 / 2
    q = W310.massa * 9.80665e-3
    esperado = 2 * Pd * (2.5 - 0.3 / 4) ** 2 / 5 + 1.25 * q * 5**2 / 8
    assert r.esforcos["M_Sd_kNm"] == pytest.approx(esperado)
    assert r.esforcos["V_Sd_kN"] == pytest.approx(Pd + Pd * 4.7 / 5 + 1.25 * q * 2.5)


def test_eixos_afastados_viram_uma_carga_no_meio():
    m, _ = mo._esforcos_biapoiada(10.0, 4000.0, 5000.0, 2)
    assert m == pytest.approx(10.0 * 5000 / 4)


def test_flecha_simetrica_e_de_balanco():
    EI = 200_000 * W310.Ix
    b = (5000 - 300) / 2
    assert mo._flecha_biapoiada(1000.0, 300.0, 5000.0, EI, 2) == pytest.approx(
        1000 * b * (3 * 5000**2 - 4 * b**2) / (24 * EI)
    )
    assert mo._flecha_balanco(1000.0, 0.0, 1500.0, EI, 1) == pytest.approx(
        1000 * 1500**3 / (3 * EI)
    )


def test_flexao_local_da_mesa_en_1993_6():
    r = mo.calcular(P)
    v = linha(r, "Flexão local da mesa inferior")
    m = 0.5 * (165 - 5.8) - 0.8 * 10 - 20
    s = m + 20
    l_eff = 2 * math.sqrt(2) * s + 0.5 * 300  # 300 < 4√2·(m + n)
    sigma = r.esforcos["M_Sd_kNm"] * 1e6 / W310.Ix * (310 / 2 - 9.7 / 2)
    esperado = l_eff * 9.7**2 * 345 / (4 * m * 1.10) * (1 - (sigma / (345 / 1.10)) ** 2) / 1000
    assert v.resistente == pytest.approx(esperado)
    assert v.solicitante == pytest.approx(r.esforcos["F_roda_calculo_kN"])


def test_ponta_sem_enrijecedor_reduz_l_eff():
    l_a, _ = mo.comprimento_efetivo(50.0, 20.0, 300.0, True, 2)
    l_b, _ = mo.comprimento_efetivo(50.0, 20.0, 1000.0, False, 2)
    assert l_a == pytest.approx(140.0) and l_b == pytest.approx(4 * math.sqrt(2) * 70)


def test_coeficientes_locais_en_1993_6():
    c = mo.coeficientes_locais(0.2)
    assert c["cx0"] == pytest.approx(0.2045, abs=1e-3)
    assert c["cy0"] == pytest.approx(-1.6865, abs=1e-3)
    assert c["cx1"] == pytest.approx(1.9676, abs=1e-3)
    assert c["cy1"] == pytest.approx(0.9317, abs=1e-3)
    assert c["cy2"] == 0.0


def test_lateral_so_na_mesa_inferior_e_interacao():
    r = mo.calcular(P)
    v = linha(r, "Flexão lateral da mesa inferior")
    assert v.resistente == pytest.approx(9.7 * 165**2 / 4 * 345 / 1.10 / 1e6)
    assert v.solicitante == pytest.approx(r.esforcos["M_lat_kNm"])
    inter = linha(r, "Interação: flexão vertical + lateral")
    flex = linha(r, "Flexão vertical")
    assert inter.solicitante == pytest.approx(
        flex.solicitante / flex.resistente + v.solicitante / v.resistente
    )


def test_balanco_e_limite_com_o_dobro_do_comprimento():
    r = mo.calcular(mo.com(P, sistema=mo.BALANCO, L=1500.0, Lb=1500.0))
    v = linha(r, "Flecha vertical")
    assert v.resistente == pytest.approx(2 * 1500 / 500)


def test_carga_alta_reprova():
    r = mo.calcular(mo.com(P, capacidade=100.0))
    assert r.situacao == "NÃO ATENDE"


def test_apoio_pendurado_verifica_a_mesa_tracionada():
    r = mo.calcular(P)
    nomes = [v.nome for v in r.grupos[-1].linhas]
    assert "Flexão local da mesa" in nomes
    r = mo.calcular(mo.com(P, apoio=mo.APOIADA))
    assert "Enrugamento da alma" in [v.nome for v in r.grupos[-1].linhas]


def test_validacao():
    assert mo.validar(mo.com(P, n_roda=500.0))
    assert mo.validar(mo.com(P, entre_eixos=6000.0))
    assert not mo.validar(P)


def test_registro_e_memorial():
    reg = mo.registro(mo.calcular(P))
    ap.conferir_registro_e_memorial(reg, mo.MODULO_ID)
    ap.conferir_entradas_curadas(reg, mo.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
    t = ap.abrir(PAGINA, mo_familia=pi.FAMILIA_SOLDADO, mo_sistema=mo.BALANCO)
    assert not ap.sem_ajuda(t)


def test_secao_da_monovia_reflete_rodas_e_perfil():
    from dataclasses import replace

    from core import cena_3d as c3
    from core import desenho_monovia as desenho

    e = mo.EntradaMonovia()
    dois = desenho.secao(e)
    um = desenho.secao(replace(e, rodas_por_eixo=1))
    assert len([i for i in dois.itens if isinstance(i, c3.Seta2D)]) == 2
    assert len([i for i in um.itens if isinstance(i, c3.Seta2D)]) == 1
    assert "por convenção" in " ".join(i.texto for i in um.itens if isinstance(i, c3.Etiqueta2D))
