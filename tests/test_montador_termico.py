"""Montador térmico: cada bloco contra a CoolProp chamada direto, e os ciclos contra Çengel e Boles."""

from __future__ import annotations

import math

import CoolProp.CoolProp as CP
import pytest
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_termico as mte

APP = "app.py"
AGUA, R134A, AR = "Água", "R134a", "Ar seco"


def no(id_: str, tipo: str, **opcoes: str) -> dict:
    return {"id": id_, "tipo": tipo, "opcoes": opcoes}


def fio(de: str, saida: str, para: str, entrada: str) -> dict:
    return {"de": de, "saida": saida, "para": para, "entrada": entrada}


def montar(nos: list[dict], fios: list[dict]) -> mt.Montagem:
    m = mt.montar(mt.grafo_de_dados({"nos": [*nos, no("r", mb.RESULTADO)], "fios": fios}))
    assert not m.erros, m.erros
    return m


def ao_resultado(id_: str) -> dict:
    return fio(id_, "condicao", "r", "condicoes")


def numero(m: mt.Montagem, no_id: str, porta: str, valores: dict, ler=lambda x: x) -> float:
    numeros = {g.simbolo_de(k): v for k, v in valores.items()}
    valor = mt.numero_de(ler(m.saidas[no_id][porta]), numeros)
    assert valor is not None
    return valor


# ---------------------------------------------------------------------------
# Blocos, um a um
# ---------------------------------------------------------------------------


def _estado_e(tipo: str, fluido: str, **opcoes: str) -> tuple[list[dict], list[dict]]:
    nos = [no("e", "estado", fluido=fluido), no("x", tipo, **opcoes), no("t", "temperatura_maxima")]
    fios = [fio("e", "saida", "x", "entrada"), fio("x", "saida", "t", "entrada"), ao_resultado("t")]
    return nos, fios


def test_estado_por_temperatura_e_pressao_e_o_da_coolprop():
    m = montar(*_estado_e("valvula", AGUA))
    valores = {"T": 333.15, "p": 3e5, "m_dot": 2.0, "p_vl": 2e5, "T_max": 400.0}
    h = numero(m, "e", "saida", valores, lambda c: c.h)
    assert h == pytest.approx(CP.PropsSI("H", "T", 333.15, "P", 3e5, "Water"), rel=1e-9)


@pytest.mark.parametrize(
    ("como", "letras", "esperado"),
    [
        (mte.LIQUIDO_PELA_PRESSAO, {"p": 2e5}, ("P", 2e5, "Q", 0)),
        (mte.VAPOR_PELA_PRESSAO, {"p": 2e5}, ("P", 2e5, "Q", 1)),
        (mte.TITULO_E_PRESSAO, {"p": 2e5, "x": 0.4}, ("P", 2e5, "Q", 0.4)),
        (mte.LIQUIDO_PELA_TEMPERATURA, {"T": 373.15}, ("T", 373.15, "Q", 0)),
        (mte.VAPOR_PELA_TEMPERATURA, {"T": 373.15}, ("T", 373.15, "Q", 1)),
    ],
)
def test_cada_jeito_de_dar_o_estado(como, letras, esperado):
    nos = [no("e", "estado", fluido=AGUA, como=como), no("t", "temperatura_maxima")]
    m = montar(nos, [fio("e", "saida", "t", "entrada"), ao_resultado("t")])
    h = numero(m, "e", "saida", {**letras, "m_dot": 1.0}, lambda c: c.h)
    a, va, b, vb = esperado
    assert h == pytest.approx(CP.PropsSI("H", a, va, b, vb, "Water"), rel=1e-9)


def test_superaquecido_e_sub_resfriado_contam_da_saturacao():
    tsat = CP.PropsSI("T", "P", 2e5, "Q", 0, "Water")
    for como, letra, sinal in ((mte.SUPERAQUECIDO, "DT_sup", 1), (mte.SUB_RESFRIADO, "DT_sub", -1)):
        nos = [no("e", "estado", fluido=AGUA, como=como), no("t", "temperatura_maxima")]
        m = montar(nos, [fio("e", "saida", "t", "entrada"), ao_resultado("t")])
        valores = {"p": 2e5, letra: 10.0, "m_dot": 1.0}
        t = numero(m, "e", "saida", valores, lambda c: c.temperatura())
        assert t == pytest.approx(tsat + sinal * 10.0, abs=1e-6)


