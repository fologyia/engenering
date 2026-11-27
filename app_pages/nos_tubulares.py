"""Nós soldados de treliças tubulares (EN 1993-1-8, capítulo 7; NBR 16239)."""

from __future__ import annotations

import streamlit as st

from components.croquis_de_referencia import mostrar_croqui_de_referencia
from components.nos_tubulares_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import nos_tubulares as nt

configurar_pagina("Nós de treliça tubular", ":material/hive:")
cabecalho_pagina(
    "Nós de treliça tubular",
    "Diagonais soldadas direto no banzo: nós T, Y, X, K e N em tubos circulares ou retangulares • "
    "EN 1993-1-8, capítulo 7 • ABNT NBR 16239",
    categoria="Dimensionamento",
    icone=":material/hive:",
    cor="blue",
    ajuda_modulo="Nós de treliça tubular",
    modulo_id=nt.MODULO_ID,
)
st.caption(
    "Em treliça de tubo sem chapa de nó, a parede do banzo é que limita a força das diagonais: "
    "verifica a face do banzo, a punção, a parede lateral e a própria diagonal."
)
mostrar_croqui_de_referencia("nos_tubulares")

P = nt.EntradaNo()
c_ = Campos("nt_", AJUDA)

with st.container(border=True), secao_protegida("1. Nó"):
    c_.titulo("1. Tipo de nó e aços", "sec_no")
    c = st.columns(4)
    forma = c_.escolha("Forma dos tubos", "forma", nt.FORMAS, P.forma, c[0])
    tipo = c_.escolha("Tipo de nó", "tipo", nt.TIPOS, P.tipo, c[1])
    aco0 = c_.escolha("Aço do banzo", "aco_banzo", list(nt.ACOS_TUBOS), P.aco_banzo, c[2])
    acoi = c_.escolha("Aço das diagonais", "aco_diagonais", list(nt.ACOS_TUBOS), P.aco_diagonais,
                      c[3])  # fmt: skip

ret = forma == nt.RETANGULAR
s = "_r" if ret else "_c"
# valores de partida coerentes com a forma: o retangular tem outras medidas comerciais
B0 = nt.Tubo(150.0, 150.0, 6.3) if ret else P.banzo
B1 = nt.Tubo(80.0, 80.0, 4.0) if ret else P.diagonal1
G0 = 40.0 if ret else P.g

with st.container(border=True), secao_protegida("2. Banzo"):
    c_.titulo("2. Banzo", "sec_banzo")
    c = st.columns(5)
    b0 = c_.numero("b₀ ou d₀ (mm)", "b0", B0.b, c[0], minimo=1.0, sufixo=s)
    h0 = b0
    if ret:
        h0 = c_.numero("h₀ (mm)", "h0", B0.h, c[1], minimo=1.0, sufixo=s)
    t0 = c_.numero("t₀ (mm)", "t0", B0.t, c[2], minimo=0.5, passo=0.1, sufixo=s)
    N0 = c_.numero("N₀ (kN)", "N0", P.N0, c[3], minimo=None, passo=10.0)
    M0 = c_.numero("M₀ (kN·m)", "M0", P.M0, c[4], minimo=None, passo=1.0)

with st.container(border=True), secao_protegida("3. Diagonais"):
    c_.titulo("3. Diagonais", "sec_diagonais")
    c = st.columns(5)
    b1 = c_.numero("b₁ ou d₁ (mm)", "b1", B1.b, c[0], minimo=1.0, sufixo=s)
    h1 = b1
    if ret:
        h1 = c_.numero("h₁ (mm)", "h1", B1.h, c[1], minimo=1.0, sufixo=s)
    t1 = c_.numero("t₁ (mm)", "t1", B1.t, c[2], minimo=0.5, passo=0.1, sufixo=s)
    th1 = c_.numero("θ₁ (°)", "theta1", P.theta1, c[3], minimo=1.0, maximo=90.0, passo=5.0)
    N1 = c_.numero("N₁ (kN)", "N1", P.N1, c[4], minimo=None, passo=10.0)
    b2, h2, t2, th2, N2, g = b1, h1, t1, P.theta2, P.N2, G0
    if tipo == nt.NO_K:
        c = st.columns(6)
        b2 = c_.numero("b₂ ou d₂ (mm)", "b2", B1.b, c[0], minimo=1.0, sufixo=s)
        if ret:
            h2 = c_.numero("h₂ (mm)", "h2", B1.h, c[1], minimo=1.0, sufixo=s)
        else:
            h2 = b2
        t2 = c_.numero("t₂ (mm)", "t2", B1.t, c[2], minimo=0.5, passo=0.1, sufixo=s)
        th2 = c_.numero("θ₂ (°)", "theta2", P.theta2, c[3], minimo=1.0, maximo=90.0, passo=5.0)
        N2 = c_.numero("N₂ (kN)", "N2", P.N2, c[4], minimo=None, passo=10.0)
        g = c_.numero("Afastamento g (mm)", "g", G0, c[5], minimo=0.0, sufixo=s)
    gama = c_.numero("γa1", "gama", P.gama, minimo=1.0, maximo=2.0, passo=0.05, formato="%.2f")

entrada = nt.EntradaNo(
    forma=forma, tipo=tipo, banzo=nt.Tubo(b0, h0, t0), diagonal1=nt.Tubo(b1, h1, t1),
    diagonal2=nt.Tubo(b2, h2, t2), theta1=th1, theta2=th2, N1=N1, N2=N2, g=g, N0=N0, M0=M0,
    aco_banzo=aco0, aco_diagonais=acoi, gama=gama,
)  # fmt: skip
erros = nt.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = nt.calcular(entrada)
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    nt.registro(r),
    prefixo="nt_",
    arquivo="memorial_no_tubular",
    rotulo_registrar="Registrar o nó no projeto ativo",
)
