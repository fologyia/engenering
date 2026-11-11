# Montador de fórmulas

A página liga blocos numa prancheta e devolve a equação isolada na grandeza escolhida: a altura, o
diâmetro, o momento, a carga, o limite do material ou o fator de segurança. Os números são opcionais.
Letra sem valor continua na fórmula, e assim sai `h = 1,6·√M` quando só o momento ficou em aberto.

## Como se usa

A tela tem três colunas: a biblioteca, a prancheta e o inspetor. Quem clica num bloco da biblioteca
já recebe a fila ligada: **Seção → esforços → critério → Em função de**. Um esforço novo entra antes
do critério, e apagar um esforço do meio não quebra a fila. As bolinhas ligam à mão também: arraste de
uma à outra, ou clique em uma e depois na outra. Puxar uma entrada já ligada solta o fio. Delete apaga
o selecionado, as setas andam de um bloco ao outro, e Enter abre o conjunto.

**O número no próprio cartão.** Dois cliques num número do cartão (M_x = 2 kN·m) abrem ali a caixinha
das medidas dos desenhos: vale conta (300/2), unidade (2000 N·m num campo em kN·m) e valor relativo
(+10, *1,2). Enter confirma, Esc desiste, Tab vai ao número seguinte do mesmo bloco, e campo vazio
volta a ser letra. Enter ou F2 com o bloco selecionado abre o primeiro número. A letra pedida não abre:
o valor dela sai da conta. O inspetor continua valendo, e os dois mostram o mesmo número.

**Um Ctrl+Z só.** Ctrl+Z desfaz e Ctrl+Y refaz tudo, na ordem em que foi feito: bloco, fio, número
digitado no cartão ou no inspetor, escolha de um bloco, Limpar e modelo aberto. O histórico guarda a
montagem inteira (blocos, fios e valores juntos) e mora no Python, junto com os valores. Por isso cada
Ctrl+Z refaz a conta e tem a mesma espera curta de mudar um valor; a linha de baixo da prancheta diz o
que voltou ("Desfeito: S_y voltou a 250 MPa."). Enquanto a conta volta, a prancheta só deixa mover a
vista: um gesto novo sairia do desenho de antes. Os pedidos vão numerados, cada um com os de antes que
ainda não voltaram confirmados, porque o Streamlit junta duas rodadas pedidas ao mesmo tempo e a
primeira se perderia; o que ficar sem resposta vai de novo.

**Copiar e colar.** Ctrl+C e Ctrl+V, ou o botão de duplicar acima da prancheta, copiam o bloco
selecionado (ou os marcados com Shift). A cópia entra na fila depois do original, como um bloco novo da
biblioteca, e leva os fios de dentro do grupo e os que trazem número ou material de fora. Ela nasce com
os números do original: o segundo trecho já vem com D₂ e L₂ iguais aos do primeiro, e só se muda o que
for diferente. Cada número copiado fica marcado "Copiado de L" no inspetor, no arquivo e no Word, e o
cartão leva a etiqueta CÓPIA, até alguém mudar o número ou confirmar que ele está certo (Enter na
caixinha sem mudar nada, ou "Os números copiados estão certos" no inspetor). O que a cópia já traria
sozinha, o padrão do programa e o da tabela, fica com a procedência de lá.

**O número segue o bloco.** O segundo bloco igual usa outra letra (M₂, L₂), e a letra sai da ordem dos
fios. Apagar o primeiro faz o segundo virar M, e os números vão junto com ele: o bloco que ficou não
passa a mostrar os do bloco apagado.

Há quatro tipos de fio. O azul leva a seção e as tensões somadas até ali. O laranja troca uma letra pela
fórmula de outro bloco: ligando a viga na flexão, M vira F·L/4, e a equação passa a falar em F e L. O
marrom leva o material, com S_y, S_ut, E e G no mesmo fio. O escuro leva a condição do critério até o
resultado. Dá para ligar vários critérios no mesmo resultado: von Mises e flecha, por exemplo, e a
página diz quem manda.

