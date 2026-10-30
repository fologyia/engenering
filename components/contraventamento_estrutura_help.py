"""Textos dos “?” da página Contraventamento de estruturas abertas, em linguagem simples.

Cada texto diz o que é o campo, como preencher e, quando houver, a simplificação adotada. Um teste
garante que todo texto é usado por algum campo e que todo campo tem o seu.
"""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_1": "Dados do documento. Não entram no cálculo; saem no registro e no memorial.",
    "sec_2": (
        "A estrutura aberta em planta retangular: comprimento em X, largura em Y, os pisos e os "
        "vãos entre pilares. O programa monta os pórticos e mede a área que o vento enxerga."
    ),
    "sec_3": (
        "As cargas de cada piso, por metro quadrado, e o que fica apoiado nele. Servem para as "
        "**forças nocionais** (0,3 % do peso, a imperfeição da estrutura) e para o **B₂**, o "
        "efeito de segunda ordem."
    ),
    "sec_4": (
        "Os dados do vento no local (NBR 6123:2023). A estrutura aberta é tratada como "
        "**reticulados planos** (capítulo 8): cada pórtico perpendicular ao vento recebe força, "
        "e os de trás ficam parcialmente protegidos pelo da frente."
    ),
    "preencher_esqueleto": (
        "Preenche a planta (L_x, L_y entre eixos dos pilares), os vãos, as cotas dos pisos, a "
        "área de piso, os perfis dos pilares e das vigas e o contraventamento de cada direção "
        "(tipo, linhas, painéis e o perfil das diagonais, se for cantoneira, tubo ou barra "
        "redonda) com o que o esqueleto do modelo mostra. Os outros campos não mudam."
    ),
    "area_piso": (
        "A área de piso de cada nível (m²), que multiplica o peso da estrutura, do piso e a "
        "sobrecarga por área. Vazio: L_x × L_y. Numa plataforma em balanço ou com recortes, a área "
        "real é diferente — o esqueleto a dá pelas chapas de piso."
    ),
    "sec_metodo_vento": (
        "De onde vem a força do vento. **Pórticos regulares**: a grade da seção 2, cada pórtico "
        "como um reticulado. **Viga a viga, pilar a pilar**: cada barra do esqueleto do modelo "
        "recebe o vento dela (a área que mostra ao vento × pressão × coeficiente), e a força vai "
        "aos pisos pelas mesmas faixas — para estruturas que não são uma grade (duas colunas, "
        "escada, balanço)."
    ),
    "metodo_vento": (
        "Pórticos regulares: rápido, para planta retangular com pilares em grade. Viga a viga: "
        "usa o esqueleto que a macro do SolidWorks exportou, com os guarda-corpos das bordas e os "
        "equipamentos da tabela."
    ),
    "vb_eixo": "Qual eixo do modelo do SolidWorks aponta para cima (Y no padrão do SolidWorks).",
    "vb_direcoes": (
        "As 8 direções incluem os ventos inclinados (45°…), a favor da segurança (C_a = 2,0 e sem "
        "proteção): cada um carrega X e Y ao mesmo tempo. A norma (8.5) pede só as 4 "
        "perpendiculares."
    ),
    "vb_protecao": (
        "Ligado: as barras que ficam atrás de um plano de barras recebem menos vento (fator η da "
        "Figura 14). Desligado: todas recebem o vento cheio."
    ),
    "vb_terreno": (
        "A cota do chão no modelo (m). Vazio: o pé dos pilares (sem pilares, o ponto mais baixo). "
        "As cotas dos pisos da seção 2 contam a partir daqui."
    ),
    "vb_usar_cotas": (
        "Copia para as cotas dos pisos as alturas em que o esqueleto tem vigas (a partir do "
        "terreno). Confira depois o número de pisos e as cargas."
    ),
    "sec_5": (
        "O contraventamento vertical: o tipo (X, diagonal simples ou V invertido), quantas linhas "
        "e painéis travam cada direção, e a barra da diagonal com a sua ligação."
    ),
    "sec_6": (
        "Ajustes do cálculo que já vêm com o valor usual: a excentricidade da força em planta, "
        "o travamento no cruzamento do X e a combinação de serviço dos deslocamentos."
    ),
    # ------------------------------------------------------------------ identificação
    "obra": "Nome da obra ou do projeto, só para identificar o documento.",
    "tag": "Código da estrutura no desenho (por exemplo, PL-03). Sai no registro e no memorial.",
    "responsavel": "Quem calculou ou conferiu. Sai no registro e no memorial.",
    "data": "Data do cálculo. Sai no registro e no memorial.",
    # ------------------------------------------------------------------ estrutura
    "Lx": "Comprimento da estrutura na direção X, entre eixos dos pilares das pontas (m).",
    "Ly": "Largura da estrutura na direção Y, entre eixos dos pilares das pontas (m).",
    "n_pisos": "Quantos pisos (níveis com piso e guarda-corpo) a estrutura tem acima da base.",
    "h_andar": (
        "Altura de cada andar, de piso a piso (m). O primeiro andar vai da base ao primeiro piso."
    ),
    "cotas_livres": (
        "Opcional. Para andares de alturas diferentes, escreva as cotas dos pisos medidas da "
        "base, separadas por ponto e vírgula (ex.: 3,5; 7,0; 9,8). Vazio usa a altura acima."
    ),
    "vaos_x": "Quantos vãos entre pilares na direção X (2 vãos = 3 linhas de pilares).",
    "vaos_y": "Quantos vãos entre pilares na direção Y.",
    "pilar": (
        "Perfil dos pilares. O vento enxerga a maior medida da seção (altura ou largura da mesa), "
        "a favor da segurança."
    ),
    "viga": "Perfil das vigas dos pórticos. O vento enxerga a altura da viga em cada piso.",
    "guarda_corpo": (
        "Guarda-corpo em todo o perímetro de cada piso. Só os guarda-corpos perpendiculares ao "
        "vento recebem força (o da frente e o de trás)."
    ),
    "h_gc": "Altura do guarda-corpo acima do piso (NR-12: 1,10 m).",
    "phi_gc": (
        "Índice de área exposta φ do guarda-corpo: parte cheia ÷ área total. Com corrimão, "
        "travessa, montantes e rodapé de 20 cm, fica perto de 0,30."
    ),
    # ------------------------------------------------------------------ cargas
    "peso_estrutura": (
        "Peso próprio da estrutura de aço por área de piso (kN/m²), em cada piso. Plataformas "
        "leves ficam entre 0,4 e 0,8 kN/m²."
    ),
    "peso_piso": "Peso do piso por área (kN/m²): grade de piso ≈ 0,4 a 0,6; chapa xadrez ≈ 0,5.",
    "sobrecarga": (
        "Sobrecarga de uso por área (kN/m²), em cada piso. Plataformas industriais: 3 a 5 kN/m² "
        "(confira o critério do cliente e a NBR 6120)."
    ),
    "cat_sobrecarga": (
        "Categoria da sobrecarga na NBR 8800 (Tabela 2): define os fatores ψ₀, ψ₁ e ψ₂ usados "
        "quando ela acompanha o vento."
    ),
    "cat_equip": (
        "Categoria do peso dos equipamentos: a NBR 8800:2025 junta equipamentos com a estrutura "
        "de aço (γ = 1,25); a edição de 2008 usava 1,50."
    ),
    "equipamentos": (
        "Equipamentos apoiados nos pisos: o peso entra nas forças nocionais e no B₂; a área "
        "exposta recebe vento. Cilindro vertical usa as Tabelas 27 e 28 da NBR 6123; caixa usa "
        "C_a = 2,0, a não ser que você informe outro."
    ),
    "forcas_h": (
        "Outras forças horizontais características num piso (vibração de equipamento, tração de "
        "correia, impacto). Escolha a categoria: ela define γ e ψ. “Nos dois sentidos” trata a "
        "força como reversível."
    ),
    # ------------------------------------------------------------------ vento
    "v0": "Velocidade básica do vento V₀ no mapa de isopletas da NBR 6123:2023 (m/s).",
    "s1": "Fator topográfico S₁: 1,0 em terreno plano; 0,9 em vale protegido; acima de 1 em morro.",
    "categoria": (
        "Rugosidade do terreno em volta (NBR 6123, 5.3): II campo aberto; III subúrbio com "
        "obstáculos baixos; IV zona industrial ou urbana densa; V cidade grande."
    ),
    "grupo_s3": (
        "Grupo estatístico S₃ (Tabela 4): 3 = instalações industriais com baixo fator de "
        "ocupação; 2 = alto fator de ocupação; 1 = ruína afeta a segurança de muitos."
    ),
    # ------------------------------------------------------------------ contraventamento
    "mesmo_sistema": (
        "Ligado: o mesmo contraventamento e a mesma barra nas direções X e Y. Desligue para "
        "escolher cada direção."
    ),
    "tipo": (
        "**X só tração**: diagonais esbeltas, só a tracionada trabalha. **X tração e "
        "compressão**: as duas trabalham. **Diagonal simples**: uma por painel, que inverte de "
        "tração para compressão. **V invertido**: duas diagonais até o meio da viga."
    ),
    "linhas": (
        "Quantas linhas de pilares paralelas à direção recebem contraventamento (2 = as duas "
        "fachadas, o usual)."
    ),
    "paineis": "Quantos painéis (vãos) contraventados em cada uma dessas linhas, por andar.",
    "familia": (
        "Tipo da barra: cantoneira simples ligada por uma aba, tubo com chapa de nó num rasgo, ou "
        "barra redonda rosqueada (tirante, só para X só tração)."
    ),
    "perfil": "A bitola da barra. Cantoneiras em polegadas (aba × espessura).",
    "aco": "Aço da barra: dá f_y e f_u (ASTM A36: 250/400 MPa; A572 Gr 50: 345/450 MPa).",
    "ligacao": (
        "Como a barra se liga à chapa de nó: parafusos numa linha ou solda longitudinal. O tubo é "
        "sempre soldado."
    ),
    "parafuso": "Diâmetro dos parafusos da ligação da diagonal.",
    "grau": "Material dos parafusos: A325 (alta resistência) ou A307 (comum).",
    "n_parafusos": "Quantos parafusos numa linha, na direção da barra (no mínimo 2).",
    "passo": "Distância entre parafusos vizinhos (mm). A norma pede no mínimo 2,7 diâmetros.",
    "borda": "Distância do último furo à ponta da barra (mm). Mínimo da Tabela 16 da NBR 8800.",
    "rosca": "Ligado: a rosca passa no plano de corte (resistência menor, a favor da segurança).",
    "comp_solda": (
        "Comprimento de cada cordão de solda ao longo da barra (mm). Na cantoneira, dois cordões; "
        "no tubo, quatro."
    ),
    "perna_solda": "Perna (lado) do filete de solda (mm). Eletrodo E70.",
    "t_chapa": (
        "Espessura da chapa de nó (mm): entra no contato dos parafusos e no rasgo do tubo. A "
        "chapa em si se verifica na página Ligação de contraventamento."
    ),
    "aco_chapa": "Aço da chapa de nó: dá o f_u do contato dos parafusos.",
    # ------------------------------------------------------------------ ajustes
    "excentricidade": (
        "Desvio da força do vento em planta, em % da dimensão perpendicular (7,5 % é o valor da "
        "NBR 6123, 6.1.4). Com duas linhas, a mais carregada recebe 50 % + e."
    ),
    "cruzamento": (
        "Ligado: as diagonais do X são parafusadas uma na outra no cruzamento, e o comprimento "
        "destravado de cada metade é L/2."
    ),
    "comb_servico": (
        "Combinação usada nos deslocamentos (Anexo B): rara (vento característico, a favor da "
        "segurança) ou frequente (ψ₁ = 0,3 do vento)."
    ),
    "tipo_estrutura": (
        "Qual limite do deslocamento horizontal do topo sob vento vale aqui: o do critério Anglo "
        "(Tabela 4: plataformas de equipamentos H/400, pipe rack H/250, cobertura H/400) ou o da "
        "NBR 8800 (H/300 com um piso; H/400 e h/500 com dois ou mais)."
    ),
    "criterio_anglo": (
        "Acrescenta as exigências do critério Anglo: espessura mínima da cantoneira (4,75 mm), "
        'diâmetros mínimos de parafuso (5/8") e de tirante (1/2"), A325 nas ligações principais, '
        "ligação com no mínimo 75 % da tração da peça e 3 t, e a redução de comprimento da Tabela 5."
    ),
    "btn_recarregar": (
        "Descarta o que foi digitado no vento e volta aos valores da base técnica do projeto."
    ),
    # ------------------------------------------------------------------ resultados
    "res_status": "OK atende · NÃO OK reprova · ALERTA ressalva · INFO informação · N/A não se aplica.",
    "res_aproveitamento": (
        "Maior relação solicitante ÷ resistente entre as verificações de resistência das "
        "diagonais e ligações. Acima de 100 % alguma coisa reprova."
    ),
    "res_vento": "Força total do vento (característica) na direção, somada em todos os níveis.",
    "res_b2": (
        "B₂ mede o efeito de segunda ordem do andar. Até 1,10 é pequena deslocabilidade; até "
        "1,40, média (o programa amplifica as forças); acima, grande."
    ),
    "res_desloc": "Maior deslocamento horizontal do topo, em serviço, entre X e Y (mm).",
    "res_verificacoes": (
        "Cada verificação com o item da NBR 8800: diagonais (tração, compressão, esbeltez), "
        "ligação (parafusos, rasgamento, solda), deslocabilidade e deslocamentos."
    ),
    "so_atencao": "Mostra só o que reprova, tem ressalva ou não se aplica.",
    "res_exportar": "Baixar as verificações em CSV, para planilha ou conferência.",
    "btn_csv": "Baixa a tabela de verificações em CSV (UTF-8).",
    "res_vento_niveis": (
        "Força do vento em cada nível: pórticos (estrutura), guarda-corpos e equipamentos, com a "
        "pressão q da faixa."
    ),
    "res_vento_casos": (
        "Cada direção do vento levada aos pisos: a força em X e em Y em cada nível e o cortante "
        "de cada andar. A linha “base” é a parte de baixo do primeiro andar, que vai direto à "
        "fundação."
    ),
    "res_comparacao": (
        "O cortante de cada andar pelos pórticos regulares e viga a viga, para ver quanto a "
        "estrutura real se afasta da grade."
    ),
    "res_vento_3d": "A carga do vento em cada barra do esqueleto (kN/m), nesta direção.",
    "vb_ver": "Qual direção do vento desenhar.",
    "res_planos": (
        "Os planos de barras perpendiculares ao vento: área exposta, contorno, φ, C_a da Figura "
        "12 e o fator de proteção η (o de barlavento tem η = 1)."
    ),
    "btn_csv_barras": "Baixa a carga do vento em cada barra, por direção (kN/m), em CSV.",
    "btn_plano_barras": (
        "Grava os casos de vento (W0, W45 …) no plano de cargas, uma carga por metro em cada "
        "barra, prontos para o SolidWorks. Se já existirem, são substituídos."
    ),
    "res_porticos": (
        "Cada pórtico perpendicular ao vento: área exposta, φ, C_a da Figura 12 e o fator de "
        "proteção η da Figura 14 (o de barlavento tem η = 1)."
    ),
    "res_acoes": "As ações com a categoria e os coeficientes γ e ψ que entram nas combinações.",
    "res_andares": (
        "Para cada andar e direção: cortante de cálculo, a combinação que governa, B₂, forças na "
        "diagonal mais carregada e deslocamento em serviço."
    ),
    "res_lista": (
        "Todas as combinações explícitas (ELU normal, rara, frequente e quase permanente) e o "
        "cortante de cada andar nelas. A tabela de andares usa a envoltória rigorosa, que tira "
        "a ação variável que alivia."
    ),
    "res_ligacao": (
        "As forças de cálculo da diagonal mais solicitada e o ângulo com a vertical: é o que a "
        "chapa de nó precisa resistir."
    ),
    "btn_ligacao": (
        "Abre a página Ligação de contraventamento já com estas forças e o ângulo preenchidos."
    ),
    "res_avisos": "O que o programa avisa que não conferiu e deve ser visto no desenho.",
    "res_desenhos": (
        "Desenhos em escala gerados com os seus dados: a planta com as linhas contraventadas e a "
        "elevação da linha mais carregada com a força em cada diagonal (azul tração, vermelho "
        "compressão)."
    ),
    "desenho_direcao": "Qual direção desenhar na elevação e no vento.",
    "res_cortante": "Cortante de cálculo de cada andar (ELU, com a força nocional), por direção.",
    "res_nos": (
        "A força do vento em cada pórtico e nível, e a parcela de cada nó pilar–viga: é o que se "
        "lança no modelo (SolidWorks, Robot) como carga nodal. Valores característicos."
    ),
    "btn_plano": (
        "Grava W0, W90, W180 e W270 no plano de cargas do projeto, na forma escolhida acima. Se "
        "já existirem, são substituídas."
    ),
    "forma": "**Simplificada** (para estruturas simples): uma carga por nível, distribuída ao longo das vigas das linhas de pilares que vão na direção do vento — no SolidWorks, uma Força só por nível, selecionando essas vigas, com a direção ao longo delas. É a mesma carga dos nós espalhada na linha: a cota, a divisão entre as linhas contraventadas e o momento na base não mudam, e a viga não ganha flexão lateral. **Nos nós**: a força de cada pórtico em cada nível, nó a nó (para casos mais complicados).",
    "res_simplificada": "A carga de cada nível: o total do nível (estrutura e guarda-corpo) dividido pelas linhas de pilares na direção do vento e pelo comprimento delas. Selecione só as vigas dessas linhas (todos os trechos), não as secundárias. Os equipamentos continuam como força no centro deles.",
    "reg_registrar": (
        "Grava este cálculo no projeto ativo: entradas, tabelas e verificações. O memorial passa "
        "a trazer o contraventamento."
    ),
}
