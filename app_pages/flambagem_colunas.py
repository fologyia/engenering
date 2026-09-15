import math

import pandas as pd
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
    "NBR 8800:2008 • N_c,Rd = χ·Q·A_g·f_y/γ_a1 • Anexos D, E e F • interação N + M",
    categoria="Análises",
    icone=":material/architecture:",
    cor="blue",
    ajuda_modulo="Flambagem de colunas",
    acoes=(("app_pages/assistente_cargas.py", "Assistente de cargas", ":material/manufacturing:"),),
    modulo_id="flambagem_colunas",
)
st.caption(
    "Verificação de barra comprimida ou flexocomprimida pelo **método dos "
    "estados-limites da ABNT NBR 8800:2008**: ações majoradas por γ_f, "
    "resistência minorada por γ_a1 = 1,10, curva de flambagem χ (imperfeições e "
    "tensões residuais), fator Q de flambagem local, flambagem por torção e "
    "flexo-torção (N_ez) e equação de interação com momentos amplificados por B_1."
)
st.session_state.setdefault("flambagem_comprimento_mm", 2_000.0)
st.session_state.setdefault("flambagem_E_MPa", 200_000.0)

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
    soldado = False

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
        colunas = st.columns([3, 1])
        nome_perfil = colunas[0].selectbox(
            "Perfil",
            list(catalogo_perfis.listar_perfis()),
            key="flambagem_perfil_catalogo",
            persist_state="session",
        )
        soldado = colunas[1].toggle(
            "Perfil soldado",
            value=False,
            key="flambagem_soldado",
            persist_state="session",
            help="Muda o grupo da mesa no Anexo F (k_c) e a tensão residual da FLT.",
        )
        perfil = catalogo_perfis.obter_perfil(nome_perfil)
        geometria = flambagem.geometria_perfil_catalogo(perfil)
        with st.container(horizontal=True):
            st.metric("Área", f"{perfil.area_mm2:.0f} mm²", border=True)
            st.metric("rx", f"{perfil.rx_mm:.1f} mm", border=True)
            st.metric("ry", f"{perfil.ry_mm:.1f} mm", border=True)
            st.metric("J", f"{perfil.j_mm4 / 1e3:.1f} ×10³ mm⁴", border=True)

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
        colunas_fibra = st.columns(2)
        fibra_x_mm = colunas_fibra[0].number_input(
            "c em x — centroide à fibra extrema (mm, só para flexocompressão)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="flambagem_direta_cx",
            persist_state="session",
            help="Meia altura numa seção simétrica. Zero = não informado.",
        )
        fibra_y_mm = colunas_fibra[1].number_input(
            "c em y — centroide à fibra extrema (mm, só para flexocompressão)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="flambagem_direta_cy",
            persist_state="session",
            help="Meia largura numa seção simétrica. Zero = não informado.",
        )
        geometria = flambagem.geometria_direta(
            area_mm2,
            raio_x_mm,
            raio_y_mm,
            distancia_fibra_x_mm=fibra_x_mm,
            distancia_fibra_y_mm=fibra_y_mm,
        )
        st.info(
            "Sem as paredes e as constantes de torção da seção, a norma não pode ser "
            "aplicada por completo: Q = 1,0 e só flambagem por flexão. Prefira uma "
            "seção geométrica ou o perfil de catálogo.",
            icon=":material/info:",
        )

    st.caption(f":material/info: {geometria.descricao}")


with st.container(border=True):
    st.subheader("2. Eixo analisado, comprimento destravado e apoio")
    comprimento_mm = st.number_input(
        "Comprimento real da coluna L (mm)",
        min_value=0.001,
        step=100.0,
        key="flambagem_comprimento_mm",
        persist_state="session",
        help="Altura total da coluna. Serve de padrão para o comprimento destravado de cada eixo e de braço para a mão-francesa.",
    )
    eixo = st.segmented_control(
        "Eixo analisado nesta verificação",
        ["x", "y"],
        format_func=lambda valor: (
            f"Eixo {valor}-{valor}" + (" (frontal, forte)" if valor == "x" else " (lateral, fraco)")
        ),
        default="x",
        required=True,
        width="stretch",
        key="flambagem_eixo_analisado",
        persist_state="session",
        help=(
            "Cada eixo é uma verificação própria, com o comprimento destravado e o K "
            "daquele plano — por exemplo, x-x do piso ao nó da mão-francesa e y-y com o "
            "contraventamento lateral. Registre uma verificação para cada eixo; o "
            "pior dos dois governa a coluna."
        ),
    )
    outro_eixo = "y" if eixo == "x" else "x"
    rotulo_eixo = f"{eixo}-{eixo}"
    if st.session_state.get(f"flambagem_L_{eixo}") is None:
        st.session_state[f"flambagem_L_{eixo}"] = float(comprimento_mm)
    colunas_eixo = st.columns([2, 3])
    comprimento_eixo_mm = colunas_eixo[0].number_input(
        f"Comprimento destravado L{eixo} (mm)",
        min_value=0.001,
        step=100.0,
        key=f"flambagem_L_{eixo}",
        persist_state="session",
        help=(
            f"Distância entre os pontos que impedem a flexão em torno de {rotulo_eixo}. "
            "No plano da mão-francesa costuma ser do piso ao nó; no plano do "
            "contraventamento, entre os travamentos laterais."
        ),
    )
    apoio = colunas_eixo[1].selectbox(
        f"Condição de apoio no plano de {rotulo_eixo} (Tabela E.1)",
        list(flambagem.CONDICOES_APOIO),
        key=f"flambagem_condicao_apoio_{eixo}",
        persist_state="session",
    )
    k_teorico = flambagem.CONDICOES_APOIO[apoio]
    k_recomendado = flambagem.CONDICOES_APOIO_RECOMENDADAS[apoio]
    usar_recomendado = st.toggle(
        f"Usar o K recomendado para projeto ({k_recomendado:.2f}) em vez do teórico ({k_teorico:.2f})",
        value=True,
        key=f"flambagem_k_recomendado_{eixo}",
        persist_state="session",
        help=(
            "Ligações reais nunca são um engaste ou um pino perfeitos. A Tabela E.1 "
            "da NBR 8800 recomenda K maior que o teórico nos casos com engaste: "
            "0,65 em vez de 0,50, 0,80 em vez de 0,70, 2,1 em vez de 2,0."
        ),
    )
    k_padrao = k_recomendado if usar_recomendado else k_teorico
    colunas_k = st.columns([1, 1, 2])
    k_manual = colunas_k[0].checkbox(
        f"Informar K{eixo} manualmente",
        value=False,
        key=f"flambagem_k_manual_{eixo}",
        persist_state="session",
    )
    if k_manual:
        k_eixo = colunas_k[1].number_input(
            f"K{eixo}",
            min_value=0.01,
            value=k_padrao,
            step=0.05,
            key=f"flambagem_k_valor_{eixo}",
            persist_state="session",
        )
    else:
        k_eixo = k_padrao
    torcao_travada = colunas_k[2].checkbox(
        "Torção com travamento próprio (informar Kz)",
        value=False,
        key=f"flambagem_kz_manual_{eixo}",
        persist_state="session",
        help=f"Comprimento de flambagem por torção K_z·L{eixo} (Anexo E). Sem travamento próprio, vale o mesmo K{eixo}·L{eixo}.",
    )
    kz = None
    if torcao_travada:
        kz = st.number_input(
            "Kz (torção)",
            min_value=0.01,
            value=k_eixo,
            step=0.05,
            key=f"flambagem_kz_valor_{eixo}",
            persist_state="session",
        )
    st.caption(
        f"Eixo {rotulo_eixo}: K{eixo}·L{eixo} = {k_eixo:.2f} × {comprimento_eixo_mm:.0f} = "
        f"**{k_eixo * comprimento_eixo_mm:.0f} mm** "
        f"({'K recomendado para projeto' if usar_recomendado and not k_manual else 'K teórico' if not k_manual else 'K informado'})."
    )
    resumo_outro = st.session_state.get(f"flambagem_resumo_{outro_eixo}")
    if resumo_outro:
        st.info(
            f"Eixo {outro_eixo}-{outro_eixo} (última análise nesta sessão): "
            f"L{outro_eixo} = {resumo_outro['comprimento_mm']:.0f} mm, K{outro_eixo} = {resumo_outro['k']:.2f}, "
            f"λ = {resumo_outro['esbeltez']:.1f}, N_c,Rd = {resumo_outro['resistencia_kN']:.2f} kN, "
            f"utilização = {resumo_outro['utilizacao']}. Lembre de registrar os dois eixos.",
            icon=":material/swap_horiz:",
        )
