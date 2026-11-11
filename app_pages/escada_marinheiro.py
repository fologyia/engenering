"""Escada marinheiro: escada fixa vertical, com ou sem gaiola, pela NR-12 e pela NBR 8800."""

from __future__ import annotations

from typing import Any

import streamlit as st

from components.cena_3d_svg import svg_da_cena
from components.escada_marinheiro_help import AJUDA
from components.figuras import mostrar_figura
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import desenho_escada_marinheiro as dem
from core import escada_marinheiro as em
from core.bolted_connection import ACOS
from core.verificacao import csv_verificacoes

configurar_pagina("Escada marinheiro", ":material/stairs:")
cabecalho_pagina(
    "Escada marinheiro",
    "Escada fixa vertical, com ou sem gaiola: as medidas da NR-12 (Anexo III, item 13), o "
    "degrau e os montantes pela NBR 8800 e as forças nos suportes.",
    categoria="Dimensionamento complementar",
    icone=":material/stairs:",
    cor="blue",
    ajuda_modulo="Escada marinheiro",
)
PADRAO = em.EntradaMarinheiro()


def _numero(rotulo: str, chave: str, minimo: float, maximo: float, padrao: float, passo: float,
            ajuda: str, formato: str = "%.0f", coluna: Any = st) -> float:  # fmt: skip
    return float(
        coluna.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=padrao,
            step=passo,
            format=formato,
            key=chave,
            persist_state="session",
            help=AJUDA[ajuda],
        )
    )


with st.container(border=True), secao_protegida("1. A escada"):
    st.subheader("1. A escada", help=AJUDA["sec_geometria"])
    c = st.columns(4)
    altura = _numero("Altura até o piso de chegada (m)", "em_altura", 0.5, 100.0,
                     PADRAO.altura_m, 0.1, "altura", "%.2f", c[0])  # fmt: skip
    lances = int(
        c[1].number_input(
            "Lances",
            min_value=1,
            max_value=20,
            value=PADRAO.lances,
            step=1,
            key="em_lances",
            persist_state="session",
            help=AJUDA["lances"],
        )
    )
    afastamento_lances = PADRAO.afastamento_entre_lances_mm
    if lances > 1:
        afastamento_lances = _numero("Afastamento entre os lances (mm)", "em_afastamento_lances",
                                     100.0, 3000.0, PADRAO.afastamento_entre_lances_mm, 50.0,
                                     "afastamento_lances", coluna=c[2])  # fmt: skip
    inclinacao = _numero("Inclinação (°)", "em_inclinacao", 45.0, 90.0, PADRAO.inclinacao_graus,
                         1.0, "inclinacao", coluna=c[3])  # fmt: skip
    c = st.columns(5)
    largura = _numero("Largura entre montantes (mm)", "em_largura", 100.0, 1500.0,
                      PADRAO.largura_mm, 10.0, "largura", coluna=c[0])  # fmt: skip
    passo = _numero("Espaçamento das barras (mm)", "em_passo", 100.0, 600.0, PADRAO.passo_mm,
                    10.0, "passo", coluna=c[1])  # fmt: skip
    primeira = _numero("Primeira barra acima do piso (mm)", "em_primeira", 50.0, 1500.0,
                       PADRAO.primeira_barra_mm, 10.0, "primeira_barra", coluna=c[2])  # fmt: skip
    afastamento = _numero("Distância à estrutura (mm)", "em_afastamento", 20.0, 1000.0,
                          PADRAO.afastamento_mm, 10.0, "afastamento", coluna=c[3])  # fmt: skip
    ultrapassa = _numero("Montantes acima do piso (mm)", "em_ultrapassa", 0.0, 3000.0,
                         PADRAO.ultrapassa_mm, 50.0, "ultrapassa", coluna=c[4])  # fmt: skip

with st.container(border=True), secao_protegida("2. Barras (degraus)"):
    st.subheader("2. Barras (degraus)", help=AJUDA["sec_degraus"])
    c = st.columns(3)
    forma = c[0].radio(
        "Forma",
        list(em.FORMAS_DO_DEGRAU),
        horizontal=True,
        key="em_forma",
        persist_state="session",
        help=AJUDA["forma_degrau"],
    )
    degrau = _numero("Diâmetro ou lado (mm)", "em_degrau", 10.0, 80.0, PADRAO.degrau_mm, 0.1,
                     "degrau", "%.1f", c[1])  # fmt: skip
    antiderrapante = c[2].toggle(
        "Barras antiderrapantes",
        value=PADRAO.antiderrapante,
        key="em_antiderrapante",
        persist_state="session",
        help=AJUDA["antiderrapante"],
    )

