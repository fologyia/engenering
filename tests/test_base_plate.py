"""Placa de base pelo AISC Design Guide 1, conferida contra os exemplos do guia.

Os exemplos 4.1 (compressão), 4.4 (momento pequeno) e 4.5 (momento grande)
da 2ª edição usam a coluna W12×96 (d = 12,7 in, b_f = 12,2 in, t_f = 0,9 in),
f_y = 36 ksi, e são convertidos para SI aqui.
"""

import math
import unittest

from core import base_plate as bp

IN = 25.4
KIP = 4_448.22
KSI = 6.894757
W12X96 = {
    "profundidade_coluna_mm": 12.7 * IN,
    "largura_mesa_mm": 12.2 * IN,
    "espessura_mesa_mm": 0.9 * IN,
    "fy_placa_MPa": 36 * KSI,
}


class ExemplosDoDesignGuideTests(unittest.TestCase):
    def test_exemplo_4_1_compressao_centrada(self):
        resultado = bp.verificar_placa_base(
            **W12X96,
            comprimento_placa_mm=22 * IN,
            largura_placa_mm=20 * IN,
            espessura_placa_mm=1.75 * IN,
            fck_MPa=3 * KSI,
            razao_areas_a2_a1=1.0,
            forca_axial_N=700 * KIP,
        )
        self.assertIn("compressão centrada", resultado.caso)
        self.assertAlmostEqual(resultado.lambda_n_linha_mm / IN, 3.11, delta=0.01)
        self.assertAlmostEqual(resultado.espessura_requerida_mm / IN, 1.60, delta=0.01)
        self.assertLess(resultado.utilizacao_contato, 1.0)
        self.assertTrue(resultado.atende)
        self.assertEqual(resultado.tracao_chumbadores_N, 0.0)

    def test_exemplo_4_4_momento_pequeno(self):
        resultado = bp.verificar_placa_base(
            **W12X96,
            comprimento_placa_mm=19 * IN,
            largura_placa_mm=19 * IN,
            espessura_placa_mm=1.5 * IN,
            fck_MPa=4 * KSI,
            razao_areas_a2_a1=4.0,
            forca_axial_N=376 * KIP,
            momento_Nmm=2_040 * KIP * IN,
            distancia_chumbador_mm=8 * IN,
        )
        self.assertIn("momento pequeno", resultado.caso)
        self.assertAlmostEqual(resultado.excentricidade_mm / IN, 5.43, delta=0.01)
        self.assertAlmostEqual(resultado.excentricidade_critica_mm / IN, 7.26, delta=0.01)
        self.assertAlmostEqual(resultado.comprimento_contato_mm / IN, 8.15, delta=0.01)
        self.assertAlmostEqual(resultado.pressao_atuante_MPa / KSI, 2.43, delta=0.01)
        self.assertAlmostEqual(resultado.espessura_requerida_mm / IN, 1.35, delta=0.01)
        self.assertEqual(resultado.tracao_chumbadores_N, 0.0)

    def test_exemplo_4_5_momento_grande(self):
        resultado = bp.verificar_placa_base(
            **W12X96,
            comprimento_placa_mm=19 * IN,
            largura_placa_mm=19 * IN,
            espessura_placa_mm=2.0 * IN,
            fck_MPa=4 * KSI,
            razao_areas_a2_a1=4.0,
            forca_axial_N=376 * KIP,
            momento_Nmm=4_020 * KIP * IN,
            distancia_chumbador_mm=8 * IN,
            diametro_chumbador_mm=1.25 * IN,
            fu_chumbador_MPa=58 * KSI,
        )
        self.assertIn("momento grande", resultado.caso)
        self.assertAlmostEqual(resultado.comprimento_contato_mm / IN, 5.72, delta=0.01)
        self.assertAlmostEqual(resultado.tracao_chumbadores_N / KIP, 104.0, delta=0.5)
        self.assertAlmostEqual(resultado.espessura_requerida_apoio_mm / IN, 1.82, delta=0.01)
        self.assertAlmostEqual(resultado.espessura_requerida_tracao_mm / IN, 1.19, delta=0.01)
        # φ·0,75·F_u·A_b = 0,75 × 0,75 × 58 × 1,227 = 40,0 kip por chumbador.
        self.assertAlmostEqual(resultado.resistencia_tracao_chumbador_N / KIP, 40.0, delta=0.1)
        self.assertAlmostEqual(resultado.tracao_por_chumbador_N / KIP, 52.0, delta=0.3)
        self.assertEqual(resultado.modo_governante, "Tração do chumbador")
        self.assertFalse(resultado.atende)
        self.assertTrue(any("Ancoragem no concreto" in aviso for aviso in resultado.avisos))


