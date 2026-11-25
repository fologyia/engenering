"""Oráculos da segunda auditoria. N e mm nos cálculos, kN e kN·m nas entradas."""

import math
from dataclasses import replace

import pytest

from core import base_de_pilar as bp
from core import base_de_pilar_soldas as solda
from core import placa_base_pilares as modelo

PADRAO = bp.EntradaBase()


def linha(r, nome):
    return next(v for v in r.verificacoes if v.nome == nome)


def test_t01_compressao_uniforme():
    r = bp.calcular(PADRAO)
    assert r.plano_pressao == pytest.approx((300000 / (458 * 200), 0, 0))
    assert sum(r.forcas_nos_chumbadores) == 0


def test_t02_tracao_simetrica():
    r = bp.calcular(replace(PADRAO, n_sd_kN=-80, v_sd_kN=0))
    assert r.forcas_nos_chumbadores == (20000,) * 4
    assert r.centro_pressao is None


def test_t03_bloco_uniaxial_da_67():
    r = bp.calcular(replace(PADRAO, m_sd_kNm=15))
    # Bloco retangular de 358 mm com o centro a 15/300 m da origem.
    assert r.l_c == pytest.approx(358)
    assert r.centro_pressao == pytest.approx((50, 0))
    assert r.plano_pressao[0] == pytest.approx(300000 / (358 * 200))


@pytest.mark.parametrize("distribuicao", bp.DISTRIBUICOES)
def test_t04_equilibrio_por_quadratura_independente(distribuicao):
    e = replace(PADRAO, m_sd_kNm=-30, m_sd_y_kNm=14, n_sd_kN=75, distribuicao=distribuicao)
    r = bp.calcular(e)
    # Triangulação e quadratura de grau 2. Integra p, xp e yp sem usar as integrais do motor.
    pol = r.zona_comprimida
    c = mx = my = 0.0
    w, ax, ay = r.plano_pressao
    for b, d in zip(pol[1:], pol[2:], strict=False):
        a = pol[0]
        area = abs((b[0] - a[0]) * (d[1] - a[1]) - (d[0] - a[0]) * (b[1] - a[1])) / 2
        for v, u, t in ((a, b, d), (b, d, a), (d, a, b)):
            x, y = ((4 * v[k] + u[k] + t[k]) / 6 for k in (0, 1))
            df = area * (w + ax * x + ay * y) / 3
            c += df
            mx += x * df
            my += y * df
    for (x, y), f in zip(r.geometria.posicoes, r.forcas_nos_chumbadores, strict=True):
        c -= f
        mx -= x * f
        my -= y * f
    assert (c / 1e3, mx / 1e6, my / 1e6) == pytest.approx((75, -30, 14), abs=1e-5)
    assert r.residuos == pytest.approx((0, 0, 0), abs=1e-5)


def test_t05_inverter_os_momentos_inverte_as_barras():
    e = replace(PADRAO, m_sd_kNm=30, m_sd_y_kNm=-14, n_sd_kN=75)
    a, b = bp.calcular(e), bp.calcular(replace(e, m_sd_kNm=-30, m_sd_y_kNm=14))
    assert a.forcas_nos_chumbadores == pytest.approx(b.forcas_nos_chumbadores[::-1])
    assert a.centro_pressao == pytest.approx(tuple(-v for v in b.centro_pressao))


def flexao(d, graute=50, v=7560):
    return bp.flexao_na_argamassa(v, 1, 6640, graute, 12.7, math.pi * d**2 / 4, 250, 1.1)


def test_t06_flexao_varia_com_o_cubo_do_diametro_resistente():
    assert flexao(20).sigma_b / flexao(16).sigma_b == pytest.approx((16 / 20) ** 3)


def test_t07_aumento_do_graute():
    assert flexao(20, 60).momento - flexao(20, 50).momento == pytest.approx(75600)


def test_t08_espessura_e_resistencia_em_momento():
    a, b = (bp.calcular(replace(PADRAO, t_placa_mm=t)) for t in (20, 40))
    assert (a.t_p_min / a.entrada.t_placa_mm) ** 2 == pytest.approx(
        4 * (b.t_p_min / b.entrada.t_placa_mm) ** 2
    )


def test_t09_corte_nulo():
    assert flexao(20, v=0).momento == flexao(20, v=0).sigma_b == 0