def test_compressor_com_rendimento_e_a_potencia_que_consome():
    m = montar(*_estado_e("compressor", AR))
    valores = {"T": 298.15, "p": 1e5, "m_dot": 2.0, "p_c": 6e5, "eta_c": 0.8, "T_max": 900.0}
    h1 = CP.PropsSI("H", "T", 298.15, "P", 1e5, "Air")
    s1 = CP.PropsSI("S", "T", 298.15, "P", 1e5, "Air")
    h2 = h1 + (CP.PropsSI("H", "P", 6e5, "S", s1, "Air") - h1) / 0.8
    assert numero(m, "x", "saida", valores, lambda c: c.h) == pytest.approx(h2, rel=1e-7)
    assert numero(m, "x", "potencia", valores) == pytest.approx(2.0 * (h2 - h1), rel=1e-7)


def test_turbina_e_a_potencia_que_produz():
    m = montar(*_estado_e("turbina", AGUA))
    valores = {"T": 723.15, "p": 4e6, "m_dot": 1.0, "p_tb": 1e4, "eta_tb": 0.85, "T_max": 900.0}
    h1 = CP.PropsSI("H", "T", 723.15, "P", 4e6, "Water")
    s1 = CP.PropsSI("S", "T", 723.15, "P", 4e6, "Water")
    h2 = h1 - 0.85 * (h1 - CP.PropsSI("H", "P", 1e4, "S", s1, "Water"))
    assert numero(m, "x", "saida", valores, lambda c: c.h) == pytest.approx(h2, rel=1e-7)
    assert numero(m, "x", "potencia", valores) == pytest.approx(h1 - h2, rel=1e-7)


def test_valvula_mantem_a_entalpia_e_da_o_titulo_depois():
    nos = [
        no("e", "estado", fluido=R134A, como=mte.LIQUIDO_PELA_PRESSAO),
        no("v", "valvula"),
        no("t", "temperatura_maxima"),
    ]
    fios = [fio("e", "saida", "v", "entrada"), fio("v", "saida", "t", "entrada"), ao_resultado("t")]
    m = montar(nos, fios)
    valores = {"p": 8e5, "m_dot": 1.0, "p_vl": 1.4e5, "T_max": 400.0}
    h = CP.PropsSI("H", "P", 8e5, "Q", 0, "R134a")
    titulo = numero(m, "v", "saida", valores, lambda c: c.titulo())
    assert titulo == pytest.approx(CP.PropsSI("Q", "P", 1.4e5, "H", h, "R134a"), rel=1e-6)


def test_troca_de_calor_da_o_calor_com_sinal():
    nos, fios = _estado_e("troca_de_calor", AGUA)
    m = montar(nos, fios)
    valores = {"T": 353.15, "p": 3e5, "m_dot": 1.5, "T_s": 313.15, "Dp_tc": 0.0, "T_max": 400.0}
    h1 = CP.PropsSI("H", "T", 353.15, "P", 3e5, "Water")
    h2 = CP.PropsSI("H", "T", 313.15, "P", 3e5, "Water")
    calor = numero(m, "x", "calor", valores)
    assert calor == pytest.approx(1.5 * (h2 - h1), rel=1e-9)
    assert calor < 0.0  # resfriar: o calor sai do fluido


def test_troca_pelo_calor_e_com_perda_de_pressao():
    nos, fios = _estado_e("troca_de_calor", AGUA, saida=mte.CALOR_TROCADO)
    m = montar(nos, fios)
    valores = {"T": 293.15, "p": 3e5, "m_dot": 2.0, "Q_dot": 1e5, "Dp_tc": 2e4, "T_max": 400.0}
    h1 = CP.PropsSI("H", "T", 293.15, "P", 3e5, "Water")
    assert numero(m, "x", "saida", valores, lambda c: c.h) == pytest.approx(h1 + 5e4, rel=1e-12)
    assert numero(m, "x", "saida", valores, lambda c: c.p) == pytest.approx(2.8e5)


def test_misturador_e_divisor_conservam_massa_e_energia():
    nos = [
        no("e1", "estado", fluido=AGUA),
        no("e2", "estado", fluido=AGUA),
        no("m", "misturador"),
        no("d", "divisor"),
        no("t", "temperatura_maxima"),
    ]
    fios = [
        fio("e1", "saida", "m", "a"),
        fio("e2", "saida", "m", "b"),
        fio("m", "saida", "d", "entrada"),
        fio("d", "a", "t", "entrada"),
        ao_resultado("t"),
    ]
    m = montar(nos, fios)
    valores = {
        "T": 353.15,
        "p": 3e5,
        "m_dot": 1.0,
        "T_2": 293.15,
        "p_2": 3e5,
        "m_dot_2": 3.0,
        "y_div": 0.25,
        "T_max": 400.0,
    }
    ha = CP.PropsSI("H", "T", 353.15, "P", 3e5, "Water")
    hb = CP.PropsSI("H", "T", 293.15, "P", 3e5, "Water")
    assert numero(m, "m", "saida", valores, lambda c: c.h) == pytest.approx((ha + 3 * hb) / 4)
    assert numero(m, "d", "a", valores, lambda c: c.m) == pytest.approx(1.0)
    assert numero(m, "d", "b", valores, lambda c: c.m) == pytest.approx(3.0)


