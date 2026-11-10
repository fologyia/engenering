"""Quadro de cargas para as fundações a partir das forças das vigas do SolidWorks."""

from __future__ import annotations

import io
import json

import pytest
from openpyxl import load_workbook

from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core.project_report import montar_modelo_relatorio
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro
from tests import dados_solidworks as sw
from tests.test_esforcos_modelo import PILAR, importar, plano_do_portico

PILAR_2 = "Viga-3(Aparar/Estender12[2])"


def portico(*pilares: str, base: str = em.BASE_INICIO) -> em.EsforcosDoModelo:
    dados = importar("PP", "SC", "W0", "W180")
    return em.com_membros(
        dados, {p: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", base=base) for p in pilares}
    )


def _manual(primeiro: float, ultimo: float) -> dict[str, tuple[em.PontoDeEsforco, ...]]:
    return {
        "PP": (
            em.PontoDeEsforco("1", "1", primeiro, 0, 0, 0, 0, 0),
            em.PontoDeEsforco("2", "2", ultimo, 0, 0, 0, 0, 0),
        )
    }


@pytest.mark.parametrize(
    ("primeiro", "ultimo", "base"),
    [(-80.0, -20.0, em.BASE_INICIO), (-20.0, -80.0, em.BASE_FIM), (-50.0, -50.0, None)],
)
def test_base_automatica_e_a_ponta_mais_comprimida(primeiro, ultimo, base):
    achada, origem = qf.ponta_da_base(_manual(primeiro, ultimo), em.BASE_AUTOMATICA)
    assert achada == base
    assert ("escolha a base" in origem) is (base is None)


def test_base_escolhida_vale_mesmo_com_compressao_igual():
    assert qf.ponta_da_base(_manual(-50, -50), em.BASE_FIM) == (em.BASE_FIM, "escolhida")


def test_quadro_do_portico_bate_com_as_reacoes():
    quadro = qf.montar_quadro(portico(PILAR, PILAR_2))
    assert [p.pilar for p in quadro.pilares] == [PILAR, PILAR_2]
    sc_pilar = next(c for c in quadro.pilares[0].cargas if c.caso == "SC")
    resultado = sw.resolver("SC")
    reacao = next(r for r in resultado.reacoes_nodais if r["no"] == 1)
    assert sc_pilar.n == pytest.approx(float(reacao["ry_N"]) / 1e3)  # 30 kN de compressão
    assert abs(sc_pilar.m2) == pytest.approx(abs(float(reacao["mz_Nmm"])) / 1e6, rel=1e-4)
    w0 = next(c for c in quadro.pilares[0].cargas if c.caso == "W0")
    assert w0.n < 0  # o vento para +X levanta o pilar de barlavento
    textos = " ".join(i.texto for i in quadro.conferencia)
    assert "SC: a soma das bases (60,00 kN) bate com a reação vertical do modelo" in textos
    assert all(i.nivel == pc.NIVEL_OK for i in quadro.conferencia)


def test_conferencia_avisa_quando_falta_pilar_ou_base():
    so_um = qf.montar_quadro(portico(PILAR))
    assert any("há apoios que não são base de pilar marcado" in i.texto for i in so_um.conferencia)
    sem_base = qf.montar_quadro(portico(PILAR, base=em.BASE_AUTOMATICA))
    assert sem_base.pendentes and any("Escolha a base" in i.texto for i in sem_base.conferencia)
    nenhum = qf.montar_quadro(importar("PP"))
    assert "Nenhuma barra marcada como Pilar" in nenhum.conferencia[0].texto


def test_matriz_csv_excel_e_registro():
    quadro = qf.montar_quadro(portico(PILAR, PILAR_2))
    plano = plano_do_portico()
    cabecalho, linhas = qf.matriz_de_compressao(quadro)
    assert cabecalho == ["Pilar", "PP", "SC", "W0", "W180"]
    assert linhas[0][2] == pytest.approx(30.0)
    assert qf.csv_do_quadro(quadro, plano).decode("utf-8-sig").splitlines()[0].split(";") == list(
        qf.COLUNAS
    )
    livro = load_workbook(io.BytesIO(qf.xlsx_do_quadro(quadro, plano, titulo="Teste")))
    assert livro.sheetnames == ["Leia-me", "Quadro", "Compressão por pilar"]
    assert "5.9" in " ".join(str(c.value) for c in livro["Leia-me"]["A"] if c.value)
    assert len(list(livro["Quadro"].values)) == 1 + 2 * 4
    registro = qf.registro_do_quadro(quadro, plano)
    assert avaliar_contrato_registro(registro)["valido"]
    json.dumps(registro)
    assert "sem combinar nem majorar" in registro["resultados"]["destaque_memorial"]
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto["registros_tecnicos"] = [registro]
    capitulo = next(s for s in montar_modelo_relatorio(projeto)["secoes"] if "blocos" in s)
    assert capitulo["blocos"][0]["rotulo"] == "Resultado do cálculo."
    legendas = " ".join(b.get("legenda", "") for b in capitulo["blocos"])
    assert "Compressão (N, kN) na base de cada pilar" in legendas


def test_base_vai_e_volta_pelo_projeto():
    dados = portico(PILAR, base=em.BASE_FIM)
    volta = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados))))
    assert volta.membros[PILAR].base == em.BASE_FIM
    estranho = em.para_dicionario(dados)
    estranho["membros"][PILAR]["base"] = "qualquer"
    assert em.de_dicionario(estranho).membros[PILAR].base == em.BASE_AUTOMATICA


