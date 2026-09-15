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
    st.subheader("2. Comprimento e condições de apoio")
    comprimento_mm = st.number_input(
        "Comprimento real da coluna L (mm)",
        min_value=0.001,
        step=100.0,
        key="flambagem_comprimento_mm",
        persist_state="session",
    )
    apoio = st.selectbox(
        "Condição de apoio idealizada (Tabela E.1)",
        list(flambagem.CONDICOES_APOIO),
        key="flambagem_condicao_apoio",
        persist_state="session",
    )
    k_teorico = flambagem.CONDICOES_APOIO[apoio]
    k_recomendado = flambagem.CONDICOES_APOIO_RECOMENDADAS[apoio]
    usar_recomendado = st.toggle(
        f"Usar o K recomendado para projeto ({k_recomendado:.2f}) em vez do teórico ({k_teorico:.2f})",
        value=True,
        key="flambagem_k_recomendado",
        persist_state="session",
        help=(
            "Ligações reais nunca são um engaste ou um pino perfeitos. A Tabela E.1 "
            "da NBR 8800 recomenda K maior que o teórico nos casos com engaste: "
            "0,65 em vez de 0,50, 0,80 em vez de 0,70, 2,1 em vez de 2,0."
        ),
    )
    k_padrao = k_recomendado if usar_recomendado else k_teorico
    st.caption(
        f"Fator de comprimento de flambagem adotado K = {k_padrao:.2f} "
        f"({'recomendado para projeto' if usar_recomendado else 'teórico'})."
    )
    contraventamento_assimetrico = st.checkbox(
        "Contraventamento diferente em cada eixo (Kx ≠ Ky) ou torção travada (Kz)",
        value=False,
        help=(
            "Use quando a coluna é travada lateralmente em um eixo (reduzindo "
            "o comprimento destravado) e livre no outro, ou quando a rotação "
            "em torno do eixo longitudinal tem travamento próprio."
        ),
        key="flambagem_kx_ky_diferentes",
        persist_state="session",
    )
    kz = None
    if contraventamento_assimetrico:
        colunas_k = st.columns(3)
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
        kz = colunas_k[2].number_input(
            "Kz (torção)",
            min_value=0.01,
            value=max(kx, ky),
            step=0.05,
            key="flambagem_kz",
            persist_state="session",
            help="Comprimento de flambagem por torção K_z·L (Anexo E). Sem travamento próprio, vale o maior de Kx·L e Ky·L.",
        )
    else:
        kx = ky = k_padrao

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

    st.markdown("**Flexocompressão** (5.5.1.2) — excentricidade e/ou momentos de cálculo")
    colunas_exc = st.columns([2, 1, 1])
    excentricidade_mm = colunas_exc[0].number_input(
        "Excentricidade e da força (mm)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key="flambagem_excentricidade_mm",
        persist_state="session",
        help=(
            "Distância entre a linha de ação da força e o centroide (ex.: força de "
            "mão-francesa chegando fora do eixo). Gera M_Sd = N_Sd·e, amplificado "
            "por B_1 (Anexo D) e levado à equação de interação."
        ),
    )
    eixo_excentricidade = colunas_exc[1].selectbox(
        "Eixo de flexão de e",
        ["governante", "x", "y"],
        key="flambagem_eixo_excentricidade",
        persist_state="session",
    )
    cm = colunas_exc[2].number_input(
        "C_m",
        min_value=0.2,
        max_value=1.0,
        value=1.0,
        step=0.05,
        key="flambagem_cm",
        persist_state="session",
        help="Coeficiente de equivalência de momentos (D.2.2): 1,0 é conservador; 0,6 − 0,4·M1/M2 sem cargas transversais.",
    )
    colunas_m = st.columns(4)
    momento_x_kNm = colunas_m[0].number_input(
        "M_x,Sd (kN·m)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key="flambagem_mx_kNm",
        persist_state="session",
        help="Momento de cálculo de 1ª ordem em torno de x (por exemplo, da força cortante da mão-francesa × braço).",
    )
    momento_y_kNm = colunas_m[1].number_input(
        "M_y,Sd (kN·m)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key="flambagem_my_kNm",
        persist_state="session",
    )
    comprimento_destravado_mm = colunas_m[2].number_input(
        "L_b para FLT (mm, 0 = igual a L)",
        min_value=0.0,
        value=0.0,
        step=100.0,
        key="flambagem_lb_mm",
        persist_state="session",
        help="Comprimento destravado lateralmente da mesa comprimida, só para M_x,Rd de perfis abertos.",
    )
    cb = colunas_m[3].number_input(
        "C_b",
        min_value=1.0,
        max_value=3.0,
        value=1.0,
        step=0.05,
        key="flambagem_cb",
        persist_state="session",
    )