Selecionar uma ligação muda a biblioteca: ela passa a mostrar primeiro o que cabe ali, e passar o
cursor mostra a prévia na prancheta. Clicar insere o bloco no meio do fio, que vira origem → novo →
destino. O resto do desenho não anda.

**A biblioteca esconde o que não serve.** Com blocos na prancheta, a biblioteca tira o que não cabe
na montagem (`core/montador_uso.py`). Duas coisas decidem:

- **A forma da seção.** Pressão interna só vale em tubo. As peças do eixo, a potência, a engrenagem,
  a polia, a inclinação, a rotação crítica e o entalhe valem só em seção redonda, maciça ou tubo.
- **O tipo de peça.** Eixo que gira não se mistura com tubo com pressão nem com coluna comprimida
  (flambagem de Euler). Tubo com pressão e coluna se misturam: a camisa de um cilindro hidráulico tem
  pressão por dentro e flamba.

Funciona nos dois sentidos. Com perfil I e flambagem de Euler, somem a pressão interna e as peças do
eixo. Com uma engrenagem, somem o perfil I, a seção retangular, a desenhada, a pressão e a flambagem.
A fadiga com "Eixo girando" conta como peça de eixo.

As seções não escondem umas às outras: a viga em perfil I e o pino redondo que a segura cabem na
mesma montagem, e com os dois as peças do eixo voltam. Bloco dentro de um conjunto também conta, e um
conjunto salvo some quando algum bloco dele não cabe.

Esconder não proíbe. O alto da lista diz quantos blocos ficaram de fora, e **Mostrar todos** traz
todos de volta, em cinza. Passar o cursor num bloco em cinza mostra o motivo. Quando a montagem muda,
a biblioteca volta a esconder. Com uma ligação selecionada, o inspetor também deixa de fora o que não
serve e diz quantos. A parte de fluidos não esconde nada, porque tanque, tubo e canal se misturam.

## O inspetor

No topo fica sempre a **resposta** (por exemplo, h ≥ 37,95 mm), quem manda e, com valor adotado,
se ele passa. Assim dá para mudar um número e ver o efeito sem rolar a página. Sem todos os números,
o quadro diz quais faltam; sem conta, diz o motivo.

Abaixo dele, o inspetor mostra o que está selecionado, e cada coisa do seu jeito:

- **Nada selecionado:** todos os valores da montagem.
- **Bloco:** os valores só dele, o uso do critério, de quem recebe e para quem envia.
- **Ligação:** o que passa no fio, medido nos números atuais (esforços somados e tensões de cada ponto),
  e a conferência de tipo, grandeza e laço, calculada na hora.
- **Conjunto:** os valores de dentro, sem precisar abrir, e as entradas e saídas públicas.
- **Em função de:** a resposta, quem manda e o uso de cada condição.

Abaixo dos resultados, "De onde veio cada valor" diz a procedência campo a campo (digitado, exemplo do
modelo, padrão do programa, tabela, copiado de outro bloco), e a página avisa o que mudou na resposta, e
por causa de qual valor.
Rastrear este resultado acende na prancheta o caminho de quem decide.

Modelo completo não quer dizer aprovado. A faixa de cima da prancheta só diz que a conta fecha, e o
resultado é sempre pré-dimensionamento.

## O que a conta faz

**Ponto a ponto.** σ e τ máximos raramente caem no mesmo lugar. Cada seção lista os pontos que importam
(fibra externa, linha neutra, junção alma-mesa) e quanto cada esforço vale em cada um. O critério roda
em cada ponto, e somar os máximos, que daria uma tensão que não existe na peça, não acontece. A
exceção é a torção de seção retangular: o τ do meio do lado maior vale nos dois pontos, a favor da
segurança.

