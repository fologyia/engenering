import streamlit as st

from components.column_ui import mostrar_flambagem_colunas
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Flambagem de colunas", ":material/architecture:")
cabecalho_pagina(
    "Flambagem de colunas",
    "Barra inteira • NBR 8800:2008, Projeto NBR 8800:2024 e AISC 360-16 • N + Mx + My • critério Anglo",
    categoria="Análises",
    icone=":material/architecture:",
    cor="blue",
    ajuda_modulo="Flambagem de colunas",
    acoes=(("app_pages/assistente_cargas.py", "Assistente de cargas", ":material/manufacturing:"),),
    modulo_id="flambagem_colunas",
)
st.caption(
    "Uma única rodada verifica a coluna **inteira**: os dois eixos, todos os modos de flambagem "
    "(flexão em x e em y, torção e flexo-torção), a flambagem local, a flexão em x e em y e a "
    "interação **N + M_x + M_y numa equação só**, nas três normas e com o critério da Anglo. "
    "O que a norma não cobre vira uma linha **NÃO OK** na tabela — o programa não corrige a "
    "entrada em silêncio."
)
mostrar_flambagem_colunas()
