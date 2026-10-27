"""O painel "Antes de verificar" (core/diagnostico_do_modelo.py): cada problema que o usuário teve
no teste01 (24/10) é achado, explicado e, quando dá, corrigido por botão."""

from __future__ import annotations

import pytest

from core import apoios_do_modelo as am
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto

PILARES = ("Viga-1(P1)", "Viga-2(P2)")
#: Reações (kN, eixos do modelo, Y para cima) e forças certas de cada caso.
REACOES = {
    "PP": (0.0, 3.0, 0.0),
    "SC": (0.0, 7.5, 0.0),
    "W0": (-1.82, 0.0, 0.0),
    "W90": (0.0, 0.0, 2.18),  # força −Z do modelo = +Y da planta
    "W180": (1.82, 0.0, 0.0),
    "W270": (0.0, 0.0, -2.18),
}


def _pontos(
    compressao: float, primeiro: int = 1, cortante: float = 0.0
) -> tuple[em.PontoDeEsforco, ...]:
    """Pilar de dois elementos com a base no início (a ponta mais comprimida)."""
    return (
        em.PontoDeEsforco(str(primeiro), "1", -compressao, cortante, 0, 0, 0, 0),
        em.PontoDeEsforco(str(primeiro), "2", -compressao * 0.9, cortante, 0, 0, 0, 0),
        em.PontoDeEsforco(str(primeiro + 1), "1", -compressao * 0.9, cortante, 0, 0, 0, 0),
        em.PontoDeEsforco(str(primeiro + 1), "2", -compressao * 0.8, cortante, 0, 0, 0, 0),
    )


def dados(
    reacoes: dict[str, tuple[float, float, float]] | None = None,
    compressao: dict[str, float] | None = None,
    primeiro_elemento: dict[str, int] | None = None,
) -> em.EsforcosDoModelo:
    reacoes = reacoes or REACOES
    compressao = compressao or {}
    primeiro_elemento = primeiro_elemento or {}
    casos = {}
    for codigo, r in reacoes.items():
        por_pilar = compressao.get(codigo, r[1] / 2)
        cortante = (r[0] + r[2]) / 2  # cada pilar leva metade do vento, com o sinal dele
        casos[codigo] = em.CasoImportado(
            codigo,
            "Análise estática 1",
            f"{codigo}-forcas.csv",
            "",
            "",
            {p: _pontos(por_pilar, primeiro_elemento.get(codigo, 1), cortante) for p in PILARES},
            reacoes=em.Reacoes(modelo=r),
            arquivo_reacoes=f"{codigo}-reacoes.csv",
        )
    return em.EsforcosDoModelo(
        casos=casos,
        membros={p: em.ConfiguracaoDoMembro("W 150 x 13,0", "Pilar") for p in PILARES},
        eixo_vertical="Y",
    )


def plano(*extras: pc.Acao) -> pc.PlanoDeCargas:
    p = pc.PlanoDeCargas()
    p = pc.com_acao(p, pc.nova_acao("PP"))
    p = pc.com_acao(
        p, pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 7.5, "kN", "Z (vertical)")])
    )
    for codigo, direcao, valor in (
        ("W0", "+X", 1.82),
        ("W90", "+Y", 2.18),
        ("W180", "−X", -1.82),
        ("W270", "−Y", -2.18),
    ):
        p = pc.com_acao(
            p, pc.nova_acao(codigo, cargas=[pc.CargaDoModelo("V", valor, "kN", direcao)])
        )
    for acao in extras:
        p = pc.com_acao(p, acao)
    return p


def _titulos(d: dm.Diagnostico) -> list[str]:
    return [a.titulo for a in d.achados]


# ------------------------------------------------------------------ cada problema
def test_tudo_certo():
    d = dm.diagnosticar(dados(), plano())
    assert d.tudo_certo and not d.achados
    assert any("W0, W90, W180 e W270" in c for c in d.certos)


def test_ventos_com_nomes_trocados_se_corrigem_por_botao():
    trocado = {**REACOES, "W90": REACOES["W270"], "W270": REACOES["W90"]}
    d = dm.diagnosticar(dados(trocado), plano())
    achado = next(a for a in d.achados if a.titulo == "Ventos com os nomes trocados")
    assert achado.nivel == dm.NIVEL_ERRO and achado.acao == dm.ACAO_TROCAR_NOMES
    assert achado.detalhe["mapa"] == {"W90": "W270", "W270": "W90"}
    assert "W90 → W270 e W270 → W90" in achado.problema
    apoios = am.ApoiosDoModelo(
        casos={
            "W90": am.ApoiosDoCaso("W90", "", "", (am.ReacaoNoNo(1, None, (0, 0, 1), (0, 0, 0)),))
        }
    )
    novos, apoios_novos = dm.corrigir_nomes(dados(trocado), apoios, achado.detalhe["mapa"])
    assert novos.casos["W270"].reacoes.modelo == REACOES["W270"]  # o W90 do estudo era o W270
    assert novos.casos["W270"].codigo == "W270" and "W90" not in apoios_novos.casos
    assert dm.diagnosticar(novos, plano()).tudo_certo


def test_vento_com_direcao_de_outro_caso_pede_correcao_no_solidworks():
    errado = {**REACOES, "W180": (0.0, 0.0, 1.82)}  # força −Z com o valor do vento em X
    d = dm.diagnosticar(dados(errado), plano())
    achado = next(a for a in d.achados if a.titulo.startswith("Ventos em direção"))
    assert achado.acao == "" and "só renomear não resolve" in achado.problema
    assert any("W180 da direita" in p for p in achado.passos)


