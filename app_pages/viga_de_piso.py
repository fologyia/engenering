"""Vigas de piso de plataforma: a viga que apoia a grade, pela NBR 8800 e pelo critério Anglo."""

from __future__ import annotations

import streamlit as st

from components.base_tecnica_ui import base_ativa, legenda_da_base
from components.figuras_estrutura import svg_viga_de_piso
from components.project_tools import botao_registrar_calculo
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from components.viga_de_piso_help import AJUDA
from core import column_buckling as cbk
from core import section_catalog as sc
from core import viga_de_piso as vp
from core.contraventamento_barras import ACOS
from core.verificacao import csv_verificacoes

configurar_pagina("Vigas de piso", ":material/view_week:")
cabecalho_pagina(
    "Vigas de piso",
    "A viga que apoia a grade da plataforma: combinações da NBR 8800, flexão com flambagem "
    "lateral, cortante, flecha (critério Anglo e NBR), reação para a ligação e o perfil mais leve.",
    categoria="Dimensionamento complementar",
    icone=":material/view_week:",
    cor="blue",
    ajuda_modulo="Vigas de piso",
)
base = base_ativa()
legenda_da_base(base)
FAMILIAS_DE_VIGA = (
    "W (mesa larga)",
    "U (canal laminado)",
    "I duplamente simétrico",
    "HP (perfil de estaca)",
)
perfis = [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_DE_VIGA]


def _sessao(chave: str, valor: object) -> None:
    if chave not in st.session_state:
        st.session_state[chave] = valor


_sessao("vp_perfil", vp.EntradaVigaDePiso().perfil)
_sessao("vp_sc", float(base.sobrecarga_kN_m2) if base else 5.0)
_sessao("vp_anglo", bool(base and base.anglo))

with st.container(border=True):
    st.subheader("1. Perfil", help=AJUDA["sec_perfil"])
    colunas = st.columns([2, 1, 2])
    perfil = colunas[0].selectbox(
        "Perfil", perfis, key="vp_perfil", persist_state="session", help=AJUDA["perfil"]
    )
    aco = colunas[1].selectbox(
        "Aço",
        list(ACOS),
        index=list(ACOS).index("ASTM A572 Gr 50"),
        key="vp_aco",
        persist_state="session",
        help=AJUDA["aco"],
    )
    tipo = colunas[2].radio(
        "Tipo", list(vp.TIPOS), key="vp_tipo", persist_state="session", help=AJUDA["tipo"]
    )

with st.container(border=True):
    st.subheader("2. Vão e faixa de piso", help=AJUDA["sec_geometria"])
    colunas = st.columns(3)
    vao = colunas[0].number_input(
        "Vão (m)",
        0.3,
        30.0,
        4.0,
        0.1,
        format="%.2f",
        key="vp_vao",
        persist_state="session",
        help=AJUDA["vao"],
    )
    largura = colunas[1].number_input(
        "Largura de influência (m)",
        0.05,
        15.0,
        1.0,
        0.05,
        format="%.2f",
        key="vp_largura",
        persist_state="session",
        help=AJUDA["largura"],
    )
    travada = colunas[2].toggle(
        "Mesa travada pela grade", key="vp_travada", persist_state="session", help=AJUDA["travada"]
    )
    lb = None
    if travada:
        lb = st.number_input(
            "Espaçamento entre pontos travados (m)",
            0.05,
            float(vao),
            min(1.0, float(vao)),
            0.05,
            format="%.2f",
            key="vp_lb",
            persist_state="session",
            help=AJUDA["lb"],
        )

with st.container(border=True):
    st.subheader("3. Cargas (características)", help=AJUDA["sec_cargas"])
    colunas = st.columns(4)
    pe = colunas[0].number_input(
        "Piso e acessórios (kN/m²)",
        0.0,
        50.0,
        0.45,
        0.05,
        format="%.2f",
        key="vp_pe",
        persist_state="session",
        help=AJUDA["pe"],
    )
    sc_ = colunas[1].number_input(
        "Sobrecarga (kN/m²)",
        0.0,
        100.0,
        step=0.5,
        format="%.2f",
        key="vp_sc",
        persist_state="session",
        help=AJUDA["sc"],
    )
    linear = colunas[2].number_input(
        "Carga linear extra (kN/m)",
        0.0,
        100.0,
        0.0,
        0.1,
        format="%.2f",
        key="vp_linear",
        persist_state="session",
        help=AJUDA["linear"],
    )
    concentrada = colunas[3].number_input(
        "Equipamento no meio do vão (kN)",
        0.0,
        1000.0,
        0.0,
        1.0,
        format="%.1f",
        key="vp_concentrada",
        persist_state="session",
        help=AJUDA["concentrada"],
    )

