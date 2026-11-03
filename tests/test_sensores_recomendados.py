"""Os sensores mínimos de cada estudo: a lista e a conferência contra o quadro do estudo estático."""

from __future__ import annotations

import pytest

from core import criterio_anglo as ca
from core import sensores_do_modelo as sm
from core import sensores_recomendados as sr
from tests.dados_sensores import CODIGOS_DO_PLANO_REAL, QUADRO_REAL
from tests.test_sensores_do_modelo import PALAVRAS_PROIBIDAS, plano_com

#: As opções que o SolidWorks mostra ao criar um sensor (as telas que o usuário mandou).
TIPOS_DO_SOLIDWORKS = (
    "Dados do Simulation",
    "Propriedades de massa",
    "Dimensão",
    "Medida",
    "Dados de Costing",
    "Propriedades da caixa delimitadora de chapa metálica",
)
QUANTIDADES_DO_SOLIDWORKS = (
    "Tensão",
    "Deformação",
    "Deslocamento",
    "Frequência",
    "Fator de segurança de flambagem",
    "Força do conector",
    "Forças de corpo livre",
    "Térmico",
    "Velocidade",
    "Aceleração",
    "Tensão da viga",
    "Sensível ao fluxo de trabalho",
    "Fator de segurança",
    "Propriedades de massa do Simulation",
)


# ------------------------------------------------------------------ a lista
def test_grandezas_da_lista_sao_as_do_programa():
    assert (sr.TENSAO, sr.DESLOCAMENTO, sr.FATOR_DE_SEGURANCA, sr.FORCA) == (
        sm.TENSAO,
        sm.DESLOCAMENTO,
        sm.FATOR_DE_SEGURANCA,
        sm.FORCA,
    )
    assert (sr.MASSA, sr.FATOR_DE_FLAMBAGEM, sr.FREQUENCIA_HZ) == (
        sm.MASSA,
        sm.FATOR_DE_FLAMBAGEM,
        sm.FREQUENCIA,
    )
    for r in sr.RECOMENDADOS:
        assert r.grandeza in sm.GRANDEZAS, r.chave
        assert r.estudo in sr.ESTUDOS and r.nivel in sr.NIVEIS, r.chave


@pytest.mark.parametrize("r", sr.RECOMENDADOS, ids=lambda r: r.chave)
def test_o_nome_sugerido_e_reconhecido_pelo_programa(r):
    primeiro = r.nome.split(",")[0].strip()
    assert sm.grandeza_sugerida(primeiro) == r.grandeza


def test_direcao_dos_deslocamentos_sugeridos():
    flecha = sm.Sensor(sr.recomendado("flecha_vigas").nome, sm.DESLOCAMENTO, "mm")
    topo = sm.Sensor(sr.recomendado("deslocamento_topo").nome, sm.DESLOCAMENTO, "mm")
    assert sm.direcao_do_deslocamento(flecha) == sm.VERTICAL
    assert sm.direcao_do_deslocamento(topo) == sm.HORIZONTAL


@pytest.mark.parametrize(
    ("nome", "direcao"),
    [
        ("UY1", sm.VERTICAL),
        ("UX2", sm.HORIZONTAL),
        ("Flecha meio da luz", sm.VERTICAL),  # "luz" tem "uz", mas não é o eixo Z
        ("Desloc. horizontal vigas", sm.HORIZONTAL),
        ("Deslocamento1", ""),
    ],
)
def test_direcao_pelo_nome(nome, direcao):
    assert sm.direcao_do_deslocamento(sm.Sensor(nome, sm.DESLOCAMENTO, "mm")) == direcao


def test_o_limite_escolhido_diz_a_direcao():
    horizontal = next(
        rotulo for rotulo, lim in sm.LIMITES_ANGLO.items() if lim in ca.DESLOCAMENTOS_HORIZONTAIS
    )
    s = sm.Sensor("Flecha vigas", sm.DESLOCAMENTO, "mm", sm.LimiteDoDeslocamento(horizontal, 6.0))
    assert sm.direcao_do_deslocamento(s) == sm.HORIZONTAL


def test_todas_as_opcoes_do_solidworks_estao_explicadas():
    por_grupo = {
        g: [o.nome for o in sr.OPCOES_DO_SOLIDWORKS if o.grupo == g]
        for g in (sr.TIPO_DE_SENSOR, sr.QUANTIDADE_DE_DADOS)
    }
    assert por_grupo[sr.TIPO_DE_SENSOR] == list(TIPOS_DO_SOLIDWORKS)
    assert por_grupo[sr.QUANTIDADE_DE_DADOS] == list(QUANTIDADES_DO_SOLIDWORKS)
    assert all(o.uso in sr.NIVEIS and o.porque for o in sr.OPCOES_DO_SOLIDWORKS)


def test_limites_da_flambagem_e_da_frequencia():
    assert sr.ALFA_PEQUENA_DESLOCABILIDADE == pytest.approx(11.0)
    assert sr.ALFA_MEDIA_DESLOCABILIDADE == pytest.approx(3.5)
    texto = sr.texto_da_deslocabilidade()
    assert "α_cr ≥ 11" in texto and "1,10" in texto and "1,40" in texto and "3,5" in texto
    assert "1,25 e 1,5" in sr.texto_do_equipamento()
    frequencia = sr.recomendado("frequencia_modo1")
    assert "4 Hz" in frequencia.para_que and "3 Hz" in frequencia.para_que


