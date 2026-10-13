"""Entradas estragadas nunca derrubam o programa: só saem os erros previstos, com mensagem.

Arquivos aleatórios, truncados ou com campos trocados, e dados gravados no projeto fora do
formato (projeto antigo, editado à mão, corrompido): cada leitor devolve o resultado ou o erro
previsto do módulo, nunca uma exceção qualquer. Os testes rodam com
``MECANICA_TOOLKIT_ERROS=levantar`` (conftest), então uma falha inesperada aparece aqui.
"""

from __future__ import annotations

import json
import random

import pytest

from core import base_tecnica as bt
from core import cargas_esqueleto as ce
from core import cargas_pelo_modelo as cpm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import placa_base_pilares as pb
from core import plano_de_cargas as pc
from core import travamentos as tv
from core.project_store import ProjetoPersistenciaErro, importar_carteira, importar_projeto
from tests import dados_solidworks as sw
from tests.test_lista_de_material import CSV_DA_MACRO, CSV_DA_MACRO_COM_GEOMETRIA

SEMENTES = range(40)
#: Caracteres que costumam aparecer (e confundir) num CSV do SolidWorks em português.
TROCAS = b';,.-"x0 9\r\nabcA' + "Ç°Â".encode("cp1252")


def _bytes_aleatorios(gerador: random.Random) -> bytes:
    return bytes(gerador.randrange(256) for _ in range(gerador.randrange(0, 400)))


def _estragar(conteudo: bytes, gerador: random.Random) -> bytes:
    """Corta, duplica, apaga ou troca trechos do arquivo bom."""
    texto = bytearray(conteudo)
    for _ in range(gerador.randrange(1, 6)):
        if not texto:
            break
        i = gerador.randrange(len(texto))
        j = min(len(texto), i + gerador.randrange(1, 40))
        acao = gerador.choice(("cortar", "apagar", "trocar", "duplicar", "lixo"))
        if acao == "cortar":
            del texto[i:]
        elif acao == "apagar":
            del texto[i:j]
        elif acao == "trocar":
            texto[i:j] = bytes(gerador.choice(TROCAS) for _ in range(j - i))
        elif acao == "duplicar":
            texto[i:i] = texto[i:j]
        else:
            texto[i:i] = _bytes_aleatorios(gerador)[:20]
    return bytes(texto)


ARQUIVOS_DO_SOLIDWORKS = (
    sw.csv_forcas_da_viga("PP"),
    sw.csv_reacoes("SC"),
    sw.csv_tensoes(),
    sw.csv_tensoes_da_viga("W0"),
)


@pytest.mark.parametrize("semente", SEMENTES)
def test_csv_do_solidworks_estragado_so_da_arquivo_invalido(semente):
    gerador = random.Random(semente)
    candidatos = [
        _bytes_aleatorios(gerador),
        *(_estragar(a, gerador) for a in ARQUIVOS_DO_SOLIDWORKS),
    ]
    for conteudo in candidatos:
        try:
            em.ler_arquivo(conteudo, "x.csv")
        except em.ArquivoInvalido:
            pass


@pytest.mark.parametrize("semente", SEMENTES)
def test_esqueleto_estragado_so_da_geometria_invalida(semente):
    gerador = random.Random(4000 + semente)
    candidatos = [
        _bytes_aleatorios(gerador),
        _estragar(sw.csv_esqueleto(), gerador),
        _estragar(sw.csv_esqueleto(decimal="."), gerador),
        _estragar(
            sw.csv_esqueleto(
                formas={"Canal c C8X13.75(1)[2]": "CHAPA"},
                contornos={
                    "Canal c C8X13.75(1)[2]": [(0, 4000, 0), (6000, 4000, 0), (6000, 4000, 900)]
                },
                aberturas={
                    "Canal c C8X13.75(1)[2]": [
                        [(100, 4000, 100), (200, 4000, 100), (200, 4000, 200)]
                    ]
                },
            ),
            gerador,
        ),
    ]
    for conteudo in candidatos:
        ld.tipo_do_arquivo(conteudo)  # reconhecer nunca quebra
        try:
            g = ld.ler_esqueleto(conteudo, "x_esqueleto.csv")
        except ld.GeometriaInvalida:
            continue
        dados = em.EsforcosDoModelo()
        ld.ler_barras(dados, g)
        ld.pontas_soltas_pela_geometria(g, "Y")
        for corpo in g.corpos:
            tv.comprimentos(g, corpo, "Viga", "Y")
        cpm.distribuir(g, {"SC": 5.0}, "Y")
        assert ld.de_dicionario(json.loads(json.dumps(ld.para_dicionario(g)))).corpos


