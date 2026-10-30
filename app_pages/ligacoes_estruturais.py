"""Ligações estruturais: chapa simples, dupla cantoneira, perfil formado a frio e as soldadas."""

from __future__ import annotations

import streamlit as st

from components.ligacoes_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_tabela_verificacoes
from core import bolted_connection as bc
from core import cantoneiras as ct
from core import ligacoes as lg
from core import ligacoes_soldadas as ls
from core import section_catalog as sc
from core import soldas as sd
from core.project_store import obter_projeto_ativo
from core.verificacao import csv_verificacoes

configurar_pagina("Ligações estruturais", ":material/link:")
cabecalho_pagina(
    "Ligações estruturais",
    "Os casos comuns do mezanino e da escada, em duas partes. Parafusadas: chapa simples e dupla "
    "cantoneira ligando viga em viga ou em pilar (NBR 8800) e perfil formado a frio (NBR 14762). "
    "Soldadas: grupo de filetes, barra na chapa de nó e chapa no apoio (filete, penetração total "
    "ou parcial). Casos especiais (ligação rígida, chapa de extremidade, enrijecedores) ficam com "
    "o projetista.",
    categoria="Dimensionamento complementar",
    icone=":material/link:",
    cor="blue",
    ajuda_modulo="Ligações estruturais",
)

PARAFUSADAS = "parafusadas"
SOLDADAS = "soldadas"
PARTES = {PARAFUSADAS: "Ligações parafusadas", SOLDADAS: "Ligações soldadas"}
TIPOS_PARAFUSADOS = {
    lg.CHAPA_SIMPLES: "Chapa simples (viga–viga e viga–pilar)",
    lg.CANTONEIRA_DUPLA: "Dupla cantoneira (viga–viga e viga–pilar)",
    lg.PERFIL_FRIO: "Perfil formado a frio (NBR 14762)",
}
TIPOS_SOLDADOS = {
    lg.SOLDA: "Grupo de filetes no plano",
    lg.BARRA_SOLDADA: "Barra soldada na chapa de nó",
    lg.CHAPA_NO_APOIO: "Chapa soldada no apoio",
}
FAMILIAS_DE_VIGA = ("W (mesa larga)", "I duplamente simétrico", "U (canal laminado)")
PERFIS_DE_VIGA = [n for n, p in sc.listar_perfis().items() if p.familia in FAMILIAS_DE_VIGA]
PERFIS_FRIOS = [
    *(n for n, p in sc.listar_perfis().items() if p.familia.startswith("C enrijecido")),
    lg.PERFIL_A_MAO,
]
PADRAO_CHAPA = lg.EntradaChapaSimples()
PADRAO_CANT = lg.EntradaCantoneiraDupla()
PADRAO_FRIO = lg.EntradaPerfilFrio()
PADRAO_SOLDA = lg.EntradaSolda()
PADRAO_BARRA = ls.EntradaBarraSoldada()
PADRAO_T = ls.EntradaChapaNoApoio()
PERFIS_DE_APOIO = ls.perfis_de_apoio()
CANTONEIRAS = list(ct.CATALOGO_CANTONEIRAS)
LADOS = {2: "Dos dois lados", 1: "De um lado só"}


def _indice(opcoes: list[str], valor: str) -> int:
    return opcoes.index(valor) if valor in opcoes else 0


def _norma_e_combinacao(colunas: list, prefixo: str) -> tuple[str, str]:
    """Norma e combinação (os γ) das ligações soldadas."""
    normas = list(sd.NORMAS)
    norma = colunas[0].selectbox(
        "Norma", normas, format_func=sd.NORMAS_ROTULOS.get, key=f"{prefixo}_norma",
        persist_state="session", help=AJUDA["norma_solda"],
    )  # fmt: skip
    combinacoes = list(sd.COMBINACOES)
    combinacao = colunas[1].selectbox(
        "Combinação de ações", combinacoes, format_func=sd.COMBINACOES.get,
        key=f"{prefixo}_comb", persist_state="session", help=AJUDA["combinacao"],
    )  # fmt: skip
    return norma, combinacao


