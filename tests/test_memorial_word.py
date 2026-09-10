import copy
import io
import unittest
import xml.etree.ElementTree as ET
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
        content = memorial_word.gerar_memorial_fadiga_word(self.dados, self.linhas)
        self.assertTrue(content.startswith(b"PK"))
        self.assertGreater(len(content), 20_000)

        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("Memorial de cálculo - análise de fadiga", text)
        self.assertIn("1. Resumo executivo", text)
        self.assertIn("7.2 Correção de temperatura", text)
        self.assertIn("10. Hipóteses, pendências e ações", text)
        self.assertIn("10.1 Checklist de verificação", text)
        self.assertIn("500,00 °F", text)
        self.assertIn("Apêndice B - Estrutura mínima", text)
        self.assertGreaterEqual(len(document.tables), 11)

        header_text = " ".join(
            paragraph.text
            for table in document.sections[0].header.tables
            for row in table.rows
            for cell in row.cells
            for paragraph in cell.paragraphs
        )
        self.assertIn("MC-FAD-001", header_text)
        self.assertIn("REV. 00", header_text)

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
    def test_tables_have_fixed_matching_dxa_geometry(self):
        content = memorial_word.gerar_memorial_fadiga_word(self.dados, self.linhas)
        ns = {"w": W_NS}
        attr = lambda name: f"{{{W_NS}}}{name}"
        with ZipFile(io.BytesIO(content)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            numbering_xml = archive.read("word/numbering.xml")
            numbering = numbering_xml.decode("utf-8")
            numbering_root = ET.fromstring(numbering_xml)

        tables = root.findall(".//w:tbl", ns)
        self.assertGreaterEqual(len(tables), 11)
        for table in tables:
            width_node = table.find("w:tblPr/w:tblW", ns)
            indent_node = table.find("w:tblPr/w:tblInd", ns)
            grid = [
                int(node.get(attr("w"), "0"))
                for node in table.findall("w:tblGrid/w:gridCol", ns)
            ]
            self.assertIsNotNone(width_node)
            self.assertEqual(width_node.get(attr("type")), "dxa")
            self.assertEqual(int(width_node.get(attr("w"))), memorial_word.CONTENT_WIDTH_DXA)
            self.assertIsNotNone(indent_node)
            self.assertEqual(int(indent_node.get(attr("w"))), memorial_word.TABLE_INDENT_DXA)
            self.assertEqual(sum(grid), memorial_word.CONTENT_WIDTH_DXA)
            for row in table.findall("w:tr", ns):
                widths = [
                    int(cell.find("w:tcPr/w:tcW", ns).get(attr("w")))
                    for cell in row.findall("w:tc", ns)
                ]
                self.assertEqual(widths, grid)

        self.assertIn('w:val="bullet"', numbering)
        self.assertIn('w:val="decimal"', numbering)
        self.assertIn("\uf0b7", numbering)

        numbering_children = list(numbering_root)
        abstract_positions = [
            index for index, node in enumerate(numbering_children)
            if node.tag == f"{{{W_NS}}}abstractNum"
        ]
        num_positions = [
            index for index, node in enumerate(numbering_children)
            if node.tag == f"{{{W_NS}}}num"
        ]
        self.assertLess(max(abstract_positions), min(num_positions))

        num_to_abstract = {
            node.get(attr("numId")): node.find("w:abstractNumId", ns).get(attr("val"))
            for node in numbering_root.findall("w:num", ns)
        }
        abstract_to_format = {
            node.get(attr("abstractNumId")): node.find("w:lvl/w:numFmt", ns).get(attr("val"))
            for node in numbering_root.findall("w:abstractNum", ns)
        }

        def list_format_for(text_fragment):
            for paragraph in root.findall(".//w:body/w:p", ns):
                text = "".join(
                    node.text or "" for node in paragraph.findall(".//w:t", ns)
                )
                if text_fragment in text:
                    num_node = paragraph.find("w:pPr/w:numPr/w:numId", ns)
                    self.assertIsNotNone(num_node)
                    return abstract_to_format[
                        num_to_abstract[num_node.get(attr("val"))]
                    ]
            self.fail(f"Item de lista não encontrado: {text_fragment}")

        self.assertEqual(list_format_for("Carregamento proporcional"), "bullet")
        self.assertEqual(
            list_format_for("Objetivo e escopo da parte adicionada"),
            "decimal",
        )


if __name__ == "__main__":
    unittest.main()