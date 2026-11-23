# Análise sobre o desenho

Página: `app_pages/analise_sobre_desenho.py` (menu Mecânica › Peças de máquinas). Arquivos:
`core/analise_desenho.py` (marcas, conta, fundo e memorial, sem Streamlit),
`components/analise_desenho_ui.py` (tela) e `components/prancheta_analise/` (a prancheta).

## O que faz

O desenho entra como fundo e, em cada parte dele, uma marca diz qual análise vale ali. A análise é um
modelo do Montador de fórmulas — pino ao corte, chapa com furo, eixo, chaveta, rolamento, fuso, coluna,
viga... — e a conta é a do Montador, sem cópia (`montador.montar` + `montador.isolar`).

1. **Desenho:** imagem (PNG, JPG), PDF (uma página por vez, a 150 dpi, pelo `pypdfium2`), DXF (pelo
   `core/esboco_dxf.py`, já em mm), um print colado na prancheta com Ctrl+V, ou um **esboço salvo**
   da Desenhar seção (com as cotas e as letras). Imagem grande é reduzida a 2000 px no lado maior.
2. **Escala (imagem):** a ferramenta Escala pede duas pontas de uma medida conhecida e o valor dela em
   mm; Medir mostra a distância real entre dois pontos. No DXF e no esboço a escala já é 1.
3. **Marcar:** cada clique com Marcar cria uma marca numerada. Ela nasce com o primeiro modelo da lista
   (pino), com os números de exemplo dele, os padrões das letras e o que os blocos sugerem, e mostra
   até onde a letra principal vai. No DXF e no esboço, a marca **gruda**: na ponta de linha ou no
   centro de furo que estiver bem perto, senão no centro do menor círculo que contém o clique, senão
   no ponto da linha mais perto. A ponta da Escala, do Medir e da régua também gruda.
4. **Análise de cada marca** (embaixo do desenho): nome da parte, modelo do Montador, e "Conferir a
   medida" (com o valor da letra principal ◀ preenchido: passou ou não, com o uso de cada condição) ou
   "Achar o limite" (a letra principal fica livre). O valor inicial da letra principal é o limite
   arredondado para o lado seguro (máximo para baixo, mínimo para cima).
5. **Medida pegada no desenho:** ao lado de cada campo de comprimento, a régua pede a medida na
   prancheta: duas pontas, ou um clique na borda de um círculo (DXF ou esboço) para o diâmetro. Na
   imagem, precisa da escala. Esc, ou trocar de ferramenta, cancela.
6. **Só nota, sem conta:** a última opção da lista. A marca leva um texto ("apoia na viga V-3",
   "transmite a força ao pino") e vai ao desenho (em roxo) e ao memorial, sem conta.
7. **No desenho**, a etiqueta da marca volta com o resultado: verde passou, vermelho não passou, azul
   o limite, cinza falta número, roxo nota.
8. **Abrir no Montador** leva a marca para o Montador de fórmulas, com o mesmo modelo e os mesmos
   números (`montador_ui.abrir_com_valores`), para usar busca, casos de carga e o memorial de lá.
9. **Gerar o Word:** o desenho com as marcas numeradas e, para cada parte, os números (os que vêm do
   esboço dizem de onde), as condições e as hipóteses.

## Esboço de fundo

- O esboço é desenhado com as letras de agora (`fundo_de_esboco`); as letras aparecem embaixo do
  desenho, e mudar uma refaz o desenho (letra que desfaz o desenho volta ao valor de antes).
- Cada campo de comprimento da marca pode ficar **ligado** a uma letra ou a uma medida com nome do
  esboço (a cota de referência com nome, como `w`). Ligado, o número vem dele (`valores_da_marca`) e
  o campo fica travado.
- **Achar pelo esboço** varia uma letra ligada na faixa de teste dela (`limite_pelo_esboco`): o esboço
  é refeito a cada valor, as medidas ligadas mudam junto, e a conta da marca é conferida. Uma grade de
  21 valores acha a troca entre passar e não passar, e a bisseção acerta o valor. Responde "a partir
  de" (crescer ajuda), "até" (crescer atrapalha), "toda a faixa" ou "nenhum"; o desenho que deixa de
  existir conta como não passar. "Usar no esboço" põe o valor, arredondado para o lado seguro, na
  letra. A marca precisa estar com a medida ◀ preenchida (ou ligada) para conferir.

## Blocos do Montador (`core/montador_ligacoes.py`, grupo "Pinos e chapas")

- **Pino ao corte:** os mesmos critérios de `calcular_pinos` (Cálculo de peças): cisalhamento
  (τ_máx = 4/3·V/A), flexão do pino pelo equilíbrio das chapas alternadas (função numérica
  `BracoDoPino` = M/V, em `core/montador_funcoes.py`), interação flexão-cortante, esmagamento nas
  chapas da ponta e de dentro, rasgamento até a borda e seção líquida. Planos de corte de 1 a 6.
  Conferido nos testes: a força resistente bate com a do Cálculo de peças com 1, 2, 3 e 4 planos.
- **Chapa com furo:** escoamento da seção bruta e ruptura da seção com furos, como `calcular_chapa`.
- Modelos: "Pino: força máxima", "Pino: diâmetro mínimo", "Chapa com furo: espessura mínima".

## Limites

- A solda de filete ainda não tem bloco no Montador (padrões de cordão e critérios da NBR 8800 e da
  AISC): continua no Cálculo de peças.
- A posição das marcas é do desenho e do memorial: a marca não anda quando a letra do esboço muda
  (as medidas ligadas, sim).
- Achar pelo esboço varia uma letra por vez, dentro da faixa de teste dela; com a marca mudando de
  lado mais de uma vez na faixa, o texto avisa.
