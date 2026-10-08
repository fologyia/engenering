"""Senha de acesso opcional: regra pura (core/acesso.py) e tela (components/acesso_ui.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import acesso, armazenamento

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
SENHA = "cobre-e-aco-2026"


# ------------------------------------------------------------------ regra pura
def test_sem_variavel_o_acesso_e_livre(monkeypatch):
    monkeypatch.delenv(acesso.VARIAVEL_SENHA, raising=False)
    assert not acesso.acesso_exigido()
    assert acesso.senha_configurada() == ""
    assert not acesso.senha_confere("qualquer")
    assert acesso.marca_da_sessao() == ""
    assert not acesso.sessao_liberada("")


def test_variavel_so_com_espacos_nao_fecha_o_acesso(monkeypatch):
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, "   ")
    assert not acesso.acesso_exigido()


def test_senha_confere_e_ignora_espacos_nas_pontas(monkeypatch):
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, f" {SENHA} ")
    assert acesso.acesso_exigido()
    assert acesso.senha_confere(SENHA)
    assert acesso.senha_confere(f"  {SENHA}")
    assert not acesso.senha_confere(SENHA.upper())
    assert not acesso.senha_confere(SENHA + "x")
    assert not acesso.senha_confere("")


def test_marca_da_sessao_nao_revela_a_senha_e_muda_com_ela(monkeypatch):
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, SENHA)
    marca = acesso.marca_da_sessao()
    assert marca and SENHA not in marca
    assert acesso.sessao_liberada(marca)
    assert not acesso.sessao_liberada("outra")
    assert not acesso.sessao_liberada(None)
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, "senha-trocada")
    assert not acesso.sessao_liberada(marca)


@pytest.mark.parametrize(
    ("falhas", "espera"),
    [(0, 0.0), (1, 0.0), (2, 0.0), (3, 2.0), (4, 4.0), (5, 8.0), (8, 60.0), (40, 60.0)],
)
def test_espera_cresce_e_para_no_teto(falhas, espera):
    assert acesso.espera_apos_falhas(falhas) == espera


# ------------------------------------------------------------------ a tela
@pytest.fixture
def com_senha(monkeypatch):
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, SENHA)
    monkeypatch.setattr(acesso, "PAUSA_APOS_ERRO_S", 0.0)


def _abrir() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def _textos(t: AppTest) -> str:
    return " ".join([*(m.value for m in t.markdown), *(c.value for c in t.caption)])


def test_com_senha_a_tela_de_entrada_vem_antes_de_qualquer_projeto(banco_com_projeto, com_senha):
    t = _abrir()
    assert t.text_input(key="acesso_campo_senha").proto.type == 1  # password
    assert "acesso restrito" in _textos(t)
    assert "Suporte do transportador CV-204" not in _textos(t)
    assert not t.metric and not t.dataframe  # nenhuma página de dados foi desenhada


def test_o_campo_de_senha_tem_interrogacao(banco_isolado, com_senha):
    t = _abrir()
    assert t.text_input(key="acesso_campo_senha").proto.help
    assert all(b.proto.help for b in t.button if b.proto.form_id)


def test_senha_errada_nao_entra_e_mostra_erro(banco_isolado, com_senha):
    t = _abrir()
    t.text_input(key="acesso_campo_senha").set_value("errada")
    t.button[0].click().run()
    assert [e.value for e in t.error] == ["Senha incorreta."]
    assert t.session_state["acesso_falhas"] == 1
    assert "acesso_marca" not in t.session_state


def test_senha_certa_libera_o_aplicativo_e_mostra_sair(banco_isolado, com_senha):
    t = _abrir()
    t.text_input(key="acesso_campo_senha").set_value(SENHA)
    t.button[0].click().run()
    assert not t.exception
    assert t.session_state["acesso_marca"] == acesso.marca_da_sessao()
    assert any(b.key == "acesso_sair" for b in t.button)
    assert "acesso restrito" not in _textos(t)


def test_sair_volta_para_a_tela_de_senha(banco_isolado, com_senha):
    t = _abrir()
    t.text_input(key="acesso_campo_senha").set_value(SENHA)
    t.button[0].click().run()
    t.button(key="acesso_sair").click().run()
    assert "acesso_marca" not in t.session_state
    assert "acesso restrito" in _textos(t)


def test_trocar_a_senha_derruba_a_sessao_aberta(banco_isolado, com_senha, monkeypatch):
    t = _abrir()
    t.text_input(key="acesso_campo_senha").set_value(SENHA)
    t.button[0].click().run()
    monkeypatch.setenv(acesso.VARIAVEL_SENHA, "outra-senha-2026")
    t.run()
    assert "acesso restrito" in _textos(t)


def test_tres_erros_seguidos_pedem_espera(banco_isolado, com_senha):
    t = _abrir()
    for _ in range(3):
        t.text_input(key="acesso_campo_senha").set_value("errada")
        t.button[0].click().run()
    assert t.session_state["acesso_falhas"] == 3
    t.text_input(key="acesso_campo_senha").set_value(SENHA)  # até a certa espera
    t.button[0].click().run()
    assert any("Aguarde" in w.value for w in t.warning)
    assert "acesso_marca" not in t.session_state


def test_sem_senha_na_nuvem_o_aviso_de_acesso_aberto_aparece(banco_isolado, monkeypatch):
    monkeypatch.setenv(armazenamento.VARIAVEL_AMBIENTE, "nuvem")
    t = _abrir()
    avisos = " ".join(c.value for c in t.sidebar.caption)
    assert "Acesso aberto" in avisos and acesso.VARIAVEL_SENHA in avisos


def test_sem_senha_no_computador_nada_muda(banco_isolado):
    t = _abrir()
    avisos = " ".join(c.value for c in t.sidebar.caption)
    assert "Acesso aberto" not in avisos
    assert not any(b.key == "acesso_sair" for b in t.button)
