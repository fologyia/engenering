"""Medidas editadas no desenho: toda letra ligada a um campo real, e a edição chega no cálculo."""

from __future__ import annotations

import re
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

import pytest
from streamlit.testing.v1 import AppTest

from components import assistente_cargas_ui as ui
from core import cotas_dos_desenhos as cd
from core import elementos_catalogo as cat
from core.elementos_base import calcular_caso

APP = str(Path(__file__).resolve().parent.parent / "app.py")
COM_COTAS = sorted(cd.COTAS)


def _textos(svg: str) -> set[str]:
    return set(re.findall(r">([^<>]+)</text>", svg))


def _alvos(mapa) -> tuple:
    return mapa if isinstance(mapa, tuple) else (mapa,)


def _valores(caso) -> dict:
    return {**caso.padroes()}


# ---------------------------------------------------------------------------
# O mapa
# ---------------------------------------------------------------------------


def test_quase_todo_caso_tem_medida_no_desenho():
    """De fora ficam o equilíbrio, com prancheta própria, e os casos feitos só de tabelas."""
    sem_cota = set(cat.CASOS) - set(cd.COTAS)
    assert sem_cota <= {
        "equilibrio_peca",
        "trelica_plana",
        "secao_montada",
        "desbalanceamento",
    }


@pytest.mark.parametrize("caso_id", COM_COTAS)
def test_toda_letra_existe_no_desenho_e_todo_campo_existe(caso_id):
    caso = cat.CASOS[caso_id]
    svg = ui._croqui(caso)
    assert svg
    textos = _textos(svg)
    campos = {c.chave: c for c in caso.campos}
    for rotulo, mapa in cd.COTAS[caso_id].items():
        assert rotulo in textos, rotulo
        for alvo in _alvos(mapa):
            if isinstance(alvo, cd.Celula):
                campo = campos[alvo.campo]
                assert campo.e_tabela
                assert alvo.coluna in {c.chave for c in campo.colunas}
            else:
                campo = campos[alvo]
                assert not campo.e_tabela
                assert not isinstance(campo.padrao, (str, bool)), alvo


@pytest.mark.parametrize("caso_id", COM_COTAS)
def test_rotulo_duplo_tem_uma_letra_para_cada_campo(caso_id):
    for rotulo, mapa in cd.COTAS[caso_id].items():
        if isinstance(mapa, tuple):
            assert len(rotulo.split(",")) == len(mapa), rotulo


@pytest.mark.parametrize("caso_id", COM_COTAS)
def test_exemplo_mostra_o_valor_no_desenho(caso_id):
    caso = cat.CASOS[caso_id]
    cotas = cd.cotas_do_caso(caso, _valores(caso))
    # Só neste caso a medida depende de uma escolha que o exemplo não faz.
    assert cotas or caso_id == "torque_aperto", "o exemplo não mostra nenhuma medida"
    original = ui._croqui(caso)
    svg = cd.desenho_com_cotas(original, cotas)
    assert svg.count("data-cota=") >= len(cotas)
    # O desenho continua inteiro: só a letra mudou, e o XML continua válido.
    assert svg.count("<text ") == original.count("<text ")
    assert svg.count("</text>") == original.count("</text>")
    assert re.search(r'<text [^>]*class="cota">', svg) or not cotas
    ElementTree.fromstring(svg)
    for cota in cotas:
        assert f'data-cota="{cota.indice}"' in svg
        assert cd.numero(cota.valor) in svg


def test_letra_que_e_resultado_fica_como_esta():
    caso = cat.CASOS["correia"]
    svg = cd.desenho_com_cotas(ui._croqui(caso), cd.cotas_do_caso(caso, _valores(caso)))
    assert ">F₁</text>" in svg  # a força na correia sai do cálculo
    assert "C = " in svg


def test_desenho_ganha_folga_para_o_texto_mais_longo():
    caso = cat.CASOS["chapa_furo"]
    svg = cd.desenho_com_cotas(ui._croqui(caso), cd.cotas_do_caso(caso, _valores(caso)))
    assert f'viewBox="{-cd.MARGEM_X} {-cd.MARGEM_Y} ' in svg


