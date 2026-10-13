# Cargas do esqueleto — o que não está no modelo, como carga nas barras

A página **Cargas do esqueleto** (`app_pages/cargas_esqueleto.py`, núcleo em
`core/cargas_esqueleto.py`, planta em `components/figuras_estrutura.py::svg_planta_do_esqueleto`) é a
etapa 2 do fluxo (Ações). No SolidWorks modela-se **só o esqueleto**: pilares, vigas e
contraventamento. Tudo o que existe na obra mas não está no modelo vira **carga característica nas
barras**, caso a caso, e vai para o Plano de cargas, que exporta a planilha para o SolidWorks.

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

`tests/test_cargas_esqueleto.py` (esqueleto da grade, larguras de influência, conta à mão do
exemplo, piso nas vigas paralelas a Y, guarda-corpo por borda, escada, equipamento e tubulação,
entradas inválidas, plano com comprimentos e fator, reações do modelo conferidas, exportação,
ida e volta pelo projeto e pelas tabelas, registro, CSV e planta) e
`tests/test_cargas_esqueleto_pagina.py`.
