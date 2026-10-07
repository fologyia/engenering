"""Cargas do vento num pórtico transversal e a solução pelo solver 2D.

As cargas por metro são a pressão líquida da zona vezes o espaçamento; a solução é conferida pelo
equilíbrio (reações = − cargas aplicadas) e pelo sentido do deslocamento.
"""

from __future__ import annotations

import math

import pytest

from core import vento_portico as vp
from core.vento_edificio import (
    COBERTURA_DUAS_AGUAS,
    COBERTURA_PLANA,
    COBERTURA_UMA_AGUA,
    EntradaEdificio,
    calcular_edificacao,
)

PILAR = vp.SecaoDoElemento(area_mm2=20_000.0, inercia_mm4=5.0e8)
RAFTER = vp.SecaoDoElemento(area_mm2=15_000.0, inercia_mm4=4.0e8)


def galpao(**mudancas) -> EntradaEdificio:
    base = dict(
        v0_m_s=40.0,
        comprimento_a_m=60.0,
        largura_b_m=30.0,
        altura_h_m=8.0,
        cobertura=COBERTURA_DUAS_AGUAS,
        theta_graus=10.0,
        categoria="III",
        grupo_s3=3,
        espacamento_porticos_m=6.0,
    )
    base.update(mudancas)
    return EntradaEdificio(**base)


def uma_agua(**mudancas) -> EntradaEdificio:
    base = dict(
        v0_m_s=40.0,
        comprimento_a_m=50.0,
        largura_b_m=30.0,
        altura_h_m=6.0,
        cobertura=COBERTURA_UMA_AGUA,
        theta_graus=10.0,
        categoria="II",
        grupo_s3=3,
        espacamento_porticos_m=5.0,
    )
    base.update(mudancas)
    return EntradaEdificio(**base)


# ------------------------------------------------------------------------------- geometria
def test_geometria_do_portico_de_duas_aguas():
    r = calcular_edificacao(galpao())
    gp = vp.geometria_do_portico(r.geometria)
    topo = 8.0 + 15.0 * math.tan(math.radians(10.0))
    esperados = ((0.0, 0.0), (0.0, 8.0), (15.0, topo), (30.0, 8.0), (30.0, 0.0))
    for obtido, esperado in zip(gp.nos, esperados, strict=True):
        assert obtido == pytest.approx(esperado)
    assert [m.id for m in gp.membros] == list(vp.MEMBROS)
    seno, cosseno = math.sin(math.radians(10.0)), math.cos(math.radians(10.0))
    assert gp.membro(vp.PILAR_ESQUERDO).normal_externa == (-1.0, 0.0)
    assert gp.membro(vp.PILAR_DIREITO).normal_externa == (1.0, 0.0)
    assert gp.membro(vp.AGUA_ESQUERDA).normal_externa == pytest.approx((-seno, cosseno))
    assert gp.membro(vp.AGUA_DIREITA).normal_externa == pytest.approx((seno, cosseno))
    assert gp.membro(vp.AGUA_ESQUERDA).comprimento_m == pytest.approx(15.0 / cosseno)
    for membro in gp.membros:
        assert math.hypot(*membro.normal_externa) == pytest.approx(1.0)
    with pytest.raises(KeyError):
        gp.membro("viga")


def test_geometria_do_portico_de_uma_agua_e_plano():
    r = calcular_edificacao(uma_agua())
    gp = vp.geometria_do_portico(r.geometria)
    alta = 6.0 + 30.0 * math.tan(math.radians(10.0))
    assert gp.nos[1] == pytest.approx((0.0, alta)) and gp.nos[3] == pytest.approx((30.0, 6.0))
    assert gp.nos[2] == pytest.approx((15.0, (alta + 6.0) / 2.0))
    seno, cosseno = math.sin(math.radians(10.0)), math.cos(math.radians(10.0))
    for id_ in (vp.AGUA_ESQUERDA, vp.AGUA_DIREITA):
        assert gp.membro(id_).normal_externa == pytest.approx((seno, cosseno))
    plano = vp.geometria_do_portico(
        calcular_edificacao(galpao(cobertura=COBERTURA_PLANA, theta_graus=0.0)).geometria
    )
    assert plano.nos[2][1] == pytest.approx(8.0)
    assert plano.membro(vp.AGUA_ESQUERDA).normal_externa == pytest.approx((0.0, 1.0))


