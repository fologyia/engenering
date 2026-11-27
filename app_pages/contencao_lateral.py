"""Contenção lateral (travamentos): força e rigidez mínimas pela NBR 8800:2025, 4.12."""

from __future__ import annotations

import streamlit as st

from components.contencao_lateral_help import AJUDA
from components.croquis_de_referencia import mostrar_croqui_de_referencia
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import contencao_lateral as cl
from core import perfil_i as pi

configurar_pagina("Contenção lateral (travamentos)", ":material/fence:")
cabecalho_pagina(
    "Contenção lateral (travamentos)",
    "Força e rigidez mínimas do travamento de pilares e vigas: translação e torção • "
    "ABNT NBR 8800:2025, 4.12",
    categoria="Dimensionamento",
    icone=":material/fence:",
    cor="blue",
    ajuda_modulo="Contenção lateral (travamentos)",
    modulo_id=cl.MODULO_ID,
)
st.caption(
    "Confere se o travamento que reduz o comprimento destravado de um pilar ou de uma viga tem a "
    "força e a rigidez que a norma exige — senão o comprimento destravado adotado não vale."
)
mostrar_croqui_de_referencia("contencao_lateral")

P = cl.EntradaContencao()
c_ = Campos("cl_", AJUDA)

with st.container(border=True), secao_protegida("1. Caso"):
    c_.titulo("1. O que é travado", "sec_caso")
    caso = c_.escolha("Tipo de contenção", "caso", cl.CASOS, P.caso)
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

pilar = caso == cl.PILAR
torcao = caso in (cl.VIGA_TORCAO, cl.VIGA_TORCAO_CONTINUA)
with st.container(border=True), secao_protegida("2. Esforço"):
    c_.titulo("2. Esforço e espaçamento", "sec_esforco")
    c = st.columns(4)
    N, M = P.N_Sd, P.M_Sd
    if pilar:
        N = c_.numero("N_Sd (kN)", "N_Sd", P.N_Sd, c[0], minimo=0.1, passo=10.0)
    else:
        M = c_.numero("M_Sd (kN·m)", "M_Sd", P.M_Sd, c[0], minimo=0.1, passo=5.0)
    barras = c_.inteiro("Barras travadas em série", "barras", P.barras, c[1], maximo=50)
    L_b = c_.numero("Distância entre contenções (mm)", "L_b", P.L_b, c[2], minimo=1.0,
                    passo=100.0, formato="%.0f")  # fmt: skip
    L_q = c_.numero("L_q (mm, opcional)", "L_q", P.L_q, c[3], passo=100.0, formato="%.0f")
    c = st.columns(4)
    n, curv, L_vao, Cb = P.n, P.curvatura_reversa, P.L_vao, P.Cb
    t_st, b_st, par = P.t_st, P.b_st, P.par_de_enrijecedores
    if caso != cl.VIGA_TORCAO_CONTINUA and caso != cl.VIGA_TRANSLACAO:
        n = c_.inteiro("Número de contenções", "n", P.n, c[0], maximo=50)
    if caso == cl.VIGA_TRANSLACAO:
        curv = c_.chave("Perto do ponto de inflexão", "curvatura_reversa", P.curvatura_reversa,
                        c[0])  # fmt: skip
    if torcao:
        L_vao = c_.numero("Vão da viga (mm)", "L_vao", P.L_vao, c[1], minimo=1.0, passo=100.0,
                          formato="%.0f")  # fmt: skip
        Cb = c_.numero("C_b", "Cb", P.Cb, c[2], minimo=1.0, maximo=3.0, passo=0.05,
                       formato="%.2f")  # fmt: skip
    if caso == cl.VIGA_TORCAO:
        c = st.columns(3)
        t_st = c_.numero("Enrijecedor t_st (mm)", "t_st", P.t_st, c[0], passo=0.5)
        b_st = c_.numero("Enrijecedor b_st (mm)", "b_st", P.b_st, c[1], passo=5.0)
        par = c_.chave("Par de enrijecedores", "par_de_enrijecedores", P.par_de_enrijecedores,
                       c[2])  # fmt: skip

