"""Fórmula própria, catálogo, fadiga completa, fluidos do dia a dia, Word e Excel do Montador."""

from __future__ import annotations

import io
import json
import math
import re
import zipfile
from pathlib import Path

import numpy as np
import pytest
import sympy as sp
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from core import casos_de_aceite as ca
from core import elementos_eixos as ee
from core import fatigue as ft
from core import montador as mt
from core import montador_aceite as ma
from core import montador_blocos as mb
from core import montador_catalogo as cat
from core import montador_conjuntos as mc
from core import montador_fluidos as fl
from core import montador_formula as mf
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_planilha as mp
from core import montador_word as mw
from core.montador_grandezas import unidades_padrao
from core.montador_modelos import Modelo

APP = str(Path(__file__).resolve().parents[1] / "app.py")
U = unidades_padrao(g.SISTEMA_SOLIDOS)
U_F = unidades_padrao(g.SISTEMA_FLUIDOS)
R = mb.RESULTADO
SOLIDOS = g.SISTEMA_SOLIDOS.chave
FLUIDOS = g.SISTEMA_FLUIDOS.chave


def abrir(pagina: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(pagina).run()
    assert not at.exception
    return at


def _tela(at: AppTest) -> str:
    return " ".join(e.proto.body for e in at.get("html"))


def _formula(texto: str, **opcoes: str) -> dict:
    return {"texto": texto, "sistema": SOLIDOS, **opcoes}


def _so_formula(texto: str, alvo: str, valores: dict, **opcoes: str) -> mt.Resposta:
    modelo = Modelo(
        "x",
        "",
        alvo,
        valores,
        (R,),
        (("n2", mb.FORMULA),),
        (("n2", "condicao", "n1", "condicoes"),),
        {"n2": _formula(texto, **opcoes)},
    )
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    return mt.isolar(base, alvo, valores)


# ---------------------------------------------------------------------------
# Fórmula própria
# ---------------------------------------------------------------------------


def test_le_as_tres_formas():
    assert mf.ler("q*L^2/8").sinal == ""
    nomeada = mf.ler("M = q*L^2/8")
    assert (nomeada.nome, nomeada.letras) == ("M", ("q", "L"))
    assert nomeada.tem_valor and nomeada.tem_condicao
    condicao = mf.ler("M*c/I <= S_y/n")
    assert condicao.sinal == mf.MENOR_IGUAL and not condicao.tem_valor


def test_precedencia_como_na_matematica():
    x = sp.Symbol("x", positive=True)
    assert mf.ler("-x^2").direita == -(x**2)
    assert mf.ler("2^3^2").direita == 512
    assert mf.ler("1/2*x").direita == x / 2
    assert mf.ler("2,5*x").direita == sp.Rational(5, 2) * x


def test_letra_grega_vale_o_nome_da_letra():
    assert mf.ler("ρ*g*h").letras == ("rho", "g", "h")
    assert mf.ler("√(x)").direita == sp.sqrt(sp.Symbol("x", positive=True))


@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        ("", "Digite"),
        ("2q", "sinal de vezes"),
        ("(a+b", "fechar"),
        ("a +", "terminou"),
        ("a < b", "Use <="),
        ("log(a)", "ln"),
        ("foo(a)", "função"),
        ("a <= b <= c", "um sinal"),
        ("1/0", "zero"),
        ("9^9^9^9", "grande demais"),
        ("(-1)^(1/2)", "não dá um número"),
        ("a @ b", "sinal"),
        ("x" * 400, "passa de"),
        ("(" * 40 + "a" + ")" * 40, "Parênteses"),
    ],
)
def test_recusa_o_que_nao_sabe_ler(texto, trecho):
    with pytest.raises(mf.ErroDeFormula, match=trecho):
        mf.ler(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "__import__('os').system('dir')",
        "lambda: 1",
        "a.__class__",
        "exec(a)",
        "open('x')",
        "a; b",
    ],
)
def test_texto_nao_vira_codigo(texto):
    with pytest.raises(mf.ErroDeFormula):
        mf.ler(texto)


def test_o_leitor_nao_usa_eval_nem_sympify():
    fonte = Path(mf.__file__).read_text(encoding="utf-8")
    codigo = fonte.split('"""', 2)[2]
    assert "eval(" not in codigo and "sympify" not in codigo and "exec(" not in codigo


def test_formula_isola_a_letra_pedida():
    resposta = _so_formula("32*M_x/(pi*d^3) <= S_y/n", "d", {"M_x": 5e5, "S_y": 250.0, "n": 2.0})
    assert resposta.valor == pytest.approx((32 * 5e5 * 2 / (math.pi * 250.0)) ** (1 / 3))
    assert resposta.sentido == mt.MINIMO


def test_maior_igual_vira_de_lado():
    resposta = _so_formula("S_y/n >= 32*M_x/(pi*d^3)", "d", {"M_x": 5e5, "S_y": 250.0, "n": 2.0})
    assert resposta.valor == pytest.approx((32 * 5e5 * 2 / (math.pi * 250.0)) ** (1 / 3))


def test_igualdade_isola_qualquer_letra():
    resposta = _so_formula("a*b^2 = 8", "b", {"a": 2.0})
    assert resposta.valor == pytest.approx(2.0)
    assert resposta.sentido == mt.IGUAL


