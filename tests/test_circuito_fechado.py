"""Circuito fechado: hidráulica com ramais, peças, regime permanente, conta no tempo, vaso, página."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from scipy import optimize
from streamlit.testing.v1 import AppTest

from components.circuito_help import AJUDA
from core import circuito as ci
from core import circuito_cenas as cc
from core import circuito_termico as cte
from core import figuras_no_tempo as fnt
from core import montador_fluidos as fl
from core.montador_funcoes import fator_de_atrito
from core.technical_records import avaliar_contrato_registro
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/circuito_fechado.py"
NODE = shutil.which("node")


def _volta(*pecas: ci.Elemento, vaso: ci.Vaso | None = None) -> ci.Circuito:
    """Um anel A → B → … → A com as peças dadas, na ordem, e o vaso em A."""
    nomes = [f"n{i}" for i in range(len(pecas))]
    nos = tuple(
        ci.No(n, n.upper(), float(i), 0.0, 0.0, vaso or ci.Vaso() if i == 0 else None)
        for i, n in enumerate(nomes)
    )
    elementos = tuple(
        replace(p, de=nomes[i], para=nomes[(i + 1) % len(nomes)]) for i, p in enumerate(pecas)
    )
    return ci.Circuito(nos, elementos)


BOMBA = ci.Elemento("b", "Bomba", ci.BOMBA, "", "", h0_m=20.0, qmax_m3h=30.0)
TUBO = ci.Elemento(
    "t",
    "Tubo",
    ci.TUBO,
    "",
    "",
    comprimento_m=80.0,
    diametro_mm=52.5,
    rugosidade_mm=0.045,
    k_local=3.0,
)


def test_anel_simples_e_o_encontro_da_bomba_com_as_perdas():
    c = _volta(BOMBA, TUBO)
    h = ci.resolver_hidraulica(c, 20.0)
    q = h.vazoes["t"]
    p = ci.propriedades("Água", 20.0)

    def sobra(qq: float) -> float:
        v = qq / TUBO.area
        f = float(fator_de_atrito(p.massa_especifica * v * 0.0525 / p.viscosidade, 0.045 / 52.5))
        return (
            20.0 - 20.0 * (qq * 3600 / 30.0) ** 2 - (f * 80.0 / 0.0525 + 3.0) * v * v / (2 * 9.81)
        )

    assert q == pytest.approx(optimize.brentq(sobra, 1e-6, 30.0 / 3600), rel=1e-6)
    assert h.vazoes["b"] == pytest.approx(q)
    assert h.pressao_bar("n0") == pytest.approx(1.5)  # o vaso fixa a pressão onde está


def test_ramais_em_paralelo_perdem_o_mesmo_e_somam_a_vazao():
    d = ci.exemplo_desenhado()
    c = ci.circuito_do_desenho(d, fl.RUGOSIDADES)
    h = ci.resolver_hidraulica(c, 30.0)
    q = {e.nome: h.vazoes[e.id] for e in c.elementos}
    assert q["2"] + q["4"] == pytest.approx(q["1"], rel=1e-9)
    assert q["Dry cooler"] == pytest.approx(q["Bomba 1"], rel=1e-9)
    # os dois ramais vão de C até H: a mesma diferença de carga
    p = ci.propriedades(c.fluido, 30.0)
    perda = {e.nome: ci.perda(e, h.vazoes[e.id], p)[0] for e in c.elementos}
    ramal_1 = perda["2"] + perda["Máquina 1"] + perda["3"]
    ramal_2 = perda["4"] + perda["Máquina 2"] + perda["5"]
    assert ramal_1 == pytest.approx(ramal_2, rel=1e-6)
    assert ramal_1 == pytest.approx(h.cargas["n3"] - h.cargas["n8"], rel=1e-6)


def test_problemas_do_desenho():
    sem_vaso = ci.Circuito(
        (ci.No("a", "A"), ci.No("b", "B")),
        (replace(BOMBA, de="a", para="b"), replace(TUBO, de="b", para="a")),
    )
    assert any("vaso de expansão" in e for e in ci.problemas(sem_vaso))
    sem_bomba = _volta(TUBO, replace(TUBO, id="t2", nome="2"))
    assert any("bomba" in e for e in ci.problemas(sem_bomba))
    dois = replace(sem_vaso, nos=(ci.No("a", "A", vaso=ci.Vaso()), ci.No("b", "B", vaso=ci.Vaso())))
    assert any("vaso de expansão só" in e for e in ci.problemas(dois))
    assert ci.problemas(ci.Circuito((), ())) == [
        "Desenhe o circuito: trechos de tubo e as peças em cima deles."
    ]


def test_dry_cooler_reproduz_o_ponto_do_catalogo():
    e = ci.Elemento("d", "DC", ci.DRY_COOLER, "", "", q_catalogo_kW=80.0, t_entrada_catalogo=40.0, t_ar_catalogo=30.0,
                    vazao_liquido_catalogo_m3h=12.0, vazao_ar_catalogo_m3h=36000.0)  # fmt: skip
    dc = cte.dry_cooler(e, "Água")
    p = ci.propriedades("Água", 35.0)
    c_liq = p.massa_especifica * 12.0 / 3600 * p.calor_especifico
    assert dc.calor(c_liq, 40.0, 30.0) == pytest.approx(80_000.0, rel=1e-9)
    assert dc.calor(c_liq, 40.0, 40.0) == 0.0
    s = dc.rotacao_para(c_liq, 40.0, 30.0, 36.0)
    assert 0 < s < 1 and dc.calor(c_liq, 40.0, 30.0, s) == pytest.approx(c_liq * 4.0, rel=1e-8)
    assert cte.eficacia_cruzada(1.0, 0.0) == pytest.approx(1 - math.exp(-1))
    assert cte.eficacia_cruzada(1.0, 1.0) == pytest.approx(1 - math.exp(math.exp(-1) - 1))
    with pytest.raises(cte.ErroTermico, match="impossível"):
        cte.dry_cooler(replace(e, q_catalogo_kW=900.0), "Água")


def test_regime_permanente_fecha_a_energia_e_o_chiller_segura_o_ajuste():
    fonte = ci.Elemento(
        "f", "Fonte", ci.FONTE, "", "", potencia_kW=30.0, dp_kPa=10.0, q_nominal_m3h=10.0
    )
    chiller = ci.Elemento(
        "c",
        "Chiller",
        ci.CHILLER,
        "",
        "",
        capacidade_kW=40.0,
        t_ajuste=12.0,
        dp_kPa=20.0,
        q_nominal_m3h=10.0,
    )
    c = _volta(BOMBA, TUBO, fonte, replace(TUBO, id="t2", nome="2"), chiller)
    h = ci.resolver_hidraulica(c, 15.0)
    r = cte.regime_permanente(c, h, 30.0, temperatura_media=15.0)
    assert r.saidas["c"] == pytest.approx(12.0)
    assert sum(r.calores.values()) == pytest.approx(0.0, abs=1e-6)
    assert r.calores["c"] == pytest.approx(-30_000.0, rel=1e-9)
    # capacidade menor que a carga: o chiller vai ao limite e o circuito não fecha o regime
    pequeno = _volta(BOMBA, TUBO, fonte, replace(chiller, capacidade_kW=20.0))
    with pytest.raises(cte.ErroTermico, match="regime permanente"):
        cte.regime_permanente(pequeno, ci.resolver_hidraulica(pequeno, 15.0), 30.0)


def test_sem_nada_que_tire_calor_nao_ha_regime():
    fonte = ci.Elemento("f", "Fonte", ci.FONTE, "", "", potencia_kW=30.0)
    c = _volta(BOMBA, TUBO, fonte)
    with pytest.raises(cte.ErroTermico, match="não tem por onde sair"):
        cte.regime_permanente(c, ci.resolver_hidraulica(c, 20.0), 30.0)


def test_no_tempo_termina_no_regime_permanente():
    c = ci.circuito_do_desenho(ci.exemplo_desenhado(), fl.RUGOSIDADES)
    r = cc.calcular(c, cte.Condicoes(t_ar=30.0, t_inicial=25.0))
    assert r.status == "OK"
    assert r.tempo is not None and r.tempo.estabiliza is not None
    for e in c.elementos:
        if e.id in r.regime.saidas:
            assert float(r.tempo.saidas[e.id][-1]) == pytest.approx(
                r.regime.saidas[e.id], abs=0.02
            ), e.nome
    assert r.regime.saidas["t10"] == pytest.approx(35.0)  # o ventilador segura o ajuste
    assert 0 < r.regime.rotacoes["t10"] < 1
    assert r.tempo.rotacoes["t10"][-1] == pytest.approx(r.regime.rotacoes["t10"], rel=1e-3)


def test_vaso_de_expansao_e_a_formula_do_ashrae():
    v = ci.Vaso(volume_L=50.0, precarga_bar=1.5, enchimento_bar=1.5, maxima_bar=3.0)
    pf, pm = 1.5e5 + ci.ATMOSFERA, 3.0e5 + ci.ATMOSFERA
    assert cte.volume_minimo_do_vaso(v, 10.0) == pytest.approx(10.0 / (1 - pf / pm))
    s = cte.estado_do_vaso(v, 10.0)
    assert (s.pressao_bar * 1e5 + ci.ATMOSFERA) == pytest.approx(pf * 50.0 / 40.0)
    assert cte.estado_do_vaso(v, 49.5).cheio
    # o vaso no volume mínimo chega exatamente na pressão máxima
    exato = replace(v, volume_L=cte.volume_minimo_do_vaso(v, 10.0))
    assert cte.estado_do_vaso(exato, 10.0).pressao_bar == pytest.approx(3.0)


def test_cena_marcas_e_registro():
    c = ci.circuito_do_desenho(ci.exemplo_desenhado(), fl.RUGOSIDADES)
    r = cc.calcular(c, cte.Condicoes(t_ar=30.0, t_inicial=25.0))
    dados = cc.cena_do_circuito(r)
    assert any(f["tipo"] == "linha" and f.get("setas") for f in dados["formas"])
    assert [g["titulo"] for g in dados["graficos"]][:2] == [
        "Temperaturas do circuito",
        "Calor (positivo: entra no fluido)",
    ]
    marcas = cc.marcas_para_o_desenho(r)
    assert set(marcas["trechos"]) == {e.id for e in c.elementos}
    assert "kW" in marcas["trechos"]["t4"]["texto"] and "m³/h" in marcas["trechos"]["t2"]["texto"]
    registro = cc.registro(r)
    assert avaliar_contrato_registro(registro)["valido"]
    assert len(fnt.figuras_do_registro(registro["resultados"])) == 2


# ---------------------------------------------------------------------------------------------
# Prancheta
# ---------------------------------------------------------------------------------------------
def _js(expressao: str):
    fonte = (RAIZ / "components" / "prancheta_circuito" / "circuito.js").read_text(encoding="utf-8")
    fonte = fonte.replace("export default function", "function _componente")
    programa = fonte + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8",
        check=True, timeout=30,
    )  # fmt: skip
    return json.loads(saida.stdout)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_prancheta_poe_a_peca_no_meio_do_tubo():
    d = json.dumps(
        {
            "nos": [
                {"id": "n1", "nome": "A", "x": 0, "y": 0, "cota": 0},
                {"id": "n2", "nome": "B", "x": 10, "y": 0, "cota": 2},
            ],
            "trechos": [
                {
                    "id": "t1",
                    "nome": "1",
                    "tipo": "tubo",
                    "de": "n1",
                    "para": "n2",
                    "diametro_mm": 50,
                    "comprimento": 20,
                }
            ],
        }
    )
    r = _js(f"inserirPeca({d}, 't1', [5, 1], 'bomba', 1)")
    tipos = [(t["tipo"], t["de"], t["para"]) for t in r["dados"]["trechos"]]
    assert tipos == [("tubo", "n1", "n3"), ("bomba", "n3", "n4"), ("tubo", "n4", "n2")]
    pontos = {n["id"]: (n["x"], n["cota"]) for n in r["dados"]["nos"]}
    assert pontos["n3"] == (pytest.approx(4.5), pytest.approx(0.9)) and pontos["n4"][
        0
    ] == pytest.approx(5.5)
    bomba = r["dados"]["trechos"][1]
    assert bomba["h0_m"] == 30 and bomba["diametro_mm"] == 50 and bomba["nome"] == "Bomba 1"
    assert [t["comprimento"] for t in r["dados"]["trechos"] if t["tipo"] == "tubo"] == [
        pytest.approx(9),
        pytest.approx(9),
    ]
    apagado = _js(
        f"apagar(inserirPeca({d}, 't1', [5, 1], 'bomba', 1).dados, {{tipo: 'trecho', id: 't2'}})"
    )
    assert [t["tipo"] for t in apagado["trechos"]] == ["tubo", "tubo", "tubo"]  # a peça vira tubo
    assert _js(f"alternarVaso({d}, 'n2').nos.map(n => n.vaso)") == [False, True]
    assert _js(f"inverter({d}, 't1').trechos[0].de") == "n2"
    assert _js(f"inserirPeca({d}, 't1', [5, 0], 'chiller', 8).dados.trechos.map(t => t.tipo)") == [
        "chiller"
    ]


# ---------------------------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------------------------
def test_toda_ajuda_e_usada_e_termina_com_ponto():
    texto = (RAIZ / PAGINA).read_text(encoding="utf-8")
    usadas = set(re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', texto))
    # os campos do painel do selecionado buscam a ajuda pelo nome do campo: AJUDA["c_<campo>"]
    campos = re.findall(r'^\s*\("([A-Za-z_0-9]+)", "', texto, flags=re.M)
    usadas |= {f"c_{campo}" for campo in campos}
    usadas.add("c_cota")
    assert set(AJUDA) <= usadas, sorted(set(AJUDA) - usadas)
    for chave, texto_ in AJUDA.items():
        assert texto_.strip() == texto_ and texto_[-1] in ".!:", chave


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_pagina_resolve_o_exemplo_e_o_painel_muda_o_desenho():
    at = _abrir()
    assert any("O circuito atende" in s.value for s in at.success)
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Vazão da bomba"].endswith("m³/h")
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    }
    sem_ajuda -= {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    for selecao in (
        {"tipo": "trecho", "id": "t10"},
        {"tipo": "trecho", "id": "t4"},
        {"tipo": "no", "id": "n1"},
    ):
        at.session_state["circ_selecao"] = selecao
        at.run()
        assert not at.exception, selecao
    versao = at.session_state["circ_versao"]
    at.session_state["circ_selecao"] = {"tipo": "trecho", "id": "t4"}
    at.run()
    at.number_input(key=f"circ_sel_t4_{versao}_potencia_kW").set_value(60.0).run()
    assert not at.exception
    fonte = next(t for t in at.session_state["circ_dados"]["trechos"] if t["id"] == "t4")
    assert fonte["potencia_kW"] == 60.0
    at.selectbox(key="circ_fluido").set_value("Propilenoglicol a 30 % em água").run()
    assert not at.exception
    at.button(key="circ_limpar").click().run()
    assert any("Desenhe o circuito" in e.value for e in at.error)


def test_chiller_no_limite_com_dry_cooler_depois_fecha_o_regime():
    """O chiller não dá conta sozinho; o dry cooler, com o ventilador controlado, tira o resto."""
    d = ci.exemplo_desenhado()
    d["trechos"].insert(
        9,
        {"id": "t20", "nome": "Chiller 1", "tipo": "chiller", "de": "n9", "para": "n20", "capacidade_kW": 50,
         "t_ajuste": 12, "cop": 3.2, "volume_L": 50, "dp_kPa": 40, "q_nominal_m3h": 10, "diametro_mm": 52.5},
    )  # fmt: skip
    d["nos"].append({"id": "n20", "nome": "M", "x": 22, "y": 11, "cota": 6})
    d["trechos"][10]["de"] = "n20"
    c = ci.circuito_do_desenho(d, fl.RUGOSIDADES)
    r = cc.calcular(c, cte.Condicoes(t_ar=30.0, t_inicial=25.0))
    assert r.regime.calores["t20"] == pytest.approx(-50_000.0, rel=1e-9)
    assert r.regime.calores["t10"] == pytest.approx(-15_000.0, rel=1e-6)
    assert r.regime.saidas["t10"] == pytest.approx(35.0)
    assert r.regime.chiller_no_limite == ("Chiller 1",)
    assert r.status == "ALERTA"
    assert r.tempo is not None
    for id_ in ("t4", "t7", "t20", "t10"):
        assert float(r.tempo.saidas[id_][-1]) == pytest.approx(r.regime.saidas[id_], abs=0.05)