# ------------------------------------------------------------------ a base pelo peso próprio
#: Quatro pilares como os da escada marinheiro (10/11): listados de cima para baixo, com as vigas
#: entregando carga no meio da altura e o vento aplicado nos nós. Compressão (kN) no trecho de
#: cima e no de baixo de cada pilar; negativo = tração.
ESCADA = {
    "PP": {"P1": (0.46, 0.72), "P2": (0.46, 0.72), "P3": (0.46, 0.72), "P4": (0.46, 0.72)},
    "SC": {"P1": (2.5, 2.5), "P2": (2.5, 2.5), "P3": (2.5, 2.5), "P4": (2.5, 2.5)},
    "W0": {"P1": (-0.6, -3.05), "P2": (0.6, 3.05), "P3": (-0.6, -3.05), "P4": (0.6, 3.05)},
    "W180": {"P1": (0.6, 3.05), "P2": (-0.6, -3.05), "P3": (0.6, 3.05), "P4": (-0.6, -3.05)},
}
PESO_DO_PILAR = 0.34  # kN, só no PP
HORIZONTAL = {"W0": -3.66, "W180": 3.66}


def _pilar(
    cima: float, baixo: float, peso: float = 0.0, *, de_baixo_para_cima: bool = False
) -> tuple[em.PontoDeEsforco, ...]:
    """Quatro elementos listados de cima para baixo (ou ao contrário); o peso entra dentro dos
    elementos e a carga das vigas, no nó do meio."""
    pontos = []
    for k, compressao in enumerate((cima, cima, baixo, baixo)):
        em_cima = -(compressao + peso * k / 4)
        em_baixo = -(compressao + peso * (k + 1) / 4)
        pontos.append(em.PontoDeEsforco(str(k + 1), "1", em_cima, 0.9, 0, 0, 0, 0))
        pontos.append(em.PontoDeEsforco(str(k + 1), "2", em_baixo, 0.9, 0, 0, 0, 0))
    if de_baixo_para_cima:
        pontos = [
            em.PontoDeEsforco(p.elemento, "2" if p.fim == "1" else "1", p.n, p.v1, 0, 0, 0, 0)
            for p in reversed(pontos)
        ]
    return tuple(pontos)


def escada(
    casos: tuple[str, ...] = tuple(ESCADA),
    *,
    viradas: tuple[str, ...] = (),
    base: dict[str, str] | None = None,
    com_reacoes: bool = True,
) -> em.EsforcosDoModelo:
    importados = {}
    for codigo in casos:
        peso = PESO_DO_PILAR if codigo == "PP" else 0.0
        vertical = sum(baixo + peso for _, baixo in ESCADA[codigo].values())
        importados[codigo] = em.CasoImportado(
            codigo,
            "Análise estática 1",
            f"{codigo}-forcas.csv",
            "",
            "",
            {
                p: _pilar(cima, baixo, peso, de_baixo_para_cima=p in viradas)
                for p, (cima, baixo) in ESCADA[codigo].items()
            },
            reacoes=em.Reacoes(modelo=(HORIZONTAL.get(codigo, 0.0), vertical, 0.0))
            if com_reacoes
            else None,
        )
    return em.EsforcosDoModelo(
        casos=importados,
        membros={
            p: em.ConfiguracaoDoMembro(
                'U 6" x 12,20', "Pilar", base=(base or {}).get(p, em.BASE_AUTOMATICA)
            )
            for p in ESCADA["PP"]
        },
        eixo_vertical="Y",
    )


