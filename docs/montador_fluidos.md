# Mecânica dos fluidos

É a segunda parte do programa. A primeira cuida de materiais, estática e fadiga, e continua como
estava. Esta usa o mesmo motor e a mesma prancheta do Montador (`docs/montador_formulas.md`), com
outros blocos, outras unidades e outros modelos. O que está escrito lá sobre o inspetor, os conjuntos,
salvar, registrar e referências vale igual aqui.

## Como se usa

A fila é **Fluido → trechos → perdas → verificação → Em função de**. O fio ciano leva a linha: o fluido,
a vazão e os trechos somados. Cada bloco acrescenta o dele, e por isso a ordem dos trechos não muda a
perda total. Os 13 modelos prontos abrem com números de exemplo.

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

## Blocos

- **Linha:** fluido, trecho de tubo, perdas localizadas.
- **Verificações:** carga disponível, altura da bomba, potência da bomba, NPSH, velocidade máxima.
- **Equações:** pressão na profundidade, força em superfície plana, empuxo, arrasto, orifício ou
  venturi, canal (Manning) e golpe de aríete.

## Bomba, peças e tubos comerciais

- **Curva da bomba:** acha o ponto de operação, onde a curva da bomba cruza a do sistema. A curva é a
  parábola H = H_0 − a·Q², ajustada pelos pontos do catálogo da bomba digitados no inspetor (dois ou
  mais). Abaixo da resposta sai o gráfico das duas curvas, com o ponto marcado.
- **Peças:** no inspetor das perdas localizadas, a tabela soma o K das curvas, tês, registros,
  válvulas, entrada e saída. São valores típicos de peça aberta: variam com o diâmetro e o fabricante.
- **Tubo comercial:** no trecho, preenche D com o diâmetro interno do aço Sch 40 (ASME B36.10M) ou do
  PVC soldável (ficha técnica da linha soldável, NBR 5648). Tubo de PVC com rugosidade de aço recebe
  aviso. "Escolher do catálogo" testa todos e devolve o menor que passa.

## Exemplos conferidos

A Central de validação refaz estes exemplos com os blocos, a cada abertura:

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
- Escoamento permanente, incompressível e monofásico.
- Golpe de aríete pela fórmula de Joukowsky, com fechamento rápido.
- Manning em canal retangular, com regime uniforme.
- Resultado de pré-dimensionamento: não substitui o projeto da instalação nem a curva do fabricante.
