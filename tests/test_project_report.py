from io import BytesIO

from docx import Document
from pypdf import PdfReader

from core.materials_registry import criar_material_projeto
from core.project_report import (
    avaliar_integridade_registro,
    gerar_relatorio_industrial_pdf,
    gerar_relatorio_industrial_word,
    montar_modelo_relatorio,
)
from core.project_store import criar_item
from tests.test_project_validation import _projeto_documentado


def test_modelo_relatorio_filtra_secoes_e_registros():
    projeto = _projeto_documentado()
    modelo = montar_modelo_relatorio(
        projeto,
        secoes_incluidas=["escopo", "validacao", "conclusao"],
        registros_ids=[],
    )
    titulos = [item["titulo"] for item in modelo["secoes"]]
    assert len(titulos) == 3
    assert any("Central de validação" in titulo for titulo in titulos)
    assert modelo["registros"] == []


def test_relatorio_word_e_pdf_sao_validos_e_contem_identificacao():
    projeto = _projeto_documentado()
    word = gerar_relatorio_industrial_word(projeto)
    pdf = gerar_relatorio_industrial_pdf(projeto)

    assert word.startswith(b"PK")
    documento = Document(BytesIO(word))
    texto_word = "\n".join(paragrafo.text for paragrafo in documento.paragraphs)
    assert "Memorial técnico do projeto industrial" in texto_word
    assert "Central de validação" in texto_word

    assert pdf.startswith(b"%PDF")
    leitor = PdfReader(BytesIO(pdf))
    assert len(leitor.pages) >= 2
    texto_pdf = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    assert "PR-204" in texto_pdf
    assert "Resumo executivo" in texto_pdf


def test_memorial_modular_preserva_ordem_materiais_sensibilidade_e_hash():
    projeto = _projeto_documentado()
    material = criar_material_projeto(
        nome="Material rastreado",
        familia="Aço",
        condicao="Normalizado",
        forma_produto="Chapa 10 mm",
        lote="L-1",
        propriedades={"Sut_MPa": 430, "Sy_MPa": 280, "temperatura_min_C": -20, "temperatura_max_C": 100},
        origem_tipo="Certificado do lote / MTR",
        fonte="Usina",
        documento="MTR-1",
        data_verificacao="2026-08-14",
        responsavel_verificacao="Eng. A",
        aplicabilidade="Produto do projeto",
    )
    projeto["materiais_projeto"] = [material]
    sensibilidade = criar_item(
        modulo="Análise de sensibilidade",
        titulo="Robustez da utilização",
        status="Atende",
        resumo="OAT e Monte Carlo",
        metodo="OAT ±10% e 1000 amostras",
        equacoes=["U = demanda/capacidade"],
        entradas={"demanda": 80, "capacidade": 100},
        resultados={
            "saida_nominal": 0.8,
            "p05": 0.7,
            "p95": 0.92,
            "probabilidade_nao_atendimento_pct": 1.2,
            "ranking_sensibilidade": [{"variavel": "Demanda", "impacto_percentual": 20, "elasticidade": 1, "direcao_critica": "aumentar"}],
            "correlacoes_spearman": [{"variavel": "Demanda", "correlacao": 0.8}],
        },
        premissas=["Entradas independentes"],
        referencias=["MC-204"],
        conclusao="Risco inferior a 5%.",
    )
    projeto["registros_tecnicos"].append(sensibilidade)
    ordem = [sensibilidade["id"], projeto["registros_tecnicos"][0]["id"]]
    modelo = montar_modelo_relatorio(projeto, registros_ids=ordem)
    assert [item["id"] for item in modelo["registros"]] == ordem
    assert any("Materiais e propriedades" in item["titulo"] for item in modelo["secoes"])
    assert any("Sensibilidade, incertezas" in item["titulo"] for item in modelo["secoes"])
    assert len(modelo["snapshot_hash"]) == 64
    assert avaliar_integridade_registro(sensibilidade)["percentual"] == 100

    alterado = montar_modelo_relatorio(projeto, registros_ids=list(reversed(ordem)))
    assert alterado["snapshot_hash"] != modelo["snapshot_hash"]
