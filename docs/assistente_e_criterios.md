# Cálculo de peças e critérios de falha

Este documento registra as equações, unidades, hipóteses e critérios usados
para converter carregamentos em tensões e avaliar materiais. Os casos de
transmissão, eixos, mancais, içamento, molas, freios e hidráulica estão em
[`elementos_de_maquinas.md`](elementos_de_maquinas.md).

## Medidas no desenho

O desenho de cada caso mostra os valores no lugar das letras, e a medida se edita ali mesmo: clique,
digite, Enter confirma e Tab vai para a próxima. `core/cotas_dos_desenhos.py` diz qual letra de cada
desenho é qual campo; letra que é resultado do cálculo fica de fora. Um teste exige que toda letra do
mapa exista no desenho e que todo campo exista no caso. O campo que está no desenho sai da lista e fica
em "Medidas do desenho em lista", recolhida. Campo escondido por uma escolha continua só como letra.
As caixinhas se afastam sozinhas quando se encostam, porque o tamanho depende do número digitado.

A caixinha é a mesma nas três pranchetas (`components/editor_numerico.js`). Além do número, aceita
conta (`300/2`, `2*150+10`), unidade (`1,5 m`, `2 pol`, `5 kN`, `10 bar`), valor relativo ao atual
(`+10`, `*1,2`, `/2`) e as setas ↑ e ↓, com Shift para dez passos. A conta não usa `eval`.

Depois de mudar uma medida, a resposta mostra o que mais andou, com o antes e o depois (`mudancas`).
O botão Desfazer volta uma medida de cada vez, e abaixo de 0,1 % a variação é tratada como ruído.

Quando a medida tem série comercial, a caixinha mostra os vizinhos do valor digitado, que acompanham
a digitação: quem escreve 7 numa chapa vê 5, 6,3, 8 e 9,5. "Achar o limite" responde ali mesmo, com os
valores prontos para usar, e "Ver gráfico" abre o estudo da medida logo abaixo. A resposta só vale
para os números que a geraram: mudou um dado, ela sai. A Desenhar seção sugere chapas comerciais no
lado menor da chapa selecionada, porque ninguém compra chapa pela largura.

Na peça desenhada de Vigas e eixos, as cotas da prancheta funcionam do mesmo jeito: mudar uma distância empurra
tudo o que está depois dela, e a peça estica sem soltar nada.

## Estudar uma medida

`core/estudo_da_medida.py` não inverte fórmula: roda o próprio cálculo do caso em vários valores. Por
isso vale para qualquer caso, e o número que ele acha é o que a tela mostraria com aquele valor.

**A faixa que passa.** A resposta é uma faixa, e não só um mínimo: para uma espessura o limite é o
menor valor, para uma carga é o maior, e há medidas com os dois lados. O estudo olha 41 valores de um
oitavo a oito vezes o valor de agora, dentro dos limites do campo. Cada troca entre passa e não passa
é fechada por bisseção, com tolerância de 0,01 %. A curva não precisa ser crescente, e dado que o caso
recusa conta como não passa, com o motivo. Um trecho que passa e cabe inteiro entre dois valores da
grade pode não aparecer.

**Valores prontos.** O número limpo mais perto do limite, com 3 algarismos, conferido no cálculo antes
de aparecer. Se o arredondamento mais próximo reprovar, ele vai para o lado que passa: 166,67 kN vira
166 kN, e 4,80 mm continua 4,8 mm. O comercial é o primeiro valor da série que passa de verdade.

**Recomendação não é critério.** Passar de uma recomendação não reprova, e por isso ela fica fora da
curva dos 100 %. Ela vira a opção "Sem ressalvas". Num caso só de recomendações, são elas que separam.

**A medida que manda.** O peso é a variação do aproveitamento governante para cada 1 % na medida,
medida com ±10 %: peso −2 quer dizer que a medida entra ao quadrado no denominador, como a espessura
na flexão de uma placa. O destaque em laranja no desenho sai só das cotas de geometria, porque carga e
material costumam vir dados. O peso vale em volta dos números de agora: uma medida com peso zero é a
que não governa hoje, e pode passar a governar se outra mudar.

