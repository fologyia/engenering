# Montador de fórmulas

A página liga blocos numa prancheta e devolve a equação isolada na grandeza escolhida: a altura, o
diâmetro, o momento, a carga, o limite do material ou o fator de segurança. Os números são opcionais.
Letra sem valor continua na fórmula, e assim sai `h = 1,6·√M` quando só o momento ficou em aberto.

## Como se usa

Quem clica num bloco acima da prancheta já recebe a fila ligada: **Seção → esforços → critério → Em
função de**. Um esforço novo entra antes do critério, e apagar um esforço do meio não quebra a fila.
As bolinhas ligam à mão também: arraste de uma à outra, ou clique em uma e depois na outra. Puxar uma
entrada já ligada solta o fio. Ctrl+Z desfaz, Delete apaga o selecionado.

Há três tipos de fio. O azul leva a seção e as tensões somadas até ali. O laranja troca uma letra pela
fórmula de outro bloco: ligando a viga na flexão, M vira F·L/4, e a equação passa a falar em F e L. O
verde leva a condição do critério até o resultado. Dá para ligar vários critérios no mesmo resultado:
von Mises e flecha, por exemplo, e a página diz quem manda.

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

## Seção desenhada

A seção da prancheta só tem números, então a letra é a escala `s`: multiplica todas as medidas juntas.
Os pontos são a fibra, a linha neutra e toda altura onde a largura pula mais de 20 %. Com M_y entram a
fibra de YY e os cantos, escolhidos entre os pontos da borda, em módulo: seção sem simetria fica a favor
da segurança. Em torção vale o τ máximo em todos os pontos, a favor da segurança.

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
