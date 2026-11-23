"""Textos dos "?" da página Viga mista, em linguagem simples."""

AJUDA: dict[str, str] = {
    "sec_perfil": (
        "O perfil de aço da viga, que trabalha junto com a laje de concreto graças aos conectores "
        "soldados na mesa de cima."
    ),
    "familia": "De onde vem o perfil: catálogo W/HP, I laminado ou soldado.",
    "perfil": "A bitola do perfil. Ex.: W 410 x 38,8.",
    "d": "Altura total do perfil soldado, em mm.",
    "bf": "Largura das mesas do perfil soldado, em mm.",
    "tf": "Espessura das mesas do perfil soldado, em mm.",
    "tw": "Espessura da alma do perfil soldado, em mm.",
    "aco": "Aço do perfil.",
    "gama_a1": "Coeficiente de ponderação do aço (γ_a1). Combinação normal: 1,10.",
    "L": "Vão da viga, de centro a centro dos apoios, em mm.",
    "sec_laje": (
        "A laje que trabalha com a viga. A parte que colabora (largura efetiva) é o menor entre "
        "1/8 do vão e metade da distância até a viga vizinha, de cada lado."
    ),
    "s_esquerda": "Distância até a viga vizinha do lado esquerdo, em mm. Use 0 se for borda de laje.",
    "s_direita": "Distância até a viga vizinha do lado direito, em mm. Use 0 se for borda de laje.",
    "balanco_esquerda": "Na borda esquerda: distância do eixo da viga até a borda da laje, em mm.",
    "balanco_direita": "Na borda direita: distância do eixo da viga até a borda da laje, em mm.",
    "tc": (
        "Espessura do concreto que trabalha, em mm: a laje inteira na laje maciça, ou o concreto "
        "acima das nervuras na laje com fôrma de aço."
    ),
    "hF": "Altura das nervuras da fôrma de aço (steel deck), em mm. Use 0 para laje maciça.",
    "fck": "Resistência característica do concreto, em MPa (a NBR 8800 aceita de 20 a 50).",
    "brita": "Tipo de brita do concreto: muda o módulo de elasticidade (α_e da NBR 8800, 4.6.3.1).",
    "sec_conectores": (
        "Os conectores tipo pino com cabeça (stud bolts) que ligam a viga à laje. Eles levam o "
        "cisalhamento entre o aço e o concreto."
    ),
    "diametro_conector": "Diâmetro do conector, em mm. Os comuns: 16, 19 e 22 mm.",
    "fu_conector": "Resistência à ruptura do aço do conector, em MPa. ASTM A108 (stud): 415 MPa.",
    "posicao": (
        "Onde o conector é soldado: direto no perfil (laje maciça) ou através da fôrma, com 1, 2 "
        "ou mais por nervura. e_mh é a distância do conector à parede da nervura, do lado da força."
    ),
    "conectores": (
        "Número de conectores entre o apoio e o meio do vão (metade da viga). O total na viga é "
        "o dobro."
    ),
    "por_linha": "Conectores lado a lado na mesma seção (1 ou 2 é o comum).",
    "sec_cargas": (
        "Cargas características por metro de viga (sem majorar), separadas em antes e depois de "
        "o concreto endurecer (importa na construção sem escoras)."
    ),
    "g1": (
        "Cargas permanentes antes da cura, em kN/m: peso do perfil, da fôrma e do concreto fresco."
    ),
    "q_construcao": "Sobrecarga de construção durante a concretagem, em kN/m (pessoas, equipamentos).",
    "g2": "Cargas permanentes aplicadas depois da cura, em kN/m: revestimento, forro, divisórias.",
    "q": "Sobrecarga de uso, em kN/m (sobrecarga do piso × largura de influência).",
    "gama_g": "Coeficiente de ponderação das permanentes. Concreto moldado no local: 1,35.",
    "gama_q": "Coeficiente de ponderação da sobrecarga de uso: 1,50.",
    "gama_construcao": "Coeficiente da sobrecarga de construção (combinação de construção): 1,30.",
    "sec_construcao": "Como a viga é construída e os limites de flecha.",
    "escorada": (
        "Ligado: a viga fica escorada até o concreto endurecer, e tudo é resistido pela seção "
        "mista. Desligado: o perfil sozinho segura o concreto fresco."
    ),
    "Lb_construcao": (
        "Comprimento sem travamento lateral do perfil durante a concretagem, em mm. Use 0 quando "
        "a fôrma de aço está fixada na mesa e trava a viga (L.2.3.2 a))."
    ),
    "flecha_limite": "Divisor do limite de flecha: L/350 para vigas de piso (NBR 8800, Tabela B.1).",
    "contraflecha": "Contraflecha de fabricação, em mm (descontada da flecha total).",
}
