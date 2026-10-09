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

### Versão web (Streamlit Cloud)

O disco do Streamlit Community Cloud é **temporário**: é apagado a cada reinício do aplicativo
(atualização do código, inatividade, manutenção), e os projetos salvos nele somem junto. Por isso a
versão web avisa "dados temporários" na barra lateral, oferece **Baixar meus projetos** em toda
página e, se você configurar um repositório **privado** do GitHub como espelho, copia cada
gravação para lá e traz tudo de volta quando o aplicativo sobe:

```toml
# Streamlit Cloud → Settings → Secrets
MECANICA_TOOLKIT_GITHUB_REPO = "seu-usuario/mecanica-toolkit-dados"
MECANICA_TOOLKIT_GITHUB_TOKEN = "github_pat_..."
```

Para **fechar o acesso**, defina também `MECANICA_TOOLKIT_SENHA` nos segredos: o aplicativo passa a
pedir a senha antes de mostrar qualquer projeto (`core/acesso.py`).

Passo a passo, variáveis, limites e cuidados (o aplicativo é público por padrão) em
[`docs/armazenamento_na_nuvem.md`](docs/armazenamento_na_nuvem.md). Sem essas variáveis nada sai do
computador.

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
- **o que passou e o que não passou**: nas análises com tabela de verificações
  (flambagem de colunas e ligações parafusadas) o capítulo abre com o resultado
  (ATENDE, NÃO ATENDE ou ATENÇÃO, com a contagem e o que governa), traz os dados de
  entrada principais, o método e as premissas, lista **o que passou** — cada
  verificação com solicitante, resistente, aproveitamento, cálculo e referência — e
  **termina sempre com o que não passou**, o que pede atenção e o que o módulo manda
  conferir antes de emitir (ou com a declaração de que nada reprovou). O que não é
  critério (N_e, χ, λ…) vai numa tabela de valores de apoio;
- **várias análises no mesmo projeto**: cada análise é um capítulo, agrupado pela
  peça; o quadro-resumo conta o que passou e o que não passou em cada uma, a conclusão
  lista o que não passou em todo o projeto, análises de mesmo título ganham
  "(cálculo i de n)" e método, premissas e critérios iguais aparecem uma vez só
  (as seguintes citam o item da primeira);
- **para incluir em outro documento**: o perfil "Para incluir em outro documento" gera
  só os capítulos numerados — sem capa, resumo executivo, controle de revisões nem
  aprovações —, em títulos e tabelas padrão do Word, que assumem o estilo do
  documento que os receber;
- registros de Círculo de Mohr e de casos de carga não entram no memorial;
  registros superados ficam fora da seleção padrão;
- listas de resultados (reações de apoio, envoltória, esbeltez de paredes,
  ranking de sensibilidade) viram tabelas próprias;
- perfis de memorial completo, memorial de cálculos, resumo executivo e capítulos para incluir
  em outro documento, com seleção independente das seções e dos registros anexados;
- controle de código, revisão, situação, elaboração, verificação e aprovação;
- Word editável e PDF gerados a partir do mesmo modelo de dados; o PDF usa uma
  fonte TrueType do sistema (Segoe UI, Arial, Calibri ou DejaVu), então σ, τ,
  √ e ≥ saem como o módulo os escreveu;
- provedores de seção independentes, permitindo que novos módulos acrescentem capítulos sem acoplamento ao renderizador;
- cada emissão entra num histórico próprio (documento, revisão, perfil,
  snapshot) e na linha do tempo do projeto.

## Recursos

### Caminho do projeto (estrutura metálica)

O programa ajuda a **conseguir as informações, registrar e anotar tudo e fazer as verificações**, junto
com o modelo (SolidWorks hoje; Robot Structural quando houver). O projeto segue cinco etapas, mostradas
na página inicial e nas páginas de cada etapa com o que o projeto ativo já tem
(`docs/fluxo_do_projeto.md`):

1. **Base técnica do projeto** — uma vez por projeto: critério do cliente (somente as normas ou o
   critério Anglo American AA-BR-DPST-DR-0001), V₀, S₁, terreno, S₃, tipo de estrutura (limite do
   deslocamento), sobrecarga, agressividade e vida útil. As páginas de vento, contraventamento,
   ligação e estruturas de aço começam com esses valores e mostram de onde vieram; a consulta do
   critério Anglo (sobrecargas, deslocamentos, mínimos, chumbadores, ligações, combinações, vibração,
   escadas, materiais e conflitos) fica na mesma página (`docs/criterio_anglo.md`).