**Isolar.** `forma_fechada` reduz a equação a polinômio em x^k. Até grau 2 sai a fórmula, e acima disso
fica a equação, com a raiz achada por número (varredura em escala log e bisseção). Quem pede um mínimo
(medida da seção, limite do material) manda pelo maior; quem pede um máximo (carga, fator de segurança)
manda pelo menor. Mínimo acima de máximo vira aviso de que nenhum valor atende.

**Módulos.** A sympy não sabe que h − t_f é positivo e deixa √(x²) como |x|, o que trava o isolamento.
`limpar` resolve o sinal numa seção válida de amostra. No estado biaxial o módulo fica, porque σ_x − σ_y
pode mesmo dar negativo.

**Validade.** Cada seção diz o que precisa ser verdade (d > 2·t, lado maior, parede fina) e o programa
confere com os números da resposta. Euler ligado ao material confere a esbeltez de transição.

## Momento em XX e YY, por valor ou por força vezes distância

Há um bloco de flexão para cada eixo. XX flete no plano de h, com M_x, e YY no plano de b, com M_y. Em
cada um, "Como entra o momento" tem três formas: o valor do momento; força × distância, com F_xx e
d_xx (ou F_yy e d_yy) no lugar de M, o que deixa pedir a força máxima ou a distância máxima; e força ×
distância com a cortante da força. A força que tem braço também corta a seção: na segunda forma a
página avisa, a não ser que exista um bloco de cortante depois dela.

**Canto.** Com M_x e M_y juntos, o pior ponto da seção retangular é o canto, onde as duas tensões somam;
ali não há cortante nem torção. Sem um dos momentos o canto nem aparece. No perfil I é a ponta da mesa.

**Seção redonda.** Não há canto: os momentos se compõem em M_r = √(M_x² + M_y²), e a fibra fica na
direção da resultante. Por isso a cortante na fibra é a parte de V ao longo da tangente: τ = 4·V_t/(3·A),
com V_t = (V_x·M_x + V_y·M_y)/M_r, pelo pior sinal. Com M_x e V_y juntos dá zero, como na conta clássica.
Com M_x e V_x, que estão em planos diferentes, soma na fibra.

**Cortante nos dois eixos.** V_y acompanha M_x, e V_x acompanha M_y. No centro da retangular as duas são
perpendiculares e entram pela raiz da soma dos quadrados, com ponto próprio. No perfil I, V_x fica toda
nas mesas.

## Procurar em faixas

Uma equação isola uma letra. Com até três incógnitas, ou com equação sem forma fechada, o interruptor
"Procurar em faixas" testa: cada incógnita recebe de, até e passo, e a grade varre as combinações. O
limite é de 250 mil combinações. Depois o refino faz uma grade pequena em volta da melhor, só encolhendo
quando ela fica por dentro, até a largura cair abaixo de 10⁻⁷ do valor.

Com mais incógnitas que condições não existe um ponto só, e sim uma família inteira que dá 100 %. Por
isso a busca precisa de um objetivo: a menor área da seção, o maior ou o menor valor de uma letra, ou
todas as condições no limite. Este último é o ponto de convergência no sentido estrito, em que as
condições encostam juntas, e só é único com tantas condições quanto incógnitas; se faltarem condições,
a página avisa. Com b e h em aberto, por exemplo, fibra e linha neutra fixam b·h² e b·h, e sai um par só.

As combinações que ferem a validade da seção (parede maior que o raio, lado maior trocado, Euler em
coluna curta) ficam de fora. Empate no objetivo se decide pela menor área. A página mostra os melhores
da grade, que respeitam o passo pedido, e o ponto refinado, que não respeita: o primeiro serve para a
medida comercial. Resposta encostada na borda recebe aviso, porque ampliar a faixa pode melhorá-la.

## Seção desenhada

A seção da prancheta só tem números, então a letra é a escala `s`: multiplica todas as medidas juntas.
Os pontos são a fibra, a linha neutra e toda altura onde a largura pula mais de 20 %. Com M_y entram a
fibra de YY e os cantos, escolhidos entre os pontos da borda, em módulo: seção sem simetria fica a favor
da segurança. Em torção vale o τ máximo em todos os pontos, a favor da segurança.

