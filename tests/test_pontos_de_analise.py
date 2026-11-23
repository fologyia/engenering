"""Marco 4 do esboço: pontos de análise presos à geometria, o I_xy na flexão, o limite num ponto e
as medidas com nome que o Montador lê do desenho."""

from __future__ import annotations

import copy
import math
from unittest import mock

import numpy as np
import pytest

from core import elementos_vigas as ev
from core import esboco as eb
from core import esboco_secao as es
from core import montador as mt
from core import montador_blocos as mb
from core import montador_desenho as md
from core import montador_modelos  # noqa: F401  (registra os blocos)
from core import montador_secoes as ms
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from tests import test_esboco_edicao as te
from tests.test_esboco import _linhas, chapa_com_furos

SY = {"S_y": 250.0, "n": 1.0}


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield
        ev._analisar_desenho.cache_clear()


def _salvar(nome: str, dados: dict) -> None:
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    partes = modelo.regioes.partes(modelo.sistema.q0[None, :])
    catalogo.salvar_perfil(
        sd.perfil_da_secao(nome, sd.analisar(partes)),
        desenho=tuple(p.como_dicionario() for p in partes),
        esboco=dados,
    )


def _montar(*nos: tuple[str, dict], fios: list[tuple[int, str, int, str]] | None = None):
    """Os blocos em fila (a saída de um na primeira entrada do próximo), ou pelos fios dados."""
    lista = [{"id": f"n{i}", "tipo": t, "opcoes": o} for i, (t, o) in enumerate(nos)]
    if fios is None:
        fios = [
            (
                i,
                mb.POR_CHAVE[a["tipo"]].saidas[0].chave,
                i + 1,
                mb.POR_CHAVE[b["tipo"]].entradas[0].chave,
            )
            for i, (a, b) in enumerate(zip(lista, lista[1:], strict=False))
        ]
    ligacoes = [
        {"de": f"n{a}", "saida": sa, "para": f"n{b}", "entrada": eb_} for a, sa, b, eb_ in fios
    ]
    return mt.montar(mt.grafo_de_dados({"nos": lista, "fios": ligacoes}))


def _com_pontos(dados: dict, *pontos: dict) -> dict:
    dados = copy.deepcopy(dados)
    dados["analises"] = list(pontos)
    return dados


def cantoneira() -> dict:
    """L 100 × 100 × 10 sem letras: aba de baixo e aba da esquerda, canto no zero."""
    return {
        "pontos": {
            "a": [0, 0],
            "b": [100, 0],
            "c": [100, 10],
            "d": [10, 10],
            "e": [10, 100],
            "f": [0, 100],
        },
        "curvas": _linhas(("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "a")),
    }


def _cantoneira_a_mao() -> tuple[float, float, float, float, float]:
    """xc, yc, Ix, Iy, Ixy da cantoneira pelos dois retângulos."""
    retangulos = [(50.0, 5.0, 100.0, 10.0), (5.0, 55.0, 10.0, 90.0)]  # centro, b, h
    area = sum(b * h for _, _, b, h in retangulos)
    xc = sum(x * b * h for x, _, b, h in retangulos) / area
    yc = sum(y * b * h for _, y, b, h in retangulos) / area
    ix = sum(b * h**3 / 12 + b * h * (y - yc) ** 2 for _, y, b, h in retangulos)
    iy = sum(h * b**3 / 12 + b * h * (x - xc) ** 2 for x, _, b, h in retangulos)
    ixy = sum(b * h * (x - xc) * (y - yc) for x, y, b, h in retangulos)
    return xc, yc, ix, iy, ixy


# ---------------------------------------------------------------------------
# O esboço guarda os pontos e as medidas com nome
# ---------------------------------------------------------------------------


def test_pontos_e_medidas_vao_e_voltam_no_dicionario():
    dados = _com_pontos(
        chapa_com_furos(),
        {"id": "a1", "nome": "A", "curva": "c1", "t": 0.25},
        {"id": "a2", "nome": "B", "ponto": "p3"},
    )
    dados["cotas"].append(
        {
            "id": "d20",
            "tipo": "distancia",
            "pontos": ["f1"],
            "centro": True,
            "modo": "h",
            "expressao": "25",
            "referencia": True,
            "nome": "e",
        }
    )
    esboco = eb.esboco_de_dicionario(dados)
    assert [a.nome for a in esboco.analises] == ["A", "B"]
    assert [c.nome for c in esboco.medidas_com_nome()] == ["e"]
    de_novo = eb.esboco_de_dicionario(esboco.como_dicionario())
    assert de_novo.analises == esboco.analises
    assert de_novo.medidas_com_nome() == esboco.medidas_com_nome()


def test_ponto_de_curva_apagada_sai_sem_erro():
    dados = _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "A", "curva": "sumiu", "t": 0.5})
    assert eb.esboco_de_dicionario(dados).analises == ()


