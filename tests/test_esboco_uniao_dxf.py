"""Marco 3: o que entra no esboço vira contorno limpo — modelos, perfis, seções antigas e DXF.

A prancheta de chapas foi aposentada: tudo o que ela fazia entra agora no esboço. As chapas que se
encostam viram um contorno só (``core.esboco_uniao``), e o DXF entra pelo ``ezdxf``
(``core.esboco_dxf``). Cada teste confere a área exata e que as regiões do esboço aceitam a forma.
"""

from __future__ import annotations

import io
import math
from unittest import mock

import ezdxf
import numpy as np
import pytest

from core import esboco as eb
from core import esboco_dxf as ed
from core import esboco_regioes as er
from core import esboco_uniao as eu
from core import secao_desenhada as sd
from core import section_catalog as catalogo


def _area(esboco: eb.Esboco) -> float:
    regioes = er.Regioes(eb.Sistema(esboco))
    assert regioes.ok, [p.mensagem for p in regioes.problemas]
    return float(regioes.avaliar(regioes.q_base[None, :], np.ones(1, bool)).exatas.area[0])


# ---------------------------------------------------------------------------
# União das formas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modelo", [m.id for m in sd.MODELOS])
def test_todo_modelo_antigo_vira_esboco_valido_com_a_mesma_area(modelo):
    partes = sd.partes_do_modelo(
        modelo, {m.chave: m.padrao for m in sd.MODELOS_POR_ID[modelo].medidas}
    )
    esboco = eb.esboco_das_partes(partes)
    # A conta antiga faz o círculo como polígono: lá a área é um pouco menor que a exata.
    assert _area(esboco) == pytest.approx(sd.analisar(partes).prop.area, rel=1e-3)


def test_i_de_tres_chapas_vira_um_contorno_de_doze_retas_e_continua_i():
    partes = sd.partes_do_modelo("i", {"d": 300, "bf": 150, "tf": 12, "tw": 8})
    esboco = eb.esboco_das_partes(partes)
    assert len(esboco.curvas) == 12 and all(c.tipo == eb.LINHA for c in esboco.curvas)
    assert len(esboco.restricoes) == 12  # cada reta deitada ou em pé
    regioes = er.Regioes(eb.Sistema(esboco))
    assert sd.reconhecer(regioes.partes(regioes.q_base)).nome == "I soldado"


def test_furo_que_corta_a_borda_tira_um_entalhe():
    chapa = eu.Forma(pontos=((0, 0), (100, 0), (100, 40), (0, 40)))
    entalhe = eu.Forma(centro=(100, 20), raio=10, furo=True)  # meio círculo para dentro
    furo_solto = eu.Forma(centro=(30, 20), raio=5, furo=True)
    fora = eu.Forma(centro=(300, 20), raio=5, furo=True)  # furo sem aço embaixo: não entra
    esboco = eu.esboco_unido([chapa, entalhe, furo_solto, fora])
    assert _area(esboco) == pytest.approx(4000 - math.pi * 100 / 2 - math.pi * 25, rel=1e-9)
    assert sum(c.tipo == eb.ARCO for c in esboco.curvas) == 1
    assert sum(c.tipo == eb.CIRCULO for c in esboco.curvas) == 1


def test_formas_encostadas_e_cruzadas_somam_sem_contar_duas_vezes():
    a = eu.Forma(pontos=((0, 0), (50, 0), (50, 20), (0, 20)))
    b = eu.Forma(pontos=((50, 0), (100, 0), (100, 20), (50, 20)))  # encosta pela borda toda
    c = eu.Forma(pontos=((40, 10), (60, 10), (60, 60), (40, 60)))  # cruza as duas
    esboco = eu.esboco_unido([a, b, c])
    assert _area(esboco) == pytest.approx(100 * 20 + 20 * 40)
    # a borda comum de a e b sumiu, e as retas em fila viraram uma só
    assert len(esboco.curvas) == 8


