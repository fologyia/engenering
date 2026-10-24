"""Persistencia local de projetos industriais e registros tecnicos.

O SQLite e a fonte permanente. O Streamlit usa apenas o identificador do
projeto ativo e recarrega o documento sempre que precisa mostrar ou editar.

Onde fica o banco
-----------------
Por padrão, na pasta de dados do usuário — ``%USERPROFILE%\\MecanicaToolkit``
no Windows, ``$XDG_DATA_HOME/mecanica_toolkit`` (ou ``~/.local/share/...``)
nos demais sistemas — e não dentro do repositório. O código costuma viver
numa pasta sincronizada (OneDrive, Google Drive), e um SQLite sincronizado
no meio de uma escrita é a causa clássica de ``database is locked`` e de
arquivo corrompido. A variável de ambiente ``MECANICA_TOOLKIT_DB`` aponta
para outro arquivo quando for preciso (banco de equipe, pasta de rede,
teste manual). Um banco antigo em ``data/`` é copiado para o novo lugar na
primeira abertura e renomeado, para não restarem duas fontes da verdade.

No Windows a pasta fica na raiz do perfil, e não em ``%LOCALAPPDATA%``, de
propósito: aplicativos empacotados (MSIX) — o Claude Desktop, por exemplo,
quando abre o programa pela sua pré-visualização — enxergam uma cópia
privada de ``AppData\\Local`` (``Packages\\...\\LocalCache``). Um banco
gravado ali por esse caminho não existe para o mesmo programa aberto num
terminal comum, e vice-versa: duas carteiras divergindo em silêncio. A raiz
do perfil é a mesma para todos.

Gravações concorrentes
----------------------
Cada linha de ``projects`` guarda um contador de gravações (``write_seq``),
que sai para o documento como ``gravacao`` (ver ``core.projeto_documento``).
:func:`salvar_projeto` só grava se o contador do banco ainda for o que o
documento carregou; duas abas (ou dois engenheiros num banco
compartilhado) editando o mesmo projeto deixam de sobrescrever uma à outra
em silêncio — a segunda gravação é recusada com
:class:`ProjetoConflitoErro` e a tela precisa recarregar.

Divisão do módulo
-----------------
Este arquivo é o núcleo de persistência — estado do banco, conexão,
esquema e migração — e re-exporta no final as operações divididas por
coesão funcional: ``core.project_crud`` (CRUD do projeto),
``core.project_revisions`` (linha do tempo e revisões),
``core.project_registros`` (registros técnicos do projeto),
``core.project_export`` e ``core.project_carteira`` (exportação e
importação JSON), ``core.project_backup`` (backups),
``core.project_espelho`` (espelho remoto) e ``core.projeto_documento``
(documento: fábrica, validação e serialização). Os imports das operações
vêm **depois** das definições deste módulo de propósito: elas importam a
base daqui, e um import no topo criaria um ciclo.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.projeto_documento import (
    CAMPO_GRAVACAO,
    VERSAO_ESQUEMA,
    ProjetoConflitoErro,
    ProjetoPersistenciaErro,
    criar_item,
    novo_projeto_documento,
    revisar_listas,
)

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
NOME_BANCO = "projetos_industriais.sqlite3"
# Onde o banco vivia até setembro de 2026: dentro do repositório, ou seja,
# dentro da pasta sincronizada. Só é lido para a migração.
BANCO_LEGADO = RAIZ_PROJETO / "data" / NOME_BANCO
VARIAVEL_BANCO = "MECANICA_TOOLKIT_DB"
FORMATO_EXPORTACAO = "mecanica-toolkit-project"
FORMATO_CARTEIRA = "mecanica-toolkit-carteira"
# Espelho remoto (ver ``core/project_espelho.py``): um arquivo por projeto, com o documento, as
# fotografias de revisão e a linha do tempo — o mesmo item que a carteira exportada carrega.
FORMATO_ESPELHO = "mecanica-toolkit-espelho-projeto"
PASTA_ESPELHO_PROJETOS = "projetos"


def pasta_dados_usuario() -> Path:
    """Pasta de dados por usuário: raiz do perfil no Windows, XDG nos demais.

    Nada de ``%LOCALAPPDATA%`` no Windows — ver "Onde fica o banco" no
    cabeçalho do módulo.
    """
    if os.name == "nt":
        return Path.home() / "MecanicaToolkit"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "mecanica_toolkit"


def caminho_banco_padrao() -> Path:
    """Banco usado quando nenhum caminho é informado: a variável de ambiente
    ``MECANICA_TOOLKIT_DB`` ou, sem ela, a pasta de dados do usuário."""
    configurado = os.environ.get(VARIAVEL_BANCO, "").strip()
    if configurado:
        return Path(configurado).expanduser()
    return pasta_dados_usuario() / NOME_BANCO


# Calculados uma vez, na importação. Os testes redirecionam ``BANCO_PADRAO``
# para um arquivo temporário; ``_banco`` lê o valor na hora da chamada, e a
# migração do banco antigo só roda quando o padrão é o da instalação.
_BANCO_INSTALACAO: Path = caminho_banco_padrao()
BANCO_PADRAO: str | Path = _BANCO_INSTALACAO


def _banco(caminho_banco: str | Path | None) -> str | Path:
    """Resolve o banco na hora da chamada, e não na definição da função.

    Com ``= BANCO_PADRAO`` no argumento, o valor ficava congelado no momento
    em que o módulo era importado: apontar ``BANCO_PADRAO`` para outro
    arquivo — como um teste faria para se isolar — não tinha efeito nenhum, e
    a escrita ia parar no banco real sem nenhum aviso.
    """
    return BANCO_PADRAO if caminho_banco is None else caminho_banco


@contextmanager
def _conectar(caminho_banco: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Conexão que confirma no fim do bloco, desfaz em erro e *fecha*.

    O ``with`` do próprio ``sqlite3.Connection`` só confirma ou desfaz a
    transação: a conexão continuava aberta até o coletor de lixo passar. No
    Windows isso mantém o arquivo preso — renomear, apagar ou copiar o banco
    falha com "being used by another process" — e é parte do que fazia o
    banco dentro do OneDrive travar. Único ponto que materializa o caminho:
    todas as demais funções apenas repassam o parâmetro.
    """
    caminho = Path(_banco(caminho_banco)).expanduser().resolve()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, timeout=15.0)
    try:
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute("PRAGMA busy_timeout = 15000")
        with conexao:
            yield conexao
    finally:
        conexao.close()


