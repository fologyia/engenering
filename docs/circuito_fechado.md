# Circuito fechado

Página `app_pages/circuito_fechado.py`, menu Mecânica › Térmica. Você desenha o circuito de
resfriamento (ou de aquecimento), com ramais em paralelo, e a página dá:

- a vazão de cada ramal e a pressão de cada ponto;
- as temperaturas em regime permanente;
- o circuito no tempo, em animação, da partida a frio até estabilizar.

**Onde está cada parte:**

- `core/circuito.py`: o desenho, as peças e a hidráulica;
- `core/circuito_termico.py`: as peças térmicas, o regime e a conta no tempo;
- `core/circuito_cenas.py`: as verificações, as marcas no desenho, a animação e o registro;
- `components/prancheta_circuito/`: a prancheta.

## Desenho

- **Tubo:** clique num ponto e no seguinte; no vazio, o ponto nasce ali. Para fechar a volta, volte
  ao primeiro ponto.
- **Peças** (bomba, fonte de calor, dry cooler, chiller, válvula, filtro, tanque pulmão): escolha a
  peça e clique em cima de um tubo. O tubo vira tubo – peça – tubo, e a peça herda o diâmetro dele.
- **Vaso de expansão:** fica num ponto.
- **Ramais:** um tubo que sai de um ponto e chega a outro.
- **Sentido:** a bomba empurra no sentido em que o tubo foi desenhado; ⇄ inverte.
- **Apagar:** uma peça volta a ser tubo, e o circuito continua fechado.
- **Dados:** clique na peça ou no ponto e o painel ao lado mostra os dados dele. As tabelas
  completam as cotas e os tubos.

Depois da conta, o desenho mostra a vazão, o calor, a temperatura de saída e a pressão. Os tubos
ficam na cor da temperatura, e o que não passa fica em vermelho.

## Hidráulica

- **Equações:** a energia em cada elemento (H_de − H_para + H_bomba = perda) e a continuidade em
  cada ponto, resolvidas juntas pelo método de Newton, como na Rede de tubos.
- **Pressão:** a carga do ponto do vaso é fixa (a pressão de enchimento). Num circuito fechado é o
  vaso que fixa a pressão, e sem ele a página recusa a conta.
- **Perdas:**
  - tubos por Darcy-Weisbach (f do Montador de fluidos) mais ΣK;
  - peças pela perda do catálogo na vazão do catálogo (Δp ∝ Q²);
  - válvula pelo K.
- **Bomba:** curva de dois pontos, H = H₀ − (H₀/Q_máx²)·Q·|Q|. Parada, ela tem retenção.
- **Avisos:** bomba atravessada ao contrário e ramal que não fecha volta.

## Peças térmicas

- **Fonte de calor:** põe a potência no fluido. A massa do equipamento esquenta junto (inércia).
- **Dry cooler:**
  - o UA sai do ponto do catálogo (capacidade, vazões de líquido e de ar, temperaturas) pelo ε-NTU
    de fluxo cruzado com os dois lados não misturados (Incropera eq. 11.33);
  - um ponto de catálogo impossível (eficácia acima da máxima) é recusado;
  - ventilador: sempre ligado, liga e desliga (±1 K) ou proporcional;
  - com rotação menor, C_ar ∝ rotação e UA ∝ rotação^0,6.
- **Chiller:** tira o calor que leva a saída à temperatura ajustada, até a capacidade. A potência
  elétrica sai pelo COP. Quando a capacidade não dá, aparece um alerta.
- **Tubo:** perda para o ar pelo isolamento e pela película de fora, se marcada.
- **Tanque pulmão:** volume bem misturado, com UA para o ar.

## Regime permanente

O método de Newton anda nas temperaturas dos pontos. Em cada ponto entra a mistura do que chega; em
cada elemento vale a curva dele, que pode saturar:

- o ventilador para abaixo do ajuste e vai a 100 % quando não dá conta;
- o chiller desliga abaixo do ajuste e fica na capacidade máxima quando não dá conta.

O passo é encurtado até o resíduo cair. No fim, o balanço de energia confere: o que as fontes põem,
as peças tiram. Sem nada que tire calor, a página diz que não há regime.

## No tempo

- Cada tubo vira células por onde o fluido passa, cada peça vira um volume bem misturado e os
  pontos fazem a mistura.
- É implícito no tempo, com o fluxo fixo da hidráulica. As fontes, o dry cooler e o chiller ficam
  explícitos, com o controle ideal.
- O ar e a carga das fontes podem variar hora a hora.
- A duração automática cresce até o circuito estabilizar com folga.
- Vaso de expansão: a dilatação é V·(ρ₀/ρ − 1), somada em todas as células, sem a dilatação dos
  tubos (a favor da segurança). O ar do vaso segue p·V constante a partir da pré-carga.
- O volume mínimo do vaso segue o ASHRAE (vaso de membrana): V = ΔV·p_máx·p_ench/(p₀·(p_máx −
  p_ench)), com as pressões absolutas.

## Verificações

- **Pressões:** mínima em cada ponto (frio e quente), abaixo da qual entra ar; máxima no vaso.
- **Vaso:** volume suficiente.
- **Tubos e bomba:** velocidade em cada tubo; NPSH da bomba (pressão de vapor da água, a favor da
  segurança com glicol).
- **Temperaturas:** saída de cada fonte (regime e pico da partida).
- **Controles:** chiller no limite e dry cooler que não segura o ajuste aparecem como alerta.

## Testes

`tests/test_circuito_fechado.py`:

- **Hidráulica:**
  - o anel contra o encontro da curva da bomba com Darcy feito à mão;
  - os ramais em paralelo, com a mesma perda e a vazão somando;
  - os erros de desenho.
- **Peças:**
  - o dry cooler reproduz o ponto do catálogo;
  - o chiller segura o ajuste;
  - sem nada que tire calor, não há regime;
  - chiller no limite com dry cooler depois.
- **Regime e tempo:**
  - o balanço de energia fecha;
  - a conta no tempo termina no regime;
  - o vaso pela fórmula do ASHRAE.
- **Saídas:** a cena, as marcas e o registro.
- **Prancheta e página:**
  - a prancheta no Node (peça no meio do tubo, apagar, vaso, inverter);
  - a página com o painel mudando o desenho.

## Limites

- **Fluxo:** fixo na conta térmica (a vazão estabiliza em segundos) e propriedades numa temperatura
  média.
- **Hidráulica:** sem golpe de aríete nem a partida da bomba.
- **Peças:** dry cooler sem dados do fabricante para outras rotações (expoente 0,6); chiller e
  ventilador com controle ideal, sem a dinâmica do controlador.
