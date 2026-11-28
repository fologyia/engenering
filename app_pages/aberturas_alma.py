"""Aberturas na alma de vigas de aço (NBR 8800:2025, Anexo F; AISC Design Guide 2)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import robot_esforcos_ui as robot_ui
from components.aberturas_alma_help import AJUDA
from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import aberturas_alma as ab
from core import desenho_aberturas_alma as desenho
from core import perfil_i as pi
from core import robot_integracao as robot_calculo

configurar_pagina("Aberturas na alma", ":material/radio_button_unchecked:")
cabecalho_pagina(
    "Aberturas na alma",
    "Furos para tubulação, eletrocalha ou duto na alma da viga • dispensa da NBR 8800 (F.3) e "
    "resistência na abertura pelo AISC Design Guide 2",
    categoria="Dimensionamento",
    icone=":material/radio_button_unchecked:",
    cor="blue",
    ajuda_modulo="Aberturas na alma",
    modulo_id=ab.MODULO_ID,
)
st.caption(
    "Diz se o furo na alma pode ser feito sem cálculo (NBR 8800, F.3) e, quando não pode, "
    "verifica a viga na seção do furo: momento, cortante e as proporções."
)

P = ab.EntradaAberturas()
c_ = Campos("ab_", AJUDA)

with st.container(border=True), secao_protegida("1. Viga"):
    c_.titulo("1. Viga", "sec_viga")
    familia = c_.escolha("Perfil", "familia", pi.FAMILIAS, P.familia, horizontal=True)
    d, bf, tf, tw, perfil = P.d, P.bf, P.tf, P.tw, P.perfil
    if familia == pi.FAMILIA_SOLDADO:
        c = st.columns(4)
        d = c_.numero("d (mm)", "d", P.d, c[0], minimo=1.0)
        bf = c_.numero("b_f (mm)", "bf", P.bf, c[1], minimo=1.0)
        tf = c_.numero("t_f (mm)", "tf", P.tf, c[2], minimo=0.5, passo=0.5)
        tw = c_.numero("t_w (mm)", "tw", P.tw, c[3], minimo=0.5, passo=0.5)
    else:
        lista = pi.nomes(familia)
        perfil = c_.escolha("Bitola", "perfil", lista, P.perfil if P.perfil in lista else lista[0],
                            sufixo="_" + familia[:1])  # fmt: skip
    c = st.columns(5)
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[0])
    g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    L = c_.numero("Vão L (mm)", "L", P.L, c[2], minimo=1.0, passo=100.0, formato="%.0f")
    q = c_.numero("q_d (kN/m)", "q", P.q, c[3], passo=1.0)
    Lb = c_.numero("L_b (mm)", "Lb", P.Lb, c[4], passo=100.0, formato="%.0f")

with st.container(border=True), secao_protegida("2. Aberturas"):
    c_.titulo("2. Aberturas", "sec_aberturas")
    tabela = st.data_editor(
        pd.DataFrame(ab.tabela_das_aberturas(P.aberturas)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="ab_aberturas",
        column_config={
            "Abertura": st.column_config.TextColumn(help=AJUDA["tabela_aberturas"]),
            "Forma": st.column_config.SelectboxColumn(options=list(ab.FORMAS), default=ab.CIRCULAR,
                                                      help=AJUDA["tabela_aberturas"]),
            "Largura ou D (mm)": st.column_config.NumberColumn(min_value=0.0, default=100.0,
                                                               help=AJUDA["tabela_aberturas"]),
            "Altura (mm)": st.column_config.NumberColumn(min_value=0.0, default=100.0,
                                                         help=AJUDA["tabela_aberturas"]),
            "Centro a partir do apoio (mm)": st.column_config.NumberColumn(
                min_value=0.0, default=1000.0, help=AJUDA["tabela_aberturas"]),
            "Excentricidade (mm)": st.column_config.NumberColumn(default=0.0,
                                                                 help=AJUDA["tabela_aberturas"]),
        },
    )  # fmt: skip
    aberturas = ab.aberturas_de_tabela(tabela.to_dict("records"))

entrada = ab.EntradaAberturas(familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, aco=aco,
                              gama_a1=g1, L=L, q=q, Lb=Lb, aberturas=aberturas)  # fmt: skip
esforcos_robot, origem_robot, pronto = robot_ui.aberturas("ab_robot", entrada)
if not pronto:
    st.stop()
if esforcos_robot:
    entrada = ab.com(entrada, esforcos=esforcos_robot)
erros = ab.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = ab.calcular(entrada)
with st.container(border=True):
    st.subheader(
        "Detalhes das aberturas",
        help="Vistas locais proporcionais às dimensões e à excentricidade informadas; não representam o vão inteiro.",
    )
    st.caption("Trechos locais proporcionais; a posição x é medida desde o apoio esquerdo.")
    for abertura in entrada.aberturas:
        mostrar_figura(svg_da_cena(desenho.detalhe(entrada, abertura)))
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    robot_calculo.registrar(ab.registro(r), origem_robot),
    prefixo="ab_",
    arquivo="memorial_aberturas_na_alma",
    rotulo_registrar="Registrar as aberturas no projeto ativo",
)