## Conjuntos

Shift + clique marca vários blocos, e Agrupar junta tudo num cartão só. O que fica sem fio por dentro
vira entrada ou saída pública, e o inspetor escolhe quais ficam de fora. Duplo clique abre o conjunto,
e a trilha acima da prancheta volta. Salvar na biblioteca guarda em Meus conjuntos, para usar em outras
montagens. O motor abre os conjuntos antes de calcular, inclusive um dentro do outro.

## Salvar, registrar e referências

A aba "Salvar, abrir e registrar" baixa a montagem em JSON, abre um arquivo baixado e registra o cálculo
no projeto ativo. O registro guarda a montagem inteira, então dá para reabrir, e entra na Central de
validação como qualquer outro cálculo.

O bloco **Cálculo registrado** lê um resultado de outro registro pelo identificador e pela assinatura,
e não pelo nome. Se o registro mudar, a Central marca o cálculo como desatualizado, e o Montador mostra o
valor velho e o novo; quem atualiza é o usuário, porque a troca muda a conta. Registro apagado ou de
outra grandeza também aparece no bloco, com a mensagem de cada caso. O que vem de fora nunca muda sozinho.

## Comparar duas montagens

"Guardar como A" fotografa a montagem inteira: blocos, fios e números. Depois é só mudar o que quiser na
prancheta (aço ou alumínio, uma seção ou outra, com cortante ou sem) e a página põe A e a de agora lado a
lado: a resposta, quem manda, o uso de cada condição, a área da seção, cada número que mudou e os blocos
que só uma das duas tem, com a diferença em % (no uso, em pontos percentuais). A conta de A é refeita uma
vez e guardada enquanto A não muda. "Voltar para A" põe A de volta na prancheta e entra no histórico, e
por isso o Ctrl+Z desfaz; "Trocar A pela de agora" guarda a de agora no lugar; "Esquecer A" tira a
comparação. A vale para a sessão, e cada parte do Montador tem a sua.

## Levar para outras análises

Com a conta fechada, o Montador leva o estado de tensão de um ponto da seção para a **Análise estática**
e para o **Círculo de Mohr**, e a fadiga para a **Análise de fadiga**, pelas mesmas chaves que o
Assistente de cargas e Vigas e eixos já usam (`core/montador_repasse.py` faz a conta;
`components/repasse_do_montador.py`, o envio e o aviso).

- **Ponto:** a lista traz os pontos da seção que chega ao critério de quem manda, depois de todos os
  esforços e da concentração de tensão, e começa no de maior von Mises. Vão σx, σy e τxy, com a resposta
  no lugar da letra pedida. Num tubo sob pressão, σy é a tensão circunferencial.
- **Fadiga:** só com o bloco Fadiga de eixo, que é quem separa a parte alternada da média. Vão σa' e σm'
  como o Montador calculou, já com K_f e K_fs, e o d da seção redonda para o fator de tamanho. Lá o
  entalhe fica em "Sem entalhe", para não contar duas vezes, e o carregamento em Flexão, de fator 1,
  como no von Mises das parcelas. O material e os fatores de Marin escolhem-se na Análise de fadiga.
- **Origem:** se a montagem foi registrada no projeto, vai junto o registro dela, e o cálculo de destino
  guarda essa origem. Sem registro, a página diz que os números vão sem origem rastreável.
- **Aviso quando muda:** cada envio fica guardado com os números que foram. A cada rodada o Montador
  refaz os números do mesmo ponto, e a página que recebeu avisa "a montagem mudou depois do envio: σx foi
  de 166,7 para 233,3 MPa", com "Trazer os números novos" e "Manter os de antes". O aviso só vale
  enquanto a página ainda mostra o que o Montador mandou: se a pessoa mudou os números lá, ou outra
  página mandou depois, ele não aparece.

