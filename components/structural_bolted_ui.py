"""Modo "Ligação estrutural de aço" da página Projeto de parafusos.

Só desenha a interface: todo cálculo está em ``core.bolted_joint_check`` (que usa as
fórmulas de ``core.bolted_connection``). A verificação roda a cada interação; as
varreduras "Comparar normas" e "Testar todos" são botões que ligam e desligam um painel.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from components.bolted_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import comparador_cenarios, fronteira_modelo
from core import bolted_connection as bc
from core import bolted_joint_check as chk

_COR_STATUS = {
    "OK": "background-color: rgba(34, 197, 94, 0.28)",
    "NÃO OK": "background-color: rgba(239, 68, 68, 0.34)",
    "ALERTA": "background-color: rgba(245, 158, 11, 0.34)",
    "INFO": "background-color: rgba(59, 130, 246, 0.22)",
    "N/A": "background-color: rgba(148, 163, 184, 0.25)",
}
_COR_BADGE = {"OK": "green", "NÃO OK": "red", "ALERTA": "orange", "INFO": "blue", "N/A": "gray"}

_GEO_GRADE = "Grade retangular"
_GEO_LIVRE = "Coordenadas livres"

_MOM_NENHUM = "Sem momento"
_MOM_EMENDA = "Emenda por sobreposição"
_MOM_EXCENTRICIDADE = "Excentricidade a informada"
_MOM_VALOR = "Momento M informado"

_REVESTIMENTOS = {
    "galvanizado_fogo": "Galvanizado a fogo (padrão Anglo)",
    "zinco_aluminio": "Zn/Al (ASTM F1136, Dacromet)",
    "outro": "Outro / sem revestimento",
}


def _chaves_estilo(estilo: Any) -> Any:
    """``Styler.map`` (pandas ≥ 2.1) ou o antigo ``applymap`` (pandas 2.0)."""
    return getattr(estilo, "map", None) or estilo.applymap


def _celula(valor: Any, formato: str) -> str:
    """Número formatado, ou “—” quando não há valor (o Streamlit mostraria “None”)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    return formato.format(valor)


def _estilizar(tabela: pd.DataFrame, formatos: dict[str, str]) -> Any:
    """Versão de exibição: números como texto formatado e a coluna Status colorida.

    Os valores exatos continuam no DataFrame de origem, no CSV e no registro técnico.
    """
    exibicao = tabela.copy()
    for coluna, formato in formatos.items():
        exibicao[coluna] = [_celula(valor, formato) for valor in tabela[coluna]]
    return _chaves_estilo(exibicao.style)(
        lambda valor: _COR_STATUS.get(valor, ""), subset=["Status"]
    )


def mostrar_tabela_verificacoes(verificacoes: Any) -> pd.DataFrame:
    """Tabela de oito colunas, com a coluna Status colorida. Devolve o DataFrame cru."""
    tabela = pd.DataFrame(chk.tabela_verificacoes(verificacoes), columns=list(chk.COLUNAS_TABELA))
    estilo = _estilizar(
        tabela, {"Solicitante": "{:.2f}", "Resistente": "{:.2f}", "Aproveitamento": "{:.0f}"}
    )
    st.dataframe(
        estilo,
        hide_index=True,
        width="stretch",
        column_config={
            "Verificação": st.column_config.TextColumn(width="large"),
            "Solicitante": st.column_config.TextColumn(
                width="small", help=AJUDA["col_solicitante"]
            ),
            "Resistente": st.column_config.TextColumn(width="small", help=AJUDA["col_resistente"]),
            "Unidade": st.column_config.TextColumn(width="small", help=AJUDA["col_unidade"]),
            "Aproveitamento": st.column_config.TextColumn(
                "Aproveitamento (%)", width="small", help=AJUDA["col_aproveitamento"]
            ),
            "Status": st.column_config.TextColumn(width="small", help=AJUDA["col_status"]),
            "Fórmula": st.column_config.TextColumn(width="large", help=AJUDA["col_formula"]),
            "Referência": st.column_config.TextColumn(width="medium", help=AJUDA["col_referencia"]),
        },
    )
    return tabela


def _avisos_fixos() -> None:
    corpo = "\n".join(f"- {aviso}" for aviso in chk.AVISOS_FIXOS)
    st.warning(f"**Leia antes de usar:**\n\n{corpo}", icon=":material/gavel:")
    with st.expander("Valores da NBR 8800:2008 marcados “CONFERIR”", icon=":material/fact_check:"):
        st.markdown("\n".join(f"- {item}" for item in bc.CONFERIR_NBR8800_2008))
        st.caption(
            "Foram trazidos de memória no módulo de referência, porque a norma vigente não estava "
            "disponível. Confirme na NBR 8800:2008 antes de liberar o documento."
        )


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
        extras = st.columns(3)
        with extras[0]:
            d_h = st.number_input(
                "Furo d_h (mm)",
                min_value=float(dados["d_b"]),
                value=float(dados["d_h"]),
                step=0.1,
                format="%.1f",
                key=f"ligest_dh_{designacao}",
                help=AJUDA["furo"],
                persist_state="session",
            )
        with extras[1]:
            rosca_no_plano = st.toggle(
                "Rosca no plano de corte",
                value=True,
                key="ligest_rosca",
                help=AJUDA["rosca_plano"],
                persist_state="session",
            )
        with extras[2]:
            deformacao_limitada = st.toggle(
                "Deformação do furo limitada",
                value=True,
                key="ligest_deformacao",
                help=AJUDA["deformacao_furo"],
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
                list(bc.ACOS),
                format_func=lambda nome: (
                    f"{nome} (f_y {bc.ACOS[nome][0]} / f_u {bc.ACOS[nome][1]} MPa)"
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
        st.caption(
            "N atua ao longo das linhas de parafusos (direção x); V é transversal (direção y). "
            "O ELU usa a força de cálculo; o deslizamento usa a de serviço (característica)."
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
                "Peça de treliça/contraventamento dimensionada por esbeltez",
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
        d_h_mm=None if math.isclose(d_h, dados["d_h"], abs_tol=1e-9) else d_h,
        rosca_no_plano=rosca_no_plano,
        n_planos=int(n_planos),
        t=t,
        aco=aco,
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
    )


_percentual = chk.formatar_percentual


def _painel_resumo(entrada: chk.EntradaLigacao, resultado: chk.ResultadoLigacao) -> str | None:
    menor = chk.menor_parafuso_que_atende(entrada)
    with st.container(border=True):
        st.subheader("Resumo", help=AJUDA["res_resumo"])
        st.badge(
            f"Status geral: {resultado.status_geral}",
            color=_COR_BADGE[resultado.status_geral],
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
            estilo = _estilizar(
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
            estilo = _estilizar(tabela, {"d_b (mm)": "{:.1f}", "Aproveitamento máx. (%)": "{:.0f}"})
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
            data=chk.csv_verificacoes(resultado.verificacoes),
            file_name="ligacao_parafusada.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="ligest_baixar_csv",
            help=AJUDA["btn_csv"],
        )
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
        "Referências: ABNT NBR 8800:2008 e Projeto NBR 8800:2024; AISC 360 (J3, J4) e Design "
        "Guide 29; RCSC (2004); Anglo American AA-BR-DPST-DR-0001, item 9.1. Confirme sempre a "
        "edição vigente da norma aplicável."
    )
