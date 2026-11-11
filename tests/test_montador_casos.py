"""Montador: casos de carga na mesma montagem, e a resposta do pior."""

from __future__ import annotations

import json

import pytest

from core import montador as mt
from core import montador_casos as mcs
from core import montador_grandezas as g
from core import montador_registro as rg
from core.montador_grandezas import unidades_padrao
from tests.test_montador_pacotes import BASE, RET, _dados, _tela, abrir

PAGINA = "app_pages/montador_formulas.py"
U = unidades_padrao(g.SISTEMA_SOLIDOS)


def _base() -> mt.Montagem:
    return mt.montar(mt.grafo_de_dados(_dados(*RET)))


def _h(valores) -> float:
    return mt.isolar(_base(), "h", valores).valor


def _com(*casos):
    return mt.com_casos(_base(), BASE, "h", "Regime", casos)


# ---------------------------------------------------------------------------
# Conta
# ---------------------------------------------------------------------------


def test_o_caso_mais_carregado_manda():
    conta, avisos = _com(("Partida", {"M_x": 4e6}))
    assert not avisos
    r = mt.isolar(conta, "h", BASE)
    assert r.valor == pytest.approx(_h({**BASE, "M_x": 4e6}))
    assert r.manda.condicao.caso == "Partida"
    assert r.manda.condicao.nome.startswith("Partida: ")


def test_caso_mais_leve_nao_muda_a_resposta():
    conta, _ = _com(("Vazio", {"M_x": 1e6}))
    r = mt.isolar(conta, "h", BASE)
    assert r.valor == pytest.approx(_h(BASE))
    assert r.manda.condicao.caso == "Regime"


def test_cada_caso_tem_as_condicoes_dele():
    conta, _ = _com(("Partida", {"M_x": 4e6}), ("Vazio", {"M_x": 1e6}))
    casos = {c.caso for c in conta.condicoes}
    assert casos == {"Regime", "Partida", "Vazio"}
    assert len(conta.condicoes) == 3 * len(_base().condicoes)


def test_resposta_de_cada_caso():
    conta, _ = _com(("Partida", {"M_x": 4e6}), ("Vazio", {"M_x": 1e6}))
    r = mt.isolar(conta, "h", BASE)
    por_caso = dict(mcs.resposta_de_cada_caso(r))
    assert por_caso["Partida"].valor == pytest.approx(_h({**BASE, "M_x": 4e6}))
    assert por_caso["Vazio"].valor == pytest.approx(_h({**BASE, "M_x": 1e6}))
    assert por_caso["Regime"].valor == pytest.approx(_h(BASE))


def test_esforco_zero_num_caso_nao_vira_zero_sobre_zero():
    conta, _ = _com(("Sem cortante", {"V_y": 0.0}))
    r = mt.isolar(conta, "h", BASE)
    assert r.valor == pytest.approx(_h(BASE))
    por_caso = dict(mcs.resposta_de_cada_caso(r))
    assert por_caso["Sem cortante"].valor == pytest.approx(_h({**BASE, "V_y": 0.0}))


def test_esforco_zero_no_inspetor_nao_perde_os_casos():
    """Com V_y = 0 no inspetor, a conta é refeita sem a cortante: os casos continuam lá."""
    conta, _ = _com(("Partida", {"M_x": 4e6}))
    r = mt.isolar(conta, "h", {**BASE, "V_y": 0.0})
    assert r.manda.condicao.caso == "Partida"
    assert r.valor == pytest.approx(_h({**BASE, "M_x": 4e6, "V_y": 0.0}))


def test_valor_adotado_confere_todos_os_casos():
    conta, _ = _com(("Partida", {"M_x": 4e6}))
    entre = (_h(BASE) + _h({**BASE, "M_x": 4e6})) / 2
    r = mt.isolar(conta, "h", BASE, adotado=entre)
    pior = max(r.conferencia_adotada, key=lambda linha: linha.uso)
    assert pior.uso > 1.0 and pior.nome.startswith("Partida: ")


def test_letra_pedida_nunca_muda_de_caso():
    conta, _ = _com(("Errado", {"h": 10.0, "M_x": 4e6}))
    assert dict(conta.casos)["Errado"] == (("M_x", 4e6),)


