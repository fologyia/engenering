"""Vigas e eixos com a prancheta: o desenho vira o modelo em texto, o resultado volta ao desenho
(core/viga_desenhada.py, components/prancheta_viga e a página)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from components import volta_da_secao as vs
from core import beam_analysis as vb
from core import beam_script as escrita
from core import elementos_vigas as ev
from core import section_catalog as catalogo
from core import viga_desenhada as vd

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/vigas_eixos.py"
NODE = shutil.which("node")
SECAO = ["secao retangular 100 200", "material aco"]


def _resolver(dados) -> vb.ResultadoViga:
    return vb.analisar_viga(escrita.interpretar("\n".join([*SECAO, *vd.linhas_do_desenho(dados)])))


def test_o_exemplo_e_a_biapoiada_de_sempre():
    dados = vd.exemplo()
    assert vd.linhas_do_desenho(dados) == [
        "viga 6",
        "apoio 0 pino",
        "apoio 6 rolete",
        "q 0 6 -15",
        "P 3 -20",
    ]
    r = _resolver(dados)
    marcas = vd.marcas(r, dados)
    assert [m["texto_fy"] for m in marcas["reacoes"]] == ["A: 55,00 kN", "B: 55,00 kN"]
    assert all(m["fy"] == pytest.approx(55.0) for m in marcas["reacoes"])  # para cima


def test_todos_os_tipos_vao_ao_texto_e_voltam():
    dados = {
        "L": 8.0,
        "apoios": [
            {"nome": "A", "tipo": vd.ENGASTE, "x": 0},
            {"nome": "B", "tipo": vd.MOLA, "x": 8, "kv": 500, "kr": None},
            {"nome": "C", "tipo": vd.TRAVA, "x": 8},
        ],
        "rotulas": [{"nome": "R1", "x": 4}],
        "cargas": [
            {"nome": "P1", "tipo": vd.FORCA, "x": 2, "valor": -10, "caso": "Sobrecarga"},
            {"nome": "M1", "tipo": vd.MOMENTO, "x": 6, "valor": 5},
            {"nome": "q1", "tipo": vd.DISTRIBUIDA, "x": 5, "x2": 1, "valor": -2, "valor2": -4},
            {"nome": "N1", "tipo": vd.AXIAL, "x": 8, "valor": -30, "e": 50},
            {"nome": "n1", "tipo": vd.AXIAL_DIST, "x": 0, "x2": 8, "valor": 1},
            {"nome": "T1", "tipo": vd.TORQUE, "x": 3, "valor": 1.5, "caso": "Peso próprio"},
        ],
    }
    linhas = vd.linhas_do_desenho(dados)
    assert "apoio 8 mola kv=500" in linhas and "apoio 8 trava_axial" in linhas
    assert "rotula 4" in linhas
    assert "P 2 -10 caso=Sobrecarga" in linhas
    assert "q 1 5 -2 -4" in linhas  # o trecho sai em ordem
    assert "N 8 -30 e=50" in linhas
    assert 'T 3 1.5 caso="Peso próprio"' in linhas
    viga = escrita.interpretar("\n".join([*SECAO, *linhas]))
    de_volta = vd.desenho_do_modelo(viga)
    assert [a["tipo"] for a in de_volta["apoios"]] == [vd.ENGASTE, vd.MOLA, vd.TRAVA]
    assert {c["tipo"] for c in de_volta["cargas"]} == set(vd.CARGAS)
    assert next(c for c in de_volta["cargas"] if c["tipo"] == vd.TORQUE)["caso"] == "Peso próprio"


@pytest.mark.parametrize("nome", list(escrita.EXEMPLOS))
def test_cada_exemplo_pronto_vai_ao_desenho_sem_mudar_a_conta(nome):
    original = escrita.interpretar(escrita.EXEMPLOS[nome])
    dados = vd.desenho_do_modelo(original)
    texto = escrita.EXEMPLOS[nome]
    # o desenho só descreve a barra, os apoios e as cargas: o resto continua como no exemplo
    resto = [
        linha
        for linha in texto.splitlines()
        if linha.split("#")[0].strip().split(" ")[0] in {"secao", "material", "peso_proprio",
                                                          "segunda_ordem", "divisoes", "combinacao"}
    ]  # fmt: skip
    refeito = escrita.interpretar("\n".join([*resto, *vd.linhas_do_desenho(dados)]))
    a, b = vb.analisar_viga(original), vb.analisar_viga(refeito)
    assert [r.fy_N for r in a.reacoes] == pytest.approx([r.fy_N for r in b.reacoes], abs=1e-6)
    assert a.extremos["momento"].valor == pytest.approx(b.extremos["momento"].valor, rel=1e-9)


def test_o_que_falta_e_o_desenho_estragado():
    assert vd.problemas(vd.vazio()) == [
        "Ponha ao menos um apoio na barra (Pino, Rolete ou Engaste)."
    ]
    dados = vd.exemplo()
    dados["apoios"].append({"nome": "C", "tipo": vd.MOLA, "x": 3})
    dados["cargas"].append({"nome": "q9", "tipo": vd.DISTRIBUIDA, "x": 2, "x2": 2, "valor": -1})
    faltam = vd.problemas(dados)
    assert any("mola C" in f for f in faltam) and any("q9" in f for f in faltam)
    estragado = {
        "L": "abc",
        "apoios": [{"tipo": "Nave"}, None],
        "cargas": [{"tipo": vd.FORCA, "x": "nan"}],
    }
    limpo = vd.normalizar(estragado)
    assert limpo["L"] == 6.0 and limpo["apoios"] == [] and limpo["cargas"][0]["x"] == 0.0


def _js(expressao: str):
    fonte = (RAIZ / "components" / "prancheta_viga" / "viga.js").read_text(encoding="utf-8")
    fonte = fonte.replace("export default function", "function _componente")
    programa = fonte + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8",
        check=True, timeout=30,
    )  # fmt: skip
    return json.loads(saida.stdout)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_prancheta_estica_muda_o_comprimento_e_da_nome():
    d = json.dumps(vd.exemplo())
    # A cota de 3 m (do P1 ao fim) passa a 4 m: o rolete, o fim da carga e a ponta vão junto.
    r = _js(f"esticar({d}, 6, 1)")
    assert r["L"] == 7 and r["apoios"][1]["x"] == 7 and r["cargas"][0]["x2"] == 7
    assert r["cargas"][1]["x"] == 3  # o que está antes não anda
    r = _js(f"novoComprimento({d}, 4)")
    assert r["L"] == 4 and r["apoios"][1]["x"] == 4 and r["cargas"][0]["x2"] == 4
    assert r["cargas"][1]["x"] == 3
    assert _js(f"pontosDaBarra({d})") == [0, 3, 6]
    assert _js("[noIma(2.96, [0, 3, 6], 0.1), noIma(2.5, [0, 3, 6], 0.1)]") == [3, None]
    assert _js('nomeLivre([{nome: "A"}, {nome: "B"}], letra)') == "C"


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_pagina_abre_no_desenho_e_resolve_sozinha():
    at = _abrir()
    assert at.segmented_control(key="vigas_modo").value == "Desenho"
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Cortante máximo |V|"] == "55.00 kN"
    assert metricas["Momento máximo |M|"] == "97.50 kN·m"
    assert not any(b.label == "Calcular diagramas" for b in at.button)
    # o desenho mudou (como a prancheta manda): a conta refaz
    dados = vd.exemplo()
    dados["cargas"] = [c for c in dados["cargas"] if c["tipo"] == vd.FORCA]
    at.session_state["vigas_desenho"] = dados
    at.session_state["vigas_desenho_versao"] = 5
    at.run()
    assert {m.label: m.value for m in at.metric}["Cortante máximo |V|"] == "10.00 kN"


def test_exemplo_pronto_texto_e_comecar_do_zero():
    at = _abrir()
    at.selectbox(key="vigas_exemplo_desenho").set_value("Viga Gerber (com rótula interna)").run()
    at.button(key="vigas_levar_exemplo").click().run()
    assert not at.exception
    assert len(at.session_state["vigas_desenho"]["rotulas"]) == 1
    at.button(key="vigas_limpar_desenho").click().run()
    assert not at.exception
    assert at.session_state["vigas_desenho"]["apoios"] == []
    assert any("Ponha ao menos um apoio" in i.value for i in at.info)
    at.button(key="vigas_trazer_texto").click().run()  # o texto do começo: a biapoiada
    assert [a["tipo"] for a in at.session_state["vigas_desenho"]["apoios"]] == [vd.PINO, vd.ROLETE]
    at.segmented_control(key="vigas_modo").set_value("Texto (script)").run()
    assert not at.exception
    assert any(b.label == "Calcular diagramas" for b in at.button)


def test_barra_que_nao_fica_parada_diz_o_motivo():
    at = _abrir()
    dados = vd.exemplo()
    dados["apoios"] = [{"nome": "A", "tipo": vd.ROLETE, "x": 0}]
    at.session_state["vigas_desenho"] = dados
    at.session_state["vigas_desenho_versao"] = 9
    at.run()
    assert not at.exception
    assert any("Não foi possível resolver a barra" in e.value for e in at.error)


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield
        ev._analisar_desenho.cache_clear()


def test_desenhar_a_secao_e_voltar_com_ela(catalogo_vazio):
    at = _abrir()
    at.segmented_control(key="vigas_form_tipo_secao").set_value("Perfil do catálogo").run()
    at.button(key="vigas_desenhar_secao").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state[vs.VOLTA]["destino"] == "vigas"
    at.switch_page(vs.PAGINA_DESENHAR)
    at.text_input(key="secao_nome").set_value("Seção da viga").run()
    at.button(key="secao_salvar_e_voltar").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.selectbox(key="vigas_form_perfil").value == "Seção da viga"
    assert {m.label: m.value for m in at.metric}["Seção"] == "Seção da viga"