with st.container(border=True), secao_protegida("3. Gaiola"):
    st.subheader("3. Gaiola", help=AJUDA["sec_gaiola"])
    gaiola = st.toggle(
        "Com gaiola de proteção",
        value=PADRAO.gaiola,
        key="em_gaiola",
        persist_state="session",
        help=AJUDA["gaiola"],
    )
    if altura > em.GAIOLA_EXIGIDA_ACIMA_M and not gaiola:
        st.warning(
            "Acima de 3,50 m a NR-12 exige gaiola (Anexo III, item 13 c).",
            icon=":material/warning:",
        )
    tipo_gaiola, inicio, gaiola_ultrapassa, diametro = (
        PADRAO.tipo_gaiola, PADRAO.inicio_gaiola_mm, PADRAO.gaiola_ultrapassa_mm,
        PADRAO.diametro_gaiola_mm,
    )  # fmt: skip
    verticais, arcos = PADRAO.verticais_mm, PADRAO.arcos_mm
    arco_b, arco_t, vertical_b, vertical_t = (
        PADRAO.arco_b_mm, PADRAO.arco_t_mm, PADRAO.vertical_b_mm, PADRAO.vertical_t_mm,
    )  # fmt: skip
    if gaiola:
        tipo_gaiola = st.radio(
            "Tipo de gaiola",
            list(em.TIPOS_DE_GAIOLA),
            horizontal=True,
            key="em_tipo_gaiola",
            persist_state="session",
            help=AJUDA["tipo_gaiola"],
        )
        c = st.columns(5)
        inicio = _numero("Começa a (mm do piso)", "em_inicio_gaiola", 0.0, 6000.0,
                         PADRAO.inicio_gaiola_mm, 50.0, "inicio_gaiola", coluna=c[0])  # fmt: skip
        gaiola_ultrapassa = _numero("Acima do piso de chegada (mm)", "em_gaiola_ultrapassa", 0.0,
                                    3000.0, PADRAO.gaiola_ultrapassa_mm, 50.0,
                                    "gaiola_ultrapassa", coluna=c[1])  # fmt: skip
        diametro = _numero("Diâmetro (mm)", "em_diametro_gaiola", 300.0, 1500.0,
                           PADRAO.diametro_gaiola_mm, 10.0, "diametro_gaiola", coluna=c[2])  # fmt: skip
        verticais = _numero("Barras verticais a cada (mm)", "em_verticais", 50.0, 1500.0,
                            PADRAO.verticais_mm, 10.0, "verticais", coluna=c[3])  # fmt: skip
        padrao_arcos = (
            PADRAO.arcos_mm if tipo_gaiola == em.GAIOLA_VERTICAIS else em.ARCOS_ESPACAMENTO_MAX_B_MM
        )
        arcos = _numero("Arcos a cada (mm)", f"em_arcos_{em.TIPOS_DE_GAIOLA.index(tipo_gaiola)}",
                        50.0, 3000.0, padrao_arcos, 10.0, "arcos", coluna=c[4])  # fmt: skip
        with st.expander("Barras da gaiola (só para o peso)", icon=":material/scale:"):
            c = st.columns(4)
            arco_b = _numero("Arco: largura (mm)", "em_arco_b", 10.0, 150.0, PADRAO.arco_b_mm,
                             0.5, "arco_b", "%.2f", c[0])  # fmt: skip
            arco_t = _numero("Arco: espessura (mm)", "em_arco_t", 2.0, 30.0, PADRAO.arco_t_mm,
                             0.5, "arco_t", "%.2f", c[1])  # fmt: skip
            vertical_b = _numero("Vertical: largura (mm)", "em_vertical_b", 10.0, 150.0,
                                 PADRAO.vertical_b_mm, 0.5, "vertical_b", "%.2f", c[2])  # fmt: skip
            vertical_t = _numero("Vertical: espessura (mm)", "em_vertical_t", 2.0, 30.0,
                                 PADRAO.vertical_t_mm, 0.5, "vertical_t", "%.2f", c[3])  # fmt: skip

with st.container(border=True), secao_protegida("4. Material e fixação"):
    st.subheader("4. Material e fixação", help=AJUDA["sec_estrutura"])
    c = st.columns(4)
    aco = c[0].selectbox(
        "Aço", list(ACOS), key="em_aco", persist_state="session", help=AJUDA["aco"]
    )
    montante_b = _numero("Montante: largura b (mm)", "em_montante_b", 20.0, 200.0,
                         PADRAO.montante_b_mm, 0.5, "montante_b", "%.2f", c[1])  # fmt: skip
    montante_t = _numero("Montante: espessura t (mm)", "em_montante_t", 3.0, 50.0,
                         PADRAO.montante_t_mm, 0.5, "montante_t", "%.2f", c[2])  # fmt: skip
    fixacoes = _numero("Suportes a cada (mm)", "em_fixacoes", 300.0, 6000.0, PADRAO.fixacoes_mm,
                       100.0, "fixacoes", coluna=c[3])  # fmt: skip
    c = st.columns(2)
    ambiente = c[0].toggle(
        "Ao tempo ou em ambiente corrosivo",
        value=PADRAO.ambiente_agressivo,
        key="em_ambiente",
        persist_state="session",
        help=AJUDA["ambiente"],
    )
    protecao = PADRAO.protecao_contra_corrosao
    if ambiente:
        protecao = c[1].toggle(
            "Com proteção contra corrosão",
            value=PADRAO.protecao_contra_corrosao,
            key="em_protecao",
            persist_state="session",
            help=AJUDA["protecao"],
        )

