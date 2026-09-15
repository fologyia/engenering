# Mecânica Toolkit — projetos e análises industriais

Aplicação Streamlit para manter projetos industriais permanentes, registrar
base de projeto e cálculos, controlar pendências, consultar referências e
emitir memoriais modulares em Word e PDF. Os módulos técnicos transformam
cargas em tensões, analisam estados 2D/3D, fadiga e estruturas de aço.

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

O aplicativo abre em `http://localhost:8501`. O menu lateral é organizado em
**Gestão industrial**, **Análises técnicas**, **Dimensionamento complementar**,
**Ferramentas**, **Referências** e **Ajuda**.

### Onde ficam os dados

O banco de projetos (`projetos_industriais.sqlite3`) fica na pasta de dados do
usuário — `%USERPROFILE%\MecanicaToolkit` no Windows,
`~/.local/share/mecanica_toolkit` nos demais sistemas — e não dentro do
repositório: um SQLite numa pasta sincronizada (OneDrive, Google Drive) é a
causa clássica de `database is locked` e de banco corrompido. (No Windows a
pasta fica na raiz do perfil, e não em `%LOCALAPPDATA%`, porque aplicativos
empacotados — o Claude Desktop, ao abrir o programa pela pré-visualização —
enxergam uma cópia privada de `AppData\Local`, e o banco gravado ali some
para o mesmo programa aberto num terminal comum.) Para usar outro arquivo
(banco de equipe, outra pasta local), defina a variável de ambiente
`MECANICA_TOOLKIT_DB` antes de abrir o programa:

```bash
set MECANICA_TOOLKIT_DB=D:\engenharia\projetos.sqlite3
```

Um banco antigo em `data/` é copiado para o novo lugar na primeira abertura e
renomeado para `.migrado`. O **Painel industrial** gera backups íntegros do
banco (`VACUUM INTO`, na pasta `backups/` ao lado do arquivo), exporta a
carteira inteira em JSON — com revisões e linha do tempo — e restaura esse
pacote num banco vazio ou parcial, sem sobrescrever projetos existentes.
Os catálogos (`data/*.json`, `data/materials.csv`) continuam no repositório.

## Interface

- tema técnico em azul-petróleo com barra lateral de alto contraste;
- logotipo próprio, tipografia consistente e ícones Material Symbols;
- cabeçalhos, cartões, indicadores e atalhos padronizados;
- navegação explícita e uma única página de tutoriais;
- indicação do projeto ativo nos cabeçalhos dos módulos.

### Painel industrial

- a carteira inteira numa tela: situação, revisão, prontidão, índice documental,
  bloqueios, pendências, avanço do checklist, prazos vencidos, registros vigentes
  e cálculos desatualizados de cada projeto;
- bloco de **atenção imediata** com os projetos que têm resultado não atendido,
  bloqueio, prazo vencido ou cálculo cuja fonte mudou;
- prazos vencidos e da semana de todos os projetos numa única tabela de cobrança;
- próximos passos sugeridos por projeto, na mesma ordem que a página do projeto
  recomenda, e abertura direta como projeto ativo;
- filtros por situação e cliente, busca por código, TAG ou responsável e
  exportação da carteira em CSV;
- **dados e backup**: caminho do banco em uso, backup íntegro com um clique,
  exportação da carteira inteira em JSON e restauração desse pacote.

### Projetos permanentes

- persistência local em SQLite na pasta de dados do usuário (ver *Onde
  ficam os dados*), configurável pela variável `MECANICA_TOOLKIT_DB`;
- gravações concorrentes detectadas: cada documento carrega o contador de
  gravações do banco, e uma segunda aba (ou outra pessoa num banco
  compartilhado) que tente gravar por cima de uma gravação mais nova é
  recusada com aviso, em vez de sobrescrevê-la em silêncio;
