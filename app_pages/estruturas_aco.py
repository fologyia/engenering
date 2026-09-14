import math
from dataclasses import asdict

import altair as alt
import pandas as pd
import streamlit as st

from components.project_tools import botao_registrar_calculo, construir_registro_tecnico
from components.ui import cabecalho_pagina, configurar_pagina, fronteira_modelo
from core import bolt_design as parafusos
from core import load_combinations as combinacoes
from core import nbr8800
from core import section_catalog as catalogo_perfis
from core import steel_connections as ligacoes
from core import steel_member_design as barras
from core import steel_sections as secoes
from core import structural_2d as estrutural

configurar_pagina("Estruturas de aço", ":material/domain:")


def fator_texto(valor: float) -> str:
    return "∞" if math.isinf(valor) else f"{valor:.2f}"


def mostrar_utilizacao(nome: str, utilizacao: float) -> None:
    if utilizacao <= 1.0:
        st.success(
            f"{nome}: utilização {utilizacao:.3f} — atende ao modelo informado.",
            icon=":material/check_circle:",
        )
    else:
        st.error(
            f"{nome}: utilização {utilizacao:.3f} — resistência excedida.",
            icon=":material/error:",
        )


cabecalho_pagina(
    "Estruturas de aço",
    "Perfis • barras • combinações ELU/ELS • ligações • treliças e pórticos 2D",
    categoria="Projetos",
    icone=":material/domain:",
    cor="violet",
    ajuda_modulo="Estruturas de aço",
    acoes=(("app_pages/projeto_parafusos.py", "Projeto de parafusos", ":material/build:"),),
    modulo_id="estruturas_aco",
)
st.session_state.setdefault("estrutura_aco_modulo", "1. Perfis")
st.session_state.setdefault("estrutura_nd_kN", 100.0)
st.session_state.setdefault("estrutura_mdx_kNm", 20.0)
st.session_state.setdefault("estrutura_vd_kN", 20.0)
st.session_state.setdefault("estrutura_comprimento_m", 3.0)

st.warning(
    "Ferramenta de pré-dimensionamento. Os coeficientes normativos são "
    "editáveis e devem ser conferidos na NBR 8800:2024, NBR 8681:2025 e "
    "demais normas aplicáveis. A responsabilidade do projeto permanece com "
    "profissional habilitado.",
    icon=":material/gavel:",
)

with st.expander(
    "Como usar este módulo — leia antes de começar (clique para abrir)",
    icon=":material/school:",
):
    st.markdown(
        """
Esta página **não é uma ferramenta única**: são 5 sub-ferramentas
independentes, escolhidas no seletor "Módulo" logo abaixo. O fluxo normal
de trabalho é passar por elas **nesta ordem**, copiando o resultado de uma
para o formulário da próxima — nada é preenchido automaticamente entre um
módulo e outro.
"""
    )

    st.markdown("##### 1. Perfis — só consulta")
    st.markdown(
        """
Filtre por família (I, W, U, tubo…) e escolha um perfil para ver área,
massa, Ix, Iy, Sx, Zx, rx, ry etc. Se o perfil que você precisa não está
no catálogo, abra "Criar perfil paramétrico personalizado" e digite as
dimensões (h, bf, tw, tf…) — o programa calcula as propriedades na hora.
Use este módulo só para conferir números; ele não verifica nada.
"""
    )

    st.markdown("##### 2. Barras — o cálculo principal (NBR 8800)")
    st.markdown(
        """
Verifica uma barra isolada (tração, compressão, flexão, cisalhamento e a
interação entre elas), mais a flecha. Preencha:

- **Perfil**: escolhido no catálogo do módulo 1.
- **Material**: Fy (escoamento), Fu (ruptura), E e G — o padrão já vem
  preenchido para um aço ASTM A36 comum (250 / 400 / 200 / 77).
- **Esforços de cálculo** (|Nd|, |Mdx|, |Mdy|, |Vd|): estes valores
  **já precisam estar majorados** pelos coeficientes γ da norma — é o
  módulo 3 (Combinações) que faz essa conta, não este.
- **Comprimentos**: L é o comprimento real da barra; Kx/Ky é o fator de
  comprimento efetivo (1,0 para apoio rotulado-rotulado nos dois eixos,
  maior se houver menos restrição); **Lb é diferente de L** — é só o
  trecho da mesa comprimida sem travamento lateral. Se uma laje trava a
  mesa continuamente, Lb pode ser bem menor que L, e isso aumenta bastante
  a resistência à flexão calculada.
- **Reduções** (Q, Cv, Cb, área líquida): Q = 1,0 assume seção compacta —
  o programa **não classifica a seção automaticamente**, então se o seu
  perfil for esbelto (mesa ou alma fina), reduza Q manualmente conforme a
  norma. Cb = 1,0 é uma hipótese conservadora para o gradiente de momento.
  Área líquida e Ct só importam em barras tracionadas com furos.

O resultado mostra a **utilização** de cada verificação (demanda dividida
pela resistência): valores até 1,0 atendem; acima de 1,0, a barra falha
com esses esforços e precisa de um perfil maior ou menor comprimento
destravado.
"""
    )

    st.markdown("##### 3. Combinações — majora as ações para você")
    st.markdown(
        """
Uma tabela editável onde cada linha é uma ação característica (peso
próprio, sobrecarga, vento…) com N, V, M e os coeficientes γ (ponderador)
e ψ0/ψ1/ψ2 (fatores de combinação). **Os valores padrão da tabela são só
um exemplo** — substitua pelos coeficientes da NBR 8681 aplicáveis à sua
situação de projeto antes de usar o resultado. O programa monta
automaticamente todas as combinações ELU e ELS e indica qual é a
governante. É o |N|, |V| e |M| governantes daqui que você leva para o
módulo 2 — mas repare que o maior N, o maior V e o maior M podem vir de
combinações **diferentes**; não trate os três como simultâneos sem
conferir a linha de origem na tabela.
"""
    )

    st.markdown("##### 4. Ligações — parafuso, chapa/bloco e solda")
    st.markdown(
        """
Três verificações independentes, escolhidas no segmented control interno:
ligação parafusada (tração, cisalhamento, esmagamento e interação
quadrática), chapa com bloco de cisalhamento e seção líquida, e solda de
filete. Os esforços de entrada também devem vir já majorados das
combinações de cálculo na ligação — geralmente diferentes dos esforços na
barra, porque a ligação está num ponto específico (extremidade, emenda).
"""
    )

    st.markdown("##### 5. Análise 2D — treliça ou pórtico plano")
    st.markdown(
        """
Um solver de elementos finitos simplificado. Você monta duas tabelas:
**nós** (posição x/y, quais direções estão travadas, forças aplicadas) e
**elementos** (qual nó liga a qual, perfil, módulo de elasticidade). Ao
clicar em "Analisar estrutura", o programa devolve deslocamentos, reações
de apoio e esforços internos por barra. Use isto **antes** do módulo 2
quando a peça faz parte de uma estrutura (pórtico, treliça) e não é uma
viga isolada — os esforços de cada barra que saem daqui alimentam a
verificação do módulo 2.

**Importante**: é um solver linear de primeira ordem — não considera
efeito P-Δ, imperfeições geométricas, flambagem global do conjunto nem
ligações semirrígidas. Serve para achar os esforços internos, não para
verificar estabilidade global do pórtico.
"""
    )

    st.markdown("##### Erros comuns")
    st.markdown(
        """
- Informar esforços **sem** majorar no módulo 2 (esqueceu de passar pelo
  módulo 3 primeiro).
- Confundir **L** (comprimento da barra) com **Lb** (comprimento
  destravado lateralmente) — são quase sempre diferentes.
- Deixar **Q = 1,0** para um perfil esbelto sem verificar a classificação
  da seção pela norma.
- Achar que o maior N, V e M da tabela de combinações acontecem ao mesmo
  tempo — confira a combinação de origem de cada um.
- Esperar que o módulo 5 alimente o módulo 2 sozinho — os números
  precisam ser copiados manualmente de um formulário para o outro.
"""
    )

    st.caption(
        "Cada um dos 5 módulos tem um exemplo numérico completo e reproduzível no Guia geral."
    )
    st.page_link(
        "app_pages/guia_geral.py",
        label="Abrir exemplos passo a passo no Guia geral",
        icon=":material/menu_book:",
    )

modulo = st.segmented_control(
    "Módulo",
    ["1. Perfis", "2. Barras", "3. Combinações", "4. Ligações", "5. Análise 2D"],
    required=True,
    width="stretch",
    key="estrutura_aco_modulo",
    persist_state="session",
)


