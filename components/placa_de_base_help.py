"""Textos dos “?” da página Placas de base, em linguagem simples (um teste exige cada um)."""

from __future__ import annotations

AJUDA: dict[str, str] = {
    # 1. Pilar e chumbadores
    "sec_pilar": (
        "O pilar que chega na base, o tipo de base e os chumbadores. A NBR 8800:2025 (6.7) trata "
        "de pilares de perfil I ou H com placa retangular."
    ),
    "perfil": (
        "Perfil do pilar (W, HP ou I do catálogo). A placa é desenhada em volta dele: as mesas "
        "ficam paralelas ao lado ℓy."
    ),
    "tipo": (
        "Onde ficam os chumbadores. Tipo 1 (externos, de 4 a 8): fora das mesas, a base que "
        "aguenta momento grande. Tipo 2 (internos, 4): entre as mesas, junto da alma; não cobre o "
        "chumbador tracionado pelo momento (C3 e T3). Rotulada (2 internos no eixo): um de cada "
        "lado da alma, quase sem momento. Internos e externos (4 + 4): para momento grande com "
        "tração alta. Os dois últimos não estão na Figura 21 e vão pelo método geral."
    ),
    "n_chumbadores": (
        "Quantos chumbadores. Tipo 1: 4, 6 ou 8, metade de cada lado; tipo 2: 4; rotulada: 2; "
        "internos e externos: 8. A Tabela 18 vale de 4 a 8 chumbadores (nota a): na rotulada, "
        "ligue a verificação da ancoragem no concreto."
    ),
    "modo_chumbador": (
        'Da Tabela 18: os 7 diâmetros da norma (3/4" a 2"), com as medidas que ela dá. Por '
        "fórmula: qualquer diâmetro, em polegada, métrico ou digitado; furo, arruela, distâncias, "
        "embutimento e concreto mínimo saem de fórmulas com fonte (AISC, ACI 318-19, ASME e NBR "
        "6118), e a ancoragem no concreto é sempre verificada. A 6.7.1.1 admite essa saída da "
        "tabela."
    ),
    "chumbador": (
        "Diâmetro do chumbador (aço ASTM A36). Cada diâmetro tem na Tabela 18 da norma as "
        "distâncias mínimas, a ancoragem, a arruela e o furo — o programa usa esses valores."
    ),
    "chumbador_formula": (
        'Diâmetro comercial do chumbador: polegada com rosca UNC (1/2" a 4") ou métrico com '
        "rosca grossa ISO (M12 a M64). Em Outro diâmetro, você digita o d_b e o passo. Os "
        "resultados mostram o diâmetro que cada critério pede e o menor comercial que atende."
    ),
    "d_b_livre": (
        "Diâmetro nominal da barra rosqueada (mm), quando não é um dos comerciais da lista: por "
        "exemplo uma barra torneada sob medida."
    ),
    "passo": (
        "Passo da rosca (mm): a distância entre dois fios. Zero usa o da rosca métrica grossa de "
        "diâmetro mais perto. Ele dá a área resistente da rosca e o comprimento de rosca acima da "
        "porca."
    ),
    "d_f": (
        "Diâmetro do furo na placa de base (mm). Zero usa a regra: os furos da Tabela 18, que são "
        "os mesmos da AISC (Manual, Tabela 14-2), interpolados no diâmetro. O furo é folgado para "
        "absorver o erro de locação dos chumbadores; a arruela especial cobre a folga."
    ),
    "tabela_18": (
        "Ligado, a₁ e a₂ são os mínimos do diâmetro escolhido — os da Tabela 18 ou, por fórmula, "
        "os calculados — e a placa sai a menor possível. Desligue para informar distâncias "
        "maiores — por exemplo para a placa ficar mais larga que a mesa (ℓy ≥ b_f + 25 mm) — ou, "
        "no tipo 2, um a₁ menor na direção ℓx."
    ),
    "a1": (
        "a₁: do centro do furo à borda da placa (mm), com o mínimo da Tabela 18. No tipo 1 a "
        "placa tem ℓx = d + 4·a₁; no tipo 2 o a₁ da direção ℓx é o campo ao lado."
    ),
    "a1_x": (
        "Só no tipo 2: na direção ℓx a placa passa 2·a₁ da face da mesa (Figura 21), então "
        "ℓx = d + 4·a₁. A nota f da Tabela 18 deixa este a₁ de 10 mm até o valor da tabela: "
        "menor, a placa fica mais curta e mais fina."
    ),
    "a2": (
        "a₂: distância entre chumbadores vizinhos da mesma linha (mm). Define a largura da placa "
        "ℓy = (n_b/2 − 1)·a₂ + 2·a₁."
    ),
    # 2. Tipo de chumbador
    "sec_chumbador": (
        "Como o chumbador se prende no concreto e de que aço ele é. O reto com porca é o da "
        "Tabela 18; os outros tipos têm a ancoragem conferida pela ACI 318-19."
    ),
    "ancoragem": (
        "Reto com porca e chapa na ponta: o da Tabela 18, concretado com o bloco. Guarda-chuva: "
        "barra dobrada em J ou L, concretada — arranca mais fácil. Químico: barra roscada colada "
        "com resina num furo do concreto pronto. Parabolt: expansão mecânica no furo. Os dois "
        "últimos são pós-instalados e precisam da resistência da ficha do fabricante."
    ),
    "aco_chumbador": (
        "A norma pede ASTM A36 ou equivalente (f_y 250, f_u 400 MPa). Outro aço muda o diâmetro "
        "mínimo (pelo f_u dele) e pede conferir a ancoragem no concreto. As classes 4.6 e 8.8 da "
        "ISO 898-1, que a NBR 8800 (6.3) admite, servem aos chumbadores métricos."
    ),
    "verificar_aci": (
        "Ligue para conferir também o arrancamento da cabeça, o cone de concreto e o arrancamento "
        "lateral junto à borda pela ACI 318-19. Sem armadura de ancoragem no bloco, o cone "
        "costuma governar."
    ),
    "e_h": (
        "Comprimento do gancho do guarda-chuva, medido da face interna da barra até a ponta (mm). "
        "A conta vale de 3·d_b a 4,5·d_b; zero usa 4,5·d_b."
    ),
    "chapa_ponta": (
        "Lado da chapa quadrada soldada ou presa na ponta do chumbador (mm). Ela aumenta a área "
        "que apoia no concreto; zero conta só a porca sextavada pesada."
    ),
    "h_ef": (
        "Embutimento efetivo: da face do concreto até onde o chumbador apoia (cabeça, gancho ou "
        "fim da resina), em mm. Zero usa h₁ da Tabela 18 (concretado) ou 12·d_b (pós-instalado); "
        "por fórmula, o menor que passa no cone de concreto, nunca menos que 12·d_b."
    ),
    "n_rd_fabricante": (
        "Resistência de cálculo à tração de um chumbador, da ficha técnica do fabricante (ETA ou "
        "ICC-ES), para o embutimento, o concreto fissurado e as distâncias da obra (kN)."
    ),
    "armadura": (
        "Ligue se o bloco tiver armadura que atravessa o cone e está ancorada dos dois lados "
        "(armadura de ancoragem). Então o cone de concreto sai como informação e a armadura "
        "precisa ser dimensionada para a tração no projeto do bloco."
    ),
    # 3. Placa
    "sec_placa": "A espessura e o aço da placa de base e a camada de argamassa por baixo dela.",
    "t_placa": (
        "Espessura da placa de base (mm). O programa calcula a mínima (t_p,min) e mostra a chapa "
        "comercial mais leve que atende."
    ),
    "aco_placa": "Aço da placa: dá o f_y usado na espessura mínima (ASTM A36: 250 MPa).",
    "e_n": (
        "Espessura da argamassa expansiva de assentamento, entre a placa e o concreto (mm). "
        "Zero usa o valor da Tabela 18 para o diâmetro do chumbador; por fórmula, a porca de "
        "nivelamento mais a arruela mais 15 mm de argamassa por baixo."
    ),
    # 3. Concreto e bloco
    "sec_concreto": (
        "O concreto do bloco de fundação: a resistência dele e o tamanho do bloco definem quanto "
        "a placa pode apertar o concreto (σ_c,Rd)."
    ),
    "fck": (
        "Resistência característica do concreto do bloco (MPa). No chumbador reto com porca, a "
        "Tabela 18 pede um mínimo para cada diâmetro, para o concreto não esmagar junto à "
        "porca da ponta (nota b)."
    ),
    "bloco_informado": (
        "Ligue para informar o tamanho do bloco: o programa calcula A₂/A₁ (a área do bloco que "
        "ajuda a placa) e confere as medidas mínimas da nota e da Tabela 18: N_b, ao longo de "
        "ℓx, com o N_b,mín, e B_b, ao longo de ℓy, com o chumbador a a₃ da face."
    ),
    "bloco_x": "Dimensão do bloco na direção de ℓx, o lado da placa no plano do momento (mm).",
    "bloco_y": "Dimensão do bloco na direção de ℓy, o outro lado da placa (mm).",
    "razao": (
        "A₂/A₁: área de concreto em volta da placa (semelhante a ela) dividida pela área da "
        "placa. 1 é o mais seguro (placa do tamanho do bloco); até 4 aumenta a pressão admitida."
    ),
    "combinacao": (
        "Tipo de combinação de cálculo: muda os coeficientes do aço (γ_a1, γ_a2) e do concreto "
        "(γ_c = 1,4 na normal e 1,2 na excepcional)."
    ),
    # 4. Esforços
    "sec_esforcos": (
        "Os esforços de cálculo (ELU) no pé do pilar, já combinados. Uma base costuma ter várias "
        "combinações que mandam em coisas diferentes: a de maior compressão na placa e no "
        "concreto, a de tração nos chumbadores, a de muita cortante com pouca compressão no atrito."
    ),
    "n_sd": (
        "Força normal de cálculo (kN): positiva comprime a placa contra o concreto, negativa "
        "arranca o pilar (tração nos chumbadores)."
    ),
    "m_sd": (
        "Momento de cálculo em torno do eixo de maior inércia do pilar (kN·m), em valor "
        "absoluto: o sinal só troca o lado dos chumbadores tracionados. O do eixo de menor inércia "
        "vai no campo M_Sd,y."
    ),
    "v_sd": (
        "Força cortante de cálculo na base, horizontal (kN), em valor absoluto. Com cortante "
        "nas duas direções, informe a resultante √(V_x² + V_y²)."
    ),
    "m_sd_y": (
        "Momento em torno do eixo de menor inércia do pilar (kN·m), em valor absoluto: comprime "
        "o lado de cima da planta. As fórmulas da 6.7 são só do eixo forte; com este momento a "
        "base vai pelo mesmo método em duas direções (flexão oblíqua): a placa aperta o concreto "
        "numa zona limitada por uma linha neutra inclinada e cada chumbador do outro lado puxa "
        "em proporção à distância a ela."
    ),
    "distribuicao": (
        "Como a placa aperta o concreto. Bloco uniforme (o da norma, 6.7): a pressão fica igual "
        "num trecho da borda; com momento médio e pouca compressão, ela cabe toda nesse trecho e "
        "nenhum chumbador puxa. Linear elástica: a placa é um corpo rígido que gira; a pressão "
        "cresce em linha reta até a borda e, do lado que levanta, os chumbadores esticam e puxam "
        "(como a armadura de uma viga de concreto). Use a elástica para ver a tração que a "
        "rotação da placa dá aos chumbadores; ela pede σ máxima ≤ σ_c,Rd."
    ),
    # 5. Cortante
    "sec_cortante": (
        "Como a cortante passa para o concreto: só pelo atrito da placa na argamassa, ou por um "
        "dispositivo — e então só ele resiste (6.7.2.3)."
    ),
    "cortante": (
        "Atrito: vale só quando a placa aperta o concreto (C1, C2, C3 e T3). Placa de cisalhamento: "
        "chapa soldada embaixo da placa, enterrada no bloco. Arruelas soldadas: os próprios "
        "chumbadores resistem, com a arruela de furo justo soldada na placa (todos engatam "
        "juntos). Direto no furo: sem arruela soldada a placa escorrega na folga do furo antes de "
        "encostar e os chumbadores pegam um de cada vez — o programa conta só 2 e avisa; prefira "
        "as arruelas ou a placa de cisalhamento."
    ),
    "mu": (
        "Coeficiente de atrito entre a placa e a argamassa. A norma dá 0,45 para argamassa "
        "expansiva; só mude com justificativa."
    ),
    "b_v": (
        "b_v: altura da placa de cisalhamento, da face de baixo da placa de base até a ponta "
        "(mm). A parte que trabalha é a enterrada no concreto, b_v − e_n."
    ),
    "b_h": "b_h: largura da placa de cisalhamento, perpendicular à cortante (mm).",
    "t_pv": (
        "t_pv: espessura da placa de cisalhamento (mm). Não pode passar da espessura da placa de "
        "base."
    ),
    "t_arruela": (
        "Espessura da arruela especial soldada na placa (mm). Zero usa a da Tabela 18 para o "
        "diâmetro do chumbador (por fórmula, d_b/3 arredondado para a chapa comercial, como na "
        "AISC). A arruela é de aço com f_y = 345 MPa e o chumbador encosta no furo dela "
        "(d_b + 1,5 mm): a pressão nesse furo também limita a cortante (6.3.3.3)."
    ),
    # resultados
    "res_status": "OK quando todas as verificações e limites passam; NÃO OK quando alguma reprova.",
    "res_caso": (
        "O caso da norma (6.7.1.4), pela força normal e pela excentricidade e = M/N: C1 a C3 na "
        "compressão, T1 a T3 na tração. Define as fórmulas usadas. Na flexão oblíqua, C2 e T2 "
        "são sem chumbador tracionado ou sem contato, e C3 e T3, com os dois."
    ),
    "res_aproveitamento": (
        "A maior razão entre solicitante e resistente das verificações. Acima de 100 % a base "
        "não atende."
    ),
    "res_tp": "Espessura mínima da placa calculada pela norma × a espessura adotada.",
    "res_governa": "A verificação com o maior aproveitamento — a que manda no dimensionamento.",
    "res_figura": (
        "Planta e corte da base com as cotas. Em vermelho, os chumbadores tracionados; em azul, "
        "a pressão de contato no trecho ℓ_c sob a placa. Na flexão oblíqua, a planta mostra a "
        "zona comprimida hachurada e a linha neutra (LN) inclinada."
    ),
    "res_adotado": (
        "As medidas para o desenho de fabricação: placa, chumbadores, furo, ancoragem, arruela, "
        "argamassa, armadura mínima e medidas mínimas do bloco (Tabela 18 e notas, ou as "
        "calculadas no modo por fórmula)."
    ),
    "res_por_formula": (
        "Cada medida do chumbador fora da Tabela 18, com a conta e a norma de onde ela sai: rosca "
        "e área resistente, porca, furo, arruela, distâncias a₁, a₂ e a₃, argamassa, rosca acima "
        "e abaixo, embutimento, comprimento e massa da barra e o concreto mínimo."
    ),
    "res_diametros": (
        "O diâmetro mínimo que cada critério pede com as forças desta base: a tração no aço "
        "(6.7.2.2), o arrancamento da porca ou do gancho no concreto (ACI 318-19) e, com as "
        "arruelas soldadas, a cortante (6.7.2.5). O maior deles manda."
    ),
    "res_menor_diametro": (
        "O menor diâmetro comercial da mesma série (polegada ou métrica) que passa em todas as "
        "verificações dos chumbadores, recalculando a base inteira para cada um (a placa e as "
        "forças mudam com o diâmetro). O cone de concreto fica de fora: ele depende do bloco, do "
        "embutimento e da armadura."
    ),
    "btn_adotar_diametro": "Usa na página o menor diâmetro comercial que atende, com o furo pela regra.",
    "res_comparacao": (
        "As medidas calculadas lado a lado com a linha da Tabela 18 de diâmetro mais perto, para "
        "conferir: nos diâmetros da tabela as fórmulas dão valores parecidos."
    ),
    "res_verificacoes": (
        "Cada verificação com o valor atuante, o resistente e o item da norma. As fórmulas com os "
        "números deste caso ficam no expansor abaixo das tabelas."
    ),
    "res_mais_leve": (
        "A placa mais leve que atende trocando só o diâmetro do chumbador e a espessura (chapas "
        "comerciais). Pilar, esforços, concreto e dispositivo de cortante ficam como estão. No "
        "químico e no parabolt com N_Rd do fabricante, o diâmetro fica (o N_Rd é dele). Por "
        "fórmula, troca entre os comerciais da mesma série, sem olhar o cone de concreto. A solda "
        "do pilar fica de fora: ela não muda com a placa."
    ),
    "btn_adotar": "Usa na página o chumbador e a espessura da base mais leve que atende.",
    "btn_csv": "Baixa a tabela de verificações em CSV (abre direto no Excel).",
    "sec_memorial": (
        "O memorial só desta base: em Word, o trecho para colar no seu memorial oficial; em "
        "PDF, o documento completo."
    ),
    "btn_memorial_word": (
        "O memorial desta base em Word, na ordem de um memorial: normas, dados, esforços, "
        "desenho, hipóteses, verificações, resumo, detalhamento, conclusão e símbolos. Sai "
        "como trecho para colar no seu memorial oficial: sem capa nem aprovações, títulos sem "
        "número (o seu documento numera), legendas que se renumeram e as contas como equações "
        "do Word. Para o documento completo do projeto, registre e use a Central de "
        "relatórios."
    ),
    "btn_memorial_pdf": "Baixa o memorial desta base em PDF, pronto para enviar.",
    "reg_registrar": (
        "Grava esta base no projeto ativo; ela entra no memorial do projeto na Central de "
        "relatórios."
    ),
    # combinações, soldas e cortante no concreto
    "bloco_z": (
        "Altura do bloco de concreto (mm). Entra na ruptura do concreto pela cortante (ACI 318-19): "
        "bloco baixo quebra mais fácil. Com 0, o programa usa a altura mínima da Tabela 18."
    ),
    "varias": (
        "Uma combinação: você digita N, M e V. Várias combinações: uma tabela com todas as "
        "combinações do pé do pilar (compressão alta, tração do vento, momento grande...). Cada "
        "uma passa por todas as contas e, em cada verificação, vale a pior delas."
    ),
    "pilar_modelo": (
        "Os pilares que a página Esforços do modelo conhece, com a base já identificada. As "
        "combinações dele vêm já majoradas (ELU), do jeito que a placa precisa."
    ),
    "btn_trazer": (
        "Troca a tabela pelas combinações ELU do pé deste pilar, tiradas do modelo do SolidWorks "
        "(as mesmas da seção de placas de base de Esforços do modelo)."
    ),
    "btn_exemplo_casos": "Volta a tabela para as três combinações de exemplo.",
    "lug_cjp": (
        "Marque se a placa de cisalhamento for soldada na placa de base com penetração total: aí a "
        "solda resiste como a própria chapa e não precisa de conta. Com filetes, o programa "
        "verifica os dois cordões."
    ),
    "sec_soldas": (
        "As soldas da base: o pilar na placa (o contorno do perfil), a placa de cisalhamento e as "
        "arruelas soldadas, quando houver. Perna 0 deixa o programa escolher a menor que passa."
    ),
    "perna_pilar": (
        "Tamanho da perna do filete que prende o pilar na placa (mm). Com 0, o programa escolhe a "
        "menor perna comercial que passa em todas as combinações, entre a mínima da norma e a "
        "máxima que cabe na ponta da mesa."
    ),
    "eletrodo": (
        "O metal da solda. E70 (485 MPa) é o comum para aço A36 e A572 Gr 50; E60 é mais fraco e "
        "E80 é para aços mais resistentes."
    ),
    "aco_pilar": (
        "Aço do perfil do pilar. Entra na verificação da chapa do pilar junto da solda (a mesa ou "
        "a alma não podem escoar antes do cordão)."
    ),
    "solda_dentro": (
        "Além do cordão por fora das mesas, cordões por dentro, de cada lado da alma. Mais solda, "
        "menos força por milímetro. Desligue se não houver espaço para soldar por dentro."
    ),
    "solda_alma": (
        "Cordões dos dois lados da alma. Ajudam a levar a cortante e parte da força normal."
    ),
    "contato": (
        "Marque só se a ponta do pilar for faceada (usinada) e assentar inteira na placa: aí a "
        "compressão passa por contato e a solda leva só a tração, o momento e a cortante. Sem "
        "isso, a solda leva tudo."
    ),
    "perna_lug": (
        "Perna dos dois filetes que prendem a placa de cisalhamento na placa de base (mm). Com 0, "
        "o programa escolhe a menor que passa."
    ),
    "perna_arruela": (
        "Perna do filete em volta de cada arruela soldada na placa (mm). Com 0, o programa "
        "escolhe a menor que passa, sem passar da espessura da arruela."
    ),
    "lx_placa": (
        "Comprimento da placa na direção da altura do pilar (mm). Com 0, o mínimo da norma: d + 4·a₁. "
        "Maior que isso, os chumbadores externos vão para perto da borda, a a₁ dela."
    ),
    "ly_placa": (
        "Largura da placa na direção das mesas (mm). Com 0, o mínimo pelos a₁ e a₂. Maior que isso, "
        "os chumbadores ficam centrados e sobra borda dos dois lados."
    ),
    "res_combinacoes": (
        "Cada combinação com o caso dela (C1 a T3), o status, o aproveitamento máximo e a "
        "verificação que manda nela. A base desenhada e o memorial seguem a combinação que governa."
    ),
    "caso_desenho": (
        "Qual combinação o desenho mostra: as forças nos chumbadores e a pressão no concreto "
        "mudam de uma para outra."
    ),
}
