# Placas de base

A página verifica a ligação entre um pilar e um bloco de concreto. A placa é retangular, com assentamento em argamassa. A NBR 8800:2025, subseção 6.7, fornece os casos uniaxiais para os perfis I e H e as disposições da Figura 21. A página também calcula configurações por método geral. O resultado identifica quais hipóteses precisam de confirmação independente.

O cálculo de uma base, de cada combinação e da envoltória entra por `core.base_de_pilar.calcular`. A tela, o desenho, o registro e o memorial usam esse resultado. A verificação de todos os pilares em **Esforços do modelo** usa o cálculo separado do AISC Design Guide 1 em `core/base_plate.py`.

## Geometria e finalidade

- Em **verificação**, informar os lados e a altura reais do bloco e a posição do centro da placa em relação ao centro do bloco. Uma dimensão ausente torna inconclusivas as resistências que dependem do bloco. As distâncias às faces são medidas a partir das posições físicas das barras.
- Em **pré-dimensionamento**, o programa pode estimar dimensões do bloco. Uma solução que atende recebe o status **Pré-dimensionado**. A massa usada na comparação é a da placa de aço.
- As disposições disponíveis são tipo 1, tipo 2, rotulada em x, rotulada em y e internos e externos. O número permitido de chumbadores e a posição das barras dependem da disposição. Para o canal U, estão disponíveis tipo 1 e rotulada em x.
- Na tipo 1, o comprimento mínimo é ℓx = d + 4a₁. Na tipo 2, a₁ em x pode ser ajustado dentro dos limites da nota f. As barras externas ficam a a₁ da borda em x. A placa pode ter dimensões maiores que as mínimas. O espaçamento efetivo é medido entre centros e a distância efetiva à borda considera as quatro faces.
- A Tabela 18 fornece medidas de referência para a montagem. As verificações indicam quando aço, tipo de ancoragem, perfil ou número de barras saem do seu campo de aplicação. No modo por fórmula as roscas podem ser UNC, métricas ou especificadas pelo usuário. O detalhamento considera furo, arruela, porca, graute, embutimento e comprimento de rosca.
- Para a pressão admissível em concreto, o fator de ampliação de área usa a maior área homotética à placa que cabe no bloco, concêntrica à área carregada. O deslocamento da placa reduz as dimensões disponíveis. A resistência é σc,Rd = 0,85 fck √(A₂/A₁) / γc, limitada a 1,7 fck / γc.

## Esforços, pressão e equilíbrio

O programa recebe kN e kN·m e calcula internamente em N e mm. N positivo comprime. As coordenadas x e y são medidas no plano da placa. M e M_y são os momentos generalizados cujo sentido positivo comprime x positivo e y positivo, respectivamente. Vx e Vy atuam ao longo desses eixos. Mz positivo gera cortantes tangenciais na direção (−y, x). A importação do modelo transforma momentos e cortantes conjuntamente segundo o eixo forte selecionado. Uma componente direcional preenchida prevalece sobre o módulo de V. A outra componente vazia vale zero. O módulo isolado exige a orientação desfavorável.

C1 e T1 representam compressão e tração centradas. C2 tem contato sem chumbador tracionado. C3 e T3 combinam pressão e tração. Em T2 as barras equilibram a carga sem contato. Para o bloco uniforme uniaxial, C2 tem ℓc = ℓx − 2|M/N|. Na flexão oblíqua, a área comprimida é a interseção da placa com o semiplano comprimido. A posição e o ângulo do limite de contato entram no equilíbrio.

O modelo elástico usa uma placa rígida, uma pressão afim truncada em zero e barras tracionadas no lado que levanta. A rigidez relativa usa E_s/E_cs e a área resistente da rosca. O núcleo do retângulo, para a distribuição linear e N de compressão, satisfaz 6|M/N|/ℓx + 6|M_y/N|/ℓy ≤ 1.

Para cada combinação o motor integra a pressão no polígono e confere três resíduos nos eixos da entrada.

| Resíduo | Expressão | Unidade exibida |
| --- | --- | --- |
| R_N | ∫p dA − ΣTᵢ − N | kN |
| R_M | ∫xp dA − ΣxᵢTᵢ − M | kN·m |
| R_M,y | ∫yp dA − ΣyᵢTᵢ − M_y | kN·m |