2. **Ações** — cada página gera as suas; o vento de estruturas abertas sai por nível, por pórtico e
   em cada nó, com desenho e CSV.
3. **Plano de cargas** — as ações com código padrão (PP, PE, EQ, EO, SC, W0…W270, T±, PRV, HT, HL, MO,
   IM, EX), de onde vieram, as cargas para lançar no modelo e as combinações ELU e ELS numeradas, com
   CSV e a cobertura das combinações mínimas do critério Anglo (5.9).
4. **Verificações** — contraventamento, ligação, barras, parafusos, degraus; cada cálculo registrado.
5. **Memorial** — Word e PDF com os cálculos registrados.

### Visão geral

- recomenda o módulo a partir dos dados disponíveis;
- dá acesso direto ao projeto guiado e ao conversor;
- resume entradas e saídas de cada área;
- explica o fluxo de cálculo e a leitura dos diagnósticos.

### Assistente de projeto

- organiza o problema em quatro etapas: definição, objetivo, dados e plano, com rotas para os
  módulos de cálculo, entre eles Vento nas estruturas, Degrau de escada em grade e Ligação de
  contraventamento (esses três só abrem o módulo: os dados se preenchem na página);
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

### Vento nas estruturas

Calcula a ação do vento numa edificação de planta retangular pela **ABNT NBR 6123:2023**
(`core/vento_*.py`; detalhes em `docs/vento_nbr6123.md`):

- **velocidade e pressão dinâmica**: `V_k = V₀·S₁·S₂·S₃` e `q = 0,613·V_k²`, com `S₁` por relevo,
  `S₂` das Tabelas 1 a 3 (classe pela superfície frontal de cada direção; Anexo A acima de 80 m) e
  `S₃` da Tabela 4 ou do Anexo B (nunca abaixo do mínimo do grupo);
- **`C_e` de cada zona** das paredes (Tabela 6) e do telhado plano, de duas águas (Tabela 7) e de uma
  água (Tabela 8), com `c_pe` médio nas zonas de altas sucções, nas duas direções do vento;
- **pressão interna** `c_pi` pelo item 6.3.2 (quatro faces, duas faces opostas, estanque, abertura
  dominante), com um caso de carga por valor;
- **vedações e fixações** (telhas, painéis, terças): pressão de projeto da classe A em cada zona;
- **forças globais**: soma das zonas, arrasto `F_a = q·C_a·A_e·f_v` (Figuras 4 e 5, lidas do gráfico),
  torção pela excentricidade, atrito, fator de vizinhança e vento de alta turbulência;
- **pórtico transversal**: carga por metro (normal ao elemento) de cada pilar e água, por direção do
  vento e faixa de posição, com a solução pelo solver 2D (reações, esforços e deslocamento);
- verificações de aplicabilidade (a/b, h/b, inclinação, T₁ ≤ 1 s, esbeltez), desenho da planta com as
  zonas, CSV das tabelas e **registro no projeto** — o memorial traz o resultado, o que passou, as
  tabelas e o que não passou;
- V₀, relevo, terreno, grupo e o S₃ do cliente começam com os valores da **base técnica** do projeto.

### Esforços do modelo

