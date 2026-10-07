# Armazenamento na versão web (Streamlit Cloud)

## O problema

No Streamlit Community Cloud o disco do aplicativo é **temporário**: é apagado a cada reinício —
atualização do código no GitHub, repouso por inatividade, manutenção da hospedagem. O banco de
projetos (`projetos_industriais.sqlite3`) e os catálogos que o usuário cadastra (`perfis_usuario.json`,
`materiais_usuario.json`) ficam nesse disco. O programa gravava e mostrava "salvo", mas na abertura
seguinte o Painel industrial dizia "Nenhum projeto no banco".

Isso não é defeito de uma tela: é a natureza da hospedagem. A solução é guardar uma cópia **fora**
do disco do servidor. No computador do usuário nada disso se aplica — o disco é dele.

## O que o programa faz

| Situação | O que a tela mostra | O que acontece com os dados |
| --- | --- | --- |
| No computador do usuário | Nada de especial: "Salvo no banco local." | O SQLite fica na pasta do usuário (ver README → *Onde ficam os dados*). |
| Na nuvem, **sem** espelho | Aviso amarelo na barra lateral e no Painel industrial: "Versão web: dados temporários". Botão **Baixar meus projetos** em toda página. | Somem no próximo reinício. A carteira baixada traz tudo de volta (Painel → *Restaurar uma carteira exportada*). |
| Na nuvem, **com** espelho no GitHub | "Projetos sincronizados com o GitHub." Mensagem de confirmação: "Salvo e copiado para o GitHub." | Cada gravação é copiada para um repositório privado. Quando o aplicativo sobe de novo, o que o disco perdeu volta sozinho. |
| Espelho configurado, mas o GitHub recusa (token vencido, fora do ar) | Aviso vermelho com a causa e o número de gravações que não chegaram. | O projeto continua salvo no disco do servidor; o envio fica numa fila e é tentado de novo a cada execução. Baixe a carteira antes de fechar. |

O SQLite continua sendo a fonte de trabalho (leitura rápida, nada muda no uso local). O GitHub é só
a cópia que sobrevive ao reinício.

## Ligar o espelho no GitHub (uns 5 minutos)

1. **Repositório de dados.** No GitHub, crie um repositório **privado** só para os dados, por
   exemplo `seu-usuario/mecanica-toolkit-dados`, marcando *Add a README file*. Não use o repositório
   do próprio aplicativo: cada salvamento seria um commit lá e reiniciaria o servidor — e apagaria o
   disco de novo.
2. **Token.** Em *Settings → Developer settings → Personal access tokens → Fine-grained tokens*,
   gere um token que enxergue **somente esse repositório** e tenha a permissão
   *Repository permissions → Contents: Read and write*. Copie o valor (`github_pat_…`).
3. **Segredos.** No Streamlit Cloud, abra o aplicativo → *Settings → Secrets* e cole:

   ```toml
   MECANICA_TOOLKIT_GITHUB_REPO = "seu-usuario/mecanica-toolkit-dados"
   MECANICA_TOOLKIT_GITHUB_TOKEN = "github_pat_..."
   ```

4. **Reinicie** o aplicativo (*Reboot*). Em *Painel industrial → Dados e backup* use
   **Testar conexão** (deve responder "Conectado a … (privado)") e, se já havia projetos no disco do
   servidor, **Enviar todos os projetos ao GitHub agora**.

Para conferir de ponta a ponta: crie um projeto, abra o repositório de dados no GitHub (a pasta
`mecanica_toolkit/projetos/` ganha um arquivo `<id>.json` e um commit por salvamento), reinicie o
aplicativo e veja o projeto ainda lá.

### Variáveis

| Variável | Obrigatória | Para quê |
| --- | --- | --- |
| `MECANICA_TOOLKIT_GITHUB_REPO` | sim | Repositório de dados, no formato `dono/nome`. |
| `MECANICA_TOOLKIT_GITHUB_TOKEN` | sim | Token de acesso (nunca aparece na tela nem em mensagens de erro). |
| `MECANICA_TOOLKIT_GITHUB_BRANCH` | não | Ramo a usar; vazio = ramo padrão do repositório. |
| `MECANICA_TOOLKIT_GITHUB_PASTA` | não | Pasta dentro do repositório; padrão `mecanica_toolkit`. |
| `MECANICA_TOOLKIT_AMBIENTE` | não | `nuvem` ou `local`: força o aviso de dados temporários (outra hospedagem de disco descartável) ou o desliga (servidor próprio com disco permanente). |