with st.container(border=True), secao_protegida("5. Cargas"):
    st.subheader("5. Cargas", help=AJUDA["sec_cargas"])
    c = st.columns(2)
    carga = _numero("Carga no degrau (kN)", "em_carga", 0.0, 20.0, PADRAO.carga_degrau_kN, 0.1,
                    "carga_degrau", "%.2f", c[0])  # fmt: skip
    pessoas = int(
        c[1].number_input(
            "Pessoas por lance",
            min_value=0,
            max_value=10,
            value=PADRAO.pessoas_por_lance,
            step=1,
            key="em_pessoas",
            persist_state="session",
            help=AJUDA["pessoas"],
        )
    )

entrada = em.EntradaMarinheiro(
    altura_m=altura,
    lances=lances,
    afastamento_entre_lances_mm=afastamento_lances,
    inclinacao_graus=inclinacao,
    largura_mm=largura,
    passo_mm=passo,
    primeira_barra_mm=primeira,
    afastamento_mm=afastamento,
    ultrapassa_mm=ultrapassa,
    forma_do_degrau=str(forma),
    degrau_mm=degrau,
    antiderrapante=bool(antiderrapante),
    gaiola=bool(gaiola),
    inicio_gaiola_mm=inicio,
    gaiola_ultrapassa_mm=gaiola_ultrapassa,
    diametro_gaiola_mm=diametro,
    tipo_gaiola=str(tipo_gaiola),
    verticais_mm=verticais,
    arcos_mm=arcos,
    arco_b_mm=arco_b,
    arco_t_mm=arco_t,
    vertical_b_mm=vertical_b,
    vertical_t_mm=vertical_t,
    aco=str(aco),
    montante_b_mm=montante_b,
    montante_t_mm=montante_t,
    fixacoes_mm=fixacoes,
    ambiente_agressivo=bool(ambiente),
    protecao_contra_corrosao=bool(protecao),
    carga_degrau_kN=carga,
    pessoas_por_lance=pessoas,
)
erros = em.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
resultado = em.calcular(entrada)

st.header("Resultados")
c = st.columns(4)
c[0].metric("Status", resultado.status, help=AJUDA["res_status"])
c[1].metric(
    "Aproveitamento",
    f"{100 * resultado.aproveitamento_maximo:.0f} %",
    help=AJUDA["res_aproveitamento"],
)
c[2].metric("Barras por lance", resultado.barras_por_lance, help=AJUDA["res_barras"])
c[3].metric("Peso estimado", f"{resultado.peso_total_kg:.0f} kg", help=AJUDA["res_peso"])

with st.container(border=True), secao_protegida("Desenhos"):
    st.subheader("Desenhos", help=AJUDA["res_desenhos"])
    lado = st.columns([3, 2])
    with lado[0]:
        mostrar_figura(svg_da_cena(dem.frente(resultado)))
    with lado[1]:
        mostrar_figura(svg_da_cena(dem.planta(resultado)))

st.subheader("Verificações", help=AJUDA["res_verificacoes"])
mostrar_tabela_verificacoes(list(resultado.verificacoes))
st.caption(
    f"Suportes (de cálculo, por lado): {resultado.suporte_vertical_kN:.2f} kN na vertical e "
    f"{resultado.suporte_momento_kNm:.3f} kN·m na estrutura".replace(".", ",")
    + ".",
    help=AJUDA["res_suportes"],
)

with st.container(border=True):
    st.subheader("Conferir além da conta", help=AJUDA["res_conferir"])
    st.markdown("\n".join(f"- {aviso}" for aviso in resultado.avisos))

st.download_button(
    "Verificações (CSV)",
    data=csv_verificacoes(list(resultado.verificacoes)),
    file_name="escada_marinheiro_verificacoes.csv",
    mime="text/csv",
    icon=":material/download:",
    key="em_csv",
    help=AJUDA["btn_csv"],
)
with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        em.registro(resultado, figuras=dem.figuras_para_o_registro(resultado)),
        key="registrar_escada_marinheiro",
        rotulo="Registrar a escada marinheiro no projeto ativo",
    )
