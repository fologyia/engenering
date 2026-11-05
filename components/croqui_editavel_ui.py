"""O desenho do caso com as medidas vivas, como componente do Streamlit."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "croqui_editavel"
_COMUM = Path(__file__).parent / "editor_numerico"
_NOME = "mecanica_toolkit_croqui_editavel"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "croqui.html").read_text(encoding="utf-8"),
        css=_COMUM.with_suffix(".css").read_text(encoding="utf-8")
        + (_PASTA / "croqui.css").read_text(encoding="utf-8"),
        js=_COMUM.with_suffix(".js").read_text(encoding="utf-8")
        + (_PASTA / "croqui.js").read_text(encoding="utf-8"),
    )


_COMPONENTE = _registrar()


def croqui_editavel(dados: Mapping[str, Any], *, key: str, ao_editar: Callable[[], None]) -> Any:
    """``dados``: svg e cotas. A edição chega em ``st.session_state[key].edicao``."""
    global _COMPONENTE
    try:
        return _COMPONENTE(data=dict(dados), key=key, on_edicao_change=ao_editar)
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _COMPONENTE = _registrar()
        return _COMPONENTE(data=dict(dados), key=key, on_edicao_change=ao_editar)