@pytest.mark.parametrize(
    "cota, texto",
    [
        ({"nome": "e", "referencia": False}, "só a de referência"),
        ({"nome": "d", "referencia": True}, "nome de uma letra"),
        ({"nome": "2x", "referencia": True}, "não serve de nome"),
        ({"centro": True, "referencia": False}, "precisa ser de referência"),
    ],
)
def test_nome_e_centro_so_na_cota_de_referencia(cota, texto):
    dados = chapa_com_furos()
    base = {"id": "d20", "tipo": "distancia", "pontos": ["f1", "f2"], "expressao": "50"}
    if cota.get("centro"):
        base["pontos"] = ["f1"]
    dados["cotas"].append({**base, **cota})
    with pytest.raises(eb.ErroDeEsboco, match=texto):
        eb.esboco_de_dicionario(dados)


def test_nomes_de_ponto_repetidos_sao_recusados():
    dados = _com_pontos(
        chapa_com_furos(),
        {"id": "a1", "nome": "A", "ponto": "p3"},
        {"id": "a2", "nome": "A", "ponto": "p4"},
    )
    with pytest.raises(eb.ErroDeEsboco, match="Dois pontos"):
        eb.esboco_de_dicionario(dados)


def test_posicao_do_ponto_na_linha_no_circulo_e_no_arco():
    dados = _com_pontos(
        chapa_com_furos(),
        {"id": "a1", "nome": "topo do furo", "curva": "c1", "t": 0.25},
        {"id": "a2", "nome": "meio de baixo", "curva": "l1", "t": 0.5},
        {"id": "a3", "nome": "canto", "ponto": "p3"},
    )
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    q = modelo.sistema.q0[None, :]
    posicoes = [
        tuple(float(v[0]) for v in eb.posicao_da_analise(modelo.sistema, a, q))
        for a in modelo.esboco.analises
    ]
    assert posicoes[0] == pytest.approx((-25.0, 5.0), abs=1e-6)
    assert posicoes[1] == pytest.approx((0.0, -10.0), abs=1e-6)
    assert posicoes[2] == pytest.approx((50.0, 10.0), abs=1e-6)

    arco = {
        "pontos": {"c": [0, 0], "i": [10, 0], "f": [0, 10]},
        "curvas": [{"id": "k", "tipo": "arco", "pontos": ["c", "i", "f"]}],
    }
    sistema = eb.Sistema(eb.esboco_de_dicionario(arco))
    meio = eb.PontoDeAnalise("a", "M", curva="k", t=0.5)
    x, y = eb.posicao_da_analise(sistema, meio, sistema.q0[None, :])
    assert (float(x[0]), float(y[0])) == pytest.approx((10 / math.sqrt(2), 10 / math.sqrt(2)))


def test_cota_ate_o_centro_de_gravidade_mede_pelo_centro():
    dados = chapa_com_furos()
    cota = eb.Cota("d20", eb.DISTANCIA, ("f1",), modo=eb.MODO_H, referencia=True, centro=True)
    sistema = eb.Sistema(eb.esboco_de_dicionario(dados))
    q = sistema.q0[None, :]
    medida = eb.medida_da_cota(sistema, cota, q, (np.array([3.0]), np.array([0.0])))
    assert float(medida[0]) == pytest.approx(28.0)


# ---------------------------------------------------------------------------
# As tensões no ponto marcado
# ---------------------------------------------------------------------------


def test_ponto_marcado_anda_com_a_letra():
    dados = _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "A", "curva": "c1", "t": 0.25})
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    p = next(i for i, ponto in enumerate(modelo.pontos, start=1) if ponto.nome == "ponto A")
    numeros = modelo.numeros({"d": np.array([10.0, 16.0])}, (100 * p + es.SX, es.IX))
    # Furo no centro de gravidade: no topo dele, σ por unidade de M_x é (d/2)/I_x.
    for i, d in enumerate((10.0, 16.0)):
        assert numeros[100 * p + es.SX][i] == pytest.approx((d / 2) / numeros[es.IX][i])