def test_cargas_da_grade_no_plano_saem_por_botao():
    grade = pc.nova_acao(
        "PE",
        cargas=[pc.CargaDoModelo("N1 · eixo A · 1–2", 0.585, "kN/m", "Z (vertical)", "", 4, 6.0)],
    )
    d = dm.diagnosticar(dados(), plano(grade))
    achado = next(a for a in d.achados if a.acao == dm.ACAO_TIRAR_GRADE)
    assert achado.nivel == dm.NIVEL_ERRO and "PE" in achado.titulo
    assert dm.tirar_grade(plano(grade)).acao("PE").cargas == ()


def test_forcas_de_outra_rodada():
    d = dm.diagnosticar(dados(primeiro_elemento={"SC": 101}), plano())
    achado = next(a for a in d.achados if a.titulo.startswith("Forças de outra rodada"))
    assert achado.titulo.endswith("SC") and achado.detalhe["casos"] == ["SC"]
    assert any("duplo clique no caso SC" in p for p in achado.passos)


def test_forcas_do_estudo_base_no_lugar_do_caso():
    """O PP-forcas.csv do usuário levava PP + SC aos pilares: era o estudo base."""
    total = sum(r[1] for r in REACOES.values())
    d = dm.diagnosticar(dados(compressao={"PP": total / 2}), plano())
    achado = next(a for a in d.achados if a.titulo == "PP: as forças não são do caso PP")
    assert "estudo base" in achado.problema
    assert achado.passos[1] == "Dê duplo clique no caso PP (o gráfico tem de mudar para ele)."


def test_apoios_de_outra_rodada_e_sem_posicao():
    apoios = am.ApoiosDoModelo(
        casos={
            "W180": am.ApoiosDoCaso(
                "W180",
                "",
                "",
                (
                    am.ReacaoNoNo(1, (0.0, 0.0, 0.0), (0.0, 0.0, 910.0), (0, 0, 0)),
                    am.ReacaoNoNo(2, (0.0, 0.0, 0.0), (0.0, 0.0, 910.0), (0, 0, 0)),
                ),
            )
        }
    )
    d = dm.diagnosticar(dados(), plano(), apoios)
    achado = next(a for a in d.achados if a.titulo.startswith("Reação em cada apoio"))
    assert "W180" in achado.detalhe["outra_rodada"] and achado.detalhe["sem_posicao"] == ["W180"]


def test_diferenca_do_tamanho_de_uma_linha_do_plano_vira_pista():
    """O PE do usuário: guarda-corpo em 5 m no plano, 4 m no modelo (0,36 kN a mais)."""
    pe = pc.nova_acao(
        "PE",
        cargas=[
            pc.CargaDoModelo("Borda B1", 0.36, "kN/m", "Z (vertical)", "guarda-corpo B1", 1, 1.0),
            pc.CargaDoModelo("Borda B2", 0.36, "kN/m", "Z (vertical)", "guarda-corpo B2", 1, 1.5),
        ],
    )
    reacoes = {**REACOES, "PE": (0.0, 0.54, 0.0)}
    d = dm.diagnosticar(dados(reacoes), plano(pe))
    achado = next(a for a in d.achados if a.titulo == "PE: o modelo não recebeu a carga do plano")
    assert "é exatamente a linha “Borda B1”" in achado.problema


def test_casos_do_plano_sem_resultado_sao_informacao():
    d = dm.diagnosticar(dados(), plano(pc.nova_acao("T+", categoria=pc.CATEGORIA_TEMPERATURA)))
    achado = next(a for a in d.achados if a.titulo.startswith("Casos do plano sem resultado"))
    assert achado.nivel == dm.NIVEL_INFO and d.tudo_certo


def test_avisos_de_malha_viram_uma_linha_so():
    avisos = [
        f"Viga-{i}(P): a numeração dos elementos muda entre os estudos; combinei pela ordem. Use "
        "a mesma malha em todos os estudos (duplique o estudo)."
        for i in range(8)
    ] + ["outro aviso"]
    agrupados = em.agrupar_avisos(avisos)
    assert len(agrupados) == 2 and agrupados[0].startswith("8 barra(s) combinadas pela ordem")


# ------------------------------------------------------------------ página
def test_painel_na_pagina_e_o_botao_de_trocar_os_nomes(banco_com_projeto):
    from tests.test_esforcos_modelo_pagina import abrir, sem_ajuda

    trocado = {**REACOES, "W90": REACOES["W270"], "W270": REACOES["W90"]}
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(plano())
    # Com o B₂ informado, o painel não pede a segunda ordem e pode dizer "Tudo confere".
    projeto["esforcos_do_modelo"] = em.para_dicionario(
        em.com_parametros(dados(trocado), {"Pilar": em.ParametrosDoTipo(b2=1.1)})
    )
    salvar_projeto(projeto, motivo="teste")
    t = abrir()
    assert not sem_ajuda(t), sorted(sem_ajuda(t))
    assert "Antes de verificar: o que conferir" in [s.value for s in t.subheader]
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Para corrigir"] == "1"
    botao = next(b for b in t.button if b.key and b.key.startswith("em_diag_nomes_"))
    botao.click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    salvo = em.esforcos_do_projeto(obter_projeto_ativo())
    assert salvo.casos["W270"].reacoes.modelo == pytest.approx(REACOES["W270"])
    assert dm.diagnosticar(salvo, plano()).tudo_certo
    assert any("Tudo confere" in s.value for s in t.success)
