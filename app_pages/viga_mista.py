"""Viga mista de aço e concreto biapoiada com conectores tipo pino com cabeça."""

from __future__ import annotations

import streamlit as st

from components.croquis_de_referencia import mostrar_croqui_de_referencia
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.viga_mista_help import AJUDA
from core import perfil_i as pi
from core import viga_mista as vmx

configurar_pagina("Viga mista", ":material/layers:")
cabecalho_pagina(
    "Viga mista",
    "Perfil de aço + laje de concreto com conectores (stud) • interação completa ou parcial, "
    "construção escorada ou não, flecha • ABNT NBR 8800:2025, Anexo L",
    categoria="Dimensionamento",
    icone=":material/layers:",
    cor="blue",
    ajuda_modulo="Viga mista",
    modulo_id=vmx.MODULO_ID,
)
st.caption(
    "Para mezanino ou piso com laje de concreto: a laje passa a trabalhar junto com a viga e "
    "o perfil pode ser bem mais leve que sozinho."
)
mostrar_croqui_de_referencia("viga_mista")

P = vmx.EntradaMista()
c_ = Campos("vmx_", AJUDA)

with st.container(border=True), secao_protegida("1. Perfil"):
    c_.titulo("1. Perfil de aço", "sec_perfil")
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
    c = st.columns(3)
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[0])
    g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    L = c_.numero("Vão L (mm)", "L", P.L, c[2], minimo=1.0, passo=100.0, formato="%.0f")

with st.container(border=True), secao_protegida("2. Laje"):
    c_.titulo("2. Laje de concreto", "sec_laje")
    c = st.columns(4)
    s_e = c_.numero("Viga vizinha à esquerda (mm)", "s_esquerda", P.s_esquerda, c[0], passo=100.0,
                    formato="%.0f")  # fmt: skip
    s_d = c_.numero("Viga vizinha à direita (mm)", "s_direita", P.s_direita, c[1], passo=100.0,
                    formato="%.0f")  # fmt: skip
    b_e, b_d = P.balanco_esquerda, P.balanco_direita
    if s_e == 0:
        b_e = c_.numero("Eixo → borda esquerda (mm)", "balanco_esquerda", 300.0, c[2], passo=50.0,
                        formato="%.0f")  # fmt: skip
    if s_d == 0:
        b_d = c_.numero("Eixo → borda direita (mm)", "balanco_direita", 300.0, c[3], passo=50.0,
                        formato="%.0f")  # fmt: skip
    c = st.columns(4)
    tc = c_.numero("Concreto t_c (mm)", "tc", P.tc, c[0], minimo=1.0, passo=5.0, formato="%.0f")
    hF = c_.numero("Fôrma h_F (mm)", "hF", P.hF, c[1], passo=5.0, formato="%.0f")
    fck = c_.numero("f_ck (MPa)", "fck", P.fck, c[2], minimo=20.0, maximo=50.0, passo=5.0,
                    formato="%.0f")  # fmt: skip
    brita = c_.escolha("Brita", "brita", list(vmx.BRITAS), P.brita, c[3])

with st.container(border=True), secao_protegida("3. Conectores"):
    c_.titulo("3. Conectores", "sec_conectores")
    c = st.columns(5)
    dc = c_.numero("Diâmetro (mm)", "diametro_conector", P.diametro_conector, c[0], minimo=1.0,
                   passo=1.0)  # fmt: skip
    fuc = c_.numero("f_u (MPa)", "fu_conector", P.fu_conector, c[1], minimo=1.0, passo=5.0,
                    formato="%.0f")  # fmt: skip
    posicao = c_.escolha("Posição", "posicao", list(vmx.POSICOES), P.posicao, c[2])
    n = c_.inteiro("Do apoio ao meio do vão", "conectores", P.conectores, c[3], maximo=500)
    nl = c_.inteiro("Por linha", "por_linha", P.por_linha, c[4], maximo=4)

with st.container(border=True), secao_protegida("4. Cargas"):
    c_.titulo("4. Cargas características (kN/m)", "sec_cargas")
    c = st.columns(4)
    g1k = c_.numero("g₁ antes da cura", "g1", P.g1, c[0], passo=0.5, formato="%.2f")
    qc = c_.numero("q de construção", "q_construcao", P.q_construcao, c[1], passo=0.5,
                   formato="%.2f")  # fmt: skip
    g2k = c_.numero("g₂ depois da cura", "g2", P.g2, c[2], passo=0.5, formato="%.2f")
    qk = c_.numero("q de uso", "q", P.q, c[3], passo=0.5, formato="%.2f")
    c = st.columns(3)
    gg = c_.numero("γg", "gama_g", P.gama_g, c[0], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    gq = c_.numero("γq", "gama_q", P.gama_q, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    gc = c_.numero("γ construção", "gama_construcao", P.gama_construcao, c[2], minimo=1.0,
                   maximo=2.0, passo=0.05, formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("5. Construção e flecha"):
    c_.titulo("5. Construção e flecha", "sec_construcao")
    c = st.columns(4)
    escorada = c_.chave("Construção escorada", "escorada", P.escorada, c[0])
    Lb = P.Lb_construcao
    if not escorada:
        Lb = c_.numero("L_b na concretagem (mm)", "Lb_construcao", P.Lb_construcao, c[1],
                       passo=100.0, formato="%.0f")  # fmt: skip
    lim = c_.numero("Flecha L/…", "flecha_limite", P.flecha_limite, c[2], minimo=1.0, passo=50.0,
                    formato="%.0f")  # fmt: skip
    cf = c_.numero("Contraflecha (mm)", "contraflecha", P.contraflecha, c[3], passo=1.0)

entrada = vmx.EntradaMista(
    familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, aco=aco, gama_a1=g1, L=L,
    s_esquerda=s_e, s_direita=s_d, balanco_esquerda=b_e, balanco_direita=b_d, tc=tc, hF=hF,
    fck=fck, brita=brita, diametro_conector=dc, fu_conector=fuc, posicao=posicao, conectores=n,
    por_linha=nl, g1=g1k, q_construcao=qc, g2=g2k, q=qk, gama_g=gg, gama_q=gq,
    gama_construcao=gc, escorada=escorada, Lb_construcao=Lb, flecha_limite=lim, contraflecha=cf,
)  # fmt: skip
erros = vmx.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = vmx.calcular(entrada)
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    vmx.registro(r),
    prefixo="vmx_",
    arquivo="memorial_viga_mista",
    rotulo_registrar="Registrar a viga mista no projeto ativo",
)