def test_tau_no_ponto_marcado_e_v_q_sobre_i_b_na_altura_dele():
    dados = _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "B", "curva": "l1", "t": 0.25})
    dados["cotas"] = [c for c in dados["cotas"] if c["expressao"] != "d"]
    dados["cotas"].append({"id": "d5", "tipo": "diametro", "curvas": ["c1"], "expressao": "10"})
    dados["variaveis"] = []
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    p = next(i for i, ponto in enumerate(modelo.pontos, start=1) if ponto.nome == "ponto B")
    n = modelo.numeros({}, (100 * p + es.TVY, 100 * p + es.SX, es.IX))
    # Na borda de baixo, Q = 0: τ zero, e σ por M_x é c/I_x.
    assert n[100 * p + es.TVY][0] == pytest.approx(0.0, abs=1e-12)
    assert n[100 * p + es.SX][0] == pytest.approx(10.0 / n[es.IX][0])


def test_cantoneira_usa_o_ixy_e_bate_com_a_conta_de_mao(catalogo_vazio):
    _salvar("L 100x10", cantoneira())
    m = _montar(
        ("desenhada", {"desenho": "L 100x10"}),
        ("flexao", {}),
        ("von_mises", {}),
        (mb.RESULTADO, {}),
    )
    assert not m.erros
    assert any("I_xy" in h for h in m.hipoteses)
    r = mt.isolar(m, "M_x", {"s": 1.0, **SY})
    xc, yc, ix, iy, ixy = _cantoneira_a_mao()
    vertices = [(0, 0), (100, 0), (100, 10), (10, 10), (10, 100), (0, 100)]
    d = ix * iy - ixy**2
    pior = max(abs((y - yc) * iy - (x - xc) * ixy) / d for x, y in vertices)
    assert r.valor == pytest.approx(250.0 / pior, rel=1e-6)
    # M·c/I daria mais momento: sem o I_xy, a conta ficava contra a segurança.
    assert r.valor < 250.0 * ix / (100.0 - yc)


def test_secao_simetrica_sem_pontos_continua_no_caminho_de_antes(catalogo_vazio):
    dados = chapa_com_furos()
    for cota in dados["cotas"]:
        if cota["expressao"] == "d":
            cota["expressao"] = "10"
    dados["variaveis"] = []
    _salvar("Chapa fixa", dados)
    secao = ms.desenhada("Chapa fixa")
    assert not any("I_xy" in h for h in secao.hipoteses)
    assert not any(p.nome.startswith("ponto ") for p in secao.pontos)


def test_ponto_marcado_entra_no_von_mises_e_no_limite_proprio(catalogo_vazio):
    _salvar(
        "Chapa A",
        _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "A", "curva": "c1", "t": 0.25}),
    )
    m = _montar(
        ("desenhada", {"desenho": "Chapa A"}),
        ("flexao", {}),
        ("limite_no_ponto", {"ponto": "A", "tensao": md.VON_MISES}),
        (mb.RESULTADO, {}),
    )
    assert not m.erros, m.erros
    assert [c.nome for c in m.condicoes] == ["von Mises no ponto A (limite próprio)"]
    r = mt.isolar(m, "M_x", {"d": 10.0, "sigma_lp": 100.0})
    ix = 100 * 20**3 / 12 - 2 * math.pi * 10**4 / 64
    assert r.valor == pytest.approx(100.0 * ix / 5.0, rel=1e-6)

    com_criterio = _montar(
        ("desenhada", {"desenho": "Chapa A"}), ("flexao", {}), ("von_mises", {}), (mb.RESULTADO, {})
    )
    assert any(c.ponto == "ponto A" for c in com_criterio.condicoes)
    assert any(c.nome == "von Mises no ponto A" for c in com_criterio.condicoes)