def test_t10_atrito_exclusivo_e_opcao_automatica():
    e = replace(PADRAO, n_sd_kN=15.3, v_sd_kN=7.6)
    assert linha(bp.calcular(e), "Cortante: atrito na argamassa").aproveitamento == pytest.approx(
        7.6 / 5.1
    )
    auto = bp.calcular(replace(e, cortante=bp.CORTANTE_AUTO))
    assert linha(auto, bp.LINHA_FLEXAO_NA_ARGAMASSA).solicitante > 0
    assert "direto" in linha(auto, "Mecanismo automático de cortante").formula


def test_t11_sinal_da_componente_muda_a_borda():
    e = replace(
        PADRAO,
        bloco_x_mm=1600,
        bloco_y_mm=2000,
        bloco_z_mm=1000,
        desloc_x_mm=500,
        vx_kN=5,
        vy_kN=0,
        cortante=bp.CORTANTE_DIRETOS,
    )
    a, b = (linha(bp.calcular(replace(e, vx_kN=v)), bp.LINHA_RUPTURA_DA_BORDA) for v in (5, -5))
    assert a.aproveitamento > b.aproveitamento
    assert "ℓx +" in a.formula


def test_t12_trechos_excluidos_recalculam_o_grupo():
    e = replace(PADRAO, perfil='U 6" x 12,20', m_sd_y_kNm=1, perna_pilar_mm=4)
    a, b = bp.calcular(e), bp.calcular(replace(e, solda_mesas_por_dentro=False))
    assert not any("comprimento dos trechos internos da mesa" in v.nome for v in a.verificacoes)
    nome = "Solda do pilar na placa: filete no ponto mais solicitado"
    assert linha(a, nome).solicitante == pytest.approx(linha(b, nome).solicitante)


def test_t13_verificacao_real_com_altura_desconhecida():
    r = bp.calcular(replace(PADRAO, modo_bloco="verificacao", bloco_x_mm=1000, bloco_y_mm=800))
    assert r.situacao == "Inconclusivo"
    assert linha(r, "Geometria real do bloco").status == "ALERTA"


def test_t14_resistencia_individual_generica_nao_valida_resina():
    r = bp.calcular(
        replace(
            PADRAO, n_sd_kN=-5, v_sd_kN=0, ancoragem=bp.ANCORAGEM_QUIMICO, n_rd_fabricante_kN=100
        )
    )
    assert linha(r, "Aderência da resina").resistente is None
    assert linha(r, "Tração sustentada da resina").resistente is None


def test_t15_sem_equilibrio_bloqueia_a_espessura():
    e = replace(PADRAO, m_sd_kNm=2000)
    r = bp.calcular(e)
    assert linha(r, "Placa de base: espessura t_p ≥ t_p,min").solicitante is None
    assert bp.base_mais_leve(e) is None


def test_t16_busca_sai_do_diametro_reprovado():
    e = replace(
        PADRAO,
        chumbador='3/4"',
        n_sd_kN=100,
        m_sd_kNm=10,
        v_sd_kN=20,
        t_placa_mm=16,
        cortante=bp.CORTANTE_ARRUELAS,
    )
    assert linha(bp.calcular(e), bp.LINHA_FLEXAO_NA_ARGAMASSA).status == "NÃO OK"
    candidato = bp.base_mais_leve(e)
    assert candidato is not None and candidato.linha.d_b > bp.disposicoes(e).d_b
    assert linha(candidato, bp.LINHA_FLEXAO_NA_ARGAMASSA).status == candidato.status == "OK"


def test_t17_torcao_no_grupo_e_conversao_de_unidades():
    e = replace(PADRAO, n_sd_kN=0, vx_kN=0, vy_kN=0, mz_kNm=2)
    r = bp.calcular(e)
    g = r.geometria
    trechos = solda.contorno_do_pilar(g.d, g.b_f, g.t_w, g.t_f, mesas_por_dentro=True, alma=True)
    # Regra de Simpson exata para a integral quadrática do momento polar.
    j = 0.0
    for t in trechos:
        a, b = (t.x1, t.y1), (t.x2, t.y2)
        meio = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        j += (
            math.dist(a, b)
            * (math.hypot(*a) ** 2 + 4 * math.hypot(*meio) ** 2 + math.hypot(*b) ** 2)
            / 6
        )
    raio = max(math.hypot(t.x1, t.y1) for t in trechos)
    assert linha(
        r, "Solda do pilar na placa: filete no ponto mais solicitado"
    ).solicitante == pytest.approx(2e6 * raio / j / 1000)


