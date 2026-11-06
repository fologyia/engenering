# Elementos de máquinas no Assistente de cargas

O Assistente de cargas cobre 65 casos: 15 de estática e resistência, 34 de elementos de máquinas e
16 de seção e tensão no ponto. Este documento registra as equações, as fontes, as hipóteses e o que
**não** é feito nos elementos de máquinas. A estática está em `docs/estatica_e_resistencia.md`.

## Como funciona

Um caso é uma tabela de campos e uma função pura (`core/elementos_*.py`). A página não conhece
nenhum caso: monta o formulário pelos campos e mostra o resultado que a função devolve. O resultado
traz métricas, verificações, pontos de tensão, tabelas, gráficos, avisos, hipóteses, referências e
os envios para o próximo caso.

Para acrescentar um caso:

1. escreva a função `calcular_x(v) -> Resultado` e a tupla de `Campo` no módulo do assunto;
2. acrescente o `Caso` à tupla `CASOS` do módulo;
3. desenhe o croqui em `components/elementos_croquis.py`.

Os testes de `tests/test_elementos_catalogo.py` percorrem o catálogo: um caso novo já nasce testado
quanto à ajuda de cada campo, croqui, memorial, Word e fuzz.

Campo com limite que depende de outro campo (furo menor que o eixo) **não** usa `max_value`: esse
limite derruba a página quando o número digitado antes sai da nova faixa. A conferência fica no
cálculo, com `ValueError`, e vira uma mensagem no lugar do resultado.

## Encadeamento

Os resultados seguem de um caso para o outro, com os valores já preenchidos:

```text
Motor e redutor → Engrenagem, Correia, Chaveta, Flange
Engrenagem, cônica, correia, cabo → Eixo sobre dois mancais
Eixo sobre dois mancais → Seção de eixo (fadiga) e Rolamento (mancal A e B)
Chaveta, Ajuste prensado → Seção de eixo com o entalhe certo
Ações de içamento → Olhal, Gancho
Olhal, Cilindro hidráulico → Pino de articulação
Desbalanceamento → Base de máquina
```

## Transmissão de potência

- **Motor e redutor:** `T = 9550·P/n`, `T_s = T·Π(i·η)`. Tempo de partida `t = J·ω/(T_p − T_r)`, com
  a inércia da carga levada ao motor por `J/i²`.
- **Engrenagem cilíndrica:** forças `F_t = 2T/d`, `F_r = F_t·tan φ_n/cos ψ`, `F_a = F_t·tan ψ`.
  Flexão por Lewis, `σ = K_o·K_v·K_m·F_t/(b·m·Y)`, com o Y da Tabela 14-2 de Shigley no número virtual
  de dentes `z/cos³ψ`. Contato `σ_c = C_p·√[K·F_t/(b·cos φ)·(1/r₁ + 1/r₂)]`. Resistências de aço
  beneficiado: `S_t = 0,533·HB + 88,3` e `S_c = 2,22·HB + 200` no grau 1; `0,703·HB + 113` e
  `2,41·HB + 237` no grau 2 (Figuras 14-2 e 14-5).
  **É pré-dimensionamento.** O cálculo pela AGMA 2001 ou pela ISO 6336 não está aqui, e a NBR 8400
  6.7.5 deixa o método a critério do fabricante, que deve indicar a origem.
- **Cônica:** eixos a 90° e dente reto, com `F_t = 2T/d_m`, `F_r = F_t·tan φ·cos γ`,
  `F_a = F_t·tan φ·sen γ`. Só as forças.
- **Sem-fim:** `η = (cos φ_n − f·tan λ)/(cos φ_n + f·cot λ)`. Atrito pela eq. 15-38 de Shigley.
  Autotrava com `f ≥ cos φ_n·tan λ`, com aviso de que isso não dispensa freio em içamento.
- **Correia:** equação de Euler com `e^(μθ/sen(β/2))` em correia em V. Carga no eixo sem a parcela
  centrífuga, que a própria correia equilibra.
- **Corrente:** `d = p/sen(π/z)`, `V = z·p·n/60000`, número par de elos, efeito poligonal
  `1 − cos(π/z)`. Carga no eixo de `1,15·F_t`, prática de catálogo. A capacidade por desgaste vem do
  fabricante; aqui vai só a segurança à ruptura.
- **Flange:** corte, esmagamento e torque por atrito.

## Eixos e cubos

- **Seção de eixo:** K_t de ressalto por `A·(r/d)^b`, com os ajustes das curvas de Peterson dados por
  Norton e interpolação em D/d. Eles batem com a Tabela 7-1 de Shigley (ver os testes). K_t fixos:
  chaveta por fresa de topo 2,14 e 3,0; canal de anel 5,0 e 3,0 (com K_f = K_t); furo transversal
  pequeno 3,0 e 4,0 (limite teórico); cubo prensado 2,0 e 1,7 (estimativa, para informar se houver
  dado melhor). Sensibilidade de Neuber pela eq. 6-35. Limite de fadiga pelos fatores de Marin de
  `core/fatigue.py`, modelo Shigley. Critérios DE-Goodman (decide), DE-Gerber, DE-ASME elíptico e
  DE-Soderberg (comparativos). Diâmetro mínimo por iteração, porque S_e depende do diâmetro.
