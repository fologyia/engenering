# Contraventamento de estruturas abertas — escopo, fórmulas e conferências

A página **Contraventamento de estruturas abertas** dimensiona o contraventamento vertical de
plataformas, mezaninos, pipe racks e outras estruturas **sem fechamento**, da planta à diagonal
verificada, sem montar o modelo estrutural. O núcleo não depende do Streamlit.

| Arquivo | O que faz |
| --- | --- |
| `core/vento_estrutura_aberta.py` | vento por reticulados planos (NBR 6123:2023, capítulo 8): Figuras 12 e 14, Tabelas 27 e 28, forças por nível |
| `core/contraventamento_vento_barras.py` | vento viga a viga, pilar a pilar, pelo esqueleto do modelo, levado aos pisos (faixas, níveis e planta do esqueleto, excentricidade real) |
| `core/load_combinations.py` | combinações (ELU normal, especial, excepcional; ELS rara, frequente, quase permanente), grupos exclusivos e envoltória rigorosa por esforço |
| `core/contraventamento_plataforma.py` | ações, cortante de cada andar, B₂, distribuição entre as linhas, forças nas diagonais, deslocamentos |
| `core/contraventamento_barras.py` | verificação das diagonais (cantoneira, tubo, tirante) e da ligação delas na chapa de nó |
| `core/cantoneiras.py` | cantoneiras de abas iguais (seção idealizada, série em polegadas) |
| `core/contraventamento_estrutura_registro.py` | registro no projeto e tabelas do memorial |
| `components/contraventamento_estrutura_ui.py`, `..._help.py` | interface e textos dos "?" |
| `app_pages/contraventamento_estrutura.py` | a página |

## Vento (NBR 6123:2023, capítulo 8)

* Cada pórtico perpendicular ao vento é um **reticulado plano**: `F_a = C_a·q·A_e` (8.3), com
  `C_a` da **Figura 12** em função do índice de área exposta `φ = A_e/A_contorno` (transcrita da
  figura: 2,0 → 1,6 de φ = 0 a 0,5; 1,6 até 0,7; volta a 2,0 em φ = 1).
* O pórtico de barlavento recebe a força cheia; cada um dos seguintes é multiplicado pelo **fator de
  proteção η** da **Figura 14** (retas de η = 1,1 em φ = 0 até o patamar em φ = 0,6; patamares 0,2;
  0,3; 0,4; 0,5; 0,6; 0,7; 0,8 e 1,0 para `e/h_b` ≤ 0,5; 1; 2; 3; 4; 5; 6 e ≥ 7; η ≤ 1). `h_b` é a
  menor dimensão do pórtico (a favor da segurança: dá `e/h_b` maior e η maior).
* A área exposta de cada pórtico: pilares (maior medida da seção), vigas de cada piso e, nos
  pórticos contraventados, as diagonais.
* **Guarda-corpos**: reticulados à parte, com φ próprio (≈ 0,30 com o rodapé); só os
  perpendiculares ao vento carregam (8.5); o de sotavento com η pela distância entre eles.
* **Equipamentos**: cilindro vertical pelas Tabelas 27 (C_a por Reynolds) e 28 (fator K, com a
  base no piso obstruída — ℓ/d dobra, 8.1.3); caixa ou painel com C_a = 2,0 ou o informado.
* As forças vão aos pisos por **faixas de influência** (meia altura do andar de baixo e de cima); a
  metade inferior do primeiro andar vai à fundação. `q` de cada faixa é o do seu topo.
* Simplificação a favor da segurança: barras circulares também usam a Figura 12 (1,6 a 2,0 contra
  1,1 da Figura 13).

### Preencher pelo esqueleto (`core/contraventamento_do_esqueleto.py`)

Com o esqueleto no projeto, a seção 2 mostra o que ele diz e o botão **Preencher pelo esqueleto**
põe na página:

* **Pilares**: barras em pé (até 15° do prumo) com o pé no chão e o topo no primeiro piso — o poste
  de um patamar de escada não conta (aviso). As linhas de pilares dão os vãos e L_x, L_y **entre
  eixos**; com os pilares numa linha só numa direção, a medida do piso e o aviso de balanço.
* **Pisos**: as cotas das vigas deitadas e a **área de piso** pelas chapas deitadas de cada nível
  (o peso por área multiplica essa área, não L_x × L_y; campo "Área de piso por nível").
* **Diagonais**: inclinadas (15° a 75°) num plano vertical X ou Y, vencendo pelo menos metade do
  andar e saindo do pé de um pilar. Mão-francesa e longarina de escada não contam. Cruzadas no mesmo
  plano e andar = X; encontrando-se em cima = V invertido; sozinha = diagonal simples. Duas barras no
  mesmo lugar (pontas a menos de 15 cm) contam uma vez, com aviso — no Simulation, cada corpo é
  uma viga inteira (o modelo real tinha uma diagonal T assim).
* **Perfis**: o mais comum dos pilares e das vigas; o das diagonais, se for cantoneira, tubo ou
  barra redonda do catálogo (senão, aviso: a página não verifica aquele perfil).
* **Direção sem diagonal**: aviso de que a estabilidade nela é de pórtico (engaste, ligação rígida,
  mãos-francesas) e a página não verifica isso.

Os avisos e o que a página tiver diferente do esqueleto aparecem no topo dos resultados.
**Chão**: o pé dos pilares (`vpb.terreno_dos_pilares`) — uma longarina de escada que desce abaixo da
base não puxa o chão para baixo (no modelo real, 15 cm), nem no vento viga a viga.

### Viga a viga, pilar a pilar (o esqueleto do modelo)

O seletor **Como o vento chega à estrutura** troca a grade da seção 2 pelo esqueleto que a macro do
SolidWorks exportou — para o que não é grade (duas colunas, escada, balanço):

* Cada barra recebe o vento dela (`core/vento_por_barras.py`, ver `docs/vento_barra_a_barra.md`):
  sombra `ℓ·sen θ·c`, φ e C_a do plano a que pertence, proteção η; os guarda-corpos das bordas do
  piso (Cargas do esqueleto) e os equipamentos da tabela (no centro da planta dos pisos, apoiados no
  piso do nível deles) entram como elementos.
* A força vai aos pisos pelas **mesmas faixas** da grade: a de uma barra se divide na proporção da
  altura que ela tem em cada faixa (carga uniforme); a de um elemento vai à faixa da cota do centro;
  acima da faixa do último piso, tudo vai para ele; a parte de baixo do primeiro andar, à fundação.
  A soma dos níveis e da base fecha com o vento da direção (teste).
* **Uma ação por direção calculada** (W0, W45 … W315) no grupo exclusivo do vento: as
  perpendiculares carregam uma direção do contraventamento; as diagonais, X e Y juntas. W0 e W180 têm
  cada um o seu valor (o plano de barlavento muda).
* **Excentricidade**: a resultante do vento perpendicular passa onde a estrutura a põe, medida do
  centro da planta dos pisos; a informada nos ajustes (6.1.4: vento oblíquo e vizinhança, a partir
  do eixo) soma-se a ela, até 0,5. Acima de 2,5 %, aviso com os dois valores.
* **Conferências**: as cotas dos pisos contra os níveis de vigas do esqueleto (grupos de vigas
  deitadas a até 15 cm, com pelo menos 25 % do comprimento do maior; botão para usar as do
  esqueleto) e L_x × L_y contra a planta dos pisos do esqueleto (aviso se não batem ou se parecem
  trocadas). O peso por área e os painéis continuam a usar as medidas da página.
* A aba **Vento** mostra o vento por nível caso a caso, a comparação com os pórticos regulares andar
  por andar, a figura 3D de cada direção, os planos (φ, C_a, η), o CSV das cargas por barra e o
  envio ao plano de cargas; o memorial leva as mesmas tabelas.

## Ações e combinações