## Peças do eixo

Para montar um eixo inteiro na prancheta: a engrenagem ou a polia dão as forças, as vigas dão o
momento de cada plano, e as peças que ficam no eixo entram com as condições delas. As contas são as do
Assistente de cargas, escritas em letra, e a Central de validação confere os dois caminhos.

- **Engrenagem:** da potência e da rotação (ou do torque T) e do diâmetro primitivo saem F_t = 2·T/d,
  F_r = F_t·tg φ_n/cos ψ e F_a = F_t·tg ψ. A radial e a tangencial ficam a 90°: cada uma vai para um
  plano, e a seção redonda junta as duas.
- **Polia e correia:** a carga no eixo pela equação de Euler (F₁/F₂ = e^(μ·θ), com o canal em V), sem a
  parcela centrífuga. A pré-tensão instalada acima do mínimo carrega mais o eixo.
- **Vigas novas:** carga fora do meio (a_m é a distância até o apoio mais perto; acima de L/2, aviso),
  duas cargas (o momento sob a força escolhida e as duas reações), biapoiada com balanço (a polia fora
  dos mancais) e engastada e apoiada, com carga no meio ou distribuída. As vigas de antes ganharam a
  bolinha de entrada da força e as saídas R (reação) e θ·EI (inclinação vezes E·I).
- **Par de engrenagens:** o par inteiro num bloco: as forças no eixo, como o bloco Engrenagem, e o
  dente, por flexão de Lewis no pinhão e na coroa (com o número virtual de dentes z/cos³ψ) e por
  contato de Hertz no flanco, com K_o, K_v pela fabricação e K_m, como no Assistente de cargas. Isola o
  módulo, a largura ou a dureza; o diâmetro primitivo sai do módulo e dos dentes, e por isso a força e
  o dente nunca usam diâmetros diferentes. A potência e a rotação podem ser do eixo do pinhão ou da
  coroa. Fora de 8 a 16 módulos de largura, com poucos dentes ou acima de 25 m/s, a página avisa.
- **Engrenagem cônica:** par de dente reto com os eixos a 90°, com as forças no primitivo médio. No
  eixo da coroa, a radial é a axial do pinhão e a axial é a radial dele. A saída r_m é o raio médio,
  o que vai na coluna "Raio da axial" do eixo com trechos.
- **Chaveta:** DIN 6885 pelo diâmetro (b, h e t₁ mudam com d) ou informada; corte e esmagamento no eixo,
  no cubo e na chaveta, com K_s, pontas e uma ou duas chavetas, como na DIN 6892. Passou de 1,5·d, aviso.
- **Cubo prensado:** Lamé com a interferência da NBR 6158 (H7/p6 a H7/u6, pelo diâmetro) menos o
  alisamento da rugosidade; transmissão por atrito com a menor interferência e escoamento do cubo e do
  eixo com a maior.
- **Rolamento:** ligue a reação R (uma por plano, que se somam como vetores) e diga a vida em horas: sai
  a capacidade C que o rolamento precisa ter, pela ISO 281, com X e Y de Shigley nas esferas de sulco
  profundo. Também confere a segurança estática s₀.
- **Inclinação:** θ = θ·EI/(E·I) no mancal ou na engrenagem, com os limites da Tabela 7-2 de Shigley.
- **Rotação crítica:** Dunkerley com o eixo biapoiado e uma peça entre os mancais ou em balanço. Fica
  abaixo da real, a favor da segurança.
- **Fuso (parafuso de potência):** a conta do fuso do Assistente de cargas (Shigley, cap. 8) em
  letra: torque para subir T = F·d_m/2·(ℓ + π·μ·d_m·sec α)/(π·d_m − μ·ℓ·sec α), mais o colar; von Mises
  no corpo pela raiz d − p; pressão, flexão (38 % da carga no primeiro filete) e corte nos filetes do
  fuso e da porca; flambagem pela raiz, com Johnson na coluna curta e Euler na longa
  (`TensaoCritica`, a mesma função do Assistente). A saída T vai ao motor ou à chaveta. Opções: rosca
  trapezoidal ISO, ACME ou quadrada, colar com ou sem atrito, fuso só tracionado (sem flambagem) e
  exigir que a rosca trave sozinha (vira condição; senão, só avisa). Como a flambagem do fuso já está
  dentro do bloco, a biblioteca esconde o bloco Flambagem de Euler numa montagem com fuso.