def test_saida_com_nome_entra_na_flexao():
    dados = {
        "nos": [
            {"id": "n1", "tipo": "retangular", "opcoes": {}},
            {"id": "n2", "tipo": "flexao", "opcoes": {}},
            {"id": "n3", "tipo": "von_mises", "opcoes": {}},
            {"id": "n4", "tipo": R, "opcoes": {}},
            {"id": "n5", "tipo": mb.FORMULA, "opcoes": _formula("M = q*L^2/8")},
        ],
        "fios": [
            {"de": "n1", "saida": "saida", "para": "n2", "entrada": "entrada"},
            {"de": "n2", "saida": "saida", "para": "n3", "entrada": "entrada"},
            {"de": "n3", "saida": "condicao", "para": "n4", "entrada": "condicoes"},
            {"de": "n5", "saida": "saida", "para": "n2", "entrada": "valor"},
        ],
    }
    grafo = mt.grafo_de_dados(dados)
    assert len(grafo.fios) == 4  # o fio passou: F·mm entra onde se pede momento
    base = mt.montar(grafo)
    letras = {i.chave for i in base.grandezas}
    assert {"q", "L"} <= letras and "M_x" not in letras


def test_bolinhas_nascem_das_letras():
    entradas, saidas = mb.portas_de(mb.FORMULA, _formula("M = q*L^2/8"))
    assert [p.chave for p in entradas] == ["q", "L"]
    assert {p.dimensao for p in entradas} == {g.DISTRIBUIDA, g.COMPRIMENTO}
    assert saidas[0].dimensao == g.MOMENTO  # sai pela conta: F/L·L² dá F·L
    assert saidas[0].rotulo == "M"
    assert saidas[1].tipo == mb.CONDICAO


def test_formula_com_erro_fica_sem_bolinhas_e_mostra_o_erro():
    assert mb.portas_de(mb.FORMULA, _formula("2q")) == ((), ())
    dados = {"nos": [{"id": "n1", "tipo": mb.FORMULA, "opcoes": _formula("2q")}], "fios": []}
    base = mt.montar(mt.grafo_de_dados(dados))
    assert "sinal de vezes" in dict(base.erros)["n1"]


def test_unidades_que_nao_fecham_viram_aviso():
    f = mf.ler("F + L")
    assert "mesma unidade" in mf.problemas_de_unidade(f, SOLIDOS, {})[0]
    certa = mf.ler("M_x*c/I <= S_y/n")
    assert mf.problemas_de_unidade(certa, SOLIDOS, {}) == []  # c e I pelo nome que costumam ter
    errada = mf.ler("M_x/c <= S_y")
    assert "dois lados" in mf.problemas_de_unidade(errada, SOLIDOS, {})[0]


def test_letra_nova_recebe_a_unidade_escolhida():
    f = mf.ler("x*b <= F")
    assert mf.problemas_de_unidade(f, SOLIDOS, {"x": g.DISTRIBUIDA}) == []
    assert mf.problemas_de_unidade(f, SOLIDOS, {"x": g.TENSAO})
    assert mf.e_letra_nova("x", SOLIDOS)
    assert not mf.e_letra_nova("S_y", SOLIDOS)


def test_a_mesma_letra_muda_de_sentido_entre_as_partes():
    assert g.letras_conhecidas(SOLIDOS)["h"].dimensao == g.MEDIDA
    assert g.letras_conhecidas(FLUIDOS)["h"].dimensao == g.ALTURA
    assert "rho" not in g.letras_conhecidas(SOLIDOS)


def test_fios_soltos_saem_quando_a_letra_some():
    dados = {
        "nos": [
            {"id": "n1", "tipo": mb.FORMULA, "opcoes": _formula("a*b")},
            {"id": "n2", "tipo": "viga_biapoiada_ponta", "opcoes": {}},
        ],
        "fios": [{"de": "n3", "saida": "x", "para": "n1", "entrada": "a"}],
    }
    assert mc.tirar_fios_soltos(dados)["fios"] == []


def test_formula_guardada_em_arquivo_ruim_nao_quebra():
    assert mf.dimensoes_das_letras("nada") == {}
    assert mf.dimensoes_das_letras('{"x": "inventada"}') == {}
    assert mf.dimensoes_das_letras('{"x": "forca"}') == {"x": "forca"}


def test_tela_recebe_a_formula_digitada():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Fórmula própria").run()
    assert not at.exception
    assert any(s.value.startswith("**d ≥") for s in at.success)
    at.session_state["mf_selecao"] = {"tipo": "no", "id": "n2"}
    at.run()
    campo = at.text_input(key="mf_formula_n2")
    assert campo.value == "32*M_x/(pi*d^3) <= S_y/n"
    assert "As unidades fecham" in _tela(at)
    campo.set_value("M_x/d^3 <= S_y").run()
    assert not at.exception
    assert "As unidades fecham" in _tela(at) or any("dois lados" in c.value for c in at.caption)
    at.text_input(key="mf_formula_n2").set_value("2q").run()
    assert not at.exception
    assert any("sinal de vezes" in w.value for w in at.warning)