- **Eixo sobre dois mancais:** diâmetro constante, dois planos, até quatro cargas. Força axial num
  raio vira binário no plano da força radial. Flecha por dupla integração de M/EI. Inclinação nos
  mancais contra a Tabela 7-2 de Shigley. Rotação crítica de Rayleigh com o peso do eixo em 400 pontos.
  Para um eixo uniforme ela fica a menos de 1 % da fórmula exata (ver os testes). Com ressaltos, a
  seção é verificada depois no caso anterior.
- **Chaveta:** seção pela DIN 6885-1. Corte `τ = F/(b·L)`, esmagamento `p = F/(t₁·L)` no eixo e
  `p = F/[(h − t₁)·L]` no cubo. Duas chavetas contam como 1,5.
- **Ajuste prensado:** `p = δ/{d·[(D² + d²)/(D² − d²)/E_c + ν_c/E_c + (d² + d_i²)/(d² − d_i²)/E_e −
  ν_e/E_e]}`. Interferência pelas Tabelas 1 e 2 da NBR 6158 (H7/p6, r6, s6, u6), ou informada, menos
  `0,8·(Rz_eixo + Rz_furo)`. Transmissão com a interferência mínima; tensões com a máxima.

## Mancais, pinos e contato

- **Rolamento:** `L₁₀h = (C/P)^p·10⁶/(60n)`, `p = 3` em esferas e `10/3` em rolos. X e Y do rolamento
  rígido pela Tabela 11-1 de Shigley. Fator a₁ da ISO 281:2007: só o valor de 99 % (0,25) foi
  confirmado em fonte aberta; os de 95 % a 98 % são os conhecidos da norma e devem ser conferidos.
  Regimes da NBR 8400: carga média `K·F_máx` (força do motor) e `(2F_máx + F_mín)/3` (reação da
  carga), com a vida pela classe de funcionamento.
- **Bucha:** `p`, `V` e `pV` contra os limites do material. Oscilação com `V = 2·θ·(d/2)·f`. Os
  limites padrão são típicos de bronze: troque pelos do fabricante.
- **Pino de articulação:** `M = F/8·(b + 4c + 2a)` (EN 1993-1-8, Tabela 3.10), corte máximo
  `4/3·F/(2A)` e interação de flexão com cortante.
- **Contato de Hertz:** esfera ou cilindro. Limite de início de escoamento `p₀ ≤ 1,79·S_y` (linha) e
  `1,61·S_y` (ponto), Johnson.

## Içamento (NBR 8400:1984)

Tabelas lidas no PDF da norma: 5 (ψ), 10 (M_x), 20 (classes), 21 a 23 (grupos), 24 (q), 25 (FS_r),
26 (δ), 27 (Q), 28 (H₁), 29 (H₂), 30 (P_lim), 31 (c₁) e 33 (c₂).

**Dois erros de impressão na norma:**

- Tabela 28, grupo 4m, polia com cabo não rotativo: a norma imprime **18**, no meio da sequência
  20 - 22,4 - 25 - **18** - 31,5. Adotado **28**, o valor coerente com a coluna.
- Exemplo do Anexo H: usa δ = 1,12 para o grupo 4m, mas a Tabela 26 dá 1,18. Vale a tabela.

Casos:

- **Ações de içamento:** `M_x·(S_G + ψ·S_L + S_H)`, caso I. Aviso de assentamento (5.5.2.1).
- **Cabo, tambor e polias:** `d_c = Q·√T` (T em daN), `D ≥ H₁·H₂·d_c`. Rendimento do moitão
  `(1 − η^n)/[n·(1 − η)]`. Cabo 6 x 19 usa a coluna do não rotativo (nota da Tabela 28). Cabo mais de
  25 % acima do mínimo dimensiona os enrolamentos por ele mesmo (nota de 6.7.3). Carga de ruptura
  `K·d²·R`, com K tirado do Anexo C da NBR 6327: 0,330 com alma de fibra e 0,356 com alma de aço.
- **Roda:** `F_r = (F_mín + 2F_máx)/3`, `F_r/(b·D) ≤ P_lim·c₁·c₂` e `≤ 1,4·P_lim` no caso III.
- **Peça de mecanismo:** `σ_a = σ_r/(q·FS_r)`, relações a a h de 6.6.1, caso III de levantamento
  como 1,6 vez o caso I, e `δ·σ_máx ≤ σ_af`.
- **Gancho:** Winkler-Bach, seções retangular, circular e trapezoidal (Tabela 3-4 de Shigley). O
  gancho de catálogo segue a norma do produto; este caso serve para peça especial.
- **Olhal:** AISC 360-16 D5 e J7: `b_e = 2t + 16 mm`, `R_n = F_u·2t·b_e`,
  `R_n = 0,6·F_u·2t(a + d/2)`, `R_n = 1,8·F_y·t·d`; `w ≥ 2b_e + d`, `a ≥ 1,33·b_e`. Base e solda à
  parte.

