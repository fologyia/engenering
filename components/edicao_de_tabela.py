"""O que o ``st.data_editor`` guarda depois de uma edição, aplicado às linhas de antes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def com_edicoes(
    linhas: Sequence[Mapping[str, Any]], mudancas: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Aplica o que o st.data_editor guarda: linhas editadas, apagadas e acrescentadas."""
    novas = [dict(linha) for linha in linhas]
    for indice, campos in (mudancas.get("edited_rows") or {}).items():
        if 0 <= int(indice) < len(novas):
            novas[int(indice)].update(campos)
    apagadas = {int(i) for i in mudancas.get("deleted_rows") or ()}
    novas = [linha for i, linha in enumerate(novas) if i not in apagadas]
    novas.extend(dict(linha) for linha in mudancas.get("added_rows") or ())
    return novas
