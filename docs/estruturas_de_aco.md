# Estruturas de aço — escopo e hipóteses

Esta área organiza cinco ferramentas de pré-dimensionamento:

1. catálogo geométrico de perfis;
2. verificação de barras pela ABNT NBR 8800;
3. combinações de ações pela ABNT NBR 8681 / NBR 8800 e ações de plataforma
   (vento, guarda-corpo, impacto, acessos);
4. ligações parafusadas, chapas, soldas e placa de base com chumbadores;
5. análise elástica de treliças e pórticos 2D, com segunda ordem no pórtico.

O que cada módulo faz e o que deixa de fora está registrado abaixo — e cada
cálculo registrado no projeto leva as mesmas premissas e alertas para o
memorial.

## Catálogo de perfis

Os perfis W, HP, I, U e T vêm das tabelas de bitolas do fabricante (Gerdau),
conferidos por coerência interna (raio de giração contra `sqrt(I/A)`, módulo
elástico contra `I/(d/2)`); os demais (C enrijecido, tubos, barras) são
idealizações sem raios de concordância. Módulo plástico, constante de torção e
de empenamento das famílias U e T são estimados por geometria idealizada, e a
descrição do perfil diz isso. O centroide e o centro de cisalhamento dos
perfis monossimétricos são estimados pelas fórmulas de parede fina de
`core/steel_sections.py`.

As bitolas U 8" × 17,10 e 20,50 entram com área, `Ix` e `Iy` conferidos
contra a C8x11.5 / C8x13.75 do AISC; o `ry` impresso na tabela de origem era
erro de impressão e o programa o deriva de `Iy/A`.

Antes do projeto executivo, o perfil deve ser conferido na tabela vigente do
fabricante.

## Barras (NBR 8800:2008, `core/nbr8800.py`)

Entradas: perfil, `f_y`, `f_u`, `E`, `G`, esforços **de cálculo** `N_Sd`,
`M_x,Sd`, `M_y,Sd`, `V_Sd`, comprimento `L`, `K_x`, `K_y` (e `K_z`), `L_b`,
`C_b`, perfil soldado ou laminado, área líquida e `C_t`.

O módulo calcula:

- tração (5.2): escoamento da seção bruta com `γ_a1 = 1,10` e ruptura da
  seção líquida com `γ_a2 = 1,35`, esbeltez `λ ≤ 300`;
- compressão (5.3): `N_c,Rd = χ·Q·A_g·f_y/γ_a1`, com `N_e` da flambagem por
  flexão nos dois eixos, por torção e flexo-torção (Anexo E — U e T
  acoplados), `λ₀ = √(Q·A_g·f_y/N_e)` e a curva única de `χ`
  (`0,658^λ₀²` até 1,5; `0,877/λ₀²` acima), `Q = Q_s·Q_a` pelo Anexo F
  (elementos AL e AA, grupos 3 a 6, largura efetiva com `c_a = 0,34/0,38`,
  tubos F.4), esbeltez `λ ≤ 200`;
- flexão (Anexo G): momento resistente por FLT (`L_p`, `L_r`, `M_cr`, `C_b`),
  FLM e FLA nos regimes plástico, inelástico e elástico, para I/W/HP/U em x,
  eixo fraco (G.5), T e tubos (G.3 / G.4);
- cisalhamento (5.4.3): `k_v`, `λ_p`, `λ_r`, com ou sem enrijecedores;
- interação N–M (5.5.1.2) com as duas expressões (razão axial maior ou menor
  que 0,2);
- flecha de viga biapoiada ou em balanço contra o limite de serviço
  (padrão L/350).

Cada estado-limite sai com memória de cálculo (esbeltezes, limites, momentos
de referência e regime), e o resultado aponta a verificação governante.

O que não está incluído: flambagem distorcional de perfis formados a frio
(NBR 14762), barras compostas, seções variáveis, vigas mistas, fadiga.

## Combinações (NBR 8681 / NBR 8800, `core/load_combinations.py`)

Cada ação recebe uma categoria das Tabelas 1 e 2 da NBR 8800 — peso próprio
metálico (1,25 / 1,0 favorável), pré-moldados (1,30), moldados no local e
elementos industrializados (1,35), com adições (1,40), equipamentos e
sobrecarga (1,50, com `ψ` por tipo de uso), guarda-corpo, vento (1,40; `ψ`
0,6 / 0,3 / 0), temperatura (1,20), truncada (1,20) — ou a categoria
personalizada com `γ` e `ψ` próprios. O gerador cria:

- ELU normais, alternando a ação variável principal, inclusive a combinação
  com as permanentes favoráveis (`γ_g = 1,0`), que governa vento de sucção e
  tombamento;
- ELS rara, frequente e quase permanente.

O envelope de cada esforço pode vir de combinações diferentes; a página e o
registro avisam para não tratar máximos independentes como simultâneos.

### Ações de plataforma

Abaixo da tabela de ações ficam três calculadoras com registro próprio:

