# Montador térmico

A terceira parte do Montador. Usa o mesmo motor e a mesma prancheta do Montador de fórmulas
(`docs/montador_formulas.md`), com blocos de termodinâmica, unidades próprias e as propriedades da
CoolProp (`core/montador_termico.py`, `core/montador_propriedades.py`). O que está escrito lá sobre o
inspetor, os conjuntos, salvar, registrar, referências, comparar e o que mais pesa vale igual aqui.

## Como se usa

A fila é **Estado do fluido → equipamentos → verificação → Em função de**. O fio vermelho é a
**corrente**: leva o fluido, a pressão absoluta, a entalpia e a vazão em massa. Temperatura, entropia e
título saem da pressão e da entalpia, pela CoolProp. Cada equipamento recebe a corrente, muda o estado
e passa adiante; bombas, compressores e turbinas entregam também a potência, e a troca de calor
entrega o calor, num fio de valor (laranja), para as verificações e para o rendimento do ciclo.

Num ciclo, o último equipamento volta para o primeiro. O bloco **Circuito** fica no laço: recebe a
saída do último equipamento e diz o fluido e a vazão do circuito, que num laço fechado não saem do
desenho. Só a corrente pode fechar laço, e só nesta parte.

As unidades ficam no botão **Unidades**: temperatura em °C, K ou °F; pressão absoluta em kPa, bar,
MPa ou Pa; entalpia em kJ/kg; vazão em kg/s, kg/h ou t/h; potência em kW, W, MW ou cv.

## Blocos

- **Estado do fluido:** o fluido e o estado dele, por temperatura e pressão, líquido ou vapor
  saturado (pela pressão ou pela temperatura), título e pressão, superaquecido ou sub-resfriado (graus
  acima ou abaixo da saturação), mais a vazão em massa.
- **Circuito:** fecha o ciclo, com o fluido e a vazão do laço.
- **Bomba e Compressor:** h₂ = h₁ + (h₂ₛ − h₁)/η, com h₂ₛ na pressão de saída e na entropia da
  entrada. Entregam a potência consumida. Avisam se a bomba recebe vapor ou o compressor recebe
  líquido.
- **Turbina:** h₂ = h₁ − η·(h₁ − h₂ₛ). Entrega a potência produzida.
- **Válvula de expansão:** h₂ = h₁, na pressão de baixa.
- **Troca de calor:** caldeira, aquecedor, condensador, evaporador ou resfriador. A saída é dada pela
  temperatura, saturada (líquido no condensador, vapor no evaporador), pelo título ou pelo calor; a
  pressão cai a perda informada. Entrega Q̇ = ṁ·(h₂ − h₁), positivo quando o fluido recebe calor.
- **Misturador e Divisor:** mistura adiabática de duas correntes do mesmo fluido; divisão da vazão
  com a fração y.
- **Verificações:** temperatura máxima e mínima, pressão mínima e máxima, título mínimo,
  superaquecimento e sub-resfriamento mínimos, potência disponível, calor pedido, rendimento do ciclo
  e COP.

A vazão em massa do Estado pode ficar em branco: se uma igualdade a determina, como o calor pedido, a
conta acha o número dela. Para ligar a corrente à tubulação (trecho, perdas, bomba, NPSH), use o botão
**Abrir esta montagem no Montador de processos**, ou monte direto lá (`docs/montador_processos.md`).

## O que a conta faz

As contas são as de Çengel e Boles, Termodinâmica, capítulos 7, 10 e 11. O estado anda por pressão e
entalpia, que definem o ponto mesmo dentro da mistura de líquido e vapor. O título vai por
(h − h_l)/(h_v − h_l): passa de 1 no vapor superaquecido e fica abaixo de 0 no líquido sub-resfriado,
o que serve para uma condição (a CoolProp dá −1 fora da mistura).

## Diagrama do ciclo

