"""Editor de capítulos externos compartilhado entre Projeto e Memorial."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from components.project_tools import registrar_gravacao_vista, tratar_conflito_de_gravacao
from core.calculo_externo import (
    ESTADOS,
    MODELOS,
    RESULTADOS,
    eh_externo,
    linhas_do_modelo,
    salvar_capitulo,
)
from core.project_store import CAMPO_GRAVACAO, salvar_projeto
from core.technical_records import registro_superado, rotulo_componente


def _linhas(registro: Mapping[str, Any], chave: str, modelo: str) -> list[dict[str, str]]:
    dados = registro.get(chave)
    if isinstance(dados, Mapping) and isinstance(dados.get("grandezas"), list):
        return dados["grandezas"]
    return linhas_do_modelo(modelo, chave)


def _tabela(linhas: list[dict[str, str]]) -> pd.DataFrame:
    colunas = ["grandeza", "valor", "unidade", "fonte"]
    return pd.DataFrame(linhas, columns=colunas).fillna("").astype(str)


def renderizar_calculos_externos(projeto: Mapping[str, Any]) -> None:
    """Mostra cadastro e edição com salvamento contra a versão vista do projeto."""
    projeto_id = str(projeto["id"])
    registros = [r for r in projeto.get("registros_tecnicos", []) if isinstance(r, Mapping)]
    externos = [r for r in registros if eh_externo(r) and not registro_superado(r)]
    st.caption(
        "Os dados e resultados são informados pelo responsável. O programa não executa "
        "nem valida o cálculo externo. Salve o rascunho antes de sair desta página."
    )
    filtro = st.selectbox(
        "Mostrar cálculos",
        ["Todos", "Programa", "Manual ou externo", "A preencher"],
        key=f"filtro_calculos_{projeto_id}",
    )
    visiveis = [
        r
        for r in registros
        if not registro_superado(r)
        and (
            filtro == "Todos"
            or (filtro == "Programa" and not eh_externo(r))
            or (filtro == "Manual ou externo" and eh_externo(r))
            or (filtro == "A preencher" and eh_externo(r) and r.get("preenchimento") != "Informado")
        )
    ]
    if visiveis:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Peça": r.get("peca") or "—",
                        "Cálculo": r.get("titulo") or "—",
                        "Origem": "Manual ou externo" if eh_externo(r) else "Programa",
                        "Preenchimento": r.get("preenchimento", "Registrado"),
                        "Resultado técnico": r.get("status") or "Pendente",
                    }
                    for r in visiveis
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhum cálculo corresponde ao filtro.")

    opcoes = {"": "Adicionar cálculo para preencher"}
    opcoes.update(
        {
            str(r["id"]): f"{r.get('titulo', 'Cálculo')} · {r.get('peca') or 'sem peça'}"
            for r in externos
        }
    )
    chave_escolha = f"externo_escolha_{projeto_id}"
    proxima_escolha = st.session_state.pop(f"{chave_escolha}_proxima", None)
    if proxima_escolha is not None and proxima_escolha in opcoes:
        st.session_state[chave_escolha] = proxima_escolha
    escolha = st.selectbox(
        "Capítulo manual ou externo", list(opcoes), format_func=opcoes.get, key=chave_escolha
    )
    registro = next((r for r in externos if str(r.get("id")) == escolha), {})
    # O contador precisa ser o do início da edição, não o da última
    # reexecução da página: mudar o filtro pode ocorrer depois de outra aba
    # gravar o projeto, enquanto este formulário ainda contém valores antigos.
    chave_versao = f"externo_versao_{projeto_id}_{escolha or 'novo'}"
    versao_edicao = st.session_state.setdefault(chave_versao, projeto.get(CAMPO_GRAVACAO))
    chave_geracao = f"externo_geracao_{projeto_id}_{escolha or 'novo'}"
    geracao = st.session_state.setdefault(chave_geracao, 0)
    if st.button(
        "Descartar edição e recarregar",
        key=f"externo_recarregar_{projeto_id}",
        help="Descarta os campos ainda não salvos e recarrega a versão atual do projeto.",
    ):
        st.session_state.pop(chave_versao, None)
        st.session_state[chave_geracao] = geracao + 1
        st.rerun()
    modelos = list(MODELOS)
    modelo_atual = str(registro.get("modelo_externo") or modelos[0])
    modelo = st.selectbox(
        "Modelo do capítulo",
        modelos,
        index=modelos.index(modelo_atual) if modelo_atual in modelos else 0,
        disabled=bool(registro),
        key=f"externo_modelo_{projeto_id}_{escolha}",
    )
    sufixo = f"{projeto_id}_{escolha or 'novo'}_{modelo}_{geracao}"
    componentes = {
        str(item["id"]): rotulo_componente(item)
        for item in projeto.get("componentes", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    escolhas_componente = ["", *componentes]
    vinculados = registro.get("componentes_ids") or []
    componente_atual = (
        str(vinculados[0]) if vinculados and str(vinculados[0]) in componentes else ""
    )
    with st.form(f"form_externo_{sufixo}"):
        titulo = st.text_input(
            "Título do cálculo",
            value=str(registro.get("titulo") or ("" if modelo == "Personalizado" else modelo)),
        )
        peca = st.text_input("Peça ou TAG", value=str(registro.get("peca") or ""))
        componente = st.selectbox(
            "Vincular ao escopo físico",
            escolhas_componente,
            index=escolhas_componente.index(componente_atual),
            format_func=lambda v: componentes.get(v, "Sem vínculo"),
        )
        resumo = st.text_area("Objetivo e descrição", value=str(registro.get("resumo") or ""))
        st.markdown("**Dados de entrada**")
        entradas = st.data_editor(
            _tabela(_linhas(registro, "entradas", modelo)),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"entradas_externo_{sufixo}",
        )
        st.markdown("**Resultados informados**")
        resultados = st.data_editor(
            _tabela(_linhas(registro, "resultados", modelo)),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"resultados_externo_{sufixo}",
        )
        premissas = st.text_area(
            "Premissas — uma por linha", value="\n".join(registro.get("premissas", []))
        )
        referencias = st.text_area(
            "Referências e revisões — uma por linha",
            value="\n".join(registro.get("referencias", [])),
        )
        metodo = st.text_area("Método", value=str(registro.get("metodo") or ""))
        equacoes = st.text_area(
            "Equações ou etapas — uma por linha", value="\n".join(registro.get("equacoes", []))
        )
        conclusao = st.text_area(
            "Conclusão informada pelo responsável", value=str(registro.get("conclusao") or "")
        )
        responsavel = st.text_input(
            "Responsável pelo cálculo externo", value=str(registro.get("responsavel") or "")
        )
        documento = st.text_input(
            "Documento externo e revisão", value=str(registro.get("documento_externo") or "")
        )
        preenchimento_atual = registro.get("preenchimento", ESTADOS[0])
        preenchimento = st.selectbox(
            "Situação do preenchimento",
            ESTADOS,
            index=ESTADOS.index(preenchimento_atual) if preenchimento_atual in ESTADOS else 0,
        )
        resultado_atual = registro.get("resultado_tecnico", RESULTADOS[0])
        resultado = st.selectbox(
            "Resultado técnico declarado",
            RESULTADOS,
            index=RESULTADOS.index(resultado_atual) if resultado_atual in RESULTADOS else 0,
            help="Quando estiver a preencher, o memorial considera o resultado pendente.",
        )
        peca_copia = (
            st.text_input(
                "Peça ou TAG da cópia",
                help="A cópia mantém os dados de entrada; confira-os. Resultados e conclusão ficam para preencher.",
            )
            if registro
            else ""
        )
        salvar = st.form_submit_button("Salvar rascunho", type="primary", icon=":material/save:")
        duplicar = (
            st.form_submit_button("Duplicar para outra peça", icon=":material/content_copy:")
            if registro
            else False
        )

    if salvar or duplicar:
        if duplicar and not peca_copia.strip():
            st.error("Informe a peça ou TAG da cópia.")
            return
        campos = {
            "titulo": titulo,
            "peca": peca_copia if duplicar else peca,
            "componente_id": "" if duplicar else componente,
            "modelo": modelo,
            "resumo": resumo,
            "entradas": entradas.fillna("").to_dict("records"),
            "resultados": resultados.fillna("").to_dict("records"),
            "premissas": premissas,
            "referencias": referencias,
            "metodo": metodo,
            "equacoes": equacoes,
            "conclusao": conclusao,
            "responsavel": responsavel,
            "documento": documento,
            "preenchimento": preenchimento,
            "resultado_tecnico": resultado,
        }
        try:
            alterado, novo_id = salvar_capitulo(
                projeto, campos=campos, registro_id=escolha or None, duplicar=duplicar
            )
            alterado[CAMPO_GRAVACAO] = versao_edicao
            with tratar_conflito_de_gravacao():
                salvo = salvar_projeto(
                    alterado, motivo="Capítulo de cálculo manual ou externo salvo"
                )
        except ValueError as erro:
            st.error(str(erro))
            return
        registrar_gravacao_vista(salvo)
        for chave in list(st.session_state):
            if chave.startswith(f"externo_versao_{projeto_id}_"):
                st.session_state.pop(chave, None)
        st.session_state[f"{chave_escolha}_proxima"] = novo_id
        st.toast("Cálculo externo salvo no projeto.", icon=":material/check:")
        st.rerun()