def test_valor_ruim_no_caso_avisa_com_o_nome():
    conta, avisos = _com(("Partida", {"M_x": 4e6, "n": -1.0}))
    assert avisos and avisos[0].startswith("Partida: ")
    assert mt.isolar(conta, "h", BASE).valor == pytest.approx(_h({**BASE, "M_x": 4e6}))


def test_nomes_repetidos_ficam_diferentes():
    conta, _ = _com(("Regime", {"M_x": 4e6}), ("", {"M_x": 3e6}))
    nomes = [nome for nome, _ in conta.casos]
    assert len(set(nomes)) == 2 and "Regime" not in nomes


def test_numeros_do_caso_que_manda():
    conta, _ = _com(("Partida", {"M_x": 4e6}))
    r = mt.isolar(conta, "h", BASE)
    assert mt.valores_do_caso(r)["M_x"] == 4e6
    assert r.valores_usados["M_x"] == 2e6


def test_sem_casos_a_montagem_e_a_mesma():
    base = _base()
    assert mt.com_casos(base, BASE, "h", "Caso 1", ())[0] is base


# ---------------------------------------------------------------------------
# Estado, arquivo e registro
# ---------------------------------------------------------------------------


def _estado(ligado=True):
    return {
        "ligado": ligado,
        "base": "Regime",
        "letras": ["M_x"],
        "lista": [{"nome": "Partida", "valores": {"M_x": 4e6, "V_y": 5e4}}],
    }


def test_so_as_letras_escolhidas_entram_na_conta():
    base, casos = mcs.para_a_conta(_estado())
    assert base == "Regime"
    assert casos == (("Partida", {"M_x": 4e6}),)
    assert mcs.para_a_conta(_estado(ligado=False)) == ("Caso 1", ())


@pytest.mark.parametrize(
    "bruto",
    [
        None,
        "lixo",
        {"lista": "lixo"},
        {"ligado": True, "lista": [None, {"valores": {"M_x": "dois"}}, {"valores": ["x"]}]},
        {"ligado": True, "lista": [{"nome": "x" * 500, "valores": {"M_x": float("nan")}}]},
    ],
)
def test_estado_estragado_nao_quebra(bruto):
    casos = mcs.normalizar(bruto)
    mcs.para_a_conta(bruto)
    if casos is not None:
        assert all(len(item["nome"]) <= mcs.TAMANHO_DO_NOME for item in casos["lista"])
        assert all(item["valores"] == {} for item in casos["lista"])


def test_no_maximo_doze_casos():
    bruto = {**_estado(), "lista": [{"nome": f"C{i}", "valores": {}} for i in range(40)]}
    assert len(mcs.normalizar(bruto)["lista"]) == mcs.MAXIMO_DE_CASOS


def _doc(casos=None):
    return rg.documento("solidos", _dados(*RET), BASE, {}, "h", None, U.escolhas, casos)


def test_arquivo_leva_e_traz_os_casos():
    doc = _doc(_estado())
    lido = rg.ler_documento(rg.em_json(doc), "solidos", g.SISTEMA_SOLIDOS)
    assert lido["casos"]["lista"][0]["nome"] == "Partida"
    assert lido["casos"]["base"] == "Regime"


def test_arquivo_sem_casos_continua_igual():
    doc = _doc()
    assert "casos" not in doc
    lido = rg.ler_documento(rg.em_json(doc), "solidos", g.SISTEMA_SOLIDOS)
    assert lido["casos"] is None


def test_mudar_um_caso_muda_a_assinatura():
    outro = _estado()
    outro["lista"][0]["valores"]["M_x"] = 5e6
    assert rg.assinatura(_doc(_estado())) != rg.assinatura(_doc(outro))
    assert rg.assinatura(_doc()) != rg.assinatura(_doc(_estado()))


