# Esforços do modelo — importar os resultados do SolidWorks

A página **Esforços do modelo** (`app_pages/esforcos_modelo.py`, núcleo em
`core/esforcos_modelo.py`) lê os resultados do SolidWorks Simulation, confere se o modelo recebeu as
cargas do **Plano de cargas** e combina os casos com os fatores do plano, ponto a ponto, para achar
o pior caso de cada barra. Os esforços ficam no projeto em `projeto["esforcos_do_modelo"]`.

## O que exportar do SolidWorks

Com o estudo resolvido, botão direito em **Resultados**:

| Menu | Conteúdo | Uso |
| --- | --- | --- |
| Listar forças da viga | Para cada viga, as forças nas duas pontas (Fim 1 e Fim 2) de cada elemento da malha: axial, cisalhamentos 1 e 2, momentos 1 e 2, torque | Esforços ao longo de toda a barra (inclusive o meio do vão) |
| Listar forças resultantes | Soma das reações X, Y, Z (seleção e modelo inteiro) e dos momentos | Conferência do equilíbrio; com uma base selecionada de cada vez, as reações de cada apoio |
| Listar tensão | Os nós de maior tensão de von Mises | Só referência (as verificações usam forças) |

* **Um estudo por caso de carga**, com o código do plano no nome do estudo (`PP`, `SC`, `W0`…): o
  arquivo traz "Nome do estudo" e o programa sugere o caso (`caso_sugerido`).
* **Duplique o estudo** para os outros casos: a malha é a mesma e os esforços são combinados
  elemento a elemento. Com malhas diferentes o programa combina pela ordem dos elementos ou, se a
  quantidade mudar, pela soma dos máximos de cada caso (a favor da segurança) — e avisa.

## Leitura (`ler_arquivo`)

* Codificação UTF-8 ou a do Windows (cp1252), separador `;` (linha `sep=;`) ou `,`.
* Números em português: ponto de milhar e vírgula decimal (`78.611` = 78 611; `-1.019,1`;
  `1,4815E+05`). Com separador `,`, o ponto é decimal.
* Colunas reconhecidas pelo nome, em português ou inglês (Axial, Cisalhamento1/Shear1, Momento 1/
  Moment1, Torque); unidades do cabeçalho (N, kN, lbf, kgf; N.m, N.mm, kN.m, lbf.in, lbf.ft),
  convertidas para kN e kN·m.
* **Sinal:** as forças das duas pontas de cada elemento têm sinais opostos (forças nas pontas). O
  esforço interno, com **tração positiva**, é −F no Fim 1 e +F no Fim 2 — conferido num pilar
  comprimido de modelo real (o axial cresce de cima para baixo com o peso próprio).
* **Perfil pelo nome** (`perfil_do_nome`): `Canal c C8X13.75` → U 8" do catálogo de massa mais
  próxima; `Ângulo L2.5X2.5X0.25` → L 2 1/2" × 1/4"; `W8X31` ou `W 200 x 35.9` → o W de mesma altura
  e massa mais próxima. Barras `Aparar/Estender…` não dizem o perfil: escolhe-se na tabela das barras.
* **Eixo forte**: o programa sugere o momento que domina (nos perfis em U de piso, o Momento 2);
  confirma-se na tabela das barras.

## Conferência das reações (`conferir_reacoes`)

Para cada caso importado, nos eixos do plano (Z para cima; o Y do SolidWorks é a vertical):

* **Caso só vertical** (todas as cargas do plano na vertical, fora vento e temperatura): reação
  vertical para baixo é erro (gravidade ou carga invertida); reação horizontal acima de 0,5 % da
  vertical (mínimo 0,05 kN) pede conferência — causas comuns: pressão em face inclinada (sai normal
  à face), direção de referência das forças, direção da gravidade.
* **Forças concentradas do plano** (kN, com a quantidade de cada linha): a soma das reações tem de
  equilibrar a soma das forças (tolerância de 2 % ou 0,1 kN).
