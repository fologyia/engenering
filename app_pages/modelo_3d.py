"""Modelo em 3D: o esqueleto do SolidWorks com o perfil real, as cargas, as reações e os resultados."""

from __future__ import annotations

import streamlit as st

from components.modelo_3d_ui import mostrar_modelo_3d
from components.ui import cabecalho_pagina, configurar_pagina
from core.project_store import obter_projeto_ativo

configurar_pagina("Modelo em 3D", ":material/deployed_code:")
cabecalho_pagina(
    "Modelo em 3D",
    "O esqueleto do SolidWorks com o perfil real de cada barra, as chapas e os guarda-corpos; as "
    "cargas de um caso, os apoios e as reações; e a cor pelo tipo, perfil, vento, esforço normal "
    "ou aproveitamento.",
    categoria="Modelo SolidWorks",
    icone=":material/deployed_code:",
    cor="blue",
    acoes=(
        ("app_pages/cargas_esqueleto.py", "Cargas do esqueleto", ":material/grid_view:"),
        ("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),
    ),
)
projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: o modelo em 3D é o "
        "esqueleto gravado no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()
mostrar_modelo_3d(projeto)