def caminho_banco_atual(caminho_banco: str | Path | None = None) -> Path:
    """Arquivo que as funções deste módulo usam para o argumento dado."""
    return Path(_banco(caminho_banco)).expanduser().resolve()


def _migrar_banco_legado(destino: Path) -> None:
    """Leva o banco de ``data/`` para a pasta de dados do usuário, uma vez só.

    Só age quando o destino ainda não existe e o banco antigo existe: nunca
    sobrescreve, e nunca mexe num banco apontado explicitamente pela
    variável de ambiente. A cópia usa a API de backup do SQLite, que respeita
    o lock de quem ainda estiver com o arquivo antigo aberto (um servidor
    antigo, por exemplo). O original é renomeado, não apagado, para o
    programa antigo e o novo não gravarem em bancos diferentes sem ninguém
    perceber; se outro processo segurar o arquivo, o rename fica de fora e
    a cópia já feita continua valendo.
    """
    if os.environ.get(VARIAVEL_BANCO, "").strip():
        return
    if destino.exists() or not BANCO_LEGADO.exists():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    origem = sqlite3.connect(BANCO_LEGADO, timeout=15.0)
    try:
        copia = sqlite3.connect(destino)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()
    try:
        BANCO_LEGADO.rename(BANCO_LEGADO.with_name(f"{BANCO_LEGADO.name}.migrado"))
    except OSError:
        pass


def _garantir_colunas(conexao: sqlite3.Connection) -> None:
    """Acrescenta colunas criadas depois do esquema original.

    ``CREATE TABLE IF NOT EXISTS`` não altera uma tabela que já existe; um
    banco criado antes da coluna precisa do ``ALTER TABLE``. O contador nasce
    em zero para todas as linhas antigas, que é o valor que a leitura injeta
    no documento — a primeira gravação depois da atualização passa limpa.
    """
    colunas = {linha["name"] for linha in conexao.execute("PRAGMA table_info(projects)")}
    if "write_seq" not in colunas:
        conexao.execute("ALTER TABLE projects ADD COLUMN write_seq INTEGER NOT NULL DEFAULT 0")


