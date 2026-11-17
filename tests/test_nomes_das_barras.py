"""Nomes das barras: o papel pelo nome, a sugestão dos nomes, o arquivo da macro e a volta dela.

O padrão (``core/papel_pelo_nome.py``) é o contrato entre o programa, a página e a macro
``renomear_corpos.bas``: o prefixo diz o papel e o resto, onde a peça está. A leitura do modelo usa
o papel do nome quando a geometria não o contradiz; o perfil declarado (PERFIL do item) vale como o
nome e a descrição juntos; as trocas guardadas no projeto casam os estudos rodados antes da troca.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace

import pytest

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import nomes_das_barras as nb
from core import papel_pelo_nome as pn
from core import piso_do_modelo as pm
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core import vento_por_barras as vpb
from tests import dados_solidworks as sw
from tests.test_esforcos_modelo import PILAR, VIGA, importar, plano_do_portico

H = 3.0


def barra(nome, a, b, item="", descricao="", forma="BARRA", area_mm2=5970.0, **mais):
    comprimento = math.dist(a, b)
    return ld.CorpoDoModelo(
        nome,
        item,
        descricao,
        tuple(float(v) for v in a),
        tuple(float(v) for v in b),
        comprimento,
        area_mm2 * comprimento / 1e6,
        forma,
        (201.0, 165.0),
        (1.0, 0.0, 0.0),
        **mais,
    )


def chapa(nome, pontos, espessura=0.00635):
    xs = [p[0] for p in pontos]
    zs = [p[2] for p in pontos]
    y = pontos[0][1]
    largura, profundidade = max(xs) - min(xs), max(zs) - min(zs)
    return ld.CorpoDoModelo(
        nome,
        "Item48",
        "Chapa",
        (min(xs), y, min(zs)),
        (max(xs), y, min(zs)),
        max(largura, profundidade),
        largura * profundidade * espessura,
        "CHAPA",
        (min(largura, profundidade) * 1000, espessura * 1000),
        None,
        tuple(tuple(float(v) for v in p) for p in pontos),
    )


def plataforma(**trocar_nomes) -> ld.GeometriaDoModelo:
    """Plataforma de 10 × 4 m a 3 m: 6 pilares (x = 0, 5, 10; z = 0, 4), vigas no contorno e nos
    eixos, uma secundária no meio, um X de contraventamento, uma mão-francesa, piso e uma placa."""
    corpos = []
    k = 0
    for x in (0, 5, 10):
        for z in (0, 4):
            k += 1
            corpos.append(
                barra(f"Aparar/Estender12[{k}]", (x, 0, z), (x, H, z), "W8x31<1>", "W8x31")
            )
    k = 0
    for z in (0, 4):
        for x0, x1 in ((0, 5), (5, 10)):
            k += 1
            corpos.append(
                barra(
                    f"Canal c C8X13.75(1)[{k}]", (x0, H, z), (x1, H, z), "C8x13.75<2>", "C8x13.75"
                )
            )
    for x in (0, 5, 10):
        k += 1
        corpos.append(
            barra(f"Canal c C8X13.75(1)[{k}]", (x, H, 0), (x, H, 4), "C8x13.75<2>", "C8x13.75")
        )
    corpos.append(barra("Membro estrutural3[1]", (0, H, 2), (10, H, 2), "C6<3>", "C6x8.2"))
    corpos.append(barra("Diagonal sobe", (0, 0, 0), (5, H, 0), "L<4>", "L2.5X2.5X0.25"))
    corpos.append(barra("Diagonal desce", (5, 0, 0), (0, H, 0), "L<4>", "L2.5X2.5X0.25"))
    corpos.append(
        barra("Membro estrutural9[1]", (10, 2.2, 4), (9.0, H, 4), "L<4>", "L2.5X2.5X0.25")
    )
    corpos.append(
        chapa("Chapa1", [(0, H + 0.1, 0), (10, H + 0.1, 0), (10, H + 0.1, 4), (0, H + 0.1, 4)])
    )
    corpos.append(
        chapa(
            "Chapa de base1",
            [(-0.15, 0, -0.15), (0.15, 0, -0.15), (0.15, 0, 0.15), (-0.15, 0, 0.15)],
        )
    )
    corpos = [replace(c, nome=trocar_nomes.get(c.nome, c.nome)) for c in corpos]
    return ld.GeometriaDoModelo(
        corpos=tuple(corpos),
        peca="plataforma.SLDPRT",
        configuracao="Padrao",
        gerado_em="2026-11-17 10:00",
    )


def nomes_de(plano: nb.PlanoDeNomes) -> dict[str, str]:
    return {s.corpo: s.nome for s in plano.sugestoes}


def aplicar(g: ld.GeometriaDoModelo, plano: nb.PlanoDeNomes) -> ld.GeometriaDoModelo:
    """O esqueleto como a macro deixaria: cada corpo com o nome novo."""
    return replace(g, corpos=tuple(replace(c, nome=plano.da(c.nome).nome) for c in g.corpos))


# ------------------------------------------------------------------ o papel pelo nome
@pytest.mark.parametrize(
    ("nome", "prefixo", "pelo_codigo"),
    [
        ("P-A1", "P", True),
        ("p-a1", "P", True),
        ("P-A1[2]", "P", True),  # o [n] do membro
        ("PS-N1-01", "PS", True),  # piso, não pilar
        ("PC-N0-01", "PC", True),
        ("LG-N0-01", "LG", True),
        ("MF-N1-01", "MF", True),
        ("P1", "P", True),  # a forma curta de costume
        ("V101", "V", True),
        ("C-Channel", "C", True),
        ("W200x31,3 - Pilar", "P", False),  # o papel por extenso (o roteiro antigo sugeria)
        ("W200x31,3 - Pilar[2]", "P", False),
        ("Viga de borda", "V", False),
        ("Mão-francesa 2", "MF", False),
        ("guarda_corpo", "GC", False),
        ("Corrimão superior", "GC", False),
        ("Longarina 1a", "LG", False),
    ],
)
def test_papel_pelo_nome(nome, prefixo, pelo_codigo):
    lido = pn.papel_do_nome(nome)
    assert lido is not None and lido.papel.prefixo == prefixo and lido.pelo_codigo is pelo_codigo


@pytest.mark.parametrize(
    "nome",
    [
        "Aparar/Estender12[1]",  # os nomes que o SolidWorks dá sozinho
        "Membro estrutural1[1]",
        "Canal c C8X13.75(1)[2]",
        "Ângulo l L2.5X2.5X0.25(1)[1]",
        'U 8"x17,1 - Plataforma',
        "Escada",  # lugar, não papel
        "Pilarete",
        "Chapa metálica1",
        "Reforço1",
        "C",  # a letra sozinha (muita peça de teste se chama assim)
        "P[3]",
        "C12",  # pode ser um perfil C de 12"
        "PS1",
        "C-8X11.5",  # perfil, não contraventamento
        "C-Channel 8X11.5",
        "",
    ],
)
def test_nomes_que_nao_dizem_papel(nome):
    assert pn.papel_do_nome(nome) is None


def test_nome_do_corpo_no_nome_da_viga_do_simulation():
    assert pn.corpo_do_nome("Viga-3(P-A1)") == "P-A1"
    assert pn.corpo_do_nome("Beam-4(V-N1-01)") == "V-N1-01"
    assert pn.corpo_do_nome("Viga-2(Canal c C8X13.75(1)[2])") == "Canal c C8X13.75(1)[2]"
    assert pn.corpo_do_nome("Canal c C8X13.75(1)") == "Canal c C8X13.75(1)"  # corpo passa direto
    assert pn.e_nome_codificado("Viga-3(V-N1-L1-L2)")
    assert not pn.e_nome_codificado("Viga-3(Canal c C8X13.75(1)[2])")


def test_letra_da_grade_nao_vira_cantoneira_nem_perfil():
    # "L1" no nome seria lido como cantoneira de 1": o padrão não diz perfil.
    assert em.perfil_do_nome("V-N1-L1-L2") is None
    assert em.perfil_do_nome("Viga-3(V-N1-L1-L2)") is None
    assert em.perfil_do_nome("C-N0-L1-M2") is None
    # O nome por extenso continua dizendo o perfil.
    assert em.perfil_do_nome("W200x31,3 - Pilar") is not None


@pytest.mark.parametrize(
    ("papel", "angulo", "forma", "vale", "trecho"),
    [
        (pn.PILAR, 90, "BARRA", True, ""),
        (pn.PILAR, 60, "BARRA", True, "pilar inclinado"),
        (pn.PILAR, 30, "BARRA", False, "30°"),
        (pn.VIGA, 0, "BARRA", True, ""),
        (pn.VIGA, 35, "BARRA", True, "viga inclinada"),
        (pn.VIGA, 80, "BARRA", False, "80°"),
        (pn.DEGRAU, 30, "BARRA", False, "30°"),
        (pn.LONGARINA, 35, "BARRA", True, ""),
        (pn.LONGARINA, 2, "BARRA", True, "em nível"),
        (pn.CONTRAVENTAMENTO, 90, "BARRA", True, ""),
        (pn.PILAR, 90, "BLOCO", True, ""),  # toco de pilar
        (pn.PILAR, None, "CHAPA", False, "chapa"),  # papel de barra numa chapa
        (pn.PISO, 0, "BARRA", False, "barra"),  # papel de chapa numa barra
        (pn.PISO, 20, "CHAPA", True, "rampa"),
        (pn.PISO, 80, "CHAPA", False, "em pé"),
        (pn.LANCE, 3, "CHAPA", False, "em nível"),
        (pn.LANCE, 35, "CHAPA", True, ""),
        (pn.CHAPA, 90, "CHAPA", True, ""),
        (pn.PILAR, None, "", True, ""),  # sem a medida, o nome vale
    ],
)
def test_o_nome_contra_a_geometria(papel, angulo, forma, vale, trecho):
    avaliacao = pn.avaliar(papel, angulo, forma)
    assert avaliacao.vale is vale and trecho in avaliacao.nota


@pytest.mark.parametrize(
    ("nome", "problema"),
    [
        ("P-A1", ""),
        ("V-N1-A1-A2", ""),
        ("C-N0_01.b", ""),
        ("P A1", "só letras"),
        ("P-Á1", "só letras"),
        ("P-A1;", "só letras"),
        ("X-1", "prefixo"),
        ("Viga-1", "prefixo"),
        ("", "vazio"),
        ("P-" + "A" * 70, "60"),
    ],
)
def test_nome_novo_no_padrao(nome, problema):
    texto = pn.problema_do_nome(nome)
    assert (texto == "") if not problema else (problema in texto)


# ------------------------------------------------------------------ a leitura do modelo usa o nome
def test_tipo_pelo_nome_quando_a_posicao_deixa():
    longarina = barra("LG-N0-01", (0, 0, 0), (3, 2, 0))
    assert ld.tipo_pela_posicao(longarina, "Y")[0] == ld.TIPO_CONTRAVENTAMENTO
    tipo, motivo = ld.tipo_pela_geometria(longarina, "Y")
    assert tipo == ld.TIPO_VIGA and "longarina de escada pelo nome" in motivo
    montante = barra("GC-N1-01", (0, 3, 0), (0, 4.1, 0))
    assert ld.tipo_pela_geometria(montante, "Y")[0] == pn.TIPO_OUTRO  # não é pilar
    pelo_extenso = barra("W200x31,3 - Pilar[1]", (0, 0, 0), (0, 3, 0))
    assert ld.tipo_pela_geometria(pelo_extenso, "Y") == (
        ld.TIPO_PILAR,
        "pilar pelo nome no SolidWorks",
    )


def test_nome_que_contradiz_a_posicao_nao_vale():
    deitado = barra("P-A1", (0, 3, 0), (5, 3, 0))
    tipo, motivo = ld.tipo_pela_geometria(deitado, "Y")
    assert tipo == ld.TIPO_VIGA
    assert "o nome diz pilar, mas a barra está a 0° da horizontal: vale a posição" in motivo
    declarado = ld.papel_declarado(deitado, "Y")
    assert declarado is not None and not declarado.vale and declarado.tipo == ""


def _com_nomes(conteudo: bytes, trocas: dict[str, str]) -> bytes:
    for antigo, novo in trocas.items():
        conteudo = conteudo.replace(antigo.encode("cp1252"), novo.encode("cp1252"))
    return conteudo


def importar_com_nomes(trocas: dict[str, str], *casos: str) -> em.EsforcosDoModelo:
    dados = em.EsforcosDoModelo()
    for caso in casos:
        arquivo = em.ler_arquivo(_com_nomes(sw.csv_forcas_da_viga(caso), trocas), f"{caso}.csv")
        dados = em.com_caso(dados, em.caso_do_arquivo(arquivo, caso))
        reacoes = em.ler_arquivo(sw.csv_reacoes(caso), f"{caso}-reacao.csv").reacoes
        dados = em.com_reacoes(dados, caso, reacoes, f"{caso}-reacao.csv")
    return dados


def esqueleto_com_nomes(trocas: dict[str, str]) -> ld.GeometriaDoModelo:
    corpos = {trocas.get(nome, nome): dados for nome, dados in sw.CORPOS.items()}
    return ld.ler_esqueleto(sw.csv_esqueleto(corpos=corpos), "portico_esqueleto.csv")


NOMES_DO_PORTICO = {
    "Aparar/Estender12[1]": "P-A1",
    "Canal c C8X13.75(1)[2]": "V-N1-A1-A2",
    "Aparar/Estender12[2]": "P-A2",
}


def test_barras_com_o_papel_no_nome():
    dados = importar_com_nomes(NOMES_DO_PORTICO, "PP", "SC")
    g = esqueleto_com_nomes(NOMES_DO_PORTICO)
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    pilar, viga = leituras["Viga-1(P-A1)"], leituras["Viga-2(V-N1-A1-A2)"]
    assert (pilar.tipo_sugerido, pilar.papel_pelo_nome) == (ld.TIPO_PILAR, "Pilar")
    assert (viga.tipo_sugerido, viga.papel_pelo_nome) == (ld.TIPO_VIGA, "Viga")
    assert "pelo nome no SolidWorks" in pilar.motivo_do_tipo and not pilar.nome_contradiz
    # O nome do padrão não diz perfil: o perfil sai do esqueleto, como antes.
    assert viga.perfil_sugerido == "W 310 x 32,7"
    # Sem o esqueleto, o nome entre parênteses no Simulation já diz o papel.
    sem = {lb.barra: lb for lb in ld.ler_barras(dados)}
    assert sem["Viga-1(P-A1)"].tipo_sugerido == ld.TIPO_PILAR
    assert sem["Viga-1(P-A1)"].papel_pelo_nome == "Pilar"


def test_nome_trocado_vira_atencao_no_diagnostico():
    trocas = {**NOMES_DO_PORTICO, "Aparar/Estender12[1]": "V-N0-01"}  # o pilar chamado de viga
    dados = importar_com_nomes(trocas, "PP", "SC")
    g = esqueleto_com_nomes(trocas)
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    errado = leituras["Viga-1(V-N0-01)"]
    assert errado.tipo_sugerido == ld.TIPO_PILAR  # vale a posição
    assert errado.nome_contradiz.startswith("o nome diz viga, mas a barra está a 90°")
    achados = ld.diagnosticar(dados, plano_do_portico(), g, list(leituras.values()))
    contradiz = next(a for a in achados if a.titulo == "Nome que contradiz a posição")
    assert contradiz.nivel == pc.NIVEL_ATENCAO and contradiz.barras == ("Viga-1(V-N0-01)",)


def test_tipo_da_tabela_diferente_do_nome():
    dados = importar_com_nomes(NOMES_DO_PORTICO, "PP", "SC")
    g = esqueleto_com_nomes(NOMES_DO_PORTICO)
    dados = em.com_membros(dados, {"Viga-1(P-A1)": em.ConfiguracaoDoMembro(tipo="Viga")})
    achados = ld.diagnosticar(dados, plano_do_portico(), g)
    achado = next(a for a in achados if a.titulo == "Tipo diferente do nome no SolidWorks")
    assert "viga na tabela, pilar no nome" in achado.texto
    assert "Tipo diferente da posição no modelo" not in {a.titulo for a in achados}


# ------------------------------------------------------------------ as trocas guardadas no projeto
def _renomeacoes(g_antes: ld.GeometriaDoModelo, trocas: dict[str, str]) -> tuple:
    saida = []
    for c in g_antes.corpos:
        if c.nome in trocas:
            meio = tuple((a + b) / 2 for a, b in zip(c.inicio, c.fim, strict=True))
            saida.append(
                pn.Renomeacao(c.nome, trocas[c.nome], meio, c.comprimento_m, "2026-11-17T10:00:00")
            )
    return tuple(saida)


def test_estudo_de_antes_da_troca_acha_o_esqueleto_novo():
    dados = importar("PP", "SC")  # o Simulation ainda com os nomes antigos
    g_novo = esqueleto_com_nomes(NOMES_DO_PORTICO)
    # Sem as trocas guardadas: nenhum corpo casa, o esqueleto parece de outro modelo.
    assert ld.esqueleto_de_outro_modelo(g_novo, dados)
    g = replace(g_novo, renomeacoes=_renomeacoes(esqueleto_com_nomes({}), NOMES_DO_PORTICO))
    casamento = ld.correspondencia(g, dados.nomes_dos_membros, dados)
    assert casamento.corpos[PILAR].nome == "P-A1" and casamento.corpos[VIGA].nome == "V-N1-A1-A2"
    assert set(casamento.pelos_nomes_trocados) == set(dados.nomes_dos_membros)
    assert not ld.esqueleto_de_outro_modelo(g, dados)
    achados = ld.diagnosticar(dados, plano_do_portico(), g)
    assert (
        next(a for a in achados if a.titulo == "Nomes trocados depois do estudo").nivel
        == em.NIVEL_INFO
    )


def test_e_o_esqueleto_de_antes_acha_o_estudo_novo():
    dados = importar_com_nomes(NOMES_DO_PORTICO, "PP")
    g_velho = esqueleto_com_nomes({})
    g = replace(g_velho, renomeacoes=_renomeacoes(g_velho, NOMES_DO_PORTICO))
    casamento = ld.correspondencia(g, dados.nomes_dos_membros, dados)
    assert casamento.corpos["Viga-1(P-A1)"].nome == "Aparar/Estender12[1]"


def test_troca_de_um_corpo_que_saiu_do_lugar_nao_casa():
    dados = importar("PP")
    g_novo = esqueleto_com_nomes(NOMES_DO_PORTICO)
    trocas = _renomeacoes(esqueleto_com_nomes({}), NOMES_DO_PORTICO)
    longe = tuple(replace(r, centro=(r.centro[0] + 1.0, r.centro[1], r.centro[2])) for r in trocas)
    casamento = ld.correspondencia(
        replace(g_novo, renomeacoes=longe), dados.nomes_dos_membros, dados
    )
    assert not casamento.corpos and not casamento.pelos_nomes_trocados


def test_trocas_em_cadeia_e_nome_original():
    trocas = (
        pn.Renomeacao("A[1]", "V-N1-01", (0, 0, 0), 1.0, "2026-11-01"),
        pn.Renomeacao("V-N1-01", "V-N1-A1-A2", (0, 0, 0), 1.0, "2026-11-02"),
    )
    assert [n for n, _ in pn.nomes_equivalentes("A[1]", trocas)] == ["V-N1-01", "V-N1-A1-A2"]
    assert ld.nome_original("V-N1-A1-A2", trocas) == "A[1]"
    g = ld.GeometriaDoModelo(corpos=(barra("V-N1-A1-A2", (0, 0, -0.5), (0, 0, 0.5)),))
    assert nb.trocas_feitas(trocas, g) == {"A[1]": "V-N1-A1-A2", "V-N1-01": "V-N1-A1-A2"}


def test_projeto_guarda_e_le_as_trocas_sem_quebrar_com_lixo():
    trocas = _renomeacoes(esqueleto_com_nomes({}), NOMES_DO_PORTICO)
    escolhas = nb.Escolhas(eixo_vertical="Y", papeis={"x": "P"}, perfis={"C8<1>": ""})
    campos = nb.campos_do_projeto({}, escolhas, trocas)
    projeto = {**campos, "geometria_do_modelo": ld.para_dicionario(esqueleto_com_nomes({}))}
    assert pn.renomeacoes_do_projeto(projeto) == trocas
    assert ld.geometria_do_projeto(projeto).renomeacoes == trocas
    lidas = nb.escolhas_do_projeto(projeto)
    assert lidas.papeis == {"x": "P"} and lidas.perfis == {"C8<1>": ""}  # vazio também é escolha
    # Dados estragados: tudo é pulado, nada levanta.
    estragado = {
        pn.CHAVE_DO_PROJETO: {
            "renomeacoes": [
                None,
                {"antigo": "a"},
                {"antigo": "a", "novo": "a", "centro": [0, 0, 0], "comprimento_m": 1},
                3,
            ],
            "papeis": {"a": "XX", "b": "P"},
            "sem_troca": "nada",
            "perfis": [1, 2],
        }
    }
    assert pn.renomeacoes_do_projeto(estragado) == ()
    assert nb.escolhas_do_projeto(estragado) == nb.Escolhas(papeis={"b": "P"})
    assert pn.renomeacoes_do_projeto(None) == () and nb.escolhas_do_projeto(None) == nb.Escolhas()


def test_juntar_trocas_sem_repetir_e_mantendo_a_confirmacao():
    a = pn.Renomeacao("A", "B", (0, 0, 0), 1.0, "2026-11-01", confirmada=True)
    b = replace(a, quando="2026-11-02", confirmada=False)
    c = pn.Renomeacao("C", "D", (0, 0, 0), 1.0, "2026-11-03")
    juntas = nb.juntar_renomeacoes([a], [b, c])
    assert [(r.antigo, r.confirmada) for r in juntas] == [("A", True), ("C", False)]


# ------------------------------------------------------------------ a sugestão dos nomes
def test_grade_niveis_e_nomes_da_plataforma():
    g = plataforma()
    plano = nb.sugerir(g, "Y")
    grade = plano.grade
    assert [r for r, _ in grade.numeros] == ["1", "2", "3"]
    assert [r for r, _ in grade.letras] == ["A", "B"]  # de baixo para cima na vista Superior
    assert len(grade.niveis) == 1 and grade.niveis[0] == pytest.approx(3.0, abs=0.05)
    nomes = nomes_de(plano)
    assert nomes["Aparar/Estender12[1]"] == "P-B1"  # x = 0, z = 0
    assert nomes["Aparar/Estender12[2]"] == "P-A1"  # x = 0, z = 4
    assert nomes["Canal c C8X13.75(1)[1]"] == "V-N1-B1-B2"
    assert nomes["Canal c C8X13.75(1)[5]"] == "V-N1-A1-B1"  # em ordem de grade
    assert nomes["Membro estrutural3[1]"] == "V-N1-01"  # secundária: numerada
    assert nomes["Diagonal sobe"] == "C-N0-B1-B2"  # da ponta de baixo para a de cima
    assert nomes["Diagonal desce"] == "C-N0-B2-B1"
    assert nomes["Membro estrutural9[1]"] == "MF-N1-01"  # mão-francesa pela geometria
    assert nomes["Chapa1"] == "PS-N1-01"
    assert nomes["Chapa de base1"] == "CH-N0-01"
    assert len(set(nomes.values())) == len(nomes) and not nb.conferir(plano, g)
    assert all(pn.problema_do_nome(n) == "" for n in nomes.values())
    # O que o nome diz é o que a página escolheu.
    assert all(pn.papel_do_nome(s.nome).papel is s.papel for s in plano.sugestoes)


def test_planta_igual_a_do_vento():
    for eixo in ("Y", "Z"):
        assert nb.planta((1.0, 2.0, 3.0), eixo) == vpb.para_a_planta((1.0, 2.0, 3.0), eixo)[:2]


def test_rodar_de_novo_nao_troca_nada():
    g = plataforma()
    plano = nb.sugerir(g, "Y")
    depois = nb.sugerir(aplicar(g, plano), "Y")
    assert depois.trocas == {} and {s.origem_do_nome for s in depois.sugestoes} == {nb.MANTIDO}
    # Refazer gera de novo — e chega aos mesmos nomes, porque o modelo não mudou.
    refeito = nb.sugerir(aplicar(g, plano), "Y", refazer=True)
    assert refeito.trocas == {}


def test_nome_no_padrao_que_ja_existe_fica_e_o_gerado_desvia_dele():
    g = plataforma(**{"Membro estrutural3[1]": "V-N1-B1-B2"})  # a secundária pegou o nome
    nomes = nomes_de(nb.sugerir(g, "Y"))
    assert nomes["V-N1-B1-B2"] == "V-N1-B1-B2"  # fica
    assert nomes["Canal c C8X13.75(1)[1]"] == "V-N1-B1-B2-2"  # o gerado desvia


def test_escolhas_da_tabela():
    g = plataforma()
    plano = nb.sugerir(
        g,
        "Y",
        escolhidos={"Membro estrutural3[1]": "C", "Diagonal sobe": "XX"},  # XX: ignorado
        a_mao={"Chapa1": "PS-MEZANINO"},
        sem_troca=("Chapa de base1",),
    )
    nomes = nomes_de(plano)
    assert nomes["Membro estrutural3[1]"] == "C-N1-01"
    assert plano.da("Membro estrutural3[1]").motivo == nb.ESCOLHIDO
    assert nomes["Diagonal sobe"] == "C-N0-B1-B2"
    assert nomes["Chapa1"] == "PS-MEZANINO" and plano.da("Chapa1").origem_do_nome == nb.A_MAO
    assert nomes["Chapa de base1"] == "Chapa de base1" and "Chapa de base1" not in plano.trocas
    assert not nb.conferir(plano, g)


def test_conferencia_barra_o_que_daria_errado():
    g = plataforma()
    plano = nb.sugerir(
        g,
        "Y",
        escolhidos={"Aparar/Estender12[1]": "V"},  # um pilar chamado de viga
        a_mao={"Chapa1": "V-N1-02", "Membro estrutural3[1]": "V-N1-02", "Diagonal sobe": "C N0"},
    )
    problemas = " | ".join(nb.conferir(plano, g))
    assert "viga: a barra está a 90° da horizontal" in problemas
    assert "o nome começa com V (viga), mas o papel escolhido é PS (piso)" in problemas
    assert "“V-N1-02” para 2 corpos" in problemas
    assert "C N0" in problemas and "só letras" in problemas


def test_longarina_e_degrau_sem_as_chapas_da_escada():
    corpos = (
        barra("P1", (0, 0, 0), (0, 3, 0)),
        barra("Lg a", (1, 0, 0), (4, 2.5, 0)),
        barra("Lg b", (1, 0, 1), (4, 2.5, 1)),
        barra("Degrau1", (2.5, 1.25, 0), (2.5, 1.25, 1)),
    )
    escolhidos = {"Lg a": "LG", "Lg b": "LG"}
    plano = nb.sugerir(ld.GeometriaDoModelo(corpos=corpos), "Y", escolhidos=escolhidos)
    assert plano.da("Degrau1").papel is pn.DEGRAU
    assert plano.da("Lg a").nome.startswith("LG-N0-")
    # Com o nome de longarina, a leitura do piso conta a escada mesmo sem as chapas dela.
    com_nomes = ld.GeometriaDoModelo(
        corpos=tuple(replace(c, nome=plano.da(c.nome).nome) for c in corpos)
    )
    leitura = pm.ler(com_nomes, "Y")
    assert dict(leitura.barras)[pm.PAPEL_LONGARINA] == 2


def test_viga_do_patamar_nas_pontas_das_longarinas_nao_e_degrau():
    corpos = (
        barra("P1", (0, 0, 0), (0, 3, 0)),
        barra("Lg a", (1, 0, 0), (4, 2.5, 0)),
        barra("Lg b", (1, 0, 1), (4, 2.5, 1)),
        barra("Patamar", (4, 2.5, 0), (4, 2.5, 1)),  # liga as pontas de cima das duas
    )
    plano = nb.sugerir(
        ld.GeometriaDoModelo(corpos=corpos), "Y", escolhidos={"Lg a": "LG", "Lg b": "LG"}
    )
    assert plano.da("Patamar").papel is pn.VIGA


def test_lance_de_escada_e_do_nivel_onde_comeca():
    # O lance vai de +1,0 a +3,0 m: o meio (+2,0) fica mais perto do N1 (+3,0), o começo do N0.
    lance = chapa("Lance", [(0, 1.0, 0), (2, 3.0, 0), (2, 3.0, 1), (0, 1.0, 1)])
    corpos = (
        barra("P1", (0, 0, 0), (0, 3, 0)),
        barra("Viga", (0, 3, 0), (4, 3, 0)),
        barra("Lg a", (0, 1.0, 0), (2, 3.0, 0)),
        barra("Lg b", (0, 1.0, 1), (2, 3.0, 1)),
        lance,
    )
    plano = nb.sugerir(
        ld.GeometriaDoModelo(corpos=corpos),
        "Y",
        escolhidos={"Lance": "ES", "Lg a": "LG", "Lg b": "LG"},
    )
    assert plano.da("Lance").nome == "ES-N0-01"  # começa no chão, mesmo com o meio mais perto do N1


def test_chapa_sem_carga_e_patamar_pelo_nome_na_leitura_do_piso():
    g = plataforma(**{"Chapa1": "PT-N1-01", "Chapa de base1": "CH-N0-01"})
    leitura = pm.ler(g, "Y")
    assert {c.nome: c.tipo for c in leitura.chapas} == {"PT-N1-01": pm.TIPO_PATAMAR}
    assert "patamar pelo nome" in leitura.chapas[0].motivo
    assert {f.nome: f.motivo for f in leitura.fora}["CH-N0-01"].startswith("chapa sem carga")


def test_sem_pilares_os_nomes_saem_numerados():
    corpos = (barra("A", (0, 3, 0), (5, 3, 0)), barra("B", (0, 3, 2), (5, 3, 2)))
    plano = nb.sugerir(ld.GeometriaDoModelo(corpos=corpos), "Y")
    assert sorted(nomes_de(plano).values()) == ["V-N0-01", "V-N0-02"]  # nada abaixo: N0
    assert any("Sem pilares" in a for a in plano.avisos)
    assert any("Nenhum nível de piso" in a for a in plano.avisos)


def test_modelo_com_z_para_cima():
    corpos = (
        barra("pe esquerdo", (0, 0, 0), (0, 0, 3)),
        barra("pe direito", (5, 0, 0), (5, 0, 3)),
        barra("travessa", (0, 0, 3), (5, 0, 3)),
    )
    nomes = nomes_de(nb.sugerir(ld.GeometriaDoModelo(corpos=corpos), "Z"))
    assert nomes == {"pe esquerdo": "P-A1", "pe direito": "P-A2", "travessa": "V-N1-A1-A2"}


# ------------------------------------------------------------------ o arquivo para a macro
def dividir_como_a_macro(linha: str) -> list[str]:
    """O mesmo que DividirLinha na macro: ponto e vírgula, aspas e aspas dobradas."""
    pedacos, atual, entre_aspas, j = [], "", False, 0
    while j < len(linha):
        c = linha[j]
        if entre_aspas:
            if c == '"':
                if linha[j + 1 : j + 2] == '"':
                    atual += '"'
                    j += 1
                else:
                    entre_aspas = False
            else:
                atual += c
        elif c == '"':
            entre_aspas = True
        elif c == ";":
            pedacos.append(atual)
            atual = ""
        else:
            atual += c
        j += 1
    return [*pedacos, atual]


def test_arquivo_para_a_macro():
    g = plataforma(**{"Membro estrutural3[1]": 'U 8"x17,1; meio'})
    plano = nb.sugerir(g, "Y")
    conteudo = nb.arquivo_para_a_macro(
        plano,
        g,
        perfis={"C8x13.75<2>": 'U 8" x 17,10', "Inexistente": "W 200 x 35,9 (H)"},
        quando="2026-11-17T11:00:00",
    )
    texto = conteudo.decode("cp1252")
    assert texto.endswith("\r\n") and "\n" not in texto.replace("\r\n", "")
    linhas = [dividir_como_a_macro(linha) for linha in texto.split("\r\n") if linha]
    chaves = [linha[0] for linha in linhas]
    assert chaves[:6] == ["ARQUIVO", "PECA", "CONFIGURACAO", "ESQUELETO", "DATA", "CORPOS"]
    assert "nomes das barras" in linhas[0][1] and linhas[1][1] == "plataforma.SLDPRT"
    assert linhas[5] == list(nb.COLUNAS_DOS_CORPOS)
    corpos = {linha[1]: linha for linha in linhas if linha[0] == "CORPO"}
    assert len(corpos) == len(plano.trocas)
    secundaria = corpos['U 8"x17,1; meio']  # aspas e ponto e vírgula sobrevivem
    assert secundaria[2] == "V-N1-01" and secundaria[3] == "V" and secundaria[4] == "BARRA"
    assert [float(v) for v in secundaria[5:11]] == [0.0, 3000.0, 2000.0, 10000.0, 3000.0, 2000.0]
    assert float(secundaria[11]) == pytest.approx(10000.0) and float(secundaria[12]) > 0
    perfis = [linha for linha in linhas if linha[0] == "PERFIL"]
    assert perfis == [["PERFIL", "C8x13.75<2>", 'U 8" x 17,10', "Canal c C8X13.75(1)[1]"]]
    assert nb.nome_do_arquivo(g) == "plataforma_nomes.csv"
    # Corpo que fica com o nome não vai ao arquivo.
    plano_sem = nb.sugerir(g, "Y", sem_troca=[c.nome for c in g.corpos])
    assert b"\r\nCORPO;" not in nb.arquivo_para_a_macro(plano_sem, g)


def test_contrato_com_a_macro():
    """As posições que a macro lê são as colunas que o programa escreve, e o relatório e o arquivo
    para desfazer que ela grava são os que o programa lê."""
    macro = nb.macro_de_renomear().decode("ascii")
    assert "\r\n" in macro and "\n" not in macro.replace("\r\n", "")
    colunas = nb.COLUNAS_DOS_CORPOS
    assert "atuais(n) = partes(1)" in macro and colunas.index("ATUAL") == 1
    assert "novos(n) = Trim(partes(2))" in macro and colunas.index("NOVO") == 2
    assert "Val(partes(5 + j)) / 1000#" in macro and colunas.index("X1 (mm)") == 5
    assert "partes(12)" in macro and colunas.index("VOLUME (cm3)") == 12
    assert "UBound(partes) >= 12" in macro and len(colunas) == 13
    perfis = nb.COLUNAS_DOS_PERFIS
    assert "corposDoPerfil(n) = partes(3)" in macro and perfis.index("CORPO DO ITEM") == 3
    assert 'Case "CORPO"' in macro and 'Case "PERFIL"' in macro
    assert 'MARCA_DO_ARQUIVO As String = "nomes das barras"' in macro
    # O arquivo para desfazer tem o mesmo cabeçalho do arquivo de nomes.
    assert '"' + ";".join(colunas) + '"' in macro
    # As situações do relatório são as que o programa reconhece.
    for situacao in (
        nb.SITUACAO_RENOMEADO,
        nb.SITUACAO_PELA_GEOMETRIA,
        nb.SITUACAO_JA_TINHA,
        nb.SITUACAO_PULADO,
    ):
        assert f'"{situacao}"' in macro, situacao
    assert '"RELATORIO;"' in macro and '"TIPO;ANTIGO;NOVO;SITUACAO;MOTIVO"' in macro
    assert 'Const PROPRIEDADE_DO_PERFIL As String = "PERFIL"' in macro
    # A leitura do esqueleto procura a coluna que a exportar_lista_de_corte v7 grava.
    exportar = lm.macro_da_lista_de_corte().decode("ascii")
    assert ';PERFIL"' in exportar and 'UCase(nomes(j)) = "PERFIL"' in exportar


def test_macro_robusta():
    macro = nb.macro_de_renomear().decode("ascii")
    assert "Option Explicit" in macro and "On Error GoTo Falha" in macro
    assert "\r\nFalha:\r\n" in macro and macro.count("    Close\r\n") >= 2
    assert "Case 52, 53, 55, 70, 75, 76" in macro
    # Confere a geometria, troca em duas fases, desfaz o que falha, reconstrói e confere de novo.
    for trecho in (
        "Function Confere(",
        "PelaGeometriaDoCorpo",
        "NomeProvisorio",
        "If Not Renomear(swCorpo, nomesDosCorpos(alvos(i))) Then",
        "swModel.ForceRebuild3 False",
        "depois.Exists(novos(i))",
        "vbYesNo + vbQuestion",  # nada muda sem a confirmação
        "_nomes_aplicados.csv",
        "_nomes_desfazer.csv",
        "GetMassProperties",
        "swCorpo.Name = nomeNovo",
        "StrComp(swCorpo.Name, nomeNovo, vbBinaryCompare) = 0",
        'Environ("USERPROFILE") & "\\Downloads\\"',
        "InputBox",
        "Add3 PROPRIEDADE_DO_PERFIL",
        "Delete2 PROPRIEDADE_DO_PERFIL",
        "UpdateFeatureTree",
        "SetSaveFlag",
    ):
        assert trecho in macro, trecho
    linhas = [linha.strip() for linha in macro.splitlines()]
    blocos_if = [linha for linha in linhas if linha.startswith("If ") and linha.endswith(" Then")]
    assert len(blocos_if) == linhas.count("End If")
    assert sum(linha.startswith("For ") for linha in linhas) == sum(
        linha.startswith("Next") for linha in linhas
    )
    assert sum(linha == "Do" or linha.startswith("Do ") for linha in linhas) == sum(
        linha.startswith("Loop") for linha in linhas
    )
    assert sum(linha.startswith("Select Case") for linha in linhas) == linhas.count("End Select")
    assert sum(linha.startswith(("Sub ", "Function ")) for linha in linhas) == linhas.count(
        "End Sub"
    ) + linhas.count("End Function")
    # Nenhum Format de número: só a data.
    assert all("Format(Now" in linha for linha in macro.splitlines() if "Format(" in linha)


def test_relatorio_da_macro():
    relatorio = (
        'RELATORIO;"Mecanica Toolkit - renomear_corpos v1"\r\n'
        'PECA;"plataforma.SLDPRT"\r\nCONFIGURACAO;"Padrao"\r\nDATA;"2026-11-17 11:05"\r\n'
        'ARQUIVO LIDO;"C:\\obra\\plataforma_nomes.csv"\r\n'
        "TIPO;ANTIGO;NOVO;SITUACAO;MOTIVO\r\n"
        'CORPO;"Aparar/Estender12[1]";"P-B1";RENOMEADO;""\r\n'
        'CORPO;"Aparar/Estender12[7]";"P-A1";RENOMEADO PELA GEOMETRIA;"no arquivo, Aparar/Estender12[2]"\r\n'
        'CORPO;"Chapa1";"PS-N1-01";JA TINHA O NOME;""\r\n'
        'CORPO;"Sumiu[1]";"V-N1-09";PULADO;"o corpo nao esta mais na peca"\r\n'
        'PERFIL;"C8x13.75<2>";"U 8"" x 17,10";GRAVADO;"antes:  "\r\n'
    ).encode("cp1252")
    lido = nb.ler_relatorio_da_macro(relatorio, "plataforma_nomes_aplicados.csv")
    assert lido.peca == "plataforma.SLDPRT" and lido.data == "2026-11-17 11:05"
    assert [(r.antigo, r.novo) for r in lido.trocados] == [
        ("Aparar/Estender12[1]", "P-B1"),
        ("Aparar/Estender12[7]", "P-A1"),
    ]
    assert [r.antigo for r in lido.pulados] == ["Sumiu[1]"] and lido.perfis[
        0
    ].novo == 'U 8" x 17,10'
    g = plataforma()
    trocas = nb.renomeacoes_do_relatorio(lido, g, "2026-11-17T11:10:00")
    assert [(r.antigo, r.novo, r.confirmada) for r in trocas] == [
        ("Aparar/Estender12[1]", "P-B1", True)
    ]
    with pytest.raises(nb.RelatorioInvalido, match="relatório da macro"):
        nb.ler_relatorio_da_macro(b"a;b\r\n1;2\r\n", "x.csv")


def test_plano_de_cargas_com_os_nomes_novos():
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao(
            "SC",
            cargas=[
                pc.CargaDoModelo(
                    "Aparar/Estender12[1] (Viga-1(Aparar/Estender12[1]))", 2.0, "kN/m"
                ),
                pc.CargaDoModelo("Canal c C8X13.75(1)[2]", 3.0, "kN/m"),
                pc.CargaDoModelo("Outro", 1.0, "kN"),
            ],
        ),
    )
    trocas = {"Aparar/Estender12[1]": "P-A1", "Canal c C8X13.75(1)[2]": "V-N1-A1-A2"}
    assert nb.linhas_com_nome_antigo(plano, trocas) == 2
    novo, mudaram = nb.plano_com_os_nomes_novos(plano, trocas)
    assert mudaram == 2
    elementos = [c.elemento for c in novo.acao("SC").cargas]
    assert elementos == ["P-A1 (Viga-1(Aparar/Estender12[1]))", "V-N1-A1-A2", "Outro"]
    assert nb.plano_com_os_nomes_novos(novo, trocas) == (novo, 0)


def test_planta_com_os_nomes():
    g = plataforma()
    plano = nb.sugerir(g, "Y")
    svg = nb.svg_da_planta(plano, g, 1)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    for texto in (">P-A1<", ">V-N1-A1-A2<", ">PS-N1-01<", ">A<", ">3<"):
        assert texto in svg, texto
    assert ">C-N0-B1-B2<" not in svg  # o contraventamento é do N0
    assert ">C-N0-B1-B2<" in nb.svg_da_planta(plano, g, 0)
    vazio = ld.GeometriaDoModelo()
    assert nb.svg_da_planta(nb.sugerir(vazio, "Y"), vazio) == ""


# ------------------------------------------------------------------ o perfil declarado
def corpo_u(nome="Canal[1]", declarado="", area_do=('U 8" x 17,10')) -> ld.CorpoDoModelo:
    perfil = sc.obter_perfil(area_do)
    return ld.CorpoDoModelo(
        nome,
        "C8x13.75<1>",
        "C8x13.75",
        (0.0, 3.0, 0.0),
        (4.0, 3.0, 0.0),
        4.0,
        perfil.area_mm2 * 4.0 / 1e6,
        "BARRA",
        (perfil.altura_mm, perfil.largura_mm),
        (0.0, 1.0, 0.0),
        perfil_declarado=declarado,
    )


def test_perfil_declarado_vale_como_o_nome_e_a_descricao():
    sem = ld.perfil_do_corpo(corpo_u())
    assert sem[0] == 'U 8" x 17,10' and sem[1].startswith("lista de corte (C8x13.75)")
    com = ld.perfil_do_corpo(corpo_u(declarado='U 8" x 17,10'))
    assert com[0] == 'U 8" x 17,10'
    assert com[1].startswith('perfil declarado no SolidWorks (U 8" x 17,10)')
    # Declarado o mais leve e desenhado o mais pesado: vale o declarado (a peça da obra).
    pesado = ld.perfil_do_corpo(corpo_u(declarado='U 8" x 17,10', area_do='U 8" x 20,50'))
    assert pesado[0] == 'U 8" x 17,10' and ld.DESENHO_MAIS_PESADO in pesado[1]


def test_esqueleto_v7_traz_o_perfil_declarado_e_avisa_o_desconhecido():
    conteudo = sw.csv_esqueleto(versao="v6").decode("cp1252")
    linhas = conteudo.split("\r\n")
    linhas[0] = linhas[0].replace("v6", "v7")
    linhas[4] += ";PERFIL"
    linhas[5] += ';"W 200 x 35,9 (H)"'
    linhas[6] += ';"Perfil que nao existe"'
    g = ld.ler_esqueleto("\r\n".join(linhas).encode("cp1252"), "portico_esqueleto.csv")
    assert g.versao_da_macro == "v7"
    assert [c.perfil_declarado for c in g.corpos] == [
        "W 200 x 35,9 (H)",
        "Perfil que nao existe",
        "",
    ]
    (aviso,) = [a for a in g.avisos if a.startswith("Perfil declarado")]
    assert "Perfil que nao existe" in aviso
    # Grava e lê de volta no projeto.
    assert ld.de_dicionario(ld.para_dicionario(g)).corpos == g.corpos


def test_perfis_dos_itens_e_o_que_gravar():
    g = ld.GeometriaDoModelo(
        corpos=(
            corpo_u("Canal[1]"),
            corpo_u("Canal[2]"),
            replace(corpo_u("Pilar[1]"), item="W8x31<1>", descricao="W8x31"),
        )
    )
    itens = {i.item: i for i in nb.perfis_dos_itens(g)}
    canal = itens["C8x13.75<1>"]
    assert canal.corpos == ("Canal[1]", "Canal[2]") and canal.perfil_lido == 'U 8" x 17,10'
    # A descrição (C8x13.75 = U 8" x 20,50) e o desenho (17,10) não batem: fica para escolher.
    assert not canal.certo and canal.sugerido == ""
    # O toco: a área não diz nada, mas a descrição diz o perfil — sem dúvida.
    pesado = sc.obter_perfil('U 8" x 20,50')
    toco = ld.CorpoDoModelo(
        "Toco[1]",
        "U8<9>",
        'U 8" x 17,10',
        (0.0, 3.0, 0.0),
        (0.15, 3.0, 0.0),
        0.15,
        pesado.area_mm2 * 0.15 / 1e6,
        "BLOCO",
        (pesado.altura_mm, pesado.largura_mm),
    )
    (item_do_toco,) = nb.perfis_dos_itens(ld.GeometriaDoModelo(corpos=(toco,)))
    assert "peça curta" in item_do_toco.origem
    assert item_do_toco.certo and item_do_toco.sugerido == 'U 8" x 17,10'
    escolhas = nb.Escolhas(perfis={"C8x13.75<1>": 'U 8" x 17,10'})
    assert nb.perfis_a_gravar(list(itens.values()), escolhas)["C8x13.75<1>"] == 'U 8" x 17,10'
    assert nb.conferir_perfis({"x": "Perfil inventado"})
    assert 'U 8" x 17,10' in nb.perfis_do_catalogo()


def test_lista_de_corte_com_o_perfil_declarado():
    csv = (
        "ITEM;QTD.;DESCRICAO;COMPRIMENTO;NOME NA LISTA DE CORTE;VOLUME POR PECA (cm3);"
        "MASSA DO ACO POR PECA (kg);CAIXA (mm);PERFIL\r\n"
        '1;2;"C8x13.75";"1800 mm";"C8x13.75<1>";"3924,0";"30,803";"1800 x 203 x 57";"U 8"" x 17,10"\r\n'
        '2;1;"C8x13.75";"1800 mm";"C8x13.75<2>";"4650,0";"36,503";"1800 x 203 x 59";""\r\n'
    ).encode("cp1252")
    itens, _ = lm.ler_lista_de_corte(csv, "plataforma_lista_de_corte.csv")
    assert [i.descricao for i in itens] == ['U 8" x 17,10', 'U 8" x 20,50']
    assert "PERFIL" in itens[0].observacao and "C8x13.75" in itens[0].observacao


# ------------------------------------------------------------------ o roteiro e o menu
def test_roteiro_e_menu_levam_a_pagina():
    from core import navegacao as nv
    from core import roteiro as rt

    item = nv.item_da_pagina("app_pages/nomes_das_barras.py")
    assert item is not None and nv.grupo_da_pagina("nomes_das_barras").nome == "Modelo SolidWorks"
    passo = rt.PASSOS[2]
    assert "renomear_corpos" in " ".join(passo.fazer) and "Nomes das barras" in " ".join(
        passo.fazer
    )
    assert re.search(r"_nomes\.csv", passo.sai)
