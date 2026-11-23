# Desenhar seção

Prancheta para desenhar uma seção qualquer, ver as propriedades e usá-la nos outros cálculos.
Dois modos: o esboço com cotas (abaixo) e o desenho simples de chapas.

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

## Usar a seção nos outros casos

A Flexão de uma seção, a Viga e a Coluna do Assistente têm o tipo **Seção desenhada**, que lista as
seções salvas aqui. Nesse tipo, o cálculo usa a forma real: furos, recortes e partes sobrepostas entram
como foram desenhados, e o τ ao longo da altura sai das faixas da malha. O botão **Trazer a seção
aberta**, no próprio caso, salva a seção que está na prancheta e a escolhe, sem voltar a esta página. Os
botões daqui fazem o mesmo caminho. O Perfil pela norma continua pelo catálogo, porque precisa das
medidas de alma e mesa. Seção sem eixos principais em x e y dá aviso: M/W não mostra a flexão no outro
eixo, e a conta certa está em Tensões na seção.

### Ir desenhar e voltar com a seção (`components/volta_da_secao.py`)

O bloco **Seção desenhada** do Montador de fórmulas e o **Perfil do catálogo** de Vigas e eixos têm
o botão **Desenhar uma seção nova**: grava de onde veio (`VOLTA`) e abre esta página, que mostra o
aviso "Você veio do …" e o botão **Salvar e voltar** (no quadro Usar esta seção). Ele salva no
catálogo e volta com a seção já escolhida no bloco ou no perfil (`CHEGOU`, lida uma vez só por
`chegada`). "Voltar sem seção" volta sem mudar nada. O `st.switch_page` não roda em callback: os
botões marcam e a troca de página acontece na rodada.

## Tensões na seção

**Normal.** Flexão oblíqua completa, com Ixy. O mapa mostra a linha neutra.

**Cortante.** V·Q/(I·b) supõe τ uniforme na largura: serve numa alma, mas não numa mesa, numa
cantoneira ou num polígono qualquer. A conta aqui é a flexão de Saint-Venant, para a forma desenhada:
dois problemas de Poisson, ∇²Ψ e ∇²Φ, resolvidos com a mesma rigidez do empenamento, com ν = 0,3. Vale
para Ixy diferente de zero e para seção fechada.

**Soma.** V e T entram como vetores em cada ponto, porque se somam num lado e se subtraem no outro. A
soma dos maiores valores daria um número que nenhum ponto tem. Von Mises usa o σ e o τ do mesmo ponto.

**Onde passa a carga.** V passa pelo centro de cisalhamento, a menos que se escolha o centro de
gravidade. Aí a excentricidade vira torção, que num U leva o τ de 47 a mais de 800 MPa no exemplo dos
testes. A conta é de torção livre: com o empenamento impedido o valor real é outro.

**Ligações.** Em chapas retas que se encostam, q = ∫τ ds é a força por metro de barra que a solda
precisa levar. Na linha da emenda a média mistura a alma com a mesa e dá 27 % a menos num I. Por isso o
fluxo é medido em duas linhas dentro da chapa estreita e levado até a emenda.

**Norma.** τ_y = f_y/√3 não enxerga flambagem. Em I, U, T e caixão, a tabela traz também V_Rd de
`nbr8800.verificar_cisalhamento`, e avisa quando a chapa é esbelta: nesse caso, a tensão passar não
quer dizer que a alma aguenta. Numa seção livre ficam só as tensões.

| Caso | Referência | Erro |
|---|---|---|
| Retângulo alto, τ máx | 1,5 V/A | 0,13 % |
| Círculo, τ no centro | (3 + 2ν)/(2(1 + ν))·V/A | 0,02 % |
| I, τ na alma | V·Q/(I·t) | 0,07 % |
| I, q na solda da mesa | V·Q/I | 0,11 % |
| Tubo fino, τ máx | 2 V/A | 2,3 % |
| I, U e cantoneira, ∫τ dA | V aplicado | 1 em 10⁵ |
| U e cantoneira, centro de cisalhamento | o do empenamento | menos de 1 % |

A seção confere a si mesma: se ∫τ dA ficar a mais de 3 % de V, a tela avisa que a parede está fina
demais para a malha. Seção em pedaços soltos não calcula cortante: ele não passa de um para o outro.

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

