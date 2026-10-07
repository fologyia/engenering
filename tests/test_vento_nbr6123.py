"""Velocidade característica e pressão dinâmica pela NBR 6123:2023 (seções 4 e 5, anexos A e B).

Os valores esperados saem das tabelas da própria norma: a Tabela 3 inteira (S2 até 250 m, três
classes, cinco categorias), linhas da Tabela A.2 (S2 para t de 3 s a 1 h) e a Tabela B.1 (S3 por
probabilidade e vida útil). As fórmulas valem, em cada caso, o que a tabela publicou.
"""

from __future__ import annotations

import math

import pytest

from core import vento_nbr6123 as v

# Tabela 3 — S2 por altura (m); colunas: categorias I a V, em cada uma as classes A, B e C.
TABELA_3 = {
    5: (1.06, 1.04, 1.01, 0.94, 0.92, 0.89, 0.88, 0.86, 0.82, 0.79, 0.76, 0.73, 0.74, 0.72, 0.67),
    10: (1.10, 1.09, 1.06, 1.00, 0.98, 0.95, 0.94, 0.92, 0.88, 0.86, 0.83, 0.80, 0.74, 0.72, 0.67),
    15: (1.13, 1.12, 1.09, 1.04, 1.02, 0.99, 0.98, 0.96, 0.93, 0.90, 0.88, 0.84, 0.79, 0.76, 0.72),
    20: (1.15, 1.14, 1.12, 1.06, 1.04, 1.02, 1.01, 0.99, 0.96, 0.93, 0.91, 0.88, 0.82, 0.80, 0.76),
    30: (1.17, 1.17, 1.15, 1.10, 1.08, 1.06, 1.05, 1.03, 1.00, 0.98, 0.96, 0.93, 0.87, 0.85, 0.82),
    40: (1.20, 1.19, 1.17, 1.13, 1.11, 1.09, 1.08, 1.07, 1.04, 1.02, 0.99, 0.96, 0.91, 0.89, 0.86),
    50: (1.21, 1.21, 1.19, 1.15, 1.13, 1.12, 1.10, 1.09, 1.06, 1.04, 1.02, 0.99, 0.94, 0.93, 0.89),
    60: (1.22, 1.22, 1.21, 1.16, 1.15, 1.14, 1.12, 1.11, 1.09, 1.07, 1.04, 1.02, 0.97, 0.95, 0.92),
    80: (1.25, 1.25, 1.23, 1.19, 1.18, 1.17, 1.16, 1.15, 1.12, 1.10, 1.08, 1.06, 1.01, 1.00, 0.97),
    100: (1.26, 1.26, 1.25, 1.22, 1.21, 1.20, 1.18, 1.17, 1.15, 1.13, 1.11, 1.09, 1.05, 1.03, 1.01),
    120: (1.28, 1.28, 1.27, 1.24, 1.23, 1.22, 1.21, 1.20, 1.18, 1.16, 1.14, 1.12, 1.07, 1.06, 1.04),
    140: (1.29, 1.29, 1.28, 1.25, 1.24, 1.24, 1.22, 1.22, 1.20, 1.18, 1.16, 1.14, 1.10, 1.09, 1.07),
    160: (1.30, 1.30, 1.29, 1.27, 1.26, 1.25, 1.24, 1.23, 1.22, 1.20, 1.18, 1.16, 1.12, 1.11, 1.10),
    180: (1.31, 1.31, 1.30, 1.28, 1.27, 1.27, 1.26, 1.25, 1.23, 1.22, 1.20, 1.18, 1.14, 1.14, 1.12),
    200: (1.32, 1.32, 1.31, 1.29, 1.28, 1.28, 1.27, 1.26, 1.25, 1.23, 1.21, 1.20, 1.16, 1.16, 1.14),
    250: (1.33, 1.34, 1.33, 1.31, 1.31, 1.31, 1.30, 1.29, 1.28, 1.27, 1.25, 1.23, 1.20, 1.20, 1.18),
}  # fmt: skip
COLUNAS_TABELA_3 = [(c, k) for c in ("I", "II", "III", "IV", "V") for k in "ABC"]

