"""Exportação e importação de um projeto industrial em JSON.

O pacote individual (``FORMATO_EXPORTACAO``) leva o documento sem o
contador de gravações e, opcionalmente, o histórico de revisões e a linha
do tempo para leitura. A importação nunca sobrescreve: cria um projeto novo,
com id, código e nome renovados e os vínculos internos renumerados.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.project_crud import (
    _renumerar_itens_copia,
    definir_projeto_ativo,
    obter_projeto,
)
from core.project_espelho import _espelhar_projeto
from core.project_revisions import (
    EVENTO_CRIACAO,
    _registrar_evento,
    historico_eventos,
    historico_revisoes,
)
from core.project_store import FORMATO_EXPORTACAO, _conectar, inicializar_banco
from core.projeto_documento import (
    CAMPO_GRAVACAO,
    VERSAO_ESQUEMA,
    ProjetoPersistenciaErro,
    _agora,
    _ler_pacote,
    _payload,
    _sem_token,
    _validar_documento,
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
    _espelhar_projeto(copia["id"], "Importação de projeto", caminho_banco=caminho_banco)
    return deepcopy(copia)
