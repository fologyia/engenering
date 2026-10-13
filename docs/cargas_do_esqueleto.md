# Cargas do esqueleto — o que não está no modelo, como carga nas barras

A página **Cargas do esqueleto** (`app_pages/cargas_esqueleto.py`, núcleo em
`core/cargas_esqueleto.py`, planta em `components/figuras_estrutura.py::svg_planta_do_esqueleto`) é a
etapa 2 do fluxo (Ações). No SolidWorks modela-se **só o esqueleto**: pilares, vigas e
contraventamento. Tudo o que existe na obra mas não está no modelo vira **carga característica nas
barras**, caso a caso, e vai para o Plano de cargas, que exporta a planilha para o SolidWorks.

## Pelo esqueleto do modelo (`core/cargas_pelo_modelo.py`)

Com o `…_esqueleto.csv` da macro do SolidWorks (enviado nesta página ou em Esforços do modelo, fica em
`projeto["geometria_do_modelo"]`), a carga do piso vai direto para as vigas do modelo — a seção de
cima da página; os eixos e níveis abaixo ficam para quando ainda não há modelo.

* **Chapas de piso** (`chapas_do_piso`): os corpos CHAPA até 60° com a horizontal (piso, patamar,
  escada). Com a macro v5, o contorno da face maior e as aberturas (normal pelo método de Newell);
  com a v4, a caixa — só se a chapa enche a caixa (volume ≥ 93 % de comprimento × largura ×
  espessura): a chapa principal do modelo real ocupava 65 % da caixa (tem recortes) e fica de fora
  com o motivo, porque a caixa mandaria carga para vigas embaixo de um buraco.
* **Vigas que apoiam** (`vigas_que_apoiam`): barras quase paralelas ao plano da chapa, com a linha
  de centro entre a face de baixo da chapa e uma altura de seção abaixo, e a projeção na chapa.
* **Área de influência** (`influencias`): a chapa é amostrada (2 a 10 cm) e cada pedaço vai para a
  viga mais perto no plano dela — entre vigas paralelas, metade do vão para cada lado; nos cantos de
  uma malha, as bissetrizes. Ponto fora da envoltória das vigas a mais de 0,60 m é balanço da chapa
  (aviso); chapa sem viga embaixo também.
* **Carga** (`distribuir`): q (kN/m², projeção horizontal — como a NBR 6120 dá a sobrecarga) × área
  de influência × cos(inclinação); por viga, o total e o kN/m uniforme na viga inteira (total ÷
  comprimento), com o trecho carregado — menos de 80 % da viga é aviso (dividir a viga no fim da
  chapa ou aplicar no trecho, para o momento sair certo). A soma fecha: q × área projetada.
* **Plano de cargas** (`aplicar_no_plano`): para cada caso, uma carga distribuída por viga (com o
  nome da viga no Simulation, se os esforços já foram importados), origem "Esqueleto do modelo", com
  o comprimento — a conferência das reações de Esforços do modelo compara o estudo com elas. CSV
  das cargas (`csv_das_cargas`).

No modelo real (macro v5): as quatro chapas com o contorno — o piso principal de 9,2 m² (4,5 × 1,8 m
com a extensão de 1,0 × 1,1 m até a escada), as duas rampas da escada e o patamar —, 32 vigas
carregadas, 72,98 kN = 5 kN/m² × 14,596 m² projetados.

As cargas por área vêm do plano (as ações com kN/m²) ou da base técnica (SC). O peso das chapas não
entra: ele já está no modelo (a gravidade do PP).

## Entrada (`EntradaEsqueleto`, gravada em `projeto["cargas_do_esqueleto"]`)

* **Eixos**: posições em X (eixos 1, 2, 3…) e em Y (eixos A, B, C…). Pilar em cada cruzamento (um
  por andar), viga em cada eixo de cada nível.
* **Níveis**: cota; **vigas paralelas a** X ou Y (as que recebem o piso — o piso vence o vão na
  outra direção); **vão máximo do piso** (o programa põe as vigas secundárias que faltam, com
  espaçamento igual); piso e sobrecarga (kN/m²); as bordas com guarda-corpo (X− é o lado do eixo 1,
  Y− o do eixo A).
