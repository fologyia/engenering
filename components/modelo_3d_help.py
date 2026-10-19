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
        "Mostra os apoios no pé dos pilares e, com um caso importado, a reação de cada um: a "
        "vertical (N) sempre e a horizontal (H) quando o programa sabe para que lado a seção do "
        "pilar está virada no Simulation. O apoio é engastado quando a base tem momento, "
        "articulado quando não tem."
    ),
    "caso_reacoes": "O caso importado de Esforços do modelo cujas reações aparecem.",
    "barra": "Destaca uma barra (as outras ficam claras) e mostra os dados dela ao lado.",
    "res_cargas": "Soma das cargas desenhadas do caso (na direção vertical, para baixo).",
    "res_reacoes": "Soma das reações verticais nas bases dos pilares (para cima).",
    "res_cargas_h": (
        "Soma das cargas horizontais desenhadas do caso, em X e em Y da planta (kN). Com todos os "
        "apoios nos pilares, as reações horizontais têm de dar o mesmo valor com o sinal trocado."
    ),
    "res_reacoes_h": (
        "Soma das reações horizontais nas bases dos pilares que têm a direção da seção, em X e Y "
        "da planta (kN): a força que o apoio faz no pilar."
    ),
    "sec_direcoes": (
        "O Simulation dá V₁ e V₂ nos eixos da seção de cada viga: a direção 1 é paralela à aresta "
        "reta mais longa da seção, mas o sentido dela ele escolhe sozinho. O programa pega a "
        "linha pela macro v6 e o sentido por um caso com carga no pilar (o vento viga a viga): a "
        "carga que o Simulation mostra no pilar tem de apontar para onde o plano mandou. Sem "
        "isso, V₁ e V₂ ficam só no rótulo."
    ),
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
