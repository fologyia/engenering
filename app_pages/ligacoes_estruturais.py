"""Ligações estruturais: chapa simples viga–viga/viga–pilar, perfil formado a frio e solda de filete."""

from __future__ import annotations

import streamlit as st

from components.ligacoes_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import bolted_connection as bc
from core import ligacoes as lg
from core import section_catalog as sc
from core.project_store import obter_projeto_ativo
from core.verificacao import csv_verificacoes

configurar_pagina("Ligações estruturais", ":material/link:")
cabecalho_pagina(
    "Ligações estruturais",
    "Os casos comuns do mezanino e da escada: chapa simples ligando viga em viga ou em pilar "
    "(NBR 8800), perfil formado a frio parafusado (NBR 14762) e grupo de soldas de filete. "
    "Casos especiais (ligação rígida, chapa de extremidade, enrijecedores) ficam com o projetista.",
    categoria="Dimensionamento complementar",
    icone=":material/link:",
    cor="blue",
    ajuda_modulo="Ligações estruturais",
)

TIPOS = {
    lg.CHAPA_SIMPLES: "Chapa simples (viga–viga e viga–pilar)",
    lg.PERFIL_FRIO: "Perfil formado a frio (NBR 14762)",
    lg.SOLDA: "Solda de filete",
}
FAMILIAS_DE_VIGA = ("W (mesa larga)", "I duplamente simétrico", "U (canal laminado)")
PERFIS_DE_VIGA = [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_DE_VIGA]
PERFIS_FRIOS = [
    *(n for n, p in sc.listar_perfis().items() if p.familia.startswith("C enrijecido")),
    lg.PERFIL_A_MAO,
]
PADRAO_CHAPA = lg.EntradaChapaSimples()
PADRAO_FRIO = lg.EntradaPerfilFrio()
PADRAO_SOLDA = lg.EntradaSolda()


def _indice(opcoes: list[str], valor: str) -> int:
    return opcoes.index(valor) if valor in opcoes else 0


tipo = st.segmented_control(
    "Tipo de ligação",
    list(TIPOS),
    format_func=TIPOS.get,
    default=lg.CHAPA_SIMPLES,
    key="lig_tipo",
    persist_state="session",
    help=AJUDA["tipo"],
)
tipo = tipo or lg.CHAPA_SIMPLES
entrada: lg.EntradaChapaSimples | lg.EntradaPerfilFrio | lg.EntradaSolda

