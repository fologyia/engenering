"""Tamanho das figuras: branco aparado, dobro de pixels e nada esticado na tela."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from streamlit.testing.v1 import AppTest

from components import assistente_cargas_ui as ui
from components import figuras as fg
from core import beam_charts as bc
from core import desenho_tensoes as dt
from core import elementos_catalogo as cat
from core.elementos_base import Grafico, calcular_caso

RAIZ = Path(__file__).resolve().parents[1]


def _quadro(caixa: tuple[int, int, int, int], tamanho=(2000, 1000)) -> Image.Image:
    imagem = Image.new("RGB", tamanho, "#ffffff")
    ImageDraw.Draw(imagem).rectangle(caixa, fill="#334155")
    return imagem


def _abrir(figura: bc.ImagemDiagrama) -> Image.Image:
    return Image.open(io.BytesIO(figura.png)).convert("RGB")


def test_apara_o_branco_e_deixa_a_margem():
    figura = bc.figura_final(_quadro((900, 400, 1499, 599)), "t", "l")
    folga = bc.MARGEM_DA_FIGURA * bc.DENSIDADE
    assert _abrir(figura).size == (600 + 2 * folga, 200 + 2 * folga)
    assert _abrir(figura).getpixel((folga, folga)) != (255, 255, 255)
    assert _abrir(figura).getpixel((folga - 1, folga - 1)) == (255, 255, 255)


def test_tamanho_de_tela_e_metade_do_arquivo_e_vai_no_png():
    figura = bc.figura_final(_quadro((100, 100, 1500, 700)), "t", "l")
    assert _abrir(figura).size == (2 * figura.largura_px, 2 * figura.altura_px)
    assert fg.largura_do_png(figura.png) == figura.largura_px


@pytest.mark.parametrize("caixa", [(10, 10, 1000, 300), (10, 10, 1001, 300), (10, 10, 1000, 301)])
def test_tamanho_de_tela_e_exato_com_medida_impar(caixa):
    figura = bc.figura_final(_quadro(caixa), "t", "l")
    assert _abrir(figura).size == (2 * figura.largura_px, 2 * figura.altura_px)


def test_desenho_alto_ganha_branco_dos_lados_para_nao_passar_da_folha_no_word():
    figura = bc.figura_final(_quadro((900, 100, 1000, 900)), "t", "l")
    assert figura.largura_px / figura.altura_px == pytest.approx(bc.PROPORCAO_MINIMA, abs=0.01)
    imagem = _abrir(figura)
    meio = imagem.width // 2
    assert imagem.getpixel((meio, imagem.height // 2)) != (255, 255, 255)
    assert imagem.getpixel((5, imagem.height // 2)) == (255, 255, 255)


def test_quadro_em_branco_nao_quebra():
    figura = bc.figura_final(Image.new("RGB", (400, 200), "#ffffff"), "t", "l")
    assert (figura.largura_px, figura.altura_px) == (200, 100)


def test_so_a_conta_nao_gasta_tempo_com_a_figura():
    with bc.so_a_conta():
        figura = bc.figura_final(_quadro((1, 1, 50, 50)), "t", "l")
    assert figura.png == b"" and figura.largura_px == 0


@pytest.mark.parametrize(
    ("view_box", "largura"),
    [
        ("0 0 1200 300", fg.LARGURA_VETORIAL),  # deitada: vale a largura
        ("0 0 600 600", fg.ALTURA_VETORIAL),  # quadrada: vale a altura
        ("0 0 300 900", round(fg.ALTURA_VETORIAL / 3)),  # em pé
        ("-20 -30 1000 200", fg.LARGURA_VETORIAL),  # origem negativa, a das cotas
    ],
)
def test_figura_vetorial_nao_passa_da_altura_de_uma_tela(view_box, largura):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}"></svg>'
    assert fg.largura_do_svg(svg) == largura


def test_svg_sem_view_box_fica_na_largura_padrao():
    assert fg.largura_do_svg("<svg></svg>") == fg.LARGURA_VETORIAL


def _pagina_de_figuras():
    import streamlit as st

    from components.figuras import mostrar_figura
    from core import beam_charts as bc
    from core import desenho_tensoes as dt

    pronta = dt.figura_dos_elementos(80.0, -20.0, 35.0)
    assert isinstance(pronta, bc.ImagemDiagrama)
    mostrar_figura(pronta)
    mostrar_figura(pronta.png, "legenda própria")
    mostrar_figura('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"></svg>')
    coluna, _ = st.columns(2)
    mostrar_figura(pronta, alvo=coluna)
    mostrar_figura(b"")  # figura dispensada: não mostra nada


def test_mostrar_figura_aceita_cada_tipo_de_figura():
    pagina = AppTest.from_function(_pagina_de_figuras, default_timeout=30).run()
    assert not pagina.exception


def test_nenhuma_imagem_passa_por_fora_de_mostrar_figura():
    """Só as miniaturas do painel acompanham a coluna, e a placa do esqueleto tem tamanho próprio."""
    achadas = []
    for pasta in ("app_pages", "components"):
        for arquivo in (RAIZ / pasta).glob("*.py"):
            if arquivo.name != "figuras.py":
                achadas += [arquivo.name] * arquivo.read_text(encoding="utf-8").count(".image(")
    assert sorted(achadas) == ["assistente_cargas_ui.py", "esforcos_modelo.py"]


@pytest.mark.parametrize(
    "caso_id", ["viga_reacoes", "trelica_plana", "barra_axial", "portico_simples"]
)
def test_figuras_do_assistente_cabem_na_coluna_de_resposta(caso_id):
    """A coluna tem cerca de 450 px numa janela comum: acima de 640, o texto cairia a menos de 9 px."""
    resultado = calcular_caso(cat.CASOS[caso_id], None)
    assert resultado.figuras
    for figura in resultado.figuras:
        assert fg.largura_do_png(figura.png) <= 640


def test_elementos_do_mohr_cabem_na_pagina_sem_encolher():
    assert dt.figura_dos_elementos(80.0, -20.0, 35.0, 25.0).largura_px <= 1000


def test_diagrama_preenche_a_area_nos_saltos(monkeypatch):
    """``order`` na área faz de cada ponto uma marca sem preenchimento."""
    pego = []
    monkeypatch.setattr(ui.st, "altair_chart", lambda grafico, **_: pego.append(grafico))
    pontos = ((0.0, 10.0, ""), (1.0, 10.0, ""), (1.0, -5.0, ""), (2.0, -5.0, ""))
    ui._grafico(Grafico(titulo="V", rotulo_x="x", rotulo_y="V", pontos=pontos, area=True))
    camadas = pego[0].to_dict()["layer"]
    area = next(c for c in camadas if str(c["mark"].get("type")) == "area")
    linha = next(c for c in camadas if str(c["mark"].get("type")) == "line")
    assert "order" not in area["encoding"]
    assert "order" in linha["encoding"]
    assert area["encoding"]["y"]["stack"] is None


def test_vigas_e_eixos_nao_ordena_a_area():
    texto = (RAIZ / "app_pages/vigas_eixos.py").read_text(encoding="utf-8")
    assert "alt.Order" not in texto
    assert "stack=None" in texto


def test_resultado_de_viga_sem_normal_nao_mostra_zero_negativo():
    pagina = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180)
    pagina.run()
    pagina.switch_page("app_pages/vigas_eixos.py").run()
    next(b for b in pagina.button if b.label == "Calcular diagramas").click().run()
    assert not pagina.exception
    valores = {m.label: m.value for m in pagina.metric}
    assert valores["Normal máximo |N|"] == "0.00 kN"
    assert not valores["Momento máximo |M|"].startswith("-")


def test_goodman_e_s_n_ajustam_so_a_largura():
    texto = (RAIZ / "app_pages/analise_fadiga.py").read_text(encoding="utf-8")
    assert texto.count("autosize=SO_NA_LARGURA") == 2
