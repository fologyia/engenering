import math
import unittest

from core import load_combinations as comb
from core import steel_connections as lig
from core import steel_member_design as barras
from core import steel_sections as secoes
from core import structural_2d as estrut


class SteelSectionsTests(unittest.TestCase):
    def test_i_section_properties(self):
        perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)
        self.assertGreater(perfil.area_mm2, 0)
        self.assertGreater(perfil.ix_mm4, perfil.iy_mm4)
        self.assertGreater(perfil.zx_mm3, perfil.sx_mm3)
        self.assertAlmostEqual(
            perfil.massa_kg_m,
            perfil.area_mm2 * 0.00785,
        )

    def test_circular_tube_is_axisymmetric(self):
        perfil = secoes.tubo_circular("TC", 100, 5)
        self.assertAlmostEqual(perfil.ix_mm4, perfil.iy_mm4)
        self.assertAlmostEqual(perfil.zx_mm3, perfil.zy_mm3)
        self.assertAlmostEqual(perfil.j_mm4, 2 * perfil.ix_mm4)

    def test_catalog_has_multiple_families(self):
        tabela = secoes.catalogo_dataframe()
        self.assertGreaterEqual(len(tabela), 30)
        self.assertGreaterEqual(tabela["familia"].nunique(), 4)


class SteelMemberTests(unittest.TestCase):
    def setUp(self):
        self.perfil = secoes.perfil_i_simetrico("I", 200, 100, 6, 10)

    def test_tension_uses_lowest_limit_state(self):
        resultado = barras.verificar_tracao(
            self.perfil, 250, 400, self.perfil.area_mm2 * 0.8, 0.9, 100_000
        )
        self.assertEqual(
            resultado.resistencia_governante_N,
            min(
                resultado.resistencia_escoamento_N,
                resultado.resistencia_ruptura_N,
            ),
        )

    def test_longer_column_has_lower_resistance(self):
        curta = barras.verificar_compressao(
            self.perfil, 250, 200_000, 2_000, 1, 1, 1, 100_000
        )
        longa = barras.verificar_compressao(
            self.perfil, 250, 200_000, 6_000, 1, 1, 1, 100_000
        )
        self.assertLess(longa.resistencia_N, curta.resistencia_N)
        self.assertGreater(longa.esbeltez_y, curta.esbeltez_y)

    def test_ltb_critical_moment_reduces_with_length(self):
        curto = barras.momento_critico_ltb(
            self.perfil, 200_000, 77_000, 2_000
        )
        longo = barras.momento_critico_ltb(
            self.perfil, 200_000, 77_000, 6_000
        )
        self.assertLess(longo, curto)

    def test_interaction_equation(self):
        resultado = barras.verificar_interacao(
            200, 1_000, 300, 1_000
        )
        self.assertAlmostEqual(resultado.indice_interacao, 0.2 + 8 / 9 * 0.3)

    def test_simply_supported_point_load_deflection(self):
        resultado = barras.verificar_deflexao_viga(
            self.perfil,
            200_000,
            3_000,
            0,
            10_000,
            "Biapoiada",
            300,
        )
        esperado = 10_000 * 3_000**3 / (
            48 * 200_000 * self.perfil.ix_mm4
        )
        self.assertAlmostEqual(resultado.deflexao_total_mm, esperado)


class LoadCombinationTests(unittest.TestCase):
    def test_generates_leading_variable_combinations(self):
        acoes = [
            comb.AcaoEstrutural("G", "Permanente", 10, 0, 5, 1.4),
            comb.AcaoEstrutural("Q", "Variável", 5, 0, 3, 1.4, 0.7, 0.5, 0.3),
            comb.AcaoEstrutural("W", "Variável", 0, 4, 2, 1.4, 0.6, 0.3, 0.0),
        ]
        resultados = comb.gerar_combinacoes(acoes)
        self.assertEqual(len(resultados), 7)
        elu_q = next(r for r in resultados if r.nome == "ELU — Q principal")
        self.assertAlmostEqual(elu_q.n_kN, 1.4 * 10 + 1.4 * 5)
        self.assertAlmostEqual(elu_q.v_kN, 1.4 * 0.6 * 4)

    def test_quasi_permanent_uses_psi2(self):
        acoes = [
            comb.AcaoEstrutural("G", "Permanente", 10, 0, 0, 1.4),
            comb.AcaoEstrutural("Q", "Variável", 5, 0, 0, 1.4, 0.7, 0.5, 0.3),
        ]
        resultado = comb.gerar_combinacoes(acoes)[-1]
        self.assertAlmostEqual(resultado.n_kN, 11.5)


