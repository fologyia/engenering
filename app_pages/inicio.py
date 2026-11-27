"""Visão geral dos indicadores do projeto ativo e acesso aos módulos."""

import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import mapa_do_projeto
from components.painel_projeto_ui import renderizar_painel_projeto
from core import armazenamento
from core import navegacao as nv
from core.project_portfolio import proximos_passos, resumir_projeto
from core.project_store import obter_projeto_ativo
from core.project_validation import validar_projeto

st.title("Visão geral")
projeto = obter_projeto_ativo()
if projeto:
    validacao = validar_projeto(projeto)
    resumo = resumir_projeto(projeto, validacao=validacao)
    st.subheader(projeto["nome"])
    st.caption(
        " · ".join(
            parte
            for parte in (
                resumo["codigo"],
                f"Revisão {resumo['revisao']:02d}",
                resumo["status"],
                resumo["cliente"],
                resumo["area"],
            )
            if parte
        )
    )
    with st.container(horizontal=True):
        st.page_link(
            "app_pages/gestao_projetos.py",
            label="Gerenciar projeto",
            icon=":material/folder_managed:",
        )
        st.page_link(
            "app_pages/roteiro_projeto.py",
            label="Roteiro do projeto",
            icon=":material/format_list_numbered:",
        )
        st.page_link(
            "app_pages/central_relatorios.py",
            label="Memorial de cálculo",
            icon=":material/description:",
        )
        st.page_link(
            "app_pages/painel_industrial.py",
            label="Carteira de projetos",
            icon=":material/dashboard:",
        )

    passo = proximos_passos(projeto, resumo=resumo, validacao=validacao, limite=1)[0]
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        with st.container():
            st.markdown(f"**{passo['titulo']}**")
            st.caption(passo["detalhe"])
        st.page_link(passo["pagina"], label="Abrir", icon=":material/arrow_forward:")

    renderizar_painel_projeto(projeto, validacao, resumo, origem="inicio")
    st.caption(armazenamento.frase_de_persistencia())
else:
    with st.container(border=True):
        st.subheader("Nenhum projeto ativo")
        st.caption("Abra ou crie um projeto para acompanhar cálculos, pendências e prazos.")
        with st.container(horizontal=True):
            st.page_link(
                "app_pages/gestao_projetos.py",
                label="Abrir ou criar projeto",
                icon=":material/folder_managed:",
            )
            st.page_link(
                "app_pages/painel_industrial.py",
                label="Carteira de projetos",
                icon=":material/dashboard:",
            )

with st.container(border=True):
    st.subheader("Atalhos para os módulos")
    itens = [item for grupo in nv.MENU for item in grupo.itens]
    tarefa = st.selectbox(
        "Escolha a tarefa",
        [item.tarefa for item in itens],
        index=None,
        placeholder="Por exemplo: calcular o vento, verificar uma ligação…",
        key="inicio_tarefa",
        help="Cada tarefa leva à página que a resolve.",
    )
    if tarefa:
        escolhido = next(item for item in itens if item.tarefa == tarefa)
        st.page_link(
            escolhido.pagina,
            label=f"Abrir {escolhido.titulo}",
            icon=escolhido.icone,
            width="stretch",
        )

catalogo = st.expander("Explorar todos os módulos", on_change="rerun", key="inicio_catalogo")
if catalogo.open:
    with catalogo:
        for inicio in range(0, len(nv.MENU), 3):
            colunas = st.columns(3)
            for coluna, grupo in zip(colunas, nv.MENU[inicio : inicio + 3], strict=False):
                with coluna, st.container(border=True, height="stretch"):
                    st.markdown(f"#### {grupo.icone} {grupo.nome}")
                    st.caption(grupo.descricao)
                    for secao, itens in grupo.secoes():
                        if secao:
                            st.markdown(f"**{secao}**")
                        for item in itens:
                            st.page_link(
                                item.pagina, label=item.titulo, icon=item.icone, help=item.tarefa
                            )

mapa_do_projeto(AJUDA_BASE["sec_mapa"])

st.caption(
    ":material/engineering: Ferramenta de cálculo e conferência. O projeto e a responsabilidade "
    "técnica continuam do engenheiro habilitado; casos fora do escopo de cada página estão "
    "indicados nela e no memorial."
)
