import pandas as pd
import streamlit as st

from components import load_models as catalogo
from components.project_tools import (
    botao_registrar_calculo,
    construir_registro_tecnico,
    id_registro_existente,
)
from components.ui import cabecalho_pagina, configurar_pagina, fronteira_modelo
from core import additional_load_models as modelos
from core import load_to_stress as cargas

configurar_pagina("Assistente de cargas", ":material/manufacturing:")


def enviar_para_mohr(
    estado: cargas.EstadoPlanoCalculado, *, origem_id: str | None
) -> None:
    """Guarda o estado calculado e abre a análise do Círculo de Mohr."""
    st.session_state["mohr_assistente_2d"] = {
        "sigma_x": estado.sigma_x,
        "sigma_y": estado.sigma_y,
        "tau_xy": estado.tau_xy,
        "descricao": estado.descricao,
        "origem_registro_id": origem_id,
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


def enviar_para_estatica(
    estado: cargas.EstadoPlanoCalculado, *, origem_id: str | None
) -> None:
    """Guarda o estado calculado e abre a Análise estática."""
    st.session_state["estatica_sigma_x"] = estado.sigma_x
    st.session_state["estatica_sigma_y"] = estado.sigma_y
    st.session_state["estatica_tau_xy"] = estado.tau_xy
    st.session_state["estatica_origem_registro_id"] = origem_id
    st.switch_page("app_pages/analise_estatica.py")


def selecionar_face(chave: str) -> str:
    rotulo = st.segmented_control(
        "Ponto na flexão",
        ["Lado tracionado", "Lado comprimido"],
        default="Lado tracionado",
        required=True,
        width="stretch",
        key=chave,
        persist_state="session",
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
    modulo_id="assistente_cargas",
)
st.info(
    "**Para que serve:** você tem forças, momentos, torques ou pressão medidos "
    "ou definidos em projeto, mas precisa saber o quanto o material está sendo "
    "esticado, comprimido ou torcido em um ponto específico. Este assistente faz "
    "essa conversão para você, sem precisar montar as fórmulas manualmente.",
    icon=":material/lightbulb:",
)
st.caption(
    "Use forças em kN, momentos e torques em N·m e dimensões em mm — "
    "salvo quando o próprio campo indicar outra unidade. "
    "A saída é calculada em MPa (megapascal)."
)

envelope_referencia = st.session_state.get("cargas_envelope_projeto")
if envelope_referencia and envelope_referencia.get("componentes"):
    with st.expander(
        f":material/layers: Consultar o envelope de {envelope_referencia.get('projeto_nome') or 'Casos de carga'}",
        expanded=False,
        icon=":material/layers:",
    ):
        st.caption(
            "Valores governantes calculados em **Casos e combinações de carga**. "
            "Escolha abaixo qual eixo corresponde ao esforço do modelo selecionado — "
            "o programa não faz essa correspondência sozinho, pois depende de qual "
            "eixo local desta peça cada resultante representa."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Componente": dados["rotulo"],
                        "Valor governante": dados["valor_governante"],
                        "Unidade": dados["unidade"],
                        "Cenário governante": dados["cenario_governante"],
                    }
                    for dados in envelope_referencia["componentes"].values()
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Valor governante": st.column_config.NumberColumn(format="%.4g"),
            },
        )
        st.page_link(
            "app_pages/casos_carga.py",
            label="Reabrir Casos e combinações de carga",
            icon=":material/arrow_back:",
        )

def _ao_trocar_grupo() -> None:
    """Mantém o modelo coerente com o grupo de peça recém-escolhido."""
    grupo_novo = st.session_state.get("assistente_grupo")
    modelos_do_grupo = catalogo.GRUPOS.get(grupo_novo, [])
    if modelos_do_grupo and st.session_state.get(
        "assistente_geometria"
    ) not in modelos_do_grupo:
        st.session_state["assistente_geometria"] = modelos_do_grupo[0]


def _ao_trocar_modelo() -> None:
    """Promove a escolha do rádio à chave canônica lida pelas outras páginas."""
    st.session_state["assistente_geometria"] = st.session_state[
        "assistente_modelo"
    ]


st.markdown("##### Passo 1 · Escolha a peça e o tipo de carregamento")

# `assistente_geometria` é a chave canônica: é ela que o Assistente de projeto
# pré-preenche e ela que sobrevive à navegação entre páginas. Os dois widgets
# abaixo são espelhos dela, re-semeados a cada execução.
modelo_ativo = catalogo.resolver_chave(st.session_state.get("assistente_geometria"))
st.session_state["assistente_geometria"] = modelo_ativo
st.session_state["assistente_grupo"] = catalogo.CATALOGO[modelo_ativo].grupo

grupo = st.pills(
    "Que tipo de peça você está analisando?",
    list(catalogo.GRUPOS),
    required=True,
    key="assistente_grupo",
    on_change=_ao_trocar_grupo,
)
opcoes_do_grupo = catalogo.GRUPOS[grupo]
if modelo_ativo not in opcoes_do_grupo:
    modelo_ativo = opcoes_do_grupo[0]
    st.session_state["assistente_geometria"] = modelo_ativo

