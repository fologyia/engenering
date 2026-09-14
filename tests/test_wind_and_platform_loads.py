"""Vento pela NBR 6123 e ações/geometria de plataformas de acesso.

Os valores de S2 são conferidos contra a Tabela 2 da NBR 6123 (que é a
Tabela 1 aplicada), e os demais contra a definição direta de cada fórmula.
"""

import math
import unittest

from core import platform_loads as pl
from core import wind_load as vento


class FatorS2Tests(unittest.TestCase):
    def test_reproduz_a_tabela_2(self):
        # (z, categoria, classe, S2 tabelado)
        casos = [
            (5.0, "II", "A", 0.94),
            (10.0, "IV", "B", 0.83),
            (20.0, "III", "A", 1.01),
            (100.0, "I", "C", 1.25),
            (50.0, "V", "C", 0.89),
            (10.0, "II", "A", 1.00),
            (30.0, "IV", "A", 0.98),
        ]
        for z, categoria, classe, esperado in casos:
            with self.subTest(z=z, categoria=categoria, classe=classe):
                self.assertAlmostEqual(vento.fator_s2(z, categoria, classe), esperado, delta=0.006)

    def test_abaixo_de_5_m_e_acima_da_altura_gradiente_saturam(self):
        self.assertEqual(vento.fator_s2(1.0, "II", "A"), vento.fator_s2(5.0, "II", "A"))
        self.assertEqual(vento.fator_s2(900.0, "III", "B"), vento.fator_s2(350.0, "III", "B"))

    def test_categoria_ou_classe_invalida(self):
        with self.assertRaises(ValueError):
            vento.fator_s2(10.0, "VI", "A")
        with self.assertRaises(ValueError):
            vento.fator_s2(10.0, "II", "D")


class FatorS1Tests(unittest.TestCase):
    def test_plano_vale_e_talude(self):
        self.assertEqual(vento.fator_s1("plano"), 1.0)
        self.assertEqual(vento.fator_s1("vale"), 0.9)
        # θ = 10°, z = 5 m, d = 50 m: 1 + (2,5 − 0,1)·tan 7°
        esperado = 1.0 + 2.4 * math.tan(math.radians(7.0))
        self.assertAlmostEqual(
            vento.fator_s1("talude", inclinacao_graus=10.0, z_m=5.0, d_m=50.0), esperado
        )
        # θ ≥ 45°: 1 + (2,5 − z/d)·0,31
        self.assertAlmostEqual(
            vento.fator_s1("morro", inclinacao_graus=60.0, z_m=0.0, d_m=30.0), 1.775
        )
        # Nunca abaixo de 1,0 no topo, mesmo alto acima do terreno.
        self.assertEqual(vento.fator_s1("talude", inclinacao_graus=10.0, z_m=200.0, d_m=50.0), 1.0)
        self.assertEqual(vento.fator_s1("talude", inclinacao_graus=2.0), 1.0)

    def test_faixas_intermediarias_interpolam_de_forma_continua(self):
        em_6 = vento.fator_s1("talude", inclinacao_graus=6.0, z_m=0.0, d_m=10.0)
        em_45 = vento.fator_s1("talude", inclinacao_graus=45.0, z_m=0.0, d_m=10.0)
        em_17 = vento.fator_s1("talude", inclinacao_graus=17.0, z_m=0.0, d_m=10.0)
        quase_6 = vento.fator_s1("talude", inclinacao_graus=5.999, z_m=0.0, d_m=10.0)
        quase_45 = vento.fator_s1("talude", inclinacao_graus=44.999, z_m=0.0, d_m=10.0)
        self.assertAlmostEqual(quase_6, em_6, places=3)
        self.assertAlmostEqual(quase_45, em_45, places=3)
        self.assertLess(em_17, em_45)

    def test_relevo_desconhecido(self):
        with self.assertRaises(ValueError):
            vento.fator_s1("montanha")


