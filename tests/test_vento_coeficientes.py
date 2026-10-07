"""Coeficientes aerodinâmicos da NBR 6123:2023 (seção 6): Tabelas 6, 7 e 8, pressão interna, arrasto.

Os números esperados são os impressos nas tabelas e figuras da norma. O ``C_a`` das Figuras 4 e 5 é
conferido nos cruzamentos das isolinhas com a linha de cima do gráfico (onde o nível é exatamente o
da curva) e pelas propriedades físicas que o gráfico mostra (cresce com a altura, cai com a
turbulência).
"""

from __future__ import annotations

import math

import pytest

from core import vento_coeficientes as c
from core.vento_arrasto_dados import (
    COLUNAS_L1_SOBRE_L2,
    FIGURA_4_BAIXA_TURBULENCIA,
    FIGURA_5_ALTA_TURBULENCIA,
)


# ------------------------------------------------------------------------------- Tabela 6
@pytest.mark.parametrize(
    ("a", "b", "h", "faixa", "esperado"),
    [
        # h/b ≤ 1/2, a/b ≤ 3/2
        (20, 20, 5, "h/b ≤ 1/2", c.LinhaParede(-0.8, -0.5, 0.7, -0.4, 0.7, -0.4, -0.8, -0.4, -0.9)),
        # h/b ≤ 1/2, 2 ≤ a/b ≤ 4
        (40, 20, 5, "h/b ≤ 1/2", c.LinhaParede(-0.8, -0.4, 0.7, -0.3, 0.7, -0.5, -0.9, -0.5, -1.0)),
        # 1/2 < h/b ≤ 3/2
        (
            20,
            20,
            15,
            "1/2 < h/b ≤ 3/2",
            c.LinhaParede(-0.9, -0.5, 0.7, -0.5, 0.7, -0.5, -0.9, -0.5, -1.1),
        ),
        (
            40,
            20,
            15,
            "1/2 < h/b ≤ 3/2",
            c.LinhaParede(-0.9, -0.4, 0.7, -0.3, 0.7, -0.6, -0.9, -0.5, -1.1),
        ),
        # 3/2 < h/b ≤ 6
        (
            20,
            20,
            40,
            "3/2 < h/b ≤ 6",
            c.LinhaParede(-1.0, -0.6, 0.8, -0.6, 0.8, -0.6, -1.0, -0.6, -1.2),
        ),
        (
            80,
            20,
            40,
            "3/2 < h/b ≤ 6",
            c.LinhaParede(-1.0, -0.5, 0.8, -0.3, 0.8, -0.6, -1.0, -0.6, -1.2),
        ),
    ],
)
def test_tabela_6_linha_a_linha(a, b, h, faixa, esperado):
    r = c.coeficientes_paredes(a, b, h)
    assert r.faixa_h_b == faixa
    obtido = (
        r.a1_b1_0,
        r.a2_b2_0,
        r.c_0,
        r.d_0,
        r.a_90,
        r.b_90,
        r.c1_d1_90,
        r.c2_d2_90,
        r.cpe_medio,
    )
    assert obtido == pytest.approx(tuple(esperado))
    assert not r.avisos


def test_tabela_6_limites_das_faixas_de_h_sobre_b_pertencem_a_faixa_de_baixo():
    assert c.coeficientes_paredes(20, 20, 10).faixa_h_b == "h/b ≤ 1/2"  # h/b = 0,5
    assert c.coeficientes_paredes(20, 20, 30).faixa_h_b == "1/2 < h/b ≤ 3/2"  # 1,5
    assert c.coeficientes_paredes(20, 20, 120).faixa_h_b == "3/2 < h/b ≤ 6"  # 6,0
    assert not c.coeficientes_paredes(20, 20, 120).avisos
    assert any("h/b" in aviso for aviso in c.coeficientes_paredes(20, 20, 130).avisos)


