"""Contas dos casos de máquinas conferidas à mão ou por um segundo caminho independente.

Quando o valor vem de um livro ou de uma norma, o teste diz de onde. As tabelas da NBR 8400 e da
NBR 6158 foram lidas no PDF da norma.
"""

from __future__ import annotations

import math

import pytest

from core import elementos_catalogo as cat
from core import elementos_eixos as ei
from core import elementos_icamento as ic
from core import elementos_mancais as ma
from core import elementos_molas_atrito as mo
from core import elementos_rotativos as ro
from core import elementos_secoes as se
from core import elementos_transmissao as tr
from core import memorial_verificacoes as mv
from core.elementos_base import Ponto, Resultado, calcular_caso


def rodar(caso_id: str, **valores) -> Resultado:
    return calcular_caso(cat.CASOS[caso_id], valores)


def metrica(resultado: Resultado, rotulo: str) -> float:
    for item in resultado.metricas:
        if item.rotulo == rotulo:
            return float(item.valor)
    raise KeyError(rotulo)


def linha(resultado: Resultado, nome: str):
    for item in resultado.verificacoes:
        if item.nome == nome:
            return item
    raise KeyError(nome)


# ---------------------------------------------------------------------------
# Transmissão
# ---------------------------------------------------------------------------


def test_torque_pela_potencia():
    assert tr.potencia_em_torque(15.0, 1750.0) == pytest.approx(9549.3 * 15.0 / 1750.0, rel=1e-4)


def test_redutor_multiplica_o_torque_pelo_rendimento():
    r = rodar(
        "acionamento", potencia_kW=10.0, rotacao_rpm=1000.0, i1=4.0, eta1=0.95, i2=1.0, eta2=1.0
    )
    assert metrica(r, "Torque na saída") == pytest.approx(95.49 * 4.0 * 0.95, rel=1e-3)
    assert metrica(r, "Rotação na saída") == pytest.approx(250.0)


def test_tempo_de_partida_a_mao():
    r = rodar(
        "acionamento",
        potencia_kW=10.0,
        rotacao_rpm=1000.0,
        i1=2.0,
        eta1=1.0,
        i2=1.0,
        eta2=1.0,
        fator_partida=2.0,
        inercia_motor=0.5,
        inercia_carga=4.0,
        torque_resistente=0.0,
    )
    # J no motor = 0,5 + 4/4 = 1,5; T = 2·95,49; ω = 104,72 rad/s
    assert metrica(r, "Tempo de partida") == pytest.approx(1.5 * 104.72 / 190.99, rel=1e-3)


def test_lewis_e_tabela_14_2():
    assert tr.fator_lewis(20) == pytest.approx(0.322)
    assert tr.fator_lewis(25) == pytest.approx((0.337 + 0.346) / 2.0)
    assert tr.fator_lewis(1000) == pytest.approx(0.485)


def test_fatores_dinamicos_de_barth():
    assert tr.fator_dinamico("Fresado", 6.1) == pytest.approx(2.0)
    assert tr.fator_dinamico("Caracol (hob)", 4.0) == pytest.approx((3.56 + 2.0) / 3.56)
    assert tr.fator_dinamico("Fundido", 3.05) == pytest.approx(2.0)


def test_coeficiente_elastico_do_aco_e_191():
    assert tr.coeficiente_elastico(207.0, 0.30) == pytest.approx(191.0, abs=1.0)


def test_forcas_da_engrenagem_helicoidal():
    r = rodar(
        "engrenagem",
        potencia_kW=10.0,
        rotacao_rpm=1000.0,
        modulo_mm=4.0,
        z1=25,
        z2=75,
        angulo_pressao=20.0,
        angulo_helice=20.0,
    )
    d1 = 4.0 * 25 / math.cos(math.radians(20.0))
    ft = 2.0 * 95_493.0 / d1
    assert metrica(r, "Primitivo do pinhão d₁") == pytest.approx(d1)
    assert metrica(r, "Força tangencial F_t") == pytest.approx(ft / 1000.0, rel=1e-3)
    assert metrica(r, "Força axial F_a") == pytest.approx(
        metrica(r, "Força tangencial F_t") * math.tan(math.radians(20.0))
    )


def test_sigma_de_lewis_a_mao():
    r = rodar(
        "engrenagem",
        potencia_kW=10.0,
        rotacao_rpm=1000.0,
        modulo_mm=4.0,
        z1=20,
        z2=60,
        largura_mm=40.0,
        ko=1.0,
        km=1.0,
        processo="Fresado",
    )
    d = 80.0
    v = math.pi * d * 1000.0 / 60_000.0
    ft = 10_000.0 / v
    esperado = (6.1 + v) / 6.1 * ft / (40.0 * 4.0 * 0.322)
    assert linha(r, "Flexão no dente do pinhão (Lewis)").solicitante == pytest.approx(esperado)


def test_pinhao_pequeno_avisa_do_adelgacamento():
    r = rodar("engrenagem", z1=14, z2=60)
    assert linha(r, "Dentes do pinhão sem adelgaçamento").status == "ALERTA"
    assert (
        linha(rodar("engrenagem", z1=18, z2=60), "Dentes do pinhão sem adelgaçamento").status
        == "OK"
    )


def test_conica_a_axial_de_um_eixo_e_a_radial_do_outro():
    r = rodar("engrenagem_conica", z1=20, z2=20)  # γ = 45°
    assert metrica(r, "Força radial no pinhão") == pytest.approx(
        metrica(r, "Força axial no pinhão")
    )


def test_sem_fim_torque_na_coroa_vem_do_rendimento():
    r = rodar("sem_fim", torque_Nm=50.0, entradas=2, z2=40, atrito_automatico=False, atrito=0.05)
    assert metrica(r, "Torque na coroa") == pytest.approx(
        50.0 * 20.0 * metrica(r, "Rendimento") / 100.0, rel=1e-6
    )


def test_sem_fim_de_avanco_baixo_e_autotravante():
    r = rodar(
        "sem_fim", modulo_mm=3.0, entradas=1, d_sem_fim_mm=60.0, atrito_automatico=False, atrito=0.1
    )
    assert "autotravante" in r.resumo and "não é" not in r.resumo
    assert any("freio" in texto for texto in r.alertas)


def test_atrito_do_sem_fim_nas_tres_faixas():
    assert tr.atrito_sem_fim(0.0) == pytest.approx(0.15)
    assert tr.atrito_sem_fim(1.0) < tr.atrito_sem_fim(0.1) < 0.15


def test_geometria_da_correia():
    menor, maior, comprimento = tr.geometria_da_correia(100.0, 100.0, 500.0)
    assert menor == pytest.approx(math.pi)
    assert maior == pytest.approx(math.pi)
    assert comprimento == pytest.approx(1000.0 + math.pi * 100.0)
    menor, maior, _ = tr.geometria_da_correia(100.0, 300.0, 400.0)
    assert menor == pytest.approx(math.pi - 2.0 * math.asin(0.25))
    with pytest.raises(ValueError, match="curto"):
        tr.geometria_da_correia(100.0, 900.0, 300.0)


def test_correia_plana_pela_equacao_de_euler():
    r = rodar(
        "correia",
        tipo="Plana",
        potencia_kW=10.0,
        rotacao_rpm=1000.0,
        fator_servico=1.0,
        d_mm=200.0,
        D_mm=200.0,
        C_mm=600.0,
        atrito=0.3,
        massa_kg_m=0.0,
    )
    f1 = metrica(r, "Ramo tenso F₁")
    f2 = metrica(r, "Ramo frouxo F₂")
    assert f1 / f2 == pytest.approx(math.exp(0.3 * math.pi))
    assert f1 - f2 == pytest.approx(metrica(r, "Força útil F_t"))
    # Com polias iguais os dois ramos ficam paralelos: o eixo recebe a soma.
    assert metrica(r, "Carga no eixo") == pytest.approx(f1 + f2)


