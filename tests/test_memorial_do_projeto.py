"""Juntar o projeto num documento: um de cada cálculo, na ordem do projeto (core/memorial_do_projeto.py
e a Central de relatórios), e as reações nas bases no memorial."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core import memorial_do_projeto as mdp
from core import reacoes_nas_bases as rb
from core.project_report import gerar_relatorio_industrial_word, montar_modelo_relatorio
from core.project_store import adicionar_registro_tecnico, obter_projeto_ativo
from core.technical_records import STATUS_SUPERADO, criar_registro_tecnico
from tests import portico_3d_teste01 as t
from tests.test_memorial_verificacoes import registro_flambagem, texto_word
from tests.test_nucleo_esforcos_ponta_a_ponta import montar

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGINA = "app_pages/central_relatorios.py"


def _registro(modulo_id: str, titulo: str, criado_em: str, **resultados: object) -> dict:
    r = criar_registro_tecnico(
        modulo=modulo_id,
        modulo_id=modulo_id,
        titulo=titulo,
        status="Calculado",
        resumo=titulo,
        entradas={"x": 1},
        resultados={"destaque_memorial": titulo, **resultados},
    )
    r["criado_em"] = criado_em
    return r


def test_do_modelo_inteiro_vale_o_mais_novo_e_nas_outras_so_a_copia_identica():
    barras_1 = _registro(
        "esforcos_modelo", "Verificação das barras do modelo — 8 barras", "2026-10-01"
    )
    barras_2 = _registro(
        "esforcos_modelo", "Verificação das barras do modelo — 9 barras", "2026-10-05"
    )
    placas = _registro("esforcos_modelo", "Placas de base dos pilares — 4 pilar(es)", "2026-10-02")
    coluna_a = _registro("flambagem_colunas", "Flambagem — W 150", "2026-10-01", n=1)
    coluna_b = _registro("flambagem_colunas", "Flambagem — W 150", "2026-10-02", n=2)
    copia = deepcopy(coluna_a) | {"id": "copia", "criado_em": "2026-10-03"}
    registros = [barras_1, placas, coluna_a, coluna_b, barras_2, copia]
    assert mdp.repetidos(registros) == {barras_1["id"]: barras_2["id"], coluna_a["id"]: "copia"}
    # Na ordem do projeto: barras, pilares (as duas colunas diferentes), placas de base.
    assert mdp.ordem_do_projeto(registros) == [
        barras_2["id"],
        coluna_b["id"],
        "copia",
        placas["id"],
    ]


def test_juntar_supera_os_repetidos_e_monta_a_composicao():
    antigo = _registro("colunas_do_modelo", "Colunas do modelo — 4 pilares", "2026-10-01")
    novo = _registro("colunas_do_modelo", "Colunas do modelo — 4 pilares", "2026-10-09")
    vento = _registro("vento_nbr6123", "Vento — galpão", "2026-10-02")
    mohr = _registro("circulo_mohr", "Mohr", "2026-10-03")
    projeto = {"registros_tecnicos": [antigo, novo, vento, mohr], "esforcos_do_modelo": {"x": 1}}
    juntado, superados, ordem = mdp.juntar(projeto, fora=["circulo_mohr"])
    assert superados == 1 and ordem == [vento["id"], novo["id"]]
    por_id = {r["id"]: r for r in juntado["registros_tecnicos"]}
    assert por_id[antigo["id"]]["status"] == STATUS_SUPERADO
    assert por_id[antigo["id"]]["superado_por"] == novo["id"]
    assert juntado["configuracao_relatorio"]["registros_incluidos"] == ordem
    assert projeto["registros_tecnicos"][0]["status"] == "Calculado"  # o original não muda
    # As etapas do modelo sem registro aparecem para registrar; as outras só com registro.
    linhas = {l.etapa: l for l in mdp.quadro(juntado, fora=["circulo_mohr"])}
    assert linhas["Pilares"].calculos == 1 and linhas["Vento"].calculos == 1
    assert linhas["Verificação das barras"].situacao == "Falta registrar"
    assert linhas["Fundações"].pagina == "app_pages/reacoes_nas_bases.py"
    assert "Ligações" not in linhas and "Outros cálculos" not in linhas


def test_reacoes_nas_bases_no_memorial_com_os_desenhos():
    dados, apoios, geometria = montar()
    r = rb.montar(dados, apoios, plano=t.plano(), geometria=geometria)
    from core import cena_3d as c3
    from core import desenho_eixos_fundacao as de

    cena = de.cena_do_projeto(geometria, r)
    registro = rb.registro_das_reacoes(
        r,
        t.plano(),
        cena=c3.cena_para_dicionario(cena),
        legenda_da_cena=de.legenda_do_projeto(r),
    )
    assert registro["modulo_id"] == "reacoes_nas_bases"
    tabelas = registro["resultados"]["tabelas_memorial"]
    assert [tb["legenda"].split(" — ")[0] for tb in tabelas[1:3]] == [
        "AÇÃO DA ESTRUTURA NA FUNDAÇÃO",
        "REAÇÃO DO APOIO NA ESTRUTURA",
    ]
    assert len(tabelas[1]["linhas"]) == 4 * len(t.CASOS)
    projeto = {"id": "p", "codigo": "P-1", "nome": "teste", "registros_tecnicos": [registro]}
    modelo = montar_modelo_relatorio(projeto, registros_ids=[registro["id"]])
    capitulo = next(s for s in modelo["secoes"] if "Reações nas bases" in str(s.get("titulo", "")))
    titulos = [b.get("titulo") for b in capitulo.get("blocos", []) if b.get("tipo") == "imagem"]
    assert (
        "Sistema de coordenadas das reações nas bases" in titulos
        and "O projeto e os pés" in titulos
    )
    texto = texto_word(gerar_relatorio_industrial_word(projeto, registros_ids=[registro["id"]]))
    assert "AÇÃO DA ESTRUTURA NA FUNDAÇÃO" in texto and "REAÇÃO DO APOIO NA ESTRUTURA" in texto


def test_central_junta_o_projeto(banco_com_projeto):
    projeto = obter_projeto_ativo()
    for _ in range(3):
        adicionar_registro_tecnico(
            projeto["id"],
            _registro(
                "esforcos_modelo", "Quadro de cargas para as fundações — 4 pilar(es)", "2026-10-01"
            ),
        )
    adicionar_registro_tecnico(projeto["id"], registro_flambagem(3000.0, 150.0))
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    quadro = next(d.value for d in at.dataframe if "Etapa" in d.value.columns)
    fundacoes = quadro[quadro["Etapa"] == "Fundações"].iloc[0]
    assert fundacoes["No memorial"] == "1 cálculo(s) · 2 repetido(s) a tirar"
    botao = at.button(key="juntar_projeto")
    assert "tira 2 repetido(s)" in botao.label
    botao.click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    salvo = obter_projeto_ativo()
    quadros = [r for r in salvo["registros_tecnicos"] if r["titulo"].startswith("Quadro de cargas")]
    assert [r["status"] for r in quadros].count(STATUS_SUPERADO) == 2
    vigente = next(r["id"] for r in quadros if r["status"] != STATUS_SUPERADO)
    incluidos = salvo["configuracao_relatorio"]["registros_incluidos"]
    flambagem = next(
        r["id"] for r in salvo["registros_tecnicos"] if r["modulo_id"] == "flambagem_colunas"
    )
    assert vigente in incluidos and flambagem in incluidos
    assert incluidos.index(flambagem) < incluidos.index(vigente)  # pilares antes das fundações
    assert not any(r["id"] in incluidos for r in quadros if r["id"] != vigente)
    assert "tira" not in at.button(key="juntar_projeto").label
