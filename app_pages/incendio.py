"""Barras de aço em situação de incêndio (NBR 14323, método simplificado)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.croquis_de_referencia import mostrar_croqui_de_referencia
from components.incendio_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import incendio as inc
from core import perfil_i as pi

configurar_pagina("Estrutura em incêndio", ":material/local_fire_department:")
cabecalho_pagina(
    "Estrutura em incêndio",
    "Temperatura do aço pela curva-padrão, com ou sem proteção • pilar, tirante e viga a quente "
    "• ABNT NBR 14323 (método simplificado) • TRRF da NBR 14432",
    categoria="Dimensionamento",
    icone=":material/local_fire_department:",
    cor="blue",
    ajuda_modulo="Estrutura em incêndio",
    modulo_id=inc.MODULO_ID,
)
st.caption(
    "Calcula quanto o perfil esquenta no tempo exigido de incêndio e se ele ainda resiste à "
    "combinação de incêndio — ou quanta proteção precisa."
)
mostrar_croqui_de_referencia("incendio")

P = inc.EntradaIncendio()
c_ = Campos("inc_", AJUDA)

with st.container(border=True), secao_protegida("1. Elemento"):
    c_.titulo("1. Elemento", "sec_elemento")
    c = st.columns(2)
    elemento = c_.escolha("Elemento", "elemento", inc.ELEMENTOS, P.elemento, c[0])
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[1])
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
    c = st.columns(4)
    L = c_.numero("L (mm)", "L", P.L, c[0], minimo=1.0, passo=100.0, formato="%.0f")
    K, Cb, hiper = P.K, P.Cb, P.viga_hiperestatica
    if elemento == inc.PILAR:
        K = c_.numero("K", "K", P.K, c[1], minimo=0.1, maximo=5.0, passo=0.05, formato="%.2f")
    if elemento == inc.VIGA:
        Cb = c_.numero("C_b", "Cb", P.Cb, c[1], minimo=1.0, maximo=3.0, passo=0.05, formato="%.2f")
        hiper = c_.chave("Apoio de viga contínua", "viga_hiperestatica", P.viga_hiperestatica, c[2])

with st.container(border=True), secao_protegida("2. Incêndio"):
    c_.titulo("2. Tempo e exposição", "sec_fogo")
    c = st.columns(3)
    trrf = c_.numero("TRRF (min)", "trrf", P.trrf, c[0], minimo=1.0, maximo=240.0, passo=30.0,
                     formato="%.0f")  # fmt: skip
    exposicao = c_.escolha("Exposição", "exposicao", inc.EXPOSICOES, P.exposicao, c[1])
    t_inf = c_.numero("Temperatura do aço (°C, 0 = calcular)", "temperatura_informada",
                      P.temperatura_informada, c[2], maximo=1200.0, passo=10.0, formato="%.0f")  # fmt: skip

with st.container(border=True), secao_protegida("3. Proteção"):
    c_.titulo("3. Proteção contra fogo", "sec_protecao")
    c = st.columns(5)
    protecao = c_.escolha("Proteção", "protecao", list(inc.PROTECOES), P.protecao, c[0])
    lam_t, rho_t, c_t = inc.PROTECOES[protecao]
    tm, lam, rho, cm = P.tm, lam_t, rho_t, c_t
    if protecao != "Sem proteção":
        sufixo = "_" + str(list(inc.PROTECOES).index(protecao))
        tm = c_.numero("Espessura (mm)", "tm", P.tm, c[1], minimo=1.0, passo=1.0, formato="%.0f")
        lam = c_.numero("λ (W/m·°C)", "lambda_m", lam_t, c[2], minimo=0.001, passo=0.01,
                        formato="%.3f", sufixo=sufixo)  # fmt: skip
        rho = c_.numero("ρ (kg/m³)", "rho_m", rho_t, c[3], minimo=1.0, passo=10.0,
                        formato="%.0f", sufixo=sufixo)  # fmt: skip
        cm = c_.numero("c (J/kg·°C)", "c_m", c_t, c[4], minimo=1.0, passo=50.0, formato="%.0f",
                       sufixo=sufixo)  # fmt: skip

with st.container(border=True), secao_protegida("4. Esforços"):
    c_.titulo("4. Esforços característicos", "sec_esforcos")
    c = st.columns(4)
    unidade = "kN·m" if elemento == inc.VIGA else "kN"
    G = c_.numero(f"G_k ({unidade})", "G_k", P.G_k, c[0], passo=10.0)
    Q = c_.numero(f"Q_k ({unidade})", "Q_k", P.Q_k, c[1], passo=10.0)
    gg = c_.numero("γg", "gama_g", P.gama_g, c[2], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    ocup = c_.escolha("Ocupação", "ocupacao", list(inc.OCUPACOES), P.ocupacao, c[3])

entrada = inc.EntradaIncendio(
    elemento=elemento, familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, aco=aco, L=L,
    K=K, Cb=Cb, exposicao=exposicao, trrf=trrf, protecao=protecao, tm=tm, lambda_m=lam,
    rho_m=rho, c_m=cm, temperatura_informada=t_inf, G_k=G, Q_k=Q, gama_g=gg, ocupacao=ocup,
    viga_hiperestatica=hiper,
)  # fmt: skip
erros = inc.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = inc.calcular(entrada)

with st.container(border=True), secao_protegida("Temperaturas"):
    c_.titulo("Temperaturas no tempo", "sec_grafico")
    c = st.columns(3)
    c[0].metric("Temperatura do aço", f"{r.theta:.0f} °C", help=AJUDA["res_temperatura"])
    c[1].metric("k_y,θ", pi.numero(r.ky, 3), help=AJUDA["res_ky"])
    c[2].metric("u/A", f"{pi.numero(r.u_A, 1)} m⁻¹", help=AJUDA["res_massividade"])
    if r.curva:
        st.line_chart(
            pd.DataFrame(r.curva, columns=["Tempo (min)", "Gases (°C)", "Aço (°C)"]).set_index(
                "Tempo (min)"
            ),
            height=260,
        )

mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    inc.registro(r),
    prefixo="inc_",
    arquivo="memorial_incendio",
    rotulo_registrar="Registrar a verificação de incêndio no projeto ativo",
)
