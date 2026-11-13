"""Do bloco Seção desenhada do Montador a Desenhar seção e de volta, com a seção já no bloco."""

from __future__ import annotations

import copy
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from components import volta_da_secao as vs
from core import elementos_vigas as ev
from core import montador_modelos as mm
from core import section_catalog as catalogo

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield
        ev._analisar_desenho.cache_clear()


def _montador_com_secao_desenhada() -> tuple[AppTest, str]:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    grafo = copy.deepcopy(mm.POR_NOME["Força máxima num braço"].grafo())
    no = next(n for n in grafo["nos"] if n["tipo"] == "retangular")
    no["tipo"], no["opcoes"] = "desenhada", {}
    at.session_state["mf_grafo"] = grafo
    at.session_state["mf_alvo"] = None
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at, str(no["id"])


def test_desenhar_e_voltar_com_a_secao_no_bloco(catalogo_vazio):
    at, no = _montador_com_secao_desenhada()
    assert (
        at.selectbox(key=f"mf_op_{no}_desenho_r{at.session_state['mf_revisao']}").value
        == ev.SEM_DESENHO
    )
    at.button(key=f"mf_desenhar_{no}").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    volta = at.session_state[vs.VOLTA]
    assert volta["destino"] == "mf" and volta["campo"] == no
    assert volta["pagina"] == "app_pages/montador_formulas.py"
    assert any("Você veio do **Montador de fórmulas**" in i.value for i in at.info)
    # O AppTest só segue o st.switch_page na rodada em que ele roda: daqui em diante, a página é
    # Desenhar seção.
    at.switch_page(vs.PAGINA_DESENHAR)
    # A seção do começo (o I) com um nome; Salvar e voltar grava e volta.
    at.text_input(key="secao_nome").set_value("Minha seção").run()
    assert "Minha seção" not in ev.nomes_dos_desenhos()
    at.button(key="secao_salvar_e_voltar").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "Minha seção" in ev.nomes_dos_desenhos()
    bloco = next(n for n in at.session_state["mf_grafo"]["nos"] if n["id"] == no)
    assert bloco["opcoes"]["desenho"] == "Minha seção"
    assert (
        at.selectbox(key=f"mf_op_{no}_desenho_r{at.session_state['mf_revisao']}").value
        == "Minha seção"
    )
    assert vs.VOLTA not in at.session_state and vs.CHEGOU not in at.session_state


def test_voltar_sem_secao_nao_muda_o_bloco(catalogo_vazio):
    at, no = _montador_com_secao_desenhada()
    at.button(key=f"mf_desenhar_{no}").click().run()
    at.switch_page(vs.PAGINA_DESENHAR)
    at.button(key="secao_voltar_sem").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert (
        at.selectbox(key=f"mf_op_{no}_desenho_r{at.session_state['mf_revisao']}").value
        == ev.SEM_DESENHO
    )
    assert vs.VOLTA not in at.session_state


def test_desenhar_secao_sem_vir_de_outra_pagina_nao_mostra_o_aviso():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(vs.PAGINA_DESENHAR).run()
    assert not at.exception
    assert not any("Você veio do" in i.value for i in at.info)
    assert not any(b.key == "secao_salvar_e_voltar" for b in at.button)
