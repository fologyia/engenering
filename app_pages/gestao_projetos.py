"""Sistema permanente de projetos industriais."""

from __future__ import annotations

import json
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from components.project_tools import contexto_sessao_projeto, sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_store import (
    ProjetoPersistenciaErro,
    adicionar_registro_tecnico,
    arquivar_projeto,
    criar_item,
    criar_projeto,
    definir_projeto_ativo,
    duplicar_projeto,
    exportar_projeto,
    historico_revisoes,
    importar_projeto,
    listar_projetos,
    obter_projeto,
    restaurar_revisao,
    salvar_projeto,
)
from core.project_validation import validar_projeto

st.set_page_config(
    page_title="Projetos permanentes",
    page_icon=":material/folder_managed:",
    layout="wide",
)

cabecalho_pagina(
    "Gestão de projetos industriais",
    "Banco permanente para base de projeto, equipamentos, normas, cálculos, pendências e revisões.",
    categoria="GESTÃO INDUSTRIAL",
    icone=":material/folder_managed:",
    cor="blue",
    ajuda_modulo="Projetos permanentes",
)


def _limpar(valor: Any) -> Any:
    if pd.isna(valor):
        return ""
    if hasattr(valor, "isoformat") and not isinstance(valor, str):
        return valor.isoformat()
    return valor


def _linhas_editor(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{chave: _limpar(valor) for chave, valor in linha.items()} for linha in df.to_dict("records")]


def _salvar(documento: Mapping[str, Any], motivo: str, *, revisao: bool = False) -> dict[str, Any]:
    salvo = salvar_projeto(documento, motivo=motivo, criar_revisao=revisao)
    st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
    st.toast("Projeto salvo no banco local.", icon=":material/check_circle:")
    return salvo


@st.dialog("Novo projeto industrial")
def _dialogo_novo_projeto() -> None:
    with st.form("form_novo_projeto", border=False):
        nome = st.text_input("Nome do projeto *", placeholder="Adequação do transportador CV-204")
        c1, c2 = st.columns(2)
        codigo = c1.text_input("Código", placeholder="PRJ-2026-014")
        cliente = c2.text_input("Cliente / solicitante")
        c3, c4, c5 = st.columns(3)
        unidade = c3.text_input("Unidade industrial")
        area = c4.text_input("Área / setor")
        tag = c5.text_input("TAG principal")
        descricao = st.text_area("Descrição inicial")
        enviar = st.form_submit_button("Criar e abrir", type="primary", icon=":material/create_new_folder:")
    if enviar:
        try:
            projeto = criar_projeto(
                nome,
                codigo=codigo,
                cliente=cliente,
                unidade_industrial=unidade,
                area=area,
                tag_equipamento=tag,
                descricao=descricao,
            )
        except ProjetoPersistenciaErro as erro:
            st.error(str(erro))
            return
        st.session_state["projeto_ativo"] = contexto_sessao_projeto(projeto)
        st.rerun()


sincronizar_projeto_ativo()
mostrar_arquivados = st.toggle("Mostrar projetos arquivados", value=False)
projetos = listar_projetos(incluir_arquivados=mostrar_arquivados)
ativo_contexto = st.session_state.get("projeto_ativo")

with st.container(border=True):
    topo1, topo2 = st.columns([4, 1])
    with topo1:
        opcoes = {item["id"]: f"{item['codigo']} · {item['nome']} · Rev. {item['revisao']:02d} · {item['status']}" for item in projetos}
        ids = list(opcoes)
        indice = ids.index(ativo_contexto["id"]) if ativo_contexto and ativo_contexto.get("id") in ids else 0
        selecionado = st.selectbox(
            "Projeto do banco",
            ids,
            index=indice if ids else None,
            format_func=lambda item: opcoes.get(item, "Nenhum projeto cadastrado"),
            placeholder="Nenhum projeto cadastrado",
        )
    with topo2:
        st.write("")
        st.write("")
        if st.button("Novo projeto", icon=":material/add:", type="primary", width="stretch"):
            _dialogo_novo_projeto()
    if selecionado and (not ativo_contexto or selecionado != ativo_contexto.get("id")):
        if st.button("Abrir como projeto ativo", icon=":material/folder_open:"):
            definir_projeto_ativo(selecionado)
            st.rerun()

