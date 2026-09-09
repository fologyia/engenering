import math
import unittest

from core import project_assistant as projetos
from core import unit_converter as unidades


class UnitConverterTests(unittest.TestCase):
    def test_force_and_stress_conversions(self):
        self.assertAlmostEqual(unidades.converter(1, "Força", "kN", "N"), 1000)
        self.assertAlmostEqual(
            unidades.converter(1, "Tensão e pressão", "ksi", "MPa"),
            unidades.MPA_PER_KSI,
        )

    def test_temperature_conversions(self):
        self.assertAlmostEqual(
            unidades.converter(32, "Temperatura", "°F", "°C"), 0
        )
        self.assertAlmostEqual(
            unidades.converter(100, "Temperatura", "°C", "°F"), 212
        )
        self.assertAlmostEqual(
            unidades.converter(273.15, "Temperatura", "K", "°C"), 0
        )

    def test_round_trip_for_every_unit(self):
        for categoria, itens in unidades.CATEGORIAS.items():
            origem = next(iter(itens))
            for destino in itens:
                convertido = unidades.converter(
                    12.345, categoria, origem, destino
                )
                retorno = unidades.converter(
                    convertido, categoria, destino, origem
                )
                self.assertAlmostEqual(retorno, 12.345, places=8)

    def test_invalid_or_non_finite_input_is_rejected(self):
        with self.assertRaises(ValueError):
            unidades.converter(math.inf, "Força", "N", "kN")
        with self.assertRaises(ValueError):
            unidades.converter(1, "inexistente", "N", "kN")


class ProjectAssistantTests(unittest.TestCase):
    def test_loads_are_prepared_before_static_check(self):
        rota = projetos.recomendar_rota(
            projetos.OBJETIVOS[1], projetos.DADOS_DISPONIVEIS[0]
        )
        self.assertEqual(rota.chave, "cargas")
        self.assertEqual(
            projetos.sequencia_recomendada(
                projetos.OBJETIVOS[1], projetos.DADOS_DISPONIVEIS[0]
            ),
            ["casos_carga", "cargas", "estatica", "analise_sensibilidade"],
        )

    def test_known_cycle_routes_to_fatigue(self):
        rota = projetos.recomendar_rota(
            projetos.OBJETIVOS[3], projetos.DADOS_DISPONIVEIS[2]
        )
        self.assertEqual(rota.chave, "fadiga")

    def test_unknown_problem_uses_component_as_hint(self):
        rota = projetos.recomendar_rota(
            projetos.OBJETIVOS[6],
            projetos.DADOS_DISPONIVEIS[5],
            projetos.COMPONENTES[3],
        )
        self.assertEqual(rota.chave, "parafusos")

    def test_cycle_components(self):
        media, alternada = projetos.calcular_tensoes_ciclo(-20, 100)
        self.assertEqual(media, 40)
        self.assertEqual(alternada, 60)
        with self.assertRaises(ValueError):
            projetos.calcular_tensoes_ciclo(100, -20)

    def test_rotas_include_casos_carga_and_sensibilidade(self):
        self.assertIn("casos_carga", projetos.ROTAS)
        self.assertIn("analise_sensibilidade", projetos.ROTAS)
        self.assertEqual(
            projetos.ROTAS["casos_carga"].pagina, "app_pages/casos_carga.py"
        )
        self.assertEqual(
            projetos.ROTAS["analise_sensibilidade"].pagina,
            "app_pages/analise_sensibilidade.py",
        )

    def test_sequencia_recomendada_sempre_comeca_e_termina_no_mesmo_par(self):
        for objetivo in projetos.OBJETIVOS[:6]:
            for dados in projetos.DADOS_DISPONIVEIS:
                try:
                    sequencia = projetos.sequencia_recomendada(objetivo, dados)
                except ValueError:
                    continue
                self.assertEqual(sequencia[0], "casos_carga")
                self.assertEqual(sequencia[-1], "analise_sensibilidade")
                self.assertEqual(len(sequencia), len(set(sequencia)))


if __name__ == "__main__":
    unittest.main()