def test_tabela_6_interpola_a_sobre_b_entre_3_2_e_2_nota_2():
    meio = c.coeficientes_paredes(35, 20, 5)  # a/b = 1,75
    curta = c.coeficientes_paredes(30, 20, 5)  # 1,5
    longa = c.coeficientes_paredes(40, 20, 5)  # 2
    assert meio.a2_b2_0 == pytest.approx((curta.a2_b2_0 + longa.a2_b2_0) / 2)
    assert meio.b_90 == pytest.approx((curta.b_90 + longa.b_90) / 2)
    assert meio.cpe_medio == pytest.approx((curta.cpe_medio + longa.cpe_medio) / 2)


def test_tabela_6_partes_a3_e_b3_nota_3():
    assert c.coeficientes_paredes(20, 20, 5).a3_b3_0 == c.coeficientes_paredes(20, 20, 5).a2_b2_0
    assert c.coeficientes_paredes(40, 20, 5).a3_b3_0 == -0.2
    assert c.coeficientes_paredes(80, 20, 5).a3_b3_0 == -0.2
    # a/b = 1,5: entre A2/B2 (da linha curta, −0,5) e −0,2.
    assert c.coeficientes_paredes(30, 20, 5).a3_b3_0 == pytest.approx((-0.5 + -0.2) / 2)


def test_tabela_6_aviso_de_a_sobre_b_acima_de_4_e_erros():
    assert any("a/b" in aviso for aviso in c.coeficientes_paredes(100, 20, 5).avisos)
    with pytest.raises(ValueError):
        c.coeficientes_paredes(10, 20, 5)  # a deve ser o maior lado
    with pytest.raises(ValueError):
        c.coeficientes_paredes(20, 20, 0)


# ------------------------------------------------------------------------------- Tabela 7
def test_tabela_7_linhas_de_cada_faixa():
    # h/b ≤ 1/2, θ = 10°
    r = c.coeficientes_telhado_duas_aguas(60, 30, 10, 10)
    assert (r.efi_90, r.ghj_90, r.eg_0, r.fh_0) == pytest.approx((-1.2, -0.4, -0.8, -0.6))
    assert (r.empena, r.canto, r.beiral, r.cumeeira) == (-1.4, -1.4, None, -1.2)
    # 1/2 < h/b ≤ 3/2, θ = 20°
    r = c.coeficientes_telhado_duas_aguas(60, 30, 30, 20)
    assert (r.efi_90, r.ghj_90, r.eg_0, r.fh_0) == pytest.approx((-0.7, -0.5, -0.8, -0.6))
    assert (r.empena, r.canto, r.beiral, r.cumeeira) == (-1.5, -1.5, -1.5, -1.0)
    # 3/2 < h/b ≤ 6, θ = 40°
    r = c.coeficientes_telhado_duas_aguas(60, 20, 40, 40)
    assert (r.efi_90, r.ghj_90, r.eg_0, r.fh_0) == pytest.approx((-0.2, -0.5, -0.8, -0.7))
    assert (r.empena, r.canto, r.beiral, r.cumeeira) == (-1.0, None, None, None)


def test_tabela_7_telhado_plano_theta_zero():
    r = c.coeficientes_telhado_duas_aguas(60, 30, 10, 0)
    assert (r.efi_90, r.ghj_90, r.eg_0, r.fh_0) == pytest.approx((-0.8, -0.4, -0.8, -0.4))
    assert (r.empena, r.canto, r.beiral, r.cumeeira) == (-2.0, -2.0, -2.0, None)


def test_tabela_7_interpola_theta_e_trata_celula_vazia_como_sem_valor():
    meio = c.coeficientes_telhado_duas_aguas(60, 30, 10, 7.5)  # entre 5° e 10°
    assert meio.efi_90 == pytest.approx((-0.9 + -1.2) / 2)
    assert meio.canto == pytest.approx((-1.2 + -1.4) / 2)
    assert meio.beiral is None  # a 10° a célula é vazia: não há valor para interpolar
    entre_15_e_20 = c.coeficientes_telhado_duas_aguas(60, 30, 10, 17.0)
    assert entre_15_e_20.canto is None  # a 20° a célula é vazia
    assert entre_15_e_20.empena == pytest.approx(-1.4 + (-1.0 - -1.4) * (17 - 15) / 5)  # −1,24


