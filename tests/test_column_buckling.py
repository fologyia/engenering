import math
import unittest

from core import column_buckling as flambagem
from core import nbr8800
from core import steel_sections as secoes


def _verificar(geometria, comprimento_mm, **overrides):
    parametros = dict(
        geometria=geometria,
        comprimento_mm=comprimento_mm,
        kx=1.0,
        ky=1.0,
        modulo_elasticidade_MPa=200_000.0,
        escoamento_MPa=250.0,
        forca_solicitante_N=10_000.0,
    )
    parametros.update(overrides)
    return flambagem.verificar_flambagem(**parametros)


class GeometriaColunaTests(unittest.TestCase):
    def test_retangular_raio_giracao(self):
        geo = flambagem.geometria_retangular(50.0, 100.0)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 100.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.raio_giracao_y_mm, 50.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.area_mm2, 5_000.0)
        self.assertIsNotNone(geo.perfil)

    def test_circular_macica_area_e_raio(self):
        geo = flambagem.geometria_circular_macica(40.0)
        self.assertAlmostEqual(geo.area_mm2, math.pi * 40.0**2 / 4.0)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 40.0 / 4.0)

    def test_circular_vazada_rejeita_diametro_interno_maior(self):
        with self.assertRaises(ValueError):
            flambagem.geometria_circular_vazada(40.0, 50.0)

    def test_circular_vazada_area_positiva(self):
        geo = flambagem.geometria_circular_vazada(60.0, 40.0)
        self.assertAlmostEqual(geo.area_mm2, math.pi / 4.0 * (60.0**2 - 40.0**2))
        self.assertTrue(secoes.e_tubo_circular(geo.perfil))

    def test_perfil_catalogo_usa_rx_ry(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)
        geo = flambagem.geometria_perfil_catalogo(perfil)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, perfil.rx_mm)
        self.assertAlmostEqual(geo.raio_giracao_y_mm, perfil.ry_mm)
        self.assertIs(geo.perfil, perfil)

    def test_direta_replica_mesmo_raio_quando_nao_informado(self):
        geo = flambagem.geometria_direta(1_000.0, 12.0)
        self.assertEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)
        self.assertIsNone(geo.perfil)


class AcoesDeCalculoTests(unittest.TestCase):
    def test_majoracao_padrao_1_40(self):
        self.assertAlmostEqual(flambagem.forca_de_calculo(30_000.0, 20_000.0), 70_000.0)

    def test_coeficientes_personalizados(self):
        self.assertAlmostEqual(
            flambagem.forca_de_calculo(10_000.0, 10_000.0, gamma_g=1.25, gamma_q=1.5),
            27_500.0,
        )

    def test_rejeita_negativos(self):
        with self.assertRaises(ValueError):
            flambagem.forca_de_calculo(-1.0)