class CasosDeBordaTests(unittest.TestCase):
    def _base(self, **extras):
        parametros = {
            "profundidade_coluna_mm": 203.0,
            "largura_mesa_mm": 133.0,
            "espessura_mesa_mm": 8.0,
            "comprimento_placa_mm": 350.0,
            "largura_placa_mm": 250.0,
            "espessura_placa_mm": 16.0,
            "fy_placa_MPa": 250.0,
            "fck_MPa": 25.0,
            "forca_axial_N": 100e3,
        }
        parametros.update(extras)
        return bp.verificar_placa_base(**parametros)

    def test_arrancamento_divide_a_tracao_e_soma_o_momento(self):
        resultado = self._base(forca_axial_N=-40e3, momento_Nmm=10e6, distancia_chumbador_mm=125.0)
        self.assertIn("arrancamento", resultado.caso)
        # |P|/2 + M/(2f) = 20 + 10e6/250 = 20 + 40 kN
        self.assertAlmostEqual(resultado.tracao_chumbadores_N, 60e3)
        self.assertAlmostEqual(resultado.tracao_por_chumbador_N, 30e3)
        self.assertGreater(resultado.espessura_requerida_tracao_mm, 0.0)
        self.assertEqual(resultado.pressao_atuante_MPa, 0.0)

    def test_utilizacao_da_placa_cresce_com_o_quadrado_da_espessura(self):
        grossa = self._base(espessura_placa_mm=20.0)
        fina = self._base(espessura_placa_mm=10.0)
        self.assertAlmostEqual(fina.utilizacao_placa, 4.0 * grossa.utilizacao_placa)

    def test_cortante_entra_na_interacao(self):
        sem = self._base(forca_axial_N=-40e3, cortante_N=0.0)
        # A redução de J3.7 só começa quando f_rv > 0,3·φ·F_nv (= 40,5 MPa aqui):
        # 40 kN em 4 chumbadores dá 35 MPa e não reduz; 80 kN dá 70 MPa e reduz.
        leve = self._base(forca_axial_N=-40e3, cortante_N=40e3)
        com = self._base(forca_axial_N=-40e3, cortante_N=80e3)
        self.assertEqual(leve.utilizacao_interacao_chumbador, sem.utilizacao_interacao_chumbador)
        self.assertGreater(com.utilizacao_interacao_chumbador, sem.utilizacao_interacao_chumbador)
        self.assertTrue(any("Cortante relevante" in aviso for aviso in com.avisos))

    def test_momento_grande_demais_para_a_placa(self):
        with self.assertRaises(ValueError) as contexto:
            self._base(momento_Nmm=400e6)
        self.assertIn("Placa insuficiente", str(contexto.exception))

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            self._base(comprimento_placa_mm=150.0)  # menor que d
        with self.assertRaises(ValueError):
            self._base(distancia_chumbador_mm=200.0)  # fora da placa
        with self.assertRaises(ValueError):
            self._base(numero_chumbadores=2, chumbadores_lado_tracionado=3)
        with self.assertRaises(ValueError):
            self._base(forca_axial_N=math.nan)

    def test_confinamento_limitado_a_dois(self):
        pouco = self._base(razao_areas_a2_a1=4.0)
        muito = self._base(razao_areas_a2_a1=16.0)
        self.assertAlmostEqual(pouco.pressao_maxima_MPa, muito.pressao_maxima_MPa)
        self.assertAlmostEqual(pouco.pressao_maxima_MPa, 0.65 * 0.85 * 25.0 * 2.0)


if __name__ == "__main__":
    unittest.main()
