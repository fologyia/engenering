"""Exigências do critério Anglo nas verificações: diagonal, deslocamentos, chapa de nó e soldas."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import base_tecnica as bt
from core import contraventamento_barras as cb
from core import contraventamento_dimensionamento as dm
from core import contraventamento_ligacao as lig
from core import contraventamento_plataforma as cp
from core import contraventamento_registro as reg
from core import criterio_anglo as ca
from tests.test_contraventamento_ligacao import exemplo_5_1


def _anglo(verificacoes) -> dict[str, object]:
    return {
        v.nome: v for v in verificacoes if "Anglo" in v.referencia or v.nome.startswith("Anglo")
    }


# ------------------------------------------------------------------ diagonal
def verificar(d: cb.Diagonal, *, anglo: bool = True, comprimento: float = 7200.0):
    return cb.verificar_diagonal(
        d,
        "X",
        comprimento_mm=comprimento,
        comprimento_destravado_mm=comprimento / 2,
        tracao_kN=20.0,
        compressao_kN=0.0,
        criterio_anglo=anglo,
    )


def test_sem_o_criterio_nao_ha_linhas_anglo():
    assert not [
        v for v in verificar(cb.Diagonal(), anglo=False).verificacoes if "Anglo" in v.referencia
    ]


def test_cantoneira_ganha_espessura_minima_reducao_e_capacidade_da_ligacao():
    linhas = {v.nome: v for v in verificar(cb.Diagonal()).verificacoes if "Anglo" in v.referencia}
    espessura = linhas["X: espessura mínima da cantoneira"]
    assert espessura.status == "OK" and espessura.solicitante == 4.75
    reducao = linhas["X: redução do comprimento da cantoneira (protensão)"]
    assert reducao.status == "INFO" and reducao.resistente == 3.0  # 7,2 m: Tabela 5 → 3 mm
    assert linhas["X: diâmetro mínimo do parafuso"].status == "OK"
    assert "X: capacidade mínima da ligação" in linhas


def test_parafuso_a307_numa_diagonal_reprova_pelo_criterio():
    linhas = {v.nome: v for v in verificar(cb.Diagonal(grau="A307")).verificacoes}
    assert linhas["X: grau do parafuso"].status == "NÃO OK"


def test_parafuso_acima_de_uma_polegada_pede_atencao():
    linhas = {v.nome: v for v in verificar(cb.Diagonal(parafuso='1 1/8"')).verificacoes}
    assert linhas['X: parafuso acima de 1"'].status == "ALERTA"


# ------------------------------------------------------------------ deslocamentos
@pytest.mark.parametrize(
    ("tipo", "divisor"),
    [("", 300.0), (ca.TIPO_PLATAFORMA, 400.0), (ca.TIPO_PIPE_RACK, 250.0)],
)
def test_limite_do_topo_vem_do_tipo_de_estrutura(tipo, divisor):
    r = cp.calcular(replace(cp.EntradaContraventamento(), tipo_de_estrutura=tipo))
    topo = next(v for v in r.verificacoes if v.nome == "X: deslocamento horizontal do topo")
    assert topo.resistente == pytest.approx(4000.0 / divisor)
    assert ("Anglo 7.2" in topo.referencia) is bool(tipo)


def test_tipo_de_estrutura_desconhecido_e_erro():
    erros = cp.validar_entrada(replace(cp.EntradaContraventamento(), tipo_de_estrutura="Torre"))
    assert any("Tipo de estrutura" in e for e in erros)


def test_registro_do_contraventamento_cita_o_criterio_e_o_limite():
    e = replace(
        cp.EntradaContraventamento(), criterio_anglo=True, tipo_de_estrutura=ca.TIPO_PLATAFORMA
    )
    from core import contraventamento_estrutura_registro as creg

    entradas = creg.registro_contraventamento(cp.calcular(e))["entradas"]
    assert entradas["criterio_do_cliente"].startswith("Anglo American")
    assert "Tabela 4" in entradas["limite_do_deslocamento"]
    assert bt.TIPO_NBR_UM_PAVIMENTO in bt.TIPOS_DE_ESTRUTURA


# ------------------------------------------------------------------ chapa de nó
def test_ligacao_sem_o_criterio_nao_muda():
    r = lig.calcular_ligacao(exemplo_5_1())
    assert not [v for v in r.verificacoes if v.nome.startswith("Anglo")]


def test_ligacao_com_o_criterio_ganha_as_exigencias():
    r = lig.calcular_ligacao(exemplo_5_1(criterio_anglo=True))
    linhas = {v.nome: v for v in r.verificacoes if v.nome.startswith("Anglo")}
    assert set(linhas) == {
        "Anglo: espessura mínima da chapa de nó",
        "Anglo: número mínimo de parafusos na ligação",
        "Anglo: diâmetro mínimo do parafuso",
        "Anglo: filete mínimo da solda na viga",
        "Anglo: filete mínimo da solda na coluna",
        "Anglo: capacidade mínima da ligação",
    }
    assert all(v.status in ("OK", "INFO") for v in linhas.values())
    assert r.aproveitamento_maximo == pytest.approx(
        lig.calcular_ligacao(exemplo_5_1()).aproveitamento_maximo
    )
    entradas = reg.registro_ligacao(r)["entradas"]
    assert entradas["criterio_do_cliente"].startswith("Anglo American")


@pytest.mark.parametrize(
    ("troca", "nome", "status"),
    [
        ({"t_chapa_mm": 6.3}, "Anglo: espessura mínima da chapa de nó", "NÃO OK"),
        ({"t_chapa_mm": 37.5}, "Anglo: chapa espessa ensaiada por ultrassom", "ALERTA"),
        ({"grau_do_parafuso": "A307"}, "Anglo: grau do parafuso", "NÃO OK"),
        ({"grau_do_parafuso": "A490"}, "Anglo: grau do parafuso", "ALERTA"),
        ({"designacao_do_parafuso": '1 1/8"'}, 'Anglo: parafuso acima de 1"', "ALERTA"),
        ({"perna_na_viga_mm": 5.0}, "Anglo: filete mínimo da solda na viga", "NÃO OK"),
    ],
)
def test_ligacao_fora_do_criterio(troca, nome, status):
    r = lig.calcular_ligacao(exemplo_5_1(criterio_anglo=True, **troca))
    assert next(v for v in r.verificacoes if v.nome == nome).status == status


def test_um_parafuso_so_reprova_pelo_criterio():
    linhas = {v.nome: v for v in lig.verificacoes_anglo(exemplo_5_1(), 1)}
    assert linhas["Anglo: número mínimo de parafusos na ligação"].status == "NÃO OK"
    assert {v.nome: v for v in lig.verificacoes_anglo(exemplo_5_1(), 2)}[
        "Anglo: número mínimo de parafusos na ligação"
    ].status == "OK"


def test_caso_3_nao_tem_solda_na_coluna():
    from core import contraventamento_ufm as ufm

    r = lig.calcular_ligacao(exemplo_5_1(criterio_anglo=True, caso=ufm.CASO_3))
    nomes = {v.nome for v in r.verificacoes}
    assert "Anglo: filete mínimo da solda na viga" in nomes
    assert "Anglo: filete mínimo da solda na coluna" not in nomes


def test_dimensionamento_respeita_o_filete_da_tabela_6():
    base = exemplo_5_1(P_tracao_kN=150.0, P_compressao_kN=150.0, criterio_anglo=True)
    dim = dm.dimensionar_ligacao(base)
    t = dim.entrada.t_chapa_mm
    assert t >= ca.ESPESSURAS_MINIMAS_MM["Chapas de ligação e enrijecedores"]
    assert dim.entrada.perna_na_viga_mm >= ca.filete_minimo_mm(t)
    assert dim.entrada.perna_na_coluna_mm >= ca.filete_minimo_mm(t)
    anglo = [v for v in dim.resultado.verificacoes if v.nome.startswith("Anglo: filete")]
    assert anglo and all(v.status == "OK" for v in anglo)
