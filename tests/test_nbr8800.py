"""Testes da verificação de barras pela NBR 8800:2008.

Os valores esperados são recalculados nos próprios testes a partir das
equações da norma, escritas de forma independente do módulo, e os limites
clássicos (coluna curta → escoamento, coluna longa → Euler/1,1, mesa
compacta → M_pl/1,1, alma compacta → V_pl/1,1) ficam travados.
"""

import math
import unittest

from core import nbr8800 as nbr
from core import steel_sections as secoes

E = 200_000.0
G = 77_000.0
FY = 345.0
FU = 450.0


def perfil_w() -> secoes.PerfilAco:
    """Perfil parecido com um W 250 x 32,7 — alma esbelta à compressão com fy = 345."""
    return secoes.perfil_w_mesa_larga("W", 258.0, 146.0, 6.1, 9.1)


def perfil_compacto() -> secoes.PerfilAco:
    """Mesa e alma compactas mesmo com fy = 345 MPa (h/tw = 29 < 35,9)."""
    return secoes.perfil_w_mesa_larga("Wc", 258.0, 146.0, 8.0, 12.0)


class CompressaoTests(unittest.TestCase):
    def test_coluna_curta_compacta_escoa_a_secao_inteira(self):
        perfil = perfil_compacto()
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 300.0, 1.0, 1.0, 100_000.0)
        self.assertAlmostEqual(resultado.fator_q, 1.0)
        self.assertGreater(resultado.chi, 0.98)
        self.assertAlmostEqual(
            resultado.resistencia_N, resultado.chi * perfil.area_mm2 * FY / 1.10, places=6
        )

    def test_coluna_longa_cai_em_euler_reduzido(self):
        # λ0 > 1,5: χ = 0,877/λ0², logo N_c,Rd = 0,877·N_e/γ_a1.
        perfil = perfil_w()
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 6_000.0, 1.0, 1.0, 10_000.0)
        self.assertGreater(resultado.lambda_0, 1.5)
        self.assertAlmostEqual(resultado.resistencia_N, 0.877 * resultado.ne_N / 1.10, places=6)
        self.assertEqual(resultado.modo_flambagem, "y")

    def test_ne_por_flexao_bate_com_euler_e_ne_z_existe_no_perfil_i(self):
        perfil = perfil_w()
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 4_000.0, 1.0, 1.0, 1.0)
        self.assertAlmostEqual(resultado.ne_x_N, math.pi**2 * E * perfil.ix_mm4 / 4_000.0**2)
        self.assertAlmostEqual(resultado.ne_y_N, math.pi**2 * E * perfil.iy_mm4 / 4_000.0**2)
        r0 = perfil.rx_mm**2 + perfil.ry_mm**2
        esperado_z = (math.pi**2 * E * perfil.cw_mm6 / 4_000.0**2 + G * perfil.j_mm4) / r0
        self.assertAlmostEqual(resultado.ne_z_N, esperado_z, delta=1e-6 * esperado_z)
        self.assertIsNone(resultado.ne_acoplada_N)

    def test_lambda_0_e_chi_seguem_a_curva_unica(self):
        perfil = perfil_w()
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 3_000.0, 1.0, 1.0, 1.0)
        lambda_0 = math.sqrt(resultado.fator_q * perfil.area_mm2 * FY / resultado.ne_N)
        self.assertAlmostEqual(resultado.lambda_0, lambda_0)
        esperado = 0.658 ** (lambda_0**2) if lambda_0 <= 1.5 else 0.877 / lambda_0**2
        self.assertAlmostEqual(resultado.chi, esperado)

    def test_esbeltez_acima_de_200_e_apontada(self):
        perfil = perfil_w()
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 8_000.0, 1.0, 1.0, 1.0)
        self.assertGreater(resultado.esbeltez_y, 200.0)
        self.assertTrue(any("5.3.4.1" in aviso for aviso in resultado.avisos))
        barra = nbr.verificar_barra(
            perfil,
            fy_MPa=FY,
            fu_MPa=FU,
            modulo_elasticidade_MPa=E,
            modulo_cisalhamento_MPa=G,
            comprimento_mm=8_000.0,
            kx=1.0,
            ky=1.0,
            forca_axial_N=-1_000.0,
        )
        self.assertTrue(math.isinf(barra.utilizacao_governante))
        self.assertIn("200", barra.modo_governante)

    def test_perfil_u_tem_modo_flexo_torcional(self):
        perfil = secoes.perfil_u("U", 203.0, 57.0, 5.6, 9.9)
        resultado = nbr.verificar_compressao(perfil, FY, E, G, 2_500.0, 1.0, 1.0, 1.0)
        self.assertIsNotNone(resultado.ne_acoplada_N)
        self.assertIsNotNone(resultado.ne_z_N)
        # A flexo-torção fica entre a torção pura e a flexão em x.
        self.assertLess(resultado.ne_acoplada_N, resultado.ne_x_N)
        self.assertLess(resultado.ne_acoplada_N, max(resultado.ne_x_N, resultado.ne_z_N))
        self.assertIn(resultado.modo_flambagem, {"y", "xz (flexo-torção)"})

    def test_kz_menor_eleva_a_torcao(self):
        perfil = perfil_w()
        livre = nbr.verificar_compressao(perfil, FY, E, G, 4_000.0, 1.0, 1.0, 1.0)
        travada = nbr.verificar_compressao(perfil, FY, E, G, 4_000.0, 1.0, 1.0, 1.0, kz=0.5)
        self.assertGreater(travada.ne_z_N, livre.ne_z_N)


