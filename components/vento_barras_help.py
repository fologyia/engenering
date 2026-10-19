"""Ajuda ("?") da parte barra a barra da página Vento em estruturas abertas, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    "sec_como": (
        "Em vez de imaginar pórticos iguais, o programa pega cada barra do seu modelo e calcula "
        "quanto vento ela recebe em cada direção: a área que a barra mostra para o vento (a "
        "“sombra”), o coeficiente da norma e a pressão na altura dela. Serve para "
        "qualquer forma: duas colunas, plataforma em balanço, escada, passarela."
    ),
    "sec_barras": (
        "As barras que recebem vento. Vêm do esqueleto que a macro do SolidWorks exporta (página "
        "Cargas do esqueleto) ou você digita. Coordenadas em metros, nos eixos do seu modelo."
    ),
    "origem": (
        "Esqueleto do modelo: as barras que a macro leu, com a seção e a posição da alma. Digitar: "
        "você mesmo monta a lista (útil para estudos rápidos ou sem a macro)."
    ),
    "eixo_vertical": (
        "Qual eixo do seu modelo aponta para cima. No SolidWorks quase sempre é o Y. O programa "
        "usa isso para saber a altura de cada barra e para devolver as cargas nos eixos certos."
    ),
    "tabela_barras": (
        "Uma linha por barra: as duas pontas (X, Y, Z do modelo, em m), as duas medidas da seção "
        "(mm) e para onde aponta a medida maior (a alma). Desmarque “Usar” para tirar uma "
        "barra do vento. “Não sei” usa a medida maior em qualquer direção (a favor da "
        "segurança)."
    ),
    "sec_elementos": (
        "O que pega vento e não está no esqueleto: guarda-corpo, a lateral da escada, painel, "
        "equipamento. A força de cada um vai para a viga que o apoia."
    ),
    "tabela_elementos": (
        "Guarda-corpo, escada e painel: as duas pontas da linha da base (onde ele apoia) e a "
        "altura. Equipamento: o centro da base, as duas medidas em planta e a altura (no "
        "cilindro, a primeira medida é o diâmetro). φ = parte cheia da área (guarda-corpo com "
        "rodapé ≈ 0,30; lateral de escada ≈ 0,50; painel fechado = 1). Barra vazia: o programa "
        "acha a viga embaixo da linha (ou a mais próxima)."
    ),
    "gc_bordas": (
        "Põe na tabela um guarda-corpo em cada borda livre do piso, na viga que o apoia — o "
        "programa acha pelas chapas de piso do esqueleto (o acesso da escada fica sem). Os "
        "trechos, a altura e o φ se ajustam em Cargas do esqueleto."
    ),
    "sec_opcoes": "Quais direções calcular, se considera a proteção entre planos e onde é o chão.",
    "direcoes": (
        "As 4 perpendiculares às faces (0°, 90°, 180°, 270°) são o que a NBR 6123 pede para "
        "estruturas reticuladas. As 8 acrescentam os diagonais (45°, 135°, 225°, 315°), calculados "
        "a favor da segurança: sem proteção e com o maior coeficiente (2,0) — por isso costumam dar "
        "mais força que os perpendiculares."
    ),
    "protecao": (
        "A barra que fica atrás de outro plano de barras, na direção do vento, recebe menos vento "
        "(fator η da norma). Desligado: todas recebem o vento cheio (mais conservador)."
    ),
    "terreno": (
        "A cota do chão no seu modelo (m, no eixo vertical). Vazio: o pé dos pilares (o mais baixo "
        "das barras em pé; sem pilares, o ponto mais baixo). A altura de cada barra acima do chão "
        "define a pressão do vento nela."
    ),
    "res_governante": "A direção que dá a maior força total na estrutura.",
    "res_total": "Soma das forças do vento (barras e elementos) na direção que mais carrega.",
    "res_tombamento": "Maior momento de tombamento na base: soma de força × altura.",
    "res_q": "Pressão dinâmica no topo da estrutura (a maior que aparece).",
    "res_resumo": (
        "Cada direção calculada: o caso no plano de cargas (W0 sopra para +X, W90 para +Y), as "
        "forças nas barras e nos elementos, o tombamento e a torção da planta."
    ),
    "res_niveis": (
        "A força do vento que chega a cada nível (piso, patamar), em cada direção — o número para "
        'aplicar "no geral" ou conferir o contraventamento. Cada barra manda metade do vento '
        "dela para cada ponta; o que chega no pé dos pilares vai direto à fundação (linha "
        '"base"). "Passa em" é a linha, no modelo, por onde passa a força do nível: fora do '
        "meio da planta, ela também torce a estrutura."
    ),
    "res_nivel_principal": (
        "A força do vento no nível com mais vigas (a plataforma), nesta direção, em kN."
    ),
    "forma": (
        "Barra a barra: cada barra com a carga dela — o mais fiel, mas muitas cargas no "
        "SolidWorks. Simplificada: a força de cada nível vai para as vigas desse nível que correm "
        "na direção do vento (uma carga por linha de vigas): bem menos cargas, com a mesma força e "
        "a mesma torção em cada nível. Só a flexão de cada barra pelo vento dela fica de fora (o "
        "programa mostra quanto)."
    ),
    "res_simplificada": (
        "Em cada nível, a força do vento dividida entre as linhas de vigas na direção dele, pela "
        "regra da alavanca (a linha mais perto da força recebe mais). Cada viga da linha recebe o "
        "q da linha, ao longo do eixo dela: no SolidWorks, força distribuída na viga, na direção "
        "da própria viga."
    ),
    "ver_direcao": "Qual direção do vento mostrar nos desenhos e nas tabelas abaixo.",
    "res_3d": (
        "A estrutura em 3D, vista de barlavento: a cor de cada barra é a carga dela (kN/m) e as "
        "setinhas mostram para onde o vento empurra. As mais carregadas têm o valor escrito."
    ),
    "res_planta": (
        "A planta vista de cima: pilares com a alma na posição do modelo, vigas na cor da carga e "
        "os planos (reticulados) perpendiculares ao vento com o fator de proteção η."
    ),
    "res_sombra": (
        "O que o vento “vê”: a sombra de cada barra num plano perpendicular ao vento. É "
        "essa área que a norma multiplica pela pressão. Tom claro = parte protegida."
    ),
    "res_barras": (
        "Barra a barra: área de sombra, o plano em que está, C_a, η, a pressão na altura dela, a "
        "força e a carga por metro, com as componentes X e Y para lançar no modelo."
    ),
    "res_elementos": (
        "Guarda-corpos, escadas, painéis e equipamentos: a força de cada um e a barra que recebe."
    ),
    "res_reticulados": (
        "Os planos de barras perpendiculares ao vento, de barlavento (R1) para trás: área, φ, C_a "
        "e a proteção η de cada um."
    ),
    "sec_levar": (
        "Leve o vento para o plano de cargas (um caso por direção) ou baixe a tabela para lançar "
        "à mão. No SolidWorks: Força por unidade de comprimento em cada viga, nas componentes X e "
        "Y dadas (o plano converte para os eixos do modelo)."
    ),
    "btn_csv": (
        "Tabela (CSV, abre no Excel) com as cargas da forma escolhida: a de cada barra em cada "
        "direção, ou a de cada linha de vigas em cada nível."
    ),
    "btn_plano": (
        "Grava W0, W90, W180 e W270 (e os diagonais, se calculados) no plano de cargas do projeto, "
        "na forma escolhida. Substitui o vento que já estiver lá."
    ),
    "reg_registrar": (
        "Grava o cálculo no projeto ativo: o memorial passa a trazer o resumo, os reticulados, a "
        "carga de cada barra e os elementos."
    ),
}
