"""Critério Anglo AA-BR-DPST-DR-0001 (valores com o item) e a base técnica do projeto."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from core import base_tecnica as bt
from core import criterio_anglo as ca


# ------------------------------------------------------------------ critério Anglo
def test_vento_do_critério_e_o_conflito_do_s3():
    assert (ca.V0_M_S, ca.S1, ca.S3) == (35.0, 1.0, 0.95)
    assert ca.item("5.6") == "Anglo 5.6"
    assert "0,95" in ca.CONFLITOS[0] and "grupo 4" in ca.CONFLITOS[0]
    assert ca.CODIGO in ca.REFERENCIA and ca.REVISAO == "1"


def test_tabela_2_de_sobrecargas():
    assert ca.sobrecarga("Plataformas de operação em geral").valor_kN_m2 == 5.0
    assert ca.sobrecarga("Cabines de controle").valor_kN_m2 == 10.0
    assert ca.sobrecarga("Escadas e passadiços em geral").valor_kN_m2 == 3.0
    with pytest.raises(ValueError, match="Tabela 2"):
        ca.sobrecarga("Lugar que não existe")
    assert len({s.local for s in ca.SOBRECARGAS}) == len(ca.SOBRECARGAS)


@pytest.mark.parametrize(
    ("espessura", "filete"),
    [(5.0, 3.0), (6.3, 3.0), (8.0, 5.0), (12.7, 5.0), (16.0, 6.0), (25.0, 8.0)],
)
def test_tabela_6_filete_minimo(espessura, filete):
    assert ca.filete_minimo_mm(espessura) == filete


@pytest.mark.parametrize(
    ("comprimento", "reducao"), [(2.0, None), (3.0, None), (4.5, 2.0), (8.0, 3.0), (12.0, 5.0)]
)
def test_tabela_5_reducao_das_cantoneiras(comprimento, reducao):
    assert ca.reducao_de_comprimento_mm(comprimento) == reducao


def test_capacidade_minima_da_ligacao_e_o_maior_entre_75_porcento_e_3_t():
    assert ca.capacidade_minima_da_ligacao_kN(100.0) == pytest.approx(75.0)
    assert ca.capacidade_minima_da_ligacao_kN(10.0) == pytest.approx(3 * 9.80665)


def test_limites_de_deslocamento_por_tipo():
    plataforma = ca.LIMITE_DO_TOPO_POR_TIPO[ca.TIPO_PLATAFORMA]
    assert plataforma.divisor == 400 and plataforma.base == "H"
    assert ca.LIMITE_DO_TOPO_POR_TIPO[ca.TIPO_PIPE_RACK].divisor == 250
    assert ca.LIMITE_ENTRE_PISOS.divisor == 500
    terca = next(d for d in ca.DESLOCAMENTOS_VERTICAIS if d.descricao.startswith("Terças"))
    assert terca.limite_mm(9000.0) == 30.0  # L/200 = 45 mm, mas no máximo 30 mm
    assert terca.texto == "L/200, máx. 30 mm"


@pytest.mark.parametrize(
    ("ne", "nm", "faixa", "atende"),
    [
        (13.0, 10.0, "preferencial", True),
        (7.0, 10.0, "alternativa", True),
        (4.0, 10.0, "abaixo", True),
        (10.0, 10.0, "fora", False),
        (20.0, 10.0, "fora", False),
    ],
)
def test_vibracao_5_7(ne, nm, faixa, atende):
    a = ca.avaliar_frequencia(ne, nm, 600.0)
    assert faixa in a.faixa and a.atende is atende
    assert a.amplitude_vertical_max_mm == pytest.approx(240.0 / 600.0)


def test_vibracao_coeficiente_dinamico():
    a = ca.avaliar_frequencia(13.0, 10.0)
    assert a.coeficiente_dinamico == pytest.approx(1 / (1 - (10 / 13) ** 2))
    assert math.isinf(ca.avaliar_frequencia(10.0, 10.0).coeficiente_dinamico)
    with pytest.raises(ValueError):
        ca.avaliar_frequencia(0.0, 10.0)


# ------------------------------------------------------------------ base técnica
def test_base_anglo_traz_o_vento_e_a_sobrecarga_do_criterio():
    base = bt.base_do_cliente(bt.CLIENTE_ANGLO)
    assert base.anglo and base.vento.grupo_s3 == bt.S3_DO_CLIENTE
    assert base.vento.s3 == 0.95 and base.vento.v0_m_s == 35.0
    assert base.sobrecarga_kN_m2 == 5.0
    assert "critério do cliente" in bt.texto_do_vento(base)
    assert bt.validar(base) == []


def test_base_sem_cliente_usa_o_grupo_da_norma():
    base = bt.base_do_cliente(bt.CLIENTE_NENHUM)
    assert not base.anglo
    assert base.vento.s3 == pytest.approx(1.0)
    assert "grupo 3" in base.vento.texto_s3
    assert bt.avisos(base) == []


@pytest.mark.parametrize(
    ("troca", "trecho"),
    [
        ({"cliente": "outro"}, "cliente desconhecido"),
        ({"tipo_de_estrutura": "Torre"}, "Tipo de estrutura"),
        ({"sobrecarga_kN_m2": -1.0}, "negativa"),
        ({"classe_de_agressividade": "C9"}, "agressividade"),
    ],
)
def test_validar_aponta_o_campo_errado(troca, trecho):
    assert any(trecho in e for e in bt.validar(replace(bt.BaseTecnica(), **troca)))


def test_validar_vento_fora_da_faixa():
    vento = bt.VentoDoLocal(v0_m_s=5.0, s1=3.0, categoria="VI", grupo_s3=bt.S3_DO_CLIENTE)
    erros = " ".join(bt.validar(bt.BaseTecnica(vento=vento)))
    for trecho in ("V₀", "S₁", "Categoria", "S₃ do cliente"):
        assert trecho in erros


def test_ida_e_volta_pelo_documento_do_projeto():
    base = replace(bt.base_do_cliente(bt.CLIENTE_ANGLO), local="Porto do Açu", vida_util_anos=None)
    dados = json.loads(json.dumps(bt.para_dicionario(base)))
    assert bt.de_dicionario(dados) == base
    assert bt.base_do_projeto({"base_tecnica": dados}) == base
    assert bt.base_do_projeto({}) is None and bt.base_do_projeto(None) is None
    assert bt.de_dicionario({}) is None


def test_documento_antigo_sem_campos_novos_ainda_le():
    base = bt.de_dicionario({"cliente": "anglo", "vento": {"v0_m_s": "32"}})
    assert base is not None and base.vento.v0_m_s == 32.0 and base.vento.s3 == 0.95


@pytest.mark.parametrize(
    ("tipo", "pisos", "divisor", "entre_pisos", "trecho"),
    [
        (ca.TIPO_PLATAFORMA, 1, 400.0, None, "Anglo 7.2"),
        (ca.TIPO_PLATAFORMA, 2, 400.0, 500.0, "Anglo 7.2"),
        (ca.TIPO_PIPE_RACK, 1, 250.0, None, "pipe rack"),
        (bt.TIPO_NBR_UM_PAVIMENTO, 1, 300.0, None, "um pavimento"),
        (bt.TIPO_NBR_UM_PAVIMENTO, 2, 400.0, 500.0, "dois ou mais"),
        (bt.TIPO_NBR_PAVIMENTOS, 1, 400.0, 500.0, "dois ou mais"),
    ],
)
def test_limite_do_topo(tipo, pisos, divisor, entre_pisos, trecho):
    limite = bt.limite_do_topo(replace(bt.BaseTecnica(), tipo_de_estrutura=tipo), pisos)
    assert limite.divisor == divisor and limite.entre_pisos_divisor == entre_pisos
    assert trecho in limite.referencia


def test_sem_base_o_limite_e_o_da_nbr():
    assert bt.limite_do_topo(None, 1).divisor == 300.0
    assert bt.limite_do_topo(None, 3).divisor == 400.0
    assert bt.limite_do_topo(None, 1).limite_mm(6000.0) == pytest.approx(20.0)


def test_avisos_da_base_anglo():
    avisos = bt.avisos(bt.base_do_cliente(bt.CLIENTE_ANGLO))
    assert avisos == [ca.CONFLITOS[0], ca.CONFLITOS[1]]
