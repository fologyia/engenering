"""As contas da prancheta de blocos em JS, rodadas no Node: as linhas do cartão e o número digitado."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EDITOR = RAIZ / "components" / "editor_numerico.js"
BLOCOS = RAIZ / "components" / "prancheta_blocos" / "blocos.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node não instalado")


def _rodar(expressao: str):
    """O arquivo junto com a caixinha, como o Python manda, mas sem o ``export`` do módulo."""
    fonte = BLOCOS.read_text(encoding="utf-8").replace(
        "export default function", "function _componente"
    )
    programa = EDITOR.read_text(encoding="utf-8") + fonte
    programa += f"\nconsole.log(JSON.stringify({expressao}));\n"
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


def _pedacos(*textos: str) -> str:
    return json.dumps([{"t": t, "c": f"k{i}"} for i, t in enumerate(textos)], ensure_ascii=False)


@pytest.mark.parametrize(
    "textos",
    [
        ("b = 50 mm", "h = ?"),
        ("D = 100 mm", "L = 100 m", "ε = 0,045 mm", "Q = ?"),
        ("Água a 20 °C", "ρ = 998,2 kg/m³", "μ = 1,002 mPa·s", "g = 9,81 m/s²"),
        ("K_f = 1,6", "K_fs = 1,3", "S_e = 210 MPa", "n = 2", "x = 1", "y = 2"),
        ("Utilização = 100 %", "S_y = 250 MPa", "n = 1,5"),
    ],
)
def test_linhas_do_cartao_iguais_as_de_antes(textos):
    """As linhas com dono por pedaço saem como as de texto corrido, que o cartão já usava."""
    linhas = _rodar(f"quebrarPedacos({_pedacos(*textos)}, 26)")
    antes = _rodar(f"quebrar({json.dumps(' · '.join(textos), ensure_ascii=False)}, 26)")
    assert len(linhas) == len(antes) <= 2
    for linha, texto in zip(linhas, antes, strict=True):
        junto = " · ".join(p["t"] for p in linha["itens"]) + (" …" if linha["mais"] else "")
        assert len(junto) <= 26
        assert junto.split(" · ")[0][:8] == texto.split(" · ")[0][:8]
        assert all(p["c"].startswith("k") for p in linha["itens"])  # o número continua sendo dele


def test_pedaco_comprido_e_cortado_sem_perder_o_dono():
    linhas = _rodar(f"quebrarPedacos({_pedacos('Q = 123456789012345678901234567890 m³/h')}, 26)")
    assert len(linhas) == 1
    (pedaco,) = linhas[0]["itens"]
    assert pedaco["c"] == "k0" and pedaco["t"].endswith("…") and len(pedaco["t"]) == 26


def test_numero_pequeno_nao_vira_zero_na_caixinha():
    assert _rodar("textoParaEditar(1e-7)") == "0,0000001"
    assert _rodar("textoParaEditar(0.045)") == "0,045"
    assert _rodar("textoParaEditar(250)") == "250"
    assert _rodar("textoParaEditar(null)") == ""
    assert _rodar(
        "[mesmoNumero(1e-7, 1.00000000001e-7), mesmoNumero(null, 0), mesmoNumero(null, null)]"
    ) == [
        True,
        False,
        True,
    ]


@pytest.mark.parametrize(
    ("texto", "campo", "esperado"),
    [
        ("350", {"v": 250, "u": "MPa"}, {"valor": 350}),
        ("0,35 GPa", {"v": 250, "u": "MPa"}, {"valor": 350}),
        ("+10", {"v": 250, "u": "MPa"}, {"valor": 260}),
        ("998 kg/m³", {"v": 998.2, "u": "kg/m³"}, {"valor": 998}),
        ("", {"v": 250, "u": "MPa"}, {"valor": None}),
        (
            "*2",
            {"v": None, "u": "mm"},
            {"erro": "Esta letra ainda não tem número: digite o valor."},
        ),
        ("3 kN", {"v": 2, "u": "kN·m"}, {"erro": "kN não combina com kN·m."}),
    ],
)
def test_o_que_se_digita_no_cartao(texto, campo, esperado):
    argumentos = json.dumps([texto, campo], ensure_ascii=False)
    assert _rodar(f"lerDoCartao(...{argumentos})") == esperado
