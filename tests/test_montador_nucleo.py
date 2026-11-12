"""O núcleo do Montador: unidades pelo SI, temperatura, sinal, letras do meio, laços e CoolProp."""

from __future__ import annotations

import math

import numpy as np
import pytest
import sympy as sp

from core import montador as mt
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_propriedades as mp
from core import montador_registro as rg
from core import montador_sensibilidade as msen
from core import montador_sistema as sm
from core import montador_word as mw

SOLIDOS, FLUIDOS = g.SISTEMA_SOLIDOS, g.SISTEMA_FLUIDOS

# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

#: Quanto vale no SI cada unidade da tela. Tabela independente do programa: se um fator ou a base de
#: um sistema estiver errado, a conta entre as partes sai errada, e é aqui que aparece.
VALOR_NO_SI = {
    (SOLIDOS, g.MEDIDA, "mm"): 1e-3,
    (SOLIDOS, g.MEDIDA, "cm"): 1e-2,
    (SOLIDOS, g.MEDIDA, "m"): 1.0,
    (SOLIDOS, g.COMPRIMENTO, "m"): 1.0,
    (SOLIDOS, g.FORCA, "N"): 1.0,
    (SOLIDOS, g.FORCA, "kN"): 1e3,
    (SOLIDOS, g.MOMENTO, "N·mm"): 1e-3,
    (SOLIDOS, g.MOMENTO, "N·m"): 1.0,
    (SOLIDOS, g.MOMENTO, "kN·m"): 1e3,
    (SOLIDOS, g.TENSAO, "MPa"): 1e6,
    (SOLIDOS, g.MODULO, "GPa"): 1e9,
    (SOLIDOS, g.POTENCIA, "kW"): 1e3,
    (SOLIDOS, g.ROTACAO, "rpm"): 2.0 * math.pi / 60.0,
    (SOLIDOS, g.ANGULO, "°"): math.pi / 180.0,
    (SOLIDOS, g.AREA, "mm²"): 1e-6,
    (SOLIDOS, g.VOLUME, "mm³"): 1e-9,
    (SOLIDOS, g.INERCIA, "mm⁴"): 1e-12,
    (SOLIDOS, g.MASSA, "kg"): 1.0,
    (SOLIDOS, g.MASSA_ESPECIFICA, "kg/m³"): 1.0,
    (SOLIDOS, g.MICRO, "µm"): 1e-6,
    (SOLIDOS, g.TEMPO, "h"): 3600.0,
    (FLUIDOS, g.DIAMETRO, "mm"): 1e-3,
    (FLUIDOS, g.DIAMETRO, "pol"): 0.0254,
    (FLUIDOS, g.COMPRIMENTO, "km"): 1e3,
    (FLUIDOS, g.VAZAO, "m³/h"): 1.0 / 3600.0,
    (FLUIDOS, g.VAZAO, "L/s"): 1e-3,
    (FLUIDOS, g.PRESSAO, "kPa"): 1e3,
    (FLUIDOS, g.PRESSAO, "bar"): 1e5,
    (FLUIDOS, g.PRESSAO, "mca"): 9806.65,
    (FLUIDOS, g.POTENCIA, "cv"): 735.49875,
    (FLUIDOS, g.VISCOSIDADE, "mPa·s"): 1e-3,
    (FLUIDOS, g.RUGOSIDADE, "mm"): 1e-3,
    (FLUIDOS, g.CURVA_BOMBA, "m/(m³/h)²"): 3600.0**2,
    (FLUIDOS, g.TEMPERATURA, "K"): 1.0,
    (FLUIDOS, g.TEMPERATURA, "°C"): 1.0,
    (FLUIDOS, g.TEMPERATURA, "°F"): 5.0 / 9.0,
}


def _fator_da_tela(sistema: g.Sistema, dimensao: str, rotulo: str) -> float:
    for seletor in sistema.seletores:
        if seletor.dimensao == dimensao:
            return seletor.opcoes[rotulo]
    fixa = sistema.fixas[dimensao]
    assert fixa[0] == rotulo
    return fixa[1]


@pytest.mark.parametrize(
    ("sistema", "dimensao", "rotulo"), list(VALOR_NO_SI), ids=lambda x: getattr(x, "chave", x)
)
def test_cada_unidade_vale_o_que_diz_no_si(sistema, dimensao, rotulo):
    no_si = _fator_da_tela(sistema, dimensao, rotulo) * sistema.fator_si(dimensao)
    assert no_si == pytest.approx(VALOR_NO_SI[(sistema, dimensao, rotulo)], rel=1e-12)


