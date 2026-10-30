# Ligação parafusada estrutural (Projeto de parafusos › Ligação estrutural de aço)

Cálculo em `core/bolted_connection.py` (fórmulas) e `core/bolted_joint_check.py` (a sequência
de verificações); tela em `components/structural_bolted_ui.py`; tabelas normativas em
`data/normas_parafusos.json`, cada uma com a fonte.

## Normas

* **ABNT NBR 8800:2025** — a versão vigente e a que a página abre. O código interno continua
  `NBR8800_2024` (veio do projeto de revisão de 2024; trocar a chave quebraria os registros
  gravados). Conferidas nas fotos da norma enviadas pelo usuário (28/10/2026): Tabelas 1, 3, 14,
  16 e 19.
* **ABNT NBR 8800:2008** — para comparação, com o texto conferido na pasta de normas.
* AISC 360 (LRFD) e RCSC 2004.

Cada versão usa as próprias tabelas e coeficientes — nada se mistura. A nota de versão aparece só
na página (`chk.NOTA_DA_VERSAO`), nunca no registro nem no memorial; o aviso antigo sobre a
validade da norma, que o usuário mandou retirar, não volta (um teste trava).

## O que é verificado

1. **Corte e contato/rasgamento** do parafuso crítico (grupo excêntrico, método elástico), com
   ℓ_f medido a partir do furo e o teto 2,4·d_b·t·f_u/γ_a2 (ou 3,0 sem limite de deformação; 1,0
   e 2,0 no furo muito alongado transversal).
2. **Tração no parafuso** (NBR 6.3.3.1): F_t,Rd = A_be·f_ub/γ_a2, A_be = 0,75·A_b. A tração do
   **grupo** (N_t, e o momento fora do plano M_t com o eixo neutro no centro do grupo) vira a
   força **por parafuso**; parafuso comprimido fica com zero.
