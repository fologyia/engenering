"""O desenho da seção na Flambagem de colunas (pedido de 30/10/2026: "imagem [...] para representar
o perfil também com angulação, faça bem feita a imagem").

A forma sai da própria seção (ou do catálogo, no T e no C enrijecido) com G na origem; o desenho
mostra eixos, G, centro de cisalhamento, elipse de giração e cotas, e gira só o desenho.
"""

from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from core import column_buckling as cb
from core import desenho_da_secao as ds
from core import section_catalog as sc


def _primeiro(familia: str) -> str:
    return next(n for n in sc.listar_perfis() if sc.obter_perfil(n).familia.startswith(familia))


def _area(poligono) -> float:
    return abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(poligono, poligono[1:] + poligono[:1], strict=True)
        )
        / 2
    )


SECOES = {
    "W": lambda: cb.secao_de_perfil(sc.obter_perfil(_primeiro("W"))),
    "U do catálogo": lambda: cb.secao_de_perfil(sc.obter_perfil(_primeiro("U"))),
    "T do catálogo": lambda: cb.secao_de_perfil(sc.obter_perfil(_primeiro("T "))),
    "C enrijecido": lambda: cb.secao_de_perfil(sc.obter_perfil(_primeiro("C enrijecido"))),
    "tubo circular": lambda: cb.secao_por_dimensoes("tubo_circular", D=60.0, t=4.0),
    "tubo retangular": lambda: cb.secao_por_dimensoes("tubo_retangular", B=100.0, H=150.0, t=5.0),
    "barra circular": lambda: cb.secao_por_dimensoes("circular_macica", d=50.0),
    "barra retangular": lambda: cb.secao_por_dimensoes("retangular_macica", b=50.0, h=100.0),
    "I por dimensões": lambda: cb.secao_por_dimensoes(
        "I", soldado=True, d=300.0, bf=150.0, tf=12.5, tw=8.0
    ),
    "U por dimensões": lambda: cb.secao_por_dimensoes("U", d=152.4, bf=48.8, tf=8.71, tw=5.08),
    "área e raios": lambda: cb.secao_direta(1000.0, 15.0, 10.0),
}


@pytest.mark.parametrize("nome", list(SECOES))
def test_toda_secao_tem_desenho(nome):
    secao = SECOES[nome]()
    desenho = ds.figura_da_secao(secao)
    imagem = Image.open(io.BytesIO(desenho.png))
    assert imagem.format == "PNG" and imagem.size == (desenho.largura_px, desenho.altura_px)
    assert secao.nome in desenho.titulo
    forma = ds.forma_da_secao(secao)
    assert forma.conhecida == (nome != "área e raios")


@pytest.mark.parametrize(
    ("nome", "tipo"),
    [
        ("I por dimensões", "I"),
        ("U por dimensões", "U"),
        ("tubo retangular", "tubo_ret"),
        ("barra retangular", "ret_macica"),
    ],
)
def test_forma_tem_a_area_da_secao_e_g_na_origem(nome, tipo):
    secao = SECOES[nome]()
    assert secao.tipo == tipo
    forma = ds.forma_da_secao(secao)
    area = sum(_area(list(c)) for c in forma.cheios) - sum(_area(list(c)) for c in forma.vazados)
    assert area == pytest.approx(secao.A, rel=1e-6)
    # G na origem: o centro geométrico do desenho é o da seção
    momento_x = sum(_area(list(c)) * ds._centroide(c)[0] for c in forma.cheios)
    momento_y = sum(_area(list(c)) * ds._centroide(c)[1] for c in forma.cheios)
    for c in forma.vazados:
        momento_x -= _area(list(c)) * ds._centroide(c)[0]
        momento_y -= _area(list(c)) * ds._centroide(c)[1]
    assert (momento_x / area, momento_y / area) == pytest.approx((0.0, 0.0), abs=1e-6)


def test_tubo_circular_tem_a_area_da_secao():
    secao = SECOES["tubo circular"]()
    (externo, interno), *_ = ds.forma_da_secao(secao).aneis
    assert math.pi * (externo**2 - interno**2) == pytest.approx(secao.A, rel=1e-6)


@pytest.mark.parametrize("nome", ["U por dimensões", "U do catálogo", "C enrijecido"])
def test_centro_de_cisalhamento_do_u_fica_por_fora_da_alma(nome):
    secao = SECOES[nome]()
    forma = ds.forma_da_secao(secao)
    dorso = min(x for c in forma.cheios for x, _ in c)
    assert dorso < 0 < secao.x0 and -secao.x0 < dorso  # o CC passa do dorso da alma


def test_t_do_catalogo_com_a_mesa_em_cima():
    secao = SECOES["T do catálogo"]()
    forma = ds.forma_da_secao(secao)
    (contorno,) = forma.cheios
    topo = max(y for _, y in contorno)
    base = min(y for _, y in contorno)
    largura_no_topo = max(x for x, y in contorno if abs(y - topo) < 1e-9)
    largura_na_base = max(x for x, y in contorno if abs(y - base) < 1e-9)
    assert largura_no_topo > largura_na_base  # a mesa em cima, o talão embaixo
    assert secao.y0 > 0  # e o CC acima de G, no encontro da mesa com o talão


@pytest.mark.parametrize("nome", ["W", "U por dimensões", "área e raios"])
def test_girar_muda_so_o_desenho(nome):
    secao = SECOES[nome]()
    parado = ds.figura_da_secao(secao)
    girado = ds.figura_da_secao(secao, giro_graus=45)
    assert girado.png != parado.png
    assert (girado.largura_px, girado.altura_px) == (parado.largura_px, parado.altura_px)
    assert ds.figura_da_secao(secao, giro_graus=360).png == parado.png
    assert "girado 45° no sentido anti-horário" in girado.legenda
    assert "girado" not in parado.legenda


@pytest.mark.parametrize("giro", [-150, -90, 30, 135, 180])
@pytest.mark.parametrize("nome", list(SECOES))
def test_desenho_girado_sai_em_qualquer_angulo(nome, giro):
    assert ds.figura_da_secao(SECOES[nome](), giro_graus=giro).png.startswith(b"\x89PNG")


def test_numero_pt_br_e_potencia_de_dez():
    assert ds._n(300.0) == "300" and ds._n(12.5) == "12,5"
    assert ds._potencia(22.91e6, "mm⁴") == "22,91 × 10⁶ mm⁴"
    assert ds._potencia(910_000.0, "mm⁴") == "910 × 10³ mm⁴"
    assert ds._potencia(493.3, "mm⁴") == "493,3 mm⁴"
