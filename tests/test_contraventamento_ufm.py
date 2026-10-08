"""Método das Forças Uniformes: os números dos Exemplos 5.1 a 5.4 do AISC Design Guide 29.

Os exemplos do guia estão em kips e polegadas; aqui convertidos para kN e mm. Os valores esperados
são os que o guia imprime (arredondados em 3 algarismos), por isso a tolerância é de 0,5 %.
"""

from __future__ import annotations

import math

import pytest

from core import contraventamento_ufm as ufm

KIP = 4.448222  # kN
POL = 25.4  # mm
KIP_POL = KIP * POL / 1000.0  # kip·in em kN·m


def kips(valor_kN: float) -> float:
    return valor_kN / KIP


def kip_pol(valor_kNmm: float) -> float:
    return valor_kNmm / 1000.0 / KIP_POL


def aprox(valor: float, rel: float = 0.005) -> object:
    return pytest.approx(valor, rel=rel)


THETA_EX1 = math.degrees(math.atan(1.08))  # o guia: "tanθ = 1,08" (θ = 47,2°)


def entrada_exemplo_5_1(**alteracoes) -> ufm.EntradaUFM:
    base = dict(
        P_kN=840.0 * KIP,
        theta_graus=THETA_EX1,
        eb_mm=10.7 * POL,
        ec_mm=7.00 * POL,
        alfa_real_mm=17.5 * POL,
        beta_real_mm=12.0 * POL,
        reacao_viga_kN=50.0 * KIP,
        transferencia_kN=100.0 * KIP,
    )
    base.update(alteracoes)
    return ufm.EntradaUFM(**base)


class TestExemplo51CasoGeral:
    """Corner connection-to-column flange, general UFM (guia, p. 52 a 54)."""

    def test_alfa_ideal_pela_equacao_4_1(self):
        # β = 12 in → α = (10,7 + 12,0)·1,08 − 7,00 = 17,5 in
        alfa = ufm.alfa_ideal(12.0 * POL, 10.7 * POL, 7.0 * POL, THETA_EX1)
        assert alfa / POL == aprox(17.5, 0.002)

    def test_beta_ideal_e_o_inverso(self):
        alfa = ufm.alfa_ideal(12.0 * POL, 10.7 * POL, 7.0 * POL, THETA_EX1)
        assert ufm.beta_ideal(alfa, 10.7 * POL, 7.0 * POL, THETA_EX1) == pytest.approx(12.0 * POL)

    def test_forcas_nas_interfaces(self):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1())
        assert r.r_mm / POL == aprox(33.4, 0.002)
        assert kips(r.Vc_kN) == aprox(302.0)
        assert kips(r.Vb_kN) == aprox(269.0)
        assert kips(r.Hc_kN) == aprox(176.0)
        assert kips(r.Hb_kN) == aprox(440.0)

    def test_as_forcas_equilibram_o_contraventamento(self):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1())
        horizontal, vertical = r.componentes_horizontal_vertical
        assert r.Hb_kN + r.Hc_kN == pytest.approx(horizontal, rel=1e-3)
        assert r.Vb_kN + r.Vc_kN == pytest.approx(vertical, rel=1e-3)
        assert kips(horizontal) == aprox(616.0)
        assert kips(vertical) == aprox(571.0)

    def test_sem_binario_quando_a_geometria_e_a_ideal(self):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1())
        assert abs(kip_pol(r.viga_momento_kNmm)) < 5.0  # ~0: α real do guia é 17,5 (ideal 17,516)
        assert abs(kip_pol(r.coluna_momento_kNmm)) < 1e-6

    def test_ligacao_viga_coluna_leva_a_vertical_mais_a_reacao_e_a_normal_mais_a_transferencia(
        self,
    ):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1())
        assert kips(r.vc_cisalhamento_kN) == aprox(319.0)  # V_ub + 50
        assert kips(r.vc_axial_kN) == aprox(276.0)  # H_uc + 100 (antes de descontar a distorção)

    def test_interfaces_do_exemplo(self):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1())
        assert kips(r.viga_cisalhamento_kN) == aprox(440.0)
        assert kips(r.viga_normal_kN) == aprox(269.0)
        assert kips(r.coluna_cisalhamento_kN) == aprox(302.0)
        assert kips(r.coluna_normal_kN) == aprox(176.0)

    def test_alfa_real_diferente_gera_binario_na_viga_eq_4_2(self):
        r = ufm.distribuir_forcas(entrada_exemplo_5_1(alfa_real_mm=19.5 * POL))
        esperado = r.Vb_kN * (19.5 * POL - r.alfa_ideal_mm)
        assert r.viga_momento_kNmm == pytest.approx(esperado)
        assert r.viga_momento_kNmm > 0
        assert any("binário" in a for a in r.avisos)

    def test_ajuste_por_alfa_calcula_beta_e_gera_binario_na_coluna_eq_4_3(self):
        r = ufm.distribuir_forcas(
            entrada_exemplo_5_1(
                ajuste=ufm.AJUSTE_ALFA, alfa_real_mm=17.5 * POL, beta_real_mm=14.0 * POL
            )
        )
        assert r.alfa_ideal_mm == pytest.approx(17.5 * POL)
        assert r.beta_ideal_mm / POL == aprox(12.0, 0.004)
        assert r.coluna_momento_kNmm == pytest.approx(r.Hc_kN * (14.0 * POL - r.beta_ideal_mm))

    def test_minimizar_excentricidades_cumpre_a_equacao_4_1(self):
        e = entrada_exemplo_5_1(
            ajuste=ufm.AJUSTE_MINIMIZAR, alfa_real_mm=20.0 * POL, beta_real_mm=11.0 * POL
        )
        r = ufm.distribuir_forcas(e)
        t = math.tan(math.radians(e.theta_graus))
        assert r.alfa_ideal_mm - r.beta_ideal_mm * t == pytest.approx(e.eb_mm * t - e.ec_mm)
        # nenhum dos dois ficou mais longe do real do que o outro modo de ajuste deixaria
        a_beta = ufm.alfa_ideal(e.beta_real_mm, e.eb_mm, e.ec_mm, e.theta_graus)
        assert abs(r.alfa_ideal_mm - e.alfa_real_mm) <= abs(a_beta - e.alfa_real_mm) + 1e-6


