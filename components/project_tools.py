"""Ponte entre os módulos Streamlit e o projeto permanente."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from core.project_store import (
    ProjetoPersistenciaErro,
    adicionar_registro_tecnico,
    obter_projeto_ativo,
)
from core.technical_records import criar_registro_tecnico


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
                "Crie ou abra um projeto para guardar este cálculo."
            )
            st.page_link(
                "app_pages/gestao_projetos.py",
                label="Abrir Gestão de projetos",
                icon=":material/folder_managed:",
            )
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
            salvo = adicionar_registro_tecnico(projeto["id"], registro)
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
