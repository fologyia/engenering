"""A prancheta como componente do Streamlit: o desenho em JS, as contas em Python."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "prancheta"
_NOME = "mecanica_toolkit_prancheta_secao"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "prancheta.html").read_text(encoding="utf-8"),
        css=(_PASTA / "prancheta.css").read_text(encoding="utf-8"),
        js=(_PASTA / "prancheta.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def prancheta(dados: Mapping[str, Any], *, key: str, ao_editar: Callable[[], None]) -> Any:
    """``dados``: partes, versao, ajustar e marcas. A edição chega em ``st.session_state[key].edicao``."""
    global _PRANCHETA
    try:
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