* **Guarda-corpo e rodapé** (kN/m), **acréscimo de ligações, chapas e parafusos** (%), **temperatura**
  ±10 °C (critério Anglo 5.8; ligado quando a base técnica usa o critério Anglo).
* **Escadas**: nível de chegada, borda e trecho da borda entre eixos, largura, projeção em planta,
  peso e sobrecarga por área em planta (Anglo, Tabela 2: escadas, 3 kN/m²).
* **Equipamentos**: nível, peso vazio, conteúdo em operação, número de apoios, impacto vertical e
  horizontal em % do peso em operação (Anglo 5.3: 20 % rotativas; 100 % e 25 % vibratórios), local.
* **Tubulações e bandejas**: nível, eixo, kN/m, caso PE ou EO.

## Cálculo (`calcular`)

| O que não está no modelo | Caso | Como vira carga |
| --- | --- | --- |
| Piso | PE | q × largura de influência (metade da distância às vizinhas de cada lado) em cada viga paralela à direção do nível |
| Sobrecarga | SC | idem |
| Guarda-corpo | PE | kN/m nas vigas das bordas marcadas (a força horizontal do topo é verificação local) |
| Tubulações | PE ou EO | kN/m nas vigas do eixo |
| Escadas | PE e SC | apoio de cima: metade de q × largura × projeção, em duas forças (longarinas), no meio do trecho; o apoio de baixo vai à fundação |
| Equipamentos | EQ, EO, IM | forças iguais nos apoios; impacto horizontal em X (trocar para Y se for o caso) |
| Ligações | PP | gravidade × (1 + acréscimo): `PlanoDeCargas.fator_peso_proprio` |
| Temperatura | T+, T− | ±10 °C nas barras |

As parcelas de um caso numa barra são **somadas** (um valor por barra e caso) e as barras com o
mesmo valor são **agrupadas** numa carga do plano (uma carga no SolidWorks com várias barras), com o
comprimento de cada uma (`CargaDoModelo.comprimento_m`).

**Conferência**: para cada nível, item, escada e equipamento, o que entrou (área × q, perímetro × q,
pesos) contra o que foi aplicado nas barras; as larguras de influência fecham a largura do piso por
construção.

## Plano de cargas e conferências seguintes

* **Gravar e enviar ao plano** (`aplicar_no_plano`) substitui no plano os casos que a página gera
  (PE, SC, EQ, EO, IM, T±; avisa quando um deles foi informado de outro jeito), tira os que uma
  aplicação anterior gerou e esta não gera mais, garante o PP e põe o fator na gravidade.
* **Exportação** (`core/exportacao_cargas.py`): a linha da gravidade do PP sai com 9,81 × fator e o
  Leia-me diz o porquê.
* **Esforços do modelo**: `total_esperado` passa a somar as cargas distribuídas que trazem o
  comprimento — a conferência das reações de PE e SC fecha contra estas cargas; o PP é conferido
  contra o peso da Lista de material × fator.

## Registro

`registro_esqueleto` → capítulo de cálculo no memorial: destaque com a resultante de cada caso, os
níveis, as cargas por barra e as forças concentradas.

## Testes

`tests/test_cargas_pelo_modelo.py` (vigas paralelas com meio vão para cada lado, abertura,
escada inclinada, chapa em pé, sem viga embaixo, balanço, trecho parcial, chapa retangular e
recortada da v4, envio ao plano com a conferência das reações e CSV),
`tests/test_cargas_esqueleto.py` (esqueleto da grade, larguras de influência, conta à mão do
exemplo, piso nas vigas paralelas a Y, guarda-corpo por borda, escada, equipamento e tubulação,
entradas inválidas, plano com comprimentos e fator, reações do modelo conferidas, exportação,
ida e volta pelo projeto e pelas tabelas, registro, CSV e planta) e
`tests/test_cargas_esqueleto_pagina.py`.
