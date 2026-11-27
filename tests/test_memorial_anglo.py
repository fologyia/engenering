import hashlib
from io import BytesIO

from docx import Document
from docx.oxml.ns import qn

from core.calculo_externo import salvar_capitulo
from core.memorial_anglo import (
    CAPITULOS,
    MODELO_PREENCHIDO,
    PERFIL_ANGLO,
    gerar_word_anglo,
    montar_modelo_anglo,
)
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_central_relatorios_pagina import abrir, gerar_rapido
from tests.test_project_validation import _projeto_documentado


def test_anglo_disponibiliza_o_original_e_prefere_dados_do_projeto():
    assert hashlib.sha256(MODELO_PREENCHIDO.read_bytes()).hexdigest() == (
        "8df7efb0345f86351748602a514677c1ac4a39f33be4af87176d6da353b2c0cf"
    )
    projeto = {"id": "anglo", "nome": "Plataforma de acesso"}
    word = Document(BytesIO(gerar_word_anglo(montar_modelo_anglo(projeto))))
    texto = "\n".join(n.text or "" for n in word.element.xpath(".//w:t"))
    assert "Referência do modelo Anglo" in texto
    assert "Referências internacionais" in texto
    assert "ABNT NBR 8681" in texto
    assert "AA-BR-DPST-DR-0001" in texto
    assert "ASTM A36" in texto
    assert "Nt,Sd / Nt,Rd" in texto
    assert "[OK" not in texto
    assert "Na planilha da emenda W 200" not in texto
    assert "Perna mínima (mm)" in texto

    projeto["normas"] = [{"codigo": "NORMA-CADASTRADA", "titulo": "Base do projeto"}]
    configuracao = {"criterio_cliente": "CRITERIO-CADASTRADO", "nao_aplicaveis": ["bases"]}
    modelo = montar_modelo_anglo(projeto, metadata_extra={"anglo": configuracao})
    word = Document(BytesIO(gerar_word_anglo(modelo)))
    texto = "\n".join(n.text or "" for n in word.element.xpath(".//w:t"))
    assert "NORMA-CADASTRADA" in texto
    assert "CRITERIO-CADASTRADO" in texto
    assert "ABNT NBR 8681" not in texto
    assert "Referências internacionais" not in texto
    assert "Furo na placa (mm)" not in texto


def test_anglo_preserva_formato_e_usa_apenas_registros_selecionados():
    projeto = _projeto_documentado()
    projeto, incluido = salvar_capitulo(
        projeto, campos={"titulo": "Solda L-01", "modelo": "Ligação estrutural"}
    )
    projeto, _ = salvar_capitulo(projeto, campos={"titulo": "Ligação excluída"})
    principal = projeto["registros_tecnicos"][0]["id"]
    metadata = {
        "anglo": {"numero_anglo": "AA-001", "finalidade": "IFA", "nao_aplicaveis": ["bases"]}
    }
    modelo = montar_modelo_anglo(
        projeto, registros_ids=[principal, incluido], metadata_extra=metadata
    )
    word = Document(BytesIO(gerar_word_anglo(modelo)))
    texto = "\n".join(n.text or "" for n in word.element.xpath(".//w:t"))
    assert "AA-001" in texto
    assert "Solda L-01" in texto
    assert "Ligação excluída" not in texto
    assert "Como usar este modelo" not in texto and "{{" not in texto
    assert "Não aplicável." in texto
    assert word.tables[2].rows[2].cells[7].text == "X"
    assert "IFA - FOR APPROVAL" in texto
    assert len(word.sections) == 4
    assert [p.text for p in word.paragraphs if p.style.name == "Heading 1"] == list(
        CAPITULOS.values()
    )
    assert word.settings.element.find(qn("w:updateFields")).get(qn("w:val")) == "true"


def test_anglo_salvo_gera_somente_word_na_emissao_rapida(banco_com_projeto):
    projeto = obter_projeto_ativo()
    projeto["configuracao_relatorio"] = {
        "perfil": PERFIL_ANGLO,
        "anglo": {"numero_anglo": "AA-RAPIDO", "finalidade": "IFI"},
    }
    salvar_projeto(projeto)
    tela = abrir()
    assert tela.button(key="gerar_rapido").label == "Gerar Word Anglo"
    gerado = gerar_rapido(tela, projeto["id"])
    assert gerado["word"].startswith(b"PK")
    assert gerado["pdf"] is None
    historico = obter_projeto_ativo()["configuracao_relatorio"]["emissoes"]
    assert historico[-1]["codigo"] == "AA-RAPIDO"
    assert historico[-1]["finalidade"] == "IFI"
