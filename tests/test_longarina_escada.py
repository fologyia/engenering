"""Longarina da escada pelo núcleo de pórtico plano: conferida contra as contas de mão."""

from __future__ import annotations

import math

import pytest

from core import degrau_escada as de
from core import escada_lances as el
from core import longarina_escada as le
from core import portico_plano as pp
from core import section_catalog as sc
from core import verificacao_barras as vb


@pytest.fixture(scope="module")
def escada() -> de.ResultadoEscada:
    return de.calcular_escada(de.EntradaDegrau())


def _carga_elu_inclinada(lg: le.LongarinaDoLance) -> float:
    cos_a = math.cos(math.radians(lg.alfa_graus))
    return (
        lg.gamma_g * lg.cargas.permanente_inclinada(cos_a) + lg.gamma_q * lg.cargas.sobrecarga_kN_m
    )


def test_lances_iguais_saem_numa_longarina_so_com_a_linha_dos_bocéis(escada):
    res = le.calcular_longarina(escada, le.EntradaLongarina())
    assert escada.lances.n_lances == 2 and len(res.longarinas) == 1
    lg = res.longarinas[0]
    assert lg.lances == (1, 2) and lg.titulo == "Longarina dos lances 1, 2"
    g = escada.geometria
    assert not lg.vao_informado
    assert lg.vao_horizontal_m == pytest.approx(escada.lances.k * g.b_mm / 1000)
    assert lg.alfa_graus == pytest.approx(g.alfa_graus)
    [trecho] = lg.trechos
    assert trecho.lb_m == pytest.approx(g.b_mm / 1000 / math.cos(math.radians(g.alfa_graus)))


def test_cargas_por_longarina(escada):
    lg = le.calcular_longarina(escada, le.EntradaLongarina(guarda_corpo_kN_m=0.4)).longarinas[0]
    c = lg.cargas
    assert c.sobrecarga_kN_m == pytest.approx(escada.entrada.q_kN_m2 * escada.entrada.L_mm / 2000)
    b = escada.geometria.b_mm / 1000
    assert c.degraus_kN_m == pytest.approx(escada.peso_unitario_kg * le.G / 1e3 / 2 / b)
    perfil = sc.obter_perfil(le.EntradaLongarina().perfil)
    assert c.peso_proprio_kN_m == pytest.approx(perfil.massa_kg_m * le.G / 1e3)


def test_reta_pino_pino_bate_com_a_viga_horizontal_equivalente(escada):
    """Sem empuxo; M = w·L_h²/8; reações verticais = w·L_h/2; flecha = 5·w⊥·L⁴/384EI."""
    lg = le.calcular_longarina(escada, le.EntradaLongarina()).longarinas[0]
    w = _carga_elu_inclinada(lg)
    vao_h = lg.vao_horizontal_m
    for reacao in lg.reacoes(le.ELU):
        assert reacao.rx == pytest.approx(0.0, abs=1e-6)
        assert reacao.ry == pytest.approx(w * vao_h / 2, rel=1e-9)
    assert lg.elu.barra(le.TRECHO_INCLINADO).m_max.m == pytest.approx(w * vao_h**2 / 8, rel=1e-6)
    cos_a = math.cos(math.radians(lg.alfa_graus))
    w_servico = lg.cargas.permanente_inclinada(cos_a) + lg.cargas.sobrecarga_kN_m
    secao = pp.secao_de_perfil(le.EntradaLongarina().perfil)
    ei = secao.e_kN_m2 * secao.inercia_m4
    flecha = 5 * w_servico * cos_a**2 * lg.vao_inclinado_m**4 / (384 * ei) * 1e3
    [trecho] = lg.trechos
    assert abs(trecho.flecha_mm) == pytest.approx(flecha, rel=1e-3)
    assert trecho.limite_flecha_mm == pytest.approx(lg.vao_inclinado_m * 1e3 / 350)


def test_rolete_no_topo_nao_muda_o_momento_da_reta(escada):
    pino = le.calcular_longarina(escada, le.EntradaLongarina()).longarinas[0]
    rolete = le.calcular_longarina(escada, le.EntradaLongarina(apoio_topo=le.ROLETE)).longarinas[0]
    assert rolete.elu.barra(le.TRECHO_INCLINADO).m_max.m == pytest.approx(
        pino.elu.barra(le.TRECHO_INCLINADO).m_max.m, rel=1e-6
    )
    assert rolete.reacoes(le.ELU)[1].rx == 0.0


