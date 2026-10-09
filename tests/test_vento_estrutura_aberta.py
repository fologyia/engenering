"""Vento em estruturas abertas (NBR 6123:2023, capítulo 8): coeficientes e o modelo de pórticos.

As curvas das Figuras 12 e 14 foram transcritas da página renderizada da norma; os pontos abaixo
estão sobre a grade da figura. O exemplo de plataforma é conferido com a conta à mão.
"""

from __future__ import annotations

import math

import pytest

from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb


# ------------------------------------------------------------------ Figura 12
@pytest.mark.parametrize(
    ("phi", "ca"),
    [
        (0.0, 2.0),
        (0.1, 1.9),
        (0.2, 1.8),
        (0.3, 1.7),
        (0.4, 1.65),
        (0.5, 1.6),
        (0.6, 1.6),
        (0.7, 1.6),
        (0.8, 1.7),
        (0.9, 1.8),
        (0.95, 1.9),
        (1.0, 2.0),
    ],
)
def test_figura_12(phi, ca):
    assert va.ca_reticulado_plano(phi) == pytest.approx(ca)


def test_figura_12_fora_do_intervalo():
    with pytest.raises(va.VentoAbertoInvalido):
        va.ca_reticulado_plano(1.2)


# ------------------------------------------------------------------ Figura 14
@pytest.mark.parametrize(
    ("phi", "e_h", "eta"),
    [
        (0.6, 0.5, 0.2),
        (0.6, 0.3, 0.2),  # abaixo de 0,5 vale a curva "≤ 0,5"
        (0.8, 1.0, 0.3),
        (0.6, 3.0, 0.5),
        (0.7, 6.0, 0.8),
        (0.6, 7.0, 1.0),
        (0.2, 10.0, 1.0),
        (0.3, 2.0, 1.1 - 0.7 * 0.5),  # reta de (0; 1,1) a (0,6; 0,4)
        (0.0, 0.5, 1.0),  # o trecho tracejado acima de 1,0 vale 1,0
        (0.6, 1.5, 0.35),  # entre as curvas 1 e 2
    ],
)
def test_figura_14(phi, e_h, eta):
    assert va.fator_de_protecao(phi, e_h) == pytest.approx(eta)


def test_coeficiente_de_n_reticulados():
    assert va.ca_de_n_reticulados(1.8, 3, 0.5) == pytest.approx(1.8 * 2.0)
    assert va.ca_de_n_reticulados(1.8, 1, 0.5) == pytest.approx(1.8)


# ------------------------------------------------------------------ Tabelas 27 e 28
@pytest.mark.parametrize(
    ("re", "ca"), [(1e5, 1.2), (4.19e5, 1.2), (4.2e5, 0.6), (9e5, 0.7), (3e6, 0.8)]
)
def test_tabela_27(re, ca):
    assert va.ca_cilindro(re) == ca


def test_reynolds():
    assert va.numero_de_reynolds(30.0, 2.0) == pytest.approx(70_000 * 60)


@pytest.mark.parametrize(
    ("razao", "tipo", "k"),
    [
        (2.0, "faces_planas", 0.62),
        (10.0, "circular_subcritico", 0.68),
        (15.0, "circular_subcritico", (0.68 + 0.74) / 2),
        (100.0, "circular_acima_do_critico", 1.0),
        (500.0, "faces_planas", 1.0),
        (1.0, "faces_planas", 0.62),
    ],
)
def test_tabela_28(razao, tipo, k):
    assert va.fator_k_comprimento(razao, tipo) == pytest.approx(k)


# ------------------------------------------------------------------ o modelo
def plataforma(**troca) -> va.GeometriaAberta:
    dados = dict(
        comprimento_x_m=12.0,
        largura_y_m=6.0,
        cotas_m=(4.0,),
        vaos_x=2,
        vaos_y=1,
        largura_pilar_m=0.25,
        altura_viga_m=0.30,
        largura_diagonal_x_m=0.076,
        largura_diagonal_y_m=0.076,
    )
    dados.update(troca)
    return va.GeometriaAberta(**dados)


VENTO = va.ParametrosVento(v0_m_s=35.0, categoria="II", grupo_s3=3)


