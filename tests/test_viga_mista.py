"""Viga mista (NBR 8800:2025, Anexo L): conector, momento plástico, interação, flecha e página."""

from __future__ import annotations

import math

import pytest

from components.viga_mista_help import AJUDA
from core import perfil_i as pi
from core import viga_mista as vmx
from tests import apoio_paginas as ap

PAGINA = "app_pages/viga_mista.py"
P = vmx.EntradaMista()


def linha(r, nome):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def test_largura_efetiva():
    assert vmx.largura_efetiva(P)[0] == pytest.approx(2000.0)  # L/8 = 1000 de cada lado
    e = vmx.com(P, s_esquerda=1500.0, s_direita=0.0, balanco_direita=300.0)
    assert vmx.largura_efetiva(e)[0] == pytest.approx(750.0 + 300.0)


def test_conector_l_4_2_1():
    Acs = math.pi * 19**2 / 4
    Ec = 0.85 * 1.0 * 5600 * 5
    concreto = 0.5 * Acs * math.sqrt(25 * Ec) / 1.25
    aco = 1.0 * 0.75 * Acs * 415 / 1.25
    assert vmx.resistencia_conector(P)[0] == pytest.approx(min(concreto, aco))
    e = vmx.com(P, posicao="Fôrma perpendicular, 3 ou mais por nervura")
    assert vmx.resistencia_conector(e)[0] == pytest.approx(0.70 * 0.60 * Acs * 415 / 1.25)


def test_interacao_completa_linha_neutra_na_laje_conta_de_mao():
    p = pi.perfil(P.perfil)
    r = vmx.calcular(P)
    Aa = 2 * p.bf * p.tf + (p.d - 2 * p.tf) * p.tw
    Tad = Aa * 345 / 1.10
    a = Tad / (0.85 * 1.0 * 25 / 1.4 * 2000)
    assert r.secao is not None and r.secao.caso.startswith("a)")
    assert r.secao.M_Rd == pytest.approx(Tad * (p.d / 2 + 100 - a / 2))


def test_linha_neutra_no_perfil_com_laje_fina():
    r = vmx.calcular(vmx.com(P, tc=40.0, s_esquerda=800.0, s_direita=800.0, conectores=40))
    assert r.secao is not None and r.secao.caso.startswith("b)")
    s = r.secao
    assert s.Tad == pytest.approx(s.Ccd + s.Cad)


def test_interacao_parcial_e_grau_minimo():
    r = vmx.calcular(vmx.com(P, conectores=8))
    assert r.secao is not None and r.secao.caso.startswith("c)")
    assert r.eta_i == pytest.approx(8 * r.QRd / (r.numeros["Fhd_kN"] * 1000))
    v = linha(r, "Grau de interação mínimo")
    assert v.status == "OK"
    r2 = vmx.calcular(vmx.com(P, conectores=3))
    assert linha(r2, "Grau de interação mínimo").status == "NÃO OK"


def test_momento_parcial_entre_o_aco_e_o_completo():
    p = pi.perfil(P.perfil)
    parcial = vmx.calcular(vmx.com(P, conectores=8)).secao
    completa = vmx.calcular(P).secao
    assert parcial is not None and completa is not None
    assert p.Zx * 345 / 1.10 < parcial.M_Rd < completa.M_Rd


def test_secao_homogeneizada_conferida_pelo_teorema_dos_eixos():
    p = pi.perfil(P.perfil)
    Itr, y_inf, y_sup = vmx.secao_homogeneizada(p, 2000.0, 100.0, 0.0, 8.4)
    assert y_inf + y_sup == pytest.approx(p.d + 100)
    assert Itr > p.Ix


def test_flecha_nao_escorada_soma_perfil_e_mista():
    r = vmx.calcular(P)
    v = linha(r, "Flecha total")
    p = pi.perfil(P.perfil)
    d1 = 5 * 7.0 * 8000**4 / (384 * 200_000 * p.Ix)
    assert v.solicitante > d1 - 15.0
    assert r.situacao == "ATENDE"


def test_escorada_nao_verifica_o_perfil_sozinho():
    r = vmx.calcular(vmx.com(P, escorada=True))
    assert not any(g.nome == "Construção não escorada" for g in r.grupos)


def test_conectores_espacamento():
    r = vmx.calcular(vmx.com(P, conectores=60, por_linha=1))
    assert linha(r, "Espaçamento mínimo dos conectores").status == "NÃO OK"  # 66,7 < 6·19


def test_validacao():
    assert vmx.validar(vmx.com(P, fck=60.0))
    assert vmx.validar(vmx.com(P, s_esquerda=0.0))
    assert not vmx.validar(P)


def test_registro_e_memorial():
    reg = vmx.registro(vmx.calcular(P))
    ap.conferir_registro_e_memorial(reg, vmx.MODULO_ID)
    ap.conferir_entradas_curadas(reg, vmx.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA, vmx_s_esquerda=0.0, vmx_s_direita=0.0)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    t = ap.abrir(PAGINA)
    assert ap.metricas(t)["Situação"] == "ATENDE"