with st.container(border=True):
    st.subheader("4. Critério", help=AJUDA["sec_criterio"])
    colunas = st.columns(2)
    anglo = colunas[0].toggle(
        "Aplicar o critério Anglo American",
        key="vp_anglo",
        persist_state="session",
        help=AJUDA["anglo"],
    )
    normas = list(cbk.NORMAS)
    norma = colunas[1].selectbox(
        "Norma",
        normas,
        index=normas.index("NBR8800_2024"),
        format_func=lambda n: cbk.NORMAS_ROTULOS.get(n, n),
        key="vp_norma",
        persist_state="session",
        help=AJUDA["norma"],
    )

entrada = vp.EntradaVigaDePiso(
    perfil=perfil,
    aco=aco,
    vao_m=float(vao),
    largura_influencia_m=float(largura),
    lb_m=float(lb) if lb else None,
    pe_kN_m2=float(pe),
    sc_kN_m2=float(sc_),
    linear_extra_kN_m=float(linear),
    concentrada_kN=float(concentrada),
    tipo=tipo,
    norma=norma,
    anglo=anglo,
)
erros = vp.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
resultado = vp.calcular(entrada)

st.header("Resultados")
colunas = st.columns(4)
colunas[0].metric("Status", resultado.status, help=AJUDA["res_status"])
colunas[1].metric(
    "Aproveitamento",
    f"{100 * resultado.aproveitamento_maximo:.0f} %",
    help=AJUDA["res_aproveitamento"],
)
colunas[2].metric(
    "M_Sd / M_Rd (kN·m)",
    f"{resultado.momento_sd_kNm:.1f} / {resultado.momento_rd_kNm:.1f}".replace(".", ","),
    help=AJUDA["res_momento"],
)
colunas[3].metric(
    "Flecha",
    f"{resultado.flecha_mm:.1f} mm (L/{vao * 1000 / resultado.flecha_mm:.0f})".replace(".", ","),
    help=AJUDA["res_flecha"],
)
st.subheader("A viga", help=AJUDA["res_desenho"])
st.image(
    svg_viga_de_piso(
        vao,
        sum(resultado.cargas_kN_m.values()),
        concentrada,
        resultado.flecha_mm,
        resultado.reacao_caracteristica_kN,
    ),
    width="stretch",
)
st.caption(
    f"Peso próprio {resultado.peso_proprio_kN_m:.3f} kN/m · momento: {resultado.combinacao_momento}"
    f" · C_b = {resultado.cb:.2f}, L_b = {resultado.lb_m:.2f} m (cargas características no "
    "desenho)".replace(".", ",")
)
st.subheader("Verificações", help=AJUDA["res_verificacoes"])
mostrar_tabela_verificacoes(list(resultado.verificacoes))

mais_leve = vp.perfil_mais_leve(entrada)
with st.container(border=True):
    st.subheader("Perfil mais leve que atende", help=AJUDA["res_mais_leve"])
    if mais_leve is None:
        st.warning(
            "Nenhum perfil da mesma família atende com estes dados: mude a família, o vão ou a "
            "faixa de piso.",
            icon=":material/warning:",
        )
    else:
        nome, r_leve = mais_leve
        st.write(
            f"**{nome}** — {sc.obter_perfil(nome).massa_kg_m:.1f} kg/m, aproveitamento "
            f"{100 * r_leve.aproveitamento_maximo:.0f} %.".replace(".", ",", 1)
        )
        if nome != perfil:
            st.button(
                f"Adotar {nome}",
                icon=":material/swap_horiz:",
                key="vp_adotar",
                help=AJUDA["btn_adotar"],
                on_click=st.session_state.update,
                kwargs={"vp_perfil": nome},
            )

st.download_button(
    "Verificações (CSV)",
    data=csv_verificacoes(list(resultado.verificacoes)),
    file_name="viga_de_piso_verificacoes.csv",
    mime="text/csv",
    icon=":material/download:",
    key="vp_csv",
    help=AJUDA["btn_csv"],
)
with st.container(border=True):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        vp.registro_viga(resultado),
        key="registrar_viga_de_piso",
        rotulo="Registrar a viga de piso no projeto ativo",
    )
