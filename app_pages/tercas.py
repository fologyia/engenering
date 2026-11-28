"""Terças e travessas em perfil U enrijecido formado a frio (NBR 14762:2010)."""

from __future__ import annotations

import streamlit as st

from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.tercas_help import AJUDA
from components.ui import cabecalho_pagina, configurar_pagina
from core import desenho_tercas as desenho
from core import tercas as tc

configurar_pagina("Terças e travessas", ":material/roofing:")
cabecalho_pagina(
    "Terças e travessas",
    "Perfil U enrijecido formado a frio na cobertura ou no fechamento • seção efetiva, FLT, "
    "distorcional, sucção do vento (Anexo F) e flechas • ABNT NBR 14762:2010",
    categoria="Dimensionamento",
    icone=":material/roofing:",
    cor="blue",
    ajuda_modulo="Terças e travessas",
    modulo_id=tc.MODULO_ID,
)
st.caption(
    "Verifica a terça (ou travessa) de chapa dobrada sob peso, sobrecarga e vento — inclusive a "
    "sucção, que comprime a mesa de baixo, solta."
)

P = tc.EntradaTerca()
c_ = Campos("tc_", AJUDA)

with st.container(border=True), secao_protegida("1. Perfil"):
    c_.titulo("1. Perfil Ue", "sec_perfil")
    c = st.columns(6)
    uso = c_.escolha("Uso", "uso", tc.USOS, P.uso, c[0])
    bw = c_.numero("b_w (mm)", "bw", P.bw, c[1], minimo=10.0, passo=5.0, formato="%.0f")
    bf = c_.numero("b_f (mm)", "bf", P.bf, c[2], minimo=5.0, passo=5.0, formato="%.0f")
    D = c_.numero("D (mm)", "D", P.D, c[3], minimo=1.0, passo=1.0, formato="%.0f")
    t = c_.numero("t (mm)", "t", P.t, c[4], minimo=0.3, passo=0.05, formato="%.2f")
    aco = c_.escolha("Aço", "aco", list(tc.ACOS_FRIO), P.aco, c[5])

with st.container(border=True), secao_protegida("2. Vão"):
    c_.titulo("2. Vão e faixa de telha", "sec_vao")
    c = st.columns(4)
    L = c_.numero("Vão L (mm)", "L", P.L, c[0], minimo=1.0, passo=100.0, formato="%.0f")
    tirantes = c_.inteiro("Linhas de corrente", "tirantes", P.tirantes, c[1], minimo=0, maximo=10)
    esp = c_.numero("Espaçamento (mm)", "espacamento", P.espacamento, c[2], minimo=1.0,
                    passo=50.0, formato="%.0f")  # fmt: skip
    inc = P.inclinacao
    if uso == tc.TERCA:
        inc = c_.numero("Inclinação (°)", "inclinacao", P.inclinacao, c[3], maximo=59.0, passo=1.0)

with st.container(border=True), secao_protegida("3. Cargas"):
    c_.titulo("3. Cargas (kN/m²) e coeficientes", "sec_cargas")
    c = st.columns(4)
    g = c_.numero("Telha g", "g", P.g, c[0], passo=0.05, formato="%.2f")
    q = P.q
    if uso == tc.TERCA:
        q = c_.numero("Sobrecarga q", "q", P.q, c[1], passo=0.05, formato="%.2f")
    ws = c_.numero("Vento de sucção", "w_succao", P.w_succao, c[2], passo=0.05, formato="%.2f")
    wp = c_.numero("Vento de pressão", "w_pressao", P.w_pressao, c[3], passo=0.05, formato="%.2f")
    c = st.columns(3)
    gg = c_.numero("γg", "gama_g", P.gama_g, c[0], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    gq = c_.numero("γq", "gama_q", P.gama_q, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    gw = c_.numero("γw", "gama_w", P.gama_w, c[2], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("4. Critérios"):
    c_.titulo("4. Travamento pela telha e flechas", "sec_criterios")
    c = st.columns(5)
    trava = c_.chave("Telha trava a mesa de cima", "telha_trava", P.telha_trava, c[0])
    anexo_f = c_.chave("Sucção pelo Anexo F (fator R)", "usar_anexo_f", P.usar_anexo_f, c[1])
    mdist = c_.numero("M_dist (kN·m)", "M_dist", P.M_dist, c[2], passo=0.5, formato="%.2f")
    fg = c_.numero("Flecha L/… (gravidade)", "flecha_gravidade", P.flecha_gravidade, c[3],
                   minimo=1.0, passo=10.0, formato="%.0f")  # fmt: skip
    fs = c_.numero("Flecha L/… (sucção)", "flecha_succao", P.flecha_succao, c[4], minimo=1.0,
                   passo=10.0, formato="%.0f")  # fmt: skip

entrada = tc.EntradaTerca(
    uso=uso, bw=bw, bf=bf, D=D, t=t, aco=aco, L=L, tirantes=tirantes, inclinacao=inc,
    espacamento=esp, g=g, q=q, w_succao=ws, w_pressao=wp, gama_g=gg, gama_q=gq, gama_w=gw,
    telha_trava=trava, usar_anexo_f=anexo_f, M_dist=mdist, flecha_gravidade=fg, flecha_succao=fs,
)  # fmt: skip
erros = tc.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = tc.calcular(entrada)
with st.container(border=True):
    st.subheader(
        "Seção adotada",
        help="Desenho proporcional do perfil informado, idealizado com cantos retos como no cálculo das propriedades.",
    )
    mostrar_figura(svg_da_cena(desenho.secao(entrada)))
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    tc.registro(r),
    prefixo="tc_",
    arquivo="memorial_terca",
    rotulo_registrar="Registrar a terça no projeto ativo",
)
