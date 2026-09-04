# Círculo de Mohr e transformação de tensões

Este documento registra as convenções, equações e limites do módulo
`Círculo de Mohr`.

## Convenções

- tensões normais de tração são positivas;
- `τxy` positiva atua na face positiva de x no sentido positivo de y;
- o ângulo físico `θ` gira o eixo x para x' no sentido anti-horário;
- no gráfico, `τ` é positiva para cima; por isso, uma rotação física `θ`
  aparece como uma rotação de `−2θ` no círculo;
- todos os valores informados na interface estão em MPa.

## Estado plano de tensões

O módulo considera:

```text
[ σx   τxy   0 ]
[ τxy  σy    0 ]
[ 0     0    0 ]
```

O centro `C` e o raio `R` do círculo 2D são:

```text
C = (σx + σy) / 2
R = sqrt(((σx − σy) / 2)² + τxy²)
```

As tensões principais no plano são `σ1 = C + R` e `σ2 = C − R`. As
componentes após uma rotação física `θ` são:

```text
σx'   = C + ((σx − σy) / 2) cos(2θ) + τxy sen(2θ)
σy'   = C − ((σx − σy) / 2) cos(2θ) − τxy sen(2θ)
τx'y' =   − ((σx − σy) / 2) sen(2θ) + τxy cos(2θ)
```

O programa usa `atan2` para determinar a orientação principal sem perder o
quadrante. As orientações de planos são apresentadas no intervalo de 0° a
180°.

### Máximo cisalhamento: no plano e absoluto

O máximo cisalhamento no plano é o raio `R`. Entretanto, em estado plano de
tensões a terceira tensão principal é zero. O máximo absoluto tridimensional
é, portanto:

```text
τmáx,abs = (máx(σ1, σ2, 0) − mín(σ1, σ2, 0)) / 2
```

Esses dois resultados podem ser diferentes. Em tração equibiaxial, por
exemplo, o raio do círculo 2D é zero, mas existe cisalhamento máximo em planos
fora do plano xy.

## Estado geral tridimensional

O tensor simétrico de Cauchy é montado com as seis componentes independentes.
As tensões principais são seus autovalores, ordenados como
`σ1 ≥ σ2 ≥ σ3`, e as direções principais são os autovetores unitários
correspondentes.

Os três círculos exibidos são os pares `σ1–σ3`, `σ1–σ2` e `σ2–σ3`.
O círculo `σ1–σ3` fornece o cisalhamento máximo absoluto:

```text
τmáx = (σ1 − σ3) / 2
```

O módulo também calcula:

```text
σmédia = I1 / 3
σVM = sqrt(3 J2)
σeq,Tresca = σ1 − σ3
τoct = sqrt(2 J2 / 3)
```

## Tração em um plano tridimensional

Para uma normal unitária `n`, a fórmula de Cauchy fornece o vetor de tração:

```text
t = σ n
σn = n · t
τ = t − σn n
|τ| = norma(τ)
```

A interface aceita a normal por componentes ou por azimute e elevação, e a
normaliza automaticamente. Em 3D, a magnitude `|τ|` pode ser representada no
diagrama de Mohr, mas sua direção vetorial também é necessária para descrever
completamente a ação no plano.

## Uso em critérios de falha

- materiais dúcteis aproximadamente isotrópicos: comparar `σVM` ou a
  equivalente de Tresca com o limite de escoamento;
- materiais frágeis: usar um critério que considere separadamente as tensões
  principais e as resistências de tração e compressão;
- carregamentos cíclicos: usar as componentes média e alternada no módulo de
  fadiga; uma única fotografia do Círculo de Mohr não determina a vida;
- o resultado não inclui automaticamente concentração de tensões, tensões
  residuais, temperatura, fluência ou efeitos ambientais.

## Referências de conferência

- MIT OpenCourseWare, *Unified Engineering — Transformation of stress
  components, principal stresses and Mohr's circle*:
  <https://ocw.mit.edu/courses/16-001-unified-engineering-materials-and-structures-fall-2021/mit16_001_f21_lec11lec12.pdf>
- MIT OpenCourseWare, *Transformation of Stresses and Strains*:
  <https://ocw.mit.edu/courses/3-11-mechanics-of-materials-fall-1999/0d670d6da74323e2d82562b0c1289635_MIT3_11F99_trans.pdf>

## Limitações

O módulo analisa tensões em um ponto. Ele não substitui o cálculo estrutural
que produz as componentes, a verificação de unidades, a seleção de uma norma
aplicável nem a revisão técnica de um projeto real.
