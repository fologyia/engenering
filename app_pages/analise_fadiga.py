import math
import sys
from datetime import date
from functools import partial
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina, comparador_cenarios, fronteira_modelo
from core import fatigue as fat
from core import fatigue_report, memorial_word
from core import materials as mat
from core import size_effect as size

st.set_page_config(
    page_title="Análise de fadiga",
    page_icon=":material/cycle:",
    layout="wide",
)
cabecalho_pagina(
    "Análise de fadiga",
    "Fatores de Marin • Goodman e Soderberg • curva S–N • estimativa de vida",
    categoria="Análises",
    icone=":material/cycle:",
    cor="green",
    ajuda_modulo="Análise de fadiga",
    modulo_id="analise_fadiga",
)

ROTULOS_MATERIAL = {
    "aco": "Aço",
    "ferro": "Ferro fundido",
    "aluminio": "Alumínio",
    "cobre": "Cobre",
}
MAPA_CATEGORIA = {
    "aco": "aco",
    "ferro": "ferro",
    "ferro_fundido": "ferro",
    "aluminio": "aluminio",
    "cobre": "cobre",
}
ROTULOS_CARGA = {
    "flexao": "Flexão",
    "axial": "Axial",
    "torcao_von_mises": "Torção — tensão equivalente de von Mises",
}
ROTULOS_MODELO = {
    "norton": "Norton — 4ª edição",
    "shigley": "Shigley — 8ª edição",
}
ROTULOS_ACABAMENTO = {
    "retificado": "Retificado",
    "usinado_ou_estirado_a_frio": "Usinado ou estirado a frio",
    "laminado_a_quente": "Laminado a quente",
    "forjado": "Forjado",
}

st.session_state.setdefault("fadiga_sigma_alternada_nominal", 180.0)
st.session_state.setdefault("fadiga_sigma_media", 50.0)

st.info(
    "A resistência corrigida é atualizada automaticamente por "
    r"$S_e=C_{carreg}\,C_{tamanho}\,C_{superf}\,C_{temp}\,C_{conf}\,S'_e$. "
    "Cada bloco abaixo mostra como seu fator é obtido."
)

modelo = st.segmented_control(
    "Referência para os fatores de Marin",
    list(ROTULOS_MODELO),
    format_func=ROTULOS_MODELO.get,
    default="norton",
    required=True,
    width="stretch",
    key="fadiga_modelo_marin",
    persist_state="session",
)
st.caption(f"Fonte ativa: {fat.FONTES_MARIN[modelo]}.")

try:
    nomes = mat.listar_nomes()
except (FileNotFoundError, ValueError) as erro:
    st.error(f"Não foi possível carregar a base de materiais: {erro}")
    st.stop()

with st.container(border=True):
    st.subheader("1. Material de referência")
    material_esquerda, material_direita = st.columns([1, 1])
    with material_esquerda:
        escolha = st.selectbox(
            "Material da base (opcional)",
            ["— entrada manual —"] + nomes,
            key="fadiga_material_escolha",
            persist_state="session",
        )
        dados = None if escolha == "— entrada manual —" else mat.obter_material(escolha)
        classe_base = MAPA_CATEGORIA.get(dados["categoria"]) if dados else None
        base_valida = bool(dados and classe_base and dados["Sut_MPa"] > 0)
        usar_base_widget = st.toggle(
            "Usar classe, Sut e Sy do material selecionado",
            value=base_valida,
            disabled=not base_valida,
            key=f"fadiga_usar_base_{escolha}",
            persist_state="session",
        )
        usar_base = bool(base_valida and usar_base_widget)
        if dados:
            st.caption(
                f"Base: Sut = {dados['Sut_MPa']:.0f} MPa | "
                f"Sy = {dados['Sy_MPa']:.0f} MPa | "
                f"{ROTULOS_MATERIAL.get(classe_base, dados['categoria'])} — "
                f"{dados['observacao']}"
            )

    with material_direita:
        opcoes_material = list(ROTULOS_MATERIAL)
        classe_padrao = classe_base if base_valida else "aco"
        material_manual = st.selectbox(
            "Classe do material",
            opcoes_material,
            index=opcoes_material.index(classe_padrao),
            format_func=ROTULOS_MATERIAL.get,
            disabled=usar_base,
            key=f"classe_{escolha}",
            persist_state="session",
        )
        Sut_padrao = float(dados["Sut_MPa"]) if base_valida else 600.0
        Sut_manual = st.number_input(
            "Resistência à tração, Sut (MPa)",
            min_value=1.0,
            value=Sut_padrao,
            step=10.0,
            disabled=usar_base,
            key=f"sut_fadiga_{escolha}",
            persist_state="session",
        )
        Sy_padrao = float(dados["Sy_MPa"]) if base_valida else 400.0
        Sy_manual = st.number_input(
            "Limite de escoamento, Sy (MPa)",
            min_value=0.0,
            value=Sy_padrao,
            step=10.0,
            disabled=usar_base,
            key=f"sy_fadiga_{escolha}",
            help="Necessário para Soderberg e para a verificação de escoamento.",
            persist_state="session",
        )

material = classe_base if usar_base else material_manual
Sut = float(dados["Sut_MPa"]) if usar_base else Sut_manual
Sy = float(dados["Sy_MPa"]) if usar_base else Sy_manual
if Sy > Sut:
    st.error(
        "Dados incompatíveis: Sy não pode ser maior que Sut. "
        "Corrija as propriedades do material para continuar."
    )
    st.stop()
Se_linha, vida_infinita = fat.se_linha(Sut, material)

