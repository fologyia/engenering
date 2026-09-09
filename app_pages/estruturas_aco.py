import math
import sys
from dataclasses import asdict
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina, fronteira_modelo
from core import bolt_design as parafusos
from core import load_combinations as combinacoes
from core import steel_connections as ligacoes
from core import steel_member_design as barras
from core import steel_sections as secoes
from core import structural_2d as estrutural


st.set_page_config(
    page_title="Estruturas de aço",
    page_icon=":material/domain:",
    layout="wide",
)


def fator_texto(valor: float) -> str:
    return "∞" if math.isinf(valor) else f"{valor:.2f}"


def mostrar_utilizacao(nome: str, utilizacao: float) -> None:
    if utilizacao <= 1.0:
        st.success(
            f"{nome}: utilização {utilizacao:.3f} — atende ao modelo informado.",
            icon=":material/check_circle:",
        )
    else:
        st.error(
            f"{nome}: utilização {utilizacao:.3f} — resistência excedida.",
            icon=":material/error:",
        )


cabecalho_pagina(
    "Estruturas de aço",
    "Perfis • barras • combinações ELU/ELS • ligações • treliças e pórticos 2D",
    categoria="Projetos",
    icone=":material/domain:",
    cor="violet",
    ajuda_modulo="Estruturas de aço",
    acoes=(("app_pages/projeto_parafusos.py", "Projeto de parafusos", ":material/build:"),),
    modulo_id="estruturas_aco",
)
st.session_state.setdefault("estrutura_aco_modulo", "1. Perfis")
st.session_state.setdefault("estrutura_nd_kN", 100.0)
st.session_state.setdefault("estrutura_mdx_kNm", 20.0)
st.session_state.setdefault("estrutura_vd_kN", 20.0)
st.session_state.setdefault("estrutura_comprimento_m", 3.0)

st.warning(
    "Ferramenta de pré-dimensionamento. Os coeficientes normativos são "
    "editáveis e devem ser conferidos na NBR 8800:2024, NBR 8681:2025 e "
    "demais normas aplicáveis. A responsabilidade do projeto permanece com "
    "profissional habilitado.",
    icon=":material/gavel:",
)

modulo = st.segmented_control(
    "Módulo",
    ["1. Perfis", "2. Barras", "3. Combinações", "4. Ligações", "5. Análise 2D"],
    required=True,
    width="stretch",
    key="estrutura_aco_modulo",
    persist_state="session",
)