def test_toda_dimensao_tem_quatro_potencias_e_nome():
    for dimensao, potencias in g.EXPOENTES.items():
        assert len(potencias) == 4, dimensao
        assert dimensao in g.ROTULOS_DAS_DIMENSOES, dimensao


def test_temperatura_soma_o_deslocamento_e_a_diferenca_nao():
    u = g.unidades_padrao(FLUIDOS)
    assert u.rotulo(g.TEMPERATURA) == "°C"
    assert u.para_base(g.TEMPERATURA, 20.0) == pytest.approx(293.15)
    assert u.da_base(g.TEMPERATURA, 373.15) == pytest.approx(100.0)
    f = g.Unidades(FLUIDOS, (*u.escolhas[:-1], "°F"))
    assert f.para_base(g.TEMPERATURA, 32.0) == pytest.approx(273.15)
    assert f.para_base(g.TEMPERATURA, 212.0) == pytest.approx(373.15)
    assert f.da_base(g.TEMPERATURA, f.para_base(g.TEMPERATURA, 77.0)) == pytest.approx(77.0)
    assert g.DIF_TEMPERATURAS["°C"] == 1.0  # 10 °C de diferença são 10 K


def test_unidade_sem_deslocamento_converte_como_antes():
    u = g.unidades_padrao(SOLIDOS)
    for dimensao in SOLIDOS.dimensoes:
        assert u.deslocamento(dimensao) == 0.0
        assert u.para_base(dimensao, 3.0) == pytest.approx(3.0 * u.fator(dimensao))


def test_numero_passa_de_uma_parte_para_a_outra_pelo_si():
    assert g.converter(0.05, FLUIDOS, g.DIAMETRO, SOLIDOS, g.MEDIDA) == pytest.approx(50.0)
    assert g.converter(2e6, FLUIDOS, g.PRESSAO, SOLIDOS, g.TENSAO) == pytest.approx(2.0)
    assert g.converter(1.5e3, FLUIDOS, g.POTENCIA, SOLIDOS, g.POTENCIA) == pytest.approx(1.5e6)
    assert g.equivalente(g.DIAMETRO, SOLIDOS) == g.MEDIDA
    assert g.equivalente(g.PRESSAO, SOLIDOS) == g.TENSAO
    assert g.equivalente(g.ALTURA, SOLIDOS) == g.COMPRIMENTO
    assert g.equivalente(g.VAZAO, SOLIDOS) is None  # vazão não entra numa seção
    assert g.equivalente(g.MOMENTO, FLUIDOS) is None  # momento não vira energia


def test_unidades_de_arquivo_antigo_ficam_e_a_nova_vem_no_padrao():
    antigas = ["cm", "m", "L/s", "bar", "cv"]  # de antes do seletor de temperatura
    assert g.unidades_lidas(FLUIDOS, antigas) == [*antigas, "°C"]
    assert g.unidades_lidas(FLUIDOS, ["xx", "m"])[:2] == ["mm", "m"]
    assert g.unidades_lidas(FLUIDOS, None) == [s.padrao for s in FLUIDOS.seletores]


def test_arquivo_de_fluidos_antigo_abre_com_as_unidades_dele():
    doc = rg.documento(
        mb.FLUIDOS, {"nos": [], "fios": []}, {}, {}, None, None, ["cm", "m", "L/s", "bar", "cv"]
    )
    lido = rg.ler_documento(rg.em_json(doc), mb.FLUIDOS, FLUIDOS)
    assert lido["unidades"] == ["cm", "m", "L/s", "bar", "cv", "°C"]


def test_resultado_dos_fluidos_entra_nos_solidos_convertido():
    projeto = {
        "registros_tecnicos": [
            {
                "id": "r1",
                "modulo": "Montador de fluidos",
                "titulo": "Diâmetro",
                "hash_calculo": "abc",
                "saidas_publicas": [
                    {
                        "chave": "D",
                        "rotulo": "D: Diâmetro interno (resposta)",
                        "dimensao": g.DIAMETRO,
                        "valor": 0.05,
                        "dominio": mb.FLUIDOS,
                    },
                    {
                        "chave": "Q",
                        "rotulo": "Q: Vazão",
                        "dimensao": g.VAZAO,
                        "valor": 0.01,
                        "dominio": mb.FLUIDOS,
                    },
                ],
            }
        ]
    }
    fontes = rg.fontes_do_projeto(projeto, mb.SOLIDOS, g.unidades_padrao(SOLIDOS))
    assert [f.campo for f in fontes] == ["D"]  # a vazão não tem onde ligar numa seção
    fonte = fontes[0]
    assert fonte.dimensao == g.MEDIDA
    assert float(rg.opcoes_da_fonte(fonte)["valor"]) == pytest.approx(50.0)
    # Na própria parte, o número entra como está.
    mesmos = rg.fontes_do_projeto(projeto, mb.FLUIDOS, g.unidades_padrao(FLUIDOS))
    assert {f.campo: f.fator for f in mesmos} == {"D": 1.0, "Q": 1.0}