* **Carga por área**: reação ÷ carga = área carregada, para comparar com o piso.
* **PP sem cargas no plano**: o peso do modelo (kN e kg) e, com a Lista de material montada
  (`conferir_peso_proprio`, peso pela geometria do modelo ou pela lista sem o acréscimo), a
  comparação: até 5 % bate; reação γ vezes o peso (γ usual da NBR 8800 a ± 2 %: 1,25; 1,30; 1,35;
  1,40; 1,50) é **erro — estudo majorado**; mais pesado que isso é **erro — o estudo PP leva só a
  gravidade** (sobrecarga, equipamentos e o não modelado vão nos estudos deles); mais leve é aviso.
* **Estudo majorado**: forças concentradas do plano recebidas γ vezes também viram erro. No
  SolidWorks cada caso leva as cargas características — os coeficientes estão nas combinações do
  programa; com o estudo majorado a verificação majoraria duas vezes e o quadro das fundações, que
  pede cargas sem majorar (Anglo 5.9), sairia errado. Não há modo de importar estudo combinado.
* Casos do plano ainda sem esforços e casos importados fora do plano são avisados.

## Pior caso de cada barra (`envoltoria`)

As combinações são as do plano (só com os casos importados), nos estados-limite escolhidos (ELU
normal por padrão). Para cada barra: a maior compressão e a maior tração (com a combinação e o
ponto), o maior momento forte com o N da mesma combinação e ponto (para a interação N + M), o maior
momento fraco, cortante (resultante de V1 e V2) e torque. CSV com ponto e vírgula.

## Verificação das barras (`core/verificacao_barras.py`)

**Parâmetros por tipo** (Pilar, Viga, Diagonal, Contraventamento, Outro; gravados no projeto): aço,
comprimentos de flambagem K·L em torno do eixo forte (`Lx`) e do fraco (`Ly`), comprimento
destravado `Lb` (vazio = `Ly`), `Cb` e `B₂`. A **tabela das barras** pode mudar o aço e os
comprimentos de uma barra. Norma: Projeto NBR 8800:2024 (padrão), NBR 8800:2008 ou AISC 360-16.

Para cada barra, com as combinações **ELU** escolhidas (as de serviço ficam de fora):

1. Os esforços de todas as combinações e pontos (os mesmos da envoltória) são multiplicados pelo
   **B₂** do tipo — todos, sem separar a parcela de translação (a favor da segurança; o estudo
   estático do SolidWorks é de primeira ordem).
2. **Varredura rápida**: com N_c,Rd, N_t,Rd = A_g·f_y/γ_a1, M_x,Rd e M_y,Rd da barra, o índice da
   interação da NBR 8800 5.5.1.2 em cada combinação e ponto.
3. **Verificação completa** dos três pontos de maior índice na compressão, dos três na tração e do
   de maior compressão, pelo motor da página Flambagem de colunas (`core/column_buckling.py`):
   todos os modos de flambagem, flambagem local, FLT/FLM/FLA, B₁ com C_m = 1, interação N + M_x +
   M_y e o limite de esbeltez (200 na compressão; 300 numa barra só tracionada). Na tração, o
   escoamento da seção bruta e a interação; a ruptura da seção líquida depende da ligação.
4. **Cantoneiras simples**: compressão pela 5.3.5.4 (`compressao_de_cantoneira_simples`), tração no
   escoamento e aviso quando a flexão passa de 10 % de f_y.
5. **Cortante** (resultante de V₁ e V₂) contra 0,6·f_y·A_w/γ_a1 e **torção** informada.

Sem perfil, sem comprimentos ou com aço desconhecido a barra fica **sem dados** (pendente). O
resultado de cada barra traz a combinação e o ponto que governam e a tabela completa da
verificação; o **registro** leva uma linha por barra e a tabela de todas para o memorial (capítulo
com o resultado, o que passou e o que não passou).

## Quadro de cargas para as fundações (`core/quadro_fundacoes.py`)

Para cada barra marcada como **Pilar**, os esforços na ponta de **base**, caso a caso, **sem combinar
nem majorar** (critério Anglo, item 5.9: quem projeta a fundação faz as combinações dela).

