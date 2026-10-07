# Vento nas estruturas — NBR 6123:2023: escopo, hipóteses e conferências

A página **Vento nas estruturas** calcula a ação do vento numa **edificação de planta retangular**
(galpão, edifício, plataforma fechada) pela **ABNT NBR 6123:2023**: da velocidade do local às
pressões em cada zona das paredes e do telhado, às pressões de projeto das telhas e fixações, à
força de arrasto, à torção e às **cargas por metro de um pórtico transversal**, com a solução do
pórtico. O núcleo não depende do Streamlit.

| Arquivo | O que faz |
| --- | --- |
| `core/vento_nbr6123.py` | `S₁`, `S₂`, `S₃`, `V_k` e `q` (seções 4 e 5, anexos A e B) |
| `core/vento_coeficientes.py` | `C_e` das Tabelas 6, 7 e 8, `c_pe` médio, `c_pi`, `C_a`, `f_v`, atrito, excentricidades |
| `core/vento_arrasto_dados.py` | `C_a` das Figuras 4 e 5, digitalizado dos gráficos (gerado) |
| `core/vento_edificio.py` | geometria, zonas, casos de vento, vedações, arrasto, verificações |
| `core/vento_portico.py` | cargas por metro do pórtico e solução pelo solver 2D |
| `core/vento_registro.py` | registro técnico e tabelas do memorial |
| `core/wind_load.py` | camada de compatibilidade (peça isolada: plataforma, barra, painel) |
| `components/wind_ui.py`, `wind_help.py`, `wind_figures.py` | interface, textos dos “?” e desenho da planta |
| `scripts/digitalizar_arrasto_nbr6123.py` | regenera `vento_arrasto_dados.py` a partir do PDF da norma |

## O que a edição de 2023 mudou, e o programa segue

* **`S₃` (Tabela 4)**: 1,11 · 1,06 · 1,00 · 0,95 · 0,83 para os grupos 1 a 5 (a edição de 1988 tinha
  1,10 · 1,00 · 0,95 · 0,88 · 0,83). Só no projeto das **vedações** a norma permite `0,92·S₃`
  (opção desligada por padrão).
* **`S₂`**: constante até **10 m na categoria V** (nas demais, o valor de 5 m vale abaixo de 5 m);
  vale até a altura da camada limite `z_g`. O Anexo A dá `S₂` para qualquer intervalo de tempo de
  3 s a 1 h, e a superfície frontal com mais de 80 m usa `t = 7,5·L_t / V_t(h)` (A.2), calculado por
  iteração.
* **`S₃` estatístico (Anexo B)**: `0,54·[−ln(1 − P_m)/m_a]^(−0,157)`, nunca abaixo do mínimo do grupo.
* **Fator de vizinhança `f_v`** (6.4) e **excentricidade da força de arrasto** de 7,5 % (15 % com
  vizinhança) do lado da planta (6.1.4).

## Convenções

* Eixos: **x** ao longo de `a` (maior lado, paralelo à cumeeira), **y** ao longo de `b`, **z** vertical.
  Vento a **0°** sopra para +x (contra a parede curta); a **90°**, para +y (contra a parede longa).
  Na cobertura de uma água o lado alto fica em y = 0 e há também o vento a **−90°** (contra a
  inclinação), como na figura da Tabela 8.
* Sinal: `C_e` e `c_pi` positivos são sobrepressão; negativos, sucção. A pressão líquida
  `Δp = q·(f_v·C_e − c_pi)` positiva empurra a superfície para dentro.
* A cumeeira é paralela ao lado maior (`a ≥ b`): é o único caso das Tabelas 6 a 8. Com `a < b` o
  cálculo recusa e explica.
* **Classe** (A, B ou C) pela maior dimensão da superfície frontal de **cada direção**: a 0° o vento
  bate na largura `b`; a 90°, no comprimento `a`. `S₂` é calculado no topo da edificação, como a
  norma recomenda; as vedações usam sempre a classe A.
* **Pressão interna** pelo método simplificado do item 6.3.2: quatro faces permeáveis (`−0,3` e `0`,
  os dois viram casos), duas faces opostas permeáveis (`+0,2` ou `−0,3` conforme o vento bata ou
  não nelas), estanque (`−0,2` e `0`) ou valores informados; o assistente de **abertura dominante**
  calcula o `c_pi` das tabelas do item 6.3.2.1-c.

## Resultados e como conferi-los

| Resultado | Origem | Conferência |
| --- | --- | --- |
| `S₂` | Tabelas 1 a 3 e Anexo A | a fórmula reproduz as 16 linhas da Tabela 3 até 250 m (3 classes × 5 categorias) e as da Tabela A.2 |
| `S₃` | Tabela 4 e Anexo B | Tabela B.1 inteira (6 vidas úteis × 6 probabilidades) |
| `C_e` por zona | Tabelas 6, 7 e 8 | transcritos das páginas da norma, linha a linha, com as notas de interpolação |
| resultante das zonas | `Σ −Δp·A·n` | a pressão interna não altera a resultante horizontal (teste); simetria; áreas cobrem a superfície |
| `C_a` | Figuras 4 e 5 | **lido do gráfico**, incerteza ±0,03; confere nos cruzamentos das isolinhas |
| pórtico | `Δp × espaçamento` | equilíbrio das reações com as cargas, sinal dos deslocamentos |

## O que não está aqui

* Telhados múltiplos, de calha central, curvos, abóbadas, cúpulas, coberturas isoladas, muros,
  reticulados, torres e cilindros (Tabelas 9 a 25, seções 7 e 8): a norma traz outras tabelas.
* Efeitos dinâmicos (seção 9) e desprendimento de vórtices (seção 10): o programa só **avisa** quando
  `T₁ > 1 s` (estimado por `0,29·√h − 0,4` se não informado) ou `h/b ≥ 6`.
* Pontes (seção 11). Topografia complexa e túnel de vento.
* O pórtico é plano e linear, só com o vento; as combinações com peso próprio e sobrecarga
  (NBR 8800/8681, γ_q = 1,4 e ψ₀ = 0,6) ficam em Casos e combinações de carga e em Estruturas de aço.

## `C_a` digitalizado

As Figuras 4 e 5 são imagens dentro do PDF. `scripts/digitalizar_arrasto_nbr6123.py` separa as
isolinhas (traço de pelo menos 3 pixels) das linhas finas da grade e dos algarismos, associa cada
isolinha ao seu nível pela ordem (a numeração impressa confirma), lê o valor nos cruzamentos da grade
do próprio gráfico por interpolação entre as duas isolinhas que enquadram o ponto e extrapola em
linha reta, no logaritmo da abscissa, os poucos cruzamentos de canto sem isolinha dos dois lados.
O resultado é uma tabela de `C_a` por `(h/ℓ₁, ℓ₁/ℓ₂)` (`core/vento_arrasto_dados.py`), interpolada
bilinearmente em escala logarítmica. Fora do gráfico (h/ℓ₁ < 0,5, por exemplo) vale o contorno e o
programa avisa.

## Memorial

O registro entra no memorial como as demais análises com tabela de verificações: **Resultado**
(com a pressão dinâmica de cada direção), dados de entrada, **O que passou** (aplicabilidade das
tabelas), **valores de apoio** (V_k, q, C_a, forças), as tabelas de pressões por zona, de vedações
e do pórtico e, no fim, **o que não passou** e o que conferir antes de emitir. As tabelas vêm de
`resultados["tabelas_memorial"]` (qualquer módulo pode usá-las) e o destaque, de
`resultados["destaque_memorial"]`.
