"""Montador de fluidos: as fórmulas contra contas de mão e contra o ábaco de Moody."""

from __future__ import annotations

import math

import pytest

from core import montador as mt
from core import montador_blocos as mb
from core import montador_busca as bs
from core.montador_funcoes import fator_de_atrito

G = 9.81
AGUA = {"rho": 998.0, "mu": 1.002e-3, "g": G}


def montar(*itens) -> mt.Montagem:
    nos = []
    for i, item in enumerate(itens):
        tipo, opcoes = item if isinstance(item, tuple) else (item, {})
        nos.append({"id": f"n{i}", "tipo": tipo, "opcoes": opcoes})
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(
            {"de": a["id"], "saida": saida.chave, "para": b["id"], "entrada": entrada.chave}
        )
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


def perda(q: float, d: float, l: float, epsilon: float, nu: float = 1.002e-3 / 998.0) -> float:
    v = 4 * q / (math.pi * d**2)
    f = fator_de_atrito(v * d / nu, epsilon / d)
    return f * l / d * v**2 / (2 * G)


# ---------------------------------------------------------------------------
# Fator de atrito
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("re", "relativa", "moody"),
    [
        (1e5, 0.001, 0.0222),
        (1e6, 0.0001, 0.0134),
        (1e4, 0.01, 0.0431),
        (1e7, 0.00001, 0.0090),
    ],
)
def test_colebrook_bate_com_moody(re, relativa, moody):
    assert fator_de_atrito(re, relativa) == pytest.approx(moody, abs=4e-4)


def test_colebrook_fecha_a_propria_equacao():
    re, relativa = 2.5e5, 0.0007
    f = fator_de_atrito(re, relativa)
    direita = -2 * math.log10(relativa / 3.7 + 2.51 / (re * math.sqrt(f)))
    assert 1 / math.sqrt(f) == pytest.approx(direita, rel=1e-9)


def test_laminar_e_64_sobre_re():
    assert fator_de_atrito(1500.0, 0.01) == pytest.approx(64 / 1500)


def test_transicao_e_continua():
    relativa = 0.001
    assert fator_de_atrito(2300.0001, relativa) == pytest.approx(64 / 2300, rel=1e-4)
    antes = fator_de_atrito(3999.99, relativa)
    depois = fator_de_atrito(4000.0, relativa)
    assert antes == pytest.approx(depois, rel=1e-3)


# ---------------------------------------------------------------------------
# Tubulação
# ---------------------------------------------------------------------------


def test_perda_de_carga_isola_o_comprimento_em_forma_fechada():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    q, d, epsilon = 0.01, 0.1, 0.045e-3
    r = mt.isolar(m, "L", {**AGUA, "Q": q, "D": d, "varepsilon": epsilon, "H_d": 5.0})
    assert r.isoladas[0].formula is not None
    esperado = 5.0 / perda(q, d, 1.0, epsilon)
    assert r.valor == pytest.approx(esperado, rel=1e-6)
    assert r.sentido == mt.MAXIMO


def test_diametro_minimo_acha_por_numero():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    valores = {**AGUA, "Q": 0.01, "L": 100.0, "varepsilon": 0.045e-3, "H_d": 2.0}
    r = mt.isolar(m, "D", valores)
    assert r.sentido == mt.MINIMO
    assert perda(0.01, r.valor, 100.0, 0.045e-3) == pytest.approx(2.0, rel=1e-5)


def test_vazao_maxima_acha_por_numero():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    valores = {**AGUA, "D": 0.1, "L": 100.0, "varepsilon": 0.045e-3, "H_d": 2.0}
    r = mt.isolar(m, "Q", valores)
    assert r.sentido == mt.MAXIMO
    assert perda(r.valor, 0.1, 100.0, 0.045e-3) == pytest.approx(2.0, rel=1e-5)


