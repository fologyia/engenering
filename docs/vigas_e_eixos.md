# Vigas e eixos

Este documento registra as convenções, equações e limites do módulo
`Vigas e eixos` (`core/beam_analysis.py` e `core/beam_script.py`).

## Convenções

- `x` cresce da esquerda para a direita; `y` é positivo para cima;
- forças transversais e cargas distribuídas são **positivas para cima**;
- momentos concentrados são positivos no sentido anti-horário (`+z`);
- a força axial é positiva em `+x`; o esforço normal interno `N` é positivo
  quando traciona a seção;
- `V` é positivo quando gira o trecho à esquerda no sentido horário;
- `M` é positivo quando comprime a fibra superior ("barriga para baixo");
- a flecha `v` é positiva para cima, coerente com `E I v'' = M`;
- unidades internas: N, mm, MPa e N·mm. A interface e a linguagem de texto
  usam m, kN, kN·m, kN/m, mm, GPa e MPa.

## Modelo numérico

A barra é resolvida por **rigidez direta**. São criados nós em toda
descontinuidade — apoios, rótulas, cargas concentradas, momentos, torques e
os extremos de cada carga distribuída. Como consequência, dentro de um
elemento a carga distribuída é sempre uma única função linear.

Cada nó tem quatro graus de liberdade desacoplados em três sistemas:

| Sistema | Graus de liberdade | Matriz elementar |
| --- | --- | --- |
| Flexão | `v`, `θ` | Euler-Bernoulli 4×4 |
| Axial | `u` | `EA/L · [[1,−1],[−1,1]]` |
| Torção | `φ` | `GJ/L · [[1,−1],[−1,1]]` |

O vetor de engastamento perfeito de uma distribuída linear `w(ξ)` que vai de
`w_i` a `w_j` ao longo do elemento de comprimento `L` é:

```text
Fy_i = L (7 w_i + 3 w_j) / 20
Mz_i = L² (3 w_i + 2 w_j) / 60
Fy_j = L (3 w_i + 7 w_j) / 20
Mz_j = − L² (2 w_i + 3 w_j) / 60
```

Para a distribuída axial `a(ξ)`:

```text
Fx_i = L (2 a_i + a_j) / 6
Fx_j = L (a_i + 2 a_j) / 6
```

### Rótulas internas

Uma rótula é implementada por **duplicação do grau de liberdade de rotação**
no nó: o elemento à esquerda e o da direita passam a ter rotações
independentes, e o momento fletor resulta nulo naquele ponto sem nenhuma
equação de restrição adicional. Uma rótula sobre um apoio que impede a
rotação é recusada, porque os dois se anulariam; uma rótula na extremidade
também é recusada, porque ali a rotação já é livre.

## Recuperação analítica dos esforços

Os deslocamentos nodais de Euler-Bernoulli com vetor consistente são
**exatos**. A partir dos esforços de extremidade `f = k u − f_eq` do
elemento, com `f = [Fy_i, Mz_i, Fy_j, Mz_j]`, o programa avalia os campos
internos em forma fechada (com `Δw = (w_j − w_i)/L`):

```text
V(x) = Fy_i + w_i x + Δw x² / 2
M(x) = Fy_i x − Mz_i + w_i x² / 2 + Δw x³ / 6
θ(x) = θ_i + [ Fy_i x²/2 − Mz_i x + w_i x³/6 + Δw x⁴/24 ] / (E I)
v(x) = v_i + θ_i x + [ Fy_i x³/6 − Mz_i x²/2 + w_i x⁴/24 + Δw x⁵/120 ] / (E I)
```

Verifica-se `dM/dx = V(x)` e `E I v'' = M(x)`. A linha elástica é, portanto,
a integração analítica de `M(x)/EI`, **não** uma interpolação do gráfico nem
um refinamento de malha.

Para os demais sistemas:

```text
N(x) = − Fx_i − (a_i x + Δa x² / 2)
u(x) = u_i + [ − Fx_i x − a_i x²/2 − Δa x³/6 ] / (E A)
T(x) = constante no elemento
φ(x) = φ_i + T x / (G J)
```

### Amostragem e extremos