if tipo == lg.CHAPA_SIMPLES:
    with st.container(border=True), secao_protegida("1. A viga e o apoio"):
        st.subheader("1. A viga e o apoio", help=AJUDA["sec_viga"])
        c = st.columns(4)
        perfil = c[0].selectbox(
            "Perfil da viga apoiada",
            PERFIS_DE_VIGA,
            index=_indice(PERFIS_DE_VIGA, PADRAO_CHAPA.perfil),
            key="lig_perfil",
            persist_state="session",
            help=AJUDA["perfil"],
        )
        acos = list(bc.ACOS)
        aco_viga = c[1].selectbox(
            "Aço da viga",
            acos,
            index=_indice(acos, PADRAO_CHAPA.aco_viga),
            key="lig_aco_viga",
            persist_state="session",
            help=AJUDA["aco_viga"],
        )
        apoio = c[2].selectbox(
            "Apoio",
            list(lg.APOIOS),
            format_func=lg.APOIOS.get,
            key="lig_apoio",
            persist_state="session",
            help=AJUDA["apoio"],
        )
        t_apoio = c[3].number_input(
            "Espessura do apoio (mm)",
            0.5,
            100.0,
            PADRAO_CHAPA.t_apoio_mm,
            0.5,
            key="lig_t_apoio",
            persist_state="session",
            help=AJUDA["t_apoio"],
        )
        c = st.columns([1, 1, 1, 1])
        recorte = c[0].toggle(
            "Mesa superior recortada",
            value=PADRAO_CHAPA.recorte,
            key="lig_recorte",
            persist_state="session",
            help=AJUDA["recorte"],
        )
        rec_h = c[1].number_input(
            "Altura do recorte (mm)",
            1.0,
            500.0,
            PADRAO_CHAPA.recorte_altura_mm,
            5.0,
            key="lig_rec_h",
            persist_state="session",
            help=AJUDA["recorte_altura"],
            disabled=not recorte,
        )
        rec_c = c[2].number_input(
            "Comprimento do recorte (mm)",
            1.0,
            2000.0,
            PADRAO_CHAPA.recorte_comprimento_mm,
            5.0,
            key="lig_rec_c",
            persist_state="session",
            help=AJUDA["recorte_comprimento"],
            disabled=not recorte,
        )
        normas = list(lg.NORMAS)
        norma = c[3].selectbox(
            "Norma",
            normas,
            format_func=lg.NORMAS_ROTULOS.get,
            key="lig_norma",
            persist_state="session",
            help=AJUDA["norma"],
        )
    with st.container(border=True), secao_protegida("2. Parafusos"):
        st.subheader("2. Parafusos", help=AJUDA["sec_parafusos"])
        c = st.columns(4)
        parafusos = list(bc.PARAFUSOS)
        parafuso = c[0].selectbox(
            "Parafuso",
            parafusos,
            index=_indice(parafusos, PADRAO_CHAPA.parafuso),
            key="lig_parafuso",
            persist_state="session",
            help=AJUDA["parafuso"],
        )
        graus = list(bc.GRAUS)
        grau = c[1].selectbox(
            "Grau",
            graus,
            key="lig_grau",
            persist_state="session",
            help=AJUDA["grau"],
        )
        n_par = c[2].number_input(
            "Nº de parafusos",
            1,
            12,
            PADRAO_CHAPA.n_parafusos,
            1,
            key="lig_n",
            persist_state="session",
            help=AJUDA["n_parafusos"],
        )
        rosca = c[3].toggle(
            "Rosca no plano de corte",
            value=True,
            key="lig_rosca",
            persist_state="session",
            help=AJUDA["rosca"],
        )
        c = st.columns(5)
        valores = {}
        for coluna, (chave, rotulo, padrao, ajuda) in zip(
            c,
            (
                ("passo", "Passo (mm)", PADRAO_CHAPA.passo_mm, AJUDA["passo"]),
                (
                    "borda_v",
                    "Borda vertical da chapa (mm)",
                    PADRAO_CHAPA.borda_vertical_mm,
                    AJUDA["borda_vertical"],
                ),
                (
                    "a",
                    "Solda até os furos, a (mm)",
                    PADRAO_CHAPA.distancia_solda_furo_mm,
                    AJUDA["a"],
                ),
                (
                    "borda_h",
                    "Borda horizontal da chapa (mm)",
                    PADRAO_CHAPA.borda_horizontal_chapa_mm,
                    AJUDA["borda_horizontal"],
                ),
                (
                    "borda_alma",
                    "Furo à ponta da viga (mm)",
                    PADRAO_CHAPA.borda_alma_mm,
                    AJUDA["borda_alma"],
                ),
            ),
            strict=True,
        ):
            valores[chave] = coluna.number_input(
                rotulo,
                1.0,
                1000.0,
                padrao,
                5.0,
                key=f"lig_{chave}",
                persist_state="session",
                help=ajuda,
            )
        topo = st.columns(5)[0].number_input(
            "Parafuso ao topo da alma (mm)",
            1.0,
            1000.0,
            PADRAO_CHAPA.topo_alma_mm,
            5.0,
            key="lig_topo",
            persist_state="session",
            help=AJUDA["topo_alma"],
        )
    with st.container(border=True), secao_protegida("3. Chapa, solda e esforços"):
        st.subheader("3. Chapa e solda", help=AJUDA["sec_chapa"])
        c = st.columns(4)
        t_chapa = c[0].number_input(
            "Espessura da chapa (mm)",
            1.0,
            50.0,
            PADRAO_CHAPA.t_chapa_mm,
            0.5,
            key="lig_t_chapa",
            persist_state="session",
            help=AJUDA["t_chapa"],
        )
        aco_chapa = c[1].selectbox(
            "Aço da chapa",
            acos,
            index=_indice(acos, PADRAO_CHAPA.aco_chapa),
            key="lig_aco_chapa",
            persist_state="session",
            help=AJUDA["aco_chapa"],
        )
        perna = c[2].number_input(
            "Perna da solda (mm)",
            1.0,
            25.0,
            PADRAO_CHAPA.perna_solda_mm,
            1.0,
            key="lig_perna",
            persist_state="session",
            help=AJUDA["perna"],
        )
        eletrodos = list(lg.ELETRODOS)
        eletrodo = c[3].selectbox(
            "Eletrodo",
            eletrodos,
            index=_indice(eletrodos, "E70"),
            key="lig_eletrodo",
            persist_state="session",
            help=AJUDA["eletrodo"],
        )
        st.subheader("4. Esforços de cálculo", help=AJUDA["sec_esforcos"])
        registradas = lg.reacoes_do_projeto(obter_projeto_ativo())
        if registradas:
            rotulos = [r.rotulo for r in registradas]
            c = st.columns([3, 1])
            escolhida = c[0].selectbox(
                "Trazer de um cálculo registrado",
                rotulos,
                key="lig_origem",
                help=AJUDA["origem"],
            )
            reacao = registradas[rotulos.index(escolhida)]
            c[1].button(
                "Usar esta reação",
                icon=":material/input:",
                key="lig_usar_reacao",
                help=AJUDA["usar_reacao"],
                on_click=st.session_state.update,
                kwargs={"lig_v": round(reacao.v_kN, 2), "lig_n_sd": round(reacao.n_kN, 2)},
            )
        c = st.columns(3)
        v_sd = c[0].number_input(
            "V_Sd (kN)",
            0.0,
            5000.0,
            PADRAO_CHAPA.v_sd_kN,
            1.0,
            key="lig_v",
            persist_state="session",
            help=AJUDA["v_sd"],
        )
        n_sd = c[1].number_input(
            "N_Sd (kN)",
            -5000.0,
            5000.0,
            0.0,
            1.0,
            key="lig_n_sd",
            persist_state="session",
            help=AJUDA["n_sd"],
        )
        anglo = c[2].toggle(
            "Critério Anglo American",
            key="lig_anglo",
            persist_state="session",
            help=AJUDA["anglo"],
        )
    entrada = lg.EntradaChapaSimples(
        perfil=perfil,
        aco_viga=aco_viga,
        apoio=apoio,
        t_apoio_mm=float(t_apoio),
        recorte=bool(recorte),
        recorte_altura_mm=float(rec_h),
        recorte_comprimento_mm=float(rec_c),
        parafuso=parafuso,
        grau=grau,
        rosca_no_plano=bool(rosca),
        n_parafusos=int(n_par),
        passo_mm=float(valores["passo"]),
        borda_vertical_mm=float(valores["borda_v"]),
        distancia_solda_furo_mm=float(valores["a"]),
        borda_horizontal_chapa_mm=float(valores["borda_h"]),
        borda_alma_mm=float(valores["borda_alma"]),
        topo_alma_mm=float(topo),
        t_chapa_mm=float(t_chapa),
        aco_chapa=aco_chapa,
        perna_solda_mm=float(perna),
        eletrodo=eletrodo,
        v_sd_kN=float(v_sd),
        n_sd_kN=float(n_sd),
        norma=norma,
        anglo=bool(anglo),
    )
