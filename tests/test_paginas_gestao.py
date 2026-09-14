"""As páginas de gestão precisam mostrar as leituras certas de um projeto real.

A abertura sem exceção de cada página — com e sem projeto — fica em
``test_paginas_carregam``. Aqui o banco temporário recebe o projeto cheio da
fixture ``banco_com_projeto`` (``conftest.py``) e os testes conferem o que
as páginas *mostram*: métricas, alertas, semeadura do checklist e backup.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import project_store
from core.project_store import criar_projeto, salvar_projeto

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")


def test_pagina_de_projetos_mostra_as_leituras_de_gestao(banco_com_projeto):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/gestao_projetos.py")
    teste.run()
    assert not teste.exception
    rotulos = {metrica.label for metrica in teste.metric}
    assert {"Situação", "Prazos vencidos", "Bloqueios"} <= rotulos
    vencidos = next(metrica for metrica in teste.metric if metrica.label == "Prazos vencidos")
    assert str(vencidos.value) == "1"
    textos = " ".join(str(item.value) for item in teste.markdown)
    assert "Próximos passos sugeridos" in textos
    assert "Comparar revisões" in " ".join(str(item.value) for item in teste.subheader)


def test_painel_lista_o_projeto_e_seus_alertas(banco_com_projeto):
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/painel_industrial.py")
    teste.run()
    assert not teste.exception
    rotulos = {metrica.label for metrica in teste.metric}
    assert {"Projetos", "Vencidos", "Desatualizados"} <= rotulos
    projetos = next(metrica for metrica in teste.metric if metrica.label == "Projetos")
    assert str(projetos.value) == "1"
    textos = " ".join(str(item.value) for item in teste.markdown)
    assert "PRJ-2026-014" in textos
    assert "prazo(s) vencido(s)" in textos


@pytest.fixture
def banco_com_projeto_vazio(tmp_path, monkeypatch):
    banco = tmp_path / "vazio.sqlite3"
    monkeypatch.setattr(project_store, "BANCO_PADRAO", banco)
    projeto = criar_projeto(
        "Mezanino da britagem",
        codigo="PRJ-MEZ-01",
        objetivo="Verificar o mezanino.",
        tipo_projeto="Estrutura metálica",
    )
    projeto.update({"responsavel": "Eng. Ana", "verificador": "Eng. Bruno"})
    salvar_projeto(projeto)
    return projeto["id"]


def test_aba_checklist_semeia_o_modelo_do_tipo_do_projeto(banco_com_projeto_vazio):
    from core.checklist_templates import obter_modelo
    from core.project_store import historico_eventos, obter_projeto

    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/gestao_projetos.py")
    teste.run()
    assert not teste.exception

    modelo = obter_modelo("estrutura_metalica")
    botao = next(
        botao
        for botao in teste.button
        if botao.label.startswith("Adicionar") and "do modelo" in botao.label
    )
    assert botao.label.startswith(f"Adicionar {len(modelo.itens)} item")
    botao.click()
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]

    projeto = obter_projeto(banco_com_projeto_vazio)
    assert len(projeto["checklist"]) == len(modelo.itens)
    origens = {item["origem_modelo"] for item in projeto["checklist"]}
    assert all(origem.startswith("estrutura_metalica:") for origem in origens)
    responsaveis = {item["responsavel"] for item in projeto["checklist"]}
    assert {"Eng. Ana", "Eng. Bruno", ""} == responsaveis  # aprovador ainda vazio
    assert any(
        "do modelo Estrutura metálica" in evento["descricao"]
        for evento in historico_eventos(banco_com_projeto_vazio)
    )

    # Depois de semear, o botão some: nada mais a acrescentar deste modelo.
    teste.run()
    assert not any(
        "do modelo" in botao.label for botao in teste.button if botao.label.startswith("Adicionar")
    )


def test_painel_gera_backup_do_banco_em_uso(banco_com_projeto):
    """O botão do painel grava um backup íntegro ao lado do banco *em uso*.

    Em uso = o banco temporário deste teste, e não o do usuário: se a página
    lesse o caminho na importação em vez de na chamada, o backup iria parar
    na pasta de dados real.
    """
    from core.project_store import listar_backups, listar_projetos, pasta_backups

    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page("app_pages/painel_industrial.py")
    teste.run()
    assert not teste.exception
    assert listar_backups() == []

    botao = next(item for item in teste.button if item.label == "Gerar backup do banco")
    botao.click()
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]

    backups = listar_backups()
    assert len(backups) == 1
    assert backups[0]["caminho"].parent == pasta_backups() == banco_com_projeto.parent / "backups"
    copia = listar_projetos(caminho_banco=backups[0]["caminho"])
    assert [item["codigo"] for item in copia] == ["PRJ-2026-014"]
    assert any("Backup gravado em" in str(item.value) for item in teste.success)


def test_duas_abas_no_mesmo_projeto_a_segunda_gravacao_e_avisada_e_nao_sobrescreve(
    banco_com_projeto,
):
    """Duas sessões abrem o projeto; a que grava por último não apaga a outra.

    A aba B renderiza com o documento que carregou antes da gravação da aba
    A. Ao salvar, o programa recusa e mostra o aviso — em vez da caixa de
    exceção do Streamlit, e em vez de sobrescrever em silêncio, que era o
    comportamento anterior.
    """
    from core.project_store import obter_projeto_ativo

    def abrir_projetos() -> AppTest:
        teste = AppTest.from_file(APP, default_timeout=180)
        teste.run()
        teste.switch_page("app_pages/gestao_projetos.py")
        teste.run()
        assert not teste.exception
        return teste

    def salvar_essencial(teste: AppTest, descricao: str) -> None:
        campo = next(item for item in teste.text_area if item.label.startswith("Descrição"))
        campo.set_value(descricao)
        botao = next(item for item in teste.button if item.label == "Salvar essencial")
        botao.click()
        teste.run()

    aba_a = abrir_projetos()
    aba_b = abrir_projetos()

    salvar_essencial(aba_a, "Escrito pela aba A")
    assert not aba_a.exception, [str(e.value) for e in aba_a.exception]
    assert obter_projeto_ativo()["descricao"] == "Escrito pela aba A"

    salvar_essencial(aba_b, "Escrito pela aba B por cima da A")
    assert not aba_b.exception, [str(e.value) for e in aba_b.exception]
    avisos = " ".join(str(item.value) for item in aba_b.error)
    assert "gravado por outra sessão" in avisos
    assert obter_projeto_ativo()["descricao"] == "Escrito pela aba A"

    # Depois de recarregar, a aba B grava normalmente.
    aba_b = abrir_projetos()
    salvar_essencial(aba_b, "Escrito pela aba B depois de recarregar")
    assert not aba_b.exception
    assert "outra sessão" not in " ".join(str(item.value) for item in aba_b.error)
    assert obter_projeto_ativo()["descricao"] == "Escrito pela aba B depois de recarregar"
