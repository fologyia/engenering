from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from core.calculo_externo import salvar_capitulo
from core.memorial_do_projeto import juntar, ordem_do_projeto, repetidos
from core.project_report import (
    avaliar_integridade_registro,
    gerar_relatorio_industrial_pdf,
    gerar_relatorio_industrial_word,
    montar_modelo_relatorio,
)
from core.project_store import obter_projeto_ativo, salvar_projeto
from core.technical_records import avaliar_contrato_registro
from tests.test_project_validation import _projeto_documentado


def campos(**extras):
    return {
        "titulo": "Ligação externa",
        "peca": "L-01",
        "modelo": "Ligação estrutural",
        "entradas": [
            {"grandeza": "Força", "valor": "120", "unidade": "kN", "fonte": "Desenho D-2"}
        ],
        "resultados": [{"grandeza": "Resistência", "valor": "", "unidade": "kN", "fonte": ""}],
        "metodo": "Método informado pelo responsável",
        **extras,
    }


def _texto_word(conteudo):
    doc = Document(BytesIO(conteudo))
    return "\n".join(
        [p.text for p in doc.paragraphs]
        + [c.text for t in doc.tables for r in t.rows for c in r.cells]
    )


def test_capitulo_em_aberto_nao_aprova_e_e_exportado_com_lacunas():
    projeto, identificador = salvar_capitulo(
        _projeto_documentado(), campos=campos(resultado_tecnico="Atende")
    )
    registro = next(r for r in projeto["registros_tecnicos"] if r["id"] == identificador)
    assert registro["status"] == "Pendente"
    assert avaliar_contrato_registro(registro)["assinatura_valida"]
    assert "Resultados" in avaliar_integridade_registro(registro)["faltantes"]
    args = {"registros_ids": [identificador], "secoes_incluidas": ["registros", "conclusao"]}
    modelo = montar_modelo_relatorio(projeto, **args)
    assert modelo["sintese"]["atendem"] == 0
    assert modelo["maior_aproveitamento"] is None
    word = _texto_word(gerar_relatorio_industrial_word(projeto, **args))
    pdf = "\n".join(
        p.extract_text() or ""
        for p in PdfReader(BytesIO(gerar_relatorio_industrial_pdf(projeto, **args))).pages
    )
    for texto in (word, pdf):
        assert "preenchimento manual ou externo" in texto
        assert "Ligação externa" in texto and "Desenho D-2" in texto
        assert "[a preencher]" in texto and "Resultado técnico informado: Pendente" in texto


@pytest.mark.parametrize(
    ("adicionados", "esperado"),
    [
        ({"premissas": "Apoio articulado"}, "Referência: [a preencher]"),
        ({"referencias": "Desenho D-2"}, "Premissa: [a preencher]"),
    ],
)
def test_lacunas_individuais_de_premissa_e_referencia_no_word_e_pdf(adicionados, esperado):
    projeto, identificador = salvar_capitulo(_projeto_documentado(), campos=campos(**adicionados))
    args = {"registros_ids": [identificador], "secoes_incluidas": ["registros"]}
    word = _texto_word(gerar_relatorio_industrial_word(projeto, **args))
    pdf = "\n".join(
        p.extract_text() or ""
        for p in PdfReader(BytesIO(gerar_relatorio_industrial_pdf(projeto, **args))).pages
    )
    assert esperado in word
    assert esperado in pdf


def test_resultado_declarado_exige_valor_e_copia_nao_herda_aprovacao():
    projeto = _projeto_documentado()
    with pytest.raises(ValueError, match="ao menos um valor"):
        salvar_capitulo(
            projeto, campos=campos(preenchimento="Informado", resultado_tecnico="Atende")
        )
    projeto, primeiro = salvar_capitulo(
        projeto,
        campos=campos(
            preenchimento="Informado",
            resultado_tecnico="Atende",
            conclusao="Verificação atende",
            resultados=[
                {"grandeza": "Resistência", "valor": "150", "unidade": "kN", "fonte": "Planilha E"}
            ],
        ),
    )
    original = next(r for r in projeto["registros_tecnicos"] if r["id"] == primeiro)
    assert original["status"] == "Atende"
    projeto, copia = salvar_capitulo(
        projeto,
        registro_id=primeiro,
        duplicar=True,
        campos=campos(
            peca="L-02",
            preenchimento="Informado",
            resultado_tecnico="Atende",
            conclusao="Atende",
            resultados=[
                {"grandeza": "Resistência", "valor": "150", "unidade": "kN", "fonte": "Planilha E"}
            ],
        ),
    )
    duplicado = next(r for r in projeto["registros_tecnicos"] if r["id"] == copia)
    assert duplicado["status"] == "Pendente" and duplicado["preenchimento"] == "A preencher"
    assert duplicado["resultados"]["grandezas"][0]["valor"] == "" and not duplicado["conclusao"]
    assert {primeiro, copia}.issubset(set(ordem_do_projeto(projeto["registros_tecnicos"])))
    assert primeiro not in repetidos(projeto["registros_tecnicos"])
    arrumado, n, ordem = juntar(projeto, ids_a_superar=[])
    assert n == 0 and {primeiro, copia}.issubset(ordem)
    assert len(arrumado["registros_tecnicos"]) == len(projeto["registros_tecnicos"])