st.session_state["assistente_modelo"] = modelo_ativo
geometria = st.radio(
    "Como ela está carregada?",
    opcoes_do_grupo,
    captions=[catalogo.CATALOGO[chave].resumo for chave in opcoes_do_grupo],
    help="Escolha o modelo que melhor representa a seção no ponto analisado.",
    key="assistente_modelo",
    on_change=_ao_trocar_modelo,
)
st.session_state["assistente_geometria"] = geometria
modelo_escolhido = catalogo.CATALOGO[geometria]

catalogo.cartao_modelo(modelo_escolhido)

with st.expander(
    "Comparar os modelos disponíveis",
    icon=":material/table_rows:",
):
    st.caption(
        "Use a coluna **Devolve** para decidir antes de preencher: um modelo "
        "que só devolve σx chega ao Círculo de Mohr como estado uniaxial."
    )
    st.dataframe(
        pd.DataFrame(catalogo.tabela_comparativa()),
        hide_index=True,
        width="stretch",
    )

st.markdown("##### Passo 2 · Informe os valores")

estado = None
alerta_flambagem = False

if geometria == "Barra sob carga axial":
    with st.container(border=True):
        entradas = st.columns(2)
        with entradas[0]:
            forca_kN = st.number_input(
                "Força axial F (kN)",
                value=20.0,
                step=1.0,
                help="Positiva para tração e negativa para compressão.",
                key="assistente_barra_forca",
                persist_state="session",
            )
        with entradas[1]:
            area_mm2 = st.number_input(
                "Área da seção A (mm²)",
                min_value=0.001,
                value=200.0,
                step=10.0,
                key="assistente_barra_area",
                persist_state="session",
            )
        estado = cargas.barra_axial(forca_kN * 1_000.0, area_mm2)
        alerta_flambagem = forca_kN < 0

elif geometria == "Barra sob carga axial excêntrica":
    with st.container(border=True):
        dimensoes = st.columns(2)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b, direção z (mm)",
                min_value=0.001,
                value=60.0,
                step=5.0,
                key="assistente_exc_largura",
                persist_state="session",
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h, direção y (mm)",
                min_value=0.001,
                value=100.0,
                step=5.0,
                key="assistente_exc_altura",
                persist_state="session",
            )
        linha = st.columns(3)
        with linha[0]:
            forca_kN = st.number_input(
                "Força axial F (kN)",
                value=-150.0,
                step=5.0,
                help="Positiva para tração e negativa para compressão.",
                key="assistente_exc_forca",
                persist_state="session",
            )
        with linha[1]:
            ey = st.number_input(
                "Excentricidade ey (mm)",
                value=20.0,
                step=1.0,
                help="Deslocamento da carga na direção y, a partir do centroide.",
                key="assistente_exc_ey",
                persist_state="session",
            )
        with linha[2]:
            ez = st.number_input(
                "Excentricidade ez (mm)",
                value=0.0,
                step=1.0,
                help="Deslocamento da carga na direção z, a partir do centroide.",
                key="assistente_exc_ez",
                persist_state="session",
            )
        ponto = st.segmented_control(
            "Ponto avaliado",
            ["Canto do lado da carga", "Canto oposto", "Personalizado"],
            default="Canto do lado da carga",
            required=True,
            width="stretch",
            key="assistente_exc_ponto",
            persist_state="session",
        )
        sinal_y = 1.0 if ey >= 0 else -1.0
        sinal_z = 1.0 if ez >= 0 else -1.0
        if ponto == "Canto do lado da carga":
            y, z = sinal_y * altura / 2.0, sinal_z * largura / 2.0
        elif ponto == "Canto oposto":
            y, z = -sinal_y * altura / 2.0, -sinal_z * largura / 2.0
        else:
            coordenadas = st.columns(2)
            with coordenadas[0]:
                y = st.number_input(
                    "Coordenada y (mm)",
                    min_value=-altura / 2.0,
                    max_value=altura / 2.0,
                    value=altura / 2.0,
                    step=max(0.1, altura / 20.0),
                    key="assistente_exc_y",
                    persist_state="session",
                )
            with coordenadas[1]:
                z = st.number_input(
                    "Coordenada z (mm)",
                    min_value=-largura / 2.0,
                    max_value=largura / 2.0,
                    value=0.0,
                    step=max(0.1, largura / 20.0),
                    key="assistente_exc_z",
                    persist_state="session",
                )
        estado = modelos.barra_axial_excentrica(
            forca_kN * 1_000.0, largura, altura, ey, ez, y, z
        )
        alerta_flambagem = forca_kN < 0

        fator_nucleo = modelos.fator_nucleo_central(largura, altura, ey, ez)
        st.metric("Posição no núcleo central", f"{fator_nucleo:.2f}", border=True)
        if fator_nucleo > 1.0:
            st.warning(
                "A carga está fora do núcleo central: há inversão de sinal na "
                "seção, ou seja, parte dela traciona enquanto o resto comprime. "
                "Em peças de concreto ou em apoios sem aderência isso significa "
                "perda de contato.",
                icon=":material/warning:",
            )
        else:
            st.success(
                "A carga está dentro do núcleo central: a seção inteira "
                "trabalha com o mesmo sinal.",
                icon=":material/check_circle:",
            )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm, z = {z:.3f} mm.")