- identificação, cliente, unidade, área, TAG, processo e responsabilidades;
- base de projeto com documentos, carregamentos, condições, critérios e limitações;
- **critérios técnicos** do projeto — fator de segurança mínimo, utilização
  máxima, risco probabilístico, condições de operação, norma principal,
  referência dos fatores e unidades — lidos pelos módulos e pela validação;
  sem eles, vale o padrão do programa, e a validação avisa;
- casos de carga vetoriais, combinações com fatores explícitos e envelopes governantes;
- escopo físico para equipamentos, linhas, estruturas, sistemas e pontos críticos;
- **documentos de entrada** controlados: código, título, tipo, revisão,
  emitente e situação (vigente, aguardando recebimento, superado), com a
  validação apontando revisão ausente e documento superado ainda citado no escopo;
- matriz normativa com edição, aplicação, fonte e conferência no original;
- registros técnicos padronizados com entradas, resultados, premissas, alertas e
  conclusão; tabela de gestão com peça, atualidade das fontes, menor fator e
  utilização; um cálculo refeito **supera** o antigo (sai do memorial padrão e
  das cobranças, fica no histórico) ou pode ser excluído, com aviso sobre os
  cálculos que dependiam dele;
- checklist com responsável, **prazo como data**, estado, evidência e
  criticidade — itens vencidos e a vencer na semana são apontados na página, no
  painel e na validação;
- **modelos de checklist por tipo de projeto** (genérico, estrutura metálica,
  vaso de pressão/tanque, transportador de correia, eixo/elemento de máquina):
  o tipo escolhido na criação semeia a lista de verificação com responsável
  preenchido pelo papel (responsável, verificador, aprovador); um modelo pode
  ser aplicado depois a qualquer projeto sem duplicar itens, e
  `data/modelos_checklist_usuario.json` adapta ou acrescenta modelos da empresa;
- **fluxo de situação com portões**: elaboração → verificação exige verificador
  e um cálculo vigente; verificação → emitido exige aprovador, zero bloqueios e
  nenhum cálculo desatualizado, e cria revisão controlada; reabrir um projeto
  emitido também cria revisão;
- **linha do tempo** com cada salvamento, mudança de situação, registro técnico
  incluído, revisão e emissão de memorial;
- **comparação entre revisões** (ou entre uma revisão e o projeto atual), campo a
  campo, ignorando o que muda sozinho, com exportação em CSV;
- marcos de revisão restauráveis, duplicação, arquivamento, exclusão e
  exportação/importação JSON (com histórico e eventos);
- integração com o Assistente de projeto e com os módulos técnicos.

### Central de validação

- consolida bloqueios, pendências, atenções e informações do projeto inteiro;
- verifica identificação, responsabilidades, base de projeto, escopo físico e materiais;
- aponta referências sem edição ou ainda não conferidas no documento-fonte;
- detecta registros incompletos e critérios numéricos conhecidos, como utilização acima de 1;
- permite transformar um achado em item rastreável do checklist, já com
  responsável e prazo, ou converter todos os bloqueios de uma vez;
- cobra prazos vencidos do checklist, critérios técnicos definidos pelo projeto e
  documentos de entrada recebidos e revisados;
- mostra o que a validação significa para o fluxo (para onde a situação pode ir
  e o que trava cada passagem), resume achados por categoria e exporta a fila em CSV;
- calcula um índice de completude documental, explicitamente separado de conformidade ou aprovação.

### Central de relatórios

- **memorial de cálculo como molde**: os cálculos registrados entram completos
  (entradas, equações, resultados, figuras, premissas e conclusão) e todo campo
  que o programa não conhece sai como `[a preencher]`, localizável com Ctrl+F
  no Word; a conclusão geral e as recomendações ficam para o responsável;
- estrutura enxuta: identificação, resumo executivo, controle de revisões (com
  linhas em branco para as próximas), objetivo e escopo, base de projeto,
  escopo físico, materiais, quadro-resumo dos cálculos, memória de cálculo
  agrupada por peça, vigas e sensibilidade (só quando há registro do tipo),
  conclusão e aprovações — sem validação, checklist, matriz normativa, casos
  e combinações de carga, faixa de situação ou apêndices;
