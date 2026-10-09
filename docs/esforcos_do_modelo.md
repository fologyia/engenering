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
* **PP sem cargas no plano**: o peso do modelo (kN e kg).
* Casos do plano ainda sem esforços e casos importados fora do plano são avisados.

## Pior caso de cada barra (`envoltoria`)

As combinações são as do plano (só com os casos importados), nos estados-limite escolhidos (ELU
normal por padrão). Para cada barra: a maior compressão e a maior tração (com a combinação e o
ponto), o maior momento forte com o N da mesma combinação e ponto (para a interação N + M), o maior
momento fraco, cortante (resultante de V1 e V2) e torque. CSV com ponto e vírgula.

## Próximas etapas

1. Verificação automática de cada barra (perfil, aço, comprimento de flambagem, B₂) com os módulos de
   barras e flambagem, registro e capítulo no memorial.
2. Quadro de cargas para as fundações (critério Anglo 5.9: ações sem combinar nem majorar) a partir
   das reações de cada apoio.

## Testes

`tests/test_esforcos_modelo.py` (leitura com arquivos no formato do SolidWorks gerados por
`tests/dados_solidworks.py` a partir do pórtico do mini exemplo, conferência, envoltória ponto a
ponto contra a conta à mão, malhas diferentes) e `tests/test_esforcos_modelo_pagina.py`.