def test_limite_num_ponto_que_a_secao_nao_tem(catalogo_vazio):
    _salvar(
        "Chapa A",
        _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "A", "curva": "c1", "t": 0.25}),
    )
    m = _montar(
        ("desenhada", {"desenho": "Chapa A"}),
        ("flexao", {}),
        ("limite_no_ponto", {"ponto": "A"}),
        (mb.RESULTADO, {}),
    )
    assert not m.erros
    assert md.SEM_PONTO in md._pontos() and "A" in md._pontos()
    # Ponto escolhido que não é desta seção: a mensagem diz quais ela tem.
    with mock.patch.object(ev, "pontos_dos_desenhos", return_value=("A", "Z")):
        m = _montar(
            ("desenhada", {"desenho": "Chapa A"}),
            ("flexao", {}),
            ("limite_no_ponto", {"ponto": "Z"}),
            (mb.RESULTADO, {}),
        )
    assert any("não tem o ponto Z" in texto and "A" in texto for _, texto in m.erros)


# ---------------------------------------------------------------------------
# A medida com nome
# ---------------------------------------------------------------------------


def _chapa_com_medidas() -> dict:
    dados = chapa_com_furos()
    dados["cotas"] += [
        {
            "id": "d20",
            "tipo": "diametro",
            "curvas": ["c2"],
            "expressao": "10",
            "referencia": True,
            "nome": "d_2",
        },
        {
            "id": "d21",
            "tipo": "distancia",
            "pontos": ["f1"],
            "centro": True,
            "modo": "h",
            "expressao": "25",
            "referencia": True,
            "nome": "e",
        },
    ]
    return dados


def test_medida_com_nome_muda_com_a_letra(catalogo_vazio):
    _salvar("Chapa e", _chapa_com_medidas())
    rotulos = md._medidas()
    assert md.rotulo_da_medida("d_2", "Chapa e") in rotulos
    valor, grandezas = md.medida_do_desenho(md.rotulo_da_medida("d_2", "Chapa e"))
    assert [g.chave for g in grandezas] == ["d"]
    d = grandezas[0].simbolo
    for numero in (10.0, 14.0):
        assert float(valor.subs(d, numero).evalf()) == pytest.approx(numero)
    braco, _ = md.medida_do_desenho(md.rotulo_da_medida("e", "Chapa e"))
    assert float(braco.subs(d, 12.0).evalf()) == pytest.approx(25.0)


def test_medida_do_desenho_vira_o_braco_da_forca(catalogo_vazio):
    _salvar("Chapa e", _chapa_com_medidas())
    m = _montar(
        ("desenhada", {"desenho": "Chapa e"}),
        ("flexao", {}),
        ("von_mises", {}),
        (mb.RESULTADO, {}),
        ("medida_do_desenho", {"medida": md.rotulo_da_medida("e", "Chapa e")}),
        fios=[
            (0, "saida", 1, "entrada"),
            (1, "saida", 2, "entrada"),
            (2, "condicao", 3, "condicoes"),
            (4, "medida", 1, "distancia"),
        ],
    )
    assert not m.erros, m.erros
    r = mt.isolar(m, "F_xx", {"d": 10.0, **SY})
    ix = 100 * 20**3 / 12 - 2 * math.pi * 10**4 / 64
    # M = F·e com e = 25 mm, do desenho: F = σ·I/(c·e).
    assert r.valor == pytest.approx(250.0 * ix / (10.0 * 25.0), rel=1e-6)


def test_medida_sem_letras_anda_com_a_escala(catalogo_vazio):
    dados = _chapa_com_medidas()
    for cota in dados["cotas"]:
        if cota["expressao"] == "d":
            cota["expressao"] = "10"
    dados["variaveis"] = []
    _salvar("Chapa fixa e", dados)
    valor, grandezas = md.medida_do_desenho(md.rotulo_da_medida("e", "Chapa fixa e"))
    assert [g.chave for g in grandezas] == ["s"]
    assert float(valor.subs(grandezas[0].simbolo, 2.0)) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Na prancheta (Node): prender, reatar depois de uma edição, renomear
# ---------------------------------------------------------------------------

precisa_do_node = pytest.mark.skipif(te.NODE is None, reason="Node não instalado")


@precisa_do_node
def test_ponto_novo_prende_no_canto_na_linha_ou_avisa():
    esboco = te._esboco(te._ret("a", -50, -10, 50, 10))
    r = te._node(
        esboco,
        """passo(edNovaAnalise(e, 50, 10, 1))
passo(edNovaAnalise(e, 0, -10.2, 1))
const longe = edNovaAnalise(e, 0, 0, 1)
if (!longe.erro) throw new Error("devia avisar")""",
    )
    a, b = r["esboco"]["analises"]
    assert (a["nome"], a["ponto"]) == ("A", "a3")
    assert (b["nome"], b["curva"]) == ("B", "al0")
    assert b["t"] == pytest.approx(0.5)
    lido = eb.esboco_de_dicionario(r["esboco"])
    assert [p.nome for p in lido.analises] == ["A", "B"]


