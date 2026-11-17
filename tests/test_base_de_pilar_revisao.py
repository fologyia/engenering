"""Revisão da placa de base (17/11/2026): os casos A a D conferidos à mão.

* A — tração (T3): a espessura pela tração usa o braço até a FACE da mesa (m = s_x/2 − d/2) e a
  largura aberta a 45° de cada chumbador, além da fórmula da 6.7 (vale a maior).
* B — compressão com e > ℓx/6 e momento nos dois eixos (C08): pelo bloco uniforme da 6.7 a base
  é C2 (equilíbrio sem tração, aceito pela norma), mas a espessura usa só a zona comprimida — não
  o balanço inteiro sob a pressão do canto; pela distribuição linear elástica (opção), os
  chumbadores tracionam pela compatibilidade da placa rígida.
* C — o caso completo (compressão elástica, tração sem contato, cone, arrancamento, aço, cortante
  pelos chumbadores e a interação 17.8).
* D — o cone com as quatro bordas perto: pela ACI 318-19 17.6.2.1.2 o h_ef útil fica em
  c_a,máx/1,5 e embutir mais não muda a resistência (sem esse limite, ela cairia com h_ef^−0,5).
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import base_de_pilar as bp

EL = bp.DISTRIBUICAO_ELASTICA
BASE = bp.EntradaBase(
    perfil="W 200 x 31,3",  # d = 210, b_f = 134
    chumbador='3/4"',
    a1_mm=45,
    a2_mm=160,
    t_placa_mm=16,
    lx_mm=390,  # chumbadores em x = ±150 (s_x/2 = 150)
    ly_mm=250,
    aco_placa="ASTM A36",
    v_sd_kN=0,
)
CASO_C = replace(
    BASE,
    lx_mm=415,
    ly_mm=270,
    bloco_x_mm=540,
    bloco_y_mm=400,
    fck_MPa=25,
    e_n_mm=50,
    h_ef_mm=250,
    verificar_concreto=True,
    cortante=bp.CORTANTE_ARRUELAS,
)


def _linha(r: bp.ResultadoBase, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def _nomes(r: bp.ResultadoBase) -> list[str]:
    return [v.nome for v in r.verificacoes]


# ------------------------------------------------------------------------------------- caso A
@pytest.mark.parametrize("distribuicao", [bp.DISTRIBUICAO_NBR, EL])
def test_caso_a_tracao_com_o_braco_ate_a_face_da_mesa(distribuicao):
    r = bp.calcular(replace(BASE, n_sd_kN=-5.1, m_sd_kNm=1.6, distribuicao=distribuicao))
    assert r.caso == "T3"
    placa = _linha(r, "Placa de base: espessura")
    assert "m = |x| − d/2 = 45,0 mm" in placa.formula  # 150 − 105: nunca a₁ + a₂ = 205
    assert "b_eff = 90,0 mm" in placa.formula  # 45 + 45 (borda e 45°), nunca d_b = 19
    # F_t ≈ 3,8 kN por chumbador: t = √(4·F_t·m/(b_eff·f_y/γ_a1)) ≈ 5,8 mm (antes 34,8 mm)
    f_t = r.f_t_sd
    assert f_t == pytest.approx(3.8e3, rel=0.03)
    assert r.t_p_min == pytest.approx(math.sqrt(4 * f_t * 45 / (90 * 250 / 1.1)), rel=1e-6)
    assert r.t_p_min < 16 and placa.status == "OK"


# ------------------------------------------------------------------------------------- caso B
def test_caso_b_bloco_uniforme_usa_so_a_zona_comprimida():
    r = bp.calcular(replace(BASE, n_sd_kN=10.5, m_sd_kNm=2.0, m_sd_y_kNm=0.7))
    assert r.caso == "C2"  # o equilíbrio da 6.7 sem tração existe; a tela explica a alternativa
    assert "Excentricidade fora do núcleo central (e > ℓx/6)" in _nomes(r)
    placa = _linha(r, "Placa de base: espessura")
    # antes: 95,25·√(2·σ/(f_y/γ_a1)) com o balanço inteiro sob a pressão do canto (26 a 29 mm)
    assert r.t_p_min < 16 and placa.status == "OK"
    assert "só na zona comprimida" in placa.formula


def test_caso_b_elastico_traciona_os_chumbadores():
    r = bp.calcular(replace(BASE, n_sd_kN=10.5, m_sd_kNm=2.0, m_sd_y_kNm=0.7, distribuicao=EL))
    assert r.caso == "C3"  # o lado que levanta puxa os chumbadores
    assert r.f_t_sd > 0 and sum(1 for f in r.forcas_nos_chumbadores if f > 0) == 2
    assert r.sigma_c_sd is not None and r.sigma_c_sd < 2.0  # nada de 10,8 MPa num canto de 10 cm²
    assert r.t_p_min < 16 and _linha(r, "Placa de base: espessura").status == "OK"


def test_c2_de_uma_direcao_com_faixa_estreita_usa_o_balanco_reduzido():
    # e = 190 mm, ℓ_c = ℓx − 2e = 10 mm < m = 95,25 mm: p = √(ℓ_c·(2m − ℓ_c)) (AISC DG1 3.3)
    r = bp.calcular(replace(BASE, n_sd_kN=10.5, m_sd_kNm=1.995))
    assert r.caso == "C2"
    l_c = 390 - 2 * 190
    sigma = 10.5e3 / (l_c * 250)
    p = math.sqrt(l_c * (2 * 95.25 - l_c))
    assert r.t_p_min == pytest.approx(p * math.sqrt(2 * sigma / (250 / 1.1)), rel=1e-3)


# ------------------------------------------------------------------------------------- caso C
def test_caso_c_compressao_elastica_placa_toda_comprimida():
    r = bp.calcular(replace(CASO_C, n_sd_kN=38, m_sd_kNm=1.6, v_sd_kN=4.8, distribuicao=EL))
    assert r.caso == "C2" and r.f_t_sd == 0  # e = 42,1 mm < ℓx/6 = 69,2 mm
    # σ_máx = N/A·(1 + 6e/ℓx) = 0,55 MPa
    assert r.sigma_c_sd == pytest.approx(38e3 / (415 * 270) * (1 + 6 * 1600 / 38 / 415), rel=1e-6)
    assert r.sigma_c_sd == pytest.approx(0.55, abs=0.005)
    # m = (415 − 0,95·210)/2 = 107,8 mm; com σ_máx em todo o balanço daria 7,5 mm, a pressão
    # linear integrada dá um pouco menos
    assert r.t_p_min == pytest.approx(7.5, rel=0.05)
    assert r.t_p_min <= 107.75 * math.sqrt(2 * r.sigma_c_sd / (250 / 1.1)) + 1e-9


def test_caso_c_compressao_atrito_passa():
    r = bp.calcular(
        replace(CASO_C, n_sd_kN=38, m_sd_kNm=1.6, v_sd_kN=4.8, cortante=bp.CORTANTE_ATRITO)
    )
    atrito = _linha(r, "Cortante: atrito")
    # V_Rd = μ·N/γ_a2 = 0,45 × 38/1,35 = 12,7 kN (a 6.7.2.2 divide por γ_a2) ≥ 4,8 kN
    assert atrito.resistente == pytest.approx(0.45 * 38 / 1.35, rel=1e-6)
    assert atrito.status == "OK"


def test_caso_c_tracao_completo():
    r = bp.calcular(replace(CASO_C, n_sd_kN=-18, m_sd_kNm=1.6, v_sd_kN=4.8))
    # e = 88,9 mm < s_x/2 = 162,5 mm: os 4 tracionados, sem contato (T2)
    assert r.caso == "T2"
    assert all(f > 0 for f in r.forcas_nos_chumbadores)
    assert r.f_t_sd / 1e3 == pytest.approx(6.96, abs=0.01)
    placa = _linha(r, "Placa de base: espessura")
    assert "m = |x| − d/2 = 57,5 mm" in placa.formula and "b_eff = 112,5 mm" in placa.formula
    assert r.t_p_min == pytest.approx(8.0, rel=0.05) and placa.status == "OK"
    cone = _linha(r, "Cone de concreto dos chumbadores")
    assert cone.resistente == pytest.approx(44.7, rel=0.05) and cone.status == "OK"
    assert _linha(r, "Arrancamento da cabeça").resistente == pytest.approx(82.3, rel=0.01)
    assert _linha(r, "Chumbador: aço à tração (ACI").resistente == pytest.approx(64.7, rel=0.01)
    assert not any(n.startswith("Arrancamento lateral") for n in _nomes(r))  # c > 0,4·h_ef
    assert "Borda do bloco corta o cone de concreto" in _nomes(r)
    # arruelas soldadas: 1,2 kN por chumbador; φ·V_sa = 0,65·0,6·A_se·f_uta·0,80 (argamassa)
    aco_v = _linha(r, "Chumbador: aço à cortante")
    assert aco_v.solicitante == pytest.approx(1.2)
    a_se = bp.ROSCAS['3/4"'].area_resistente
    assert aco_v.resistente == pytest.approx(0.65 * 0.6 * a_se * 400 * 0.80 / 1e3, rel=1e-9)
    assert _linha(r, "Chumbador: flexão na camada de argamassa").status == "OK"
    # 17.8: N/φN_n é o do modo que governa (o cone, 0,38), não só o do aço (0,11): a interação
    # é exigida e passa
    interacao = _linha(r, "Interação tração × cortante")
    assert interacao.solicitante is not None and interacao.solicitante <= 1.2
    assert interacao.status == "OK"


def test_caso_c_tracao_sem_dispositivo_nao_tem_atrito():
    r = bp.calcular(
        replace(CASO_C, n_sd_kN=-18, m_sd_kNm=1.6, v_sd_kN=4.8, cortante=bp.CORTANTE_ATRITO)
    )
    assert _linha(r, "Cortante: atrito").status == "NÃO OK"


def test_chumbadores_direto_no_furo_contam_dois_e_avisam():
    r = bp.calcular(
        replace(CASO_C, n_sd_kN=-18, m_sd_kNm=1.6, v_sd_kN=4.8, cortante=bp.CORTANTE_DIRETOS)
    )
    deslize = _linha(r, "Chumbadores direto no furo")
    assert deslize.status == "ALERTA"
    assert "(d_f − d_b)/2 = 7,0 mm" in deslize.formula  # furo 33 mm, chumbador 19 mm
    assert _linha(r, "Chumbador: aço à cortante").solicitante == pytest.approx(2.4)  # V/2
    assert LINHAS_OBRIGATORIAS <= set(_nomes(r))
    assert any("desliza" in a for a in r.avisos)
    assert r.v_rd == pytest.approx(2 * _linha(r, "Chumbador: aço à cortante").resistente * 1e3)


LINHAS_OBRIGATORIAS = {
    "Chumbador: aço à cortante (ACI 318-19)",
    "Chumbador: flexão na camada de argamassa",
    bp.LINHA_RUPTURA_DA_BORDA,
    bp.LINHA_ALAVANCA,
    bp.LINHA_INTERACAO,
}


def test_direto_no_furo_liga_a_ancoragem_aci():
    e = replace(BASE, cortante=bp.CORTANTE_DIRETOS)
    assert bp.ancoragem_verificada(e) and not bp.ancoragem_verificada(BASE)


# ------------------------------------------------------------------------------------- caso D
def _um_chumbador(h_ef: float):
    e = replace(BASE, bloco_x_mm=240, bloco_y_mm=240, verificar_concreto=True, h_ef_mm=h_ef)
    g = replace(bp.geometria(e), posicoes=((0.0, 0.0),))  # bordas c = 120 mm dos 4 lados
    return e, g, bp.disposicoes(e), (18.6e3,)


def test_caso_d_embutir_mais_nao_muda_o_cone_perto_das_bordas():
    longo = bp.cone_de_concreto(*_um_chumbador(250))
    curto = bp.cone_de_concreto(*_um_chumbador(80))
    assert longo is not None and curto is not None
    esperado = 0.70 * 10 * math.sqrt(25) * 80**1.5  # h_ef útil = c_a,máx/1,5 = 80 mm
    assert longo[1] == pytest.approx(esperado, rel=1e-9)
    assert curto[1] == pytest.approx(esperado, rel=1e-9)
    assert longo[1] >= 18.6e3  # 25,0 kN: passa (sem o limite da 17.6.2.1.2 daria 11,3 kN)
    assert "17.6.2.1.2" in longo[2]


def test_caso_d_aviso_de_cone_truncado():
    assert "embutir mais não aumenta" in bp.cone_truncado(*_um_chumbador(250))
    assert bp.cone_truncado(*_um_chumbador(80)) == ""  # 1,5·h_ef = 120 = c: cone inteiro


def test_armadura_de_ancoragem_dimensiona_a_area():
    r = bp.calcular(
        replace(CASO_C, n_sd_kN=-18, m_sd_kNm=1.6, v_sd_kN=0.0, armadura_de_ancoragem=True)
    )
    linha = _linha(r, "Cone de concreto: armadura de ancoragem")
    a_s = 6.9615e3 / (0.75 * 500)
    assert f"= {round(a_s)} mm²" in linha.formula and "ramos de Ø" in linha.formula


# ----------------------------------------------------------------- distribuição elástica
@pytest.mark.parametrize(
    ("axial", "mx", "my"),
    [
        (38e3, 1.6e6, 0.0),
        (10.5e3, 2.0e6, 0.7e6),
        (-5.1e3, 1.6e6, 0.0),
        (-18e3, 1.6e6, 0.0),
        (0.0, 5e6, 0.0),
        (300e3, 30e6, 10e6),
        (-40e3, 2e6, 3e6),
    ],
)
def test_distribuicao_elastica_equilibra_n_m_e_my(axial, mx, my):
    g = bp.geometria(BASE)
    a_se = bp.ROSCAS['3/4"'].area_resistente
    d = bp.distribuicao_elastica(g, axial, mx, my, 25.0, a_se)
    assert d.equilibrio
    w0, ax, ay = d.plano
    if d.zona:
        a, sx, sy, ixx, ixy, iyy = bp._momentos_do_poligono(list(d.zona))
        c, cx, cy = (
            w0 * a + ax * sx + ay * sy,
            w0 * sx + ax * ixx + ay * ixy,
            w0 * sy + ax * ixy + ay * iyy,
        )
    else:
        c = cx = cy = 0.0
    f = d.forcas
    pos = g.posicoes
    escala = max(abs(axial), 1e3)
    assert c - sum(f) == pytest.approx(axial, abs=1e-6 * escala)
    assert cx - sum(fi * x for fi, (x, _) in zip(f, pos, strict=True)) == pytest.approx(
        mx, abs=1e-6 * escala * 200
    )
    assert cy - sum(fi * y for fi, (_, y) in zip(f, pos, strict=True)) == pytest.approx(
        my, abs=1e-6 * escala * 200
    )
    # compatibilidade: cada chumbador tracionado com força proporcional ao levantamento
    for fi, (x, y) in zip(f, pos, strict=True):
        w = w0 + ax * x + ay * y
        assert fi == pytest.approx(max(-d.rigidez * w, 0.0), abs=1e-6 * escala)


def test_elastica_sem_momento_e_a_compressao_centrada():
    r = bp.calcular(replace(BASE, n_sd_kN=300, distribuicao=EL))
    assert r.caso == "C1" and r.sigma_c_sd == pytest.approx(300e3 / (390 * 250))
    nbr = bp.calcular(replace(BASE, n_sd_kN=300))
    assert r.t_p_min == pytest.approx(nbr.t_p_min, rel=0.02)  # mesma placa na compressão centrada


def test_elastica_pede_sigma_maximo_ate_o_resistente():
    r = bp.calcular(replace(BASE, n_sd_kN=900, m_sd_kNm=60, distribuicao=EL))
    pressao = _linha(r, "Concreto: pressão de contato")
    assert pressao.solicitante == pytest.approx(r.sigma_c_sd)
    assert pressao.status == ("OK" if r.sigma_c_sd <= r.sigma_c_rd else "NÃO OK")


# ------------------------------------------------------------------ montagem e mensagens
def test_rosca_acima_do_concreto_e_comprimento_da_barra():
    r = bp.calcular(replace(BASE, n_sd_kN=100))
    assert _linha(r, "Rosca acima do concreto").status == "OK"
    barra = dict(r.detalhamento)["Barra de cada chumbador"]
    assert barra.startswith("L = h_ef + h₂ + porca da ponta + 3 fios = 450 + 150 + ")
    grossa = bp.calcular(replace(BASE, n_sd_kN=100, t_placa_mm=100, e_n_mm=60))
    assert _linha(grossa, "Rosca acima do concreto").status == "NÃO OK"


def test_o_que_trava_separa_as_partes_da_base():
    r = bp.calcular(
        replace(CASO_C, n_sd_kN=-18, m_sd_kNm=1.6, v_sd_kN=4.8, cortante=bp.CORTANTE_ATRITO)
    )
    travas = bp.o_que_trava(r)
    assert travas[bp.TRAVA_CORTANTE] == ["Cortante: atrito na argamassa"]
    assert any(n.startswith("Bloco") for n in travas[bp.TRAVA_CONCRETO])  # nota e da Tabela 18
    assert bp.TRAVA_PLACA not in travas


def test_registro_tem_os_criterios_novos():
    r = bp.calcular(
        replace(
            CASO_C,
            n_sd_kN=-18,
            m_sd_kNm=1.6,
            v_sd_kN=4.8,
            cortante=bp.CORTANTE_DIRETOS,
            distribuicao=EL,
        )
    )
    reg = bp.registro_base(r)
    premissas = " ".join(reg["premissas"])
    assert "45°" in premissas and "face da mesa" in premissas
    assert "só 2 chumbadores" in premissas
    assert "Distribuição linear elástica" in reg["metodo"]
    assert reg["entradas"]["distribuicao_da_pressao"] == bp.DISTRIBUICOES[EL]


# ------------------------------------------------- rodada 2: flexão, espessura exibida, furo justo
def test_c16_flexao_na_argamassa_com_os_valores_de_referencia():
    # direto no furo, 2 engatados: V = 4,9 kN, F_t = 6,4 kN, e_n = 50, t_p = 16, A_se = 216, f_y = 248
    f = bp.flexao_na_argamassa(4.9e3, 2, 6.4e3, 50.0, 16.0, 216.0, 248.0, 1.1)
    assert f.n_engatados == 2 and f.braco == pytest.approx(33.0)
    assert f.momento / 1e3 == pytest.approx(80.9, rel=0.01)  # 2,45 kN × 33 mm
    assert f.sigma_b == pytest.approx(119, rel=0.05)
    assert f.sigma_t == pytest.approx(30, rel=0.05)
    assert f.sigma == pytest.approx(149, rel=0.05)
    assert f.sigma / f.limite == pytest.approx(0.66, rel=0.05)
    texto = f.texto()
    for parte in ("n_engatados = 2", "b = e_n/2 + t_p/2 = 33,0 mm", "M = V_i·b", "W = π·d_s³/32",
                  "σ_b = M/(1,5·W)", "σ_t = F_t/A_se", "f_y/γ_a1 = 248/1,10"):  # fmt: skip
        assert parte in texto, parte


def test_c16_na_base_a_flexao_fica_em_66_por_cento():
    e = replace(
        CASO_C,
        n_sd_kN=-6.3,
        m_sd_kNm=3.15,
        v_sd_kN=4.9,
        cortante=bp.CORTANTE_DIRETOS,
        aco_chumbador="ASTM F1554 Gr 36",
    )
    r = bp.calcular(e)
    flexao = _linha(r, bp.LINHA_FLEXAO_NA_ARGAMASSA)
    # antes 93 % (W elástico na rosca, sem a reserva plástica); agora ≈ 66 %
    assert flexao.aproveitamento == pytest.approx(0.66, rel=0.05)
    assert "n_engatados = 2" in flexao.formula


def test_placa_que_reprova_por_pouco_mostra_a_diferenca_e_a_chapa_seguinte():
    from core.verificacao import Verificacao, casas_coerentes, percentual_coerente

    justa = Verificacao("Placa de base: espessura t_p ≥ t_p,min", 16.004, 16.0, "mm", "")
    assert justa.status == "NÃO OK"
    casas = casas_coerentes(justa)
    assert f"{justa.solicitante:.{casas}f}" != f"{justa.resistente:.{casas}f}"
    assert percentual_coerente(justa) != "100 %"
    passa = Verificacao("x", 15.996, 16.0, "mm", "")
    assert passa.status == "OK" and casas_coerentes(passa) == 2
    # no cálculo: a sugestão da chapa comercial seguinte
    r = bp.calcular(replace(BASE, n_sd_kN=900, t_placa_mm=16))
    placa = _linha(r, "Placa de base: espessura")
    assert placa.status == "NÃO OK" and "a chapa comercial seguinte é" in placa.formula
    assert f"t_p,min = {r.t_p_min:.2f}".replace(".", ",") in bp.destaque(r)


def test_furo_justo_avisa_e_vai_para_o_memorial():
    e = replace(BASE, por_formula=True, d_f_mm=20.0, n_sd_kN=100)
    r = bp.calcular(e)
    linha = _linha(r, "Furo justo na placa")
    assert (
        "gabarito de montagem" in linha.formula
        and "furo padrão + arruelas soldadas" in linha.formula
    )
    assert any("Furo justo" in a for a in r.avisos)
    assert any("Furo justo" in p for p in bp.registro_base(r)["premissas"])
    padrao = bp.calcular(replace(e, d_f_mm=0.0))
    assert not any(v.nome == "Furo justo na placa" for v in padrao.verificacoes)