with st.container(border=True):
    st.subheader("2. Fator de carregamento")
    carga_controle, carga_referencia = st.columns([0.8, 1.2])
    with carga_controle:
        tipo_carga = st.selectbox(
            "Tipo de carregamento",
            list(ROTULOS_CARGA),
            format_func=ROTULOS_CARGA.get,
            key="fadiga_tipo_carregamento",
            persist_state="session",
        )
        Ccarreg = fat.fator_carregamento(tipo_carga, modelo)
        st.metric("Ccarreg", f"{Ccarreg:.3f}", border=True)
        st.caption(
            "Corrige a diferença entre o ensaio padrão de flexão rotativa "
            "e o tipo de solicitação real da peça. Para torção, o fluxo "
            "completo usa a tensão equivalente de von Mises."
        )
        st.info(
            "A comparação direta com τ exige resistências próprias em "
            "cisalhamento (Ssu e Ssy). Sem essas entradas, ela não é usada "
            "em Goodman, Soderberg ou na curva S–N desta tela."
        )
    with carga_referencia:
        tabela_carga = pd.DataFrame(
            {
                "Carregamento": [ROTULOS_CARGA[chave] for chave in ROTULOS_CARGA],
                "Fator": [
                    fat.fator_carregamento(chave, modelo)
                    for chave in ROTULOS_CARGA
                ],
                "Selecionado": [
                    "Sim" if chave == tipo_carga else "" for chave in ROTULOS_CARGA
                ],
            }
        )
        st.dataframe(
            tabela_carga,
            hide_index=True,
            column_config={
                "Fator": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        st.caption(
            "Norton: PDF p. 356, Eq. 6.7a. "
            "Shigley: PDF p. 302, Eq. 6-26."
        )

with st.container(border=True):
    st.subheader("3. Fator de tamanho")
    tamanho_controle, tamanho_grafico = st.columns([0.95, 1.05])
    diametro_maximo = 10_000.0 if modelo == "norton" else 254.0
    diametro_minimo = 0.1 if modelo == "norton" or tipo_carga == "axial" else 2.79

    with tamanho_controle:
        modo_diametro = st.segmented_control(
            "Como obter o diametro equivalente?",
            ["Informar d equivalente", "Calcular pela geometria"],
            default="Informar d equivalente", required=True, width="stretch",
            key=f"modo_diametro_{modelo}_{tipo_carga}",
            persist_state="session",
        )
        if modo_diametro == "Informar d equivalente":
            diametro_mm = st.number_input(
                "Diametro equivalente da secao (mm)", min_value=diametro_minimo,
                max_value=diametro_maximo, value=max(diametro_minimo, 20.0), step=1.0,
                key=f"diametro_{modelo}_{tipo_carga}",
                help="Para secoes nao circulares, informe o diametro equivalente obtido pela area submetida a pelo menos 95% da tensao maxima.",
                persist_state="session",
            )
            st.caption("Use esta opcao quando A0,95sigma ja tiver sido determinada por outro metodo.")
        else:
            st.markdown("**Calculadora de diametro equivalente (A0,95sigma)**")
            geometria = st.selectbox("Geometria e condicao de flexao", ["Cilindro macico rotativo", "Circulo nao rotativo", "Retangulo", "Perfil I", "Perfil canal", "Area A0,95sigma manual"], key="geometria_diametro_equivalente", persist_state="session")
            rotulo_svg = {"Cilindro macico rotativo": "Circulo rotativo", "Circulo nao rotativo": "Circulo nao rotativo", "Retangulo": "Retangulo", "Perfil I": "Perfil I", "Perfil canal": "Perfil canal", "Area A0,95sigma manual": "Area manual"}[geometria]
            entrada_geometria, desenho_geometria = st.columns(2)
            with entrada_geometria:
                try:
                    if geometria == "Cilindro macico rotativo":
                        d_fisico = st.number_input("d (mm)", min_value=0.1, value=20.0, step=1.0, key="de_circulo_rotativo", persist_state="session")
                        area_95 = size.area_95_circulo_rotativo(d_fisico)
                        st.latex(r"A_{0,95\sigma}=0,0766d^2 \quad\Rightarrow\quad d_e=d")
                    elif geometria == "Circulo nao rotativo":
                        d_fisico = st.number_input("d (mm)", min_value=0.1, value=60.0, step=1.0, key="de_circulo_nao_rotativo", persist_state="session")
                        area_95 = size.area_95_circulo_nao_rotativo(d_fisico)
                        st.latex(r"A_{0,95\sigma}=0,01046d^2 \quad\Rightarrow\quad d_e=0,370d")
                    elif geometria == "Retangulo":
                        h_mm = st.number_input("h (mm)", min_value=0.1, value=60.0, step=1.0, key="de_retangulo_h", persist_state="session")
                        b_mm = st.number_input("b (mm)", min_value=0.1, value=40.0, step=1.0, key="de_retangulo_b", persist_state="session")
                        area_95 = size.area_95_retangulo(h_mm, b_mm)
                        st.latex(r"A_{0,95\sigma}=0,05hb \quad\Rightarrow\quad d_e=0,808\sqrt{hb}")
                    elif geometria == "Perfil I":
                        a_mm = st.number_input("a (mm)", min_value=0.1, value=100.0, step=1.0, key="de_i_a", persist_state="session")
                        b_mm = st.number_input("b (mm)", min_value=0.1, value=200.0, step=1.0, key="de_i_b", persist_state="session")
                        tf_mm = st.number_input("tf (mm)", min_value=0.1, value=10.0, step=0.5, key="de_i_tf", persist_state="session")
                        eixo = st.segmented_control("Eixo de flexao", ["eixo 1-1", "eixo 2-2"], default="eixo 1-1", required=True, width="stretch", key="de_i_eixo", persist_state="session")
                        area_95 = size.area_95_perfil_i(a_mm, b_mm, tf_mm, eixo)
                        st.latex(r"A_{0,95\sigma}=0,10at_f\ (eixo\ 1\text{-}1)\quad;\quad A_{0,95\sigma}=0,05ba\ (eixo\ 2\text{-}2)")
                        st.caption("Validade desta aproximacao: tf > 0,025a.")
                    elif geometria == "Perfil canal":
                        a_mm = st.number_input("a (mm)", min_value=0.1, value=100.0, step=1.0, key="de_canal_a", persist_state="session")
                        b_mm = st.number_input("b (mm)", min_value=0.1, value=200.0, step=1.0, key="de_canal_b", persist_state="session")
                        tf_mm = st.number_input("tf (mm)", min_value=0.1, value=10.0, step=0.5, key="de_canal_tf", persist_state="session")
                        x_mm = st.number_input("x (mm)", min_value=0.0, max_value=b_mm, value=min(70.0, b_mm), step=1.0, key="de_canal_x", persist_state="session")
                        eixo = st.segmented_control("Eixo de flexao", ["eixo 1-1", "eixo 2-2"], default="eixo 1-1", required=True, width="stretch", key="de_canal_eixo", persist_state="session")
                        area_95 = size.area_95_perfil_canal(a_mm, b_mm, tf_mm, x_mm, eixo)
                        st.latex(r"A_{0,95\sigma}=0,05ab\ (eixo\ 1\text{-}1)\quad;\quad A_{0,95\sigma}=0,052xa+0,10t_f(b-x)\ (eixo\ 2\text{-}2)")
                    else:
                        area_95 = st.number_input("A0,95sigma (mm2)", min_value=0.001, value=100.0, step=1.0, key="de_area_manual", persist_state="session")
                        st.latex(r"d_e=\sqrt{\frac{A_{0,95\sigma}}{0,0766}}")
                    diametro_mm = size.diametro_equivalente_por_area_95(area_95)
                except ValueError as erro:
                    st.error(str(erro))
                    st.stop()
            with desenho_geometria:
                st.image(size.desenho_svg(rotulo_svg), width="stretch")
                st.caption("Esquema para orientar as dimensoes da formula selecionada.")
            st.metric("A0,95sigma", f"{area_95:.2f} mm2", border=True)
            st.metric("Diametro equivalente calculado", f"{diametro_mm:.2f} mm", border=True)
            st.latex(r"d_e=\sqrt{\frac{A_{0,95\sigma}}{0,0766}}")

        try:
            Ctamanho = fat.fator_tamanho(diametro_mm, tipo_carga, modelo)
        except ValueError as erro:
            st.error(str(erro))
            st.stop()
        st.metric("Ctamanho", f"{Ctamanho:.3f}", border=True)
        if tipo_carga == "axial":
            st.latex(r"C_{tamanho}=1\quad\mathrm{para\ carga\ axial}")
            st.code("Secao solicitada axialmente -> Ctamanho = 1,000")
        elif modelo == "norton":
            st.latex(r"C_{tamanho}=\begin{cases}1, & d\leq 8\ \mathrm{mm}\\1{,}189\,d^{-0{,}097}, & 8<d\leq250\ \mathrm{mm}\\0{,}6, & d>250\ \mathrm{mm}\end{cases}")
            if diametro_mm <= 8:
                st.code(f"d = {diametro_mm:.2f} mm -> Ctamanho = 1,000")
            elif diametro_mm <= 250:
                st.code(f"Ctamanho = 1,189 x {diametro_mm:.2f}^(-0,097) = {Ctamanho:.3f}")
            else:
                st.code(f"d = {diametro_mm:.2f} mm > 250 mm -> Ctamanho = 0,600")
        else:
            st.latex(r"k_b=\begin{cases}1{,}24\,d^{-0{,}107}, & 2{,}79\leq d\leq51\ \mathrm{mm}\\1{,}51\,d^{-0{,}157}, & 51<d\leq254\ \mathrm{mm}\end{cases}")
            st.code(f"Shigley: d = {diametro_mm:.2f} mm -> kb = {Ctamanho:.3f}")
        st.caption("Norton: PDF p. 357, Eq. 6.7b. Shigley: PDF pp. 300 e 307-308, Eqs. 6-20, 6-21 e Tabela 6-3.")
        if material != "aco":
            st.warning("A correlacao de tamanho foi levantada principalmente para aco. Para materiais nao ferrosos, use validacao experimental ou um fator documentado.")

    with tamanho_grafico:
        limite_grafico = max(250.0, diametro_mm * 1.15) if modelo == "norton" else 254.0
        inicio_grafico = 0.1 if modelo == "norton" or tipo_carga == "axial" else 2.79
        diametros_fator = np.geomspace(inicio_grafico, limite_grafico, 180)
        df_tamanho = pd.DataFrame({"Diametro (mm)": diametros_fator, "Ctamanho": [fat.fator_tamanho(float(diametro), tipo_carga, modelo) for diametro in diametros_fator]})
        curva_tamanho = alt.Chart(df_tamanho).mark_line(strokeWidth=3).encode(x=alt.X("Diametro (mm):Q", scale=alt.Scale(type="log"), title="Diametro equivalente (mm, escala log)"), y=alt.Y("Ctamanho:Q", scale=alt.Scale(zero=False), title="Fator de tamanho"), tooltip=[alt.Tooltip("Diametro (mm):Q", format=".2f"), alt.Tooltip("Ctamanho:Q", format=".3f")])
        ponto_tamanho = alt.Chart(pd.DataFrame({"Diametro (mm)": [diametro_mm], "Ctamanho": [Ctamanho]})).mark_point(size=140, filled=True, color="#e05a47").encode(x="Diametro (mm):Q", y="Ctamanho:Q", tooltip=[alt.Tooltip("Diametro (mm):Q", format=".2f"), alt.Tooltip("Ctamanho:Q", format=".3f")])
        transicoes = [8.0, 250.0] if modelo == "norton" else [2.79, 51.0]
        linhas_transicao = alt.Chart(pd.DataFrame({"Transicao": transicoes})).mark_rule(strokeDash=[5, 5], color="#777").encode(x="Transicao:Q")
        st.altair_chart((curva_tamanho + ponto_tamanho + linhas_transicao).properties(height=315), width="stretch")
        st.caption("As linhas tracejadas indicam as mudancas de trecho da correlacao. Para Norton, d > 250 mm usa 0,600.")
with st.container(border=True):
    st.subheader("4. Fator de acabamento superficial")
    superficie_controle, superficie_grafico = st.columns([0.8, 1.2])
    with superficie_controle:
        acabamento = st.selectbox(
            "Acabamento superficial de referência",
            list(ROTULOS_ACABAMENTO),
            format_func=ROTULOS_ACABAMENTO.get,
            key="fadiga_acabamento",
            persist_state="session",
        )
        modo_superficie = st.segmented_control(
            "Como definir Csuperf?",
            ["Calculado pela curva", "Valor manual"],
            default="Calculado pela curva",
            required=True,
            width="stretch",
            key="fadiga_modo_superficie",
            persist_state="session",
        )
        Csuperf_calculado = fat.fator_superficie(
            Sut, acabamento, material=material
        )
        if material == "ferro":
            st.info(
                "Para ferro fundido, Norton recomenda Csuperf = 1 porque as "
                "descontinuidades internas dominam o efeito da rugosidade."
            )
        elif material != "aco":
            st.warning(
                "As curvas de acabamento foram obtidas principalmente para aços. "
                "Para aplicações críticas em metais não ferrosos, prefira ensaio "
                "ou valor manual documentado."
            )
        if modo_superficie == "Valor manual":
            Csuperf = st.slider(
                "Valor manual de Csuperf",
                min_value=0.01,
                max_value=1.0,
                value=float(round(Csuperf_calculado, 2)),
                step=0.01,
                help=(
                    "O valor manual substitui a correlação. Use-o quando houver "
                    "um gráfico, ensaio ou norma diferente da base implementada."
                ),
                key="fadiga_csuperf_manual",
                persist_state="session",
            )
            st.warning(
                "Modo manual ativo: o valor informado será usado no produto de Marin."
            )
        else:
            Csuperf = Csuperf_calculado

        A, expoente_b = fat.COEFICIENTES_SUPERFICIE[acabamento]
        st.metric("Csuperf usado", f"{Csuperf:.3f}", border=True)
        st.latex(r"C_{superf}=\min\left(A\,S_{ut}^{\,b},\,1\right)")
        if material == "ferro":
            st.code("Ferro fundido → Csuperf = 1,000 (recomendação de Norton)")
        else:
            st.code(
                f"Csuperf = min({A:g} × {Sut:.1f}^({expoente_b:.3f}), 1) "
                f"= {Csuperf_calculado:.3f}"
            )
        st.caption(
            "Coeficientes coincidentes nas duas referências: "
            "Norton, PDF p. 359, Tabela 6-3; "
            "Shigley, PDF p. 300, Tabela 6-2."
        )
        if modo_superficie == "Valor manual":
            st.caption(
                f"Curva selecionada: {Csuperf_calculado:.3f}. "
                f"Valor manual aplicado: {Csuperf:.3f}."
            )

    with superficie_grafico:
        sut_min = min(300.0, max(50.0, Sut * 0.75))
        sut_max = max(1800.0, Sut * 1.2)
        sut_curvas = np.linspace(sut_min, sut_max, 220)
        linhas_superficie = []
        for acabamento_chave, acabamento_rotulo in ROTULOS_ACABAMENTO.items():
            for sut_curva in sut_curvas:
                linhas_superficie.append(
                    {
                        "Sut (MPa)": float(sut_curva),
                        "Sut (kpsi)": float(sut_curva / 6.894757),
                        "Csuperf": fat.fator_superficie(
                            float(sut_curva), acabamento_chave
                        ),
                        "Acabamento": acabamento_rotulo,
                    }
                )
        df_superficie = pd.DataFrame(linhas_superficie)
        acabamento_selecionado = ROTULOS_ACABAMENTO[acabamento]
        curvas_superficie = alt.Chart(df_superficie).mark_line().encode(
            x=alt.X(
                "Sut (MPa):Q",
                title="Resistência à tração, Sut (MPa)",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                "Csuperf:Q",
                title="Fator de superfície",
                scale=alt.Scale(domain=[0, 1.02]),
            ),
            color=alt.Color("Acabamento:N", title="Acabamento"),
            strokeWidth=alt.condition(
                alt.datum.Acabamento == acabamento_selecionado,
                alt.value(4),
                alt.value(1.5),
            ),
            opacity=alt.condition(
                alt.datum.Acabamento == acabamento_selecionado,
                alt.value(1.0),
                alt.value(0.55),
            ),
            tooltip=[
                "Acabamento:N",
                alt.Tooltip("Sut (MPa):Q", format=".0f"),
                alt.Tooltip("Sut (kpsi):Q", format=".1f"),
                alt.Tooltip("Csuperf:Q", format=".3f"),
            ],
        )
        ponto_superficie = alt.Chart(
            pd.DataFrame(
                {
                    "Sut (MPa)": [Sut],
                    "Csuperf": [Csuperf],
                    "Origem": [
                        "Manual"
                        if modo_superficie == "Valor manual"
                        else "Curva calculada"
                    ],
                }
            )
        ).mark_point(size=170, filled=True, color="#111").encode(
            x="Sut (MPa):Q",
            y="Csuperf:Q",
            tooltip=[
                "Origem:N",
                alt.Tooltip("Sut (MPa):Q", format=".1f"),
                alt.Tooltip("Csuperf:Q", format=".3f"),
            ],
        )
        camadas_superficie = [curvas_superficie, ponto_superficie]
        if modo_superficie == "Valor manual":
            regra_manual = alt.Chart(
                pd.DataFrame({"Manual": [Csuperf]})
            ).mark_rule(color="#111", strokeDash=[6, 4]).encode(y="Manual:Q")
            camadas_superficie.append(regra_manual)
        st.altair_chart(
            alt.layer(*camadas_superficie).properties(height=360),
            width="stretch",
        )
        st.caption(
            "As curvas são geradas pelas equações A·Sutᵇ do programa. "
            "O ponto preto é o valor efetivamente usado no cálculo."
        )

with st.container(border=True):
    st.subheader("5. Fator de temperatura")
    temperatura_controle, temperatura_grafico = st.columns([0.8, 1.2])
    with temperatura_controle:
        unidade_temperatura = st.segmented_control(
            "Unidade da temperatura informada",
            ["°F", "°C"],
            default="°F" if modelo == "norton" else "°C",
            required=True,
            width="stretch",
            key=f"unidade_temperatura_{modelo}",
            help=(
                "Norton publica a Equação 6.7f em °F; Shigley usa °C. "
                "O programa converte a entrada antes do cálculo."
            ),
            persist_state="session",
        )
        temp_min, temp_max = fat.limites_temperatura_entrada(
            modelo, unidade_temperatura
        )
        temperatura_padrao = 68.0 if unidade_temperatura == "°F" else 20.0
        temperatura_entrada = st.number_input(
            f"Temperatura estimada do corpo da peça ({unidade_temperatura})",
            min_value=temp_min,
            max_value=temp_max,
            value=temperatura_padrao,
            step=5.0,
            key=f"temperatura_{modelo}_{unidade_temperatura}",
            help=(
                "Informe a temperatura da peça na região crítica. Não use "
                "automaticamente a temperatura dos gases, do fluido ou do ambiente."
            ),
            persist_state="session",
        )
        temperatura = fat.temperatura_para_celsius(
            temperatura_entrada, unidade_temperatura
        )
        temperatura_f = fat.celsius_para_fahrenheit(temperatura)
        Ctemp = fat.fator_temperatura_na_unidade(
            temperatura_entrada, unidade_temperatura, modelo
        )
        with st.container(horizontal=True):
            st.metric("Ctemp", f"{Ctemp:.3f}", border=True)
            st.metric(
                "Temperatura convertida",
                f"{temperatura:.1f} °C / {temperatura_f:.1f} °F",
                border=True,
            )

        if modelo == "norton":
            st.info(
                "A equação de Norton é calculada em °F. Exemplo do livro: "
                "500 °F = 260 °C e resulta em Ctemp = 0,710."
            )

        if modelo == "norton":
            st.latex(r"T_F=1{,}8T_C+32")
            st.latex(
                r"C_{temp}="
                r"\begin{cases}"
                r"1, & T_F\leq450^\circ F\\"
                r"1-0{,}0058\,(T_F-450), & 450<T_F\leq550^\circ F"
                r"\end{cases}"
            )
            if temperatura_f <= 450:
                st.code(f"T = {temperatura:.1f} °C = {temperatura_f:.1f} °F ≤ 450 °F → Ctemp = 1,000")
            else:
                st.code(
                    f"Ctemp = 1 - 0,0058 × ({temperatura_f:.1f} - 450) "
                    f"= {Ctemp:.3f}"
                )
            st.caption("Norton: PDF p. 361, Eq. 6.7f; a equação usa °F e é válida até 550 °F (287,8 °C), para aços.")
        else:
            st.latex(
                r"k_d=0{,}9877+0{,}6507\!\times\!10^{-3}T"
                r"-0{,}3414\!\times\!10^{-5}T^2"
                r"+0{,}5621\!\times\!10^{-8}T^3"
                r"-6{,}246\!\times\!10^{-12}T^4"
            )
            if temperatura < 37:
                st.code(
                    f"Shigley: interpolação da Tabela 6-4 em "
                    f"T = {temperatura:.1f} °C → kd = {Ctemp:.3f}"
                )
            else:
                st.code(
                    f"Shigley: polinômio em T = {temperatura:.1f} °C "
                    f"→ kd = {Ctemp:.3f}"
                )
            st.caption(
                "Shigley: PDF pp. 303–304, Tabela 6-4 e Eq. 6-27. "
                "A equação polinomial é indicada para 37–540 °C."
            )

        if modelo == "norton" and temperatura < 20:
            st.warning(
                "Ctemp = 1 nesta correlação, mas isso não verifica a transição "
                "dúctil-frágil nem a tenacidade à fratura em baixa temperatura."
            )
        if modelo == "norton" and temperatura > fat.NORTON_TEMPERATURA_INICIO_C:
            st.warning(
                "A redução de Norton começa em 450 °F (232,2 °C). A correlação "
                "não substitui propriedades do material medidas na temperatura da peça."
            )
        if modelo == "shigley" and temperatura > 450:
            st.warning(
                "Em temperatura elevada, confirme também Sy na temperatura de "
                "operação e avalie fluência ou interação fadiga-fluência."
            )
        if material != "aco":
            st.warning(
                "A correlação de temperatura selecionada é baseada em dados de "
                "aços. Não a trate como validada para este material."
            )

    with temperatura_grafico:
        if modelo == "norton":
            temperaturas_c_curva = np.linspace(
                min(-50.0, temperatura),
                fat.NORTON_TEMPERATURA_MAX_C,
                240,
            )
            transicao_c = [fat.NORTON_TEMPERATURA_INICIO_C]
        else:
            temperaturas_c_curva = np.linspace(20.0, 540.0, 240)
            transicao_c = [37.0]

        temperaturas_f_curva = [
            fat.celsius_para_fahrenheit(float(temp_c))
            for temp_c in temperaturas_c_curva
        ]
        if unidade_temperatura == "°F":
            temperaturas_exibidas = temperaturas_f_curva
            transicoes_exibidas = [
                fat.celsius_para_fahrenheit(temp_c) for temp_c in transicao_c
            ]
        else:
            temperaturas_exibidas = temperaturas_c_curva
            transicoes_exibidas = transicao_c

        df_temperatura = pd.DataFrame(
            {
                "Temperatura informada": temperaturas_exibidas,
                "Temperatura (°C)": temperaturas_c_curva,
                "Temperatura (°F)": temperaturas_f_curva,
                "Ctemp": [
                    fat.fator_temperatura(float(temp_c), modelo)
                    for temp_c in temperaturas_c_curva
                ],
            }
        )
        curva_temperatura = alt.Chart(df_temperatura).mark_line(
            strokeWidth=3
        ).encode(
            x=alt.X(
                "Temperatura informada:Q",
                title=f"Temperatura ({unidade_temperatura})",
            ),
            y=alt.Y(
                "Ctemp:Q",
                scale=alt.Scale(zero=False),
                title="Fator de temperatura",
            ),
            tooltip=[
                alt.Tooltip("Temperatura (°C):Q", format=".1f"),
                alt.Tooltip("Temperatura (°F):Q", format=".1f"),
                alt.Tooltip("Ctemp:Q", format=".3f"),
            ],
        )
        ponto_temperatura = alt.Chart(
            pd.DataFrame(
                {
                    "Temperatura informada": [temperatura_entrada],
                    "Temperatura (°C)": [temperatura],
                    "Temperatura (°F)": [temperatura_f],
                    "Ctemp": [Ctemp],
                }
            )
        ).mark_point(size=150, filled=True, color="#e05a47").encode(
            x="Temperatura informada:Q",
            y="Ctemp:Q",
            tooltip=[
                alt.Tooltip("Temperatura (°C):Q", format=".1f"),
                alt.Tooltip("Temperatura (°F):Q", format=".1f"),
                alt.Tooltip("Ctemp:Q", format=".3f"),
            ],
        )
        limite_temperatura = alt.Chart(
            pd.DataFrame({"Transição": transicoes_exibidas})
        ).mark_rule(strokeDash=[5, 5], color="#777").encode(x="Transição:Q")
        st.altair_chart(
            (
                curva_temperatura
                + ponto_temperatura
                + limite_temperatura
            ).properties(height=315),
            width="stretch",
        )
        st.caption(
            "A linha tracejada indica a transição principal da correlação ativa. "
            "Passe o cursor sobre a curva para conferir °C, °F e Ctemp."
        )

with st.container(border=True):
    st.subheader("6. Fator de confiabilidade")
    confiabilidade_controle, confiabilidade_tabela = st.columns([0.8, 1.2])
    with confiabilidade_controle:
        confiabilidade = st.selectbox(
            "Confiabilidade desejada (%)",
            list(fat.FATORES_CONFIABILIDADE),
            index=2,
            key="fadiga_confiabilidade",
            persist_state="session",
        )
        Cconf = fat.fator_confiabilidade(confiabilidade)
        st.metric("Cconf", f"{Cconf:.3f}", border=True)
        st.caption(
            "Quanto maior a confiabilidade estatistica exigida, menor o fator "
            "e mais conservadora a resistencia a fadiga."
        )
    with confiabilidade_tabela:
        df_confiabilidade = pd.DataFrame(
            {
                "Confiabilidade": [
                    f"{valor:g}%" for valor in fat.FATORES_CONFIABILIDADE
                ],
                "Cconf": list(fat.FATORES_CONFIABILIDADE.values()),
            }
        )
        st.dataframe(
            df_confiabilidade,
            hide_index=True,
            column_config={
                "Cconf": st.column_config.NumberColumn(format="%.3f"),
            },
            width="stretch",
        )
        st.caption(
            "As duas referencias apresentam a mesma tabela: "
            "Norton, PDF p. 361, Tabela 6-4; "
            "Shigley, PDF p. 305, Tabela 6-5."
        )
with st.container(border=True):
    st.subheader("7. Resultado da equação de Marin")
    fatores = {
        "Carregamento": Ccarreg,
        "Tamanho": Ctamanho,
        "Superfície": Csuperf,
        "Temperatura": Ctemp,
        "Confiabilidade": Cconf,
    }
    Se = fat.calcular_se(Se_linha, *fatores.values())
    with st.container(horizontal=True):
        st.metric(
            "Se' teórico" if vida_infinita else "Sf' em 5×10⁸ ciclos",
            f"{Se_linha:.1f} MPa",
            border=True,
        )
        st.metric(
            "Produto dos fatores",
            f"{math.prod(fatores.values()):.3f}",
            border=True,
        )
        st.metric(
            "Se corrigido" if vida_infinita else "Sf corrigido em 5×10⁸",
            f"{Se:.1f} MPa",
            delta=f"{(Se / Se_linha - 1):.1%}",
            delta_color="inverse",
            border=True,
        )

    substituicao = " × ".join(f"{valor:.3f}" for valor in fatores.values())
    st.code(
        f"Se = ({substituicao}) × {Se_linha:.1f} MPa = {Se:.1f} MPa"
    )
    st.caption(f"Resultado calculado integralmente segundo {fat.FONTES_MARIN[modelo]}.")

    acumulado = 1.0
    linhas_impacto = [{"Etapa": "Teórico", "Multiplicador acumulado": acumulado}]
    for nome, valor in fatores.items():
        acumulado *= valor
        linhas_impacto.append(
            {"Etapa": nome, "Multiplicador acumulado": acumulado}
        )
    df_impacto = pd.DataFrame(linhas_impacto)
    grafico_impacto = (
        alt.Chart(df_impacto)
        .mark_line(point=alt.OverlayMarkDef(size=85))
        .encode(
            x=alt.X("Etapa:N", sort=None, title=None),
            y=alt.Y(
                "Multiplicador acumulado:Q",
                scale=alt.Scale(domain=[0, 1.05]),
                axis=alt.Axis(format=".0%"),
            ),
            tooltip=[
                "Etapa:N",
                alt.Tooltip("Multiplicador acumulado:Q", format=".1%"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(grafico_impacto, width="stretch")

with st.container(border=True):
    st.subheader("8. Concentração e sensibilidade ao entalhe")
    st.caption(
        "Escolha se a tensão alternada é nominal sem entalhe, corrigida "
        "diretamente por Kt ou corrigida pelo fator de fadiga Kf com a "
        "sensibilidade q."
    )
    modo_entalhe = st.segmented_control(
        "Tratamento do entalhe",
        ["Sem entalhe", "Usar Kt diretamente", "Usar Kf com q"],
        default="Sem entalhe",
        required=True,
        width="stretch",
        key="modo_entalhe",
        help=(
            "Kt considera a concentração elástica teórica. Kf reduz esse "
            "efeito conforme a sensibilidade do material ao entalhe."
        ),
        persist_state="session",
    )

    entrada_entalhe, explicacao_entalhe = st.columns([0.85, 1.15])
    with entrada_entalhe:
        tensao_alternada_nominal = st.number_input(
            "Tensão alternada nominal, σa,nom (MPa)",
            min_value=0.0,
            step=10.0,
            key="fadiga_sigma_alternada_nominal",
            help="Amplitude calculada na seção nominal da peça, antes do entalhe.",
            persist_state="session",
        )
        Kt = st.number_input(
            "Fator teórico de concentração, Kt",
            min_value=1.0,
            value=1.50,
            step=0.05,
            disabled=modo_entalhe == "Sem entalhe",
            help="Obtido da geometria do entalhe e do tipo de carregamento.",
            key="fadiga_kt",
            persist_state="session",
        )
        q = st.slider(
            "Índice de sensibilidade ao entalhe, q",
            min_value=0.0,
            max_value=1.0,
            value=0.80,
            step=0.01,
            disabled=modo_entalhe != "Usar Kf com q",
            help="q = 0: material insensível; q = 1: totalmente sensível.",
            key="fadiga_q",
            persist_state="session",
        )

        if modo_entalhe == "Sem entalhe":
            fator_entalhe = 1.0
            nome_fator_entalhe = "K = 1"
        elif modo_entalhe == "Usar Kt diretamente":
            fator_entalhe = Kt
            nome_fator_entalhe = "Kt"
        else:
            fator_entalhe = fat.fator_concentracao_fadiga(Kt, q)
            nome_fator_entalhe = "Kf"

        tensao_alternada = fat.tensao_com_concentracao(
            tensao_alternada_nominal, fator_entalhe
        )
        with st.container(horizontal=True):
            st.metric(
                f"Fator aplicado ({nome_fator_entalhe})",
                f"{fator_entalhe:.3f}",
                border=True,
            )
            st.metric(
                "σa efetiva",
                f"{tensao_alternada:.1f} MPa",
                border=True,
            )

        if modo_entalhe == "Sem entalhe":
            st.code(f"σa = σa,nom = {tensao_alternada_nominal:.1f} MPa")
        elif modo_entalhe == "Usar Kt diretamente":
            st.code(
                f"σa = Kt·σa,nom = {Kt:.3f} × "
                f"{tensao_alternada_nominal:.1f} = {tensao_alternada:.1f} MPa"
            )
        else:
            st.code(
                f"Kf = 1 + q(Kt − 1) = 1 + {q:.2f}({Kt:.3f} − 1) "
                f"= {fator_entalhe:.3f}\n"
                f"σa = Kf·σa,nom = {fator_entalhe:.3f} × "
                f"{tensao_alternada_nominal:.1f} = {tensao_alternada:.1f} MPa"
            )

    with explicacao_entalhe:
        st.markdown("**Como o índice q altera Kf**")
        st.latex(r"K_f=1+q\,(K_t-1)")
        st.markdown(
            "- **q = 0:** o material não sente o entalhe em fadiga, então Kf = 1.\n"
            "- **0 < q < 1:** resposta parcial, com 1 < Kf < Kt.\n"
            "- **q = 1:** sensibilidade total, então Kf = Kt."
        )
        valores_q = np.linspace(0.0, 1.0, 101)
        df_sensibilidade = pd.DataFrame(
            {
                "Sensibilidade q": valores_q,
                "Fator de fadiga Kf": 1 + valores_q * (Kt - 1),
            }
        )
        curva_sensibilidade = (
            alt.Chart(df_sensibilidade)
            .mark_line(strokeWidth=3)
            .encode(
                x=alt.X(
                    "Sensibilidade q:Q",
                    scale=alt.Scale(domain=[0, 1]),
                    title="Índice de sensibilidade ao entalhe, q",
                ),
                y=alt.Y(
                    "Fator de fadiga Kf:Q",
                    scale=alt.Scale(domain=[1, max(1.05, Kt * 1.05)]),
                    title="Fator de concentração em fadiga, Kf",
                ),
                tooltip=[
                    alt.Tooltip("Sensibilidade q:Q", format=".2f"),
                    alt.Tooltip("Fator de fadiga Kf:Q", format=".3f"),
                ],
            )
        )
        q_destacado = q if modo_entalhe == "Usar Kf com q" else (
            1.0 if modo_entalhe == "Usar Kt diretamente" else 0.0
        )
        ponto_sensibilidade = (
            alt.Chart(
                pd.DataFrame(
                    {
                        "Sensibilidade q": [q_destacado],
                        "Fator de fadiga Kf": [1 + q_destacado * (Kt - 1)],
                        "Modo": [modo_entalhe],
                    }
                )
            )
            .mark_point(size=180, filled=True, color="#d62728")
            .encode(
                x="Sensibilidade q:Q",
                y="Fator de fadiga Kf:Q",
                tooltip=[
                    "Modo:N",
                    alt.Tooltip("Sensibilidade q:Q", format=".2f"),
                    alt.Tooltip("Fator de fadiga Kf:Q", format=".3f"),
                ],
            )
        )
        st.altair_chart(
            (curva_sensibilidade + ponto_sensibilidade).properties(height=330),
            width="stretch",
        )
        st.caption(
            "O ponto vermelho representa o modo aplicado. A correção atua "
            "sobre a componente alternada; a tensão média é tratada "
            "separadamente na seção seguinte."
        )

with st.container(border=True):
    st.subheader("9. Segurança por Goodman e Soderberg")
    st.caption(
        "Carregamento proporcional com tensão média de tração. Para tensão "
        "média compressiva, adote σm = 0 neste modelo conservador. A tensão "
        "alternada usada abaixo já inclui o tratamento de entalhe escolhido."
    )
    entrada_tensoes, resultados_criterios = st.columns([0.75, 1.25])
    with entrada_tensoes:
        st.metric(
            "Tensão alternada efetiva, σa",
            f"{tensao_alternada:.1f} MPa",
            delta=(
                None
                if fator_entalhe == 1
                else f"{fator_entalhe:.3f} × tensão nominal"
            ),
            border=True,
        )
        tensao_media = st.number_input(
            "Tensão média local/equivalente de tração, σm (MPa)",
            min_value=0.0,
            step=10.0,
            key="fadiga_sigma_media",
            help=(
                "Informe a tensão média já avaliada no ponto crítico. Ela não "
                "é multiplicada automaticamente por Kf porque o tratamento "
                "depende do escoamento local e da ductilidade."
            ),
            persist_state="session",
        )
        st.latex(
            r"\frac{1}{n_G}=\frac{\sigma_a}{S_e}+\frac{\sigma_m}{S_{ut}}"
        )
        st.latex(
            r"\frac{1}{n_S}=\frac{\sigma_a}{S_e}+\frac{\sigma_m}{S_y}"
        )

    n_goodman = fat.fator_seguranca_goodman(
        tensao_alternada, tensao_media, Se, Sut
    )
    sy_valido = 0 < Sy <= Sut
    n_soderberg = None
    n_escoamento = None
    if sy_valido:
        n_soderberg = fat.fator_seguranca_soderberg(
            tensao_alternada, tensao_media, Se, Sy
        )
        n_escoamento = fat.fator_seguranca_escoamento_flutuante(
            tensao_alternada, tensao_media, Sy
        )

    with resultados_criterios:
        with st.container(horizontal=True):
            st.metric(
                "Goodman — fadiga",
                "∞" if math.isinf(n_goodman) else f"{n_goodman:.2f}",
                border=True,
            )
            if n_soderberg is not None:
                st.metric(
                    "Soderberg",
                    "∞" if math.isinf(n_soderberg) else f"{n_soderberg:.2f}",
                    border=True,
                )
                st.metric(
                    "Escoamento — 1º ciclo",
                    "∞" if math.isinf(n_escoamento) else f"{n_escoamento:.2f}",
                    border=True,
                )

        inverso_goodman = (
            tensao_alternada / Se + tensao_media / Sut
        )
        st.code(
            f"Goodman: 1/n = {tensao_alternada:.1f}/{Se:.1f} + "
            f"{tensao_media:.1f}/{Sut:.1f} = {inverso_goodman:.4f} "
            f"→ n = {'∞' if math.isinf(n_goodman) else f'{n_goodman:.2f}'}"
        )
        if n_soderberg is not None:
            inverso_soderberg = (
                tensao_alternada / Se + tensao_media / Sy
            )
            st.code(
                f"Soderberg: 1/n = {tensao_alternada:.1f}/{Se:.1f} + "
                f"{tensao_media:.1f}/{Sy:.1f} = {inverso_soderberg:.4f} "
                f"→ n = {'∞' if math.isinf(n_soderberg) else f'{n_soderberg:.2f}'}"
            )
            menor_fator = min(n_goodman, n_soderberg, n_escoamento)
            if menor_fator < 1:
                st.error("O estado informado não é seguro: há fator de segurança < 1.")
            elif menor_fator < 1.5:
                st.warning("O menor fator de segurança está entre 1 e 1,5.")
            else:
                st.success("Os critérios calculados apresentam fator de segurança ≥ 1,5.")
        else:
            st.warning(
                "Soderberg não pode ser calculado: informe Sy maior que zero "
                "e não superior a Sut. Goodman permanece disponível."
            )
            if n_goodman < 1:
                st.error("O estado informado falha pelo critério de Goodman.")
            elif n_goodman < 1.5:
                st.warning("Goodman fornece fator de segurança entre 1 e 1,5.")
            else:
                st.success("Goodman fornece fator de segurança ≥ 1,5.")

    linhas_criterios = []
    for sigma_m_curva in np.linspace(0.0, Sut, 180):
        linhas_criterios.append(
            {
                "Tensão média (MPa)": sigma_m_curva,
                "Tensão alternada admissível (MPa)": max(
                    0.0, Se * (1 - sigma_m_curva / Sut)
                ),
                "Critério": "Goodman modificado",
            }
        )
    if sy_valido:
        for sigma_m_curva in np.linspace(0.0, Sy, 160):
            linhas_criterios.append(
                {
                    "Tensão média (MPa)": sigma_m_curva,
                    "Tensão alternada admissível (MPa)": max(
                        0.0, Se * (1 - sigma_m_curva / Sy)
                    ),
                    "Critério": "Soderberg",
                }
            )

    df_criterios = pd.DataFrame(linhas_criterios)
    curvas_criterios = alt.Chart(df_criterios).mark_line(strokeWidth=3).encode(
        x=alt.X(
            "Tensão média (MPa):Q",
            title="Tensão média de tração, σm (MPa)",
        ),
        y=alt.Y(
            "Tensão alternada admissível (MPa):Q",
            title="Tensão alternada, σa (MPa)",
        ),
        color=alt.Color("Critério:N", title=None),
        tooltip=[
            "Critério:N",
            alt.Tooltip("Tensão média (MPa):Q", format=".1f"),
            alt.Tooltip("Tensão alternada admissível (MPa):Q", format=".1f"),
        ],
    )
    ponto_operacao = alt.Chart(
        pd.DataFrame(
            {
                "Tensão média (MPa)": [tensao_media],
                "Tensão alternada (MPa)": [tensao_alternada],
                "Ponto": ["Operação"],
            }
        )
    ).mark_point(size=180, filled=True, color="#111").encode(
        x="Tensão média (MPa):Q",
        y="Tensão alternada (MPa):Q",
        tooltip=[
            "Ponto:N",
            alt.Tooltip("Tensão média (MPa):Q", format=".1f"),
            alt.Tooltip("Tensão alternada (MPa):Q", format=".1f"),
        ],
    )
    st.altair_chart(
        (curvas_criterios + ponto_operacao).properties(height=390),
        width="stretch",
    )
    st.caption(
        "Região segura: abaixo das linhas. Norton: PDF pp. 387–390, "
        "Eqs. 6.15 e 6.16. Shigley: PDF pp. 318–319, Eqs. 6-44 e 6-45."
    )

with st.container(border=True):
    st.subheader("10. Curva S–N e estimativa de vida")
    N1 = 1.0e3
    N2 = 1.0e6 if vida_infinita else 5.0e8
    Sm = fat.resistencia_em_1e3_ciclos(Sut, tipo_carga, modelo)
    tensao_equivalente_vida = fat.tensao_alternada_equivalente_goodman(
        tensao_alternada, tensao_media, Sut
    )
    ciclos_estimados = None
    resultado_vida = "Não calculada"

    with st.container(horizontal=True):
        st.metric(
            "Resistência em 10³ ciclos, Sm",
            f"{Sm:.1f} MPa",
            border=True,
        )
        st.metric(
            "Amplitude equivalente de Goodman",
            (
                "∞"
                if math.isinf(tensao_equivalente_vida)
                else f"{tensao_equivalente_vida:.1f} MPa"
            ),
            border=True,
        )

    if math.isinf(tensao_equivalente_vida):
        st.code(
            f"σa,eq = σa / (1 − σm/Sut): σm = {tensao_media:.1f} MPa "
            f"≥ Sut = {Sut:.1f} MPa → sem margem pela reta de Goodman"
        )
    else:
        st.code(
            f"σa,eq = σa / (1 − σm/Sut) = {tensao_alternada:.1f} / "
            f"(1 − {tensao_media:.1f}/{Sut:.1f}) = "
            f"{tensao_equivalente_vida:.1f} MPa"
        )

    if modelo == "norton" and tipo_carga == "axial":
        st.caption(
            "Norton, Eq. 6.9: Sm = 0,75·Sut para força normal. "
            "Nos demais casos implementados, usa-se Sm = 0,90·Sut."
        )
    else:
        st.caption(
            "Sm = 0,90·Sut em 10³ ciclos. Para Shigley, esse valor é uma "
            "aproximação do fator f; dados S–N experimentais têm preferência."
        )

    if tipo_carga == "torcao":
        st.warning(
            "A curva S–N em torção comparada diretamente com τ é aproximada. "
            "Quando possível, prefira a opção de tensão equivalente de von Mises."
        )

    if Sm <= Se:
        resultado_vida = "Curva não construída: Sm ≤ resistência corrigida"
        st.warning(
            "Não foi possível montar a curva: a resistência em 10³ ciclos "
            "não supera a resistência corrigida de alto ciclo."
        )
    else:
        a, b = fat.parametros_curva_sn(Sm, Se, N2, N1)
        ciclos_finitos = np.geomspace(N1, N2, 180)
        resistencias = [
            fat.resistencia_para_N(float(numero_ciclos), a, b)
            for numero_ciclos in ciclos_finitos
        ]
        df_sn = pd.DataFrame(
            {
                "Ciclos": ciclos_finitos,
                "Resistência (MPa)": resistencias,
                "Trecho": "Vida finita",
            }
        )
        if vida_infinita:
            df_sn = pd.concat(
                [
                    df_sn,
                    pd.DataFrame(
                        {
                            "Ciclos": np.geomspace(N2, 1.0e9, 70),
                            "Resistência (MPa)": Se,
                            "Trecho": "Limite de fadiga",
                        }
                    ),
                ],
                ignore_index=True,
            )

        curva_sn = alt.Chart(df_sn).mark_line(strokeWidth=3).encode(
            x=alt.X(
                "Ciclos:Q",
                scale=alt.Scale(type="log"),
                title="Número de ciclos, N (escala log)",
            ),
            y=alt.Y(
                "Resistência (MPa):Q",
                scale=alt.Scale(zero=False),
                title="Amplitude totalmente reversa equivalente (MPa)",
            ),
            color=alt.Color("Trecho:N", title=None),
            tooltip=[
                alt.Tooltip("Ciclos:Q", format=".3e"),
                alt.Tooltip("Resistência (MPa):Q", format=".1f"),
                "Trecho:N",
            ],
        )
        camadas_sn = [curva_sn]
        if math.isfinite(tensao_equivalente_vida) and tensao_equivalente_vida > 0:
            camadas_sn.append(
                alt.Chart(
                    pd.DataFrame(
                        {
                            "Amplitude equivalente de Goodman": [
                                tensao_equivalente_vida
                            ]
                        }
                    )
                )
                .mark_rule(color="#d62728", strokeDash=[6, 4])
                .encode(y="Amplitude equivalente de Goodman:Q")
            )
        st.altair_chart(
            alt.layer(*camadas_sn).properties(height=390), width="stretch"
        )
        st.caption(
            "A vida é estimada com a amplitude totalmente reversa equivalente "
            "de Goodman, incorporando o efeito da tensão média de tração. "
            "A curva continua sendo uma aproximação e não substitui ensaios."
        )

        if math.isinf(tensao_equivalente_vida):
            resultado_vida = "Fora do domínio: σm ≥ Sut"
            st.error(
                "A tensão média alcança ou supera Sut; a reta de Goodman não "
                "possui margem e a vida S–N não pode ser estimada."
            )
        elif tensao_equivalente_vida <= 0:
            resultado_vida = "Sem componente alternada equivalente"
            st.info(
                "A amplitude equivalente é zero; não há dano por fadiga "
                "alternada neste modelo."
            )
        elif tensao_equivalente_vida > Sm:
            resultado_vida = "Inferior a 10³ ciclos; fora do modelo"
            st.error(
                "A amplitude equivalente está acima do início da curva; "
                "a vida é inferior a 10³ ciclos e exige outro modelo."
            )
        elif tensao_equivalente_vida <= Se:
            if vida_infinita:
                resultado_vida = "Vida infinita no modelo tensão–vida"
                st.success(
                    "A amplitude equivalente está abaixo de Se: vida infinita "
                    "segundo este modelo idealizado."
                )
            else:
                resultado_vida = "Superior a 5×10⁸ ciclos; sem extrapolação"
                st.info(
                    "A vida supera 5×10⁸ ciclos; a extrapolação não é "
                    "suportada para este material."
                )
        else:
            ciclos_estimados = fat.ciclos_para_S(
                tensao_equivalente_vida, a, b
            )
            resultado_vida = f"{ciclos_estimados:,.0f} ciclos"
            st.metric("Vida estimada", resultado_vida)

if not vida_infinita:
    st.warning(
        "Alumínio e cobre não apresentam limite de fadiga verdadeiro neste "
        "modelo. O valor final é uma resistência de referência em 5×10⁸ ciclos."
    )

with st.container(border=True):
    st.subheader("11. Resumo do problema e memória de cálculo")
    st.caption(
        "Tabela consolidada das entradas, hipóteses, fatores e resultados "
        "efetivamente usados nesta análise."
    )

    origem_material = (
        escolha
        if usar_base
        else f"{ROTULOS_MATERIAL[material]} — entrada manual"
    )
    valor_kt = f"{Kt:.3f}" if modo_entalhe != "Sem entalhe" else "Não aplicado"
    valor_q = f"{q:.2f}" if modo_entalhe == "Usar Kf com q" else "Não aplicado"
    valor_soderberg = (
        "Não calculado"
        if n_soderberg is None
        else ("∞" if math.isinf(n_soderberg) else f"{n_soderberg:.3f}")
    )
    valor_escoamento = (
        "Não calculado"
        if n_escoamento is None
        else ("∞" if math.isinf(n_escoamento) else f"{n_escoamento:.3f}")
    )
    valor_goodman = "∞" if math.isinf(n_goodman) else f"{n_goodman:.3f}"
    valor_sigma_eq = (
        "∞"
        if math.isinf(tensao_equivalente_vida)
        else f"{tensao_equivalente_vida:.2f}"
    )
    produto_marin = math.prod(fatores.values())

    linhas_resumo = [
        {
            "Grupo": "Configuração",
            "Grandeza": "Referência de cálculo",
            "Símbolo": "—",
            "Valor": ROTULOS_MODELO[modelo],
            "Unidade": "—",
            "Observação": fat.FONTES_MARIN[modelo],
        },
        {
            "Grupo": "Material",
            "Grandeza": "Material / origem",
            "Símbolo": "—",
            "Valor": origem_material,
            "Unidade": "—",
            "Observação": ROTULOS_MATERIAL[material],
        },
        {
            "Grupo": "Material",
            "Grandeza": "Resistência à tração",
            "Símbolo": "Sut",
            "Valor": f"{Sut:.2f}",
            "Unidade": "MPa",
            "Observação": "Entrada usada em Goodman e nas estimativas S–N",
        },
        {
            "Grupo": "Material",
            "Grandeza": "Limite de escoamento",
            "Símbolo": "Sy",
            "Valor": f"{Sy:.2f}",
            "Unidade": "MPa",
            "Observação": "Usado em Soderberg e no escoamento de 1º ciclo",
        },
        {
            "Grupo": "Material",
            "Grandeza": "Resistência de fadiga de referência",
            "Símbolo": "Se'" if vida_infinita else "Sf'",
            "Valor": f"{Se_linha:.2f}",
            "Unidade": "MPa",
            "Observação": (
                "Limite teórico de fadiga"
                if vida_infinita
                else "Referência teórica em 5×10⁸ ciclos"
            ),
        },
        {
            "Grupo": "Condição",
            "Grandeza": "Tipo de carregamento",
            "Símbolo": "—",
            "Valor": ROTULOS_CARGA[tipo_carga],
            "Unidade": "—",
            "Observação": "Define Ccarreg e a interpretação das tensões",
        },
        {
            "Grupo": "Condição",
            "Grandeza": "Diâmetro equivalente",
            "Símbolo": "d",
            "Valor": f"{diametro_mm:.2f}",
            "Unidade": "mm",
            "Observação": "Base do fator de tamanho",
        },
        {
            "Grupo": "Condição",
            "Grandeza": "Acabamento superficial",
            "Símbolo": "—",
            "Valor": ROTULOS_ACABAMENTO[acabamento],
            "Unidade": "—",
            "Observação": modo_superficie,
        },
        {
            "Grupo": "Condição",
            "Grandeza": "Temperatura de operação",
            "Símbolo": "T",
            "Valor": f"{temperatura:.2f}",
            "Unidade": "°C",
            "Observação": (
                f"Entrada: {temperatura_entrada:.2f} {unidade_temperatura}; "
                f"equivalente a {temperatura_f:.2f} °F"
            ),
        },
        {
            "Grupo": "Condição",
            "Grandeza": "Confiabilidade",
            "Símbolo": "R",
            "Valor": f"{confiabilidade:g}",
            "Unidade": "%",
            "Observação": "Nível estatístico selecionado",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Fator de carregamento",
            "Símbolo": "Ccarreg",
            "Valor": f"{Ccarreg:.4f}",
            "Unidade": "—",
            "Observação": "Fator multiplicativo",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Fator de tamanho",
            "Símbolo": "Ctamanho",
            "Valor": f"{Ctamanho:.4f}",
            "Unidade": "—",
            "Observação": "Fator multiplicativo",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Fator de superfície",
            "Símbolo": "Csuperf",
            "Valor": f"{Csuperf:.4f}",
            "Unidade": "—",
            "Observação": modo_superficie,
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Fator de temperatura",
            "Símbolo": "Ctemp",
            "Valor": f"{Ctemp:.4f}",
            "Unidade": "—",
            "Observação": "Fator multiplicativo",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Fator de confiabilidade",
            "Símbolo": "Cconf",
            "Valor": f"{Cconf:.4f}",
            "Unidade": "—",
            "Observação": "Fator multiplicativo",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Produto dos fatores",
            "Símbolo": "Ctotal",
            "Valor": f"{produto_marin:.4f}",
            "Unidade": "—",
            "Observação": "Ccarreg·Ctamanho·Csuperf·Ctemp·Cconf",
        },
        {
            "Grupo": "Marin",
            "Grandeza": "Resistência de fadiga corrigida",
            "Símbolo": "Se" if vida_infinita else "Sf",
            "Valor": f"{Se:.2f}",
            "Unidade": "MPa",
            "Observação": (
                "Limite corrigido"
                if vida_infinita
                else "Resistência corrigida em 5×10⁸ ciclos"
            ),
        },
        {
            "Grupo": "Entalhe",
            "Grandeza": "Tratamento selecionado",
            "Símbolo": "—",
            "Valor": modo_entalhe,
            "Unidade": "—",
            "Observação": "Define o fator aplicado à tensão alternada",
        },
        {
            "Grupo": "Entalhe",
            "Grandeza": "Fator teórico",
            "Símbolo": "Kt",
            "Valor": valor_kt,
            "Unidade": "—",
            "Observação": "Obtido da geometria e do carregamento",
        },
        {
            "Grupo": "Entalhe",
            "Grandeza": "Sensibilidade ao entalhe",
            "Símbolo": "q",
            "Valor": valor_q,
            "Unidade": "—",
            "Observação": "Aplicada somente no modo Kf com q",
        },
        {
            "Grupo": "Entalhe",
            "Grandeza": "Fator aplicado",
            "Símbolo": nome_fator_entalhe,
            "Valor": f"{fator_entalhe:.4f}",
            "Unidade": "—",
            "Observação": "Multiplica a tensão alternada nominal",
        },
        {
            "Grupo": "Tensões",
            "Grandeza": "Tensão alternada nominal",
            "Símbolo": "σa,nom",
            "Valor": f"{tensao_alternada_nominal:.2f}",
            "Unidade": "MPa",
            "Observação": "Antes da concentração de tensão",
        },
        {
            "Grupo": "Tensões",
            "Grandeza": "Tensão alternada efetiva",
            "Símbolo": "σa",
            "Valor": f"{tensao_alternada:.2f}",
            "Unidade": "MPa",
            "Observação": "Após o tratamento de entalhe",
        },
        {
            "Grupo": "Tensões",
            "Grandeza": "Tensão média local/equivalente",
            "Símbolo": "σm",
            "Valor": f"{tensao_media:.2f}",
            "Unidade": "MPa",
            "Observação": "Informada no ponto crítico",
        },
        {
            "Grupo": "Tensões",
            "Grandeza": "Amplitude equivalente de Goodman",
            "Símbolo": "σa,eq",
            "Valor": valor_sigma_eq,
            "Unidade": "MPa",
            "Observação": "Usada na estimativa de vida S–N",
        },
        {
            "Grupo": "S–N",
            "Grandeza": "Resistência em 10³ ciclos",
            "Símbolo": "Sm",
            "Valor": f"{Sm:.2f}",
            "Unidade": "MPa",
            "Observação": f"Curva entre {N1:.0e} e {N2:.0e} ciclos",
        },
        {
            "Grupo": "Resultados",
            "Grandeza": "Fator de segurança Goodman",
            "Símbolo": "nG",
            "Valor": valor_goodman,
            "Unidade": "—",
            "Observação": "Fadiga com tensão média de tração",
        },
        {
            "Grupo": "Resultados",
            "Grandeza": "Fator de segurança Soderberg",
            "Símbolo": "nS",
            "Valor": valor_soderberg,
            "Unidade": "—",
            "Observação": "Disponível quando 0 < Sy ≤ Sut",
        },
        {
            "Grupo": "Resultados",
            "Grandeza": "Fator contra escoamento no 1º ciclo",
            "Símbolo": "ny",
            "Valor": valor_escoamento,
            "Unidade": "—",
            "Observação": "Sy/(σa + σm)",
        },
        {
            "Grupo": "Resultados",
            "Grandeza": "Vida estimada",
            "Símbolo": "N",
            "Valor": resultado_vida,
            "Unidade": "—",
            "Observação": "Modelo tensão–vida com correção de Goodman",
        },
    ]
    df_resumo = pd.DataFrame(linhas_resumo)
    st.dataframe(
        df_resumo,
        hide_index=True,
        width="stretch",
        height=620,
        row_height=36,
        column_config={
            "Grupo": st.column_config.TextColumn(width="small", pinned=True),
            "Grandeza": st.column_config.TextColumn(width="large"),
            "Símbolo": st.column_config.TextColumn(width="small"),
            "Valor": st.column_config.TextColumn(width="medium"),
            "Unidade": st.column_config.TextColumn(width="small"),
            "Observação": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(
        "Resumo somente leitura. Todas as grandezas internas permanecem em "
        "MPa, mm e °C; valores manuais devem ser rastreados à norma, ensaio "
        "ou gráfico usado no projeto."
    )

    st.divider()
    st.markdown("**Exportar memorial de cálculo**")
    st.caption(
        "O Word começa com um resumo executivo básico e depois apresenta a memória "
        "técnica completa. O PDF permanece disponível como versão estável para impressão."
    )

    with st.expander(
        "Identificação, revisão e aprovações do documento",
        expanded=True,
        icon=":material/badge:",
    ):
        projeto_col, cliente_col = st.columns(2)
        with projeto_col:
            nome_projeto = st.text_input(
                "Identificação do projeto",
                value="Análise de fadiga",
                key="fadiga_nome_projeto_pdf",
                persist_state="session",
            )
        with cliente_col:
            cliente_projeto = st.text_input(
                "Cliente, empresa ou setor",
                key="fadiga_cliente_memorial",
                placeholder="Organização responsável pelo equipamento",
                persist_state="session",
            )

        codigo_col, revisao_col, emissao_col = st.columns([1.4, 0.7, 1.0])
        with codigo_col:
            codigo_documento = st.text_input(
                "Código do documento",
                value="MC-FAD-001",
                key="fadiga_codigo_memorial",
                persist_state="session",
            )
        with revisao_col:
            revisao_documento = st.text_input(
                "Revisão",
                value="00",
                key="fadiga_revisao_memorial",
                persist_state="session",
            )
        with emissao_col:
            data_emissao = st.date_input(
                "Data de emissão",
                value=date.today(),
                key="fadiga_emissao_memorial",
            )

        responsavel_col, verificador_col = st.columns(2)
        with responsavel_col:
            responsavel_projeto = st.text_input(
                "Elaborado por",
                key="fadiga_responsavel_pdf",
                placeholder="Nome do projetista ou da equipe",
                persist_state="session",
            )
        with verificador_col:
            verificador_projeto = st.text_input(
                "Verificado por",
                key="fadiga_verificador_memorial",
                placeholder="Responsável pela verificação independente",
                persist_state="session",
            )

        aprovador_col, situacao_col = st.columns(2)
        with aprovador_col:
            aprovador_projeto = st.text_input(
                "Aprovado por",
                key="fadiga_aprovador_memorial",
                placeholder="Responsável pela aprovação final",
                persist_state="session",
            )
        with situacao_col:
            situacao_documento = st.selectbox(
                "Situação do documento",
                ["Preliminar", "Para verificação", "Para aprovação", "Final"],
                key="fadiga_situacao_memorial",
                persist_state="session",
            )

        with st.container(border=True):
            st.markdown("**Critérios e rastreabilidade do projeto**")
            st.caption(
                "Estes campos alimentam o resumo executivo, os critérios de aceitação "
                "e o registro de pendências do Word."
            )
            componente_col, referencia_col = st.columns(2)
            with componente_col:
                componente_analisado = st.text_input(
                    "Componente ou ponto crítico",
                    key="fadiga_componente_memorial",
                    placeholder="Ex.: eixo, seção junto ao ombro, desenho 123 - posição A",
                    persist_state="session",
                )
            with referencia_col:
                referencia_projeto = st.text_input(
                    "Norma, especificação ou desenho de referência",
                    key="fadiga_referencia_projeto_memorial",
                    placeholder="Ex.: especificação interna, desenho, norma ou requisito do cliente",
                    persist_state="session",
                )

            fator_col, vida_col = st.columns(2)
            with fator_col:
                fator_seguranca_minimo = st.number_input(
                    "Fator de segurança mínimo exigido",
                    min_value=0.01,
                    max_value=20.0,
                    value=1.50,
                    step=0.10,
                    format="%.2f",
                    key="fadiga_meta_seguranca_memorial",
                    help="Meta usada para interpretar Goodman, Soderberg e escoamento.",
                    persist_state="session",
                )
            with vida_col:
                vida_requerida_ciclos = st.number_input(
                    "Vida mínima requerida (ciclos)",
                    min_value=0.0,
                    value=0.0,
                    step=100_000.0,
                    format="%.0f",
                    key="fadiga_vida_requerida_memorial",
                    help="Use 0 quando o requisito ainda não estiver definido; o relatório marcará a pendência.",
                    persist_state="session",
                )
        observacoes_memorial = st.text_area(
            "Observações para o memorial (opcional)",
            key="fadiga_observacoes_memorial",
            placeholder=(
                "Escopo específico, número do desenho, equipamento, requisito de "
                "vida, norma contratual ou hipótese que deve constar no documento."
            ),
            height=90,
        )

    dados_memorial = {
        "projeto": nome_projeto,
        "cliente": cliente_projeto,
        "codigo_documento": codigo_documento,
        "revisao": revisao_documento,
        "emissao": data_emissao.strftime("%d/%m/%Y"),
        "responsavel": responsavel_projeto,
        "verificador": verificador_projeto,
        "aprovador": aprovador_projeto,
        "situacao_documento": situacao_documento,
        "observacoes_memorial": observacoes_memorial,
        "componente_analisado": componente_analisado,
        "referencia_projeto": referencia_projeto,
        "fator_seguranca_minimo": fator_seguranca_minimo,
        "vida_requerida_ciclos": vida_requerida_ciclos,
        "modelo": modelo,
        "fonte": fat.FONTES_MARIN[modelo],
        "material": origem_material,
        "material_classe": material,
        "Sut": Sut,
        "Sy": Sy,
        "tipo_carga": ROTULOS_CARGA[tipo_carga],
        "diametro_mm": diametro_mm,
        "acabamento": ROTULOS_ACABAMENTO[acabamento],
        "modo_superficie": modo_superficie,
        "confiabilidade": confiabilidade,
        "temperatura_entrada": temperatura_entrada,
        "unidade_temperatura": unidade_temperatura,
        "temperatura_c": temperatura,
        "temperatura_f": temperatura_f,
        "Ctemp": Ctemp,
        "Se_linha": Se_linha,
        "Se": Se,
        "fatores": fatores,
        "produto_marin": produto_marin,
        "modo_entalhe": modo_entalhe,
        "Kt": Kt,
        "q": q,
        "fator_entalhe": fator_entalhe,
        "nome_fator_entalhe": nome_fator_entalhe,
        "sigma_a_nom": tensao_alternada_nominal,
        "sigma_a": tensao_alternada,
        "sigma_m": tensao_media,
        "sigma_a_eq": tensao_equivalente_vida,
        "Sm": Sm,
        "N1": N1,
        "N2": N2,
        "ciclos_estimados": ciclos_estimados,
        "vida_infinita": vida_infinita,
        "n_goodman": n_goodman,
        "n_soderberg": n_soderberg,
        "n_escoamento": n_escoamento,
        "resultado_vida": resultado_vida,
    }
    gerar_word_atual = partial(
        memorial_word.gerar_memorial_fadiga_word,
        dados_memorial,
        linhas_resumo,
    )
    gerar_pdf_atual = partial(
        fatigue_report.gerar_memorial_fadiga_pdf,
        dados_memorial,
        linhas_resumo,
    )

    word_col, pdf_col = st.columns(2)
    with word_col:
        st.download_button(
            "Baixar memorial editável em Word",
            data=gerar_word_atual,
            file_name="memorial_analise_fadiga.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            icon=":material/description:",
            type="primary",
            width="stretch",
            on_click="ignore",
            help=(
                "Gera um DOCX com resumo executivo, critérios, memória completa, "
                "pendências, checklist, aprovações e integração de outras partes."
            ),
        )
    with pdf_col:
        st.download_button(
            "Baixar memorial em PDF",
            data=gerar_pdf_atual,
            file_name="memorial_analise_fadiga.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            width="stretch",
            on_click="ignore",
            help="Gera a versão estável para impressão com os valores atuais.",
        )

    fatores_validos_registro = [
        float(valor)
        for valor in (n_goodman, n_soderberg, n_escoamento)
        if valor is not None and math.isfinite(float(valor))
    ]
    menor_fator_registro = min(fatores_validos_registro) if fatores_validos_registro else None
    vida_atende_registro = (
        vida_requerida_ciclos <= 0
        or vida_infinita
        or (
            ciclos_estimados is not None
            and math.isfinite(float(ciclos_estimados))
            and float(ciclos_estimados) >= vida_requerida_ciclos
        )
    )
    atende_registro = (
        menor_fator_registro is not None
        and menor_fator_registro >= fator_seguranca_minimo
        and vida_atende_registro
    )
    status_registro = "Atende" if atende_registro else ("Inconclusivo" if menor_fator_registro is None else "Não atende")
    conclusao_registro = (
        f"Menor fator calculado = {menor_fator_registro:.3f} para meta {fator_seguranca_minimo:.3f}; {resultado_vida}."
        if menor_fator_registro is not None
        else "Não há fatores de segurança válidos suficientes para concluir."
    )

    fronteira_modelo(
        [
            "Fadiga multiaxial não proporcional (tensões fora de fase entre si).",
            "Propagação de trinca — este é um modelo de iniciação (tensão-vida), não de mecânica da fratura.",
            "Acúmulo de dano por blocos de carga com amplitudes diferentes (regra de Miner não aplicada aqui).",
            "Corrosão-fadiga e fadiga térmica.",
        ]
    )

    with st.container(border=True):
        st.subheader("Comparar cenários")
        comparador_cenarios(
            escopo="analise_fadiga",
            resumo_entradas={
                "σa (MPa)": round(tensao_alternada, 1),
                "σm (MPa)": round(tensao_media, 1),
                "Se (MPa)": round(Se, 1),
            },
            metricas={
                "n Goodman": "∞" if math.isinf(n_goodman) else round(n_goodman, 2),
                "n Soderberg": (
                    "—" if n_soderberg is None
                    else ("∞" if math.isinf(n_soderberg) else round(n_soderberg, 2))
                ),
                "Vida": resultado_vida,
            },
        )

    registro_fadiga = construir_registro_tecnico(
        modulo="Análise de fadiga",
        modulo_id="analise_fadiga",
        titulo=f"Avaliação de fadiga — {componente_analisado or 'ponto crítico'}",
        status=status_registro,
        resumo="Fatores de Marin, concentração de tensões, Goodman, Soderberg, escoamento no primeiro ciclo e vida S-N.",
        entradas={
            "componente": componente_analisado,
            "material": origem_material,
            "Sut_MPa": Sut,
            "Sy_MPa": Sy,
            "tipo_carga": ROTULOS_CARGA[tipo_carga],
            "diametro_mm": diametro_mm,
            "temperatura_C": temperatura,
            "temperatura_F": temperatura_f,
            "sigma_a_nominal_MPa": tensao_alternada_nominal,
            "sigma_m_MPa": tensao_media,
            "Kt": Kt,
            "q": q,
            "referencia": referencia_projeto,
        },
        resultados={
            "Se_corrigido_MPa": Se,
            "Ctemp": Ctemp,
            "sigma_a_efetiva_MPa": tensao_alternada,
            "n_goodman": n_goodman if n_goodman is not None and math.isfinite(float(n_goodman)) else None,
            "n_soderberg": n_soderberg if n_soderberg is not None and math.isfinite(float(n_soderberg)) else None,
            "n_escoamento": n_escoamento if n_escoamento is not None and math.isfinite(float(n_escoamento)) else None,
            "fator_seguranca": menor_fator_registro,
            "fator_seguranca_minimo": fator_seguranca_minimo,
            "vida_estimada_ciclos": ciclos_estimados if ciclos_estimados is not None and math.isfinite(float(ciclos_estimados)) else None,
            "vida_requerida_ciclos": vida_requerida_ciclos,
            "vida_infinita": vida_infinita,
        },
        premissas=[
            "Modelo tensão-vida e carregamento proporcional no ponto crítico.",
            "As propriedades e fatores devem representar material, acabamento, tamanho e temperatura reais.",
        ],
        alertas=[] if atende_registro else [conclusao_registro],
        referencias=[referencia_projeto or "Definir norma, desenho ou especificação de referência."],
        conclusao=conclusao_registro,
        responsavel=responsavel_projeto,
    )
    botao_registrar_calculo(
        registro_fadiga,
        key="registrar_analise_fadiga",
        rotulo="Registrar análise de fadiga no projeto",
        tipo="secondary",
    )