def test_tabela_7_partes_i_e_j_nota_3():
    quadrado = c.coeficientes_telhado_duas_aguas(30, 30, 10, 10)  # a/b = 1
    assert quadrado.ij_0 == quadrado.fh_0
    assert c.coeficientes_telhado_duas_aguas(60, 30, 10, 10).ij_0 == -0.2  # a/b = 2
    assert c.coeficientes_telhado_duas_aguas(90, 30, 10, 10).ij_0 == -0.2  # a/b = 3
    meio = c.coeficientes_telhado_duas_aguas(45, 30, 10, 10)  # a/b = 1,5
    assert meio.ij_0 == pytest.approx((-0.6 + -0.2) / 2)


def test_tabela_7_avisos_e_erros():
    assert any("60°" in aviso for aviso in c.coeficientes_telhado_duas_aguas(60, 30, 10, 70).avisos)
    assert any("h/b" in aviso for aviso in c.coeficientes_telhado_duas_aguas(60, 10, 70, 10).avisos)
    with pytest.raises(ValueError):
        c.coeficientes_telhado_duas_aguas(60, 30, 10, -1)
    with pytest.raises(ValueError):
        c.coeficientes_telhado_duas_aguas(10, 30, 10, 10)


# ------------------------------------------------------------------------------- Tabela 8
def test_tabela_8_linhas():
    r = c.coeficientes_telhado_uma_agua(60, 30, 10, 10)
    assert (r.hi_90, r.lj_90, r.h_45, r.l_45) == pytest.approx((-1.0, -0.5, -1.0, -0.8))
    assert (r.hl_0_ate_b2, r.hl_0_de_b2_a_a2) == pytest.approx((-1.0, -0.5))
    assert (r.h_m45, r.l_m45, r.hi_m90, r.lj_m90) == pytest.approx((-0.8, -1.0, -0.4, -1.0))
    assert (r.h1, r.h2, r.l1, r.l2, r.he, r.le) == pytest.approx(
        (-2.0, -1.5, -2.0, -1.5, -2.0, -2.0)
    )
    r = c.coeficientes_telhado_uma_agua(60, 30, 10, 30)
    assert (r.hi_90, r.lj_90) == pytest.approx((-0.5, -0.5))
    assert (r.h_m45, r.l_m45, r.hi_m90, r.lj_m90) == pytest.approx((-0.1, -0.6, 0.0, -0.6))
    assert (r.h1, r.h2, r.l1, r.l2) == pytest.approx((-1.8, -0.5, -0.5, -0.5))


def test_tabela_8_interpola_e_avisa_fora_do_campo():
    meio = c.coeficientes_telhado_uma_agua(60, 30, 10, 12.5)  # entre 10° e 15°
    assert meio.hi_90 == pytest.approx((-1.0 + -0.9) / 2)
    assert meio.hi_m90 == pytest.approx((-0.4 + -0.3) / 2)
    assert any("5°" in a for a in c.coeficientes_telhado_uma_agua(60, 30, 10, 2).avisos)
    assert any("30°" in a for a in c.coeficientes_telhado_uma_agua(60, 30, 10, 35).avisos)
    assert any("h/b" in a for a in c.coeficientes_telhado_uma_agua(60, 30, 60, 10).avisos)


def test_tabela_8_partes_i_e_j_nota_1():
    assert c.coeficientes_telhado_uma_agua(30, 30, 10, 10).ij_0 == -1.0  # a/b = 1: igual a H e L
    assert c.coeficientes_telhado_uma_agua(60, 30, 10, 10).ij_0 == -0.2  # a/b = 2
    assert c.coeficientes_telhado_uma_agua(45, 30, 10, 10).ij_0 == pytest.approx((-1.0 + -0.2) / 2)


# ------------------------------------------------------------------------------- pressão interna
def _valores(sugestoes):
    return [s.valor for s in sugestoes]


def test_cpi_quatro_faces_considera_os_dois_valores():
    for alpha in (0, 90):
        assert _valores(c.sugerir_cpi("quatro_faces", alpha)) == [-0.3, 0.0]