A tolerância relativa é 10⁻⁷ com piso absoluto na unidade exibida. A escala de momento considera também a compressão vezes a maior dimensão da placa. A ausência de equilíbrio bloqueia a espessura e as verificações dependentes. A planta hachura o contato efetivo. O corte de pressão atravessa o centro da resultante e usa os valores do plano nas extremidades do corte.

## Flexão da placa e perfil U

Para as faixas em balanço, q = ∫p(u)·u du por unidade de largura. A espessura por flexão é √(4q/fyd). O motor procura o maior q entre todas as faixas de cada linha de engaste. Entre vértices do polígono e cruzamentos do engaste, q é um polinômio de grau até três. A busca inclui as extremidades e os pontos estacionários de cada intervalo. A região entre as mesas e as barras tracionadas têm verificações próprias. Para barras externas, a verificação local a 45° limita a largura efetiva pelas bordas e pelo espaçamento. A maior espessura exigida governa.

No U, o centro da placa coincide com o centroide calculado da seção. As mesas abrem para +y e o dorso permanece na mesma posição ao inverter o momento. A aproximação de meia seção I adota engastes no dorso e a 0,80 b_f dele. As faixas dos dois lados são calculadas separadamente. A integração de cada faixa tem solução analítica de referência nos testes. A representatividade desses engastes para a placa bidimensional, da deformabilidade da ligação e do acréscimo de tração por efeito de alavanca exige um modelo independente da ligação real. O programa registra essa pendência para o U e para o carregamento fora do eixo principal.

## Transferência de cortante

| Opção | Modelo |
| --- | --- |
| Somente atrito | Compara V com μC/γa2 e o limite de cisalhamento do apoio. Uma insuficiência reprova essa combinação. O programa desconsidera a contribuição de atrito sob tração axial. |
| Automático | Registra o mecanismo escolhido na combinação. Usa contato direto dos chumbadores quando o atrito não basta ou há torção. |
| Contato direto no furo | Adota engate desigual de uma ou duas barras conforme a disposição. Confere o aço, a flexão na região do graute, o contato e o rasgamento no furo. A folga radial entra na comparação com o limite de serviço informado. |
| Arruelas soldadas | Adota as barras engatadas pelo furo justo da arruela. Verifica a interação de tração e corte, a solda e, com Mz, a resultante de translação e torção em cada barra. |
| Placa de cisalhamento | Usa a componente normal à face e verifica o dispositivo e sua solda. A componente paralela ou uma orientação desconhecida na verificação real exige conferência da orientação e do caminho de carga. |

Na flexão da barra considera-se a seção resistente da rosca e o braço até o ponto de aplicação da cortante. A hipótese adotada é rotação livre, sem apoio lateral do graute, com acréscimo d_b/2 no concreto. Para o contato direto, o braço é e_n + t_p/2 + d_b/2. Para a arruela soldada, é e_n + t_p + t_a/2 + d_b/2. A barra combina F_t/A_se com M/(1,5 W), sendo W = πd_s³/32. O braço segue a hipótese de 6.2.2.3 da EN 1992-4 e o limite da seção segue a NBR 8800. Uma alteração no diâmetro pode alterar a flexão, a geometria, as reações, o embutimento e as soldas.

## Ancoragem no concreto

A ACI 318-19, capítulo 17, fundamenta as verificações em concreto fissurado de peso normal. O código distingue armadura de ancoragem e armadura suplementar. A primeira pressupõe barras dimensionadas e desenvolvidas para transmitir o esforço. A segunda seleciona a condição do fator de redução para os modos previstos na tabela 17.5.3(b). O fator para o aço depende da ductilidade da barra. O pryout usa a tabela 17.5.3(c).

