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
  Pilar, como seta para cima no pé dela (compressão positiva), e a **horizontal H** como seta quando
  o programa sabe para que lado o Simulation virou a seção do pilar (abaixo); sem isso, V₁ e V₂ ficam
  no rótulo (H = √(V₁² + V₂²)) e o aviso diz por quê.
- **Apoios**: no pé de cada pilar do quadro — engastado quando a base tem momento (> 0,05 kN·m) num
  caso importado, articulado quando nunca tem. Os pés no chão (até 20 cm do ponto mais baixo) que
  não estão no quadro saem sem o tipo, com aviso. Pilar do quadro com o pé longe do chão vira aviso
  (barra marcada como Pilar por engano).
- A página mostra a soma das cargas desenhadas e a das reações, para a conferência do equilíbrio
  (o PP pela gravidade não está nas linhas do plano).

## As direções 1 e 2 da seção no Simulation (`core/direcoes_da_secao.py`)

O Simulation lista os esforços de cada viga nos eixos dela (ajuda do SOLIDWORKS, "Beam Directions"):
o axial do Fim 1 ao Fim 2, a **direção 1 paralela à aresta reta mais longa da seção** e a direção 2 a
90°, no sentido anti-horário. O triedro é destro — conferido nos arquivos reais (a relação entre
momento e cortante de 2 422 elementos de 2 422) — e, nas vigas U deitadas do modelo real, o peso
próprio cai todo no V₁ (a direção 1 é a alma, como diz a regra). Mas o **sentido** da direção 1 muda
de viga para viga no mesmo modelo, e a API do Simulation não o dá. O programa:

1. **A linha da direção 1**: a macro **v6** mede a seção no SolidWorks — a face plana ao longo da
   barra mais larga é a aresta reta mais longa da seção — e grava a direção e a folga para a segunda
   (perto de zero é empate: tubo quadrado, cantoneira de abas iguais). Sem a v6: o perfil (U e I com a
   alma reta bem mais alta que a mesa, tubo retangular) e a alma da v5.
2. **O axial**: pela ponta da base do quadro das fundações (início da lista = Fim 1 embaixo, o axial
   sobe); o peso próprio confere — dentro dos elementos do pilar, a carga do PP aponta para baixo.
3. **O sentido**: num caso com carga distribuída transversal no pilar (o vento viga a viga põe carga
   em cada pilar), a carga que o Simulation mostra dentro dos elementos (V₁ e V₂ de uma ponta menos a
   da outra) tem de apontar para onde o plano de cargas mandou e ter o mesmo tamanho (0,5 a 2 vezes).
   Só um sentido bate. Sem a linha, esse caso dá o ângulo inteiro (dois casos têm de concordar até
   10°); com a linha, a dos resultados tem de ficar a até 20° dela.

A reação horizontal na base é a força que o apoio faz no pilar: `H = F₁·d₁ + F₂·d₂` com a força na
ponta da base. Conferido num pilar em balanço sintético (`tests/test_direcoes_da_secao.py`): H = −q·L
para cinco giros da seção, as duas ordens dos elementos e a direção da macro nos dois sentidos. Com
todos os pilares sabidos e o arquivo de reações do caso, a soma das horizontais é conferida contra
ele (apoio fora dos pilares ou diagonal chegando na base aparecem aí). A página mostra uma tabela com
o axial, as direções 1 e 2 nos eixos do modelo, de onde veio a linha e o caso que deu o sentido — para
conferir no SolidWorks: num gráfico do estudo, Configurações › Mostrar direções da viga (seta verde =
direção 1, azul = direção 2).

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

`tests/test_cena_3d.py`, `tests/test_cena_do_modelo.py`, `tests/test_direcoes_da_secao.py`,
`tests/test_modelo_3d_pagina.py`; o 3D do
vento barra a barra (`components/figuras_vento.svg_vento_3d`) já usa o núcleo.
