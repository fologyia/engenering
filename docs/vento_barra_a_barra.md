# Vento barra a barra — viga a viga, pilar a pilar (NBR 6123:2023, capítulo 8)

Na página **Vento em estruturas abertas**, o botão **"Viga a viga, pilar a pilar"** troca o método
dos pórticos regulares pelo cálculo em cada barra do modelo. Serve para qualquer forma: duas colunas
com a plataforma em balanço, escada ao lado, passarela, estrutura assimétrica — onde imaginar quatro
pilares e pórticos iguais daria um resultado que não é o da estrutura.

Arquivos: `core/vento_por_barras.py` (cálculo, plano de cargas, CSV),
`core/vento_por_nivel.py` (força em cada nível e forma simplificada),
`core/vento_por_barras_registro.py` (memorial), `components/vento_barras_ui.py` e
`components/vento_barras_help.py` (página), `components/figuras_vento.py` (desenhos 3D, planta e
"o que o vento vê"), `components/desenho_svg.py` (peças de desenho comuns).

## De onde vêm as barras

- **Esqueleto do modelo**: o `…_esqueleto.csv` da macro do SolidWorks (página Cargas do esqueleto),
  com as pontas de cada barra, as duas medidas da seção e a direção da maior (a alma, macro v5).
  O mesmo cálculo alimenta o **Contraventamento de estruturas abertas** (seletor "Viga a viga, pilar
  a pilar"), levado aos pisos por faixas (`core/contraventamento_vento_barras.py`).
  As chapas ficam de fora: piso deitado não pega vento e chapa em pé pode ser só apoio de carga do
  modelo — a página lista as chapas em pé para o engenheiro decidir.
- **Digitar**: uma tabela com as pontas (X, Y, Z do modelo, em m), as medidas da seção (mm) e o eixo
  da alma (X, Y, Z, "da macro" ou "não sei", que usa a medida maior de qualquer lado).

O eixo vertical do modelo (Y no SolidWorks) converte o modelo para a planta do programa (X e Y
horizontais, Z para cima): com o Y para cima, (X, Y, Z) do modelo vira (X, −Z, Y). É a mesma
convenção do plano de cargas e da exportação: W0 sopra para +X, W90 para +Y da planta.

## A força em cada barra

1. **Área de sombra** (8.3: projeção da barra num plano perpendicular ao vento):
   `A = ℓ·sen θ·c` — θ é o ângulo entre o vento e o eixo da barra e `c` a largura da seção vista pelo
   vento, `c = d·|s·v| + b_f·|t·v|` (s = direção da alma, t = a outra, v = perpendicular ao vento e ao
   eixo). Viga ao longo do vento: sen θ = 0, força nula (8.5).
2. **Vento perpendicular às faces** (0°, 90°, 180°, 270° — o que 8.5 pede para reticulados): as barras
   perpendiculares ao vento (|cos| ≤ 0,05) são agrupadas em planos a até 0,25 m um do outro ao longo
   do vento. Cada plano tem `φ = ΣA/contorno` (retângulo das barras com meia largura de folga) e o
   `C_a` da Figura 12. Para o plano k, o anterior (k − 1, imediatamente a barlavento) dá
   `η = Figura 14(φ_{k−1}, e/h_b)`, com `e` = afastamento e `h_b` = menor lado do contorno do plano
   anterior; só a **fração da barra que fica atrás desse contorno** recebe o η (8.4, "partes
   protegidas"): `η_ef = 1 − fração·(1 − η)`. Barras fora dos planos: `C_a = 2,0`, η = 1.
3. **Vento diagonal** (45°, 135°, 225°, 315°, opcional): verificação a mais, a favor da segurança —
   `C_a = 2,0` (o maior da Figura 12) e sem proteção. Costuma dar mais força que os perpendiculares
   por isso; a NBR 6123 (8.5) pede só os perpendiculares para estruturas reticuladas retangulares.
4. **q** de cada barra é o da cota do seu ponto mais alto, medida do terreno (o pé dos pilares, ou a
   cota informada). `F = C_a·η·q·A`; a carga é uniforme na barra, `F/ℓ` em kN/m, na direção do vento,
   com as componentes X e Y.

Na grade regular, o resultado bate com o método dos pórticos a menos de 5 % (o contorno de cada
plano inclui a meia largura das barras; teste `test_grade_regular_da_o_mesmo_que_os_porticos`).

## Guarda-corpos, escadas, painéis e equipamentos

- **Guarda-corpo, lateral de escada, painel**: reticulado plano com a linha da base (duas pontas), a
  altura e o φ (0,30; 0,50; 1,0 de referência). `F = C_a(φ)·q·φ·h·L·sen θ` (C_a = 2,0 no diagonal),
  sem proteção. Vai para as **vigas sob a linha** (horizontais, na cota da base, paralelas e a até
  0,35 m), dividida pelo trecho que cada uma apoia, como kN/m na viga inteira; sem viga, para a barra
  mais próxima, com aviso. Pode-se escolher a barra.
- **Equipamento**: caixa (`C_a = 2,0`, largura vista `l_x·|sen θ| + l_y·|cos θ|`) ou cilindro vertical
  (Tabelas 27 e 28, base apoiada: ℓ/d dobra), com o q do topo; vai como força total (kN) na barra
  mais próxima do centro da base (no SolidWorks: Força › Por item na viga).

Com o esqueleto, a tabela de elementos já abre com um guarda-corpo em cada borda livre do piso,
na viga que o apoia (`core/guarda_corpo_do_modelo.py`; os trechos, a altura e o φ se ajustam em
Cargas do esqueleto). No guarda-corpo de escada o q é o da ponta de cima.

## A força em cada nível (`core/vento_por_nivel.py`)

A carga barra a barra não mostra "quanto vento chega na plataforma" — a seção **Força do vento em
cada nível** mostra, em cada direção:

- **Níveis**: as cotas onde o esqueleto tem vigas deitadas (vigas a menos de 15 cm uma da outra, na
  vertical, formam um nível), a 0,5 m ou mais do terreno. Um patamar de escada é um nível (não há o
  filtro de 25 % do comprimento que o contraventamento usa para os pisos). Abaixo de 0,5 m é a base.
- **Das barras às pontas**: cada barra manda metade do vento dela para cada ponta (barra biapoiada);
  a parcela de guarda-corpo, escada, painel e equipamento vai às pontas da barra que o apoia. Ponta
  que cai no meio de outra barra em pé (a mão francesa no pilar) passa às pontas dessa barra pela
  regra da alavanca, até chegar a um nível (até 15 cm dele) ou à base (até 25 cm do terreno). Ponta
  solta (um poste que não chega a nada) vai pela faixa de altura, com aviso.
- **O que sai**: F_x e F_y de cada nível, a linha do modelo por onde a força passa (a componente X
  num y da planta, a Y num x — em coordenadas do SolidWorks, com o Y da planta = −Z) e a **base**, que
  vai direto à fundação. Níveis + base = a força total da direção (conferido em estruturas sorteadas).
  O nível com mais vigas (a plataforma) aparece em destaque, uma métrica por direção.

No esqueleto real do usuário (Simulador, 15/10; plataforma a 3,35 m, patamar a 1,92 m, mãos
francesas e escada): W0 = 4,72 kN na plataforma, 1,42 kN no patamar e 1,90 kN na base; nenhuma
ponta solta.

## Forma simplificada (poucas cargas no SolidWorks)

"Como aplicar o vento no modelo" em **Levar ao projeto**:

- **Barra a barra**: cada barra com a carga dela (a viga com o vento dela e o do guarda-corpo vira uma
  linha só — antes eram duas e a conferência do plano avisava "aparece duas vezes").
- **Simplificada**: em cada nível, a componente X de cada força das pontas vai às **linhas de vigas
  em X** do nível (vigas deitadas alinhadas a menos de 10°, agrupadas a menos de 15 cm em y) pela
  regra da alavanca na coordenada y — a de fora do vão, pelas duas linhas da ponta (fração negativa
  na de longe) —, e a componente Y às linhas em Y pela coordenada x. Cada viga da linha recebe
  `q = F_linha/L_linha` ao longo do eixo dela. **A força e a torção de cada nível ficam as do
  cálculo barra a barra** (conferido em teste); sai do modelo só a flexão local de cada barra pelo
  vento dela, e a maior (w⊥·ℓ²/8) aparece na página. Com uma linha só numa direção, a torção que
  fica de fora vira aviso (a partir de 0,05 kN·m); nível sem vigas na direção do vento não aceita a
  forma simplificada (os botões ficam desligados e a página diz por quê).
- No esqueleto real: **50 cargas de vento no estudo barra a barra → 14 na simplificada** (uma por
  viga e eixo; cada caso só muda o valor).

As combinações não se digitam no SolidWorks: o programa combina os casos primários (Esforços do
modelo) e o arquivo do Gerenciador de casos de carga já leva todas — a página e o Plano de cargas
dizem isso.

## Saídas

- Resumo por direção (barras, elementos, F_x, F_y, tombamento, torção em torno do centro da planta).
- A força em cada nível (acima), na página e no memorial.
- Desenhos: estrutura em 3D com a cor da carga de cada barra e as setas; planta com a alma dos
  pilares, os planos (R1 = barlavento) e o η; "o que o vento vê" (as sombras, com os planos).
- Tabelas: barra a barra, elementos, reticulados; CSV.
- **Enviar ao plano de cargas**: W0, W90, W180, W270 (e W45, W135, W225, W315 se calculados) na
  forma escolhida (barra a barra ou simplificada); o CSV segue a forma. Enviar de novo só os
  perpendiculares tira os diagonais antigos.
- **Registrar**: o memorial traz o resumo, a força em cada nível, os reticulados, a carga de cada
  barra em cada direção e os elementos.

## Fora do escopo

Efeitos dinâmicos (capítulo 9); muros, placas e coberturas isoladas (Tabelas 23 a 25: módulo Vento
nas estruturas); chapas do esqueleto como superfície (entram como painel); as combinações (saem do
plano de cargas). A estabilidade de uma estrutura sem contraventamento numa direção (duas colunas
numa linha, por exemplo) vem do engaste na base ou do pórtico — verificar pelo modelo (Esforços do
modelo), não pelo Contraventamento de estruturas abertas, que supõe linhas contraventadas.

## Testes

`tests/test_vento_por_barras.py` (sombra, coluna isolada à mão, grade × pórticos, proteção parcial,
diagonal, torção da plataforma em balanço, guarda-corpo, cilindro × método dos pórticos, plano de
cargas, uma linha por barra, CSV, esqueleto com Y para cima, validação, registro),
`tests/test_vento_por_nivel.py` (níveis com patamar, metade em cada ponta, mão francesa pela
alavanca, patamar da escada, ponta solta, 25 estruturas sorteadas sem perder força, força e torção
da forma simplificada, linha única, nível sem vigas, flexão local, coordenadas do SolidWorks) e
`tests/test_vento_barras_pagina.py` (ajuda, desenhos em todas as direções, força por nível e forma
simplificada até o plano pelo AppTest).