def test_registro_diz_qual_caso_manda():
    conta, _ = _com(("Partida", {"M_x": 4e6}))
    r = mt.isolar(conta, "h", BASE)
    registro = rg.registro_tecnico(
        modulo="Montador de fórmulas",
        modulo_id="montador_formulas",
        dominio="solidos",
        titulo="Teste",
        resposta=r,
        montagem=r.montagem,
        doc=_doc(_estado()),
        u=U,
    )
    assert registro["resultados"]["caso_que_manda"] == "Partida"
    assert registro["entradas"]["casos_de_carga"]["Partida"] == {"M_x (kN·m)": pytest.approx(4.0)}
    json.dumps(registro)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def test_ligar_os_casos_na_tela():
    at = abrir(PAGINA)
    at.toggle(key="mf_casos_ligado").set_value(True).run()
    assert not at.exception
    casos = at.session_state["mf_casos"]
    assert casos["ligado"] and casos["lista"][0]["nome"] == "Caso 2"
    assert "M_x" in casos["letras"]
    # O Caso 2 nasce igual ao primeiro: a resposta não muda.
    assert any("h ≥ 37,95 mm" in s.value for s in at.success)


def test_caso_mais_carregado_na_tela():
    at = abrir(PAGINA)
    at.session_state["mf_casos"] = {
        "ligado": True,
        "base": "Regime",
        "letras": ["M_x"],
        "lista": [{"nome": "Partida", "valores": {"M_x": 4e6}}],
    }
    at.run()
    assert not at.exception
    esperado = _h({**BASE, "M_x": 4e6})
    texto = f"{esperado:.2f}".replace(".", ",")
    assert any(texto in s.value and "Partida" in s.value for s in at.success)
    assert "Partida: von Mises" in _tela(at)
    quadro = next(d.value for d in at.dataframe if "Quem manda no caso" in d.value.columns)
    assert list(quadro["Caso"]) == ["Regime", "Partida"]
    assert list(quadro["Manda"]) == ["", "●"]
    novos = [
        w
        for w in (*at.toggle, *at.text_input, *at.multiselect)
        if (w.key or "").startswith("mf_casos_")
    ]
    assert len(novos) == 3
    for widget in novos:
        assert widget.help and widget.help.strip()[-1] in ".!:", widget.label


def test_ctrl_z_desfaz_os_casos():
    at = abrir(PAGINA)
    at.toggle(key="mf_casos_ligado").set_value(True).run()
    assert at.session_state["mf_casos"]["ligado"]
    historico = at.session_state["mf_historico"]
    assert historico["passado"], "ligar os casos entra no histórico"


def test_trocar_de_modelo_desliga_os_casos():
    at = abrir(PAGINA)
    at.toggle(key="mf_casos_ligado").set_value(True).run()
    at.selectbox(key="mf_modelo").set_value("Eixo com flexão e torção").run()
    assert not at.exception
    assert at.session_state["mf_casos"] is None


def test_editar_a_tabela_dos_casos(monkeypatch):
    """O que o st.data_editor manda (linha editada, linha nova) vira os casos, na base."""
    from components import montador_ui as mui
    from core.montador_modelos import PARTE_SOLIDOS

    estado = {
        "mf_casos": {
            "ligado": True,
            "base": "Regime",
            "letras": ["M_x"],
            "lista": [{"nome": "Caso 2", "valores": {"M_x": 2e6}}],
        },
        "mf_casos_tabela_0": {
            "edited_rows": {0: {"Caso": "Partida", "M_x (kN·m)": 4.0}},
            "added_rows": [{"Caso": "", "M_x (kN·m)": None}],
            "deleted_rows": [],
        },
    }
    monkeypatch.setattr(mui.st, "session_state", estado)
    mui._ao_editar_casos(PARTE_SOLIDOS, "mf_casos_tabela_0", [("M_x (kN·m)", "M_x", 1e6)])
    assert estado["mf_casos"]["lista"] == [
        {"nome": "Partida", "valores": {"M_x": 4e6}},
        {"nome": "Caso 3", "valores": {}},
    ]
    assert estado["mf_casos_rev"] == 1  # a tabela nasce de novo, sem a edição pendente


def test_formula_do_caso_sem_ponto_zero():
    conta, _ = _com(("Partida", {"M_x": 4e6}))
    r = mt.isolar(conta, "h", BASE)
    assert "24000000.0" not in r.manda.formula.latex