with st.container(border=True):
    st.subheader("3. Material")

    try:
        nomes_materiais = mat.listar_nomes()
    except (FileNotFoundError, ValueError) as erro:
        st.error(f"Não foi possível carregar a base de materiais: {erro}", icon=":material/error:")
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
        "Material de referência (opcional, só para f_y)",
        list(opcoes_materiais),
        format_func=lambda valor: opcoes_materiais[valor],
        key="flambagem_material_escolha",
        persist_state="session",
    )
    material_id = None
    dados_material = None
    if escolha_id.startswith("projeto::"):
        material_id = escolha_id.split("::", 1)[1]
        material_projeto = next(item for item in materiais_projeto if item["id"] == material_id)
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
        help="NBR 8800 4.5.2.9: E = 200 000 MPa e G = 77 000 MPa para o aço.",
    )
    escoamento_MPa = colunas_material[1].number_input(
        "Resistência ao escoamento f_y (MPa)",
        min_value=0.001,
        value=sy_padrao,
        step=10.0,
        key=f"flambagem_Sy_{escolha_id}",
        persist_state="session",
    )
    modulo_cisalhamento_MPa = colunas_material[2].number_input(
        "Módulo de cisalhamento G (MPa)",
        min_value=0.001,
        value=77_000.0,
        step=1_000.0,
        key="flambagem_G_MPa",
        persist_state="session",
        help="Entra em N_ez (flambagem por torção, Anexo E) e na FLT.",
    )
    if dados_material:
        st.caption(
            f"f_y de referência: {sy_padrao:.0f} MPa — "
            f"{dados_material.get('observacao', 'catálogo orientativo')}."
        )

with st.container(border=True):
    st.subheader("4. Esforços solicitantes de cálculo")
    modo_carga = st.radio(
        "Como informar a força de compressão",
        [
            "Cargas características majoradas aqui (γ_g·N_g + γ_q·N_q)",
            "N_Sd já de cálculo (vindo das combinações)",
        ],
        key="flambagem_modo_carga",
        persist_state="session",
        horizontal=True,
    )
    if modo_carga.startswith("Cargas"):
        colunas_g = st.columns([2, 2])
        permanente_kN = colunas_g[0].number_input(
            "Permanente N_g (kN)",
            min_value=0.0,
            value=30.0,
            step=5.0,
            key="flambagem_ng_kN",
            persist_state="session",
        )
        categoria_g = colunas_g[1].selectbox(
            "Categoria da permanente (Tabela 1)",
            list(flambagem.COEFICIENTES_PERMANENTE),
            index=2,
            key="flambagem_categoria_g",
            persist_state="session",
        )
        colunas_q = st.columns([2, 2])
        variavel_kN = colunas_q[0].number_input(
            "Variável N_q (kN)",
            min_value=0.0,
            value=20.0,
            step=5.0,
            key="flambagem_nq_kN",
            persist_state="session",
        )
        categoria_q = colunas_q[1].selectbox(
            "Categoria da variável (Tabela 1)",
            list(flambagem.COEFICIENTES_VARIAVEL),
            index=1,
            key="flambagem_categoria_q",
            persist_state="session",
        )
        gamma_g = flambagem.COEFICIENTES_PERMANENTE[categoria_g]
        gamma_q = flambagem.COEFICIENTES_VARIAVEL[categoria_q]
        forca_sd_kN = (
            flambagem.forca_de_calculo(
                permanente_kN * 1e3, variavel_kN * 1e3, gamma_g=gamma_g, gamma_q=gamma_q
            )
            / 1e3
        )
        st.caption(
            f"N_Sd = {gamma_g:.2f} × {permanente_kN:.1f} + {gamma_q:.2f} × {variavel_kN:.1f} "
            f"= **{forca_sd_kN:.2f} kN**. Para mais de duas ações, ou combinações com ψ, "
            "use Casos de carga."
        )
    else:
        gamma_g = gamma_q = None
        permanente_kN = variavel_kN = None
        forca_sd_kN = st.number_input(
            "Força de compressão de cálculo N_Sd (kN)",
            min_value=0.0,
            value=70.0,
            step=5.0,
            key="flambagem_nsd_kN",
            persist_state="session",
            help="Já majorada pelos γ_f das combinações (NBR 8681 / NBR 8800 4.7).",
        )

    st.markdown(
        f"**Flexocompressão no eixo {rotulo_eixo}** (5.5.1.2) — excentricidade e/ou momento de cálculo"
    )
    colunas_exc = st.columns([2, 2, 1])
    excentricidade_mm = colunas_exc[0].number_input(
        f"Excentricidade e da força no eixo {rotulo_eixo} (mm)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key=f"flambagem_excentricidade_{eixo}",
        persist_state="session",
        help=(
            "Distância entre a linha de ação da força e o centroide, medida no plano "
            f"que flete {rotulo_eixo}. Gera M_Sd = N_Sd·e, amplificado por B_1 (Anexo D) "
            "e levado à equação de interação."
        ),
    )
    momento_kNm = colunas_exc[1].number_input(
        f"M_{eixo},Sd (kN·m)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key=f"flambagem_momento_{eixo}",
        persist_state="session",
        help=f"Momento de cálculo de 1ª ordem em torno de {rotulo_eixo}, além do que a mão-francesa gera abaixo.",
    )
    cm = colunas_exc[2].number_input(
        "C_m",
        min_value=0.2,
        max_value=1.0,
        value=1.0,
        step=0.05,
        key=f"flambagem_cm_{eixo}",
        persist_state="session",
        help="Coeficiente de equivalência de momentos (D.2.2): 1,0 é conservador; 0,6 − 0,4·M1/M2 sem cargas transversais.",
    )
    comprimento_destravado_mm = 0.0
    cb = 1.0
    if eixo == "x":
        colunas_flt = st.columns(2)
        comprimento_destravado_mm = colunas_flt[0].number_input(
            "L_b para FLT (mm, 0 = igual a Lx)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            key="flambagem_lb_mm",
            persist_state="session",
            help="Comprimento destravado lateralmente da mesa comprimida, só para M_x,Rd de perfis abertos.",
        )
        cb = colunas_flt[1].number_input(
            "C_b",
            min_value=1.0,
            max_value=3.0,
            value=1.0,
            step=0.05,
            key="flambagem_cb",
            persist_state="session",
        )