def test_correia_em_v_aperta_mais_que_a_plana():
    plana = rodar("correia", tipo="Plana")
    em_v = rodar("correia", tipo="Em V")
    assert metrica(em_v, "Pré-tensão mínima") < metrica(plana, "Pré-tensão mínima")


def test_corrente_primitivo_e_elos():
    assert 25.4 / math.sin(math.pi / 19) == pytest.approx(154.32, abs=0.01)
    r = rodar("corrente", passo_mm=25.4, z1=19, z2=57, C_mm=1016.0, massa_kg_m=0.0)
    assert metrica(r, "Número de elos") % 2 == 0
    elos, par = tr.elos_da_corrente(25.4, 19, 57, 1016.0)
    assert elos == pytest.approx(2 * 40 + 38 + 38**2 * 25.4 / (4 * math.pi**2 * 1016.0))
    assert par >= elos


def test_flange_divide_o_torque_entre_os_parafusos():
    r = rodar(
        "acoplamento",
        torque_Nm=1000.0,
        fator_servico=1.0,
        parafusos=4,
        circulo_mm=200.0,
        d_parafuso_mm=20.0,
    )
    assert metrica(r, "Força por parafuso") == pytest.approx(2.5)
    assert metrica(r, "Tensão no parafuso") == pytest.approx(2500.0 / (math.pi * 100.0))


# ---------------------------------------------------------------------------
# Eixos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("carga", "D_d", "r_d", "esperado", "folga"),
    [
        # Shigley, Tabela 7-1: primeira estimativa do ressalto.
        ("flexao", 1.5, 0.10, 1.7, 0.05),
        ("flexao", 1.5, 0.02, 2.7, 0.15),
        ("axial", 1.5, 0.10, 1.9, 0.05),
        ("axial", 1.5, 0.02, 3.0, 0.05),
        ("torcao", 1.33, 0.10, 1.5, 0.08),
        ("torcao", 1.33, 0.02, 2.2, 0.12),
    ],
)
def test_kt_de_ressalto_bate_com_a_tabela_7_1(carga, D_d, r_d, esperado, folga):
    assert ei.kt_ressalto(D_d * 100.0, 100.0, r_d * 100.0, carga) == pytest.approx(
        esperado, abs=folga
    )


def test_kt_cresce_com_o_raio_menor_e_com_o_degrau_maior():
    assert ei.kt_ressalto(150, 100, 1, "flexao") > ei.kt_ressalto(150, 100, 5, "flexao")
    assert ei.kt_ressalto(200, 100, 5, "flexao") > ei.kt_ressalto(110, 100, 5, "flexao")


def test_neuber_bate_com_os_valores_de_shigley():
    assert ei.raiz_neuber(689.5, "flexao") == pytest.approx(0.062, abs=0.001)
    assert ei.raiz_neuber(689.5, "torcao") == pytest.approx(0.047, abs=0.001)


def test_exemplo_de_eixo_de_shigley():
    """Shigley, exemplo 7-1: d = 28, D = 42, r = 2,8, M = 142,4, T = 124,3, S_ut = 735."""
    r = rodar(
        "eixo_secao",
        d_mm=28.0,
        D_mm=42.0,
        r_mm=2.8,
        ma_Nm=142.4,
        mm_Nm=0.0,
        ta_Nm=0.0,
        tm_Nm=124.3,
        sut_MPa=735.0,
        sy_MPa=574.0,
        confiabilidade="99 %",
    )
    assert metrica(r, "Limite de fadiga S_e") == pytest.approx(205.0, abs=1.5)
    n = metrica(r, "Fadiga, DE-Goodman")
    assert n == pytest.approx(1.64, abs=0.03)
    assert metrica(r, "Escoamento") == pytest.approx(4.55, abs=0.15)


def test_goodman_a_mao_sem_entalhe():
    r = rodar(
        "eixo_secao",
        d_mm=40.0,
        entalhe=ei.ENTALHE_LISO,
        ma_Nm=300.0,
        mm_Nm=0.0,
        ta_Nm=0.0,
        tm_Nm=0.0,
        sut_MPa=700.0,
        sy_MPa=600.0,
    )
    sigma = 32.0 * 300_000.0 / (math.pi * 40.0**3)
    assert metrica(r, "σ'a") == pytest.approx(sigma)
    assert metrica(r, "Fadiga, DE-Goodman") == pytest.approx(
        metrica(r, "Limite de fadiga S_e") / sigma
    )


def test_diametro_minimo_devolve_o_fator_pedido():
    r = rodar("eixo_secao")
    d_min = metrica(r, "Diâmetro mínimo")
    novo = rodar("eixo_secao", d_mm=d_min, D_mm=d_min * 1.4, r_mm=d_min * 0.06)
    assert metrica(novo, "Fadiga, DE-Goodman") == pytest.approx(1.5, abs=0.25)


def test_canal_de_anel_nao_credita_a_sensibilidade():
    r = rodar("eixo_secao", entalhe=ei.ENTALHE_ANEL)
    assert any(m.rotulo == "K_t / K_f" and m.valor == "5.00 / 5.00" for m in r.metricas)


def test_a_seta_de_fadiga_leva_a_tensao_nominal():
    r = rodar("eixo_secao", d_mm=40.0, ma_Nm=300.0, ta_Nm=0.0, tm_Nm=0.0, mm_Nm=0.0, axial_kN=0.0)
    assert r.fadiga[0] == pytest.approx(32.0 * 300_000.0 / (math.pi * 40.0**3))
    assert r.fadiga[1] == pytest.approx(0.0)


def _eixo(**valores) -> Resultado:
    base = {
        "f1_ativa": True,
        "f2_ativa": False,
        "f1_fz_kN": 0.0,
        "f1_torque_Nm": 0.0,
        "f1_massa_kg": 0.0,
        "xa_mm": 0.0,
        "mancal_a": "Esferas autocompensadoras",
        "mancal_b": "Esferas autocompensadoras",
        "rotacao_rpm": 0.0,
    }
    return rodar("eixo_transmissao", **{**base, **valores})


def test_viga_biapoiada_com_carga_no_meio():
    r = _eixo(xb_mm=1000.0, f1_x_mm=500.0, f1_fy_kN=10.0, d_mm=50.0, e_GPa=200.0)
    assert metrica(r, "Reação radial em A") == pytest.approx(5.0)
    assert metrica(r, "Reação radial em B") == pytest.approx(5.0)
    assert metrica(r, "Momento máximo") == pytest.approx(2500.0)
    i = math.pi * 50.0**4 / 64.0
    assert metrica(r, "Flecha máxima") == pytest.approx(
        10_000.0 * 1000.0**3 / (48.0 * 200_000.0 * i), rel=1e-3
    )
    assert linha(r, "Inclinação no mancal A").solicitante == pytest.approx(
        10_000.0 * 1000.0**2 / (16.0 * 200_000.0 * i), rel=2e-3
    )


def test_eixo_em_balanco_alem_do_mancal():
    a = 200.0
    vao = 800.0
    r = _eixo(xb_mm=vao, f1_x_mm=vao + a, f1_fy_kN=5.0, d_mm=60.0, e_GPa=200.0)
    assert metrica(r, "Reação radial em A") == pytest.approx(5.0 * a / vao)
    assert metrica(r, "Reação radial em B") == pytest.approx(5.0 * (vao + a) / vao)
    i = math.pi * 60.0**4 / 64.0
    assert metrica(r, "Flecha máxima") == pytest.approx(
        5000.0 * a**2 * (vao + a) / (3.0 * 200_000.0 * i), rel=1e-3
    )