class FatorQTests(unittest.TestCase):
    def test_perfil_compacto_tem_q_unitario_e_paredes_classificadas(self):
        q, elementos, avisos = nbr.fator_q(perfil_compacto(), FY, E)
        self.assertAlmostEqual(q, 1.0)
        self.assertEqual({item.nome for item in elementos}, {"mesa", "alma"})
        self.assertEqual(avisos, ())
        mesa = next(item for item in elementos if item.nome == "mesa")
        self.assertAlmostEqual(mesa.razao, (146.0 / 2.0) / 12.0)
        # O W 250 x 32,7 com fy = 345 tem alma esbelta: Q_a < 1 e a norma manda reduzir.
        q_esbelto, elementos_esbelto, _ = nbr.fator_q(perfil_w(), FY, E)
        alma = next(item for item in elementos_esbelto if item.nome == "alma")
        self.assertGreater(alma.razao, alma.limite_r)
        self.assertLess(q_esbelto, 1.0)
        self.assertAlmostEqual(mesa.limite_r, 0.56 * math.sqrt(E / FY))

    def test_mesa_esbelta_reduz_qs_pela_reta_do_grupo_4(self):
        # b/2t = 20 entre 0,56√(E/fy) = 13,5 e 1,03√(E/fy) = 24,8.
        perfil = secoes.perfil_i_simetrico("I", 300.0, 320.0, 8.0, 8.0)
        q, elementos, _ = nbr.fator_q(perfil, FY, E)
        razao = 160.0 / 8.0
        esperado = 1.415 - 0.74 * razao * math.sqrt(FY / E)
        mesa = next(item for item in elementos if item.nome == "mesa")
        self.assertAlmostEqual(mesa.fator_q, esperado)
        # Alma compacta: Q_a = 1, logo Q = Q_s.
        self.assertAlmostEqual(q, esperado)

    def test_alma_esbelta_usa_largura_efetiva(self):
        # h/tw = 120 > 1,49√(E/fy) = 35,9: só parte da alma trabalha.
        perfil = secoes.perfil_i_simetrico("I", 620.0, 200.0, 5.0, 10.0)
        q, elementos, _ = nbr.fator_q(perfil, FY, E, chi_para_sigma=1.0)
        alma = next(item for item in elementos if item.nome == "alma")
        hw, tw = 600.0, 5.0
        raiz = math.sqrt(E / FY)
        b_ef = min(hw, 1.92 * tw * raiz * (1.0 - (0.34 / (hw / tw)) * raiz))
        self.assertAlmostEqual(alma.largura_efetiva_mm, b_ef)
        self.assertAlmostEqual(q, (perfil.area_mm2 - (hw - b_ef) * tw) / perfil.area_mm2)
        self.assertLess(q, 0.9)

    def test_tubo_circular_segue_f4(self):
        fino = secoes.tubo_circular("TC", 300.0, 3.0)  # D/t = 100 > 0,11 E/fy = 63,8
        q, elementos, avisos = nbr.fator_q(fino, FY, E)
        self.assertAlmostEqual(q, 0.038 * E / (FY * 100.0) + 2.0 / 3.0)
        self.assertEqual(avisos, ())
        compacto = secoes.tubo_circular("TC", 100.0, 5.0)
        self.assertAlmostEqual(nbr.fator_q(compacto, FY, E)[0], 1.0)

    def test_perfil_t_usa_o_menor_qs_entre_mesa_e_talao(self):
        perfil = secoes.perfil_t("T", 200.0, 150.0, 5.0, 8.0)  # talão h/tw = 40 > 0,75√(E/fy)
        q, elementos, _ = nbr.fator_q(perfil, FY, E)
        talao = next(item for item in elementos if "talão" in item.nome)
        self.assertLess(talao.fator_q, 1.0)
        self.assertAlmostEqual(q, min(item.fator_q for item in elementos))

    def test_perfil_soldado_usa_kc_no_grupo_5(self):
        perfil = secoes.perfil_i_simetrico("I", 300.0, 320.0, 8.0, 8.0)
        laminado, _, _ = nbr.fator_q(perfil, FY, E, soldado=False)
        soldado, elementos, _ = nbr.fator_q(perfil, FY, E, soldado=True)
        self.assertEqual(next(item for item in elementos if item.nome == "mesa").grupo, "5")
        self.assertNotAlmostEqual(laminado, soldado)


