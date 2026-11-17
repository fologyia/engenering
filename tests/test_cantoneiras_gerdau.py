"""Cantoneiras de abas iguais da tabela de bolso Gerdau no catálogo de perfis."""

import math
import re

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


# ------------------------------------------------------------- uma fonte só (core/cantoneiras.py)
import pytest  # noqa: E402

from core import cantoneiras as ct  # noqa: E402
from core import esforcos_modelo as em  # noqa: E402
from core import lista_de_material as lm  # noqa: E402
from core import perfis_compostos as pc  # noqa: E402


def test_catalogo_de_cantoneiras_usa_os_valores_gerdau():
    assert len(ct.CATALOGO_CANTONEIRAS) == 50
    assert {c.fonte for c in ct.CATALOGO_CANTONEIRAS.values()} == {ct.FONTE_GERDAU}
    perfis = catalogo.listar_perfis()
    for nome, c in ct.CATALOGO_CANTONEIRAS.items():
        p = perfis[re.sub(r"(\d) (\d+/)", r"\1.\2", nome).replace(" × ", " x ")]
        assert (c.area_mm2, c.i_x_mm4, c.massa_kg_m) == (p.area_mm2, p.ix_mm4, p.massa_kg_m), nome
        assert c.i_z_mm4 == pytest.approx(p.i_min_mm4), nome
        assert c.i_w_mm4 + c.i_z_mm4 == pytest.approx(2 * c.i_x_mm4), nome


def test_nomes_antigos_continuam_abrindo():
    # Projetos gravados com os nomes da série antiga.
    for nome in ct.SERIE_POLEGADAS:
        assert f'L {nome[0]}" × {nome[1]}"' in ct.CATALOGO_CANTONEIRAS
    assert ct.obter_cantoneira('L 2.1/2" x 1/4"') is ct.obter_cantoneira('L 2 1/2" × 1/4"')
    with pytest.raises(ValueError):
        ct.obter_cantoneira('L 9" × 1/4"')


def test_2l_do_catalogo_tem_o_rz_do_fabricante():
    c = ct.obter_cantoneira('L 3" × 1/4"')
    peca = pc.cantoneira_do_catalogo(c)
    assert peca.r_min_mm == pytest.approx(c.r_z_mm)
    assert peca.area_mm2 == c.area_mm2


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Viga-23(Ângulo l L2.5X2.5X0.25(1)[5])", 'L 2 1/2" × 1/4"'),
        ('Viga-2(Perfil l de abas iguais L 3"X0,25"(1)[7])', 'L 3" × 1/4"'),
        ('Viga-6(L 3" x 3" x 3/8"(1)[2])', 'L 3" × 3/8"'),
        ('L 2.1/2" x 1/4"', 'L 2 1/2" × 1/4"'),  # jeito da Gerdau
        ('L 2-1/2" x 1/4"', 'L 2 1/2" × 1/4"'),
        ('CANTONEIRA 2" X 3/16"', 'L 2" × 3/16"'),
        ('Cant. 1 1/4" x 1/8"', 'L 1 1/4" × 1/8"'),
        ("L 2 x 1/4", 'L 2" × 1/4"'),
        ("l 2x2x1/4", 'L 2" × 1/4"'),
        ("Angle L4X4X1/2", 'L 4" × 1/2"'),
        ("L 3 x 3 x 0.25 in", 'L 3" × 1/4"'),
        ("L 50,8 x 6,35", 'L 2" × 1/4"'),  # milímetros
        ("L 76,2x76,2x6,3", 'L 3" × 1/4"'),
        ('L 2" x 6,35', 'L 2" × 1/4"'),  # aba em polegada, espessura em mm
        ("L 101,6 x 12,7", 'L 4" × 1/2"'),
        ('L 3"X0,27"', None),  # espessura que não é bitola
        ("L 76x76x6", None),  # 6 mm não é 1/4": mais fina, contra a segurança
        ("L 3x2x1/4", None),  # abas desiguais
        ('L 9" x 1/2"', None),
        ("W 200 x 35,9", None),
        ("Viga-1", None),
    ],
)
def test_cantoneira_pelo_nome(nome, esperado):
    assert ct.cantoneira_pelo_nome(nome) == esperado


def test_perfil_do_nome_e_lista_de_material_usam_o_mesmo_leitor():
    assert em.perfil_do_nome('Viga-9(L 2.1/2" x 5/16")') == 'L 2 1/2" × 5/16"'
    assert em.perfil_do_nome("L 76x76x6") is None
    assert lm.perfil_conhecido("Viga-3(L 50,8 x 6,35)").massa_kg_m == 4.74
    # Abas desiguais em polegadas: fora do catálogo, mas com a massa pelas medidas.
    desigual = lm.perfil_conhecido("L 3x2x1/4")
    assert desigual is not None
    assert desigual.massa_kg_m == pytest.approx(6.35 * (76.2 + 50.8 - 6.35) * 7.85e-3, rel=0.01)


def test_explica_por_que_nao_reconheceu():
    assert "abas desiguais" in ct.por_que_nao_reconheceu("L 3x2x1/4")
    motivo = ct.por_que_nao_reconheceu("L 76x76x6")
    assert 'L 3" × 1/4"' in motivo and "não troquei" in motivo
    assert ct.por_que_nao_reconheceu('L 3" x 1/4"') == ""
    assert ct.por_que_nao_reconheceu("W 200 x 35,9") == ""
