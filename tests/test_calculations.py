import math
import unittest

from core import fatigue, materials, size_effect, static_analysis


class StaticAnalysisTests(unittest.TestCase):
    def test_uniaxial_state(self):
        self.assertAlmostEqual(static_analysis.tensao_von_mises_plana(100, 0, 0), 100)
        self.assertEqual(static_analysis.tensoes_principais_planas(100, 0, 0), (100, 0))

    def test_zero_stress_has_infinite_safety(self):
        self.assertTrue(math.isinf(static_analysis.fator_seguranca_escoamento(0, 250)))

    def test_invalid_strength_is_rejected(self):
        with self.assertRaises(ValueError):
            static_analysis.fator_seguranca_ruptura(100, 0)


class FatigueTests(unittest.TestCase):
    def test_steel_endurance_limit(self):
        valor, infinite = fatigue.se_linha(600, "aco")
        self.assertEqual(valor, 300)
        self.assertTrue(infinite)

    def test_sn_round_trip(self):
        a, b = fatigue.parametros_curva_sn(540, 200, 1e6)
        strength = fatigue.resistencia_para_N(1e5, a, b)
        self.assertAlmostEqual(fatigue.ciclos_para_S(strength, a, b), 1e5)

    def test_sn_mean_stress_and_1e3_strength(self):
        self.assertEqual(
            fatigue.resistencia_em_1e3_ciclos(600, "flexao", "norton"),
            540,
        )
        self.assertEqual(
            fatigue.resistencia_em_1e3_ciclos(600, "axial", "norton"),
            450,
        )
        self.assertEqual(
            fatigue.resistencia_em_1e3_ciclos(600, "axial", "shigley"),
            540,
        )
        self.assertAlmostEqual(
            fatigue.tensao_alternada_equivalente_goodman(100, 100, 600),
            120,
        )
        self.assertTrue(
            math.isinf(
                fatigue.tensao_alternada_equivalente_goodman(100, 600, 600)
            )
        )

    def test_fatigue_domain_validation(self):
        with self.assertRaises(ValueError):
            fatigue.fator_tamanho(20, tipo_carga="invalida")
        with self.assertRaises(ValueError):
            fatigue.tensao_com_concentracao(-1, 1.5)
    def test_norton_marin_factors(self):
        self.assertEqual(fatigue.fator_carregamento("axial", "norton"), 0.70)
        self.assertEqual(fatigue.fator_tamanho(251, modelo="norton"), 0.6)
        self.assertAlmostEqual(
            fatigue.fator_temperatura(260, "norton"),
            0.71,
        )
        self.assertEqual(
            fatigue.fator_temperatura((450 - 32) / 1.8, "norton"),
            1.0,
        )
        with self.assertRaises(ValueError):
            fatigue.fator_temperatura(287.79, "norton")

        self.assertAlmostEqual(fatigue.fahrenheit_para_celsius(500), 260.0)
        self.assertAlmostEqual(
            fatigue.fator_temperatura_na_unidade(500, "°F", "norton"),
            0.71,
        )
        self.assertAlmostEqual(
            fatigue.fator_temperatura_na_unidade(260, "°C", "norton"),
            0.71,
        )
        self.assertEqual(
            fatigue.limites_temperatura_entrada("norton", "°F")[1],
            550.0,
        )
        self.assertAlmostEqual(
            fatigue.limites_temperatura_entrada("norton", "°C")[1],
            (550.0 - 32.0) / 1.8,
        )
        with self.assertRaises(ValueError):
            fatigue.fator_temperatura_na_unidade(551, "°F", "norton")
        with self.assertRaises(ValueError):
            fatigue.temperatura_para_celsius(20, "kelvin")

    def test_shigley_marin_factors(self):
        self.assertEqual(fatigue.fator_carregamento("axial", "shigley"), 0.85)
        self.assertEqual(fatigue.fator_carregamento("torcao", "shigley"), 0.59)
        self.assertAlmostEqual(
            fatigue.fator_temperatura(500, "shigley"),
            0.768,
            delta=0.01,
        )
        self.assertAlmostEqual(
            fatigue.fator_tamanho(20, modelo="shigley"),
            1.24 * 20 ** (-0.107),
        )
        self.assertEqual(
            fatigue.fator_tamanho(100, tipo_carga="axial", modelo="shigley"),
            1.0,
        )
        with self.assertRaises(ValueError):
            fatigue.fator_tamanho(255, modelo="shigley")
        with self.assertRaises(ValueError):
            fatigue.fator_temperatura(19, "shigley")

    def test_surface_factor_for_cast_iron(self):
        self.assertEqual(
            fatigue.fator_superficie(214, "forjado", material="ferro"),
            1.0,
        )

    def test_goodman_and_soderberg_safety_factors(self):
        self.assertAlmostEqual(
            fatigue.fator_seguranca_goodman(100, 100, 200, 600),
            1.5,
        )
        self.assertAlmostEqual(
            fatigue.fator_seguranca_soderberg(100, 100, 200, 400),
            4 / 3,
        )
        self.assertAlmostEqual(
            fatigue.fator_seguranca_escoamento_flutuante(100, 100, 400),
            2.0,
        )

    def test_zero_fluctuating_stress_has_infinite_safety(self):
        self.assertTrue(
            math.isinf(fatigue.fator_seguranca_goodman(0, 0, 200, 600))
        )

    def test_negative_mean_stress_is_rejected_by_tensile_model(self):
        with self.assertRaises(ValueError):
            fatigue.fator_seguranca_goodman(100, -10, 200, 600)

    def test_notch_factor_limits(self):
        self.assertEqual(fatigue.fator_concentracao_fadiga(2.0, 0.0), 1.0)
        self.assertEqual(fatigue.fator_concentracao_fadiga(2.0, 1.0), 2.0)
        self.assertAlmostEqual(
            fatigue.fator_concentracao_fadiga(2.0, 0.5), 1.5
        )
        self.assertAlmostEqual(
            fatigue.tensao_com_concentracao(100.0, 1.5), 150.0
        )
        with self.assertRaises(ValueError):
            fatigue.fator_concentracao_fadiga(0.9, 0.5)

