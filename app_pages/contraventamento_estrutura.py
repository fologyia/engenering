import streamlit as st

from components.contraventamento_estrutura_ui import mostrar_contraventamento_de_estrutura
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Contraventamento de estruturas abertas", ":material/grid_on:")
cabecalho_pagina(
    "Contraventamento de estruturas abertas",
    "Plataformas, mezaninos e pipe racks • vento por reticulados (NBR 6123:2023, cap. 8) • "
    "combinações, forças nocionais e B₂ (NBR 8800:2024) • diagonais e ligações",
    categoria="Dimensionamento",
    icone=":material/grid_on:",
    cor="blue",
    ajuda_modulo="Contraventamento de estruturas abertas",
    acoes=(
        ("app_pages/ligacao_contraventamento.py", "Ligação de contraventamento", ":material/hub:"),
    ),
    modulo_id="contraventamento_estrutura",
)
st.caption(
    "Informe a planta, os pisos, as cargas e o vento do local: o programa calcula o vento nos "
    "pórticos, guarda-corpos e equipamentos, monta as combinações (ELU, ELS e forças nocionais), "
    "avalia a segunda ordem (B₂), leva o cortante de cada andar às diagonais e verifica barra, "
    "parafusos, solda e deslocamentos — com o item da norma em cada linha."
)
mostrar_contraventamento_de_estrutura()
