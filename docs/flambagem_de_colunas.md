# Flambagem de colunas — escopo, hipóteses e conferências

A página **Flambagem de colunas** verifica a barra inteira numa rodada: dois eixos, todos os modos
de flambagem elástica, flambagem local, flexão em x e em y e a interação N + Mx + My, pela
ABNT NBR 8800:2008, pela NBR 8800:2025 ou pelo AISC 360-16, com o critério da Anglo
(AA-BR-DPST-DR-0001). Este documento registra o que o módulo faz, o que ele recusa fazer e como
cada decisão foi conferida.

## Onde está cada coisa

| Camada | Arquivo | O que tem |
| --- | --- | --- |
| Fórmulas | `core/column_design.py` | Porte do módulo de referência: seções, `N_e` de todos os modos, `χ`, `Q` e `A_ef`, `M_Rd` (FLT, FLM, FLA), `C_b`, `C_m`, `B₁`, interação e critério Anglo. Funções puras, em mm, MPa, kN e kN·m. |
| Orquestração | `core/column_buckling.py` | `EntradaColuna` → `verificar_coluna` → `ResultadoColuna`: encadeia as fórmulas, monta a tabela de verificações, bloqueia o que a norma não cobre e gera o registro técnico. Também guarda as tabelas de K, a mão-francesa e a combinação de ações. |
| Tabela comum | `core/verificacao.py` | `Verificacao` e a tabela de oito colunas, a mesma de Projeto de parafusos. |
| Interface | `components/column_ui.py`, `components/column_help.py`, `components/verification_table.py`, `app_pages/flambagem_colunas.py` | Só desenha; todo cálculo vem do núcleo. Cada campo tem um “?” em `AJUDA`. |
| Desenhos | `core/desenho_da_secao.py`, `core/desenho_da_coluna.py` (com `core/desenho_girado.py`) | Atrás do botão **Ver os desenhos** (`col_ver_desenhos`, depois da mão-francesa) e sempre no Word. **Coluna em pé** (`figura_da_coluna`): vista frontal (plano x–z: apoio, K_y, travamentos a cada L_y) e lateral (plano y–z: apoio, K_x, travamentos a cada L_x), com as arestas do perfil vistas ou escondidas (olhando de y e de x negativos, sem espelhar), a planta da seção e a seta de onde se olha em cima de cada vista, e a mão-francesa (F, θ, nó a "a" da base) na vista do plano em que age; a largura do perfil é aumentada quando ficaria fina demais. **Seção**: a forma em corte (hachurada) a partir de `Secao.tipo`/`dims` — ou do catálogo pelo nome, no T e no C enrijecido —, os eixos x e y por G, o centro de cisalhamento quando sai de G (U, C, T), a elipse de giração (r_y ao longo de x, r_x ao longo de y) e as cotas. **Girar o desenho da seção** (`col_giro`, −180° a 180°, positivo anti-horário) gira só o desenho, com o texto de pé; o Word sai com o mesmo giro. Laminados sem os raios de concordância; seção dada só pelas propriedades aparece sem a forma. |

## Barras compostas

Tipo de seção **Perfil composto** (`core/perfis_compostos.py`, `Secao.tipo = "composta"`): dois
perfis iguais, em contato ou com o afastamento `s` de uma chapa espaçadora. O eixo y passa sempre
entre os perfis, e a flexão em torno de y é a única que carrega as ligações.

| Arranjo | `K_i` | Seção |
| --- | --- | --- |
| 2 cantoneiras em T (abas iguais ou desiguais) | 0,50 | Monossimétrica, y de simetria; `C_w = 0`, `y₀ = ȳ − t/2` |
| 2 cantoneiras em cruz | 0,86 | Simétrica em relação a G; x é o eixo principal mais próximo da reta entre os centros das cantoneiras |
| 2 U costas com costas (forma de I) | 0,75 | Dupla simetria |
| 2 U com as mesas de frente (caixa, ligada a intervalos) | 0,86 | Dupla simetria |

`ℓ = L/(n + 1)`, com `n` espaçadores entre as pontas e `r_mín` o menor raio de giração de um perfil
(na cantoneira, o do eixo inclinado).

| | NBR 8800:2008 | NBR 8800:2025 | AISC 360-16 |
| --- | --- | --- | --- |
| Limite de `ℓ/r_mín` | 1/2 de `(KL/r)` máx. (5.3.4.2) | 3/4 de `(L/r)₀` máx. (5.3.6.1) | 3/4 (E6.2) |
| Espaçadores | pelo menos 2 | pelo menos 2 | pelo menos 2 |
| Pontas soldadas ou protendidas | não pede | exige (5.3.6.2) | exige (E6.1) |
| Redução de `N_ey` | não tem | `N_e,m` (5.3.6.3) | `(L_c/r)_m` (E6.1), a mesma conta |

