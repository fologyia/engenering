"""Os blocos de fluidos que vêm de norma, contra a biblioteca ``fluids`` chamada direto.

Crane (TP-410) nas peças, ASME B36.10M e B36.19M nos tubos, gás isotérmico em tubo longo, válvula de
controle pela IEC 60534-2-1 e placa de orifício e venturi pela ISO 5167.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import CoolProp.CoolProp as CP
import pytest
from fluids import compressible, control_valve, fittings, flow_meter, piping
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_fluidos as fl
from core import montador_funcoes as fn
from core import montador_modelos as mm
from core.montador_modelos import Modelo

APP = str(Path(__file__).resolve().parents[1] / "app.py")
R = "resultado"
SCH40_2 = "Aço Sch 40, DN 50 (2 pol)"


def _base(*tipos: str, opcoes: dict | None = None) -> mt.Montagem:
    modelo = Modelo("x", "", "", {}, tipos, opcoes=opcoes or {})
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not base.erros, base.erros
    return base


def _com_padroes(base: mt.Montagem, **valores: float) -> dict[str, float]:
    letras = {i.chave: i.padrao for i in base.grandezas if i.padrao is not None}
    return {**letras, **dict(base.padroes), **valores}


def _do_modelo(nome: str) -> mt.Resposta:
    modelo = mm.PARTE_FLUIDOS.por_nome[nome]
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not base.erros, base.erros
    return mt.isolar(base, modelo.alvo, _com_padroes(base, **modelo.valores))


# --- Crane ------------------------------------------------------------------------------------


@pytest.mark.parametrize("d", [0.0158, 0.0525, 0.1023, 0.3])
def test_k_das_valvulas_e_o_da_fluids(d):
    ft = fittings.ft_Crane(d)
    esperado = {
        "Registro de gaveta aberto (8·f_T)": fittings.K_gate_valve_Crane(d, d, 0.0),
        "Válvula de globo aberta (340·f_T)": fittings.K_globe_valve_Crane(d, d),
        "Válvula de esfera aberta (3·f_T)": fittings.K_ball_valve_Crane(d, d, 0.0),
        "Válvula borboleta centrada (45, 35 ou 25·f_T)": fittings.K_butterfly_valve_Crane(d),
        "Retenção de portinhola (100·f_T)": fittings.K_swing_check_valve_Crane(D=d),
        "Cotovelo 90° padrão (30·f_T)": 30.0 * ft,
        "Curva 90°, r/D = 1 (20·f_T)": 20.0 * ft,
        "Tê, saída lateral (60·f_T)": 60.0 * ft,
    }
    for nome, k in esperado.items():
        assert fn.k_do_crane(d, fl.PECAS_CRANE.index(nome)) == pytest.approx(k, rel=1e-9), nome


def test_borboleta_muda_de_faixa_com_o_diametro():
    i = fl.PECAS_CRANE.index("Válvula borboleta centrada (45, 35 ou 25·f_T)")
    assert fn.k_do_crane(0.2, i) / fittings.ft_Crane(0.2) == pytest.approx(45.0)
    assert fn.k_do_crane(0.3, i) / fittings.ft_Crane(0.3) == pytest.approx(35.0)
    assert fn.k_do_crane(0.5, i) / fittings.ft_Crane(0.5) == pytest.approx(25.0)


def test_linha_com_crane_bate_com_a_conta_de_mao():
    r = _do_modelo("Peças pelo Crane: vazão por gravidade")
    assert r.sentido == mt.MAXIMO
    d = fl.TUBOS_COMERCIAIS[SCH40_2].interno_m
    v = 4 * r.valor / (math.pi * d**2)
    re = 998.2 * v * d / 1.0016e-3
    f = fn.fator_de_atrito(re, 0.045e-3 / d)
    k = 4 * 30.0 * fittings.ft_Crane(d) + fittings.K_gate_valve_Crane(d, d, 0.0)
    assert (f * 50.0 / d + k) * v**2 / (2 * 9.81) == pytest.approx(10.0, rel=1e-6)


def test_crane_sem_pecas_avisa():
    base = _base("fluido", "trecho", "perdas_crane", "carga", R)
    assert any("Crane" in a for a in base.alertas)


# --- ASME ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rotulo", "schedule", "nps"),
    [
        ("Aço Sch 40, DN 100 (4 pol)", "40", 4.0),
        ("Aço Sch 80, DN 50 (2 pol)", "80", 2.0),
        ("Aço Sch 160, DN 25 (1 pol)", "160", 1.0),
        ("Aço XS, DN 300 (12 pol)", "XS", 12.0),
        ("Aço inox Sch 10S, DN 150 (6 pol)", "10S", 6.0),
    ],
)
def test_tubos_da_asme(rotulo, schedule, nps):
    _, di, _, _ = piping.nearest_pipe(NPS=nps, schedule=schedule)
    assert fl.TUBOS_COMERCIAIS[rotulo].interno_m == pytest.approx(di, abs=1e-6)


def test_nomes_antigos_dos_tubos_continuam():
    """Os arquivos salvos guardam o nome do tubo: o Sch 40 e o PVC não mudaram."""
    assert fl.TUBOS_COMERCIAIS["Aço Sch 40, DN 50 (2 pol)"].interno_m * 1000 == pytest.approx(52.48)
    assert "PVC soldável, DN 110" in fl.TUBOS_COMERCIAIS


# --- Gás em tubo longo --------------------------------------------------------------------------


def test_gas_no_tubo_bate_com_a_fluids():
    r = _do_modelo("Gás natural: diâmetro do tubo")
    assert r.sentido == mt.MINIMO
    d = r.valor
    rho = CP.PropsSI("D", "T", 293.15, "P", 1e6, "Methane")
    mu = CP.PropsSI("V", "T", 293.15, "P", 1e6, "Methane")
    m = rho * 0.05
    fd = fn.fator_de_atrito(4 * m / (math.pi * d * mu), 0.045e-3 / d)
    # No diâmetro mínimo, a vazão que chega com 7 bar é a vazão pedida.
    assert compressible.isothermal_gas(rho, fd, P1=1e6, P2=7e5, L=5000.0, D=d) == pytest.approx(
        m, rel=1e-6
    )


def test_gas_no_tubo_pede_gas():
    base = mt.montar(
        mt.grafo_de_dados(Modelo("x", "", "", {}, ("fluido", "gas_no_tubo", R)).grafo())
    )
    assert any("gás" in e for _, e in base.erros)


# --- Válvula de controle ------------------------------------------------------------------------


def _agua(p: float) -> tuple[float, float, float, float]:
    return (
        CP.PropsSI("D", "T", 293.15, "P", p, "Water"),
        CP.PropsSI("P", "T", 293.15, "Q", 0, "Water"),
        CP.PropsSI("pcrit", "Water"),
        CP.PropsSI("V", "T", 293.15, "P", p, "Water"),
    )


def test_kv_bate_com_a_fluids():
    r = _do_modelo("Válvula de controle: K_v pedido")
    rho, pv, pc, mu = _agua(6e5)
    kv = control_valve.size_control_valve_l(rho, pv, pc, mu, 6e5, 4.5e5, 50 / 3600, FL=0.9)
    assert r.valor == pytest.approx(kv, rel=1e-5)
    assert r.sentido == mt.MINIMO and not r.alertas


def test_kv_com_cavitacao_usa_a_queda_maxima_e_avisa():
    modelo = mm.PARTE_FLUIDOS.por_nome["Válvula de controle: K_v pedido"]
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    r = mt.isolar(base, "K_v", _com_padroes(base, **{**modelo.valores, "Delta_p_v": 5.5e5}))
    rho, pv, pc, mu = _agua(6e5)
    kv = control_valve.size_control_valve_l(rho, pv, pc, mu, 6e5, 0.5e5, 50 / 3600, FL=0.9)
    assert r.valor == pytest.approx(kv, rel=1e-5)
    assert any("cavita" in a for a in r.alertas)


# --- Medidores da ISO 5167 ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "medidor", "tomadas"),
    [
        (fl.ORIFICIO_CANTO, "ISO 5167 orifice", "corner"),
        (fl.ORIFICIO_FLANGE, "ISO 5167 orifice", "flange"),
        (fl.ORIFICIO_D, "ISO 5167 orifice", "D"),
        (fl.VENTURI_USINADO, "machined convergent venturi tube", None),
        (fl.VENTURI_FUNDIDO, "as cast convergent venturi tube", None),
    ],
)
def test_medidor_com_liquido_bate_com_a_fluids(tipo, medidor, tomadas):
    base = _base("fluido", "medidor", R, opcoes={"n2": {"tipo": tipo}})
    r = mt.isolar(base, "Q", _com_padroes(base, D=0.15, D_o=0.09, Delta_p=20e3))
    m = flow_meter.differential_pressure_meter_solver(
        0.15,
        998.2,
        1.0016e-3,
        k=1.4,
        D2=0.09,
        P1=3e5,
        P2=2.8e5,
        meter_type=medidor,
        taps=tomadas,
        epsilon_specified=1.0,
    )
    assert r.valor * 998.2 == pytest.approx(m, rel=1e-6)


def test_orificio_com_gas_tem_expansibilidade():
    opcoes = {
        "n1": {"fluido": "Ar seco pela temperatura (CoolProp)"},
        "n2": {"tipo": fl.ORIFICIO_FLANGE},
    }
    base = _base("fluido", "medidor", R, opcoes=opcoes)
    valores = _com_padroes(base, T_f=293.15, p_f=5e5, D=0.1, D_o=0.05, Delta_p=20e3)
    r = mt.isolar(base, "Q", valores)
    rho = CP.PropsSI("D", "T", 293.15, "P", 5e5, "Air")
    mu = CP.PropsSI("V", "T", 293.15, "P", 5e5, "Air")
    m = flow_meter.differential_pressure_meter_solver(
        0.1,
        rho,
        mu,
        k=1.4,
        D2=0.05,
        P1=5e5,
        P2=4.8e5,
        meter_type="ISO 5167 orifice",
        taps="flange",
    )
    assert r.valor * rho == pytest.approx(m, rel=1e-6)


def test_medidor_fora_da_norma_avisa():
    base = _base("fluido", "medidor", R, opcoes={"n2": {"tipo": fl.ORIFICIO_FLANGE}})
    r = mt.isolar(base, "Q", _com_padroes(base, D=0.1, D_o=0.09, Delta_p=20e3))
    assert any("β" in a for a in r.alertas)


def test_medidor_antigo_continua_igual():
    r = _do_modelo("Medidor de orifício")
    area = math.pi * 0.05**2 / 4
    esperado = 0.6 * area * math.sqrt(2 * 20000.0 / 998.2) / math.sqrt(1 - 0.5**4)
    assert r.valor == pytest.approx(esperado, rel=1e-9)


# --- Tela -------------------------------------------------------------------------------------


def test_pagina_abre_os_modelos_novos():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    at.switch_page("app_pages/montador_fluidos.py").run()
    for nome in (
        "Placa de orifício pela ISO 5167",
        "Peças pelo Crane: vazão por gravidade",
        "Gás natural: diâmetro do tubo",
        "Válvula de controle: K_v pedido",
    ):
        at.selectbox(key="mfl_modelo").set_value(nome).run()
        assert not at.exception, nome
        assert at.success, nome


def test_pecas_do_crane_ficam_no_bloco():
    modelo = mm.PARTE_FLUIDOS.por_nome["Peças pelo Crane: vazão por gravidade"]
    texto = modelo.opcoes["n3"]["pecas"]
    assert fl.ler_pecas(texto, fl.PECAS_CRANE) == {
        "Cotovelo 90° padrão (30·f_T)": 4,
        "Registro de gaveta aberto (8·f_T)": 1,
    }
    assert fl.ler_pecas(json.dumps({"Peça que não existe": 2}), fl.PECAS_CRANE) == {}
