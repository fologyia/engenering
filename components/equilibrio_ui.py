"""Tela da peça ou pórtico desenhado: modelo, prancheta, resposta, esforços nas barras e tabelas.

Mora dentro de Vigas e eixos. O corpo rígido dá as reações que a estática define; os trechos, lidos
como barras de pórtico, dão N, V e M e as reações da peça com apoio de sobra.

Os dados moram em ``st.session_state`` e três lugares os alteram: a prancheta, os modelos e as
tabelas. Os três entram por callback, antes de o script rodar, e por isso a prancheta recebe as
reações do desenho que acabou de mandar. ``versao`` conta as alterações: a prancheta ignora um
desenho mais velho que o dela. Todo aviso fica abaixo dela: acima, ele empurraria as ferramentas
durante o desenho, e um bloco que some remontaria a prancheta, com a seleção e o desfazer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.assistente_cargas_ui import (
    barra_de_navegacao,
    coluna_da_tabela,
    detalhes,
    quadro_da_tabela,
    resposta,
)
from components.figuras import mostrar_figura
from components.prancheta_equilibrio_ui import prancheta_do_equilibrio
from components.robustez import secao_protegida
from core import equilibrio_corpo as eq
from core.elementos_base import Caso, Resultado, calcular_caso, conferir_tabela
from core.elementos_equilibrio import (
    ROTULAS,
    SEM_PERFIL,
    marcas_para_a_tela,
    motivo_sem_barras,
    perfis_das_barras,
)
from core.equilibrio_modelos import MODELO_INICIAL, MODELOS, POR_NOME

DADOS = "eq_dados"
VERSAO = "eq_versao"
AJUSTE = "eq_ajuste"
MODELO = "eq_modelo"
COMPRIMENTO = "eq_comprimento"
FORCA = "eq_forca"
UNIDADES_ATUAIS = "eq_unidades_atuais"
MODELO_ATUAL = "eq_modelo_atual"
REVISAO = "eq_tabela_rev"
BASES = "eq_tabela_base"
ERRO_TABELA = "eq_erro_tabela"
CHAVE_PRANCHETA = "eq_prancheta"
BARRAS = "eq_barras"  # só os trechos que fogem do padrão: trecho, perfil e rótulas
BARRAS_BASE = "eq_barras_base"
BARRAS_REV = "eq_barras_rev"
PERFIL = "eq_perfil"
PERFIL_ATUAL = "eq_perfil_atual"
DIAGRAMA = "eq_diagrama"
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
    estado.setdefault(BARRAS, [])
    estado.setdefault(BARRAS_REV, 0)
    estado.setdefault(PERFIL_ATUAL, SEM_PERFIL)
    if DADOS in estado:
        return
    estado[VERSAO] = 0
    estado[AJUSTE] = 0
    estado[REVISAO] = 0
    estado[ERRO_TABELA] = ""
    estado[MODELO_ATUAL] = MODELO_INICIAL.nome
    estado[UNIDADES_ATUAIS] = (MODELO_INICIAL.comprimento, MODELO_INICIAL.forca)
    _trocar_dados(MODELO_INICIAL.dados(), ajustar=True)


def _aplicar_modelo() -> None:
    nome = st.session_state.get(MODELO)
    st.session_state[MODELO_ATUAL] = nome
    modelo = POR_NOME.get(nome or "")
    if modelo is None:
        return
    st.session_state[UNIDADES_ATUAIS] = (modelo.comprimento, modelo.forca)
    st.session_state[ERRO_TABELA] = ""
    _esquecer_barras()
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
    st.session_state[MODELO_ATUAL] = None
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
    estado[MODELO_ATUAL] = None
    _trocar_dados(dados, tabela=False)


def _esquecer_barras() -> None:
    """Peça nova: perfil e rótulas de cada trecho valiam para a peça de antes."""
    st.session_state[BARRAS] = []
    st.session_state[BARRAS_REV] = st.session_state.get(BARRAS_REV, 0) + 1


def _limpar() -> None:
    st.session_state[MODELO_ATUAL] = None
    st.session_state[ERRO_TABELA] = ""
    _esquecer_barras()
    _trocar_dados({nome: [] for nome, _ in TABELAS}, ajustar=True)


def _cabecalho() -> None:
    # O Streamlit apaga o estado do seletor que não foi desenhado: ao voltar de outro caso, a
    # unidade cairia em mm e N sem converter a peça. Quem manda são as chaves atuais.
    estado = st.session_state
    estado[COMPRIMENTO], estado[FORCA] = estado[UNIDADES_ATUAIS]
    estado[MODELO] = estado[MODELO_ATUAL]
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
            chave = f"eq_tabela_{nome}_{st.session_state[REVISAO]}"
            if chave not in st.session_state:
                # Voltando de outro caso: a edição guardada no editor se perdeu, os dados não.
                st.session_state[BASES][nome] = [dict(x) for x in st.session_state[DADOS][nome]]
            st.data_editor(
                quadro_da_tabela(campo, st.session_state[BASES][nome]),
                key=chave,
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


def _linhas_das_barras() -> list[dict[str, Any]]:
    """Uma linha por trecho desenhado, com o que já foi escolhido para ele."""
    estado = st.session_state
    escolhidas = {int(linha["trecho"]): linha for linha in estado[BARRAS]}
    linhas = []
    for numero, t in enumerate(estado[DADOS]["trechos"], start=1):
        escolha = escolhidas.get(numero, {})
        linhas.append(
            {
                "trecho": numero,
                "de": f"({t['x1']:g}; {t['y1']:g})",
                "ate": f"({t['x2']:g}; {t['y2']:g})",
                "perfil": escolha.get("perfil") or None,
                "rotulas": escolha.get("rotulas") or ROTULAS[0],
            }
        )
    return linhas


def _ao_editar_barras(chave: str) -> None:
    estado = st.session_state
    linhas = [dict(linha) for linha in estado[BARRAS_BASE]]
    for indice, campos in (estado.get(chave) or {}).get("edited_rows", {}).items():
        if int(indice) < len(linhas):
            linhas[int(indice)].update(campos)
    estado[BARRAS] = [
        {"trecho": l["trecho"], "perfil": l["perfil"] or "", "rotulas": l["rotulas"] or ROTULAS[0]}
        for l in linhas
        if l["perfil"] or (l["rotulas"] or ROTULAS[0]) != ROTULAS[0]
    ]


def _ao_escolher_perfil() -> None:
    st.session_state[PERFIL_ATUAL] = st.session_state[PERFIL]


def _secao_das_barras() -> None:
    estado = st.session_state
    perfis = perfis_das_barras()
    if estado[PERFIL_ATUAL] not in perfis:  # perfil apagado do catálogo
        estado[PERFIL_ATUAL] = SEM_PERFIL
    estado[BARRAS] = [l for l in estado[BARRAS] if not l["perfil"] or l["perfil"] in perfis]
    estado[PERFIL] = estado[PERFIL_ATUAL]
    with st.expander("Seção e rótulas das barras", icon=":material/view_column:"):
        st.selectbox(
            "Perfil das barras",
            perfis,
            key=PERFIL,
            on_change=_ao_escolher_perfil,
            help="Só muda o resultado quando há apoio de sobra, e a deformada. Sem perfil, todas "
            "as barras têm a mesma rigidez.",
        )
        chave = f"eq_barras_editor_{len(estado[DADOS]['trechos'])}_{estado[BARRAS_REV]}"
        if chave not in estado or BARRAS_BASE not in estado:
            estado[BARRAS_BASE] = _linhas_das_barras()
        base = estado[BARRAS_BASE]
        for linha, atual in zip(base, _linhas_das_barras(), strict=False):
            linha["de"], linha["ate"] = atual["de"], atual["ate"]
        if len(base) != len(estado[DADOS]["trechos"]):
            estado[BARRAS_BASE] = base = _linhas_das_barras()
        st.data_editor(
            pd.DataFrame(base, columns=["trecho", "de", "ate", "perfil", "rotulas"]),
            key=chave,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            disabled=["trecho", "de", "ate"],
            column_config={
                "trecho": st.column_config.NumberColumn(
                    "Trecho", help="Número do trecho: a barra B1 é o trecho 1."
                ),
                "de": st.column_config.TextColumn("Início", help="Onde o trecho começa."),
                "ate": st.column_config.TextColumn("Fim", help="Onde o trecho termina."),
                "perfil": st.column_config.SelectboxColumn(
                    "Perfil",
                    options=[p for p in perfis if p != SEM_PERFIL],
                    help="Em branco, vale o perfil das barras, escolhido acima.",
                ),
                "rotulas": st.column_config.SelectboxColumn(
                    "Rótulas",
                    options=list(ROTULAS),
                    required=True,
                    help="Rótula na ponta: a barra não passa momento ali, como numa ligação "
                    "por um parafuso só.",
                ),
            },
            on_change=_ao_editar_barras,
            args=(chave,),
        )
        st.caption(
            "As barras se ligam de forma rígida onde uma ponta toca outra barra. Trechos que só "
            "se cruzam pelo meio não se ligam."
        )


def _esforcos_nas_barras(caso: Caso, valores: Mapping[str, Any], resultado: Resultado) -> None:
    """N, V, M, reações e deformada das barras, uma figura por vez, no jeito do Ftool."""
    if not st.session_state[DADOS]["trechos"]:
        return
    st.markdown("##### Esforços nas barras")
    figuras = {figura.titulo: figura for figura in resultado.figuras[1:]}
    if not figuras:
        try:
            motivo = motivo_sem_barras(valores_conferidos(caso, {**caso.padroes(), **valores}))
        except ValueError as erro:
            motivo = str(erro)
        if motivo:
            st.info(motivo, icon=":material/info:")
        return
    nomes = list(figuras)
    if st.session_state.get(DIAGRAMA) not in nomes:
        st.session_state[DIAGRAMA] = nomes[0]
    escolhido = st.segmented_control(
        "Diagrama",
        nomes,
        key=DIAGRAMA,
        required=True,
        label_visibility="collapsed",
        help="Momento desenhado do lado tracionado da barra. Normal positivo é tração.",
    )
    mostrar_figura(figuras[escolhido or nomes[0]])


def tela_do_equilibrio(caso: Caso, *, navegacao: bool = True) -> None:
    if navegacao:
        barra_de_navegacao(caso)
    _iniciar()
    _cabecalho()

    estado = st.session_state
    unidades = eq.Unidades(estado[COMPRIMENTO], estado[FORCA])
    valores: dict[str, Any] = {
        "comprimento": unidades.comprimento,
        "forca": unidades.forca,
        **estado[DADOS],
        "perfil_das_barras": estado[PERFIL_ATUAL],
        "barras": estado[BARRAS],
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
        with secao_protegida("Esforços nas barras"):
            _esforcos_nas_barras(caso, valores, resultado)
    if estado[DADOS]["trechos"]:
        _secao_das_barras()
    _tabelas(caso)
    if resultado is not None:
        detalhes(caso, valores, resultado, figuras=False)