# ---------------------------------------------------------------------------
# Letras com sinal
# ---------------------------------------------------------------------------


def test_letra_com_sinal_aceita_negativo_e_a_positiva_nao():
    com_sinal = g.Grandeza("q_saida_teste", "Q", "Calor", g.POTENCIA, "Teste.", sinal_livre=True)
    assert com_sinal.problema_no_valor(-3.0) is None
    assert com_sinal.problema_no_valor(0.0) is None
    assert com_sinal.simbolo.is_positive is None
    assert com_sinal.simbolo.is_real
    assert g.simbolo_de("q_saida_teste") == com_sinal.simbolo
    assert g.D.problema_no_valor(-3.0) is not None
    assert g.D.simbolo.is_positive


def test_nenhuma_letra_com_sinal_usa_a_chave_de_uma_positiva():
    positivas = {
        item.chave
        for sistema in (SOLIDOS.chave, FLUIDOS.chave)
        for item in g.letras_conhecidas(sistema).values()
        if not item.sinal_livre
    }
    assert not (positivas & g._COM_SINAL)


# ---------------------------------------------------------------------------
# Letras do meio e laços
# ---------------------------------------------------------------------------


def _formula(id_: str, texto: str) -> dict:
    return {"id": id_, "tipo": mb.FORMULA, "opcoes": {"texto": texto}}


def _ao_resultado(*ids: str) -> list[dict]:
    return [{"de": i, "saida": "condicao", "para": "r", "entrada": "condicoes"} for i in ids]


def _isolar(nos, fios, alvo, valores):
    dados = {"nos": [*nos, {"id": "r", "tipo": mb.RESULTADO}], "fios": fios}
    m = mt.montar(mt.grafo_de_dados(dados))
    assert not m.erros, m.erros
    return m, mt.isolar(m, alvo, valores)


def test_letra_do_meio_sem_a_pedida_se_resolve_antes():
    _, r = _isolar(
        [_formula("f1", "ua = 2*ub"), _formula("f2", "uc*ua <= 100")],
        _ao_resultado("f1", "f2"),
        "uc",
        {"ub": 5.0},
    )
    assert r.valor == pytest.approx(10.0)
    assert r.sentido == mt.MAXIMO
    assert dict(r.do_meio)["ua"] == pytest.approx(10.0)
    assert not r.faltam


def test_letra_do_meio_que_muda_com_a_pedida():
    _, r = _isolar(
        [_formula("f1", "ua = uc + ub"), _formula("f2", "ua*uc <= 100")],
        _ao_resultado("f1", "f2"),
        "uc",
        {"ub": 5.0},
    )
    assert r.valor == pytest.approx((-5.0 + math.sqrt(425.0)) / 2.0, rel=1e-9)
    assert dict(r.do_meio)["ua"] == pytest.approx(r.valor + 5.0, rel=1e-9)
    usos = {linha.nome: linha.uso for linha in r.conferencia}
    assert max(usos.values()) == pytest.approx(1.0, rel=1e-6)


def test_letras_do_meio_amarradas_se_resolvem_juntas():
    _, r = _isolar(
        [
            _formula("f1", "ua = ub + ud/2"),
            _formula("f2", "ud = ua/3 + 1"),
            _formula("f3", "uc <= ua*ud"),
        ],
        _ao_resultado("f1", "f2", "f3"),
        "uc",
        {"ub": 5.0},
    )
    assert dict(r.do_meio) == pytest.approx({"ua": 6.6, "ud": 3.2})
    assert r.valor == pytest.approx(6.6 * 3.2)


def test_sem_igualdade_que_feche_a_letra_continua_faltando():
    _, r = _isolar(
        [_formula("f1", "uc*ua <= 100")], _ao_resultado("f1"), "uc", {}
    )  # ua não tem igualdade nenhuma
    assert [f.chave for f in r.faltam] == ["ua"]
    assert r.valor is None