def test_misturador_recusa_fluidos_diferentes():
    nos = [no("e1", "estado", fluido=AGUA), no("e2", "estado", fluido=AR), no("m", "misturador")]
    dados = {"nos": nos, "fios": [fio("e1", "saida", "m", "a"), fio("e2", "saida", "m", "b")]}
    m = mt.montar(mt.grafo_de_dados(dados))
    assert any("mesmo fluido" in erro for _, erro in m.erros)


def test_compressor_que_recebe_liquido_avisa():
    nos = [
        no("e", "estado", fluido=R134A, como=mte.LIQUIDO_PELA_PRESSAO),
        no("k", "compressor"),
        no("t", "temperatura_maxima"),
    ]
    fios = [fio("e", "saida", "k", "entrada"), fio("k", "saida", "t", "entrada"), ao_resultado("t")]
    m = montar(nos, fios)
    r = mt.isolar(m, "T_max", {"p": 2e5, "m_dot": 1.0, "p_c": 8e5, "eta_c": 0.8})
    assert any("recebe líquido" in a for a in r.alertas)


def test_fluido_sem_saturacao_explica():
    nos = [no("e", "estado", fluido=AR, como=mte.VAPOR_PELA_PRESSAO)]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": []}))
    assert any("não tem saturação" in erro for _, erro in m.erros)


# ---------------------------------------------------------------------------
# Ciclos em laço
# ---------------------------------------------------------------------------


def _rankine_de_mao() -> float:
    h1 = CP.PropsSI("H", "P", 75e3, "Q", 0, "Water")
    s1 = CP.PropsSI("S", "P", 75e3, "Q", 0, "Water")
    h2 = CP.PropsSI("H", "P", 3e6, "S", s1, "Water")
    h3 = CP.PropsSI("H", "P", 3e6, "T", 623.15, "Water")
    s3 = CP.PropsSI("S", "P", 3e6, "T", 623.15, "Water")
    h4 = CP.PropsSI("H", "P", 75e3, "S", s3, "Water")
    return ((h3 - h4) - (h2 - h1)) / (h3 - h2)


def _do_modelo(nome: str, alvo: str | None = None, **trocas: float) -> mt.Resposta:
    modelo = mm.PARTE_TERMICA.por_nome[nome]
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not m.erros, m.erros
    letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
    valores = {**letras, **dict(m.padroes), **modelo.valores, **trocas}
    return mt.isolar(m, alvo or modelo.alvo, valores)


def test_rankine_de_cengel_10_1_fecha_o_laco():
    r = _do_modelo("Ciclo Rankine simples")
    assert r.valor == pytest.approx(_rankine_de_mao(), rel=1e-6)
    assert r.valor == pytest.approx(0.260, abs=5e-4)  # Çengel e Boles, Exemplo 10-1: 26,0 %
    meio = dict(r.do_meio)
    assert meio["p_lc1"] == pytest.approx(75e3)
    assert meio["h_lc1"] == pytest.approx(CP.PropsSI("H", "P", 75e3, "Q", 0, "Water"), rel=1e-9)
    assert r.montagem is not None and set(r.montagem.cortes) == {"p_lc1", "h_lc1"}
    assert all(mt.e_corte(c) for c in r.montagem.cortes)
    assert not mt.e_corte("p_b") and not mt.e_corte("T_s")


def test_refrigeracao_de_cengel_11_1():
    r = _do_modelo("Refrigeração por compressão (R134a)")
    assert r.valor == pytest.approx(3.97, abs=0.005)  # Çengel e Boles, Exemplo 11-1
    h1 = CP.PropsSI("H", "P", 1.4e5, "Q", 1, "R134a")
    h3 = CP.PropsSI("H", "P", 8e5, "Q", 0, "R134a")
    assert 0.05 * (h1 - h3) == pytest.approx(7.18e3, rel=1e-3)  # Q_L do livro: 7,18 kW


def test_rankine_real_rende_menos_que_o_ideal():
    ideal = _do_modelo("Ciclo Rankine simples").valor
    real = _do_modelo("Ciclo Rankine simples", eta_tb=0.85, eta_b=0.8).valor
    assert ideal is not None and real is not None and real < ideal


