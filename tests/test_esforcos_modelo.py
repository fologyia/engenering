"""Esforços do modelo: leitura dos CSV do SolidWorks, conferência das reações e envoltória."""

from __future__ import annotations

import json
import math

import pytest

from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from tests import dados_solidworks as sw

PILAR = "Viga-1(Aparar/Estender12[1])"
VIGA = "Viga-2(Canal c C8X13.75(1)[2])"


def plano_do_portico(*, vento_kN: float = 8.0, quantidade: int = 1) -> pc.PlanoDeCargas:
    plano = pc.PlanoDeCargas()
    plano = pc.com_acao(plano, pc.nova_acao("PP"))
    plano = pc.com_acao(
        plano,
        pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Viga", 5.0, "kN/m²", "Z (vertical)")]),
    )
    for codigo, sinal in (("W0", 1.0), ("W180", -1.0)):
        plano = pc.com_acao(
            plano,
            pc.nova_acao(
                codigo,
                cargas=[
                    pc.CargaDoModelo(
                        "Topo do pilar", sinal * vento_kN / quantidade, "kN", "X", "", quantidade
                    )
                ],
            ),
        )
    return plano


def importar(*casos: str, com_reacoes: bool = True) -> em.EsforcosDoModelo:
    dados = em.EsforcosDoModelo()
    for caso in casos:
        arquivo = em.ler_arquivo(sw.csv_forcas_da_viga(caso), f"{caso}.csv")
        dados = em.com_caso(dados, em.caso_do_arquivo(arquivo, caso))
        if com_reacoes:
            reacoes = em.ler_arquivo(sw.csv_reacoes(caso), f"{caso}-reacao.csv").reacoes
            dados = em.com_reacoes(dados, caso, reacoes, f"{caso}-reacao.csv")
    return dados


# ------------------------------------------------------------------ leitura
@pytest.mark.parametrize(
    ("texto", "virgula", "valor"),
    [
        ("78.611", True, 78611.0),
        ("-1.019,1", True, -1019.1),
        ("-0,44897", True, -0.44897),
        ("1,4815E+05", True, 148150.0),
        ("4,07610e+07", True, 4.0761e7),
        ("1,019.5", False, 1019.5),
        ("  ", True, None),
        ("abc", True, None),
    ],
)
def test_numeros_do_solidworks(texto, virgula, valor):
    assert em.numero(texto, decimal_virgula=virgula) == (
        None if valor is None else pytest.approx(valor)
    )


def test_le_as_forcas_da_viga_com_o_sinal_do_esforco_interno():
    arquivo = em.ler_arquivo(sw.csv_forcas_da_viga("PP", estudo="PP — peso próprio"), "pp.csv")
    assert arquivo.tipo == em.TIPO_VIGAS
    assert arquivo.estudo == "PP — peso próprio" and "2026" in arquivo.data
    assert list(arquivo.membros) == list(sw.BARRAS)
    pilar = arquivo.membros[PILAR]
    assert len(pilar) == 4 and {p.fim for p in pilar} == {"1", "2"}
    # PP = 1,5 kN/m × 6 m: cada pilar leva 4,5 kN comprimido, em toda a altura.
    assert all(p.n == pytest.approx(-4.5) for p in pilar)
    resultado = sw.resolver("PP")
    base = next(e for e in resultado.esforcos_elementos if e["elemento"] == 101)
    assert pilar[0].m2 == pytest.approx(-base["Mi_Nmm"] / 1e6, rel=1e-4)


def test_unidades_e_formato_ingles():
    texto = (
        "Study name:W0\n"
        "Beam Name,Element,End,Axial(kN),Shear1(kN),Shear2(kN),Moment1(N.mm),Moment2(N.mm),Torque(N.mm)\n"
        "Beam-1(W8X31),,,,,,,,\n"
        ",7,1,1.5,0.2,0,1000000,0,0\n"
        ",,2,-1.5,-0.2,0,-500000,0,0\n"
    )
    arquivo = em.ler_arquivo(texto.encode("utf-8"), "w0.csv")
    pontos = arquivo.membros["Beam-1(W8X31)"]
    assert arquivo.estudo == "W0"
    assert pontos[0].n == pytest.approx(-1.5) and pontos[0].m1 == pytest.approx(-1.0)
    assert pontos[1].n == pytest.approx(-1.5) and pontos[1].m1 == pytest.approx(-0.5)


