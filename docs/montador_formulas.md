# Montador de fórmulas

A página liga blocos numa prancheta e devolve a equação isolada na grandeza escolhida: a altura, o
diâmetro, o momento, a carga, o limite do material ou o fator de segurança. Os números são opcionais.
Letra sem valor continua na fórmula, e assim sai `h = 1,6·√M` quando só o momento ficou em aberto.

## Como se usa

A tela tem três colunas: a biblioteca, a prancheta e o inspetor. Quem clica num bloco da biblioteca
já recebe a fila ligada: **Seção → esforços → critério → Em função de**. Um esforço novo entra antes
do critério, e apagar um esforço do meio não quebra a fila. As bolinhas ligam à mão também: arraste de
uma à outra, ou clique em uma e depois na outra. Puxar uma entrada já ligada solta o fio. Ctrl+Z desfaz,
Ctrl+Y refaz, Delete apaga o selecionado, as setas andam de um bloco ao outro, e Enter abre o conjunto.

Há quatro tipos de fio. O azul leva a seção e as tensões somadas até ali. O laranja troca uma letra pela
fórmula de outro bloco: ligando a viga na flexão, M vira F·L/4, e a equação passa a falar em F e L. O
marrom leva o material, com S_y, S_ut, E e G no mesmo fio. O escuro leva a condição do critério até o
resultado. Dá para ligar vários critérios no mesmo resultado: von Mises e flecha, por exemplo, e a
página diz quem manda.

Selecionar uma ligação muda a biblioteca: ela passa a mostrar primeiro o que cabe ali, e passar o
cursor mostra a prévia na prancheta. Clicar insere o bloco no meio do fio, que vira origem → novo →
destino. O resto do desenho não anda.

## O inspetor

Mostra o que está selecionado, e cada coisa do seu jeito:

- **Nada selecionado:** todos os valores da montagem.
- **Bloco:** os valores só dele, o uso do critério, de quem recebe e para quem envia.
- **Ligação:** o que passa no fio, medido nos números atuais (esforços somados e tensões de cada ponto),
  e a conferência de tipo, grandeza e laço, calculada na hora.
- **Conjunto:** os valores de dentro, sem precisar abrir, e as entradas e saídas públicas.
- **Em função de:** a resposta, quem manda e o uso de cada condição.

Abaixo dos resultados, "De onde veio cada valor" diz a procedência campo a campo (digitado, exemplo do
modelo, padrão do programa, tabela), e a página avisa o que mudou na resposta, e por causa de qual valor.
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
  Colebrook, e a planilha avisa; o K_t de ressalto fica com o número do programa.

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

## Limites

- XX e YY são os eixos da seção: seção sem simetria, com produto de inércia, recebe aviso, porque M·c/I
  não vê os eixos principais.
- Sem flambagem local nem flambagem lateral: perfil I e tubo fino pedem as páginas próprias.
- Na torção de perfil I vale Saint-Venant, sem empenamento impedido.
- Euler só vale para coluna esbelta; a coluna curta recebe aviso, sem a fórmula de Johnson.
- Os números da fórmula parcial estão na base: forças em N, medidas em mm, tensões em MPa.
- A fadiga é de eixo, com as fórmulas de Shigley: peça soldada, carga variável com espectro e dano
  acumulado pedem a Análise de fadiga.
- As unidades da tela valem dentro do Montador. Os envios entre páginas seguem copiando valores: só o
  bloco Cálculo registrado acompanha o registro.
