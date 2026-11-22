"""O esboço paramétrico: contas com letras, solver, regiões, contas exatas e o teste do desenho.

Os mesmos esboços rodam no solver do navegador (Node) e no de Python: os números têm de bater, senão
a prancheta mostra um desenho e o Montador calcula outro.
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

from core import esboco as eb
from core import esboco_regioes as er
from core import esboco_secao as es
from core import secao_desenhada as sd
from core import section_catalog as catalogo

RAIZ = Path(__file__).resolve().parent.parent
PASTA_JS = RAIZ / "components" / "esboco"
NODE = shutil.which("node")


# ---------------------------------------------------------------------------
# Esboços de exemplo
# ---------------------------------------------------------------------------


def _linhas(*pares: tuple[str, str], inicio: int = 1) -> list[dict]:
    return [
        {"id": f"l{i}", "tipo": "linha", "pontos": list(par)}
        for i, par in enumerate(pares, start=inicio)
    ]


def chapa_com_furos(d: float = 10.0, h: float = 20.0, *, letra_h: bool = False) -> dict:
    """Chapa 100 × h com dois furos iguais de diâmetro d no meio da altura, a 50 mm um do outro."""
    altura = "h" if letra_h else str(h)
    variaveis = [{"nome": "d", "valor": d}]
    if letra_h:
        variaveis.append({"nome": "h", "valor": h})
    return {
        "pontos": {
            "p1": [-50, -h / 2],
            "p2": [50, -h / 2],
            "p3": [50, h / 2],
            "p4": [-50, h / 2],
            "f1": [-25, 0.5],
            "f2": [24, 0],
        },
        "curvas": [
            *_linhas(("p1", "p2"), ("p2", "p3"), ("p3", "p4"), ("p4", "p1")),
            {"id": "c1", "tipo": "circulo", "pontos": ["f1"], "raio": 4},
            {"id": "c2", "tipo": "circulo", "pontos": ["f2"], "raio": 6},
        ],
        "restricoes": [
            {"id": "r1", "tipo": "horizontal", "curvas": ["l1", "l3"]},
            {"id": "r2", "tipo": "vertical", "curvas": ["l2", "l4"]},
            {"id": "r3", "tipo": "igual", "curvas": ["c1", "c2"]},
        ],
        "cotas": [
            {
                "id": "d1",
                "tipo": "distancia",
                "pontos": ["p1", "p2"],
                "modo": "h",
                "expressao": "100",
            },
            {
                "id": "d2",
                "tipo": "distancia",
                "pontos": ["p2", "p3"],
                "modo": "v",
                "expressao": altura,
            },
            {
                "id": "d3",
                "tipo": "distancia",
                "pontos": ["O", "p1"],
                "modo": "h",
                "expressao": "50",
            },
            {
                "id": "d4",
                "tipo": "distancia",
                "pontos": ["O", "p1"],
                "modo": "v",
                "expressao": f"{altura}/2",
            },
            {"id": "d5", "tipo": "diametro", "curvas": ["c1"], "expressao": "d"},
            {
                "id": "d6",
                "tipo": "distancia",
                "pontos": ["O", "f1"],
                "modo": "h",
                "expressao": "25",
            },
            {
                "id": "d7",
                "tipo": "distancia",
                "pontos": ["f1", "f2"],
                "modo": "h",
                "expressao": "50",
            },
            {"id": "d8", "tipo": "distancia", "pontos": ["O", "f1"], "modo": "v", "expressao": "0"},
            {"id": "d9", "tipo": "distancia", "pontos": ["O", "f2"], "modo": "v", "expressao": "0"},
        ],
        "variaveis": variaveis,
    }


def rasgo(comprimento: float = 60.0, raio: float = 10.0) -> dict:
    """Oblongo: duas retas e dois meios círculos tangentes, comprimento L entre centros e raio r."""
    meio = comprimento / 2
    return {
        "pontos": {
            "a": [-meio, -raio * 1.1],
            "b": [meio, -raio],
            "c": [meio, raio],
            "e": [-meio, raio * 0.9],
            "cd": [meio + 1, 0],
            "ce": [-meio, 0.5],
        },
        "curvas": [
            *_linhas(("a", "b"), ("c", "e")),
            {"id": "k1", "tipo": "arco", "pontos": ["cd", "b", "c"]},
            {"id": "k2", "tipo": "arco", "pontos": ["ce", "e", "a"]},
        ],
        "restricoes": [
            {"id": "r1", "tipo": "horizontal", "curvas": ["l1", "l2"]},
            {"id": "r2", "tipo": "tangente", "curvas": ["l1", "k1"]},
            {"id": "r3", "tipo": "tangente", "curvas": ["l2", "k1"]},
            {"id": "r4", "tipo": "tangente", "curvas": ["l2", "k2"]},
            {"id": "r5", "tipo": "tangente", "curvas": ["l1", "k2"]},
            {"id": "r6", "tipo": "igual", "curvas": ["k1", "k2"]},
            {"id": "r7", "tipo": "coincidente", "pontos": ["O", "ce"]},
        ],
        "cotas": [
            {
                "id": "d1",
                "tipo": "distancia",
                "pontos": ["ce", "cd"],
                "modo": "h",
                "expressao": "L",
            },
            {"id": "d2", "tipo": "raio", "curvas": ["k1"], "expressao": "r"},
        ],
        "variaveis": [{"nome": "L", "valor": comprimento}, {"nome": "r", "valor": raio}],
    }


def trapezio() -> dict:
    """Base deitada, lado inclinado por um ângulo em letra, topo deitado e lado em pé."""
    return {
        "pontos": {"p1": [0, 0], "p2": [100, 0], "p3": [70, 50], "p4": [0, 48]},
        "curvas": _linhas(("p1", "p2"), ("p2", "p3"), ("p3", "p4"), ("p4", "p1")),
        "restricoes": [
            {"id": "r1", "tipo": "horizontal", "curvas": ["l1", "l3"]},
            {"id": "r2", "tipo": "vertical", "curvas": ["l4"]},
            {"id": "r3", "tipo": "coincidente", "pontos": ["O", "p1"]},
        ],
        "cotas": [
            {
                "id": "d1",
                "tipo": "distancia",
                "curvas": ["l1"],
                "pontos": ["p1", "p2"],
                "expressao": "100",
            },
            {
                "id": "d2",
                "tipo": "distancia",
                "pontos": ["p1", "p4"],
                "modo": "v",
                "expressao": "50",
            },
            {"id": "d3", "tipo": "angulo", "curvas": ["l1", "l2"], "expressao": "a"},
        ],
        "variaveis": [{"nome": "a", "valor": 120.0, "tipo": "angulo"}],
    }


def retangulo_solto() -> dict:
    """Só horizontal e vertical: posição, largura e altura ficam livres (4 graus)."""
    return {
        "pontos": {"p1": [10, 10], "p2": [60, 10], "p3": [60, 40], "p4": [10, 40]},
        "curvas": _linhas(("p1", "p2"), ("p2", "p3"), ("p3", "p4"), ("p4", "p1")),
        "restricoes": [
            {"id": "r1", "tipo": "horizontal", "curvas": ["l1", "l3"]},
            {"id": "r2", "tipo": "vertical", "curvas": ["l2", "l4"]},
        ],
    }


def _ler(dados: dict) -> eb.Esboco:
    return eb.esboco_de_dicionario(dados)


# ---------------------------------------------------------------------------
# Contas com letras
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "valores", "esperado"),
    [
        ("2*d + 5", {"d": 3}, 11.0),
        ("2,5*b", {"b": 4}, 10.0),
        ("L/2 - 10", {"L": 100}, 40.0),
        ("-d^2", {"d": 3}, -9.0),
        ("(a+b)*(a-b)", {"a": 5, "b": 3}, 16.0),
        ("pi*d", {"d": 2}, 2 * math.pi),
        ("1,5e2", {}, 150.0),
    ],
)
def test_conta_com_letras(texto, valores, esperado):
    assert eb.avaliar_conta(eb.ler_conta(texto), valores) == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        ("2*", "termina no meio"),
        ("d)", "Sobrou"),
        ("(d", "parêntese"),
        ("d # 2", "Não entendi"),
        ("", "vazia"),
    ],
)
def test_conta_ruim_diz_onde(texto, trecho):
    with pytest.raises(eb.ErroDeEsboco, match=trecho):
        eb.ler_conta(texto)


def test_letras_da_conta_e_letra_sem_valor():
    no = eb.ler_conta("2*d + L/b")
    assert eb.letras_da_conta(no) == {"d", "L", "b"}
    with pytest.raises(eb.ErroDeEsboco, match="crie a variável"):
        eb.avaliar_conta(no, {"d": 1, "L": 2})


def test_cota_com_letra_que_nao_existe_e_recusada():
    dados = chapa_com_furos()
    dados["variaveis"] = []
    with pytest.raises(eb.ErroDeEsboco, match="tabela de letras"):
        _ler(dados)


# ---------------------------------------------------------------------------
# Solver e graus de liberdade
# ---------------------------------------------------------------------------


def test_chapa_fica_totalmente_definida_e_o_furo_segue_a_letra():
    modelo = es.Modelo(_ler(chapa_com_furos()))
    assert modelo.graus.definido
    assert modelo.letras == ("d",)
    for d in (4.0, 12.0, 18.0):
        e = modelo.medir({"d": d}).avaliacao.exatas
        assert float(e.area[0]) == pytest.approx(100 * 20 - 2 * math.pi * d**2 / 4, rel=1e-9)
        assert float(e.ix[0]) == pytest.approx(100 * 20**3 / 12 - 2 * math.pi * d**4 / 64, rel=1e-9)
        assert float(e.yc[0]) == pytest.approx(0.0, abs=1e-9)


def test_cota_que_muda_muito_nao_vira_o_desenho_do_avesso():
    modelo = es.Modelo(_ler(chapa_com_furos(letra_h=True)))
    medicao = modelo.medir({"h": 400.0, "d": 10.0})
    assert bool(medicao.avaliacao.valido[0])
    assert float(medicao.avaliacao.exatas.area[0]) == pytest.approx(100 * 400 - 2 * math.pi * 25)


def test_graus_livres_e_restricao_repetida():
    sistema = eb.Sistema(_ler(retangulo_solto()))
    graus = eb.graus_de_liberdade(sistema)
    assert graus.livres == 4
    assert {"p1", "p2", "p3", "p4"} <= graus.pontos_livres
    dados = retangulo_solto()
    dados["restricoes"].append({"id": "r3", "tipo": "paralela", "curvas": ["l1", "l3"]})
    graus = eb.graus_de_liberdade(eb.Sistema(_ler(dados)))
    assert graus.livres == 4
    assert graus.redundantes  # paralelas já eram, por serem as duas horizontais


def test_cotas_que_brigam_dizem_quem():
    dados = chapa_com_furos()
    dados["cotas"].append(
        {"id": "d10", "tipo": "distancia", "pontos": ["p1", "p2"], "modo": "d", "expressao": "120"}
    )
    with pytest.raises(eb.ErroDeEsboco, match="não fecha"):
        eb.esboco_resolvido(_ler(dados))


def test_angulo_em_letra_gira_o_lado():
    modelo = es.Modelo(_ler(trapezio()))
    esboco = eb.com_q(modelo.esboco, modelo.sistema, modelo.medir({}).q[0])
    (x2, y2), (x3, y3) = esboco.pontos["p2"], esboco.pontos["p3"]
    angulo = math.degrees(math.atan2(y3 - y2, x3 - x2))
    assert angulo == pytest.approx(120.0, abs=1e-6)
    assert y3 == pytest.approx(50.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Regiões e contas exatas
# ---------------------------------------------------------------------------


def test_furo_dentro_da_chapa_e_contorno_fora():
    regioes = er.Regioes(eb.Sistema(eb.esboco_resolvido(_ler(chapa_com_furos()))))
    assert regioes.ok
    assert sorted(regioes.profundidade) == [0, 1, 1]


def test_contorno_aberto_diz_o_ponto():
    dados = retangulo_solto()
    dados["curvas"] = dados["curvas"][:3]
    dados["restricoes"] = [{"id": "r1", "tipo": "horizontal", "curvas": ["l1", "l3"]}]
    regioes = er.Regioes(eb.Sistema(_ler(dados)))
    assert not regioes.ok
    assert any(p.tipo == "ponta" and p.onde is not None for p in regioes.problemas)


def test_contornos_que_se_cruzam_sao_recusados():
    dados = retangulo_solto()
    dados["pontos"].update({"q1": [40, 20], "q2": [90, 20], "q3": [90, 30], "q4": [40, 30]})
    dados["curvas"] += _linhas(("q1", "q2"), ("q2", "q3"), ("q3", "q4"), ("q4", "q1"), inicio=5)
    regioes = er.Regioes(eb.Sistema(_ler(dados)))
    assert any(p.tipo == "cruzam" for p in regioes.problemas)


def test_rasgo_com_arcos_tangentes_tem_as_contas_exatas():
    """Exato até a tolerância do solver (10⁻⁹ do tamanho do desenho), com os arcos na integral."""
    modelo = es.Modelo(_ler(rasgo()))
    assert modelo.graus.definido
    for comprimento, raio in ((60.0, 10.0), (90.0, 6.0)):
        e = modelo.medir({"L": comprimento, "r": raio}).avaliacao.exatas
        area = comprimento * 2 * raio + math.pi * raio**2
        ix = comprimento * (2 * raio) ** 3 / 12 + math.pi * raio**4 / 4
        meio_circulo = math.pi * raio**2 / 2
        iy = (2 * raio) * comprimento**3 / 12 + 2 * (
            comprimento**2 / 4 * meio_circulo
            + comprimento * 2 * raio**3 / 3
            + math.pi * raio**4 / 8
        )
        assert float(e.area[0]) == pytest.approx(area, rel=1e-8)
        assert float(e.ix[0]) == pytest.approx(ix, rel=1e-8)
        assert float(e.iy[0]) == pytest.approx(iy, rel=1e-8)
        assert float(e.y_max[0]) == pytest.approx(raio, rel=1e-8)
        assert float(e.x_max[0]) == pytest.approx(
            comprimento + raio, rel=1e-8
        )  # centro esquerdo na origem


def test_partes_da_malha_batem_com_as_contas_exatas():
    modelo = es.Modelo(_ler(rasgo()))
    q = modelo.sistema.q0[None, :]
    exatas = modelo.medir({}).avaliacao.exatas
    prop = sd.analisar(modelo.regioes.partes(q)).prop
    assert prop.area == pytest.approx(float(exatas.area[0]), rel=2e-3)
    assert prop.ix == pytest.approx(float(exatas.ix[0]), rel=5e-3)


# ---------------------------------------------------------------------------
# Até onde a letra pode ir
# ---------------------------------------------------------------------------


def test_furo_que_encosta_na_borda_e_o_limite_da_letra():
    modelo = es.Modelo(_ler(chapa_com_furos()))
    faixa = modelo.faixa("d")
    assert faixa.maximo == pytest.approx(20.0, abs=1e-3)
    assert faixa.motivo_maximo == er.ENCOSTOU
    assert faixa.minimo is None
    assert "20 mm" in faixa.texto()
    assert modelo.medir({"d": 10.0}).avaliacao.folga[0] == pytest.approx(5.0)


def test_altura_que_aperta_o_furo_tem_limite_por_baixo():
    modelo = es.Modelo(_ler(chapa_com_furos(letra_h=True)))
    faixa = modelo.faixa("h")
    assert faixa.minimo == pytest.approx(10.0, abs=1e-3)
    assert faixa.maximo is None


def test_numeros_da_secao_vem_em_vetor_e_ficam_guardados():
    modelo = es.Modelo(_ler(chapa_com_furos()))
    d = np.array([4.0, 10.0, 25.0])
    numeros = modelo.numeros({"d": d}, (es.AREA, es.FOLGA))
    assert numeros[es.AREA][1] == pytest.approx(2000 - 2 * math.pi * 25)
    assert math.isnan(numeros[es.AREA][2]) and numeros[es.FOLGA][2] == -1.0
    # Linha neutra: τ = V·Q/(I·b), com a largura líquida 100 − 2d e Q menos os dois meios furos.
    neutra = next(i for i, p in enumerate(modelo.pontos, start=1) if p.tipo == "neutra")
    tau = modelo.numero(100 * neutra + es.TVY, {"d": 10.0})[0]
    inercia = 100 * 20**3 / 12 - 2 * math.pi * 10**4 / 64
    q = 100 * 10 * 5 - 2 * (10**3 / 12)
    assert tau == pytest.approx(q / (inercia * 80), rel=5e-3)


def test_esboco_das_partes_antigas():
    partes = [
        sd.Parte(sd.RET, 0, 0, 80, 40),
        sd.Parte(sd.CIRC, 10, 0, 12, 12, furo=True),
    ]
    esboco = eb.esboco_das_partes(partes)
    regioes = er.Regioes(eb.Sistema(esboco))
    assert regioes.ok
    area = float(regioes.avaliar(regioes.q_base[None, :], np.ones(1, bool)).exatas.area[0])
    assert area == pytest.approx(80 * 40 - math.pi * 36)


def test_secao_salva_guarda_o_esboco(tmp_path):
    dados = chapa_com_furos()
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        modelo = es.Modelo(_ler(dados))
        partes = modelo.regioes.partes(modelo.sistema.q0[None, :])
        catalogo.salvar_perfil(
            sd.perfil_da_secao("Chapa furada", sd.analisar(partes)),
            desenho=tuple(p.como_dicionario() for p in partes),
            esboco=dados,
        )
        item = catalogo.obter("Chapa furada")
        assert item.esboco == dados
        assert item.desenho


# ---------------------------------------------------------------------------
# O solver do navegador é o mesmo
# ---------------------------------------------------------------------------


def _node(esboco: dict, valores: dict) -> dict:
    programa = "".join(
        (PASTA_JS / n).read_text(encoding="utf-8")
        for n in ("conta.js", "solver.js", "contornos.js")
    )
    programa += f"""
