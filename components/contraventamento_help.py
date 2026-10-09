"""Textos dos “?” (dicas) da página Ligação de contraventamento, em linguagem simples.

Ficam num módulo só para a página e os testes falarem do mesmo jeito e para um teste garantir que
nenhum campo fique sem explicação. Aceitam Markdown (negrito e listas). Cada texto diz, na ordem:
o que é, como preencher e — quando existir — a simplificação que o programa adota.
"""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções
    "sec_1": (
        "Dados do documento: obra, TAG da ligação, responsável e data. Não entram no cálculo; "
        "saem no registro do projeto e no memorial."
    ),
    "sec_2": (
        "A força que o contraventamento (a barra diagonal) puxa ou empurra o nó, o ângulo dela e "
        "o sistema de normas: **LRFD** (esforços já majorados) ou **ASD** (esforços de serviço)."
    ),
    "sec_3": (
        "A viga e a coluna que se encontram no nó. O programa precisa das medidas da seção I: "
        "altura, espessuras da alma e da mesa, largura da mesa, a distância **k** e as "
        "propriedades de flexão. Use o catálogo do programa (seção idealizada, sem raio de "
        "concordância) ou digite as medidas do catálogo do fabricante."
    ),
    "sec_4": (
        "Como as forças se dividem entre a chapa de nó, a viga e a coluna. O **Método das Forças "
        "Uniformes** (Design Guide 29 do AISC) escolhe as dimensões da chapa para que nenhuma "
        "das ligações fique com momento. Os **casos especiais** tratam o contraventamento que "
        "chega no canto da chapa, o que deve aliviar o cisalhamento da ligação viga–coluna e o "
        "que prende a chapa só na viga."
    ),
    "sec_5": (
        "A chapa de nó: espessura, aço e tamanho. Os comprimentos são medidos nas bordas "
        "soldadas, e o **corte** é o recorte do canto, que reduz o trecho de solda."
    ),
    "sec_6": (
        "Os parafusos que prendem o contraventamento à chapa: tipo, grau, quantidade e "
        "distâncias. As fileiras correm paralelas ao eixo da barra."
    ),
    "sec_7": (
        "Dados da **seção de Whitmore** (a faixa da chapa que trabalha, abrindo 30° a partir dos "
        "parafusos) e da flambagem da chapa quando o contraventamento comprime."
    ),
    "sec_8": (
        "A solda da chapa na viga e na coluna: eletrodo, perna (o lado do filete) e o fator de "
        "ductilidade que cobre a redistribuição de tensões."
    ),
    "sec_9": (
        "Opcional. A flexão que o pórtico faz na ligação viga–coluna quando o contraventamento "
        "se alonga (DG29, seção 4.4). Só entra se você informar a área da barra e os "
        "comprimentos b e c."
    ),
    "sec_simples": (
        "No modo simplificado você escolhe só o parafuso e o aço: o programa define o número de "
        "parafusos, a espessura e o tamanho da chapa e as soldas, e verifica tudo."
    ),
    "modo": (
        "**Simplificado**: você informa a força, o ângulo, a viga, a coluna e o parafuso; o "
        "programa dimensiona a chapa de nó (parafusos, espessura, comprimentos sem momento nas "
        "interfaces e soldas). **Completo**: você informa todas as medidas, para conferir um "
        "desenho pronto."
    ),
    "res_dimensoes": (
        "O que o programa escolheu no modo simplificado e por quê. É um ponto de partida que "
        "fecha nas verificações; leve as medidas para o desenho e confira."
    ),
    # ------------------------------------------------------------------ identificação
    "obra": "Nome da obra ou do projeto, só para identificar o documento.",
    "tag": "Código da ligação no desenho (por exemplo, LC-12). Sai no registro e no memorial.",
    "responsavel": "Quem calculou ou conferiu. Sai no registro e no memorial.",
    "data": "Data do cálculo. Sai no registro e no memorial.",
    # ------------------------------------------------------------------ força
    "metodo": (
        "**LRFD**: as forças já vêm majoradas (combinações últimas) e a resistência é φ·R_n. "
        "**ASD**: as forças são de serviço e a resistência é R_n/Ω. Use as forças do mesmo "
        "sistema do método escolhido."
    ),
    "P_tracao": (
        "Força de **tração** no contraventamento (kN), de cálculo. Use 0 se a barra só "
        "comprime. Se vier do módulo do vento, divida a horizontal por sen θ."
    ),
    "P_compressao": (
        "Força de **compressão** no contraventamento (kN), de cálculo. Use 0 se a barra só "
        "traciona. A compressão exige a verificação de flambagem da chapa."
    ),
    "theta": (
        "Ângulo da barra com a **vertical**, em graus. Uma barra a 45° tem θ = 45°. Quanto "
        "mais próxima da vertical, maior a parcela de força vertical no nó."
    ),
    "calc_P": (
        "Atalho: converte a força **horizontal** que o contraventamento recebe (vento ou "
        "sismo) na força **axial da barra**, P = H / sen θ. Copie o resultado para o campo "
        "de tração ou de compressão."
    ),
    "H_horizontal": "Força horizontal que o contraventamento deve levar ao nó, em kN.",
    "reacao_viga": (
        "Cisalhamento da viga no nó (reação de apoio, kN), sem o contraventamento. Soma-se ao "
        "cisalhamento que a chapa devolve à viga."
    ),
    "transferencia": (
        "Força axial que a viga traz ao nó (kN), por exemplo o arrastamento de um diafragma. "
        "É o H′ do guia, o que passa direto da viga à coluna. Zero se não houver."
    ),
    # ------------------------------------------------------------------ perfis
    "perfil_origem": (
        "**Digitar** usa as medidas que você informar (recomendado, do catálogo do fabricante). "
        "**Catálogo do programa** usa a seção idealizada do I (sem raio de concordância); só "
        "informe o k."
    ),
    "perfil_catalogo": "Perfil I ou W do catálogo do programa. A seção é idealizada, sem raios.",
    "perfil_nome": "Nome do perfil, só para o relatório (por exemplo, W 530 × 85).",
    "aco_perfil": (
        "Aço do perfil. Dá o limite de escoamento F_y e a resistência à ruptura F_u (ASTM "
        "A992 ≈ MR 250 / ASTM A572 Gr 50 ≈ AR 350)."
    ),
    "d": "Altura total do perfil, de uma face externa da mesa à outra (mm).",
    "tw": "Espessura da alma (mm).",
    "tf": "Espessura da mesa (mm).",
    "bf": "Largura da mesa (mm).",
    "k": (
        "Distância da face externa da mesa ao pé do raio de concordância na alma (mm). Está nas "
        "tabelas do perfil como **k** (≈ t_f + raio). Entra no escoamento local e no "
        "enrugamento da alma."
    ),
    "Zx": "Módulo plástico em torno do eixo de maior inércia (cm³). Está na tabela do perfil.",
    "Ix": "Momento de inércia em torno do eixo de maior inércia (cm⁴). Está na tabela do perfil.",
    "mesa_coluna": (
        "Ligado: a chapa é soldada na **mesa** da coluna (e_c = d/2 da coluna). Desligado: na "
        "**alma** da coluna (e_c = 0)."
    ),
    # ------------------------------------------------------------------ UFM
    "caso": (
        "**Geral**: o ponto de trabalho fica no cruzamento dos eixos da viga e da coluna. "
        "**Especial 1**: ele fica no canto da chapa. **Especial 2**: você tira cisalhamento "
        "da ligação viga–coluna. **Especial 3**: a chapa liga só à viga (θ grande, perto de "
        "60° ou mais)."
    ),
    "ajuste": (
        "Qual das duas ligações o programa ajusta para eliminar o momento: mantém β e acerta α "
        "(a ligação à coluna é a mais flexível), mantém α e acerta β, ou distribui o binário "
        "para minimizar as excentricidades."
    ),
    "x_mm": (
        "Caso especial 1: posição do ponto de trabalho em relação ao canto da chapa (mm), "
        "medida na direção da viga."
    ),
    "y_mm": (
        "Caso especial 1: posição do ponto de trabalho em relação ao canto da chapa (mm), "
        "medida na direção da coluna."
    ),
    "anular_Vb": (
        "Caso especial 2: ligado, **toda** a componente vertical da viga é levada pela chapa, "
        "e a ligação viga–coluna fica sem cisalhamento do contraventamento."
    ),
    "delta_Vb": (
        "Caso especial 2: quanto de cisalhamento (kN) você tira da ligação viga–coluna e "
        "passa para a chapa."
    ),
    # ------------------------------------------------------------------ chapa
    "aco_chapa": "Aço da chapa de nó: dá F_y e F_u.",
    "t_chapa": "Espessura da chapa de nó (mm).",
    "lh": (
        "Comprimento da chapa ao longo da **viga** (mm), medido pela borda soldada. Deve ser "
        "pelo menos o comprimento necessário para o α̅ ideal, mostrado nos resultados."
    ),
    "corte_h": "Recorte (mm) no canto da chapa na borda da viga; reduz o trecho de solda.",
    "lv": "Comprimento da chapa ao longo da **coluna** (mm), medido pela borda soldada.",
    "corte_v": "Recorte (mm) no canto da chapa na borda da coluna; reduz o trecho de solda.",
    "t_topo": (
        "Espessura (mm) da chapa de topo da viga, se houver (zero se a viga é soldada direto). "
        "Entra na posição do centroide da solda na viga (α real)."
    ),
    # ------------------------------------------------------------------ parafusos
    "parafuso": "Diâmetro do parafuso. Define o furo, o espaçamento mínimo e as resistências.",
    "grau": "Material do parafuso: A325, A490 ou A307 (resistência à tração e ao corte).",
    "rosca": (
        "Ligado: a rosca está no plano de corte (menor resistência ao corte). Desligado: a "
        "rosca fica fora do plano de corte."
    ),
    "planos": "Quantos planos de corte o parafuso atravessa: 1 (chapa simples) ou 2 (dupla).",
    "fileiras": "Número de fileiras paralelas ao eixo da barra.",
    "por_fileira": "Número de parafusos em cada fileira.",
    "passo": "Distância entre parafusos na mesma fileira (mm), no sentido da força.",
    "gabarito": "Distância entre as fileiras (mm), no sentido transversal.",
    "extremidade": "Distância do último parafuso à borda da chapa (mm), no sentido da força.",
    "t_barra": (
        "Espessura da barra do contraventamento ou da cantoneira (mm). Com o F_u da barra, "
        "entra na pressão de contato da barra; zero ignora essa verificação."
    ),
    "Fu_barra": "Resistência à ruptura F_u do aço da barra do contraventamento (MPa).",
    "extremidade_barra": (
        "Distância do primeiro parafuso à ponta da barra (mm). Zero adota a mesma distância da "
        "chapa."
    ),
    # ------------------------------------------------------------------ Whitmore e flambagem
    "L_flamb": (
        "Comprimento livre da chapa (mm) usado na flambagem com compressão, do último parafuso "
        "ao canto da viga ou coluna. Zero adota metade do comprimento do grupo de parafusos."
    ),
    "K_flamb": (
        "Fator K de comprimento efetivo da chapa. 0,5 vale para chapa travada nas duas pontas "
        "(DG29 pág. 6); use 0,65 ou 1,0 se houver dúvida."
    ),
    "trecho_alma": (
        "Parte (mm) da seção de Whitmore que cai sobre a **alma** da viga ou da coluna, quando "
        "a chapa entra nela. Zero ignora. Aumenta a área que resiste."
    ),
    # ------------------------------------------------------------------ solda
    "FEXX": (
        "Resistência do eletrodo (MPa). E70XX = 482,6 MPa (70 ksi); E60XX = 413,7 MPa. Dá a "
        "resistência da solda de filete."
    ),
    "perna_viga": "Perna do filete na ligação da chapa com a viga (mm).",
    "perna_coluna": "Perna do filete na ligação da chapa com a coluna (mm).",
    "ductilidade": (
        "Multiplicador da força da solda para cobrir a redistribuição de tensões (Manual do "
        "AISC, Parte 13). 1,25 é o valor do guia; use 1,0 só com justificativa."
    ),
    # ------------------------------------------------------------------ distorção
    "distorcao": (
        "Liga o cálculo das forças extras da ligação viga–coluna quando o pórtico se "
        "deforma com o contraventamento (DG29 seção 4.4)."
    ),
    "area_barra": "Área da seção do contraventamento (mm²), para o alongamento da barra.",
    "b_viga": "Comprimento b da viga até o ponto de inflexão, o meio do vão (mm).",
    "c_coluna": "Comprimento c da coluna até o ponto de inflexão, o meio da altura (mm).",
    # ------------------------------------------------------------------ resultados
    "res_status": "OK atende · NÃO OK reprova · ALERTA ressalva · INFO informação · N/A não se aplica.",
    "res_aproveitamento": (
        "Maior relação solicitante ÷ resistente entre todas as verificações de resistência. "
        "Acima de 100 % o conjunto reprova."
    ),
    "res_forcas": "Forças de cálculo em cada interface do nó (a Tabela 5-1 do guia).",
    "res_geometria": "Posições, comprimentos de solda, Whitmore e quantidade mínima de parafusos.",
    "res_verificacoes": (
        "Cada estado-limite do AISC 360-16 (parafusos, chapa, solda, viga e coluna) com a "
        "referência da norma. A tabela inclui as verificações de resistência e os avisos."
    ),
    "so_atencao": "Mostra só o que reprova, tem ressalva ou não se aplica.",
    "res_exportar": "Baixar as verificações em CSV, para planilha ou conferência.",
    "btn_csv": "Baixa a tabela de verificações em CSV (separador ponto e vírgula, UTF-8).",
    "res_avisos": "O que o programa avisa que não conferiu e deve ser visto no desenho.",
    "reg_registrar": (
        "Grava este cálculo no projeto ativo: entradas, tabelas e verificações. O memorial e "
        "o relatório do projeto passam a trazer a ligação."
    ),
}
