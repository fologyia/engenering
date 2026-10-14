# Fluxo do projeto — base técnica, ações, plano de cargas, verificações e memorial

O programa serve para **conseguir as informações, registrar e anotar tudo e fazer as verificações** de
uma estrutura metálica, junto com o modelo (SolidWorks hoje; Robot Structural quando houver). Para o
preenchimento seguir sempre o mesmo padrão, o projeto passa por cinco etapas. A página inicial, a Base
técnica, o Plano de cargas e o Guia mostram esse caminho com o que o projeto ativo já tem.

| Etapa | Página | O que sai |
| --- | --- | --- |
| 1. Base técnica | **Base técnica do projeto** | critério do cliente, vento do local, tipo de estrutura (limite do deslocamento), sobrecarga, agressividade, vida útil |
| 2. Ações | **Cargas do esqueleto** (o que não está no modelo), **Vento em estruturas abertas**, **Vento nas estruturas** | cargas características nas barras do esqueleto (piso, sobrecarga, guarda-corpo, escadas, equipamentos, tubulações, ligações); forças do vento por nível, por pórtico e em cada nó; CSV |
| 3. Plano de cargas | **Plano de cargas** | ações com código padrão, cargas para o modelo, combinações ELU e ELS numeradas; CSV |
| 4. Verificações | **Esforços do modelo** (resultados do SolidWorks, placas de base), Vigas de piso, Contraventamento, Ligação, Estruturas de aço, Flambagem, Parafusos, Degrau | conferência das reações, pior caso de cada barra, tabelas de verificação com a norma e o item de cada linha; registro no projeto |
| 5. Memorial | **Central de relatórios** | Word e PDF com os cálculos registrados (o plano de cargas não entra: o memorial é o molde dos cálculos) |

## 1. Base técnica do projeto

Fica no documento do projeto em `projeto["base_tecnica"]` — fora de `criterios_projeto`, para não
mexer no hash dos critérios que marca registros como desatualizados (`core/base_tecnica.py`).

| Campo | Para que serve |
| --- | --- |
| Critério do cliente | `nenhum` ou `anglo` (Anglo American AA-BR-DPST-DR-0001 Rev. 1). Com o Anglo, a base começa com V₀ = 35 m/s, S₁ = 1,0, S₃ = 0,95 do cliente, plataforma de equipamentos e 5 kN/m². |
| V₀, S₁, terreno, S₃ | S₃ por grupo da Tabela 4 da NBR 6123:2023 ou o valor do cliente. |
| Tipo de estrutura | Define o limite do deslocamento horizontal do topo: plataforma H/400, pipe rack H/250, cobertura H/400 (Anglo, Tabela 4) ou NBR 8800 Tabela B.1 (H/300 um pavimento; H/400 e h/500 dois ou mais). |
| Sobrecarga | Local da Tabela 2 do critério Anglo ou valor informado. |
| Agressividade, vida útil, observações | Anotação do projeto. |

**Quem lê a base:** Vento em estruturas abertas e Contraventamento (V₀, S₁, terreno, S₃, sobrecarga,
tipo de estrutura, critério Anglo), Vento nas estruturas (V₀, relevo, terreno, grupo e S₃ do cliente),
Estruturas de aço → ações de plataforma (vento), Ligação de contraventamento (critério Anglo). Cada
página mostra de onde vieram os valores e tem o botão **Voltar aos valores da base técnica**. Os
conflitos do critério aparecem como aviso (ver `docs/criterio_anglo.md`).

## 2. Vento em estruturas abertas — só o vento, para anotar e lançar no modelo

A página usa os mesmos campos (mesmas chaves de sessão) do Contraventamento de estruturas abertas: o
que se digita numa aparece na outra. O cálculo é o do capítulo 8 da NBR 6123:2023
(`core/vento_estrutura_aberta.py`; ver `docs/contraventamento_estrutura.md`). Saídas:

* **Forças por nível** — estrutura, guarda-corpos e equipamentos, com a faixa de influência e o q.
* **Forças nos nós** (`cargas_nodais`) — uma linha por pórtico e nível: a força da estrutura e do
  guarda-corpo daquele pórtico naquele nível e a parcela de cada nó pilar–viga. A soma das linhas, mais
  os equipamentos e a faixa da base, é o total da direção (o teste trava isso).
