import math
import unittest

from core import column_buckling as flambagem
from core import steel_sections as secoes


class GeometriaColunaTests(unittest.TestCase):
    def test_retangular_raio_giracao(self):
        geo = flambagem.geometria_retangular(50.0, 100.0)
        # r = h/sqrt(12) para o lado usado como espessura do eixo correspondente
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 100.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.raio_giracao_y_mm, 50.0 / math.sqrt(12.0))
        self.assertAlmostEqual(geo.area_mm2, 5_000.0)

    def test_circular_macica_area_e_raio(self):
        geo = flambagem.geometria_circular_macica(40.0)
        area_esperada = math.pi * 40.0**2 / 4.0
        self.assertAlmostEqual(geo.area_mm2, area_esperada)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, 40.0 / 4.0)

    def test_circular_vazada_rejeita_diametro_interno_maior(self):
        with self.assertRaises(ValueError):
            flambagem.geometria_circular_vazada(40.0, 50.0)

    def test_circular_vazada_area_positiva(self):
        geo = flambagem.geometria_circular_vazada(60.0, 40.0)
        area_esperada = math.pi / 4.0 * (60.0**2 - 40.0**2)
        self.assertAlmostEqual(geo.area_mm2, area_esperada)

    def test_perfil_catalogo_usa_rx_ry(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)
        geo = flambagem.geometria_perfil_catalogo(perfil)
        self.assertAlmostEqual(geo.raio_giracao_x_mm, perfil.rx_mm)
        self.assertAlmostEqual(geo.raio_giracao_y_mm, perfil.ry_mm)

    def test_direta_replica_mesmo_raio_quando_nao_informado(self):
        geo = flambagem.geometria_direta(1_000.0, 12.0)
        self.assertEqual(geo.raio_giracao_x_mm, geo.raio_giracao_y_mm)


class VerificarFlambagemTests(unittest.TestCase):
    def setUp(self):
        self.geometria = flambagem.geometria_circular_macica(50.0)

    def _verificar(self, comprimento_mm, **overrides):
        parametros = dict(
            geometria=self.geometria,
            comprimento_mm=comprimento_mm,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=200_000.0,
            escoamento_MPa=250.0,
            forca_solicitante_N=10_000.0,
            fator_seguranca_desejado=2.0,
        )
        parametros.update(overrides)
        return flambagem.verificar_flambagem(**parametros)

    def test_coluna_longa_usa_euler(self):
        resultado = self._verificar(3_000.0)
        self.assertIn("Euler", resultado.regime)
        self.assertGreaterEqual(resultado.esbeltez_governante, resultado.esbeltez_transicao)
        self.assertAlmostEqual(resultado.tensao_critica_MPa, resultado.carga_critica_euler_N / self.geometria.area_mm2)

    def test_coluna_curta_usa_johnson(self):
        resultado = self._verificar(200.0)
        self.assertIn("Johnson", resultado.regime)
        self.assertLess(resultado.esbeltez_governante, resultado.esbeltez_transicao)
        # Johnson nunca deve prever tensão crítica acima do escoamento.
        self.assertLessEqual(resultado.tensao_critica_MPa, 250.0)

    def test_coluna_mais_longa_tem_carga_critica_menor(self):
        curta = self._verificar(500.0)
        longa = self._verificar(3_000.0)
        self.assertLess(longa.carga_critica_N, curta.carga_critica_N)

    def test_engastada_livre_reduz_carga_critica_frente_a_biapoiada(self):
        biapoiada = self._verificar(2_000.0, kx=1.0, ky=1.0)
        engastada_livre = self._verificar(2_000.0, kx=2.0, ky=2.0)
        self.assertLess(engastada_livre.carga_critica_N, biapoiada.carga_critica_N)

    def test_fator_seguranca_infinito_sem_solicitacao(self):
        resultado = self._verificar(2_000.0, forca_solicitante_N=0.0)
        self.assertTrue(math.isinf(resultado.fator_seguranca))
        self.assertEqual(resultado.utilizacao, 0.0)

    def test_eixo_governante_e_o_mais_esbelto(self):
        geometria = flambagem.geometria_retangular(20.0, 80.0)
        resultado = flambagem.verificar_flambagem(
            geometria=geometria,
            comprimento_mm=2_000.0,
            kx=1.0,
            ky=1.0,
            modulo_elasticidade_MPa=200_000.0,
            escoamento_MPa=250.0,
            forca_solicitante_N=5_000.0,
        )
        self.assertEqual(resultado.eixo_governante, "y")
        self.assertGreater(resultado.esbeltez_y, resultado.esbeltez_x)

    def test_transicao_depende_de_e_e_sy(self):
        resultado = self._verificar(2_000.0, escoamento_MPa=500.0)
        self.assertAlmostEqual(
            resultado.esbeltez_transicao,
            math.sqrt(2.0 * math.pi**2 * 200_000.0 / 500.0),
        )

    def test_rejeita_entradas_nao_positivas(self):
        with self.assertRaises(ValueError):
            self._verificar(0.0)
        with self.assertRaises(ValueError):
            self._verificar(2_000.0, modulo_elasticidade_MPa=-1.0)
        with self.assertRaises(ValueError):
            self._verificar(2_000.0, forca_solicitante_N=-1.0)


if __name__ == "__main__":
    unittest.main()
