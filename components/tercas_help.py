"""Textos dos "?" da página Terças e travessas, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_perfil": (
        "O perfil U enrijecido (Ue) de chapa dobrada a frio: altura da alma, largura das mesas, "
        "enrijecedor de borda (a dobra da ponta) e espessura, em medidas nominais."
    ),
    "uso": (
        "Terça: apoia a telha da cobertura (peso, sobrecarga e vento). Travessa: apoia a telha do "
        "fechamento lateral (vento de pressão e de sucção; o peso atua de lado)."
    ),
    "bw": "Altura nominal da alma b_w, em mm. Ex.: 200.",
    "bf": "Largura nominal das mesas b_f, em mm. Ex.: 75.",
    "D": "Largura do enrijecedor de borda D (a dobra na ponta da mesa), em mm. Ex.: 20.",
    "t": "Espessura da chapa, em mm. Ex.: 2,65.",
    "aco": "Aço da chapa. Ex.: ZAR 345 (f_y = 345 MPa).",
    "sec_vao": "O vão entre os apoios (pórticos), as linhas de corrente e a faixa de telha que a barra recebe.",
    "L": "Vão da terça ou travessa entre os apoios, em mm.",
    "tirantes": (
        "Linhas de corrente (tirantes) no vão. Elas seguram a barra de lado e cortam o vão que "
        "pode girar (FLT) e dobrar na menor inércia: com 1 linha, metade do vão."
    ),
    "inclinacao": "Inclinação do telhado, em graus (só para terça). Ex.: 10°.",
    "espacamento": "Distância entre terças (ou travessas), em mm: a faixa de telha que cada uma recebe.",
    "sec_cargas": "As cargas na telha por m², características (sem majorar), e os coeficientes.",
    "g": "Peso da telha, fixações e forro, em kN/m² (o peso do perfil o programa soma).",
    "q": "Sobrecarga de cobertura, em kN/m². NBR 8800, Anexo B: 0,25 kN/m² no mínimo.",
    "w_succao": "Vento de sucção perpendicular à telha, em kN/m² (o que puxa a telha para fora).",
    "w_pressao": "Vento de pressão perpendicular à telha, em kN/m² (o que empurra a telha).",
    "gama_g": "Coeficiente das cargas permanentes na gravidade. Na sucção o programa usa 1,0.",
    "gama_q": "Coeficiente da sobrecarga. Ação variável: 1,50.",
    "gama_w": "Coeficiente do vento. Ação variável: 1,40.",
    "sec_criterios": "Como a telha trava o perfil e os limites de flecha.",
    "telha_trava": (
        "Ligado: a telha parafusada na mesa de cima impede a flambagem lateral quando essa mesa "
        "está comprimida (gravidade). Desligado: a FLT é verificada entre as linhas de corrente."
    ),
    "usar_anexo_f": (
        "Ligado: na sucção, com a mesa livre comprimida, usa o fator R do Anexo F (telha de aço "
        "parafusada na mesa tracionada), se as condições geométricas valerem; senão, a FLT."
    ),
    "M_dist": (
        "Momento de flambagem distorcional elástica M_dist, em kN·m, de uma análise de "
        "estabilidade (ex.: programa de faixas finitas). Só é usado quando o enrijecedor de borda "
        "é curto para a Tabela 14 dispensar a verificação. Use 0 se não tiver."
    ),
    "flecha_gravidade": (
        "Divisor do limite de flecha com peso + sobrecarga (ou pressão): L/180 para terças "
        "(NBR 14762, Tabela A.1)."
    ),
    "flecha_succao": "Divisor do limite de flecha só com o vento de sucção: L/120 (Tabela A.1).",
}
