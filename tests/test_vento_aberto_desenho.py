"""Desenhos do vento em estruturas abertas: a força de cada pórtico em cada nível, a força por
nível (cortante e momento na base) e as figuras que vão ao memorial. O desenho tem de mostrar
exatamente os números do cálculo."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest

from components.figuras_estrutura import svg_vento_elevacao
from core import cena_3d as c3
from core import vento_aberto_desenho as vad
from core import vento_aberto_registro as var
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb
from core import vento_por_barras_registro as vbr
from core import vento_por_nivel as vpn
from core.record_charts import imagens_do_registro

VENTO = va.ParametrosVento(v0_m_s=35.0, categoria="II")


def plataforma(**troca) -> va.GeometriaAberta:
    dados = dict(
        comprimento_x_m=12.0,
        largura_y_m=6.0,
        cotas_m=(3.0, 6.0),
        vaos_x=2,
        vaos_y=1,
        largura_diagonal_x_m=0.076,
        largura_diagonal_y_m=0.076,
        equipamentos=(va.Equipamento("Tanque", 2, va.FORMA_CILINDRO, 2.0, 2.0, 3.0),),
    )
    dados.update(troca)
    return va.GeometriaAberta(**dados)


def _norma(v) -> float:
    return math.sqrt(sum(c * c for c in v))


# ------------------------------------------------------------------ pórticos
@pytest.mark.parametrize("direcao", ["X", "Y"])
@pytest.mark.parametrize("cotas", [(4.0,), (3.0, 6.0), (3.5, 7.0, 10.5, 14.0)])
def test_cena_dos_porticos_tem_uma_seta_por_portico_e_nivel_com_a_forca_do_calculo(direcao, cotas):
    tanque = va.Equipamento("Tanque", len(cotas), va.FORMA_CILINDRO, 2.0, 2.0, 3.0)
    g = plataforma(cotas_m=cotas, equipamentos=(tanque,))
    d = va.calcular_vento_aberto(g, VENTO).direcao(direcao)
    cena = vad.cena_dos_porticos(g, d)
    vento = [s for s in cena.setas if s.larga]
    forcas = [s for s in cena.setas if not s.larga and s.rotulo]
    base = [s for s in cena.setas if not s.larga and not s.rotulo]
    assert len(vento) == 1
    assert len(forcas) == len(d.planos) * len(d.niveis)
    # As setas somam a força dos pórticos (estrutura + guarda-corpo) e a base vai à fundação.
    equipamentos = sum(f for nivel in d.equipamentos_por_nivel for _, f, _ in nivel)
    assert sum(_norma(s.vetor) for s in forcas) == pytest.approx(
        d.total_kN - d.forca_na_base_kN - equipamentos
    )
    assert sum(_norma(s.vetor) for s in base) == pytest.approx(d.forca_na_base_kN)
    # Todas sopram do pórtico de barlavento (P1) para os de trás.
    sentido = vento[0].vetor
    p1 = next(p.coordenada_m for p in d.planos if p.posicao == 1)
    for p in d.planos:
        if p.posicao > 1:
            eixo = 0 if direcao == "X" else 1
            assert (p.coordenada_m - p1) * sentido[eixo] > 0
    for s in forcas:
        assert sum(a * b for a, b in zip(s.vetor, sentido, strict=True)) > 0
        assert f"{_norma(s.vetor):.1f}".replace(".", ",") in s.rotulo
    # O total de cada nível e o φ, C_a e η de cada pórtico estão escritos.
    textos = " ".join(t.texto for t in cena.textos)
    for nivel in d.niveis:
        assert f"{nivel.total_kN:.1f}".replace(".", ",") + " kN" in textos
    for p in d.planos:
        assert f"P{p.posicao} · φ" in textos
    assert d.classe in cena.titulo


def test_elevacao_dos_porticos_e_um_svg_valido_e_sem_triedro_do_solidworks():
    g = plataforma()
    d = va.calcular_vento_aberto(g, VENTO).x
    svg = svg_vento_elevacao(g, d)
    raiz = ET.fromstring(svg)
    assert raiz.tag.endswith("svg")
    assert "eixos do SolidWorks" not in svg
    assert "P1" in svg and "P3" in svg


# ------------------------------------------------------------------ força por nível
def test_forca_por_nivel_da_grade_fecha_com_o_calculo():
    r = va.calcular_vento_aberto(plataforma(), VENTO)
    colunas = vad.forcas_da_grade(r)
    assert [c.rotulo.split(" (")[0] for c in colunas] == ["Vento em X", "Vento em Y"]
    for c, d in zip(colunas, (r.x, r.y), strict=True):
        assert c.total_kN == pytest.approx(d.total_kN)
        assert c.momento_na_base_kNm == pytest.approx(d.momento_na_base_kNm)
        assert c.cortantes_kN == pytest.approx(d.cortantes_dos_andares_kN)
    desenho = vad.desenho_das_forcas_por_nivel(colunas)
    textos = " ".join(i.texto for i in desenho.itens if isinstance(i, c3.Etiqueta2D))
    for c in colunas:
        for v in c.cortantes_kN:
            assert f"V = {v:.1f}".replace(".", ",") in textos
        assert f"{c.momento_na_base_kNm:.1f}".replace(".", ",") + " kN·m" in textos
    # As setas crescem com a força.
    setas = [i for i in desenho.itens if isinstance(i, c3.Seta2D) and i.cor == vad.COR_VENTO]
    comprimentos = [abs(s.b[0] - s.a[0]) for s in setas]
    forcas = [f for c in colunas for f in c.forcas_kN]
    assert sorted(range(len(forcas)), key=forcas.__getitem__) == sorted(
        range(len(comprimentos)), key=comprimentos.__getitem__
    )


def _duas_colunas() -> vpb.ResultadoPorBarras:
    alma_x, alma_z = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    barras = [
        vpb.BarraAoVento("P1", (0, 0, 0), (0, 0, 4), 0.21, 0.134, alma_x),
        vpb.BarraAoVento("P2", (0, 1.8, 0), (0, 1.8, 4), 0.21, 0.134, alma_x),
        vpb.BarraAoVento("V1", (-2.25, 0, 4), (2.25, 0, 4), 0.203, 0.057, alma_z),
        vpb.BarraAoVento("V2", (-2.25, 1.8, 4), (2.25, 1.8, 4), 0.203, 0.057, alma_z),
        vpb.BarraAoVento("V3", (-2.25, 0, 4), (-2.25, 1.8, 4), 0.203, 0.057, alma_z),
        vpb.BarraAoVento("V4", (2.25, 0, 4), (2.25, 1.8, 4), 0.203, 0.057, alma_z),
        vpb.BarraAoVento("D1", (0, 0.2, 0), (0, 1.6, 3.8), 0.064, 0.064),
    ]
    return vpb.calcular(
        vpb.EntradaPorBarras(barras=tuple(barras), direcoes=vpb.DIRECOES_COM_DIAGONAIS)
    )


def test_forca_por_nivel_do_barra_a_barra_conserva_o_tombamento():
    """Metade de cada barra em cada ponta (e a alavanca nas pontas no meio de outra barra) não muda
    o momento na base: Σ F·z dos níveis é o tombamento barra a barra."""
    r = _duas_colunas()
    vn = vpn.vento_por_nivel(r)
    colunas = vad.forcas_do_barra_a_barra(vn)
    assert [c.rotulo.split(" ")[0] for c in colunas] in (["W0", "W90"], ["W180", "W90"],
                                                         ["W0", "W270"], ["W180", "W270"])  # fmt: skip
    for c in colunas:
        angulo = int(c.rotulo.split(" ")[0][1:])
        d = r.direcao(angulo)
        assert c.total_kN == pytest.approx(d.total_kN)
        assert c.momento_na_base_kNm == pytest.approx(d.momento_tombamento_kNm, rel=1e-6)


def test_registro_dos_niveis_ida_e_volta_e_dado_estragado():
    r = va.calcular_vento_aberto(plataforma(), VENTO)
    colunas = vad.forcas_da_grade(r)
    gravado = vad.niveis_para_o_registro(colunas, titulo="T", subtitulo="S")
    lidas, titulo, subtitulo = vad.niveis_do_registro(gravado)
    assert (titulo, subtitulo) == ("T", "S")
    assert [c.rotulo for c in lidas] == [c.rotulo for c in colunas]
    assert lidas[0].forcas_kN == pytest.approx(colunas[0].forcas_kN, abs=1e-4)
    estragado = {"colunas": [{"rotulo": "x"}, {"cotas_m": [1, 2], "forcas_kN": [1]},
                             {"cotas_m": ["nan"], "forcas_kN": [1]}, "lixo",
                             {"cotas_m": [3.0], "forcas_kN": [2.0], "base_kN": None}]}  # fmt: skip
    lidas, _, _ = vad.niveis_do_registro(estragado)
    assert len(lidas) == 1 and lidas[0].base_kN == 0.0
    assert vad.niveis_do_registro({}) == ([], "", "")


# ------------------------------------------------------------------ memorial
def test_memorial_da_grade_tem_os_porticos_e_a_forca_por_nivel():
    r = va.calcular_vento_aberto(plataforma(), VENTO)
    registro = var.registro_vento_aberto(r)
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == ""
    titulos = [i["titulo"] for i in imagens]
    assert sum("força em cada pórtico" in t for t in titulos) == 2
    assert sum(t == "Força do vento em cada nível" for t in titulos) == 1
    assert all(i["png"][:8] == b"\x89PNG\r\n\x1a\n" for i in imagens)


def test_memorial_do_barra_a_barra_tem_as_direcoes_principais_e_a_forca_por_nivel():
    r = _duas_colunas()
    direcoes = vbr.direcoes_das_figuras(r)
    assert len(direcoes) <= 3 and r.governante.angulo in direcoes
    assert {a for a in direcoes if a % 90 == 0} & {0, 180} and {a for a in direcoes} & {90, 270}
    registro = vbr.registro_vento_por_barras(r, eixo_vertical="Z")
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == ""
    titulos = [i["titulo"] for i in imagens]
    assert sum("carga em cada barra" in t for t in titulos) == len(direcoes)
    assert sum(t == "Força do vento em cada nível" for t in titulos) == 1


def test_barra_a_barra_sem_niveis_nao_desenha_a_forca_por_nivel():
    """Um poste sozinho não tem viga deitada: não há nível, e o memorial não inventa a figura."""
    poste = vpb.BarraAoVento("P", (0, 0, 0), (0, 0, 6), 0.2, 0.2)
    r = vpb.calcular(vpb.EntradaPorBarras(barras=(poste,)))
    assert vad.forcas_do_barra_a_barra(vpn.vento_por_nivel(r)) == []
    imagens, _ = imagens_do_registro(vbr.registro_vento_por_barras(r), {})
    assert not any(i["titulo"] == "Força do vento em cada nível" for i in imagens)