def test_editar_capitulo_preserva_id_e_recalcula_assinatura():
    projeto, identificador = salvar_capitulo(_projeto_documentado(), campos=campos())
    anterior = next(r for r in projeto["registros_tecnicos"] if r["id"] == identificador)
    projeto, mesmo_id = salvar_capitulo(
        projeto, registro_id=identificador, campos=campos(documento="EX-04 rev. 2")
    )
    atual = next(r for r in projeto["registros_tecnicos"] if r["id"] == identificador)
    assert mesmo_id == identificador and atual["hash_calculo"] != anterior["hash_calculo"]
    assert avaliar_contrato_registro(atual)["assinatura_valida"]


def test_valor_zero_informado_nao_e_apagado():
    projeto, identificador = salvar_capitulo(
        _projeto_documentado(),
        campos=campos(
            preenchimento="Informado",
            resultado_tecnico="Atende",
            resultados=[
                {"grandeza": "Deslocamento", "valor": 0, "unidade": "mm", "fonte": "Medição"}
            ],
        ),
    )
    registro = next(r for r in projeto["registros_tecnicos"] if r["id"] == identificador)
    assert registro["resultados"]["grandezas"][0]["valor"] == "0"
    assert "Resultados" not in avaliar_integridade_registro(registro)["faltantes"]


def test_pagina_salva_e_recupera_rascunho_sem_json(banco_com_projeto):
    from pathlib import Path

    app = str(Path(__file__).resolve().parent.parent / "app.py")
    tela = AppTest.from_file(app, default_timeout=180).run()
    tela.switch_page("app_pages/calculos_manuais.py").run()
    assert not tela.exception, [str(e.value) for e in tela.exception]
    next(campo for campo in tela.text_input if campo.label == "Título do cálculo").set_value(
        "Verificação de fixação"
    )
    next(campo for campo in tela.text_input if campo.label == "Peça ou TAG").set_value("FX-01")
    next(campo for campo in tela.text_area if campo.label == "Método").set_value(
        "A completar pelo responsável"
    )
    next(botao for botao in tela.button if botao.label == "Salvar rascunho").click().run()
    assert not tela.exception, [str(e.value) for e in tela.exception]
    registros = obter_projeto_ativo()["registros_tecnicos"]
    externo = next(r for r in registros if r.get("origem_calculo") == "manual_externo")
    assert externo["titulo"] == "Verificação de fixação"
    assert externo["peca"] == "FX-01" and externo["metodo"] == "A completar pelo responsável"
    assert externo["status"] == "Pendente"
    next(campo for campo in tela.text_input if campo.label == "Peça ou TAG da cópia").set_value(
        "FX-02"
    )
    next(botao for botao in tela.button if botao.label == "Duplicar para outra peça").click().run()
    assert not tela.exception, [str(e.value) for e in tela.exception]
    copias = [
        r
        for r in obter_projeto_ativo()["registros_tecnicos"]
        if r.get("origem_calculo") == "manual_externo"
    ]
    assert {r["peca"] for r in copias} == {"FX-01", "FX-02"}
    assert all(r["status"] == "Pendente" for r in copias)


def test_editor_externo_recusa_conflito_mesmo_apos_interacao_e_permite_recarregar(
    banco_com_projeto,
):
    from pathlib import Path

    projeto, registro_id = salvar_capitulo(obter_projeto_ativo(), campos=campos(metodo="Original"))
    salvar_projeto(projeto)
    projeto_id = projeto["id"]
    app = str(Path(__file__).resolve().parent.parent / "app.py")
    tela = AppTest.from_file(app, default_timeout=180).run()
    tela.switch_page("app_pages/calculos_manuais.py").run()
    tela.selectbox(key=f"externo_escolha_{projeto_id}").set_value(registro_id).run()
    next(campo for campo in tela.text_area if campo.label == "Método").set_value("Alteração local")

    remoto = obter_projeto_ativo()
    remoto, _ = salvar_capitulo(
        remoto, registro_id=registro_id, campos=campos(metodo="Alterado em outra sessão")
    )
    salvar_projeto(remoto)
    tela.selectbox(key=f"filtro_calculos_{projeto_id}").set_value("Manual ou externo").run()
    next(botao for botao in tela.button if botao.label == "Salvar rascunho").click().run()
    assert not tela.exception
    assert any("gravado por outra sessão" in str(item.value) for item in tela.error)
    assert (
        next(r for r in obter_projeto_ativo()["registros_tecnicos"] if r["id"] == registro_id)[
            "metodo"
        ]
        == "Alterado em outra sessão"
    )

    tela.button(key=f"externo_recarregar_{projeto_id}").click().run()
    assert not tela.exception
    assert (
        next(campo for campo in tela.text_area if campo.label == "Método").value
        == "Alterado em outra sessão"
    )
