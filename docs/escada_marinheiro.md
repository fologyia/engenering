# Escada marinheiro (Estrutura metálica › Barras e vigas)

Escada fixa vertical, com ou sem gaiola. Cálculo em `core/escada_marinheiro.py`, desenhos em
`core/desenho_escada_marinheiro.py` (frente e planta, `Desenho2D`: os mesmos na página e no
memorial), página em `app_pages/escada_marinheiro.py` e ajuda em
`components/escada_marinheiro_help.py`.

## Fontes

* **NR-12, Anexo III** (texto vigente, "Meios de acesso a máquinas e equipamentos"), lido em
  11/11/2026: itens 1.3, 2 (Figura 1), 7.2, 13 e 13.1.
* **Orientação Técnica SIT nº 8/2023** (escadas verticais, NR-12 e NR-35).
* **ABNT NBR 6120**: degrau isolado com 2,5 kN na posição mais desfavorável (2.2.1.7 da edição de
  1980, conferido na pasta de normas; Tabela 10, nota t, da de 2019, a mesma regra que a página
  Escada em grade já usa).
* **ABNT NBR 8800**: Tabela 1 (γ_g = 1,25 e γ_q = 1,50), 5.3 (compressão, χ), 5.3.4.1 (esbeltez
  até 200) e 5.4.2.2 (M_Rd ≤ 1,5·W·f_y/γ_a1).

A ISO 14122-4 (citada pela NR-12 1.6 e pela Orientação SIT) não está na pasta: o programa não usa
valores dela.

## O que a NR-12 pede (item 13 e 13.1)

| Item | Exigência | Na página |
| --- | --- | --- |
| Figura 1 | inclinação de 75° a 90° | Inclinação |
| 13 b) | material resistente a intempéries e corrosão em ambiente externo ou corrosivo | Ambiente e proteção |
| 13 c) | gaiola acima de 3,50 m, a partir de 2,0 m do piso, passando 1,10–1,20 m do piso de chegada | Gaiola |
| 13 d) | montantes (ou corrimão) passando 1,10–1,20 m do piso de chegada | Montantes acima do piso |
| 13 e) | largura de 0,40 m a 0,60 m | Largura |
| 13 f) | lance único até 10,00 m | Lances |
| 13 g) | vários lances: até 6,00 m entre plataformas, lances paralelos afastados ≥ 0,70 m | Lances e afastamento |
| 13 h) | barras a cada 0,25 m a 0,30 m | Espaçamento |
| 13 i) | primeira barra até 0,55 m do piso | Primeira barra |
| 13 j) | ao menos 0,15 m da estrutura | Distância à estrutura |
| 13 k) | barras de 25 mm a 38 mm | Diâmetro ou lado |
| 13 l) | barras antiderrapantes | Barras antiderrapantes |
| 13.1 | gaiola Ø 0,65–0,80 m; a) verticais ≤ 0,30 m e arcos ≤ 1,50 m, ou b) arcos ≤ 0,30 m com barra vertical de sustentação | Tipo de gaiola |

Interpretações do programa:

* "Gaiola a partir de 2,0 m do piso": o início da gaiola pode ser no máximo 2,0 m (acima disso,
  sobra trecho sem proteção). Em vários lances, cada lance conta a partir da sua plataforma.
* "Altura superior a 3,50 m": a altura total da escada.
* As barras ficam abaixo do piso de chegada; quando ele cai numa posição de barra, o piso faz o
  papel do degrau. A distância da última barra ao piso de chegada é boa prática (no máximo o
  espaçamento): passar dela pede atenção, não reprova.

Fora da conta, a página lembra: a marinheiro só vale quando não cabe rampa, passarela, plataforma ou
escada de degraus (1.3); a NR-35 vale acima de 2 m, com ou sem gaiola (Orientação SIT nº 8/2023);
a marinheiro é dispensada do guarda-corpo do item 7 (7.2).

## A estrutura (NBR 8800)

* **Degrau**: barra maciça biapoiada entre os eixos dos montantes (vão = largura + t), com a
  carga do degrau isolado no meio: M_Sd = 1,5·P·L/4 ≤ M_Rd = mín(Z; 1,5·W)·f_y/γ_a1.
* **Montante** (barra chata b × t, b em direção à estrutura): a carga do lance inteiro desce até o
  apoio de baixo, metade em cada montante — N_Sd = (1,25·peso do lance + 1,5·pessoas·P)/2. A
  flambagem tem dois eixos: para a estrutura, pela largura b, entre os suportes; no plano da
  escada, pela espessura t, entre as barras, que ligam um montante no outro. Vale a maior
  esbeltez (até 200), χ da NBR 8800 com Q = 1.
* **Suportes**: força vertical de cálculo por lado (o peso entre dois suportes e uma pessoa junto
  dele) e o momento na estrutura até o eixo do montante, para dimensionar o suporte e os
  chumbadores em outra página.
* **Peso**: montantes, barras e, com gaiola, arcos (π·D a cada espaçamento) e barras verticais
  (em volta, fora o lado da escada).

Critério do programa (a NR-12 não dá): uma pessoa por lance, com a carga do degrau isolado,
nos montantes e nos suportes. O usuário muda o número de pessoas e a carga. A gaiola entra só
pelo peso: a resistência dos arcos e das barras verticais não é verificada.

## Memorial

O registro leva as verificações (o capítulo "o que passou / não passou"), os dados de entrada com
rótulos próprios e os dois desenhos (`figuras_2d`). Entra na etapa "Escadas e acessos" do Juntar o
projeto.

## Testes

`tests/test_escada_marinheiro.py`: cada limite da NR-12 dos dois lados, gaiola exigida acima de
3,50 m, lances, as contas do degrau e do montante feitas à mão, os dois eixos do montante, o peso,
o registro e o memorial, os desenhos e a página (AppTest).