trabalho, A_br, r_br, L_br, ang, aco_br, k_lig = (P.trabalho, P.A_br, P.r_br, P.L_br, P.angulo,
                                                  P.aco_br, P.k_ligacao)  # fmt: skip
beta_tipo, beta, I_t, S_t, M_lig = (P.beta_tipo, P.beta, P.I_transversal, P.S_transversal,
                                    P.M_Rd_ligacao)  # fmt: skip
g1 = P.gama_a1
if not torcao:
    with st.container(border=True), secao_protegida("3. Barra de contenção"):
        c_.titulo("3. Barra de contenção", "sec_barra")
        c = st.columns(4)
        trabalho = c_.escolha("Trabalha a", "trabalho", cl.TRABALHOS, P.trabalho, c[0])
        aco_br = c_.escolha("Aço", "aco_br", list(pi.ACOS), P.aco_br, c[1])
        A_br = c_.numero("Área A (mm²)", "A_br", P.A_br, c[2], minimo=1.0, passo=10.0)
        r_br = c_.numero("Raio de giração r (mm)", "r_br", P.r_br, c[3], minimo=0.1, passo=0.5)
        c = st.columns(4)
        L_br = c_.numero("Comprimento L (mm)", "L_br", P.L_br, c[0], minimo=1.0, passo=100.0,
                         formato="%.0f")  # fmt: skip
        ang = c_.numero("Ângulo θ (°)", "angulo", P.angulo, c[1], maximo=89.0, passo=5.0)
        k_lig = c_.numero("Rigidez da ligação (kN/mm)", "k_ligacao", P.k_ligacao, c[2],
                          passo=1.0)  # fmt: skip
        g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[3], minimo=1.0, maximo=2.0, passo=0.05,
                       formato="%.2f")  # fmt: skip
else:
    with st.container(border=True), secao_protegida("3. Contenção de torção"):
        c_.titulo("3. Contenção de torção", "sec_torcao")
        c = st.columns(4)
        if caso == cl.VIGA_TORCAO:
            beta_tipo = c_.escolha("Rigidez β", "beta_tipo", cl.BETAS, P.beta_tipo, c[0])
        if caso == cl.VIGA_TORCAO_CONTINUA or beta_tipo == cl.BETA_INFORMADO:
            beta = c_.numero("β (kN·m/rad)", "beta", P.beta, c[1], minimo=0.001, passo=50.0)
        else:
            I_t = c_.numero("I da transversal (mm⁴)", "I_transversal", P.I_transversal, c[1],
                            minimo=1.0, passo=1e6, formato="%.0f")  # fmt: skip
            S_t = c_.numero("Vão da transversal (mm)", "S_transversal", P.S_transversal, c[2],
                            minimo=1.0, passo=100.0, formato="%.0f")  # fmt: skip
        M_lig = c_.numero("M_Rd da ligação (kN·m)", "M_Rd_ligacao", P.M_Rd_ligacao, c[3],
                          passo=1.0)  # fmt: skip

entrada = cl.EntradaContencao(
    caso=caso, familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, N_Sd=N, M_Sd=M,
    barras=barras, L_b=L_b, L_q=L_q, n=n, curvatura_reversa=curv, L_vao=L_vao, Cb=Cb, t_st=t_st,
    b_st=b_st, par_de_enrijecedores=par, trabalho=trabalho, A_br=A_br, r_br=r_br, L_br=L_br,
    angulo=ang, aco_br=aco_br, k_ligacao=k_lig, beta_tipo=beta_tipo, beta=beta, I_transversal=I_t,
    S_transversal=S_t, M_Rd_ligacao=M_lig, gama_a1=g1,
)  # fmt: skip
erros = cl.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = cl.calcular(entrada)
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    cl.registro(r),
    prefixo="cl_",
    arquivo="memorial_contencao_lateral",
    rotulo_registrar="Registrar a contenção no projeto ativo",
)