def test_vazao_do_circuito_pode_ser_a_pedida():
    """Quanta água no ciclo para a turbina dar 10 MW: a vazão do laço vira a letra pedida."""
    modelo = mm.PARTE_TERMICA.por_nome["Ciclo Rankine simples"]
    dados = modelo.grafo()
    dados["nos"].append(no("pm", "potencia_maxima"))
    dados["fios"] = [f for f in dados["fios"] if f["de"] != "n1"]
    dados["fios"] += [
        fio("t1", "potencia", "pm", "potencias"),
        fio("pm", "condicao", "r1", "condicoes"),
    ]
    m = mt.montar(mt.grafo_de_dados(dados))
    valores = {**modelo.valores, "P_max": 10e6}
    valores.pop("m_c")
    r = mt.isolar(m, "m_c", valores)
    h3 = CP.PropsSI("H", "P", 3e6, "T", 623.15, "Water")
    s3 = CP.PropsSI("S", "P", 3e6, "T", 623.15, "Water")
    h4 = CP.PropsSI("H", "P", 75e3, "S", s3, "Water")
    assert r.valor == pytest.approx(10e6 / (h3 - h4), rel=1e-6)
    assert r.sentido == mt.MAXIMO


def test_laco_de_corrente_sem_circuito_avisa():
    nos = [no("k", "compressor"), no("q", "troca_de_calor")]
    fios = [fio("k", "saida", "q", "entrada"), fio("q", "saida", "k", "entrada")]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    assert any("laço" in erro for _, erro in m.erros)
    assert m.cortes == ()


@pytest.mark.parametrize("modelo", mm.MODELOS_TERMICOS, ids=lambda m: m.nome)
def test_todo_modelo_termico_responde(modelo):
    r = _do_modelo(modelo.nome)
    assert r.valor is not None and not r.faltam and not r.alertas, modelo.nome


def test_mistura_bate_com_a_conta_de_mao():
    r = _do_modelo("Misturar água quente e fria")
    assert r.valor == pytest.approx(35.0 / 30.0, rel=1e-2)  # c_p quase constante entre 15 e 80 °C


def test_aquecer_agua_bate_com_a_entalpia():
    r = _do_modelo("Aquecer água: vazão pelo calor")
    h20 = CP.PropsSI("H", "T", 293.15, "P", 3e5, "Water")
    h60 = CP.PropsSI("H", "T", 333.15, "P", 3e5, "Water")
    assert r.valor == pytest.approx(200e3 / (h60 - h20), rel=1e-9)


# ---------------------------------------------------------------------------
# Unidades e tela
# ---------------------------------------------------------------------------


def test_unidades_do_termico_valem_o_que_dizem():
    u = g.unidades_padrao(g.SISTEMA_TERMICO)
    assert u.para_base(g.TEMPERATURA, 25.0) == pytest.approx(298.15)
    assert u.para_base(g.PRESSAO, 101.325) == pytest.approx(101325.0)
    assert u.para_base(g.ENERGIA_ESPECIFICA, 2500.0) == pytest.approx(2.5e6)
    assert u.para_base(g.VAZAO_MASSICA, 1.0) == pytest.approx(1.0)
    assert u.fator(g.DIF_TEMPERATURA) == 1.0
    f = g.Unidades(g.SISTEMA_TERMICO, ("°F", *u.escolhas[1:]))
    assert f.fator(g.DIF_TEMPERATURA) == pytest.approx(5.0 / 9.0)


def test_letras_do_termico_nao_repetem_as_dos_fluidos():
    termico = set(g.letras_conhecidas(g.SISTEMA_TERMICO.chave))
    fluidos = set(g.letras_conhecidas(g.SISTEMA_FLUIDOS.chave))
    assert not termico & fluidos  # no Montador que liga os dois, elas se encontram
    assert g.Q_DOT.sinal_livre and g.Q_DOT.simbolo.is_positive is None


def test_pagina_do_termico_abre_e_cada_modelo_responde():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_termico.py").run()
    assert not at.exception
    for modelo in mm.MODELOS_TERMICOS:
        at.selectbox(key="mte_modelo").set_value(modelo.nome).run()
        assert not at.exception, modelo.nome
        assert at.success, modelo.nome


def test_rankine_na_tela_tem_a_tabela_de_estados_com_numeros():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_termico.py").run()
    at.selectbox(key="mte_modelo").set_value("Ciclo Rankine simples").run()
    tabelas = [d.value for d in at.dataframe]
    estados = next(t for t in tabelas if "Ponto" in t.columns)
    assert len(estados) == 5
    temperaturas = estados[[c for c in estados.columns if c.startswith("T ")][0]]
    assert temperaturas.notna().all()
    assert temperaturas.iloc[2] == pytest.approx(350.0, abs=1e-3)  # saída da caldeira, em °C
    assert not math.isnan(float(temperaturas.iloc[3]))
