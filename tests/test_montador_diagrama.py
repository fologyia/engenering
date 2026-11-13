"""O diagrama T-s e p-h do Montador térmico: pontos, processos e curva de saturação."""

from __future__ import annotations

from pathlib import Path

import CoolProp.CoolProp as CP
import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_diagrama as dgm
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_propriedades as mp
from core import montador_termico as mte

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _diagrama(nome: str, **trocas: float) -> tuple[dgm.Diagrama, mt.Montagem]:
    modelo = mm.PARTE_TERMICA.por_nome[nome]
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    letras = {i.chave: i.padrao for i in base.grandezas if i.padrao is not None}
    r = mt.isolar(base, modelo.alvo, {**letras, **dict(base.padroes), **modelo.valores, **trocas})
    usados = {**dict(r.do_meio), **mt.valores_do_caso(r)}
    if r.valor is not None:
        usados[r.alvo.chave] = r.valor
    numeros = {g.simbolo_de(k): sp.Float(v) for k, v in usados.items()}
    conta = r.montagem or base
    return dgm.montar(conta, numeros), conta


def test_rankine_tem_as_fases_certas():
    d, _ = _diagrama("Ciclo Rankine simples")
    fases = [p.fase for p in d.pontos]
    # Circuito, bomba, caldeira, turbina, condensador
    assert fases == [dgm.LIQUIDO, dgm.LIQUIDO, dgm.VAPOR, dgm.MISTURA, dgm.LIQUIDO]
    assert len(d.caminhos) == 5 and not d.sem_numero


def test_caldeira_vai_pela_isobarica():
    """Os pontos do meio da caldeira estão na mesma pressão e passam pela mistura."""
    d, _ = _diagrama("Ciclo Rankine simples")
    caldeira = next(c for c in d.caminhos if c.de == 2 and c.para == 3)
    assert max(caldeira.p) == pytest.approx(min(caldeira.p), rel=1e-9)
    t_sat = CP.PropsSI("T", "P", caldeira.p[0], "Q", 0, "Water")
    no_patamar = [t for t in caldeira.t if t is not None and abs(t - t_sat) < 1e-6]
    assert len(no_patamar) >= 5  # o patamar de ebulição


def test_estado_da_tabela_e_o_da_coolprop():
    d, _ = _diagrama("Ciclo Rankine simples")
    for ponto in d.pontos:
        assert ponto.t == pytest.approx(CP.PropsSI("T", "P", ponto.p, "H", ponto.h, "Water"))


def test_curva_de_saturacao_fecha_no_critico():
    agua = mp.FLUIDOS.index(mp.POR_ROTULO["Água"])
    curva = dgm.saturacao(agua)
    assert curva is not None
    assert max(curva.t) == pytest.approx(CP.PropsSI("Tcrit", "Water"), rel=1e-3)
    assert curva.s[0] < curva.s[-1]  # começa no líquido e volta pelo vapor
    assert dgm.saturacao(mp.FLUIDOS.index(mp.POR_ROTULO["Óleo térmico Therminol 66"])) is None


def test_bomba_com_vapor_aparece():
    """Condensador que não condensa tudo: a bomba recebe mistura, e o diagrama diz."""
    modelo = mm.PARTE_TERMICA.por_nome["Ciclo Rankine simples"]
    dados = modelo.grafo()
    for no in dados["nos"]:
        if no["id"] == "q2":
            no["opcoes"]["saida"] = mte.TITULO_NA_SAIDA
    base = mt.montar(mt.grafo_de_dados(dados))
    assert not base.erros, base.erros
    letras = {i.chave: i.padrao for i in base.grandezas if i.padrao is not None}
    titulo = next(i.chave for i in base.grandezas if i.chave.startswith("x_s"))
    valores = {**letras, **dict(base.padroes), **modelo.valores, titulo: 0.2}
    r = mt.isolar(base, modelo.alvo, valores)
    usados = {**dict(r.do_meio), **mt.valores_do_caso(r)}
    numeros = {g.simbolo_de(k): sp.Float(v) for k, v in usados.items()}
    conta = r.montagem or base
    d = dgm.montar(conta, numeros)
    assert any("bomba" in aviso for aviso in dgm.estranhos(d.pontos, conta))


def test_pagina_mostra_o_diagrama():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_termico.py").run()
    at.selectbox(key="mte_modelo").set_value("Ciclo Rankine simples").run()
    assert not at.exception
    assert any("Diagrama do ciclo" in h.proto.body for h in at.get("html"))
    at.session_state["mte_diagrama"] = "p-h"
    at.run()
    assert not at.exception
