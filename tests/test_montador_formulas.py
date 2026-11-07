"""Montador de fórmulas: a fórmula isolada bate com a conta de livro e com ela mesma."""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from core import elementos_vigas as ev
from core import montador as mt
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import secao_desenhada as sd
from core import section_catalog as catalogo

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def cadeia(*tipos: str, opcoes: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Blocos em fila: seção, esforços, critério e resultado."""
    nos = [
        {"id": f"n{i}", "tipo": tipo, "opcoes": (opcoes or {}).get(tipo, {})}
        for i, tipo in enumerate(tipos)
    ]
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(
            {"de": a["id"], "saida": saida.chave, "para": b["id"], "entrada": entrada.chave}
        )
    return nos, fios


def montar(*tipos: str, opcoes: dict | None = None) -> mt.Montagem:
    nos, fios = cadeia(*tipos, opcoes=opcoes)
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


def letra(chave: str) -> sp.Symbol:
    return sp.Symbol(chave, positive=True)


def iguais(a: sp.Expr, b: sp.Expr) -> bool:
    """Compara em números soltos: a forma escrita pode variar sem mudar a conta."""
    livres = sorted(a.free_symbols | b.free_symbols, key=lambda s: s.name)
    trocas = {s: 1.37 + 0.61 * i for i, s in enumerate(livres)}
    trocas.update({s: 0.5 for s in livres if s.name == "k"})  # relação entre diâmetros: abaixo de 1
    return float(a.subs(trocas)) == pytest.approx(float(b.subs(trocas)), rel=1e-9)


def formula(r: mt.Resposta, nome_do_ponto: str) -> sp.Expr:
    item = next(i for i in r.isoladas if nome_do_ponto in i.condicao.nome)
    assert item.formula is not None
    return item.formula.expressao


# ---------------------------------------------------------------------------
# Contas de livro
# ---------------------------------------------------------------------------


def test_eixo_com_flexao_e_torcao_von_mises():
    """Shigley: d³ = 16·n/(π·S_y)·√(4·M² + 3·T²)."""
    m = montar("circular", "flexao", "torcao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {})
    d, M, T, S, n = letra("d"), letra("M_x"), letra("T"), letra("S_y"), letra("n")
    assert d not in formula(r, "fibra").free_symbols
    esperado = (16 * n * sp.sqrt(4 * M**2 + 3 * T**2) / (sp.pi * S)) ** sp.Rational(1, 3)
    assert iguais(formula(r, "fibra"), esperado)


def test_eixo_com_flexao_e_torcao_tresca():
    m = montar("circular", "flexao", "torcao", "tresca", mb.RESULTADO)
    r = mt.isolar(m, "d", {})
    M, T, S, n = letra("M_x"), letra("T"), letra("S_y"), letra("n")
    esperado = (32 * n * sp.sqrt(M**2 + T**2) / (sp.pi * S)) ** sp.Rational(1, 3)
    assert iguais(formula(r, "fibra"), esperado)


def test_retangular_com_flexao_isola_a_altura():
    m = montar("retangular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {})
    M, b, S, n = letra("M_x"), letra("b"), letra("S_y"), letra("n")
    assert iguais(formula(r, "fibra"), sp.sqrt(6 * M * n / (b * S)))


def test_retangular_com_cortante_isola_a_altura():
    m = montar("retangular", "cortante", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {})
    V, b, S, n = letra("V_y"), letra("b"), letra("S_y"), letra("n")
    assert iguais(formula(r, "linha neutra"), 3 * sp.sqrt(3) * V * n / (2 * b * S))


def test_flexao_e_cortante_nao_somam_os_maximos():
    """A fibra não tem τ, e a linha neutra não tem σ: quem manda é um dos dois pontos."""
    m = montar("retangular", "flexao", "cortante", "von_mises", mb.RESULTADO)
    valores = {"b": 50.0, "M_x": 2e6, "V_y": 1e4, "S_y": 250.0, "n": 2.0}
    r = mt.isolar(m, "h", valores)
    assert r.sentido == mt.MINIMO
    assert r.valor == pytest.approx(math.sqrt(6 * 2e6 * 2 / (50 * 250)))
    assert "fibra" in r.manda.condicao.nome
    nomes = [i.condicao.nome for i in r.isoladas]
    assert len(nomes) == 2


def test_cortante_manda_em_viga_curta():
    m = montar("retangular", "flexao", "cortante", "von_mises", mb.RESULTADO)
    valores = {"b": 50.0, "M_x": 1e3, "V_y": 5e4, "S_y": 250.0, "n": 2.0}
    r = mt.isolar(m, "h", valores)
    assert "linha neutra" in r.manda.condicao.nome
    assert r.valor == pytest.approx(3 * math.sqrt(3) * 5e4 * 2 / (2 * 50 * 250))


def test_torcao_e_cortante_somam_na_linha_neutra_do_eixo():
    m = montar("circular", "cortante", "torcao", "von_mises", mb.RESULTADO)
    valores = {"d": 30.0, "S_y": 300.0, "n": 1.0, "T": 1e5}
    r = mt.isolar(m, "V_y", valores)
    a = math.pi * 30**2 / 4
    tau_t = 16 * 1e5 / (math.pi * 30**3)
    esperado = (300.0 / math.sqrt(3) - tau_t) * 3 * a / 4
    assert r.valor == pytest.approx(esperado)
    assert r.sentido == mt.MAXIMO


# ---------------------------------------------------------------------------
# Em função do quê
# ---------------------------------------------------------------------------


def test_em_funcao_do_momento():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "M_x", {})
    d, S, n = letra("d"), letra("S_y"), letra("n")
    assert iguais(formula(r, "fibra"), sp.pi * d**3 * S / (32 * n))


def test_em_funcao_do_material():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "S_y", {"d": 20.0, "M_x": 1e5, "n": 2.0})
    assert r.valor == pytest.approx(2 * 32 * 1e5 / (math.pi * 20**3))
    assert r.sentido == mt.MINIMO


def test_em_funcao_do_fator_de_seguranca():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "n", {"d": 20.0, "M_x": 1e5, "S_y": 300.0})
    assert r.valor == pytest.approx(300 * math.pi * 20**3 / (32 * 1e5))
    assert r.sentido == mt.MAXIMO


def test_cada_letra_vale_de_volta_na_conta():
    """Isola cada letra e põe de volta: a condição precisa fechar em 100 %."""
    m = montar("retangular", "flexao", "cortante", "torcao", "von_mises", mb.RESULTADO)
    base = {"b": 40.0, "h": 90.0, "M_x": 3e6, "V_y": 2e4, "T": 1e5, "S_y": 250.0, "n": 1.5}
    for chave in base:
        outros = {k: v for k, v in base.items() if k != chave}
        r = mt.isolar(m, chave, outros)
        assert r.valor is not None, chave
        maior = max(linha.uso for linha in r.conferencia)
        assert maior == pytest.approx(1.0, rel=1e-6), chave


def test_letra_sem_valor_fica_na_formula():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"S_y": 250.0, "n": 2.0})
    assert [item.chave for item in r.faltam] == ["M_x"]
    assert r.valor is None
    assert "M_{x}" in r.isoladas[0].com_numeros


def test_equacao_sem_forma_fechada_acha_a_raiz_por_numero():
    """Flexão com normal numa seção circular: a equação em d fica de grau 3 com termo em d."""
    m = montar("circular", "flexao", "normal", "torcao", "von_mises", mb.RESULTADO)
    valores = {"M_x": 1e6, "N": 1e5, "T": 5e5, "S_y": 300.0, "n": 2.0}
    r = mt.isolar(m, "d", valores)
    item = next(i for i in r.isoladas if "fibra" in i.condicao.nome)
    assert item.formula is None
    assert r.valor is not None
    assert max(linha.uso for linha in r.conferencia) == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# Outras seções
# ---------------------------------------------------------------------------


def test_tubo_com_relacao_fica_em_forma_fechada():
    m = montar("tubo_relacao", "flexao", "torcao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {})
    M, T, S, n, k = letra("M_x"), letra("T"), letra("S_y"), letra("n"), letra("k")
    esperado = (16 * n * sp.sqrt(4 * M**2 + 3 * T**2) / (sp.pi * S * (1 - k**4))) ** sp.Rational(
        1, 3
    )
    assert iguais(formula(r, "fibra"), esperado)


def test_tubo_com_parede_acha_por_numero():
    m = montar("tubo_parede", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"t": 3.0, "M_x": 1e6, "S_y": 250.0, "n": 1.5})
    assert r.valor is not None and r.valor > 6.0
    d, t = r.valor, 3.0
    i = math.pi * (d**4 - (d - 2 * t) ** 4) / 64
    assert 1e6 * (d / 2) / i == pytest.approx(250 / 1.5, rel=1e-6)


def test_perfil_i_tem_tres_pontos_e_a_juncao_pode_mandar():
    m = montar("perfil_i", "flexao", "cortante", "von_mises", mb.RESULTADO)
    r = mt.isolar(
        m,
        "S_y",
        {"b_f": 100.0, "h": 200.0, "t_f": 10.0, "t_w": 6.0, "M_x": 8e7, "V_y": 2e5, "n": 1.0},
    )
    assert len(r.isoladas) == 3
    assert "junção" in r.manda.condicao.nome
    i = (100 * 200**3 - 94 * 180**3) / 12
    sigma = 8e7 * 90 / i
    tau = 2e5 * (100 * 10 * 95) / (i * 6)
    assert r.valor == pytest.approx(math.sqrt(sigma**2 + 3 * tau**2))


def test_sem_torcao_nao_importa_qual_lado_e_o_maior():
    m = montar("retangular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {"b": 100.0, "M_x": 1e5, "S_y": 250.0, "n": 1.5})
    assert r.valor < 100.0
    assert not r.alertas


def test_lado_maior_errado_avisa():
    m = montar("retangular", "torcao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {"b": 100.0, "T": 1e5, "S_y": 250.0, "n": 1.5})
    assert any("Lado maior" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# Blocos de origem, deformação e fadiga
# ---------------------------------------------------------------------------


def viga_com_flecha() -> mt.Montagem:
    nos = [
        {"id": "s", "tipo": "retangular"},
        {"id": "v", "tipo": "balanco_ponta"},
        {"id": "f", "tipo": "flexao"},
        {"id": "c", "tipo": "cortante"},
        {"id": "e", "tipo": "von_mises"},
        {"id": "d", "tipo": "flecha"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "f", "entrada": "entrada"},
        {"de": "f", "saida": "saida", "para": "c", "entrada": "entrada"},
        {"de": "c", "saida": "saida", "para": "e", "entrada": "entrada"},
        {"de": "s", "saida": "saida", "para": "d", "entrada": "entrada"},
        {"de": "v", "saida": "M", "para": "f", "entrada": "valor"},
        {"de": "v", "saida": "V", "para": "c", "entrada": "valor"},
        {"de": "v", "saida": "flecha", "para": "d", "entrada": "flecha"},
        {"de": "e", "saida": "condicao", "para": "r", "entrada": "condicoes"},
        {"de": "d", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


def test_fio_de_valor_troca_a_letra_pela_formula_da_viga():
    m = viga_com_flecha()
    chaves = {item.chave for item in m.grandezas}
    assert "F" in chaves and "L" in chaves
    assert "M_x" not in chaves and "V_y" not in chaves


def test_flecha_manda_em_viga_comprida():
    m = viga_com_flecha()
    valores = {
        "b": 50.0,
        "F": 1000.0,
        "L": 3000.0,
        "S_y": 250.0,
        "n": 1.5,
        "E": 200000.0,
        "r_delta": 300.0,
    }
    r = mt.isolar(m, "h", valores)
    assert r.manda.condicao.nome == "Flecha"
    i = 1000 * 3000**3 / (3 * 200000 * (3000 / 300))
    assert r.valor == pytest.approx((12 * i / 50) ** (1 / 3))


def test_torque_vem_da_potencia():
    nos = [
        {"id": "s", "tipo": "circular"},
        {"id": "p", "tipo": "potencia"},
        {"id": "t", "tipo": "torcao"},
        {"id": "e", "tipo": "von_mises"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "t", "entrada": "entrada"},
        {"de": "p", "saida": "T", "para": "t", "entrada": "valor"},
        {"de": "t", "saida": "saida", "para": "e", "entrada": "entrada"},
        {"de": "e", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    # 10 kW a 1500 rpm: T = 63,66 N·m.
    r = mt.isolar(m, "d", {"P": 10e6, "n_rot": 1500.0, "S_y": 300.0, "n": 2.0})
    t = 10e6 * 30 / (math.pi * 1500)
    assert t == pytest.approx(63662, rel=1e-3)
    assert r.valor == pytest.approx((16 * 2 * math.sqrt(3) * t / (math.pi * 300)) ** (1 / 3))


def test_flambagem_de_euler_isola_o_diametro():
    nos = [
        {"id": "s", "tipo": "circular"},
        {"id": "f", "tipo": "flambagem"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "f", "entrada": "entrada"},
        {"de": "f", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    r = mt.isolar(m, "d", {"N": 1e4, "E": 200000.0, "L": 2000.0, "K": 1.0, "n": 2.0})
    i = 2 * 1e4 * 2000**2 / (math.pi**2 * 200000)
    assert r.valor == pytest.approx((64 * i / math.pi) ** 0.25)


def test_euler_em_coluna_curta_avisa():
    nos = [
        {"id": "s", "tipo": "circular"},
        {"id": "m", "tipo": "material"},
        {"id": "f", "tipo": "flambagem"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "f", "entrada": "entrada"},
        {"de": "m", "saida": "saida", "para": "f", "entrada": "material"},
        {"de": "f", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    r = mt.isolar(m, "d", {"N": 1e6, "E": 200000.0, "L": 300.0, "K": 1.0, "n": 2.0, "S_y": 250.0})
    assert any("Johnson" in a for a in r.alertas)


def test_giro_por_torcao():
    nos = [
        {"id": "s", "tipo": "circular"},
        {"id": "g", "tipo": "giro"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "g", "entrada": "entrada"},
        {"de": "g", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    fi = math.radians(1.0)
    r = mt.isolar(m, "d", {"T": 1e6, "L": 1000.0, "G": 80000.0, "phi_adm": fi})
    j = 1e6 * 1000 / (80000 * fi)
    assert r.valor == pytest.approx((32 * j / math.pi) ** 0.25)


def test_de_goodman_bate_com_shigley():
    """Shigley 7-8: 1/n = 16/(π·d³)·[√(4·(K_f·M_a)²)/S_e + √(3·(K_fs·T_m)²)/S_ut]."""
    m = montar("circular", "goodman", mb.RESULTADO)
    valores = {
        "M_a": 142e3,
        "M_m": 0.0,
        "T_a": 0.0,
        "T_m": 124e3,
        "K_f": 1.7,
        "K_fs": 1.5,
        "S_e": 195.0,
        "S_ut": 735.0,
        "n": 1.5,
    }
    r = mt.isolar(m, "d", valores)
    d3 = 16 * 1.5 / math.pi * (2 * 1.7 * 142e3 / 195 + math.sqrt(3) * 1.5 * 124e3 / 735)
    assert r.valor == pytest.approx(d3 ** (1 / 3), rel=1e-6)


def test_pressao_em_tubo_da_estado_biaxial():
    m = montar("tubo_parede", "pressao_interna", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "p", {"d": 100.0, "t": 2.0, "S_y": 250.0, "n": 1.0})
    # σ_c = 2·σ_l: von Mises = √3/2·σ_c.
    assert r.valor == pytest.approx(250 / (math.sqrt(3) / 2) * 2 * 2 / 100)


def test_pressao_em_seccao_maciça_diz_o_que_falta():
    m = montar("circular", "pressao_interna", "von_mises", mb.RESULTADO)
    assert any("tubo" in erro for _, erro in m.erros)


def test_tresca_biaxial_olha_as_duas_principais():
    m = montar("tubo_parede", "pressao_interna", "tresca", mb.RESULTADO)
    r = mt.isolar(m, "p", {"d": 100.0, "t": 2.0, "S_y": 250.0, "n": 1.0})
    assert r.valor == pytest.approx(250 * 2 * 2 / 100)


def test_concentracao_multiplica_as_tensoes():
    m = montar("circular", "flexao", "concentracao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "M_x", {"d": 20.0, "S_y": 300.0, "n": 1.0, "K_t": 2.0, "K_ts": 1.0})
    assert r.valor == pytest.approx(300 * math.pi * 20**3 / 32 / 2)


def test_segundo_esforco_igual_ganha_outra_letra():
    m = montar("circular", "flexao", "flexao", "von_mises", mb.RESULTADO)
    chaves = [item.chave for item in m.grandezas]
    assert "M_x" in chaves and "M_x_2" in chaves


def test_material_preenche_o_limite_e_a_letra_fica():
    m = montar(
        "circular",
        "flexao",
        "von_mises",
        mb.RESULTADO,
    )
    assert "S_y" in [item.chave for item in m.grandezas]
    nos = [{"id": "m", "tipo": "material", "opcoes": {"material": "ASTM A36"}}]
    grafo = mt.grafo_de_dados({"nos": nos, "fios": []})
    assert dict(mt.montar(grafo).padroes).get("S_y", 250.0) > 0


def test_material_sugerido_quando_o_alvo_e_o_escoamento():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "S_y", {"d": 30.0, "M_x": 1e6, "n": 1.0})
    assert r.materiais


# ---------------------------------------------------------------------------
# Desenho incompleto
# ---------------------------------------------------------------------------


def test_esforco_sem_secao_diz_o_que_falta():
    m = montar("flexao", "von_mises", mb.RESULTADO)
    assert any("Ligue uma seção" in erro for _, erro in m.erros)


def test_critério_sem_esforco_diz_o_que_falta():
    m = montar("circular", "von_mises", mb.RESULTADO)
    assert any("esforço" in erro for _, erro in m.erros)


def test_resultado_sem_criterio_diz_o_que_falta():
    m = montar(mb.RESULTADO)
    assert any("critério" in erro for _, erro in m.erros)


def test_laco_nao_trava():
    nos = [{"id": "a", "tipo": "flexao"}, {"id": "b", "tipo": "cortante"}]
    fios = [
        {"de": "a", "saida": "saida", "para": "b", "entrada": "entrada"},
        {"de": "b", "saida": "saida", "para": "a", "entrada": "entrada"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    assert len(m.erros) == 2


def test_fio_de_tipo_errado_fica_de_fora():
    nos = [{"id": "a", "tipo": "balanco_ponta"}, {"id": "b", "tipo": "cortante"}]
    fios = [{"de": "a", "saida": "M", "para": "b", "entrada": "valor"}]
    assert mt.grafo_de_dados({"nos": nos, "fios": fios}).fios == ()


def test_bloco_desconhecido_fica_de_fora():
    grafo = mt.grafo_de_dados({"nos": [{"id": "a", "tipo": "nao_existe"}], "fios": []})
    assert grafo.nos == ()


def test_alvo_fora_do_desenho_explica():
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    with pytest.raises(mt.ErroDeMontagem):
        mt.isolar(m, "h", {})


def test_independente_que_nao_passa_avisa():
    """Só a altura muda a fibra. A linha neutra com b pequeno reprova sem depender de M."""
    m = montar("retangular", "flexao", "cortante", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "M_x", {"b": 1.0, "h": 2.0, "V_y": 1e6, "S_y": 250.0, "n": 1.0})
    assert any("não depende" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


def test_todo_bloco_tem_o_que_a_tela_precisa():
    for item in mb.catalogo_para_tela():
        assert item["nome"] and item["dica"] and item["formula"]
        assert item["grupo"] in mb.GRUPOS


def test_toda_opcao_tem_padrao_na_lista():
    for bloco in mb.BLOCOS:
        for opcao in bloco.opcoes:
            assert opcao.padrao in opcao.lista(), opcao.chave
            assert opcao.ajuda.endswith((".", "!", ":"))


def test_toda_grandeza_tem_ajuda():
    for item in vars(g).values():
        if isinstance(item, g.Grandeza):
            assert item.nome and item.ajuda.endswith((".", "!", ":"))


# ---------------------------------------------------------------------------
# Seção desenhada
# ---------------------------------------------------------------------------


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield


def _salvar(nome: str, partes: list[sd.Parte]) -> None:
    catalogo.salvar_perfil(
        sd.perfil_da_secao(nome, sd.analisar(partes)),
        desenho=tuple(p.como_dicionario() for p in partes),
    )


CHAPA = [sd.Parte(sd.RET, 0, 0, 50, 100)]
I_MONTADO = [
    sd.Parte(sd.RET, 0, 95, 100, 10),
    sd.Parte(sd.RET, 0, 0, 6, 180),
    sd.Parte(sd.RET, 0, -95, 100, 10),
]


def desenhada(nome: str, *tipos: str) -> mt.Montagem:
    return montar("desenhada", *tipos, mb.RESULTADO, opcoes={"desenhada": {"desenho": nome}})


def test_escala_da_secao_desenhada_bate_com_a_retangular(catalogo_vazio):
    _salvar("Chapa", CHAPA)
    m = desenhada("Chapa", "flexao", "von_mises")
    r = mt.isolar(m, "s", {"M_x": 2e7, "S_y": 250.0, "n": 1.0})
    # Escala s: b = 50·s e h = 100·s, então W = 50·100²·s³/6.
    assert r.valor == pytest.approx((2e7 / 250 / (50 * 100**2 / 6)) ** (1 / 3), rel=1e-3)


def test_secao_desenhada_acha_a_juncao(catalogo_vazio):
    _salvar("I", I_MONTADO)
    m = desenhada("I", "flexao", "cortante", "von_mises")
    nomes = [c.ponto for c in m.condicoes]
    assert any("junção" in nome for nome in nomes)
    r = mt.isolar(m, "S_y", {"s": 1.0, "M_x": 8e7, "V_y": 2e5, "n": 1.0})
    i = (100 * 200**3 - 94 * 180**3) / 12
    sigma = 8e7 * 90 / i
    tau = 2e5 * (100 * 10 * 95) / (i * 6)
    assert r.valor == pytest.approx(math.sqrt(sigma**2 + 3 * tau**2), rel=5e-3)


def test_secao_desenhada_sem_escolher_diz_o_que_fazer(catalogo_vazio):
    m = montar("desenhada", "flexao", "von_mises", mb.RESULTADO)
    assert any("Escolha uma seção salva" in erro for _, erro in m.erros)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modelo", [*mm.MODELOS, *mm.MODELOS_FLUIDOS], ids=lambda m: m.nome)
def test_todo_modelo_monta_e_responde(modelo):
    grafo = mt.grafo_de_dados(modelo.grafo())
    if modelo.conjunto is None:
        assert len(grafo.fios) == len(modelo.grafo()["fios"])
    m = mt.montar(grafo)
    assert not m.erros
    valores = dict(modelo.valores)
    for item in m.grandezas:
        if item.padrao is not None:
            valores.setdefault(item.chave, item.padrao)
    valores = {**dict(m.padroes), **valores}
    r = mt.isolar(m, modelo.alvo, valores)
    assert r.valor is not None, r.alertas
    assert max(linha.uso for linha in r.conferencia) == pytest.approx(1.0, rel=1e-5)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    assert not at.exception
    return at


def test_pagina_abre_com_a_resposta_do_modelo():
    at = abrir()
    assert any("h ≥ 37,95 mm" in s.value for s in at.success)
    assert any("fibra externa" in s.value for s in at.success)


def test_trocar_a_unidade_nao_muda_a_conta():
    at = abrir()
    at.selectbox(key="mf_u_medida").set_value("cm").run()
    assert not at.exception
    assert any("h ≥ 3,795 cm" in s.value for s in at.success)


def test_apagar_um_valor_deixa_a_letra_na_formula():
    at = abrir()
    # O AppTest não esvazia campo: aqui entra o que o callback faz. No navegador foi conferido.
    del at.session_state["mf_valores"]["M_x"]
    at.session_state["mf_revisao"] += 1
    at.run()
    assert not at.exception
    assert not at.success
    assert any("preencha M_x" in i.value for i in at.info)


def test_trocar_o_alvo_isola_outra_letra():
    at = abrir()
    at.selectbox(key="mf_alvo_escolha").set_value("b").run()
    assert not at.exception
    assert any("preencha h" in i.value for i in at.info)  # a altura agora é dado
    campo = next(n for n in at.number_input if n.label.startswith("h:"))
    campo.set_value(38.0).run()
    assert any(s.value.startswith("**b ≥") for s in at.success)


def test_todo_modelo_abre_na_tela():
    at = abrir()
    for modelo in mm.MODELOS:
        at.selectbox(key="mf_modelo").set_value(modelo.nome).run()
        assert not at.exception, modelo.nome
        assert at.success, modelo.nome


def test_limpar_nao_quebra_e_diz_como_comecar():
    at = abrir()
    at.button(key="mf_limpar").click().run()
    assert not at.exception
    assert any("Comece por um bloco" in i.value for i in at.info)


def test_edicao_da_prancheta_refaz_a_conta():
    at = abrir()
    grafo = mm.POR_NOME["Eixo com flexão e torção"].grafo()
    at.session_state["mf_grafo"] = grafo
    at.session_state["mf_alvo"] = None
    at.run()
    assert not at.exception
    # Sem T na tabela, a conta espera e a fórmula sai em letra.
    assert at.session_state["mf_alvo"] == "d"


def test_formula_com_numeros_mantem_a_raiz_da_letra():
    m = montar("retangular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {"b": 50.0, "S_y": 250.0, "n": 1.5})
    assert r"\sqrt{M_{x}}" in r.isoladas[0].com_numeros
    m = montar("circular", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"S_y": 250.0, "n": 1.5})
    assert r"\sqrt[3]{M_{x}}" in r.isoladas[0].com_numeros
