# Ligações estruturais

Página **Ligações estruturais** (`app_pages/ligacoes_estruturais.py`), núcleo em `core/ligacoes.py`.
Os esforços entram **de cálculo** (combinação ELU) — por exemplo a reação da viga de piso ou da
longarina. Unidades: mm, MPa, kN e kN·m. Os coeficientes foram conferidos no texto da NBR 8800:2008
e da NBR 14762:2010 e, nas soldas, nas fotos da NBR 8800:2025 (Tabela 9, 6.2.5.2 a e b, Tabelas 10 e
11). A 2025 (chave interna `NBR8800_2024`) muda o coeficiente do corte do parafuso (0,45/0,56), via
`core/bolted_connection.py`, e o número das tabelas das soldas (8 → 9, 9 → 10, 10 → 11). Item da 2025
ainda não visto no texto sai com "(a confirmar)" na referência (segue a 2008). As ligações soldadas
estão em `core/soldas.py` (regras) e `core/ligacoes_soldadas.py` (barra na chapa de nó e chapa no
apoio).

## 1. Chapa simples (viga–viga e viga–pilar) — NBR 8800

Chapa soldada no apoio (alma da viga principal, mesa ou alma do pilar) com dois filetes e parafusada
na alma da viga apoiada, numa linha vertical; mesa superior recortada ou não.

| Verificação | Fórmula | Item |
|---|---|---|
| Parafuso mais solicitado | grupo elástico com V, N e M = V·a; F_Rd = mín(F_v,Rd; F_c,Rd chapa; F_c,Rd alma) | 6.3.3.2, 6.3.3.3 |
| Chapa: escoamento e ruptura por cisalhamento | 0,60·f_y·A_g/γ_a1; 0,60·f_u·A_nv/γ_a2 | 6.5.5 |
| Chapa: colapso por rasgamento | (0,60·f_u·A_nv + C_ts·f_u·A_nt)/γ_a2 ≤ (0,60·f_y·A_gv + C_ts·f_u·A_nt)/γ_a2 | 6.5.6 |
| Chapa: flexão | V·a ≤ f_y·t·h²/4/γ_a1 | 5.4.2 |
| Chapa: tração / compressão | mín(A_g·f_y/γ_a1; A_e·f_u/γ_a2), A_e = A_n ≤ 0,85·A_g / A_g·f_y/γ_a1 | 6.5.3, 6.5.4 |
| Alma da viga: cisalhamento | escoamento e ruptura na linha dos furos (altura recortada) | 6.5.5 |
| Alma recortada | colapso por rasgamento; flexão V·c com só a alma (a favor da segurança); faixa usual do recorte | 6.5.6; AISC Manual Parte 9 |
| Solda no apoio | método elástico com V, N e V·a; 0,60·f_w·(0,707·perna)/γ_w2 | Tabela 9 (2025) / 8 (2008) |
| Metal-base do apoio | 2 filetes na espessura do apoio ≤ 0,60·f_y·t/γ_a1 | 6.5.5 |
| Perna mínima, máxima e comprimento | Tabela 11 (2025) / 10 (2008); t ou t − 1,5 mm; ≥ 4·perna e 40 mm | 6.2.6.2 |
| Disposições | espaçamentos e distâncias às bordas (tipo "limite": não entram no aproveitamento) | 6.3.9 a 6.3.12 |
| Ductilidade | chapa ou alma ≤ d_b/2 + 1,6 mm (ALERTA) | AISC Manual Parte 10 |

A favor da segurança, o momento V·a entra nos parafusos **e** na solda, e a pressão de contato usa a
menor distância livre ℓ_f de cada parte em qualquer direção.

**Trazer de um cálculo ou do modelo** (`reacoes_do_projeto`): as reações ELU dos cálculos
registrados (viga de piso, longarina) e as **pontas das vigas e diagonais do modelo importado** em
Esforços do modelo (`reacoes_do_modelo`): em cada ponta (Fim 1 e Fim 2 da viga no Simulation), a
combinação ELU do plano de cargas com o maior cortante no plano da alma — V₁ quando o eixo forte da
tabela é o M₂, V₂ quando é o M₁ — e o normal na mesma combinação (tração positiva). Barra sem tipo
na tabela entra pelo que o peso próprio diz. Quando a ponta tem momento (mais de 0,5 kN·m), ele vai
no rótulo: a junta do modelo é rígida e a ligação flexível não o leva — articule a ponta no modelo
ou detalhe uma ligação rígida.

## 1b. Dupla cantoneira (viga–viga e viga–pilar) — NBR 8800

