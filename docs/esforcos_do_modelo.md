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
| Listar tensões da viga | Para cada viga, as tensões nas pontas de cada elemento: axial, flexão nas direções 1 e 2, torção e o pior cenário (N/m²) | A maior tensão (referência) e a seção que o Simulation usou em cada barra (`conferir_tensoes`) |

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
* **Eixo forte**: na importação, o momento que domina (nos perfis em U de piso, o Momento 2). Com
  o perfil e o esqueleto, a **seção** decide (`ld.eixo_forte_pela_secao`): o Simulation põe a
  direção 1 na aresta reta mais longa da seção; ao longo da alma, o M₂ é o do eixo forte; ao longo
  da mesa, o M₁. A direção 1 vem medida pela macro v6 (comparada com a direção da alma) ou, sem
  dúvida, do catálogo (alma reta com um raio generoso contra a mesa; U pelas costas da alma; T;
  tubo retangular). No modelo real, a regra antiga trocava os pilares W 200 × 31,3 — no PP, o M₁
  dominava, mas é o do eixo fraco (S₁ = 61,2 cm³ = W_y no próprio Simulation).

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

## Antes de verificar (`core/diagnostico_do_modelo.py`)

Logo depois do envio dos arquivos, a página junta todas as conferências num painel, do mais grave ao
menos, cada problema num cartão com **o que está errado** e **como corrigir** (passo a passo, em
linguagem simples), e o que já confere embaixo:

- **Forças que não são do caso** — o erro mais comum: salvar o "Listar forças da viga" sem trocar o
  caso no gerenciador. O programa confere o arquivo de forças de cada caso de quatro jeitos, todos
  independentes da orientação da seção, e diz de que caso os números são quando dá:
  - *mesmo arquivo em dois casos* (os mesmos números, reações diferentes): o caso cujas outras
    conferências fecham é o dono; o outro foi salvo errado;
  - *vertical*: a compressão nas bases dos pilares contra a reação vertical — se bate com a reação de
    outro caso, diz qual; com a soma de todos, foi salvo com o estudo base (o PP-forcas, 24/10);
  - *pé de cada pilar*: a compressão e a cortante na base de cada pilar contra a reação no pé dele (o
    -apoios.csv da macro; com o esqueleto, cada pilar no seu apoio, desde que só ele chegue ali; sem o
    esqueleto, os conjuntos de tamanhos). Batendo com os apoios de outro caso, diz qual. Sem o pé de
    cada pilar, um vento e o do lado oposto (W0 × W180) têm as mesmas forças em tamanho: o espelho
    não conta como prova (falso alarme visto no banco real, 26/10);
  - *tombamento*: com o esqueleto, o lado comprimido mostra para onde as forças empurram
    (Σ N·posição do pé); contra a reação do caso, acha forças de vento com a direção de outro caso;
  - *cortante*: os pilares não levam menos que a reação horizontal quando todos os apoios são pés de
    pilar (confirmado pelos apoios da macro → erro; sem eles → para conferir, pode haver travamento
    na estrutura existente). Com a direção pelo tombamento, diz se é a mesma direção com outro valor
    — o W270 do usuário (26/10): vento em −Z com 1,82 kN em vez de 2,18 kN, de uma rodada anterior.
- **Plano com cargas de exemplo** — linhas da grade de eixos ("N1 · eixo A…") que o modelo não tem:
  botão **Tirar do plano as cargas da grade**.
- **Ventos com os nomes trocados** — cada caso do estudo é, em direção e valor, um caso do programa
  (`em.mapa_de_nomes_dos_ventos`): botão **Trocar os nomes no programa** (forças, reações e apoios,
  `em.trocar_codigos`/`am.trocar_codigos`); se há direção de um com valor de outro, pede a correção no
  SolidWorks com a regra da vista Superior.
- **Forças de outra rodada** — o arquivo de forças de um caso tem outra numeração de elementos que a
  maioria (rodada anterior): diz qual caso listar de novo. Os avisos "combinei pela ordem" de cada barra
  viram uma linha só nas seções 5 e 7 (`em.agrupar_avisos`).
