"""Peças do eixo no Montador: engrenagem, polia, vigas novas, chaveta, cubo, rolamento, rigidez,
eixo com trechos e o que mais pesa na resposta.

As contas são conferidas contra o Assistente de cargas, que tem as mesmas peças escritas em
número, contra fórmulas fechadas conhecidas e contra o próprio eixo com trechos, que integra a
viga por outro caminho.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from components import montador_eixo_ui as eixo_ui
from core import desenho_do_eixo as de
from core import elementos_eixos as ee
from core import elementos_transmissao as et
from core import montador as mt
from core import montador_aceite as ma
from core import montador_blocos as mb
from core import montador_eixo as me
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_pecas as mpe
from core import montador_sensibilidade as ms
from core.montador_modelos import Modelo

R = mb.RESULTADO
APP = str(Path(__file__).resolve().parents[1] / "app.py")
SOLIDOS = mm.PARTE_SOLIDOS
_NOVOS = (
    "engrenagem",
    "polia",
    "chaveta",
    "cubo_prensado",
    "rolamento",
    "inclinacao",
    "rotacao_critica",
    me.TIPO,
    "biapoiada_fora",
    "biapoiada_duas",
    "biapoiada_balanco",
    "engastada_apoiada_meio",
    "engastada_apoiada_distribuida",
)


def _resolver(
    tipos: tuple[str, ...],
    alvo: str,
    valores: dict,
    extras: tuple = (),
    fios: tuple = (),
    opcoes: dict | None = None,
) -> mt.Resposta:
    modelo = Modelo("caso", "", alvo, valores, tipos, extras, fios, opcoes or {})
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    completos = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **valores,
    }
    return mt.isolar(base, alvo, completos)


def _saida(tipo: str, porta: str, valores: dict, opcoes: dict | None = None) -> float:
    dados = {"nos": [{"id": "b", "tipo": tipo, "opcoes": opcoes or {}}], "fios": []}
    base = mt.montar(mt.grafo_de_dados(dados))
    numeros = {sp.Symbol(k, positive=True): sp.Float(v) for k, v in valores.items()}
    return float(base.saidas["b"][porta].subs(numeros))


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chave", _NOVOS)
def test_bloco_novo_tem_ajuda_e_opcoes_validas(chave):
    bloco = mb.POR_CHAVE[chave]
    assert bloco.nome and bloco.dica and bloco.formula
    assert bloco.grupo in mb.GRUPOS
    for opcao in bloco.opcoes:
        assert opcao.padrao in opcao.lista(), opcao.chave
        assert opcao.ajuda.endswith((".", "!", ":"))


def test_biblioteca_mostra_as_pecas_do_eixo():
    grupos = {item["grupo"] for item in mb.catalogo_para_tela(mb.SOLIDOS)}
    assert mb.GRUPO_PECAS in grupos
    nomes = {item["nome"] for item in mb.catalogo_para_tela(mb.SOLIDOS)}
    assert {"Engrenagem", "Chaveta", "Rolamento", "Eixo com trechos"} <= nomes
    assert "Chaveta" not in {item["nome"] for item in mb.catalogo_para_tela(mb.FLUIDOS)}


def test_vigas_antigas_ganharam_entrada_de_forca_e_reacao():
    entradas, saidas = mb.portas_de("biapoiada_central", {})
    assert [p.chave for p in entradas] == ["F"]
    assert {"R", "giro"} <= {p.chave for p in saidas}


# ---------------------------------------------------------------------------
# Engrenagem e polia
# ---------------------------------------------------------------------------


def test_engrenagem_bate_com_o_assistente():
    caso = ma._ENGRENAGEM_DO_CASO
    resultado = et.calcular_engrenagem(caso)
    primitivo = 3.0 * 20 / math.cos(math.radians(15.0))
    valores = {
        "P": 15e6,
        "n_rot": 1450.0,
        "d_g": primitivo,
        "phi_n": math.radians(20.0),
        "psi": math.radians(15.0),
    }
    for porta, rotulo in (
        ("F_t", "Força tangencial F_t"),
        ("F_r", "Força radial F_r"),
        ("F_a", "Força axial F_a"),
    ):
        esperado = ma._metrica(resultado, rotulo) * 1000.0
        assert _saida("engrenagem", porta, valores) == pytest.approx(esperado, rel=1e-12)


def test_engrenagem_reta_nao_tem_axial():
    valores = {"P": 15e6, "n_rot": 1450.0, "d_g": 80.0, "phi_n": math.radians(20.0), "psi": 0.0}
    assert _saida("engrenagem", "F_a", valores) == 0.0
    torque = 15e6 * 30 / (math.pi * 1450.0)
    assert _saida("engrenagem", "F_t", valores) == pytest.approx(2 * torque / 80.0)


def test_polia_bate_com_a_correia_do_assistente():
    valores_assistente = {
        "tipo": "Em V",
        "potencia_kW": 7.5,
        "fator_servico": 1.0,
        "rotacao_rpm": 1750.0,
        "d_mm": 120.0,
        "D_mm": 120.0,
        "C_mm": 400.0,
        "atrito": 0.3,
        "massa_kg_m": 0.0,
        "correias": 1,
        "angulo_ranhura": 38.0,
        "pretensao_kN": 0.0,
    }
    esperado = ma._metrica(et.calcular_correia(valores_assistente), "Carga no eixo") * 1000.0
    valores = {"P": 7.5e6, "n_rot": 1750.0, "d_pol": 120.0, "mu_c": 0.3, "theta_c": math.pi}
    assert _saida("polia", "F", valores) == pytest.approx(esperado, rel=1e-9)


# ---------------------------------------------------------------------------
# Vigas novas, contra a integração do eixo com trechos
# ---------------------------------------------------------------------------


def _viga_unitaria(vao: float, posicao: float, binario: bool = False) -> me.Unitaria:
    pontos = np.array(sorted({0.0, vao, posicao, *(vao * i / 400 for i in range(401))}))
    return me._viga(pontos, np.ones(len(pontos) - 1), 0.0, vao, posicao, binario)


def test_carga_fora_do_meio_bate_com_a_integracao():
    f, a, vao = 1.0, 250.0, 1000.0
    valores = {"F": f, "a_m": a, "L": vao}
    unitaria = _viga_unitaria(vao, a)
    momento = max(abs(x) for x in unitaria.direita)
    assert _saida("biapoiada_fora", "M", valores) == pytest.approx(momento, rel=1e-9)
    assert _saida("biapoiada_fora", "R", valores) == pytest.approx(abs(unitaria.reacao_a), rel=1e-9)
    # Na integração, M/(E·I) com E·I = 1: a flecha e o giro saem já vezes E·I.
    assert _saida("biapoiada_fora", "flecha", valores) == pytest.approx(
        max(abs(y) for y in unitaria.flecha), rel=1e-4
    )
    assert _saida("biapoiada_fora", "giro", valores) == pytest.approx(
        abs(unitaria.giro[0]), rel=1e-9
    )
    nos = np.array(sorted({0.0, vao, a, *(vao * k / 400 for k in range(401))}))
    i = int(np.searchsorted(nos, a))
    assert _saida("biapoiada_fora", "giro_carga", valores) == pytest.approx(
        abs(unitaria.giro[i]), rel=1e-9
    )


def test_carga_no_meio_vira_o_caso_de_sempre():
    valores = {"F": 1000.0, "a_m": 500.0, "L": 1000.0}
    assert _saida("biapoiada_fora", "M", valores) == pytest.approx(1000.0 * 1000.0 / 4)
    assert _saida("biapoiada_fora", "flecha", valores) == pytest.approx(1000.0 * 1000.0**3 / 48)
    assert _saida("biapoiada_fora", "giro_carga", valores) == pytest.approx(0.0, abs=1e-9)


def test_carga_do_lado_errado_avisa():
    resposta = _resolver(
        ("circular", "flexao", "von_mises", R),
        "d",
        {"F": 1e4, "a_m": 700.0, "L": 1000.0, "S_y": 250.0, "n": 2.0},
        (("v", "biapoiada_fora"),),
        (("v", "M", "n2", "valor"),),
    )
    assert any("L/2" in a for a in resposta.alertas)


def test_duas_cargas_fecham_o_equilibrio():
    valores = {"F_1": 1000.0, "F_2": 2000.0, "a_1": 200.0, "a_2": 700.0, "L": 1000.0}
    ra = _saida("biapoiada_duas", "R_A", valores)
    rb = _saida("biapoiada_duas", "R_B", valores)
    assert ra + rb == pytest.approx(3000.0)
    assert _saida("biapoiada_duas", "M", valores) == pytest.approx(ra * 200.0)
    sob_f2 = _saida("biapoiada_duas", "M", valores, {"secao": mb.SOB_F2})
    assert sob_f2 == pytest.approx(rb * 300.0)


def test_balanco_bate_com_a_integracao():
    vao, balanco = 600.0, 150.0
    nos = np.array(
        sorted({0.0, vao, vao + balanco, *(i * (vao + balanco) / 600 for i in range(601))})
    )
    unitaria = me._viga(nos, np.ones(len(nos) - 1), 0.0, vao, vao + balanco, False)
    valores = {"F": 1.0, "c_b": balanco, "L": vao}
    assert _saida("biapoiada_balanco", "R", valores) == pytest.approx(
        abs(unitaria.reacao_b), rel=1e-9
    )
    assert _saida("biapoiada_balanco", "flecha", valores) == pytest.approx(
        abs(unitaria.flecha[-1]), rel=1e-9
    )
    assert _saida("biapoiada_balanco", "giro_carga", valores) == pytest.approx(
        abs(unitaria.giro[-1]), rel=1e-9
    )
    i = int(np.searchsorted(nos, vao))
    assert _saida("biapoiada_balanco", "giro", valores) == pytest.approx(
        abs(unitaria.giro[i]), rel=1e-9
    )


def test_engastada_e_apoiada_tem_os_coeficientes_das_tabelas():
    assert _saida("engastada_apoiada_meio", "M", {"F": 16.0, "L": 1.0}) == pytest.approx(3.0)
    assert _saida("engastada_apoiada_meio", "flecha", {"F": 1.0, "L": 1.0}) == pytest.approx(
        0.009317, rel=1e-3
    )
    assert _saida("engastada_apoiada_distribuida", "flecha", {"q": 1.0, "L": 1.0}) == pytest.approx(
        1 / 185, rel=2e-3
    )
    assert _saida("engastada_apoiada_distribuida", "R", {"q": 8.0, "L": 1.0}) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Chaveta, cubo prensado e rolamento
# ---------------------------------------------------------------------------


def test_casos_de_aceite_das_pecas_passam():
    for caso in ma.casos():
        if caso.modulo == ma._PECAS:
            assert caso.calcular() == pytest.approx(caso.esperado, rel=caso.tolerancia), caso.caso


def test_chaveta_informada_confere_os_dois_lados():
    resposta = _resolver(
        ("chaveta", R),
        "L_ch",
        {
            "T": 600e3,
            "d": 50.0,
            "b_ch": 14.0,
            "h_ch": 9.0,
            "t_1": 5.5,
            "S_y_ch": 350.0,
            "S_y": 420.0,
            "S_y_cubo": 310.0,
            "n": 2.0,
            "K_s": 1.25,
        },
        opcoes={"n1": {"dimensoes": mpe.CHAVETA_INFORMADA}},
    )
    nomes = {i.condicao.nome for i in resposta.isoladas}
    assert {
        "Esmagamento da chaveta do lado do eixo",
        "Esmagamento da chaveta do lado do cubo",
    } <= nomes
    # A mesma chaveta da DIN para d = 50: o mesmo comprimento.
    assert resposta.valor == pytest.approx(ma._chaveta_no_montador(), rel=1e-9)


def test_chaveta_comprida_demais_avisa():
    resposta = _resolver(
        ("chaveta", R),
        "T",
        {"L_ch": 120.0, "d": 40.0, "S_y_ch": 350.0, "S_y": 420.0, "S_y_cubo": 310.0, "n": 2.0},
    )
    assert any("1,5·d" in a for a in resposta.alertas)


def test_ajuste_solto_pela_rugosidade_avisa():
    resposta = _resolver(
        ("cubo_prensado", R),
        "T",
        {
            "d": 50.0,
            "D_cubo": 90.0,
            "L_aj": 50.0,
            "E": 200000.0,
            "S_y": 420.0,
            "S_y_cubo": 300.0,
            "n": 1.5,
            "F_ac": 0.0,
            "Rz_e": 0.02,
            "Rz_cubo": 0.02,
        },
        opcoes={"n1": {"ajuste": "H7/p6 (leve, com prensa)"}},
    )
    assert resposta.valor is None or any("solto" in a for a in resposta.alertas)


def test_rolamento_de_rolos_usa_10_tercos():
    valores = {
        "F_rm": 8000.0,
        "F_am": 0.0,
        "n_rot": 500.0,
        "C_0": 60000.0,
        "L_h": 30000 * 3600.0,
        "f_ap": 1.0,
        "X_r": 1.0,
        "Y_r": 0.0,
    }
    resposta = _resolver(
        ("rolamento", R), "C_din", valores, opcoes={"n1": {"tipo": mpe.ROLOS_INFORMADOS}}
    )
    voltas = 500.0 * 30000 * 60 / 1e6
    assert resposta.valor == pytest.approx(8000.0 * voltas ** (3 / 10), rel=1e-9)


def test_rolamento_soma_os_dois_planos():
    resposta = _resolver(
        ("rolamento", R),
        "C_din",
        {
            "F": 3000.0,
            "F_2": 3000.0,  # o segundo bloco de viga numera a força
            "a_m": 100.0,
            "L": 300.0,
            "n_rot": 1000.0,
            "C_0": 30000.0,
            "F_am": 0.0,
        },
        (("v1", "biapoiada_fora"), ("v2", "biapoiada_fora")),
        (("v1", "R", "n1", "R"), ("v2", "R", "n1", "R_2")),
    )
    so_um = _resolver(
        ("rolamento", R),
        "C_din",
        {
            "F_rm": math.sqrt(2) * 3000.0 * 200 / 300,
            "n_rot": 1000.0,
            "C_0": 30000.0,
            "F_am": 0.0,
        },
    )
    assert resposta.valor == pytest.approx(so_um.valor, rel=1e-9)


# ---------------------------------------------------------------------------
# Rigidez
# ---------------------------------------------------------------------------


def test_rotacao_critica_do_eixo_liso_e_a_exata():
    d, vao = 40.0, 800.0
    area, inercia = math.pi * d**2 / 4, math.pi * d**4 / 64
    exata = (math.pi / vao) ** 2 * math.sqrt(200000.0 * inercia / (7850e-12 * area)) * 30 / math.pi
    resposta = _resolver(
        ("circular", "rotacao_critica", R), "n_rot", {"d": d, "L": vao, "E": 200000.0, "f_cr": 1.0}
    )
    assert resposta.valor == pytest.approx(exata, rel=1e-9)


def test_peca_no_eixo_baixa_a_rotacao_critica():
    comum = {"d": 40.0, "L": 800.0, "E": 200000.0, "f_cr": 1.0}
    sozinho = _resolver(("circular", "rotacao_critica", R), "n_rot", comum).valor
    com_peca = _resolver(
        ("circular", "rotacao_critica", R),
        "n_rot",
        {**comum, "m_p": 0.02, "a_m": 400.0},
        opcoes={"n2": {"massas": mpe.PECA_ENTRE_MANCAIS}},
    ).valor
    assert com_peca < sozinho


def test_inclinacao_de_dois_planos_soma_como_vetor():
    valores = {"F": 2000.0, "F_2": 2000.0, "a_m": 100.0, "L": 300.0, "E": 200000.0}
    um = _resolver(
        ("circular", "inclinacao", R),
        "d",
        valores,
        (("v1", "biapoiada_fora"),),
        (("v1", "giro", "n2", "giro"),),
    ).valor
    dois = _resolver(
        ("circular", "inclinacao", R),
        "d",
        valores,
        (("v1", "biapoiada_fora"), ("v2", "biapoiada_fora")),
        (("v1", "giro", "n2", "giro"), ("v2", "giro", "n2", "giro_2")),
    ).valor
    # θ ∝ 1/d⁴: com o dobro de giro em módulo vetorial (√2), d cresce √2^(1/4).
    assert dois == pytest.approx(um * 2 ** (1 / 8), rel=1e-6)


# ---------------------------------------------------------------------------
# Eixo com trechos
# ---------------------------------------------------------------------------


def _eixo(opcoes: dict) -> mt.Montagem:
    dados = {
        "nos": [
            {"id": "e", "tipo": me.TIPO, "opcoes": opcoes},
            {"id": "r", "tipo": R, "opcoes": {}},
        ],
        "fios": [{"de": "e", "saida": "condicao", "para": "r", "entrada": "condicoes"}],
    }
    return mt.montar(mt.grafo_de_dados(dados))


def test_eixo_de_um_diametro_bate_com_o_assistente():
    d = ma._valor(ma._eixo_de_um_diametro(mancal_a=me.NAO_CONFERIR, mancal_b=me.NAO_CONFERIR))
    assert d == pytest.approx(ma._goodman_do_assistente(), rel=1e-6)


def test_secoes_numeradas_sem_buraco_e_sem_repetir():
    base = _eixo({})
    rotulos = [c.secao.rotulo for c in base.saidas["e"]["secoes"]]
    assert rotulos == [f"S{k}" for k in range(1, len(rotulos) + 1)]
    nomes = [c.nome for c in base.condicoes]
    assert len(nomes) == len(set(nomes))
    # Os ombros do lado fino e o rasgo da engrenagem, dos dois lados dela.
    entalhes = [c.secao.entalhe for c in base.saidas["e"]["secoes"]]
    assert entalhes.count(ee.ENTALHE_RESSALTO) >= 4
    assert entalhes.count(ee.ENTALHE_CHAVETA) >= 2


def test_bolinhas_seguem_a_tabela():
    elementos = [dict(x) for x in me.ELEMENTOS_PADRAO]
    elementos[1] = {**elementos[1], "axial": True, "raio": 40.0}
    entradas, saidas = mb.portas_de(me.TIPO, {"elementos": json.dumps(elementos)})
    assert [p.chave for p in entradas] == ["material", "v1", "h1", "t1", "a1"]
    assert {p.chave for p in saidas} == {"condicao", "R_A", "R_B"}


def test_tabela_com_problema_vira_erro_do_bloco():
    elementos = [x for x in me.ELEMENTOS_PADRAO if x["funcao"] != me.MANCAL_B]
    base = _eixo({"elementos": json.dumps(elementos)})
    assert "mancal b" in dict(base.erros)["e"]


def test_axial_entra_no_trecho_ate_o_mancal_que_segura():
    elementos = [dict(x) for x in me.ELEMENTOS_PADRAO]
    elementos[1] = {**elementos[1], "axial": True, "raio": 40.0}
    base = _eixo({"elementos": json.dumps(elementos)})
    normais = [c for c in base.saidas["e"]["secoes"] if c.normal != 0]
    # Encosto no mancal A (x = 15): só as seções entre ele e a engrenagem (x = 60) levam o normal.
    assert normais and all(15.0 <= c.secao.x <= 60.0 for c in normais)


def test_torque_que_entra_no_meio_vai_para_os_dois_lados():
    trechos = [{"nome": "Eixo", "comprimento": 400.0, "relacao": 1.0, "entalhe": me.LISO}]
    elementos = [
        {"nome": "Mancal A", "x": 20.0, "funcao": me.MANCAL_A},
        {"nome": "Esquerda", "x": 100.0, "funcao": me.CARGA, "torque": me.SAI},
        {"nome": "Motor", "x": 200.0, "funcao": me.CARGA, "torque": me.ENTRA},
        {"nome": "Direita", "x": 300.0, "funcao": me.CARGA, "torque": me.SAI},
        {"nome": "Mancal B", "x": 380.0, "funcao": me.MANCAL_B},
    ]
    base = _eixo(
        {
            "trechos": json.dumps(trechos),
            "elementos": json.dumps(elementos),
            "critica": me.NAO_CONFERIR,
        }
    )
    t1, t2 = sp.Symbol("T_e1", positive=True), sp.Symbol("T_e3", positive=True)
    torques = {c.torque for c in base.saidas["e"]["secoes"]}
    assert {t1, t2} <= torques
    assert t1 + t2 not in torques  # nenhuma seção leva os dois


def test_rotacao_critica_do_eixo_liso_fica_logo_abaixo_da_exata():
    trechos = [{"nome": "Eixo", "comprimento": 800.0, "relacao": 1.0, "entalhe": me.LISO}]
    elementos = [
        {"nome": "Mancal A", "x": 0.0, "funcao": me.MANCAL_A},
        {"nome": "Peso", "x": 400.0, "funcao": me.CARGA, "vertical": me.MAIS},
        {"nome": "Mancal B", "x": 800.0, "funcao": me.MANCAL_B},
    ]
    base = _eixo({"trechos": json.dumps(trechos), "elementos": json.dumps(elementos)})
    critica = next(c for c in base.condicoes if c.criterio == "Rotação crítica")
    d = 40.0
    numeros = {
        sp.Symbol("d", positive=True): d,
        sp.Symbol("E", positive=True): 200000.0,
        sp.Symbol("rho_e", positive=True): 7850e-12,
    }
    area, inercia = math.pi * d**2 / 4, math.pi * d**4 / 64
    exata = (
        (math.pi / 800.0) ** 2 * math.sqrt(200000.0 * inercia / (7850e-12 * area)) * 30 / math.pi
    )
    dunkerley = float(critica.direita.subs(numeros))
    # Dunkerley no eixo contínuo: √(90/π⁴) da exata, cerca de 4 % abaixo, a favor.
    assert dunkerley == pytest.approx(exata * math.sqrt(90 / math.pi**4), rel=5e-3)


def test_desenho_do_eixo_sai_com_a_secao_que_manda():
    base = _eixo({})
    secoes = [c.secao for c in base.saidas["e"]["secoes"]]
    figura = de.desenhar_eixo(me.ler_arranjo({}), secoes, d=30.0, manda="S3")
    assert figura.png.startswith(b"\x89PNG")


def test_tabela_editada_volta_para_o_bloco_e_tira_o_fio_que_sobrou():
    modelo = mm.POR_NOME["Eixo com trechos"]
    dados = modelo.grafo()
    u = g.unidades_padrao(g.SISTEMA_SOLIDOS)
    estado: dict = {
        SOLIDOS.k("grafo"): dados,
        SOLIDOS.k("unidades"): tuple(s.padrao for s in g.SISTEMA_SOLIDOS.seletores),
        SOLIDOS.k("versao"): 3,
    }
    # Tira a força horizontal da engrenagem: a bolinha h1 some, e o fio de F_t junto.
    estado["tabela"] = {"edited_rows": {1: {"Força horizontal": me.NENHUMA}}}
    with mock.patch.object(eixo_ui.st, "session_state", estado):
        eixo_ui._ao_editar(SOLIDOS, "n1", "tabela", "elementos")
    no = next(n for n in estado[SOLIDOS.k("grafo")]["nos"] if n["id"] == "n1")
    assert json.loads(no["opcoes"]["elementos"])[1]["horizontal"] == me.NENHUMA
    assert "h1" not in {p["chave"] for p in no["portas"]["entradas"]}
    assert not any(f["entrada"] == "h1" for f in estado[SOLIDOS.k("grafo")]["fios"])
    assert estado[SOLIDOS.k("versao")] == 4
    # Na unidade da tela: o comprimento padrão é em metros, e volta em milímetros.
    linhas = eixo_ui._linhas_dos_trechos(me.ler_arranjo({}), u)
    assert eixo_ui._trechos_guardados(linhas, u)[0]["comprimento"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# O que mais pesa
# ---------------------------------------------------------------------------


def test_o_que_mais_pesa_segue_o_expoente_da_formula():
    modelo = mm.MODELOS[0]  # h de uma seção retangular: h ∝ √M
    resposta = _resolver(modelo.tipos, modelo.alvo, dict(modelo.valores))
    pesos = {p.grandeza.chave: p for p in ms.pesos(resposta)}
    assert pesos["M_x"].sobe == pytest.approx(math.sqrt(1.1) - 1, rel=1e-6)
    assert pesos["M_x"].desce == pytest.approx(math.sqrt(0.9) - 1, rel=1e-6)
    assert pesos["V_y"].quase_nada  # a linha neutra não manda


def test_o_que_mais_pesa_avisa_quando_outra_condicao_passa_a_mandar():
    # Tensão e flecha quase empatadas: 10 % a mais de força troca quem manda.
    valores = {"b": 50.0, "F": 1e4, "L": 3000.0, "S_y": 250.0, "n": 1.5, "r_delta": 300.0}
    resposta = _resolver(
        ("retangular", "flexao", "cortante", "von_mises", R),
        "h",
        valores,
        (("n6", "biapoiada_central"), ("n7", "flecha")),
        (
            ("n6", "M", "n2", "valor"),
            ("n6", "V", "n3", "valor"),
            ("n1", "saida", "n7", "entrada"),
            ("n6", "flecha", "n7", "flecha"),
            ("n7", "condicao", "n5", "condicoes"),
        ),
    )
    assert resposta.manda.condicao.nome == "Flecha"
    pesos = {p.grandeza.chave: p for p in ms.pesos(resposta)}
    # A flecha não depende de S_y: baixar S_y 10 % não muda nada, e subir também não.
    assert pesos["S_y"].quase_nada
    assert pesos["E"].sobe == pytest.approx(1.1 ** (-1 / 3) - 1, rel=1e-6)


def test_o_que_mais_pesa_fica_vazio_sem_numero():
    modelo = mm.MODELOS[0]
    resposta = _resolver(modelo.tipos, modelo.alvo, {"b": 50.0})
    assert ms.pesos(resposta) == []


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    assert not at.exception
    return at


def test_tela_do_eixo_com_trechos_mostra_tabelas_e_o_que_mais_pesa():
    at = _abrir()
    at.selectbox(key=SOLIDOS.k("modelo")).set_value("Eixo com trechos").run()
    assert not at.exception
    htmls = " ".join(str(h.proto.body) for h in at.get("html"))
    assert "Eixo com trechos" in htmls
    assert "O que mais pesa" in htmls
    textos = " ".join(m.value for m in at.markdown)
    assert "Trechos, da esquerda para a direita" in textos
    assert "Pesa mais" in textos


@pytest.mark.parametrize(
    "nome",
    [
        "Eixo com engrenagem",
        "Rigidez do eixo",
        "Polia em balanço",
        "Chaveta: comprimento mínimo",
        "Cubo prensado: comprimento do ajuste",
        "Rolamento: capacidade C",
    ],
)
def test_modelos_novos_abrem_com_resposta(nome):
    at = _abrir()
    at.selectbox(key=SOLIDOS.k("modelo")).set_value(nome).run()
    assert not at.exception
    assert at.success, nome  # a resposta em verde
