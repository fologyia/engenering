"""O arquivo do gerenciador de casos de carga do SolidWorks: ler, montar do plano e preencher."""

from __future__ import annotations

import pytest

from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import gerenciador_solidworks as gs
from core import load_combinations as comb
from core import plano_de_cargas as pc

Y = ex.EIXO_Y_PARA_CIMA

# O formato exato do "Salvar os dados em um arquivo .csv externo" do SolidWorks: cp1252, vírgula,
# ponto decimal, CRLF, sem aspas e sem quebra de linha no fim. A força tem seis colunas, a
# gravidade três (normal primeiro) e a pressão uma.
LINHAS_DO_SOLIDWORKS = [
    "Tipo de carga,3,3,3,3,3,3,4,4,4,1",
    "Nome da carga:,Força-1,Força-1,Força-1,Força-1,Força-1,Força-1,PP,PP,PP,SC",
    "Valor de:,Ao longo da face dir 1,Ao longo da face dir 2,Normal ao plano,"
    "Ao longo da face dir 1,Ao longo da face dir 2,Normal ao plano,Normal ao plano,"
    "Ao longo da face dir 2,Ao longo da face dir 1,Valor da pressão",
    "Valores originais/iniciais:,Suprimir (N),Suprimir (N),-2000 N,Suprimir (N.m),"
    "Suprimir (N.m),Suprimir (N.m),-10.5 m/s^2,0 m/s^2,0 m/s^2,5000 N/m^2",
    "Caso de carga 1,Suprimir,Suprimir,-2000,Suprimir,Suprimir,Suprimir,-10.5,Suprimir,"
    "Suprimir,Suprimir",
    "SC,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,4000",
    "Combinações de casos de carga",
    'Combinação 1, "Caso de carga 1" + 2*"SC"',
]
DO_SOLIDWORKS = "\r\n".join(LINHAS_DO_SOLIDWORKS).encode("cp1252")


def plano_completo() -> pc.PlanoDeCargas:
    plano = pc.PlanoDeCargas()
    plano = pc.com_acao(plano, pc.nova_acao("PP"))
    plano = pc.com_acao(
        plano,
        pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")]),
    )
    vento = {
        "X": [pc.CargaDoModelo("P1, nível 1", 2.0, "kN", "X")],
        "Y": [pc.CargaDoModelo("P1, nível 1", 3.0, "kN", "Y")],
    }
    for acao in pc.acoes_de_vento("teste", vento):
        plano = pc.com_acao(plano, acao)
    return plano


def com_temperatura(plano: pc.PlanoDeCargas) -> pc.PlanoDeCargas:
    for codigo, delta in (("T+", 10), ("T−", -10)):
        plano = pc.com_acao(
            plano,
            pc.nova_acao(codigo, cargas=[pc.CargaDoModelo("Toda a estrutura", delta, "°C", "—")]),
        )
    return plano


# ------------------------------------------------------------------ ler e gravar
def test_le_o_arquivo_do_solidworks_e_grava_igual():
    lido = gs.ler(DO_SOLIDWORKS)
    assert list(lido.cargas()) == ["Força-1", "PP", "SC"]
    normal = lido.colunas[2]
    assert normal.componente == "Normal ao plano" and normal.valor_original == -2000.0
    assert normal.unidade == "N" and lido.colunas[3].unidade == "N.m"
    assert lido.colunas[0].valor_original is None  # "Suprimir (N)"
    assert lido.colunas[6].valor_original == -10.5 and lido.colunas[7].valor_original == 0.0
    assert lido.colunas[9].unidade == "N/m^2" and gs.grandeza("N/m^2") == gs.PRESSAO
    assert [nome for nome, _ in lido.casos] == ["Caso de carga 1", "SC"]
    assert lido.combinacoes == (("Combinação 1", '"Caso de carga 1" + 2*"SC"'),)
    # Lido e gravado de novo, sai byte a byte igual ao do SolidWorks.
    assert gs.csv_do_gerenciador(lido) == DO_SOLIDWORKS


