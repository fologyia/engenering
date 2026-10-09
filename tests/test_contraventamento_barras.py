"""Cantoneiras (seção idealizada) e verificação das diagonais pela NBR 8800:2024."""

from __future__ import annotations

import math

import pytest

from core import cantoneiras as ct
from core import contraventamento_barras as cb
from core import nbr8800
from core import perfis_gerdau_k as gk
from core import section_catalog as sc

POL = 25.4


# ------------------------------------------------------------------ cantoneiras
@pytest.mark.parametrize(
    ("nome", "area_in2", "x_in", "ix_in4", "rz_in"),
    [
        ('L 4" × 1/2"', 3.75, 1.18, 5.52, 0.776),  # AISC L4x4x1/2
        ('L 2" × 1/4"', 0.944, 0.586, 0.346, 0.391),  # AISC L2x2x1/4
        ('L 3" × 3/8"', 2.11, 0.884, 1.75, 0.581),  # AISC L3x3x3/8
    ],
)
def test_cantoneira_idealizada_fica_a_1_porcento_da_tabela_do_aisc(
    nome, area_in2, x_in, ix_in4, rz_in
):
    c = ct.obter_cantoneira(nome)
    assert c.area_mm2 / POL**2 == pytest.approx(area_in2, rel=0.01)
    assert c.x_barra_mm / POL == pytest.approx(x_in, rel=0.015)
    assert c.i_x_mm4 / POL**4 == pytest.approx(ix_in4, rel=0.015)
    assert c.r_z_mm / POL == pytest.approx(rz_in, rel=0.015)


def test_cantoneira_massa_do_catalogo_gerdau():
    assert ct.obter_cantoneira('L 2" × 1/4"').massa_kg_m == pytest.approx(4.74, abs=0.02)


def test_cantoneira_invalida():
    with pytest.raises(ValueError):
        ct.propriedades(50.0, 60.0)
    with pytest.raises(ValueError):
        ct.obter_cantoneira("L 9 × 9")


# ------------------------------------------------------------------ k do catálogo Gerdau
def test_k_do_catalogo_gerdau():
    assert gk.k_tabelado_mm("W 530 x 85,0", 16.5) == pytest.approx(28.5)
    assert gk.k_tabelado_mm("W 360 x 91,0(H)", 16.4) == pytest.approx(16.4 + (320 - 288) / 2)
    assert gk.k_tabelado_mm("Perfil inventado", 10.0) is None


def test_todo_w_e_hp_do_catalogo_tem_k():
    from core import steel_sections as ss

    faltam = [
        n
        for n, p in sc.listar_perfis().items()
        if ss.familia_do_perfil(p) in ("w", "hp")
        and gk.k_tabelado_mm(n, p.espessura_mesa_mm) is None
    ]
    assert not faltam, faltam


# ------------------------------------------------------------------ diagonais
def _linha(resultado, trecho):
    achadas = [v for v in resultado.verificacoes if trecho in v.nome]
    assert len(achadas) == 1, (trecho, [v.nome for v in resultado.verificacoes])
    return achadas[0]


CANTONEIRA = cb.Diagonal()  # L 2 1/2" × 1/4" A36, 3 × 5/8" A325 a 50 mm, borda 30 mm


def test_tracao_da_cantoneira_parafusada_confere_com_a_conta_a_mao():
    r = cb.verificar_diagonal(
        CANTONEIRA,
        "X",
        comprimento_mm=3606.0,
        comprimento_destravado_mm=1803.0,
        tracao_kN=100.0,
        compressao_kN=0.0,
    )
    c = ct.obter_cantoneira(CANTONEIRA.perfil)
    an = c.area_mm2 - (17.5 + 2.0) * c.t_mm  # furo-padrão de 5/8" = 17,5 mm (Tabela 14)
    coef = 1 - c.x_barra_mm / 100.0  # ℓ_c = 2 × 50 mm
    esperado = min(c.area_mm2 * 250 / 1.10, coef * an * 400 / 1.35) / 1e3
    linha = _linha(r, "tração da diagonal")
    assert linha.resistente == pytest.approx(esperado)
    assert linha.status == "OK"
    assert r.resistencia_tracao_kN == pytest.approx(esperado)


def test_ct_nao_fica_abaixo_de_ac_sobre_ag():
    curta = cb.Diagonal(n_parafusos=2, passo_mm=40.0, parafuso='1/2"')
    r = cb.verificar_diagonal(
        curta,
        "X",
        comprimento_mm=3000.0,
        comprimento_destravado_mm=3000.0,
        tracao_kN=10.0,
        compressao_kN=0.0,
    )
    c = ct.obter_cantoneira(curta.perfil)
    assert "C_t" in _linha(r, "tração").formula
    assert 1 - c.x_barra_mm / 40.0 > c.area_aba_mm2 / c.area_mm2  # aqui governa a fórmula
    longa = cb.Diagonal(perfil='L 6" × 3/4"', n_parafusos=2, passo_mm=40.0)
    r = cb.verificar_diagonal(
        longa,
        "X",
        comprimento_mm=3000.0,
        comprimento_destravado_mm=3000.0,
        tracao_kN=10.0,
        compressao_kN=0.0,
    )
    c = ct.obter_cantoneira(longa.perfil)
    assert f"{c.area_aba_mm2 / c.area_mm2:.3f}".replace(".", ",") in _linha(r, "tração").formula


