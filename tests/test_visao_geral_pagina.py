"""A Visão geral acompanha os dados persistidos e os filtros do projeto ativo."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.project_store import obter_projeto_ativo

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_visao_geral_sem_projeto_oferece_navegacao(banco_isolado):
    tela = AppTest.from_file(APP).run()
    assert not tela.exception
    assert any(item.value == "Nenhum projeto ativo" for item in tela.subheader)
    assert not tela.metric


def test_visao_geral_detalha_validacao_calculos_e_prazos(banco_com_projeto):
    projeto = obter_projeto_ativo()
    chave = f"painel_projeto_inicio_{projeto['id']}"
    tela = AppTest.from_file(APP).run()
    assert not tela.exception
    indicadores = {item.label: item.value for item in tela.metric}
    assert indicadores["Cálculos vigentes"] == "1"
    assert indicadores["Prazos vencidos"] == "1"
    assert indicadores["Checklist encerrado"] == "1/4"

    tela.selectbox(key=f"{chave}_gravidade").set_value("Bloqueio").run()
    achados = tela.dataframe[0].value
    assert set(achados["Gravidade"]) == {"Bloqueio"}

    tela.segmented_control(key=f"{chave}_visao").set_value("Cálculos").run()
    assert tela.dataframe[0].value["Cálculo"].tolist() == ["Ponto crítico P1"]
    assert tela.dataframe[0].value["Menor fator"].tolist() == [2.1]

    tela.segmented_control(key=f"{chave}_visao").set_value("Prazos").run()
    assert tela.dataframe[0].value["Item"].tolist() == [
        "Cobrar folha de dados",
        "Conferir desenho",
        "Revisão independente",
    ]
    tela.selectbox(key=f"{chave}_prazo").set_value("Vencido").run()
    assert tela.dataframe[0].value["Item"].tolist() == ["Cobrar folha de dados"]

    tela.segmented_control(key=f"{chave}_visao").set_value("Escopo").run()
    indicadores = {item.label: item.value for item in tela.metric}
    assert indicadores["Componentes"] == "1"
    assert indicadores["Documentos"] == "2"

    tela.switch_page("app_pages/gestao_projetos.py").run()
    assert not tela.exception
    assert tela.segmented_control(key=f"painel_projeto_jornada_{projeto['id']}_visao").value == (
        "Validação"
    )
    assert any(item.label == "Cálculos vigentes" and item.value == "1" for item in tela.metric)
