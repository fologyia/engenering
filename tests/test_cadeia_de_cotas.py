"""Cadeia de cotas: pior caso, estatístico e a tela."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import cadeia_de_cotas as cc

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _linha(nome, sentido, nominal, superior=0.0, inferior=0.0, classe=""):
    return {
        "nome": nome,
        "sentido": sentido,
        "nominal": nominal,
        "classe": classe,
        "superior": superior,
        "inferior": inferior,
    }


def test_exemplo_conta_de_mao():
    # 60 (+0,1/0) − 20 (0/−0,12) − 20 (0/−0,12) − 19,8 h11 (0/−0,13, IT11 de 18 a 30 mm).
    c = cc.montar(cc.EXEMPLO)
    assert c.nominal == pytest.approx(0.2)
    assert c.pior_minima == pytest.approx(0.2)
    assert c.pior_maxima == pytest.approx(60.1 - 19.88 - 19.88 - 19.67)
    sigmas = [0.1 / 6, 0.12 / 6, 0.12 / 6, 0.13 / 6]
    assert c.sigma == pytest.approx(math.sqrt(sum(s**2 for s in sigmas)))
    media = 60.05 - 19.94 - 19.94 - 19.735
    assert c.media == pytest.approx(media)
    assert c.estatistica_minima == pytest.approx(media - 3 * c.sigma)
    # O estatístico é sempre mais estreito que o pior caso.
    assert c.pior_minima < c.estatistica_minima < c.estatistica_maxima < c.pior_maxima


def test_classe_iso_da_os_afastamentos():
    elo = cc.elo_da_linha(_linha("Espaçador", cc.DIMINUI, 19.8, classe="h11"), 1)
    assert (elo.superior, elo.inferior) == (0.0, pytest.approx(-0.13))
    assert elo.classe == "h11"


def test_contribuicoes_somam_100_e_vem_em_ordem():
    c = cc.montar(cc.EXEMPLO)
    assert sum(x.no_pior_caso for x in c.contribuicoes) == pytest.approx(1.0)
    assert sum(x.na_variancia for x in c.contribuicoes) == pytest.approx(1.0)
    assert c.contribuicoes[0].elo.nome == "Espaçador"  # a maior tolerância, 0,13 mm


def test_exigencia_pior_caso_e_estatistico():
    atende = cc.montar(cc.EXEMPLO, exigida_min=0.1, exigida_max=0.8)
    assert atende.pior_caso_atende and atende.estatistico_atende
    so_em_serie = cc.montar(cc.EXEMPLO, exigida_min=0.25)
    assert so_em_serie.pior_caso_atende is False and so_em_serie.estatistico_atende
    assert 0 < so_em_serie.fora_abaixo() < 0.0027
    nao = cc.montar(cc.EXEMPLO, exigida_min=0.40)
    assert nao.estatistico_atende is False and nao.fora_abaixo() > 0.0027


def test_sem_exigencia_nao_diz_se_atende():
    c = cc.montar(cc.EXEMPLO)
    assert c.pior_caso_atende is None and c.fora_abaixo() is None


@pytest.mark.parametrize(
    ("linhas", "trecho"),
    [
        ([_linha("A", cc.AUMENTA, 10.0)], "dois elos"),
        ([_linha("A", cc.DIMINUI, 10.0), _linha("B", cc.DIMINUI, 5.0)], "Nenhum elo aumenta"),
        ([_linha("A", cc.AUMENTA, 10.0), _linha("B", "?", 5.0)], "aumenta ou diminui"),
        ([_linha("A", cc.AUMENTA, 10.0), _linha("B", cc.DIMINUI, -5.0)], "maior que zero"),
        (
            [_linha("A", cc.AUMENTA, 10.0), _linha("B", cc.DIMINUI, 5.0, -0.1, 0.1)],
            "não pode ficar",
        ),
        ([_linha("A", cc.AUMENTA, 10.0), _linha("B", cc.DIMINUI, 5.0, classe="zz9")], "B:"),
        ([_linha("A", cc.AUMENTA, 10.0), _linha("B", cc.DIMINUI, 5.0, classe="t6")], "24 mm"),
    ],
)
def test_entrada_ruim_explica(linhas, trecho):
    with pytest.raises(cc.ErroDaCadeia, match=trecho):
        cc.montar(linhas)


def test_linhas_vazias_da_tabela_nao_contam():
    vazia = {"nome": None, "sentido": None, "nominal": None, "classe": None}
    assert len(cc.montar([*cc.EXEMPLO, vazia]).elos) == 4


def test_numero_em_texto_com_virgula():
    elo = cc.elo_da_linha(_linha("A", cc.AUMENTA, "12,5", "0,1", "0"), 1)
    assert elo.nominal == 12.5 and elo.superior == pytest.approx(0.1)


def test_exigencias_invertidas_explica():
    with pytest.raises(cc.ErroDaCadeia, match="mínima"):
        cc.montar(cc.EXEMPLO, exigida_min=0.5, exigida_max=0.1)


def test_registro():
    registro = cc.registro(cc.montar(cc.EXEMPLO, exigida_min=0.1))
    assert registro["status"] == "Atende"
    assert len(registro["entradas"]["elos"]) == 4
    assert "0,2 mm" in registro["resumo"]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _abrir() -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/ajustes_e_tolerancias.py").run()
    assert not t.exception, [e.value for e in t.exception]
    return t


def test_aba_da_cadeia_abre_com_o_exemplo():
    t = _abrir()
    assert any(m.label == "Folga nominal" and m.value == "0,2 mm" for m in t.metric)
    assert any("Atende no pior caso" in s.value for s in t.success)
    quadro = next(d.value for d in t.dataframe if "Peso na variação" in d.value.columns)
    assert list(quadro["Elo"])[0] == "Espaçador"


def test_folga_minima_maior_avisa():
    t = _abrir()
    t.number_input(key="aj_cadeia_min").set_value(0.4).run()
    assert not t.exception
    assert any("Não atende" in e.value for e in t.error)


def test_editar_a_tabela():
    """O que o st.data_editor manda: linha editada, apagada e nova."""
    from components.edicao_de_tabela import com_edicoes

    mudancas = {
        "edited_rows": {0: {"Nominal (mm)": 61.0}},
        "deleted_rows": [3],
        "added_rows": [{"Elo": "Anel", "Sentido": cc.DIMINUI, "Nominal (mm)": 1.0}],
    }
    linhas = cc.da_tela(com_edicoes(cc.para_a_tela(cc.EXEMPLO), mudancas))
    assert linhas[0]["nominal"] == 61.0
    assert [linha["nome"] for linha in linhas] == [
        "Largura interna da caixa",
        "Rolamento 1 (largura)",
        "Rolamento 2 (largura)",
        "Anel",
    ]
    assert cc.montar(linhas).nominal == pytest.approx(61 - 40 - 1)
