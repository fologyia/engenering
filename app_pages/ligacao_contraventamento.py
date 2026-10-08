import streamlit as st

from components.contraventamento_ui import mostrar_ligacao_de_contraventamento
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Ligação de contraventamento", ":material/hub:")
cabecalho_pagina(
    "Ligação de contraventamento",
    "Chapa de nó em canto viga–coluna • Método das Forças Uniformes • AISC Design Guide 29 • "
    "AISC 360-16",
    categoria="Dimensionamento",
    icone=":material/hub:",
    cor="blue",
    ajuda_modulo="Ligação de contraventamento",
    acoes=(("app_pages/vento_nbr6123.py", "Vento nas estruturas", ":material/air:"),),
    modulo_id="ligacao_contraventamento",
)
st.caption(
    "Distribui a força do contraventamento entre a chapa de nó, a viga e a coluna pelo Método "
    "das Forças Uniformes (caso geral e casos especiais 1, 2 e 3) e verifica os parafusos, a "
    "seção de Whitmore, o bloco de cisalhamento, a flambagem da chapa, as soldas e a alma da "
    "viga e da coluna, em LRFD ou ASD, com o item da norma em cada linha. O que não dá para "
    "calcular vira erro claro — o programa não corrige a entrada em silêncio."
)
mostrar_ligacao_de_contraventamento()
