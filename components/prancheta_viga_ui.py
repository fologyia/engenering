"""A prancheta da viga (Vigas e eixos) como componente do Streamlit: o desenho em JS, as contas em
Python. O visual é o da prancheta do equilíbrio (o mesmo CSS e o mesmo editor de números)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "prancheta_viga"
_EQUILIBRIO = Path(__file__).parent / "prancheta_equilibrio" / "equilibrio.css"
_COMUM = Path(__file__).parent / "editor_numerico"
_NOME = "mecanica_toolkit_prancheta_viga"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "viga.html").read_text(encoding="utf-8"),
        css=_COMUM.with_suffix(".css").read_text(encoding="utf-8")
        + _EQUILIBRIO.read_text(encoding="utf-8")
        + (_PASTA / "viga.css").read_text(encoding="utf-8"),
        js=_COMUM.with_suffix(".js").read_text(encoding="utf-8")
        + (_PASTA / "viga.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def prancheta_da_viga(dados: Mapping[str, Any], *, key: str, ao_editar: Callable[[], None]) -> Any:
    """``dados``: dados (o desenho), versao, ajustar e marcas. A edição chega em ``.edicao``."""
    global _PRANCHETA
    try:
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return _PRANCHETA(data=dict(dados), key=key, on_edicao_change=ao_editar)
