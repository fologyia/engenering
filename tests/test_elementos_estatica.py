"""Casos de estática do Assistente de cargas, contra contas à mão e exemplos publicados.

Fontes das conferências: fórmulas fechadas de resistência dos materiais (Hibbeler, Roark),
SAND2008-0371 (exemplo do apêndice C), tolerâncias da ISO 965-1 e Shigley, cap. 8.
"""

from __future__ import annotations

import math

import pytest

from core import bolt_design as bd
from core import elementos_barras as eb
from core import elementos_catalogo as cat
from core import elementos_estatica as ee
from core import elementos_parafusos as ep
from core import elementos_vigas as ev
from core.elementos_base import calcular_caso

CASOS = cat.CASOS


def _metrica(resultado, rotulo: str) -> float:
    return next(float(m.valor) for m in resultado.metricas if m.rotulo == rotulo)


def _linha(resultado, trecho: str):
    return next(v for v in resultado.verificacoes if trecho in v.nome)


def _tabela(resultado, titulo: str):
    return next(t for t in resultado.tabelas if titulo in t.titulo).linhas


# ---------------------------------------------------------------------------
# Rosca
# ---------------------------------------------------------------------------


def test_dimensoes_da_rosca_batem_com_a_iso_965_em_m10():
    r = ep.dimensoes_da_rosca(bd.obter_rosca("M10"))
    # ISO 724: diâmetros básicos.
    assert r.d2 == pytest.approx(9.026, abs=0.001)
    assert r.d3 == pytest.approx(8.160, abs=0.001)
    assert r.d1_interno == pytest.approx(8.376, abs=0.001)
    # Tabelas de 6g e 6H: as fórmulas ficam a poucos micrômetros.
    assert r.d2_min == pytest.approx(8.862, abs=0.004)
    assert r.d_min == pytest.approx(9.732, abs=0.004)
    assert r.d2_interno_max == pytest.approx(9.206, abs=0.006)
    assert r.d1_interno_max == pytest.approx(8.676, abs=0.008)


def test_areas_de_arrancamento_reproduzem_o_exemplo_da_sandia():
    """Apêndice C de SAND2008-0371: 5/8-11, SAE 5 em ferro fundido, pede 0,9 in engrenados."""
    n, d_bmp, d_bmm, d_mt, d_it = 11.0, 0.5561, 0.6052, 0.5460, 0.5767
    a_s = math.pi * d_mt * (0.5 + n * ep.TAN_30 * (d_bmp - d_mt))
    a_n = math.pi * d_bmm * (0.5 + n * ep.TAN_30 * (d_bmm - d_it))
    # Área de tração para aço acima de 100 ksi, Eq. 36.
    area_tracao = math.pi * (d_bmp / 2.0 - 0.16238 / n) ** 2
    engrenamento = 2.0 * area_tracao / a_s
    razao_j = a_s * 120.0 / (a_n * 45.0)
    assert engrenamento * razao_j == pytest.approx(0.9, abs=0.01)


def test_engrenamento_em_aco_comum_fica_perto_de_um_diametro_e_cresce_na_peca_fraca():
    m10 = bd.obter_rosca("M10")
    igual = ep.engrenamento_minimo(m10, 800.0, 800.0)
    em_a36 = ep.engrenamento_minimo(m10, 800.0, 400.0)
    em_fraca = ep.engrenamento_minimo(m10, 800.0, 200.0)
    assert igual == pytest.approx(7.47, abs=0.05)  # 2·At/a_s, com J < 1
    assert 1.0 < em_a36 / 10.0 < 1.2
    assert em_fraca == pytest.approx(2.0 * em_a36, rel=1e-9)


def test_rosca_curta_em_material_fraco_reprova_e_a_peca_arranca_primeiro():
    resultado = calcular_caso(
        CASOS["rosca_arrancamento"],
        {"le_mm": 6.0, "sut_MPa": 200.0, "forca_kN": 30.0, "peca": "Alumínio, latão ou bronze"},
    )
    assert resultado.status == "NÃO OK"
    assert "rosca da peça arranca" in resultado.resumo
    assert _linha(resultado, "Engrenamento").status == "ALERTA"
    assert _linha(resultado, "Regra prática").status == "ALERTA"


def test_forca_de_arrancamento_e_metade_da_ruptura_vezes_a_area():
    resultado = calcular_caso(CASOS["rosca_arrancamento"], {"le_mm": 10.0, "sut_MPa": 400.0})
    r = ep.dimensoes_da_rosca(bd.obter_rosca("M12"))
    esperado = 0.5 * 400.0 * ep.area_de_arrancamento_da_peca(r) * 10.0 / 1000.0
    assert _metrica(resultado, "Rosca da peça arranca com") == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Parafuso sob força axial
# ---------------------------------------------------------------------------


def test_rigidez_do_parafuso_e_das_pecas_contra_a_conta_de_mao():
    m12 = bd.obter_rosca("M12")
    junta = ep.rigidez_da_junta(m12, 40.0, 16.0, "Aço")
    area_lisa = math.pi * 12.0**2 / 4.0
    k_b = 1.0 / (16.0 / (84.3 * 207e3) + 24.0 / (area_lisa * 207e3))
    assert junta.k_parafuso == pytest.approx(k_b, rel=1e-9)
    assert junta.k_pecas == pytest.approx(207e3 * 12.0 * 0.78715 * math.exp(0.62873 * 12 / 40))
    # Os dois modelos da junta concordam na faixa usual.
    assert junta.k_pecas == pytest.approx(junta.k_pecas_cone, rel=0.1)
    assert 0.05 < junta.c < 0.35


def test_sem_pre_carga_o_parafuso_recebe_a_carga_inteira():
    resultado = calcular_caso(
        CASOS["parafuso_axial"],
        {"aperto": ep.SEM_PRE_CARGA, "n": 2, "forca_kN": 20.0, "rosca": "M12", "fs": 1.0},
    )
    assert _metrica(resultado, "Carga por parafuso") == pytest.approx(10.0)
    assert _metrica(resultado, "Tensão na rosca") == pytest.approx(10000.0 / 84.3)
    # S_p = 580 MPa até M16, e dois parafusos.
    assert _metrica(resultado, "O conjunto aguenta") == pytest.approx(2 * 580 * 84.3 / 1000)


