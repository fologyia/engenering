"""O menu da barra lateral: busca por tudo, fixados, recentes e grupos que abrem e fecham.

Os dados vêm de :mod:`core.navegacao`. O ``st.navigation`` fica escondido e continua cuidando das
rotas: o menu nativo é uma lista fixa, sem busca e sem grupos recolhíveis na lateral.
"""

from __future__ import annotations

import streamlit as st

from core import elementos_catalogo as cat
from core import navegacao as nv
from core import preferencias_menu as pm

_BUSCA = "menu_busca"
_DESTINO = "menu_destino"
_RECENTES = 4

_ESTILO = """
<style>
/* Valor longo quebra a linha em vez de sair cortado com reticências. */
[data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] p {
  white-space: normal;
  overflow: visible;
  overflow-wrap: anywhere;
  line-height: 1.2;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
  border: 0;
  background: transparent;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  padding: 0.3rem 0.45rem;
  border-radius: 8px;
  font-weight: 600;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
  background: rgba(98, 199, 238, 0.12);
}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {
  padding: 0 0 0.3rem 0.5rem;
  gap: 0;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.2rem;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {
  padding: 0.12rem 0.45rem;
  border-radius: 8px;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  margin-top: 0.45rem;
  letter-spacing: 0.04em;
}
</style>
"""


def _opcoes_de_busca() -> dict[str, tuple[str, str | None]]:
    """Texto da opção → (página, caso do Assistente). O texto é o que a busca filtra."""
    opcoes: dict[str, tuple[str, str | None]] = {}
    for grupo in nv.MENU:
        for item in grupo.itens:
            opcoes[f"{item.titulo} · {item.tarefa}"] = (item.pagina, None)
    for caso in cat.CASOS.values():
        opcoes[f"{caso.titulo} · Assistente de cargas, {caso.grupo}"] = (
            "app_pages/assistente_cargas.py",
            caso.id,
        )
    return opcoes


def _ao_buscar() -> None:
    escolha = st.session_state.get(_BUSCA)
    if escolha:
        st.session_state[_DESTINO] = _opcoes_de_busca().get(escolha)
        st.session_state[_BUSCA] = None


def _alternar_fixado(pagina: str) -> None:
    pm.alternar_fixado(pagina)


def _anotar_recente(pagina: str) -> None:
    if pagina == nv.VISAO_GERAL.pagina:
        return  # ela já tem lugar fixo no alto do menu
    if pagina and pagina != st.session_state.get("menu_ultima"):
        st.session_state["menu_ultima"] = pagina
        pm.anotar_recente(pagina)


def _ligacao(item: nv.ItemMenu) -> None:
    st.page_link(item.pagina, label=item.titulo, icon=item.icone, help=item.tarefa, width="stretch")


def _itens(caminhos: list[str]) -> list[nv.ItemMenu]:
    return [item for caminho in caminhos if (item := nv.item_da_pagina(caminho)) is not None]


def menu_lateral(paginas: dict[str, st.Page], atual: str) -> None:
    """Desenha o menu. ``atual`` é o caminho da página aberta."""
    destino = st.session_state.pop(_DESTINO, None)
    if destino:
        pagina, caso_id = destino
        if caso_id:
            st.session_state["assistente_geometria"] = caso_id
        st.switch_page(paginas[pagina])

    _anotar_recente(atual)
    grupo_atual = nv.grupo_da_pagina(atual) if atual else None
    fixados = pm.fixados()
    with st.sidebar:
        st.html(_ESTILO)
        st.selectbox(
            "Buscar",
            list(_opcoes_de_busca()),
            index=None,
            placeholder="Buscar: vento, parafuso, flambagem…",
            key=_BUSCA,
            on_change=_ao_buscar,
            label_visibility="collapsed",
            help="Procura em todas as páginas e em todos os casos do Assistente de cargas.",
        )
        _ligacao(nv.VISAO_GERAL)

        lista_fixados = _itens(fixados)
        if lista_fixados:
            st.caption("FIXADOS")
            for item in lista_fixados:
                _ligacao(item)
        recentes = [
            item
            for item in _itens(pm.recentes())
            if item.pagina not in {atual, nv.VISAO_GERAL.pagina, *fixados}
        ][:_RECENTES]
        if recentes:
            st.caption("RECENTES")
            for item in recentes:
                _ligacao(item)

        st.caption("TODAS AS PÁGINAS")
        for grupo in nv.MENU:
            # A chave leva a página aberta: cada troca de página volta a abrir só o grupo dela.
            with st.expander(
                grupo.nome,
                expanded=grupo is grupo_atual,
                icon=grupo.icone,
                key=f"menu_{grupo.nome}_{atual}",
            ):
                for item in grupo.itens:
                    _ligacao(item)

        if atual and nv.item_da_pagina(atual) is not None and atual != nv.VISAO_GERAL.pagina:
            fixada = atual in fixados
            st.button(
                "Tirar esta página dos fixados" if fixada else "Fixar esta página no menu",
                icon=":material/keep_off:" if fixada else ":material/keep:",
                type="tertiary",
                key="menu_fixar",
                on_click=_alternar_fixado,
                args=(atual,),
                help="Páginas fixadas ficam no alto do menu, para abrir com um clique.",
            )
