# Sensores do modelo

Página **Sensores do modelo** (`app_pages/sensores_do_modelo.py`), núcleo
`core/sensores_do_modelo.py`, lista dos sensores mínimos `core/sensores_recomendados.py`, gráfico
`core/desenho_dos_sensores.py`, ajuda `components/sensores_do_modelo_help.py`.

## De onde vem

A macro `macros_solidworks/exportar_casos_de_carga.bas` (botão em Esforços do modelo), depois de
**Executar** no gerenciador de casos de carga, grava `<estudo>-gerenciador-resultados.csv`: o quadro
da Vista de resultados — uma coluna por sensor, uma linha por caso primário e por combinação, com o
valor como a API devolve (`GetSensorResultValueForPrimaryLoadCase` e
`GetSensorResultValueForLoadCaseCombination`), **na unidade do sensor, que o arquivo não diz**.

O quadro entra na página Esforços do modelo junto com os outros arquivos da macro (ao gravar, vai
para o projeto, campo `sensores_do_modelo`) ou direto na página Sensores do modelo.

## O que cada sensor mede

O nome sugere a grandeza (`sm.grandeza_sugerida`): tensão (von Mises ou limite superior das vigas,
verificada ao escoamento), componente de tensão (axial, flexão, cisalhamento — só mostrada),
deslocamento, fator de segurança, força, momento, massa do estudo, frequência, fator de
flambagem, deformação específica (o strain do SolidWorks, não o deslocamento) ou outra. O fator de
segurança, o de flambagem e a frequência governam pelo menor valor; os outros, pelo maior em
módulo. A unidade padrão é a do SolidWorks em
português (N/mm², mm); o usuário confirma as duas na tabela. Uma linha `Unidade;;N/mm^2;mm;…` logo
abaixo dos títulos, se um dia a macro gravar, é lida.

**Conferência da unidade pelo FS.** O fator de segurança do SolidWorks é `f_y/σ` de cada ponto.
Onde o FS mínimo cai no ponto da tensão máxima, `σ·FS = f_y`; fora dele, `σ·FS > f_y` (porque
`σ(ponto do FS) ≤ σ_máx`). O programa agrupa os produtos e fica com o **menor grupo** (≥ 2 linhas):
é o f_y (250 MPa → A36; 345 → A572 Gr 50). Fora de 150–1000 MPa, a unidade da tensão está errada
(erro na conferência). As linhas com `σ·FS` maior são listadas: ali o FS mínimo está em outro
ponto — outro aço ou tensão menor.

## Ligação com o plano

As combinações vêm com o nome que o programa exportou (`C07-ELU`, `C49-ELSR`:
`ex.nome_da_combinacao`). A numeração depende dos estados-limites exportados e da ordem: o programa
tenta as permutações dos estados que as siglas indicam e o padrão, e fica com a que liga mais
nomes (`sm.ligar_ao_plano`). Cada combinação ligada traz o estado-limite, os fatores (código como
no SolidWorks: `T−` → `T-`) e a expressão.

## Conferência do quadro

| Achado | Nível | Efeito |
|---|---|---|
| Casos do plano que o estudo não tem (ex.: T+, T−) | atenção | linha ALERTA: as combinações saíram sem eles |
| Combinações do plano que não vieram (ex.: C51) | atenção | linha ALERTA |
| Combinações com o mesmo resultado em todos os sensores e **coeficientes diferentes nos casos do estudo** | erro | ficam **fora** da verificação (não são resultado) + linha ALERTA |
| Combinações iguais que diferem só em casos fora do estudo (C01 = C03 sem T) | info | explicado; observação "igual a C01" |
| Casos primários iguais | atenção | confira se não é o mesmo caso duas vezes |
| Superposição: `máx(comb) ≤ Σ|γ|·máx(caso)` (tensão, deslocamento) e `FS(comb) ≥ 1/Σ(|γ|/FS)` (folga 1 %) | atenção | o gerenciador tem coeficientes diferentes do plano + linha ALERTA |
| Combinação sem sigla e fora do plano | atenção | fora da verificação |
| Sem plano | info | estado pela sigla; sem conferir coeficientes nem repetidas |

A desigualdade do FS vale ponto a ponto mesmo com dois aços: `f_y(p)/σ_c(p) ≥ 1/Σγ_i·σ_i(p)/f_y(p) ≥
1/Σγ_i/FS_i`.

**Caso real (01/11/2026, peça teste01, macro v15):** o plano tinha T+ e T− (72 combinações) e o
estudo não; a pasta do gerenciador tinha só 50 "Secondary Load Case"; a C51-ELSR não veio e da C50
em diante as ELS deram os mesmos números em todos os sensores (C60 = PP + PE + 0,6·SC + 1·W90 igual
à C50 = PP + PE + SC + 0,3·W0). O arquivo está em `tests/dados_sensores.py`.

## Verificações

* **Tensão** (ELU, sem as linhas fora): `σ ≤ f_y/γ_a1`, `γ_a1 = 1,10`; f_y informado, ou o do
  `σ·FS`, ou 250 MPa adotado (com aviso).