def test_tela_pergunta_o_que_e_a_letra_nova():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Fórmula própria").run()
    at.session_state["mf_selecao"] = {"tipo": "no", "id": "n2"}
    at.run()
    at.text_input(key="mf_formula_n2").set_value("x*b <= S_y").run()
    assert not at.exception
    assert "Letras novas" in _tela(at)
    assert any("dois lados" in c.value for c in at.caption)
    at.selectbox(key="mf_letra_n2_x").set_value(g.TENSAO).run()
    assert not at.exception
    grafo = at.session_state["mf_grafo"]
    no = next(n for n in grafo["nos"] if n["id"] == "n2")
    assert json.loads(no["opcoes"]["dimensoes"]) == {"x": g.TENSAO}
    assert [p["chave"] for p in no["portas"]["entradas"]] == ["x", "b", "S_y"]


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


def _base(*tipos: str, opcoes: dict | None = None) -> mt.Montagem:
    modelo = Modelo("x", "", "", {}, tipos, opcoes=opcoes or {})
    return mt.montar(mt.grafo_de_dados(modelo.grafo()))


def test_cada_secao_sabe_o_seu_catalogo():
    assert {f.familias for f in cat.fontes(_base("circular", "flexao", "von_mises", R))} == {
        ("Barra circular",)
    }
    i = cat.fontes(_base("perfil_i", "flexao", "von_mises", R))[0]
    assert "W (mesa larga)" in i.familias
    familias = cat.fontes(_base("fluido", "trecho", "carga", R))[0].familias
    assert familias[0] == "Aço Sch 40" and familias[-1] == "PVC soldável"
    assert {"Aço Sch 80", "Aço inox Sch 10S"} <= set(familias)


def test_acha_o_perfil_mais_leve_que_passa():
    base = _base("perfil_i", "flexao", "von_mises", R)
    fonte = cat.fontes(base)[0]
    escolha = cat.testar(base, fonte, {"M_x": 5e7, "S_y": 250.0, "n": 1.5})
    melhor = escolha.melhor
    assert melhor is not None and melhor.passa and melhor.uso <= 1.0
    leves = [
        x for x in escolha.linhas if x.peca.massa is not None and x.peca.massa < melhor.peca.massa
    ]
    assert leves and not any(x.passa for x in leves)
    assert escolha.aprovadas + sum(not x.passa for x in escolha.linhas) == escolha.testadas


def test_o_uso_do_catalogo_e_o_da_conta_direta():
    base = _base("perfil_i", "flexao", "von_mises", R)
    fonte = cat.fontes(base)[0]
    valores = {"M_x": 5e7, "S_y": 250.0, "n": 1.5}
    melhor = cat.testar(base, fonte, valores).melhor
    medidas = dict(melhor.peca.valores)
    tudo = {**valores, **{k: v for k, v in medidas.items() if k != "h"}}
    direta = mt.isolar(base, "h", tudo, medidas["h"])
    assert max(x.uso for x in direta.conferencia_adotada) == pytest.approx(melhor.uso)


def test_sem_peca_que_passe_nao_inventa():
    base = _base("circular", "flexao", "von_mises", R)
    fonte = cat.fontes(base)[0]
    escolha = cat.testar(base, fonte, {"M_x": 1e13, "S_y": 250.0, "n": 1.5})
    assert escolha.melhor is None and escolha.aprovadas == 0


def test_catalogo_pede_o_que_falta():
    base = _base("circular", "flexao", "von_mises", R)
    fonte = cat.fontes(base)[0]
    with pytest.raises(cat.ErroDoCatalogo, match="preencha"):
        cat.testar(base, fonte, {"M_x": 1e6})


def test_tubo_comercial_pelo_menor_diametro():
    base = _base("fluido", "trecho", "perda_local", "carga", R)
    fonte = cat.fontes(base)[0]
    valores = {
        "rho": 998.2,
        "mu": 1.0016e-3,
        "g": 9.81,
        "L": 100.0,
        "Q": 0.01,
        "K_L": 2.0,
        "H_d": 5.0,
        "varepsilon": 4.5e-5,
    }
    escolha = cat.testar(base, fonte, valores, ("Aço Sch 40",))
    melhor = escolha.melhor
    assert melhor is not None and melhor.peca.familia == "Aço Sch 40"
    menores = [
        x for x in escolha.linhas if dict(x.peca.valores)["D"] < dict(melhor.peca.valores)["D"]
    ]
    assert menores and not any(x.passa for x in menores)


def test_tela_usa_a_peca_do_catalogo():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Eixo com flexão e torção").run()
    at.toggle(key="mf_catalogo_ligado").set_value(True).run()
    assert not at.exception
    assert any("A mais leve que passa" in s.value for s in at.success)
    peca = at.selectbox(key="mf_catalogo_peca").value
    at.button(key="mf_catalogo_usar").click().run()
    assert not at.exception
    assert at.session_state["mf_adotado"] is not None
    assert "Barra circular" in peca


# ---------------------------------------------------------------------------
# Fadiga
# ---------------------------------------------------------------------------


