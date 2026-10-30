"""Opção "furos feitos com broca" (pedido de 30/10/2026: "acrescente como uma opção que pode ou
não ser usada").

NBR 8800, 5.2.4.1 a) — na 2008 e na 2025: na área líquida o furo vale 2,0 mm a mais que a dimensão
máxima; se os furos forem feitos com broca, pode valer a própria dimensão. Desligada (o padrão),
nada muda; o AISC soma sempre 1/16" (B4.3b), com ou sem a opção.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core import contraventamento_barras as cbar
from core import ligacoes as lg


def _linha(verificacoes, inicio: str):
    return next(v for v in verificacoes if v.nome.startswith(inicio))


@pytest.mark.parametrize("norma", ["NBR8800_2008", "NBR8800_2024"])
def test_folga_da_nbr_some_com_furo_de_broca(norma):
    assert bc.folga_do_furo(norma) == 2.0
    assert bc.folga_do_furo(norma, broca=True) == 0.0
    assert bc.area_liquida(1000.0, 2, 18.0, 5.0, norma, broca=True) == pytest.approx(
        1000 - 2 * 18 * 5
    )
    assert bc.area_liquida(1000.0, 2, 18.0, 5.0, norma) == pytest.approx(1000 - 2 * 20 * 5)


@pytest.mark.parametrize("norma", ["AISC360_LRFD", "RCSC2004"])
def test_aisc_soma_sempre_1_16_de_polegada(norma):
    assert bc.folga_do_furo(norma, broca=True) == pytest.approx(25.4 / 16)


def _parafusos(**mudancas) -> chk.EntradaLigacao:
    base = dict(
        designacao="M16", N=44.8, valores_sao_de_calculo=True, A_g=1542.0, e_c=13.0,
        norma="NBR8800_2024", chapa_largura=150.0,
    )  # fmt: skip
    base.update(mudancas)
    return chk.EntradaLigacao(**base)


def test_projeto_de_parafusos_com_furo_de_broca():
    sem = chk.verificar_ligacao(_parafusos())
    com = chk.verificar_ligacao(_parafusos(furo_com_broca=True))
    for nome in ("Tração da peça", "Colapso por rasgamento"):
        assert _linha(com.verificacoes, nome).resistente > _linha(sem.verificacoes, nome).resistente
    assert "furos feitos com broca" in _linha(com.verificacoes, "Tração da peça").formula
    assert "furos feitos com broca" not in _linha(sem.verificacoes, "Tração da peça").formula
    # a peça tracionada: A_n sem os 2 mm (2 linhas de furos, t = 5,08 mm)
    entrada = _parafusos()
    a_n_sem = sem.intermediarios["A_n_mm2"]
    assert com.intermediarios["A_n_mm2"] == pytest.approx(a_n_sem + entrada.n_lin * 2.0 * entrada.t)


def test_no_aisc_a_opcao_nao_muda_nada():
    aisc = _parafusos(norma="AISC360_LRFD")
    sem = chk.verificar_ligacao(aisc)
    com = chk.verificar_ligacao(replace(aisc, furo_com_broca=True))
    assert [v.resistente for v in com.verificacoes] == [v.resistente for v in sem.verificacoes]


@pytest.mark.parametrize("entrada", [lg.EntradaChapaSimples(), lg.EntradaCantoneiraDupla()])
def test_ligacoes_parafusadas_com_furo_de_broca(entrada):
    sem = lg.calcular(entrada)
    com = lg.calcular(replace(entrada, furo_com_broca=True))
    nome = "Alma da viga: ruptura por cisalhamento na linha dos furos"
    assert _linha(com.verificacoes, nome).resistente > _linha(sem.verificacoes, nome).resistente
    dh = float(bc.dados_parafuso(entrada.parafuso)["d_h"])
    assert ("Furo na área líquida", f"{dh:.1f}".replace(".", ",") + " mm — furos feitos com broca: a largura do próprio furo, sem somar os 2 mm") in lg.detalhamento_adotado(com)  # fmt: skip
    assert not any(n == "Furo na área líquida" for n, _ in lg.detalhamento_adotado(sem))


def test_chapa_simples_ruptura_por_cisalhamento_sem_os_2_mm():
    e = replace(lg.EntradaChapaSimples(), furo_com_broca=True)
    r = lg.calcular(e)
    dh = float(bc.dados_parafuso(e.parafuso)["d_h"])
    fu = lg.ACOS[e.aco_chapa][1]
    esperado = 0.60 * fu * (e.altura_chapa_mm - e.n_parafusos * dh) * e.t_chapa_mm / 1.35 / 1000
    assert _linha(r.verificacoes, "Chapa: ruptura por cisalhamento").resistente == pytest.approx(
        esperado
    )


def test_diagonal_parafusada_do_contraventamento_com_furo_de_broca():
    diagonal = cbar.Diagonal()
    medidas = dict(
        comprimento_mm=3000.0, comprimento_destravado_mm=3000.0, tracao_kN=40.0, compressao_kN=0.0
    )
    sem = cbar.verificar_diagonal(diagonal, "Y", **medidas)
    com = cbar.verificar_diagonal(replace(diagonal, furo_com_broca=True), "Y", **medidas)
    tracao_sem = next(v for v in sem.verificacoes if "tração da diagonal" in v.nome)
    tracao_com = next(v for v in com.verificacoes if "tração da diagonal" in v.nome)
    assert "furo de broca" in tracao_com.formula and "furo de broca" not in tracao_sem.formula
    assert "A_n = A_g − d_h·t" in tracao_com.formula  # sem os 2 mm
    assert "A_n = A_g − (d_h + 2)·t" in tracao_sem.formula
    assert tracao_com.resistente >= tracao_sem.resistente
