# Mecânica dos fluidos

É a segunda parte do programa. A primeira cuida de materiais, estática e fadiga, e continua como
estava. Esta usa o mesmo motor e a mesma prancheta do Montador (`docs/montador_formulas.md`), com
outros blocos, outras unidades e outros modelos. O que está escrito lá sobre o inspetor, os conjuntos,
salvar, registrar e referências vale igual aqui.

## Como se usa

A fila é **Fluido → trechos → perdas → verificação → Em função de**. O fio ciano leva a linha: o fluido,
a vazão e os trechos somados. Cada bloco acrescenta o dele, e por isso a ordem dos trechos não muda a
perda total. Os 13 modelos prontos abrem com números de exemplo.

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