@pytest.mark.parametrize("semente", SEMENTES)
def test_lista_de_corte_estragada_so_da_o_erro_previsto(semente):
    gerador = random.Random(1000 + semente)
    candidatos = [
        _bytes_aleatorios(gerador),
        _estragar(CSV_DA_MACRO, gerador),
        _estragar(CSV_DA_MACRO_COM_GEOMETRIA, gerador),
    ]
    for conteudo in candidatos:
        for nome in ("lista.csv", "lista.xlsx"):
            try:
                itens, avisos = lm.ler_lista_de_corte(conteudo, nome)
            except lm.ListaDeCorteInvalida:
                continue
            assert all(isinstance(a, str) for a in avisos)
            lm.resumir(lm.ListaDeMaterial(itens=tuple(itens)))  # e o resumo também não quebra


def _json_aleatorio(gerador: random.Random, profundidade: int = 0) -> object:
    escolhas = ["nada", "int", "float", "texto", "bool"]
    if profundidade < 3:
        escolhas += ["lista", "dict", "dict"]
    tipo = gerador.choice(escolhas)
    if tipo == "nada":
        return None
    if tipo == "int":
        return gerador.randrange(-5, 1000)
    if tipo == "float":
        return gerador.choice((0.0, -1.5, 3.25, 1e9, -1e-9))
    if tipo == "bool":
        return gerador.random() < 0.5
    if tipo == "texto":
        return gerador.choice(("", "abc", "W 200 x 35,9 (H)", "PP", "1,5", "Pilar", "-", "{}"))
    if tipo == "lista":
        return [_json_aleatorio(gerador, profundidade + 1) for _ in range(gerador.randrange(4))]
    chaves = (
        "casos",
        "membros",
        "acoes",
        "cargas",
        "itens",
        "parametros",
        "placa",
        "reacoes",
        "modelo",
        "perfil",
        "tipo",
        "valor",
        "codigo",
        "quantidade",
        "comprimento_m",
        "cliente",
        "vento",
        "v0_m_s",
        "s1",
        "categoria",
        "grupo_s3",
        "s3_cliente",
        "tipo_de_estrutura",
        "sobrecarga_local",
        "sobrecarga_kN_m2",
        "classe_de_agressividade",
        "vida_util_anos",
        "eixo_vertical",
        "norma",
        "acrescimo_pct",
        "massa_unitaria",
        "massa_geometria_kg",
        "pontos",
        "x",
    )
    return {
        gerador.choice(chaves): _json_aleatorio(gerador, profundidade + 1)
        for _ in range(gerador.randrange(5))
    }


LEITORES_DO_PROJETO = (
    ("plano_de_cargas", pc.plano_do_projeto),
    ("base_tecnica", bt.base_do_projeto),
    ("esforcos_do_modelo", em.esforcos_do_projeto),
    ("lista_de_material", lm.lista_do_projeto),
    ("cargas_do_esqueleto", ce.entrada_do_projeto),
    ("geometria_do_modelo", ld.geometria_do_projeto),
)


@pytest.mark.parametrize("semente", SEMENTES)
def test_dados_do_projeto_fora_do_formato_viram_o_padrao(semente):
    """Projeto antigo, editado à mão ou corrompido: o leitor devolve algo usável, sem exceção."""
    gerador = random.Random(2000 + semente)
    for campo, leitor in LEITORES_DO_PROJETO:
        for _ in range(5):
            valor = _json_aleatorio(gerador)
            leitor({campo: valor})
            leitor({campo: {"casos": valor, "membros": valor, "acoes": valor, "itens": valor}})
    for _ in range(5):
        pb.de_dicionario(_json_aleatorio(gerador))  # type: ignore[arg-type]


@pytest.mark.parametrize("semente", SEMENTES[:15])
def test_importar_projeto_ou_carteira_estragados_so_da_o_erro_previsto(semente, banco_isolado):
    gerador = random.Random(3000 + semente)
    candidatos = [
        _bytes_aleatorios(gerador),
        json.dumps(_json_aleatorio(gerador)).encode(),
        json.dumps(
            {"formato": "mecanica-toolkit-project", "projeto": _json_aleatorio(gerador)}
        ).encode(),
        json.dumps(
            {"formato": "mecanica-toolkit-carteira", "projetos": [_json_aleatorio(gerador)]}
        ).encode(),
    ]
    for conteudo in candidatos:
        for importar in (importar_projeto, importar_carteira):
            try:
                importar(conteudo)
            except ProjetoPersistenciaErro:
                pass
