"""Esforços do modelo: importa os resultados do SolidWorks, confere as reações e acha o pior caso de
cada barra com as combinações do plano de cargas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import gravar_campo_do_projeto, mapa_do_projeto
from components.esforcos_modelo_help import AJUDA
from components.ui import cabecalho_pagina, configurar_pagina
from core import cantoneiras as ct
from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core.project_store import obter_projeto_ativo

configurar_pagina("Esforços do modelo", ":material/upload_file:")
cabecalho_pagina(
    "Esforços do modelo",
    "Importe as forças das vigas e as reações do SolidWorks, confira se o modelo recebeu as "
    "cargas do plano e veja o pior caso de cada barra nas combinações.",
    categoria="Gestão industrial",
    icone=":material/upload_file:",
    cor="violet",
    ajuda_modulo="Esforços do modelo",
    acoes=(("app_pages/plano_cargas.py", "Plano de cargas", ":material/table_chart:"),),
)
mapa_do_projeto(AJUDA_BASE["sec_mapa"])

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: os esforços ficam "
        "guardados no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()

plano = pc.plano_do_projeto(projeto)
dados = em.esforcos_do_projeto(projeto)
ICONES = {
    pc.NIVEL_ERRO: ":material/error:",
    pc.NIVEL_ATENCAO: ":material/warning:",
    pc.NIVEL_OK: ":material/check_circle:",
    em.NIVEL_INFO: ":material/info:",
}
MOSTRAR = {pc.NIVEL_ERRO: st.error, pc.NIVEL_ATENCAO: st.warning, em.NIVEL_INFO: st.info}


def gravar(novos: em.EsforcosDoModelo, motivo: str) -> bool:
    return gravar_campo_do_projeto("esforcos_do_modelo", em.para_dicionario(novos), motivo)


if not plano.acoes:
    st.warning(
        "O plano de cargas está vazio: as combinações saem dele. Monte-o antes (pelo menos os "
        "casos que você rodou no SolidWorks).",
        icon=":material/table_chart:",
    )
codigos = list(dict.fromkeys([*plano.codigos, *(c.codigo for c in pc.CODIGOS)]))

# ============================================================ 1. arquivos
with st.container(border=True):
    st.subheader("1. Enviar os arquivos do SolidWorks", help=AJUDA["sec_arquivos"])
    versao = int(st.session_state.get("em_versao", 0))
    eixo = st.radio(
        "Eixo vertical do modelo",
        ["Y", "Z"],
        index=0 if dados.eixo_vertical == "Y" else 1,
        format_func=lambda e: "Y para cima (SolidWorks)" if e == "Y" else "Z para cima (Robot)",
        horizontal=True,
        key="em_eixo",
        help=AJUDA["eixo_vertical"],
    )
    enviados = st.file_uploader(
        "Arquivos CSV (forças da viga e forças de reação)",
        type=["csv", "txt"],
        accept_multiple_files=True,
        key=f"em_arquivos_{versao}",
        help=AJUDA["arquivos"],
    )
    lidos: list[em.ArquivoLido] = []
    for enviado in enviados or []:
        try:
            lidos.append(em.ler_arquivo(enviado.getvalue(), enviado.name))
        except em.ArquivoInvalido as erro:
            st.error(f"{enviado.name}: {erro}", icon=":material/error:")
    if lidos:
        st.subheader("O que foi reconhecido", help=AJUDA["res_arquivos"])
        tabela = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Arquivo": a.nome_arquivo,
                        "Tipo": a.tipo,
                        "Estudo": a.estudo,
                        "Conteúdo": (
                            f"{len(a.membros)} barras"
                            if a.tipo == em.TIPO_VIGAS
                            else "soma das reações"
                            if a.tipo == em.TIPO_REACOES
                            else f"maior von Mises {a.tensao_maxima_MPa or 0:.1f} MPa".replace(
                                ".", ","
                            )
                        ),
                        "Caso": em.caso_sugerido(a.estudo, codigos) or "",
                    }
                    for a in lidos
                ]
            ),
            hide_index=True,
            width="stretch",
            disabled=["Arquivo", "Tipo", "Estudo", "Conteúdo"],
            key=f"em_tabela_arquivos_{versao}",
            column_config={
                "Caso": st.column_config.SelectboxColumn(
                    options=["", *codigos], help="O código do plano de cargas deste estudo."
                )
            },
        )
        for a in lidos:
            for aviso in a.avisos:
                st.warning(f"{a.nome_arquivo}: {aviso}", icon=":material/warning:")
            if a.tipo == em.TIPO_TENSOES and a.tensao_maxima_MPa is not None:
                st.metric(
                    f"Maior tensão de von Mises — {a.estudo or a.nome_arquivo}",
                    f"{a.tensao_maxima_MPa:.1f} MPa".replace(".", ","),
                    help=AJUDA["res_tensao"],
                )
        if st.button(
            "Gravar no projeto",
            type="primary",
            icon=":material/save:",
            key="em_gravar_arquivos",
            help=AJUDA["btn_gravar_arquivos"],
        ):
            novos = em.EsforcosDoModelo(dados.casos, dados.membros, eixo)
            problemas: list[str] = []
            casos_por_arquivo = dict(zip(tabela["Arquivo"], tabela["Caso"], strict=True))
            for a in sorted(lidos, key=lambda x: x.tipo != em.TIPO_VIGAS):
                caso = str(casos_por_arquivo.get(a.nome_arquivo) or "")
                if a.tipo == em.TIPO_TENSOES:
                    continue
                if not caso:
                    problemas.append(f"{a.nome_arquivo}: escolha o caso.")
                    continue
                try:
                    if a.tipo == em.TIPO_VIGAS:
                        novos = em.com_caso(novos, em.caso_do_arquivo(a, caso))
                    elif a.reacoes is not None:
                        novos = em.com_reacoes(novos, caso, a.reacoes, a.nome_arquivo)
                except em.ArquivoInvalido as erro:
                    problemas.append(f"{a.nome_arquivo}: {erro}")
            for problema in problemas:
                st.error(problema, icon=":material/error:")
            if not problemas and gravar(novos, "Esforços do modelo importados do SolidWorks"):
                st.session_state["em_versao"] = versao + 1
                st.rerun()
    elif eixo != dados.eixo_vertical and dados.casos:
        if gravar(em.EsforcosDoModelo(dados.casos, dados.membros, eixo), "Eixo vertical do modelo"):
            st.rerun()

if not dados.casos:
    st.caption(
        "Nenhum caso importado ainda. Rode um estudo por caso de carga no SolidWorks (nome do "
        "estudo = código do plano) e envie as listas aqui."
    )
    st.stop()

# ============================================================ 2. casos
with st.container(border=True):
    st.subheader(f"2. Casos importados ({len(dados.casos)})", help=AJUDA["sec_casos"])
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Caso": c.codigo,
                    "Estudo no SolidWorks": c.estudo,
                    "Arquivo": c.arquivo,
                    "Barras": len(c.membros),
                    "Elementos": c.elementos,
                    "Reações": c.arquivo_reacoes or "—",
                    "Importado em": c.importado_em.replace("T", " "),
                }
                for c in dados.casos.values()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    colunas = st.columns([2, 1])
    remover = colunas[0].selectbox(
        "Caso a remover", list(dados.casos), key="em_caso_remover", help=AJUDA["caso_remover"]
    )
    if colunas[1].button(
        "Remover o caso",
        icon=":material/delete:",
        key="em_remover",
        help=AJUDA["btn_remover"],
        width="stretch",
    ) and gravar(em.sem_caso(dados, remover), f"Esforços do modelo: caso {remover} removido"):
        st.rerun()

# ============================================================ 3. conferência
with st.container(border=True):
    st.subheader("3. Conferência das reações", help=AJUDA["sec_conferencia"])
    for item in em.conferir_reacoes(dados, plano):
        MOSTRAR.get(item.nivel, st.success)(item.texto, icon=ICONES[item.nivel])

# ============================================================ 4. barras
catalogo = ["", *sc.listar_perfis(), *ct.CATALOGO_CANTONEIRAS]
with st.container(border=True):
    st.subheader(f"4. Barras do modelo ({len(dados.nomes_dos_membros)})", help=AJUDA["sec_barras"])
    linhas_barras = []
    for nome in dados.nomes_dos_membros:
        cfg = dados.membros.get(nome, em.ConfiguracaoDoMembro())
        pontos = [p for c in dados.casos.values() for p in c.membros.get(nome, ())]
        linhas_barras.append(
            {
                "Barra": nome,
                "Perfil no nome": em.perfil_do_nome(nome) or "—",
                "Perfil": cfg.perfil if cfg.perfil in catalogo else "",
                "Tipo": cfg.tipo,
                "Eixo forte": cfg.eixo_forte,
                "|N| máx. (kN)": max((abs(p.n) for p in pontos), default=0.0),
                "|M1| máx. (kN·m)": max((abs(p.m1) for p in pontos), default=0.0),
                "|M2| máx. (kN·m)": max((abs(p.m2) for p in pontos), default=0.0),
            }
        )
    barras = st.data_editor(
        pd.DataFrame(linhas_barras),
        hide_index=True,
        width="stretch",
        key=f"em_barras_{versao}",
        disabled=[
            "Barra",
            "Perfil no nome",
            "|N| máx. (kN)",
            "|M1| máx. (kN·m)",
            "|M2| máx. (kN·m)",
        ],
        column_config={
            "Perfil": st.column_config.SelectboxColumn(
                options=catalogo, help="Perfil do catálogo do programa."
            ),
            "Tipo": st.column_config.SelectboxColumn(
                options=list(em.TIPOS_DE_BARRA), help="Pilar, viga, diagonal…"
            ),
            "Eixo forte": st.column_config.SelectboxColumn(
                options=[em.EIXO_M1, em.EIXO_M2],
                help="Qual momento do SolidWorks é o do eixo forte (o que domina numa viga).",
            ),
            **{
                c: st.column_config.NumberColumn(format="%.2f")
                for c in ("|N| máx. (kN)", "|M1| máx. (kN·m)", "|M2| máx. (kN·m)")
            },
        },
    )
    st.caption(
        "Valores característicos (de todos os casos importados, sem coeficientes). Os perfis lidos "
        "do nome vêm preenchidos; os das barras “Aparar/Estender” você escolhe uma vez."
    )
    if st.button(
        "Gravar a tabela das barras",
        icon=":material/save:",
        key="em_gravar_barras",
        help=AJUDA["btn_gravar_barras"],
    ):
        configuracoes = {
            str(linha["Barra"]): em.ConfiguracaoDoMembro(
                perfil=str(linha["Perfil"] or ""),
                tipo=str(linha["Tipo"] or "—"),
                eixo_forte=str(linha["Eixo forte"] or em.EIXO_M2),
            )
            for _, linha in barras.iterrows()
        }
        if gravar(em.com_membros(dados, configuracoes), "Esforços do modelo: tabela das barras"):
            st.rerun()

# ============================================================ 5. envoltória
with st.container(border=True):
    st.subheader("5. Pior caso de cada barra", help=AJUDA["sec_envoltoria"])
    colunas = st.columns([3, 1])
    estados = colunas[0].multiselect(
        "Estados-limite",
        list(comb.TODOS_OS_ESTADOS),
        default=[comb.ELU_NORMAL],
        key="em_estados",
        help=AJUDA["estados"],
    )
    filtro = colunas[1].selectbox(
        "Mostrar", ["Todas", *em.TIPOS_DE_BARRA[1:]], key="em_filtro", help=AJUDA["filtro_tipo"]
    )
    if not estados:
        st.stop()
    resultado = em.envoltoria(dados, plano, estados)
    for aviso in resultado.avisos:
        st.warning(aviso, icon=":material/warning:")
    if resultado.membros:
        st.caption(
            f"{resultado.combinacoes} combinações com os casos {', '.join(resultado.casos)}, em "
            "todos os pontos de cada barra. M forte e M fraco seguem a tabela das barras; “N junto” "
            "é o esforço normal na mesma combinação e ponto do M forte (para a interação N + M)."
        )
        linhas = em.linhas_da_envoltoria(dados, resultado)
        tabela_env = pd.DataFrame(linhas, columns=list(em.COLUNAS_ENVOLTORIA))
        if filtro != "Todas":
            tabela_env = tabela_env[tabela_env["Tipo"] == filtro]
        st.dataframe(
            tabela_env.replace("", None),
            hide_index=True,
            width="stretch",
            column_config={
                c: st.column_config.NumberColumn(format="%.2f")
                for c in em.COLUNAS_ENVOLTORIA
                if "(kN" in c
            },
        )
        st.download_button(
            "Pior caso de cada barra (CSV)",
            data=em.csv_da_envoltoria(dados, resultado),
            file_name=f"esforcos_envoltoria_{projeto.get('codigo') or 'projeto'}.csv",
            mime="text/csv",
            icon=":material/download:",
            key="em_csv",
            help=AJUDA["btn_csv"],
        )
        st.info(
            "Próxima etapa: a verificação automática de cada barra (perfil, aço, comprimento de "
            "flambagem) com estes esforços, e o quadro de cargas para as fundações.",
            icon=":material/construction:",
        )
