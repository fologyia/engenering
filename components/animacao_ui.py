"""O tocador de animações como componente do Streamlit: as contas em Python, o toque em JS.

A cena vem pronta de :class:`core.animacao.Cena`. Nada volta ao Python: tocar, pausar e arrastar a
barra do tempo não fazem a página rodar de novo.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "animacao"
_NOME = "mecanica_toolkit_animacao"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "animacao.html").read_text(encoding="utf-8"),
        css=(_PASTA / "animacao.css").read_text(encoding="utf-8"),
        js=(_PASTA / "animacao.js").read_text(encoding="utf-8"),
    )


_TOCADOR = _registrar()


def tocador(cena: Mapping[str, Any], *, key: str) -> Any:
    """Mostra a cena (:meth:`core.animacao.Cena.como_dados`). Trocar o ``id`` da cena volta ao
    começo; com o mesmo ``id`` o instante mostrado fica onde estava."""
    global _TOCADOR

    def chamar() -> Any:
        return _TOCADOR(data=dict(cena), key=key)

    try:
        return chamar()
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _TOCADOR = _registrar()
        return chamar()
