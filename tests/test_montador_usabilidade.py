"""Montador: começar pela pergunta, abas abaixo da resposta e as escolhas velhas que o navegador manda.

Ao abrir outro modelo, o navegador ainda manda, junto com a rodada que a prancheta pede, o que os
campos tinham antes: a lista de modelos de antes da pergunta, a opção do bloco q1 do modelo de antes e
o desenho de antes. Nada disso pode voltar por cima do modelo novo.
"""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from streamlit.testing.v1 import AppTest

from components import montador_ui as ui
from core import montador_modelos as mm

APP = str(Path(__file__).resolve().parents[1] / "app.py")
TERMICA = mm.PARTE_TERMICA
FLUIDOS = mm.PARTE_FLUIDOS


def _abrir(pagina: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page(pagina).run()
    assert not at.exception
    return at


def test_cada_modelo_responde_a_uma_pergunta():
    for parte in (mm.PARTE_SOLIDOS, FLUIDOS, TERMICA, mm.PARTE_PROCESSOS):
        perguntas = ui._perguntas(parte)
        nomes = [nome for lista in perguntas.values() for nome in lista]
        assert sorted(nomes) == sorted(m.nome for m in parte.modelos), parte.titulo
        assert list(perguntas) == sorted(perguntas, key=str.casefold)


def test_pergunta_com_uma_situacao_abre_o_modelo():
    at = _abrir("app_pages/montador_termico.py")
    at.selectbox(key="mte_pergunta").set_value("Coeficiente de desempenho (COP)").run()
    assert not at.exception
    assert at.session_state["mte_modelo_atual"] == "Refrigeração por compressão (R134a)"
    assert at.session_state["mte_alvo"] == "COP"


def test_pergunta_com_varias_situacoes_filtra_a_lista():
    at = _abrir("app_pages/montador_fluidos.py")
    at.selectbox(key="mfl_pergunta").set_value("Vazão (Q)").run()
    assert not at.exception
    chave = at.session_state["mfl_chave_do_modelo"]
    assert chave != "mfl_modelo"
    opcoes = at.selectbox(key=chave).options
    assert len(opcoes) == len(ui._perguntas(FLUIDOS)["Vazão (Q)"]) >= 2
    at.selectbox(key=chave).set_value("Placa de orifício pela ISO 5167").run()
    assert at.session_state["mfl_modelo_atual"] == "Placa de orifício pela ISO 5167"


def test_lista_de_antes_da_pergunta_nao_abre_o_modelo_velho():
    at = _abrir("app_pages/montador_termico.py")
    at.selectbox(key="mte_pergunta").set_value("Coeficiente de desempenho (COP)").run()
    estado = {
        "mte_modelo": "Aquecer água: vazão pelo calor",
        "mte_chave_do_modelo": at.session_state["mte_chave_do_modelo"],
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_escolher_modelo(TERMICA, "mte_modelo")
    assert "mte_grafo" not in estado  # não abriu nada


def test_opcao_do_modelo_de_antes_nao_troca_a_do_novo():
    at = _abrir("app_pages/montador_termico.py")
    revisao_velha = at.session_state["mte_revisao"]
    at.selectbox(key="mte_pergunta").set_value("Coeficiente de desempenho (COP)").run()
    grafo = copy.deepcopy(at.session_state["mte_grafo"])
    velha = f"mte_op_q1_saida_r{revisao_velha}"
    estado = {
        "mte_grafo": grafo,
        "mte_revisao": at.session_state["mte_revisao"],
        "mte_versao": 1,
        "mte_modelo_atual": "Refrigeração por compressão (R134a)",
        velha: "Temperatura de saída",
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_mudar_opcao(TERMICA, "q1", "saida", velha)
    q1 = next(n for n in grafo["nos"] if n["id"] == "q1")
    assert q1["opcoes"]["saida"] != "Temperatura de saída"
    assert estado["mte_modelo_atual"] == "Refrigeração por compressão (R134a)"


def test_desenho_atrasado_da_prancheta_nao_volta():
    at = _abrir("app_pages/montador_termico.py")
    antigo = copy.deepcopy(at.session_state["mte_grafo"])
    at.selectbox(key="mte_pergunta").set_value("Coeficiente de desempenho (COP)").run()
    novo = at.session_state["mte_grafo"]
    atrasado = {"grafo": antigo, "versao": at.session_state["mte_versao"], "so_posicao": True}
    estado = {
        "mte_prancheta": SimpleNamespace(edicao=atrasado),
        "mte_grafo": novo,
        "mte_versao": at.session_state["mte_versao"],
        "mte_modelo_atual": "Refrigeração por compressão (R134a)",
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar(TERMICA)
    assert estado["mte_grafo"] is novo


def test_abas_abaixo_da_resposta():
    at = _abrir("app_pages/montador_termico.py")
    at.selectbox(key="mte_pergunta").set_value("Rendimento térmico do ciclo (η_t)").run()
    assert not at.exception
    assert [t.label for t in at.tabs] == list(ui.ABAS)
