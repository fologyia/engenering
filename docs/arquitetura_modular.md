# Arquitetura modular do Mecânica Toolkit

## Objetivo

O núcleo separa cálculo, interface, persistência, validação e documento. Um novo
módulo técnico não deve depender do Streamlit para calcular nem alterar os
renderizadores Word/PDF para acrescentar dados padronizados.

## Contrato do módulo

Cada capacidade é declarada em `core/technical_modules.py` por meio de
`ModuloTecnico`. O contrato contém:

- ID estável;
- título apresentado ao usuário;
- versão do módulo;
- página Streamlit;
- grupo e ordem de navegação;
- ícone e descrição;
- esquema do registro técnico;
- provedor de relatório e regras de validação aplicáveis.

O `app.py` monta as áreas técnicas a partir desse catálogo. A identidade também
é usada por registros, relatórios e validações.

## Registro técnico v2

Use `core.technical_records.criar_registro_tecnico` diretamente no núcleo ou o
adaptador `components.project_tools.construir_registro_tecnico` nas páginas.
Além do conteúdo técnico, o registro recebe:

- `schema_registro`;
- `modulo_id` e `modulo_versao`;
- `metodo_versao`;
- vínculos com casos de carga, componentes e materiais;
- `hash_calculo`, calculado sobre entradas, resultados, método e critérios.

Se o conteúdo técnico for alterado depois da assinatura, a Central de Validação
gera um bloqueio. A correção esperada é registrar novamente o cálculo ou criar
uma nova revisão controlada.

## Provedores de relatório

`core/report_plugins.py` mantém provedores de seções neutras. Um provedor
declara ID, título, posição e uma função que devolve parágrafos, tabelas,
fórmulas, bullets ou nota. O modelo unificado numera a seção e os renderizadores
Word/PDF a apresentam sem conhecer o módulo de origem.

O provedor `carregamentos` é a implementação de referência: ele acrescenta
casos, combinações e envelope ao memorial.

## Regras de validação

`core/validation_plugins.py` registra regras independentes. Além das regras
de contrato, cargas, dependências, margens e deslocamentos, há três regras
de gestão: `prazos-checklist` (vencido, a vencer, prazo ilegível),
`criterios-projeto` (critérios ausentes ou incompletos) e
`documentos-entrada` (revisão ausente, aguardando recebimento, superado
ainda citado no escopo). Cada regra devolve:

- achados com severidade, categoria, detalhe, recomendação e evidência;
- pontos documentais preenchidos e totais, quando aplicável;
- ID e versão da própria regra.

A Central de Validação agrega esses resultados às regras gerais. O índice
continua sendo documental; não representa conformidade ou aprovação.

## Gestão do projeto: fluxo, eventos, registros e comparação

A camada de gestão fica em módulos puros, sem Streamlit, para a página do
projeto, o painel de carteira e a validação lerem a mesma coisa:

- `core/project_workflow.py` — situações, transições permitidas e portões.
  `avaliar_transicao` devolve impedimentos (travam), avisos (não travam) e
  se a passagem cria revisão controlada. A interface nunca altera `status`
  sem passar por aqui.
- `core/project_checklist.py` — leitura do prazo (ISO e formatos
  brasileiros), classificação de cada item em relação a hoje e resumo de
  vencidos, a vencer e ilegíveis.
- `core/project_records.py` — superar e remover registros já gravados, e
  resumir cada um (peça, atualidade das fontes, menor fator, utilização).
  Um registro com `status = "Superado"` sai das cobranças da validação, da
  sequência sugerida e da seleção padrão do memorial, mas continua no
  documento e nas dependências.
- `core/project_diff.py` — comparação campo a campo entre dois documentos
  (revisão × revisão ou revisão × atual), ignorando datas, hashes e estados
  recalculados.
- `core/project_portfolio.py` — resumo comparável de cada projeto, agregação
  da carteira, vencimentos consolidados e próximos passos sugeridos.

`core/project_store.py` mantém a tabela `project_events`: todo
`salvar_projeto` grava o motivo, e uma mudança de `status` sempre gera um
evento próprio, seja qual for a página que a provocou. Criação, cópia,
importação, registro técnico e emissão de memorial têm tipos de evento
específicos. A exportação JSON leva os eventos junto com o histórico.

## Fluxo para adicionar um novo módulo

1. Crie o cálculo em `core/` sem importar Streamlit.
2. Adicione testes determinísticos do núcleo.
3. Registre o `ModuloTecnico` no catálogo central.
4. Crie a página direta em `app_pages/`, mantendo nela somente a interface.
5. Gere o registro técnico v2 e inclua os vínculos aplicáveis.
6. Quando necessário, registre uma regra de validação independente.
7. Quando o módulo precisar de capítulo próprio, registre um provedor de seção.
8. Teste persistência, importação/duplicação, interface e emissão Word/PDF.

## Regras de engenharia para carregamentos

- todos os casos de uma combinação devem usar os mesmos eixos, ponto de
  referência e unidades;
- componentes simultâneos permanecem no mesmo vetor;
- fatores vêm de fontes controladas e não são inferidos pelo aplicativo;
- o envelope identifica um governante por componente;
- máximos de linhas diferentes não formam automaticamente um caso simultâneo;
- a transferência para outro módulo deve usar o vetor completo do cenário
  governante selecionado.