Os segredos de primeiro nível do Streamlit viram variáveis de ambiente; o programa também lê o
`.streamlit/secrets.toml` de quem roda por conta própria. Uma variável já definida no ambiente tem
prioridade sobre o segredo. Configuração pela metade (só o repositório, ou só o token) aparece como
erro na barra lateral, em vez de o espelho simplesmente não ligar.

## Como funciona

- **Gravação.** Depois que o SQLite confirma o salvamento, o programa envia o projeto — documento,
  fotografias de revisão e linha do tempo, o mesmo item da carteira exportada — para
  `mecanica_toolkit/projetos/<id>.json`. Os catálogos do usuário vão para
  `mecanica_toolkit/catalogos/`. Excluir um projeto apaga o arquivo (o histórico do Git guarda).
- **Falha nunca desfaz o salvamento.** O envio roda depois da gravação local e não levanta erro: um
  GitHub fora do ar vira aviso na tela e uma fila de pendências, reenviada a cada execução (no máximo
  a cada 20 s) e a cada envio bem-sucedido.
- **Restauração.** Na primeira execução do aplicativo depois de um reinício, o programa lista a pasta
  de projetos, baixa em paralelo o que o disco não tem e importa — com os mesmos `id`, revisões e
  linha do tempo, sem gerar evento novo. Nunca sobrescreve um projeto que já está no disco, e um
  arquivo ilegível no repositório aparece no aviso sem impedir os demais. Se o GitHub falhar nessa
  hora, a tentativa se repete (no máximo a cada 30 s) até dar certo; o botão **Recarregar do GitHub**
  força uma nova leitura.
- **Só biblioteca padrão.** O cliente usa `urllib`; nenhuma dependência nova para o deploy.

| Arquivo | O que tem |
| --- | --- |
| `core/espelho_remoto.py` | Cliente da API de conteúdo do GitHub, configuração, fila de pendências e estado (sem Streamlit). |
| `core/armazenamento.py` | Ambiente (nuvem × local), nível de proteção, restauração na partida e "enviar tudo". |
| `core/project_store.py` | Ganchos de envio em criar, salvar, duplicar, importar e excluir; `restaurar_projetos_do_espelho`. |
| `components/armazenamento_ui.py` | Avisos, botões e o passo a passo exibido na tela. |

Os testes (`tests/test_espelho_remoto.py`, `tests/test_project_store_espelho.py`,
`tests/test_armazenamento.py`) rodam contra `tests/github_falso.py`, um servidor local que guarda os
arquivos e repete as regras da API (`sha` obrigatório para atualizar, `sha` velho recusado, 404 para
repositório sem acesso). Nenhum teste fala com o GitHub de verdade nem herda os segredos de quem
roda a suíte.

## Cuidados

- **O aplicativo é público por padrão.** Quem tem o link abre as páginas, vê os projetos e pode
  baixar a carteira. Com os dados guardados de forma permanente, isso pesa mais: restrinja quem pode
  abrir em *Settings → Sharing* do Streamlit Cloud (visualizadores por e-mail) se os projetos forem
  de cliente.
- **Um servidor, um conjunto de dados.** Não é um banco multiusuário: todos que abrem o aplicativo
  enxergam os mesmos projetos, e o "projeto ativo" é um só no servidor — duas pessoas trabalhando ao
  mesmo tempo disputam o mesmo ponteiro.
- **Token.** Fine-grained, só com o repositório de dados, e com data de validade: ao vencer, a barra
  lateral passa a mostrar "O GitHub recusou o token" e as gravações ficam na fila.
- **Exclusão com o GitHub fora do ar.** A exclusão vale no disco na hora, mas o aviso ao GitHub fica
  numa fila na memória do servidor; se ele reiniciar antes de conseguir enviá-la, o projeto
  excluído volta na próxima restauração (o aviso vermelho da barra lateral mostra que havia
  pendência).
- **Latência.** Cada salvamento faz uma requisição ao GitHub (algumas centenas de milissegundos).
- **Tamanho.** Um arquivo por projeto, com todas as revisões (cada uma é uma fotografia completa do
  documento). Para a quantidade de projetos de uma equipe pequena isso é desprezível; a API de
  conteúdo aceita arquivos de até 100 MB.
- **Outro destino.** O espelho é uma camada pequena e isolada (`core/espelho_remoto.py`). Trocar o
  GitHub por um banco hospedado (Postgres, Supabase, Neon…) ou por armazenamento de objetos (S3,
  Google Drive) significa implementar `listar`, `ler`, `gravar` e `apagar` para o novo destino; o
  restante não muda.