def test_textos_da_lista_sem_palavras_proibidas():
    textos = [
        x
        for r in sr.RECOMENDADOS
        for x in (r.titulo, r.nome, r.componente, r.criterio, r.onde, r.alerta, r.para_que)
    ] + [o.porque for o in sr.OPCOES_DO_SOLIDWORKS]
    for texto in textos:
        for proibido in PALAVRAS_PROIBIDAS:
            assert proibido not in texto, (proibido, texto)


# ------------------------------------------------------------------ a conferência
def test_arquivo_real_tem_o_minimo_mas_nao_diz_a_direcao_do_deslocamento():
    a = sm.analisar(sm.ler_quadro(QUADRO_REAL, "real.csv"), plano_com(*CODIGOS_DO_PLANO_REAL))
    situacao = {m.recomendado.chave: m.situacao for m in a.minimos}
    assert situacao == {
        "tensao_barras": sm.TEM,
        "fator_de_seguranca": sm.TEM,
        "flecha_vigas": sm.CONFIRMAR,
        "deslocamento_topo": sm.FALTA,
        "tensao_chapas": sm.FALTA,
        "tensao_por_grupo": sm.FALTA,
        "massa": sm.FALTA,
        "forca_conector": sm.FALTA,
    }
    # o que falta é condicional ou recomendado: nada de aviso nem de verificação a mais
    assert "Sensores mínimos que faltam no estudo" not in [x.titulo for x in a.achados]
    assert not any("sem sensor no estudo" in v.nome for v in a.verificacoes)
    linhas = sm.linhas_dos_minimos(a)
    assert [len(x) for x in linhas] == [len(sm.COLUNAS_MINIMOS)] * len(a.minimos)
    flecha = next(x for x in linhas if x[0] == "Flecha das vigas")
    assert flecha[2] == "Deslocamento1" and "Tabela 3" in flecha[4]


def test_sem_tensao_e_sem_deslocamento_a_verificacao_avisa():
    conteudo = (
        "sep=;\r\nCaso;Tipo;Fator de segurança\r\nPP;caso primario;12\r\nC01-ELU;combinacao;8\r\n"
    ).encode("cp1252")
    a = sm.analisar(sm.ler_quadro(conteudo))
    achado = next(x for x in a.achados if x.titulo == "Sensores mínimos que faltam no estudo")
    assert achado.nivel == sm.NIVEL_ATENCAO
    assert "Tensão barras" in achado.texto and "Flecha vigas" in achado.texto
    faltam = [v for v in a.verificacoes if "sem sensor no estudo" in v.nome]
    assert [v.nome.split(" — ")[0] for v in faltam] == ["Tensão nas barras", "Flecha das vigas"]
    assert all(v.status == "ALERTA" for v in faltam) and a.status == "ALERTA"


def test_quadro_completo_atende_tudo():
    nomes = [
        "Tensão vigas",
        "Tensão pilares",
        "Tensão chapas",
        "Fator de segurança",
        "Flecha vigas",
        "Deslocamento topo pilares",
        "Massa do modelo",
        "Força parafusos",
    ]
    conteudo = (
        "sep=;\r\nCaso;Tipo;" + ";".join(nomes) + "\r\nPP;caso primario;" + ";".join(["1"] * 8)
    ).encode("cp1252")
    a = sm.analisar(sm.ler_quadro(conteudo))
    assert {m.situacao for m in a.minimos} == {sm.TEM}
    grupos = next(m for m in a.minimos if m.recomendado.chave == "tensao_por_grupo")
    assert grupos.sensores == ("Tensão vigas", "Tensão pilares")


# ------------------------------------------------------------------ a massa
def _quadro_com_massa(unidade: str = "", valor: str = "298,7") -> sm.QuadroDeSensores:
    linhas = ["sep=;", "Caso;Tipo;Tensão barras;Massa do modelo"]
    if unidade:
        linhas.append(f"Unidade;;N/mm^2;{unidade}")
    linhas += [f"PP;caso primario;10;{valor}", f"C01-ELU;combinacao;14;{valor}"]
    return sm.ler_quadro("\r\n".join(linhas).encode("cp1252"))


@pytest.mark.parametrize(
    ("massa_da_lista", "nivel", "titulo"),
    [
        (300.0, sm.NIVEL_INFO, "A massa do estudo bate com a lista de material"),
        (250.0, sm.NIVEL_ATENCAO, "A massa do estudo não bate com a lista de material"),
    ],
)
def test_massa_do_estudo_contra_a_lista_de_material(massa_da_lista, nivel, titulo):
    a = sm.analisar(_quadro_com_massa(), massa_da_lista_kg=massa_da_lista)
    achado = next(x for x in a.achados if x.titulo == titulo)
    assert achado.nivel == nivel and "298,7 kg" in achado.texto


def test_massa_sem_lista_nao_avisa_e_unidade_em_gramas():
    a = sm.analisar(_quadro_com_massa())
    assert not [x for x in a.achados if "massa" in x.titulo.casefold()]
    q = _quadro_com_massa("g", "298736,55")
    assert q.sensores[1].unidade == "g"
    assert q.valor(q.linhas[0], 1) == pytest.approx(298.73655)


def test_flambagem_e_frequencia_governam_pelo_menor():
    conteudo = (
        "sep=;\r\nCaso;Tipo;Fator de flambagem modo 1;Frequência modo 1\r\n"
        "A;caso primario;12;9\r\nB;caso primario;4;15\r\n"
    ).encode("cp1252")
    a = sm.analisar(sm.ler_quadro(conteudo))
    assert a.extremo(0, sm.GRUPO_CASOS).valor == 4.0
    assert a.extremo(1, sm.GRUPO_CASOS).valor == 9.0