Os modelos "Eixo com engrenagem", "Par de engrenagens: módulo do dente", "Pinhão cônico em balanço",
"Rigidez do eixo", "Polia em balanço", "Chaveta: comprimento mínimo",
"Cubo prensado: comprimento do ajuste", "Rolamento: capacidade C" e "Fuso: diâmetro mínimo" já
abrem montados. O caso de aceite "Fuso Tr 40×7, carga máxima" confere a carga máxima do
Montador contra a do Assistente (35 317,8 N, governada pela pressão nos filetes).

## Eixo com trechos

O bloco **Eixo com trechos** faz o eixo inteiro numa conta só. As duas tabelas ficam logo abaixo da
prancheta, com o desenho do eixo em escala:

- **Trechos**, da esquerda para a direita: comprimento, diâmetro como múltiplo de d, o entalhe do trecho
  (liso, rasgo de chaveta, canal de anel, furo, cubo prensado) e o raio do canto no fim (r/d). O ressalto
  entre dois trechos entra sozinho.
- **Elementos:** um mancal A, um mancal B e as cargas, com o sentido da força em cada plano, o torque que
  entra (um elemento) e os que saem, a força axial com o raio dela e a massa da peça.

Cada força vira uma letra com bolinha no bloco (F_v1, F_h1, T_e1, F_a1), e a engrenagem liga direto
nelas. As posições e as relações são números; as forças e o d ficam em letra. Como todos os diâmetros
são proporcionais a d, o momento de cada seção e a inclinação saem como uma soma das forças com pesos que
só dependem do arranjo, calculados uma vez pela integração exata de M/k⁴ trecho a trecho
(`core/montador_eixo.py`). Por isso a conta acha o d que faz o eixo inteiro passar e diz em qual seção
ele quebraria primeiro.

As seções conferidas são o ombro do lado fino, onde o raio do canto concentra a tensão, e o entalhe de
cada trecho nos pontos de carga: entre dois pontos de carga o momento de cada plano é uma reta e o
torque é constante, e o pior fica sempre num desses pontos. Em cada seção entram fadiga e escoamento no
primeiro ciclo, com o k_b do diâmetro dela; nos mancais e nas engrenagens marcadas, a inclinação; e no
eixo todo, a rotação crítica por Dunkerley, com a massa do eixo e das peças. As saídas R_A e R_B levam
as reações para o rolamento.

Com um diâmetro só, o d por DE-Goodman e a inclinação no mancal batem com o Eixo de transmissão do
Assistente de cargas (casos de aceite na Central).

## O que mais pesa

Com a resposta pronta, cada número sobe e desce 10 %, um de cada vez, e a conta roda de novo
(`core/montador_sensibilidade.py`). A tabela mostra quanto a resposta muda, do que mais pesa ao que
menos pesa, e avisa quando outra condição passa a mandar. Os que quase não mexem (menos de 0,1 %)
aparecem numa linha só. Só entram as condições perto do limite (uso de 75 % para cima): uma com folga
maior não chega a mandar com 10 % a mais numa letra.

## Fórmula própria

O bloco **Fórmula própria** recebe uma conta digitada no inspetor. Há três formas:

- `q*L^2/8` entrega um valor por uma bolinha, para ligar em outro bloco.
- `M = q*L^2/8` entrega o mesmo valor, com nome, e também uma equação para o bloco Em função de.
- `M*c/I <= S_y/n` é uma condição, como a de um critério.

