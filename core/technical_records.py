"""Envelope versionado para registros produzidos pelos módulos técnicos."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import uuid4

from core.technical_modules import resolver_modulo


SCHEMA_REGISTRO = "mecanica-toolkit/registro-tecnico/v2"


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _lista(valor: Any) -> list[Any]:
    if valor is None:
        return []
    if isinstance(valor, Sequence) and not isinstance(valor, (str, bytes)):
        return list(valor)
    return [valor]


def calcular_hash_registro(registro: Mapping[str, Any]) -> str:
    """Assina o conteúdo técnico, excluindo campos administrativos mutáveis."""
    campos = {
        chave: registro.get(chave)
        for chave in (
            "schema_registro",
            "modulo_id",
            "modulo_versao",
            "metodo_versao",
            "titulo",
            "status",
            "entradas",
            "resultados",
            "premissas",
            "metodo",
            "equacoes",
            "criterios",
            "incertezas",
            "alertas",
            "referencias",
            "conclusao",
            "casos_carga_ids",
            "componentes_ids",
            "materiais_ids",
        )
    }
    serializado = json.dumps(
        campos,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def normalizar_registro_tecnico(registro: Mapping[str, Any]) -> dict[str, Any]:
    """Completa registros novos ou legados sem descartar campos específicos."""
    item = deepcopy(dict(registro))
    modulo = resolver_modulo(item.get("modulo_id") or item.get("modulo"))
    instante = str(item.get("criado_em") or _agora())
    item.setdefault("id", str(uuid4()))
    item.setdefault("criado_em", instante)
    item.setdefault("atualizado_em", instante)
    item.setdefault("modulo", modulo.titulo if modulo else "Registro manual")
    item.setdefault("modulo_id", modulo.id if modulo else "personalizado")
    item.setdefault("modulo_versao", modulo.versao if modulo else "1.0")
    item.setdefault("metodo_versao", item.get("modulo_versao", "1.0"))
    item.setdefault("schema_registro", modulo.schema_registro if modulo else SCHEMA_REGISTRO)
    item.setdefault("titulo", "Verificação técnica")
    item.setdefault("status", "Pendente")
    item.setdefault("resumo", "")
    item["entradas"] = dict(item.get("entradas") or {})
    item["resultados"] = dict(item.get("resultados") or {})
    for campo in ("premissas", "equacoes", "criterios", "alertas", "referencias"):
        item[campo] = _lista(item.get(campo))
    item["incertezas"] = dict(item.get("incertezas") or {})
    item.setdefault("metodo", "")
    item.setdefault("conclusao", "")
    item.setdefault("responsavel", "")
    for campo in ("casos_carga_ids", "componentes_ids", "materiais_ids"):
        item[campo] = [str(valor) for valor in _lista(item.get(campo)) if str(valor).strip()]
    item["hash_calculo"] = calcular_hash_registro(item)
    return item


def criar_registro_tecnico(
    *,
    modulo: str,
    titulo: str,
    status: str,
    resumo: str,
    entradas: Mapping[str, Any],
    resultados: Mapping[str, Any],
    modulo_id: str | None = None,
    metodo_versao: str | None = None,
    premissas: Sequence[Any] = (),
    metodo: str = "",
    equacoes: Sequence[Any] = (),
    criterios: Sequence[Any] = (),
    incertezas: Mapping[str, Any] | None = None,
    alertas: Sequence[Any] = (),
    referencias: Sequence[Any] = (),
    conclusao: str = "",
    responsavel: str = "",
    casos_carga_ids: Sequence[Any] = (),
    componentes_ids: Sequence[Any] = (),
    materiais_ids: Sequence[Any] = (),
) -> dict[str, Any]:
    instante = _agora()
    bruto = {
        "id": str(uuid4()),
        "criado_em": instante,
        "atualizado_em": instante,
        "modulo": str(modulo).strip(),
        "modulo_id": str(modulo_id or "").strip(),
        "metodo_versao": str(metodo_versao or "").strip(),
        "titulo": str(titulo).strip(),
        "status": str(status).strip() or "Pendente",
        "resumo": str(resumo).strip(),
        "entradas": dict(entradas),
        "resultados": dict(resultados),
        "premissas": list(premissas),
        "metodo": str(metodo).strip(),
        "equacoes": list(equacoes),
        "criterios": list(criterios),
        "incertezas": dict(incertezas or {}),
        "alertas": list(alertas),
        "referencias": list(referencias),
        "conclusao": str(conclusao).strip(),
        "responsavel": str(responsavel).strip(),
        "casos_carga_ids": list(casos_carga_ids),
        "componentes_ids": list(componentes_ids),
        "materiais_ids": list(materiais_ids),
    }
    # Campos vazios não devem impedir a resolução pelo título legado.
    if not bruto["modulo_id"]:
        bruto.pop("modulo_id")
    if not bruto["metodo_versao"]:
        bruto.pop("metodo_versao")
    return normalizar_registro_tecnico(bruto)


def avaliar_contrato_registro(registro: Mapping[str, Any]) -> dict[str, Any]:
    """Avalia estrutura e integridade da assinatura sem julgar engenharia."""
    obrigatorios = {
        "Esquema": registro.get("schema_registro"),
        "Identidade do módulo": registro.get("modulo_id"),
        "Versão do módulo": registro.get("modulo_versao"),
        "Entradas": registro.get("entradas"),
        "Resultados": registro.get("resultados"),
        "Método": registro.get("metodo") or registro.get("resumo"),
        "Conclusão": registro.get("conclusao"),
    }
    faltantes = [rotulo for rotulo, valor in obrigatorios.items() if not valor]
    hash_salvo = str(registro.get("hash_calculo") or "")
    hash_atual = calcular_hash_registro(registro) if hash_salvo else ""
    assinatura_valida = bool(hash_salvo) and hash_salvo == hash_atual
    return {
        "valido": not faltantes and assinatura_valida,
        "faltantes": faltantes,
        "assinatura_presente": bool(hash_salvo),
        "assinatura_valida": assinatura_valida,
        "modulo_conhecido": resolver_modulo(
            registro.get("modulo_id") or registro.get("modulo")
        )
        is not None,
    }