def test_cpi_duas_faces_opostas_permeaveis_depende_da_direcao():
    # Paredes longas permeáveis: o vento a 90° bate nelas (+0,2); a 0° bate nas curtas (−0,3).
    assert _valores(c.sugerir_cpi("duas_faces_longas", 90)) == [0.2]
    assert _valores(c.sugerir_cpi("duas_faces_longas", 0)) == [-0.3]
    assert _valores(c.sugerir_cpi("duas_faces_curtas", 0)) == [0.2]
    assert _valores(c.sugerir_cpi("duas_faces_curtas", 90)) == [-0.3]


def test_cpi_edificacao_estanque_e_erros():
    assert _valores(c.sugerir_cpi("estanque", 0)) == [-0.2, 0.0]
    with pytest.raises(ValueError):
        c.sugerir_cpi("inventado", 0)
    with pytest.raises(ValueError):
        c.sugerir_cpi("quatro_faces", 45)
    assert all(
        s.referencia.startswith("NBR 6123:2023, 6.3.2") for s in c.sugerir_cpi("estanque", 0)
    )


@pytest.mark.parametrize(
    ("razao", "esperado"),
    [
        (1.0, 0.1),
        (1.5, 0.3),
        (2.0, 0.5),
        (3.0, 0.6),
        (6.0, 0.8),
        (10.0, 0.8),
        (0.5, 0.1),
        (2.5, 0.55),
    ],
)
def test_cpi_abertura_dominante_a_barlavento(razao, esperado):
    r = c.cpi_abertura_dominante("barlavento", razao_aberturas=razao)
    assert r.valor == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("razao", "esperado"),
    [
        (0.25, -0.4),
        (0.5, -0.5),
        (0.75, -0.6),
        (1.0, -0.7),
        (1.5, -0.8),
        (3.0, -0.9),
        (5.0, -0.9),
        (1.25, -0.75),
    ],
)
def test_cpi_abertura_dominante_em_zona_de_alta_succao(razao, esperado):
    assert c.cpi_abertura_dominante(
        "paralela_alta_succao", razao_aberturas=razao
    ).valor == pytest.approx(esperado)


def test_cpi_abertura_dominante_a_sotavento_ou_paralela_e_o_ce_da_zona():
    assert c.cpi_abertura_dominante("sotavento", ce_da_zona=-0.4).valor == -0.4
    assert c.cpi_abertura_dominante("paralela", ce_da_zona=-0.5).valor == -0.5
    with pytest.raises(ValueError):
        c.cpi_abertura_dominante("sotavento")
    with pytest.raises(ValueError):
        c.cpi_abertura_dominante("barlavento")
    with pytest.raises(ValueError):
        c.cpi_abertura_dominante("teto", razao_aberturas=1)


# ------------------------------------------------------------------------------- alta turbulência
def test_criterios_de_alta_turbulencia():
    ok, motivos = c.verificar_alta_turbulencia(
        30.0, 40.0, 20.0, altura_media_vizinhanca_m=20.0, extensao_vizinhanca_m=600.0
    )
    assert ok and not motivos
    ok, motivos = c.verificar_alta_turbulencia(
        30.0, 40.0, 10.0, altura_media_vizinhanca_m=20.0, extensao_vizinhanca_m=600.0
    )
    assert not ok and any("profundidade/largura" in m for m in motivos)  # 10/40 = 0,25 < 1/3
    ok, motivos = c.verificar_alta_turbulencia(
        50.0, 40.0, 40.0, altura_media_vizinhanca_m=20.0, extensao_vizinhanca_m=2500.0
    )
    assert not ok and any("duas vezes" in m for m in motivos)
    ok, motivos = c.verificar_alta_turbulencia(
        30.0, 40.0, 20.0, altura_media_vizinhanca_m=20.0, extensao_vizinhanca_m=300.0
    )
    assert not ok and any("500 m" in m for m in motivos)
    ok, motivos = c.verificar_alta_turbulencia(
        90.0, 40.0, 40.0, altura_media_vizinhanca_m=60.0, extensao_vizinhanca_m=5000.0
    )
    assert not ok and any("80 m" in m for m in motivos)


# ------------------------------------------------------------------------------- C_a
def _ca(h_sobre_l1, l1_sobre_l2, **kw):
    # ℓ₁ = 1 m: h/ℓ₁ = h; ℓ₂ = 1/(ℓ₁/ℓ₂)
    return c.coeficiente_arrasto_paralelepipedo(h_sobre_l1, 1.0, 1.0 / l1_sobre_l2, **kw)


