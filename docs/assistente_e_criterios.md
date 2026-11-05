# Assistente de cargas e critérios de falha

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

No Equilíbrio de uma peça, as cotas da prancheta funcionam do mesmo jeito: mudar uma distância empurra
tudo o que está depois dela, e a peça estica sem soltar nada.

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
