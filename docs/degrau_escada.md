# Degrau de escada em grade — escopo, fórmulas e conferências

A página **Degrau de escada em grade** dimensiona o degrau de uma escada industrial em **grade de
piso eletrofundida** e escolhe o modelo do catálogo **Selmec "Degraus" (DS)**. Verifica a NR-12
(Anexo III), a NR-22, o Critério de Projeto Anglo American AA-BR-DPST-DR-0001 Rev.1 (22/12/2025), a
NBR 8800:2008, a NBR 6120 e a ISO 14122-3. A fonte dos valores e das fórmulas é a planilha validada
`Degrau_Escada_Grade_NR12_Anglo_Selmec.xlsx`; os casos de aceite dela estão em
`tests/test_degrau_escada.py`. O núcleo não depende do Streamlit.

| Arquivo | O que faz |
| --- | --- |
| `core/degrau_escada.py` | geometria, lances, catálogo, dimensionamento, seleção e as 38 verificações |
| `core/degrau_registro.py` | registro no projeto, tabelas do memorial, tabela de 7 colunas e CSV |
| `core/degrau_relatorio.py` | relatório em PDF (reportlab, A4 em paisagem) |
| `components/degrau_ui.py`, `degrau_help.py` | interface e textos dos "?" |
| `app_pages/degrau_escada.py` | a página |

## O que faz e o que não faz

**Faz:** define o nº de espelhos, o espelho `h` e o piso `b` pelo requisito legal, pelo Critério Anglo
e pelo limite do catálogo, nessa ordem de prioridade; calcula a profundidade `C`, a furação `F` e a
sobreposição `r`; divide a escada em lances; avalia os **64 modelos** e adota o mais leve que atende
ao cálculo e à largura recomendada pelo fabricante (ou o que o usuário escolher); dimensiona o
degrau (flexão com flambagem lateral por torção, cisalhamento, flechas, reações e parafusos A307);
mostra **38 verificações** com o item da norma em cada uma e gera o texto da requisição.

**Não faz:** longarina, patamar e ligações da longarina; guarda-corpo (só confere as medidas); a
pressão de contato do parafuso na chapa lateral (o catálogo não informa a espessura).

## Geometria (seção 5.1 a 5.5)

* **Espelho.** Faixa legal `[hL_min; hL_max]`: NR-22 180–200 mm; NR-12 com espelho 200–250 mm; NR-12
  sem espelho até 250 mm. Três níveis, testados em ordem: 1) `[max(hL_min; 160; 175); min(hL_max; 180)]`
  (atende norma, Anglo e catálogo); 2) `[max(hL_min; 160); min(hL_max; 180)]` (`C` passa de 300 mm);
  3) a faixa legal (conflito: prevalece a norma, Anglo 3.1); 4) nenhuma. Um nível é viável quando
  `h_min ≤ h_max` e `⌈H/h_max⌉ ≤ ⌊H/h_min⌋`. `n` = o imposto ou o automático; `h = H/n`.
* **Piso.** Faixa Anglo `630 − 2h ≤ b ≤ 640 − 2h` e faixa legal (NR-22 sem limite; espelho fechado
  `b ≥ 200`; NR-12 sem espelho `max(150; 600 − 2h) ≤ b ≤ 660 − 2h`). O automático é o **menor
  múltiplo de 5 mm** da interseção (menor `b`, menor `C`); sem interseção, vale o requisito legal.
  `α = atan(h/b)`.
* **Profundidade.** `C ≥ max(b + 20; b; 175)`; padronizada, segue 175, 200, 225… (e passa de 300 se
  preciso); `F` vem do maior `C` padrão que não passa de `min(max(C; 175); 300)` (85, 85, 110, 110, 135,
  135). `r = C − b`.
* **Lances.** Altura máxima por lance: a imposta, 3.600 mm (NR-22) ou 3.000 mm (NR-12). `k_max = ⌊altura/h⌋`;
  `n_lances = ⌈n/k_max⌉`; degraus em grade `= n − n_lances` (o último espelho chega ao patamar).
  **Se a altura imposta for maior que a legal, a verificação 12 continua comparando com a legal.**
* **Largura.** Mínima legal 600 mm (NR-22), 600 mm (NR-12; 500 mm num lance único abaixo de 1,5 m);
  mínima Anglo 800 mm (1.100 mm em permanência constante; cabine até 3.700 mm 800 mm).

## Degrau (seção 5.6 a 5.9)

Vão `L`, biapoiado nas chapas laterais. `n_bb = ⌊(C − t)/p⌋ + 1` barras; `n_ef = min(n_bb; ⌊b_c/p⌋ + 1)`
sob a carga concentrada (um modelo de grelha deu 4,0 a 4,9 barras efetivas na malha 30 e 3,0 a 3,2 na
malha 41; o valor adotado fica igual ou abaixo, a favor da segurança).

