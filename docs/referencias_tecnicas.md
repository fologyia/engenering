# Referências técnicas dos fatores de Marin

Este documento registra as fórmulas utilizadas no programa e evita misturar
coeficientes de autores diferentes em uma mesma análise.

## Fontes locais

- Robert L. Norton, *Projeto de Máquinas: uma abordagem integrada*, 4ª edição.
- Budynas e Nisbett, *Elementos de Máquinas de Shigley*, 8ª edição.

Os números abaixo são páginas do arquivo PDF. O número impresso no livro também
é indicado para facilitar a conferência.

## Mapeamento das correlações

| Tema | Norton 4ª edição | Shigley 8ª edição | Implementação |
|---|---|---|---|
| Produto de Marin | PDF 356, impressa 330, Eq. 6.6 | PDF 299, impressa 305, Eq. 6-18 | Modelo selecionável |
| Carregamento | PDF 356, impressa 330, Eq. 6.7a | PDF 302, impressa 308, Eq. 6-26 | Valores próprios de cada autor |
| Tamanho | PDF 357, impressa 331, Eq. 6.7b | PDFs 300–302, impressas 306–308, Eqs. 6-20 a 6-25 | Curvas e faixas próprias |
| Superfície | PDF 359, impressa 333, Tabela 6-3 | PDF 300, impressa 306, Tabela 6-2 | Coeficientes coincidentes |
| Temperatura | PDF 361, impressa 335, Eq. 6.7f | PDFs 303–304, impressas 309–310, Tabela 6-4 e Eq. 6-27 | Equações distintas |
| Confiabilidade | PDF 361, impressa 335, Tabela 6-4 | PDFs 304–305, impressas 310–311, Eq. 6-29 e Tabela 6-5 | Tabela coincidente |
| Curva S–N estimada | PDFs 363–364, impressas 337–338, Eqs. 6.9 e 6.10 | Capítulo 6 | Mantida como estimativa |
| Sensibilidade ao entalhe | Capítulo 6, Eq. 6.11b | Capítulo 6, relação entre Kf, Kt e q | Correção opcional da tensão alternada |
| Goodman e Soderberg | PDFs 387–390, impressas 361–364, Eqs. 6.15 e 6.16 | PDFs 318–319, impressas 324–325, Eqs. 6-44 e 6-45 | Fatores de segurança e diagrama |

## Diferenças que afetam resultados

### Carregamento

Norton usa 1,00 para flexão e 0,70 para carga axial. Shigley usa 1,00 e
0,85, respectivamente. Para torção comparada diretamente em cisalhamento,
Norton usa 0,577 e Shigley usa 0,59. Quando a torção é convertida para tensão
equivalente de von Mises, o fator de carregamento adotado é 1,00.

### Tamanho

Norton utiliza uma correlação única acima de 8 mm e recomenda fator 0,60 para
diâmetros maiores que 250 mm. Shigley usa duas correlações, separadas em
51 mm, válidas até 254 mm. Em ambos os modelos, carga axial recebe fator de
tamanho igual a 1.

Para seções não circulares, o diâmetro equivalente deve ser obtido a partir da
região submetida a pelo menos 95% da tensão máxima. O programa ainda recebe o
diâmetro equivalente já calculado; a determinação automática pela geometria é
uma extensão futura.

### Superfície

As duas fontes apresentam os mesmos coeficientes para a expressão em MPa:

| Acabamento | A | b |
|---|---:|---:|
| Retificado | 1,58 | -0,085 |
| Usinado ou estirado a frio | 4,51 | -0,265 |
| Laminado a quente | 57,7 | -0,718 |
| Forjado | 272 | -0,995 |

As curvas foram desenvolvidas principalmente para aços. Norton recomenda fator
de superfície igual a 1 para ferro fundido. Para alumínio, cobre e condições
corrosivas, o valor manual deve vir de ensaio, norma ou gráfico aplicável.

### Temperatura