Importa os resultados do **SolidWorks Simulation** (`core/esforcos_modelo.py`; detalhes em
`docs/esforcos_do_modelo.md`): "Listar forças da viga" e "Listar forças resultantes" de cada estudo
(um por caso de carga, com o código no nome). O programa lê o formato em português (cp1252, ponto de
milhar), converte para esforço interno com tração positiva, **confere as reações** contra o Plano de
cargas (caso vertical sem reação horizontal, forças concentradas equilibradas, área carregada) e
combina os casos **ponto a ponto** para achar o pior de cada barra (compressão, tração, momento
forte com o N junto, momento fraco, cortante, torque). Perfil lido do nome da viga quando o
SolidWorks diz qual é; tabela das barras com perfil, tipo e eixo forte gravada no projeto.
**Verificação de todas as barras** (`core/verificacao_barras.py`) pela NBR 8800 com os esforços de
todas as combinações ELU em todos os pontos, multiplicados pelo B₂ do tipo: varredura rápida da
interação e verificação completa dos pontos críticos pelo motor da Flambagem de colunas (todos os
modos, FLT/FLM/FLA, B₁, N + Mx + My, esbeltez), cantoneiras pela 5.3.5.4, cortante; registro com o
capítulo de cada barra no memorial. **Quadro de cargas para as fundações** (`core/quadro_fundacoes.py`):
os esforços na base de cada pilar, caso a caso, sem combinar nem majorar (critério Anglo 5.9), com a
base achada pela ponta mais comprimida, conferência da soma contra a reação total, Excel, CSV e
registro no memorial. **Placas de base dos pilares** (`core/placa_base_pilares.py`): uma placa padrão
verificada em cada pilar pelo AISC Design Guide 1 com os esforços da base combinados (ELU) — contato,
espessura da placa, tração e cisalhamento nos chumbadores — e, com o critério Anglo, placa ≥ 16 mm,
chumbador ≥ 5/8" e o furo, a arruela e o graute do item 8.7; desenho da placa em planta, CSV e registro.

### Lista de material

Perfis, chapas, grades e outros itens com a **massa**, o **peso**, a **área de pintura** e as **barras
comerciais** de cada perfil, para o orçamento (`core/lista_de_material.py`; detalhes em
`docs/lista_de_material.md`). Importa a **lista de corte do SolidWorks** (CSV ou Excel, colunas achadas
pelo nome, perfis reconhecidos pela descrição ou pelas medidas) — com a **macro**
`macros_solidworks/exportar_lista_de_corte.bas`, que exporta a lista direto da árvore da peça, sem
desenho —, traz as placas de base dos pilares e
**confere o peso com a reação do caso PP** do modelo. Excel (resumo, itens, por perfil, chapas) e CSV.
Não vai para o memorial.

### Vigas de piso

A viga biapoiada que apoia a grade da plataforma (`core/viga_de_piso.py`; detalhes em
`docs/vigas_de_piso.md`): combinações da NBR 8800 com o peso próprio, flexão com FLT (C_b do diagrama
ou mesa travada pela grade), FLM e FLA, cortante, flecha (L/350 da NBR; L/350 ou L/300 do critério
Anglo), espessura mínima Anglo, reação para a ligação com o mínimo de 75 % do item 9.1, frequência
natural, o **perfil mais leve** da família com o botão para adotá-lo, desenho da viga e registro no
memorial.

### Vento em estruturas abertas

Só o vento de **plataformas, mezaninos e pipe racks sem fechamento**, para anotar no relatório e lançar
no modelo (`core/vento_estrutura_aberta.py`, `core/vento_aberto_registro.py`): pórticos como
reticulados (NBR 6123:2023, capítulo 8), guarda-corpos e equipamentos; **forças por nível**, **por
pórtico**, **em cada nó** pilar–viga e **carga por metro** em pilares, vigas e guarda-corpos; desenho
dos pórticos com as forças; CSV (ponto e vírgula, vírgula decimal); envio de W0, W90, W180 e W270 ao
**plano de cargas**; registro com capítulo próprio no memorial (resultado, entradas, método e as
tabelas). Usa os mesmos campos do Contraventamento de estruturas abertas.

### Base técnica do projeto e Plano de cargas

`core/base_tecnica.py` e `core/plano_de_cargas.py` (ver o caminho do projeto acima e
`docs/fluxo_do_projeto.md`). O plano guarda uma ação por código; enviar o vento de novo substitui as
quatro direções. A **conferência do plano** aponta o que falta ou não fecha antes de exportar, cada
ação pode ser editada e a matriz de fatores das combinações sai colorida (majorada × acompanhante).
**Exportar para o modelo** (`core/exportacao_cargas.py`): escolha as unidades (N e mm, N e m, kN e m)
e o eixo vertical (Y no SolidWorks, Z no Robot) e baixe a planilha Excel (Leia-me, Ações, Cargas com
F_x, F_y e F_z já com sinal e o comando equivalente em cada programa, Combinações em matriz e em
lista) ou os CSV; o PP vira a gravidade do modelo. Na página **Estruturas de aço → Combinações**, o
botão **Trazer as ações do plano de cargas** monta a tabela com as ações do plano para receber os
esforços da barra tirados do modelo.

