"""Vento numa edificação paralelepipédica (NBR 6123:2023): zonas, casos, forças e verificações.

Dois tipos de teste: valores conferidos à mão numa caixa simples (planta 40 × 20 m, altura 10 m) e
invariantes físicos que valem para qualquer geometria — a pressão interna não muda a resultante
horizontal, um edifício simétrico não recebe força transversal, a soma das zonas cobre a superfície.
"""

from __future__ import annotations

import math

import pytest

from core import vento_coeficientes as c
from core import vento_edificio as ve
from core.vento_edificio import (
    COBERTURA_DUAS_AGUAS,
    COBERTURA_PLANA,
    COBERTURA_UMA_AGUA,
    EntradaEdificio,
    calcular_edificacao,
)


def caixa(**mudancas) -> EntradaEdificio:
    """Caixa de 40 × 20 m, h = 10 m, telhado plano, V₀ = 40 m/s, categoria II, grupo 3."""
    base = dict(
        v0_m_s=40.0,
        comprimento_a_m=40.0,
        largura_b_m=20.0,
        altura_h_m=10.0,
        cobertura=COBERTURA_PLANA,
        theta_graus=0.0,
        categoria="II",
        grupo_s3=3,
    )
    base.update(mudancas)
    return EntradaEdificio(**base)


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
    )
    base.update(mudancas)
    return EntradaEdificio(**base)


def uma_agua(**mudancas) -> EntradaEdificio:
    base = dict(
        v0_m_s=40.0,
        comprimento_a_m=40.0,
        largura_b_m=20.0,
        altura_h_m=6.0,
        cobertura=COBERTURA_UMA_AGUA,
        theta_graus=10.0,
        categoria="II",
        grupo_s3=3,
    )
    base.update(mudancas)
    return EntradaEdificio(**base)


# ------------------------------------------------------------------------------- caixa à mão
def test_pressoes_dinamicas_por_direcao_conferidas_a_mao():
    r = calcular_edificacao(caixa())
    # α = 0°: superfície frontal 20 × 10 m → classe A (S2 = 1,00 em z = 10 m): q = 0,613·40².
    assert r.classe_por_alpha[0] == "A"
    assert r.vento_por_alpha[0].q_N_m2 == pytest.approx(0.613 * 40.0**2)
    # α = 90°: frontal 40 × 10 m → classe B (S2 = 0,98): V_k = 39,2 m/s.
    assert r.classe_por_alpha[90] == "B"
    assert r.vento_por_alpha[90].vk_m_s == pytest.approx(39.2)
    assert r.vento_por_alpha[90].q_N_m2 == pytest.approx(0.613 * 39.2**2)
    # Vedações: classe A no topo.
    assert r.vento_vedacoes.classe == "A"
    assert r.vento_vedacoes.q_N_m2 == pytest.approx(0.613 * 40.0**2)


def test_resultantes_horizontais_das_paredes_conferidas_a_mao():
    r = calcular_edificacao(caixa())
    q0, q90 = r.vento_por_alpha[0].q_kN_m2, r.vento_por_alpha[90].q_kN_m2
    # Tabela 6: h/b = 0,5 (faixa ≤ 1/2), a/b = 2: C = +0,7, D = −0,3, A = +0,7, B = −0,5.
    assert r.caso(0, -0.3).fx_kN == pytest.approx(q0 * 20.0 * 10.0 * (0.7 + 0.3))
    assert r.caso(90, -0.3).fy_kN == pytest.approx(q90 * 40.0 * 10.0 * (0.7 + 0.5))


def test_empuxo_do_telhado_plano_conferido_a_mao():
    r = calcular_edificacao(caixa())
    q0, q90 = r.vento_por_alpha[0].q_kN_m2, r.vento_por_alpha[90].q_kN_m2
    # θ = 0°, h/b = 0,5: EFI = −0,8; GHJ = −0,4; EG = −0,8; FH = −0,4; I e J (a/b = 2) = −0,2.
    # Vento a 90°: duas metades de 400 m² (e c_pi sobe da sucção interna ao zero).
    assert r.caso(90, 0.0).fz_telhado_kN == pytest.approx(q90 * 400.0 * (0.8 + 0.4))
    assert r.caso(90, -0.3).fz_telhado_kN == pytest.approx(q90 * 400.0 * (0.5 + 0.1))
    # Vento a 0°: x = máx(b/3; a/4) = 10 m → EG 200 m², FH 200 m², IJ 400 m².
    assert r.geometria.x_m == pytest.approx(10.0)
    esperado = q0 * (0.8 * 200.0 + 0.4 * 200.0 + 0.2 * 400.0)
    assert r.caso(0, 0.0).fz_telhado_kN == pytest.approx(esperado)