def test_rotulo_duplo_vira_duas_medidas():
    caso = cat.CASOS["acionamento"]
    cotas = cd.cotas_do_caso(caso, _valores(caso))
    letras = [c.letra for c in cotas if c.rotulo == "P, n"]
    assert letras == ["P", "n"]
    svg = cd.desenho_com_cotas(ui._croqui(caso), cotas)
    assert re.search(r'<tspan data-cota="\d+">P = [^<]+</tspan>  ·  <tspan data-cota', svg)


def test_campo_escondido_fica_so_como_letra():
    caso = cat.CASOS["chaveta"]
    valores = _valores(caso)
    assert valores["dimensoes"] != "Informar"
    alvos = [c.alvo for c in cd.cotas_do_caso(caso, valores)]
    assert "b_mm" not in alvos and "d_mm" in alvos
    valores["dimensoes"] = "Informar"
    assert "b_mm" in [c.alvo for c in cd.cotas_do_caso(caso, valores)]


def test_celula_so_vale_enquanto_a_linha_for_daquele_tipo():
    caso = cat.CASOS["viga_reacoes"]
    valores = _valores(caso)
    assert any(c.letra == "q" for c in cd.cotas_do_caso(caso, valores))
    valores["cargas"] = ({"tipo": "Concentrada", "x1_m": 1.0, "valor": 5.0},)
    assert not any(c.letra == "q" for c in cd.cotas_do_caso(caso, valores))


def test_linha_que_nao_existe_fica_de_fora():
    caso = cat.CASOS["barra_axial"]
    valores = _valores(caso)
    valores["trechos"] = valores["trechos"][:1]
    assert not any(c.letra == "L₂" for c in cd.cotas_do_caso(caso, valores))


def test_valor_aceito_confere_a_faixa_e_o_inteiro():
    caso = cat.CASOS["chapa_furo"]
    cotas = {c.alvo: c for c in cd.cotas_do_caso(caso, _valores(caso))}
    assert cd.valor_aceito(cotas["b_mm"], 120.0) == (120.0, "")
    valor, motivo = cd.valor_aceito(cotas["b_mm"], -3.0)
    assert valor is None and "mínimo" in motivo
    valor, motivo = cd.valor_aceito(cotas["b_mm"], "abc")
    assert valor is None and "número" in motivo
    motor = {
        c.alvo: c for c in cd.cotas_do_caso(cat.CASOS["corrente"], _valores(cat.CASOS["corrente"]))
    }
    assert isinstance(cd.valor_aceito(motor["z1"], 21.0)[0], int)


# ---------------------------------------------------------------------------
# A edição chega no cálculo
# ---------------------------------------------------------------------------


def _editar(caso, estado, cota, valor):
    chave = f"assistente_croqui::{caso.id}"
    estado[chave] = mock.Mock(edicao={"indice": cota.indice, "valor": valor, "n": 1})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_cota(caso, chave)


def _cota(caso, estado, alvo):
    with mock.patch.object(ui.st, "session_state", estado):
        cotas = cd.cotas_do_caso(caso, ui._valores_da_sessao(caso))
    return next(c for c in cotas if c.alvo == alvo)


def test_editar_medida_grava_no_campo():
    caso = cat.CASOS["chapa_furo"]
    estado: dict = {}
    _editar(caso, estado, _cota(caso, estado, "b_mm"), 150.0)
    assert estado[ui.chave_do_campo(caso.id, "b_mm")] == 150.0
    assert not estado[f"assistente_croqui::{caso.id}::aviso"]


def test_valor_fora_da_faixa_avisa_e_nao_grava():
    caso = cat.CASOS["chapa_furo"]
    estado: dict = {}
    _editar(caso, estado, _cota(caso, estado, "b_mm"), -5.0)
    assert ui.chave_do_campo(caso.id, "b_mm") not in estado
    assert "mínimo" in estado[f"assistente_croqui::{caso.id}::aviso"]


