"""A prancheta da rede de tubos como componente do Streamlit: o desenho em JS, as contas em Python."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "prancheta_rede"
_NOME = "mecanica_toolkit_prancheta_rede"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "rede.html").read_text(encoding="utf-8"),
        css=(_PASTA / "rede.css").read_text(encoding="utf-8"),
        js=(_PASTA / "rede.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def prancheta_da_rede(
    dados: Mapping[str, Any],
    *,
    key: str,
    ao_desenhar: Callable[[], None],
    ao_selecionar: Callable[[], None],
) -> Any:
    """``dados``: dados (nós e tubos), versao, ajustar e marcas (o resultado no desenho).

    O desenho chega em ``.edicao`` (com a versão) e o item escolhido em ``.selecao``.
    """
    global _PRANCHETA

    def chamar() -> Any:
        return _PRANCHETA(
            data=dict(dados),
            key=key,
            on_edicao_change=ao_desenhar,
            on_selecao_change=ao_selecionar,
        )

    try:
        return chamar()
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return chamar()