- registros de Círculo de Mohr e de casos de carga não entram no memorial;
  registros superados ficam fora da seleção padrão;
- listas de resultados (reações de apoio, envoltória, esbeltez de paredes,
  ranking de sensibilidade) viram tabelas próprias;
- perfis de memorial completo, memorial de cálculos e resumo executivo, com
  seleção independente das seções e dos registros anexados;
- controle de código, revisão, situação, elaboração, verificação e aprovação;
- Word editável e PDF gerados a partir do mesmo modelo de dados; o PDF usa uma
  fonte TrueType do sistema (Segoe UI, Arial, Calibri ou DejaVu), então σ, τ,
  √ e ≥ saem como o módulo os escreveu;
- provedores de seção independentes, permitindo que novos módulos acrescentem capítulos sem acoplamento ao renderizador;
- cada emissão entra num histórico próprio (documento, revisão, perfil,
  snapshot) e na linha do tempo do projeto.

## Recursos

### Visão geral

- recomenda o módulo a partir dos dados disponíveis;
- dá acesso direto ao projeto guiado e ao conversor;
- resume entradas e saídas de cada área;
- explica o fluxo de cálculo e a leitura dos diagnósticos.

### Assistente de projeto

- organiza o problema em quatro etapas: definição, objetivo, dados e plano;
- valida nome e coerência dos dados antes de avançar;
- recomenda a primeira análise e a sequência completa de módulos;
- mantém um checklist de DCL, geometria, material, cargas, critério e norma;
- mostra uma prévia das entradas já convertidas para a unidade do módulo;
- cria um projeto permanente, prepara o módulo inicial e mantém o roteiro no checklist.

### Conversor global de unidades

- converte 15 grandezas de engenharia;
- contempla unidades SI, usuais de projeto e sistema inglês;
- mostra todas as equivalências da categoria selecionada;
- permite inverter origem e destino para conferência;
- apresenta até seis algarismos significativos sem reduzir a precisão interna;
- destaca as unidades preferidas em cada módulo do aplicativo.

### Análise estática

- tensão equivalente de von Mises em estado plano;
- tensões principais e fatores de segurança;
- círculo de Mohr e gráfico de utilização de Sy e Sut;
- diagnóstico de margem contra escoamento.
- registro rastreável do cálculo no projeto industrial ativo.

### Análise de fadiga

- fatores de Marin para carga, tamanho, superfície, temperatura e confiabilidade;
- modelos de Norton e Shigley;
- concentração e sensibilidade ao entalhe;
- Goodman modificado, Soderberg, curva S–N e estimativa de vida;
- memorial em Word editável, com resumo executivo, referências, premissas, dados de entrada, memória de cálculo completa, resultados, conclusão, controle de revisões e aprovações;
- exportação complementar em PDF para impressão, sem faixa de situação.
- registro padronizado da avaliação no projeto industrial ativo.

### Vigas e eixos

- barra reta com apoios de rolete, pino, engaste, engaste deslizante e trava axial;
- rótulas internas (vigas Gerber) e vãos contínuos isostáticos ou hiperestáticos;
- cargas pontuais, distribuídas uniformes e trapezoidais, momentos concentrados,
  carga axial, carga axial distribuída, torques e peso próprio;
- diagramas de esforço normal, cortante, momento fletor, linha elástica (flecha),
  rotação, torque e ângulo de torção;
- tensões combinadas: N/A ± M·c/I, V·Q/(I·t), T/Wt, von Mises e Tresca avaliados
  na fibra superior, na fibra inferior e na linha neutra (onde τ de V e de T
  somam em módulo — o sentido do torque não pode reduzir a tensão);
- perfis do catálogo com o centroide guardado (U, T, C idealizados e perfis
  cadastrados) ou estimado pela geometria (bitolas T em x e U em y), não com a
  meia altura; módulo de torção por família (Bredt para tubos, Roark para
  barras, J/t_máx só nos perfis abertos) e área de cisalhamento das mesas na
  flexão em torno de y;
