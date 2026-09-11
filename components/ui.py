"""Elementos visuais compartilhados pelas páginas Streamlit."""

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import streamlit as st

AcaoCabecalho = tuple[str, str, str]

_ICONE_SITUACAO = {
    "concluida": ":material/check_circle:",
    "atencao": ":material/warning:",
    "pendente": ":material/radio_button_unchecked:",
}


def _mostrar_sequencia_sugerida(modulo_id: str) -> None:
    """Mostra, quando aplicável, onde este módulo se encaixa em um fluxo.

    Não bloqueia nada: um módulo fora de qualquer fluxo, ou sem projeto
    ativo, simplesmente não mostra a barra — o "caso específico" continua
    funcionando exatamente como um módulo isolado.
    """
    from core.module_sequencing import montar_sequencia, proximo_passo
    from core.project_store import obter_projeto_ativo

    projeto = None
    if st.session_state.get("projeto_ativo"):
        try:
            projeto = obter_projeto_ativo()
        except Exception:
            projeto = None

    etapas = montar_sequencia(projeto, modulo_id)
    if not etapas:
        return

    with st.container(border=True):
        st.caption("Sequência sugerida para este tipo de verificação")
        colunas = st.container(horizontal=True)
        for etapa in etapas:
            with colunas:
                if etapa.situacao == "atual":
                    st.markdown(f"**:material/radio_button_checked: {etapa.titulo}**")
                else:
                    st.page_link(
                        etapa.pagina,
                        label=etapa.titulo,
                        icon=_ICONE_SITUACAO[etapa.situacao],
                        help=etapa.detalhe or None,
                    )
        proxima = proximo_passo(etapas)
        if proxima is not None:
            st.caption(f"Próximo passo sugerido: **{proxima.titulo}**.")
        elif projeto is not None and all(
            etapa.situacao == "concluida" for etapa in etapas if etapa.situacao != "atual"
        ):
            st.caption("Sequência concluída com os dados atuais do projeto.")


def fronteira_modelo(
    itens: Sequence[str],
    *,
    titulo: str = "Fora do escopo deste cálculo",
) -> None:
    """Bloco padronizado e sempre visível do que o modelo NÃO verifica.

    Não é um aviso de rodapé nem fica escondido num expander: aparece junto
    do resultado, antes do registro, para que a decisão de aceitar (ou não)
    o número leve em conta o que ele deliberadamente não cobre. O programa
    assiste a leitura do resultado — quem decide sobre os itens listados
    continua sendo o engenheiro responsável.
    """
    if not itens:
        return
    corpo = "\n".join(f"- {item}" for item in itens)
    st.warning(f"**{titulo}:**\n\n{corpo}", icon=":material/rule:")


def comparador_cenarios(
    *,
    escopo: str,
    resumo_entradas: Mapping[str, Any],
    metricas: Mapping[str, Any],
    max_cenarios: int = 4,
) -> None:
    """Fixa até ``max_cenarios`` resultados lado a lado, na própria sessão.

    Para o uso "modo singular" (dimensionar, não só verificar): comparar
    d = 50 mm com d = 60 mm hoje exige recalcular e anotar à parte. Aqui o
    programa só guarda o que você já calculou — a escolha de qual cenário é
    o melhor continua sendo do engenheiro. Nada disto é salvo no projeto;
    é só uma mesa de trabalho temporária desta sessão.
    """
    chave_estado = f"_cenarios_fixados_{escopo}"
    cenarios: list[dict[str, Any]] = st.session_state.setdefault(chave_estado, [])

    coluna_fixar, coluna_limpar = st.columns([3, 1])
    with coluna_fixar:
        fixar = st.button(
            "Fixar este cenário para comparar",
            key=f"{escopo}_fixar_cenario",
            icon=":material/push_pin:",
            width="stretch",
        )
    with coluna_limpar:
        limpar = cenarios and st.button(
            "Limpar cenários",
            key=f"{escopo}_limpar_cenarios",
            icon=":material/delete_sweep:",
            width="stretch",
        )
    if fixar:
        cenarios.append({**resumo_entradas, **metricas})
        if len(cenarios) > max_cenarios:
            cenarios.pop(0)
        st.rerun()
    if limpar:
        st.session_state[chave_estado] = []
        st.rerun()

    if cenarios:
        tabela = pd.DataFrame(
            [{"Cenário": f"#{indice + 1}", **linha} for indice, linha in enumerate(cenarios)]
        )
        st.caption(
            f"{len(cenarios)} de {max_cenarios} cenário(s) fixado(s) nesta sessão "
            "— não são salvos no projeto; registre o escolhido normalmente."
        )
        st.dataframe(tabela, hide_index=True, width="stretch")


def configurar_pagina(titulo: str, icone: str) -> None:
    """Aplica a configuração padrão (layout largo) usada por todas as páginas."""
    st.set_page_config(page_title=titulo, page_icon=icone, layout="wide")


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
    modulo_id: str | None = None,
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

    if modulo_id:
        _mostrar_sequencia_sugerida(modulo_id)
