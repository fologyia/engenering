# Vigas de piso — a viga que apoia a grade da plataforma

A página **Vigas de piso** (`app_pages/viga_de_piso.py`, núcleo em `core/viga_de_piso.py`, desenho em
`components/figuras_estrutura.py::svg_viga_de_piso`) verifica uma viga **biapoiada** de piso pela
NBR 8800 e, quando ligado, pelo critério Anglo American AA-BR-DPST-DR-0001 Rev. 1.

## Entradas

| Campo | Uso |
| --- | --- |
| Perfil, aço | Catálogo do programa (famílias W, U, I e HP); f_y da tabela de aços (A36, A572 Gr 50, A588). |
| Tipo | Principal (recebe vigas ou apoia nos pilares) ou secundária (só a grade): muda o limite de flecha Anglo. |
| Vão, largura de influência | A faixa de piso que a viga carrega (em geral a distância entre vigas vizinhas). |
| Mesa travada | Com a grade travando a mesa comprimida, L_b = espaçamento dos pontos travados e C_b = 1; sem travamento, L_b = vão e C_b do diagrama de momentos (5.4.2.3, R_m = 1). |
| Cargas | Piso e acessórios (kN/m²), sobrecarga (kN/m², da base técnica), carga linear permanente (kN/m) e equipamento no meio do vão (kN). O peso próprio do perfil entra sozinho. |
| Norma | Projeto NBR 8800:2024 (padrão), NBR 8800:2008 ou AISC 360-16 (motor da Flambagem de colunas). |

## Cálculo (`calcular`)

* **Combinações ELU** pelas Tabelas 1 e 2 da NBR 8800 (`core/load_combinations`): peso próprio de
  estrutura metálica, elementos construtivos industrializados (grade), sobrecarga de equipamentos e
  peso de equipamentos; a combinação que dá o maior momento e a que dá o maior cortante.
* **Flexão**: M_Sd = q·L²/8 + P·L/4 contra M_Rd do motor da Flambagem de colunas (FLT com o C_b,
  FLM, FLA e o limite 1,5·W·f_y), com N ≈ 0.
* **Cortante** (5.4.3, alma sem enrijecedores, k_v = 5): V_pl = 0,6·d·t_w·f_y, com λ_p = 1,10·√(k_v·E/f_y)
  e λ_r = 1,37·√(k_v·E/f_y).
* **Flecha** com todas as cargas características (combinação rara): 5qL⁴/(384EI) + PL³/(48EI) contra
  L/350 (NBR 8800, Anexo C, vigas de piso) e, com o critério Anglo, L/350 nas principais e L/300 nas
  secundárias (Tabela 3).
* **Critério Anglo**: espessura mínima de 4,8 mm de perfis laminados (8.8); a **ligação** precisa
  resistir ao menos a 75 % da carga uniforme que a viga suporta (9.1): R_mín = máx(0,75·W_Rd/2; R_d),
  com W_Rd = 8·M_Rd/L.
* **Frequência natural** (informativa): f ≈ 18/√δ (δ em mm, cargas permanentes), para comparar com a
  dos equipamentos apoiados (critério Anglo 5.7).
* **Perfil mais leve** (`perfil_mais_leve`): percorre a mesma família em ordem de massa e devolve o
  primeiro que atende; o botão **Adotar** troca o perfil da página.

## Exemplo (do guia)

W 200 × 15,0, ASTM A572 Gr 50, viga principal de 4,0 m, faixa de 1,0 m, piso 0,45 kN/m² e
sobrecarga 5,0 kN/m², mesa sem travamento: M_Sd = 16,6 kN·m e M_Rd = 17,2 kN·m (96 %), V_Rd =
161,8 kN, flecha de 7,1 mm (L/560). Com o critério Anglo, a alma de 4,3 mm fica abaixo dos 4,8 mm do
item 8.8 e o mais leve que atende passa a ser o W 250 × 17,9.

## Registro

`registro_viga` grava a verificação no projeto (módulo `viga_de_piso`): o memorial ganha o capítulo
com o resultado, o que passou e o que não passou, e as entradas com rótulo próprio
(`ENTRADAS_CURADAS["viga_de_piso"]`).

## Testes

`tests/test_viga_de_piso.py` (conta à mão do exemplo, C_b, travamento, critério Anglo, carga
concentrada, perfil mais leve, validação, registro e memorial) e `tests/test_viga_de_piso_pagina.py`
(ajuda de todos os campos, adotar o perfil, registro e o capítulo do guia).
