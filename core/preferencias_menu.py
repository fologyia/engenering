"""Páginas fixadas e recentes do menu, num arquivo ao lado do banco de projetos.

Preferência de tela: se o arquivo não puder ser lido ou gravado, o menu segue sem ela. Sem Streamlit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.project_store import caminho_banco_atual

_NOME = "preferencias_menu.json"
_LIMITE_RECENTES = 12


def _arquivo() -> Path:
    return caminho_banco_atual().parent / _NOME


def _ler() -> dict[str, Any]:
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(dados: dict[str, Any]) -> None:
    try:
        _arquivo().write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _lista(chave: str) -> list[str]:
    valor = _ler().get(chave)
    return [str(item) for item in valor] if isinstance(valor, list) else []


def fixados() -> list[str]:
    return _lista("fixados")


def recentes() -> list[str]:
    return _lista("recentes")


def alternar_fixado(pagina: str) -> None:
    dados = _ler()
    lista = [str(item) for item in dados.get("fixados") or []]
    dados["fixados"] = [p for p in lista if p != pagina] if pagina in lista else [*lista, pagina]
    _gravar(dados)


def anotar_recente(pagina: str) -> None:
    dados = _ler()
    lista = [str(item) for item in dados.get("recentes") or [] if item != pagina]
    dados["recentes"] = [pagina, *lista][:_LIMITE_RECENTES]
    _gravar(dados)