### Degrau de escada em grade

Dimensiona o degrau de uma escada industrial em **grade de piso eletrofundida** e escolhe o modelo do
catálogo **Selmec "Degraus" (DS)**, verificando a NR-12 (Anexo III), a NR-22, o Critério Anglo
AA-BR-DPST-DR-0001, a NBR 8800:2008, a NBR 6120 e a ISO 14122-3 (`core/degrau_escada.py`; detalhes em
`docs/degrau_escada.md`):

- **geometria**: nº de espelhos, espelho `h` e piso `b` pelo requisito legal, pelo critério Anglo e pelo
  limite do catálogo (nessa ordem de prioridade), profundidade `C`, furação `F`, sobreposição `r`,
  lances, degraus em grade, projeção horizontal e larguras mínimas;
- **64 modelos do catálogo** avaliados, com o mais leve que atende ao cálculo e à largura recomendada
  (ou a escolha manual) e a tabela que explica por que um modelo entrou e os outros não;
- **dimensionamento do degrau**: flexão com flambagem lateral por torção (NBR 8800 Tabela G.1),
  cisalhamento, flechas (Anglo L/300 e ISO 14122-3), reação na longarina e parafusos A307;
- **38 verificações** com a norma e o item em cada uma, contagem `OK · NÃO OK · ALERTA · N/A`, bloco
  fixo de **conflitos entre normas** e texto pronto para a requisição de compra;
- CSV das verificações e dos 64 modelos, relatório em PDF e **registro no projeto** (o memorial traz o
  resultado, o que passou, as tabelas e o que não passou).

Entrada impossível (desnível ou comprimento nulo, altura por lance menor que um espelho, `C ≤ b`…) vira
erro claro: nada é corrigido em silêncio. Não dimensiona longarina, patamar nem guarda-corpo.

### Contraventamento de estruturas abertas

Contraventamento vertical de **plataformas, mezaninos e pipe racks sem fechamento**, da planta à
diagonal verificada (`core/contraventamento_plataforma.py`; detalhes em
`docs/contraventamento_estrutura.md`):

- **vento por reticulados** pela NBR 6123:2023, capítulo 8 — C_a da Figura 12 por φ, proteção η da
  Figura 14 entre pórticos, guarda-corpos e equipamentos (cilindros pelas Tabelas 27 e 28), levados
  aos pisos (`core/vento_estrutura_aberta.py`);
- **ações e combinações** da NBR 8800 com forças nocionais de 0,3 % em todas as combinações
  últimas, vento nas quatro direções num grupo exclusivo e cortante de cada andar pela envoltória
  rigorosa, com a combinação governante escrita por extenso;
- **B₂** de cada andar (Anexo C) e classificação da deslocabilidade, com amplificação na média;
- **diagonais** em X (só tração ou tração e compressão), diagonal simples ou V invertido, em
  cantoneira (5.3.5.4), tubo ou tirante, com parafusos, rasgamento e solda; **deslocamentos** do
  Anexo B ou da Tabela 4 do critério Anglo (pelo tipo de estrutura); botão que leva as forças para a
  Ligação de contraventamento;
- **desenhos** (planta, elevação de cada linha com as forças, vento nos pórticos, cortante por andar),
  forças nos nós e envio do vento ao plano de cargas; com o **critério Anglo**, as exigências de
  espessura, diâmetros, parafusos e capacidade mínima da ligação.

### Ligação de contraventamento

Dimensiona a **chapa de nó** de um contraventamento vertical que chega ao canto viga–coluna pelo
**Método das Forças Uniformes** do AISC Design Guide 29 (caso geral e casos especiais 1, 2 e 3) e
verifica pelo AISC 360-16, em LRFD ou ASD: parafusos da barra, seção de Whitmore, bloco de
cisalhamento, flambagem da chapa, interfaces, soldas e alma/mesa da viga e da coluna (cerca de 24
linhas com o item da norma em cada uma). No **modo simplificado** o programa dimensiona a chapa
sozinho (parafusos, espessura, comprimentos sem momento nas interfaces e soldas) a partir da força,
do ângulo, dos perfis do catálogo (com o `k` tabelado) e do parafuso. Reproduz os Exemplos 5.1 a 5.4 do guia
(`core/contraventamento_*.py`; detalhes em `docs/ligacao_contraventamento.md`). A aba **Desenho**
mostra a chapa de nó em escala com a seção de Whitmore e as forças em cada interface; com o **critério
Anglo**, a tabela ganha chapa ≥ 8 mm, parafusos A325 de 5/8" a 1", ao menos 2 parafusos e o filete
mínimo da Tabela 6. O registro leva as forças nas interfaces e a geometria para o memorial. Não
verifica a barra nem a chapa de topo parafusada.