# ------------------------------------------------------------------------------- cargas por metro
def test_cargas_do_vento_a_90_sao_a_pressao_liquida_vezes_o_espacamento():
    r = calcular_edificacao(galpao())
    casos = [c for c in vp.casos_do_portico(r) if c.alpha == 90]
    assert [c.cpi.valor for c in casos] == [-0.3, 0.0]
    q = r.vento_por_alpha[90].q_kN_m2
    ct, cp = r.coef_telhado, r.coef_paredes
    for caso, cpi in zip(casos, (-0.3, 0.0), strict=True):
        assert caso.faixa_x_m is None
        assert caso.carga(vp.PILAR_ESQUERDO).carga_kN_m == pytest.approx(q * (cp.a_90 - cpi) * 6.0)
        assert caso.carga(vp.PILAR_DIREITO).carga_kN_m == pytest.approx(q * (cp.b_90 - cpi) * 6.0)
        assert caso.carga(vp.AGUA_ESQUERDA).carga_kN_m == pytest.approx(q * (ct.efi_90 - cpi) * 6.0)
        assert caso.carga(vp.AGUA_DIREITA).carga_kN_m == pytest.approx(q * (ct.ghj_90 - cpi) * 6.0)
    caso = casos[0]
    assert caso.carga(vp.PILAR_ESQUERDO).zona == "A (barlavento)"
    assert caso.carga(vp.AGUA_DIREITA).zona == "G, H e J (sotavento)"


def test_cargas_do_vento_a_0_mudam_por_faixa_de_posicao():
    r = calcular_edificacao(galpao())  # x = 15 m, a/2 = 30 m, a = 60 m
    casos = [c for c in vp.casos_do_portico(r) if c.alpha == 0 and c.cpi.valor == -0.3]
    assert [c.faixa_x_m for c in casos] == [(0.0, 15.0), (15.0, 30.0), (30.0, 60.0)]
    q = r.vento_por_alpha[0].q_kN_m2
    cp, ct = r.coef_paredes, r.coef_telhado
    esperados = [(cp.a1_b1_0, ct.eg_0), (cp.a2_b2_0, ct.fh_0), (cp.a3_b3_0, ct.ij_0)]
    for caso, (ce_parede, ce_telhado) in zip(casos, esperados, strict=True):
        assert caso.carga(vp.PILAR_ESQUERDO).carga_kN_m == pytest.approx(
            q * (ce_parede + 0.3) * 6.0
        )
        assert caso.carga(vp.PILAR_DIREITO).carga_kN_m == pytest.approx(q * (ce_parede + 0.3) * 6.0)
        assert caso.carga(vp.AGUA_ESQUERDA).carga_kN_m == pytest.approx(
            q * (ce_telhado + 0.3) * 6.0
        )
        assert caso.carga(vp.AGUA_DIREITA).carga_kN_m == caso.carga(vp.AGUA_ESQUERDA).carga_kN_m


def test_uma_agua_a_0_ganha_o_ponto_de_quebra_em_b_sobre_2():
    r = calcular_edificacao(
        uma_agua(altura_h_m=8.0)
    )  # a = 50, b = 30: x = 12,5; b/2 = 15; a/2 = 25
    casos = [c for c in vp.casos_do_portico(r) if c.alpha == 0 and c.cpi.valor == -0.3]
    assert [c.faixa_x_m for c in casos] == [(0.0, 12.5), (12.5, 15.0), (15.0, 25.0), (25.0, 50.0)]
    assert [c.carga(vp.AGUA_ESQUERDA).zona for c in casos] == [
        "H e L (até b/2)",
        "H e L (até b/2)",
        "H e L (de b/2 até a/2)",
        "I e J",
    ]
    assert [c.carga(vp.PILAR_ESQUERDO).zona for c in casos] == [
        "A1 e B1",
        "A2 e B2",
        "A2 e B2",
        "A3 e B3",
    ]