def _fadiga(
    alvo: str,
    valores: dict,
    criterio: str = mb.GOODMAN,
    vida: str = mb.VIDA_INFINITA,
    entalhe: str = ee.ENTALHE_LISO,
    confianca: str = "50 %",
    acabamento: str = "Usinado ou estirado a frio",
) -> mt.Resposta:
    modelo = Modelo(
        "x",
        "",
        alvo,
        valores,
        ("circular", "flexao", "torcao", "goodman", R),
        (("m1", "material"), ("m2", "limite_fadiga"), ("m3", "entalhe")),
        (
            ("m1", "saida", "n4", "material"),
            ("m1", "saida", "m2", "material"),
            ("m1", "saida", "m3", "material"),
            ("m2", "se", "n4", "se"),
            ("m3", "kf", "n4", "kf"),
            ("m3", "kfs", "n4", "kfs"),
        ),
        {
            "n4": {"esforcos": mb.EIXO_GIRANDO, "criterio": criterio, "vida": vida},
            "m2": {"confiabilidade": confianca, "acabamento": acabamento},
            "m3": {"entalhe": entalhe},
        },
    )
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    tudo = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **valores,
    }
    return mt.isolar(base, alvo, tudo)


_EIXO = {"M_x": 2e5, "T": 1.5e5, "S_y": 420.0, "S_ut": 690.0, "d": 30.0}


def _se_do_assistente(d: float = 30.0, confianca: float = 50) -> float:
    return ee.limite_de_fadiga(690.0, d, "usinado_ou_estirado_a_frio", confianca, 20.0)[0]


def _tensoes(kf: float = 1.0, kfs: float = 1.0, d: float = 30.0) -> tuple[float, float]:
    alternada = 32.0 * kf * 2e5 / (math.pi * d**3)
    media = math.sqrt(3.0) * 16.0 * kfs * 1.5e5 / (math.pi * d**3)
    return alternada, media


@pytest.mark.parametrize("confianca", ["50 %", "90 %", "99 %"])
def test_limite_de_fadiga_e_o_mesmo_do_assistente(confianca):
    modelo = Modelo(
        "x",
        "",
        "S_ut",
        {},
        ("limite_fadiga",),
        opcoes={"n1": {"confiabilidade": confianca}},
    )
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    se = base.saidas["n1"]["se"]
    numeros = {
        sp.Symbol(k, positive=True): sp.Float(v)
        for k, v in {
            "S_ut": 690.0,
            "d": 30.0,
            "k_d": 1.0,
            "k_div": 1.0,
            "k_e": dict(base.padroes)["k_e"],
        }.items()
    }
    esperado = _se_do_assistente(30.0, ee.CONFIABILIDADES[confianca])
    assert float(sp.N(se.subs(numeros))) == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("criterio", "chave"),
    [
        (mb.GOODMAN, "DE-Goodman"),
        (mb.GERBER, "DE-Gerber"),
        (mb.SODERBERG, "DE-Soderberg"),
        (mb.ELIPTICO, "DE-ASME elíptico"),
    ],
)
def test_cada_criterio_da_o_fator_do_assistente(criterio, chave):
    se = _se_do_assistente()
    sa, sm = _tensoes()
    esperado = ee._criterios_de_fadiga(sa, sm, se, 690.0, 420.0)[chave]
    r = _fadiga("n", _EIXO, criterio)
    n_fadiga = next(i.valor for i in r.isoladas if "Fadiga" in i.condicao.nome)
    assert n_fadiga == pytest.approx(esperado, rel=1e-6)


def test_entalhe_de_ressalto_e_o_do_assistente():
    valores = {**_EIXO, "D_r": 40.0, "r_e": 3.0}
    q = ee.sensibilidade(690.0, 3.0, "flexao")
    qs = ee.sensibilidade(690.0, 3.0, "torcao")
    kt = ee.kt_ressalto(40.0, 30.0, 3.0, "flexao")
    kts = ee.kt_ressalto(40.0, 30.0, 3.0, "torcao")
    kf, kfs = 1 + q * (kt - 1), 1 + qs * (kts - 1)
    se = _se_do_assistente()
    sa, sm = _tensoes(kf, kfs)
    esperado = ee._criterios_de_fadiga(sa, sm, se, 690.0, 420.0)["DE-Goodman"]
    r = _fadiga("n", valores, entalhe=ee.ENTALHE_RESSALTO)
    n_fadiga = next(i.valor for i in r.isoladas if "Fadiga" in i.condicao.nome)
    assert n_fadiga == pytest.approx(esperado, rel=1e-6)


def test_diametro_pedido_acompanha_o_kb_e_o_kt():
    valores = {k: v for k, v in _EIXO.items() if k != "d"}
    r = _fadiga("d", {**valores, "n": 2.0, "D_r": 60.0, "r_e": 3.0}, entalhe=ee.ENTALHE_RESSALTO)
    assert r.valor is not None
    d = r.valor
    kt = ee.kt_ressalto(60.0, d, 3.0, "flexao")
    kts = ee.kt_ressalto(60.0, d, 3.0, "torcao")
    q, qs = ee.sensibilidade(690.0, 3.0, "flexao"), ee.sensibilidade(690.0, 3.0, "torcao")
    sa, sm = _tensoes(1 + q * (kt - 1), 1 + qs * (kts - 1), d)
    n = ee._criterios_de_fadiga(sa, sm, _se_do_assistente(d), 690.0, 420.0)["DE-Goodman"]
    assert n == pytest.approx(2.0, rel=1e-6)


