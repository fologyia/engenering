"""Ajuda ("?") da página Modelo em 3D, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "vista": (
        "De onde olhar: isométrica (de cima e de lado), superior (planta), frontal ou lateral. "
        "Os nomes seguem a planta do programa."
    ),
    "giro": "Gira a vista em torno do eixo vertical, de 15° em 15°.",
    "cor_por": (
        "O que a cor de cada barra mostra: o tipo (pilar, viga, contraventamento), o perfil, a "
        "carga do vento numa direção, o esforço normal de um caso importado (tração azul, "
        "compressão vermelho) ou o aproveitamento da verificação (verde a vermelho)."
    ),
    "direcao_vento": "Qual vento colorir (W0 sopra para +X, W90 para +Y da planta).",
    "caso_normal": "O caso importado de Esforços do modelo cujo esforço normal vai na cor.",
    "desenho": (
        "Perfil real: cada barra com a seção do catálogo (o I, o U, a cantoneira) e a alma na "
        "posição do modelo. Só eixos: as linhas de centro, mais leve."
    ),
    "mostrar": "O que entra no desenho.",
    "cargas": (
        "Mostra as cargas de um caso do plano de cargas: kN/m como um pente ao longo da barra, "
        "kN como uma seta no meio dela. Só entram as linhas que estão numa barra do esqueleto."
    ),
    "reacoes": (
        "Mostra os apoios no pé dos pilares e, com um caso importado, a reação vertical (N) de "
        "cada um. O apoio é engastado quando a base tem momento, articulado quando não tem."
    ),
    "caso_reacoes": "O caso importado de Esforços do modelo cujas reações aparecem.",
    "barra": "Destaca uma barra (as outras ficam claras) e mostra os dados dela ao lado.",
    "res_cargas": "Soma das cargas desenhadas do caso (na direção vertical, para baixo).",
    "res_reacoes": "Soma das reações verticais nas bases dos pilares (para cima).",
    "res_fora": (
        "Linhas do caso que não estão numa barra do esqueleto (por área, por texto, num nó): "
        "não têm lugar certo no desenho."
    ),
    "btn_png": "Baixa o desenho em PNG (para relatório ou apresentação).",
    "modo_escada": (
        "Escada detalhada: cada degrau, as longarinas e o guarda-corpo de verdade (corrimão, "
        "travessa e montantes). Casca translúcida: o lance como uma tampa e o guarda-corpo como "
        "painéis translúcidos — o volume, que ajuda a ver o conjunto e fica limpo no relatório."
    ),
}