* **Cargas nas barras** (`cargas_distribuidas`) — para quem prefere carga distribuída: pilares
  `η·C_a·q·b` por faixa, vigas de cada piso `η·C_a·q·d`, guarda-corpo `C_a·q·φ·h` na viga de borda.
  As diagonais ficam de fora (o vento nelas já está na força nos nós).
* **Desenho** dos pórticos vistos de lado com as forças por nível.
* **CSV** com ponto e vírgula e vírgula decimal (abre direto no Excel): nós (com a base) e barras.
* **Vento simplificado** (`cargas_simplificadas`) — para estruturas simples: uma carga por nível,
  o total do nível (estrutura e guarda-corpo) dividido pelas linhas de pilares que vão na direção do
  vento e pelo comprimento delas, aplicado **ao longo do eixo** dessas vigas. É a carga dos nós
  espalhada na linha: cada pórtico divide a força igualmente entre os pilares, então cada linha
  recebe `F/linhas` — e deslizar uma força ao longo da linha de ação não muda o equilíbrio. A cota,
  a divisão entre as linhas contraventadas, o momento na base e a torção da planta ficam iguais, e
  a viga não ganha a flexão lateral que teria uma viga perpendicular ao vento (o teste trava a
  soma por linha). Só as vigas das linhas de pilares; os equipamentos continuam como força no
  centro deles; a faixa da base vai à fundação. No SolidWorks: uma Força por nível, nas vigas,
  "por unidade de comprimento" (N/m).
* **Enviar ao plano de cargas** — grava W0, W90, W180 e W270 (as de 180° e 270° com o sinal
  trocado), na forma escolhida: simplificada (padrão) ou nos nós, para casos mais complicados. A
  mesma escolha está no Contraventamento de estruturas abertas.
* **Registrar** — o memorial traz o capítulo de cálculo com as três tabelas (níveis, pórticos, nós).

### No SolidWorks (Simulation)

Use a exportação do **Plano de cargas** (abaixo): ela já converte as unidades e os eixos. A faixa
da base (nível 0 do CSV dos nós) vai direto à fundação e não precisa entrar no modelo.

## 3. Plano de cargas

`projeto["plano_de_cargas"]` (`core/plano_de_cargas.py`): uma ação por código, com origem, resumo e as
cargas que vão para o modelo.

| Código | Ação | Categoria da NBR 8800 |
| --- | --- | --- |
| PP | Peso próprio da estrutura | peso próprio de estrutura metálica |
| PE | Permanentes de elementos construtivos | elementos construtivos industrializados |
| EQ | Equipamentos (vazios) | peso próprio de equipamentos (Projeto 2024) |
| EO | Equipamentos em operação (conteúdo) | sobrecarga de uso — depósitos |
| SC | Sobrecarga de uso | sobrecarga de uso |
| W0, W90, W180, W270 | Vento nas quatro direções | vento — grupo exclusivo "Vento" |
| T+, T− | Temperatura ±10 °C (Anglo 5.8) | variação de temperatura — grupo exclusivo |
| PRV, HT, HL, MO | Ponte rolante (vertical, transversal, longitudinal) e monovia | pontes rolantes |
| IM | Impacto e cargas dinâmicas de equipamentos (Anglo 5.3) | forças horizontais de equipamentos |
| EX | Ação excepcional | excepcional |

* **Um código por ação**: enviar o vento de novo substitui W0 a W270 — o plano não acumula cópias.
* **Combinações** (`combinacoes`) pelas Tabelas 1 e 2 da NBR 8800, numeradas (o número serve de nome
  do caso no modelo); grupos exclusivos nunca atuam juntos.
* **Critério Anglo 5.9** (`cobertura_das_combinacoes_anglo`): quais combinações mínimas do cliente já
  podem ser formadas e quais ações faltam; PRV, HT, HL e MO só contam se houver o equipamento.
* **CSV** das ações, das cargas e das combinações (com o fator de cada ação em colunas).
* Na página **Estruturas de aço → Combinações**, o botão **Trazer as ações do plano de cargas** monta a
  tabela com código, categoria, grupo e coeficientes do plano; N, V e M ficam zerados para receber os
  esforços característicos da barra tirados do modelo.
