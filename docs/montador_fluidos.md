# Mecânica dos fluidos

É a segunda parte do programa. A primeira cuida de materiais, estática e fadiga, e continua como
estava. Esta usa o mesmo motor e a mesma prancheta do Montador (`docs/montador_formulas.md`), com
outros blocos, outras unidades e outros modelos. O que está escrito lá sobre o inspetor, os conjuntos,
salvar, registrar e referências vale igual aqui.

## Como se usa

A fila é **Fluido → trechos → perdas → verificação → Em função de**. O fio ciano leva a linha: o fluido,
a vazão e os trechos somados. Cada bloco acrescenta o dele, e por isso a ordem dos trechos não muda a
perda total. Os 17 modelos prontos abrem com números de exemplo.

Para um segundo trecho parecido, selecione o trecho e use Ctrl+C e Ctrl+V: ele entra antes da
verificação com D₂, L₂ e ε₂ iguais aos do primeiro, marcados como cópia, e é só mudar o que for
diferente, com dois cliques no número do cartão. As perdas localizadas usam a velocidade do trecho de
antes delas: apagar o primeiro trecho, com as perdas logo depois dele, deixa as perdas sem trecho, e a
página avisa.

## O que a conta faz

**Perda de carga.** Darcy-Weisbach em cada trecho, h_f = f·(L/D)·V²/(2·g), mais K_L·V²/(2·g) nas perdas
localizadas. O fator de atrito é 64/Re no laminar e Colebrook no turbulento, resolvido por ponto fixo a
partir de Haaland. Entre Re 2300 e 4000 a conta interpola, porque ali o escoamento não é previsível.

**Isolar.** Com f dentro da equação não existe forma fechada para Q nem para D: a página mostra a equação
e acha a raiz por número, como no Montador de materiais.

**Fluidos e rugosidades.** Vêm de tabelas de valores típicos, e o valor aparece como "Tabela: ...". Dá
para digitar por cima.

**Fluido pela temperatura.** As opções "pela temperatura (CoolProp)" do bloco Fluido tiram ρ, μ e a
pressão de vapor da CoolProp, na temperatura T_f e na pressão absoluta p_f. A temperatura entra em °C,
K ou °F (botão Unidades) e pode ser a letra pedida: até quantos graus a bomba não cavita, por exemplo. A
água a 20 °C dá o mesmo da tabela até a 4ª casa. Se o líquido ferve na pressão da linha, ou a temperatura
sai da faixa do fluido, a página avisa. Detalhes e a lista dos fluidos em `docs/montador_formulas.md`,
"Propriedades pela CoolProp".

**Ligar com o térmico.** O botão **Abrir esta montagem no Montador de processos** leva a linha inteira
para a página que liga os dois, onde ela recebe o estado de um bloco térmico e devolve a perda de carga
para a corrente (`docs/montador_processos.md`).

## Blocos

- **Linha:** fluido, trecho de tubo, perdas localizadas, peças pelo Crane.
- **Verificações:** carga disponível, altura da bomba, potência da bomba, NPSH, gás no tubo, válvula
  de controle, velocidade máxima.
- **Equações:** pressão na profundidade, força em superfície plana, empuxo, arrasto, orifício ou
  venturi (C informado ou pela ISO 5167), canal (Manning) e golpe de aríete.

Com o fluido escolhido, a biblioteca esconde o que não serve para ele: com gás, a bomba, o NPSH, o
golpe e a válvula de controle; com líquido, o gás no tubo (`core/montador_uso.py`).

## Bomba, peças e tubos comerciais

- **Curva da bomba:** acha o ponto de operação, onde a curva da bomba cruza a do sistema. A curva é a
  parábola H = H_0 − a·Q², ajustada pelos pontos do catálogo da bomba digitados no inspetor (dois ou
  mais). Abaixo da resposta sai o gráfico das duas curvas, com o ponto marcado.
- **Peças:** no inspetor das perdas localizadas, a tabela soma o K das curvas, tês, registros,
  válvulas, entrada e saída. São valores típicos de peça aberta: variam com o diâmetro e o fabricante.
- **Tubo comercial:** no trecho, preenche D com o diâmetro interno do tubo. Aço carbono pela ASME
  B36.10M (Sch 10, 40, 80 e 160, STD, XS e XXS), inox pela ASME B36.19M (Sch 10S, 40S e 80S), de 1/2
  a 24 pol, com as tabelas da biblioteca `fluids`, e PVC soldável (ficha técnica da linha soldável,
  NBR 5648). Tubo de PVC com rugosidade de aço recebe aviso. "Escolher do catálogo" testa os tubos das
  séries marcadas e devolve o menor que passa.

## Peças pelo Crane, gás, válvula de controle e medidores

