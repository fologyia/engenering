import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina, comparador_cenarios, fronteira_modelo
from core import bolt_design as parafusos


st.set_page_config(
    page_title="Projeto de parafusos",
    page_icon=":material/build:",
    layout="wide",
)


def formatar_fator(valor: float) -> str:
    return "∞" if math.isinf(valor) else f"{valor:.2f}"


def classificar_fator(valor: float, minimo: float) -> str:
    if math.isinf(valor):
        return "Não solicitado"
    if valor >= minimo:
        return "Atende"
    if valor >= 1.0:
        return "Abaixo da meta"
    return "Falha prevista"


def exibir_diagnostico(nome: str, valor: float, minimo: float) -> None:
    if math.isinf(valor):
        st.info(f"{nome}: não há solicitação neste modo.")
    elif valor < 1.0:
        st.error(
            f"{nome}: fator {valor:.2f}; a capacidade calculada foi excedida.",
            icon=":material/error:",
        )
    elif valor < minimo:
        st.warning(
            f"{nome}: fator {valor:.2f}; resiste nominalmente, mas não alcança "
            f"a meta n = {minimo:.2f}.",
            icon=":material/warning:",
        )
    else:
        st.success(
            f"{nome}: fator {valor:.2f}; atende à meta informada.",
            icon=":material/check_circle:",
        )


cabecalho_pagina(
    "Projeto completo de juntas parafusadas",
    "Roscas ISO • pré-carga e torque • grupo circular • chapa • fadiga axial",
    categoria="Projetos",
    icone=":material/build:",
    cor="orange",
    ajuda_modulo="Projeto de parafusos",
    acoes=(("app_pages/assistente_cargas.py", "Assistente de cargas", ":material/manufacturing:"),),
    modulo_id="projeto_parafusos",
)
st.session_state.setdefault("parafuso_rosca", "M10")
st.session_state.setdefault("parafuso_numero", 4)
st.session_state.setdefault("parafuso_carga_axial", 40.0)
st.session_state.setdefault("parafuso_carga_cortante", 20.0)
st.session_state.setdefault("parafuso_momento", 0.0)
st.session_state.setdefault("parafuso_torque_grupo", 0.0)

st.warning(
    "Esta aba faz um pré-dimensionamento mecânico. Juntas de segurança, "
    "estruturais, pressurizadas ou sujeitas a vibração exigem a norma aplicável, "
    "dados certificados e validação do processo de aperto.",
    icon=":material/engineering:",
)

with st.container(border=True):
    st.subheader("1. Parafuso e padrão da junta")
    selecao = st.columns(4)
    with selecao[0]:
        nomes_rosca = list(parafusos.ROSCAS_METRICAS)
        rosca_escolhida = st.selectbox(
            "Rosca métrica",
            nomes_rosca,
            key="parafuso_rosca",
            help="Quando não aparece o passo, a rosca é de passo normal.",
            persist_state="session",
        )
    rosca = parafusos.obter_rosca(rosca_escolhida)
    with selecao[1]:
        nomes_classe = list(parafusos.CLASSES_PARAFUSO)
        classe_escolhida = st.selectbox(
            "Classe de propriedade",
            nomes_classe,
            index=nomes_classe.index("8.8"),
            key="parafuso_classe",
            persist_state="session",
        )
    with selecao[2]:
        numero_parafusos = st.number_input(
            "Número de parafusos",
            min_value=1,
            step=1,
            key="parafuso_numero",
            persist_state="session",
        )
    with selecao[3]:
        diametro_circulo_mm = st.number_input(
            "Diâmetro do círculo de parafusos (mm)",
            min_value=0.0,
            value=100.0,
            step=5.0,
            help=(
                "Distância entre parafusos opostos. Pode ser zero somente "
                "quando não há momento nem torque."
            ),
            key="parafuso_diametro_circulo",
            persist_state="session",
        )

    try:
        classe = parafusos.obter_classe(
            classe_escolhida, rosca.diametro_mm
        )
    except ValueError as erro:
        st.error(str(erro), icon=":material/error:")
        st.stop()

    with st.container(horizontal=True):
        st.metric(
            "Área resistente At",
            f"{rosca.area_tracao_mm2:.2f} mm²",
            border=True,
        )
        st.metric(
            "Tensão de prova Sp",
            f"{classe.resistencia_prova_MPa:.0f} MPa",
            border=True,
        )
        st.metric(
            "Escoamento mínimo",
            f"{classe.escoamento_min_MPa:.0f} MPa",
            border=True,
        )
        st.metric(
            "Ruptura mínima",
            f"{classe.ruptura_min_MPa:.0f} MPa",
            border=True,
        )
    if classe.observacao:
        st.caption(classe.observacao)
    if classe.classe == "12.9":
        st.warning(
            "Classe 12.9 requer atenção especial ao fabricante, revestimento, "
            "ambiente e risco de fragilização.",
            icon=":material/warning:",
        )

