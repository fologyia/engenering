# Nomes das barras

Página **Nomes das barras** (grupo Modelo SolidWorks), núcleo em `core/papel_pelo_nome.py` (o
padrão e a leitura) e `core/nomes_das_barras.py` (a sugestão, o arquivo da macro, o relatório),
macro `macros_solidworks/renomear_corpos.bas`.

## Por que

O programa entende o modelo pela posição de cada corpo: vertical é pilar, horizontal é viga,
inclinada é contraventamento. Isso erra onde a posição engana:

- a longarina da escada é inclinada e trabalha fletida (não é contraventamento);
- o montante do guarda-corpo é vertical e não é pilar (não vai para as fundações nem para o B₂);
- a chapa de base ou de ligação deitada não é piso (não recebe sobrecarga);
- o nome que o SolidWorks dá ao corpo (`Aparar/Estender12[1]`) não diz nada, e o `[n]` muda de corpo
  quando o modelo é editado.

O nome do corpo resolve: ele diz o papel, e o programa passa a ler o papel pelo nome.

## O padrão

`PREFIXO-LOCAL`. O prefixo diz o papel; o resto, onde a peça está (só para quem lê).

| Prefixo | Papel | Tipo na verificação | Forma |
|---|---|---|---|
| P | Pilar | Pilar | barra |
| V | Viga | Viga | barra |
| LG | Longarina de escada | Viga | barra |
| DG | Degrau | Viga | barra |
| C | Contraventamento | Contraventamento | barra |
| MF | Mão-francesa | Contraventamento | barra |
| GC | Guarda-corpo | Outro | barra |
| PS | Piso | — (chapa de piso) | chapa |
| PT | Patamar | — (sobrecarga de escada) | chapa |
| ES | Lance de escada | — (sobrecarga de escada) | chapa |
| CH | Chapa sem carga | — (fora do piso) | chapa |
| PC | Outra peça | — (o programa segue a geometria) | qualquer |

O local que a página gera:

- **pilar**: `P-A1` (o cruzamento da grade no pé); `P-A1-N1` quando o pilar tem um trecho por nível;
- **barra com as duas pontas em cruzamentos**: `V-N1-A1-A2` (nível, depois os cruzamentos — na barra
  inclinada, da ponta de baixo para a de cima: `C-N0-B1-B2` sobe de B1 a B2);
- **as outras barras**: `V-N1-07`, numeradas na ordem da planta, por papel e nível;
- **chapas e peças**: `PS-N1-01`, `CH-N0-01`, `PC-N0-01`.

A **grade** sai dos pés dos pilares: as posições em planta agrupadas a 0,20 m viram eixos — números
da esquerda para a direita, letras de baixo para cima, como na vista Superior do SolidWorks (sem I e
O). Os **níveis** saem das vigas em nível e das chapas de piso, agrupados a 0,25 m: N0 é o pé da
estrutura, N1, N2… para cima. Uma ponta cai no cruzamento se estiver a até 0,35 m dele.

O programa também entende o papel escrito por extenso (`W200x31,3 - Pilar`, `Viga de borda`,
`Mão-francesa 2`) e a forma curta de costume (`P1`, `V101`). A letra sozinha (`C`, `P[2]`) e um nome
que parece perfil (`C-8X11.5`) não dizem papel. Os nomes do padrão não dizem perfil: a letra L da
grade não vira cantoneira.

## O nome contra a geometria

O nome não manda sozinho (`pn.avaliar`). Contradição — vale a posição, e o programa avisa:

- papel de chapa numa barra, papel de barra numa chapa;
- pilar a menos de 45° da horizontal; viga a mais de 45°; degrau a mais de 15°;
- piso ou patamar a mais de 60° (em pé); lance de escada em nível.

O resto vale, com uma nota quando é pouco comum: pilar inclinado (45° a 76°), viga inclinada (10° a
45°), rampa (piso de 10° a 60°), longarina em nível. Na chapa e na peça curta a medida maior não é o
eixo; aí vale a inclinação do peso próprio (com o estudo) ou nenhuma.

A conferência da página não deixa sair um arquivo com contradição, nome fora do padrão, prefixo que
não é o do papel ou nome repetido.

## Onde o programa usa o nome

- `ld.tipo_pela_geometria` (3D, leitura do piso, cenas) e `ld.ler_barras` (Esforços do modelo): o
  tipo pelo nome; sem o esqueleto, pelo nome que o Simulation mostra entre parênteses
  (`Viga-3(P-A1)`). Contraventamento pelo nome que trabalha fletido vira aviso.