elif tipo == lg.PERFIL_FRIO:
    with st.container(border=True), secao_protegida("1. Perfil e chapa"):
        st.subheader("1. Perfil e chapa", help=AJUDA["sec_perfil_frio"])
        c = st.columns(4)
        perfil = c[0].selectbox(
            "Perfil",
            PERFIS_FRIOS,
            index=_indice(PERFIS_FRIOS, PADRAO_FRIO.perfil),
            key="lig_f_perfil",
            persist_state="session",
            help=AJUDA["perfil_frio"],
        )
        acos_frio = list(lg.ACOS)
        aco_perfil = c[1].selectbox(
            "Aço do perfil",
            acos_frio,
            index=_indice(acos_frio, PADRAO_FRIO.aco_perfil),
            key="lig_f_aco",
            persist_state="session",
            help=AJUDA["aco_perfil"],
        )
        t_chapa = c[2].number_input(
            "Espessura da chapa (mm)",
            0.5,
            50.0,
            PADRAO_FRIO.t_chapa_mm,
            0.25,
            key="lig_f_t_chapa",
            persist_state="session",
            help=AJUDA["t_chapa_frio"],
        )
        aco_chapa = c[3].selectbox(
            "Aço da chapa",
            acos_frio,
            index=_indice(acos_frio, PADRAO_FRIO.aco_chapa),
            key="lig_f_aco_chapa",
            persist_state="session",
            help=AJUDA["aco_chapa_frio"],
        )
        t_mao = area_mao = x_mao = None
        if perfil == lg.PERFIL_A_MAO:
            c = st.columns(3)
            t_mao = c[0].number_input(
                "Espessura do perfil (mm)",
                0.4,
                8.0,
                3.0,
                0.05,
                key="lig_f_t",
                persist_state="session",
                help=AJUDA["t_perfil"],
            )
            area_mao = c[1].number_input(
                "Área (mm²)",
                10.0,
                20000.0,
                600.0,
                10.0,
                key="lig_f_area",
                persist_state="session",
                help=AJUDA["area_perfil"],
            )
            x_mao = c[2].number_input(
                "x̄ (mm)",
                0.0,
                300.0,
                12.0,
                0.5,
                key="lig_f_x",
                persist_state="session",
                help=AJUDA["x_perfil"],
            )
    with st.container(border=True), secao_protegida("2. Parafusos e furos"):
        st.subheader("2. Parafusos e furos", help=AJUDA["sec_parafusos_frio"])
        c = st.columns(4)
        parafusos = list(bc.PARAFUSOS)
        parafuso = c[0].selectbox(
            "Parafuso",
            parafusos,
            index=_indice(parafusos, PADRAO_FRIO.parafuso),
            key="lig_f_parafuso",
            persist_state="session",
            help=AJUDA["parafuso"],
        )
        especificacao = c[1].selectbox(
            "Especificação",
            list(lg.PARAFUSOS_FRIO),
            key="lig_f_espec",
            persist_state="session",
            help=AJUDA["especificacao"],
        )
        planos = c[2].selectbox(
            "Planos de corte",
            [1, 2],
            key="lig_f_planos",
            persist_state="session",
            help=AJUDA["planos"],
        )
        rosca = c[3].toggle(
            "Rosca no plano de corte",
            value=True,
            key="lig_f_rosca",
            persist_state="session",
            help=AJUDA["rosca"],
        )
        c = st.columns(6)
        n_linhas = c[0].number_input(
            "Linhas", 1, 6, PADRAO_FRIO.n_linhas, 1, key="lig_f_linhas",
            persist_state="session", help=AJUDA["n_linhas"],
        )  # fmt: skip
        n_por_linha = c[1].number_input(
            "Por linha", 1, 12, PADRAO_FRIO.n_por_linha, 1, key="lig_f_por_linha",
            persist_state="session", help=AJUDA["n_por_linha"],
        )  # fmt: skip
        passo = c[2].number_input(
            "Passo s (mm)", 1.0, 500.0, PADRAO_FRIO.passo_mm, 5.0, key="lig_f_passo",
            persist_state="session", help=AJUDA["passo_frio"],
        )  # fmt: skip
        gabarito = c[3].number_input(
            "Gabarito g (mm)", 1.0, 500.0, PADRAO_FRIO.gabarito_mm, 5.0, key="lig_f_g",
            persist_state="session", help=AJUDA["gabarito"],
        )  # fmt: skip
        borda = c[4].number_input(
            "Borda e (mm)", 1.0, 500.0, PADRAO_FRIO.borda_mm, 5.0, key="lig_f_e",
            persist_state="session", help=AJUDA["borda_frio"],
        )  # fmt: skip
        borda_lat = c[5].number_input(
            "Borda lateral e₁ (mm)", 1.0, 500.0, PADRAO_FRIO.borda_lateral_mm, 5.0,
            key="lig_f_e1", persist_state="session", help=AJUDA["borda_lateral"],
        )  # fmt: skip
    with st.container(border=True), secao_protegida("3. Esforços de cálculo"):
        st.subheader("3. Esforços de cálculo", help=AJUDA["sec_esforcos"])
        c = st.columns(4)
        n_sd = c[0].number_input(
            "N_Sd (kN)", -5000.0, 5000.0, PADRAO_FRIO.n_sd_kN, 1.0, key="lig_f_n",
            persist_state="session", help=AJUDA["n_sd_frio"],
        )  # fmt: skip
        v_sd = c[1].number_input(
            "V_Sd (kN)", -5000.0, 5000.0, 0.0, 1.0, key="lig_f_v",
            persist_state="session", help=AJUDA["v_sd_frio"],
        )  # fmt: skip
        barra_axial = c[2].toggle(
            "Barra de treliça ou contraventamento",
            value=True,
            key="lig_f_axial",
            persist_state="session",
            help=AJUDA["barra_axial"],
        )
        n_rd_barra = c[3].number_input(
            "N_Rd da barra (kN)",
            0.0,
            100000.0,
            value=None,
            step=1.0,
            placeholder="a tração calculada",
            key="lig_f_nrd",
            persist_state="session",
            help=AJUDA["n_rd_barra"],
        )
    entrada = lg.EntradaPerfilFrio(
        perfil=perfil,
        t_perfil_mm=t_mao,
        area_perfil_mm2=area_mao,
        excentricidade_mm=x_mao,
        aco_perfil=aco_perfil,
        t_chapa_mm=float(t_chapa),
        aco_chapa=aco_chapa,
        parafuso=parafuso,
        especificacao=especificacao,
        rosca_no_plano=bool(rosca),
        planos_de_corte=int(planos),
        n_linhas=int(n_linhas),
        n_por_linha=int(n_por_linha),
        passo_mm=float(passo),
        gabarito_mm=float(gabarito),
        borda_mm=float(borda),
        borda_lateral_mm=float(borda_lat),
        n_sd_kN=float(n_sd),
        v_sd_kN=float(v_sd),
        barra_axial=bool(barra_axial),
        n_rd_barra_kN=float(n_rd_barra) if n_rd_barra else None,
    )
