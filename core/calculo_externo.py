"""Capítulos de cálculo informados pelo responsável, sem executar verificações."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.technical_records import normalizar_registro_tecnico

ORIGEM_EXTERNA = "manual_externo"
MODELOS = {
    "Personalizado": ((), ()),
    "Ligação estrutural": (
        ("Solicitação", "Geometria", "Material"),
        ("Resistência", "Aproveitamento"),
    ),
    "Deslocamentos e vibrações": (
        ("Solicitação", "Geometria"),
        ("Deslocamento ou frequência", "Limite"),
    ),
    "Base e fundação": (
        ("Reação de apoio", "Geometria", "Material"),
        ("Solicitação", "Resistência"),
    ),
    "Elemento estrutural": (
        ("Solicitação", "Geometria", "Material"),
        ("Resistência", "Aproveitamento"),
    ),
}
ESTADOS = ("A preencher", "Informado")
RESULTADOS = ("Pendente", "Atende", "Não atende", "Inconclusivo", "Atenção")


def eh_externo(registro: Mapping[str, Any]) -> bool:
    return registro.get("origem_calculo") == ORIGEM_EXTERNA


def linhas_do_modelo(modelo: str, tipo: str) -> list[dict[str, str]]:
    entradas, resultados = MODELOS.get(modelo, MODELOS["Personalizado"])
    nomes = entradas if tipo == "entradas" else resultados
    return [{"grandeza": n, "valor": "", "unidade": "", "fonte": ""} for n in nomes]


def _linhas(valor: Any) -> list[dict[str, str]]:
    if not isinstance(valor, Sequence) or isinstance(valor, (str, bytes)):
        return []

    def texto(valor: Any) -> str:
        return "" if valor is None else str(valor).strip()

    return [
        {chave: texto(item.get(chave)) for chave in ("grandeza", "valor", "unidade", "fonte")}
        for item in valor
        if isinstance(item, Mapping)
        and any(texto(item.get(chave)) for chave in ("grandeza", "valor", "unidade", "fonte"))
    ]


def salvar_capitulo(
    projeto: Mapping[str, Any],
    *,
    campos: Mapping[str, Any],
    registro_id: str | None = None,
    duplicar: bool = False,
) -> tuple[dict[str, Any], str]:
    """Adiciona ou edita um capítulo; não modifica nem calcula seus valores."""
    documento = deepcopy(dict(projeto))
    registros = documento.setdefault("registros_tecnicos", [])
    indice = next((i for i, item in enumerate(registros) if item.get("id") == registro_id), None)
    if registro_id and indice is None:
        raise ValueError("Cálculo externo não encontrado.")
    antigo = deepcopy(registros[indice]) if indice is not None else {}
    if antigo and (not eh_externo(antigo) or antigo.get("status") == "Superado"):
        raise ValueError("Este registro não pode ser editado como cálculo externo vigente.")
    titulo = str(campos.get("titulo") or "").strip()
    if not titulo:
        raise ValueError("Informe o título do cálculo.")
    estado = campos.get("preenchimento") if campos.get("preenchimento") in ESTADOS else ESTADOS[0]
    resultado = (
        campos.get("resultado_tecnico")
        if campos.get("resultado_tecnico") in RESULTADOS
        else RESULTADOS[0]
    )
    linhas_resultado = _linhas(campos.get("resultados"))
    if duplicar:
        estado, resultado = "A preencher", "Pendente"
        linhas_resultado = [{**linha, "valor": ""} for linha in linhas_resultado]
    if (
        estado == "Informado"
        and resultado != "Pendente"
        and not any(linha["valor"] for linha in linhas_resultado)
    ):
        raise ValueError(
            "Informe ao menos um valor de resultado antes de declarar um resultado técnico."
        )
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    if not antigo or duplicar:
        antigo.pop("hash_calculo", None)
        antigo["id"] = str(uuid4())
        antigo["criado_em"] = agora
    antigo.update(
        {
            "origem_calculo": ORIGEM_EXTERNA,
            "preenchimento": estado,
            "resultado_tecnico": resultado,
            "modelo_externo": str(campos.get("modelo") or "Personalizado"),
            "modulo": "Cálculo manual ou externo",
            "modulo_id": "calculo_externo",
            "titulo": titulo,
            "peca": str(campos.get("peca") or "").strip(),
            "componentes_ids": [str(campos["componente_id"])]
            if campos.get("componente_id")
            else [],
            "status": resultado if estado == "Informado" else "Pendente",
            "resumo": str(campos.get("resumo") or "").strip(),
            "metodo": str(campos.get("metodo") or "").strip(),
            "conclusao": "" if duplicar else str(campos.get("conclusao") or "").strip(),
            "responsavel": str(campos.get("responsavel") or "").strip(),
            "documento_externo": str(campos.get("documento") or "").strip(),
            "premissas": [
                s.strip() for s in str(campos.get("premissas") or "").splitlines() if s.strip()
            ],
            "equacoes": [
                s.strip() for s in str(campos.get("equacoes") or "").splitlines() if s.strip()
            ],
            "referencias": [
                s.strip() for s in str(campos.get("referencias") or "").splitlines() if s.strip()
            ],
            "entradas": {"grandezas": _linhas(campos.get("entradas"))},
            "resultados": {"grandezas": linhas_resultado},
            "atualizado_em": agora,
        }
    )
    capitulo = normalizar_registro_tecnico(antigo)
    if indice is not None and not duplicar:
        registros[indice] = capitulo
    else:
        registros.append(capitulo)
    return documento, capitulo["id"]