class TestExemplo52CasoEspecial1:
    """Ponto de trabalho no canto da chapa (Eqs. 4-5 a 4-8, guia p. 78 a 82)."""

    @pytest.fixture()
    def r(self):
        return ufm.distribuir_forcas(
            entrada_exemplo_5_1(
                caso=ufm.CASO_1, Zviga_mm3=196.0 * POL**3, Zcoluna_mm3=157.0 * POL**3
            )
        )

    def test_excentricidade_e_momento(self, r):
        assert r.excentricidade_mm / POL == aprox(3.09, 0.003)
        assert kip_pol(r.M_excentrico_kNmm) == aprox(2600.0, 0.003)

    def test_eta_pelos_modulos_plasticos(self, r):
        assert r.eta == aprox(0.384, 0.002)

    def test_forcas_extras_h_linha_e_v_linha(self, r):
        assert kips(r.H_linha_kN) == aprox(70.6, 0.005)
        assert kips(r.V_linha_kN) == aprox(100.0, 0.01)

    def test_forcas_somadas_da_figura_5_5c(self, r):
        assert kips(r.coluna_normal_kN) == aprox(247.0, 0.005)
        assert kips(r.coluna_cisalhamento_kN) == aprox(402.0, 0.005)
        assert kips(r.viga_cisalhamento_kN) == aprox(369.0, 0.005)
        assert kips(r.viga_normal_kN) == aprox(169.0, 0.01)

    def test_momentos_extras_na_viga_e_na_coluna(self, r):
        assert kip_pol(r.momento_extra_viga_kNmm) == aprox(998.0, 0.005)
        assert kip_pol(r.momento_extra_coluna_kNmm) == aprox(801.0, 0.005)

    def test_ligacao_viga_coluna(self, r):
        assert kips(r.vc_cisalhamento_kN) == aprox(219.0, 0.01)  # 169 + 50
        assert kips(r.vc_axial_kN) == aprox(347.0, 0.005)  # 247 + 100

    def test_sem_excentricidade_volta_ao_caso_geral(self):
        geral = ufm.distribuir_forcas(entrada_exemplo_5_1())
        # ponto de trabalho no cruzamento dos eixos: x = e_c e y = e_b → e = 0
        r = ufm.distribuir_forcas(
            entrada_exemplo_5_1(
                caso=ufm.CASO_1,
                x_mm=7.0 * POL,
                y_mm=10.7 * POL,
                Zviga_mm3=196.0 * POL**3,
                Zcoluna_mm3=157.0 * POL**3,
            )
        )
        assert abs(r.excentricidade_mm) < 1e-9
        assert r.viga_cisalhamento_kN == pytest.approx(geral.viga_cisalhamento_kN)
        assert r.coluna_cisalhamento_kN == pytest.approx(geral.coluna_cisalhamento_kN)

    def test_exige_os_modulos_plasticos(self):
        with pytest.raises(ufm.UFMInvalido, match="módulos plásticos"):
            ufm.distribuir_forcas(entrada_exemplo_5_1(caso=ufm.CASO_1))


