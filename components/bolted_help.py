"""Textos dos “?” (dicas) da página Projeto de parafusos, em linguagem simples.

Ficam num módulo só para o modo mecânico e o estrutural falarem do mesmo jeito e para um
teste garantir que nenhum campo fique sem explicação. Aceitam Markdown (negrito e listas).
Cada texto diz, na ordem: o que é, como preencher e — quando existir — a simplificação que o
programa adota.
"""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # ------------------------------------------------------------------ seções (modo estrutural)
    "sec_est_1": (
        "Escolha a norma e o parafuso. Não sabe o diâmetro? Deixe qualquer um e clique em "
        "**Testar todos os parafusos**, nos resultados: o programa mostra o menor que atende."
    ),
    "sec_est_2": (
        "Descreva as chapas ligadas e onde ficam os furos. Meça sempre do **centro** do furo.\n\n"
        "**Simplificação:** os furos são tratados como furo-padrão e a chapa mais fina governa o "
        "contato e o rasgamento."
    ),
    "sec_est_3": (
        "Informe as forças que a ligação transmite, no centro do grupo de parafusos.\n\n"
        "**Simplificação:** o grupo é analisado pelo método elástico (cada parafuso recebe a "
        "força direta mais a parcela do momento, proporcional à sua distância ao centro), que é "
        "conservador."
    ),
    "sec_est_4": (
        "Atrito entre as chapas, instalação do parafuso e o que esta verificação não cobre."
    ),
    "sec_est_5": (
        "Só preencha se a peça ligada também trabalha à **tração** (ex.: diagonal de treliça ou "
        "contraventamento) ou se a regra dos 75% da Anglo se aplica. Pode deixar em branco nas "
        "emendas de viga."
    ),
    "sec_est_6": (
        "Exigências do critério de projeto da Anglo American para parafusos estruturais "
        "(item 9.1): mínimo de 2 parafusos, A325 galvanizado a fogo nas ligações principais, "
        "diâmetro até 1″ e a regra dos 75% para peças de treliça e contraventamento."
    ),
    # ------------------------------------------------------------------ 1. norma e parafuso
    "norma": (
        "Define as regras (fórmulas e coeficientes) da verificação. Cada norma calcula de um jeito "
        "um pouco diferente.\n\n"
        "Na dúvida, comece pela **NBR 8800:2008** e use **Comparar normas**, nos resultados, para "
        "ver como a mesma ligação ficaria nas outras."
    ),
    "parafuso": (
        "Diâmetro do parafuso. **M22** é um parafuso métrico de 22 mm; as medidas em polegadas "
        "(ex.: 7/8″) vêm das normas americanas.\n\n"
        "Não sabe qual usar? Escolha qualquer um e clique em **Testar todos os parafusos**."
    ),
    "grau": (
        "Tipo de aço do parafuso:\n\n"
        "- **A325**: alta resistência. É o padrão das ligações estruturais e o exigido pela Anglo "
        "nas ligações principais.\n"
        "- **A490**: ainda mais resistente. Não pode ser galvanizado a fogo.\n"
        "- **A307**: comum, de baixa resistência. Só serve para ligações secundárias, sem atrito, "
        "porque não admite o aperto controlado (protensão)."
    ),
    "planos_corte": (
        "Quantas “fatias” do parafuso são cortadas pela força. Imagine duas chapas tentando "
        "escorregar uma sobre a outra: o parafuso é cisalhado no ponto onde elas se tocam.\n\n"
        "- **1 plano** (o caso mais comum): o parafuso une duas chapas sobrepostas. Ex.: a alma de "
        "um perfil U sobre a alma de outro.\n"
        "- **2 planos**: o parafuso atravessa três chapas — a do meio puxa para um lado e as de "
        "fora para o outro (emenda com chapa dupla).\n\n"
        "Mais planos = mais resistência ao corte e ao deslizamento."
    ),
    "furo": (
        "Diâmetro do furo na chapa. Já vem preenchido com o **furo-padrão** da tabela (um pouco "
        "maior que o parafuso). Só altere se o seu furo for diferente — por exemplo, para "
        "reproduzir o AISC 360-10, que usa 27,0 mm no parafuso de 1″.\n\n"
        "**Simplificação:** o programa só trata furo-padrão (não calcula furos alargados nem "
        "alongados)."
    ),
    "rosca_plano": (
        "A rosca é a parte “ranhurada” do parafuso. Se ela cai bem no plano onde as chapas se "
        "tocam, a seção que resiste ao corte fica menor e a resistência cai.\n\n"
        "- **Ligado** (padrão, e a Anglo exige): considera a rosca no plano de corte — é o lado "
        "seguro.\n"
        "- **Desligado**: só use se o projeto garante que a parte lisa do corpo é a que fica no "
        "plano de corte."
    ),
    "deformacao_furo": (
        "Se a deformação do furo ao redor do parafuso (a “ovalização”) sob a carga de serviço é um "
        "limite do projeto, **deixe ligado**: a norma usa coeficientes mais conservadores "
        "(1,2 e 2,4).\n\n"
        "Desligado, usa 1,5 e 3,0, mais favoráveis. Na dúvida, deixe ligado."
    ),
    "m_diametro": "Diâmetro nominal do parafuso escolhido.",
    "m_borda_min": (
        "Menor distância permitida entre o centro do furo e a borda da chapa (Tabela 16 da "
        "NBR 8800). Se a sua borda for menor, a verificação reprova."
    ),
    "m_protensao": (
        "Força de aperto mínima que o parafuso deve receber na instalação (Tabela 19 da NBR 8800 "
        "e Tabela 8.1 da RCSC). É ela que mantém as chapas coladas numa ligação por atrito."
    ),
    # ------------------------------------------------------------------ 2. partes ligadas e geometria
    "t": (
        "Espessura, em mm, da chapa **mais fina** entre as que o parafuso atravessa — é ela que "
        "“cede” primeiro ao apoio do parafuso.\n\n"
        "Ex.: duas almas de 5,08 mm sobrepostas → **5,08**. **Não some** as espessuras (isso "
        "dobraria a resistência e seria contra a segurança); a soma vai no campo *Pega*."
    ),
    "aco": (
        "Aço das chapas ou perfis ligados. Dele vêm a resistência ao escoamento (f_y) e à ruptura "
        "(f_u), usadas no contato, no rasgamento e na peça. Se não souber, veja o certificado ou a "
        "especificação do perfil — o A36 é o mais comum."
    ),
    "pega": (
        "Soma das espessuras de todas as chapas que o parafuso atravessa (mais arruelas, se "
        "houver).\n\n"
        "**Opcional.** Só serve para avisar de “pega longa” (acima de 5 vezes o diâmetro) em "
        "ligações sem aperto controlado. Deixe **0** se não souber."
    ),
    "arranjo": (
        "**Grade retangular**: parafusos em fileiras regulares (o caso mais comum).\n\n"
        "**Coordenadas livres**: você digita a posição x e y de cada parafuso, para arranjos "
        "irregulares."
    ),
    "n_lin": (
        "Quantas **fileiras** de parafusos existem lado a lado. Cada fileira segue a direção da "
        "força; a distância entre fileiras é o gabarito g.\n\n"
        "Ex.: 2 fileiras."
    ),
    "n_col": (
        "Quantos parafusos há **em cada fileira**, um atrás do outro na direção da força; a "
        "distância entre eles é o passo s.\n\n"
        "Ex.: 2 por fileira. Com 2 fileiras de 2 parafusos, são 4 parafusos (grade 2 × 2)."
    ),
    "passo": (
        "**Passo**: distância entre os centros de dois parafusos vizinhos, medida na direção da "
        "força (mm).\n\n"
        "Mínimo: 2,7·d_b (o ideal é 3·d_b). Máximo: 24·t, limitado a 300 mm."
    ),
    "gabarito": (
        "**Gabarito**: distância entre duas fileiras de parafusos, medida perpendicularmente à "
        "força (mm).\n\n"
        "Os limites são os mesmos do passo."
    ),
    "borda": (
        "Distância do centro do primeiro furo até a **ponta (borda) da chapa**, medida na direção "
        "da força (mm).\n\n"
        "Não pode ser menor que a borda mínima da tabela nem maior que 12·t (limitada a 150 mm)."
    ),
    "tem_borda_vertical": (
        "Marque se existe uma borda livre ao lado dos parafusos, perpendicular à força. O programa "
        "passa a verificar também a distância até ela."
    ),
    "borda_vertical": (
        "Distância do centro do furo até a **borda lateral** da chapa (mm), perpendicular à força. "
        "Os limites são os mesmos da borda na direção da força."
    ),
    "coordenadas": (
        "Digite x e y de cada parafuso, em mm, a partir de qualquer origem. Use o “+” da tabela "
        "para acrescentar parafusos."
    ),
    # ------------------------------------------------------------------ 3. esforços
    "ja_calculo": (
        "**Característico**: o valor esperado em uso, sem coeficientes de segurança. **De "
        "cálculo**: o característico × γ_f.\n\n"
        "Deixe **desligado** se você tem os valores característicos (o programa majora). Ligue se "
        "os valores já vêm com os coeficientes aplicados (combinações da NBR 8681).\n\n"
        "**Simplificação:** o deslizamento é verificado com a força de serviço, obtida dividindo a "
        "de cálculo por γ_f."
    ),
    "N": (
        "Força **axial** (kN): puxa ou empurra a peça na direção das fileiras de parafusos "
        "(eixo x). Deixe 0 se não houver."
    ),
    "V": (
        "Força **cortante** (kN): atua **perpendicularmente** às fileiras (eixo y), tentando fazer "
        "uma chapa escorregar de lado sobre a outra. Numa emenda de perfis, é a cortante do perfil "
        "no ponto da emenda."
    ),
    "gama_f": (
        "Coeficiente de segurança das ações: multiplica o valor característico para obter o de "
        "cálculo. O padrão **1,4** é o usual para ação variável; para outras combinações use o "
        "coeficiente da NBR 8681."
    ),
    "momento": (
        "Quando a cortante V não passa pelo centro do grupo de parafusos, ela gira o grupo e cria "
        "um momento **M = V·a**.\n\n"
        "- **Sem momento**: V passa pelo centro do grupo.\n"
        "- **Emenda por sobreposição**: o programa calcula a = e + (n_col − 1)·s/2, a distância do "
        "centro do grupo até a ponta da sobreposição. *Simplificação usual:* a cortante age ali, "
        "onde o momento do perfil é nulo.\n"
        "- **Excentricidade a informada**: você digita a distância.\n"
        "- **Momento M informado**: você digita o momento pronto (ex.: vindo da análise da viga)."
    ),
    "excentricidade": (
        "Distância (mm) entre a linha de ação da cortante V e o centro do grupo de parafusos. "
        "Ela gira o grupo e cria o momento M = V·a."
    ),
    "momento_valor": (
        "Momento **total** (kN·m) no centro do grupo. Use quando já conhece o valor. Positivo = "
        "anti-horário."
    ),
    # ------------------------------------------------------------------ 4. atrito, instalação e escopo
    "superficie": (
        "Estado da superfície de contato entre as chapas. Ele define o coeficiente de atrito μ "
        "(quanto maior, mais difícil as chapas deslizarem).\n\n"
        "- **Galvanizada a fogo sem tratamento**: padrão da Anglo (μ = 0,20 na NBR).\n"
        "- **Classes A, B e C**: tratamentos das normas americanas; a **B (jateada)** dá o maior "
        "atrito.\n\n"
        "AISC e RCSC não definem μ para galvanizada sem tratamento (exigem ensaio): nelas o "
        "deslizamento aparece como NÃO OK."
    ),
    "atrito": (
        "Numa ligação **por atrito** o aperto controlado dos parafusos segura as chapas coladas e "
        "**não deixa elas deslizarem** em serviço. A Anglo exige esse tipo quando há inversão do "
        "esforço, vibração ou deslizamento indesejável.\n\n"
        "Desligado, a ligação trabalha por contato (a chapa escorrega até encostar no parafuso) e "
        "o deslizamento não é verificado."
    ),
    "Ce": (
        "Fator multiplicador do atrito usado pela norma no cálculo do deslizamento. "
        "Deixe **1,0** se não souber: é o valor do furo-padrão, que é o único tratado aqui."
    ),
    "K_torque": (
        "Coeficiente de torque: liga o torque aplicado na chave à força de aperto "
        "(T ≈ K·F·d). **0,20** é um valor típico para parafuso sem lubrificação especial.\n\n"
        "É só referência de instalação — nunca critério de aprovação. Aperte por rotação da porca, "
        "chave calibrada ou indicador de tração."
    ),
    "patinavel": (
        "Aço patinável (resistente à corrosão atmosférica) **sem pintura**: a norma reduz o "
        "espaçamento máximo entre parafusos (14·t, limitado a 180 mm) para evitar que a umidade "
        "entre entre as chapas. Marque só se for o seu caso."
    ),
    "fora_escopo": (
        "Marque o que existe na sua ligação e que esta verificação **não** calcula. Isso não muda "
        "os números, mas acrescenta um ALERTA na tabela e impede que o resultado pareça completo."
    ),
    # ------------------------------------------------------------------ 5. peça tracionada
    "Ag": (
        "Área bruta da seção transversal da peça tracionada, em mm² (está no catálogo do perfil). "
        "Deixe **0** se não precisa verificar a tração da peça."
    ),
    "ec": (
        "Excentricidade da ligação: distância do centro de gravidade da peça até o plano onde ela "
        "está ligada (ex.: num perfil U ligado pela alma, é a distância do centro de gravidade à "
        "face externa da alma). No catálogo do perfil costuma aparecer como x̄.\n\n"
        "Quanto maior, menor a resistência da peça (C_t = 1 − e_c/ℓ_c)."
    ),
    # ------------------------------------------------------------------ 6. Anglo
    "principal": (
        "**Principal**: a ligação faz parte do sistema que sustenta a estrutura — a Anglo exige "
        "A325 galvanizado a fogo.\n\n"
        "**Secundária**: elemento que não é essencial à estabilidade — a Anglo aceita o A307."
    ),
    "revestimento": (
        "Proteção do parafuso contra corrosão. O A325 vai **galvanizado a fogo** (padrão Anglo). "
        "O A490 **não pode** ser galvanizado a fogo: use Zn/Al (ASTM F1136 ou Dacromet)."
    ),
    "esbeltez": (
        "Barras de treliça e contraventamento dimensionadas pela esbeltez (e não pela força) têm "
        "pouca força calculada. Para elas, a Anglo manda a ligação resistir a pelo menos **75% da "
        "resistência à tração da peça** e a no mínimo **3 tf**.\n\n"
        "Se ligar, preencha A_g e e_c na seção 5."
    ),
    # ------------------------------------------------------------------ resultados
    "res_status": (
        "- **OK**: todas as verificações atendem.\n"
        "- **ALERTA**: atende, mas há uma ressalva ou algo que não pôde ser calculado.\n"
        "- **NÃO OK**: alguma verificação reprova — veja a tabela."
    ),
    "res_aproveitamento": (
        "Quanto da capacidade a ligação usa na verificação mais crítica: **solicitante ÷ "
        "resistente**. Até 100% atende; acima de 100% não atende.\n\n"
        "Ex.: 41% = a ligação usa menos da metade do que resiste."
    ),
    "res_menor": (
        "O menor parafuso da tabela (por diâmetro) que passa em todas as verificações com a sua "
        "geometria e os seus esforços.\n\n"
        "Se aparecer *nenhum com esta geometria*, o problema costuma estar na geometria (borda, "
        "espaçamento…) e não no diâmetro."
    ),
    "res_critico_elu": (
        "Força resultante no parafuso **mais carregado**, com os esforços de cálculo (majorados). "
        "É comparada com a resistência ao corte e ao contato.\n\n"
        "ELU = estado-limite último: a verificação de ruptura."
    ),
    "res_critico_els": (
        "A mesma força, mas com os esforços de **serviço** (sem majorar). É a que se compara com a "
        "resistência ao deslizamento."
    ),
    "res_tabela": (
        "Cada linha é uma verificação:\n\n"
        "- **Solicitante**: o que atua (a carga) — ou, nas distâncias, o valor exigido.\n"
        "- **Resistente**: o que a ligação suporta — ou, nas distâncias, o valor adotado.\n"
        "- **Aproveitamento**: solicitante ÷ resistente. Acima de 100% reprova.\n"
        "- **Status**: OK, NÃO OK, ALERTA (ressalva), INFO (informação) ou N/A (não se aplica).\n"
        "- **Fórmula** e **Referência**: como foi calculado e o item da norma."
    ),
    "btn_comparar": (
        "Calcula a mesma ligação nas quatro normas e mostra o resultado lado a lado. Não muda a "
        "norma escolhida na seção 1."
    ),
    "btn_testar": (
        "Roda todas as verificações para cada parafuso da tabela, do menor ao maior diâmetro, "
        "mantendo a geometria e os esforços, e indica o menor que atende."
    ),
    "btn_csv": "Baixa a tabela de verificações em CSV (abre no Excel).",
    "res_distribuicao": (
        "Força em cada parafuso pelo **método elástico**: cada um recebe a parte direta de V e N "
        "(divididas igualmente) mais a parcela do momento, proporcional à sua distância ao centro "
        "do grupo. É uma simplificação conservadora."
    ),
    "res_resumo": (
        "O essencial em poucas linhas: status geral, a verificação mais crítica e o menor parafuso "
        "que atende."
    ),
    "reg_registrar": (
        "Guarda este cálculo — entradas, resultados e a tabela de verificações — no projeto "
        "ativo. Ele passa a fazer parte do memorial em Word e PDF e da Central de validação."
    ),
    "reg_comparar": (
        "Fixe um cenário (ex.: o M20 e depois o M22) para ver os resultados lado a lado. Os "
        "cenários valem só nesta sessão; para guardar o escolhido, registre-o no projeto."
    ),
    # ------------------------------------------------------------------ modo mecânico
    "mec_aperto": (
        "A pré-carga (força de aperto) e o torque estimado que você deve especificar para a "
        "montagem. O torque é estimativa: o atrito real varia."
    ),
    "mec_critico": (
        "O parafuso mais carregado do grupo: é nele que as verificações de tração, "
        "cisalhamento e von Mises são feitas."
    ),
    "sec_mec_1": (
        "Escolha a rosca, a classe do parafuso e como os parafusos estão distribuídos na junta "
        "(em círculo, em grade ou em posições livres)."
    ),
    "sec_mec_2": (
        "Define como o parafuso é apertado e quanta força de aperto (pré-carga) ele recebe. A "
        "pré-carga mantém as chapas comprimidas e protege o parafuso da variação da carga externa.\n\n"
        "**Simplificação:** o torque é uma estimativa (T = K·F·d); o atrito real varia muito."
    ),
    "sec_mec_3": (
        "Informe as cargas **de serviço** (as que a junta realmente vê em uso). Este modo aplica o "
        "fator de segurança mínimo n da seção 4; se os seus valores já têm coeficientes de "
        "segurança, escolha “Já majorados” para não aplicar a margem duas vezes."
    ),
    "sec_mec_4": (
        "Atrito entre as chapas, fator de segurança desejado e dados da chapa junto ao furo."
    ),
    "sec_mec_5": (
        "Use quando a carga varia ao longo do tempo (ciclos). **Simplificação:** Goodman modificado, "
        "válido enquanto a junta permanece fechada."
    ),
    "mec_diagnostico": (
        "Cada linha é um modo de falha, com o que atua (solicitante), o que o parafuso ou a chapa "
        "suporta (resistente), o aproveitamento (= 1/n), o status, a fórmula e a fonte.\n\n"
        "Abaixo da meta n desejada o status é ALERTA; abaixo de 1, NÃO OK."
    ),
    "mec_distribuicao": (
        "Carga axial externa e cisalhamento em cada parafuso, pelo método elástico: a carga "
        "direta é dividida igualmente e o momento M e o torque T somam parcelas proporcionais à "
        "distância de cada parafuso ao centro do grupo."
    ),
    "mec_classe": (
        "Classe de resistência do parafuso (ISO 898-1), ex.: **8.8**. O primeiro número × 100 é a "
        "resistência à ruptura em MPa (8 → 800 MPa); multiplicando os dois números e por 10 obtém-se "
        "o escoamento mínimo (8 × 8 × 10 = 640 MPa). Quanto maior o número, mais resistente."
    ),
    "mec_padrao": (
        "Como os parafusos estão distribuídos:\n\n"
        "- **Círculo**: igualmente espaçados num círculo (ex.: flange).\n"
        "- **Grade retangular**: fileiras e colunas regulares.\n"
        "- **Coordenadas livres**: você digita x e y de cada parafuso."
    ),
    "mec_numero": "Quantidade de parafusos igualmente espaçados ao longo do círculo.",
    "mec_grade_linhas": (
        "Quantas fileiras de parafusos há, uma ao lado da outra, ao longo do eixo y. "
        "Ex.: 2 fileiras."
    ),
    "mec_grade_colunas": (
        "Quantos parafusos há em cada fileira, ao longo do eixo x — o mesmo eixo da força "
        "cortante V. Ex.: 2 por fileira."
    ),
    "mec_grade_passo": "Distância entre os centros de dois parafusos vizinhos ao longo de x (mm).",
    "mec_grade_gabarito": "Distância entre duas fileiras, ao longo de y (mm).",
    "mec_instalacao": (
        "Como o parafuso é apertado. A escolha muda o fator de torque K e a incerteza padrão da "
        "pré-carga:\n\n"
        "- **Torque lubrificado**: chave de torque com parafuso lubrificado.\n"
        "- **Torque seco**: chave de torque sem lubrificação (mais dispersão).\n"
        "- **Controle aprimorado**: medição da força ou do ângulo (menos dispersão)."
    ),
    "mec_gama_f": (
        "Coeficiente que foi usado para majorar os valores. O programa divide por ele para voltar "
        "à carga de serviço."
    ),
    "mec_P": (
        "Carga axial total sobre o grupo (kN). **Positiva** tende a abrir a junta (tração nos "
        "parafusos); negativa comprime."
    ),
    "mec_V": (
        "Força cortante total (kN), paralela às chapas: tenta fazer uma chapa escorregar sobre a "
        "outra. É dividida entre os parafusos."
    ),
    "mec_M": (
        "Momento de tombamento (N·m): tende a abrir um lado da junta. Os parafusos de um lado "
        "ganham tração e os do outro perdem, proporcionalmente à distância ao eixo."
    ),
    "mec_T": (
        "Torque no grupo (N·m): momento que gira o grupo no plano das chapas e gera cisalhamento "
        "em cada parafuso, perpendicular ao seu raio."
    ),
    "mec_excentricidade": (
        "Distância (mm) da linha de ação da cortante ao centro do grupo. O programa calcula "
        "T = V·a (V em kN × a em mm = N·m)."
    ),
    "mec_rosca_plano": (
        "Define a área do parafuso que resiste ao corte:\n\n"
        "- **Rosca cruza o plano**: a parte rosqueada fica onde as chapas se tocam — seção menor, "
        "lado seguro.\n"
        "- **Corpo liso cruza o plano**: a parte lisa fica no plano — seção maior."
    ),
    "mec_atrito": (
        "Quanto maior, mais difícil as chapas deslizarem. Depende do tratamento da superfície: "
        "galvanizada ≈ 0,2; jateada ≈ 0,5. Use o valor do seu caso."
    ),
    "mec_interfaces": (
        "Número de superfícies de contato entre chapas que o aperto do parafuso mantém coladas e "
        "que resistem ao deslizamento. Duas chapas sobrepostas = **1**; três chapas (chapa dupla) "
        "= **2**."
    ),
    "mec_fator_minimo": (
        "Fator de segurança que você exige: n = capacidade ÷ carga de serviço. Abaixo dele o status "
        "vira ALERTA; abaixo de 1, a junta falha. Como as cargas aqui são de serviço, esta é a sua "
        "margem de segurança."
    ),
    "mec_furo": (
        "Diâmetro do furo na chapa (mm), no mínimo o do parafuso. O furo-padrão costuma ter 1 a "
        "2 mm a mais que o parafuso."
    ),
    "mec_borda": (
        "Distância do centro do furo até a borda da chapa (mm). A distância livre usada no "
        "rasgamento é e − d_h/2."
    ),
    "mec_Sy": (
        "Tensão de escoamento da chapa (MPa), no certificado ou na especificação do material "
        "(ex.: aço A36 = 250 MPa)."
    ),
    "mec_P_min": "Menor valor da carga axial P durante o ciclo de carregamento (kN).",
    "mec_P_max": "Maior valor da carga axial P durante o ciclo de carregamento (kN).",
    "mec_M_min": "Menor valor do momento de tombamento durante o ciclo (N·m).",
    "mec_M_max": "Maior valor do momento de tombamento durante o ciclo (N·m).",
    # métricas do modo mecânico
    "mec_m_At": "Área da seção resistente à tração da rosca, da tabela de roscas ISO.",
    "mec_m_Sp": "Tensão de prova: até ela o parafuso volta ao comprimento original, sem deformar.",
    "mec_m_Sy": "Tensão a partir da qual o parafuso passa a se deformar permanentemente.",
    "mec_m_Sut": "Maior tensão que o parafuso suporta antes de romper.",
    "mec_m_pre_carga": (
        "Força de aperto alvo em cada parafuso: a fração da carga de prova que você escolheu."
    ),
    "mec_m_faixa": (
        "Menor e maior pré-carga prováveis na prática, considerando a incerteza do aperto e as "
        "perdas."
    ),
    "mec_m_torque": (
        "Torque estimado na chave para chegar à pré-carga (T = K·F·d). É estimativa: o atrito "
        "real varia."
    ),
    "mec_m_prova": "Sp × At: a força que o parafuso aguenta sem deformar permanentemente.",
    "mec_m_carga_max": (
        "Maior força de tração no parafuso mais carregado: pré-carga máxima mais a parte da carga "
        "externa que chega ao parafuso (C·P)."
    ),
    "mec_m_sigma": "Carga axial máxima ÷ área resistente.",
    "mec_m_tau": "Cortante no parafuso mais carregado ÷ área da seção que resiste ao corte.",
    "mec_m_vm": (
        "Tensão equivalente que combina tração e cisalhamento, √(σ² + 3τ²). É comparada com o "
        "escoamento."
    ),
    "mec_m_alternada": "Metade da variação de tensão no ciclo, já com o fator Kf.",
    "mec_m_media": "Média entre a tensão mínima e a máxima do ciclo.",
    "mec_m_goodman": (
        "Fator de segurança à fadiga pelo critério de Goodman. Acima de 1 resiste; quanto maior, "
        "melhor."
    ),
    "mec_m_escoamento_max": "Margem contra escoar na tensão máxima do ciclo.",
}
