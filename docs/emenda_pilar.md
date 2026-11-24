# Emenda de pilar com talas parafusadas

Página **Estrutura metálica › Ligações e bases › Emenda de pilar** (`app_pages/emenda_pilar.py`).
Cálculo puro em `core/emenda_pilar.py`, desenho em `core/desenho_emenda_pilar.py`, textos dos "?"
em `components/emenda_pilar_help.py`, testes em `tests/test_emenda_pilar.py`.

## Arranjo

- uma tala externa em cada mesa (corte simples);
- duas talas na alma, uma de cada lado (corte duplo).

## Referências

| Fonte | O que vem dela |
|---|---|
| ABNT NBR 8800:2025 | todas as resistências (corte, contato, escoamento, ruptura, rasgamento, contato usinado, deslizamento), enchimento, esforço mínimo 6.1.6.2 e disposições. Os números de item seguem o texto de revisão de 2024: confirmar na edição vigente. |
| Critério Anglo AA-BR-DPST-DR-0001 | aço dos perfis (12), d_b ≥ 5/8" e talas ≥ 8 mm (8.8), rosca no plano, d_b ≤ 1" e n ≥ 2 (9.1) |
| SCI P207, seção 5 | só o modelo mecânico: forças nas mesas (passo 1), grupo da alma, flexão em y (passo 5), continuidade (5.2.4), atrito sob momento (5.2.1), nota C (módulo líquido) |
| AISC Manual Parte 14; Kulak, Fisher e Struik cap. 13 e 16 | método elástico do grupo de parafusos e filosofia da emenda |

Não são usados os fatores da BS 5950 (K_e = 1,1/1,2, p_y, 0,9·A_net, 1,1·K_s).

## O que é reaproveitado

`core.bolted_connection`: `resist_corte`, `resist_contato`, `resist_deslizamento`,
`areas_bloco_central`, `resist_colapso_rasgamento`, `dimensoes_do_furo` (furo-padrão da Tab. 14),
`PARAFUSOS` (borda mínima Tab. 16, F_Tb Tab. 19), `GRAUS` (f_ub da Tab. A.3), `SUPERFICIES` (μ),
`folga_do_furo` (+2 mm). `core.nbr8800.fator_chi` para χ. γ_a1 e γ_a2 editáveis: as funções
reaproveitadas são reescaladas por γ_a2 da tabela / γ_a2 informado.

