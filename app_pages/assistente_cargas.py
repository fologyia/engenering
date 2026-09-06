import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina
from core import additional_load_models as modelos
from core import load_to_stress as cargas


st.set_page_config(
    page_title="Assistente de cargas",
    page_icon=":material/manufacturing:",
    layout="wide",
)


def enviar_para_mohr(estado: cargas.EstadoPlanoCalculado) -> None:
    """Guarda o estado calculado e abre a análise do Círculo de Mohr."""
    st.session_state["mohr_assistente_2d"] = {
        "sigma_x": estado.sigma_x,
        "sigma_y": estado.sigma_y,
        "tau_xy": estado.tau_xy,
        "descricao": estado.descricao,
    }
    st.session_state["mohr_tipo_estado"] = "Estado plano (2D)"
    st.session_state["mohr_2d_exemplo"] = "assistente"
    for chave in (
        "mohr_2d_sigma_x_assistente",
        "mohr_2d_sigma_y_assistente",
        "mohr_2d_tau_xy_assistente",
        "mohr_2d_theta_assistente",
    ):
        st.session_state.pop(chave, None)
    st.switch_page("app_pages/circulo_mohr.py")


def selecionar_face(chave: str) -> str:
    rotulo = st.segmented_control(
        "Ponto na flexão",
        ["Lado tracionado", "Lado comprimido"],
        default="Lado tracionado",
        required=True,
        width="stretch",
        key=chave,
    )
    return "tracionada" if rotulo == "Lado tracionado" else "comprimida"


def mostrar_validacao_parede_fina(diametro: float, espessura: float) -> None:
    relacao = cargas.relacao_diametro_espessura(diametro, espessura)
    st.metric("Relação D/t", f"{relacao:.1f}", border=True)
    if relacao < 20.0:
        st.warning(
            "D/t < 20: a hipótese de parede fina pode ser inadequada. "
            "Use um modelo de parede espessa.",
            icon=":material/warning:",
        )
    else:
        st.success(
            "D/t é compatível com a aproximação de parede fina.",
            icon=":material/check_circle:",
        )


cabecalho_pagina(
    "Assistente de cargas e geometrias",
    "Converta forças, momentos, torque, pressão e dimensões em componentes de tensão.",
    categoria="Preparação de dados",
    icone=":material/manufacturing:",
    cor="violet",
    ajuda_modulo="Assistente de cargas",
    acoes=(("app_pages/circulo_mohr.py", "Círculo de Mohr", ":material/donut_large:"),),
)
st.info(
    "**Para que serve:** você tem forças, momentos, torques ou pressão medidos "
    "ou definidos em projeto, mas precisa saber o quanto o material está sendo "
    "esticado, comprimido ou torcido em um ponto específico. Este assistente faz "
    "essa conversão para você, sem precisar montar as fórmulas manualmente.",
    icon=":material/lightbulb:",
)
st.caption(
    "Use forças em kN, momentos e torques em N·m e dimensões em mm. "
    "A saída é calculada em MPa (megapascal)."
)

opcoes_modelo = [
    "Barra sob carga axial",
    "Eixo circular maciço",
    "Eixo circular vazado",
    "Viga de seção retangular",
    "Seção retangular com flexão biaxial",
    "Seção I sob força axial e flexão",
    "Pinos ou parafusos sob cisalhamento",
    "Vaso cilíndrico de parede fina",
    "Vaso esférico de parede fina",
]
descricoes_simples = {
    "Barra sob carga axial": (
        "Uma peça reta sendo puxada (tração) ou empurrada (compressão) "
        "no sentido do seu comprimento — como um tirante ou uma coluna."
    ),
    "Eixo circular maciço": (
        "Um eixo redondo e cheio (sem furo no meio) que pode estar sendo "
        "puxado/empurrado, dobrado e torcido ao mesmo tempo."
    ),
    "Eixo circular vazado": (
        "Um tubo — eixo redondo oco — sob os mesmos tipos de esforço do "
        "eixo maciço."
    ),
    "Viga de seção retangular": (
        "Uma viga retangular (como uma régua de canto) que dobra e também "
        "sofre corte transversal."
    ),
    "Seção retangular com flexão biaxial": (
        "Uma barra retangular que dobra em duas direções ao mesmo tempo, "
        "não só em uma."
    ),
    "Seção I sob força axial e flexão": (
        "Uma viga com seção em forma de 'I', muito comum em estruturas "
        "metálicas."
    ),
    "Pinos ou parafusos sob cisalhamento": (
        "Um pino ou parafuso sendo cortado transversalmente pela força, "
        "como uma tesoura corta um papel."
    ),
    "Vaso cilíndrico de parede fina": (
        "Um tubo ou vaso de pressão com parede fina, como um cilindro de "
        "gás ou uma tubulação pressurizada."
    ),
    "Vaso esférico de parede fina": (
        "Um vaso esférico de parede fina, como um tanque redondo "
        "pressurizado."
    ),
}