def _apoio_da_solda(prefixo: str, padrao: ls.EntradaChapaNoApoio | ls.EntradaBarraSoldada, desligado: bool = False) -> dict[str, object]:  # fmt: skip
    """O apoio da chapa soldada: uma chapa qualquer ou a mesa de um perfil I/H do catálogo."""
    c = st.columns(4)
    apoios = list(ls.APOIOS)
    apoio = c[0].selectbox(
        "O apoio", apoios, format_func=ls.APOIOS.get, key=f"{prefixo}_apoio",
        persist_state="session", help=AJUDA["apoio_solda"], disabled=desligado,
    )  # fmt: skip
    perfil = apoio == ls.APOIO_PERFIL
    t_apoio = c[1].number_input(
        "Espessura do apoio (mm)", 1.0, 200.0, padrao.t_apoio_mm, 0.5, key=f"{prefixo}_t_apoio",
        persist_state="session", help=AJUDA["t_apoio_solda"], disabled=desligado or perfil,
    )  # fmt: skip
    acos = list(lg.ACOS)
    aco_apoio = c[2].selectbox(
        "Aço do apoio", acos, index=_indice(acos, padrao.aco_apoio), key=f"{prefixo}_aco_apoio",
        persist_state="session", help=AJUDA["aco_apoio_solda"], disabled=desligado,
    )  # fmt: skip
    perfil_apoio = c[3].selectbox(
        "Perfil do apoio", PERFIS_DE_APOIO, key=f"{prefixo}_perfil_apoio",
        persist_state="session", help=AJUDA["perfil_apoio"], disabled=desligado or not perfil,
    )  # fmt: skip
    c = st.columns(4)
    orientacoes = list(ls.ORIENTACOES)
    orientacao = c[0].selectbox(
        "Posição da chapa na mesa", orientacoes, format_func=ls.ORIENTACOES.get,
        key=f"{prefixo}_orient", persist_state="session", help=AJUDA["orientacao"],
        disabled=desligado or not perfil,
    )  # fmt: skip
    perto = c[1].toggle(
        "Perto da ponta do perfil", key=f"{prefixo}_perto", persist_state="session",
        help=AJUDA["perto_extremidade"], disabled=desligado or not perfil,
    )  # fmt: skip
    return {
        "apoio": apoio,
        "t_apoio_mm": float(t_apoio),
        "aco_apoio": aco_apoio,
        "perfil_apoio": perfil_apoio if perfil else "",
        "orientacao": orientacao,
        "perto_da_extremidade": bool(perto),
    }


parte = st.segmented_control(
    "Parte",
    list(PARTES),
    format_func=PARTES.get,
    default=PARAFUSADAS,
    key="lig_parte",
    persist_state="session",
    help=AJUDA["parte"],
)
# Um seletor de tipo por parte, cada um com a sua chave: voltar a uma parte reencontra o tipo
# que estava escolhido nela.
if parte == SOLDADAS:
    tipo = st.segmented_control(
        "Tipo de ligação soldada",
        list(TIPOS_SOLDADOS),
        format_func=TIPOS_SOLDADOS.get,
        default=lg.SOLDA,
        key="lig_tipo_solda",
        persist_state="session",
        help=AJUDA["tipo_soldada"],
    )
    tipo = tipo or lg.SOLDA
else:
    tipo = st.segmented_control(
        "Tipo de ligação parafusada",
        list(TIPOS_PARAFUSADOS),
        format_func=TIPOS_PARAFUSADOS.get,
        default=lg.CHAPA_SIMPLES,
        key="lig_tipo_parafuso",
        persist_state="session",
        help=AJUDA["tipo_parafusada"],
    )
    tipo = tipo or lg.CHAPA_SIMPLES
