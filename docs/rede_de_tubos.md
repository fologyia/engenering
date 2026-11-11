# Rede de tubos

Página do grupo Mecânica, submenu Fluidos (`app_pages/rede_de_tubos.py`), com o núcleo em
`core/rede_de_tubos.py`, sem Streamlit. A linha do Montador de fluidos é em série, com a mesma vazão
em todos os trechos; aqui a água se divide nos ramais e as malhas se fecham.

## Como se usa

A rede se **desenha** na prancheta (`components/prancheta_rede/`, componente do Streamlit em JS),
a planta vista de cima, em metros, com grade e ímã:

- **Reservatório:** clique onde ele fica (nível da água fixo; começa com 20 m).
- **Nó:** clique onde a água é consumida. Em cima de um tubo, o nó divide o tubo em dois
  (`dividirTrecho`): os dois ficam com os dados do original, o comprimento real informado se divide
  na proporção do desenho e a bomba fica num só.
- **Tubo:** clique num nó e no seguinte; no vazio, o nó nasce ali. A ferramenta continua do último
  nó, como uma polilinha; Esc, duplo clique ou o botão direito terminam. O tubo novo copia o diâmetro
  e o material do último.
- **Selecionar:** clique num nó ou num tubo para ver e mudar os dados dele no painel ao lado;
  arraste um nó para mover (os tubos vão junto); arraste o fundo para andar. Delete apaga (o nó leva
  os tubos dele), Ctrl+Z e Ctrl+Y desfazem e refazem, a rodinha aproxima.

O **comprimento** de cada tubo é o do desenho. O comprimento real só se informa quando o desenho é
um esquema fora de escala ou o tubo sobe, desce ou dá voltas que a planta não mostra.

As **tabelas** embaixo são os mesmos nós e tubos, só para completar o que o desenho não dá: cotas,
vazões, diâmetros, materiais, rugosidade ("Outro"), K das peças e bomba. Elas não criam nem apagam:
isso é no desenho.

Com a conta feita, o **resultado volta ao desenho** (`marcas_para_o_desenho`): seta no sentido da
água com a vazão e a velocidade, a pressão em cada nó e o nível e a vazão de cada reservatório; o que
não passa fica em vermelho.

Os dados ficam em `rede_dados` (nós com id, nome, tipo, x, y, cota, nível e retirada; tubos com id,
nome, de, para, comprimento real, diâmetro, material, rugosidade, K e bomba), e a prancheta, o painel
e as tabelas os mudam por callback, com `rede_versao` contando as mudanças, como no Equilíbrio de
uma peça. `rede_do_desenho` faz a rede da conta e diz o que falta preencher.

- **Limites:** pressão mínima e máxima em metros de coluna do fluido (usual em rede de abastecimento:
  10 e 40 m.c.a.) e velocidade máxima. A pressão máxima confere a maior entre a estática (rede parada,
  com o nível do reservatório mais alto) e a dinâmica.

## A conta

- Em cada trecho, a energia: H_de − H_para + H_bomba = (f·L/D + ΣK)·v·|v|/(2g), com f pela mesma
  `fator_de_atrito` do Montador (64/Re no laminar, Colebrook no turbulento, reta na transição, com
  aviso). Com vazão nula, Hagen-Poiseuille, para a conta continuar lisa.
- Em cada nó de consumo, a continuidade: o que entra menos o que sai é a retirada.
- Tudo junto pelo método de Newton nas vazões e nas cargas (método do gradiente de Todini e Pilati,
  o do EPANET), com o passo encurtado enquanto o resíduo não cai. A derivada da perda é numérica,
  e por isso vale também no laminar. Na resposta, a soma das perdas em cada malha fecha em zero
  (`soma_nas_malhas`, pelo espaço nulo da matriz de incidência): é a condição de Hardy Cross, sem
  precisar achar as malhas à mão.

## O que a página confere antes

Nó com nome repetido ou vazio, rede sem reservatório, trecho que liga nó que não existe ou que volta
ao mesmo nó, comprimento ou diâmetro zero, rugosidade ou K negativos e nó sem caminho até um
reservatório. Depois da conta: trecho na transição laminar-turbulento, velocidade abaixo da mínima e
água correndo contra uma bomba.

## Testes

`tests/test_rede_de_tubos.py`: um tubo contra Darcy-Weisbach à mão; tubos em paralelo com a mesma
perda; duas malhas e dois reservatórios (malhas fecham, o que entra é o que sai, a energia de cada
trecho, o reservatório mais baixo recebe água); laminar contra Hagen-Poiseuille; bomba; tabelas
erradas; desenho, CSV e registro; a página com o exemplo.

## Limites

Escoamento permanente e incompressível; reservatórios de nível fixo; bomba como altura constante
(sem curva); sem válvula redutora de pressão nem retenção. Para curva de bomba e NPSH, use o
Montador de fluidos.