def test_cargas_em_dois_planos_somam_como_vetor():
    r = _eixo(xb_mm=1000.0, f1_x_mm=500.0, f1_fy_kN=3.0, f1_fz_kN=4.0, d_mm=50.0)
    assert metrica(r, "Reação radial em A") == pytest.approx(2.5)
    assert metrica(r, "Momento máximo") == pytest.approx(1250.0)


def test_forca_axial_no_raio_muda_as_reacoes():
    r = _eixo(xb_mm=1000.0, f1_x_mm=500.0, f1_fy_kN=0.0, f1_fx_kN=10.0, f1_raio_mm=100.0, d_mm=50.0)
    # Binário de 1 kN·m em 1 m: reações de ±1 kN.
    assert metrica(r, "Reação radial em A") == pytest.approx(1.0)
    assert metrica(r, "Reação radial em B") == pytest.approx(1.0)
    assert metrica(r, "Reação axial") == pytest.approx(10.0)


def test_rotacao_critica_de_rayleigh_contra_a_formula_exata():
    d = 50.0
    vao = 2000.0
    r = _eixo(
        xb_mm=vao,
        f1_x_mm=1000.0,
        f1_fy_kN=0.0,
        d_mm=d,
        e_GPa=205.0,
        densidade_kg_m3=7850.0,
    )
    area = math.pi * d**2 / 4.0
    i = math.pi * d**4 / 64.0
    # ω₁ = (π/L)²·√(EI/ρA), em unidades de N, mm e t/mm³.
    omega = (math.pi / vao) ** 2 * math.sqrt(205_000.0 * i / (7.85e-9 * area))
    assert metrica(r, "Rotação crítica") == pytest.approx(omega * 60.0 / (2.0 * math.pi), rel=0.01)


def test_sinal_do_normal_entre_a_carga_e_o_mancal_fixo():
    # Força para a direita em x = 300 e mancal axial em B (x = 1000): trecho comprimido.
    r = _eixo(
        xb_mm=1000.0,
        mancal_axial="B",
        f1_x_mm=300.0,
        f1_fy_kN=10.0,
        f1_fx_kN=20.0,
        f1_raio_mm=0.0,
    )
    destino = r.envios[0].valores
    assert destino["axial_kN"] == pytest.approx(-20.0)
    # Com o mancal axial em A, à esquerda da carga, a mesma força traciona o trecho até ela? Não:
    # a seção crítica fica na carga, e dali para a direita não passa força axial nenhuma.
    r = _eixo(
        xa_mm=100.0,
        xb_mm=1000.0,
        mancal_axial="A",
        f1_x_mm=300.0,
        f1_fy_kN=10.0,
        f1_fx_kN=20.0,
        f1_raio_mm=0.0,
    )
    assert r.envios[0].valores["axial_kN"] == pytest.approx(0.0)


def test_envio_da_engrenagem_fecha_o_torque_no_eixo():
    envio = rodar("engrenagem").envios[0]
    assert envio.valores["f2_torque_Nm"] == pytest.approx(-envio.valores["f1_torque_Nm"])
    r = rodar("eixo_transmissao", **envio.valores)
    assert not any("não zero" in texto for texto in r.alertas)


def test_torque_que_nao_fecha_gera_aviso():
    r = _eixo(xb_mm=1000.0, f1_x_mm=500.0, f1_fy_kN=1.0, f1_torque_Nm=100.0)
    assert any("não zero" in texto for texto in r.alertas)


def test_chaveta_din_6885():
    assert ei.chaveta_din(50.0) == (14.0, 9.0, 5.5, 3.8)
    assert ei.chaveta_din(30.0) == (8.0, 7.0, 4.0, 3.3)
    assert ei.chaveta_din(30.1) == (10.0, 8.0, 5.0, 3.3)
    with pytest.raises(ValueError, match="DIN 6885"):
        ei.chaveta_din(600.0)


def test_chaveta_a_mao():
    r = rodar(
        "chaveta",
        d_mm=50.0,
        torque_Nm=500.0,
        fator_servico=1.0,
        comprimento_mm=64.0,
        pontas="Arredondadas",
    )
    # F = 20 kN; L útil = 50; b = 14; t₁ = 5,5; h − t₁ = 3,5
    assert metrica(r, "Força na chaveta") == pytest.approx(20.0)
    assert metrica(r, "Cisalhamento τ") == pytest.approx(20_000.0 / (14.0 * 50.0))
    assert metrica(r, "Esmagamento no eixo") == pytest.approx(20_000.0 / (5.5 * 50.0))
    assert metrica(r, "Esmagamento no cubo") == pytest.approx(20_000.0 / (3.5 * 50.0))


def test_duas_chavetas_valem_uma_e_meia():
    uma = rodar("chaveta", quantidade=1)
    duas = rodar("chaveta", quantidade=2)
    assert metrica(uma, "Cisalhamento τ") == pytest.approx(1.5 * metrica(duas, "Cisalhamento τ"))


@pytest.mark.parametrize(
    ("d", "ajuste", "minima", "maxima"),
    [
        (80.0, "H7/s6 (forte)", 29.0, 78.0),  # ei 59, IT6 19, IT7 30
        (50.0, "H7/p6 (leve, com prensa)", 1.0, 42.0),  # ei 26, IT6 16, IT7 25
        (40.0, "H7/u6 (muito forte, a quente)", 35.0, 76.0),  # ei 60, IT6 16, IT7 25
        (120.0, "H7/r6 (médio)", 19.0, 76.0),  # ei 54, IT6 22, IT7 35
        (200.0, "H7/s6 (forte)", 76.0, 151.0),  # ei 122, IT6 29, IT7 46
    ],
)
def test_interferencia_pela_nbr_6158(d, ajuste, minima, maxima):
    assert ei.interferencia_do_ajuste(d, ajuste) == (minima, maxima)


def test_pressao_de_ajuste_no_caso_classico():
    # Eixo maciço e cubo do mesmo material: p = E·δ·(D² − d²)/(2·d·D²).
    d, D = 80.0, 140.0
    delta = 0.05
    e = 205_000.0
    p = ei.pressao_de_ajuste(delta, d, 0.0, D, e, 0.3, e, 0.3)
    assert p == pytest.approx(e * delta * (D**2 - d**2) / (2.0 * d * D**2))


def test_ajuste_torque_por_atrito_a_mao():
    r = rodar(
        "ajuste_prensado",
        ajuste=ei.AJUSTE_MANUAL,
        delta_min_um=60.0,
        delta_max_um=60.0,
        rz_eixo_um=0.0,
        rz_cubo_um=0.0,
        d_mm=80.0,
        L_mm=80.0,
        D_cubo_mm=140.0,
        atrito=0.12,
    )
    p = metrica(r, "Pressão mínima")
    assert metrica(r, "Torque por atrito") == pytest.approx(
        math.pi * 0.12 * p * 80.0**2 * 80.0 / 2.0 / 1000.0
    )


def test_rugosidade_consome_a_interferencia():
    with pytest.raises(ValueError, match="rugosidade"):
        rodar("ajuste_prensado", d_mm=50.0, ajuste="H7/p6 (leve, com prensa)")


def test_kf_do_cubo_prensado_aparece_no_envio():
    envio = rodar("ajuste_prensado").envios[0]
    assert envio.valores["entalhe"] == ei.ENTALHE_PRENSADO


# ---------------------------------------------------------------------------
# Mancais e contato
# ---------------------------------------------------------------------------


def test_fatores_x_y_do_rolamento_rigido():
    assert ma.fatores_xy(0.0, 5000.0, 44_000.0) == (1.0, 0.0, 0.0)
    assert ma.fatores_xy(100.0, 5000.0, 44_000.0)[:2] == (1.0, 0.0)  # Fa/Fr abaixo de e
    x, y, e = ma.fatores_xy(0.28 * 10_000.0, 1000.0, 10_000.0)
    assert (x, y, e) == (0.56, pytest.approx(1.15), pytest.approx(0.38))