def test_compressao_da_cantoneira_pelo_comprimento_equivalente_de_5_3_5_4():
    lb = 1803.0
    r = cb.verificar_diagonal(
        CANTONEIRA,
        "X",
        comprimento_mm=2 * lb,
        comprimento_destravado_mm=lb,
        tracao_kN=0.0,
        compressao_kN=10.0,
    )
    c = ct.obter_cantoneira(CANTONEIRA.perfil)
    razao = lb / c.r_x_mm
    leq = (72 * c.r_x_mm + 0.75 * lb) if razao <= 80 else (32 * c.r_x_mm + 1.25 * lb)
    ne = math.pi**2 * 200_000 * c.i_x_mm4 / leq**2
    q = nbr8800._qs_grupo(c.b_sobre_t, 250.0, 200_000.0, "3")
    lam = math.sqrt(q * c.area_mm2 * 250 / ne)
    esperado = nbr8800.fator_chi(lam) * q * c.area_mm2 * 250 / 1.10 / 1e3
    assert _linha(r, "compressão da diagonal").resistente == pytest.approx(esperado)
    assert _linha(r, "esbeltez equivalente").solicitante == pytest.approx(leq / c.r_x_mm)


def test_parafusos_rasgamento_e_espacamentos_da_cantoneira():
    r = cb.verificar_diagonal(
        CANTONEIRA,
        "X",
        comprimento_mm=3606.0,
        comprimento_destravado_mm=1803.0,
        tracao_kN=50.0,
        compressao_kN=0.0,
    )
    for trecho in ("parafusos da diagonal", "colapso por rasgamento", "espaçamento", "borda"):
        assert _linha(r, trecho).status == "OK", trecho
    apertado = cb.Diagonal(passo_mm=30.0, borda_mm=15.0)
    r = cb.verificar_diagonal(
        apertado,
        "X",
        comprimento_mm=3606.0,
        comprimento_destravado_mm=1803.0,
        tracao_kN=50.0,
        compressao_kN=0.0,
    )
    assert _linha(r, "espaçamento").status == "NÃO OK"  # 2,7·15,9 = 43 mm
    assert _linha(r, "borda").status == "NÃO OK"  # mínima de 22 mm para 5/8"


def test_tirante_rosqueado_e_a_compressao_reprova():
    tirante = cb.Diagonal(familia=cb.FAMILIA_BARRA_REDONDA, perfil="Barra circular Ø19")
    r = cb.verificar_diagonal(
        tirante,
        "X",
        comprimento_mm=7000.0,
        comprimento_destravado_mm=3500.0,
        tracao_kN=40.0,
        compressao_kN=5.0,
    )
    ab = math.pi * 19.0**2 / 4
    assert _linha(r, "tração do tirante").resistente == pytest.approx(
        min(0.75 * ab * 400 / 1.35, ab * 250 / 1.10) / 1e3
    )
    assert _linha(r, "compressão do tirante").status == "NÃO OK"
    assert _linha(r, "esbeltez do tirante").status == "ALERTA"


def test_tubo_com_chapa_concentrica_soldada():
    nome = next(n for n in cb.perfis_da_familia(cb.FAMILIA_TUBO) if "60.3" in n)
    tubo = cb.Diagonal(familia=cb.FAMILIA_TUBO, perfil=nome, ligacao=cb.LIGACAO_SOLDADA)
    r = cb.verificar_diagonal(
        tubo,
        "Y",
        comprimento_mm=5000.0,
        comprimento_destravado_mm=2500.0,
        tracao_kN=40.0,
        compressao_kN=40.0,
    )
    p = sc.obter_perfil(nome)
    an = p.area_mm2 - 2 * p.espessura_alma_mm * (9.5 + 2.0)
    coef = (1 + (p.altura_mm / math.pi / 120.0) ** 3.2) ** -10
    esperado = min(p.area_mm2 * 250 / 1.10, coef * an * 400 / 1.35) / 1e3
    assert _linha(r, "tração da diagonal").resistente == pytest.approx(esperado)
    assert _linha(r, "solda da diagonal").resistente == pytest.approx(
        0.60 * 485 * 0.707 * 5.0 * 120.0 * 4 / 1.35 / 1e3
    )
    assert _linha(r, "compressão da diagonal").resistente > 0


@pytest.mark.parametrize(
    ("troca", "trecho"),
    [
        ({"n_parafusos": 1}, "2 parafusos"),
        ({"familia": cb.FAMILIA_TUBO}, "não pertence"),
        ({"parafuso": "9/9"}, "Parafuso"),
        ({"aco": "Aço X"}, "Aço"),
        ({"ligacao": cb.LIGACAO_SOLDADA, "comprimento_solda_mm": 0.0}, "solda"),
    ],
)
def test_diagonal_invalida(troca, trecho):
    d = cb.Diagonal(**troca)
    assert any(trecho in e for e in cb.validar(d)), cb.validar(d)
    with pytest.raises(cb.DiagonalInvalida):
        cb.verificar_diagonal(
            d,
            "X",
            comprimento_mm=3000.0,
            comprimento_destravado_mm=1500.0,
            tracao_kN=10.0,
            compressao_kN=0.0,
        )