elif geometria == "Eixo circular maciço":
    with st.container(border=True):
        linha_1 = st.columns(2)
        with linha_1[0]:
            diametro = st.number_input(
                "Diâmetro d (mm)",
                min_value=0.001,
                value=30.0,
                step=1.0,
                key="assistente_macico_diametro",
                persist_state="session",
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
                key="assistente_macico_forca",
                persist_state="session",
            )
        with linha_2[1]:
            momento = st.number_input(
                "Momento fletor |M| (N·m)",
                min_value=0.0,
                value=500.0,
                step=10.0,
                key="assistente_macico_momento",
                persist_state="session",
            )
        with linha_2[2]:
            torque = st.number_input(
                "Torque T (N·m)",
                value=300.0,
                step=10.0,
                help="O sinal define o sinal de τxy.",
                key="assistente_macico_torque",
                persist_state="session",
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
        linha_1 = st.columns(3)
        with linha_1[0]:
            de = st.number_input(
                "Diâmetro externo De (mm)",
                min_value=0.002,
                value=40.0,
                step=1.0,
                key="assistente_vazado_de",
                persist_state="session",
            )
        with linha_1[1]:
            di = st.number_input(
                "Diâmetro interno Di (mm)",
                min_value=0.0,
                max_value=de - 0.001,
                value=min(25.0, de - 0.001),
                step=1.0,
                key="assistente_vazado_di",
                persist_state="session",
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
                persist_state="session",
            )
        with linha_2[1]:
            momento = st.number_input(
                "Momento fletor |M| (N·m)",
                min_value=0.0,
                value=500.0,
                step=10.0,
                key="assistente_vazado_momento",
                persist_state="session",
            )
        with linha_2[2]:
            torque = st.number_input(
                "Torque T (N·m)",
                value=300.0,
                step=10.0,
                key="assistente_vazado_torque",
                persist_state="session",
            )
        estado = modelos.eixo_circular_vazado(
            de, di, forca * 1_000.0, momento * 1_000.0, torque * 1_000.0, face
        )

elif geometria == "Mola helicoidal de compressão":
    with st.container(border=True):
        linha = st.columns(3)
        with linha[0]:
            forca_mola = st.number_input(
                "Força na mola F (N)",
                value=500.0,
                step=10.0,
                help="Em newtons, não em kN — molas costumam trabalhar nessa faixa.",
                key="assistente_mola_forca",
                persist_state="session",
            )
        with linha[1]:
            diametro_medio = st.number_input(
                "Diâmetro médio da mola D (mm)",
                min_value=0.002,
                value=40.0,
                step=1.0,
                help="Medido no eixo do fio, não na face externa das espiras.",
                key="assistente_mola_diametro",
                persist_state="session",
            )
        with linha[2]:
            diametro_fio = st.number_input(
                "Diâmetro do fio d (mm)",
                min_value=0.001,
                max_value=diametro_medio - 0.001,
                value=min(5.0, diametro_medio / 4.0),
                step=0.5,
                key="assistente_mola_fio",
                persist_state="session",
            )
        usar_wahl = st.toggle(
            "Aplicar o fator de Wahl",
            value=True,
            help=(
                "Corrige a curvatura da espira e o cisalhamento direto. "
                "Sem ele a tensão sai subestimada, sobretudo em molas "
                "de índice baixo."
            ),
            key="assistente_mola_wahl",
            persist_state="session",
        )
        estado = modelos.mola_helicoidal(
            forca_mola, diametro_medio, diametro_fio, usar_wahl
        )
        indice = modelos.indice_mola(diametro_medio, diametro_fio)
        medidas = st.columns(2)
        with medidas[0]:
            st.metric("Índice de mola C = D/d", f"{indice:.2f}", border=True)
        with medidas[1]:
            st.metric(
                "Fator de Wahl K",
                f"{modelos.fator_wahl(indice):.3f}" if usar_wahl else "1,000",
                border=True,
            )
        if not 4.0 <= indice <= 12.0:
            st.warning(
                "O índice de mola está fora da faixa usual de 4 a 12. Abaixo "
                "de 4 a mola fica difícil de enrolar e muito sensível à "
                "curvatura; acima de 12 ela tende a emaranhar e a flambar.",
                icon=":material/warning:",
            )

elif geometria == "Viga de seção retangular":
    with st.container(border=True):
        dimensoes = st.columns(2)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b (mm)",
                min_value=0.001,
                value=20.0,
                step=1.0,
                key="assistente_viga_largura",
                persist_state="session",
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h (mm)",
                min_value=0.001,
                value=40.0,
                step=1.0,
                key="assistente_viga_altura",
                persist_state="session",
            )
        posicao = st.selectbox(
            "Ponto na altura da seção",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            help="y é positivo para a fibra superior.",
            key="assistente_viga_posicao",
            persist_state="session",
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
                key="assistente_viga_y",
                persist_state="session",
            )
        linha = st.columns(3)
        with linha[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_viga_forca",
                persist_state="session",
            )
        with linha[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=500.0,
                step=10.0,
                help="Momento positivo comprime a região de y positivo.",
                key="assistente_viga_momento",
                persist_state="session",
            )
        with linha[2]:
            cortante = st.number_input(
                "Força cortante V (kN)",
                value=1.0,
                step=0.5,
                help="O sinal define o sinal de τxy.",
                key="assistente_viga_cortante",
                persist_state="session",
            )
        estado = cargas.viga_retangular(
            largura, altura, y, forca * 1_000.0, momento * 1_000.0,
            cortante * 1_000.0
        )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm.")