def test_vida_do_rolamento_a_mao():
    r = rodar(
        "rolamento",
        c_kN=30.0,
        fr_kN=3.0,
        fa_kN=0.0,
        rotacao_rpm=1000.0,
        fator_aplicacao=1.0,
        confiabilidade="90 %",
    )
    assert metrica(r, "Vida básica L₁₀h") == pytest.approx(1e3 * 1e6 / (60.0 * 1000.0))
    assert metrica(r, "Vida ajustada") == pytest.approx(metrica(r, "Vida básica L₁₀h"))


def test_rolo_usa_expoente_dez_tercos():
    r = rodar(
        "rolamento",
        tipo="Rolos, X e Y informados",
        x=1.0,
        y=0.0,
        c_kN=30.0,
        fr_kN=3.0,
        fa_kN=0.0,
        rotacao_rpm=1000.0,
        fator_aplicacao=1.0,
    )
    assert metrica(r, "Vida básica L₁₀h") == pytest.approx(10.0 ** (10.0 / 3.0) * 1e6 / 60_000.0)


def test_resumo_do_rolamento_em_portugues():
    r = rodar("rolamento", c_kN=62.0, fr_kN=5.0, fa_kN=1.0, vida_h=20_000.0)
    texto = mv.decimal_ptbr(r.resumo)
    assert "61 298 h" in texto and "20 000 h" in texto, texto
    assert "6,00 kN" in texto, texto


def test_confiabilidade_de_99_corta_a_vida_a_um_quarto():
    base = metrica(rodar("rolamento", confiabilidade="90 %"), "Vida ajustada")
    alta = metrica(rodar("rolamento", confiabilidade="99 %"), "Vida ajustada")
    assert alta == pytest.approx(0.25 * base)


def test_c_necessario_devolve_a_vida_pedida():
    r = rodar("rolamento", vida_h=30_000.0)
    novo = rodar("rolamento", vida_h=30_000.0, c_kN=metrica(r, "C necessário"))
    assert metrica(novo, "Vida ajustada") == pytest.approx(30_000.0, rel=1e-6)


def test_regimes_da_nbr_8400_no_rolamento():
    sm = rodar(
        "rolamento", regime=ma.REGIME_SM, estado="2", fa_kN=0.0, fator_aplicacao=1.0, fr_kN=10.0
    )
    assert metrica(sm, "Carga equivalente P") == pytest.approx(6.7)
    sr = rodar(
        "rolamento", regime=ma.REGIME_SR, fr_min_kN=3.0, fa_kN=0.0, fator_aplicacao=1.0, fr_kN=9.0
    )
    assert metrica(sr, "Carga equivalente P") == pytest.approx(7.0)
    classe = rodar("rolamento", criterio_vida="V4")
    assert linha(classe, "Vida do rolamento").solicitante == 25_000.0


def test_bucha_oscilante_a_mao():
    r = rodar(
        "bucha",
        forca_kN=20.0,
        d_mm=50.0,
        largura_mm=50.0,
        movimento="Oscilação",
        giro_graus=90.0,
        ciclos_min=60.0,
    )
    assert metrica(r, "Pressão p") == pytest.approx(8.0)
    assert metrica(r, "Velocidade V") == pytest.approx(2.0 * (math.pi / 2.0) * 0.025 * 1.0)


def test_pino_momento_do_eurocode():
    r = rodar(
        "pino_articulacao",
        forca_kN=100.0,
        fator_dinamico=1.0,
        d_mm=40.0,
        t_olhal_mm=40.0,
        t_garfo_mm=20.0,
        folga_mm=2.0,
    )
    momento = 100_000.0 / 8.0 * (40.0 + 8.0 + 40.0)
    assert metrica(r, "Momento no pino") == pytest.approx(momento / 1000.0)
    assert metrica(r, "Flexão σ") == pytest.approx(32.0 * momento / (math.pi * 40.0**3))
    assert metrica(r, "Esmagamento no olhal") == pytest.approx(100_000.0 / (40.0 * 40.0))
    assert metrica(r, "Esmagamento no garfo") == pytest.approx(100_000.0 / (2.0 * 40.0 * 20.0))


def test_hertz_em_linha_pela_formula_fechada():
    r = ma.contato_de_hertz(
        ma.GEOMETRIA_CILINDRO_PLANO, 100_000.0, 500.0, 0.0, 50.0, 205e3, 0.3, 205e3, 0.3
    )
    e_ef = 205e3 / (2.0 * (1.0 - 0.09))
    # p₀ = √(q·E*/(π·R)), outro caminho para o mesmo número.
    assert r["p0"] == pytest.approx(math.sqrt(2000.0 * e_ef / (math.pi * 250.0)))


def test_hertz_em_ponto_pela_formula_fechada():
    r = ma.contato_de_hertz(
        ma.GEOMETRIA_ESFERA_PLANO, 1000.0, 20.0, 0.0, 0.0, 205e3, 0.3, 205e3, 0.3
    )
    e_ef = 205e3 / (2.0 * (1.0 - 0.09))
    assert r["p0"] == pytest.approx(
        (6.0 * 1000.0 * e_ef**2 / (math.pi**3 * 10.0**2)) ** (1.0 / 3.0)
    )


def test_duas_esferas_iguais_equivalem_a_metade_do_raio():
    duas = ma.contato_de_hertz(
        ma.GEOMETRIA_ESFERAS, 1000.0, 20.0, 20.0, 0.0, 205e3, 0.3, 205e3, 0.3
    )
    uma = ma.contato_de_hertz(
        ma.GEOMETRIA_ESFERA_PLANO, 1000.0, 10.0, 0.0, 0.0, 205e3, 0.3, 205e3, 0.3
    )
    assert duas["p0"] == pytest.approx(uma["p0"])


# ---------------------------------------------------------------------------
# NBR 8400
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("classe", "estado", "grupo"),
    [
        ("V0,25", "1", "1Bm"),
        ("V2", "1", "1Am"),
        ("V5", "1", "4m"),
        ("V1", "2", "1Am"),
        ("V4", "2", "4m"),
        ("V5", "2", "5m"),
        ("V0,5", "3", "1Am"),
        ("V3", "3", "4m"),
        ("V5", "3", "5m"),
    ],
)
def test_tabela_23(classe, estado, grupo):
    assert ic.grupo_do_mecanismo(classe, estado) == grupo


def test_servico_perigoso_sobe_um_grupo_e_para_no_5m():
    assert ic.grupo_do_mecanismo("V2", "2", perigoso=True) == "3m"
    assert ic.grupo_do_mecanismo("V5", "3", perigoso=True) == "5m"


@pytest.mark.parametrize(
    ("tipo", "v", "psi"),
    [
        (ic.TIPO_PONTE, 0.1, 1.15),
        (ic.TIPO_PONTE, 0.5, 1.30),
        (ic.TIPO_PONTE, 1.5, 1.60),
        (ic.TIPO_LANCA, 0.3, 1.15),
        (ic.TIPO_LANCA, 0.8, 1.24),
        (ic.TIPO_LANCA, 2.0, 1.30),
    ],
)
def test_coeficiente_dinamico_da_tabela_5(tipo, v, psi):
    assert ic.coeficiente_dinamico(tipo, v) == pytest.approx(psi)


def test_coluna_das_polias_da_tabela_28_cresce_sem_quebra():
    """A norma imprime 18 no grupo 4m: o valor correto, 28, fica entre 25 e 31,5."""
    coluna = [ic.H1[g][1][1] for g in ic.GRUPOS_MECANISMO]
    assert coluna == sorted(coluna)
    assert ic.H1["4m"][1][1] == 28.0