def test_plataforma_de_um_piso_confere_com_a_conta_a_mao():
    r = va.calcular_vento_aberto(plataforma(), VENTO)
    q = vb.calcular_vento_no_local(35.0, categoria="II", classe="A", altura_m=5.1).q_N_m2 / 1e3
    # Vento em X: 3 pórticos (x = 0, 6, 12 m); os das pontas têm as diagonais de Y.
    diag = 1 * 2 * math.hypot(6.0, 4.0) * 0.076
    braco = 2 * 0.25 * 4.0 + 0.30 * 6.0 + diag
    simples = 2 * 0.25 * 4.0 + 0.30 * 6.0
    phi_b, phi_s = braco / 24.0, simples / 24.0
    planos = r.x.planos
    assert [p.contraventado for p in planos] == [True, False, True]
    assert planos[0].phi == pytest.approx(phi_b) and planos[1].phi == pytest.approx(phi_s)
    assert planos[0].eta == 1.0
    assert planos[1].eta == pytest.approx(va.fator_de_protecao(phi_b, 6.0 / 4.0))
    assert planos[2].eta == pytest.approx(va.fator_de_protecao(phi_s, 6.0 / 4.0))
    # Faixa do nível 1: de 2,0 m (meio do andar) a 5,1 m (topo do guarda-corpo).
    nivel = r.x.niveis[0]
    assert nivel.faixa_m == (2.0, 5.1)
    a_braco = 2 * 0.25 * 2.0 + 0.30 * 6.0 + diag / 2
    a_simples = 2 * 0.25 * 2.0 + 0.30 * 6.0
    esperado = q * (
        planos[0].ca * a_braco
        + planos[1].eta * planos[1].ca * a_simples
        + planos[2].eta * planos[2].ca * a_braco
    )
    assert nivel.estrutura_kN == pytest.approx(esperado)
    # Guarda-corpos de barlavento e sotavento (afastados de 12 m: η = 1).
    assert nivel.guarda_corpo_kN == pytest.approx(
        va.ca_reticulado_plano(0.3) * q * 0.3 * 1.1 * 6 * 2
    )
    assert r.x.cortantes_dos_andares_kN == pytest.approx((nivel.total_kN,))


def test_dois_pisos_acumulam_o_cortante():
    r = va.calcular_vento_aberto(plataforma(cotas_m=(3.0, 6.0)), VENTO)
    f1, f2 = r.y.forcas_nos_niveis_kN
    assert r.y.cortantes_dos_andares_kN == pytest.approx((f1 + f2, f2))
    assert r.y.niveis[0].faixa_m == (1.5, 4.5) and r.y.niveis[1].faixa_m == (4.5, 7.1)
    assert r.y.momento_na_base_kNm == pytest.approx(3.0 * f1 + 6.0 * f2)


def test_sem_guarda_corpo_nao_ha_forca_de_guarda_corpo():
    r = va.calcular_vento_aberto(plataforma(guarda_corpo=False), VENTO)
    assert r.x.niveis[0].guarda_corpo_kN == 0.0
    assert r.x.niveis[0].faixa_m == (2.0, 4.0)


def test_equipamento_cilindrico_usa_tabelas_27_e_28():
    tanque = va.Equipamento("Tanque", 1, va.FORMA_CILINDRO, 2.0, 2.0, 3.0, peso_kN=80.0)
    r = va.calcular_vento_aberto(plataforma(equipamentos=(tanque,)), VENTO)
    vento = vb.calcular_vento_no_local(35.0, categoria="II", classe="A", altura_m=7.0)
    re = va.numero_de_reynolds(vento.vk_m_s, 2.0)
    ca = va.ca_cilindro(re) * va.fator_k_comprimento(
        2 * 3.0 / 2.0, "circular_subcritico" if re < 4.2e5 else "circular_acima_do_critico"
    )
    assert r.x.niveis[0].equipamentos_kN == pytest.approx(ca * vento.q_N_m2 / 1e3 * 2.0 * 3.0)
    assert "Tanque" in r.x.detalhes_equipamentos[0]


def test_equipamento_caixa_usa_a_medida_frontal_de_cada_direcao():
    caixa = va.Equipamento("Painel", 1, va.FORMA_CAIXA, 1.0, 3.0, 2.0)
    r = va.calcular_vento_aberto(plataforma(equipamentos=(caixa,)), VENTO)
    q = vb.calcular_vento_no_local(35.0, categoria="II", classe="A", altura_m=6.0).q_N_m2 / 1e3
    assert r.x.niveis[0].equipamentos_kN == pytest.approx(2.0 * q * 3.0 * 2.0)  # frontal em X: y
    assert r.y.niveis[0].equipamentos_kN == pytest.approx(2.0 * q * 1.0 * 2.0)


@pytest.mark.parametrize(
    ("troca", "trecho"),
    [
        ({"cotas_m": ()}, "nível"),
        ({"cotas_m": (4.0, 3.0)}, "crescentes"),
        ({"vaos_x": 0}, "vão"),
        ({"paineis_contraventados_x": 3}, "painéis"),
        ({"linhas_contraventadas_y": 9}, "linhas"),
        ({"indice_guarda_corpo": 0.0}, "guarda-corpo"),
        ({"equipamentos": (va.Equipamento("E", 5),)}, "nível"),
    ],
)
def test_geometria_impossivel_vira_erro(troca, trecho):
    erros = va.validar_geometria(plataforma(**troca))
    assert any(trecho in e for e in erros), erros
    with pytest.raises(va.VentoAbertoInvalido):
        va.calcular_vento_aberto(plataforma(**troca), VENTO)


def test_estrutura_esbelta_avisa_dos_efeitos_dinamicos():
    r = va.calcular_vento_aberto(
        plataforma(comprimento_x_m=3.0, largura_y_m=3.0, cotas_m=(10.0, 20.0)), VENTO
    )
    assert any("dinâmicos" in a for a in r.avisos)
