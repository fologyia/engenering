"""Montador de processos: fluidos e térmico no mesmo desenho, ligados pela corrente e pela linha."""

from __future__ import annotations

import streamlit as st

from components.montador_ui import tela_do_montador
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core.montador_modelos import PARTE_PROCESSOS as PARTE

configurar_pagina(PARTE.titulo, ":material/hub:")

cabecalho_pagina(
    PARTE.titulo,
    PARTE.subtitulo,
    categoria="Mecânica",
    icone=":material/hub:",
    modulo_id=PARTE.modulo_id,
)
colunas = st.columns(2)
colunas[0].page_link(
    PARTE.pagina_da_outra, label=f"Ir para {PARTE.nome_da_outra}", icon=":material/thermostat:"
)
colunas[1].page_link(
    "app_pages/montador_fluidos.py",
    label="Ir para o Montador de fluidos",
    icon=":material/water_drop:",
)

with secao_protegida(PARTE.titulo):
    tela_do_montador(PARTE)
