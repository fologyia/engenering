# Critério Anglo American — o que o programa usa e onde

Critério de Projeto **Anglo American AA-BR-DPST-DR-0001, Rev. 1 (22/12/2025) — Estruturas
Metálicas**, aplicável ao Sistema Minas-Rio (Conceição do Mato Dentro-MG, mineroduto e filtragem do
porto). Todos os valores estão em `core/criterio_anglo.py`, cada um com o item do documento
(`ca.item("5.6")` → "Anglo 5.6"). A página **Base técnica do projeto** traz a consulta completa, em
abas, com o número do item.

## Onde cada item entra

| Item | Valor | Onde o programa usa |
| --- | --- | --- |
| 5.6 | V₀ = 35 m/s, S₁ = 1,0, S₃ = 0,95 | base técnica Anglo → páginas de vento e contraventamento |
| 5.2, Tabela 2 | sobrecargas mínimas por local (0,25 a 10 kN/m²) | base técnica (sobrecarga de referência) e Plano de cargas (SC) |
| 5.3 | impactos (rotativas +20 %, vibratórios +100 %/25 %, veículos +30 %, tirantes +33 %) | consulta; código IM do plano |
| 5.4 e 5.5 | ponte rolante e monovia | consulta; códigos PRV, HT, HL, MO |
| 5.7 | vibração: Ne entre 1,25 e 1,5·Nm (preferencial), entre 0,575 e 0,8·Nm (alternativa) ou abaixo de 0,425·Nm; coeficiente dinâmico; amplitudes | calculadora na base técnica (`avaliar_frequencia`) |
| 5.8 | temperatura ±10 °C | botão "Incluir temperatura" do Plano de cargas (T+ e T−, grupo exclusivo) |
| 5.9 | combinações mínimas | Plano de cargas: quais já podem ser formadas e o que falta |
| 7, Tabelas 3 e 4 | deslocamentos (plataforma H/400, pipe rack H/250, cobertura H/400, entre pisos h/500…) | tipo de estrutura da base → limite do topo no Contraventamento |
| 8.2, Tabela 5 | redução do comprimento de cantoneiras tracionadas (2, 3 ou 5 mm acima de 3 m) | linha INFO na diagonal em cantoneira |
| 8.3 | esbeltez 300 (tração) e 200 (compressão) | consulta (as verificações já usam os limites da NBR) |
| 8.8 | espessuras e diâmetros mínimos (cantoneira 4,75 mm, chapa de ligação 8 mm, parafuso 5/8", tirante 1/2") | diagonal e chapa de nó |
| 4.5, nota 1 | chapas acima de 31,5 mm 100 % ensaiadas por ultrassom | chapa de nó (ALERTA) |
| 8.7 | chumbadores: furos, arruelas, grout | consulta |
| 9.1 | A325 galvanizado com rosca no plano de corte; ≥ 2 parafusos; até 1" de preferência; ligação ≥ 0,75·N_t,Rd e ≥ 3 t | diagonal e chapa de nó |
| 9.2.1, Tabela 6 | filete mínimo por espessura (3, 5, 6, 8 mm) | chapa de nó e dimensionamento automático |
| 10.2 | escadas e guarda-corpos | consulta (o módulo Degrau de escada usa o critério completo) |

## Verificações acrescentadas com o critério ligado

**Contraventamento de estruturas abertas** (`contraventamento_barras.verificacoes_anglo`): espessura
mínima da cantoneira, redução do comprimento (INFO), diâmetro mínimo do tirante, diâmetro mínimo do
parafuso, parafuso acima de 1" (ALERTA), A307 numa diagonal (NÃO OK) e capacidade mínima da ligação.
O tipo de estrutura troca o limite do deslocamento pelo da Tabela 4.

**Ligação de contraventamento** (`contraventamento_ligacao.verificacoes_anglo`): chapa de nó ≥ 8 mm,
chapa > 31,5 mm com ultrassom (ALERTA), ≥ 2 parafusos, parafuso ≥ 5/8", parafuso > 1" (ALERTA), grau
A307 (NÃO OK) ou A490 (ALERTA: não pode ser galvanizado a fogo), filete mínimo da Tabela 6 na viga e
na coluna, e a lembrança da capacidade mínima (conferida na página do contraventamento, com a
diagonal). No modo simplificado as pernas das soldas nunca ficam abaixo da Tabela 6.

O critério liga sozinho quando a base técnica do projeto é a da Anglo; cada página tem a chave para
ligar ou desligar.

## Conflitos com as normas (aparecem como aviso)

1. **S₃ = 0,95** (5.6) é o valor que a NBR 6123:**1988** dava a instalações industriais com baixo fator
   de ocupação. Na NBR 6123:**2023**, indústrias são o grupo 3 (S₃ = 1,00) e 0,95 ficou para
   edificações sem ocupação humana (grupo 4). Com 0,95 a pressão dinâmica fica cerca de 10 % menor
   que a da norma vigente — **confirme com a Anglo qual adotar**. O programa usa o valor do cliente
   quando a base é a da Anglo e mostra o aviso em toda página de vento.
2. **Tabela 4**: colunas de plataformas sob vento aparecem com H/400 e com H/300 (máx. 30 mm); colunas
   ao nível da cobertura com H/300 e com H/400. O programa usa a mais rigorosa (H/400).
3. **5.7**: o coeficiente dinâmico para Nm > Ne está escrito `1/(1 − Ne²/m)`; o programa usa
   `1/(1 − Ne²/Nm²)`.

## Testes

`tests/test_base_tecnica.py` (valores e tabelas do critério, base técnica, limites) e
`tests/test_criterio_anglo_verificacoes.py` (linhas acrescentadas na diagonal, na chapa de nó e no
dimensionamento automático).