def test_vida_finita_vai_de_09_sut_a_se():
    assert ft.resistencia_em_1e3_ciclos(690.0, "flexao", "shigley") == pytest.approx(621.0)
    se = 200.0
    a, b = ft.parametros_curva_sn(621.0, se, 1e6)
    from core.montador_funcoes import resistencia_em_vida

    for ciclos in (1e3, 1e4, 1e5, 1e6):
        assert resistencia_em_vida(621.0, se, ciclos) == pytest.approx(
            ft.resistencia_para_N(ciclos, a, b)
        )


def test_vida_finita_aguenta_mais_que_a_infinita():
    infinita = _fadiga("n", _EIXO)
    finita = _fadiga("n", {**_EIXO, "N_c": 1e5}, vida=mb.VIDA_FINITA)
    n_i = next(i.valor for i in infinita.isoladas if "Fadiga" in i.condicao.nome)
    n_f = next(i.valor for i in finita.isoladas if "Fadiga" in i.condicao.nome)
    assert n_f > n_i


def test_pede_a_vida_em_ciclos():
    r = _fadiga("N_c", {**_EIXO, "n": 1.0}, vida=mb.VIDA_FINITA)
    assert r.sentido in (mt.MAXIMO, mt.MINIMO)
    assert r.valor is not None and r.valor > 1e3


def test_acima_de_um_milhao_de_ciclos_avisa():
    r = _fadiga("n", {**_EIXO, "N_c": 1e8}, vida=mb.VIDA_FINITA)
    assert any("vida infinita" in a for a in r.alertas)


def test_escoamento_no_primeiro_ciclo_entra_com_o_material():
    r = _fadiga("n", _EIXO)
    nomes = [i.condicao.nome for i in r.isoladas]
    assert "Escoamento no primeiro ciclo" in nomes
    sa, sm = _tensoes()
    maxima = math.hypot(sa, sm)
    item = next(i for i in r.isoladas if i.condicao.nome == "Escoamento no primeiro ciclo")
    assert item.valor == pytest.approx(420.0 / maxima, rel=1e-6)


@pytest.mark.parametrize(
    ("campo", "valor", "trecho"),
    [
        ("K_t", 0.8, "pelo menos 1"),
        ("q_e", 1.2, "no máximo"),
        ("N_c", 500.0, "pelo menos"),
    ],
)
def test_valor_sem_sentido_e_recusado(campo, valor, trecho):
    item = next(i for i in vars(g).values() if isinstance(i, g.Grandeza) and i.chave == campo)
    assert trecho in item.problema_no_valor(valor)


def test_aluminio_avisa_que_nao_tem_limite():
    modelo = Modelo(
        "x",
        "",
        "S_ut",
        {},
        ("material", "limite_fadiga"),
        opcoes={"n1": {"material": _material_de("aluminio")}},
    )
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert any("Alumínio" in a for a in base.alertas)


def _material_de(categoria: str) -> str:
    from core import material_catalog as cm

    return next(n for n, m in cm.listar_cadastrados().items() if m.categoria == categoria)


# ---------------------------------------------------------------------------
# Fluidos do dia a dia
# ---------------------------------------------------------------------------


def test_agua_bate_com_as_duas_tabelas():
    """roymech.org e engineeringtoolbox.com: ρ, μ e p_v a 20, 40, 60 e 80 °C."""
    conferidos = {
        "Água a 20 °C": (998.2, 1.0016e-3, 2339.3),
        "Água a 40 °C": (992.2, 6.527e-4, 7384.9),
        "Água a 60 °C": (983.2, 4.660e-4, 19946.0),
        "Água a 80 °C": (971.8, 3.540e-4, 47414.0),
    }
    for nome, esperado in conferidos.items():
        assert fl.FLUIDOS_TIPICOS[nome] == pytest.approx(esperado, rel=2e-3)


def test_tubos_comerciais_batem_com_as_tabelas():
    sch40 = fl.TUBOS_COMERCIAIS["Aço Sch 40, DN 100 (4 pol)"]
    assert sch40.interno_m * 1000.0 == pytest.approx(102.26)
    pvc = fl.TUBOS_COMERCIAIS["PVC soldável, DN 50"]
    assert pvc.interno_m * 1000.0 == pytest.approx(44.0)
    assert all(t.interno_m > 0.0 for t in fl.TUBOS_COMERCIAIS.values())


def test_tubo_comercial_preenche_o_diametro():
    m = _base("fluido", "trecho", "carga", R, opcoes={"n2": {"comercial": "PVC soldável, DN 50"}})
    assert dict(m.padroes)["D"] == pytest.approx(0.044)


def test_tubo_de_pvc_com_rugosidade_de_aco_avisa():
    m = _base("fluido", "trecho", "carga", R, opcoes={"n2": {"comercial": "PVC soldável, DN 50"}})
    assert any("confira" in a for a in m.alertas)
    certo = _base(
        "fluido",
        "trecho",
        "carga",
        R,
        opcoes={"n2": {"comercial": "PVC soldável, DN 50", "tubo": "PVC ou plástico"}},
    )
    assert not any("confira" in a for a in certo.alertas)


def test_pecas_somam_o_k():
    pecas = json.dumps({"Curva 90° padrão (R/D = 1)": 3, "Registro de gaveta aberto": 1})
    m = _base("fluido", "trecho", "perda_local", "carga", R, opcoes={"n3": {"pecas": pecas}})
    assert dict(m.padroes)["K_L"] == pytest.approx(3 * 0.75 + 0.17)
    assert "3 × Curva" in dict(m.origens)["K_L"]


