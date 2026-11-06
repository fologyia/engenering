# Estática e resistência no Assistente de cargas

São 15 casos para a pergunta do dia a dia: as forças que chegam, e se a peça aguenta. O painel do
Assistente de cargas abre nesta área. Os módulos estão em `core/elementos_parafusos.py`,
`core/elementos_vigas.py`, `core/elementos_barras.py` e `core/elementos_estatica.py`, e os desenhos
feitos com os números do cálculo em `core/desenho_estatica.py`.

Nenhum solver novo foi escrito onde o programa já tinha um: a viga usa `core/beam_solver.py`, o
pórtico usa `core/portico_plano.py` e o perfil usa `core/verificacao_barras.py`. A diferença é a
entrada reduzida e a resposta ao lado dos dados.

## Painel

- Sem caso aberto, a página mostra a busca, seis perguntas comuns com croqui e todos os casos em
  abas por área, com os grupos em cartões.
- Com um caso aberto, os dados ficam à esquerda e a resposta à direita. Ao mudar um número, o
  desenho, a faixa de status e os números mudam na mesma altura da tela.
- `Campo` aceita `colunas`: vira uma tabela em que o usuário acrescenta e tira linhas. A tabela
  guarda as edições como diferenças em relação à base, então a base fica parada em
  `chave::base` enquanto ela está na tela, e as últimas linhas ficam em `chave::ultimas` para ela
  renascer quando o usuário volta ao caso.
- `Campo.opcoes_de` busca a lista na hora, para o catálogo de perfis que o usuário aumenta.
- `Resultado.figuras` traz PNGs: o primeiro aparece no lugar do croqui fixo, e todos vão para o Word.
  Os gráficos também vão para o Word, desenhados só na hora de gerar o documento.

## Parafusos e roscas

**Parafuso sob força axial.** Com pré-carga, segue Shigley, cap. 8:

- rigidez do parafuso: `k_b = A_d·A_t·E/(A_d·l_t + A_t·l_d)`;
- rigidez das peças: ajuste de Wileman, Choudury e Green, `k_m = E·d·A·exp(B·d/l)`, com A e B por
  material. Sai também o tronco de cone de Shigley, `k_m = 0,5774·π·E·d/(2·ln(5(0,5774·l + 0,5·d)/
  (0,5774·l + 2,5·d)))`. Se os dois diferem mais de 20 %, a tela avisa;
- `C = k_b/(k_b + k_m)` e `F_b = F_i + C·P`.

A dispersão do aperto vem da Tabela 3 de SAND2008-0371. O parafuso se confere com a maior pré-carga,
a separação com a menor, e o fator de segurança vai só na carga externa, como manda o item 3 da guia.

**Arrancamento da rosca.** Áreas de cisalhamento do Machinery's Handbook (SAND2008-0371, Eq. 34 a 40),
nas dimensões de mínimo material de 6g e 6H. As tolerâncias saem das fórmulas da ISO 965-1, que dão
os valores das tabelas a poucos micrômetros (M10 conferida em teste). O teste reproduz o exemplo do
apêndice C da guia: 5/8-11 SAE 5 em ferro fundido pede 0,9 in.

**Torque de aperto.** `T = K·F·d`, com K da Tabela 8-15 de Shigley. A tensão combinada no aperto
considera metade do torque passando pela rosca e compara com 0,90·S_y, como recomendação.

**Grupo de parafusos.** Distribuição linear a partir do centroide do grupo, nos dois eixos, com o
cortante e o torque no plano da junta.

## Vigas e flexão

**Viga: reações e momentos.** Oito esquemas de apoio e cargas por tabela. A flecha é verificada por
trecho, e no balanço o L é o dobro do comprimento (NBR 8800, Tabela C.1, nota a). Os perfis mais
leves da família saem por reescala: com EI constante, M e V não mudam com o perfil e a flecha cai com
a inércia, então não é preciso resolver a viga de novo.

**Flexão de uma seção.** `σ = N/A ± M/W` e o W necessário. A seção é cortada em faixas
(`core/geometria_da_secao.py`): com b(y) saem Q(y), `τ = V·Q/(I·b)` ao longo da altura e von Mises em
cada ponto, com σ e τ do mesmo ponto. Isso vale para I, U, T, tubos e círculo, e a integral de τ·b
devolve V. Num perfil I, o ponto mais solicitado pode ser a junção da alma com a mesa, onde σ ainda é
alto e τ já cresceu: com a W 250 x 28,4, M = 50 kN·m e V = 100 kN, a tensão normal e o cortante passam
e von Mises não. Saem também a linha neutra, o momento e o cortante admissíveis, `M_y`, `M_p` e o
fator de forma, e a comparação entre os dois eixos do perfil. O contorno não tem os raios de
concordância, e na mesa `V·Q/(I·b)` é a média vertical, não o caminho real do cisalhamento. Sem a
forma (propriedades informadas), a conta volta a `V/A_v` e não há von Mises ao longo da altura.
A mesma figura (`core/desenho_flexao.py`) aparece em Viga de seção retangular, Seção I, Perfil U e
Perfil tubular; neste último, a torção entra como τ uniforme.

