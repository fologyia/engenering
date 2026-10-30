"""Regras das soldas (NBR 8800 2025 e 2008) e o método do centro instantâneo de rotação."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import ligacoes as lg
from core import soldas as sd


# ------------------------------------------------------------------ tabelas
def test_perna_minima_pelas_chapas_em_polegada():
    # 6,3 / 12,5 / 19 da tabela são as chapas de 1/4", 1/2" e 3/4"
    assert [sd.perna_minima(t) for t in (5.0, 6.35, 6.4, 12.7, 12.8, 19.05, 19.1)] == [
        3.0, 3.0, 5.0, 5.0, 6.0, 6.0, 8.0,
    ]  # fmt: skip
    assert sd.perna_maxima(5.0) == 5.0 and sd.perna_maxima(8.0) == 6.5


def test_garganta_minima_da_penetracao_parcial_muda_na_2025():
    assert sd.garganta_minima(6.35, sd.NBR_2025) == 3.0
    assert sd.garganta_minima(30.0, sd.NBR_2025) == 8.0
    assert sd.garganta_minima(151.0, sd.NBR_2025) == 16.0  # 2025: "acima de 57 até 150"
    assert sd.garganta_minima(151.0, sd.NBR_2008) == 13.0  # 2008: "até 152"


def test_comprimentos_e_beta_do_filete_longo():
    assert sd.comprimento_minimo(5.0) == 40.0 and sd.comprimento_minimo(12.0) == 48.0
    assert sd.perna_considerada(8.0, 24.0) == 6.0  # L < 4·perna: perna = L/4
    assert sd.cobrimento_minimo(9.525) == pytest.approx(47.625)
    assert sd.cobrimento_minimo(3.0) == 25.0
    assert sd.beta_filete_longo(400.0, 4.0) == 1.0  # L = 100·perna
    assert sd.beta_filete_longo(800.0, 4.0) == pytest.approx(0.8)
    assert sd.beta_filete_longo(5000.0, 4.0) == 0.6
    assert sd.adotar(115.5) == 120.0 and sd.adotar(120.0) == 120.0


def test_coeficientes_por_combinacao_e_direcao_da_forca():
    normal = sd.coeficientes(sd.COMBINACAO_NORMAL)
    excepcional = sd.coeficientes(sd.COMBINACAO_EXCEPCIONAL)
    assert (normal.a1, normal.a2, normal.w1, normal.w2) == (1.10, 1.35, 1.25, 1.35)
    assert (excepcional.a1, excepcional.a2, excepcional.w1, excepcional.w2) == (
        1.00, 1.15, 1.05, 1.15,
    )  # fmt: skip
    assert sd.fator_direcao(0) == 1.0 and sd.fator_direcao(90) == pytest.approx(1.5)
    assert sd.fator_direcao(60) == pytest.approx(1 + 0.5 * math.sin(math.radians(60)) ** 1.5)
    # 0,60·f_w·0,707·d_w/γ_w2: o filete de 8 mm E70 da apostila, 12,192 kN/cm
    assert 10 * sd.resistencia_filete_por_mm(8.0, 485.0, 1.35) == pytest.approx(12.192, abs=1e-3)


def test_referencias_marcam_o_que_falta_conferir_na_2025():
    assert sd.ref(sd.NBR_2008, "6.5.5") == "NBR 8800:2008 6.5.5"
    assert sd.ref(sd.NBR_2025, "6.2.6.2.2") == "NBR 8800:2025 6.2.6.2.2 (a confirmar)"
    assert sd.ref(sd.NBR_2025, "6.5.5 a)") == "NBR 8800:2025 6.5.5 a)"  # visto no texto (30/10)
    assert sd.ref(sd.NBR_2025, "6.2.5.2 a)", vista_na_2025=True) == "NBR 8800:2025 6.2.5.2 a)"
    assert sd.tabela(sd.NBR_2025, "resistencia") == "Tabela 9"
    assert sd.tabela(sd.NBR_2008, "perna") == "Tabela 10"


def test_compatibilidade_do_metal_da_solda():
    assert sd.eletrodo_compativel("ASTM A36", 12.7, "E60") is True
    # penetração total à tração: com duas classes no grupo, só a maior (nota e)
    assert sd.eletrodo_compativel("ASTM A36", 12.7, "E60", so_a_maior_classe=True) is False
    assert sd.eletrodo_compativel("ASTM A36", 25.0, "E60") is False  # A36 > 19 mm: grupo II
    assert sd.eletrodo_compativel("ASTM A572 Gr 50", 12.7, "E70") is True
    assert sd.eletrodo_compativel("ZAR 250 (NBR 7008)", 2.0, "E70") is None
    # 2025, compressão normal: até 70 MPa abaixo do compatível
    assert sd.eletrodo_compativel_a_compressao("ASTM A572 Gr 50", 12.7, "E60") is True


def test_forca_minima_da_ligacao():
    assert sd.forca_minima_da_ligacao(40.0, True) == 45.0
    assert sd.forca_minima_da_ligacao(40.0, False) == 40.0
    assert sd.forca_minima_da_ligacao(-60.0, True) == 60.0


def test_combinacao_longitudinal_transversal():
    assert sd.combinacao_longitudinal_transversal(100.0, 10.0) == 110.0
    assert sd.combinacao_longitudinal_transversal(100.0, 100.0) == pytest.approx(235.0)


# ------------------------------------------------------------------ centro instantâneo
Q = sd.resistencia_filete_por_mm(6.0, 485.0, 1.35)


def _integral_do_filete_sob_momento(comprimento: float, perna: float) -> float:
    """Momento resistente de um filete reto girando em torno do meio (θ = 90° em todo ele)."""
    du = sd.deformacao_ultima(90.0, perna)
    dm = sd.deformacao_na_tensao_maxima(90.0, perna)
    n = 4000
    meio = comprimento / 2
    total = 0.0
    for i in range(n):
        y = (i + 0.5) / n * meio
        p = y / meio * du / dm
        total += Q * 1.5 * sd.fator_deformacao(p) * y * (meio / n)
    return 2 * total / 1000  # kN·m


def test_filete_unico_sob_momento_puro_confere_com_a_integral():
    r = sd.centro_instantaneo([sd.Segmento(0, 0, 0, 150)], 6.0, Q, 0.0, 0.0, 1000.0)
    assert r.convergiu
    assert abs(r.x_mm) < 1e-6 and abs(r.y_mm) < 1e-6
    assert r.capacidade_kN == pytest.approx(_integral_do_filete_sob_momento(150, 6.0), rel=2e-3)


@pytest.mark.parametrize(
    "arranjo, v, n, m",
    [
        (lg.ARRANJO_PARALELOS, 40.0, 0.0, 2.0),
        (lg.ARRANJO_TRES_LADOS, 40.0, 0.0, 3.0),
        (lg.ARRANJO_TRES_LADOS, 60.0, 20.0, 0.5),
        (lg.ARRANJO_HORIZONTAIS, -60.0, -20.0, 4.0),
        (lg.ARRANJO_CONTORNO, 0.0, 0.0, 2.0),
        (lg.ARRANJO_TRES_LADOS, 1.0, 0.0, -50.0),
    ],
)
def test_centro_instantaneo_converge_e_resiste_mais_que_o_elastico(arranjo, v, n, m):
    e = lg.EntradaSolda(arranjo=arranjo, v_sd_kN=v, n_sd_kN=n, m_sd_kNm=m)
    cir = lg.calcular(e)
    elastico = lg.calcular(replace(e, metodo=lg.METODO_ELASTICO))
    linha = cir.verificacoes[0]
    assert "6.2.5.2 b)" in linha.referencia and not cir.avisos
    assert linha.aproveitamento < elastico.verificacoes[0].aproveitamento


def test_centro_instantaneo_tende_a_regra_dos_filetes_longitudinais_e_transversais():
    # carga quase centrada: o grupo em C vai para ≈ 0,83·F_wl + 1,5·F_wt (6.2.5.2 c usa 0,85)
    segs = [sd.Segmento(*s) for s in ((0, 0, 0, 150), (0, 0, 100, 0), (0, 150, 100, 150))]
    r = sd.centro_instantaneo(segs, 6.0, Q, 0.0, 60.0, 0.01)
    du90 = sd.deformacao_ultima(90, 6.0)
    longitudinal = sd.fator_deformacao(du90 / sd.deformacao_na_tensao_maxima(0, 6.0))
    transversal = 1.5 * sd.fator_deformacao(du90 / sd.deformacao_na_tensao_maxima(90, 6.0))
    esperado = Q * (150 * longitudinal + 200 * transversal)
    assert r.convergiu and r.capacidade_kN == pytest.approx(esperado, rel=0.01)
    assert longitudinal == pytest.approx(0.83, abs=0.01)


def test_grupo_de_filetes_pela_direcao_da_forca():
    centrada = lg.calcular(lg.EntradaSolda(n_sd_kN=30.0))
    linha = centrada.verificacoes[0]
    theta = math.degrees(math.atan2(30, 40))
    assert linha.resistente == pytest.approx(10 * Q * sd.fator_direcao(theta))
    contorno = lg.calcular(lg.EntradaSolda(arranjo=lg.ARRANJO_CONTORNO))
    linha = contorno.verificacoes[0]
    assert "6.2.5.2 c)" in linha.referencia
    assert linha.resistente == pytest.approx(0.85 * Q * 300 + 1.5 * Q * 200)
    # a perna estimada é proporcional: a capacidade é linear na perna
    assert contorno.grandezas["perna_estimada_mm"] == pytest.approx(6.0 * linha.aproveitamento)


def test_grupo_inclinado_com_filetes_nas_duas_direcoes_fica_elastico():
    r = lg.calcular(lg.EntradaSolda(arranjo=lg.ARRANJO_CONTORNO, n_sd_kN=20.0))
    assert r.verificacoes[0].resistente == pytest.approx(10 * Q) and r.avisos


def test_combinacao_excepcional_e_norma_2008_no_grupo():
    excepcional = lg.calcular(lg.EntradaSolda(combinacao=sd.COMBINACAO_EXCEPCIONAL))
    assert excepcional.verificacoes[0].resistente == pytest.approx(10 * Q * 1.35 / 1.15)
    antiga = lg.calcular(lg.EntradaSolda(norma=sd.NBR_2008))
    assert any(
        "NBR 8800:2008" in v.referencia and "Tabela 10" in v.referencia for v in antiga.verificacoes
    )
