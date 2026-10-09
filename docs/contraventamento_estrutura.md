# Contraventamento de estruturas abertas — escopo, fórmulas e conferências

A página **Contraventamento de estruturas abertas** dimensiona o contraventamento vertical de
plataformas, mezaninos, pipe racks e outras estruturas **sem fechamento**, da planta à diagonal
verificada, sem montar o modelo estrutural. O núcleo não depende do Streamlit.

| Arquivo | O que faz |
| --- | --- |
| `core/vento_estrutura_aberta.py` | vento por reticulados planos (NBR 6123:2023, capítulo 8): Figuras 12 e 14, Tabelas 27 e 28, forças por nível |
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

## Ações e combinações

| Ação | Categoria (NBR 8800, Tabelas 1 e 2) | Esforços |
| --- | --- | --- |
| Estrutura | peso próprio de estrutura metálica (1,25 / 1,0) | gravidade acima do andar + nocional |
| Piso | elementos construtivos industrializados (1,35 / 1,0) | idem |
| Equipamentos | peso de equipamentos (Projeto 2024: 1,25; ou 1,50) | idem |
| Sobrecarga | sobrecarga de uso (1,50; ψ por tipo de uso) | idem |
| Vento +X, −X, +Y, −Y | vento (1,40; ψ 0,6 / 0,3 / 0) — **grupo exclusivo** | cortante do andar |
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

## Verificação das diagonais (NBR 8800:2024)

* **Cantoneira simples ligada por uma aba**: tração com `A_n = A_g − (d_h + 2)·t` e
  `C_t = 1 − e_c/ℓ_c ≥ A_c/A_g` (5.2.4 e 5.2.5-c); compressão por 5.3.5.4 (`L_x1,eq = 72·r_x1 +
  0,75·L_x1` ou `32·r_x1 + 1,25·L_x1`, `N_ex = π²·E·I_x1/L_eq²`, Q do grupo 3); esbeltez
  equivalente ≤ 200; parafusos (6.3.3.2 e 6.3.3.3), colapso por rasgamento da aba (6.5.6), passo ≥
  2,7·d (6.3.9) e borda ≥ Tabela 16 (6.3.11).
* **Tubo** com chapa concêntrica soldada num rasgo: `A_n` sem o rasgo, `C_t = [1 + (e_c/ℓ_c)^3,2]^−10`
  (5.2.5-e; no tubo retangular, o maior `e_c` das duas orientações), compressão pela 5.3 e solda de
  quatro cordões (6.2.5, γ_w2 = 1,35).
* **Barra redonda rosqueada** (tirante): `N_t,Rd = mín(0,75·A_b·f_u/γ_a2; A_b·f_y/γ_a1)` (5.2.7 e
  6.3.3.1); só em X só tração.
* Esbeltez: tração ≤ 300 (recomendação de 5.2.8.1, dispensada no tirante pré-tensionado); no X
  ligado no cruzamento, o comprimento destravado é a metade da diagonal.
* **Cantoneiras**: seção idealizada (dois retângulos, sem raios) — fica a menos de 1,5 % das
  tabelas do AISC (conferido nos testes).

## Deslocamentos (Anexo B, Tabela B.1)

Deformação axial das diagonais da linha mais carregada, na combinação de serviço escolhida (rara ou
frequente): um piso, `H/300`; dois ou mais, `H/400` no topo e `h/500` entre pisos.

## Ligação

A aba "Ligação" mostra a diagonal mais solicitada (tração, compressão e ângulo com a vertical) e o
botão leva esses valores para a página **Ligação de contraventamento**, que dimensiona a chapa de nó
(modo simplificado) pelo AISC DG29.

## Fora do escopo

Pilares, vigas e bases (o programa dá o acréscimo de força nos pilares do painel), contraventamento
horizontal do piso (grade não é diafragma), efeitos dinâmicos, sismo, vento oblíquo, deformação axial
dos pilares e a compressão que ela induz nas diagonais.

## Testes

`tests/test_vento_estrutura_aberta.py` (figuras e tabelas da norma, exemplo conferido à mão),
`tests/test_contraventamento_barras.py`, `tests/test_contraventamento_plataforma.py` (ações,
envoltória, B₂, tipos, deslocamentos, registro e memorial), `tests/test_combinacoes_nbr8681.py` e
`tests/test_contraventamento_estrutura_pagina.py`.
