"""Indicadores e detalhamento dos dados permanentes do projeto ativo."""

from collections.abc import Mapping
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from core.project_checklist import resumo_checklist
from core.project_records import resumir_registros

_CORES_GRAVIDADE = {
    "Bloqueio": "#dc4449",
    "Pendência": "#c27b21",
    "Atenção": "#ad8d26",
    "Informação": "#4188be",
}


def _validacao(validacao: Mapping[str, Any], chave: str) -> None:
    severidade = st.selectbox(
        "Gravidade",
        list(_CORES_GRAVIDADE),
        index=None,
        placeholder="Todas as gravidades",
        key=f"{chave}_gravidade",
        help="Filtra o gráfico e a tabela de achados.",
    )
    achados = pd.DataFrame.from_records(
        achado
        for achado in validacao["achados"]
        if severidade is None or achado["severidade"] == severidade
    )
    if achados.empty:
        st.caption("Nenhum achado de validação neste filtro.")
        return

    contagem = achados.value_counts(["categoria", "severidade"]).rename("total").reset_index()
    grafico = (
        alt.Chart(contagem)
        .mark_bar()
        .encode(
            x=alt.X("total:Q", title="Achados", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("categoria:N", title=None, sort="-x"),
            color=alt.Color(
                "severidade:N",
                title="Gravidade",
                scale=alt.Scale(
                    domain=list(_CORES_GRAVIDADE), range=list(_CORES_GRAVIDADE.values())
                ),
            ),
            tooltip=[
                alt.Tooltip("categoria:N", title="Área"),
                alt.Tooltip("severidade:N", title="Gravidade"),
                alt.Tooltip("total:Q", title="Achados"),
            ],
        )
        .properties(height=max(120, 25 * contagem["categoria"].nunique()))
    )
    st.altair_chart(grafico, width="stretch")
    st.dataframe(
        achados[["severidade", "categoria", "titulo", "recomendacao"]].rename(
            columns={
                "severidade": "Gravidade",
                "categoria": "Área",
                "titulo": "Achado",
                "recomendacao": "Ação sugerida",
            }
        ),
        hide_index=True,
    )
    st.page_link(
        "app_pages/central_validacao.py",
        label="Abrir validação completa",
        icon=":material/fact_check:",
    )


def _calculos(projeto: Mapping[str, Any], resumo: Mapping[str, Any], chave: str) -> None:
    registros = pd.DataFrame.from_records(
        linha for linha in resumir_registros(projeto) if not linha["superado"]
    )
    if registros.empty:
        st.caption("Os cálculos gravados no projeto aparecem aqui.")
        return

    st.caption(
        f"{resumo['registros_nao_atendem']} com resultado de não atendimento · "
        f"{resumo['registros_superados']} superados no histórico"
    )
    modulos, fontes = st.columns(2)
    modulo = modulos.selectbox(
        "Módulo",
        sorted(registros["modulo"].unique()),
        index=None,
        placeholder="Todos os módulos",
        key=f"{chave}_modulo",
        help="Filtra os cálculos pelo módulo de origem.",
    )
    atualidade = fontes.selectbox(
        "Atualidade das fontes",
        sorted(registros["atualidade"].unique()),
        index=None,
        placeholder="Todos os estados",
        key=f"{chave}_atualidade",
        help="Filtra pela situação das dependências do cálculo.",
    )
    if modulo is not None:
        registros = registros[registros["modulo"] == modulo]
    if atualidade is not None:
        registros = registros[registros["atualidade"] == atualidade]
    if registros.empty:
        st.caption("Nenhum cálculo vigente corresponde aos filtros.")
        return

    contagem = registros["modulo"].value_counts().rename_axis("Módulo").reset_index(name="Cálculos")
    grafico = (
        alt.Chart(contagem.head(12))
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("Cálculos:Q", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("Módulo:N", title=None, sort="-x"),
            tooltip=["Módulo:N", "Cálculos:Q"],
        )
        .properties(height=max(100, 25 * min(len(contagem), 12)))
    )
    st.caption(f"{len(registros)} cálculos no recorte · módulos com mais registros")
    st.altair_chart(grafico, width="stretch")
    registros = registros.astype({"utilizacao": "float64", "menor_fator": "float64"})
    tabela = registros.sort_values("utilizacao", ascending=False, kind="stable")[
        ["titulo", "peca", "modulo", "status", "atualidade", "utilizacao", "menor_fator"]
    ].rename(
        columns={
            "titulo": "Cálculo",
            "peca": "Peça",
            "modulo": "Módulo",
            "status": "Resultado",
            "atualidade": "Atualidade",
            "utilizacao": "Utilização",
            "menor_fator": "Menor fator",
        }
    )
    st.dataframe(
        tabela,
        hide_index=True,
        column_config={
            "Utilização": st.column_config.NumberColumn(format="percent"),
            "Menor fator": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.caption("Utilização e fator de segurança aparecem quando registrados pelo módulo.")


def _prazos(projeto: Mapping[str, Any], chave: str) -> None:
    checklist = resumo_checklist(projeto.get("checklist", []))
    st.caption(
        f"{checklist['abertos']} de {checklist['total']} itens em aberto · "
        f"{checklist['criticos_abertos']} críticos · "
        f"{len(checklist['proximos'])} com prazo de hoje aos próximos 7 dias"
    )
    abertos = checklist["itens_abertos"]
    if not abertos:
        st.caption("Nenhum item do checklist em aberto.")
        return

    situacao = st.selectbox(
        "Situação do prazo",
        list(dict.fromkeys(item["situacao"] for item in abertos)),
        index=None,
        placeholder="Todos os prazos",
        key=f"{chave}_prazo",
        help="Mostra itens em aberto pela situação do prazo.",
    )
    linhas = sorted(
        (item for item in abertos if situacao is None or item["situacao"] == situacao),
        key=lambda item: (item["dias"] is None, item["dias"] or 0, not item["critico"]),
    )
    st.dataframe(
        [
            {
                "Item": item["item"],
                "Responsável": item["responsavel"] or "Sem responsável",
                "Prazo": item["prazo_texto"],
                "Dias até o prazo": item["dias"],
                "Situação": item["situacao"],
                "Crítico": item["critico"],
            }
            for item in linhas
        ],
        hide_index=True,
    )


def _escopo(projeto: Mapping[str, Any]) -> None:
    with st.container(horizontal=True):
        for campo, rotulo in (
            ("componentes", "Componentes"),
            ("casos_carga", "Casos de carga"),
            ("combinacoes_carga", "Combinações"),
            ("materiais_projeto", "Materiais"),
            ("normas", "Normas"),
            ("anexos", "Documentos"),
        ):
            registros = sum(isinstance(item, Mapping) for item in projeto.get(campo, []))
            st.metric(rotulo, registros, border=True)


def renderizar_painel_projeto(
    projeto: Mapping[str, Any],
    validacao: Mapping[str, Any],
    resumo: Mapping[str, Any],
    *,
    origem: str,
) -> None:
    chave = f"painel_projeto_{origem}_{projeto['id']}"
    cor = "red" if resumo["bloqueios"] else "orange" if resumo["pendencias"] else "blue"
    st.badge(validacao["prontidao"], color=cor, icon=":material/fact_check:")
    with st.container(horizontal=True):
        st.metric(
            "Índice documental",
            f"{validacao['indice_documental']}%",
            border=True,
            help=validacao["aviso"],
        )
        st.metric("Bloqueios", resumo["bloqueios"], border=True)
        st.metric("Cálculos vigentes", resumo["registros"], border=True)
        st.metric(
            "Fontes a revisar",
            resumo["registros_desatualizados"],
            border=True,
            help="Cálculos vigentes com fonte alterada, ausente ou em ciclo de dependências.",
        )
        st.metric("Prazos vencidos", resumo["checklist_vencidos"], border=True)
        total = resumo["checklist_total"]
        encerrados = total - resumo["checklist_abertos"]
        st.metric(
            "Checklist encerrado",
            f"{encerrados}/{total}" if total else "—",
            border=True,
            help="Inclui itens concluídos ou classificados como não aplicáveis.",
        )

    visao = st.segmented_control(
        "Analisar o projeto por",
        ("Validação", "Cálculos", "Prazos", "Escopo"),
        default="Validação",
        key=f"{chave}_visao",
        help="Escolha os dados que deseja detalhar abaixo dos indicadores do projeto.",
    )
    with st.container(border=True):
        if visao == "Cálculos":
            _calculos(projeto, resumo, chave)
        elif visao == "Prazos":
            _prazos(projeto, chave)
        elif visao == "Escopo":
            _escopo(projeto)
        else:
            _validacao(validacao, chave)
