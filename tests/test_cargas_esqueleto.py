"""Cargas do esqueleto: o que não está no modelo vira carga característica nas barras."""

from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd
import pytest

from components.figuras_estrutura import svg_planta_do_esqueleto
from core import cargas_esqueleto as ce
from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import plano_de_cargas as pc
from core.project_report import montar_modelo_relatorio
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro

#: Planta de 12 × 3 m, eixos 1-2-3 (6 m) e A-B, um nível a +3,00 m, piso nas vigas paralelas a X
#: com vão máximo de 1,20 m: 2 secundárias por vão, a 1,00 m.
PADRAO = ce.EntradaEsqueleto()


def _cargas(r: ce.ResultadoEsqueleto, caso: str) -> dict[str, float]:
    return {c.barra: c.valor_kN_m for c in ce.por_barra(r) if c.caso == caso}


def test_esqueleto_da_grade_tem_pilares_vigas_e_secundarias():
    barras = ce.esqueleto(PADRAO)
    por_tipo = {
        t: [b for b in barras if b.tipo == t]
        for t in (ce.TIPO_PILAR, ce.TIPO_VIGA, ce.TIPO_SECUNDARIA)
    }
    assert len(por_tipo[ce.TIPO_PILAR]) == 6  # 3 × 2 cruzamentos, um andar
    assert len(por_tipo[ce.TIPO_VIGA]) == 2 * 2 + 3 * 1  # eixos A e B (2 trechos) e 1, 2, 3
    secundarias = por_tipo[ce.TIPO_SECUNDARIA]
    assert len(secundarias) == 2 * 2 and {b.inicio[1] for b in secundarias} == {1.0, 2.0}
    assert {b.comprimento_m for b in secundarias} == {6.0}
    assert "N1 · secundária A–B nº 1 · 1–2" in {b.nome for b in secundarias}
    assert any(b.nome == "Pilar A1 · +0,00 a +3,00" for b in por_tipo[ce.TIPO_PILAR])


def test_larguras_de_influencia_fecham_a_largura_do_piso():
    assert ce.larguras_de_influencia([0.0, 1.0, 2.0, 3.0]) == [0.5, 1.0, 1.0, 0.5]
    assert ce.larguras_de_influencia([0.0, 2.0, 5.0]) == [1.0, 2.5, 1.5]


def test_exemplo_padrao_confere_com_a_conta_a_mao():
    r = ce.calcular(PADRAO)
    sc, pe = _cargas(r, "SC"), _cargas(r, "PE")
    assert sc["N1 · secundária A–B nº 1 · 1–2"] == pytest.approx(5.0 * 1.0)
    assert sc["N1 · eixo A · 1–2"] == pytest.approx(5.0 * 0.5)
    assert "N1 · eixo 1 · A–B" not in sc  # o piso não apoia nas vigas paralelas a Y
    assert pe["N1 · eixo A · 1–2"] == pytest.approx(0.30 * 0.5 + 0.25)  # piso + guarda-corpo
    assert pe["N1 · eixo 1 · A–B"] == pytest.approx(0.25)  # só o guarda-corpo
    assert ce.resumo_do_caso(r, "SC") == pytest.approx(5.0 * 36)
    assert ce.resumo_do_caso(r, "PE") == pytest.approx(0.30 * 36 + 0.25 * 30)
    assert all(c.confere for c in r.conferencia)


def test_piso_nas_vigas_paralelas_a_y():
    nivel = replace(PADRAO.niveis[0], vigas_paralelas_a=ce.DIRECAO_Y, bordas_com_guarda_corpo=())
    r = ce.calcular(replace(PADRAO, niveis=(nivel,)))
    sc = _cargas(r, "SC")
    # Vãos de 6 m em X com vão máximo de 1,20 m: 4 secundárias por vão, a 1,20 m.
    assert sum(b.tipo == ce.TIPO_SECUNDARIA for b in r.barras) == 4 * 2
    assert sc["N1 · secundária 1–2 nº 1 · A–B"] == pytest.approx(5.0 * 1.2)
    assert sc["N1 · eixo 2 · A–B"] == pytest.approx(5.0 * 1.2)
    assert sc["N1 · eixo 1 · A–B"] == pytest.approx(5.0 * 0.6)
    assert ce.resumo_do_caso(r, "SC") == pytest.approx(180.0)
    assert not [c for c in r.distribuidas if "guarda-corpo" in c.origem]


def test_guarda_corpo_so_nas_bordas_marcadas():
    nivel = replace(PADRAO.niveis[0], bordas_com_guarda_corpo=(ce.BORDA_X_MENOS, ce.BORDA_Y_MAIS))
    r = ce.calcular(replace(PADRAO, niveis=(nivel,)))
    com_gc = {c.barra for c in r.distribuidas if c.origem == "guarda-corpo"}
    assert com_gc == {"N1 · eixo 1 · A–B", "N1 · eixo B · 1–2", "N1 · eixo B · 2–3"}
    linha = next(c for c in r.conferencia if c.item.endswith("guarda-corpo"))
    assert linha.esperado_kN == pytest.approx(0.25 * (3 + 12)) and linha.confere


