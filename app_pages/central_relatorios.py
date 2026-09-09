"""Montagem modular de memoriais Word e PDF."""

from __future__ import annotations

from datetime import date
import re

import pandas as pd
import streamlit as st

from components.project_tools import sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_report import (
    SECOES_RELATORIO,
    gerar_relatorio_industrial_pdf,
    gerar_relatorio_industrial_word,
    montar_modelo_relatorio,
    avaliar_integridade_registro,
)
from core.project_store import obter_projeto_ativo, salvar_projeto


PERFIS = {
    "Memorial industrial completo": list(SECOES_RELATORIO),
    "Resumo executivo": ["escopo", "carregamentos", "componentes", "materiais", "normas", "sensibilidade", "validacao", "conclusao"],
    "Dossiê de validação": ["base", "carregamentos", "materiais", "normas", "plano_calculo", "registros", "sensibilidade", "validacao", "checklist", "conclusao"],
    "Memorial de cálculos": ["escopo", "base", "carregamentos", "materiais", "normas", "plano_calculo", "registros", "sensibilidade", "conclusao"],
}

st.set_page_config(
    page_title="Central de relatórios",
    page_icon=":material/description:",
    layout="wide",
)

cabecalho_pagina(
    "Central de relatórios",
    "Monte um memorial por seções, selecione registros técnicos e emita Word editável ou PDF controlado.",
    categoria="DOCUMENTAÇÃO INDUSTRIAL",
    icone=":material/description:",
    cor="blue",
    ajuda_modulo="Central de relatórios",
    acoes=(("app_pages/central_validacao.py", "Validação", ":material/fact_check:"),),
)

sincronizar_projeto_ativo()
projeto = obter_projeto_ativo()
if projeto is None:
    st.warning("Abra um projeto permanente para montar o memorial.")
    st.page_link("app_pages/gestao_projetos.py", label="Abrir Gestão de projetos", icon=":material/folder_managed:")
    st.stop()

st.subheader(f"{projeto['codigo']} · {projeto['nome']}")
st.caption(
    "O Word é indicado para revisão, comentários e assinatura. O PDF preserva o layout para distribuição. "
    "Ambos são gerados a partir do mesmo conjunto de dados."
)

perfil_padrao = projeto.get("configuracao_relatorio", {}).get("perfil", "Memorial industrial completo")
if perfil_padrao not in PERFIS:
    perfil_padrao = "Memorial industrial completo"
perfil = st.segmented_control(
    "Perfil documental",
    list(PERFIS),
    default=perfil_padrao,
    selection_mode="single",
    help="O perfil sugere seções; você pode ajustar a seleção antes de gerar.",
) or perfil_padrao

chave_perfil = f"perfil_relatorio_anterior_{projeto['id']}"
chave_secoes = f"secoes_relatorio_{projeto['id']}"
if st.session_state.get(chave_perfil) != perfil:
    st.session_state[chave_secoes] = PERFIS[perfil]
    st.session_state[chave_perfil] = perfil

selecoes = st.multiselect(
    "Seções incluídas",
    options=list(SECOES_RELATORIO),
    format_func=lambda chave: SECOES_RELATORIO[chave],
    key=chave_secoes,
)

registros = projeto.get("registros_tecnicos", [])
config_salva = projeto.get("configuracao_relatorio", {})
ordem_salva = {str(valor): indice for indice, valor in enumerate(config_salva.get("ordem_registros", []))}
linhas_composicao = []
for indice, item in enumerate(registros, start=1):
    integridade = avaliar_integridade_registro(item)
    linhas_composicao.append(
        {
            "id": item["id"],
            "Incluir": item["id"] in config_salva.get("registros_incluidos", [registro["id"] for registro in registros]),
            "Ordem": ordem_salva.get(item["id"], indice - 1) + 1,
            "Módulo": item.get("modulo", "Módulo"),
            "Registro": item.get("titulo", "Registro"),
            "Situação": item.get("status", "Pendente"),
            "Integridade (%)": integridade["percentual"],
            "Contrato": f"{integridade['contrato']} · assinatura {integridade['assinatura'].lower()}",
            "Lacunas": ", ".join(integridade["faltantes"]),
        }
    )
st.markdown("##### Composição e ordem dos capítulos")
if linhas_composicao:
    composicao = st.data_editor(
        pd.DataFrame(linhas_composicao),
        hide_index=True,
        width="stretch",
        disabled=["id", "Módulo", "Registro", "Situação", "Integridade (%)", "Contrato", "Lacunas"],
        column_config={
            "id": None,
            "Incluir": st.column_config.CheckboxColumn("Incluir"),
            "Ordem": st.column_config.NumberColumn("Ordem", min_value=1, max_value=max(1, len(registros)), step=1, required=True),
            "Módulo": st.column_config.TextColumn(width="medium"),
            "Registro": st.column_config.TextColumn(width="large"),
            "Integridade (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%"),
            "Contrato": st.column_config.TextColumn(width="medium"),
            "Lacunas": st.column_config.TextColumn(width="large"),
        },
        key=f"composicao_relatorio_{projeto['id']}",
    )
    linhas_selecionadas = composicao[composicao["Incluir"]].sort_values(["Ordem", "Módulo", "Registro"])
    ids_registros = linhas_selecionadas["id"].astype(str).tolist()
else:
    ids_registros = []
if not registros:
    st.info("O projeto ainda não possui registros técnicos. O relatório pode ser emitido como base documental, com essa pendência sinalizada.")

