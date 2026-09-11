"""Painel da carteira: todos os projetos industriais numa tela só."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.project_tools import sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_portfolio import (
    proximos_passos,
    resumir_carteira,
    resumir_projeto,
    vencimentos_da_carteira,
)
from core.project_store import carregar_projetos, definir_projeto_ativo
from core.project_workflow import SITUACOES

st.set_page_config(
    page_title="Painel industrial",
    page_icon=":material/dashboard:",
    layout="wide",
)

cabecalho_pagina(
    "Painel industrial",
    "A carteira inteira: situação, prontidão, bloqueios, prazos vencidos e cálculos desatualizados de cada projeto.",
    categoria="GESTÃO INDUSTRIAL",
    icone=":material/dashboard:",
    cor="blue",
    ajuda_modulo="Painel industrial",
    acoes=(
        ("app_pages/gestao_projetos.py", "Projetos", ":material/folder_managed:"),
        ("app_pages/central_validacao.py", "Validação", ":material/fact_check:"),
    ),
)


def _data_curta(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    try:
        return datetime.fromisoformat(texto).astimezone().strftime("%d/%m/%Y")
    except ValueError:
        return texto


sincronizar_projeto_ativo()
ativo = st.session_state.get("projeto_ativo") or {}

incluir_arquivados = st.toggle("Incluir projetos arquivados", value=False)
projetos = carregar_projetos(incluir_arquivados=incluir_arquivados)
if not projetos:
    st.info("Nenhum projeto no banco. Crie o primeiro em Projetos permanentes.")
    st.page_link("app_pages/gestao_projetos.py", label="Abrir Projetos permanentes", icon=":material/folder_managed:")
    st.stop()

hoje = date.today()
resumos = [resumir_projeto(projeto, hoje=hoje) for projeto in projetos]
por_id = {resumo["id"]: (projeto, resumo) for projeto, resumo in zip(projetos, resumos, strict=True)}
carteira = resumir_carteira(resumos)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Projetos", carteira["total"], border=True)
m2.metric("Com bloqueio", carteira["com_bloqueio"], border=True, help="Projetos com ao menos um bloqueio na validação.")
m3.metric("Prontos", carteira["prontos"], border=True, help="Prontos para revisão: sem bloqueios nem pendências documentais.")
m4.metric("Vencidos", carteira["checklist_vencidos"], border=True, help="Itens de checklist abertos com prazo anterior a hoje, somados na carteira.")
m5.metric("Desatualizados", carteira["registros_desatualizados"], border=True, help="Cálculos cujas fontes mudaram depois do registro.")
m6.metric("Índice médio", f"{carteira['indice_medio']}%", border=True, help="Média do índice documental dos projetos listados.")

situacoes_presentes = [situacao for situacao in SITUACOES if carteira["por_situacao"].get(situacao)]
if situacoes_presentes:
    st.caption(
        "Por situação: "
        + " · ".join(f"**{situacao}** {carteira['por_situacao'][situacao]}" for situacao in situacoes_presentes)
    )

# ------------------------------------------------------------- Filtros
f1, f2, f3 = st.columns([2, 2, 3])
filtro_situacao = f1.multiselect("Situação", situacoes_presentes, default=situacoes_presentes)
clientes = sorted({resumo["cliente"] for resumo in resumos if resumo["cliente"]})
filtro_cliente = f2.multiselect("Cliente", clientes, default=clientes)
busca = f3.text_input("Buscar", placeholder="código, nome, TAG, unidade, responsável…")

def _corresponde(resumo: dict[str, Any]) -> bool:
    if resumo["status"] not in filtro_situacao:
        return False
    if clientes and resumo["cliente"] and resumo["cliente"] not in filtro_cliente:
        return False
    if busca.strip():
        alvo = " ".join(
            str(resumo[chave]) for chave in ("codigo", "nome", "tag", "unidade", "area", "responsavel", "cliente")
        ).casefold()
        return busca.strip().casefold() in alvo
    return True


visiveis = [resumo for resumo in resumos if _corresponde(resumo)]

# ------------------------------------------------------ Atenção imediata
urgentes = [
    resumo
    for resumo in visiveis
    if resumo["bloqueios"] or resumo["checklist_vencidos"] or resumo["registros_desatualizados"] or resumo["registros_nao_atendem"]
]
if urgentes:
    with st.container(border=True):
        st.markdown("##### Atenção imediata")
        for resumo in urgentes:
            motivos = []
            if resumo["registros_nao_atendem"]:
                motivos.append(f"{resumo['registros_nao_atendem']} resultado(s) não atende(m)")
            if resumo["bloqueios"]:
                motivos.append(f"{resumo['bloqueios']} bloqueio(s)")
            if resumo["checklist_vencidos"]:
                motivos.append(f"{resumo['checklist_vencidos']} prazo(s) vencido(s)")
            if resumo["registros_desatualizados"]:
                motivos.append(f"{resumo['registros_desatualizados']} cálculo(s) desatualizado(s)")
            st.markdown(f"- **{resumo['codigo']} · {resumo['nome']}** ({resumo['status']}): " + "; ".join(motivos) + ".")
else:
    st.success("Nenhum projeto visível exige atenção imediata.", icon=":material/check_circle:")

# ---------------------------------------------------------- Tabela geral
st.markdown("##### Carteira")
tabela = pd.DataFrame(
    [
        {
            "id": resumo["id"],
            "Ativo": resumo["id"] == ativo.get("id"),
            "Código": resumo["codigo"],
            "Projeto": resumo["nome"],
            "Situação": resumo["status"],
            "Rev.": f"{resumo['revisao']:02d}",
            "Prontidão": resumo["prontidao"],
            "Índice": resumo["indice_documental"],
            "Bloqueios": resumo["bloqueios"],
            "Pendências": resumo["pendencias"],
            "Checklist": resumo["checklist_percentual"],
            "Vencidos": resumo["checklist_vencidos"],
            "Registros": resumo["registros"],
            "Desatualizados": resumo["registros_desatualizados"],
            "Responsável": resumo["responsavel"] or "—",
            "Cliente": resumo["cliente"] or "—",
            "Atualizado": _data_curta(resumo["atualizado_em"]),
            "Parado (dias)": (
                resumo["dias_sem_atualizacao"] if resumo["dias_sem_atualizacao"] is not None else float("nan")
            ),
        }
        for resumo in visiveis
    ]
)
if tabela.empty:
    st.info("Nenhum projeto corresponde aos filtros.")
else:
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "id": None,
            "Ativo": st.column_config.CheckboxColumn("Ativo", disabled=True, width="small"),
            "Índice": st.column_config.ProgressColumn("Índice documental", min_value=0, max_value=100, format="%d%%"),
            "Checklist": st.column_config.ProgressColumn("Checklist", min_value=0, max_value=100, format="%d%%"),
            "Projeto": st.column_config.TextColumn(width="large"),
        },
    )
    st.download_button(
        "Baixar carteira (CSV)",
        data=tabela.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"carteira_{hoje.isoformat()}.csv",
        mime="text/csv",
        icon=":material/download:",
    )

# ------------------------------------------------------- Vencimentos
vencimentos = vencimentos_da_carteira(visiveis)
col_venc, col_detalhe = st.columns([1, 1])
with col_venc, st.container(border=True):
    st.markdown("##### Prazos vencidos e da semana")
    if vencimentos:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Projeto": linha["projeto"],
                        "Item": linha["item"],
                        "Responsável": linha["responsavel"] or "—",
                        "Prazo": linha["prazo_texto"],
                        "Dias": linha["dias"],
                        "Situação": linha["situacao"],
                        "Crítico": linha["critico"],
                    }
                    for linha in vencimentos
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhum item vencido ou a vencer em 7 dias nos projetos visíveis.")

with col_detalhe, st.container(border=True):
    st.markdown("##### Próximos passos de um projeto")
    if visiveis:
        opcoes = {resumo["id"]: f"{resumo['codigo']} · {resumo['nome']}" for resumo in visiveis}
        ids = list(opcoes)
        indice_padrao = ids.index(ativo["id"]) if ativo.get("id") in ids else 0
        escolhido = st.selectbox("Projeto", ids, index=indice_padrao, format_func=lambda valor: opcoes[valor])
        projeto_escolhido, resumo_escolhido = por_id[escolhido]
        for numero, passo in enumerate(proximos_passos(projeto_escolhido, resumo=resumo_escolhido), start=1):
            st.markdown(f"**{numero}. {passo['titulo']}** — {passo['detalhe']}")
        if escolhido != ativo.get("id"):
            if st.button("Abrir como projeto ativo", icon=":material/folder_open:", key="painel_abrir"):
                definir_projeto_ativo(escolhido)
                st.rerun()
        else:
            st.page_link("app_pages/gestao_projetos.py", label="Este é o projeto ativo — abrir", icon=":material/folder_managed:")
    else:
        st.caption("Sem projetos visíveis.")

st.info(
    "O painel lê o banco local a cada abertura. Índice documental e prontidão medem preenchimento e "
    "rastreabilidade — não certificam conformidade nem aprovação de engenharia.",
    icon=":material/info:",
)
