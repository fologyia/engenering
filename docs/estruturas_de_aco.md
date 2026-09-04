# Estruturas de aço — escopo e hipóteses

Esta área organiza cinco ferramentas de pré-dimensionamento:

1. catálogo geométrico de perfis;
2. verificação de barras isoladas;
3. combinações editáveis de ações;
4. ligações parafusadas, chapas e soldas;
5. análise elástica linear de treliças e pórticos 2D.

## Catálogo de perfis

Os perfis são idealizações sem raios de concordância, tolerâncias ou
propriedades certificadas de fabricante. O programa calcula área, massa,
momentos de inércia, módulos elásticos e plásticos, raios de giração, constante
de torção e área aproximada de cisalhamento.

Antes do projeto executivo, o perfil deve ser substituído pelas propriedades
da tabela oficial do fabricante.

## Barras

O módulo inclui:

- escoamento da seção bruta e ruptura da seção líquida em tração;
- flambagem elástica nos dois eixos e curva de redução em compressão;
- plastificação da seção e momento crítico elástico de flambagem lateral;
- resistência ao cisalhamento;
- interação entre força axial e flexão biaxial;
- flecha de viga biapoiada ou em balanço.

Os fatores `Q`, `Cv`, `Cb`, `Kx`, `Ky` e os coeficientes de resistência são
entradas do usuário. Eles dependem da geometria, vínculos e norma.

## Combinações

O gerador cria:

- ELU fundamental, alternando a ação variável principal;
- ELS rara;
- ELS frequente;
- ELS quase permanente.

Os coeficientes `γ`, `ψ0`, `ψ1` e `ψ2` são editáveis. Os valores iniciais são
exemplos e não podem ser aplicados automaticamente a qualquer edificação.

## Ligações

São verificadas:

- resistência de parafusos à tração e ao cisalhamento;
- interação tração–cisalhamento;
- pressão de contato e rasgamento junto ao furo;
- deslizamento por atrito;
- ruptura da seção líquida;
- cisalhamento de bloco;
- solda de filete.

Não estão incluídos efeito alavanca, base de pilar, chumbadores, ligação
semirrígida, distribuição não linear, fadiga de solda ou qualificação do
procedimento de soldagem.

## Análise 2D

O solver usa o método matricial da rigidez:

- treliça plana: dois graus de liberdade por nó;
- pórtico plano: dois deslocamentos e uma rotação por nó;
- cargas nodais;
- carga distribuída uniforme no eixo local do elemento de pórtico;
- deslocamentos, reações e esforços de elemento.

A análise é linear de primeira ordem. Não inclui `P–Δ`, imperfeições,
plasticidade, flambagem, cabos, apoios elásticos ou ligações semirrígidas.

## Referências normativas

O escopo foi organizado em torno da ABNT NBR 8800:2024, da ABNT NBR
8681:2025, da ABNT NBR 6120:2019 e da ABNT NBR 6123:2023. O programa não
reproduz integralmente essas normas e não certifica conformidade.
