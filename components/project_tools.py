"""Ponte entre os módulos Streamlit e o projeto permanente."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from core.project_store import (
    ProjetoPersistenciaErro,
    criar_projeto,
    obter_projeto_ativo,
    registrar_calculo_tecnico,
)
from core.technical_records import (
    calcular_hash_registro,
    criar_registro_tecnico,
    normalizar_registro_tecnico,
)


def contexto_sessao_projeto(projeto: Mapping[str, Any]) -> dict[str, Any]:
    """Mantém compatibilidade com cabeçalhos e módulos antigos."""
    return {
        "id": projeto.get("id"),
        "nome": projeto.get("nome"),
        "codigo": projeto.get("codigo"),
        "status": projeto.get("status"),
        "revisao": projeto.get("revisao"),
        "descricao": projeto.get("descricao"),
        "objetivo": projeto.get("objetivo"),
        "tag_equipamento": projeto.get("tag_equipamento"),
        "rota": "Gestão industrial",
        "persistente": True,
    }


def sincronizar_projeto_ativo() -> dict[str, Any] | None:
    """Recarrega o projeto ativo do SQLite a cada execução da página."""
    projeto = obter_projeto_ativo()
    st.session_state["projeto_ativo"] = (
        contexto_sessao_projeto(projeto) if projeto is not None else None
    )
    return projeto


def projeto_ativo_persistente() -> dict[str, Any] | None:
    return obter_projeto_ativo()


def construir_registro_tecnico(
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
    return criar_registro_tecnico(
        modulo=modulo,
        modulo_id=modulo_id,
        metodo_versao=metodo_versao,
        titulo=titulo,
        status=status,
        resumo=resumo,
        entradas=entradas,
        resultados=resultados,
        premissas=premissas,
        metodo=metodo,
        equacoes=equacoes,
        criterios=criterios,
        incertezas=incertezas,
        alertas=alertas,
        referencias=referencias,
        conclusao=conclusao,
        responsavel=responsavel,
        casos_carga_ids=casos_carga_ids,
        componentes_ids=componentes_ids,
        materiais_ids=materiais_ids,
    )


def id_registro_existente(registro: Mapping[str, Any]) -> str | None:
    """Encontra, no projeto ativo, um registro já salvo com este mesmo conteúdo.

    Usado para levar a *origem* de um cálculo ao repassá-lo entre módulos
    (Assistente de cargas → Mohr, Mohr → Estática etc.) sem inventar um
    vínculo: só aponta para um registro que o usuário de fato registrou no
    projeto. Se o cálculo ainda não foi salvo, retorna ``None`` — a origem
    fica em aberto, em vez de apontar para algo que não existe.
    """
    projeto = projeto_ativo_persistente()
    if projeto is None:
        return None
    alvo = calcular_hash_registro(normalizar_registro_tecnico(registro))
    for existente in projeto.get("registros_tecnicos", []):
        if isinstance(existente, Mapping) and existente.get("hash_calculo") == alvo:
            return existente.get("id")
    return None


def botao_registrar_calculo(
    registro: Mapping[str, Any],
    *,
    key: str,
    rotulo: str = "Registrar no projeto ativo",
    tipo: str = "primary",
) -> bool:
    """Mostra uma ação explícita e persiste o resultado no projeto ativo."""
    projeto = projeto_ativo_persistente()
    if projeto is None:
        with st.container(border=True):
            st.caption(
                ":material/folder_off: Nenhum projeto permanente está ativo. "
                "Crie um projeto rápido para guardar este cálculo agora, sem "
                "sair do módulo, ou abra um projeto já existente."
            )
            coluna_nome, coluna_botao = st.columns([3, 1])
            nome_novo_projeto = coluna_nome.text_input(
                "Nome do novo projeto",
                key=f"{key}_novo_projeto_nome",
                label_visibility="collapsed",
                placeholder="Nome do novo projeto industrial…",
            )
            criar_e_registrar = coluna_botao.button(
                "Criar e registrar",
                icon=":material/add_circle:",
                key=f"{key}_criar_projeto",
                width="stretch",
            )
            st.page_link(
                "app_pages/gestao_projetos.py",
                label="Ou abrir um projeto existente",
                icon=":material/folder_managed:",
            )
            if criar_e_registrar:
                nome_limpo = nome_novo_projeto.strip()
                if not nome_limpo:
                    st.error("Informe um nome para o novo projeto antes de criar.")
                    return False
                try:
                    novo_projeto = criar_projeto(nome_limpo)
                    salvo = registrar_calculo_tecnico(novo_projeto["id"], registro)
                except ProjetoPersistenciaErro as erro:
                    st.error(f"Não foi possível criar o projeto: {erro}")
                    return False
                st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
                st.success(
                    f"Projeto {salvo['codigo']} · {salvo['nome']} criado e ativado, "
                    "com este cálculo já registrado nele. Complete a identificação "
                    "e a base de projeto em Gestão de projetos quando puder."
                )
                st.rerun()
        return False
    if st.button(
        rotulo,
        icon=":material/save:",
        type=tipo,
        key=key,
        help=(
            f"Salva uma cópia rastreável destas entradas e resultados em "
            f"{projeto['codigo']} · {projeto['nome']}."
        ),
    ):
        try:
            salvo = registrar_calculo_tecnico(projeto["id"], registro)
        except ProjetoPersistenciaErro as erro:
            st.error(f"Não foi possível salvar o registro: {erro}")
            return False
        st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
        st.success(
            f"Registro incluído em {salvo['codigo']} · {salvo['nome']}. "
            "A alteração já está gravada no banco local."
        )
        return True
    return False