def test_acoes_do_caso_i():
    r = rodar(
        "acoes_icamento",
        tipo=ic.TIPO_PONTE,
        velocidade_m_s=0.5,
        grupo_estrutura="5",
        peso_kN=10.0,
        carga_kN=100.0,
        horizontal_kN=5.0,
    )
    assert metrica(r, "Caso I com M_x") == pytest.approx(1.12 * (10.0 + 1.30 * 100.0 + 5.0))


def test_assentamento_com_sinal_trocado_avisa():
    r = rodar("acoes_icamento", velocidade_m_s=2.0, peso_kN=10.0, carga_kN=100.0)
    assert metrica(r, "Assentamento da carga") == pytest.approx(10.0 - 100.0 * 0.6 / 2.0)
    assert any("baixar" in texto for texto in r.alertas)


def test_rendimento_do_moitao():
    assert ic.rendimento_do_moitao(1, 0.98) == 1.0
    assert ic.rendimento_do_moitao(2, 0.98) == pytest.approx(0.99)
    assert ic.rendimento_do_moitao(4, 1.0) == 1.0


def test_cabo_a_mao():
    r = rodar(
        "cabo_tambor",
        classe="V3",
        estado="2",  # 3m: Q = 0,335; tambor 20 (6 x 36 normal); polia 22,4
        carga_kN=19.6,
        moitao_kN=0.4,
        ramais=1,
        eta_polia=1.0,
        tipo_cabo=ic.CABO_NORMAL,
        classe_cabo="6 x 36 AA",
        d_cabo_mm=16.0,
        polias=1,
        polias_inversao=0,
    )
    assert metrica(r, "Tração no cabo") == pytest.approx(20.0)
    d_min = 0.335 * math.sqrt(2000.0)
    assert metrica(r, "Cabo mínimo") == pytest.approx(d_min)
    assert metrica(r, "Tambor mínimo") == pytest.approx(20.0 * d_min)
    assert metrica(r, "Polia mínima") == pytest.approx(22.4 * d_min)  # W_T = 3: H₂ = 1


def test_carga_de_ruptura_bate_com_a_tabela_da_nbr_6327():
    # Tabela C.6, 6 x 19 AF, categoria 1770: d = 12,7 mm → 94,2 kN.
    assert ic.carga_de_ruptura_do_cabo("6 x 19 AF", "1770", 12.7) == pytest.approx(
        94_200.0, rel=0.002
    )
    # Mesma tabela, d = 14 mm → 114 kN.
    assert ic.carga_de_ruptura_do_cabo("6 x 19 AF", "1770", 14.0) == pytest.approx(
        114_000.0, rel=0.01
    )


def test_cabo_6x19_usa_a_coluna_do_nao_rotativo():
    r = rodar("cabo_tambor", classe="V3", estado="2", classe_cabo="6 x 19 AA", d_cabo_mm=16.0)
    d_min = metrica(r, "Cabo mínimo")
    assert metrica(r, "Tambor mínimo") == pytest.approx(22.4 * d_min)


def test_cabo_muito_maior_que_o_minimo_dimensiona_os_enrolamentos_por_ele():
    r = rodar("cabo_tambor", d_cabo_mm=40.0)
    assert any("25 %" in texto for texto in r.alertas)
    assert metrica(r, "Tambor mínimo") == pytest.approx(18.0 * 40.0)


def test_h2_da_tabela_29():
    assert [ic.h2_das_polias(w) for w in (5, 6, 9, 10)] == [1.0, 1.12, 1.12, 1.25]


def test_c1_bate_com_a_tabela_32():
    # D = 500 mm a 63 m/min: 40,1 rpm. Tabela 32: 0,97.
    assert ic.c1_da_rotacao(63_000.0 / (math.pi * 500.0)) == pytest.approx(0.97, abs=0.005)
    # D = 800 mm a 100 m/min: 39,8 rpm. Tabela 32: 0,97.
    assert ic.c1_da_rotacao(100_000.0 / (math.pi * 800.0)) == pytest.approx(0.97, abs=0.005)
    # D = 250 mm a 25 m/min: 31,8 rpm. Tabela 32: 1.
    assert ic.c1_da_rotacao(25_000.0 / (math.pi * 250.0)) == pytest.approx(1.0, abs=0.005)


def test_pressao_limite_da_tabela_30():
    assert ic.pressao_limite(450.0) is None
    assert ic.pressao_limite(550.0) == 0.50
    assert ic.pressao_limite(650.0) == 0.56
    assert ic.pressao_limite(750.0) == 0.65
    assert ic.pressao_limite(850.0) == 0.72


def test_roda_a_mao():
    r = rodar(
        "roda_ponte",
        classe="V2",
        estado="2",  # 2m: c₂ = 1
        f_max_kN=120.0,
        f_min_kN=30.0,
        d_mm=500.0,
        velocidade_m_min=63.0,
        sigma_r_MPa=750.0,
        boleto_mm=70.0,
        raio_mm=10.0,
        superficie="Plana",
    )
    # F_r = 90 kN = 9000 daN; b = 50; pressão = 9000/(50·500) = 0,36
    assert linha(r, "Pressão na roda, casos I e II").solicitante == pytest.approx(0.36)
    assert linha(r, "Pressão na roda, casos I e II").resistente == pytest.approx(
        0.65 * 0.97, abs=0.005
    )


def test_roda_de_material_fraco_reprova():
    r = rodar("roda_ponte", sigma_r_MPa=400.0)
    assert r.status == "NÃO OK"
    assert any("Tabela 30" in texto for texto in r.alertas)


def test_mecanismo_tensao_admissivel_e_tracao_pesando_mais():
    r = rodar(
        "mecanismo_nbr8400",
        classe="V3",
        estado="2",  # 3m: q = 1,25
        sigma_r_MPa=700.0,
        sigma_axial_MPa=40.0,
        sigma_flexao_MPa=60.0,
        tau_MPa=0.0,
        levantamento=False,
    )
    assert metrica(r, "σ_a, casos I e II") == pytest.approx(700.0 / (1.25 * 2.8))
    assert linha(r, "Ruptura, casos I e II").solicitante == pytest.approx(1.25 * 40.0 + 60.0)


def test_mecanismo_compressao_nao_tem_o_fator_de_125():
    r = rodar("mecanismo_nbr8400", sigma_axial_MPa=-40.0, sigma_flexao_MPa=60.0, tau_MPa=0.0)
    assert linha(r, "Ruptura, casos I e II").solicitante == pytest.approx(100.0)


def test_mecanismo_caso_iii_e_16_vezes_o_caso_i():
    r = rodar("mecanismo_nbr8400", sigma_axial_MPa=0.0, sigma_flexao_MPa=100.0, tau_MPa=0.0)
    assert linha(r, "Ruptura, caso III (1,6 × caso I)").solicitante == pytest.approx(160.0)


def test_ferro_fundido_sobe_q_e_fsr():
    r = rodar("mecanismo_nbr8400", classe="V1", estado="1", material="Ferro fundido cinzento")
    assert metrica(r, "q") == pytest.approx(1.25)
    assert metrica(r, "FS_r") == pytest.approx(3.5)


def test_fadiga_de_mecanismo_usa_delta_da_tabela_26():
    r = rodar(
        "mecanismo_nbr8400",
        classe="V4",
        estado="2",  # 4m: δ = 1,18
        sigma_max_fadiga_MPa=100.0,
        sigma_af_MPa=119.0,
    )
    assert linha(r, "Fadiga").solicitante == pytest.approx(118.0)