with st.expander("Identificação e controle do documento", expanded=True):
    c1, c2 = st.columns([2, 1])
    titulo = c1.text_input("Título", value="Memorial técnico do projeto industrial")
    subtitulo = c1.text_input("Subtítulo", value="Base de projeto, registros técnicos e central de validação")
    codigo_documento = c2.text_input("Código do documento", value=projeto["codigo"])
    revisao = c2.text_input("Revisão", value=f"{int(projeto.get('revisao', 0)):02d}")
    d1, d2, d3 = st.columns(3)
    responsavel = d1.text_input("Elaborado por", value=projeto.get("responsavel", ""))
    verificador = d2.text_input("Verificado por", value=projeto.get("verificador", ""))
    aprovador = d3.text_input("Aprovado por", value=projeto.get("aprovador", ""))
    e1, e2 = st.columns(2)
    situacao = e1.selectbox("Situação do documento", ["Para revisão", "Para aprovação", "Emitido", "Preliminar"])
    emissao = e2.date_input("Data de emissão", value=date.today(), format="DD/MM/YYYY")

metadata = {
    "titulo": titulo,
    "subtitulo": subtitulo,
    "codigo": codigo_documento,
    "revisao": revisao,
    "responsavel": responsavel,
    "verificador": verificador,
    "aprovador": aprovador,
    "situacao": situacao,
    "emissao": emissao.strftime("%d/%m/%Y"),
}
modelo = montar_modelo_relatorio(
    projeto,
    secoes_incluidas=selecoes,
    registros_ids=ids_registros,
    metadata_extra=metadata,
)

st.subheader("Prévia da composição")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Seções", len(selecoes))
m2.metric("Registros anexados", len(ids_registros))
m3.metric(
    "Integridade média",
    f"{round(sum(avaliar_integridade_registro(item)['percentual'] for item in modelo['registros']) / max(len(modelo['registros']), 1))}%",
)
m4.metric("Prontidão", modelo["validacao"]["prontidao"])
st.caption(f"Snapshot desta composição: `{modelo['snapshot_hash']}`")
incompletos = [item for item in modelo["registros"] if avaliar_integridade_registro(item)["percentual"] < 100]
if incompletos:
    st.warning(f"{len(incompletos)} registro(s) selecionado(s) possuem lacunas estruturais. Consulte a coluna 'Lacunas' antes da emissão.")
with st.expander("Sumário planejado"):
    st.markdown("\n".join(f"- {secao['titulo']}" for secao in modelo["secoes"]))
    st.markdown(f"- {modelo['numero_integracao']}. Integração com outras partes do projeto")
    st.markdown(f"- {modelo['numero_aprovacoes']}. Aprovações")
    st.markdown("- Apêndice A — quadro consolidado")

if not selecoes:
    st.warning("Selecione ao menos uma seção antes de gerar o documento.")

chave_arquivos = f"relatorio_gerado_{projeto['id']}"
if st.button(
    "Gerar Word e PDF",
    type="primary",
    icon=":material/docs:",
    disabled=not bool(selecoes),
):
    with st.spinner("Montando o memorial e paginando os documentos..."):
        try:
            word = gerar_relatorio_industrial_word(
                projeto,
                secoes_incluidas=selecoes,
                registros_ids=ids_registros,
                metadata_extra=metadata,
            )
            pdf = gerar_relatorio_industrial_pdf(
                projeto,
                secoes_incluidas=selecoes,
                registros_ids=ids_registros,
                metadata_extra=metadata,
            )
        except Exception as erro:
            st.exception(erro)
        else:
            st.session_state[chave_arquivos] = {
                "word": word,
                "pdf": pdf,
                "metadata": metadata,
                "perfil": perfil,
                "secoes": selecoes,
                "registros": ids_registros,
                "snapshot_hash": modelo["snapshot_hash"],
            }
            configuracao = dict(projeto.get("configuracao_relatorio", {}))
            configuracao.update(
                {
                    "perfil": perfil,
                    "secoes": list(selecoes),
                    "ordem_registros": list(ids_registros),
                    "registros_incluidos": list(ids_registros),
                    "ultimo_snapshot_hash": modelo["snapshot_hash"],
                    "ultima_emissao": metadata["emissao"],
                }
            )
            projeto["configuracao_relatorio"] = configuracao
            salvar_projeto(projeto, motivo="Configuração da central de relatórios")
            st.success("Documentos gerados a partir da mesma revisão de dados.")

arquivos = st.session_state.get(chave_arquivos)
if arquivos:
    nome_base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(codigo_documento)).strip("_") or "memorial_industrial"
    d1, d2 = st.columns(2)
    d1.download_button(
        "Baixar Word editável",
        data=arquivos["word"],
        file_name=f"{nome_base}_R{revisao}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/download:",
        type="primary",
        width="stretch",
    )
    d2.download_button(
        "Baixar PDF para distribuição",
        data=arquivos["pdf"],
        file_name=f"{nome_base}_R{revisao}.pdf",
        mime="application/pdf",
        icon=":material/picture_as_pdf:",
        width="stretch",
    )
    st.caption(
        f"Arquivos do snapshot {arquivos.get('snapshot_hash', '')[:16]}… . "
        "Se alterar dados, seleção ou revisão, gere novamente antes de baixar."
    )

st.divider()
st.warning(
    "A geração do relatório organiza os dados e achados disponíveis. Ela não substitui a conferência dos "
    "cálculos, das normas aplicáveis, dos documentos de entrada nem a aprovação do responsável técnico.",
    icon=":material/gavel:",
)
