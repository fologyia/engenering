# Calor no tempo

Página `app_pages/calor_no_tempo.py`, menu Mecânica › Térmica. Mostra a temperatura andando por
dentro de uma peça que vai para um forno, um banho ou o ar, numa animação com as curvas no tempo ao
lado. São duas abas:

- **Parede, tubo, cilindro ou esfera**: uma dimensão (a espessura), em `core/calor_no_tempo.py`;
- **Seção desenhada**: duas dimensões, numa barra comprida de seção constante, em
  `core/calor_na_secao.py`. A seção é um modelo pronto do Desenhar seção ou a seção que está
  desenhada lá.

A cena do tocador, as figuras do memorial e o registro ficam em `core/calor_cenas.py`.

## O que entra

- **Peça:** a forma e as medidas (mm). Um cilindro ou uma esfera com diâmetro de dentro maior que
  zero é tubo ou esfera oca.
- **Material:** Incropera, Tab. A.1 e A.3, a 300 K (aços, inox, alumínio, cobre, latão, titânio,
  concreto, tijolo, vidro, madeiras), ou k, ρ e c_p informados.
- **Temperatura inicial:** uma só, a da peça inteira.
- **Cada face**, a partir do instante zero, pode ter:
  - convecção (h e temperatura do fluido; o "?" traz as faixas da Tab. 1.1 do Incropera);
  - temperatura fixa;
  - fluxo de calor;
  - face isolada.

  Na seção desenhada há uma condição para o contorno de fora e outra para o contorno dos furos.
- **Duração:** automática (ln(250)·τ, um pouco além de a peça estabilizar) ou informada.
- **Pergunta (opcional):** a temperatura que um ponto precisa alcançar. Com um prazo, vira
  verificação (atende ou não atende).

## Como a conta é feita

### Uma dimensão

- **Espaço:** volumes finitos com 81 nós na espessura, com nós nas faces. Usa a área de cada
  forma: 1 na parede, 2πr no cilindro e 4πr² na esfera. No centro do maciço vale a simetria.
- **Tempo:** Crank–Nicolson com 3000 passos. Os 4 primeiros passos são implícitos (partida de
  Rannacher), que amortecem o salto do instante zero.
- **Duração automática:** sai do modo mais lento da própria malha. O menor autovalor λ de K·v = λ·C·v
  dá τ = 1/λ, e a peça fica a 1 % do regime em ln(100)·τ.
- **Sem regime permanente:** sem convecção nem temperatura fixa (só fluxo e faces isoladas), a
  temperatura sobe sem parar. A página avisa e mostra 2·e²/α.
- **Biot:** Bi = h·(V/A)/k. Abaixo de 0,1 a página avisa que a peça esquenta praticamente por igual
  (capacitância concentrada).

### Conferência com a solução exata

Quando o caso é o dos livros, a página compara com a solução exata em série (Incropera, seção 5.5;
Çengel, cap. 4), com 60 termos e as raízes isoladas sem polos. Os casos são:

- parede com as duas faces iguais;
- parede com uma face isolada e a outra com convecção ou temperatura fixa;
- cilindro ou esfera maciços com convecção ou temperatura fixa.

A diferença nos casos de teste fica abaixo de 0,01 °C.

### Duas dimensões

- **Grade:** células de volumes finitos em linhas que passam pelas bordas das partes; parede fina
  ganha ao menos 3 células na espessura média. Uma célula com metade ou mais de material conta como
  material, e a massa é corrigida para a área de verdade.
- **Contorno curvo ou inclinado:** os degraus das células somariam mais que o contorno de verdade (no
  círculo, 4/π vezes). As bordas retas das partes alinhadas caem em linhas da grade e ficam exatas.
  As curvas são medidas no próprio contorno de cada parte (círculo, retângulo girado, polígono):
  vale o pedaço que separa material de vazio. As faces de degrau são então reduzidas para somar
  esse comprimento, distribuído pela inclinação local (1/(|n_x| + |n_y|)).
- **Furo ou fora:** o vazio ligado à borda da grade é o contorno de fora; o vazio cercado é furo.
- **Tempo:** Crank–Nicolson com fatoração esparsa (scipy) e τ pelo autovalor (eigsh).

## Estabiliza, equaliza e a maior diferença

`ct.marcos` (e `cs.marcos` na seção) dá três tempos, marcados nos gráficos e nas métricas:

- **Estabiliza:** a peça inteira chega a 1 % do regime permanente (do quanto a temperatura muda do
  começo ao fim) e não sai mais dali.
