"""Administração dos registros técnicos já gravados no projeto.

Os módulos só sabiam *acrescentar* registros. Um cálculo refeito ficava ao
lado do antigo, os dois entravam no memorial e a validação cobrava os dois.
Aqui ficam as operações sobre a lista já gravada: marcar um registro como
superado por outro, remover um registro e resumir cada um numa linha de
tabela (peça, menor fator, utilização, atualidade das fontes) — tudo em
funções puras sobre o documento, para a página só decidir quando salvar.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any

from core.project_dependencies import (
    STATUS_ATUAL,
    STATUS_SEM_DEPENDENCIAS,
    sincronizar_estados_dependencias,
)
from core.technical_records import (
    STATUS_SUPERADO,
    normalizar_registro_tecnico,
    registro_superado,
    rotulo_componente,
)

__all__ = [
    "STATUS_SUPERADO",
    "dependentes_do_registro",
    "menor_fator_registro",
    "registro_superado",
    "remover_registro",
    "resumir_registros",
    "superar_registro",
    "utilizacao_registro",
]

# Chaves em que os módulos gravam fatores de segurança e utilização. A lista
# repete a da validação de propósito: aqui é leitura para tabela, lá é
# critério; podem divergir sem quebrar uma à outra.
_CHAVES_FATOR = (
    "fator_seguranca",
    "fator_seguranca_escoamento",
    "fator_seguranca_ruptura",
    "fator_ruptura",
    "fator_seguranca_minimo_calculado",
    "menor_fator",
    "fator_governante",
    "n_min",
)
_CHAVES_UTILIZACAO = ("utilizacao", "utilizacao_maxima", "indice_utilizacao")


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _numero(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _localizar(
    projeto: Mapping[str, Any], registro_id: str
) -> tuple[int, Mapping[str, Any]]:
    alvo = _texto(registro_id)
    for indice, registro in enumerate(projeto.get("registros_tecnicos", [])):
        if isinstance(registro, Mapping) and _texto(registro.get("id")) == alvo:
            return indice, registro
    raise ValueError("Registro técnico não encontrado no projeto.")


def superar_registro(
    projeto: Mapping[str, Any],
    registro_id: str,
    *,
    motivo: str = "",
    substituto_id: str | None = None,
) -> dict[str, Any]:
    """Marca o registro como superado, sem apagá-lo.

    O conteúdo técnico fica intacto; mudam só o status e os campos
    administrativos ``superado_em``, ``superado_motivo`` e ``superado_por``.
    Registros superados saem da seleção padrão do memorial e deixam de gerar
    bloqueios na validação, mas continuam no histórico. Os cálculos que o
    usaram como origem passam a "Desatualizado" na sincronização — a fonte
    deles foi substituída, e é isso que a validação deve mostrar.
    """
    documento = deepcopy(dict(projeto))
    indice, registro = _localizar(documento, registro_id)
    substituto = _texto(substituto_id)
    if substituto:
        if substituto == _texto(registro_id):
            raise ValueError("Um registro não pode ser superado por ele mesmo.")
        _localizar(documento, substituto)
    item = deepcopy(dict(registro))
    item["status_anterior"] = _texto(item.get("status")) or "Pendente"
    item["status"] = STATUS_SUPERADO
    item["superado_em"] = _agora()
    item["superado_motivo"] = _texto(motivo)
    item["superado_por"] = substituto
    item["atualizado_em"] = item["superado_em"]
    # O status faz parte da assinatura: recalcular mantém a Central de
    # Validação sem acusar divergência num registro que ninguém adulterou.
    item.pop("hash_calculo", None)
    documento["registros_tecnicos"][indice] = normalizar_registro_tecnico(item)
    return sincronizar_estados_dependencias(documento)


def remover_registro(projeto: Mapping[str, Any], registro_id: str) -> dict[str, Any]:
    """Retira o registro da lista e reavalia quem dependia dele.

    Os cálculos que apontavam para o registro removido passam a
    "Referência ausente" na sincronização — a validação mostra isso como
    bloqueio, que é o comportamento certo: a origem de um resultado sumiu.
    """
    documento = deepcopy(dict(projeto))
    indice, _ = _localizar(documento, registro_id)
    del documento["registros_tecnicos"][indice]
    configuracao = documento.get("configuracao_relatorio")
    if isinstance(configuracao, Mapping):
        configuracao = dict(configuracao)
        for chave in ("registros_incluidos", "ordem_registros"):
            valores = configuracao.get(chave)
            if isinstance(valores, Sequence) and not isinstance(valores, (str, bytes)):
                configuracao[chave] = [
                    valor for valor in valores if _texto(valor) != _texto(registro_id)
                ]
        documento["configuracao_relatorio"] = configuracao
    return sincronizar_estados_dependencias(documento)


def menor_fator_registro(registro: Mapping[str, Any]) -> tuple[str, float] | None:
    resultados = registro.get("resultados")
    if not isinstance(resultados, Mapping):
        return None
    fatores = [
        (chave, numero)
        for chave in _CHAVES_FATOR
        if (numero := _numero(resultados.get(chave))) is not None
    ]
    if not fatores:
        return None
    return min(fatores, key=lambda par: par[1])


def utilizacao_registro(registro: Mapping[str, Any]) -> float | None:
    resultados = registro.get("resultados")
    if not isinstance(resultados, Mapping):
        return None
    for chave in _CHAVES_UTILIZACAO:
        numero = _numero(resultados.get(chave))
        if numero is not None:
            return numero
    return None


def dependentes_do_registro(
    projeto: Mapping[str, Any], registro_id: str
) -> list[Mapping[str, Any]]:
    """Registros que declararam este como origem (Mohr → Estática etc.)."""
    alvo = _texto(registro_id)
    dependentes = []
    for registro in projeto.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping):
            continue
        ids = registro.get("dependencias_ids", [])
        if isinstance(ids, Sequence) and alvo in {_texto(valor) for valor in ids}:
            dependentes.append(registro)
    return dependentes


def resumir_registros(projeto: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Uma linha por registro, com o que uma tabela de gestão precisa ver.

    Sincroniza os estados de dependência antes de resumir, para a coluna
    "Atualidade" refletir o projeto de agora e não o último salvamento.
    """
    sincronizado = sincronizar_estados_dependencias(projeto)
    componentes = {
        _texto(item.get("id")): item
        for item in sincronizado.get("componentes", [])
        if isinstance(item, Mapping) and _texto(item.get("id"))
    }
    linhas: list[dict[str, Any]] = []
    for registro in sincronizado.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping):
            continue
        estado = registro.get("estado_dependencias")
        estado = estado if isinstance(estado, Mapping) else {}
        status_dependencias = _texto(estado.get("status")) or STATUS_SEM_DEPENDENCIAS
        pecas = [
            rotulo_componente(componentes[_texto(valor)])
            for valor in registro.get("componentes_ids", []) or []
            if _texto(valor) in componentes
        ]
        fator = menor_fator_registro(registro)
        linhas.append(
            {
                "id": _texto(registro.get("id")),
                "peca": _texto(registro.get("peca")) or ", ".join(pecas) or "",
                "modulo": _texto(registro.get("modulo")) or "Registro técnico",
                "titulo": _texto(registro.get("titulo")) or "Registro",
                "status": _texto(registro.get("status")) or "Pendente",
                "superado": registro_superado(registro),
                "atualidade": status_dependencias,
                "atualizado": status_dependencias in {STATUS_ATUAL, STATUS_SEM_DEPENDENCIAS},
                "motivos": [str(m) for m in estado.get("motivos", []) or []],
                "menor_fator": fator[1] if fator else None,
                "criterio_fator": fator[0] if fator else "",
                "utilizacao": utilizacao_registro(registro),
                "criado_em": _texto(registro.get("criado_em")),
                "dependentes": len(dependentes_do_registro(sincronizado, _texto(registro.get("id")))),
            }
        )
    return linhas
