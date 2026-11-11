"""Casos de carga no Montador: partida e regime, cheio e vazio, na mesma montagem.

Os valores do inspetor são o primeiro caso. Cada caso a mais muda só algumas letras (os esforços,
quase sempre); o que fica em branco vale o número do primeiro caso. Na conta, cada caso vira mais um
jogo de condições, com os números dele dentro (``core.montador.com_casos``), e a resposta sai do
pior de todos, como sai a condição que manda num caso só.

Aqui fica o que não é conta: o formato guardado na tela e no arquivo, e a resposta de cada caso.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import montador as mt

MAXIMO_DE_CASOS = 12
TAMANHO_DO_NOME = 60
CASO_BASE = "Caso 1"


def vazio() -> dict[str, Any]:
    return {"ligado": False, "base": CASO_BASE, "letras": [], "lista": []}


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


def normalizar(bruto: Any) -> dict[str, Any] | None:
    """O que veio da tela ou de um arquivo, conferido: nome curto, número de verdade, até 12 casos."""
    if not isinstance(bruto, Mapping):
        return None
    letras = [str(x) for x in bruto.get("letras") or () if isinstance(x, str)]
    lista = []
    for item in list(bruto.get("lista") or ())[:MAXIMO_DE_CASOS]:
        if not isinstance(item, Mapping):
            continue
        valores = {}
        brutos = item.get("valores")
        for chave, valor in brutos.items() if isinstance(brutos, Mapping) else ():
            numero = _numero(valor)
            if numero is not None:
                valores[str(chave)] = numero
        lista.append(
            {"nome": str(item.get("nome") or "").strip()[:TAMANHO_DO_NOME], "valores": valores}
        )
    return {
        "ligado": bool(bruto.get("ligado")),
        "base": (str(bruto.get("base") or "").strip() or CASO_BASE)[:TAMANHO_DO_NOME],
        "letras": list(dict.fromkeys(letras)),
        "lista": lista,
    }


def para_a_conta(
    bruto: Any,
) -> tuple[str, tuple[tuple[str, Mapping[str, float]], ...]]:
    """(nome do primeiro caso, os outros casos) para ``mt.com_casos``. Desligado: sem casos.

    Só as letras escolhidas entram: tirar uma letra da lista volta o caso ao número do primeiro.
    """
    casos = normalizar(bruto)
    if casos is None or not casos["ligado"]:
        return CASO_BASE, ()
    letras = set(casos["letras"])
    lista = tuple(
        (
            item["nome"] or f"Caso {i + 2}",
            {k: v for k, v in item["valores"].items() if k in letras},
        )
        for i, item in enumerate(casos["lista"])
    )
    return casos["base"], lista


def resposta_de_cada_caso(resposta: mt.Resposta) -> list[tuple[str, mt.Isolada | None]]:
    """Para cada caso, a condição que manda nele, pela mesma regra da resposta inteira."""
    conta = resposta.montagem
    if conta is None or not conta.casos:
        return []
    nomes = [conta.caso_base, *(nome for nome, _ in conta.casos)]
    saida: list[tuple[str, mt.Isolada | None]] = []
    for nome in nomes:
        do_caso = [i for i in resposta.isoladas if i.condicao.caso == nome and i.valor is not None]
        manda: mt.Isolada | None
        minimos = [i for i in do_caso if i.lado == mt.MINIMO]
        maximos = [i for i in do_caso if i.lado == mt.MAXIMO]
        iguais = [i for i in do_caso if i.lado == mt.IGUAL]
        if minimos:
            manda = max(minimos, key=lambda i: i.valor or 0.0)
        elif maximos:
            manda = min(maximos, key=lambda i: i.valor or 0.0)
        else:
            manda = iguais[0] if iguais else None
        saida.append((nome, manda))
    return saida