with st.container(border=True):
    st.subheader("5. Mão-francesa (força inclinada chegando na coluna)")
    st.caption(
        "A mão-francesa descarrega na coluna uma força inclinada: a componente "
        "horizontal H flete a coluna (M = H × braço) e a vertical V comprime. "
        "O momento calculado aqui é somado a M_Sd do eixo que ela flete e entra na "
        "interação N + M — sem isto o campo fica em zero e a flexão da mão-francesa é ignorada."
    )
    incluir_mao_francesa = st.toggle(
        "Incluir a mão-francesa nesta verificação",
        value=False,
        key="flambagem_mf_incluir",
        persist_state="session",
    )
    esforcos_mf = None
    somar_v_mf = False
    forca_mf_kN = angulo_mf = altura_mf_mm = None
    vinculo_mf = eixo_mf = None
    gamma_mf = excentricidade_mf_mm = None
    if incluir_mao_francesa:
        colunas_mf = st.columns(4)
        forca_mf_kN = colunas_mf[0].number_input(
            "Força na mão-francesa F (kN)",
            min_value=0.0,
            value=20.0,
            step=1.0,
            key="flambagem_mf_forca_kN",
            persist_state="session",
            help="Força axial na barra da mão-francesa (compressão ou tração), vinda da reação da viga ou do console que ela suporta.",
        )
        opcoes_gamma_mf = {"Já é de cálculo (γ = 1,00)": 1.0, **flambagem.COEFICIENTES_VARIAVEL}
        rotulo_gamma_mf = colunas_mf[1].selectbox(
            "Majoração de F",
            list(opcoes_gamma_mf),
            index=2,
            key="flambagem_mf_gamma",
            persist_state="session",
            help="Se F veio das combinações já majorada, escolha γ = 1,00.",
        )
        gamma_mf = opcoes_gamma_mf[rotulo_gamma_mf]
        angulo_mf = colunas_mf[2].number_input(
            "Ângulo θ com a coluna (°)",
            min_value=1.0,
            max_value=89.0,
            value=45.0,
            step=5.0,
            key="flambagem_mf_angulo",
            persist_state="session",
            help="Ângulo entre a barra da mão-francesa e o eixo da coluna: 45° é o usual. H = F·sen θ e V = F·cos θ.",
        )
        altura_mf_mm = colunas_mf[3].number_input(
            "Altura do nó a (mm, medida da base)",
            min_value=1.0,
            max_value=float(comprimento_mm),
            value=float(min(comprimento_mm, 800.0)),
            step=50.0,
            key="flambagem_mf_altura_mm",
            persist_state="session",
            help="Distância da base da coluna ao ponto onde a mão-francesa é ligada — o braço da componente horizontal.",
        )
        colunas_mf2 = st.columns([2, 1, 1, 1])
        vinculo_mf = colunas_mf2[0].selectbox(
            "Vínculo da coluna no plano da mão-francesa",
            list(flambagem.VINCULOS_MAO_FRANCESA),
            key="flambagem_mf_vinculo",
            persist_state="session",
            help="Define como H vira momento: engaste na base (M = H·a), pino-pino (M = H·a·(L−a)/L) ou engaste com topo apoiado.",
        )
        eixo_mf = colunas_mf2[1].selectbox(
            "Eixo que ela flete",
            ["x", "y"],
            key="flambagem_mf_eixo",
            persist_state="session",
            help="Mão-francesa no plano da alma flete o eixo forte x-x.",
        )
        excentricidade_mf_mm = colunas_mf2[2].number_input(
            "e da ligação (mm)",
            min_value=0.0,
            value=float(round(geometria.distancia_fibra(eixo_mf), 1)),
            step=1.0,
            key=f"flambagem_mf_e_{eixo_mf}",
            persist_state="session",
            help="Distância do eixo da coluna à face onde a mão-francesa chega (meia altura do perfil, por padrão): V·e é somado ao momento. Zero se a força passa pelo eixo.",
        )
        somar_v_mf = colunas_mf2[3].checkbox(
            "Somar V a N_Sd",
            value=False,
            key="flambagem_mf_somar_v",
            persist_state="session",
            help="Marque só se N_Sd acima ainda não inclui a reação vertical que a mão-francesa traz para a coluna.",
        )
        try:
            esforcos_mf = flambagem.esforcos_mao_francesa(
                forca_mf_kN * 1e3 * gamma_mf,
                angulo_mf,
                altura_mf_mm,
                comprimento_mm,
                vinculo_mf,
                excentricidade_mf_mm,
            )
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()
        with st.container(horizontal=True):
            st.metric(
                "F_Sd",
                f"{esforcos_mf.forca_N / 1e3:.2f} kN",
                border=True,
                help=f"F × γ = {forca_mf_kN:.2f} × {gamma_mf:.2f}",
            )
            st.metric(
                "H = F·sen θ", f"{esforcos_mf.componente_horizontal_N / 1e3:.2f} kN", border=True
            )
            st.metric(
                "V = F·cos θ", f"{esforcos_mf.componente_vertical_N / 1e3:.2f} kN", border=True
            )
            st.metric(
                f"M_{eixo_mf},Sd da mão-francesa",
                f"{esforcos_mf.momento_Nmm / 1e6:.3f} kN·m",
                border=True,
                help=esforcos_mf.expressao,
            )
        st.caption(
            f"{esforcos_mf.expressao}: H = {esforcos_mf.componente_horizontal_N / 1e3:.2f} kN, "
            f"a = {esforcos_mf.altura_no_mm:.0f} mm, L = {comprimento_mm:.0f} mm → "
            f"M_H = {esforcos_mf.momento_horizontal_Nmm / 1e6:.3f} kN·m"
            + (
                f"; V·e = {esforcos_mf.componente_vertical_N / 1e3:.2f} × {esforcos_mf.excentricidade_mm:.1f} mm "
                f"= {esforcos_mf.momento_excentricidade_Nmm / 1e6:.3f} kN·m"
                if esforcos_mf.momento_excentricidade_Nmm > 0
                else ""
            )
            + "."
        )
        if eixo_mf == eixo:
            st.caption(f"Este momento é somado a M_{eixo},Sd na verificação do eixo {rotulo_eixo}.")
        else:
            st.info(
                f"A mão-francesa flete o eixo {eixo_mf}-{eixo_mf}; nesta verificação do eixo "
                f"{rotulo_eixo} o momento dela não entra"
                + (" — só a componente V somada a N_Sd." if somar_v_mf else "."),
                icon=":material/info:",
            )

