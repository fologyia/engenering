"""Sistema permanente de projetos industriais."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.project_tools import contexto_sessao_projeto, sincronizar_projeto_ativo
from components.ui import cabecalho_pagina
from core.project_checklist import (
    ESTADOS_CHECKLIST,
    interpretar_prazo,
    resumo_checklist,
)
from core.project_criteria import (
    UNIDADES_PROJETO,
    avaliar_criterios_projeto,
    normalizar_criterios_projeto,
    resumo_criterios_projeto,
)
from core.project_diff import comparar_documentos, resumir_diferencas
from core.project_portfolio import proximos_passos, resumir_projeto
from core.project_records import (
    STATUS_SUPERADO,
    dependentes_do_registro,
    remover_registro,
    resumir_registros,
    superar_registro,
)
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
    historico_eventos,
    historico_revisoes,
    importar_projeto,
    listar_projetos,
    obter_projeto,
    obter_revisao,
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
from core.project_workflow import (
    ARQUIVADO,
    DESCRICOES,
    SUSPENSO,
    avaliar_todas_transicoes,
    situacao_atual,
)

st.set_page_config(
    page_title="Projetos permanentes",
    page_icon=":material/folder_managed:",
    layout="wide",
)

cabecalho_pagina(
    "Gestão de projetos industriais",
    "Banco permanente para base de projeto, critérios, equipamentos, documentos, normas, cálculos, pendências e revisões.",
    categoria="GESTÃO INDUSTRIAL",
    icone=":material/folder_managed:",
    cor="blue",
    ajuda_modulo="Projetos permanentes",
    acoes=(("app_pages/painel_industrial.py", "Painel da carteira", ":material/dashboard:"),),
)


ICONE_SEVERIDADE = {
    "Bloqueio": ":material/block:",
    "Pendência": ":material/pending:",
    "Atenção": ":material/warning:",
}

TIPOS_DOCUMENTO = (
    "Desenho",
    "Folha de dados",
    "Certificado de material",
    "Memorial ou relatório anterior",
    "Especificação ou norma do cliente",
    "Relatório de inspeção",
    "Outro",
)
SITUACOES_DOCUMENTO = ("Vigente", "Aguardando recebimento", "Superado")

ROTULOS_EVENTO = {
    "criacao": "Criação",
    "salvamento": "Salvamento",
    "revisao": "Revisão controlada",
    "situacao": "Situação",
    "registro": "Registro técnico",
    "emissao": "Emissão",
    "administracao": "Administração",
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
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "isoformat") and not isinstance(valor, str):
        return valor.isoformat()
    return valor


def _linhas_editor(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{chave: _limpar(valor) for chave, valor in linha.items()} for linha in df.to_dict("records")]


def _mesclar_linhas(
    originais: Sequence[Mapping[str, Any]],
    editadas: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Devolve as linhas editadas sem perder campos que o editor não mostra.

    A tabela do escopo físico não exibe ``material_id`` (vem de Materiais
    técnicos) e a do checklist não exibe ``origem_validacao`` (vem da Central
    de validação). Salvar só as colunas visíveis apagava esses vínculos em
    silêncio: o material "desvinculava" e o achado voltava a pedir conversão.
    """
    por_id = {
        str(item.get("id")): dict(item)
        for item in originais
        if isinstance(item, Mapping) and str(item.get("id") or "").strip()
    }
    resultado = []
    for linha in editadas:
        base = por_id.get(str(linha.get("id") or ""), {})
        combinado = {**base, **dict(linha)}
        combinado["id"] = str(linha.get("id") or "").strip() or criar_item()["id"]
        resultado.append(combinado)
    return resultado


def _salvar(documento: Mapping[str, Any], motivo: str, *, revisao: bool = False, tipo_evento: str = "") -> dict[str, Any]:
    salvo = salvar_projeto(documento, motivo=motivo, criar_revisao=revisao, tipo_evento=tipo_evento)
    st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
    st.toast("Projeto salvo no banco local.", icon=":material/check_circle:")
    return salvo


def _data_curta(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    try:
        return datetime.fromisoformat(texto).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return texto


def _numero_ou_none(valor: Any) -> float | None:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


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
    st.page_link(
        "app_pages/painel_industrial.py",
        label="Ver a carteira inteira no Painel industrial",
        icon=":material/dashboard:",
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
resumo = resumir_projeto(projeto, validacao=validacao)
c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
c1.metric("Situação", projeto["status"], help=validacao["prontidao"])
c2.metric("Revisão", f"{int(projeto['revisao']):02d}")
c3.metric("Índice documental", f"{validacao['indice_documental']}%", help=validacao["aviso"])
c4.metric("Bloqueios", validacao["contagens"]["Bloqueio"])
c5.metric(
    "Prazos vencidos",
    resumo["checklist_vencidos"],
    help="Itens do checklist abertos com prazo anterior a hoje.",
)

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
    "Critérios",
    "Escopo físico",
    "Normas",
    "Documentos",
    "Registros técnicos",
    "Checklist",
    "Fluxo e revisões",
    "Administração",
])

