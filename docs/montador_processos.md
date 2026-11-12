# Montador de processos

A página que liga o Montador térmico e o Montador de fluidos. Usa o mesmo motor e a mesma prancheta
(`docs/montador_formulas.md`), com os blocos das duas partes na mesma biblioteca e dois blocos de
ponte (`core/montador_processos.py`). O que está escrito nos documentos das duas partes
(`docs/montador_termico.md` e `docs/montador_fluidos.md`) vale igual aqui.

## Para que serve

- **Do térmico para os fluidos:** "preciso tirar 200 kW com água: que vazão, que tubo, que bomba?". O
  calor pedido acha a vazão, e a corrente segue para o trecho de tubo, as perdas, a velocidade, a
  bomba e o NPSH, com as propriedades do estado dela.
- **Dos fluidos para o térmico:** a perda de carga e o desnível do tubo voltam para a corrente, e os
  equipamentos de depois recebem a pressão já descontada: a bomba que alimenta uma caldeira precisa
  vencer a pressão da caldeira, o tubo e a altura.

## Os dois blocos da ponte

- **Linha da corrente** (do térmico para os fluidos). Recebe uma corrente e entrega a linha de
  fluidos: ρ e μ na pressão e na entalpia da corrente, a pressão de vapor na temperatura dela, e a
  vazão em volume, Q = ṁ/ρ. Daí em diante valem os blocos de fluidos de sempre. Se a corrente chega
  com líquido e vapor misturados, a página avisa: a linha é de uma fase só.
- **Corrente depois da linha** (dos fluidos para o térmico). Recebe a corrente do começo do tubo e a
  linha, já com os trechos e as perdas, e entrega a corrente no fim do tubo: p₂ = p₁ − ρ·g·(h_L + Δz)
  e h₂ = h₁ − g·Δz. O desnível Δz é positivo quando a linha sobe. O atrito não muda a entalpia: ele
  troca pressão por temperatura dentro do próprio fluido.

As duas partes usam o SI na base, e por isso nenhum número se converte no caminho. O botão **Unidades**
junta os seletores das duas: temperatura, pressão (com mca), entalpia, vazão em massa, potência,
diâmetro, comprimento e vazão em volume.

## Letras que a conta acha

Nesta página é comum uma letra ficar em branco de propósito. No modelo de resfriamento, a vazão em
massa não é digitada: a igualdade do calor pedido a determina, e ela aparece na resposta ("Achadas
pelas igualdades da montagem"), na tabela de estados, no registro do projeto e nas saídas que outro
cálculo pode ler (`docs/montador_formulas.md`, "Letras do meio e laços").

## Trazer uma montagem pronta

Nas páginas de fluidos e do térmico, o botão **Abrir esta montagem no Montador de processos** leva a
montagem inteira para cá, com os blocos, os fios e os números, e a de origem continua como estava. É
o caminho de quem já tem uma análise de fluidos pronta e precisa ligar nela uma parte térmica, ou o
contrário. O arquivo JSON de uma montagem de fluidos ou do térmico também abre aqui, e os conjuntos
salvos numa das duas aparecem na biblioteca desta página. O bloco **Cálculo registrado** lê o
resultado de uma montagem de qualquer parte, convertido pelo SI.

## Exemplos conferidos

- **Resfriar com água:** 200 kW com água de 30 °C a 40 °C dão 4,786 kg/s; com 2 m/s, o tubo sai com
  55,3 mm. Bate com a conta de mão pela entalpia da CoolProp.
- **Bomba de água quente:** a 80 °C, a altura de sucção máxima cai para 2,42 m, com a pressão de
  vapor do estado; a 40 °C ela é maior. Bate com a conta de mão do NPSH.
- **Da bomba à caldeira:** para a água chegar à caldeira com 3 MPa depois de 80 m de tubo de 40 mm e
  15 m de altura, a bomba precisa de 3,206 MPa na saída. Bate com a conta de mão, resolvida por
  bisseção, em todas as casas.

## Limites

- A linha de fluidos continua incompressível e na mesma temperatura do começo ao fim: aquecer ou
  esfriar ao longo do tubo, e gás com grande queda de pressão, chegam com a transferência de calor e o
  escoamento compressível.
- As propriedades da linha são as do ponto onde ela começa.
- A linha é em série; rede com ramais fica na página Rede de tubos.
