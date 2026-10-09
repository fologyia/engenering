"""Esforços do modelo: importa os resultados do SolidWorks, confere as reações e acha o pior caso de
cada barra com as combinações do plano de cargas."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import base_ativa, gravar_campo_do_projeto, mapa_do_projeto
from components.esforcos_modelo_help import AJUDA
from components.figuras_estrutura import svg_placa_de_base
from components.project_tools import botao_registrar_calculo
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import cantoneiras as ct
from core import column_buckling as cbk
from core import criterio_anglo as ca
from core import esforcos_modelo as em
from core import lista_de_material as lm
from core import load_combinations as comb
from core import placa_base_pilares as pb
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core import section_catalog as sc
from core import verificacao_barras as vb
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
            novos = replace(dados, eixo_vertical=eixo)
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
        if gravar(replace(dados, eixo_vertical=eixo), "Eixo vertical do modelo"):
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
    peso_da_estrutura = lm.peso_da_estrutura_kN(lm.resumir(lm.lista_do_projeto(projeto)))
    for item in em.conferir_reacoes(dados, plano, peso_da_estrutura_kN=peso_da_estrutura):
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
                "Aço": cfg.aco,
                "Lx (m)": cfg.lx_m,
                "Ly (m)": cfg.ly_m,
                "Lb (m)": cfg.lb_m,
                "Base (pilar)": cfg.base,
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
            "Aço": st.column_config.SelectboxColumn(
                options=["", *vb.ACOS], help="Vazio = o aço do tipo (tabela de parâmetros)."
            ),
            "Base (pilar)": st.column_config.SelectboxColumn(
                options=list(em.BASES),
                help="Qual ponta do pilar é a base, para o quadro das fundações.",
            ),
            **{
                c: st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", help="Vazio = o do tipo (tabela de parâmetros)."
                )
                for c in ("Lx (m)", "Ly (m)", "Lb (m)")
            },
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
                aco=str(linha["Aço"] or "") if not pd.isna(linha["Aço"]) else "",
                lx_m=None
                if pd.isna(linha["Lx (m)"]) or not linha["Lx (m)"]
                else float(linha["Lx (m)"]),
                ly_m=None
                if pd.isna(linha["Ly (m)"]) or not linha["Ly (m)"]
                else float(linha["Ly (m)"]),
                lb_m=None
                if pd.isna(linha["Lb (m)"]) or not linha["Lb (m)"]
                else float(linha["Lb (m)"]),
                base=str(linha["Base (pilar)"] or em.BASE_AUTOMATICA),
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

# ============================================================ 6. parâmetros
with st.container(border=True):
    st.subheader("6. Parâmetros da verificação", help=AJUDA["sec_parametros"])
    normas = list(cbk.NORMAS)
    norma = st.selectbox(
        "Norma",
        normas,
        index=normas.index(dados.norma) if dados.norma in normas else 0,
        format_func=lambda n: cbk.NORMAS_ROTULOS.get(n, n),
        key="em_norma",
        help=AJUDA["norma"],
    )
    parametros = st.data_editor(
        pd.DataFrame(
            [
                {
                    "Tipo": tipo,
                    "Aço": dados.parametros_do_tipo(tipo).aco,
                    "Lx (m)": dados.parametros_do_tipo(tipo).lx_m,
                    "Ly (m)": dados.parametros_do_tipo(tipo).ly_m,
                    "Lb (m)": dados.parametros_do_tipo(tipo).lb_m,
                    "Cb": dados.parametros_do_tipo(tipo).cb,
                    "B₂": dados.parametros_do_tipo(tipo).b2,
                }
                for tipo in em.TIPOS_DE_BARRA
            ]
        ),
        hide_index=True,
        width="stretch",
        key=f"em_parametros_{versao}",
        disabled=["Tipo"],
        column_config={
            "Aço": st.column_config.SelectboxColumn(options=list(vb.ACOS), help="f_y e f_u."),
            "Lx (m)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", help="K·L para a flambagem em torno do eixo forte."
            ),
            "Ly (m)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", help="K·L para a flambagem em torno do eixo fraco."
            ),
            "Lb (m)": st.column_config.NumberColumn(
                min_value=0.0,
                format="%.2f",
                help="Comprimento destravado da mesa comprimida (FLT). Vazio = Ly.",
            ),
            "Cb": st.column_config.NumberColumn(
                min_value=1.0, max_value=3.0, format="%.2f", help="Fator de momento da FLT."
            ),
            "B₂": st.column_config.NumberColumn(
                min_value=1.0,
                max_value=2.0,
                format="%.3f",
                help="Amplificação da 2ª ordem global (da página Contraventamento).",
            ),
        },
    )
    st.caption(
        "Valem para todas as barras do tipo; a tabela das barras pode mudar o aço e os "
        "comprimentos de uma barra. O estudo do SolidWorks é de 1ª ordem: o B₂ multiplica todos "
        "os esforços (a favor da segurança)."
    )
    if st.button(
        "Gravar os parâmetros",
        icon=":material/save:",
        key="em_gravar_parametros",
        help=AJUDA["btn_gravar_parametros"],
    ):

        def _comprimento(valor: object) -> float | None:
            return None if pd.isna(valor) or not valor else float(valor)  # type: ignore[arg-type]

        novos = {
            str(linha["Tipo"]): em.ParametrosDoTipo(
                aco=str(linha["Aço"] or em.ACO_PADRAO),
                lx_m=_comprimento(linha["Lx (m)"]),
                ly_m=_comprimento(linha["Ly (m)"]),
                lb_m=_comprimento(linha["Lb (m)"]),
                cb=_comprimento(linha["Cb"]) or 1.0,
                b2=_comprimento(linha["B₂"]) or 1.0,
            )
            for _, linha in parametros.iterrows()
        }
        if gravar(em.com_parametros(dados, novos, norma), "Esforços do modelo: parâmetros"):
            st.rerun()

# ============================================================ 7. verificação
with st.container(border=True):
    st.subheader("7. Verificação das barras", help=AJUDA["sec_verificacao"])
    resultados, avisos_verificacao = vb.verificar_barras(dados, plano, estados)
    for aviso in avisos_verificacao:
        st.warning(aviso, icon=":material/warning:")
    sintese = vb.resumo(resultados)
    colunas = st.columns(4)
    colunas[0].metric("Atendem", sintese["atendem"], help=AJUDA["res_resumo"])
    colunas[1].metric("Não atendem", sintese["nao_atendem"], help=AJUDA["res_resumo"])
    colunas[2].metric("Sem dados", sintese["pendentes"], help=AJUDA["res_resumo"])
    pior = sintese["pior"]
    colunas[3].metric(
        "Maior aproveitamento",
        "—" if pior is None else f"{100 * (pior.aproveitamento or 0.0):.0f} %",
        help=AJUDA["res_resumo"],
    )
    tabela_verif = pd.DataFrame(vb.linhas_da_tabela(resultados), columns=list(vb.COLUNAS))
    if filtro != "Todas":
        tabela_verif = tabela_verif[tabela_verif["Tipo"] == filtro]
    st.dataframe(
        tabela_verif.replace("", None),
        hide_index=True,
        width="stretch",
        column_config={
            "Aproveitamento (%)": st.column_config.ProgressColumn(
                min_value=0.0, max_value=100.0, format="%.0f %%"
            ),
            **{c: st.column_config.NumberColumn(format="%.2f") for c in vb.COLUNAS if "(kN" in c},
        },
    )
    verificadas = [r for r in resultados if r.linhas]
    if verificadas:
        nomes = [r.membro for r in verificadas]
        escolhida = st.selectbox(
            "Ver o cálculo da barra",
            nomes,
            index=nomes.index(pior.membro) if pior is not None and pior.membro in nomes else 0,
            key="em_barra_detalhe",
            help=AJUDA["barra_detalhe"],
        )
        detalhe = next(r for r in verificadas if r.membro == escolhida)
        st.caption(
            f"{detalhe.perfil} · {detalhe.combinacao}, {detalhe.ponto} · N = {detalhe.n:.2f} kN, "
            f"M forte = {detalhe.m_forte:.2f} kN·m, M fraco = {detalhe.m_fraco:.2f} kN·m "
            f"(de cálculo, com B₂) · {detalhe.metodo}".replace(".", ",")
        )
        mostrar_tabela_verificacoes(list(detalhe.linhas))
    st.download_button(
        "Verificação das barras (CSV)",
        data=vb.csv_das_barras(resultados),
        file_name=f"verificacao_barras_{projeto.get('codigo') or 'projeto'}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="em_csv_verificacao",
        help=AJUDA["btn_csv_verificacao"],
    )
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        vb.registro_das_barras(resultados, dados, estados),
        key="registrar_esforcos_modelo",
        rotulo="Registrar a verificação das barras no projeto ativo",
        identificar_peca=False,
    )

# ============================================================ 8. fundações
with st.container(border=True):
    st.subheader("8. Quadro de cargas para as fundações", help=AJUDA["sec_fundacoes"])
    quadro = qf.montar_quadro(dados)
    for item in quadro.conferencia:
        MOSTRAR.get(item.nivel, st.success)(item.texto, icon=ICONES[item.nivel])
    if quadro.pilares and any(p.cargas for p in quadro.pilares):
        numeros = qf.resumo_numerico(quadro)
        colunas = st.columns(3)
        colunas[0].metric("Pilares", numeros["pilares"], help=AJUDA["res_fundacoes"])
        colunas[1].metric(
            "Maior compressão",
            "—"
            if numeros["maior_compressao"] is None
            else f"{numeros['maior_compressao']:.1f} kN".replace(".", ","),
            help=AJUDA["res_fundacoes"],
        )
        colunas[2].metric(
            "Maior tração (arrancamento)",
            "—"
            if numeros["maior_tracao"] is None
            else f"{-numeros['maior_tracao']:.1f} kN".replace(".", ","),
            help=AJUDA["res_fundacoes"],
        )
        ver_quadro = st.radio(
            "Mostrar",
            ["Compressão por pilar", "Quadro completo"],
            horizontal=True,
            key="em_ver_quadro",
            help=AJUDA["ver_quadro"],
        )
        if ver_quadro == "Compressão por pilar":
            cabecalho, linhas_m = qf.matriz_de_compressao(quadro)
            st.dataframe(
                pd.DataFrame(linhas_m, columns=cabecalho).replace("", None),
                hide_index=True,
                width="stretch",
                column_config={
                    c: st.column_config.NumberColumn(format="%.2f") for c in cabecalho[1:]
                },
            )
        else:
            st.dataframe(
                pd.DataFrame(qf.linhas_do_quadro(quadro, plano), columns=list(qf.COLUNAS)),
                hide_index=True,
                width="stretch",
                column_config={
                    c: st.column_config.NumberColumn(format="%.2f")
                    for c in qf.COLUNAS
                    if "(kN" in c
                },
            )
        st.caption(f"{qf.NOTA_ANGLO} {qf.CONVENCAO}")
        colunas = st.columns(2)
        colunas[0].download_button(
            "Quadro das fundações (Excel)",
            data=qf.xlsx_do_quadro(
                quadro, plano, titulo=f"{projeto.get('nome', '')} ({projeto.get('codigo', '')})"
            ),
            file_name=f"quadro_fundacoes_{projeto.get('codigo') or 'projeto'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/table_view:",
            key="em_xlsx_quadro",
            help=AJUDA["btn_xlsx_quadro"],
            width="stretch",
        )
        colunas[1].download_button(
            "Quadro das fundações (CSV)",
            data=qf.csv_do_quadro(quadro, plano),
            file_name=f"quadro_fundacoes_{projeto.get('codigo') or 'projeto'}.csv",
            mime="text/csv",
            icon=":material/download:",
            key="em_csv_quadro",
            help=AJUDA["btn_csv_quadro"],
            width="stretch",
        )
        st.subheader("Registrar o quadro no projeto", help=AJUDA["reg_quadro"])
        botao_registrar_calculo(
            qf.registro_do_quadro(quadro, plano),
            key="registrar_quadro_fundacoes",
            rotulo="Registrar o quadro das fundações no projeto ativo",
            identificar_peca=False,
        )

# ============================================================ 9. placas de base
with st.container(border=True):
    st.subheader("9. Placas de base dos pilares", help=AJUDA["sec_placas"])
    if not quadro.pilares:
        st.info(
            "Marque os pilares na tabela das barras (tipo **Pilar**) para verificar as placas.",
            icon=":material/info:",
        )
        st.stop()
    placa = pb.placa_do_modelo(dados)
    with st.form("em_placa_form", border=False):
        colunas = st.columns(4)
        comprimento_placa = colunas[0].number_input(
            "N — comprimento (mm)",
            50.0,
            3000.0,
            float(placa.comprimento_mm),
            10.0,
            format="%.0f",
            key="em_placa_n",
            help=AJUDA["placa_n"],
        )
        largura_placa = colunas[1].number_input(
            "B — largura (mm)",
            50.0,
            3000.0,
            float(placa.largura_mm),
            10.0,
            format="%.0f",
            key="em_placa_b",
            help=AJUDA["placa_b"],
        )
        espessura_placa = colunas[2].number_input(
            "Espessura (mm)",
            3.0,
            150.0,
            float(placa.espessura_mm),
            0.5,
            format="%.1f",
            key="em_placa_t",
            help=AJUDA["placa_t"],
        )
        aco_placa = colunas[3].selectbox(
            "Aço da placa",
            list(vb.ACOS),
            index=list(vb.ACOS).index(placa.aco),
            key="em_placa_aco",
            help=AJUDA["placa_aco"],
        )
        colunas = st.columns(4)
        fck_placa = colunas[0].number_input(
            "f_ck do concreto (MPa)",
            10.0,
            90.0,
            float(placa.fck_MPa),
            5.0,
            format="%.0f",
            key="em_placa_fck",
            help=AJUDA["placa_fck"],
        )
        a2a1_placa = colunas[1].number_input(
            "A₂/A₁",
            1.0,
            4.0,
            float(placa.razao_a2_a1),
            0.1,
            format="%.2f",
            key="em_placa_a2a1",
            help=AJUDA["placa_a2a1"],
        )
        chumbadores_placa = colunas[2].number_input(
            "Chumbadores (total)",
            1,
            16,
            int(placa.chumbadores),
            1,
            key="em_placa_chumbadores",
            help=AJUDA["placa_chumbadores"],
        )
        lado_placa = colunas[3].number_input(
            "Na linha tracionada",
            1,
            8,
            int(placa.lado_tracionado),
            1,
            key="em_placa_lado",
            help=AJUDA["placa_lado"],
        )
        colunas = st.columns(4)
        diametro_placa = colunas[0].selectbox(
            "Diâmetro do chumbador",
            list(pb.DIAMETROS_MM),
            index=list(pb.DIAMETROS_MM).index(placa.diametro),
            key="em_placa_diametro",
            help=AJUDA["placa_diametro"],
        )
        aco_chumbador_placa = colunas[1].selectbox(
            "Aço do chumbador",
            list(pb.ACOS_CHUMBADOR),
            index=list(pb.ACOS_CHUMBADOR).index(placa.aco_chumbador),
            key="em_placa_aco_chumbador",
            help=AJUDA["placa_aco_chumbador"],
        )
        distancia_placa = colunas[2].number_input(
            "f — centro à linha tracionada (mm)",
            0.0,
            1500.0,
            float(placa.distancia_mm or 0.0),
            5.0,
            format="%.0f",
            key="em_placa_f",
            help=AJUDA["placa_f"],
        )
        leve_placa = colunas[3].toggle(
            "Elemento leve",
            value=placa.elemento_leve,
            key="em_placa_leve",
            help=AJUDA["placa_leve"],
        )
        gravar_placa = st.form_submit_button(
            "Gravar a placa",
            icon=":material/save:",
            key="em_gravar_placa",
            help=AJUDA["btn_gravar_placa"],
        )
    if gravar_placa:
        nova_placa = pb.ParametrosDaPlaca(
            comprimento_mm=float(comprimento_placa),
            largura_mm=float(largura_placa),
            espessura_mm=float(espessura_placa),
            aco=str(aco_placa),
            fck_MPa=float(fck_placa),
            razao_a2_a1=float(a2a1_placa),
            chumbadores=int(chumbadores_placa),
            lado_tracionado=int(lado_placa),
            diametro=str(diametro_placa),
            aco_chumbador=str(aco_chumbador_placa),
            distancia_mm=float(distancia_placa) or None,
            elemento_leve=bool(leve_placa),
        )
        erros_placa = pb.validar(nova_placa)
        for erro_placa in erros_placa:
            st.error(erro_placa, icon=":material/error:")
        if not erros_placa and gravar(
            em.com_placa(dados, pb.para_dicionario(nova_placa)), "Esforços do modelo: placa de base"
        ):
            st.rerun()
    base = base_ativa()
    anglo_placa = st.toggle(
        "Aplicar o critério Anglo American",
        value=bool(base and base.anglo),
        key="em_placa_anglo",
        help=AJUDA["placa_anglo"],
    )
    resultados_placa = pb.verificar_placas(dados, plano, placa, anglo=anglo_placa, estados=estados)
    verificadas_placa = [r for r in resultados_placa if r.linhas]
    pior_placa = max(verificadas_placa, key=lambda r: r.utilizacao or 0.0, default=None)
    colunas = st.columns(3)
    colunas[0].metric(
        "Pilares que atendem",
        f"{sum(r.status == 'OK' for r in resultados_placa)} de {len(resultados_placa)}",
        help=AJUDA["res_placas"],
    )
    colunas[1].metric(
        "Maior utilização",
        "—"
        if pior_placa is None or pior_placa.utilizacao is None
        else f"{100 * pior_placa.utilizacao:.0f} %",
        help=AJUDA["res_placas"],
    )
    espessuras = [r.espessura_requerida_mm for r in resultados_placa if r.espessura_requerida_mm]
    colunas[2].metric(
        "Espessura necessária",
        "—" if not espessuras else f"{max(espessuras):.1f} mm".replace(".", ","),
        help=AJUDA["res_placas"],
    )
    perfil_da_figura = next(
        (r.perfil for r in [pior_placa, *resultados_placa] if r and r.perfil in sc.listar_perfis()),
        None,
    )
    if perfil_da_figura is not None and not pb.validar(placa):
        secao = sc.obter_perfil(perfil_da_figura)
        furo, _, _, lado_arruela, _ = ca.CHUMBADORES[placa.diametro]
        st.subheader("A placa", help=AJUDA["res_desenho_placa"])
        st.image(
            svg_placa_de_base(
                comprimento_mm=placa.comprimento_mm,
                largura_mm=placa.largura_mm,
                altura_perfil_mm=secao.altura_mm,
                largura_mesa_mm=secao.largura_mm,
                espessura_mesa_mm=secao.espessura_mesa_mm,
                espessura_alma_mm=secao.espessura_alma_mm,
                chumbadores=placa.chumbadores,
                distancia_mm=placa.distancia_mm or placa.comprimento_mm / 2 - 50,
                furo_mm=furo,
                arruela_mm=lado_arruela,
            ),
            width=470,
        )
        st.caption(
            f"Pilar {perfil_da_figura}; furo e arruela do item 8.7 do critério Anglo para o "
            f"chumbador de {placa.diametro}."
        )
    st.dataframe(
        pd.DataFrame(pb.linhas_da_tabela(resultados_placa), columns=list(pb.COLUNAS)).replace(
            "", None
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Utilização (%)": st.column_config.ProgressColumn(
                min_value=0.0, max_value=100.0, format="%.0f %%"
            ),
            **{
                c: st.column_config.NumberColumn(format="%.2f")
                for c in pb.COLUNAS
                if "(kN" in c or "(mm)" in c
            },
        },
    )
    if verificadas_placa:
        nomes_placa = [r.pilar for r in verificadas_placa]
        escolhido = st.selectbox(
            "Ver o cálculo da placa do pilar",
            nomes_placa,
            index=nomes_placa.index(pior_placa.pilar) if pior_placa is not None else 0,
            key="em_placa_detalhe",
            help=AJUDA["placa_detalhe"],
        )
        detalhe_placa = next(r for r in verificadas_placa if r.pilar == escolhido)
        st.caption(
            f"{detalhe_placa.perfil} · {detalhe_placa.combinacao} · N = {detalhe_placa.n:.2f} kN, "
            f"M = {detalhe_placa.m:.2f} kN·m, V = {detalhe_placa.v:.2f} kN (de cálculo)".replace(
                ".", ","
            )
        )
        mostrar_tabela_verificacoes(list(detalhe_placa.linhas))
    st.download_button(
        "Verificação das placas (CSV)",
        data=pb.csv_das_placas(resultados_placa),
        file_name=f"placas_de_base_{projeto.get('codigo') or 'projeto'}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="em_csv_placas",
        help=AJUDA["btn_csv_placas"],
    )
    st.subheader("Registrar as placas no projeto", help=AJUDA["reg_placas"])
    botao_registrar_calculo(
        pb.registro_das_placas(
            resultados_placa,
            placa,
            anglo=anglo_placa,
            contexto={
                "casos_do_modelo": ", ".join(dados.casos),
                "estados_limites": ", ".join(estados),
            },
        ),
        key="registrar_placas_de_base",
        rotulo="Registrar as placas de base no projeto ativo",
        identificar_peca=False,
    )