try:
    resultado = flambagem.verificar_flambagem(
        geometria=geometria,
        comprimento_mm=comprimento_mm,
        kx=kx,
        ky=ky,
        kz=kz,
        modulo_elasticidade_MPa=modulo_elasticidade_MPa,
        modulo_cisalhamento_MPa=modulo_cisalhamento_MPa,
        escoamento_MPa=escoamento_MPa,
        forca_solicitante_N=forca_sd_kN * 1e3,
        momento_x_Nmm=momento_x_kNm * 1e6,
        momento_y_Nmm=momento_y_kNm * 1e6,
        excentricidade_mm=excentricidade_mm,
        eixo_excentricidade=eixo_excentricidade,
        cm=cm,
        comprimento_destravado_mm=(
            comprimento_destravado_mm if comprimento_destravado_mm > 0 else comprimento_mm
        ),
        cb=cb,
        soldado=soldado,
    )
except ValueError as erro:
    st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
    st.stop()

st.header("Resultados")

for aviso in resultado.avisos:
    st.warning(aviso, icon=":material/warning:")

with st.container(border=True):
    st.subheader("Esbeltez e flambagem elástica (Anexo E)")
    with st.container(horizontal=True):
        st.metric("λx = KxL/rx", f"{resultado.esbeltez_x:.1f}", border=True)
        st.metric("λy = KyL/ry", f"{resultado.esbeltez_y:.1f}", border=True)
        st.metric(
            f"λ governante (eixo {resultado.eixo_governante})",
            f"{resultado.esbeltez_governante:.1f}",
            border=True,
            help=f"Limite 5.3.4.1: KL/r ≤ {flambagem.ESBELTEZ_MAXIMA:.0f}.",
        )
    with st.container(horizontal=True):
        st.metric("N_ex", f"{resultado.ne_x_N / 1e3:.1f} kN", border=True)
        st.metric("N_ey", f"{resultado.ne_y_N / 1e3:.1f} kN", border=True)
        st.metric(
            "N_ez (torção)",
            "—" if resultado.ne_z_N is None else f"{resultado.ne_z_N / 1e3:.1f} kN",
            border=True,
            help="Seções maciças e tubos circulares: torção não governa (J alto, Cw ≈ 0).",
        )
        if resultado.ne_acoplada_N is not None:
            st.metric(
                "N_e flexo-torção",
                f"{resultado.ne_acoplada_N / 1e3:.1f} kN",
                border=True,
                help="Modo acoplado das seções monossimétricas (E.1.2).",
            )
        st.metric(
            f"N_e governante (modo {resultado.modo_flambagem})",
            f"{resultado.ne_N / 1e3:.1f} kN",
            border=True,
        )
    st.latex(
        r"N_{ex}=\frac{\pi^2 E I_x}{(K_xL_x)^2},\quad "
        r"N_{ey}=\frac{\pi^2 E I_y}{(K_yL_y)^2},\quad "
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
        st.metric(
            "λ_0",
            f"{resultado.lambda_0:.3f}",
            border=True,
            help="λ_0 = √(Q·A_g·f_y / N_e)",
        )
        st.metric(
            "χ",
            f"{resultado.chi:.3f}",
            border=True,
            help="0,658^(λ_0²) para λ_0 ≤ 1,5; 0,877/λ_0² acima.",
        )
        st.metric(
            "Q·A_g·f_y",
            f"{resultado.forca_escoamento_N / 1e3:.1f} kN",
            border=True,
        )
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
    st.subheader("Resistência de cálculo à compressão (5.3.2)")
    with st.container(horizontal=True):
        st.metric(
            "N_c,Rd = χ·Q·A_g·f_y/γ_a1",
            f"{resultado.resistencia_N / 1e3:.2f} kN",
            border=True,
            help=f"γ_a1 = {flambagem.GAMMA_A1:.2f} (Tabela 3).",
        )
        st.metric("N_Sd", f"{resultado.forca_solicitante_N / 1e3:.2f} kN", border=True)
        st.metric(
            "N_Sd / N_c,Rd",
            "∞" if math.isinf(resultado.utilizacao_axial) else f"{resultado.utilizacao_axial:.3f}",
            border=True,
        )
    st.latex(
        r"N_{c,Rd}=\frac{\chi\,Q\,A_g\,f_y}{\gamma_{a1}},\qquad \frac{N_{Sd}}{N_{c,Rd}}\le1{,}0"
    )

momentos_ativos = [
    m for m in (resultado.momento_x, resultado.momento_y) if m.momento_primeira_ordem_Nmm > 0
]
if momentos_ativos:
    with st.container(border=True):
        st.subheader("Flexocompressão (5.5.1.2, amplificação B_1 do Anexo D)")
        for momento in momentos_ativos:
            with st.container(horizontal=True):
                st.metric(
                    f"M_{momento.eixo},Sd 1ª ordem",
                    f"{momento.momento_primeira_ordem_Nmm / 1e6:.3f} kN·m",
                    border=True,
                )
                st.metric(
                    f"B_1 ({momento.eixo})",
                    "∞" if math.isinf(momento.b1) else f"{momento.b1:.3f}",
                    border=True,
                    help="B_1 = C_m/(1 − N_Sd/N_e) ≥ 1",
                )
                st.metric(
                    f"M_{momento.eixo},Sd amplificado",
                    "∞"
                    if math.isinf(momento.momento_solicitante_Nmm)
                    else f"{momento.momento_solicitante_Nmm / 1e6:.3f} kN·m",
                    border=True,
                )
                st.metric(
                    f"M_{momento.eixo},Rd",
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
                "∞"
                if math.isinf(resultado.interacao.indice)
                else f"{resultado.interacao.indice:.3f}",
                border=True,
                help=resultado.interacao.expressao,
            )
            st.latex(
                r"\frac{N_{Sd}}{N_{Rd}}\ge0{,}2:\ \frac{N_{Sd}}{N_{Rd}}+\frac{8}{9}\left("
                r"\frac{M_{x,Sd}}{M_{x,Rd}}+\frac{M_{y,Sd}}{M_{y,Rd}}\right)\le1{,}0\qquad "
                r"\frac{N_{Sd}}{N_{Rd}}<0{,}2:\ \frac{N_{Sd}}{2N_{Rd}}+\frac{M_{x,Sd}}{M_{x,Rd}}"
                r"+\frac{M_{y,Sd}}{M_{y,Rd}}\le1{,}0"
            )

tabela_resumo_flambagem = pd.DataFrame(
    {
        "Grandeza": [
            "λx",
            "λy",
            "λ governante",
            "N_ex (kN)",
            "N_ey (kN)",
            "N_ez (kN)",
            "N_e governante (kN)",
            "Q",
            "λ_0",
            "χ",
            "N_c,Rd (kN)",
            "N_Sd (kN)",
            "Índice de interação",
            "Utilização governante",
        ],
        "Valor": [
            resultado.esbeltez_x,
            resultado.esbeltez_y,
            resultado.esbeltez_governante,
            resultado.ne_x_N / 1e3,
            resultado.ne_y_N / 1e3,
            None if resultado.ne_z_N is None else resultado.ne_z_N / 1e3,
            resultado.ne_N / 1e3,
            resultado.fator_q,
            resultado.lambda_0,
            resultado.chi,
            resultado.resistencia_N / 1e3,
            resultado.forca_solicitante_N / 1e3,
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
    file_name="flambagem_colunas_nbr8800.csv",
    mime="text/csv",
    icon=":material/download:",
    width="stretch",
    key="flambagem_baixar",
)

utilizacao_texto = "∞" if math.isinf(resultado.utilizacao) else f"{resultado.utilizacao * 100:.0f}%"
if not resultado.atende:
    st.error(
        f"Não atende: utilização de {utilizacao_texto} pelo modo **{resultado.modo_governante}**. "
        "Reforce a seção, reduza o comprimento de flambagem ou revise o apoio.",
        icon=":material/error:",
    )
elif resultado.utilizacao > 0.9:
    st.warning(
        f"Atende com utilização de {utilizacao_texto} ({resultado.modo_governante}) "
        "— margem pequena; confira K, comprimentos destravados e os γ_f das ações.",
        icon=":material/warning:",
    )
else:
    st.success(
        f"Atende: utilização de {utilizacao_texto} pelo modo {resultado.modo_governante}.",
        icon=":material/check_circle:",
    )

fronteira_modelo(
    [
        "Efeitos globais de segunda ordem (B_2, deslocabilidade do pórtico) e cargas "
        "nocionais pertencem à análise da estrutura — Estruturas de aço (pórtico 2D).",
        "Cisalhamento na coluna (5.4.3) e ligações nas extremidades não são verificados aqui.",
        "Com A e r diretos não há Q nem N_ez: use uma seção geométrica ou o perfil de catálogo.",
        "Cargas dinâmicas, de impacto ou variáveis no tempo (fadiga da própria coluna).",
    ]
)

with st.container(border=True):
    st.subheader("Registrar no projeto")
    status_registro = (
        "Não atende"
        if not resultado.atende
        else "Atenção"
        if resultado.utilizacao > 0.9 or resultado.avisos
        else "Atende"
    )
    conclusao_registro = (
        f"N_c,Rd = {resultado.resistencia_N / 1e3:.2f} kN (χ = {resultado.chi:.3f}, "
        f"Q = {resultado.fator_q:.3f}, λ_0 = {resultado.lambda_0:.3f}); "
        f"N_Sd = {resultado.forca_solicitante_N / 1e3:.2f} kN; "
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
            "Seção": tipo_secao,
            "L (mm)": round(comprimento_mm, 0),
            "K": round(k_padrao, 2),
        },
        metricas={
            "λ governante": f"{resultado.esbeltez_governante:.1f}",
            "χ": f"{resultado.chi:.3f}",
            "N_c,Rd (kN)": f"{resultado.resistencia_N / 1e3:.2f}",
            "Utilização": utilizacao_texto,
        },
    )

    def _momento_registro(momento: flambagem.MomentoFletor) -> dict:
        return {
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
        }

    registro_flambagem = construir_registro_tecnico(
        modulo="Flambagem de colunas",
        modulo_id="flambagem_colunas",
        titulo=f"Flambagem de coluna — {geometria.descricao}",
        status=status_registro,
        resumo=(
            f"Verificação pela NBR 8800:2008: modo de flambagem {resultado.modo_flambagem}, "
            f"χ = {resultado.chi:.3f}, Q = {resultado.fator_q:.3f}, "
            f"utilização {utilizacao_texto} ({resultado.modo_governante})."
        ),
        entradas={
            "secao": geometria.descricao,
            "perfil": geometria.perfil.nome if geometria.perfil else None,
            "soldado": soldado,
            "area_mm2": geometria.area_mm2,
            "raio_giracao_x_mm": geometria.raio_giracao_x_mm,
            "raio_giracao_y_mm": geometria.raio_giracao_y_mm,
            "distancia_fibra_x_mm": geometria.distancia_fibra_x_mm,
            "distancia_fibra_y_mm": geometria.distancia_fibra_y_mm,
            "comprimento_mm": comprimento_mm,
            "condicao_apoio": apoio,
            "k_recomendado_de_norma": usar_recomendado,
            "kx": kx,
            "ky": ky,
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
            "momento_x_kNm": momento_x_kNm,
            "momento_y_kNm": momento_y_kNm,
            "excentricidade_mm": excentricidade_mm,
            "eixo_excentricidade": eixo_excentricidade,
            "cm": cm,
            "comprimento_destravado_mm": comprimento_destravado_mm or comprimento_mm,
            "cb": cb,
        },
        resultados={
            "esbeltez_x": resultado.esbeltez_x,
            "esbeltez_y": resultado.esbeltez_y,
            "esbeltez_governante": resultado.esbeltez_governante,
            "eixo_governante": resultado.eixo_governante,
            "ne_x_kN": resultado.ne_x_N / 1e3,
            "ne_y_kN": resultado.ne_y_N / 1e3,
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
            "momento_x": _momento_registro(resultado.momento_x),
            "momento_y": _momento_registro(resultado.momento_y),
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
            "NBR 8800:2008 — N_c,Rd = χ·Q·A_g·f_y/γ_a1 (5.3.2) com λ_0 = √(Q·A_g·f_y/N_e), "
            "χ pela curva única (5.3.3), N_e o menor entre flexão em x e y, torção e "
            "flexo-torção (Anexo E) e Q = Q_s·Q_a das esbeltezes das paredes (Anexo F). "
            "Momentos de cálculo (excentricidade e aplicados) amplificados por "
            "B_1 = C_m/(1 − N_Sd/N_e) (Anexo D) e verificados pela interação 5.5.1.2 "
            "com M_Rd do Anexo G."
        ),
        premissas=[
            (
                f"Ações majoradas: N_Sd = {gamma_g:.2f}·N_g + {gamma_q:.2f}·N_q (Tabela 1, combinação normal)."
                if gamma_g is not None
                else "N_Sd informado já majorado pelas combinações de ações (NBR 8681 / NBR 8800 4.7)."
            ),
            f"Resistência minorada por γ_a1 = {flambagem.GAMMA_A1:.2f} (Tabela 3).",
            (
                "K é o valor recomendado para projeto da Tabela E.1 para a condição de apoio escolhida."
                if usar_recomendado
                else "K é o valor teórico da Tabela E.1 para a condição de apoio idealizada."
            ),
            "Barra prismática, isolada, com efeitos de 2ª ordem locais (B_1); B_2 e deslocabilidade do pórtico ficam na análise global.",
        ],
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
        key="registrar_flambagem_colunas",
        rotulo="Registrar verificação de flambagem no projeto ativo",
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
    "Verificação de barra isolada pela NBR 8800:2008. Para a estrutura completa "
    "(pórtico, B_2, cargas nocionais, ligações e placa de base), use Estruturas de aço."
)
