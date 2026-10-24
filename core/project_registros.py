"""Inclusão de registros técnicos no projeto industrial.

Anexa ao documento o registro produzido por um módulo técnico
(``core.technical_records``) e grava: ``adicionar_registro_tecnico`` só
acrescenta; :func:`registrar_calculo_tecnico` também fotografa as fontes
que o cálculo consumiu e reavalia a atualidade dos demais cálculos do
projeto (``core.project_dependencies``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from core.project_crud import obter_projeto, salvar_projeto
from core.project_dependencies import (
    preparar_registro_dependencias,
    sincronizar_estados_dependencias,
)
from core.project_revisions import EVENTO_REGISTRO
from core.projeto_documento import (
    ProjetoPersistenciaErro,
    _json_seguro,
)
from core.technical_records import normalizar_registro_tecnico


def _motivo_registro(registro: Mapping[str, Any]) -> str:
    modulo = str(registro.get("modulo") or "Registro técnico").strip()
    titulo = str(registro.get("titulo") or "").strip()
    return (
        f"Registro técnico incluído: {modulo} · {titulo}"
        if titulo
        else f"Registro técnico incluído: {modulo}"
    )


def adicionar_registro_tecnico(
    projeto_id: str,
    registro: Mapping[str, Any],
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    item = _json_seguro(normalizar_registro_tecnico(registro))
    projeto["registros_tecnicos"].append(item)
    return salvar_projeto(
        projeto,
        motivo=_motivo_registro(item),
        tipo_evento=EVENTO_REGISTRO,
        caminho_banco=caminho_banco,
    )


def registrar_calculo_tecnico(
    projeto_id: str,
    registro: Mapping[str, Any],
    *,
    dependencias_chaves: Sequence[str] = (),
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    """Anexa um registro técnico fotografando as fontes que ele consumiu.

    Diferente de :func:`adicionar_registro_tecnico`, esta função também
    reavalia a atualidade de *todos* os cálculos do projeto após a inclusão,
    para que um material, caso de carga ou registro de origem alterado
    apareça como desatualizado assim que outro cálculo for salvo.
    """
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    item = preparar_registro_dependencias(
        projeto, registro, dependencias_chaves=dependencias_chaves
    )
    projeto["registros_tecnicos"] = [
        *projeto["registros_tecnicos"],
        _json_seguro(item),
    ]
    projeto = sincronizar_estados_dependencias(projeto)
    return salvar_projeto(
        projeto,
        motivo=_motivo_registro(item),
        tipo_evento=EVENTO_REGISTRO,
        caminho_banco=caminho_banco,
    )