def test_escada_equipamento_e_tubulacao():
    e = replace(
        PADRAO,
        escadas=(ce.Escada(borda=ce.BORDA_Y_MAIS, trecho=2, largura_m=1.0, projecao_m=4.0),),
        equipamentos=(
            ce.Equipamento(
                peso_vazio_kN=40,
                conteudo_kN=20,
                apoios=4,
                impacto_vertical=1.0,
                impacto_horizontal=0.25,
            ),
        ),
        cargas_lineares=(ce.CargaLinear(eixo="2", valor_kN_m=0.6, caso="EO"),),
    )
    r = ce.calcular(e)
    escada = [f for f in r.forcas if "Escada 1" in f.onde]
    assert {f.caso for f in escada} == {"PE", "SC"}
    assert all(f.onde.startswith("N1 · eixo B · 2–3") and f.quantidade == 2 for f in escada)
    sc = next(f for f in escada if f.caso == "SC")
    assert sc.valor_kN == pytest.approx(3.0 * 1.0 * 4.0 / 2 / 2)
    assert "vai direto à fundação" in r.fundacao[0]
    equipamento = {f.caso + f.direcao: f for f in r.forcas if "Equipamento" in f.onde}
    assert equipamento["EQ" + ce.VERTICAL].valor_kN == pytest.approx(10.0)
    assert equipamento["EO" + ce.VERTICAL].valor_kN == pytest.approx(5.0)
    assert equipamento["IM" + ce.VERTICAL].valor_kN == pytest.approx(60.0 / 4)
    assert equipamento["IMX"].valor_kN == pytest.approx(0.25 * 60 / 4)
    assert _cargas(r, "EO") == {"N1 · eixo 2 · A–B": pytest.approx(0.6)}
    assert all(c.confere for c in r.conferencia)
    assert r.casos == ("PE", "SC", "EQ", "EO", "IM")


@pytest.mark.parametrize(
    ("mudanca", "trecho"),
    [
        ({"eixos_x_m": (0.0, 6.0, 6.0)}, "eixos em X"),
        ({"eixos_y_m": (0.0,)}, "dois eixos em Y"),
        ({"niveis": (ce.Nivel(cota_m=3.0), ce.Nivel(cota_m=2.0))}, "crescentes"),
        ({"escadas": (ce.Escada(nivel=3),)}, "nível de chegada"),
        ({"escadas": (ce.Escada(borda=ce.BORDA_X_MENOS, trecho=5),)}, "trecho da borda"),
        ({"cargas_lineares": (ce.CargaLinear(eixo="Z"),)}, "eixo 'Z' não existe"),
        ({"cargas_lineares": (ce.CargaLinear(caso="SC"),)}, "PE ou EO"),
        ({"acrescimo_ligacoes_pct": 40.0}, "entre 0 e 30"),
    ],
)
def test_entrada_invalida(mudanca, trecho):
    e = replace(PADRAO, **mudanca)
    assert any(trecho in erro for erro in ce.validar(e)), ce.validar(e)
    with pytest.raises(ce.EsqueletoInvalido):
        ce.calcular(e)


def test_vai_para_o_plano_com_comprimentos_e_o_fator_do_peso_proprio():
    r = ce.calcular(replace(PADRAO, equipamentos=(ce.Equipamento(),), temperatura=True))
    manual = pc.nova_acao("W0", cargas=[pc.CargaDoModelo("Topo", 5.0, "kN", "X")])
    plano = ce.aplicar_no_plano(r, pc.com_acao(pc.PlanoDeCargas(), manual))
    assert set(plano.codigos) == {"PP", "PE", "SC", "EQ", "W0", "T+", "T−"}
    assert plano.fator_peso_proprio == pytest.approx(1.07)
    assert plano.acao("W0") == manual  # o que foi informado de outro jeito fica
    for caso in ("PE", "SC", "EQ"):
        acao = plano.acao(caso)
        assert acao.origem == ce.ORIGEM
        assert sum(c.resultante or 0 for c in acao.cargas) == pytest.approx(
            ce.resumo_do_caso(r, caso)
        )
    # Sem o equipamento e sem a temperatura, o que a página tinha gerado sai do plano.
    de_novo = ce.aplicar_no_plano(ce.calcular(PADRAO), plano)
    assert set(de_novo.codigos) == {"PP", "PE", "SC", "W0"}
    volta = pc.de_dicionario(json.loads(json.dumps(pc.para_dicionario(de_novo))))
    assert volta.fator_peso_proprio == pytest.approx(1.07)
    assert volta.acao("SC").cargas[0].comprimento_m > 0


