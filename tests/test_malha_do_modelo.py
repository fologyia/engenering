"""Ligação de cada viga do Simulation ao corpo do esqueleto pela posição (malha do estudo, macro v18).

O "Listar forças da viga" guarda o nome que o corpo tinha quando a viga foi criada no estudo:
renomear o corpo depois não muda esse nome, nem rodando o estudo de novo (visto no modelo do
usuário em 23/11/2026: ``Viga-1(Viga u VIGAS U VIGA U 6''_2ª ALMA(1)[1])`` nas forças e ``P-A1`` no
esqueleto — nenhuma barra achava o corpo, e o esqueleto inteiro era descartado). A malha diz onde
fica cada elemento, e os números dos elementos estão no arquivo de forças.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from core import esforcos_modelo as em
from core import gerenciador_solidworks as gs
from core import leitura_do_modelo as ld
from core import malha_do_modelo as mm
from core import plano_de_cargas as pc
from tests import dados_solidworks as sw
from tests.test_esforcos_modelo import importar, plano_do_portico

PILAR_1, VIGA, PILAR_2 = sw.BARRAS  # os nomes do Simulation (os antigos)
#: O mesmo pórtico com os corpos renomeados depois do estudo (sem a numeração [n]).
RENOMEADOS = {
    "P-A1": sw.CORPOS["Aparar/Estender12[1]"],
    "V-N1-A1-A2": sw.CORPOS["Canal c C8X13.75(1)[2]"],
    "P-A2": sw.CORPOS["Aparar/Estender12[2]"],
}
VERDADE = {PILAR_1: "P-A1", VIGA: "V-N1-A1-A2", PILAR_2: "P-A2"}


def esqueleto(corpos: dict) -> ld.GeometriaDoModelo:
    return ld.ler_esqueleto(sw.csv_esqueleto(corpos=corpos), "portico_esqueleto.csv")


def csv_da_malha(
    dados: em.EsforcosDoModelo,
    corpo_de: dict[str, str],
    *,
    corpos: dict = RENOMEADOS,
    escala: float = 1.0,
    desvio_m: float = 0.01,
    extras: int = 50,
) -> bytes:
    """O ``<estudo>-malha.csv`` da macro v18: o centro de cada elemento das vigas sobre o eixo do
    corpo dele (a ``desvio_m`` do eixo, como o centro da seção de um U) e ``extras`` elementos de
    outra coisa (chapa), em m vezes ``escala``."""
    linhas = [
        "sep=;",
        "14:12; 23/11/2026",
        "Nome do estudo:Análise estática 1",
        "Macro: Mecanica Toolkit - exportar_casos_de_carga v18",
        "",
        "Centros dos elementos da malha (como a malha devolve)",
        "Elemento;X;Y;Z",
    ]
    for viga, elementos in mm.elementos_dos_membros(dados).items():
        _, _, p1, p2, _ = corpos[corpo_de[viga]]
        for i, elemento in enumerate(elementos):
            t = (i + 0.5) / len(elementos)
            ponto = [(p1[k] + t * (p2[k] - p1[k])) / 1000.0 for k in range(3)]
            ponto[2] += desvio_m
            linhas.append(
                elemento + ";" + ";".join(f"{c * escala:.6f}".replace(".", ",") for c in ponto)
            )
    for i in range(extras):
        linhas.append(f"{90000 + i};{1.5 * escala:.4f};{2.0 * escala:.4f};{0.5 * escala:.4f}")
    return "\r\n".join(linhas).replace(".", ",").encode("cp1252")


def malha(dados: em.EsforcosDoModelo, corpo_de: dict[str, str] = VERDADE, **kwargs):
    return mm.ler_malha(csv_da_malha(dados, corpo_de, **kwargs), "Análise estática 1-malha.csv")


# ------------------------------------------------------------------ o arquivo
def test_le_o_arquivo_da_malha():
    dados = importar("PP")
    conteudo = csv_da_malha(dados, VERDADE)
    assert mm.e_arquivo_da_malha(conteudo)
    assert not mm.e_arquivo_da_malha(sw.csv_forcas_da_viga("PP"))
    assert ld.tipo_do_arquivo(conteudo) is None  # não é o esqueleto nem a lista de corte
    lida = mm.ler_malha(conteudo, "x-malha.csv")
    assert lida.estudo == "Análise estática 1"
    conferencia = mm.conferir(lida, dados)
    assert conferencia.serve and conferencia.completa and conferencia.vigas_com_posicao == 3
    guardada = mm.so_das_vigas(lida, dados)
    assert len(guardada.centros) == conferencia.elementos  # sem os elementos da chapa
    assert mm.de_dicionario(mm.para_dicionario(guardada)) == guardada


@pytest.mark.parametrize(
    ("conteudo", "trecho"),
    [
        (b"sep=;\r\nCentros dos elementos da malha\r\n", "linha das colunas"),
        (b"Centros dos elementos da malha\r\nElemento;X;Y;Z\r\n1;a;b;c\r\n", "nenhum elemento"),
        (
            b"Centros dos elementos da malha\r\nElemento;X;Y;Z\r\n1;0;0;0\r\n2;0;0;0\r\n",
            "mesmo ponto",
        ),
    ],
)
def test_arquivo_da_malha_estragado(conteudo, trecho):
    with pytest.raises(mm.MalhaInvalida, match=trecho):
        mm.ler_malha(conteudo, "x-malha.csv")


@pytest.mark.parametrize("gravado", [None, {}, {"centros": {"1": [0, "x", 0], "a": [1, 2, 3]}}])
def test_malha_gravada_estragada_nao_quebra(gravado):
    assert mm.de_dicionario(gravado).vazia


# ------------------------------------------------------------------ a ligação
def test_corpos_renomeados_sem_malha_nao_acham_o_corpo():
    """O caso do usuário: sem a malha, o nome não serve e o esqueleto vira "de outro modelo"."""
    dados = importar("PP", "SC")
    g = esqueleto(RENOMEADOS)
    assert not ld.correspondencia(g, dados.nomes_dos_membros, dados).corpos
    assert ld.esqueleto_de_outro_modelo(g, dados)
    erro = next(
        a
        for a in ld.diagnosticar(dados, plano_do_portico(), g)
        if a.titulo == "Esqueleto de outro modelo"
    )
    assert "-malha.csv" in erro.texto and "renomeados" in erro.texto


@pytest.mark.parametrize("escala", [1.0, 1000.0])
def test_com_a_malha_cada_viga_acha_o_corpo_pela_posicao(escala):
    dados = importar("PP", "SC")
    g = ld.com_malha(esqueleto(RENOMEADOS), mm.so_das_vigas(malha(dados, escala=escala), dados))
    casamento = ld.correspondencia(g, dados.nomes_dos_membros, dados)
    assert {v: c.nome for v, c in casamento.corpos.items()} == VERDADE
    assert set(casamento.pelas_coordenadas) == set(VERDADE)
    assert not ld.esqueleto_de_outro_modelo(g, dados)
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    assert leituras[PILAR_1].comprimento_m == pytest.approx(4.0)
    assert leituras[VIGA].comprimento_m == pytest.approx(6.0)
    assert leituras[VIGA].tipo_sugerido == ld.TIPO_VIGA
    assert leituras[PILAR_2].tipo_sugerido == ld.TIPO_PILAR
    titulos = {
        a.titulo
        for a in ld.diagnosticar(dados, plano_do_portico(), g, leituras=list(leituras.values()))
    }
    assert "Barras ligadas pela posição" in titulos and "Esqueleto de outro modelo" not in titulos


def test_a_posicao_vale_mais_que_um_nome_que_engana():
    """Os nomes do Simulation existem no esqueleto, mas trocados de lugar (os dois pilares): vale
    onde cada elemento está, não o nome."""
    dados = importar("PP")
    trocados = {
        "Aparar/Estender12[1]": sw.CORPOS["Aparar/Estender12[2]"],
        "Canal c C8X13.75(1)[2]": sw.CORPOS["Canal c C8X13.75(1)[2]"],
        "Aparar/Estender12[2]": sw.CORPOS["Aparar/Estender12[1]"],
    }
    pelo_lugar = {
        PILAR_1: "Aparar/Estender12[2]",
        VIGA: "Canal c C8X13.75(1)[2]",
        PILAR_2: "Aparar/Estender12[1]",
    }
    g = esqueleto(trocados)
    pelo_nome = ld.correspondencia(g, dados.nomes_dos_membros, dados).corpos
    assert pelo_nome[PILAR_1].nome == "Aparar/Estender12[1]"  # sem a malha, o nome manda
    g = ld.com_malha(g, malha(dados, pelo_lugar, corpos=trocados))
    casados = ld.correspondencia(g, dados.nomes_dos_membros, dados).corpos
    assert {v: c.nome for v, c in casados.items()} == pelo_lugar


def test_malha_de_outro_modelo_nao_liga_nada():
    """Elementos que não caem sobre corpo nenhum (outro modelo, malha refeita): nenhuma ligação
    pela posição — e o aviso diz quais barras ficaram de fora."""
    dados = importar("PP")
    longe = {
        nome: (i, d, (p1[0] + 5000, p1[1], p1[2]), (p2[0] + 5000, p2[1], p2[2]), perfil)
        for nome, (i, d, p1, p2, perfil) in RENOMEADOS.items()
    }
    g = ld.com_malha(esqueleto(RENOMEADOS), malha(dados, corpos=longe))
    assert not ld.casar_pela_malha(g, dados)
    assert ld.esqueleto_de_outro_modelo(g, dados)
    erro = next(
        a
        for a in ld.diagnosticar(dados, plano_do_portico(), g)
        if a.titulo == "Esqueleto de outro modelo"
    )
    assert "malha" in erro.texto


def test_viga_que_ocupa_so_um_pedaco_do_corpo_nao_e_dele():
    """Os elementos de uma viga de 1 m sobre um corpo de 6 m: não é esse corpo."""
    dados = importar("PP")
    curtos = dict(RENOMEADOS)
    curtos["V-N1-A1-A2"] = ("x", "W 310 x 32,7", (0, sw.H, 0), (1000, sw.H, 0), "W 310 x 32,7")
    g = ld.com_malha(esqueleto(RENOMEADOS), malha(dados, corpos=curtos))
    casados = ld.casar_pela_malha(g, dados)
    assert VIGA not in casados and casados[PILAR_1].nome == "P-A1"


def test_cada_corpo_serve_a_uma_viga_so():
    dados = importar("PP")
    todos_no_pilar = {PILAR_1: "P-A1", VIGA: "V-N1-A1-A2", PILAR_2: "P-A1"}
    g = ld.com_malha(esqueleto(RENOMEADOS), malha(dados, todos_no_pilar))
    casados = ld.casar_pela_malha(g, dados)
    assert [v for v, c in casados.items() if c.nome == "P-A1"] in ([PILAR_1], [PILAR_2])


def test_malha_gravada_no_projeto_chega_na_geometria():
    dados = importar("PP")
    projeto = {
        "geometria_do_modelo": ld.para_dicionario(esqueleto(RENOMEADOS)),
        mm.CAMPO_DO_PROJETO: mm.para_dicionario(mm.so_das_vigas(malha(dados), dados)),
    }
    g = ld.geometria_do_projeto(projeto)
    assert g.centros_da_malha
    assert len(ld.correspondencia(g, dados.nomes_dos_membros, dados).corpos) == 3


# ------------------------------------------------------------------ a macro
def test_a_macro_grava_a_malha():
    texto = gs.macro_dos_casos_de_carga()
    for trecho in (
        b'VERSAO_DA_MACRO As String = "v18"',
        b"malha.GetElements()",
        b"malha.GetElementLocation(",
        b"Centros dos elementos da malha (como a malha devolve)",
        b"Elemento;X;Y;Z",
        b'"-malha"',
        b"Dim malha As CosmosWorksLib.CWMesh",  # pelo Object as saidas ByRef nao voltam
    ):
        assert trecho in texto, trecho
    # O título que a macro escreve é o que o programa reconhece.
    assert mm.e_arquivo_da_malha(b"Centros dos elementos da malha (como a malha devolve)")


# ------------------------------------------------------------------ a página
def test_pagina_mostra_as_barras_com_o_esqueleto_pela_malha(banco_com_projeto):
    from core.project_store import obter_projeto_ativo, salvar_projeto

    dados = importar("PP", "SC", "W0", "W180")
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(plano_do_portico())
    projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    projeto["geometria_do_modelo"] = ld.para_dicionario(esqueleto(RENOMEADOS))
    projeto[mm.CAMPO_DO_PROJETO] = mm.para_dicionario(mm.so_das_vigas(malha(dados), dados))
    salvar_projeto(projeto, motivo="teste")
    t = AppTest.from_file(str(sw_app()), default_timeout=180)
    t.run()
    t.switch_page("app_pages/esforcos_modelo.py")
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    barras = next(d.value for d in t.dataframe if "Tipo sugerido" in d.value.columns)
    assert list(barras["Comprimento (m)"]) == pytest.approx([4.0, 6.0, 4.0])
    assert list(barras["Tipo sugerido"]) == ["Pilar", "Viga", "Pilar"]
    textos = " ".join(s.value for s in t.success) + " ".join(m.value for m in t.markdown)
    assert "Esqueleto de outro modelo" not in textos


def sw_app():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "app.py"