else:
    with st.container(border=True), secao_protegida("1. Os filetes"):
        st.subheader("1. Os filetes", help=AJUDA["sec_solda"])
        c = st.columns(4)
        arranjo = c[0].selectbox(
            "Arranjo",
            list(lg.ARRANJOS),
            format_func=lg.ARRANJOS.get,
            index=list(lg.ARRANJOS).index(PADRAO_SOLDA.arranjo),
            key="lig_s_arranjo",
            persist_state="session",
            help=AJUDA["arranjo"],
        )
        comprimento = c[1].number_input(
            "Comprimento L (mm)", 5.0, 5000.0, PADRAO_SOLDA.comprimento_mm, 5.0,
            key="lig_s_l", persist_state="session", help=AJUDA["comprimento_solda"],
        )  # fmt: skip
        largura = c[2].number_input(
            "Largura b (mm)", 5.0, 5000.0, PADRAO_SOLDA.largura_mm, 5.0, key="lig_s_b",
            persist_state="session", help=AJUDA["largura_solda"],
            disabled=arranjo == lg.ARRANJO_UM,
        )  # fmt: skip
        perna = c[3].number_input(
            "Perna (mm)", 1.0, 25.0, PADRAO_SOLDA.perna_mm, 1.0, key="lig_s_perna",
            persist_state="session", help=AJUDA["perna_solda"],
        )  # fmt: skip
        c = st.columns(4)
        eletrodos = list(lg.ELETRODOS)
        eletrodo = c[0].selectbox(
            "Eletrodo",
            eletrodos,
            index=_indice(eletrodos, "E70"),
            key="lig_s_eletrodo",
            persist_state="session",
            help=AJUDA["eletrodo"],
        )
        t1 = c[1].number_input(
            "t₁ chapa soldada (mm)", 0.4, 100.0, PADRAO_SOLDA.t1_mm, 0.5, key="lig_s_t1",
            persist_state="session", help=AJUDA["t1"],
        )  # fmt: skip
        t2 = c[2].number_input(
            "t₂ peça que recebe (mm)", 0.4, 100.0, PADRAO_SOLDA.t2_mm, 0.5, key="lig_s_t2",
            persist_state="session", help=AJUDA["t2"],
        )  # fmt: skip
        acos_solda = list(lg.ACOS)
        aco = c[3].selectbox(
            "Aço",
            acos_solda,
            index=_indice(acos_solda, PADRAO_SOLDA.aco),
            key="lig_s_aco",
            persist_state="session",
            help=AJUDA["aco_solda"],
        )
    with st.container(border=True), secao_protegida("2. Esforços de cálculo"):
        st.subheader("2. Esforços de cálculo", help=AJUDA["sec_esforcos"])
        c = st.columns(3)
        v_sd = c[0].number_input(
            "V_Sd (kN)", -5000.0, 5000.0, PADRAO_SOLDA.v_sd_kN, 1.0, key="lig_s_v",
            persist_state="session", help=AJUDA["v_solda"],
        )  # fmt: skip
        n_sd = c[1].number_input(
            "N_Sd (kN)", -5000.0, 5000.0, 0.0, 1.0, key="lig_s_n",
            persist_state="session", help=AJUDA["n_solda"],
        )  # fmt: skip
        m_sd = c[2].number_input(
            "M_Sd (kN·m)", -1000.0, 1000.0, 0.0, 0.1, key="lig_s_m",
            persist_state="session", help=AJUDA["m_solda"],
        )  # fmt: skip
    entrada = lg.EntradaSolda(
        arranjo=arranjo,
        comprimento_mm=float(comprimento),
        largura_mm=float(largura),
        perna_mm=float(perna),
        eletrodo=eletrodo,
        t1_mm=float(t1),
        t2_mm=float(t2),
        aco=aco,
        v_sd_kN=float(v_sd),
        n_sd_kN=float(n_sd),
        m_sd_kNm=float(m_sd),
    )