O diâmetro das polegadas é o exato (3/4" = 19,05 mm); a tabela `PARAFUSOS` guarda 19,1, o que
daria F_v,Rd 0,5 % maior. A tabela T1 dos perfis W/HP 200 está embutida no módulo; um teste confere
com `data/perfis_ref_gerdau.json` e `core/perfis_gerdau_k.py`.

## Caso de validação

Entradas padrão (W 200 x 46,1 nos dois trechos, A572 Gr 50 e A36, 3/4" A325 com rosca no plano,
contato com gap 0, os dois casos padrão, L_x = L_y = 6000, a = 1200): F_v,Rd = 78,86 kN,
N_c,Rd = 671,0 kN, caso mínimo b, verificação 1 com 51 % (governa), extensão da tala 155 < 225 mm
→ VERIFICAR. Todos os números da especificação estão em `tests/test_emenda_pilar.py` (±0,5 %),
junto com os testes extras e o exemplo do SCI P207 5.4.

## Famílias de perfis

- **W e HP**: todos os do catálogo Gerdau (`data/perfis_ref_gerdau.json`, 98 W e 8 HP), com h e d'
  de `core/perfis_gerdau_k.py`. Os nomes seguem o catálogo (há grafias como "W 200 x 71,0(H)").
- **U**: os 12 U laminados (`data/perfis_ref_gerdau_u.json`). O catálogo não traz o raio de
  concordância: ele é informado (R); com R = 0 a disposição "Raio de concordância do U" fica a
  VERIFICAR. A furação da mesa é dada por x1 (do dorso da alma à 1ª linha); a tala externa
  encosta no dorso. Diferenças no cálculo:
  - mesa do pilar ao rasgamento (verif. 10): bloco em L, um plano de cisalhamento junto à alma e
    tração até a borda livre (a mesa do U só tem uma borda);
  - enchimento da alma com a diferença inteira de t_w (dorsos alinhados);
  - esbeltez local da mesa com b_f/t_f (aba única);
  - aviso: a estimativa de N_c,Rd não considera a flexo-torção; informar N_c,Rd.
- Os dois trechos precisam ser da mesma família.

## Talas internas (corte duplo)

Opcional. Duas talas internas por mesa no W (uma de cada lado da alma; n_l par) ou uma no U,
encostadas na ponta da mesa e com o comprimento da externa. A força da mesa se divide entre a
externa e as internas pela área (simplificação; AISC Manual Parte 14). Muda:

- verif. 1: corte duplo, n_b·2·F_v,Rd·β_f; verif. 13: deslizamento com 2 planos;
- verif. 2, 5–9 passam a levar só a parcela da externa; as internas têm 2i, 4i, 5i, 6i, 7i, 8i, 9i;
- 7i: menor entre a nota A (duas bordas) e o bloco em L para cada borda, em cada tala;
- disposições: t_i ≥ 8 mm, b_i ≤ (b_f − t_w)/2 − R (W) ou b_f − t_w − R (U), e_2i ≥ borda mínima,
  borda máxima com t_i, área de continuidade = externa + internas.

## Parafusos

Todos os diâmetros de `core.bolted_connection.PARAFUSOS` (1/2" a 1 1/4", M16 a M30); as
disposições marcam os que saem da faixa 5/8"–1" do critério Anglo.

## Registro, memorial e guia

- **Registrar no projeto** (`ep.registro`): grava só as verificações que se aplicam (as N/A
  ficam fora), os dados de entrada (rótulos em `ENTRADAS_CURADAS["emenda_pilar"]` de
  `core/memorial_verificacoes.py`), os esforços por caso (`tabelas_memorial` para o memorial do
  projeto e `combinacoes` para o trecho) e as duas vistas (`figuras_para_o_registro`). Status:
  "Atenção" quando há disposição a verificar.
- No **Memorial de cálculo** do projeto, a emenda entra na etapa "Ligações"
  (`core/memorial_do_projeto.py`).
- **Memorial desta emenda** (`ep.memorial_da_emenda`): Word = trecho para colar no documento
  oficial (`core.memorial_trecho`); PDF = padrão do memorial do projeto.
- **Guia geral**: capítulo "Emenda de pilar", com o exemplo do caso de validação (o "?" do
  cabeçalho da página abre o capítulo).

## Ligada ao modelo do SolidWorks

- `core/emendas_do_modelo.py`: acha as emendas no esqueleto (topo de um pilar em pé a menos de 5 cm
  do pé de outro; perfis diferentes = troca de perfil), junta as informadas (pilar + altura do pé) e
  tira as desmarcadas (gravadas em `EsforcosDoModelo.emendas`). Os esforços são os das combinações
  ELU (`combinados_do_membro`), com o B₂ do tipo Pilar, no pilar de cima: ponta de baixo por
  `quadro_fundacoes.ponta_da_base`, altura dos pontos pela ordem dos elementos, interpolação linear
  no meio, o ponto de cima num nó. Eixos como nas Ligações (eixo forte no Momento 2: V = V1,
  M_x = M2, M_y = M1).
- `montar_entrada`: perfis e aço da tabela das barras, K·L pelos travamentos do esqueleto, N_c,Rd
  pela Flambagem de colunas (com flexo-torção), vão e altura da situação b pelo trecho travado em
  L_x (`EntradaEmenda.vao_b`).
- `ep.sugerir_talas`: monta as talas pelas regras da página e sobe fileiras/espessuras até atender;
  o que reprova no próprio pilar (10–12) vira nota, sem engrossar a tala.
- Telas: seção 9 de Esforços do modelo; na Emenda de pilar, "Trazer do modelo", "Sugerir as
  talas" e "Todas as emendas do modelo" (`components/emendas_do_modelo_ui.py`). Testes:
  `tests/test_emendas_do_modelo.py` (contra o pórtico 3D resolvido de `tests/portico_3d_teste01.py`).

## Fora do escopo (extensível)

Emenda soldada, chapa de topo, perfis I/L/T, montagem, division plate (SCI P206/P212) e AISC 341.
