"""Regras que valem para todos os casos do Assistente de cargas, sem exceção.

Cada caso é só uma tabela de campos e uma função. Estes testes percorrem o catálogo inteiro: um caso
novo já nasce coberto, com ajuda em todo campo, croqui, memorial, Word e fuzz.
"""

from __future__ import annotations

import math
import random
import re

import pytest

from components import load_models as modelos_de_secao
from components.elementos_croquis import CROQUIS
from core import elementos_catalogo as cat
from core import memorial_verificacoes as mv
from core.elementos_base import Caso, Resultado, calcular_caso, dados_do_registro
from core.elementos_word import gerar_word_do_caso
from core.technical_records import criar_registro_tecnico

CASOS = list(cat.CASOS.values())
IDS = [caso.id for caso in CASOS]

PALAVRAS_PROIBIDAS = ("bloqueio", "Snapshot", "Apêndice", "Não informado", "sem valor normativo")


def test_ha_casos_de_estatica_de_maquinas_e_de_secoes():
    assert len(CASOS) >= 62
    assert len(cat.GRUPOS[cat.AREA_ESTATICA]) == 4
    assert len(cat.GRUPOS[cat.AREA_MAQUINAS]) >= 8
    assert len(cat.GRUPOS[cat.AREA_SECOES]) == 6


def test_todo_grupo_e_toda_area_tem_icone_e_descricao():
    for area, grupos in cat.GRUPOS.items():
        assert cat.AREAS_INFO[area].icone.startswith(":material/")
        for grupo in grupos:
            info = cat.info_do_grupo(grupo)
            assert info.icone.startswith(":material/"), grupo
            assert info.descricao.endswith("."), grupo


def test_os_atalhos_do_painel_abrem_casos_que_existem():
    assert len(cat.ATALHOS) == 6
    for atalho in cat.ATALHOS:
        assert atalho.caso in cat.CASOS
        assert atalho.icone.startswith(":material/")


def test_os_modelos_antigos_continuam_abrindo_pelo_mesmo_rotulo():
    # O Assistente de projeto grava estes rótulos em ``assistente_geometria``.
    for rotulo in modelos_de_secao.CATALOGO:
        assert rotulo in cat.CASOS, rotulo
    assert cat.resolver("Seção I sob força axial e flexão") in cat.CASOS
    assert cat.resolver("nada disso") == cat.CASO_PADRAO
    assert cat.resolver(None) == cat.CASO_PADRAO


def test_cada_caso_esta_em_um_so_grupo():
    vistos = [i for grupos in cat.GRUPOS.values() for ids in grupos.values() for i in ids]
    assert sorted(vistos) == sorted(cat.CASOS)


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_todo_caso_tem_texto_e_croqui(caso: Caso):
    assert caso.titulo and caso.resumo and caso.descricao and caso.formula
    assert caso.id in CROQUIS or caso.id in modelos_de_secao.CATALOGO


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_todo_campo_tem_ajuda_decente(caso: Caso):
    chaves = [campo.chave for campo in caso.campos]
    assert len(chaves) == len(set(chaves)), "chave repetida"
    for campo in caso.campos:
        assert 3 <= len(campo.ajuda) <= 900, campo.chave
        assert campo.ajuda.strip()[-1] in ".!:", (caso.id, campo.chave)
        for palavra in PALAVRAS_PROIBIDAS:
            assert palavra not in campo.ajuda, campo.chave
        for coluna in campo.colunas:
            assert 3 <= len(coluna.ajuda) <= 300, coluna.chave
            assert coluna.ajuda.strip()[-1] in ".!:", (caso.id, coluna.chave)


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_o_padrao_do_campo_cabe_nos_limites(caso: Caso):
    posicao = {campo.chave: i for i, campo in enumerate(caso.campos)}
    for i, campo in enumerate(caso.campos):
        if campo.e_tabela:
            chaves = {coluna.chave for coluna in campo.colunas}
            assert all(set(linha) == chaves for linha in campo.padrao), campo.chave
        elif isinstance(campo.padrao, str):
            assert campo.padrao in campo.lista_de_opcoes, campo.chave
        elif not isinstance(campo.padrao, bool):
            if campo.minimo is not None:
                assert campo.padrao >= campo.minimo, campo.chave
            if campo.maximo is not None:
                assert campo.padrao <= campo.maximo, campo.chave
        if campo.quando is not None:
            # O formulário desenha na ordem: quem controla precisa vir antes.
            assert posicao[campo.quando[0]] < i, campo.chave


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_o_exemplo_padrao_abre_sem_reprovar(caso: Caso):
    """O número que aparece ao abrir o caso é um exemplo: não pode abrir reprovado."""
    resultado = calcular_caso(caso)
    assert isinstance(resultado, Resultado)
    assert resultado.resumo
    assert resultado.hipoteses, "o caso precisa dizer as hipóteses"
    assert resultado.referencias, "o caso precisa dizer de onde saiu a conta"
    assert resultado.status != "NÃO OK", [
        v.nome for v in resultado.verificacoes if v.status == "NÃO OK"
    ]


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_os_envios_apontam_para_campos_que_existem(caso: Caso):
    for envio in calcular_caso(caso).envios:
        destino = cat.CASOS[envio.destino]
        chaves = {campo.chave for campo in destino.campos}
        assert set(envio.valores) <= chaves, envio.rotulo


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_o_registro_passa_pelo_memorial(caso: Caso):
    valores = caso.padroes()
    resultado = calcular_caso(caso, valores)
    dados = dados_do_registro(
        caso, valores, resultado, modulo="Assistente de cargas", modulo_id="assistente_cargas"
    )
    registro = criar_registro_tecnico(**dados)  # recusa NaN e infinito
    if resultado.verificacoes:
        linhas = mv.extrair_linhas(registro) or []
        assert len(linhas) == len(resultado.verificacoes)
        capitulo = mv.capitulo_de_verificacoes(
            registro, linhas, titulo=caso.titulo, nivel=2, peca="Peça", formatar=str, rotular=str
        )
        assert capitulo


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_gera_o_word(caso: Caso):
    valores = caso.padroes()
    documento = gerar_word_do_caso(caso, valores, calcular_caso(caso, valores))
    assert documento[:2] == b"PK"


