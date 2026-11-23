"""Marco 2 do esboço: as ferramentas de edição (no Node, com o solver) e a parte de testar.

As ferramentas são funções puras de ``components/esboco/edicao.js``: recebem o esboço e devolvem
outro. Cada teste confere a forma que sai, que o solver fecha com ela e, quando é o caso, que os
contornos viram uma seção (os mesmos contornos que o Python lê).
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from core import elementos_vigas as ev
from core import esboco as eb
from core import esboco_regioes as er
from core import esboco_secao as es
from core import montador as mt
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from tests.test_esboco import chapa_com_furos

RAIZ = Path(__file__).resolve().parent.parent
PASTA_JS = RAIZ / "components" / "esboco"
APP = str(RAIZ / "app.py")
NODE = shutil.which("node")
_JS = ("conta.js", "solver.js", "contornos.js", "edicao.js")


def _ret(prefixo: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    ids = [f"{prefixo}{i}" for i in range(1, 5)]
    pontos = dict(zip(ids, ([x0, y0], [x1, y0], [x1, y1], [x0, y1]), strict=True))
    curvas = [
        {"id": f"{prefixo}l{i}", "tipo": "linha", "pontos": [ids[i], ids[(i + 1) % 4]]}
        for i in range(4)
    ]
    restricoes = [
        {"id": f"{prefixo}h", "tipo": "horizontal", "curvas": [curvas[0]["id"], curvas[2]["id"]]},
        {"id": f"{prefixo}v", "tipo": "vertical", "curvas": [curvas[1]["id"], curvas[3]["id"]]},
    ]
    return {"pontos": pontos, "curvas": curvas, "restricoes": restricoes}


def _esboco(*partes: dict, variaveis: list | None = None) -> dict:
    esb = {
        "pontos": {"O": [0, 0]},
        "curvas": [],
        "restricoes": [],
        "cotas": [],
        "variaveis": variaveis or [],
    }
    for parte in partes:
        esb["pontos"].update(parte.get("pontos", {}))
        esb["curvas"] += parte.get("curvas", [])
        esb["restricoes"] += parte.get("restricoes", [])
    return esb


def _node(esboco: dict, passos: str) -> dict:
    """Roda ``passos`` (JS que muda ``e``) e devolve o esboço, os contornos e se o solver fecha."""
    programa = "".join((PASTA_JS / n).read_text(encoding="utf-8") for n in _JS)
    programa += f"""
let e = {json.dumps(esboco)}
let r = null
const passo = (res) => {{ if (res.erro) throw new Error(res.erro); e = res.esboco; r = res }}
{passos}
const s = esSistema(JSON.parse(JSON.stringify(e)))
const sol = esResolver(s, {{}}, {{ alvosIniciais: esAlvosAtuais(s, s.q0) }})
const c = esContornos(e)
console.log(JSON.stringify({{ esboco: e, convergiu: sol.convergiu, lacos: c.lacos.length + c.circulos.length,
  soltas: c.soltas.length, bifurcacoes: c.bifurcacoes.length, novas: r && r.novas }}))
"""
    saida = subprocess.run(
        [NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    if saida.returncode:
        raise AssertionError(saida.stderr[-2000:])
    return json.loads(saida.stdout)


def _regioes(esboco: dict) -> er.Regioes:
    return er.Regioes(eb.Sistema(eb.esboco_resolvido(eb.esboco_de_dicionario(esboco))))


precisa_do_node = pytest.mark.skipif(NODE is None, reason="Node não instalado")


@precisa_do_node
def test_aparar_os_dois_lados_junta_contornos_que_se_cruzam():
    """Mesa e alma desenhadas como dois retângulos: aparando, viram um T de contorno só."""
    esboco = _esboco(_ret("a", -50, -10, 50, 10), _ret("b", -10, -60, 10, 0))
    assert any(p.tipo == "cruzam" for p in _regioes(esboco).problemas)
    r = _node(
        esboco,
        """passo(edAparar(e, "al0", 0, -10))
