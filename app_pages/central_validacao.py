"""Central consolidada de validação do projeto industrial ativo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.project_tools import contexto_sessao_projeto, sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_store import criar_item, obter_projeto_ativo, salvar_projeto
from core.project_validation import SEVERIDADES, validar_projeto

st.set_page_config(
    page_title="Central de validação",
    page_icon=":material/fact_check:",
    layout="wide",
)

cabecalho_pagina(
    "Central de validação",
    "Uma fila única para bloqueios técnicos, lacunas documentais, normas e pendências de emissão.",
    categoria="CONTROLE INDUSTRIAL",
    icone=":material/fact_check:",
    cor="orange",
    ajuda_modulo="Central de validação",
    acoes=(("app_pages/central_relatorios.py", "Relatórios", ":material/description:"),),
)

sincronizar_projeto_ativo()
projeto = obter_projeto_ativo()
if projeto is None:
    st.warning("Abra um projeto permanente para executar a validação consolidada.")
    st.page_link(
        "app_pages/gestao_projetos.py",
        label="Abrir Gestão de projetos",
        icon=":material/folder_managed:",
    )
    st.stop()

resultado = validar_projeto(projeto)
contagens = resultado["contagens"]

st.subheader(f"{projeto['codigo']} · {projeto['nome']}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Prontidão", resultado["prontidao"])
c2.metric("Índice documental", f"{resultado['indice_documental']}%", help=resultado["aviso"])
c3.metric("Bloqueios", contagens["Bloqueio"], border=True)
c4.metric("Pendências", contagens["Pendência"], border=True)
c5.metric("Atenções", contagens["Atenção"], border=True)

if contagens["Bloqueio"]:
    st.error(
        "Existem bloqueios em aberto. O memorial pode ser gerado para revisão, mas não deve ser tratado como liberado."
    )
elif contagens["Pendência"]:
    st.warning("Não há bloqueios automáticos, porém o projeto ainda está em consolidação.")
else:
    st.success("Não há bloqueios automáticos. Mantenha a verificação independente antes da emissão.")
st.info(resultado["aviso"], icon=":material/info:")

achados = resultado["achados"]
categorias = sorted({item["categoria"] for item in achados})
f1, f2, f3 = st.columns([2, 2, 3])
severidades = f1.multiselect("Severidade", list(SEVERIDADES), default=list(SEVERIDADES))
categorias_sel = f2.multiselect("Categoria", categorias, default=categorias)
busca = f3.text_input("Buscar", placeholder="material, norma, carregamento, checklist...")

filtrados = [
    item for item in achados
    if item["severidade"] in severidades
    and item["categoria"] in categorias_sel
    and (
        not busca.strip()
        or busca.lower() in " ".join(str(valor) for valor in item.values()).lower()
    )
]

if filtrados:
    tabela = pd.DataFrame([
        {
            "ID": item["id"],
            "Severidade": item["severidade"],
            "Categoria": item["categoria"],
            "Módulo": item["modulo"],
            "Achado": item["titulo"],
            "Detalhe": item["detalhe"],
            "Ação recomendada": item["recomendacao"],
        }
        for item in filtrados
    ])
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        column_config={
            "Severidade": st.column_config.TextColumn(width="small"),
            "Achado": st.column_config.TextColumn(width="large"),
            "Detalhe": st.column_config.TextColumn(width="large"),
            "Ação recomendada": st.column_config.TextColumn(width="large"),
        },
    )
    mapa = {item["id"]: item for item in filtrados}
    achado_id = st.selectbox(
        "Detalhar e tratar achado",
        list(mapa),
        format_func=lambda valor: f"{mapa[valor]['severidade']} · {valor} · {mapa[valor]['titulo']}",
    )
    achado = mapa[achado_id]
    with st.container(border=True):
        st.subheader(achado["titulo"])
        st.caption(f"{achado['id']} · {achado['categoria']} · {achado['modulo']}")
        st.write(achado["detalhe"])
        st.markdown(f"**Ação recomendada:** {achado['recomendacao']}")
        if achado.get("evidencia"):
            st.code(achado["evidencia"], language=None)
        existente = any(item.get("origem_validacao") == achado_id for item in projeto["checklist"])
        if existente:
            st.caption(":material/check_circle: Este achado já está vinculado ao checklist do projeto.")
        elif st.button("Converter em item de checklist", icon=":material/add_task:"):
            projeto["checklist"].append(
                criar_item(
                    item=achado["titulo"],
                    categoria=achado["categoria"],
                    responsavel="",
                    prazo="",
                    estado="Aberto",
                    evidencia=achado["evidencia"],
                    critico=achado["severidade"] == "Bloqueio",
                    origem_validacao=achado_id,
                )
            )
            salvo = salvar_projeto(projeto, motivo=f"Achado {achado_id} incluído no checklist")
            st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
            st.rerun()
else:
    st.success("Nenhum achado corresponde aos filtros selecionados.")

st.divider()
st.subheader("Leitura por camada")
camadas = [
    ("1. Identificação e responsabilidades", "Define quem, onde, qual equipamento e com qual objetivo."),
    ("2. Base de projeto", "Confere documentos de entrada, carregamentos, condições de operação, critérios e limitações."),
    ("3. Casos e combinações de carga", "Confere vetores não nulos, TAG, origem, referências internas, fatores e consistência do envelope."),
    ("4. Escopo físico e materiais", "Verifica TAGs, vínculos, condição de fornecimento, lote, fonte, aplicabilidade e confiança das propriedades."),
    ("5. Matriz normativa", "Exige referência, edição, escopo e conferência no documento-fonte."),
    ("6. Registros e contratos técnicos", "Avalia entradas, resultados, versão do módulo, assinatura, premissas, alertas, conclusão e critérios conhecidos."),
    ("7. Sensibilidade e incerteza", "Sinaliza risco probabilístico relevante e exige que faixas, distribuições e método permaneçam documentados."),
    ("8. Checklist de emissão", "Expõe itens abertos, responsáveis, evidências e pendências críticas."),
]
for titulo, descricao in camadas:
    with st.expander(titulo):
        st.write(descricao)

with st.container(horizontal=True, horizontal_alignment="right"):
    st.page_link("app_pages/gestao_projetos.py", label="Corrigir dados do projeto", icon=":material/edit_note:")
    st.page_link("app_pages/casos_carga.py", label="Revisar cargas", icon=":material/layers:")
    st.page_link("app_pages/central_relatorios.py", label="Montar memorial", icon=":material/description:")
