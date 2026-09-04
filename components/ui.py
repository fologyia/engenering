"""Elementos visuais compartilhados pelas páginas Streamlit."""

from collections.abc import Sequence

import streamlit as st


AcaoCabecalho = tuple[str, str, str]


def cabecalho_pagina(
    titulo: str,
    subtitulo: str,
    *,
    categoria: str,
    icone: str,
    cor: str = "blue",
    ajuda_modulo: str | None = None,
    acoes: Sequence[AcaoCabecalho] = (),
    mostrar_ferramentas: bool = True,
) -> None:
    """Exibe um cabeçalho consistente com ações e acesso ao guia."""
    with st.container(border=True):
        with st.container(horizontal=True):
            st.badge(categoria, icon=icone, color=cor)
            st.badge(
                "Unidades SI",
                icon=":material/straighten:",
                color="gray",
                help="Leia sempre a unidade indicada no rótulo de cada campo.",
            )
        st.title(titulo)
        st.caption(subtitulo)

        projeto = st.session_state.get("projeto_ativo")
        if projeto:
            st.caption(
                f":material/folder_open: Projeto ativo: **{projeto['nome']}** · "
                f"{projeto.get('codigo', 'sem código')} · Rev. {int(projeto.get('revisao', 0)):02d}"
            )

        if acoes or ajuda_modulo or mostrar_ferramentas:
            with st.container(horizontal=True, horizontal_alignment="right"):
                for pagina, rotulo, icone_acao in acoes:
                    st.page_link(
                        pagina,
                        label=rotulo,
                        icon=icone_acao,
                    )
                if mostrar_ferramentas:
                    st.page_link(
                        "app_pages/gestao_projetos.py",
                        label="Projeto ativo",
                        icon=":material/folder_managed:",
                    )
                    st.page_link(
                        "app_pages/assistente_projeto.py",
                        label="Projeto guiado",
                        icon=":material/route:",
                    )
                    st.page_link(
                        "app_pages/conversor_unidades.py",
                        label="Conversor",
                        icon=":material/swap_horiz:",
                    )
                if ajuda_modulo:
                    st.page_link(
                        "app_pages/guia_geral.py",
                        label="Guia e exemplo",
                        icon=":material/help:",
                        query_params={"modulo": ajuda_modulo},
                    )
