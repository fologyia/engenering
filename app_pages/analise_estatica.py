import math
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina
from core import materials as mat
from core import static_analysis as est
from core.materials_registry import avaliar_material, resumir_fonte
from core.project_store import obter_projeto_ativo


st.set_page_config(
    page_title="Análise estática",
    page_icon=":material/analytics:",
    layout="wide",
)
cabecalho_pagina(
    "Análise estática",
    "Estado plano de tensões • von Mises • tensões principais • segurança",
    categoria="Análises",
    icone=":material/analytics:",
    cor="blue",
    ajuda_modulo="Análise estática",
)

st.session_state.setdefault("estatica_sigma_x", 100.0)
st.session_state.setdefault("estatica_sigma_y", 0.0)
st.session_state.setdefault("estatica_tau_xy", 0.0)

try:
    nomes = mat.listar_nomes()
except (FileNotFoundError, ValueError) as erro:
    st.error(f"Não foi possível carregar a base de materiais: {erro}")
    st.stop()

projeto_ativo = obter_projeto_ativo()
materiais_projeto = (projeto_ativo or {}).get("materiais_projeto", [])
opcoes_materiais = {"manual": "— entrada manual —"}
for item in materiais_projeto:
    opcoes_materiais[f"projeto::{item['id']}"] = f"Projeto · {item.get('nome')} · {avaliar_material(item)['nivel']}"
for nome in nomes:
    opcoes_materiais[f"catalogo::{nome}"] = f"Catálogo orientativo · {nome}"
escolha_id = st.selectbox(
    "Material de referência (opcional)",
    list(opcoes_materiais),
    format_func=lambda valor: opcoes_materiais[valor],
)
escolha = opcoes_materiais[escolha_id]
material_id = None
if escolha_id == "manual":
    dados = None
elif escolha_id.startswith("projeto::"):
    material_id = escolha_id.split("::", 1)[1]
    material_projeto = next(item for item in materiais_projeto if item["id"] == material_id)
    props = material_projeto.get("propriedades", {})
    dados = {
        "Sy_MPa": props.get("Sy_MPa") or 0.0,
        "Sut_MPa": props.get("Sut_MPa") or 0.0,
        "observacao": resumir_fonte(material_projeto),
        "nivel_confianca": avaliar_material(material_projeto)["nivel"],
    }
else:
    nome_catalogo = escolha_id.split("::", 1)[1]
    dados = mat.obter_material(nome_catalogo)
base_valida = bool(dados and dados["Sy_MPa"] > 0 and dados["Sut_MPa"] > 0)
usar_base = st.checkbox(
    "Usar Sy e Sut deste material",
    value=base_valida,
    disabled=not base_valida,
)
if dados:
    st.caption(
        f"Base: Sy = {dados['Sy_MPa']:.0f} MPa | Sut = {dados['Sut_MPa']:.0f} MPa "
        f"— {dados['observacao']}"
    )
    if dados.get("nivel_confianca") == "Referência":
        st.warning("Valor de catálogo orientativo: confirme a propriedade antes de emitir o memorial.")
    else:
        st.info(f"Confiança documental do cadastro: {dados.get('nivel_confianca')}. A aplicabilidade técnica ainda deve ser conferida.")
    if not base_valida:
        st.warning(
            "Este material não possui Sy válido para o critério de von Mises. "
            "Informe propriedades manuais ou use um critério apropriado a materiais frágeis."
        )

