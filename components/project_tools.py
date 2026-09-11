"""Ponte entre os módulos Streamlit e o projeto permanente."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from core.project_store import (
    ProjetoPersistenciaErro,
    criar_item,
    criar_projeto,
    obter_projeto_ativo,
    registrar_calculo_tecnico,
    revisar_listas,
    salvar_projeto,
)
from core.technical_records import (
    calcular_hash_registro,
    criar_registro_tecnico,
    identificar_peca_registro,
    normalizar_registro_tecnico,
    rotulo_componente,
)

_OPCAO_SEM_COMPONENTE = "__sem_componente__"
_OPCAO_NOVO_COMPONENTE = "__novo_componente__"


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


def selecionar_peca_registro(
    projeto: Mapping[str, Any] | None,
    *,
    key: str,
) -> tuple[str, str | None, bool]:
    """Pergunta qual peça o cálculo verifica antes de registrá-lo.

    Devolve ``(nome_da_peca, id_do_componente, cadastrar_nova)``. O nome é
    livre ("Coluna P1", "Mão francesa esquerda") e entra na frente do título
    do registro; o componente vincula o registro ao escopo físico já
    cadastrado no projeto, o que permite ao memorial agrupar por peça. Quem
    ainda não cadastrou o escopo pode pedir para criar o componente na hora,
    com o próprio nome informado.
    """
    componentes = [
        item
        for item in (projeto or {}).get("componentes", [])
        if isinstance(item, Mapping) and str(item.get("id") or "").strip()
    ]
    coluna_nome, coluna_componente = st.columns([1, 1])
    nome_peca = coluna_nome.text_input(
        "Identificação da peça",
        key=f"{key}_peca_nome",
        placeholder="Ex.: Coluna P1, Viga principal, Mão francesa esquerda",
        help=(
            "Aparece na frente do título do registro e no quadro-resumo do "
            "memorial, para distinguir peças iguais do mesmo projeto."
        ),
    ).strip()
    opcoes = [_OPCAO_SEM_COMPONENTE, _OPCAO_NOVO_COMPONENTE, *[str(item["id"]) for item in componentes]]
    rotulos = {
        _OPCAO_SEM_COMPONENTE: "Sem vínculo com o escopo físico",
        _OPCAO_NOVO_COMPONENTE: "Cadastrar nova peça no escopo com este nome",
        **{str(item["id"]): rotulo_componente(item) for item in componentes},
    }
    # Sugere o componente cujo TAG ou descrição coincide com o nome digitado,
    # para que quem já cadastrou o escopo não precise escolher duas vezes.
    indice_padrao = 0
    if nome_peca:
        chave_nome = nome_peca.casefold()
        for indice, item in enumerate(componentes, start=2):
            candidatos = {
                str(item.get("tag") or "").strip().casefold(),
                str(item.get("descricao") or "").strip().casefold(),
            }
            if chave_nome in candidatos:
                indice_padrao = indice
                break
    escolha = coluna_componente.selectbox(
        "Componente do escopo físico",
        options=opcoes,
        index=indice_padrao,
        format_func=lambda valor: rotulos.get(valor, valor),
        key=f"{key}_peca_componente",
        help=(
            "Vincula o registro a um item do escopo físico (Gestão de projetos). "
            "No memorial, os cálculos ficam agrupados por peça."
        ),
    )
    if escolha == _OPCAO_NOVO_COMPONENTE:
        return nome_peca, None, True
    if escolha == _OPCAO_SEM_COMPONENTE:
        return nome_peca, None, False
    return nome_peca, escolha, False


def _aplicar_peca(
    projeto: Mapping[str, Any],
    registro: Mapping[str, Any],
    *,
    nome_peca: str,
    componente_id: str | None,
    cadastrar_novo: bool,
) -> tuple[dict[str, Any], str | None]:
    """Vincula o registro à peça, criando o componente no projeto se pedido.

    Retorna o registro identificado e uma mensagem de erro quando o cadastro
    da nova peça não é possível (por exemplo, sem nome). O componente novo é
    gravado antes do registro, porque ``registrar_calculo_tecnico`` relê o
    projeto do banco para fotografar as dependências.
    """
    if cadastrar_novo:
        if not nome_peca:
            return dict(registro), "Informe a identificação da peça para cadastrá-la no escopo físico."
        novo = criar_item(
            tag=nome_peca,
            descricao="",
            servico="",
            material="",
            fonte_material="",
            desenho="",
            criticidade="",
        )
        documento = revisar_listas(projeto, componentes=[*projeto.get("componentes", []), novo])
        salvar_projeto(documento)
        componente_id = novo["id"]
    return (
        identificar_peca_registro(
            registro,
            peca=nome_peca,
            componentes_ids=[componente_id] if componente_id else (),
        ),
        None,
    )


def botao_registrar_calculo(
    registro: Mapping[str, Any],
    *,
    key: str,
    rotulo: str = "Registrar no projeto ativo",
    tipo: str = "primary",
    identificar_peca: bool = True,
) -> bool:
    """Mostra uma ação explícita e persiste o resultado no projeto ativo.

    Com ``identificar_peca`` (padrão), pergunta antes qual peça o cálculo
    verifica; desligue em registros que não pertencem a uma peça específica,
    como combinações de ações ou cadastros de casos de carga.
    """
    projeto = projeto_ativo_persistente()
    nome_peca, componente_id, cadastrar_novo = "", None, False
    if identificar_peca:
        nome_peca, componente_id, cadastrar_novo = selecionar_peca_registro(projeto, key=key)
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
                    registro_final, erro_peca = _aplicar_peca(
                        novo_projeto,
                        registro,
                        nome_peca=nome_peca,
                        componente_id=componente_id,
                        cadastrar_novo=cadastrar_novo,
                    )
                    if erro_peca:
                        st.error(erro_peca)
                        return False
                    salvo = registrar_calculo_tecnico(novo_projeto["id"], registro_final)
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
            registro_final, erro_peca = _aplicar_peca(
                projeto,
                registro,
                nome_peca=nome_peca,
                componente_id=componente_id,
                cadastrar_novo=cadastrar_novo,
            )
            if erro_peca:
                st.error(erro_peca)
                return False
            salvo = registrar_calculo_tecnico(projeto["id"], registro_final)
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