* **Conferência do plano** (`conferir_plano`): erro para o que o modelo não aceita (temperatura em
  kN, força em °C, carga sem direção) e atenção para o que costuma ser esquecido (sem PP, sem
  sobrecarga, vento numa direção só, temperatura num sentido só, ação sem carga, carga nula ou
  repetida, vento com carga vertical, combinações mínimas Anglo com a ação que falta).
* **Editar** uma ação: escolha o código que já está no plano e os campos trazem o que está gravado.
* **Símbolos** na tabela: ↓ g gravidade, → ↑ ← ↓ vento na planta, ΔT temperatura, ⇄ ⇅ ponte rolante.

### Exportar para o modelo (`core/exportacao_cargas.py`)

| Escolha | Opções |
| --- | --- |
| Unidades | N e mm (SolidWorks MMGS), N e m (SolidWorks SI), kN e m (Robot, SAP2000, Ftool) |
| Eixo vertical | Y para cima (SolidWorks) ou Z para cima (Robot, SAP2000) |

* **Cargas por caso**: uma linha por carga com o tipo (força concentrada, carga distribuída em
  barra, por área, momento, temperatura), onde aplicar, o valor convertido, **F_x, F_y e F_z com
  sinal** nos eixos escolhidos, o sentido por extenso e o comando equivalente no SolidWorks e no
  Robot. O **PP** sem cargas vira a **gravidade** do modelo (9,81 m/s² para baixo).
* Convenção: Z (vertical) com valor positivo é para baixo; X e Y levam o sinal no valor. Com Y para
  cima, (F_x, F_y, F_z) do programa vira (F_x, F_z, −F_y): na vista Superior do SolidWorks o
  desenho fica igual à planta.
* **Combinações**: matriz (uma linha por combinação, uma coluna por caso — o arranjo do gerenciador
  de casos de carga do SolidWorks) e lista (combinação, caso, fator — o formato que SAP2000, ETABS e
  STAAD importam). Nomes curtos: C01-ELU, C14-ELSR, C20-ELSF, C27-ELSQ.
* **Gerenciador de casos de carga do SolidWorks** (`cenario_de_carga`): o arranjo da vista de
  cenário de carga — uma coluna por carga do estudo (a gravidade, cada força ou carga distribuída
  num lugar e num eixo, cada pressão, cada temperatura), uma linha por caso primário, e em cada
  célula o valor do caso ou "Suprimir". A gravidade e as forças são criadas com o plano de
  referência do eixo (Plano superior = Y, Plano direito = X, Plano frontal = Z) e o valor com sinal
  em "Normal ao plano": a gravidade é −9,81 com o Y para cima, o W0 e o W180 na mesma barra são a
  mesma carga em X (+2000 e −2000), e o Y da planta é o −Z do SolidWorks. As colunas têm o nome que
  o SolidWorks dá (Gravidade-1, Força-1, Pressão-1…) se as cargas forem criadas na ordem da aba
  "Cargas do estudo"; o momento na junta da viga é componente da Força. Os códigos vão com hífen
  (T− → T-). As combinações vêm embaixo, só para ver no SolidWorks.
* **Arquivo do gerenciador** (`core/gerenciador_solidworks.py`): o CSV que o gerenciador salva e
  carrega ("Salvar os dados em um arquivo .csv externo" / "Carregar os dados de entrada…"):
  linhas Tipo de carga (3 força, 4 gravidade, 1 pressão), Nome da carga, Valor de (a componente:
  a força tem seis — três de força e três de momento —, a gravidade três, a pressão uma) e Valores
  originais (com a unidade); depois um caso por linha (valor sem unidade, ponto decimal, ou
  Suprimir) e as combinações (`C01-ELU, 1.25*"PP" + 1.5*"SC"`). cp1252, vírgula, CRLF, sem aspas:
  lido e gravado de novo, o arquivo do SolidWorks sai byte a byte igual. `do_plano` monta o arquivo
  do plano, em N e m; `preencher` pega o arquivo salvo pelo SolidWorks, liga cada carga do estudo
  à do plano (pelo nome Força-1…, ou pelo código do caso que só ela usa, como PP e SC), confere o
  valor e o sinal com que ela foi criada (gravidade de 10,5 contra 9,81 do plano: aviso e o valor
  do plano; sinal oposto: troca o sinal e pede para conferir a seta), suprime a carga que o plano
  não tem, aponta a que falta e devolve o arquivo com o cabeçalho do SolidWorks e os casos do
  plano. A temperatura fica como está no SolidWorks: lá a carga é a temperatura aplicada
  (referência do estudo + ΔT). Caso sem nenhuma carga no estudo fica de fora do arquivo.