with st.container(border=True):
    st.subheader("2. Pré-carga, torque e rigidez")
    metodo = st.segmented_control(
        "Condição de instalação",
        ["Torque lubrificado", "Torque seco", "Controle aprimorado"],
        default="Torque lubrificado",
        required=True,
        width="stretch",
        key="parafuso_metodo_instalacao",
        persist_state="session",
    )
    padroes_instalacao = {
        "Torque lubrificado": (0.18, 0.25),
        "Torque seco": (0.20, 0.35),
        "Controle aprimorado": (0.18, 0.10),
    }
    K_padrao, incerteza_padrao = padroes_instalacao[metodo]

    aperto = st.columns(4)
    with aperto[0]:
        fracao_pre_carga = st.number_input(
            "Pré-carga / carga de prova",
            min_value=0.05,
            max_value=1.0,
            value=0.70,
            step=0.05,
            help="Fração da carga de prova usada como pré-carga nominal.",
            key="parafuso_fracao_pre_carga",
            persist_state="session",
        )
    with aperto[1]:
        fator_K = st.number_input(
            "Fator de torque K",
            min_value=0.01,
            max_value=1.0,
            value=K_padrao,
            step=0.01,
            key=f"parafuso_K_{metodo}",
            help="Use valor obtido em ensaio torque–pré-carga quando disponível.",
            persist_state="session",
        )
    with aperto[2]:
        incerteza_pre_carga = st.number_input(
            "Incerteza da pré-carga (±)",
            min_value=0.0,
            max_value=0.95,
            value=incerteza_padrao,
            step=0.05,
            key=f"parafuso_incerteza_{metodo}",
            help="0,25 representa ±25% ao redor da pré-carga nominal.",
            persist_state="session",
        )
    with aperto[3]:
        perda_pre_carga = st.number_input(
            "Perda adicional de pré-carga",
            min_value=0.0,
            max_value=0.95,
            value=0.05,
            step=0.01,
            help="Relaxação, assentamento, fluência ou efeitos térmicos.",
            key="parafuso_perda_pre_carga",
            persist_state="session",
        )

    rigidez = st.number_input(
        "Constante de rigidez C = kb / (kb + km)",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
        help=(
            "Fração da carga axial externa adicionada ao parafuso antes da "
            "separação. kb é a rigidez do parafuso e km a das peças comprimidas."
        ),
        key="parafuso_rigidez",
        persist_state="session",
    )
    st.latex(
        r"F_i=f_i\,S_pA_t,\qquad T=K F_i d,\qquad "
        r"\Delta F_b=C\,P,\quad C=\frac{k_b}{k_b+k_m}"
    )