momento_total_kNm = momento_kNm
forca_sd_total_kN = forca_sd_kN
momento_mf_no_eixo_kNm = 0.0
if esforcos_mf is not None:
    if eixo_mf == eixo:
        momento_mf_no_eixo_kNm = esforcos_mf.momento_Nmm / 1e6
        momento_total_kNm += momento_mf_no_eixo_kNm
    if somar_v_mf:
        forca_sd_total_kN += esforcos_mf.componente_vertical_N / 1e3

try:
    resultado = flambagem.verificar_flambagem_eixo(
        eixo=eixo,
        geometria=geometria,
        comprimento_mm=comprimento_eixo_mm,
        k=k_eixo,
        kz=kz,
        modulo_elasticidade_MPa=modulo_elasticidade_MPa,
        modulo_cisalhamento_MPa=modulo_cisalhamento_MPa,
        escoamento_MPa=escoamento_MPa,
        forca_solicitante_N=forca_sd_total_kN * 1e3,
        momento_Nmm=momento_total_kNm * 1e6,
        excentricidade_mm=excentricidade_mm,
        cm=cm,
        comprimento_destravado_mm=(
            comprimento_destravado_mm if comprimento_destravado_mm > 0 else comprimento_eixo_mm
        ),
        cb=cb,
        soldado=soldado,
    )
except ValueError as erro:
    st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
    st.stop()

utilizacao_texto = "∞" if math.isinf(resultado.utilizacao) else f"{resultado.utilizacao * 100:.0f}%"
st.session_state[f"flambagem_resumo_{eixo}"] = {
    "comprimento_mm": comprimento_eixo_mm,
    "k": k_eixo,
    "esbeltez": resultado.esbeltez,
    "resistencia_kN": resultado.resistencia_N / 1e3,
    "utilizacao": utilizacao_texto,
}

st.header(f"Resultados — eixo {rotulo_eixo}")

for aviso in resultado.avisos:
    st.warning(aviso, icon=":material/warning:")


def _fmt(valor: float | None, casas: int = 3, sufixo: str = "") -> str:
    if valor is None:
        return "—"
    if math.isinf(valor):
        return "∞"
    return f"{valor:.{casas}f}{sufixo}"


with st.container(border=True):
    st.subheader(f"Esbeltez e flambagem elástica no eixo {rotulo_eixo} (Anexo E)")
    with st.container(horizontal=True):
        st.metric(
            f"K{eixo}·L{eixo}",
            f"{resultado.comprimento_efetivo_mm:.0f} mm",
            border=True,
            help=f"{resultado.fator_k:.2f} × {resultado.comprimento_mm:.0f} mm",
        )
        st.metric(f"r{eixo}", f"{resultado.raio_giracao_mm:.1f} mm", border=True)
        st.metric(
            f"λ{eixo} = K{eixo}L{eixo}/r{eixo}",
            f"{resultado.esbeltez:.1f}",
            border=True,
            help=f"Limite 5.3.4.1: KL/r ≤ {flambagem.ESBELTEZ_MAXIMA:.0f}.",
        )
    with st.container(horizontal=True):
        st.metric(
            f"N_e{eixo} (flexão)",
            f"{resultado.ne_flexao_N / 1e3:.1f} kN",
            border=True,
            help=f"π²·E·I{eixo}/(K{eixo}L{eixo})²",
        )
        st.metric(
            "N_ez (torção)",
            "—" if resultado.ne_z_N is None else f"{resultado.ne_z_N / 1e3:.1f} kN",
            border=True,
            help=(
                "Seções maciças e tubos circulares: torção não governa (J alto, Cw ≈ 0)."
                if resultado.ne_z_N is None
                else f"Com K_z·L = {resultado.comprimento_efetivo_z_mm:.0f} mm."
            ),
        )
        if resultado.ne_acoplada_N is not None:
            st.metric(
                "N_e flexo-torção",
                f"{resultado.ne_acoplada_N / 1e3:.1f} kN",
                border=True,
                help="Modo acoplado das seções monossimétricas (E.1.2).",
            )
        st.metric(
            f"N_e adotado (modo {resultado.modo_flambagem})",
            f"{resultado.ne_N / 1e3:.1f} kN",
            border=True,
        )
    st.latex(
        rf"N_{{e{eixo}}}=\frac{{\pi^2 E I_{eixo}}}{{(K_{eixo}L_{eixo})^2}},\qquad "
        r"N_{ez}=\frac{1}{r_0^2}\left[\frac{\pi^2 E C_w}{(K_zL_z)^2}+GJ\right]"
    )

