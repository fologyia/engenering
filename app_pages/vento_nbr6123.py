import streamlit as st

from components.ui import cabecalho_pagina, configurar_pagina
from components.wind_ui import mostrar_vento_nas_estruturas

configurar_pagina("Vento nas estruturas", ":material/air:")
cabecalho_pagina(
    "Vento nas estruturas",
    "NBR 6123:2023 • pressões em paredes e telhado • vedações e fixações • forças globais • pórtico",
    categoria="Análises",
    icone=":material/air:",
    cor="blue",
    ajuda_modulo="Vento nas estruturas",
    acoes=(("app_pages/casos_carga.py", "Casos de carga", ":material/layers:"),),
    modulo_id="vento_nbr6123",
)
st.caption(
    "Calcula o vento numa edificação de planta retangular (galpão ou edifício): a velocidade e a "
    "pressão dinâmica do local, o coeficiente de forma de **cada zona** das paredes e do telhado, "
    "a pressão interna, as pressões de projeto das **telhas e fixações**, a força de arrasto, a "
    "torção e as **cargas por metro de um pórtico transversal**, com a solução do pórtico. O que "
    "a norma não cobre vira aviso na tabela — o programa não corrige a entrada em silêncio."
)
mostrar_vento_nas_estruturas()