st.markdown("##### Passo 1 · Escolha a peça e o tipo de carregamento")
geometria = st.selectbox(
    "Selecione o modelo",
    opcoes_modelo,
    help="Escolha o modelo que melhor representa a seção no ponto analisado.",
    key="assistente_geometria",
    label_visibility="collapsed",
)
st.caption(f":material/info: {descricoes_simples[geometria]}")

st.markdown("##### Passo 2 · Informe os valores")

estado = None

if geometria == "Barra sob carga axial":
    with st.container(border=True):
        st.subheader("Barra sob tração ou compressão")
        st.latex(r"\sigma_x=\frac{F}{A}")
        entradas = st.columns(2)
        with entradas[0]:
            forca_kN = st.number_input(
                "Força axial F (kN)",
                value=20.0,
                step=1.0,
                help="Positiva para tração e negativa para compressão.",
            )
        with entradas[1]:
            area_mm2 = st.number_input(
                "Área da seção A (mm²)",
                min_value=0.001,
                value=200.0,
                step=10.0,
            )
        estado = cargas.barra_axial(forca_kN * 1_000.0, area_mm2)

elif geometria == "Eixo circular maciço":
    with st.container(border=True):
        st.subheader("Eixo maciço com carga axial, flexão e torção")
        st.latex(
            r"\sigma_x=\frac{F}{A}\pm\frac{32M}{\pi d^3},"
            r"\qquad \tau_{xy}=\frac{16T}{\pi d^3}"
        )
        linha_1 = st.columns(2)
        with linha_1[0]:
            diametro = st.number_input(
                "Diâmetro d (mm)", min_value=0.001, value=30.0, step=1.0
            )
        with linha_1[1]:
            face = selecionar_face("assistente_face_eixo_macico")
        linha_2 = st.columns(3)
        with linha_2[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                help="Positiva para tração e negativa para compressão.",
            )
        with linha_2[1]:
            momento = st.number_input(
                "Momento fletor |M| (N·m)",
                min_value=0.0,
                value=500.0,
                step=10.0,
            )
        with linha_2[2]:
            torque = st.number_input(
                "Torque T (N·m)",
                value=300.0,
                step=10.0,
                help="O sinal define o sinal de τxy.",
            )
        estado = cargas.eixo_circular_macico(
            diametro_mm=diametro,
            forca_axial_N=forca * 1_000.0,
            momento_fletor_Nmm=momento * 1_000.0,
            torque_Nmm=torque * 1_000.0,
            face_flexao=face,
        )

elif geometria == "Eixo circular vazado":
    with st.container(border=True):
        st.subheader("Eixo vazado com carga axial, flexão e torção")
        st.latex(
            r"\sigma_x=\frac{F}{A}\pm\frac{M(D_e/2)}{I},"
            r"\qquad \tau_{xy}=\frac{T(D_e/2)}{J}"
        )
        linha_1 = st.columns(3)
        with linha_1[0]:
            de = st.number_input(
                "Diâmetro externo De (mm)",
                min_value=0.002,
                value=40.0,
                step=1.0,
            )
        with linha_1[1]:
            di = st.number_input(
                "Diâmetro interno Di (mm)",
                min_value=0.0,
                max_value=de - 0.001,
                value=min(25.0, de - 0.001),
                step=1.0,
            )
        with linha_1[2]:
            face = selecionar_face("assistente_face_eixo_vazado")
        linha_2 = st.columns(3)
        with linha_2[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_vazado_forca",
            )
        with linha_2[1]:
            momento = st.number_input(
                "Momento fletor |M| (N·m)",
                min_value=0.0,
                value=500.0,
                step=10.0,
                key="assistente_vazado_momento",
            )
        with linha_2[2]:
            torque = st.number_input(
                "Torque T (N·m)",
                value=300.0,
                step=10.0,
                key="assistente_vazado_torque",
            )
        estado = modelos.eixo_circular_vazado(
            de, di, forca * 1_000.0, momento * 1_000.0, torque * 1_000.0, face
        )