def test_reacoes_do_modelo_conferidas_contra_as_cargas_do_esqueleto():
    r = ce.calcular(PADRAO)
    plano = ce.aplicar_no_plano(r, pc.PlanoDeCargas())
    sc = ce.resumo_do_caso(r, "SC")
    dados = em.EsforcosDoModelo(
        casos={
            "SC": em.CasoImportado("SC", "", "", "", "", {}, em.Reacoes((0.0, sc, 0.0))),
            "PP": em.CasoImportado("PP", "", "", "", "", {}, em.Reacoes((0.0, 10.7, 0.0))),
        }
    )
    textos = {
        i.texto: i.nivel for i in em.conferir_reacoes(dados, plano, peso_da_estrutura_kN=10.0)
    }
    assert any("SC: as reações equilibram as forças do plano (180,00 kN)" in t for t in textos)
    pp = next(t for t in textos if "peso da estrutura" in t)
    assert textos[pp] == pc.NIVEL_OK and "1,07 de ligações não modeladas" in pp


def test_exportacao_usa_a_gravidade_com_o_fator():
    plano = ce.aplicar_no_plano(ce.calcular(PADRAO), pc.PlanoDeCargas())
    linhas = ex.linhas_de_carga(plano, ex.UNIDADES_KN_M, ex.EIXO_Y_PARA_CIMA)
    gravidade = next(linha for linha in linhas if linha.tipo == ex.TIPO_GRAVIDADE)
    assert gravidade.valor == pytest.approx(9.81 * 1.07)
    assert "10,50 m/s²" in gravidade.solidworks and "ligações" in gravidade.observacao
    leia = " ".join(
        ex.texto_leia_me(ex.UNIDADES_KN_M, ex.EIXO_Y_PARA_CIMA, fator_peso_proprio=1.07)
    )
    assert "10,50 m/s² = 9,81 × 1,07" in leia


def test_entrada_vai_e_volta_pelo_projeto_e_pelas_tabelas_da_pagina():
    e = replace(
        PADRAO,
        niveis=(
            ce.Nivel(),
            ce.Nivel(cota_m=6.0, vigas_paralelas_a=ce.DIRECAO_Y, bordas_com_guarda_corpo=("X−",)),
        ),
        escadas=(ce.Escada(),),
        equipamentos=(ce.Equipamento(impacto_vertical=0.2),),
        cargas_lineares=(ce.CargaLinear(),),
    )
    assert ce.de_dicionario(json.loads(json.dumps(ce.para_dicionario(e)))) == e
    assert ce.entrada_do_projeto({"cargas_do_esqueleto": ce.para_dicionario(e)}) == e
    assert ce.entrada_do_projeto({}) is None
    assert ce.de_dicionario({"niveis": 5, "eixos_x_m": ["a"], "escadas": [3]}) == replace(
        PADRAO, niveis=PADRAO.niveis
    )
    # Tabelas como o data_editor devolve: bool do numpy, NaN nas células vazias, linha em branco.
    niveis = pd.DataFrame(ce.tabela_dos_niveis(e), columns=list(ce.COLUNAS_NIVEIS))
    niveis.loc[len(niveis)] = [None] * len(ce.COLUNAS_NIVEIS)
    assert ce.niveis_da_tabela(niveis.to_dict("records")) == e.niveis
    assert ce.escadas_da_tabela(ce.tabela_das_escadas(e)) == e.escadas
    assert ce.equipamentos_da_tabela(ce.tabela_dos_equipamentos(e)) == e.equipamentos
    assert ce.tubulacoes_da_tabela(ce.tabela_das_tubulacoes(e)) == e.cargas_lineares
    assert ce.ler_eixos("0; 6,5 12") == (0.0, 6.5, 12.0)
    with pytest.raises(ce.EsqueletoInvalido):
        ce.ler_eixos("0; seis")


def test_registro_memorial_csv_e_desenho():
    r = ce.calcular(replace(PADRAO, escadas=(ce.Escada(),)))
    registro = ce.registro_esqueleto(r)
    assert avaliar_contrato_registro(registro)["valido"]
    json.dumps(registro)
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto["registros_tecnicos"] = [registro]
    capitulo = next(s for s in montar_modelo_relatorio(projeto)["secoes"] if "blocos" in s)
    assert capitulo["blocos"][0]["rotulo"] == "Resultado do cálculo."
    texto = ce.csv_das_cargas(r).decode("utf-8-sig")
    assert "N1 · secundária A–B nº 1 · 1–2" in texto and "Escada 1" in texto
    svg = svg_planta_do_esqueleto(r, 1, "SC")
    assert svg.startswith("<svg") and "5,00" in svg and "caso SC" in svg