- **Peças pelo Crane:** o bloco soma K·V²/(2·g) como as perdas localizadas, mas o K de cada peça é o do
  Crane (Flow of Fluids, TP-410): K = n·f_T, com f_T do escoamento todo turbulento em tubo de aço novo
  do diâmetro do trecho de antes. Por isso o K muda quando o diâmetro muda, e o diâmetro pode ser a
  letra pedida. Cotovelos, curvas de r/D 1, 1,5 e 3, tês, registro de gaveta, válvulas de globo,
  angular, de esfera, macho e borboleta, retenções de portinhola e de levantamento, entrada e saída. As
  contas são as da biblioteca `fluids`; abaixo de Reynolds 4000 a página avisa.
- **Gás no tubo:** gás em tubo longo, em temperatura constante (Crane TP-410; Menon). A pressão que
  chega no fim precisa ser pelo menos p_s:
  p_s² + G²·(p₁/ρ₁)·(f·L/D + 2·ln(p₁/p_s)) ≤ p₁², com G = ṁ/A e a vazão Q medida na entrada. Pede um
  gás pela temperatura no Fluido (ar, nitrogênio ou metano, que faz as vezes do gás natural). Avisa
  quando a saída chega ao limite do escoamento isotérmico (Mach 1/√κ).
- **Válvula de controle:** o K_v que a válvula precisa ter pela IEC 60534-2-1, para líquido em
  escoamento turbulento e válvula do tamanho do tubo: K_v = Q·√((ρ/ρ₀)/Δp), Q em m³/h, Δp em bar e
  ρ₀ da água a 15 °C. Acima de Δp_máx = F_L²·(p₁ − F_F·p_v), com F_F = 0,96 − 0,28·√(p_v/p_c), o
  líquido cavita dentro da válvula e a vazão para de subir: a conta usa Δp_máx e a página avisa. A
  pressão crítica sai da CoolProp quando o fluido vem pela temperatura.
- **Orifício ou venturi:** a opção Medidor escolhe o C. Informado, como antes; placa de orifício pela
  ISO 5167-2, com o C de Reader-Harris/Gallagher (tomadas de canto, de flange ou a D e D/2), que muda
  com β e com Reynolds, e por isso a vazão sai por iteração; ou venturi clássico pela ISO 5167-4, com o
  C fixo da norma (0,995 usinado, 0,984 fundido, 0,985 de chapa soldada). Com gás, entra a
  expansibilidade ε da norma, com κ. Fora dos limites da norma (β, D, d e Re_D), a página avisa.

## Exemplos conferidos

A Validação do projeto refaz estes exemplos com os blocos, a cada abertura:

| Exemplo | Fonte | Resultado |
|---|---|---|
| Perda num tubo de 0,5 m, Q = 0,416 m³/s | Maurer, exemplo 4.1 | h_f = 0,61 m |
| Vazão com h_f = 0,6 m | Maurer, seção 4.5.2 | Q = 0,413 m³/s |
| Diâmetro com Q e h_f | Maurer, seção 4.6.2 | D = 0,501 m |
| Ponto de operação da bomba | Maurer, exemplos 7.1 a 7.3 | Q = 12,05 pés³/s, H = 53,3 pés |
| Lâmina num canal retangular | Maurer, exemplo 5.10 | y = 0,498 m e 1,180 m |
| Força na comporta, 6 m de água | Maurer, exemplo 3.3 | F_h = 176.268 N |
| NPSH disponível | Omni Calculator | 7,41 m |
| Golpe de aríete | Joukowsky | 2,4 MPa |

Os blocos que vêm de norma batem com a biblioteca `fluids` chamada direto, até a 6ª casa
(`tests/test_montador_fluidos_biblioteca.py`): K de cada peça pelo Crane, tubos da ASME, vazão de gás
isotérmico (`isothermal_gas`), K_v da IEC 60534 com e sem cavitação (`size_control_valve_l`) e vazão
dos medidores da ISO 5167, com líquido e com gás (`differential_pressure_meter_solver`).

O livro aberto de Maurer (Hydraulics and Water Resources: Examples Using R) congela o atrito na curva do
sistema do exemplo da bomba. O caso de aceite faz o mesmo; na prancheta, Colebrook é refeito a cada
vazão, e a vazão sai cerca de 6 % maior. As propriedades da água foram conferidas em duas tabelas
(saturação pela IAPWS) e as rugosidades na tabela de Moody.

## Como acrescentar uma equação

Basta um `Bloco` em `core/montador_fluidos.py`, com `dominio=mb.FLUIDOS`. Letra nova vai em
`core/montador_grandezas.py`. O teste de coerência das unidades passa em todos os blocos das duas
partes: multiplica cada grandeza por um fator de escala e confere se a resposta escala junto.

## Limites

- A linha é em série. Redes com ramais e malhas não estão no modelo.
- Escoamento permanente, incompressível e monofásico, menos o bloco Gás no tubo e a
  expansibilidade dos medidores.
- A válvula de controle é só para líquido; gás pela IEC 60534 ainda não está.
- Golpe de aríete pela fórmula de Joukowsky, com fechamento rápido.
- Manning em canal retangular, com regime uniforme.
- Resultado de pré-dimensionamento: não substitui o projeto da instalação nem a curva do fabricante.
