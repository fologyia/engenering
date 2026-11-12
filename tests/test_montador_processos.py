"""Montador de processos: a ponte entre o térmico e os fluidos, contra a conta feita à mão."""

from __future__ import annotations

import math
from pathlib import Path

import CoolProp.CoolProp as CP
import pytest
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_registro as rg
from core.montador_funcoes import fator_de_atrito

#: Caminho inteiro: no Linux, o AppTest procura um caminho solto ao lado deste arquivo.
APP = str(Path(__file__).resolve().parents[1] / "app.py")
PROCESSOS = g.SISTEMA_PROCESSOS


def _do_modelo(parte: mm.Parte, nome: str, **trocas: float) -> tuple[mt.Montagem, mt.Resposta]:
    modelo = parte.por_nome[nome]
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not m.erros, m.erros
    letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
    return m, mt.isolar(m, modelo.alvo, {**letras, **dict(m.padroes), **modelo.valores, **trocas})


# ---------------------------------------------------------------------------
# Os três modelos, à mão
# ---------------------------------------------------------------------------


def test_do_calor_a_vazao_e_ao_tubo():
    """O calor pedido acha a vazão (letra do meio), e a velocidade dá o diâmetro."""
    _, r = _do_modelo(mm.PARTE_PROCESSOS, "Resfriar com água: vazão e diâmetro do tubo")
    h30 = CP.PropsSI("H", "T", 303.15, "P", 3e5, "Water")
    h40 = CP.PropsSI("H", "T", 313.15, "P", 3e5, "Water")
    vazao = 200e3 / (h40 - h30)
    rho = CP.PropsSI("D", "T", 303.15, "P", 3e5, "Water")
    assert dict(r.do_meio)["mdot"] == pytest.approx(vazao, rel=1e-9)
    assert r.valor == pytest.approx(math.sqrt(4 * (vazao / rho) / (math.pi * 2.0)), rel=1e-9)
    assert r.sentido == mt.MINIMO
    assert not r.faltam and not r.alertas


def test_succao_de_agua_quente_usa_a_pressao_de_vapor_do_estado():
    _, quente = _do_modelo(mm.PARTE_PROCESSOS, "Bomba de água quente: altura de sucção")
    _, morna = _do_modelo(mm.PARTE_PROCESSOS, "Bomba de água quente: altura de sucção", T=313.15)
    assert quente.valor is not None and morna.valor is not None
    assert morna.valor > quente.valor > 0.0
    # À mão, com a água a 80 °C: NPSH disponível menos o requerido e a perda.
    rho = CP.PropsSI("D", "T", 353.15, "P", 101325.0, "Water")
    mu = CP.PropsSI("V", "T", 353.15, "P", 101325.0, "Water")
    pv = CP.PropsSI("P", "T", 353.15, "Q", 0, "Water")
    v = 4 * (5.0 / rho) / (math.pi * 0.08**2)
    f = fator_de_atrito(rho * v * 0.08 / mu, 0.045e-3 / 0.08)
    perda = (f * 6.0 / 0.08 + 3.0) * v**2 / (2 * 9.81)
    assert quente.valor == pytest.approx((101325.0 - pv) / (rho * 9.81) - 3.0 - perda, rel=1e-6)


def _pressao_na_chegada(pb: float) -> float:
    h1 = CP.PropsSI("H", "P", 75e3, "Q", 0, "Water")
    s1 = CP.PropsSI("S", "P", 75e3, "Q", 0, "Water")
    h2 = h1 + (CP.PropsSI("H", "P", pb, "S", s1, "Water") - h1) / 0.75
    rho = CP.PropsSI("D", "P", pb, "H", h2, "Water")
    mu = CP.PropsSI("V", "P", pb, "H", h2, "Water")
    v = 4 * (2.0 / rho) / (math.pi * 0.04**2)
    f = fator_de_atrito(rho * v * 0.04 / mu, 0.045e-3 / 0.04)
    perda = (f * 80.0 / 0.04 + 6.0) * v**2 / (2 * 9.81)
    return pb - rho * 9.81 * (perda + 15.0)


def test_pressao_da_bomba_para_chegar_na_caldeira():
    """A bomba térmica alimenta a linha, e a perda do tubo volta para a corrente."""
    _, r = _do_modelo(mm.PARTE_PROCESSOS, "Da bomba à caldeira: pressão que a bomba precisa")
    assert r.valor is not None and r.sentido == mt.MINIMO
    assert _pressao_na_chegada(r.valor) == pytest.approx(3e6, rel=1e-9)
    assert r.valor > 3e6 + 990.0 * 9.81 * 15.0  # mais que o desnível sozinho