def test_com_pre_carga_usa_as_duas_pontas_da_dispersao():
    v = {
        "rosca": "M12",
        "n": 1,
        "forca_kN": 10.0,
        "fs": 1.0,
        "fracao": 0.6,
        "metodo": "Medição do alongamento (±5 %)",
    }
    resultado = calcular_caso(CASOS["parafuso_axial"], v)
    prova = 580.0 * 84.3 / 1000.0
    c = _metrica(resultado, "Rigidez C")
    parafuso = _linha(resultado, "maior pré-carga")
    assert parafuso.solicitante == pytest.approx(0.6 * prova * 1.05 + c * 10.0)
    assert parafuso.resistente == pytest.approx(prova)
    separacao = _linha(resultado, "Separação")
    assert separacao.solicitante == pytest.approx((1.0 - c) * 10.0)
    assert separacao.resistente == pytest.approx(0.6 * prova * 0.95)


def test_torque_sai_de_k_f_d_e_o_conjunto_da_capacidade():
    resultado = calcular_caso(CASOS["parafuso_axial"], {"fracao": 0.6, "n": 4})
    prova = 580.0 * 84.3
    assert _metrica(resultado, "Torque de aperto") == pytest.approx(
        0.2 * 0.6 * prova * 12.0 / 1000.0
    )
    capacidade, _ = ep.capacidade_com_pre_carga(
        prova, 0.6, 0.25, _metrica(resultado, "Rigidez C"), 1.5
    )
    assert _metrica(resultado, "O conjunto aguenta") == pytest.approx(
        4 * capacidade / 1000.0, rel=1e-3
    )


def test_carga_alta_reprova_e_aponta_a_rosca_que_atende():
    resultado = calcular_caso(CASOS["parafuso_axial"], {"forca_kN": 400.0, "rosca": "M8"})
    assert resultado.status == "NÃO OK"
    assert "menor rosca que atende" in resultado.resumo
    linhas = _tabela(resultado, "Qual rosca atende")
    atende = [linha["Rosca"] for linha in linhas if linha["Atende"] == "Sim"]
    assert atende
    # O resumo cita a primeira que atende, e as maiores também atendem.
    assert f"a {atende[0]}." in resultado.resumo
    assert linhas[-1]["Atende"] == "Sim"


def test_grafico_da_junta_troca_de_regime_na_separacao():
    resultado = calcular_caso(CASOS["parafuso_axial"], {"n": 1, "forca_kN": 1.0})
    parafuso = [p for p in resultado.graficos[0].pontos if p[2] == "Força no parafuso"]
    aperto = [p for p in resultado.graficos[0].pontos if p[2] == "Aperto nas peças"]
    # Depois de abrir a junta, o parafuso recebe a carga inteira e o aperto acaba.
    assert parafuso[-1][1] == pytest.approx(parafuso[-1][0])
    assert aperto[-1][1] == pytest.approx(0.0)
    assert parafuso[0][1] == pytest.approx(aperto[0][1])


def test_torque_nos_dois_sentidos_da_a_mesma_conta():
    caso = CASOS["torque_aperto"]
    ida = calcular_caso(caso, {"fracao": 0.5})
    torque = _metrica(ida, "Torque de aperto")
    volta = calcular_caso(caso, {"sentido": ep.TENHO_TORQUE, "torque_Nm": torque})
    assert _metrica(volta, "Pré-carga") == pytest.approx(_metrica(ida, "Pré-carga"))


def test_tabela_de_torque_por_classe_cresce_com_a_classe():
    linhas = _tabela(calcular_caso(CASOS["torque_aperto"], {"rosca": "M12"}), "Torque por classe")
    torques = {linha["Classe"]: linha["Torque (N·m)"] for linha in linhas}
    assert torques["4.6"] < torques["8.8"] < torques["10.9"] < torques["12.9"]


def test_torque_alto_passa_da_carga_de_prova():
    resultado = calcular_caso(
        CASOS["torque_aperto"], {"sentido": ep.TENHO_TORQUE, "torque_Nm": 200.0}
    )
    assert resultado.status == "NÃO OK"


# ---------------------------------------------------------------------------
# Grupo de parafusos
# ---------------------------------------------------------------------------


def test_grupo_circular_com_momento_bate_com_m_r_sobre_soma():
    pontos = ep.coordenadas_do_grupo({"arranjo": ep.CIRCULO, "n_circulo": 4, "dc_mm": 200.0})
    forcas = ep.forcas_no_grupo(pontos, 40.0, 0.0, 2.0, 0.0, 0.0, 0.0)
    # Quatro parafusos: dois em x = ±100; Σx² = 2·100². M·x/Σx² = 2e3·100/20000 = 10 kN.
    tracoes = sorted(t for t, _ in forcas)
    assert tracoes[-1] == pytest.approx(10.0 + 10.0)
    assert tracoes[0] == pytest.approx(10.0 - 10.0)