- **Plano × modelo** em casos sem vento, com a pista quando a diferença é exatamente uma linha do plano
  (um guarda-corpo numa borda que no modelo é o acesso).
- **Apoios de outra rodada ou sem posição**, **falta o arquivo de reações**, **casos do plano sem
  resultado** (informação) e os erros do estudo (majorado, eixo vertical, sem fixação).
- **Os problemas da leitura do modelo** (`ld.diagnosticar`: gravidade esquecida num caso, PP mais
  pesado que o aço, eixo forte trocado, pontas soltas, B₂…), os de corrigir e os de conferir, com o
  passo a passo dos mais comuns; a seção 3 fica com os informativos e diz quais foram para o painel.
  O que outra conferência do painel já disse não se repete (eixo vertical, malha, estudo sem carga).

Robustez: cada conferência roda separada (`_protegido`). Uma que falhe com um dado fora do esperado
vira um cartão "Não deu para conferir", com a referência da ocorrência, e as outras rodam; enquanto
isso, o painel não diz "Tudo confere".

Macro **v16** (`exportar_casos_de_carga`): com as vigas selecionadas na árvore do estudo do Simulation,
lê as forças de cada viga pela seleção, como o exemplo oficial da API ("Get Forces and Stresses for
Selected Beams"), e grava os -forcas junto com os -reacoes e -apoios; se duas vigas derem os mesmos
números, não grava e diz para listar à mão. A v14 trocava a pasta de resultados para consertar uma
pasta presa e o SOLIDWORKS travou: desde a v15 a macro não muda mais a pasta (só avisa).

### Direção de cada vento (`diagnostico_do_vento`, `resumo_dos_ventos`)

Caso de vento que não equilibra o plano: em vez de "falta ou sobra carga", o programa diz para onde
o caso do estudo empurrou (a reação com o sinal trocado, nos eixos do SolidWorks: o +Y da planta é o
−Z com o Y para cima) e com que caso do plano ele bate — mesma direção e valor de outro caso (nomes
trocados: renomear basta), direção de um caso com o valor do próprio (plano de referência ou sentido
da força errados no SolidWorks), sentido oposto, ou só o valor diferente. Um resumo lado a lado
("no seu estudo" × "no programa") diz se dá para só renomear ou se as forças precisam ser corrigidas
— o valor do vento depende da direção (a face que ele vê). Caso do usuário (24/10, teste01): W90 em
+Z, W180 em −Z com 1,82 kN e W270 em −X com 2,18 kN, contra W90 −Z, W180 −X e W270 +Z do programa.
O PP mostra também o aço sem o acréscimo de ligações (320 kg com g = 9,81 → 299 kg de aço).

## Leitura do modelo (`core/leitura_do_modelo.py`)

Os arquivos dizem números; a leitura do modelo diz o que eles significam e o que parece errado.
Aparece na página em "O que o programa entendeu do modelo" (passo 3), nas colunas sugeridas da
tabela das barras (passo 4) e nos avisos da hora de enviar (passo 1).

**Esqueleto do modelo.** A macro do SolidWorks (`macros_solidworks/exportar_lista_de_corte.bas`)
grava, além da lista de corte, o `<peça>_esqueleto.csv`: quatro linhas de cabeçalho (MACRO com a
versão, PECA, CONFIGURACAO, DATA) e um corpo por linha, com o item da lista de corte, a descrição, a
**forma** (BARRA, CHAPA ou BLOCO), as pontas da linha de centro (X1…Z2, mm, nos eixos da peça), o
comprimento, as duas medidas da seção (SECAO A e B, mm) e o volume (cm³); desde a v5, a direção da
medida maior da seção (a alma) e o contorno das chapas; na **v6**, a **direção 1 do Simulation** de
cada barra (a face plana ao longo da barra mais larga = a aresta reta mais longa da seção, com a folga
para a segunda; ver `docs/modelo_3d.md`). Como a macro (v4) mede:
as direções principais da nuvem de pontos do corpo (vértices e centros das arestas circulares — um
tubo redondo não tem vértice), pelo método de Jacobi; as medidas, pelos pontos extremos do corpo
nessas direções (caixa orientada: uma chapa inclinada sai com comprimento × largura × espessura); a
linha de centro passa pelo centro de massa. Conferido com corpos sintéticos (perfil I inclinado em
3D, U em diagonal de planta com o centroide fora do meio, tubo redondo inclinado, chapa a 37°,
cantoneira com meia-esquadria): pontas certas a menos de 2 mm. Chapa é o corpo muito fino para a
largura (≤ 10 %, até 6 vezes mais comprido que largo); barra, o que tem pelo menos 2 vezes a maior
medida da seção. Os números saem sempre com vírgula decimal, qualquer que seja a configuração
regional do Windows. A macro trata os erros (diz a etapa e o motivo — arquivo aberto no Excel, pasta
sem permissão —, fecha os arquivos, inclusive os de uma execução interrompida), deixa de fora e
lista no fim um corpo cuja geometria não pode ser lida, exporta os corpos fora da lista de corte e,
numa peça que não é de soldagens, ainda grava o esqueleto.

A leitura (`ler_esqueleto`) acha a linha das colunas depois do cabeçalho, e o que dá para ler com
ressalva vira aviso, não erro: arquivo de versão antiga da macro (sem a forma: lê e pede a nova),
versão diferente da esperada, linhas sem coordenadas puladas, corpo repetido (fica o primeiro),
coordenadas acima de 10 km (não está em mm?), corpos sem volume. Chapas e blocos não entram na
procura de pontas soltas; o perfil sugerido diz a seção medida no modelo. A página mostra a peça, a
configuração, a data e as formas. Envia-se no passo 1 junto com os CSV do Simulation (`tipo_do_arquivo`
reconhece pelo cabeçalho; a lista de corte enviada aqui é recusada com a orientação de ir à Lista
de material, e o esqueleto enviado lá, o contrário). A viga do Simulation `Viga-12(<corpo>)` acha o
seu corpo pelo nome entre parênteses (`corpo_da_viga`, com espaços e acentos tolerados). Com ele:

* **Tipo pela posição** (`tipo_pela_geometria`): até ~14° do prumo é pilar; horizontal alinhada a
  um eixo em planta (~10°) é viga; horizontal diagonal em planta é contraventamento do piso;
  inclinada é contraventamento — ou viga inclinada (banzo de escada) se a cortante passa de 10 % da
  normal.
* **Esqueleto × peso próprio**: a inclinação do corpo tem de bater (± 10°) com a que o PP mostra
  (abaixo); se não bate, o corpo não é o da viga (esqueleto de outra versão) ou a gravidade não está
  na vertical.
* **Comprimento** de cada barra → comprimentos de flambagem iniciais (K = 1).
* **Perfil do modelo** (`_perfil`): a descrição ou o item da lista de corte, conferido pela área
  real da seção (volume ÷ comprimento, `lm.secao_pela_area`) — "W8x31" com a seção do W 200 × 35,9
  vira o W 200 × 35,9. Vale também para as barras "Aparar/Estender", cujo nome não diz o perfil.
* **Pontas que não encostam** (`pontas_soltas_pela_geometria`): ponta a mais de 0,30 m de qualquer
  outra barra e fora do nível mais baixo (apoio).
* **Peso próprio**: a reação do PP tem de ficar entre o aço das barras do estudo e o de todos os
  corpos (volume × 7 850 kg/m³, × o fator das ligações não modeladas do plano), a ± 5 %. Acima é
  erro (γ vezes: estudo majorado; mais: o PP levou outras cargas); abaixo é aviso (corpo sem
  material, alumínio, densidade errada, ou a gravidade do PP sem o fator das ligações). Com o
  esqueleto, esta conferência substitui a da Lista de material.

**Barra a barra, pelos esforços** (`ler_barras`, com ou sem esqueleto):

* **Pontas** (`classificar_pontas`, primeira e última da lista em todos os casos): **solta** (força
  e momento ≈ 0 em todos os casos — a junta que faltou, ou um balanço), **articulada** (momento até
  2 % do máximo da barra), **rígida**, ou **sem esforço** (a barra inteira).
* **Inclinação pelo peso próprio** (`variacao_no_pp`, `inclinacao_pelo_peso`): dentro de um
  elemento só uma carga distribuída ao longo da barra muda N e V — as barras que chegam nos nós
  mudam os esforços *entre* elementos, não dentro deles. No PP essa carga é o peso próprio: a parte
  ao longo do eixo muda N, a transversal muda V. Somando os ΔN e ΔV dos elementos, `atan2(ΔN, ΔV)`
  é a inclinação da barra com a horizontal e `hypot(ΔN, ΔV)` a carga distribuída total. No modelo
  real conferido: pilares 90°, vigas 0°, diagonais 45°, banzos da escada 34° a 37°. (A regra antiga,
  "normal que muda ao longo da barra = pilar", chamava de pilar as vigas de piso de um pórtico 3D,
  cuja normal muda onde chegam as secundárias.)
* **Tipo sem o esqueleto** (`tipo_pelos_esforcos`): pela inclinação do peso próprio — ≥ 76° pilar;
  ≤ 2° viga (contraventamento do piso se só trabalha à força normal); entre os dois,
  contraventamento ou viga inclinada, conforme a flexão. Sem esse sinal (PP sem peso nas barras):
  só força normal → contraventamento; nos casos só verticais, comprimida com N > 2 V → pilar,
  V > 2 N → viga; senão fica "—".
* **Malha grossa**: viga com número ímpar e pequeno (< 7) de elementos não tem nó no meio do vão; o
  momento de uma carga distribuída pode sair até 100/n² % abaixo do real.

**O conjunto** (`diagnosticar`, do mais grave ao informativo): valores fora de escala (> 10⁵ kN ou
kN·m: unidade); eixo vertical trocado (o peso do PP aparece em outro eixo); estudo sem carga; dois
casos com o mesmo resultado (arquivo repetido ou estudo duplicado sem trocar as cargas); estudo que
ficou com a gravidade (reação vertical − cargas do plano = o peso do PP, ± 3 %); barras que faltam
num caso (o modelo mudou); malha diferente entre os estudos; peso próprio × esqueleto; **carga além
do peso próprio no PP** (com o esqueleto: a carga distribuída que o PP mostra em cada barra, em
kN/m, contra o peso dela pelo volume × o fator das ligações — acima de 15 % + 0,05 kN/m é erro: há
carga por metro no estudo PP; sem o esqueleto, com a Lista de material: a carga que o PP leva ao
longo de todas as barras não pode passar do aço inteiro, e o aviso aponta as barras que mais
recebem); **caminho do peso no PP** (informação: quanto do PP chega ao longo
das barras e quanto pelos nós — chapas, sólidos, forças concentradas; num esqueleto puro, quase
tudo vem ao longo das barras); pontas
soltas; barras sem esforço; malha grossa; tipo da tabela diferente da posição no esqueleto
(contraventamento e diagonal são o mesmo papel); **segunda ordem global**: o estudo do SolidWorks é
linear, de 1ª ordem — com pilares e B₂ = 1,00, aviso (sem contraventamento: o pórtico costuma ser de
média ou grande deslocabilidade) ou informação (com contraventamento: só vale para pequena
deslocabilidade), com o lembrete das imperfeições iniciais (força nocional de 0,3 %); vigas
engastadas nas duas pontas (informação: as juntas do SolidWorks são rígidas — articule se a ligação
real só transmite cortante; num pórtico sem contraventamento é ela que dá a estabilidade e tem de
ser detalhada como rígida); perfil da tabela diferente da seção do modelo (os esforços saíram da
seção do modelo); barras sem corpo no esqueleto (esqueleto de outra versão). Sem nada disso, "Nada
de estranho".

**Na hora de enviar** (`avisos_da_importacao`): dois arquivos de forças ou de reações no mesmo caso
são **erro e bloqueiam a gravação**; nome do estudo que indica outro caso, forças e reações de
estudos diferentes são aviso; forças sem as reações, informação.

**Perfil de cada corpo** (`perfil_do_corpo`, `perfis_do_esqueleto`). Corpo a corpo, entre os
perfis da família do item da lista de corte: a área da seção (volume ÷ comprimento) só pode ser
menor que a do perfil (o corte nas pontas tira volume, no máximo duas alturas de seção sobre o
comprimento, até 60 %); o perfil tem de caber na seção medida (`cabe_na_secao`: um L 2" não chega
aos 91,8 mm de um L 2½" medido nos eixos principais) e, numa barra comprida, a caixa não pode ser
menor que a seção (I, U, W, H: altura × aba — um corpo com aba de 57,4 mm não é U 8" x 20,50). Entre
os que passam, nesta ordem: a peça reta (caixa e área exatas do perfil, ± 2,5 % e ± 3 %), as peças
retas do mesmo membro (o nome antes do [n]: as cortadas seguem as retas do membro), o nome do
corpo (U 8"x17,1), o item da lista de corte; sem nenhum, o mais leve que cobre a área. A caixa
sozinha engana (um 17,1 cortado a 45° chega à aba de 59,5 mm do 20,5) e o nome também (o modelo
já teve membros chamados "U 8"x17,1" desenhados com o C8x13.75): a geometria vem antes. Quando o
mesmo item da lista de corte sai com perfis diferentes, o esqueleto avisa e diz quais corpos — no
modelo real, os dois banzos da escada que ficaram com o perfil antigo (U 8" x 20,50) depois da troca
dos outros 24 corpos para o U 8" x 17,10. Numa peça curta (BLOCO), a maior medida pode ser a da
seção: a direção vem do peso próprio, e a caixa não entra na conferência. Perfil de mesmo nome
com volume por metro diferente (peças longas, ± 30 %) também vira aviso do esqueleto. A Lista de
material faz o mesmo item a item: o perfil adotado pelas peças retas de um nome do SolidWorks não
vale para o item com a seção maior que a dele (fica o do nome).

**Tensões da viga** (`em.TIPO_TENSOES_VIGA`, `conferir_tensoes`). O "Listar tensões da viga" tem o
mesmo cabeçalho do "Listar forças da viga", mas em tensão (N/m², MPa, psi…) — reconhecido pela
unidade da coluna Axial; as tensões das duas pontas já vêm com o sinal (compressão negativa), sem
inverter. Não vai para o projeto: mostra a maior tensão normal (pior cenário) como referência
(acima de 250 MPa, aviso de que a barra não vai atender) e, com as forças do mesmo estudo (enviadas
junto ou já no projeto), a área que o Simulation usou em cada barra = |N| ÷ |σ axial|, ponta a ponta
(`area_no_simulation`, a mediana). Comparada com o perfil da tabela (ou o sugerido pelo esqueleto):
mais de 5 % de diferença é aviso. No modelo real, a seção nominal apareceu em todas as barras (U 8":
25,9 cm²; pilares: 40,4 cm² do W 200 x 31,3), menos numa peça de 340 mm com cortes a 53°/37°, em
que o Simulation tomou 14,8 cm² — a seção errada.
Também o **módulo resistente** de cada direção (`modulos_no_simulation`): S₁ = |M₁| ÷ |σ flexão 1| e
S₂ = |M₂| ÷ |σ flexão 2|. O maior (pelo menos 1,5 vez o outro) é o do eixo forte, pelo próprio
Simulation: diferente da coluna Eixo forte da tabela é **erro** ("eixo forte trocado (pelas
tensões)"); igual, conferido. O S do eixo forte contra o W_x do perfil (mais de 10 % é aviso: a
seção do modelo não é a da tabela). No modelo real: pilares S₁ = 61,2 e S₂ = 301,9 cm³ (W_y e W_x
do W 200 × 31,3), vigas U 8" S₂ = 147,5 cm³.

**Corpos renomeados depois do estudo** (`correspondencia`). O Simulation guarda o nome do corpo de
quando a malha foi feita; renomeado o membro estrutural depois ("Canal c C8X13.75(1)" → "U 8"x17,1 -
Plataforma"), o nome não casa mais. O membro mantém a numeração `[n]` dos corpos: cada grupo antigo
vai para o grupo novo com os mesmos números, o perfil do item da lista de corte no nome antigo
("C8x13.75" em "Canal c C8X13.75") e, com o caso PP, a mesma inclinação do peso próprio (o poste
vertical e as peças a 45° da escada desempatam "Plataforma" de "Escada"). Um grupo novo serve a um
só antigo; na dúvida, fica sem corpo. Vira aviso "Corpos renomeados depois do estudo" com o mapa.
No modelo real: 46 de 46 vigas casadas, 24 pela renomeação.

**Nome do membro × seção desenhada.** O nome brasileiro com polegadas e kg/m (`U 8"x17,1`,
`W 8" x 31,3`) é lido por `perfil_do_nome`. Se o nome do membro indica um perfil cuja área difere
mais de 5 % da seção desenhada, o esqueleto avisa: no modelo real, "U 8"x17,1" (21,8 cm²) com a seção
do C8x13.75 = U 8" x 20,50 (25,9 cm²) — o Simulation calcula com a desenhada.

**PP só com a gravidade nas barras** (informação positiva): sem precisar das reações, a carga que o
PP mostra ao longo de cada barra é comparada com o peso dela pelo volume do esqueleto. No modelo
real, o estudo novo ("Apenas Gravidade") deu 13,95 kN ao longo das barras contra 13,75 kN de aço.
O nome do estudo sugere o caso também pelo assunto: "Apenas Gravidade", "Peso próprio" → PP;
"Sobrecarga" → SC (`caso_sugerido`).

**Comprimentos de flambagem pelos travamentos** (`core/travamentos.py`, `comprimentos`). Com o
esqueleto, o programa acha onde cada barra é ligada a outras (`ligacoes`: a ponta da outra encosta
nela, a até 0,30 m, ou as duas se cruzam; paralelas lado a lado não contam) e em que direção cada
ligação trava: a outra barra trava a direção d se tem componente nela (|cos| ≥ 0,5). Entre dois
travamentos, o trecho destravado; o maior é o comprimento de flambagem, com K = 1 — o B₂ da segunda
ordem global (página Contraventamento) cobre o deslocamento lateral, como no método da amplificação
dos esforços da NBR 8800. Nas pontas, qualquer ligação faz um nó (só a ponta que não encosta em
nada, fora do apoio, é balanço: K = 2,1, NBR 8800 Tabela E.1); ligações a menos de 0,10 m são o mesmo
nó, e a sobra de esqueleto de até 0,40 m além do último nó não é balanço quando a barra tem vão.

* **Pilar**: as duas direções em planta. Com a orientação da seção (macro v5: a direção da medida
  maior, a alma), Lx é o trecho na direção da alma e Ly na da mesa; sem ela (v4), Lx = Ly = o maior
  dos dois, a favor da segurança.
* **Viga**: Lx entre os apoios verticais (pontas, pilares e mãos-francesas que chegam nela); Ly e Lb
  entre os travamentos laterais (vigas e contraventamentos que chegam de lado, e os apoios — o topo
  do pilar segura a viga de lado e contra a torção). A chapa de piso sobre a mesa superior fica dita
  no motivo (presa à viga, trava a mesa comprimida no momento positivo), mas não entra no Lb sugerido.
* **Barra inclinada**: no plano vertical dela e fora dele; contraventamento: Lx = Ly = o maior.

No modelo real: a viga principal de 4,48 m saiu com Lx = 1,23 m (apoiada no pilar do meio e nas
mãos-francesas) e Lb = 0,60 m (as transversais e as cantoneiras que chegam de lado); o pilar com a
mão-francesa em X e outra em Z, 2,83 m em X e 3,14 m em Z (sem a orientação, Lx = Ly = 3,14 m).
A tabela das barras mostra "Lx / Ly / Lb sugeridos (m)" e a leitura barra a barra, o motivo.

**Sugestões** (`aplicar_sugestoes`, botão "Aplicar as sugestões"): preenchem só o que está vazio —
tipo, perfil (só se estiver no catálogo), eixo forte (quando o tipo também era vazio) e Lx, Ly e Lb
pelos travamentos do esqueleto (sem eles, o comprimento da barra). O perfil que entrou sozinho pelo nome da viga na importação dá lugar ao do modelo
(com o esqueleto). Nada escolhido à mão é trocado — menos o eixo forte tirado da seção (macro v6 ou
catálogo): ele não é escolha, é qual momento do Simulation é o do eixo forte, e troca o da tabela.
Enquanto a tabela tiver o outro, o diagnóstico mostra **"Eixo forte trocado"** (erro). O esqueleto fica em
`projeto["geometria_do_modelo"]` (lido de forma tolerante: linhas fora do formato são puladas).

## Pior caso de cada barra (`envoltoria`)

As combinações são as do plano (só com os casos importados), nos estados-limite escolhidos (ELU
normal por padrão). Para cada barra: a maior compressão e a maior tração (com a combinação e o
ponto), o maior momento forte com o N da mesma combinação e ponto (para a interação N + M), o maior
momento fraco, cortante (resultante de V1 e V2) e torque. CSV com ponto e vírgula.

## Verificação das barras (`core/verificacao_barras.py`)

**Parâmetros por tipo** (Pilar, Viga, Diagonal, Contraventamento, Outro; gravados no projeto): aço,
comprimentos de flambagem K·L em torno do eixo forte (`Lx`) e do fraco (`Ly`), comprimento
destravado `Lb` (vazio = `Ly`), `Cb` e `B₂`. A **tabela das barras** pode mudar o aço e os
comprimentos de uma barra. Norma: NBR 8800:2025 (padrão), NBR 8800:2008 ou AISC 360-16.

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
* **Nos eixos do modelo** (`ds.na_fundacao_no_modelo`): com a direção da seção de cada pilar no
  Simulation (`core/direcoes_da_secao.py`: a linha pela macro v6, o sentido por um caso de vento
  viga a viga com carga no pilar), o quadro ganha F e M nos dois eixos horizontais do SolidWorks
  (FX, FZ, MX, MZ com Y vertical) — a força e o momento que o pilar faz na fundação, o contrário da
  reação. Conferido num pilar em balanço: a fundação recebe q·L e o momento (L²/2)·(ẑ × q), com o
  Fim 1 na base ou no topo. Os pilares sem a direção ficam vazios, e o motivo aparece.

## Reações nas bases para o engenheiro civil (`core/reacoes_nas_bases.py`)

Página própria (**Modelo SolidWorks › Reações nas bases**; atalho na seção 8): de cada pé, em cada
caso importado (PP, PE, SC, W0, W90…), as três forças e os três momentos que a estrutura faz na
fundação — **característicos, sem combinar nem majorar** (Anglo 5.9): o engenheiro civil combina.

* **De onde vem cada número**, caso a caso: (1) a reação em cada apoio da macro (`-apoios.csv`), se
  os apoios do caso somam a reação total dele; (2) senão, a força na base do pilar levada aos eixos
  do modelo pela direção da seção (`ds.DirecoesDaSecao.na_fundacao`). O pé sem nenhuma das duas fica
  de fora com o motivo (nunca uma célula vazia que pareça zero).
* **Apoio × pilar**: pela posição (esqueleto e nós com posição, macro v13+) ou, sem ela (macro
  v12), **pelos valores** — o único apoio cuja compressão e cortante batem com a base do pilar em
  todos os casos da macro (`_ligar_pelos_valores`).
* **Direção da seção pela macro** (`_direcao_pela_macro`): sem a direção da página (vento só nos
  nós do topo, sem carga ao longo do pilar), a cortante na base (V₁, V₂) gira até ser a reação
  horizontal no pé, nos casos da macro (mínimos quadrados no ângulo, só casos com cortante ≥ 0,05 kN
  e ≥ 10 % da compressão; o axial também tem de bater). Assim, os casos com os apoios de outra
  rodada saem pela base dos pilares. No banco real (27/10): PP, PE, SC, W0 e W90 pela macro; W180 e
  W270 pelos pilares — o W180 fecha com a reação total (1,82 kN).
* **Conferência**: a soma dos pés de cada caso contra a reação total do caso.
* **Pendências** (`pendencias`): os erros do painel "Antes de verificar" que mudam as reações (não
  contam a grade no plano nem o eixo forte; os do arquivo de forças só se algum pé do caso saiu da
  base do pilar). Com pendência, o Excel sai **PRELIMINAR** e a página lista o que corrigir.
* **Eixos**: da fundação (X e Y na planta, Z para cima: Y = −Z do SolidWorks) ou os do SolidWorks.
* **Excel**: Leia-me (nota da Anglo, convenção, conferência, avisos, pendências), Casos (natureza,
  γ e ψ da NBR 8800 — ψ só nas variáveis), Locação (coordenadas e engastado/articulado), Reações por
  pé (pé × caso, com filtro: Fx…Mz, N, H, M horizontal, descrição, pilar e de onde veio) e Resumo
  por pé (maior compressão, arrancamento, H e M, com o caso).

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

`tests/test_nucleo_esforcos_ponta_a_ponta.py` prova o núcleo de ponta a ponta com o teste01 do
usuário resolvido como **pórtico espacial** (`tests/portico_3d_teste01.py`: rigidez direta, 12 graus
de liberdade por elemento, 4 elementos por barra, PP com g = 10,5, SC 1,5 kN/m no contorno e os
quatro ventos nos nós do topo). Os arquivos saem no formato do SolidWorks e da macro (forças,
reações, apoios, fixações, esqueleto) e passam pela leitura, pelo projeto, pelos quadros, pela
envoltória (contra Σ γ·N à mão) e pelo painel: tudo certo primeiro; depois cada erro de envio — forças
de outro caso (W0 com o W90, W180 com o W0, SC com o PP), estudo base, gravidade no vento, estudo
majorado, nomes trocados, apoios de outra rodada, eixo vertical, B₂, o W270 real com o valor do vento
em X — e o painel tem de apontar o problema certo, com o caso certo; dados estragados ao acaso nunca
quebram o painel, e uma conferência que falha não derruba as outras.

`tests/test_reacoes_nas_bases.py`: com o mesmo pórtico, cada pé em cada caso tem de ser a reação do
cálculo (forças e momentos) pela macro, pela base do pilar (direção da seção dada ou tirada da
macro), com os apoios v12 sem posição ligados pelos valores, com apoios de outra rodada; eixos da
fundação × SolidWorks, casos com γ e ψ, Excel, pendências (só as que mudam as reações) e a página.

`tests/test_travamentos.py` (pontos mais próximos entre barras, pilar travado numa direção, com e
sem a orientação, balanço, viga com secundárias e pilar no meio, mão-francesa, sobra curta,
paralelas, chapa sobre a viga, contraventamento em X, leitura e sugestões),
`tests/test_leitura_do_modelo.py` (esqueleto, tipo pela posição e pelos esforços, pontas, malha, cada achado do diagnóstico, avisos do envio, sugestões, gravado corrompido), `tests/test_esforcos_modelo.py` (leitura com arquivos no formato do SolidWorks gerados por
`tests/dados_solidworks.py` a partir do pórtico do mini exemplo, conferência, envoltória ponto a
ponto contra a conta à mão, malhas diferentes), `tests/test_verificacao_barras.py` (pilar contra a página Flambagem de colunas, B₂, pendências, tirante, cantoneira, registro e memorial) `tests/test_quadro_fundacoes.py`, `tests/test_placa_base_pilares.py` (conta à mão do Design Guide 1, momento grande, critério Anglo, placa pequena, pendências, eixo fraco, ida e volta pelo projeto, registro e desenho) e `tests/test_esforcos_modelo_pagina.py`.