def test_sinais_das_pressoes_positivo_empurra_para_dentro_negativo_puxa_para_fora():
    r = calcular_edificacao(caixa())
    caso = r.caso(90, -0.3)
    por_zona = {p.zona.id: p for p in caso.pressoes}
    assert por_zona["A"].pressao_liquida_kN_m2 > 0  # barlavento com sucção interna: empurra
    assert por_zona["EFI"].pressao_liquida_kN_m2 < 0  # telhado: puxa
    assert por_zona["A"].pressao_liquida_kN_m2 == pytest.approx(
        r.vento_por_alpha[90].q_kN_m2 * (0.7 + 0.3)
    )
    assert por_zona["A"].forca_liquida_kN == pytest.approx(
        por_zona["A"].pressao_liquida_kN_m2 * por_zona["A"].zona.area_m2
    )


def test_c_pi_da_norma_para_quatro_faces_gera_dois_casos_por_direcao():
    r = calcular_edificacao(caixa())
    assert [caso.alpha for caso in r.casos] == [0, 0, 90, 90]
    assert [caso.cpi.valor for caso in r.casos] == [-0.3, 0.0, -0.3, 0.0]
    duas = calcular_edificacao(caixa(cenario_permeabilidade="duas_faces_longas"))
    assert [(caso.alpha, caso.cpi.valor) for caso in duas.casos] == [(0, -0.3), (90, 0.2)]
    informado = calcular_edificacao(caixa(cpis_informados=(0.5,)))
    assert [(caso.alpha, caso.cpi.valor) for caso in informado.casos] == [(0, 0.5), (90, 0.5)]


# ------------------------------------------------------------------------------- invariantes
@pytest.mark.parametrize(
    "entrada",
    [
        caixa(),
        galpao(),
        galpao(theta_graus=25.0, altura_h_m=12.0),
        uma_agua(),
        uma_agua(theta_graus=20.0, comprimento_a_m=25.0),
    ],
    ids=["caixa", "duas-aguas-10", "duas-aguas-25", "uma-agua-10", "uma-agua-20"],
)
def test_pressao_interna_nao_muda_a_resultante_horizontal(entrada):
    r = calcular_edificacao(entrada)
    for alpha in r.alphas:
        casos = r.casos_do_angulo(alpha)
        assert len(casos) >= 2
        for outro in casos[1:]:
            assert outro.fx_kN == pytest.approx(casos[0].fx_kN, abs=1e-6)
            assert outro.fy_kN == pytest.approx(casos[0].fy_kN, abs=1e-6)


@pytest.mark.parametrize("entrada", [caixa(), galpao(), galpao(theta_graus=25.0)])
def test_edificio_simetrico_nao_recebe_forca_transversal(entrada):
    r = calcular_edificacao(entrada)
    for caso in r.casos_do_angulo(0):
        assert caso.fy_kN == pytest.approx(0.0, abs=1e-6)
    for caso in r.casos_do_angulo(90):
        assert caso.fx_kN == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("entrada", [caixa(), galpao(), uma_agua()])
def test_zonas_cobrem_toda_a_superficie(entrada):
    r = calcular_edificacao(entrada)
    g = r.geometria
    area_telhado = g.a_m * g.b_m / g.cos_theta
    area_longas = g.a_m * (g.h_parede_y0_m + g.h_parede_yb_m)
    area_curtas = 2.0 * g.area_da_parede_curta_m2(0.0, g.b_m)
    for caso in r.casos:
        telhado = sum(p.zona.area_m2 for p in caso.pressoes if p.zona.superficie == "telhado")
        paredes = sum(p.zona.area_m2 for p in caso.pressoes if p.zona.superficie == "parede")
        assert telhado == pytest.approx(area_telhado), caso.nome
        assert paredes == pytest.approx(area_longas + area_curtas), caso.nome