def test_grupo_em_filas_com_torque_cresce_com_a_distancia():
    pontos = ep.coordenadas_do_grupo(
        {"arranjo": ep.FILAS, "filas": 2, "colunas": 2, "sx_mm": 100.0, "sy_mm": 100.0}
    )
    forcas = ep.forcas_no_grupo(pontos, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    r = math.hypot(50.0, 50.0)
    esperado = 1.0 * 1000.0 * r / (4 * r**2)
    assert all(c == pytest.approx(esperado) for _, c in forcas)


def test_coordenadas_livres_acham_o_centro_sozinhas():
    pontos = ep.coordenadas_do_grupo(
        {
            "arranjo": ep.LIVRE,
            "coordenadas": ({"x_mm": 100.0, "y_mm": 100.0}, {"x_mm": 300.0, "y_mm": 100.0}),
        }
    )
    assert pontos == [(-100.0, 0.0), (100.0, 0.0)]


def test_parafusos_em_linha_nao_resistem_ao_momento_na_outra_direcao():
    pontos = [(-100.0, 0.0), (100.0, 0.0)]
    with pytest.raises(ValueError, match="linha só"):
        ep.forcas_no_grupo(pontos, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0)


def test_lado_comprimido_gera_o_aviso_de_junta_fechada():
    resultado = calcular_caso(CASOS["grupo_parafusos"], {"n_kN": 10.0, "mx_kNm": 8.0})
    assert any("tração negativa" in texto for texto in resultado.alertas)


# ---------------------------------------------------------------------------
# Viga
# ---------------------------------------------------------------------------

UNIFORME = ({"tipo": ev.DISTRIBUIDA, "x1_m": 0.0, "x2_m": None, "valor": 10.0, "valor2": None},)
PONTUAL_MEIO = ({"tipo": ev.CONCENTRADA, "x1_m": 2.0, "x2_m": None, "valor": 12.0, "valor2": None},)
RETANGULO = {"tipo_secao": ev.RETANGULAR, "b_mm": 100.0, "h_mm": 200.0, "e_GPa": 200.0}
I_RET = 100.0 * 200.0**3 / 12.0


def test_viga_biapoiada_com_carga_uniforme():
    resultado = calcular_caso(CASOS["viga_reacoes"], {**RETANGULO, "l_m": 4.0, "cargas": UNIFORME})
    assert _metrica(resultado, "Reação em A") == pytest.approx(20.0)
    assert _metrica(resultado, "Reação em B") == pytest.approx(20.0)
    assert _metrica(resultado, "Momento máximo") == pytest.approx(10.0 * 4.0**2 / 8.0)
    assert _metrica(resultado, "Cortante máximo") == pytest.approx(20.0)
    flecha = 5.0 * 10.0 * 4000.0**4 / (384.0 * 200e3 * I_RET)
    assert _metrica(resultado, "Flecha máxima") == pytest.approx(flecha, rel=1e-6)
    assert _metrica(resultado, "Tensão máxima") == pytest.approx(20e6 / (100.0 * 200.0**2 / 6.0))


def test_balanco_com_ponta_carregada_tem_reacao_e_momento_no_engaste():
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {
            **RETANGULO,
            "esquema": ev.BALANCO_ESQ,
            "l_m": 2.0,
            "cargas": (
                {"tipo": ev.CONCENTRADA, "x1_m": 2.0, "x2_m": None, "valor": 5.0, "valor2": None},
            ),
        },
    )
    reacao = _tabela(resultado, "Reações")[0]
    assert reacao["Vertical, para cima (kN)"] == pytest.approx(5.0)
    assert abs(reacao["Momento (kN·m)"]) == pytest.approx(10.0)
    flecha = 5000.0 * 2000.0**3 / (3.0 * 200e3 * I_RET)
    assert _metrica(resultado, "Flecha máxima") == pytest.approx(flecha, rel=1e-6)


def test_balanco_usa_o_dobro_do_comprimento_no_limite_de_flecha():
    """NBR 8800, Tabela C.1, nota a: L é o dobro do comprimento teórico do balanço."""
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {
            **RETANGULO,
            "esquema": ev.BALANCO_DIR,
            "l_m": 2.0,
            "limite_flecha": "L/250",
            "cargas": UNIFORME,
        },
    )
    linha = _linha(resultado, "Flecha")
    assert "balanço" in linha.nome
    assert linha.resistente == pytest.approx(2.0 * 2000.0 / 250.0)


def test_viga_engastada_e_apoiada_tem_as_reacoes_classicas():
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {**RETANGULO, "esquema": ev.ENGASTADA_APOIADA, "l_m": 4.0, "cargas": UNIFORME},
    )
    assert _metrica(resultado, "Reação em A") == pytest.approx(5.0 * 10.0 * 4.0 / 8.0)
    assert _metrica(resultado, "Reação em B") == pytest.approx(3.0 * 10.0 * 4.0 / 8.0)
    assert _metrica(resultado, "Momento máximo") == pytest.approx(10.0 * 4.0**2 / 8.0)


def test_viga_biengastada_tem_momento_de_q_l2_sobre_12():
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {**RETANGULO, "esquema": ev.BIENGASTADA, "l_m": 6.0, "cargas": UNIFORME},
    )
    assert _metrica(resultado, "Momento máximo") == pytest.approx(10.0 * 36.0 / 12.0)
    flecha = 10.0 * 6000.0**4 / (384.0 * 200e3 * I_RET)
    assert _metrica(resultado, "Flecha máxima") == pytest.approx(flecha, rel=1e-6)


def test_viga_continua_de_dois_vaos_iguais():
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {**RETANGULO, "esquema": ev.DOIS_VAOS, "l_m": 8.0, "a_m": 4.0, "cargas": UNIFORME},
    )
    reacoes = [r["Vertical, para cima (kN)"] for r in _tabela(resultado, "Reações")]
    assert reacoes == pytest.approx([3 / 8 * 40, 10 / 8 * 40, 3 / 8 * 40])
    assert _metrica(resultado, "Momento máximo") == pytest.approx(10.0 * 4.0**2 / 8.0)


def test_viga_com_balancos_separa_a_flecha_por_trecho():
    resultado = calcular_caso(
        CASOS["viga_reacoes"],
        {**RETANGULO, "esquema": ev.COM_BALANCOS, "l_m": 6.0, "a_m": 1.0, "b_m": 5.0},
    )
    trechos = [linha["Trecho"] for linha in _tabela(resultado, "Flecha em cada trecho")]
    assert trechos == ["Balanço à esquerda", "Vão 1", "Balanço à direita"]


