# Robustez — falhas contidas, conferências silenciosas e diagnóstico

Quem usa o programa não vê nada técnico. Uma falha inesperada não derruba a página. Ela vira uma
linha discreta no fim da página, com uma referência curta, e o detalhe vai para o arquivo de
diagnóstico.

> :material/info: Uma parte desta página não pôde ser exibida (ref. 3F2A9C). Se repetir, informe a
> referência.

## Camadas

| Camada | Onde | O que faz |
| --- | --- | --- |
| Página inteira | `app.py` → `executar_pagina` | A página que falha para ali, sem tela de erro; o aviso sai no fim, mesmo com `st.stop()` |
| Seção | `with st.container(border=True), secao_protegida("3. …"):` | A seção que falha some; as outras continuam (88 seções e abas em 14 páginas) |
| Início | `app.py` | Armazenamento, projeto ativo e lateral protegidos; a senha de acesso **não** é contida (falha fechada) |
| Arquivos enviados | `em.ler_arquivo`, `lm.ler_lista_de_corte` | Só sai o erro do módulo (`ArquivoInvalido`, `ListaDeCorteInvalida`) com uma mensagem para quem usa; um trecho inesperado vira essa mensagem com a referência |
| Dados gravados no projeto | `de_dicionario` de plano, base técnica, esforços, lista e placa; `project_store._validar_documento` | O que estiver fora do formato (projeto antigo, editado à mão, corrompido) volta ao padrão campo a campo; listas só com objetos; registros técnicos com os tipos certos e um id estável |
| Valores | `mostrar_tabela_verificacoes`, `botao_registrar_calculo` | NaN (e infinito no solicitante ou no resistente) viram ocorrência de conferência e "—"/"∞" na tela; um registro com NaN ou infinito não é gravado |
| Configuração | `.streamlit/config.toml` | `client.showErrorDetails = "none"`: o que escapar de tudo isso aparece sem detalhe |

Os sinais de controle do Streamlit (`st.stop`, `st.rerun`, `st.switch_page`) derivam de
`BaseException` e atravessam a contenção sem ser engolidos.

## Diagnóstico (`core/diagnostico.py`)

* **Referência**: 6 caracteres do SHA-1 de "tipo da exceção | arquivo:linha" do quadro mais interno
  do código do programa. O mesmo defeito dá sempre a mesma referência, em qualquer máquina.
* **Arquivo**: `diagnostico/ocorrencias.jsonl`, ao lado do banco de projetos
  (`%USERPROFILE%\MecanicaToolkit\diagnostico` no Windows). Uma linha JSON por ocorrência: referência,
  tipo (falha ou conferência), origem ("Página › seção"), resumo, traceback e o momento. Gira acima de
  1 MB, guardando 3 cópias. Gravar nunca derruba o programa: falha de disco é engolida.
* Para depurar com o detalhe na tela: `MECANICA_TOOLKIT_ERROS=levantar` (a falha sobe) e
  `streamlit run app.py --client.showErrorDetails=full`.

## Testes

* Os testes rodam com `MECANICA_TOOLKIT_ERROS=levantar` e `client.showErrorDetails=full`
  (conftest): a contenção nunca esconde um erro de um teste.
* `tests/test_robustez.py`: referência estável, arquivo e rodízio, conferência de números, seção que
  quebra sem derrubar as outras, `st.stop` não engolido, tabela com NaN, registro com NaN não
  gravado, página real com uma seção quebrada e com uma falha fora das seções.
* `tests/test_robustez_entradas.py`: CSV do SolidWorks e lista de corte aleatórios ou estragados
  (cortados, duplicados, trocados), dados do projeto fora do formato e pacotes de projeto e carteira
  estragados — só saem os erros previstos. Foi o que achou cinco fragilidades reais (bytes que nem
  UTF-8 nem cp1252 leem, CSV com aspas soltas, plano, esforços e lista gravados fora do formato,
  versão de esquema não numérica).
* `tests/test_paginas_carregam.py::test_pagina_abre_com_dados_do_projeto_corrompidos`: todas as
  páginas abrem com plano, base técnica, esforços, lista, placa e registros técnicos corrompidos.