if modulo == "1. Perfis":
    st.header("Catálogo geométrico de perfis")
    st.info(
        "Os perfis são idealizações geométricas, não tabelas comerciais. "
        "Raios de concordância e tolerâncias não estão incluídos.",
        icon=":material/info:",
    )
    catalogo = secoes.catalogo_dataframe()
    familias = sorted(catalogo["familia"].unique())
    familia = st.selectbox(
        "Família", ["Todas"] + familias, key="estrutura_perfil_familia_filtro",
        persist_state="session",
    )
    filtrado = (
        catalogo
        if familia == "Todas"
        else catalogo[catalogo["familia"] == familia]
    )
    tabela_catalogo = pd.DataFrame(
        {
            "Perfil": filtrado["nome"],
            "Família": filtrado["familia"],
            "Massa (kg/m)": filtrado["massa_kg_m"],
            "Área (cm²)": filtrado["area_mm2"] / 100.0,
            "Ix (cm⁴)": filtrado["ix_mm4"] / 10_000.0,
            "Iy (cm⁴)": filtrado["iy_mm4"] / 10_000.0,
            "Sx (cm³)": filtrado["sx_mm3"] / 1_000.0,
            "Zx (cm³)": filtrado["zx_mm3"] / 1_000.0,
            "rx (cm)": filtrado["rx_mm"] / 10.0,
            "ry (cm)": filtrado["ry_mm"] / 10.0,
        }
    )
    st.dataframe(
        tabela_catalogo,
        hide_index=True,
        column_config={
            coluna: st.column_config.NumberColumn(format="%.3f")
            for coluna in tabela_catalogo.columns
            if coluna not in {"Perfil", "Família"}
        },
    )

    nome_perfil = st.selectbox(
        "Inspecionar perfil",
        list(secoes.CATALOGO_PERFIS),
        key="estrutura_perfil_selecionado",
        persist_state="session",
    )
    perfil = secoes.obter_perfil(nome_perfil)
    with st.container(border=True):
        st.subheader(perfil.nome)
        with st.container(horizontal=True):
            st.metric("Massa", f"{perfil.massa_kg_m:.2f} kg/m", border=True)
            st.metric("Área", f"{perfil.area_mm2 / 100:.2f} cm²", border=True)
            st.metric("Ix", f"{perfil.ix_mm4 / 1e4:.1f} cm⁴", border=True)
            st.metric("Iy", f"{perfil.iy_mm4 / 1e4:.1f} cm⁴", border=True)
            st.metric("Zx", f"{perfil.zx_mm3 / 1e3:.1f} cm³", border=True)
        propriedades = pd.DataFrame(
            {
                "Propriedade": [
                    "Sx", "Sy", "Zx", "Zy", "rx", "ry", "J", "Cw", "Área de cisalhamento"
                ],
                "Valor": [
                    perfil.sx_mm3 / 1e3,
                    perfil.sy_mm3 / 1e3,
                    perfil.zx_mm3 / 1e3,
                    perfil.zy_mm3 / 1e3,
                    perfil.rx_mm / 10,
                    perfil.ry_mm / 10,
                    perfil.j_mm4 / 1e4,
                    perfil.cw_mm6 / 1e6,
                    perfil.area_cisalhamento_mm2 / 100,
                ],
                "Unidade": [
                    "cm³", "cm³", "cm³", "cm³", "cm", "cm", "cm⁴", "cm⁶", "cm²"
                ],
            }
        )
        st.dataframe(
            propriedades,
            hide_index=True,
            column_config={
                "Valor": st.column_config.NumberColumn(format="%.4g")
            },
        )
        st.caption(perfil.descricao)

    with st.expander(
        "Criar perfil paramétrico personalizado",
        icon=":material/tune:",
    ):
        familia_custom = st.segmented_control(
            "Geometria",
            [
                "I simétrico",
                "W mesa larga",
                "U (canal)",
                "C enrijecido",
                "T (tê)",
                "Tubo retangular",
                "Tubo circular",
                "Barra retangular",
                "Barra circular",
            ],
            default="I simétrico",
            required=True,
            width="stretch",
            key="estrutura_perfil_custom_familia",
            persist_state="session",
        )
        try:
            if familia_custom == "I simétrico":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=300.0, key="estrutura_custom_i_h"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=150.0, key="estrutura_custom_i_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=6.5, key="estrutura_custom_i_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=10.0, key="estrutura_custom_i_tf"
                )
                custom = secoes.perfil_i_simetrico("Personalizado", h, b, tw, tf)
            elif familia_custom == "W mesa larga":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=300.0, key="estrutura_custom_w_h"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=300.0, key="estrutura_custom_w_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=10.0, key="estrutura_custom_w_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=15.0, key="estrutura_custom_w_tf"
                )
                custom = secoes.perfil_w_mesa_larga("Personalizado", h, b, tw, tf)
            elif familia_custom == "U (canal)":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=150.0, key="estrutura_custom_u_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=75.0, key="estrutura_custom_u_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=6.5, key="estrutura_custom_u_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=9.5, key="estrutura_custom_u_tf"
                )
                custom = secoes.perfil_u("Personalizado", h, b, tw, tf)
            elif familia_custom == "C enrijecido":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=150.0, key="estrutura_custom_c_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=50.0, key="estrutura_custom_c_b"
                )
                d = dimensoes[2].number_input(
                    "aba enrijecedora (mm)", 0.1, value=17.0, key="estrutura_custom_c_d"
                )
                t = dimensoes[3].number_input(
                    "t (mm)", 0.1, value=3.0, key="estrutura_custom_c_t"
                )
                custom = secoes.perfil_c_enrijecido("Personalizado", h, b, d, t)
            elif familia_custom == "T (tê)":
                dimensoes = st.columns(4)
                d = dimensoes[0].number_input(
                    "altura total (mm)", 1.0, value=150.0, key="estrutura_custom_t_d"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=150.0, key="estrutura_custom_t_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=7.5, key="estrutura_custom_t_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=10.5, key="estrutura_custom_t_tf"
                )
                custom = secoes.perfil_t("Personalizado", d, b, tw, tf)
            elif familia_custom == "Barra circular":
                d = st.number_input(
                    "Diâmetro (mm)", 1.0, value=25.0, key="estrutura_custom_barra_circular_d"
                )
                custom = secoes.barra_circular("Personalizado", d)
            elif familia_custom == "Tubo retangular":
                dimensoes = st.columns(3)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=100.0, key="estrutura_custom_tubo_ret_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=50.0, key="estrutura_custom_tubo_ret_b"
                )
                t = dimensoes[2].number_input(
                    "t (mm)", 0.1, value=3.0, key="estrutura_custom_tubo_ret_t"
                )
                custom = secoes.tubo_retangular("Personalizado", h, b, t)
            elif familia_custom == "Tubo circular":
                dimensoes = st.columns(2)
                d = dimensoes[0].number_input(
                    "D (mm)", 1.0, value=114.3, key="estrutura_custom_tubo_circ_d"
                )
                t = dimensoes[1].number_input(
                    "t (mm)", 0.1, value=4.5, key="estrutura_custom_tubo_circ_t"
                )
                custom = secoes.tubo_circular("Personalizado", d, t)
            else:
                dimensoes = st.columns(2)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=100.0, key="estrutura_custom_barra_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=20.0, key="estrutura_custom_barra_b"
                )
                custom = secoes.barra_retangular("Personalizado", h, b)
        except ValueError as erro:
            st.error(str(erro))
        else:
            with st.container(horizontal=True):
                st.metric("Área", f"{custom.area_mm2 / 100:.3f} cm²", border=True)
                st.metric("Massa", f"{custom.massa_kg_m:.3f} kg/m", border=True)
                st.metric("Ix", f"{custom.ix_mm4 / 1e4:.3f} cm⁴", border=True)
                st.metric("Iy", f"{custom.iy_mm4 / 1e4:.3f} cm⁴", border=True)


