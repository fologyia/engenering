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

### Projetos permanentes

- persistência local em `data/projetos_industriais.sqlite3`;
- identificação, cliente, unidade, área, TAG, processo e responsabilidades;
- base de projeto com documentos, carregamentos, condições, critérios e limitações;
- casos de carga vetoriais, combinações com fatores explícitos e envelopes governantes;
- escopo físico para equipamentos, linhas, estruturas, sistemas e pontos críticos;
- matriz normativa com edição, aplicação, fonte e conferência no original;
- registros técnicos padronizados com entradas, resultados, premissas, alertas e conclusão;
- checklist com responsável, prazo, estado, evidência e criticidade;
- marcos de revisão restauráveis, duplicação, arquivamento e exportação/importação JSON;
- integração com o Assistente de projeto e com os módulos técnicos.

### Central de validação

- consolida bloqueios, pendências, atenções e informações do projeto inteiro;
- verifica identificação, responsabilidades, base de projeto, escopo físico e materiais;
- aponta referências sem edição ou ainda não conferidas no documento-fonte;
- detecta registros incompletos e critérios numéricos conhecidos, como utilização acima de 1;
- permite transformar um achado em item rastreável do checklist;
- calcula um índice de completude documental, explicitamente separado de conformidade ou aprovação.

### Central de relatórios

- perfis de resumo executivo, memorial industrial completo e dossiê de validação;
- seleção independente das seções e dos registros técnicos anexados;
- controle de código, revisão, situação, elaboração, verificação e aprovação;
- Word editável e PDF estável gerados a partir do mesmo modelo de dados;
- provedores de seção independentes, permitindo que novos módulos acrescentem capítulos sem acoplamento ao renderizador;
- resumo básico no início, seguido de base, escopo, normas, memória técnica, validação e checklist;
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
- exemplos individuais dos cinco módulos de estruturas de aço.
- uso completo dos projetos permanentes, da validação e dos relatórios modulares.

## Estrutura

```text
mecanica_toolkit/
├── app.py
├── requirements.txt
├── .streamlit/config.toml
├── assets/
├── app_pages/
│   ├── inicio.py
│   ├── gestao_projetos.py
│   ├── central_validacao.py
│   ├── central_relatorios.py
│   ├── assistente_projeto.py
│   ├── conversor_unidades.py
│   ├── analise_estatica.py
│   ├── analise_fadiga.py
│   ├── assistente_cargas.py
│   ├── circulo_mohr.py
│   ├── projeto_parafusos.py
│   ├── estruturas_aco.py
│   ├── normas_tecnicas.py
│   └── guia_geral.py
├── core/
│   ├── technical_modules.py
│   ├── technical_records.py
│   ├── load_cases.py
│   ├── report_plugins.py
│   ├── validation_plugins.py
│   ├── project_assistant.py
│   ├── project_store.py
│   ├── project_validation.py
│   ├── project_report.py
│   ├── unit_converter.py
│   ├── standards_library.py
│   └── ...
├── components/
├── data/
│   ├── normas_catalogo.json
│   └── projetos_industriais.sqlite3  # criado automaticamente
├── docs/
├── normas_pdf/
└── tests/
```

A interface fica separada do núcleo de cálculo para permitir testes e evolução
independente. A rastreabilidade das equações está na pasta `docs/`.

Os módulos técnicos possuem um contrato central com identidade, versão, página,
esquema de registro e pontos de extensão. Novos registros recebem hash SHA-256
do conteúdo técnico. Relatórios e validações aceitam provedores independentes,
reduzindo a necessidade de alterar os orquestradores centrais ao criar um módulo.

## Validade e segurança

Os modelos possuem hipóteses e faixas de validade. Os materiais cadastrados são
referências típicas. Antes de usar resultados em projeto real, valide
propriedades, carregamentos, combinações, concentrações de tensão, ambiente,
processo de fabricação, norma aplicável e certificado do material.
#   e n g e n e r i n g  
 