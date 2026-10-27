"""Reações nas bases: a força e o momento de cada pé, caso a caso, para o projeto da fundação."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.reacoes_nas_bases_help import AJUDA
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import apoios_do_modelo as am
from core import cena_do_modelo as cm
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core import reacoes_nas_bases as rb
from core.project_store import obter_projeto_ativo

configurar_pagina("Reações nas bases", ":material/foundation:")
cabecalho_pagina(
    "Reações nas bases",
    "A força e o momento de cada pé da estrutura em cada caso de carga (PP, PE, SC, ventos…), "
    "sem combinar, para quem projeta a fundação fazer as combinações dele — em Excel.",
    categoria="Modelo SolidWorks",
    icone=":material/foundation:",
    cor="blue",
    acoes=(("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),),
)
projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: as reações saem dos "
        "resultados do SolidWorks gravados no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()
dados = em.esforcos_do_projeto(projeto)
if not dados.casos:
    st.info(
        "O projeto ainda não tem os resultados do SolidWorks. Em **Esforços do modelo**, envie os "
        "arquivos de cada caso (a macro exportar_casos_de_carga grava as forças, as reações e os "
        "apoios de todos de uma vez).",
        icon=":material/upload_file:",
    )
    st.page_link(
        "app_pages/esforcos_modelo.py", label="Esforços do modelo", icon=":material/upload_file:"
    )
    st.stop()

with secao_protegida("Reações nas bases"):
    plano = pc.plano_do_projeto(projeto)
    apoios = am.do_projeto(projeto)
    geometria = ld.geometria_do_projeto(projeto)
    leituras = ld.ler_barras(dados, geometria, plano)
    quadro = qf.montar_quadro(dados)
    direcoes = None
    if quadro.pilares and geometria.corpos:
        try:
            direcoes = cm.direcoes_do_projeto(
                geometria,
                dados.eixo_vertical,
                dados,
                cm.Nomes.do_projeto(geometria, dados),
                quadro,
                plano,
            )
        except (ArithmeticError, ValueError, KeyError):
            direcoes = None
    reacoes = rb.montar(
        dados, apoios, plano=plano, geometria=geometria, leituras=leituras, direcoes=direcoes
    )
    diagnostico = dm.diagnosticar(
        dados,
        plano,
        apoios,
        geometria=geometria,
        leituras=leituras,
        ler_o_modelo=True,
        peso_da_estrutura_kN=lm.peso_da_estrutura_kN(lm.resumir(lm.lista_do_projeto(projeto))),
    )
    pendentes = rb.pendencias(diagnostico, reacoes)

    # ======================================================== o que vai
    with st.container(border=True):
        st.subheader("O que vai para o engenheiro civil", help=AJUDA["sec_resumo"])
        fontes = [a.fonte for a in reacoes.acoes]
        colunas = st.columns(4)
        colunas[0].metric("Pés", len(reacoes.pes), help=AJUDA["res_pes"])
        colunas[1].metric("Casos", len(reacoes.casos), help=AJUDA["res_casos"])
        colunas[2].metric("Pela macro", fontes.count(rb.FONTE_APOIO), help=AJUDA["res_macro"])
        colunas[3].metric("Pelos pilares", fontes.count(rb.FONTE_PILAR), help=AJUDA["res_pilar"])
        st.caption(rb.NOTA_COMBINACOES)
        if pendentes:
            st.error(
                "**Antes de mandar ao engenheiro civil, corrija** — estes problemas mudam as "
                "reações (o Excel sai marcado como PRELIMINAR):\n\n"
                + "\n".join(f"- {a.titulo}" for a in pendentes)
                + "\n\nO passo a passo de cada um está no painel “Antes de verificar”, em Esforços "
                "do modelo.",
                icon=":material/error:",
            )
            st.page_link(
                "app_pages/esforcos_modelo.py",
                label="Esforços do modelo › Antes de verificar",
                icon=":material/upload_file:",
            )
        elif reacoes.acoes:
            st.success(
                "Nada pendente que mude as reações: os arquivos de cada caso conferem.",
                icon=":material/verified:",
            )
        for texto in reacoes.faltam:
            st.warning(texto, icon=":material/warning:")
        for texto in reacoes.avisos:
            st.info(texto, icon=":material/info:")
        for item in reacoes.conferencia:
            if item.nivel == pc.NIVEL_OK:
                st.caption(f":material/check_circle: {item.texto}")
            else:
                st.warning(item.texto, icon=":material/warning:")

    # ======================================================== as reações
    with st.container(border=True):
        st.subheader("Reações de cada pé, caso a caso", help=AJUDA["sec_reacoes"])
        eixos = st.radio(
            "Eixos",
            rb.EIXOS,
            format_func=lambda e: (
                "Da fundação (Z para cima)"
                if e == rb.EIXOS_FUNDACAO
                else f"Do SolidWorks ({dados.eixo_vertical} para cima)"
            ),
            horizontal=True,
            key="rb_eixos",
            help=AJUDA["eixos"],
        )
        st.caption(rb.convencao(reacoes, eixos))
        tabela = rb.linhas(reacoes, plano, eixos)
        if tabela:
            cabecalho = rb.colunas(reacoes, eixos)
            st.dataframe(
                pd.DataFrame(tabela, columns=cabecalho),
                hide_index=True,
                width="stretch",
                column_config={
                    c: st.column_config.NumberColumn(format="%.3f") for c in cabecalho if "(kN" in c
                },
            )
            st.markdown("**O maior de cada pé** (característico, entre os casos)")
            st.dataframe(
                pd.DataFrame(rb.linhas_do_resumo(reacoes), columns=rb.COLUNAS_RESUMO).replace(
                    "—", None
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info(
                "Nenhum pé com valor ainda: veja os avisos acima (falta o -apoios.csv de cada caso "
                "ou a direção da seção dos pilares).",
                icon=":material/info:",
            )
        with st.expander("Locação dos pés e natureza de cada caso"):
            st.dataframe(
                pd.DataFrame(rb.linhas_da_locacao(reacoes, eixos), columns=rb.COLUNAS_LOCACAO),
                hide_index=True,
                width="stretch",
            )
            st.dataframe(
                pd.DataFrame(rb.linhas_dos_casos(reacoes, plano), columns=rb.COLUNAS_CASOS),
                hide_index=True,
                width="stretch",
            )
        nome = str(projeto.get("nome") or "")
        st.download_button(
            "Baixar o Excel para o engenheiro civil" + (" (PRELIMINAR)" if pendentes else ""),
            data=rb.xlsx(
                reacoes,
                plano,
                eixos=eixos,
                projeto=nome,
                responsavel=str(projeto.get("responsavel") or ""),
                pendentes=pendentes,
            ),
            file_name=rb.nome_do_arquivo(nome),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/table_view:",
            type="primary",
            key="rb_excel",
            help=AJUDA["btn_excel"],
            disabled=not tabela,
        )