# Tabela A.2 — S2 por intervalo de tempo (3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 600 e 3 600 s).
TABELA_A2 = {
    ("I", 5): (1.06, 1.04, 1.01, 1.00, 0.97, 0.95, 0.92, 0.90, 0.86, 0.82, 0.79, 0.76),
    ("I", 10): (1.10, 1.09, 1.06, 1.05, 1.02, 1.00, 0.97, 0.96, 0.92, 0.87, 0.85, 0.81),
    ("II", 5): (0.94, 0.92, 0.89, 0.86, 0.83, 0.80, 0.77, 0.75, 0.70, 0.65, 0.62, 0.58),
    ("II", 10): (1.00, 0.98, 0.95, 0.93, 0.90, 0.87, 0.84, 0.82, 0.77, 0.72, 0.69, 0.65),
    ("III", 5): (0.88, 0.86, 0.82, 0.78, 0.75, 0.72, 0.68, 0.67, 0.61, 0.55, 0.52, 0.48),
    ("III", 10): (0.94, 0.92, 0.88, 0.86, 0.83, 0.79, 0.76, 0.74, 0.69, 0.63, 0.59, 0.55),
    ("IV", 5): (0.79, 0.76, 0.73, 0.70, 0.67, 0.64, 0.60, 0.57, 0.51, 0.45, 0.42, 0.37),
    ("IV", 10): (0.86, 0.83, 0.80, 0.77, 0.74, 0.71, 0.67, 0.65, 0.59, 0.53, 0.49, 0.44),
}  # fmt: skip

# Tabela B.1 — S3 por vida útil (anos) e probabilidade P_m.
PROBABILIDADES_B1 = (0.10, 0.20, 0.50, 0.63, 0.75, 0.90)
TABELA_B1 = {
    2: (0.86, 0.76, 0.64, 0.60, 0.57, 0.53),
    10: (1.10, 0.98, 0.82, 0.78, 0.74, 0.68),
    25: (1.27, 1.13, 0.95, 0.90, 0.85, 0.79),
    50: (1.42, 1.26, 1.06, 1.00, 0.95, 0.88),
    100: (1.58, 1.41, 1.18, 1.11, 1.06, 0.98),
    200: (1.77, 1.57, 1.31, 1.24, 1.18, 1.09),
}


# ------------------------------------------------------------------------------- S2
@pytest.mark.parametrize("altura", sorted(TABELA_3))
def test_s2_reproduz_a_tabela_3_inteira(altura):
    for (categoria, classe), publicado in zip(COLUNAS_TABELA_3, TABELA_3[altura], strict=True):
        calculado = v.fator_s2(float(altura), categoria, classe)
        assert round(calculado, 2) == pytest.approx(publicado, abs=1e-9), (
            altura,
            categoria,
            classe,
        )


def test_tabela_1_e_a_tabela_a1_em_3_5_e_10_s():
    # Tabela 1 (b_m e p por classe) e Tabela 2 (F_r) são as colunas de 3, 5 e 10 s do Anexo A.
    assert v.PARAMETROS_S2[("II", "A")] == (1.00, 0.085)
    assert v.PARAMETROS_S2[("II", "B")] == (1.00, 0.09)
    assert v.PARAMETROS_S2[("II", "C")] == (1.00, 0.10)
    assert v.PARAMETROS_S2[("V", "C")] == (0.71, 0.175)
    assert v.PARAMETROS_S2[("III", "C")] == (0.93, 0.115)
    assert v.FATOR_RAJADA == {"A": 1.00, "B": 0.98, "C": 0.95}
    assert v.ALTURA_GRADIENTE_M == {"I": 250.0, "II": 300.0, "III": 350.0, "IV": 420.0, "V": 500.0}
    assert v.COMPRIMENTO_RUGOSIDADE_M["IV"] == 1.0


def test_categoria_v_mantem_s2_constante_ate_10_m_e_as_demais_ate_5_m():
    assert v.fator_s2(2.0, "V", "A") == v.fator_s2(10.0, "V", "A") == pytest.approx(0.74)
    assert v.fator_s2(7.0, "V", "A") == v.fator_s2(10.0, "V", "A")
    for categoria in ("I", "II", "III", "IV"):
        assert v.fator_s2(1.0, categoria, "A") == v.fator_s2(5.0, categoria, "A")
        assert v.fator_s2(9.0, categoria, "A") < v.fator_s2(10.0, categoria, "A")