passo(edAparar(e, "bl1", 10, -5))
passo(edAparar(e, "bl3", -10, -5))
passo(edAparar(e, "bl2", 0, 0))""",
    )
    assert r["convergiu"] and r["lacos"] == 1 and r["soltas"] == 0 and r["bifurcacoes"] == 0
    regioes = _regioes(r["esboco"])
    assert regioes.ok
    area = float(regioes.avaliar(regioes.q_base[None, :], np.ones(1, bool)).exatas.area[0])
    assert area == pytest.approx(100 * 20 + 20 * 50)


@precisa_do_node
def test_aparar_o_circulo_vira_arco():
    esboco = _esboco(_ret("a", -50, -10, 50, 10))
    esboco["pontos"]["k"] = [50, 0]
    esboco["curvas"].append({"id": "furo", "tipo": "circulo", "pontos": ["k"], "raio": 6})
    r = _node(esboco, 'passo(edAparar(e, "furo", 56, 0))\npasso(edAparar(e, "al1", 50, 0))')
    furo = next(c for c in r["esboco"]["curvas"] if c["id"] == "furo")
    assert furo["tipo"] == "arco"
    assert r["convergiu"] and r["lacos"] == 1  # a chapa com o rebaixo de meio círculo
    regioes = _regioes(r["esboco"])
    area = float(regioes.avaliar(regioes.q_base[None, :], np.ones(1, bool)).exatas.area[0])
    assert area == pytest.approx(100 * 20 - math.pi * 36 / 2, rel=1e-6)


@precisa_do_node
def test_filete_com_letra_segue_o_raio():
    esboco = _esboco(_ret("a", 0, 0, 100, 40), variaveis=[{"nome": "r", "valor": 5}])
    r = _node(esboco, 'passo(edFilete(e, "a3", "r", { r: 5 }))')
    assert r["convergiu"] and r["lacos"] == 1
    dados = r["esboco"]
    arco = next(c for c in dados["curvas"] if c["tipo"] == "arco")
    assert any(c["tipo"] == "raio" and c["expressao"] == "r" for c in dados["cotas"])
    assert (
        sum(1 for x in dados["restricoes"] if x["tipo"] == "tangente" and arco["id"] in x["curvas"])
        == 2
    )
    sistema = eb.Sistema(eb.esboco_de_dicionario(dados))
    solucao = eb.resolver(sistema, {"r": 15.0})
    q = solucao.q[0]
    c, a = (sistema.colunas[p] for p in arco["pontos"][:2])
    assert bool(solucao.convergiu[0])
    assert math.hypot(q[a] - q[c], q[a + 1] - q[c + 1]) == pytest.approx(15.0, rel=1e-6)


@precisa_do_node
def test_filete_que_nao_cabe_diz_o_motivo():
    esboco = _esboco(_ret("a", 0, 0, 10, 8))
    with pytest.raises(AssertionError, match="não cabe"):
        _node(esboco, 'passo(edFilete(e, "a3", "30", {}))')


@precisa_do_node
def test_chanfro_guarda_o_canto_para_as_cotas():
    r = _node(_esboco(_ret("a", 0, 0, 100, 40)), 'passo(edChanfro(e, "a1", "8", {}))')
    assert r["convergiu"] and r["lacos"] == 1
    assert "a1" in r["esboco"]["pontos"]  # o canto virtual continua
    assert sum(1 for c in r["esboco"]["cotas"] if c["expressao"] == "8") == 2


@precisa_do_node
def test_deslocar_uma_fila_de_linhas_com_a_espessura_em_letra():
    esboco = {
        "pontos": {"O": [0, 0], "p1": [0, 50], "p2": [0, 0], "p3": [80, 0], "p4": [80, 50]},
        "curvas": [
            {"id": "c1", "tipo": "linha", "pontos": ["p1", "p2"]},
            {"id": "c2", "tipo": "linha", "pontos": ["p2", "p3"]},
            {"id": "c3", "tipo": "linha", "pontos": ["p3", "p4"]},
        ],
        "restricoes": [],
        "cotas": [],
        "variaveis": [{"nome": "t", "valor": 3}],
    }
    r = _node(esboco, 'passo(edDeslocar(e, ["c1", "c2", "c3"], [40, 10], "t", { t: 3 }))')
    assert r["convergiu"] and len(r["novas"]) == 3
    dados = r["esboco"]
    baixo = next(c for c in dados["curvas"] if c["id"] == r["novas"][1])
    ys = {round(dados["pontos"][p][1], 9) for p in baixo["pontos"]}
    assert ys == {3.0}  # a base copiada 3 mm para dentro da U
    assert sum(1 for c in dados["cotas"] if c["expressao"] == "t") == 3


@precisa_do_node
def test_espelho_vivo_e_padroes():
    base = {
        "pontos": {"O": [0, 0], "a": [0, -50], "b": [0, 50], "f": [20, 5]},
        "curvas": [
            {"id": "m", "tipo": "linha", "pontos": ["a", "b"], "construcao": True},
            {"id": "k", "tipo": "circulo", "pontos": ["f"], "raio": 4},
        ],
        "restricoes": [],
        "cotas": [],
        "variaveis": [{"nome": "p", "valor": 20}],
    }
    r = _node(base, 'passo(edEspelhar(e, ["k"], "m"))')
    copia = r["esboco"]["curvas"][-1]
    assert r["esboco"]["pontos"][copia["pontos"][0]] == pytest.approx([-20, 5])
    assert any(x["tipo"] == "simetrico" for x in r["esboco"]["restricoes"])
    r = _node(base, 'passo(edPadraoLinear(e, ["k"], 4, "p", "h", { p: 20 }))')
    assert r["convergiu"] and len(r["novas"]) == 3
    visiveis = [c for c in r["esboco"]["cotas"] if not c.get("oculta")]
    assert len(visiveis) == 1 and visiveis[0]["expressao"] == "p"
    r = _node(base, 'passo(edPadraoCircular(e, ["k"], "O", 6, 360))')
    assert r["convergiu"]
    assert sum(1 for c in r["esboco"]["curvas"] if c["tipo"] == "circulo") == 6


# ---------------------------------------------------------------------------
# Formas prontas, mover e girar, copiar e colar, unir
# ---------------------------------------------------------------------------


def _area(esboco: dict) -> float:
    regioes = _regioes(esboco)
    assert regioes.ok, [p.mensagem for p in regioes.problemas]
    return float(regioes.avaliar(regioes.q_base[None, :], np.ones(1, bool)).exatas.area[0])


def _livres(esboco: dict) -> int:
    return eb.graus_de_liberdade(eb.Sistema(eb.esboco_de_dicionario(esboco))).livres


@precisa_do_node
def test_rasgo_sai_com_tangentes_raios_iguais_e_area_certa():
    r = _node(_esboco(), "passo(edRasgo(e, [10, 0], [50, 0], 5))")
    assert r["convergiu"] and r["lacos"] == 1 and r["soltas"] == 0
    assert _area(r["esboco"]) == pytest.approx(40 * 10 + math.pi * 25, rel=1e-9)
    # os dois centros (4) e o raio (1): a tangente com ponta comum não deixa a ponta solta
    assert _livres(r["esboco"]) == 5


@precisa_do_node
def test_filete_tambem_prende_a_ponta_da_tangente():
    """A tangente de reta e arco com ponta comum é "raio em pé na reta": o filete não sobra solto."""
    esboco = _esboco(_ret("a", 0, 0, 100, 40))
    antes = _livres(esboco)
    r = _node(esboco, 'passo(edFilete(e, "a3", "5", {}))')
    # o filete troca um canto por um arco de raio cotado: some o grau do canto e nada sobra
    assert _livres(r["esboco"]) == antes


@precisa_do_node
def test_poligono_regular_de_seis_lados():
    r = _node(_esboco(), "passo(edPoligono(e, [20, 10], [30, 10], 6))")
    assert r["convergiu"] and r["lacos"] == 1 and len(r["novas"]) == 6
    assert _area(r["esboco"]) == pytest.approx(3 * math.sqrt(3) / 2 * 100, rel=1e-9)
    assert _livres(r["esboco"]) == 4  # centro, raio e giro
    r = _node(
        _esboco(), "r = edPoligono(e, [0, 0], [10, 0], 2)\nif (!r.erro) throw new Error('aceitou')"
    )


@precisa_do_node
def test_unir_dois_retangulos_que_se_cruzam_vira_um_t():
    esboco = _esboco(_ret("a", -50, -10, 50, 10), _ret("b", -10, -60, 10, 0))
    r = _node(esboco, "passo(edUnir(e))")
    assert r["convergiu"] and r["lacos"] == 1 and r["soltas"] == 0 and r["bifurcacoes"] == 0
    assert _area(r["esboco"]) == pytest.approx(100 * 20 + 20 * 50)
    assert not any(p.tipo == "cruzam" for p in _regioes(r["esboco"]).problemas)


@precisa_do_node
def test_unir_com_os_nomes_da_prancheta_nao_troca_as_restricoes():
    """Na prancheta as curvas se chamam c1, c2...: as novas não herdam as restrições das velhas."""
    esboco = _esboco(
        _ret("a", -50, -10, 50, 10), _ret("b", -10, -60, 10, 0), _ret("s", 80, 0, 90, 30)
    )
    nomes = {c["id"]: f"c{i}" for i, c in enumerate(esboco["curvas"], start=1)}
    for c in esboco["curvas"]:
        c["id"] = nomes[c["id"]]
    for r in esboco["restricoes"]:
        r["curvas"] = [nomes[c] for c in r["curvas"]]
    r = _node(esboco, "passo(edUnir(e))")
    assert r["convergiu"] and r["lacos"] == 2
    # a chapa solta, que não encosta em nada, fica com as curvas dela
    assert {"c9", "c10", "c11", "c12"} <= {c["id"] for c in r["esboco"]["curvas"]}
    assert _area(r["esboco"]) == pytest.approx(100 * 20 + 20 * 50 + 10 * 30)


@precisa_do_node
def test_unir_encostados_tira_a_borda_comum_e_guarda_o_furo():
    esboco = _esboco(_ret("a", 0, 0, 50, 20), _ret("b", 50, 5, 80, 15))
    esboco["pontos"]["k"] = [20, 10]
    esboco["curvas"].append({"id": "furo", "tipo": "circulo", "pontos": ["k"], "raio": 4})
    r = _node(esboco, "passo(edUnir(e))")
    assert r["convergiu"] and r["lacos"] == 2 and r["soltas"] == 0
    assert _area(r["esboco"]) == pytest.approx(50 * 20 + 30 * 10 - math.pi * 16)
    # o canto que estava na origem não fica preso nela
    assert "O" not in {p for c in r["esboco"]["curvas"] for p in c["pontos"]}


@precisa_do_node
def test_unir_com_circulo_e_recusar_o_que_nao_encosta():
    esboco = _esboco(_ret("a", 0, 0, 50, 20))
    esboco["pontos"]["k"] = [50, 10]
    esboco["curvas"].append({"id": "bola", "tipo": "circulo", "pontos": ["k"], "raio": 15})
    r = _node(esboco, "passo(edUnir(e))")
    sobra = 10 * math.sqrt(125) + 225 * math.asin(2 / 3)  # o pedaço do círculo dentro da chapa
    assert _area(r["esboco"]) == pytest.approx(1000 + math.pi * 225 - sobra, rel=1e-9)
    separados = _esboco(_ret("a", 0, 0, 10, 10), _ret("b", 20, 0, 30, 10))
    r = _node(separados, "r = edUnir(e)\nif (!r.erro) throw new Error('uniu')")


@precisa_do_node
def test_colar_e_girar_a_copia_guardam_a_forma():
    esboco = _esboco(_ret("a", 0, 0, 50, 20))
    esboco["cotas"].append(
        {
            "id": "d1",
            "tipo": "distancia",
            "pontos": ["a1", "a2"],
            "modo": "h",
            "sinal": 1,
            "expressao": "50",
            "lugar": [25, -5],
        }
    )
    todas = '["al0", "al1", "al2", "al3"]'
    r = _node(esboco, f"passo(edColar(e, edRecorte(e, {todas}), ([x, y]) => [x + 100, y]))")
    assert r["convergiu"] and r["lacos"] == 2 and len(r["esboco"]["cotas"]) == 2
    # girar 90° troca deitada e em pé (e a cota horizontal vira vertical); 30° vira paralelas,
    # perpendiculares e cota alinhada; 180° vira o sinal da cota: a peça copiada não deforma
    for graus in (90, 30, 180):
        r = _node(
            esboco,
            f"passo(edTransformar(e, {todas}, 100, 0, {graus}, edCentroDe(e, {todas}), true))",
        )
        assert r["convergiu"] and r["lacos"] == 2
        assert _area(r["esboco"]) == pytest.approx(2 * 50 * 20, rel=1e-9)
    # mover sem cópia leva a cota junto
    r = _node(esboco, f"passo(edTransformar(e, {todas}, 10, 5, 0, [0, 0], false))")
    assert r["esboco"]["pontos"]["a1"] == pytest.approx([10, 5])
    assert r["esboco"]["cotas"][0]["lugar"] == pytest.approx([35, 0])


# ---------------------------------------------------------------------------
# A parte de testar: regras de projeto e faixas
# ---------------------------------------------------------------------------


def test_regra_le_e_mede():
    regra = eb.ler_regra("parede >= 1,5*d")
    assert regra.comparacao == ">=" and eb.letras_da_regra(regra) == {"parede", "d"}
    assert eb.folga_da_regra(regra, {"parede": 9.0, "d": 4.0}) == pytest.approx(3.0)
    assert eb.folga_da_regra(eb.ler_regra("d <= 0,6*h"), {"d": 13.0, "h": 20.0}) == pytest.approx(
        -1.0
    )
    with pytest.raises(eb.ErroDeEsboco, match=">= ou <="):
        eb.ler_regra("d = 3")


def test_regra_com_letra_que_nao_existe_e_recusada():
    dados = chapa_com_furos()
    dados["regras"] = ["parede >= 2*x"]
    with pytest.raises(eb.ErroDeEsboco, match="não é letra"):
        eb.esboco_de_dicionario(dados)


def test_regra_de_parede_corta_a_faixa_da_letra():
    """Parede ≥ 1,5·d: com a chapa de 20 e o furo no meio, (20 − d)/2 ≥ 1,5·d dá d ≤ 5."""
    dados = chapa_com_furos(d=4.0)
    dados["regras"] = ["parede >= 1,5*d"]
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    faixa = modelo.faixa("d")
    assert faixa.maximo == pytest.approx(5.0, abs=1e-3)
    assert faixa.motivo_maximo == er.REGRA + "parede >= 1,5*d"
    assert "regra de projeto" in faixa.texto()
    assert modelo.numero(es.FOLGA, {"d": 6.0})[0] == -1.0


def test_faixa_da_letra_vai_para_a_busca_do_montador():
    dados = chapa_com_furos()
    dados["variaveis"][0].update(de=2.0, ate=18.0, passo=0.5)
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    assert modelo.faixa_de_teste("d") == (2.0, 18.0, 0.5)
    sem = es.Modelo(eb.esboco_de_dicionario(chapa_com_furos()))
    de, ate, _ = sem.faixa_de_teste("d")
    assert de == pytest.approx(2.5) and ate == pytest.approx(19.98, abs=0.01)  # até o furo encostar


def test_dicionario_guarda_faixa_regras_e_cotas_escondidas():
    dados = chapa_com_furos()
    dados["variaveis"][0].update(de=2.0, ate=18.0, passo=0.5)
    dados["regras"] = ["parede >= 1,5*d"]
    dados["cotas"][0]["oculta"] = True
    volta = eb.esboco_de_dicionario(dados).como_dicionario()
    assert volta["variaveis"][0]["de"] == 2.0 and volta["regras"] == ["parede >= 1,5*d"]
    assert volta["cotas"][0]["oculta"] is True


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


def test_montador_para_na_regra_de_projeto(catalogo_vazio):
    from tests.test_montador_esboco import _montar

    dados = chapa_com_furos(d=4.0)
    dados["regras"] = ["parede >= 1,5*d"]
    _salvar("Chapa com regra", dados)
    m = _montar("Chapa com regra", "flexao", "von_mises")
    r = mt.isolar(m, "d", {"M_x": 1.0e6, "S_y": 250.0, "n": 1.0})
    assert r.valor == pytest.approx(5.0, abs=1e-3)
    assert any("regra de projeto" in a for a in r.alertas)
    assert m.grandeza("d").faixa is not None


def test_painel_de_teste_na_pagina(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/desenhar_secao.py").run()
    at.selectbox(key="secao_abrir").set_value("Chapa furada").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert [t.label for t in at.tabs][:4] == [
        "Até onde vai",
        "Varredura",
        "Regras de projeto",
        "Configurações",
    ]
    assert at.number_input(key="secao_faixa_d_ate").value == pytest.approx(19.98, abs=0.01)
    # Uma regra de projeto: a faixa de d passa a parar nela.
    # (20 − d)/2 ≥ d/4 dá d ≤ 13,33; o d de agora (10) cumpre.
    at.text_area(key="secao_regras").set_value("parede >= d/4").run()
    at.button(key="secao_aplicar_regras").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    from components import desenhar_secao_ui as ui

    assert at.session_state[ui.ESBOCO]["regras"] == ["parede >= d/4"]
    textos = " ".join(m.value for m in at.markdown)
    assert "até 13,33 mm" in textos and "regra de projeto" in textos
    # A faixa de teste mudada vai para o esboço (e para a seção salva).
    at.number_input(key="secao_faixa_d_ate").set_value(12.5).run()
    variavel = at.session_state[ui.ESBOCO]["variaveis"][0]
    assert variavel["ate"] == pytest.approx(12.5)
    # Salvar leva a tabela de configurações junto.
    at.session_state[ui.CONFIGURACOES] = [{"Nome": "A", "d": 3.0}]
    assert ui.CONFIGURACOES in at.session_state