def test_uma_agua_a_menos_90_troca_os_lados_do_vento():
    r = calcular_edificacao(uma_agua())
    por_alpha = {
        c.alpha: c for c in vp.casos_do_portico(r) if c.cpi.valor == -0.3 and c.alpha in (90, -90)
    }
    q = r.vento_por_alpha[90].q_kN_m2
    cp, ct = r.coef_paredes, r.coef_telhado
    assert por_alpha[90].carga(vp.PILAR_ESQUERDO).carga_kN_m == pytest.approx(
        q * (cp.a_90 + 0.3) * 5.0
    )
    assert por_alpha[-90].carga(vp.PILAR_DIREITO).carga_kN_m == pytest.approx(
        q * (cp.a_90 + 0.3) * 5.0
    )
    assert por_alpha[-90].carga(vp.PILAR_ESQUERDO).carga_kN_m == pytest.approx(
        q * (cp.b_90 + 0.3) * 5.0
    )
    assert por_alpha[-90].carga(vp.AGUA_ESQUERDA).carga_kN_m == pytest.approx(
        q * (ct.hi_m90 + 0.3) * 5.0
    )
    assert por_alpha[-90].carga(vp.AGUA_DIREITA).carga_kN_m == pytest.approx(
        q * (ct.lj_m90 + 0.3) * 5.0
    )


def test_tabela_do_portico_tem_quatro_linhas_por_caso():
    r = calcular_edificacao(galpao())
    casos = vp.casos_do_portico(r)
    linhas = vp.tabela_do_portico(casos)
    assert len(linhas) == 4 * len(casos)
    assert {"Caso", "Elemento", "Zona", "C_e", "Carga normal (kN/m)"} <= set(linhas[0])
    assert any(
        linha["Faixa a partir da empena de barlavento"] == "toda a extensão" for linha in linhas
    )
    assert any(
        "15,00 a 30,00 m" in str(linha["Faixa a partir da empena de barlavento"])
        for linha in linhas
    )


# ------------------------------------------------------------------------------- solução
@pytest.mark.parametrize(
    "entrada",
    [galpao(), galpao(cobertura=COBERTURA_PLANA, theta_graus=0.0), uma_agua()],
    ids=["duas-aguas", "plana", "uma-agua"],
)
@pytest.mark.parametrize("engastado", [True, False])
def test_reacoes_equilibram_as_cargas_do_vento(entrada, engastado):
    r = calcular_edificacao(entrada)
    gp = vp.geometria_do_portico(r.geometria)
    for caso in vp.casos_do_portico(r):
        s = vp.resolver_portico(gp, caso, pilar=PILAR, rafter=RAFTER, bases_engastadas=engastado)
        rh = sum(item["Rh (kN)"] for item in s.reacoes)
        rv = sum(item["Rv (kN)"] for item in s.reacoes)
        assert rh == pytest.approx(-s.soma_cargas_horizontais_kN, abs=1e-6), caso.nome
        assert rv == pytest.approx(-s.soma_cargas_verticais_kN, abs=1e-6), caso.nome
        if not engastado:
            assert all(abs(item["M (kN·m)"]) < 1e-6 for item in s.reacoes)


def test_resultante_vertical_do_vento_a_0_e_de_succao_simetrica():
    r = calcular_edificacao(galpao())
    gp = vp.geometria_do_portico(r.geometria)
    caso = next(
        c
        for c in vp.casos_do_portico(r)
        if c.alpha == 0 and c.cpi.valor == 0.0 and c.faixa_x_m == (0.0, 15.0)
    )
    s = vp.resolver_portico(gp, caso, pilar=PILAR, rafter=RAFTER, bases_engastadas=False)
    esquerda, direita = s.reacoes
    assert esquerda["Rv (kN)"] == pytest.approx(direita["Rv (kN)"], abs=1e-6)
    assert esquerda["Rh (kN)"] == pytest.approx(-direita["Rh (kN)"], abs=1e-6)
    assert s.soma_cargas_verticais_kN > 0  # sucção no telhado levanta o pórtico
    assert esquerda["Rv (kN)"] < 0  # e as bases seguram para baixo


