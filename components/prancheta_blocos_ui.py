"""A prancheta de blocos como componente do Streamlit: os blocos em JS, as contas em Python."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "prancheta_blocos"
_NOME = "mecanica_toolkit_prancheta_blocos"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "blocos.html").read_text(encoding="utf-8"),
        css=(_PASTA / "blocos.css").read_text(encoding="utf-8"),
        js=(_PASTA / "blocos.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def prancheta_de_blocos(
    dados: Mapping[str, Any], *, key: str, ao_editar: Callable[[], None]
) -> Any:
    """``dados``: catalogo, grafo, versao, ajustar e marcas. A edição chega em ``.edicao``."""
    global _PRANCHETA
    try:
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
