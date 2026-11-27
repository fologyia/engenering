"""Prévia do conteúdo do mesmo modelo usado pelos renderizadores do memorial."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from core.memorial_blocos import blocos_da_secao


def _celula(valor: Any) -> str:
    if isinstance(valor, (tuple, list)):
        return "\n".join(str(item) for item in valor if item is not None)
    return "" if valor is None else str(valor)


def mostrar_previa(secao: Mapping[str, Any]) -> None:
    """Exibe texto, tabelas e figuras na ordem definida pelo modelo de emissão."""
    st.markdown(f"#### {secao.get('titulo', '')}")
    for bloco in blocos_da_secao(secao):
        tipo = bloco.get("tipo")
        texto = str(bloco.get("texto") or "")
        if tipo == "subtitulo":
            st.markdown(f"**{texto}**")
        elif tipo == "destaque":
            st.write(f"{bloco.get('rotulo', '')} {texto}".strip())
        elif tipo in {"paragrafo", "nota", "formula"}:
            st.write(texto)
        elif tipo in {"bullets", "passos"}:
            for item in bloco.get("itens", []):
                st.write(f"• {_celula(item)}")
        elif tipo == "tabela":
            legenda = bloco.get("legenda")
            if legenda:
                st.caption(str(legenda))
            colunas = [_celula(item) for item in bloco.get("cabecalhos", [])]
            linhas = [[_celula(celula) for celula in linha] for linha in bloco.get("linhas", [])]
            if colunas and all(len(linha) == len(colunas) for linha in linhas):
                st.dataframe(
                    pd.DataFrame(linhas, columns=colunas), hide_index=True, width="stretch"
                )
            elif linhas:
                st.write(linhas)
        elif tipo == "imagem":
            if bloco.get("png"):
                st.image(bloco["png"], caption=bloco.get("legenda"))
            elif bloco.get("legenda"):
                st.caption(str(bloco["legenda"]))
