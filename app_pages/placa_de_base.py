"""Placas de base: base de pilar de perfil I ou H pela ABNT NBR 8800:2025, Subseção 6.7."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from components.edicao_de_tabela import com_edicoes
from components.figuras import mostrar_figura
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
    categoria="Estrutura metálica",
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


MODOS = {"tabela": "Da Tabela 18", "formula": "Por fórmula (fora da Tabela 18)"}


def _rotulo_rosca(nome: str) -> str:
    if nome == bp.CHUMBADOR_LIVRE:
        return "Outro diâmetro (digitar)"
    rosca = bp.ROSCAS[nome]
    return f"Ø {nome} ({_n(rosca.d_b)} mm, passo {_n(rosca.passo, 2)} mm)"


_sessao("pb_perfil", PADRAO.perfil)
_sessao("pb_chumbador", PADRAO.chumbador)
_sessao("pb_chumbador_f", PADRAO.chumbador)
_sessao("pb_t", PADRAO.t_placa_mm)

CASOS_TELA = "pb_casos"  # as combinações da tabela (lista de dicionários do núcleo)
CASOS_REV = "pb_casos_rev"
COLUNAS_CASOS = {
    "nome": "Combinação",
    "n_sd_kN": "N_Sd (kN)",
    "m_sd_kNm": "M_Sd (kN·m)",
    "m_sd_y_kNm": "M_Sd,y (kN·m)",
    "v_sd_kN": "V_Sd (kN)",
}
EXEMPLO_CASOS = [
    {"nome": "ELU1 — máxima compressão", "n_sd_kN": 600.0, "m_sd_kNm": 15.0, "m_sd_y_kNm": 0.0, "v_sd_kN": 25.0},
    {"nome": "ELU2 — vento (sucção)", "n_sd_kN": -80.0, "m_sd_kNm": 25.0, "m_sd_y_kNm": 0.0, "v_sd_kN": 40.0},
    {"nome": "ELU3 — máximo momento", "n_sd_kN": 200.0, "m_sd_kNm": 40.0, "m_sd_y_kNm": 0.0, "v_sd_kN": 35.0},
]  # fmt: skip
_sessao(CASOS_TELA, [dict(linha) for linha in EXEMPLO_CASOS])
_sessao(CASOS_REV, 0)


def _para_a_tela(linhas: list[dict]) -> list[dict]:
    return [{COLUNAS_CASOS[k]: linha.get(k) for k in COLUNAS_CASOS} for linha in linhas]


def _da_tela(linhas: list[dict]) -> list[dict]:
    saida = []
    for linha in linhas:
        valores = {k: linha.get(rotulo) for k, rotulo in COLUNAS_CASOS.items()}
        nome = str(valores["nome"] or "").strip()
        numeros = [valores[k] for k in COLUNAS_CASOS if k != "nome"]
        if not nome and all(v in (None, "") or v != v for v in numeros):
            continue  # linha acrescentada e deixada em branco
        for k in COLUNAS_CASOS:
            if k != "nome":
                v = valores[k]
                valores[k] = 0.0 if v in (None, "") or v != v else float(v)
        valores["nome"] = nome
        saida.append(valores)
    return saida


def _ao_editar_casos(chave: str) -> None:
    st.session_state[CASOS_TELA] = _da_tela(
        com_edicoes(_para_a_tela(st.session_state[CASOS_TELA]), st.session_state.get(chave) or {})
    )
    st.session_state[CASOS_REV] = st.session_state.get(CASOS_REV, 0) + 1


def _trocar_casos(linhas: list[dict]) -> None:
    st.session_state[CASOS_TELA] = linhas
    st.session_state[CASOS_REV] = st.session_state.get(CASOS_REV, 0) + 1


def _trazer_do_modelo(perfil: str, linhas: list[dict]) -> None:
    _trocar_casos(linhas)
    if perfil in bp.perfis_i():  # o pilar do modelo, se for um perfil I do catálogo
        st.session_state["pb_perfil"] = perfil


def _pilares_do_modelo() -> list:
    """As combinações ELU na base de cada pilar de Esforços do modelo (vazio sem modelo)."""
    projeto = obter_projeto_ativo()
    if not projeto:
        return []
    try:
        from core import placa_base_pilares as pbp
        from core import plano_de_cargas as pc
        from core import tratamento_do_modelo as tm

        return pbp.combinacoes_dos_pilares(
            tm.do_projeto(projeto).dados, pc.plano_do_projeto(projeto)
        )
    except (ArithmeticError, ValueError, KeyError, TypeError):
        return []


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
    modo = st.radio(
        "Medidas do chumbador",
        list(MODOS),
        format_func=MODOS.get,
        horizontal=True,
        key="pb_modo_ch",
        persist_state="session",
        help=AJUDA["modo_chumbador"],
    )
    por_formula = modo == "formula"
    colunas = st.columns(3)
    n_chumbadores = colunas[0].selectbox(
        "Número de chumbadores",
        quantidades,
        key="pb_n",
        persist_state="session",
        help=AJUDA["n_chumbadores"],
    )
    if por_formula:
        chumbador = colunas[1].selectbox(
            "Diâmetro do chumbador",
            [*bp.ROSCAS, bp.CHUMBADOR_LIVRE],
            format_func=_rotulo_rosca,
            key="pb_chumbador_f",
            persist_state="session",
            help=AJUDA["chumbador_formula"],
        )
    else:
        chumbador = colunas[1].selectbox(
            "Diâmetro do chumbador",
            list(bp.TABELA_18),
            format_func=lambda p: f"Ø {p} ({bp.TABELA_18[p].d_b:.0f} mm)",
            key="pb_chumbador",
            persist_state="session",
            help=AJUDA["chumbador"],
        )
    da_tabela = colunas[2].toggle(
        "a₁ e a₂ mínimos",
        value=True,
        key="pb_tab18",
        persist_state="session",
        help=AJUDA["tabela_18"],
    )
    d_b_livre = passo_livre = d_f = 0.0
    if por_formula:
        colunas = st.columns(3)
        if chumbador == bp.CHUMBADOR_LIVRE:
            d_b_livre = colunas[0].number_input(
                "Diâmetro d_b (mm)",
                6.0,
                150.0,
                24.0,
                1.0,
                format="%.1f",
                key="pb_db_livre",
                persist_state="session",
                help=AJUDA["d_b_livre"],
            )
            passo_livre = colunas[1].number_input(
                "Passo da rosca (mm) — 0 = métrica grossa",
                0.0,
                12.0,
                0.0,
                0.25,
                format="%.2f",
                key="pb_passo",
                persist_state="session",
                help=AJUDA["passo"],
            )
            d_b_atual = float(d_b_livre)
        else:
            d_b_atual = bp.ROSCAS[chumbador].d_b
        _sessao("pb_df", 0.0)  # sem valor padrão no widget: o botão Adotar zera este campo
        d_f = colunas[2].number_input(
            f"Furo na placa d_f (mm) — 0 = {bp.furo_padrao(d_b_atual):.0f}",
            0.0,
            400.0,
            step=1.0,
            format="%.0f",
            key="pb_df",
            persist_state="session",
            help=AJUDA["d_f"],
        )
    # as medidas dos rótulos abaixo (a ancoragem e a placa vêm das seções seguintes)
    ancoragem_atual = st.session_state.get("pb_ancoragem", bp.ANCORAGEM_PORCA)
    previa = bp.EntradaBase(
        por_formula=por_formula,
        chumbador=chumbador,
        d_b_mm=float(d_b_livre),
        passo_mm=float(passo_livre),
        d_f_mm=float(d_f),
        ancoragem=ancoragem_atual if ancoragem_atual in bp.ANCORAGENS else bp.ANCORAGEM_PORCA,
        t_placa_mm=float(st.session_state.get("pb_t", PADRAO.t_placa_mm)),
    )
    tabela = bp.disposicoes(previa)
    origem = "por fórmula" if por_formula else "da Tabela 18"
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
    if ancoragem == bp.ANCORAGEM_PORCA and not por_formula:
        verificar_concreto = st.toggle(
            "Verificar a ancoragem no concreto (ACI 318-19)",
            key="pb_aci",
            persist_state="session",
            help=AJUDA["verificar_aci"],
        )
    else:
        verificar_concreto = True
        st.caption(
            ":material/info: Fora da Tabela 18 (por fórmula), a ancoragem no concreto é sempre "
            "verificada pela ACI 318-19, Capítulo 17."
            if por_formula
            else ":material/info: A Tabela 18 não cobre este tipo: a ancoragem no concreto é sempre "
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
            "Embutimento h_ef (mm) — 0 = pelo cone"
            if por_formula
            else f"Embutimento h_ef (mm) — 0 = {padrao_h_ef:.0f}",
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
        f"Argamassa e_n (mm) — 0 = {tabela.e_n:.0f} {origem}",
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
    bloco_x = bloco_y = bloco_z = 0.0
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
        bloco_z = colunas[2].number_input(
            "Altura do bloco h_a (mm) — 0 = a mínima",
            0.0,
            10000.0,
            0.0,
            50.0,
            format="%.0f",
            key="pb_bz",
            persist_state="session",
            help=AJUDA["bloco_z"],
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
    varias = (
        st.radio(
            "Esforços",
            ["uma", "varias"],
            format_func={"uma": "Uma combinação", "varias": "Várias combinações (envoltória)"}.get,
            horizontal=True,
            key="pb_varias",
            persist_state="session",
            help=AJUDA["varias"],
        )
        == "varias"
    )
    casos: tuple = ()
    if varias:
        chave_casos = f"pb_tabela_casos_{st.session_state.get(CASOS_REV, 0)}"
        st.data_editor(
            pd.DataFrame(
                _para_a_tela(st.session_state[CASOS_TELA]), columns=list(COLUNAS_CASOS.values())
            ),
            key=chave_casos,
            on_change=_ao_editar_casos,
            args=(chave_casos,),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "Combinação": st.column_config.TextColumn(width="medium", required=True),
                "N_Sd (kN)": st.column_config.NumberColumn(
                    format="%.1f", help="Positiva na compressão, negativa na tração."
                ),
                "M_Sd (kN·m)": st.column_config.NumberColumn(format="%.1f"),
                "M_Sd,y (kN·m)": st.column_config.NumberColumn(format="%.1f"),
                "V_Sd (kN)": st.column_config.NumberColumn(format="%.1f", min_value=0.0),
            },
        )
        casos = tuple(bp.caso_de_dicionario(linha) for linha in st.session_state[CASOS_TELA])
        if not casos:
            st.warning(
                "A tabela está vazia: acrescente ao menos uma combinação.",
                icon=":material/warning:",
            )
            st.stop()
        pilares = _pilares_do_modelo()
        botoes = st.columns([3, 2])
        if pilares:
            nomes_pilares = {p.pilar: p for p in pilares}
            escolhido = botoes[0].selectbox(
                "Pilar do modelo (Esforços do modelo)",
                list(nomes_pilares),
                format_func=lambda nome: f"{nome} — {nomes_pilares[nome].perfil or 'sem perfil'}",
                key="pb_pilar_modelo",
                help=AJUDA["pilar_modelo"],
            )
            botoes[1].button(
                "Trazer as combinações deste pilar",
                icon=":material/download:",
                key="pb_trazer_casos",
                help=AJUDA["btn_trazer"],
                on_click=_trazer_do_modelo,
                args=(
                    nomes_pilares[escolhido].perfil,
                    [
                        {"nome": nome, "n_sd_kN": round(n, 2), "m_sd_kNm": round(abs(m), 2),
                         "m_sd_y_kNm": round(abs(my), 2), "v_sd_kN": round(v, 2)}
                        for nome, n, m, my, v in nomes_pilares[escolhido].combinacoes
                    ],
                ),
            )  # fmt: skip
        botoes[-1].button(
            "Voltar ao exemplo",
            icon=":material/restart_alt:",
            key="pb_exemplo_casos",
            help=AJUDA["btn_exemplo_casos"],
            on_click=_trocar_casos,
            args=([dict(linha) for linha in EXEMPLO_CASOS],),
        )
    n_sd, m_sd, v_sd, m_sd_y = PADRAO.n_sd_kN, PADRAO.m_sd_kNm, PADRAO.v_sd_kN, 0.0
    if not varias:
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
    penetracao_lug = False
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
        penetracao_lug = st.toggle(
            "Placa de cisalhamento soldada com penetração total",
            key="pb_lug_cjp",
            persist_state="session",
            help=AJUDA["lug_cjp"],
        )
    else:
        t_arruela = colunas[0].number_input(
            f"Espessura da arruela (mm) — 0 = {_n(tabela.t_arruela)} {origem}",
            0.0,
            50.0,
            0.0,
            0.5,
            format="%.1f",
            key="pb_ta",
            persist_state="session",
            help=AJUDA["t_arruela"],
        )

with st.container(border=True), secao_protegida("7. Soldas"):
    st.subheader("7. Soldas", help=AJUDA["sec_soldas"])
    colunas = st.columns(3)
    perna_pilar = colunas[0].number_input(
        "Perna do filete do pilar (mm) — 0 = automática",
        0.0,
        30.0,
        0.0,
        1.0,
        format="%.0f",
        key="pb_perna_pilar",
        persist_state="session",
        help=AJUDA["perna_pilar"],
    )
    eletrodo = colunas[1].selectbox(
        "Eletrodo",
        list(sd.ELETRODOS),
        index=list(sd.ELETRODOS).index("E70"),
        key="pb_eletrodo",
        persist_state="session",
        help=AJUDA["eletrodo"],
    )
    aco_pilar = colunas[2].selectbox(
        "Aço do pilar",
        list(bp.ACOS_DA_PLACA),
        index=list(bp.ACOS_DA_PLACA).index(bp.ACO_DO_PILAR_PADRAO),
        key="pb_aco_pilar",
        persist_state="session",
        help=AJUDA["aco_pilar"],
    )
    colunas = st.columns(3)
    mesas_por_dentro = colunas[0].toggle(
        "Soldar as mesas também por dentro",
        value=True,
        key="pb_solda_dentro",
        persist_state="session",
        help=AJUDA["solda_dentro"],
    )
    solda_alma = colunas[1].toggle(
        "Soldar a alma (dos dois lados)",
        value=True,
        key="pb_solda_alma",
        persist_state="session",
        help=AJUDA["solda_alma"],
    )
    contato = colunas[2].toggle(
        "Compressão por contato (pilar faceado)",
        key="pb_contato",
        persist_state="session",
        help=AJUDA["contato"],
    )
    perna_lug = perna_arruela = 0.0
    if cortante == bp.CORTANTE_PLACA and not penetracao_lug:
        perna_lug = st.number_input(
            "Perna dos filetes da placa de cisalhamento (mm) — 0 = automática",
            0.0,
            30.0,
            0.0,
            1.0,
            format="%.0f",
            key="pb_perna_lug",
            persist_state="session",
            help=AJUDA["perna_lug"],
        )
    elif cortante == bp.CORTANTE_ARRUELAS:
        perna_arruela = st.number_input(
            "Perna do filete das arruelas (mm) — 0 = automática",
            0.0,
            30.0,
            0.0,
            1.0,
            format="%.0f",
            key="pb_perna_arruela",
            persist_state="session",
            help=AJUDA["perna_arruela"],
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
    por_formula=por_formula,
    d_b_mm=float(d_b_livre),
    passo_mm=float(passo_livre),
    d_f_mm=float(d_f),
    casos=casos,
    aco_pilar=aco_pilar,
    eletrodo=eletrodo,
    perna_pilar_mm=float(perna_pilar),
    solda_mesas_por_dentro=bool(mesas_por_dentro),
    solda_alma=bool(solda_alma),
    compressao_por_contato=bool(contato),
    perna_cisalhamento_mm=float(perna_lug),
    cisalhamento_penetracao_total=bool(penetracao_lug),
    perna_arruela_mm=float(perna_arruela),
    bloco_z_mm=float(bloco_z),
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
    CASOS[resultado.caso].capitalize()
    + ("; flexão oblíqua" if resultado.entrada.m_sd_y_kNm else "")
    + (f" — em «{resultado.combinacao_governante}»" if resultado.envoltoria else "")
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

if resultado.envoltoria:
    with st.container(border=True), secao_protegida("Combinações"):
        st.subheader("Combinações", help=AJUDA["res_combinacoes"])
        st.dataframe(
            pd.DataFrame(bp.linhas_das_combinacoes(resultado)),
            hide_index=True,
            width="stretch",
            column_config={
                "Aproveitamento": st.column_config.NumberColumn(format="percent"),
            },
        )
        st.caption(
            ":material/info: Em cada verificação abaixo vale a combinação mais desfavorável: o nome "
            "dela vem entre colchetes no começo da fórmula."
        )
if bp.solda_do_pilar_reprova(resultado):
    st.error(
        "A solda do pilar na placa não passa. Ela depende do perfil e dos esforços: trocar a placa "
        "ou o chumbador não resolve. Veja o grupo **Soldas** abaixo.",
        icon=":material/error:",
    )

with secao_protegida("Desenho da base"):
    st.subheader("A base", help=AJUDA["res_figura"])
    resultado_desenho = resultado
    if resultado.envoltoria:
        nomes_casos = [item.caso.nome for item in resultado.casos]
        if st.session_state.get("pb_caso_desenho") not in nomes_casos:
            st.session_state["pb_caso_desenho"] = resultado.combinacao_governante
        nome_desenho = st.selectbox(
            "Combinação desenhada",
            nomes_casos,
            key="pb_caso_desenho",
            help=AJUDA["caso_desenho"],
        )
        resultado_desenho = next(
            i.resultado for i in resultado.casos if i.caso.nome == nome_desenho
        )
    desenho = figura_da_base(resultado_desenho)
    mostrar_figura(desenho)
st.subheader("Detalhamento adotado", help=AJUDA["res_adotado"])
st.table(pd.DataFrame(resultado.detalhamento, columns=["Item", "Valor"]).set_index("Item"))
st.caption(f":material/info: {bp.NOTA_POR_FORMULA if por_formula else bp.NOTA_TABELA_18}")

medidas = resultado.por_formula
if medidas is not None:
    with st.container(border=True), secao_protegida("Chumbador por fórmula"):
        st.subheader("Chumbador por fórmula", help=AJUDA["res_por_formula"])
        st.table(
            pd.DataFrame(
                list(medidas.contas), columns=["Medida", "Valor", "Conta e fonte"]
            ).set_index("Medida")
        )
        if resultado.diametros:
            st.markdown("**Diâmetro que cada critério pede**", help=AJUDA["res_diametros"])
            linhas_d = [
                (nome, f"{_n(d)} mm" if d is not None else "nenhum até 160 mm", fonte)
                for nome, d, fonte in resultado.diametros
            ]
            st.table(
                pd.DataFrame(linhas_d, columns=["Critério", "d_b necessário", "Fonte"]).set_index(
                    "Critério"
                )
            )
        menor = bp.menor_diametro_que_atende(entrada)
        familia = bp.NOMES_DAS_FAMILIAS[medidas.rosca.familia]
        if menor is None:
            st.warning(
                f"Nenhum diâmetro comercial da série {familia} passa nos chumbadores: o que "
                "reprova não depende do diâmetro — veja acima.",
                icon=":material/warning:",
            )
        else:
            nome_menor = bp.nome_do_chumbador(menor.entrada)
            st.markdown(
                f"**Menor diâmetro comercial que atende** (série {familia}): **Ø {nome_menor}**"
                f" — d_b = {_n(menor.linha.d_b)} mm, placa {menor.geometria.lx:.0f} × "
                f"{menor.geometria.ly:.0f} mm.",
                help=AJUDA["res_menor_diametro"],
            )
            if nome_menor != bp.nome_do_chumbador(entrada):
                st.button(
                    f"Adotar Ø {nome_menor}",
                    icon=":material/swap_horiz:",
                    key="pb_adotar_d",
                    help=AJUDA["btn_adotar_diametro"],
                    on_click=st.session_state.update,
                    kwargs={"pb_chumbador_f": menor.entrada.chumbador, "pb_df": 0.0},
                )
        d_atual = medidas.rosca.d_b
        perto = min(bp.TABELA_18.values(), key=lambda linha: abs(linha.d_b - d_atual))
        st.markdown(
            f"**Conferência com a Tabela 18** (a linha mais perto, Ø {perto.polegada})",
            help=AJUDA["res_comparacao"],
        )
        calculada = resultado.linha
        comparacao = [
            ("d_b (mm)", calculada.d_b, perto.d_b),
            ("a₁ (mm)", calculada.a1, perto.a1),
            ("a₂ (mm)", calculada.a2, perto.a2),
            ("a₃ (mm)", calculada.a3, perto.a3),
            ("Furo d_f (mm)", calculada.d_f, perto.d_f),
            ("Arruela, lado (mm)", calculada.lado_da_arruela, perto.lado_da_arruela),
            ("Arruela, espessura (mm)", calculada.t_arruela, perto.t_arruela),
            ("Argamassa e_n (mm)", calculada.e_n, perto.e_n),
            ("Embutimento h_ef ou h₁ (mm)", bp.embutimento(entrada, calculada), perto.h1),
            ("f_ck mínimo (MPa)", calculada.fck_min, perto.fck_min),
        ]
        st.table(
            pd.DataFrame(
                [(nome, _n(a), _n(b)) for nome, a, b in comparacao],
                columns=["Medida", "Por fórmula", f"Tabela 18, Ø {perto.polegada}"],
            ).set_index("Medida")
        )

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
        nome_leve = bp.nome_do_chumbador(leve.entrada)
        if bp.solda_do_pilar_reprova(leve):
            st.caption(
                ":material/info: A busca não olha a solda do pilar (não depende da placa nem do "
                "chumbador); ela continua reprovando — veja o grupo Soldas."
            )
        st.write(
            f"**Ø {nome_leve}** com placa **{g.lx:.0f} × {g.ly:.0f} × "
            f"{_n(leve.entrada.t_placa_mm)} mm** — {_n(leve.massa_da_placa_kg)} kg "
            f"(a atual: {_n(resultado.massa_da_placa_kg)} kg), aproveitamento "
            f"{100 * leve.aproveitamento_maximo:.0f} %."
        )
        if por_formula:
            st.caption(
                ":material/info: Por fórmula, a busca troca entre os diâmetros comerciais da mesma "
                "série e não olha o cone de concreto, que depende do bloco, do embutimento e da "
                "armadura, não do diâmetro."
            )
        if (leve.entrada.chumbador, leve.entrada.t_placa_mm) != (chumbador, entrada.t_placa_mm):
            chave_d = "pb_chumbador_f" if por_formula else "pb_chumbador"
            novo: dict[str, object] = {
                chave_d: leve.entrada.chumbador,
                "pb_t": leve.entrada.t_placa_mm,
            }
            if por_formula and leve.entrada.chumbador != chumbador:
                novo["pb_df"] = 0.0  # o furo informado era do outro diâmetro
            st.button(
                f"Adotar Ø {nome_leve} e t_p = {_n(leve.entrada.t_placa_mm)} mm",
                icon=":material/swap_horiz:",
                key="pb_adotar",
                help=AJUDA["btn_adotar"],
                on_click=st.session_state.update,
                kwargs=novo,
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
