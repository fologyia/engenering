import streamlit as st

from components.degrau_ui import mostrar_degrau_de_escada
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Degrau de escada em grade", ":material/stairs:")
cabecalho_pagina(
    "Degrau de escada em grade",
    "Degrau industrial em grade de piso eletrofundida (Selmec DS) • NR-12 • NR-22 • Critério "
    "Anglo • NBR 8800 • ISO 14122-3",
    categoria="Dimensionamento",
    icone=":material/stairs:",
    cor="green",
    ajuda_modulo="Degrau de escada em grade",
    acoes=(("app_pages/casos_carga.py", "Casos de carga", ":material/layers:"),),
    modulo_id="degrau_escada",
)
st.caption(
    "Define o espelho, o piso e a profundidade do degrau pelo requisito legal, pelo Critério "
    "Anglo e pelo limite do catálogo; divide a escada em lances; avalia os **64 modelos** do "
    "catálogo Selmec e adota o mais leve que atende; dimensiona o degrau (flexão com flambagem "
    "lateral, cisalhamento, flechas, reações e parafusos A307) e fecha em **38 verificações** com "
    "o item da norma em cada uma. O que não dá para calcular vira erro claro — o programa não "
    "corrige a entrada em silêncio."
)
mostrar_degrau_de_escada()