Uma cantoneira de cada lado da alma da viga apoiada. Parafusos da alma em corte duplo, com o
momento V·g (g = da face do apoio aos furos), contato nas duas cantoneiras e na alma; parafusos do
apoio em corte simples com V/(2n) (a excentricidade da aba curta é desprezada) e contato na
cantoneira e no apoio. Cantoneiras ao cisalhamento (6.5.5) e ao colapso por rasgamento da aba na
alma (6.5.6); a alma da viga como na chapa simples; furo à borda da aba e folga para apertar o
parafuso (gabarito ≥ t + d_b).

## 2. Perfil formado a frio parafusado — NBR 14762:2010

Perfil ligado pela alma a uma chapa, grade de parafusos com forças iguais (sem momento no grupo).

| Verificação | Fórmula | Item |
|---|---|---|
| Corte do parafuso | 0,4 (rosca no plano) ou 0,5·A_b·f_ub/1,35 por plano | 10.3.7 |
| Rasgamento | t·e·f_u/1,45 (e = borda ou passo, na direção da força) | 10.3.4 |
| Esmagamento | α_e·d·t·f_u/1,55, α_e = 0,183·t + 1,53 | 10.3.5 |
| Tração no perfil | mín(A·f_y/1,10; C_t·A_n·f_u/1,65), C_t = 1 − 1,2·x̄/L ∈ [0,4; 0,9] ou 2,5·d/g | 9.6.2 |
| Colapso por rasgamento | (0,6·A_gv·f_y + A_nt·f_u)/1,65 e (0,6·A_nv·f_u + A_nt·f_u)/1,65 | 10.4 |
| Espaçamentos | livre entre furos ≥ 2·d; livre à borda ≥ d | 10.3.3.1 |
| Regra dos 50 % | barra de treliça/contraventamento: ligação ≥ 0,5·N_Rd da barra | 10.1 a) |

Peça com mais de 4,75 mm segue a NBR 8800 (10.3.1). Furo-padrão d + 0,8 (d < 12,5 mm) ou d + 1,5 mm
(Tabela 15). Aços: Tabela 1 (ZAR, CF) e o limite de 180/300 MPa para aço sem qualificação (4.2);
parafusos: Tabela 16 e 300 MPa sem qualificação (4.4).

## 3. Grupo de filetes no plano

Um filete, dois paralelos (verticais ou horizontais), três lados em C ou o contorno de um retângulo,
com V, N e momento no plano, perna uniforme. Chapa mais fina acima de 4,75 mm, NBR 8800:

| Caso | Metal da solda | Item |
|---|---|---|
| Método elástico (opção, a favor da segurança) | maior força por mm ≤ 0,60·f_w·(0,707·d_w)/γ_w2 | Tabela 9 / 8 |
| Carga pelo centro, filetes em linha ou paralelos | × (1 + 0,5·sen^1,5 θ), θ entre a resultante e o eixo dos filetes | 6.2.5.2 a) |
| Carga pelo centro, filetes longitudinais e transversais (V ou N puro) | o maior entre F_wl + F_wt e 0,85·F_wl + 1,5·F_wt | 6.2.5.2 c) |
| Com momento | centro instantâneo de rotação: Δu = 1,087·(θ + 6)^−0,65·d_w ≤ 0,17·d_w, Δm = 0,209·(θ + 2)^−0,32·d_w (AISC 360-16 J2.4), f(p) = [p·(1,9 − 0,9·p)]^0,3; o elemento crítico limitado pela ponta | 6.2.5.2 b) |

Carga inclinada pelo centro num grupo com filetes nas duas direções fica no método elástico (6.2.5.2 a
vale para filetes em linha ou paralelos). O metal-base pela força por mm do método elástico,
0,60·f_y·t/γ_a1 e 0,60·f_u·t/γ_a2 na parte menos espessa (6.5.5). Até 4,75 mm: NBR 14762 10.2.3
(metal-base fino pela direção mais desfavorável e, com t > 2,5 mm, 0,75·t_ef·f_w/1,65). A
capacidade é linear na perna, então a página mostra a **perna necessária** = perna × aproveitamento.
Combinação normal/especial/de construção (γ_a1 1,10, γ_a2 1,35, γ_w1 1,25, γ_w2 1,35) ou excepcional
(1,00, 1,15, 1,05, 1,15).

## 4. Barra soldada na chapa de nó

Cantoneira ligada por uma aba ou tala de chapa sobreposta, de um lado ou dos dois lados da chapa de
nó, com filetes longitudinais no dorso e na borda e, se pedido, transversal na ponta. Modo
**dimensionar** (acha os comprimentos, arredondados no passo de 5 mm) ou **verificar**.