# ============================================================== Visão geral
with abas[0]:
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader(projeto["nome"])
        st.caption(f"{projeto['codigo']} · {_limpar(projeto.get('unidade_industrial'))} · {_limpar(projeto.get('area'))}")
        st.write(projeto.get("descricao") or "Descrição ainda não preenchida.")
        st.markdown(f"**Objetivo:** {projeto.get('objetivo') or 'não definido'}")
        st.markdown(f"**TAG principal:** {projeto.get('tag_equipamento') or 'não definido'}")
        st.markdown(
            f"**Responsável:** {projeto.get('responsavel') or '—'} · "
            f"**Verificador:** {projeto.get('verificador') or '—'} · "
            f"**Aprovador:** {projeto.get('aprovador') or '—'}"
        )
    with col_b:
        with st.container(border=True):
            st.markdown(f"##### Situação: {situacao_atual(projeto)}")
            st.caption(DESCRICOES.get(situacao_atual(projeto), ""))
            transicoes = avaliar_todas_transicoes(projeto, validacao=validacao)
            liberadas = [item["destino"] for item in transicoes if item["permitida"]]
            travadas = [item for item in transicoes if not item["permitida"] and item["destino"] != ARQUIVADO]
            if liberadas:
                st.markdown("Pode avançar para: " + ", ".join(f"**{destino}**" for destino in liberadas))
            for item in travadas:
                st.markdown(
                    f":material/lock: **{item['destino']}** exige: "
                    + "; ".join(item["impedimentos"])
                )
            st.caption("A mudança de situação é feita na aba **Fluxo e revisões**.")

    # Painel de leitura: cada cartão responde a uma pergunta de gestão —
    # posso emitir? o que está atrasado? os cálculos ainda valem?
    p1, p2, p3, p4 = st.columns(4)
    with p1, st.container(border=True):
        st.markdown("**Emissão**")
        st.markdown(f"### {validacao['prontidao']}")
        st.caption(
            f"{validacao['contagens']['Bloqueio']} bloqueio(s) · "
            f"{validacao['contagens']['Pendência']} pendência(s) · "
            f"{validacao['contagens']['Atenção']} atenção(ões)"
        )
    with p2, st.container(border=True):
        st.markdown("**Checklist**")
        st.progress(
            resumo["checklist_percentual"] / 100,
            text=f"{resumo['checklist_percentual']}% concluído ({resumo['checklist_total']} itens)",
        )
        st.caption(
            f"{resumo['checklist_vencidos']} vencido(s) · {resumo['checklist_proximos']} vence(m) na semana · "
            f"{resumo['criticos_abertos']} crítico(s) aberto(s)"
        )
    with p3, st.container(border=True):
        st.markdown("**Registros técnicos**")
        st.markdown(f"### {resumo['registros']} vigente(s)")
        st.caption(
            f"{resumo['registros_desatualizados']} desatualizado(s) · "
            f"{resumo['registros_nao_atendem']} não atende(m) · "
            f"{resumo['registros_superados']} superado(s)"
        )
    with p4, st.container(border=True):
        st.markdown("**Conteúdo permanente**")
        st.markdown(
            f"- {len(projeto['componentes'])} item(ns) no escopo físico\n"
            f"- {len(projeto.get('casos_carga', []))} caso(s), "
            f"{len(projeto.get('combinacoes_carga', []))} combinação(ões)\n"
            f"- {len(projeto.get('materiais_projeto', []))} material(is), "
            f"{len(projeto['normas'])} norma(s), {len(projeto.get('anexos', []))} documento(s)\n"
            "- Critérios técnicos: "
            + ("definidos" if resumo["criterios_definidos"] else "padrão do programa")
        )

    passos = proximos_passos(projeto, resumo=resumo, validacao=validacao)
    col_passos, col_tempo = st.columns([3, 2])
    with col_passos, st.container(border=True):
        st.markdown("##### Próximos passos sugeridos")
        st.caption("Da ação que mais destrava para a que menos. A ordem vem das mesmas regras da validação.")
        for numero, passo in enumerate(passos, start=1):
            st.markdown(f"**{numero}. {passo['titulo']}** — {passo['detalhe']}")
            if passo["pagina"] != "app_pages/gestao_projetos.py":
                st.page_link(passo["pagina"], label="Abrir", icon=":material/arrow_forward:")
    with col_tempo, st.container(border=True):
        st.markdown("##### Linha do tempo recente")
        eventos_recentes = historico_eventos(projeto["id"], limite=8)
        if eventos_recentes:
            for evento in eventos_recentes:
                st.markdown(
                    f"`{_data_curta(evento['quando'])}` · {ROTULOS_EVENTO.get(evento['tipo'], evento['tipo'])} — "
                    f"{evento['descricao']}"
                )
            st.caption("Histórico completo na aba **Fluxo e revisões**.")
        else:
            st.caption("Os salvamentos passam a ser registrados aqui a partir de agora.")
    st.info(validacao["aviso"], icon=":material/info:")