**Perfil de aço pela norma.** O mesmo motor das barras do modelo, com a norma escolhida.

## Barras e estruturas

**Barra sob força axial e barra em torção.** Trechos em série, com a ponta da direita livre ou presa,
por rigidez direta. A temperatura entra como esforço inicial `E·A·α·ΔT`.

**Coluna simples.** Euler e Johnson (Shigley, Eq. 4-43 e 4-48), com K da Tabela E.1 da NBR 8800.

**Treliça plana.** Rigidez direta com dois graus de liberdade por nó. Testada contra o método dos nós
e contra o trabalho virtual.

**Pórtico simples ou console.** `core/portico_plano.py`. O deslocamento é procurado ao longo das
barras, não só nos nós: na viga de um pórtico, o maior fica no meio do vão.

## Peças, seções e chapas

**Equilíbrio de uma peça.** `core/equilibrio_corpo.py`. Preenche desenhando: a prancheta recebe a
peça, os apoios e as cargas, e as reações voltam na hora. Cada apoio entra com as forças que consegue
fazer, e as três equações viram uma matriz 3 × n, lida por valores singulares:

- o posto diz quantas reações a estática define; quem tem componente zero no espaço nulo tem valor
  único mesmo em peça hiperestática (a força horizontal nas duas dobradiças de uma tampa);
- o espaço nulo da transposta diz para onde a peça foge quando falta apoio, giro em torno de um ponto
  ou translação, e a carga projetada nele diz se ela empurra para esse lado;
- três reações concorrentes ou paralelas contam três incógnitas e ainda assim não seguram: o posto
  pega isso sem caso especial;
- apoio simples, atrito e cabo são de um lado só. Na peça isostática a linha reprova quando o apoio
  precisaria puxar ou o cabo empurrar. Com um grau hiperestático, procura a divisão que respeita as
  restrições; com dois ou mais a divisão mostrada é a de menor esforço e a linha só pede atenção.

Os esforços N, V e M saem do equilíbrio do pedaço à frente do corte. A linha do corte é infinita: se
atravessa mais de um trecho, o programa avisa que o valor é a soma dos pedaços.

Conferido contra contas de mão e, em peças sorteadas, contra as propriedades que valem sempre: ΣF e
ΣM somados de novo, fora da matriz; o mesmo N e M pelos dois lados do corte; reações iguais com a peça
girada e transladada; resposta igual em qualquer unidade.

Limites: peça rígida no plano; sem mecanismo de várias peças (cada corpo é um caso); sem folga nem
sequência de carga; a distribuída vale por comprimento da peça, sem opção por projeção.

**Seção montada.** Teorema dos eixos paralelos, com retângulos, círculos e furos, além dos eixos
principais. O resultado segue para uma viga ou uma coluna.

**Chapa tracionada com furo.** Seção bruta ao escoamento e seção líquida à ruptura. `K_t` do Chart 4.1
de Peterson (Pilkey), na tensão líquida, mostrado sem reprovar: sob carga estática em material dúctil
o pico se redistribui.

## O que não é feito

- A resistência da rosca não considera a dilatação da porca fina nem a flexão dos filetes (fatores
  C1 e C3 da VDI 2230): as fórmulas exatas não foram confirmadas em fonte aberta. A conta vale para
  parede grossa e diz isso na tela.
- A regra prática de engrenamento (1 d em aço e 1,5 d nos materiais mais fracos) é só a segunda
  opinião: quem manda é a conta.
- O parafuso sob força axial é estático. Fadiga de parafuso fica na página Projeto de parafusos.
- O grupo de parafusos não acha a linha neutra de uma placa sem pré-carga: nesse caso, a tela manda
  para a página Placas de base ou Projeto de parafusos.
- A viga é de seção constante e não verifica a flambagem lateral: a tela avisa em perfil aberto e
  leva ao caso Perfil de aço.
- O pórtico é de primeira ordem, sem flambagem, e a treliça usa a mesma seção em todas as barras.

## Fontes consultadas

- Brown, Morrow, Durbin e Baca, *Guideline for Bolted Joint Design and Analysis*, SAND2008-0371.
- Shigley, *Elementos de Máquinas*, cap. 3, 4 e 8.
- Wileman, Choudury e Green, em ASME J. Mech. Design (1991); constantes conferidas em RoyMech.
- ISO 965-1, ISO 724 e ISO 898-1.
- ABNT NBR 8800:2008, Anexo C e Tabela E.1, conferidos no PDF da norma.
- Pilkey, *Peterson's Stress Concentration Factors*, Chart 4.1.