def test_desnivel_tira_pressao_e_entalpia():
    modelo = mm.PARTE_PROCESSOS.por_nome["Da bomba à caldeira: pressão que a bomba precisa"]
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
    valores = {**letras, **dict(m.padroes), **modelo.valores, "p_b": 3.3e6}
    numeros = {g.simbolo_de(k): v for k, v in valores.items()}
    antes, depois = m.saidas["b1"]["saida"], m.saidas["d1"]["saida"]
    queda = mt.numero_de(antes.h - depois.h, numeros)
    assert queda == pytest.approx(9.81 * 15.0)  # g·Δz: a energia que virou altura
    assert mt.numero_de(depois.p, numeros) == pytest.approx(_pressao_na_chegada(3.3e6), rel=1e-9)


def test_corrente_com_duas_fases_avisa_na_linha():
    modelo = mm.PARTE_PROCESSOS.por_nome["Bomba de água quente: altura de sucção"]
    dados = modelo.grafo()
    for no in dados["nos"]:
        if no["tipo"] == "estado":
            no["opcoes"]["como"] = "Título e pressão (mistura)"
    m = mt.montar(mt.grafo_de_dados(dados))
    valores = {**{i.chave: i.padrao for i in m.grandezas if i.padrao is not None}}
    valores.update({**dict(m.padroes), **modelo.valores, "x": 0.5})
    r = mt.isolar(m, "D", {k: v for k, v in valores.items() if k != "D"} | {"z_s": 1.0})
    # Sem resposta (a mistura não tem viscosidade), o aviso que explica o motivo aparece assim mesmo.
    assert not r.faltam
    assert any("líquido e vapor misturados" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# O que passa de uma página para a outra
# ---------------------------------------------------------------------------


def test_biblioteca_de_processos_junta_as_duas_e_a_ponte():
    chaves = {b["chave"] for b in mb.catalogo_para_tela(mb.PROCESSOS)}
    assert {
        "estado",
        "bomba_termica",
        "trecho",
        "npsh",
        "linha_da_corrente",
        mb.RESULTADO,
    } <= chaves
    assert "circular" not in chaves  # seção é dos sólidos
    fluidos = {b["chave"] for b in mb.catalogo_para_tela(mb.FLUIDOS)}
    termico = {b["chave"] for b in mb.catalogo_para_tela(mb.TERMICO)}
    assert "estado" not in fluidos and "trecho" not in termico
    assert "linha_da_corrente" not in fluidos | termico


def test_unidades_de_processos_cobrem_as_duas_partes():
    u = g.unidades_padrao(PROCESSOS)
    for sistema in (g.SISTEMA_FLUIDOS, g.SISTEMA_TERMICO):
        for dimensao in sistema.dimensoes:
            assert dimensao in PROCESSOS.dimensoes, dimensao
            if dimensao != g.PURO:
                assert u.rotulo(dimensao), dimensao
    letras = g.letras_conhecidas(PROCESSOS.chave)
    assert {"D", "T", "mdot", "Delta_z", "p_b", "K_L"} <= set(letras)
    assert u.para_base(g.TEMPERATURA, 80.0) == pytest.approx(353.15)
    assert u.para_base(g.DIAMETRO, 50.0) == pytest.approx(0.05)


@pytest.mark.parametrize(
    ("parte", "nome"),
    [
        (mm.PARTE_FLUIDOS, "Diâmetro mínimo do tubo"),
        (mm.PARTE_TERMICA, "Ciclo Rankine simples"),
    ],
)
def test_montagem_de_fluidos_ou_do_termico_abre_em_processos_com_a_mesma_resposta(parte, nome):
    modelo = parte.por_nome[nome]
    m, r = _do_modelo(parte, nome)
    valores = {**{i.chave: i.padrao for i in m.grandezas if i.padrao is not None}}
    valores.update({**dict(m.padroes), **modelo.valores})
    unidades = [s.padrao for s in parte.sistema.seletores]
    doc = rg.documento(parte.dominio, modelo.grafo(), valores, {}, modelo.alvo, None, unidades)
    aberto = rg.ler_documento(rg.em_json(doc), mb.PROCESSOS, PROCESSOS)
    assert aberto["dominio"] == mb.PROCESSOS
    assert aberto["unidades"] == [s.padrao for s in PROCESSOS.seletores]
    de_novo = mt.isolar(
        mt.montar(mt.grafo_de_dados(aberto["grafo"])), aberto["alvo"], aberto["valores"]
    )
    assert de_novo.valor == pytest.approx(r.valor, rel=1e-12)


def test_fluidos_nao_abre_montagem_do_termico():
    modelo = mm.PARTE_TERMICA.por_nome["Ciclo Rankine simples"]
    doc = rg.documento(mb.TERMICO, modelo.grafo(), dict(modelo.valores), {}, modelo.alvo, None, [])
    with pytest.raises(rg.ErroDeArquivo):
        rg.ler_documento(rg.em_json(doc), mb.FLUIDOS, g.SISTEMA_FLUIDOS)


def test_conjunto_salvo_nos_fluidos_aparece_em_processos(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "ARQUIVO_USUARIO", tmp_path / "conjuntos.json")
    conjunto = {"grafo": {"nos": [{"id": "n1", "tipo": "trecho"}], "fios": []}, "portas": {}}
    mc.salvar("Trecho de teste", mb.FLUIDOS, conjunto)
    assert [c.nome for c in mc.listar(mb.PROCESSOS)] == ["Trecho de teste"]
    assert [c.nome for c in mc.listar(mb.FLUIDOS)] == ["Trecho de teste"]
    assert mc.listar(mb.TERMICO) == []
    assert mc.listar(mb.SOLIDOS) == []


def test_letra_do_meio_vai_para_o_registro_e_para_outro_calculo():
    parte = mm.PARTE_PROCESSOS
    modelo = parte.por_nome["Resfriar com água: vazão e diâmetro do tubo"]
    m, r = _do_modelo(parte, modelo.nome)
    u = g.unidades_padrao(PROCESSOS)
    doc = rg.documento(
        parte.dominio, modelo.grafo(), dict(modelo.valores), {}, modelo.alvo, None, list(u.escolhas)
    )
    registro = rg.registro_tecnico(
        modulo=parte.titulo,
        modulo_id=parte.modulo_id,
        dominio=parte.dominio,
        titulo="Resfriamento",
        resposta=r,
        montagem=m,
        doc=doc,
        u=u,
    )
    assert registro["resultados"]["ṁ (kg/s)"] == pytest.approx(4.786, abs=1e-3)
    assert registro["resultados"]["D (mm)"] == pytest.approx(55.32, abs=0.01)
    publicas = {s["chave"]: s for s in registro["saidas_publicas"]}
    assert publicas["mdot"]["valor"] == pytest.approx(4.786, abs=1e-3)
    # O D achado aqui entra nos sólidos como medida, em mm.
    projeto = {"registros_tecnicos": [{**registro, "id": "r1"}]}
    fontes = rg.fontes_do_projeto(projeto, mb.SOLIDOS, g.unidades_padrao(g.SISTEMA_SOLIDOS))
    do_tubo = next(f for f in fontes if f.campo == "D")
    assert do_tubo.dimensao == g.MEDIDA
    assert float(rg.opcoes_da_fonte(do_tubo)["valor"]) == pytest.approx(55.32, abs=0.01)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def test_pagina_de_processos_abre_e_cada_modelo_responde():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_processos.py").run()
    assert not at.exception
    for modelo in mm.MODELOS_DE_PROCESSOS:
        at.selectbox(key="mpr_modelo").set_value(modelo.nome).run()
        assert not at.exception, modelo.nome
        assert at.success, modelo.nome
    tabelas = [d.value for d in at.dataframe]
    assert any("Ponto" in t.columns for t in tabelas)  # a tabela de estados também vale aqui


@pytest.mark.parametrize(
    ("pagina", "prefixo", "modelo"),
    [
        ("montador_fluidos", "mfl", "Diâmetro mínimo do tubo"),
        ("montador_termico", "mte", "Ciclo Rankine simples"),
    ],
)
def test_botao_leva_a_montagem_inteira_para_processos(pagina, prefixo, modelo):
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page(f"app_pages/{pagina}.py").run()
    at.selectbox(key=f"{prefixo}_modelo").set_value(modelo).run()
    antes = at.success[0].value
    blocos = [n["tipo"] for n in at.session_state[f"{prefixo}_grafo"]["nos"]]
    at.button(key=f"{prefixo}_abrir_em_processos").click().run()
    assert not at.exception
    assert [n["tipo"] for n in at.session_state["mpr_grafo"]["nos"]] == blocos
    assert at.success[0].value == antes  # a mesma resposta, agora na página que liga os dois
    assert at.session_state[f"{prefixo}_grafo"]["nos"]  # a de origem continua como estava


def test_solidos_nao_oferecem_continuar_em_processos():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    assert not [b for b in at.button if b.key == "mf_abrir_em_processos"]
