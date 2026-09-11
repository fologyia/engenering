import math

import streamlit as st

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina, comparador_cenarios, configurar_pagina, fronteira_modelo
from core import column_buckling as flambagem
from core import material_catalog as mat
from core import section_catalog as catalogo_perfis
from core.materials_registry import avaliar_material, resumir_fonte
from core.project_store import obter_projeto_ativo

configurar_pagina("Flambagem de colunas", ":material/architecture:")
cabecalho_pagina(
    "Flambagem de colunas",
    "Índice de esbeltez • carga crítica de Euler • transição de Johnson",
    categoria="Análises",
    icone=":material/architecture:",
    cor="blue",
    ajuda_modulo="Flambagem de colunas",
    acoes=(("app_pages/assistente_cargas.py", "Assistente de cargas", ":material/manufacturing:"),),
    modulo_id="flambagem_colunas",
)
st.caption(
    "Modelo clássico de Euler/Johnson, válido para qualquer material e "
    "seção prismática sob compressão centrada. Para o dimensionamento "
    "normativo de perfis de aço (NBR 8800/AISC, com o fator χ), use "
    "**Estruturas de aço**."
)
st.session_state.setdefault("flambagem_comprimento_mm", 2_000.0)
st.session_state.setdefault("flambagem_forca_kN", 50.0)
st.session_state.setdefault("flambagem_E_MPa", 200_000.0)
st.session_state.setdefault("flambagem_fs_desejado", 2.0)

with st.container(border=True):
    st.subheader("1. Geometria da seção")
    tipo_secao = st.segmented_control(
        "Tipo de seção",
        [
            "Retangular",
            "Circular maciça",
            "Circular vazada (tubo)",
            "Perfil de aço (catálogo)",
            "Área e raio de giração diretos",
        ],
        default="Circular maciça",
        required=True,
        width="stretch",
        key="flambagem_tipo_secao",
        persist_state="session",
    )

    if tipo_secao == "Retangular":
        colunas = st.columns(2)
        largura_mm = colunas[0].number_input(
            "Largura b (mm)",
            min_value=0.001,
            value=50.0,
            step=5.0,
            key="flambagem_retangular_b",
            persist_state="session",
        )
        altura_mm = colunas[1].number_input(
            "Altura h (mm)",
            min_value=0.001,
            value=100.0,
            step=5.0,
            key="flambagem_retangular_h",
            persist_state="session",
        )
        geometria = flambagem.geometria_retangular(largura_mm, altura_mm)

    elif tipo_secao == "Circular maciça":
        diametro_mm = st.number_input(
            "Diâmetro d (mm)",
            min_value=0.001,
            value=50.0,
            step=5.0,
            key="flambagem_circular_d",
            persist_state="session",
        )
        geometria = flambagem.geometria_circular_macica(diametro_mm)

    elif tipo_secao == "Circular vazada (tubo)":
        colunas = st.columns(2)
        de_mm = colunas[0].number_input(
            "Diâmetro externo (mm)",
            min_value=0.001,
            value=60.0,
            step=5.0,
            key="flambagem_tubo_de",
            persist_state="session",
        )
        di_mm = colunas[1].number_input(
            "Diâmetro interno (mm)",
            min_value=0.0,
            value=48.0,
            step=5.0,
            key="flambagem_tubo_di",
            persist_state="session",
        )
        try:
            geometria = flambagem.geometria_circular_vazada(de_mm, di_mm)
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()

    elif tipo_secao == "Perfil de aço (catálogo)":
        nome_perfil = st.selectbox(
            "Perfil",
            list(catalogo_perfis.listar_perfis()),
            key="flambagem_perfil_catalogo",
            persist_state="session",
        )
        perfil = catalogo_perfis.obter_perfil(nome_perfil)
        geometria = flambagem.geometria_perfil_catalogo(perfil)
        with st.container(horizontal=True):
            st.metric("Área", f"{perfil.area_mm2:.0f} mm²", border=True)
            st.metric("rx", f"{perfil.rx_mm:.1f} mm", border=True)
            st.metric("ry", f"{perfil.ry_mm:.1f} mm", border=True)

    else:
        colunas = st.columns(3)
        area_mm2 = colunas[0].number_input(
            "Área A (mm²)",
            min_value=0.001,
            value=1_000.0,
            step=50.0,
            key="flambagem_direta_area",
            persist_state="session",
        )
        raio_x_mm = colunas[1].number_input(
            "Raio de giração rx (mm)",
            min_value=0.001,
            value=15.0,
            step=1.0,
            key="flambagem_direta_rx",
            persist_state="session",
        )
        mesmo_raio = colunas[2].checkbox(
            "ry = rx (seção com simetria dupla)",
            value=True,
            key="flambagem_direta_mesmo_raio",
            persist_state="session",
        )
        raio_y_mm = raio_x_mm
        if not mesmo_raio:
            raio_y_mm = st.number_input(
                "Raio de giração ry (mm)",
                min_value=0.001,
                value=raio_x_mm,
                step=1.0,
                key="flambagem_direta_ry",
                persist_state="session",
            )
        geometria = flambagem.geometria_direta(area_mm2, raio_x_mm, raio_y_mm)

    st.caption(f":material/info: {geometria.descricao}")

