"""Textos dos “?” da página Ligações estruturais, em linguagem simples (um teste exige cada um)."""

AJUDA: dict[str, str] = {
    "tipo": (
        "Qual ligação calcular: a chapa simples ou a dupla cantoneira que liga uma viga em outra "
        "viga ou num pilar (NBR 8800), a ligação parafusada de um perfil dobrado de chapa fina "
        "(NBR 14762), um grupo de filetes no plano, a barra (cantoneira ou tala) soldada na chapa "
        "de nó, ou uma chapa soldada num apoio com filete ou solda de penetração."
    ),
    "norma": (
        "Versão da NBR 8800. A 2025 é a vigente; a 2008 serve para conferir projetos antigos. "
        "Na 2025 o corte do parafuso usa 0,45 e 0,56 (0,40 e 0,50 na 2008)."
    ),
    "exemplo": (
        "Quatro exemplos resolvidos de solda: duas talas sobrepostas, chapa com filete "
        "intermitente, chapa com penetração total e a cantoneira de contraventamento soldada na "
        "chapa de nó e no pilar. Escolha um e clique em Preencher."
    ),
    "preencher_exemplo": (
        "Troca o tipo de ligação e preenche os campos com o exemplo escolhido. Os outros campos "
        "ficam como estão; confira tudo antes de usar o resultado."
    ),
    # ------------------------------------------------------------------ chapa simples
    "sec_viga": "A viga que chega na ligação (a apoiada) e onde ela se apoia.",
    "perfil": "O perfil da viga apoiada; a alma dela recebe os parafusos.",
    "aco_viga": "O aço da viga apoiada.",
    "apoio": (
        "Onde a chapa é soldada: na alma de outra viga (viga–viga) ou no pilar, na mesa ou na "
        "alma (viga–pilar)."
    ),
    "t_apoio": (
        "Espessura da parte em que a chapa é soldada (alma da viga principal ou mesa/alma do "
        "pilar), em mm. Entra na perna mínima da solda e no cisalhamento junto à solda."
    ),
    "recorte": (
        "Ligue quando a mesa de cima da viga apoiada é cortada para encaixar na viga principal "
        "(as duas no mesmo nível). Aparecem o colapso por rasgamento e a flexão da alma recortada."
    ),
    "recorte_altura": "Altura do corte na ponta da viga, medida do topo da viga, em mm.",
    "recorte_comprimento": "Comprimento do corte ao longo da viga, a partir da ponta, em mm.",
    "sec_parafusos": "Os parafusos da chapa: diâmetro, grau, quantidade e posição dos furos.",
    "parafuso": "Diâmetro do parafuso; o furo-padrão e a distância mínima à borda vêm dele.",
    "grau": "Grau do parafuso: A325 (alta resistência), A490 ou A307 (comum).",
    "rosca": (
        "Ligado: a rosca fica no plano de corte (o mais comum e a favor da segurança). "
        "Desligado: só a parte lisa do corpo passa pelo plano de corte, e o parafuso resiste mais."
    ),
    "n_parafusos": "Quantos parafusos na linha vertical da chapa.",
    "passo": "Distância entre os centros de dois parafusos vizinhos, em mm (3 diâmetros é o usual).",
    "borda_vertical": "Do centro do furo de cima (e do de baixo) até a borda da chapa, em mm.",
    "a": (
        "Distância da solda (face do apoio) até a linha dos parafusos, em mm. Ela cria o momento "
        "V·a que os parafusos, a chapa e a solda precisam resistir."
    ),
    "borda_horizontal": "Do centro dos furos até a borda livre da chapa, em mm.",
    "borda_alma": "Do centro dos furos até a ponta da viga apoiada, em mm.",
    "topo_alma": (
        "Do centro do parafuso de cima até o topo da alma: o fundo do recorte, ou a face de "
        "baixo da mesa quando não há recorte, em mm."
    ),
    "sec_chapa": "A chapa de ligação e a solda dela no apoio.",
    "t_chapa": "Espessura da chapa de ligação, em mm.",
    "aco_chapa": "O aço da chapa de ligação.",
    "perna": "Tamanho da perna do filete de solda, em mm (os dois lados da chapa).",
    "eletrodo": "Classe do eletrodo: E70 (485 MPa) é o usual; E60 tem 415 MPa.",
    "sec_esforcos": "Os esforços de cálculo (já majorados, combinação ELU) que chegam na ligação.",
    "origem": (
        "Reações de cálculo dos cálculos já registrados no projeto ativo — vigas de piso (a de "
        "cálculo e, com o Anglo, a mínima da ligação) e longarinas da escada (cada apoio, ELU) — "
        "e as pontas das vigas e diagonais do modelo do SolidWorks importado em Esforços do "
        "modelo: em cada ponta, a combinação ELU com o maior cortante no plano da alma e o "
        "normal junto. Quando a ponta tem momento, ele aparece no rótulo: a junta do modelo é "
        "rígida e a ligação flexível não o leva."
    ),
    "usar_reacao": (
        "Copia a reação escolhida para V_Sd e N_Sd (a horizontal da longarina vira N_Sd). Dá "
        "para ajustar os números depois."
    ),
    "v_sd": "Força cortante de cálculo na ponta da viga (a reação ELU), em kN.",
    "n_sd": (
        "Força normal de cálculo na viga, em kN: positiva se puxa (tração), negativa se empurra. "
        "Deixe 0 se não houver."
    ),
    "anglo": "Acrescenta as exigências do critério Anglo American para parafusos (item 9.1).",
    # ------------------------------------------------------------------ dupla cantoneira
    "sec_cantoneiras": (
        "As duas cantoneiras, uma de cada lado da alma da viga, e os parafusos: os da alma "
        "trabalham com dois planos de corte, os do apoio com um."
    ),
    "cantoneira": "O tamanho das cantoneiras (aba × espessura), iguais dos dois lados.",
    "aco_cantoneira": "O aço das cantoneiras.",
    "aco_apoio": "O aço do apoio (alma da viga principal ou pilar), para o contato dos parafusos.",
    "comprimento_cantoneira": (
        "Altura das cantoneiras ao longo da alma, em mm: precisa caber os furos e caber na alma "
        "livre da viga."
    ),
    "gabarito_alma": (
        "Da quina da cantoneira (face do apoio) até os furos da alma, em mm. Cria o momento V·g "
        "nos parafusos da alma."
    ),
    "gabarito_apoio": "Da quina da cantoneira até os furos que vão no apoio, em mm.",
    # ------------------------------------------------------------------ perfil formado a frio
    "sec_perfil_frio": "O perfil dobrado ligado pela alma e a chapa em que ele se apoia.",
    "perfil_frio": (
        "O perfil dobrado do catálogo, ou “Informado à mão” para digitar espessura, área e x̄ "
        "(por exemplo um U simples que não está no catálogo)."
    ),
    "t_perfil": "Espessura da chapa do perfil, em mm.",
    "area_perfil": "Área da seção do perfil, em mm².",
    "x_perfil": (
        "x̄: distância do centroide do perfil até a face da alma que encosta na chapa, em mm. "
        "Quanto maior, menos eficiente é a ligação só pela alma (C_t menor)."
    ),
    "aco_perfil": "O aço do perfil (os da NBR 14762 Tabela 1, ou sem qualificação estrutural).",
    "t_chapa_frio": (
        "Espessura da chapa (ou cantoneira) que recebe o perfil, em mm. Acima de 4,75 mm ela é "
        "verificada pela NBR 8800."
    ),
    "aco_chapa_frio": "O aço da chapa que recebe o perfil.",
    "sec_parafusos_frio": "Os parafusos e a grade de furos na alma do perfil.",
    "especificacao": (
        "Especificação do parafuso (NBR 14762 Tabela 16). “Sem qualificação estrutural” usa no "
        "máximo 300 MPa de ruptura."
    ),
    "planos": "Quantos planos de corte cada parafuso atravessa: 1 (uma chapa) ou 2 (perfil entre duas chapas).",
    "n_linhas": "Quantas linhas de parafusos, lado a lado, na direção da barra.",
    "n_por_linha": "Quantos parafusos em cada linha, um atrás do outro na direção da barra.",
    "passo_frio": "Distância entre centros de parafusos na direção da barra, em mm.",
    "gabarito": "Distância entre as linhas de parafusos, em mm.",
    "borda_frio": "Do centro do último furo até a ponta do perfil, na direção da barra, em mm.",
    "borda_lateral": "Do centro do furo até a borda da alma (ou da dobra), na outra direção, em mm.",
    "n_sd_frio": "Força axial de cálculo na barra, em kN: positiva na tração, negativa na compressão.",
    "v_sd_frio": "Força de cálculo perpendicular à barra, no plano da ligação, em kN (0 se não houver).",
    "barra_axial": (
        "Ligue para barra de treliça ou contraventamento: a norma pede que a ligação resista a "
        "pelo menos 50 % da força axial que a barra resiste (NBR 14762 10.1)."
    ),
    "n_rd_barra": (
        "Força axial resistente de cálculo da barra, em kN, para a regra dos 50 %. Vazio: a "
        "tração calculada aqui (na compressão, informe a resistência à compressão da barra)."
    ),
    # ------------------------------------------------------------------ solda
    "sec_solda": (
        "O grupo de filetes no mesmo plano, com a carga nesse plano: o desenho do grupo, a perna, "
        "as chapas soldadas, a norma e o método."
    ),
    "norma_solda": (
        "Versão da NBR 8800. A 2025 é a vigente; a 2008 serve para conferir projetos antigos. "
        "As regras das soldas são as mesmas; a 2025 muda o número das tabelas (resistência na "
        "Tabela 9, perna mínima na Tabela 11). Item que ainda não foi conferido no texto da 2025 "
        'sai com "(a confirmar)" na referência.'
    ),
    "combinacao": (
        "A combinação de ações das forças de cálculo. Normal, especial ou de construção: γ_a1 = "
        "1,10, γ_a2 = 1,35 e γ_w2 = 1,35. Excepcional (incêndio, explosão, choque): 1,00, 1,15 e "
        "1,15."
    ),
    "metodo_solda": (
        "Pela direção da força: a norma deixa somar resistência quando a força cruza o filete "
        "(até 50 % a 90°) e, com momento, usa o centro instantâneo de rotação — o resultado mais "
        "econômico permitido. Elástico: sem esse aumento, a favor da segurança (o cálculo antigo "
        "de mão)."
    ),
    "arranjo": (
        "Como os filetes estão: um filete vertical, dois verticais paralelos, dois horizontais "
        "(em cima e embaixo), três lados em C ou o contorno de um retângulo."
    ),
    "comprimento_solda": (
        "A altura do grupo (na direção da força V), em mm: o comprimento dos filetes verticais, "
        "ou a distância entre os dois horizontais."
    ),
    "largura_solda": (
        "A largura do grupo, em mm: a distância entre os filetes verticais paralelos ou o "
        "comprimento dos filetes horizontais."
    ),
    "perna_solda": "Tamanho da perna do filete, em mm.",
    "t1": "Espessura da chapa soldada (a solda corre na borda dela), em mm.",
    "t2": "Espessura da peça que recebe a solda, em mm.",
    "aco_solda": "O aço das chapas soldadas (o mais fraco dos dois).",
    "v_solda": "Força de cálculo ao longo dos filetes verticais, em kN.",
    "n_solda": "Força de cálculo perpendicular aos filetes verticais, no plano, em kN.",
    "m_solda": "Momento de cálculo no plano do grupo de solda (torção do grupo), em kN·m.",
    # ------------------------------------------------------------------ barra soldada
    "sec_barra": (
        "A barra que chega (cantoneira ou tala de chapa), a chapa de nó em que ela é soldada e o "
        "que o programa deve fazer: achar os comprimentos dos filetes ou verificar os que você "
        "der."
    ),
    "modo": (
        "Dimensionar: o programa acha os comprimentos dos filetes (e da solda no apoio), "
        "arredondados para cima, e verifica tudo com eles. Verificar: você dá os comprimentos."
    ),
    "peca": (
        "Cantoneira ligada por uma aba (o caso do contraventamento) ou chapa sobreposta (tala). "
        "Os filetes correm nas duas bordas da parte ligada."
    ),
    "cantoneira_barra": (
        "A cantoneira de abas iguais do catálogo; a área, a espessura e a posição do centro "
        "geométrico (x̄, do dorso) vêm dela."
    ),
    "largura_barra": "Largura da tala, em mm: é a distância entre os dois filetes das bordas.",
    "t_barra": "Espessura da tala, em mm.",
    "aco_barra": "O aço da barra (cantoneira ou tala).",
    "duas_pecas": (
        "Ligue quando há uma peça de cada lado da chapa de nó (dupla cantoneira, duas talas): a "
        "força se divide entre as duas e a chapa de nó recebe os filetes dos dois lados nas "
        "mesmas linhas."
    ),
    "t_no": "Espessura da chapa de nó (gusset), em mm.",
    "aco_no": "O aço da chapa de nó.",
    "largura_no": (
        "A largura real da chapa de nó na ponta da barra, em mm. A seção de Whitmore (a faixa que "
        "trabalha, aberta a 30°) não pode passar dela. Zero: a chapa é larga o bastante e vale a "
        "seção de Whitmore inteira."
    ),
    "sec_filetes_barra": (
        "Os filetes longitudinais nas duas bordas da parte ligada — o do dorso (lado do canto da "
        "cantoneira) e o da borda —, a perna e o filete opcional na ponta da barra."
    ),
    "perna_barra": (
        "Perna dos filetes da barra, em mm. Mínimo pela parte mais fina (Tabela 11 da 2025); "
        "máximo ao longo da borda: a espessura menos 1,5 mm."
    ),
    "distribuicao": (
        "Balanceada: o filete do dorso é mais longo, para o centro da solda cair no eixo da barra "
        "(sem excentricidade). Iguais: os dois do mesmo tamanho — a norma permite em cantoneira "
        "sem fadiga, desprezando a excentricidade (6.1.8.2). Na tala os dois são iguais."
    ),
    "solda_na_ponta": (
        "Ligue para soldar também a ponta da barra (filete transversal). Ele ajuda a resistir e "
        "encurta os filetes longitudinais (6.2.5.2 c)."
    ),
    "l_dorso": "No modo verificar: comprimento do filete do dorso, em mm.",
    "l_borda": "No modo verificar: comprimento do filete da borda, em mm.",
    "cobrimento": (
        "Quanto a barra entra sobre a chapa de nó, em mm. A norma pede pelo menos 5 vezes a "
        "espessura da parte mais fina e 25 mm. Zero: é o maior filete."
    ),
    "passo_arredondamento": (
        "Os comprimentos achados são arredondados para cima neste passo, em mm (5 mm é o usual "
        "de desenho)."
    ),
    "sec_esforcos_barra": (
        "As forças de cálculo (combinação ELU) na barra, positivas. A ligação usa a maior, com os "
        "mínimos ligados aqui."
    ),
    "n_t_barra": "Tração de cálculo na barra, em kN (zero quando a barra só comprime).",
    "n_c_barra": (
        "Compressão de cálculo na barra, em kN. Com compressão, a chapa de nó também é "
        "verificada à flambagem na seção de Whitmore."
    ),
    "minimo_45": (
        "A norma manda dimensionar a ligação para pelo menos 45 kN quando a força é menor "
        "(6.1.5.2). Desligue só nas exceções: travejamento de barras compostas, tirantes de barra "
        "redonda, travessas de fechamento e terças."
    ),
    "anglo_barra": (
        "Critério Anglo American (9.1): a ligação de treliça ou contraventamento resiste a pelo "
        "menos 75 % da tração resistente da barra e a 3 t."
    ),
    "k_no": (
        "Coeficiente de flambagem da chapa de nó comprimida. 0,65 é o usual para a chapa de canto "
        "presa à viga e ao pilar (Thornton, AISC Manual Parte 9). Para a chapa presa só por um "
        "lado, que pode se deslocar para fora do plano, use valor maior (1,2 ou mais)."
    ),
    "l_livre_no": (
        "Comprimento da chapa de nó sem apoio, na direção da barra, da ponta da barra até o "
        "apoio, em mm."
    ),
    "sec_apoio_barra": (
        "A chapa de nó soldada no apoio (pilar, viga ou outra chapa) com dois filetes, um de "
        "cada lado. A força da barra chega inclinada: uma parte ao longo da solda e outra puxando "
        "(ou empurrando) a chapa contra o apoio."
    ),
    "com_apoio": "Ligue para verificar (ou dimensionar) também a solda da chapa de nó no apoio.",
    "theta": (
        "Ângulo entre o eixo da barra e a linha da solda no apoio, em graus. 90°: a barra puxa "
        "na perpendicular do apoio; 0°: ao longo dele."
    ),
    "l_apoio": (
        "Comprimento de cada filete da chapa de nó no apoio, em mm. No modo dimensionar é o "
        "comprimento disponível: o programa acha o menor que passa."
    ),
    "perna_apoio": "Perna dos dois filetes da chapa de nó no apoio, em mm.",
    "excentricidade": (
        "Distância, ao longo da solda, do meio da solda até onde o eixo da barra encontra o "
        "apoio, em mm. Zero: o eixo passa pelo meio. Com excentricidade, aparece momento na solda."
    ),
    # ------------------------------------------------------------------ apoio da chapa soldada
    "apoio_solda": (
        "Onde a chapa é soldada: uma chapa ou peça qualquer (só o metal-base junto à solda) ou a "
        "mesa de um perfil I ou H, que também verifica a mesa e a alma sob a força normal "
        "(NBR 8800 5.7)."
    ),
    "t_apoio_solda": "Espessura da parte em que a solda é feita, em mm (com perfil, vem a mesa).",
    "aco_apoio_solda": "O aço do apoio em que a chapa é soldada.",
    "perfil_apoio": "O perfil I ou H do catálogo, quando a chapa é soldada na mesa dele.",
    "orientacao": (
        "Chapa ao longo do eixo do perfil (como a chapa de nó numa coluna) ou atravessando a mesa "
        "(como um enrijecedor). Muda o trecho da mesa que recebe a força."
    ),
    "perto_extremidade": (
        "Ligue quando a chapa fica perto da ponta do perfil do apoio (a menos da altura dele): a "
        "mesa e a alma resistem menos."
    ),
    # ------------------------------------------------------------------ chapa soldada no apoio
    "sec_chapa_apoio": (
        "A solda da chapa no apoio (junta em T): filete, penetração total ou parcial, de um ou "
        "dos dois lados, contínua ou intermitente."
    ),
    "modo_chapa": (
        "Dimensionar: o programa acha o comprimento da solda (ou quantos segmentos do filete "
        "intermitente) dentro do comprimento da junta. Verificar: a solda ocupa o que você der."
    ),
    "tipo_solda": (
        "Filete: o cordão de canto, o mais comum. Penetração total: a solda ocupa a espessura "
        "toda da chapa e resiste como ela. Penetração parcial: chanfro só em parte da espessura."
    ),
    "lados": "Solda dos dois lados da chapa (o usual) ou de um lado só.",
    "perna_chapa": ("Perna do filete, em mm. O mínimo vem da parte mais fina (Tabela 11 da 2025)."),
    "profundidade": (
        "Profundidade do chanfro S da penetração parcial, em mm, em cada lado soldado. A "
        "garganta mínima vem da Tabela 10 da 2025."
    ),
    "menos_3mm": (
        "Ligue quando a garganta efetiva é a profundidade do chanfro menos 3 mm: chanfro em "
        "bisel de 45° com eletrodo revestido em qualquer posição, ou com arame (MIG/MAG, arame "
        "tubular) na vertical ou sobrecabeça (Tabela 5 da 2008)."
    ),
    "intermitente": (
        "Filete em segmentos, com intervalos. A norma só deixa usar quando a solda contínua de "
        "perna mínima já resistiria mais que o necessário; cada segmento tem pelo menos 4 pernas "
        "e 40 mm."
    ),
    "segmento": "Comprimento de cada segmento do filete intermitente, em mm.",
    "n_segmentos": (
        "No modo verificar: quantos segmentos em cada linha de solda, distribuídos por igual no "
        "comprimento da junta."
    ),
    "sec_chapa_e_apoio": "A chapa soldada, o comprimento da junta e o apoio que a recebe.",
    "t_chapa_apoio": "Espessura da chapa soldada, em mm.",
    "aco_chapa_apoio": "O aço da chapa soldada.",
    "comprimento_junta": (
        "O comprimento da borda da chapa encostada no apoio, em mm. No modo dimensionar é o "
        "máximo que a solda pode ocupar."
    ),
    "sec_esforcos_chapa": (
        "As forças de cálculo (combinação ELU) que a chapa leva ao apoio. Com momento, a solda é "
        "calculada pelo método elástico."
    ),
    "n_chapa": "Força perpendicular à face do apoio, em kN: positiva puxa a chapa, negativa empurra.",
    "v_chapa": "Força ao longo da solda, em kN.",
    "m_chapa": "Momento no plano da chapa, em kN·m (abre um lado da solda e fecha o outro).",
    # ------------------------------------------------------------------ resultados
    "res_status": "OK: tudo passa. NÃO OK: alguma verificação reprova. ALERTA: ressalva para conferir.",
    "res_aproveitamento": "A maior razão solicitante ÷ resistente entre as verificações; até 100 % passa.",
    "res_governa": "A verificação com o maior aproveitamento: é ela que define a ligação.",
    "res_figura": "O desenho da ligação com as medidas informadas, para conferir antes de olhar os números.",
    "res_verificacoes": "Todas as verificações, com a norma e o item, os valores e a situação.",
    "res_adotado": (
        "O que o cálculo adotou ou pede: comprimentos dos filetes, a seção de Whitmore da chapa "
        "de nó, a perna necessária. São esses que vão para o desenho."
    ),
    "btn_csv": "Baixa a tabela de verificações para abrir no Excel.",
    "sec_memorial": (
        "O memorial só desta ligação, no padrão do memorial do projeto: dados, verificações com "
        "a norma e o item, a figura e o que não passou."
    ),
    "btn_memorial_word": (
        "Gera o memorial desta ligação em Word, para editar. Com projeto ativo, a capa leva os "
        "dados dele."
    ),
    "btn_memorial_pdf": "Gera o memorial desta ligação em PDF, pronto para enviar.",
    "reg_registrar": "Grava esta ligação no projeto ativo; ela entra no memorial com a figura e as verificações.",
}