def test_ca_nos_nos_da_grade_devolve_o_valor_da_tabela():
    for h, linha in FIGURA_4_BAIXA_TURBULENCIA.items():
        for razao, valor in zip(COLUNAS_L1_SOBRE_L2, linha, strict=True):
            assert _ca(h, razao).valor == pytest.approx(valor, abs=1e-9)
    for h, linha in FIGURA_5_ALTA_TURBULENCIA.items():
        for razao, valor in zip(COLUNAS_L1_SOBRE_L2, linha, strict=True):
            assert _ca(h, razao, alta_turbulencia=True).valor == pytest.approx(valor, abs=1e-9)


def test_ca_figura_4_nos_cruzamentos_das_isolinhas_com_o_alto_do_grafico():
    # Em h/ℓ₁ = 40 cada isolinha termina na linha de cima, com o nível exato impresso nela.
    # ℓ₁/ℓ₂ lido na escala logarítmica do gráfico (4,0 a 0,2).
    pontos = {2.0: 1.006, 1.9: 0.877, 1.8: 0.776, 1.7: 0.676, 1.6: 0.598, 1.5: 0.527, 1.4: 0.447,
              1.3: 0.400, 1.2: 0.347, 1.1: 0.300, 1.0: 0.249}  # fmt: skip
    for nivel, razao in pontos.items():
        assert _ca(40.0, razao).valor == pytest.approx(nivel, abs=0.04), (nivel, razao)


def test_ca_figura_5_nos_cruzamentos_das_isolinhas_com_o_alto_do_grafico():
    # Em h/ℓ₁ = 6 (linha de cima da Figura 5), com a abscissa lida na escala logarítmica.
    pontos = {
        1.5: 3.28,
        1.4: 2.78,
        1.3: 2.23,
        1.2: 1.73,
        1.1: 1.10,
        1.0: 0.639,
        0.9: 0.425,
        0.8: 0.287,
    }
    for nivel, razao in pontos.items():
        assert _ca(6.0, razao, alta_turbulencia=True).valor == pytest.approx(nivel, abs=0.04)


def test_ca_valores_lidos_a_olho_no_grafico():
    # Cubo (h = ℓ₁ = ℓ₂) em baixa turbulência: ≈ 1,1 a 1,2; em alta turbulência o arrasto é menor.
    assert _ca(1.0, 1.0).valor == pytest.approx(1.13, abs=0.04)
    assert _ca(1.0, 1.0, alta_turbulencia=True).valor == pytest.approx(0.91, abs=0.04)
    assert _ca(1.0, 1.0, alta_turbulencia=True).valor < _ca(1.0, 1.0).valor
    # Torre esbelta de seção quadrada (h/ℓ₁ = 10, ℓ₁/ℓ₂ = 1).
    assert _ca(10.0, 1.0).valor == pytest.approx(1.56, abs=0.05)


def test_ca_cresce_com_a_altura_em_toda_a_grade():
    for tabela in (FIGURA_4_BAIXA_TURBULENCIA, FIGURA_5_ALTA_TURBULENCIA):
        alturas = sorted(tabela)
        for coluna in range(len(COLUNAS_L1_SOBRE_L2)):
            valores = [tabela[h][coluna] for h in alturas]
            assert valores == sorted(valores)


def test_ca_interpolacao_e_continua_entre_os_nos():
    anterior = _ca(1.0, 1.0).valor
    for passo in range(1, 11):
        atual = _ca(1.0 + 0.05 * passo, 1.0).valor
        assert atual >= anterior - 1e-12
        assert atual - anterior < 0.05
        anterior = atual


