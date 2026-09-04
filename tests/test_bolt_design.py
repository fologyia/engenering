import math
import unittest

from core import bolt_design as bolts


class BoltCatalogTests(unittest.TestCase):
    def test_metric_catalog_matches_known_m10_area(self):
        rosca = bolts.obter_rosca("M10")
        self.assertEqual(rosca.diametro_mm, 10.0)
        self.assertEqual(rosca.passo_mm, 1.5)
        self.assertEqual(rosca.area_tracao_mm2, 58.0)

    def test_approximate_stress_area_is_close_to_table(self):
        aproximada = bolts.area_tensao_aproximada(10.0, 1.5)
        self.assertAlmostEqual(aproximada, 58.0, delta=0.2)

    def test_property_class_changes_above_m16(self):
        menor = bolts.obter_classe("8.8", 16.0)
        maior = bolts.obter_classe("8.8", 20.0)
        self.assertEqual(menor.resistencia_prova_MPa, 580.0)
        self.assertEqual(maior.resistencia_prova_MPa, 600.0)
        self.assertEqual(maior.ruptura_min_MPa, 830.0)

    def test_class_98_is_limited_to_16_mm(self):
        with self.assertRaises(ValueError):
            bolts.obter_classe("9.8", 20.0)


class BoltGroupTests(unittest.TestCase):
    def test_direct_loads_split_equally(self):
        grupo = bolts.distribuir_cargas_grupo_circular(
            4, 50.0, carga_axial_N=40_000.0, carga_cortante_N=20_000.0
        )
        self.assertTrue(all(abs(v - 10_000.0) < 1e-9 for v in grupo.forcas_axiais_N))
        self.assertTrue(all(abs(v - 5_000.0) < 1e-9 for v in grupo.forcas_cisalhantes_N))

    def test_overturning_moment_load_distribution(self):
        grupo = bolts.distribuir_cargas_grupo_circular(
            4, 50.0, momento_tombamento_Nmm=1_000_000.0
        )
        # Soma x² = 2R²; o parafuso em x=R recebe M/(2R).
        self.assertAlmostEqual(grupo.maior_tracao_N, 10_000.0)
        self.assertAlmostEqual(sum(grupo.forcas_axiais_N), 0.0)

    def test_torsion_is_equal_for_circular_pattern(self):
        grupo = bolts.distribuir_cargas_grupo_circular(
            6, 40.0, torque_grupo_Nmm=240_000.0
        )
        self.assertTrue(all(abs(v - 1_000.0) < 1e-9 for v in grupo.forcas_cisalhantes_N))

    def test_zero_radius_rejects_moment(self):
        with self.assertRaises(ValueError):
            bolts.distribuir_cargas_grupo_circular(
                1, 0.0, momento_tombamento_Nmm=10.0
            )


class BoltJointTests(unittest.TestCase):
    def setUp(self):
        self.rosca = bolts.obter_rosca("M10")
        self.classe = bolts.obter_classe("8.8", 10.0)

    def _resultado(self, **mudancas):
        entradas = dict(
            rosca=self.rosca,
            classe=self.classe,
            numero_parafusos=4,
            raio_grupo_mm=50.0,
            carga_axial_N=40_000.0,
            carga_cortante_N=20_000.0,
            momento_tombamento_Nmm=0.0,
            torque_grupo_Nmm=0.0,
            fracao_pre_carga_prova=0.75,
            fator_porcar_K=0.2,
            incerteza_pre_carga=0.25,
            perda_pre_carga=0.05,
            constante_rigidez_C=0.25,
            rosca_no_plano_corte=True,
            coeficiente_atrito_junta=0.2,
            numero_interfaces_atrito=1,
            espessura_chapa_mm=10.0,
            diametro_furo_mm=11.0,
            distancia_centro_borda_mm=20.0,
            limite_esmagamento_MPa=250.0,
            escoamento_chapa_MPa=250.0,
        )
        entradas.update(mudancas)
        return bolts.avaliar_junta(**entradas)

    def test_preload_and_torque(self):
        resultado = self._resultado()
        carga_prova = 580.0 * 58.0
        self.assertAlmostEqual(resultado.carga_prova_N, carga_prova)
        self.assertAlmostEqual(resultado.pre_carga_nominal_N, 0.75 * carga_prova)
        self.assertAlmostEqual(
            resultado.torque_nominal_Nm,
            0.2 * resultado.pre_carga_nominal_N * 10.0 / 1_000.0,
        )

    def test_external_load_fraction_increases_bolt_load(self):
        resultado = self._resultado()
        esperado = resultado.pre_carga_maxima_N + 0.25 * 10_000.0
        self.assertAlmostEqual(resultado.carga_maxima_parafuso_N, esperado)

    def test_no_external_shear_has_infinite_slip_factor(self):
        resultado = self._resultado(carga_cortante_N=0.0)
        self.assertTrue(math.isinf(resultado.fator_deslizamento))
        self.assertTrue(math.isinf(resultado.fator_esmagamento))
        self.assertTrue(math.isinf(resultado.fator_rasgamento_borda))

    def test_combined_stress_uses_von_mises(self):
        resultado = self._resultado()
        esperado = math.sqrt(
            resultado.tensao_axial_MPa**2
            + 3.0 * resultado.tensao_cisalhante_MPa**2
        )
        self.assertAlmostEqual(resultado.tensao_von_mises_MPa, esperado)

    def test_fatigue_goodman(self):
        fadiga = bolts.avaliar_fadiga_axial(
            self.rosca,
            self.classe,
            pre_carga_nominal_N=20_000.0,
            constante_rigidez_C=0.25,
            carga_externa_minima_por_parafuso_N=0.0,
            carga_externa_maxima_por_parafuso_N=10_000.0,
            fator_concentracao_fadiga_Kf=2.0,
            limite_fadiga_parafuso_MPa=160.0,
        )
        self.assertGreater(fadiga.tensao_alternada_MPa, 0.0)
        self.assertGreater(fadiga.tensao_media_MPa, 0.0)
        self.assertGreater(fadiga.fator_goodman, 0.0)


if __name__ == "__main__":
    unittest.main()
