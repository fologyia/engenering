"""Tabela de verificações de oito colunas, com a coluna Status colorida.

Usada pelo modo estrutural de Projeto de parafusos e por Flambagem de colunas: as duas
fecham o cálculo na mesma tabela (:mod:`core.verificacao`). As Ligações estruturais mostram a
versão resumida (:func:`mostrar_verificacoes_resumidas`): cinco colunas por grupo e as fórmulas
num expansor.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd
import streamlit as st

from components.robustez import conferir_valores
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
    """Número formatado, “—” sem valor (o Streamlit mostraria “None”) e “∞” no infinito."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    if isinstance(valor, float) and math.isinf(valor):
        return "∞" if valor > 0 else "−∞"
    return formato.format(valor)


def conferir_linhas(verificacoes: Sequence[Verificacao]) -> bool:
    """Anota, sem mostrar, NaN em qualquer número e infinito no solicitante ou no resistente.

    O aproveitamento infinito é legítimo (resistência nula: a linha reprova) e não conta.
    """
    valores = {
        f"{indice + 1}. {v.nome}": {
            "solicitante": v.solicitante,
            "resistente": v.resistente,
            "aproveitamento": None
            if v.aproveitamento is not None and math.isinf(v.aproveitamento)
            else v.aproveitamento,
        }
        for indice, v in enumerate(verificacoes)
    }
    return conferir_valores("tabela de verificações", valores)


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
    conferir_linhas(verificacoes)
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


# ---------------------------------------------------------------------------------------------
# Versão resumida: cinco colunas por grupo e, num expansor, as fórmulas e os itens da norma
# ---------------------------------------------------------------------------------------------
COLUNAS_RESUMIDAS = (
    "Verificação",
    "Solicitante",
    "Resistente / limite",
    "Aproveitamento",
    "Status",
)
AJUDA_COLUNAS_RESUMIDAS = {
    "Solicitante": AJUDA_COLUNAS["Solicitante"],
    "Resistente / limite": AJUDA_COLUNAS["Resistente"],
    "Aproveitamento": AJUDA_COLUNAS["Aproveitamento"],
    "Status": AJUDA_COLUNAS["Status"],
}
_ESCAPAR_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]<>#$~|"})


def texto_markdown(texto: str) -> str:
    """O texto sem que o Markdown do Streamlit o interprete (f_y, A·B*, $ ...)."""
    return texto.translate(_ESCAPAR_MARKDOWN)


def _valor_com_unidade(valor: float | None, unidade: str) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    if isinstance(valor, float) and math.isinf(valor):
        return "∞"
    numero = f"{valor:.2f}".replace(".", ",")
    return numero if unidade in ("", "—") else f"{numero} {unidade}"


def linhas_resumidas(
    verificacoes: Sequence[Verificacao], nome: Callable[[Verificacao], str] = lambda v: v.nome
) -> pd.DataFrame:
    """As cinco colunas da tabela resumida, já em texto (unidade junto do número)."""
    return pd.DataFrame(
        [
            (
                nome(v),
                _valor_com_unidade(v.solicitante, v.unidade),
                _valor_com_unidade(v.resistente, v.unidade),
                "—"
                if v.aproveitamento is None or math.isinf(v.aproveitamento)
                else f"{100 * v.aproveitamento:.0f} %",
                v.status,
            )
            for v in verificacoes
        ],
        columns=list(COLUNAS_RESUMIDAS),
    )


def mostrar_verificacoes_resumidas(
    grupos: Sequence[tuple[str, Sequence[Verificacao]]],
    *,
    nome: Callable[[Verificacao], str] = lambda v: v.nome,
    titulo_detalhes: str = "Fórmulas e itens da norma de cada verificação",
) -> None:
    """Uma tabela de cinco colunas por grupo e, no fim, um expansor com os detalhes de cada linha.

    O nome inteiro, os valores com a unidade e o status cabem sem cortar; a fórmula com os
    números do caso e o item da norma ficam no expansor, em texto corrido.
    """
    todas = [v for _, linhas in grupos for v in linhas]
    conferir_linhas(todas)
    configuracao = {
        "Verificação": st.column_config.TextColumn(width="large"),
        **{
            coluna: st.column_config.TextColumn(width="small", help=ajuda)
            for coluna, ajuda in AJUDA_COLUNAS_RESUMIDAS.items()
        },
    }
    for grupo, linhas in grupos:
        st.markdown(f"**{texto_markdown(grupo)}**")
        tabela = linhas_resumidas(linhas, nome)
        st.dataframe(
            _chaves_estilo(tabela.style)(
                lambda valor: COR_STATUS.get(valor, ""), subset=["Status"]
            ),
            hide_index=True,
            width="stretch",
            column_config=configuracao,
        )
    with st.expander(titulo_detalhes, icon=":material/functions:"):
        for grupo, linhas in grupos:
            st.markdown(f"#### {texto_markdown(grupo)}")
            for v in linhas:
                valores = (
                    f"{_valor_com_unidade(v.solicitante, v.unidade)} / "
                    f"{_valor_com_unidade(v.resistente, v.unidade)}"
                )
                partes = [f"**{texto_markdown(nome(v))}** — {v.status} ({texto_markdown(valores)})"]
                if v.formula:
                    partes.append(f"Fórmula: {texto_markdown(v.formula)}")
                if v.referencia:
                    partes.append(f"Referência: {texto_markdown(v.referencia)}")
                st.markdown("  \n".join(partes))
