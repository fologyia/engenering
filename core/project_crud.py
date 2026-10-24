"""CRUD do projeto industrial: criação, leitura, gravação e ciclo de vida.

Toda operação passa pelo banco SQLite de ``core.project_store``: cria o
projeto, lista e carrega documentos, grava com o controle de concorrência do
contador ``write_seq``, aponta o projeto ativo, arquiva, exclui e duplica.
O histórico (linha do tempo e revisões) fica em ``core.project_revisions`` e
o espelhamento remoto, em ``core.project_espelho``.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from core import espelho_remoto
from core.project_espelho import _espelhar_projeto
from core.project_revisions import (
    EVENTO_ADMINISTRACAO,
    EVENTO_CRIACAO,
    EVENTO_REVISAO,
    EVENTO_SALVAMENTO,
    EVENTO_SITUACAO,
    _registrar_evento,
    obter_revisao,
)
from core.project_store import (
    PASTA_ESPELHO_PROJETOS,
    _conectar,
    inicializar_banco,
)
from core.projeto_documento import (
    CAMPO_GRAVACAO,
    ProjetoConflitoErro,
    ProjetoPersistenciaErro,
    _agora,
    _documento_da_linha,
    _payload,
    _validar_documento,
    novo_projeto_documento,
)
from core.technical_records import normalizar_registro_tecnico


def criar_projeto(
    nome: str,
    *,
    caminho_banco: str | Path | None = None,
    ativar: bool = True,
    **campos: Any,
) -> dict[str, Any]:
    inicializar_banco(caminho_banco)
    projeto = novo_projeto_documento(nome, **campos)
    payload = _payload(projeto)
    projeto[CAMPO_GRAVACAO] = 0
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
        _registrar_evento(
            conexao,
            projeto["id"],
            EVENTO_CRIACAO,
            "Criação do projeto",
            revisao=0,
            status=projeto["status"],
            instante=projeto["criado_em"],
        )
        if ativar:
            conexao.execute(
                """
                INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (projeto["id"],),
            )
    _espelhar_projeto(projeto["id"], "Criação do projeto", caminho_banco=caminho_banco)
    return deepcopy(projeto)