with st.form("formulario_estatico"):
    st.subheader("Entradas")
    tensoes, propriedades = st.columns(2)
    with tensoes:
        st.markdown("**Estado de tensões no ponto crítico**")
        sigma_x = st.number_input(
            "σx (MPa)", step=10.0, key="estatica_sigma_x"
        )
        sigma_y = st.number_input(
            "σy (MPa)", step=10.0, key="estatica_sigma_y"
        )
        tau_xy = st.number_input(
            "τxy (MPa)", step=10.0, key="estatica_tau_xy"
        )
    with propriedades:
        st.markdown("**Propriedades do material**")
        Sy_padrao = float(dados["Sy_MPa"]) if base_valida else 250.0
        Sut_padrao = float(dados["Sut_MPa"]) if base_valida else 400.0
        Sy_manual = st.number_input(
            "Sy — limite de escoamento (MPa)",
            min_value=0.1,
            value=Sy_padrao,
            step=10.0,
            disabled=usar_base,
            key=f"sy_{escolha}",
        )
        Sut_manual = st.number_input(
            "Sut — resistência à ruptura (MPa)",
            min_value=0.1,
            value=Sut_padrao,
            step=10.0,
            disabled=usar_base,
            key=f"sut_{escolha}",
        )
    calcular = st.form_submit_button(
        "Calcular análise", type="primary", icon=":material/calculate:"
    )