class CurvaDeFlambagemTests(unittest.TestCase):
    def setUp(self):
        self.geometria = flambagem.geometria_circular_macica(50.0)

    def test_resistencia_e_chi_q_a_fy_sobre_gamma(self):
        resultado = _verificar(self.geometria, 2_000.0)
        area = self.geometria.area_mm2
        self.assertAlmostEqual(resultado.esbeltez_governante, 160.0, places=6)
        ne = math.pi**2 * 200_000.0 * area * 12.5**2 / 2_000.0**2
        self.assertAlmostEqual(resultado.ne_N, ne, places=3)
        self.assertEqual(resultado.fator_q, 1.0)
        lambda_0 = math.sqrt(area * 250.0 / ne)
        self.assertAlmostEqual(resultado.lambda_0, lambda_0)
        self.assertGreater(lambda_0, 1.5)
        self.assertAlmostEqual(resultado.chi, 0.877 / lambda_0**2)
        self.assertAlmostEqual(
            resultado.resistencia_N, resultado.chi * area * 250.0 / nbr8800.GAMMA_A1
        )
        self.assertEqual(resultado.modo_governante, "Compressão N_c,Rd (5.3)")

    def test_chi_reduz_em_relacao_a_euler_mesmo_na_coluna_longa(self):
        resultado = _verificar(self.geometria, 2_000.0)
        # 0,877/γ_a1 ≈ 0,80 de N_e: a curva já embute imperfeições e tensões residuais.
        self.assertLess(resultado.resistencia_N, resultado.ne_N)
        self.assertAlmostEqual(resultado.resistencia_N / resultado.ne_N, 0.877 / 1.10, places=6)

    def test_coluna_curta_usa_ramo_exponencial(self):
        resultado = _verificar(self.geometria, 500.0)
        self.assertLess(resultado.lambda_0, 1.5)
        self.assertAlmostEqual(resultado.chi, 0.658 ** (resultado.lambda_0**2))
        self.assertLess(resultado.resistencia_N, self.geometria.area_mm2 * 250.0 / 1.10)

    def test_coluna_mais_longa_resiste_menos(self):
        self.assertLess(
            _verificar(self.geometria, 3_000.0).resistencia_N,
            _verificar(self.geometria, 2_000.0).resistencia_N,
        )

    def test_engastada_livre_reduz_resistencia(self):
        self.assertLess(
            _verificar(self.geometria, 2_000.0, kx=2.0, ky=2.0).resistencia_N,
            _verificar(self.geometria, 2_000.0).resistencia_N,
        )

    def test_eixo_governante_e_o_mais_esbelto(self):
        geo = flambagem.geometria_retangular(30.0, 80.0)
        resultado = _verificar(geo, 1_000.0)
        self.assertEqual(resultado.eixo_governante, "y")
        self.assertEqual(resultado.modo_flambagem, "y")
        self.assertGreater(resultado.esbeltez_y, resultado.esbeltez_x)

    def test_utilizacao_e_nsd_sobre_ncrd(self):
        resultado = _verificar(self.geometria, 2_000.0, forca_solicitante_N=60_000.0)
        self.assertAlmostEqual(resultado.utilizacao_axial, 60_000.0 / resultado.resistencia_N)
        self.assertAlmostEqual(resultado.utilizacao, resultado.utilizacao_axial)
        self.assertTrue(resultado.atende)
        self.assertFalse(_verificar(self.geometria, 2_000.0, forca_solicitante_N=200_000.0).atende)

    def test_coincide_com_o_modulo_nbr8800_para_perfil(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)
        resultado = _verificar(flambagem.geometria_perfil_catalogo(perfil), 3_000.0)
        referencia = nbr8800.verificar_compressao(
            perfil, 250.0, 200_000.0, 200_000.0 / 2.6, 3_000.0, 1.0, 1.0, 10_000.0
        )
        self.assertAlmostEqual(resultado.resistencia_N, referencia.resistencia_N)
        self.assertAlmostEqual(resultado.chi, referencia.chi)
        self.assertEqual(resultado.fator_q, referencia.fator_q)

    def test_geometria_direta_e_flexao_pura_com_q_unitario(self):
        geo = flambagem.geometria_direta(1_963.5, 12.5)
        resultado = _verificar(geo, 2_000.0)
        self.assertIsNone(resultado.ne_z_N)
        self.assertEqual(resultado.fator_q, 1.0)
        self.assertTrue(any("Q de flambagem local" in aviso for aviso in resultado.avisos))
        referencia = _verificar(self.geometria, 2_000.0)
        self.assertAlmostEqual(resultado.resistencia_N, referencia.resistencia_N, delta=50.0)

    def test_rejeita_entradas_nao_positivas(self):
        with self.assertRaises(ValueError):
            _verificar(self.geometria, 0.0)
        with self.assertRaises(ValueError):
            _verificar(self.geometria, 1_000.0, escoamento_MPa=0.0)
        with self.assertRaises(ValueError):
            _verificar(self.geometria, 1_000.0, forca_solicitante_N=-1.0)

    def test_caso_normal_nao_gera_aviso(self):
        self.assertEqual(_verificar(self.geometria, 2_000.0).avisos, ())

    def test_k_recomendado_cobre_os_mesmos_casos_e_nunca_e_menor(self):
        self.assertEqual(
            set(flambagem.CONDICOES_APOIO), set(flambagem.CONDICOES_APOIO_RECOMENDADAS)
        )
        for nome, teorico in flambagem.CONDICOES_APOIO.items():
            with self.subTest(apoio=nome):
                self.assertGreaterEqual(flambagem.CONDICOES_APOIO_RECOMENDADAS[nome], teorico)

    def test_valores_teoricos_classicos(self):
        self.assertEqual(flambagem.CONDICOES_APOIO["Biapoiada (pino-pino)"], 1.0)
        self.assertEqual(flambagem.CONDICOES_APOIO["Engastada-livre (em balanço)"], 2.0)
        self.assertEqual(flambagem.CONDICOES_APOIO["Biengastada"], 0.5)
        self.assertAlmostEqual(flambagem.CONDICOES_APOIO_RECOMENDADAS["Biengastada"], 0.65)


