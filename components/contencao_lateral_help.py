"""Textos dos "?" da página Contenção lateral (travamentos), em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_caso": (
        "O que está sendo travado e como. Um travamento só vale para reduzir o comprimento "
        "destravado se for forte e rígido o bastante (NBR 8800, 4.12)."
    ),
    "caso": (
        "Pilar: a barra de travamento impede o pilar de andar de lado. Viga, translação: a barra "
        "segura a mesa comprimida. Viga, torção: uma viga transversal ou um quadro impede a viga "
        "de girar (pode ficar em qualquer altura da seção). Torção contínua: forma de aço, laje "
        "ou painel ligado ao longo da viga."
    ),
    "familia": "De onde vem o perfil travado: catálogo W/HP, I laminado ou soldado.",
    "perfil": "A bitola do pilar ou da viga travada.",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura das mesas do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "sec_esforco": "O esforço de cálculo na barra travada e a distância entre os travamentos.",
    "N_Sd": "Força de compressão de cálculo no pilar, em kN.",
    "M_Sd": "Momento fletor de cálculo máximo na viga entre os travamentos, em kN·m.",
    "barras": (
        "Quantas barras iguais a mesma linha de travamento segura em série (por exemplo, uma "
        "escora que trava três pilares). As forças se somam."
    ),
    "L_b": "Distância entre os pontos travados (o comprimento destravado), em mm.",
    "L_q": (
        "Opcional: o maior comprimento destravado com que a barra ainda resiste ao esforço, em "
        "mm. Se a distância real for menor, a norma deixa usar L_q, o que reduz a rigidez "
        "exigida. Use 0 para não considerar."
    ),
    "n": (
        "Pilar: número de travamentos ao longo dele. Viga, torção: número de pontos travados "
        "dentro do vão."
    ),
    "curvatura_reversa": (
        "Ligue quando o travamento fica perto do ponto de inflexão de uma viga com momento "
        "trocando de sinal: a força dobra (C_d = 2) e é preciso travar as duas mesas."
    ),
    "L_vao": "Vão da viga, em mm (entra no momento exigido da contenção de torção).",
    "Cb": "Fator C_b do diagrama de momento da viga (5.4.2.3). Na dúvida, 1,0.",
    "t_st": (
        "Espessura do enrijecedor da alma no ponto travado, em mm (0 = sem). Sem enrijecedor, a "
        "alma costuma se deformar e o travamento de torção não funciona."
    ),
    "b_st": "Largura de um enrijecedor (de um lado da alma), em mm.",
    "par_de_enrijecedores": "Ligado: um enrijecedor de cada lado da alma (a largura conta dobrado).",
    "sec_barra": (
        "A barra que faz o travamento: a força passa por ela, e a rigidez dela (E·A/L, com a "
        "inclinação e a ligação) precisa ser maior que a exigida."
    ),
    "trabalho": (
        "Só tração: tirante ou barra redonda, que não aguenta compressão (é preciso ter outra "
        "barra para o outro sentido). Tração e compressão: cantoneira, tubo ou perfil, verificado "
        "à flambagem."
    ),
    "A_br": 'Área da seção da barra de travamento, em mm². Ex.: L 2" × 3/16" ≈ 460 mm².',
    "r_br": "Menor raio de giração da barra de travamento, em mm (para a flambagem).",
    "L_br": "Comprimento da barra de travamento, em mm.",
    "angulo": (
        "Ângulo entre a barra de travamento e a direção em que ela segura a barra travada, em "
        "graus. 0° = perpendicular à barra travada (o ideal)."
    ),
    "aco_br": "Aço da barra de travamento.",
    "k_ligacao": (
        "Rigidez da ligação da barra de travamento, em kN/mm (folga e deformação dos parafusos). "
        "Use 0 para ligação rígida. Ela entra em série com a barra e reduz a rigidez total."
    ),
    "sec_torcao": (
        "A contenção de torção: a rigidez à rotação que ela oferece e a resistência da ligação "
        "dela com a viga."
    ),
    "beta_tipo": (
        "Como obter a rigidez à rotação β: informada por você, ou de uma viga transversal ligada "
        "rigidamente (6·E·I/S se ela dobra em S, travando vigas dos dois lados; 2·E·I/S se dobra "
        "em curvatura simples)."
    ),
    "beta": (
        "Rigidez à rotação da contenção, em kN·m/rad (na torção contínua, por metro de viga)."
    ),
    "I_transversal": "Momento de inércia da viga transversal no plano em que ela dobra, em mm⁴.",
    "S_transversal": "Vão da viga transversal (distância entre as vigas travadas), em mm.",
    "M_Rd_ligacao": (
        "Momento resistente de cálculo da ligação da contenção com a viga, em kN·m (na torção "
        "contínua, por metro)."
    ),
    "gama_a1": "Coeficiente de ponderação do escoamento e da flambagem (γ_a1). Normal: 1,10.",
}
