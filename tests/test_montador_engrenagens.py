"""Par de engrenagens e engrenagem cônica no Montador, contra o Assistente de cargas.

O par confere o dente por Lewis e por contato, com as mesmas fórmulas de
``core/elementos_transmissao.py``; a cônica dá as forças no eixo do pinhão ou da coroa.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from core import elementos_transmissao as et
from core import montador as mt
from core import montador_aceite as ma
from core import montador_blocos as mb
from core import montador_funcoes as mf
from core import montador_modelos as mm
from core import montador_pecas as mpe

R = mb.RESULTADO
APP = str(Path(__file__).resolve().parents[1] / "app.py")
_CASO = ma._ENGRENAGEM_DO_CASO
_VALORES = {
    "P": _CASO["potencia_kW"] * 1e6,
    "n_rot": _CASO["rotacao_rpm"],
    "m_n": _CASO["modulo_mm"],
    "z_1": float(_CASO["z1"]),
    "z_2": float(_CASO["z2"]),
    "phi_n": math.radians(_CASO["angulo_pressao"]),
    "psi": math.radians(_CASO["angulo_helice"]),
    "b_g": _CASO["largura_mm"],
    "K_o": _CASO["ko"],
    "K_m": _CASO["km"],
    "n": _CASO["fs"],
    "E": _CASO["e_GPa"] * 1000.0,
    "nu_g": _CASO["poisson"],
    "HB": _CASO["dureza_HB"],
}


def _par(opcoes: dict | None = None) -> mt.Montagem:
    dados = {
        "nos": [
            {
                "id": "p",
                "tipo": "par_engrenagens",
                "opcoes": {"processo": _CASO["processo"], **(opcoes or {})},
            },
            {"id": "r", "tipo": R, "opcoes": {}},
        ],
        "fios": [{"de": "p", "saida": "condicao", "para": "r", "entrada": "condicoes"}],
    }
    return mt.montar(mt.grafo_de_dados(dados))


def _numeros(valores: dict) -> dict[sp.Symbol, sp.Float]:
    return {sp.Symbol(k, positive=True): sp.Float(v) for k, v in valores.items()}


def test_dente_bate_com_o_assistente():
    esperado = {
        v.nome: float(v.solicitante)
        for v in et.calcular_engrenagem(_CASO).verificacoes
        if v.solicitante is not None and v.resistente is not None
    }
    base = _par()
    numeros = _numeros(_VALORES)
    for condicao in base.condicoes:
        assert float(condicao.esquerda.subs(numeros)) == pytest.approx(
            esperado[condicao.nome], rel=1e-12
        ), condicao.nome


def test_forcas_do_par_batem_com_o_assistente():
    metricas = {m.rotulo: m.valor for m in et.calcular_engrenagem(_CASO).metricas}
    saidas = _par().saidas["p"]
    numeros = _numeros(_VALORES)
    for porta, rotulo in (
        ("F_t", "Força tangencial F_t"),
        ("F_r", "Força radial F_r"),
        ("F_a", "Força axial F_a"),
    ):
        assert float(saidas[porta].subs(numeros)) == pytest.approx(
            float(metricas[rotulo]) * 1000.0, rel=1e-12
        )


def test_no_eixo_da_coroa_o_torque_muda_e_o_dente_nao():
    pinhao = _par()
    coroa = _par({"eixo": mpe.EIXO_DA_COROA})
    razao = _VALORES["z_2"] / _VALORES["z_1"]
    na_coroa = _numeros({**_VALORES, "n_rot": _VALORES["n_rot"] / razao})
    no_pinhao = _numeros(_VALORES)
    assert float(coroa.saidas["p"]["T"].subs(na_coroa)) == pytest.approx(
        float(pinhao.saidas["p"]["T"].subs(no_pinhao)) * razao
    )
    for a, b in zip(pinhao.condicoes, coroa.condicoes, strict=True):
        assert float(b.esquerda.subs(na_coroa)) == pytest.approx(float(a.esquerda.subs(no_pinhao)))


@pytest.mark.parametrize("processo", et.PROCESSOS)
def test_fator_dinamico_em_letra_e_o_do_assistente(processo):
    velocidade = 7.3
    assert float(mpe.fator_dinamico(processo, sp.Float(velocidade))) == pytest.approx(
        et.fator_dinamico(processo, velocidade), rel=1e-12
    )


def test_lewis_abaixo_de_12_dentes_nao_existe():
    assert math.isnan(mf.fator_de_lewis(10.0))
    assert mf.fator_de_lewis(20.0) == pytest.approx(0.322)


def test_largura_curta_para_o_modulo_avisa():
    valores = {k: v for k, v in _VALORES.items() if k != "m_n"}
    resposta = mt.isolar(_par(), "m_n", valores)
    assert resposta.valor is not None
    assert any("8 módulos" in a for a in resposta.alertas)


def test_largura_isolada_bate_com_o_caso_de_aceite():
    assert ma._par_no_montador() == pytest.approx(ma._par_do_assistente(), rel=1e-6)


def test_conica_bate_com_o_assistente_e_troca_no_eixo_da_coroa():
    metricas = {m.rotulo: m.valor for m in et.calcular_conica(ma._CONICA_DO_CASO).metricas}
    valores = {
        "T": 200e3,
        "m_c": 4.0,
        "z_c1": 18.0,
        "z_c2": 36.0,
        "b_c": 24.0,
        "phi_n": math.radians(20.0),
    }
    numeros = _numeros(valores)

    def saidas(eixo: str) -> dict[str, float]:
        opcoes = {"torque": mpe.PELO_TORQUE, "eixo": eixo}
        dados = {"nos": [{"id": "c", "tipo": "engrenagem_conica", "opcoes": opcoes}], "fios": []}
        base = mt.montar(mt.grafo_de_dados(dados))
        return {p: float(v.subs(numeros)) for p, v in base.saidas["c"].items()}

    pinhao = saidas(mpe.EIXO_DO_PINHAO)
    assert pinhao["F_t"] == pytest.approx(float(metricas["Força tangencial F_t"]) * 1000.0)
    assert pinhao["F_r"] == pytest.approx(float(metricas["Força radial no pinhão"]) * 1000.0)
    assert pinhao["F_a"] == pytest.approx(float(metricas["Força axial no pinhão"]) * 1000.0)
    assert pinhao["r_m"] == pytest.approx(float(metricas["Primitivo médio"]) / 2.0)
    # No eixo da coroa o torque é o dela: o dobro, com z_c2 = 2·z_c1, para a mesma força.
    numeros[sp.Symbol("T", positive=True)] = sp.Float(400e3)
    coroa = saidas(mpe.EIXO_DA_COROA)
    assert coroa["F_r"] == pytest.approx(pinhao["F_a"])
    assert coroa["F_a"] == pytest.approx(pinhao["F_r"])


def test_conica_larga_demais_avisa():
    resposta = ma.resolver(
        ("circular", "flexao", "von_mises", R),
        "d",
        {
            "T": 200e3,
            "m_c": 4.0,
            "z_c1": 18.0,
            "z_c2": 36.0,
            "b_c": 50.0,
            "phi_n": math.radians(20.0),
            "c_b": 50.0,
            "L": 200.0,
            "S_y": 420.0,
            "n": 2.0,
        },
        {"c1": {"torque": mpe.PELO_TORQUE}},
        ligar=(("c1", "F_r", "v1", "F"), ("v1", "M", "n2", "valor")),
        extras=(("c1", "engrenagem_conica"), ("v1", "biapoiada_balanco")),
    )
    assert any("10 módulos" in a for a in resposta.alertas)


@pytest.mark.parametrize(
    "nome", ["Par de engrenagens: módulo do dente", "Pinhão cônico em balanço"]
)
def test_modelos_das_engrenagens_abrem_com_resposta(nome):
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    at.selectbox(key=mm.PARTE_SOLIDOS.k("modelo")).set_value(nome).run()
    assert not at.exception
    assert at.success, nome