def test_carga_trapezoidal_e_o_momento_aplicado_entram_com_o_sinal_da_tela():
    trapezio = ({"tipo": ev.DISTRIBUIDA, "x1_m": 0.0, "x2_m": 4.0, "valor": 0.0, "valor2": 12.0},)
    resultado = calcular_caso(CASOS["viga_reacoes"], {**RETANGULO, "l_m": 4.0, "cargas": trapezio})
    # Triângulo: resultante 24 kN a 2/3 do vão.
    assert _metrica(resultado, "Reação em A") == pytest.approx(8.0)
    assert _metrica(resultado, "Reação em B") == pytest.approx(16.0)
    momento = ({"tipo": ev.MOMENTO, "x1_m": 2.0, "x2_m": None, "valor": 8.0, "valor2": None},)
    resultado = calcular_caso(CASOS["viga_reacoes"], {**RETANGULO, "l_m": 4.0, "cargas": momento})
    # ΣM em A: R_B·L + M = 0. O momento anti-horário puxa B para baixo e levanta A.
    assert _metrica(resultado, "Reação em A") == pytest.approx(2.0)
    assert _metrica(resultado, "Reação em B") == pytest.approx(-2.0)


def test_carga_fora_da_viga_e_sem_carga_viram_mensagem():
    fora = ({"tipo": ev.CONCENTRADA, "x1_m": 9.0, "x2_m": None, "valor": 1.0, "valor2": None},)
    with pytest.raises(ValueError, match="linha 1"):
        calcular_caso(CASOS["viga_reacoes"], {"l_m": 4.0, "cargas": fora})
    with pytest.raises(ValueError, match="ao menos uma carga"):
        calcular_caso(CASOS["viga_reacoes"], {"cargas": ()})


def test_linha_em_branco_na_tabela_de_cargas_e_ignorada():
    base = calcular_caso(CASOS["viga_reacoes"], {"cargas": UNIFORME})
    branca = {"tipo": None, "x1_m": float("nan"), "x2_m": None, "valor": None, "valor2": None}
    com_branca = calcular_caso(CASOS["viga_reacoes"], {"cargas": (*UNIFORME, branca)})
    assert _metrica(com_branca, "Momento máximo") == _metrica(base, "Momento máximo")


def test_celula_obrigatoria_vazia_diz_a_linha_e_a_coluna():
    meia = {"tipo": ev.CONCENTRADA, "x1_m": 1.0, "x2_m": None, "valor": None, "valor2": None}
    with pytest.raises(ValueError, match="linha 2, Valor"):
        calcular_caso(CASOS["viga_reacoes"], {"cargas": (*UNIFORME, meia)})


def test_peso_proprio_soma_o_peso_da_secao():
    secao = {**RETANGULO, "peso_proprio": True, "densidade_kg_m3": 7850.0, "l_m": 4.0}
    resultado = calcular_caso(CASOS["viga_reacoes"], {**secao, "cargas": ()})
    peso = 0.1 * 0.2 * 7850.0 * 9.80665 * 4.0 / 1000.0
    assert _metrica(resultado, "Reação em A") == pytest.approx(peso / 2.0, rel=1e-6)


def test_lista_de_perfis_mais_leves_vem_em_ordem_e_atende():
    resultado = calcular_caso(CASOS["viga_reacoes"])
    linhas = _tabela(resultado, "Perfis mais leves")
    massas = [linha["Massa (kg/m)"] for linha in linhas]
    assert massas == sorted(massas)
    assert all(linha["Flecha (fração do limite)"] <= 1.0 for linha in linhas)
    assert all(linha["Tensão (MPa)"] <= 250.0 / 1.5 for linha in linhas)


def test_perfil_aberto_avisa_da_flambagem_lateral_e_leva_para_a_norma():
    resultado = calcular_caso(CASOS["viga_reacoes"])
    assert any("flambar de lado" in texto for texto in resultado.alertas)
    assert resultado.envios[0].destino == "perfil_nbr8800"
    assert resultado.envios[0].valores["mx_kNm"] == pytest.approx(37.5)


def test_tubo_nao_tem_o_aviso_de_flambagem_lateral():
    resultado = calcular_caso(
        CASOS["viga_reacoes"], {"tipo_secao": ev.TUBO_CIRCULAR, "d_mm": 200.0, "t_mm": 8.0}
    )
    assert not any("flambar de lado" in texto for texto in resultado.alertas)


# ---------------------------------------------------------------------------
# Seção e flexão
# ---------------------------------------------------------------------------


def test_secao_retangular_e_as_propriedades_informadas_dao_a_mesma_tensao():
    conta = calcular_caso(
        CASOS["flexao_secao"],
        {"tipo_secao": ev.RETANGULAR, "b_mm": 100.0, "h_mm": 200.0, "m_kNm": 20.0, "v_kN": 0.0},
    )
    w = 100.0 * 200.0**2 / 6.0
    assert _metrica(conta, "Tensão na fibra de baixo") == pytest.approx(20e6 / w)
    assert _metrica(conta, "Tensão na fibra de cima") == pytest.approx(-20e6 / w)
    direta = calcular_caso(
        CASOS["flexao_secao"],
        {
            "tipo_secao": ev.INFORMAR,
            "a_mm2": 20000.0,
            "i_mm4": I_RET,
            "w_mm3": w,
            "m_kNm": 20.0,
            "v_kN": 0.0,
        },
    )
    assert _metrica(direta, "Tensão na fibra de baixo") == pytest.approx(20e6 / w)


def test_flexao_com_forca_axial_soma_na_fibra_tracionada():
    resultado = calcular_caso(
        CASOS["flexao_secao"],
        {
            "tipo_secao": ev.RETANGULAR,
            "b_mm": 100.0,
            "h_mm": 200.0,
            "m_kNm": 10.0,
            "n_kN": 100.0,
            "v_kN": 15.0,
        },
    )
    w = 100.0 * 200.0**2 / 6.0
    assert _metrica(resultado, "Tensão na fibra de baixo") == pytest.approx(5.0 + 10e6 / w)
    assert _metrica(resultado, "Cortante máximo") == pytest.approx(1.5 * 15e3 / 20000.0)


def test_w_necessario_e_o_limite_exato_da_tensao():
    resultado = calcular_caso(CASOS["flexao_secao"], {"m_kNm": 30.0, "n_kN": 0.0, "fs": 1.5})
    assert _metrica(resultado, "W necessário") == pytest.approx(30e6 / (250.0 / 1.5) / 1000.0)