def test_base_pelo_peso_proprio_e_nao_pelo_vento_que_traciona():
    """O defeito de 10/11: no vento o pilar de barlavento é tracionado e a maior força fica na
    base com o sinal trocado — a "ponta mais comprimida" do caso de maior diferença era o topo."""
    quadro = qf.montar_quadro(escada(viradas=("P3",)))
    bases = {p.pilar: p.base for p in quadro.pilares}
    assert bases == {"P1": em.BASE_FIM, "P2": em.BASE_FIM, "P3": em.BASE_INICIO, "P4": em.BASE_FIM}
    assert {p.origem_da_base for p in quadro.pilares} == {qf.ORIGEM_PESO}
    assert all(i.nivel == pc.NIVEL_OK for i in quadro.conferencia), quadro.conferencia
    w0 = {p.pilar: next(c.n for c in p.cargas if c.caso == "W0") for p in quadro.pilares}
    assert w0 == pytest.approx({"P1": -3.05, "P2": 3.05, "P3": -3.05, "P4": 3.05})
    pp = {p.pilar: next(c.n for c in p.cargas if c.caso == "PP") for p in quadro.pilares}
    assert pp == pytest.approx(dict.fromkeys(ESCADA["PP"], 0.72 + PESO_DO_PILAR))
    assert not quadro.pendentes and not quadro.de_ponta_cabeca
    assert [linha[3] for linha in qf.linhas_das_bases(quadro)] == ["Certo"] * 4


def test_casos_de_gravidade_sao_o_pp_e_os_de_reacao_so_vertical():
    assert qf.casos_de_gravidade(escada()) == ("PP", "SC")
    assert qf.casos_de_gravidade(escada(("W0", "SC", "PP"))) == ("PP", "SC")
    assert qf.casos_de_gravidade(escada(("W0", "W180"))) == ()


def test_so_com_vento_o_programa_nao_adivinha_a_base():
    # Só ventos: nenhuma ponta sai do peso, e com os pilares simétricos várias combinações de
    # pontas fecham a soma — o programa pede a escolha, com o motivo.
    for dados in (escada(("W0", "W180")), escada(("W0", "W180"), com_reacoes=False)):
        quadro = qf.montar_quadro(dados)
        assert len(quadro.pendentes) == 4
        assert {p.origem_da_base for p in quadro.pendentes} == {qf.SEM_GRAVIDADE}
        assert any("Escolha a base de 4 pilar(es)" in i.texto for i in quadro.conferencia)
    pontos = {"W0": _pilar(-0.6, -3.05)}
    assert qf.ponta_da_base(pontos, em.BASE_AUTOMATICA, ()) == (None, qf.SEM_GRAVIDADE)


def test_sem_peso_no_pilar_vale_a_ponta_mais_comprimida_do_caso_vertical():
    quadro = qf.montar_quadro(escada(("SC", "W0")))
    # No SC as duas pontas têm 2,5 kN: não dá para saber.
    assert {p.origem_da_base for p in quadro.pilares} == {qf.MESMA_COMPRESSAO}
    pontos = {"SC": _pilar(1.0, 2.5), "W0": _pilar(-0.6, -3.05)}
    assert qf.ponta_da_base(pontos, em.BASE_AUTOMATICA, ("SC",)) == (
        em.BASE_FIM,
        qf.ORIGEM_GRAVIDADE,
    )


def _estudo_unico(pilares: dict[str, tuple[em.PontoDeEsforco, ...]], vertical: float):
    caso = em.CasoImportado(
        "C1", "Tudo", "C1.csv", "", "", pilares, reacoes=em.Reacoes(modelo=(4.0, vertical, 0.0))
    )
    return em.EsforcosDoModelo(
        casos={"C1": caso},
        membros={p: em.ConfiguracaoDoMembro(tipo="Pilar") for p in pilares},
        eixo_vertical="Y",
    )


