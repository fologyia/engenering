"""A prancheta de blocos como componente do Streamlit: os blocos em JS, as contas em Python."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "prancheta_blocos"
_COMUM = Path(__file__).parent / "editor_numerico"  # a caixinha do número, a mesma dos desenhos
_NOME = "mecanica_toolkit_prancheta_blocos"


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "blocos.html").read_text(encoding="utf-8"),
        css=_COMUM.with_suffix(".css").read_text(encoding="utf-8")
        + (_PASTA / "blocos.css").read_text(encoding="utf-8"),
        js=_COMUM.with_suffix(".js").read_text(encoding="utf-8")
        + (_PASTA / "blocos.js").read_text(encoding="utf-8"),
    )


_PRANCHETA = _registrar()


def prancheta_de_blocos(
    dados: Mapping[str, Any],
    *,
    key: str,
    ao_editar: Callable[[], None],
    ao_selecionar: Callable[[], None],
    ao_comandar: Callable[[], None],
) -> Any:
    """``dados``: catalogo, grafo, versao, ajustar, marcas, selecionar, historia, recebido e colagens.

    Os gestos vêm nos callbacks: ``edicao`` traz o desenho (e as colagens ainda sem confirmação),
    ``selecao`` o que está escolhido, e ``comando`` a fila numerada de pedidos (número digitado no
    cartão, Ctrl+Z, Ctrl+Y e agrupar). ``recebido`` e ``colagens`` dizem à prancheta o que já entrou.
    """
    global _PRANCHETA

    def chamar() -> Any:
        return _PRANCHETA(
            data=dict(dados),
            key=key,
            on_edicao_change=ao_editar,
            on_selecao_change=ao_selecionar,
            on_comando_change=ao_comandar,
        )

    try:
        return chamar()
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _PRANCHETA = _registrar()
        return chamar()
