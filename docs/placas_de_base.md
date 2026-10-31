# Placas de base — base de pilar pela NBR 8800:2025, Subseção 6.7

A página **Placas de base** (`app_pages/placa_de_base.py`, núcleo em `core/base_de_pilar.py`, desenho
em `core/desenho_placa_base.py`) verifica a ligação de um pilar de perfil **I ou H** ao bloco de
concreto: placa retangular soldada no pilar, chumbadores com porca sextavada pesada e argamassa
expansiva de assentamento (6.7.1.2). As fórmulas da 6.7 são do momento em torno do eixo de maior
inércia (6.7.1.3); com momento também no eixo de menor inércia, a base vai pelo mesmo método em duas
direções (flexão oblíqua, abaixo).

A página **Esforços do modelo** continua verificando as placas de base de todos os pilares do modelo,
pelo AISC Design Guide 1 com a pressão de contato da 6.6.5 (2025) e o critério Anglo
(`core/placa_base_pilares.py`). Esta página é a verificação de **uma** base pelo método da NBR.

## Entradas

| Campo | Uso |
| --- | --- |
| Perfil do pilar | W, HP ou I duplamente simétrico do catálogo (6.7.1.1); U e outros são recusados. |
| Disposição | Tipo 1: externos às mesas, 4 ≤ n_b ≤ 8 em duas linhas; tipo 2: 4 entre as mesas (Figura 21); **rotulada**: 2 internos, um de cada lado da alma, no eixo; **internos e externos**: 4 + 4 (as duas últimas pelo método geral). |
| Chumbador | Ø 3/4" a 2" (Tabela 18); a₁ e a₂ da tabela ou maiores (o toggle libera os campos); no tipo 2, também o a₁ da direção ℓx, de 10 mm ao da tabela (nota f). |
| Tipo do chumbador | Reto com porca e chapa na ponta (Tabela 18), **guarda-chuva** (gancho em J ou L, e_h), **químico** ou **parabolt** (pós-instalados, com o N_Rd do fabricante); embutimento h_ef; chapa na ponta; opção de verificar a ancoragem no concreto e de armadura de ancoragem no bloco. |
| Aço do chumbador | ASTM A36 e F1554 Gr 36 (equivalentes, 6.7.1.5 c), F1554 Gr 55 e Gr 105, A193 B7, SAE 1020. |
| Placa | Espessura, aço (ASTM A36, A572 Gr 50, A588) e argamassa e_n (0 = Tabela 18). |
| Concreto | f_ck do bloco, combinação (γ_c = 1,4 ou 1,2) e o bloco (N_b × B_b) ou A₂/A₁ direto. |
| Esforços | N_Sd (+ compressão), M_Sd, M_Sd,y (eixo de menor inércia) e V_Sd (a resultante) de cálculo no pé do pilar. |
| Cortante | Atrito (μ = 0,45), placa de cisalhamento (b_v, b_h, t_pv) ou arruelas soldadas (t_a). |

## Cálculo (`calcular`)

* **Geometria (6.7.2.1)**: ℓx = d + 4a₁ (no tipo 2, com o a₁ da direção ℓx); ℓy = (0,5n_b − 1)a₂ + 2a₁ ≥ b_f + 25 mm; ℓ₀ = (0,5n_b − 1)a₂
  + 1,75(a₂ − t_w) ≤ d (tipo 2); m, n, n₀, X ≤ 1 e λ; a = ℓx/2 − a₁ (tipo 1) ou a₂/2 (tipo 2).
* **Concreto**: σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c (6.6.5 da 2025; o teto vem com
  A₂/A₁ = 4). Com o bloco informado, A₂ é a área dele quando é homotético à placa (6.6.5 a) e, quando
  não é, a maior área homotética e concêntrica que cabe nele (6.6.5 b; a Figura 20 não foi vista —
  é a regra da ACI 318 e da AISC J8). τ_c,Rd = 0,2f_ck/γ_c ≤ 4 MPa.