def test_le_o_arquivo_salvo_de_novo_pelo_excel():
    texto = "\r\n".join(LINHAS_DO_SOLIDWORKS[:6]).replace(",", ";").replace("10.5", "10,5")
    lido = gs.ler(texto.encode("cp1252"))
    assert lido.colunas[6].valor_original == -10.5 and len(lido.colunas) == 10


def test_arquivo_que_nao_e_do_gerenciador():
    assert gs.e_do_gerenciador(DO_SOLIDWORKS)
    with pytest.raises(em.ArquivoInvalido, match="Salvar os dados"):
        gs.ler("Nome do estudo: PP\r\nViga;Axial(N)\r\n".encode("cp1252"))


def test_a_pagina_esforcos_do_modelo_manda_o_arquivo_para_o_plano_de_cargas():
    with pytest.raises(em.ArquivoInvalido, match="Plano de cargas"):
        em.ler_arquivo(DO_SOLIDWORKS, "Simulador-Análise estática-Gerenciador.csv")


def test_numero_como_o_solidworks_escreve():
    assert gs.numero_sw(-9.81) == "-9.81" and gs.numero_sw(5000.0) == "5000"
    assert gs.numero_sw(-0.0) == "0" and gs.numero_sw(0.005) == "0.005"
    assert "e" not in gs.numero_sw(2.5e-11) and gs.numero_sw(1e-13) == "0"


# ------------------------------------------------------------------ montado do plano
def test_do_plano_no_formato_do_solidworks():
    arquivo, avisos = gs.do_plano(com_temperatura(plano_completo()), Y, comb.ESTADOS_PADRAO)
    texto = gs.csv_do_gerenciador(arquivo).decode("cp1252")
    linhas = texto.split("\r\n")
    assert linhas[0] == "Tipo de carga,4,4,4,1" + ",3" * 12
    assert linhas[1].startswith("Nome da carga:,Gravidade-1,Gravidade-1,Gravidade-1,Pressão-1,")
    assert "Força-2" in linhas[1] and "Temperatura" not in linhas[1]
    originais = linhas[3].split(",")
    assert originais[1:5] == ["-9.81 m/s^2", "0 m/s^2", "0 m/s^2", "5000 N/m^2"]
    assert originais[5:11] == [
        "Suprimir (N)",
        "Suprimir (N)",
        "2000 N",
        "Suprimir (N.m)",
        "Suprimir (N.m)",
        "Suprimir (N.m)",
    ]
    assert originais[13] == "-3000 N"  # o Y da planta é o −Z do SolidWorks
    casos = {linha.split(",")[0]: linha.split(",")[1:] for linha in linhas[4:10]}
    assert list(casos) == ["PP", "SC", "W0", "W90", "W180", "W270"]
    assert casos["PP"][:3] == ["-9.81", "Suprimir", "Suprimir"]
    assert casos["SC"][3] == "5000" and casos["W0"][6] == "2000" and casos["W180"][6] == "-2000"
    assert casos["W90"][12] == "-3000" and casos["W270"][12] == "3000"
    assert set(casos["W0"]) == {"Suprimir", "2000"}
    # A temperatura fica de fora (lá ela é a temperatura aplicada), e os casos dela também.
    assert any("Temperatura-1" in a and "temperatura aplicada" in a for a in avisos)
    assert any("T+, T-" in a for a in avisos)
    assert linhas[10] == "Combinações de casos de carga"
    for linha in linhas[11:]:
        nome, expressao = linha.split(", ", 1)
        assert nome.startswith("C") and expressao.count('"') % 2 == 0
        assert '"T' not in expressao
    assert ";" not in texto and "−" not in texto and not texto.endswith("\r\n")
    # O arquivo do programa é lido de volta como um do SolidWorks.
    assert gs.ler(gs.csv_do_gerenciador(arquivo)) == arquivo


def test_momento_vai_na_componente_de_momento_da_forca():
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao("EQ", cargas=[pc.CargaDoModelo("Bocal do tanque", 1.2, "kN·m", "X")]),
    )
    arquivo, _ = gs.do_plano(plano, Y, [])
    assert [c.unidade for c in arquivo.colunas] == ["N", "N", "N", "N.m", "N.m", "N.m"]
    assert arquivo.colunas[5].original == "1200 N.m" and arquivo.colunas[0].carga == "Força-1"
    assert arquivo.casos == (("EQ", ("Suprimir",) * 5 + ("1200",)),)