def test_gancho_de_shigley():
    """Shigley, exemplo 3-15, em polegadas: F = 5000, r_i = 2, h = 4, b = 0,75."""
    p = ic.propriedades_viga_curva(ic.SECAO_RETANGULAR, 2.0, 4.0, 0.75, 0.0, 0.0)
    assert p["rn"] == pytest.approx(3.641, abs=0.001)
    assert p["e"] == pytest.approx(0.359, abs=0.001)
    momento = 5000.0 * p["rc"]
    interna = ic.tensao_viga_curva(2.0, 5000.0, momento, p["area"], p["rn"], p["e"])
    externa = ic.tensao_viga_curva(6.0, 5000.0, momento, p["area"], p["rn"], p["e"])
    assert interna == pytest.approx(16_900.0, abs=30.0)
    assert externa == pytest.approx(-5_630.0, abs=30.0)


def test_viga_curva_de_raio_enorme_recai_na_viga_reta():
    p = ic.propriedades_viga_curva(ic.SECAO_RETANGULAR, 1e6, 100.0, 50.0, 0.0, 0.0)
    momento = 1e6
    externa = ic.tensao_viga_curva(p["ro"], 0.0, momento, p["area"], p["rn"], p["e"])
    interna = ic.tensao_viga_curva(1e6, 0.0, momento, p["area"], p["rn"], p["e"])
    reta = momento * 50.0 / (50.0 * 100.0**3 / 12.0)
    assert interna == pytest.approx(reta, rel=1e-3)
    assert externa == pytest.approx(-reta, rel=1e-3)


def test_secao_circular_e_trapezoidal_na_formula_de_area():
    circular = ic.propriedades_viga_curva(ic.SECAO_CIRCULAR, 50.0, 0.0, 0.0, 0.0, 40.0)
    assert circular["area"] == pytest.approx(math.pi * 400.0)
    assert 0 < circular["e"] < 10.0
    # Trapézio com as duas bases iguais é um retângulo.
    trapezio = ic.propriedades_viga_curva(ic.SECAO_TRAPEZOIDAL, 60.0, 80.0, 40.0, 40.0, 0.0)
    retangulo = ic.propriedades_viga_curva(ic.SECAO_RETANGULAR, 60.0, 80.0, 40.0, 0.0, 0.0)
    assert trapezio["rn"] == pytest.approx(retangulo["rn"])
    assert trapezio["rc"] == pytest.approx(retangulo["rc"])


def test_olhal_a_mao():
    r = rodar(
        "olhal",
        forca_kN=10.0,
        fator_dinamico=1.0,
        t_mm=20.0,
        w_mm=150.0,
        d_pino_mm=32.0,
        d_furo_mm=33.0,
        a_mm=90.0,
        fy_MPa=345.0,
        fu_MPa=450.0,
    )
    assert metrica(r, "Largura efetiva b_e") == pytest.approx(56.0)
    assert metrica(r, "Tração no furo R_n") == pytest.approx(450.0 * 2 * 20 * 56 / 1000.0)
    assert metrica(r, "Rasgamento R_n") == pytest.approx(
        0.6 * 450.0 * 2 * 20 * (90.0 + 16.0) / 1000.0
    )
    assert metrica(r, "Esmagamento R_n") == pytest.approx(1.8 * 345.0 * 20 * 32 / 1000.0)


def test_olhal_estreito_ou_curto_reprova_na_geometria():
    assert linha(rodar("olhal", w_mm=120.0), "Largura mínima no furo").status == "NÃO OK"
    assert linha(rodar("olhal", a_mm=50.0), "Distância à frente do furo").status == "NÃO OK"
    r = rodar("olhal", gira_sob_carga=True, d_furo_mm=35.0)
    assert linha(r, "Folga do furo com giro sob carga").status == "NÃO OK"


def test_olhal_o_fator_de_icamento_substitui_o_da_aisc():
    r = rodar("olhal", fs_minimo=4.0, forca_kN=10.0, fator_dinamico=1.0)
    item = linha(r, "Esmagamento do furo")
    assert item.resistente == pytest.approx(1.8 * 345.0 * 20.0 * 32.0 / 4.0)


def test_olhal_o_fator_de_icamento_vale_na_solda_e_na_base():
    r = rodar("olhal", fs_minimo=4.0, fexx_MPa=485.0, fy_MPa=345.0)
    assert linha(r, "Solda da base (2 filetes)").resistente == pytest.approx(0.6 * 485.0 / 4.0)
    assert linha(r, "Base do olhal").resistente == pytest.approx(345.0 / 4.0)


def test_olhal_carga_inclinada_flete_a_base():
    r = rodar("olhal", angulo_graus=30.0, forca_kN=20.0, fator_dinamico=1.0)
    assert any("fora do plano" in texto for texto in r.alertas)
    assert metrica(r, "Tensão na base") > metrica(
        rodar("olhal", forca_kN=20.0, fator_dinamico=1.0), "Tensão na base"
    )


# ---------------------------------------------------------------------------
# Molas, freios, fusos
# ---------------------------------------------------------------------------


def test_mola_rigidez_e_comprimentos():
    r = rodar("mola_compressao", d_mm=10.0, D_mm=60.0, ativas=8.0, L0_mm=150.0, f_max_N=2000.0)
    assert metrica(r, "Rigidez k") == pytest.approx(77_200.0 * 1e4 / (8.0 * 60.0**3 * 8.0))
    assert metrica(r, "Comprimento de bloco") == pytest.approx(100.0)  # esquadrada e esmerilhada
    assert metrica(r, "Passo") == pytest.approx((150.0 - 20.0) / 8.0)


def test_resistencia_do_fio_de_shigley():
    assert mo._sut_do_fio("ASTM A228 corda de piano", 1.0) == pytest.approx(2211.0)


def test_mola_longa_sem_guia_flamba():
    r = rodar("mola_compressao", apoio="Uma ponta livre")
    assert linha(r, "Flambagem da mola").status == "NÃO OK"


def test_fadiga_da_mola_por_zimmerli():
    r = rodar(
        "mola_compressao",
        ciclica=True,
        superficie=mo.SEM_JATEAMENTO,
        f_max_N=2000.0,
        f_min_N=2000.0,
    )
    jateada = rodar(
        "mola_compressao", ciclica=True, superficie=mo.JATEADA, f_max_N=2000.0, f_min_N=500.0
    )
    assert linha(jateada, "Fadiga da mola").resistente > 0
    assert linha(r, "Fadiga da mola").status == "OK"


def test_embreagem_desgaste_uniforme_a_mao():
    r = rodar("embreagem_disco", D_ext_mm=400.0, D_int_mm=240.0, pares=2, forca_kN=5.0, atrito=0.3)
    assert metrica(r, "Torque de atrito") == pytest.approx(2 * 0.3 * 5000.0 * 160.0 / 1000.0)
    assert metrica(r, "Pressão no forro") == pytest.approx(5000.0 / (2.0 * math.pi * 120.0 * 80.0))


def test_pressao_uniforme_da_mais_torque_que_desgaste_uniforme():
    desgaste = rodar("embreagem_disco", criterio=mo.DESGASTE_UNIFORME)
    pressao = rodar("embreagem_disco", criterio=mo.PRESSAO_UNIFORME)
    assert metrica(pressao, "Torque de atrito") > metrica(desgaste, "Torque de atrito")


def test_energia_da_frenagem_e_a_cinetica():
    r = rodar(
        "embreagem_disco",
        funcao="Freio",
        inercia_kgm2=2.0,
        rotacao_rpm=955.0,
        torque_carga_Nm=0.0,
        massa_kg=10.0,
        calor_especifico=500.0,
    )
    omega = 955.0 * 2.0 * math.pi / 60.0
    energia = 0.5 * 2.0 * omega**2
    assert metrica(r, "Energia dissipada") == pytest.approx(energia / 1000.0)
    assert metrica(r, "Aquecimento") == pytest.approx(energia / (10.0 * 500.0))


