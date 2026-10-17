"""Núcleo de pórtico plano: conferido contra as soluções fechadas de livro."""

from __future__ import annotations

import math

import pytest

from core import portico_plano as pp

E = 200e6  # kN/m²
SECAO = pp.Secao("teste", area_m2=1e-2, inercia_m4=1e-5, modulo_w_m3=1e-4)
RIGIDA_AXIAL = pp.Secao("rígida", area_m2=1e3, inercia_m4=1e-5)
EI = E * 1e-5


def biapoiada(comprimento=6.0, cargas=(), pontuais=(), secao=SECAO, apoio_j=None):
    return pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", comprimento, 0)),
        barras=(pp.Barra("V1", "A", "B", secao),),
        apoios=(pp.pino("A"), apoio_j or pp.rolete("B")),
        cargas_distribuidas=tuple(cargas),
        cargas_pontuais=tuple(pontuais),
    )


def test_biapoiada_com_carga_uniforme():
    w, comprimento = 10.0, 6.0
    r = pp.resolver(biapoiada(comprimento, [pp.CargaDistribuida("V1", -w)]))
    assert r.reacao("A").ry == pytest.approx(w * comprimento / 2)
    assert r.reacao("B").ry == pytest.approx(w * comprimento / 2)
    barra = r.barra("V1")
    assert barra.m_max.m == pytest.approx(w * comprimento**2 / 8, rel=1e-9)
    assert barra.m_max.x == pytest.approx(comprimento / 2, abs=1e-9)
    assert barra.v_max.v == pytest.approx(w * comprimento / 2, rel=1e-9)
    flecha = 5 * w * comprimento**4 / (384 * EI)
    assert barra.flecha_max.flecha == pytest.approx(-flecha, rel=1e-3)
    assert r.residuo_kN < 1e-9


def test_balanco_com_carga_na_ponta():
    p_kN, comprimento = 5.0, 3.0
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", comprimento, 0)),
        barras=(pp.Barra("V1", "A", "B", SECAO),),
        apoios=(pp.engaste("A"),),
        cargas_nodais=(pp.CargaNodal("B", fy=-p_kN),),
    )
    r = pp.resolver(portico)
    assert r.reacao("A").mz == pytest.approx(p_kN * comprimento)
    assert r.barra("V1").pontos[0].m == pytest.approx(-p_kN * comprimento)
    assert r.deslocamentos["B"][1] == pytest.approx(-p_kN * comprimento**3 / (3 * EI))
    assert r.barra("V1").pontos[-1].dy == pytest.approx(-p_kN * comprimento**3 / (3 * EI))


def test_biengastada_com_carga_uniforme():
    w, comprimento = 12.0, 5.0
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", comprimento, 0)),
        barras=(pp.Barra("V1", "A", "B", SECAO),),
        apoios=(pp.engaste("A"), pp.engaste("B")),
        cargas_distribuidas=(pp.CargaDistribuida("V1", -w),),
    )
    barra = pp.resolver(portico).barra("V1")
    assert barra.pontos[0].m == pytest.approx(-w * comprimento**2 / 12)
    meio = min(barra.pontos, key=lambda p: abs(p.x - comprimento / 2))
    assert meio.m == pytest.approx(w * comprimento**2 / 24)
    assert meio.flecha == pytest.approx(-w * comprimento**4 / (384 * EI), rel=1e-3)


def test_carga_triangular_e_concentrada():
    q, comprimento = 9.0, 6.0
    r = pp.resolver(biapoiada(comprimento, [pp.CargaDistribuida("V1", 0.0, -q)]))
    assert r.reacao("A").ry == pytest.approx(q * comprimento / 6)
    assert r.reacao("B").ry == pytest.approx(q * comprimento / 3)
    assert r.barra("V1").m_max.m == pytest.approx(q * comprimento**2 / (9 * math.sqrt(3)), rel=1e-4)
    p_kN, a = 10.0, 2.0
    r2 = pp.resolver(biapoiada(comprimento, pontuais=[pp.CargaPontual("V1", a, fy=-p_kN)]))
    assert r2.reacao("A").ry == pytest.approx(p_kN * (comprimento - a) / comprimento)
    assert r2.barra("V1").m_max.m == pytest.approx(p_kN * a * (comprimento - a) / comprimento)


# ------------------------------------------------------------------ vigas inclinadas
def inclinada(apoio_j, carga):
    """Longarina de 3 m na horizontal e 2 m de altura (α = 33,7°)."""
    return pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", 3.0, 2.0)),
        barras=(pp.Barra("L1", "A", "B", SECAO),),
        apoios=(pp.pino("A"), apoio_j),
        cargas_distribuidas=(carga,),
    )