class TestExemplo53CasoEspecial2:
    """ΔV_b = 102 kips tirados da ligação viga–coluna (guia, Tabela 5-1a)."""

    @pytest.fixture()
    def r(self):
        return ufm.distribuir_forcas(
            entrada_exemplo_5_1(caso=ufm.CASO_2, delta_Vb_kN=102.0 * KIP, alfa_real_mm=17.5 * POL)
        )

    def test_tabela_5_1a(self, r):
        assert kips(r.viga_cisalhamento_kN) == aprox(440.0)
        assert kips(r.viga_normal_kN) == aprox(167.0, 0.01)
        assert kips(r.coluna_cisalhamento_kN) == aprox(404.0)
        assert kips(r.coluna_normal_kN) == aprox(176.0)
        assert kips(r.vc_cisalhamento_kN) == aprox(217.0, 0.01)

    def test_binario_na_viga_vale_delta_vb_vezes_alfa(self, r):
        assert kip_pol(r.viga_momento_kNmm) == aprox(1790.0, 0.01)

    def test_anular_toda_a_vertical_da_viga_eq_4_11(self):
        r = ufm.distribuir_forcas(
            entrada_exemplo_5_1(caso=ufm.CASO_2, anular_Vb=True, alfa_real_mm=17.5 * POL)
        )
        assert r.viga_normal_kN == pytest.approx(0.0, abs=1e-9)
        assert r.vc_cisalhamento_kN == pytest.approx(50.0 * KIP)  # só a reação da viga
        # Eq. 4-11: M_b = V_b·α = H_b·e_b (a restrição α − β tanθ = e_b tanθ − e_c faz as duas iguais)
        assert r.viga_momento_kNmm == pytest.approx(r.Hb_kN * r.entrada.eb_mm, rel=0.01)

    def test_delta_maior_que_a_vertical_e_erro(self):
        with pytest.raises(ufm.UFMInvalido, match="ΔV_b"):
            ufm.distribuir_forcas(entrada_exemplo_5_1(caso=ufm.CASO_2, delta_Vb_kN=400.0 * KIP))


class TestExemplo54CasoEspecial3:
    """Chapa ligada só à viga (guia, p. 98 a 106): P = 100 kips, tanθ = 12/7."""

    @pytest.fixture()
    def r(self):
        return ufm.distribuir_forcas(
            ufm.EntradaUFM(
                P_kN=100.0 * KIP,
                theta_graus=59.7,  # o guia arredonda θ = atan(12/7) para 59,7°
                eb_mm=8.85 * POL,
                ec_mm=6.10 * POL,
                alfa_real_mm=11.5 * POL,
                beta_real_mm=0.0,
                caso=ufm.CASO_3,
                reacao_viga_kN=30.0 * KIP,
            )
        )

    def test_alfa_ideal(self, r):
        assert r.alfa_ideal_mm / POL == aprox(9.07, 0.004)  # o guia usa tanθ = 12/7 exato
        assert r.beta_ideal_mm == 0.0

    def test_forcas_na_interface_chapa_viga(self, r):
        assert kips(r.viga_cisalhamento_kN) == aprox(86.3, 0.002)
        assert kips(r.viga_normal_kN) == aprox(50.5, 0.002)
        assert kip_pol(r.viga_momento_kNmm) == aprox(123.0, 0.01)

    def test_ligacao_viga_coluna_com_momento_v_ec(self, r):
        assert kip_pol(r.vc_momento_kNmm) == aprox(308.0, 0.005)
        assert kips(r.vc_cisalhamento_kN) == aprox(80.5, 0.005)

    def test_nao_ha_forca_na_coluna(self, r):
        assert (r.coluna_cisalhamento_kN, r.coluna_normal_kN) == (0.0, 0.0)

    def test_avisa_quando_o_contraventamento_nao_e_deitado(self):
        r = ufm.distribuir_forcas(
            ufm.EntradaUFM(
                P_kN=100.0,
                theta_graus=50.0,
                eb_mm=300.0,
                ec_mm=100.0,
                alfa_real_mm=300.0,
                beta_real_mm=0.0,
                caso=ufm.CASO_3,
            )  # fmt: skip
        )
        assert any("deitado" in a for a in r.avisos)


