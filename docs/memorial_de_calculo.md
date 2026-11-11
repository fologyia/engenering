# Memorial de cálculo — o que passou e o que não passou

O memorial é um **molde de cálculo**: os cálculos registrados entram completos e o que o programa não
sabe sai como `[a preencher]`. Como o documento costuma ser **incluído em outro**, ele traz só o que
quem lê precisa: o resultado de cada análise, o que passou e, no fim, o que não passou.

## Capítulo de uma análise com tabela de verificações

Vale para a **flambagem de colunas** e as **ligações parafusadas** (qualquer registro com
`resultados["verificações"]`). Os outros módulos seguem o capítulo de sempre.

| Ordem | Bloco | O que mostra |
| --- | --- | --- |
| 1 | **Resultado** (caixa em destaque) | `ATENDE`, `NÃO ATENDE`, `ATENÇÃO` ou `NÃO AVALIADO`; quantas verificações passaram e quantas não; a de maior aproveitamento; o dado-chave do módulo (N_c,Rd na coluna; o menor parafuso que atende na ligação). A palavra do resultado está no texto, então o documento impresso em preto e branco continua legível. |
| 2 | Identificação | Módulo, peça, situação registrada e quando foi registrado. |
| 3 | **Dados de entrada** | Os dados que importam, em quatro colunas e com rótulos e unidades legíveis; o que não foi preenchido (excentricidade zero, mão-francesa ausente…) não aparece. Um dado que o módulo passe a registrar e o mapa ainda não conheça aparece mesmo assim, com rótulo automático. |
| 4 | Método, premissas e critérios | Uma vez só: as análises seguintes com a mesma base dizem "os mesmos do item 8.1.1". |
| 5 | Figuras | Os desenhos que a página mostra (ver "Figuras das páginas no memorial"). |
| 6 | **O que passou** | Uma linha por verificação aprovada: solicitante, resistente, aproveitamento e, sob o nome, o cálculo com a referência. |
| 7 | Valores de apoio | Grandezas informativas (N_e de cada modo, λ, χ, B₁…), sem critério de aceitação; esbeltez local das paredes; outros resultados que o módulo registre. |
| 8 | **Não passou** — sempre o fim | As verificações reprovadas, com o cálculo que explica o motivo; as que pedem **atenção** (passaram com ressalva); as **não avaliadas**; e o que o módulo manda **conferir antes de emitir**. Se nada reprovou, a declaração "Não passou: nenhuma." |

Nenhuma linha da tabela do módulo some: cada verificação aparece uma vez, na tabela do seu status
(`OK` → O que passou; `NÃO OK` e `ALERTA` → Não passou; `INFO` → Valores de apoio; `N/A` → Não
avaliadas). Os números saem em português: o ponto decimal das fórmulas vira vírgula, sem mexer em
números de item ("5.3.2") nem em siglas ("Tab. A.3").

## Capítulo de um cálculo sem tabela de verificações

Vale para os registros que guardam um texto de destaque ou tabelas próprias
(`resultados["destaque_memorial"]`, `resultados["tabelas_memorial"]`) mas não fecham numa tabela de
verificações — hoje, o **Vento em estruturas abertas** (forças por nível, por pórtico e nos nós). O
capítulo segue o mesmo roteiro, sem as seções de passou e não passou:

| Ordem | Bloco | O que mostra |
| --- | --- | --- |
| 1 | **Resultado do cálculo** (caixa em destaque) | O texto que o módulo guardou (forças totais, momentos na base, q no topo). |
| 2 | Identificação | Módulo, peça, situação registrada e quando foi registrado. |
| 3 | **Dados de entrada** | Os mesmos rótulos legíveis do capítulo de verificações. |
| 4 | Método, premissas e critérios | Método, premissas, referências e equações. |
| 5 | Tabelas do módulo | As tabelas prontas que o módulo registrou. |
| 6 | Conferir antes de emitir | Os alertas do registro (os conflitos da base técnica, por exemplo). |

Os demais módulos sem tabela continuam com o capítulo de sempre (`core/memorial_verificacoes.py`,
`capitulo_de_calculo`).

## Figuras das páginas no memorial

O registro guarda o que é preciso para desenhar de novo, e o memorial (Word e PDF) desenha na hora
de emitir (`core/record_charts.py`, `imagens_gravadas`). As figuras entram no capítulo do cálculo,
depois do método:

| Página | Figuras no memorial | Como o registro guarda |
| --- | --- | --- |
| Flambagem de colunas | Curva de flambagem, a seção (com o giro escolhido) e a coluna em pé | `figura_coluna`: a seção e a coluna (`core/desenho_da_coluna.py`) |
| Pilares do modelo | O pilar de maior aproveitamento em pé, com os travamentos do esqueleto | `figura_coluna`, sem a seção |
| Projeto de parafusos | Planta e corte da ligação, com a força em cada parafuso | `figura_parafusos`: a entrada; a ligação é refeita |
| Contraventamento | Planta das linhas contraventadas e a elevação da linha mais carregada em X e em Y | `figuras_2d`: o desenho pronto (`core/desenho_contraventamento.py`) |
| Vigas de piso | A viga com as cargas, a deformada e as reações | `figuras_2d` (`core/desenho_viga_de_piso.py`) |
| Vigas e eixos | O esquema do modelo antes dos diagramas | O texto do modelo (já era assim) |
| Cálculo de peças e Desenhar seção | As figuras do caso (seção, viga, grupo de parafusos, pino…) | `figuras_do_caso`: o caso e os valores; a conta é refeita |
| Modelo em 3D, vento, escada, ligações, placas de base, reações, sensores | Como antes | `figura_3d`, `figuras_3d`, `figuras_portico`… |