## Polígono e cotas, no jeito de um CAD

**Desenhar com medida.** Na ferramenta Polígono, depois do primeiro ponto, basta digitar:

| Digitado | O próximo ponto fica |
|---|---|
| `100` | a 100 mm, na direção do mouse |
| `100<45` | a 100 mm, a 45° (0° para a direita, 90° para cima) |
| `@50;20` | 50 mm em x e 20 mm em y do ponto anterior |

Orto (ou a tecla O) trava os lados em 0°, 45° e 90°, e Shift faz o contrário na hora. Enter fecha o
polígono, Backspace volta um ponto, e ao lado do mouse aparece o comprimento e o ângulo do trecho.

**Editar o polígono.** Com ele selecionado, cada lado mostra a medida, e clicar nela abre a caixinha. O
ponto azul fica e o laranja anda; "Mover a outra ponta" troca os dois, e o botão de ângulo gira o lado.
Clicar num ponto mostra x e y no painel. A alça no meio de um lado cria um ponto, e Delete apaga o
ponto selecionado.

**Cota de um ponto a outro.** Na ferramenta Cota: clique no ponto que fica, no ponto que anda e no
lugar da cota, como no SolidWorks. O lugar escolhe o tipo: acima ou abaixo dos dois pontos mede a
horizontal, ao lado mede a vertical, e na diagonal mede a distância direta. Os pontos aceitos ficam
marcados em verde: cantos, meios de lado e centros, em qualquer parte.

| Os dois pontos estão | Digitar um valor faz |
|---|---|
| no mesmo polígono | o ponto anda, levando o trecho do contorno que está além dele |
| na mesma chapa, de lados opostos | a chapa muda de tamanho a partir do primeiro ponto |
| no mesmo círculo | o diâmetro muda |
| em partes diferentes | a parte do segundo ponto anda inteira, com o grupo dela |
| em partes do mesmo perfil | não muda: use as medidas da chapa |

**Por que o trecho anda junto.** Mover só o ponto entortaria o perfil. O contorno é percorrido a partir
do ponto, nos dois sentidos, e anda junto tudo o que está ligado a ele e além dele na direção da cota.
Num T, subir a alma leva a mesa inteira; num U, subir uma aba não leva a outra, que fica depois de um
trecho que desce. Um corte reto, "tudo acima desta linha", erraria no U.

**O que não vira polígono ruim.** O contorno é conferido antes de valer: dois pontos no mesmo lugar,
polígono sem área e lados que se cruzam, encostam ou ficam um sobre o outro são recusados, com o
motivo, e o desenho fica como estava. Um polígono sem área seria descartado no cálculo e sumiria.

**O que estas cotas não são.** A cota mede e comanda uma vez: digitou, a peça muda. Ela acompanha a
peça depois disso, mas não segura o valor se outra coisa mudar, como faria um CAD paramétrico. Para
isso seria preciso um solver de restrições, que este programa não tem.

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

## Esboço com cotas (o padrão da página)

Arquivos: `core/esboco.py` (modelo, contas com letras, solver), `core/esboco_regioes.py` (contornos,
aço e furo, contas exatas, validade), `core/esboco_secao.py` (teste do desenho e números do Montador),
`components/esboco/*.js` (a prancheta) e `components/esboco_ui.py`.

**Como num CAD paramétrico.** Pontos, linhas, arcos e círculos, presos por restrições (juntos,
horizontal, vertical, paralelas, perpendiculares, tangentes, iguais, no meio, mesmo centro,
simétricos, fixo) e por cotas que seguram a medida (distância, distância à linha, diâmetro, raio,
ângulo). O que ainda está livre aparece em azul; totalmente definido fica preto. A cota que já estava
presa pelo resto vira cota de referência, entre parênteses. Restrição que briga com o resto é
recusada, dizendo quem briga.

**Letras.** A medida de uma cota aceita número, letra ou conta (`25`, `d`, `2*d`, `L/2 - 10`), lida
sem `eval`. Letra nova nasce com o valor que a medida já tem. Mudar a letra na tabela refaz o
desenho.