- **vento (NBR 6123, `core/wind_load.py`)**: `V_k = V₀·S₁·S₂·S₃` e
  `q = 0,613·V_k²`, com `S₁` por relevo (plano, vale, topo de talude ou morro
  pela fórmula de 5.2), `S₂ = b·F_r·(z/10)^p` da Tabela 1 (categorias I a V,
  classes A a C, `z` entre 5 m e a altura gradiente), `S₃` por grupo da
  Tabela 3, e força `F = C_f·q·A_e` ou carga por metro `w = C_f·q·d` com um
  `C_f` de referência das tabelas de barras prismáticas e treliças. Os
  parâmetros tabelados são os da NBR 6123:1988; `V₀` e `S₃` devem ser
  conferidos na edição adotada;
- **guarda-corpo e impacto (`core/platform_loads.py`)**: carga horizontal
  uniforme no topo (1,0 kN/m em uso comum, 2,0 kN/m com concentração de
  pessoas — NBR 6120:2019 / NBR 14718) e concentrada de 1,0 kN, esforços no
  montante em balanço (`H = q·s`, `M = q·s·h`) e acréscimo dinâmico de
  equipamentos (ASCE 7-22, 4.6.2) na falta de valor do cliente;
- **acessos (NR-12)**: altura do guarda-corpo (mínimo 1,10 m ou o do
  cliente), rodapé ≥ 0,20 m, vão entre travessas ≤ 0,40 m, largura útil
  ≥ 0,60 m, degraus pela fórmula de Blondel (630 ≤ 2h + b ≤ 640 mm),
  inclinação de 20° a 45° e patamar a cada 3,00 m — tabela de conformidade
  com fonte por item.

## Ligações

São verificadas:

- resistência de parafusos à tração e ao cisalhamento e interação;
- pressão de contato e rasgamento junto ao furo;
- deslizamento por atrito;
- ruptura da seção líquida e cisalhamento de bloco;
- solda de filete;
- **placa de base e chumbadores** (`core/base_plate.py`, AISC Design Guide 1,
  2ª ed.): pressão de contato `f_p,max = φ_c·0,85·f_ck·√(A₂/A₁)` com
  `√(A₂/A₁) ≤ 2`, placa em flexão plástica com cantiléveres `m`, `n` e `λn'`,
  casos de compressão centrada, momento pequeno (`Y = N − 2e`, `e ≤ e_crit`),
  momento grande (`Y` pela equação do 2º grau, `T = q_max·Y − P`, placa
  fletida pela tração dos chumbadores) e arrancamento; chumbadores por AISC
  J3 (`F_nt = 0,75·F_u`, `F_nv = 0,45·F_u`, interação J3.7). Os exemplos 4.1,
  4.4 e 4.5 do guia são reproduzidos nos testes.

Não estão incluídos efeito alavanca, ligação semirrígida, distribuição não
linear, fadiga de solda, qualificação do procedimento de soldagem, ancoragem
no concreto (cone de arrancamento, fendilhamento — ACI 318 cap. 17 / NBR 6118)
e o dimensionamento do bloco ou sapata.

## Análise 2D (`core/structural_2d.py`)

O solver usa o método matricial da rigidez:

- treliça plana: dois graus de liberdade por nó, sempre em primeira ordem;
- pórtico plano: dois deslocamentos e uma rotação por nó, cargas nodais e
  carga distribuída uniforme no eixo local do elemento;
- deslocamentos, reações e esforços de elemento.

No pórtico, a estabilidade global segue a NBR 8800, 4.9:

- **segunda ordem** pela rigidez geométrica consistente de cada barra,
  montada com o esforço normal e iterada até convergir (P–Δ e P–δ dentro da
  discretização); os esforços de extremidade saem em equilíbrio na
  configuração deformada;
- **carga nocional** de 0,3 % da carga gravitacional de cada nó livre em x
  (imperfeições geométricas iniciais, 4.9.7.1.1), no sentido escolhido;
- **fator de carga crítica global** pelo autoproblema `K_e·φ = λ·(−K_g)·φ`;
  em segunda ordem, carga acima da crítica é recusada;
- **classificação da deslocabilidade** por `Δ₂/Δ₁` (4.9.4.1): pequena
  (≤ 1,1), média (≤ 1,4) ou grande, com aviso pedindo a **rigidez reduzida a
  80 %** (4.9.7.1.2) na média deslocabilidade;
- **coeficiente B₂** (4.9.4.6) com `R_s = 0,85`, para comparação com a
  amplificação exata;
- **deslocamento horizontal** contra `H/400` (Anexo C) ou outro divisor, com
  a altura de referência informada ou a altura total dos nós.

A treliça continua sendo de primeira ordem. Nenhum dos dois modelos inclui
plasticidade, cabos, apoios elásticos ou ligações semirrígidas, e a flambagem
de cada barra é verificada no módulo 2 com os esforços que saem daqui. Cada
combinação exige uma análise (ELU para esforços, ELS para `H/400`).

## Referências normativas

O escopo foi organizado em torno da ABNT NBR 8800 (as fórmulas implementadas
são as da edição de 2008, com a numeração dela), da ABNT NBR 8681, da ABNT
NBR 6120:2019, da ABNT NBR 6123, da ABNT NBR 14718, da NR-12 e do AISC Design
Guide 1. O programa não reproduz integralmente essas normas e não certifica
conformidade; a edição adotada e o critério do cliente prevalecem.