- **Equaliza:** a diferença entre o ponto mais quente e o mais frio cai a 1 % do salto e não volta a
  subir. Só existe quando o regime permanente é por igual (o mesmo fluido ou a mesma temperatura em
  todas as faces). Com fluidos diferentes nas faces, a página diz o gradiente que fica no regime.
- **Maior diferença dentro da peça:** o valor e o instante. É o que dá a tensão térmica (choque
  térmico).

O calor que entra por cada face sai de `ct.fluxos_nas_faces`: h·(T∞ − T_s) na convecção, o fluxo
informado ou a condução do nó da face na temperatura fixa. Na seção, `cs.calcular` guarda a cada
passo o calor que entra pelo contorno de fora e pelos furos. Os testes conferem que a integral desse
calor no tempo é o calor guardado na peça.

## O que a página mostra

- **Métricas:** tempo mostrado, constante de tempo, temperatura no fim ou o tempo para chegar à
  temperatura pedida, o calor que entrou, e em quanto tempo a peça estabiliza e equaliza, com a
  maior diferença dentro dela.
- **Animação:**
  - a peça mudando de cor: faixas na parede, anéis no cilindro e na esfera, a grade na seção;
  - o fluido em volta (e dentro dos furos) na cor da temperatura dele;
  - setas laranja do calor em cada face, que crescem com o fluxo e trocam de sentido quando o calor
    passa a sair;
  - face isolada hachurada, os três pontos das curvas marcados na peça (com as cores das curvas),
    as cotas e quanto falta para o regime permanente;
  - gráfico da diferença dentro da peça;
  - gráfico no tempo dos três pontos (as duas faces e o meio; no maciço, centro, meio raio e
    superfície), com a reta da temperatura pedida;
  - perfil ao longo da espessura, com o começo e o regime permanente tracejados;
  - calor guardado na peça.
- **Conferência e hipóteses:** a conferência com a solução exata e as hipóteses.
- **Registro:** grava no projeto, e o memorial recebe as figuras (`graficos_no_tempo`).

## O tocador

`components/animacao/` (HTML, CSS e JS) e `components/animacao_ui.py`, usados também por Tanques e
linhas no tempo e pela Rede de tubos ao longo do dia.

- **Cena:** `core/animacao.Cena`. Leva as escalas de cor, os canais (um valor por quadro, em
  Float32 base64), as formas e a grade de calor (Uint8 por quadro).
  - Formas: polígono (com hachura e de fundo), linha com traços ou com setas que andam no sentido do
    escoamento, nível de líquido, círculo, texto, seta de valor (calor, vazão) e cota.
  - Gráficos: no tempo, com marcos (estabiliza, equaliza, chega ao alvo), e perfil.
- **Tocar:** o JS só toca. Tem tocar e pausar, barra do tempo e velocidade (em 1× o tempo inteiro
  passa em 10 s). Interpola entre quadros e, com o mouse sobre o desenho, mostra o valor.
- **Gráficos:** clique num gráfico no tempo para ir àquele instante.
- **Sem rodar de novo:** nada volta ao Python, e a página não roda de novo enquanto toca. Com o
  mesmo `id` da cena, o instante fica onde estava; um cálculo novo volta ao começo.
- **Cores:** mapas de um matiz só (calor: do claro ao vermelho escuro; água: do azul claro ao
  escuro) e séries na ordem fixa da paleta.

## Limites

- **Material:** propriedades constantes, sem geração de calor dentro e sem mudança de fase.
- **Condições:** constantes depois do instante zero.
- **Convecção:** h vem de tabela ou de correlação feita fora desta conta. Radiação, se importar,
  entra somada no h.
- **1D:** sem perda pelas bordas (parede larga, cilindro comprido).
- **2D:** sem perda pelas pontas da barra.

## Testes

`tests/test_calor_no_tempo.py`:

- raízes da Tab. 4-2 do Çengel;
- parede, cilindro e esfera contra a série;
- face isolada igual à meia parede simétrica;
- temperatura fixa;
- resistências em série;
- fluxo com energia conservada;
- capacitância concentrada (esfera de cobre);
- tempo para chegar;
- áreas e contornos de verdade da grade (círculo, tubo fino, retângulo girado, furo);
- retângulo igual ao produto das duas paredes (±0,1 °C);
- círculo de cobre com o τ concentrado;
- tubo em regime permanente;
- cena, registro válido e figuras;
- a página, com todo campo com ajuda.

`tests/test_animacao.py` cobre a cena e as contas do JS no Node.