with st.container(border=True):
    st.subheader("Flambagem local (Anexo F) e curva de flambagem (5.3.3)")
    with st.container(horizontal=True):
        st.metric(
            "Q = Q_s·Q_a",
            f"{resultado.fator_q:.3f}",
            border=True,
            help="1,0 quando nenhuma parede passa de λ_r.",
        )
        st.metric("λ_0", f"{resultado.lambda_0:.3f}", border=True, help="λ_0 = √(Q·A_g·f_y / N_e)")
        st.metric(
            "χ",
            f"{resultado.chi:.3f}",
            border=True,
            help="0,658^(λ_0²) para λ_0 ≤ 1,5; 0,877/λ_0² acima.",
        )
        st.metric("Q·A_g·f_y", f"{resultado.forca_escoamento_N / 1e3:.1f} kN", border=True)
    if resultado.elementos:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Elemento": item.nome,
                        "Tipo": item.tipo,
                        "b/t": round(item.razao, 1),
                        "λ_r": round(item.limite_r, 1),
                        "Grupo (Tab. F.1)": item.grupo,
                        "Q_s": round(item.fator_q, 3),
                        "b_ef (mm)": (
                            None
                            if item.largura_efetiva_mm is None
                            else round(item.largura_efetiva_mm, 1)
                        ),
                    }
                    for item in resultado.elementos
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.latex(
        r"\lambda_0=\sqrt{\frac{Q\,A_g\,f_y}{N_e}},\qquad "
        r"\chi=\begin{cases}0{,}658^{\lambda_0^2} & \lambda_0\le1{,}5\\[4pt]"
        r"\dfrac{0{,}877}{\lambda_0^2} & \lambda_0>1{,}5\end{cases}"
    )

with st.container(border=True):
    st.subheader(f"Resistência de cálculo à compressão no eixo {rotulo_eixo} (5.3.2)")
    with st.container(horizontal=True):
        st.metric(
            "N_c,Rd = χ·Q·A_g·f_y/γ_a1",
            f"{resultado.resistencia_N / 1e3:.2f} kN",
            border=True,
            help=f"γ_a1 = {flambagem.GAMMA_A1:.2f} (Tabela 3).",
        )
        st.metric("N_Sd", f"{resultado.forca_solicitante_N / 1e3:.2f} kN", border=True)
        st.metric("N_Sd / N_c,Rd", _fmt(resultado.utilizacao_axial), border=True)
    st.latex(
        r"N_{c,Rd}=\frac{\chi\,Q\,A_g\,f_y}{\gamma_{a1}},\qquad \frac{N_{Sd}}{N_{c,Rd}}\le1{,}0"
    )

momento = resultado.momento
if momento.momento_primeira_ordem_Nmm > 0:
    with st.container(border=True):
        st.subheader(
            f"Flexocompressão no eixo {rotulo_eixo} (5.5.1.2, amplificação B_1 do Anexo D)"
        )
        with st.container(horizontal=True):
            st.metric(
                f"M_{eixo},Sd 1ª ordem",
                f"{momento.momento_primeira_ordem_Nmm / 1e6:.3f} kN·m",
                border=True,
                help=(
                    f"M informado {momento_kNm:.3f} + mão-francesa {momento_mf_no_eixo_kNm:.3f}"
                    + (
                        f" + N_Sd·e {resultado.forca_solicitante_N * excentricidade_mm / 1e6:.3f}"
                        if excentricidade_mm > 0
                        else ""
                    )
                    + " kN·m"
                ),
            )
            st.metric("B_1", _fmt(momento.b1), border=True, help="B_1 = C_m/(1 − N_Sd/N_e) ≥ 1")
            st.metric(
                f"M_{eixo},Sd amplificado",
                "∞"
                if math.isinf(momento.momento_solicitante_Nmm)
                else f"{momento.momento_solicitante_Nmm / 1e6:.3f} kN·m",
                border=True,
            )
            st.metric(
                f"M_{eixo},Rd",
                "—"
                if momento.momento_resistente_Nmm is None
                else f"{momento.momento_resistente_Nmm / 1e6:.3f} kN·m",
                border=True,
                help=(
                    momento.flexao.modo_governante
                    if momento.flexao is not None
                    else "W·f_y/γ_a1 (escoamento da fibra extrema)"
                ),
            )
        if resultado.interacao is not None:
            st.metric(
                "Índice de interação",
                _fmt(resultado.interacao.indice),
                border=True,
                help=resultado.interacao.expressao,
            )
            st.latex(
                rf"\frac{{N_{{Sd}}}}{{N_{{Rd}}}}\ge0{{,}}2:\ \frac{{N_{{Sd}}}}{{N_{{Rd}}}}+\frac{{8}}{{9}}\,"
                rf"\frac{{M_{{{eixo},Sd}}}}{{M_{{{eixo},Rd}}}}\le1{{,}}0\qquad "
                rf"\frac{{N_{{Sd}}}}{{N_{{Rd}}}}<0{{,}}2:\ \frac{{N_{{Sd}}}}{{2N_{{Rd}}}}+"
                rf"\frac{{M_{{{eixo},Sd}}}}{{M_{{{eixo},Rd}}}}\le1{{,}}0"
            )