if not ativo_contexto:
    st.info(
        "Crie um projeto ou selecione um projeto do banco. Os cálculos registrados pelos módulos "
        "serão vinculados ao projeto ativo."
    )
    arquivo = st.file_uploader("Ou importe um projeto exportado pelo aplicativo", type=["json"])
    if arquivo and st.button("Importar projeto", icon=":material/upload:"):
        try:
            importar_projeto(arquivo.getvalue())
            st.rerun()
        except ProjetoPersistenciaErro as erro:
            st.error(str(erro))
    st.stop()

projeto = obter_projeto(ativo_contexto["id"])
if projeto is None:
    definir_projeto_ativo(None)
    st.error("O projeto ativo não foi encontrado. Selecione outro projeto.")
    st.stop()

validacao = validar_projeto(projeto)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Situação", projeto["status"])
c2.metric("Revisão controlada", f"{int(projeto['revisao']):02d}")
c3.metric("Índice documental", f"{validacao['indice_documental']}%", help=validacao["aviso"])
c4.metric("Bloqueios", validacao["contagens"]["Bloqueio"])

with st.container(horizontal=True):
    st.page_link("app_pages/central_validacao.py", label="Central de validação", icon=":material/fact_check:")
    st.page_link("app_pages/central_relatorios.py", label="Central de relatórios", icon=":material/description:")
    st.page_link("app_pages/casos_carga.py", label="Casos de carga", icon=":material/layers:")
    st.page_link("app_pages/materiais_tecnicos.py", label="Materiais técnicos", icon=":material/science:")
    pacote = exportar_projeto(projeto["id"])
    st.download_button(
        "Exportar projeto",
        data=pacote,
        file_name=f"{projeto['codigo']}_projeto.json".replace("/", "-"),
        mime="application/json",
        icon=":material/download:",
    )

abas = st.tabs([
    "Visão geral",
    "Dados e base",
    "Escopo físico",
    "Normas",
    "Registros técnicos",
    "Checklist",
    "Revisões",
    "Administração",
])

with abas[0]:
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader(projeto["nome"])
        st.caption(f"{projeto['codigo']} · {_limpar(projeto.get('unidade_industrial'))} · {_limpar(projeto.get('area'))}")
        st.write(projeto.get("descricao") or "Descrição ainda não preenchida.")
        st.markdown(f"**Objetivo:** {projeto.get('objetivo') or 'não definido'}")
        st.markdown(f"**TAG principal:** {projeto.get('tag_equipamento') or 'não definido'}")
    with col_b:
        st.subheader("Conteúdo permanente")
        st.write(f"{len(projeto['componentes'])} item(ns) no escopo físico")
        st.write(
            f"{len(projeto.get('casos_carga', []))} caso(s) e "
            f"{len(projeto.get('combinacoes_carga', []))} combinação(ões) de carga"
        )
        st.write(f"{len(projeto.get('materiais_projeto', []))} material(is) com proveniência cadastrada")
        st.write(f"{len(projeto['normas'])} referência(s) normativa(s)")
        st.write(f"{len(projeto['registros_tecnicos'])} registro(s) técnico(s)")
        st.write(f"{len(projeto['checklist'])} item(ns) de checklist")
    st.info(validacao["aviso"], icon=":material/info:")