entrada: object

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
                "Trazer de um cálculo ou do modelo",
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
elif tipo == lg.CANTONEIRA_DUPLA:
    acos = list(bc.ACOS)
    with st.container(border=True), secao_protegida("1. A viga e o apoio"):
        st.subheader("1. A viga e o apoio", help=AJUDA["sec_viga"])
        c = st.columns(4)
        perfil = c[0].selectbox(
            "Perfil da viga apoiada", PERFIS_DE_VIGA,
            index=_indice(PERFIS_DE_VIGA, PADRAO_CANT.perfil), key="lig_c_perfil",
            persist_state="session", help=AJUDA["perfil"],
        )  # fmt: skip
        aco_viga = c[1].selectbox(
            "Aço da viga", acos, index=_indice(acos, PADRAO_CANT.aco_viga), key="lig_c_aco_viga",
            persist_state="session", help=AJUDA["aco_viga"],
        )  # fmt: skip
        apoio = c[2].selectbox(
            "Apoio", list(lg.APOIOS), format_func=lg.APOIOS.get, key="lig_c_apoio",
            persist_state="session", help=AJUDA["apoio"],
        )  # fmt: skip
        t_apoio = c[3].number_input(
            "Espessura do apoio (mm)", 0.5, 100.0, PADRAO_CANT.t_apoio_mm, 0.5,
            key="lig_c_t_apoio", persist_state="session", help=AJUDA["t_apoio"],
        )  # fmt: skip
        c = st.columns(5)
        aco_apoio = c[0].selectbox(
            "Aço do apoio", acos, index=_indice(acos, PADRAO_CANT.aco_apoio), key="lig_c_aco_apoio",
            persist_state="session", help=AJUDA["aco_apoio"],
        )  # fmt: skip
        recorte = c[1].toggle(
            "Mesa superior recortada", value=PADRAO_CANT.recorte, key="lig_c_recorte",
            persist_state="session", help=AJUDA["recorte"],
        )  # fmt: skip
        rec_h = c[2].number_input(
            "Altura do recorte (mm)", 1.0, 500.0, PADRAO_CANT.recorte_altura_mm, 5.0,
            key="lig_c_rec_h", persist_state="session", help=AJUDA["recorte_altura"],
            disabled=not recorte,
        )  # fmt: skip
        rec_c = c[3].number_input(
            "Comprimento do recorte (mm)", 1.0, 2000.0, PADRAO_CANT.recorte_comprimento_mm, 5.0,
            key="lig_c_rec_c", persist_state="session", help=AJUDA["recorte_comprimento"],
            disabled=not recorte,
        )  # fmt: skip
        normas = list(lg.NORMAS)
        norma = c[4].selectbox(
            "Norma", normas, format_func=lg.NORMAS_ROTULOS.get, key="lig_c_norma",
            persist_state="session", help=AJUDA["norma"],
        )  # fmt: skip
    with st.container(border=True), secao_protegida("2. Cantoneiras e parafusos"):
        st.subheader("2. Cantoneiras e parafusos", help=AJUDA["sec_cantoneiras"])
        c = st.columns(4)
        cantoneiras = list(ct.CATALOGO_CANTONEIRAS)
        cantoneira = c[0].selectbox(
            "Cantoneira", cantoneiras, index=_indice(cantoneiras, PADRAO_CANT.cantoneira),
            key="lig_c_cantoneira", persist_state="session", help=AJUDA["cantoneira"],
        )  # fmt: skip
        aco_cant = c[1].selectbox(
            "Aço das cantoneiras", acos, index=_indice(acos, PADRAO_CANT.aco_cantoneira),
            key="lig_c_aco_cant", persist_state="session", help=AJUDA["aco_cantoneira"],
        )  # fmt: skip
        comprimento = c[2].number_input(
            "Comprimento das cantoneiras (mm)", 20.0, 2000.0, PADRAO_CANT.comprimento_mm, 5.0,
            key="lig_c_comp", persist_state="session", help=AJUDA["comprimento_cantoneira"],
        )  # fmt: skip
        parafusos = list(bc.PARAFUSOS)
        parafuso = c[3].selectbox(
            "Parafuso", parafusos, index=_indice(parafusos, PADRAO_CANT.parafuso),
            key="lig_c_parafuso", persist_state="session", help=AJUDA["parafuso"],
        )  # fmt: skip
        c = st.columns(4)
        grau = c[0].selectbox(
            "Grau", list(bc.GRAUS), key="lig_c_grau", persist_state="session", help=AJUDA["grau"]
        )
        n_par = c[1].number_input(
            "Parafusos por linha", 1, 12, PADRAO_CANT.n_parafusos, 1, key="lig_c_n",
            persist_state="session", help=AJUDA["n_parafusos"],
        )  # fmt: skip
        passo = c[2].number_input(
            "Passo (mm)", 1.0, 1000.0, PADRAO_CANT.passo_mm, 5.0, key="lig_c_passo",
            persist_state="session", help=AJUDA["passo"],
        )  # fmt: skip
        rosca = c[3].toggle(
            "Rosca no plano de corte", value=True, key="lig_c_rosca", persist_state="session",
            help=AJUDA["rosca"],
        )  # fmt: skip
        c = st.columns(5)
        borda_v = c[0].number_input(
            "Borda vertical (mm)", 1.0, 1000.0, PADRAO_CANT.borda_vertical_mm, 5.0,
            key="lig_c_borda_v", persist_state="session", help=AJUDA["borda_vertical"],
        )  # fmt: skip
        g_alma = c[1].number_input(
            "Gabarito na alma (mm)", 1.0, 500.0, PADRAO_CANT.gabarito_alma_mm, 5.0,
            key="lig_c_g_alma", persist_state="session", help=AJUDA["gabarito_alma"],
        )  # fmt: skip
        g_apoio = c[2].number_input(
            "Gabarito no apoio (mm)", 1.0, 500.0, PADRAO_CANT.gabarito_apoio_mm, 5.0,
            key="lig_c_g_apoio", persist_state="session", help=AJUDA["gabarito_apoio"],
        )  # fmt: skip
        borda_alma = c[3].number_input(
            "Furo à ponta da viga (mm)", 1.0, 1000.0, PADRAO_CANT.borda_alma_mm, 5.0,
            key="lig_c_borda_alma", persist_state="session", help=AJUDA["borda_alma"],
        )  # fmt: skip
        topo = c[4].number_input(
            "Parafuso ao topo da alma (mm)", 1.0, 1000.0, PADRAO_CANT.topo_alma_mm, 5.0,
            key="lig_c_topo", persist_state="session", help=AJUDA["topo_alma"],
        )  # fmt: skip
    with st.container(border=True), secao_protegida("3. Esforço de cálculo"):
        st.subheader("3. Esforço de cálculo", help=AJUDA["sec_esforcos"])
        registradas = lg.reacoes_do_projeto(obter_projeto_ativo())
        if registradas:
            rotulos = [r.rotulo for r in registradas]
            c = st.columns([3, 1])
            escolhida = c[0].selectbox(
                "Trazer de um cálculo ou do modelo", rotulos, key="lig_c_origem",
                help=AJUDA["origem"],
            )  # fmt: skip
            c[1].button(
                "Usar esta reação",
                icon=":material/input:",
                key="lig_c_usar_reacao",
                help=AJUDA["usar_reacao"],
                on_click=st.session_state.update,
                kwargs={"lig_c_v": round(registradas[rotulos.index(escolhida)].v_kN, 2)},
            )
        c = st.columns(2)
        v_sd = c[0].number_input(
            "V_Sd (kN)", 0.0, 5000.0, PADRAO_CANT.v_sd_kN, 1.0, key="lig_c_v",
            persist_state="session", help=AJUDA["v_sd"],
        )  # fmt: skip
        anglo = c[1].toggle(
            "Critério Anglo American", key="lig_c_anglo", persist_state="session",
            help=AJUDA["anglo"],
        )  # fmt: skip
    entrada = lg.EntradaCantoneiraDupla(
        perfil=perfil,
        aco_viga=aco_viga,
        apoio=apoio,
        t_apoio_mm=float(t_apoio),
        aco_apoio=aco_apoio,
        recorte=bool(recorte),
        recorte_altura_mm=float(rec_h),
        recorte_comprimento_mm=float(rec_c),
        cantoneira=cantoneira,
        aco_cantoneira=aco_cant,
        comprimento_mm=float(comprimento),
        parafuso=parafuso,
        grau=grau,
        rosca_no_plano=bool(rosca),
        n_parafusos=int(n_par),
        passo_mm=float(passo),
        borda_vertical_mm=float(borda_v),
        gabarito_alma_mm=float(g_alma),
        gabarito_apoio_mm=float(g_apoio),
        borda_alma_mm=float(borda_alma),
        topo_alma_mm=float(topo),
        v_sd_kN=float(v_sd),
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
elif tipo == lg.SOLDA:
    with st.container(border=True), secao_protegida("1. Os filetes"):
        st.subheader("1. Os filetes", help=AJUDA["sec_solda"])
        c = st.columns(3)
        norma_s, comb_s = _norma_e_combinacao(c, "lig_s")
        metodos = list(lg.METODOS_SOLDA)
        metodo = c[2].selectbox(
            "Método",
            metodos,
            format_func=lg.METODOS_SOLDA.get,
            key="lig_s_metodo",
            persist_state="session",
            help=AJUDA["metodo_solda"],
        )
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
        norma=norma_s,
        combinacao=comb_s,
        metodo=metodo,
    )