- barra comprimida: fator de carga crítica no plano da flexão e estimativa
  fora do plano (eixo de menor inércia), na página, no registro e no memorial;
- posições quase coincidentes (menos de 0,01 % de L) caem no mesmo nó, em vez
  de gerar um elemento minúsculo e um falso "mecanismo"; malha e amostragem
  com teto, seção e material com verificação de plausibilidade (unidades
  trocadas viram erro ou aviso, não tensão absurda);
- verificação de flecha admissível por L/limite e fator de segurança ao escoamento;
- entrada por **texto e números** (uma instrução por linha) ou por formulário —
  os dois modos usam o mesmo interpretador;
- conferência automática do equilíbrio global e exportação dos diagramas em CSV;
- repasse da seção escolhida para o Círculo de Mohr, a Análise estática e a
  Análise de fadiga, com vínculo de origem — sem redigitar tensões;
- casos de carga nomeados e combinações: a barra é resolvida uma vez por
  combinação e o programa desenha a envoltória de V, M e flecha, apontando
  qual combinação governa cada grandeza;
- importação das combinações de carga do projeto ativo;
- material do catálogo do programa ou material qualificado do projeto, com
  o vínculo de rastreabilidade gravado no registro;
- meta de fator de segurança lida dos critérios do projeto ativo;
- efeito de segunda ordem (P–Δ) opcional e fator de carga crítica elástica,
  com aviso quando a compressão se aproxima da instabilidade; os diagramas
  de segunda ordem são recuperados em equilíbrio na configuração deformada
  (M e V contínuos, momento máximo a menos de 0,02 % da solução fechada de
  coluna-viga) e a conferência de ΣM inclui o momento P·Δ;
- capítulo próprio no memorial, com barras, esforços governantes, reações e
  combinações;
- registro rastreável do modelo e dos resultados no projeto industrial ativo.

### Assistente de cargas e geometrias

- barras, eixos maciços e vazados, vigas e seção I;
- flexão biaxial, pinos em cisalhamento e vasos de parede fina;
- conversão de forças, momentos, torque, pressão e dimensões em σx, σy e τxy;
- transferência direta para o Círculo de Mohr;
- avisos sobre as hipóteses de cada modelo.
- gravação do estado de tensões e das hipóteses no projeto ativo.

### Casos e combinações de carga

- cenários permanentes para operação, partida, parada, emergência, teste, transporte, içamento e manutenção;
- forças, momentos, pressão relativa e variação de temperatura em um sistema de eixos comum;
- fatores explícitos vinculados a cada caso, sem atribuição automática de caráter normativo;
- envelope algébrico com combinação governante por componente;
- preservação do vetor completo para evitar misturar máximos não simultâneos;
- registro técnico versionado, rastreado pela validação (o memorial não reproduz casos e combinações).

### Círculo de Mohr e transformação de tensões

- estados 2D e 3D, tensões e direções principais;
- transformação para planos inclinados e tração em plano arbitrário;
- cisalhamento máximo, von Mises, Tresca e Rankine;
- três círculos de Mohr, invariantes e tabelas de transformação.
- registro 2D ou 3D no projeto permanente.

### Flambagem de colunas

- verificação pela **NBR 8800:2008** (método dos estados-limites) para
  qualquer seção (retangular, circular, tubo, perfil do catálogo ou A e r
  diretos): `N_c,Rd = χ·Q·A_g·f_y/γ_a1` com `λ₀ = √(Q·A_g·f_y/N_e)` e a curva
  única de χ (5.3.3), que já embute imperfeições e tensões residuais;
- ações majoradas na própria página (`N_Sd = γ_g·N_g + γ_q·N_q`, Tabela 1) ou
  `N_Sd` já de cálculo; resistência minorada por `γ_a1 = 1,10`;
- forças de flambagem elástica do Anexo E — flexão em x e y, torção (`N_ez`)
  e o modo flexo-torcional das seções monossimétricas — e fator `Q = Q_s·Q_a`
  de flambagem local do Anexo F, com a tabela de esbeltez das paredes;