**Solver.** Newton com o passo de menor norma (`Δ = −Jᵀ(JJᵀ + μI)⁻¹F`), derivada numérica e
continuação (a cota que muda muito anda aos poucos, para o desenho não pular para outra forma). O
mesmo método está em Python e em JS, equação por equação; os testes conferem que os dois dão os mesmos
números. Em Python ele resolve centenas de desenhos de uma vez.

**Regiões.** Linhas e arcos que dividem pontas formam contornos; o círculo é um contorno sozinho;
contorno dentro de contorno é furo. Contornos não podem se cruzar nem encostar: apare os dois lados ou
use Unir (U). Área, centro e inércias saem do contorno pelo teorema de Green, com os
arcos exatos; J, Cw e o resto continuam na malha da prancheta antiga.

**Testar o desenho.** Para cada letra, até onde ela pode ir sem a forma deixar de existir (furo
encostando na borda, contorno do avesso, cotas que não cabem), e a parede mais fina de agora.

**A prancheta antiga (Desenho simples) foi aposentada.** O que ela fazia entra no esboço: os
modelos ("Começar de um modelo", com as medidas logo abaixo), os perfis do catálogo e as seções salvas
por ela, que abrem como esboço de um contorno só, sem cotas.

## Edição como num CAD (marco 2)

Arquivo: `components/esboco/edicao.js` (funções puras, testadas no Node com o solver).

- **Aparar (X), estender (W), dividir.** Aparar tira o trecho entre os cortes em volta do clique; o
  ponto novo do corte fica preso à curva que cortou, ou reaproveita o ponto que já está ali. É assim
  que dois contornos que se cruzam viram um só: apara-se um lado, depois o outro. Círculo aparado
  vira arco.
- **Filete (G) e chanfro.** No canto de duas linhas; o raio (ou a distância) aceita letra. O canto
  continua como ponto virtual nas duas retas, para as cotas que apontavam para ele.
- **Deslocar (O).** Uma fila de linhas e arcos, para o lado do clique: cada reta nova é paralela com
  a distância em cota (letra t = espessura), cada arco novo é concêntrico, com o raio pela cota do
  original ± t ou pela tangência às retas vizinhas.
- **Espelhar (S).** Com simetria viva: cada ponto copiado fica simétrico ao original pela linha.
- **Padrões em fila e em círculo.** Passo em letra; as cotas repetidas ficam escondidas.

## Testar o desenho (marco 2)

Embaixo do esboço, em quatro abas:

- **Até onde vai:** a faixa em que cada letra mantém a forma, e a faixa de teste (de, até, passo), que
  vai junto da seção salva e é a faixa padrão da busca do Montador.
- **Varredura:** área, inércias, W ou parede mais fina ao longo de uma letra.
- **Regras de projeto:** desigualdades com as letras e as medidas `parede`, `area`, `largura` e
  `altura` (por exemplo `parede >= 1,5*d`). O desenho que fura uma regra deixa de existir no teste e no
  Montador, com o motivo.
- **Configurações:** a tabela de projeto, com uma linha por conjunto de valores e a conta de cada uma.

## Núcleo do desenho, mais perto de um CAD

- **Arrastar e juntar.** Ponto arrastado até outro ponto vira um ponto só; até uma curva, fica preso
  nela ("ponto na curva"). Um anel laranja mostra onde vai juntar antes de soltar. Pontos vizinhos na
  mesma curva não se juntam (a curva sumiria).
- **Tab entre cotas.** Com a caixinha de uma cota aberta, Tab confirma e abre a próxima (Shift+Tab, a
  anterior).
- **Inferências ao desenhar linha.** Além de deitada e em pé: tangente ao arco de onde a linha sai,
  perpendicular à linha de onde sai, e paralela ou perpendicular a uma linha próxima (até 120 px do
  traço). O sinal aparece ao lado do mouse e a linha de referência fica acesa; ao clicar, a restrição
  entra.
- **Duplo clique numa curva** escolhe o contorno inteiro (as curvas ligadas pelas pontas).
- **Copiar, colar, mover e girar.** Ctrl+C e Ctrl+V colam onde o mouse estiver, com as restrições e
  cotas de dentro (o "fixo" não vai junto). "Mover e girar" (menu do Deslocar) anda em x e y e gira em
  volta do meio da escolha ou da origem, com ou sem cópia. No giro, deitada e em pé trocam entre si de
  90° em 90°; noutro ângulo viram paralelas e perpendiculares, e as cotas horizontais e verticais viram
  alinhadas, para a peça não deformar.