if modulo == "1. Perfis":
    st.header("Catálogo geométrico de perfis")
    st.info(
        "Os perfis são idealizações geométricas, não tabelas comerciais. "
        "Raios de concordância e tolerâncias não estão incluídos.",
        icon=":material/info:",
    )
    catalogo = catalogo_perfis.catalogo_dataframe()
    familias = sorted(catalogo["familia"].unique())
    familia = st.selectbox(
        "Família",
        ["Todas"] + familias,
        key="estrutura_perfil_familia_filtro",
        persist_state="session",
    )
    filtrado = catalogo if familia == "Todas" else catalogo[catalogo["familia"] == familia]
    tabela_catalogo = pd.DataFrame(
        {
            "Perfil": filtrado["nome"],
            "Família": filtrado["familia"],
            "Massa (kg/m)": filtrado["massa_kg_m"],
            "Área (cm²)": filtrado["area_mm2"] / 100.0,
            "Ix (cm⁴)": filtrado["ix_mm4"] / 10_000.0,
            "Iy (cm⁴)": filtrado["iy_mm4"] / 10_000.0,
            "Sx (cm³)": filtrado["sx_mm3"] / 1_000.0,
            "Zx (cm³)": filtrado["zx_mm3"] / 1_000.0,
            "rx (cm)": filtrado["rx_mm"] / 10.0,
            "ry (cm)": filtrado["ry_mm"] / 10.0,
        }
    )
    st.dataframe(
        tabela_catalogo,
        hide_index=True,
        column_config={
            coluna: st.column_config.NumberColumn(format="%.3f")
            for coluna in tabela_catalogo.columns
            if coluna not in {"Perfil", "Família"}
        },
    )

    nome_perfil = st.selectbox(
        "Inspecionar perfil",
        list(catalogo_perfis.listar_perfis()),
        key="estrutura_perfil_selecionado",
        persist_state="session",
    )
    perfil = catalogo_perfis.obter_perfil(nome_perfil)
    with st.container(border=True):
        st.subheader(perfil.nome)
        with st.container(horizontal=True):
            st.metric("Massa", f"{perfil.massa_kg_m:.2f} kg/m", border=True)
            st.metric("Área", f"{perfil.area_mm2 / 100:.2f} cm²", border=True)
            st.metric("Ix", f"{perfil.ix_mm4 / 1e4:.1f} cm⁴", border=True)
            st.metric("Iy", f"{perfil.iy_mm4 / 1e4:.1f} cm⁴", border=True)
            st.metric("Zx", f"{perfil.zx_mm3 / 1e3:.1f} cm³", border=True)
        propriedades = pd.DataFrame(
            {
                "Propriedade": [
                    "Sx",
                    "Sy",
                    "Zx",
                    "Zy",
                    "rx",
                    "ry",
                    "J",
                    "Cw",
                    "Área de cisalhamento",
                ],
                "Valor": [
                    perfil.sx_mm3 / 1e3,
                    perfil.sy_mm3 / 1e3,
                    perfil.zx_mm3 / 1e3,
                    perfil.zy_mm3 / 1e3,
                    perfil.rx_mm / 10,
                    perfil.ry_mm / 10,
                    perfil.j_mm4 / 1e4,
                    perfil.cw_mm6 / 1e6,
                    perfil.area_cisalhamento_mm2 / 100,
                ],
                "Unidade": ["cm³", "cm³", "cm³", "cm³", "cm", "cm", "cm⁴", "cm⁶", "cm²"],
            }
        )
        st.dataframe(
            propriedades,
            hide_index=True,
            column_config={"Valor": st.column_config.NumberColumn(format="%.4g")},
        )
        st.download_button(
            "Baixar propriedades do perfil em CSV",
            data=propriedades.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"perfil_{perfil.nome}.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="aco_baixar_perfil",
        )
        st.caption(perfil.descricao)

    with st.expander(
        "Criar perfil paramétrico personalizado",
        icon=":material/tune:",
    ):
        familia_custom = st.segmented_control(
            "Geometria",
            [
                "I simétrico",
                "W mesa larga",
                "U (canal)",
                "C enrijecido",
                "T (tê)",
                "Tubo retangular",
                "Tubo circular",
                "Barra retangular",
                "Barra circular",
            ],
            default="I simétrico",
            required=True,
            width="stretch",
            key="estrutura_perfil_custom_familia",
            persist_state="session",
        )
        try:
            if familia_custom == "I simétrico":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=300.0, key="estrutura_custom_i_h"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=150.0, key="estrutura_custom_i_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=6.5, key="estrutura_custom_i_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=10.0, key="estrutura_custom_i_tf"
                )
                custom = secoes.perfil_i_simetrico("Personalizado", h, b, tw, tf)
            elif familia_custom == "W mesa larga":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=300.0, key="estrutura_custom_w_h"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=300.0, key="estrutura_custom_w_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=10.0, key="estrutura_custom_w_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=15.0, key="estrutura_custom_w_tf"
                )
                custom = secoes.perfil_w_mesa_larga("Personalizado", h, b, tw, tf)
            elif familia_custom == "U (canal)":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=150.0, key="estrutura_custom_u_h"
                )
                b = dimensoes[1].number_input("b (mm)", 1.0, value=75.0, key="estrutura_custom_u_b")
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=6.5, key="estrutura_custom_u_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=9.5, key="estrutura_custom_u_tf"
                )
                custom = secoes.perfil_u("Personalizado", h, b, tw, tf)
            elif familia_custom == "C enrijecido":
                dimensoes = st.columns(4)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=150.0, key="estrutura_custom_c_h"
                )
                b = dimensoes[1].number_input("b (mm)", 1.0, value=50.0, key="estrutura_custom_c_b")
                d = dimensoes[2].number_input(
                    "aba enrijecedora (mm)", 0.1, value=17.0, key="estrutura_custom_c_d"
                )
                t = dimensoes[3].number_input("t (mm)", 0.1, value=3.0, key="estrutura_custom_c_t")
                custom = secoes.perfil_c_enrijecido("Personalizado", h, b, d, t)
            elif familia_custom == "T (tê)":
                dimensoes = st.columns(4)
                d = dimensoes[0].number_input(
                    "altura total (mm)", 1.0, value=150.0, key="estrutura_custom_t_d"
                )
                b = dimensoes[1].number_input(
                    "bf (mm)", 1.0, value=150.0, key="estrutura_custom_t_b"
                )
                tw = dimensoes[2].number_input(
                    "tw (mm)", 0.1, value=7.5, key="estrutura_custom_t_tw"
                )
                tf = dimensoes[3].number_input(
                    "tf (mm)", 0.1, value=10.5, key="estrutura_custom_t_tf"
                )
                custom = secoes.perfil_t("Personalizado", d, b, tw, tf)
            elif familia_custom == "Barra circular":
                d = st.number_input(
                    "Diâmetro (mm)", 1.0, value=25.0, key="estrutura_custom_barra_circular_d"
                )
                custom = secoes.barra_circular("Personalizado", d)
            elif familia_custom == "Tubo retangular":
                dimensoes = st.columns(3)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=100.0, key="estrutura_custom_tubo_ret_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=50.0, key="estrutura_custom_tubo_ret_b"
                )
                t = dimensoes[2].number_input(
                    "t (mm)", 0.1, value=3.0, key="estrutura_custom_tubo_ret_t"
                )
                custom = secoes.tubo_retangular("Personalizado", h, b, t)
            elif familia_custom == "Tubo circular":
                dimensoes = st.columns(2)
                d = dimensoes[0].number_input(
                    "D (mm)", 1.0, value=114.3, key="estrutura_custom_tubo_circ_d"
                )
                t = dimensoes[1].number_input(
                    "t (mm)", 0.1, value=4.5, key="estrutura_custom_tubo_circ_t"
                )
                custom = secoes.tubo_circular("Personalizado", d, t)
            else:
                dimensoes = st.columns(2)
                h = dimensoes[0].number_input(
                    "h (mm)", 1.0, value=100.0, key="estrutura_custom_barra_h"
                )
                b = dimensoes[1].number_input(
                    "b (mm)", 1.0, value=20.0, key="estrutura_custom_barra_b"
                )
                custom = secoes.barra_retangular("Personalizado", h, b)
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
        else:
            with st.container(horizontal=True):
                st.metric("Área", f"{custom.area_mm2 / 100:.3f} cm²", border=True)
                st.metric("Massa", f"{custom.massa_kg_m:.3f} kg/m", border=True)
                st.metric("Ix", f"{custom.ix_mm4 / 1e4:.3f} cm⁴", border=True)
                st.metric("Iy", f"{custom.iy_mm4 / 1e4:.3f} cm⁴", border=True)