### Flambagem de colunas

Verifica a **barra inteira numa só rodada** (`core/column_buckling.py`, com as fórmulas em
`core/column_design.py`, validado contra o AISC Design Guide 29 e contra o módulo de barras de
Estruturas de aço em todo o catálogo de perfis):

- os **dois eixos** e **todos os modos de flambagem elástica** — flexão em x, flexão em y, torção,
  flexo-torção das seções monossimétricas e a raiz da cúbica nas assimétricas; adota-se o menor
  `N_e` (NBR 5.3.5; AISC E3/E4);
- **três normas**, escolhidas na página: **NBR 8800:2008** (`N_c,Rd = χ·Q·A_g·f_y/γ_a1`, fator `Q`
  do Anexo F), **Projeto NBR 8800:2024** e **AISC 360-16** (área efetiva `A_ef` com `c₁` e `c₂` das
  Tabelas 4 e 5; `φ = 0,90` no AISC). *Comparar normas* mostra a mesma coluna nas três, e uma norma
  que bloqueia o cálculo aparece com o motivo;
- seções: perfil do catálogo (com as propriedades da tabela), barra circular ou retangular maciça,
  tubo circular ou retangular, I e U por dimensões, área e raio de giração, ou seção genérica com as
  paredes (b/t) informadas;
- **flexão em x e em y** (FLT, FLM e FLA, com o limite `1,5·W·f_y`) e momentos amplificados por
  `B₁` com o **comprimento real** da barra (K = 1); `C_m` pela razão `M₁/M₂` ou por força transversal
  (sem a razão, `C_m = 1,0`); `C_b` informado ou pelo diagrama de quatro pontos;
- **interação N + M_x + M_y numa só equação** (5.5.1.2; AISC H1-1) — verificar cada eixo separado
  aprovaria colunas que a norma reprova;
- **critério Anglo** AA-BR-DPST-DR-0001, como linhas da tabela: esbeltez `KL/r ≤ 200` (8.3) e
  espessuras mínimas (8.8);
- **o que a norma não cobre vira linha NÃO OK**, sem correção silenciosa: tubo circular com
  `D/t > 0,45·E/f_y`, alma esbelta ou tubo não compacto na flexão, `N_Sd ≥ N_e` no `B₁` e seção sem
  `Z`. Seção genérica sem as paredes ou sem a confirmação “compacta e torção não governa” fica em
  **ALERTA**, nunca em OK; perfil formado a frio também (NBR 14762);
- **mão-francesa**: a força inclinada é decomposta em `H = F·sen θ` e `V = F·cos θ`; o momento
  (`H·a` no engaste, `H·a·(L−a)/L` na biapoiada ou o do engaste com topo apoiado, mais `V·e`) é
  somado ao do eixo que ela flete e a força horizontal conta como transversal no `C_m`. O
  cisalhamento (5.4.3) não é verificado, mas o programa avisa;
- **tabela de verificações** de oito colunas (Verificação · Solicitante · Resistente · Unidade ·
  Aproveitamento · Status · Fórmula · Referência), em CSV, no registro do projeto e no memorial
  (Word e PDF), com a curva de flambagem da norma escolhida;
- K teórico ou **recomendado para projeto** (Tabela E.1) por eixo, ou informado; `K_z` e `L_z` da
  torção; ações majoradas na própria página (`N_Sd = γ_g·N_g + γ_q·N_q`, Tabela 1) ou `N_Sd` já de
  cálculo;
- cada campo tem um “?” em linguagem simples, com as simplificações adotadas.

Valores da NBR 8800:2008 marcados “CONFERIR” no código (`Q_s` e `Q_a` do Anexo F, Tabela E.1 de K,
`λ_p` dos tubos na flexão e a forma da FLT de 2008) vieram de memória do módulo de referência e
precisam ser confirmados na norma antes de emitir documentos.

### Projeto de juntas parafusadas

