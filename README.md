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
  exportação da carteira em CSV.

### Projetos permanentes

- persistência local em `data/projetos_industriais.sqlite3`;
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

- perfis de resumo executivo, memorial industrial completo e dossiê de validação;
- seleção independente das seções e dos registros técnicos anexados;
- controle de código, revisão, situação, elaboração, verificação e aprovação;
- Word editável e PDF estável gerados a partir do mesmo modelo de dados;
- provedores de seção independentes, permitindo que novos módulos acrescentem capítulos sem acoplamento ao renderizador;
- resumo básico no início, seguido de base, escopo, normas, memória técnica, validação e checklist;
- a base de projeto traz os critérios técnicos estruturados e a lista de documentos de entrada;
- registros superados ficam fora da seleção padrão; cada emissão entra num histórico
  próprio (documento, revisão, perfil, snapshot) e na linha do tempo do projeto;
- quadros de integração, aprovações e apêndice consolidado de entradas e resultados.

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
- memorial consolidado em Word editável, com resumo executivo básico, critérios de projeto, memória completa, pendências, checklist, revisão, aprovações e integração de outras partes;
- exportação complementar em PDF para impressão.
- registro padronizado da avaliação no projeto industrial ativo.

### Vigas e eixos

- barra reta com apoios de rolete, pino, engaste, engaste deslizante e trava axial;
- rótulas internas (vigas Gerber) e vãos contínuos isostáticos ou hiperestáticos;
- cargas pontuais, distribuídas uniformes e trapezoidais, momentos concentrados,
  carga axial, carga axial distribuída, torques e peso próprio;
- diagramas de esforço normal, cortante, momento fletor, linha elástica (flecha),
  rotação, torque e ângulo de torção;
- tensões combinadas: N/A ± M·c/I, V·Q/(I·t), T/Wt, von Mises e Tresca avaliados
  na fibra superior, na fibra inferior e na linha neutra;
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
  com aviso quando a compressão se aproxima da instabilidade;
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
- registro técnico versionado e capítulo automático no memorial unificado.

### Círculo de Mohr e transformação de tensões

- estados 2D e 3D, tensões e direções principais;
- transformação para planos inclinados e tração em plano arbitrário;
- cisalhamento máximo, von Mises, Tresca e Rankine;
- três círculos de Mohr, invariantes e tabelas de transformação.
- registro 2D ou 3D no projeto permanente.

### Projeto de juntas parafusadas

- roscas métricas de M3 a M36 e classes 4.6 a 12.9;
- pré-carga, dispersão e torque de aperto;
- distribuição de P, V, M e T em grupo circular;
- prova, escoamento, ruptura, separação e deslizamento;
- esmagamento, rasgamento da chapa e fadiga axial opcional.

### Estruturas de aço

- catálogo geométrico de perfis e propriedades de seção;
- barras à tração, compressão, flexão, cisalhamento e interação N–M;
- flecha de vigas e combinações editáveis ELU/ELS;
- ligações parafusadas, chapa, cisalhamento de bloco e soldas;
- análise matricial linear de treliças e pórticos 2D.
- registro das combinações, verificações de barras e análises 2D no projeto ativo.

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
│   ├── project_records.py
│   ├── project_diff.py
│   ├── project_portfolio.py
│   ├── project_report.py
│   ├── unit_converter.py
│   ├── standards_library.py
│   └── ...
├── components/
├── data/
│   ├── normas_catalogo.json
│   ├── materiais_ref_anglo.json
│   ├── materiais_ref_gerdau.json
│   ├── perfis_ref_gerdau.json
│   └── projetos_industriais.sqlite3  # criado automaticamente
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