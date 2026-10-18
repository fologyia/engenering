"""Visão geral: o projeto ativo, o próximo passo e tudo o que o programa faz, na ordem do trabalho."""

import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import mapa_do_projeto
from core import armazenamento
from core import navegacao as nv
from core import roteiro as rt
from core.project_store import obter_projeto_ativo

with st.container(border=True):
    with st.container(horizontal=True):
        st.badge("Estruturas de aço industriais", icon=":material/domain:", color="primary")
        st.badge(
            "NBR 8800 · NBR 6120 · NBR 6123 · Anglo", icon=":material/verified:", color="green"
        )
    st.title("Mecânica Toolkit")
    st.markdown(
        "Do esqueleto no SolidWorks ao **memorial de cálculo**: cargas, vento, verificação das "
        "barras, ligações, bases e escadas, com a norma e o item em cada conta."
    )
    with st.container(horizontal=True):
        st.page_link(
            "app_pages/roteiro_projeto.py",
            label="Roteiro do projeto",
            icon=":material/format_list_numbered:",
        )
        st.page_link(
            "app_pages/gestao_projetos.py", label="Projetos", icon=":material/folder_managed:"
        )
        st.page_link(
            "app_pages/central_relatorios.py",
            label="Gerar memorial",
            icon=":material/description:",
        )
        st.page_link(
            "app_pages/guia_geral.py",
            label="Guia",
            icon=":material/help:",
            query_params={"modulo": "Comece aqui"},
        )

# ------------------------------------------------------------------ projeto ativo e próximo passo
projeto = obter_projeto_ativo()
with st.container(border=True):
    if projeto:
        st.badge("Projeto ativo", icon=":material/folder_open:", color="green")
        st.subheader(projeto["nome"])
        st.caption(
            f"Código {projeto.get('codigo') or '—'} · Revisão "
            f"{int(projeto.get('revisao', 0)):02d} · {projeto.get('status', 'Em elaboração')}. "
            f"{armazenamento.frase_de_persistencia()}"
        )
        proximo = rt.proximo_passo(rt.situacoes(projeto))
        if proximo is not None:
            passo = rt.PASSOS[proximo - 1]
            st.info(
                f"**Próximo passo — {passo.numero}. {passo.titulo}:** {passo.onde}.",
                icon=":material/arrow_forward:",
            )
            if passo.pagina:
                st.page_link(
                    passo.pagina, label=f"Abrir {passo.onde}", icon=":material/open_in_new:"
                )
        else:
            st.success(
                "Todos os passos com rastro no projeto estão feitos: gere o memorial.",
                icon=":material/check_circle:",
            )
    else:
        st.badge("Sem projeto ativo", icon=":material/folder_off:", color="gray")
        st.markdown(
            "Abra ou crie um projeto para o programa guardar os cálculos e montar o memorial."
        )
        st.page_link(
            "app_pages/gestao_projetos.py",
            label="Abrir ou criar um projeto",
            icon=":material/folder_managed:",
        )

mapa_do_projeto(AJUDA_BASE["sec_mapa"])

# ------------------------------------------------------------------ rota rápida
with st.container(border=True):
    st.subheader("O que você precisa fazer?")
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

# ------------------------------------------------------------------ tudo o que o programa faz
st.subheader("Tudo o que o programa faz")
st.caption("Os grupos estão na mesma ordem da barra lateral e do trabalho.")
for inicio in range(0, len(nv.MENU), 3):
    colunas = st.columns(3)
    for coluna, grupo in zip(colunas, nv.MENU[inicio : inicio + 3], strict=False):
        with coluna, st.container(border=True, height="stretch"):
            st.markdown(f"#### {grupo.icone} {grupo.nome}")
            st.caption(grupo.descricao)
            for item in grupo.itens:
                st.page_link(item.pagina, label=item.titulo, icon=item.icone, help=item.tarefa)

st.caption(
    ":material/engineering: Ferramenta de cálculo e conferência. O projeto e a responsabilidade "
    "técnica continuam do engenheiro habilitado; casos fora do escopo de cada página estão "
    "indicados nela e no memorial."
)