- K teórico ou **recomendado para projeto** (Tabela E.1) por condição de
  apoio, `Kx ≠ Ky` e `Kz` para torção;
- **flexocompressão** (5.5.1.2): excentricidade da força e/ou momentos de
  cálculo, amplificados por `B_1 = C_m/(1 − N_Sd/N_e)` (Anexo D), contra
  `M_Rd` do Anexo G na equação de interação;
- **mão-francesa**: a força inclinada é decomposta em `H = F·sen θ` e
  `V = F·cos θ`; o momento `M = H·a` (engaste na base), `H·a·(L−a)/L`
  (biapoiada) ou o do engaste com topo apoiado, mais `V·e` da ligação, é
  somado a `M_Sd` automaticamente — o campo não fica em zero;
- **leitura por eixo x-x e y-y**: esbeltez, `N_e`, `λ₀`, `χ`, `N_c,Rd` e a
  interação de cada eixo lado a lado, com o eixo que governa marcado, além
  da verificação normativa pelo menor `N_e`;
- reprovação automática com `KL/r > 200` (5.3.4.1), avisos de K fora da faixa
  física e unidades implausíveis, registro no projeto com o modo governante e
  curva χ·Q·f_y/γ_a1 × λ no memorial.

### Projeto de juntas parafusadas

- roscas métricas de M3 a M36 e classes 4.6 a 12.9;
- pré-carga, dispersão e torque de aperto;
- distribuição de P, V, M e T em grupo circular;
- prova, escoamento, ruptura, separação e deslizamento;
- esmagamento, rasgamento da chapa e fadiga axial opcional.

### Estruturas de aço

- catálogo geométrico de perfis e propriedades de seção;
- barras pela **NBR 8800:2008**: tração (5.2), compressão
  `N_c,Rd = χ·Q·A_g·f_y/γ_a1` com λ₀ e curva única de χ (5.3), flambagem
  elástica por flexão, torção e flexo-torção (Anexo E), fator Q de flambagem
  local (Anexo F, elementos AL/AA e tubos), momento resistente por FLT, FLM
  e FLA com L_p, L_r, M_cr e C_b (Anexo G), cortante (5.4.3), interação N–M
  (5.5.1.2) e limites de esbeltez λ ≤ 200 / 300 — com memória de cálculo
  por estado-limite;
- combinações pela **NBR 8681 / NBR 8800** por categoria de ação (γ_f, γ
  favorável, ψ₀/ψ₁/ψ₂ das Tabelas 1 e 2), ELU normais com permanentes
  favoráveis e ELS rara, frequente e quase permanente;
- ações de plataforma: vento pela **NBR 6123** (S₁ por relevo, S₂ por
  categoria/classe/altura, S₃ por grupo, `q = 0,613·V_k²`, força e carga por
  metro com C_f), guarda-corpo e impacto (NBR 6120 / NBR 14718 / ASCE 7) e
  conformidade de acessos da **NR-12** (guarda-corpo, rodapé, travessas,
  largura, degraus por Blondel, patamares) com critério do cliente;
- ligações parafusadas, chapa, cisalhamento de bloco e soldas;
- placa de base e chumbadores pelo **AISC Design Guide 1** (pressão de contato
  `φ_c·0,85·f_ck·√(A₂/A₁)`, placa em flexão plástica com m, n e λn', momento
  pequeno e grande com tração nos chumbadores, arrancamento, chumbadores por
  AISC J3 com interação tração–cisalhamento), conferido contra os exemplos
  4.1, 4.4 e 4.5 do guia;
- treliças e pórticos 2D pela rigidez direta; no pórtico, **segunda ordem**
  (P–Δ pela rigidez geométrica iterada), carga nocional de 0,3 % (4.9.7.1.1),
  fator de carga crítica global, classificação da deslocabilidade por Δ₂/Δ₁
  (4.9.4.1), coeficiente B₂ (4.9.4.6), rigidez reduzida a 80 % e
  deslocamento horizontal contra H/400;