Redução (`cd.resist_compressao(..., fator_Ney=...)`): com aperto normal,
`N_e,m = N_e,o·(L/r)₀²/[(L/r)₀² + (ℓ/r_mín)²]`; com solda ou protensão, `N_e,m = N_e,o` até
`ℓ/r_mín = 40` e, acima, com `K_i·ℓ/r_mín`. `(L/r)₀` é a esbeltez do conjunto em y. O `N_ey` reduzido
entra na flexo-torção das cantoneiras em T (5.3.5.2): o AISC 360-16 faz o mesmo, com `F_e` elástico
(E4-3) levado à curva de `χ`. A esbeltez de 200 continua sendo a do conjunto (5.3.7.1).

**Conferido em:** texto da NBR 8800:2008 (5.3.4.2) e Projeto de revisão de maio de 2024 (5.3.6, Tabela
4). O texto publicado da 2025 não estava disponível para o item 5.3.6. O caso de aceite é o exemplo
E.5 do AISC (Design Examples): 2L4×3½×3/8 LLBB, s = 3/4 pol., L = 8 pés, A36: `φP_n ≈ 127 kips`,
2 ligações, `a = 32 pol.`; as propriedades batem com a tabela com menos de 0,5 % de diferença e o
programa dá 126,9 kips.

**Simplificações, a favor da segurança:** cantoneira sem raios; torção com cada perfil sozinho (`J`
e `C_w` somados); abas como elementos livres (grupo 3 da Tabela 4, "providas de chapas espaçadoras").
**De fora:** `M_Rd` (com momento, o usuário informa), o dimensionamento dos espaçadores (a norma não
fixa a força neles), perfis diferentes, mais de dois perfis e treliçados (5.3.6.4).

## O que a verificação não faz em silêncio

Nenhuma entrada é “consertada”. Os casos abaixo viram linha **NÃO OK** (bloqueio) e impedem o
resultado que dependeria deles:

- tubo circular com `D/t > 0,45·E/f_y` (a norma não cobre);
- alma esbelta na flexão (`h/t_w > 5,70·√(E/f_y)`: viga de alma esbelta, Anexo H da NBR 2008) e
  tubo não compacto na flexão — o usuário pode informar `M_Rd` calculado por fora, e a tabela
  registra que o valor veio dele;
- `N_Sd,1 ≥ N_e` no `B₁` (a barra é instável no plano de flexão);
- barra composta com `ℓ/r_mín` acima do limite, menos de dois espaçadores ou, na 2025 e no AISC,
  pontas com parafusos de aperto normal;
- seção sem módulo plástico `Z`, ou sem rotina de `M_Rd`, com momento aplicado.

Ficam em **ALERTA**, nunca em OK:

- seção genérica (inclui “área e raio de giração”) sem as paredes `b/t` ou sem a confirmação de
  que a seção é compacta e a torção não governa;
- perfil formado a frio do catálogo (NBR 14762 é que vale);
- cisalhamento (5.4.3) quando há mão-francesa ou força transversal — a verificação do cortante
  está fora do escopo e o programa só avisa.

## Diferenças deliberadas em relação a `core/nbr8800.py`

O módulo de barras de Barras, treliças e pórticos e este concordam, para compressão, em todo o catálogo
(I, W, HP, U, T, barras e tubos circulares), com diferença relativa menor que 1e-9 — o teste
`tests/test_column_buckling.py::TestConcordaComNbr8800` cobre dois valores de f_y, três conjuntos de
comprimentos e perfil soldado e laminado. As diferenças que sobram são intencionais:

| Caso | `core/nbr8800.py` | Este módulo | Por quê |
| --- | --- | --- | --- |
| Tubo retangular | largura plana = lado − 2t | lado − 3t | AISC B4.1b, com cantos vivos; em `Q`, a diferença é da ordem de 1% nos casos conferidos. |
| Flexão em y da mesa | limita `M_pl` a `1,5·W·f_y` antes de interpolar | limita só o resultado final | 5.4.2.2; o resultado novo é igual ou até 4% maior nos perfis conferidos. |
| Perfil U em y | `W = I_y/(b_f/2)` | `W = I_y/(distância à ponta da mesa)` | O módulo antigo superestimava o `W` do U. |
| Larguras efetivas de colunas muito esbeltas | `b_ef` zerava e `Q` caía a 0,5 | limiar em `σ = χ·f_y` | Corrigido nos dois módulos (`fator_q`). |

## Simplificações conservadoras

