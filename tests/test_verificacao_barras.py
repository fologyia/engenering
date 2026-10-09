"""Verificação automática das barras do modelo com os esforços importados do SolidWorks."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from core import column_buckling as cbk
from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core import verificacao_barras as vb
from core.project_report import montar_modelo_relatorio
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro
from tests.test_esforcos_modelo import PILAR, VIGA, importar, plano_do_portico

PILAR_2 = "Viga-3(Aparar/Estender12[2])"


def portico_configurado(**tipo) -> em.EsforcosDoModelo:
    dados = importar("PP", "SC", "W0", "W180")
    dados = em.com_membros(
        dados,
        {
            PILAR: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", em.EIXO_M2),
            PILAR_2: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", em.EIXO_M2),
            VIGA: em.ConfiguracaoDoMembro("W 310 x 32,7", "Viga", em.EIXO_M2, lb_m=1.5),
        },
    )
    return em.com_parametros(
        dados,
        {
            "Pilar": em.ParametrosDoTipo(lx_m=4.0, ly_m=4.0, **tipo),
            "Viga": em.ParametrosDoTipo(lx_m=6.0, ly_m=1.5),
        },
    )


def resultado(resultados, membro):
    return next(r for r in resultados if r.membro == membro)


def test_portico_atende_e_o_pilar_bate_com_a_flambagem_de_colunas():
    resultados, avisos = vb.verificar_barras(portico_configurado(), plano_do_portico())
    assert not avisos and all(r.status == "OK" for r in resultados)
    pilar = resultado(resultados, PILAR)
    assert pilar.combinacao == "C03-ELU" and pilar.n == pytest.approx(-52.6, abs=0.05)
    direto = cbk.verificar_coluna(
        cbk.EntradaColuna(
            secao=cbk.secao_de_perfil(sc.obter_perfil("W 200 x 35,9 (H)")),
            fy_MPa=345.0,
            norma="NBR8800_2024",
            Lx_mm=4000.0,
            Ly_mm=4000.0,
            Lb_mm=4000.0,
            N_Sd_kN=-pilar.n,
            Mx_kNm=abs(pilar.m_forte),
            My_kNm=abs(pilar.m_fraco),
        )
    )
    assert pilar.aproveitamento == pytest.approx(direto.indice_interacao, rel=1e-6)
    assert pilar.governante.startswith("Interação")
    viga = resultado(resultados, VIGA)
    assert viga.m_forte == pytest.approx(45.07, abs=0.05)  # meio do vão
    assert any(v.nome.startswith("Cortante") for v in viga.linhas)
    assert any(v.nome.startswith("Torção") for v in viga.linhas)


def test_b2_amplifica_os_esforcos():
    sem = resultado(vb.verificar_barras(portico_configurado(), plano_do_portico())[0], PILAR)
    com = resultado(vb.verificar_barras(portico_configurado(b2=1.2), plano_do_portico())[0], PILAR)
    assert com.n == pytest.approx(1.2 * sem.n)
    assert com.aproveitamento > sem.aproveitamento


def test_barra_sem_perfil_ou_sem_comprimentos_fica_pendente():
    dados = importar("PP", "SC")
    resultados, _ = vb.verificar_barras(dados, plano_do_portico())
    assert all(r.status == vb.STATUS_PENDENTE for r in resultados)
    assert "escolha o perfil" in resultado(resultados, PILAR).motivo
    dados = em.com_membros(dados, {PILAR: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar")})
    assert (
        "comprimentos de flambagem"
        in resultado(vb.verificar_barras(dados, plano_do_portico())[0], PILAR).motivo
    )
    dados = em.com_membros(
        dados,
        {PILAR: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", aco="Aço X", lx_m=4, ly_m=4)},
    )
    assert (
        "aço desconhecido"
        in resultado(vb.verificar_barras(dados, plano_do_portico())[0], PILAR).motivo
    )


def _caso_manual(codigo: str, membro: str, n: float, m: float = 0.0) -> em.CasoImportado:
    pontos = tuple(
        em.PontoDeEsforco(str(i), fim, n, 0.0, 0.0, 0.0, m, 0.0)
        for i in (1, 2)
        for fim in ("1", "2")
    )
    return em.CasoImportado(codigo, codigo, f"{codigo}.csv", "", "", {membro: pontos})


def test_tirante_so_tracionado_usa_o_limite_de_esbeltez_da_tracao():
    dados = em.com_caso(em.EsforcosDoModelo(), _caso_manual("PP", "Tirante", 50.0))
    dados = em.com_membros(
        dados, {"Tirante": em.ConfiguracaoDoMembro("W 150 x 22,5 (H)", "Diagonal", lx_m=5, ly_m=5)}
    )
    plano = pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PP"))
    r = resultado(vb.verificar_barras(dados, plano)[0], "Tirante")
    nomes = [v.nome for v in r.linhas]
    assert "Esbeltez limite (tração)" in nomes
    assert not any(n.startswith("Esbeltez limite (compressão)") for n in nomes)
    tracao = next(v for v in r.linhas if v.nome.startswith("Tração"))
    perfil = sc.obter_perfil("W 150 x 22,5 (H)")
    assert tracao.resistente == pytest.approx(perfil.area_mm2 * 345.0 / 1.10 / 1e3)
    assert r.n == pytest.approx(1.25 * 50.0) and r.status == "OK"


def test_cantoneira_usa_a_5_3_5_4_e_avisa_da_flexao():
    dados = em.com_caso(em.EsforcosDoModelo(), _caso_manual("PP", "Diagonal L", -10.0, m=0.2))
    dados = em.com_membros(
        dados,
        {"Diagonal L": em.ConfiguracaoDoMembro('L 2 1/2" × 1/4"', "Diagonal", lx_m=1.5, ly_m=1.5)},
    )
    plano = pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PP"))
    r = resultado(vb.verificar_barras(dados, plano)[0], "Diagonal L")
    nomes = [v.nome for v in r.linhas]
    assert "Cantoneira: compressão da diagonal" in nomes
    flexao = next(v for v in r.linhas if v.nome == "Cantoneira: flexão")
    assert flexao.status == "ALERTA" and r.status == "ALERTA"


def test_estados_de_servico_nao_entram_na_verificacao():
    assert vb.estados_ultimos([comb.ELS_RARA]) == [comb.ELU_NORMAL]
    assert vb.estados_ultimos([comb.ELU_NORMAL, comb.ELS_RARA]) == [comb.ELU_NORMAL]


def test_registro_tabela_csv_e_memorial():
    dados = portico_configurado()
    dados = em.com_membros(dados, {PILAR_2: em.ConfiguracaoDoMembro()})  # vira pendente
    resultados, _ = vb.verificar_barras(dados, plano_do_portico())
    sintese = vb.resumo(resultados)
    assert (sintese["atendem"], sintese["pendentes"]) == (2, 1)
    registro = vb.registro_das_barras(
        resultados, dados, [comb.ELU_NORMAL], contexto={"obra": "Obra X"}
    )
    assert avaliar_contrato_registro(registro)["valido"]
    json.dumps(registro)
    verificacoes = registro["resultados"]["verificações"]
    assert len(verificacoes) == 3
    assert sum(v["status"] == "N/A" for v in verificacoes) == 1
    assert "2 atendem" in registro["resultados"]["destaque_memorial"]
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto["registros_tecnicos"] = [registro]
    capitulos = [s for s in montar_modelo_relatorio(projeto)["secoes"] if "blocos" in s]
    assert len(capitulos) == 1
    blocos = capitulos[0]["blocos"]
    assert blocos[0]["rotulo"].startswith("Resultado:")
    legendas = " ".join(b.get("legenda", "") for b in blocos)
    assert "Verificação das barras do modelo" in legendas and "Dados de entrada." in legendas
    cabecalho = vb.csv_das_barras(resultados).decode("utf-8-sig").splitlines()[0]
    assert cabecalho.split(";") == list(vb.COLUNAS)


def test_parametros_vao_e_voltam_pelo_projeto():
    dados = replace(portico_configurado(b2=1.15), norma="NBR8800_2008")
    volta = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados))))
    assert volta.parametros_do_tipo("Pilar") == dados.parametros_do_tipo("Pilar")
    assert volta.norma == "NBR8800_2008"
    assert volta.membros[VIGA].lb_m == 1.5