# ============================================================ Dados e base
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
            "verificação e aprovação. A situação do projeto muda na aba "
            "**Fluxo e revisões**, que confere o que cada passagem exige."
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
                help="Exigido para enviar o projeto à verificação.",
            )
            aprov = i.text_input(
                "Aprovador" + _marca(estado, "aprovador"),
                value=projeto.get("aprovador", ""),
                help="Exigido para marcar o projeto como emitido.",
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
                help="A lista controlada, com revisão e situação de cada documento, fica na aba Documentos.",
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
                help="Os limites numéricos que a validação usa ficam na aba Critérios.",
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

# =============================================================== Critérios
with abas[2]:
    criterios_salvos = projeto.get("criterios_projeto")
    criterios = normalizar_criterios_projeto(criterios_salvos if isinstance(criterios_salvos, Mapping) else None)
    avaliacao_criterios = avaliar_criterios_projeto(criterios)
    st.caption(
        "Limites e condições que os módulos consultam e contra os quais a Central de "
        "validação cobra cada cálculo. Enquanto não forem definidos, vale o padrão do programa."
    )
    if not isinstance(criterios_salvos, Mapping):
        st.info(
            "Este projeto ainda usa os critérios padrão: n ≥ 1,5; utilização ≤ 1,0; "
            "risco de não atendimento ≤ 5%. Salve abaixo para torná-los critérios do projeto.",
            icon=":material/tune:",
        )
    else:
        st.success(
            f"Critérios definidos: {resumo_criterios_projeto(criterios)}.",
            icon=":material/check_circle:",
        )
        if avaliacao_criterios["faltantes"]:
            st.warning("Faltam: " + "; ".join(avaliacao_criterios["faltantes"]) + ".", icon=":material/pending:")
        for alerta in avaliacao_criterios["alertas"]:
            st.caption(f":material/info: {alerta}")
    st.warning(
        "Alterar um critério marca os cálculos já registrados como **desatualizados** até serem "
        "refeitos — é o comportamento esperado: a meta contra a qual eles foram conferidos mudou.",
        icon=":material/history:",
    )
    with st.form("projeto_criterios"):
        st.markdown("**Segurança e aceitação**")
        s1, s2, s3 = st.columns(3)
        fs_min = s1.number_input(
            "Fator de segurança mínimo (n)",
            min_value=0.01,
            value=float(criterios["seguranca"]["fator_seguranca_minimo"]),
            step=0.05,
            format="%.2f",
            help="Meta lida por Vigas e eixos e usada pela regra de margens da validação.",
        )
        util_max = s2.number_input(
            "Utilização máxima",
            min_value=0.01,
            value=float(criterios["seguranca"]["utilizacao_maxima"]),
            step=0.05,
            format="%.2f",
        )
        prob_max = s3.number_input(
            "Risco máximo de não atendimento (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(criterios["seguranca"]["probabilidade_nao_atendimento_max_pct"]),
            step=0.5,
            format="%.1f",
            help="Limite para as análises de sensibilidade probabilísticas.",
        )
        st.markdown("**Condições de operação**")
        o1, o2, o3, o4 = st.columns(4)
        temperatura = o1.number_input(
            "Temperatura de projeto (°C)",
            value=_numero_ou_none(criterios["operacao"]["temperatura_projeto_C"]),
            placeholder="ex.: 45",
            step=1.0,
        )
        pressao = o2.number_input(
            "Pressão de projeto (bar)",
            min_value=0.0,
            value=_numero_ou_none(criterios["operacao"]["pressao_projeto_bar"]),
            placeholder="ex.: 10",
            step=0.5,
        )
        vida_util = o3.number_input(
            "Vida útil (anos)",
            min_value=0.0,
            value=_numero_ou_none(criterios["operacao"]["vida_util_anos"]),
            placeholder="ex.: 20",
            step=1.0,
        )
        regime_criterio = o4.text_input(
            "Regime",
            value=criterios["operacao"]["regime"],
            placeholder="contínuo, intermitente…",
        )
        st.markdown("**Base normativa**")
        n1, n2 = st.columns([2, 1])
        norma_principal = n1.text_input(
            "Norma, especificação ou procedimento principal",
            value=criterios["normativo"]["norma_principal"],
            placeholder="ABNT NBR 8800",
        )
        edicao_norma = n2.text_input("Edição", value=criterios["normativo"]["edicao"], placeholder="2024")
        criterio_aceitacao = st.text_input(
            "Critério de aceitação (descrição)",
            value=criterios["normativo"]["criterio_aceitacao"],
            placeholder="ELU e ELS conforme NBR 8800; flecha ≤ L/350",
        )
        obs_normativo = st.text_input("Observações normativas", value=criterios["normativo"]["observacoes"])
        st.markdown("**Combinações de ações**")
        c1_, c2_ = st.columns(2)
        metodo_comb = c1_.text_input(
            "Método",
            value=criterios["combinacoes"]["metodo"],
            placeholder="Fatores explícitos definidos pelo projeto",
        )
        ref_comb = c2_.text_input(
            "Referência dos fatores",
            value=criterios["combinacoes"]["referencia"],
            placeholder="NBR 8681:2003, tabela 1",
        )
        obs_comb = st.text_input("Observações das combinações", value=criterios["combinacoes"]["observacoes"])
        maximos = st.checkbox(
            "Autorizar tratar máximos independentes como simultâneos",
            value=bool(criterios["combinacoes"]["maximos_independentes_simultaneos"]),
            help="Só marque com justificativa: a validação passa a sinalizar este ponto como alerta.",
        )
        st.markdown("**Unidades preferidas do projeto**")
        colunas_unidades = st.columns(len(UNIDADES_PROJETO))
        unidades_escolhidas = {}
        for coluna, (grandeza, opcoes_unidade) in zip(colunas_unidades, UNIDADES_PROJETO.items(), strict=True):
            atual = criterios["unidades"].get(grandeza, opcoes_unidade[0])
            unidades_escolhidas[grandeza] = coluna.selectbox(
                grandeza.capitalize(),
                list(opcoes_unidade),
                index=list(opcoes_unidade).index(atual) if atual in opcoes_unidade else 0,
                key=f"unidade_{grandeza}_{projeto['id']}",
            )
        salvar_criterios = st.form_submit_button(
            "Salvar critérios do projeto", type="primary", icon=":material/save:"
        )
    if salvar_criterios:
        novo = normalizar_criterios_projeto(
            {
                "unidades": unidades_escolhidas,
                "seguranca": {
                    "fator_seguranca_minimo": fs_min,
                    "utilizacao_maxima": util_max,
                    "probabilidade_nao_atendimento_max_pct": prob_max,
                },
                "operacao": {
                    "temperatura_projeto_C": temperatura,
                    "pressao_projeto_bar": pressao,
                    "vida_util_anos": vida_util,
                    "regime": regime_criterio,
                },
                "combinacoes": {
                    "metodo": metodo_comb,
                    "referencia": ref_comb,
                    "observacoes": obs_comb,
                    "maximos_independentes_simultaneos": maximos,
                },
                "normativo": {
                    "norma_principal": norma_principal,
                    "edicao": edicao_norma,
                    "criterio_aceitacao": criterio_aceitacao,
                    "observacoes": obs_normativo,
                },
                "responsavel": projeto.get("responsavel", ""),
                "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        )
        projeto["criterios_projeto"] = novo
        _salvar(projeto, "Atualização dos critérios técnicos do projeto")
        st.rerun()

# ============================================================ Escopo físico
with abas[3]:
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
        linhas = [
            linha
            for linha in _linhas_editor(editado)
            if any(str(linha.get(campo, "")).strip() for campo in ("tag", "descricao", "servico"))
        ]
        projeto["componentes"] = _mesclar_linhas(projeto["componentes"], linhas)
        _salvar(projeto, "Atualização do escopo físico")
        st.rerun()

# ================================================================== Normas
with abas[4]:
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
        linhas = [linha for linha in _linhas_editor(editado_normas) if str(linha.get("codigo", "")).strip()]
        projeto["normas"] = _mesclar_linhas(projeto["normas"], linhas)
        _salvar(projeto, "Atualização da matriz normativa")
        st.rerun()

# ============================================================== Documentos
with abas[5]:
    st.caption(
        "Lista controlada dos documentos de entrada: desenhos, folhas de dados, certificados, "
        "memoriais anteriores e especificações. A validação cobra a revisão de cada um e avisa "
        "quando o escopo cita um documento superado ou ainda não recebido."
    )
    documentos = [item for item in projeto.get("anexos", []) if isinstance(item, Mapping)]
    if not documentos and st.button(
        "Começar com uma linha de exemplo",
        icon=":material/playlist_add:",
        key="semear_documento",
    ):
        projeto["anexos"] = [
            {
                **criar_item(),
                "codigo": "DE-1042",
                "titulo": "Arranjo geral do suporte do CV-204",
                "tipo": "Desenho",
                "revisao": "C",
                "data": date.today().strftime("%d/%m/%Y"),
                "emitente": "Engenharia do cliente",
                "situacao": "Vigente",
                "observacao": "",
            }
        ]
        _salvar(projeto, "Linha de exemplo dos documentos de entrada")
        st.rerun()
    colunas_documentos = ["id", "codigo", "titulo", "tipo", "revisao", "data", "emitente", "situacao", "observacao"]
    df_documentos = pd.DataFrame(documentos)
    for coluna in colunas_documentos:
        if coluna not in df_documentos:
            df_documentos[coluna] = ""
    editado_documentos = st.data_editor(
        df_documentos[colunas_documentos],
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "id": None,
            "codigo": st.column_config.TextColumn("Código", required=True),
            "titulo": st.column_config.TextColumn("Título", width="large"),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=list(TIPOS_DOCUMENTO)),
            "revisao": st.column_config.TextColumn("Revisão", width="small"),
            "data": st.column_config.TextColumn("Data", width="small"),
            "emitente": st.column_config.TextColumn("Emitente"),
            "situacao": st.column_config.SelectboxColumn("Situação", options=list(SITUACOES_DOCUMENTO)),
            "observacao": st.column_config.TextColumn("Observação", width="large"),
        },
        key=f"documentos_{projeto['id']}",
    )
    linhas_documentos = _linhas_editor(editado_documentos)
    if linhas_documentos:
        aguardando = [linha for linha in linhas_documentos if str(linha.get("situacao")) == "Aguardando recebimento"]
        sem_revisao = [linha for linha in linhas_documentos if str(linha.get("codigo", "")).strip() and not str(linha.get("revisao", "")).strip()]
        if aguardando or sem_revisao:
            st.warning(
                f"{len(aguardando)} documento(s) aguardando recebimento · "
                f"{len(sem_revisao)} sem revisão informada.",
                icon=":material/pending:",
            )
        else:
            st.success("Todos os documentos têm revisão e estão recebidos.", icon=":material/check_circle:")
    if st.button("Salvar documentos de entrada", type="primary", icon=":material/save:"):
        linhas = [linha for linha in linhas_documentos if str(linha.get("codigo", "")).strip()]
        projeto["anexos"] = _mesclar_linhas(documentos, linhas)
        _salvar(projeto, "Atualização dos documentos de entrada")
        st.rerun()

# ======================================================= Registros técnicos
with abas[6]:
    registros = projeto["registros_tecnicos"]
    if registros:
        linhas_registros = resumir_registros(projeto)
        f1, f2, f3 = st.columns([2, 2, 1])
        situacoes_registro = sorted({linha["status"] for linha in linhas_registros})
        filtro_situacao = f1.multiselect(
            "Situação", situacoes_registro, default=[s for s in situacoes_registro if s != STATUS_SUPERADO]
        )
        pecas_registro = sorted({linha["peca"] or "(sem peça)" for linha in linhas_registros})
        filtro_peca = f2.multiselect("Peça", pecas_registro, default=pecas_registro)
        so_desatualizados = f3.toggle("Só desatualizados", value=False)
        filtrados = [
            linha
            for linha in linhas_registros
            if linha["status"] in filtro_situacao
            and (linha["peca"] or "(sem peça)") in filtro_peca
            and (not so_desatualizados or not linha["atualizado"])
        ]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Peça": linha["peca"] or "—",
                        "Módulo": linha["modulo"],
                        "Registro": linha["titulo"],
                        "Situação": linha["status"],
                        "Atualidade": linha["atualidade"],
                        # NaN, e não None: a coluna numérica mostra vazio em vez de "None".
                        "Menor fator": linha["menor_fator"] if linha["menor_fator"] is not None else float("nan"),
                        "Utilização": linha["utilizacao"] if linha["utilizacao"] is not None else float("nan"),
                        "Dependentes": linha["dependentes"],
                        "Registrado em": _data_curta(linha["criado_em"]),
                    }
                    for linha in filtrados
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Menor fator": st.column_config.NumberColumn(format="%.2f"),
                "Utilização": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        desatualizados = [linha for linha in linhas_registros if not linha["atualizado"] and not linha["superado"]]
        if desatualizados:
            st.warning(
                f"{len(desatualizados)} registro(s) usam fontes que mudaram depois do cálculo: "
                + "; ".join(linha["titulo"] for linha in desatualizados[:4])
                + ("…" if len(desatualizados) > 4 else "."),
                icon=":material/history:",
            )
        opcoes_registro = {linha["id"]: f"{linha['modulo']} · {linha['titulo']} · {linha['status']}" for linha in filtrados}
        if opcoes_registro:
            registro_id = st.selectbox(
                "Inspecionar registro", list(opcoes_registro), format_func=lambda valor: opcoes_registro[valor]
            )
            registro = next(item for item in registros if item["id"] == registro_id)
            linha_registro = next(linha for linha in linhas_registros if linha["id"] == registro_id)
            with st.container(border=True):
                st.markdown(f"**{registro.get('titulo')}** · {registro.get('modulo')} · {registro.get('status')}")
                if registro.get("conclusao"):
                    st.write(registro["conclusao"])
                if linha_registro["motivos"]:
                    st.warning(" ".join(linha_registro["motivos"]), icon=":material/history:")
                if registro.get("superado_em"):
                    st.caption(
                        f"Superado em {_data_curta(registro['superado_em'])}"
                        + (f" — {registro.get('superado_motivo')}" if registro.get("superado_motivo") else "")
                    )
                dependentes = dependentes_do_registro(projeto, registro_id)
                if dependentes:
                    st.caption(
                        "Usado como origem por: "
                        + "; ".join(str(item.get("titulo")) for item in dependentes)
                    )
                with st.expander("Dados completos do registro", expanded=False):
                    st.json(registro, expanded=2)

                st.markdown("**Administrar este registro**")
                col_superar, col_excluir = st.columns(2)
                with col_superar:
                    if linha_registro["superado"]:
                        st.caption("Este registro já está superado.")
                    else:
                        outros = {
                            linha["id"]: f"{linha['modulo']} · {linha['titulo']}"
                            for linha in linhas_registros
                            if linha["id"] != registro_id and not linha["superado"]
                        }
                        substituto = st.selectbox(
                            "Superado por",
                            ["", *outros],
                            format_func=lambda valor: outros.get(valor, "(sem substituto declarado)"),
                            key=f"substituto_{registro_id}",
                        )
                        motivo_superar = st.text_input(
                            "Motivo",
                            key=f"motivo_superar_{registro_id}",
                            placeholder="Refeito com a carga corrigida da folha de dados rev. 2",
                        )
                        if st.button(
                            "Marcar como superado",
                            icon=":material/history_toggle_off:",
                            key=f"superar_{registro_id}",
                            help="Mantém o registro no histórico, mas fora do memorial padrão e das cobranças da validação.",
                        ):
                            try:
                                documento = superar_registro(
                                    projeto, registro_id, motivo=motivo_superar, substituto_id=substituto or None
                                )
                            except ValueError as erro:
                                st.error(str(erro))
                            else:
                                _salvar(documento, f"Registro superado: {registro.get('titulo')}")
                                st.rerun()
                with col_excluir:
                    confirmar_exclusao_registro = st.checkbox(
                        "Confirmo a exclusão definitiva deste registro.",
                        key=f"confirma_excluir_{registro_id}",
                    )
                    if dependentes:
                        st.caption(
                            f":material/warning: {len(dependentes)} registro(s) dependem deste e passarão a "
                            "'Referência ausente'. Prefira marcar como superado."
                        )
                    if st.button(
                        "Excluir registro",
                        icon=":material/delete:",
                        key=f"excluir_{registro_id}",
                        disabled=not confirmar_exclusao_registro,
                    ):
                        documento = remover_registro(projeto, registro_id)
                        _salvar(documento, f"Registro excluído: {registro.get('titulo')}")
                        st.rerun()
        else:
            st.info("Nenhum registro corresponde aos filtros.")
    else:
        st.info("Ainda não há registros técnicos. Os módulos de cálculo podem gravar resultados aqui.")
    st.subheader("Adicionar verificação manual")
    with st.form("registro_manual"):
        r1, r2, r3 = st.columns(3)
        modulo = r1.text_input("Disciplina / módulo", value="Verificação industrial")
        titulo = r2.text_input("Título", placeholder="Verificação do suporte SP-104")
        status_reg = r3.selectbox("Situação", ["Pendente", "Atende", "Não atende", "Inconclusivo"])
        resumo_manual = st.text_area("Escopo e método")
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
                    "resumo": resumo_manual, "entradas": entradas, "resultados": resultados,
                    "premissas": [linha.strip() for linha in premissas.splitlines() if linha.strip()],
                    "referencias": [linha.strip() for linha in referencias.splitlines() if linha.strip()],
                    "conclusao": conclusao, "responsavel": projeto.get("responsavel", ""),
                },
            )
            st.success("Registro técnico adicionado e salvo.")
            st.rerun()
        except (json.JSONDecodeError, ValueError) as erro:
            st.error(f"Revise os campos JSON: {erro}")

