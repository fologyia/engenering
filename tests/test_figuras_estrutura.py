"""Desenhos em SVG: vento nos pórticos, planta e elevação do contraventamento, chapa de nó."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from components import figuras_estrutura as fig
from core import contraventamento_ligacao as lig
from core import contraventamento_plataforma as cp
from core import contraventamento_ufm as ufm
from core import vento_estrutura_aberta as va
from tests.test_contraventamento_ligacao import exemplo_5_1
from tests.test_vento_estrutura_aberta import VENTO, plataforma

SVG = "{http://www.w3.org/2000/svg}"


def raiz(svg: str) -> ET.Element:
    elemento = ET.fromstring(svg)
    assert elemento.tag == f"{SVG}svg"
    assert float(elemento.get("width", "0")) > 0 and float(elemento.get("height", "0")) > 0
    return elemento


def textos(svg: str) -> str:
    return " ".join("".join(t.itertext()) for t in raiz(svg).iter(f"{SVG}text"))


@pytest.mark.parametrize("cotas", [(4.0,), (3.0, 6.0, 9.0)])
@pytest.mark.parametrize("direcao", ["X", "Y"])
def test_vento_nos_porticos_mostra_um_valor_por_nivel(cotas, direcao):
    g = plataforma(cotas_m=cotas)
    r = va.calcular_vento_aberto(g, VENTO).direcao(direcao)
    escrito = textos(fig.svg_vento_elevacao(g, r))
    for nivel in r.niveis:
        assert f"{nivel.total_kN:.1f}".replace(".", ",") in escrito


@pytest.fixture(scope="module")
def contraventamento() -> tuple[cp.EntradaContraventamento, cp.ResultadoContraventamento]:
    e = replace(cp.EntradaContraventamento(), cotas_m=(3.0, 6.0))
    return e, cp.calcular(e)


def test_planta_e_elevacao_sao_svg_valido(contraventamento):
    e, r = contraventamento
    raiz(fig.svg_planta(e))
    for direcao in ("X", "Y"):
        raiz(fig.svg_elevacao_linha(e, r.andares_da_direcao(direcao), direcao))


@pytest.mark.parametrize(
    "troca",
    [
        {},
        {"caso": ufm.CASO_1, "x_mm": 0.0, "y_mm": 0.0},
        {"caso": ufm.CASO_3},
        {"ligacao_na_mesa_da_coluna": False},
        {"theta_graus": 30.0},
        {"theta_graus": 60.0, "fileiras": 1, "por_fileira": 3},
    ],
)
def test_chapa_de_no_e_svg_valido_com_as_forcas(troca):
    r = lig.calcular_ligacao(exemplo_5_1(**troca))
    escrito = textos(fig.svg_ligacao(r))
    assert "Whitmore" in escrito
    P = max(r.entrada.P_tracao_kN, r.entrada.P_compressao_kN)
    assert f"P = {P:.0f} kN" in escrito
    assert f"H_b = {r.forcas.viga_cisalhamento_kN:.0f} kN" in escrito
    assert ("Chapa–coluna" in escrito) is (r.entrada.caso != ufm.CASO_3)


def test_convencao_de_eixos_mostra_o_vento_e_o_eixo_vertical():
    from core import exportacao_cargas as ex

    solidworks = textos(fig.svg_convencao_de_eixos(ex.EIXO_Y_PARA_CIMA))
    robot = textos(fig.svg_convencao_de_eixos(ex.EIXO_Z_PARA_CIMA))
    for escrito in (solidworks, robot):
        for direcao in ("W0 → +X", "W90 → +Y", "W180 → −X", "W270 → −Y"):
            assert direcao in escrito
    assert "No SolidWorks (Y para cima)" in solidworks
    assert "No SolidWorks" not in robot


@pytest.mark.parametrize(
    ("divisor", "maximo", "texto"),
    [(400, None, "δ ≤ H/400 = 15,0 mm"), (300, 10.0, "δ ≤ H/300 (máx. 10 mm) = 10,0 mm")],
)
def test_limite_de_deslocamento(divisor, maximo, texto):
    assert texto in textos(fig.svg_limite_de_deslocamento(divisor, maximo, 6.0))
