"""O esboço paramétrico como componente do Streamlit: o desenho e o solver em JS, as contas em Python.

O navegador é o dono do esboço enquanto se desenha: o solver roda lá (``components/esboco``), e o
Python só recebe o esboço pronto ao fim de cada gesto, em ``st.session_state[key].edicao``. O Python
só manda um esboço de volta quando troca o desenho por fora (abrir um salvo, limpar, converter): para
isso ``versao`` sobe, e o navegador só aceita versão mais nova que a dele.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

_PASTA = Path(__file__).parent / "esboco"
_COMUM = Path(__file__).parent / "editor_numerico"
_NOME = "mecanica_toolkit_esboco_secao"
#: A ordem importa: o CCv2 não importa módulos, os arquivos são colados um depois do outro.
ARQUIVOS_JS = ("conta.js", "solver.js", "contornos.js", "esboco.js")


def _registrar() -> Any:
    return st.components.v2.component(
        _NOME,
        html=(_PASTA / "esboco.html").read_text(encoding="utf-8"),
        css=_COMUM.with_suffix(".css").read_text(encoding="utf-8")
        + (_PASTA / "esboco.css").read_text(encoding="utf-8"),
        js=_COMUM.with_suffix(".js").read_text(encoding="utf-8")
        + "".join((_PASTA / nome).read_text(encoding="utf-8") for nome in ARQUIVOS_JS),
    )


_ESBOCO = _registrar()


def prancheta_do_esboco(
    dados: Mapping[str, Any], *, key: str, ao_editar: Callable[[], None]
) -> Any:
    """``dados``: esboco, versao, ajustar, problemas e marcas."""
    global _ESBOCO
    try:
        return _ESBOCO(data=dict(dados), key=key, on_edicao_change=ao_editar)
    except ValueError as erro:
        # O registro é do servidor, e este módulo pode sobreviver a um servidor novo.
        if "is not registered" not in str(erro):
            raise
        _ESBOCO = _registrar()
        return _ESBOCO(data=dict(dados), key=key, on_edicao_change=ao_editar)