elif geometria == "Seção retangular com flexão biaxial":
    with st.container(border=True):
        dimensoes = st.columns(2)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b, direção z (mm)",
                min_value=0.001,
                value=40.0,
                step=1.0,
                key="assistente_biaxial_largura",
                persist_state="session",
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h, direção y (mm)",
                min_value=0.001,
                value=60.0,
                step=1.0,
                key="assistente_biaxial_altura",
                persist_state="session",
            )
        ponto = st.columns(2)
        with ponto[0]:
            y = st.number_input(
                "Coordenada y (mm)",
                min_value=-altura / 2.0,
                max_value=altura / 2.0,
                value=altura / 2.0,
                step=max(0.1, altura / 20.0),
                key="assistente_biaxial_y",
                persist_state="session",
            )
        with ponto[1]:
            z = st.number_input(
                "Coordenada z (mm)",
                min_value=-largura / 2.0,
                max_value=largura / 2.0,
                value=largura / 2.0,
                step=max(0.1, largura / 20.0),
                key="assistente_biaxial_z",
                persist_state="session",
            )
        linha = st.columns(3)
        with linha[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_biaxial_forca",
                persist_state="session",
            )
        with linha[1]:
            my = st.number_input(
                "Momento My (N·m)",
                value=200.0,
                step=10.0,
                key="assistente_biaxial_my",
                persist_state="session",
            )
        with linha[2]:
            mz = st.number_input(
                "Momento Mz (N·m)",
                value=500.0,
                step=10.0,
                key="assistente_biaxial_mz",
                persist_state="session",
            )
        estado = modelos.secao_retangular_flexao_biaxial(
            largura, altura, y, z, forca * 1_000.0,
            my * 1_000.0, mz * 1_000.0
        )

elif geometria == catalogo.MODELO_SECAO_I:
    with st.container(border=True):
        dimensoes = st.columns(4)
        with dimensoes[0]:
            altura = st.number_input(
                "Altura total h (mm)",
                min_value=0.01,
                value=200.0,
                step=5.0,
                key="assistente_i_altura",
                persist_state="session",
            )
        with dimensoes[1]:
            mesa = st.number_input(
                "Largura da mesa b (mm)",
                min_value=0.01,
                value=100.0,
                step=5.0,
                key="assistente_i_mesa",
                persist_state="session",
            )
        with dimensoes[2]:
            t_mesa = st.number_input(
                "Espessura da mesa tf (mm)",
                min_value=0.001,
                max_value=altura / 2.0 - 0.001,
                value=min(10.0, altura / 4.0),
                step=1.0,
                key="assistente_i_t_mesa",
                persist_state="session",
            )
        with dimensoes[3]:
            t_alma = st.number_input(
                "Espessura da alma tw (mm)",
                min_value=0.001,
                max_value=mesa - 0.001,
                value=min(6.0, mesa / 2.0),
                step=1.0,
                key="assistente_i_t_alma",
                persist_state="session",
            )
        ponto = st.selectbox(
            "Ponto na altura",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            help=(
                "A flexão é máxima nas fibras extremas; o cisalhamento da "
                "alma é máximo no centroide."
            ),
            key="assistente_i_ponto",
            persist_state="session",
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
                key="assistente_i_y",
                persist_state="session",
            )
        cargas_i = st.columns(3)
        with cargas_i[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_i_forca",
                persist_state="session",
            )
        with cargas_i[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=5_000.0,
                step=100.0,
                key="assistente_i_momento",
                persist_state="session",
            )
        with cargas_i[2]:
            cortante = st.number_input(
                "Força cortante V (kN)",
                value=0.0,
                step=1.0,
                help="O sinal define o sinal de τxy.",
                key="assistente_i_cortante",
                persist_state="session",
            )
        estado = modelos.secao_i_flexao(
            altura, mesa, t_mesa, t_alma, y,
            forca * 1_000.0, momento * 1_000.0, cortante * 1_000.0
        )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm.")