def test_t18_eixos_e_propriedades_do_u_e_do_i():
    for nome in (PADRAO.perfil, bp.perfis_u()[0]):
        g = bp.geometria(replace(PADRAO, perfil=nome))
        t = solda.contorno_do_pilar(
            g.d,
            g.b_f,
            g.t_w,
            g.t_f,
            mesas_por_dentro=False,
            alma=True,
            y_dorso=g.y_dorso if g.e_u else None,
        )
        yc = solda.propriedades(t).y_c
        assert bool(abs(yc) > 1e-8) == g.e_u


def test_t19_rotacao_de_90_graus_no_equilibrio_elastico():
    g = bp.geometria(PADRAO)
    rot = replace(g, lx=g.ly, ly=g.lx, posicoes=tuple((-y, x) for x, y in g.posicoes))
    a = bp.distribuicao_elastica(g, 75000, 23e6, -12e6, 25, 300)
    b = bp.distribuicao_elastica(rot, 75000, 12e6, 23e6, 25, 300)
    assert a.equilibrio and b.equilibrio
    assert a.forcas == pytest.approx(b.forcas, abs=0.01)
    assert a.sigma_max == pytest.approx(b.sigma_max, abs=1e-5)


def test_t20_pryout_por_aderencia_contra_exemplo_publicado():
    # Hilti PROFIS 3.0.84, Waterfowl 2B03, pp. 7 e 10, 10/03/2023.
    # Dados publicados em psi/in/lbf. Tolerância 0,2 % pelos valores arredondados e
    # pelas constantes métricas da ACI. A geometria é a do grupo ensaiado no cálculo.
    inch, psi, lbf = 25.4, 0.0068947573, 4.4482216
    e = replace(
        PADRAO,
        ancoragem=bp.ANCORAGEM_QUIMICO,
        cortante=bp.CORTANTE_ARRUELAS,
        h_ef_mm=3.894 * inch,
        tau_cr_MPa=1387 * psi,
        tau_uncr_MPa=2533 * psi,
        fck_MPa=5000 * psi,
        bloco_x_mm=57.318 * inch,
        bloco_y_mm=57.318 * inch,
    )
    g = replace(
        bp.geometria(e), posicoes=tuple((x * inch, y * inch) for x in (-3, 3) for y in (-3, 3))
    )
    tab = replace(bp.disposicoes(e), d_b=0.75 * inch)
    assert bp.aderencia(e, g, tab, (1, 1, 1, 1))[0] / lbf == pytest.approx(12724, rel=0.002)
    assert bp.arrancamento_por_alavanca(e, g, tab, 12728 * lbf)[1] / lbf == pytest.approx(
        28497, rel=0.002
    )
    direto = replace(e, cortante=bp.CORTANTE_DIRETOS)
    dois = bp.arrancamento_por_alavanca(direto, g, tab, 12728 * lbf)
    assert dois[1] < 28497 * lbf and "2 de 4" in dois[2]


def test_aderencia_sustentada_e_categoria_por_certificado():
    e = replace(
        PADRAO,
        ancoragem=bp.ANCORAGEM_QUIMICO,
        tau_cr_MPa=3,
        tau_uncr_MPa=7.6,
        categoria_aci=2,
        h_ef_mm=200,
        n_sustentada_kN=18,
        n_sd_kN=-10,
        v_sd_kN=0,
    )
    r = bp.calcular(e)
    esperado = 0.55 * 0.55 * 3 * math.pi * r.linha.d_b * 200 / 1000
    assert linha(r, "Tração sustentada da resina").resistente == pytest.approx(esperado)
    assert linha(r, "Tração sustentada da resina").status == "NÃO OK"
    assert linha(r, "Aderência da resina no grupo").solicitante == 10


def test_importacao_preserva_sinais_e_torcao_nos_dois_eixos_fortes():
    componentes = (("ELU", 1, 3, -4, -5, 6, -7),)
    for eixo, esperado in ((modelo.em.EIXO_M2, (6, 5, 3, -4)), (modelo.em.EIXO_M1, (-5, 6, 4, 3))):
        dados = modelo.CombinacoesDoPilar("P1", PADRAO.perfil, componentes, eixo).entradas_placa()[
            0
        ]
        c = bp.caso_de_dicionario(dados)
        assert (c.m_sd_kNm, c.m_sd_y_kNm, c.vx_kN, c.vy_kN) == esperado
        assert c.mz_kNm == -7 and c.v_sd_kN == 5