elif modulo == "2. Barras":
    st.header("Verificação de barras pela NBR 8800")
    st.caption(
        "Estados-limites últimos de barra prismática com as equações da norma: "
        "N_c,Rd = χ·Q·A_g·f_y/γ_a1 (5.3, Anexos E e F), M_Rd pelo menor entre FLT, "
        "FLM e FLA (Anexo G), V_Rd (5.4.3), interação N–M (5.5.1.2) e limites de "
        "esbeltez. γ_a1 = 1,10 e γ_a2 = 1,35 (Tabela 3). Os esforços entram já "
        "majorados pelas combinações do módulo 3."
    )
    nome_perfil = st.selectbox(
        "Perfil",
        list(catalogo_perfis.listar_perfis()),
        key="estrutura_barra_perfil",
        persist_state="session",
    )
    perfil = catalogo_perfis.obter_perfil(nome_perfil)

    with st.container(border=True):
        st.subheader("Material e esforços de cálculo")
        material = st.columns(4)
        fy = material[0].number_input(
            "f_y (MPa)", 1.0, value=250.0, step=10.0, key="estrutura_barra_fy"
        )
        fu = material[1].number_input(
            "f_u (MPa)", 1.0, value=400.0, step=10.0, key="estrutura_barra_fu"
        )
        e = material[2].number_input("E (GPa)", 1.0, value=200.0, step=5.0, key="estrutura_barra_e")
        g = material[3].number_input("G (GPa)", 1.0, value=77.0, step=1.0, key="estrutura_barra_g")
        if fu < fy:
            st.error("f_u deve ser maior ou igual a f_y.", icon=":material/error:")
            st.stop()
        tipo_axial = st.segmented_control(
            "Solicitação axial",
            ["Tração", "Compressão"],
            default="Compressão",
            required=True,
            width="stretch",
            key="estrutura_barra_tipo_axial",
            persist_state="session",
        )
        esforcos = st.columns(4)
        nd_kN = esforcos[0].number_input("|N_Sd| (kN)", 0.0, step=10.0, key="estrutura_nd_kN")
        mdx_kNm = esforcos[1].number_input(
            "|M_x,Sd| (kN·m)", 0.0, step=5.0, key="estrutura_mdx_kNm"
        )
        mdy_kNm = esforcos[2].number_input(
            "|M_y,Sd| (kN·m)", 0.0, value=0.0, step=5.0, key="estrutura_mdy_kNm"
        )
        vd_kN = esforcos[3].number_input("|V_Sd| (kN)", 0.0, step=5.0, key="estrutura_vd_kN")

    with st.container(border=True):
        st.subheader("Comprimentos, travamentos e fabricação")
        estabilidade = st.columns(4)
        comprimento_m = estabilidade[0].number_input(
            "Comprimento L (m)",
            0.001,
            step=0.25,
            key="estrutura_comprimento_m",
        )
        kx = estabilidade[1].number_input("K_x", 0.01, value=1.0, step=0.1, key="estrutura_kx")
        ky = estabilidade[2].number_input("K_y", 0.01, value=1.0, step=0.1, key="estrutura_ky")
        kz = estabilidade[3].number_input(
            "K_z (torção)",
            0.01,
            value=1.0,
            step=0.1,
            key="estrutura_kz",
            help="Comprimento de flambagem por torção (Anexo E): 1,0 se as extremidades não impedem o empenamento.",
        )
        travamento = st.columns(4)
        lb_m = travamento[0].number_input(
            "Comprimento destravado L_b (m)",
            0.001,
            value=3.0,
            step=0.25,
            key="estrutura_lb_m",
            help="Trecho da mesa comprimida sem travamento lateral — entra na FLT.",
        )
        cb = travamento[1].number_input(
            "C_b",
            0.01,
            value=1.0,
            step=0.1,
            key="estrutura_cb",
            help="Fator de modificação para diagrama de momento não uniforme (G.2.1). 1,0 é conservador; em seções U a norma impõe 1,0.",
        )
        soldado = travamento[2].toggle(
            "Perfil soldado",
            value=False,
            key="estrutura_soldado",
            help="Mesas de perfis soldados usam k_c nos limites de FLM e no grupo 5 do Anexo F.",
        )
        area_liquida_pct = travamento[3].number_input(
            "Área líquida / bruta (%)",
            1.0,
            100.0,
            value=100.0,
            step=1.0,
            key="estrutura_area_liquida_pct",
            help="Só para barras tracionadas com furos.",
        )
        ct = st.number_input(
            "Coeficiente de redução da área líquida C_t (5.2.5)",
            0.01,
            1.0,
            value=1.0,
            step=0.05,
            key="estrutura_ct",
            persist_state="session",
        )

    try:
        barra_nbr = nbr8800.verificar_barra(
            perfil,
            fy_MPa=fy,
            fu_MPa=fu,
            modulo_elasticidade_MPa=e * 1e3,
            modulo_cisalhamento_MPa=g * 1e3,
            comprimento_mm=comprimento_m * 1e3,
            kx=kx,
            ky=ky,
            forca_axial_N=(-1.0 if tipo_axial == "Compressão" else 1.0) * nd_kN * 1e3,
            momento_x_Nmm=mdx_kNm * 1e6,
            momento_y_Nmm=mdy_kNm * 1e6,
            cortante_N=vd_kN * 1e3,
            comprimento_destravado_mm=lb_m * 1e3,
            cb=cb,
            kz=kz,
            soldado=soldado,
            area_liquida_mm2=perfil.area_mm2 * area_liquida_pct / 100.0,
            coeficiente_ct=ct,
        )
    except ValueError as erro:
        st.error(f"Não foi possível verificar a barra: {erro}", icon=":material/error:")
        st.stop()

    for aviso in barra_nbr.avisos:
        st.warning(aviso, icon=":material/warning:")

    st.subheader("Resistências de cálculo e utilização")
    if barra_nbr.compressao is not None:
        axial = barra_nbr.compressao
        resistencia_axial = axial.resistencia_N
        utilizacao_axial = axial.utilizacao
        modo_axial = f"N_c,Rd (χ = {axial.chi:.3f}, Q = {axial.fator_q:.3f})"
    else:
        assert barra_nbr.tracao is not None
        tracao = barra_nbr.tracao
        resistencia_axial = tracao.resistencia_N
        utilizacao_axial = tracao.utilizacao
        modo_axial = f"N_t,Rd — {tracao.modo_governante}"
    flexao_x = barra_nbr.flexao_x
    cisalhamento = barra_nbr.cisalhamento
    interacao = barra_nbr.interacao
    with st.container(horizontal=True):
        st.metric(
            modo_axial,
            f"{resistencia_axial / 1e3:.1f} kN",
            border=True,
        )
        st.metric(
            f"M_x,Rd — {flexao_x.modo_governante}",
            f"{flexao_x.resistencia_Nmm / 1e6:.2f} kN·m",
            border=True,
        )
        st.metric(
            f"V_Rd — {cisalhamento.regime}",
            f"{cisalhamento.resistencia_N / 1e3:.1f} kN",
            border=True,
        )
        st.metric(
            "Interação N–M (5.5.1.2)",
            f"{interacao.indice:.3f}",
            border=True,
            help=interacao.expressao,
        )
    mostrar_utilizacao("Esforço axial", utilizacao_axial)
    mostrar_utilizacao("Flexão em torno de x", flexao_x.utilizacao)
    if barra_nbr.flexao_y is not None:
        mostrar_utilizacao("Flexão em torno de y", barra_nbr.flexao_y.utilizacao)
    mostrar_utilizacao("Cisalhamento", cisalhamento.utilizacao)
    mostrar_utilizacao("Interação N–Mx–My", interacao.indice)
    if math.isinf(barra_nbr.utilizacao_governante):
        st.error(
            f"Modo governante: {barra_nbr.modo_governante} — a barra não atende "
            "independentemente da resistência.",
            icon=":material/error:",
        )
    else:
        st.info(
            f"Modo governante: **{barra_nbr.modo_governante}** — utilização "
            f"{barra_nbr.utilizacao_governante:.3f}.",
            icon=":material/rule:",
        )

    st.latex(
        r"N_{c,Rd}=\frac{\chi\,Q\,A_g\,f_y}{\gamma_{a1}},\qquad "
        r"\lambda_0=\sqrt{\frac{Q\,A_g\,f_y}{N_e}},\qquad "
        r"M_{Rd}=\min(M_{Rd}^{FLT},M_{Rd}^{FLM},M_{Rd}^{FLA})\le\frac{1{,}5\,W\,f_y}{\gamma_{a1}}"
    )

    with st.expander(
        "Memória de cálculo — compressão e classificação das paredes", icon=":material/calculate:"
    ):
        if barra_nbr.compressao is not None:
            axial = barra_nbr.compressao
            linhas_compressao = [
                ("K_x·L/r_x", axial.esbeltez_x, "—"),
                ("K_y·L/r_y", axial.esbeltez_y, "—"),
                ("N_ex (flexão em x)", axial.ne_x_N / 1e3, "kN"),
                ("N_ey (flexão em y)", axial.ne_y_N / 1e3, "kN"),
            ]
            if axial.ne_z_N is not None:
                linhas_compressao.append(("N_ez (torção)", axial.ne_z_N / 1e3, "kN"))
            if axial.ne_acoplada_N is not None:
                linhas_compressao.append(
                    ("N_e flexo-torção (E.1.2)", axial.ne_acoplada_N / 1e3, "kN")
                )
            linhas_compressao += [
                (f"N_e governante — modo {axial.modo_flambagem}", axial.ne_N / 1e3, "kN"),
                ("Q (Anexo F)", axial.fator_q, "—"),
                ("λ_0", axial.lambda_0, "—"),
                ("χ (5.3.3)", axial.chi, "—"),
                ("N_c,Rd", axial.resistencia_N / 1e3, "kN"),
            ]
            st.dataframe(
                pd.DataFrame(linhas_compressao, columns=["Parâmetro", "Valor", "Unidade"]),
                hide_index=True,
                column_config={"Valor": st.column_config.NumberColumn(format="%.4g")},
            )
            if axial.elementos:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Elemento": item.nome,
                                "Tipo": item.tipo,
                                "Grupo (Tab. F.1)": item.grupo,
                                "b/t": item.razao,
                                "(b/t)_lim": item.limite_r,
                                "Q do elemento": item.fator_q,
                                "b_ef (mm)": item.largura_efetiva_mm,
                            }
                            for item in axial.elementos
                        ]
                    ),
                    hide_index=True,
                    column_config={
                        "b/t": st.column_config.NumberColumn(format="%.2f"),
                        "(b/t)_lim": st.column_config.NumberColumn(format="%.2f"),
                        "Q do elemento": st.column_config.NumberColumn(format="%.3f"),
                        "b_ef (mm)": st.column_config.NumberColumn(format="%.1f"),
                    },
                )
        else:
            assert barra_nbr.tracao is not None
            st.dataframe(
                pd.DataFrame(
                    [
                        ("A_g·f_y/γ_a1", barra_nbr.tracao.resistencia_escoamento_N / 1e3, "kN"),
                        ("C_t·A_n·f_u/γ_a2", barra_nbr.tracao.resistencia_ruptura_N / 1e3, "kN"),
                        ("L/r", barra_nbr.tracao.esbeltez, "—"),
                    ],
                    columns=["Parâmetro", "Valor", "Unidade"],
                ),
                hide_index=True,
                column_config={"Valor": st.column_config.NumberColumn(format="%.4g")},
            )

    with st.expander(
        "Memória de cálculo — flexão (Anexo G) e cisalhamento (5.4.3)", icon=":material/calculate:"
    ):
        modos = list(flexao_x.modos) + (
            list(barra_nbr.flexao_y.modos) if barra_nbr.flexao_y else []
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Modo": modo.nome,
                        "λ": modo.esbeltez,
                        "λ_p": modo.lambda_p,
                        "λ_r": modo.lambda_r,
                        "M_pl (kN·m)": modo.momento_pl_Nmm / 1e6,
                        "M_r (kN·m)": modo.momento_r_Nmm / 1e6,
                        "M_cr (kN·m)": None
                        if modo.momento_cr_Nmm is None
                        else modo.momento_cr_Nmm / 1e6,
                        "M_Rd (kN·m)": modo.resistencia_Nmm / 1e6,
                        "Regime": modo.regime,
                    }
                    for modo in modos
                ]
            ),
            hide_index=True,
            column_config={
                coluna: st.column_config.NumberColumn(format="%.3f")
                for coluna in (
                    "λ",
                    "λ_p",
                    "λ_r",
                    "M_pl (kN·m)",
                    "M_r (kN·m)",
                    "M_cr (kN·m)",
                    "M_Rd (kN·m)",
                )
            },
        )
        st.dataframe(
            pd.DataFrame(
                [
                    ("h/t_w (alma)", cisalhamento.esbeltez_alma, "—"),
                    ("k_v", cisalhamento.kv, "—"),
                    ("λ_p", cisalhamento.lambda_p, "—"),
                    ("λ_r", cisalhamento.lambda_r, "—"),
                    ("A_w", cisalhamento.area_cisalhamento_mm2, "mm²"),
                    ("V_pl = 0,6·f_y·A_w", cisalhamento.vpl_N / 1e3, "kN"),
                    (f"V_Rd — {cisalhamento.regime}", cisalhamento.resistencia_N / 1e3, "kN"),
                ],
                columns=["Parâmetro", "Valor", "Unidade"],
            ),
            hide_index=True,
            column_config={"Valor": st.column_config.NumberColumn(format="%.4g")},
        )

    tabela_resumo_barra = pd.DataFrame(
        {
            "Grandeza": [
                f"Resistência axial — {modo_axial} (kN)",
                "M_x,Rd (kN·m)",
                "V_Rd (kN)",
                "Índice de interação",
                "Utilização axial",
                "Utilização flexão x",
                "Utilização cisalhamento",
                "Utilização interação",
            ],
            "Valor": [
                resistencia_axial / 1e3,
                flexao_x.resistencia_Nmm / 1e6,
                cisalhamento.resistencia_N / 1e3,
                interacao.indice,
                utilizacao_axial,
                flexao_x.utilizacao,
                cisalhamento.utilizacao,
                interacao.indice,
            ],
        }
    )
    st.download_button(
        "Baixar resultado da barra em CSV",
        data=tabela_resumo_barra.to_csv(index=False).encode("utf-8-sig"),
        file_name="estrutura_aco_barra_nbr8800.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="aco_baixar_barra",
    )

    with st.expander(
        "Estado-limite de serviço — flecha",
        icon=":material/straighten:",
    ):
        els = st.columns(4)
        condicao = els[0].selectbox("Viga", ["Biapoiada", "Balanço"])
        q_servico = els[1].number_input("Carga distribuída de serviço (kN/m)", 0.0, value=5.0)
        p_servico = els[2].number_input("Carga concentrada de serviço (kN)", 0.0, value=0.0)
        limite_relativo = els[3].number_input("Limite L/divisor", 1.0, value=350.0)
        flecha = barras.verificar_deflexao_viga(
            perfil,
            e * 1e3,
            comprimento_m * 1e3,
            q_servico,
            p_servico * 1e3,
            condicao,
            limite_relativo,
        )
        with st.container(horizontal=True):
            st.metric("Flecha", f"{flecha.deflexao_total_mm:.2f} mm", border=True)
            st.metric("Limite", f"{flecha.limite_mm:.2f} mm", border=True)
            st.metric(
                "Relação obtida",
                "∞"
                if math.isinf(flecha.razao_vao_deflexao)
                else f"L/{flecha.razao_vao_deflexao:.0f}",
                border=True,
            )
        mostrar_utilizacao("Flecha", flecha.utilizacao)
        st.caption(
            "Flecha com as ações de serviço (combinação ELS), não com os esforços "
            "majorados. Limites usuais do Anexo C: L/350 em vigas de piso, L/250 em "
            "vigas de cobertura; adote o critério do projeto."
        )

    fronteira_modelo(
        [
            "Vigas de alma esbelta (Anexo H), perfis T à flexão (G.6) e tubos circulares ao cisalhamento (5.4.3.6) só recebem o limite de escoamento, com aviso.",
            "Flambagem lateral com torção de perfis U com torção aplicada e de seções monossimétricas I não está no Anexo G; o programa trata o U como não torcido.",
            "Efeitos de segunda ordem (B1/B2, análise direta) e imperfeições (4.9) pertencem à análise global — módulo 5 —, não à verificação da barra.",
            "Ligações, placas de base e chumbadores ficam no módulo 4.",
        ]
    )

    utilizacao_governante = max(
        barra_nbr.utilizacao_governante,
        flecha.utilizacao,
    )
    status_barra = "Atende" if utilizacao_governante <= 1.0 else "Não atende"
    registro_barra = construir_registro_tecnico(
        modulo="Estruturas de aço",
        modulo_id="estruturas_aco",
        titulo=f"Verificação da barra {nome_perfil} (NBR 8800)",
        status=status_barra,
        resumo=(
            "Barra isolada verificada pela NBR 8800: compressão/tração, flexão "
            "(FLT, FLM, FLA), cisalhamento, interação N–M, esbeltez limite e flecha."
        ),
        entradas={
            "perfil": nome_perfil,
            "solicitacao_axial": tipo_axial,
            "fy_MPa": fy,
            "fu_MPa": fu,
            "E_GPa": e,
            "G_GPa": g,
            "N_Sd_kN": nd_kN,
            "Mx_Sd_kNm": mdx_kNm,
            "My_Sd_kNm": mdy_kNm,
            "V_Sd_kN": vd_kN,
            "comprimento_m": comprimento_m,
            "Kx": kx,
            "Ky": ky,
            "Kz": kz,
            "Lb_m": lb_m,
            "Cb": cb,
            "perfil_soldado": soldado,
            "area_liquida_pct": area_liquida_pct,
            "Ct": ct,
            "gamma_a1": nbr8800.GAMMA_A1,
            "gamma_a2": nbr8800.GAMMA_A2,
        },
        resultados={
            "resistencia_axial_kN": resistencia_axial / 1e3,
            "modo_axial": modo_axial,
            "Q": None if barra_nbr.compressao is None else barra_nbr.compressao.fator_q,
            "lambda_0": None if barra_nbr.compressao is None else barra_nbr.compressao.lambda_0,
            "chi": None if barra_nbr.compressao is None else barra_nbr.compressao.chi,
            "Ne_kN": None if barra_nbr.compressao is None else barra_nbr.compressao.ne_N / 1e3,
            "modo_flambagem": None
            if barra_nbr.compressao is None
            else barra_nbr.compressao.modo_flambagem,
            "esbeltez_x": None if barra_nbr.compressao is None else barra_nbr.compressao.esbeltez_x,
            "esbeltez_y": None if barra_nbr.compressao is None else barra_nbr.compressao.esbeltez_y,
            "Mx_Rd_kNm": flexao_x.resistencia_Nmm / 1e6,
            "modo_flexao_x": flexao_x.modo_governante,
            "modos_flexao": [
                {
                    "modo": modo.nome,
                    "lambda": modo.esbeltez,
                    "lambda_p": modo.lambda_p,
                    "lambda_r": modo.lambda_r,
                    "M_pl_kNm": modo.momento_pl_Nmm / 1e6,
                    "M_r_kNm": modo.momento_r_Nmm / 1e6,
                    "M_cr_kNm": None if modo.momento_cr_Nmm is None else modo.momento_cr_Nmm / 1e6,
                    "M_Rd_kNm": modo.resistencia_Nmm / 1e6,
                    "regime": modo.regime,
                }
                for modo in modos
            ],
            "My_Rd_kNm": None
            if barra_nbr.flexao_y is None
            else barra_nbr.flexao_y.resistencia_Nmm / 1e6,
            "V_Rd_kN": cisalhamento.resistencia_N / 1e3,
            "regime_cisalhamento": cisalhamento.regime,
            "utilizacao_axial": utilizacao_axial,
            "utilizacao_flexao": flexao_x.utilizacao,
            "utilizacao_cisalhamento": cisalhamento.utilizacao,
            "utilizacao_interacao": interacao.indice,
            "expressao_interacao": interacao.expressao,
            "utilizacao_flecha": flecha.utilizacao,
            "utilizacao_maxima": None
            if math.isinf(utilizacao_governante)
            else utilizacao_governante,
            "modo_governante": barra_nbr.modo_governante,
            "flecha_mm": flecha.deflexao_total_mm,
            "limite_flecha_mm": flecha.limite_mm,
        },
        metodo=(
            "NBR 8800:2008 — compressão por 5.3 com N_e do Anexo E (flexão, torção e "
            "flexo-torção) e Q do Anexo F; flexão pelo Anexo G (FLT, FLM, FLA) limitada a "
            "1,5·W·f_y; cisalhamento por 5.4.3; interação por 5.5.1.2; esbeltez limite "
            "por 5.3.4.1 e 5.2.8."
        ),
        equacoes=[
            "N_c,Rd = χ·Q·A_g·f_y/γ_a1;  λ_0 = √(Q·A_g·f_y/N_e);  χ = 0,658^(λ_0²) (λ_0 ≤ 1,5) ou 0,877/λ_0²",
            "M_Rd = min(M_Rd,FLT, M_Rd,FLM, M_Rd,FLA) ≤ 1,5·W·f_y/γ_a1",
            "V_Rd = V_pl/γ_a1 · {1; λ_p/λ; 1,24·(λ_p/λ)²},  V_pl = 0,6·f_y·A_w",
            interacao.expressao,
        ],
        premissas=[
            "Perfil de catálogo idealizado; raios de concordância e tolerâncias desprezados.",
            "Esforços solicitantes já majorados pelas combinações ELU (NBR 8681).",
            f"Coeficientes de ponderação da resistência γ_a1 = {nbr8800.GAMMA_A1} e γ_a2 = {nbr8800.GAMMA_A2} (Tabela 3).",
            "Comprimentos de flambagem K·L e comprimento destravado L_b informados pelo projetista.",
        ],
        alertas=([] if utilizacao_governante <= 1.0 else ["Ao menos uma utilização supera 1,0."])
        + list(barra_nbr.avisos),
        referencias=[
            "ABNT NBR 8800:2008 — Projeto de estruturas de aço e de estruturas mistas de aço e concreto de edifícios (5.2, 5.3, 5.4, 5.5, Anexos E, F e G).",
            "ABNT NBR 8681:2003 — Ações e segurança nas estruturas (combinações).",
        ],
        conclusao=(
            f"Modo governante: {barra_nbr.modo_governante}; maior índice de utilização = "
            + ("∞" if math.isinf(utilizacao_governante) else f"{utilizacao_governante:.3f}")
            + ("; a barra atende." if utilizacao_governante <= 1.0 else "; a barra não atende.")
        ),
    )
    botao_registrar_calculo(
        registro_barra,
        key="registrar_estrutura_barra",
        rotulo="Registrar verificação da barra no projeto",
    )