const esb = {json.dumps(esboco)}
const s = esSistema(esb)
const r = esResolver(s, {json.dumps(valores)})
const g = esGraus(s, s.q0)
const c = esContornos(esb)
console.log(JSON.stringify({{ q: Array.from(r.q), convergiu: r.convergiu, livres: g.livres,
  redundantes: g.redundantes, lacos: c.lacos.length + c.circulos.length, soltas: c.soltas.length }}))
"""
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    return json.loads(saida.stdout)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
@pytest.mark.parametrize(
    ("fabrica", "valores"),
    [
        (chapa_com_furos, {"d": 16.0}),
        (rasgo, {"L": 85.0, "r": 7.5}),
        (trapezio, {"a": 105.0}),
        (retangulo_solto, {}),
    ],
)
def test_solver_do_navegador_da_os_mesmos_numeros(fabrica, valores):
    esboco = eb.esboco_resolvido(_ler(fabrica()))
    dados = esboco.como_dicionario()
    sistema = eb.Sistema(esboco)
    python = eb.resolver(sistema, valores)
    js = _node(dados, valores)
    assert js["convergiu"] and bool(python.convergiu[0])
    assert np.max(np.abs(np.array(js["q"]) - python.q[0])) < 1e-8 * sistema.tamanho
    graus = eb.graus_de_liberdade(sistema)
    assert js["livres"] == graus.livres
    assert js["redundantes"] == list(graus.redundantes)
    lacos, problemas = er.contornos(esboco)
    assert js["lacos"] == len(lacos) and js["soltas"] == sum(p.tipo == "ponta" for p in problemas)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
@pytest.mark.parametrize("texto", ["2*d + 5", "2,5*b", "L/2 - 10", "-d^2", "(a+b)*(a-b)", "pi*d"])
def test_conta_do_navegador_da_o_mesmo_numero(texto):
    valores = {"d": 3.0, "b": 4.0, "L": 100.0, "a": 5.0}
    programa = (PASTA_JS / "conta.js").read_text(encoding="utf-8")
    programa += f"\nconsole.log(JSON.stringify(avaliarConta(lerConta({json.dumps(texto)}), {json.dumps(valores)})))\n"
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    assert json.loads(saida.stdout) == pytest.approx(eb.avaliar_conta(eb.ler_conta(texto), valores))


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_arrastar_mexe_so_o_que_esta_livre():
    """Arrastar um canto do retângulo solto: as restrições continuam e o desenho acompanha."""
    esboco = eb.esboco_resolvido(_ler(retangulo_solto())).como_dicionario()
    programa = "".join(
        (PASTA_JS / n).read_text(encoding="utf-8") for n in ("conta.js", "solver.js")
    )
    programa += f"""
const esb = {json.dumps(esboco)}
const s = esSistema(esb)
const i = s.colunas.get("p3")
const q = esArrastar(s, s.q0, [{{ coluna: i, valor: 80 }}, {{ coluna: i + 1, valor: 55 }}])
const f = esResiduos(s, q, esAlvos(s, {{}}))
console.log(JSON.stringify({{ p3: [q[i], q[i + 1]], erro: Math.max(...f.map(Math.abs)), p1: [q[s.colunas.get("p1")], q[s.colunas.get("p1") + 1]] }}))
"""
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    r = json.loads(saida.stdout)
    assert r["p3"] == pytest.approx([80.0, 55.0])
    assert r["erro"] < 1e-6
    assert r["p1"] == pytest.approx([10.0, 10.0], abs=1e-6)  # o canto oposto não precisou andar