with st.container(border=True):
    st.subheader("3. Carregamentos de serviço")
    st.caption(
        "A carga axial positiva abre a junta. O momento de tombamento distribui "
        "tração de forma linear; o torque produz cisalhamento tangencial."
    )
    cargas_entrada = st.columns(4)
    with cargas_entrada[0]:
        carga_axial_kN = st.number_input(
            "Carga axial total P (kN)",
            step=5.0,
            key="parafuso_carga_axial",
            persist_state="session",
        )
    with cargas_entrada[1]:
        carga_cortante_kN = st.number_input(
            "Força cortante total V (kN)",
            step=5.0,
            key="parafuso_carga_cortante",
            persist_state="session",
        )
    with cargas_entrada[2]:
        momento_tombamento_Nm = st.number_input(
            "Momento de tombamento M (N·m)",
            step=100.0,
            key="parafuso_momento",
            persist_state="session",
        )
    with cargas_entrada[3]:
        torque_grupo_Nm = st.number_input(
            "Torque no grupo T (N·m)",
            step=100.0,
            key="parafuso_torque_grupo",
            persist_state="session",
        )

    plano_corte = st.segmented_control(
        "Posição da rosca no plano de cisalhamento",
        ["Rosca cruza o plano", "Corpo liso cruza o plano"],
        default="Rosca cruza o plano",
        required=True,
        width="stretch",
        key="parafuso_plano_corte",
        persist_state="session",
    )

with st.container(border=True):
    st.subheader("4. Atrito e verificações da chapa")
    junta = st.columns(3)
    with junta[0]:
        coeficiente_atrito = st.number_input(
            "Coeficiente de atrito entre chapas",
            min_value=0.0,
            value=0.20,
            step=0.05,
            key="parafuso_coeficiente_atrito",
            persist_state="session",
        )
    with junta[1]:
        interfaces_atrito = st.number_input(
            "Interfaces de atrito",
            min_value=1,
            value=1,
            step=1,
            key="parafuso_interfaces_atrito",
            persist_state="session",
        )
    with junta[2]:
        fator_minimo = st.number_input(
            "Fator mínimo desejado",
            min_value=1.0,
            value=1.50,
            step=0.10,
            key="parafuso_fator_minimo",
            persist_state="session",
        )

    chapa = st.columns(4)
    with chapa[0]:
        espessura_chapa_mm = st.number_input(
            "Espessura da chapa t (mm)",
            min_value=0.001,
            value=10.0,
            step=1.0,
            key="parafuso_espessura_chapa",
            persist_state="session",
        )
    with chapa[1]:
        diametro_furo_mm = st.number_input(
            "Diâmetro do furo dh (mm)",
            min_value=rosca.diametro_mm,
            value=rosca.diametro_mm + 1.0,
            step=0.5,
            key=f"parafuso_furo_{rosca.designacao}",
            persist_state="session",
        )
    with chapa[2]:
        distancia_borda_mm = st.number_input(
            "Centro do furo até a borda e (mm)",
            min_value=diametro_furo_mm / 2.0 + 0.001,
            value=max(
                2.0 * rosca.diametro_mm,
                diametro_furo_mm / 2.0 + 0.001,
            ),
            step=1.0,
            key=f"parafuso_borda_{rosca.designacao}_{diametro_furo_mm}",
            persist_state="session",
        )
    with chapa[3]:
        escoamento_chapa_MPa = st.number_input(
            "Escoamento da chapa Sy (MPa)",
            min_value=0.001,
            value=250.0,
            step=10.0,
            key="parafuso_escoamento_chapa",
            persist_state="session",
        )
    limite_esmagamento_MPa = st.number_input(
        "Limite adotado para esmagamento da chapa (MPa)",
        min_value=0.001,
        value=250.0,
        step=10.0,
        key="parafuso_limite_esmagamento",
        help=(
            "Use o limite definido pela norma do material e da junta. "
            "O valor padrão apenas replica Sy."
        ),
        persist_state="session",
    )

try:
    resultado = parafusos.avaliar_junta(
        rosca=rosca,
        classe=classe,
        numero_parafusos=int(numero_parafusos),
        raio_grupo_mm=diametro_circulo_mm / 2.0,
        carga_axial_N=carga_axial_kN * 1_000.0,
        carga_cortante_N=carga_cortante_kN * 1_000.0,
        momento_tombamento_Nmm=momento_tombamento_Nm * 1_000.0,
        torque_grupo_Nmm=torque_grupo_Nm * 1_000.0,
        fracao_pre_carga_prova=fracao_pre_carga,
        fator_porcar_K=fator_K,
        incerteza_pre_carga=incerteza_pre_carga,
        perda_pre_carga=perda_pre_carga,
        constante_rigidez_C=rigidez,
        rosca_no_plano_corte=plano_corte == "Rosca cruza o plano",
        coeficiente_atrito_junta=coeficiente_atrito,
        numero_interfaces_atrito=int(interfaces_atrito),
        espessura_chapa_mm=espessura_chapa_mm,
        diametro_furo_mm=diametro_furo_mm,
        distancia_centro_borda_mm=distancia_borda_mm,
        limite_esmagamento_MPa=limite_esmagamento_MPa,
        escoamento_chapa_MPa=escoamento_chapa_MPa,
    )