Além de pontos igualmente espaçados, a malha de saída inclui as raízes
analíticas de `V(x) = 0` (quadrática) e de `θ(x) = 0` (quártica) dentro de
cada elemento. Assim o momento máximo e a flecha máxima caem **exatamente**
sobre uma amostra, em vez de dependerem da densidade da malha. O extremo
reportado é o valor de maior módulo, com o sinal preservado.

Nos nós há dois valores por grandeza — o do elemento à esquerda e o do
elemento à direita —, o que reproduz corretamente os saltos de `V` sob carga
concentrada e de `M` sob momento aplicado.

## Tensões combinadas

O cálculo das tensões em um ponto **não vive neste módulo**: está em
`core/section_stress.py`, compartilhado com o assistente de cargas
(`core/load_to_stress.py`). As duas páginas do programa precisam responder a
mesma coisa para a mesma seção, e manter duas cópias da fórmula é o caminho
mais curto para elas divergirem em silêncio quando uma for corrigida.

```text
σ_axial = N / A
σ_sup   = N/A − M c_sup / I
σ_inf   = N/A + M c_inf / I
τ_V     = V Q / (I t)        (ou V / A_v quando Q não é conhecido)
τ_T     = T / W_t
```

`W_t` é o **módulo de torção**, não `J/c`: em seções retangulares e em
perfis abertos a tensão máxima de torção não vale `T c / J`. Para a seção
retangular maciça usa-se a aproximação de Roark, `W_t = a² b² / (3a + 1.8b)`
com `a ≥ b`; para seções fechadas de parede fina, Bredt (`W_t = 2 A_m t`);
para perfis abertos, `W_t = J / t_máx`.

O critério é avaliado em **três pontos** de cada seção e o programa reporta o
pior deles:

| Ponto | σ | τ |
| --- | --- | --- |
| Fibra superior | `σ_sup` | `τ_T` |
| Fibra inferior | `σ_inf` | `τ_T` |
| Linha neutra | `N/A` | `τ_V + τ_T` |

```text
σ_VM     = sqrt(σ² + 3 τ²)
σ_Tresca = sqrt(σ² + 4 τ²)
```

Isso evita o erro clássico de somar a flexão máxima com o cisalhamento
máximo: onde `|M|` é máximo o cisalhamento de `V` é nulo na fibra extrema, e
na linha neutra a tensão de flexão é nula.

## Apoios (Tabela 12.1)

| Tipo | Impede | Consequência no ponto |
| --- | --- | --- |
| `rolete` | vertical | `Δ = 0`, `M = 0` |
| `pino` | vertical, horizontal, torção | `Δ = 0`, `M = 0` |
| `engaste` | vertical, horizontal, rotação, torção | `Δ = 0`, `θ = 0` |
| `engaste deslizante` | horizontal, rotação, torção | `θ = 0`, `V = 0` |
| `apoio horizontal` | horizontal | trava axial pura |
| `mola` | nada por si só | a restrição vem de `kv` e/ou `kr` |
| extremidade livre | nada | `V = 0`, `M = 0` |

O apoio elástico soma `kv` (N/mm) e `kr` (N·mm/rad) à diagonal da matriz de
rigidez, e sua reação vale `−k u` — a mola reage contra o deslocamento.
Informar `kv` num apoio que já impede o deslocamento vertical (ou `kr` num
que já impede a rotação) é recusado: a rigidez seria silenciosamente inútil,
porque naquele grau o deslocamento é zero.

O grau de hiperestaticidade é reportado como
`incógnitas de reação − 3 − número de rótulas`.

A meta de fator de segurança usada para concluir "atende / não atende" vem
de `criterios_projeto.seguranca.fator_seguranca_minimo` do projeto ativo, e
vai junto no registro para o memorial poder repetir a mesma conclusão.

## Diagnóstico de instabilidade

Antes de resolver, o programa compara o posto da submatriz livre com sua
dimensão. Um posto menor indica mecanismo, e a quantidade de movimentos de
corpo rígido é informada na mensagem de erro — em vez de devolver uma
solução numérica sem sentido ou uma exceção de álgebra linear.

Nos sistemas axial e de torção, quando não há restrição alguma **e** a
resultante aplicada é nula, o programa ancora um nó apenas como referência e
avisa: os esforços internos são autoequilibrados e não dependem dessa
escolha. Se a resultante não for nula, o modelo é recusado.

## Conferência de equilíbrio