elif tipo == lg.BARRA_SOLDADA:
    P = PADRAO_BARRA
    with st.container(border=True), secao_protegida("1. A barra e a chapa de nó"):
        st.subheader("1. A barra e a chapa de nó", help=AJUDA["sec_barra"])
        c = st.columns(3)
        modos = list(ls.MODOS)
        modo_b = c[0].selectbox(
            "O que fazer", modos, format_func=ls.MODOS.get, key="lig_b_modo",
            persist_state="session", help=AJUDA["modo"],
        )  # fmt: skip
        norma_b, comb_b = _norma_e_combinacao(c[1:], "lig_b")
        dimensionar = modo_b == ls.MODO_DIMENSIONAR
        c = st.columns(5)
        pecas = list(ls.PECAS)
        peca = c[0].selectbox(
            "A barra", pecas, format_func=ls.PECAS.get, key="lig_b_peca",
            persist_state="session", help=AJUDA["peca"],
        )  # fmt: skip
        e_cant = peca == ls.PECA_CANTONEIRA
        cantoneira = c[1].selectbox(
            "Cantoneira", CANTONEIRAS, index=_indice(CANTONEIRAS, P.cantoneira), key="lig_b_cant",
            persist_state="session", help=AJUDA["cantoneira_barra"], disabled=not e_cant,
        )  # fmt: skip
        largura_b = c[2].number_input(
            "Largura da chapa (mm)", 5.0, 1000.0, P.largura_mm, 5.0, key="lig_b_larg",
            persist_state="session", help=AJUDA["largura_barra"], disabled=e_cant,
        )  # fmt: skip
        t_b = c[3].number_input(
            "Espessura da chapa (mm)", 1.0, 100.0, P.t_peca_mm, 0.5, key="lig_b_t",
            persist_state="session", help=AJUDA["t_barra"], disabled=e_cant,
        )  # fmt: skip
        acos_b = list(lg.ACOS)
        aco_b = c[4].selectbox(
            "Aço da barra", acos_b, index=_indice(acos_b, P.aco_peca), key="lig_b_aco",
            persist_state="session", help=AJUDA["aco_barra"],
        )  # fmt: skip
        c = st.columns(4)
        duas = c[0].toggle(
            "Uma peça de cada lado da chapa de nó", key="lig_b_duas", persist_state="session",
            help=AJUDA["duas_pecas"],
        )  # fmt: skip
        t_no = c[1].number_input(
            "Espessura da chapa de nó (mm)", 1.0, 100.0, P.t_no_mm, 0.5, key="lig_b_tno",
            persist_state="session", help=AJUDA["t_no"],
        )  # fmt: skip
        aco_no = c[2].selectbox(
            "Aço da chapa de nó", acos_b, index=_indice(acos_b, P.aco_no), key="lig_b_aco_no",
            persist_state="session", help=AJUDA["aco_no"],
        )  # fmt: skip
        largura_no = c[3].number_input(
            "Largura da chapa de nó na seção de Whitmore (mm)", 0.0, 3000.0, P.largura_no_mm,
            5.0, key="lig_b_larg_no", persist_state="session", help=AJUDA["largura_no"],
        )  # fmt: skip
    with st.container(border=True), secao_protegida("2. Os filetes da barra"):
        st.subheader("2. Os filetes da barra", help=AJUDA["sec_filetes_barra"])
        c = st.columns(4)
        perna_b = c[0].number_input(
            "Perna (mm)", 1.0, 25.0, P.perna_mm, 1.0, key="lig_b_perna",
            persist_state="session", help=AJUDA["perna_barra"],
        )  # fmt: skip
        eletrodos = list(lg.ELETRODOS)
        eletrodo_b = c[1].selectbox(
            "Eletrodo", eletrodos, index=_indice(eletrodos, P.eletrodo), key="lig_b_eletrodo",
            persist_state="session", help=AJUDA["eletrodo"],
        )  # fmt: skip
        distribuicoes = list(ls.DISTRIBUICOES)
        distribuicao = c[2].selectbox(
            "Comprimentos no dorso e na borda", distribuicoes, format_func=ls.DISTRIBUICOES.get,
            key="lig_b_dist", persist_state="session", help=AJUDA["distribuicao"],
            disabled=not e_cant,
        )  # fmt: skip
        ponta = c[3].toggle(
            "Filete também na ponta da barra", key="lig_b_ponta", persist_state="session",
            help=AJUDA["solda_na_ponta"],
        )  # fmt: skip
        c = st.columns(4)
        l_dorso = c[0].number_input(
            "Filete do dorso (mm)", 5.0, 3000.0, P.l_dorso_mm, 5.0, key="lig_b_la",
            persist_state="session", help=AJUDA["l_dorso"], disabled=dimensionar,
        )  # fmt: skip
        l_borda = c[1].number_input(
            "Filete da borda (mm)", 5.0, 3000.0, P.l_borda_mm, 5.0, key="lig_b_lb",
            persist_state="session", help=AJUDA["l_borda"], disabled=dimensionar,
        )  # fmt: skip
        cobrimento = c[2].number_input(
            "Cobrimento da superposição (mm)", 0.0, 3000.0, P.cobrimento_mm, 5.0,
            key="lig_b_cob", persist_state="session", help=AJUDA["cobrimento"],
        )  # fmt: skip
        passo_b = c[3].number_input(
            "Arredondar para (mm)", 1.0, 50.0, P.passo_arredondamento_mm, 1.0,
            key="lig_b_passo", persist_state="session", help=AJUDA["passo_arredondamento"],
            disabled=not dimensionar,
        )  # fmt: skip
    with st.container(border=True), secao_protegida("3. Esforços de cálculo"):
        st.subheader("3. Esforços de cálculo", help=AJUDA["sec_esforcos_barra"])
        c = st.columns(4)
        n_t = c[0].number_input(
            "Tração N_t,Sd (kN)", 0.0, 20000.0, P.n_t_sd_kN, 1.0, key="lig_b_nt",
            persist_state="session", help=AJUDA["n_t_barra"],
        )  # fmt: skip
        n_c = c[1].number_input(
            "Compressão N_c,Sd (kN)", 0.0, 20000.0, P.n_c_sd_kN, 1.0, key="lig_b_nc",
            persist_state="session", help=AJUDA["n_c_barra"],
        )  # fmt: skip
        minimo_b = c[2].toggle(
            "Mínimo de 45 kN (6.1.5.2)", value=True, key="lig_b_45", persist_state="session",
            help=AJUDA["minimo_45"],
        )  # fmt: skip
        anglo_b = c[3].toggle(
            "Critério Anglo American", key="lig_b_anglo", persist_state="session",
            help=AJUDA["anglo_barra"],
        )  # fmt: skip
        c = st.columns(4)
        k_no = c[0].number_input(
            "K da chapa de nó", 0.5, 3.0, P.k_no, 0.05, key="lig_b_k", persist_state="session",
            help=AJUDA["k_no"], disabled=n_c <= 0,
        )  # fmt: skip
        l_livre = c[1].number_input(
            "Comprimento livre da chapa de nó (mm)", 1.0, 3000.0, P.l_livre_no_mm, 5.0,
            key="lig_b_lliv", persist_state="session", help=AJUDA["l_livre_no"],
            disabled=n_c <= 0,
        )  # fmt: skip
    with st.container(border=True), secao_protegida("4. A chapa de nó soldada no apoio"):
        st.subheader("4. A chapa de nó soldada no apoio", help=AJUDA["sec_apoio_barra"])
        com_apoio = st.toggle(
            "Verificar a solda da chapa de nó no apoio", value=True, key="lig_b_com_apoio",
            persist_state="session", help=AJUDA["com_apoio"],
        )  # fmt: skip
        c = st.columns(4)
        theta = c[0].number_input(
            "Ângulo θ entre a barra e o apoio (°)", 1.0, 90.0, P.theta_graus, 1.0,
            key="lig_b_theta", persist_state="session", help=AJUDA["theta"],
            disabled=not com_apoio,
        )  # fmt: skip
        l_apoio = c[1].number_input(
            "Comprimento da solda no apoio (mm)" if not dimensionar else "Comprimento disponível no apoio (mm)",
            5.0, 5000.0, P.l_apoio_mm, 5.0, key="lig_b_lapoio", persist_state="session",
            help=AJUDA["l_apoio"], disabled=not com_apoio,
        )  # fmt: skip
        perna_apoio = c[2].number_input(
            "Perna no apoio (mm)", 1.0, 25.0, P.perna_apoio_mm, 1.0, key="lig_b_perna_apoio",
            persist_state="session", help=AJUDA["perna_apoio"], disabled=not com_apoio,
        )  # fmt: skip
        excentricidade = c[3].number_input(
            "Excentricidade no apoio (mm)", -2000.0, 2000.0, P.excentricidade_mm, 5.0,
            key="lig_b_exc", persist_state="session", help=AJUDA["excentricidade"],
            disabled=not com_apoio,
        )  # fmt: skip
        apoio_b = _apoio_da_solda("lig_b", P, desligado=not com_apoio)
    entrada = ls.EntradaBarraSoldada(
        norma=norma_b,
        combinacao=comb_b,
        modo=modo_b,
        peca=peca,
        cantoneira=cantoneira,
        largura_mm=float(largura_b),
        t_peca_mm=float(t_b),
        aco_peca=aco_b,
        duas_pecas=bool(duas),
        t_no_mm=float(t_no),
        aco_no=aco_no,
        largura_no_mm=float(largura_no),
        eletrodo=eletrodo_b,
        perna_mm=float(perna_b),
        distribuicao=distribuicao,
        solda_na_ponta=bool(ponta),
        l_dorso_mm=float(l_dorso),
        l_borda_mm=float(l_borda),
        cobrimento_mm=float(cobrimento),
        passo_arredondamento_mm=float(passo_b),
        n_t_sd_kN=float(n_t),
        n_c_sd_kN=float(n_c),
        k_no=float(k_no),
        l_livre_no_mm=float(l_livre),
        minimo_45kN=bool(minimo_b),
        anglo=bool(anglo_b),
        com_apoio=bool(com_apoio),
        theta_graus=float(theta),
        l_apoio_mm=float(l_apoio),
        perna_apoio_mm=float(perna_apoio),
        excentricidade_mm=float(excentricidade),
        **apoio_b,  # type: ignore[arg-type]
    )