except ValueError as erro:
    st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
    st.stop()

st.header("Resultados do projeto")

with st.container(border=True):
    st.subheader("Aperto especificado")
    with st.container(horizontal=True):
        st.metric(
            "Pré-carga nominal por parafuso",
            f"{resultado.pre_carga_nominal_N / 1_000.0:.2f} kN",
            border=True,
        )
        st.metric(
            "Faixa estimada de pré-carga",
            (
                f"{resultado.pre_carga_minima_N / 1_000.0:.2f} a "
                f"{resultado.pre_carga_maxima_N / 1_000.0:.2f} kN"
            ),
            border=True,
        )
        st.metric(
            "Torque nominal estimado",
            f"{resultado.torque_nominal_Nm:.2f} N·m",
            border=True,
        )
        st.metric(
            "Carga de prova por parafuso",
            f"{resultado.carga_prova_N / 1_000.0:.2f} kN",
            border=True,
        )
    st.caption(
        "O torque é uma estimativa pela relação T = K·Fi·d. Dispersão de atrito, "
        "revestimento, reutilização e ferramenta podem alterar muito a pré-carga."
    )

with st.container(border=True):
    st.subheader("Parafuso crítico")
    with st.container(horizontal=True):
        st.metric(
            "Carga axial máxima",
            f"{resultado.carga_maxima_parafuso_N / 1_000.0:.2f} kN",
            border=True,
        )
        st.metric(
            "Tensão axial",
            f"{resultado.tensao_axial_MPa:.1f} MPa",
            border=True,
        )
        st.metric(
            "Tensão de cisalhamento",
            f"{resultado.tensao_cisalhante_MPa:.1f} MPa",
            border=True,
        )
        st.metric(
            "von Mises combinada",
            f"{resultado.tensao_von_mises_MPa:.1f} MPa",
            border=True,
        )

criterios = [
    ("Carga de prova", resultado.fator_prova),
    ("Escoamento combinado", resultado.fator_escoamento_vm),
    ("Ruptura em tração", resultado.fator_ruptura_tracao),
    ("Separação da junta", resultado.fator_separacao),
    ("Deslizamento por atrito", resultado.fator_deslizamento),
    ("Esmagamento da chapa", resultado.fator_esmagamento),
    ("Rasgamento até a borda", resultado.fator_rasgamento_borda),
]
tabela_criterios = pd.DataFrame(
    {
        "Critério": [nome for nome, _ in criterios],
        "Fator calculado": [
            None if math.isinf(valor) else valor for _, valor in criterios
        ],
        "Resultado": [
            classificar_fator(valor, fator_minimo)
            for _, valor in criterios
        ],
    }
)
st.dataframe(
    tabela_criterios,
    hide_index=True,
    column_config={
        "Fator calculado": st.column_config.NumberColumn(format="%.3f"),
    },
)

with st.expander(
    "Diagnóstico de cada modo de falha",
    icon=":material/fact_check:",
):
    for nome, valor in criterios:
        exibir_diagnostico(nome, valor, fator_minimo)