elif geometria == "Viga de seção retangular":
    with st.container(border=True):
        st.subheader("Viga retangular no ponto escolhido")
        st.latex(
            r"\sigma_x=\frac{F}{A}-\frac{My}{I},\qquad "
            r"\tau_{xy}=\frac{3V}{2A}"
            r"\left[1-\left(\frac{2y}{h}\right)^2\right]"
        )
        dimensoes = st.columns(2)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b (mm)", min_value=0.001, value=20.0, step=1.0
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h (mm)", min_value=0.001, value=40.0, step=1.0
            )
        posicao = st.selectbox(
            "Ponto na altura da seção",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            help="y é positivo para a fibra superior.",
        )
        if posicao == "Fibra superior":
            y = altura / 2.0
        elif posicao == "Centroide":
            y = 0.0
        elif posicao == "Fibra inferior":
            y = -altura / 2.0
        else:
            y = st.number_input(
                "Coordenada y desde o centroide (mm)",
                min_value=-altura / 2.0,
                max_value=altura / 2.0,
                value=0.0,
                step=max(0.1, altura / 20.0),
            )
        linha = st.columns(3)
        with linha[0]:
            forca = st.number_input(
                "Força axial F (kN)", value=0.0, step=1.0
            )
        with linha[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=500.0,
                step=10.0,
                help="Momento positivo comprime a região de y positivo.",
            )
        with linha[2]:
            cortante = st.number_input(
                "Força cortante V (kN)",
                value=1.0,
                step=0.5,
                help="O sinal define o sinal de τxy.",
            )
        estado = cargas.viga_retangular(
            largura, altura, y, forca * 1_000.0, momento * 1_000.0,
            cortante * 1_000.0
        )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm.")

elif geometria == "Seção retangular com flexão biaxial":
    with st.container(border=True):
        st.subheader("Seção retangular sob flexão nos dois eixos")
        st.latex(
            r"\sigma_x=\frac{F}{A}+\frac{M_y z}{I_y}"
            r"-\frac{M_z y}{I_z}"
        )
        dimensoes = st.columns(2)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b, direção z (mm)",
                min_value=0.001,
                value=40.0,
                step=1.0,
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h, direção y (mm)",
                min_value=0.001,
                value=60.0,
                step=1.0,
            )
        ponto = st.columns(2)
        with ponto[0]:
            y = st.number_input(
                "Coordenada y (mm)",
                min_value=-altura / 2.0,
                max_value=altura / 2.0,
                value=altura / 2.0,
                step=max(0.1, altura / 20.0),
            )
        with ponto[1]:
            z = st.number_input(
                "Coordenada z (mm)",
                min_value=-largura / 2.0,
                max_value=largura / 2.0,
                value=largura / 2.0,
                step=max(0.1, largura / 20.0),
            )
        linha = st.columns(3)
        with linha[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_biaxial_forca",
            )
        with linha[1]:
            my = st.number_input(
                "Momento My (N·m)", value=200.0, step=10.0
            )
        with linha[2]:
            mz = st.number_input(
                "Momento Mz (N·m)", value=500.0, step=10.0
            )
        estado = modelos.secao_retangular_flexao_biaxial(
            largura, altura, y, z, forca * 1_000.0,
            my * 1_000.0, mz * 1_000.0
        )