class VentoTests(unittest.TestCase):
    def test_calculo_completo(self):
        resultado = vento.calcular_vento(
            35.0,
            s1=1.0,
            categoria="IV",
            classe="A",
            altura_m=6.0,
            grupo_s3=3,
            coeficiente_arrasto=2.0,
            area_efetiva_m2=1.2,
            largura_exposta_m=0.2032,
        )
        s2 = 0.86 * 1.0 * (6.0 / 10.0) ** 0.12
        vk = 35.0 * s2 * 0.95
        self.assertAlmostEqual(resultado.s2, s2)
        self.assertAlmostEqual(resultado.vk_m_s, vk)
        self.assertAlmostEqual(resultado.pressao_N_m2, 0.613 * vk**2)
        self.assertAlmostEqual(resultado.forca_kN, 2.0 * 0.613 * vk**2 * 1.2 / 1e3)
        self.assertAlmostEqual(resultado.carga_linear_kN_m, 2.0 * 0.613 * vk**2 * 0.2032 / 1e3)
        self.assertTrue(any("V_k" in linha for linha in resultado.memoria))
        self.assertTrue(any("F = C_f" in linha for linha in resultado.memoria))

    def test_s3_informado_sobrepoe_o_grupo(self):
        resultado = vento.calcular_vento(40.0, s3=1.0, grupo_s3=5)
        self.assertEqual(resultado.s3, 1.0)
        self.assertIsNone(resultado.forca_kN)
        self.assertIsNone(resultado.carga_linear_kN_m)

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            vento.calcular_vento(0.0)
        with self.assertRaises(ValueError):
            vento.calcular_vento(30.0, grupo_s3=9)
        with self.assertRaises(ValueError):
            vento.calcular_vento(30.0, area_efetiva_m2=-1.0)


class GuardaCorpoTests(unittest.TestCase):
    def test_esforcos_no_montante(self):
        esforcos = pl.esforcos_no_montante(1.0, 1.10, 1.5)
        self.assertAlmostEqual(esforcos.forca_horizontal_kN, 1.5)
        self.assertAlmostEqual(esforcos.momento_base_kNm, 1.65)
        self.assertAlmostEqual(esforcos.momento_concentrado_kNm, 1.10)
        self.assertAlmostEqual(esforcos.momento_governante_kNm, 1.65)
        with self.assertRaises(ValueError):
            pl.esforcos_no_montante(1.0, 0.0, 1.5)

    def test_impacto(self):
        self.assertAlmostEqual(pl.carga_com_impacto(10.0, 0.2), 12.0)
        self.assertEqual(pl.COEFICIENTES_IMPACTO["Máquinas leves (motores, eixos)"], 0.20)

    def test_geometria_do_guarda_corpo_com_criterio_do_cliente(self):
        itens = pl.verificar_guarda_corpo(1.10, 0.20, 0.40)
        self.assertTrue(all(item.atende for item in itens))
        mais_alto = pl.verificar_guarda_corpo(1.10, 0.15, 0.45, altura_minima_m=1.30)
        self.assertEqual([item.atende for item in mais_alto], [False, False, False])
        self.assertIn("critério do projeto", mais_alto[0].fonte)

    def test_passarela_e_escada(self):
        self.assertTrue(pl.verificar_passarela(0.80)[0].atende)
        self.assertFalse(pl.verificar_passarela(0.50)[0].atende)
        itens = pl.verificar_escada(180.0, 270.0, altura_entre_patamares_m=2.9, largura_util_m=0.8)
        self.assertEqual(len(itens), 4)
        self.assertTrue(all(item.atende for item in itens))
        fora = pl.verificar_escada(200.0, 200.0, altura_entre_patamares_m=3.5)
        self.assertFalse(fora[0].atende)  # 2h + b = 600 < 630
        self.assertTrue(fora[1].atende)  # 45° ainda dentro
        self.assertFalse(fora[2].atende)


if __name__ == "__main__":
    unittest.main()