class TestDistorcaoDoPortico:
    """Eqs. 4-12 e 4-14 do guia (Exemplo 5.1, p. 70 e 71)."""

    def test_momento_e_forca_de_distorcao(self):
        d = ufm.forcas_de_distorcao(
            P_kN=840.0 * KIP,
            area_contraventamento_mm2=26.2 * POL**2,
            inercia_viga_mm4=1830.0 * POL**4,
            inercia_coluna_mm4=999.0 * POL**4,
            b_mm=150.0 * POL,
            c_mm=139.0 * POL,
            beta_mm=12.0 * POL,
            alfa_mm=17.5 * POL,
            eb_mm=10.7 * POL,
        )
        assert kip_pol(d.MD_kNmm) == aprox(1270.0, 0.005)
        assert kips(d.HD_kN) == aprox(55.9, 0.005)
        assert d.VD_kN == pytest.approx(d.HD_kN * 12.0 / 17.5)
        assert d.FD_kN == pytest.approx(math.hypot(d.HD_kN, d.VD_kN))

    def test_exige_dados_positivos(self):
        with pytest.raises(ufm.UFMInvalido):
            ufm.forcas_de_distorcao(100.0, 0.0, 1e8, 1e8, 3000.0, 3000.0, 300.0, 400.0, 250.0)


class TestGeometriaEAuxiliares:
    def test_comprimento_horizontal_da_chapa_do_exemplo_5_1(self):
        # l_h = 2·17,5 − 2·1,00 − 3/4 = 32,25 in
        lh = ufm.comprimento_horizontal_para_alfa(17.5 * POL, 1.00 * POL, 0.75 * POL)
        assert lh / POL == pytest.approx(32.25)
        assert ufm.centroide_da_solda_na_viga(lh, 0.75 * POL, 1.00 * POL) == pytest.approx(
            17.5 * POL
        )

    def test_centroide_da_solda_na_coluna(self):
        assert ufm.centroide_da_solda_na_coluna(600.0, 100.0) == 350.0

    def test_forca_no_contraventamento_pela_horizontal(self):
        assert ufm.forca_no_contraventamento(100.0, 30.0) == pytest.approx(200.0)
        with pytest.raises(ufm.UFMInvalido):
            ufm.forca_no_contraventamento(0.0, 30.0)

    def test_theta_da_geometria(self):
        assert ufm.theta_da_geometria(12.0, 7.0) == pytest.approx(59.74, abs=0.01)
        assert ufm.theta_da_geometria(1.0, 1.0) == pytest.approx(45.0)
        with pytest.raises(ufm.UFMInvalido):
            ufm.theta_da_geometria(0.0, 5.0)


@pytest.mark.parametrize(
    ("alteracoes", "trecho"),
    [
        ({"P_kN": 0.0}, "força do contraventamento"),
        ({"theta_graus": 0.0}, "ângulo θ"),
        ({"theta_graus": 90.0}, "ângulo θ"),
        ({"eb_mm": 0.0}, "e_b"),
        ({"ec_mm": -1.0}, "e_c"),
        ({"alfa_real_mm": -1.0}, "negativos"),
        ({"caso": "outro"}, "Caso do UFM"),
        ({"ajuste": "x"}, "Ajuste"),
    ],
)
def test_entrada_invalida_vira_erro_claro(alteracoes, trecho):
    with pytest.raises(ufm.UFMInvalido, match=trecho):
        ufm.distribuir_forcas(entrada_exemplo_5_1(**alteracoes))


def test_geometria_ideal_negativa_e_erro_claro():
    # β curto demais com e_c grande e θ pequeno: α̅ negativo
    with pytest.raises(ufm.UFMInvalido, match="negativo"):
        ufm.distribuir_forcas(
            ufm.EntradaUFM(
                P_kN=100.0,
                theta_graus=15.0,
                eb_mm=300.0,
                ec_mm=300.0,
                alfa_real_mm=300.0,
                beta_real_mm=100.0,
            )
        )


def test_o_caso_3_sem_alfa_possivel_e_erro_claro():
    with pytest.raises(ufm.UFMInvalido, match="não positivo"):
        ufm.distribuir_forcas(
            ufm.EntradaUFM(
                P_kN=100.0,
                theta_graus=20.0,
                eb_mm=100.0,
                ec_mm=300.0,
                alfa_real_mm=100.0,
                beta_real_mm=0.0,
                caso=ufm.CASO_3,
            )  # fmt: skip
        )
