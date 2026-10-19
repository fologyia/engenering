"""Leitura do modelo: o que o programa entende dos arquivos do SolidWorks e o que parece errado."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import plano_de_cargas as pc
from tests import dados_solidworks as sw
from tests.test_esforcos_modelo import PILAR, VIGA, importar, plano_do_portico

PILAR_2 = "Viga-3(Aparar/Estender12[2])"
TODOS = ("PP", "SC", "W0", "W180")
CODIGOS = ["PP", "SC", "W0", "W180"]


def outros_avisos(g: ld.GeometriaDoModelo) -> tuple[str, ...]:
    """Os avisos do esqueleto sem o do nome × seção: no pórtico do exemplo, o corpo da viga se
    chama "Canal c C8X13.75" e tem a seção do W 310 × 32,7 (o aviso é de propósito)."""
    return tuple(a for a in g.avisos if not a.startswith("Nome do membro"))


def geometria(**kwargs) -> ld.GeometriaDoModelo:
    return ld.ler_esqueleto(sw.csv_esqueleto(**kwargs), "portico_esqueleto.csv")


def geometria_que_pesa(peso_kN: float) -> ld.GeometriaDoModelo:
    """O esqueleto do pórtico com o volume ajustado para o aço pesar ``peso_kN``."""
    return geometria(escala_do_volume=peso_kN / sw.peso_do_esqueleto_kN())


def geometria_coerente() -> ld.GeometriaDoModelo:
    """O esqueleto que bate com o PP do exemplo: no PP só a viga tem carga (1,5 kN/m, o "peso"
    dela) e os pilares não pesam nada — então a viga pesa 1,5 kN/m e os pilares, quase zero."""
    volume_da_viga = 1.5 * 6.0 * 1e3 / 9.80665 / 7850.0 * 1e6  # cm³
    return geometria(
        volumes_cm3={
            "Canal c C8X13.75(1)[2]": volume_da_viga,
            "Aparar/Estender12[1]": 1.0,
            "Aparar/Estender12[2]": 1.0,
        }
    )


def caso_manual(codigo: str, membros: dict) -> em.CasoImportado:
    return em.CasoImportado(codigo, codigo, f"{codigo}.csv", "", "", membros)


def ponto(elemento: str, fim: str, n=0.0, v1=0.0, m2=0.0) -> em.PontoDeEsforco:
    return em.PontoDeEsforco(elemento, fim, n, v1, 0.0, 0.0, m2, 0.0)


def titulos(achados: list[ld.Achado]) -> dict[str, str]:
    return {a.titulo: a.nivel for a in achados}


def achado(achados: list[ld.Achado], titulo: str) -> ld.Achado:
    return next(a for a in achados if a.titulo == titulo)


# ------------------------------------------------------------------ arquivos da macro
def test_reconhece_os_arquivos_da_macro():
    assert ld.tipo_do_arquivo(sw.csv_esqueleto()) == ld.TIPO_ESQUELETO
    lista = "QTD.;DESCRIÇÃO;COMPRIMENTO (mm)\r\n2;W 200 x 35,9 (H);4000".encode("cp1252")
    assert ld.tipo_do_arquivo(lista) == ld.TIPO_LISTA_DE_CORTE
    assert ld.tipo_do_arquivo(sw.csv_forcas_da_viga("PP")) is None
    assert ld.tipo_do_arquivo(sw.csv_reacoes("PP")) is None
    assert ld.tipo_do_arquivo(b"") is None
    assert ld.tipo_do_arquivo(b"\x00\xff\xfe lixo") is None


@pytest.mark.parametrize("decimal", [",", "."])
def test_le_o_esqueleto_em_metros(decimal):
    g = geometria(decimal=decimal)
    assert [c.nome for c in g.corpos] == list(sw.CORPOS)
    pilar = g.corpo("Aparar/Estender12[1]")
    assert pilar is not None
    assert pilar.inicio == (0.0, 0.0, 0.0) and pilar.fim == pytest.approx((0.0, 4.0, 0.0))
    assert pilar.comprimento_m == pytest.approx(4.0)
    assert pilar.item == "W8x31<1>" and pilar.descricao == "W8x31"
    # Área da seção pelo volume da macro: a do W 200 × 35,9 (45,7 cm²).
    assert pilar.area_mm2 == pytest.approx(4570, rel=2e-3)
    assert g.arquivo == "portico_esqueleto.csv" and g.importado_em


def test_esqueleto_sem_volume_ainda_le():
    g = geometria(com_volume=False)
    assert len(g.corpos) == 3
    assert all(c.volume_m3 is None and c.area_mm2 is None for c in g.corpos)
    assert ld.peso_do_esqueleto_kN(g) is None


@pytest.mark.parametrize(
    ("conteudo", "trecho"),
    [
        (b"", "vazio"),
        (b"CORPO;X1 (mm)\r\nA;0", "coluna"),
        (
            b"CORPO;ITEM;DESCRICAO;X1;Y1;Z1;X2;Y2;Z2;COMPRIMENTO\r\nA;i;d;a;b;c;d;e;f;g",
            "Nenhum corpo",
        ),
    ],
)
def test_esqueleto_fora_do_formato(conteudo, trecho):
    with pytest.raises(ld.GeometriaInvalida, match=trecho):
        ld.ler_esqueleto(conteudo, "x.csv")


def test_esqueleto_na_lista_de_material_manda_para_a_pagina_certa():
    with pytest.raises(lm.ListaDeCorteInvalida, match="Esforços do modelo"):
        lm.ler_lista_de_corte(sw.csv_esqueleto(), "portico_esqueleto.csv")


def test_esqueleto_gravado_ida_e_volta():
    g = geometria()
    gravado = json.loads(json.dumps(ld.para_dicionario(g)))
    lido = ld.geometria_do_projeto({"geometria_do_modelo": gravado})
    assert [c.nome for c in lido.corpos] == [c.nome for c in g.corpos]
    for a, b in zip(lido.corpos, g.corpos, strict=True):
        assert a.inicio == pytest.approx(b.inicio) and a.fim == pytest.approx(b.fim)
        assert a.comprimento_m == pytest.approx(b.comprimento_m)
        assert a.volume_m3 == pytest.approx(b.volume_m3)
    assert lido.arquivo == g.arquivo


@pytest.mark.parametrize(
    "gravado",
    [
        None,
        [],
        "texto",
        {"corpos": "x"},
        {"corpos": [[1, 2]]},
        {"corpos": [["a", "b", "c", "x", 0, 0, 0, 0, 0, 1]]},
        {"corpos": [["a", "b", "c", 0, 0, 0, 0, 0, 0, 0]]},
        {"corpos": [["a", "b", "c", 0, 0, 0, 0, float("nan"), 0, 1]]},
        {"corpos": [None, 3, {"a": 1}]},
    ],
)
def test_esqueleto_gravado_corrompido_nao_quebra(gravado):
    assert ld.de_dicionario(gravado).corpos == ()
    assert ld.geometria_do_projeto({"geometria_do_modelo": gravado}).corpos == ()


def test_volume_gravado_invalido_vira_sem_volume():
    linha = ["a", "b", "c", 0, 0, 0, 0, 4, 0, 4, "lixo"]
    (corpo,) = ld.de_dicionario({"corpos": [linha]}).corpos
    assert corpo.volume_m3 is None and corpo.comprimento_m == 4


# ------------------------------------------------------------------ corpo de cada viga
@pytest.mark.parametrize(
    ("viga", "corpo"),
    [
        ("Viga-2(Canal c C8X13.75(1)[2])", "Canal c C8X13.75(1)[2]"),
        ("Viga-1(Aparar/Estender12[1])", "Aparar/Estender12[1]"),
        ("Sem parênteses", "Sem parênteses"),
    ],
)
def test_nome_do_corpo(viga, corpo):
    assert ld.nome_do_corpo(viga) == corpo


def test_acha_o_corpo_mesmo_com_espacos_e_acentos_diferentes():
    g = geometria()
    assert ld.corpo_da_viga(g, PILAR).nome == "Aparar/Estender12[1]"
    assert ld.corpo_da_viga(g, "Viga-7( Aparar/Estender12 [1] )").nome == "Aparar/Estender12[1]"
    assert ld.corpo_da_viga(g, "Viga-8(Outro corpo)") is None


@pytest.mark.parametrize(
    ("inicio", "fim", "eixo", "tipo", "trecho"),
    [
        ((0, 0, 0), (0, 4, 0), "Y", ld.TIPO_PILAR, "vertical"),
        ((0, 0, 0), (0.3, 4, 0), "Y", ld.TIPO_PILAR, "vertical"),  # 4° fora do prumo
        ((0, 4, 0), (6, 4, 0), "Y", ld.TIPO_VIGA, "horizontal"),
        ((0, 4, 0), (0, 4, 6), "Y", ld.TIPO_VIGA, "horizontal"),
        ((0, 4, 0), (6, 4, 3), "Y", ld.TIPO_CONTRAVENTAMENTO, "diagonal em planta"),
        ((0, 0, 0), (4, 4, 0), "Y", ld.TIPO_CONTRAVENTAMENTO, "inclinada 45°"),
        ((0, 0, 0), (0, 0, 4), "Z", ld.TIPO_PILAR, "vertical"),
        ((0, 0, 4), (6, 0, 4), "Z", ld.TIPO_VIGA, "horizontal"),
        ((1, 1, 1), (1, 1, 1), "Y", "—", "comprimento nulo"),
    ],
)
def test_tipo_pela_posicao(inicio, fim, eixo, tipo, trecho):
    corpo = ld.CorpoDoModelo("c", "", "", inicio, fim, 4.0)
    sugerido, motivo = ld.tipo_pela_geometria(corpo, eixo)
    assert sugerido == tipo and trecho in motivo


# ------------------------------------------------------------------ barra a barra
def test_le_as_barras_com_o_esqueleto():
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar(*TODOS), geometria())}
    pilar, viga, pilar_2 = leituras[PILAR], leituras[VIGA], leituras[PILAR_2]
    assert (pilar.tipo_sugerido, viga.tipo_sugerido, pilar_2.tipo_sugerido) == (
        ld.TIPO_PILAR,
        ld.TIPO_VIGA,
        ld.TIPO_PILAR,
    )
    # "W8x31" no item da lista, mas a seção do modelo é a do W 200 × 35,9: vale a do modelo.
    assert pilar.perfil_sugerido == "W 200 x 35,9 (H)"
    assert "lista de corte (W8x31)" in pilar.origem_do_perfil
    assert "W 200 x 35,9 (H)" in pilar.origem_do_perfil
    # O nome da viga diz C8X13.75, mas a lista de corte do modelo diz W 310 × 32,7: vale o modelo.
    assert viga.perfil_sugerido == "W 310 x 32,7"
    assert (pilar.comprimento_m, viga.comprimento_m) == (pytest.approx(4.0), pytest.approx(6.0))
    assert (pilar.elementos, viga.elementos) == (2, 4)
    assert pilar.pontas == viga.pontas == (ld.PONTA_RIGIDA, ld.PONTA_RIGIDA)
    assert not pilar.avisos and not viga.avisos and not pilar.tem_ponta_solta
    assert viga.eixo_forte == em.EIXO_M2


def test_sem_esqueleto_le_pelos_esforcos_e_pelo_nome():
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar(*TODOS), plano=plano_do_portico())}
    assert leituras[PILAR].tipo_sugerido == ld.TIPO_PILAR
    assert "N muito maior que V" in leituras[PILAR].motivo_do_tipo
    assert leituras[VIGA].tipo_sugerido == ld.TIPO_VIGA
    assert leituras[VIGA].perfil_sugerido == 'U 8" x 20,50'
    assert leituras[VIGA].origem_do_perfil == "nome da viga no SolidWorks"
    assert leituras[PILAR].perfil_sugerido == "" and leituras[PILAR].comprimento_m is None
    assert leituras[PILAR].corpo is None


def test_barra_so_com_forca_normal_e_contraventamento():
    membros = {"Viga-9(Diagonal[1])": (ponto("1", "1", n=-10), ponto("1", "2", n=-10))}
    dados = em.EsforcosDoModelo(casos={"W0": caso_manual("W0", membros)})
    tipo, motivo = ld.tipo_pelos_esforcos(dados, "Viga-9(Diagonal[1])")
    assert tipo == ld.TIPO_CONTRAVENTAMENTO and "força normal" in motivo


def test_compressao_que_cresce_com_o_peso_e_pilar():
    membros = {"B": (ponto("1", "1", n=-12, v1=3), ponto("1", "2", n=-10, v1=3))}
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", membros)})
    tipo, motivo = ld.tipo_pelos_esforcos(dados, "B")
    assert tipo == ld.TIPO_PILAR and "peso próprio" in motivo


def test_barra_sem_esforco_nao_tem_tipo():
    membros = {"B": (ponto("1", "1"), ponto("1", "2"))}
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", membros)})
    assert ld.tipo_pelos_esforcos(dados, "B") == ("—", "")
    assert ld.classificar_pontas(dados, "B") == (ld.PONTA_SEM_ESFORCO, ld.PONTA_SEM_ESFORCO)
    (leitura,) = ld.ler_barras(dados)
    assert any("sem esforço" in a for a in leitura.avisos)


@pytest.mark.parametrize(
    ("inicio", "fim", "pontas"),
    [
        (ponto("1", "1", 5, 3, 8), ponto("2", "2"), (ld.PONTA_RIGIDA, ld.PONTA_SOLTA)),
        (ponto("1", "1"), ponto("2", "2", 5, 3, 8), (ld.PONTA_SOLTA, ld.PONTA_RIGIDA)),
        (ponto("1", "1", 5, 3), ponto("2", "2", 5, 3), (ld.PONTA_ARTICULADA,) * 2),
        (ponto("1", "1", 5, 3, 8), ponto("2", "2", 5, 3, 8), (ld.PONTA_RIGIDA,) * 2),
    ],
)
def test_pontas_soltas_articuladas_e_rigidas(inicio, fim, pontas):
    meio = (ponto("1", "2", 5, 3, 10), ponto("2", "1", 5, 3, 10))
    dados = em.EsforcosDoModelo(casos={"SC": caso_manual("SC", {"B": (inicio, *meio, fim)})})
    assert ld.classificar_pontas(dados, "B") == pontas
    (leitura,) = ld.ler_barras(dados)
    assert leitura.tem_ponta_solta == (ld.PONTA_SOLTA in pontas)
    if ld.PONTA_SOLTA in pontas:
        assert any("ponta solta" in a for a in leitura.avisos)


@pytest.mark.parametrize(("elementos", "avisa"), [(1, True), (3, True), (4, False), (7, False)])
def test_malha_grossa_na_viga(elementos, avisa):
    pontos = tuple(
        ponto(str(e), fim, n=0.1, v1=5, m2=3) for e in range(1, elementos + 1) for fim in "12"
    )
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", {"V": pontos})})
    (leitura,) = ld.ler_barras(dados)
    assert leitura.tipo_sugerido == ld.TIPO_VIGA and leitura.elementos == elementos
    assert any("malha de" in a for a in leitura.avisos) == avisa


def test_ponta_que_nao_encosta_no_esqueleto():
    corpos = dict(sw.CORPOS)
    item, descricao, p1, p2, perfil = corpos["Canal c C8X13.75(1)[2]"]
    corpos["Canal c C8X13.75(1)[2]"] = (item, descricao, (0, 5000, 0), (6000, 5000, 0), perfil)
    g = geometria(corpos=corpos)
    soltas = ld.pontas_soltas_pela_geometria(g, "Y")
    assert soltas == {
        "Aparar/Estender12[1]": ["fim"],
        "Canal c C8X13.75(1)[2]": ["início", "fim"],
        "Aparar/Estender12[2]": ["fim"],
    }
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar("PP"), g)}
    assert any("não encosta" in a for a in leituras[PILAR].avisos)


def test_balanco_no_esqueleto_tem_a_ponta_solta():
    corpos = {
        **sw.CORPOS,
        "Balanço[1]": ("x", "x", (6000, 4000, 0), (7500, 4000, 0), "W 310 x 32,7"),
    }
    assert ld.pontas_soltas_pela_geometria(geometria(corpos=corpos), "Y") == {"Balanço[1]": ["fim"]}


# ------------------------------------------------------------------ o conjunto
def test_modelo_coerente_nao_tem_nada_de_estranho():
    g = geometria_coerente()
    dados = replace(importar(*TODOS), parametros={"Pilar": em.ParametrosDoTipo(b2=1.12)})
    # O perfil do nome da viga (C8X13.75) não é a seção do modelo (W 310 × 32,7): avisa…
    assert "Perfil diferente do modelo" in titulos(ld.diagnosticar(dados, plano_do_portico(), g))
    # …e as sugestões trocam o perfil que veio só do nome pelo do modelo.
    dados, _ = ld.aplicar_sugestoes(dados, ld.ler_barras(dados, g))
    achados = ld.diagnosticar(dados, plano_do_portico(), g)
    niveis = titulos(achados)
    assert pc.NIVEL_ERRO not in niveis.values() and pc.NIVEL_ATENCAO not in niveis.values()
    assert niveis["Nada de estranho"] == pc.NIVEL_OK
    assert niveis["Peso próprio confere com o esqueleto"] == pc.NIVEL_OK
    # Pórtico: a viga tem momento nas duas pontas — informa, explicando quando articular.
    assert niveis["Vigas engastadas nas pontas"] == em.NIVEL_INFO


def test_sem_casos_nao_ha_achados():
    assert ld.diagnosticar(em.EsforcosDoModelo(), plano_do_portico()) == []


def test_pp_majorado_pelo_esqueleto():
    achados = ld.diagnosticar(importar("PP"), plano_do_portico(), geometria_que_pesa(9.0 / 1.4))
    erro = achado(achados, "PP mais pesado que a estrutura")
    assert erro.nivel == pc.NIVEL_ERRO and "γ ≈ 1,40" in erro.texto
    assert achados[0].nivel == pc.NIVEL_ERRO  # do mais grave para o informativo


def test_pp_com_outras_cargas_pelo_esqueleto():
    erro = achado(
        ld.diagnosticar(importar("PP"), plano_do_portico(), geometria()),
        "PP mais pesado que a estrutura",
    )
    assert erro.nivel == pc.NIVEL_ERRO and "vezes" in erro.texto and "só a gravidade" in erro.texto


def test_pp_mais_leve_que_o_aco_das_barras():
    atencao = achado(
        ld.diagnosticar(importar("PP"), plano_do_portico(), geometria_que_pesa(13.5)),
        "PP mais leve que o aço das barras",
    )
    assert atencao.nivel == pc.NIVEL_ATENCAO and "alumínio" in atencao.texto


def test_fator_das_ligacoes_que_nao_foi_para_a_gravidade():
    plano = pc.com_fator_peso_proprio(plano_do_portico(), 1.07)
    atencao = achado(
        ld.diagnosticar(importar("PP"), plano, geometria_que_pesa(9.0)),
        "PP mais leve que o aço das barras",
    )
    assert "9,81 × 1,07" in atencao.texto
    # Com a gravidade multiplicada no estudo, confere.
    certo = ld.diagnosticar(importar("PP"), plano, geometria_que_pesa(9.0 / 1.07))
    assert "Peso próprio confere com o esqueleto" in titulos(certo)


def test_sem_volume_no_esqueleto_nao_confere_o_peso():
    achados = titulos(
        ld.diagnosticar(importar("PP"), plano_do_portico(), geometria(com_volume=False))
    )
    assert not {
        "PP mais pesado que a estrutura",
        "PP mais leve que o aço das barras",
        "Peso próprio confere com o esqueleto",
    } & set(achados)


def test_eixo_vertical_trocado():
    dados = replace(importar("PP"), eixo_vertical="Z")
    erro = achado(ld.diagnosticar(dados, plano_do_portico()), "Eixo vertical trocado")
    assert erro.nivel == pc.NIVEL_ERRO and "para Y" in erro.texto


def test_dois_casos_com_o_mesmo_resultado():
    dados = importar("PP", "W0")
    arquivo = em.ler_arquivo(sw.csv_forcas_da_viga("W0"), "W0-de-novo.csv")
    dados = em.com_caso(dados, em.caso_do_arquivo(arquivo, "W180"))
    reacoes = em.ler_arquivo(sw.csv_reacoes("W0"), "W0-reacao.csv").reacoes
    dados = em.com_reacoes(dados, "W180", reacoes, "W0-reacao.csv")
    niveis = titulos(ld.diagnosticar(dados, plano_do_portico()))
    assert niveis["W0 e W180 têm o mesmo resultado"] == pc.NIVEL_ERRO


def test_estudo_sem_carga(monkeypatch):
    monkeypatch.setitem(sw.CASOS, "VAZIO", (0.0, 0.0))
    niveis = titulos(ld.diagnosticar(importar("PP", "VAZIO"), plano_do_portico()))
    assert niveis["VAZIO: estudo sem carga"] == pc.NIVEL_ERRO


def test_estudo_que_ficou_com_a_gravidade():
    dados = importar("PP", "W0")
    w0 = dados.casos["W0"]
    rx, ry, rz = w0.reacoes.modelo
    com_peso = replace(w0, reacoes=replace(w0.reacoes, modelo=(rx, ry + 9.0, rz)))
    dados = replace(dados, casos={**dados.casos, "W0": com_peso})
    erro = achado(ld.diagnosticar(dados, plano_do_portico()), "W0: ficou com a gravidade")
    assert erro.nivel == pc.NIVEL_ERRO and "exclua-a" in erro.texto


def test_modelo_que_mudou_entre_os_estudos():
    dados = importar("PP", "W0")
    w0 = dados.casos["W0"]
    sem_viga = replace(w0, membros={k: v for k, v in w0.membros.items() if k != VIGA})
    dados = replace(dados, casos={**dados.casos, "W0": sem_viga})
    erro = achado(ld.diagnosticar(dados, plano_do_portico()), "W0: faltam barras")
    assert erro.nivel == pc.NIVEL_ERRO and erro.barras == (VIGA,)


def test_malha_diferente_entre_os_estudos():
    dados = importar("PP")
    arquivo = em.ler_arquivo(sw.csv_forcas_da_viga("W0", ids={101: 777}), "W0.csv")
    dados = em.com_caso(dados, em.caso_do_arquivo(arquivo, "W0"))
    atencao = achado(ld.diagnosticar(dados, plano_do_portico()), "Malha diferente entre os estudos")
    assert atencao.nivel == pc.NIVEL_ATENCAO and PILAR in atencao.barras


def test_valores_fora_de_escala(monkeypatch):
    monkeypatch.setitem(sw.CASOS, "GIGANTE", (1e6, 0.0))
    niveis = titulos(ld.diagnosticar(importar("PP", "GIGANTE"), plano_do_portico()))
    assert niveis["Valores fora de escala"] == pc.NIVEL_ERRO


def test_pontas_soltas_no_conjunto():
    membros = {
        "B": (ponto("1", "1", 5, 3, 8), ponto("1", "2", 5, 3, 4), ponto("2", "1"), ponto("2", "2"))
    }
    dados = em.EsforcosDoModelo(casos={"SC": caso_manual("SC", membros)})
    atencao = achado(ld.diagnosticar(dados, plano_do_portico()), "Pontas soltas")
    assert atencao.nivel == pc.NIVEL_ATENCAO and atencao.barras == ("B",)


def test_segunda_ordem_global():
    dados = importar(*TODOS)
    sem_b2 = achado(ld.diagnosticar(dados, plano_do_portico()), "Segunda ordem global (B₂)")
    assert sem_b2.nivel == pc.NIVEL_ATENCAO and "Sem contraventamento" in sem_b2.texto
    assert set(sem_b2.barras) == {PILAR, PILAR_2}
    # Com uma barra de contraventamento na tabela: só informa (pequena deslocabilidade?).
    contraventada = em.com_membros(dados, {VIGA: em.ConfiguracaoDoMembro(tipo="Diagonal")})
    info = achado(ld.diagnosticar(contraventada, plano_do_portico()), "Segunda ordem global (B₂)")
    assert info.nivel == em.NIVEL_INFO and "pequena deslocabilidade" in info.texto
    # Com o B₂ dos pilares informado, some.
    com_b2 = replace(dados, parametros={"Pilar": em.ParametrosDoTipo(b2=1.12)})
    assert "Segunda ordem global (B₂)" not in titulos(ld.diagnosticar(com_b2, plano_do_portico()))


def test_tipo_da_tabela_diferente_da_posicao():
    dados = em.com_membros(importar("PP"), {PILAR: em.ConfiguracaoDoMembro(tipo="Viga")})
    atencao = achado(
        ld.diagnosticar(dados, plano_do_portico(), geometria()),
        "Tipo diferente da posição no modelo",
    )
    assert atencao.barras == (PILAR,)
    # Sem o esqueleto não há posição para comparar.
    sem = titulos(ld.diagnosticar(dados, plano_do_portico()))
    assert "Tipo diferente da posição no modelo" not in sem


@pytest.mark.parametrize(
    ("escolhido", "sugerido", "mesmo"),
    [
        ("Pilar", "Pilar", True),
        ("Diagonal", ld.TIPO_CONTRAVENTAMENTO, True),
        (ld.TIPO_CONTRAVENTAMENTO, "Diagonal", True),
        ("Viga", "Pilar", False),
    ],
)
def test_mesmo_papel(escolhido, sugerido, mesmo):
    assert ld._mesmo_papel(escolhido, sugerido) == mesmo


def test_perfil_da_tabela_diferente_do_modelo():
    dados = em.com_membros(
        importar("PP"), {PILAR: em.ConfiguracaoDoMembro(perfil="W 200 x 46,1 (H)")}
    )
    atencao = achado(
        ld.diagnosticar(dados, plano_do_portico(), geometria()), "Perfil diferente do modelo"
    )
    # O pilar foi escolhido diferente; a viga ficou com o perfil do nome (C8X13.75).
    assert set(atencao.barras) == {PILAR, VIGA}


def test_barras_fora_do_esqueleto():
    corpos = {k: v for k, v in sw.CORPOS.items() if k != "Aparar/Estender12[2]"}
    atencao = achado(
        ld.diagnosticar(importar("PP"), plano_do_portico(), geometria(corpos=corpos)),
        "Barras fora do esqueleto",
    )
    assert atencao.barras == (PILAR_2,)


# ------------------------------------------------------------------ na hora de enviar
def forcas(caso: str, estudo: str | None = None, nome: str | None = None) -> em.ArquivoLido:
    return em.ler_arquivo(sw.csv_forcas_da_viga(caso, estudo=estudo), nome or f"{caso}.csv")


def reacoes(caso: str, nome: str | None = None) -> em.ArquivoLido:
    return em.ler_arquivo(sw.csv_reacoes(caso), nome or f"{caso}-reacao.csv")


def test_envio_coerente_nao_tem_aviso():
    escolhas = [(forcas("PP"), "PP"), (reacoes("PP"), "PP"), (forcas("W0"), "W0")]
    avisos = ld.avisos_da_importacao([*escolhas, (reacoes("W0"), "W0")], CODIGOS)
    assert avisos == []


def test_estudo_com_nome_de_outro_caso():
    avisos = ld.avisos_da_importacao([(forcas("PP"), "SC"), (reacoes("PP"), "SC")], CODIGOS)
    assert {a.nivel for a in avisos} == {pc.NIVEL_ATENCAO}
    assert all("caso PP" in a.texto for a in avisos)


def test_dois_arquivos_de_forcas_no_mesmo_caso_bloqueiam():
    escolhas = [(forcas("PP"), "PP"), (forcas("SC", nome="sc.csv"), "PP"), (reacoes("PP"), "PP")]
    avisos = ld.avisos_da_importacao(escolhas, CODIGOS)
    assert avisos[0].nivel == pc.NIVEL_ERRO and "dois arquivos de forças" in avisos[0].titulo


def test_duas_reacoes_no_mesmo_caso_bloqueiam():
    escolhas = [(forcas("PP"), "PP"), (reacoes("PP"), "PP"), (reacoes("PP", "outra.csv"), "PP")]
    niveis = titulos(ld.avisos_da_importacao(escolhas, CODIGOS))
    assert niveis["PP: dois arquivos de reações"] == pc.NIVEL_ERRO


def test_forcas_sem_reacoes_so_informa():
    niveis = titulos(ld.avisos_da_importacao([(forcas("W0"), "W0")], CODIGOS))
    assert niveis == {"W0: sem o arquivo de reações": em.NIVEL_INFO}


def test_forcas_e_reacoes_de_estudos_diferentes():
    escolhas = [(forcas("PP"), "PP"), (reacoes("SC"), "PP")]
    niveis = titulos(ld.avisos_da_importacao(escolhas, CODIGOS))
    assert niveis["PP: forças e reações de estudos diferentes"] == pc.NIVEL_ATENCAO


def test_arquivo_sem_caso_escolhido_e_ignorado():
    assert ld.avisos_da_importacao([(forcas("PP"), ""), (forcas("SC"), "")], CODIGOS) == []


# ------------------------------------------------------------------ sugestões
def test_aplicar_sugestoes_preenche_a_tabela_vazia():
    dados = importar(*TODOS)
    leituras = ld.ler_barras(dados, geometria())
    sugerido, mudaram = ld.aplicar_sugestoes(dados, leituras)
    assert mudaram == 3
    pilar, viga = sugerido.membros[PILAR], sugerido.membros[VIGA]
    assert (pilar.tipo, pilar.perfil) == ("Pilar", "W 200 x 35,9 (H)")
    assert (pilar.lx_m, pilar.ly_m, pilar.lb_m) == (4.0, 4.0, 4.0)
    assert (viga.tipo, viga.perfil, viga.lb_m) == ("Viga", "W 310 x 32,7", 6.0)
    # Aplicar de novo não muda nada.
    assert ld.aplicar_sugestoes(sugerido, ld.ler_barras(sugerido, geometria()))[1] == 0


def test_aplicar_sugestoes_nao_troca_o_que_foi_escolhido():
    escolhido = em.ConfiguracaoDoMembro(
        perfil="W 200 x 46,1 (H)", tipo="Pilar", eixo_forte=em.EIXO_M1, lx_m=2.0
    )
    dados = em.com_membros(importar(*TODOS), {PILAR: escolhido})
    sugerido, _ = ld.aplicar_sugestoes(dados, ld.ler_barras(dados, geometria()))
    pilar = sugerido.membros[PILAR]
    assert (pilar.perfil, pilar.tipo, pilar.eixo_forte, pilar.lx_m) == (
        "W 200 x 46,1 (H)",
        "Pilar",
        em.EIXO_M1,
        2.0,
    )
    assert pilar.ly_m == 4.0 and pilar.lb_m == 4.0  # só o que estava vazio


def test_aplicar_sugestoes_so_usa_perfil_do_catalogo():
    dados = importar("PP")
    leituras = [replace(lb, perfil_sugerido="Perfil inventado") for lb in ld.ler_barras(dados)]
    sugerido, _ = ld.aplicar_sugestoes(dados, leituras)
    assert sugerido.membros[PILAR].perfil == sugerido.membros[PILAR_2].perfil == ""
    assert sugerido.membros[VIGA].perfil == dados.membros[VIGA].perfil == 'U 8" x 20,50'


def test_resumo_e_linhas_da_leitura():
    leituras = ld.ler_barras(importar(*TODOS), geometria())
    assert ld.resumo_das_barras(leituras) == {
        ld.TIPO_PILAR: 2,
        ld.TIPO_VIGA: 1,
        ld.TIPO_CONTRAVENTAMENTO: 0,
        "—": 0,
    }
    linhas = ld.linhas_da_leitura(leituras)
    assert len(linhas) == 3 and all(len(linha) == len(ld.COLUNAS_LEITURA) for linha in linhas)
    assert linhas[0][0] == PILAR and linhas[0][7] == "rígida / rígida"


# ------------------------------------------------------------------ inclinação pelo peso próprio
def elemento(n1, v1_1, n2, v1_2, m=0.0, nome="1"):
    return (ponto(nome, "1", n=n1, v1=v1_1, m2=m), ponto(nome, "2", n=n2, v1=v1_2, m2=m))


@pytest.mark.parametrize(
    ("pontos", "angulo"),
    [
        (elemento(-10.0, 1.0, -9.8, 1.0), 90.0),  # a normal varia, a cortante não: vertical
        (elemento(-5.0, 1.0, -5.0, 0.7), 0.0),  # só a cortante varia: horizontal
        (elemento(-30.0, 1.0, -29.9, 0.9), 45.0),
        (elemento(-5.0, 1.0, -5.0, 0.999), None),  # sinal pequeno demais
    ],
)
def test_inclinacao_pelo_peso_proprio(pontos, angulo):
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", {"B": pontos})})
    medido = ld.inclinacao_pelo_peso(dados, "B")
    assert medido == (None if angulo is None else pytest.approx(angulo, abs=0.5))


def test_sem_pp_nao_ha_inclinacao():
    dados = em.EsforcosDoModelo(casos={"SC": caso_manual("SC", {"B": elemento(-10, 1, -9, 1)})})
    assert ld.inclinacao_pelo_peso(dados, "B") is None and ld.variacao_no_pp(dados, "B") is None


@pytest.mark.parametrize(
    ("pontos", "tipo", "trecho"),
    [
        (elemento(-50.0, 1.0, -49.0, 1.0, m=1.0), ld.TIPO_PILAR, "vertical"),
        # Viga de piso de pórtico 3D: normal grande (das secundárias), mas constante no elemento.
        (elemento(-25.0, 10.0, -25.0, 9.6, m=4.0), ld.TIPO_VIGA, "horizontal"),
        (elemento(-8.0, 0.05, -8.0, 0.0), ld.TIPO_CONTRAVENTAMENTO, "só com força normal"),
        (elemento(-30.0, 1.0, -29.9, 0.9, m=1.0), ld.TIPO_CONTRAVENTAMENTO, "inclinada 45°"),
        (elemento(-3.0, 2.7, -2.93, 2.6, m=1.2), ld.TIPO_VIGA, "banzo de escada"),
    ],
)
def test_tipo_pelo_peso_proprio(pontos, tipo, trecho):
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", {"B": pontos})})
    sugerido, motivo = ld.tipo_pelos_esforcos(dados, "B")
    assert sugerido == tipo and trecho in motivo


def test_diagonal_inclinada_no_esqueleto_que_flete_e_viga_inclinada():
    corpos = {
        "Banzo[1]": ("x", "x", (0, 0, 0), (3000, 2200, 0), "W 200 x 35,9 (H)"),
        "Diagonal[1]": ("x", "x", (0, 0, 0), (3000, 3000, 0), "W 200 x 35,9 (H)"),
    }
    membros = {
        "Viga-1(Banzo[1])": elemento(-3.0, 2.7, -2.93, 2.6, m=1.2),
        "Viga-2(Diagonal[1])": elemento(-30.0, 1.0, -29.9, 0.9, m=1.0),
    }
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", membros)})
    banzo, diagonal = ld.ler_barras(dados, geometria(corpos=corpos))
    assert banzo.tipo_sugerido == ld.TIPO_VIGA and "inclinada 36° no modelo" in banzo.motivo_do_tipo
    assert diagonal.tipo_sugerido == ld.TIPO_CONTRAVENTAMENTO
    # O esqueleto e o PP concordam na inclinação.
    assert not any("não é o desta viga" in a for a in (*banzo.avisos, *diagonal.avisos))


def test_esqueleto_que_nao_bate_com_o_peso_proprio():
    corpos = dict(sw.CORPOS)
    item, descricao, _, _, perfil = corpos["Canal c C8X13.75(1)[2]"]
    corpos["Canal c C8X13.75(1)[2]"] = (item, descricao, (0, 0, 0), (0, 6000, 0), perfil)
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar("PP"), geometria(corpos=corpos))}
    assert any("não é o desta viga" in a for a in leituras[VIGA].avisos)


def test_carga_alem_do_peso_proprio_no_pp():
    erro = achado(
        ld.diagnosticar(importar("PP"), plano_do_portico(), geometria()),
        "Carga além do peso próprio no PP",
    )
    assert erro.nivel == pc.NIVEL_ERRO and erro.barras == (VIGA,)
    assert "1,50 kN/m" in erro.texto
    coerente = ld.diagnosticar(importar("PP"), plano_do_portico(), geometria_coerente())
    assert "Carga além do peso próprio no PP" not in titulos(coerente)


def test_caminho_do_peso_no_pp():
    dados = importar("PP")
    pp = dados.casos["PP"]
    rx, ry, rz = pp.reacoes.modelo
    mais_pesado = replace(pp, reacoes=replace(pp.reacoes, modelo=(rx, ry + 5.0, rz)))
    dados = replace(dados, casos={"PP": mais_pesado})
    info = achado(ld.diagnosticar(dados, plano_do_portico()), "Caminho do peso no PP")
    assert info.nivel == em.NIVEL_INFO
    assert "9,00 kN chegam distribuídos" in info.texto and "5,00 kN pelos nós" in info.texto
    # Tudo ao longo das barras: nada a dizer.
    assert "Caminho do peso no PP" not in titulos(
        ld.diagnosticar(importar("PP"), plano_do_portico())
    )


def test_carga_alem_do_peso_proprio_pela_lista_de_material():
    # Sem o esqueleto: o PP leva 9 kN ao longo da viga, e a Lista diz que o aço todo pesa 4 kN.
    erro = achado(
        ld.diagnosticar(importar("PP"), plano_do_portico(), peso_da_estrutura_kN=4.0),
        "Carga além do peso próprio no PP",
    )
    assert erro.nivel == pc.NIVEL_ERRO and erro.barras[0] == VIGA
    assert "9,00 kN" in erro.texto and "4,00 kN (Lista de material)" in erro.texto
    # Com o aço da Lista igual ao que o PP leva, nada.
    certo = ld.diagnosticar(importar("PP"), plano_do_portico(), peso_da_estrutura_kN=9.0)
    assert "Carga além do peso próprio no PP" not in titulos(certo)


# ------------------------------------------------------------------ macro v4: cabeçalho, forma, avisos
def test_le_o_cabecalho_da_macro():
    g = geometria()
    assert (g.peca, g.configuracao, g.gerado_em, g.versao_da_macro) == (
        "portico.SLDPRT",
        "Padrão",
        "2026-10-12 18:30",
        "v6",
    )
    assert g.origem == "portico.SLDPRT, configuração Padrão, gerado em 2026-10-12 18:30"
    assert outros_avisos(g) == ()
    (nome,) = [a for a in g.avisos if a.startswith("Nome do membro")]
    assert '“Canal c C8X13.75(1)” (1 corpo(s)): o nome diz U 8" x 20,50' in nome
    assert "(W 310 x 32,7)" in nome
    assert g.formas == {ld.FORMA_BARRA: 3, ld.FORMA_CHAPA: 0, ld.FORMA_BLOCO: 0}
    pilar = g.corpo("Aparar/Estender12[1]")
    assert pilar.forma == ld.FORMA_BARRA and pilar.e_barra
    assert pilar.secao_mm == pytest.approx((201.0, 165.0), abs=0.1)


def test_versao_antiga_da_macro_ainda_le_e_avisa():
    g = geometria(versao_antiga=True)
    assert len(g.corpos) == 3 and g.corpos[0].forma == "" and g.corpos[0].e_barra
    assert outros_avisos(g) == (ld.MACRO_ANTIGA,) and g.versao_da_macro == ""


def test_linhas_ruins_viram_aviso_e_nao_erro():
    extras = (
        '"Aparar/Estender12[1]";"x";"x";BARRA;0;0;0;0;9000;0;9000;200;150;100',  # repetido
        '"Sem medida";"x";"x";BARRA;a;b;c;d;e;f;g;0;0;0',
        "",
        '"Longe";"x";"x";BARRA;0;0;0;0;0;99000000;99000000;200;150;100',
    )
    g = geometria(linhas_extras=extras)
    assert [c.nome for c in g.corpos] == [*sw.CORPOS, "Longe"]
    assert g.corpo("Aparar/Estender12[1]").fim == pytest.approx((0.0, 4.0, 0.0))  # o primeiro
    texto = " | ".join(g.avisos)
    assert "1 linha(s) sem coordenadas" in texto
    assert "1 corpo(s) repetido(s)" in texto and "Aparar/Estender12[1]" in texto
    assert "acima de 10 km" in texto


def test_versao_diferente_da_esperada_avisa():
    conteudo = sw.csv_esqueleto().replace(
        b"exportar_lista_de_corte v6", b"exportar_lista_de_corte v9"
    )
    (aviso,) = outros_avisos(ld.ler_esqueleto(conteudo, "x.csv"))
    assert "macro v9" in aviso and "espera a v6" in aviso
    # A v5 ainda vale: lê tudo e diz o que falta (a direção 1 do Simulation).
    (aviso,) = outros_avisos(ld.ler_esqueleto(sw.csv_esqueleto(versao="v5"), "x.csv"))
    assert aviso.startswith("Esqueleto da macro v5") and "direção 1" in aviso
    # A v4 ainda vale: lê tudo e diz o que falta (orientação e contorno).
    (aviso,) = outros_avisos(ld.ler_esqueleto(sw.csv_esqueleto(versao="v4"), "x.csv"))
    assert aviso.startswith("Esqueleto da macro v4") and "contorno das chapas" in aviso


def test_sem_a_linha_das_colunas_explica():
    with pytest.raises(ld.GeometriaInvalida, match="linha das colunas"):
        ld.ler_esqueleto(b'MACRO;"x v4"\r\nPECA;"p"\r\n1;2;3\r\n', "x.csv")


def test_chapas_e_blocos_nao_tem_ponta_solta():
    corpos = {
        **sw.CORPOS,
        "Chapa de piso[1]": ("x", "CH 6,35", (9000, 4000, 0), (10000, 4000, 2000), "W 310 x 32,7"),
        "Calço[1]": ("x", "bloco", (12000, 2000, 0), (12300, 2000, 0), "W 310 x 32,7"),
    }
    g = geometria(corpos=corpos, formas={"Chapa de piso[1]": "CHAPA", "Calço[1]": "BLOCO"})
    assert g.formas == {ld.FORMA_BARRA: 3, ld.FORMA_CHAPA: 1, ld.FORMA_BLOCO: 1}
    assert not g.corpo("Chapa de piso[1]").e_barra
    assert ld.pontas_soltas_pela_geometria(g, "Y") == {}
    # Uma forma que a leitura não conhece fica vazia (tratada como barra).
    g = geometria(formas={"Aparar/Estender12[1]": "TRELICA"})
    assert g.corpo("Aparar/Estender12[1]").forma == ""


def test_perfil_sugerido_diz_a_secao_no_modelo():
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar("PP"), geometria())}
    assert "seção de 201 × 165 mm no modelo" in leituras[PILAR].origem_do_perfil


def test_esqueleto_v4_gravado_ida_e_volta():
    extras = ('"Longe";"x";"x";BARRA;0;0;0;0;0;99000000;99000000;200;150;100',)
    g = geometria(linhas_extras=extras)
    lido = ld.de_dicionario(json.loads(json.dumps(ld.para_dicionario(g))))
    assert (lido.peca, lido.configuracao, lido.gerado_em, lido.versao_da_macro, lido.avisos) == (
        g.peca,
        g.configuracao,
        g.gerado_em,
        g.versao_da_macro,
        g.avisos,
    )
    for a, b in zip(lido.corpos, g.corpos, strict=True):
        assert a.forma == b.forma and a.secao_mm == pytest.approx(b.secao_mm)
    # O gravado pela versão anterior (sem forma nem seção) continua lido.
    antigo = ld.para_dicionario(g)
    antigo["corpos"] = [linha[:11] for linha in antigo["corpos"]]
    del antigo["avisos"], antigo["peca"]
    lido = ld.de_dicionario(antigo)
    assert len(lido.corpos) == 4 and lido.corpos[0].forma == "" and lido.corpos[0].secao_mm is None


@pytest.mark.parametrize(
    "extras",
    [
        ["TRELICA", 200, 150],
        [7, "a", None],
        [None, -5, 3],
        ["CHAPA", float("inf"), 1],
        [True, True, True],
    ],
)
def test_forma_e_secao_gravadas_estragadas(extras):
    linha = ["a", "b", "c", 0, 0, 0, 0, 4, 0, 4, 0.01, *extras]
    (corpo,) = ld.de_dicionario({"corpos": [linha], "avisos": "texto", "peca": 3}).corpos
    assert corpo.forma in ("", "CHAPA") and corpo.secao_mm in (None, (200, 150))
    assert ld.de_dicionario({"corpos": [linha], "avisos": [1, "ok"]}).avisos == ("ok",)


def test_contrato_com_a_macro():
    """As colunas e o cabeçalho que a macro grava são os que a leitura procura."""
    import re

    macro = lm.macro_da_lista_de_corte().decode("ascii")
    partes = re.search(r'"(CORPO;[^"]*)" & _\s*"([^"]*)" & _\s*"([^"]*)"', macro)
    assert partes is not None
    colunas = "".join(partes.groups()).split(";")
    chaves = re.findall(r'Print #numeroDoArquivo, "(\w+);"', macro)
    assert {c.lower() for c in chaves} == set(ld._METADADOS)
    versao = re.search(r'VERSAO_DA_MACRO As String = "(v\d+)"', macro).group(1)
    assert versao == ld.VERSAO_ATUAL_DA_MACRO
    # Uma linha como a macro escreve (EscreverCorpo): nome, item, descrição, forma, 6
    # coordenadas, comprimento, seção A e B, volume, a direção da seção e, numa chapa, o contorno
    # e as aberturas — tantos campos quanto colunas.
    valores = ['"Viga[1]"', '"W8x31<1>"', '"W8x31"', "BARRA", "0,0", "0,0", "0,0", "0,0"]
    valores += ["4000,0", "0,0", "4000,0", "201,0", "165,0", "18280,0"]
    valores += ["1,0000", "0,0000", "-0,0000", '""', '""', "0,0000", "0,0000", "1,0000", "15,6"]
    assert len(valores) == len(colunas)
    cabecalho = [
        f'{chave};"{valor}"'
        for chave, valor in zip(
            chaves,
            (
                "Mecanica Toolkit - exportar_lista_de_corte " + versao,
                "p.SLDPRT",
                "Padrao",
                "2026-10-12 18:30",
            ),
            strict=True,
        )
    ]
    conteudo = "\r\n".join([*cabecalho, ";".join(colunas), ";".join(valores)]).encode("ascii")
    g = ld.ler_esqueleto(conteudo, "p_esqueleto.csv")
    (corpo,) = g.corpos
    assert g.avisos == () and g.versao_da_macro == versao and g.peca == "p.SLDPRT"
    assert corpo.forma == "BARRA" and corpo.secao_mm == (201.0, 165.0)
    assert corpo.fim == pytest.approx((0.0, 4.0, 0.0)) and corpo.volume_m3 == pytest.approx(0.01828)
    assert corpo.direcao_secao == pytest.approx((1.0, 0.0, 0.0))
    assert corpo.direcao_1 == pytest.approx((0.0, 0.0, 1.0))
    assert corpo.folga_da_direcao_1_mm == pytest.approx(15.6)
    assert ld.tipo_do_arquivo(conteudo) == ld.TIPO_ESQUELETO
    # Uma chapa, com o contorno e uma abertura como a macro escreve (PontosDoLaco).
    contorno = '"0,0 0,0 0,0 | 2000,0 0,0 0,0 | 2000,0 0,0 1000,0 | 0,0 0,0 1000,0"'
    furo = '"500,0 0,0 300,0 | 700,0 0,0 300,0 | 700,0 0,0 500,0"'
    chapa = ['"Chapa[1]"', '"Item48"', '"Item48"', "CHAPA", "0,0", "0,0", "500,0", "2000,0"]
    chapa += ["0,0", "500,0", "2000,0", "1000,0", "6,4", "12800,0", "0,0000", "0,0000"]
    chapa += ["1,0000", contorno, furo, "", "", "", ""]
    conteudo = "\r\n".join(
        [*cabecalho, ";".join(colunas), ";".join(valores), ";".join(chapa)]
    ).encode("ascii")
    placa = ld.ler_esqueleto(conteudo, "p_esqueleto.csv").corpo("Chapa[1]")
    esperado = ((0, 0, 0), (2, 0, 0), (2, 0, 1), (0, 0, 1))
    assert all(p == pytest.approx(e) for p, e in zip(placa.contorno, esperado, strict=True))
    assert len(placa.aberturas) == 1 and placa.aberturas[0][1] == pytest.approx((0.7, 0, 0.3))


# ------------------------------------------------------------------ tensões da viga
def tensoes(caso="W0", **kwargs) -> em.ArquivoLido:
    return em.ler_arquivo(sw.csv_tensoes_da_viga(caso, **kwargs), f"{caso}-tensao.csv")


def test_le_o_listar_tensoes_da_viga():
    t = tensoes("PP")
    assert t.tipo == em.TIPO_TENSOES_VIGA and t.estudo == "PP" and not t.avisos
    assert set(t.tensoes_da_viga) == set(sw.BARRAS)
    primeira = t.tensoes_da_viga[PILAR][0]
    # PP: 4,5 kN de compressão no pilar ÷ 4 570 mm² = −0,98 MPa (compressão negativa).
    assert primeira.axial == pytest.approx(-4500 / 4570, rel=1e-3)
    assert t.tensao_maxima_MPa == pytest.approx(
        max(abs(x.pior) for pontos in t.tensoes_da_viga.values() for x in pontos)
    )


@pytest.mark.parametrize("unidade", ["N/m^2", "MPa", "N/mm^2"])
def test_tensoes_em_outras_unidades_e_sem_o_pior_cenario(unidade):
    com = tensoes(unidade="N/m^2")
    sem = tensoes(com_pior=False, unidade=unidade)
    for a, b in zip(com.tensoes_da_viga[VIGA], sem.tensoes_da_viga[VIGA], strict=True):
        assert b.axial == pytest.approx(a.axial, rel=1e-3)
        assert b.pior == pytest.approx(abs(a.axial) + abs(a.flexao2), rel=1e-3)


def test_tensoes_da_viga_sem_resultados_e_erro_previsto():
    so_cabecalho = sw.csv_tensoes_da_viga("W0").split(b"\r\n")[:5]
    with pytest.raises(em.ArquivoInvalido, match="tensões da viga"):
        em.ler_arquivo(b"\r\n".join(so_cabecalho), "t.csv")


def test_area_que_o_simulation_usou():
    areas = ld.area_no_simulation(
        em.ler_arquivo(sw.csv_forcas_da_viga("W0"), "f.csv").membros, tensoes().tensoes_da_viga
    )
    assert areas[PILAR] == pytest.approx(4570, rel=2e-3)  # W 200 x 35,9
    assert areas[VIGA] == pytest.approx(4210, rel=2e-3)  # W 310 x 32,7


def portico_com_perfis() -> em.EsforcosDoModelo:
    perfis = {PILAR: "W 200 x 35,9 (H)", PILAR_2: "W 200 x 35,9 (H)", VIGA: "W 310 x 32,7"}
    return em.com_membros(
        importar("W0"), {b: em.ConfiguracaoDoMembro(perfil=p) for b, p in perfis.items()}
    )


def test_secao_do_simulation_confere():
    achados = titulos(ld.conferir_tensoes([tensoes()], portico_com_perfis()))
    assert achados == {
        "W0: seção do Simulation confere": pc.NIVEL_OK,
        "W0: tensões da viga": em.NIVEL_INFO,
    }


def test_secao_do_simulation_diferente_do_perfil():
    achados = ld.conferir_tensoes([tensoes(fator_da_area=0.8)], portico_com_perfis())
    atencao = achado(achados, "W0: seção do Simulation diferente do perfil")
    assert atencao.nivel == pc.NIVEL_ATENCAO and set(atencao.barras) == set(sw.BARRAS)
    assert "36,6 cm² no Simulation; W 200 x 35,9 (H): 45,7 cm²" in atencao.texto
    assert achados[0] is atencao  # o mais grave primeiro


def test_forcas_enviadas_junto_conferem_pelo_esqueleto():
    # Projeto vazio: a seção é conferida com as forças do mesmo envio e o perfil do esqueleto.
    forcas = em.ler_arquivo(sw.csv_forcas_da_viga("W0"), "W0.csv")
    g = geometria()  # o esqueleto diz W 200 x 35,9 nos pilares e W 310 x 32,7 na viga
    achados = titulos(ld.conferir_tensoes([tensoes(), forcas], em.EsforcosDoModelo(), g))
    assert achados["W0: seção do Simulation confere"] == pc.NIVEL_OK


def test_tensoes_sem_as_forcas_pedem_o_outro_arquivo():
    achados = ld.conferir_tensoes([tensoes(estudo="Outro estudo")], importar("W0"))
    assert titulos(achados)["Outro estudo: seção do Simulation"] == em.NIVEL_INFO


def test_tensao_acima_do_escoamento_avisa():
    achados = ld.conferir_tensoes([tensoes(fator_da_area=0.001)], portico_com_perfis())
    atencao = achado(achados, "W0: tensões da viga")
    assert atencao.nivel == pc.NIVEL_ATENCAO and "escoamento do A36" in atencao.texto


def test_sem_arquivo_de_tensoes_nada_a_dizer():
    assert ld.conferir_tensoes([em.ler_arquivo(sw.csv_tensoes(), "vm.csv")], importar("W0")) == []


# ------------------------------------------------------------------ perfis com cortes e peças curtas
@pytest.mark.parametrize(
    ("perfil", "secao", "cabe"),
    [
        ('L 2 1/2" × 1/4"', (91.8, 54.2), True),  # cantoneira medida nos eixos principais
        ('L 2" × 5/16"', (91.8, 54.2), False),  # aba de 50,8 mm não chega a 91,8 mm
        ("W 200 x 31,3", (210.0, 134.0), True),
        ('U 6" x 12,20', (218.4, 67.7), False),  # U 6" não chega aos 218 mm do U 8"
        ("Perfil desconhecido", (100.0, 50.0), True),
        ("W 200 x 31,3", None, True),
    ],
)
def test_perfil_cabe_na_secao_medida(perfil, secao, cabe):
    assert ld.cabe_na_secao(perfil, secao) == cabe


def test_corte_em_meia_esquadria_nao_troca_o_perfil():
    """A peça cortada tem menos volume; a mais reta do mesmo perfil dá a área verdadeira."""
    u8 = sw.sc.obter_perfil('U 8" x 20,50')
    corpos = {
        "Reta[1]": ("C8x13.75<1>", "C8x13.75", (0, 0, 0), (2000, 0, 0), 'U 8" x 20,50'),
        "Cortada[1]": ("C8x13.75<2>", "C8x13.75", (0, 0, 0), (0, 0, 1000), 'U 8" x 20,50'),
    }
    volume_cortado = u8.area_mm2 * 0.76 * 1000 / 1000  # 24 % a menos: meia-esquadria
    g = geometria(corpos=corpos, volumes_cm3={"Cortada[1]": volume_cortado})
    assert ld.areas_por_perfil(g)["C8x13.75"] == pytest.approx(u8.area_mm2, rel=2e-3)
    membros = {
        "Viga-1(Reta[1])": elemento(-0.1, 2.0, -0.1, 1.6, m=1.0),
        "Viga-2(Cortada[1])": elemento(-0.1, 2.0, -0.1, 1.6, m=1.0),
    }
    dados = em.EsforcosDoModelo(casos={"PP": caso_manual("PP", membros)})
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    assert leituras["Viga-2(Cortada[1])"].perfil_sugerido == 'U 8" x 20,50'
    # Sem a peça reta, a área sozinha lembraria outro perfil, mas a seção medida não cabe nele.
    so_cortada = geometria(
        corpos={"Cortada[1]": corpos["Cortada[1]"]}, volumes_cm3={"Cortada[1]": volume_cortado}
    )
    dados = em.EsforcosDoModelo(
        casos={"PP": caso_manual("PP", {"Viga-2(Cortada[1])": membros["Viga-2(Cortada[1])"]})}
    )
    (leitura,) = ld.ler_barras(dados, so_cortada)
    # O U 6" teria a área, mas não cabe na seção medida (203 mm): fica o U 8" do item.
    assert leitura.perfil_sugerido == 'U 8" x 20,50'


def test_peca_curta_toma_a_direcao_do_peso_proprio():
    corpos = dict(sw.CORPOS)
    item, descricao, _, _, perfil = corpos["Canal c C8X13.75(1)[2]"]
    # Peça curta: a maior medida (a altura da seção) saiu na vertical.
    corpos["Canal c C8X13.75(1)[2]"] = (item, descricao, (0, 4000, 0), (0, 4310, 0), perfil)
    g = geometria(corpos=corpos, formas={"Canal c C8X13.75(1)[2]": "BLOCO"})
    leituras = {lb.barra: lb for lb in ld.ler_barras(importar("PP"), g)}
    viga = leituras[VIGA]
    assert viga.tipo_sugerido == ld.TIPO_VIGA and "peça curta" in viga.motivo_do_tipo
    assert not any("não é o desta viga" in a for a in viga.avisos)


def test_mesmo_perfil_com_volumes_diferentes_avisa():
    corpos = {
        "Diagonal[1]": ("T<1>", "AL T SECTION", (0, 0, 0), (0, 3600, 1700), "W 200 x 35,9 (H)"),
        "Diagonal[2]": ("T<2>", "AL T SECTION", (0, 0, 1700), (0, 3600, 0), "W 200 x 35,9 (H)"),
    }
    volume = sw.sc.obter_perfil("W 200 x 35,9 (H)").area_mm2 * 3981 / 1000
    g = geometria(corpos=corpos, volumes_cm3={"Diagonal[2]": volume / 2})
    assert any("volumes por metro diferentes" in a and "AL T SECTION" in a for a in g.avisos)
    assert not any("volumes por metro" in a for a in geometria().avisos)


@pytest.mark.parametrize(
    "extras",
    [
        [None, "contorno", 7],
        [[1, 0], [[0, 0, 0], [1, "a", 0], "x"], [[[0, 0, 0]], "lixo"]],
        [[0, 0, 0], [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], [[[0.1, 0, 0.1]] * 3]],
        [["a", "b", "c"], [], None],
    ],
)
def test_direcao_e_contorno_gravados_estragados(extras):
    linha = ["a", "b", "c", 0, 0, 0, 0, 4, 0, 4, 0.01, "CHAPA", 2000, 6, *extras]
    (corpo,) = ld.de_dicionario({"corpos": [linha]}).corpos
    assert corpo.direcao_secao is None  # vetor nulo, curto ou com texto
    assert len(corpo.contorno) in (0, 4) and all(len(a) >= 3 for a in corpo.aberturas)
    # E o que é lido continua servindo para as cargas do piso e os travamentos.
    g = ld.GeometriaDoModelo(corpos=(corpo,))
    from core import cargas_pelo_modelo as cpm

    cpm.distribuir(g, {"SC": 5.0}, "Y")


# ------------------------------------------------------------------ nomes brasileiros e corpos renomeados
@pytest.mark.parametrize(
    ("nome", "perfil"),
    [
        ('U 8"x17,1 - Plataforma[1]', 'U 8" x 17,10'),
        ('Viga-3(U 8" x 20,5 - Escada[2])', 'U 8" x 20,50'),
        ('W 8" x 31,3', "W 200 x 31,3"),
        ('U 8"x99', None),  # massa sem perfil perto: não chuta
        ("Perfil T - Plataforma[5]", None),
    ],
)
def test_nome_brasileiro_em_polegadas_e_kg_por_metro(nome, perfil):
    assert em.perfil_do_nome(nome) == perfil


def test_lista_de_corte_reconhece_o_nome_brasileiro():
    assert lm.perfil_conhecido('U 8"x17,1').nome == 'U 8" x 17,10'
    assert lm.perfil_conhecido("C8x13.75").nome == 'U 8" x 20,50'


def renomeado(*, isca: bool = False) -> ld.GeometriaDoModelo:
    """O pórtico com o corpo da viga renomeado depois do estudo (o Simulation tem o antigo)."""
    corpos = dict(sw.CORPOS)
    corpos['U 8"x17,1 - Plataforma[2]'] = corpos.pop("Canal c C8X13.75(1)[2]")
    if isca:
        # Outro grupo com o mesmo número [2], mas em pé: a inclinação do PP descarta.
        corpos['U 8"x17,1 - Escada[2]'] = ("x", "x", (9000, 0, 0), (9000, 4000, 0), "W 310 x 32,7")
    return geometria(corpos=corpos)


@pytest.mark.parametrize("isca", [False, True])
def test_corpo_renomeado_depois_do_estudo(isca):
    g = renomeado(isca=isca)
    dados = importar("PP", "W0")
    assert ld.corpo_da_viga(g, VIGA) is None  # pelo nome, não acha
    casamento = ld.correspondencia(g, dados.nomes_dos_membros, dados)
    assert casamento.corpos[VIGA].nome == 'U 8"x17,1 - Plataforma[2]'
    assert casamento.renomeados == {"Canal c C8X13.75(1)": 'U 8"x17,1 - Plataforma'}
    assert casamento.pela_renomeacao == 1
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    assert leituras[VIGA].corpo.nome == 'U 8"x17,1 - Plataforma[2]'
    achados = ld.diagnosticar(dados, plano_do_portico(), g, list(leituras.values()))
    atencao = achado(achados, "Corpos renomeados depois do estudo")
    assert '“Canal c C8X13.75(1)” → “U 8"x17,1 - Plataforma”' in atencao.texto
    assert "Barras fora do esqueleto" not in titulos(achados)


def test_sem_numero_que_case_fica_sem_corpo():
    corpos = dict(sw.CORPOS)
    corpos["Outro nome"] = corpos.pop("Canal c C8X13.75(1)[2]")  # sem [n]: não dá para casar
    g = geometria(corpos=corpos)
    casamento = ld.correspondencia(g, importar("PP").nomes_dos_membros, importar("PP"))
    assert VIGA not in casamento.corpos and not casamento.renomeados


def test_pp_so_com_a_gravidade_nas_barras_confirma():
    achados = ld.diagnosticar(importar("PP"), plano_do_portico(), geometria_coerente())
    ok = achado(achados, "PP só com a gravidade nas barras")
    assert ok.nivel == pc.NIVEL_OK and "Em 3 barra(s)" in ok.texto
    # Sem as reações: a conferência barra a barra continua (não depende delas).
    sem_reacoes = importar("PP", com_reacoes=False)
    assert "PP só com a gravidade nas barras" in titulos(
        ld.diagnosticar(sem_reacoes, plano_do_portico(), geometria_coerente())
    )
    erro = achado(
        ld.diagnosticar(sem_reacoes, plano_do_portico(), geometria()),
        "Carga além do peso próprio no PP",
    )
    assert erro.barras == (VIGA,)


def test_mesmo_item_com_dois_perfis_corpo_a_corpo():
    """O membro renomeado para U 8"x17,1 com a seção nova; um banzo ficou com o perfil antigo."""
    u17, u20 = sw.sc.obter_perfil('U 8" x 17,10'), sw.sc.obter_perfil('U 8" x 20,50')
    corpos = {
        'U 8"x17,1 - Plataforma[1]': (
            "C8x13.75<1>",
            "C8x13.75",
            (0, 4000, 0),
            (6000, 4000, 0),
            'U 8" x 17,10',
        ),
        'U 8"x17,1 - Plataforma[2]': (
            "C8x13.75<1>",
            "C8x13.75",
            (0, 4000, 1500),
            (6000, 4000, 1500),
            'U 8" x 17,10',
        ),
        "Aparar/Estender24": (
            "C8x13.75<34>",
            "C8x13.75",
            (0, 0, 3000),
            (3200, 2100, 3000),
            'U 8" x 20,50',
        ),
    }
    # O banzo tem cortes: 8 % de volume a menos que o perfil cheio.
    banzo = u20.area_mm2 * 3827.5 / 1000 * 0.92
    g = geometria(corpos=corpos, volumes_cm3={"Aparar/Estender24": banzo})
    perfis = {c.nome: ld.perfil_do_corpo(c)[0] for c in g.corpos}
    assert perfis['U 8"x17,1 - Plataforma[1]'] == 'U 8" x 17,10'
    assert perfis["Aparar/Estender24"] == 'U 8" x 20,50'  # 0,92 × 26,1 > 21,8 × 1,03
    (aviso,) = [a for a in g.avisos if a.startswith("O mesmo item da lista de corte")]
    assert (
        '“C8x13.75”: 2 corpo(s) com a seção do U 8" x 17,10, 1 com o U 8" x 20,50 (Aparar/Estender24)'
        in aviso
    )
    # Sem o nome do corpo, a área decide: o mais leve que ainda cobre a seção.
    assert u17.area_mm2 < u20.area_mm2


