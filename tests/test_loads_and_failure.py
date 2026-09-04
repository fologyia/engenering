import math
import unittest

from core import failure_criteria as falha
from core import load_to_stress as cargas


class LoadToStressTests(unittest.TestCase):
    def test_axial_bar(self):
        estado = cargas.barra_axial(20_000.0, 200.0)
        self.assertEqual(estado.sigma_x, 100.0)
        self.assertEqual(estado.sigma_y, 0.0)
        self.assertEqual(estado.tau_xy, 0.0)

    def test_solid_shaft_bending_and_torsion(self):
        estado = cargas.eixo_circular_macico(
            diametro_mm=30.0,
            forca_axial_N=0.0,
            momento_fletor_Nmm=500_000.0,
            torque_Nmm=300_000.0,
            face_flexao="tracionada",
        )
        self.assertAlmostEqual(
            estado.sigma_x,
            32.0 * 500_000.0 / (math.pi * 30.0**3),
        )
        self.assertAlmostEqual(
            estado.tau_xy,
            16.0 * 300_000.0 / (math.pi * 30.0**3),
        )

    def test_rectangular_beam_shear_is_maximum_at_neutral_axis(self):
        centro = cargas.viga_retangular(20.0, 40.0, 0.0, 0.0, 0.0, 1_000.0)
        superficie = cargas.viga_retangular(
            20.0, 40.0, 20.0, 0.0, 0.0, 1_000.0
        )
        self.assertAlmostEqual(centro.tau_xy, 1.5 * 1_000.0 / (20.0 * 40.0))
        self.assertAlmostEqual(superficie.tau_xy, 0.0)

    def test_thin_closed_pressure_vessel(self):
        estado = cargas.vaso_cilindrico_parede_fina(2.0, 500.0, 5.0, True)
        self.assertAlmostEqual(estado.sigma_x, 50.0)
        self.assertAlmostEqual(estado.sigma_y, 100.0)
        self.assertEqual(cargas.relacao_diametro_espessura(500.0, 5.0), 100.0)

    def test_invalid_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            cargas.barra_axial(1_000.0, 0.0)
        with self.assertRaises(ValueError):
            cargas.viga_retangular(20.0, 40.0, 21.0, 0.0, 0.0, 0.0)


class FailureCriteriaTests(unittest.TestCase):
    def test_uniaxial_factors_match_strength_ratios(self):
        principais = (100.0, 0.0, 0.0)
        self.assertEqual(falha.fator_seguranca_von_mises(100.0, 250.0), 2.5)
        self.assertEqual(falha.fator_seguranca_tresca(principais, 250.0), 2.5)
        rankine = falha.fator_seguranca_rankine(principais, 400.0, 600.0)
        self.assertEqual(rankine.fator_seguranca, 4.0)
        self.assertEqual(rankine.modo_critico, "tração")

    def test_rankine_uses_compressive_strength(self):
        rankine = falha.fator_seguranca_rankine(
            (20.0, 0.0, -120.0),
            Sut_MPa=100.0,
            Suc_MPa=300.0,
        )
        self.assertAlmostEqual(rankine.fator_tracao, 5.0)
        self.assertAlmostEqual(rankine.fator_compressao, 2.5)
        self.assertAlmostEqual(rankine.fator_seguranca, 2.5)
        self.assertEqual(rankine.modo_critico, "compressão")

    def test_rankine_requires_compressive_strength_when_needed(self):
        rankine = falha.fator_seguranca_rankine(
            (20.0, 0.0, -120.0),
            Sut_MPa=100.0,
        )
        self.assertFalse(rankine.completo)
        self.assertIsNone(rankine.fator_seguranca)

    def test_zero_state_has_infinite_safety(self):
        self.assertTrue(math.isinf(falha.fator_seguranca_von_mises(0.0, 250.0)))
        self.assertTrue(
            math.isinf(falha.fator_seguranca_tresca((0.0, 0.0, 0.0), 250.0))
        )
        rankine = falha.fator_seguranca_rankine((0.0, 0.0, 0.0), 400.0)
        self.assertTrue(rankine.completo)
        self.assertTrue(math.isinf(rankine.fator_seguranca))


if __name__ == "__main__":
    unittest.main()