def test_le_reacoes_e_tensoes():
    reacoes = em.ler_arquivo(sw.csv_reacoes("SC"), "r.csv")
    assert reacoes.tipo == em.TIPO_REACOES
    assert reacoes.reacoes.modelo == pytest.approx((0.0, 60.0, 0.0), abs=1e-3)
    tensoes = em.ler_arquivo(sw.csv_tensoes(), "t.csv")
    assert tensoes.tipo == em.TIPO_TENSOES
    assert tensoes.tensao_maxima_MPa == pytest.approx(40.761)


def test_arquivo_que_nao_e_do_solidworks():
    with pytest.raises(em.ArquivoInvalido, match="Listar forças da viga"):
        em.ler_arquivo(b"a;b;c\n1;2;3\n", "qualquer.csv")
    with pytest.raises(em.ArquivoInvalido, match="Faltam colunas"):
        em.ler_arquivo(b"Nome da viga;Axial (N)\nV1;\n", "x.csv")


@pytest.mark.parametrize(
    ("estudo", "caso"),
    [
        ("W0 vento +X", "W0"),
        ("PP", "PP"),
        ("Estudo SC - sobrecarga", "SC"),
        ("T- frio", "T−"),
        ("W0-vento", "W0"),
        ("Análise estática 1", None),
    ],
)
def test_caso_sugerido_pelo_nome_do_estudo(estudo, caso):
    assert em.caso_sugerido(estudo, [c.codigo for c in pc.CODIGOS]) == caso


@pytest.mark.parametrize(
    ("nome", "perfil"),
    [
        ("Viga-2(Canal c C8X13.75(1)[2])", 'U 8" x 20,50'),
        ("Viga-23(Ângulo l L2.5X2.5X0.25(1)[5])", 'L 2 1/2" × 1/4"'),
        ("Beam-1(W8X31)", "W 200 x 46,1 (H)"),
        ("Pilar W 250 x 32.7", "W 250 x 32,7"),
        ("Viga-1(Aparar/Estender12[1])", None),
    ],
)
def test_perfil_pelo_nome_da_viga(nome, perfil):
    assert em.perfil_do_nome(nome) == perfil


def test_eixo_forte_sugerido_e_o_momento_que_domina():
    dados = importar("SC")
    assert dados.membros[VIGA].eixo_forte == em.EIXO_M2
    assert dados.membros[VIGA].perfil == 'U 8" x 20,50'
    assert dados.membros[PILAR].perfil == ""


# ------------------------------------------------------------------ casos no projeto
def test_casos_reacoes_remocao_e_ida_e_volta():
    dados = importar("PP", "SC")
    assert set(dados.casos) == {"PP", "SC"} and dados.casos["PP"].elementos == 8
    with pytest.raises(em.ArquivoInvalido, match="forças da viga"):
        em.com_reacoes(dados, "W0", dados.casos["PP"].reacoes, "r.csv")
    # Reimportar as forças mantém as reações já gravadas do caso.
    novo = em.caso_do_arquivo(em.ler_arquivo(sw.csv_forcas_da_viga("PP"), "pp2.csv"), "PP")
    dados2 = em.com_caso(dados, novo)
    assert dados2.casos["PP"].arquivo == "pp2.csv" and dados2.casos["PP"].reacoes is not None
    assert set(em.sem_caso(dados2, "SC").casos) == {"PP"}
    dados3 = em.com_membros(dados2, {PILAR: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar")})
    volta = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados3))))
    assert volta.membros[PILAR] == em.ConfiguracaoDoMembro(
        "W 200 x 35,9 (H)", "Pilar", dados3.membros[PILAR].eixo_forte
    )
    for nome, pontos in dados3.casos["SC"].membros.items():
        for a, b in zip(volta.casos["SC"].membros[nome], pontos, strict=True):
            assert a.chave == b.chave
            assert all(
                math.isclose(x, y, rel_tol=1e-5, abs_tol=1e-9)
                for x, y in zip(a.vetor(), b.vetor(), strict=True)
            )
    assert volta.casos["SC"].reacoes.modelo == pytest.approx(dados3.casos["SC"].reacoes.modelo)
    assert em.esforcos_do_projeto(None).casos == {}


# ------------------------------------------------------------------ conferência
def niveis(itens) -> dict[str, str]:
    saida: dict[str, str] = {}
    for item in itens:
        saida[item.nivel] = saida.get(item.nivel, "") + " | " + item.texto
    return saida