# =============================================================== Checklist
with abas[7]:
    resumo_check = resumo_checklist(projeto["checklist"])
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Itens", resumo_check["total"])
    k2.metric("Concluídos", f"{resumo_check['percentual_concluido']}%")
    k3.metric("Vencidos", len(resumo_check["vencidos"]))
    k4.metric("Vencem em 7 dias", len(resumo_check["proximos"]))
    if resumo_check["vencidos"] or resumo_check["proximos"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Situação": linha["situacao"],
                        "Item": linha["item"],
                        "Responsável": linha["responsavel"] or "—",
                        "Prazo": linha["prazo_texto"],
                        "Dias": linha["dias"],
                        "Crítico": linha["critico"],
                    }
                    for linha in [*resumo_check["vencidos"], *resumo_check["proximos"]]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    if resumo_check["ilegiveis"]:
        st.caption(
            ":material/info: Prazos que não são datas e por isso não entram na cobrança: "
            + "; ".join(f"{linha['item']} ({linha['prazo_texto']})" for linha in resumo_check["ilegiveis"])
            + ". Eles aparecem em branco na tabela; ao reescrever como data, a cobrança passa a valer."
        )

    colunas_check = ["id", "item", "categoria", "responsavel", "prazo", "estado", "evidencia", "critico"]
    df_check = pd.DataFrame(projeto["checklist"])
    for coluna in colunas_check:
        if coluna not in df_check:
            df_check[coluna] = False if coluna == "critico" else ""
    # O prazo vira data de verdade no editor. O texto original fica guardado
    # por id para não se perder quando não for interpretável como data.
    prazos_originais = {
        str(item.get("id")): str(item.get("prazo") or "")
        for item in projeto["checklist"]
        if isinstance(item, Mapping)
    }
    df_check["prazo"] = pd.to_datetime(
        df_check["prazo"].map(interpretar_prazo), errors="coerce"
    )
    editado_check = st.data_editor(
        df_check[colunas_check], num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "id": None,
            "item": st.column_config.TextColumn("Item de verificação", required=True, width="large"),
            "categoria": st.column_config.TextColumn("Categoria"),
            "responsavel": st.column_config.TextColumn("Responsável"),
            "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
            "estado": st.column_config.SelectboxColumn("Estado", options=list(ESTADOS_CHECKLIST)),
            "evidencia": st.column_config.TextColumn("Evidência / documento", width="large"),
            "critico": st.column_config.CheckboxColumn("Crítico"),
        },
        key=f"check_{projeto['id']}",
    )
    if st.button("Salvar checklist", type="primary", icon=":material/save:"):
        linhas = []
        for linha in _linhas_editor(editado_check):
            if not str(linha.get("item", "")).strip():
                continue
            prazo_editor = interpretar_prazo(linha.get("prazo"))
            original = prazos_originais.get(str(linha.get("id") or ""), "")
            if prazo_editor is not None:
                linha["prazo"] = prazo_editor.isoformat()
            elif original and interpretar_prazo(original) is None:
                linha["prazo"] = original  # texto livre preservado
            else:
                linha["prazo"] = ""
            linhas.append(linha)
        projeto["checklist"] = _mesclar_linhas(projeto["checklist"], linhas)
        _salvar(projeto, "Atualização do checklist")
        st.rerun()

