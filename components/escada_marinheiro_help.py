"""Ajuda (o "?") de cada campo da página Escada marinheiro, em linguagem simples."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_geometria": (
        "A escada em si: altura, lances, largura e onde ficam as barras. Os limites são os da "
        "NR-12, Anexo III, item 13."
    ),
    "sec_degraus": "As barras em que se pisa (os degraus da escada marinheiro).",
    "sec_gaiola": (
        "A gaiola de proteção em volta de quem sobe. A NR-12 exige gaiola em escada com mais de "
        "3,50 m de altura."
    ),
    "sec_estrutura": "O aço, os montantes (as barras laterais) e onde a escada se prende.",
    "sec_cargas": (
        "As cargas da conta. A NR-12 só pede que a escada aguente os esforços: a carga do degrau "
        "vem da NBR 6120 e a das pessoas no lance é critério do programa, que você pode mudar."
    ),
    # ------------------------------------------------------------------ geometria
    "altura": "Desnível do piso de baixo até o piso de chegada, em metros.",
    "lances": (
        "Em quantos lances a escada é dividida. Um lance só vai até 10 m; com mais de um, cada "
        "lance tem até 6 m e para numa plataforma de descanso (NR-12, item 13 f e g)."
    ),
    "afastamento_lances": (
        "Distância entre os eixos de dois lances seguidos, que ficam lado a lado e paralelos. "
        "A NR-12 pede pelo menos 700 mm (item 13 g)."
    ),
    "inclinacao": (
        "Ângulo da escada com o chão. Escada marinheiro vai de 75° a 90° (NR-12, Figura 1); "
        "abaixo disso, use escada de degraus."
    ),
    "largura": "Largura livre entre os montantes. A NR-12 pede de 400 a 600 mm (item 13 e).",
    "passo": (
        "Distância de uma barra até a próxima, sempre igual. A NR-12 pede de 250 a 300 mm "
        "(item 13 h)."
    ),
    "primeira_barra": (
        "Altura da primeira barra acima do piso de baixo. A NR-12 pede no máximo 550 mm "
        "(item 13 i)."
    ),
    "afastamento": (
        "Distância das barras até a parede, coluna ou equipamento em que a escada é presa: é o "
        "espaço para o pé. A NR-12 pede pelo menos 150 mm (item 13 j)."
    ),
    "ultrapassa": (
        "Quanto os montantes (ou o corrimão) passam acima do piso de chegada, para a mão ter "
        "onde segurar ao sair. A NR-12 pede de 1100 a 1200 mm (item 13 d)."
    ),
    # ------------------------------------------------------------------ degraus
    "forma_degrau": "Barra redonda ou quadrada maciça, em que se pisa.",
    "degrau": (
        "Diâmetro da barra redonda ou lado da quadrada. A NR-12 pede de 25 a 38 mm (item 13 k)."
    ),
    "antiderrapante": (
        "Ligue se as barras têm ranhura, recartilhado ou forma que impeça o pé de escorregar. A "
        "NR-12 exige (item 13 l)."
    ),
    # ------------------------------------------------------------------ gaiola
    "gaiola": "Ligue quando a escada tem gaiola de proteção.",
    "inicio_gaiola": (
        "Altura do piso até o começo da gaiola. A NR-12 manda a gaiola começar a 2,0 m do piso "
        "(item 13 c)."
    ),
    "gaiola_ultrapassa": (
        "Quanto a gaiola passa acima do piso de chegada. A NR-12 pede de 1100 a 1200 mm "
        "(item 13 c)."
    ),
    "diametro_gaiola": "Diâmetro da gaiola. A NR-12 pede de 650 a 800 mm (item 13.1).",
    "tipo_gaiola": (
        "Como a gaiola é feita. **Barras verticais e arcos**: barras verticais a até 300 mm "
        "uma da outra e arcos a até 1500 mm. **Arcos próximos**: arcos a até 300 mm, presos por "
        "barra vertical de sustentação (NR-12, item 13.1)."
    ),
    "verticais": (
        "Distância entre as barras verticais da gaiola, medida em volta. No tipo com barras "
        "verticais e arcos, a NR-12 pede no máximo 300 mm."
    ),
    "arcos": (
        "Distância de um arco da gaiola ao próximo, na altura. Até 1500 mm com barras verticais; "
        "até 300 mm no tipo de arcos próximos (NR-12, item 13.1)."
    ),
    "arco_b": "Largura da barra chata dos arcos da gaiola (entra só no peso).",
    "arco_t": "Espessura da barra chata dos arcos da gaiola (entra só no peso).",
    "vertical_b": "Largura da barra chata das barras verticais da gaiola (entra só no peso).",
    "vertical_t": "Espessura da barra chata das barras verticais (entra só no peso).",
    # ------------------------------------------------------------------ estrutura
    "aco": "Aço das barras e dos montantes; dá o f_y da conta.",
    "montante_b": (
        "Largura da barra chata do montante, a medida que vai em direção à parede. É ela que "
        "segura a escada entre os suportes."
    ),
    "montante_t": (
        "Espessura da barra chata do montante. No plano da escada, as barras travam um "
        "montante no outro: ali a flambagem é entre duas barras."
    ),
    "fixacoes": (
        "Distância, na altura, entre dois suportes que prendem a escada na estrutura. É o "
        "comprimento de flambagem do montante em direção à parede."
    ),
    "ambiente": (
        "Ligue se a escada fica ao tempo ou em ambiente corrosivo: aí a NR-12 pede material ou "
        "revestimento resistente a intempéries e corrosão (item 13 b)."
    ),
    "protecao": "Ligue se a escada é galvanizada, pintada para o ambiente ou de aço inoxidável.",
    # ------------------------------------------------------------------ cargas
    "carga_degrau": (
        "Carga concentrada no meio da barra, na conta do degrau. 2,5 kN é a do degrau isolado "
        "da NBR 6120 (2.2.1.7 da edição de 1980; Tabela 10, nota t, da de 2019)."
    ),
    "pessoas": (
        "Quantas pessoas sobem o mesmo lance ao mesmo tempo, cada uma com a carga do degrau. "
        "Entra na compressão dos montantes e nos suportes. A NR-12 não dá esse número: confira "
        "com o cliente."
    ),
    # ------------------------------------------------------------------ resultados
    "res_status": "Se a escada atende a todas as verificações da NR-12 e da NBR 8800.",
    "res_aproveitamento": (
        "A maior razão solicitante ÷ resistente entre o degrau e o montante; até 100 % passa."
    ),
    "res_barras": "Quantas barras cada lance tem, contando a partir da primeira.",
    "res_peso": "Peso estimado da escada inteira, com a gaiola, sem os suportes.",
    "res_desenhos": (
        "A escada de frente, com as cotas da NR-12, e a planta, com a distância à estrutura e a "
        "gaiola. Os mesmos desenhos vão para o memorial."
    ),
    "res_verificacoes": (
        "Cada exigência da NR-12 e cada conta da NBR 8800, com o valor, o limite e o item."
    ),
    "res_suportes": (
        "Forças de cálculo em cada suporte, para dimensionar o suporte e os chumbadores na "
        "página Placas de base ou Projeto de parafusos."
    ),
    "res_conferir": "O que a NR-12 e a NR-35 pedem além da conta.",
    "btn_csv": "Baixa a tabela de verificações para abrir no Excel.",
    "reg_registrar": "Grava esta escada no projeto ativo; ela entra no memorial com os desenhos.",
}
