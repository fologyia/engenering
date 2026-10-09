"""Plano de cargas: ações com código padrão, cargas para o modelo, combinações e CSV."""

from __future__ import annotations

import csv
import io
import json

import pytest

from core import load_combinations as comb
from core import plano_de_cargas as pc


def plano_com(*codigos: str) -> pc.PlanoDeCargas:
    plano = pc.PlanoDeCargas()
    for codigo in codigos:
        plano = pc.com_acao(plano, pc.nova_acao(codigo))
    return plano


def ler_csv(conteudo: bytes) -> list[list[str]]:
    assert conteudo.startswith("﻿".encode())  # BOM: o Excel abre em UTF-8
    return list(csv.reader(io.StringIO(conteudo.decode("utf-8-sig")), delimiter=";"))


def test_codigos_sao_unicos_e_as_categorias_existem():
    assert len(pc.CODIGOS_POR_NOME) == len(pc.CODIGOS)
    for c in pc.CODIGOS:
        comb.categoria_nbr(c.categoria)  # não levanta
    assert {"PP", "SC", "W0", "W90", "W180", "W270", "T+", "T−"} <= set(pc.CODIGOS_POR_NOME)


def test_nova_acao_herda_nome_categoria_e_grupo_do_codigo():
    w = pc.nova_acao("W90")
    assert w.nome == "Vento a 90° (+Y)" and w.grupo == "Vento" and w.origem == "Informada"
    assert comb.categoria_nbr(w.categoria).tipo == comb.TIPO_VARIAVEL
    assert pc.nova_acao("PP", nome="Peso do aço").nome == "Peso do aço"


def test_com_acao_substitui_o_mesmo_codigo_e_ordena_pelo_padrao():
    plano = plano_com("W0", "SC", "PP")
    assert plano.codigos == ("PP", "SC", "W0")
    novo = pc.com_acao(plano, pc.nova_acao("SC", resumo="7,5 kN/m²"))
    assert novo.codigos == ("PP", "SC", "W0")
    assert novo.acao("SC").resumo == "7,5 kN/m²"
    assert pc.sem_acao(novo, "SC").codigos == ("PP", "W0")


def test_permanente_com_grupo_exclusivo_e_invalida():
    acao = pc.nova_acao("PP", grupo="Vento")
    assert any("permanente" in e for e in pc.validar_acao(acao))
    with pytest.raises(pc.PlanoInvalido):
        pc.com_acao(pc.PlanoDeCargas(), acao)


def test_unidade_desconhecida_e_invalida():
    acao = pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kgf", "Z (vertical)")])
    assert any("unidade" in e for e in pc.validar_acao(acao))


def test_ida_e_volta_pelo_documento_do_projeto():
    plano = pc.com_acao(
        plano_com("PP"),
        pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)", "nota")]),
    )
    dados = json.loads(json.dumps(pc.para_dicionario(plano)))
    assert pc.plano_do_projeto({"plano_de_cargas": dados}) == plano
    assert pc.plano_do_projeto(None).acoes == ()
    assert pc.de_dicionario({"acoes": ["lixo", {"codigo": "PP"}]}).codigos == ("PP",)


def test_vento_nas_quatro_direcoes_nunca_atua_junto():
    plano = plano_com("PP", "PE", "SC", "W0", "W90", "W180", "W270")
    lista = pc.combinacoes(plano, comb.ESTADOS_PADRAO)
    assert [c.numero for c in lista] == list(range(1, len(lista) + 1))
    for c in lista:
        ventos = [k for k, v in c.fatores.items() if k.startswith("W") and v]
        assert len(ventos) <= 1, c.expressao
    elu = [c for c in lista if c.estado_limite == comb.ELU_NORMAL]
    assert any(c.fatores.get("W0") for c in elu)
    assert pc.combinacoes(pc.PlanoDeCargas()) == []


def test_cobertura_das_combinacoes_minimas_do_criterio_anglo():
    cobertura = pc.cobertura_das_combinacoes_anglo(plano_com("PP", "EQ", "W0"))
    so_vento = cobertura[2]  # Permanente + Equipamento vazio + Vento
    assert so_vento.coberta and set(so_vento.presentes) == {"PP", "EQ", "W0"}
    com_ponte = cobertura[0]
    assert com_ponte.faltantes == ("SC",)
    assert set(com_ponte.opcionais_ausentes) == {"PRV", "MO"}


def test_acoes_de_vento_trocam_o_sinal_em_180_e_270():
    cargas = {
        "X": [pc.CargaDoModelo("P1", 2.0, "kN", "X")],
        "Y": [pc.CargaDoModelo("P1", 3.0, "kN", "Y")],
    }
    w0, w90, w180, w270 = pc.acoes_de_vento("teste", cargas, resumo_por_direcao={"X": "x"})
    assert [a.codigo for a in (w0, w90, w180, w270)] == ["W0", "W90", "W180", "W270"]
    assert w0.cargas[0].valor == 2.0 and w0.cargas[0].direcao == "+X" and w0.resumo == "x"
    assert w180.cargas[0].valor == -2.0 and w180.cargas[0].direcao == "−X"
    assert w270.cargas[0].valor == -3.0 and w90.origem == "teste"


def test_csv_abre_no_excel_com_virgula_decimal():
    plano = pc.com_acao(
        plano_com("PP"),
        pc.nova_acao(
            "SC",
            cargas=[
                pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)"),
                pc.CargaDoModelo("Passadiço", 3.0, "kN/m²", "Z (vertical)"),
            ],
        ),
    )
    acoes = ler_csv(pc.csv_das_acoes(plano))
    assert acoes[0][0] == "Código" and [linha[0] for linha in acoes[1:]] == ["PP", "SC"]
    cargas = ler_csv(pc.csv_das_cargas(plano))
    assert len(cargas) == 3  # cabeçalho + uma linha por carga
    assert cargas[1][4] == "5,0000"
    combinacoes = ler_csv(pc.csv_das_combinacoes(plano, [comb.ELU_NORMAL]))
    assert combinacoes[0][:3] == ["Nº", "Estado-limite", "Combinação"]
    assert combinacoes[0][3:5] == ["PP", "SC"]


def test_linhas_para_o_editor_de_combinacoes_da_barra():
    linhas = pc.linhas_para_esforcos(plano_com("PP", "W0"))
    assert len(linhas[0]) == len(pc.COLUNAS_DOS_ESFORCOS)
    pp, w0 = linhas
    assert pp[0] == "PP" and pp[2] == comb.TIPO_PERMANENTE and pp[4:7] == [0.0, 0.0, 0.0]
    assert w0[3] == "Vento" and w0[7] == pytest.approx(1.4)


def test_resumo():
    assert pc.resumo_do_plano(pc.PlanoDeCargas()) == "Plano de cargas vazio."
    assert pc.resumo_do_plano(plano_com("PP", "SC")) == "2 ação(ões): PP, SC"
