"""Documento do projeto industrial: fábrica, validação e serialização.

Tudo aqui é puro: nenhuma função deste módulo abre conexão com o banco.
A persistência (SQLite, conexão, migração e gravação) fica em
``core.project_store``; as operações que leem e gravam usam estas funções
para montar, conferir e serializar o documento que viaja no ``payload_json``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

VERSAO_ESQUEMA = 1
# Campo do documento que carrega o contador de gravações da linha. Não é
# gravado no payload nem nas fotografias de revisão: é metadado da linha,
# injetado na leitura e conferido na escrita.
CAMPO_GRAVACAO = "gravacao"


class ProjetoPersistenciaErro(RuntimeError):
    """Falha controlada de validacao ou persistencia."""


class ProjetoConflitoErro(ProjetoPersistenciaErro):
    """O projeto foi gravado por outra sessão depois que este documento foi lido."""


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_seguro(valor: Any) -> Any:
    """Normaliza estruturas para JSON sem aceitar objetos opacos."""
    try:
        return json.loads(json.dumps(valor, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as erro:
        raise ProjetoPersistenciaErro(
            f"O projeto contem um valor que nao pode ser salvo: {erro}"
        ) from erro


def novo_projeto_documento(
    nome: str,
    *,
    codigo: str = "",
    cliente: str = "",
    unidade_industrial: str = "",
    area: str = "",
    tag_equipamento: str = "",
    descricao: str = "",
    objetivo: str = "",
    tipo_projeto: str = "",
) -> dict[str, Any]:
    nome_limpo = str(nome).strip()
    if not nome_limpo:
        raise ProjetoPersistenciaErro("Informe o nome do projeto.")
    instante = _agora()
    identificador = str(uuid4())
    codigo_limpo = str(codigo).strip() or f"PRJ-{instante[:10].replace('-', '')}"
    return {
        "schema_version": VERSAO_ESQUEMA,
        "id": identificador,
        "nome": nome_limpo,
        "codigo": codigo_limpo,
        "status": "Em elaboração",
        "revisao": 0,
        "criado_em": instante,
        "atualizado_em": instante,
        "cliente": str(cliente).strip(),
        "unidade_industrial": str(unidade_industrial).strip(),
        "area": str(area).strip(),
        "tag_equipamento": str(tag_equipamento).strip(),
        "tipo_projeto": str(tipo_projeto).strip() or "Projeto industrial",
        "descricao": str(descricao).strip(),
        # O objetivo bloqueia a emissão do memorial, então precisa poder ser
        # informado já na criação — antes ele só aceitava ficar vazio, e todo
        # projeto nascia bloqueado.
        "objetivo": str(objetivo).strip(),
        "processo": "",
        "regime_operacao": "",
        "responsavel": "",
        "verificador": "",
        "aprovador": "",
        "base_projeto": {
            "referencias_desenho": "",
            "base_carregamentos": "",
            "condicoes_operacao": "",
            "criterio_aceitacao": "",
            "vida_requerida": "",
            "limitacoes": "",
        },
        "componentes": [],
        "materiais_projeto": [],
        "casos_carga": [],
        "combinacoes_carga": [],
        "normas": [],
        "registros_tecnicos": [],
        "checklist": [],
        "anexos": [],
        "configuracao_relatorio": {
            "perfil": "Memorial industrial completo",
            "incluir_resumo": True,
            "incluir_validacao": True,
            "incluir_apendice": True,
        },
    }


def _validar_documento(projeto: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(projeto, Mapping):
        raise ProjetoPersistenciaErro(
            "Arquivo de projeto invalido: o projeto nao e um objeto JSON."
        )
    documento = _json_seguro(dict(projeto))
    try:
        versao = int(documento.get("schema_version", 0))
    except (TypeError, ValueError):
        versao = -1
    if versao != VERSAO_ESQUEMA:
        raise ProjetoPersistenciaErro(
            f"Versao de projeto nao suportada: {documento.get('schema_version')}."
        )
    for campo in ("id", "nome", "codigo", "status"):
        if not str(documento.get(campo, "")).strip():
            raise ProjetoPersistenciaErro(f"Campo obrigatorio ausente: {campo}.")
    # Campos adicionados de forma compatível: projetos da versão 1 são
    # completados na leitura sem exigir uma migração destrutiva do SQLite.
    documento.setdefault("materiais_projeto", [])
    documento.setdefault("casos_carga", [])
    documento.setdefault("combinacoes_carga", [])
    documento.setdefault("configuracao_relatorio", {})
    for campo in (
        "componentes",
        "materiais_projeto",
        "casos_carga",
        "combinacoes_carga",
        "normas",
        "registros_tecnicos",
        "checklist",
        "anexos",
    ):
        if not isinstance(documento.get(campo, []), list):
            raise ProjetoPersistenciaErro(f"O campo '{campo}' deve ser uma lista.")
        if campo in documento:
            # Só objetos: um item estranho (número, texto) de um projeto antigo, editado à mão ou
            # corrompido derrubaria toda página que lê a lista.
            documento[campo] = [item for item in documento[campo] if isinstance(item, dict)]
    if not isinstance(documento.get("base_projeto", {}), dict):
        raise ProjetoPersistenciaErro("O campo 'base_projeto' deve ser um objeto.")
    if "registros_tecnicos" in documento:
        documento["registros_tecnicos"] = [
            _normalizar_tipos_do_registro(r) for r in documento["registros_tecnicos"]
        ]
    return documento


#: Campos do registro técnico por tipo (``core.technical_records.criar_registro_tecnico``).
_TEXTOS_DO_REGISTRO = (
    "id",
    "criado_em",
    "atualizado_em",
    "modulo",
    "modulo_id",
    "metodo_versao",
    "titulo",
    "status",
    "resumo",
    "metodo",
    "conclusao",
    "responsavel",
)
_OBJETOS_DO_REGISTRO = ("entradas", "resultados", "incertezas")
_LISTAS_DO_REGISTRO = (
    "premissas",
    "equacoes",
    "criterios",
    "alertas",
    "referencias",
    "casos_carga_ids",
    "componentes_ids",
    "materiais_ids",
)


def _normalizar_tipos_do_registro(registro: dict[str, Any]) -> dict[str, Any]:
    """Cada campo conhecido com o tipo certo; num registro íntegro não muda nada (nem o hash).

    Num registro corrompido o hash deixa de bater e a validação o marca — mas nenhuma página quebra
    ao lê-lo.
    """
    for campo in _TEXTOS_DO_REGISTRO:
        if campo in registro and not isinstance(registro[campo], str):
            registro[campo] = "" if registro[campo] is None else str(registro[campo])
    for campo in _OBJETOS_DO_REGISTRO:
        if campo in registro and not isinstance(registro[campo], dict):
            registro[campo] = {}
    for campo in _LISTAS_DO_REGISTRO:
        if campo in registro and not isinstance(registro[campo], list):
            registro[campo] = []
    # Campos que as páginas leem com colchetes: o registro íntegro sempre os tem.
    for campo, padrao in (("titulo", ""), ("status", "Pendente"), ("modulo", "")):
        registro.setdefault(campo, padrao)
    registro.setdefault("entradas", {})
    registro.setdefault("resultados", {})
    if not registro.get("id"):
        # Estável: o mesmo conteúdo dá o mesmo id a cada leitura.
        conteudo = json.dumps(registro, ensure_ascii=False, sort_keys=True, default=str)
        registro["id"] = "registro-" + hashlib.sha1(conteudo.encode("utf-8")).hexdigest()[:12]
    return registro


def _sem_token(documento: Mapping[str, Any]) -> dict[str, Any]:
    """Cópia do documento sem o contador de gravações."""
    return {chave: valor for chave, valor in documento.items() if chave != CAMPO_GRAVACAO}


def _payload(documento: Mapping[str, Any]) -> str:
    """Serializa o documento para a linha, sem o contador de gravações."""
    return json.dumps(_sem_token(documento), ensure_ascii=False, sort_keys=True)


def _documento_da_linha(linha: sqlite3.Row) -> dict[str, Any]:
    """Documento validado com o contador de gravações da linha injetado."""
    documento = _validar_documento(json.loads(linha["payload_json"]))
    documento[CAMPO_GRAVACAO] = int(linha["write_seq"])
    return documento


def _ler_pacote(conteudo: bytes | str) -> dict[str, Any]:
    try:
        texto = conteudo.decode("utf-8-sig") if isinstance(conteudo, bytes) else conteudo
        pacote = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ProjetoPersistenciaErro(f"Arquivo de projeto invalido: {erro}") from erro
    if not isinstance(pacote, dict):
        raise ProjetoPersistenciaErro("Arquivo de projeto invalido: esperava um objeto JSON.")
    return pacote


def criar_item(
    **campos: Any,
) -> dict[str, Any]:
    """Cria uma linha identificada para componentes, normas ou checklists."""
    return {"id": str(uuid4()), **_json_seguro(campos)}


def revisar_listas(
    projeto: Mapping[str, Any],
    *,
    componentes: Sequence[Mapping[str, Any]] | None = None,
    normas: Sequence[Mapping[str, Any]] | None = None,
    checklist: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    documento = deepcopy(dict(projeto))
    if componentes is not None:
        documento["componentes"] = [_json_seguro(dict(item)) for item in componentes]
    if normas is not None:
        documento["normas"] = [_json_seguro(dict(item)) for item in normas]
    if checklist is not None:
        documento["checklist"] = [_json_seguro(dict(item)) for item in checklist]
    return documento
