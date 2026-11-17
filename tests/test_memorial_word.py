import copy
import io
import unittest
from zipfile import ZipFile

from docx import Document

from core import memorial_word

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class MemorialWordTests(unittest.TestCase):
    def setUp(self):
        self.dados = {
            "projeto": "Eixo de teste",
            "cliente": "Laboratório de engenharia",
            "codigo_documento": "MC-FAD-001",
            "revisao": "00",
            "emissao": "28/07/2026",
            "responsavel": "Projetista",
            "verificador": "Verificador",
            "aprovador": "Aprovador",
            "situacao_documento": "Para verificação",
            "observacoes_memorial": "Caso padrão de validação com 500 °F.",
            "componente_analisado": "Eixo - seção junto ao ombro",
            "referencia_projeto": "Desenho DX-001 e especificação EF-02",
            "fator_seguranca_minimo": 1.5,
            "vida_requerida_ciclos": 1_000_000.0,
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
            "Kt": 1.5,
            "q": 0.8,
            "fator_entalhe": 1.0,
            "sigma_a_nom": 200.0,
            "sigma_a": 200.0,
            "sigma_m": 100.0,
            "sigma_a_eq": 240.0,
            "Sm": 540.0,
            "n_goodman": 0.61,
            "n_soderberg": 0.58,
            "n_escoamento": 1.33,
            "resultado_vida": "31.875 ciclos",
            "ciclos_estimados": 31_875.0,
            "vida_infinita": False,
        }
        rows = [
            ("Material", "Resistência à tração", "Sut", "600,00", "MPa", "Entrada manual"),
            ("Material", "Limite de escoamento", "Sy", "400,00", "MPa", "Entrada manual"),
            ("Condição", "Diâmetro equivalente", "d", "20,00", "mm", "Seção crítica"),
            ("Condição", "Temperatura", "T", "260,00", "°C", "Entrada: 500,00 °F"),
            ("Entalhe", "Tratamento", "-", "Sem entalhe", "-", "Fator igual a 1"),
            ("Tensões", "Tensão alternada", "σa", "200,00", "MPa", "Valor efetivo"),
            ("Tensões", "Tensão média", "σm", "100,00", "MPa", "Ponto crítico"),
            ("Marin", "Fator de temperatura", "Ctemp", "0,7100", "-", "Norton em °F"),
            ("Resultados", "Goodman", "nG", "0,610", "-", "Não atende"),
            ("Resultados", "Vida estimada", "N", "31.875 ciclos", "-", "Modelo S-N"),
        ]
        keys = ["Grupo", "Grandeza", "Símbolo", "Valor", "Unidade", "Observação"]
        self.linhas = [dict(zip(keys, row, strict=True)) for row in rows]

    def test_generates_editable_standardized_docx(self):
        # Memorial separado: o trecho para colar no documento oficial (core.memorial_trecho) —
        # sem capa, cabeçalho, resumo executivo nem aprovações, títulos sem número.
        content = memorial_word.gerar_memorial_fadiga_word(self.dados, self.linhas)
        self.assertTrue(content.startswith(b"PK"))

        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("Análise de fadiga — Eixo - seção junto ao ombro", text)
        self.assertIn("Correção de temperatura", text)
        self.assertIn("Conclusão e recomendações", text)
        self.assertIn("500,00 °F", text)
        for ausente in (
            "Resumo executivo", "Aprovações", "7.2 Correção", "controle de revisão",
            "pendências e ações", "Checklist", "Apêndice", "Integração com outras",
        ):  # fmt: skip
            self.assertNotIn(ausente, text)
        self.assertGreaterEqual(len(document.tables), 2)
        self.assertEqual(document.sections[0].header.paragraphs[0].text, "")
        self.assertEqual(len(document.sections), 1)

    def test_required_life_can_govern_the_final_status(self):
        dados = copy.deepcopy(self.dados)
        dados.update(
            {
                "n_goodman": 2.0,
                "n_soderberg": 1.8,
                "n_escoamento": 2.2,
                "ciclos_estimados": 500_000.0,
                "resultado_vida": "500.000 ciclos",
                "vida_requerida_ciclos": 1_000_000.0,
            }
        )
        content = memorial_word.gerar_memorial_fadiga_word(dados, self.linhas)
        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("NÃO ATENDE", text)
        self.assertIn("500.000 ciclos", text)
        self.assertIn("1.000.000 ciclos requeridos", text)

    def test_trecho_tem_legendas_numeradas_equacoes_e_listas(self):
        content = memorial_word.gerar_memorial_fadiga_word(self.dados, self.linhas)
        with ZipFile(io.BytesIO(content)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        self.assertGreaterEqual(xml.count("SEQ Tabela"), 2)
        self.assertGreaterEqual(xml.count("<m:oMathPara"), 5)  # Marin, Goodman, vida…
        document = Document(io.BytesIO(content))
        estilos = {p.style.name for p in document.paragraphs if p.text.strip()}
        self.assertIn("List Bullet", estilos)
        self.assertIn("List Number", estilos)  # os passos do cálculo, em ordem
        legendas = [p.text for p in document.paragraphs if p.style.name == "Caption"]
        self.assertTrue(legendas and not any("Tabela 1 -" in x for x in legendas))
