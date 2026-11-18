"""O tocador de animações: a cena em Python (core/animacao.py) e as contas do JS no Node."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from core import animacao as an

RAIZ = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def _cena() -> an.Cena:
    cena = an.Cena(np.linspace(0, 100, 11), id="x")
    cena.vista = (0, 0, 1, 1)
    return cena


def test_canais_vao_em_float32_na_ordem_quadro_por_canal():
    cena = _cena()
    esc = cena.escala("T", "°C", 0, 10)
    a = cena.canal(np.arange(11.0))
    b = cena.canal(5.0)  # número só = canal constante
    cena.retangulo(0, 0, 1, 1, escala=esc, canal=a)
    dados = cena.como_dados()
    valores = np.frombuffer(base64.b64decode(dados["canais_b64"]), dtype="<f4").reshape(11, 2)
    assert valores[:, a].tolist() == list(range(11)) and set(valores[:, b]) == {5.0}
    assert dados["unidade_tempo"]["rotulo"] == "s" and dados["id"] == "x"


def test_erros_da_cena():
    with pytest.raises(ValueError, match="ordem crescente"):
        an.Cena(np.array([0.0, 2.0, 1.0]))
    cena = _cena()
    with pytest.raises(ValueError, match="um por quadro"):
        cena.canal([1.0, 2.0])
    with pytest.raises(ValueError, match="escala"):
        cena.linha([(0, 0), (1, 1)], canal=0)
    with pytest.raises(ValueError, match="Mapa"):
        cena.escala("T", "°C", 0, 1, cores="arco-íris")
    sem_vista = an.Cena(np.array([0.0]))
    with pytest.raises(ValueError, match="vista"):
        sem_vista.como_dados()


def test_escala_de_faixa_nula_ganha_folga():
    cena = _cena()
    k = cena.escala("T", "°C", 20.0, 20.0)
    esc = cena.como_dados()["escalas"][k]
    assert esc["min"] < 20.0 < esc["max"]


def test_grade_vai_em_0_a_255_dentro_da_escala():
    cena = _cena()
    esc = cena.escala("T", "°C", 0.0, 100.0)
    quadros = np.tile(np.array([0.0, 50.0, 100.0, 200.0]), (11, 1))
    cena.grade([0, 1, 2], [0, 1, 2], np.array([0, 1, 2, 3]), quadros, esc)
    grade = cena.como_dados()["grade"]
    q = np.frombuffer(base64.b64decode(grade["quadros_b64"]), dtype=np.uint8).reshape(11, 4)
    assert q[0].tolist() == [0, 128, 255, 255]
    assert np.frombuffer(base64.b64decode(grade["celulas_b64"]), dtype="<i4").tolist() == [
        0,
        1,
        2,
        3,
    ]


def test_unidade_de_tempo_e_reamostrar():
    assert an.unidade_de_tempo(60).rotulo == "s"
    assert an.unidade_de_tempo(3600).rotulo == "min"
    assert an.unidade_de_tempo(86400).rotulo == "h"
    assert an.unidade_de_tempo(10 * 86400).rotulo == "dias"
    assert an.tempo_em_texto(90.0) == "90,0 s"
    novos = an.reamostrar(
        np.array([0.0, 10.0]), np.array([[0.0, 100.0], [10.0, 200.0]]), np.array([5.0])
    )
    assert novos.tolist() == [[5.0, 150.0]]


# ---------------------------------------------------------------------------------------------
# JS
# ---------------------------------------------------------------------------------------------
def _js(expressao: str):
    fonte = (RAIZ / "components" / "animacao" / "animacao.js").read_text(encoding="utf-8")
    fonte = fonte.replace("export default function", "function _componente")
    programa = fonte + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"], input=programa, capture_output=True, text=True, encoding="utf-8",
        check=True, timeout=30,
    )  # fmt: skip
    return json.loads(saida.stdout)


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_contas_do_tocador():
    assert _js('corNoMapa("agua", 0)') == [205, 226, 251]
    assert _js('corNoMapa("agua", 1)') == [13, 54, 107]
    assert _js('corNoMapa("calor", 2)') == _js('corNoMapa("calor", 1)')  # fora da faixa: o extremo
    assert _js("formatar(1234.567, 1)") == "1.234,6"
    assert _js("formatar(NaN)") == "—"
    assert _js("posicaoDoTempo([0, 10, 20], 15)") == 1.5
    assert _js("posicaoDoTempo([0, 10, 20], 99)") == 2
    # dois quadros, dois canais: [[0, 10], [2, 30]]; o canal 1 no meio vale 20
    assert _js("valorNoCanal([0, 10, 2, 30], 2, 2, 1, 0.5)") == 20
    assert _js("marcasDoEixo(0, 47, 5)") == [0, 10, 20, 30, 40]
    assert _js("casasDoPasso([0, 0.25, 0.5])") == 2
    t = _js("enquadrar({x0: 0, y0: 0, x1: 10, y1: 5}, 220, 120, 10)")
    assert t["escala"] == 20 and t["ox"] == 10 and t["oy"] == 110
    assert _js("pontoNoPoligono([1, 1], [[0, 0], [2, 0], [2, 2], [0, 2]])") is True
    assert _js("alturaDoQuadro({x0: 0, y0: 0, x1: 1, y1: 10}, 600)") == 460


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_base64_do_python_le_igual_no_js():
    valores = np.array([1.5, -2.25, 1e6], dtype="<f4")
    b64 = base64.b64encode(valores.tobytes()).decode("ascii")
    assert _js(f'Array.from(decodificarF32("{b64}"))') == [1.5, -2.25, 1e6]


def test_setas_cota_hachura_e_marcos_vao_na_cena():
    cena = _cena()
    v = cena.canal(np.linspace(-1, 1, 11))
    cena.linha([(0, 0), (1, 0)], fluxo=v, setas=True, cor_setas="#fff", contorno_setas="#000")
    cena.seta(0, 0, 1, 0, comprimento=0.5, canal=v, chega=True, rotulo="{} kW")
    cena.cota((0, 0), (1, 0), "1 m", desloc=10)
    cena.poligono([(0, 0), (1, 0), (1, 1)], cor="#eee", hachura=True, atras=True)
    cena.grafico_no_tempo("x", "m", [("a", v)], marcos=[("estabiliza", 50.0), ("nunca", None)])
    dados = cena.como_dados()
    linha, seta, cota, poligono = dados["formas"]
    assert linha["setas"] and linha["sentido"] == 1 and linha["contorno_setas"] == "#000"
    assert seta["chega"] and seta["ref"] == 1.0 and seta["rotulo"] == "{} kW"
    assert cota["desloc"] == 10.0 and poligono["hachura"] and poligono["atras"]
    assert dados["graficos"][0]["marcos"] == [{"nome": "estabiliza", "tempo": 50.0}]


@pytest.mark.skipif(NODE is None, reason="Node não instalado")
def test_setas_andam_ao_longo_da_linha():
    assert _js("posicoesDasSetas(300, 90, 45, 10)") == [45, 135, 225]
    assert _js("posicoesDasSetas(300, 90, -45, 10)") == [45, 135, 225]  # fase negativa: volta
    assert _js("posicoesDasSetas(300, 90, 0, 10)") == [90, 180, 270]
    assert _js("posicoesDasSetas(15, 90, 0, 10)") == []
    assert _js("pontoNaLinha([[0, 0], [100, 0], [100, 100]], 150)") == [100, 50, 0, 1]
    assert _js("comprimentoDaLinha([[0, 0], [3, 4]])") == 5
