"""Desenhar uma seção qualquer e usá-la em qualquer cálculo do programa."""

from components.desenhar_secao_ui import tela
from components.ui import cabecalho_pagina, configurar_pagina

configurar_pagina("Desenhar seção", ":material/draw:")
cabecalho_pagina(
    "Desenhar seção",
    "Desenhe, ajuste as medidas e use a seção em qualquer cálculo do programa",
    categoria="Seções e materiais",
    icone=":material/draw:",
    cor="violet",
    mostrar_ferramentas=False,
)
tela()