class SteelConnectionTests(unittest.TestCase):
    def test_bolt_group_capacity_scales_with_bolt_count(self):
        base = dict(
            area_parafuso_mm2=58,
            fu_parafuso_MPa=800,
            coeficiente_cisalhamento=0.48,
            coeficiente_tracao=0.75,
            phi_parafuso=0.75,
            numero_planos_corte=1,
            forca_cortante_N=50_000,
            forca_tracao_N=20_000,
            espessura_chapa_mm=10,
            fu_chapa_MPa=400,
            diametro_parafuso_mm=10,
            distancia_livre_carga_mm=15,
            coeficiente_contato_lc=1.2,
            coeficiente_limite_contato=2.4,
            phi_contato=0.75,
            pre_tensao_parafuso_N=20_000,
            coeficiente_atrito=0.3,
            numero_interfaces_atrito=1,
            phi_deslizamento=1.0,
        )
        dois = lig.verificar_ligacao_parafusada(numero_parafusos=2, **base)
        quatro = lig.verificar_ligacao_parafusada(numero_parafusos=4, **base)
        self.assertAlmostEqual(
            quatro.resistencia_cisalhamento_parafusos_N,
            2 * dois.resistencia_cisalhamento_parafusos_N,
        )

    def test_weld_strength(self):
        resultado = lig.verificar_solda_filete(6, 200, 490, 0.6, 0.75, 50_000)
        self.assertAlmostEqual(resultado.area_efetiva_mm2, 0.707 * 6 * 200)
        self.assertGreater(resultado.resistencia_N, 0)


class StructuralSolverTests(unittest.TestCase):
    def test_single_truss_bar(self):
        nos = [
            estrut.NoTrelica(1, 0, 0, True, True),
            estrut.NoTrelica(2, 1_000, 0, False, True, 10_000, 0),
        ]
        elementos = [estrut.ElementoTrelica(1, 1, 2, 100, 200_000)]
        resultado = estrut.analisar_trelica(nos, elementos)
        self.assertAlmostEqual(resultado.deslocamentos_nodais[1]["ux_mm"], 0.5)
        self.assertAlmostEqual(resultado.esforcos_elementos[0]["normal_N"], 10_000)
        self.assertAlmostEqual(resultado.reacoes_nodais[0]["rx_N"], -10_000)

    def test_cantilever_frame_tip_load(self):
        nos = [
            estrut.NoPortico(1, 0, 0, True, True, True),
            estrut.NoPortico(2, 1_000, 0, False, False, False, 0, -1_000, 0),
        ]
        elementos = [
            estrut.ElementoPortico(1, 1, 2, 1_000, 1_000_000, 200_000)
        ]
        resultado = estrut.analisar_portico(nos, elementos)
        uy = resultado.deslocamentos_nodais[1]["uy_mm"]
        esperado = -1_000 * 1_000**3 / (3 * 200_000 * 1_000_000)
        self.assertAlmostEqual(uy, esperado)
        self.assertAlmostEqual(resultado.reacoes_nodais[0]["ry_N"], 1_000)

    def test_simply_supported_beam_uniform_load(self):
        nos = [
            estrut.NoPortico(1, 0, 0, True, True, False),
            estrut.NoPortico(2, 1_000, 0, False, True, False),
        ]
        elementos = [
            estrut.ElementoPortico(
                1, 1, 2, 1_000, 1_000_000, 200_000, -1.0
            )
        ]
        resultado = estrut.analisar_portico(nos, elementos)
        self.assertAlmostEqual(resultado.reacoes_nodais[0]["ry_N"], 500)
        self.assertAlmostEqual(resultado.reacoes_nodais[1]["ry_N"], 500)

    def test_unstable_model_is_rejected(self):
        with self.assertRaises(ValueError):
            estrut.analisar_trelica(
                [
                    estrut.NoTrelica(1, 0, 0),
                    estrut.NoTrelica(2, 1_000, 0, fx_N=1_000),
                ],
                [estrut.ElementoTrelica(1, 1, 2, 100, 200_000)],
            )


if __name__ == "__main__":
    unittest.main()