* **Caso (6.7.1.4)**: C1 (e = 0), C2 (e ≤ ½(ℓx − N/(σ_c,Rd·ℓy))), C3; T1 (e = 0), T2 (e ≤ a), T3. A
  base tipo 2 só cobre C1, C2, T1 e T2. As contas usam N·(e ± a) = M ± N·a, então a flexão pura
  (N = 0) cai em C3 sem dividir por zero.
* **Placa e chumbadores (6.7.2.2 a–f)**: t_p,min de cada caso (ℓ_max·√(2σ/(f_y/γ_a1)) e, com tração,
  √(2n_b·F_t(m − a₁)/(ℓy·f_y/γ_a1)); no tipo 2, √(n_b·F_t(a₂ − t_w)/(ℓ₀·f_y/γ_a1))); ℓ_c de C3 e T3
  pela raiz da equação de equilíbrio (sem raiz: "alterar a ligação"); F_t por chumbador e
  d_b,min = √(4F_t/(0,75π·f_ub/γ_a2)), f_ub = 400 MPa.
* **Cortante**: V_Rd = μσℓ_cℓy/γ_a2 ≤ τ_c,Rd·ℓx·ℓy; sem pressão de contato (T1, T2) não há atrito.
  Com dispositivo, só ele resiste (6.7.2.3): placa de cisalhamento (6.7.2.4: V_Rd = σ_c,Rd(A₂/A₁ = 4)·
  (b_v − e_n)·b_h, t_pv,min, t_pv ≤ t_p e os esforços na solda) ou arruelas soldadas (6.7.2.5: V_Rd,i
  com a interação com a tração, ≤ 5d_b²σ_c,Rd). Nas arruelas, F_v,Rd,i é o menor entre o corte do
  chumbador com a rosca no plano, 0,45·A_b·f_ub/γ_a2 (6.3.3.2 a), e o contato no furo da arruela,
  mín(1,2·ℓ_f; 2,4·d_b)·t_a·f_u/γ_a2 (6.3.3.3, que a 6.3.3.2 manda atender; furo d_b + 1,5 mm, f_u =
  450 MPa do aço de f_y = 345 MPa, ℓ_f até a borda da arruela). Só as arruelas de cima se soldam, com
  solda para F_v,Rd,i.
* **Tabela 18 e notas** (valores e notas a–i conferidos no texto da 2025):
  * limites: a₁ e a₂; no tipo 2, 10 mm ≤ a₁ em ℓx ≤ o da tabela (nota f); f_ck ≥ f_ck,mín no reto
    com porca (nota b: o concreto junto à porca da ponta); bloco informado com N_b ≥ máx(N_b,mín;
    ℓx + 2e_n; ℓx + 2(a₃ − a₁)) e B_b ≥ máx(ℓy + 2e_n; ℓy + 2(a₃ − a₁)) (nota e; no tipo 2 é a
    borda da placa a a₃ − a₁ da face, nota g);
  * nota a (A36, de 4 a 8 chumbadores): aço fora do A36 ou a rotulada (2) com o reto com porca
    ficam em ALERTA até a ancoragem no concreto ser verificada (então INFO);
  * detalhamento: furo d_f (nota i), ancoragem h₁/h₂/r₁/r₂, arruela de f_y = 345 MPa com furo
    d_b + 1,5 mm (notas a e c), também entre a placa e a porca de nivelamento, soldada só para a
    cortante (nota d), argamassa, bloco mínimo com a altura máx(h₁ + 100; N_b) (nota e) e a
    armadura mínima com d_a ≤ ½·[h₁ − 0,5(r₂ + d_b)] (nota h). Sem bloco informado, o cone usa o
    bloco mínimo da nota e.
* **Base mais leve** (`base_mais_leve`): percorre os 7 diâmetros e as espessuras comerciais (6,3 a
  100 mm) e devolve a placa de menor massa que atende; o botão **Adotar** troca o chumbador e a
  espessura da página. Sem resultado quando o que reprova não depende da placa (cortante, concreto).

Saídas: verificações por grupo (geometria, concreto e placa, chumbadores, cortante, Tabela 18), CSV,
desenho (planta e corte, chumbadores tracionados em vermelho, pressão de contato no trecho ℓ_c), o
memorial desta base em Word ou PDF e o registro no projeto (o memorial redesenha a figura pela
entrada gravada em `figura_base_de_pilar`).