def inicializar_banco(caminho_banco: str | Path | None = None) -> None:
    if caminho_banco is None and Path(BANCO_PADRAO) == _BANCO_INSTALACAO:
        _migrar_banco_legado(_BANCO_INSTALACAO)
    with _conectar(caminho_banco) as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                status TEXT NOT NULL,
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_projects_status_updated
                ON projects(status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS project_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, revision)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                description TEXT NOT NULL,
                revision INTEGER NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_project_events_project
                ON project_events(project_id, id DESC);
            """
        )
        _garantir_colunas(conexao)


# As operações do repositório foram divididas por coesão funcional em
# módulos próprios (ver "Divisão do módulo" no cabeçalho) e são re-exportadas
# aqui para os importadores antigos continuarem valendo sem alteração.
# Os imports vêm no fim do arquivo, depois de ``_conectar``,
# ``inicializar_banco`` e das constantes estarem definidos: os módulos de
# operação importam a base deste módulo, e um import no topo criaria um
# ciclo de importação.
from core.project_backup import fazer_backup, listar_backups, pasta_backups  # noqa: E402
from core.project_carteira import (  # noqa: E402
    enviar_projetos_ao_espelho,
    exportar_carteira,
    importar_carteira,
    restaurar_projetos_do_espelho,
)
from core.project_crud import (  # noqa: E402
    arquivar_projeto,
    carregar_projetos,
    criar_projeto,
    definir_projeto_ativo,
    duplicar_projeto,
    excluir_projeto,
    listar_projetos,
    obter_projeto,
    obter_projeto_ativo,
    restaurar_revisao,
    salvar_projeto,
)
from core.project_export import exportar_projeto, importar_projeto  # noqa: E402
from core.project_registros import (  # noqa: E402
    adicionar_registro_tecnico,
    registrar_calculo_tecnico,
)
from core.project_revisions import (  # noqa: E402
    EVENTO_ADMINISTRACAO,
    EVENTO_CRIACAO,
    EVENTO_EMISSAO,
    EVENTO_REGISTRO,
    EVENTO_REVISAO,
    EVENTO_SALVAMENTO,
    EVENTO_SITUACAO,
    historico_eventos,
    historico_revisoes,
    obter_revisao,
)

__all__ = [
    "BANCO_LEGADO",
    "BANCO_PADRAO",
    "CAMPO_GRAVACAO",
    "EVENTO_ADMINISTRACAO",
    "EVENTO_CRIACAO",
    "EVENTO_EMISSAO",
    "EVENTO_REGISTRO",
    "EVENTO_REVISAO",
    "EVENTO_SALVAMENTO",
    "EVENTO_SITUACAO",
    "FORMATO_CARTEIRA",
    "FORMATO_ESPELHO",
    "FORMATO_EXPORTACAO",
    "NOME_BANCO",
    "PASTA_ESPELHO_PROJETOS",
    "ProjetoConflitoErro",
    "ProjetoPersistenciaErro",
    "RAIZ_PROJETO",
    "VARIAVEL_BANCO",
    "VERSAO_ESQUEMA",
    "adicionar_registro_tecnico",
    "arquivar_projeto",
    "caminho_banco_atual",
    "caminho_banco_padrao",
    "carregar_projetos",
    "criar_item",
    "criar_projeto",
    "definir_projeto_ativo",
    "duplicar_projeto",
    "enviar_projetos_ao_espelho",
    "excluir_projeto",
    "exportar_carteira",
    "exportar_projeto",
    "fazer_backup",
    "historico_eventos",
    "historico_revisoes",
    "importar_carteira",
    "importar_projeto",
    "inicializar_banco",
    "listar_backups",
    "listar_projetos",
    "novo_projeto_documento",
    "obter_projeto",
    "obter_projeto_ativo",
    "obter_revisao",
    "pasta_backups",
    "pasta_dados_usuario",
    "registrar_calculo_tecnico",
    "restaurar_projetos_do_espelho",
    "restaurar_revisao",
    "revisar_listas",
    "salvar_projeto",
]