with st.container(border=True):
    st.subheader("Distribuição entre os parafusos")
    raio = diametro_circulo_mm / 2.0
    linhas = []
    for indice, (axial, cisalhamento) in enumerate(
        zip(
            resultado.distribuicao.forcas_axiais_N,
            resultado.distribuicao.forcas_cisalhantes_N,
        )
    ):
        angulo = 2.0 * math.pi * indice / int(numero_parafusos)
        linhas.append(
            {
                "Parafuso": indice + 1,
                "x (mm)": raio * math.cos(angulo),
                "y (mm)": raio * math.sin(angulo),
                "Carga axial externa (kN)": axial / 1_000.0,
                "Cisalhamento resultante (kN)": cisalhamento / 1_000.0,
            }
        )
    distribuicao_df = pd.DataFrame(linhas)
    visual, tabela = st.columns([1, 1.4])
    with visual:
        st.scatter_chart(
            distribuicao_df,
            x="x (mm)",
            y="y (mm)",
            size="Cisalhamento resultante (kN)",
            color="Carga axial externa (kN)",
        )
    with tabela:
        st.dataframe(
            distribuicao_df,
            hide_index=True,
            column_config={
                "x (mm)": st.column_config.NumberColumn(format="%.1f"),
                "y (mm)": st.column_config.NumberColumn(format="%.1f"),
                "Carga axial externa (kN)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
                "Cisalhamento resultante (kN)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
            },
        )

fadiga_resultado = None
fadiga_entradas: dict[str, float] = {}
with st.container(border=True):
    st.subheader("5. Verificação opcional de fadiga axial")
    analisar_fadiga = st.toggle(
        "Ativar análise de fadiga",
        value=False,
        help=(
            "Modelo de Goodman preliminar, válido enquanto a junta permanece "
            "fechada e a distribuição elástica é aplicável."
        ),
        key="parafuso_analisar_fadiga",
        persist_state="session",
    )
    if analisar_fadiga:
        ciclo = st.columns(4)
        with ciclo[0]:
            axial_min_kN = st.number_input(
                "P mínima do ciclo (kN)",
                value=0.0,
                step=5.0,
                key="parafuso_fadiga_axial_min",
                persist_state="session",
            )
        with ciclo[1]:
            axial_max_kN = st.number_input(
                "P máxima do ciclo (kN)",
                value=max(0.0, carga_axial_kN),
                step=5.0,
                key="parafuso_fadiga_axial_max",
                persist_state="session",
            )
        with ciclo[2]:
            momento_min_Nm = st.number_input(
                "M mínimo do ciclo (N·m)",
                value=0.0,
                step=100.0,
                key="parafuso_fadiga_momento_min",
                persist_state="session",
            )
        with ciclo[3]:
            momento_max_Nm = st.number_input(
                "M máximo do ciclo (N·m)",
                value=momento_tombamento_Nm,
                step=100.0,
                key="parafuso_fadiga_momento_max",
                persist_state="session",
            )
        propriedades_fadiga = st.columns(2)
        with propriedades_fadiga[0]:
            Kf = st.number_input(
                "Fator de concentração em fadiga Kf",
                min_value=1.0,
                value=2.0,
                step=0.1,
                help="Inclui o efeito da raiz da rosca e outras concentrações.",
                key="parafuso_fadiga_Kf",
                persist_state="session",
            )
        with propriedades_fadiga[1]:
            Se_parafuso = st.number_input(
                "Limite de fadiga adotado Se (MPa)",
                min_value=0.001,
                value=0.20 * classe.ruptura_min_MPa,
                step=10.0,
                key=f"parafuso_Se_{classe.classe}",
                help=(
                    "O padrão de 20% de Sut é apenas uma estimativa inicial. "
                    "Prefira curva S–N ou dados de ensaio do parafuso."
                ),
                persist_state="session",
            )

        try:
            dist_min = parafusos.distribuir_cargas_grupo_circular(
                int(numero_parafusos),
                raio,
                axial_min_kN * 1_000.0,
                0.0,
                momento_min_Nm * 1_000.0,
                0.0,
            )
            dist_max = parafusos.distribuir_cargas_grupo_circular(
                int(numero_parafusos),
                raio,
                axial_max_kN * 1_000.0,
                0.0,
                momento_max_Nm * 1_000.0,
                0.0,
            )
            resultados_fadiga = []
            for minimo, maximo in zip(
                dist_min.forcas_axiais_N,
                dist_max.forcas_axiais_N,
            ):
                menor, maior = sorted((minimo, maximo))
                resultados_fadiga.append(
                    parafusos.avaliar_fadiga_axial(
                        rosca,
                        classe,
                        resultado.pre_carga_nominal_N,
                        rigidez,
                        menor,
                        maior,
                        Kf,
                        Se_parafuso,
                    )
                )
            fadiga = min(
                resultados_fadiga,
                key=lambda item: item.fator_goodman,
            )
        except ValueError as erro:
            st.error(f"Não foi possível analisar a fadiga: {erro}")
        else:
            with st.container(horizontal=True):
                st.metric(
                    "Tensão alternada",
                    f"{fadiga.tensao_alternada_MPa:.2f} MPa",
                    border=True,
                )
                st.metric(
                    "Tensão média",
                    f"{fadiga.tensao_media_MPa:.2f} MPa",
                    border=True,
                )
                st.metric(
                    "Fator de Goodman",
                    formatar_fator(fadiga.fator_goodman),
                    border=True,
                )
                st.metric(
                    "Fator contra escoamento máximo",
                    formatar_fator(fadiga.fator_escoamento_maximo),
                    border=True,
                )
            exibir_diagnostico(
                "Fadiga por Goodman",
                fadiga.fator_goodman,
                fator_minimo,
            )
            if resultado.fator_separacao < 1.0:
                st.error(
                    "A junta separa no carregamento estático informado. O modelo "
                    "linear de fadiga antes da separação deixa de ser válido.",
                    icon=":material/error:",
                )
            fadiga_resultado = fadiga
            fadiga_entradas = {
                "P_min_kN": axial_min_kN,
                "P_max_kN": axial_max_kN,
                "M_min_Nm": momento_min_Nm,
                "M_max_Nm": momento_max_Nm,
                "Kf": Kf,
                "Se_MPa": Se_parafuso,
            }

