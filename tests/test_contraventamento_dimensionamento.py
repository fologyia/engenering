"""Modo simplificado da ligação: o programa escolhe parafusos, chapa e soldas e verifica."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import contraventamento_chapa as ch
from core import contraventamento_dimensionamento as dm
from core import contraventamento_ufm as ufm
from tests.test_contraventamento_ligacao import exemplo_5_1


def test_exemplo_5_1_fecha_com_chapa_de_25_mm():
    """O guia usa chapa de 1" (25,4 mm); a série comercial dá 25 mm."""
    d = dm.dimensionar_ligacao(exemplo_5_1())
    assert d.chapa_atende
    assert d.entrada.t_chapa_mm == 25.0
    assert d.entrada.fileiras == 2
    assert all(
        v.status in ("OK", "INFO", "N/A")
        for v in d.resultado.verificacoes
        if v.nome.startswith(dm.PREFIXOS_DA_CHAPA)
    )


def test_comprimentos_zeram_o_momento_nas_interfaces():
    d = dm.dimensionar_ligacao(exemplo_5_1())
    r = d.resultado
    if d.entrada.ajuste == ufm.AJUSTE_BETA:
        assert abs(r.alfa_real_mm - r.forcas.alfa_ideal_mm) <= 2.5  # arredondamento de 5 mm em l_h
    else:
        assert abs(r.beta_real_mm - r.forcas.beta_ideal_mm) <= 2.5


def test_pernas_sao_as_necessarias_arredondadas_para_cima():
    d = dm.dimensionar_ligacao(exemplo_5_1())
    r = d.resultado
    assert d.entrada.perna_na_viga_mm >= r.solda_viga.perna_necessaria_mm
    assert d.entrada.perna_na_viga_mm in dm.PERNAS_MM
    assert d.entrada.perna_na_viga_mm >= r.solda_viga.perna_minima_mm


@pytest.mark.parametrize("forca", [50.0, 300.0, 1500.0])
def test_forcas_crescentes_pedem_mais_parafusos_ou_chapa_mais_grossa(forca):
    base = replace(exemplo_5_1(), P_tracao_kN=forca, P_compressao_kN=forca)
    d = dm.dimensionar_ligacao(base)
    grupo = d.resultado.parafusos.grupo_kN
    assert grupo >= forca
    assert d.chapa_atende


def test_parafuso_pequeno_demais_vira_erro_claro():
    base = replace(
        exemplo_5_1(), designacao_do_parafuso='1/2"', grau_do_parafuso="A307", planos_de_corte=1
    )
    with pytest.raises(ch.ChapaInvalida, match="parafuso maior"):
        dm.dimensionar_ligacao(base)


def test_espacamentos_padrao_de_3d():
    d = dm.dimensionar_ligacao(exemplo_5_1())
    diametro = 22.2  # 7/8"
    assert d.entrada.passo_mm == 5 * math.ceil(3 * diametro / 5)
    assert d.entrada.extremidade_mm >= 1.5 * diametro