def test_peca_desconhecida_ou_texto_ruim_fica_de_fora():
    assert fl.ler_pecas('{"Inventada": 2, "Tê, saída lateral": 0}') == {}
    assert fl.ler_pecas("nada") == {}
    assert fl.ler_pontos('[[1, "x"], [2], "y", [0.1, 10]]') == [(0.1, 10.0)]


def test_tirar_todas_as_pecas_zera_o_k():
    m = _base("fluido", "trecho", "perda_local", "carga", R, opcoes={"n3": {"pecas": "{}"}})
    assert dict(m.padroes)["K_L"] == 0.0


def test_curva_de_tres_pontos_e_a_do_livro():
    """Exemplo 7.2: 0, 5000 e 7850 gpm dão h = 82,5 − 0,201·Q², em pés e pés³/s."""
    pontos = [(0.0, 81.0), (5000.0 / 448.831, 60.0), (7850.0 / 448.831, 20.0)]
    h_0, a = fl.ajustar_curva(pontos)
    assert h_0 == pytest.approx(82.5, abs=0.05)
    assert a == pytest.approx(0.201, abs=0.0005)


@pytest.mark.parametrize(
    "pontos",
    [[(1.0, 10.0)], [(1.0, 10.0), (1.0, 20.0)], [(0.0, 10.0), (1.0, 20.0)]],
)
def test_curva_que_nao_e_de_bomba_e_recusada(pontos):
    with pytest.raises(mb.ErroDeBloco):
        fl.ajustar_curva(pontos)


def test_pontos_da_curva_preenchem_as_letras():
    pontos = json.dumps([[0.0, 40.0], [0.01, 30.0], [0.02, 0.0]])
    m = _base("fluido", "trecho", "curva_bomba", R, opcoes={"n3": {"pontos": pontos}})
    h_0, a = dict(m.padroes)["H_0"], dict(m.padroes)["a_b"]
    assert (h_0, a) == pytest.approx(fl.ajustar_curva(json.loads(pontos)))


def test_ponto_de_operacao_cruza_as_duas_curvas():
    r = ma._ponto_de_operacao()
    assert r.sentido == mt.IGUAL
    linhas = mt.curvas_da_bomba(r, r.valores_usados)
    assert len(linhas) > 20
    q = r.valor
    antes = [x for x in linhas if x[0] < q * 0.9]
    depois = [x for x in linhas if x[0] > q * 1.1]
    assert all(s < b for _, s, b in antes)
    assert all(s > b for _, s, b in depois)


def test_grafico_de_bomba_so_sai_com_a_bomba():
    r = ma.resolver(
        ("fluido", "trecho", "carga", R),
        "Q",
        {"D": 0.1, "L": 100.0, "H_d": 5.0, "g": 9.81},
    )
    assert mt.curvas_da_bomba(r, r.valores_usados) == []


def test_tela_mostra_o_ponto_de_operacao():
    at = abrir("app_pages/montador_fluidos.py")
    at.selectbox(key="mfl_modelo").set_value("Ponto de operação da bomba").run()
    assert not at.exception
    assert any(s.value.startswith("**Q =") for s in at.success)
    assert any("A bomba entrega" in c.value for c in at.caption)


def test_inspetor_das_pecas_e_dos_pontos_abre():
    at = abrir("app_pages/montador_fluidos.py")
    at.selectbox(key="mfl_modelo").set_value("Ponto de operação da bomba").run()
    for id_ in ("n3", "n4"):
        at.session_state["mfl_selecao"] = {"tipo": "no", "id": id_}
        at.run()
        assert not at.exception
    assert "Pontos do catálogo da bomba" in _tela(at)


def test_edicao_da_tabela_e_aplicada():
    from components.montador_ui import _com_edicoes

    linhas = [{"a": 1}, {"a": 2}, {"a": 3}]
    novas = _com_edicoes(
        linhas,
        {"edited_rows": {"0": {"a": 9}}, "deleted_rows": [1], "added_rows": [{"a": 7}]},
    )
    assert novas == [{"a": 9}, {"a": 3}, {"a": 7}]


# ---------------------------------------------------------------------------
# Central de validação
# ---------------------------------------------------------------------------


def test_central_roda_os_casos_do_montador():
    nomes = {c.modulo for c in ca.casos()}
    assert {"Montador de fluidos", "Montador de fórmulas"} <= nomes


def test_cada_exemplo_publicado_passa():
    for resultado in ca.rodar(list(ma.casos())):
        assert resultado.passou, (resultado.caso.caso, resultado.obtido, resultado.erro)


def test_atrito_e_velocidade_do_exemplo_do_livro():
    """Exemplo 4.1: V = 2,120 m/s, Re = 1,036·10⁶ e f = 0,0133."""
    r = ma.resolver(
        ("fluido", "trecho", "carga", R),
        "H_d",
        {"rho": 1000.0, "mu": 1.023e-3, "g": 9.81, "L": 100.0, "varepsilon": 4.6e-5}
        | {"Q": 0.416, "D": 0.5},
        {"n1": {"fluido": fl.INFORMAR}, "n2": {"tubo": fl.RUGOSIDADE_INFORMADA}},
    )
    numeros = {sp.Symbol(k, positive=True): sp.Float(v) for k, v in r.valores_usados.items()}
    trecho = r.montagem.saidas["n2"]["saida"].trechos[0]
    assert float(trecho.velocidade.subs(numeros)) == pytest.approx(2.120, abs=0.002)
    assert float(trecho.reynolds.subs(numeros)) == pytest.approx(1.036e6, rel=1e-3)
    assert float(sp.N(trecho.atrito.subs(numeros))) == pytest.approx(0.0133, abs=5e-5)


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------


