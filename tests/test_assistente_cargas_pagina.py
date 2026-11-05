"""A página Assistente de cargas pela interface (AppTest): todos os casos abrem e se encadeiam."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.assistente_cargas_ui import chave_do_campo
from core import elementos_catalogo as cat
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/assistente_cargas.py"
#: Campos que pertencem ao registro no projeto, e não ao caso.
ISENTOS = {("text_input", "Nome do novo projeto"), ("button", "Criar projeto e registrar")}


@pytest.fixture(name="pagina")
def _pagina() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    teste.run()
    assert not teste.exception
    return teste


def _abrir_caso(teste: AppTest, caso_id: str) -> None:
    teste.session_state["assistente_geometria"] = caso_id
    teste.run()
    assert not teste.exception, (caso_id, [e.value for e in teste.exception])


def _textos(lista) -> str:
    return " ".join(str(item.value) for item in lista)


def _botao(teste: AppTest, chave: str):
    return next(botao for botao in teste.button if botao.key == chave)


def test_abre_no_painel_com_todas_as_areas_e_todos_os_casos(pagina: AppTest):
    assert not pagina.session_state["assistente_geometria"]
    assert any("O que você precisa" in str(s.value) for s in pagina.subheader)
    chaves = {botao.key for botao in pagina.button}
    assert {f"abrir::{caso_id}" for caso_id in cat.CASOS} <= chaves
    assert {f"atalho::{atalho.caso}" for atalho in cat.ATALHOS} <= chaves
    assert len(pagina.tabs) == len(cat.AREAS)


def test_todo_botao_de_caso_do_painel_explica_o_caso(pagina: AppTest):
    for botao in pagina.button:
        if str(botao.key).startswith("abrir::"):
            assert botao.help, botao.key


def test_atalho_abre_o_caso_e_o_botao_volta_ao_painel(pagina: AppTest):
    _botao(pagina, "atalho::viga_reacoes").click().run()
    assert not pagina.exception
    assert pagina.session_state["assistente_geometria"] == "viga_reacoes"
    assert any("Resposta" in str(m.value) for m in pagina.markdown)
    _botao(pagina, "assistente_voltar").click().run()
    assert not pagina.exception
    assert not pagina.session_state["assistente_geometria"]
    assert any("O que você precisa" in str(s.value) for s in pagina.subheader)


def test_caso_aberto_fica_na_lista_de_recentes_do_painel(pagina: AppTest):
    _botao(pagina, "abrir::rosca_arrancamento").click().run()
    _botao(pagina, "assistente_voltar").click().run()
    assert not pagina.exception
    assert "recente::rosca_arrancamento" in {botao.key for botao in pagina.button}


def test_valores_digitados_sobrevivem_a_ida_ao_painel(pagina: AppTest):
    _abrir_caso(pagina, "chapa_furo")
    chave = chave_do_campo("chapa_furo", "f_kN")
    pagina.number_input(key=chave).set_value(55.0).run()
    _botao(pagina, "assistente_voltar").click().run()
    _botao(pagina, "abrir::chapa_furo").click().run()
    assert not pagina.exception
    assert pagina.number_input(key=chave).value == 55.0


def test_pilulas_trocam_de_caso_dentro_do_grupo(pagina: AppTest):
    _abrir_caso(pagina, "parafuso_axial")
    pagina.button_group(key="assistente_modelo").set_value("torque_aperto").run()
    assert not pagina.exception
    assert pagina.session_state["assistente_geometria"] == "torque_aperto"


def test_todos_os_casos_abrem_e_todo_campo_tem_ajuda(pagina: AppTest):
    for caso_id, caso in cat.CASOS.items():
        _abrir_caso(pagina, caso_id)
        assert any(caso.titulo in str(s.value) for s in pagina.subheader), caso_id
        assert not pagina.error, (caso_id, _textos(pagina.error))
        faltando = [
            (tipo, _rotulo(elemento))
            for tipo in TIPOS_COM_AJUDA
            if tipo in ("number_input", "selectbox", "toggle")
            for elemento in pagina.get(tipo)
            if not _ajuda(elemento) and (tipo, _rotulo(elemento)) not in ISENTOS
        ]
        assert not faltando, (caso_id, faltando)


def test_rotulo_gravado_pelo_assistente_de_projeto_abre_o_caso_de_secao(pagina: AppTest):
    _abrir_caso(pagina, "Viga de seção retangular")
    assert pagina.session_state["assistente_geometria"] == "Viga de seção retangular"
    assert any("Vigas de seção cheia" in str(c.value) for c in pagina.caption)


def test_rotulo_desconhecido_cai_no_painel(pagina: AppTest):
    _abrir_caso(pagina, "um rótulo que não existe mais")
    assert not pagina.session_state["assistente_geometria"]
    assert any("O que você precisa" in str(s.value) for s in pagina.subheader)


def test_procurar_um_caso_abre_ele(pagina: AppTest):
    pagina.selectbox(key="assistente_busca").set_value("rolamento").run()
    assert not pagina.exception
    assert pagina.session_state["assistente_geometria"] == "rolamento"


def test_ponto_a_mais_entra_na_varredura(pagina: AppTest):
    caso = "Viga de seção retangular"
    _abrir_caso(pagina, caso)
    pagina.toggle(key=chave_do_campo(caso, "ponto_extra")).set_value(True).run()
    pagina.number_input(key=chave_do_campo(caso, "y_extra_mm")).set_value(99.0).run()
    assert not pagina.exception
    assert any("dentro da altura" in str(e.value) for e in pagina.error)


def test_dado_invalido_vira_mensagem_na_pagina(pagina: AppTest):
    _abrir_caso(pagina, "Eixo circular vazado")
    pagina.number_input(key=chave_do_campo("Eixo circular vazado", "di_mm")).set_value(99.0).run()
    assert not pagina.exception
    assert any("diâmetro interno" in str(e.value) for e in pagina.error)


def test_mudar_o_controle_mostra_e_esconde_campos(pagina: AppTest):
    _abrir_caso(pagina, "chaveta")
    chave = chave_do_campo("chaveta", "b_mm")
    assert chave not in [campo.key for campo in pagina.number_input]
    pagina.selectbox(key=chave_do_campo("chaveta", "dimensoes")).set_value("Informar").run()
    assert not pagina.exception
    assert chave in [campo.key for campo in pagina.number_input]


def test_o_envio_abre_o_proximo_caso_preenchido(pagina: AppTest):
    _abrir_caso(pagina, "engrenagem")
    botoes = [b for b in pagina.button if "eixo do pinhão" in str(b.label)]
    assert botoes
    botoes[0].click().run()
    assert not pagina.exception
    assert pagina.session_state["assistente_geometria"] == "eixo_transmissao"
    forca = pagina.number_input(key=chave_do_campo("eixo_transmissao", "f1_fz_kN")).value
    assert forca > 0


def test_cadeia_do_eixo_ao_rolamento(pagina: AppTest):
    _abrir_caso(pagina, "eixo_transmissao")
    botoes = [b for b in pagina.button if "mancal A" in str(b.label)]
    botoes[0].click().run()
    assert not pagina.exception
    assert pagina.session_state["assistente_geometria"] == "rolamento"
    assert pagina.number_input(key=chave_do_campo("rolamento", "fr_kN")).value > 0


def test_material_do_catalogo_preenche_os_campos(pagina: AppTest):
    _abrir_caso(pagina, "eixo_secao")
    pagina.selectbox(key="assistente_material::eixo_secao").set_value(
        "AISI 4140 temperado e revenido"
    ).run()
    assert not pagina.exception
    assert pagina.number_input(key=chave_do_campo("eixo_secao", "sy_MPa")).value == 760.0
    assert pagina.number_input(key=chave_do_campo("eixo_secao", "sut_MPa")).value == 950.0


def test_tabela_de_verificacoes_aparece(pagina: AppTest):
    _abrir_caso(pagina, "cabo_tambor")
    assert any("Verificações" in str(m.value) for m in pagina.markdown)
    assert pagina.dataframe