if calcular:
    Sy = float(dados["Sy_MPa"]) if usar_base else Sy_manual
    Sut = float(dados["Sut_MPa"]) if usar_base else Sut_manual
    try:
        if Sy > Sut:
            raise ValueError("Sy não pode ser maior que Sut para este modelo.")

        sigma_vm = est.tensao_von_mises_plana(sigma_x, sigma_y, tau_xy)
        s1, s2 = est.tensoes_principais_planas(sigma_x, sigma_y, tau_xy)
        n_esc = est.fator_seguranca_escoamento(sigma_vm, Sy)
        n_rup = est.fator_seguranca_ruptura(sigma_vm, Sut)

        st.subheader("Resultados")
        with st.container(horizontal=True):
            st.metric("von Mises", f"{sigma_vm:.2f} MPa", border=True)
            st.metric("Tensão principal σ1", f"{s1:.2f} MPa", border=True)
            st.metric("Tensão principal σ2", f"{s2:.2f} MPa", border=True)
            st.metric(
                "Segurança ao escoamento",
                "∞" if math.isinf(n_esc) else f"{n_esc:.2f}",
                border=True,
            )

        if n_esc < 1:
            st.error("Escoamento previsto: a tensão equivalente supera Sy.")
        elif n_esc < 1.5:
            st.warning("Margem contra escoamento baixa: n < 1,5.")
        else:
            st.success("O estado informado permanece abaixo do limite de escoamento.")

        grafico_esforcos, grafico_mohr = st.columns(2)
        with grafico_esforcos:
            with st.container(border=True):
                st.subheader("Resumo das tensões")
                df_tensoes = pd.DataFrame(
                    {
                        "Componente": ["σx", "σy", "τxy", "σ1", "σ2", "von Mises"],
                        "Tensão (MPa)": [sigma_x, sigma_y, tau_xy, s1, s2, sigma_vm],
                    }
                )
                barras = (
                    alt.Chart(df_tensoes)
                    .mark_bar()
                    .encode(
                        x=alt.X("Componente:N", sort=None, title=None),
                        y=alt.Y("Tensão (MPa):Q"),
                        color=alt.condition(
                            "datum['Tensão (MPa)'] >= 0",
                            alt.value("#2f80ed"),
                            alt.value("#e05a47"),
                        ),
                        tooltip=[
                            "Componente:N",
                            alt.Tooltip("Tensão (MPa):Q", format=".2f"),
                        ],
                    )
                    .properties(height=330)
                )
                st.altair_chart(barras, width="stretch")

        with grafico_mohr:
            with st.container(border=True):
                st.subheader("Círculo de Mohr")
                centro = (sigma_x + sigma_y) / 2
                raio = math.sqrt(((sigma_x - sigma_y) / 2) ** 2 + tau_xy**2)
                angulos = np.linspace(0, 2 * np.pi, 241)
                circulo = pd.DataFrame(
                    {
                        "σ (MPa)": centro + raio * np.cos(angulos),
                        "τ (MPa)": raio * np.sin(angulos),
                        "ordem": np.arange(len(angulos)),
                    }
                )
                pontos = pd.DataFrame(
                    {
                        "σ (MPa)": [sigma_x, sigma_y, s1, s2],
                        "τ (MPa)": [tau_xy, -tau_xy, 0.0, 0.0],
                        "Ponto": ["x", "y", "σ1", "σ2"],
                    }
                )
                linha = alt.Chart(circulo).mark_line().encode(
                    x=alt.X("σ (MPa):Q", scale=alt.Scale(zero=False)),
                    y=alt.Y("τ (MPa):Q", scale=alt.Scale(zero=False)),
                    order="ordem:Q",
                )
                marcadores = alt.Chart(pontos).mark_point(size=90, filled=True).encode(
                    x="σ (MPa):Q",
                    y="τ (MPa):Q",
                    color=alt.Color("Ponto:N"),
                    tooltip=[
                        "Ponto:N",
                        alt.Tooltip("σ (MPa):Q", format=".2f"),
                        alt.Tooltip("τ (MPa):Q", format=".2f"),
                    ],
                )
                st.altair_chart((linha + marcadores).properties(height=330), width="stretch")

        with st.container(border=True):
            st.subheader("Utilização das resistências")
            utilizacao = pd.DataFrame(
                {
                    "Verificação": ["Escoamento", "Ruptura"],
                    "Utilização": [sigma_vm / Sy, sigma_vm / Sut],
                }
            )
            barras = alt.Chart(utilizacao).mark_bar().encode(
                x=alt.X("Utilização:Q", title="Tensão equivalente / resistência"),
                y=alt.Y("Verificação:N", title=None),
                color=alt.condition(
                    "datum.Utilização >= 1",
                    alt.value("#d62728"),
                    alt.value("#2ca02c"),
                ),
                tooltip=[
                    "Verificação:N",
                    alt.Tooltip("Utilização:Q", format=".1%"),
                ],
            )
            limite = alt.Chart(pd.DataFrame({"limite": [1.0]})).mark_rule(
                color="#d62728", strokeDash=[5, 5]
            ).encode(x="limite:Q")
            st.altair_chart((barras + limite).properties(height=140), width="stretch")
            st.caption(f"Fator contra ruptura: {'∞' if math.isinf(n_rup) else f'{n_rup:.2f}'}.")
        status_registro = "Não atende" if n_esc < 1.0 else ("Atenção" if n_esc < 1.5 else "Atende")
        conclusao_registro = (
            "A tensão equivalente supera o limite de escoamento informado."
            if n_esc < 1.0
            else (
                "O estado permanece abaixo de Sy, porém com margem inferior a 1,5."
                if n_esc < 1.5
                else "O estado informado permanece abaixo do limite de escoamento com n ≥ 1,5."
            )
        )
        registro = construir_registro_tecnico(
            modulo="Análise estática",
            titulo="Verificação do estado plano de tensões",
            status=status_registro,
            resumo="Cálculo de tensões principais, von Mises e margens contra escoamento e ruptura.",
            entradas={
                "sigma_x_MPa": sigma_x,
                "sigma_y_MPa": sigma_y,
                "tau_xy_MPa": tau_xy,
                "material": escolha if usar_base else "Propriedades informadas manualmente",
                "material_id": material_id if usar_base else None,
                "Sy_MPa": Sy,
                "Sut_MPa": Sut,
            },
            resultados={
                "sigma_1_MPa": s1,
                "sigma_2_MPa": s2,
                "von_mises_MPa": sigma_vm,
                "fator_seguranca": n_esc if math.isfinite(n_esc) else None,
                "fator_seguranca_minimo": 1.5,
                "fator_ruptura": n_rup if math.isfinite(n_rup) else None,
                "utilizacao_maxima": sigma_vm / Sy,
            },
            premissas=[
                "Estado plano de tensões no ponto informado.",
                "Critério de von Mises aplicável a material dúctil isotrópico.",
            ],
            alertas=[] if n_esc >= 1.5 else [conclusao_registro],
            referencias=["Propriedades e critérios devem ser confirmados na norma ou especificação do projeto."],
            conclusao=conclusao_registro,
        )
        botao_registrar_calculo(registro, key="registrar_analise_estatica")
    except ValueError as erro:
        st.error(str(erro))
