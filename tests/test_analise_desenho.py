"""Análise sobre o desenho: marcas num desenho, cada uma com uma análise do Montador.

Os blocos novos do Montador (pino ao corte e chapa com furo) têm de dar os mesmos números do Cálculo
de peças. Cada análise do Montador tem de funcionar como marca. O desenho de fundo entra por imagem,
PDF, DXF ou print colado, e o memorial sai com o desenho e as marcas.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from unittest import mock

import ezdxf
import pytest
from streamlit.testing.v1 import AppTest

from core import analise_desenho as ad
from core import elementos_estatica as ees
from core import elementos_pinos as ep
from core import montador as mt
from core import montador_modelos as mm

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _pino_no_montador(valores: dict, planos: int) -> float:
    modelo = mm.POR_NOME["Pino: força máxima"]
    grafo = modelo.grafo()
    for no in grafo["nos"]:
        if no["tipo"] == "pino":
            no["opcoes"] = {"planos": str(planos)}
    montagem = mt.montar(mt.grafo_de_dados(grafo))
    resposta = mt.isolar(montagem, "F_lig", valores)
    assert resposta.valor is not None
    return resposta.valor


@pytest.mark.parametrize(
    ("planos", "pinos", "a", "b", "c"),
    [
        (1, 1, 12.0, 12.0, 0.0),
        (2, 1, 10.0, 16.0, 1.0),
        (3, 2, 8.0, 12.0, 2.0),
        (4, 1, 6.0, 10.0, 0.5),
    ],
)
def test_pino_do_montador_da_a_mesma_forca_do_calculo_de_pecas(planos, pinos, a, b, c):
    caso = {
        "forca_kN": 40.0,
        "pinos": pinos,
        "planos": planos,
        "elemento": ep.PINO_MACICO,
        "d_mm": 20.0,
        "d_i_mm": 0.0,
        "rosca": "M20",
        "a_mm": a,
        "b_mm": b,
        "c_mm": c,
        "w_mm": 60.0,
        "e_mm": 40.0,
        "sy_MPa": 350.0,
        "sy_chapa_MPa": 250.0,
        "fs": 2.0,
    }
    no_calculo = ep.calcular_pinos(caso).metricas[0].valor * 1000.0
    no_montador = _pino_no_montador(
        {
            "n_pi": float(pinos),
            "d_p": 20.0,
            "t_a": a,
            "t_b": b,
            "c_f": c,
            "w_c": 60.0,
            "e_c": 40.0,
            "S_y": 350.0,
            "S_y_c": 250.0,
            "n": 2.0,
        },
        planos,
    )
    assert no_montador == pytest.approx(no_calculo, rel=1e-6)


def test_chapa_com_furo_do_montador_da_a_mesma_capacidade():
    caso = {"b_mm": 80.0, "t_mm": 6.0, "d_mm": 22.0, "n": 2, "f_kN": 60.0, "sy_MPa": 250.0}
    caso |= {"sut_MPa": 400.0, "fs": 1.67}
    no_calculo = ees.calcular_chapa(caso).metricas[0].valor * 1000.0
    montagem = mt.montar(mt.grafo_de_dados(mm.POR_NOME["Chapa com furo: espessura mínima"].grafo()))
    valores = {
        "w_c": 80.0,
        "t_c": 6.0,
        "d_f": 22.0,
        "n_f": 2.0,
        "S_y": 250.0,
        "S_ut": 400.0,
        "n": 1.67,
    }
    resposta = mt.isolar(montagem, "F_lig", valores)
    assert resposta.valor == pytest.approx(no_calculo, rel=1e-9)


# ---------------------------------------------------------------------------
# Marcas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analise", [a for a in ad.ANALISES if a != ad.NOTA])
def test_toda_analise_do_montador_funciona_como_marca(analise):
    marca = ad.marca_nova("m1", 10.0, 20.0, analise)
    resultado = ad.calcular(marca)
    assert resultado.situacao == ad.LIMITE, resultado.texto
    # O valor já preenchido do alvo foi arredondado para o lado seguro: conferido, ele passa.
    marca.conferir = True
    conferida = ad.calcular(marca)
    assert conferida.situacao == ad.PASSOU, conferida.texto
    assert conferida.linhas and conferida.uso is not None and conferida.uso <= 1.0 + 1e-9


def test_marca_que_nao_passa_diz_quem_manda():
    marca = ad.marca_nova("m1", 0.0, 0.0, "Pino: força máxima")
    marca.conferir = True
    marca.valores["F_lig"] = 40e3  # o pino aguenta 25,2 kN
    resultado = ad.calcular(marca)
    assert resultado.situacao == ad.NAO_PASSOU
    assert resultado.manda == "Flexão com cortante"
    assert "não passou" in resultado.resumo and "25,2 kN" in resultado.texto


def test_marca_vai_e_volta_pelo_dicionario_e_troca_de_analise():
    marca = ad.marca_nova("m3", 1.5, -2.0, "Chapa com furo: espessura mínima")
    marca.nome = "Olhal"
    volta = ad.marca_de_dicionario(json.loads(json.dumps(marca.como_dicionario())))
    assert volta == marca
    trocada = ad.trocar_analise(volta, "Pino: diâmetro mínimo")
    assert (
        trocada.nome == "Olhal" and trocada.alvo == "d_p" and (trocada.x, trocada.y) == (1.5, -2.0)
    )


# ---------------------------------------------------------------------------
# Desenho de fundo
# ---------------------------------------------------------------------------


def _png(largura: int = 300, altura: int = 200) -> bytes:
    from PIL import Image

    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), "white").save(saida, format="PNG")
    return saida.getvalue()


def _pdf(paginas: int = 2) -> bytes:
    from reportlab.pdfgen import canvas

    saida = io.BytesIO()
    folha = canvas.Canvas(saida, pagesize=(300, 200))
    for i in range(paginas):
        folha.drawString(20, 100, f"Folha {i + 1}")
        folha.rect(10, 10, 280, 180)
        folha.showPage()
    folha.save()
    return saida.getvalue()


def _dxf() -> bytes:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm (o ezdxf cria em metros)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    msp.add_circle((30, 25), 8)
    msp.add_arc((70, 25), 10, 0, 180)
    texto = io.StringIO()
    doc.write(texto)
    return texto.getvalue().encode("utf-8")


def test_fundo_de_imagem_grande_e_reduzido():
    fundo = ad.fundo_do_arquivo("planta.png", _png(4000, 1000))
    assert fundo.tipo == "imagem" and fundo.imagem.startswith("data:image/jpeg;base64,")
    assert (fundo.largura, fundo.altura) == (ad.LADO_MAXIMO_DA_IMAGEM, 500)


def test_fundo_de_pdf_escolhe_a_pagina():
    dados = _pdf(3)
    assert ad.paginas_do_pdf(dados) == 3
    fundo = ad.fundo_do_arquivo("folhas.pdf", dados, pagina=2)
    assert fundo.tipo == "imagem" and "página 2" in fundo.nome
    assert fundo.largura == pytest.approx(300 * 150 / 72, abs=2)


def test_fundo_de_dxf_traz_as_curvas_em_mm():
    fundo = ad.fundo_do_arquivo("peca.dxf", _dxf())
    tipos = sorted(c["tipo"] for c in fundo.curvas)
    assert tipos == ["arco", "circulo", "linha", "linha", "linha", "linha"]
    assert any(c["tipo"] == "linha" and c["b"] == [100.0, 0.0] for c in fundo.curvas)


def test_print_colado_e_arquivo_ruim():
    url = "data:image/png;base64," + base64.b64encode(_png()).decode()
    assert ad.fundo_colado(url).largura == 300
    with pytest.raises(ad.ErroDeDesenho):
        ad.fundo_colado("data:text/plain;base64,b2k=")
    with pytest.raises(ad.ErroDeDesenho):
        ad.fundo_do_arquivo("foto.png", b"isto nao e imagem")
    with pytest.raises(ad.ErroDeDesenho):
        ad.fundo_do_arquivo("peca.dwg", b"AC1032" + b"\x00" * 32)


# ---------------------------------------------------------------------------
# Memorial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", ["imagem", "dxf", "nenhum"])
def test_word_traz_o_desenho_e_a_conta_de_cada_marca(tipo):
    from docx import Document

    fundo = {
        "imagem": ad.fundo_do_arquivo("planta.png", _png()).como_dicionario(),
        "dxf": ad.fundo_do_arquivo("peca.dxf", _dxf()).como_dicionario(),
        "nenhum": None,
    }[tipo]
    pino = ad.marca_nova("m1", 50.0, -25.0, "Pino: força máxima")
    pino.nome, pino.conferir = "Pino da articulação", True
    chapa = ad.marca_nova("m2", 20.0, -10.0, "Chapa com furo: espessura mínima")
    marcas = [pino, chapa]
    resultados = [ad.calcular(m) for m in marcas]
    bruto = ad.word_da_analise(fundo, marcas, resultados, escala=1.0)
    documento = Document(io.BytesIO(bruto))
    assert len(documento.inline_shapes) == 1
    titulos = [p.text for p in documento.paragraphs if p.style.name.startswith("Heading")]
    assert "1 · Pino da articulação" in titulos
    texto = " ".join(c.text for t in documento.tables for linha in t.rows for c in linha.cells)
    assert (
        "Flexão no pino" in texto and "Escoamento da seção bruta" not in texto
    )  # só o pino confere


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


def _estado() -> dict:
    from components import analise_desenho_ui as ui

    estado: dict = {}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._iniciar()
    return estado


def test_prancheta_cria_move_e_apaga_marcas():
    from components import analise_desenho_ui as ui

    estado = _estado()
    estado[ui.CHAVE] = mock.Mock(edicao={"versao": 1, "marcas": [{"id": "m1", "x": 5, "y": 6}]})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar()
        (marca,) = ui._marcas()
        assert (marca.id, marca.x, marca.analise) == ("m1", 5.0, ad.ANALISES[0])
        estado[ui.CHAVE] = mock.Mock(
            edicao={
                "versao": 2,
                "marcas": [{"id": "m1", "x": 7, "y": 6}, {"id": "m2", "x": 1, "y": 1}],
                "selecionada": "m2",
                "escala": 0.5,
            }
        )
        ui._ao_editar()
        assert [(m.id, m.x) for m in ui._marcas()] == [("m1", 7.0), ("m2", 1.0)]
        assert estado[ui.SELECIONADA] == "m2" and estado[ui.ESCALA] == 0.5
        estado[f"ad_m2_{ui._revisao('m2')}_analise"] = "Chapa com furo: espessura mínima"
        ui._ao_trocar_analise("m2")
        assert ui._marcas()[1].analise == "Chapa com furo: espessura mínima"
        assert estado[ui.REVISOES]["m2"] == 1
        ui._apagar("m1")
        assert [m.id for m in ui._marcas()] == ["m2"]


def test_abrir_no_montador_leva_o_modelo_e_os_numeros():
    from components import analise_desenho_ui as ui

    estado = _estado()
    marca = ad.marca_nova("m1", 0.0, 0.0, "Pino: força máxima")
    marca.conferir = True
    estado[ui.MARCAS] = [marca.como_dicionario()]
    with (
        mock.patch.object(ui.st, "session_state", estado),
        mock.patch.object(ui.montador_ui.st, "session_state", estado),
    ):
        ui._abrir_no_montador("m1")
    assert estado["mf_modelo_atual"] == "Pino: força máxima"
    assert estado["mf_alvo"] == "F_lig" and estado["mf_adotado"] == marca.valores["F_lig"]
    assert estado["mf_valores"]["d_p"] == 20.0 and "F_lig" not in estado["mf_valores"]
    assert estado["ad_ir_ao_montador"] is True


def test_pagina_abre_e_mostra_a_marca_com_o_resultado():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/analise_sobre_desenho.py")
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("Marcar" in i.value for i in at.info)
    marca = ad.marca_nova("m1", 0.0, 0.0, "Pino: força máxima")
    marca.conferir = True
    at.session_state["ad_marcas"] = [marca.como_dicionario()]
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("maior uso" in s.value for s in at.success)
    assert any("1 marca" in m.value for m in at.markdown)
