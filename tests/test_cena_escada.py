"""A escada em 3D — detalhada ou casca translúcida — na página do degrau, no PDF e no memorial, e os
degraus dos lances que vêm como chapa no esqueleto; mais a cena gravada (ida e volta)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import cena_escada as cesc
from core import degrau_escada as de
from core import degrau_registro as reg
from core import escada_lances as el
from core.degrau_relatorio import gerar_pdf_degrau
from core.record_charts import imagens_gravadas


@pytest.fixture(scope="module")
def resultado() -> de.ResultadoEscada:
    return de.calcular_escada(de.EntradaDegrau(H_mm=3600))


def escadas(r: de.ResultadoEscada) -> dict[str, el.EscadaComPatamares]:
    return {
        "reta": el.montar_escada(r),
        "em U": el.montar_escada(
            r, (el.PatamarInformado(1800, 1200, None, True),), lances_em_u=True
        ),
    }


@pytest.mark.parametrize("tipo", ["reta", "em U"])
def test_escada_detalhada_tem_degraus_longarinas_e_apoios(resultado, tipo):
    esc = escadas(resultado)[tipo]
    cena = cesc.cena_da_escada(esc.H_mm, esc.lances, esc.patamares, modo=cesc.MODO_DETALHADO)
    degraus = [b for b in cena.barras if b.grupo == "degrau"]
    assert len(degraus) == sum(ln.n_espelhos - 1 for ln in esc.lances)
    assert len([b for b in cena.barras if b.grupo == "longarina"]) == 2 * len(esc.lances)
    assert len(cena.apoios) == 4  # duas longarinas no pé e duas no topo
    assert any(b.grupo == "gc" for b in cena.barras) and not any(
        p.grupo == "lance" for p in cena.paineis
    )
    d = c3.projetar(cena)
    assert not d.avisos and d.poligonos > 200


@pytest.mark.parametrize("tipo", ["reta", "em U"])
def test_casca_translucida_tem_so_o_volume(resultado, tipo):
    esc = escadas(resultado)[tipo]
    cena = cesc.cena_da_escada(esc.H_mm, esc.lances, esc.patamares, modo=cesc.MODO_CASCA)
    assert not [b for b in cena.barras if b.grupo in ("degrau", "longarina", "gc")]
    lances = [p for p in cena.paineis if p.grupo == "lance"]
    assert len(lances) == len(esc.lances) and all(p.opacidade < 0.5 for p in lances)
    assert all(p.opacidade < 0.5 for p in cena.paineis if p.grupo == "gc")


def test_escada_em_u_poe_o_lance_de_cima_ao_lado(resultado):
    esc = escadas(resultado)["em U"]
    cena = cesc.cena_da_escada(esc.H_mm, esc.lances, esc.patamares)
    ys = {
        lance: {
            round(b.inicio[1], 3) for b in cena.barras if b.nome.startswith(f"Longarina L{lance}")
        }
        for lance in (1, 2)
    }
    assert min(ys[2]) >= max(ys[1])  # o segundo lance fica ao lado do primeiro


def test_registro_e_memorial_desenham_a_escada_no_modo_escolhido(resultado):
    esc = escadas(resultado)["reta"]
    dados = cesc.para_o_registro(
        esc,
        modo=cesc.MODO_CASCA,
        secao_da_longarina=cm.secao_do_perfil('U 8" x 17,10'),
        altura_do_guarda_corpo_m=1.2,
    )
    registro = reg.registro_degrau(resultado, escada=esc, escada_3d=dados)
    assert registro["resultados"]["escada_3d"]["modo"] == cesc.MODO_CASCA
    figuras = imagens_gravadas(registro["resultados"])
    tres_d = [f for f, _ in figuras if "3D" in f.legenda]
    assert len(tres_d) == 1 and "casca translúcida" in tres_d[0].legenda
    assert Image.open(io.BytesIO(tres_d[0].png)).format == "PNG"
    # o PDF do degrau leva a mesma figura
    sem = gerar_pdf_degrau(resultado, escada=esc)
    com = gerar_pdf_degrau(resultado, escada=esc, escada_3d=dados)
    assert len(com) > len(sem)


def test_lance_que_vem_como_chapa_ganha_degraus():
    # chapa inclinada: 2,0 m de queda em 2,6 m de corrida, 0,8 m de largura
    pontos = ((0.0, 0.0, 2.0), (2.6, 0.0, 0.0), (2.6, 0.8, 0.0), (0.0, 0.8, 2.0))
    degraus = cm._degraus_do_lance("Lance", pontos)
    assert len(degraus) == round(2.0 / 0.18) - 1
    assert all(abs(b.inicio[1] - 0.02) < 1e-6 and abs(b.fim[1] - 0.78) < 1e-6 for b in degraus)
    alturas = sorted(b.inicio[2] for b in degraus)
    assert alturas[0] > 0 and alturas[-1] < 2.0


# ------------------------------------------------------------------ cena gravada
def test_cena_vai_e_volta_do_registro_e_lixo_nao_derruba():
    cena = c3.Cena(
        barras=(
            c3.BarraCena(
                "P",
                (0, 0, 0),
                (0, 0, 3),
                c3.Secao(c3.FORMA_I, 0.2, 0.1, 0.006, 0.01),
                (1.0, 0.0, 0.0),
                "#3f6fb5",
                "P1",
                True,
                "Pilar",
            ),
        ),  # fmt: skip
        paineis=(c3.PainelCena("piso", ((0, 0, 3), (1, 0, 3), (1, 1, 3)), "#ccc", 0.3, "chapa"),),
        setas=(c3.SetaCena((0, 0, 3), (0, 0, -1), "1 kN", larga=True, comprimento_relativo=0.3),),
        distribuidas=(c3.CargaDistribuidaCena((0, 0, 3), (1, 0, 3), (0, 0, -2), "2 kN/m"),),
        apoios=(c3.ApoioCena((0, 0, 0), c3.APOIO_ENGASTE),),
        textos=(c3.TextoCena((0, 0, 1), "texto"),),
        titulo="T",
        legenda=(("#000", "x"),),
        escala=c3.EscalaDeCor(0, 1, "kN/m", "carga"),
    )
    volta = c3.cena_de_dicionario(c3.cena_para_dicionario(cena))
    assert volta == cena
    assert c3.cena_de_dicionario(None) == c3.Cena()
    lixo = {"barras": [["x"], ["P", [0, 0], [1, 1, 1], None, None, "#000", "", False, ""]],
            "paineis": "texto", "setas": [[None] * 8], "escala": [1, 2]}  # fmt: skip
    assert c3.cena_de_dicionario(lixo).barras == ()


def test_vista_registrada_vai_ao_memorial():
    cena = c3.Cena(barras=(c3.BarraCena("P", (0, 0, 0), (0, 0, 3), c3.Secao()),), titulo="Modelo")
    registro = cm.registro_da_vista(cena, azimute=-125, elevacao=27, perfil_real=True,
                                    descricao="vista isométrica")  # fmt: skip
    assert registro["modulo_id"] == cm.MODULO_ID
    figuras = imagens_gravadas(registro["resultados"])
    assert len(figuras) == 1 and figuras[0][0].legenda.startswith("Modelo em 3D")