- registro das combinações, do vento, do guarda-corpo, dos acessos, das
  verificações de barras e das análises 2D no projeto ativo;
- modelo de checklist "Plataforma de acesso / passarela" com o escopo mínimo
  que um verificador cobra (ações completas, modelo global, NBR 8800,
  torção de U, H/400, secundários, ligações e base, NR-12/NR-20, memorial
  sem sobras).

### Catálogo de materiais

- base orientativa do programa, catálogos de critério de projeto distribuídos
  junto do programa e materiais cadastrados pelo usuário, fundidos numa lista só;
- tabela de materiais do critério **Anglo American AA-BR-DPST-DR-0001**
  (Estruturas metálicas, item 4.5): 16 designações com a aplicação que cada
  uma é autorizada a cumprir e a proteção exigida;
- procedência separada: o critério especifica a **designação e a norma**, não
  as propriedades. Sy e Sut vêm da norma citada e ficam marcados como tal —
  nunca atribuídos ao critério. Valores sem mínimo normativo (SAE 1020,
  ASTM A108) são declarados como típicos;
- propriedades mecânicas do catálogo **Gerdau**: 10 aços das duas tabelas de
  propriedades (perfis W e HP; perfis I, U, T e cantoneiras), com alongamento
  e equivalência NBR 7007. A diferença por forma de produto é preservada — o
  mesmo ASTM A572 Gr. 50 vale 345 MPa em perfil W e 350 MPa (AR 350) em
  perfil laminado, e achatar isso apagaria um dado do fabricante;
- filtro por aplicação: responde "que aço posso usar num perfil laminado
  neste projeto" em vez de só listar aços;
- aviso quando dois critérios definem a mesma designação, para o valor de um
  não sobrepor o do outro em silêncio;
- cadastro, edição, exclusão e importação em lote, com aviso de coerência
  (Sy/Sut fora da faixa, unidade em psi, propriedade sem procedência);
- Sy igual a zero é aceito como dado físico: ferro fundido cinzento rompe sem
  patamar de escoamento definido;
- alimenta a seleção de material em análise estática, fadiga e flambagem.

### Catálogo de perfis

- catálogo geométrico embutido, catálogos de referência distribuídos com o
  programa e perfis cadastrados pelo usuário, fundidos em uma lista só;
- 60 perfis W e HP da tabela de bitolas Gerdau — as bitolas correntes, de
  W 150 a W 310 — extraídos por posição na
  página e conferidos por coerência interna (raio de giração contra
  `sqrt(I/A)` e módulo elástico contra `I/(d/2)`, de colunas diferentes da
  mesma linha) — um erro de leitura vira perfil rejeitado, nunca propriedade
  errada entrando em silêncio. Bitolas maiores podem ser importadas pela
  própria página, ou reimportadas com `--altura-maxima`;
- cadastro, edição e exclusão de perfis próprios, com aviso de coerência
  (eixos trocados, massa incompatível com a área, Z/W fora da faixa usual);
- importação em lote colando uma tabela do Excel ou de um CSV, aceita
  parcialmente: uma linha malformada não derruba as outras;
- perfis de referência e embutidos não podem ser excluídos, mas podem ser
  sobrepostos por um perfil próprio de mesmo nome;
- tudo fica disponível em vigas e eixos, flambagem e estruturas de aço.

### Normas técnicas

- catálogo orientativo separado por segurança, estruturas, parafusos, materiais, soldagem, vasos, tolerâncias e elementos de máquinas;
- leitura recursiva da pasta `normas_pdf` ou de outro caminho local configurado;
- identificação provável da norma pelo nome e pelas primeiras páginas;
- extração e busca de texto com referência ao arquivo e à página física do PDF;
- diagnóstico de PDFs digitalizados que precisam de OCR;
- hash SHA-256, metadados, possíveis duplicidades e links para fontes oficiais;
- visualizador interno e guia para edição, emendas, escopo e rastreabilidade.
- inclusão direta de uma referência do catálogo na matriz normativa do projeto ativo.

## Guia geral

A página **Guia geral** reúne:

- orientação pelo tipo de dado disponível;
- coleta de cargas, geometrias e propriedades de material;
- unidades, sinais e glossário;
- passo a passo de todos os módulos e ferramentas;
- um exemplo preenchido e interpretação para cada parte;
- exemplos individuais dos cinco módulos de estruturas de aço;
- a tabela de comandos de vigas e eixos, com os apoios da Tabela 12.1 e a
  leitura de cada diagrama.
- uso completo dos projetos permanentes, da validação e dos relatórios modulares.

## Qualidade

- suíte de testes com pytest, conferida contra soluções fechadas clássicas
  em vez de valores colhidos do próprio programa;
- `ruff` no projeto inteiro e `mypy` no núcleo de cálculo, com adoção
  gradual: só entram na verificação de tipos os módulos que já passam
  limpos, para o resultado poder bloquear o CI e continuar significando
  alguma coisa;
- GitHub Actions roda lint, tipos e testes a cada push e pull request.

```bash
pip install -r requirements-dev.txt
ruff check .
mypy
pytest -q
```

## Estrutura

```text
mecanica_toolkit/
├── app.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .github/workflows/
├── .streamlit/config.toml
├── assets/
├── app_pages/
│   ├── inicio.py
│   ├── painel_industrial.py
│   ├── gestao_projetos.py
│   ├── central_validacao.py
│   ├── central_relatorios.py
│   ├── assistente_projeto.py
│   ├── conversor_unidades.py
│   ├── analise_estatica.py
│   ├── analise_fadiga.py
│   ├── vigas_eixos.py
│   ├── assistente_cargas.py
│   ├── circulo_mohr.py
│   ├── projeto_parafusos.py
│   ├── estruturas_aco.py
│   ├── catalogo_materiais.py
│   ├── catalogo_perfis.py
│   ├── normas_tecnicas.py
│   └── guia_geral.py
├── core/
│   ├── technical_modules.py
│   ├── beam_analysis.py
│   ├── beam_script.py
│   ├── section_stress.py
│   ├── section_catalog.py
│   ├── material_catalog.py
│   ├── technical_records.py
│   ├── load_cases.py
│   ├── report_plugins.py
│   ├── validation_plugins.py
│   ├── project_assistant.py
│   ├── project_store.py
│   ├── project_validation.py
│   ├── project_workflow.py
│   ├── project_checklist.py
│   ├── checklist_templates.py
│   ├── project_records.py
│   ├── project_diff.py
│   ├── project_portfolio.py
│   ├── project_report.py
│   ├── unit_converter.py
│   ├── standards_library.py
│   └── ...
├── components/
├── data/
│   ├── modelos_checklist.json
│   ├── normas_catalogo.json
│   ├── materiais_ref_anglo.json
│   ├── materiais_ref_gerdau.json
│   ├── perfis_ref_gerdau.json
│   └── (o banco de projetos fica fora do repositório — ver "Onde ficam os dados")
├── docs/
├── normas_pdf/
└── tests/
```

A interface fica separada do núcleo de cálculo para permitir testes e evolução
independente. A rastreabilidade das equações está na pasta `docs/`.

Cálculos usados por mais de um módulo ficam em um único lugar: as tensões
combinadas em um ponto de seção, por exemplo, vivem em `core/section_stress.py`
e são consumidas tanto pelo assistente de cargas quanto pela análise de vigas —
as duas páginas não podem divergir na mesma seção.

Os módulos técnicos possuem um contrato central com identidade, versão, página,
esquema de registro e pontos de extensão. Novos registros recebem hash SHA-256
do conteúdo técnico. Relatórios e validações aceitam provedores independentes,
reduzindo a necessidade de alterar os orquestradores centrais ao criar um módulo.

## Validade e segurança

Os modelos possuem hipóteses e faixas de validade. Os materiais cadastrados são
referências típicas. Antes de usar resultados em projeto real, valide
propriedades, carregamentos, combinações, concentrações de tensão, ambiente,
processo de fabricação, norma aplicável e certificado do material.