- O limite `M_Rd ≤ 1,5·W·f_y` (NBR 5.4.2.2) é aplicado às três normas, como no módulo de referência. O AISC 360-16 não o tem na F2 (usa `1,6·S·F_y` só em F6 e F11): na verificação AISC de uma seção com `Z/W` acima de 1,5 (flexão em y de perfis I) o resultado sai menor que o da norma americana.
- Sem `M₁/M₂` informado, `C_m = 1,0`; sem `C_b` informado, `C_b = 1,0`.
- `verificar_barra` (`core/column_design.py`) é o caminho do módulo de referência, mantido para os testes de aceite; o app usa `verificar_coluna` (`core/column_buckling.py`), cujo `L_b` padrão é `L_y`.

## Casos de aceite

Reproduzidos pela tela (`tests/test_flambagem_pagina.py`) e pelas funções
(`tests/test_column_buckling.py`):

| Caso | Resultado |
| --- | --- |
| Barra circular Ø50, L = 2000, K = 1, f_y = 250, `N_Sd = 1,4·30 + 1,5·20 = 72 kN`, NBR 2008 | `N_c,Rd = 120,71 kN`, 60%, `λ = 160`, OK |
| HSS8×8×1/2, `A = 13,5 in²`, `r = 3,04 in`, L = 24 ft, `F_y = 46 ksi`, AISC (Design Guide 29) | `φP_n ≈ 1 361 kN` (306 kips) |
| U 152,4×48,8×8,71×5,08, A36, `K_xL_x = 3000`, `K_yL_y = 1500`, `K_zL_z = 3000`, NBR 2008 | `N_ey = 308,4 kN` governa; flexo-torção xz = 457,4 kN; `N_c,Rd = 207,3 kN` |
| `N/N_Rd = 0,30`, `M_x/M_x,Rd = 0,50`, `M_y/M_y,Rd = 0,40` | interação 1,10, **NÃO OK** (eixo a eixo daria 0,744 e 0,656) |
| `λ = 201` | **NÃO OK** (Anglo 8.3) |
| U laminado com `t = 4,5 mm` | **NÃO OK** (Anglo 8.8) |

## Valores a conferir na norma

O módulo de referência trouxe de memória os itens abaixo da NBR 8800:2008, porque a norma vigente
não estava disponível. Estão marcados “CONFERIR” na página e no registro, e **precisam ser
conferidos na norma antes de emitir documentos**:

- `Q_s` e `Q_a` do Anexo F;
- Tabela E.1 de K;
- `λ_p` dos tubos na flexão;
- a forma da FLT de 2008, com `C_b` multiplicando a interpolação.

## Fora do escopo

Cantoneira simples (NBR 5.3.5.4), barras compostas (NBR 5.3.6), cisalhamento (5.4.3), o `B₂` de
um andar com várias colunas (ΣN_Sd, ΣH_Sd e Δh, Anexo D) — que pertence à análise da estrutura,
em Barras, treliças e pórticos —, fadiga, cargas dinâmicas e perfis formados a frio.

## Coluna deslocável (31/10/2026)

No plano em que uma ponta se desloca de lado — em balanço, ou com translação (Tabela E.1, casos
d a f), ou com K informado maior que 1 — o `B₁` (K = 1) não pega o efeito P-Δ. Nesse plano o
programa:

- soma o **desaprumo**: força nocional `H_n` de 0,3 % de `N_Sd` no topo (h/333, NBR 8800:2008
  4.9.7.1.1; 0,2 % no AISC 360-16, C2.2b), com `M_imp = H_n·K·L/2` (balanço: `H_n·L`;
  biengastada com translação: `H_n·L/2`). A 12.3.3.1.1 da 2025 (pilar aprumado até 1:500) é a
  tolerância de montagem, não esta imperfeição da análise, e é menor que ela;
- amplia pelo **B₂ da coluna isolada**, `B₂ = 1/(1 − N_Sd/N_e2)`, `N_e2 = π²·E·I/(K·L)²` — o
  equivalente, para uma coluna só, ao `Δh/h·ΣN/ΣH` da D.2.3 (em balanço com `R_s` = 0,85 dá
  `N·L²/(2,55·E·I)`; o K de 2,0 a 2,1 dá de 2,47 a 2,24 no lugar de 2,55, a favor da segurança);
- usa `M_Sd = máx(B₁; B₂)·(M₁ + M_imp)`, porque não sabe que parte de `M₁` vem do deslocamento
  lateral (com `K ≥ 1`, `B₂ ≥ B₁`);
- classifica pelo `B₂` com `E·I`: até 1,1 pequena; até 1,4 média, e então `B₁` e `B₂` com
  `0,8·E·I` (4.9.7.1.2); acima, grande deslocabilidade — ALERTA pedindo análise rigorosa
  (4.9.7.2); `N_Sd ≥ N_e2` bloqueia.

Se os momentos já vêm de uma análise de 2ª ordem com as imperfeições, a opção “já são de 2ª
ordem” deixa só o `B₁`. O vínculo da mão-francesa segue o apoio do eixo que ela flete
(`vinculo_do_apoio`); com “Informar K” ele é escolhido.

