"""O aplicativo inteiro (``app.py``) com o armazenamento: aviso na lateral, restauração ao abrir, painel.

Reproduz a queixa "o programa não salva na versão web": o disco da hospedagem é apagado e, sem o
espelho, o projeto some; com o espelho, o que foi salvo antes do reinício volta na abertura.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import armazenamento as arm
from core import project_store
from core.project_store import criar_projeto, listar_projetos, obter_projeto, salvar_projeto

# Caminho absoluto: o AppTest resolve um relativo contra a pasta do arquivo de teste nas versões
# novas do Streamlit (ver test_flambagem_pagina.py).
APP = str(Path(__file__).resolve().parent.parent / "app.py")
FLAMBAGEM = "app_pages/flambagem_colunas.py"
RAIZ_REMOTA = "mecanica_toolkit"


@pytest.fixture
def nuvem(monkeypatch):
    monkeypatch.setenv(arm.VARIAVEL_AMBIENTE, "nuvem")


def abrir(pagina: str | None = None) -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    if pagina:
        teste.switch_page(pagina)
        teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def textos(elementos) -> str:
    return " ".join(str(e.value) for e in elementos)


def registrar_flambagem(teste: AppTest) -> None:
    teste.button(key="registrar_flambagem_colunas").click().run()
    assert not teste.exception, [str(e.value) for e in teste.exception]


def test_no_computador_do_usuario_o_app_nao_acrescenta_avisos(banco_isolado):
    teste = abrir()
    assert not teste.sidebar.warning and not teste.sidebar.error
    assert "sincronizados" not in textos(teste.sidebar.caption)
    assert not teste.sidebar.get("download_button")


@pytest.mark.parametrize("pagina", [None, FLAMBAGEM, "app_pages/painel_industrial.py"])
def test_na_nuvem_sem_espelho_toda_pagina_avisa_na_lateral(banco_isolado, nuvem, pagina):
    teste = abrir(pagina)
    assert "Versão web: dados temporários" in textos(teste.sidebar.warning)
    assert "Baixe a carteira ao terminar" in textos(teste.sidebar.warning)
    assert len(teste.sidebar.get("download_button")) == 1


def test_o_painel_industrial_explica_o_problema_e_como_resolver(banco_isolado, nuvem):
    teste = abrir("app_pages/painel_industrial.py")
    assert "Nenhum projeto no banco" in textos(teste.info)
    assert "apagado quando o aplicativo reinicia" in textos(teste.warning)
    assert "MECANICA_TOOLKIT_GITHUB_TOKEN" in textos(teste.code)
    assert "disco temporário da hospedagem" in textos(teste.caption)


def test_projetos_permanentes_avisa_antes_de_o_usuario_criar_algo(banco_isolado, nuvem):
    teste = abrir("app_pages/gestao_projetos.py")
    assert "apagado quando o aplicativo reinicia" in textos(teste.warning)


def test_a_pagina_inicial_nao_promete_o_que_o_disco_nao_cumpre(banco_isolado, nuvem):
    criar_projeto("Mezanino", codigo="PRJ-1", objetivo="Verificar.")
    teste = abrir()
    assert "na versão web os dados são temporários" in textos(teste.caption)
    assert "O banco local mantém" not in textos(teste.caption)


def test_registrar_na_web_sem_espelho_diz_que_o_dado_e_temporario(banco_com_projeto, nuvem):
    teste = abrir(FLAMBAGEM)
    registrar_flambagem(teste)
    assert "só temporariamente (versão web)" in textos(teste.success)


def test_na_nuvem_com_espelho_o_que_o_disco_perdeu_volta_ao_abrir(
    banco_isolado, nuvem, espelho_github, github_falso, tmp_path
):
    antigo = tmp_path / "antes.sqlite3"
    for nome, codigo in (("Mezanino", "PRJ-1"), ("Escada", "PRJ-2")):
        projeto = criar_projeto(nome, codigo=codigo, objetivo="Verificar.", caminho_banco=antigo)
        salvar_projeto(projeto, motivo="Marco", criar_revisao=True, caminho_banco=antigo)
    assert listar_projetos() == []  # o disco da web recomeçou vazio

    teste = abrir()
    assert {p["codigo"] for p in listar_projetos()} == {"PRJ-1", "PRJ-2"}
    assert "2 projeto(s) e 0 catálogo(s) carregado(s) do GitHub." in textos(teste.toast)
    assert "Projetos sincronizados com o GitHub." in textos(teste.sidebar.caption)
    assert not teste.sidebar.warning


def test_salvar_na_web_com_espelho_confirma_e_o_github_recebe_o_registro(
    banco_com_projeto, nuvem, espelho_github, github_falso
):
    teste = abrir(FLAMBAGEM)
    registrar_flambagem(teste)
    assert "Salvo e copiado para o GitHub." in textos(teste.success)
    arquivos = github_falso.caminhos(f"{RAIZ_REMOTA}/projetos")
    assert len(arquivos) == 1
    registros = github_falso.documento(arquivos[0])["projeto"]["registros_tecnicos"]
    assert any(r["modulo_id"] == "flambagem_colunas" for r in registros)


def test_ciclo_completo_salvar_perder_o_disco_e_reabrir(
    banco_com_projeto, nuvem, espelho_github, github_falso, tmp_path, monkeypatch
):
    """A queixa original: salvou, o servidor reiniciou, o projeto sumiu."""
    teste = abrir(FLAMBAGEM)
    registrar_flambagem(teste)
    assert "Salvo e copiado para o GitHub." in textos(teste.success)

    # Reinício do servidor: disco novo e vazio, processo novo (nada lembra da restauração).
    monkeypatch.setattr(project_store, "BANCO_PADRAO", tmp_path / "disco_novo.sqlite3")
    arm.redefinir()
    assert listar_projetos() == []

    abrir()
    projetos = listar_projetos()
    assert [p["codigo"] for p in projetos] == ["PRJ-2026-014"]
    restaurado = obter_projeto(projetos[0]["id"])
    assert any(r["modulo_id"] == "flambagem_colunas" for r in restaurado["registros_tecnicos"])
    assert len(restaurado["registros_tecnicos"]) == 3  # os dois da fixture mais o da flambagem


def test_espelho_com_token_vencido_aparece_na_lateral_sem_derrubar_o_app(
    banco_isolado, nuvem, espelho_github, github_falso
):
    github_falso.token = "outro-token"  # o do cliente passa a ser recusado (401)
    teste = abrir()
    assert "recusou o token" in textos(teste.sidebar.warning)
    assert len(teste.sidebar.get("download_button")) == 1


def test_o_painel_nao_chama_de_temporario_o_disco_protegido_pelo_espelho(
    banco_isolado, nuvem, espelho_github
):
    teste = abrir("app_pages/painel_industrial.py")
    assert "disco da hospedagem, com cópia no GitHub" in textos(teste.caption)
    assert "disco temporário" not in textos(teste.caption)
    assert "Projetos sincronizados com o GitHub." in textos(teste.success)