- Diagnóstico: "Nome que contradiz a posição" e "Tipo diferente do nome no SolidWorks" (o tipo da
  tabela das barras é outro).
- Leitura do piso: longarina pelo nome conta como longarina mesmo sem as chapas da escada; PS, PT e
  ES dão o tipo da chapa; CH tira a chapa do piso.
- Perfil: o PERFIL declarado no item da lista de corte (propriedade que a macro grava; a
  exportar_lista_de_corte v7 o leva ao esqueleto) vale como o nome e a descrição juntos. A área
  desenhada continua conferindo: até 10 % mais pesada vale o declarado; mais pesada que isso vale o
  declarado com aviso; mais leve vale o desenho (lado seguro), com aviso. A Lista de material usa o
  PERFIL no lugar da descrição.

## A macro renomear_corpos.bas

1. Acha o `<peça>_nomes.csv` ao lado da peça, depois em Downloads; senão pede o caminho.
2. Lê os corpos da peça (nome, centro de massa, volume).
3. Casa cada linha com o corpo: pelo nome, **conferido pela geometria** (o centro de massa a até 5 mm
   da linha de centro do esqueleto e o volume a 1 %); se o nome não existe mais ou a geometria não
   bate, pelo único corpo livre que bate; senão pula, com o motivo.
4. Confere os nomes novos: o que o SolidWorks não aceita, nome de um corpo que fica, o mesmo nome
   para dois corpos.
5. Mostra o resumo e **só continua com a confirmação**.
6. Grava o PERFIL dos itens (Add3/Delete2, conferido lendo de volta).
7. Troca os nomes em duas fases (nome provisório, depois o novo): dois corpos podem trocar de nome
   entre si. Um corpo que o SolidWorks recusa volta ao nome antigo.
8. Reconstrói a peça e confere os nomes de novo; atualiza a árvore e marca a peça para salvar.
9. Grava `<peça>_nomes_aplicados.csv` (relatório: cada corpo, antes, depois, situação, motivo) e
   `<peça>_nomes_desfazer.csv` (o mesmo formato do arquivo de nomes, ao contrário).

O arquivo de nomes (cp1252, ponto e vírgula, números com ponto decimal, lidos com `Val`) traz:
`ARQUIVO`, `PECA`, `CONFIGURACAO`, `ESQUELETO`, `DATA`, a linha `CORPOS;ATUAL;NOVO;PAPEL;FORMA;X1…Z2
(mm);COMPRIMENTO (mm);VOLUME (cm3)` e uma linha `CORPO` por corpo que muda; depois
`PERFIS;ITEM;PERFIL;CORPO DO ITEM` e uma linha `PERFIL` por item (vazio apaga o PERFIL).

Não testada no SolidWorks real quando foi escrita (17/11/2026): a matemática e o contrato com o
programa estão travados em `tests/test_nomes_das_barras.py`.

## As trocas guardadas no projeto

Baixar o arquivo de nomes guarda as trocas pedidas (com a posição de cada corpo); o relatório da
macro, enviado na seção 6, as confirma. `ld.geometria_do_projeto` junta as trocas ao esqueleto, e
`ld.correspondencia` acha o corpo de um estudo rodado antes da troca (e o de um esqueleto de antes
da troca), **só se o corpo não saiu do lugar** (o meio dele a até 5 cm, o comprimento a 2 %). Cadeias
(A → B → C) são seguidas. O diagnóstico avisa "Nomes trocados depois do estudo" (informativo): o
certo é refazer a malha e rodar os estudos de novo.

O corpo renomeado continua contando no membro do nome de antes para escolher o perfil das peças
cortadas (`ld.nome_original`).

A seção 6 também passa o plano de cargas aos nomes novos (as linhas que citam um corpo pelo nome
antigo), só com as trocas que aconteceram: confirmadas pelo relatório ou com o nome novo já no
esqueleto.

## Rodar de novo

O nome que já está no padrão, limpo e com o mesmo papel, fica (`MANTIDO`): mexer no modelo e rodar a
página de novo só dá nome ao que é novo. "Refazer também os nomes que já estão no padrão" gera tudo
de novo (a grade mudou e os nomes devem acompanhar) — os estudos do Simulation vão precisar de malha
nova.
