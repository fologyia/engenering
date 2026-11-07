"""Montador de fluidos: tubulação, bombas, hidrostática e escoamento externo."""

from __future__ import annotations

import streamlit as st

from components.montador_ui import tela_do_montador
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core.montador_modelos import PARTE_FLUIDOS as PARTE

configurar_pagina(PARTE.titulo, ":material/water_drop:")

cabecalho_pagina(
    PARTE.titulo,
    PARTE.subtitulo,
    categoria="Mecânica dos fluidos",
    icone=":material/water_drop:",
    modulo_id=PARTE.modulo_id,
)
st.page_link(
    PARTE.pagina_da_outra, label=f"Ir para {PARTE.nome_da_outra}", icon=":material/function:"
)

with secao_protegida(PARTE.titulo):
    tela_do_montador(PARTE)