# ======================================================= Fluxo e revisões
with abas[8]:
    st.subheader("Situação e fluxo de trabalho")
    st.caption(
        f"Situação atual: **{situacao_atual(projeto)}** — {DESCRICOES.get(situacao_atual(projeto), '')} "
        "Cada passagem confere o que o projeto precisa ter; nada é alterado sem passar por aqui."
    )
    transicoes = avaliar_todas_transicoes(projeto, validacao=validacao)
    colunas_transicao = st.columns(len(transicoes)) if transicoes else []
    for coluna, transicao in zip(colunas_transicao, transicoes, strict=True):
        with coluna, st.container(border=True):
            st.markdown(f"**→ {transicao['destino']}**")
            st.caption(DESCRICOES.get(transicao["destino"], ""))
            for impedimento in transicao["impedimentos"]:
                st.markdown(f":material/block: {impedimento}")
            for aviso in transicao["avisos"]:
                st.markdown(f":material/warning: {aviso}")
            motivo_transicao = ""
            if transicao["destino"] == SUSPENSO:
                motivo_transicao = st.text_input(
                    "Motivo da suspensão", key=f"motivo_suspensao_{projeto['id']}", placeholder="Aguardando dados do cliente"
                )
            if st.button(
                f"Mudar para {transicao['destino']}",
                key=f"transicao_{transicao['destino']}_{projeto['id']}",
                disabled=not transicao["permitida"],
                type="primary" if transicao["permitida"] else "secondary",
                icon=":material/arrow_forward:",
                width="stretch",
            ):
                if transicao["destino"] == ARQUIVADO:
                    arquivar_projeto(projeto["id"])
                    st.session_state["projeto_ativo"] = None
                    st.rerun()
                projeto["status"] = transicao["destino"]
                descricao_evento = transicao["motivo"]
                if motivo_transicao.strip():
                    descricao_evento += f": {motivo_transicao.strip()}"
                # A mudança de situação em si vira evento próprio dentro de
                # salvar_projeto; aqui só o motivo declarado é gravado.
                _salvar(projeto, descricao_evento, revisao=transicao["cria_revisao"])
                st.rerun()

    st.divider()
    st.subheader("Revisões controladas")
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
    st.dataframe(
        pd.DataFrame(
            [
                {"Revisão": f"{item['revisao']:02d}", "Motivo": item["motivo"], "Criada em": _data_curta(item["criado_em"])}
                for item in historico
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if len(historico) > 1:
        alvo = st.selectbox("Revisão histórica", [item["revisao"] for item in historico[1:]], format_func=lambda valor: f"Revisão {valor:02d}")
        confirmar_restaura = st.checkbox("Confirmo que a restauração criará uma nova revisão a partir deste marco.")
        if st.button("Restaurar como nova revisão", disabled=not confirmar_restaura, icon=":material/restore:"):
            restaurar_revisao(projeto["id"], alvo)
            st.rerun()

    st.divider()
    st.subheader("Comparar revisões")
    st.caption(
        "Mostra o que mudou de engenharia entre dois marcos — ou entre um marco e o projeto atual. "
        "Datas, hashes e estados recalculados ficam de fora."
    )
    opcoes_comparacao = {"atual": "Projeto atual (não salvo como revisão)"}
    opcoes_comparacao.update({str(item["revisao"]): f"Revisão {item['revisao']:02d} · {item['motivo']}" for item in historico})
    chaves_comparacao = list(opcoes_comparacao)
    comp1, comp2 = st.columns(2)
    base_comparacao = comp1.selectbox(
        "De",
        chaves_comparacao,
        index=min(1, len(chaves_comparacao) - 1) if len(chaves_comparacao) > 2 else len(chaves_comparacao) - 1,
        format_func=lambda valor: opcoes_comparacao[valor],
        key=f"comparar_de_{projeto['id']}",
    )
    alvo_comparacao = comp2.selectbox(
        "Para",
        chaves_comparacao,
        index=0,
        format_func=lambda valor: opcoes_comparacao[valor],
        key=f"comparar_para_{projeto['id']}",
    )

    def _documento_para_comparar(chave: str) -> Mapping[str, Any] | None:
        if chave == "atual":
            return projeto
        return obter_revisao(projeto["id"], int(chave))

    if base_comparacao == alvo_comparacao:
        st.caption("Escolha dois marcos diferentes para comparar.")
    else:
        doc_antes = _documento_para_comparar(base_comparacao)
        doc_depois = _documento_para_comparar(alvo_comparacao)
        if doc_antes is None or doc_depois is None:
            st.error("Uma das revisões não foi encontrada no banco.")
        else:
            diferencas = comparar_documentos(doc_antes, doc_depois)
            resumo_diferencas = resumir_diferencas(diferencas)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Diferenças", resumo_diferencas["total"])
            d2.metric("Alterações", resumo_diferencas["por_tipo"].get("Alterado", 0))
            d3.metric("Inclusões", resumo_diferencas["por_tipo"].get("Incluído", 0))
            d4.metric("Remoções", resumo_diferencas["por_tipo"].get("Removido", 0))
            if diferencas:
                tabela_diferencas = pd.DataFrame(
                    [
                        {
                            "Seção": item["secao"],
                            "Item": item["item"] or "—",
                            "Campo": item["campo"] or "—",
                            "Tipo": item["tipo"],
                            "Antes": item["antes"],
                            "Depois": item["depois"],
                        }
                        for item in diferencas
                    ]
                )
                st.dataframe(tabela_diferencas, hide_index=True, width="stretch")
                st.download_button(
                    "Baixar comparação (CSV)",
                    data=tabela_diferencas.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{projeto['codigo']}_comparacao_{base_comparacao}_{alvo_comparacao}.csv".replace("/", "-"),
                    mime="text/csv",
                    icon=":material/download:",
                )
            else:
                st.success("Nenhuma diferença de engenharia entre os dois marcos.", icon=":material/check_circle:")

    st.divider()
    st.subheader("Linha do tempo")
    eventos = historico_eventos(projeto["id"], limite=200)
    if eventos:
        tipos_disponiveis = sorted({evento["tipo"] for evento in eventos})
        filtro_tipos = st.multiselect(
            "Tipo de evento",
            tipos_disponiveis,
            default=tipos_disponiveis,
            format_func=lambda valor: ROTULOS_EVENTO.get(valor, valor),
            key=f"filtro_eventos_{projeto['id']}",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Quando": _data_curta(evento["quando"]),
                        "Tipo": ROTULOS_EVENTO.get(evento["tipo"], evento["tipo"]),
                        "Descrição": evento["descricao"],
                        "Rev.": f"{int(evento['revisao']):02d}",
                        "Situação": evento["status"],
                    }
                    for evento in eventos
                    if evento["tipo"] in filtro_tipos
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Ainda não há eventos registrados para este projeto.")

# =========================================================== Administração
with abas[9]:
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
        "Excluir apaga o projeto, todos os registros técnicos, a linha do tempo e o histórico de revisões. "
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