* **Base**: a ponta inicial ou final da lista de pontos do pilar no arquivo. Automática = a ponta
  mais comprimida (o peso próprio faz a compressão crescer para baixo); com as duas pontas iguais
  (sem peso próprio no estudo), escolhe-se na coluna "Base (pilar)" da tabela das barras.
* **Convenção**: N = força vertical na fundação, compressão positiva (negativo = arrancamento);
  V₁, V₂, M₁, M₂ e T = esforços internos na seção da base, nos eixos 1 e 2 da seção do SolidWorks.
* **Conferência**: a soma de N das bases tem de bater com a reação vertical total do modelo (2 % ou
  0,1 kN) — se não bate, há apoios que não são base de pilar marcado ou alguma base está na ponta
  errada.
* **Saídas**: compressão por pilar (pilar × caso), quadro completo, Excel (Leia-me com a nota da
  Anglo e a convenção, Quadro, Compressão por pilar), CSV e registro no projeto (capítulo de cálculo
  no memorial com as duas tabelas).

## Placas de base dos pilares (`core/placa_base_pilares.py`)

Uma **placa padrão** para todos os pilares (gravada em `esforcos_do_modelo["placa"]`): comprimento N
(na direção da alma, a do momento do eixo forte), largura B, espessura, aço, f_ck, A₂/A₁, número de
chumbadores (total e na linha tracionada), diâmetro, aço do chumbador e a distância f do centro à
linha tracionada (vazio = N/2 − 50 mm).

* Para cada pilar do quadro das fundações, os esforços da base de cada caso (N com compressão
  positiva, cortantes, momentos) são **combinados com os fatores ELU** do plano; o momento é o do
  **eixo forte** da tabela das barras e o cortante, a resultante de V₁ e V₂.
* Em cada combinação, `core/base_plate.verificar_placa_base` (AISC Design Guide 1): compressão
  centrada (3.1), momento pequeno (3.3), momento grande com tração nos chumbadores (3.4) ou tração
  (3.2); **espessura da placa** com utilização (t_req/t)² (o momento resistente cresce com t²),
  **chumbadores** na tração, no cisalhamento e na interação (AISC J3.6 e J3.7). Vale a combinação
  de maior utilização.
* No **momento grande** o concreto trabalha em f_p,máx num comprimento Y por construção: a linha do
  contato é informativa (não é 100 % de uso); se Y não existe, a placa é pequena para o momento e o
  pilar **não atende**.
* **Alertas**: momento no eixo fraco acima de 10 % do forte (o DG1 trata um eixo só) e pilar que não
  é seção I. Placa menor que o pilar ou chumbador fora da placa deixa o pilar pendente.
* **Critério Anglo**: espessura mínima da placa (8.8: 16 mm; 12,5 mm em elemento leve), diâmetro
  mínimo do chumbador (5/8") e, para o diâmetro escolhido, o furo na placa, a arruela (não soldada) e
  o graute mínimo da tabela do item 8.7.
* **Saídas**: desenho da placa em planta (`svg_placa_de_base`), tabela por pilar, o cálculo completo
  do pilar escolhido, CSV e registro (uma linha por pilar; capítulo com o que passou e o que não
  passou no memorial). A ancoragem no concreto (cone, comprimento) e o bloco ficam para a fundação.

## Testes

`tests/test_esforcos_modelo.py` (leitura com arquivos no formato do SolidWorks gerados por
`tests/dados_solidworks.py` a partir do pórtico do mini exemplo, conferência, envoltória ponto a
ponto contra a conta à mão, malhas diferentes), `tests/test_verificacao_barras.py` (pilar contra a página Flambagem de colunas, B₂, pendências, tirante, cantoneira, registro e memorial) `tests/test_quadro_fundacoes.py`, `tests/test_placa_base_pilares.py` (conta à mão do Design Guide 1, momento grande, critério Anglo, placa pequena, pendências, eixo fraco, ida e volta pelo projeto, registro e desenho) e `tests/test_esforcos_modelo_pagina.py`.
