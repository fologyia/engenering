"""Ir a Desenhar seção a partir de outra página e voltar com a seção desenhada já escolhida.

Quem chama (o bloco Seção desenhada do Montador, a seção de Vigas e eixos) grava de onde veio e
qual campo espera a seção; Desenhar seção mostra o aviso e o botão "Salvar e voltar"; ao voltar,
a página de origem pega a seção com :func:`chegada` e a põe no campo.

O ``st.switch_page`` não roda dentro de callback: os botões marcam e a página troca na rodada.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

PAGINA_DESENHAR = "app_pages/desenhar_secao.py"
#: De onde veio: {"pagina", "rotulo", "destino", "campo"}.
VOLTA = "secao_volta"
#: A seção que volta: {"destino", "campo", "nome"}.
CHEGOU = "secao_chegou"
_IR = "secao_volta_ir"


def ir_desenhar(pagina: str, rotulo: str, destino: str, campo: str) -> None:
    """Grava de onde veio e abre Desenhar seção (chamar no corpo da página, não em callback)."""
    st.session_state[VOLTA] = {
        "pagina": pagina,
        "rotulo": rotulo,
        "destino": destino,
        "campo": campo,
    }
    st.session_state.pop(CHEGOU, None)
    st.switch_page(PAGINA_DESENHAR)


def de_onde_veio() -> Mapping[str, Any] | None:
    volta = st.session_state.get(VOLTA)
    return volta if isinstance(volta, Mapping) and volta.get("pagina") else None


def marcar_volta(nome: str | None) -> None:
    """Callback: a seção salva (ou ``None``, voltar sem ela) e a troca de página na rodada."""
    volta = de_onde_veio()
    if volta is None:
        return
    if nome:
        st.session_state[CHEGOU] = {
            "destino": volta["destino"],
            "campo": volta["campo"],
            "nome": nome,
        }
    st.session_state[_IR] = True


def trocar_se_marcado() -> None:
    """No começo de Desenhar seção: volta à página de origem quando um botão marcou."""
    if not st.session_state.pop(_IR, False):
        return
    volta = st.session_state.pop(VOLTA, None)
    if isinstance(volta, Mapping) and volta.get("pagina"):
        st.switch_page(str(volta["pagina"]))


def chegada(destino: str) -> Mapping[str, Any] | None:
    """A seção que voltou para ``destino`` (uma vez só: some depois de lida)."""
    chegou = st.session_state.get(CHEGOU)
    if not isinstance(chegou, Mapping) or chegou.get("destino") != destino:
        return None
    st.session_state.pop(CHEGOU, None)
    return chegou