def _celula_ao_acaso(coluna, sorteio: random.Random):
    if coluna.opcional and sorteio.random() < 0.3:
        return None
    if coluna.opcoes:
        return sorteio.choice(coluna.opcoes)
    if isinstance(coluna.padrao, str):
        return coluna.padrao or "A"
    return _numero_ao_acaso(coluna, sorteio)


def _tabela_ao_acaso(campo, sorteio: random.Random):
    """Parte das linhas do exemplo, com células trocadas: ligações entre tabelas continuam certas."""
    linhas = []
    for linha in campo.padrao:
        nova = dict(linha)
        for coluna in campo.colunas:
            if sorteio.random() < 0.25 and not (
                isinstance(coluna.padrao, str) and not coluna.opcoes
            ):
                nova[coluna.chave] = _celula_ao_acaso(coluna, sorteio)
        linhas.append(nova)
    if len(linhas) > 1 and sorteio.random() < 0.2:
        linhas.pop(sorteio.randrange(len(linhas)))
    return tuple(linhas)


def _numero_ao_acaso(campo, sorteio: random.Random) -> float:
    padrao = float(campo.padrao or 0.0)
    inferior = campo.minimo if campo.minimo is not None else -abs(padrao) * 3.0 - 1.0
    superior = campo.maximo if campo.maximo is not None else abs(padrao) * 10.0 + 1.0
    escolha = sorteio.random()
    if escolha < 0.15:
        valor = inferior
    elif escolha < 0.30:
        valor = superior
    else:
        valor = sorteio.uniform(inferior, superior)
    return int(valor) if isinstance(campo.padrao, int) else float(valor)


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_fuzz_entrada_ruim_vira_mensagem_e_nunca_nan(caso: Caso):
    """Qualquer combinação dentro das faixas dos campos dá resultado ou ``ValueError`` com texto."""
    sorteio = random.Random(caso.id)
    for _ in range(120):
        valores = {}
        for campo in caso.campos:
            if campo.e_tabela:
                valores[campo.chave] = _tabela_ao_acaso(campo, sorteio)
            elif isinstance(campo.padrao, bool):
                valores[campo.chave] = sorteio.random() < 0.5
            elif isinstance(campo.padrao, str):
                valores[campo.chave] = sorteio.choice(campo.lista_de_opcoes)
            else:
                valores[campo.chave] = _numero_ao_acaso(campo, sorteio)
        try:
            resultado = calcular_caso(caso, valores)
        except ValueError as erro:
            assert str(erro), "mensagem vazia"
            assert not re.search(r"math domain|could not|invalid literal", str(erro)), str(erro)
            continue
        except (ZeroDivisionError, OverflowError):
            continue  # a página mostra como mensagem
        for metrica in resultado.metricas:
            if isinstance(metrica.valor, float):
                assert not math.isnan(metrica.valor), (caso.id, metrica.rotulo, valores)
        for linha in resultado.verificacoes:
            for numero in (linha.solicitante, linha.resistente):
                assert numero is None or not math.isnan(numero), (caso.id, linha.nome, valores)
        for ponto in resultado.pontos:
            assert not math.isnan(ponto.von_mises), (caso.id, ponto.nome, valores)