elif geometria == "Perfil U sob força axial, flexão e cortante":
    with st.container(border=True):
        dimensoes = st.columns(4)
        with dimensoes[0]:
            altura = st.number_input(
                "Altura total h (mm)",
                min_value=0.01,
                value=200.0,
                step=5.0,
                key="assistente_u_altura",
                persist_state="session",
            )
        with dimensoes[1]:
            mesa = st.number_input(
                "Largura da mesa bf (mm)",
                min_value=0.01,
                value=75.0,
                step=5.0,
                help="Medida da face externa da alma até a ponta da mesa.",
                key="assistente_u_mesa",
                persist_state="session",
            )
        with dimensoes[2]:
            t_mesa = st.number_input(
                "Espessura da mesa tf (mm)",
                min_value=0.001,
                max_value=altura / 2.0 - 0.001,
                value=min(10.0, altura / 4.0),
                step=0.5,
                key="assistente_u_t_mesa",
                persist_state="session",
            )
        with dimensoes[3]:
            t_alma = st.number_input(
                "Espessura da alma tw (mm)",
                min_value=0.001,
                max_value=mesa - 0.001,
                value=min(6.0, mesa / 2.0),
                step=0.5,
                key="assistente_u_t_alma",
                persist_state="session",
            )
        ponto = st.selectbox(
            "Ponto na altura",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            help=(
                "A flexão é máxima nas fibras extremas; o cisalhamento da "
                "alma é máximo no centroide."
            ),
            key="assistente_u_ponto",
            persist_state="session",
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
                key="assistente_u_y",
                persist_state="session",
            )
        esforcos = st.columns(3)
        with esforcos[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_u_forca",
                persist_state="session",
            )
        with esforcos[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=5_000.0,
                step=100.0,
                help="Flexão em torno do eixo forte, o de simetria.",
                key="assistente_u_momento",
                persist_state="session",
            )
        with esforcos[2]:
            cortante = st.number_input(
                "Força cortante V (kN)",
                value=50.0,
                step=1.0,
                help="O sinal define o sinal de τxy.",
                key="assistente_u_cortante",
                persist_state="session",
            )
        estado = modelos.secao_u_flexao(
            altura, mesa, t_mesa, t_alma, y,
            forca * 1_000.0, momento * 1_000.0, cortante * 1_000.0
        )
        propriedades_u = modelos.propriedades_perfil_u(
            altura, mesa, t_mesa, t_alma
        )
        medidas = st.columns(3)
        with medidas[0]:
            st.metric(
                "Área da seção",
                f"{propriedades_u['area'] / 100.0:.2f} cm²",
                border=True,
            )
        with medidas[1]:
            st.metric(
                "Centroide, a partir da face externa da alma",
                f"{propriedades_u['z_centroide']:.2f} mm",
                border=True,
            )
        with medidas[2]:
            st.metric(
                "Centro de cisalhamento, a partir da linha média da alma",
                f"{propriedades_u['excentricidade_centro_cisalhamento']:.2f} mm",
                border=True,
            )
        if cortante != 0.0:
            st.warning(
                "O centro de cisalhamento do perfil U fica fora da alma, do "
                "lado oposto ao das mesas. Um cortante que não passe por esse "
                "ponto acrescenta torção que este modelo não calcula — "
                "reposicione a carga, use contenção lateral ou trate a torção "
                "à parte.",
                icon=":material/warning:",
            )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm.")

