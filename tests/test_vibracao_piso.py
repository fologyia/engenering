"""Vibração do piso nas Vigas de piso: NBR 8800:2008 Anexo L."""

from __future__ import annotations

import math

import pytest

from core import section_catalog as sc
from core import viga_de_piso as vp

BASE = vp.EntradaVigaDePiso(vao_m=8.0, perfil="W 310 x 38,7")


def _linha(r, inicio):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def test_flecha_na_combinacao_frequente_e_a_frequencia():
    r = vp.calcular(BASE)
    perfil = sc.obter_perfil(BASE.perfil)
    q = r.cargas_kN_m["PP"] + r.cargas_kN_m["PE"] + 0.6 * r.cargas_kN_m["SC"]  # ψ₁ = 0,6
    l_mm = BASE.vao_m * 1e3
    delta = 5 * q * l_mm**4 / (384 * 200_000 * perfil.ix_mm4)
    assert r.flecha_vibracao_mm == pytest.approx(delta)
    assert r.frequencia_piso_Hz == pytest.approx(18 / math.sqrt(delta))
    assert r.flecha_vibracao_mm < r.flecha_mm  # a frequente é menor que a rara


def test_onde_se_caminha_o_limite_e_20_mm():
    r = vp.calcular(BASE)
    linha = _linha(r, "Vibração: flecha total")
    assert linha.resistente == 20.0 and "L.3.2" in linha.referencia
    assert linha.status == "OK"


def test_onde_se_pula_o_limite_e_9_mm():
    r = vp.calcular(vp.EntradaVigaDePiso(**{**BASE.__dict__, "uso_vibracao": vp.USO_PULAR}))
    linha = _linha(r, "Vibração: flecha total")
    assert linha.resistente == 9.0 and linha.status == "NÃO OK"
    assert r.status == "NÃO OK"


def test_aerobica_5_mm():
    r = vp.calcular(vp.EntradaVigaDePiso(**{**BASE.__dict__, "uso_vibracao": vp.USO_REPETITIVO}))
    assert _linha(r, "Vibração: flecha total").resistente == 5.0


def test_flecha_do_apoio_soma():
    sem = vp.calcular(BASE)
    com = vp.calcular(vp.EntradaVigaDePiso(**{**BASE.__dict__, "flecha_apoio_mm": 10.0}))
    assert com.flecha_vibracao_mm == pytest.approx(sem.flecha_vibracao_mm + 10.0)
    assert _linha(com, "Vibração: flecha total").status == "NÃO OK"  # 11,9 + 10 > 20
    assert "apoio 10,0 mm" in _linha(com, "Vibração: flecha total").formula


def test_so_manutencao_vale_so_os_3_hz():
    r = vp.calcular(vp.EntradaVigaDePiso(**{**BASE.__dict__, "uso_vibracao": vp.USO_MANUTENCAO}))
    nomes = [v.nome for v in r.verificacoes if v.nome.startswith("Vibração")]
    assert nomes == ["Vibração: frequência natural do piso ≥ 3 Hz"]


def test_abaixo_de_3_hz_reprova_sempre():
    # δ = 40 mm de apoio: f = 18/√(11,9 + 40) ≈ 2,5 Hz.
    r = vp.calcular(
        vp.EntradaVigaDePiso(
            **{**BASE.__dict__, "uso_vibracao": vp.USO_MANUTENCAO, "flecha_apoio_mm": 40.0}
        )
    )
    linha = _linha(r, "Vibração: frequência natural")
    assert r.frequencia_piso_Hz < 3.0 and linha.status == "NÃO OK"


@pytest.mark.parametrize(
    ("campo", "valor", "trecho"),
    [
        ("uso_vibracao", "Discoteca", "Uso do piso"),
        ("flecha_apoio_mm", -1.0, "flecha do apoio"),
        ("flecha_apoio_mm", float("nan"), "flecha do apoio"),
    ],
)
def test_entrada_ruim_explica(campo, valor, trecho):
    erros = vp.validar(vp.EntradaVigaDePiso(**{**BASE.__dict__, campo: valor}))
    assert any(trecho in e for e in erros)


def test_registro_leva_o_uso_do_piso():
    r = vp.calcular(vp.EntradaVigaDePiso(**{**BASE.__dict__, "flecha_apoio_mm": 3.0}))
    registro = vp.registro_viga(r)
    assert registro["entradas"]["uso_do_piso_vibracao"] == vp.USO_CAMINHAR
    assert registro["entradas"]["flecha_do_apoio_mm"] == 3.0
