"""Jornada do projeto ativo e rascunhos editáveis por seção.

Os dados continuam nos campos permanentes usados pelos módulos. O rascunho é
da sessão até o usuário salvar e guarda o contador visto no início da edição,
para não apagar uma gravação feita em outra janela.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any

import streamlit as st

from components.painel_projeto_ui import renderizar_painel_projeto
from core.checklist_templates import (
    ModeloChecklistErro,
    aplicar_modelo,
    itens_ja_aplicados,
    modelo_para_tipo,
    tipos_de_projeto,
)
from core.project_store import CAMPO_GRAVACAO, criar_item
from core.project_validation import pendencias_de_preenchimento

SECOES = ("Visão geral", "Escopo", "Base técnica", "Cálculos", "Entrega")
_CAMPOS_ESCOPO = (
    ("tipo_projeto", "Tipo de projeto"),
    ("nome", "Nome do projeto"),
    ("codigo", "Código do projeto"),
    ("objetivo", "Objetivo e resultado esperado"),
    ("descricao", "Descrição do escopo"),
    ("cliente", "Cliente ou solicitante"),
    ("unidade_industrial", "Unidade industrial"),
    ("area", "Área ou setor"),
    ("tag_equipamento", "TAG principal"),
    ("responsavel", "Responsável técnico"),
    ("verificador", "Verificador"),
    ("aprovador", "Aprovador"),
)
_CAMPOS_BASE = (
    ("referencias_desenho", "Desenhos e documentos de entrada"),
    ("base_carregamentos", "Base e origem dos carregamentos"),
    ("condicoes_operacao", "Condições de operação"),
    ("criterio_aceitacao", "Critérios de aceitação"),
    ("vida_requerida", "Vida requerida"),
    ("limitacoes", "Limitações, exclusões e interfaces"),
)


def _sugestoes_elementos(tipo: str) -> tuple[str, ...]:
    """Sugestões de escopo, nunca dados técnicos ou afirmações de aplicabilidade."""
    nome = tipo.casefold()
    if "plataforma" in nome or "estrutura" in nome:
        return (
            "Piso",
            "Vigas",
            "Pilares",
            "Contraventamentos",
            "Escada",
            "Guarda-corpo",
            "Ligações",
            "Bases",
        )
    if "transportador" in nome:
        return ("Estrutura de suporte", "Acionamento", "Tambor", "Eixo", "Ligações")
    if "tanque" in nome or "vaso" in nome:
        return ("Costado", "Tampos", "Suportes", "Bocais", "Ligações")
    if "eixo" in nome:
        return ("Eixo", "Apoios", "Acoplamento", "Ligações")
    return ("Equipamento", "Estrutura de suporte", "Ligações")


def _abrir_secao(chave: str, secao: str) -> None:
    st.session_state[chave] = secao


def _alterar_rascunho(chave: str, campo: str, widget: str) -> None:
    st.session_state[chave]["valores"][campo] = st.session_state[widget]


def _rascunho(
    projeto: Mapping[str, Any], secao: str, campos: tuple[tuple[str, str], ...]
) -> tuple[str, dict[str, Any]]:
    chave = f"jornada_rascunho_{projeto['id']}_{secao}"
    fonte = projeto.get("base_projeto", {}) if secao == "base" else projeto
    if not isinstance(fonte, Mapping):
        fonte = {}
    valores = {campo: str(fonte.get(campo) or "") for campo, _ in campos}
    existente = st.session_state.get(chave)
    if existente is None or (
        existente["valores"] == existente["originais"]
        and existente["gravacao"] != projeto.get(CAMPO_GRAVACAO)
    ):
        for campo, _ in campos:
            st.session_state.pop(f"{chave}_{campo}", None)
        existente = {
            "valores": valores.copy(),
            "originais": valores,
            "gravacao": projeto.get(CAMPO_GRAVACAO),
        }
        st.session_state[chave] = existente
    return chave, existente


def _editor(
    projeto: dict[str, Any],
    secao: str,
    campos: tuple[tuple[str, str], ...],
    salvar: Callable[..., Any],
) -> bool:
    chave, rascunho = _rascunho(projeto, secao, campos)
    st.caption(
        "Os valores existentes vêm do cadastro do projeto. Suas alterações ficam no rascunho até salvar."
    )
    for campo, rotulo in campos:
        widget = f"{chave}_{campo}"
        if widget not in st.session_state:
            st.session_state[widget] = rascunho["valores"][campo]
        if campo == "tipo_projeto":
            try:
                opcoes = tipos_de_projeto()
            except ModeloChecklistErro:
                opcoes = ["Projeto industrial"]
            if rascunho["valores"][campo] not in opcoes:
                opcoes.append(rascunho["valores"][campo])
            st.selectbox(
                rotulo, opcoes, key=widget, on_change=_alterar_rascunho, args=(chave, campo, widget)
            )
        else:
            multiline = campo in {
                "objetivo",
                "descricao",
                "referencias_desenho",
                "base_carregamentos",
                "condicoes_operacao",
                "criterio_aceitacao",
                "limitacoes",
            }
            metodo = st.text_area if multiline else st.text_input
            metodo(rotulo, key=widget, on_change=_alterar_rascunho, args=(chave, campo, widget))
    alterado = rascunho["valores"] != rascunho["originais"]
    if alterado:
        st.warning("Há alterações não salvas nesta etapa. Salve antes de encerrar a sessão.")
    else:
        st.caption("Nenhuma alteração pendente nesta etapa.")
    if st.button("Salvar rascunho", key=f"salvar_{chave}", type="primary", disabled=not alterado):
        documento = deepcopy(projeto)
        documento[CAMPO_GRAVACAO] = rascunho["gravacao"]
        if secao == "base":
            documento["base_projeto"] = {**documento.get("base_projeto", {}), **rascunho["valores"]}
        else:
            documento.update(rascunho["valores"])
        if (
            not str(documento.get("nome") or "").strip()
            or not str(documento.get("codigo") or "").strip()
        ):
            st.error("Nome e código são necessários para salvar o projeto.")
        else:
            salvar(documento, f"Jornada: atualização de {secao}")
            st.session_state.pop(chave, None)
            st.rerun()
    return alterado


def renderizar_jornada(
    projeto: dict[str, Any],
    validacao: Mapping[str, Any],
    resumo: Mapping[str, Any],
    salvar: Callable[..., Any],
) -> None:
    """Uma entrada orientada por trabalho, sobre os dados permanentes existentes."""
    identificador = str(projeto["id"])
    chave_secao = f"jornada_secao_{identificador}"
    st.session_state.setdefault(chave_secao, SECOES[0])
    alvo = st.session_state.pop("projeto_jornada_alvo", None)
    if isinstance(alvo, Mapping) and alvo.get("secao") in SECOES:
        st.session_state[chave_secao] = alvo["secao"]
        if alvo.get("campo"):
            st.info(f"Preencha ou revise: {alvo['campo']}.")
    st.markdown(f"### {projeto['codigo']} · {projeto['nome']}")
    st.caption(
        f"Projeto ativo · Revisão {int(projeto.get('revisao', 0)):02d} · {projeto.get('status', '')}"
    )
    secao = (
        st.segmented_control("Etapa do projeto", SECOES, key=chave_secao, selection_mode="single")
        or SECOES[0]
    )
    pendentes = [
        nome
        for nome in ("escopo", "base")
        if (rascunho := st.session_state.get(f"jornada_rascunho_{identificador}_{nome}"))
        and rascunho["valores"] != rascunho["originais"]
    ]
    if pendentes:
        st.caption("Rascunho ainda não salvo: " + ", ".join(pendentes) + ".")

    if secao == "Visão geral":
        renderizar_painel_projeto(projeto, validacao, resumo, origem="jornada")
        st.subheader("Continue de onde parou")
        faltantes = pendencias_de_preenchimento(projeto)
        if faltantes:
            for item in faltantes[:5]:
                destino = "Base técnica" if item["grupo"] == "base" else "Escopo"
                col1, col2 = st.columns([5, 1])
                col1.markdown(f"**{item['rotulo'].capitalize()}** · {item['severidade']}")
                col2.button(
                    "Abrir",
                    key=f"jornada_abrir_{identificador}_{item['campo']}",
                    on_click=_abrir_secao,
                    args=(chave_secao, destino),
                )
        else:
            st.success("Os campos principais do cadastro estão preenchidos.")
        st.page_link(
            "app_pages/central_validacao.py",
            label="Ver todas as pendências",
            icon=":material/fact_check:",
        )
        st.page_link(
            "app_pages/roteiro_projeto.py",
            label="Abrir roteiro completo e verificações complementares",
            icon=":material/format_list_numbered:",
        )
        st.markdown("##### Caminho sem SolidWorks")
        st.caption(
            "Se o projeto não usa modelo no SolidWorks, informe a base, registre os cálculos "
            "nos módulos ou como preenchimento externo e prepare o memorial."
        )
        with st.container(horizontal=True):
            st.button(
                "Abrir base técnica",
                key=f"jornada_sem_cad_base_{identificador}",
                on_click=_abrir_secao,
                args=(chave_secao, "Base técnica"),
            )
            st.button(
                "Abrir cálculos",
                key=f"jornada_sem_cad_calculos_{identificador}",
                on_click=_abrir_secao,
                args=(chave_secao, "Cálculos"),
            )
            st.button(
                "Abrir entrega",
                key=f"jornada_sem_cad_entrega_{identificador}",
                on_click=_abrir_secao,
                args=(chave_secao, "Entrega"),
            )
    elif secao == "Escopo":
        st.subheader("Identificação e escopo")
        st.caption("A escolha do tipo orienta as sugestões de elementos após salvar a etapa.")
        alterado = _editor(projeto, "escopo", _CAMPOS_ESCOPO, salvar)
        st.markdown("##### Elementos que podem fazer parte do projeto")
        st.caption(
            "Selecione somente os elementos aplicáveis. Novos itens entram sem TAG ou material para você completar."
        )
        opcoes = _sugestoes_elementos(str(projeto.get("tipo_projeto") or ""))
        existentes = {
            str(item.get("descricao") or "").strip().casefold()
            for item in projeto.get("componentes", [])
            if isinstance(item, Mapping)
        }
        disponiveis = [item for item in opcoes if item.casefold() not in existentes]
        selecionados = st.multiselect(
            "Sugestões de elementos", disponiveis, key=f"jornada_elementos_{identificador}"
        )
        if st.button(
            "Adicionar elementos selecionados",
            key=f"jornada_adicionar_{identificador}",
            disabled=not selecionados or alterado,
        ):
            documento = deepcopy(projeto)
            documento["componentes"] = [
                *documento.get("componentes", []),
                *[
                    {**criar_item(), "descricao": item, "tag": "", "material": ""}
                    for item in selecionados
                ],
            ]
            salvar(documento, "Jornada: elementos adicionados ao escopo")
            st.rerun()
        st.caption(
            f"{len(projeto.get('componentes', []))} item(ns) no escopo. A edição detalhada permite identificar cada peça."
        )

    elif secao == "Base técnica":
        st.subheader("Base e premissas do projeto")
        _editor(projeto, "base", _CAMPOS_BASE, salvar)
        st.caption(
            "A base documental, os critérios de aceitação e a base técnica dos cálculos são cadastros distintos."
        )
        with st.container(horizontal=True):
            st.page_link(
                "app_pages/base_tecnica.py",
                label="Base técnica dos cálculos",
                icon=":material/tune:",
            )
            st.page_link(
                "app_pages/casos_carga.py",
                label="Casos e combinações de carga",
                icon=":material/layers:",
            )
            st.page_link(
                "app_pages/materiais_tecnicos.py", label="Materiais", icon=":material/science:"
            )

    elif secao == "Cálculos":
        st.subheader("Cálculos do projeto")
        registros = [r for r in projeto.get("registros_tecnicos", []) if isinstance(r, Mapping)]
        st.caption(
            f"{len(registros)} registro(s) no projeto, incluindo o histórico. A situação técnica é informada por cada registro."
        )
        for registro in registros[:8]:
            st.markdown(
                f"- **{registro.get('titulo') or 'Cálculo'}** · {registro.get('peca') or 'peça não informada'} · {registro.get('status') or 'Pendente'}"
            )
        st.page_link(
            "app_pages/calculos_manuais.py",
            label="Cálculos manuais e externos",
            icon=":material/edit_note:",
        )
        st.page_link(
            "app_pages/roteiro_projeto.py",
            label="Roteiro e verificações complementares",
            icon=":material/format_list_numbered:",
        )

    else:
        st.subheader("Revisar e preparar a entrega")
        bloqueios = validacao["contagens"]["Bloqueio"]
        st.caption(
            f"{bloqueios} bloqueio(s) na validação. Um rascunho pode ser gerado para revisão; isso não aprova o projeto."
        )
        try:
            modelo = modelo_para_tipo(str(projeto.get("tipo_projeto") or ""))
        except ModeloChecklistErro as erro:
            modelo = None
            st.error(f"Não foi possível carregar os modelos de checklist: {erro}")
        if modelo:
            st.markdown("##### Checklist sugerido para este tipo de projeto")
            st.caption(
                f"Modelo: {modelo.nome}. Os itens são sugestões para revisar a aplicabilidade; "
                "entram como abertos e não comprovam cálculos nem aprovação."
            )
            aplicados = itens_ja_aplicados(projeto, modelo)
            disponiveis = {item.chave: item for item in modelo.itens if item.chave not in aplicados}
            if disponiveis:
                escolhas = st.multiselect(
                    "Verificações a acrescentar",
                    list(disponiveis),
                    default=list(disponiveis),
                    format_func=lambda chave: disponiveis[chave].item,
                    key=f"jornada_checklist_{identificador}_{modelo.id}",
                )
                if st.button(
                    "Adicionar verificações ao checklist",
                    key=f"jornada_aplicar_checklist_{identificador}",
                    disabled=not escolhas,
                    icon=":material/add_task:",
                ):
                    selecionado = replace(
                        modelo, itens=tuple(item for item in modelo.itens if item.chave in escolhas)
                    )
                    documento, novos, _ = aplicar_modelo(projeto, selecionado)
                    if novos:
                        salvar(
                            documento, f"Checklist: {len(novos)} sugestões do modelo {modelo.nome}"
                        )
                    st.session_state.pop(f"jornada_checklist_{identificador}_{modelo.id}", None)
                    st.rerun()
            else:
                st.caption("Os itens deste modelo já estão no checklist do projeto.")
        st.page_link(
            "app_pages/central_validacao.py",
            label="Revisar validação e pendências",
            icon=":material/fact_check:",
        )
        st.page_link(
            "app_pages/central_relatorios.py",
            label="Preparar memorial",
            icon=":material/description:",
        )
        st.caption(
            "A situação e as revisões do projeto permanecem disponíveis na edição detalhada."
        )