def test_s2_acima_de_zg_usa_o_de_zg_e_avisa():
    detalhe = v.detalhar_s2(900.0, "III", "B")
    assert detalhe.altura_usada_m == 350.0 and detalhe.s2 == v.fator_s2(350.0, "III", "B")
    assert detalhe.avisos and "z_g" in detalhe.avisos[0]
    abaixo = v.detalhar_s2(2.0, "II", "A")
    assert abaixo.altura_usada_m == 5.0 and "5 m" in abaixo.avisos[0]
    assert not v.detalhar_s2(20.0, "II", "A").avisos


def test_s2_rejeita_categoria_ou_classe_invalida():
    with pytest.raises(ValueError):
        v.fator_s2(10.0, "VI", "A")
    with pytest.raises(ValueError):
        v.fator_s2(10.0, "II", "D")
    with pytest.raises(ValueError):
        v.fator_s2(-1.0, "II", "A")


@pytest.mark.parametrize("chave", sorted(TABELA_A2))
def test_s2_do_anexo_a_reproduz_a_tabela_a2(chave):
    categoria, altura = chave
    for tempo, publicado in zip(v.ANEXO_A_TEMPOS_S, TABELA_A2[chave], strict=True):
        calculado = v.fator_s2(float(altura), categoria, t_s=tempo)
        # A tabela é arredondada (e em poucas células truncada): uma unidade da última casa.
        assert calculado == pytest.approx(publicado, abs=0.0101), (chave, tempo)


def test_anexo_a_interpola_entre_os_intervalos_e_limita_o_campo():
    assert v.fator_s2(10.0, "II", t_s=3) == pytest.approx(1.0)
    assert v.fator_s2(10.0, "II", t_s=3600) == pytest.approx(0.65)
    meio = v.fator_s2(10.0, "II", t_s=30)  # intervalo da própria tabela
    assert meio == pytest.approx(0.87)
    entre = v.fator_s2(10.0, "II", t_s=40)
    assert v.fator_s2(10.0, "II", t_s=45) < entre < meio
    with pytest.raises(ValueError):
        v.fator_s2(10.0, "II", t_s=2)
    with pytest.raises(ValueError):
        v.fator_s2(10.0, "II", t_s=7200)


def test_intervalo_de_tempo_do_anexo_a_2_e_ponto_fixo():
    lt, v0, s1, categoria, topo = 120.0, 40.0, 1.0, "II", 60.0
    tempo = v.intervalo_de_tempo_anexo_a(lt, v0, s1, categoria, topo)
    velocidade = v0 * s1 * v.fator_s2(topo, categoria, t_s=tempo)
    assert tempo == pytest.approx(7.5 * lt / velocidade, rel=1e-6)
    assert 10.0 < tempo < 60.0
    # Mais alta e mais larga: a rajada abrange mais, o intervalo cresce.
    assert v.intervalo_de_tempo_anexo_a(300.0, v0, s1, categoria, topo) > tempo


def test_classe_pela_maior_dimensao_da_superficie_frontal():
    assert v.classe_da_edificacao(20.0) == "A"
    assert v.classe_da_edificacao(20.01) == "B"
    assert v.classe_da_edificacao(50.0) == "B"
    assert v.classe_da_edificacao(50.01) == "C"
    with pytest.raises(ValueError):
        v.classe_da_edificacao(0.0)


# ------------------------------------------------------------------------------- S3
def test_s3_da_tabela_4():
    esperado = {1: (1.11, 100), 2: (1.06, 75), 3: (1.00, 50), 4: (0.95, 37), 5: (0.83, 15)}
    for grupo, (s3, periodo) in esperado.items():
        assert v.fator_s3(grupo) == s3
        assert v.GRUPOS_S3[grupo][:2] == (s3, periodo)
        assert v.fator_s3(grupo, vedacao=True) == pytest.approx(0.92 * s3)
    with pytest.raises(ValueError):
        v.fator_s3(0)
    with pytest.raises(ValueError):
        v.fator_s3(6)