`conferir_equilibrio` soma reações e cargas aplicadas e devolve os resíduos
de `ΣFy`, `ΣFx`, `ΣM` e `ΣT`. É um controle numérico do próprio solver,
exibido na interface: valores muito acima do zero de máquina indicam
problema no modelo ou no condicionamento.

## Segunda ordem (P–Δ) e carga crítica

Com `segunda_ordem` no modelo, a matriz de rigidez da flexão passa a ser
`K = K_e + K_g`, onde `K_g` é a rigidez geométrica consistente do elemento
sob esforço normal:

```text
K_g = N/(30 L) ·
[[ 36,    3L,  -36,    3L ],
 [ 3L,  4L²,  -3L,   -L² ],
 [-36,   -3L,   36,   -3L ],
 [ 3L,   -L²,  -3L,  4L² ]]
```

`N` positivo é tração: tração enrijece a barra à flexão, compressão a
amolece. Por isso o **esforço normal é resolvido antes da flexão** — neste
modelo o axial não depende da flecha, então uma única passagem basta e não
há iteração a fazer.

O programa também resolve `K_e φ = λ (−K_g) φ` e reporta o **fator de carga
crítica**: o multiplicador das cargas *axiais* que levaria o modelo à
flambagem elástica. Um fator 3,2 quer dizer que a compressão poderia
triplicar antes da instabilidade. Quando o fator fica abaixo de 10 e a
segunda ordem está desligada, o resultado traz um aviso; quando a carga já
passou da crítica, a análise é recusada em vez de devolver um número sem
significado.

### Malha

A rigidez geométrica converge com o refino, e a solução de primeira ordem
**não**: os deslocamentos nodais de Euler-Bernoulli são exatos em qualquer
malha. Por isso o refino é gratuito em precisão e só custa tempo — e é
aplicado sempre que há carga axial, não apenas quando a segunda ordem está
ligada. Com um elemento por trecho, a carga crítica de uma coluna biapoiada
sai `12EI/L²` em vez de `π²EI/L²`, ou seja **21,6% alta** — e alto é
exatamente o lado inseguro. Com oito divisões o erro cai para 0,003%.

`divisoes n` refina ainda mais, quando se quer conferir a convergência.

### Limites

A segunda ordem aqui parte da barra perfeitamente reta: imperfeições
geométricas iniciais e desaprumo não são considerados, e as normas costumam
exigi-los. A flambagem lateral com torção e a flambagem local também
continuam fora do escopo.

## Casos de carga e envoltória

Cada carga pertence a um **caso**, declarado com `caso=<nome>`; sem isso ela
é `Permanente`. Uma `combinacao` atribui um fator a cada caso, e um caso
ausente da combinação entra com fator **zero** — a combinação declara o que
participa dela.

`analisar_envoltoria` resolve a barra uma vez por combinação e monta a
faixa envelopada. Duas decisões importam:

* **A malha é a mesma em todas as combinações.** Geometria, apoios e
  posições de carga não mudam; só as intensidades são escaladas. A
  envoltória é montada sobre a interseção das abscissas, porque cada
  combinação ainda acrescenta as raízes de `V(x)=0` e `θ(x)=0` da sua
  própria solução, que naturalmente não coincidem.
* **Os extremos governantes vêm dos resultados completos**, não da malha
  comum: assim o pico continua exato, em vez de arredondado para a amostra
  mais próxima. Para cada grandeza, a envoltória guarda **qual** combinação
  governou — que raramente é a mesma para todas.

Um caso citado numa combinação mas ausente do modelo é recusado com a lista
do que existe: o efeito silencioso seria a parcela simplesmente não entrar.
A comparação de nomes ignora maiúsculas, para uma letra trocada não zerar
uma carga.

O peso próprio é permanente. Quando a combinação aplica um fator diferente
de 1,0 ao permanente, ele é materializado como distribuída antes de ser
escalado, para não duplicar a fórmula do peso.

`linhas_de_combinacoes_do_projeto` converte as combinações do projeto ativo
em linhas de `combinacao`, trocando o **id** do caso pelo seu **nome** — que
é o que as cargas do modelo usam em `caso=`.

## Memorial

