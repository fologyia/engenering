"""Painel da carteira: todos os projetos industriais numa tela só."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
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
from core.project_store import (
    VARIAVEL_BANCO,
    ProjetoPersistenciaErro,
    caminho_banco_atual,
    carregar_projetos,
    definir_projeto_ativo,
    exportar_carteira,
    fazer_backup,
    importar_carteira,
    listar_backups,
    pasta_backups,
)
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


def _data_hora(valor: Any) -> str:
    texto = str(valor or "").strip()
    try:
        return datetime.fromisoformat(texto).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return texto


def _tamanho(bytes_: int) -> str:
    if bytes_ >= 1_048_576:
        return f"{bytes_ / 1_048_576:.1f} MB"
    return f"{max(1, bytes_ // 1024)} KB"


def _secao_dados_e_backup(*, expandida: bool) -> None:
    """Onde o banco está, backup íntegro e exportação/restauração da carteira.

    Fica no painel — e não em Projetos permanentes — porque trata da carteira
    inteira e precisa existir mesmo sem nenhum projeto no banco: restaurar
    uma carteira exportada é justamente o que se faz num banco vazio.
    """
    banco = caminho_banco_atual()
    with st.expander("Dados e backup", icon=":material/database:", expanded=expandida):
        tamanho = _tamanho(banco.stat().st_size) if banco.exists() else "ainda não criado"
        st.caption(
            f"Banco de projetos: `{banco}` ({tamanho}). Para usar outro arquivo, defina a "
            f"variável de ambiente `{VARIAVEL_BANCO}` antes de abrir o programa."
        )
        with st.container(horizontal=True):
            if st.button(
                "Gerar backup do banco",
                icon=":material/backup:",
                help=(
                    "Grava uma cópia íntegra e compactada (VACUUM INTO) na pasta backups/, "
                    "ao lado do banco. Nunca sobrescreve um backup anterior."
                ),
            ):
                try:
                    st.session_state["painel_ultimo_backup"] = str(fazer_backup())
                except ProjetoPersistenciaErro as erro:
                    st.error(str(erro))
            st.download_button(
                "Exportar carteira (JSON)",
                data=exportar_carteira,
                file_name=f"carteira_{date.today().isoformat()}.json",
                mime="application/json",
                icon=":material/download:",
                help=(
                    "Todos os projetos, com revisões e linha do tempo, num arquivo legível. "
                    "É o pacote que a restauração abaixo aceita."
                ),
            )
        ultimo = st.session_state.get("painel_ultimo_backup")
        if ultimo and Path(ultimo).exists():
            st.success(f"Backup gravado em `{ultimo}`.", icon=":material/check_circle:")
            st.download_button(
                "Baixar este backup",
                data=lambda: Path(ultimo).read_bytes(),
                file_name=Path(ultimo).name,
                mime="application/vnd.sqlite3",
                icon=":material/download:",
                key="painel_baixar_backup",
            )
        backups = listar_backups()
        if backups:
            st.caption(
                f"Backups em `{pasta_backups()}` — "
                + " · ".join(
                    f"{item['nome']} ({_data_hora(item['modificado_em'])}, "
                    f"{_tamanho(item['tamanho_bytes'])})"
                    for item in backups[:5]
                )
                + (f" · e mais {len(backups) - 5}" if len(backups) > 5 else "")
                + "."
            )
        arquivo = st.file_uploader(
            "Restaurar uma carteira exportada",
            type=["json"],
            key="painel_importar_carteira",
            help=(
                "Projetos que já existem no banco (mesmo id) são ignorados: a restauração "
                "nunca sobrescreve o que está gravado."
            ),
        )
        if arquivo and st.button("Restaurar projetos do arquivo", icon=":material/upload:"):
            try:
                resultado = importar_carteira(arquivo.getvalue())
            except ProjetoPersistenciaErro as erro:
                st.error(str(erro))
            else:
                st.toast(
                    f"{len(resultado['importados'])} projeto(s) restaurado(s); "
                    f"{len(resultado['ignorados'])} já existia(m) e foi/foram ignorado(s).",
                    icon=":material/check_circle:",
                )
                st.rerun()


sincronizar_projeto_ativo()
ativo = st.session_state.get("projeto_ativo") or {}

incluir_arquivados = st.toggle("Incluir projetos arquivados", value=False)
projetos = carregar_projetos(incluir_arquivados=incluir_arquivados)
if not projetos:
    st.info("Nenhum projeto no banco. Crie o primeiro em Projetos permanentes.")
    st.page_link(
        "app_pages/gestao_projetos.py",
        label="Abrir Projetos permanentes",
        icon=":material/folder_managed:",
    )
    _secao_dados_e_backup(expandida=True)
    st.stop()

hoje = date.today()
resumos = [resumir_projeto(projeto, hoje=hoje) for projeto in projetos]
por_id = {
    resumo["id"]: (projeto, resumo) for projeto, resumo in zip(projetos, resumos, strict=True)
}
carteira = resumir_carteira(resumos)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Projetos", carteira["total"], border=True)
m2.metric(
    "Com bloqueio",
    carteira["com_bloqueio"],
    border=True,
    help="Projetos com ao menos um bloqueio na validação.",
)
m3.metric(
    "Prontos",
    carteira["prontos"],
    border=True,
    help="Prontos para revisão: sem bloqueios nem pendências documentais.",
)
m4.metric(
    "Vencidos",
    carteira["checklist_vencidos"],
    border=True,
    help="Itens de checklist abertos com prazo anterior a hoje, somados na carteira.",
)
m5.metric(
    "Desatualizados",
    carteira["registros_desatualizados"],
    border=True,
    help="Cálculos cujas fontes mudaram depois do registro.",
)
m6.metric(
    "Índice médio",
    f"{carteira['indice_medio']}%",
    border=True,
    help="Média do índice documental dos projetos listados.",
)

situacoes_presentes = [situacao for situacao in SITUACOES if carteira["por_situacao"].get(situacao)]
if situacoes_presentes:
    st.caption(
        "Por situação: "
        + " · ".join(
            f"**{situacao}** {carteira['por_situacao'][situacao]}"
            for situacao in situacoes_presentes
        )
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
            str(resumo[chave])
            for chave in ("codigo", "nome", "tag", "unidade", "area", "responsavel", "cliente")
        ).casefold()
        return busca.strip().casefold() in alvo
    return True


visiveis = [resumo for resumo in resumos if _corresponde(resumo)]

# ------------------------------------------------------ Atenção imediata
urgentes = [
    resumo
    for resumo in visiveis
    if resumo["bloqueios"]
    or resumo["checklist_vencidos"]
    or resumo["registros_desatualizados"]
    or resumo["registros_nao_atendem"]
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
            st.markdown(
                f"- **{resumo['codigo']} · {resumo['nome']}** ({resumo['status']}): "
                + "; ".join(motivos)
                + "."
            )
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
                resumo["dias_sem_atualizacao"]
                if resumo["dias_sem_atualizacao"] is not None
                else float("nan")
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
            "Índice": st.column_config.ProgressColumn(
                "Índice documental", min_value=0, max_value=100, format="%d%%"
            ),
            "Checklist": st.column_config.ProgressColumn(
                "Checklist", min_value=0, max_value=100, format="%d%%"
            ),
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
        escolhido = st.selectbox(
            "Projeto", ids, index=indice_padrao, format_func=lambda valor: opcoes[valor]
        )
        projeto_escolhido, resumo_escolhido = por_id[escolhido]
        for numero, passo in enumerate(
            proximos_passos(projeto_escolhido, resumo=resumo_escolhido), start=1
        ):
            st.markdown(f"**{numero}. {passo['titulo']}** — {passo['detalhe']}")
        if escolhido != ativo.get("id"):
            if st.button(
                "Abrir como projeto ativo", icon=":material/folder_open:", key="painel_abrir"
            ):
                definir_projeto_ativo(escolhido)
                st.rerun()
        else:
            st.page_link(
                "app_pages/gestao_projetos.py",
                label="Este é o projeto ativo — abrir",
                icon=":material/folder_managed:",
            )
    else:
        st.caption("Sem projetos visíveis.")

_secao_dados_e_backup(expandida=False)

st.info(
    "O painel lê o banco local a cada abertura. Índice documental e prontidão medem preenchimento e "
    "rastreabilidade — não certificam conformidade nem aprovação de engenharia.",
    icon=":material/info:",
)
