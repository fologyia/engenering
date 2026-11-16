"""Cantoneiras de abas iguais da tabela de bolso Gerdau no catálogo de perfis."""

import math

from core import column_buckling as cb
from core import section_catalog as catalogo


def _cantoneiras():
    return {n: p for n, p in catalogo.listar_perfis().items() if n.startswith("L ")}


def test_cinquenta_bitolas_da_tabela():
    ls = _cantoneiras()
    assert len(ls) == 50
    assert {'L 1/2" x 1/8"', 'L 2" x 1/4"', 'L 8" x 3/4"'} <= set(ls)


def test_valores_da_tabela_gerdau():
    p = _cantoneiras()['L 2" x 1/4"']
    assert p.area_mm2 == 606.0 and p.ix_mm4 == p.iy_mm4 == 146_000.0
    assert p.massa_kg_m == 4.74 and p.centroide_x_mm == p.centroide_y_mm == 15.0
    assert abs(math.sqrt(p.i_min_mm4 / p.area_mm2) - 9.9) < 0.01  # r_z mín. = 0,99 cm


def test_coerencia_interna_de_todas():
    for nome, p in _cantoneiras().items():
        assert math.sqrt(p.ix_mm4 / p.area_mm2) > math.sqrt(p.i_min_mm4 / p.area_mm2), nome
        assert 1.5 < p.zx_mm3 / (p.ix_mm4 / (p.altura_mm - p.centroide_y_mm)) < 2.0, nome
        assert abs(p.massa_kg_m - p.area_mm2 * 7.85e-3) < 0.12 * p.massa_kg_m, nome


def test_flambagem_usa_inercia_minima_e_abas():
    p = _cantoneiras()['L 2" x 1/4"']
    s = cb.secao_de_perfil(p)
    assert s.Ix == p.i_min_mm4
    assert [e["grupo"] for e in s.elementos] == [3, 3]
