"""Backups do banco de projetos industriais.

Cópia íntegra e compactada do arquivo SQLite (``VACUUM INTO``), num arquivo
novo na pasta ``backups/`` ao lado do banco — ou num destino explícito.
Nunca sobrescreve: um destino que já existe é erro, não substituição.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.project_store import caminho_banco_atual, inicializar_banco
from core.projeto_documento import ProjetoPersistenciaErro


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
