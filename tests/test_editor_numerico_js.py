"""A lógica das pranchetas em JS, rodada no Node: o que se digita e a geometria das chapas."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EDITOR = RAIZ / "components" / "editor_numerico.js"
GEOMETRIA = RAIZ / "components" / "prancheta" / "geometria.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node não instalado")


def _rodar(fonte: Path, expressao: str):
    programa = fonte.read_text(encoding="utf-8") + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(saida.stdout)


def _ler(texto: str, atual: float = 100.0, unidade: str = "mm"):
    argumentos = json.dumps([texto, atual, unidade], ensure_ascii=False)
    return _rodar(EDITOR, f"lerValorDigitado(...{argumentos})")


# ---------------------------------------------------------------------------
# O que se digita
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("150", 150.0),
        ("1,5", 1.5),
        ("1.5", 1.5),
        ("1.200,5", 1200.5),
        ("300/2", 150.0),
        ("2*150+10", 310.0),
        ("(100+50)/3", 50.0),
        ("2x150", 300.0),
        ("-20", -20.0),
    ],
)
def test_numero_e_conta(texto, esperado):
    assert _ler(texto)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "unidade", "esperado"),
    [
        ("1,5 m", "mm", 1500.0),
        ("2 pol", "mm", 50.8),
        ('2"', "mm", 50.8),
        ("10 cm", "mm", 100.0),
        ("3000 mm", "m", 3.0),
        ("5 kN", "N", 5000.0),
        ("500 N", "kN", 0.5),
        ("100 kgf", "kN", 0.980665),
        ("2 tf", "kN", 19.6133),
        ("10 bar", "MPa", 1.0),
        ("1500 N·mm", "N·m", 1.5),
        ("2 kN.m", "N·m", 2000.0),
        ("300/2 mm", "mm", 150.0),
        ("2 cm²", "mm²", 200.0),
    ],
)
def test_unidade_digitada_converte_para_a_do_campo(texto, unidade, esperado):
    assert _ler(texto, unidade=unidade)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("+10", 110.0), ("*1,5", 150.0), ("/4", 25.0), ("+5 cm", 150.0)],
)
def test_valor_relativo_parte_do_atual(texto, esperado):
    assert _ler(texto, 100.0)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "unidade", "trecho"),
    [
        ("", "mm", "Digite"),
        ("abc", "mm", "não combina"),
        ("5 kN", "mm", "não combina"),
        ("5 mm", "", "não tem unidade"),
        ("3+", "mm", "Não entendi"),
        ("(2", "mm", "Não entendi"),
        ("1/0", "mm", "Não entendi"),
        ("/0", "mm", "dividir por zero"),
    ],
)
def test_digitacao_ruim_vira_motivo_e_nao_numero(texto, unidade, trecho):
    lido = _ler(texto, unidade=unidade)
    assert "valor" not in lido
    assert trecho in lido["erro"]


def test_texto_do_usuario_nao_e_executado():
    lido = _ler("process.exit(1)")
    assert "erro" in lido


@pytest.mark.parametrize(
    ("valor", "passo", "esperado"),
    [(150.0, 5.0, 5.0), (150.0, None, 10.0), (3.5, None, 0.1), (0.0, None, 0.1)],
)
def test_passo_das_setas(valor, passo, esperado):
    argumentos = json.dumps([valor, passo])
    assert _rodar(EDITOR, f"passoDoValor(...{argumentos})") == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Geometria da seção
# ---------------------------------------------------------------------------


def _ret(x, y, b, h, **extra):
    return {"forma": "ret", "x": x, "y": y, "b": b, "h": h, "giro": 0, "furo": False, **extra}


def _i():
    """Mesa de baixo, alma e mesa de cima: 300 × 150, mesas de 20 e alma de 10."""
    return [_ret(75, 10, 150, 20), _ret(75, 150, 10, 260), _ret(75, 290, 150, 20)]


def _chamar(partes, funcao, *argumentos):
    dados = json.dumps(partes, ensure_ascii=False)
    resto = ", ".join(json.dumps(a, ensure_ascii=False) for a in argumentos)
    return _rodar(GEOMETRIA, f"(() => {{const p = {dados}; {funcao}(p, {resto}); return p}})()")


def _bordas(p):
    return p["x"] - p["b"] / 2, p["y"] - p["h"] / 2, p["x"] + p["b"] / 2, p["y"] + p["h"] / 2


def test_alma_mais_alta_empurra_a_mesa_de_cima_e_nada_solta():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 1, "h", 300)
    assert alma["h"] == 300
    assert _bordas(alma)[1] == pytest.approx(_bordas(base)[3])
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] == pytest.approx(340)


def test_mesa_de_baixo_mais_grossa_sobe_o_resto():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 0, "h", 30)
    assert _bordas(base)[:2] == pytest.approx((0, 0))
    assert _bordas(alma)[1] == pytest.approx(30)
    assert _bordas(topo)[3] == pytest.approx(310)


def test_mesa_de_cima_mais_grossa_nao_invade_a_alma():
    """Era o limite antigo: crescer do centro fazia a mesa entrar na alma."""
    _, alma, topo = _chamar(_i(), "dimensionarParte", 2, "h", 30)
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] == pytest.approx(310)


def test_mesa_mais_larga_fica_centrada_e_nao_mexe_na_outra():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 2, "b", 200)
    assert topo["b"] == 200
    assert topo["x"] == pytest.approx(alma["x"])
    assert base["b"] == 150  # dá para ter mesas diferentes


def test_alma_mais_grossa_continua_centrada():
    _, alma, _ = _chamar(_i(), "dimensionarParte", 1, "b", 16)
    assert alma["x"] == pytest.approx(75)
    assert alma["b"] == 16


def test_duas_almas_de_caixao_crescem_juntas():
    partes = [
        _ret(100, 5, 200, 10),
        _ret(5, 110, 10, 200),
        _ret(195, 110, 10, 200),
        _ret(100, 215, 200, 10),
    ]
    _, a, b, topo = _chamar(partes, "dimensionarParte", 1, "h", 240)
    assert a["h"] == b["h"] == 240
    assert _bordas(b)[3] == pytest.approx(_bordas(topo)[1])


def test_chapas_lado_a_lado_empurram_para_os_dois_lados():
    partes = [_ret(50, 50, 100, 100), _ret(150, 50, 100, 100), _ret(250, 50, 100, 100)]
    a, b, c = _chamar(partes, "dimensionarParte", 1, "b", 120)
    assert _bordas(a)[2] == pytest.approx(_bordas(b)[0])
    assert _bordas(c)[0] == pytest.approx(_bordas(b)[2])


def test_furo_acompanha_a_chapa_que_andou():
    partes = [
        _ret(50, 50, 100, 100),
        _ret(50, 150, 100, 100),
        {"forma": "circ", "x": 50, "y": 150, "b": 20, "h": 20, "giro": 0, "furo": True},
    ]
    _, chapa, furo = _chamar(partes, "dimensionarParte", 0, "h", 130)
    assert chapa["y"] == pytest.approx(180)
    assert furo["y"] == pytest.approx(180)


def test_circulo_muda_os_dois_lados():
    partes = [{"forma": "circ", "x": 0, "y": 0, "b": 50, "h": 50, "giro": 0, "furo": False}]
    circulo = _chamar(partes, "dimensionarParte", 0, "b", 80)[0]
    assert (circulo["b"], circulo["h"]) == (80, 80)


def test_medida_invalida_nao_mexe_em_nada():
    assert _chamar(_i(), "dimensionarParte", 1, "h", -5) == _i()
    assert _chamar(_i(), "dimensionarParte", 1, "h", 0) == _i()


def test_altura_total_estica_a_alma_e_mantem_as_mesas():
    base, alma, topo = _chamar(_i(), "esticarConjunto", "h", 400)
    assert (base["h"], topo["h"]) == (20, 20)
    assert alma["h"] == 360
    assert _bordas(alma)[1] == pytest.approx(_bordas(base)[3])
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] - _bordas(base)[1] == pytest.approx(400)


def test_largura_total_alarga_as_mesas_e_nao_a_alma():
    base, alma, topo = _chamar(_i(), "esticarConjunto", "b", 200)
    assert (base["b"], topo["b"]) == (200, 200)
    assert alma["b"] == 10
    assert alma["x"] == pytest.approx(base["x"])


def test_largura_total_do_u_mantem_a_alma_na_borda():
    partes = [_ret(50, 10, 100, 20), _ret(5, 100, 10, 160), _ret(50, 190, 100, 20)]
    mesa, alma, _ = _chamar(partes, "esticarConjunto", "b", 140)
    assert mesa["b"] == 140
    assert _bordas(alma)[0] == pytest.approx(_bordas(mesa)[0])


def test_tubo_redondo_muda_de_escala():
    partes = [
        {"forma": "circ", "x": 0, "y": 0, "b": 100, "h": 100, "giro": 0, "furo": False},
        {"forma": "circ", "x": 0, "y": 0, "b": 80, "h": 80, "giro": 0, "furo": True},
    ]
    fora, furo = _chamar(partes, "esticarConjunto", "b", 150)
    assert fora["b"] == pytest.approx(150)
    assert furo["b"] == pytest.approx(120)