elif geometria == "Seção I sob força axial e flexão":
    with st.container(border=True):
        st.subheader("Seção I duplamente simétrica")
        st.latex(r"\sigma_x=\frac{F}{A}-\frac{My}{I}")
        dimensoes = st.columns(4)
        with dimensoes[0]:
            altura = st.number_input(
                "Altura total h (mm)", min_value=0.01, value=200.0, step=5.0
            )
        with dimensoes[1]:
            mesa = st.number_input(
                "Largura da mesa b (mm)",
                min_value=0.01,
                value=100.0,
                step=5.0,
            )
        with dimensoes[2]:
            t_mesa = st.number_input(
                "Espessura da mesa tf (mm)",
                min_value=0.001,
                max_value=altura / 2.0 - 0.001,
                value=min(10.0, altura / 4.0),
                step=1.0,
            )
        with dimensoes[3]:
            t_alma = st.number_input(
                "Espessura da alma tw (mm)",
                min_value=0.001,
                max_value=mesa - 0.001,
                value=min(6.0, mesa / 2.0),
                step=1.0,
            )
        ponto = st.selectbox(
            "Ponto na altura",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            key="assistente_i_ponto",
        )
        if ponto == "Fibra superior":
            y = altura / 2.0
        elif ponto == "Centroide":
            y = 0.0
        elif ponto == "Fibra inferior":
            y = -altura / 2.0
        else:
            y = st.number_input(
                "Coordenada y (mm)",
                min_value=-altura / 2.0,
                max_value=altura / 2.0,
                value=0.0,
            )
        cargas_i = st.columns(2)
        with cargas_i[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_i_forca",
            )
        with cargas_i[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=5_000.0,
                step=100.0,
                key="assistente_i_momento",
            )
        estado = modelos.secao_i_flexao(
            altura, mesa, t_mesa, t_alma, y,
            forca * 1_000.0, momento * 1_000.0
        )

elif geometria == "Pinos ou parafusos sob cisalhamento":
    with st.container(border=True):
        st.subheader("Pinos ou parafusos sob cisalhamento direto")
        st.latex(
            r"\tau_{média}=\frac{F}{n_p\,n_c\,(\pi d^2/4)}"
        )
        entradas = st.columns(4)
        with entradas[0]:
            forca = st.number_input(
                "Força total F (kN)", value=20.0, step=1.0
            )
        with entradas[1]:
            diametro = st.number_input(
                "Diâmetro resistente d (mm)",
                min_value=0.001,
                value=10.0,
                step=1.0,
            )
        with entradas[2]:
            numero_pinos = st.number_input(
                "Número de pinos", min_value=1, value=1, step=1
            )
        with entradas[3]:
            corte = st.segmented_control(
                "Planos de corte",
                ["Simples", "Duplo"],
                default="Simples",
                required=True,
                width="stretch",
            )
        planos = 1 if corte == "Simples" else 2
        estado = modelos.pino_cisalhamento(
            forca * 1_000.0, diametro, int(numero_pinos), planos
        )

elif geometria == "Vaso cilíndrico de parede fina":
    with st.container(border=True):
        st.subheader("Tubo ou vaso cilíndrico de parede fina")
        st.latex(
            r"\sigma_\theta=\frac{pD}{2t},\quad "
            r"\sigma_{long}=\frac{pD}{4t}+\frac{F}{\pi Dt},\quad "
            r"\tau=\frac{2T}{\pi D^2t}"
        )
        dimensoes = st.columns(3)
        with dimensoes[0]:
            pressao = st.number_input(
                "Pressão interna p (MPa)",
                min_value=0.0,
                value=2.0,
                step=0.1,
            )
        with dimensoes[1]:
            diametro = st.number_input(
                "Diâmetro médio D (mm)",
                min_value=0.001,
                value=500.0,
                step=10.0,
            )
        with dimensoes[2]:
            espessura = st.number_input(
                "Espessura t (mm)",
                min_value=0.001,
                value=5.0,
                step=0.5,
            )
        adicionais = st.columns(3)
        with adicionais[0]:
            fechado = st.toggle(
                "Extremidades fechadas",
                value=True,
                help="Inclui a tensão longitudinal causada pela pressão.",
            )
        with adicionais[1]:
            forca = st.number_input(
                "Força axial adicional F (kN)", value=0.0, step=1.0
            )
        with adicionais[2]:
            torque = st.number_input(
                "Torque adicional T (N·m)", value=0.0, step=10.0
            )
        estado = modelos.tubo_fino_pressao_axial_torcao(
            pressao, diametro, espessura, fechado,
            forca * 1_000.0, torque * 1_000.0
        )
        mostrar_validacao_parede_fina(diametro, espessura)
        st.caption("Mapeamento: x = longitudinal; y = circunferencial.")

