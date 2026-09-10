"""Critérios técnicos centralizados do projeto industrial.

O módulo mantém uma estrutura pequena, versionada e independente da interface.
Os cálculos podem consultar os mesmos limites, unidades e condições de projeto,
enquanto o hash técnico permite detectar quando uma análise ficou defasada.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

SCHEMA_CRITERIOS = "mecanica-toolkit/criterios-projeto/v1"

UNIDADES_PROJETO = {
    "forca": ("N", "kN"),
    "momento": ("N·mm", "N·m", "kN·m"),
    "tensao": ("Pa", "kPa", "MPa"),
    "comprimento": ("mm", "cm", "m"),
    "pressao": ("kPa", "bar", "MPa"),
    "temperatura": ("°C", "°F"),
}


def criterios_padrao() -> dict[str, Any]:
    return {
        "schema_criterios": SCHEMA_CRITERIOS,
        "versao": "1.0",
        "unidades": {
            "forca": "kN",
            "momento": "kN·m",
            "tensao": "MPa",
            "comprimento": "mm",
            "pressao": "bar",
            "temperatura": "°C",
        },
        "seguranca": {
            "fator_seguranca_minimo": 1.5,
            "utilizacao_maxima": 1.0,
            "probabilidade_nao_atendimento_max_pct": 5.0,
        },
        "operacao": {
            "temperatura_projeto_C": None,
            "pressao_projeto_bar": None,
            "vida_util_anos": None,
            "regime": "",
        },
        "combinacoes": {
            "metodo": "Fatores explícitos definidos pelo projeto",
            "referencia": "",
            "observacoes": "",
            "maximos_independentes_simultaneos": False,
        },
        "normativo": {
            "norma_principal": "",
            "edicao": "",
            "criterio_aceitacao": "",
            "observacoes": "",
        },
        "responsavel": "",
        "atualizado_em": "",
    }


def _numero(
    valor: Any,
    padrao: float | None,
    *,
    minimo: float | None = None,
) -> float | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return padrao
    if isinstance(valor, str):
        valor = valor.strip().replace(" ", "").replace(",", ".")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if not math.isfinite(numero) or (minimo is not None and numero < minimo):
        return padrao
    return numero


def normalizar_criterios_projeto(valor: Mapping[str, Any] | None) -> dict[str, Any]:
    """Completa critérios ausentes e normaliza números sem mutar a origem."""
    padrao = criterios_padrao()
    origem = deepcopy(dict(valor or {}))
    resultado = deepcopy(padrao)
    resultado["schema_criterios"] = SCHEMA_CRITERIOS
    resultado["versao"] = str(origem.get("versao") or "1.0")

    for grupo in ("unidades", "seguranca", "operacao", "combinacoes", "normativo"):
        recebido = origem.get(grupo)
        if isinstance(recebido, Mapping):
            resultado[grupo].update(deepcopy(dict(recebido)))

    for grandeza, opcoes in UNIDADES_PROJETO.items():
        unidade = str(resultado["unidades"].get(grandeza) or padrao["unidades"][grandeza])
        resultado["unidades"][grandeza] = unidade if unidade in opcoes else padrao["unidades"][grandeza]

    seguranca = resultado["seguranca"]
    seguranca["fator_seguranca_minimo"] = _numero(
        seguranca.get("fator_seguranca_minimo"), 1.5, minimo=0.01
    )
    seguranca["utilizacao_maxima"] = _numero(
        seguranca.get("utilizacao_maxima"), 1.0, minimo=0.01
    )
    seguranca["probabilidade_nao_atendimento_max_pct"] = min(
        100.0,
        _numero(
            seguranca.get("probabilidade_nao_atendimento_max_pct"),
            5.0,
            minimo=0.0,
        )
        or 0.0,
    )

    operacao = resultado["operacao"]
    operacao["temperatura_projeto_C"] = _numero(
        operacao.get("temperatura_projeto_C"), None
    )
    operacao["pressao_projeto_bar"] = _numero(
        operacao.get("pressao_projeto_bar"), None, minimo=0.0
    )
    operacao["vida_util_anos"] = _numero(
        operacao.get("vida_util_anos"), None, minimo=0.0
    )
    operacao["regime"] = str(operacao.get("regime") or "").strip()

    combinacoes = resultado["combinacoes"]
    combinacoes["metodo"] = str(combinacoes.get("metodo") or "").strip()
    combinacoes["referencia"] = str(combinacoes.get("referencia") or "").strip()
    combinacoes["observacoes"] = str(combinacoes.get("observacoes") or "").strip()
    combinacoes["maximos_independentes_simultaneos"] = bool(
        combinacoes.get("maximos_independentes_simultaneos", False)
    )

    normativo = resultado["normativo"]
    for campo in ("norma_principal", "edicao", "criterio_aceitacao", "observacoes"):
        normativo[campo] = str(normativo.get(campo) or "").strip()

    resultado["responsavel"] = str(origem.get("responsavel") or "").strip()
    resultado["atualizado_em"] = str(origem.get("atualizado_em") or "").strip()
    return resultado


def conteudo_tecnico_criterios(valor: Mapping[str, Any] | None) -> dict[str, Any]:
    criterios = normalizar_criterios_projeto(valor)
    return {
        chave: criterios[chave]
        for chave in ("schema_criterios", "versao", "unidades", "seguranca", "operacao", "combinacoes", "normativo")
    }


def calcular_hash_criterios(valor: Mapping[str, Any] | None) -> str:
    serializado = json.dumps(
        conteudo_tecnico_criterios(valor),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def avaliar_criterios_projeto(valor: Mapping[str, Any] | None) -> dict[str, Any]:
    criterios = normalizar_criterios_projeto(valor)
    faltantes: list[str] = []
    alertas: list[str] = []
    if not criterios["normativo"]["norma_principal"]:
        faltantes.append("Norma, especificação ou procedimento principal")
    if not criterios["normativo"]["criterio_aceitacao"]:
        faltantes.append("Descrição do critério de aceitação")
    if not criterios["combinacoes"]["referencia"]:
        faltantes.append("Referência dos fatores de combinação")
    if criterios["operacao"]["temperatura_projeto_C"] is None:
        alertas.append("Temperatura de projeto não estruturada")
    if criterios["operacao"]["vida_util_anos"] is None:
        alertas.append("Vida útil de projeto não estruturada")
    if criterios["combinacoes"]["maximos_independentes_simultaneos"]:
        alertas.append("Máximos independentes foram autorizados como simultâneos")
    return {
        "completo": not faltantes,
        "faltantes": faltantes,
        "alertas": alertas,
        "hash": calcular_hash_criterios(criterios),
        "criterios": criterios,
    }


def resumo_criterios_projeto(valor: Mapping[str, Any] | None) -> str:
    criterios = normalizar_criterios_projeto(valor)
    seguranca = criterios["seguranca"]
    operacao = criterios["operacao"]
    partes = [
        f"n mínimo = {seguranca['fator_seguranca_minimo']:g}",
        f"utilização máxima = {seguranca['utilizacao_maxima']:g}",
        (
            "risco máximo de não atendimento = "
            f"{seguranca['probabilidade_nao_atendimento_max_pct']:g}%"
        ),
    ]
    if operacao["temperatura_projeto_C"] is not None:
        partes.append(f"temperatura de projeto = {operacao['temperatura_projeto_C']:g} °C")
    if operacao["pressao_projeto_bar"] is not None:
        partes.append(f"pressão de projeto = {operacao['pressao_projeto_bar']:g} bar")
    if operacao["vida_util_anos"] is not None:
        partes.append(f"vida útil = {operacao['vida_util_anos']:g} anos")
    return "; ".join(partes)
