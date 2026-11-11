"""Torção nas barras do modelo: NBR 8800:2008 5.5.2."""

from __future__ import annotations

import math

import pytest

from core import column_buckling as cbk
from core import torcao_barras as tb
from core import verificacao_barras as vb

FY = 345.0
SEM = tb.Resistencias(500.0, 600.0, 50.0, 20.0, 200.0, 200.0)


def _e(t: float, n: float = 0.0, mx: float = 0.0, v: float = 0.0) -> tb.EsforcoDeTorcao:
    return tb.EsforcoDeTorcao("ELU 1", "meio", n, mx, 0.0, v, 0.0, t)


def test_mesmo_gamma_da_verificacao_das_barras():
    assert tb.GAMMA_A1 == cbk.GAMMA_A1


# ---------------------------------------------------------------------------
# Tubos: conta de mão
# ---------------------------------------------------------------------------


def test_tubo_circular_no_escoamento():
    # W_T = π·95²·5/2 = 70 882 mm³; 0,6·W_T·f_y/γ = 13,34 kN·m. D/t = 20: a flambagem fica acima.
    t_rd, texto = tb.momento_resistente_tubo_circular(100.0, 5.0, 3000.0, FY)
    wt = math.pi * 95**2 * 5 / 2
    assert t_rd == pytest.approx(0.6 * wt * FY / 1.1 / 1e6)
    assert "escoamento" in texto


def test_tubo_circular_fino_flamba_por_torcao():
    t_rd, texto = tb.momento_resistente_tubo_circular(500.0, 2.0, 6000.0, FY)
    wt = math.pi * 498**2 * 2 / 2
    curto = 0.6 * wt * 200_000 / 250**1.5 / 1.1
    longo = 1.23 * wt * 200_000 / (250**1.25 * math.sqrt(6000 / 500)) / 1.1
    assert t_rd == pytest.approx(max(curto, longo) / 1e6)
    assert "flambagem" in texto


def test_tubo_retangular_compacto():
    # W_T = 2·95·95·5 − 4,5·(4 − π)·5³; h/t = (100 − 15)/5 = 17 ≤ 2,45·√(E/f_y).
    t_rd, _ = tb.momento_resistente_tubo_retangular(100.0, 100.0, 5.0, FY)
    wt = 2 * 95 * 95 * 5 - 4.5 * (4 - math.pi) * 125
    assert t_rd == pytest.approx(0.6 * wt * FY / 1.1 / 1e6)


def test_tubo_retangular_esbelto_elastico():
    t_rd, texto = tb.momento_resistente_tubo_retangular(200.0, 200.0, 2.0, FY)
    wt = 2 * 198 * 198 * 2 - 4.5 * (4 - math.pi) * 8
    esbeltez = (200 - 6) / 2
    assert esbeltez > 3.07 * math.sqrt(200_000 / FY)
    assert t_rd == pytest.approx(0.46 * math.pi**2 * wt * 200_000 / esbeltez**2 / 1.1 / 1e6)
    assert "elástica" in texto


def test_tubo_retangular_acima_de_260_explica():
    with pytest.raises(ValueError, match="260"):
        tb.momento_resistente_tubo_retangular(600.0, 600.0, 2.0, FY)


def test_tubo_ate_20_por_cento_despreza_a_torcao():
    t_rd, _ = tb.momento_resistente_tubo_circular(100.0, 5.0, 3000.0, FY)
    linhas = tb.linhas_de_torcao(
        "tubo_circ", {"D": 100.0, "t": 5.0}, None, FY, [_e(0.15 * t_rd)], SEM, 3000.0
    )
    assert [v.nome for v in linhas] == ["Torção ≤ T_Rd", tb.INFORMATIVO]
    assert linhas[0].status == "OK"


def test_tubo_acima_de_20_por_cento_usa_a_interacao():
    t_rd, _ = tb.momento_resistente_tubo_circular(100.0, 5.0, 3000.0, FY)
    esforco = _e(0.5 * t_rd, n=-100.0, mx=10.0, v=20.0)
    linhas = tb.linhas_de_torcao(
        "tubo_circ", {"D": 100.0, "t": 5.0}, None, FY, [esforco], SEM, 3000.0
    )
    interacao = next(v for v in linhas if "interação" in v.nome)
    esperado = (100 / 500 + 10 / 50) + (20 / 200 + 0.5) ** 2
    assert interacao.solicitante == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Seções quaisquer
