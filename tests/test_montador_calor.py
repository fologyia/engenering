"""Transferência de calor no Montador térmico: tubo isolado e trocador ε-NTU, contra a conta de mão."""

from __future__ import annotations

import math
from pathlib import Path

import CoolProp.CoolProp as CP
import ht
import pytest
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_grandezas as g
from core import montador_modelos as mm

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _resposta(nome: str, **trocas: float) -> tuple[mt.Montagem, mt.Resposta]:
    modelo = mm.PARTE_TERMICA.por_nome[nome]
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not m.erros, m.erros
    letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
    return m, mt.isolar(m, modelo.alvo, {**letras, **dict(m.padroes), **modelo.valores, **trocas})


def _l_sobre_r(espessura: float, d_e: float = 60.3e-3, k: float = 0.04, h: float = 10.0) -> float:
    r_e = d_e / 2
    r_i = r_e + espessura
    return 300.0 / (math.log(r_i / r_e) / (2 * math.pi * k) + 1 / (2 * math.pi * r_i * h))


def test_isolamento_minimo_bate_com_a_conta_de_mao():
    _, r = _resposta("Tubo de água quente: isolamento mínimo")
    cp = CP.PropsSI("C", "T", 353.15, "P", 3e5, "Water")
    alvo = -2.0 * cp * math.log((351.15 - 293.15) / (353.15 - 293.15))
    assert r.sentido == mt.MINIMO
    # O programa sai pela entalpia (a saída é T(h₁ + Q/ṁ)); a mão usa c_p constante: 0,1 %.
    assert _l_sobre_r(r.valor) == pytest.approx(alvo, rel=1e-3)


def test_tubo_nu_perde_mais_que_isolado():
    m, _ = _resposta("Tubo de água quente: isolamento mínimo")
    valores = {**mm.PARTE_TERMICA.por_nome["Tubo de água quente: isolamento mínimo"].valores}
    numeros = lambda e: {g.simbolo_de(k): v for k, v in {**valores, "e_iso": e}.items()}  # noqa: E731
    calor = m.saidas["t1"]["calor"]
    nu = mt.numero_de(calor, numeros(0.0))
    isolado = mt.numero_de(calor, numeros(0.05))
    assert nu < isolado < 0.0  # sai do fluido; o tubo nu perde mais


def test_temperatura_da_superficie_cai_com_o_isolamento():
    m, _ = _resposta("Tubo de água quente: isolamento mínimo")
    valores = mm.PARTE_TERMICA.por_nome["Tubo de água quente: isolamento mínimo"].valores
    sup = m.saidas["t1"]["superficie"]
    t = [
        mt.numero_de(sup, {g.simbolo_de(k): v for k, v in {**valores, "e_iso": e}.items()})
        for e in (0.0, 0.025, 0.05)
    ]
    assert t[0] > t[1] > t[2] > 293.15


def test_trocador_bate_com_o_ht_e_com_a_entalpia():
    _, r = _resposta("Trocador: tamanho para resfriar óleo")
    cq = CP.PropsSI("C", "T", 423.15, "P", 3e5, "INCOMP::T66")
    cf = 1.5 * CP.PropsSI("C", "T", 293.15, "P", 3e5, "Water")
    q = CP.PropsSI("H", "T", 423.15, "P", 3e5, "INCOMP::T66") - CP.PropsSI(
        "H", "T", 353.15, "P", 3e5, "INCOMP::T66"
    )
    cmin, cmax = min(cq, cf), max(cq, cf)
    ntu = ht.hx.NTU_from_effectiveness(q / (cmin * 130.0), cmin / cmax, subtype="counterflow")
    assert r.valor == pytest.approx(ntu * cmin, rel=1e-6)
    assert r.sentido == mt.MINIMO


def test_paralelo_pede_trocador_maior():
    modelo = mm.PARTE_TERMICA.por_nome["Trocador: tamanho para resfriar óleo"]
    dados = modelo.grafo()
    for no in dados["nos"]:
        if no["tipo"] == "trocador":
            no["opcoes"]["arranjo"] = "Correntes paralelas"
    m = mt.montar(mt.grafo_de_dados(dados))
    paralelo = mt.isolar(m, "UA", dict(modelo.valores)).valor
    _, contra = _resposta("Trocador: tamanho para resfriar óleo")
    assert paralelo > contra.valor


def test_pagina_mostra_os_modelos_de_calor():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_termico.py").run()
    for nome in ("Tubo de água quente: isolamento mínimo", "Trocador: tamanho para resfriar óleo"):
        at.selectbox(key="mte_modelo").set_value(nome).run()
        assert not at.exception, nome
        assert at.success, nome