def test_conferencia_do_portico_correto():
    r = niveis(em.conferir_reacoes(importar("PP", "SC", "W0", "W180"), plano_do_portico()))
    assert pc.NIVEL_ATENCAO not in r and pc.NIVEL_ERRO not in r
    assert "W0: as reações equilibram as forças do plano (8,00 kN)" in r[pc.NIVEL_OK]
    assert "SC: 60,00 kN de reação ÷ 5,00 kN/m² = 12,0 m²" in r[em.NIVEL_INFO]
    assert "PP: peso do modelo = 9,00 kN" in r[em.NIVEL_INFO]


@pytest.mark.parametrize(
    ("peso_kN", "nivel", "trecho"),
    [
        (9.1, pc.NIVEL_OK, "bate com a estrutura"),
        (9.0 / 1.4, pc.NIVEL_ERRO, "parece majorado (γ ≈ 1,40)"),
        (1.3, pc.NIVEL_ERRO, "leva só a gravidade"),
        (12.0, pc.NIVEL_ATENCAO, "pesa menos que a estrutura"),
    ],
)
def test_pp_conferido_contra_o_peso_da_estrutura(peso_kN, nivel, trecho):
    r = niveis(
        em.conferir_reacoes(importar("PP"), plano_do_portico(), peso_da_estrutura_kN=peso_kN)
    )
    assert trecho in r[nivel]
    assert "Monte a Lista de material" not in r[em.NIVEL_INFO]
    sem_lista = niveis(em.conferir_reacoes(importar("PP"), plano_do_portico()))
    assert "Monte a Lista de material" in sem_lista[em.NIVEL_INFO]


def test_forcas_recebidas_gama_vezes_denunciam_estudo_majorado():
    # O modelo recebeu 8 kN de vento; o plano tem 8 ÷ 1,4: o estudo foi majorado por 1,4.
    r = niveis(em.conferir_reacoes(importar("W0"), plano_do_portico(vento_kN=8.0 / 1.4)))
    assert "As reações são 1,40 vez as forças: o estudo parece majorado" in r[pc.NIVEL_ERRO]
    assert "cargas características" in r[pc.NIVEL_ERRO]


def test_conferencia_usa_a_quantidade_das_cargas():
    r = niveis(em.conferir_reacoes(importar("W0"), plano_do_portico(vento_kN=8.0, quantidade=4)))
    assert "W0: as reações equilibram" in r[pc.NIVEL_OK]


def test_conferencia_aponta_carga_que_falta_no_modelo():
    r = niveis(em.conferir_reacoes(importar("W0"), plano_do_portico(vento_kN=10.0)))
    assert "W0: o plano soma (10,00; 0,00; 0,00) kN" in r[pc.NIVEL_ATENCAO]


def test_conferencia_aponta_reacao_horizontal_num_caso_vertical():
    dados = importar("SC", com_reacoes=False)
    reacoes = em.ler_arquivo(sw.csv_reacoes("SC", extra_z_N=-3146.0), "r.csv").reacoes
    dados = em.com_reacoes(dados, "SC", reacoes, "r.csv")
    r = niveis(em.conferir_reacoes(dados, plano_do_portico()))
    assert (
        "SC: o plano só tem carga vertical, mas as reações horizontais somam 3,15 kN"
        in r[pc.NIVEL_ATENCAO]
    )


def test_conferencia_de_gravidade_invertida_e_de_reacoes_ausentes():
    dados = importar("PP", com_reacoes=False)
    r = niveis(em.conferir_reacoes(dados, plano_do_portico()))
    assert "PP: falta o arquivo de reações" in r[pc.NIVEL_ATENCAO]
    assert "ainda sem esforços do modelo: SC, W0, W180" in r[pc.NIVEL_ATENCAO]
    invertida = em.Reacoes(modelo=(0.0, -9.0, 0.0))
    r2 = niveis(
        em.conferir_reacoes(em.com_reacoes(dados, "PP", invertida, "r"), plano_do_portico())
    )
    assert "para baixo" in r2[pc.NIVEL_ERRO]


def test_caso_fora_do_plano_e_avisado():
    dados = importar("PP")
    dados = em.com_caso(
        dados, em.caso_do_arquivo(em.ler_arquivo(sw.csv_forcas_da_viga("SC"), "x.csv"), "EQ")
    )
    r = niveis(em.conferir_reacoes(dados, plano_do_portico()))
    assert "EQ: falta o arquivo de reações" in r[pc.NIVEL_ATENCAO]