- **Tração.** Entram o aço, o cone do grupo tracionado e, conforme o tipo, o apoio da cabeça, o gancho, o arrancamento lateral ou o limite do fabricante. A área projetada do cone é a união das projeções efetivas recortadas pelo bloco.
- **Resina.** São necessários a identificação e os dados do sistema avaliado para a barra, o embutimento e as condições de instalação. O cálculo considera τ_cr e τ_uncr, as verificações individual e de grupo, o efeito de borda e da excentricidade, os mínimos de espaçamento, borda e altura e a categoria de instalação. A maior tração sustentada de cálculo por barra é comparada com 0,55 φ N_ba. Uma resistência individual genérica entra apenas como limite adicional.
- **Pryout.** O concreto usa k_cp N_cb(g). Para o químico, a resistência nominal é k_cp mín(N_cb(g), N_a(g)). O fator de corte é aplicado uma vez. O subconjunto mobilizado acompanha o mecanismo de transferência. No contato direto verifica-se o subconjunto mais desfavorável.
- **Ruptura de borda.** O cálculo considera cada face, a fila solicitada, o menor c_a2, a excentricidade e′_V do grupo ativo e as componentes normal e paralela. Em bloco baixo e estreito, a redução de c_a1 considera a maior distância às duas bordas laterais, como determina 17.7.2.1.2. A componente paralela considera o limite de duas vezes a resistência normal e combina as duas componentes por uma interação elíptica conservadora. A interação de ancoragem da seção 17.8 usa as razões governantes de tração e corte.
- **Limites da ligação.** A torção global transferida ao concreto requer conferência específica. A resistência global e a armadura da fundação pertencem ao modelo do bloco. A compatibilidade da rigidez rotacional com a análise global e a elevação da tração por deformação da placa exigem avaliação quando aplicáveis.

## Soldas, busca e memorial

As soldas do pilar são grupos de segmentos de linha no contorno real de I/H ou U. Os segmentos menores que o mínimo geométrico saem das propriedades resistentes. A seleção da perna recalcula o grupo, seu centro, os momentos de inércia e o momento polar. As solicitações combinam a força normal, os dois momentos, as duas cortantes, a torção aplicada e a excentricidade do grupo. O metal-base é conferido por elemento, no pilar e na placa. O contorno das arruelas e os filetes da placa de cisalhamento têm verificações próprias.

A busca de menor massa recalcula cada combinação para cada par de diâmetro e espessura comercial. Somente um candidato que passa nas verificações e está livre de pendências pode ser sugerido. Os dados de um produto certificado permanecem vinculados à barra especificada. Uma busca sem solução significa que nenhum candidato avaliado atendeu sob aquelas hipóteses.

O memorial Word ou PDF é gerado pelo núcleo a partir do registro técnico. Os quadros separam esforços, resíduos de equilíbrio e resultados por combinação. As equações e figuras de cada verificação usam a combinação correspondente.

## Conferências reproduzíveis

Os testes de `tests/test_base_de_pilar_validacao.py` cobrem T01–T20 da auditoria. Incluem quadratura independente de p, xp e yp, inversão de momentos, rotação dos eixos, sensibilidade ao diâmetro e ao graute, mecanismos de cortante, grupo de soldas, ausência de dados e bloqueio da busca. O caso T20 usa quatro barras de ¾″ e espaçamento de 6″. A referência para a resistência de cálculo ao pryout é 28.497 lbf, com tolerância relativa de 0,2% para as conversões e os dados arredondados. Esse exemplo verifica o modo de ruptura de ancoragem descrito. [Relatório Hilti PROFIS, Waterfowl 2B03, pp. 7 e 10](https://files-ask.hilti.com/original/cd/cd1kczablk.pdf).

As verificações de base também estão em `tests/test_base_de_pilar*.py`. A importação é exercitada em `tests/test_placa_base_pilares.py`, a página em `tests/test_placa_de_base_pagina.py` e a exportação em `tests/test_memorial_trecho.py`. O cálculo de ancoragens e as hipóteses do braço têm como referências a [ACI 318-19, capítulo 17](https://www.ocf.berkeley.edu/~chiep/wp-content/uploads/2024/01/CE-123-ACI-318-19.pdf) e a [nota técnica Hilti que aplica a EN 1992-4, 6.2.2.3](https://www.hilti.ch/medias/sys_master/documents/hf4/h84/10211081748510/HCW-FinalWhitePaper-SOFA-EN-04-2024-Technical-information-ASSET-DOC-23194478.pdf).
