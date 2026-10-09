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
        "Categoria do peso dos equipamentos: o Projeto de 2024 junta equipamentos com a estrutura "
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
    "reg_registrar": (
        "Grava este cálculo no projeto ativo: entradas, tabelas e verificações. O memorial passa "
        "a trazer o contraventamento."
    ),
}