| Verificação | Fórmula | Item |
|---|---|---|
| Força da ligação | máx(N_t,Sd; N_c,Sd); ≥ 45 kN (exceções da norma); Anglo: ≥ 75 % de A_g·f_y/γ_a1 da barra e 3 t | 6.1.5.2; Anglo 9.1 |
| Filetes do dorso e da borda | balanceados: F₁ = N·(C − x̄)/C − F₃/2, F₂ = N·x̄/C − F₃/2 (6.1.8.1); ou iguais (6.1.8.2, cantoneira sem fadiga); por mm, o menor entre o metal da solda, o metal-base da barra e o da chapa de nó (dividido pelas peças nas mesmas linhas); β do filete longo | 6.2.5.1, 6.5.5, 6.2.2.2 d) |
| Filete na ponta | F₃ = q·C (primeira expressão de 6.2.5.2 c); grupo: o maior entre F_wl + F_wt e 0,85·F_wl + 1,5·F_wt | 6.2.5.2 c) |
| Perna, comprimento, cobrimento | Tabela 11; t − 1,5 mm na borda; ≥ 4·perna e 40 mm; cobrimento ≥ 5·t e 25 mm; tala só com filetes longitudinais: cada filete ≥ largura | 6.2.6.2 |
| Barra à tração | A_g·f_y/γ_a1; C_t·A_g·f_u/γ_a2, cantoneira C_t = 1 − x̄/ℓ_c (ℓ_c = média dos filetes) ∈ [0,60; 0,90]; tala 1,00/0,87/0,75 por ℓ_w/b | 5.2.2, 5.2.5 |
| Chapa de nó | seção de Whitmore b_W = C + (L_dorso + L_borda)·tg 30° (limitada à largura da chapa): tração (escoamento e ruptura), compressão (KL/r ≤ 25 ou χ da 5.3, r = t/√12, K informado); colapso por rasgamento com A_gv = t·(L_dorso + L_borda), A_nt = t·C | 6.5.3, 6.5.4, 6.5.6 |
| Chapa de nó no apoio | o caso 5 com a força da barra: H = N·sen θ normal ao apoio, V = N·cos θ ao longo da solda, M = H·e | — |

## 5. Chapa soldada no apoio (junta em T)

Filete de um ou dos dois lados, contínuo ou intermitente (segmentos iguais, distribuídos na junta),
penetração total ou parcial. Forças por mm pelo método elástico na linha de solda (com os segmentos).

| Verificação | Fórmula | Item |
|---|---|---|
| Filete | sem momento: × (1 + 0,5·sen^1,5 θ); com momento: sem o aumento (a carga fica fora do plano dos filetes) | Tabela 9, 6.2.5.2 a) |
| Penetração total | A_MB·f_y/γ_a1 à tração ou compressão normal (com momento: N/N_Rd + M/M_Rd, Z = t·L²/4), 0,60·A_MB·f_y/γ_a1 ao cisalhamento; metal da solda compatível (tração: só a maior classe do grupo; compressão na 2025: até 70 MPa abaixo) | Tabela 9; Tabela 7 (2008) |
| Penetração parcial | 0,60·A_w·f_w/γ_w1 (normal), /γ_w2 (cisalhamento; combinado pela resultante com γ_w2); garganta S ou S − 3 mm (Tabela 5 da 2008); garganta mínima | Tabela 9, Tabela 10 |
| Chapa junto à solda | tração (escoamento e ruptura), compressão, N + M linear, cisalhamento (escoamento e ruptura) no comprimento soldado | 6.5.3 a 6.5.5 |
| Apoio | metal-base junto à solda (a parcela ao longo da solda); na mesa de perfil I/H: flexão local da mesa (dispensada com atuação < 0,15·b_f), escoamento local e enrugamento da alma, k = t_f | 6.5.5; 5.7.2 a 5.7.4 |
| Intermitente | só quando a contínua de perna mínima já sobra; segmento ≥ 4·perna e 40 mm; os segmentos cabem na junta | 6.2.6.2.4 |

## Exemplos resolvidos e casos de aceite

A página traz quatro exemplos de solda (talas sobrepostas, filete intermitente, penetração total e a
cantoneira de contraventamento na chapa de nó e no pilar) que preenchem os campos com um clique. Os
mesmos números estão nos casos de aceite da Central de validação (`core/casos_de_aceite.py`). Onde a
apostila verifica o "metal-base" do filete pela face de fusão (0,60·d_w·L·f_y/γ_a1, critério antigo),
a norma pede a 6.5 na espessura das peças — e os comprimentos adotados mudam (exercício 4: filetes de
120 e 50 mm em vez de 130 e 55; solda no pilar de 50 mm em vez de 70). No exercício 1 a norma pede
cobrimento ≥ 5·t = 47,6 mm e cada filete ≥ a largura da tala.

## Fora do programa

Ligação rígida (com momento), chapa de extremidade, enrijecedores, efeito de alavanca, parafusos
auto-atarraxantes, a verificação do apoio como um todo, solda de tampão, filetes de pernas
diferentes, o acréscimo da garganta do arco submerso, a fadiga e a flambagem da barra comprimida —
casos específicos ficam com o projetista.
