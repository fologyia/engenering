"""Rede de tubos ao longo do dia (simulação estendida)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from core import figuras_no_tempo as fnt
from core import montador_fluidos as fl
from core import rede_de_tubos as rt
from core import rede_no_tempo as rnt
from core.technical_records import avaliar_contrato_registro

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
AGUA = rt.Fluido("Água a 20 °C", 998.2, 1.0016e-3)


@pytest.fixture(scope="module")
def rede():
    desenho = rt.exemplo_desenhado()
    nos, trechos, faltas = rt.rede_do_desenho(desenho, fl.RUGOSIDADES)
    assert not faltas
    return desenho, nos, trechos


def test_padrao_de_exemplo_tem_media_um():
    assert len(rnt.PADRAO_DE_EXEMPLO) == 24
    assert np.mean(rnt.PADRAO_DE_EXEMPLO) == pytest.approx(1.0, abs=2e-3)


def test_sem_tanque_e_padrao_plano_e_a_rede_parada_a_cada_passo(rede):
    _, nos, trechos = rede
    r = rnt.simular(
        nos, trechos, AGUA, rt.Limites(), [], rnt.PADRAO_PLANO, horas=2.0, passo_min=30.0
    )
    fixo = rt.resolver(nos, trechos, AGUA, rt.Limites())
    assert len(r.tempos) == 5 and not r.evento
    for i in range(len(r.tempos)):
        assert r.pressoes[i] == pytest.approx([n.pressao_m for n in fixo.nos])
        assert r.vazoes[i] == pytest.approx([t.vazao_L_s for t in fixo.trechos])


def test_nivel_do_tanque_anda_pelo_balanco_de_volume(rede):
    _, nos, trechos = rede
    tanque = rnt.TanqueDaRede("R2", 200.0, 40.0, 46.0)
    r = rnt.simular(nos, trechos, AGUA, rt.Limites(), [tanque], rnt.PADRAO_DE_EXEMPLO, horas=6.0)
    dt = 600.0
    nivel = 44.0
    for i in range(len(r.tempos) - 1):
        nos_i = [
            rt.No(
                n.nome,
                n.cota_m,
                n.retirada_L_s * r.multiplicador[i],
                n.reservatorio,
                nivel if n.nome == "R2" else n.nivel_m,
            )
            for n in nos
        ]
        q = (
            next(n.vazao_L_s for n in rt.resolver(nos_i, trechos, AGUA).nos if n.nome == "R2")
            / 1000.0
        )
        nivel -= q * dt / 200.0
        assert r.niveis[i + 1, 0] == pytest.approx(nivel, abs=1e-9)
    assert (
        r.multiplicador[0] == rnt.PADRAO_DE_EXEMPLO[0]
        and r.multiplicador[-1] == rnt.PADRAO_DE_EXEMPLO[6]
    )


def test_tanque_pequeno_esvazia_e_para_a_simulacao(rede):
    _, nos, trechos = rede
    # com R1 mais baixo, o tanque R2 abastece a rede inteira e esvazia
    nos = [replace(n, nivel_m=30.0) if n.nome == "R1" else n for n in nos]
    pequeno = rnt.TanqueDaRede("R2", 20.0, 43.5, 44.5)
    r = rnt.simular(nos, trechos, AGUA, rt.Limites(), [pequeno], rnt.PADRAO_PLANO)
    assert "mínimo" in r.evento
    assert "nível" in r.evento and "simulação para" in r.evento
    assert r.status == "NÃO OK"
    assert r.niveis[-1, 0] == pytest.approx(43.5)
    assert r.tempos[-1] < 24 * 3600


def test_dados_ruins_dao_mensagem(rede):
    _, nos, _ = rede
    erros = rnt.problemas(
        nos,
        [rnt.TanqueDaRede("A", 10.0, 1.0, 2.0), rnt.TanqueDaRede("R2", 0.0, 50.0, 40.0)],
        [1.0, -1.0],
        0.0,
        10.0,
    )
    assert any("não é um reservatório" in e for e in erros)
    assert any("área" in e for e in erros)
    assert any("abaixo do máximo" in e for e in erros)
    assert any("multiplicadores" in e for e in erros)
    assert any("horas" in e for e in erros)


def test_cena_e_registro(rede):
    desenho, nos, trechos = rede
    r = rnt.simular(
        nos,
        trechos,
        AGUA,
        rt.Limites(),
        [rnt.TanqueDaRede("R2", 200.0, 40.0, 46.0)],
        rnt.PADRAO_DE_EXEMPLO,
    )
    dados = rnt.cena_da_rede(desenho, r)
    assert len([f for f in dados["formas"] if f["tipo"] == "linha"]) == len(trechos)
    assert [g["titulo"] for g in dados["graficos"]] == [
        "Nível dos tanques",
        "Pressão nos nós mais baixos",
        "Consumo da rede",
    ]
    registro = rnt.registro(r, rnt.PADRAO_DE_EXEMPLO, 24.0, 10.0)
    assert avaliar_contrato_registro(registro)["valido"]
    assert len(fnt.figuras_do_registro(registro["resultados"])) == 2
    assert rnt.hora_em_texto(67800) == "18h50" and rnt.hora_em_texto(90000) == "01h00 do dia 2"


def test_pagina_simula_o_dia():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/rede_de_tubos.py").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("atende o dia inteiro" in s.value for s in at.success)
    at.button(key="rede_dia_exemplo").click().run()
    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Menor pressão do dia"].endswith("18h00)")
