"""Carteira de projetos: exportação, importação e sincronização com o espelho.

A carteira exportada (``FORMATO_CARTEIRA``) leva todos os projetos num JSON
só, com a fotografia de cada revisão controlada e a linha do tempo — é um
pacote de restauração, não só de leitura. A importação preserva identidade e
histórico e nunca sobrescreve o que já está no banco. As funções
:func:`restaurar_projetos_do_espelho` e :func:`enviar_projetos_ao_espelho`
movem a carteira inteira entre o disco local e o espelho remoto
(``core.espelho_remoto``).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core import espelho_remoto
from core.project_espelho import _espelhar_projeto
from core.project_revisions import (
    EVENTO_ADMINISTRACAO,
    EVENTO_SALVAMENTO,
    _pacote_projeto,
    _registrar_evento,
)
from core.project_store import (
    FORMATO_CARTEIRA,
    PASTA_ESPELHO_PROJETOS,
    _conectar,
    inicializar_banco,
)
from core.projeto_documento import (
    VERSAO_ESQUEMA,
    ProjetoPersistenciaErro,
    _agora,
    _ler_pacote,
    _payload,
    _sem_token,
    _validar_documento,
)


def exportar_carteira(
    *,
    incluir_arquivados: bool = True,
    caminho_banco: str | Path | None = None,
) -> bytes:
    """Todos os projetos num JSON só, com revisões e linha do tempo.

    Diferente de :func:`core.project_export.exportar_projeto`, leva a
    fotografia de cada revisão controlada — é um pacote de restauração, não
    só de leitura — e por isso :func:`importar_carteira` consegue devolver o
    histórico inteiro.
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
            pacotes.append(_pacote_projeto(conexao, linha["id"], linha["payload_json"]))
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
    registrar_evento: bool = True,
    espelhar: bool = True,
) -> dict[str, list[str]]:
    """Restaura os projetos de um pacote de carteira, com identidade e histórico.

    Projetos cujo ``id`` já existe no banco são ignorados: a restauração
    nunca sobrescreve o que está gravado. Quem quiser uma cópia de um
    projeto que já existe usa :func:`core.project_export.importar_projeto`
    com o pacote individual. Tudo entra numa transação só — um pacote
    malformado não deixa metade dos projetos no banco. O projeto ativo não
    muda. Devolve os códigos importados e os ignorados.

    ``registrar_evento`` e ``espelhar`` existem para a restauração a partir do
    espelho remoto (:func:`restaurar_projetos_do_espelho`): o que veio de lá
    já está lá, então não gera o evento "Restaurado…" a cada reinício do
    servidor nem é enviado de volta.
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
    ids_importados: list[str] = []
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
            if registrar_evento:
                _registrar_evento(
                    conexao,
                    documento["id"],
                    EVENTO_ADMINISTRACAO,
                    "Restaurado de uma carteira exportada",
                    revisao=int(documento.get("revisao", 0)),
                    status=documento["status"],
                )
            importados.append(str(documento["codigo"]))
            ids_importados.append(str(documento["id"]))
    if espelhar:
        for projeto_id in ids_importados:
            _espelhar_projeto(
                projeto_id, "Restaurado de uma carteira exportada", caminho_banco=caminho_banco
            )
    return {"importados": importados, "ignorados": ignorados}


def restaurar_projetos_do_espelho(*, caminho_banco: str | Path | None = None) -> dict[str, Any]:
    """Traz do espelho remoto os projetos que este banco ainda não tem.

    É o que devolve o trabalho depois de um reinício do servidor que apagou
    o disco. Só entra o que falta (pelo ``id``): nunca sobrescreve um projeto
    que já está no banco, e um arquivo ilegível no espelho não impede os
    demais — ele aparece em ``falhas``. Sem espelho configurado não faz nada.
    Erros de rede ou de acesso (:class:`core.espelho_remoto.EspelhoErro`)
    sobem para quem chamou decidir como avisar.

    Devolve ``{"importados": [códigos], "falhas": {arquivo: motivo}}``.
    """
    resultado: dict[str, Any] = {"importados": [], "falhas": {}}
    if espelho_remoto.obter_espelho() is None:
        return resultado
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        locais = {linha["id"] for linha in conexao.execute("SELECT id FROM projects")}
    conteudos, falhas = espelho_remoto.baixar(
        PASTA_ESPELHO_PROJETOS, ignorar={f"{projeto_id}.json" for projeto_id in locais}
    )
    resultado["falhas"] = dict(falhas)
    for nome, conteudo in sorted(conteudos.items()):
        try:
            item = _ler_pacote(conteudo)
            carteira = {
                "formato": FORMATO_CARTEIRA,
                "versao": VERSAO_ESQUEMA,
                "projetos": [item],
            }
            resposta = importar_carteira(
                json.dumps(carteira, ensure_ascii=False),
                caminho_banco=caminho_banco,
                registrar_evento=False,
                espelhar=False,
            )
        except (ProjetoPersistenciaErro, sqlite3.Error, ValueError) as erro:
            resultado["falhas"][nome] = str(erro)
            continue
        resultado["importados"].extend(resposta["importados"])
    return resultado


def enviar_projetos_ao_espelho(*, caminho_banco: str | Path | None = None) -> dict[str, int]:
    """Copia todos os projetos do banco para o espelho remoto (inclusive os arquivados).

    Para quem ligou o espelho depois de já ter projetos no disco, ou quer
    garantir que nada ficou para trás. Devolve a quantidade de projetos e
    quantos envios ficaram pendentes.
    """
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        ids = [linha["id"] for linha in conexao.execute("SELECT id FROM projects ORDER BY name")]
    for projeto_id in ids:
        _espelhar_projeto(projeto_id, "Envio completo", caminho_banco=caminho_banco)
    return {"projetos": len(ids), "pendentes": espelho_remoto.situacao().pendentes}
