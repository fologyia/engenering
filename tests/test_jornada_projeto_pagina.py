"""A jornada guarda rascunhos e não atropela alterações de outra sessão."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.project_store import obter_projeto_ativo, salvar_projeto

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _abrir() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180).run()
    teste.switch_page("app_pages/gestao_projetos.py")
    teste.run()
    assert not teste.exception
    return teste


def test_jornada_salva_base_sem_apagar_dados_e_retorna_ao_rascunho(banco_com_projeto):
    projeto = obter_projeto_ativo()
    projeto_id = projeto["id"]
    teste = _abrir()
    teste.session_state[f"jornada_secao_{projeto_id}"] = "Base técnica"
    teste.run()
    chave = f"jornada_rascunho_{projeto_id}_base_base_carregamentos"
    teste.text_area(key=chave).set_value("Folha de dados EQ-01, revisão B.").run()
    assert (
        obter_projeto_ativo()["base_projeto"]["base_carregamentos"]
        != "Folha de dados EQ-01, revisão B."
    )
    assert any("alterações não salvas" in str(item.value) for item in teste.warning)
    teste.session_state[f"jornada_secao_{projeto_id}"] = "Visão geral"
    teste.run()
    teste.session_state[f"jornada_secao_{projeto_id}"] = "Base técnica"
    teste.run()
    assert teste.text_area(key=chave).value == "Folha de dados EQ-01, revisão B."
    teste.button(key=f"salvar_jornada_rascunho_{projeto_id}_base").click().run()
    assert not teste.exception
    salvo = obter_projeto_ativo()
    assert salvo["base_projeto"]["base_carregamentos"] == "Folha de dados EQ-01, revisão B."
    assert salvo["codigo"] == projeto["codigo"]


def test_jornada_detecta_gravacao_concorrente_antes_de_salvar(banco_com_projeto):
    projeto_id = obter_projeto_ativo()["id"]
    teste = _abrir()
    teste.session_state[f"jornada_secao_{projeto_id}"] = "Escopo"
    teste.run()
    campo = f"jornada_rascunho_{projeto_id}_escopo_descricao"
    teste.text_area(key=campo).set_value("Texto ainda não salvo.").run()
    projeto = obter_projeto_ativo()
    projeto["descricao"] = "Alterado em outra sessão."
    salvar_projeto(projeto)
    teste.button(key=f"salvar_jornada_rascunho_{projeto_id}_escopo").click().run()
    assert not teste.exception
    assert any("gravado por outra sessão" in str(item.value) for item in teste.error)
    assert obter_projeto_ativo()["descricao"] == "Alterado em outra sessão."
