"""Persistencia local de projetos industriais e registros tecnicos.

O SQLite e a fonte permanente. O Streamlit usa apenas o identificador do
projeto ativo e recarrega o documento sempre que precisa mostrar ou editar.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.project_dependencies import (
    preparar_registro_dependencias,
    sincronizar_estados_dependencias,
)
from core.technical_records import normalizar_registro_tecnico

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
BANCO_PADRAO = RAIZ_PROJETO / "data" / "projetos_industriais.sqlite3"
FORMATO_EXPORTACAO = "mecanica-toolkit-project"
VERSAO_ESQUEMA = 1


class ProjetoPersistenciaErro(RuntimeError):
    """Falha controlada de validacao ou persistencia."""


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


def _banco(caminho_banco: str | Path | None) -> str | Path:
    """Resolve o banco na hora da chamada, e não na definição da função.

    Com ``= BANCO_PADRAO`` no argumento, o valor ficava congelado no momento
    em que o módulo era importado: apontar ``BANCO_PADRAO`` para outro
    arquivo — como um teste faria para se isolar — não tinha efeito nenhum, e
    a escrita ia parar no banco real sem nenhum aviso.
    """
    return BANCO_PADRAO if caminho_banco is None else caminho_banco


def _conectar(caminho_banco: str | Path | None = None) -> sqlite3.Connection:
    # Único ponto que materializa o caminho: todas as demais funções apenas
    # repassam o parâmetro, então resolver aqui cobre o módulo inteiro.
    caminho = Path(_banco(caminho_banco)).expanduser().resolve()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, timeout=15.0)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA busy_timeout = 15000")
    return conexao


def inicializar_banco(caminho_banco: str | Path | None = None) -> None:
    with _conectar(caminho_banco) as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                status TEXT NOT NULL,
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_projects_status_updated
                ON projects(status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS project_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, revision)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


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
        "tipo_projeto": "Projeto industrial",
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
    documento = _json_seguro(dict(projeto))
    if int(documento.get("schema_version", 0)) != VERSAO_ESQUEMA:
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
    if not isinstance(documento.get("base_projeto", {}), dict):
        raise ProjetoPersistenciaErro("O campo 'base_projeto' deve ser um objeto.")
    return documento


def criar_projeto(
    nome: str,
    *,
    caminho_banco: str | Path | None = None,
    ativar: bool = True,
    **campos: Any,
) -> dict[str, Any]:
    inicializar_banco(caminho_banco)
    projeto = novo_projeto_documento(nome, **campos)
    payload = json.dumps(projeto, ensure_ascii=False, sort_keys=True)
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                projeto["id"],
                projeto["nome"],
                projeto["codigo"],
                projeto["status"],
                projeto["revisao"],
                projeto["criado_em"],
                projeto["atualizado_em"],
                payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (projeto["id"], 0, "Criação do projeto", projeto["criado_em"], payload),
        )
        if ativar:
            conexao.execute(
                """
                INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (projeto["id"],),
            )
    return deepcopy(projeto)


def listar_projetos(
    *,
    incluir_arquivados: bool = False,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    inicializar_banco(caminho_banco)
    sql = (
        "SELECT id, name, code, status, revision, created_at, updated_at "
        "FROM projects"
    )
    parametros: tuple[Any, ...] = ()
    if not incluir_arquivados:
        sql += " WHERE status <> ?"
        parametros = ("Arquivado",)
    sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [
        {
            "id": linha["id"],
            "nome": linha["name"],
            "codigo": linha["code"],
            "status": linha["status"],
            "revisao": linha["revision"],
            "criado_em": linha["created_at"],
            "atualizado_em": linha["updated_at"],
        }
        for linha in linhas
    ]


def obter_projeto(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any] | None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            "SELECT payload_json FROM projects WHERE id = ?", (str(projeto_id),)
        ).fetchone()
    if linha is None:
        return None
    return _validar_documento(json.loads(linha["payload_json"]))


