"""Contenção de falhas: a página segue, um aviso discreto no fim e o detalhe no diagnóstico."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import diagnostico as dg

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")


@pytest.fixture
def contido(monkeypatch, banco_isolado):
    """Modo de quem usa o programa: a falha é contida (os testes, por padrão, levantam)."""
    monkeypatch.delenv(dg.VARIAVEL_MODO, raising=False)
    return banco_isolado


def _falha(mensagem: str = "boom") -> ZeroDivisionError:
    try:
        1 / 0  # noqa: B018
    except ZeroDivisionError as erro:
        erro.args = (mensagem,)
        return erro
    raise AssertionError


# ------------------------------------------------------------------ núcleo
def test_referencia_e_estavel_e_aponta_o_lugar_do_codigo():
    a, b = _falha("um"), _falha("outro")
    assert dg.referencia_da_falha(a) == dg.referencia_da_falha(b)  # mesmo lugar, mesma ref.
    try:
        int("x")
    except ValueError as outra:
        assert dg.referencia_da_falha(outra) != dg.referencia_da_falha(a)
    ocorrencia = dg.ocorrencia_de_falha("Página › seção", a)
    assert len(ocorrencia.referencia) == 6 and ocorrencia.tipo == dg.TIPO_FALHA
    assert ocorrencia.resumo.startswith("ZeroDivisionError em tests/test_robustez.py:")
    assert "Traceback" in ocorrencia.detalhe


def test_gravar_ler_girar_e_nunca_levantar(tmp_path, monkeypatch):
    destino = tmp_path / "diag"
    for i in range(3):
        assert dg.gravar(dg.ocorrencia_de_conferencia(f"origem {i}", "x"), destino=destino)
    lidas = dg.ler(destino=destino)
    assert [o["origem"] for o in lidas] == ["origem 0", "origem 1", "origem 2"]
    monkeypatch.setattr(dg, "TAMANHO_MAXIMO", 10)
    for i in range(6):
        dg.gravar(dg.ocorrencia_de_conferencia(f"giro {i}", "x"), destino=destino)
    arquivos = sorted(p.name for p in destino.iterdir())
    assert arquivos == [dg.NOME_ARQUIVO, *(f"{dg.NOME_ARQUIVO}.{n}" for n in (1, 2, 3))]
    arquivo_no_lugar_da_pasta = tmp_path / "arquivo"
    arquivo_no_lugar_da_pasta.write_text("não é pasta")
    assert (
        dg.gravar(dg.ocorrencia_de_conferencia("o", "x"), destino=arquivo_no_lugar_da_pasta)
        is False
    )
    assert dg.ler(destino=tmp_path / "nada") == []


def test_pasta_do_diagnostico_fica_ao_lado_do_banco(banco_isolado):
    assert dg.pasta() == banco_isolado.parent / dg.NOME_PASTA


def test_numeros_invalidos_em_valores_aninhados():
    @dataclass
    class R:
        a: float
        b: list

    valor = {"ok": 1.0, "bool": True, "lista": [1, math.nan], "r": R(math.inf, [2.0])}
    assert dg.numeros_invalidos(valor) == ["lista[1]", "r.a"]
    assert dg.numeros_invalidos({"x": 1, "y": "nan"}) == []


def test_modo_levantar_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv(dg.VARIAVEL_MODO, "levantar")
    assert dg.levantar_erros()
    monkeypatch.delenv(dg.VARIAVEL_MODO)
    assert not dg.levantar_erros()


# ------------------------------------------------------------------ interface
def _script_com_secoes():
    import streamlit as st

    from components.robustez import aviso_final, iniciar_execucao, secao_protegida

    iniciar_execucao()
    with st.container(border=True), secao_protegida("1. Antes"):
        st.subheader("Seção boa 1")
    with st.container(border=True), secao_protegida("2. Quebra"):
        st.subheader("Seção que quebra")
        _ = {}["chave que não existe"]
        st.subheader("nunca aparece")
    with st.container(border=True), secao_protegida("3. Depois"):
        st.subheader("Seção boa 3")
    aviso_final()


def test_secao_que_quebra_nao_derruba_as_outras(contido):
    t = AppTest.from_function(_script_com_secoes).run()
    assert not t.exception
    assert [s.value for s in t.subheader] == ["Seção boa 1", "Seção que quebra", "Seção boa 3"]
    aviso = next(c.value for c in t.caption if "ref." in c.value)
    assert "Uma parte desta página não pôde ser exibida" in aviso
    assert "KeyError" not in aviso and "Traceback" not in aviso  # nada técnico na tela
    gravadas = dg.ler()
    assert gravadas[-1]["origem"] == "Programa › 2. Quebra"
    assert gravadas[-1]["resumo"].startswith("KeyError")
    assert gravadas[-1]["referencia"] in aviso


def test_com_o_modo_levantar_a_falha_aparece(banco_isolado):
    t = AppTest.from_function(_script_com_secoes).run()
    assert t.exception  # nos testes, nada fica escondido


def _script_com_stop_e_rerun():
    import streamlit as st

    from components.robustez import aviso_final, iniciar_execucao, secao_protegida

    iniciar_execucao()
    with secao_protegida("parar"):
        st.write("antes do stop")
        st.stop()
    st.write("depois do stop")
    aviso_final()


def test_st_stop_passa_pela_protecao(contido):
    t = AppTest.from_function(_script_com_stop_e_rerun).run()
    textos = [m.value for m in t.markdown]
    assert "antes do stop" in textos and "depois do stop" not in textos
    assert not [c for c in t.caption if "ref." in c.value]
    assert dg.ler() == []


def _script_conferencia():
    import math

    from components.robustez import aviso_final, iniciar_execucao
    from components.verification_table import mostrar_tabela_verificacoes
    from core.verificacao import Verificacao

    iniciar_execucao()
    mostrar_tabela_verificacoes(
        [
            Verificacao("Boa", 1.0, 2.0, "kN", "—"),
            Verificacao("Resistência nula", 1.0, 0.0, "kN", "—"),  # ∞ legítimo: reprova
            Verificacao("Com NaN", math.nan, 2.0, "kN", "—"),
        ]
    )
    aviso_final()


def test_tabela_de_verificacoes_confere_nan_sem_mostrar_detalhe(contido):
    t = AppTest.from_function(_script_conferencia).run()
    assert not t.exception
    aviso = next(c.value for c in t.caption if "ref." in c.value)
    assert "não passou na conferência interna" in aviso
    gravada = dg.ler()[-1]
    assert gravada["tipo"] == dg.TIPO_CONFERENCIA
    assert "3. Com NaN.solicitante" in gravada["resumo"]
    assert "Resistência nula" not in gravada["resumo"]


def _script_registro_com_nan():
    import math

    from components.project_tools import botao_registrar_calculo
    from components.robustez import aviso_final, iniciar_execucao

    iniciar_execucao()
    botao_registrar_calculo(
        {"modulo_id": "x", "resultados": {"valor": math.nan}},
        key="reg_nan",
        identificar_peca=False,
    )
    aviso_final()


def test_registro_com_nan_nao_e_gravado(contido):
    t = AppTest.from_function(_script_registro_com_nan).run()
    assert not t.exception
    assert any("não pode ser registrado" in c.value for c in t.caption)
    assert not [b for b in t.button if b.key == "reg_nan"]


def test_pagina_real_com_uma_secao_quebrada_mostra_o_resto(contido, monkeypatch):
    """A seção 4 da Lista de material falha; a 5 (Exportar) continua e o aviso fica no fim."""
    from core import lista_de_material as lm
    from core import project_store

    project_store.criar_projeto("Plataforma", codigo="MC-01")

    def quebrar(*_args, **_kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(lm, "conferir_com_o_modelo", quebrar)
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/lista_de_material.py")
    t.run()
    assert not t.exception
    subtitulos = [s.value for s in t.subheader]
    assert "4. Conferência com o peso próprio do modelo" in subtitulos
    assert "5. Exportar" in subtitulos
    aviso = next(c.value for c in t.caption if "ref." in c.value)
    assert "Uma parte desta página não pôde ser exibida" in aviso
    origem = dg.ler()[-1]["origem"]
    assert origem == "Lista de material › 4. Conferência com o peso próprio do modelo"


def test_pagina_que_quebra_no_meio_fica_contida(contido, monkeypatch):
    """Falha fora de qualquer seção: a página para ali, sem tela de erro, com o aviso."""
    from core import lista_de_material as lm
    from core import project_store

    project_store.criar_projeto("Plataforma", codigo="MC-02")

    def quebrar(*_args, **_kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(lm, "resumir", quebrar)
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/lista_de_material.py")
    t.run()
    assert not t.exception
    assert any("Uma parte desta página não pôde ser exibida" in c.value for c in t.caption)
    assert dg.ler()[-1]["origem"].startswith("Lista de material")
