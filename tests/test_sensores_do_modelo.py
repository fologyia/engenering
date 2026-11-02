"""Sensores do modelo: o quadro do gerenciador de casos de carga do SolidWorks lido, conferido
contra o plano de cargas e verificado. O arquivo real do usuário fecha os achados; quadros
sintéticos (superposição coerente com o plano) mostram que nada é acusado sem motivo."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest

from components.cena_3d_svg import svg_da_cena
from core import cena_3d_png
from core import desenho_dos_sensores as dds
from core import exportacao_cargas as ex
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import sensores_do_modelo as sm
from core.memorial_verificacoes import tabelas_do_registro
from core.project_report import gerar_relatorio_industrial_pdf, gerar_relatorio_industrial_word
from core.project_store import novo_projeto_documento
from core.record_charts import imagens_do_registro
from core.technical_records import avaliar_contrato_registro
from tests.dados_sensores import CODIGOS_DO_PLANO_REAL, QUADRO_REAL

ESTADOS = (comb.ELU_NORMAL, comb.ELS_RARA)
SETE = ("PP", "PE", "SC", "W0", "W90", "W180", "W270")
#: Máximo de cada caso em cada sensor: tensão (MPa), deslocamento (mm), FS e axial (MPa).
CASOS = {
    "PP": (3.988, 0.1654, 62.68, 0.278),
    "PE": (0.7562, 0.01409, 330.6, 0.1203),
    "SC": (20.92, 0.9346, 11.95, 1.372),
    "W0": (23.09, 1.292, 10.83, 0.3482),
    "W90": (9.941, 0.3497, 25.15, 0.5913),
    "W180": (23.05, 1.297, 10.85, 0.349),
    "W270": (9.628, 0.3438, 25.97, 0.5912),
}
NOMES = ("Tensão vigas", "Deslocamento1", "Fator mínimo de segurança1", "Axial")


def plano_com(*codigos: str) -> pc.PlanoDeCargas:
    plano = pc.PlanoDeCargas()
    for codigo in codigos:
        plano = pc.com_acao(plano, pc.nova_acao(codigo))
    return plano


def _num(valor: float) -> str:
    return f"{valor:.6E}".replace(".", ",")


def quadro_sintetico(
    plano: pc.PlanoDeCargas,
    estados=ESTADOS,
    *,
    casos=CASOS,
    nomes=NOMES,
    trocar: dict[str, tuple[float, ...]] | None = None,
    tirar: tuple[str, ...] = (),
    unidades: str = "",
) -> bytes:
    """O quadro como a macro grava, com cada combinação calculada dos casos: 90 % de Σ|γ|·v na
    tensão, no deslocamento e no axial e o FS de 1/(0,9·Σ(γ/FS)) — coerente com a superposição e
    com o mesmo aço (σ·FS igual ao dos casos)."""
    lista = pc.combinacoes(plano, estados)
    linhas = [
        "sep=;",
        "Nome do estudo:Estudo sintético",
        "Quadro da Vista de resultados do gerenciador de casos de carga - valores como a API do "
        "SOLIDWORKS devolve",
        "",
        "Caso;Tipo;" + ";".join(nomes),
    ]
    if unidades:
        linhas.append(unidades)
    for codigo, valores in casos.items():
        linhas.append(f"{codigo};caso primario;" + ";".join(_num(v) for v in valores))
    for c in lista:
        nome = ex.nome_da_combinacao(c, len(lista))
        if nome in tirar:
            continue
        termos = [
            (casos[ex.nome_no_solidworks(k)], abs(f))
            for k, f in c.fatores.items()
            if ex.nome_no_solidworks(k) in casos and abs(f) > 0
        ]
        if trocar and nome in trocar:
            valores = trocar[nome]
        else:
            sigma = 0.9 * sum(f * v[0] for v, f in termos)
            desloc = 0.9 * sum(f * v[1] for v, f in termos)
            fs = 1.0 / (0.9 * sum(f / v[2] for v, f in termos))
            axial = 0.9 * sum(f * v[3] for v, f in termos)
            valores = (sigma, desloc, fs, axial)[: len(nomes)]
        linhas.append(f"{nome};combinacao;" + ";".join(_num(v) for v in valores))
    return "\r\n".join(linhas).encode("cp1252")


def achados(a: sm.AnaliseDosSensores, nivel: str) -> list[str]:
    return [x.titulo for x in a.achados if x.nivel == nivel]


# ------------------------------------------------------------------ o arquivo real
def test_le_o_arquivo_real_da_macro():
    q = sm.ler_quadro(QUADRO_REAL, "Análise estática 1-gerenciador-resultados.csv")
    assert q.estudo == "Análise estática 1"
    assert [s.nome for s in q.sensores] == list(NOMES)
    assert [s.grandeza for s in q.sensores] == [
        sm.TENSAO,
        sm.DESLOCAMENTO,
        sm.FATOR_DE_SEGURANCA,
        sm.COMPONENTE,
    ]
    assert [s.unidade for s in q.sensores] == [sm.MPA, "mm", "—", sm.MPA]
    assert len(q.casos) == 7 and len(q.combinacoes) == 71
    assert q.valor(q.casos[0], 0) == pytest.approx(3.988)
    assert not q.avisos


def test_arquivo_real_com_o_plano_do_projeto_acha_o_que_estava_errado():
    q = sm.ler_quadro(QUADRO_REAL, "real.csv")
    a = sm.analisar(q, plano_com(*CODIGOS_DO_PLANO_REAL))
    assert len(a.ligacao.combinacoes) == 71
    assert a.ligacao.faltam == ("C51-ELSR",) and not a.ligacao.sobram
    # da C50 em diante as ELS repetem o mesmo número: 22 combinações fora
    assert a.fora == {"C50-ELSR"} | {f"C{n}-ELSR" for n in range(52, 73)}
    assert "Resultados repetidos com coeficientes diferentes" in achados(a, sm.NIVEL_ERRO)
    assert "Casos do plano que não estão no estudo" in achados(a, sm.NIVEL_ATENCAO)
    assert "Combinações do plano que não vieram do SolidWorks" in achados(a, sm.NIVEL_ATENCAO)
    # C01 = C03 porque diferem só em T+/T−, que o estudo não tem: explicado, não sai
    assert "Combinações iguais (explicado)" in achados(a, sm.NIVEL_INFO)
    assert "C01-ELU" not in a.fora and a.observacoes["C03-ELU"] == "igual a C01-ELU"
    # σ·FS = 250 MPa: o aço e a unidade conferem
    assert a.fy_MPa == 250.0 and "σ·FS" in a.fy_origem
    assert a.fy_aparente is not None and {"W0", "W180"} <= {n for n, _ in a.fy_aparente.maiores}
    tensao, desloc, fs = (a.verificacoes[i] for i in range(3))
    assert tensao.status == "OK" and tensao.solicitante == pytest.approx(39.12)
    assert tensao.resistente == pytest.approx(250 / 1.1) and "C09-ELU" in tensao.nome
    assert desloc.status == "INFO" and desloc.solicitante == pytest.approx(1.176)
    assert "C49-ELSR" in desloc.nome  # a única ELS que é resultado
    assert fs.status == "OK" and fs.resistente == pytest.approx(6.39)
    assert fs.aproveitamento == pytest.approx(tensao.aproveitamento, rel=2e-3)
    assert a.status == "ALERTA"
    assert sum(v.status == "ALERTA" for v in a.verificacoes) == 2


# ------------------------------------------------------------------ leitura
@pytest.mark.parametrize(
    ("nome", "grandeza"),
    [
        ("Tensão vigas", sm.TENSAO),
        ("von Mises máx.", sm.TENSAO),
        ("Tensão de flexão dir1", sm.COMPONENTE),
        ("Axial", sm.COMPONENTE),
        ("Deslocamento1", sm.DESLOCAMENTO),
        ("UY1", sm.DESLOCAMENTO),
        ("URES", sm.DESLOCAMENTO),
        ("Fator mínimo de segurança1", sm.FATOR_DE_SEGURANCA),
        ("FS2", sm.FATOR_DE_SEGURANCA),
        ("Força de reação", sm.FORCA),
        ("Momento fletor", sm.MOMENTO),
        ("Temperatura", sm.OUTRA),
    ],
)
def test_grandeza_pelo_nome_do_sensor(nome, grandeza):
    assert sm.grandeza_sugerida(nome) == grandeza


def test_linha_de_unidades_e_conversao():
    conteudo = quadro_sintetico(
        plano_com(*SETE),
        unidades="Unidade;;N/m^2;m;;kN",
        casos={k: (v[0] * 1e6, v[1] / 1000, v[2], v[3]) for k, v in CASOS.items()},
    )
    q = sm.ler_quadro(conteudo)
    assert [s.unidade for s in q.sensores] == ["Pa (N/m²)", "m", "—", sm.MPA]  # kN não é tensão
    assert q.valor(q.casos[0], 0) == pytest.approx(3.988)
    assert q.valor(q.casos[0], 1) == pytest.approx(0.1654)


def test_unidade_errada_da_tensao_aparece_pelo_fator_de_seguranca():
    conteudo = quadro_sintetico(
        plano_com(*SETE), casos={k: (v[0] * 1e6, *v[1:]) for k, v in CASOS.items()}
    )
    a = sm.analisar(sm.ler_quadro(conteudo), plano_com(*SETE))  # tensão em Pa lida como MPa
    assert "A unidade da tensão não confere com o fator de segurança" in achados(a, sm.NIVEL_ERRO)
    assert a.fy_origem.startswith("adotado")


@pytest.mark.parametrize(
    "conteudo",
    [
        b"",
        b"qualquer coisa",
        b"sep=;\r\nCaso;Tipo\r\nPP;caso primario",
        b"Caso;Tipo;S1\r\n",
    ],
)
def test_arquivo_que_nao_e_o_quadro(conteudo):
    with pytest.raises(sm.QuadroInvalido):
        sm.ler_quadro(conteudo)


def test_linhas_vazias_e_repetidas_viram_aviso():
    conteudo = b"sep=;\r\nCaso;Tipo;S1;S1\r\nPP;caso primario;;\r\nPP;caso primario;1;2\r\n"
    q = sm.ler_quadro(conteudo)
    assert [s.nome for s in q.sensores] == ["S1", "S1 (2)"]
    assert len(q.linhas) == 1 and len(q.avisos) == 2


# ------------------------------------------------------------------ conferência
def test_quadro_coerente_nao_acusa_nada():
    plano = plano_com(*SETE)
    a = sm.analisar(sm.ler_quadro(quadro_sintetico(plano)), plano)
    assert not achados(a, sm.NIVEL_ERRO) and not achados(a, sm.NIVEL_ATENCAO)
    assert not a.fora and not a.ligacao.faltam and not a.ligacao.sobram
    assert len(a.ligacao.combinacoes) == len(pc.combinacoes(plano, ESTADOS))
    assert a.status == "OK"


def test_ordem_dos_estados_exportados_nao_atrapalha_a_ligacao():
    plano = plano_com(*SETE)
    conteudo = quadro_sintetico(plano, (comb.ELS_RARA, comb.ELU_NORMAL))
    a = sm.analisar(sm.ler_quadro(conteudo), plano)
    assert not a.ligacao.sobram and not a.ligacao.faltam
    assert a.tipos["C01-ELSR"] == "ELS"


def test_combinacao_fora_da_superposicao_e_acusada():
    plano = plano_com(*SETE)
    lista = pc.combinacoes(plano, ESTADOS)
    alvo = ex.nome_da_combinacao(lista[3], len(lista))
    conteudo = quadro_sintetico(plano, trocar={alvo: (500.0, 0.5, 0.3, 1.0)})
    a = sm.analisar(sm.ler_quadro(conteudo), plano)
    texto = next(x.texto for x in a.achados if x.titulo.startswith("Combinações que não fecham"))
    assert alvo in texto and "Tensão vigas" in texto and "Fator mínimo" in texto
    assert a.observacoes[alvo] == "não fecha com o plano"
    assert a.status in ("ALERTA", "NÃO OK")


def test_casos_iguais_sao_avisados():
    casos = dict(CASOS, W180=CASOS["W0"])
    plano = plano_com(*SETE)
    a = sm.analisar(sm.ler_quadro(quadro_sintetico(plano, casos=casos)), plano)
    assert "Casos com o mesmo resultado" in achados(a, sm.NIVEL_ATENCAO)


def test_sem_plano_usa_a_sigla_do_nome():
    a = sm.analisar(sm.ler_quadro(QUADRO_REAL))
    assert a.tipos["C01-ELU"] == "ELU" and a.tipos["C49-ELSR"] == "ELS"
    assert "Sem plano de cargas" in achados(a, sm.NIVEL_INFO)
    assert not a.fora  # sem o plano não dá para provar que a repetição é errada
    assert a.verificacoes[0].status == "OK"


def test_combinacao_sem_sigla_fica_fora_da_verificacao():
    conteudo = b"sep=;\r\nCaso;Tipo;Tensao\r\nPP;caso primario;10\r\nComb1;combinacao;20\r\n"
    a = sm.analisar(sm.ler_quadro(conteudo))
    assert "Combinações sem estado-limite" in achados(a, sm.NIVEL_ATENCAO)
    assert a.verificacoes[0].status == "ALERTA"  # sem ELU: não dá para verificar


# ------------------------------------------------------------------ verificações
def _com_limite(q: sm.QuadroDeSensores, limite: sm.LimiteDoDeslocamento) -> sm.QuadroDeSensores:
    sensores = [sm.Sensor(s.nome, s.grandeza, s.unidade, limite) for s in q.sensores]
    return sm.com_ajustes(q, sensores)


@pytest.mark.parametrize(
    ("limite", "esperado_mm"),
    [
        (sm.LimiteDoDeslocamento(next(iter(sm.LIMITES_ANGLO))), None),  # falta o vão
        (sm.LimiteDoDeslocamento(sm.L_SOBRE_X, 6.0, 350.0), 6000 / 350),
        (sm.LimiteDoDeslocamento(sm.EM_MM, maximo_mm=1.0), 1.0),
        (sm.LimiteDoDeslocamento(sm.SEM_LIMITE), None),
    ],
)
def test_limite_do_deslocamento(limite, esperado_mm):
    plano = plano_com(*SETE)
    q = _com_limite(sm.ler_quadro(quadro_sintetico(plano)), limite)
    a = sm.analisar(q, plano)
    v = next(v for v in a.verificacoes if v.nome.startswith("Deslocamento"))
    if esperado_mm is None:
        assert v.resistente is None
        assert v.status == ("ALERTA" if limite.falta() else "INFO")
    else:
        assert v.resistente == pytest.approx(esperado_mm)
        assert v.status == ("OK" if v.solicitante <= esperado_mm else "NÃO OK")


def test_limite_anglo_com_o_vao():
    vigas = next(
        k for k, v in sm.LIMITES_ANGLO.items() if v.descricao == "Vigas de piso principais"
    )
    limite = sm.LimiteDoDeslocamento(vigas, comprimento_m=6.0)
    assert limite.limite_mm() == pytest.approx(6000 / 350)
    assert "L/350" in limite.texto() and "Anglo" in limite.referencia()


def test_fy_informado_vale_sobre_o_do_fator_de_seguranca():
    plano = plano_com(*SETE)
    q = sm.com_ajustes(sm.ler_quadro(quadro_sintetico(plano)), fy_MPa=345.0)
    a = sm.analisar(q, plano)
    assert a.fy_MPa == 345.0 and a.fy_origem == "informado"
    assert a.verificacoes[0].resistente == pytest.approx(345 / 1.1)


# ------------------------------------------------------------------ projeto
def test_ida_e_volta_no_projeto_e_dado_estragado():
    q = sm.ler_quadro(QUADRO_REAL, "real.csv")
    limite = sm.LimiteDoDeslocamento(sm.L_SOBRE_X, 4.5, 300.0)
    q = sm.com_ajustes(q, [sm.Sensor("Deslocamento1", sm.DESLOCAMENTO, "mm", limite)], fy_MPa=250.0)
    assert sm.de_dicionario(sm.para_dicionario(q)) == q
    assert sm.de_dicionario(None).vazio and sm.de_dicionario({"sensores": "x"}).vazio
    estragado = {
        "sensores": [{"nome": "S", "grandeza": "inventada", "unidade": "parsec", "limite": 3}, 5],
        "linhas": [{"nome": "PP", "valores": [1, "x", float("nan")]}, {"valores": [2]}, "lixo"],
        "fy_MPa": "muito",
    }
    lido = sm.de_dicionario(estragado)
    assert lido.sensores == (sm.Sensor("S", sm.OUTRA, "—"),)
    assert lido.linhas == (sm.LinhaDoQuadro("PP", False, (1.0,)),) and lido.fy_MPa is None


def test_manter_ajustes_ao_reenviar_o_arquivo():
    q = sm.ler_quadro(QUADRO_REAL, "real.csv")
    ajustado = sm.com_ajustes(q, [sm.Sensor("Axial", sm.FORCA, "kN")], fy_MPa=300.0)
    de_novo = sm.ler_quadro(QUADRO_REAL, "real.csv")
    assert sm.manter_ajustes(de_novo, ajustado) is ajustado  # o mesmo arquivo: nada muda
    outro = sm.ler_quadro(QUADRO_REAL.replace(b"3,988000E+00", b"4,000000E+00"), "novo.csv")
    mantido = sm.manter_ajustes(outro, ajustado)
    assert mantido.sensores[3] == sm.Sensor("Axial", sm.FORCA, "kN") and mantido.fy_MPa == 300.0
    assert mantido.arquivo == "novo.csv"


# ------------------------------------------------------------------ memorial e desenho
def test_registro_vai_ao_memorial_com_tabelas_e_grafico():
    a = sm.analisar(sm.ler_quadro(QUADRO_REAL, "real.csv"), plano_com(*CODIGOS_DO_PLANO_REAL))
    registro = sm.registro_sensores(a)
    assert registro["modulo_id"] == sm.MODULO_ID and registro["status"] == "Atenção"
    tabelas = tabelas_do_registro(registro)
    assert [t["cabecalhos"][0] for t in tabelas] == ["Sensor", "Combinação", "Caso / combinação"]
    quadro = tabelas[2]
    assert len(quadro["linhas"]) == 78
    linha_c60 = next(linha for linha in quadro["linhas"] if linha[0] == "C60-ELSR")
    assert linha_c60[-1] == "repetido: fora da verificação"
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == "" and len(imagens) == 1
    assert imagens[0]["png"][:8] == b"\x89PNG\r\n\x1a\n"
    assert any("C51-ELSR" in alerta for alerta in registro["alertas"])


def test_quadro_com_muitos_sensores_quebra_em_tabelas_de_cinco():
    nomes = tuple(f"Tensão {i}" for i in range(7))
    casos = {k: (v[0],) * 7 for k, v in CASOS.items()}
    plano = plano_com(*SETE)
    lista = pc.combinacoes(plano, ESTADOS)
    trocar = {ex.nome_da_combinacao(c, len(lista)): (30.0 + i,) * 7 for i, c in enumerate(lista)}
    conteudo = quadro_sintetico(plano, casos=casos, nomes=nomes, trocar=trocar)
    a = sm.analisar(sm.ler_quadro(conteudo), plano)
    tabelas = sm.tabelas_para_memorial(a)
    assert [len(t["cabecalhos"]) for t in tabelas[2:]] == [2 + 5 + 1, 2 + 2 + 1]


def test_desenho_mostra_a_que_governa_o_limite_e_as_que_ficaram_fora():
    a = sm.analisar(sm.ler_quadro(QUADRO_REAL, "real.csv"), plano_com(*CODIGOS_DO_PLANO_REAL))
    paineis = dds.paineis_da_analise(a)
    assert [p.grupo for p in paineis] == ["ELU", "ELS", "ELU"]
    tensao, desloc, fs = paineis
    assert tensao.rotulos[tensao.governa] == "C09-ELU" and tensao.limite == pytest.approx(250 / 1.1)
    assert fs.menor_governa and fs.rotulos[fs.governa] == "C09-ELU" and fs.limite == 1.1
    assert sum(desloc.fora) == 22 and desloc.rotulos[desloc.governa] == "C49-ELSR"
    assert desloc.limite is None
    desenho = dds.desenho_dos_sensores(paineis)
    raiz = ET.fromstring(svg_da_cena(desenho))
    assert raiz.tag.endswith("svg")
    assert ("#d98c8c", "fora (resultado repetido)") in desenho.legenda
    assert cena_3d_png.png_da_cena(desenho, escala=1.0)[:4] == b"\x89PNG"
    gravados = dds.paineis_do_registro(dds.paineis_para_o_registro(paineis))
    assert [(p.rotulos, p.fora, p.grupo) for p in gravados] == [
        (p.rotulos, p.fora, p.grupo) for p in paineis
    ]
    assert gravados[0].limite == pytest.approx(paineis[0].limite)
    assert gravados[0].valores == pytest.approx(paineis[0].valores)


def test_paineis_gravados_estragados_sao_ignorados():
    assert dds.paineis_do_registro(None) == []
    assert dds.paineis_do_registro({"paineis": [1, {"rotulos": ["a"], "valores": []}]}) == []
    um = dds.paineis_do_registro(
        {"paineis": [{"rotulos": ["C1-ELU"], "valores": [float("inf")], "casas": 99}]}
    )
    assert um[0].valores == (None,) and um[0].casas == 2 and um[0].governa is None


def test_tracejado_no_png():
    trechos = cena_3d_png.trechos_do_tracejado((0.0, 0.0), (100.0, 0.0), "7 5")
    assert len(trechos) == math.ceil(100 / 12)
    assert trechos[0] == ((0.0, 0.0), (7.0, 0.0)) and trechos[-1][1] == (100.0, 0.0)
    assert cena_3d_png.trechos_do_tracejado((0, 0), (1, 1), "") == [((0, 0), (1, 1))]
    assert cena_3d_png.trechos_do_tracejado((0, 0), (1, 1), "a b") == [((0, 0), (1, 1))]


def test_lista_curta_junta_as_faixas():
    nomes = ["C01-ELU", "C03-ELU", "C50-ELSR", "C52-ELSR", "C53-ELSR", "C54-ELSR", "PP"]
    assert sm.lista_curta(nomes) == "C01-ELU, C03-ELU, C50-ELSR, C52-ELSR a C54-ELSR, PP"


PALAVRAS_PROIBIDAS = ("Não informado", "bloqueio", "Snapshot", "Apêndice", "sem valor normativo")


def test_capitulo_no_word_e_no_pdf_do_memorial():
    from io import BytesIO

    from docx import Document
    from pypdf import PdfReader

    a = sm.analisar(sm.ler_quadro(QUADRO_REAL, "real.csv"), plano_com(*CODIGOS_DO_PLANO_REAL))
    registro = sm.registro_sensores(a, responsavel="Eng. A")
    assert avaliar_contrato_registro(registro)["valido"]
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto.update({"objetivo": "Verificar a plataforma.", "responsavel": "Eng. A"})
    projeto["registros_tecnicos"] = [registro]
    conteudo = gerar_relatorio_industrial_word(projeto)
    documento = Document(BytesIO(conteudo))
    word = "\n".join(
        [p.text for p in documento.paragraphs]
        + [c.text for tabela in documento.tables for linha in tabela.rows for c in linha.cells]
    )
    pdf = "\n".join(
        pagina.extract_text() or ""
        for pagina in PdfReader(BytesIO(gerar_relatorio_industrial_pdf(projeto))).pages
    )
    for texto in (word, pdf):
        assert "Sensores do modelo" in texto and "C09-ELU" in texto
        assert "Quadro dos sensores" in texto and "C60-ELSR" in texto
        for proibido in PALAVRAS_PROIBIDAS:
            assert proibido not in texto, proibido
    assert len(documento.inline_shapes) >= 1