def test_descida_com_carga_gasta_mais_energia_que_parada_livre():
    livre = rodar("embreagem_disco", torque_carga_Nm=0.0)
    descendo = rodar("embreagem_disco", torque_carga_Nm=-300.0)
    assert metrica(descendo, "Energia dissipada") > metrica(livre, "Energia dissipada")


def test_freio_de_cinta_pela_equacao_de_euler():
    r = rodar(
        "freio_cinta",
        torque_Nm=1000.0,
        fator_servico=1.0,
        D_mm=500.0,
        b_mm=100.0,
        angulo_graus=180.0,
        atrito=0.3,
    )
    razao = math.exp(0.3 * math.pi)
    assert metrica(r, "Razão P₁/P₂") == pytest.approx(razao)
    p1 = 4000.0 * razao / (razao - 1.0)
    assert metrica(r, "Ramo tenso P₁") == pytest.approx(p1 / 1000.0)
    assert metrica(r, "Pressão máxima") == pytest.approx(p1 / (100.0 * 250.0))


def test_freio_de_cinta_cai_no_giro_contrario():
    r = rodar("freio_cinta")
    assert metrica(r, "Torque no giro contrário") < 1500.0 / 2.0


def test_exemplo_de_fuso_de_shigley():
    """Shigley, exemplo 8-1: quadrada, d = 32, p = 4, duas entradas, F = 6,4 kN, f = f_c = 0,08."""
    r = rodar(
        "parafuso_potencia",
        rosca=mo.ROSCA_QUADRADA,
        forca_kN=6.4,
        d_mm=32.0,
        passo_mm=4.0,
        entradas=2,
        atrito=0.08,
        atrito_colar=0.08,
        d_colar_mm=40.0,
        comprimento_mm=0.0,
    )
    assert metrica(r, "Torque para subir") == pytest.approx(26.18, abs=0.02)
    assert metrica(r, "Torque para descer") == pytest.approx(9.77, abs=0.02)
    # A rosca sozinha daria −0,47 N·m: quem segura é o colar, e o programa avisa.
    assert any("só o atrito do colar" in texto for texto in r.alertas)
    assert metrica(r, "Rendimento") == pytest.approx(31.1, abs=0.1)


def test_fuso_de_muitas_entradas_nao_trava():
    r = rodar("parafuso_potencia", entradas=4, atrito=0.08, passo_mm=8.0)
    assert any("NÃO é autotravante" in texto for texto in r.alertas)
    r = rodar("parafuso_potencia", entradas=1)
    assert any("autotravante pela conta" in texto for texto in r.alertas)


def test_coluna_de_johnson_e_euler_se_encontram():
    sy, e = 420.0, 205_000.0
    transicao = math.pi * math.sqrt(2.0 * e / sy)
    assert mo.tensao_critica_coluna(transicao, sy, e) == pytest.approx(sy / 2.0)
    assert mo.tensao_critica_coluna(transicao - 1e-6, sy, e) == pytest.approx(sy / 2.0)
    assert mo.tensao_critica_coluna(0.0, sy, e) == sy


# ---------------------------------------------------------------------------
# Rotativos, hidráulica, placas
# ---------------------------------------------------------------------------


def test_disco_sem_furo_no_centro_tem_a_formula_classica():
    rho = 7.85e-6
    omega = 100.0
    sigma, radial = ro.tensoes_no_disco(rho, omega, 0.3, 0.0, 400.0, 0.0)
    assert sigma == pytest.approx(rho * omega**2 / 1000.0 * 3.3 / 8.0 * 400.0**2)
    assert radial == pytest.approx(sigma)


def test_furo_pequeno_dobra_a_tensao_do_disco():
    rho = 7.85e-6
    sem_furo, _ = ro.tensoes_no_disco(rho, 100.0, 0.3, 0.0, 400.0, 0.0)
    com_furo, radial = ro.tensoes_no_disco(rho, 100.0, 0.3, 0.1, 400.0, 0.1)
    assert com_furo == pytest.approx(2.0 * sem_furo, rel=1e-4)
    assert radial == pytest.approx(0.0, abs=1e-6)


def test_tensao_do_disco_e_nula_na_borda_livre():
    _, radial = ro.tensoes_no_disco(7.85e-6, 100.0, 0.3, 50.0, 400.0, 400.0)
    assert radial == pytest.approx(0.0, abs=1e-9)


def test_energia_e_inercia_do_volante():
    r = rodar(
        "disco_girante",
        rotacao_rpm=955.0,
        D_ext_mm=800.0,
        D_int_mm=0.0,
        t_mm=50.0,
        energia_kJ=5.0,
        cs=0.1,
    )
    massa = 7.85e-6 * math.pi * 400.0**2 * 50.0
    assert metrica(r, "Massa") == pytest.approx(massa)
    assert metrica(r, "Inércia") == pytest.approx(massa * 0.4**2 / 2.0)
    omega = 955.0 * 2.0 * math.pi / 60.0
    assert metrica(r, "Inércia necessária") == pytest.approx(5000.0 / (0.1 * omega**2))


def test_grau_g_da_iso_21940():
    r = rodar("desbalanceamento", grau="G 6,3", rotacao_rpm=3000.0, massa_rotor_kg=100.0)
    assert metrica(r, "Excentricidade") == pytest.approx(6.3 / (3000.0 * math.pi / 30.0))
    # F = m·G·ω
    assert metrica(r, "Força rotativa") == pytest.approx(100.0 * 0.0063 * 314.16 / 1000.0, rel=1e-4)


def test_transmissibilidade_em_raiz_de_dois_vale_um():
    for zeta in (0.01, 0.1, 0.5):
        assert ro.transmissibilidade(math.sqrt(2.0), zeta) == pytest.approx(1.0)


def test_frequencia_pela_deflexao_estatica():
    r = rodar("desbalanceamento", deflexao_mm=10.0)
    assert metrica(r, "Frequência própria do apoio") == pytest.approx(4.98, abs=0.01)


def test_operar_na_ressonancia_reprova():
    r = rodar(
        "desbalanceamento",
        apoio="Direto na estrutura",
        fn_estrutura_Hz=30.0,
        rotacao_rpm=1750.0,
        amortecimento=0.02,
    )
    assert linha(r, "Afastamento da ressonância").status == "NÃO OK"
    assert any("ressonância" in texto for texto in r.alertas)


def test_massa_excentrica_de_peneira():
    r = rodar(
        "desbalanceamento",
        modo=ro.MODO_EXCENTRICO,
        massa_excentrica_kg=20.0,
        raio_mm=100.0,
        rotacao_rpm=955.0,
    )
    omega = 955.0 * 2.0 * math.pi / 60.0
    assert metrica(r, "Força rotativa") == pytest.approx(20.0 * 0.1 * omega**2 / 1000.0)


def test_base_de_maquina_fecha_o_equilibrio():
    r = rodar(
        "base_maquina",
        peso_kN=40.0,
        fh_x_kN=4.0,
        fh_y_kN=0.0,
        altura_mm=500.0,
        torque_Nm=0.0,
        lx_mm=1000.0,
        ly_mm=1000.0,
    )
    reacoes = [item["Reação (kN)"] for item in r.tabelas[0].linhas]
    assert sum(reacoes) == pytest.approx(40.0)
    # Momento de 2 kN·m em 1 m de distância entre pés: ±1 kN por par, ±0,5 por pé.
    assert max(reacoes) == pytest.approx(10.5 + 0.5)
    assert min(reacoes) == pytest.approx(10.0 - 1.0)


def test_base_que_levanta_avisa_e_carrega_o_chumbador():
    r = rodar(
        "base_maquina", peso_kN=2.0, fh_x_kN=10.0, altura_mm=800.0, lx_mm=500.0, torque_Nm=0.0
    )
    assert metrica(r, "Menor reação") < 0
    assert any("levantar" in texto for texto in r.alertas)
    assert linha(r, "Tração no pé (arrancamento)").status == "ALERTA"