class FlambagemLocalETorcaoTests(unittest.TestCase):
    def test_tubo_de_parede_fina_reduz_q(self):
        geo = flambagem.geometria_circular_vazada(200.0, 198.0)  # D/t = 200 > 0,11·E/fy = 88
        resultado = _verificar(geo, 1_000.0)
        self.assertLess(resultado.fator_q, 1.0)
        self.assertTrue(any("Q =" in aviso for aviso in resultado.avisos))
        self.assertLess(
            resultado.resistencia_N,
            resultado.chi * geo.area_mm2 * 250.0 / nbr8800.GAMMA_A1,
        )

    def test_perfil_i_compacto_tem_q_unitario_e_nez(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 8, 12)
        resultado = _verificar(flambagem.geometria_perfil_catalogo(perfil), 2_000.0)
        self.assertEqual(resultado.fator_q, 1.0)
        self.assertIsNotNone(resultado.ne_z_N)
        self.assertEqual(len(resultado.elementos), 2)

    def test_perfil_u_tem_modo_flexo_torcional(self):
        perfil = secoes.perfil_u("U", 100, 50, 5, 8)
        resultado = _verificar(flambagem.geometria_perfil_catalogo(perfil), 1_500.0)
        self.assertIsNotNone(resultado.ne_acoplada_N)
        self.assertLess(resultado.ne_N, max(resultado.ne_x_N, resultado.ne_y_N))

    def test_barras_macicas_nao_tem_parede_nem_torcao(self):
        for geo in (
            flambagem.geometria_retangular(20.0, 60.0),
            flambagem.geometria_circular_macica(30.0),
        ):
            resultado = _verificar(geo, 500.0)
            self.assertEqual(resultado.elementos, ())
            self.assertEqual(resultado.fator_q, 1.0)
            self.assertIsNone(resultado.ne_z_N)


class AvisosTests(unittest.TestCase):
    def test_esbeltez_acima_de_200_reprova(self):
        geo = flambagem.geometria_circular_macica(20.0)  # r = 5 mm
        resultado = _verificar(geo, 1_500.0, forca_solicitante_N=100.0)  # λ = 300
        self.assertTrue(any("5.3.4.1" in aviso for aviso in resultado.avisos))
        self.assertFalse(resultado.atende)
        self.assertTrue(math.isinf(resultado.utilizacao))
        self.assertIn("200", resultado.modo_governante)

    def test_k_fora_da_faixa_fisica_e_apontado(self):
        geo = flambagem.geometria_circular_macica(50.0)
        resultado = _verificar(geo, 1_000.0, kx=0.2, ky=1.0)
        self.assertTrue(any("Kx = 0.2" in aviso for aviso in resultado.avisos))

    def test_unidades_implausiveis_de_e_e_fy_sao_apontadas(self):
        geo = flambagem.geometria_circular_macica(50.0)
        resultado = _verificar(geo, 1_000.0, modulo_elasticidade_MPa=200.0, escoamento_MPa=250.0)
        self.assertTrue(any("GPa" in aviso for aviso in resultado.avisos))
        self.assertTrue(any("f_y/E" in aviso for aviso in resultado.avisos))