def test_flexao_leva_os_pontos_para_o_circulo_de_mohr():
    resultado = calcular_caso(CASOS["flexao_secao"])
    assert [p.nome for p in resultado.pontos] == [
        "Fibra de cima",
        "Fibra de baixo",
        "Centro da seção",
    ]


def test_perfil_pela_norma_usa_a_mesma_verificacao_das_barras_do_modelo():
    resultado = calcular_caso(CASOS["perfil_nbr8800"], {"mx_kNm": 40.0, "v_kN": 30.0, "lb_m": 3.0})
    flexao = _linha(resultado, "Flexão em torno de x")
    assert flexao.solicitante == pytest.approx(40.0)
    assert flexao.resistente == pytest.approx(67.26, abs=0.05)
    assert any("flambagem lateral" in texto for texto in resultado.alertas)


def test_travar_a_viga_aumenta_o_momento_resistente():
    solta = calcular_caso(CASOS["perfil_nbr8800"], {"lb_m": 6.0})
    travada = calcular_caso(CASOS["perfil_nbr8800"], {"lb_m": 1.0})
    assert _metrica(travada, "Mx,Rd") > 1.5 * _metrica(solta, "Mx,Rd")


def test_perfil_reprovado_mostra_os_que_atendem():
    resultado = calcular_caso(
        CASOS["perfil_nbr8800"], {"perfil": "W 150 x 13,0", "mx_kNm": 60.0, "lb_m": 1.0}
    )
    assert resultado.status == "NÃO OK"
    assert _tabela(resultado, "Perfis mais leves")


def test_norma_escolhida_chega_na_conta():
    nova = calcular_caso(CASOS["perfil_nbr8800"], {"norma": "ABNT NBR 8800:2025"})
    antiga = calcular_caso(CASOS["perfil_nbr8800"], {"norma": "AISC 360-16 (LRFD)"})
    assert _metrica(nova, "Mx,Rd") != _metrica(antiga, "Mx,Rd")


# ---------------------------------------------------------------------------
# Barras
# ---------------------------------------------------------------------------


def test_corrente_presa_nas_duas_pontas_divide_pela_rigidez():
    _, esforcos, r_esq, r_dir = eb.resolver_corrente(
        [100.0, 300.0], [40.0, 0.0], [0.0, 0.0], presa_nas_duas=True
    )
    # Carga no nó do meio: u = 40/400 = 0,1. O trecho mais rígido é o que recebe mais.
    assert esforcos == pytest.approx([10.0, -30.0])
    assert r_esq == pytest.approx(-10.0)
    assert r_dir == pytest.approx(-30.0)


def test_barra_em_trechos_soma_os_alongamentos():
    resultado = calcular_caso(
        CASOS["barra_axial"],
        {
            "trechos": (
                {"l_mm": 500.0, "a_mm2": 800.0, "e_GPa": 200.0, "f_kN": 0.0},
                {"l_mm": 300.0, "a_mm2": 400.0, "e_GPa": 200.0, "f_kN": 40.0},
            )
        },
    )
    esperado = 40e3 * 500.0 / (800.0 * 200e3) + 40e3 * 300.0 / (400.0 * 200e3)
    assert _metrica(resultado, "Deslocamento no fim") == pytest.approx(esperado)
    assert _metrica(resultado, "Maior tensão") == pytest.approx(100.0)


def test_barra_com_cargas_intermediarias_muda_o_esforco_em_cada_trecho():
    resultado = calcular_caso(
        CASOS["barra_axial"],
        {
            "trechos": (
                {"l_mm": 200.0, "a_mm2": 500.0, "e_GPa": 200.0, "f_kN": -30.0},
                {"l_mm": 200.0, "a_mm2": 500.0, "e_GPa": 200.0, "f_kN": 50.0},
            )
        },
    )
    linhas = _tabela(resultado, "Trecho a trecho")
    assert linhas[0]["Esforço N (kN)"] == pytest.approx(20.0)
    assert linhas[1]["Esforço N (kN)"] == pytest.approx(50.0)


def test_barra_presa_nas_duas_pontas_com_calor_comprime_pela_formula_classica():
    resultado = calcular_caso(
        CASOS["barra_axial"],
        {
            "apoio": eb.PRESA_DUAS,
            "dt_C": 50.0,
            "alfa": 12.0,
            "sy_MPa": 500.0,
            "trechos": ({"l_mm": 1000.0, "a_mm2": 500.0, "e_GPa": 200.0, "f_kN": 0.0},),
        },
    )
    assert _metrica(resultado, "Maior tensão") == pytest.approx(200e3 * 12e-6 * 50.0)
    assert any("comprimido" in texto for texto in resultado.alertas)


def test_dois_trechos_diferentes_presos_com_calor_mantem_o_mesmo_esforco():
    """Regressão do sinal da carga térmica: em série, o esforço é único em todos os trechos."""
    resultado = calcular_caso(
        CASOS["barra_axial"],
        {
            "apoio": eb.PRESA_DUAS,
            "dt_C": 40.0,
            "alfa": 12.0,
            "sy_MPa": 800.0,
            "trechos": (
                {"l_mm": 300.0, "a_mm2": 1000.0, "e_GPa": 200.0, "f_kN": 0.0},
                {"l_mm": 700.0, "a_mm2": 400.0, "e_GPa": 200.0, "f_kN": 0.0},
            ),
        },
    )
    linhas = _tabela(resultado, "Trecho a trecho")
    # N = -α·ΔT·L_total / Σ(L/(E·A)), a soma dos alongamentos precisa dar zero.
    flexibilidade = 300.0 / (1000.0 * 200e3) + 700.0 / (400.0 * 200e3)
    esperado = -12e-6 * 40.0 * 1000.0 / flexibilidade / 1000.0
    assert linhas[0]["Esforço N (kN)"] == pytest.approx(esperado)
    assert linhas[1]["Esforço N (kN)"] == pytest.approx(esperado)
    assert linhas[1]["Deslocamento no fim (mm)"] == pytest.approx(0.0, abs=1e-9)