| Ação | Categoria (NBR 8800, Tabelas 1 e 2) | Esforços |
| --- | --- | --- |
| Estrutura | peso próprio de estrutura metálica (1,25 / 1,0) | gravidade acima do andar + nocional |
| Piso | elementos construtivos industrializados (1,35 / 1,0) | idem |
| Equipamentos | peso de equipamentos (NBR 8800:2025: 1,25; ou 1,50 na 2008) | idem |
| Sobrecarga | sobrecarga de uso (1,50; ψ por tipo de uso) | idem |
| Vento +X, −X, +Y, −Y (grade) ou W0 … W315 (viga a viga) | vento (1,40; ψ 0,6 / 0,3 / 0) — **grupo exclusivo** | cortante do andar |
| Forças horizontais | equipamentos em operação, truncada, ponte rolante ou excepcional | cortante dos andares abaixo do nível |

* **Força nocional** (4.10.7.1.1): cada ação gravitacional leva 0,3 % do seu valor como força
  horizontal no andar, **reversível** (entra sempre no sentido desfavorável) e com os mesmos γ e ψ —
  é "0,3 % das forças gravitacionais de cálculo". Fica em todas as combinações últimas, como pede
  4.10.7.1.4-b para dispensar a análise global de segunda ordem na pequena deslocabilidade.
* O cortante de cálculo de cada andar é a **envoltória rigorosa** (`load_combinations.extremo`):
  cada variável testada como principal; permanente com γ desfavorável ou favorável conforme o sinal;
  acompanhante só se agrava (nota a da Tabela 1: variável favorável não entra); um membro por grupo
  exclusivo. A combinação governante aparece por extenso na tabela dos andares e no memorial.
* A lista explícita de todas as combinações (ELU normal, ELS rara, frequente e quase permanente)
  aparece na aba "Combinações e andares".

## Segunda ordem (Anexo C e 4.10)

`B₂ = 1/[1 − (1/R_s)·(Δh/h)·(ΣN_Sd/ΣH_Sd)]` com `R_s = 1` (só treliças) e `Δh/ΣH = 1/K`, sendo
`K` a rigidez axial das diagonais ativas do andar (`E·A·cos²α/L` por diagonal). `ΣN_Sd` é a maior
força gravitacional de cálculo acima do andar (4.10.4.7). Até 1,10: pequena deslocabilidade; até
1,40: média — as forças são amplificadas pelo `B₂` calculado com 80 % da rigidez (4.10.7.1.2 e
4.10.7.1.3); acima: grande (NÃO OK; o método não vale).

## Forças nas diagonais

`N = f·V_Sd·B₂/(n_painéis·n_ativas·cos α)`, com `f = 1/n + e·y_máx/Σy²` (linhas igualmente
espaçadas; duas linhas nas bordas: `f = 0,5 + e`), `e` = excentricidade informada (7,5 % por
padrão, como a NBR 6123 6.1.4). Diagonais ativas por painel: X só tração 1 (a comprimida é
desprezada); X tração e compressão 2; diagonal simples 1 (inverte); V invertido 2 (cada uma vence
meio painel).

## Verificação das diagonais (NBR 8800:2025)

* **Cantoneira simples ligada por uma aba**: tração com `A_n = A_g − (d_h + 2)·t` e
  `C_t = 1 − e_c/ℓ_c ≥ A_c/A_g` (5.2.4 e 5.2.5-c; com "Furos feitos com broca", A_n sem os 2 mm
  do furo, 5.2.4.1 a); compressão por 5.3.5.4 (`L_x1,eq = 72·r_x1 +
  0,75·L_x1` ou `32·r_x1 + 1,25·L_x1`, `N_ex = π²·E·I_x1/L_eq²`, Q do grupo 3); esbeltez
  equivalente ≤ 200; parafusos (6.3.3.2 e 6.3.3.3), colapso por rasgamento da aba (6.5.6), passo ≥
  2,7·d (6.3.9) e borda ≥ Tabela 16 (6.3.11).