## Disposições fora da Figura 21 (método geral)

A 6.7.1.1 admite outras configurações desde que atendam 6.1.1.3. Para a **rotulada** e a de
**internos e externos**, o programa usa o mesmo método com os chumbadores em mais de uma linha
(`equilibrio_geral`, `forcas_sem_contato`, `_espessura_pela_tracao`):

* **C3 e T3:** bloco σ_c,Rd no trecho ℓ_c da borda comprimida; cada chumbador à esquerda da borda
  desse trecho, x_n = ℓx/2 − ℓ_c, com força proporcional a (x_n − x_i) — placa rígida. Vale o menor
  ℓ_c que equilibra N e M. Com uma só linha tracionada, dá a equação de ℓ_c da norma (testado).
* **T1 e T2:** F_i = |N|/n − M·x_i/Σx²; T2 enquanto todos F_i ≥ 0 (o limite é M ≤ |N|·Σx²/(n·x_máx),
  que é o ``a`` nos tipos 1 e 2).
* **Espessura pela tração:** fora das mesas, t = √(4·T_linha·c/(ℓy·f_y/γ_a1)), c = |x| − 0,475·d
  (a conta do tipo 1); entre as mesas, de cada lado da alma, t = √(2·n·F_máx·(a₂ − t_w)/(ℓ₀·f_y/γ_a1))
  com ℓ₀ = (n − 1)·s + 1,75·(a₂ − t_w) (a conta do tipo 2). A arruela dos internos precisa caber entre
  a alma e as mesas.
* A rotulada só aguenta o momento que o concreto faz sozinho (os chumbadores ficam no eixo): no W 250
  × 32,7 com N = 300 kN, cerca de 67 kN·m; acima disso, "Equilíbrio possível" reprova.

## Flexão oblíqua (momento nos dois eixos, 31/10/2026)

Com M_Sd,y ≠ 0 (`flexao_obliqua`, com cache: o equilíbrio não depende da espessura), qualquer
disposição vai pelo método geral em duas direções. M comprime x > 0 e M_y comprime y > 0; a zona
comprimida é a parte da placa com n·p ≥ s, n = (cos θ, sen θ):

* **Sem tração (C2):** a zona cujo centro cai na resultante (e_x = M/N, e_y = M_y/N), com
  σ_c,Sd = N/A_c ≤ σ_c,Rd. Com M_y = 0 é o C2 da norma (ℓ_c = ℓx − 2e).
* **Com tração (C3, T3):** σ_c,Rd na zona e F_i = k·(s − n·p_i) nos chumbadores do outro lado da
  linha neutra (placa rígida); para cada θ, s e k fecham N e o momento na direção n (o menor s,
  como na 6.7); θ fecha o momento ao longo da linha. Com M_y → 0 volta ao método de uma direção.
* **Sem contato (T2):** F_i = |N|/n − M·x_i/Σx² − M_y·y_i/Σy², enquanto todos F_i ≥ 0.
* **Espessura:** compressão com ℓ_max = máx(m; n; λ·n₀) (C) ou máx(m; n) (T) e, como na 6.7, p =
  √(ℓ_c(2m − ℓ_c)) no lugar de m quando ℓ_c < m, com ℓ_c a maior profundidade da zona em ℓx (o
  balanço n fica inteiro); tração pelas contas acima, com a linha toda na força do chumbador mais carregado dela
  (n·F_máx; numa só direção as forças da linha são iguais e nada muda).
* **Atrito:** μ·σ_c·A_c/γ_a2. Ancoragem na ACI com as forças de cada chumbador (ψ_ec nos dois
  eixos).

Os testes conferem o equilíbrio de N, M e M_y em todas as disposições (inclusive só M_y logo acima
do C2, com a raiz na ponta da busca, θ = 90°) e a continuidade com M_y → 0.

## Ancoragem no concreto (ACI 318-19, Capítulo 17)

Sempre nos tipos que a Tabela 18 não cobre (guarda-chuva, químico, parabolt) e, no reto com porca,
quando a opção está ligada (`verificar_ancoragem`). φ da condição B (sem armadura suplementar): 0,70
nos concretados e 0,65 nos pós-instalados; concreto fissurado (ψ_c = 1,0).