Cada letra vira uma bolinha de entrada, e quem não está ligado vira campo de valor. Letra igual à do
programa (S_y, M_x, n, d) usa o mesmo valor e a mesma unidade dos outros blocos. Letra nova recebe uma
sugestão pelo costume (M é momento, I é inércia, c é medida), e o inspetor deixa trocar. Com isso a
página confere a unidade: as parcelas somadas e os dois lados do sinal precisam bater, e o resultado sai
na grandeza que a conta der. Função só recebe número puro.

O texto vem de quem digita e vai para arquivos que circulam, então não vira código: o leitor é próprio,
sem `eval` nem `sympify`, e só conhece números, letras, `+ − * / ^`, parênteses, `sqrt`, `sin`,
`cos`, `tan`, `exp`, `ln`, `log10` e `abs`. O resto é recusado dizendo onde parou, como `2q` (falta
o sinal de vezes) ou `log` (que pede `ln` ou `log10`). Fórmula guardada num conjunto vai junto para a
biblioteca.

## Escolher do catálogo

O interruptor abaixo das condições testa as peças que existem para comprar, em vez de uma faixa de
números: perfil I (W, HP e I), tubo circular, barra redonda e barra chata na parte de materiais, e os
tubos comerciais na de fluidos. Cada peça troca as letras do bloco dela, e a lista volta da mais leve
para a mais pesada (ou do menor diâmetro, nos tubos), com o uso e quem manda. "Usar esta peça"
preenche as medidas, e a letra pedida vira o valor adotado.

Perfil I entra pelas quatro medidas, sem os raios de concordância: a inércia fica um pouco abaixo da
real, a favor da segurança. Com equação na montagem, cada peça dá um resultado diferente, e o catálogo
pede para escolher a peça no bloco.

## Fadiga completa

Três blocos fazem a fadiga de eixo com as mesmas contas do Assistente de cargas
(`core/elementos_eixos.py` e `core/fatigue.py`), e há caso de aceite que confere os dois caminhos:

- **Limite de fadiga:** S_e = k_a·k_b·k_c·k_d·k_e·k_div·S_e', com acabamento, fator de tamanho pelo
  diâmetro (ou informado), carregamento e confiabilidade. Com d em aberto, k_b acompanha a resposta.
- **Entalhe:** K_f e K_fs do ressalto (curvas de Peterson e Neuber), da chaveta, do canal de anel, do
  furo e do cubo prensado. Sem raio definido, q fica em 1, a favor da segurança.
- **Fadiga de eixo:** DE-Goodman, DE-Gerber, DE-Soderberg ou DE-ASME elíptico, com vida infinita ou
  finita em N_c ciclos (S_f na reta log-log de 0,9·S_ut em 10³ a S_e em 10⁶). Com o material ligado,
  confere também o escoamento no primeiro ciclo.

## Word e Excel

Na aba "Salvar, abrir e registrar", com a conta completa, saem dois arquivos:

- **Word:** resultado, o desenho dos blocos, os dados com a origem de cada valor, as condições, o
  passo a passo, as hipóteses e o que não passou. As fórmulas vão como equação do próprio Word, que dá
  para editar.
- **Excel:** cada letra numa célula com nome (`v_S_y`), e cada condição com as duas fórmulas e o uso.
  Mudou um dado, a conta acompanha. O fator de atrito vai por Swamee-Jain, a cerca de 1 % de
  Colebrook, e a planilha avisa. O que vem de curva ou de tabela (K_t de ressalto, as medidas da
  chaveta, a interferência do ajuste, o X e Y do rolamento) fica com o número do programa.

## Como acrescentar uma equação

Basta um `Bloco` em `BLOCOS`, em `core/montador_blocos.py`: a prancheta, os campos e a conta leem dali.

    origem(
        "balanco_ponta",
        "Balanço: carga na ponta",
        "Viga engastada com uma força na ponta livre.",
        "M = F·L · V = F",
        (g.F, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, l_: f * l_),
            "V": ("V", g.FORCA, lambda f, l_: f),
        },
    )

