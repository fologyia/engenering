import math
import unittest

from core import additional_load_models as modelos
from core import materials


class AdditionalLoadModelsTests(unittest.TestCase):
    def test_hollow_shaft_matches_section_properties(self):
        de, di = 40.0, 20.0
        estado = modelos.eixo_circular_vazado(
            de, di, 10_000.0, 200_000.0, 100_000.0, "tracionada"
        )
        area = math.pi * (de**2 - di**2) / 4.0
        inercia = math.pi * (de**4 - di**4) / 64.0
        self.assertAlmostEqual(
            estado.sigma_x, 10_000.0 / area + 200_000.0 * (de / 2) / inercia
        )
        self.assertAlmostEqual(
            estado.tau_xy, 100_000.0 * (de / 2) / (2.0 * inercia)
        )

    def test_hollow_shaft_rejects_invalid_diameters(self):
        with self.assertRaises(ValueError):
            modelos.eixo_circular_vazado(20, 20, 0, 0, 0)

    def test_biaxial_bending_signs(self):
        estado = modelos.secao_retangular_flexao_biaxial(
            largura_mm=40.0,
            altura_mm=60.0,
            coordenada_y_mm=30.0,
            coordenada_z_mm=20.0,
            forca_axial_N=0.0,
            momento_y_Nmm=100_000.0,
            momento_z_Nmm=200_000.0,
        )
        iy = 60.0 * 40.0**3 / 12.0
        iz = 40.0 * 60.0**3 / 12.0
        esperado = 100_000.0 * 20.0 / iy - 200_000.0 * 30.0 / iz
        self.assertAlmostEqual(estado.sigma_x, esperado)

    def test_i_section_inertia_and_surface_stress(self):
        estado = modelos.secao_i_flexao(
            altura_total_mm=200.0,
            largura_mesa_mm=100.0,
            espessura_mesa_mm=10.0,
            espessura_alma_mm=6.0,
            coordenada_y_mm=100.0,
            forca_axial_N=0.0,
            momento_fletor_Nmm=5_000_000.0,
        )
        inercia = (100.0 * 200.0**3 - 94.0 * 180.0**3) / 12.0
        self.assertAlmostEqual(
            estado.sigma_x, -5_000_000.0 * 100.0 / inercia
        )

    def test_pin_double_shear(self):
        estado = modelos.pino_cisalhamento(
            forca_N=20_000.0,
            diametro_mm=10.0,
            numero_pinos=2,
            numero_planos_corte=2,
        )
        esperado = 20_000.0 / (4.0 * math.pi * 10.0**2 / 4.0)
        self.assertAlmostEqual(estado.tau_xy, esperado)

    def test_thin_tube_combines_pressure_axial_and_torsion(self):
        estado = modelos.tubo_fino_pressao_axial_torcao(
            pressao_MPa=2.0,
            diametro_medio_mm=500.0,
            espessura_mm=5.0,
            extremidades_fechadas=True,
            forca_axial_N=10_000.0,
            torque_Nmm=1_000_000.0,
        )
        self.assertAlmostEqual(estado.sigma_y, 100.0)
        self.assertAlmostEqual(
            estado.sigma_x, 50.0 + 10_000.0 / (math.pi * 500.0 * 5.0)
        )
        self.assertAlmostEqual(
            estado.tau_xy, 2_000_000.0 / (math.pi * 500.0**2 * 5.0)
        )

    def test_thin_sphere_is_equibiaxial(self):
        estado = modelos.vaso_esferico_parede_fina(2.0, 500.0, 5.0)
        self.assertAlmostEqual(estado.sigma_x, 50.0)
        self.assertAlmostEqual(estado.sigma_y, 50.0)
        self.assertEqual(estado.tau_xy, 0.0)


class ExpandedMaterialsTests(unittest.TestCase):
    def test_material_database_is_expanded_and_valid(self):
        df = materials.carregar_materiais()
        self.assertGreaterEqual(len(df), 30)
        self.assertIn("Aço inoxidável duplex 2205 solubilizado", set(df["nome"]))
        self.assertIn("Alumínio 7075-T6 chapa", set(df["nome"]))
        self.assertIn(
            "Ferro fundido nodular ASTM A536 65-45-12", set(df["nome"])
        )


if __name__ == "__main__":
    unittest.main()