def listar_projetos(
    *,
    incluir_arquivados: bool = False,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    inicializar_banco(caminho_banco)
    sql = "SELECT id, name, code, status, revision, created_at, updated_at FROM projects"
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


def carregar_projetos(
    *,
    incluir_arquivados: bool = False,
    caminho_banco: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Documentos completos de todos os projetos, na ordem de :func:`listar_projetos`.

    O painel de carteira precisa validar cada projeto, e isso exige o
    documento inteiro — não a linha de resumo. Uma consulta só, em vez de
    uma por projeto.
    """
    inicializar_banco(caminho_banco)
    sql = "SELECT payload_json, write_seq FROM projects"
    parametros: tuple[Any, ...] = ()
    if not incluir_arquivados:
        sql += " WHERE status <> ?"
        parametros = ("Arquivado",)
    sql += " ORDER BY updated_at DESC, name COLLATE NOCASE"
    with _conectar(caminho_banco) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [_documento_da_linha(linha) for linha in linhas]


def obter_projeto(
    projeto_id: str,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any] | None:
    inicializar_banco(caminho_banco)
    with _conectar(caminho_banco) as conexao:
        linha = conexao.execute(
            "SELECT payload_json, write_seq FROM projects WHERE id = ?", (str(projeto_id),)
        ).fetchone()
    if linha is None:
        return None
    return _documento_da_linha(linha)


def salvar_projeto(
    projeto: Mapping[str, Any],
    *,
    motivo: str = "Salvamento",
    criar_revisao: bool = False,
    tipo_evento: str = "",
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    """Grava o documento e anota o motivo na linha do tempo.

    Uma mudança de situação (``status``) sempre gera um evento próprio, seja
    qual for o caminho que a provocou — formulário, fluxo com portões,
    arquivamento ou restauração — para a linha do tempo não depender de cada
    página lembrar de avisar.

    O documento carrega o contador de gravações que leu do banco
    (``gravacao``). Se o banco já estiver adiante — outra aba ou outra
    pessoa gravou no meio do caminho — a escrita é recusada com
    :class:`ProjetoConflitoErro` em vez de sobrescrever a gravação alheia.
    Documentos sem o campo (fotografias de revisão restauradas, documentos
    montados à mão) não são conferidos: são sobrescritas deliberadas.
    """
    inicializar_banco(caminho_banco)
    documento = _validar_documento(projeto)
    gravacao_lida = documento.pop(CAMPO_GRAVACAO, None)
    instante = _agora()
    with _conectar(caminho_banco) as conexao:
        atual = conexao.execute(
            "SELECT revision, created_at, status, write_seq FROM projects WHERE id = ?",
            (documento["id"],),
        ).fetchone()
        if atual is None:
            raise ProjetoPersistenciaErro("Projeto nao encontrado no banco.")
        gravacao_atual = int(atual["write_seq"])
        if gravacao_lida is not None and int(gravacao_lida) != gravacao_atual:
            raise ProjetoConflitoErro(
                "Este projeto foi gravado por outra sessão depois que esta tela o carregou "
                f"(gravação nº {gravacao_atual} no banco, nº {int(gravacao_lida)} nesta tela). "
                "Recarregue a página e refaça a alteração, para não sobrescrever o que já foi salvo."
            )
        revisao = int(atual["revision"]) + (1 if criar_revisao else 0)
        status_anterior = str(atual["status"])
        documento["revisao"] = revisao
        documento["criado_em"] = atual["created_at"]
        documento["atualizado_em"] = instante
        payload = _payload(documento)
        # A condição ``write_seq=?`` fecha a janela entre o SELECT acima e
        # este UPDATE: quem gravou nesse intervalo faz o UPDATE não casar
        # nenhuma linha, e a recusa vale mesmo para documentos sem o campo.
        gravados = conexao.execute(
            """
            UPDATE projects
            SET name=?, code=?, status=?, revision=?, updated_at=?, payload_json=?, write_seq=?
            WHERE id=? AND write_seq=?
            """,
            (
                documento["nome"],
                documento["codigo"],
                documento["status"],
                revisao,
                instante,
                payload,
                gravacao_atual + 1,
                documento["id"],
                gravacao_atual,
            ),
        ).rowcount
        if gravados != 1:
            raise ProjetoConflitoErro(
                "Este projeto foi gravado por outra sessão neste exato momento. "
                "Recarregue a página e refaça a alteração."
            )
        documento[CAMPO_GRAVACAO] = gravacao_atual + 1
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
        tipo = str(tipo_evento).strip() or (EVENTO_REVISAO if criar_revisao else EVENTO_SALVAMENTO)
        descricao = str(motivo).strip() or (
            f"Revisão {revisao:02d} criada" if criar_revisao else "Salvamento"
        )
        if criar_revisao and tipo == EVENTO_REVISAO:
            descricao = f"Revisão {revisao:02d}: {descricao}"
        _registrar_evento(
            conexao,
            documento["id"],
            tipo,
            descricao,
            revisao=revisao,
            status=documento["status"],
            instante=instante,
        )
        if documento["status"] != status_anterior:
            _registrar_evento(
                conexao,
                documento["id"],
                EVENTO_SITUACAO,
                f"Situação alterada de {status_anterior} para {documento['status']}",
                revisao=revisao,
                status=documento["status"],
                instante=instante,
            )
    _espelhar_projeto(documento["id"], descricao, caminho_banco=caminho_banco)
    return deepcopy(documento)


def restaurar_revisao(
    projeto_id: str,
    revisao: int,
    *,
    caminho_banco: str | Path | None = None,
) -> dict[str, Any]:
    documento = obter_revisao(projeto_id, revisao, caminho_banco=caminho_banco)
    if documento is None:
        raise ProjetoPersistenciaErro("Revisao nao encontrada.")
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
        existe = conexao.execute("SELECT 1 FROM projects WHERE id=?", (str(projeto_id),)).fetchone()
        if existe is None:
            raise ProjetoPersistenciaErro("Projeto ativo nao encontrado.")
        conexao.execute(
            """
            INSERT INTO app_settings(key, value) VALUES('active_project_id', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(projeto_id),),
        )


def obter_projeto_ativo(*, caminho_banco: str | Path | None = None) -> dict[str, Any] | None:
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
    salvo = salvar_projeto(
        projeto,
        motivo="Projeto arquivado" if arquivado else "Projeto desarquivado",
        tipo_evento=EVENTO_ADMINISTRACAO,
        caminho_banco=caminho_banco,
    )
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
    espelho_remoto.apagar(f"{PASTA_ESPELHO_PROJETOS}/{projeto_id}.json", "Projeto excluído")


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
    payload = _payload(_validar_documento(copia))
    copia[CAMPO_GRAVACAO] = 0
    with _conectar(caminho_banco) as conexao:
        conexao.execute(
            """
            INSERT INTO projects
                (id, name, code, status, revision, created_at, updated_at, payload_json)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                copia["id"],
                copia["nome"],
                copia["codigo"],
                copia["status"],
                instante,
                instante,
                payload,
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
        _registrar_evento(
            conexao,
            copia["id"],
            EVENTO_CRIACAO,
            f"Criado como cópia de {origem['codigo']} · {origem['nome']}",
            revisao=0,
            status=copia["status"],
            instante=instante,
        )
    definir_projeto_ativo(copia["id"], caminho_banco=caminho_banco)
    _espelhar_projeto(copia["id"], f"Cópia de {origem['codigo']}", caminho_banco=caminho_banco)
    return deepcopy(copia)