def test_longarina_dobrada_tem_empuxo_e_equilibrio(escada):
    e = le.EntradaLongarina(trecho_topo_m=0.30)
    lg = le.calcular_longarina(escada, e).longarinas[0]
    assert [t.barra for t in lg.trechos] == [le.TRECHO_INCLINADO, le.TRECHO_TOPO]
    pe, topo = lg.reacoes(le.ELU)
    assert abs(pe.rx) > 0.5 and pe.rx == pytest.approx(-topo.rx)
    w = _carga_elu_inclinada(lg)
    w_topo = lg.gamma_g * lg.cargas.permanente_topo + lg.gamma_q * lg.cargas.sobrecarga_topo_kN_m
    total = w * lg.vao_horizontal_m + w_topo * 0.30
    assert pe.ry + topo.ry == pytest.approx(total, rel=1e-9)
    assert lg.elu.residuo_kN < 1e-9


def test_lances_diferentes_dao_longarinas_diferentes(escada):
    r = de.calcular_escada(de.EntradaDegrau(H_mm=5400))
    esc = el.montar_escada(
        r, [el.PatamarInformado(1500, 1200, 1000), el.PatamarInformado(3700, 800, None, True)]
    )
    res = le.calcular_longarina(r, le.EntradaLongarina(), esc)
    assert [lg.lances for lg in res.longarinas] == [(1,), (2,), (3,)]
    assert res.governante.lances == (2,)  # o lance mais longo
    assert res.status == "OK"
    assert all(v.status in ("OK", "ALERTA", "NÃO OK") for v in res.decisivas)
    assert len(res.decisivas) < len(res.verificacoes)  # as informativas ficam só na página


def test_distancia_informada_vale_para_o_lance_mais_longo(escada):
    r = de.calcular_escada(de.EntradaDegrau(H_mm=5400))
    esc = el.montar_escada(r, [el.PatamarInformado(1500, 1200)])
    res = le.calcular_longarina(r, le.EntradaLongarina(vao_horizontal_m=4.0), esc)
    informadas = [lg for lg in res.longarinas if lg.vao_informado]
    assert len(informadas) == 1 and informadas[0].vao_horizontal_m == 4.0
    assert any("lance mais longo" in aviso for aviso in res.avisos)


def test_perfil_fraco_nao_atende_e_entradas_invalidas(escada):
    longo = le.calcular_longarina(
        escada, le.EntradaLongarina(perfil='U 3" x 6,10', vao_horizontal_m=8.0)
    )
    assert longo.status == "NÃO OK"
    for errada in (
        le.EntradaLongarina(guarda_corpo_kN_m=-1.0),
        le.EntradaLongarina(apoio_pe=le.ROLETE, apoio_topo=le.ROLETE),
        le.EntradaLongarina(aco="aço que não existe"),
        le.EntradaLongarina(perfil="perfil que não existe"),
        le.EntradaLongarina(trecho_topo_m=-0.1),
    ):
        with pytest.raises(le.LongarinaInvalida):
            le.calcular_longarina(escada, errada)


def test_tabelas_da_longarina(escada):
    lg = le.calcular_longarina(escada, le.EntradaLongarina(trecho_topo_m=0.3)).longarinas[0]
    assert len(le.linhas_dos_trechos(lg)) == 2
    assert len(le.linhas_das_reacoes(lg)) == 8  # 2 apoios × G, Q, ELS e ELU
    assert all("-0,00" not in celula for linha in le.linhas_das_reacoes(lg) for celula in linha)
    assert any("topo" in linha[0] for linha in le.linhas_das_cargas(lg))


def test_verificacao_com_esforcos_de_fora_sem_torcao():
    esforcos = [vb.EsforcoNoPonto("ELU", "meio", -5.0, 8.0, 3.0)]
    r = vb.verificar_barra_com_esforcos(
        "V1", 'U 8" x 17,10', "ASTM A36", esforcos, lx_m=3.0, ly_m=0.5, lb_m=0.5
    )
    assert r.status == "OK" and r.aproveitamento and 0 < r.aproveitamento < 1
    assert not any(v.nome.startswith("Torção") for v in r.linhas)
    with pytest.raises(ValueError):
        vb.verificar_barra_com_esforcos(
            "V1", 'U 8" x 17,10', "ASTM A36", [], lx_m=1, ly_m=1, lb_m=1
        )