elif geometria == "Cantoneira de abas iguais":
    with st.container(border=True):
        dimensoes = st.columns(2)
        with dimensoes[0]:
            aba = st.number_input(
                "Comprimento da aba b (mm)",
                min_value=0.002,
                value=100.0,
                step=5.0,
                key="assistente_cantoneira_aba",
                persist_state="session",
            )
        with dimensoes[1]:
            espessura = st.number_input(
                "Espessura t (mm)",
                min_value=0.001,
                max_value=aba - 0.001,
                value=min(10.0, aba / 10.0),
                step=0.5,
                key="assistente_cantoneira_espessura",
                persist_state="session",
            )
        propriedades_l = modelos.propriedades_cantoneira_abas_iguais(
            aba, espessura
        )
        centroide = propriedades_l["centroide"]
        ponto = st.selectbox(
            "Ponto avaliado",
            [
                "Ponta da aba vertical",
                "Ponta da aba horizontal",
                "Canto externo",
                "Personalizado",
            ],
            help=(
                "Com a linha neutra inclinada, o ponto mais solicitado nem "
                "sempre é o mesmo — confira os três cantos."
            ),
            key="assistente_cantoneira_ponto",
            persist_state="session",
        )
        if ponto == "Ponta da aba vertical":
            y, z = aba - centroide, -centroide
        elif ponto == "Ponta da aba horizontal":
            y, z = -centroide, aba - centroide
        elif ponto == "Canto externo":
            y, z = -centroide, -centroide
        else:
            coordenadas = st.columns(2)
            with coordenadas[0]:
                y = st.number_input(
                    "Coordenada y (mm)",
                    min_value=-centroide,
                    max_value=aba - centroide,
                    value=aba - centroide,
                    step=max(0.1, aba / 20.0),
                    key="assistente_cantoneira_y",
                    persist_state="session",
                )
            with coordenadas[1]:
                z = st.number_input(
                    "Coordenada z (mm)",
                    min_value=-centroide,
                    max_value=aba - centroide,
                    value=-centroide,
                    step=max(0.1, aba / 20.0),
                    key="assistente_cantoneira_z",
                    persist_state="session",
                )
        esforcos = st.columns(3)
        with esforcos[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_cantoneira_forca",
                persist_state="session",
            )
        with esforcos[1]:
            my = st.number_input(
                "Momento My (N·m)",
                value=0.0,
                step=10.0,
                help=(
                    "Momento em torno do eixo y (vertical): faz a tensão "
                    "variar ao longo de z."
                ),
                key="assistente_cantoneira_my",
                persist_state="session",
            )
        with esforcos[2]:
            mz = st.number_input(
                "Momento Mz (N·m)",
                value=1_000.0,
                step=10.0,
                help=(
                    "Momento em torno do eixo z (horizontal): faz a "
                    "tensão variar ao longo de y."
                ),
                key="assistente_cantoneira_mz",
                persist_state="session",
            )
        estado = modelos.cantoneira_abas_iguais(
            aba, espessura, y, z, forca * 1_000.0,
            my * 1_000.0, mz * 1_000.0
        )
        inclinacao = modelos.angulo_linha_neutra(
            my * 1_000.0,
            mz * 1_000.0,
            propriedades_l["inercia_y"],
            propriedades_l["inercia_z"],
            propriedades_l["produto_inercia"],
        )
        medidas = st.columns(3)
        with medidas[0]:
            st.metric(
                "Área da seção",
                f"{propriedades_l['area'] / 100.0:.2f} cm²",
                border=True,
            )
        with medidas[1]:
            st.metric(
                "Centroide, a partir das faces externas",
                f"{centroide:.2f} mm",
                border=True,
            )
        with medidas[2]:
            st.metric(
                "Inclinação da linha neutra",
                f"{inclinacao:.1f}°",
                border=True,
            )
        inercias = st.columns(4)
        with inercias[0]:
            st.metric(
                "Iy", f"{propriedades_l['inercia_y'] / 1e4:.1f} cm⁴",
                border=True,
            )
        with inercias[1]:
            st.metric(
                "Iz", f"{propriedades_l['inercia_z'] / 1e4:.1f} cm⁴",
                border=True,
            )
        with inercias[2]:
            st.metric(
                "Iyz", f"{propriedades_l['produto_inercia'] / 1e4:.1f} cm⁴",
                border=True,
            )
        with inercias[3]:
            st.metric(
                "Imáx / Imín (cm⁴)",
                f"{propriedades_l['inercia_maxima'] / 1e4:.0f} / "
                f"{propriedades_l['inercia_minima'] / 1e4:.0f}",
                help=(
                    "Inércias nos eixos principais, a 45° das abas. É entre "
                    "elas que a flexão real se distribui."
                ),
                border=True,
            )
        if (my != 0.0 or mz != 0.0) and abs(inclinacao) > 1.0:
            st.warning(
                f"A linha neutra está a {inclinacao:.1f}° do eixo z, e não "
                "alinhada com ele: a cantoneira flexiona para fora do plano "
                "de carregamento. Se a peça não estiver contida lateralmente, "
                "a flecha e a tensão reais serão maiores que as de uma flexão "
                "reta — verifique também os três cantos, porque o mais "
                "solicitado muda com a direção do momento.",
                icon=":material/warning:",
            )
        else:
            st.info(
                "Sem momento aplicado, a linha neutra não é definida pela "
                "flexão. Informe My ou Mz para ver a flexão oblíqua.",
                icon=":material/info:",
            )
        st.caption(
            f"Ponto avaliado: y = {y:.3f} mm, z = {z:.3f} mm, medidos a "
            "partir do centroide."
        )

elif geometria == "Perfil tubular retangular (caixão)":
    with st.container(border=True):
        dimensoes = st.columns(3)
        with dimensoes[0]:
            largura = st.number_input(
                "Largura b, direção z (mm)",
                min_value=0.003,
                value=60.0,
                step=5.0,
                key="assistente_caixao_largura",
                persist_state="session",
            )
        with dimensoes[1]:
            altura = st.number_input(
                "Altura h, direção y (mm)",
                min_value=0.003,
                value=100.0,
                step=5.0,
                key="assistente_caixao_altura",
                persist_state="session",
            )
        with dimensoes[2]:
            espessura = st.number_input(
                "Espessura da parede t (mm)",
                min_value=0.001,
                max_value=min(largura, altura) / 2.0 - 0.001,
                value=min(5.0, min(largura, altura) / 8.0),
                step=0.5,
                key="assistente_caixao_espessura",
                persist_state="session",
            )
        posicao = st.selectbox(
            "Ponto na altura da seção",
            ["Fibra superior", "Centroide", "Fibra inferior", "Personalizado"],
            key="assistente_caixao_posicao",
            persist_state="session",
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
                key="assistente_caixao_y",
                persist_state="session",
            )
        linha = st.columns(3)
        with linha[0]:
            forca = st.number_input(
                "Força axial F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_caixao_forca",
                persist_state="session",
            )
        with linha[1]:
            momento = st.number_input(
                "Momento fletor M (N·m)",
                value=2_000.0,
                step=50.0,
                help="Momento positivo comprime a região de y positivo.",
                key="assistente_caixao_momento",
                persist_state="session",
            )
        with linha[2]:
            torque = st.number_input(
                "Torque T (N·m)",
                value=500.0,
                step=10.0,
                help="O sinal define o sinal de τxy.",
                key="assistente_caixao_torque",
                persist_state="session",
            )
        estado = modelos.secao_tubular_retangular(
            largura, altura, espessura, y,
            forca * 1_000.0, momento * 1_000.0, torque * 1_000.0
        )
        relacao_parede = min(largura, altura) / espessura
        st.metric(
            "Relação menor lado / t", f"{relacao_parede:.1f}", border=True
        )
        if relacao_parede < 10.0:
            st.warning(
                "Com a parede tão grossa em relação ao lado, a fórmula de "
                "Bredt perde precisão — ela supõe parede fina e tensão "
                "constante ao longo da espessura.",
                icon=":material/warning:",
            )
        st.caption(f"Ponto avaliado: y = {y:.3f} mm.")