* **Planilha Excel** com as abas Leia-me (passo a passo no SolidWorks — um estudo por caso ou um
  estudo só com o gerenciador de casos de carga —, no Robot e em outros programas), Ações, Cargas,
  Casos de carga (SolidWorks), Cargas do estudo, Combinações e Combinações (lista); os mesmos dados
  em CSV.

### Passo a passo no SolidWorks Simulation

1. Estudo estático com o material do aço (200 GPa, 7850 kg/m³).
2. Cada carga da aba **Cargas do estudo** criada uma vez, na ordem da aba, com o plano de
   referência e o valor com sinal em "Normal ao plano".
3. No **Gerenciador de casos de carga**, "Carregar os dados de entrada de um arquivo .csv externo"
   com o arquivo da página Plano de cargas — ou, mais seguro, "Salvar os dados em um arquivo .csv
   externo", enviar na página (Conferir e preencher) e carregar o arquivo preenchido. As fixações
   ficam ativas em todos os casos. Valores característicos.
4. Os resultados de cada caso primário: a macro `macros_solidworks/exportar_casos_de_carga.bas`
   (botão na página Esforços do modelo) passa caso por caso pelo gerenciador
   (`LoadResultsOfPrimaryLoadCase`) e grava `<estudo>-<caso>-forcas.csv` (formato do "Listar forças
   da viga", elemento a elemento, por `GetBeamForcesForEntities`) e `<estudo>-<caso>-reacoes.csv`
   (formato do "Listar forças resultantes", por `GetReactionForcesAndMomentsWithSelections`), com
   "Caso de carga: <caso>" no cabeçalho, e o quadro dos sensores da Vista de resultados em cada caso
   e combinação. Sem a macro: Listar forças da viga e Listar forças resultantes à mão, com o código
   do caso no nome do arquivo (`caso_do_arquivo_sugerido`). A leitura descobre sozinha se o arquivo
   traz a força na ponta (o "Listar") ou já o esforço interno: no mesmo elemento, o axial e o torque
   das duas pontas têm de sair iguais.
5. Força em vigas: no SolidWorks ela é "por item" (o valor inteiro em cada viga selecionada) se não
   se marcar "por unidade de comprimento". O preenchimento do gerenciador avisa quando a carga do
   plano é por metro e a do estudo foi criada em N.
6. As combinações do gerenciador servem só para olhar no SolidWorks: o programa importa os casos
   primários e combina pela NBR 8800. Combinações iguais saem uma vez só (`pc.combinacoes`): no ELS
   frequente e no quase permanente o vento entra com ψ2 = 0.
7. Reação zero em um caso = modelo sem fixação (o SolidWorks rodou com mola macia ou alívio
   inercial): a conferência das reações acusa erro e os esforços daquele caso não valem.

## 4 e 5. Verificações e memorial

Os resultados do SolidWorks (forças das vigas e reações de cada estudo/caso) entram pela página
**Esforços do modelo**: conferência das reações contra o plano e pior caso de cada barra nas
combinações, verificação das barras, quadro das fundações e placas de base (ver
`docs/esforcos_do_modelo.md`). A **Lista de material** (`docs/lista_de_material.md`) dá a massa, o
peso e a pintura para o orçamento e confere o peso com o caso PP do modelo; fica fora do memorial.

Cada página de verificação registra o cálculo no projeto. Os registros com tabela de verificações têm o
capítulo com o resultado, o que passou e o que não passou (`docs/memorial_de_calculo.md`). Os de
cálculo sem verificação (o vento em estruturas abertas) têm o **capítulo de cálculo**: resultado em
destaque, dados de entrada, método, as tabelas do módulo e o que conferir.

## Testes

`tests/test_base_tecnica.py`, `tests/test_plano_de_cargas.py`, `tests/test_vento_aberto_saidas.py`,
`tests/test_figuras_estrutura.py`, `tests/test_criterio_anglo_verificacoes.py` e
`tests/test_base_tecnica_pagina.py` (páginas, “?” em todo campo, gravação da base, envio ao plano,
registro, guia e página inicial).