def test_analise_ordena_os_grupos():
    a, b, c, x = sp.symbols("a b c x", positive=True)
    condicoes = [
        mb.Condicao("c", "c", c, a + b, "c", igualdade=True),
        mb.Condicao("a", "a", a, 2 * x, "a", igualdade=True),
        mb.Condicao("b", "b", b, a + 1, "b", igualdade=True),
        mb.Condicao("limite", "limite", c, sp.Integer(50), "c"),
    ]
    meio = sm.analisar(condicoes, x, frozenset())
    assert meio is not None
    assert [tuple(s.name for s in grupo.letras) for grupo in meio.grupos] == [
        ("a",),
        ("b",),
        ("c",),
    ]
    assert meio.depende_do_alvo


def _laco(volta: str, alvo_texto: str) -> tuple[list, list]:
    nos = [_formula("f1", "ua = 0.5*ub + 3"), _formula("f2", volta), _formula("f3", alvo_texto)]
    entrada = sorted(mb.portas_de(mb.FORMULA, {"texto": volta})[0], key=lambda p: p.chave)[0].chave
    fios = [
        {"de": "f1", "saida": "saida", "para": "f2", "entrada": entrada},
        {"de": "f2", "saida": "saida", "para": "f1", "entrada": "ub"},
        {"de": "f1", "saida": "saida", "para": "f3", "entrada": "ua"},
        *_ao_resultado("f3"),
    ]
    return nos, fios


def test_laco_de_fios_de_valor_fecha_pela_conta():
    nos, fios = _laco("ub = ua + 1", "uc <= ua")
    m, r = _isolar(nos, fios, "uc", {})
    assert m.cortes == ("lc_1",)
    assert mt.e_corte("lc_1") and not mt.e_corte("L")
    assert r.valor == pytest.approx(7.0)
    assert dict(r.do_meio)["lc_1"] == pytest.approx(8.0)
    assert any(c.criterio == "Laço" for c in m.condicoes)


def test_laco_que_fecha_abaixo_de_zero():
    nos, fios = _laco("ub = uf - 30", "uc <= ua + 40")
    _, r = _isolar(nos, fios, "uc", {})
    assert dict(r.do_meio)["lc_1"] == pytest.approx(-54.0)
    assert r.valor == pytest.approx(16.0)


def test_laco_de_secao_continua_avisando():
    dados = {
        "nos": [
            {"id": "s", "tipo": "circular"},
            {"id": "a", "tipo": "normal"},
            {"id": "b", "tipo": "torcao"},
        ],
        "fios": [
            {"de": "s", "saida": "saida", "para": "a", "entrada": "entrada"},
            {"de": "a", "saida": "saida", "para": "b", "entrada": "entrada"},
            {"de": "b", "saida": "saida", "para": "a", "entrada": "entrada"},
        ],
    }
    grafo = mt.Grafo(
        tuple(mt.No(n["id"], n["tipo"]) for n in dados["nos"]),
        tuple(mt.Fio(f["de"], f["saida"], f["para"], f["entrada"]) for f in dados["fios"]),
    )
    m = mt.montar(grafo)
    assert any("laço" in erro for _, erro in m.erros)
    assert m.cortes == ()


def test_modelos_prontos_nao_tem_letra_do_meio():
    """Os modelos de antes dão a mesma resposta: nenhuma letra do meio entrou neles."""
    for parte in (mm.PARTE_SOLIDOS, mm.PARTE_FLUIDOS):
        for modelo in parte.modelos:
            m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
            letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
            valores = {**letras, **dict(m.padroes), **modelo.valores}
            if modelo.alvo not in {i.chave for i in m.grandezas}:
                continue
            r = mt.isolar(m, modelo.alvo, valores)
            assert r.do_meio == (), modelo.nome
            assert m.cortes == (), modelo.nome


# ---------------------------------------------------------------------------
# CoolProp
# ---------------------------------------------------------------------------

AGUA = mp.FLUIDOS.index(mp.POR_ROTULO["Água"])


def test_agua_da_coolprop_bate_com_a_tabela():
    assert mp.propriedade(AGUA, mp.RHO, mp.TP, 293.15, 101325.0) == pytest.approx(998.2, rel=2e-4)
    assert mp.propriedade(AGUA, mp.MU, mp.TP, 293.15, 101325.0) == pytest.approx(
        1.0016e-3, rel=1e-2
    )
    assert mp.propriedade(AGUA, mp.PV, mp.TX, 293.15, 0.0) == pytest.approx(2339.0, rel=1e-3)
    assert mp.propriedade(AGUA, mp.T, mp.PX, 101325.0, 0.0) == pytest.approx(373.124, abs=0.01)