elif geometria == "Pinos ou parafusos sob cisalhamento":
    with st.container(border=True):
        entradas = st.columns(4)
        with entradas[0]:
            forca = st.number_input(
                "Força total F (kN)",
                value=20.0,
                step=1.0,
                key="assistente_pino_forca",
                persist_state="session",
            )
        with entradas[1]:
            diametro = st.number_input(
                "Diâmetro resistente d (mm)",
                min_value=0.001,
                value=10.0,
                step=1.0,
                key="assistente_pino_diametro",
                persist_state="session",
            )
        with entradas[2]:
            numero_pinos = st.number_input(
                "Número de pinos",
                min_value=1,
                value=1,
                step=1,
                key="assistente_pino_numero",
                persist_state="session",
            )
        with entradas[3]:
            corte = st.segmented_control(
                "Planos de corte",
                ["Simples", "Duplo"],
                default="Simples",
                required=True,
                width="stretch",
                key="assistente_pino_corte",
                persist_state="session",
            )
        planos = 1 if corte == "Simples" else 2
        estado = modelos.pino_cisalhamento(
            forca * 1_000.0, diametro, int(numero_pinos), planos
        )

elif geometria == "Vaso cilíndrico de parede fina":
    with st.container(border=True):
        dimensoes = st.columns(3)
        with dimensoes[0]:
            pressao = st.number_input(
                "Pressão interna p (MPa)",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key="assistente_cilindro_pressao",
                persist_state="session",
            )
        with dimensoes[1]:
            diametro = st.number_input(
                "Diâmetro médio D (mm)",
                min_value=0.001,
                value=500.0,
                step=10.0,
                key="assistente_cilindro_diametro",
                persist_state="session",
            )
        with dimensoes[2]:
            espessura = st.number_input(
                "Espessura t (mm)",
                min_value=0.001,
                value=5.0,
                step=0.5,
                key="assistente_cilindro_espessura",
                persist_state="session",
            )
        adicionais = st.columns(3)
        with adicionais[0]:
            fechado = st.toggle(
                "Extremidades fechadas",
                value=True,
                help="Inclui a tensão longitudinal causada pela pressão.",
                key="assistente_cilindro_fechado",
                persist_state="session",
            )
        with adicionais[1]:
            forca = st.number_input(
                "Força axial adicional F (kN)",
                value=0.0,
                step=1.0,
                key="assistente_cilindro_forca",
                persist_state="session",
            )
        with adicionais[2]:
            torque = st.number_input(
                "Torque adicional T (N·m)",
                value=0.0,
                step=10.0,
                key="assistente_cilindro_torque",
                persist_state="session",
            )
        estado = modelos.tubo_fino_pressao_axial_torcao(
            pressao, diametro, espessura, fechado,
            forca * 1_000.0, torque * 1_000.0
        )
        mostrar_validacao_parede_fina(diametro, espessura)
        st.caption("Mapeamento: x = longitudinal; y = circunferencial.")

elif geometria == "Vaso esférico de parede fina":
    with st.container(border=True):
        dimensoes = st.columns(3)
        with dimensoes[0]:
            pressao = st.number_input(
                "Pressão interna p (MPa)",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key="assistente_esfera_pressao",
                persist_state="session",
            )
        with dimensoes[1]:
            diametro = st.number_input(
                "Diâmetro médio D (mm)",
                min_value=0.001,
                value=500.0,
                step=10.0,
                key="assistente_esfera_diametro",
                persist_state="session",
            )
        with dimensoes[2]:
            espessura = st.number_input(
                "Espessura t (mm)",
                min_value=0.001,
                value=5.0,
                step=0.5,
                key="assistente_esfera_espessura",
                persist_state="session",
            )
        estado = modelos.vaso_esferico_parede_fina(
            pressao, diametro, espessura
        )
        mostrar_validacao_parede_fina(diametro, espessura)

