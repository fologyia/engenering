# Flambagem de colunas — escopo, hipóteses e conferências

A página **Flambagem de colunas** verifica a barra inteira numa rodada: dois eixos, todos os modos
de flambagem elástica, flambagem local, flexão em x e em y e a interação N + Mx + My, pela
ABNT NBR 8800:2008, pelo Projeto NBR 8800:2024 ou pelo AISC 360-16, com o critério da Anglo
(AA-BR-DPST-DR-0001). Este documento registra o que o módulo faz, o que ele recusa fazer e como
cada decisão foi conferida.

## Onde está cada coisa

| Camada | Arquivo | O que tem |
| --- | --- | --- |
| Fórmulas | `core/column_design.py` | Porte do módulo de referência: seções, `N_e` de todos os modos, `χ`, `Q` e `A_ef`, `M_Rd` (FLT, FLM, FLA), `C_b`, `C_m`, `B₁`, interação e critério Anglo. Funções puras, em mm, MPa, kN e kN·m. |
| Orquestração | `core/column_buckling.py` | `EntradaColuna` → `verificar_coluna` → `ResultadoColuna`: encadeia as fórmulas, monta a tabela de verificações, bloqueia o que a norma não cobre e gera o registro técnico. Também guarda as tabelas de K, a mão-francesa e a combinação de ações. |
| Tabela comum | `core/verificacao.py` | `Verificacao` e a tabela de oito colunas, a mesma de Projeto de parafusos. |
| Interface | `components/column_ui.py`, `components/column_help.py`, `components/verification_table.py`, `app_pages/flambagem_colunas.py` | Só desenha; todo cálculo vem do núcleo. Cada campo tem um “?” em `AJUDA`. |

## O que a verificação não faz em silêncio

Nenhuma entrada é “consertada”. Os casos abaixo viram linha **NÃO OK** (bloqueio) e impedem o
resultado que dependeria deles:

- tubo circular com `D/t > 0,45·E/f_y` (a norma não cobre);
- alma esbelta na flexão (`h/t_w > 5,70·√(E/f_y)`: viga de alma esbelta, Anexo H da NBR 2008) e
  tubo não compacto na flexão — o usuário pode informar `M_Rd` calculado por fora, e a tabela
  registra que o valor veio dele;
- `N_Sd,1 ≥ N_e` no `B₁` (a barra é instável no plano de flexão);
- seção sem módulo plástico `Z`, ou sem rotina de `M_Rd`, com momento aplicado.

Ficam em **ALERTA**, nunca em OK:

- seção genérica (inclui “área e raio de giração”) sem as paredes `b/t` ou sem a confirmação de
  que a seção é compacta e a torção não governa;
- perfil formado a frio do catálogo (NBR 14762 é que vale);
- cisalhamento (5.4.3) quando há mão-francesa ou força transversal — a verificação do cortante
  está fora do escopo e o programa só avisa.

## Diferenças deliberadas em relação a `core/nbr8800.py`

O módulo de barras de Estruturas de aço e este concordam, para compressão, em todo o catálogo
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

Cantoneira simples (NBR 5.3.5.4), barras compostas (NBR 5.3.6), cisalhamento (5.4.3), efeitos
globais de segunda ordem (`B₂`), deslocabilidade do pórtico e cargas nocionais — que pertencem à
análise da estrutura, em Estruturas de aço —, fadiga, cargas dinâmicas e perfis formados a frio.