else:
    with st.container(border=True):
        st.subheader("Vaso esférico de parede fina")
        st.latex(r"\sigma_x=\sigma_y=\frac{pD}{4t}")
        dimensoes = st.columns(3)
        with dimensoes[0]:
            pressao = st.number_input(
                "Pressão interna p (MPa)",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key="assistente_esfera_pressao",
            )
        with dimensoes[1]:
            diametro = st.number_input(
                "Diâmetro médio D (mm)",
                min_value=0.001,
                value=500.0,
                step=10.0,
                key="assistente_esfera_diametro",
            )
        with dimensoes[2]:
            espessura = st.number_input(
                "Espessura t (mm)",
                min_value=0.001,
                value=5.0,
                step=0.5,
                key="assistente_esfera_espessura",
            )
        estado = modelos.vaso_esferico_parede_fina(
            pressao, diametro, espessura
        )
        mostrar_validacao_parede_fina(diametro, espessura)

if estado is not None:
    st.markdown("##### Passo 3 · Resultado")
    st.subheader("Estado de tensão calculado")
    st.caption(
        "**σx** e **σy** indicam o quanto o material está sendo esticado "
        "(valor positivo) ou comprimido (valor negativo) em cada direção. "
        "**τxy** indica o quanto está sendo torcido/cisalhado nesse ponto."
    )
    with st.container(horizontal=True):
        st.metric("σx", f"{estado.sigma_x:.3f} MPa", border=True)
        st.metric("σy", f"{estado.sigma_y:.3f} MPa", border=True)
        st.metric("τxy", f"{estado.tau_xy:.3f} MPa", border=True)

    with st.container(border=True):
        st.markdown(f"**Modelo:** {estado.descricao}")
        tabela_saida = pd.DataFrame(
            {
                "Campo no Círculo de Mohr": ["σx", "σy", "τxy"],
                "Valor (MPa)": [
                    estado.sigma_x,
                    estado.sigma_y,
                    estado.tau_xy,
                ],
            }
        )
        st.dataframe(
            tabela_saida,
            hide_index=True,
            column_config={
                "Valor (MPa)": st.column_config.NumberColumn(format="%.4f"),
            },
        )

    with st.expander(
        "Hipóteses deste cálculo",
        icon=":material/fact_check:",
    ):
        for hipotese in estado.hipoteses:
            st.markdown(f"- {hipotese}")
        st.warning(
            "Os modelos não incluem automaticamente entalhes, furos, soldas, "
            "contato, tensões residuais ou concentrações de tensão.",
            icon=":material/warning:",
        )

    registro_cargas = construir_registro_tecnico(
        modulo="Assistente de cargas",
        titulo=f"Conversão de cargas em tensões — {geometria}",
        status="Calculado",
        resumo=estado.descricao,
        entradas={
            "modelo": geometria,
            "descrição_do_modelo": estado.descricao,
        },
        resultados={
            "sigma_x_MPa": estado.sigma_x,
            "sigma_y_MPa": estado.sigma_y,
            "tau_xy_MPa": estado.tau_xy,
        },
        premissas=list(estado.hipoteses),
        alertas=[
            "Entalhes, furos, soldas, contato, tensões residuais e concentrações não são incluídos automaticamente."
        ],
        referencias=["Confirmar dimensões, combinações, condições de contorno e norma aplicável."],
        conclusao="Estado de tensões calculado; encaminhar para verificação estática, Mohr ou critério específico do projeto.",
    )
    botao_registrar_calculo(
        registro_cargas,
        key=f"registrar_cargas_{geometria}",
        rotulo="Registrar estado de tensões no projeto",
        tipo="secondary",
    )

    if st.button(
        "Enviar para o Círculo de Mohr",
        type="primary",
        icon=":material/arrow_forward:",
        width="stretch",
    ):
        enviar_para_mohr(estado)

st.caption(
    "Modelos elementares de resistência dos materiais. Para projeto real, "
    "confirme as hipóteses, fatores de concentração e a norma aplicável."
)
