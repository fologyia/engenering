# Desenhar seção

Prancheta para desenhar uma seção qualquer, ver as propriedades e usá-la nos outros cálculos.

## Como a conta é feita

Arquivo: `core/secao_desenhada.py`. Só usa numpy.

A seção é uma lista de partes (retângulo, círculo ou polígono, cheias ou furos). A conta é sobre a
figura final: parte sobre parte conta uma vez e o furo tira de tudo o que estiver embaixo.

**Malha.** Grade cartesiana com linhas sobre as arestas das partes, então seção de retângulos fica
exata. Aresta curva ou inclinada corta a célula, que é integrada por subpontos (método das células
finitas). Como o problema de torção só tem condição natural no contorno, a malha não precisa
acompanhar a forma. Seção fechada, com furos ou com mais de uma célula entra sem tratamento especial.

**Torção.** Elementos Q4 resolvem a função de empenamento (∇²ω = 0), por gradiente conjugado:

- `J = Ix + Iy − ωᵀf`;
- centro de cisalhamento pela condição ∫ω_s·x dA = ∫ω_s·y dA = 0;
- `Cw = ∫ω_s² dA`.

**Módulo plástico.** Linha neutra plástica por bisseção sobre as faixas da malha.

## Conferido contra

| Caso | Referência | Erro |
|---|---|---|
| Retângulo 1:1 a 10:1, J | série de Saint-Venant | até 0,27 % |
| Chapa 40:1, J | bt³/3·(1 − 0,63 t/b) | 0,47 % |
| Barra redonda, J | πd⁴/32 | 0,02 % |
| Tubo 200×3 a 200×20, A, I e J | fórmula fechada | até 0,10 % |
| Tubo retangular fino, J | Bredt | até 1 % |
| I, A, Ix, Iy, Zx | `perfil_i_simetrico` | exato |
| I, Cw | Iy·h²/4 | 0,15 % |
| U, centro de cisalhamento | parede fina | 0,4 % |
| U, Cw | parede fina | 0,6 % |
| T, centro de cisalhamento | encontro da mesa com a alma | menos de 1 mm |

τ de torção: dentro de 5 % nos casos conferidos (círculo, quadrado, 2:1 e 10:1). O valor é lido na
superfície, sem os cantos vivos reentrantes, onde a teoria dá infinito.

## O que vale para as rotinas de norma

`reconhecer()` olha a figura, venha ela de um modelo ou de chapas soltas:

| Figura | Família no catálogo | Efeito |
|---|---|---|
| I de dupla simetria | I soldado | rotinas de I |
| U | U soldado | rotinas de U, com o centro de cisalhamento da malha |
| T | T soldado | rotinas de T |
| Caixão ou tubo retangular | Tubo retangular | rotinas de tubo, com a menor parede |
| Tubo redondo, barra | Tubo circular, Barra | rotinas da família |
| C enrijecido | C enrijecido | aviso de perfil formado a frio |
| Qualquer outra | Personalizado (desenhada) | propriedades calculadas; norma em alerta |

Uma I de mesas diferentes **não** entra como I: as fórmulas de lá são de dupla simetria e dariam W e
M_Rd maiores que os reais. O mesmo vale para o I com chapa em uma mesa.

Na forma livre, `PerfilAco` leva três dados que a família não sabe calcular:

- `x0_mm`, `y0_mm`: centro de cisalhamento, usado na flexo-torção;
- `i_min_mm4`: menor inércia principal, quando os eixos principais são girados. Ela entra no lugar
  da menor entre Ix e Iy, porque a barra flamba nesse eixo.

Wx e Wy da forma livre usam a fibra mais afastada, não d/2.

## Medidas digitadas no desenho

Clique na cota: a altura e a largura totais estão sempre à vista, e as da chapa aparecem com ela
selecionada (num perfil pronto, o primeiro clique pega o grupo e o segundo pega a chapa).

- Mudar a altura de uma chapa deixa a base no lugar e sobe o topo, levando quem está encostado em
  cima. Assim a alma cresce sem soltar a mesa, e a mesa engrossa sem invadir a alma.
- Mudar a largura cresce do centro, para não tirar a seção de simetria, e empurra quem está dos lados.
- A outra alma de um caixão acompanha: sem isso ela ficaria solta da mesa que subiu.
- Na medida total, cresce quem vai de ponta a ponta (as mesas de um I, na largura); sem ninguém assim,
  cresce quem cruza o meio (a alma, na altura). Os outros andam para fora e continuam encostados.
  Sem chapa para crescer, como num tubo redondo, a seção inteira muda de escala.
- Chapa girada e polígono mudam só a própria medida, sem empurrar ninguém.

A lógica está em `components/prancheta/geometria.js`, testada no Node por
`tests/test_editor_numerico_js.py`.

## Limites

- Partes encostadas contam como uma peça só: a ligação entre elas precisa passar o cortante.
- Pedaços soltos não vão ao catálogo. Peças ligadas por espaçadores ficam em Perfis compostos, na
  Flambagem de colunas.
- Perfil do catálogo entra como chapas, sem os raios de concordância. A tela mostra a diferença de
  área quando passa de 0,5 %.
- Flambagem local da forma livre não é avaliada, e a página de Flambagem não desenha a forma livre
  (o Catálogo de perfis desenha).
- I monossimétrico pelo Anexo G da NBR 8800 não está implementado: esses perfis ficam como forma
  livre.
