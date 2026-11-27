"""Sugestões editáveis para o memorial, somente com dados registrados no projeto."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


def _texto(valor: Any) -> str:
    return str(valor).strip() if valor is not None else ""


def sugerir_contexto(
    projeto: Mapping[str, Any], registros: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    """Monta propostas, não valida cálculos nem supõe combinações processadas.

    O consumidor apresenta estas sugestões antes de aplicá-las e conserva textos já editados.
    """
    sugestoes: dict[str, str] = {}
    descricao = _texto(projeto.get("descricao"))
    if descricao:
        sugestoes["sistema"] = f"Descrição cadastrada para o projeto: {descricao}"
    base = projeto.get("base_projeto")
    if not isinstance(base, Mapping):
        base = {}
    cargas = _texto(base.get("base_carregamentos"))
    if cargas:
        sugestoes["acoes"] = f"Base dos carregamentos cadastrada no projeto: {cargas}"
    limitacoes = _texto(base.get("limitacoes"))
    if limitacoes:
        sugestoes["recomendacoes"] = f"Limitações e exclusões cadastradas: {limitacoes}"
    metodos = [
        f"{_texto(item.get('titulo')) or 'Cálculo'}: {_texto(item.get('metodo'))}"
        for item in registros
        if _texto(item.get("metodo"))
    ]
    if metodos:
        sugestoes["modelo"] = "Métodos informados nos registros selecionados: " + "; ".join(metodos)
    if registros:
        situacoes = Counter(_texto(item.get("status")) or "não informada" for item in registros)
        resumo = "; ".join(
            f"{quantidade} com situação {nome}" for nome, quantidade in situacoes.items()
        )
        sugestoes["conclusao_geral"] = (
            f"Foram selecionados {len(registros)} registro(s): {resumo}. "
            "A conclusão técnica e as recomendações devem considerar o escopo e as premissas registrados."
        )
    return sugestoes
