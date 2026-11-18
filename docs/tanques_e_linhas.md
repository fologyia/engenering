# Tanques e linhas no tempo

Página `app_pages/tanques_e_linhas.py`, menu Mecânica › Fluidos. São quatro abas em animação, com
o tocador descrito em `docs/calor_no_tempo.md`. As contas ficam em `core/tanque_no_tempo.py` e
`core/linha_no_tempo.py`; as cenas e os registros, em `core/fluidos_cenas.py`.

## Tanque: nível

- **Tanque:** cilíndrico vertical, retangular ou cilíndrico horizontal. No horizontal, a área do
  líquido muda com o nível.
- **Nível e entrada:** nível inicial e vazão de entrada constante.
- **Saída:**
  - orifício no fundo: Torricelli, Q = C_d·A·√(2gh), com C_d = 0,61 de borda viva (Çengel e
    Cimbala, cap. 8);
  - tubo descarregando livre: energia h + z = (1 + f·L/D + ΣK)·v²/2g, com o f de Darcy do
    Montador;
  - bomba de vazão fixa;
  - nenhuma.
- **Conta:** dV/dt = Q_e − Q_s(h). Anda no volume, e não na altura, para o tanque horizontal não
  ter singularidade no fundo e no topo. É integrada pelo solve_ivp com controle de erro.
- **Tabelas:** a vazão do tubo e a altura do tanque horizontal saem de tabelas calculadas de uma
  vez (o f é iterado para todos os níveis juntos).
- **Para quando:** esvazia (1 mm de líquido: pelo tubo, no fim, o escoamento fica laminar e o
  último milímetro levaria um tempo sem fim), enche (aviso de transbordar) ou estabiliza (a 0,5 %
  do nível de equilíbrio, onde a saída iguala a entrada).

### Vasos comunicantes

A saída "Tubo para outro tanque" liga o fundo do tanque 1 ao de um tanque 2 (cilíndrico vertical,
com a cota do fundo dele):

- A água passa do nível mais alto para o mais baixo pela energia do tubo de ligação (atrito,
  peças e saída), integrada nos dois volumes.
- O tempo de equalização vai até as duas superfícies ficarem a 1 mm. No fim o escoamento fica
  laminar, e o último milímetro levaria um tempo sem fim.
- A cota final iguala as superfícies guardando o volume total, e os testes conferem com a conta à
  mão.
- Se um tanque esvazia ou transborda antes, a página para ali e avisa.

## Desenhos e marcos

- **Setas:** as brancas andam nos tubos no sentido da água, mais rápidas com mais vazão. As laranja
  são o calor: aquecimento, perda pela parede do tanque, perda do tubo para o ar.
- **Símbolos:** bomba (círculo com triângulo), válvula (dois triângulos), agitador, isolamento
  hachurado, régua de nível, jato do orifício e cotas.
- **Marcos nos gráficos:** esvazia, transborda ou estabiliza; equaliza; chega ao alvo; 95 % e 99 %
  da partida; trânsito L/v e estabilização da saída do tubo; o termostato segurando.

## Tanque: temperatura

- **Modelo:** tanque bem misturado e de massa constante,
  m·c·dT/dt = P + UA_s·(T_s − T) + ṁ·c·(T_e − T) − UA_p·(T − T_amb).
- **Solução:** com tudo constante a equação é linear e tem solução exata,
  T = T_eq + (T₀ − T_eq)·e^(−t/τ).
- **Aquecimento:** resistência (potência fixa) ou serpentina/camisa (UA e temperatura da fonte).
- **Perda e vazão:** perda pela parede (UA) e vazão que passa.
- **Termostato (opcional):** ideal. Ao chegar à temperatura dele, o aquecimento só repõe o que sai.
- **Água:** ρ e c_p pela CoolProp na temperatura inicial. Se a água chegar a 100 °C ou a 0 °C, a
  conta para ali e avisa (a 1 atm ela ferve ou congela).

## Partida da linha

- **Modelo:** coluna rígida (Wylie e Streeter, cap. 2),
  (L/(gA))·dQ/dt = Δz + H_b(Q, s) − (1 + f·L/D + ΣK + K_v)·Q·|Q|/(2gA²).
- **Abrir a válvula:** a área de passagem cresce em linha reta, s = t/t_a, com K_v = K_aberta/s².
- **Ligar a bomba:** a rotação cresce em linha reta, e a curva segue a semelhança,
  H_b = s²·H₀ − (H₀/Q_máx²)·Q².
- **Resultado:** a vazão de regime, os tempos para 95 % e 99 % e o tempo de ida e volta da onda,
  2L/a.
- **Aviso:** quando a manobra não é ao menos 10 vezes mais lenta que 2L/a, a coluna rígida não vê
  as ondas de pressão. As vazões valem, mas as pressões pedem a conta com a onda (golpe de aríete).
- **Desenho:** o tubo tem a cor da velocidade, e os traços andam com ela.

## Água quente chegando

Um tubo cheio de água parada recebe, no instante zero, água a outra temperatura.

- **Transporte:** a água anda com a velocidade média. A cada passo (Δt = Δx/v) ela anda uma célula,
  e o transporte é exato.
- **Troca com a parede:** a troca célula a célula entre água e parede é resolvida exata no passo
  (exponencial da matriz 2×2).
- **Película de dentro:** h por Gnielinski (Re ≥ 3000, com o f de Petukhov) ou Nu = 3,66 (laminar
  desenvolvido) (Incropera, cap. 8). Na transição a página avisa.
- **Parede:** guarda calor (massa e c do material) e perde para fora pelo isolamento e pela película
  de fora.
- **Regime permanente:** T_s = T_amb + (T_e − T_amb)·e^(−L/(ṁ·c·R')), com R' das resistências em
  série. É a conta do tubo isolado do Montador térmico, mais a película de dentro.
- **Resultado:** o tempo para a saída chegar à temperatura pedida e a água que sai fria até lá.

## Testes

`tests/test_tanques_e_linhas.py`:

- **Tanque:**
  - orifício contra Torricelli exato;
  - nível de equilíbrio;
  - tempo de encher;
  - volume do tanque horizontal;
  - saída por tubo contra a integração direta e a energia fechando.
- **Temperatura:**
  - a exponencial exata;
  - o balanço m·c·dT/dt;
  - o termostato;
  - a água que ferve.
- **Partida:**
  - a energia de regime;
  - a tangente hiperbólica (abertura instantânea com f constante);
  - o encontro das curvas da bomba.
- **Tubo:**
  - o regime permanente contra as resistências;
  - a frente no tempo de trânsito sem parede;
  - Gnielinski igual ao da biblioteca `ht`;
  - o isolamento.
- **Cenas, registros e página:** cenas e registros válidos; a página com as quatro abas.

## Limites

- **Tanque de nível:** líquido incompressível, saída em regime quase permanente, bomba sem NPSH.
- **Tanque de temperatura:** bem misturado, parede sem capacidade térmica, UA constantes.
- **Partida:** coluna rígida (sem onda de pressão), reservatório de nível fixo, saída livre.
- **Tubo:** água com a velocidade média (sem perfil nem mistura ao longo do tubo), parede com a
  temperatura igual na espessura, isolamento sem capacidade térmica.
