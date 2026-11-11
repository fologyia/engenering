# Ajustes e tolerâncias

Página do grupo **Mecânica** (submenu Peças de máquinas). Dá os limites de um furo e de um eixo pela NBR 6158:1995 (a
ISO 286-1), a folga ou a interferência do ajuste, o aperto de um ajuste prensado e qual ajuste
escolher para segurar um torque.

## Como se usa

1. Ponha o **diâmetro nominal** (até 500 mm).
2. Escolha um **ajuste recomendado** (H7/s6, H8/f7, S7/h6...) ou **as classes à mão**: a letra e o
   grau IT do furo e do eixo.
3. Veja as três abas:
   - **Ajuste:** o tipo (com folga, incerto ou com interferência), a folga ou a interferência mínima
     e máxima, a tabela dos afastamentos e das dimensões máxima e mínima, a indicação para o desenho
     (por exemplo, Ø50 H7 (+0,025 / 0)) e o gráfico das zonas em volta da linha zero. Em *Como saiu
     cada número* estão o IT, a faixa e a tabela de onde veio cada afastamento.
   - **Aperto e montagem:** só para ajuste com interferência. Com o cubo, o comprimento do ajuste,
     os materiais, a rugosidade e a carga, dá a pressão mínima e máxima, o torque que o atrito segura,
     as tensões no furo do cubo e no eixo, a força de prensagem e a temperatura para montar a quente.
   - **Escolher o ajuste:** todos os ajustes recomendados na medida, com a faixa de cada um. Com os
     dados da aba Aperto, diz quais seguram o torque, quais escoam e a temperatura de montagem, e
     aponta o mais leve que serve. O botão *Usar* leva esse ajuste para as outras abas.
4. **Registrar no projeto** grava o ajuste (e o aperto, quando calculado) para o memorial.

## De onde vêm os números

O programa não guarda uma lista de ajustes prontos: ele monta qualquer classe com o sistema da norma.

- **Tabela 1:** os graus de tolerância IT1 a IT18, por faixa de dimensão.
- **Tabela 2:** o afastamento fundamental dos eixos. De a até h ele é o superior (es); de k até u, o
  inferior (ei). O outro sai somando ou tirando o IT.
- **Tabela 3:** o dos furos. De A até H, EI = −es do eixo da mesma letra. Em K, M e N até IT8 e de P
  até U até IT7, ES = −ei + Δ, com Δ = IT_n − IT_(n−1) (Δ = 0 até 3 mm). Acima disso, ES = −ei, e N
  acima de IT8 fica com ES = 0.
- **Casos especiais da norma:** M6 de 250 a 315 mm tem ES = −9 µm. Em js e JS o campo é ±IT/2,
  como na Tabela 32 (js7 de 18 a 30 mm é ±10,5 µm). A norma permite arredondar o IT ímpar de 7 a
  11 para o par de baixo (±10 µm); se o desenho usar o arredondado, ele fica dentro deste.

Folga máxima = ES − ei. Folga mínima = EI − es. Folga negativa é interferência.

Uma amostra dos números foi conferida no PDF da norma, nas tabelas de afastamentos limites (M e N
na Tabela 18, U na 22, js na 32, s na 37), e nos dois exemplos da nota C da Tabela 3 (K7 e S6 de
18 a 30 mm). Os testes guardam essas conferências. Os quatro ajustes H7 que o Assistente de
cargas já usava dão exatamente os mesmos números.

O aperto é o mesmo cálculo do caso *Ajuste prensado* do Cálculo de peças: Lamé (Shigley, cap. 3),
com a interferência útil descontada de 0,8·(Rz do eixo + Rz do furo), transmissão com a menor
interferência e tensões com a maior.

## Cadeia de cotas

Na aba **Cadeia de cotas**, as medidas vão em fila, cada uma com o sentido:

- a que **aumenta** a folga (a largura do alojamento) entra com +;
- as que a **diminuem** (rolamentos, espaçadores, anéis) entram com −.

A tolerância de cada elo vem dos afastamentos da linha ou de uma **classe ISO** (h11, js9…), que sai da
NBR 6158 na própria medida. Linhas vazias não contam.

- **Pior caso:** todos os elos no limite que mais atrapalha ao mesmo tempo. A folga nunca sai daqui.
- **Estatístico (±3σ):** cada tolerância é ±3σ de um processo centrado; a folga tem média = soma das
  médias e σ = √Σσᵢ². Cobre 99,73 % das montagens em série. Para poucas peças, vale o pior caso.
- **Peso de cada elo:** no pior caso (a tolerância dele na soma) e na variação (σᵢ² na soma). Apertar
  a tolerância de quem mais pesa é o que mais estreita a folga.
- Com a **folga mínima** e a **máxima** exigidas, a página diz se atende no pior caso, só no
  estatístico (e a fração das montagens que sairia) ou se não atende.

Exemplo da tela: caixa de 60 (+0,10/0), dois rolamentos de 20 (0/−0,12) e espaçador de 19,8 h11 (0/−0,13).
Folga nominal 0,20 mm; pior caso de 0,20 a 0,67 mm.

## Limites

- Dimensões de 0 a 500 mm. Acima disso a norma tem tabelas próprias, em parte para uso experimental.
- Letras de uso raro ficam de fora: cd, ef, fg, j, v, x, y, z, za, zb, zc e as maiúsculas delas.
- K acima de IT8 só existe até 3 mm; t e T só acima de 24 mm. A página explica quando a classe não
  existe.
- Peças a 20 °C, sem erro de forma. A força centrífuga, que afrouxa o ajuste em rotação alta, não
  entra no aperto.