3. **Interação tração + corte** (6.3.3.4), parafuso a parafuso: (F_t,Sd/F_t,Rd)² +
   (F_v,Sd/F_v,Rd)² ≤ 1. Alternativa tabelada (opcional): F_t,Sd ≤ f_ub·A_b/γ_a2 − 1,9·F_v,Sd
   (1,5 com o plano de corte fora da rosca) — **Tabela 11 na 2008** (conferida), **Tabela 12 na
   2025** (pelo pedido do usuário). AISC: J3.7 (F'_nt reduzido).
4. **Efeito de alavanca** (6.3.5):
   * 2025: placa rígida t ≥ √[4·(b − 0,5·d_b)·F_t,0,Sd·γ_a1/(p·f_u)]; placa flexível com δ, β e
     α, t_req = t_rígida/√(1 + δ·α) (a limitado a 1,25·b; β < 0 → trocar o parafuso). Larguras
     p_ext e p_int calculadas. A tração com alavanca é informada pelo usuário (nunca menor que
     F_t,0,Sd); sem ela, um aviso.
   * 2008 (6.3.5.2, conferido): chapa com M = F_t·b na largura p — plástico (Z = p·t²/4, parafuso
     −33 %) ou elástico (W = p·t²/6, −25 %) — e a ≥ b.
5. **Furos** (tipo: padrão, alargado, pouco/muito alongado paralelo/transversal à força): medidas
   da Tab. 14 da 2025 (= AISC 360-16) ou da Tab. 12 da 2008 (furo-padrão d_b + 1,5 mm: o M16 tem
   17,5 mm na 2008 e 18 mm na 2025). ℓ_f usa a medida ao longo da força; a seção líquida, a que a
   atravessa. Furo alargado só em ligação por atrito (Tab. 13 da 2008). Borda mínima com β·d_b na
   2008 (6.3.11.2).
6. **Deslizamento**: serviço com furo-padrão (e alongado transversal), ELU com alargado e alongado
   paralelo. 2025: C_e (chapas de enchimento) e γ_e 1,20 / 1,40 (muito alongado). 2008: fator de
   furo C_h (1,00 / 0,85 / 0,70) e γ_e 1,20 — sem C_e. A tração reduz: F_t,Sk no serviço, F_t,Sd
   no ELU. AISC J3.8: φ 1,00 / 0,85 / 0,70.
7. **Chapa de ligação (gusset)**: tração por N — escoamento A_g·f_y/γ_a1 e ruptura A_e·f_u/γ_a2
   com **A_e = mín(A_n; 0,85·A_g)** (NBR 8800:2008, 6.5.3, conferido), A_n = A_g − Σ(d_h + 2)·t (sem os 2 mm com a opção
   "Furos feitos com broca", NBR 5.2.4.1 a, nas duas edições; o AISC soma sempre 1/16");
   C_t não se aplica à chapa de ligação; t mínimo abaixo de 1 mm sai como "desprezível". E
   **cisalhamento por V** (6.5.5, conferido na 2008): 0,60·A_g·f_y/γ_a1 e 0,60·A_nv·f_u/γ_a2 na
   mesma seção transversal da chapa (largura × t, com os furos), separado de N — a norma não traz
   interação para elemento de ligação. Sem a chapa, o memorial declara que V não foi verificado na
   chapa; na peça, o cisalhamento por V fica "a confirmar" (a seção dela não é informada).
8. Peça tracionada (C_t), colapso por rasgamento, disposições construtivas (espaçamento máximo
   compara o passo real com mín(24t; 300) ou mín(14t; 180)), critério Anglo.
9. **Regra dos 75% da Anglo (9.1)** — só para peça de treliça/contraventamento dimensionada pela
   esbeltez ou sem esforço indicado: R_lig ≥ máx(0,75·N_t,Rd; 3 tf), com R_lig = a menor entre
   corte × n, contato × n (o parafuso crítico, conservador), colapso por rasgamento, chapa de
   ligação (escoamento e ruptura) e deslizamento × n. O marcador aparece nos dados de entrada do
   memorial mesmo desligado.

Aço digitado (f_y e f_u): f_u ≤ f_y é erro, com a sugestão do aço do catálogo.

## Memorial na página

Os botões "Baixar o memorial desta ligação (Word / PDF)" geram, no clique, o memorial só desta
ligação no padrão do memorial do projeto (`chk.memorial_da_ligacao`). Com projeto ativo, a capa
leva os dados dele; sem projeto, os campos ficam "[a preencher]".

Regras do memorial (correções de 28/10/2026, caso M22 do usuário em
`tests/test_memorial_ligacao_parafusada.py`):

* o nome da norma vem só de `chk.NORMAS_ROTULOS` — título, campo Norma, referência de cada linha e
  lista de referências; nada de "2024" nem "Projeto de revisão" no memorial da ligação;
* a equação do contato sai dos mesmos coeficientes do cálculo (`bc.coeficientes_contato`: 1,2/2,4
  com a deformação do furo limitada, 1,5/3,0 sem limite), com os valores substituídos;
* só entram as equações que valem para a ligação (`ResultadoLigacao.equacoes`); a tração, a
  interação, o limite da tabela alternativa e a placa rígida ficam na seção "Tração, interação e
  efeito de alavanca", que só aparece com F_t,Sd > 0;
* item de norma não vira decimal ("AISC J3.3", "RCSC 5.1", "NBR 5.2" — `decimal_ptbr`);
* as colunas Solicitante e Resistente saem com duas casas decimais
  (`resultados["casas_decimais_da_tabela"]`);
* o método não cita planilha: a planilha de referência não tem versão registrada.

## A confirmar na NBR 8800:2025 (texto não visto)

* 6.3.3.4 e Tabela 12 (a alternativa da interação);
* 6.3.4.3/6.3.4.4 e Tabela 13 (γ_e; o muito alongado transversal como ELU);
* Tabela 15 (tipos de ligação permitidos com furo alargado/alongado — aplicada a regra da 2008);
* Tabela 17 (incremento da borda mínima — não aplicado na 2025; aparece um aviso);
* 6.3.5 (alavanca: o pedido dizia "× √(1 + δ·α)"; a dedução e o AISC Manual dividem — o
  programa divide);
* 6.5.3 (A_e da chapa de ligação);
* 6.5.5 (cisalhamento do elemento de ligação e se há interação com a tração);
* Tabela A.3 (f_ub; graus ISO 8.8 e 4.6 não entraram).

## Testes

`tests/test_parafusos_tracao_e_furos.py` (casos de aceite A a E, 0,5 %; tração, interação,
alavanca, furos das duas versões, deslizamento, chapa de ligação, entradas, memorial Word e PDF),
`tests/test_casos_de_aceite.py` (os mesmos casos que a Central de validação mostra ao vivo),
`tests/test_bolted_connection.py`, `tests/test_bolted_joint_check.py`, `tests/test_bolted_help.py`
e `tests/test_projeto_parafusos_pagina.py` (a página; o caso real da emenda de U pela 2008).