**Não está aqui:** a verificação de olhal pela **ASME BTH-1**, própria para içamento. As fontes
abertas confirmam a estrutura (divisor `1,20·N_d`, `N_d` = 2 e 3), mas não os coeficientes. Em peça de
içamento, coeficiente não vem de memória: entra quando houver o texto da norma. Por isso a AISC D5,
com um fator mínimo próprio para içamento, é o método aplicado. A **NBR 15516-2** (correntes de elos)
está digitalizada como imagem e também não foi usada.

## Molas, freios e fusos

- **Mola de compressão:** Tabelas 10-1, 10-4, 10-5 e 10-6 de Shigley. `S_ut = A/d^m`. Bloco, reserva
  de 15 %, `L₀ ≤ 2,63·D/α`, fadiga de Zimmerli com Goodman torsional e frequência própria.
- **Mola de tração:** eq. 10-34 a 10-41 de Shigley. Corpo com `K_B`, gancho nos pontos A (flexão) e
  B (torção), `N_a = N_b + G/E` e `L₀ = (2C − 1 + N_b)d`. Limites da Tabela 10-7: 45 %, 40 % e 75 % de
  `S_ut`; com tensão inicial acima da faixa, o corpo usa 40 %, como manda a nota da tabela. Fadiga de
  Zimmerli, com `S_e = S_se/0,577` na flexão.
- **Mola de torção:** `σ = K_i·32M/(π·d³)`, `k' = d⁴E/(10,8·D·N_a)` e `N_a = N_b + (ℓ₁+ℓ₂)/(3πD)`.
  `S_y` é a Tabela 10-6 dividida por 0,577. O diâmetro sob carga usa só o giro do corpo, eq. 10-53.
  Fadiga de Gerber a partir da Tabela 10-10, que só traz A228, A230 e A232: os outros fios ficam na
  coluna do A228.
- **Mola prato:** Almen e László, com `K₁`, `K₂` e `K₃`, sem apoios planos. Pilha em série e paralelo
  sem atrito. Conferido com o disco A 40 (40 × 20,4 × 2,25, h₀ = 0,9): 6,5 kN a 0,75·h₀. A DIN EN 16984
  não está na pasta de normas. Por isso o limite de `σ_OM` é um dado, as faixas de `D_e/D_i`, `D_e/t` e
  `h₀/t`, o curso de 0,75·h₀ e a pré-carga de 15 % vêm de catálogos de fabricantes, e a fadiga não é
  calculada: saem `σ_o` e `σ_u` para levar ao diagrama da norma.
- **Freio ou embreagem de disco:** desgaste uniforme (projeto) e pressão uniforme. Energia
  `½·J·ω²·T/T_líq` e aquecimento `E/(m·c)`.
- **Freio de cinta:** Euler, com o aviso de que a capacidade cai no giro contrário.
- **Fuso:** eq. 8-5 e 8-6 de Shigley, colar, flexão no primeiro filete (38 % da carga), corte nos
  filetes e flambagem por Johnson ou Euler. O autotravamento olha a rosca; se só o colar segura, o
  programa avisa.

## Máquinas e vibração

- **Desbalanceamento:** `e = G/ω`, `F = m·e·ω²`, ou massa excêntrica de peneira. Transmissibilidade
  com `r = f/f_n`. A faixa `0,7 ≤ r ≤ 1,4` reprova. Velocidade rms contra o limite da ISO 10816-3.
- **Base de máquina:** quatro pés nos cantos de um retângulo, com peso, força horizontal na altura h
  e torque de reação. Chumbador por von Mises.
- **Disco girante:** Shigley eq. 3-55. Sem furo a tensão é `ρω²(3+ν)/8·r_o²`, e um furo pequeno a dobra.

## Hidráulica e tampas

- **Cilindro:** forças, velocidades, Lamé na camisa com as três tensões, tampa plana e flambagem da
  haste, com aviso de multiplicação de pressão na câmara da haste.
- **Placas:** Roark, Tabelas 11.2 e 11.4, com aviso quando a flecha passa de t/2.

## Seção e tensão no ponto

Os 15 modelos antigos continuam com os mesmos nomes (o Assistente de projeto grava esses nomes) e as
mesmas contas de `core/load_to_stress.py` e `core/additional_load_models.py`, mais a torção de seção
retangular. O que mudou:

- a **varredura** avalia vários pontos da seção e aponta o crítico, em vez de pedir que o usuário
  adivinhe: cantos em flexão biaxial, junção mesa-alma em perfis, linha neutra em eixo com cortante;
- o **material** entra na própria página, com S_y, fator de segurança e K_t;
- no **cilindro de parede espessa** o von Mises usa as três tensões, e não duas.

## Limitações gerais

Os casos são de resistência dos materiais, com as hipóteses listadas em cada resultado. Não incluem
efeitos térmicos, fluência, corrosão, soldas além das citadas, nem análise dinâmica além da citada.
As propriedades do catálogo são de referência: confirme no certificado antes de emitir o memorial.
