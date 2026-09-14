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
que sai para o documento como ``gravacao``. :func:`salvar_projeto` só grava
se o contador do banco ainda for o que o documento carregou; duas abas (ou
dois engenheiros num banco compartilhado) editando o mesmo projeto deixam
de sobrescrever uma à outra em silêncio — a segunda gravação é recusada
com :class:`ProjetoConflitoErro` e a tela precisa recarregar.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.project_dependencies import (
    preparar_registro_dependencias,
    sincronizar_estados_dependencias,
)
from core.technical_records import normalizar_registro_tecnico

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
NOME_BANCO = "projetos_industriais.sqlite3"
# Onde o banco vivia até setembro de 2026: dentro do repositório, ou seja,
# dentro da pasta sincronizada. Só é lido para a migração.
BANCO_LEGADO = RAIZ_PROJETO / "data" / NOME_BANCO
VARIAVEL_BANCO = "MECANICA_TOOLKIT_DB"
FORMATO_EXPORTACAO = "mecanica-toolkit-project"
FORMATO_CARTEIRA = "mecanica-toolkit-carteira"
VERSAO_ESQUEMA = 1
# Campo do documento que carrega o contador de gravações da linha. Não é
# gravado no payload nem nas fotografias de revisão: é metadado da linha,
# injetado na leitura e conferido na escrita.
CAMPO_GRAVACAO = "gravacao"


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


class ProjetoPersistenciaErro(RuntimeError):
    """Falha controlada de validacao ou persistencia."""


