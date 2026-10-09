import streamlit as st

from components.ui import cabecalho_pagina, configurar_pagina
from components.vento_aberto_ui import mostrar_vento_em_estrutura_aberta

configurar_pagina("Vento em estruturas abertas", ":material/air:")
cabecalho_pagina(
    "Vento em estruturas abertas",
    "Plataformas, mezaninos, pipe racks e estruturas sem fechamento • NBR 6123:2023, capítulo 8 • "
    "forças por nível, nos nós e nas barras para o modelo",
    categoria="Análise",
    icone=":material/air:",
    cor="blue",
    ajuda_modulo="Vento em estruturas abertas",
    acoes=(
        ("app_pages/plano_cargas.py", "Plano de cargas", ":material/table_chart:"),
        ("app_pages/contraventamento_estrutura.py", "Contraventamento", ":material/grid_on:"),
    ),
    modulo_id="vento_estrutura_aberta",
)
st.caption(
    "Calcula a força do vento nos pórticos (reticulados com proteção η), nos guarda-corpos e nos "
    "equipamentos, por nível e direção, e entrega o que lançar no modelo: forças nos nós de cada "
    "pórtico ou carga por metro nas barras. Valores característicos; as combinações saem do plano "
    "de cargas."
)
mostrar_vento_em_estrutura_aberta()
