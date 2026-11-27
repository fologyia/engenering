"""Composição salva, prévia e proteção contra downloads desatualizados."""

from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_central_relatorios_pagina import abrir, registrar_analises


def test_rascunho_persiste_sem_registrar_emissao(banco_com_projeto):
    projeto_id = registrar_analises()
    projeto = obter_projeto_ativo()
    projeto["configuracao_relatorio"] = {"perfil": "Memorial estrutural detalhado"}
    salvar_projeto(projeto)
    teste = abrir()
    teste.text_area(key=f"contexto_sistema_{projeto_id}").set_value(
        "Pórtico com pilares engastados."
    )
    teste.text_input(key=f"codigo_memorial_{projeto_id}").set_value("MC-TESTE")
    teste.text_input(key=f"revisao_memorial_{projeto_id}").set_value("B")
    teste.button(key=f"salvar_rascunho_{projeto_id}").click().run()
    assert not teste.exception
    salvo = obter_projeto_ativo()["configuracao_relatorio"]
    assert salvo["contexto_estrutural"]["sistema"] == "Pórtico com pilares engastados."
    assert salvo["identificacao"]["codigo"] == "MC-TESTE"
    assert salvo["identificacao"]["revisao"] == "B"
    assert not salvo.get("emissoes")

    retomado = abrir()
    assert (
        retomado.text_area(key=f"contexto_sistema_{projeto_id}").value
        == "Pórtico com pilares engastados."
    )
    assert retomado.text_input(key=f"codigo_memorial_{projeto_id}").value == "MC-TESTE"


def test_arquivo_gerado_guarda_identificacao_e_avisa_mudanca(banco_com_projeto):
    projeto_id = registrar_analises()
    teste = abrir()
    teste.text_input(key=f"codigo_memorial_{projeto_id}").set_value("MC-ORIGINAL")
    teste.text_input(key=f"revisao_memorial_{projeto_id}").set_value("01")
    next(botao for botao in teste.button if botao.label == "Gerar Word e PDF").click().run()
    assert not teste.exception
    gerado = teste.session_state[f"relatorio_gerado_{projeto_id}"]
    assert gerado["metadata"]["codigo"] == "MC-ORIGINAL"
    assert gerado["metadata"]["revisao"] == "01"

    teste.text_input(key=f"codigo_memorial_{projeto_id}").set_value("MC-ALTERADO").run()
    assert any("mudaram após a geração" in aviso.value for aviso in teste.warning)
    assert (
        teste.session_state[f"relatorio_gerado_{projeto_id}"]["metadata"]["codigo"] == "MC-ORIGINAL"
    )


def test_sugestao_preserva_texto_existente_e_usa_dados_do_projeto(banco_com_projeto):
    projeto_id = registrar_analises()
    projeto = obter_projeto_ativo()
    projeto["descricao"] = "Plataforma de manutenção"
    projeto["base_projeto"]["limitacoes"] = "Fundações fora do escopo."
    projeto["configuracao_relatorio"] = {"perfil": "Memorial estrutural detalhado"}
    salvar_projeto(projeto)
    teste = abrir()
    teste.text_area(key=f"contexto_sistema_{projeto_id}").set_value(
        "Texto redigido pelo responsável."
    )
    teste.button(key=f"sugerir_contexto_{projeto_id}").click().run()
    assert not teste.exception
    assert (
        teste.text_area(key=f"contexto_sistema_{projeto_id}").value
        == "Texto redigido pelo responsável."
    )
    recomendacoes = teste.text_area(key=f"contexto_recomendacoes_{projeto_id}").value
    assert "Fundações fora do escopo" in recomendacoes
    assert not obter_projeto_ativo()["configuracao_relatorio"].get("contexto_estrutural")


def test_edicao_concorrente_exige_recarregar_sem_sobrescrever(banco_com_projeto):
    projeto_id = registrar_analises()
    projeto = obter_projeto_ativo()
    projeto["configuracao_relatorio"] = {"perfil": "Memorial estrutural detalhado"}
    salvar_projeto(projeto)
    teste = abrir()
    teste.text_area(key=f"contexto_sistema_{projeto_id}").set_value("Edição local")
    externo = obter_projeto_ativo()
    externo["configuracao_relatorio"]["contexto_estrutural"] = {"sistema": "Edição externa"}
    salvar_projeto(externo)
    # Um rerun de widget não pode transformar a gravação externa na versão vista do rascunho.
    teste.text_input(key=f"codigo_memorial_{projeto_id}").set_value("NOVO").run()
    teste.button(key=f"salvar_rascunho_{projeto_id}").click().run()
    assert not teste.exception
    assert any("outra sessão" in str(erro.value) for erro in teste.error)
    assert (
        obter_projeto_ativo()["configuracao_relatorio"]["contexto_estrutural"]["sistema"]
        == "Edição externa"
    )
    teste.button(key=f"recarregar_memorial_{projeto_id}").click().run()
    assert teste.text_area(key=f"contexto_sistema_{projeto_id}").value == "Edição externa"


def test_composicao_salva_preserva_superado_incluido_explicitamente(banco_com_projeto):
    projeto = obter_projeto_ativo()
    antigo = next(
        item for item in projeto["registros_tecnicos"] if item.get("status") == "Superado"
    )
    projeto["configuracao_relatorio"] = {"registros_incluidos": [antigo["id"]]}
    salvar_projeto(projeto)
    teste = abrir()
    teste.button(key=f"salvar_rascunho_{projeto['id']}").click().run()
    assert not teste.exception
    assert obter_projeto_ativo()["configuracao_relatorio"]["registros_incluidos"] == [antigo["id"]]