def test_estudo_unico_com_gravidade_e_vento_acha_a_base_pelo_peso():
    # Um caso só, com tudo ligado (reação horizontal grande): não é "de gravidade", mas o peso
    # dentro dos elementos do pilar continua apontando para baixo.
    dados = _estudo_unico(
        {"P1": _pilar(-0.6, -3.05, 0.34), "P2": _pilar(0.6, 3.05, 0.34, de_baixo_para_cima=True)},
        vertical=0.68,
    )
    assert qf.casos_de_gravidade(dados) == () and qf.casos_com_gravidade(dados) == ("C1",)
    quadro = qf.montar_quadro(dados)
    assert [p.base for p in quadro.pilares] == [em.BASE_FIM, em.BASE_INICIO]
    assert {p.origem_da_base for p in quadro.pilares} == {qf.ORIGEM_PESO}


def test_sem_peso_a_soma_das_bases_decide_quando_so_uma_combinacao_fecha():
    dados = _estudo_unico({"P1": _pilar(1.0, 3.0), "P2": _pilar(2.0, 2.0)}, vertical=5.0)
    quadro = qf.montar_quadro(dados)
    p1, p2 = quadro.pilares
    assert (p1.base, p1.origem_da_base) == (em.BASE_FIM, qf.ORIGEM_SOMA)
    assert p2.base is None  # as duas pontas fecham: o programa não adivinha


def test_o_arredondamento_do_arquivo_nao_vira_peso_proprio():
    # 100 kN com cinco algarismos: ±0,005 kN por valor não é peso do pilar.
    pontos = tuple(
        em.PontoDeEsforco(str(k), fim, -100.0 - 0.004 * (int(fim) % 2), 0, 0, 0, 0, 0)
        for k in range(1, 9)
        for fim in ("1", "2")
    )
    assert qf._pelo_peso_nos_elementos(pontos) is None
    assert qf._pelo_peso_nos_elementos(_pilar(100.0, 100.0, 0.5)) == em.BASE_FIM
    assert qf._pelo_peso_nos_elementos(_pilar(1.0, 1.0)) is None


def test_base_escolhida_na_ponta_de_cima_e_avisada_e_corrigida():
    from core import diagnostico_do_modelo as dm

    dados = escada(base={"P1": em.BASE_INICIO, "P2": em.BASE_FIM})
    quadro = qf.montar_quadro(dados)
    assert [p.pilar for p in quadro.de_ponta_cabeca] == ["P1"]
    assert quadro.pilares[0].base == em.BASE_INICIO  # a escolha fica, com o aviso
    assert any("é a ponta de cima em 1 pilar(es) — P1" in i.texto for i in quadro.conferencia)
    assert "Ponta de cima" in qf.linhas_das_bases(quadro)[0][3]
    diagnostico = dm.diagnosticar(dados, pc.PlanoDeCargas())
    achado = next(a for a in diagnostico.achados if a.acao == dm.ACAO_BASES_AUTOMATICAS)
    assert achado.nivel == dm.NIVEL_ERRO and achado.detalhe["pilares"] == ["P1"]
    # O erro é da escolha: os arquivos de forças não levam a culpa.
    assert not any("as forças não são do caso" in a.titulo for a in diagnostico.achados)
    corrigido = dm.bases_automaticas(dados, achado.detalhe["pilares"])
    assert corrigido.membros["P1"].base == em.BASE_AUTOMATICA
    assert corrigido.membros["P2"].base == em.BASE_FIM  # a escolha certa não muda
    depois = qf.montar_quadro(corrigido)
    assert not depois.de_ponta_cabeca
    assert all(i.nivel == pc.NIVEL_OK for i in depois.conferencia)
    assert not any(
        a.acao == dm.ACAO_BASES_AUTOMATICAS
        for a in dm.diagnosticar(corrigido, pc.PlanoDeCargas()).achados
    )


def test_base_sem_definicao_vira_achado_do_painel():
    from core import diagnostico_do_modelo as dm

    diagnostico = dm.diagnosticar(escada(("W0", "W180"), com_reacoes=False), pc.PlanoDeCargas())
    achado = next(a for a in diagnostico.achados if a.titulo == "Base do pilar sem definição")
    assert achado.nivel == dm.NIVEL_ATENCAO and len(achado.detalhe["pilares"]) == 4
    assert any("PP" in passo for passo in achado.passos)


def test_as_forcas_certas_nao_viram_erro_de_arquivo_no_painel():
    from core import diagnostico_do_modelo as dm

    diagnostico = dm.diagnosticar(escada(viradas=("P2", "P4")), pc.PlanoDeCargas())
    titulos = [a.titulo for a in diagnostico.achados]
    assert not any("as forças" in t for t in titulos), titulos
    assert not any(t.startswith("Base do pilar") for t in titulos), titulos