class ProjetoConflitoErro(ProjetoPersistenciaErro):
    """O projeto foi gravado por outra sessão depois que este documento foi lido."""


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_seguro(valor: Any) -> Any:
    """Normaliza estruturas para JSON sem aceitar objetos opacos."""
    try:
        return json.loads(json.dumps(valor, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as erro:
        raise ProjetoPersistenciaErro(
            f"O projeto contem um valor que nao pode ser salvo: {erro}"
        ) from erro


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


# Tipos de evento da linha do tempo. Um salvamento comum antes não deixava
# rastro nenhum: só a revisão controlada era guardada. Agora cada gravação
# registra o motivo, e a mudança de situação vira um evento próprio.
EVENTO_CRIACAO = "criacao"
EVENTO_SALVAMENTO = "salvamento"
EVENTO_REVISAO = "revisao"
EVENTO_SITUACAO = "situacao"
EVENTO_REGISTRO = "registro"
EVENTO_EMISSAO = "emissao"
EVENTO_ADMINISTRACAO = "administracao"


def _registrar_evento(
    conexao: sqlite3.Connection,
    projeto_id: str,
    tipo: str,
    descricao: str,
    *,
    revisao: int,
    status: str,
    instante: str | None = None,
) -> None:
    conexao.execute(
        """
        INSERT INTO project_events
            (project_id, created_at, kind, description, revision, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(projeto_id),
            instante or _agora(),
            str(tipo).strip() or EVENTO_SALVAMENTO,
            str(descricao).strip() or "Salvamento",
            int(revisao),
            str(status),
        ),
    )


def historico_eventos(
    projeto_id: str,
    *,
    limite: int | None = None,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Linha do tempo do projeto, do evento mais recente para o mais antigo."""
    inicializar_banco(caminho_banco)
    sql = (
        "SELECT created_at, kind, description, revision, status FROM project_events "
        "WHERE project_id=? ORDER BY id DESC"
    )
    parametros: tuple[Any, ...] = (str(projeto_id),)
    if limite is not None:
        sql += " LIMIT ?"
        parametros = (*parametros, int(limite))
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [
        {
            "quando": linha["created_at"],
            "tipo": linha["kind"],
            "descricao": linha["description"],
            "revisao": linha["revision"],
            "status": linha["status"],
        }
        for linha in linhas
    ]


def novo_projeto_documento(
    nome: str,
    *,
    codigo: str = "",
    cliente: str = "",
    unidade_industrial: str = "",
    area: str = "",
    tag_equipamento: str = "",
    descricao: str = "",
    objetivo: str = "",
    tipo_projeto: str = "",
) -> dict[str, Any]:
    nome_limpo = str(nome).strip()
    if not nome_limpo:
        raise ProjetoPersistenciaErro("Informe o nome do projeto.")
    instante = _agora()
    identificador = str(uuid4())
    codigo_limpo = str(codigo).strip() or f"PRJ-{instante[:10].replace('-', '')}"
    return {
        "schema_version": VERSAO_ESQUEMA,
        "id": identificador,
        "nome": nome_limpo,
        "codigo": codigo_limpo,
        "status": "Em elaboração",
        "revisao": 0,
        "criado_em": instante,
        "atualizado_em": instante,
        "cliente": str(cliente).strip(),
        "unidade_industrial": str(unidade_industrial).strip(),
        "area": str(area).strip(),
        "tag_equipamento": str(tag_equipamento).strip(),
        "tipo_projeto": str(tipo_projeto).strip() or "Projeto industrial",
        "descricao": str(descricao).strip(),
        # O objetivo bloqueia a emissão do memorial, então precisa poder ser
        # informado já na criação — antes ele só aceitava ficar vazio, e todo
        # projeto nascia bloqueado.
        "objetivo": str(objetivo).strip(),
        "processo": "",
        "regime_operacao": "",
        "responsavel": "",
        "verificador": "",
        "aprovador": "",
        "base_projeto": {
            "referencias_desenho": "",
            "base_carregamentos": "",
            "condicoes_operacao": "",
            "criterio_aceitacao": "",
            "vida_requerida": "",
            "limitacoes": "",
        },
        "componentes": [],
        "materiais_projeto": [],
        "casos_carga": [],
        "combinacoes_carga": [],
        "normas": [],
        "registros_tecnicos": [],
        "checklist": [],
        "anexos": [],
        "configuracao_relatorio": {
            "perfil": "Memorial industrial completo",
            "incluir_resumo": True,
            "incluir_validacao": True,
            "incluir_apendice": True,
        },
    }


def _validar_documento(projeto: Mapping[str, Any]) -> dict[str, Any]:
    documento = _json_seguro(dict(projeto))
    if int(documento.get("schema_version", 0)) != VERSAO_ESQUEMA:
        raise ProjetoPersistenciaErro(
            f"Versao de projeto nao suportada: {documento.get('schema_version')}."
        )
    for campo in ("id", "nome", "codigo", "status"):
        if not str(documento.get(campo, "")).strip():
            raise ProjetoPersistenciaErro(f"Campo obrigatorio ausente: {campo}.")
    # Campos adicionados de forma compatível: projetos da versão 1 são
    # completados na leitura sem exigir uma migração destrutiva do SQLite.
    documento.setdefault("materiais_projeto", [])
    documento.setdefault("casos_carga", [])
    documento.setdefault("combinacoes_carga", [])
    documento.setdefault("configuracao_relatorio", {})
    for campo in (
        "componentes",
        "materiais_projeto",
        "casos_carga",
        "combinacoes_carga",
        "normas",
        "registros_tecnicos",
        "checklist",
        "anexos",
    ):
        if not isinstance(documento.get(campo, []), list):
            raise ProjetoPersistenciaErro(f"O campo '{campo}' deve ser uma lista.")
    if not isinstance(documento.get("base_projeto", {}), dict):
        raise ProjetoPersistenciaErro("O campo 'base_projeto' deve ser um objeto.")
    return documento


def _sem_token(documento: Mapping[str, Any]) -> dict[str, Any]:
    """Cópia do documento sem o contador de gravações."""
    return {chave: valor for chave, valor in documento.items() if chave != CAMPO_GRAVACAO}


def _payload(documento: Mapping[str, Any]) -> str:
    """Serializa o documento para a linha, sem o contador de gravações."""
    return json.dumps(_sem_token(documento), ensure_ascii=False, sort_keys=True)


def _documento_da_linha(linha: sqlite3.Row) -> dict[str, Any]:
    """Documento validado com o contador de gravações da linha injetado."""
    documento = _validar_documento(json.loads(linha["payload_json"]))
    documento[CAMPO_GRAVACAO] = int(linha["write_seq"])
    return documento


def _ler_pacote(conteudo: bytes | str) -> dict[str, Any]:
    try:
        texto = conteudo.decode("utf-8-sig") if isinstance(conteudo, bytes) else conteudo
        pacote = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ProjetoPersistenciaErro(f"Arquivo de projeto invalido: {erro}") from erro
    if not isinstance(pacote, dict):
        raise ProjetoPersistenciaErro("Arquivo de projeto invalido: esperava um objeto JSON.")
    return pacote


def criar_projeto(
    nome: str,
    *,
    caminho_banco: str | Path | None = None,
    ativar: bool = True,
    **campos: Any,
) -> dict[str, Any]:
    inicializar_banco(caminho_banco)
    projeto = novo_projeto_documento(nome, **campos)
    payload = _payload(projeto)
    projeto[CAMPO_GRAVACAO] = 0
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                projeto["id"],
                projeto["nome"],
                projeto["codigo"],
                projeto["status"],
                projeto["revisao"],
                projeto["criado_em"],
                projeto["atualizado_em"],
                payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (projeto["id"], 0, "Criação do projeto", projeto["criado_em"], payload),
        )
        _registrar_evento(
            conexao,
            projeto["id"],
            EVENTO_CRIACAO,
            "Criação do projeto",
            revisao=0,
            status=projeto["status"],
            instante=projeto["criado_em"],
        )
        if ativar:
            conexao.execute(
                """
                INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (projeto["id"],),
            )
    return deepcopy(projeto)


def listar_projetos(
    *,
    incluir_arquivados: bool = False,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    inicializar_banco(caminho_banco)
    sql = "SELECT id, name, code, status, revision, created_at, updated_at FROM projects"
    parametros: tuple[Any, ...] = ()
    if not incluir_arquivados:
        sql += " WHERE status <> ?"
        parametros = ("Arquivado",)
    sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [
        {
            "id": linha["id"],
            "nome": linha["name"],
            "codigo": linha["code"],
            "status": linha["status"],
            "revisao": linha["revision"],
            "criado_em": linha["created_at"],
            "atualizado_em": linha["updated_at"],
        }
        for linha in linhas
    ]


def carregar_projetos(
    *,
    incluir_arquivados: bool = False,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Documentos completos de todos os projetos, na ordem de :func:`listar_projetos`.

    O painel de carteira precisa validar cada projeto, e isso exige o
    documento inteiro — não a linha de resumo. Uma consulta só, em vez de
    uma por projeto.
    """
    inicializar_banco(caminho_banco)
    sql = "SELECT payload_json, write_seq FROM projects"
    parametros: tuple[Any, ...] = ()
    if not incluir_arquivados:
        sql += " WHERE status <> ?"
        parametros = ("Arquivado",)
    sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [_documento_da_linha(linha) for linha in linhas]


def obter_projeto(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any] | None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            "SELECT payload_json, write_seq FROM projects WHERE id = ?", (str(projeto_id),)
        ).fetchone()
    if linha is None:
        return None
    return _documento_da_linha(linha)


def salvar_projeto(
    projeto: Mapping[str, Any],
    *,
    motivo: str = "Salvamento",
    criar_revisao: bool = False,
    tipo_evento: str = "",
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    """Grava o documento e anota o motivo na linha do tempo.

    Uma mudança de situação (``status``) sempre gera um evento próprio, seja
    qual for o caminho que a provocou — formulário, fluxo com portões,
    arquivamento ou restauração — para a linha do tempo não depender de cada
    página lembrar de avisar.

    O documento carrega o contador de gravações que leu do banco
    (``gravacao``). Se o banco já estiver adiante — outra aba ou outra
    pessoa gravou no meio do caminho — a escrita é recusada com
    :class:`ProjetoConflitoErro` em vez de sobrescrever a gravação alheia.
    Documentos sem o campo (fotografias de revisão restauradas, documentos
    montados à mão) não são conferidos: são sobrescritas deliberadas.
    """
    inicializar_banco(caminho_banco)
    documento = _validar_documento(projeto)
    gravacao_lida = documento.pop(CAMPO_GRAVACAO, None)
    instante = _agora()
    with _conectar(caminho_banco) as conexao:
        atual = conexao.execute(
            "SELECT revision, created_at, status, write_seq FROM projects WHERE id = ?",
            (documento["id"],),
        ).fetchone()
        if atual is None:
            raise ProjetoPersistenciaErro("Projeto nao encontrado no banco.")
        gravacao_atual = int(atual["write_seq"])
        if gravacao_lida is not None and int(gravacao_lida) != gravacao_atual:
            raise ProjetoConflitoErro(
                "Este projeto foi gravado por outra sessão depois que esta tela o carregou "
                f"(gravação nº {gravacao_atual} no banco, nº {int(gravacao_lida)} nesta tela). "
                "Recarregue a página e refaça a alteração, para não sobrescrever o que já foi salvo."
            )
        revisao = int(atual["revision"]) + (1 if criar_revisao else 0)
        status_anterior = str(atual["status"])
        documento["revisao"] = revisao
        documento["criado_em"] = atual["created_at"]
        documento["atualizado_em"] = instante
        payload = _payload(documento)
        # A condição ``write_seq=?`` fecha a janela entre o SELECT acima e
        # este UPDATE: quem gravou nesse intervalo faz o UPDATE não casar
        # nenhuma linha, e a recusa vale mesmo para documentos sem o campo.
        gravados = conexao.execute(
            """
            UPDATE projects
            SET name=?, code=?, status=?, revision=?, updated_at=?, payload_json=?, write_seq=?
            WHERE id=? AND write_seq=?
            """,
            (
                documento["nome"],
                documento["codigo"],
                documento["status"],
                revisao,
                instante,
                payload,
                gravacao_atual + 1,
                documento["id"],
                gravacao_atual,
            ),
        ).rowcount
        if gravados != 1:
            raise ProjetoConflitoErro(
                "Este projeto foi gravado por outra sessão neste exato momento. "
                "Recarregue a página e refaça a alteração."
            )
        documento[CAMPO_GRAVACAO] = gravacao_atual + 1
        if criar_revisao:
            conexao.execute(
                """
                INSERT INTO project_revisions
                    (project_id, revision, reason, created_at, snapshot_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    documento["id"],
                    revisao,
                    str(motivo).strip() or "Nova revisao",
                    instante,
                    payload,
                ),
            )
        tipo = str(tipo_evento).strip() or (EVENTO_REVISAO if criar_revisao else EVENTO_SALVAMENTO)
        descricao = str(motivo).strip() or (
            f"Revisão {revisao:02d} criada" if criar_revisao else "Salvamento"
        )
        if criar_revisao and tipo == EVENTO_REVISAO:
            descricao = f"Revisão {revisao:02d}: {descricao}"
        _registrar_evento(
            conexao,
            documento["id"],
            tipo,
            descricao,
            revisao=revisao,
            status=documento["status"],
            instante=instante,
        )
        if documento["status"] != status_anterior:
            _registrar_evento(
                conexao,
                documento["id"],
                EVENTO_SITUACAO,
                f"Situação alterada de {status_anterior} para {documento['status']}",
                revisao=revisao,
                status=documento["status"],
                instante=instante,
            )
    return deepcopy(documento)


def historico_revisoes(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(
            """
            SELECT revision, reason, created_at
            FROM project_revisions
            WHERE project_id=? ORDER BY revision DESC
            """,
            (str(projeto_id),),
        ).fetchall()
    return [
        {
            "revisao": linha["revision"],
            "motivo": linha["reason"],
            "criado_em": linha["created_at"],
        }
        for linha in linhas
    ]


def obter_revisao(
    projeto_id: str,
    revisao: int,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any] | None:
    """Documento fotografado numa revisão controlada, sem alterar nada."""
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            """
            SELECT snapshot_json FROM project_revisions
            WHERE project_id=? AND revision=?
            """,
            (str(projeto_id), int(revisao)),
        ).fetchone()
    if linha is None:
        return None
    return _validar_documento(json.loads(linha["snapshot_json"]))


def restaurar_revisao(
    projeto_id: str,
    revisao: int,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    documento = obter_revisao(projeto_id, revisao, caminho_banco=caminho_banco)
    if documento is None:
        raise ProjetoPersistenciaErro("Revisao nao encontrada.")
    documento["status"] = "Em elaboração"
    return salvar_projeto(
        documento,
        motivo=f"Restauracao da revisao {int(revisao):02d}",
        criar_revisao=True,
        caminho_banco=caminho_banco,
    )


def definir_projeto_ativo(
    projeto_id: str | None,
    *,
    caminho_banco: str | Path | None = None,
) -> None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        if projeto_id is None:
            conexao.execute("DELETE FROM app_settings WHERE key='active_project_id'")
            return
        existe = conexao.execute("SELECT 1 FROM projects WHERE id=?", (str(projeto_id),)).fetchone()
        if existe is None:
            raise ProjetoPersistenciaErro("Projeto ativo nao encontrado.")
        conexao.execute(
            """
            INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(projeto_id),),
        )


def obter_projeto_ativo(*, caminho_banco: str | Path | None = None) -> dict[str, Any] | None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            "SELECT value FROM app_settings WHERE key='active_project_id'"
        ).fetchone()
    if linha is None:
        return None
    projeto = obter_projeto(linha["value"], caminho_banco=caminho_banco)
    if projeto is None:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    return projeto


def arquivar_projeto(
    projeto_id: str,
    *,
    arquivado: bool = True,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    projeto["status"] = "Arquivado" if arquivado else "Em elaboração"
    salvo = salvar_projeto(
        projeto,
        motivo="Projeto arquivado" if arquivado else "Projeto desarquivado",
        tipo_evento=EVENTO_ADMINISTRACAO,
        caminho_banco=caminho_banco,
    )
    ativo = obter_projeto_ativo(caminho_banco=caminho_banco)
    if arquivado and ativo and ativo["id"] == projeto_id:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    return salvo


def excluir_projeto(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> None:
    """Apaga o projeto e todo o seu histórico de revisões, sem volta.

    Diferente de :func:`arquivar_projeto`, que só esconde o projeto da lista,
    esta operação remove as linhas do banco. As revisões caem em cascata
    pela chave estrangeira; o ponteiro de projeto ativo é limpo antes, para
    que nenhuma página fique apontando para um id inexistente.
    """
    inicializar_banco(caminho_banco)
    ativo = obter_projeto_ativo(caminho_banco=caminho_banco)
    if ativo and ativo["id"] == projeto_id:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    with _conectar(caminho_banco) as conexao:
        removido = conexao.execute("DELETE FROM projects WHERE id=?", (str(projeto_id),)).rowcount
    if not removido:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")


def _renumerar_itens_copia(copia: dict[str, Any]) -> dict[str, Any]:
    """Renova IDs internos e preserva vínculos ao duplicar ou importar."""
    colecoes = (
        "componentes",
        "materiais_projeto",
        "casos_carga",
        "combinacoes_carga",
        "normas",
        "registros_tecnicos",
        "checklist",
        "anexos",
    )
    mapas: dict[str, dict[str, str]] = {}
    for colecao in colecoes:
        mapa: dict[str, str] = {}
        for item in copia.get(colecao, []):
            if not isinstance(item, dict):
                continue
            antigo = str(item.get("id") or "")
            novo = str(uuid4())
            item["id"] = novo
            if antigo:
                mapa[antigo] = novo
        mapas[colecao] = mapa

    mapa_componentes = mapas["componentes"]
    mapa_materiais = mapas["materiais_projeto"]
    mapa_casos = mapas["casos_carga"]
    mapa_registros = mapas["registros_tecnicos"]
    for componente in copia.get("componentes", []):
        if isinstance(componente, dict):
            material_id = str(componente.get("material_id") or "")
            if material_id in mapa_materiais:
                componente["material_id"] = mapa_materiais[material_id]
    for material in copia.get("materiais_projeto", []):
        if isinstance(material, dict):
            material["vinculacoes"] = [
                mapa_componentes.get(str(valor), str(valor))
                for valor in material.get("vinculacoes", [])
            ]
    for combinacao in copia.get("combinacoes_carga", []):
        if not isinstance(combinacao, dict):
            continue
        fatores = combinacao.get("fatores", {})
        if isinstance(fatores, Mapping):
            combinacao["fatores"] = {
                mapa_casos.get(str(caso_id), str(caso_id)): fator
                for caso_id, fator in fatores.items()
            }
    for registro in copia.get("registros_tecnicos", []):
        if not isinstance(registro, dict):
            continue
        for campo, mapa in (
            ("casos_carga_ids", mapa_casos),
            ("componentes_ids", mapa_componentes),
            ("materiais_ids", mapa_materiais),
        ):
            registro[campo] = [
                mapa.get(str(valor), str(valor)) for valor in registro.get(campo, [])
            ]
        entradas = registro.get("entradas")
        if isinstance(entradas, dict):
            if str(entradas.get("material_id") or "") in mapa_materiais:
                entradas["material_id"] = mapa_materiais[str(entradas["material_id"])]
            if str(entradas.get("registro_origem") or "") in mapa_registros:
                entradas["registro_origem"] = mapa_registros[str(entradas["registro_origem"])]
        # A assinatura anterior deixa de ser válida após a troca deliberada dos IDs.
        registro.pop("hash_calculo", None)
        registro.update(normalizar_registro_tecnico(registro))
    return copia


def duplicar_projeto(
    projeto_id: str,
    *,
    novo_nome: str | None = None,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    origem = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if origem is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    instante = _agora()
    copia = deepcopy(origem)
    copia["id"] = str(uuid4())
    copia["nome"] = str(novo_nome).strip() if novo_nome else f"{origem['nome']} - cópia"
    copia["codigo"] = f"{origem['codigo']}-COPIA"
    copia["status"] = "Em elaboração"
    copia["revisao"] = 0
    copia["criado_em"] = instante
    copia["atualizado_em"] = instante
    _renumerar_itens_copia(copia)
    payload = _payload(_validar_documento(copia))
    copia[CAMPO_GRAVACAO] = 0
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                copia["id"],
                copia["nome"],
                copia["codigo"],
                copia["status"],
                instante,
                instante,
                payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, 0, ?, ?, ?)
            """,
            (copia["id"], f"Cópia de {origem['codigo']}", instante, payload),
        )
        _registrar_evento(
            conexao,
            copia["id"],
            EVENTO_CRIACAO,
            f"Criado como cópia de {origem['codigo']} · {origem['nome']}",
            revisao=0,
            status=copia["status"],
            instante=instante,
        )
    definir_projeto_ativo(copia["id"], caminho_banco=caminho_banco)
    return deepcopy(copia)


def _motivo_registro(registro: Mapping[str, Any]) -> str:
    modulo = str(registro.get("modulo") or "Registro técnico").strip()
    titulo = str(registro.get("titulo") or "").strip()
    return (
        f"Registro técnico incluído: {modulo} · {titulo}"
        if titulo
        else f"Registro técnico incluído: {modulo}"
    )


def adicionar_registro_tecnico(
    projeto_id: str,
    registro: Mapping[str, Any],
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    item = _json_seguro(normalizar_registro_tecnico(registro))
    projeto["registros_tecnicos"].append(item)
    return salvar_projeto(
        projeto,
        motivo=_motivo_registro(item),
        tipo_evento=EVENTO_REGISTRO,
        caminho_banco=caminho_banco,
    )


def registrar_calculo_tecnico(
    projeto_id: str,
    registro: Mapping[str, Any],
    *,
    dependencias_chaves: Sequence[str] = (),
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    """Anexa um registro técnico fotografando as fontes que ele consumiu.

    Diferente de :func:`adicionar_registro_tecnico`, esta função também
    reavalia a atualidade de *todos* os cálculos do projeto após a inclusão,
    para que um material, caso de carga ou registro de origem alterado
    apareça como desatualizado assim que outro cálculo for salvo.
    """
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    item = preparar_registro_dependencias(
        projeto, registro, dependencias_chaves=dependencias_chaves
    )
    projeto["registros_tecnicos"] = [
        *projeto["registros_tecnicos"],
        _json_seguro(item),
    ]
    projeto = sincronizar_estados_dependencias(projeto)
    return salvar_projeto(
        projeto,
        motivo=_motivo_registro(item),
        tipo_evento=EVENTO_REGISTRO,
        caminho_banco=caminho_banco,
    )


def exportar_projeto(
    projeto_id: str,
    *,
    incluir_historico: bool = True,
    caminho_banco: str | Path | None = None,
) -> bytes:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    pacote = {
        "formato": FORMATO_EXPORTACAO,
        "versao": VERSAO_ESQUEMA,
        "exportado_em": _agora(),
        "projeto": _sem_token(projeto),
        "historico": (
            historico_revisoes(projeto_id, caminho_banco=caminho_banco) if incluir_historico else []
        ),
        "eventos": (
            historico_eventos(projeto_id, caminho_banco=caminho_banco) if incluir_historico else []
        ),
    }
    return json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8")


def importar_projeto(
    conteudo: bytes | str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    pacote = _ler_pacote(conteudo)
    if pacote.get("formato") != FORMATO_EXPORTACAO:
        raise ProjetoPersistenciaErro("O arquivo nao e um projeto do Mecanica Toolkit.")
    origem = _validar_documento(pacote.get("projeto", {}))
    copia = deepcopy(origem)
    instante = _agora()
    copia["id"] = str(uuid4())
    copia["nome"] = f"{origem['nome']} - importado"
    copia["codigo"] = f"{origem['codigo']}-IMP"
    copia["status"] = "Em elaboração"
    copia["revisao"] = 0
    copia["criado_em"] = instante
    copia["atualizado_em"] = instante
    _renumerar_itens_copia(copia)
    inicializar_banco(caminho_banco)
    payload = _payload(copia)
    copia[CAMPO_GRAVACAO] = 0
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                copia["id"],
                copia["nome"],
                copia["codigo"],
                copia["status"],
                instante,
                instante,
                payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, 0, 'Importação de projeto', ?, ?)
            """,
            (copia["id"], instante, payload),
        )
        _registrar_evento(
            conexao,
            copia["id"],
            EVENTO_CRIACAO,
            f"Importado do arquivo exportado de {origem['codigo']} · {origem['nome']}",
            revisao=0,
            status=copia["status"],
            instante=instante,
        )
    definir_projeto_ativo(copia["id"], caminho_banco=caminho_banco)
    return deepcopy(copia)


def pasta_backups(caminho_banco: str | Path | None = None) -> Path:
    """Pasta ``backups/`` ao lado do banco."""
    return caminho_banco_atual(caminho_banco).parent / "backups"


def fazer_backup(
    destino: str | Path | None = None,
    *,
    caminho_banco: str | Path | None = None,
) -> Path:
    """Copia íntegra e compactada do banco (``VACUUM INTO``), num arquivo novo.

    Sem ``destino``, grava em ``backups/`` ao lado do banco, com data e hora
    no nome. Nunca sobrescreve: um destino que já existe é erro, não
    substituição. O ``VACUUM INTO`` é transacional do lado do SQLite — a
    cópia sai consistente mesmo com o programa aberto — e não pode rodar
    dentro de uma transação, por isso usa uma conexão própria.
    """
    inicializar_banco(caminho_banco)
    origem = caminho_banco_atual(caminho_banco)
    if destino is None:
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        pasta = origem.parent / "backups"
        alvo = pasta / f"{origem.stem}-{carimbo}{origem.suffix}"
        sequencia = 1
        while alvo.exists():
            alvo = pasta / f"{origem.stem}-{carimbo}-{sequencia}{origem.suffix}"
            sequencia += 1
    else:
        alvo = Path(destino).expanduser().resolve()
    if alvo.exists():
        raise ProjetoPersistenciaErro(f"Ja existe um arquivo em {alvo}; o backup nao sobrescreve.")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(origem, timeout=15.0)
    try:
        conexao.execute("VACUUM INTO ?", (str(alvo),))
    except sqlite3.Error as erro:
        raise ProjetoPersistenciaErro(f"Nao foi possivel gerar o backup: {erro}") from erro
    finally:
        conexao.close()
    return alvo


def listar_backups(caminho_banco: str | Path | None = None) -> list[dict[str, Any]]:
    """Backups da pasta padrão, do mais recente para o mais antigo."""
    pasta = pasta_backups(caminho_banco)
    if not pasta.is_dir():
        return []
    arquivos = sorted(
        (item for item in pasta.glob("*.sqlite3") if item.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "caminho": arquivo,
            "nome": arquivo.name,
            "tamanho_bytes": arquivo.stat().st_size,
            "modificado_em": datetime.fromtimestamp(arquivo.stat().st_mtime)
            .astimezone()
            .isoformat(timespec="seconds"),
        }
        for arquivo in arquivos
    ]


def exportar_carteira(
    *,
    incluir_arquivados: bool = True,
    caminho_banco: str | Path | None = None,
) -> bytes:
    """Todos os projetos num JSON só, com revisões e linha do tempo.

    Diferente de :func:`exportar_projeto`, leva a fotografia de cada revisão
    controlada — é um pacote de restauração, não só de leitura — e por isso
    :func:`importar_carteira` consegue devolver o histórico inteiro.
    """
    inicializar_banco(caminho_banco)
    sql = "SELECT id, payload_json FROM projects"
    parametros: tuple[Any, ...] = ()
    if not incluir_arquivados:
        sql += " WHERE status <> ?"
        parametros = ("Arquivado",)
    sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
    pacotes: list[dict[str, Any]] = []
    with _conectar(caminho_banco) as conexao:
        for linha in conexao.execute(sql, parametros).fetchall():
            revisoes = conexao.execute(
                """
                SELECT revision, reason, created_at, snapshot_json
                FROM project_revisions WHERE project_id=? ORDER BY revision
                """,
                (linha["id"],),
            ).fetchall()
            eventos = conexao.execute(
                """
                SELECT created_at, kind, description, revision, status
                FROM project_events WHERE project_id=? ORDER BY id
                """,
                (linha["id"],),
            ).fetchall()
            pacotes.append(
                {
                    "projeto": _validar_documento(json.loads(linha["payload_json"])),
                    "revisoes": [
                        {
                            "revisao": item["revision"],
                            "motivo": item["reason"],
                            "criado_em": item["created_at"],
                            "documento": json.loads(item["snapshot_json"]),
                        }
                        for item in revisoes
                    ],
                    "eventos": [
                        {
                            "quando": item["created_at"],
                            "tipo": item["kind"],
                            "descricao": item["description"],
                            "revisao": item["revision"],
                            "status": item["status"],
                        }
                        for item in eventos
                    ],
                }
            )
    pacote = {
        "formato": FORMATO_CARTEIRA,
        "versao": VERSAO_ESQUEMA,
        "exportado_em": _agora(),
        "projetos": pacotes,
    }
    return json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8")


def importar_carteira(
    conteudo: bytes | str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, list[str]]:
    """Restaura os projetos de um pacote de carteira, com identidade e histórico.

    Projetos cujo ``id`` já existe no banco são ignorados: a restauração
    nunca sobrescreve o que está gravado. Quem quiser uma cópia de um
    projeto que já existe usa :func:`importar_projeto` com o pacote
    individual. Tudo entra numa transação só — um pacote malformado não
    deixa metade dos projetos no banco. O projeto ativo não muda. Devolve
    os códigos importados e os ignorados.
    """
    pacote = _ler_pacote(conteudo)
    if pacote.get("formato") != FORMATO_CARTEIRA:
        raise ProjetoPersistenciaErro(
            "O arquivo nao e uma carteira exportada pelo Mecanica Toolkit."
        )
    itens = pacote.get("projetos")
    if not isinstance(itens, list):
        raise ProjetoPersistenciaErro("A carteira exportada nao traz a lista de projetos.")
    inicializar_banco(caminho_banco)
    importados: list[str] = []
    ignorados: list[str] = []
    with _conectar(caminho_banco) as conexao:
        for item in itens:
            if not isinstance(item, Mapping):
                raise ProjetoPersistenciaErro("A carteira exportada tem um projeto malformado.")
            documento = _sem_token(_validar_documento(item.get("projeto", {})))
            existe = conexao.execute(
                "SELECT 1 FROM projects WHERE id=?", (documento["id"],)
            ).fetchone()
            if existe is not None:
                ignorados.append(str(documento["codigo"]))
                continue
            conexao.execute(
                """
                INSERT INTO projects
                    (id, name, code, status, revision, created_at, updated_at,
                     payload_json, write_seq)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    documento["id"],
                    documento["nome"],
                    documento["codigo"],
                    documento["status"],
                    int(documento.get("revisao", 0)),
                    str(documento.get("criado_em") or _agora()),
                    str(documento.get("atualizado_em") or _agora()),
                    _payload(documento),
                ),
            )
            for revisao in item.get("revisoes", []):
                fotografia = revisao.get("documento") if isinstance(revisao, Mapping) else None
                if not isinstance(fotografia, Mapping):
                    raise ProjetoPersistenciaErro(
                        f"A carteira exportada tem uma revisao sem documento em {documento['codigo']}."
                    )
                conexao.execute(
                    """
                    INSERT INTO project_revisions
                        (project_id, revision, reason, created_at, snapshot_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        documento["id"],
                        int(revisao.get("revisao", 0)),
                        str(revisao.get("motivo") or "Revisao"),
                        str(revisao.get("criado_em") or documento.get("criado_em") or _agora()),
                        json.dumps(_sem_token(fotografia), ensure_ascii=False, sort_keys=True),
                    ),
                )
            for evento in item.get("eventos", []):
                if not isinstance(evento, Mapping):
                    continue
                _registrar_evento(
                    conexao,
                    documento["id"],
                    str(evento.get("tipo") or EVENTO_SALVAMENTO),
                    str(evento.get("descricao") or ""),
                    revisao=int(evento.get("revisao") or 0),
                    status=str(evento.get("status") or documento["status"]),
                    instante=str(evento.get("quando") or "") or None,
                )
            _registrar_evento(
                conexao,
                documento["id"],
                EVENTO_ADMINISTRACAO,
                "Restaurado de uma carteira exportada",
                revisao=int(documento.get("revisao", 0)),
                status=documento["status"],
            )
            importados.append(str(documento["codigo"]))
    return {"importados": importados, "ignorados": ignorados}


def criar_item(
    **campos: Any,
) -> dict[str, Any]:
    """Cria uma linha identificada para componentes, normas ou checklists."""
    return {"id": str(uuid4()), **_json_seguro(campos)}


def revisar_listas(
    projeto: Mapping[str, Any],
    *,
    componentes: Sequence[Mapping[str, Any]] | None = None,
    normas: Sequence[Mapping[str, Any]] | None = None,
    checklist: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    documento = deepcopy(dict(projeto))
    if componentes is not None:
        documento["componentes"] = [_json_seguro(dict(item)) for item in componentes]
    if normas is not None:
        documento["normas"] = [_json_seguro(dict(item)) for item in normas]
    if checklist is not None:
        documento["checklist"] = [_json_seguro(dict(item)) for item in checklist]
    return documento