@precisa_do_node
def test_ponto_volta_a_se_prender_depois_de_dividir_e_de_unir():
    esboco = te._esboco(te._ret("a", -50, -10, 50, 10), te._ret("b", -10, -60, 10, 0))
    r = te._node(
        esboco,
        """passo(edNovaAnalise(e, 30, 10, 1))
passo(edNovaAnalise(e, -10, -60, 1))
passo(edDividir(e, "al2", 0, 10))
passo(edUnir(e))""",
    )
    assert r["convergiu"] and r["lacos"] == 1
    analises = {a["nome"]: a for a in r["esboco"]["analises"]}
    assert set(analises) == {"A", "B"}
    for nome, lugar in (("A", (30.0, 10.0)), ("B", (-10.0, -60.0))):
        assert analises[nome]["xy"] == pytest.approx(lugar, abs=1e-6)
    lido = eb.esboco_de_dicionario(r["esboco"])
    sistema = eb.Sistema(lido)
    for a in lido.analises:
        x, y = eb.posicao_da_analise(sistema, a, sistema.q0[None, :])
        assert (float(x[0]), float(y[0])) == pytest.approx(analises[a.nome]["xy"], abs=1e-6)


@precisa_do_node
def test_renomear_recusa_nome_repetido_e_nome_ruim():
    esboco = te._esboco(te._ret("a", -50, -10, 50, 10))
    r = te._node(
        esboco,
        """passo(edNovaAnalise(e, 50, 10, 1))
passo(edNovaAnalise(e, -50, 10, 1))
if (!edRenomearAnalise(e, "a2", "A").erro) throw new Error("repetido passou")
if (!edRenomearAnalise(e, "a2", " -x").erro) throw new Error("nome ruim passou")
passo(edRenomearAnalise(e, "a2", "solda 1"))""",
    )
    assert [a["nome"] for a in r["esboco"]["analises"]] == ["A", "solda 1"]


@precisa_do_node
def test_ponto_anda_junto_quando_a_curva_dele_e_movida():
    esboco = te._esboco(te._ret("a", -50, -10, 50, 10))
    esboco["pontos"]["fc"] = [-20, 0]
    esboco["curvas"].append({"id": "furo", "tipo": "circulo", "pontos": ["fc"], "raio": 4})
    r = te._node(
        esboco,
        """passo(edNovaAnalise(e, -20, 4, 0.5))
passo(edTransformar(e, ["furo"], 15, 0, 0, [-20, 0], false))""",
    )
    (a,) = r["esboco"]["analises"]
    assert a["curva"] == "furo"
    assert a["xy"] == pytest.approx((-5.0, 4.0), abs=1e-6)


def test_tensao_no_ponto_pela_malha_bate_com_m_c_sobre_i():
    partes = [sd.Parte(sd.RET, 0.0, 0.0, 20.0, 40.0)]
    analise = sd.analisar(partes)
    mapa = sd.tensoes(analise, 0.0, 2.0, 0.0)  # M_x = 2 kN·m
    topo = sd.tensao_no_ponto(analise, mapa, 0.0, 20.0)
    ix = 20.0 * 40.0**3 / 12.0
    assert abs(topo.sigma) == pytest.approx(2e6 * 20.0 / ix, rel=1e-6)
    assert topo.tau == pytest.approx(0.0, abs=1e-9)
    assert topo.mises == pytest.approx(abs(topo.sigma))


def test_posicoes_dos_pontos_para_a_tabela_da_desenhar_secao():
    from components.desenhar_secao_ui import posicoes_dos_pontos_de_analise

    bruto = _com_pontos(chapa_com_furos(), {"id": "a1", "nome": "A", "curva": "c1", "t": 0.25})
    # Como a prancheta manda: o esboço já resolvido.
    dados = eb.esboco_resolvido(eb.esboco_de_dicionario(bruto)).como_dicionario()
    assert posicoes_dos_pontos_de_analise(dados) == [
        ("A", pytest.approx(-25.0), pytest.approx(5.0))
    ]
    assert posicoes_dos_pontos_de_analise({"pontos": "ruim"}) == []