def test_inclinada_com_carga_por_metro_horizontal_e_apoio_movel():
    """Vertical por metro horizontal: M_máx = w·L_h²/8, como na viga horizontal equivalente."""
    w, vao_h = 4.0, 3.0
    r = pp.resolver(
        inclinada(pp.rolete("B"), pp.CargaDistribuida("L1", -w, direcao=pp.GLOBAL_Y_PROJETADA))
    )
    assert r.reacao("A").ry + r.reacao("B").ry == pytest.approx(w * vao_h)
    assert r.reacao("B").rx == 0.0 and r.reacao("A").rx == pytest.approx(0.0, abs=1e-9)
    barra = r.barra("L1")
    assert barra.angulo_graus == pytest.approx(math.degrees(math.atan2(2, 3)))
    assert barra.m_max.m == pytest.approx(w * vao_h**2 / 8, rel=1e-9)
    # A componente ao longo da barra vira esforço normal: comprime embaixo, traciona em cima.
    assert barra.pontos[0].n < 0 < barra.pontos[-1].n or barra.pontos[0].n > 0 > barra.pontos[-1].n


def test_inclinada_reta_com_pino_nas_duas_pontas_nao_tem_empuxo():
    """Barra reta pino-pino com carga vertical: a parcela axial divide-se igual pelas pontas e
    cada reação sai vertical — sem empuxo horizontal; o normal vai de compressão a tração."""
    w = 4.0
    r = pp.resolver(
        inclinada(pp.pino("B"), pp.CargaDistribuida("L1", -w, direcao=pp.GLOBAL_Y_PROJETADA))
    )
    assert r.reacao("A").rx == pytest.approx(0.0, abs=1e-6)
    assert r.reacao("B").rx == pytest.approx(0.0, abs=1e-6)
    barra = r.barra("L1")
    assert barra.m_max.m == pytest.approx(w * 3.0**2 / 8, rel=1e-6)
    assert barra.pontos[0].n == pytest.approx(-barra.pontos[-1].n, rel=1e-6)
    assert r.residuo_kN < 1e-9


def test_longarina_dobrada_com_trecho_horizontal_no_topo_tem_empuxo():
    """Com um trecho horizontal no topo (como a longarina do curso), pino-pino dá empuxo."""
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", 3.0, 2.0), pp.No("C", 3.3, 2.0)),
        barras=(pp.Barra("L1", "A", "B", SECAO), pp.Barra("L2", "B", "C", SECAO)),
        apoios=(pp.pino("A"), pp.pino("C")),
        cargas_distribuidas=(
            pp.CargaDistribuida("L1", -4.0, direcao=pp.GLOBAL_Y_PROJETADA),
            pp.CargaDistribuida("L2", -4.0),
        ),
    )
    r = pp.resolver(portico)
    assert abs(r.reacao("A").rx) > 0.1
    assert r.reacao("A").rx == pytest.approx(-r.reacao("C").rx)
    assert r.reacao("A").ry + r.reacao("C").ry == pytest.approx(4.0 * 3.3)
    assert r.residuo_kN < 1e-9


def test_peso_proprio_por_metro_de_barra():
    secao = pp.Secao("p", 1e-2, 1e-5, peso_kN_m=0.5)
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", 3.0, 4.0)),
        barras=(pp.Barra("L1", "A", "B", secao),),
        apoios=(pp.pino("A"), pp.rolete("B")),
        peso_proprio=True,
    )
    r = pp.resolver(portico)
    assert r.reacao("A").ry + r.reacao("B").ry == pytest.approx(0.5 * 5.0)  # barra de 5 m


# ------------------------------------------------------------------ pórticos e rótulas
def test_l_engastado_com_carga_na_ponta_da_viga():
    """Pilar engastado (h) e viga em balanço (a): flecha = P·a³/3EI + (P·a·h/EI)·a."""
    p_kN, h, a = 3.0, 4.0, 2.0
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", 0, h), pp.No("C", a, h)),
        barras=(pp.Barra("P1", "A", "B", RIGIDA_AXIAL), pp.Barra("V1", "B", "C", RIGIDA_AXIAL)),
        apoios=(pp.engaste("A"),),
        cargas_nodais=(pp.CargaNodal("C", fy=-p_kN),),
    )
    r = pp.resolver(portico)
    assert r.reacao("A").mz == pytest.approx(p_kN * a)
    esperado = p_kN * a**3 / (3 * EI) + p_kN * a * h / EI * a
    assert r.deslocamentos["C"][1] == pytest.approx(-esperado, rel=1e-6)
    assert r.barra("P1").n_max.n == pytest.approx(-p_kN)  # o pilar comprime


def test_rotula_interna_gerber():
    """Engaste em A, rótula em B, rolete em C, carga w em BC: R_C = w·b/2 e M_A = −w·b/2·a."""
    w, a, b = 6.0, 2.0, 4.0
    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", a, 0), pp.No("C", a + b, 0)),
        barras=(pp.Barra("V1", "A", "B", SECAO), pp.Barra("V2", "B", "C", SECAO, rotula_i=True)),
        apoios=(pp.engaste("A"), pp.rolete("C")),
        cargas_distribuidas=(pp.CargaDistribuida("V2", -w),),
    )
    r = pp.resolver(portico)
    assert r.reacao("C").ry == pytest.approx(w * b / 2)
    assert r.barra("V1").pontos[0].m == pytest.approx(-w * b / 2 * a)
    assert r.barra("V2").pontos[0].m == pytest.approx(0.0, abs=1e-9)