elif modulo == "2. Barras":
    st.header("Verificação de barras isoladas")
    nome_perfil = st.selectbox(
        "Perfil",
        list(secoes.CATALOGO_PERFIS),
        key="estrutura_barra_perfil",
        persist_state="session",
    )
    perfil = secoes.obter_perfil(nome_perfil)

    with st.container(border=True):
        st.subheader("Material e esforços de cálculo")
        material = st.columns(4)
        fy = material[0].number_input(
            "Fy (MPa)", 1.0, value=250.0, step=10.0, key="estrutura_barra_fy"
        )
        fu = material[1].number_input(
            "Fu (MPa)", 1.0, value=400.0, step=10.0, key="estrutura_barra_fu"
        )
        e = material[2].number_input(
            "E (GPa)", 1.0, value=200.0, step=5.0, key="estrutura_barra_e"
        )
        g = material[3].number_input(
            "G (GPa)", 1.0, value=77.0, step=1.0, key="estrutura_barra_g"
        )
        if fu < fy:
            st.error("Fu deve ser maior ou igual a Fy.")
            st.stop()
        tipo_axial = st.segmented_control(
            "Solicitação axial",
            ["Tração", "Compressão"],
            default="Compressão",
            required=True,
            width="stretch",
            key="estrutura_barra_tipo_axial",
            persist_state="session",
        )
        esforcos = st.columns(4)
        nd_kN = esforcos[0].number_input(
            "|Nd| (kN)", 0.0, step=10.0, key="estrutura_nd_kN"
        )
        mdx_kNm = esforcos[1].number_input(
            "|Mdx| (kN·m)", 0.0, step=5.0, key="estrutura_mdx_kNm"
        )
        mdy_kNm = esforcos[2].number_input(
            "|Mdy| (kN·m)", 0.0, value=0.0, step=5.0, key="estrutura_mdy_kNm"
        )
        vd_kN = esforcos[3].number_input(
            "|Vd| (kN)", 0.0, step=5.0, key="estrutura_vd_kN"
        )

    with st.container(border=True):
        st.subheader("Comprimentos e reduções")
        estabilidade = st.columns(4)
        comprimento_m = estabilidade[0].number_input(
            "Comprimento L (m)",
            0.001,
            step=0.25,
            key="estrutura_comprimento_m",
        )
        kx = estabilidade[1].number_input(
            "Kx", 0.01, value=1.0, step=0.1, key="estrutura_kx"
        )
        ky = estabilidade[2].number_input(
            "Ky", 0.01, value=1.0, step=0.1, key="estrutura_ky"
        )
        lb_m = estabilidade[3].number_input(
            "Comprimento destravado Lb (m)",
            0.001,
            value=3.0,
            step=0.25,
            key="estrutura_lb_m",
        )
        reducoes = st.columns(4)
        q_local = reducoes[0].number_input(
            "Redução local Q", 0.01, 1.0, value=1.0, step=0.05, key="estrutura_q_local"
        )
        cv = reducoes[1].number_input(
            "Redução de cisalhamento Cv",
            0.01,
            1.0,
            value=1.0,
            step=0.05,
            key="estrutura_cv",
        )
        cb = reducoes[2].number_input(
            "Cb", 0.01, value=1.0, step=0.1, key="estrutura_cb"
        )
        area_liquida_pct = reducoes[3].number_input(
            "Área líquida / bruta (%)",
            1.0,
            100.0,
            value=90.0,
            step=1.0,
            key="estrutura_area_liquida_pct",
        )
        ct = st.number_input(
            "Coeficiente de redução da área líquida Ct",
            0.01,
            1.0,
            value=1.0,
            step=0.05,
            key="estrutura_ct",
            persist_state="session",
        )

    with st.expander("Coeficientes de resistência", icon=":material/settings:"):
        coef = st.columns(5)
        phi_y = coef[0].number_input(
            "φ escoamento", 0.01, 1.0, value=0.90, key="estrutura_phi_y"
        )
        phi_u = coef[1].number_input(
            "φ ruptura", 0.01, 1.0, value=0.75, key="estrutura_phi_u"
        )
        phi_c = coef[2].number_input(
            "φ compressão", 0.01, 1.0, value=0.90, key="estrutura_phi_c"
        )
        phi_b = coef[3].number_input(
            "φ flexão", 0.01, 1.0, value=0.90, key="estrutura_phi_b"
        )
        phi_v = coef[4].number_input(
            "φ cisalhamento", 0.01, 1.0, value=0.90, key="estrutura_phi_v"
        )

    try:
        if tipo_axial == "Tração":
            axial = barras.verificar_tracao(
                perfil,
                fy,
                fu,
                perfil.area_mm2 * area_liquida_pct / 100,
                ct,
                nd_kN * 1e3,
                phi_y,
                phi_u,
            )
            resistencia_axial = axial.resistencia_governante_N
            utilizacao_axial = axial.utilizacao
            modo_axial = axial.modo_governante
        else:
            axial = barras.verificar_compressao(
                perfil,
                fy,
                e * 1e3,
                comprimento_m * 1e3,
                kx,
                ky,
                q_local,
                nd_kN * 1e3,
                phi_c,
            )
            resistencia_axial = axial.resistencia_N
            utilizacao_axial = axial.utilizacao
            modo_axial = "Flambagem global/local"
        flexao = barras.verificar_flexao_cisalhamento(
            perfil,
            fy,
            e * 1e3,
            g * 1e3,
            lb_m * 1e3,
            mdx_kNm * 1e6,
            vd_kN * 1e3,
            cb,
            q_local,
            cv,
            phi_b,
            phi_v,
        )
        resistencia_my = phi_b * q_local * fy * perfil.zy_mm3
        interacao = barras.verificar_interacao(
            nd_kN * 1e3,
            resistencia_axial,
            mdx_kNm * 1e6,
            flexao.resistencia_flexao_Nmm,
            mdy_kNm * 1e6,
            resistencia_my,
        )
    except ValueError as erro:
        st.error(f"Não foi possível verificar a barra: {erro}")
        st.stop()

    st.subheader("Resistências e utilização")
    with st.container(horizontal=True):
        st.metric(
            f"Resistência axial — {modo_axial}",
            f"{resistencia_axial / 1e3:.1f} kN",
            border=True,
        )
        st.metric(
            "Resistência à flexão x",
            f"{flexao.resistencia_flexao_Nmm / 1e6:.2f} kN·m",
            border=True,
        )
        st.metric(
            "Resistência ao cisalhamento",
            f"{flexao.resistencia_cisalhamento_N / 1e3:.1f} kN",
            border=True,
        )
        st.metric(
            "Índice de interação",
            f"{interacao.indice_interacao:.3f}",
            border=True,
        )
    mostrar_utilizacao("Esforço axial", utilizacao_axial)
    mostrar_utilizacao("Flexão no eixo x", flexao.utilizacao_momento)
    mostrar_utilizacao("Cisalhamento", flexao.utilizacao_cisalhamento)
    mostrar_utilizacao("Interação N–Mx–My", interacao.indice_interacao)

    if tipo_axial == "Compressão":
        detalhes = pd.DataFrame(
            {
                "Parâmetro": ["KL/rx", "KL/ry", "λ₀", "χ", "Ne,x", "Ne,y"],
                "Valor": [
                    axial.esbeltez_x,
                    axial.esbeltez_y,
                    axial.indice_esbeltez_reduzido,
                    axial.fator_reducao_chi,
                    axial.carga_euler_x_N / 1e3,
                    axial.carga_euler_y_N / 1e3,
                ],
                "Unidade": ["—", "—", "—", "—", "kN", "kN"],
            }
        )
        st.dataframe(
            detalhes,
            hide_index=True,
            column_config={"Valor": st.column_config.NumberColumn(format="%.3f")},
        )

    with st.expander(
        "Estado-limite de serviço — flecha",
        icon=":material/straighten:",
    ):
        els = st.columns(4)
        condicao = els[0].selectbox("Viga", ["Biapoiada", "Balanço"])
        q_servico = els[1].number_input(
            "Carga distribuída de serviço (kN/m)", 0.0, value=5.0
        )
        p_servico = els[2].number_input(
            "Carga concentrada de serviço (kN)", 0.0, value=0.0
        )
        limite_relativo = els[3].number_input(
            "Limite L/divisor", 1.0, value=300.0
        )
        flecha = barras.verificar_deflexao_viga(
            perfil,
            e * 1e3,
            comprimento_m * 1e3,
            q_servico,
            p_servico * 1e3,
            condicao,
            limite_relativo,
        )
        with st.container(horizontal=True):
            st.metric("Flecha", f"{flecha.deflexao_total_mm:.2f} mm", border=True)
            st.metric("Limite", f"{flecha.limite_mm:.2f} mm", border=True)
            st.metric(
                "Relação obtida",
                "∞" if math.isinf(flecha.razao_vao_deflexao) else f"L/{flecha.razao_vao_deflexao:.0f}",
                border=True,
            )
        mostrar_utilizacao("Flecha", flecha.utilizacao)

    st.caption(
        "Q, Cv, Cb, comprimentos efetivos e coeficientes φ devem ser "
        "determinados conforme a seção e as condições de contorno reais."
    )

    utilizacao_governante = max(
        utilizacao_axial,
        flexao.utilizacao_momento,
        flexao.utilizacao_cisalhamento,
        interacao.indice_interacao,
        flecha.utilizacao,
    )
    status_barra = "Atende" if utilizacao_governante <= 1.0 else "Não atende"
    registro_barra = construir_registro_tecnico(
        modulo="Estruturas de aço",
        modulo_id="estruturas_aco",
        titulo=f"Verificação da barra {nome_perfil}",
        status=status_barra,
        resumo="Pré-dimensionamento de barra isolada sob esforço axial, flexão, cisalhamento, interação e flecha.",
        entradas={
            "perfil": nome_perfil,
            "solicitacao_axial": tipo_axial,
            "Fy_MPa": fy,
            "Fu_MPa": fu,
            "E_GPa": e,
            "Nd_kN": nd_kN,
            "Mdx_kNm": mdx_kNm,
            "Mdy_kNm": mdy_kNm,
            "Vd_kN": vd_kN,
            "comprimento_m": comprimento_m,
            "Kx": kx,
            "Ky": ky,
            "Lb_m": lb_m,
            "Q": q_local,
            "Cv": cv,
            "Cb": cb,
        },
        resultados={
            "resistencia_axial_kN": resistencia_axial / 1e3,
            "resistencia_flexao_kNm": flexao.resistencia_flexao_Nmm / 1e6,
            "resistencia_cisalhamento_kN": flexao.resistencia_cisalhamento_N / 1e3,
            "utilizacao_axial": utilizacao_axial,
            "utilizacao_flexao": flexao.utilizacao_momento,
            "utilizacao_cisalhamento": flexao.utilizacao_cisalhamento,
            "utilizacao_interacao": interacao.indice_interacao,
            "utilizacao_flecha": flecha.utilizacao,
            "utilizacao_maxima": utilizacao_governante,
            "flecha_mm": flecha.deflexao_total_mm,
            "limite_flecha_mm": flecha.limite_mm,
        },
        premissas=[
            "Perfil idealizado geometricamente; tolerâncias e raios devem ser conferidos.",
            "Coeficientes de resistência, comprimentos efetivos e reduções são entradas do usuário.",
        ],
        alertas=[] if utilizacao_governante <= 1.0 else ["Ao menos uma utilização supera 100%."],
        referencias=["ABNT NBR 8800 — confirmar edição, cláusulas, classificação da seção e estados-limites aplicáveis."],
        conclusao=(
            f"Maior índice de utilização = {utilizacao_governante:.3f}; o pré-dimensionamento atende."
            if utilizacao_governante <= 1.0
            else f"Maior índice de utilização = {utilizacao_governante:.3f}; o pré-dimensionamento não atende."
        ),
    )
    botao_registrar_calculo(
        registro_barra,
        key="registrar_estrutura_barra",
        rotulo="Registrar verificação da barra no projeto",
    )