def test_anexar_da_nomes_novos_e_guarda_o_que_ja_existia():
    base = eb.esboco_das_partes([sd.Parte(sd.RET, 0, 0, 40, 20)]).como_dicionario()
    base["cotas"] = [
        {
            "id": "d1",
            "tipo": "distancia",
            "curvas": ["c1"],
            "pontos": ["p1", "p2"],
            "expressao": "40",
        }
    ]
    outro = eb.esboco_das_partes([sd.Parte(sd.CIRC, 100, 0, 10, 10)]).como_dicionario()
    junto = eu.anexar(base, outro)
    assert [c["id"] for c in junto["curvas"]] == ["c1", "c2", "c3", "c4", "c5"]
    assert junto["cotas"] == base["cotas"]
    assert len({*junto["pontos"]}) == len(junto["pontos"])
    lido = eb.esboco_de_dicionario(junto)
    assert _area(lido) == pytest.approx(800 + math.pi * 25)


# ---------------------------------------------------------------------------
# DXF
# ---------------------------------------------------------------------------


def _dxf(montar, unidade: int = 4) -> bytes:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = unidade
    montar(doc.modelspace(), doc)
    texto = io.StringIO()
    doc.write(texto)
    return texto.getvalue().encode("utf-8")


def _chapa_com_cantos_e_rasgo(msp, doc):
    b = math.tan(math.radians(90) / 4)  # bulge de um quarto de volta
    pontos = [(0, 0, 0), (10, 0, 0), (10, 3, b), (9, 4, 0), (1, 4, b), (0, 3, 0)]
    msp.add_lwpolyline(pontos, format="xyb", close=True, dxfattribs={"layer": "PECA"})
    msp.add_circle((5, 2), 0.5, dxfattribs={"layer": "PECA"})
    msp.add_line((2, 1), (3, 1), dxfattribs={"layer": "PECA"})
    msp.add_line((3, 2), (2, 2), dxfattribs={"layer": "PECA"})
    msp.add_arc((3, 1.5), 0.5, -90, 90, dxfattribs={"layer": "PECA"})
    msp.add_arc((2, 1.5), 0.5, 90, 270, dxfattribs={"layer": "PECA"})
    msp.add_text("PECA 1", dxfattribs={"layer": "TEXTO"})
    msp.add_line((-5, -5), (20, -5), dxfattribs={"layer": "MOLDURA"})


def test_dxf_com_polilinha_curva_arcos_circulo_e_unidade_em_cm():
    dados = _dxf(_chapa_com_cantos_e_rasgo, unidade=5)
    assert ed.camadas(dados) == ("PECA", "MOLDURA")  # a camada só de texto não aparece
    leitura = ed.ler_dxf(dados, usar=["PECA"])
    assert leitura.fator_mm == 10.0 and leitura.unidade == "cm"
    assert leitura.ignoradas == {"TEXT": 1}
    cantos = 2 * (100 - math.pi * 100 / 4)
    rasgo = 10 * 10 + math.pi * 25
    assert _area(leitura.esboco) == pytest.approx(4000 - cantos - math.pi * 25 - rasgo, rel=1e-9)


def test_dxf_com_bloco_explodido_e_origem_no_meio():
    def montar(msp, doc):
        bloco = doc.blocks.new("FURO")
        bloco.add_circle((0, 0), 3)
        msp.add_lwpolyline([(100, 100), (160, 100), (160, 130), (100, 130)], close=True)
        msp.add_blockref("FURO", (115, 115))
        msp.add_blockref("FURO", (145, 115))

    leitura = ed.ler_dxf(_dxf(montar))
    assert _area(leitura.esboco) == pytest.approx(60 * 30 - 2 * math.pi * 9, rel=1e-9)
    xs = [x for x, _ in leitura.esboco.pontos.values()]
    assert min(xs) == pytest.approx(-30) and max(xs) == pytest.approx(30)  # o meio foi para (0, 0)
    sem_mudar = ed.ler_dxf(_dxf(montar), levar_para_origem=False)
    assert max(x for x, _ in sem_mudar.esboco.pontos.values()) == pytest.approx(160)


def test_dxf_com_elipse_avisa_que_virou_retas():
    def montar(msp, doc):
        msp.add_ellipse((0, 0), major_axis=(20, 0), ratio=0.5)

    leitura = ed.ler_dxf(_dxf(montar))
    assert leitura.avisos and "retas" in leitura.avisos[0]
    assert _area(leitura.esboco) == pytest.approx(math.pi * 20 * 10, rel=1e-3)