fronteira_modelo(
    [
        "Torque real de aperto medido em campo — o torque aqui é estimado por T = K·Fi·d.",
        "Relaxamento térmico, fluência ou reaperto ao longo da vida da junta.",
        "Corrosão, fricção galvânica ou ambiente agressivo.",
        "Fadiga axial, a menos que explicitamente ativada na seção 5.",
    ]
)

with st.container(border=True):
    st.subheader("6. Registrar no projeto")
    fatores_criticos = [valor for _, valor in criterios if math.isfinite(valor)]
    if fadiga_resultado is not None and math.isfinite(fadiga_resultado.fator_goodman):
        fatores_criticos.append(fadiga_resultado.fator_goodman)
    pior_fator = min(fatores_criticos) if fatores_criticos else float("inf")
    if pior_fator < 1.0:
        status_registro = "Não atende"
    elif pior_fator < fator_minimo:
        status_registro = "Atenção"
    else:
        status_registro = "Atende"
    conclusao_registro = (
        f"Menor fator entre os critérios avaliados = {pior_fator:.2f}; meta = {fator_minimo:.2f}."
        if math.isfinite(pior_fator)
        else "Nenhum critério com solicitação finita foi avaliado."
    )
    resultados_registro = {
        "fator_prova": None if math.isinf(resultado.fator_prova) else resultado.fator_prova,
        "fator_escoamento_combinado": (
            None if math.isinf(resultado.fator_escoamento_vm) else resultado.fator_escoamento_vm
        ),
        "fator_ruptura_tracao": (
            None if math.isinf(resultado.fator_ruptura_tracao) else resultado.fator_ruptura_tracao
        ),
        "fator_separacao": None if math.isinf(resultado.fator_separacao) else resultado.fator_separacao,
        "fator_deslizamento": (
            None if math.isinf(resultado.fator_deslizamento) else resultado.fator_deslizamento
        ),
        "fator_esmagamento": (
            None if math.isinf(resultado.fator_esmagamento) else resultado.fator_esmagamento
        ),
        "fator_rasgamento_borda": (
            None if math.isinf(resultado.fator_rasgamento_borda) else resultado.fator_rasgamento_borda
        ),
        "pre_carga_nominal_kN": resultado.pre_carga_nominal_N / 1_000.0,
        "torque_nominal_Nm": resultado.torque_nominal_Nm,
        "tensao_von_mises_MPa": resultado.tensao_von_mises_MPa,
        "fator_seguranca": None if math.isinf(pior_fator) else pior_fator,
        "fator_seguranca_minimo": fator_minimo,
    }
    if fadiga_resultado is not None:
        resultados_registro.update(
            {
                "fadiga_tensao_alternada_MPa": fadiga_resultado.tensao_alternada_MPa,
                "fadiga_tensao_media_MPa": fadiga_resultado.tensao_media_MPa,
                "fadiga_fator_goodman": (
                    None if math.isinf(fadiga_resultado.fator_goodman) else fadiga_resultado.fator_goodman
                ),
                "fadiga_fator_escoamento_maximo": (
                    None
                    if math.isinf(fadiga_resultado.fator_escoamento_maximo)
                    else fadiga_resultado.fator_escoamento_maximo
                ),
            }
        )
    st.subheader("Comparar cenários")
    comparador_cenarios(
        escopo="projeto_parafusos",
        resumo_entradas={
            "Rosca": rosca.designacao,
            "Classe": classe.classe,
            "Nº parafusos": int(numero_parafusos),
            "P (kN)": round(carga_axial_kN, 1),
        },
        metricas={
            "n prova": formatar_fator(resultado.fator_prova),
            "n escoamento": formatar_fator(resultado.fator_escoamento_vm),
            "n separação": formatar_fator(resultado.fator_separacao),
            "Pior fator": formatar_fator(pior_fator),
        },
    )

    registro_parafusos = construir_registro_tecnico(
        modulo="Projeto de parafusos",
        modulo_id="projeto_parafusos",
        titulo=f"Junta parafusada — {rosca.designacao} classe {classe.classe} ({int(numero_parafusos)}x)",
        status=status_registro,
        resumo="Pré-dimensionamento de junta parafusada: pré-carga, torque, grupo circular, chapa e, quando ativada, fadiga axial.",
        entradas={
            "rosca": rosca.designacao,
            "classe": classe.classe,
            "numero_parafusos": int(numero_parafusos),
            "diametro_circulo_mm": diametro_circulo_mm,
            "carga_axial_kN": carga_axial_kN,
            "carga_cortante_kN": carga_cortante_kN,
            "momento_tombamento_Nm": momento_tombamento_Nm,
            "torque_grupo_Nm": torque_grupo_Nm,
            "fracao_pre_carga_prova": fracao_pre_carga,
            "coeficiente_atrito": coeficiente_atrito,
            "espessura_chapa_mm": espessura_chapa_mm,
            "escoamento_chapa_MPa": escoamento_chapa_MPa,
            "fadiga_avaliada": fadiga_resultado is not None,
            **({"fadiga": fadiga_entradas} if fadiga_entradas else {}),
        },
        resultados=resultados_registro,
        metodo="Distribuição elástica em grupo circular; pré-carga por fração da carga de prova; Goodman modificado para fadiga axial opcional.",
        premissas=[
            "Distribuição elástica linear de carga entre os parafusos do grupo.",
            "Pré-carga estimada por T = K·Fi·d; a dispersão real de aperto pode ser maior.",
            "Modelo de fadiga válido enquanto a junta permanece fechada (sem separação).",
        ],
        alertas=(
            [] if status_registro == "Atende"
            else [conclusao_registro]
        ),
        referencias=["NASA Fastener Design Manual, NASA-STD-5020 e tabelas ISO 898.", "Confirmar norma, fabricante e processo de aperto do projeto."],
        conclusao=conclusao_registro,
    )
    botao_registrar_calculo(
        registro_parafusos,
        key="registrar_projeto_parafusos",
        rotulo="Registrar junta parafusada no projeto ativo",
    )

with st.container(border=True):
    st.subheader("Precisa de ajuda para preencher ou interpretar?")
    st.markdown(
        "O **Guia geral** mostra a origem de cada entrada, um exemplo completo "
        "e a leitura dos fatores de prova, separação, deslizamento e chapa."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir o guia de parafusos",
        icon=":material/help:",
        query_params={"modulo": "Projeto de parafusos"},
        width="stretch",
    )
st.caption(
    "Referências técnicas: NASA Fastener Design Manual, NASA-STD-5020 e "
    "tabelas ISO 898 compiladas pela Bossard. Confirme sempre a edição da "
    "norma aplicável ao seu setor."
)