with st.container(border=True):
    st.subheader("2. Comprimento e condições de apoio")
    comprimento_mm = st.number_input(
        "Comprimento real da coluna L (mm)",
        min_value=0.001,
        step=100.0,
        key="flambagem_comprimento_mm",
        persist_state="session",
    )
    apoio = st.selectbox(
        "Condição de apoio idealizada",
        list(flambagem.CONDICOES_APOIO),
        key="flambagem_condicao_apoio",
        persist_state="session",
    )
    k_padrao = flambagem.CONDICOES_APOIO[apoio]
    st.caption(
        f"Fator de comprimento efetivo teórico K = {k_padrao:.2f}. Ligações "
        "reais raramente são um engaste ou um pino perfeitos — valores de "
        "norma (ex.: AISC/NBR) costumam recomendar K maior que o teórico."
    )
    contraventamento_assimetrico = st.checkbox(
        "Contraventamento diferente em cada eixo (Kx ≠ Ky)",
        value=False,
        help=(
            "Use quando a coluna é travada lateralmente em um eixo (reduzindo "
            "o comprimento destravado) e livre no outro."
        ),
        key="flambagem_kx_ky_diferentes",
        persist_state="session",
    )
    if contraventamento_assimetrico:
        colunas_k = st.columns(2)
        kx = colunas_k[0].number_input(
            "Kx (eixo x)",
            min_value=0.01,
            value=k_padrao,
            step=0.05,
            key="flambagem_kx",
            persist_state="session",
        )
        ky = colunas_k[1].number_input(
            "Ky (eixo y)",
            min_value=0.01,
            value=k_padrao,
            step=0.05,
            key="flambagem_ky",
            persist_state="session",
        )
    else:
        kx = ky = k_padrao

with st.container(border=True):
    st.subheader("3. Material e carga de compressão")

    try:
        nomes_materiais = mat.listar_nomes()
    except (FileNotFoundError, ValueError) as erro:
        st.error(f"Não foi possível carregar a base de materiais: {erro}")
        st.stop()

    projeto_ativo = obter_projeto_ativo()
    materiais_projeto = (projeto_ativo or {}).get("materiais_projeto", [])
    opcoes_materiais = {"manual": "— entrada manual —"}
    for item in materiais_projeto:
        opcoes_materiais[f"projeto::{item['id']}"] = (
            f"Projeto · {item.get('nome')} · {avaliar_material(item)['nivel']}"
        )
    for nome in nomes_materiais:
        opcoes_materiais[f"catalogo::{nome}"] = f"Catálogo orientativo · {nome}"
    if st.session_state.get("flambagem_material_escolha") not in opcoes_materiais:
        st.session_state["flambagem_material_escolha"] = "manual"
    escolha_id = st.selectbox(
        "Material de referência (opcional, só para Sy)",
        list(opcoes_materiais),
        format_func=lambda valor: opcoes_materiais[valor],
        key="flambagem_material_escolha",
        persist_state="session",
    )
    material_id = None
    dados_material = None
    if escolha_id.startswith("projeto::"):
        material_id = escolha_id.split("::", 1)[1]
        material_projeto = next(
            item for item in materiais_projeto if item["id"] == material_id
        )
        props = material_projeto.get("propriedades", {})
        dados_material = {
            "Sy_MPa": props.get("Sy_MPa") or 0.0,
            "observacao": resumir_fonte(material_projeto),
        }
    elif escolha_id.startswith("catalogo::"):
        nome_catalogo = escolha_id.split("::", 1)[1]
        dados_material = mat.obter_material(nome_catalogo)
    sy_padrao = (
        float(dados_material["Sy_MPa"])
        if dados_material and dados_material.get("Sy_MPa")
        else 250.0
    )

    colunas_material = st.columns(3)
    modulo_elasticidade_MPa = colunas_material[0].number_input(
        "Módulo de elasticidade E (MPa)",
        min_value=0.001,
        step=1_000.0,
        key="flambagem_E_MPa",
        persist_state="session",
    )
    escoamento_MPa = colunas_material[1].number_input(
        "Limite de escoamento Sy (MPa)",
        min_value=0.001,
        value=sy_padrao,
        step=10.0,
        key=f"flambagem_Sy_{escolha_id}",
        persist_state="session",
    )
    fator_seguranca_desejado = colunas_material[2].number_input(
        "Fator de segurança desejado",
        min_value=1.01,
        step=0.1,
        key="flambagem_fs_desejado",
        persist_state="session",
    )
    if dados_material:
        st.caption(
            f"Sy de referência: {sy_padrao:.0f} MPa — "
            f"{dados_material.get('observacao', 'catálogo orientativo')}."
        )

    forca_kN = st.number_input(
        "Força de compressão atuante P (kN)",
        min_value=0.0,
        step=5.0,
        key="flambagem_forca_kN",
        persist_state="session",
        help="Informe apenas a magnitude; este módulo trata sempre compressão.",
    )