@pytest.mark.parametrize(
    ("volume_relativo", "esperado"),
    [(1.0, 'U 8" x 17,10'), (0.75, 'U 8" x 17,10'), (1.2, 'U 8" x 20,50')],
)
def test_perfil_pela_area_com_folga_do_corte(volume_relativo, esperado):
    u17 = sw.sc.obter_perfil('U 8" x 17,10')
    corpos = {"Peca[1]": ("C8x13.75<1>", "C8x13.75", (0, 0, 0), (1000, 0, 0), 'U 8" x 17,10')}
    g = geometria(corpos=corpos, volumes_cm3={"Peca[1]": u17.area_mm2 * volume_relativo})
    (corpo,) = g.corpos
    perfil, origem = ld.perfil_do_corpo(corpo)
    assert perfil == esperado
    if esperado == 'U 8" x 17,10':
        assert "área da seção" in origem


def test_pecas_cortadas_seguem_as_retas_do_mesmo_membro():
    """O nome diz U 8"x17,1, mas a peça reta do membro é do U 8" x 20,50: a cortada segue a reta
    (é o que está desenhado), não o nome."""
    u20 = sw.sc.obter_perfil('U 8" x 20,50')
    corpos = {
        'U 8"x17,1 - Escada[1]': (
            "C8x13.75<17>",
            "C8x13.75",
            (0, 0, 0),
            (0, 0, 800),
            'U 8" x 20,50',
        ),
        'U 8"x17,1 - Escada[7]': (
            "C8x13.75<24>",
            "C8x13.75",
            (0, 0, 0),
            (760, 0, 0),
            'U 8" x 20,50',
        ),
    }
    cortada = u20.area_mm2 * 760 / 1000 * 0.73  # dois cortes a 45°
    g = geometria(corpos=corpos, volumes_cm3={'U 8"x17,1 - Escada[7]': cortada})
    perfis = ld.perfis_do_esqueleto(g)
    assert perfis['U 8"x17,1 - Escada[1]'][0] == 'U 8" x 20,50'  # reta: caixa e área exatas
    assert perfis['U 8"x17,1 - Escada[7]'][0] == 'U 8" x 20,50'
    assert "as peças retas do mesmo membro" in perfis['U 8"x17,1 - Escada[7]'][1]
    # Sozinha, a peça cortada fica com o que o nome diz (os dois perfis cabem nela).
    so = geometria(
        corpos={'U 8"x17,1 - Escada[7]': corpos['U 8"x17,1 - Escada[7]']},
        volumes_cm3={'U 8"x17,1 - Escada[7]': cortada},
    )
    assert ld.perfis_do_esqueleto(so)['U 8"x17,1 - Escada[7]'][0] == 'U 8" x 17,10'


def test_esqueleto_de_outro_modelo_nao_e_usado():
    """Esqueleto de outra peça: menos da metade das barras acha o corpo — o programa ignora."""
    texto = sw.csv_esqueleto().decode("cp1252")
    for antigo in ("Aparar/Estender12[", "Canal c C8X13.75(1)["):
        texto = texto.replace(antigo, "Outra peca[7")  # outro nome e outra numeração
    outro = ld.ler_esqueleto(texto.encode("cp1252"), "outra_esqueleto.csv")
    dados = importar("PP", "SC")
    assert not ld.esqueleto_de_outro_modelo(geometria(), dados)
    assert ld.esqueleto_de_outro_modelo(outro, dados)
    assert all(lb.corpo is None for lb in ld.ler_barras(dados, outro))
    achados = ld.diagnosticar(dados, plano_do_portico(), outro)
    assert achados[0].titulo == "Esqueleto de outro modelo" and achados[0].nivel == pc.NIVEL_ERRO
    assert not any(a.titulo == "Barras fora do esqueleto" for a in achados)
