import unittest

from core import fatigue_report


class FatigueReportTests(unittest.TestCase):
    def test_pdf_report_is_generated_with_current_calculation(self):
        dados = {
            "projeto": "Eixo de teste",
            "responsavel": "Equipe",
            "modelo": "norton",
            "fonte": "Norton, Projeto de Máquinas, 4ª ed., cap. 6",
            "material": "Aço - entrada manual",
            "Sut": 600.0,
            "Sy": 400.0,
            "tipo_carga": "Flexão",
            "diametro_mm": 20.0,
            "temperatura_entrada": 500.0,
            "unidade_temperatura": "°F",
            "temperatura_c": 260.0,
            "temperatura_f": 500.0,
            "Ctemp": 0.71,
            "Se_linha": 300.0,
            "Se": 136.1,
            "fatores": {
                "Carregamento": 1.0,
                "Tamanho": 0.889,
                "Superfície": 0.828,
                "Temperatura": 0.71,
                "Confiabilidade": 0.868,
            },
            "modo_entalhe": "Sem entalhe",
            "sigma_a_nom": 200.0,
            "sigma_a": 200.0,
            "sigma_m": 100.0,
            "sigma_a_eq": 240.0,
            "Sm": 540.0,
            "n_goodman": 0.61,
            "n_soderberg": 0.58,
            "n_escoamento": 1.33,
            "resultado_vida": "45.000 ciclos",
        }
        linhas = [
            {
                "Grupo": "Condição",
                "Grandeza": "Temperatura de operação",
                "Símbolo": "T",
                "Valor": "260,00",
                "Unidade": "°C",
                "Observação": "Entrada: 500,00 °F",
            }
        ]

        pdf = fatigue_report.gerar_memorial_fadiga_pdf(dados, linhas)

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 5_000)


if __name__ == "__main__":
    unittest.main()