"""Degrau de escada em grade de piso (Selmec DS): os 8 casos de aceite da especificação e as bordas.

Os valores esperados saíram da planilha validada ``Degrau_Escada_Grade_NR12_Anglo_Selmec.xlsx``.
Geometria: igualdade exata (inteiros) ou tolerância de 0,01; resistências e pesos: 0,5 %.
Se um valor não bater, o teste NÃO se ajusta: mostra a diferença e a fórmula envolvida.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import degrau_escada as de

OK, NAO_OK, ALERTA, NA, INFO = "OK", "NÃO OK", "ALERTA", "N/A", "INFO"


def calcular(**alteracoes) -> de.ResultadoEscada:
    return de.calcular_escada(de.EntradaDegrau(**alteracoes))


def itens_com_status(resultado: de.ResultadoEscada, status: str) -> set[int]:
    """Números (1 a 38) das verificações com o status pedido."""
    return {i for i, v in enumerate(resultado.verificacoes, start=1) if v.status == status}


def aprox(valor: float) -> object:
    return pytest.approx(valor, rel=0.005)


# ---------------------------------------------------------------------------------------------
# Os 8 casos de aceite (seção 9 da especificação)
# ---------------------------------------------------------------------------------------------
class TestCaso1Padrao:
    """NR-12, H = 3600, L = 800."""

    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular()

    def test_espelho_e_piso(self, r):
        g = r.geometria
        assert g.faixa.nivel == 1
        assert g.n == 20
        assert g.h_mm == pytest.approx(180.0, abs=0.01)
        assert g.b_mm == pytest.approx(270.0, abs=0.01)
        assert g.blondel_mm == pytest.approx(630.0, abs=0.01)
        assert g.alfa_graus == pytest.approx(33.690, abs=0.001)

    def test_profundidade_furacao_e_projecao(self, r):
        g = r.geometria
        assert (g.C_mm, g.F_mm, g.r_mm) == (300.0, 135, 30.0)

    def test_lances(self, r):
        ln = r.lances
        assert ln.n_lances == 2 and ln.k == 10 and ln.k_min == 10
        assert ln.texto == "2 lance(s) de 10 espelhos"
        assert ln.n_degraus_grade == 18
        assert ln.projecao_total_mm == pytest.approx(5760.0, abs=0.01)

    def test_larguras_minimas(self, r):
        assert r.larguras.minima_legal_mm == 600
        assert r.larguras.minima_anglo_mm == 800

    def test_modelo_adotado(self, r):
        a = r.adotado
        assert a.modelo.nome == "DS-A4-35/3"
        assert (a.n_bb, a.n_ef) == (10, 4)

    def test_resistencia_e_peso(self, r):
        a = r.adotado
        assert a.MRd_kNm == aprox(0.1938)
        assert a.peso_grade_kg_m2 == aprox(30.301)
        assert a.peso_degrau_kg == aprox(8.727)
        assert a.g_kN_m2 == aprox(0.3567)

    def test_aproveitamentos(self, r):
        a = r.adotado
        assert a.u_flex_d == aprox(0.0613)
        assert a.u_flex_c == aprox(0.9731)
        assert a.u_cis == aprox(0.0658)
        assert a.u_fl_d == aprox(0.0939)
        assert a.u_fl_i == aprox(0.6997)
        assert a.delta_iso_mm == aprox(1.866)
        assert a.u_max == aprox(0.9731)

    def test_reacao_e_parafuso(self, r):
        rp = r.reacoes
        assert rp.R_d_kN == aprox(3.8035)
        assert rp.F_vRd_kN == aprox(24.338)
        assert rp.u_par == aprox(0.0781)

    def test_verificacoes(self, r):
        assert len(r.verificacoes) == 38
        assert itens_com_status(r, ALERTA) == {31, 35}
        assert itens_com_status(r, NAO_OK) == set()
        assert itens_com_status(r, NA) == set()
        assert de.texto_da_contagem(r.contagem) == "35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A"
        assert r.status == ALERTA


#: Linha da tabela dos 64 modelos do caso 1: λ, λp, λr, M_Rd, peso, u_flex_c, δ_iso, u_fl_i, atende.
TABELA_64_CASO_1 = [
    ("DS-A4-25/3", 115.47, 27.71, 639.47, 0.1014, 6.466, 1.856, 5.120, 1.920, False),
    ("DS-A4-30/3", 115.47, 23.25, 536.51, 0.1442, 7.596, 1.307, 2.963, 1.111, False),
    ("DS-A4-35/3", 115.47, 20.02, 462.07, 0.1938, 8.727, 0.973, 1.866, 0.700, True),
    ("DS-A2-35/3", 57.74, 20.02, 462.07, 0.2029, 9.541, 0.930, 1.866, 0.700, True),
    ("DS-B4-25/5", 72.78, 42.90, 989.99, 0.1673, 11.575, 0.904, 2.582, 0.968, True),
    ("DS-C4-40/3", 115.47, 17.58, 405.75, 0.2498, 8.565, 1.006, 1.667, 0.625, False),
    ("DS-F2-40/3", 57.74, 17.58, 405.75, 0.2633, 8.245, 0.954, 1.667, 0.625, True),
]


@pytest.mark.parametrize(
    ("nome", "lam", "lam_p", "lam_r", "mrd", "peso", "u_flex_c", "delta_iso", "u_fl_i", "atende"),
    TABELA_64_CASO_1,
)
def test_caso_1_linhas_da_tabela_dos_64_modelos(
    nome, lam, lam_p, lam_r, mrd, peso, u_flex_c, delta_iso, u_fl_i, atende
):
    r = calcular()
    linha = next(x for x in r.tabela_modelos if x.modelo.nome == nome)
    assert linha.lam == aprox(lam)
    assert linha.lam_p == aprox(lam_p)
    assert linha.lam_r == aprox(lam_r)
    assert linha.MRd_kNm == aprox(mrd)
    assert linha.peso_degrau_kg == aprox(peso)
    assert linha.u_flex_c == aprox(u_flex_c)
    assert linha.delta_iso_mm == aprox(delta_iso)
    assert linha.u_fl_i == aprox(u_fl_i)
    assert linha.atende is atende


def test_caso_1_o_dsa430_cabe_na_largura_do_catalogo_mas_nao_passa_no_calculo():
    r = calcular()
    linha = next(x for x in r.tabela_modelos if x.modelo.nome == "DS-A4-30/3")
    assert r.entrada.L_mm <= linha.modelo.L_max_mm  # 800 ≤ 800: a largura é recomendada…
    assert linha.u_max > 1 and not linha.atende  # …mas o cálculo reprova


class TestCaso2NR22:
    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(enquadramento=de.NR22)

    def test_geometria_e_lances(self, r):
        assert r.geometria.n == 20
        assert r.geometria.h_mm == pytest.approx(180.0)
        assert r.lances.n_lances == 1 and r.lances.k == 20  # lance ≤ 3600 mm
        assert r.lances.n_degraus_grade == 19
        assert r.lances.projecao_total_mm == pytest.approx(5130.0)

    def test_modelo(self, r):
        assert r.adotado.modelo.nome == "DS-A4-35/3"
        assert r.adotado.u_max == aprox(0.9731)

    def test_verificacoes(self, r):
        assert itens_com_status(r, NA) == {4, 5, 6, 16}
        assert de.texto_da_contagem(r.contagem) == "31 OK · 0 NÃO OK · 2 ALERTA · 4 N/A"


class TestCaso3DesnivelForaDoCatalogo:
    """H = 2000: não há n com 175 ≤ h ≤ 180; o degrau passa de 300 mm."""

    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(H_mm=2000.0)

    def test_geometria(self, r):
        g = r.geometria
        assert g.faixa.nivel == 2
        assert g.n == 12
        assert g.h_mm == pytest.approx(166.667, abs=0.001)
        assert g.b_mm == pytest.approx(300.0)
        assert g.blondel_mm == pytest.approx(633.333, abs=0.001)
        assert g.alfa_graus == pytest.approx(29.055, abs=0.001)
        assert (g.C_mm, g.F_mm, g.r_mm) == (325.0, 135, 25.0)
        assert not g.C_na_serie

    def test_lances(self, r):
        assert r.lances.n_lances == 1 and r.lances.k == 12 and r.lances.n_degraus_grade == 11

    def test_modelo(self, r):
        a = r.adotado
        assert a.modelo.nome == "DS-A4-35/3"
        assert a.n_bb == 11
        assert a.peso_degrau_kg == aprox(9.454)
        assert a.u_max == aprox(0.973)

    def test_verificacoes(self, r):
        assert itens_com_status(r, NAO_OK) == {8}
        assert {9, 11, 31, 35} <= itens_com_status(r, ALERTA)
        assert de.texto_da_contagem(r.contagem) == "31 OK · 1 NÃO OK · 4 ALERTA · 1 N/A"
        assert "consulta técnica Anglo" in r.verificacoes[7].formula  # a saída para o item 8


class TestCaso4EspelhoFechado:
    """NR-12 item 12: com espelho, h de 200 a 250 mm — sem interseção com o Anglo."""

    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(espelho_fechado=True)

    def test_geometria(self, r):
        g = r.geometria
        assert g.faixa.nivel == 3
        assert g.n == 18
        assert g.h_mm == pytest.approx(200.0)
        assert g.b_mm == pytest.approx(230.0)
        assert g.alfa_graus == pytest.approx(41.009, abs=0.001)
        assert (g.C_mm, g.F_mm, g.r_mm) == (250.0, 110, 20.0)

    def test_lances(self, r):
        assert r.lances.n_lances == 2 and r.lances.k == 9 and r.lances.n_degraus_grade == 16

    def test_verificacoes(self, r):
        assert {2, 11, 31, 35} == itens_com_status(r, ALERTA)
        assert itens_com_status(r, NAO_OK) == set()
        assert de.texto_da_contagem(r.contagem) == "31 OK · 0 NÃO OK · 4 ALERTA · 2 N/A"
        # Derivado das regras 4 e 6 (só valem com NR-12 sem espelho); a 5 vale no espelho fechado.
        assert itens_com_status(r, NA) == {4, 6}

    def test_o_conflito_com_o_anglo_vem_com_a_orientacao(self, r):
        assert "PRO.BRA.DPR.017" in r.verificacoes[1].formula
        assert de.MENSAGENS_NIVEL[3] in r.avisos


class TestCaso5LarguraEPermanencia:
    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(L_mm=1200.0, uso=de.USO_PERMANENTE)

    def test_largura_anglo(self, r):
        assert r.larguras.minima_anglo_mm == 1100

    def test_modelo_e_resistencia(self, r):
        a = r.adotado
        assert a.modelo.nome == "DS-A4-35/5"
        assert a.MRd_kNm == aprox(0.3247)
        assert a.peso_grade_kg_m2 == aprox(46.420)
        assert a.peso_degrau_kg == aprox(20.053)
        assert a.u_flex_c == aprox(0.8777)
        assert a.delta_iso_mm == aprox(3.969)
        assert a.u_fl_i == aprox(0.9922)  # governa
        assert a.u_max == a.u_fl_i

    def test_verificacoes(self, r):
        assert de.texto_da_contagem(r.contagem) == "35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A"
        assert "NBR 9077" in r.verificacoes[14].formula


class TestCaso6Manual:
    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(
            selecao=de.SELECAO_MANUAL,
            modelo_manual="DS-A4-25/3",
            L_mm=700.0,
            parafuso='1/2"',
            superficie=de.SUPERFICIE_LISA,
        )

    def test_aproveitamentos(self, r):
        a = r.adotado
        assert a.modelo.nome == "DS-A4-25/3"
        assert a.u_flex_c == aprox(1.6233)
        assert a.u_fl_i == aprox(1.470)
        assert a.delta_iso_mm == aprox(3.43)
        assert a.limite_iso_mm == aprox(2.33)

    def test_parafuso(self, r):
        assert r.reacoes.F_vRd_kN == aprox(15.577)

    def test_verificacoes(self, r):
        assert itens_com_status(r, NAO_OK) == {15, 22, 25, 30}
        assert itens_com_status(r, ALERTA) == {27, 35}
        assert de.texto_da_contagem(r.contagem) == "31 OK · 4 NÃO OK · 2 ALERTA · 0 N/A"
        assert r.status == NAO_OK

    def test_o_furo_padrao_do_parafuso_de_meia_polegada_cabe_no_catalogo(self, r):
        assert "padrão" in r.especificacao and '9/16"' in r.especificacao


class TestCaso7Inox:
    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(
            material="AISI 304",
            acabamento=de.ACABAMENTO_PASSIVADO,
            malha_preferida=de.QUALQUER,
            ligacao_preferida=de.QUALQUER,
        )

    def test_modelo(self, r):
        a = r.adotado
        assert a.modelo.nome == "DS-A4-40/3"
        assert a.MRd_kNm == aprox(0.2082)
        assert a.peso_grade_kg_m2 == aprox(34.880)
        assert a.peso_degrau_kg == aprox(10.045)
        assert a.u_flex_c == aprox(0.9066)

    def test_verificacoes(self, r):
        assert itens_com_status(r, ALERTA) == {29, 31, 35}
        assert de.texto_da_contagem(r.contagem) == "34 OK · 0 NÃO OK · 3 ALERTA · 0 N/A"


class TestCaso8DesnivelPequeno:
    """H = 1200, L = 550: um só lance curto; a largura mínima legal cai para 500 mm."""

    @pytest.fixture()
    def r(self) -> de.ResultadoEscada:
        return calcular(H_mm=1200.0, L_mm=550.0)

    def test_geometria(self, r):
        g = r.geometria
        assert g.faixa.nivel == 2
        assert g.n == 7
        assert g.h_mm == pytest.approx(171.429, abs=0.001)
        assert g.b_mm == pytest.approx(290.0)
        assert g.C_mm == pytest.approx(325.0)
        assert r.lances.n_lances == 1 and r.lances.k == 7 and r.lances.n_degraus_grade == 6

    def test_largura_minima_legal(self, r):
        assert r.larguras.minima_legal_mm == 500  # lance único com menos de 1,50 m

    def test_modelo(self, r):
        assert r.adotado.modelo.nome == "DS-A4-30/3"
        assert r.adotado.n_bb == 11
        assert r.adotado.u_flex_c == aprox(0.8968)

    def test_verificacoes(self, r):
        assert itens_com_status(r, NAO_OK) == {8, 15}
        assert itens_com_status(r, ALERTA) == {9, 31, 35}
        assert de.texto_da_contagem(r.contagem) == "31 OK · 2 NÃO OK · 3 ALERTA · 1 N/A"


# ---------------------------------------------------------------------------------------------
# Catálogo e fórmulas
# ---------------------------------------------------------------------------------------------
def test_catalogo_tem_64_modelos_unicos_na_ordem_da_regra():
    modelos = de.catalogo()
    assert len(modelos) == 64
    assert len({m.nome for m in modelos}) == 64
    assert modelos[0].nome == "DS-A4-25/3" and modelos[-1].nome == "DS-F2-40/5"
    assert [m.nome for m in modelos[:4]] == ["DS-A4-25/3", "DS-A4-25/5", "DS-A4-30/3", "DS-A4-30/5"]


@pytest.mark.parametrize(
    ("nome", "p", "s", "t_b", "h_chapa", "l_max"),
    [
        ("DS-A4-25/3", 30, 100, 3.00, 40, 700),
        ("DS-B2-30/5", 25, 50, 4.76, 45, 1100),
        ("DS-C4-35/3", 35, 100, 3.00, 50, 800),
        ("DS-F2-40/5", 41, 50, 4.76, 55, 1200),
        ("DS-A2-40/5", 30, 50, 4.76, 55, 1500),
    ],
)
def test_modelo_do_catalogo_tem_o_passo_a_espessura_a_chapa_lateral_e_o_l_maximo(
    nome, p, s, t_b, h_chapa, l_max
):
    m = de.obter_modelo(nome)
    assert (m.p_mm, m.s_mm, m.t_b_mm, m.h_chapa_mm, m.L_max_mm) == (p, s, t_b, h_chapa, l_max)


def test_l_maximo_vale_igual_para_barras_de_ligacao_tipo_4_e_tipo_2():
    for m in de.catalogo():
        outro = "2" if m.k == "4" else "4"
        irmao = de.obter_modelo(f"DS-{m.tipo}{outro}-{m.h_b_mm}/{m.tt}")
        assert irmao.L_max_mm == m.L_max_mm


def test_modelo_inexistente_e_erro_claro():
    with pytest.raises(de.EntradaInvalida, match="DS-Z9-99/9"):
        de.obter_modelo("DS-Z9-99/9")


def test_flt_nos_tres_regimes_da_tabela_g1():
    e = de.EntradaDegrau()
    # barra alta e fina com travamento frequente → plástica; sem travamento → elástica.
    plastica = de.calcular_modelo(de.obter_modelo("DS-B4-25/5"), 300.0, replace(e, Cb=1.0))
    assert plastica.lam_p < plastica.lam <= plastica.lam_r
    assert "inelástica" in plastica.regime_flt
    assert plastica.MRk_Nmm == pytest.approx(
        plastica.Mpl_Nmm
        - (plastica.Mpl_Nmm - plastica.Mr_Nmm)
        * (plastica.lam - plastica.lam_p)
        / (plastica.lam_r - plastica.lam_p)
    )
    elastica = de.calcular_modelo(de.obter_modelo("DS-A4-40/3"), 300.0, e)
    assert elastica.lam < elastica.lam_r  # estas barras de ligação a cada 100 mm nunca chegam a λr
    # Força os dois extremos trocando o material e o travamento via modelo sintético.
    curto = replace(de.obter_modelo("DS-A4-40/3"), s_mm=10.0)
    assert de.calcular_modelo(curto, 300.0, e).regime_flt.startswith("plástica")
    longo = replace(de.obter_modelo("DS-A4-25/3"), s_mm=2000.0)
    r_longo = de.calcular_modelo(longo, 300.0, e)
    assert r_longo.regime_flt.startswith("elástica")
    assert r_longo.MRk_Nmm == pytest.approx(min(r_longo.Mpl_Nmm, r_longo.Mcr_Nmm))


def test_momento_resistente_nunca_passa_do_plastico():
    e = de.EntradaDegrau(Cb=1.67)
    for r in de.avaliar_catalogo(300.0, e):
        assert r.MRk_Nmm <= r.Mpl_Nmm + 1e-6


def test_n_ef_imposto_limita_as_barras_sob_a_carga_concentrada():
    base = calcular()
    menos = calcular(n_ef_imposto=2)
    assert menos.adotado.n_ef == 2 or menos.selecao.adotado.n_ef == 2
    mesmo_modelo = next(
        r for r in menos.tabela_modelos if r.modelo.nome == base.adotado.modelo.nome
    )
    assert mesmo_modelo.n_ef == 2 and mesmo_modelo.u_flex_c > base.adotado.u_flex_c


def test_n_ef_nunca_passa_do_numero_de_barras_da_profundidade():
    r = calcular(n_ef_imposto=99)
    assert all(x.n_ef <= x.n_bb for x in r.tabela_modelos)


def test_cb_maior_aumenta_a_resistencia_na_faixa_inelastica():
    a = de.calcular_modelo(de.obter_modelo("DS-A4-35/3"), 300.0, de.EntradaDegrau(Cb=1.0))
    b = de.calcular_modelo(de.obter_modelo("DS-A4-35/3"), 300.0, de.EntradaDegrau(Cb=1.2))
    assert b.MRd_kNm > a.MRd_kNm


def test_reacao_usa_a_maior_das_duas_combinacoes():
    r = calcular()
    rp = r.reacoes
    com_q = 1.25 * rp.R_g_kN + 1.5 * rp.R_q_kN
    com_p = 1.25 * rp.R_g_kN + 1.5 * rp.R_P_kN
    assert rp.R_d_kN == pytest.approx(max(com_q, com_p))
    assert com_p > com_q  # a carga concentrada governa a reação


def test_parafuso_de_cinco_oitavos_tem_a_area_e_a_resistencia_certas():
    rp = calcular().reacoes
    assert rp.A_b_mm2 == pytest.approx(math.pi * 15.875**2 / 4)
    assert rp.F_vRd_kN == pytest.approx(0.40 * rp.A_b_mm2 * 415 / 1.35 / 1000)


# ---------------------------------------------------------------------------------------------
# Espelho, piso, profundidade e lances
# ---------------------------------------------------------------------------------------------
def test_h_catalogo_minimo_e_175():
    assert de.faixa_espelho(3600, 175, de.NR12, False).hCat_min == 175


@pytest.mark.parametrize(
    ("enquadramento", "fechado", "esperado"),
    [
        (de.NR22, False, (180.0, 200.0)),
        (de.NR22, True, (180.0, 200.0)),  # NR-22 prevalece sobre o espelho fechado
        (de.NR12, True, (200.0, 250.0)),
        (de.NR12, False, (0.0, 250.0)),
    ],
)
def test_faixa_legal_do_espelho(enquadramento, fechado, esperado):
    assert de.faixa_legal_espelho(enquadramento, fechado) == esperado


def test_nivel_4_quando_nenhuma_faixa_e_atendida():
    # NR-22 (h de 180 a 200): 250 mm não cabe em 1 espelho (250 > 200) nem em 2 (125 < 180).
    f = de.faixa_espelho(250.0, 175.0, de.NR22, False)
    assert f.nivel == 4 and f.n_lo == f.n_hi == f.n_auto == 2
    assert f.mensagem == de.MENSAGENS_NIVEL[4]


def test_nivel_3_usa_o_minimo_legal_como_alvo_quando_ele_passa_de_180():
    f = de.faixa_espelho(3600, 175, de.NR12, True)
    assert f.nivel == 3 and f.h_alvo_ef == 200 and f.n_auto == 18


def test_nivel_3_sem_minimo_legal_continua_no_alvo_do_usuario():
    # NR-12 sem espelho e desnível que nenhum nível 1 ou 2 atende: o limite superior de n é infinito.
    f = de.faixa_espelho(90.0, 175.0, de.NR12, False)
    assert f.nivel == 3 and math.isinf(f.n_hi)
    assert f.n_auto == 1  # arredonda 90/175 e respeita n ≥ 1


def test_n_imposto_prevalece_sobre_o_automatico():
    r = calcular(n_imposto=21)
    assert r.geometria.n == 21
    assert r.geometria.h_mm == pytest.approx(3600 / 21)
    assert r.geometria.faixa.n_auto == 20  # o automático continua registrado


def test_lances_com_numero_diferente_de_espelhos_viram_alerta_no_item_13():
    r = calcular(n_imposto=21)
    assert r.lances.n_lances == 2 and (r.lances.k, r.lances.k_min) == (11, 10)
    assert r.lances.texto == "1 lance(s) de 11 + 1 lance(s) de 10 espelhos"
    assert r.verificacoes[12].status == ALERTA
    assert r.lances.n_degraus_grade == 19


def test_altura_maxima_por_lance_imposta_divide_em_mais_lances():
    r = calcular(altura_max_lance_imposta_mm=1200.0)
    assert r.lances.k_max == 6 and r.lances.n_lances == 4 and r.lances.k == 5
    assert r.lances.n_patamares == 3
    assert r.lances.projecao_total_mm == pytest.approx(16 * 270 + 3 * 900)
    assert r.verificacoes[11].status == OK  # item 12


def test_altura_imposta_acima_do_limite_legal_continua_reprovando_o_item_12():
    r = calcular(altura_max_lance_imposta_mm=4000.0)  # NR-12: 3000 mm por lance
    assert r.lances.n_lances == 1  # a meta imposta deixaria 1 lance de 20 espelhos (3600 mm)
    assert r.verificacoes[11].status == NAO_OK


def test_comprimento_inclinado_e_projecao_do_lance_maior():
    ln = calcular().lances
    assert ln.altura_lance_maior_mm == pytest.approx(1800.0)
    assert ln.projecao_lance_maior_mm == pytest.approx(9 * 270.0)
    assert ln.comprimento_inclinado_mm == pytest.approx(math.hypot(1800.0, 9 * 270.0))


def test_piso_automatico_e_o_menor_multiplo_de_cinco_da_faixa_combinada():
    assert de.piso_b(180.0, de.NR12, False, None) == 270.0
    assert de.piso_b(200.0, de.NR12, True, None) == 230.0
    assert de.piso_b(166.667, de.NR12, False, None) == 300.0


def test_piso_automatico_arredonda_para_cima_em_multiplo_de_cinco_dentro_da_faixa():
    # h = 180,3: Anglo pede b de 269,4 a 279,4 → o menor múltiplo de 5 é 270.
    assert de.piso_b(180.3, de.NR12, False, None) == 270.0
    # h = 177,3: Anglo b ∈ [275,4; 285,4] → 280.
    assert de.piso_b(177.3, de.NR12, False, None) == 280.0


def test_piso_imposto_nao_e_recalculado():
    assert de.piso_b(177.3, de.NR12, False, 281.0) == 281.0


def test_piso_com_requisito_legal_sem_intersecao_com_o_anglo_prevalece_a_norma():
    # NR-12 sem espelho com h = 250: g + 2h ≥ 600 → b ≥ 150 (g mínimo) e b ≤ 160; Anglo pede b ≤ 140.
    assert de.piso_b(250.0, de.NR12, False, None) == 150.0


def test_profundidade_padronizada_e_personalizada():
    assert de.profundidade_C(270.0, None, True) == 300.0
    assert de.profundidade_C(300.0, None, True) == 325.0
    assert de.profundidade_C(270.0, None, False) == 290.0  # múltiplo de 5 de b + 20
    assert de.profundidade_C(270.0, 310.0, True) == 310.0  # imposta
    assert de.profundidade_C(100.0, None, True) == 175.0  # nunca abaixo do catálogo


@pytest.mark.parametrize(
    ("C", "F"),
    [(175, 85), (200, 85), (225, 110), (250, 110), (275, 135), (300, 135), (325, 135), (290, 135)],
)
def test_furacao_pela_serie_do_catalogo(C, F):
    assert de.furacao_F(C) == F


def test_c_fora_da_serie_e_detectado():
    assert de.c_na_serie(250.0) and de.c_na_serie(300.0)
    assert not de.c_na_serie(290.0) and not de.c_na_serie(325.0)


def test_c_fora_da_serie_vira_alerta_no_item_9():
    r = calcular(C_padronizado=False)
    assert r.geometria.C_mm == 290.0 and not r.geometria.C_na_serie
    assert r.verificacoes[8].status == ALERTA


def test_c_imposto_menor_que_b_mais_20_reprova_o_item_7_e_menor_que_b_e_erro():
    r = calcular(C_imposto_mm=280.0)  # b = 270: C ≥ b + 20 não vale
    assert r.verificacoes[6].status == NAO_OK
    with pytest.raises(de.EntradaInvalida, match="maior que o piso b"):
        calcular(C_imposto_mm=270.0)


# ---------------------------------------------------------------------------------------------
# Larguras
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("enquadramento", "n_lances", "H", "uso", "legal", "anglo"),
    [
        (de.NR22, 1, 1200.0, de.USO_GERAL, 600, 800),
        (de.NR12, 1, 1200.0, de.USO_GERAL, 500, 800),
        (de.NR12, 1, 1500.0, de.USO_GERAL, 600, 800),
        (de.NR12, 2, 1200.0, de.USO_GERAL, 600, 800),
        (de.NR12, 2, 3600.0, de.USO_PERMANENTE, 600, 1100),
        (de.NR12, 2, 3700.0, de.USO_CABINE, 600, 800),
        (de.NR12, 2, 3800.0, de.USO_CABINE, 600, 1100),
    ],
)
def test_larguras_minimas(enquadramento, n_lances, H, uso, legal, anglo):
    lg = de.larguras(800.0, 0.0, enquadramento, n_lances, H, uso)
    assert (lg.minima_legal_mm, lg.minima_anglo_mm) == (legal, anglo)


def test_reducao_da_largura_util_vale_para_os_itens_14_e_15():
    r = calcular(reducao_largura_mm=250.0)  # 800 − 250 = 550
    assert r.larguras.util_mm == 550
    assert r.verificacoes[13].status == NAO_OK  # < 600 legal
    assert r.verificacoes[14].status == NAO_OK  # < 800 Anglo


# ---------------------------------------------------------------------------------------------
# Seleção do modelo
# ---------------------------------------------------------------------------------------------
def test_sem_modelo_na_preferencia_adota_o_mais_leve_do_catalogo_com_aviso():
    # Malha B + ligação 2 não atende no caso padrão; o mais leve que atende sai de outra família.
    r = calcular(malha_preferida="F", ligacao_preferida="4")
    assert r.selecao.situacao in (de.SELECIONADO_PREFERENCIA, de.SELECIONADO_FORA_DA_PREFERENCIA)
    r2 = calcular(L_mm=1500.0, malha_preferida="C", ligacao_preferida="2")
    assert r2.selecao.situacao == de.SELECIONADO_FORA_DA_PREFERENCIA
    assert r2.adotado.atende and not r2.adotado.na_preferencia
    assert any("Nenhum modelo da preferência" in a for a in r2.avisos)


def test_nenhum_modelo_atende_adota_o_de_menor_aproveitamento_maximo():
    r = calcular(P_kN=12.0)  # carga concentrada absurda para qualquer barra
    assert r.selecao.situacao == de.SELECIONADO_NENHUM
    assert r.adotado.u_max == min(x.u_max for x in r.tabela_modelos)
    assert not r.adotado.atende
    assert any("NENHUM modelo" in a for a in r.avisos)
    assert r.status == NAO_OK


def test_adotado_e_o_mais_leve_entre_os_que_atendem_e_estao_na_preferencia():
    r = calcular()
    candidatos = [x for x in r.tabela_modelos if x.atende and x.na_preferencia]
    assert r.adotado.peso_degrau_kg == min(x.peso_degrau_kg for x in candidatos)
    assert r.selecao.situacao == de.SELECIONADO_PREFERENCIA


def test_selecao_manual_nao_exige_que_o_modelo_atenda():
    r = calcular(selecao=de.SELECAO_MANUAL, modelo_manual="DS-F4-25/3")
    assert r.adotado.modelo.nome == "DS-F4-25/3"
    assert r.selecao.situacao == de.SELECIONADO_MANUAL
    assert r.verificacoes[18].status == NAO_OK  # L = 800 > L máx 500 do F 25/3


def test_atende_exige_o_comprimento_no_intervalo_do_catalogo():
    r = calcular(L_mm=450.0)
    assert not any(x.atende for x in r.tabela_modelos)  # L < 500: nenhum atende
    assert r.verificacoes[17].status == NAO_OK  # item 18


def test_desempate_pela_ordem_do_catalogo():
    r = calcular(malha_preferida=de.QUALQUER, ligacao_preferida=de.QUALQUER)
    pesos = [x.peso_degrau_kg for x in r.tabela_modelos if x.atende]
    assert r.adotado.peso_degrau_kg == min(pesos)


# ---------------------------------------------------------------------------------------------
# Verificações e texto para a requisição
# ---------------------------------------------------------------------------------------------
def test_toda_verificacao_traz_a_referencia_da_norma():
    r = calcular()
    assert len(r.verificacoes) == 38
    assert all(v.referencia.strip() for v in r.verificacoes)
    assert [v.nome.split(".")[0] for v in r.verificacoes] == [str(i) for i in range(1, 39)]


def test_verificacoes_de_resistencia_entram_no_aproveitamento_maximo():
    r = calcular()
    resistencia = [v for v in r.verificacoes if v.tipo == "resistencia"]
    assert len(resistencia) == 6  # itens 21 a 25 e 33
    assert r.aproveitamento_maximo == pytest.approx(r.adotado.u_max)
    assert all(
        v.tipo == "limite" for v in r.verificacoes if v.tipo != "resistencia" and v.status != INFO
    )


def test_so_o_item_17_e_informativo():
    r = calcular()
    assert itens_com_status(r, INFO) == {17}
    assert r.verificacoes[16].nome.startswith("17. Modelo adotado: DS-A4-35/3")


def test_controle_interno_confere_o_adotado_com_a_tabela():
    r = calcular()
    assert r.verificacoes[25].status == OK
    assert r.verificacoes[25].aproveitamento is None


@pytest.mark.parametrize(
    ("alteracao", "item", "esperado"),
    [
        ({"superficie": de.SUPERFICIE_SERRILHADA}, 27, OK),
        ({"superficie": de.SUPERFICIE_LISA}, 27, ALERTA),
        ({"acabamento": de.ACABAMENTO_NATURAL}, 28, NAO_OK),
        ({"acabamento": de.ACABAMENTO_GALVANIZADO}, 28, OK),
        ({"material": "AISI 316", "acabamento": de.ACABAMENTO_GALVANIZADO}, 28, ALERTA),
        ({"material": "AISI 316", "acabamento": de.ACABAMENTO_PASSIVADO}, 28, OK),
        ({"acabamento": de.ACABAMENTO_PASSIVADO}, 28, NAO_OK),  # passivado em A36
        ({"material": "AISI 304L"}, 29, ALERTA),
        ({"parafuso": '1/2"'}, 30, NAO_OK),
        ({"parafuso": '1/2"'}, 31, OK),
        ({"n_parafusos_por_lado": 1}, 32, NAO_OK),
        ({"gc_superior_mm": 1300.0}, 34, NAO_OK),  # a NR limita a 1200 mm
        ({"gc_superior_mm": 1300.0}, 35, OK),
        ({"gc_superior_mm": 1100.0}, 34, OK),
        ({"gc_intermediario_mm": 650.0}, 36, NAO_OK),
        ({"gc_intermediario_mm": 700.4}, 36, OK),
        ({"gc_rodape_mm": 150.0}, 37, NAO_OK),
        ({"gc_espacamento_mm": 160.0}, 38, NAO_OK),
        ({"L_mm": 1600.0}, 18, NAO_OK),
        ({"patamar_mm": 500.0}, 16, NAO_OK),
    ],
)
def test_status_de_cada_verificacao_por_entrada(alteracao, item, esperado):
    assert calcular(**alteracao).verificacoes[item - 1].status == esperado


def test_tolerancia_de_um_centesimo_de_milimetro_nas_faixas():
    # Largura útil 799,995 mm contra o mínimo de 800: dentro da tolerância de 0,01 mm.
    r = calcular(L_mm=800.0, reducao_largura_mm=0.005)
    assert r.verificacoes[14].status == OK


def test_inclinacao_nr22_tem_faixa_diferente_da_nr12():
    # α = atan(h/b); NR-22 aceita até 50°, a NR-12 até 45°.
    nr12 = calcular(b_imposto_mm=170.0, C_imposto_mm=300.0)  # α ≈ 46,7°
    nr22 = calcular(b_imposto_mm=170.0, C_imposto_mm=300.0, enquadramento=de.NR22)
    assert nr12.geometria.alfa_graus == pytest.approx(math.degrees(math.atan(180 / 170)))
    assert nr12.verificacoes[9].status == NAO_OK
    assert nr22.verificacoes[9].status == OK


def test_espelho_fora_da_faixa_anglo_so_alerta_no_nivel_3():
    nivel3 = calcular(espelho_fechado=True)
    assert nivel3.verificacoes[1].status == ALERTA
    imposto = calcular(n_imposto=15)  # h = 240 mm no nível 1: fora do Anglo, sem conflito de faixa
    assert imposto.geometria.faixa.nivel == 1
    assert imposto.verificacoes[1].status == NAO_OK


def test_especificacao_com_parafuso_de_meia_polegada_usa_o_furo_padrao():
    r = calcular(parafuso='1/2"')
    assert 'furos oblongos 9/16" x 25 mm (padrão) a F = 135 mm' in r.especificacao
    r2 = calcular()
    assert (
        'furos oblongos 11/16" x 25 mm (especial, p/ parafuso 5/8") a F = 135 mm'
        in r2.especificacao
    )


def test_especificacao_do_caso_1_e_exatamente_a_do_modelo_da_especificacao():
    assert calcular().especificacao == (
        "Degrau Selmec DS-A4-35/3 – malha 30 x 100 mm – barra portante 35 x 3,00 mm – C = 300 mm "
        "× L = 800 mm – ASTM A36 – Galvanizado a fogo – superfície serrilhada – chapa xadrez no "
        'bocel – furos oblongos 11/16" x 25 mm (especial, p/ parafuso 5/8") a F = 135 mm – '
        "qtd. 18"
    )


def test_especificacao_sem_xadrez_e_com_barra_de_4_76():
    r = calcular(L_mm=1200.0, chapa_xadrez=False)
    assert "barra portante 35 x 4,76 mm" in r.especificacao
    assert "sem chapa xadrez no bocel" in r.especificacao


def test_peso_total_e_quantidade_vezes_peso_unitario():
    r = calcular()
    assert r.peso_unitario_kg == aprox(8.727)
    assert r.peso_total_kg == pytest.approx(18 * r.peso_unitario_kg)


# ---------------------------------------------------------------------------------------------
# Entradas impossíveis: erro claro, nada é corrigido em silêncio
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("alteracao", "trecho"),
    [
        ({"H_mm": 0.0}, "desnível"),
        ({"H_mm": -100.0}, "desnível"),
        ({"L_mm": 0.0}, "comprimento do degrau L"),
        ({"n_imposto": 0}, "nº de espelhos imposto"),
        ({"n_imposto": -3}, "nº de espelhos imposto"),
        ({"n_imposto": 20.5}, "nº de espelhos imposto"),
        ({"b_imposto_mm": 0.0}, "piso b imposto"),
        ({"b_imposto_mm": -5.0}, "piso b imposto"),
        ({"C_imposto_mm": 0.0}, "profundidade C imposta"),
        ({"h_alvo_mm": 0.0}, "espelho alvo"),
        ({"reducao_largura_mm": 900.0}, "redução da largura"),
        ({"reducao_largura_mm": -1.0}, "redução da largura"),
        ({"altura_max_lance_imposta_mm": 0.0}, "altura máxima por lance"),
        ({"selecao": de.SELECAO_MANUAL, "modelo_manual": "DS-X"}, "não existe no catálogo"),
        ({"material": "Latão"}, "Material desconhecido"),
        ({"parafuso": '3/4"'}, "Parafuso desconhecido"),
        ({"n_parafusos_por_lado": 0}, "parafusos por lado"),
        ({"q_kN_m2": 0.0}, "q precisa"),
        ({"gamma_a1": 0.0}, "γa1"),
        ({"Cb": -1.0}, "Cb"),
        ({"n_ef_imposto": 0}, "n_ef"),
        ({"enquadramento": "NR-99"}, "Enquadramento"),
    ],
)
def test_entrada_impossivel_levanta_erro_claro(alteracao, trecho):
    with pytest.raises(de.EntradaInvalida, match=trecho):
        calcular(**alteracao)


def test_altura_maxima_por_lance_menor_que_um_espelho_e_erro():
    with pytest.raises(de.EntradaInvalida, match="menor que um espelho"):
        calcular(altura_max_lance_imposta_mm=100.0)


def test_piso_nao_positivo_e_erro():
    # NR-12 sem espelho com h enorme (n = 1, h = 3600): 660 − 2h < 0, o piso sairia negativo.
    with pytest.raises(de.EntradaInvalida, match="piso b"):
        calcular(n_imposto=1)


def test_validar_entrada_lista_todos_os_erros_de_uma_vez():
    erros = de.validar_entrada(de.EntradaDegrau(H_mm=0.0, L_mm=0.0, n_imposto=0))
    assert len(erros) == 3


def test_erro_de_entrada_nao_deixa_resultado_parcial():
    with pytest.raises(de.EntradaInvalida):
        calcular(H_mm=0.0)


def test_entrada_valida_nao_tem_erros():
    assert de.validar_entrada(de.EntradaDegrau()) == []


# ---------------------------------------------------------------------------------------------
# Invariantes
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("H", [900.0, 1500.0, 2400.0, 3000.0, 3600.0, 4800.0, 6000.0, 7200.0])
@pytest.mark.parametrize("enquadramento", [de.NR12, de.NR22])
def test_geometria_fecha_com_o_desnivel_em_qualquer_altura(H, enquadramento):
    r = calcular(H_mm=H, enquadramento=enquadramento)
    g, ln = r.geometria, r.lances
    assert g.n * g.h_mm == pytest.approx(H)  # n espelhos de altura h cobrem o desnível
    assert ln.n_degraus_grade == g.n - ln.n_lances
    assert ln.altura_lance_maior_mm <= ln.altura_max_lance_mm + de.TOL_MM
    assert g.C_mm > g.b_mm
    assert len(r.verificacoes) == 38
    assert len({x.modelo.nome for x in r.tabela_modelos}) == 64
    contagem = r.contagem
    assert sum(contagem.values()) == 38 and contagem[INFO] == 1


def test_u_max_e_o_maior_dos_cinco_aproveitamentos():
    for r in calcular().tabela_modelos:
        assert r.u_max == max(r.usos.values())


def test_peso_cresce_com_a_barra_e_com_a_espessura():
    por_nome = {r.modelo.nome: r for r in calcular().tabela_modelos}
    assert por_nome["DS-A4-40/3"].peso_degrau_kg > por_nome["DS-A4-35/3"].peso_degrau_kg
    assert por_nome["DS-A4-35/5"].peso_degrau_kg > por_nome["DS-A4-35/3"].peso_degrau_kg


def test_resultado_nao_depende_da_ordem_de_chamada():
    assert calcular().adotado.u_max == calcular().adotado.u_max
    assert calcular().especificacao == calcular().especificacao
