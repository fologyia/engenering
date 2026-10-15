"""Longarina da escada em grade: viga biapoiada inclinada com metade de cada degrau."""

from __future__ import annotations

import math

import pytest

from core import degrau_escada as de
from core import longarina_escada as le
from core import viga_de_piso as vp


@pytest.fixture(scope="module")
def escada() -> de.ResultadoEscada:
    return de.calcular_escada(de.EntradaDegrau())


def test_vao_automatico_e_a_projecao_do_lance_maior(escada):
    lg = le.calcular_longarina(escada, le.EntradaLongarina())
    assert not lg.vao_informado
    assert lg.vao_horizontal_m == pytest.approx(escada.lances.projecao_lance_maior_mm / 1000)
    alfa = math.radians(escada.geometria.alfa_graus)
    assert lg.vao_inclinado_m == pytest.approx(lg.vao_horizontal_m / math.cos(alfa))
    assert lg.lb_m == pytest.approx(escada.geometria.b_mm / 1000 / math.cos(alfa))


def test_cargas_e_momento_iguais_a_viga_horizontal_equivalente(escada):
    """w·cos²α no vão L_h/cos α dá o mesmo momento que w no vão L_h."""
    e = le.EntradaLongarina(vao_horizontal_m=3.0, guarda_corpo_kN_m=0.0)
    lg = le.calcular_longarina(escada, e)
    assert lg.vao_informado and lg.vao_horizontal_m == 3.0
    assert lg.carga_sc_kN_m == pytest.approx(escada.entrada.q_kN_m2 * escada.entrada.L_mm / 2000)
    cos_a = math.cos(math.radians(lg.alfa_graus))
    sc_perp = lg.carga_sc_kN_m * cos_a**2
    m_sc = sc_perp * lg.vao_inclinado_m**2 / 8
    assert m_sc == pytest.approx(lg.carga_sc_kN_m * 3.0**2 / 8)
    # Deslocamento vertical = flecha perpendicular / cos α.
    assert lg.deslocamento_vertical_mm == pytest.approx(lg.flecha_perpendicular_mm / cos_a)
    assert lg.limite_flecha_mm == pytest.approx(lg.vao_inclinado_m * 1000 / 350)


def test_reacao_soma_as_cargas_verticais(escada):
    lg = le.calcular_longarina(escada, le.EntradaLongarina(vao_horizontal_m=2.0))
    cos_a = math.cos(math.radians(lg.alfa_graus))
    vertical = (
        lg.carga_sc_kN_m
        + lg.carga_degraus_kN_m
        + (lg.carga_gc_kN_m + lg.viga.peso_proprio_kN_m) / cos_a
    )
    assert 2 * lg.reacao_vertical_kN == pytest.approx(vertical * 2.0)


def test_perfil_fraco_nao_atende_e_vao_invalido(escada):
    longo = le.calcular_longarina(
        escada, le.EntradaLongarina(perfil='U 3" x 6,10', vao_horizontal_m=8.0)
    )
    assert longo.status != "OK"
    with pytest.raises(le.LongarinaInvalida):
        le.calcular_longarina(escada, le.EntradaLongarina(guarda_corpo_kN_m=-1.0))
    assert isinstance(longo.viga, vp.ResultadoVigaDePiso)