def test_torcao_bate_com_t_l_sobre_g_j():
    resultado = calcular_caso(
        CASOS["barra_torcao"],
        {
            "g_GPa": 80.0,
            "giro_limite": 10.0,
            "trechos": ({"l_mm": 1000.0, "d_mm": 50.0, "di_mm": None, "t_Nm": 1000.0},),
        },
    )
    j = math.pi * 50.0**4 / 32.0
    assert _metrica(resultado, "Giro máximo") == pytest.approx(
        math.degrees(1e6 * 1000.0 / (80e3 * j))
    )
    assert _metrica(resultado, "Maior tensão") == pytest.approx(1e6 * 25.0 / j)


def test_tubo_em_torcao_e_diametro_interno_impossivel():
    tubo = calcular_caso(
        CASOS["barra_torcao"],
        {"trechos": ({"l_mm": 500.0, "d_mm": 60.0, "di_mm": 40.0, "t_Nm": 400.0},)},
    )
    j = math.pi * (60.0**4 - 40.0**4) / 32.0
    assert _metrica(tubo, "Maior tensão") == pytest.approx(400e3 * 30.0 / j)
    with pytest.raises(ValueError, match="diâmetro interno"):
        calcular_caso(
            CASOS["barra_torcao"],
            {"trechos": ({"l_mm": 500.0, "d_mm": 40.0, "di_mm": 40.0, "t_Nm": 1.0},)},
        )


def test_eixo_preso_nas_duas_pontas_divide_o_torque():
    resultado = calcular_caso(
        CASOS["barra_torcao"],
        {
            "apoio": eb.PRESA_DUAS,
            "trechos": (
                {"l_mm": 200.0, "d_mm": 40.0, "di_mm": None, "t_Nm": 300.0},
                {"l_mm": 600.0, "d_mm": 40.0, "di_mm": None, "t_Nm": 0.0},
            ),
        },
    )
    linhas = _tabela(resultado, "Trecho a trecho")
    assert linhas[0]["Torque (N·m)"] == pytest.approx(225.0)
    assert linhas[1]["Torque (N·m)"] == pytest.approx(-75.0)


def test_coluna_longa_e_euler_e_curta_e_johnson():
    area, raio, sy, e = 1000.0, 10.0, 250.0, 200e3
    longa = 2000.0
    assert eb.carga_critica(area, raio, longa, sy, e) == pytest.approx(
        math.pi**2 * e * area / (longa / raio) ** 2
    )
    curta = 500.0
    assert eb.carga_critica(area, raio, curta, sy, e) == pytest.approx(
        area * (sy - (sy * curta / raio / (2.0 * math.pi)) ** 2 / e)
    )


def test_euler_e_johnson_se_encontram_na_transicao():
    area, raio, sy, e = 1000.0, 10.0, 250.0, 200e3
    transicao = math.sqrt(2.0 * math.pi**2 * e / sy) * raio
    assert eb.carga_critica(area, raio, transicao * 0.9999, sy, e) == pytest.approx(
        eb.carga_critica(area, raio, transicao * 1.0001, sy, e), rel=1e-3
    )


def test_coluna_engastada_e_livre_aguenta_bem_menos():
    articulada = calcular_caso(CASOS["coluna_simples"], {"l_m": 4.0})
    livre = calcular_caso(
        CASOS["coluna_simples"], {"l_m": 4.0, "condicao": "Engastada e livre (K = 2,1)"}
    )
    razao = _metrica(articulada, "Carga crítica") / _metrica(livre, "Carga crítica")
    assert razao > 3.5
    assert _metrica(livre, "Fator K") == pytest.approx(2.1)


def test_coluna_usa_o_menor_raio_de_giracao():
    resultado = calcular_caso(
        CASOS["coluna_simples"],
        {"tipo_secao": ev.RETANGULAR, "b_mm": 20.0, "h_mm": 100.0},
    )
    assert _metrica(resultado, "Raio de giração mínimo") == pytest.approx(20.0 / math.sqrt(12.0))


# ---------------------------------------------------------------------------
# Treliça
# ---------------------------------------------------------------------------

NOS = (
    {"nome": "A", "x_m": 0.0, "y_m": 0.0, "apoio": eb.PINO, "fx_kN": 0.0, "fy_kN": 0.0},
    {"nome": "B", "x_m": 4.0, "y_m": 0.0, "apoio": eb.ROLETE_Y, "fx_kN": 0.0, "fy_kN": 0.0},
    {"nome": "C", "x_m": 2.0, "y_m": 1.5, "apoio": eb.LIVRE, "fx_kN": 0.0, "fy_kN": -30.0},
)
BARRAS = ({"i": "A", "j": "B"}, {"i": "A", "j": "C"}, {"i": "B", "j": "C"})


def test_trelica_de_tres_barras_bate_com_o_metodo_dos_nos():
    resposta = eb.resolver_trelica(NOS, BARRAS, 200e3 * 500.0 / 1000.0)
    # Diagonal: 2 m por 1,5 m, comprimento 2,5 m. Cada apoio leva 15 kN.
    assert resposta.reacoes["A"][1] == pytest.approx(15.0)
    assert resposta.reacoes["B"][1] == pytest.approx(15.0)
    diagonal = -15.0 * 2.5 / 1.5
    inferior = 15.0 * 2.0 / 1.5
    assert resposta.forcas == pytest.approx((inferior, diagonal, diagonal))
    assert resposta.hiperestatica == 0


def test_flecha_da_trelica_bate_com_o_trabalho_virtual():
    ea = 200e3 * 500.0 / 1000.0  # kN
    resposta = eb.resolver_trelica(NOS, BARRAS, ea)
    # δ = Σ N·n·L/(EA), com n = N/30 para a carga unitária em C.
    soma = sum(n**2 / 30.0 * l for n, l in zip(resposta.forcas, resposta.comprimentos, strict=True))
    assert abs(resposta.deslocamentos["C"][1]) == pytest.approx(soma / ea * 1000.0)