def test_tensao_e_estrutura_hipostatica():
    r = pp.resolver(biapoiada(4.0, [pp.CargaDistribuida("V1", -10.0)]))
    pior = r.barra("V1").tensao_max
    assert pior is not None and pior.tensao_MPa == pytest.approx(20.0 / 1e-4 / 1e3)
    with pytest.raises(pp.PorticoInvalido, match="hipostática"):
        pp.resolver(
            biapoiada(4.0, [pp.CargaDistribuida("V1", -10.0)], apoio_j=pp.Apoio("B", True, False))
        )


def test_secao_de_perfil_do_catalogo():
    s = pp.secao_de_perfil("W 200 x 15,0")
    assert (
        s.area_m2 > 0
        and s.inercia_m4 > 0
        and s.modulo_w_m3
        and s.peso_kN_m == pytest.approx(15.0 * 9.80665 / 1e3, rel=0.05)
    )


def test_confere_com_o_solver_antigo_do_programa():
    """Pórtico dobrado com carga perpendicular: o núcleo novo e o structural_2d dão o mesmo."""
    from core import structural_2d as s2d

    e_mpa, a_mm2, i_mm4, q = 200e3, 1e4, 1e7, -3.0  # q em kN/m = N/mm
    coordenadas = {"A": (0, 0), "B": (0, 3000), "C": (2000, 4000), "D": (5000, 4000)}
    ligacoes = (("P1", "A", "B"), ("V1", "B", "C"), ("V2", "C", "D"))
    antigo = s2d.analisar_portico(
        [
            s2d.NoPortico(1, *coordenadas["A"], True, True, True),
            s2d.NoPortico(2, *coordenadas["B"]),
            s2d.NoPortico(3, *coordenadas["C"]),
            s2d.NoPortico(4, *coordenadas["D"], False, True, False),
        ],
        [
            s2d.ElementoPortico(k + 1, k + 1, k + 2, a_mm2, i_mm4, e_mpa, q if k else 0.0)
            for k in range(3)
        ],
    )
    secao = pp.Secao("s", a_mm2 * 1e-6, i_mm4 * 1e-12)
    novo = pp.resolver(
        pp.Portico(
            nos=tuple(pp.No(n, x / 1e3, y / 1e3) for n, (x, y) in coordenadas.items()),
            barras=tuple(pp.Barra(nome, i, j, secao) for nome, i, j in ligacoes),
            apoios=(pp.engaste("A"), pp.rolete("D")),
            cargas_distribuidas=(
                pp.CargaDistribuida("V1", q, direcao=pp.LOCAL_Y),
                pp.CargaDistribuida("V2", q, direcao=pp.LOCAL_Y),
            ),
        )
    )
    for indice, no in ((0, "A"), (3, "D")):
        r_antigo = antigo.reacoes_nodais[indice]
        assert novo.reacao(no).rx == pytest.approx(r_antigo["rx_N"] / 1e3, abs=1e-6)
        assert novo.reacao(no).ry == pytest.approx(r_antigo["ry_N"] / 1e3, abs=1e-6)
    assert novo.reacao("A").mz == pytest.approx(antigo.reacoes_nodais[0]["mz_Nmm"] / 1e6)
    for k, no in enumerate(coordenadas):
        d = antigo.deslocamentos_nodais[k]
        assert novo.deslocamentos[no][0] == pytest.approx(d["ux_mm"] / 1e3, abs=1e-9)
        assert novo.deslocamentos[no][1] == pytest.approx(d["uy_mm"] / 1e3, abs=1e-9)


def test_modelo_gravado_em_json_volta_igual():
    import json

    portico = pp.Portico(
        nos=(pp.No("A", 0, 0), pp.No("B", 3.0, 2.0), pp.No("C", 3.3, 2.0)),
        barras=(pp.Barra("L1", "A", "B", SECAO), pp.Barra("L2", "B", "C", SECAO, rotula_j=True)),
        apoios=(pp.pino("A"), pp.Apoio("C", False, True, False)),
        cargas_nodais=(pp.CargaNodal("B", fx=1.0, mz=0.5),),
        cargas_distribuidas=(pp.CargaDistribuida("L1", -4.0, -2.0, pp.GLOBAL_Y_PROJETADA, "Q"),),
        cargas_pontuais=(pp.CargaPontual("L2", 0.1, fy=-3.0, local=True, nome="P"),),
        peso_proprio=True,
    )
    de_volta = pp.de_dicionario(json.loads(json.dumps(pp.para_dicionario(portico))))
    assert de_volta == portico
    with pytest.raises(pp.PorticoInvalido, match="incompleto"):
        pp.de_dicionario({"nos": []})