with abas[1]:
    with st.form("dados_gerais_projeto"):
        st.subheader("Identificação e responsabilidades")
        a, b, c = st.columns(3)
        nome = a.text_input("Nome *", value=projeto.get("nome", ""))
        codigo = b.text_input("Código *", value=projeto.get("codigo", ""))
        status = c.selectbox(
            "Situação",
            ["Em elaboração", "Em verificação", "Emitido", "Suspenso", "Arquivado"],
            index=(["Em elaboração", "Em verificação", "Emitido", "Suspenso", "Arquivado"].index(projeto["status"]) if projeto["status"] in ["Em elaboração", "Em verificação", "Emitido", "Suspenso", "Arquivado"] else 0),
        )
        d, e, f = st.columns(3)
        cliente = d.text_input("Cliente / solicitante", value=projeto.get("cliente", ""))
        unidade = e.text_input("Unidade industrial", value=projeto.get("unidade_industrial", ""))
        area = f.text_input("Área / setor", value=projeto.get("area", ""))
        g, h, i = st.columns(3)
        tag = g.text_input("TAG principal", value=projeto.get("tag_equipamento", ""))
        processo = h.text_input("Processo / serviço", value=projeto.get("processo", ""))
        regime = i.text_input("Regime de operação", value=projeto.get("regime_operacao", ""))
        responsavel, verificador, aprovador = st.columns(3)
        resp = responsavel.text_input("Responsável técnico", value=projeto.get("responsavel", ""))
        verif = verificador.text_input("Verificador", value=projeto.get("verificador", ""))
        aprov = aprovador.text_input("Aprovador", value=projeto.get("aprovador", ""))
        descricao = st.text_area("Descrição", value=projeto.get("descricao", ""))
        objetivo = st.text_area("Objetivo e resultado esperado", value=projeto.get("objetivo", ""))
        st.subheader("Base de projeto")
        base = projeto.get("base_projeto", {})
        desenhos = st.text_area("Desenhos, memoriais e documentos de entrada", value=base.get("referencias_desenho", ""))
        cargas = st.text_area("Base dos carregamentos", value=base.get("base_carregamentos", ""))
        condicoes = st.text_area("Condições de operação e projeto", value=base.get("condicoes_operacao", ""))
        criterio = st.text_area("Critérios de aceitação", value=base.get("criterio_aceitacao", ""))
        vida = st.text_input("Vida requerida / horizonte de projeto", value=base.get("vida_requerida", ""))
        limitacoes = st.text_area("Limitações, exclusões e interfaces", value=base.get("limitacoes", ""))
        enviar = st.form_submit_button("Salvar dados e base", type="primary", icon=":material/save:")
    if enviar:
        projeto.update({
            "nome": nome, "codigo": codigo, "status": status, "cliente": cliente,
            "unidade_industrial": unidade, "area": area, "tag_equipamento": tag,
            "processo": processo, "regime_operacao": regime, "responsavel": resp,
            "verificador": verif, "aprovador": aprov, "descricao": descricao, "objetivo": objetivo,
        })
        projeto["base_projeto"] = {
            "referencias_desenho": desenhos, "base_carregamentos": cargas,
            "condicoes_operacao": condicoes, "criterio_aceitacao": criterio,
            "vida_requerida": vida, "limitacoes": limitacoes,
        }
        _salvar(projeto, "Atualização dos dados e da base de projeto")
        st.rerun()

with abas[2]:
    st.caption("Cadastre equipamentos, linhas, estruturas, suportes, pontos críticos ou sistemas — não apenas elementos de máquinas.")
    colunas_componentes = ["id", "tag", "descricao", "servico", "material", "fonte_material", "desenho", "criticidade"]
    df_componentes = pd.DataFrame(projeto["componentes"])
    for coluna in colunas_componentes:
        if coluna not in df_componentes:
            df_componentes[coluna] = ""
    editado = st.data_editor(
        df_componentes[colunas_componentes],
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "id": None,
            "tag": st.column_config.TextColumn("TAG", required=True),
            "descricao": st.column_config.TextColumn("Descrição", required=True, width="large"),
            "servico": st.column_config.TextColumn("Serviço / função", width="large"),
            "material": st.column_config.TextColumn("Material"),
            "fonte_material": st.column_config.TextColumn("Fonte do material", width="large"),
            "desenho": st.column_config.TextColumn("Desenho / documento"),
            "criticidade": st.column_config.SelectboxColumn("Criticidade", options=["Baixa", "Média", "Alta", "Crítica"]),
        },
        key=f"componentes_{projeto['id']}",
    )
    if st.button("Salvar escopo físico", type="primary", icon=":material/save:"):
        linhas = _linhas_editor(editado)
        projeto["componentes"] = [
            {**linha, "id": linha.get("id") or criar_item()["id"]}
            for linha in linhas if any(str(linha.get(campo, "")).strip() for campo in ("tag", "descricao", "servico"))
        ]
        _salvar(projeto, "Atualização do escopo físico")
        st.rerun()