A interface aceita a temperatura da peça em °C ou °F e normaliza o valor antes do cálculo. Norton usa a Equação 6.7f em °F: fator 1 até 450 °F (232,2 °C), com redução linear de 450 °F a 550 °F (287,8 °C). Assim, 500 °F equivale a 260 °C e resulta em Ctemp = 0,71. Acima de 550 °F, o programa bloqueia a extrapolação. Shigley
apresenta uma tabela e um ajuste polinomial de quarta ordem para aços, indicado
entre 37 °C e 540 °C. As duas abordagens não devem ser combinadas.

### Confiabilidade

As tabelas das duas fontes coincidem para os níveis implementados. Elas assumem
desvio padrão da resistência à fadiga igual a aproximadamente 8% da média.

## Curva S–N e efeito da tensão média

A curva tensão–vida é construída somente depois da correção de Marin. O ponto de
alto ciclo usa Se em 10⁶ ciclos para materiais com limite de fadiga ou Sf em
5×10⁸ ciclos para alumínio e cobre. O ponto de 10³ ciclos usa a estimativa de
Norton da Eq. 6.9:

- flexão e solicitações convertidas para tensão equivalente: Sm = 0,90 Sut;
- força normal no modelo Norton: Sm = 0,75 Sut.

No modelo Shigley, o programa mantém Sm = 0,90 Sut como aproximação do fator f.
Dados S–N experimentais do material, acabamento, ambiente e processo sempre têm
prioridade sobre essa construção estimada.

Para tensão média de tração, a vida não é calculada diretamente com sigma_a. A
reta de Goodman é rearranjada para obter uma amplitude totalmente reversa
equivalente:

sigma_a,eq = sigma_a / (1 - sigma_m/Sut).

Essa amplitude equivalente é então comparada à curva S–N. Quando sigma_m é maior
ou igual a Sut, não existe margem pela reta de Goodman e a vida não é estimada.

## Sensibilidade ao entalhe

A correção opcional da tensão alternada usa:

- sem entalhe: K = 1;
- concentração teórica direta: sigma_a = Kt · sigma_a,nom;
- com sensibilidade: Kf = 1 + q(Kt − 1) e sigma_a = Kf · sigma_a,nom.

O índice q varia de 0 a 1. Para q = 0, Kf = 1 e o material é tratado como
insensível ao entalhe; para q = 1, Kf = Kt e há sensibilidade total. O programa
aplica esse fator à componente alternada antes de Goodman, Soderberg e da curva
S–N. A tensão média deve ser informada já como tensão local ou equivalente,
pois sua concentração efetiva depende da ductilidade e do possível escoamento
local no entalhe.

## Goodman modificado e Soderberg

Para tensão média de tração e carregamento proporcional, usando a tensão alternada efetiva após a opção de entalhe, o programa calcula:

- Goodman modificado: 1/n = sigma_a/Se + sigma_m/Sut;
- Soderberg: 1/n = sigma_a/Se + sigma_m/Sy;
- escoamento no primeiro ciclo: n = Sy/(sigma_a + sigma_m).

Soderberg é mais conservador porque usa o limite de escoamento no eixo de
tensão média. Goodman deve ser acompanhado pela verificação de escoamento.
Na região de tensão média compressiva, o programa adota a recomendação
conservadora de considerar a tensão média igual a zero.

## Limitações de uso

- As correlações são estimativas e não substituem dados S–N experimentais.
- O fluxo completo de torção usa tensão equivalente de von Mises. A comparação
  direta com tau exige Ssu, Ssy e dados S–N em cisalhamento, que não são entradas
  desta tela.
- Temperatura, superfície e tamanho são fundamentados principalmente em aços.
- Corrosão, revestimentos, tensões residuais e tratamentos superficiais exigem
  fatores ou dados adicionais.
- Em temperatura elevada, fluência e interação fadiga-fluência podem invalidar
  o modelo tensão–vida.
- O resultado deve ser validado com norma aplicável, certificado do material e
  condições reais de fabricação e carregamento.