**Valores comerciais.** `core/medidas_comerciais.py` liga cada campo a uma série: chapas, parafusos
ISO 261, assentos de rolamento ISO 15, arame EN 10270-1, módulos ISO 54, polias ISO 4183, correntes
ISO 606, roscas ISO 2904, cilindros ISO 3320, chavetas ISO 773, cabos, cantoneiras e pernas de solda.
Só tem série o que tem tabela de verdade por trás: um comprimento qualquer fica sem sugestão. As séries
de mercado (chapas, barras, cabos, cantoneiras) variam por fornecedor, e quem confirma é a compra.

As varreduras rodam em `so_a_conta()`, que dispensa o PNG das figuras. O número não muda, e um teste
confere isso em todos os casos.

## Convenção de unidades

O núcleo trabalha com forças em N e dimensões em mm. Assim, as tensões
resultam em N/mm², equivalentes a MPa. A interface aceita forças em kN e
momentos/torques em N·m e converte esses valores na entrada.

## Barra axial

Para carga aplicada pelo centroide de uma seção prismática:

```text
σx = F/A
σy = 0
τxy = 0
```

Força positiva representa tração e negativa representa compressão.

## Eixo circular maciço

Na superfície externa:

```text
A = πd²/4
σaxial = F/A
|σflexão| = 32|M|/(πd³)
τtorção = 16T/(πd³)
```

O usuário escolhe o lado tracionado ou comprimido da flexão. O sinal do
torque determina o sinal de `τxy`.

## Viga de seção retangular

Para largura `b`, altura `h` e coordenada `y` medida do centroide:

```text
A = bh
I = bh³/12
σx = F/A − My/I
τxy = 3V/(2A) · [1 − (2y/h)²]
```

O modelo mostra por que as componentes devem ser avaliadas no mesmo ponto:
a tensão de flexão é máxima nas fibras externas, onde o cisalhamento devido a
`V` é zero; o cisalhamento é máximo no centroide, onde a parcela de flexão é
zero.

## Vaso cilíndrico de parede fina

Para pressão interna `p`, diâmetro médio `D` e espessura `t`:

```text
σcircunferencial = pD/(2t)
σlongitudinal = pD/(4t)  — extremidades fechadas
σlongitudinal = 0        — tubo aberto
```

O programa usa `x` como direção longitudinal e `y` como direção
circunferencial. Quando `D/t < 20`, a interface alerta que a hipótese de
parede fina pode ser inadequada.

## Critérios de falha

As tensões principais são ordenadas como `σ1 ≥ σ2 ≥ σ3`.

### von Mises

Para materiais dúcteis aproximadamente isotrópicos:

```text
nVM = Sy/σVM
```

### Tresca

A tensão equivalente é a maior diferença entre tensões principais:

```text
σeq,Tresca = σ1 − σ3
nTresca = Sy/(σ1 − σ3)
```

### Rankine

O critério da máxima tensão normal compara tração e compressão
separadamente:

```text
nt = Sut/σ1       para σ1 > 0
nc = Suc/|σ3|     para σ3 < 0
nRankine = mín(nt, nc)
```

Quando existe `σ3 < 0` e `Suc` não foi informada, o programa não apresenta um
fator global de Rankine. Essa restrição evita concluir segurança usando apenas
a resistência à tração.

## Propriedades dos materiais

A base local possui `Sy` e `Sut`, mas não possui `Suc`. A resistência à
compressão deve ser obtida de norma, certificado ou ensaio e informada
manualmente. Materiais sem limite de escoamento definido não são avaliados por
von Mises ou Tresca usando a base local.

## Referências de conferência

- MIT OpenCourseWare, *Mechanics of Materials* — conteúdos de carga axial,
  flexão e torção:
  <https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/>
- MIT OpenCourseWare, *Stresses in Beams*:
  <https://ocw.mit.edu/courses/3-91-mechanical-behavior-of-plastics-spring-2007/19f0e5ed0cd050837baa34bff76ad347_13_bstress.pdf>
- MIT OpenCourseWare, *Pressure Vessels*:
  <https://ocw.mit.edu/courses/3-91-mechanical-behavior-of-plastics-spring-2007/0be49aef0263a94601f18b28c64af705_06_pv.pdf>
- MIT OpenCourseWare, *Yield and Plastic Flow*:
  <https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/913c0305981479e7474e1a229f53d2d9_MIT3_11F99_yield.pdf>

## Limitações

Nos modelos de seção, a concentração de tensões só entra pelo K_t informado.
Eles não incluem efeitos locais de aplicação de carga, contato, soldas,
tensões residuais, plasticidade,
instabilidade, fluência ou carregamentos cíclicos. O fator aceitável depende da
norma e da consequência da falha.
