"""Envelope versionado para registros produzidos pelos módulos técnicos."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any
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


SEPARADOR_PECA = " — "
STATUS_SUPERADO = "Superado"


def registro_superado(registro: Mapping[str, Any]) -> bool:
    """Registro substituído por outro: fica no histórico, sai das cobranças."""
    return str(registro.get("status") or "").strip().casefold() == STATUS_SUPERADO.casefold()


def identificar_peca_registro(
    registro: Mapping[str, Any],
    *,
    peca: str = "",
    componentes_ids: Sequence[Any] = (),
) -> dict[str, Any]:
    """Amarra um registro à peça que ele verifica.

    Os módulos geram o título a partir do modelo e da seção ("Flambagem de
    coluna — W 200 x 26,6"), o que não distingue duas colunas iguais do mesmo
    mezanino. A identificação da peça entra na frente do título e o vínculo
    com o componente cadastrado (``componentes_ids``) permite ao memorial
    agrupar os cálculos por peça, em vez de listá-los soltos.
    """
    item = deepcopy(dict(registro))
    nome = str(peca or "").strip()
    if nome:
        item["peca"] = nome
        titulo = str(item.get("titulo") or "").strip()
        if not titulo.startswith(f"{nome}{SEPARADOR_PECA}"):
            item["titulo"] = f"{nome}{SEPARADOR_PECA}{titulo}" if titulo else nome
    ids = [str(valor) for valor in _lista(componentes_ids) if str(valor).strip()]
    if ids:
        existentes = [str(valor) for valor in _lista(item.get("componentes_ids"))]
        item["componentes_ids"] = existentes + [valor for valor in ids if valor not in existentes]
    return item


def agrupar_registros_por_componente(
    registros: Sequence[Mapping[str, Any]],
    componentes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Distribui os registros pelos componentes do escopo físico.

    Retorna grupos na ordem em que os componentes foram cadastrados, cada um
    com ``componente`` (ou ``None`` para o grupo "sem vínculo"), ``rotulo``
    e a lista de ``registros``. Um registro ligado a mais de um componente
    aparece em cada um deles; grupos vazios são omitidos. Os registros sem
    vínculo ficam por último, para que o memorial deixe claro o que ainda
    não foi amarrado a uma peça.
    """
    por_id = {
        str(item.get("id")): item
        for item in componentes
        if isinstance(item, Mapping) and str(item.get("id") or "").strip()
    }
    grupos: dict[str | None, list[Mapping[str, Any]]] = {chave: [] for chave in por_id}
    grupos[None] = []
    for registro in registros:
        vinculados = [
            valor for valor in _lista(registro.get("componentes_ids")) if str(valor) in por_id
        ]
        if not vinculados:
            grupos[None].append(registro)
            continue
        for valor in vinculados:
            grupos[str(valor)].append(registro)
    resultado: list[dict[str, Any]] = []
    for chave, itens in grupos.items():
        if not itens:
            continue
        componente = por_id.get(chave) if chave is not None else None
        resultado.append(
            {
                "componente": componente,
                "rotulo": rotulo_componente(componente),
                "registros": list(itens),
            }
        )
    return resultado


def rotulo_componente(componente: Mapping[str, Any] | None) -> str:
    if componente is None:
        return "Registros sem peça vinculada"
    tag = str(componente.get("tag") or "").strip()
    descricao = str(componente.get("descricao") or "").strip()
    if tag and descricao:
        return f"{tag} · {descricao}"
    return tag or descricao or "Componente sem identificação"


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
    item["peca"] = str(item.get("peca") or "").strip()
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

