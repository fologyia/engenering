"""Placas de base: base de pilar de perfil I ou H pela ABNT NBR 8800:2025, Subseção 6.7."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from components.placa_de_base_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_verificacoes_resumidas, texto_markdown
from core import base_de_pilar as bp
from core import soldas as sd
from core.desenho_placa_base import figura_da_base
from core.project_store import obter_projeto_ativo
from core.verificacao import csv_verificacoes

configurar_pagina("Placas de base", ":material/anchor:")
cabecalho_pagina(
    "Placas de base",
    "Base de pilar de perfil I ou H pela ABNT NBR 8800:2025 (6.7): chumbadores externos, "
    "internos, base rotulada ou internos e externos; o caso pela força normal e pelo momento, a "
    "espessura da placa, os chumbadores (reto com porca, guarda-chuva, químico ou parabolt, com a "
    "ancoragem no concreto pela ACI 318-19), a cortante, a Tabela 18, o desenho e o memorial.",
    categoria="Ligações e bases",
    icone=":material/anchor:",
    cor="blue",
    ajuda_modulo="Placas de base",
)
PADRAO = bp.EntradaBase()
CASOS = {
    "C1": "compressão centrada",
    "C2": "compressão, pequena excentricidade",
    "C3": "compressão, grande excentricidade",
    "T1": "tração centrada",
    "T2": "tração, pequena excentricidade",
    "T3": "tração, grande excentricidade",
}


def _sessao(chave: str, valor: object) -> None:
    if chave not in st.session_state:
        st.session_state[chave] = valor


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


_sessao("pb_perfil", PADRAO.perfil)
_sessao("pb_chumbador", PADRAO.chumbador)
_sessao("pb_t", PADRAO.t_placa_mm)

with st.container(border=True), secao_protegida("1. Pilar e chumbadores"):
    st.subheader("1. Pilar e chumbadores", help=AJUDA["sec_pilar"])
    colunas = st.columns([2, 3])
    perfil = colunas[0].selectbox(
        "Perfil do pilar",
        bp.perfis_i(),
        key="pb_perfil",
        persist_state="session",
        help=AJUDA["perfil"],
    )
    tipo = colunas[1].radio(
        "Disposição dos chumbadores",
        list(bp.TIPOS),
        format_func=bp.TIPOS.get,
        key="pb_tipo",
        persist_state="session",
        help=AJUDA["tipo"],
    )
    colunas[1].caption(
        "Método da NBR 8800:2025, Figura 21."
        if tipo in bp.TIPOS_DA_NORMA
        else "Fora da Figura 21: método geral (o da 6.7 com os chumbadores em mais de uma linha)."
    )
    quantidades = bp.QUANTIDADES[tipo]
    if st.session_state.get("pb_n") not in quantidades:
        st.session_state["pb_n"] = quantidades[0]
    colunas = st.columns(3)
    n_chumbadores = colunas[0].selectbox(
        "Número de chumbadores",
        quantidades,
        key="pb_n",
        persist_state="session",
        help=AJUDA["n_chumbadores"],
    )
    chumbador = colunas[1].selectbox(
        "Diâmetro do chumbador",
        list(bp.TABELA_18),
        format_func=lambda p: f"Ø {p} ({bp.TABELA_18[p].d_b:.0f} mm)",
        key="pb_chumbador",
        persist_state="session",
        help=AJUDA["chumbador"],
    )
    tabela = bp.TABELA_18[chumbador]
    da_tabela = colunas[2].toggle(
        "a₁ e a₂ da Tabela 18",
        value=True,
        key="pb_tab18",
        persist_state="session",
        help=AJUDA["tabela_18"],
    )
    a1 = a2 = a1_x = 0.0
    if not da_tabela:
        colunas = st.columns(3 if tipo == bp.TIPO_2 else 2)
        a1 = colunas[0].number_input(
            f"a₁ (mm) — mínimo {tabela.a1:.0f}",
            10.0,
            500.0,
            float(tabela.a1),
            5.0,
            format="%.0f",
            key="pb_a1",
            persist_state="session",
            help=AJUDA["a1"],
        )
        a2 = colunas[1].number_input(
            f"a₂ (mm) — mínimo {tabela.a2:.0f}",
            10.0,
            1000.0,
            float(tabela.a2),
            5.0,
            format="%.0f",
            key="pb_a2",
            persist_state="session",
            help=AJUDA["a2"],
        )
        if tipo == bp.TIPO_2:  # nota f da Tabela 18
            a1_x = colunas[2].number_input(
                f"a₁ na direção ℓx (mm) — de {bp.A1_X_MINIMO_TIPO_2:.0f} a {tabela.a1:.0f}",
                bp.A1_X_MINIMO_TIPO_2,
                500.0,
                float(tabela.a1),
                5.0,
                format="%.0f",
                key="pb_a1_x",
                persist_state="session",
                help=AJUDA["a1_x"],
            )

with st.container(border=True), secao_protegida("2. Tipo de chumbador"):
    st.subheader("2. Tipo de chumbador", help=AJUDA["sec_chumbador"])
    colunas = st.columns([3, 2])
    ancoragem = colunas[0].selectbox(
        "Tipo do chumbador",
        list(bp.ANCORAGENS),
        format_func=bp.ANCORAGENS.get,
        key="pb_ancoragem",
        persist_state="session",
        help=AJUDA["ancoragem"],
    )
    aco_chumbador = colunas[1].selectbox(
        "Aço do chumbador",
        list(bp.ACOS_CHUMBADOR),
        key="pb_aco_ch",
        persist_state="session",
        help=AJUDA["aco_chumbador"],
    )
    e_h = chapa_na_ponta = h_ef = n_rd_fabricante = 0.0
    if ancoragem == bp.ANCORAGEM_PORCA:
        verificar_concreto = st.toggle(
            "Verificar a ancoragem no concreto (ACI 318-19)",
            key="pb_aci",
            persist_state="session",
            help=AJUDA["verificar_aci"],
        )
    else:
        verificar_concreto = True
        st.caption(
            ":material/info: A Tabela 18 não cobre este tipo: a ancoragem no concreto é sempre "
            "verificada pela ACI 318-19, Capítulo 17."
        )
    colunas = st.columns(3)
    if ancoragem == bp.ANCORAGEM_GANCHO:
        e_h = colunas[0].number_input(
            f"Gancho e_h (mm) — 0 = 4,5·d_b = {4.5 * tabela.d_b:.0f}",
            0.0,
            1000.0,
            0.0,
            5.0,
            format="%.0f",
            key="pb_eh",
            persist_state="session",
            help=AJUDA["e_h"],
        )
    if ancoragem == bp.ANCORAGEM_PORCA and verificar_concreto:
        chapa_na_ponta = colunas[0].number_input(
            "Chapa na ponta, lado (mm) — 0 = só a porca",
            0.0,
            500.0,
            0.0,
            5.0,
            format="%.0f",
            key="pb_chapa_ponta",
            persist_state="session",
            help=AJUDA["chapa_ponta"],
        )
    if verificar_concreto:
        padrao_h_ef = 12 * tabela.d_b if ancoragem in bp.POS_INSTALADOS else tabela.h1
        h_ef = colunas[1].number_input(
            f"Embutimento h_ef (mm) — 0 = {padrao_h_ef:.0f}",
            0.0,
            3000.0,
            0.0,
            5.0,
            format="%.0f",
            key="pb_hef",
            persist_state="session",
            help=AJUDA["h_ef"],
        )
    if ancoragem in bp.POS_INSTALADOS:
        n_rd_fabricante = colunas[2].number_input(
            "N_Rd do fabricante, por chumbador (kN)",
            0.0,
            5000.0,
            0.0,
            1.0,
            format="%.1f",
            key="pb_nrd_fab",
            persist_state="session",
            help=AJUDA["n_rd_fabricante"],
        )
    armadura = False
    if verificar_concreto:
        armadura = st.toggle(
            "O bloco tem armadura de ancoragem que costura o cone",
            key="pb_armadura",
            persist_state="session",
            help=AJUDA["armadura"],
        )

with st.container(border=True), secao_protegida("3. Placa"):
    st.subheader("3. Placa", help=AJUDA["sec_placa"])
    colunas = st.columns(3)
    t_placa = colunas[0].number_input(
        "Espessura t_p (mm)",
        4.0,
        200.0,
        step=0.5,
        format="%.1f",
        key="pb_t",
        persist_state="session",
        help=AJUDA["t_placa"],
    )
    aco_placa = colunas[1].selectbox(
        "Aço da placa",
        bp.ACOS_DA_PLACA,
        key="pb_aco",
        persist_state="session",
        help=AJUDA["aco_placa"],
    )
    e_n = colunas[2].number_input(
        f"Argamassa e_n (mm) — 0 = {tabela.e_n:.0f} da Tabela 18",
        0.0,
        200.0,
        0.0,
        5.0,
        format="%.0f",
        key="pb_en",
        persist_state="session",
        help=AJUDA["e_n"],
    )

with st.container(border=True), secao_protegida("4. Concreto e bloco"):
    st.subheader("4. Concreto e bloco", help=AJUDA["sec_concreto"])
    colunas = st.columns(3)
    fck = colunas[0].number_input(
        "f_ck do bloco (MPa)",
        10.0,
        90.0,
        PADRAO.fck_MPa,
        1.0,
        format="%.0f",
        key="pb_fck",
        persist_state="session",
        help=AJUDA["fck"],
    )
    combinacao = colunas[1].selectbox(
        "Combinação",
        list(sd.COMBINACOES),
        format_func=sd.COMBINACOES.get,
        key="pb_comb",
        persist_state="session",
        help=AJUDA["combinacao"],
    )
    bloco_informado = colunas[2].toggle(
        "Informar o bloco", key="pb_bloco", persist_state="session", help=AJUDA["bloco_informado"]
    )
    bloco_x = bloco_y = 0.0
    razao = 1.0
    colunas = st.columns(3)
    if bloco_informado:
        bloco_x = colunas[0].number_input(
            "Bloco na direção de ℓx (mm)",
            100.0,
            10000.0,
            900.0,
            50.0,
            format="%.0f",
            key="pb_bx",
            persist_state="session",
            help=AJUDA["bloco_x"],
        )
        bloco_y = colunas[1].number_input(
            "Bloco na direção de ℓy (mm)",
            100.0,
            10000.0,
            900.0,
            50.0,
            format="%.0f",
            key="pb_by",
            persist_state="session",
            help=AJUDA["bloco_y"],
        )
    else:
        razao = colunas[0].number_input(
            "A₂/A₁",
            1.0,
            4.0,
            1.0,
            0.1,
            format="%.2f",
            key="pb_razao",
            persist_state="session",
            help=AJUDA["razao"],
        )

with st.container(border=True), secao_protegida("5. Esforços de cálculo"):
    st.subheader("5. Esforços de cálculo (ELU)", help=AJUDA["sec_esforcos"])
    colunas = st.columns(3)
    n_sd = colunas[0].number_input(
        "N_Sd (kN) — + compressão",
        -20000.0,
        50000.0,
        PADRAO.n_sd_kN,
        10.0,
        format="%.1f",
        key="pb_n_sd",
        persist_state="session",
        help=AJUDA["n_sd"],
    )
    m_sd = colunas[1].number_input(
        "M_Sd (kN·m)",
        0.0,
        20000.0,
        PADRAO.m_sd_kNm,
        5.0,
        format="%.1f",
        key="pb_m_sd",
        persist_state="session",
        help=AJUDA["m_sd"],
    )
    v_sd = colunas[2].number_input(
        "V_Sd (kN)",
        0.0,
        20000.0,
        PADRAO.v_sd_kN,
        5.0,
        format="%.1f",
        key="pb_v_sd",
        persist_state="session",
        help=AJUDA["v_sd"],
    )
    m_sd_y = st.number_input(
        "M_Sd,y no eixo de menor inércia (kN·m)",
        0.0,
        20000.0,
        0.0,
        1.0,
        format="%.1f",
        key="pb_m_sd_y",
        persist_state="session",
        help=AJUDA["m_sd_y"],
    )

with st.container(border=True), secao_protegida("6. Cortante"):
    st.subheader("6. Cortante", help=AJUDA["sec_cortante"])
    cortante = st.radio(
        "A cortante passa por",
        list(bp.CORTANTES),
        format_func=bp.CORTANTES.get,
        horizontal=True,
        key="pb_cortante",
        persist_state="session",
        help=AJUDA["cortante"],
    )
    mu = PADRAO.mu
    b_v, b_h, t_pv = PADRAO.b_v_mm, PADRAO.b_h_mm, PADRAO.t_pv_mm
    t_arruela = 0.0
    colunas = st.columns(3)
    if cortante == bp.CORTANTE_ATRITO:
        mu = colunas[0].number_input(
            "μ (atrito)",
            0.1,
            1.0,
            bp.MU_PADRAO,
            0.05,
            format="%.2f",
            key="pb_mu",
            persist_state="session",
            help=AJUDA["mu"],
        )
    elif cortante == bp.CORTANTE_PLACA:
        b_v = colunas[0].number_input(
            "b_v — altura (mm)",
            20.0,
            1000.0,
            PADRAO.b_v_mm,
            10.0,
            format="%.0f",
            key="pb_bv",
            persist_state="session",
            help=AJUDA["b_v"],
        )
        b_h = colunas[1].number_input(
            "b_h — largura (mm)",
            20.0,
            2000.0,
            PADRAO.b_h_mm,
            10.0,
            format="%.0f",
            key="pb_bh",
            persist_state="session",
            help=AJUDA["b_h"],
        )
        t_pv = colunas[2].number_input(
            "t_pv — espessura (mm)",
            4.0,
            100.0,
            PADRAO.t_pv_mm,
            0.5,
            format="%.1f",
            key="pb_tpv",
            persist_state="session",
            help=AJUDA["t_pv"],
        )
    else:
        t_arruela = colunas[0].number_input(
            f"Espessura da arruela (mm) — 0 = {tabela.t_arruela:.1f} da Tabela 18".replace(
                ".", ","
            ),
            0.0,
            50.0,
            0.0,
            0.5,
            format="%.1f",
            key="pb_ta",
            persist_state="session",
            help=AJUDA["t_arruela"],
        )

entrada = bp.EntradaBase(
    perfil=perfil,
    tipo=tipo,
    n_chumbadores=int(n_chumbadores),
    chumbador=chumbador,
    a1_mm=float(a1),
    a2_mm=float(a2),
    a1_x_mm=float(a1_x),
    t_placa_mm=float(t_placa),
    aco_placa=aco_placa,
    fck_MPa=float(fck),
    razao_a2_a1=float(razao),
    bloco_x_mm=float(bloco_x),
    bloco_y_mm=float(bloco_y),
    n_sd_kN=float(n_sd),
    m_sd_kNm=float(m_sd),
    v_sd_kN=float(v_sd),
    combinacao=combinacao,
    cortante=cortante,
    mu=float(mu),
    b_v_mm=float(b_v),
    b_h_mm=float(b_h),
    t_pv_mm=float(t_pv),
    e_n_mm=float(e_n),
    t_arruela_mm=float(t_arruela),
    aco_chumbador=aco_chumbador,
    ancoragem=ancoragem,
    e_h_mm=float(e_h),
    m_sd_y_kNm=float(m_sd_y),
    verificar_concreto=bool(verificar_concreto),
    armadura_de_ancoragem=bool(armadura),
    chapa_na_ponta_mm=float(chapa_na_ponta),
    h_ef_mm=float(h_ef),
    n_rd_fabricante_kN=float(n_rd_fabricante),
)
try:
    resultado = bp.calcular(entrada)
except bp.BaseInvalida as erro:
    st.error(str(erro), icon=":material/error:")
    st.stop()

st.header("Resultados")
colunas = st.columns(4)
colunas[0].metric("Status", resultado.status, help=AJUDA["res_status"])
colunas[1].metric("Caso", resultado.caso, help=AJUDA["res_caso"])
colunas[1].caption(
    CASOS[resultado.caso].capitalize() + ("; flexão oblíqua" if entrada.m_sd_y_kNm else "")
)
aproveitamento = resultado.aproveitamento_maximo
colunas[2].metric(
    "Aproveitamento",
    f"{100 * aproveitamento:.0f} %" if math.isfinite(aproveitamento) else "sem resistência",
    help=AJUDA["res_aproveitamento"],
)
colunas[3].metric("t_p,min (mm)", _n(resultado.t_p_min), help=AJUDA["res_tp"])
colunas[3].caption(f"Adotada: {_n(entrada.t_placa_mm)} mm")
governante = resultado.governante
if governante is not None:
    st.markdown(f"**Governa:** {texto_markdown(governante.nome)}", help=AJUDA["res_governa"])
for aviso in resultado.avisos:
    st.warning(aviso, icon=":material/warning:")
reprovadas = [v.nome for v in resultado.verificacoes if v.status == "NÃO OK"]
if reprovadas:
    st.error(
        "Não passou: " + "; ".join(texto_markdown(nome) for nome in reprovadas) + ".",
        icon=":material/error:",
    )

with secao_protegida("Desenho da base"):
    st.subheader("A base", help=AJUDA["res_figura"])
    desenho = figura_da_base(resultado)
    st.image(desenho.png, caption=desenho.legenda, width="stretch")
st.subheader("Detalhamento adotado", help=AJUDA["res_adotado"])
st.table(pd.DataFrame(resultado.detalhamento, columns=["Item", "Valor"]).set_index("Item"))
st.caption(f":material/info: {bp.NOTA_TABELA_18}")

st.subheader("Verificações", help=AJUDA["res_verificacoes"])
mostrar_verificacoes_resumidas(list(resultado.grupos))
st.download_button(
    "Verificações (CSV)",
    data=csv_verificacoes(list(resultado.verificacoes)),
    file_name="placa_de_base_verificacoes.csv",
    mime="text/csv",
    icon=":material/download:",
    key="pb_csv",
    help=AJUDA["btn_csv"],
)

with st.container(border=True), secao_protegida("Base mais leve que atende"):
    st.subheader("Base mais leve que atende", help=AJUDA["res_mais_leve"])
    leve = bp.base_mais_leve(entrada)
    if leve is None:
        st.warning(
            "Nenhuma combinação de chumbador e espessura de chapa atende: o que reprova não "
            "depende da placa nem do chumbador — veja acima a cortante, o concreto ou a geometria.",
            icon=":material/warning:",
        )
    else:
        g = leve.geometria
        st.write(
            f"**Ø {leve.entrada.chumbador}** com placa **{g.lx:.0f} × {g.ly:.0f} × "
            f"{_n(leve.entrada.t_placa_mm)} mm** — {_n(leve.massa_da_placa_kg)} kg "
            f"(a atual: {_n(resultado.massa_da_placa_kg)} kg), aproveitamento "
            f"{100 * leve.aproveitamento_maximo:.0f} %."
        )
        if (leve.entrada.chumbador, leve.entrada.t_placa_mm) != (chumbador, entrada.t_placa_mm):
            st.button(
                f"Adotar Ø {leve.entrada.chumbador} e t_p = {_n(leve.entrada.t_placa_mm)} mm",
                icon=":material/swap_horiz:",
                key="pb_adotar",
                help=AJUDA["btn_adotar"],
                on_click=st.session_state.update,
                kwargs={"pb_chumbador": leve.entrada.chumbador, "pb_t": leve.entrada.t_placa_mm},
            )

with st.container(border=True), secao_protegida("Memorial desta base"):
    st.subheader("Memorial desta base", help=AJUDA["sec_memorial"])
    projeto_ativo = obter_projeto_ativo()
    botoes = st.columns(2)
    botoes[0].download_button(
        "Baixar o memorial (Word)",
        data=lambda: bp.memorial_da_base(resultado, projeto=projeto_ativo),
        file_name="memorial_placa_de_base.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:",
        width="stretch",
        on_click="ignore",
        key="pb_memorial_word",
        help=AJUDA["btn_memorial_word"],
    )
    botoes[1].download_button(
        "Baixar o memorial (PDF)",
        data=lambda: bp.memorial_da_base(resultado, projeto=projeto_ativo, formato="pdf"),
        file_name="memorial_placa_de_base.pdf",
        mime="application/pdf",
        icon=":material/picture_as_pdf:",
        width="stretch",
        on_click="ignore",
        key="pb_memorial_pdf",
        help=AJUDA["btn_memorial_pdf"],
    )
with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        bp.registro_base(resultado),
        key="registrar_placa_de_base",
        rotulo="Registrar a base no projeto ativo",
    )