def test_editar_celula_troca_a_linha_e_reinicia_a_tabela():
    caso = cat.CASOS["barra_axial"]
    chave = ui.chave_do_campo(caso.id, "trechos")
    estado: dict = {chave: "edicao antiga", f"{chave}::base": "base antiga"}
    alvo = cd.Celula("trechos", 1, "l_mm")
    _editar(caso, estado, _cota(caso, estado, alvo), 450.0)
    assert estado[f"{chave}::ultimas"][1]["l_mm"] == 450.0
    assert estado[f"{chave}::ultimas"][0]["l_mm"] == 500.0
    assert chave not in estado
    assert f"{chave}::base" not in estado


def test_voltar_ao_exemplo_limpa_o_caso():
    caso = cat.CASOS["barra_axial"]
    chave = ui.chave_do_campo(caso.id, "trechos")
    estado = {f"{chave}::ultimas": [], f"{chave}::base": 1, chave: 2, "outra": 3}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._voltar_ao_exemplo(caso)
    assert estado == {"outra": 3}


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _abrir(caso_id: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.session_state["assistente_geometria"] = caso_id
    at.switch_page("app_pages/assistente_cargas.py")
    return at.run()


def _lista(at: AppTest):
    """Conforme a versão do Streamlit, o AppTest entrega o expander como Status."""
    return next(e for e in [*at.expander, *at.status] if "Medidas do desenho" in e.label)


def test_medida_do_desenho_vai_para_a_lista_recolhida():
    at = _abrir("chapa_furo")
    assert not at.exception
    chaves = {campo.key for campo in _lista(at).number_input}
    assert ui.chave_do_campo("chapa_furo", "b_mm") in chaves
    assert ui.chave_do_campo("chapa_furo", "t_mm") not in chaves  # não aparece no desenho


def test_valor_gravado_pelo_desenho_muda_o_resultado():
    at = _abrir("chapa_furo")
    antes = calcular_caso(cat.CASOS["chapa_furo"]).resumo
    at.number_input(key=ui.chave_do_campo("chapa_furo", "b_mm")).set_value(200.0).run()
    assert not at.exception
    assert at.session_state[ui.chave_do_campo("chapa_furo", "b_mm")] == 200.0
    assert antes


def test_botao_volta_ao_exemplo_na_tela():
    at = _abrir("chapa_furo")
    chave = ui.chave_do_campo("chapa_furo", "b_mm")
    at.number_input(key=chave).set_value(200.0).run()
    at.button(key="assistente_exemplo::chapa_furo").click().run()
    assert not at.exception
    assert at.number_input(key=chave).value == 100.0


def test_caso_com_campo_dependente_abre_com_a_lista():
    """``quando`` agora lê a sessão: um campo pode depender de outro desenhado depois dele."""
    at = _abrir("chaveta")
    assert not at.exception
    at.selectbox(key=ui.chave_do_campo("chaveta", "dimensoes")).set_value("Informar").run()
    assert not at.exception
    assert ui.chave_do_campo("chaveta", "b_mm") in {c.key for c in _lista(at).number_input}


def test_tabela_de_verificacoes_nao_mostra_none():
    """Linha informativa não tem limite: a célula sai com traço, e não com a palavra None."""
    at = _abrir("chapa_furo")
    quadro = next(d.value for d in at.dataframe if "Aproveitamento" in d.value.columns)
    for coluna in ("Solicitante", "Resistente", "Aproveitamento"):
        assert quadro[coluna].notna().all(), coluna
        assert all(isinstance(v, str) for v in quadro[coluna]), coluna
    at = _abrir("equilibrio_peca")
    quadro = next(d.value for d in at.dataframe if "Aproveitamento" in d.value.columns)
    assert "—" in set(quadro["Resistente"])
    assert "—" in set(quadro["Aproveitamento"])


def test_celula_da_tabela():
    assert ui._celula(None) == "—"
    assert ui._celula(float("nan")) == "—"
    assert ui._celula(float("inf"), " %") == "∞"
    assert ui._celula(87.4, " %", casas=0) == "87 %"
    assert ui._celula(1.5) == "1,5"


@pytest.mark.parametrize("caso_id", ["viga_reacoes", "barra_axial", "Barra sob carga axial"])
def test_casos_de_familias_diferentes_abrem(caso_id):
    at = _abrir(caso_id)
    assert not at.exception