`core/report_plugins.py` registra o provedor `vigas_eixos`, que entra no
memorial depois dos registros técnicos com as barras analisadas, os esforços
e deslocamentos governantes com a seção em que ocorrem, a verificação de
resistência e de serviço, as reações de apoio e — quando há combinações — a
tabela de qual delas governa cada grandeza.

O gancho de extensão do memorial precisou ser corrigido para isso: as seções
`registros` e `sensibilidade` são anexadas diretamente, sem passar por
`adicionar`, então um provedor registrado com `apos="registros"` era
silenciosamente descartado. Agora `anexar_extensoes` é chamada
explicitamente ao fim dessas seções.

## Repasse para os outros módulos

`estado_plano_da_secao(resultado, x_mm, ponto=...)` converte qualquer seção
da barra no mesmo `EstadoPlanoCalculado` que o assistente de cargas entrega
ao Círculo de Mohr e à Análise estática. É o que permite levar a seção
crítica adiante sem redigitar nada, com o vínculo de origem preservado — a
Central de Validação passa a marcar o cálculo de destino como
"Desatualizado" quando a viga muda.

Funções de apoio:

| Função | Para que serve |
| --- | --- |
| `ponto_em(resultado, x_mm)` | Ponto do diagrama em `x`; numa descontinuidade devolve o lado mais solicitado |
| `secoes_notaveis(resultado)` | Abscissas de cada grandeza governante (M máx, V máx, von Mises…) |
| `estado_plano_da_secao(...)` | Estado plano `(σx, 0, τxy)` da seção, no ponto governante ou em um nomeado |
| `amplitudes_de_fadiga(...)` | Par `(σa, σm)` para a Análise de fadiga |

Sobre a fadiga: num **eixo girante** cada fibra passa por tração e compressão
a cada volta, então a flexão é totalmente alternada (`σa = |M| c/I`) e a
parcela axial permanece como tensão média. Numa **viga fixa** o mesmo momento
é estático: `amplitudes_de_fadiga(..., eixo_girante=False)` devolve amplitude
zero e joga tudo na média, em vez de inventar um ciclo que não existe.

## Fora do escopo

- imperfeições geométricas iniciais e desaprumo — a segunda ordem, quando
  ligada, parte da barra perfeitamente reta;
- flambagem local ou lateral com torção (a flambagem global por flexão
  aparece no fator de carga crítica);
- deformação por cisalhamento (viga de Timoshenko) — em vigas curtas
  (`L/h < 10`) a flecha real é maior que a calculada aqui;
- empenamento restringido na torção (só torção uniforme de Saint-Venant);
- flexão oblíqua: o modelo é plano, em torno de um único eixo principal;
- seção variável ao longo do comprimento;
- concentração de tensão em furos, entalhes, mudanças de seção e rasgos de
  chaveta;
- fadiga, fluência, impacto e temperatura — os esforços saem daqui pelo
  repasse, mas a verificação é do módulo próprio;
- ligações e apoios reais — engaste, pino e rolete são idealizados.

Para perfis monossimétricos do catálogo (U, C, T) mantém-se `c = altura/2`,
a mesma convenção já usada em `sx_mm3` de `core/steel_sections.py`. É uma
aproximação: a fibra mais distante do centroide real fica subestimada.

## Linguagem de texto

O interpretador de `core/beam_script.py` lê uma instrução por linha. Tudo
depois de `#` é comentário. Espaço e ponto e vírgula sempre separam campos;
a vírgula separa apenas quando **não** está entre dois dígitos, de modo que
`viga 4,5` continua sendo um decimal em português e `apoio 0, pino` continua
tendo dois campos.

O sufixo de sentido (`baixo`, `cima`, `tracao`, `compressao`) inverte o
sinal do valor digitado, para quem prefere informar só a intensidade.

Todo erro traz o número da linha, o texto original e o que era esperado.
O modo formulário gera exatamente o mesmo script, de modo que as duas
entradas compartilham parser e validações — não há dois caminhos que possam
divergir.

## Referências

- Hibbeler, R. C. *Resistência dos Materiais* — diagramas de esforço
  cortante e momento fletor, linha elástica, cargas combinadas e a tabela de
  condições de contorno reproduzida na interface.
- Shigley, J. E. *Mechanical Engineering Design* — eixos sob flexão e
  torção combinadas.
- Roark, R. J. *Formulas for Stress and Strain* — constante e módulo de
  torção de seções não circulares.
