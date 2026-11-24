"""Placa de base com pilar de perfil U (o método da 6.7 estendido: o U como meia I de mesa 2·b_f)."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from core import base_de_pilar as bp
from core import base_de_pilar_soldas as bs
from core import section_catalog as sc

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/placa_de_base.py"
U8 = 'U 8" x 17,10'
BASE = bp.EntradaBase(
    perfil=U8, chumbador='3/4"', n_sd_kN=100.0, m_sd_kNm=0.0, v_sd_kN=5.0, t_placa_mm=19.0,
    solda_mesas_por_dentro=False,
)  # fmt: skip


def _medidas(nome: str) -> tuple[float, float, float, float]:
    p = sc.obter_perfil(nome)
    return p.altura_mm, p.largura_mm, p.espessura_alma_mm, p.espessura_mesa_mm


def test_os_u_do_catalogo_entram_na_lista_e_so_na_tipo_1():
    assert U8 in bp.perfis_u() and U8 in bp.perfis_do_pilar()
    assert not set(bp.perfis_u()) & set(bp.perfis_i())
    assert bp.forma_do_perfil(U8) == bp.FORMA_U and bp.tipos_do_perfil(U8) == (bp.TIPO_1,)
    assert bp.forma_do_perfil("W 250 x 32,7") == bp.FORMA_I
    for tipo in (bp.TIPO_2, bp.TIPO_ROTULADA, bp.TIPO_INTERNOS_E_EXTERNOS):
        with pytest.raises(bp.BaseInvalida, match="tipo 1"):
            bp.calcular(replace(BASE, tipo=tipo, n_chumbadores=bp.QUANTIDADES[tipo][0]))


def test_centroide_do_u_a_mao():
    d, b_f, t_w, t_f = _medidas(U8)
    alma, mesas = d * t_w, 2 * (b_f - t_w) * t_f
    esperado = (alma * t_w / 2 + mesas * (t_w + (b_f - t_w) / 2)) / (alma + mesas)
    assert bp.centroide_do_u(d, b_f, t_w, t_f) == pytest.approx(esperado)
    assert 0 < esperado < b_f / 2  # o centro fica mais perto do dorso


def test_balancos_do_u_como_meia_i_de_mesa_dupla():
    d, b_f, t_w, t_f = _medidas(U8)
    x_barra = bp.centroide_do_u(d, b_f, t_w, t_f)
    g = bp.geometria(BASE)
    assert g.e_u and g.y_dorso == pytest.approx(-x_barra)
    assert g.m == pytest.approx((g.lx - 0.95 * d) / 2)
    assert g.n == pytest.approx(max(g.ly / 2 - x_barra, g.ly / 2 - (0.80 * b_f - x_barra)))
    assert g.n0 == pytest.approx(math.sqrt(d * 2 * b_f) / 4)
    assert g.engaste_y == pytest.approx((-x_barra, 0.80 * b_f - x_barra))
    assert g.faixa_y == pytest.approx((-x_barra, b_f - x_barra))
    # M_y < 0: o U espelhado, com as mesmas contas
    h = bp.geometria(replace(BASE, m_sd_y_kNm=-1.0))
    assert h.y_dorso == pytest.approx(x_barra) and h.n == pytest.approx(g.n)
    assert h.engaste_y == pytest.approx((-(0.80 * b_f - x_barra), x_barra))


def test_compressao_pura_pela_formula_com_o_maior_balanco():
    r = bp.calcular(BASE)
    g = r.geometria
    assert r.caso == "C1"
    fy_d = 250.0 / 1.10
    assert r.sigma_c_sd is not None
    x_fator = 4 * g.d * 2 * g.b_f / (g.d + 2 * g.b_f) ** 2
    x_val = x_fator * 100e3 / (g.lx * g.ly * r.sigma_c_rd)
    lam = min(2 * math.sqrt(x_val) / (1 + math.sqrt(1 - x_val)), 1.0)
    l_max = max(g.m, g.n, lam * g.n0)
    assert r.t_p_min == pytest.approx(l_max * math.sqrt(2 * r.sigma_c_sd / fy_d), rel=1e-3)
    nomes = {v.nome: v for v in r.verificacoes}
    assert nomes["Pilar U: método da 6.7 estendido"].status == "INFO"
    assert nomes["Largura da placa ℓy: 12,5 mm além do U de cada lado"].status == "OK"
    assert "Largura da placa ℓy ≥ b_f + 25 mm" not in nomes
    assert any("meia I" in a for a in r.avisos)


@pytest.mark.parametrize(
    ("n", "m", "m_y"), [(100, 5, 0), (20, 15, 0), (-20, 0, 0), (-20, 3, 0), (50, 3, 1.5)]
)
def test_todos_os_casos_rodam_com_o_u(n, m, m_y):
    r = bp.calcular(replace(BASE, n_sd_kN=n, m_sd_kNm=m, m_sd_y_kNm=m_y))
    assert r.caso in ("C1", "C2", "C3", "T1", "T2", "T3")
    assert r.t_p_min > 0


def test_momento_y_espelhado_da_o_mesmo_resultado():
    a = bp.calcular(replace(BASE, n_sd_kN=50, m_sd_kNm=3, m_sd_y_kNm=1.5))
    b = bp.calcular(replace(BASE, n_sd_kN=50, m_sd_kNm=3, m_sd_y_kNm=-1.5))
    assert a.t_p_min == pytest.approx(b.t_p_min)
    assert [v.aproveitamento for v in a.verificacoes] == pytest.approx(
        [v.aproveitamento for v in b.verificacoes], nan_ok=True
    )


@pytest.mark.parametrize("y_dorso", [-16.4, 16.4])
def test_solda_do_u_equilibra_os_esforcos_no_centro_do_perfil(y_dorso):
    d, b_f, t_w, t_f = _medidas(U8)
    trechos = bs.contorno_do_pilar(
        d, b_f, t_w, t_f, mesas_por_dentro=True, alma=True, y_dorso=y_dorso
    )
    nomes = {t.nome for t in trechos}
    assert nomes == {
        "dorso da alma",
        "mesa, face externa",
        "mesa, face interna",
        "alma, face interna",
    }
    p = bs.propriedades(trechos)
    # dorso e face interna da alma pesam mais: o centro do grupo fica do lado do dorso
    assert p.y_c != 0 and math.copysign(1, p.y_c) == math.copysign(1, y_dorso)
    axial, momento, momento_y = 100e3, 5e6, 2e6
    soma = soma_x = soma_y = 0.0
    for t in trechos:
        u = (np.arange(400) + 0.5) / 400
        x, y = t.x1 + u * (t.x2 - t.x1), t.y1 + u * (t.y2 - t.y1)
        f = (
            -axial / p.comprimento
            - momento * x / p.i_x
            - (momento_y - axial * p.y_c) * (y - p.y_c) / p.i_y
        )
        ds = t.comprimento / 400
        soma += float(np.sum(f) * ds)
        soma_x += float(np.sum(f * x) * ds)
        soma_y += float(np.sum(f * y) * ds)
    assert soma == pytest.approx(-axial, rel=1e-5)
    assert soma_x == pytest.approx(-momento, rel=1e-5)
    assert soma_y == pytest.approx(-momento_y, rel=1e-5)


def test_solda_do_u_compressao_pura_e_uniforme():
    d, b_f, t_w, t_f = _medidas(U8)
    c = bp.sd.coeficientes(bp.sd.COMBINACAO_NORMAL)
    trechos = bs.contorno_do_pilar(
        d, b_f, t_w, t_f, mesas_por_dentro=False, alma=False, y_dorso=-16.4
    )
    p = bs.propriedades(trechos)
    r = bs.solda_do_pilar(
        d=d, b_f=b_f, t_w=t_w, t_f=t_f, t_placa=19.0, aco_pilar=(345.0, 450.0), axial=50e3,
        momento=0.0, momento_y=0.0, cortante=0.0, perna_informada=5.0, eletrodo="E70",
        mesas_por_dentro=False, alma=False, contato=False, c=c, y_dorso=-16.4,
    )  # fmt: skip
    # N no centro do U, fora do centro do grupo: a força varia, e o pior ponto passa de N/L
    assert r.linhas[0].solicitante > 50e3 / p.comprimento / 1e3
    assert "y_c" in r.linhas[0].formula and "dorso da alma" in r.linhas[0].formula


def test_solda_da_i_nao_mudou():
    trechos = bs.contorno_do_pilar(258.0, 146.0, 6.1, 9.1, mesas_por_dentro=True, alma=True)
    assert bs.propriedades(trechos).y_c == 0.0


def test_desenhos_do_u():
    from core import desenho_placa_base as dpb
    from core import desenho_placa_base_contas as dpc

    r = bp.calcular(replace(BASE, n_sd_kN=20, m_sd_kNm=8, m_sd_y_kNm=0.5))
    assert dpb.figura_da_base(r).png
    for lista in dpc.figuras_das_contas(r).values():
        assert all(f.png for f in lista)
    contorno = bp.contorno_do_perfil(r.geometria)
    ys = [y for _, y in contorno]
    assert min(ys) == pytest.approx(r.geometria.faixa_y[0])
    assert max(ys) == pytest.approx(r.geometria.faixa_y[1])


def test_pagina_com_pilar_u(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    t.session_state["pb_tipo"] = bp.TIPO_2
    t.session_state["pb_perfil"] = U8
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    radio = next(r for r in t.radio if r.label == "Disposição dos chumbadores")
    assert list(radio.options) == [bp.TIPOS[bp.TIPO_1]]
    assert t.session_state["pb_tipo"] == bp.TIPO_1
    assert any("Pilar U" in c.value for c in t.caption)