* **Fator de segurança** (ELU): `FS ≥ γ_a1` (o FS do SolidWorks já usa o aço de cada ponto).
* **Deslocamento** (ELS): contra o limite escolhido para o sensor — item das Tabelas 3 e 4 do
  critério Anglo (`ca.DESLOCAMENTOS_VERTICAIS` e `ca.DESLOCAMENTOS_HORIZONTAIS`, com o vão L ou a
  altura H), `L/x` informado ou valor em mm. Sem limite: linha INFO; faltando o comprimento: ALERTA.
  O deslocamento do sensor é absoluto (a favor da segurança para a flecha relativa).
* Componente, força, momento e outras: só no resumo e no quadro.

A tensão elástica do modelo não verifica flambagem, FLT nem a interação N + M: isso é a
verificação barra a barra (Esforços do modelo). A página e o registro dizem isso.

## Memorial

`sm.registro_sensores` (módulo `sensores_do_modelo`): verificações, `tabelas_memorial` (o pior de
cada sensor nas ELU/ELS/casos; as combinações que governam com a expressão no modelo; o quadro
inteiro com o estado e a observação de cada linha, em tabelas de até 5 sensores),
`conferencia_do_quadro` e `figura_sensores` (redesenhada por `core/record_charts.py`: um painel por
sensor verificado, barra por combinação, a que governa escura e com o valor, as que ficaram fora em
vermelho claro, o limite tracejado). Alertas do registro = achados de erro e de atenção.

## Sensores mínimos de cada estudo

Cada sensor é o máximo (ou mínimo) de onde ele foi posto. A lista (`sr.RECOMENDADOS`, mostrada no
alto da página, aberta enquanto não há quadro) diz, para cada estudo, o nome a dar (o programa
reconhece), o caminho no SolidWorks (Dados do Simulation › quantidade › componente), o critério,
onde pôr, a unidade, o valor para o Alerta do sensor e para que serve:

| Estudo | Nível | Sensor (nome sugerido) | No SolidWorks |
|---|---|---|---|
| Estático | Mínimo | Tensão barras | Tensão da viga › limite superior de axial e flexão, máximo do modelo |
| Estático | Mínimo | Fator de segurança | Fator de segurança, mínimo do modelo |
| Estático | Mínimo | Flecha vigas | Deslocamento › UY, **mínimo** sobre as vigas (com Y para cima a flecha é negativa) |
| Estático | Mínimo, se há pilares | Deslocamento topo pilares | Deslocamento › URES, máximo sobre o topo dos pilares |
| Estático | Mínimo, se há chapas | Tensão chapas | Tensão › von Mises, máximo sobre as cascas/sólidos |
| Estático | Recomendado | Tensão vigas, Tensão pilares… | um sensor de tensão por grupo |
| Estático | Recomendado | Massa do modelo | Propriedades de massa do Simulation › Massa |
| Estático | Recomendado, se há conectores | Força parafusos | Força do conector |
| Flambagem | Mínimo | Fator de flambagem modo 1 | Fator de segurança de flambagem, com a ELU que governa |
| Flambagem | Recomendado | modos 2 e 3 | idem, estudo com ≥ 3 modos |
| Frequência | Mínimo | Frequência modo 1 | Frequência (o primeiro modo vertical do piso) |
| Frequência | Mínimo, se há equipamento | Frequência modo 1, 2, 3… | os modos até 1,5·Nm |
| Frequência | Recomendado | modos 2 a 5 | estudo com ≥ 5 modos |

Critérios citados: escoamento `f_y/γ_a1` (ABNT NBR 8800:2025); flecha e deslocamento lateral
(critério Anglo, Tabelas 3 e 4); flambagem pelo α_cr do modo de deslocamento lateral, com
`B₂ ≈ 1/(1 − 1/α_cr)`: α_cr ≥ 11 → pequena deslocabilidade (Δ₂/Δ₁ ≤ 1,10), 3,5 a 11 → média
(≤ 1,40), abaixo de 3,5 → grande (4.10.4; os números saem dos limites de `core/structural_2d.py`);
frequência do piso ≥ 4 Hz onde se caminha e nunca abaixo de 3 Hz (ABNT NBR 8800:2008, Anexo L,
L.1.2 e L.3.2); equipamento: faixas de Ne/Nm do critério Anglo 5.7. A aba "As opções do
SolidWorks" explica cada tipo e cada quantidade da lista do SolidWorks (Deformação, Forças de corpo
livre, Térmico, Sensível ao fluxo de trabalho… não precisam).

Flambagem e frequência são estudos à parte: o gerenciador de casos de carga é só do estático, e o
quadro não traz esses valores.

**Conferência** (`sm.conferir_minimo`, seção 3 da página): cada item do estudo estático fica
*Tem*, *Confirmar* (deslocamento cujo nome não diz a direção — a direção vem do limite escolhido,
Tabela 3 = vertical, Tabela 4 = horizontal, ou do nome: flecha/UY/viga × topo/UX/UZ/pilar) ou
*Falta*. Faltar um mínimo sem condição (tensão das barras, FS, flecha) dá aviso na conferência e
uma linha ALERTA nas verificações (a verificação fica de fora); os condicionais e os recomendados
só aparecem na tabela. A massa do estudo é conferida com a dos itens da lista de material (sem o
acréscimo): acima de 5 % de diferença é aviso.

Um sensor num vértice dá um valor com sinal e linear: a superposição fecha exatamente.