def test_area_da_parede_curta_inclui_a_empena():
    g = ve.geometria_da_edificacao(galpao())
    # Retângulo b × h mais o triângulo de base b e altura (b/2)·tan θ.
    esperado = 30.0 * 8.0 + 0.5 * 30.0 * (15.0 * math.tan(math.radians(10.0)))
    assert g.area_da_parede_curta_m2(0.0, 30.0) == pytest.approx(esperado)
    assert g.area_da_parede_curta_m2(0.0, 15.0) + g.area_da_parede_curta_m2(15.0, 30.0) == (
        pytest.approx(esperado)
    )
    assert g.area_da_parede_curta_m2(5.0, 5.0) == 0.0
    # Uma água: trapézio de altura h_baixa + (h_alta − h_baixa)·(1 − y/b).
    g1 = ve.geometria_da_edificacao(uma_agua())
    alta = 6.0 + 20.0 * math.tan(math.radians(10.0))
    assert g1.area_da_parede_curta_m2(0.0, 20.0) == pytest.approx(20.0 * (alta + 6.0) / 2.0)


def test_geometria_derivada_segue_as_notas_da_norma():
    g = ve.geometria_da_edificacao(galpao())
    assert g.x_m == pytest.approx(min(max(30.0 / 3, 60.0 / 4), 2 * 8.0))  # 15
    assert g.y_telhado_m == pytest.approx(min(8.0, 0.15 * 30.0))  # 4,5
    assert g.faixa_cpe_medio_parede_m == pytest.approx(min(0.2 * 30.0, 8.0))  # 6
    assert g.c1_m == pytest.approx(min(2 * 8.0, 15.0))  # 15
    assert g.h_topo_m == pytest.approx(8.0 + 15.0 * math.tan(math.radians(10.0)))
    # x nunca passa de 2h: prédio baixo e comprido.
    baixo = ve.geometria_da_edificacao(galpao(altura_h_m=4.0))
    assert baixo.x_m == pytest.approx(8.0)


# ------------------------------------------------------------------------------- classe e altura
def test_classe_vem_da_superficie_frontal_de_cada_direcao():
    r = calcular_edificacao(galpao())  # 60 × 30 m, topo a 10,6 m
    assert r.classe_por_alpha == {0: "B", 90: "C"}  # frontal 30 m e 60 m
    pequeno = calcular_edificacao(caixa(comprimento_a_m=20.0, largura_b_m=20.0))
    assert pequeno.classe_por_alpha == {0: "A", 90: "A"}
    forcada = calcular_edificacao(galpao(classe="A"))
    assert forcada.classe_por_alpha == {0: "A", 90: "A"}


def test_altura_de_referencia_topo_ou_beiral():
    topo = calcular_edificacao(galpao())
    beiral = calcular_edificacao(galpao(referencia_altura=ve.REFERENCIA_ALTURA_BEIRAL))
    assert topo.vento_por_alpha[0].altura_m == pytest.approx(topo.geometria.h_topo_m)
    assert beiral.vento_por_alpha[0].altura_m == pytest.approx(8.0)
    assert beiral.vento_por_alpha[0].q_N_m2 < topo.vento_por_alpha[0].q_N_m2


def test_superficie_frontal_acima_de_80_m_usa_o_anexo_a():
    r = calcular_edificacao(galpao(comprimento_a_m=150.0))
    vento = r.vento_por_alpha[90]
    assert vento.classe is None and vento.t_s != 10.0
    assert any("Anexo A" in aviso for aviso in r.avisos)
    assert r.classe_por_alpha[90] == "C"


def test_vedacoes_sao_classe_a_no_topo_e_aceitam_092():
    r = calcular_edificacao(galpao())
    assert r.vento_vedacoes.classe == "A"
    assert r.vento_vedacoes.altura_m == pytest.approx(r.geometria.h_topo_m)
    com_092 = calcular_edificacao(galpao(vedacoes_com_092=True))
    assert com_092.vento_vedacoes.q_N_m2 == pytest.approx(0.92**2 * r.vento_vedacoes.q_N_m2)
    assert com_092.vento_por_alpha[0].q_N_m2 == r.vento_por_alpha[0].q_N_m2  # estrutura não muda


