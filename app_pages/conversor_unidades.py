import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.ui import cabecalho_pagina
from core import unit_converter as unidades

st.set_page_config(
    page_title="Conversor de unidades",
    page_icon=":material/swap_horiz:",
    layout="wide",
)

cabecalho_pagina(
    "Conversor global de unidades",
    "Converta entradas e resultados sem alterar o núcleo de cálculo em unidades SI.",
    categoria="Ferramentas",
    icone=":material/swap_horiz:",
    cor="blue",
    ajuda_modulo="Conversor de unidades",
    acoes=(
        (
            "app_pages/assistente_projeto.py",
            "Assistente de projeto",
            ":material/route:",
        ),
    ),
    mostrar_ferramentas=False,
)

st.info(
    "Escolha primeiro a grandeza. Origem e destino sempre pertencem à mesma "
    "categoria, evitando misturar massa com força ou pressão com momento.",
    icon=":material/info:",
)


def formatar_numero(valor: float, algarismos: int = 6) -> str:
    """Formata com precisão de engenharia sem poluir a leitura."""
    if valor == 0:
        return "0"
    absoluto = abs(valor)
    if absoluto >= 1e7 or absoluto < 1e-4:
        return f"{valor:.{algarismos - 1}e}".replace(".", ",")
    casas = max(0, algarismos - math.floor(math.log10(absoluto)) - 1)
    return f"{valor:,.{casas}f}".rstrip("0").rstrip(".").replace(
        ",", "X"
    ).replace(".", ",").replace("X", ".")


def inverter_unidades(chave_origem: str, chave_destino: str) -> None:
    origem_atual = st.session_state[chave_origem]
    st.session_state[chave_origem] = st.session_state[chave_destino]
    st.session_state[chave_destino] = origem_atual


with st.container(border=True):
    st.subheader("Conversão")
    categoria = st.selectbox(
        "Grandeza",
        unidades.listar_categorias(),
        key="conversor_categoria",
        persist_state="session",
    )
    opcoes = unidades.listar_unidades(categoria)
    origem_padrao, destino_padrao = unidades.PARES_PADRAO[categoria]
    chave_origem = f"conversor_origem_{categoria}"
    chave_destino = f"conversor_destino_{categoria}"

    entrada, troca, saida = st.columns([1, 0.38, 1], vertical_alignment="bottom")
    with entrada:
        valor = st.number_input(
            "Valor",
            value=1.0,
            step=1.0,
            format="%.8g",
            key=f"conversor_valor_{categoria}",
            persist_state="session",
        )
        origem = st.selectbox(
            "Unidade de origem",
            opcoes,
            index=opcoes.index(origem_padrao),
            key=chave_origem,
            persist_state="session",
        )
    with troca:
        st.button(
            "Trocar",
            icon=":material/swap_horiz:",
            help="Troca a unidade de origem pela unidade de destino.",
            on_click=inverter_unidades,
            args=(chave_origem, chave_destino),
            width="stretch",
        )
    with saida:
        destino = st.selectbox(
            "Unidade de destino",
            opcoes,
            index=opcoes.index(destino_padrao),
            key=chave_destino,
            persist_state="session",
        )
        resultado = unidades.converter(valor, categoria, origem, destino)
        st.metric(
            "Resultado",
            f"{formatar_numero(resultado)} {destino}",
            border=True,
        )

    st.code(
        f"{formatar_numero(valor)} {origem} = "
        f"{formatar_numero(resultado)} {destino}"
    )
    st.caption(
        "Exibição com até seis algarismos significativos; o cálculo interno "
        "mantém a precisão completa."
    )

equivalencias, referencia = st.columns([1.15, 0.85])
with equivalencias:
    with st.container(border=True):
        st.subheader("Equivalências na mesma grandeza")
        linhas = [
            {
                "Unidade": simbolo,
                "Valor convertido": formatar_numero(convertido),
            }
            for simbolo, convertido in unidades.conversoes_da_categoria(
                valor, categoria, origem
            )
        ]
        st.dataframe(pd.DataFrame(linhas), hide_index=True)

with referencia:
    with st.container(border=True, height="stretch"):
        st.subheader("Unidades preferidas no app")
        st.markdown(
            """
            - **Tensões e resistências:** MPa
            - **Dimensões:** mm
            - **Forças:** N ou kN, conforme o campo
            - **Momentos e torques:** N·m ou kN·m
            - **Módulo elástico:** GPa
            - **Temperatura:** °C
            - **Ângulos:** graus
            """
        )
        st.caption(
            "Leia sempre o rótulo do campo. O conversor não altera "
            "automaticamente valores já digitados em outra página."
        )

with st.expander(
    "Cuidados que evitam erros de unidade",
    icon=":material/rule:",
):
    st.markdown(
        """
        - Não trate **kg** como força; use kgf somente quando a fonte realmente
          informar quilograma-força.
        - Em tensão, **1 N/mm² = 1 MPa**.
        - Em carga distribuída, **1 N/mm = 1 kN/m**.
        - Converta o valor completo antes de copiar para outro módulo.
        - Preserve o sinal de forças, tensões e momentos depois da conversão.
        """
    )