elif modulo == "3. Combinações":
    st.header("Combinações de ações pela NBR 8681 / NBR 8800")
    st.info(
        "Escolha a **categoria** de cada ação e os coeficientes γ_f e ψ das "
        "Tabelas 1 e 2 da NBR 8800 (NBR 8681) são aplicados automaticamente — "
        "inclusive a combinação com as permanentes favoráveis (γ_g = 1,0), que "
        "governa vento de sucção e tombamento. Use a categoria personalizada "
        "para informar γ e ψ próprios.",
        icon=":material/edit_note:",
    )
    categorias = [combinacoes.CATEGORIA_PERSONALIZADA] + [
        item.rotulo for item in combinacoes.CATEGORIAS_NBR8800
    ]
    acoes_padrao = pd.DataFrame(
        [
            [
                "PP",
                "Peso próprio de estrutura metálica",
                "Permanente",
                50.0,
                10.0,
                20.0,
                1.25,
                1.0,
                1.0,
                1.0,
            ],
            [
                "Piso",
                "Elementos construtivos industrializados (grades, pisos, guarda-corpos)",
                "Permanente",
                10.0,
                2.0,
                4.0,
                1.35,
                1.0,
                1.0,
                1.0,
            ],
            [
                "SC",
                "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas",
                "Variável",
                30.0,
                5.0,
                15.0,
                1.50,
                0.7,
                0.6,
                0.4,
            ],
            ["W+", "Vento (NBR 6123)", "Variável", 0.0, 20.0, 40.0, 1.40, 0.6, 0.3, 0.0],
            ["W−", "Vento (NBR 6123)", "Variável", -15.0, -20.0, -40.0, 1.40, 0.6, 0.3, 0.0],
        ],
        columns=[
            "nome",
            "categoria",
            "tipo",
            "N (kN)",
            "V (kN)",
            "M (kN·m)",
            "γ",
            "ψ0",
            "ψ1",
            "ψ2",
        ],
    )
    editadas = st.data_editor(
        acoes_padrao,
        num_rows="dynamic",
        hide_index=True,
        key="estrutura_acoes_editor",
        column_config={
            "categoria": st.column_config.SelectboxColumn(
                options=categorias,
                required=True,
                help="Categoria da NBR 8800 (Tabelas 1 e 2). Define tipo, γ_f e ψ; a personalizada usa as colunas γ e ψ.",
            ),
            "tipo": st.column_config.SelectboxColumn(
                options=["Permanente", "Variável"],
                required=True,
                help="Só é usado na categoria personalizada.",
            ),
            "γ": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "ψ0": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
            "ψ1": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
            "ψ2": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, format="%.3f"),
        },
    )
    try:
        lista_acoes = []
        for _, linha in editadas.dropna(subset=["nome", "N (kN)", "V (kN)", "M (kN·m)"]).iterrows():
            categoria = str(linha.get("categoria") or combinacoes.CATEGORIA_PERSONALIZADA)
            if categoria != combinacoes.CATEGORIA_PERSONALIZADA:
                lista_acoes.append(
                    combinacoes.acao_da_categoria(
                        str(linha["nome"]),
                        categoria,
                        float(linha["N (kN)"]),
                        float(linha["V (kN)"]),
                        float(linha["M (kN·m)"]),
                    )
                )
            else:
                lista_acoes.append(
                    combinacoes.AcaoEstrutural(
                        nome=str(linha["nome"]),
                        tipo=str(linha["tipo"]),
                        n_kN=float(linha["N (kN)"]),
                        v_kN=float(linha["V (kN)"]),
                        m_kNm=float(linha["M (kN·m)"]),
                        gamma=float(linha["γ"]),
                        psi0=float(linha["ψ0"]),
                        psi1=float(linha["ψ1"]),
                        psi2=float(linha["ψ2"]),
                        gamma_favoravel=1.0 if str(linha["tipo"]) == "Permanente" else None,
                        categoria=categoria,
                    )
                )
        resultados = combinacoes.gerar_combinacoes(lista_acoes)
    except (ValueError, TypeError) as erro:
        st.error(f"Revise a tabela: {erro}", icon=":material/error:")
        st.stop()

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Ação": acao.nome,
                    "Categoria": acao.categoria or combinacoes.CATEGORIA_PERSONALIZADA,
                    "Tipo": acao.tipo,
                    "γ_f": acao.gamma,
                    "γ_f favorável": acao.gamma_favoravel,
                    "ψ0": acao.psi0,
                    "ψ1": acao.psi1,
                    "ψ2": acao.psi2,
                }
                for acao in lista_acoes
            ]
        ),
        hide_index=True,
        column_config={
            coluna: st.column_config.NumberColumn(format="%.2f")
            for coluna in ("γ_f", "γ_f favorável", "ψ0", "ψ1", "ψ2")
        },
    )

    tabela_resultados = pd.DataFrame([asdict(item) for item in resultados]).rename(
        columns={
            "nome": "Combinação",
            "estado_limite": "Estado-limite",
            "acao_principal": "Ação principal",
            "n_kN": "N (kN)",
            "v_kN": "V (kN)",
            "m_kNm": "M (kN·m)",
            "expressao": "Expressão",
        }
    )
    st.dataframe(
        tabela_resultados,
        hide_index=True,
        column_config={
            "N (kN)": st.column_config.NumberColumn(format="%.3f"),
            "V (kN)": st.column_config.NumberColumn(format="%.3f"),
            "M (kN·m)": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.download_button(
        "Baixar combinações em CSV",
        data=tabela_resultados.to_csv(index=False).encode("utf-8-sig"),
        file_name="estrutura_aco_combinacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="aco_baixar_combinacoes",
    )
    with st.container(horizontal=True):
        st.metric(
            "Maior |N|",
            f"{tabela_resultados['N (kN)'].abs().max():.2f} kN",
            border=True,
        )
        st.metric(
            "Maior |V|",
            f"{tabela_resultados['V (kN)'].abs().max():.2f} kN",
            border=True,
        )
        st.metric(
            "Maior |M|",
            f"{tabela_resultados['M (kN·m)'].abs().max():.2f} kN·m",
            border=True,
        )
    st.caption(
        "O envelope de cada esforço pode vir de combinações diferentes. "
        "Não combine máximos independentes como se fossem simultâneos."
    )
    registro_combinacoes = construir_registro_tecnico(
        modulo="Estruturas de aço",
        modulo_id="estruturas_aco",
        titulo="Combinações de ações ELU e ELS",
        status="Calculado",
        resumo="Geração de combinações editáveis e envelope de esforços para uso nas verificações estruturais.",
        entradas={
            "acoes": [asdict(item) for item in lista_acoes],
            "numero_acoes": len(lista_acoes),
        },
        resultados={
            "maior_N_absoluto_kN": float(tabela_resultados["N (kN)"].abs().max()),
            "maior_V_absoluto_kN": float(tabela_resultados["V (kN)"].abs().max()),
            "maior_M_absoluto_kNm": float(tabela_resultados["M (kN·m)"].abs().max()),
            "numero_combinacoes": len(resultados),
            "combinacoes": [asdict(item) for item in resultados],
        },
        premissas=[
            "Coeficientes γ_f e ψ das Tabelas 1 e 2 da NBR 8800 (NBR 8681) aplicados por categoria de ação; a categoria personalizada usa os valores informados.",
            "Ações permanentes entram também com γ_g favorável (1,0) na combinação em que aliviam o efeito.",
        ],
        alertas=["Os máximos independentes do envelope podem pertencer a combinações diferentes."],
        referencias=[
            "ABNT NBR 8800:2008, Tabelas 1 e 2 (γ_f e ψ) e ABNT NBR 8681:2003 — confirmar a edição vigente e as ações do projeto."
        ],
        conclusao="Combinações geradas; selecionar casos simultâneos governantes para cada verificação.",
    )
    botao_registrar_calculo(
        registro_combinacoes,
        key="registrar_estrutura_combinacoes",
        rotulo="Registrar combinações no projeto",
        tipo="secondary",
        identificar_peca=False,
    )


elif modulo == "4. Ligações":
    st.header("Ligações estruturais")
    tipo_ligacao = st.segmented_control(
        "Verificação",
        ["Parafusos", "Chapa e bloco", "Solda de filete"],
        default="Parafusos",
        required=True,
        width="stretch",
        key="estrutura_ligacao_tipo",
        persist_state="session",
    )

    if tipo_ligacao == "Parafusos":
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.page_link(
                "app_pages/projeto_parafusos.py",
                label="Abrir projeto detalhado da junta",
                icon=":material/open_in_new:",
            )
        escolha_rosca = st.selectbox(
            "Rosca",
            list(parafusos.ROSCAS_METRICAS),
            index=list(parafusos.ROSCAS_METRICAS).index("M20"),
            key="estrutura_ligacao_rosca",
            persist_state="session",
        )
        rosca = parafusos.obter_rosca(escolha_rosca)
        classe_nome = st.selectbox(
            "Classe",
            list(parafusos.CLASSES_PARAFUSO),
            index=list(parafusos.CLASSES_PARAFUSO).index("8.8"),
            key="estrutura_ligacao_classe",
            persist_state="session",
        )
        try:
            classe = parafusos.obter_classe(classe_nome, rosca.diametro_mm)
        except ValueError as erro:
            st.error(str(erro), icon=":material/error:")
            st.stop()
        dados = st.columns(4)
        n_parafusos = dados[0].number_input(
            "Número de parafusos", 1, value=4, key="estrutura_lig_n_parafusos"
        )
        planos = dados[1].number_input("Planos de corte", 1, value=1, key="estrutura_lig_planos")
        vd = dados[2].number_input("|Vd| (kN)", 0.0, value=100.0, key="estrutura_lig_vd")
        td = dados[3].number_input("|Td| (kN)", 0.0, value=20.0, key="estrutura_lig_td")
        chapa = st.columns(4)
        t = chapa[0].number_input("Espessura da chapa (mm)", 0.1, value=10.0, key="estrutura_lig_t")
        fu_chapa = chapa[1].number_input(
            "Fu da chapa (MPa)", 1.0, value=400.0, key="estrutura_lig_fu_chapa"
        )
        lc = chapa[2].number_input(
            "Distância livre Lc na direção da força (mm)",
            0.1,
            value=30.0,
            key="estrutura_lig_lc",
        )
        pre_tensao = chapa[3].number_input(
            "Pré-tensão por parafuso (kN)",
            0.0,
            value=50.0,
            key="estrutura_lig_pre_tensao",
        )
        atrito = st.columns(2)
        mu = atrito[0].number_input(
            "Coeficiente de atrito", 0.0, value=0.30, key="estrutura_lig_mu"
        )
        interfaces = atrito[1].number_input(
            "Interfaces de atrito", 1, value=1, key="estrutura_lig_interfaces"
        )
        with st.expander("Coeficientes da ligação", icon=":material/settings:"):
            cs = st.columns(4)
            cnv = cs[0].number_input(
                "Coef. cisalhamento", 0.01, value=0.48, key="estrutura_lig_cnv"
            )
            cnt = cs[1].number_input("Coef. tração", 0.01, value=0.75, key="estrutura_lig_cnt")
            phi_b = cs[2].number_input(
                "φ parafuso", 0.01, 1.0, value=0.75, key="estrutura_lig_phi_b"
            )
            phi_c = cs[3].number_input(
                "φ contato", 0.01, 1.0, value=0.75, key="estrutura_lig_phi_c"
            )
            cc = st.columns(3)
            c_lc = cc[0].number_input("Coef. Lc", 0.01, value=1.20, key="estrutura_lig_c_lc")
            c_lim = cc[1].number_input(
                "Coef. limite contato", 0.01, value=2.40, key="estrutura_lig_c_lim"
            )
            phi_s = cc[2].number_input(
                "φ deslizamento", 0.01, 1.0, value=1.0, key="estrutura_lig_phi_s"
            )
        resultado = ligacoes.verificar_ligacao_parafusada(
            int(n_parafusos),
            rosca.area_tracao_mm2,
            classe.ruptura_min_MPa,
            cnv,
            cnt,
            phi_b,
            int(planos),
            vd * 1e3,
            td * 1e3,
            t,
            fu_chapa,
            rosca.diametro_mm,
            lc,
            c_lc,
            c_lim,
            phi_c,
            pre_tensao * 1e3,
            mu,
            int(interfaces),
            phi_s,
        )
        criterios = pd.DataFrame(
            {
                "Modo": [
                    "Cisalhamento dos parafusos",
                    "Tração dos parafusos",
                    "Pressão de contato/rasgamento",
                    "Deslizamento",
                ],
                "Resistência (kN)": [
                    resultado.resistencia_cisalhamento_parafusos_N / 1e3,
                    resultado.resistencia_tracao_parafusos_N / 1e3,
                    resultado.resistencia_pressao_contato_N / 1e3,
                    resultado.resistencia_deslizamento_N / 1e3,
                ],
                "Fator": [
                    resultado.fator_cisalhamento,
                    resultado.fator_tracao,
                    resultado.fator_contato,
                    resultado.fator_deslizamento,
                ],
            }
        )
        st.dataframe(
            criterios,
            hide_index=True,
            column_config={
                "Resistência (kN)": st.column_config.NumberColumn(format="%.2f"),
                "Fator": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        st.download_button(
            "Baixar resultado da ligação parafusada em CSV",
            data=criterios.to_csv(index=False).encode("utf-8-sig"),
            file_name="estrutura_aco_ligacao_parafusos.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="aco_baixar_ligacao_parafusos",
        )
        st.metric(
            "Interação quadrática tração–cisalhamento",
            f"{resultado.interacao_parafuso:.3f}",
            border=True,
        )
        mostrar_utilizacao(
            "Interação dos parafusos",
            resultado.interacao_parafuso,
        )

    elif tipo_ligacao == "Chapa e bloco":
        material = st.columns(3)
        fy = material[0].number_input(
            "Fy da chapa (MPa)", 1.0, value=250.0, key="estrutura_bloco_fy"
        )
        fu = material[1].number_input(
            "Fu da chapa (MPa)", 1.0, value=400.0, key="estrutura_bloco_fu"
        )
        sd = material[2].number_input("|Sd| (kN)", 0.0, value=100.0, key="estrutura_bloco_sd")
        areas = st.columns(4)
        ant = areas[0].number_input(
            "An de tração (mm²)", 0.1, value=800.0, key="estrutura_bloco_ant"
        )
        agv = areas[1].number_input(
            "Agv do bloco (mm²)", 0.1, value=1200.0, key="estrutura_bloco_agv"
        )
        anv = areas[2].number_input(
            "Anv do bloco (mm²)", 0.1, value=900.0, key="estrutura_bloco_anv"
        )
        antb = areas[3].number_input(
            "Ant do bloco (mm²)", 0.1, value=400.0, key="estrutura_bloco_antb"
        )
        fatores = st.columns(2)
        ubs = fatores[0].number_input("Ubs", 0.01, 1.0, value=1.0, key="estrutura_bloco_ubs")
        phi = fatores[1].number_input("φ ruptura", 0.01, 1.0, value=0.75, key="estrutura_bloco_phi")
        resultado = ligacoes.verificar_chapa_ligacao(
            fu, fy, ant, agv, anv, antb, ubs, phi, sd * 1e3
        )
        with st.container(horizontal=True):
            st.metric(
                "Seção líquida",
                f"{resultado.resistencia_secao_liquida_N / 1e3:.1f} kN",
                border=True,
            )
            st.metric(
                "Cisalhamento de bloco",
                f"{resultado.resistencia_cisalhamento_bloco_N / 1e3:.1f} kN",
                border=True,
            )
        mostrar_utilizacao(
            "Ruptura da seção líquida",
            1.0 / resultado.fator_secao_liquida
            if not math.isinf(resultado.fator_secao_liquida)
            else 0.0,
        )
        mostrar_utilizacao(
            "Cisalhamento de bloco",
            1.0 / resultado.fator_cisalhamento_bloco
            if not math.isinf(resultado.fator_cisalhamento_bloco)
            else 0.0,
        )
        tabela_resumo_bloco = pd.DataFrame(
            {
                "Grandeza": [
                    "Resistência da seção líquida (kN)",
                    "Resistência ao cisalhamento de bloco (kN)",
                    "Fator seção líquida",
                    "Fator cisalhamento de bloco",
                ],
                "Valor": [
                    resultado.resistencia_secao_liquida_N / 1e3,
                    resultado.resistencia_cisalhamento_bloco_N / 1e3,
                    None
                    if math.isinf(resultado.fator_secao_liquida)
                    else resultado.fator_secao_liquida,
                    None
                    if math.isinf(resultado.fator_cisalhamento_bloco)
                    else resultado.fator_cisalhamento_bloco,
                ],
            }
        )
        st.download_button(
            "Baixar resultado da chapa e bloco em CSV",
            data=tabela_resumo_bloco.to_csv(index=False).encode("utf-8-sig"),
            file_name="estrutura_aco_ligacao_bloco.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="aco_baixar_ligacao_bloco",
        )

    else:
        solda = st.columns(4)
        perna = solda[0].number_input(
            "Perna da solda a (mm)", 0.1, value=6.0, key="estrutura_solda_perna"
        )
        comprimento = solda[1].number_input(
            "Comprimento total efetivo (mm)",
            0.1,
            value=300.0,
            key="estrutura_solda_comprimento",
        )
        fexx = solda[2].number_input("FEXX (MPa)", 1.0, value=490.0, key="estrutura_solda_fexx")
        sd = solda[3].number_input("|Sd| (kN)", 0.0, value=100.0, key="estrutura_solda_sd")
        coef = st.columns(2)
        c_solda = coef[0].number_input(
            "Coeficiente resistente", 0.01, value=0.60, key="estrutura_solda_c_solda"
        )
        phi = coef[1].number_input("φ solda", 0.01, 1.0, value=0.75, key="estrutura_solda_phi")
        resultado = ligacoes.verificar_solda_filete(
            perna, comprimento, fexx, c_solda, phi, sd * 1e3
        )
        with st.container(horizontal=True):
            st.metric(
                "Garganta efetiva",
                f"{0.707 * perna:.2f} mm",
                border=True,
            )
            st.metric(
                "Área efetiva",
                f"{resultado.area_efetiva_mm2:.1f} mm²",
                border=True,
            )
            st.metric(
                "Resistência",
                f"{resultado.resistencia_N / 1e3:.1f} kN",
                border=True,
            )
            st.metric(
                "Fator",
                fator_texto(resultado.fator_seguranca),
                border=True,
            )
        mostrar_utilizacao(
            "Solda de filete",
            1.0 / resultado.fator_seguranca if not math.isinf(resultado.fator_seguranca) else 0.0,
        )
        tabela_resumo_solda = pd.DataFrame(
            {
                "Grandeza": [
                    "Garganta efetiva (mm)",
                    "Área efetiva (mm²)",
                    "Resistência (kN)",
                    "Fator",
                ],
                "Valor": [
                    0.707 * perna,
                    resultado.area_efetiva_mm2,
                    resultado.resistencia_N / 1e3,
                    None if math.isinf(resultado.fator_seguranca) else resultado.fator_seguranca,
                ],
            }
        )
        st.download_button(
            "Baixar resultado da solda de filete em CSV",
            data=tabela_resumo_solda.to_csv(index=False).encode("utf-8-sig"),
            file_name="estrutura_aco_ligacao_solda.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="aco_baixar_ligacao_solda",
        )

    st.caption(
        "Os coeficientes padrão são valores preliminares. Confirme furação, "
        "distâncias mínimas, parafusos estruturais, soldabilidade e inspeção."
    )


else:
    st.header("Análise elástica linear 2D")
    st.warning(
        "O solver é de primeira ordem, com pequenas deformações. Não inclui "
        "P–Δ, imperfeições, ligações semirrígidas, flambagem ou não linearidade.",
        icon=":material/warning:",
    )
    modelo = st.segmented_control(
        "Modelo estrutural",
        ["Treliça 2D", "Pórtico 2D"],
        default="Treliça 2D",
        required=True,
        width="stretch",
        key="estrutura_2d_modelo",
        persist_state="session",
    )
    perfil_padrao = 'I 4" x 11,46'
    if modelo == "Treliça 2D":
        nos_padrao = pd.DataFrame(
            [
                [1, 0.0, 0.0, True, True, 0.0, 0.0],
                [2, 4.0, 0.0, False, True, 0.0, 0.0],
                [3, 2.0, 3.0, False, False, 0.0, -100.0],
            ],
            columns=["id", "x (m)", "y (m)", "fixa x", "fixa y", "Fx (kN)", "Fy (kN)"],
        )
        elementos_padrao = pd.DataFrame(
            [
                [1, 1, 2, perfil_padrao, 200.0],
                [2, 1, 3, perfil_padrao, 200.0],
                [3, 2, 3, perfil_padrao, 200.0],
            ],
            columns=["id", "nó i", "nó j", "perfil", "E (GPa)"],
        )
    else:
        nos_padrao = pd.DataFrame(
            [
                [1, 0.0, 0.0, True, True, True, 0.0, 0.0, 0.0],
                [2, 0.0, 3.0, False, False, False, 0.0, 0.0, 0.0],
                [3, 4.0, 3.0, False, False, False, 0.0, 0.0, 0.0],
                [4, 4.0, 0.0, True, True, True, 0.0, 0.0, 0.0],
            ],
            columns=[
                "id",
                "x (m)",
                "y (m)",
                "fixa x",
                "fixa y",
                "fixa rotação",
                "Fx (kN)",
                "Fy (kN)",
                "Mz (kN·m)",
            ],
        )
        elementos_padrao = pd.DataFrame(
            [
                [1, 1, 2, perfil_padrao, 200.0, 0.0],
                [2, 2, 3, perfil_padrao, 200.0, -10.0],
                [3, 3, 4, perfil_padrao, 200.0, 0.0],
            ],
            columns=["id", "nó i", "nó j", "perfil", "E (GPa)", "qy local (kN/m)"],
        )

    st.subheader("Nós")
    nos_editados = st.data_editor(
        nos_padrao,
        num_rows="dynamic",
        hide_index=True,
        key=f"estrutura_nos_{modelo}",
    )
    st.subheader("Elementos")
    elementos_editados = st.data_editor(
        elementos_padrao,
        num_rows="dynamic",
        hide_index=True,
        key=f"estrutura_elementos_{modelo}",
        column_config={
            "perfil": st.column_config.SelectboxColumn(
                options=list(catalogo_perfis.listar_perfis()),
                required=True,
            )
        },
    )
    analisar = st.button(
        "Analisar estrutura",
        type="primary",
        icon=":material/calculate:",
        width="stretch",
    )
    if analisar:
        try:
            if modelo == "Treliça 2D":
                nos = [
                    estrutural.NoTrelica(
                        id=int(linha["id"]),
                        x_mm=float(linha["x (m)"]) * 1e3,
                        y_mm=float(linha["y (m)"]) * 1e3,
                        restringe_x=bool(linha["fixa x"]),
                        restringe_y=bool(linha["fixa y"]),
                        fx_N=float(linha["Fx (kN)"]) * 1e3,
                        fy_N=float(linha["Fy (kN)"]) * 1e3,
                    )
                    for _, linha in nos_editados.dropna().iterrows()
                ]
                elementos = []
                for _, linha in elementos_editados.dropna().iterrows():
                    perfil_elemento = catalogo_perfis.obter_perfil(str(linha["perfil"]))
                    elementos.append(
                        estrutural.ElementoTrelica(
                            id=int(linha["id"]),
                            no_i=int(linha["nó i"]),
                            no_j=int(linha["nó j"]),
                            area_mm2=perfil_elemento.area_mm2,
                            modulo_elasticidade_MPa=float(linha["E (GPa)"]) * 1e3,
                        )
                    )
                resultado = estrutural.analisar_trelica(nos, elementos)
            else:
                nos = [
                    estrutural.NoPortico(
                        id=int(linha["id"]),
                        x_mm=float(linha["x (m)"]) * 1e3,
                        y_mm=float(linha["y (m)"]) * 1e3,
                        restringe_x=bool(linha["fixa x"]),
                        restringe_y=bool(linha["fixa y"]),
                        restringe_rotacao=bool(linha["fixa rotação"]),
                        fx_N=float(linha["Fx (kN)"]) * 1e3,
                        fy_N=float(linha["Fy (kN)"]) * 1e3,
                        mz_Nmm=float(linha["Mz (kN·m)"]) * 1e6,
                    )
                    for _, linha in nos_editados.dropna().iterrows()
                ]
                elementos = []
                for _, linha in elementos_editados.dropna().iterrows():
                    perfil_elemento = catalogo_perfis.obter_perfil(str(linha["perfil"]))
                    elementos.append(
                        estrutural.ElementoPortico(
                            id=int(linha["id"]),
                            no_i=int(linha["nó i"]),
                            no_j=int(linha["nó j"]),
                            area_mm2=perfil_elemento.area_mm2,
                            inercia_mm4=perfil_elemento.ix_mm4,
                            modulo_elasticidade_MPa=float(linha["E (GPa)"]) * 1e3,
                            carga_distribuida_local_y_N_mm=float(linha["qy local (kN/m)"]),
                        )
                    )
                resultado = estrutural.analisar_portico(nos, elementos)
        except (ValueError, TypeError, KeyError) as erro:
            st.error(f"Modelo inválido: {erro}", icon=":material/error:")
        else:
            # Guardado em session_state (e não só nas variáveis locais) para
            # que o resultado sobreviva ao clique em "Registrar análise 2D no
            # projeto": esse clique também dispara um rerun do script, no
            # qual "analisar" (um st.button comum) voltaria a ser False.
            st.session_state["estrutura_2d_resultado"] = {
                "modelo": modelo,
                "nos": nos,
                "elementos": elementos,
                "resultado": resultado,
            }

    resultado_estrutura_2d = st.session_state.get("estrutura_2d_resultado")
    if resultado_estrutura_2d and resultado_estrutura_2d["modelo"] == modelo:
        nos = resultado_estrutura_2d["nos"]
        elementos = resultado_estrutura_2d["elementos"]
        resultado = resultado_estrutura_2d["resultado"]

        st.subheader("Resultados")
        st.metric(
            "Maior deslocamento translacional",
            f"{resultado.deslocamento_maximo_mm:.3f} mm",
            border=True,
        )
        deslocamentos = pd.DataFrame(resultado.deslocamentos_nodais)
        reacoes = pd.DataFrame(resultado.reacoes_nodais)
        esforcos = pd.DataFrame(resultado.esforcos_elementos)
        for coluna in reacoes.columns:
            if coluna.endswith("_N"):
                reacoes[coluna] = reacoes[coluna] / 1e3
                reacoes.rename(columns={coluna: coluna.replace("_N", "_kN")}, inplace=True)
            elif coluna.endswith("_Nmm"):
                reacoes[coluna] = reacoes[coluna] / 1e6
                reacoes.rename(columns={coluna: coluna.replace("_Nmm", "_kNm")}, inplace=True)
        for coluna in esforcos.columns:
            if coluna.endswith("_N"):
                esforcos[coluna] = esforcos[coluna] / 1e3
                esforcos.rename(columns={coluna: coluna.replace("_N", "_kN")}, inplace=True)
            elif coluna.endswith("_Nmm"):
                esforcos[coluna] = esforcos[coluna] / 1e6
                esforcos.rename(columns={coluna: coluna.replace("_Nmm", "_kNm")}, inplace=True)
        resultados_tabs = st.tabs(["Deslocamentos", "Reações", "Esforços"])
        with resultados_tabs[0]:
            st.dataframe(deslocamentos, hide_index=True)
            st.download_button(
                "Baixar deslocamentos em CSV",
                data=deslocamentos.to_csv(index=False).encode("utf-8-sig"),
                file_name="estrutura_aco_2d_deslocamentos.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
                key="aco_baixar_2d_deslocamentos",
            )
        with resultados_tabs[1]:
            st.dataframe(reacoes, hide_index=True)
            st.download_button(
                "Baixar reações em CSV",
                data=reacoes.to_csv(index=False).encode("utf-8-sig"),
                file_name="estrutura_aco_2d_reacoes.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
                key="aco_baixar_2d_reacoes",
            )
        with resultados_tabs[2]:
            st.dataframe(esforcos, hide_index=True)
            st.download_button(
                "Baixar esforços em CSV",
                data=esforcos.to_csv(index=False).encode("utf-8-sig"),
                file_name="estrutura_aco_2d_esforcos.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
                key="aco_baixar_2d_esforcos",
            )

        coordenadas = {int(no.id): (no.x_mm / 1e3, no.y_mm / 1e3) for no in nos}
        desloc_por_no = {
            int(item["no"]): (item["ux_mm"], item["uy_mm"])
            for item in resultado.deslocamentos_nodais
        }
        maior_dimensao = max(
            max(x for x, _ in coordenadas.values()) - min(x for x, _ in coordenadas.values()),
            max(y for _, y in coordenadas.values()) - min(y for _, y in coordenadas.values()),
            1.0,
        )
        escala = (
            1.0
            if resultado.deslocamento_maximo_mm == 0
            else 0.15 * maior_dimensao * 1e3 / resultado.deslocamento_maximo_mm
        )
        linhas_grafico = []
        for elemento in elementos:
            for estado, fator in (("Original", 0.0), ("Deformada", escala)):
                for ordem, no_id in enumerate((elemento.no_i, elemento.no_j)):
                    x, y = coordenadas[no_id]
                    ux, uy = desloc_por_no[no_id]
                    linhas_grafico.append(
                        {
                            "elemento": str(elemento.id),
                            "estado": estado,
                            "ordem": ordem,
                            "x (m)": x + fator * ux / 1e3,
                            "y (m)": y + fator * uy / 1e3,
                        }
                    )
        df_grafico = pd.DataFrame(linhas_grafico)
        grafico = (
            alt.Chart(df_grafico)
            .mark_line(point=True)
            .encode(
                x=alt.X("x (m):Q", scale=alt.Scale(zero=False)),
                y=alt.Y("y (m):Q", scale=alt.Scale(zero=False)),
                color=alt.Color("estado:N"),
                detail="elemento:N",
                order="ordem:O",
                strokeDash=alt.StrokeDash("estado:N"),
                tooltip=["elemento", "estado", "x (m)", "y (m)"],
            )
            .properties(height=420)
            .interactive()
        )
        st.altair_chart(grafico)
        st.caption(f"Forma deformada ampliada {escala:.1f}×.")

        fronteira_modelo(
            [
                "Efeitos de segunda ordem (P–Δ, P–δ) e imperfeições geométricas iniciais.",
                "Flambagem global ou local dos elementos.",
                "Ligações semirrígidas — os apoios e nós são idealizados como rígidos ou rotulados.",
                "Combinações de ações e dimensionamento de cada barra (fazer em separado).",
            ]
        )

        registro_modelo_2d = construir_registro_tecnico(
            modulo="Estruturas de aço",
            modulo_id="estruturas_aco",
            titulo=f"Análise linear — {modelo}",
            status="Calculado",
            resumo="Análise elástica linear de treliça ou pórtico plano com deslocamentos, reações e esforços internos.",
            entradas={
                "modelo": modelo,
                "numero_nos": len(nos),
                "numero_elementos": len(elementos),
                "nos": [asdict(item) for item in nos],
                "elementos": [asdict(item) for item in elementos],
            },
            resultados={
                "deslocamento_maximo_mm": resultado.deslocamento_maximo_mm,
                "deslocamentos_nodais": resultado.deslocamentos_nodais,
                "reacoes_nodais": resultado.reacoes_nodais,
                "esforcos_elementos": resultado.esforcos_elementos,
            },
            premissas=[
                "Análise linear elástica, pequenas deformações e ligações idealizadas.",
                "Propriedades geométricas e módulos são os valores informados no modelo.",
            ],
            alertas=[
                "Estabilidade, imperfeições, segunda ordem, ligações e combinações não são verificadas automaticamente por este modelo."
            ],
            referencias=[
                "Vincular o modelo aos desenhos, combinações de ações e critérios de deslocamento do projeto."
            ],
            conclusao="Modelo resolvido sem singularidade; validar idealização, deslocamentos admissíveis e dimensionar cada elemento.",
        )
        botao_registrar_calculo(
            registro_modelo_2d,
            key="registrar_estrutura_2d",
            rotulo="Registrar análise 2D no projeto",
            identificar_peca=False,
        )

st.caption(
    "Referências de escopo: ABNT NBR 8800:2024, ABNT NBR 8681:2025, "
    "ABNT NBR 6120:2019 e ABNT NBR 6123:2023."
)