def test_barra_sem_forca_da_trelica_mostra_zero_exato():
    linhas = _tabela(calcular_caso(CASOS["trelica_plana"]), "Força em cada barra")
    assert any(linha["Força (kN)"] == 0.0 and linha["Regime"] == "Sem força" for linha in linhas)


def test_trelica_instavel_e_nome_errado_viram_mensagem():
    sem_diagonal = (
        {"nome": "A", "x_m": 0.0, "y_m": 0.0, "apoio": eb.PINO, "fx_kN": 0.0, "fy_kN": 0.0},
        {"nome": "B", "x_m": 2.0, "y_m": 0.0, "apoio": eb.PINO, "fx_kN": 0.0, "fy_kN": 0.0},
        {"nome": "C", "x_m": 0.0, "y_m": 2.0, "apoio": eb.LIVRE, "fx_kN": 1.0, "fy_kN": 0.0},
        {"nome": "D", "x_m": 2.0, "y_m": 2.0, "apoio": eb.LIVRE, "fx_kN": 0.0, "fy_kN": 0.0},
    )
    quadro = ({"i": "A", "j": "C"}, {"i": "B", "j": "D"}, {"i": "C", "j": "D"})
    with pytest.raises(ValueError, match="não é estável"):
        eb.resolver_trelica(sem_diagonal, quadro, 1000.0)
    with pytest.raises(ValueError, match="nomes de nós"):
        eb.resolver_trelica(NOS, ({"i": "A", "j": "Z"},), 1000.0)
    with pytest.raises(ValueError, match="já existe"):
        eb.resolver_trelica(NOS, (*BARRAS, {"i": "C", "j": "A"}), 1000.0)


def test_trelica_compara_a_comprimida_com_a_flambagem():
    resultado = calcular_caso(CASOS["trelica_plana"], {"nos": NOS, "barras": BARRAS})
    linha = _linha(resultado, "comprimida")
    assert "A-C" in linha.nome or "B-C" in linha.nome
    assert linha.solicitante == pytest.approx(25.0)
    assert linha.resistente < 0.9 * 250.0 * 864.0 / 1.5 / 1000.0


# ---------------------------------------------------------------------------
# Pórtico
# ---------------------------------------------------------------------------


def test_console_em_l_com_carga_na_ponta():
    resultado = calcular_caso(
        CASOS["portico_simples"],
        {"forma": eb.CONSOLE, "l_m": 2.0, "h_m": 3.0, "q_kNm": 0.0, "p_kN": 10.0, "h_kN": 0.0},
    )
    reacao = _tabela(resultado, "Reações")[0]
    assert reacao["Ry (kN)"] == pytest.approx(10.0)
    assert abs(reacao["Momento (kN·m)"]) == pytest.approx(20.0)
    assert _metrica(resultado, "Maior momento") == pytest.approx(20.0)


def test_mao_francesa_bate_com_o_equilibrio_do_no():
    resultado = calcular_caso(
        CASOS["portico_simples"],
        {
            "forma": eb.MAO_FRANCESA,
            "h_m": 1.0,
            "l_m": 2.0,
            "a_m": 1.0,
            "q_kNm": 0.0,
            "p_kN": 10.0,
            "h_kN": 0.0,
        },
    )
    reacoes = {r["Apoio"]: r for r in _tabela(resultado, "Reações")}
    # Soma de momentos em B: a diagonal, a 45 graus, tem componente vertical de 20 kN em D.
    assert abs(reacoes["A"]["Ry (kN)"]) == pytest.approx(20.0, rel=1e-3)
    assert abs(reacoes["A"]["Rx (kN)"]) == pytest.approx(20.0, rel=1e-3)


def test_portico_confere_o_topo_e_a_flecha_no_meio_da_viga():
    resultado = calcular_caso(CASOS["portico_simples"])
    assert _linha(resultado, "topo").nome == "Deslocamento horizontal do topo"
    flecha = _linha(resultado, "Flecha da viga")
    # A flecha do meio da viga é maior que o deslocamento de qualquer nó.
    assert flecha.solicitante > 3.0
    maior = _metrica(resultado, "Maior deslocamento")
    assert maior >= flecha.solicitante


# ---------------------------------------------------------------------------
# Peças, seções e chapas
# ---------------------------------------------------------------------------


def test_equilibrio_sobre_dois_apoios():
    resultado = calcular_caso(
        CASOS["equilibrio_peca"],
        {
            "xb_m": 4.0,
            "cargas": ({"x_m": 1.0, "y_m": 0.0, "fx_kN": 3.0, "fy_kN": -8.0, "m_kNm": 0.0},),
        },
    )
    linhas = {linha["Apoio"]: linha for linha in _tabela(resultado, "Reações")}
    assert linhas["B"]["Ry (kN)"] == pytest.approx(2.0)
    assert linhas["A"]["Ry (kN)"] == pytest.approx(6.0)
    assert linhas["A"]["Rx (kN)"] == pytest.approx(-3.0)


def test_equilibrio_com_rolete_horizontal_e_braco_vertical():
    resultado = calcular_caso(
        CASOS["equilibrio_peca"],
        {
            "xb_m": 0.0,
            "yb_m": 2.0,
            "rolete": ee.ROLETE_X,
            "cargas": ({"x_m": 3.0, "y_m": 0.0, "fx_kN": 0.0, "fy_kN": -10.0, "m_kNm": 0.0},),
        },
    )
    linhas = {linha["Apoio"]: linha for linha in _tabela(resultado, "Reações")}
    assert linhas["B"]["Rx (kN)"] == pytest.approx(-15.0)
    assert linhas["A"]["Rx (kN)"] == pytest.approx(15.0)
    assert linhas["A"]["Ry (kN)"] == pytest.approx(10.0)


