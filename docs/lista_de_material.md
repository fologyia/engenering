# Lista de material — massa, peso e pintura para o orçamento

A página **Lista de material** (`app_pages/lista_de_material.py`, núcleo em
`core/lista_de_material.py`) guarda no projeto (`projeto["lista_de_material"]`) os itens da
estrutura e dá a massa, o peso, a área de pintura e as barras comerciais de cada perfil — para o
orçamento — e confere o peso com o caso PP do modelo. É ferramenta de gestão: **não vai para o
memorial**.

## Itens

| Tipo | Massa | Pintura |
| --- | --- | --- |
| Perfil | quantidade × comprimento × kg/m do catálogo (ou o kg/m informado, fora do catálogo) | contorno da seção × comprimento |
| Chapa | comprimento × largura × espessura × 7 850 kg/m³ | as duas faces |
| Grade / piso | comprimento × largura × kg/m² do fabricante | não entra (galvanizada) |
| Outro | kg por unidade (chumbadores, parafusos, equipamentos) | não entra |

**Perfil pela descrição** (`perfil_conhecido`): o nome do catálogo (`W 200 x 35,9 (H)`), o nome do
SolidWorks (`W8X31`, `C8X13.75`, `L2X2X1/4`, `L 2 1/2 x 2 1/2 x 1/4` — o mesmo
`perfil_do_nome` dos Esforços do modelo, com as frações convertidas) ou as medidas em mm
(`TUBO QUADRADO 50 X 50 X 3`, `TUBO REDONDO 60,3 X 3,6`, `BARRA REDONDA 16`,
`CANTONEIRA 50 X 50 X 5`), com a área calculada da seção.

**Contorno de pintura** por família: I, W, HP e U = 2d + 4b − 2t_w (faces de fora e de dentro das
mesas e da alma); T = 2d + 2b; tubos e barras = perímetro externo; cantoneira = 4b; C enrijecido =
2(d + 2b + 2c).

## Resumo (`resumir`)

Massa dos itens, **acréscimo** de ligações, parafusos e soldas (5 % por padrão), massa total, peso
(kN), área de pintura, massa por tipo, **por perfil** (peças, comprimento total, kg/m, massa e barras
comerciais = comprimento total ÷ barra de 6 ou 12 m, arredondado para cima, sem otimização de corte)
e **chapas por espessura**. Itens sem dado (comprimento, medidas, kg/m) ficam pendentes e não somam.

## Lista de corte do SolidWorks (`ler_lista_de_corte`)

O menu da pasta "Lista de corte" na árvore da peça não exporta, e a tabela de lista de corte de um
desenho pode sair vazia. Por isso a página oferece a **macro do SolidWorks**
`macros_solidworks/exportar_lista_de_corte.bas` (botão "Macro do SolidWorks",
`macro_da_lista_de_corte`):

* lê a lista de corte direto da árvore da peça aberta (atualiza a lista, percorre as pastas
  `CutListFolder`), sem desenho nem tabela;
* grava `<peça>_lista_de_corte.csv` na pasta da peça, com ITEM, QTD. (corpos da pasta), DESCRICAO (o
  nome do item sem o `<n>`; se o nome for automático, "Item da lista de corte1", a propriedade de
  descrição), COMPRIMENTO (a propriedade LENGTH/COMPRIMENTO com a unidade do documento), o nome do
  item, VOLUME POR PECA (cm3) e MASSA DO ACO POR PECA (kg) — o volume médio dos corpos da pasta
  (`Body2.GetMassProperties`) × 7 850 kg/m³ — e todas as propriedades da lista de corte;
* a leitura ignora os itens sem corpo (quantidade 0, sobras de alterações no modelo, com o LENGTH sem
  resolver) e avisa quantos foram; o item que o catálogo não conhece (perfil de outra biblioteca,
  corpo com nome automático) entra com a **massa da geometria** — como perfil, se tiver
  comprimento, ou como "Outro" — e o aviso pede para conferir o material;
* texto ASCII, para colar no editor sem problema de acento: Ferramentas › Macro › Nova (nome e
  salvar), apagar o texto do editor, colar e F5; depois, Ferramentas › Macro › Executar.

Também serve o CSV da tabela de lista de corte de um desenho (botão direito na tabela › Salvar como ›
CSV). Excel `.xlsx` também; o `.xls` antigo é recusado com a orientação de salvar em CSV. O programa:

* lê CSV (UTF-8 ou cp1252; separador `;`, `,` ou tabulação) ou a primeira planilha do Excel;
* acha o cabeçalho nas 30 primeiras linhas: coluna de **quantidade** (QTD., Qty., Quantidade) e de
  **descrição** (DESCRIÇÃO > PERFIL > MATERIAL, nesta preferência); comprimento (COMPRIMENTO, Length)
  e marca (Nº DO ITEM, Item, Marca, Posição) quando houver;
* números em português ou inglês (`1.234,5`, `1234.5`, `6.000` mm), com unidade na célula (`mm`,
  `cm`, `m`, `in`, `ft`) ou no cabeçalho (`(m)`); sem unidade vale a escolhida na página (mm por
  padrão);
* descrição começando com CHAPA, PLACA, PL ou CH vira chapa (a espessura sai do número; a largura se
  completa na tabela); as demais são perfis, e as fora do catálogo pedem o kg/m.

## Placas de base

**Incluir as placas de base** (`com_placas_de_base`) acrescenta uma linha de chapa com a placa
gravada em Esforços do modelo (seção 9) × número de pilares; repetir troca a linha, não duplica.

## Conferência com o modelo (`conferir_com_o_modelo`)

O peso dos itens **sem o acréscimo** contra a reação vertical do caso **PP** importado em Esforços do
modelo (nos eixos do plano, Z para cima). Quando todos os itens têm a massa da geometria (macro), vale
ela — é o peso que a gravidade do modelo enxerga; senão, a massa da lista. Até 5 % de diferença: bate.
Acima, o aviso diz o sentido — modelo mais leve (barra faltando no modelo, peso próprio fora de alguma
peça, placas e grades que o modelo não tem) ou mais pesado (lista incompleta, ou o caso PP com outras
cargas). Razão perto de 10 ou de 1 000 sugere unidade trocada: a gravidade (9,81 m/s²) ou a densidade
(7 850 kg/m³) do estudo.

A massa da geometria fica em cada item (`massa_geometria_kg`, coluna só de leitura "Pela geometria
(kg/peça)" na tabela da página) e entra no resumo e no Excel quando todos os itens a têm.

## Saídas

Excel (`xlsx_da_lista`: Resumo, Itens, Por perfil, Chapas) e CSV dos itens (ponto e vírgula,
vírgula decimal).

## Testes

`tests/test_lista_de_material.py` (perfis por nome e por medida, contorno de pintura, massa de cada
tipo, pendências, resumo, números, listas de corte em português, em inglês e em Excel, conferência
com o PP, placas de base, ida e volta pelo projeto e pela tabela da página, Excel e CSV) e
`tests/test_lista_de_material_pagina.py`.
