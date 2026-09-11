"""Sistema permanente de projetos industriais."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

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
    excluir_projeto,
    exportar_projeto,
    historico_revisoes,
    importar_projeto,
    listar_projetos,
    obter_projeto,
    restaurar_revisao,
    salvar_projeto,
)
from core.project_validation import (
    diagnostico_componente,
    diagnostico_norma,
    estado_de_preenchimento,
    pendencias_de_preenchimento,
    validar_projeto,
)

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


ICONE_SEVERIDADE = {
    "Bloqueio": ":material/block:",
    "Pendência": ":material/pending:",
    "Atenção": ":material/warning:",
}


def _marca(estado: Mapping[str, Any], campo: str) -> str:
    """Sufixo do rótulo dizendo o que a falta daquele campo provoca.

    A informação já existia na Central de Validação, mas descobrir a QUAL
    campo um achado se referia obrigava a sair da tela e voltar caçando. Aqui
    ela fica ao lado do campo, no momento de preencher.
    """
    dados = estado.get(campo)
    if not dados or dados["preenchido"]:
        return ""
    return {
        "Bloqueio": " · bloqueia a emissão",
        "Pendência": " · pendência",
        "Atenção": " · recomendado",
    }.get(dados["severidade"], "")


def _avisos_por_linha(linhas: list[dict[str, Any]], diagnosticar, rotular) -> None:
    """Mostra, embaixo da tabela, o que falta em cada linha.

    A Central de Validação já apontava isso, mas só depois de sair da tela.
    Aqui o retorno chega enquanto a linha ainda está à vista.
    """
    problemas = []
    for indice, linha in enumerate(linhas, start=1):
        for severidade, mensagem in diagnosticar(linha):
            problemas.append(
                {
                    "Linha": rotular(linha, indice),
                    "Situação": severidade,
                    "O que falta": mensagem,
                }
            )
    if not problemas:
        if linhas:
            st.success(
                "Todas as linhas estão completas.", icon=":material/check_circle:"
            )
        return
    bloqueios = sum(1 for item in problemas if item["Situação"] == "Pendência")
    st.warning(
        f"{len(problemas)} ponto(s) a completar em {len(linhas)} linha(s)"
        + (f", sendo {bloqueios} pendência(s)." if bloqueios else "."),
        icon=":material/pending:",
    )
    st.dataframe(pd.DataFrame(problemas), hide_index=True, width="stretch")


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
    # Só os três campos que bloqueiam a emissão. A versão anterior pedia
    # cliente, unidade, área e TAG — que são pendências — e NÃO pedia o
    # objetivo, que é bloqueio: o projeto nascia travado e sem dizer por quê.
    st.caption(
        "Estes são os três **campos** que bloqueiam a emissão do memorial. "
        "Depois de criar, ainda faltarão o escopo físico, a matriz normativa "
        "e o primeiro cálculo registrado — o painel da aba **Dados e base** "
        "mostra o que falta e onde resolver."
    )
    with st.form("form_novo_projeto", border=False):
        nome = st.text_input(
            "Nome do projeto *", placeholder="Adequação do transportador CV-204"
        )
        codigo = st.text_input("Código *", placeholder="PRJ-2026-014")
        objetivo = st.text_area(
            "Objetivo e resultado esperado *",
            placeholder=(
                "Verificar a estrutura de suporte para a nova carga de 12 t e "
                "emitir memorial para aprovação."
            ),
            height=90,
        )
        enviar = st.form_submit_button(
            "Criar e abrir", type="primary", icon=":material/create_new_folder:"
        )
    if enviar:
        faltando = [
            rotulo
            for rotulo, valor in (
                ("nome", nome),
                ("código", codigo),
                ("objetivo", objetivo),
            )
            if not str(valor).strip()
        ]
        if faltando:
            st.error(
                "Preencha " + ", ".join(faltando) + " para o projeto não nascer "
                "bloqueado.",
                icon=":material/error:",
            )
            return
        try:
            projeto = criar_projeto(nome, codigo=codigo, objetivo=objetivo)
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
    estado = estado_de_preenchimento(projeto)
    faltando = pendencias_de_preenchimento(projeto)
    bloqueios = [item for item in faltando if item["severidade"] == "Bloqueio"]

    # Painel de progresso: antes só existia um "índice documental" no topo da
    # página, sem dizer QUAL campo o derrubava. Aqui a lista é a própria
    # ordem de trabalho.
    with st.container(border=True):
        preenchidos = sum(1 for dados in estado.values() if dados["preenchido"])
        total = len(estado)
        st.progress(
            preenchidos / total if total else 0.0,
            text=f"{preenchidos} de {total} campos do cadastro preenchidos",
        )
        # Nem todo bloqueio é campo de formulário: escopo físico, matriz
        # normativa e primeiro cálculo também travam a emissão e se resolvem
        # em outra aba. Mostrar só as pendências de campo faria o painel dizer
        # "completo" com o projeto ainda bloqueado.
        onde_resolver = {
            "Escopo físico": ("na aba **Escopo físico**, aqui mesmo", None, ""),
            "Normas": ("na aba **Normas**, aqui mesmo", None, ""),
            "Cálculos": (
                "em qualquer módulo de análise, registrando o cálculo no projeto",
                "app_pages/vigas_eixos.py",
                "Abrir Vigas e eixos",
            ),
            "Carregamentos": (
                "na página de casos de carga",
                "app_pages/casos_carga.py",
                "Abrir Casos de carga",
            ),
        }
        bloqueios_validacao = [
            achado
            for achado in validacao["achados"]
            if achado["severidade"] == "Bloqueio"
        ]
        if bloqueios_validacao:
            st.error(
                f"{len(bloqueios_validacao)} bloqueio(s) impedem a emissão do "
                "memorial.",
                icon=":material/block:",
            )
            for achado in bloqueios_validacao:
                destino, pagina, rotulo_link = onde_resolver.get(
                    achado["categoria"], ("nos campos abaixo", None, "")
                )
                st.markdown(f"- **{achado['titulo']}** — resolva {destino}.")
                if pagina:
                    st.page_link(
                        pagina, label=rotulo_link, icon=":material/arrow_forward:"
                    )
        elif faltando:
            st.warning(
                f"Nada bloqueia a emissão. Ainda faltam {len(faltando)} "
                "campo(s) para a documentação ficar completa: "
                + ", ".join(item["rotulo"] for item in faltando[:4])
                + ("…" if len(faltando) > 4 else "."),
                icon=":material/pending:",
            )
        else:
            st.success(
                "Cadastro completo e sem bloqueios: o memorial pode ser emitido.",
                icon=":material/check_circle:",
            )
            st.page_link(
                "app_pages/central_relatorios.py",
                label="Ir para a Central de relatórios",
                icon=":material/description:",
            )

    st.caption(
        "Os três blocos abaixo salvam separadamente. Comece pelo essencial — "
        "o resto pode esperar sem travar o trabalho."
    )

    # ---------------------------------------------------------------- bloco 1
    with st.container(border=True):
        st.subheader("Essencial")
        st.caption("Sem estes campos o memorial não pode ser emitido.")
        with st.form("projeto_essencial"):
            a, b = st.columns(2)
            nome = a.text_input(
                "Nome" + _marca(estado, "nome"), value=projeto.get("nome", "")
            )
            codigo = b.text_input(
                "Código" + _marca(estado, "codigo"), value=projeto.get("codigo", "")
            )
            objetivo = st.text_area(
                "Objetivo e resultado esperado" + _marca(estado, "objetivo"),
                value=projeto.get("objetivo", ""),
                height=90,
                help=(
                    "O que este projeto precisa concluir. É o que abre o "
                    "memorial e o que a conclusão retoma."
                ),
            )
            descricao = st.text_area(
                "Descrição", value=projeto.get("descricao", ""), height=90
            )
            salvar_essencial = st.form_submit_button(
                "Salvar essencial", type="primary", icon=":material/save:"
            )
        if salvar_essencial:
            projeto.update(
                {
                    "nome": nome,
                    "codigo": codigo,
                    "objetivo": objetivo,
                    "descricao": descricao,
                }
            )
            _salvar(projeto, "Atualização dos dados essenciais")
            st.rerun()

    # ---------------------------------------------------------------- bloco 2
    with st.container(border=True):
        st.subheader("Identificação e responsáveis")
        st.caption(
            "Localiza o projeto na planta e define a cadeia de elaboração, "
            "verificação e aprovação."
        )
        with st.form("projeto_identificacao"):
            a, b, c = st.columns(3)
            cliente = a.text_input(
                "Cliente / solicitante" + _marca(estado, "cliente"),
                value=projeto.get("cliente", ""),
            )
            unidade = b.text_input(
                "Unidade industrial" + _marca(estado, "unidade_industrial"),
                value=projeto.get("unidade_industrial", ""),
            )
            area = c.text_input(
                "Área / setor" + _marca(estado, "area"), value=projeto.get("area", "")
            )
            d, e, f = st.columns(3)
            tag = d.text_input(
                "TAG principal" + _marca(estado, "tag_equipamento"),
                value=projeto.get("tag_equipamento", ""),
            )
            processo = e.text_input(
                "Processo / serviço", value=projeto.get("processo", "")
            )
            regime = f.text_input(
                "Regime de operação", value=projeto.get("regime_operacao", "")
            )
            g, h, i = st.columns(3)
            resp = g.text_input(
                "Responsável técnico" + _marca(estado, "responsavel"),
                value=projeto.get("responsavel", ""),
            )
            verif = h.text_input(
                "Verificador" + _marca(estado, "verificador"),
                value=projeto.get("verificador", ""),
            )
            aprov = i.text_input(
                "Aprovador" + _marca(estado, "aprovador"),
                value=projeto.get("aprovador", ""),
            )
            situacoes = [
                "Em elaboração",
                "Em verificação",
                "Emitido",
                "Suspenso",
                "Arquivado",
            ]
            status = st.selectbox(
                "Situação",
                situacoes,
                index=situacoes.index(projeto["status"])
                if projeto["status"] in situacoes
                else 0,
            )
            salvar_identificacao = st.form_submit_button(
                "Salvar identificação", type="primary", icon=":material/save:"
            )
        if salvar_identificacao:
            projeto.update(
                {
                    "cliente": cliente,
                    "unidade_industrial": unidade,
                    "area": area,
                    "tag_equipamento": tag,
                    "processo": processo,
                    "regime_operacao": regime,
                    "responsavel": resp,
                    "verificador": verif,
                    "aprovador": aprov,
                    "status": status,
                }
            )
            _salvar(projeto, "Atualização da identificação e das responsabilidades")
            st.rerun()

    # ---------------------------------------------------------------- bloco 3
    base = projeto.get("base_projeto", {})
    faltando_base = [item for item in faltando if item.get("grupo") == "base"]
    with st.expander(
        "Base de projeto"
        + (f" — {len(faltando_base)} campo(s) por preencher" if faltando_base else " — completa"),
        expanded=bool(faltando_base) and not bloqueios,
    ):
        st.caption(
            "As premissas que o memorial cita e que a conclusão limita. É o "
            "que separa um cálculo verificável de um número solto."
        )
        with st.form("projeto_base"):
            desenhos = st.text_area(
                "Desenhos, memoriais e documentos de entrada"
                + _marca(estado, "referencias_desenho"),
                value=base.get("referencias_desenho", ""),
                height=80,
                placeholder="Desenho DE-1042 rev. C; memorial MC-08 rev. 2",
            )
            cargas = st.text_area(
                "Base dos carregamentos" + _marca(estado, "base_carregamentos"),
                value=base.get("base_carregamentos", ""),
                height=80,
                placeholder="NBR 6120 para sobrecarga; peso do equipamento por folha de dados",
            )
            condicoes = st.text_area(
                "Condições de operação e projeto" + _marca(estado, "condicoes_operacao"),
                value=base.get("condicoes_operacao", ""),
                height=80,
                placeholder="Ambiente externo, temperatura de 0 a 45 °C, operação contínua",
            )
            criterio = st.text_area(
                "Critérios de aceitação" + _marca(estado, "criterio_aceitacao"),
                value=base.get("criterio_aceitacao", ""),
                height=80,
                placeholder="NBR 8800 para ELU e ELS; flecha limitada a L/350",
            )
            limitacoes = st.text_area(
                "Limitações, exclusões e interfaces" + _marca(estado, "limitacoes"),
                value=base.get("limitacoes", ""),
                height=80,
                placeholder="Fundação e ligações soldadas fora do escopo",
            )
            vida = st.text_input(
                "Vida requerida / horizonte de projeto",
                value=base.get("vida_requerida", ""),
                placeholder="20 anos",
            )
            salvar_base = st.form_submit_button(
                "Salvar base de projeto", type="primary", icon=":material/save:"
            )
        if salvar_base:
            projeto["base_projeto"] = {
                "referencias_desenho": desenhos,
                "base_carregamentos": cargas,
                "condicoes_operacao": condicoes,
                "criterio_aceitacao": criterio,
                "vida_requerida": vida,
                "limitacoes": limitacoes,
            }
            _salvar(projeto, "Atualização da base de projeto")
            st.rerun()

with abas[2]:
    st.caption(
        "Cadastre equipamentos, linhas, estruturas, suportes, pontos críticos "
        "ou sistemas — não apenas elementos de máquinas."
    )
    with st.container(border=True):
        st.markdown("**Como preencher uma linha**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "TAG": "CV-204-SUP-01",
                        "Descrição": "Suporte do transportador CV-204",
                        "Serviço / função": "Sustenta o trecho elevado entre os pórticos P3 e P4",
                        "Material": "ASTM A572 Gr. 50",
                        "Fonte do material": "Certificado do lote MTR 88213",
                        "Desenho": "DE-1042 rev. C",
                        "Criticidade": "Alta",
                    }
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "TAG, descrição e material são cobrados pela validação. A fonte do "
            "material é o que separa um valor de catálogo de um dado do lote."
        )
    if not projeto["componentes"] and st.button(
        "Começar com esta linha de exemplo",
        icon=":material/playlist_add:",
        key="semear_componente",
        help="Cria a linha acima para você editar, em vez de partir da tabela vazia.",
    ):
        projeto["componentes"] = [
            {
                **criar_item(),
                "tag": "CV-204-SUP-01",
                "descricao": "Suporte do transportador CV-204",
                "servico": "Sustenta o trecho elevado entre os pórticos P3 e P4",
                "material": "ASTM A572 Gr. 50",
                "fonte_material": "Certificado do lote MTR 88213",
                "desenho": "DE-1042 rev. C",
                "criticidade": "Alta",
            }
        ]
        _salvar(projeto, "Linha de exemplo do escopo físico")
        st.rerun()
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
    _avisos_por_linha(
        _linhas_editor(editado),
        diagnostico_componente,
        lambda linha, indice: str(linha.get("tag") or linha.get("descricao") or f"linha {indice}"),
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
    st.caption(
        "Registre a referência aplicável e marque 'Conferida' somente após "
        "verificar o documento-fonte e sua edição."
    )
    with st.container(border=True):
        st.markdown("**Como preencher uma linha**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Código / título": "ABNT NBR 8800",
                        "Edição": "2024",
                        "Aplicação no projeto": "Dimensionamento das barras e das ligações da estrutura de suporte",
                        "Obrigatória": True,
                        "Conferida": True,
                        "PDF / fonte": "normas_pdf/NBR8800-2024.pdf",
                    }
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "A aplicação no projeto é o campo que o memorial cita: escreva o "
            "que a norma governa aqui, não o título dela outra vez."
        )
    if not projeto["normas"] and st.button(
        "Começar com esta linha de exemplo",
        icon=":material/playlist_add:",
        key="semear_norma",
    ):
        projeto["normas"] = [
            {
                **criar_item(),
                "codigo": "ABNT NBR 8800",
                "edicao": "2024",
                "escopo": "Dimensionamento das barras e das ligações da estrutura de suporte",
                "obrigatoria": True,
                "conferida": False,
                "fonte": "",
            }
        ]
        _salvar(projeto, "Linha de exemplo da matriz normativa")
        st.rerun()
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
    _avisos_por_linha(
        _linhas_editor(editado_normas),
        diagnostico_norma,
        lambda linha, indice: str(linha.get("codigo") or f"linha {indice}"),
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
    st.subheader("Duplicação, arquivamento e exclusão")
    nome_copia = st.text_input("Nome da cópia", value=f"{projeto['nome']} - cópia")
    if st.button("Duplicar projeto", icon=":material/content_copy:"):
        duplicar_projeto(projeto["id"], novo_nome=nome_copia)
        st.rerun()
    confirmar_arquivo = st.checkbox("Confirmo que desejo arquivar este projeto.")
    if st.button("Arquivar projeto", disabled=not confirmar_arquivo, icon=":material/archive:"):
        arquivar_projeto(projeto["id"])
        st.rerun()
    if projeto.get("status") == "Arquivado" and st.button("Desarquivar projeto", icon=":material/unarchive:"):
        arquivar_projeto(projeto["id"], arquivado=False)
        st.rerun()

    st.subheader("Exclusão definitiva")
    st.warning(
        "Excluir apaga o projeto, todos os registros técnicos e o histórico de revisões. "
        "Não há como recuperar; se houver dúvida, arquive ou exporte o JSON antes."
    )
    codigo_confirmacao = st.text_input(
        f"Digite o código {projeto['codigo']} para confirmar a exclusão",
        key=f"confirmar_exclusao_{projeto['id']}",
        placeholder=projeto["codigo"],
    )
    if st.button(
        "Excluir projeto definitivamente",
        type="primary",
        disabled=codigo_confirmacao.strip() != projeto["codigo"],
        icon=":material/delete_forever:",
    ):
        excluir_projeto(projeto["id"])
        st.session_state["projeto_ativo"] = None
        st.success(f"Projeto {projeto['codigo']} · {projeto['nome']} excluído.")
        st.rerun()
    st.subheader("Importar outro projeto")
    novo_arquivo = st.file_uploader("Arquivo JSON exportado", type=["json"], key="importar_administracao")
    if novo_arquivo and st.button("Importar e abrir", icon=":material/upload:"):
        try:
            importar_projeto(novo_arquivo.getvalue())
            st.rerun()
        except ProjetoPersistenciaErro as erro:
            st.error(str(erro))