def salvar_projeto(
    projeto: Mapping[str, Any],
    *,
    motivo: str = "Salvamento",
    criar_revisao: bool = False,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    inicializar_banco(caminho_banco)
    documento = _validar_documento(projeto)
    instante = _agora()
    with _conectar(caminho_banco) as conexao:
        atual = conexao.execute(
            "SELECT revision, created_at FROM projects WHERE id = ?",
            (documento["id"],),
        ).fetchone()
        if atual is None:
            raise ProjetoPersistenciaErro("Projeto nao encontrado no banco.")
        revisao = int(atual["revision"]) + (1 if criar_revisao else 0)
        documento["revisao"] = revisao
        documento["criado_em"] = atual["created_at"]
        documento["atualizado_em"] = instante
        payload = json.dumps(documento, ensure_ascii=False, sort_keys=True)
        conexao.execute(
            """
            UPDATE projects
            SET name=?, code=?, status=?, revision=?, updated_at=?, payload_json=?
            WHERE id=?
            """,
            (
                documento["nome"],
                documento["codigo"],
                documento["status"],
                revisao,
                instante,
                payload,
                documento["id"],
            ),
        )
        if criar_revisao:
            conexao.execute(
                """
                INSERT INTO project_revisions
                    (project_id, revision, reason, created_at, snapshot_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    documento["id"],
                    revisao,
                    str(motivo).strip() or "Nova revisao",
                    instante,
                    payload,
                ),
            )
    return deepcopy(documento)


def historico_revisoes(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(
            """
            SELECT revision, reason, created_at
            FROM project_revisions
            WHERE project_id=? ORDER BY revision DESC
            """,
            (str(projeto_id),),
        ).fetchall()
    return [
        {
            "revisao": linha["revision"],
            "motivo": linha["reason"],
            "criado_em": linha["created_at"],
        }
        for linha in linhas
    ]


def restaurar_revisao(
    projeto_id: str,
    revisao: int,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            """
            SELECT snapshot_json FROM project_revisions
            WHERE project_id=? AND revision=?
            """,
            (str(projeto_id), int(revisao)),
        ).fetchone()
    if linha is None:
        raise ProjetoPersistenciaErro("Revisao nao encontrada.")
    documento = json.loads(linha["snapshot_json"])
    documento["status"] = "Em elaboração"
    return salvar_projeto(
        documento,
        motivo=f"Restauracao da revisao {int(revisao):02d}",
        criar_revisao=True,
        caminho_banco=caminho_banco,
    )


def definir_projeto_ativo(
    projeto_id: str | None,
    *,
    caminho_banco: str | Path | None = None,
) -> None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        if projeto_id is None:
            conexao.execute("DELETE FROM app_settings WHERE key='active_project_id'")
            return
        existe = conexao.execute(
            "SELECT 1 FROM projects WHERE id=?", (str(projeto_id),)
        ).fetchone()
        if existe is None:
            raise ProjetoPersistenciaErro("Projeto ativo nao encontrado.")
        conexao.execute(
            """
            INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(projeto_id),),
        )


def obter_projeto_ativo(
    *, caminho_banco: str | Path | None = None
) -> dict[str, Any] | None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            "SELECT value FROM app_settings WHERE key='active_project_id'"
        ).fetchone()
    if linha is None:
        return None
    projeto = obter_projeto(linha["value"], caminho_banco=caminho_banco)
    if projeto is None:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    return projeto