def _caso_manual(**cargas_kN_m: float) -> vp.CasoPortico:
    """Caso só com as cargas pedidas (kN/m, normais, + = pressão); o restante fica zerado."""
    from core.vento_coeficientes import SugestaoCpi

    itens = tuple(
        vp.CargaNoMembro(id_, "manual", 0.0, 0.0, cargas_kN_m.get(id_, 0.0)) for id_ in vp.MEMBROS
    )
    return vp.CasoPortico("manual", 90, SugestaoCpi(0.0, "manual", "teste"), None, itens)


def test_pressao_no_pilar_de_barlavento_empurra_o_portico_para_sotavento():
    gp = vp.geometria_do_portico(calcular_edificacao(galpao()).geometria)
    caso = _caso_manual(**{vp.PILAR_ESQUERDO: 5.0})  # 5 kN/m sobre a parede de barlavento
    engastado = vp.resolver_portico(gp, caso, pilar=PILAR, rafter=RAFTER, bases_engastadas=True)
    ux = {d["no"]: d["ux_mm"] for d in engastado.deslocamentos}
    assert ux[2] > 0 and ux[4] > 0  # os beirais vão para +y, o sentido do vento
    assert engastado.soma_cargas_horizontais_kN == pytest.approx(5.0 * 8.0)  # 5 kN/m × 8 m
    assert sum(r["Rh (kN)"] for r in engastado.reacoes) == pytest.approx(-40.0, abs=1e-6)
    rotulado = vp.resolver_portico(gp, caso, pilar=PILAR, rafter=RAFTER, bases_engastadas=False)
    assert rotulado.deslocamento_horizontal_max_mm > engastado.deslocamento_horizontal_max_mm
    assert any(abs(item["M (kN·m)"]) > 1.0 for item in engastado.reacoes)


def test_succao_no_telhado_levanta_o_meio_do_vao():
    gp = vp.geometria_do_portico(calcular_edificacao(galpao()).geometria)
    caso = _caso_manual(**{vp.AGUA_ESQUERDA: -3.0, vp.AGUA_DIREITA: -3.0})
    s = vp.resolver_portico(gp, caso, pilar=PILAR, rafter=RAFTER, bases_engastadas=False)
    uy = {d["no"]: d["uy_mm"] for d in s.deslocamentos}
    assert uy[3] > 0 and s.soma_cargas_verticais_kN > 0
    assert sum(r["Rv (kN)"] for r in s.reacoes) == pytest.approx(
        -s.soma_cargas_verticais_kN, abs=1e-6
    )


def test_solucao_cresce_linearmente_com_o_espacamento():
    gp = vp.geometria_do_portico(calcular_edificacao(galpao()).geometria)
    pequeno = calcular_edificacao(galpao(espacamento_porticos_m=3.0))
    grande = calcular_edificacao(galpao(espacamento_porticos_m=6.0))
    c_p = next(c for c in vp.casos_do_portico(pequeno) if c.alpha == 90 and c.cpi.valor == 0.0)
    c_g = next(c for c in vp.casos_do_portico(grande) if c.alpha == 90 and c.cpi.valor == 0.0)
    s_p = vp.resolver_portico(gp, c_p, pilar=PILAR, rafter=RAFTER)
    s_g = vp.resolver_portico(gp, c_g, pilar=PILAR, rafter=RAFTER)
    assert s_g.deslocamento_horizontal_max_mm == pytest.approx(
        2.0 * s_p.deslocamento_horizontal_max_mm
    )


def test_carga_local_de_um_pilar_sob_pressao_aponta_para_dentro():
    gp = vp.geometria_do_portico(calcular_edificacao(galpao()).geometria)
    # Pilar esquerdo: da base ao topo, o eixo local y aponta para −y; a pressão empurra para +y.
    assert vp._carga_local_N_mm(gp.membro(vp.PILAR_ESQUERDO), 2.0) == pytest.approx(-2.0)
    # Pilar direito: do pé ao topo também; a pressão empurra para −y (para dentro), que é o local +y...
    assert vp._carga_local_N_mm(gp.membro(vp.PILAR_DIREITO), 2.0) == pytest.approx(2.0)
    # Sucção troca o sinal.
    assert vp._carga_local_N_mm(gp.membro(vp.PILAR_ESQUERDO), -2.0) == pytest.approx(2.0)