# ------------------------------------------------------------------ envoltória
def combinado_a_mao(dados, plano, membro, componente):
    """Mínimo e máximo do componente em todas as combinações ELU e pontos, calculados à parte."""
    lista = pc.combinacoes(plano, [comb.ELU_NORMAL])
    valores = []
    pontos = {k: dados.casos[k].membros[membro] for k in dados.casos}
    for c in lista:
        for j in range(len(pontos["PP"])):
            valores.append(
                sum(c.fatores.get(k, 0.0) * getattr(pontos[k][j], componente) for k in dados.casos)
            )
    return min(valores), max(valores)


def test_envoltoria_ponto_a_ponto_bate_com_a_conta_a_mao():
    dados = importar("PP", "SC", "W0", "W180")
    plano = plano_do_portico()
    r = em.envoltoria(dados, plano, [comb.ELU_NORMAL])
    assert r.combinacoes == 8 and r.casos == ("PP", "SC", "W0", "W180") and not r.avisos
    pilar = next(m for m in r.membros if m.membro == PILAR)
    assert pilar.metodo == "ponto a ponto"
    menor_n, _ = combinado_a_mao(dados, plano, PILAR, "n")
    assert pilar.compressao.valor == pytest.approx(menor_n)
    assert pilar.compressao.valor == pytest.approx(-52.6, abs=0.05)  # o mini exemplo
    assert pilar.tracao is None
    menor_m, maior_m = combinado_a_mao(dados, plano, PILAR, "m2")
    assert pilar.m2.valor == pytest.approx(max(abs(menor_m), abs(maior_m)))
    viga = next(m for m in r.membros if m.membro == VIGA)
    assert viga.m2.valor == pytest.approx(45.07, abs=0.05)  # meio do vão, C01
    assert viga.m2.combinacao == "C01-ELU" and "elemento" in viga.m2.ponto


def test_envoltoria_com_numeracao_diferente_combina_pela_ordem():
    dados = importar("PP", "SC")
    outra = em.ler_arquivo(sw.csv_forcas_da_viga("W0", ids={101: 9001}), "w0.csv")
    dados = em.com_caso(dados, em.caso_do_arquivo(outra, "W0"))
    r = em.envoltoria(dados, plano_do_portico(), [comb.ELU_NORMAL])
    pilar = next(m for m in r.membros if m.membro == PILAR)
    assert pilar.metodo == "pela ordem dos elementos"
    assert any("numeração" in a for a in r.avisos)
    assert any("W180" not in c for c in r.casos)


def test_envoltoria_conservadora_quando_faltam_pontos():
    dados = importar("PP", "SC", "W0", "W180")
    sc_caso = dados.casos["SC"]
    menos = dict(sc_caso.membros)
    # O fim 2 do 1º elemento e o fim 1 do 2º são o mesmo nó (meia altura): nada se perde.
    menos[PILAR] = menos[PILAR][:1] + menos[PILAR][2:]
    dados = em.com_caso(dados, em.CasoImportado(**{**sc_caso.__dict__, "membros": menos}))
    r = em.envoltoria(dados, plano_do_portico(), [comb.ELU_NORMAL])
    pilar = next(m for m in r.membros if m.membro == PILAR)
    assert pilar.metodo.startswith("soma dos máximos")
    exato = em.envoltoria(importar("PP", "SC", "W0", "W180"), plano_do_portico(), [comb.ELU_NORMAL])
    pilar_exato = next(m for m in exato.membros if m.membro == PILAR)
    assert pilar.compressao.valor <= pilar_exato.compressao.valor + 1e-9
    assert pilar.m2.valor >= pilar_exato.m2.valor - 1e-9


def test_sem_casos_do_plano_nao_combina():
    r = em.envoltoria(em.EsforcosDoModelo(), plano_do_portico(), [comb.ELU_NORMAL])
    assert r.membros == () and r.avisos


def test_tabela_e_csv_da_envoltoria():
    dados = em.com_membros(
        importar("PP", "SC", "W0", "W180"),
        {PILAR: em.ConfiguracaoDoMembro("W 200 x 35,9 (H)", "Pilar", em.EIXO_M2)},
    )
    r = em.envoltoria(dados, plano_do_portico(), [comb.ELU_NORMAL])
    linhas = em.linhas_da_envoltoria(dados, r)
    pilar = next(linha for linha in linhas if linha[0] == PILAR)
    assert pilar[1] == "Pilar" and pilar[2] == "W 200 x 35,9 (H)"
    assert pilar[3] == pytest.approx(-52.6, abs=0.05) and pilar[5] == ""
    conteudo = em.csv_da_envoltoria(dados, r).decode("utf-8-sig")
    assert conteudo.splitlines()[0].split(";") == list(em.COLUNAS_ENVOLTORIA)
