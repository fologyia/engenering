"""Central consolidada de validação do projeto industrial ativo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.project_tools import contexto_sessao_projeto, sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_checklist import resumo_checklist
from core.project_store import criar_item, obter_projeto_ativo, salvar_projeto
from core.project_validation import SEVERIDADES, validar_projeto
from core.project_workflow import avaliar_todas_transicoes

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
    acoes=(
        ("app_pages/painel_industrial.py", "Painel", ":material/dashboard:"),
        ("app_pages/central_relatorios.py", "Relatórios", ":material/description:"),
    ),
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

# O que a validação significa para o fluxo: a mesma leitura que a aba
# "Fluxo e revisões" usa para liberar ou travar cada passagem de situação.
_transicoes = avaliar_todas_transicoes(projeto, validacao=resultado)
_resumo_checklist = resumo_checklist(projeto.get("checklist", []))
with st.container(border=True):
    st.markdown(f"**Situação atual: {projeto['status']}**")
    for _item in _transicoes:
        if _item["destino"] == "Arquivado":
            continue
        if _item["permitida"]:
            st.markdown(f":material/check_circle: Pode passar para **{_item['destino']}**" + (" — " + "; ".join(_item["avisos"]) if _item["avisos"] else "."))
        else:
            st.markdown(f":material/lock: **{_item['destino']}** exige: " + "; ".join(_item["impedimentos"]))
    if _resumo_checklist["vencidos"]:
        st.markdown(
            f":material/schedule: {len(_resumo_checklist['vencidos'])} item(ns) do checklist com prazo vencido — "
            "veja a categoria **Prazos** abaixo."
        )
    st.page_link("app_pages/gestao_projetos.py", label="Mudar a situação em Fluxo e revisões", icon=":material/arrow_forward:")
st.info(resultado["aviso"], icon=":material/info:")

# Leitura por categoria: onde os achados se concentram.
_achados_todos = resultado["achados"]
if _achados_todos:
    _linhas_categoria = {}
    for _achado in _achados_todos:
        _linha = _linhas_categoria.setdefault(_achado["categoria"], {severidade: 0 for severidade in SEVERIDADES})
        _linha[_achado["severidade"]] += 1
    with st.expander("Achados por categoria", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [{"Categoria": categoria, **valores, "Total": sum(valores.values())} for categoria, valores in _linhas_categoria.items()]
            ).sort_values(["Bloqueio", "Total"], ascending=False),
            hide_index=True,
            width="stretch",
        )

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
    _ja_no_checklist = {
        str(item.get("origem_validacao"))
        for item in projeto["checklist"]
        if isinstance(item, dict) and item.get("origem_validacao")
    }
    # Achados da categoria Checklist já SÃO itens do checklist: convertê-los
    # criaria um item "Checklist aberto: Checklist aberto: ..." em cascata.
    _bloqueios_sem_item = [
        item
        for item in filtrados
        if item["severidade"] == "Bloqueio"
        and item["categoria"] not in {"Checklist", "Prazos"}
        and item["id"] not in _ja_no_checklist
    ]
    with st.container(horizontal=True):
        st.download_button(
            "Baixar achados filtrados (CSV)",
            data=tabela.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{projeto['codigo']}_validacao.csv".replace("/", "-"),
            mime="text/csv",
            icon=":material/download:",
        )
        if _bloqueios_sem_item and st.button(
            f"Converter {len(_bloqueios_sem_item)} bloqueio(s) em itens de checklist",
            icon=":material/add_task:",
            help="Cria um item crítico e aberto para cada bloqueio filtrado que ainda não está no checklist.",
        ):
            for item in _bloqueios_sem_item:
                projeto["checklist"].append(
                    criar_item(
                        item=item["titulo"],
                        categoria=item["categoria"],
                        responsavel=projeto.get("responsavel", ""),
                        prazo="",
                        estado="Aberto",
                        evidencia=item["evidencia"],
                        critico=True,
                        origem_validacao=item["id"],
                    )
                )
            salvo = salvar_projeto(
                projeto, motivo=f"{len(_bloqueios_sem_item)} bloqueio(s) da validação convertidos em checklist"
            )
            st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
            st.rerun()
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
        existente = next(
            (item for item in projeto["checklist"] if item.get("origem_validacao") == achado_id), None
        )
        if achado["categoria"] in {"Checklist", "Prazos"}:
            st.caption(
                ":material/checklist: Este achado aponta para um item que já está no checklist: "
                "trate-o na aba Checklist de Gestão de projetos."
            )
        elif existente is not None:
            st.caption(
                ":material/check_circle: Este achado já está no checklist do projeto — "
                f"estado **{existente.get('estado') or 'Aberto'}**, responsável "
                f"{existente.get('responsavel') or 'não definido'}, prazo {existente.get('prazo') or 'não definido'}."
            )
        else:
            _c1, _c2 = st.columns([2, 1])
            _responsavel = _c1.text_input(
                "Responsável pelo tratamento", value=projeto.get("responsavel", ""), key=f"resp_{achado_id}"
            )
            _prazo = _c2.date_input("Prazo", value=None, format="DD/MM/YYYY", key=f"prazo_{achado_id}")
            if st.button("Converter em item de checklist", icon=":material/add_task:"):
                projeto["checklist"].append(
                    criar_item(
                        item=achado["titulo"],
                        categoria=achado["categoria"],
                        responsavel=_responsavel,
                        prazo=_prazo.isoformat() if _prazo else "",
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
    ("9. Prazos, critérios e documentos", "Cobra prazos vencidos do checklist, critérios técnicos definidos pelo projeto e documentos de entrada recebidos e revisados."),
]
for titulo, descricao in camadas:
    with st.expander(titulo):
        st.write(descricao)

with st.container(horizontal=True, horizontal_alignment="right"):
    st.page_link("app_pages/gestao_projetos.py", label="Corrigir dados do projeto", icon=":material/edit_note:")
    st.page_link("app_pages/casos_carga.py", label="Revisar cargas", icon=":material/layers:")
    st.page_link("app_pages/central_relatorios.py", label="Montar memorial", icon=":material/description:")