class FlexaoTests(unittest.TestCase):
    def test_viga_travada_e_compacta_atinge_mpl(self):
        perfil = perfil_w()
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=500.0)
        self.assertAlmostEqual(resultado.resistencia_Nmm, perfil.zx_mm3 * FY / 1.10)
        for modo in resultado.modos:
            self.assertIn("plástico", modo.regime)

    def test_viga_muito_destravada_cai_em_mcr(self):
        perfil = perfil_w()
        lb = 12_000.0
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=lb)
        flt = next(modo for modo in resultado.modos if modo.nome.startswith("FLT"))
        self.assertIn("elástico", flt.regime)
        mcr = (math.pi**2 * E * perfil.iy_mm4 / lb**2) * math.sqrt(
            (perfil.cw_mm6 / perfil.iy_mm4) * (1.0 + 0.039 * perfil.j_mm4 * lb**2 / perfil.cw_mm6)
        )
        self.assertAlmostEqual(flt.momento_cr_Nmm, mcr, delta=1e-9 * mcr)
        self.assertAlmostEqual(resultado.resistencia_Nmm, mcr / 1.10, delta=1e-9 * mcr)
        self.assertTrue(resultado.modo_governante.startswith("FLT"))

    def test_limites_da_flt_seguem_o_anexo_g(self):
        perfil = perfil_w()
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=3_000.0)
        flt = next(modo for modo in resultado.modos if modo.nome.startswith("FLT"))
        self.assertAlmostEqual(flt.lambda_p, 1.76 * math.sqrt(E / FY))
        w = perfil.sx_mm3
        beta1 = 0.7 * FY * w / (E * perfil.j_mm4)
        lambda_r = (
            1.38 * math.sqrt(perfil.iy_mm4 * perfil.j_mm4) / (perfil.ry_mm * perfil.j_mm4 * beta1)
        ) * math.sqrt(1.0 + math.sqrt(1.0 + 27.0 * perfil.cw_mm6 * beta1**2 / perfil.iy_mm4))
        self.assertAlmostEqual(flt.lambda_r, lambda_r, delta=1e-9 * lambda_r)
        self.assertAlmostEqual(flt.momento_r_Nmm, 0.7 * FY * w)

    def test_regime_inelastico_interpola_e_cb_amplifica_ate_mpl(self):
        perfil = perfil_w()
        lb = 3_000.0
        cb1 = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=lb, cb=1.0)
        cb2 = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=lb, cb=1.75)
        flt1 = next(modo for modo in cb1.modos if modo.nome.startswith("FLT"))
        self.assertIn("inelástico", flt1.regime)
        esperado = (
            flt1.momento_pl_Nmm
            - (flt1.momento_pl_Nmm - flt1.momento_r_Nmm)
            * (flt1.esbeltez - flt1.lambda_p)
            / (flt1.lambda_r - flt1.lambda_p)
        ) / 1.10
        self.assertAlmostEqual(flt1.resistencia_Nmm, esperado, delta=1e-9 * esperado)
        self.assertGreater(cb2.resistencia_Nmm, cb1.resistencia_Nmm)
        self.assertLessEqual(cb2.resistencia_Nmm, perfil.zx_mm3 * FY / 1.10 * (1 + 1e-12))

    def test_mesa_esbelta_governa_por_flm(self):
        perfil = secoes.perfil_i_simetrico("I", 300.0, 400.0, 8.0, 6.0)  # b/2t = 33
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=500.0)
        self.assertTrue(resultado.modo_governante.startswith("FLM"))
        flm = next(modo for modo in resultado.modos if modo.nome.startswith("FLM"))
        self.assertAlmostEqual(
            flm.momento_cr_Nmm, 0.69 * E * perfil.sx_mm3 / 33.333333333333336**2, delta=1.0
        )

    def test_alma_esbelta_avisa_anexo_h(self):
        perfil = secoes.perfil_i_simetrico(
            "I", 1_000.0, 250.0, 6.0, 12.0
        )  # h/tw = 163 > 5,70√(E/fy)
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, comprimento_destravado_mm=500.0)
        self.assertTrue(any("Anexo H" in aviso for aviso in resultado.avisos))

    def test_eixo_fraco_so_tem_flm_e_respeita_1_5_w_fy(self):
        perfil = perfil_w()
        resultado = nbr.verificar_flexao(perfil, FY, E, G, 1e6, eixo="y")
        self.assertEqual([modo.nome for modo in resultado.modos], ["FLM (G.2)"])
        self.assertLessEqual(
            resultado.resistencia_Nmm, 1.5 * perfil.sy_mm3 * FY / 1.10 * (1 + 1e-12)
        )

    def test_perfil_u_forca_cb_unitario_na_flt(self):
        perfil = secoes.perfil_u("U", 203.0, 57.0, 5.6, 9.9)
        resultado = nbr.verificar_flexao(
            perfil, FY, E, G, 1e6, comprimento_destravado_mm=4_000.0, cb=1.5
        )
        self.assertTrue(any("C_b" in aviso for aviso in resultado.avisos))
        sem_cb = nbr.verificar_flexao(
            perfil, FY, E, G, 1e6, comprimento_destravado_mm=4_000.0, cb=1.0
        )
        self.assertAlmostEqual(
            resultado.resistencia_Nmm, sem_cb.resistencia_Nmm, delta=1e-9 * sem_cb.resistencia_Nmm
        )

    def test_sem_lb_a_flt_e_apontada_como_nao_verificada(self):
        resultado = nbr.verificar_flexao(perfil_w(), FY, E, G, 1e6)
        self.assertTrue(any("L_b" in aviso for aviso in resultado.avisos))
        self.assertFalse(any(modo.nome.startswith("FLT") for modo in resultado.modos))


