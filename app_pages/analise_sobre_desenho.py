"""Análise sobre o desenho: marcas num desenho, cada uma ligada a uma análise do Montador."""

from __future__ import annotations

from components.analise_desenho_ui import tela
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina

TITULO = "Análise sobre o desenho"

configurar_pagina(TITULO, ":material/ads_click:")

cabecalho_pagina(
    TITULO,
    "Solte o desenho (imagem, PDF, DXF ou print colado), marque as partes e escolha a análise do "
    "Montador de cada uma: pino, chapa com furo, eixo, chaveta...",
    categoria="Mecânica",
    icone=":material/ads_click:",
    modulo_id="analise_sobre_desenho",
)

with secao_protegida(TITULO):
    tela()