* **Arrancamento de um chumbador:** cabeça, φ·8·A_brg·f_c (17.6.3.2.2 a), A_brg da porca sextavada
  pesada (s = 1,5·d + 3,2 mm) ou da chapa na ponta, menos a haste; gancho, φ·0,9·f_c·e_h·d_b
  (17.6.3.2.2 b), com 3·d_b ≤ e_h ≤ 4,5·d_b; pós-instalado, o N_Rd do fabricante (sem ele, ALERTA).
* **Cone do grupo tracionado (17.6.2):** A_Nc/A_Nco com o bloco (ou o bloco mínimo da nota e da
  Tabela 18, placa centrada), h_ef reduzido pela 17.6.2.1.2 perto de três ou mais bordas, ψ_ed,N, ψ_ec,N pela
  excentricidade das forças; N_b = 10 (concretado) ou 7 (pós-instalado)·√f_c·h_ef^1,5, ou
  3,9·√f_c·h_ef^(5/3) no chumbador com cabeça de 280 a 635 mm. Com **armadura de ancoragem** no bloco
  (17.5.2.1), o cone sai como informação e a armadura fica com o projeto do bloco.
* **Arrancamento lateral (17.6.4):** chumbador com cabeça a menos de 0,4·h_ef da borda; grupo ao longo
  da borda com (1 + s/(6·c_a1)) e o fator de c_a2.
* Aço fora do A36 ou 2 chumbadores (rotulada) sem essa verificação: ALERTA (a Tabela 18 vale para
  o A36, de 4 a 8 chumbadores — nota a).

## Exemplo (do guia)

W 250 × 32,7, tipo 1, 4 chumbadores Ø 1", placa de 25 mm ASTM A36, f_ck = 25 MPa, A₂/A₁ = 1,
N_Sd = 300 kN, V_Sd = 20 kN: caso C1, placa 458 × 200 mm, σ_c,Rd = 0,85 × 25/1,4 = 15,18 MPa,
σ_c,Sd = 3,28 MPa, t_p,min = 18,1 mm (72 %), V_Rd = 100 kN. Com 6 chumbadores, M_Sd = 150 kN·m e
placa de 40 mm o caso passa a C3: ℓ_c = 130,5 mm, F_t = 98,1 kN por chumbador, d_b,min = 23,7 mm e
t_p,min = 38,9 mm (97 %). Os testes
(`tests/test_base_de_pilar.py`) conferem essas contas e o equilíbrio de forças e momentos entre o
concreto e os chumbadores em C3, T1, T2 e T3.

## Texto da norma conferido (31/10/2026)

Vistos no texto da NBR 8800:2025 e aplicados (nada mais sai "a confirmar" nesta página):

* **6.6.5 Apoios de concreto:** σ_c,Rd = 0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c. A 2008 dava
  f_ck/(γ_c·γ_n)·√(A₂/A₁) ≤ f_ck, γ_n = 1,4: com A₂/A₁ = 1 a 2025 admite 19 % a mais e o teto passa
  de f_ck a 1,21·f_ck. A placa fica mais grossa onde a pressão governa (t_p,min1 ∝ √σ_c,Rd) e o
  chumbador menos tracionado em C3 (ℓ_c menor). A Figura 20 (A₂ com o bloco não homotético) não foi
  vista.
* **6.3.3.2 Cisalhamento:** 0,45·A_b·f_ub/γ_a2 com a rosca no plano de corte (e parafuso comum),
  0,56 sem; atender também a 6.3.3.3. Vale também na placa de base do Design Guide 1
  (`core/base_plate.py`, Estruturas de aço e Esforços do modelo), que usava a 6.6.5 e os 0,40 da 2008.
* **Tabela 18:** os valores batem com os do programa; as notas a–i estão acima.
* **12.3.3.1 (tolerâncias de montagem):** pilar aprumado com desvio até 1:500. É a tolerância de
  execução, não a imperfeição da análise; a flambagem continua com o desaprumo h/333 (0,3 %) da
  análise (4.9.7.1.1 da 2008), maior que ela.
