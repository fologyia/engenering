"""Espelhamento de um projeto para o repositório remoto configurado.

O espelho remoto (``core.espelho_remoto``) guarda um arquivo por projeto
com o documento, as fotografias de revisão e a linha do tempo — o mesmo
pacote que a carteira exportada carrega. A cópia roda depois que a gravação
local foi confirmada e **nunca levanta**: um GitHub fora do ar não pode
desfazer nem impedir o salvamento no disco.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core import espelho_remoto
from core.project_revisions import _pacote_projeto
from core.project_store import (
    FORMATO_ESPELHO,
    PASTA_ESPELHO_PROJETOS,
    VERSAO_ESQUEMA,
    _conectar,
)
from core.projeto_documento import ProjetoPersistenciaErro, _agora


def _mensagem_de_commit(codigo: Any, motivo: str) -> str:
    texto = " ".join(f"Projeto {codigo}: {motivo}".split())
    return texto[:120]


def _espelhar_projeto(
    projeto_id: str, motivo: str, *, caminho_banco: str | Path | None = None
) -> None:
    """Copia o projeto para o espelho remoto, se houver um configurado.

    Roda depois que a gravação local foi confirmada e **nunca levanta**: um
    GitHub fora do ar não pode desfazer nem impedir o salvamento no disco. O
    erro fica na situação do espelho (:func:`core.espelho_remoto.situacao`),
    e o conteúdo, na fila de pendências.
    """
    if espelho_remoto.obter_espelho() is None:
        return
    try:
        with _conectar(caminho_banco) as conexao:
            linha = conexao.execute(
                "SELECT id, code, payload_json FROM projects WHERE id = ?", (str(projeto_id),)
            ).fetchone()
            if linha is None:
                return
            pacote = _pacote_projeto(conexao, linha["id"], linha["payload_json"])
    except (sqlite3.Error, OSError, ValueError, ProjetoPersistenciaErro) as erro:
        espelho_remoto.registrar_erro(f"Não foi possível preparar o projeto para o espelho: {erro}")
        return
    conteudo = json.dumps(
        {
            "formato": FORMATO_ESPELHO,
            "versao": VERSAO_ESQUEMA,
            "enviado_em": _agora(),
            **pacote,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    espelho_remoto.enviar(
        f"{PASTA_ESPELHO_PROJETOS}/{linha['id']}.json",
        conteudo,
        _mensagem_de_commit(linha["code"], motivo),
    )