def test_torcao_pura_no_aco_e_flexao_de_cada_chumbador():
    e = replace(PADRAO, vx_kN=0, vy_kN=0, mz_kNm=3, cortante=bp.CORTANTE_ARRUELAS)
    r = bp.calcular(e)
    raio = math.hypot(*r.geometria.posicoes[0])
    vi = 3e6 / (len(r.geometria.posicoes) * raio)
    assert linha(r, "Chumbador: aço à cortante (ACI 318-19)").solicitante == pytest.approx(
        vi / 1000
    )
    assert linha(r, bp.LINHA_FLEXAO_NA_ARGAMASSA).solicitante > 0
    assert linha(r, "Torção na transferência ao concreto").status == "ALERTA"


@pytest.mark.parametrize("lado", [-1, 1])
def test_faixa_do_u_contra_solucao_analitica_na_face_livre(lado):
    # Faixa em ℓy, estreita em ℓx e de pressão triangular crescente para a borda.
    # Para comprimento L e p(u)=p_max*u/L, o engaste recebe p_max*L²/3.
    g = bp.geometria(replace(PADRAO, perfil='U 6" x 12,20'))
    apoio = g.engaste_y[0 if lado < 0 else 1]
    ponta = lado * g.ly / 2
    l = abs(ponta - apoio)
    pmax = 13
    zona = ((-1, apoio), (1, apoio), (1, ponta), (-1, ponta))
    plano = (-pmax * lado * apoio / l, 0, pmax * lado / l)
    t, _ = bp.espessura_pela_zona(g, zona, 0, 250 / 1.1, plano=plano)
    assert t == pytest.approx(math.sqrt(4 * pmax * l * l / (3 * (250 / 1.1))))


@pytest.mark.parametrize("sinal", [-1, 1])
def test_t11_cortante_biaxial_verifica_interacao_da_borda(sinal):
    e = replace(
        PADRAO,
        bloco_x_mm=1600,
        bloco_y_mm=1800,
        bloco_z_mm=900,
        desloc_x_mm=250 * sinal,
        desloc_y_mm=180 * sinal,
        vx_kN=8 * sinal,
        vy_kN=6 * sinal,
        cortante=bp.CORTANTE_ARRUELAS,
    )
    r = bp.calcular(e)
    borda = linha(r, bp.LINHA_RUPTURA_DA_BORDA)
    assert "ψ_ec,V" in borda.formula
    assert "Interação elíptica" in borda.formula
    assert 0 < borda.aproveitamento < 1


def test_t11_excentricidade_da_fila_ativa_no_modelo_de_borda():
    e = replace(
        PADRAO,
        tipo=bp.TIPO_ROTULADA,
        n_chumbadores=2,
        vx_kN=8,
        vy_kN=0,
        bloco_x_mm=1200,
        bloco_y_mm=1000,
        bloco_z_mm=800,
        cortante=bp.CORTANTE_DIRETOS,
    )
    r = bp.calcular(e)
    borda = linha(r, bp.LINHA_RUPTURA_DA_BORDA)
    assert "e′_V = 50 mm" in borda.formula


def test_tabelas_do_memorial_pdf_separam_esforcos_componentes_residuos_e_resultados():
    casos = (
        bp.CasoDeCarga("C42", 2.9, 1.1, 0.7, 0.0, vx_kN=4, vy_kN=-2, mz_kNm=0.35),
        bp.CasoDeCarga("C43", -5.0, -0.4, 0.1, 3.0),
    )
    registro = bp.registro_base(bp.calcular(replace(PADRAO, casos=casos)))
    from core.memorial_verificacoes import tabelas_do_registro

    tabelas = tabelas_do_registro(registro)
    assert [t["legenda"] for t in tabelas] == [
        "Esforços aplicados por combinação",
        "Componentes e torção por combinação",
        "Resíduos do equilíbrio por combinação",
        "Verificação por combinação",
        "Espessura e tração por combinação",
    ]
    assert tabelas[1]["linhas"][0][1:] == ["4,00", "-2,00", "0,35"]
    assert len(tabelas[2]["linhas"][0]) == 4
    assert tabelas[4]["linhas"][0][1] != "—" and tabelas[4]["linhas"][0][2] != "—"
    resultado = bp.calcular(replace(PADRAO, casos=casos))
    assert bp.memorial_da_base(resultado, formato="pdf").startswith(b"%PDF")