def test_estado_que_nao_existe_vira_sem_numero():
    grade = mp.propriedade(AGUA, mp.RHO, mp.TP, np.array([293.15, 5.0, 353.15]), 101325.0)
    assert math.isnan(grade[1]) and grade[0] > grade[2] > 900.0
    assert math.isnan(mp.propriedade(AGUA, mp.RHO, mp.TP, 5.0, 101325.0))
    assert math.isnan(mp.propriedade(AGUA, mp.PV, mp.TX, 700.0, 0.0))  # acima do ponto crítico


def test_propriedade_na_formula_e_no_word():
    t, p = sp.symbols("T_f p_f", positive=True)
    rho = mp.massa_especifica(mp.POR_ROTULO["Água"], t, p)
    assert rho.is_positive
    assert "água" in sp.latex(rho)
    assert float(rho.subs({t: 293.15, p: 101325.0}).evalf()) == pytest.approx(998.2, rel=2e-4)
    assert "ρ" in mw.em_omml(rho)
    entalpia = mp._f(mp.POR_ROTULO["Água"], mp.H, mp.TP, t, p)
    assert entalpia.is_positive is None  # h pode ser negativa


def _modelo_com_agua_da_coolprop(nome: str) -> tuple[mt.Montagem, dict[str, float], str]:
    modelo = mm.PARTE_FLUIDOS.por_nome[nome]
    dados = modelo.grafo()
    for no in dados["nos"]:
        if no["tipo"] == "fluido":
            no.setdefault("opcoes", {})["fluido"] = "Água pela temperatura (CoolProp)"
    m = mt.montar(mt.grafo_de_dados(dados))
    letras = {i.chave: i.padrao for i in m.grandezas if i.padrao is not None}
    valores = {**letras, **dict(m.padroes)}
    valores.update({k: v for k, v in modelo.valores.items() if k not in ("rho", "mu", "p_v")})
    return m, valores, modelo.alvo


@pytest.mark.parametrize("nome", ["Diâmetro mínimo do tubo", "Altura máxima de sucção"])
def test_fluidos_com_a_coolprop_dao_o_da_tabela_a_20_graus(nome):
    modelo = mm.PARTE_FLUIDOS.por_nome[nome]
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    letras = {i.chave: i.padrao for i in base.grandezas if i.padrao is not None}
    tabela = mt.isolar(base, modelo.alvo, {**letras, **dict(base.padroes), **modelo.valores})
    m, valores, alvo = _modelo_com_agua_da_coolprop(nome)
    assert mt.isolar(m, alvo, valores).valor == pytest.approx(tabela.valor, rel=1e-4)


def test_agua_quente_cavita_antes_e_a_temperatura_pode_ser_a_pedida():
    m, valores, alvo = _modelo_com_agua_da_coolprop("Altura máxima de sucção")
    alturas = [mt.isolar(m, alvo, {**valores, "T_f": t + 273.15}).valor for t in (20, 60, 80)]
    assert alturas[0] > alturas[1] > alturas[2] > 0.0
    sem_t = {k: v for k, v in valores.items() if k != "T_f"}
    r = mt.isolar(m, "T_f", {**sem_t, alvo: alturas[1]})
    assert r.valor == pytest.approx(333.15, abs=0.05)
    assert r.sentido == mt.MAXIMO


def test_o_que_mais_pesa_com_a_temperatura_abaixo_de_zero_nao_quebra():
    """Descer 10 % de 293 K passa de 0 °C: a água sai da tabela, e a conta fica sem número ali."""
    m, valores, alvo = _modelo_com_agua_da_coolprop("Altura máxima de sucção")
    r = mt.isolar(m, alvo, {**valores, "T_f": 280.0})
    pesos = msen.pesos(r)
    assert pesos  # roda até o fim, mesmo com um lado sem número


def test_agua_que_ferve_na_linha_avisa():
    m, valores, alvo = _modelo_com_agua_da_coolprop("Diâmetro mínimo do tubo")
    r = mt.isolar(m, alvo, {**valores, "T_f": 383.15})  # 110 °C a 1 atm
    assert any("ferve" in a for a in r.alertas)