def test_laminar_na_linha_bate_com_hagen_poiseuille():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    mu, rho, q, d, l_ = 0.04, 870.0, 1e-5, 0.02, 10.0
    valores = {"rho": rho, "mu": mu, "g": G, "Q": q, "D": d, "L": l_, "varepsilon": 1e-6}
    r = mt.isolar(m, "H_d", valores)
    esperado = 128 * mu * l_ * q / (math.pi * d**4 * rho * G)
    assert r.valor == pytest.approx(esperado, rel=1e-6)


def test_perdas_localizadas_usam_a_velocidade_do_trecho():
    m = montar("fluido", "trecho", "perda_local", "carga", mb.RESULTADO)
    q, d = 0.01, 0.1
    valores = {**AGUA, "Q": q, "D": d, "L": 50.0, "varepsilon": 0.045e-3, "K_L": 2.5}
    r = mt.isolar(m, "H_d", valores)
    v = 4 * q / (math.pi * d**2)
    assert r.valor == pytest.approx(perda(q, d, 50.0, 0.045e-3) + 2.5 * v**2 / (2 * G), rel=1e-6)


def test_perda_local_sem_trecho_diz_o_que_falta():
    m = montar("fluido", "perda_local", "carga", mb.RESULTADO)
    assert any("trecho de tubo" in erro for _, erro in m.erros)


def test_dois_trechos_em_serie_tem_letras_proprias_e_a_mesma_vazao():
    m = montar("fluido", "trecho", "trecho", "carga", mb.RESULTADO)
    chaves = {item.chave for item in m.grandezas}
    assert {"D", "D_2", "L", "L_2", "varepsilon", "varepsilon_2"} <= chaves
    assert "Q_2" not in chaves
    valores = {
        **AGUA,
        "Q": 0.01,
        "D": 0.1,
        "L": 50.0,
        "varepsilon": 0.045e-3,
        "D_2": 0.08,
        "L_2": 30.0,
        "varepsilon_2": 0.045e-3,
    }
    r = mt.isolar(m, "H_d", valores)
    esperado = perda(0.01, 0.1, 50.0, 0.045e-3) + perda(0.01, 0.08, 30.0, 0.045e-3)
    assert r.valor == pytest.approx(esperado, rel=1e-6)


def test_fluido_da_tabela_preenche_as_propriedades():
    m = montar(("fluido", {"fluido": "Água a 60 °C"}), "trecho", "carga", mb.RESULTADO)
    padroes = dict(m.padroes)
    assert padroes["rho"] == pytest.approx(983.3)
    assert padroes["mu"] == pytest.approx(4.67e-4)
    assert dict(m.origens)["rho"] == "Tabela: Água a 60 °C"


def test_material_do_tubo_preenche_a_rugosidade():
    m = montar("fluido", ("trecho", {"tubo": "PVC ou plástico"}), "carga", mb.RESULTADO)
    assert dict(m.padroes)["varepsilon"] == pytest.approx(1.5e-6)


def test_rugosidade_informada_nao_preenche():
    m = montar("fluido", ("trecho", {"tubo": "Informar a rugosidade"}), "carga", mb.RESULTADO)
    assert "varepsilon" not in dict(m.padroes)