# ---------------------------------------------------------------------------

ABERTA = tb.SecaoAberta(
    j_mm4=1.0e5,
    espessura_mm=10.0,
    area_mm2=3000.0,
    wx_mm3=3.0e5,
    wy_mm3=5.0e4,
    area_alma_mm2=1500.0,
    area_mesas_mm2=2000.0,
    empenamento=True,
)


def test_secao_aberta_tau_de_saint_venant_mais_o_cortante():
    # τ_T = 1 kN·m · 10 mm / 10⁵ mm⁴ = 100 MPa; τ_V = 30 kN / 1500 mm² = 20 MPa.
    linhas = tb.linhas_de_torcao("I", {}, ABERTA, FY, [_e(1.0, v=30.0, mx=20.0)], SEM, 3000.0)
    tau = next(v for v in linhas if "cisalhamento" in v.nome)
    assert tau.solicitante == pytest.approx(120.0)
    assert tau.resistente == pytest.approx(0.6 * FY / 1.1)
    assert "empenamento livre" in tau.formula
    sigma = next(v for v in linhas if "normal" in v.nome)
    assert sigma.solicitante == pytest.approx(20e6 / 3.0e5)


def test_secao_aberta_torque_pequeno_fica_como_informacao():
    # τ_T = 0,02·10⁶·10/10⁵ = 2 MPa, bem abaixo de 20 % de 188 MPa.
    linhas = tb.linhas_de_torcao("I", {}, ABERTA, FY, [_e(0.02)], SEM, 3000.0)
    assert [v.nome for v in linhas] == [tb.INFORMATIVO]
    assert "desprezado" in linhas[0].formula


def test_secao_sem_j_avisa():
    sem_j = tb.SecaoAberta(0.0, 10.0, 3000.0, 3e5, 5e4, 1500.0, 2000.0, True)
    linhas = tb.linhas_de_torcao("I", {}, sem_j, FY, [_e(1.0)], SEM, 3000.0)
    assert linhas[0].status == "ALERTA" and "constante de torção J" in linhas[0].formula


def test_sem_torque_uma_linha_de_informacao():
    linhas = tb.linhas_de_torcao("I", {}, ABERTA, FY, [_e(0.0)], SEM, 3000.0)
    assert [v.status for v in linhas] == ["INFO"]


# ---------------------------------------------------------------------------
# Na verificação das barras
# ---------------------------------------------------------------------------


def _barra(t: float, perfil: str = 'U 8" x 17,10'):
    esforcos = [vb.EsforcoNoPonto("ELU", "meio", -5.0, 8.0, 3.0, t=t)]
    return vb.verificar_barra_com_esforcos(
        "V1", perfil, "ASTM A36", esforcos, lx_m=3.0, ly_m=0.5, lb_m=0.5
    )


def test_barra_com_torque_grande_e_verificada_e_pode_reprovar():
    sem = _barra(0.0)
    com = _barra(2.0)
    nomes = [v.nome for v in com.linhas]
    assert any(n.startswith("Torção: cisalhamento") for n in nomes)
    tau = next(v for v in com.linhas if v.nome.startswith("Torção: cisalhamento"))
    assert tau.aproveitamento > 1.0  # U aberto não serve para torção
    assert com.status == "NÃO OK" and sem.status == "OK"
    assert com.aproveitamento > sem.aproveitamento


def test_barra_sem_torque_continua_sem_linha_de_torcao():
    assert not any(v.nome.startswith("Torção") for v in _barra(0.0).linhas)


def test_b2_multiplica_o_torque():
    combinados = [("ELU", "meio", (0.0, 0.0, 0.0, 0.0, 0.0, 1.0))]
    triplas = vb._triplas(combinados, "M1", 1.2)
    assert triplas[0].t == pytest.approx(1.2)