class CisalhamentoTests(unittest.TestCase):
    def test_alma_compacta_atinge_vpl(self):
        perfil = perfil_w()
        resultado = nbr.verificar_cisalhamento(perfil, FY, E, 10_000.0)
        self.assertAlmostEqual(resultado.kv, 5.0)
        self.assertAlmostEqual(resultado.area_cisalhamento_mm2, 258.0 * 6.1)
        self.assertAlmostEqual(resultado.resistencia_N, 0.6 * FY * 258.0 * 6.1 / 1.10)
        self.assertIn("plástico", resultado.regime)

    def test_alma_esbelta_reduz_pela_esbeltez(self):
        perfil = secoes.perfil_i_simetrico("I", 1_000.0, 250.0, 5.0, 12.0)  # h/tw = 195
        resultado = nbr.verificar_cisalhamento(perfil, FY, E, 10_000.0)
        lambda_p = 1.10 * math.sqrt(5.0 * E / FY)
        self.assertGreater(resultado.esbeltez_alma, resultado.lambda_r)
        esperado = (
            1.24 * (lambda_p / resultado.esbeltez_alma) ** 2 * 0.6 * FY * 1_000.0 * 5.0 / 1.10
        )
        self.assertAlmostEqual(resultado.resistencia_N, esperado, delta=1e-9 * esperado)

    def test_enrijecedores_elevam_kv(self):
        perfil = secoes.perfil_i_simetrico("I", 1_000.0, 250.0, 5.0, 12.0)
        sem = nbr.verificar_cisalhamento(perfil, FY, E, 1.0)
        com = nbr.verificar_cisalhamento(perfil, FY, E, 1.0, distancia_enrijecedores_mm=1_000.0)
        self.assertGreater(com.kv, sem.kv)
        self.assertGreater(com.resistencia_N, sem.resistencia_N)

    def test_cortante_nas_mesas_usa_kv_1_2(self):
        resultado = nbr.verificar_cisalhamento(perfil_w(), FY, E, 1.0, eixo="y")
        self.assertAlmostEqual(resultado.kv, 1.2)
        self.assertAlmostEqual(resultado.area_cisalhamento_mm2, 2 * 146.0 * 9.1)


