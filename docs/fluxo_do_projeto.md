# Fluxo do projeto — base técnica, ações, plano de cargas, verificações e memorial

O programa serve para **conseguir as informações, registrar e anotar tudo e fazer as verificações** de
uma estrutura metálica, junto com o modelo (SolidWorks hoje; Robot Structural quando houver). Para o
preenchimento seguir sempre o mesmo padrão, o projeto passa por cinco etapas. A página inicial, a Base
técnica, o Plano de cargas e o Guia mostram esse caminho com o que o projeto ativo já tem.

| Etapa | Página | O que sai |
| --- | --- | --- |
| 1. Base técnica | **Base técnica do projeto** | critério do cliente, vento do local, tipo de estrutura (limite do deslocamento), sobrecarga, agressividade, vida útil |
| 2. Ações | **Vento em estruturas abertas**, **Vento nas estruturas**, pesos | forças características por nível, por pórtico e em cada nó; CSV |
| 3. Plano de cargas | **Plano de cargas** | ações com código padrão, cargas para o modelo, combinações ELU e ELS numeradas; CSV |
| 4. Verificações | Contraventamento, Ligação, Estruturas de aço, Flambagem, Parafusos, Degrau | tabelas de verificação com a norma e o item de cada linha; registro no projeto |
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
* **Enviar ao plano de cargas** — grava W0, W90, W180 e W270 (as de 180° e 270° com o sinal trocado).
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
* **Planilha Excel** com as abas Leia-me (passo a passo no SolidWorks, no Robot e em outros
  programas), Ações, Cargas, Combinações e Combinações (lista); os mesmos dados em CSV.

### Passo a passo no SolidWorks Simulation

1. Estudo estático com o material do aço (200 GPa, 7850 kg/m³).
2. No **Gerenciador de casos de carga**, um caso primário por código da aba Cargas (PP, SC, W0…).
3. Em cada caso, as cargas da aba Cargas (tipo e comando nas colunas "Tipo da carga" e "No
   SolidWorks"); o PP é a Gravidade.
4. As combinações da aba Combinações, uma por linha, com os fatores de cada caso.
5. Os esforços característicos de cada caso nas barras a verificar vão para as páginas de
   verificação (Estruturas de aço → "Trazer as ações do plano de cargas").

## 4 e 5. Verificações e memorial

Cada página de verificação registra o cálculo no projeto. Os registros com tabela de verificações têm o
capítulo com o resultado, o que passou e o que não passou (`docs/memorial_de_calculo.md`). Os de
cálculo sem verificação (o vento em estruturas abertas) têm o **capítulo de cálculo**: resultado em
destaque, dados de entrada, método, as tabelas do módulo e o que conferir.

## Testes

`tests/test_base_tecnica.py`, `tests/test_plano_de_cargas.py`, `tests/test_vento_aberto_saidas.py`,
`tests/test_figuras_estrutura.py`, `tests/test_criterio_anglo_verificacoes.py` e
`tests/test_base_tecnica_pagina.py` (páginas, “?” em todo campo, gravação da base, envio ao plano,
registro, guia e página inicial).
