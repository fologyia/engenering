"""Montador de fórmulas: ligar blocos e isolar a grandeza que se quer."""

from __future__ import annotations

from components.montador_ui import tela_do_montador
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Montador de fórmulas", ":material/function:")

cabecalho_pagina(
    "Montador de fórmulas",
    "Ligue a seção, os esforços e o critério, e escolha em função do que a equação deve ficar.",
    categoria="Mecânica geral",
    icone=":material/function:",
)

with secao_protegida("Montador de fórmulas"):
    tela_do_montador()