def test_expressao_da_combinacao_como_no_solidworks():
    assert ex.expressao_da_combinacao([("PP", 1.25), ("SC", 1.5)]) == '1.25*"PP" + 1.5*"SC"'
    assert ex.expressao_da_combinacao([("PP", 1.0), ("T−", -0.6)]) == '"PP" - 0.6*"T-"'


# ------------------------------------------------------------------ preencher o do SolidWorks
def test_preenche_o_arquivo_do_solidworks_com_os_casos_do_plano():
    resultado = gs.preencher(gs.ler(DO_SOLIDWORKS), plano_completo(), Y, comb.ESTADOS_PADRAO)
    ligacoes = {lig.carga_sw: lig for lig in resultado.ligacoes}
    assert ligacoes["Força-1"].carga_plano.startswith("Força-1: P1, nível 1")
    assert ligacoes["Força-1"].componente == "Normal ao plano (N)"
    # "PP" e "SC" são o código do caso que só aquela carga usa.
    assert ligacoes["PP"].carga_plano.startswith("Gravidade-1")
    assert ligacoes["SC"].carga_plano.startswith("Pressão-1") and resultado.ligadas == 3
    avisos = " ".join(resultado.avisos)
    assert "-10,5 m/s^2" in avisos and "Cargas do esqueleto" in avisos  # gravidade majorada
    assert "sinal oposto" in avisos  # a Força-1 foi criada com −2000 e o plano tem +2000
    assert "Força-2" in avisos  # o vento em Z não está no estudo
    assert "Caso de carga 1" in avisos
    arquivo = resultado.arquivo
    assert arquivo.colunas == gs.ler(DO_SOLIDWORKS).colunas  # o cabeçalho é o do SolidWorks
    casos = dict(arquivo.casos)
    assert list(casos) == ["PP", "SC", "W0", "W180"]  # W90 e W270 não têm carga no estudo
    assert casos["PP"][6] == "-9.81" and casos["SC"][9] == "5000"
    assert casos["W0"][2] == "-2000" and casos["W180"][2] == "2000"  # sinal trocado
    assert ("SC", "SC › Valor da pressão", "4000", "5000") in resultado.diferencas
    texto = gs.csv_do_gerenciador(arquivo).decode("cp1252")
    assert texto.split("\r\n")[:4] == LINHAS_DO_SOLIDWORKS[:4]
    assert all('"W90"' not in e and '"W270"' not in e for _, e in arquivo.combinacoes)


def test_carga_que_o_plano_nao_tem_fica_suprimida():
    texto = DO_SOLIDWORKS.decode("cp1252").replace("Força-1", "Peso extra")
    resultado = gs.preencher(gs.ler(texto.encode("cp1252")), plano_completo(), Y, [])
    ligacao = next(lig for lig in resultado.ligacoes if lig.carga_sw == "Peso extra")
    assert ligacao.carga_plano == "" and "suprimida" in ligacao.situacao
    assert all(set(celulas[:6]) == {"Suprimir"} for _, celulas in resultado.arquivo.casos)


def test_temperatura_fica_como_esta_no_solidworks():
    linhas = [
        "Tipo de carga,4,4,4,7",
        "Nome da carga:,PP,PP,PP,Temperatura-1",
        "Valor de:,Normal ao plano,Ao longo da face dir 2,Ao longo da face dir 1,Temperatura",
        "Valores originais/iniciais:,-9.81 m/s^2,0 m/s^2,0 m/s^2,35 Celsius",
        "T+,Suprimir,Suprimir,Suprimir,45",
    ]
    lido = gs.ler("\r\n".join(linhas).encode("cp1252"))
    plano = com_temperatura(pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PP")))
    resultado = gs.preencher(lido, plano, Y, [])
    casos = dict(resultado.arquivo.casos)
    assert casos["T+"] == ("Suprimir", "Suprimir", "Suprimir", "45")
    assert "T-" not in casos  # o T− ainda não foi preenchido no SolidWorks
    assert any("temperatura aplicada" in a for a in resultado.avisos)
