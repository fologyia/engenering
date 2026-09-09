import math
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.material_verification import mostrar_verificacao_material
from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    id_registro_existente,
)
from components.ui import cabecalho_pagina, fronteira_modelo
from core import mohr_analysis as mohr


st.set_page_config(
    page_title="Círculo de Mohr",
    page_icon=":material/donut_large:",
    layout="wide",
)


EXEMPLOS_2D = {
    "geral": ("Estado combinado", (80.0, -20.0, 35.0)),
    "tracao": ("Tração uniaxial", (100.0, 0.0, 0.0)),
    "cisalhamento": ("Cisalhamento puro", (0.0, 0.0, 50.0)),
    "biaxial": ("Tração biaxial", (120.0, 60.0, 25.0)),
    "compressao": ("Compressão com cisalhamento", (-90.0, -30.0, -40.0)),
}
_estado_assistente = st.session_state.get("mohr_assistente_2d")
if _estado_assistente:
    EXEMPLOS_2D["assistente"] = (
        f"Assistente — {_estado_assistente['descricao']}",
        (
            float(_estado_assistente["sigma_x"]),
            float(_estado_assistente["sigma_y"]),
            float(_estado_assistente["tau_xy"]),
        ),
    )

EXEMPLOS_3D = {
    "geral": ("Estado tridimensional combinado", (90.0, 20.0, -30.0, 25.0, 10.0, -15.0)),
    "uniaxial": ("Tração uniaxial", (120.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    "cisalhamento": ("Cisalhamento puro xy", (0.0, 0.0, 0.0, 50.0, 0.0, 0.0)),
    "hidrostatico": ("Tração hidrostática", (60.0, 60.0, 60.0, 0.0, 0.0, 0.0)),
    "diagonal": ("Estado principal conhecido", (120.0, 40.0, -20.0, 0.0, 0.0, 0.0)),
}

CORES_GRUPOS_2D = {
    "Estado original": "#2563eb",
    "Estado transformado": "#f59e0b",
    "Tensões principais": "#16a34a",
    "Cisalhamento máximo": "#dc2626",
}

CORES_CIRCULOS_3D = {
    "σ1–σ3": "#2563eb",
    "σ1–σ2": "#16a34a",
    "σ2–σ3": "#f59e0b",
}


def formatar_tensao(valor: float) -> str:
    return f"{valor:,.2f} MPa".replace(",", "X").replace(".", ",").replace("X", ".")


def criar_grafico_mohr_2d(
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    resultado: mohr.ResultadoEstadoPlano,
) -> alt.Chart:
    angulos = np.linspace(0.0, 2.0 * np.pi, 361)
    circulo = pd.DataFrame(
        {
            "σ (MPa)": resultado.centro + resultado.raio * np.cos(angulos),
            "τ (MPa)": resultado.raio * np.sin(angulos),
            "ordem": np.arange(len(angulos)),
        }
    )
    transformada = resultado.transformacao
    pontos = pd.DataFrame(
        {
            "σ (MPa)": [
                sigma_x,
                sigma_y,
                transformada.sigma_x_linha,
                transformada.sigma_y_linha,
                resultado.sigma_1_plana,
                resultado.sigma_2_plana,
                resultado.centro,
                resultado.centro,
            ],
            "τ (MPa)": [
                tau_xy,
                -tau_xy,
                transformada.tau_x_linha_y_linha,
                -transformada.tau_x_linha_y_linha,
                0.0,
                0.0,
                resultado.tau_max_plana,
                -resultado.tau_max_plana,
            ],
            "Ponto": ["x", "y", "x'", "y'", "σ1", "σ2", "+τmáx", "−τmáx"],
            "Grupo": [
                "Estado original",
                "Estado original",
                "Estado transformado",
                "Estado transformado",
                "Tensões principais",
                "Tensões principais",
                "Cisalhamento máximo",
                "Cisalhamento máximo",
            ],
        }
    )
    diametros = pd.DataFrame(
        {
            "σ (MPa)": [
                sigma_x,
                sigma_y,
                transformada.sigma_x_linha,
                transformada.sigma_y_linha,
            ],
            "τ (MPa)": [
                tau_xy,
                -tau_xy,
                transformada.tau_x_linha_y_linha,
                -transformada.tau_x_linha_y_linha,
            ],
            "Diâmetro": ["Original", "Original", "Transformado", "Transformado"],
            "ordem": [0, 1, 0, 1],
        }
    )

    margem = max(resultado.raio * 1.18, 1.0)
    dominio_x = [resultado.centro - margem, resultado.centro + margem]
    dominio_y = [-margem, margem]
    eixo_x = alt.X(
        "σ (MPa):Q",
        scale=alt.Scale(domain=dominio_x, zero=False),
        axis=alt.Axis(title="Tensão normal σ (MPa)", grid=True),
    )
    eixo_y = alt.Y(
        "τ (MPa):Q",
        scale=alt.Scale(domain=dominio_y, zero=False),
        axis=alt.Axis(title="Tensão de cisalhamento τ (MPa)", grid=True),
    )

    linha_zero = (
        alt.Chart(pd.DataFrame({"τ (MPa)": [0.0]}))
        .mark_rule(color="#64748b", opacity=0.55)
        .encode(y=eixo_y)
    )
    linha_circulo = (
        alt.Chart(circulo)
        .mark_line(color="#334155", strokeWidth=2.5)
        .encode(x=eixo_x, y=eixo_y, order="ordem:Q")
    )
    linhas_diametro = (
        alt.Chart(diametros)
        .mark_line(strokeDash=[6, 4], strokeWidth=1.5)
        .encode(
            x=eixo_x,
            y=eixo_y,
            detail="Diâmetro:N",
            order="ordem:Q",
            color=alt.Color(
                "Diâmetro:N",
                scale=alt.Scale(
                    domain=["Original", "Transformado"],
                    range=[
                        CORES_GRUPOS_2D["Estado original"],
                        CORES_GRUPOS_2D["Estado transformado"],
                    ],
                ),
                legend=None,
            ),
        )
    )
    marcadores = (
        alt.Chart(pontos)
        .mark_point(size=105, filled=True)
        .encode(
            x=eixo_x,
            y=eixo_y,
            color=alt.Color(
                "Grupo:N",
                scale=alt.Scale(
                    domain=list(CORES_GRUPOS_2D),
                    range=list(CORES_GRUPOS_2D.values()),
                ),
                title=None,
            ),
            tooltip=[
                alt.Tooltip("Ponto:N"),
                alt.Tooltip("Grupo:N"),
                alt.Tooltip("σ (MPa):Q", format=".3f"),
                alt.Tooltip("τ (MPa):Q", format=".3f"),
            ],
        )
    )
    rotulos = (
        alt.Chart(pontos)
        .mark_text(dx=10, dy=-10, fontSize=12)
        .encode(x=eixo_x, y=eixo_y, text="Ponto:N", color=alt.value("#0f172a"))
    )
    return (
        (linha_zero + linha_circulo + linhas_diametro + marcadores + rotulos)
        .properties(height=480)
        .interactive()
    )


def criar_grafico_componentes_2d(
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    resultado: mohr.ResultadoEstadoPlano,
) -> alt.Chart:
    dados = pd.DataFrame(
        {
            "Componente": ["σx", "σy", "τxy", "σx'", "σy'", "τx'y'"],
            "Tensão (MPa)": [
                sigma_x,
                sigma_y,
                tau_xy,
                resultado.transformacao.sigma_x_linha,
                resultado.transformacao.sigma_y_linha,
                resultado.transformacao.tau_x_linha_y_linha,
            ],
            "Referencial": ["Original"] * 3 + ["Girado"] * 3,
        }
    )
    return (
        alt.Chart(dados)
        .mark_bar()
        .encode(
            x=alt.X("Componente:N", sort=None, title=None),
            y=alt.Y("Tensão (MPa):Q", title="Tensão (MPa)"),
            color=alt.Color(
                "Referencial:N",
                scale=alt.Scale(
                    domain=["Original", "Girado"],
                    range=["#2563eb", "#f59e0b"],
                ),
                title=None,
            ),
            tooltip=[
                "Referencial:N",
                "Componente:N",
                alt.Tooltip("Tensão (MPa):Q", format=".3f"),
            ],
        )
        .properties(height=300)
    )


def criar_tabela_transformacoes(
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    theta_graus: float,
    resultado: mohr.ResultadoEstadoPlano,
) -> pd.DataFrame:
    estados = [
        ("Original", 0.0),
        ("Plano escolhido", theta_graus),
        ("Plano principal σ1", resultado.theta_p1_graus),
        ("Plano principal σ2", resultado.theta_p2_graus),
        ("Cisalhamento +τmáx", resultado.theta_tau_positivo_graus),
        ("Cisalhamento −τmáx", resultado.theta_tau_negativo_graus),
    ]
    linhas = []
    for nome, angulo in estados:
        transformacao = mohr.transformar_tensoes_planas(
            sigma_x, sigma_y, tau_xy, angulo
        )
        linhas.append(
            {
                "Estado": nome,
                "θ físico (°)": angulo,
                "σx' (MPa)": transformacao.sigma_x_linha,
                "σy' (MPa)": transformacao.sigma_y_linha,
                "τx'y' (MPa)": transformacao.tau_x_linha_y_linha,
            }
        )
    return pd.DataFrame(linhas)


def criar_grafico_mohr_3d(
    resultado: mohr.ResultadoEstadoTridimensional,
    tracao: mohr.TracaoEmPlano,
) -> alt.Chart:
    angulos = np.linspace(0.0, 2.0 * np.pi, 361)
    partes = []
    for circulo in resultado.circulos:
        partes.append(
            pd.DataFrame(
                {
                    "σ (MPa)": circulo.centro + circulo.raio * np.cos(angulos),
                    "τ (MPa)": circulo.raio * np.sin(angulos),
                    "Círculo": circulo.par,
                    "ordem": np.arange(len(angulos)),
                }
            )
        )
    dados_circulos = pd.concat(partes, ignore_index=True)
    sigma_1, sigma_2, sigma_3 = resultado.tensoes_principais
    pontos_principais = pd.DataFrame(
        {
            "σ (MPa)": [sigma_1, sigma_2, sigma_3],
            "τ (MPa)": [0.0, 0.0, 0.0],
            "Ponto": ["σ1", "σ2", "σ3"],
        }
    )
    ponto_plano = pd.DataFrame(
        {
            "σ (MPa)": [tracao.sigma_normal],
            "τ (MPa)": [tracao.tau_resultante],
            "Ponto": ["Plano n (|τ|)"],
        }
    )

    circulo_maior = resultado.circulos[0]
    margem = max(circulo_maior.raio * 1.18, 1.0)
    dominio_x = [circulo_maior.centro - margem, circulo_maior.centro + margem]
    dominio_y = [-margem, margem]
    eixo_x = alt.X(
        "σ (MPa):Q",
        scale=alt.Scale(domain=dominio_x, zero=False),
        axis=alt.Axis(title="Tensão normal σ (MPa)", grid=True),
    )
    eixo_y = alt.Y(
        "τ (MPa):Q",
        scale=alt.Scale(domain=dominio_y, zero=False),
        axis=alt.Axis(title="Tensão de cisalhamento τ (MPa)", grid=True),
    )
    linha_zero = (
        alt.Chart(pd.DataFrame({"τ (MPa)": [0.0]}))
        .mark_rule(color="#64748b", opacity=0.55)
        .encode(y=eixo_y)
    )
    linhas = (
        alt.Chart(dados_circulos)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=eixo_x,
            y=eixo_y,
            order="ordem:Q",
            detail="Círculo:N",
            color=alt.Color(
                "Círculo:N",
                scale=alt.Scale(
                    domain=list(CORES_CIRCULOS_3D),
                    range=list(CORES_CIRCULOS_3D.values()),
                ),
                title=None,
            ),
            tooltip=["Círculo:N"],
        )
    )
    principais = (
        alt.Chart(pontos_principais)
        .mark_point(size=115, filled=True, color="#0f172a")
        .encode(
            x=eixo_x,
            y=eixo_y,
            tooltip=[
                "Ponto:N",
                alt.Tooltip("σ (MPa):Q", format=".3f"),
            ],
        )
    )
    rotulos = (
        alt.Chart(pontos_principais)
        .mark_text(dx=10, dy=-11, fontSize=12, color="#0f172a")
        .encode(x=eixo_x, y=eixo_y, text="Ponto:N")
    )
    plano = (
        alt.Chart(ponto_plano)
        .mark_point(
            size=160,
            filled=True,
            color="#dc2626",
            shape="diamond",
        )
        .encode(
            x=eixo_x,
            y=eixo_y,
            tooltip=[
                "Ponto:N",
                alt.Tooltip("σ (MPa):Q", format=".3f"),
                alt.Tooltip("τ (MPa):Q", format=".3f"),
            ],
        )
    )
    return (
        (linha_zero + linhas + principais + rotulos + plano)
        .properties(height=500)
        .interactive()
    )


def mostrar_diagnostico_equivalente(von_mises: float, tresca: float | None = None) -> None:
    with st.expander(
        "Como usar as tensões equivalentes com um material",
        icon=":material/verified_user:",
    ):
        st.markdown(
            """
            Para um material **dúctil e aproximadamente isotrópico**, compare
            a tensão equivalente com o limite de escoamento $S_y$:

            $$n_{VM}=\\frac{S_y}{\\sigma_{VM}}$$

            O critério de Tresca é mais conservador em muitos estados e usa
            $\\sigma_{eq,T}=\\sigma_1-\\sigma_3$. Para material frágil, não
            substitua automaticamente as tensões principais por von Mises:
            compare $\\sigma_1$ e $\\sigma_3$ com resistências de tração e
            compressão por um critério apropriado.
            """
        )
        if tresca is None:
            st.caption(f"Resultado atual: σVM = {formatar_tensao(von_mises)}.")
        else:
            st.caption(
                f"Resultados atuais: σVM = {formatar_tensao(von_mises)} e "
                f"σeq,Tresca = {formatar_tensao(tresca)}."
            )


cabecalho_pagina(
    "Círculo de Mohr e transformação de tensões",
    "Estados 2D e 3D • tensões principais • planos inclinados • critérios de falha",
    categoria="Análises",
    icone=":material/donut_large:",
    cor="blue",
    ajuda_modulo="Círculo de Mohr",
    acoes=(("app_pages/assistente_cargas.py", "Calcular pelas cargas", ":material/manufacturing:"),),
    modulo_id="circulo_mohr",
)
st.info(
    "**Para que serve:** em um mesmo ponto do material, a tensão medida muda "
    "conforme o ângulo do corte que você observa. O Círculo de Mohr encontra, "
    "para qualquer ponto, a direção onde o material está sendo mais esticado "
    "(**tensões principais**, σ1/σ2) e a direção onde está sendo mais torcido "
    "(**cisalhamento máximo**) — informações essenciais para saber se algo vai "
    "romper ou escoar.",
    icon=":material/lightbulb:",
)
st.caption(
    "Convenção: tração positiva; θ físico é anti-horário de x para x'. "
    "No círculo, a mesma transformação percorre −2θ."
)

modo = st.segmented_control(
    "Tipo de estado de tensão",
    ["Estado plano (2D)", "Estado geral (3D)"],
    default="Estado plano (2D)",
    required=True,
    width="stretch",
    key="mohr_tipo_estado",
    persist_state="session",
)

if modo == "Estado plano (2D)":
    with st.container(border=True):
        st.subheader("Entradas do estado plano")
        exemplo = st.selectbox(
            "Exemplo rápido",
            list(EXEMPLOS_2D),
            format_func=lambda chave: EXEMPLOS_2D[chave][0],
            help="Escolha um caso e altere livremente as componentes.",
            key="mohr_2d_exemplo",
            persist_state="session",
        )
        padroes = EXEMPLOS_2D[exemplo][1]
        entradas = st.columns(3)
        with entradas[0]:
            sigma_x = st.number_input(
                "σx (MPa)",
                value=padroes[0],
                step=5.0,
                key=f"mohr_2d_sigma_x_{exemplo}",
                persist_state="session",
            )
        with entradas[1]:
            sigma_y = st.number_input(
                "σy (MPa)",
                value=padroes[1],
                step=5.0,
                key=f"mohr_2d_sigma_y_{exemplo}",
                persist_state="session",
            )
        with entradas[2]:
            tau_xy = st.number_input(
                "τxy (MPa)",
                value=padroes[2],
                step=5.0,
                key=f"mohr_2d_tau_xy_{exemplo}",
                help="Positiva na face +x apontando para +y.",
                persist_state="session",
            )
        theta_graus = st.slider(
            "Rotação física do elemento, θ (graus)",
            min_value=-90.0,
            max_value=90.0,
            value=25.0,
            step=0.5,
            key=f"mohr_2d_theta_{exemplo}",
            help="Ângulo anti-horário do eixo x para o eixo x'.",
            persist_state="session",
        )

    resultado_2d = mohr.analisar_estado_plano(
        sigma_x, sigma_y, tau_xy, theta_graus
    )
    transformada = resultado_2d.transformacao

    st.subheader("Resultados principais")
    st.caption(
        "**σ1/σ2** são os maiores valores de tração/compressão que existem "
        "nesse ponto, em alguma direção. **τmáx** é o maior cisalhamento "
        "(torção local) possível. **von Mises** combina tudo em um único "
        "número para comparar diretamente com o limite de escoamento do "
        "material."
    )
    with st.container(horizontal=True):
        st.metric("σ1 no plano", formatar_tensao(resultado_2d.sigma_1_plana), border=True)
        st.metric("σ2 no plano", formatar_tensao(resultado_2d.sigma_2_plana), border=True)
        st.metric("τmáx no plano", formatar_tensao(resultado_2d.tau_max_plana), border=True)
        st.metric("von Mises", formatar_tensao(resultado_2d.von_mises), border=True)
    with st.container(horizontal=True):
        st.metric("σx' no plano escolhido", formatar_tensao(transformada.sigma_x_linha), border=True)
        st.metric("σy' no plano escolhido", formatar_tensao(transformada.sigma_y_linha), border=True)
        st.metric("τx'y' no plano escolhido", formatar_tensao(transformada.tau_x_linha_y_linha), border=True)
        st.metric("τmáx absoluto (3D)", formatar_tensao(resultado_2d.tau_max_absoluta), border=True)

    if math.isclose(resultado_2d.raio, 0.0, abs_tol=1e-12):
        st.info(
            "Estado equibiaxial: todo plano no plano xy é principal e a orientação "
            "de σ1 é indeterminada. O programa mostra 0° apenas como referência.",
            icon=":material/info:",
        )

    graficos = st.columns([1.35, 0.85])
    with graficos[0]:
        with st.container(border=True):
            st.subheader("Círculo de Mohr 2D")
            st.altair_chart(
                criar_grafico_mohr_2d(sigma_x, sigma_y, tau_xy, resultado_2d),
                width="stretch",
            )
            st.caption(
                "Azul: faces originais • laranja: faces giradas • "
                "verde: tensões principais • vermelho: cisalhamento máximo."
            )
    with graficos[1]:
        with st.container(border=True):
            st.subheader("Original × transformado")
            st.altair_chart(
                criar_grafico_componentes_2d(
                    sigma_x, sigma_y, tau_xy, resultado_2d
                ),
                width="stretch",
            )
            st.markdown(
                f"""
                **Centro:** {formatar_tensao(resultado_2d.centro)}

                **Raio:** {formatar_tensao(resultado_2d.raio)}

                **Plano de σ1:** θ = {resultado_2d.theta_p1_graus:.2f}°

                **Plano de +τmáx:** θ = {resultado_2d.theta_tau_positivo_graus:.2f}°
                """
            )

    with st.container(border=True):
        st.subheader("Mapa das transformações")
        tabela_transformacoes = criar_tabela_transformacoes(
            sigma_x, sigma_y, tau_xy, theta_graus, resultado_2d
        )
        st.dataframe(
            tabela_transformacoes,
            hide_index=True,
            column_config={
                "θ físico (°)": st.column_config.NumberColumn(format="%.2f°"),
                "σx' (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "σy' (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "τx'y' (MPa)": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        st.caption(
            "As orientações de plano se repetem a cada 180°. Nos planos principais, "
            "τ = 0; os planos de cisalhamento extremo ficam a 45° deles."
        )

    with st.expander(
        "Equações usadas no estado plano",
        icon=":material/functions:",
    ):
        st.markdown(
            r"""
            $$
            C=\frac{\sigma_x+\sigma_y}{2},\qquad
            R=\sqrt{\left(\frac{\sigma_x-\sigma_y}{2}\right)^2+\tau_{xy}^2}
            $$

            $$
            \sigma_{1,2}=C\pm R,\qquad
            \tan(2\theta_p)=\frac{2\tau_{xy}}{\sigma_x-\sigma_y}
            $$

            $$
            \sigma_{x'}=C+\frac{\sigma_x-\sigma_y}{2}\cos(2\theta)
            +\tau_{xy}\sin(2\theta)
            $$

            $$
            \tau_{x'y'}=-\frac{\sigma_x-\sigma_y}{2}\sin(2\theta)
            +\tau_{xy}\cos(2\theta)
            $$

            Em **estado plano de tensões**, a terceira tensão principal é
            $\sigma_z=0$. Por isso, o máximo cisalhamento absoluto deve usar
            o maior intervalo entre $\{\sigma_1,\sigma_2,0\}$ e pode ser
            maior que o raio do círculo 2D.
            """
        )

    mostrar_diagnostico_equivalente(resultado_2d.von_mises)
    mostrar_verificacao_material(
        resultado_2d.tensoes_principais_3d,
        resultado_2d.von_mises,
        prefixo="mohr_2d",
    )
    origem_assistente = (
        _estado_assistente.get("origem_registro_id")
        if (exemplo == "assistente" and _estado_assistente)
        else None
    )

    fronteira_modelo(
        [
            "Estado real tridimensional — aqui σz = 0 é uma hipótese, não um dado medido.",
            "Concentração de tensão e efeitos localizados de furos, entalhes ou soldas.",
            "Carga variável no tempo (fadiga) — este é um estado instantâneo.",
        ]
    )

    registro_mohr_2d = construir_registro_tecnico(
        modulo="Círculo de Mohr",
        modulo_id="circulo_mohr",
        titulo="Transformação do estado plano de tensões",
        status="Calculado",
        resumo="Tensões principais, cisalhamento máximo, von Mises e transformação no plano escolhido.",
        entradas={
            "sigma_x_MPa": sigma_x,
            "sigma_y_MPa": sigma_y,
            "tau_xy_MPa": tau_xy,
            "theta_graus": theta_graus,
            "registro_origem": origem_assistente,
        },
        resultados={
            "sigma_1_MPa": resultado_2d.sigma_1_plana,
            "sigma_2_MPa": resultado_2d.sigma_2_plana,
            "tau_max_plana_MPa": resultado_2d.tau_max_plana,
            "tau_max_absoluta_MPa": resultado_2d.tau_max_absoluta,
            "von_mises_MPa": resultado_2d.von_mises,
            "theta_principal_graus": resultado_2d.theta_p1_graus,
            "sigma_x_transformada_MPa": transformada.sigma_x_linha,
            "sigma_y_transformada_MPa": transformada.sigma_y_linha,
            "tau_transformada_MPa": transformada.tau_x_linha_y_linha,
        },
        premissas=[
            "Tensor simétrico e estado plano de tensões, com sigma_z = 0.",
            "Ângulos representam rotação física anti-horária do elemento.",
        ],
        referencias=["Vincular o tensor ao ponto, caso de carga e revisão do modelo ou memória de origem."],
        conclusao="Estado transformado calculado; a aceitação depende do material e do critério do projeto.",
    )
    if exemplo == "assistente" and not origem_assistente:
        st.caption(
            ":material/link_off: Este estado veio do Assistente de cargas, mas "
            "ainda não foi registrado lá — a origem não será rastreada até que "
            "seja registrado."
        )
    botao_registrar_calculo(
        registro_mohr_2d,
        key="registrar_mohr_2d",
        rotulo="Registrar análise de Mohr no projeto",
        tipo="secondary",
    )
    # A origem a repassar adiante é a que já vinha do Assistente de cargas
    # (Mohr só transforma o mesmo estado, não cria um novo); na ausência
    # dela, usa o próprio registro de Mohr, se ele já tiver sido salvo.
    origem_para_repasse = origem_assistente or id_registro_existente(registro_mohr_2d)
    if st.button(
        "Enviar σx, σy, τxy para a Análise estática",
        icon=":material/analytics:",
        key="mohr_2d_enviar_estatica",
    ):
        st.session_state["estatica_sigma_x"] = sigma_x
        st.session_state["estatica_sigma_y"] = sigma_y
        st.session_state["estatica_tau_xy"] = tau_xy
        st.session_state["estatica_origem_registro_id"] = origem_para_repasse
        st.switch_page("app_pages/analise_estatica.py")

else:
    with st.container(border=True):
        st.subheader("Entradas do tensor de tensões")
        exemplo = st.selectbox(
            "Exemplo rápido",
            list(EXEMPLOS_3D),
            format_func=lambda chave: EXEMPLOS_3D[chave][0],
            help="Escolha um caso e altere livremente as seis componentes.",
            key="mohr_3d_exemplo",
            persist_state="session",
        )
        padroes = EXEMPLOS_3D[exemplo][1]
        normais = st.columns(3)
        with normais[0]:
            sigma_x = st.number_input(
                "σx (MPa)", value=padroes[0], step=5.0, key=f"mohr_3d_sx_{exemplo}",
                persist_state="session",
            )
        with normais[1]:
            sigma_y = st.number_input(
                "σy (MPa)", value=padroes[1], step=5.0, key=f"mohr_3d_sy_{exemplo}",
                persist_state="session",
            )
        with normais[2]:
            sigma_z = st.number_input(
                "σz (MPa)", value=padroes[2], step=5.0, key=f"mohr_3d_sz_{exemplo}",
                persist_state="session",
            )
        cisalhamentos = st.columns(3)
        with cisalhamentos[0]:
            tau_xy = st.number_input(
                "τxy = τyx (MPa)",
                value=padroes[3],
                step=5.0,
                key=f"mohr_3d_txy_{exemplo}",
                persist_state="session",
            )
        with cisalhamentos[1]:
            tau_xz = st.number_input(
                "τxz = τzx (MPa)",
                value=padroes[4],
                step=5.0,
                key=f"mohr_3d_txz_{exemplo}",
                persist_state="session",
            )
        with cisalhamentos[2]:
            tau_yz = st.number_input(
                "τyz = τzy (MPa)",
                value=padroes[5],
                step=5.0,
                key=f"mohr_3d_tyz_{exemplo}",
                persist_state="session",
            )

    resultado_3d = mohr.analisar_estado_tridimensional(
        sigma_x, sigma_y, sigma_z, tau_xy, tau_xz, tau_yz
    )

    with st.container(border=True):
        st.subheader("Plano de interesse")
        modo_normal = st.segmented_control(
            "Como definir a normal unitária do plano?",
            ["Componentes", "Azimute e elevação"],
            default="Componentes",
            required=True,
            width="stretch",
            key="mohr_3d_modo_normal",
            persist_state="session",
        )
        if modo_normal == "Componentes":
            componentes = st.columns(3)
            with componentes[0]:
                normal_x = st.number_input("nx", value=1.0, step=0.1, key="normal_x_3d", persist_state="session")
            with componentes[1]:
                normal_y = st.number_input("ny", value=1.0, step=0.1, key="normal_y_3d", persist_state="session")
            with componentes[2]:
                normal_z = st.number_input("nz", value=0.0, step=0.1, key="normal_z_3d", persist_state="session")
            normal = (normal_x, normal_y, normal_z)
        else:
            angulos_normal = st.columns(2)
            with angulos_normal[0]:
                azimute = st.slider(
                    "Azimute α no plano xy (°)",
                    -180.0,
                    180.0,
                    45.0,
                    1.0,
                    help="Medido de +x para +y.",
                    key="mohr_3d_azimute",
                    persist_state="session",
                )
            with angulos_normal[1]:
                elevacao = st.slider(
                    "Elevação β a partir do plano xy (°)",
                    -90.0,
                    90.0,
                    0.0,
                    1.0,
                    help="Positiva em direção a +z.",
                    key="mohr_3d_elevacao",
                    persist_state="session",
                )
            alpha = math.radians(azimute)
            beta = math.radians(elevacao)
            normal = (
                math.cos(beta) * math.cos(alpha),
                math.cos(beta) * math.sin(alpha),
                math.sin(beta),
            )
        try:
            tracao = mohr.tracao_em_plano(resultado_3d.tensor, normal)
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()
        st.caption(
            "A normal informada é normalizada automaticamente. Trocar n por −n "
            "representa a outra face do mesmo plano."
        )

    st.subheader("Resultados principais")
    st.caption(
        "**σ1, σ2, σ3** são as três tensões principais do ponto (as maiores "
        "trações/compressões em qualquer direção). **von Mises** e **Tresca** "
        "são formas de resumir tudo em um único número comparável ao limite "
        "de escoamento do material."
    )
    sigma_1, sigma_2, sigma_3 = resultado_3d.tensoes_principais
    with st.container(horizontal=True):
        st.metric("σ1", formatar_tensao(sigma_1), border=True)
        st.metric("σ2", formatar_tensao(sigma_2), border=True)
        st.metric("σ3", formatar_tensao(sigma_3), border=True)
        st.metric("τmáx absoluto", formatar_tensao(resultado_3d.tau_max_absoluta), border=True)
    with st.container(horizontal=True):
        st.metric("von Mises", formatar_tensao(resultado_3d.von_mises), border=True)
        st.metric("Tresca equivalente", formatar_tensao(resultado_3d.tresca_equivalente), border=True)
        st.metric("Tensão média", formatar_tensao(resultado_3d.tensao_media), border=True)
        st.metric("τ octaédrica", formatar_tensao(resultado_3d.tau_octaedrica), border=True)

    escala = max(1.0, max(abs(valor) for valor in resultado_3d.tensoes_principais))
    if (
        abs(sigma_1 - sigma_2) <= 1e-9 * escala
        or abs(sigma_2 - sigma_3) <= 1e-9 * escala
    ):
        st.info(
            "Há tensões principais repetidas. Dentro do subespaço repetido, "
            "as direções principais não são únicas.",
            icon=":material/info:",
        )

    visualizacoes = st.columns([1.35, 0.85])
    with visualizacoes[0]:
        with st.container(border=True):
            st.subheader("Três círculos de Mohr")
            st.altair_chart(
                criar_grafico_mohr_3d(resultado_3d, tracao),
                width="stretch",
            )
            st.caption(
                "O losango vermelho posiciona (σn, |τ|) do plano escolhido. "
                "Sem definir uma direção tangente, o cisalhamento 3D tem magnitude, não sinal único."
            )
    with visualizacoes[1]:
        with st.container(border=True):
            st.subheader("Tração no plano escolhido")
            with st.container(horizontal=True):
                st.metric("σn", formatar_tensao(tracao.sigma_normal), border=True)
                st.metric("|τ|", formatar_tensao(tracao.tau_resultante), border=True)
            dados_tracao = pd.DataFrame(
                {
                    "Componente": ["x", "y", "z"],
                    "n unitário": tracao.normal_unitaria,
                    "t = σ·n (MPa)": tracao.vetor_tracao,
                    "τ no plano (MPa)": tracao.vetor_cisalhamento,
                }
            )
            st.dataframe(
                dados_tracao,
                hide_index=True,
                column_config={
                    "n unitário": st.column_config.NumberColumn(format="%.5f"),
                    "t = σ·n (MPa)": st.column_config.NumberColumn(format="%.3f"),
                    "τ no plano (MPa)": st.column_config.NumberColumn(format="%.3f"),
                },
            )
            st.latex(
                rf"\mathbf{{n}}=({tracao.normal_unitaria[0]:.4f},"
                rf"{tracao.normal_unitaria[1]:.4f},"
                rf"{tracao.normal_unitaria[2]:.4f})"
            )

    with st.container(border=True):
        st.subheader("Direções principais")
        st.caption(
            "Mostra para onde apontam as direções de σ1, σ2 e σ3 no espaço "
            "— útil para saber em que orientação a peça está sendo mais "
            "solicitada."
        )
        direcoes = resultado_3d.direcoes_principais
        tabela_direcoes = pd.DataFrame(
            {
                "Direção": ["σ1", "σ2", "σ3"],
                "Tensão (MPa)": resultado_3d.tensoes_principais,
                "nx": direcoes[0, :],
                "ny": direcoes[1, :],
                "nz": direcoes[2, :],
            }
        )
        st.dataframe(
            tabela_direcoes,
            hide_index=True,
            column_config={
                "Tensão (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "nx": st.column_config.NumberColumn(format="%.5f"),
                "ny": st.column_config.NumberColumn(format="%.5f"),
                "nz": st.column_config.NumberColumn(format="%.5f"),
            },
        )
        st.caption(
            "Cada linha fornece o vetor unitário normal ao plano principal correspondente."
        )

    with st.expander(
        "Avançado — invariantes do tensor (I1, I2, I3, J2, J3)",
        icon=":material/functions:",
    ):
        st.caption(
            "Grandezas matemáticas que não mudam com a orientação dos eixos. "
            "Só são necessárias para verificações mais avançadas ou "
            "conferência com outro software — a maioria dos usuários pode "
            "ignorar esta tabela."
        )
        tabela_invariantes = pd.DataFrame(
            {
                "Invariante": ["I1", "I2", "I3", "J2", "J3"],
                "Valor": [
                    resultado_3d.I1,
                    resultado_3d.I2,
                    resultado_3d.I3,
                    resultado_3d.J2,
                    resultado_3d.J3,
                ],
                "Unidade": ["MPa", "MPa²", "MPa³", "MPa²", "MPa³"],
                "Leitura": [
                    "Traço do tensor",
                    "Segundo invariante",
                    "Determinante",
                    "Energia distorcional",
                    "Terceiro invariante desviador",
                ],
            }
        )
        st.dataframe(
            tabela_invariantes,
            hide_index=True,
            column_config={
                "Valor": st.column_config.NumberColumn(format="%.5g"),
            },
        )

    with st.expander(
        "Equações usadas no estado tridimensional",
        icon=":material/functions:",
    ):
        st.markdown(
            r"""
            As tensões principais são os autovalores do tensor simétrico:

            $$
            \det(\boldsymbol{\sigma}-\sigma_p\mathbf{I})=0
            $$

            Para um plano cuja normal unitária é $\mathbf{n}$:

            $$
            \mathbf{t}=\boldsymbol{\sigma}\mathbf{n},\qquad
            \sigma_n=\mathbf{n}\cdot\mathbf{t},\qquad
            \boldsymbol{\tau}=\mathbf{t}-\sigma_n\mathbf{n}
            $$

            $$
            \sigma_{VM}=\sqrt{3J_2},\qquad
            \tau_{\max}=\frac{\sigma_1-\sigma_3}{2},\qquad
            \sigma_{eq,Tresca}=\sigma_1-\sigma_3
            $$
            """
        )

    mostrar_diagnostico_equivalente(
        resultado_3d.von_mises, resultado_3d.tresca_equivalente
    )
    mostrar_verificacao_material(
        resultado_3d.tensoes_principais,
        resultado_3d.von_mises,
        prefixo="mohr_3d",
    )
    registro_mohr_3d = construir_registro_tecnico(
        modulo="Círculo de Mohr",
        modulo_id="circulo_mohr",
        titulo="Análise tridimensional do tensor de tensões",
        status="Calculado",
        resumo="Tensões principais, invariantes, equivalentes e tração no plano de interesse.",
        entradas={
            "sigma_x_MPa": sigma_x,
            "sigma_y_MPa": sigma_y,
            "sigma_z_MPa": sigma_z,
            "tau_xy_MPa": tau_xy,
            "tau_xz_MPa": tau_xz,
            "tau_yz_MPa": tau_yz,
            "normal_do_plano": [float(valor) for valor in tracao.normal_unitaria],
        },
        resultados={
            "sigma_1_MPa": sigma_1,
            "sigma_2_MPa": sigma_2,
            "sigma_3_MPa": sigma_3,
            "tau_max_absoluta_MPa": resultado_3d.tau_max_absoluta,
            "von_mises_MPa": resultado_3d.von_mises,
            "tresca_equivalente_MPa": resultado_3d.tresca_equivalente,
            "sigma_normal_plano_MPa": tracao.sigma_normal,
            "tau_resultante_plano_MPa": tracao.tau_resultante,
            "I1": resultado_3d.I1,
            "J2": resultado_3d.J2,
        },
        premissas=[
            "Tensor de Cauchy simétrico no ponto e sistema de coordenadas informado.",
            "A normal do plano é normalizada automaticamente.",
        ],
        referencias=["Rastrear o tensor ao nó/elemento, caso de carga e revisão da análise de origem."],
        conclusao="Estado tridimensional calculado; a aceitação depende do critério de falha e da base normativa do projeto.",
    )
    botao_registrar_calculo(
        registro_mohr_3d,
        key="registrar_mohr_3d",
        rotulo="Registrar análise 3D no projeto",
        tipo="secondary",
    )

with st.container(border=True):
    st.subheader("Precisa interpretar estes resultados?")
    st.markdown(
        "O **Guia geral** explica tensões principais, cisalhamento máximo, "
        "planos inclinados, sinais e como copiar o tensor de uma simulação."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir o guia do Círculo de Mohr",
        icon=":material/help:",
        query_params={"modulo": "Círculo de Mohr"},
        width="stretch",
    )
st.caption(
    "Referência de conferência: notas de transformação de tensões e Círculo de Mohr "
    "do [MIT OpenCourseWare](https://ocw.mit.edu/courses/16-001-unified-engineering-materials-and-structures-fall-2021/mit16_001_f21_lec11lec12.pdf)."
)
