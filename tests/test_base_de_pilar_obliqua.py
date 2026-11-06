"""Placa de base com momento nos dois eixos (pedido de 31/10/2026: "confira se [...] considera
todos os momentos relevantes"): o M_Sd,y, que antes só deixava a base em ALERTA, entra pelo método
geral em duas direções — zona comprimida além de uma linha neutra inclinada e chumbadores com força
proporcional à distância a ela.
"""

from __future__ import annotations

import io
import math
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from core import base_de_pilar as bp
from core.desenho_placa_base import figura_da_base

PADRAO = bp.EntradaBase()  # W 250 x 32,7, tipo 1, 4 × Ø 1", N 300 kN
C3_6 = replace(PADRAO, n_chumbadores=6, m_sd_kNm=100, t_placa_mm=38)
MISTA = replace(
    PADRAO, perfil="W 360 x 51,0", tipo=bp.TIPO_INTERNOS_E_EXTERNOS, n_chumbadores=8,
    m_sd_kNm=120, t_placa_mm=50,
)  # fmt: skip

CASOS = {
    "C2": replace(PADRAO, m_sd_kNm=10, m_sd_y_kNm=5),
    "C3": replace(C3_6, m_sd_y_kNm=30),
    "C3 só M_y": replace(C3_6, m_sd_kNm=0, m_sd_y_kNm=40),
    "T2": replace(PADRAO, n_sd_kN=-100, m_sd_kNm=5, m_sd_y_kNm=3),
    "T3": replace(PADRAO, n_sd_kN=-80, m_sd_kNm=60, m_sd_y_kNm=20),
    "flexão pura": replace(PADRAO, n_sd_kN=0, m_sd_kNm=30, m_sd_y_kNm=10),
    "tipo 2": replace(PADRAO, perfil="W 360 x 51,0", tipo=bp.TIPO_2, m_sd_kNm=5, m_sd_y_kNm=5),
    "rotulada": replace(PADRAO, tipo=bp.TIPO_ROTULADA, n_chumbadores=2, m_sd_kNm=30, m_sd_y_kNm=10),
    "mista": replace(MISTA, m_sd_y_kNm=40),
}


def _equilibrio(r: bp.ResultadoBase) -> tuple[float, float, float]:
    """(N, M, M_y) que a pressão na zona e os chumbadores devolvem, em kN e kN·m."""
    g = r.geometria
    if r.zona_comprimida:
        area, cx, cy = bp._area_e_centro(list(r.zona_comprimida))
        sigma = r.sigma_c_sd if r.sigma_c_sd is not None else r.sigma_c_rd
    else:
        area = cx = cy = sigma = 0.0
    c = sigma * area
    f = r.forcas_nos_chumbadores
    return (
        (c - sum(f)) / 1e3,
        (c * cx - sum(fi * x for fi, (x, _) in zip(f, g.posicoes, strict=True))) / 1e6,
        (c * cy - sum(fi * y for fi, (_, y) in zip(f, g.posicoes, strict=True))) / 1e6,
    )


@pytest.mark.parametrize("nome", list(CASOS))
def test_pressao_e_chumbadores_equilibram_n_m_e_m_y(nome):
    e = CASOS[nome]
    r = bp.calcular(e)
    assert r.caso[0] == ("T" if e.n_sd_kN < 0 else "C")
    assert _equilibrio(r) == pytest.approx((e.n_sd_kN, e.m_sd_kNm, e.m_sd_y_kNm), abs=1e-3)
    assert all(f >= 0 for f in r.forcas_nos_chumbadores)


def test_sem_tracao_a_zona_tem_o_centro_na_resultante():
    r = bp.calcular(CASOS["C2"])
    assert r.caso == "C2" and max(r.forcas_nos_chumbadores) == 0
    area, cx, cy = bp._area_e_centro(list(r.zona_comprimida))
    assert (cx, cy) == pytest.approx((10e6 / 300e3, 5e6 / 300e3), abs=1e-3)  # e_x, e_y
    assert r.sigma_c_sd == pytest.approx(300e3 / area)
    assert _linha(r, "Concreto: pressão").aproveitamento == pytest.approx(
        r.sigma_c_sd / r.sigma_c_rd
    )


def test_sem_contato_conta_de_mao():
    r = bp.calcular(CASOS["T2"])
    g = r.geometria
    sx = sum(x * x for x, _ in g.posicoes)
    sy = sum(y * y for _, y in g.posicoes)
    esperado = [100e3 / 4 - 5e6 * x / sx - 3e6 * y / sy for x, y in g.posicoes]
    assert r.caso == "T2" and not r.zona_comprimida
    assert r.forcas_nos_chumbadores == pytest.approx(esperado)


def test_chumbadores_tracionados_seguem_a_placa_rigida():
    # forças num plano F = α + β·x + γ·y (proporcionais à distância à linha neutra)
    r = bp.calcular(CASOS["C3"])
    pontos = [
        (x, y, f)
        for (x, y), f in zip(r.geometria.posicoes, r.forcas_nos_chumbadores, strict=True)
        if f > 1.0
    ]
    assert len(pontos) >= 4
    a = np.array([[1.0, x, y] for x, y, _ in pontos])
    coef, *_ = np.linalg.lstsq(a, np.array([f for *_, f in pontos]), rcond=None)
    assert a @ coef == pytest.approx([f for *_, f in pontos], rel=1e-6)