@pytest.mark.parametrize("vida", sorted(TABELA_B1))
def test_s3_estatistico_reproduz_a_tabela_b1(vida):
    for pm, publicado in zip(PROBABILIDADES_B1, TABELA_B1[vida], strict=True):
        assert v.fator_s3_estatistico(pm, vida) == pytest.approx(publicado, abs=0.0051), (vida, pm)


def test_s3_estatistico_do_grupo_3_e_50_anos_com_63_por_cento_vale_1():
    assert v.fator_s3_estatistico(0.63, 50.0) == pytest.approx(1.0, abs=0.002)
    with pytest.raises(ValueError):
        v.fator_s3_estatistico(1.0, 50.0)
    with pytest.raises(ValueError):
        v.fator_s3_estatistico(0.0, 50.0)
    with pytest.raises(ValueError):
        v.fator_s3_estatistico(0.5, 0.0)


# ------------------------------------------------------------------------------- S1
def test_s1_plano_vale_e_talude_seguem_a_secao_5_2():
    assert v.fator_s1("plano") == 1.0
    assert v.fator_s1("vale") == 0.9
    esperado = 1.0 + 2.4 * math.tan(math.radians(7.0))  # θ = 10°, z/d = 0,1
    assert v.fator_s1("talude", inclinacao_graus=10.0, z_m=5.0, d_m=50.0) == pytest.approx(esperado)
    assert v.fator_s1("morro", inclinacao_graus=60.0, z_m=0.0, d_m=30.0) == pytest.approx(1.775)
    assert v.fator_s1("talude", inclinacao_graus=2.0) == 1.0
    assert v.fator_s1("talude", inclinacao_graus=10.0, z_m=200.0, d_m=50.0) == 1.0  # nunca < 1
    with pytest.raises(ValueError):
        v.fator_s1("montanha")


# ------------------------------------------------------------------------------- Vk e q
def test_cadeia_completa_de_um_caso_conferido_a_mao():
    # V0 = 40 m/s, S1 = 1, categoria II, classe A, z = 10 m (S2 = 1,00), grupo 3 (S3 = 1,00).
    vento = v.calcular_vento_no_local(40.0, categoria="II", classe="A", altura_m=10.0, grupo_s3=3)
    assert vento.s2 == pytest.approx(1.0) and vento.s3 == 1.0
    assert vento.vk_m_s == pytest.approx(40.0)
    assert vento.q_N_m2 == pytest.approx(0.613 * 1600.0)  # 980,8 N/m²
    assert vento.q_kN_m2 == pytest.approx(0.9808)
    assert vento.classe == "A" and vento.t_s == 3.0
    assert any("V_k = V₀·S₁·S₂·S₃ = 40,00 m/s" in linha for linha in vento.memoria)
    assert any("q = 0,613·V_k²" in linha for linha in vento.memoria)


def test_vedacoes_usam_092_do_s3_so_quando_pedido():
    base = v.calcular_vento_no_local(40.0, altura_m=10.0, grupo_s3=3)
    vedacao = v.calcular_vento_no_local(40.0, altura_m=10.0, grupo_s3=3, vedacao=True)
    assert vedacao.s3 == pytest.approx(0.92)
    assert vedacao.vk_m_s == pytest.approx(0.92 * base.vk_m_s)
    assert any("0,92" in linha for linha in vedacao.memoria)
    # S3 informado vence o grupo, com ou sem o fator das vedações.
    informado = v.calcular_vento_no_local(40.0, s3=1.1, vedacao=True)
    assert informado.s3 == 1.1 and informado.grupo_s3 is None


def test_anexo_a_substitui_a_classe_no_calculo_de_vento():
    vento = v.calcular_vento_no_local(40.0, categoria="II", classe=None, t_s=600.0, altura_m=10.0)
    assert vento.classe is None and vento.t_s == 600.0
    assert vento.s2 == pytest.approx(0.69)
    assert vento.vk_m_s == pytest.approx(40.0 * 0.69)


def test_velocidade_de_projeto_dinamica():
    assert v.velocidade_de_projeto_dinamica(40.0, 1.0, 1.0) == pytest.approx(27.6)


@pytest.mark.parametrize("v0", [0.0, -5.0, float("nan"), float("inf")])
def test_v0_invalido(v0):
    with pytest.raises(ValueError):
        v.calcular_vento_no_local(v0)