def test_engaste_devolve_o_momento_e_fecha_o_equilibrio():
    resultado = calcular_caso(
        CASOS["equilibrio_peca"],
        {
            "apoios": ee.ENGASTE,
            "cargas": ({"x_m": 2.0, "y_m": 1.0, "fx_kN": 5.0, "fy_kN": -10.0, "m_kNm": 1.0},),
        },
    )
    assert _metrica(resultado, "Momento no engaste") == pytest.approx(-(2 * -10 - 1 * 5 + 1))
    assert all(abs(v.solicitante) < 1e-9 for v in resultado.verificacoes)


def test_apoios_na_mesma_linha_do_rolete_nao_seguram_o_giro():
    with pytest.raises(ValueError, match="giraria"):
        calcular_caso(CASOS["equilibrio_peca"], {"xb_m": 0.0, "yb_m": 3.0})


def test_secao_t_montada_bate_com_a_conta_de_mao():
    partes = (
        {
            "tipo": ee.CHEIO,
            "forma": ee.RETANGULO,
            "b_mm": 100.0,
            "h_mm": 20.0,
            "x_mm": 0.0,
            "y_mm": 110.0,
        },
        {
            "tipo": ee.CHEIO,
            "forma": ee.RETANGULO,
            "b_mm": 20.0,
            "h_mm": 100.0,
            "x_mm": 0.0,
            "y_mm": 50.0,
        },
    )
    resultado = calcular_caso(CASOS["secao_montada"], {"partes": partes})
    assert _metrica(resultado, "Área") == pytest.approx(4000.0)
    y_cg = (2000.0 * 110.0 + 2000.0 * 50.0) / 4000.0
    assert y_cg == 80.0
    ix = 100 * 20**3 / 12 + 2000 * 30**2 + 20 * 100**3 / 12 + 2000 * 30**2
    assert _metrica(resultado, "Ix") == pytest.approx(ix / 1e4)
    # Fibra mais afastada: a base da alma, a 80 mm do centro.
    assert _metrica(resultado, "Menor W em x") == pytest.approx(ix / 80.0 / 1e3)


def test_furo_e_circulo_entram_na_secao():
    partes = (
        {
            "tipo": ee.CHEIO,
            "forma": ee.CIRCULO,
            "b_mm": 100.0,
            "h_mm": None,
            "x_mm": 0.0,
            "y_mm": 0.0,
        },
        {
            "tipo": ee.FURO,
            "forma": ee.CIRCULO,
            "b_mm": 60.0,
            "h_mm": None,
            "x_mm": 0.0,
            "y_mm": 0.0,
        },
    )
    resultado = calcular_caso(CASOS["secao_montada"], {"partes": partes})
    assert _metrica(resultado, "Área") == pytest.approx(math.pi / 4 * (100.0**2 - 60.0**2))
    assert _metrica(resultado, "Ix") == pytest.approx(math.pi / 64 * (100.0**4 - 60.0**4) / 1e4)


def test_cantoneira_montada_mostra_eixos_principais_girados():
    partes = (
        {
            "tipo": ee.CHEIO,
            "forma": ee.RETANGULO,
            "b_mm": 100.0,
            "h_mm": 10.0,
            "x_mm": 50.0,
            "y_mm": 5.0,
        },
        {
            "tipo": ee.CHEIO,
            "forma": ee.RETANGULO,
            "b_mm": 10.0,
            "h_mm": 90.0,
            "x_mm": 5.0,
            "y_mm": 55.0,
        },
    )
    resultado = calcular_caso(CASOS["secao_montada"], {"partes": partes})
    assert any("flexão oblíqua" in texto for texto in resultado.alertas)
    linhas = {linha["Grandeza"]: linha["Valor"] for linha in _tabela(resultado, "Propriedades")}
    # Cantoneira de abas iguais: eixo principal a 45 graus.
    assert abs(linhas["Ângulo do eixo principal"]) == pytest.approx(45.0)


def test_furo_maior_que_a_secao_vira_mensagem():
    partes = (
        {
            "tipo": ee.CHEIO,
            "forma": ee.RETANGULO,
            "b_mm": 10.0,
            "h_mm": 10.0,
            "x_mm": 0.0,
            "y_mm": 0.0,
        },
        {
            "tipo": ee.FURO,
            "forma": ee.RETANGULO,
            "b_mm": 20.0,
            "h_mm": 20.0,
            "x_mm": 0.0,
            "y_mm": 0.0,
        },
    )
    with pytest.raises(ValueError, match="furos"):
        calcular_caso(CASOS["secao_montada"], {"partes": partes})


def test_secao_montada_segue_para_viga_e_coluna():
    resultado = calcular_caso(CASOS["secao_montada"])
    assert {envio.destino for envio in resultado.envios} == {"viga_reacoes", "coluna_simples"}
    envio = resultado.envios[0]
    conta = calcular_caso(
        CASOS[envio.destino], {**envio.valores, "cargas": UNIFORME, "tipo_secao": ev.INFORMAR}
    )
    assert conta.status != "NÃO OK"


def test_kt_da_chapa_bate_com_os_extremos_do_grafico_de_peterson():
    assert ee.fator_kt_furo(0.0) == pytest.approx(3.0, abs=0.01)
    assert ee.fator_kt_furo(0.5) == pytest.approx(2.16, abs=0.01)
    assert ee.fator_kt_furo(1.0) == pytest.approx(2.0, abs=0.01)


def test_chapa_com_furo_confere_bruta_e_liquida():
    resultado = calcular_caso(
        CASOS["chapa_furo"],
        {"b_mm": 100.0, "t_mm": 10.0, "d_mm": 20.0, "n": 2, "f_kN": 100.0, "fs": 1.0},
    )
    assert _metrica(resultado, "Tensão na seção bruta") == pytest.approx(100.0)
    assert _metrica(resultado, "Tensão na seção do furo") == pytest.approx(100e3 / 600.0)
    assert _metrica(resultado, "A chapa aguenta") == pytest.approx(240.0)


def test_furos_maiores_que_a_chapa_viram_mensagem():
    with pytest.raises(ValueError, match="largura"):
        calcular_caso(CASOS["chapa_furo"], {"b_mm": 50.0, "d_mm": 20.0, "n": 3})