try:
    resultado = lg.calcular(entrada)
except lg.LigacaoInvalida as erro:
    st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
    st.stop()

st.header("Resultados")
c = st.columns(3)
c[0].metric("Status", resultado.status, help=AJUDA["res_status"])
c[1].metric(
    "Aproveitamento",
    f"{100 * resultado.aproveitamento_maximo:.0f} %",
    help=AJUDA["res_aproveitamento"],
)
governante = resultado.governante
c[2].metric("Governa", governante.nome if governante else "—", help=AJUDA["res_governa"])
for aviso in resultado.avisos:
    st.warning(aviso, icon=":material/warning:")
with secao_protegida("Figura da ligação"):
    st.subheader("A ligação", help=AJUDA["res_figura"])
    desenho = lg.figura(resultado)
    st.image(desenho.png, caption=desenho.legenda, width="stretch")
st.subheader("Verificações", help=AJUDA["res_verificacoes"])
mostrar_tabela_verificacoes(list(resultado.verificacoes))
st.download_button(
    "Verificações (CSV)",
    data=csv_verificacoes(list(resultado.verificacoes)),
    file_name=f"ligacao_{resultado.tipo}_verificacoes.csv",
    mime="text/csv",
    icon=":material/download:",
    key="lig_csv",
    help=AJUDA["btn_csv"],
)
with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        lg.registro_ligacao(resultado),
        key="registrar_ligacao",
        rotulo="Registrar a ligação no projeto ativo",
    )