with abas[3]:
    st.caption("Registre a referência aplicável e marque 'Conferida' somente após verificar o documento-fonte e sua edição.")
    colunas_normas = ["id", "codigo", "edicao", "escopo", "obrigatoria", "conferida", "fonte"]
    df_normas = pd.DataFrame(projeto["normas"])
    for coluna in colunas_normas:
        if coluna not in df_normas:
            df_normas[coluna] = False if coluna in {"obrigatoria", "conferida"} else ""
    editado_normas = st.data_editor(
        df_normas[colunas_normas],
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "id": None,
            "codigo": st.column_config.TextColumn("Código / título", required=True),
            "edicao": st.column_config.TextColumn("Edição / revisão"),
            "escopo": st.column_config.TextColumn("Aplicação no projeto", width="large"),
            "obrigatoria": st.column_config.CheckboxColumn("Obrigatória"),
            "conferida": st.column_config.CheckboxColumn("Conferida no original"),
            "fonte": st.column_config.TextColumn("PDF / fonte", width="large"),
        },
        key=f"normas_{projeto['id']}",
    )
    if st.button("Salvar matriz normativa", type="primary", icon=":material/save:"):
        linhas = _linhas_editor(editado_normas)
        projeto["normas"] = [
            {**linha, "id": linha.get("id") or criar_item()["id"]}
            for linha in linhas if str(linha.get("codigo", "")).strip()
        ]
        _salvar(projeto, "Atualização da matriz normativa")
        st.rerun()

with abas[4]:
    registros = projeto["registros_tecnicos"]
    if registros:
        st.dataframe(
            pd.DataFrame([
                {
                    "Módulo": item.get("modulo"), "Título": item.get("titulo"),
                    "Situação": item.get("status"), "Conclusão": item.get("conclusao"),
                    "Registrado em": item.get("criado_em"),
                }
                for item in registros
            ]),
            hide_index=True,
            width="stretch",
        )
        opcoes_registro = {item["id"]: f"{item.get('modulo')} · {item.get('titulo')}" for item in registros}
        registro_id = st.selectbox("Inspecionar registro", list(opcoes_registro), format_func=lambda valor: opcoes_registro[valor])
        registro = next(item for item in registros if item["id"] == registro_id)
        with st.expander("Dados completos do registro", expanded=False):
            st.json(registro, expanded=2)
    else:
        st.info("Ainda não há registros técnicos. Os módulos de cálculo podem gravar resultados aqui.")
    st.subheader("Adicionar verificação manual")
    with st.form("registro_manual"):
        r1, r2, r3 = st.columns(3)
        modulo = r1.text_input("Disciplina / módulo", value="Verificação industrial")
        titulo = r2.text_input("Título", placeholder="Verificação do suporte SP-104")
        status_reg = r3.selectbox("Situação", ["Pendente", "Atende", "Não atende", "Inconclusivo"])
        resumo = st.text_area("Escopo e método")
        entradas_json = st.text_area("Entradas em JSON", value='{"Documento de entrada": "A preencher"}')
        resultados_json = st.text_area("Resultados em JSON", value='{"Critério": "A preencher"}')
        premissas = st.text_area("Premissas — uma por linha")
        referencias = st.text_area("Referências — uma por linha")
        conclusao = st.text_area("Conclusão")
        adicionar = st.form_submit_button("Adicionar registro", type="primary", icon=":material/note_add:")
    if adicionar:
        try:
            entradas = json.loads(entradas_json or "{}")
            resultados = json.loads(resultados_json or "{}")
            if not isinstance(entradas, dict) or not isinstance(resultados, dict):
                raise ValueError("Entradas e resultados precisam ser objetos JSON.")
            adicionar_registro_tecnico(
                projeto["id"],
                {
                    "modulo": modulo, "titulo": titulo, "status": status_reg,
                    "resumo": resumo, "entradas": entradas, "resultados": resultados,
                    "premissas": [linha.strip() for linha in premissas.splitlines() if linha.strip()],
                    "referencias": [linha.strip() for linha in referencias.splitlines() if linha.strip()],
                    "conclusao": conclusao, "responsavel": projeto.get("responsavel", ""),
                },
            )
            st.success("Registro técnico adicionado e salvo.")
            st.rerun()
        except (json.JSONDecodeError, ValueError) as erro:
            st.error(f"Revise os campos JSON: {erro}")

