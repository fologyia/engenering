"""Rede de tubos com ramais e malhas (core/rede_de_tubos.py e a página)."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.rede_de_tubos_help import AJUDA
from core import montador_fluidos as fl
from core import rede_de_tubos as rt
from core.montador_funcoes import fator_de_atrito
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/rede_de_tubos.py"
NODE = shutil.which("node")
AGUA = rt.Fluido("Água a 20 °C", 998.2, 1.0016e-3)


def darcy(q: float, comprimento: float, d_mm: float, eps_mm: float, k: float = 0.0) -> float:
    d = d_mm / 1000
    v = q / (math.pi * d**2 / 4)
    re = AGUA.massa_especifica * abs(v) * d / AGUA.viscosidade
    f = fator_de_atrito(re, eps_mm / d_mm)
    return (f * comprimento / d + k) * v * abs(v) / (2 * 9.81)


def test_um_tubo_e_darcy_weisbach():
    nos = [rt.No("R", 0.0, reservatorio=True, nivel_m=30.0), rt.No("A", 5.0, 10.0)]
    trecho = rt.Trecho("T1", "R", "A", 300.0, 102.3, 0.045, k_local=1.5)
    r = rt.resolver(nos, [trecho], AGUA)
    a = r.nos[1]
    assert a.carga_m == pytest.approx(30.0 - darcy(0.010, 300.0, 102.3, 0.045, 1.5), rel=1e-12)
    assert a.pressao_m == pytest.approx(a.carga_m - 5.0)
    assert a.pressao_kPa == pytest.approx(a.pressao_m * 998.2 * 9.81 / 1000)
    assert r.nos[0].vazao_L_s == pytest.approx(10.0)  # o reservatório manda o que se consome
    assert r.trechos[0].regime == "turbulento"


def test_tubos_em_paralelo_perdem_o_mesmo():
    nos = [
        rt.No("R", 0, reservatorio=True, nivel_m=40.0),
        rt.No("A", 0, 0.0),
        rt.No("B", 0, 25.0),
    ]
    trechos = [
        rt.Trecho("T1", "R", "A", 200, 150, 0.045),
        rt.Trecho("T2", "A", "B", 400, 100, 0.045),
        rt.Trecho("T3", "A", "B", 300, 80, 0.15, k_local=2.0),
    ]
    r = rt.resolver(nos, trechos, AGUA)
    _, t2, t3 = r.trechos
    assert t2.vazao_L_s + t3.vazao_L_s == pytest.approx(25.0, rel=1e-9)
    assert t2.perda_m == pytest.approx(t3.perda_m, rel=1e-9)
    assert t2.perda_m == pytest.approx(darcy(t2.vazao_L_s / 1000, 400, 100, 0.045), rel=1e-9)


@pytest.fixture
def malhas():
    nos = [
        rt.No("R1", 0, reservatorio=True, nivel_m=50.0),
        rt.No("R2", 10, reservatorio=True, nivel_m=45.0),
        rt.No("A", 10, 5.0),
        rt.No("B", 12, 8.0),
        rt.No("C", 8, 6.0),
        rt.No("D", 9, 4.0),
    ]
    trechos = [
        rt.Trecho("1", "R1", "A", 500, 200, 0.045),
        rt.Trecho("2", "A", "B", 300, 150, 0.045),
        rt.Trecho("3", "B", "C", 400, 100, 0.045),
        rt.Trecho("4", "A", "D", 400, 150, 0.045),
        rt.Trecho("5", "D", "C", 300, 100, 0.045),
        rt.Trecho("6", "B", "D", 250, 80, 0.045),
        rt.Trecho("7", "R2", "C", 600, 100, 0.045),
    ]
    return nos, trechos


def test_duas_malhas_e_dois_reservatorios_fecham(malhas):
    nos, trechos = malhas
    r = rt.resolver(nos, trechos, AGUA)
    assert rt.soma_nas_malhas(trechos, r) < 1e-9  # Hardy Cross: Σ perdas = 0 em cada malha
    assert r.fornecido_L_s == pytest.approx(r.consumo_L_s, rel=1e-9) == pytest.approx(23.0)
    cargas = {n.nome: n.carga_m for n in r.nos}
    for t, d in zip(r.trechos, trechos, strict=True):
        # A energia de cada trecho: a diferença de carga é a perda, no sentido da água.
        diferenca = cargas[d.de] - cargas[d.para]
        assert diferenca == pytest.approx(math.copysign(t.perda_m, t.vazao_L_s), abs=1e-7)
    # O R2 está mais baixo: recebe água do R1 pela rede.
    r2 = next(n for n in r.nos if n.nome == "R2")
    assert r2.vazao_L_s < 0
    # A estática do nó mais baixo (8 m) com o nível de 50 m passa de 40 m.
    c = next(v for v in r.verificacoes if v.nome == "Pressão máxima no nó C")
    assert c.status == "NÃO OK" and r.status == "NÃO OK"


def test_laminar_e_hagen_poiseuille():
    oleo = rt.Fluido("Óleo", 870.0, 0.04)
    nos = [rt.No("R", 0, reservatorio=True, nivel_m=20.0), rt.No("A", 0, 0.5)]
    r = rt.resolver(nos, [rt.Trecho("T1", "R", "A", 50, 50, 0.045)], oleo)
    v = 0.0005 / (math.pi * 0.05**2 / 4)
    perda = 32 * 0.04 * 50 * v / (870 * 9.81 * 0.05**2)
    assert r.trechos[0].regime == "laminar"
    assert r.nos[1].carga_m == pytest.approx(20.0 - perda, rel=1e-9)


def test_bomba_soma_carga_e_contra_a_bomba_avisa():
    nos = [rt.No("R", 0, reservatorio=True, nivel_m=0.0), rt.No("A", 20.0, 5.0)]
    trecho = rt.Trecho("B1", "R", "A", 100, 100, 0.045, bomba_m=45.0)
    r = rt.resolver(nos, [trecho], AGUA)
    assert r.nos[1].carga_m == pytest.approx(45.0 - darcy(0.005, 100, 100, 0.045), rel=1e-9)
    alto = [
        rt.No("R", 0, reservatorio=True, nivel_m=0.0),
        rt.No("R2", 0, reservatorio=True, nivel_m=60.0),
    ]
    r = rt.resolver(alto, [rt.Trecho("B1", "R", "R2", 100, 100, 0.045, bomba_m=45.0)], AGUA)
    assert r.trechos[0].vazao_L_s < 0
    assert any("contra a bomba" in a for a in r.avisos)


@pytest.mark.parametrize(
    ("nos", "trechos", "trecho_do_erro"),
    [
        ([rt.No("A", 0, 1.0)], [], "pelo menos um reservatório"),
        (
            [rt.No("R", 0, reservatorio=True), rt.No("A", 0, 1.0), rt.No("B", 0, 1.0)],
            [rt.Trecho("T", "R", "A", 10, 50, 0.0)],
            "Sem caminho até um reservatório: B",
        ),
        (
            [rt.No("R", 0, reservatorio=True), rt.No("R", 0, 1.0)],
            [],
            "mesmo nome",
        ),
        (
            [rt.No("R", 0, reservatorio=True), rt.No("A", 0, 1.0)],
            [rt.Trecho("T", "R", "X", 10, 50, 0.0)],
            "não está na tabela",
        ),
        (
            [rt.No("R", 0, reservatorio=True), rt.No("A", 0, 1.0)],
            [rt.Trecho("T", "R", "A", 0.0, 50, 0.0)],
            "maiores que zero",
        ),
    ],
)
def test_tabela_errada_explica(nos, trechos, trecho_do_erro):
    assert any(trecho_do_erro in e for e in rt.problemas(nos, trechos))
    with pytest.raises(rt.ErroDaRede):
        rt.resolver(nos, trechos or [rt.Trecho("T", "R", "A", 1, 1, 0)], AGUA)


def test_csv_e_registro(malhas):
    nos, trechos = malhas
    r = rt.resolver(nos, trechos, AGUA)
    texto = rt.csv_da_rede(r).decode("utf-8-sig")
    assert texto.startswith("Nó;Tipo") and "Trecho;Sentido" in texto
    registro = rt.registro_da_rede(nos, trechos, r)
    json.dumps(registro)
    assert (
        registro["modulo_id"] == rt.MODULO_ID and registro["resultados"]["status_geral"] == "NÃO OK"
    )


# ------------------------------------------------------------------ a rede desenhada
def test_exemplo_desenhado_e_a_mesma_rede_das_tabelas(malhas):
    desenho = rt.exemplo_desenhado()
    nos, trechos, faltas = rt.rede_do_desenho(desenho, fl.RUGOSIDADES)
    assert faltas == [] and rt.problemas(nos, trechos) == []
    comprimentos = {t.nome: t.comprimento_m for t in trechos}
    assert comprimentos["1"] == 500.0  # o real informado manda
    assert comprimentos["2"] == pytest.approx(300.0)  # os outros saem do desenho
    assert comprimentos["6"] == pytest.approx(300.0 * math.sqrt(2))
    assert {t.nome: (t.de, t.para) for t in trechos}["7"] == ("R2", "C")
    assert all(t.rugosidade_mm == pytest.approx(0.045) for t in trechos)
    r = rt.resolver(nos, trechos, AGUA)
    assert r.status == "OK" and r.consumo_L_s == pytest.approx(23.0)


def test_o_que_falta_preencher():
    desenho = rt.exemplo_desenhado()
    desenho["trechos"][1]["diametro"] = None
    desenho["trechos"][2]["material"] = rt.OUTRO_MATERIAL
    desenho["nos"][3]["x"] = desenho["nos"][2]["x"]  # B em cima de A: o tubo 2 fica sem tamanho
    _, _, faltas = rt.rede_do_desenho(desenho, fl.RUGOSIDADES)
    assert any("tubo 2 não tem diâmetro" in f for f in faltas)
    assert any("tubo 3 é de material Outro" in f for f in faltas)
    assert any("tubo 2 tem as duas pontas no mesmo lugar" in f for f in faltas)
    desenho["trechos"][2]["rugosidade"] = 0.1
    _, trechos, faltas = rt.rede_do_desenho(desenho, fl.RUGOSIDADES)
    assert not any("tubo 3" in f for f in faltas)
    assert trechos[2].rugosidade_mm == 0.1


def test_marcas_no_desenho():
    desenho = rt.exemplo_desenhado()
    nos, trechos, _ = rt.rede_do_desenho(desenho, fl.RUGOSIDADES)
    r = rt.resolver(nos, trechos, AGUA, rt.Limites(pressao_min_m=33.0))
    marcas = rt.marcas_para_o_desenho(desenho, r)
    assert set(marcas["nos"]) == {n["id"] for n in desenho["nos"]}
    assert set(marcas["trechos"]) == {t["id"] for t in desenho["trechos"]}
    assert marcas["nos"]["n4"]["ruim"]  # B, com 32,4 m, fica abaixo dos 33 m pedidos
    assert not marcas["nos"]["n3"]["ruim"] and marcas["nos"]["n3"]["texto"].startswith("p = ")
    assert marcas["nos"]["n1"]["texto"].startswith("NA 46,00 m · ")
    assert marcas["trechos"]["t6"]["sentido"] == -1  # a água vai de D para B
    assert "L/s" in marcas["trechos"]["t1"]["texto"]


def _js(expressao: str):
    fonte = (RAIZ / "components" / "prancheta_rede" / "rede.js").read_text(encoding="utf-8")
    fonte = fonte.replace("export default function", "function _componente")
    programa = fonte + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8",
        check=True, timeout=30,
    )  # fmt: skip
    return json.loads(saida.stdout)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_prancheta_divide_apaga_e_da_nome():
    d = json.dumps(
        {
            "nos": [
                {"id": "n1", "nome": "R1", "tipo": "reservatorio", "x": 0, "y": 0, "cota": 0},
                {"id": "n2", "nome": "A", "tipo": "consumo", "x": 10, "y": 0, "cota": 10},
            ],
            "trechos": [
                {"id": "t1", "nome": "1", "de": "n1", "para": "n2", "comprimento": 100,
                 "diametro": 100, "bomba": 5},
            ],
        }
    )  # fmt: skip
    r = _js(f"dividirTrecho({d}, 't1', [4, 3])")
    novo = next(n for n in r["dados"]["nos"] if n["id"] == r["no"])
    assert (novo["x"], novo["y"], novo["cota"], novo["nome"]) == (4, 0, 4, "B")
    t1, t2 = r["dados"]["trechos"]
    assert (t1["para"], t2["de"], t2["para"]) == (r["no"], r["no"], "n2")
    assert (t1["comprimento"], t2["comprimento"]) == (pytest.approx(40), pytest.approx(60))
    assert (t1["bomba"], t2["bomba"]) == (5, 0)  # a bomba fica num só
    apagado = _js(f"apagar(dividirTrecho({d}, 't1', [4, 3]).dados, {{tipo: 'no', id: 'n3'}})")
    assert [n["id"] for n in apagado["nos"]] == ["n1", "n2"] and apagado["trechos"] == []
    assert _js('[proximoNome(["A", "B", "R1"], "consumo"), proximoNome(["R1"], "reservatorio"), '
               'proximoNome(["1", "2"], "tubo")]') == ["C", "R2", "3"]  # fmt: skip
    assert _js(f"comprimentoDesenhado({d}, {{de: 'n1', para: 'n2'}})") == 10


def test_toda_ajuda_e_usada_e_termina_com_ponto():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and texto[-1] in ".!:", chave


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_pagina_resolve_o_exemplo():
    at = _abrir()
    assert any("A rede atende" in s.value for s in at.success)
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Consumo"] == "23,00 L/s"
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    }
    sem_ajuda -= {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    at.number_input(key="rede_p_min").set_value(35.0).run()
    assert not at.exception
    assert any("não atende" in e.value for e in at.error)
    at.selectbox(key="rede_fluido").set_value("Óleo hidráulico ISO VG 46 a 40 °C").run()
    assert not at.exception


def test_painel_do_selecionado_muda_o_desenho():
    at = _abrir()
    at.session_state["rede_selecao"] = {"tipo": "trecho", "id": "t2"}
    at.run()
    versao = at.session_state["rede_versao"]
    chave = f"rede_sel_t2_{versao}_diametro"
    at.number_input(key=chave).set_value(80.0).run()
    assert not at.exception
    tubo = next(t for t in at.session_state["rede_dados"]["trechos"] if t["id"] == "t2")
    assert tubo["diametro"] == 80.0 and at.session_state["rede_versao"] == versao + 1
    at.session_state["rede_selecao"] = {"tipo": "no", "id": "n4"}
    at.run()
    versao = at.session_state["rede_versao"]
    at.number_input(key=f"rede_sel_n4_{versao}_retirada").set_value(12.0).run()
    no = next(n for n in at.session_state["rede_dados"]["nos"] if n["id"] == "n4")
    assert no["retirada"] == 12.0
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Consumo"] == "27,00 L/s"


def test_limpar_e_voltar_ao_exemplo():
    at = _abrir()
    at.button(key="rede_limpar").click().run()
    assert not at.exception
    assert at.session_state["rede_dados"] == {"nos": [], "trechos": []}
    assert any("Desenhe ao menos" in i.value for i in at.info)
    at.button(key="rede_exemplo").click().run()
    assert len(at.session_state["rede_dados"]["trechos"]) == 7
