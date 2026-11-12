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
- **Verificações:** temperatura máxima e mínima, título mínimo, superaquecimento e sub-resfriamento
  mínimos, potência disponível, calor pedido, rendimento do ciclo e COP.

## O que a conta faz

As contas são as de Çengel e Boles, Termodinâmica, capítulos 7, 10 e 11. O estado anda por pressão e
entalpia, que definem o ponto mesmo dentro da mistura de líquido e vapor. O título vai por
(h − h_l)/(h_v − h_l): passa de 1 no vapor superaquecido e fica abaixo de 0 no líquido sub-resfriado,
o que serve para uma condição (a CoolProp dá −1 fora da mistura).

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
