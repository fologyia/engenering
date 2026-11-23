"""Fadiga da estrutura (NBR 8800:2025, Anexo H): faixas admissíveis, dispensas e a página."""

from __future__ import annotations

import pytest

from components.fadiga_estrutural_help import AJUDA
from core import fadiga_estrutural as fe
from tests import apoio_paginas as ap

PAGINA = "app_pages/fadiga_estrutural.py"
P = fe.EntradaFadiga()


def rotulo(codigo: str, categoria: str) -> str:
    return next(c.rotulo for c in fe.CASOS if c.codigo == codigo and c.categoria == categoria)


def test_constantes_da_tabela_h1():
    assert fe.CATEGORIAS["A"] == (250e8, 165.0)
    assert fe.CATEGORIAS["E'"] == (3.9e8, 18.0)
    assert fe.CATEGORIAS["F"] == (160e10, 55.0)
    assert fe.CATEGORIAS["G"] == (3.9e8, 48.0)
    assert len({c.rotulo for c in fe.CASOS}) == len(fe.CASOS)


@pytest.mark.parametrize("categoria", ["B", "C", "D", "E"])
def test_faixa_admissivel_h4_a(categoria):
    Cf, th = fe.CATEGORIAS[categoria]
    N = 2e6
    esperado = max((329 * Cf / N) ** 0.333, th)
    assert fe.faixa_admissivel(categoria, N)[0] == pytest.approx(esperado)


def test_vida_infinita_usa_o_limite():
    assert fe.faixa_admissivel("A", 1e9)[0] == pytest.approx(165.0)


def test_categoria_f_h4_b():
    assert fe.faixa_admissivel("F", 2e6)[0] == pytest.approx((11e4 * 160e10 / 2e6) ** 0.167)


def test_fatores_r_pjp_e_r_fil():
    assert fe.fator_r_pjp(16, 8, 8) == pytest.approx((1.12 - 1.01 * 0.5 + 1.24 * 0.5) / 16**0.167)
    assert fe.fator_r_fil(16, 8) == pytest.approx((0.103 + 1.24 * 0.5) / 16**0.167)
    assert fe.fator_r_fil(8, 20) == 1.0
    sr, texto = fe.faixa_admissivel("C''", 2e6, R=0.5)
    assert sr == pytest.approx(0.5 * (14.4e11 / 2e6) ** 0.333) and "sem σ_TH" in texto
    sr, _ = fe.faixa_admissivel("C'", 1e9, R=1.0)
    assert sr == 69.0


def test_padrao_atende_e_numero_de_ciclos():
    r = fe.calcular(P)
    assert P.N == 200 * 300 * 25
    assert r.situacao == "ATENDE"
    assert fe.calcular(fe.com(P, ciclos_informados=1e5)).entrada.N == 1e5


def test_dispensas_h2_5_e_h2_6():
    d = fe.Detalhe("Comprimido", rotulo("5.8", "C"), -20.0, -150.0)
    r = fe.calcular(fe.com(P, detalhes=(d,)))
    v = [x for x in r.grupos[0].linhas if x.nome == "Faixa de variação de tensões"][0]
    assert v.status == "N/A" and "H.2.5" in v.referencia
    r = fe.calcular(fe.com(P, ciclos_informados=10_000.0))
    assert all(x.status == "N/A" for g in r.grupos for x in g.linhas if x.nome.startswith("Faixa"))


def test_inversao_usa_a_diferenca_algebrica():
    d = fe.Detalhe("Inversão", rotulo("1.1", "A"), 100.0, -80.0)
    r = fe.calcular(fe.com(P, detalhes=(d,)))
    v = [x for x in r.grupos[0].linhas if x.nome == "Faixa de variação de tensões"][0]
    assert v.solicitante == 180.0 and v.status == "NÃO OK"


def test_limite_de_aplicacao_h2_2():
    d = fe.Detalhe("Alta", rotulo("1.1", "A"), 300.0, 250.0)
    r = fe.calcular(fe.com(P, detalhes=(d,)))
    assert r.grupos[0].linhas[0].status == "NÃO OK"


def test_tabela_e_validacao():
    assert fe.detalhes_de_tabela(fe.tabela_dos_detalhes(P.detalhes)) == P.detalhes
    assert fe.validar(fe.com(P, detalhes=()))
    d = fe.Detalhe("Errado", fe.ROTULOS[0], 10.0, 50.0)
    assert fe.validar(fe.com(P, detalhes=(d,)))


def test_registro_e_memorial():
    reg = fe.registro(fe.calcular(P))
    ap.conferir_registro_e_memorial(reg, fe.MODULO_ID)
    ap.conferir_entradas_curadas(reg, fe.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
    assert ap.metricas(t)["Ciclos na vida útil N"] == "1.500.000"
