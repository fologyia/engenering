"""Tela do Equilíbrio de uma peça: modelo, prancheta, resposta e os mesmos dados em tabela.

Os dados moram em ``st.session_state`` e três lugares os alteram: a prancheta, os modelos e as
tabelas. Os três entram por callback, antes de o script rodar, e por isso a prancheta recebe as
reações do desenho que acabou de mandar. ``versao`` conta as alterações: a prancheta ignora um
desenho mais velho que o dela. Todo aviso fica abaixo dela: acima, ele empurraria as ferramentas
durante o desenho, e um bloco que some remontaria a prancheta, com a seleção e o desfazer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

from components.assistente_cargas_ui import (
    barra_de_navegacao,
    coluna_da_tabela,
    detalhes,
    quadro_da_tabela,
    resposta,
)
from components.prancheta_equilibrio_ui import prancheta_do_equilibrio
from core import equilibrio_corpo as eq
from core.elementos_base import Caso, Resultado, calcular_caso, conferir_tabela
from core.elementos_equilibrio import marcas_para_a_tela
from core.equilibrio_modelos import MODELO_INICIAL, MODELOS, POR_NOME

DADOS = "eq_dados"
VERSAO = "eq_versao"
AJUSTE = "eq_ajuste"
MODELO = "eq_modelo"
COMPRIMENTO = "eq_comprimento"
FORCA = "eq_forca"
UNIDADES_ATUAIS = "eq_unidades_atuais"
REVISAO = "eq_tabela_rev"
BASES = "eq_tabela_base"
ERRO_TABELA = "eq_erro_tabela"
CHAVE_PRANCHETA = "eq_prancheta"
TABELAS = (
    ("apoios", "Apoios"),
    ("cargas", "Cargas"),
    ("trechos", "Trechos da peça"),
    ("cortes", "Seções"),
)


def _trocar_dados(
    dados: Mapping[str, Any],
    *,
    ajustar: bool = False,
    tabela: bool = True,
    versao: int | None = None,
) -> None:
    estado = st.session_state
    estado[DADOS] = {nome: [dict(linha) for linha in dados[nome]] for nome, _ in TABELAS}
    estado[VERSAO] = estado[VERSAO] + 1 if versao is None else versao
    if ajustar:
        estado[AJUSTE] += 1
    if tabela:  # base nova nas tabelas: a edição guardada nelas valia para a base antiga
        estado[REVISAO] += 1
        estado[BASES] = {
            nome: [dict(linha) for linha in estado[DADOS][nome]] for nome, _ in TABELAS
        }


def _iniciar() -> None:
    estado = st.session_state
    if DADOS in estado:
        return
    estado[VERSAO] = 0
    estado[AJUSTE] = 0
    estado[REVISAO] = 0
    estado[ERRO_TABELA] = ""
    estado[MODELO] = MODELO_INICIAL.nome
    estado[COMPRIMENTO] = MODELO_INICIAL.comprimento
    estado[FORCA] = MODELO_INICIAL.forca
    estado[UNIDADES_ATUAIS] = (MODELO_INICIAL.comprimento, MODELO_INICIAL.forca)
    _trocar_dados(MODELO_INICIAL.dados(), ajustar=True)


def _aplicar_modelo() -> None:
    modelo = POR_NOME.get(st.session_state.get(MODELO) or "")
    if modelo is None:
        return
    st.session_state[COMPRIMENTO] = modelo.comprimento
    st.session_state[FORCA] = modelo.forca
    st.session_state[UNIDADES_ATUAIS] = (modelo.comprimento, modelo.forca)
    st.session_state[ERRO_TABELA] = ""
    _trocar_dados(modelo.dados(), ajustar=True)


def _ao_trocar_unidade() -> None:
    estado = st.session_state
    de = eq.Unidades(*estado[UNIDADES_ATUAIS])
    para = eq.Unidades(estado[COMPRIMENTO], estado[FORCA])
    estado[UNIDADES_ATUAIS] = (para.comprimento, para.forca)
    _trocar_dados(eq.converter_dados(estado[DADOS], de, para))


def _ao_editar_na_prancheta() -> None:
    evento = getattr(st.session_state.get(CHAVE_PRANCHETA), "edicao", None)
    if not evento:
        return
    dados = evento.get("dados") or {}
    if any(not isinstance(dados.get(nome), list) for nome, _ in TABELAS):
        return
    # O modelo deixa de mandar: a escolha na lista já não descreve o desenho.
    st.session_state[MODELO] = None
    st.session_state[ERRO_TABELA] = ""
    _trocar_dados(dados, versao=int(evento.get("versao", 0)))


def _ao_editar_tabela(caso: Caso, nome: str) -> None:
    estado = st.session_state
    mudancas = estado.get(f"eq_tabela_{nome}_{estado[REVISAO]}") or {}
    linhas = [dict(linha) for linha in estado[BASES][nome]]
    for indice, campos in mudancas.get("edited_rows", {}).items():
        linhas[int(indice)].update(campos)
    apagadas = {int(i) for i in mudancas.get("deleted_rows", [])}
    linhas = [linha for i, linha in enumerate(linhas) if i not in apagadas]
    linhas += [dict(nova) for nova in mudancas.get("added_rows", [])]
    campo = next(c for c in caso.campos if c.chave == nome)
    estado[ERRO_TABELA] = ""
    try:
        conferidas = conferir_tabela(campo, linhas)
    except ValueError as erro:
        estado[ERRO_TABELA] = str(erro)
        return
    dados = dict(estado[DADOS])
    dados[nome] = eq.nomear(nome, conferidas)
    estado[MODELO] = None
    _trocar_dados(dados, tabela=False)


def _limpar() -> None:
    st.session_state[MODELO] = None
    st.session_state[ERRO_TABELA] = ""
    _trocar_dados({nome: [] for nome, _ in TABELAS}, ajustar=True)


def _cabecalho() -> None:
    colunas = st.columns([4, 1, 1, 1], vertical_alignment="bottom")
    colunas[0].selectbox(
        "Começar de um modelo",
        [modelo.nome for modelo in MODELOS],
        index=None,
        placeholder="Desenho meu, sem modelo",
        key=MODELO,
        on_change=_aplicar_modelo,
        format_func=lambda nome: f"{nome}: {POR_NOME[nome].dica}",
        help="Abre a peça pronta com números de exemplo. Depois é só arrastar ou digitar por cima.",
    )
    colunas[1].selectbox(
        "Comprimento",
        tuple(eq.COMPRIMENTOS),
        key=COMPRIMENTO,
        on_change=_ao_trocar_unidade,
        help="Trocar a unidade converte os números: a peça continua a mesma.",
    )
    colunas[2].selectbox(
        "Força",
        tuple(eq.FORCAS),
        key=FORCA,
        on_change=_ao_trocar_unidade,
        help="Vale para forças e reações. Momento sai em força vezes metro.",
    )
    colunas[3].button(
        "Limpar",
        key="eq_limpar",
        icon=":material/delete:",
        on_click=_limpar,
        help="Apaga o desenho para começar do zero.",
        width="stretch",
    )


def _tabelas(caso: Caso) -> None:
    with st.expander("Dados em tabela", icon=":material/table_chart:"):
        st.caption("A mesma peça da prancheta. Mudou aqui, muda lá.")
        erro = st.session_state[ERRO_TABELA]
        if erro:
            st.error(erro, icon=":material/error:")
        for nome, titulo in TABELAS:
            campo = next(c for c in caso.campos if c.chave == nome)
            st.markdown(f"**{titulo}**")
            st.caption(campo.ajuda)
            st.data_editor(
                quadro_da_tabela(campo, st.session_state[BASES][nome]),
                key=f"eq_tabela_{nome}_{st.session_state[REVISAO]}",
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                placeholder="—",
                column_config={c.chave: coluna_da_tabela(c) for c in campo.colunas},
                on_change=_ao_editar_tabela,
                args=(caso, nome),
            )


def _marcas(valores: Mapping[str, Any], caso: Caso) -> dict[str, Any] | None:
    try:
        return marcas_para_a_tela(valores_conferidos(caso, valores))
    except ValueError:
        return None


def valores_conferidos(caso: Caso, valores: Mapping[str, Any]) -> dict[str, Any]:
    conferidos = dict(valores)
    for campo in caso.campos:
        if campo.e_tabela:
            conferidos[campo.chave] = conferir_tabela(campo, valores[campo.chave])
    return conferidos


def tela_do_equilibrio(caso: Caso) -> None:
    barra_de_navegacao(caso)
    _iniciar()
    _cabecalho()

    estado = st.session_state
    unidades = eq.Unidades(estado[COMPRIMENTO], estado[FORCA])
    valores: dict[str, Any] = {
        "comprimento": unidades.comprimento,
        "forca": unidades.forca,
        **estado[DADOS],
    }
    resultado: Resultado | None = None
    erro = ""
    try:
        resultado = calcular_caso(caso, valores)
    except (ValueError, ZeroDivisionError, OverflowError) as falha:
        erro = str(falha)

    prancheta_do_equilibrio(
        {
            "dados": estado[DADOS],
            "versao": estado[VERSAO],
            "ajustar": estado[AJUSTE],
            "unidades": {
                "c": unidades.comprimento,
                "f": unidades.forca,
                "m": unidades.momento,
                "q": unidades.distribuida,
            },
            "marcas": _marcas(valores, caso) if resultado is not None else None,
        },
        key=CHAVE_PRANCHETA,
        ao_editar=_ao_editar_na_prancheta,
    )
    if erro:
        vazio = not estado[DADOS]["apoios"] or not estado[DADOS]["cargas"]
        (st.info if vazio else st.error)(erro, icon=":material/info:")
    if resultado is not None:
        resposta(resultado, por_linha=4)
    _tabelas(caso)
    if resultado is not None:
        detalhes(caso, valores, resultado)
