"""Cálculos externos e capítulos manuais do projeto ativo."""

import streamlit as st

from components.calculo_externo_ui import renderizar_calculos_externos
from components.project_tools import obter_projeto_ativo_para_edicao, sincronizar_projeto_ativo
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Cálculos do projeto", ":material/calculate:")
cabecalho_pagina(
    "Cálculos do projeto",
    "Consulte os registros e prepare capítulos manuais ou externos para o memorial.",
    categoria="PROJETO ATIVO",
    icone=":material/calculate:",
    cor="blue",
)
sincronizar_projeto_ativo()
projeto = obter_projeto_ativo_para_edicao()
if projeto is None:
    st.warning("Abra um projeto permanente para cadastrar cálculos externos.")
    st.page_link(
        "app_pages/gestao_projetos.py", label="Abrir projetos", icon=":material/folder_open:"
    )
    st.stop()
st.subheader(f"{projeto['codigo']} · {projeto['nome']}")
renderizar_calculos_externos(projeto)