with abas[5]:
    colunas_check = ["id", "item", "categoria", "responsavel", "prazo", "estado", "evidencia", "critico"]
    df_check = pd.DataFrame(projeto["checklist"])
    for coluna in colunas_check:
        if coluna not in df_check:
            df_check[coluna] = False if coluna == "critico" else ""
    editado_check = st.data_editor(
        df_check[colunas_check], num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "id": None,
            "item": st.column_config.TextColumn("Item de verificação", required=True, width="large"),
            "categoria": st.column_config.TextColumn("Categoria"),
            "responsavel": st.column_config.TextColumn("Responsável"),
            "prazo": st.column_config.TextColumn("Prazo"),
            "estado": st.column_config.SelectboxColumn("Estado", options=["Aberto", "Em andamento", "Concluído", "Não aplicável"]),
            "evidencia": st.column_config.TextColumn("Evidência / documento", width="large"),
            "critico": st.column_config.CheckboxColumn("Crítico"),
        },
        key=f"check_{projeto['id']}",
    )
    if st.button("Salvar checklist", type="primary", icon=":material/save:"):
        linhas = _linhas_editor(editado_check)
        projeto["checklist"] = [
            {**linha, "id": linha.get("id") or criar_item()["id"]}
            for linha in linhas if str(linha.get("item", "")).strip()
        ]
        _salvar(projeto, "Atualização do checklist")
        st.rerun()

with abas[6]:
    st.write(
        "Salvamentos comuns atualizam o projeto permanente. Uma **revisão controlada** cria um "
        "marco histórico restaurável para emissão ou mudança relevante de engenharia."
    )
    with st.form("nova_revisao"):
        motivo = st.text_input("Motivo da nova revisão", placeholder="Consolidação para verificação interdisciplinar")
        confirmar = st.form_submit_button("Criar revisão controlada", type="primary", icon=":material/history:")
    if confirmar:
        _salvar(projeto, motivo or "Nova revisão controlada", revisao=True)
        st.rerun()
    historico = historico_revisoes(projeto["id"])
    st.dataframe(pd.DataFrame(historico), hide_index=True, width="stretch")
    if len(historico) > 1:
        alvo = st.selectbox("Revisão histórica", [item["revisao"] for item in historico[1:]], format_func=lambda valor: f"Revisão {valor:02d}")
        confirmar_restaura = st.checkbox("Confirmo que a restauração criará uma nova revisão a partir deste marco.")
        if st.button("Restaurar como nova revisão", disabled=not confirmar_restaura, icon=":material/restore:"):
            restaurar_revisao(projeto["id"], alvo)
            st.rerun()

with abas[7]:
    st.subheader("Duplicação e arquivamento")
    nome_copia = st.text_input("Nome da cópia", value=f"{projeto['nome']} - cópia")
    if st.button("Duplicar projeto", icon=":material/content_copy:"):
        duplicar_projeto(projeto["id"], novo_nome=nome_copia)
        st.rerun()
    confirmar_arquivo = st.checkbox("Confirmo que desejo arquivar este projeto.")
    if st.button("Arquivar projeto", disabled=not confirmar_arquivo, icon=":material/archive:"):
        arquivar_projeto(projeto["id"])
        st.rerun()
    st.subheader("Importar outro projeto")
    novo_arquivo = st.file_uploader("Arquivo JSON exportado", type=["json"], key="importar_administracao")
    if novo_arquivo and st.button("Importar e abrir", icon=":material/upload:"):
        try:
            importar_projeto(novo_arquivo.getvalue())
            st.rerun()
        except ProjetoPersistenciaErro as erro:
            st.error(str(erro))
