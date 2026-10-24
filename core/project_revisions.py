"""Linha do tempo e fotografias de revisão do projeto industrial.

A linha do tempo (``project_events``) registra o motivo de cada gravação e
as mudanças de situação; as revisões controladas (``project_revisions``)
guardam a fotografia completa do documento em cada marco. A gravação em si
fica em ``core.project_crud`` — este módulo só lê e escreve as tabelas de
histórico e monta o pacote (documento + revisões + eventos) usado pela
carteira exportada e pelo espelho remoto.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.project_store import _conectar, inicializar_banco
from core.projeto_documento import _agora, _validar_documento

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


def _pacote_projeto(
    conexao: sqlite3.Connection, projeto_id: str, payload_json: str
) -> dict[str, Any]:
    """Documento, fotografias de revisão e linha do tempo de um projeto.

    É o item da carteira exportada e também o arquivo que o espelho remoto guarda.
    """
    revisoes = conexao.execute(
        """
        SELECT revision, reason, created_at, snapshot_json
        FROM project_revisions WHERE project_id=? ORDER BY revision
        """,
        (projeto_id,),
    ).fetchall()
    eventos = conexao.execute(
        """
        SELECT created_at, kind, description, revision, status
        FROM project_events WHERE project_id=? ORDER BY id
        """,
        (projeto_id,),
    ).fetchall()
    return {
        "projeto": _validar_documento(json.loads(payload_json)),
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
