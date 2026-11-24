"""Esforços do modelo › 3: onde e como as cargas entraram no estudo — as setas do vento, a altura e
o centro de cada carga (equilíbrio pelos pés) e o que o gerenciador de casos aplicou.

Fica num arquivo à parte da página para ela só chamar :func:`mostrar`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.figuras import mostrar_figura
from core import apoios_do_modelo as am
from core import cargas_aplicadas as ca
from core import centro_das_cargas as cc
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import setas_do_vento as sv

AJUDA = {
    "sec": (
        "Quanto o modelo recebeu é a soma das reações; aqui, ONDE e COMO cada carga entrou. As "
        "setas mostram, para cada vento, a força do plano (azul) e a que o estudo aplicou "
        "(laranja). Com a reação e a posição de cada pé (o -apoios.csv da macro dos casos de "
        "carga), o equilíbrio dá onde a resultante atua: a altura do vento e o centro dos pesos "
        "na planta — comparados com o plano. A divisão entre os pés não entra: com quatro ou mais "
        "pés ela depende da rigidez. Com o CSV do gerenciador de casos de carga enviado no passo 1, "
        "a tabela diz o valor que entrou em cada caso: uma vez, “Por item” em várias barras, ou "
        "com outro valor que o do plano."
    ),
    "tabela": (
        "Cada caso do gerenciador: o valor digitado de cada carga, a reação que o estudo deu e a "
        "soma do plano. “Entrou n vezes” = a força “Por item” foi aplicada inteira em n barras "
        "(ou faces). O sentido das forças vem das reações: o arquivo do gerenciador só diz a "
        "componente, não a direção no espaço."
    ),
}


def mostrar(
    projeto: Mapping[str, Any] | None,
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    geometria: ld.GeometriaDoModelo,
    apoios: am.ApoiosDoModelo,
    mostrar_item: Mapping[str, Any],
    icones: Mapping[str, str],
) -> None:
    """Desenha a parte; ``mostrar_item`` e ``icones`` são os da página (nível → st.warning…)."""
    ventos = em.ventos_comparados(dados, plano)
    centros = cc.comparar(dados, plano, apoios, geometria)
    gerenciador = ca.do_projeto(projeto)
    if not ventos and not centros and gerenciador is None:
        st.caption(
            ":material/my_location: Para ver onde cada carga entrou no estudo, envie no passo 1 "
            "os -apoios.csv da macro dos casos de carga (a reação e a posição de cada pé) e o CSV "
            "do gerenciador de casos de carga (Salvar os dados em um arquivo .csv externo)."
        )
        return
    st.subheader("Onde e como as cargas entraram", help=AJUDA["sec"])
    if ventos and geometria.corpos:
        desenho = sv.svg(dados, plano, geometria, ventos)
        if desenho:
            mostrar_figura(
                desenho,
                "Vento: a força do plano (azul) e a que o estudo aplicou (laranja), na vista "
                "Superior. Setas opostas = sentido trocado; seta menor = menos carga.",
            )
    for centro in centros:
        mostrar_item.get(centro.nivel, st.success)(centro.texto, icon=icones[centro.nivel])
    if centros:
        st.caption(
            "Pelo equilíbrio das reações nos pés (força e momento): onde a resultante das cargas "
            "atua. A divisão entre os pés depende da rigidez e não é comparada."
        )
    if gerenciador is not None:
        nome, arquivo = gerenciador
        linhas = ca.conferir(arquivo, dados, plano)
        if linhas:
            st.markdown(f"**O que o gerenciador aplicou** — {nome}", help=AJUDA["tabela"])
            st.dataframe(
                pd.DataFrame(
                    [linha.como_linha() for linha in linhas], columns=list(ca.COLUNAS_DA_TABELA)
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Reação do estudo (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "Plano (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "O que explica": st.column_config.TextColumn(width="large"),
                },
            )
    elif ventos or centros:
        st.caption(
            ":material/table: Envie no passo 1 o CSV do gerenciador de casos de carga (Salvar os "
            "dados em um arquivo .csv externo): o programa diz o valor que entrou em cada caso — "
            "uma vez, “Por item” em várias barras ou outro valor que o do plano."
        )