# ------------------------------------------------------------------------------- uma água
def test_uma_agua_vento_a_menos_90_espelha_o_a_90():
    r = calcular_edificacao(uma_agua())
    assert r.alphas == (0, 90, -90)
    assert r.caso(90, -0.3).fy_kN > 0  # sopra para +y
    assert r.caso(-90, -0.3).fy_kN < 0  # sopra para −y
    zonas_90 = {p.zona.id: p.zona for p in r.caso(90, -0.3).pressoes}
    zonas_m90 = {p.zona.id: p.zona for p in r.caso(-90, -0.3).pressoes}
    t = r.coef_telhado
    assert zonas_90["HI"].ce == pytest.approx(t.hi_90) and zonas_90["LJ"].ce == pytest.approx(
        t.lj_90
    )
    assert zonas_m90["HI"].ce == pytest.approx(t.hi_m90)
    assert zonas_m90["LJ"].ce == pytest.approx(t.lj_m90)
    # A parede de barlavento é a do lado de onde o vento sopra: alta em +90°, baixa em −90°.
    a90 = zonas_90["A"].partes[0]
    am90 = zonas_m90["A"].partes[0]
    assert a90.normal == (0.0, -1.0, 0.0) and am90.normal == (0.0, 1.0, 0.0)
    assert a90.area_m2 > am90.area_m2


def test_uma_agua_normal_do_telhado_inclina_para_o_lado_baixo():
    r = calcular_edificacao(uma_agua())
    zona = next(p.zona for p in r.caso(90, 0.0).pressoes if p.zona.id == "HI")
    nx, ny, nz = zona.partes[0].normal
    assert nx == 0.0
    assert ny == pytest.approx(math.sin(math.radians(10.0)))
    assert nz == pytest.approx(math.cos(math.radians(10.0)))


# ------------------------------------------------------------------------------- arrasto e torção
def test_arrasto_global_e_torcao_conferidos_a_mao():
    r = calcular_edificacao(caixa())
    for alpha, (l1, l2) in {0: (20.0, 40.0), 90: (40.0, 20.0)}.items():
        arrasto = r.arrasto[alpha]
        ca = c.coeficiente_arrasto_paralelepipedo(10.0, l1, l2).valor
        q = r.vento_por_alpha[alpha].q_kN_m2
        assert arrasto.ca.valor == pytest.approx(ca)
        assert arrasto.area_frontal_m2 == pytest.approx(l1 * 10.0)
        assert arrasto.forca_kN == pytest.approx(q * ca * l1 * 10.0)
        excentricidade = 0.075 * (20.0 if alpha == 0 else 40.0)  # e_b a 0°, e_a a 90°
        assert arrasto.excentricidade_m == pytest.approx(excentricidade)
        assert arrasto.torsor_kNm == pytest.approx(arrasto.forca_kN * excentricidade)


def test_vizinhanca_aumenta_arrasto_e_excentricidade():
    sem = calcular_edificacao(caixa())
    com = calcular_edificacao(caixa(com_vizinhanca=True, afastamento_vizinha_m=5.0))
    assert com.fv_paredes == pytest.approx(1.3)
    assert com.arrasto[0].forca_kN == pytest.approx(1.3 * sem.arrasto[0].forca_kN)
    assert com.arrasto[0].excentricidade_m == pytest.approx(2.0 * sem.arrasto[0].excentricidade_m)
    # f_v multiplica C_e, não c_pi: a resultante horizontal sobe 1,3×.
    assert com.caso(0, -0.3).fx_kN == pytest.approx(1.3 * sem.caso(0, -0.3).fx_kN)
    with pytest.raises(ValueError):
        calcular_edificacao(caixa(com_vizinhanca=True))


