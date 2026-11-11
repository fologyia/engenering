"""Pilares do modelo: todos os pilares do SolidWorks, com os travamentos lidos do esqueleto."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.colunas_do_modelo_help import AJUDA
from components.figuras import mostrar_figura
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import colunas_do_modelo as cdm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import tratamento_do_modelo as tm
from core.desenho_da_coluna import figura_da_coluna
from core.project_store import obter_projeto_ativo

configurar_pagina("Pilares do modelo", ":material/view_column:")
cabecalho_pagina(
    "Pilares do modelo",
    "Todos os pilares do modelo do SolidWorks verificados de uma vez: os travamentos de cada um "
    "saem do esqueleto, em x e em y, e cada trecho recebe o seu K.",
    categoria="Modelo SolidWorks",
    icone=":material/view_column:",
    cor="blue",
    acoes=(
        ("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),
        (
            "app_pages/flambagem_colunas.py",
            "Flambagem de colunas",
            ":material/vertical_align_center:",
        ),
    ),
)
projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos**: os pilares saem do "
        "modelo do SolidWorks gravado no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()
dados = tm.do_projeto(projeto).dados
geometria = ld.geometria_do_projeto(projeto)
faltam = []
if not dados.casos:
    faltam.append("os resultados do SolidWorks (as forças das vigas de cada caso)")
if not geometria.corpos:
    faltam.append("o esqueleto do modelo (o arquivo _esqueleto.csv da macro)")
if faltam:
    st.info(
        "Para achar os travamentos de cada pilar, o projeto precisa de "
        + " e de ".join(faltam)
        + ". Envie em **Esforços do modelo**. Para um pilar só, digitado à mão, use **Flambagem "
        "de colunas**.",
        icon=":material/upload_file:",
    )
    st.page_link(
        "app_pages/esforcos_modelo.py", label="Esforços do modelo", icon=":material/upload_file:"
    )
    st.page_link(
        "app_pages/flambagem_colunas.py",
        label="Flambagem de colunas",
        icon=":material/vertical_align_center:",
    )
    st.stop()

plano = pc.plano_do_projeto(projeto)

with st.container(border=True), secao_protegida("Como os pilares são presos"):
    st.subheader("Como os pilares são presos", help=AJUDA["sec_como"])
    escolhas = st.columns([1.2, 1, 1.6])
    base = escolhas[0].radio(
        "Base dos pilares no apoio",
        cdm.BASES,
        key="cdm_base",
        persist_state="session",
        help=AJUDA["base"],
    )
    recomendado = escolhas[1].toggle(
        "K recomendado da Tabela E.1",
        value=True,
        key="cdm_recomendado",
        persist_state="session",
        help=AJUDA["recomendado"],
    )
    estados = escolhas[2].multiselect(
        "Estados-limite",
        list(comb.COMBINACOES_ULTIMAS),
        default=[comb.ELU_NORMAL],
        key="cdm_estados",
        help=AJUDA["estados"],
    )
    b2 = dados.parametros_do_tipo(ld.TIPO_PILAR).b2
    st.caption(
        "Os nós da estrutura contam como travados de lado. O deslocamento da estrutura inteira "
        f"entra pelo B₂ do tipo Pilar, hoje {f'{b2:.2f}'.replace('.', ',')}, que multiplica todos "
        "os esforços (em Esforços do modelo, parâmetros por tipo)."
    )

if not estados:
    st.stop()

with st.container(border=True), secao_protegida("Pilares do modelo"):
    st.subheader("Pilares do modelo", help=AJUDA["sec_resultado"])
    colunas, avisos = cdm.verificar_colunas(
        dados, geometria, plano, estados, base=base, recomendado=recomendado
    )
    for aviso in em.agrupar_avisos(avisos):
        st.warning(aviso, icon=":material/warning:")
    if not colunas:
        st.info(
            "Nenhum pilar no modelo: nenhuma barra tem o tipo Pilar na tabela das barras nem está "
            "em pé no esqueleto.",
            icon=":material/info:",
        )
        st.stop()
    sintese = cdm.resumo(colunas)
    metricas = st.columns(5)
    metricas[0].metric("Pilares", sintese["total"], help=AJUDA["res_pilares"])
    metricas[1].metric("Atendem", sintese["atendem"], help=AJUDA["res_atendem"])
    metricas[2].metric("Não atendem", sintese["nao_atendem"], help=AJUDA["res_nao"])
    metricas[3].metric("Pendentes", sintese["pendentes"], help=AJUDA["res_pendentes"])
    pior = sintese["pior"]
    metricas[4].metric(
        "Maior aproveitamento",
        "—" if pior is None else f"{100 * (pior.aproveitamento or 0.0):.0f} %",
        help=AJUDA["res_pior"],
    )
    if any(c.posicao for c in colunas):
        st.info(
            "O esqueleto não diz a direção da alma (macro anterior à v5). Em cada pilar, o "
            "programa testou a alma nas duas direções e ficou com a pior. Com a macro nova, cada "
            "travamento vai para o eixo certo.",
            icon=":material/info:",
        )
    st.dataframe(
        pd.DataFrame(cdm.linhas_da_tabela(colunas), columns=list(cdm.COLUNAS)),
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "Pilares do modelo (CSV)",
        data=cdm.csv_das_colunas(colunas),
        file_name=f"pilares_{projeto.get('codigo') or 'projeto'}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="cdm_csv",
        help=AJUDA["csv"],
    )

with st.container(border=True), secao_protegida("O cálculo de um pilar"):
    st.subheader("O cálculo de um pilar", help=AJUDA["sec_detalhe"])
    nomes = [c.barra for c in colunas]
    inicial = nomes.index(pior.barra) if pior is not None else 0
    escolhido = st.selectbox("Pilar", nomes, index=inicial, key="cdm_pilar", help=AJUDA["pilar"])
    coluna = next(c for c in colunas if c.barra == escolhido)
    pilar = coluna.pilar
    if coluna.status == cdm.STATUS_PENDENTE:
        st.warning(f"Pendente: {coluna.motivo}", icon=":material/pending:")
    if pilar is not None:
        partes = [
            f"{coluna.perfil}",
            f"L = {pilar.comprimento_mm / 1000:.2f} m".replace(".", ","),
            f"base: {cdm.NOME_DA_PONTA[pilar.base]}",
        ]
        if coluna.posicao:
            partes.append(f"posição que governou: {coluna.posicao}")
        st.caption(" · ".join(partes))
        for nota in pilar.notas:
            st.caption(f":material/info: {nota[0].upper()}{nota[1:]}.")
        if pilar.travamentos:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Altura da base (m)": t.altura_mm / 1000,
                            "Trava L_x": t.trava_x,
                            "Trava L_y": t.trava_y,
                            "Barras que chegam": t.descricao,
                        }
                        for t in pilar.travamentos
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={"Altura da base (m)": st.column_config.NumberColumn(format="%.2f")},
            )
        else:
            st.caption("Nenhuma barra encosta no pilar entre as pontas: um trecho só em cada eixo.")
    if coluna.eixo_x is not None and coluna.eixo_y is not None:
        linhas = []
        for eixo in (coluna.eixo_x, coluna.eixo_y):
            governa = eixo.indice_que_governa
            for i, trecho in enumerate(eixo.trechos):
                linhas.append(
                    {
                        "Eixo": f"L_{eixo.eixo} (em torno de {eixo.eixo})",
                        "Trecho (m)": f"{trecho.de_mm / 1000:.2f} a {trecho.ate_mm / 1000:.2f}".replace(
                            ".", ","
                        ),
                        "K": trecho.k,
                        "K·L (m)": trecho.kl_mm / 1000,
                        "De onde vem o K": trecho.como,
                        "Governa": "sim" if i == governa else "",
                    }
                )
        st.dataframe(
            pd.DataFrame(linhas),
            hide_index=True,
            width="stretch",
            column_config={
                "K": st.column_config.NumberColumn(format="%.2f"),
                "K·L (m)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    resultado = coluna.resultado
    if resultado is not None:
        st.caption(
            f"Pior caso: {resultado.combinacao}, {resultado.ponto} · N = {resultado.n:.2f} kN, "
            f"M forte = {resultado.m_forte:.2f} kN·m, M fraco = {resultado.m_fraco:.2f} kN·m "
            "(de cálculo, com o B₂)".replace(".", ",")
        )
        mostrar_tabela_verificacoes(list(resultado.linhas))
    if (
        pilar is not None
        and coluna.eixo_x is not None
        and coluna.eixo_y is not None
        and st.toggle(
            "Ver o pilar em pé",
            value=False,
            key="cdm_ver_desenho",
            persist_state="session",
            help=AJUDA["ver_desenho"],
        )
    ):
        em_pe = cdm.coluna_em_pe(coluna)
        if em_pe is None:
            st.caption(
                "Este pilar não tem desenho: a base rotulada com o topo livre não está entre os "
                "casos da Tabela E.1."
            )
        else:
            mostrar_figura(figura_da_coluna(em_pe))

with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["registrar"])
    botao_registrar_calculo(
        cdm.registro_das_colunas(colunas, dados, estados, base=base, recomendado=recomendado),
        key="registrar_colunas_do_modelo",
        rotulo="Registrar a verificação dos pilares no projeto ativo",
        identificar_peca=False,
    )
