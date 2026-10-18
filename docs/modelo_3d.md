# Modelo em 3D — o núcleo de cena e a página

O núcleo desenha o modelo em 3D para qualquer parte do programa: barras com o perfil de verdade,
chapas, guarda-corpos, setas de força, cargas distribuídas, reações, apoios e rótulos, com luz,
profundidade e enquadramento. A mesma cena sai em SVG (páginas) e em PNG (memorial).

| Peça | Arquivo | O que faz |
|---|---|---|
| Cena e projeção | `core/cena_3d.py` | primitivas, seções, faces, câmera, vistas, setas, apoios, rótulos, robustez |
| PNG | `core/cena_3d_png.py` | o `Desenho2D` pelo Pillow (memorial, botão de baixar) |
| SVG | `components/cena_3d_svg.py` | o `Desenho2D` em SVG (`st.image`) |
| Fábricas | `core/cena_do_modelo.py` | esqueleto, chapas, guarda-corpos, cargas do plano, apoios e reações, cores por resultado |
| Página | `app_pages/modelo_3d.py`, `components/modelo_3d_ui.py` | Modelo SolidWorks › Modelo em 3D |

## Como desenha

- **Coordenadas da cena**: a planta do programa (X e Y horizontais, Z para cima, m). O esqueleto do
  SolidWorks com Y para cima vira (X, −Z, Y); o triedro do desenho mostra os eixos do SolidWorks.
- **Barras**: a seção do perfil (I, U, L, T, tubo retangular, tubo circular, barra) varrida ao longo
  da linha de centro, com a alma na direção que a macro v5 leu. Seção: catálogo de perfis (W, HP, I,
  U, C, T, tubos, barras), catálogo de cantoneiras, ou as medidas da macro (retângulo). Barras
  compridas viram até 8 pedaços para a ordem de desenho sair certa.
- **Faces**: a normal de cada face pelo método de Newell (vale na tampa côncava de um I); as de trás
  de cada sólido não são desenhadas; as outras do fundo para a frente (pintor), com luz difusa de
  cima e da esquerda de quem olha. Acima de 60 000 faces (modelo enorme), as barras viram linhas.
- **Vistas**: isométrica, superior, frontal, lateral, e o giro de 15° em 15°.
- **Setas e rótulos** por cima de tudo, com os rótulos sem se cobrirem.

## Setas, reações e apoios — o que é viável com o que o programa lê

- **Cargas** (Plano de cargas): as linhas cujo elemento é uma barra do esqueleto — pelo nome do corpo,
  "corpo (Viga-n)" ou "Viga-n(corpo)" — saem como pente (kN/m) ou seta no meio da barra (kN, "por
  item" no SolidWorks). Por área, por nó ou por texto livre ("Pórtico P1…") não têm lugar certo:
  ficam listadas como não localizadas. Direção: X e Y com o sinal do valor; "Z (vertical)" positivo
  para baixo.
- **Reações** (Esforços do modelo › quadro das fundações): o N na base de cada barra marcada como
  Pilar, como seta para cima no pé dela (compressão positiva). V₁ e V₂ estão nos eixos da seção do
  Simulation, sem a orientação no espaço: entram no rótulo (H = √(V₁² + V₂²)), não como seta.
- **Apoios**: no pé de cada pilar do quadro — engastado quando a base tem momento (> 0,05 kN·m) num
  caso importado, articulado quando nunca tem. Os pés no chão (até 20 cm do ponto mais baixo) que
  não estão no quadro saem sem o tipo, com aviso. Pilar do quadro com o pé longe do chão vira aviso
  (barra marcada como Pilar por engano).
- A página mostra a soma das cargas desenhadas e a das reações, para a conferência do equilíbrio
  (o PP pela gravidade não está nas linhas do plano).

## Escadas e guarda-corpos: detalhada ou casca translúcida

Um seletor na página (e na aba "Escada em 3D" do Degrau de escada) escolhe:

- **Escada detalhada** — os lances que vêm como chapa inclinada no esqueleto ganham os degraus
  (espelhos de ~18 cm na altura do lance, grade de 35 mm na largura da chapa); o guarda-corpo é o de
  verdade (corrimão, travessa e montantes em tubo de 42 mm, rodapé translúcido). Na página do degrau
  entram também as longarinas com o perfil escolhido, os patamares e os apoios das pontas (pino,
  rolete → articulado; engaste → engastado). Escada em U põe o lance seguinte ao lado.
- **Casca translúcida** — o lance como uma tampa translúcida na linha dos bocéis e o guarda-corpo como
  painéis translúcidos do piso à altura dele: o volume, que ajuda a ver o conjunto e fica limpo no
  relatório.

`core/cena_escada.py` monta a escada da página do degrau; `cena_do_modelo.chapas_da_cena` e
`guarda_corpos_da_cena` recebem o modo para o modelo.

## O relatório

- **Degrau de escada**: o modo e a vista da aba "Escada em 3D" vão ao PDF (seção 2.1, junto do
  esquemático) e ao memorial (`escada_3d` no registro, redesenhado em PNG por `record_charts`).
- **Modelo em 3D**: "Registrar a vista no memorial" grava a cena (`figura_3d`, a cena em dicionário
  por `cena_para_dicionario`) com a vista; o memorial a desenha de novo em PNG.

## Cor por

Tipo de barra (da tabela de Esforços do modelo ou da geometria), perfil, carga do vento barra a barra
numa direção (com o vento da base técnica), esforço normal de um caso importado (tração azul,
compressão vermelho) e aproveitamento da verificação ELU (verde a vermelho).

## Robustez

Coordenada inválida, barra de comprimento zero, polígono degenerado e seção com medida inválida ficam
de fora (ou com a seção padrão) e viram aviso; cena vazia sai com a mensagem; o enquadramento ignora
pontos inválidos. Teste de fuzz em `tests/test_cena_3d.py`; modelo de 2 500 barras em menos de 8 s.

## Testes

`tests/test_cena_3d.py`, `tests/test_cena_do_modelo.py`, `tests/test_modelo_3d_pagina.py`; o 3D do
vento barra a barra (`components/figuras_vento.svg_vento_3d`) já usa o núcleo.
