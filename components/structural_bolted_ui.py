"""Modo "Ligação estrutural de aço" da página Projeto de parafusos.

Só desenha a interface: todo cálculo está em ``core.bolted_joint_check`` (que usa as
fórmulas de ``core.bolted_connection``). A verificação roda a cada interação; as
varreduras "Comparar normas" e "Testar todos" são botões que ligam e desligam um painel.
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from components.bolted_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import comparador_cenarios, fronteira_modelo
from components.verification_table import (
    COR_BADGE,
    estilizar,
    mostrar_tabela_verificacoes,
)
from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core.verificacao import csv_verificacoes, formatar_percentual

_GEO_GRADE = "Grade retangular"
_GEO_LIVRE = "Coordenadas livres"

_MOM_NENHUM = "Sem momento"
_MOM_EMENDA = "Emenda por sobreposição"
_MOM_EXCENTRICIDADE = "Excentricidade a informada"
_MOM_VALOR = "Momento M informado"

_ESF_CORTANTE = "Só cortante"
_ESF_TRACAO = "Só tração"
_ESF_COMBINADO = "Combinado"

_P_INFORMADO = "Informar p"
_P_EXTREMO = "Parafuso da ponta"
_P_INTERNO = "Parafuso do meio"

_REVESTIMENTOS = {
    "galvanizado_fogo": "Galvanizado a fogo (padrão Anglo)",
    "zinco_aluminio": "Zn/Al (ASTM F1136, Dacromet)",
    "outro": "Outro / sem revestimento",
}


def _avisos_fixos() -> None:
    # A nota de versão fica só na página (não vai para o registro nem para o memorial).
    st.info(chk.NOTA_DA_VERSAO, icon=":material/menu_book:")
    corpo = "\n".join(f"- {aviso}" for aviso in chk.AVISOS_FIXOS)
    st.warning(f"**Leia antes de usar:**\n\n{corpo}", icon=":material/gavel:")
    with st.expander("Valores da NBR 8800:2008 conferidos na norma", icon=":material/fact_check:"):
        st.markdown("\n".join(f"- {item}" for item in bc.CONFERIDOS_NBR8800_2008))


def _formulario() -> chk.EntradaLigacao | None:
    designacoes = sorted(bc.PARAFUSOS, key=lambda nome: bc.PARAFUSOS[nome][0])

    # ------------------------------------------------------------------ 1. norma e parafuso
    with st.container(border=True):
        st.subheader("1. Norma e parafuso", help=AJUDA["sec_est_1"])
        linha = st.columns(4)
        with linha[0]:
            norma = st.selectbox(
                "Norma",
                list(bc.NORMAS),
                index=list(bc.NORMAS).index("NBR8800_2024"),  # a NBR 8800:2025, vigente
                format_func=lambda n: chk.NORMAS_ROTULOS[n],
                key="ligest_norma",
                persist_state="session",
                help=AJUDA["norma"],
            )
        with linha[1]:
            designacao = st.selectbox(
                "Parafuso",
                designacoes,
                index=designacoes.index("M22"),
                key="ligest_designacao",
                help=AJUDA["parafuso"],
                persist_state="session",
            )
        with linha[2]:
            grau = st.selectbox(
                "Grau (ASTM F3125 / A307)",
                list(bc.GRAUS),
                key="ligest_grau",
                help=AJUDA["grau"],
                persist_state="session",
            )
        with linha[3]:
            n_planos = st.number_input(
                "Planos de corte",
                min_value=1,
                value=1,
                step=1,
                key="ligest_planos",
                persist_state="session",
                help=AJUDA["planos_corte"],
            )
        dados = bc.dados_parafuso(designacao)
        extras = st.columns(4)
        with extras[0]:
            tipo_furo = st.selectbox(
                "Tipo de furo",
                list(bc.TIPOS_DE_FURO),
                format_func=lambda tipo: bc.ROTULOS_DE_FURO[tipo],
                key="ligest_tipo_furo",
                persist_state="session",
                help=AJUDA["tipo_furo"],
            )
        # O furo-padrão da tabela da versão escolhida (a 2008 tem d_b + 1,5 mm).
        furo_padrao = bc.dimensoes_do_furo(designacao, bc.FURO_PADRAO, norma)[0]
        d_h = furo_padrao
        with extras[1]:
            if tipo_furo == bc.FURO_PADRAO:
                d_h = st.number_input(
                    "Furo d_h (mm)",
                    min_value=float(dados["d_b"]),
                    value=round(float(furo_padrao), 1),
                    step=0.1,
                    format="%.1f",
                    key=f"ligest_dh_{designacao}_{norma}",
                    help=AJUDA["furo"],
                    persist_state="session",
                )
            else:
                largura, comprimento = bc.dimensoes_do_furo(designacao, tipo_furo, norma)
                st.metric(
                    "Furo (tabela da norma)",
                    f"{largura:.1f} mm"
                    if largura == comprimento
                    else f"{largura:.1f} × {comprimento:.1f} mm",
                    border=True,
                    help=AJUDA["tipo_furo"],
                )
        with extras[2]:
            rosca_no_plano = st.toggle(
                "Rosca no plano de corte",
                value=True,
                key="ligest_rosca",
                help=AJUDA["rosca_plano"],
                persist_state="session",
            )
        with extras[3]:
            deformacao_limitada = st.toggle(
                "Deformação do furo limitada",
                value=True,
                key="ligest_deformacao",
                help=AJUDA["deformacao_furo"],
                persist_state="session",
            )
        furo_broca = False
        if norma.startswith("NBR"):  # o AISC soma sempre 1/16"
            furo_broca = st.toggle(
                "Furos feitos com broca (área líquida sem os 2 mm)",
                value=False,
                key="ligest_broca",
                help=AJUDA["furo_broca"],
                persist_state="session",
            )
        with st.container(horizontal=True):
            st.metric(
                "Diâmetro d_b", f"{dados['d_b']:.1f} mm", border=True, help=AJUDA["m_diametro"]
            )
            st.metric(
                "Borda mínima (Tab. 16)",
                f"{dados['e_min']:.0f} mm",
                border=True,
                help=AJUDA["m_borda_min"],
            )
            if bc.GRAUS[grau].protendivel:
                st.metric(
                    "Protensão mínima F_Tb",
                    f"{dados['F_Tb'][grau]:.0f} kN",
                    border=True,
                    help=AJUDA["m_protensao"],
                )
            else:
                st.metric("Protensão F_Tb", "não aplicável", border=True, help=AJUDA["m_protensao"])
        if grau == "A307":
            st.info(
                "O A307 não admite protensão: serve só a ligações secundárias, sem atrito.",
                icon=":material/info:",
            )

    # ------------------------------------------------------------------ 2. partes ligadas e geometria
    with st.container(border=True):
        st.subheader("2. Partes ligadas e geometria", help=AJUDA["sec_est_2"])
        chapas = st.columns(3)
        with chapas[0]:
            t = st.number_input(
                "Espessura da parte ligada mais fina t (mm)",
                min_value=0.01,
                value=5.08,
                step=0.01,
                format="%.2f",
                key="ligest_t",
                help=AJUDA["t"],
                persist_state="session",
            )
        with chapas[1]:
            aco = st.selectbox(
                "Aço das partes ligadas",
                [*bc.ACOS, chk.ACO_INFORMADO],
                format_func=lambda nome: (
                    nome
                    if nome == chk.ACO_INFORMADO
                    else f"{nome} (f_y {bc.ACOS[nome][0]} / f_u {bc.ACOS[nome][1]} MPa)"
                ),
                key="ligest_aco",
                persist_state="session",
                help=AJUDA["aco"],
            )
        with chapas[2]:
            pega_mm = st.number_input(
                "Pega — soma das espessuras (mm, opcional)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                key="ligest_pega",
                help=AJUDA["pega"],
                persist_state="session",
            )
        f_y = f_u = None
        if aco == chk.ACO_INFORMADO:
            resistencias = st.columns(2)
            with resistencias[0]:
                f_y = st.number_input(
                    "f_y — escoamento (MPa)",
                    min_value=1.0,
                    value=250.0,
                    step=5.0,
                    key="ligest_fy",
                    persist_state="session",
                    help=AJUDA["f_y"],
                )
            with resistencias[1]:
                f_u = st.number_input(
                    "f_u — ruptura (MPa)",
                    min_value=1.0,
                    value=400.0,
                    step=5.0,
                    key="ligest_fu",
                    persist_state="session",
                    help=AJUDA["f_u"],
                )
        if 0 < pega_mm < t:
            st.error(
                "A pega (soma das espessuras) não pode ser menor que t.", icon=":material/error:"
            )
            return None

        geometria = st.segmented_control(
            "Arranjo dos parafusos",
            [_GEO_GRADE, _GEO_LIVRE],
            default=_GEO_GRADE,
            required=True,
            width="stretch",
            key="ligest_geometria",
            persist_state="session",
            help=AJUDA["arranjo"],
        )
        coordenadas: tuple[tuple[float, float], ...] | None = None
        n_lin = n_col = 1
        s = g = 70.0
        if geometria == _GEO_GRADE:
            grade = st.columns(5)
            with grade[0]:
                n_lin = int(
                    st.number_input(
                        "Fileiras de parafusos n_lin",
                        min_value=1,
                        value=2,
                        step=1,
                        key="ligest_n_lin",
                        persist_state="session",
                        help=AJUDA["n_lin"],
                    )
                )
            with grade[1]:
                n_col = int(
                    st.number_input(
                        "Parafusos por fileira n_col",
                        min_value=1,
                        value=2,
                        step=1,
                        key="ligest_n_col",
                        persist_state="session",
                        help=AJUDA["n_col"],
                    )
                )
            with grade[2]:
                s = st.number_input(
                    "Passo s na direção da força (mm)",
                    min_value=0.1,
                    value=70.0,
                    step=1.0,
                    key="ligest_s",
                    persist_state="session",
                    help=AJUDA["passo"],
                )
            with grade[3]:
                g = st.number_input(
                    "Gabarito g entre fileiras (mm)",
                    min_value=0.1,
                    value=70.0,
                    step=1.0,
                    key="ligest_g",
                    persist_state="session",
                    help=AJUDA["gabarito"],
                )
            with grade[4]:
                e = st.number_input(
                    "Borda e na direção da força (mm)",
                    min_value=0.1,
                    value=70.0,
                    step=1.0,
                    key="ligest_e",
                    help=AJUDA["borda"],
                    persist_state="session",
                )
        else:
            padrao = pd.DataFrame(
                {"x (mm)": [0.0, 70.0, 0.0, 70.0], "y (mm)": [0.0, 0.0, 70.0, 70.0]}
            )
            st.caption("Posição de cada parafuso (mm)", help=AJUDA["coordenadas"])
            editado = st.data_editor(
                padrao,
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                key="ligest_coordenadas",
            )
            validas = editado.dropna()
            coordenadas = tuple((float(x), float(y)) for x, y in validas.itertuples(index=False))
            if not coordenadas:
                st.error("Informe ao menos um parafuso.", icon=":material/error:")
                return None
            e = st.number_input(
                "Borda e na direção da força (mm)",
                min_value=0.1,
                value=70.0,
                step=1.0,
                key="ligest_e_livre",
                persist_state="session",
                help=AJUDA["borda"],
            )
            st.caption(
                "Com coordenadas livres, ℓ_f entre furos usa a menor distância centro a centro; "
                "tração da peça e colapso por rasgamento dependem da grade e não são calculados."
            )
        tem_borda_vertical = st.toggle(
            "Há borda livre na direção vertical (perpendicular à força)",
            value=False,
            key="ligest_tem_ev",
            persist_state="session",
            help=AJUDA["tem_borda_vertical"],
        )
        e_v = None
        if tem_borda_vertical:
            e_v = st.number_input(
                "Borda vertical e_v (mm)",
                min_value=0.1,
                value=40.0,
                step=1.0,
                key="ligest_ev",
                persist_state="session",
                help=AJUDA["borda_vertical"],
            )

    # ------------------------------------------------------------------ 3. esforços
    with st.container(border=True):
        st.subheader("3. Esforços no centro do grupo", help=AJUDA["sec_est_3"])
        modo_esforco = st.segmented_control(
            "Como os parafusos trabalham",
            [_ESF_CORTANTE, _ESF_TRACAO, _ESF_COMBINADO],
            default=_ESF_CORTANTE,
            required=True,
            width="stretch",
            key="ligest_modo_esforco",
            persist_state="session",
            help=AJUDA["modo_esforco"],
        )
        com_corte = modo_esforco != _ESF_TRACAO
        com_tracao = modo_esforco != _ESF_CORTANTE
        st.caption(
            "Esforços **do grupo** (o programa divide pelos parafusos). N atua ao longo das "
            "linhas de parafusos (x) e V é transversal (y), no plano das chapas; N_t puxa os "
            "parafusos pelo comprimento. O ELU usa a força de cálculo; o deslizamento, a de "
            "serviço (característica)."
        )
        base = st.columns([2, 1, 1, 1])
        with base[0]:
            valores_de_calculo = st.toggle(
                "Os valores informados já são de cálculo (majorados)",
                value=False,
                key="ligest_ja_majorado",
                help=AJUDA["ja_calculo"],
                persist_state="session",
            )
        sufixo = "Sd" if valores_de_calculo else "k"
        N = V = 0.0
        if com_corte:
            with base[1]:
                N = st.number_input(
                    f"N_{sufixo} (kN)",
                    value=0.0,
                    step=1.0,
                    key="ligest_N",
                    persist_state="session",
                    help=AJUDA["N"],
                )
            with base[2]:
                V = st.number_input(
                    f"V_{sufixo} (kN)",
                    value=32.0,
                    step=1.0,
                    key="ligest_V",
                    persist_state="session",
                    help=AJUDA["V"],
                )
        with base[3]:
            gama_f = st.number_input(
                "γ_f",
                min_value=1.0,
                value=1.40,
                step=0.05,
                key="ligest_gama_f",
                help=AJUDA["gama_f"],
                persist_state="session",
            )

        opcoes_momento = (
            [_MOM_NENHUM, _MOM_EMENDA, _MOM_EXCENTRICIDADE, _MOM_VALOR]
            if geometria == _GEO_GRADE
            else [_MOM_NENHUM, _MOM_EXCENTRICIDADE, _MOM_VALOR]
        )
        modo_momento = _MOM_NENHUM
        if com_corte:
            modo_momento = st.segmented_control(
                "Momento no centro do grupo",
                opcoes_momento,
                default=_MOM_EMENDA if geometria == _GEO_GRADE else _MOM_NENHUM,
                required=True,
                width="stretch",
                key=f"ligest_momento_{'g' if geometria == _GEO_GRADE else 'l'}",
                persist_state="session",
                help=AJUDA["momento"],
            )
        M = 0.0
        excentricidade: float | None = None
        if modo_momento == _MOM_EMENDA:
            excentricidade = chk.excentricidade_emenda(e, s, n_col)
            st.caption(f"a = e + (n_col − 1)·s/2 = {excentricidade:g} mm  →  M = V·a")
        elif modo_momento == _MOM_EXCENTRICIDADE:
            excentricidade = st.number_input(
                "Excentricidade a da cortante (mm)",
                value=105.0,
                step=5.0,
                key="ligest_a",
                help=AJUDA["excentricidade"],
                persist_state="session",
            )
        elif modo_momento == _MOM_VALOR:
            M = st.number_input(
                f"M_{sufixo} (kN·m)",
                value=0.0,
                step=0.5,
                key="ligest_M",
                persist_state="session",
                help=AJUDA["momento_valor"],
            )
        N_t = M_t = 0.0
        interacao_tabela = False
        if com_tracao:
            tracao = st.columns([1, 1, 2])
            with tracao[0]:
                N_t = st.number_input(
                    f"N_t,{sufixo} do grupo — tração nos parafusos (kN)",
                    min_value=0.0,
                    value=10.0,
                    step=1.0,
                    key="ligest_Nt",
                    persist_state="session",
                    help=AJUDA["N_t"],
                )
            with tracao[1]:
                M_t = st.number_input(
                    f"M_t,{sufixo} fora do plano (kN·m)",
                    value=0.0,
                    step=0.5,
                    key="ligest_Mt",
                    persist_state="session",
                    help=AJUDA["M_t"],
                )
            with tracao[2]:
                if norma.startswith("NBR") and com_corte:
                    interacao_tabela = st.toggle(
                        "Ver também o limite tabelado da tração com corte",
                        value=False,
                        key="ligest_interacao_tabela",
                        persist_state="session",
                        help=AJUDA["interacao_tabela"],
                    )

    alavanca = dict(alavanca=False)
    if com_tracao:
        alavanca = _secao_alavanca(norma, t, d_h)

    # ------------------------------------------------------------------ 4. opções
    with st.container(border=True):
        st.subheader("4. Atrito, instalação e escopo", help=AJUDA["sec_est_4"])
        opcoes = st.columns(4)
        with opcoes[0]:
            superficie = st.selectbox(
                "Superfície de contato",
                list(bc.SUPERFICIES),
                format_func=lambda chave: chk.SUPERFICIES_ROTULOS[chave],
                key="ligest_superficie",
                help=AJUDA["superficie"],
                persist_state="session",
            )
        with opcoes[1]:
            por_atrito = st.toggle(
                "Ligação por atrito",
                value=True,
                key="ligest_atrito",
                help=AJUDA["atrito"],
                persist_state="session",
            )
        with opcoes[2]:
            C_e = st.number_input(
                "C_e (fator do deslizamento)",
                min_value=0.1,
                max_value=2.0,
                value=1.0,
                step=0.05,
                key="ligest_Ce",
                persist_state="session",
                help=AJUDA["Ce"],
            )
        with opcoes[3]:
            K_torque = st.number_input(
                "K do torque (estimativa)",
                min_value=0.05,
                max_value=0.5,
                value=0.20,
                step=0.01,
                key="ligest_K",
                help=AJUDA["K_torque"],
                persist_state="session",
            )
        patinavel = st.toggle(
            "Aço patinável sem pintura",
            value=False,
            key="ligest_patinavel",
            help=AJUDA["patinavel"],
            persist_state="session",
        )
        fora = st.pills(
            "Condições presentes que esta verificação não cobre",
            list(chk.FORA_DO_ESCOPO),
            selection_mode="multi",
            format_func=lambda chave: chk.FORA_DO_ESCOPO[chave],
            key="ligest_fora_escopo",
            help=AJUDA["fora_escopo"],
            persist_state="session",
        )

    # ------------------------------------------------------------------ 5. peça tracionada
    with st.container(border=True):
        st.subheader("5. Peça tracionada (opcional)", help=AJUDA["sec_est_5"])
        st.caption(
            "Necessária para a tração da peça (com C_t) e para a regra dos 75% da Anglo. "
            "A_n desconta os n_lin furos da seção, na espessura t."
        )
        peca = st.columns(2)
        with peca[0]:
            A_g = st.number_input(
                "A_g da peça (mm², 0 = não informada)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="ligest_Ag",
                persist_state="session",
                help=AJUDA["Ag"],
            )
        with peca[1]:
            e_c = st.number_input(
                "Excentricidade da ligação e_c (mm)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="ligest_ec",
                help=AJUDA["ec"],
                persist_state="session",
            )
        chapa_largura = chapa_t = None
        chapa_furos = None
        if st.toggle(
            "Verificar a chapa de ligação (gusset) tracionada",
            value=False,
            key="ligest_chapa",
            persist_state="session",
            help=AJUDA["chapa"],
        ):
            chapa = st.columns(3)
            with chapa[0]:
                chapa_largura = st.number_input(
                    "Largura da chapa na seção (mm)",
                    min_value=1.0,
                    value=150.0,
                    step=5.0,
                    key="ligest_chapa_largura",
                    persist_state="session",
                    help=AJUDA["chapa_largura"],
                )
            with chapa[1]:
                chapa_t = st.number_input(
                    "Espessura da chapa (mm)",
                    min_value=0.01,
                    value=float(t),
                    step=0.01,
                    format="%.2f",
                    key="ligest_chapa_t",
                    persist_state="session",
                    help=AJUDA["chapa_t"],
                )
            with chapa[2]:
                chapa_furos = int(
                    st.number_input(
                        "Furos na seção",
                        min_value=0,
                        value=int(n_lin) if geometria == _GEO_GRADE else 1,
                        step=1,
                        key="ligest_chapa_furos",
                        persist_state="session",
                        help=AJUDA["chapa_furos"],
                    )
                )

    # ------------------------------------------------------------------ 6. Anglo
    with st.container(border=True):
        st.subheader(
            "6. Critério Anglo American (AA-BR-DPST-DR-0001, item 9.1)", help=AJUDA["sec_est_6"]
        )
        anglo = st.columns(3)
        with anglo[0]:
            principal = (
                st.segmented_control(
                    "Tipo da ligação (Anglo)",
                    ["Principal", "Secundária"],
                    default="Principal",
                    required=True,
                    key="ligest_principal",
                    persist_state="session",
                    help=AJUDA["principal"],
                )
                == "Principal"
            )
        with anglo[1]:
            revestimento = st.selectbox(
                "Revestimento do parafuso",
                list(_REVESTIMENTOS),
                format_func=lambda chave: _REVESTIMENTOS[chave],
                key="ligest_revestimento",
                persist_state="session",
                help=AJUDA["revestimento"],
            )
        with anglo[2]:
            por_esbeltez = st.toggle(
                "Peça de treliça/contraventamento por esbeltez ou sem esforço indicado",
                value=False,
                key="ligest_esbeltez",
                help=AJUDA["esbeltez"],
                persist_state="session",
            )

    return chk.EntradaLigacao(
        norma=norma,
        N=N,
        V=V,
        M=M,
        excentricidade_mm=excentricidade,
        gama_f=gama_f,
        valores_sao_de_calculo=valores_de_calculo,
        designacao=designacao,
        grau=grau,
        d_h_mm=None if math.isclose(d_h, round(furo_padrao, 1), abs_tol=1e-9) else d_h,
        tipo_furo=tipo_furo,
        furo_com_broca=furo_broca,
        rosca_no_plano=rosca_no_plano,
        n_planos=int(n_planos),
        t=t,
        aco=aco,
        f_y=f_y,
        f_u=f_u,
        pega=pega_mm if pega_mm > 0 else None,
        n_lin=n_lin,
        n_col=n_col,
        s=s,
        g=g,
        e=e,
        e_v=e_v,
        coordenadas=coordenadas,
        deformacao_limitada=deformacao_limitada,
        superficie=superficie,
        ligacao_por_atrito=por_atrito,
        C_e=C_e,
        patinavel_sem_pintura=patinavel,
        A_g=A_g if A_g > 0 else None,
        e_c=e_c if A_g > 0 else None,
        ligacao_principal=principal,
        revestimento=revestimento,
        peca_por_esbeltez=por_esbeltez,
        K_torque=K_torque,
        fora_do_escopo=tuple(fora or ()),
        N_t=N_t,
        M_t=M_t,
        interacao_por_tabela=interacao_tabela,
        chapa_largura=chapa_largura,
        chapa_t=chapa_t,
        chapa_furos=chapa_furos,
        **alavanca,
    )


def _secao_alavanca(norma: str, t: float, d_h: float) -> dict[str, object]:
    """Os campos do efeito de alavanca (só com tração nos parafusos)."""
    with st.container(border=True):
        st.subheader("Efeito de alavanca", help=AJUDA["sec_est_alavanca"])
        if not st.toggle(
            "A tração passa por uma chapa que pode dobrar (chapa de topo, mesa, cantoneira)",
            value=False,
            key="ligest_alavanca",
            persist_state="session",
            help=AJUDA["alavanca"],
        ):
            return {"alavanca": False}
        linha = st.columns(3)
        with linha[0]:
            a = st.number_input(
                "a — parafuso até a borda livre (mm)",
                min_value=0.1,
                value=35.0,
                step=1.0,
                key="ligest_alav_a",
                persist_state="session",
                help=AJUDA["alav_a"],
            )
        with linha[1]:
            b = st.number_input(
                "b — parafuso até a face da alma (mm)",
                min_value=0.1,
                value=35.0,
                step=1.0,
                key="ligest_alav_b",
                persist_state="session",
                help=AJUDA["alav_b"],
            )
        with linha[2]:
            modo_p = st.segmented_control(
                "Largura tributária p",
                [_P_INFORMADO, _P_EXTREMO, _P_INTERNO],
                default=_P_INFORMADO,
                required=True,
                key="ligest_alav_modo_p",
                persist_state="session",
                help=AJUDA["alav_modo_p"],
            )
        if modo_p == _P_INFORMADO:
            p = st.number_input(
                "p (mm)",
                min_value=0.1,
                value=60.0,
                step=1.0,
                key="ligest_alav_p",
                persist_state="session",
                help=AJUDA["alav_p"],
            )
        else:
            distancias = st.columns(2)
            e_ext = None
            if modo_p == _P_EXTREMO:
                with distancias[0]:
                    e_ext = st.number_input(
                        "e_ext — até a borda (mm)",
                        min_value=0.1,
                        value=40.0,
                        step=1.0,
                        key="ligest_alav_e_ext",
                        persist_state="session",
                        help=AJUDA["alav_e_ext"],
                    )
            with distancias[1]:
                e_int = st.number_input(
                    "e_int — entre parafusos (mm)",
                    min_value=0.1,
                    value=80.0,
                    step=1.0,
                    key="ligest_alav_e_int",
                    persist_state="session",
                    help=AJUDA["alav_e_int"],
                )
            p = bc.largura_tributaria_alavanca(b, e_ext, e_int, extremo=modo_p == _P_EXTREMO)
            st.caption(f"p = {p:.1f} mm")
        outros = st.columns(3)
        with outros[0]:
            d_f = st.number_input(
                "d_f — furo na direção de p (mm)",
                min_value=0.0,
                value=round(float(d_h), 1),
                step=0.1,
                format="%.1f",
                key="ligest_alav_df",
                persist_state="session",
                help=AJUDA["alav_d_f"],
            )
        with outros[1]:
            t_placa = st.number_input(
                "Espessura da chapa que dobra (mm)",
                min_value=0.01,
                value=float(t),
                step=0.01,
                format="%.2f",
                key="ligest_alav_t",
                persist_state="session",
                help=AJUDA["alav_t"],
            )
        with outros[2]:
            F_t = st.number_input(
                "F_t,Sd com alavanca, por parafuso (kN; 0 = não informada)",
                min_value=0.0,
                value=0.0,
                step=0.5,
                key="ligest_alav_Ft",
                persist_state="session",
                help=AJUDA["alav_F_t"],
            )
        plastico = True
        if norma == "NBR8800_2008":
            plastico = st.radio(
                "Método da NBR 8800:2008 (6.3.5.2)",
                ["a) Momento plástico, parafuso −33 %", "b) Momento elástico, parafuso −25 %"],
                horizontal=True,
                key="ligest_alav_metodo",
                persist_state="session",
                help=AJUDA["alav_metodo_2008"],
            ).startswith("a)")
    return {
        "alavanca": True,
        "alav_a": a,
        "alav_b": b,
        "alav_p": p,
        "alav_d_f": d_f,
        "alav_t": t_placa,
        "alav_plastico": plastico,
        "F_t_com_alavanca": F_t if F_t > 0 else None,
    }


_percentual = formatar_percentual


def _painel_resumo(entrada: chk.EntradaLigacao, resultado: chk.ResultadoLigacao) -> str | None:
    menor = chk.menor_parafuso_que_atende(entrada)
    with st.container(border=True):
        st.subheader("Resumo", help=AJUDA["res_resumo"])
        st.badge(
            f"Status geral: {resultado.status_geral}",
            color=COR_BADGE[resultado.status_geral],
            icon=":material/verified:" if resultado.status_geral == "OK" else ":material/rule:",
            help=AJUDA["res_status"],
        )
        with st.container(horizontal=True):
            st.metric(
                "Aproveitamento máximo",
                _percentual(resultado.aproveitamento_max),
                border=True,
                help=AJUDA["res_aproveitamento"],
            )
            st.metric(
                "Menor parafuso que atende",
                menor or "nenhum com esta geometria",
                border=True,
                help=AJUDA["res_menor"],
            )
            if resultado.forcas:
                st.metric(
                    "Parafuso crítico (ELU)",
                    f"{resultado.forcas['R_max_ELU_kN']:.2f} kN",
                    border=True,
                    help=AJUDA["res_critico_elu"],
                )
                st.metric(
                    "Parafuso crítico (serviço)",
                    f"{resultado.forcas['R_max_ELS_kN']:.2f} kN",
                    border=True,
                    help=AJUDA["res_critico_els"],
                )
            if "F_t_Sd_kN" in resultado.forcas:
                st.metric(
                    "Tração no parafuso crítico (ELU)",
                    f"{resultado.forcas['F_t_Sd_kN']:.2f} kN",
                    border=True,
                    help=AJUDA["res_tracao"],
                )
        st.markdown(f"**Verificação que governa:** {resultado.governante}")
        if resultado.forcas:
            partes = [
                f"J = {resultado.forcas['J_mm2']:,.0f} mm²".replace(",", "."),
                f"V_Sd = {resultado.forcas['V_Sd_kN']:.2f} kN",
                f"N_Sd = {resultado.forcas['N_Sd_kN']:.2f} kN",
                f"M_Sd = {resultado.forcas['M_Sd_kNm']:.3f} kN·m",
            ]
            if "excentricidade_mm" in resultado.forcas:
                partes.append(f"a = {resultado.forcas['excentricidade_mm']:g} mm")
            st.caption(" · ".join(partes))
        if resultado.torque_referencia_Nm is not None:
            st.caption(
                f"Referência de instalação: torque ≈ {resultado.torque_referencia_Nm:.0f} N·m "
                "(estimativa T = K·F_Tb·d; instale por rotação da porca, chave calibrada ou "
                "indicador de tração)."
            )
    return menor


def _varreduras(entrada: chk.EntradaLigacao) -> None:
    botoes = st.columns(2)
    with botoes[0]:
        if st.button(
            "Comparar normas",
            icon=":material/compare_arrows:",
            width="stretch",
            key="ligest_btn_comparar",
            help=AJUDA["btn_comparar"],
        ):
            st.session_state["ligest_ver_comparacao"] = not st.session_state.get(
                "ligest_ver_comparacao", False
            )
    with botoes[1]:
        if st.button(
            "Testar todos os parafusos",
            icon=":material/checklist:",
            width="stretch",
            key="ligest_btn_testar",
            help=AJUDA["btn_testar"],
        ):
            st.session_state["ligest_ver_varredura"] = not st.session_state.get(
                "ligest_ver_varredura", False
            )

    if st.session_state.get("ligest_ver_comparacao"):
        with st.container(border=True):
            st.markdown("**Mesma ligação nas quatro normas**")
            linhas = [
                {
                    "Norma": item["rotulo"],
                    "Status": item["status"],
                    "Aproveitamento máx. (%)": (
                        None
                        if item.get("aproveitamento_max") is None
                        else 100 * item["aproveitamento_max"]
                    ),
                    "Governa": item.get("governante", ""),
                    "F_v,Rd (kN)": item.get("F_v_Rd_kN"),
                    "F_c,Rd (kN)": item.get("F_c_Rd_kN"),
                    "F_f,Rk (kN)": item.get("F_f_Rk_kN"),
                    "Observação": item.get("erro", ""),
                }
                for item in chk.comparar_normas(entrada)
            ]
            tabela = pd.DataFrame(linhas)
            estilo = estilizar(
                tabela,
                {
                    "Aproveitamento máx. (%)": "{:.0f}",
                    "F_v,Rd (kN)": "{:.1f}",
                    "F_c,Rd (kN)": "{:.1f}",
                    "F_f,Rk (kN)": "{:.2f}",
                },
            )
            st.dataframe(
                estilo,
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "“—” em F_f,Rk: a norma não define μ para a superfície escolhida (RCSC/AISC exigem "
                "ensaio para galvanizado sem tratamento) ou o grau não se aplica."
            )

    if st.session_state.get("ligest_ver_varredura"):
        with st.container(border=True):
            varredura = chk.testar_todos_parafusos(entrada)
            menor = next((item for item in varredura if item["atende"]), None)
            if menor is None:
                st.error(
                    "Nenhum parafuso da tabela atende com a geometria e os esforços informados.",
                    icon=":material/error:",
                )
            else:
                st.success(
                    f"Menor parafuso que atende: **{menor['designacao']}** "
                    f"(d_b = {menor['d_b_mm']:.1f} mm, aproveitamento "
                    f"{_percentual(menor['aproveitamento_max'])}).",
                    icon=":material/check_circle:",
                )
            tabela = pd.DataFrame(
                [
                    {
                        "Parafuso": item["designacao"],
                        "d_b (mm)": item["d_b_mm"],
                        "Status": item["status"],
                        "Aproveitamento máx. (%)": (
                            None
                            if item["aproveitamento_max"] is None
                            else 100 * item["aproveitamento_max"]
                        ),
                        "Governa": item["governante"],
                    }
                    for item in varredura
                ]
            )
            estilo = estilizar(tabela, {"d_b (mm)": "{:.1f}", "Aproveitamento máx. (%)": "{:.0f}"})
            st.dataframe(
                estilo,
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "A varredura usa a mesma geometria e os mesmos esforços, com o furo-padrão e a "
                "borda mínima de cada parafuso. “Atende” = nenhuma verificação NÃO OK."
            )


def _distribuicao(resultado: chk.ResultadoLigacao) -> None:
    if not resultado.coordenadas:
        return
    with st.container(border=True):
        st.subheader(
            "Distribuição entre os parafusos (ELU, método elástico)", help=AJUDA["res_distribuicao"]
        )
        linhas = [
            {
                "Parafuso": indice + 1,
                "x (mm)": x,
                "y (mm)": y,
                "F_x (kN)": fx,
                "F_y (kN)": fy,
                "Resultante (kN)": r,
            }
            for indice, ((x, y), (fx, fy, r)) in enumerate(
                zip(resultado.coordenadas, resultado.forcas_parafusos, strict=True)
            )
        ]
        tabela = pd.DataFrame(linhas)
        visual, dados = st.columns([1, 1.4])
        with visual:
            st.scatter_chart(tabela, x="x (mm)", y="y (mm)", size="Resultante (kN)")
        with dados:
            st.dataframe(
                tabela,
                hide_index=True,
                column_config={
                    "x (mm)": st.column_config.NumberColumn(format="%.1f"),
                    "y (mm)": st.column_config.NumberColumn(format="%.1f"),
                    "F_x (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "F_y (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "Resultante (kN)": st.column_config.NumberColumn(format="%.2f"),
                },
            )


def _registro(
    entrada: chk.EntradaLigacao, resultado: chk.ResultadoLigacao, menor: str | None
) -> None:
    pior = resultado.aproveitamento_max
    registro = chk.registro_ligacao(entrada, resultado, menor)

    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        st.subheader("Comparar cenários", divider=False, help=AJUDA["reg_comparar"])
        comparador_cenarios(
            escopo="projeto_parafusos_estrutural",
            resumo_entradas={
                "Norma": chk.NORMAS_ROTULOS[entrada.norma].split(" (")[0],
                "Parafuso": f"{entrada.designacao} {entrada.grau}",
                "V (kN)": round(entrada.V, 1),
                "N (kN)": round(entrada.N, 1),
            },
            metricas={
                "Status": resultado.status_geral,
                "Aprov. máx.": _percentual(pior),
                "Governa": resultado.governante[:40],
            },
        )
        botao_registrar_calculo(
            registro,
            key="registrar_projeto_parafusos_estrutural",
            rotulo="Registrar ligação parafusada no projeto ativo",
        )


def _memorial(
    entrada: chk.EntradaLigacao, resultado: chk.ResultadoLigacao, menor: str | None
) -> None:
    """Word e PDF do memorial desta ligação, gerados só no clique."""
    from core.project_store import obter_projeto_ativo

    projeto = obter_projeto_ativo()
    parafuso = entrada.designacao.replace('"', "pol")
    nome = f"memorial_ligacao_{parafuso}_{entrada.grau}"
    botoes = st.columns(2)
    with botoes[0]:
        st.download_button(
            "Baixar o memorial desta ligação (Word)",
            data=lambda: chk.memorial_da_ligacao(entrada, resultado, menor, projeto=projeto),
            file_name=f"{nome}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            icon=":material/description:",
            width="stretch",
            on_click="ignore",
            key="ligest_memorial_word",
            help=AJUDA["btn_memorial_word"],
        )
    with botoes[1]:
        st.download_button(
            "Baixar o memorial desta ligação (PDF)",
            data=lambda: chk.memorial_da_ligacao(
                entrada, resultado, menor, projeto=projeto, formato="pdf"
            ),
            file_name=f"{nome}.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            width="stretch",
            on_click="ignore",
            key="ligest_memorial_pdf",
            help=AJUDA["btn_memorial_pdf"],
        )


def mostrar_ligacao_estrutural() -> None:
    """Desenha o modo estrutural completo (entradas, resultados, varreduras e registro)."""
    st.info(
        "Verificação pela norma estrutural: von Mises, carga de prova e torque **não** são "
        "critérios de aprovação aqui. O torque aparece só como referência de instalação.",
        icon=":material/domain:",
    )
    _avisos_fixos()

    entrada = _formulario()
    if entrada is None:
        return
    try:
        resultado = chk.verificar_ligacao(entrada)
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        return

    st.header("Resultados da verificação")
    menor = _painel_resumo(entrada, resultado)

    with st.container(border=True):
        st.subheader("Tabela de verificações", help=AJUDA["res_tabela"])
        mostrar_tabela_verificacoes(resultado.verificacoes)
        st.download_button(
            "Baixar verificações em CSV",
            data=csv_verificacoes(resultado.verificacoes),
            file_name="ligacao_parafusada.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="ligest_baixar_csv",
            help=AJUDA["btn_csv"],
        )
        _memorial(entrada, resultado, menor)
        with st.expander(
            "Fórmula e item da norma de cada verificação", icon=":material/functions:"
        ):
            for v in resultado.verificacoes:
                st.markdown(f"**{v.nome}** — `{v.status}` · {v.referencia}")
                if v.formula:
                    st.caption(v.formula)
        _varreduras(entrada)

    _distribuicao(resultado)

    fronteira_modelo(
        [chk.FORA_DO_ESCOPO[chave] for chave in chk.FORA_DO_ESCOPO]
        + [
            "Centro instantâneo de rotação do grupo (o método elástico usado é conservador).",
            "Torque real de aperto e verificação de instalação em campo.",
        ]
    )
    _registro(entrada, resultado, menor)

    with st.container(border=True):
        st.subheader("Precisa de ajuda para preencher ou interpretar?")
        st.markdown(
            "O **Guia geral** traz o caso da emenda de perfis U passo a passo, com a origem de "
            "cada entrada e a leitura de cada verificação."
        )
        st.page_link(
            "app_pages/guia_geral.py",
            label="Abrir o guia de parafusos",
            icon=":material/help:",
            query_params={"modulo": "Projeto de parafusos"},
            width="stretch",
        )
    st.caption(
        "Referências: ABNT NBR 8800:2025 e NBR 8800:2008; AISC 360 (J3, J4) e Design Guide 29; "
        "RCSC (2004); Anglo American AA-BR-DPST-DR-0001, item 9.1."
    )