tabela_resumo_flambagem = pd.DataFrame(
    {
        "Grandeza": [
            "Eixo",
            f"L{eixo} (mm)",
            f"K{eixo}",
            f"λ{eixo}",
            f"N_e{eixo} flexão (kN)",
            "N_ez (kN)",
            "N_e adotado (kN)",
            "Modo",
            "Q",
            "λ_0",
            "χ",
            "N_c,Rd (kN)",
            "N_Sd (kN)",
            f"M_{eixo},Sd amplificado (kN·m)",
            f"M_{eixo},Rd (kN·m)",
            "Índice de interação",
            "Utilização governante",
        ],
        "Valor": [
            rotulo_eixo,
            resultado.comprimento_mm,
            resultado.fator_k,
            resultado.esbeltez,
            resultado.ne_flexao_N / 1e3,
            None if resultado.ne_z_N is None else resultado.ne_z_N / 1e3,
            resultado.ne_N / 1e3,
            resultado.modo_flambagem,
            resultado.fator_q,
            resultado.lambda_0,
            resultado.chi,
            resultado.resistencia_N / 1e3,
            resultado.forca_solicitante_N / 1e3,
            None
            if math.isinf(momento.momento_solicitante_Nmm)
            else momento.momento_solicitante_Nmm / 1e6,
            None
            if momento.momento_resistente_Nmm is None
            else momento.momento_resistente_Nmm / 1e6,
            None
            if resultado.interacao is None or math.isinf(resultado.interacao.indice)
            else resultado.interacao.indice,
            None if math.isinf(resultado.utilizacao) else resultado.utilizacao,
        ],
    }
)
st.download_button(
    "Baixar resultado em CSV",
    data=tabela_resumo_flambagem.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"flambagem_colunas_eixo_{eixo}.csv",
    mime="text/csv",
    icon=":material/download:",
    width="stretch",
    key="flambagem_baixar",
)

if not resultado.atende:
    st.error(
        f"Eixo {rotulo_eixo} não atende: utilização de {utilizacao_texto} pelo modo "
        f"**{resultado.modo_governante}**. Reforce a seção, reduza o comprimento destravado "
        "ou revise o apoio.",
        icon=":material/error:",
    )
elif resultado.utilizacao > 0.9:
    st.warning(
        f"Eixo {rotulo_eixo} atende com utilização de {utilizacao_texto} "
        f"({resultado.modo_governante}) — margem pequena; confira K, comprimento destravado "
        "e os γ_f das ações.",
        icon=":material/warning:",
    )
else:
    st.success(
        f"Eixo {rotulo_eixo} atende: utilização de {utilizacao_texto} pelo modo "
        f"{resultado.modo_governante}.",
        icon=":material/check_circle:",
    )

fronteira_modelo(
    [
        f"Esta verificação cobre só o eixo {rotulo_eixo}: registre também o eixo "
        f"{outro_eixo}-{outro_eixo} com o comprimento destravado e o K daquele plano — o pior "
        "dos dois governa a coluna.",
        "Efeitos globais de segunda ordem (B_2, deslocabilidade do pórtico) e cargas "
        "nocionais pertencem à análise da estrutura — Estruturas de aço (pórtico 2D).",
        "Cisalhamento na coluna (5.4.3) e ligações nas extremidades não são verificados aqui.",
        "Com A e r diretos não há Q nem N_ez: use uma seção geométrica ou o perfil de catálogo.",
        "Cargas dinâmicas, de impacto ou variáveis no tempo (fadiga da própria coluna).",
    ]
)