else:
    with st.container(border=True):
        dimensoes = st.columns(4)
        with dimensoes[0]:
            pressao_interna = st.number_input(
                "Pressão interna pi (MPa)",
                value=50.0,
                step=1.0,
                key="assistente_espessa_pi",
                persist_state="session",
            )
        with dimensoes[1]:
            pressao_externa = st.number_input(
                "Pressão externa pe (MPa)",
                value=0.0,
                step=1.0,
                key="assistente_espessa_pe",
                persist_state="session",
            )
        with dimensoes[2]:
            raio_interno = st.number_input(
                "Raio interno ri (mm)",
                min_value=0.001,
                value=50.0,
                step=1.0,
                key="assistente_espessa_ri",
                persist_state="session",
            )
        with dimensoes[3]:
            raio_externo = st.number_input(
                "Raio externo re (mm)",
                min_value=raio_interno + 0.001,
                value=max(80.0, raio_interno + 0.001),
                step=1.0,
                key="assistente_espessa_re",
                persist_state="session",
            )
        posicao = st.segmented_control(
            "Ponto na espessura",
            ["Parede interna", "Parede externa", "Personalizado"],
            default="Parede interna",
            required=True,
            width="stretch",
            help=(
                "A tensão varia ao longo da parede; na face interna ela é "
                "máxima para pressão interna."
            ),
            key="assistente_espessa_posicao",
            persist_state="session",
        )
        if posicao == "Parede interna":
            raio = raio_interno
        elif posicao == "Parede externa":
            raio = raio_externo
        else:
            raio = st.number_input(
                "Raio avaliado r (mm)",
                min_value=raio_interno,
                max_value=raio_externo,
                value=raio_interno,
                step=max(0.1, (raio_externo - raio_interno) / 20.0),
                key="assistente_espessa_r",
                persist_state="session",
            )
        opcoes_extra = st.columns(2)
        with opcoes_extra[0]:
            fechado = st.toggle(
                "Extremidades fechadas",
                value=True,
                help="Inclui a tensão longitudinal gerada pelas tampas.",
                key="assistente_espessa_fechado",
                persist_state="session",
            )
        with opcoes_extra[1]:
            plano_rotulo = st.segmented_control(
                "Plano levado adiante",
                ["Radial e circunferencial", "Longitudinal e circunferencial"],
                default="Radial e circunferencial",
                required=True,
                width="stretch",
                help=(
                    "O estado aqui é triaxial e só duas componentes seguem "
                    "para o Círculo de Mohr. O plano radial–circunferencial "
                    "é o que governa o cisalhamento máximo."
                ),
                key="assistente_espessa_plano",
                persist_state="session",
            )
        plano = (
            "radial-circunferencial"
            if plano_rotulo == "Radial e circunferencial"
            else "longitudinal-circunferencial"
        )
        estado = modelos.cilindro_parede_espessa(
            pressao_interna,
            pressao_externa,
            raio_interno,
            raio_externo,
            raio,
            fechado,
            plano,
        )
        sigma_r, sigma_theta, sigma_long = modelos.tensoes_lame(
            pressao_interna,
            pressao_externa,
            raio_interno,
            raio_externo,
            raio,
            fechado,
        )
        st.caption(
            f"Tensões principais em r = {raio:.2f} mm — as três componentes, "
            "inclusive a que não segue no plano escolhido:"
        )
        with st.container(horizontal=True):
            st.metric("σr (radial)", f"{sigma_r:.3f} MPa", border=True)
            st.metric(
                "σθ (circunferencial)", f"{sigma_theta:.3f} MPa", border=True
            )
            st.metric(
                "σlong (longitudinal)", f"{sigma_long:.3f} MPa", border=True
            )
        relacao_espessura = 2.0 * raio_externo / (raio_externo - raio_interno)
        st.metric(
            "Relação De/t", f"{relacao_espessura:.1f}", border=True
        )
        if relacao_espessura >= 20.0:
            st.info(
                "Com De/t ≥ 20 o modelo de parede fina já daria um resultado "
                "equivalente e com menos entradas — considere usar o **Vaso "
                "cilíndrico de parede fina**, que também aceita torque.",
                icon=":material/lightbulb:",
            )

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

    if alerta_flambagem:
        st.warning(
            "Esta barra está sob compressão. A tensão σx isolada não indica "
            "flambagem — uma barra esbelta pode falhar por instabilidade bem "
            "antes de atingir o escoamento. Verifique o índice de esbeltez e "
            "a carga crítica de Euler no módulo **Flambagem de colunas**.",
            icon=":material/warning:",
        )
        st.page_link(
            "app_pages/flambagem_colunas.py",
            label="Abrir Flambagem de colunas",
            icon=":material/architecture:",
        )

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

    fronteira_modelo(
        [
            "Entalhes, furos, soldas, contato, tensões residuais ou concentrações de tensão.",
            "Efeitos dinâmicos, impacto ou carga variável no tempo.",
            "Combinação com outros esforços não incluídos no modelo escolhido.",
        ]
    )

    registro_cargas = construir_registro_tecnico(
        modulo="Assistente de cargas",
        modulo_id="assistente_cargas",
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

    origem_id = id_registro_existente(registro_cargas)
    if origem_id is None:
        st.caption(
            ":material/link_off: Este estado ainda não foi registrado no projeto — "
            "o repasse abaixo leva os valores, mas não uma origem rastreável. "
            "Registre acima para que o próximo módulo saiba de onde eles vieram."
        )
    destino_estatica, destino_mohr = st.columns(2)
    with destino_estatica:
        if st.button(
            "Enviar para a Análise estática",
            type="secondary",
            icon=":material/analytics:",
            width="stretch",
        ):
            enviar_para_estatica(estado, origem_id=origem_id)
    with destino_mohr:
        if st.button(
            "Enviar para o Círculo de Mohr",
            type="primary",
            icon=":material/arrow_forward:",
            width="stretch",
        ):
            enviar_para_mohr(estado, origem_id=origem_id)

st.caption(
    "Modelos elementares de resistência dos materiais. Para projeto real, "
    "confirme as hipóteses, fatores de concentração e a norma aplicável."
)