class FlexocompressaoTests(unittest.TestCase):
    def setUp(self):
        self.geometria = flambagem.geometria_circular_macica(50.0)

    def test_sem_momento_nao_ha_interacao(self):
        resultado = _verificar(self.geometria, 2_000.0)
        self.assertIsNone(resultado.interacao)
        self.assertEqual(resultado.momento_x.momento_solicitante_Nmm, 0.0)

    def test_excentricidade_vira_momento_amplificado_por_b1(self):
        resultado = _verificar(
            self.geometria, 2_000.0, forca_solicitante_N=50_000.0, excentricidade_mm=5.0
        )
        momento = resultado.momento_x
        self.assertEqual(resultado.eixo_governante, "x")
        self.assertAlmostEqual(momento.momento_primeira_ordem_Nmm, 250_000.0)
        b1 = 1.0 / (1.0 - 50_000.0 / resultado.ne_x_N)
        self.assertAlmostEqual(momento.b1, b1)
        self.assertAlmostEqual(momento.momento_solicitante_Nmm, 250_000.0 * b1)
        self.assertIsNotNone(momento.momento_resistente_Nmm)
        self.assertIsNotNone(resultado.interacao)
        self.assertGreater(resultado.utilizacao, resultado.utilizacao_axial)
        self.assertEqual(resultado.modo_governante, "Interação N + M (5.5.1.2)")

    def test_equacao_de_interacao_5_5_1_2(self):
        resultado = _verificar(
            self.geometria,
            2_000.0,
            forca_solicitante_N=50_000.0,
            momento_x_Nmm=1.0e6,
        )
        rn = 50_000.0 / resultado.resistencia_N
        rm = (
            resultado.momento_x.momento_solicitante_Nmm / resultado.momento_x.momento_resistente_Nmm
        )
        self.assertGreaterEqual(rn, 0.2)
        self.assertAlmostEqual(resultado.interacao.indice, rn + 8.0 / 9.0 * rm)

    def test_ramo_de_n_pequeno_usa_metade_da_razao_axial(self):
        resultado = _verificar(
            self.geometria, 1_000.0, forca_solicitante_N=20_000.0, momento_x_Nmm=2.0e6
        )
        rn = 20_000.0 / resultado.resistencia_N
        self.assertLess(rn, 0.2)
        rm = (
            resultado.momento_x.momento_solicitante_Nmm / resultado.momento_x.momento_resistente_Nmm
        )
        self.assertAlmostEqual(resultado.interacao.indice, rn / 2.0 + rm)

    def test_momento_em_y_usa_o_eixo_y(self):
        geo = flambagem.geometria_retangular(30.0, 80.0)
        resultado = _verificar(geo, 1_000.0, forca_solicitante_N=20_000.0, momento_y_Nmm=5.0e5)
        self.assertGreater(resultado.momento_y.momento_solicitante_Nmm, 0.0)
        self.assertEqual(resultado.momento_x.momento_solicitante_Nmm, 0.0)
        self.assertAlmostEqual(resultado.momento_y.b1, 1.0 / (1.0 - 20_000.0 / resultado.ne_y_N))

    def test_cm_menor_reduz_a_amplificacao_mas_nunca_abaixo_de_um(self):
        com_cm = _verificar(
            self.geometria, 2_000.0, forca_solicitante_N=50_000.0, momento_x_Nmm=1e6, cm=0.6
        )
        sem_cm = _verificar(
            self.geometria, 2_000.0, forca_solicitante_N=50_000.0, momento_x_Nmm=1e6
        )
        self.assertLess(com_cm.momento_x.b1, sem_cm.momento_x.b1)
        self.assertGreaterEqual(com_cm.momento_x.b1, 1.0)
        self.assertEqual(flambagem.fator_amplificacao_b1(10.0, 1_000.0, cm=0.2), 1.0)

    def test_nsd_acima_de_ne_diverge_b1(self):
        resultado = _verificar(
            self.geometria, 2_000.0, forca_solicitante_N=200_000.0, momento_x_Nmm=1e6
        )
        self.assertTrue(math.isinf(resultado.momento_x.b1))
        self.assertFalse(resultado.atende)
        self.assertTrue(any("B_1" in aviso for aviso in resultado.avisos))

    def test_geometria_direta_sem_fibra_avisa_e_pula_a_interacao(self):
        geo = flambagem.geometria_direta(1_963.5, 12.5)
        resultado = _verificar(geo, 2_000.0, forca_solicitante_N=50_000.0, excentricidade_mm=5.0)
        self.assertIsNone(resultado.momento_x.momento_resistente_Nmm)
        self.assertIsNone(resultado.interacao)
        self.assertTrue(any("M_x,Rd" in aviso for aviso in resultado.avisos))

    def test_geometria_direta_com_fibra_usa_w_fy_sobre_gamma(self):
        geo = flambagem.geometria_direta(1_963.5, 12.5, distancia_fibra_x_mm=25.0)
        resultado = _verificar(geo, 2_000.0, forca_solicitante_N=50_000.0, momento_x_Nmm=1e6)
        w = 1_963.5 * 12.5**2 / 25.0
        self.assertAlmostEqual(
            resultado.momento_x.momento_resistente_Nmm, w * 250.0 / nbr8800.GAMMA_A1
        )
        self.assertIsNotNone(resultado.interacao)

    def test_eixo_invalido_e_recusado(self):
        with self.assertRaises(ValueError):
            _verificar(self.geometria, 1_000.0, excentricidade_mm=1.0, eixo_excentricidade="z")


if __name__ == "__main__":
    unittest.main()