def test_alta_turbulencia_reduz_sotavento_e_usa_a_figura_5():
    sem = calcular_edificacao(caixa())
    com = calcular_edificacao(
        caixa(alta_turbulencia=True, altura_media_vizinhanca_m=10.0, extensao_vizinhanca_m=600.0)
    )
    assert com.alta_turbulencia_por_alpha == {0: True, 90: True}
    ze = {p.zona.id: p.zona.ce for p in com.caso(0, -0.3).pressoes}
    assert ze["D"] == pytest.approx(-0.3 * 2.0 / 3.0)
    assert com.arrasto[0].ca.alta_turbulencia and com.arrasto[0].ca.valor < sem.arrasto[0].ca.valor
    # Sem as vizinhas exigidas pela norma, a redução não é aplicada e a verificação avisa.
    recusada = calcular_edificacao(
        caixa(alta_turbulencia=True, altura_media_vizinhanca_m=10.0, extensao_vizinhanca_m=100.0)
    )
    assert recusada.alta_turbulencia_por_alpha == {0: False, 90: False}
    linhas = [v for v in recusada.verificacoes if "Alta turbulência" in v.nome]
    assert linhas and all(v.status == "ALERTA" for v in linhas)


def test_atrito_so_aparece_em_edificacao_comprida():
    comprida = calcular_edificacao(caixa(comprimento_a_m=100.0, largura_b_m=20.0, altura_h_m=6.0))
    assert comprida.arrasto[0].atrito.aplica  # ℓ₂ = 100 m > 4·6 m
    assert not comprida.arrasto[90].atrito.aplica  # ℓ₂ = 20 m < 4·6 m = 24 m
    assert not calcular_edificacao(caixa()).arrasto[0].atrito.aplica


# ------------------------------------------------------------------------------- vedações
def test_vedacoes_trazem_ce_e_cpe_medio_com_o_q_da_classe_a():
    r = calcular_edificacao(galpao())
    q = r.vento_vedacoes.q_kN_m2
    por_id = {linha.id: linha for linha in r.vedacoes}
    cpe_parede = por_id["parede-cpe-medio"]
    assert cpe_parede.fonte_cpe == "c_pe médio"
    assert cpe_parede.cpe == pytest.approx(r.coef_paredes.cpe_medio)
    assert cpe_parede.pressao_externa_kN_m2 == pytest.approx(q * r.coef_paredes.cpe_medio)
    ct = r.coef_telhado
    assert (
        por_id["telhado-empena"].cpe == ct.empena and por_id["telhado-cumeeira"].cpe == ct.cumeeira
    )
    assert "telhado-beiral" not in por_id  # a 10° a célula do beiral é vazia
    # Pressão líquida = q·(c_pe − c_pi) e o "mais desfavorável" é o de maior módulo.
    linha = por_id["telhado-empena"]
    for cpi, liquida in linha.liquida_por_cpi:
        assert liquida == pytest.approx(q * (ct.empena - cpi))
    assert linha.mais_desfavoravel_kN_m2 == pytest.approx(q * (ct.empena - 0.0))
    # As zonas de Ce também entram, uma por direção.
    assert any(i.startswith("parede-0-") for i in por_id) and any(
        i.startswith("telhado-90-") for i in por_id
    )


def test_vedacoes_da_uma_agua_trazem_as_seis_zonas_da_figura():
    r = calcular_edificacao(uma_agua())
    ids = {linha.id for linha in r.vedacoes}
    assert {f"telhado-{z}" for z in ("h1", "h2", "l1", "l2", "he", "le")} <= ids


# ------------------------------------------------------------------------------- verificações
def _status(r, trecho):
    achadas = [v for v in r.verificacoes if trecho in v.nome]
    assert len(achadas) == 1, (trecho, [v.nome for v in r.verificacoes])
    return achadas[0].status


def test_verificacoes_de_aplicabilidade_de_um_caso_normal():
    r = calcular_edificacao(galpao())
    assert _status(r, "1 ≤ a/b ≤ 4") == "OK"
    assert _status(r, "h/b ≤ 6") == "OK"
    assert _status(r, "θ ≤ 60°") == "OK"
    assert _status(r, "T₁ ≤ 1 s") == "OK"
    assert _status(r, "h/b < 6") == "OK"
    assert _status(r, "camada limite") == "OK"
    assert not any(v.status in ("NÃO OK", "ALERTA") for v in r.verificacoes)


