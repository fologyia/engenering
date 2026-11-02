# Sensores do modelo

Página **Sensores do modelo** (`app_pages/sensores_do_modelo.py`), núcleo
`core/sensores_do_modelo.py`, gráfico `core/desenho_dos_sensores.py`, ajuda
`components/sensores_do_modelo_help.py`.

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
deslocamento, fator de segurança, força, momento ou outra. A unidade padrão é a do SolidWorks em
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

## Para ter mais do que o máximo do modelo

Cada sensor é o máximo (ou mínimo) de onde ele foi posto. Para o memorial ficar completo, crie
sensores com nome claro:

* deslocamento **UY** num vértice no meio do vão de cada viga principal (flecha) e **UX/UZ** no topo
  dos pilares (deslocamento horizontal), cada um com o seu limite;
* tensão de von Mises (ou limite superior) por grupo de barras (pilares, vigas, contraventamento) e
  nas chapas de ligação modeladas como casca/sólido;
* fator de segurança mínimo do modelo.

Um sensor num vértice dá um valor com sinal e linear: a superposição fecha exatamente.