def arquivar_projeto(
    projeto_id: str,
    *,
    arquivado: bool = True,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    projeto["status"] = "Arquivado" if arquivado else "Em elaboração"
    salvo = salvar_projeto(projeto, caminho_banco=caminho_banco)
    ativo = obter_projeto_ativo(caminho_banco=caminho_banco)
    if arquivado and ativo and ativo["id"] == projeto_id:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    return salvo


def excluir_projeto(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> None:
    """Apaga o projeto e todo o seu histórico de revisões, sem volta.

    Diferente de :func:`arquivar_projeto`, que só esconde o projeto da lista,
    esta operação remove as linhas do banco. As revisões caem em cascata
    pela chave estrangeira; o ponteiro de projeto ativo é limpo antes, para
    que nenhuma página fique apontando para um id inexistente.
    """
    inicializar_banco(caminho_banco)
    ativo = obter_projeto_ativo(caminho_banco=caminho_banco)
    if ativo and ativo["id"] == projeto_id:
        definir_projeto_ativo(None, caminho_banco=caminho_banco)
    with _conectar(caminho_banco) as conexao:
        removido = conexao.execute("DELETE FROM projects WHERE id=?", (str(projeto_id),)).rowcount
    if not removido:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")


def _renumerar_itens_copia(copia: dict[str, Any]) -> dict[str, Any]:
    """Renova IDs internos e preserva vínculos ao duplicar ou importar."""
    colecoes = (
        "componentes",
        "materiais_projeto",
        "casos_carga",
        "combinacoes_carga",
        "normas",
        "registros_tecnicos",
        "checklist",
        "anexos",
    )
    mapas: dict[str, dict[str, str]] = {}
    for colecao in colecoes:
        mapa: dict[str, str] = {}
        for item in copia.get(colecao, []):
            if not isinstance(item, dict):
                continue
            antigo = str(item.get("id") or "")
            novo = str(uuid4())
            item["id"] = novo
            if antigo:
                mapa[antigo] = novo
        mapas[colecao] = mapa

    mapa_componentes = mapas["componentes"]
    mapa_materiais = mapas["materiais_projeto"]
    mapa_casos = mapas["casos_carga"]
    mapa_registros = mapas["registros_tecnicos"]
    for componente in copia.get("componentes", []):
        if isinstance(componente, dict):
            material_id = str(componente.get("material_id") or "")
            if material_id in mapa_materiais:
                componente["material_id"] = mapa_materiais[material_id]
    for material in copia.get("materiais_projeto", []):
        if isinstance(material, dict):
            material["vinculacoes"] = [
                mapa_componentes.get(str(valor), str(valor))
                for valor in material.get("vinculacoes", [])
            ]
    for combinacao in copia.get("combinacoes_carga", []):
        if not isinstance(combinacao, dict):
            continue
        fatores = combinacao.get("fatores", {})
        if isinstance(fatores, Mapping):
            combinacao["fatores"] = {
                mapa_casos.get(str(caso_id), str(caso_id)): fator
                for caso_id, fator in fatores.items()
            }
    for registro in copia.get("registros_tecnicos", []):
        if not isinstance(registro, dict):
            continue
        for campo, mapa in (
            ("casos_carga_ids", mapa_casos),
            ("componentes_ids", mapa_componentes),
            ("materiais_ids", mapa_materiais),
        ):
            registro[campo] = [
                mapa.get(str(valor), str(valor)) for valor in registro.get(campo, [])
            ]
        entradas = registro.get("entradas")
        if isinstance(entradas, dict):
            if str(entradas.get("material_id") or "") in mapa_materiais:
                entradas["material_id"] = mapa_materiais[str(entradas["material_id"])]
            if str(entradas.get("registro_origem") or "") in mapa_registros:
                entradas["registro_origem"] = mapa_registros[str(entradas["registro_origem"])]
        # A assinatura anterior deixa de ser válida após a troca deliberada dos IDs.
        registro.pop("hash_calculo", None)
        registro.update(normalizar_registro_tecnico(registro))
    return copia


def duplicar_projeto(
    projeto_id: str,
    *,
    novo_nome: str | None = None,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    origem = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if origem is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    instante = _agora()
    copia = deepcopy(origem)
    copia["id"] = str(uuid4())
    copia["nome"] = str(novo_nome).strip() if novo_nome else f"{origem['nome']} - cópia"
    copia["codigo"] = f"{origem['codigo']}-COPIA"
    copia["status"] = "Em elaboração"
    copia["revisao"] = 0
    copia["criado_em"] = instante
    copia["atualizado_em"] = instante
    _renumerar_itens_copia(copia)
    payload = json.dumps(_validar_documento(copia), ensure_ascii=False, sort_keys=True)
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                copia["id"], copia["nome"], copia["codigo"], copia["status"],
                instante, instante, payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, 0, ?, ?, ?)
            """,
            (copia["id"], f"Cópia de {origem['codigo']}", instante, payload),
        )
    definir_projeto_ativo(copia["id"], caminho_banco=caminho_banco)
    return deepcopy(copia)


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
    return salvar_projeto(projeto, caminho_banco=caminho_banco)


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
    return salvar_projeto(projeto, caminho_banco=caminho_banco)


def exportar_projeto(
    projeto_id: str,
    *,
    incluir_historico: bool = True,
    caminho_banco: str | Path | None = None,
) -> bytes:
    projeto = obter_projeto(projeto_id, caminho_banco=caminho_banco)
    if projeto is None:
        raise ProjetoPersistenciaErro("Projeto nao encontrado.")
    pacote = {
        "formato": FORMATO_EXPORTACAO,
        "versao": VERSAO_ESQUEMA,
        "exportado_em": _agora(),
        "projeto": projeto,
        "historico": (
            historico_revisoes(projeto_id, caminho_banco=caminho_banco)
            if incluir_historico
            else []
        ),
    }
    return json.dumps(pacote, ensure_ascii=False, indent=2).encode("utf-8")


def importar_projeto(
    conteudo: bytes | str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    try:
        texto = conteudo.decode("utf-8-sig") if isinstance(conteudo, bytes) else conteudo
        pacote = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ProjetoPersistenciaErro(f"Arquivo de projeto invalido: {erro}") from erro
    if pacote.get("formato") != FORMATO_EXPORTACAO:
        raise ProjetoPersistenciaErro("O arquivo nao e um projeto do Mecanica Toolkit.")
    origem = _validar_documento(pacote.get("projeto", {}))
    copia = deepcopy(origem)
    instante = _agora()
    copia["id"] = str(uuid4())
    copia["nome"] = f"{origem['nome']} - importado"
    copia["codigo"] = f"{origem['codigo']}-IMP"
    copia["status"] = "Em elaboração"
    copia["revisao"] = 0
    copia["criado_em"] = instante
    copia["atualizado_em"] = instante
    _renumerar_itens_copia(copia)
    inicializar_banco(caminho_banco)
    payload = json.dumps(copia, ensure_ascii=False, sort_keys=True)
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                copia["id"], copia["nome"], copia["codigo"], copia["status"],
                instante, instante, payload,
            ),
        )
        conexao.execute(
            """
            INSERT INTO project_revisions
                (project_id, revision, reason, created_at, snapshot_json)
            VALUES (?, 0, 'Importação de projeto', ?, ?)
            """,
            (copia["id"], instante, payload),
        )
    definir_projeto_ativo(copia["id"], caminho_banco=caminho_banco)
    return deepcopy(copia)


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