* **Tubo** com chapa concêntrica soldada num rasgo: `A_n` sem o rasgo, `C_t = [1 + (e_c/ℓ_c)^3,2]^−10`
  (5.2.5-e) com `e_c = D/π − t_c/2` no circular e `(h² + 2hb)/[4(h + b)] − t_c/2` no retangular
  (Figuras 6 e 7 da 2025; o maior das duas orientações), compressão pela 5.3 e solda de
  quatro cordões (6.2.5, γ_w2 = 1,35).
* **Barra redonda rosqueada** (tirante): `N_t,Rd = mín(0,75·A_b·f_u/γ_a2; A_b·f_y/γ_a1)` (5.2.7 e
  6.3.3.1); só em X só tração.
* Esbeltez: tração ≤ 300 (recomendação de 5.2.8.1, dispensada no tirante pré-tensionado); no X
  ligado no cruzamento, o comprimento destravado é a metade da diagonal.
* **Cantoneiras**: seção idealizada (dois retângulos, sem raios) — fica a menos de 1,5 % das
  tabelas do AISC (conferido nos testes).

## Deslocamentos (Anexo B, Tabela B.1, ou o critério do cliente)

Deformação axial das diagonais da linha mais carregada, na combinação de serviço escolhida (rara ou
frequente): um piso, `H/300`; dois ou mais, `H/400` no topo e `h/500` entre pisos. Em **Limite do
deslocamento** (aba de ajustes) dá para escolher o tipo de estrutura da Tabela 4 do critério Anglo —
plataforma de equipamentos H/400, pipe rack ou cable rack H/250, estrutura com cobertura H/400 (com
`h/500` entre pisos quando há mais de um) —, que vem da base técnica do projeto.

## Critério Anglo

Com a chave **Aplicar o critério Anglo** (ligada quando a base técnica é a da Anglo), a diagonal
ganha as exigências do critério: espessura mínima da cantoneira (8.8), redução do comprimento para
montagem com protensão (8.2, Tabela 5), diâmetros mínimos de tirante e parafuso (8.8), parafuso até
1" e A325 (9.1) e capacidade mínima da ligação (9.1). Detalhes em `docs/criterio_anglo.md`.

## Desenhos e saídas para o modelo

A aba **Desenhos** mostra a planta com as linhas contraventadas, a elevação de cada linha com as
diagonais e as forças, o vento nos pórticos e o gráfico do cortante por andar. A aba **Vento** traz as
forças nos nós por pórtico e o botão que envia W0, W90, W180 e W270 ao **Plano de cargas**; a página
**Vento em estruturas abertas** usa os mesmos campos para quem só quer as forças (ver
`docs/fluxo_do_projeto.md`).

## Ligação

A aba "Ligação" mostra a diagonal mais solicitada (tração, compressão e ângulo com a vertical) e o
botão leva esses valores — e a chave do critério Anglo — para a página **Ligação de
contraventamento**, que dimensiona a chapa de nó (modo simplificado) pelo AISC DG29.

## Fora do escopo

Pilares, vigas e bases (o programa dá o acréscimo de força nos pilares do painel), contraventamento
horizontal do piso (grade não é diafragma), efeitos dinâmicos, sismo, vento oblíquo, deformação axial
dos pilares e a compressão que ela induz nas diagonais.

## Testes

`tests/test_vento_estrutura_aberta.py` (figuras e tabelas da norma, exemplo conferido à mão),
`tests/test_contraventamento_vento_barras.py` (faixas, soma que fecha, níveis, planta, excentricidade,
ações caso a caso, registro), `tests/test_contraventamento_do_esqueleto.py` (planta, vãos, área,
X/V/simples, mão-francesa, poste, sobrepostas, balanço, conferência),
`tests/test_contraventamento_barras.py`, `tests/test_contraventamento_plataforma.py` (ações,
envoltória, B₂, tipos, deslocamentos, registro e memorial), `tests/test_combinacoes_nbr8681.py` e
`tests/test_contraventamento_estrutura_pagina.py`.