try:
    resultado = flambagem.verificar_flambagem(
        geometria=geometria,
        comprimento_mm=comprimento_mm,
        kx=kx,
        ky=ky,
        modulo_elasticidade_MPa=modulo_elasticidade_MPa,
        escoamento_MPa=escoamento_MPa,
        forca_solicitante_N=forca_kN * 1_000.0,
        fator_seguranca_desejado=fator_seguranca_desejado,
    )
except ValueError as erro:
    st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
    st.stop()

st.header("Resultados")

with st.container(border=True):
    st.subheader("Esbeltez")
    with st.container(horizontal=True):
        st.metric("λx = KxL/rx", f"{resultado.esbeltez_x:.1f}", border=True)
        st.metric("λy = KyL/ry", f"{resultado.esbeltez_y:.1f}", border=True)
        st.metric(
            f"λ governante (eixo {resultado.eixo_governante})",
            f"{resultado.esbeltez_governante:.1f}",
            border=True,
        )
        st.metric(
            "λ de transição (Euler↔Johnson)",
            f"{resultado.esbeltez_transicao:.1f}",
            border=True,
        )
    st.latex(r"\lambda=\frac{KL}{r},\qquad \lambda_{transicao}=\pi\sqrt{\frac{2E}{S_y}}")
    st.caption(
        f"Regime governante: **{resultado.regime}** "
        f"(flambagem em torno do eixo {resultado.eixo_governante})."
    )

with st.container(border=True):
    st.subheader("Carga crítica")
    with st.container(horizontal=True):
        st.metric(
            "Carga crítica de Euler (referência)",
            f"{resultado.carga_critica_euler_N / 1_000.0:.2f} kN",
            border=True,
            help="π²EI/(KL)², calculada sempre, mesmo quando Johnson governa.",
        )
        st.metric(
            "Carga crítica governante",
            f"{resultado.carga_critica_N / 1_000.0:.2f} kN",
            border=True,
        )
        st.metric(
            "Carga admissível",
            f"{resultado.carga_admissivel_N / 1_000.0:.2f} kN",
            border=True,
            help=f"Crítica ÷ fator de segurança desejado ({fator_seguranca_desejado:.2f}).",
        )
        st.metric(
            "Fator de segurança real",
            "∞" if math.isinf(resultado.fator_seguranca) else f"{resultado.fator_seguranca:.2f}",
            border=True,
        )
    st.latex(
        r"P_{cr,Euler}=\frac{\pi^2 EI}{(KL)^2},\qquad "
        r"\sigma_{cr,Johnson}=S_y-\left(\frac{S_y}{2\pi}\right)^2\frac{\lambda^2}{E}"
    )

if resultado.utilizacao > 1.0:
    st.error(
        f"A carga atuante ({forca_kN:.1f} kN) excede a carga admissível "
        f"({resultado.carga_admissivel_N / 1_000.0:.2f} kN). Reforce a seção, "
        "reduza o comprimento destravado ou revise o apoio.",
        icon=":material/error:",
    )
elif resultado.utilizacao > 0.8:
    st.warning(
        f"Utilização de {resultado.utilizacao * 100:.0f}% da carga admissível "
        "— margem pequena frente às incertezas do modelo.",
        icon=":material/warning:",
    )
else:
    st.success(
        f"Utilização de {resultado.utilizacao * 100:.0f}% da carga admissível.",
        icon=":material/check_circle:",
    )

fronteira_modelo(
    [
        "Flambagem local da parede (perfis de parede fina) e flambagem torcional ou flexo-torcional.",
        "Imperfeições geométricas iniciais, excentricidade de carga e efeitos de segunda ordem (P–δ).",
        "Cargas dinâmicas, de impacto ou variáveis no tempo (fadiga da própria coluna).",
        "Ligações reais nas extremidades — o fator K aqui é o valor teórico do caso idealizado escolhido.",
    ]
)

