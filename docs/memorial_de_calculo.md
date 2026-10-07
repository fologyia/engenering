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
| 5 | Figura | A curva de flambagem, quando existe. |
| 6 | **O que passou** | Uma linha por verificação aprovada: solicitante, resistente, aproveitamento e, sob o nome, o cálculo com a referência. |
| 7 | Valores de apoio | Grandezas informativas (N_e de cada modo, λ, χ, B₁…), sem critério de aceitação; esbeltez local das paredes; outros resultados que o módulo registre. |
| 8 | **Não passou** — sempre o fim | As verificações reprovadas, com o cálculo que explica o motivo; as que pedem **atenção** (passaram com ressalva); as **não avaliadas**; e o que o módulo manda **conferir antes de emitir**. Se nada reprovou, a declaração "Não passou: nenhuma." |

Nenhuma linha da tabela do módulo some: cada verificação aparece uma vez, na tabela do seu status
(`OK` → O que passou; `NÃO OK` e `ALERTA` → Não passou; `INFO` → Valores de apoio; `N/A` → Não
avaliadas). Os números saem em português: o ponto decimal das fórmulas vira vírgula, sem mexer em
números de item ("5.3.2") nem em siglas ("Tab. A.3").

## Vários cálculos no mesmo projeto

* Cada análise é um capítulo, agrupado pela peça do escopo físico.
* O **quadro-resumo** conta, por análise, o que passou, o que não passou, o aproveitamento máximo e a
  situação.
* O **resumo executivo** ganha a linha "Não passou" com as análises reprovadas.
* A **conclusão** traz uma linha por análise e a tabela "O que não passou, por cálculo", com todas as
  verificações reprovadas do projeto — o que o responsável precisa tratar, sem abrir cada capítulo.
* Análises de mesmo título ganham "(cálculo 1 de 2)", e as de outros módulos (estática, fadiga, vigas…)
  continuam com o capítulo de sempre.

## Para incluir em outro documento

O perfil **Para incluir em outro documento** (Central de relatórios) gera só os capítulos
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