## Travamentos informados (09/11/2026)

O botão **Informar onde a coluna é travada** (`col_trav_ativar`, item 3) troca L_x e L_y por uma
tabela: a altura de cada travamento a partir da base, se ele trava L_x (a coluna não anda em y ali),
se trava L_y (não anda em x) e o que trava. As linhas ficam em `col_trav_linhas`; a tabela na tela
tem a chave `col_trav_tabela_<revisão>` e é refeita a cada edição (`com_edicoes`). O núcleo está
em `core/travamentos_da_coluna.py`, sem Streamlit:

- `organizar` tira o travamento numa ponta ou fora da coluna (as pontas são a condição de apoio) e
  o que não trava nenhum plano, com o aviso na tela; alturas a menos de 1 mm são o mesmo ponto.
- `trechos_do_eixo` dá a cada trecho o K da Tabela E.1 pelas pontas dele: a ponta da coluna com a
  condição escolhida e o travamento como pino (`PONTAS`; na (f), pino embaixo e o engaste que anda
  em cima, como na figura da tabela). Entre travamentos K = 1,0; da base engastada até o primeiro,
  0,7 ou 0,8. O pino no travamento despreza a continuidade, a favor da segurança (soltar um
  vínculo nunca aumenta a carga crítica; há teste com 75 sorteios contra a coluna contínua).
- Acima do último travamento de uma coluna em balanço, o trecho (pino e ponta livre) não fica de
  pé sozinho: `comprimento_de_flambagem` faz a flambagem elástica da coluna inteira, contínua
  (12 elementos de viga por trecho, autovalor por Cholesky; erro < 0,002 %), com os travamentos
  como apoios laterais rígidos. Com o K recomendado, o engaste da base vira uma mola
  k = u·tan u·E·I/L, u = π/2,1 (≈ 20·E·I/L), que dá K = 2,1 à coluna sem travamentos. O K desse
  trecho pode passar de 3 sem ser engano: `EntradaColuna.k_pela_coluna_continua` cala o aviso de
  digitação.
- Com “Informar K”, o mesmo K vale para todos os trechos.
- O trecho de maior K·L vai para `Lx_mm`/`kx` (e y). O maior trecho, sem o K, vai para o B₁
  (`Lx_B1_mm`/`Ly_B1_mm`, K = 1) e, em y, para o L_b da FLT quando o campo fica em 0.
- Mão-francesa: com travamentos no plano dela, `esforcos_mao_francesa(..., travamentos_mm,
  pontas)` tira o momento de H da coluna contínua com os travamentos como apoios
  (`momento_da_forca_horizontal`); sem travamentos, as fórmulas de antes (o teste confere que a
  coluna contínua as reproduz).
- Desenho: os travamentos nas alturas informadas, com a altura ao lado; registro, memorial e Word
  levam `travamentos`, `trechos_em_x`/`trechos_em_y` e o maior trecho do B₁.

O travamento é suposto rígido e resistente; o programa não o dimensiona (AISC 360-16, Appendix 6).

## Travamentos lidos do modelo: página Pilares do modelo (10/11/2026)

A tabela de travamentos desta página é para digitar à mão um pilar com travamento especial. Para
todos os pilares do modelo do SolidWorks de uma vez, a página **Pilares do modelo** (grupo Modelo
SolidWorks, `core/colunas_do_modelo.py`) lê os travamentos do esqueleto da macro:

- `ler_pilar`: cada barra que encosta no pilar (`core.travamentos.ligacoes`) entra na altura dela,
  medida da base. Ela trava L_x se chega na direção da alma (|cos| ≥ 0,5) e L_y se chega na da
  mesa. Barras a menos de 0,10 m uma da outra são o mesmo nó. A direção da alma vem da macro v5 ou
  mais nova; sem ela, `verificar_colunas` testa as duas posições e fica com a pior.
- Pontas: o pé no apoio do modelo é rotulado ou engastado, como o usuário escolhe (o arquivo não
  diz); o pé sobre outra barra é um nó (pino). O topo com barra encostada é um nó; sem nada, é
  livre, e o trecho de cima sai da coluna inteira. Um resto de até 0,40 m acima do último nó não é
  balanço. `tc.trechos_pelas_pontas` recebe a base e o topo direto; com a base rotulada e o topo
  livre sem travamento, a coluna não fica de pé e o pilar fica pendente, com o motivo.
- Os nós contam como travados de lado; o deslocamento da estrutura entra pelo B₂ do tipo Pilar
  (método da amplificação dos esforços). A verificação é a das barras do modelo
  (`verificacao_barras.verificar_com_comprimentos`) com o K·L do trecho que governa em cada eixo, o
  B₁ no maior trecho e o L_b entre os travamentos de L_y. Sem travamento no meio e com a base
  rotulada, o pilar sai igual à verificação de Esforços do modelo (há teste).

