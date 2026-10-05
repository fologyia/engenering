"""Tabela de verificações de oito colunas, com a coluna Status colorida.

Usada pelo modo estrutural de Projeto de parafusos e por Flambagem de colunas: as duas
fecham o cálculo na mesma tabela (:mod:`core.verificacao`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pandas as pd
import streamlit as st

from core.verificacao import COLUNAS_TABELA, Verificacao, tabela_verificacoes

COR_STATUS = {
    "OK": "background-color: rgba(34, 197, 94, 0.28)",
    "NÃO OK": "background-color: rgba(239, 68, 68, 0.34)",
    "ALERTA": "background-color: rgba(245, 158, 11, 0.34)",
    "INFO": "background-color: rgba(59, 130, 246, 0.22)",
    "N/A": "background-color: rgba(148, 163, 184, 0.25)",
}
COR_BADGE = {"OK": "green", "NÃO OK": "red", "ALERTA": "orange", "INFO": "blue", "N/A": "gray"}

#: Dicas (“?”) do cabeçalho de cada coluna, em linguagem simples.
AJUDA_COLUNAS = {
    "Solicitante": "O que atua (a carga) ou, nas distâncias e limites, o valor exigido.",
    "Resistente": (
        "O que a peça suporta ou, nas distâncias e limites, o valor adotado. Nas linhas de "
        "status INFO é só a grandeza mostrada (ex.: N_e)."
    ),
    "Unidade": "Unidade do solicitante e do resistente.",
    "Aproveitamento": "Solicitante ÷ resistente, em %. Acima de 100% a verificação reprova.",
    "Status": "OK atende · NÃO OK reprova · ALERTA ressalva · INFO informação · N/A não se aplica.",
    "Fórmula": "Como o valor foi calculado, com os números deste caso.",
    "Referência": "Item da norma ou do critério de projeto em que a verificação se baseia.",
}


def _chaves_estilo(estilo: Any) -> Any:
    """``Styler.map`` (pandas ≥ 2.1) ou o antigo ``applymap`` (pandas 2.0)."""
    return getattr(estilo, "map", None) or estilo.applymap


def _celula(valor: Any, formato: str) -> str:
    """Número formatado, ou “—” quando não há valor (o Streamlit mostraria “None”)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    return formato.format(valor)


def estilizar(tabela: pd.DataFrame, formatos: dict[str, str]) -> Any:
    """Versão de exibição: números como texto formatado e a coluna Status colorida.

    Os valores exatos continuam no DataFrame de origem, no CSV e no registro técnico.
    """
    exibicao = tabela.copy()
    for coluna, formato in formatos.items():
        exibicao[coluna] = [_celula(valor, formato) for valor in tabela[coluna]]
    return _chaves_estilo(exibicao.style)(
        lambda valor: COR_STATUS.get(valor, ""), subset=["Status"]
    )


def mostrar_tabela_verificacoes(verificacoes: Sequence[Verificacao]) -> pd.DataFrame:
    """Tabela de oito colunas, com a coluna Status colorida. Devolve o DataFrame cru."""
    tabela = pd.DataFrame(tabela_verificacoes(verificacoes), columns=list(COLUNAS_TABELA))
    estilo = estilizar(
        tabela, {"Solicitante": "{:.2f}", "Resistente": "{:.2f}", "Aproveitamento": "{:.0f}"}
    )
    st.dataframe(
        estilo,
        hide_index=True,
        width="stretch",
        column_config={
            "Verificação": st.column_config.TextColumn(width="large"),
            "Solicitante": st.column_config.TextColumn(
                width="small", help=AJUDA_COLUNAS["Solicitante"]
            ),
            "Resistente": st.column_config.TextColumn(
                width="small", help=AJUDA_COLUNAS["Resistente"]
            ),
            "Unidade": st.column_config.TextColumn(width="small", help=AJUDA_COLUNAS["Unidade"]),
            "Aproveitamento": st.column_config.TextColumn(
                "Aproveitamento (%)", width="small", help=AJUDA_COLUNAS["Aproveitamento"]
            ),
            "Status": st.column_config.TextColumn(width="small", help=AJUDA_COLUNAS["Status"]),
            "Fórmula": st.column_config.TextColumn(width="large", help=AJUDA_COLUNAS["Fórmula"]),
            "Referência": st.column_config.TextColumn(
                width="medium", help=AJUDA_COLUNAS["Referência"]
            ),
        },
    )
    return tabela