def test_ca_fora_do_grafico_usa_o_contorno_e_avisa():
    abaixo = c.coeficiente_arrasto_paralelepipedo(2.0, 20.0, 40.0)  # h/ℓ₁ = 0,1
    assert abaixo.valor == pytest.approx(_ca(0.5, 0.5).valor)
    assert any("h/ℓ₁" in aviso for aviso in abaixo.avisos)
    acima = _ca(60.0, 1.0)
    assert acima.valor == pytest.approx(_ca(40.0, 1.0).valor) and acima.avisos
    estreito = _ca(5.0, 10.0)
    assert estreito.valor == pytest.approx(_ca(5.0, 4.0).valor)
    assert any("ℓ₁/ℓ₂" in aviso for aviso in estreito.avisos)
    figura_5_alta = _ca(10.0, 1.0, alta_turbulencia=True)
    assert figura_5_alta.valor == pytest.approx(_ca(6.0, 1.0, alta_turbulencia=True).valor)
    assert not _ca(1.0, 1.0).avisos
    with pytest.raises(ValueError):
        c.coeficiente_arrasto_paralelepipedo(0.0, 1.0, 1.0)


# ------------------------------------------------------------------------------- vizinhança
def test_fator_de_vizinhanca():
    # a = b = 20 m: semidiagonal 14,1 m, d* = 14,1 m.
    d_estrela = 0.5 * math.hypot(20.0, 20.0)
    assert c.fator_de_vizinhanca(d_estrela * 1.0, 20, 20) == pytest.approx(1.3)
    assert c.fator_de_vizinhanca(d_estrela * 3.0, 20, 20) == pytest.approx(1.0)
    assert c.fator_de_vizinhanca(d_estrela * 2.0, 20, 20) == pytest.approx(1.15)  # meio do caminho
    assert c.fator_de_vizinhanca(0.0, 20, 20) == 1.3
    # d* é o menor entre b e a semidiagonal: planta alongada → b.
    assert c.fator_de_vizinhanca(10.0, 100, 10) == pytest.approx(1.3)  # s/d* = 1,0
    # Cobertura: o valor máximo já em s/d* ≤ 0,5.
    assert c.fator_de_vizinhanca(0.5 * d_estrela, 20, 20, na_cobertura=True) == pytest.approx(1.3)
    # Em s/d* = 1,0 a parede ainda tem 1,3, mas a cobertura já desceu: 1,3 − 0,3·(1,0 − 0,5)/2,5.
    assert c.fator_de_vizinhanca(d_estrela, 20, 20) == pytest.approx(1.3)
    assert c.fator_de_vizinhanca(d_estrela, 20, 20, na_cobertura=True) == pytest.approx(1.24)
    assert c.fator_de_vizinhanca(100.0, 20, 20, na_cobertura=True) == 1.0
    with pytest.raises(ValueError):
        c.fator_de_vizinhanca(-1.0, 20, 20)


# ------------------------------------------------------------------------------- atrito e torção
def test_forca_de_atrito_6_1_5():
    # h = 6 ≤ ℓ₁ = 20: F_t = C_t·q·ℓ₁·(ℓ₂ − 4h) + C_t·q·2h·(ℓ₂ − 4h), com ℓ₂ = 100.
    f = c.forca_de_atrito(800.0, 0.02, 6.0, 20.0, 100.0)
    comprimento = 100.0 - 4.0 * 6.0
    assert f.aplica
    assert f.telhado_kN == pytest.approx(0.02 * 0.8 * 20.0 * comprimento)
    assert f.paredes_kN == pytest.approx(0.02 * 0.8 * 2.0 * 6.0 * comprimento)
    assert f.total_kN == pytest.approx(f.telhado_kN + f.paredes_kN)
    # h ≥ ℓ₁: o termo é ℓ₂ − 4ℓ₁.
    g = c.forca_de_atrito(800.0, 0.02, 30.0, 10.0, 100.0)
    assert g.telhado_kN == pytest.approx(0.02 * 0.8 * 10.0 * (100.0 - 40.0))
    # ℓ₂ ≤ 4·min(h, ℓ₁): sem atrito.
    nulo = c.forca_de_atrito(800.0, 0.02, 6.0, 20.0, 24.0)
    assert not nulo.aplica and nulo.total_kN == 0.0


def test_excentricidades_da_forca_de_arrasto():
    assert c.excentricidades(60.0, 30.0, com_vizinhanca=False) == pytest.approx((4.5, 2.25))
    assert c.excentricidades(60.0, 30.0, com_vizinhanca=True) == pytest.approx((9.0, 4.5))