def test_verificacoes_acusam_o_que_sai_do_campo_da_norma():
    comprida = calcular_edificacao(galpao(comprimento_a_m=150.0))
    assert _status(comprida, "1 ≤ a/b ≤ 4") == "ALERTA"
    alto = calcular_edificacao(caixa(altura_h_m=120.0, comprimento_a_m=30.0, largura_b_m=20.0))
    assert _status(alto, "T₁ ≤ 1 s") == "ALERTA"  # T₁ = 0,29·√120 − 0,4 ≈ 2,8 s
    assert _status(alto, "h/b < 6") == "ALERTA"
    assert _status(alto, "h/b ≤ 6") == "OK"  # h/b = 6 ainda está na Tabela 6
    com_t = calcular_edificacao(caixa(altura_h_m=120.0, comprimento_a_m=30.0, largura_b_m=20.0,
                                      periodo_fundamental_s=0.8))  # fmt: skip
    assert _status(com_t, "T₁ ≤ 1 s") == "OK"
    uma = calcular_edificacao(uma_agua(theta_graus=35.0))
    assert _status(uma, "5° ≤ θ ≤ 30°") == "ALERTA"
    beiral = calcular_edificacao(galpao(beiral_m=4.0))
    assert _status(beiral, "Balanço do beiral") == "ALERTA"  # 0,1·b = 3 m
    assert _status(calcular_edificacao(galpao(beiral_m=2.0)), "Balanço do beiral") == "OK"


def test_verificacoes_de_valores_de_apoio_tem_numeros_e_formulas():
    r = calcular_edificacao(galpao())
    info = [v for v in r.verificacoes if v.status == "INFO"]
    assert info and all(v.resistente is not None for v in info)
    q0 = next(v for v in info if v.nome.startswith("q do vento a 0°"))
    assert q0.resistente == pytest.approx(r.vento_por_alpha[0].q_kN_m2)
    assert q0.unidade == "kN/m²" and "0,613" in q0.formula
    fa = next(v for v in info if v.nome.startswith("Força de arrasto F_a do vento a 90°"))
    assert fa.resistente == pytest.approx(r.arrasto[90].forca_kN)
    assert "F_a = q·C_a·A_e·f_v" in fa.formula


# ------------------------------------------------------------------------------- entradas e tabelas
@pytest.mark.parametrize(
    "mudancas",
    [
        dict(comprimento_a_m=10.0, largura_b_m=20.0),  # cumeeira fora do lado maior
        dict(v0_m_s=0.0),
        dict(altura_h_m=-1.0),
        dict(theta_graus=95.0),
        dict(cobertura="abobada"),
        dict(cobertura=COBERTURA_PLANA, theta_graus=10.0),
        dict(classe="D"),
        dict(periodo_fundamental_s=-1.0),
        dict(beiral_m=-1.0),
        dict(espacamento_porticos_m=0.0),
        dict(cpis_informados=()),
        dict(referencia_altura="meio"),
    ],
)
def test_entradas_invalidas_viram_erro_claro(mudancas):
    with pytest.raises(ValueError):
        calcular_edificacao(galpao(**mudancas))


def test_tabela_de_pressoes_tem_uma_linha_por_zona_com_unidades():
    r = calcular_edificacao(galpao())
    caso = r.caso(90, -0.3)
    linhas = ve.tabela_de_pressoes(caso)
    assert len(linhas) == len(caso.pressoes)
    assert {"Zona", "C_e", "Área (m²)", "Δp = q·(C_e − c_pi) (kN/m²)", "Força (kN)"} <= set(
        linhas[0]
    )
    assert sum(float(linha["Área (m²)"]) for linha in linhas) == pytest.approx(
        sum(p.zona.area_m2 for p in caso.pressoes)
    )


def test_periodo_estimado_para_estrutura_de_aco_soldada():
    assert ve.estimar_periodo_edificio_aco_s(100.0) == pytest.approx(0.29 * 10.0 - 0.4)
    assert ve.estimar_periodo_edificio_aco_s(1.0) == 0.0  # nunca negativo