def test_atrito_reduz_o_corte_no_chumbador():
    sem = rodar("base_maquina", atrito=0.0)
    com = rodar("base_maquina", atrito=0.3)
    assert metrica(com, "Corte no chumbador") < metrica(sem, "Corte no chumbador")


def test_cilindro_hidraulico_a_mao():
    r = rodar(
        "cilindro_hidraulico",
        pressao_bar=160.0,
        d_camisa_mm=100.0,
        d_haste_mm=56.0,
        vazao_l_min=40.0,
    )
    assert metrica(r, "Força de avanço") == pytest.approx(16.0 * math.pi * 2500.0 / 1000.0)
    assert metrica(r, "Força de recuo") == pytest.approx(16.0 * math.pi * (2500.0 - 784.0) / 1000.0)
    assert metrica(r, "Potência hidráulica") == pytest.approx(16.0 * 40.0 / 60.0)
    assert metrica(r, "Velocidade de avanço") == pytest.approx(40e6 / 60.0 / (math.pi * 2500.0))


def test_haste_longa_flamba():
    r = rodar("cilindro_hidraulico", comprimento_mm=4000.0)
    assert linha(r, "Flambagem da haste").status == "NÃO OK"


def test_placa_circular_nas_duas_bordas():
    apoiada = rodar(
        "placa_circular", borda=ro.BORDA_APOIADA, pressao_MPa=1.0, d_mm=200.0, t_mm=10.0
    )
    engastada = rodar(
        "placa_circular", borda=ro.BORDA_ENGASTADA, pressao_MPa=1.0, d_mm=200.0, t_mm=10.0
    )
    assert metrica(apoiada, "Tensão máxima") == pytest.approx(
        3.0 * 3.3 * 1.0 * 100.0**2 / (8.0 * 100.0)
    )
    assert metrica(engastada, "Tensão máxima") == pytest.approx(0.75 * 100.0)
    assert metrica(apoiada, "Flecha máxima") > 4.0 * metrica(engastada, "Flecha máxima")


def test_placa_retangular_coeficientes_de_roark():
    assert ro.fatores_de_placa(1000.0, 1000.0, ro.BORDA_APOIADA) == (0.2874, 0.0444)
    assert ro.fatores_de_placa(2000.0, 1000.0, ro.BORDA_ENGASTADA) == (0.4974, 0.0277)
    assert ro.fatores_de_placa(9000.0, 1000.0, ro.BORDA_APOIADA) == (0.75, 0.1421)
    beta, _ = ro.fatores_de_placa(1100.0, 1000.0, ro.BORDA_APOIADA)
    assert beta == pytest.approx((0.2874 + 0.3762) / 2.0)


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------


def test_von_mises_tridimensional_do_ponto():
    assert Ponto("uniaxial", 100.0).von_mises == pytest.approx(100.0)
    assert Ponto("corte", 0.0, 0.0, 100.0).von_mises == pytest.approx(100.0 * math.sqrt(3.0))
    assert Ponto("hidrostático", 50.0, 50.0, 0.0, 50.0).von_mises == pytest.approx(0.0, abs=1e-9)


def test_lame_com_von_mises_completo_na_parede_interna():
    pi, ri, re = 50.0, 50.0, 80.0
    r = rodar("Cilindro de parede espessa", pi_MPa=pi, pe_MPa=0.0, ri_mm=ri, re_mm=re, fechado=True)
    assert r.ponto_critico.nome == "Parede interna"
    # Resultado fechado para tubo com tampas e sem pressão externa.
    assert r.ponto_critico.von_mises == pytest.approx(math.sqrt(3.0) * pi * re**2 / (re**2 - ri**2))


def test_lame_nao_manda_trocar_um_plano_que_nao_existe_mais():
    r = rodar("Cilindro de parede espessa")
    assert not any("troque o plano" in texto for texto in r.hipoteses)
    # Segue o plano que governa o cisalhamento: σx radial e σy circunferencial.
    assert r.ponto_critico.sigma_x == pytest.approx(-50.0)


def test_varredura_acha_o_lado_tracionado_com_forca_axial():
    r = rodar("Eixo circular maciço", forca_kN=20.0, momento_Nm=200.0, torque_Nm=0.0)
    assert r.ponto_critico.nome == "Superfície, lado tracionado"
    r = rodar("Eixo circular maciço", forca_kN=-20.0, momento_Nm=200.0, torque_Nm=0.0)
    assert r.ponto_critico.nome == "Superfície, lado comprimido"


def test_eixo_curto_com_cortante_governa_na_linha_neutra():
    r = rodar("Eixo circular maciço", d_mm=30.0, momento_Nm=0.0, torque_Nm=0.0, cortante_kN=50.0)
    assert r.ponto_critico.nome == "Superfície, na linha neutra"
    assert r.ponto_critico.tau_xy == pytest.approx(4.0 * 50_000.0 / (3.0 * math.pi * 225.0))


def test_viga_retangular_pura_em_corte_governa_no_centroide():
    r = rodar("Viga de seção retangular", momento_Nm=0.0, cortante_kN=5.0)
    assert r.ponto_critico.nome == "Centroide"


def test_perfil_i_com_muito_cortante_governa_na_juncao():
    r = rodar(
        MODELO := se.MODELO_SECAO_I,
        h_mm=300.0,
        b_mm=150.0,
        tf_mm=12.0,
        tw_mm=6.0,
        momento_Nm=160_000.0,
        cortante_kN=250.0,
    )
    assert MODELO in cat.CASOS
    assert "Junção" in r.ponto_critico.nome


def test_cantoneira_avisa_da_flexao_obliqua_e_nao_diz_sem_momento():
    r = rodar("Cantoneira de abas iguais", my_Nm=0.0, mz_Nm=1000.0)
    assert any("linha neutra" in texto for texto in r.alertas)
    r = rodar("Cantoneira de abas iguais", my_Nm=0.0, mz_Nm=0.0)
    assert r.alertas == ()


def test_saint_venant_quadrado():
    r = rodar("Torção de seção retangular", b_mm=50.0, c_mm=50.0, torque_Nm=500.0)
    assert r.ponto_critico.tau_xy == pytest.approx(500_000.0 / (0.208 * 50.0**3))


def test_saint_venant_nao_importa_a_ordem_dos_lados():
    a = rodar("Torção de seção retangular", b_mm=60.0, c_mm=30.0)
    b = rodar("Torção de seção retangular", b_mm=30.0, c_mm=60.0)
    assert a.ponto_critico.tau_xy == pytest.approx(b.ponto_critico.tau_xy)


def test_chapa_muito_fina_recai_em_t_sobre_um_terco():
    a, _b = se.coeficientes_saint_venant(1000.0)
    assert a == pytest.approx(1.0 / 3.0)


def test_sem_escoamento_informado_nao_decide():
    r = rodar("Barra sob carga axial", sy_MPa=0.0)
    assert r.status == "N/A"


def test_kt_multiplica_a_tensao_comparada():
    r = rodar("Barra sob carga axial", forca_kN=20.0, area_mm2=200.0, sy_MPa=250.0, fs=1.0, kt=3.0)
    assert linha(r, "von Mises no ponto crítico").solicitante == pytest.approx(300.0)
    assert r.status == "NÃO OK"


def test_compressao_avisa_da_flambagem():
    r = rodar("Barra sob carga axial", forca_kN=-20.0)
    assert any("Flambagem" in texto for texto in r.alertas)


def test_vaso_de_parede_grossa_avisa():
    r = rodar("Vaso cilíndrico de parede fina", d_mm=100.0, t_mm=10.0)
    assert any("D/t < 20" in texto for texto in r.alertas)
    assert linha(r, "Parede fina (D/t)").status == "ALERTA"