Letra nova vai em `core/montador_grandezas.py`, e seção nova em `core/montador_secoes.py`, dizendo os
pontos dela. O teste `test_todo_bloco_tem_o_que_a_tela_precisa` confere o catálogo.

## Casos de carga

A mesma peça com cargas diferentes, como partida e regime, ou cheio e vazio. Em **Casos de carga**,
logo abaixo da resposta, ligue **Mais de um caso de carga**:

- Os valores do inspetor são o primeiro caso. Dê um nome a ele, como Regime.
- Escolha as **letras que mudam** de um caso para outro. O programa já sugere os esforços (força,
  momento, pressão, potência). A letra pedida nunca muda: ela é a resposta.
- Na tabela, uma linha por caso a mais. Célula vazia vale o número do primeiro caso. Até 12 casos.

Na conta, cada caso entra com as condições dele, com o nome na frente (“Partida: von Mises na fibra
externa”). A resposta sai do pior caso, do mesmo jeito que sai a condição que manda num caso só. Um
quadro mostra quanto cada caso pede e qual manda.

O resto da página vê todos os casos: o valor adotado é conferido em todos, a busca em faixas e o
catálogo só aceitam o que passa em todos, e os gráficos mostram as condições de cada caso. Os
cartões da prancheta e **Levar para outras análises** usam os números do caso que manda. Os casos
entram no Ctrl+Z, em Comparar, no arquivo e no registro do projeto (com o caso que manda). O que
fica de fora: o Montador de fluidos, porque lá a conta é uma igualdade, e “o que mais pesa”, que
varia só os números do primeiro caso.

## Quando alguma coisa dá errado

- **Escolha que o bloco não conhece** (arquivo de outra versão, ou mexido à mão): vale o padrão do
  bloco, o mesmo que o inspetor mostra.
- **Bloco que não consegue fazer a conta:** só ele fica marcado na prancheta, com uma referência
  para o arquivo de diagnóstico. Os outros blocos continuam.
- **Conta que não fecha:** a prancheta e o inspetor continuam na tela, com o aviso do que conferir.
- **Uma parte da página que falha** (condições, busca, catálogo, o que mais pesa, gráficos,
  comparação, envios, documentos): só ela some, com uma linha no lugar. O resto continua valendo.
- **Valor adotado ruim no arquivo** (texto, negativo, sem número): fica de fora.
- **Conta demorada** (pinhão cônico, fuso): aparece "Fazendo a conta…". Na segunda vez ela é rápida.

A linha de cima cabe em tela de notebook: as unidades ficam num botão só, **Unidades**. Quando a
janela muda de tamanho, a prancheta se ajusta sozinha, a não ser que a vista tenha sido movida à mão.
No alto da página, **Como usar esta página** tem os passos e os atalhos da prancheta.

## Limites

- XX e YY são os eixos da seção: seção sem simetria, com produto de inércia, recebe aviso, porque M·c/I
  não vê os eixos principais.
- Sem flambagem local nem flambagem lateral: perfil I e tubo fino pedem as páginas próprias.
- Na torção de perfil I vale Saint-Venant, sem empenamento impedido.
- Euler só vale para coluna esbelta; a coluna curta recebe aviso, sem a fórmula de Johnson.
- No eixo com trechos, os mancais são apoios simples e rígidos, o binário da força axial fica no plano
  vertical com o sentido da tabela, e só um elemento recebe o torque. Carga que inverte e espectro de
  cargas pedem a Análise de fadiga.
- Os números da fórmula parcial estão na base: forças em N, medidas em mm, tensões em MPa.
- A fadiga é de eixo, com as fórmulas de Shigley: peça soldada, carga variável com espectro e dano
  acumulado pedem a Análise de fadiga.
- As unidades da tela valem dentro do Montador. Os envios entre páginas seguem copiando valores: só o
  bloco Cálculo registrado acompanha o registro.
