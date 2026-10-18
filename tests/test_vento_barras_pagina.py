"""Vento barra a barra pela interface (AppTest) e os desenhos dele (SVG)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components import figuras_vento as fv
from components import vento_aberto_ui
from components.vento_barras_help import AJUDA
from core import vento_por_barras as vpb
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_vento_por_barras import VENTO, _grade

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/vento_estrutura_aberta.py"
SVG = "{http://www.w3.org/2000/svg}"


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(
            r'AJUDA\["([A-Za-z_0-9]+)"\]',
            (RAIZ / "components/vento_barras_ui.py").read_text(encoding="utf-8"),
        )
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


@pytest.fixture(scope="module")
def resultado() -> vpb.ResultadoPorBarras:
    elementos = (
        vpb.ElementoAoVento("GC", vpb.TIPO_GUARDA_CORPO, (0.0, 0.0, 4.0), (6.0, 0.0, 4.0)),
        vpb.ElementoAoVento("Vaso", vpb.TIPO_CILINDRO, (3.0, 3.0, 4.0), altura_m=1.5),
        vpb.ElementoAoVento("Painel", vpb.TIPO_CAIXA, (9.0, 3.0, 4.0), altura_m=1.0),
    )
    return vpb.calcular(
        vpb.EntradaPorBarras(
            tuple(_grade()), VENTO, elementos=elementos, direcoes=vpb.DIRECOES_COM_DIAGONAIS
        )
    )


def _textos(svg: str) -> str:
    raiz = ET.fromstring(svg)
    assert raiz.tag == f"{SVG}svg" and float(raiz.get("width", "0")) > 0
    return " ".join("".join(t.itertext()) for t in raiz.iter(f"{SVG}text"))


@pytest.mark.parametrize("angulo", vpb.DIRECOES_COM_DIAGONAIS)
def test_os_tres_desenhos_sao_svg_valido_em_toda_direcao(resultado, angulo):
    tres_d = _textos(fv.svg_vento_3d(resultado, angulo))
    assert f"Vento a {angulo}°" in tres_d and "kN/m" in tres_d
    maior = max(resultado.direcao(angulo).barras, key=lambda f: f.forca_kN)
    assert f"{maior.kN_m:.3f}".replace(".", ",") in tres_d  # a barra mais carregada tem o valor
    planta = _textos(fv.svg_vento_planta(resultado, angulo))
    sombra = _textos(fv.svg_vento_sombra(resultado, angulo))
    if angulo % 90 == 0:
        assert "R1 · η 1,00" in planta and "R1: φ" in sombra
    else:
        assert "C_a = 2,0" in sombra


def test_metodo_barra_a_barra_abre_com_ajuda_em_tudo_e_os_desenhos(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    t.session_state["va_metodo"] = vento_aberto_ui.METODO_BARRAS
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Direção que mais carrega"].startswith("W")
    assert len(t.get("imgs")) + len(t.get("image")) >= 3
    textos = " ".join(str(m.value) for m in t.markdown)
    assert "viga a viga" in textos.lower() or "Como o programa faz" in " ".join(
        s.value for s in t.subheader
    )


def test_so_as_perpendiculares_pela_interface(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    t.session_state["va_metodo"] = vento_aberto_ui.METODO_BARRAS
    t.session_state["vb_direcoes"] = "Só as 4 perpendiculares às faces (NBR 6123, 8.5)"
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    radio = next(r for r in t.radio if r.label == "Direção mostrada")
    assert [o.split(" ")[0] for o in radio.options] == ["W0", "W90", "W180", "W270"]