A página tem dois modos, escolhidos no topo:

**Junta mecânica (NASA/ISO)** — pré-dimensionamento, que não substitui a norma estrutural:

- roscas métricas de M3 a M36 e classes 4.6 a 12.9;
- pré-carga, dispersão e torque de aperto;
- distribuição de P, V, M e T em círculo, **grade retangular** ou coordenadas livres
  (o 2 × 2 de 70 × 70 mm fica num círculo de diâmetro √(s² + g²), não de 70 mm);
- cargas em serviço com fator mínimo n; valores já majorados são divididos por γ_f;
  torque por excentricidade da cortante (T = V·a);
- esmagamento e rasgamento com t da parte ligada mais fina (a pega vai em campo
  separado), prova, escoamento, ruptura, separação, deslizamento e fadiga axial opcional;
- diagnóstico de cada modo de falha com solicitante, resistente, aproveitamento, status,
  fórmula e fonte, igual no CSV e no memorial.

**Ligação estrutural de aço** — verificação pela norma (`core/bolted_connection.py`,
conferido contra os exemplos do AISC Design Guide 29 e um caso real de planilha):

- NBR 8800:2008, Projeto NBR 8800:2024, AISC 360 LRFD e
  RCSC 2004, com **Comparar normas** lado a lado;
- parafusos ASTM A325, A490 e A307 (rosca no plano ou fora, n planos de corte), com
  **Testar todos** para achar o menor que atende;
- esforços característicos × de cálculo (γ_f), grupo excêntrico elástico (emenda por
  sobreposição a = e + (n_col − 1)·s/2), grade ou coordenadas livres;
- corte, contato e rasgamento por furo (ℓ_f medido a partir do furo), soma por furo no grupo,
  deslizamento em serviço (F_Tb das tabelas da NBR/RCSC), tração da peça com C_t e colapso
  por rasgamento;
- disposições construtivas (bordas, espaçamentos, pega longa) e critério Anglo
  AA-BR-DPST-DR-0001, item 9.1 (inclui a regra dos 75%);
- tabela Verificação · Solicitante · Resistente · Unidade · Aproveitamento · Status ·
  Fórmula · Referência, em CSV e no memorial; entradas inválidas (ℓ_f ≤ 0, C_t
  indefinido, A307 por atrito, superfície sem μ) aparecem na tabela, não são corrigidas
  em silêncio;
- fora do escopo desta etapa: tração com alavanca e interação tração + corte, furos
  alargados ou alongados, fadiga e perfis formados a frio.

Valores da NBR 8800:2008 marcados “CONFERIR” no código (μ = 0,35 nas classes A e C, f_ub do
A325 e C_t ≤ 0,90) precisam ser confirmados na norma antes de emitir documentos.

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
  favoráveis, especiais ou de construção e excepcionais, ELS rara (ψ₁ nas
  acompanhantes), frequente e quase permanente, grupos de ações exclusivas
  (W+ e W− nunca juntos) e envoltória rigorosa por esforço;
- ações de plataforma: vento pela **NBR 6123:2023** (S₁ por relevo, S₂ por
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
- o caminho do projeto em cinco etapas (base técnica, ações, plano de cargas, verificações e
  memorial), com capítulos para a base técnica, o plano de cargas e o vento em estruturas abertas.

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
│   ├── base_tecnica.py
│   ├── plano_cargas.py
│   ├── esforcos_modelo.py
│   ├── lista_de_material.py
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
│   ├── degrau_escada.py
│   ├── vento_nbr6123.py
│   ├── vento_estrutura_aberta.py
│   ├── contraventamento_estrutura.py
│   ├── ligacao_contraventamento.py
│   ├── viga_de_piso.py
│   ├── estruturas_aco.py
│   ├── catalogo_materiais.py
│   ├── catalogo_perfis.py
│   ├── normas_tecnicas.py
│   └── guia_geral.py
├── core/
│   ├── technical_modules.py
│   ├── base_tecnica.py
│   ├── criterio_anglo.py
│   ├── plano_de_cargas.py
│   ├── exportacao_cargas.py
│   ├── esforcos_modelo.py
│   ├── verificacao_barras.py
│   ├── quadro_fundacoes.py
│   ├── placa_base_pilares.py
│   ├── lista_de_material.py
│   ├── viga_de_piso.py
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