else:
    T = PADRAO_T
    with st.container(border=True), secao_protegida("1. A solda"):
        st.subheader("1. A solda", help=AJUDA["sec_chapa_apoio"])
        c = st.columns(4)
        modo_t = c[0].selectbox(
            "O que fazer", list(ls.MODOS), format_func=ls.MODOS.get, key="lig_c2_modo",
            persist_state="session", help=AJUDA["modo_chapa"],
        )  # fmt: skip
        norma_t, comb_t = _norma_e_combinacao(c[1:3], "lig_c2")
        tipos_de_solda = list(ls.TIPOS_DE_SOLDA)
        tipo_solda = c[3].selectbox(
            "Tipo de solda", tipos_de_solda, format_func=ls.TIPOS_DE_SOLDA.get, key="lig_c2_tipo",
            persist_state="session", help=AJUDA["tipo_solda"],
        )  # fmt: skip
        filete = tipo_solda == ls.TIPO_FILETE
        parcial = tipo_solda == ls.TIPO_PARCIAL
        c = st.columns(4)
        lados = c[0].selectbox(
            "Lados da chapa com solda", [2, 1], format_func=LADOS.get, key="lig_c2_lados",
            persist_state="session",
            help=AJUDA["lados"], disabled=tipo_solda == ls.TIPO_TOTAL,
        )  # fmt: skip
        perna_t = c[1].number_input(
            "Perna do filete (mm)", 1.0, 25.0, T.perna_mm, 1.0, key="lig_c2_perna",
            persist_state="session", help=AJUDA["perna_chapa"], disabled=not filete,
        )  # fmt: skip
        profundidade = c[2].number_input(
            "Profundidade do chanfro S (mm)", 1.0, 100.0, T.profundidade_mm, 0.5,
            key="lig_c2_prof", persist_state="session", help=AJUDA["profundidade"],
            disabled=not parcial,
        )  # fmt: skip
        menos3 = c[3].toggle(
            "Garganta = S − 3 mm", key="lig_c2_menos3", persist_state="session",
            help=AJUDA["menos_3mm"], disabled=not parcial,
        )  # fmt: skip
        c = st.columns(4)
        eletrodos = list(lg.ELETRODOS)
        eletrodo_t = c[0].selectbox(
            "Eletrodo", eletrodos, index=_indice(eletrodos, T.eletrodo), key="lig_c2_eletrodo",
            persist_state="session", help=AJUDA["eletrodo"],
        )  # fmt: skip
        intermitente = c[1].toggle(
            "Filete intermitente", value=T.intermitente, key="lig_c2_inter",
            persist_state="session", help=AJUDA["intermitente"], disabled=not filete,
        )  # fmt: skip
        inter = filete and intermitente
        segmento = c[2].number_input(
            "Segmento (mm)", 5.0, 1000.0, T.segmento_mm, 5.0, key="lig_c2_seg",
            persist_state="session", help=AJUDA["segmento"], disabled=not inter,
        )  # fmt: skip
        n_seg = c[3].number_input(
            "Segmentos por linha", 1, 50, T.n_segmentos, 1, key="lig_c2_nseg",
            persist_state="session", help=AJUDA["n_segmentos"],
            disabled=not inter or modo_t == ls.MODO_DIMENSIONAR,
        )  # fmt: skip
    with st.container(border=True), secao_protegida("2. A chapa e o apoio"):
        st.subheader("2. A chapa e o apoio", help=AJUDA["sec_chapa_e_apoio"])
        c = st.columns(4)
        t_t = c[0].number_input(
            "Espessura da chapa (mm)", 1.0, 200.0, T.t_chapa_mm, 0.5, key="lig_c2_t",
            persist_state="session", help=AJUDA["t_chapa_apoio"],
        )  # fmt: skip
        acos_t = list(lg.ACOS)
        aco_t = c[1].selectbox(
            "Aço da chapa", acos_t, index=_indice(acos_t, T.aco_chapa), key="lig_c2_aco",
            persist_state="session", help=AJUDA["aco_chapa_apoio"],
        )  # fmt: skip
        comprimento_t = c[2].number_input(
            "Comprimento da junta (mm)", 5.0, 5000.0, T.comprimento_mm, 5.0, key="lig_c2_l",
            persist_state="session", help=AJUDA["comprimento_junta"],
        )  # fmt: skip
        passo_t = c[3].number_input(
            "Arredondar para (mm)", 1.0, 50.0, T.passo_arredondamento_mm, 1.0,
            key="lig_c2_passo", persist_state="session", help=AJUDA["passo_arredondamento"],
            disabled=modo_t != ls.MODO_DIMENSIONAR,
        )  # fmt: skip
        apoio_t = _apoio_da_solda("lig_c2", T)
    with st.container(border=True), secao_protegida("3. Esforços de cálculo"):
        st.subheader("3. Esforços de cálculo", help=AJUDA["sec_esforcos_chapa"])
        c = st.columns(4)
        n_t2 = c[0].number_input(
            "N_Sd normal ao apoio (kN)", -20000.0, 20000.0, T.n_sd_kN, 1.0, key="lig_c2_n",
            persist_state="session", help=AJUDA["n_chapa"],
        )  # fmt: skip
        v_t2 = c[1].number_input(
            "V_Sd ao longo da solda (kN)", -20000.0, 20000.0, T.v_sd_kN, 1.0, key="lig_c2_v",
            persist_state="session", help=AJUDA["v_chapa"],
        )  # fmt: skip
        m_t2 = c[2].number_input(
            "M_Sd no plano da chapa (kN·m)", -5000.0, 5000.0, T.m_sd_kNm, 0.1, key="lig_c2_m",
            persist_state="session", help=AJUDA["m_chapa"],
        )  # fmt: skip
        minimo_t = c[3].toggle(
            "Mínimo de 45 kN (6.1.5.2)", value=True, key="lig_c2_45", persist_state="session",
            help=AJUDA["minimo_45"],
        )  # fmt: skip
    entrada = ls.EntradaChapaNoApoio(
        norma=norma_t,
        combinacao=comb_t,
        modo=modo_t,
        tipo_solda=tipo_solda,
        lados=int(lados),
        t_chapa_mm=float(t_t),
        aco_chapa=aco_t,
        comprimento_mm=float(comprimento_t),
        perna_mm=float(perna_t),
        profundidade_mm=float(profundidade),
        descontar_3mm=bool(menos3),
        eletrodo=eletrodo_t,
        intermitente=bool(inter),
        segmento_mm=float(segmento),
        n_segmentos=int(n_seg),
        passo_arredondamento_mm=float(passo_t),
        n_sd_kN=float(n_t2),
        v_sd_kN=float(v_t2),
        m_sd_kNm=float(m_t2),
        minimo_45kN=bool(minimo_t),
        **apoio_t,  # type: ignore[arg-type]
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
g = resultado.grandezas
adotados: list[tuple[str, str]] = []
if "perna_necessaria_mm" in g:
    adotados.append(("Perna necessária", f"{g['perna_necessaria_mm']:.1f} mm".replace(".", ",")))
if resultado.tipo == lg.BARRA_SOLDADA:
    adotados += [
        ("Filete do dorso", f"{g['l_dorso_mm']:.0f} mm"),
        ("Filete da borda", f"{g['l_borda_mm']:.0f} mm"),
        ("Seção de Whitmore", f"{g['largura_whitmore_mm']:.0f} mm"),
    ]
    if "l_apoio_mm" in g:
        adotados.append(("Solda no apoio", f"{g['l_apoio_mm']:.0f} mm de cada lado"))
if resultado.tipo == lg.CHAPA_NO_APOIO:
    if "n_segmentos" in g:
        texto = f"{g['n_segmentos']:.0f} × {g['segmento_mm']:.0f} mm por linha"
    else:
        texto = f"{g['comprimento_efetivo_mm']:.0f} mm"
    adotados.append(("Solda", texto))
if adotados:
    c = st.columns(len(adotados))
    for coluna, (rotulo, valor) in zip(c, adotados, strict=True):
        coluna.metric(rotulo, valor, help=AJUDA["res_adotado"])
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
with st.container(border=True), secao_protegida("Memorial desta ligação"):
    st.subheader("Memorial desta ligação", help=AJUDA["sec_memorial"])
    projeto_ativo = obter_projeto_ativo()
    botoes = st.columns(2)
    botoes[0].download_button(
        "Baixar o memorial (Word)",
        data=lambda: lg.memorial_da_ligacao(resultado, projeto=projeto_ativo),
        file_name=f"memorial_ligacao_{resultado.tipo}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:",
        width="stretch",
        on_click="ignore",
        key="lig_memorial_word",
        help=AJUDA["btn_memorial_word"],
    )
    botoes[1].download_button(
        "Baixar o memorial (PDF)",
        data=lambda: lg.memorial_da_ligacao(resultado, projeto=projeto_ativo, formato="pdf"),
        file_name=f"memorial_ligacao_{resultado.tipo}.pdf",
        mime="application/pdf",
        icon=":material/picture_as_pdf:",
        width="stretch",
        on_click="ignore",
        key="lig_memorial_pdf",
        help=AJUDA["btn_memorial_pdf"],
    )
with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        lg.registro_ligacao(resultado),
        key="registrar_ligacao",
        rotulo="Registrar a ligação no projeto ativo",
    )
