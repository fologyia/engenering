"""Cadastro permanente de cenários, combinações e envelopes industriais."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    contexto_sessao_projeto,
    sincronizar_projeto_ativo,
)
from components.ui import cabecalho_pagina
from core.load_cases import (
    CHAVES_CARGA,
    COMPONENTES_CARGA,
    CONDICOES_OPERACIONAIS,
    NATUREZAS_CARGA,
    TIPOS_COMBINACAO,
    calcular_envelope,
    criar_caso_carga,
    criar_combinacao_carga,
    fatores_legiveis,
)
from core.project_store import obter_projeto_ativo, salvar_projeto

st.set_page_config(
    page_title="Casos e combinações de carga",
    page_icon=":material/layers:",
    layout="wide",
)

cabecalho_pagina(
    "Casos e combinações de carga",
    "Estruture cenários operacionais, aplique fatores rastreáveis e obtenha envelopes sem perder a simultaneidade física.",
    categoria="GESTÃO INDUSTRIAL",
    icone=":material/layers:",
    cor="blue",
    ajuda_modulo="Casos de carga",
    acoes=(
        ("app_pages/central_validacao.py", "Validação", ":material/fact_check:"),
        ("app_pages/central_relatorios.py", "Relatórios", ":material/description:"),
    ),
    modulo_id="casos_carga",
)


def _limpar(valor: Any) -> Any:
    if pd.isna(valor):
        return ""
    return valor


def _salvar(projeto: Mapping[str, Any], motivo: str) -> None:
    salvo = salvar_projeto(projeto, motivo=motivo)
    st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)


sincronizar_projeto_ativo()
projeto = obter_projeto_ativo()
if projeto is None:
    st.warning("Abra um projeto permanente para cadastrar os carregamentos.")
    st.page_link(
        "app_pages/gestao_projetos.py",
        label="Abrir Gestão de projetos",
        icon=":material/folder_managed:",
    )
    st.stop()

st.subheader(f"{projeto['codigo']} · {projeto['nome']}")
st.caption(
    "Use sinais coerentes com os eixos do projeto. Os fatores devem vir da base de projeto, "
    "da especificação ou da norma aplicável; o programa não os assume como normativos."
)

casos = [item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)]
combinacoes = [
    item for item in projeto.get("combinacoes_carga", []) if isinstance(item, Mapping)
]
ativos = [item for item in casos if bool(item.get("ativo", True))]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Casos", len(casos))
m2.metric("Casos ativos", len(ativos))
m3.metric("Combinações", len(combinacoes))
m4.metric("TAGs cobertos", len({str(item.get("tag")) for item in casos if str(item.get("tag") or "").strip()}))

aba_casos, aba_combinacoes, aba_envelope = st.tabs(
    ["1. Casos de carga", "2. Combinações", "3. Envelope e registro"]
)

with aba_casos:
    st.markdown("#### Registro permanente dos casos")
    st.write(
        "Cada linha representa um cenário físico completo. Não divida forças simultâneas do mesmo cenário em casos diferentes apenas para obter máximos maiores."
    )
    linhas_casos = []
    for item in casos:
        cargas = item.get("cargas", {}) if isinstance(item.get("cargas"), Mapping) else {}
        linha = {
            "id": item.get("id", ""),
            "Ativo": bool(item.get("ativo", True)),
            "Código": item.get("codigo", ""),
            "Nome": item.get("nome", ""),
            "Condição": item.get("condicao", CONDICOES_OPERACIONAIS[0]),
            "Natureza": item.get("natureza", NATUREZAS_CARGA[0]),
            "TAG": item.get("tag", ""),
            "Origem": item.get("origem", ""),
            "Referência": item.get("referencia", ""),
            "Observações": item.get("observacoes", ""),
        }
        linha.update({chave: float(cargas.get(chave, 0.0) or 0.0) for chave in CHAVES_CARGA})
        linhas_casos.append(linha)
    colunas = [
        "id", "Ativo", "Código", "Nome", "Condição", "Natureza", "TAG",
        *CHAVES_CARGA, "Origem", "Referência", "Observações",
    ]
    quadro = pd.DataFrame(linhas_casos, columns=colunas)
    editor_casos = st.data_editor(
        quadro,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"casos_carga_editor_{projeto['id']}",
        column_config={
            "id": None,
            "Ativo": st.column_config.CheckboxColumn("Ativo"),
            "Código": st.column_config.TextColumn("Código", required=True, width="small"),
            "Nome": st.column_config.TextColumn("Nome do cenário", required=True, width="large"),
            "Condição": st.column_config.SelectboxColumn("Condição", options=list(CONDICOES_OPERACIONAIS), required=True),
            "Natureza": st.column_config.SelectboxColumn("Natureza", options=list(NATUREZAS_CARGA), required=True),
            "TAG": st.column_config.TextColumn("TAG / sistema"),
            "Fx_kN": st.column_config.NumberColumn("Fx [kN]", format="%.4g"),
            "Fy_kN": st.column_config.NumberColumn("Fy [kN]", format="%.4g"),
            "Fz_kN": st.column_config.NumberColumn("Fz [kN]", format="%.4g"),
            "Mx_kNm": st.column_config.NumberColumn("Mx [kN·m]", format="%.4g"),
            "My_kNm": st.column_config.NumberColumn("My [kN·m]", format="%.4g"),
            "Mz_kNm": st.column_config.NumberColumn("Mz [kN·m]", format="%.4g"),
            "pressao_bar": st.column_config.NumberColumn("Pressão [bar]", format="%.4g"),
            "delta_temperatura_C": st.column_config.NumberColumn("ΔT [°C]", format="%.4g"),
            "Origem": st.column_config.TextColumn("Origem física", width="large"),
            "Referência": st.column_config.TextColumn("Documento / revisão", width="large"),
            "Observações": st.column_config.TextColumn(width="large"),
        },
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        salvar_casos = st.button(
            "Salvar casos de carga",
            type="primary",
            icon=":material/save:",
            key="salvar_casos_carga",
        )
    if salvar_casos:
        novos_casos = []
        erros = []
        for indice, linha in enumerate(editor_casos.to_dict("records"), start=1):
            dados = {chave: _limpar(valor) for chave, valor in linha.items()}
            if not str(dados.get("Nome") or dados.get("Código") or "").strip():
                continue
            try:
                novos_casos.append(
                    criar_caso_carga(
                        caso_id=str(dados.get("id") or "").strip() or None,
                        codigo=str(dados.get("Código") or ""),
                        nome=str(dados.get("Nome") or dados.get("Código") or ""),
                        condicao=str(dados.get("Condição") or ""),
                        natureza=str(dados.get("Natureza") or ""),
                        tag=str(dados.get("TAG") or ""),
                        cargas={chave: dados.get(chave, 0.0) or 0.0 for chave in CHAVES_CARGA},
                        origem=str(dados.get("Origem") or ""),
                        referencia=str(dados.get("Referência") or ""),
                        observacoes=str(dados.get("Observações") or ""),
                        ativo=bool(dados.get("Ativo", True)),
                    )
                )
            except ValueError as erro:
                erros.append(f"Linha {indice}: {erro}")
        if erros:
            st.error("Revise os casos antes de salvar:\n\n" + "\n".join(f"- {item}" for item in erros))
        else:
            projeto["casos_carga"] = novos_casos
            _salvar(projeto, "Atualização dos casos de carga")
            st.success("Casos de carga gravados no projeto permanente.")
            st.rerun()

with aba_combinacoes:
    st.markdown("#### Combinações com fatores explícitos")
    if not casos:
        st.info("Salve ao menos um caso de carga antes de montar combinações.")
    else:
        if combinacoes:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Combinação": item.get("nome"),
                            "Tipo": item.get("tipo"),
                            "Parcelas": fatores_legiveis(item, casos),
                            "Estado": "Ativa" if item.get("ativo", True) else "Inativa",
                        }
                        for item in combinacoes
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        opcoes = {str(item.get("id")): str(item.get("nome")) for item in combinacoes}
        modo = st.segmented_control(
            "Operação",
            ["Nova combinação", "Editar combinação"],
            default="Nova combinação",
            selection_mode="single",
            key="casos_carga_modo_combinacao",
            persist_state="session",
        ) or "Nova combinação"
        selecionada_id = None
        selecionada: Mapping[str, Any] = {}
        if modo == "Editar combinação" and opcoes:
            if st.session_state.get("casos_carga_combinacao_selecionada") not in opcoes:
                # A seleção persistida (session) pode apontar para uma
                # combinação já excluída; sem isto, o selectbox devolveria
                # um id que não existe mais e o next() abaixo quebraria com
                # StopIteration.
                st.session_state.pop("casos_carga_combinacao_selecionada", None)
            selecionada_id = st.selectbox(
                "Combinação existente",
                list(opcoes),
                format_func=lambda valor: opcoes[valor],
                key="casos_carga_combinacao_selecionada",
                persist_state="session",
            )
            selecionada = next(item for item in combinacoes if str(item.get("id")) == selecionada_id)
        elif modo == "Editar combinação":
            st.info("Ainda não há combinações para editar.")

        if modo == "Nova combinação" or selecionada:
            fatores_atuais = selecionada.get("fatores", {}) if isinstance(selecionada.get("fatores"), Mapping) else {}
            dados_fatores = pd.DataFrame(
                [
                    {
                        "caso_id": str(caso.get("id")),
                        "Usar": str(caso.get("id")) in fatores_atuais,
                        "Código": caso.get("codigo"),
                        "Caso": caso.get("nome"),
                        "Fator": float(fatores_atuais.get(str(caso.get("id")), 1.0)),
                    }
                    for caso in casos if caso.get("ativo", True)
                ]
            )
            identidade_form = selecionada_id or "nova"
            with st.form(f"form_combinacao_{identidade_form}"):
                a, b, c = st.columns([2, 2, 1])
                nome_combinacao = a.text_input("Nome", value=str(selecionada.get("nome", "")), placeholder="OP-01 · Operação + térmico")
                tipo_combinacao = b.selectbox(
                    "Tipo",
                    list(TIPOS_COMBINACAO),
                    index=(list(TIPOS_COMBINACAO).index(selecionada.get("tipo")) if selecionada.get("tipo") in TIPOS_COMBINACAO else 0),
                )
                ativa_combinacao = c.checkbox("Ativa", value=bool(selecionada.get("ativo", True)))
                descricao_combinacao = st.text_area("Origem e finalidade da combinação", value=str(selecionada.get("descricao", "")))
                editor_fatores = st.data_editor(
                    dados_fatores,
                    hide_index=True,
                    width="stretch",
                    disabled=["caso_id", "Código", "Caso"],
                    column_config={
                        "caso_id": None,
                        "Usar": st.column_config.CheckboxColumn("Usar"),
                        "Código": st.column_config.TextColumn(width="small"),
                        "Caso": st.column_config.TextColumn(width="large"),
                        "Fator": st.column_config.NumberColumn(format="%.5g", required=True),
                    },
                    key=f"fatores_{identidade_form}",
                )
                enviar_combinacao = st.form_submit_button(
                    "Salvar combinação",
                    type="primary",
                    icon=":material/save:",
                )
            if enviar_combinacao:
                fatores = {
                    str(linha["caso_id"]): float(linha["Fator"])
                    for linha in editor_fatores.to_dict("records")
                    if bool(linha["Usar"])
                }
                try:
                    nova = criar_combinacao_carga(
                        combinacao_id=selecionada_id,
                        nome=nome_combinacao,
                        tipo=tipo_combinacao,
                        descricao=descricao_combinacao,
                        fatores=fatores,
                        ativo=ativa_combinacao,
                    )
                except ValueError as erro:
                    st.error(str(erro))
                else:
                    atualizadas = [dict(item) for item in combinacoes if str(item.get("id")) != str(selecionada_id)]
                    atualizadas.append(nova)
                    projeto["combinacoes_carga"] = atualizadas
                    _salvar(projeto, "Atualização das combinações de carga")
                    st.success("Combinação gravada no projeto.")
                    st.rerun()

        if selecionada_id:
            confirmar_exclusao = st.checkbox(
                "Confirmo a exclusão desta combinação.",
                key=f"confirmar_exclusao_combinacao_{selecionada_id}",
            )
            if st.button(
                "Excluir combinação",
                icon=":material/delete:",
                disabled=not confirmar_exclusao,
                key=f"excluir_combinacao_{selecionada_id}",
            ):
                projeto["combinacoes_carga"] = [
                    item for item in combinacoes if str(item.get("id")) != selecionada_id
                ]
                _salvar(projeto, "Exclusão de combinação de carga")
                st.rerun()

with aba_envelope:
    st.markdown("#### Envelope rastreável")
    incluir_isolados = st.toggle(
        "Incluir também os casos isolados",
        value=not bool(combinacoes),
        help="Útil para conferir cada cenário. As combinações continuam sendo avaliadas separadamente.",
        key="casos_carga_incluir_isolados",
        persist_state="session",
    )
    try:
        envelope = calcular_envelope(
            casos,
            combinacoes,
            incluir_casos_isolados=incluir_isolados,
        )
    except ValueError as erro:
        st.error(f"Não foi possível montar o envelope: {erro}")
        envelope = {"componentes": {}, "resultados": [], "total_cenarios": 0}

    if not envelope["componentes"]:
        st.info("Cadastre casos válidos para calcular o envelope.")
    else:
        st.caption(
            f"{envelope['total_cenarios']} cenário(s) avaliados. {envelope.get('aviso', '')}"
        )
        linhas_envelope = [
            {
                "Componente": item.rotulo,
                "Mínimo": envelope["componentes"][item.chave]["minimo"],
                "Máximo": envelope["componentes"][item.chave]["maximo"],
                "Governante algébrico": envelope["componentes"][item.chave]["valor_governante"],
                "Unidade": item.unidade,
                "Cenário governante": envelope["componentes"][item.chave]["cenario_governante"],
            }
            for item in COMPONENTES_CARGA
        ]
        st.dataframe(pd.DataFrame(linhas_envelope), hide_index=True, width="stretch")
        st.session_state["cargas_envelope_projeto"] = {
            "projeto_id": projeto.get("id"),
            "projeto_nome": projeto.get("nome"),
            "componentes": {
                item.chave: {
                    "rotulo": item.rotulo,
                    "unidade": item.unidade,
                    "valor_governante": envelope["componentes"][item.chave]["valor_governante"],
                    "cenario_governante": envelope["componentes"][item.chave]["cenario_governante"],
                }
                for item in COMPONENTES_CARGA
            },
        }
        grafico = pd.DataFrame(
            {
                "Componente": [item.rotulo for item in COMPONENTES_CARGA],
                "Máximo absoluto": [envelope["componentes"][item.chave]["maximo_absoluto"] for item in COMPONENTES_CARGA],
            }
        ).set_index("Componente")
        st.bar_chart(grafico)
        with st.expander("Vetores completos por combinação"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Cenário": item["nome"], "Tipo": item["tipo"], **item["vetor"]}
                        for item in envelope["resultados"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

        ids_casos = [str(item.get("id")) for item in casos if item.get("ativo", True)]
        tags = {str(item.get("tag")) for item in casos if str(item.get("tag") or "").strip()}
        ids_componentes = [
            str(item.get("id"))
            for item in projeto.get("componentes", [])
            if str(item.get("tag") or "") in tags
        ]
        referencias = sorted(
            {
                texto
                for item in casos
                for texto in (str(item.get("origem") or "").strip(), str(item.get("referencia") or "").strip())
                if texto
            }
        )
        resultados_registro = {
            "total_casos": len(casos),
            "total_combinacoes": len(combinacoes),
            "total_cenarios_envelope": envelope["total_cenarios"],
        }
        resultados_registro.update(
            {
                f"{chave.rsplit('_', 1)[0]}_envelope_{chave.rsplit('_', 1)[1]}": (
                    f"{dados['valor_governante']:.6g} {dados['unidade']} | "
                    f"{dados['cenario_governante']}"
                )
                for chave, dados in envelope["componentes"].items()
            }
        )
        registro = construir_registro_tecnico(
            modulo="Casos de carga",
            modulo_id="casos_carga",
            titulo="Casos, combinações e envelope de carregamentos",
            status="Calculado",
            resumo="Consolidação vetorial dos cenários permanentes e identificação da combinação governante por componente.",
            metodo="Soma algébrica componente a componente com fatores explícitos informados pelo usuário.",
            metodo_versao="1.0",
            entradas={
                "casos": [
                    {"id": item.get("id"), "codigo": item.get("codigo"), "cargas": item.get("cargas")}
                    for item in casos
                ],
                "combinacoes": [
                    {"id": item.get("id"), "nome": item.get("nome"), "fatores": item.get("fatores")}
                    for item in combinacoes
                ],
            },
            resultados=resultados_registro,
            premissas=[
                "Eixos, sinais e unidades são comuns a todos os casos.",
                "Os fatores foram informados pelo usuário e devem ser conferidos na base normativa.",
                "Máximos de componentes diferentes podem pertencer a combinações diferentes.",
                envelope.get("aviso", ""),
            ],
            equacoes=["R_j = Σ(γ_i · R_ij)"],
            criterios=["Preservar o vetor completo da combinação governante antes de transferir esforços para outro módulo."],
            alertas=[],
            referencias=referencias,
            conclusao=f"Envelope calculado para {envelope['total_cenarios']} cenário(s), sem atribuir aprovação normativa aos fatores.",
            responsavel=projeto.get("responsavel", ""),
            casos_carga_ids=ids_casos,
            componentes_ids=ids_componentes,
        )
        botao_registrar_calculo(
            registro,
            key=f"registrar_envelope_cargas_{projeto['id']}",
            rotulo="Registrar envelope no projeto ativo",
        )

st.divider()
st.warning(
    "O envelope é uma ferramenta de organização. Confirme casos simultâneos, fatores, sinais, "
    "condições excepcionais e critérios na documentação controlada do projeto.",
    icon=":material/gavel:",
)