elif modulo == "3. Combinações":
    st.header("Combinações editáveis de ações")
    st.info(
        "Os valores padrão são apenas um exemplo. Substitua γ e ψ pelos "
        "coeficientes aplicáveis à categoria da ação e à situação de projeto.",
        icon=":material/edit_note:",
    )
    acoes_padrao = pd.DataFrame(
        [
            ["G", "Permanente", 50.0, 10.0, 20.0, 1.40, 1.0, 1.0, 1.0],
            ["Q", "Variável", 30.0, 5.0, 15.0, 1.40, 0.7, 0.5, 0.3],
            ["W+", "Variável", 0.0, 20.0, 40.0, 1.40, 0.6, 0.3, 0.0],
            ["W−", "Variável", 0.0, -20.0, -40.0, 1.40, 0.6, 0.3, 0.0],
        ],
        columns=["nome", "tipo", "N (kN)", "V (kN)", "M (kN·m)", "γ", "ψ0", "ψ1", "ψ2"],
    )
    editadas = st.data_editor(
        acoes_padrao,
        num_rows="dynamic",
        hide_index=True,
        key="estrutura_acoes_editor",
        column_config={
            "tipo": st.column_config.SelectboxColumn(
                options=["Permanente", "Variável"],
                required=True,
            ),
            "γ": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "ψ0": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
            "ψ1": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
            "ψ2": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
        },
    )
    try:
        lista_acoes = [
            combinacoes.AcaoEstrutural(
                nome=str(linha["nome"]),
                tipo=str(linha["tipo"]),
                n_kN=float(linha["N (kN)"]),
                v_kN=float(linha["V (kN)"]),
                m_kNm=float(linha["M (kN·m)"]),
                gamma=float(linha["γ"]),
                psi0=float(linha["ψ0"]),
                psi1=float(linha["ψ1"]),
                psi2=float(linha["ψ2"]),
            )
            for _, linha in editadas.dropna().iterrows()
        ]
        resultados = combinacoes.gerar_combinacoes(lista_acoes)
    except (ValueError, TypeError) as erro:
        st.error(f"Revise a tabela: {erro}")
        st.stop()

    tabela_resultados = pd.DataFrame([asdict(item) for item in resultados]).rename(
        columns={
            "nome": "Combinação",
            "estado_limite": "Estado-limite",
            "acao_principal": "Ação principal",
            "n_kN": "N (kN)",
            "v_kN": "V (kN)",
            "m_kNm": "M (kN·m)",
            "expressao": "Expressão",
        }
    )
    st.dataframe(
        tabela_resultados,
        hide_index=True,
        column_config={
            "N (kN)": st.column_config.NumberColumn(format="%.3f"),
            "V (kN)": st.column_config.NumberColumn(format="%.3f"),
            "M (kN·m)": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    with st.container(horizontal=True):
        st.metric(
            "Maior |N|",
            f"{tabela_resultados['N (kN)'].abs().max():.2f} kN",
            border=True,
        )
        st.metric(
            "Maior |V|",
            f"{tabela_resultados['V (kN)'].abs().max():.2f} kN",
            border=True,
        )
        st.metric(
            "Maior |M|",
            f"{tabela_resultados['M (kN·m)'].abs().max():.2f} kN·m",
            border=True,
        )
    st.caption(
        "O envelope de cada esforço pode vir de combinações diferentes. "
        "Não combine máximos independentes como se fossem simultâneos."
    )
    registro_combinacoes = construir_registro_tecnico(
        modulo="Estruturas de aço",
        modulo_id="estruturas_aco",
        titulo="Combinações de ações ELU e ELS",
        status="Calculado",
        resumo="Geração de combinações editáveis e envelope de esforços para uso nas verificações estruturais.",
        entradas={
            "acoes": [asdict(item) for item in lista_acoes],
            "numero_acoes": len(lista_acoes),
        },
        resultados={
            "maior_N_absoluto_kN": float(tabela_resultados["N (kN)"].abs().max()),
            "maior_V_absoluto_kN": float(tabela_resultados["V (kN)"].abs().max()),
            "maior_M_absoluto_kNm": float(tabela_resultados["M (kN·m)"].abs().max()),
            "numero_combinacoes": len(resultados),
            "combinacoes": [asdict(item) for item in resultados],
        },
        premissas=["Coeficientes gama e psi foram informados pelo usuário para cada ação."],
        alertas=["Os máximos independentes do envelope podem pertencer a combinações diferentes."],
        referencias=["ABNT NBR 8681 e documentos de carregamento — confirmar edição e coeficientes aplicáveis."],
        conclusao="Combinações geradas; selecionar casos simultâneos governantes para cada verificação.",
    )
    botao_registrar_calculo(
        registro_combinacoes,
        key="registrar_estrutura_combinacoes",
        rotulo="Registrar combinações no projeto",
        tipo="secondary",
    )


elif modulo == "4. Ligações":
    st.header("Ligações estruturais")
    tipo_ligacao = st.segmented_control(
        "Verificação",
        ["Parafusos", "Chapa e bloco", "Solda de filete"],
        default="Parafusos",
        required=True,
        width="stretch",
        key="estrutura_ligacao_tipo",
        persist_state="session",
    )

    if tipo_ligacao == "Parafusos":
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.page_link(
                "app_pages/projeto_parafusos.py",
                label="Abrir projeto detalhado da junta",
                icon=":material/open_in_new:",
            )
        escolha_rosca = st.selectbox(
            "Rosca",
            list(parafusos.ROSCAS_METRICAS),
            index=list(parafusos.ROSCAS_METRICAS).index("M20"),
            key="estrutura_ligacao_rosca",
            persist_state="session",
        )
        rosca = parafusos.obter_rosca(escolha_rosca)
        classe_nome = st.selectbox(
            "Classe",
            list(parafusos.CLASSES_PARAFUSO),
            index=list(parafusos.CLASSES_PARAFUSO).index("8.8"),
            key="estrutura_ligacao_classe",
            persist_state="session",
        )
        try:
            classe = parafusos.obter_classe(classe_nome, rosca.diametro_mm)
        except ValueError as erro:
            st.error(str(erro))
            st.stop()
        dados = st.columns(4)
        n_parafusos = dados[0].number_input(
            "Número de parafusos", 1, value=4, key="estrutura_lig_n_parafusos"
        )
        planos = dados[1].number_input(
            "Planos de corte", 1, value=1, key="estrutura_lig_planos"
        )
        vd = dados[2].number_input(
            "|Vd| (kN)", 0.0, value=100.0, key="estrutura_lig_vd"
        )
        td = dados[3].number_input(
            "|Td| (kN)", 0.0, value=20.0, key="estrutura_lig_td"
        )
        chapa = st.columns(4)
        t = chapa[0].number_input(
            "Espessura da chapa (mm)", 0.1, value=10.0, key="estrutura_lig_t"
        )
        fu_chapa = chapa[1].number_input(
            "Fu da chapa (MPa)", 1.0, value=400.0, key="estrutura_lig_fu_chapa"
        )
        lc = chapa[2].number_input(
            "Distância livre Lc na direção da força (mm)",
            0.1,
            value=30.0,
            key="estrutura_lig_lc",
        )
        pre_tensao = chapa[3].number_input(
            "Pré-tensão por parafuso (kN)",
            0.0,
            value=50.0,
            key="estrutura_lig_pre_tensao",
        )
        atrito = st.columns(2)
        mu = atrito[0].number_input(
            "Coeficiente de atrito", 0.0, value=0.30, key="estrutura_lig_mu"
        )
        interfaces = atrito[1].number_input(
            "Interfaces de atrito", 1, value=1, key="estrutura_lig_interfaces"
        )
        with st.expander("Coeficientes da ligação", icon=":material/settings:"):
            cs = st.columns(4)
            cnv = cs[0].number_input(
                "Coef. cisalhamento", 0.01, value=0.48, key="estrutura_lig_cnv"
            )
            cnt = cs[1].number_input(
                "Coef. tração", 0.01, value=0.75, key="estrutura_lig_cnt"
            )
            phi_b = cs[2].number_input(
                "φ parafuso", 0.01, 1.0, value=0.75, key="estrutura_lig_phi_b"
            )
            phi_c = cs[3].number_input(
                "φ contato", 0.01, 1.0, value=0.75, key="estrutura_lig_phi_c"
            )
            cc = st.columns(3)
            c_lc = cc[0].number_input(
                "Coef. Lc", 0.01, value=1.20, key="estrutura_lig_c_lc"
            )
            c_lim = cc[1].number_input(
                "Coef. limite contato", 0.01, value=2.40, key="estrutura_lig_c_lim"
            )
            phi_s = cc[2].number_input(
                "φ deslizamento", 0.01, 1.0, value=1.0, key="estrutura_lig_phi_s"
            )
        resultado = ligacoes.verificar_ligacao_parafusada(
            int(n_parafusos),
            rosca.area_tracao_mm2,
            classe.ruptura_min_MPa,
            cnv,
            cnt,
            phi_b,
            int(planos),
            vd * 1e3,
            td * 1e3,
            t,
            fu_chapa,
            rosca.diametro_mm,
            lc,
            c_lc,
            c_lim,
            phi_c,
            pre_tensao * 1e3,
            mu,
            int(interfaces),
            phi_s,
        )
        criterios = pd.DataFrame(
            {
                "Modo": [
                    "Cisalhamento dos parafusos",
                    "Tração dos parafusos",
                    "Pressão de contato/rasgamento",
                    "Deslizamento",
                ],
                "Resistência (kN)": [
                    resultado.resistencia_cisalhamento_parafusos_N / 1e3,
                    resultado.resistencia_tracao_parafusos_N / 1e3,
                    resultado.resistencia_pressao_contato_N / 1e3,
                    resultado.resistencia_deslizamento_N / 1e3,
                ],
                "Fator": [
                    resultado.fator_cisalhamento,
                    resultado.fator_tracao,
                    resultado.fator_contato,
                    resultado.fator_deslizamento,
                ],
            }
        )
        st.dataframe(
            criterios,
            hide_index=True,
            column_config={
                "Resistência (kN)": st.column_config.NumberColumn(format="%.2f"),
                "Fator": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        st.metric(
            "Interação quadrática tração–cisalhamento",
            f"{resultado.interacao_parafuso:.3f}",
            border=True,
        )
        mostrar_utilizacao(
            "Interação dos parafusos",
            resultado.interacao_parafuso,
        )

    elif tipo_ligacao == "Chapa e bloco":
        material = st.columns(3)
        fy = material[0].number_input(
            "Fy da chapa (MPa)", 1.0, value=250.0, key="estrutura_bloco_fy"
        )
        fu = material[1].number_input(
            "Fu da chapa (MPa)", 1.0, value=400.0, key="estrutura_bloco_fu"
        )
        sd = material[2].number_input(
            "|Sd| (kN)", 0.0, value=100.0, key="estrutura_bloco_sd"
        )
        areas = st.columns(4)
        ant = areas[0].number_input(
            "An de tração (mm²)", 0.1, value=800.0, key="estrutura_bloco_ant"
        )
        agv = areas[1].number_input(
            "Agv do bloco (mm²)", 0.1, value=1200.0, key="estrutura_bloco_agv"
        )
        anv = areas[2].number_input(
            "Anv do bloco (mm²)", 0.1, value=900.0, key="estrutura_bloco_anv"
        )
        antb = areas[3].number_input(
            "Ant do bloco (mm²)", 0.1, value=400.0, key="estrutura_bloco_antb"
        )
        fatores = st.columns(2)
        ubs = fatores[0].number_input(
            "Ubs", 0.01, 1.0, value=1.0, key="estrutura_bloco_ubs"
        )
        phi = fatores[1].number_input(
            "φ ruptura", 0.01, 1.0, value=0.75, key="estrutura_bloco_phi"
        )
        resultado = ligacoes.verificar_chapa_ligacao(
            fu, fy, ant, agv, anv, antb, ubs, phi, sd * 1e3
        )
        with st.container(horizontal=True):
            st.metric(
                "Seção líquida",
                f"{resultado.resistencia_secao_liquida_N / 1e3:.1f} kN",
                border=True,
            )
            st.metric(
                "Cisalhamento de bloco",
                f"{resultado.resistencia_cisalhamento_bloco_N / 1e3:.1f} kN",
                border=True,
            )
        mostrar_utilizacao(
            "Ruptura da seção líquida",
            1.0 / resultado.fator_secao_liquida
            if not math.isinf(resultado.fator_secao_liquida)
            else 0.0,
        )
        mostrar_utilizacao(
            "Cisalhamento de bloco",
            1.0 / resultado.fator_cisalhamento_bloco
            if not math.isinf(resultado.fator_cisalhamento_bloco)
            else 0.0,
        )

    else:
        solda = st.columns(4)
        perna = solda[0].number_input(
            "Perna da solda a (mm)", 0.1, value=6.0, key="estrutura_solda_perna"
        )
        comprimento = solda[1].number_input(
            "Comprimento total efetivo (mm)",
            0.1,
            value=300.0,
            key="estrutura_solda_comprimento",
        )
        fexx = solda[2].number_input(
            "FEXX (MPa)", 1.0, value=490.0, key="estrutura_solda_fexx"
        )
        sd = solda[3].number_input(
            "|Sd| (kN)", 0.0, value=100.0, key="estrutura_solda_sd"
        )
        coef = st.columns(2)
        c_solda = coef[0].number_input(
            "Coeficiente resistente", 0.01, value=0.60, key="estrutura_solda_c_solda"
        )
        phi = coef[1].number_input(
            "φ solda", 0.01, 1.0, value=0.75, key="estrutura_solda_phi"
        )
        resultado = ligacoes.verificar_solda_filete(
            perna, comprimento, fexx, c_solda, phi, sd * 1e3
        )
        with st.container(horizontal=True):
            st.metric(
                "Garganta efetiva",
                f"{0.707 * perna:.2f} mm",
                border=True,
            )
            st.metric(
                "Área efetiva",
                f"{resultado.area_efetiva_mm2:.1f} mm²",
                border=True,
            )
            st.metric(
                "Resistência",
                f"{resultado.resistencia_N / 1e3:.1f} kN",
                border=True,
            )
            st.metric(
                "Fator",
                fator_texto(resultado.fator_seguranca),
                border=True,
            )
        mostrar_utilizacao(
            "Solda de filete",
            1.0 / resultado.fator_seguranca
            if not math.isinf(resultado.fator_seguranca)
            else 0.0,
        )

    st.caption(
        "Os coeficientes padrão são valores preliminares. Confirme furação, "
        "distâncias mínimas, parafusos estruturais, soldabilidade e inspeção."
    )


else:
    st.header("Análise elástica linear 2D")
    st.warning(
        "O solver é de primeira ordem, com pequenas deformações. Não inclui "
        "P–Δ, imperfeições, ligações semirrígidas, flambagem ou não linearidade.",
        icon=":material/warning:",
    )
    modelo = st.segmented_control(
        "Modelo estrutural",
        ["Treliça 2D", "Pórtico 2D"],
        default="Treliça 2D",
        required=True,
        width="stretch",
        key="estrutura_2d_modelo",
        persist_state="session",
    )
    perfil_padrao = "I ideal 200×100×5.5×8"
    if modelo == "Treliça 2D":
        nos_padrao = pd.DataFrame(
            [
                [1, 0.0, 0.0, True, True, 0.0, 0.0],
                [2, 4.0, 0.0, False, True, 0.0, 0.0],
                [3, 2.0, 3.0, False, False, 0.0, -100.0],
            ],
            columns=["id", "x (m)", "y (m)", "fixa x", "fixa y", "Fx (kN)", "Fy (kN)"],
        )
        elementos_padrao = pd.DataFrame(
            [
                [1, 1, 2, perfil_padrao, 200.0],
                [2, 1, 3, perfil_padrao, 200.0],
                [3, 2, 3, perfil_padrao, 200.0],
            ],
            columns=["id", "nó i", "nó j", "perfil", "E (GPa)"],
        )
    else:
        nos_padrao = pd.DataFrame(
            [
                [1, 0.0, 0.0, True, True, True, 0.0, 0.0, 0.0],
                [2, 0.0, 3.0, False, False, False, 0.0, 0.0, 0.0],
                [3, 4.0, 3.0, False, False, False, 0.0, 0.0, 0.0],
                [4, 4.0, 0.0, True, True, True, 0.0, 0.0, 0.0],
            ],
            columns=[
                "id", "x (m)", "y (m)", "fixa x", "fixa y", "fixa rotação",
                "Fx (kN)", "Fy (kN)", "Mz (kN·m)"
            ],
        )
        elementos_padrao = pd.DataFrame(
            [
                [1, 1, 2, perfil_padrao, 200.0, 0.0],
                [2, 2, 3, perfil_padrao, 200.0, -10.0],
                [3, 3, 4, perfil_padrao, 200.0, 0.0],
            ],
            columns=["id", "nó i", "nó j", "perfil", "E (GPa)", "qy local (kN/m)"],
        )

    st.subheader("Nós")
    nos_editados = st.data_editor(
        nos_padrao,
        num_rows="dynamic",
        hide_index=True,
        key=f"estrutura_nos_{modelo}",
    )
    st.subheader("Elementos")
    elementos_editados = st.data_editor(
        elementos_padrao,
        num_rows="dynamic",
        hide_index=True,
        key=f"estrutura_elementos_{modelo}",
        column_config={
            "perfil": st.column_config.SelectboxColumn(
                options=list(secoes.CATALOGO_PERFIS),
                required=True,
            )
        },
    )
    analisar = st.button(
        "Analisar estrutura",
        type="primary",
        icon=":material/calculate:",
        width="stretch",
    )
    if analisar:
        try:
            if modelo == "Treliça 2D":
                nos = [
                    estrutural.NoTrelica(
                        id=int(linha["id"]),
                        x_mm=float(linha["x (m)"]) * 1e3,
                        y_mm=float(linha["y (m)"]) * 1e3,
                        restringe_x=bool(linha["fixa x"]),
                        restringe_y=bool(linha["fixa y"]),
                        fx_N=float(linha["Fx (kN)"]) * 1e3,
                        fy_N=float(linha["Fy (kN)"]) * 1e3,
                    )
                    for _, linha in nos_editados.dropna().iterrows()
                ]
                elementos = []
                for _, linha in elementos_editados.dropna().iterrows():
                    perfil_elemento = secoes.obter_perfil(str(linha["perfil"]))
                    elementos.append(
                        estrutural.ElementoTrelica(
                            id=int(linha["id"]),
                            no_i=int(linha["nó i"]),
                            no_j=int(linha["nó j"]),
                            area_mm2=perfil_elemento.area_mm2,
                            modulo_elasticidade_MPa=float(linha["E (GPa)"]) * 1e3,
                        )
                    )
                resultado = estrutural.analisar_trelica(nos, elementos)
            else:
                nos = [
                    estrutural.NoPortico(
                        id=int(linha["id"]),
                        x_mm=float(linha["x (m)"]) * 1e3,
                        y_mm=float(linha["y (m)"]) * 1e3,
                        restringe_x=bool(linha["fixa x"]),
                        restringe_y=bool(linha["fixa y"]),
                        restringe_rotacao=bool(linha["fixa rotação"]),
                        fx_N=float(linha["Fx (kN)"]) * 1e3,
                        fy_N=float(linha["Fy (kN)"]) * 1e3,
                        mz_Nmm=float(linha["Mz (kN·m)"]) * 1e6,
                    )
                    for _, linha in nos_editados.dropna().iterrows()
                ]
                elementos = []
                for _, linha in elementos_editados.dropna().iterrows():
                    perfil_elemento = secoes.obter_perfil(str(linha["perfil"]))
                    elementos.append(
                        estrutural.ElementoPortico(
                            id=int(linha["id"]),
                            no_i=int(linha["nó i"]),
                            no_j=int(linha["nó j"]),
                            area_mm2=perfil_elemento.area_mm2,
                            inercia_mm4=perfil_elemento.ix_mm4,
                            modulo_elasticidade_MPa=float(linha["E (GPa)"]) * 1e3,
                            carga_distribuida_local_y_N_mm=float(
                                linha["qy local (kN/m)"]
                            ),
                        )
                    )
                resultado = estrutural.analisar_portico(nos, elementos)
        except (ValueError, TypeError, KeyError) as erro:
            st.error(f"Modelo inválido: {erro}", icon=":material/error:")
        else:
            # Guardado em session_state (e não só nas variáveis locais) para
            # que o resultado sobreviva ao clique em "Registrar análise 2D no
            # projeto": esse clique também dispara um rerun do script, no
            # qual "analisar" (um st.button comum) voltaria a ser False.
            st.session_state["estrutura_2d_resultado"] = {
                "modelo": modelo,
                "nos": nos,
                "elementos": elementos,
                "resultado": resultado,
            }

    resultado_estrutura_2d = st.session_state.get("estrutura_2d_resultado")
    if resultado_estrutura_2d and resultado_estrutura_2d["modelo"] == modelo:
        nos = resultado_estrutura_2d["nos"]
        elementos = resultado_estrutura_2d["elementos"]
        resultado = resultado_estrutura_2d["resultado"]

        st.subheader("Resultados")
        st.metric(
            "Maior deslocamento translacional",
            f"{resultado.deslocamento_maximo_mm:.3f} mm",
            border=True,
        )
        deslocamentos = pd.DataFrame(resultado.deslocamentos_nodais)
        reacoes = pd.DataFrame(resultado.reacoes_nodais)
        esforcos = pd.DataFrame(resultado.esforcos_elementos)
        for coluna in reacoes.columns:
            if coluna.endswith("_N"):
                reacoes[coluna] = reacoes[coluna] / 1e3
                reacoes.rename(columns={coluna: coluna.replace("_N", "_kN")}, inplace=True)
            elif coluna.endswith("_Nmm"):
                reacoes[coluna] = reacoes[coluna] / 1e6
                reacoes.rename(columns={coluna: coluna.replace("_Nmm", "_kNm")}, inplace=True)
        for coluna in esforcos.columns:
            if coluna.endswith("_N"):
                esforcos[coluna] = esforcos[coluna] / 1e3
                esforcos.rename(columns={coluna: coluna.replace("_N", "_kN")}, inplace=True)
            elif coluna.endswith("_Nmm"):
                esforcos[coluna] = esforcos[coluna] / 1e6
                esforcos.rename(columns={coluna: coluna.replace("_Nmm", "_kNm")}, inplace=True)
        resultados_tabs = st.tabs(["Deslocamentos", "Reações", "Esforços"])
        with resultados_tabs[0]:
            st.dataframe(deslocamentos, hide_index=True)
        with resultados_tabs[1]:
            st.dataframe(reacoes, hide_index=True)
        with resultados_tabs[2]:
            st.dataframe(esforcos, hide_index=True)

        coordenadas = {
            int(no.id): (no.x_mm / 1e3, no.y_mm / 1e3)
            for no in nos
        }
        desloc_por_no = {
            int(item["no"]): (item["ux_mm"], item["uy_mm"])
            for item in resultado.deslocamentos_nodais
        }
        maior_dimensao = max(
            max(x for x, _ in coordenadas.values()) - min(x for x, _ in coordenadas.values()),
            max(y for _, y in coordenadas.values()) - min(y for _, y in coordenadas.values()),
            1.0,
        )
        escala = (
            1.0
            if resultado.deslocamento_maximo_mm == 0
            else 0.15 * maior_dimensao * 1e3 / resultado.deslocamento_maximo_mm
        )
        linhas_grafico = []
        for elemento in elementos:
            for estado, fator in (("Original", 0.0), ("Deformada", escala)):
                for ordem, no_id in enumerate((elemento.no_i, elemento.no_j)):
                    x, y = coordenadas[no_id]
                    ux, uy = desloc_por_no[no_id]
                    linhas_grafico.append(
                        {
                            "elemento": str(elemento.id),
                            "estado": estado,
                            "ordem": ordem,
                            "x (m)": x + fator * ux / 1e3,
                            "y (m)": y + fator * uy / 1e3,
                        }
                    )
        df_grafico = pd.DataFrame(linhas_grafico)
        grafico = (
            alt.Chart(df_grafico)
            .mark_line(point=True)
            .encode(
                x=alt.X("x (m):Q", scale=alt.Scale(zero=False)),
                y=alt.Y("y (m):Q", scale=alt.Scale(zero=False)),
                color=alt.Color("estado:N"),
                detail="elemento:N",
                order="ordem:O",
                strokeDash=alt.StrokeDash("estado:N"),
                tooltip=["elemento", "estado", "x (m)", "y (m)"],
            )
            .properties(height=420)
            .interactive()
        )
        st.altair_chart(grafico)
        st.caption(f"Forma deformada ampliada {escala:.1f}×.")

        fronteira_modelo(
            [
                "Efeitos de segunda ordem (P–Δ, P–δ) e imperfeições geométricas iniciais.",
                "Flambagem global ou local dos elementos.",
                "Ligações semirrígidas — os apoios e nós são idealizados como rígidos ou rotulados.",
                "Combinações de ações e dimensionamento de cada barra (fazer em separado).",
            ]
        )

        registro_modelo_2d = construir_registro_tecnico(
            modulo="Estruturas de aço",
            modulo_id="estruturas_aco",
            titulo=f"Análise linear — {modelo}",
            status="Calculado",
            resumo="Análise elástica linear de treliça ou pórtico plano com deslocamentos, reações e esforços internos.",
            entradas={
                "modelo": modelo,
                "numero_nos": len(nos),
                "numero_elementos": len(elementos),
                "nos": [asdict(item) for item in nos],
                "elementos": [asdict(item) for item in elementos],
            },
            resultados={
                "deslocamento_maximo_mm": resultado.deslocamento_maximo_mm,
                "deslocamentos_nodais": resultado.deslocamentos_nodais,
                "reacoes_nodais": resultado.reacoes_nodais,
                "esforcos_elementos": resultado.esforcos_elementos,
            },
            premissas=[
                "Análise linear elástica, pequenas deformações e ligações idealizadas.",
                "Propriedades geométricas e módulos são os valores informados no modelo.",
            ],
            alertas=["Estabilidade, imperfeições, segunda ordem, ligações e combinações não são verificadas automaticamente por este modelo."],
            referencias=["Vincular o modelo aos desenhos, combinações de ações e critérios de deslocamento do projeto."],
            conclusao="Modelo resolvido sem singularidade; validar idealização, deslocamentos admissíveis e dimensionar cada elemento.",
        )
        botao_registrar_calculo(
            registro_modelo_2d,
            key="registrar_estrutura_2d",
            rotulo="Registrar análise 2D no projeto",
        )

st.caption(
    "Referências de escopo: ABNT NBR 8800:2024, ABNT NBR 8681:2025, "
    "ABNT NBR 6120:2019 e ABNT NBR 6123:2023."
)