class TracaoEInteracaoTests(unittest.TestCase):
    def test_tracao_usa_gamma_a1_e_a2(self):
        perfil = perfil_w()
        resultado = nbr.verificar_tracao(
            perfil, FY, FU, 100_000.0, area_liquida_mm2=0.85 * perfil.area_mm2, coeficiente_ct=0.9
        )
        self.assertAlmostEqual(resultado.resistencia_escoamento_N, perfil.area_mm2 * FY / 1.10)
        self.assertAlmostEqual(
            resultado.resistencia_ruptura_N, 0.9 * 0.85 * perfil.area_mm2 * FU / 1.35
        )
        self.assertEqual(
            resultado.resistencia_N,
            min(resultado.resistencia_escoamento_N, resultado.resistencia_ruptura_N),
        )

    def test_interacao_troca_de_expressao_em_0_2(self):
        alta = nbr.verificar_interacao(30.0, 100.0, 40.0, 100.0)
        self.assertAlmostEqual(alta.indice, 0.3 + 8.0 / 9.0 * 0.4)
        baixa = nbr.verificar_interacao(10.0, 100.0, 40.0, 100.0)
        self.assertAlmostEqual(baixa.indice, 0.05 + 0.4)
        self.assertIn("8/9", alta.expressao)

    def test_verificacao_completa_escolhe_o_pior_modo(self):
        perfil = perfil_w()
        barra = nbr.verificar_barra(
            perfil,
            fy_MPa=FY,
            fu_MPa=FU,
            modulo_elasticidade_MPa=E,
            modulo_cisalhamento_MPa=G,
            comprimento_mm=3_000.0,
            kx=1.0,
            ky=1.0,
            forca_axial_N=-200_000.0,
            momento_x_Nmm=60e6,
            cortante_N=50_000.0,
            comprimento_destravado_mm=3_000.0,
        )
        self.assertIsNotNone(barra.compressao)
        self.assertIsNone(barra.tracao)
        self.assertAlmostEqual(
            barra.utilizacao_governante,
            max(
                barra.compressao.utilizacao,
                barra.flexao_x.utilizacao,
                barra.cisalhamento.utilizacao,
                barra.interacao.indice,
            ),
        )
        self.assertTrue(barra.modo_governante)
        tracionada = nbr.verificar_barra(
            perfil,
            fy_MPa=FY,
            fu_MPa=FU,
            modulo_elasticidade_MPa=E,
            modulo_cisalhamento_MPa=G,
            comprimento_mm=3_000.0,
            kx=1.0,
            ky=1.0,
            forca_axial_N=200_000.0,
        )
        self.assertIsNotNone(tracionada.tracao)
        self.assertIsNone(tracionada.compressao)


class GeometriaDerivadaTests(unittest.TestCase):
    def test_centro_de_cisalhamento_do_u_fica_fora_da_alma(self):
        perfil = secoes.perfil_u("U", 203.0, 57.0, 5.6, 9.9)
        x0, y0 = secoes.centro_de_cisalhamento_do_perfil(perfil)
        self.assertLess(x0, 0.0)  # do lado oposto às mesas
        self.assertGreater(abs(x0), perfil.centroide_x_mm)  # além da face externa da alma
        self.assertEqual(y0, 0.0)

    def test_cw_estimado_para_u_sem_cw_tabelado(self):
        from dataclasses import replace

        perfil = replace(secoes.perfil_u("U", 203.0, 57.0, 5.6, 9.9), cw_mm6=0.0)
        estimado = secoes.constante_de_empenamento_estimada(perfil)
        self.assertGreater(estimado, 0.0)
        # Ordem de grandeza: tf·b³·h²/12 × fator entre 0 e 1.
        b, h = 57.0 - 2.8, 203.0 - 9.9
        self.assertLess(estimado, 9.9 * b**3 * h**2 / 12.0)

    def test_perfis_simetricos_tem_centro_de_cisalhamento_no_centroide(self):
        self.assertEqual(secoes.centro_de_cisalhamento_do_perfil(perfil_w()), (0.0, 0.0))
        self.assertEqual(
            secoes.centro_de_cisalhamento_do_perfil(secoes.tubo_retangular("TR", 200, 100, 6)),
            (0.0, 0.0),
        )


if __name__ == "__main__":
    unittest.main()