def test_dwg_lixo_e_dxf_grande_demais_dizem_o_motivo():
    with pytest.raises(ed.ErroDeDxf, match="DXF"):
        ed.ler_dxf(b"AC1032" + b"\x00" * 64)
    with pytest.raises(ed.ErroDeDxf, match="Nada no DXF"):
        ed.ler_dxf(_dxf(lambda msp, doc: msp.add_text("só texto")))

    def muitas(msp, doc):
        for i in range(ed.MAX_CURVAS + 1):
            msp.add_line((i, 0), (i, 1))

    with pytest.raises(ed.ErroDeDxf, match="camadas"):
        ed.ler_dxf(_dxf(muitas))


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


class _Arquivo:
    def __init__(self, nome: str, dados: bytes) -> None:
        self.name = nome
        self._dados = dados

    def getvalue(self) -> bytes:
        return self._dados


def _estado() -> dict:
    from components import desenhar_secao_ui as ui

    estado: dict = {}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._iniciar()
    return estado


def test_pagina_importa_o_dxf_com_as_camadas_escolhidas():
    from components import desenhar_secao_ui as ui

    estado = _estado()
    estado[ui.DXF_ARQUIVO] = _Arquivo("peca.dxf", _dxf(_chapa_com_cantos_e_rasgo, unidade=5))
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_escolher_dxf()
        assert estado[ui.DXF_CAMADAS] == ["PECA", "MOLDURA"]
        estado[ui.DXF_USAR] = ["PECA"]
        ui._abrir_dxf()
    assert not estado[ui.DXF_ERRO]
    assert estado[ui.PARTES_ESBOCO] and not estado[ui.PROBLEMAS]
    assert "peca.dxf" in estado[ui.AVISO] and "cm" in estado[ui.AVISO]
    assert estado[ui.VERSAO_ESBOCO] >= 1_000_000  # a prancheta aceita o desenho novo


def test_pagina_recusa_dwg_com_o_caminho_para_o_dxf():
    from components import desenhar_secao_ui as ui

    estado = _estado()
    estado[ui.DXF_ARQUIVO] = _Arquivo("peca.dwg", b"AC1027" + b"\x00" * 64)
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_escolher_dxf()
    assert "Salvar como" in estado[ui.DXF_ERRO] and estado[ui.DXF_CAMADAS] == []


def test_secao_antiga_abre_como_esboco_de_um_contorno(tmp_path):
    from components import desenhar_secao_ui as ui

    partes = sd.partes_do_modelo("t", {"d": 200, "bf": 150, "tf": 12, "tw": 8})
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(
            sd.perfil_da_secao("T antigo", sd.analisar(partes)),
            desenho=tuple(p.como_dicionario() for p in partes),
        )
        estado = _estado()
        estado["secao_abrir"] = "T antigo"
        with mock.patch.object(ui.st, "session_state", estado):
            ui._abrir_salva()
    assert "prancheta antiga" in estado[ui.AVISO]
    assert not estado[ui.PROBLEMAS]
    area = sd.analisar(sd.partes_de_lista(estado[ui.PARTES_ESBOCO])).prop.area
    assert area == pytest.approx(150 * 12 + 188 * 8)


def test_perfil_do_catalogo_entra_encostado_e_pede_unir():
    from components import desenhar_secao_ui as ui

    estado = _estado()
    nome = next(n for n in sorted(catalogo.listar_perfis()) if n.startswith("W"))
    with mock.patch.object(ui.st, "session_state", estado):
        estado["secao_add_perfil"] = nome
        ui._por_perfil()  # desenho vazio: o perfil entra sozinho
        assert estado[ui.PARTES_ESBOCO] and not estado[ui.PROBLEMAS]
        estado[ui.MODELO] = "Chapa"
        ui._aplicar_modelo()
        estado["secao_add_lado"] = sd.LADOS[0]
        ui._por_perfil()  # agora encosta na chapa: dois contornos que se tocam
    assert "Unir" in estado[ui.AVISO]
    assert any("Unir" in p["mensagem"] for p in estado[ui.PROBLEMAS])