- **Medir** (menu da Cota): uma curva, ou dois pontos ou curvas, mostra a medida sem criar cota
  (distância com as projeções, comprimento e ângulo da linha, diâmetro e perímetro, raio e arco,
  ângulo).
- **Conflito no desenho.** Quando uma mudança não fecha, quem briga fica em vermelho (cotas e sinais) e
  a faixa de baixo oferece "só medir" (a cota vira referência) ou "Apagar" (a restrição sai); a mudança
  é refeita sem quem brigava. Fechar encolhendo uma curva até o tamanho zero (deitada e em pé na mesma
  linha, por exemplo) também conta como conflito.
- **Rasgo e polígono regular** (menu ao lado do arco): o rasgo sai com as quatro tangências e os dois
  raios iguais; o polígono, com os vértices num círculo de construção e os lados iguais (3 a 24 lados).
- **Unir contornos (U, no menu do Aparar).** Contornos que se encostam ou se cruzam viram uma peça só,
  sem aparar à mão: as curvas são partidas nos encontros e sai o que ficou com aço dos dois lados (de
  dentro) ou repetido (a borda comum). Contorno que não encosta em nada fica como está, e furo solto
  continua furo. Cotas de trechos que saíram são avisadas.
- **Cotas que se arrumam.** Texto de cota que cai em cima de outro desce (ou sobe) até ficar livre; só
  na tela, o lugar guardado não muda.
- **Tangente com ponta comum.** Reta e arco que dividem a ponta usam "raio em pé na reta" em vez de
  "distância ao centro = raio": a forma é a mesma, mas a ponta deixa de aparecer como grau livre (o
  filete e o rasgo saem com a conta certa de graus livres). Igual no Python e no JS.
- **Arcos na tela.** O sentido do arco no SVG estava trocado (o filete aparecia "para dentro"); as
  contas não mudam, só o desenho na tela.
- Depois de clicar num botão da barra ou da faixa, as teclas voltam para o desenho.

## O que entra no esboço (marco 3)

Arquivos: `core/esboco_uniao.py` e `core/esboco_dxf.py`.

- **União das formas.** Modelos, perfis do catálogo e seções antigas são feitos de chapas que se
  encostam (o I são três). Antes de virar esboço, as bordas são partidas onde se encontram e fica só
  o trecho que separa aço de vazio: aço é estar dentro de alguma forma cheia e fora de todo furo. As
  retas que ficaram em fila viram uma só. Os 17 modelos antigos saem com a mesma área da conta antiga
  (nos círculos, a conta antiga usava polígono) e com o mesmo reconhecimento de forma (I soldado, U,
  T, tubo...), menos "2 cantoneiras em T", que tem folga entre as duas e por isso são dois pedaços.
- **Perfil do catálogo.** Com o desenho vazio, entra sozinho; com algo desenhado, encosta no lado
  escolhido, como contorno à parte, e o aviso lembra o Unir (U) para virar uma peça só.
- **DXF.** Pelo `ezdxf` (MIT): retas, arcos, círculos, polilinhas com os trechos curvos (bulge) e
  blocos explodidos; elipses e splines entram como filas de retas, com aviso. Textos, cotas e
  hachuras ficam de fora e são contados. A unidade vem do cabeçalho ($INSUNITS) e tudo vira mm; sem
  unidade, lê como mm. Escolhem-se as camadas, e o meio do desenho pode ir para a origem. Pontas que
  caem no mesmo lugar (1e-5 do tamanho) viram um ponto só, e é assim que as retas soltas formam
  contornos. Até 600 curvas: acima disso, a prancheta pede para tirar camadas. DWG não entra (formato
  fechado): a mensagem manda salvar como DXF no próprio CAD.
- **Cisalhamento nas junções.** Sem chapas separadas, o q da solda sai de V·Q/I nas alturas em que a
  largura pula (alma e mesa), pelas faixas da seção (`core/geometria_da_secao.py`).
- O "Trazer a seção aberta" do Cálculo de peças e a página Calor no tempo passaram a ler a seção do
  esboço (antes liam a da prancheta antiga, mesmo com o esboço aberto).