class SizeEffectTests(unittest.TestCase):
    def test_equivalent_diameter_from_area_95(self):
        self.assertAlmostEqual(
            size_effect.diametro_equivalente_por_area_95(
                size_effect.area_95_circulo_rotativo(20)
            ),
            20,
        )
        self.assertAlmostEqual(
            size_effect.diametro_equivalente_por_area_95(
                size_effect.area_95_circulo_nao_rotativo(20)
            ),
            math.sqrt(0.01046 / 0.0766) * 20,
            places=6,
        )
        self.assertAlmostEqual(
            size_effect.diametro_equivalente_por_area_95(
                size_effect.area_95_retangulo(60, 40)
            ),
            0.808 * math.sqrt(60 * 40),
            places=2,
        )

    def test_i_and_channel_areas_follow_selected_axis(self):
        self.assertEqual(
            size_effect.area_95_perfil_i(100, 200, 10, "eixo 1-1"), 100
        )
        self.assertEqual(
            size_effect.area_95_perfil_i(100, 200, 10, "eixo 2-2"), 1000
        )
        self.assertEqual(
            size_effect.area_95_perfil_canal(100, 200, 10, 70, "eixo 1-1"),
            1000,
        )
        self.assertAlmostEqual(
            size_effect.area_95_perfil_canal(100, 200, 10, 70, "eixo 2-2"),
            494,
        )

    def test_geometry_domain_validation(self):
        with self.assertRaises(ValueError):
            size_effect.area_95_perfil_i(100, 200, 2.5, "eixo 1-1")
        with self.assertRaises(ValueError):
            size_effect.area_95_perfil_canal(100, 200, 10, 201, "eixo 2-2")
        with self.assertRaises(ValueError):
            fatigue.fator_tamanho(2.78, modelo="shigley")

class MaterialsTests(unittest.TestCase):
    def test_material_database_schema(self):
        df = materials.carregar_materiais()
        self.assertTrue(materials.COLUNAS_OBRIGATORIAS.issubset(df.columns))
        self.assertFalse(df.empty)


if __name__ == "__main__":
    unittest.main()