* Página e memorial usam o **mesmo desenho**: a planta do contraventamento e a viga de piso saem de
  um `Desenho2D` do núcleo, que a página mostra em SVG e o memorial em PNG.
* Quando a figura depende de **refazer a conta** (parafusos e casos do Cálculo de peças), o memorial
  confere o resultado de agora com o registrado (o aproveitamento na ligação, o resumo no caso). Se não
  bater, a figura sai e o capítulo diz por quê: o cálculo mudou desde o registro e precisa ser
  registrado de novo. A figura nunca mostra números diferentes da tabela ao lado.
* Dado estragado ou que o JSON não guarda (infinito) deixa o registro **sem a figura**; o registro e o
  memorial continuam saindo.
* As chaves que só guardam dados para desenhar (`record_charts.CHAVES_DE_FIGURA`) nunca aparecem como
  texto, nem no capítulo de sempre.
* Registros feitos antes desta versão não têm os dados: registre de novo na página para a figura
  entrar.

Ainda sem figura no memorial: a Ligação de contraventamento (o desenho da chapa de nó é só da página) e
a planta das reações por caso (o memorial já leva os eixos e o 3D com as reações).

## Vários cálculos no mesmo projeto

* Cada análise é um capítulo, agrupado pela peça do escopo físico.
* O **quadro-resumo** conta, por análise, o que passou, o que não passou, o aproveitamento máximo e a
  situação.
* O **resumo executivo** ganha a linha "Não passou" com as análises reprovadas.
* A **conclusão** traz uma linha por análise e a tabela "O que não passou, por cálculo", com todas as
  verificações reprovadas do projeto — o que o responsável precisa tratar, sem abrir cada capítulo.
* Análises de mesmo título ganham "(cálculo 1 de 2)", e as de outros módulos (estática, fadiga, vigas…)
  continuam com o capítulo de sempre.

## Juntar o projeto num documento (`core/memorial_do_projeto.py`)

No Memorial de cálculo, o quadro **Juntar o projeto num documento** mostra, etapa por etapa
(cargas, vento, contraventamento, barras, sensores, pilares, vigas, escadas, ligações, placas de
base, fundações, modelo em 3D), o que cada página registrou e o que falta (num projeto com o modelo
do SolidWorks, as etapas do modelo sem registro aparecem com o link da página). O botão **Juntar**:

* deixa **um de cada** cálculo: nas páginas do modelo inteiro (Esforços do modelo — barras, placas,
  quadro das fundações —, Pilares do modelo, Reações nas bases, Cargas do esqueleto, Sensores), o
  registro novo do mesmo tipo substitui o anterior; nas outras, só a cópia idêntica (mesmo título,
  peça, entradas e resultados) — duas colunas diferentes com o mesmo título continuam as duas;
* marca os repetidos como **Superado** (ficam no histórico, saem do memorial);
* grava a composição do memorial na **ordem do projeto**, e o Emitir agora já sai assim. Sem juntar,
  o padrão também já é um de cada, na ordem do projeto.

## Para incluir em outro documento

O perfil **Para incluir em outro documento** (Memorial de cálculo) gera só os capítulos
numerados a partir de 1 — quadro-resumo, memória de cálculo, vigas, sensibilidade e conclusão —, sem
capa, resumo executivo, controle de revisões nem aprovações, com uma linha de identificação no topo.
No Word os títulos são `Título 1/2/3` e as tabelas são tabelas comuns: ao copiar para o documento de
destino, assumem o estilo dele. As tabelas medem 16,5 cm (a largura útil da página do memorial); se o
documento de destino tiver margens maiores, selecione as tabelas e use *Layout da Tabela → Ajustar
Automaticamente → Janela*.

## Para quem estende o memorial

Uma seção do modelo pode trazer `blocos`, uma lista ordenada (`paragrafo`, `subtitulo`, `destaque`,
`nota`, `bullets`, `passos`, `formula`, `imagem`, `tabela`) que Word e PDF desenham na ordem dada;
sem ela vale a ordem histórica das chaves soltas (`paragrafos`, `tabelas`…). Uma célula de tabela pode
ser `(principal, detalhe)`, e uma tabela aceita `tom` (`ok`, `erro`, `atencao`) para colorir o cabeçalho.
Os tipos e a paleta estão em `core/memorial_blocos.py`; o capítulo de verificações, em
`core/memorial_verificacoes.py`.