@pytest.mark.parametrize("base", [C3_6, replace(PADRAO, m_sd_kNm=20), replace(MISTA)])
def test_com_m_y_tendendo_a_zero_volta_a_conta_de_uma_direcao(base):
    sem = bp.calcular(base)
    quase = bp.calcular(replace(base, m_sd_y_kNm=1e-4))
    assert quase.caso == sem.caso
    assert quase.t_p_min == pytest.approx(sem.t_p_min, rel=1e-3)
    assert quase.forcas_nos_chumbadores == pytest.approx(sem.forcas_nos_chumbadores, abs=5.0)  # N
    assert quase.v_rd == pytest.approx(sem.v_rd, rel=1e-3)


@pytest.mark.parametrize("m_y", [39.0, 40.0, 45.0, 60.0])
def test_so_m_y_logo_acima_do_c2_acha_o_equilibrio(m_y):
    """Só M_y: a raiz fica na ponta da busca (θ = 90°); com M_y = 39, F_t de menos de 1 kN."""
    e = replace(C3_6, m_sd_kNm=0, m_sd_y_kNm=m_y)
    r = bp.calcular(e)
    assert r.caso == "C3"
    assert _linha(r, "Equilíbrio possível").status == "OK"
    assert _equilibrio(r) == pytest.approx((300.0, 0.0, m_y), abs=1e-3)


def test_so_m_y_e_simetrico_em_x():
    # com M_y = 60 a linha neutra passa acima dos chumbadores de cima (com 40, logo abaixo deles)
    r = bp.calcular(replace(CASOS["C3 só M_y"], m_sd_y_kNm=60))
    por_posicao = dict(zip(r.geometria.posicoes, r.forcas_nos_chumbadores, strict=True))
    for (x, y), f in por_posicao.items():
        assert por_posicao[(-x, y)] == pytest.approx(f, abs=1e-3)
    assert max(f for (_, y), f in por_posicao.items() if y > 0) == 0  # o lado de cima comprime
    assert por_posicao[(179.0, -100.0)] > por_posicao[(179.0, 0.0)] > 0  # proporcional à distância


def test_m_y_aumenta_a_tracao_e_a_espessura():
    sem, com = bp.calcular(C3_6), bp.calcular(CASOS["C3"])
    assert com.f_t_sd > sem.f_t_sd
    assert com.t_p_min >= sem.t_p_min


def test_sem_equilibrio_reprova_e_tipo_2_continua_sem_c3():
    rotulada = bp.calcular(replace(CASOS["rotulada"], m_sd_kNm=90, m_sd_y_kNm=40))
    linha = _linha(rotulada, "Equilíbrio possível com a placa (flexão oblíqua)")
    assert linha.status == "NÃO OK" and rotulada.status == "NÃO OK"
    tipo2 = bp.calcular(replace(CASOS["tipo 2"], m_sd_kNm=60, m_sd_y_kNm=20))
    assert tipo2.caso == "C3" and _linha(tipo2, "Caso previsto").status == "NÃO OK"


def test_registro_texto_e_mais_leve_falam_da_flexao_obliqua():
    r = bp.calcular(CASOS["C3"])
    registro = bp.registro_base(r)
    assert "Flexão oblíqua" in registro["metodo"]
    assert any("dois eixos" in p for p in registro["premissas"])
    assert "M_Sd,y = 30,0 kN·m" in bp.destaque(r)
    leve = bp.base_mais_leve(CASOS["C3"])
    assert leve is not None and leve.zona_comprimida and leve.status != "NÃO OK"


def test_desenho_hachura_a_zona_inclinada_e_marca_a_linha_neutra():
    r = bp.calcular(CASOS["C3"])
    desenho = figura_da_base(r)
    assert "flexão oblíqua" in desenho.legenda
    imagem = np.asarray(Image.open(io.BytesIO(desenho.png)).convert("RGB")).astype(int)
    planta = imagem[220:1040, 72:932]  # no dobro de pixels e sem os 4 px aparados à esquerda
    hachura = np.all(np.abs(planta - [0x60, 0xA5, 0xFA]) < 40, axis=-1)  # #60a5fa
    pressao = np.all(np.abs(planta - [0x1D, 0x4E, 0xD8]) < 40, axis=-1)  # #1d4ed8 (LN)
    assert hachura.sum() > 300 and pressao.sum() > 60
    # a hachura fica no canto comprimido (x > 0 e y > 0: direita e em cima na planta)
    linhas, colunas = np.nonzero(hachura)
    assert colunas.mean() > planta.shape[1] / 2 and linhas.mean() < planta.shape[0] / 2


def _linha(r: bp.ResultadoBase, inicio: str):
    achadas = [v for v in r.verificacoes if v.nome.startswith(inicio)]
    assert len(achadas) == 1, (inicio, [v.nome for v in r.verificacoes])
    return achadas[0]


def test_linha_neutra_e_um_lado_da_zona_que_corta_a_placa():
    from core.desenho_placa_base import _linha_neutra

    r = bp.calcular(CASOS["C3"])
    a, b = _linha_neutra(r.geometria, r.zona_comprimida)
    g = r.geometria
    for ponto in (a, b):  # as duas pontas ficam na borda da placa
        assert math.isclose(abs(ponto[0]), g.lx / 2, abs_tol=1e-6) or math.isclose(
            abs(ponto[1]), g.ly / 2, abs_tol=1e-6
        )