with st.container(border=True):
    st.subheader(f"Registrar no projeto — eixo {rotulo_eixo}")
    status_registro = (
        "Não atende"
        if not resultado.atende
        else "Atenção"
        if resultado.utilizacao > 0.9 or resultado.avisos
        else "Atende"
    )
    conclusao_registro = (
        f"Eixo {rotulo_eixo}: L{eixo} = {resultado.comprimento_mm:.0f} mm, K{eixo} = {resultado.fator_k:.2f}, "
        f"λ{eixo} = {resultado.esbeltez:.1f}; N_c,Rd = {resultado.resistencia_N / 1e3:.2f} kN "
        f"(χ = {resultado.chi:.3f}, Q = {resultado.fator_q:.3f}, λ_0 = {resultado.lambda_0:.3f}, "
        f"modo {resultado.modo_flambagem}); N_Sd = {resultado.forca_solicitante_N / 1e3:.2f} kN; "
        f"utilização = {utilizacao_texto} ({resultado.modo_governante})."
        + (
            f" Interação N + M: {resultado.interacao.indice:.3f}."
            if resultado.interacao is not None and not math.isinf(resultado.interacao.indice)
            else ""
        )
    )

    st.markdown("**Comparar cenários**")
    comparador_cenarios(
        escopo="flambagem_colunas",
        resumo_entradas={
            "Eixo": rotulo_eixo,
            "Seção": tipo_secao,
            f"L{eixo} (mm)": round(comprimento_eixo_mm, 0),
            "K": round(k_eixo, 2),
        },
        metricas={
            f"λ{eixo}": f"{resultado.esbeltez:.1f}",
            "χ": f"{resultado.chi:.3f}",
            "N_c,Rd (kN)": f"{resultado.resistencia_N / 1e3:.2f}",
            "Utilização": utilizacao_texto,
        },
    )

    registro_flambagem = construir_registro_tecnico(
        modulo="Flambagem de colunas",
        modulo_id="flambagem_colunas",
        titulo=f"Flambagem de coluna — eixo {rotulo_eixo} — {geometria.descricao}",
        status=status_registro,
        resumo=(
            f"Verificação pela NBR 8800:2008 no eixo {rotulo_eixo}: modo de flambagem "
            f"{resultado.modo_flambagem}, χ = {resultado.chi:.3f}, Q = {resultado.fator_q:.3f}, "
            f"utilização {utilizacao_texto} ({resultado.modo_governante})."
        ),
        entradas={
            "eixo": eixo,
            "secao": geometria.descricao,
            "perfil": geometria.perfil.nome if geometria.perfil else None,
            "soldado": soldado,
            "area_mm2": geometria.area_mm2,
            "raio_giracao_x_mm": geometria.raio_giracao_x_mm,
            "raio_giracao_y_mm": geometria.raio_giracao_y_mm,
            "raio_giracao_mm": resultado.raio_giracao_mm,
            "distancia_fibra_x_mm": geometria.distancia_fibra_x_mm,
            "distancia_fibra_y_mm": geometria.distancia_fibra_y_mm,
            "comprimento_total_mm": comprimento_mm,
            "comprimento_mm": comprimento_eixo_mm,
            "condicao_apoio": apoio,
            "k_recomendado_de_norma": usar_recomendado and not k_manual,
            "k": k_eixo,
            "kz": kz,
            "modulo_elasticidade_MPa": modulo_elasticidade_MPa,
            "modulo_cisalhamento_MPa": modulo_cisalhamento_MPa,
            "escoamento_MPa": escoamento_MPa,
            "permanente_kN": permanente_kN,
            "variavel_kN": variavel_kN,
            "gamma_g": gamma_g,
            "gamma_q": gamma_q,
            "gamma_a1": flambagem.GAMMA_A1,
            "forca_solicitante_kN": resultado.forca_solicitante_N / 1e3,
            "momento_kNm": momento_total_kNm,
            "momento_informado_kNm": momento_kNm,
            "excentricidade_mm": excentricidade_mm,
            "cm": cm,
            "comprimento_destravado_mm": (
                (comprimento_destravado_mm or comprimento_eixo_mm) if eixo == "x" else None
            ),
            "cb": cb if eixo == "x" else None,
            **(
                {
                    "mao_francesa_forca_kN": forca_mf_kN,
                    "mao_francesa_gamma_f": gamma_mf,
                    "mao_francesa_forca_calculo_kN": esforcos_mf.forca_N / 1e3,
                    "mao_francesa_angulo_graus": esforcos_mf.angulo_graus,
                    "mao_francesa_altura_no_mm": esforcos_mf.altura_no_mm,
                    "mao_francesa_vinculo": esforcos_mf.vinculo,
                    "mao_francesa_eixo": eixo_mf,
                    "mao_francesa_excentricidade_mm": esforcos_mf.excentricidade_mm,
                    "mao_francesa_H_kN": esforcos_mf.componente_horizontal_N / 1e3,
                    "mao_francesa_V_kN": esforcos_mf.componente_vertical_N / 1e3,
                    "mao_francesa_momento_kNm": esforcos_mf.momento_Nmm / 1e6,
                    "mao_francesa_momento_neste_eixo_kNm": momento_mf_no_eixo_kNm,
                    "mao_francesa_expressao": esforcos_mf.expressao,
                    "mao_francesa_V_somado_a_NSd": somar_v_mf,
                }
                if esforcos_mf is not None
                else {"mao_francesa": "não incluída"}
            ),
        },
        resultados={
            "eixo": eixo,
            "comprimento_efetivo_mm": resultado.comprimento_efetivo_mm,
            "esbeltez": resultado.esbeltez,
            "esbeltez_governante": resultado.esbeltez,
            "eixo_governante": eixo,
            "ne_flexao_kN": resultado.ne_flexao_N / 1e3,
            "ne_z_kN": None if resultado.ne_z_N is None else resultado.ne_z_N / 1e3,
            "ne_acoplada_kN": (
                None if resultado.ne_acoplada_N is None else resultado.ne_acoplada_N / 1e3
            ),
            "ne_kN": resultado.ne_N / 1e3,
            "modo_flambagem": resultado.modo_flambagem,
            "fator_q": resultado.fator_q,
            "lambda_0": resultado.lambda_0,
            "chi": resultado.chi,
            "forca_escoamento_kN": resultado.forca_escoamento_N / 1e3,
            "resistencia_kN": resultado.resistencia_N / 1e3,
            "utilizacao_axial": (
                None if math.isinf(resultado.utilizacao_axial) else resultado.utilizacao_axial
            ),
            "momento_primeira_ordem_kNm": momento.momento_primeira_ordem_Nmm / 1e6,
            "b1": None if math.isinf(momento.b1) else momento.b1,
            "momento_solicitante_kNm": (
                None
                if math.isinf(momento.momento_solicitante_Nmm)
                else momento.momento_solicitante_Nmm / 1e6
            ),
            "momento_resistente_kNm": (
                None
                if momento.momento_resistente_Nmm is None
                else momento.momento_resistente_Nmm / 1e6
            ),
            "modo_flexao": momento.flexao.modo_governante if momento.flexao else None,
            "indice_interacao": (
                None
                if resultado.interacao is None or math.isinf(resultado.interacao.indice)
                else resultado.interacao.indice
            ),
            "expressao_interacao": (
                None if resultado.interacao is None else resultado.interacao.expressao
            ),
            "utilizacao": None if math.isinf(resultado.utilizacao) else resultado.utilizacao,
            "modo_governante": resultado.modo_governante,
            "atende": resultado.atende,
            "esbeltez_paredes": [
                {
                    "elemento": item.nome,
                    "tipo": item.tipo,
                    "razao": item.razao,
                    "limite_r": item.limite_r,
                    "grupo": item.grupo,
                    "fator_q": item.fator_q,
                }
                for item in resultado.elementos
            ],
        },
        metodo=(
            f"NBR 8800:2008, eixo {rotulo_eixo} — N_c,Rd = χ·Q·A_g·f_y/γ_a1 (5.3.2) com "
            f"λ_0 = √(Q·A_g·f_y/N_e), χ pela curva única (5.3.3), N_e = π²·E·I{eixo}/(K{eixo}·L{eixo})² "
            "ou, se menor, o da torção/flexo-torção (Anexo E), e Q = Q_s·Q_a das esbeltezes das "
            f"paredes (Anexo F). Momento de cálculo em {rotulo_eixo} (excentricidade, aplicado e "
            "mão-francesa) amplificado por B_1 = C_m/(1 − N_Sd/N_e) (Anexo D) e verificado pela "
            "interação 5.5.1.2 com M_Rd do Anexo G."
            + (
                f" Mão-francesa: F_Sd = {esforcos_mf.forca_N / 1e3:.2f} kN a {esforcos_mf.angulo_graus:.0f}° "
                f"decomposta em H = {esforcos_mf.componente_horizontal_N / 1e3:.2f} kN e "
                f"V = {esforcos_mf.componente_vertical_N / 1e3:.2f} kN; {esforcos_mf.expressao} "
                f"= {esforcos_mf.momento_Nmm / 1e6:.3f} kN·m no eixo {eixo_mf}-{eixo_mf}."
                if esforcos_mf is not None
                else ""
            )
        ),
        premissas=[
            f"Verificação do eixo {rotulo_eixo} com comprimento destravado L{eixo} = {comprimento_eixo_mm:.0f} mm "
            f"e K{eixo} = {k_eixo:.2f}; o eixo {outro_eixo}-{outro_eixo} é verificado em registro próprio.",
            (
                f"Ações majoradas: N_Sd = {gamma_g:.2f}·N_g + {gamma_q:.2f}·N_q (Tabela 1, combinação normal)."
                if gamma_g is not None
                else "N_Sd informado já majorado pelas combinações de ações (NBR 8681 / NBR 8800 4.7)."
            ),
            f"Resistência minorada por γ_a1 = {flambagem.GAMMA_A1:.2f} (Tabela 3).",
            (
                "K é o valor recomendado para projeto da Tabela E.1 para a condição de apoio escolhida."
                if usar_recomendado and not k_manual
                else "K informado manualmente."
                if k_manual
                else "K é o valor teórico da Tabela E.1 para a condição de apoio idealizada."
            ),
            "Barra prismática, isolada, com efeitos de 2ª ordem locais (B_1); B_2 e deslocabilidade do pórtico ficam na análise global.",
        ]
        + (
            [
                f"Mão-francesa ligada a {esforcos_mf.altura_no_mm:.0f} mm da base, coluna "
                f"{esforcos_mf.vinculo.lower()} no plano da mão-francesa; V·e somado integralmente ao momento (conservador)"
                + (
                    "; componente vertical V somada a N_Sd."
                    if somar_v_mf
                    else "; N_Sd já inclui a reação vertical da mão-francesa."
                )
            ]
            if esforcos_mf is not None
            else []
        ),
        equacoes=[
            f"N_Sd = γ_g·N_g + γ_q·N_q = {gamma_g:.2f}·{permanente_kN:.2f} + {gamma_q:.2f}·{variavel_kN:.2f} = {forca_sd_kN:.2f} kN"
            if gamma_g is not None
            else f"N_Sd = {forca_sd_kN:.2f} kN (de cálculo)",
            f"λ{eixo} = K{eixo}·L{eixo}/r{eixo} = {k_eixo:.2f}·{comprimento_eixo_mm:.0f}/{resultado.raio_giracao_mm:.1f} = {resultado.esbeltez:.1f} ≤ 200",
            f"N_e{eixo} = π²·E·I{eixo}/(K{eixo}·L{eixo})² = {resultado.ne_flexao_N / 1e3:.1f} kN"
            + (
                f";  N_ez = [π²·E·Cw/(Kz·Lz)² + G·J]/r0² = {resultado.ne_z_N / 1e3:.1f} kN"
                if resultado.ne_z_N is not None
                else ""
            )
            + f";  N_e adotado = {resultado.ne_N / 1e3:.1f} kN (modo {resultado.modo_flambagem})",
            f"Q = Q_s·Q_a = {resultado.fator_q:.3f} (Anexo F)",
            f"λ_0 = √(Q·A_g·f_y/N_e) = √({resultado.fator_q:.3f}·{geometria.area_mm2:.0f}·{escoamento_MPa:.0f}/{resultado.ne_N:.0f}) = {resultado.lambda_0:.3f}",
            (
                f"χ = 0,658^(λ_0²) = {resultado.chi:.3f}"
                if resultado.lambda_0 <= 1.5
                else f"χ = 0,877/λ_0² = {resultado.chi:.3f}"
            ),
            f"N_c,Rd = χ·Q·A_g·f_y/γ_a1 = {resultado.chi:.3f}·{resultado.fator_q:.3f}·{geometria.area_mm2:.0f}·{escoamento_MPa:.0f}/{flambagem.GAMMA_A1:.2f} = {resultado.resistencia_N / 1e3:.2f} kN",
            f"N_Sd/N_c,Rd = {resultado.forca_solicitante_N / 1e3:.2f}/{resultado.resistencia_N / 1e3:.2f} = {_fmt(resultado.utilizacao_axial)}",
        ]
        + (
            [
                f"Mão-francesa: H = F_Sd·sen θ = {esforcos_mf.forca_N / 1e3:.2f}·sen {esforcos_mf.angulo_graus:.0f}° = {esforcos_mf.componente_horizontal_N / 1e3:.2f} kN;  "
                f"V = F_Sd·cos θ = {esforcos_mf.componente_vertical_N / 1e3:.2f} kN;  {esforcos_mf.expressao} = {esforcos_mf.momento_Nmm / 1e6:.3f} kN·m"
            ]
            if esforcos_mf is not None
            else []
        )
        + (
            [
                f"B_1 = C_m/(1 − N_Sd/N_e{eixo}) = {cm:.2f}/(1 − {resultado.forca_solicitante_N / 1e3:.2f}/{resultado.ne_flexao_N / 1e3:.1f}) = {_fmt(momento.b1)}",
                f"M_{eixo},Sd = B_1·M_1 = {_fmt(momento.b1)}·{momento.momento_primeira_ordem_Nmm / 1e6:.3f} = {_fmt(None if math.isinf(momento.momento_solicitante_Nmm) else momento.momento_solicitante_Nmm / 1e6)} kN·m;  "
                f"M_{eixo},Rd = {_fmt(None if momento.momento_resistente_Nmm is None else momento.momento_resistente_Nmm / 1e6)} kN·m",
            ]
            + (
                [f"{resultado.interacao.expressao}  →  {_fmt(resultado.interacao.indice)}"]
                if resultado.interacao is not None
                else []
            )
            if momento.momento_primeira_ordem_Nmm > 0
            else []
        ),
        alertas=([] if status_registro == "Atende" else [conclusao_registro])
        + list(resultado.avisos),
        referencias=[
            "ABNT NBR 8800:2008 — 4.7 (ações), 5.3 (compressão), 5.5.1.2 (interação), Anexos D, E, F e G.",
            "Confirmar comprimentos destravados reais, K de norma e as combinações de ações do projeto.",
        ],
        conclusao=conclusao_registro,
        materiais_ids=[material_id] if material_id else [],
    )
    botao_registrar_calculo(
        registro_flambagem,
        key=f"registrar_flambagem_colunas_{eixo}",
        rotulo=f"Registrar verificação do eixo {rotulo_eixo} no projeto ativo",
    )
    st.caption(
        f"Depois de registrar, troque para o eixo {outro_eixo}-{outro_eixo} na seção 2 e registre "
        "também: cada eixo fica como um registro próprio no memorial."
    )

with st.container(border=True):
    st.subheader("Precisa de ajuda para preencher ou interpretar?")
    st.markdown(
        "O **Guia geral** mostra como escolher K, o que são χ, Q e N_ez e um "
        "exemplo completo de coluna pela NBR 8800."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir o guia de flambagem",
        icon=":material/help:",
        query_params={"modulo": "Flambagem de colunas"},
        width="stretch",
    )
st.caption(
    "Verificação de barra isolada pela NBR 8800:2008, um eixo por vez. Para a estrutura "
    "completa (pórtico, B_2, cargas nocionais, ligações e placa de base), use Estruturas de aço."
)