def test_transicao_avisa_sem_tirar_a_resposta():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    # Re = 3000: V = 3000·μ/(ρ·D).
    d = 0.05
    v = 3000 * 1.002e-3 / (998.0 * d)
    q = v * math.pi * d**2 / 4
    r = mt.isolar(m, "H_d", {**AGUA, "Q": q, "D": d, "L": 10.0, "varepsilon": 1e-5})
    assert r.valor is not None
    assert any("transição" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# Bomba
# ---------------------------------------------------------------------------


def test_altura_da_bomba_soma_estatica_pressao_e_perdas():
    m = montar("fluido", "trecho", "altura_bomba", mb.RESULTADO)
    q, d = 0.01, 0.1
    valores = {
        **AGUA,
        "Q": q,
        "D": d,
        "L": 100.0,
        "varepsilon": 0.045e-3,
        "H_est": 20.0,
        "Delta_p": 1e5,
    }
    r = mt.isolar(m, "H_b", valores)
    esperado = 20.0 + 1e5 / (998.0 * G) + perda(q, d, 100.0, 0.045e-3)
    assert r.valor == pytest.approx(esperado, rel=1e-6)
    assert r.sentido == mt.MINIMO


def test_potencia_no_eixo():
    m = montar("fluido", "trecho", "potencia_bomba", mb.RESULTADO)
    q, d = 0.01, 0.1
    valores = {
        **AGUA,
        "Q": q,
        "D": d,
        "L": 100.0,
        "varepsilon": 0.045e-3,
        "H_est": 20.0,
        "Delta_p": 0.0,
        "eta": 0.7,
    }
    r = mt.isolar(m, "P_m", valores)
    esperado = 998.0 * G * q * (20.0 + perda(q, d, 100.0, 0.045e-3)) / 0.7
    assert r.valor == pytest.approx(esperado, rel=1e-6)


def test_npsh_com_bomba_acima_do_nivel():
    m = montar("fluido", "trecho", "npsh", mb.RESULTADO)
    q, d = 0.01, 0.1
    valores = {
        **AGUA,
        "p_v": 2339.0,
        "Q": q,
        "D": d,
        "L": 5.0,
        "varepsilon": 0.045e-3,
        "NPSH_r": 3.0,
        "p_atm": 101325.0,
    }
    r = mt.isolar(m, "z_s", valores)
    esperado = (101325.0 - 2339.0) / (998.0 * G) - 3.0 - perda(q, d, 5.0, 0.045e-3)
    assert r.valor == pytest.approx(esperado, rel=1e-6)
    assert r.sentido == mt.MAXIMO


def test_npsh_com_bomba_abaixo_do_nivel_soma_a_altura():
    m = montar(
        "fluido",
        "trecho",
        ("npsh", {"succao": "Bomba abaixo do nível do líquido"}),
        mb.RESULTADO,
    )
    valores = {
        **AGUA,
        "p_v": 2339.0,
        "Q": 0.01,
        "D": 0.1,
        "L": 5.0,
        "varepsilon": 0.045e-3,
        "p_atm": 101325.0,
        "z_s": 2.0,
    }
    r = mt.isolar(m, "NPSH_r", valores)
    esperado = (101325.0 - 2339.0) / (998.0 * G) + 2.0 - perda(0.01, 0.1, 5.0, 0.045e-3)
    assert r.valor == pytest.approx(esperado, rel=1e-6)


def test_velocidade_maxima_da_diametro_em_forma_fechada():
    m = montar("fluido", "trecho", "velocidade", mb.RESULTADO)
    r = mt.isolar(m, "D", {**AGUA, "Q": 0.01, "L": 10.0, "varepsilon": 1e-4, "V_adm": 2.0})
    assert r.valor == pytest.approx(math.sqrt(4 * 0.01 / (math.pi * 2.0)))
    assert r.sentido == mt.MINIMO


# ---------------------------------------------------------------------------
# Equações
# ---------------------------------------------------------------------------


def test_pressao_na_profundidade():
    m = montar("fluido", "coluna", mb.RESULTADO)
    r = mt.isolar(m, "p_h", {"rho": 1000.0, "g": G, "p_0": 101325.0, "h": 10.0})
    assert r.valor == pytest.approx(101325.0 + 1000.0 * G * 10.0)
    assert r.sentido == mt.IGUAL


def test_profundidade_isola_em_forma_fechada():
    m = montar("fluido", "coluna", mb.RESULTADO)
    r = mt.isolar(m, "h", {"rho": 1000.0, "g": G, "p_0": 0.0, "p_h": 98100.0})
    assert r.valor == pytest.approx(10.0)


def test_forca_em_superficie_plana():
    m = montar("fluido", "forca_plana", mb.RESULTADO)
    r = mt.isolar(m, "F_R", {"rho": 1000.0, "g": G, "h_c": 2.0, "A": 3.0})
    assert r.valor == pytest.approx(1000.0 * G * 2.0 * 3.0)


def test_empuxo():
    m = montar("fluido", "empuxo", mb.RESULTADO)
    r = mt.isolar(m, "V_d", {"rho": 1000.0, "g": G, "F_e": 981.0})
    assert r.valor == pytest.approx(0.1)


def test_arrasto_isola_a_velocidade():
    m = montar("fluido", "arrasto", mb.RESULTADO)
    r = mt.isolar(m, "V_r", {"rho": 1.2, "C_D": 0.47, "A_f": 0.5, "F_D": 100.0})
    assert r.valor == pytest.approx(math.sqrt(2 * 100.0 / (0.47 * 1.2 * 0.5)))


def test_medidor_de_orificio():
    m = montar("fluido", "medidor", mb.RESULTADO)
    valores = {"rho": 1000.0, "C_d": 0.6, "D_o": 0.05, "D": 0.1, "Delta_p": 2e4}
    r = mt.isolar(m, "Q", valores)
    beta = 0.5
    area = math.pi * 0.05**2 / 4
    assert r.valor == pytest.approx(
        0.6 * area * math.sqrt(2 * 2e4 / 1000.0) / math.sqrt(1 - beta**4)
    )


def test_medidor_isola_a_queda_de_pressao():
    m = montar("fluido", "medidor", mb.RESULTADO)
    valores = {"rho": 1000.0, "C_d": 0.6, "D_o": 0.05, "D": 0.1, "Q": 0.005}
    r = mt.isolar(m, "Delta_p", valores)
    volta = {**valores}
    volta.pop("Q")
    q = mt.isolar(m, "Q", {**volta, "Delta_p": r.valor}).valor
    assert q == pytest.approx(0.005, rel=1e-6)


def test_manning_vazao():
    m = montar("manning", mb.RESULTADO)
    valores = {"n_m": 0.013, "b_c": 2.0, "y_c": 1.0, "S_0": 0.001}
    r = mt.isolar(m, "Q", valores)
    area, raio = 2.0, 2.0 / 4.0
    assert r.valor == pytest.approx(area * raio ** (2 / 3) * math.sqrt(0.001) / 0.013)


def test_manning_acha_a_lamina_por_numero():
    m = montar("manning", mb.RESULTADO)
    valores = {"n_m": 0.013, "b_c": 2.0, "S_0": 0.001, "Q": 3.0}
    y = mt.isolar(m, "y_c", valores).valor
    q = mt.isolar(m, "Q", {"n_m": 0.013, "b_c": 2.0, "S_0": 0.001, "y_c": y}).valor
    assert q == pytest.approx(3.0, rel=1e-6)


def test_golpe_de_ariete():
    m = montar("fluido", "golpe", mb.RESULTADO)
    r = mt.isolar(m, "Delta_p_g", {"rho": 998.0, "a_c": 1000.0, "Delta_V": 2.0})
    assert r.valor == pytest.approx(998.0 * 1000.0 * 2.0)


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------


def test_busca_pelo_menor_diametro_com_comprimento_em_aberto():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    b = bs.procurar(
        m,
        [bs.Faixa("D", 0.02, 0.5, 0.01)],
        bs.Objetivo("Menor D", bs.MENOR, "D"),
        {**AGUA, "Q": 0.01, "L": 100.0, "varepsilon": 0.045e-3, "H_d": 2.0},
    )
    direto = mt.isolar(m, "D", {**AGUA, "Q": 0.01, "L": 100.0, "varepsilon": 0.045e-3, "H_d": 2.0})
    assert b.convergido.valor("D") == pytest.approx(direto.valor, rel=1e-5)


def test_equacao_so_aceita_todas_no_limite():
    m = montar("fluido", "empuxo", mb.RESULTADO)
    assert [o.tipo for o in bs.objetivos(m, ["V_d"])] == [bs.NO_LIMITE]


def test_catalogos_separados():
    fluidos = {b["chave"] for b in mb.catalogo_para_tela(mb.FLUIDOS)}
    solidos = {b["chave"] for b in mb.catalogo_para_tela(mb.SOLIDOS)}
    assert "trecho" in fluidos and "trecho" not in solidos
    assert "von_mises" in solidos and "von_mises" not in fluidos
    assert mb.RESULTADO in fluidos and mb.RESULTADO in solidos
