"""Nós de treliça tubular (EN 1993-1-8, capítulo 7): fatores, resistências, validade e página."""

from __future__ import annotations

import math

import pytest

from components.nos_tubulares_help import AJUDA
from core import nos_tubulares as nt
from tests import apoio_paginas as ap

PAGINA = "app_pages/nos_tubulares.py"
P = nt.EntradaNo()
RHS = nt.com(P, forma=nt.RETANGULAR, banzo=nt.Tubo(150, 150, 6.3), diagonal1=nt.Tubo(80, 80, 4.0),
             diagonal2=nt.Tubo(80, 80, 4.0), g=40.0)  # fmt: skip


def linha(r, nome):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def sen(g):
    return math.sin(math.radians(g))


def test_fatores():
    assert nt.fator_kp(-0.2) == 1.0
    assert nt.fator_kp(0.35) == pytest.approx(1 - 0.3 * 0.35 * 1.35)
    g = 168.3 / (2 * 6.4)
    assert nt.fator_kg(g, 30.0, 6.4) == pytest.approx(
        g**0.2 * (1 + 0.024 * g**1.2 / (1 + math.exp(0.5 * 30 / 6.4 - 1.33)))
    )
    assert nt.fator_kn(0.3, 0.5) == pytest.approx(1.0)  # 1,3 − 0,24 > 1
    assert nt.fator_kn(0.8, 0.4) == pytest.approx(0.5)


def test_chs_k_face_do_banzo_conta_de_mao():
    r = nt.calcular(P)
    A0 = math.pi * (168.3 - 6.4) * 6.4
    n = 400e3 / A0 / 350
    kp = 1 - 0.3 * n * (1 + n)
    g = 168.3 / 12.8
    kg = nt.fator_kg(g, 30.0, 6.4)
    esperado = kg * kp * 350 * 6.4**2 / sen(45) * (1.8 + 10.2 * 88.9 / 168.3) / 1.10 / 1000
    assert linha(r, "Diagonal 1: plastificação da face do banzo").resistente == pytest.approx(
        esperado
    )
    assert r.situacao == "ATENDE"


def test_chs_t_e_x():
    t = nt.calcular(nt.com(P, tipo=nt.NO_T, theta1=90.0, N1=-100.0, N0=0.0))
    beta = 88.9 / 168.3
    g = 168.3 / 12.8
    assert linha(t, "Diagonal 1: plastificação da face do banzo").resistente == pytest.approx(
        g**0.2 * 350 * 6.4**2 * (2.8 + 14.2 * beta**2) / 1.10 / 1000
    )
    x = nt.calcular(nt.com(P, tipo=nt.NO_X, theta1=90.0, N1=-100.0, N0=0.0))
    assert linha(x, "Diagonal 1: plastificação da face do banzo").resistente == pytest.approx(
        350 * 6.4**2 * 5.2 / (1 - 0.81 * beta) / 1.10 / 1000
    )
    assert linha(x, "Diagonal 1: punção do banzo").resistente == pytest.approx(
        350 / math.sqrt(3) * 6.4 * math.pi * 88.9 * 2 / 2 / 1.10 / 1000
    )


def test_chs_validade():
    r = nt.calcular(nt.com(P, banzo=nt.Tubo(168.3, 168.3, 3.0)))  # d/t = 56
    assert linha(r, "Validade: d₀/t₀").status == "NÃO OK"
    r = nt.calcular(nt.com(P, g=5.0))
    assert linha(r, "Validade: afastamento").status == "NÃO OK"


def test_rhs_k_face_e_cisalhamento():
    r = nt.calcular(RHS)
    beta = 320 / 600
    gama = 150 / 12.6
    face = 8.9 * 1.0 * 350 * 6.3**2 * math.sqrt(gama) * beta / sen(45) / 1.10 / 1000
    assert linha(r, "Diagonal 1: plastificação da face do banzo").resistente == pytest.approx(face)
    alfa = 1 / math.sqrt(1 + 4 * 40**2 / (3 * 6.3**2))
    Av = (2 * 150 + alfa * 150) * 6.3
    assert linha(r, "Diagonal 1: cisalhamento do banzo no afastamento").resistente == pytest.approx(
        350 * Av / math.sqrt(3) / sen(45) / 1.10 / 1000
    )
    assert r.situacao == "ATENDE"


def test_rhs_t_parede_lateral_com_beta_alto():
    e = nt.com(RHS, tipo=nt.NO_T, diagonal1=nt.Tubo(140, 140, 6.3), theta1=90.0, N1=-150.0)
    r = nt.calcular(e)
    assert linha(r, "Diagonal 1: parede lateral do banzo").status == "OK"
    assert "Diagonal 1: ruptura da diagonal" in {v.nome for g in r.grupos for v in g.linhas}


def test_rhs_t_face_com_beta_baixo():
    e = nt.com(RHS, tipo=nt.NO_T, diagonal1=nt.Tubo(100, 100, 5.0), theta1=60.0, N1=-100.0, N0=0.0)
    r = nt.calcular(e)
    beta = eta = 100 / 150
    esperado = (350 * 6.3**2 / ((1 - beta) * sen(60)) * (2 * eta / sen(60) + 4 * math.sqrt(1 - beta))
                / 1.10 / 1000)  # fmt: skip
    assert linha(r, "Diagonal 1: plastificação da face do banzo").resistente == pytest.approx(
        esperado
    )


def test_validacao():
    assert nt.validar(nt.com(P, theta1=0.0))
    assert nt.validar(nt.com(P, diagonal1=nt.Tubo(200, 200, 5)))
    assert not nt.validar(P)


def test_registro_e_memorial():
    for e in (P, RHS):
        reg = nt.registro(nt.calcular(e))
        ap.conferir_registro_e_memorial(reg, nt.MODULO_ID)
        ap.conferir_entradas_curadas(reg, nt.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
    t = ap.abrir(PAGINA, nt_forma=nt.RETANGULAR)
    assert not ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
    t = ap.abrir(PAGINA, nt_tipo=nt.NO_X)
    assert not ap.sem_ajuda(t)


@pytest.mark.parametrize(("tipo", "n_ramos"), [(nt.NO_T, 1), (nt.NO_X, 2), (nt.NO_K, 2)])
def test_elevacao_conforme_tipo_de_no(tipo, n_ramos):
    from core import cena_3d as c3
    from core import desenho_nos_tubulares as desenho

    e = nt.com(P, tipo=tipo)
    figura = desenho.elevacao(e)
    assert len([i for i in figura.itens if isinstance(i, c3.Poligono2D)]) == n_ramos + 1
    textos = " ".join(i.texto for i in figura.itens if isinstance(i, c3.Etiqueta2D))
    assert ("g =" in textos) == (tipo == nt.NO_K)
    assert "sem recortes" in textos