Abaixo da tabela de estados, na aba Condições, sai o diagrama T-s ou p-h (pressão em escala log),
com a curva de saturação do fluido em cinza. Cada ponto tem o número da tabela e a cor da fase:
líquido, mistura, ou vapor e gás. Numa troca de calor e na válvula, o caminho entre dois pontos é
calculado com a pressão e a entalpia andando em reta, pela CoolProp: é a isobárica de verdade, que
entra e sai da curva. Na bomba, no compressor e na turbina, a figura só liga a entrada à saída.

O diagrama mostra de relance o estado que não faz sentido. Se a bomba recebe vapor ou o compressor
recebe líquido, a página avisa embaixo dele (`core/montador_diagrama.py`). Com dois fluidos, como num
trocador, uma lista escolhe o fluido do diagrama. Glicóis, óleos térmicos e o ar seco não têm curva de
saturação na CoolProp.

## O laço

O laço é cortado no fio que chega no Circuito. A pressão e a entalpia supostas (p_lc1 e h_lc1) viram
letras do meio, e duas igualdades as fecham com as que de fato voltam (`core/montador_sistema.py`). A
resposta mostra os números delas, e a tabela de estados mostra cada ponto do ciclo.

## Exemplos conferidos

- **Ciclo Rankine simples** (Çengel e Boles, Exemplo 10-1): 3 MPa e 350 °C na turbina, condensador a
  75 kPa, bomba e turbina ideais. O livro dá 26,0 %; o programa dá 0,2602, igual à conta com a CoolProp
  chamada direto.
- **Refrigeração com R134a** (Exemplo 11-1): 0,14 e 0,8 MPa, 0,05 kg/s. O livro dá COP 3,97 e
  7,18 kW tirados no evaporador; o programa dá 3,968 e 7,184 kW.
- Aquecer água, mistura de água quente e fria, compressor de ar e turbina batem com a CoolProp chamada
  direto, bloco a bloco (`tests/test_montador_termico.py`).

## Limites

- Regime permanente, sem variação de energia cinética e potencial; equipamentos adiabáticos, menos a
  troca de calor.
- A troca de calor é de um lado só: o trocador com as duas correntes (ε-NTU e média logarítmica)
  chega na fase de transferência de calor.
- Os glicóis e os óleos térmicos são líquidos de tabela: não evaporam, e os blocos que pedem saturação
  avisam.
- Ácidos não estão na CoolProp.
- O Circuito precisa estar no laço: laço de corrente sem ele dá o aviso de laço.
- A biblioteca esconde o que não serve para o fluido do Estado e do Circuito: com ar ou nitrogênio, a
  bomba, o título, o superaquecimento, o sub-resfriamento e o COP; com glicol ou óleo, o compressor e a
  turbina. Com dois fluidos, basta um servir.

## Transferência de calor

- **Tubo isolado:** quanto o fluido esfria num tubo com isolamento e a temperatura por fora dele.
  Resistência por metro R' = ln(r_iso/r_e)/(2π·k) + 1/(2π·r_iso·h), com o ar em temperatura fixa;
  o fluido esfria em exponencial ao longo do tubo. A película de dentro e a parede de aço ficam de
  fora (pequenas perto do isolamento). Entrega o calor perdido e a temperatura da superfície, que vai
  para a verificação **Temperatura da superfície**.
- **Trocador de calor:** duas correntes, pelo método ε-NTU (Incropera, cap. 11), em contracorrente
  ou em correntes paralelas. O UA diz o tamanho do trocador e pode ser a letra pedida. O c_p de cada
  corrente é o da entrada, e a saída sai pela entalpia.
- Modelos: **Tubo de água quente: isolamento mínimo** (300 m de 2 pol a 80 °C: 4,9 mm para cair no
  máximo 2 °C) e **Trocador: tamanho para resfriar óleo** (Therminol 66 de 150 °C para 80 °C com
  água a 20 °C: UA = 1563 W/K). Os dois batem com a conta de mão; o do trocador também com a
  biblioteca `ht` (`tests/test_montador_calor.py`).
- O h externo é um dado (convecção e radiação juntas): o programa não calcula a película externa.
