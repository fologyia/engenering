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

## Guarda-corpo nas bordas do piso (`core/guarda_corpo_do_modelo.py`)

O guarda-corpo fica nas bordas do piso que não encostam em outro piso, parafusado na viga da borda.
Com as chapas de piso do esqueleto (macro v5: contorno e aberturas):

1. o contorno e as aberturas de cada chapa são percorridos em estações de 5 cm; a estação é
   **livre** quando o ponto 12 cm para fora (no plano da chapa) não cai em outra chapa a menos de
   30 cm do plano dela. Onde o lance da escada encosta na plataforma ou no patamar há piso dos dois
   lados: é o **acesso**, sem guarda-corpo. O lado em nível de um lance (pé ou topo) também é acesso;
2. a **viga da borda** de cada estação é a barra paralela à borda (até 12°) que cobre a estação,
   logo abaixo da chapa (de 5 cm acima da linha de centro até a altura da seção + 25 cm abaixo) e a
   até 35 cm dela no plano da chapa — a mais perto; cantoneira de enrijecimento (seção < 10 cm)
   perde para a viga. Estações seguidas com a mesma viga formam um **trecho**; no lance inclinado
   (> 10°) é guarda-corpo de escada, na longarina;
3. borda livre **sem viga embaixo** vira aviso e não recebe carga.

Sem chapas de piso, as bordas saem das vigas: estação a estação, a viga horizontal (seção ≥ 10 cm,
≥ 0,5 m) que tem paralela do mesmo nível (±25 cm, a 0,2–15 m) só de um lado é borda; isolada não
entra. O acesso da escada que não está como chapa vem das **longarinas**: duas barras de 15° a 65°,
paralelas, a 0,5–2,0 m uma da outra, com a ponta junto da borda (até 40 cm) e saindo para **fora**
do piso — a mão-francesa e o travamento, que vão para baixo do piso, não contam.

O engenheiro confere numa tabela (desmarca o lado da parede, o portão) e na planta; a escolha fica em
`projeto["guarda_corpo_do_modelo"]` (só os trechos trocados, pela chave, mais peso, altura e φ). O
peso (padrão 0,40 kN/m ≈ 40 kg/m) vai ao caso **PE**, uniforme em cada viga de borda (total ÷
comprimento da viga, como o piso), em linhas marcadas "Guarda-corpo nas bordas": reenviar o piso
mantém essas linhas e reenviar o guarda-corpo troca só elas. O vento barra a barra usa os mesmos
trechos como guarda-corpos (altura 1,10 m, ou 1,30 m no critério Anglo; φ 0,30).

**Ajustes** (no alto do bloco): duas chaves — "Achar o acesso da escada pelas longarinas" (desligada,
não procura o acesso pelas longarinas; o que vem das chapas fica) e "Guarda-corpo nos lances de escada"
(desligada, os lados dos lances aparecem desmarcados) — e a tabela **Trechos à mão**: viga, de/até (m,
do início da viga; vazio = a viga inteira) e tipo. *Guarda-corpo à mão* entra no lugar do que o
programa achou naquela parte da viga (corta os trechos achados: nunca conta duas vezes); *acesso /
portão à mão* tira o guarda-corpo daquela parte. Os pedaços de um trecho cortado herdam a escolha
dele (chave com "#1", "#2"). Viga que não está no esqueleto, faixa invertida (é invertida de volta),
fora da viga (é cortada nela), menor que 10 cm ou com valor inválido vira aviso. Tudo fica em
`projeto["guarda_corpo_do_modelo"]` e vale para o peso no PE e para o vento barra a barra.

Robustez: corpo com coordenada inválida, chapa sem área ou contorno dobrado e barra de comprimento
zero ficam de fora com o motivo nos avisos; o cálculo não levanta exceção por geometria (teste de
fuzz em `tests/test_guarda_corpo_do_modelo.py`).

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