with st.container(border=True):
    st.subheader("Registrar no projeto")
    status_registro = (
        "Não atende" if resultado.utilizacao > 1.0
        else "Atenção" if resultado.utilizacao > 0.8
        else "Atende"
    )
    conclusao_registro = (
        f"Carga admissível = {resultado.carga_admissivel_N / 1_000.0:.2f} kN; "
        f"atuante = {forca_kN:.2f} kN; utilização = {resultado.utilizacao * 100:.0f}%; "
        f"regime = {resultado.regime}."
    )

    st.markdown("**Comparar cenários**")
    comparador_cenarios(
        escopo="flambagem_colunas",
        resumo_entradas={
            "Seção": tipo_secao,
            "L (mm)": round(comprimento_mm, 0),
            "K": round(k_padrao, 2),
        },
        metricas={
            "λ governante": f"{resultado.esbeltez_governante:.1f}",
            "Regime": resultado.regime.split(" ")[0],
            "Pcr (kN)": f"{resultado.carga_critica_N / 1_000.0:.2f}",
            "FS": "∞" if math.isinf(resultado.fator_seguranca) else f"{resultado.fator_seguranca:.2f}",
        },
    )

    registro_flambagem = construir_registro_tecnico(
        modulo="Flambagem de colunas",
        modulo_id="flambagem_colunas",
        titulo=f"Flambagem de coluna — {geometria.descricao}",
        status=status_registro,
        resumo=(
            f"Verificação de flambagem por Euler/Johnson: {resultado.regime}, "
            f"eixo governante {resultado.eixo_governante}."
        ),
        entradas={
            "secao": geometria.descricao,
            "area_mm2": geometria.area_mm2,
            "raio_giracao_x_mm": geometria.raio_giracao_x_mm,
            "raio_giracao_y_mm": geometria.raio_giracao_y_mm,
            "comprimento_mm": comprimento_mm,
            "condicao_apoio": apoio,
            "kx": kx,
            "ky": ky,
            "modulo_elasticidade_MPa": modulo_elasticidade_MPa,
            "escoamento_MPa": escoamento_MPa,
            "forca_solicitante_kN": forca_kN,
            "fator_seguranca_desejado": fator_seguranca_desejado,
        },
        resultados={
            "esbeltez_x": resultado.esbeltez_x,
            "esbeltez_y": resultado.esbeltez_y,
            "esbeltez_governante": resultado.esbeltez_governante,
            "eixo_governante": resultado.eixo_governante,
            "esbeltez_transicao": resultado.esbeltez_transicao,
            "regime": resultado.regime,
            "carga_critica_euler_kN": resultado.carga_critica_euler_N / 1_000.0,
            "carga_critica_kN": resultado.carga_critica_N / 1_000.0,
            "carga_admissivel_kN": resultado.carga_admissivel_N / 1_000.0,
            "fator_seguranca": (
                None if math.isinf(resultado.fator_seguranca) else resultado.fator_seguranca
            ),
            "utilizacao": resultado.utilizacao,
        },
        metodo=(
            "Euler para colunas longas (λ ≥ λ_transição) com transição parabólica "
            "de Johnson para colunas curtas/intermediárias; eixo governante é o "
            "de maior esbeltez."
        ),
        premissas=[
            "Compressão centrada, coluna prismática e material elástico linear até a transição.",
            "K é o valor teórico da condição de apoio idealizada escolhida.",
        ],
        alertas=[] if status_registro == "Atende" else [conclusao_registro],
        referencias=[
            "Shigley — Mechanical Engineering Design (Euler/Johnson).",
            "Confirmar comprimento destravado real, K de norma e imperfeições do projeto.",
        ],
        conclusao=conclusao_registro,
        materiais_ids=[material_id] if material_id else [],
    )
    botao_registrar_calculo(
        registro_flambagem,
        key="registrar_flambagem_colunas",
        rotulo="Registrar verificação de flambagem no projeto ativo",
    )

with st.container(border=True):
    st.subheader("Precisa de ajuda para preencher ou interpretar?")
    st.markdown(
        "O **Guia geral** mostra como escolher K, quando Euler deixa de valer "
        "e um exemplo completo de coluna curta e longa."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir o guia de flambagem",
        icon=":material/help:",
        query_params={"modulo": "Flambagem de colunas"},
        width="stretch",
    )
st.caption(
    "Modelo elementar de Euler/Johnson. Para peças de aço estrutural conforme "
    "norma, use Estruturas de aço; para colunas críticas, valide K com a "
    "condição real de apoio e considere imperfeições e efeitos de 2ª ordem."
)