* **FLT** (NBR 8800 Tabela G.1, seção sólida retangular): `λ = s/r_y` com `s` = passo das barras de
  ligação; `λp = 0,13·E·√(J·A)/M_pl`; `λr = 2,00·E·√(J·A)/M_r`; `M_cr = 2,00·C_b·E·√(J·A)/λ`; `M_Rk` =
  `M_pl` (λ ≤ λp), interpolação (λp < λ ≤ λr) ou `min(M_pl; M_cr)`; `M_Rd = M_Rk/γa1`.
* **Cargas:** `w = (γg·g + γq·q)·C` (distribuída em todas as barras); a concentrada `P` junto ao bocel,
  sobre `n_ef` barras, **não se soma** à distribuída; cisalhamento com a carga junto ao apoio.
* **Flechas:** `δ = 5·(g + q)·C·L⁴/(384·E·n_bb·I) ≤ L/300`; `δ_ISO = P_ISO·L³/(48·E·n_ef·I) ≤
  min(L/300; 6 mm)`.
* **Peso:** `(h·t/p + a²/s)·ρ/1000` kg/m², com `a` = lado da barra de ligação (**adotado**); o degrau
  pesa `×1,20·C·L` (Selmec nota 4). É estimativa.
* **Seleção:** "Atende" = `u_max ≤ 1`, `L ≤ L máx` do modelo, `L ≥ 500` e `t ≥ 2,00 mm`. Ordem: manual;
  o mais leve que atende e está na preferência; o mais leve que atende; o de menor `u_max`. Desempate
  pela ordem do catálogo (`T`, `k`, `h_b`, `tt`).
* **Parafuso A307** (`f_ub = 415 MPa`): `F_v,Rd = 0,40·A_b·f_ub/γa2`; reação `R_d = max(γg·R_g + γq·R_q;
  γg·R_g + γq·P)` por chapa lateral.

## As 38 verificações

Cada linha traz a **norma e o item**, o valor, o limite, o aproveitamento (só as de resistência) e o
status. Status: `OK`, `NÃO OK`, `ALERTA` (atende com ressalva ou há conflito entre normas), `N/A` e
`INFO`; a contagem `35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A` não inclui o `INFO` (o modelo adotado).
Os itens 1 a 16 são a geometria (espelho, Blondel, profundidade, inclinação, lances, larguras,
patamar); 17 a 29, o degrau e o material; 30 a 33, a fixação; 34 a 38, a conferência do guarda-corpo.

## Conflitos entre normas (sempre mostrados)

1. NR-22 (espelho de 180 a 200 mm) × Anglo (160 a 180 mm): só `h = 180 mm` atende aos dois.
2. NR-12 item 12 (com espelho, `h` de 200 a 250 mm) × Anglo: sem interseção.
3. Guarda-corpo NR (1,10 a 1,20 m) × Anglo (≥ 1,30 m).
4. Parafuso Anglo ≥ 5/8" × furo padrão Selmec 9/16" (só aceita 1/2").
5. Catálogo (`C ≤ 300 mm`) × Anglo: exige `h ≥ 175 mm`.

## Regras de implementação

* **Nada é corrigido em silêncio.** `H ≤ 0`, `L ≤ 0`, `n` imposto inválido, altura por lance menor que
  um espelho, `b ≤ 0` e `C ≤ b` levantam `EntradaInvalida` (a página mostra o erro e não calcula).
* Um parâmetro, um nome: `h_max_legal` (a faixa do espelho) e `altura_max_lance` (o lance) nunca se
  misturam — a planilha teve um erro real por dois nomes que só diferiam em maiúsculas.
* Toda constante numérica sai do dicionário `K` ou das tabelas do módulo, com a fonte em comentário.
* Tolerância de 0,01 mm nas comparações de faixa.

## Pontos a conferir

* O item da NBR 6120 da carga de 2,5 kN (2.2.1.7 é da edição 1980; conferir o da edição 2019).
* A numeração dos itens da NR-22 (22.6.5, 22.9.3, 22.10) segue a especificação do projeto.
* Aço inoxidável está fora do escopo da NBR 8800: `fy` e `E` do inox são indicativos.
* Conferir os desenhos-padrão Anglo AA-BR-DPST-ES-0001 a 0004 (Anglo 8.4 e 10.2).

## Memorial e exportações

O registro entra no memorial da Central de relatórios como as demais análises com tabela de
verificações: **Resultado**, dados de entrada, método e premissas, **O que passou**, valores de apoio,
as quatro tabelas (geometria, dimensionamento do modelo adotado, modelos que atendem e texto da
requisição) e, no fim, **o que não passou** e o que conferir antes de emitir. A página ainda exporta as
38 verificações e os 64 modelos em CSV e o relatório completo em PDF.