def _word(modelo: Modelo, sistema: g.Sistema) -> bytes:
    u = unidades_padrao(sistema)
    dados = modelo.grafo()
    base = mt.montar(mt.grafo_de_dados(dados))
    valores = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **modelo.valores,
    }
    r = mt.isolar(base, modelo.alvo, valores)
    return mw.gerar_word(
        modelo.nome, dados, r, u, valores, {}, {}, "resumo da resposta", ["Uma hipótese."]
    )


def _texto_do_word(conteudo: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        return z.read("word/document.xml").decode("utf-8")


@pytest.mark.parametrize(
    ("modelo", "sistema"),
    [
        *((m, g.SISTEMA_SOLIDOS) for m in mm.MODELOS),
        *((m, g.SISTEMA_FLUIDOS) for m in mm.MODELOS_FLUIDOS),
    ],
    ids=lambda x: getattr(x, "nome", "") or getattr(x, "chave", ""),
)
def test_todo_modelo_gera_word(modelo, sistema):
    conteudo = _word(modelo, sistema)
    texto = _texto_do_word(conteudo)
    assert "resumo da resposta" in texto and "Uma hipótese." in texto
    assert "Condições" in texto and "Passo a passo" in texto
    assert "oMath" in texto  # equação de verdade do Word, e não imagem


def test_formula_vira_equacao_do_word():
    x, y = sp.symbols("x y", positive=True)
    assert "<m:f>" in mw.em_omml(x / y)
    assert "<m:rad>" in mw.em_omml(sp.sqrt(x))
    assert "<m:deg>" in mw.em_omml(x ** sp.Rational(1, 3))
    assert "<m:sSup>" in mw.em_omml(x**2)
    assert "<m:sSub>" in mw.em_omml(sp.Symbol("S_y", positive=True))
    assert "ρ" in mw.em_omml(sp.Symbol("rho", positive=True))
    assert "−" in mw.em_omml(x - y)
    assert "π" in mw.em_omml(sp.pi * x)


def test_figura_da_montagem_e_um_png():
    dados = mm.MODELOS[0].grafo()
    png = mw.figura_da_montagem(dados, {"n1": {"a": "b = 50 mm", "b": "h ≥ 37 mm"}})
    assert png.startswith(b"\x89PNG")
    assert mw.figura_da_montagem({"nos": [], "fios": []}, {}) == b""


def test_o_que_nao_passou_vai_para_o_fim_do_word():
    modelo = mm.MODELOS[0]
    dados = modelo.grafo()
    base = mt.montar(mt.grafo_de_dados(dados))
    r = mt.isolar(base, modelo.alvo, dict(modelo.valores), 5.0)
    conteudo = mw.gerar_word(modelo.nome, dados, r, U, modelo.valores, {}, {}, "x", ["y"])
    assert "O que não passou" in _texto_do_word(conteudo)


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------


def _em_python(formula: str) -> str:
    texto = formula.lstrip("=").replace("^", "**").replace("PI()", "pi")
    return re.sub(r"\bIF\(", "SE(", texto)


def _calcular(formula: str, celulas: dict[str, float]) -> float:
    """Só para o teste: roda em Python o texto que o próprio programa escreveu para o Excel."""
    ambiente = {
        "pi": math.pi,
        "SQRT": math.sqrt,
        "LOG10": math.log10,
        "LN": math.log,
        "EXP": math.exp,
        "SIN": math.sin,
        "COS": math.cos,
        "TAN": math.tan,
        "ABS": abs,
        "MIN": min,
        "MAX": max,
        "SE": lambda condicao, a, b: a if condicao else b,
        **celulas,
    }
    return float(eval(_em_python(formula), {"__builtins__": {}}, ambiente))  # noqa: S307


def _planilha(modelo: Modelo, sistema: g.Sistema) -> tuple[bytes, mt.Resposta]:
    u = unidades_padrao(sistema)
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    valores = {
        **{i.chave: i.padrao for i in base.grandezas if i.padrao is not None},
        **dict(base.padroes),
        **modelo.valores,
    }
    r = mt.isolar(base, modelo.alvo, valores)
    return mp.gerar_planilha(modelo.nome, base, r, u, {}), r


def _celulas(aba, livro) -> dict[str, float]:
    celulas = {}
    for nome, definido in livro.defined_names.items():
        celula = definido.attr_text.split("!")[1].replace("$", "")
        formula = str(aba[celula].value)
        linha = aba[celula].row
        # =C5*1000, ou =C5*1+273.15 nos campos em °C
        fator, _, deslocamento = formula.split("*")[1].partition("+")
        celulas[nome] = float(aba.cell(linha, 3).value) * float(fator) + float(deslocamento or 0)
    return celulas


@pytest.mark.parametrize(
    ("modelo", "sistema"),
    [
        *((m, g.SISTEMA_SOLIDOS) for m in mm.MODELOS),
        *((m, g.SISTEMA_FLUIDOS) for m in mm.MODELOS_FLUIDOS),
    ],
    ids=lambda x: getattr(x, "nome", "") or getattr(x, "chave", ""),
)
def test_formulas_do_excel_dao_o_numero_do_programa(modelo, sistema):
    conteudo, r = _planilha(modelo, sistema)
    if r.valor is None or r.faltam:
        pytest.skip("modelo sem todos os valores")
    livro = load_workbook(io.BytesIO(conteudo))
    aba = livro["Calculo"]
    celulas = _celulas(aba, livro)
    conferidas = 0
    for linha in r.conferencia:
        for fila in aba.iter_rows(min_row=2, max_col=5):  # a linha 1 é o título
            if fila[0].value == linha.nome:
                tolerancia = 0.03 if "IF(" in str(fila[1].value) else 1e-6
                assert _calcular(str(fila[1].value), celulas) == pytest.approx(
                    linha.esquerda, rel=tolerancia, abs=1e-9
                )
                assert _calcular(str(fila[2].value), celulas) == pytest.approx(
                    linha.direita, rel=tolerancia, abs=1e-9
                )
                conferidas += 1
                break
    assert conferidas == len(r.conferencia)


def test_numero_negativo_vai_entre_parenteses():
    x = sp.Symbol("x", positive=True)
    assert "(-2)" in mp.em_excel(-2 * x**2)


def test_nome_da_celula_nunca_e_reservado():
    assert mp.nome_da_celula("R") == "v_R"
    assert mp.nome_da_celula("K_1") == "v_K_1"


def test_excel_avisa_do_atrito():
    modelo = next(m for m in mm.MODELOS_FLUIDOS if m.nome == "Diâmetro mínimo do tubo")
    conteudo, _ = _planilha(modelo, g.SISTEMA_FLUIDOS)
    aba = load_workbook(io.BytesIO(conteudo))["Calculo"]
    textos = " ".join(str(c.value) for fila in aba.iter_rows() for c in fila if c.value)
    assert "Swamee-Jain" in textos


def test_mudar_um_dado_muda_a_conta():
    modelo = mm.MODELOS[0]
    conteudo, _ = _planilha(modelo, g.SISTEMA_SOLIDOS)
    livro = load_workbook(io.BytesIO(conteudo))
    aba = livro["Calculo"]
    celulas = _celulas(aba, livro)
    fila = next(f for f in aba.iter_rows(max_col=5) if f[0].value == "von Mises na fibra externa")
    antes = _calcular(str(fila[1].value), celulas)
    celulas["v_M_x"] *= 2.0
    assert _calcular(str(fila[1].value), celulas) == pytest.approx(2.0 * antes)


def test_grade_numerica_das_funcoes_novas():
    from core.montador_funcoes import fator_de_tamanho, limite_base, sensibilidade_neuber

    vetor = np.array([10.0, 30.0, 60.0])
    assert fator_de_tamanho(vetor).shape == (3,)
    assert limite_base(np.array([500.0, 1500.0]), 0).tolist() == [250.0, 700.0]
    assert math.isnan(float(sensibilidade_neuber(690.0, -1.0, 0)))


# ---------------------------------------------------------------------------
# Campos velhos depois de trocar o modelo
# ---------------------------------------------------------------------------


def test_campo_de_rodada_velha_nao_grava():
    """Achado nos cliques: a prancheta pede rodada enquanto a outra desenha, e o navegador manda
    junto os campos do modelo anterior. Eles não podem regravar os números do modelo novo."""
    from unittest import mock

    from components import montador_ui as ui

    estado = {
        "mf_revisao": 5,
        "mf_valores": {"K_L": 8.0},
        "mf_origens": {},
        "mf_adotado": None,
        "mf_v_4_K_L": 2.5,
        "mf_v_5_K_L": 3.0,
        "mf_adotado_4": 7.0,
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_digitar(mm.PARTE_SOLIDOS, "K_L", 1.0, "mf_v_4_K_L")
        assert estado["mf_valores"]["K_L"] == 8.0
        ui._ao_digitar_adotado(mm.PARTE_SOLIDOS, "mf_adotado_4", 1.0)
        assert estado["mf_adotado"] is None
        ui._ao_digitar(mm.PARTE_SOLIDOS, "K_L", 1.0, "mf_v_5_K_L")
        assert estado["mf_valores"]["K_L"] == 3.0


def test_lista_velha_nao_muda_bloco_de_outro_tipo():
    from unittest import mock

    from components import montador_ui as ui

    grafo = {"nos": [{"id": "n2", "tipo": "flexao", "opcoes": {}}], "fios": []}
    estado = {
        "mf_grafo": grafo,
        "mf_versao": 1,
        "mf_modelo_atual": "x",
        "mf_op_n2_criterio_r0": mb.GERBER,
        "mf_formula_n2": "a*b",
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_mudar_opcao(mm.PARTE_SOLIDOS, "n2", "criterio", "mf_op_n2_criterio_r0")
        ui._ao_digitar_formula(mm.PARTE_SOLIDOS, "n2", "mf_formula_n2")
    assert grafo["nos"][0]["opcoes"] == {}
    assert "portas" not in grafo["nos"][0]
