import math
import unittest

import numpy as np

from core import mohr_analysis as mohr


class PlaneStressTransformationTests(unittest.TestCase):
    def test_uniaxial_stress_rotated_45_degrees(self):
        resultado = mohr.analisar_estado_plano(100.0, 0.0, 0.0, 45.0)

        self.assertAlmostEqual(resultado.sigma_1_plana, 100.0)
        self.assertAlmostEqual(resultado.sigma_2_plana, 0.0)
        self.assertAlmostEqual(resultado.tau_max_plana, 50.0)
        self.assertAlmostEqual(resultado.von_mises, 100.0)
        self.assertAlmostEqual(resultado.transformacao.sigma_x_linha, 50.0)
        self.assertAlmostEqual(resultado.transformacao.sigma_y_linha, 50.0)
        self.assertAlmostEqual(
            resultado.transformacao.tau_x_linha_y_linha,
            -50.0,
        )

    def test_pure_shear_principal_values_and_angles(self):
        resultado = mohr.analisar_estado_plano(0.0, 0.0, 50.0)

        self.assertAlmostEqual(resultado.sigma_1_plana, 50.0)
        self.assertAlmostEqual(resultado.sigma_2_plana, -50.0)
        self.assertAlmostEqual(resultado.theta_p1_graus, 45.0)
        self.assertAlmostEqual(resultado.theta_tau_positivo_graus, 0.0)
        self.assertAlmostEqual(resultado.von_mises, math.sqrt(3.0) * 50.0)

    def test_absolute_shear_in_plane_stress_includes_sigma_z_zero(self):
        resultado = mohr.analisar_estado_plano(100.0, 100.0, 0.0)

        self.assertAlmostEqual(resultado.tau_max_plana, 0.0)
        self.assertAlmostEqual(resultado.tau_max_absoluta, 50.0)
        self.assertEqual(resultado.tensoes_principais_3d, (100.0, 100.0, 0.0))

    def test_plane_transformation_preserves_trace(self):
        transformada = mohr.transformar_tensoes_planas(80.0, -20.0, 35.0, 27.0)
        self.assertAlmostEqual(
            transformada.sigma_x_linha + transformada.sigma_y_linha,
            60.0,
        )

    def test_non_finite_plane_input_is_rejected(self):
        with self.assertRaises(ValueError):
            mohr.analisar_estado_plano(math.nan, 0.0, 0.0)


class ThreeDimensionalStressTests(unittest.TestCase):
    def test_diagonal_tensor_has_known_principal_stresses(self):
        resultado = mohr.analisar_estado_tridimensional(
            120.0, 40.0, -20.0, 0.0, 0.0, 0.0
        )

        self.assertEqual(resultado.tensoes_principais, (120.0, 40.0, -20.0))
        self.assertAlmostEqual(resultado.tau_max_absoluta, 70.0)
        self.assertAlmostEqual(resultado.tresca_equivalente, 140.0)
        self.assertAlmostEqual(
            resultado.von_mises,
            math.sqrt(
                0.5
                * (
                    (120.0 - 40.0) ** 2
                    + (40.0 + 20.0) ** 2
                    + (-20.0 - 120.0) ** 2
                )
            ),
        )
        np.testing.assert_allclose(resultado.direcoes_principais, np.eye(3))

    def test_hydrostatic_state_has_no_distortional_stress(self):
        resultado = mohr.analisar_estado_tridimensional(
            60.0, 60.0, 60.0, 0.0, 0.0, 0.0
        )

        self.assertAlmostEqual(resultado.tensao_media, 60.0)
        self.assertAlmostEqual(resultado.von_mises, 0.0)
        self.assertAlmostEqual(resultado.tau_max_absoluta, 0.0)
        self.assertAlmostEqual(resultado.J2, 0.0)

    def test_pure_shear_principal_stresses(self):
        resultado = mohr.analisar_estado_tridimensional(
            0.0, 0.0, 0.0, 50.0, 0.0, 0.0
        )

        np.testing.assert_allclose(
            resultado.tensoes_principais,
            (50.0, 0.0, -50.0),
            atol=1e-12,
        )
        self.assertAlmostEqual(resultado.von_mises, math.sqrt(3.0) * 50.0)

    def test_traction_on_inclined_plane(self):
        tensor = mohr.montar_tensor_tensoes(
            100.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )
        tracao = mohr.tracao_em_plano(tensor, (1.0, 1.0, 0.0))

        self.assertAlmostEqual(tracao.sigma_normal, 50.0)
        self.assertAlmostEqual(tracao.tau_resultante, 50.0)
        np.testing.assert_allclose(
            tracao.normal_unitaria,
            np.array([1.0, 1.0, 0.0]) / math.sqrt(2.0),
        )

    def test_zero_normal_is_rejected(self):
        with self.assertRaises(ValueError):
            mohr.tracao_em_plano(np.eye(3), (0.0, 0.0, 0.0))

    def test_non_symmetric_tensor_is_rejected_for_plane_traction(self):
        with self.assertRaises(ValueError):
            mohr.tracao_em_plano(
                np.array(
                    [
                        [1.0, 2.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ]
                ),
                (1.0, 0.0, 0.0),
            )


if __name__ == "__main__":
    unittest.main()
