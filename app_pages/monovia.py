"""Viga de monovia: talha correndo na mesa inferior de um perfil I."""

from __future__ import annotations

import streamlit as st

from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.monovia_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import desenho_monovia as desenho
from core import monovia as mo
from core import perfil_i as pi

configurar_pagina("Viga de monovia", ":material/conveyor_belt:")
cabecalho_pagina(
    "Viga de monovia",
    "Talha na mesa inferior • flexão vertical e lateral, cortante, mesa sob as rodas (EN 1993-6) "
    "e flechas • ABNT NBR 8800:2025 • Critério Anglo",
    categoria="Dimensionamento",
    icone=":material/conveyor_belt:",
    cor="blue",
    ajuda_modulo="Viga de monovia",
    modulo_id=mo.MODULO_ID,
)
st.caption(
    "Coloca a talha na posição mais desfavorável, soma o impacto e a força lateral e verifica a "
    "viga, a mesa de baixo onde as rodas correm e o apoio."
)

P = mo.EntradaMonovia()
c_ = Campos("mo_", AJUDA)

with st.container(border=True), secao_protegida("1. Perfil e aço"):
    c_.titulo("1. Perfil e aço", "sec_perfil")
    familia = c_.escolha("Perfil", "familia", pi.FAMILIAS, P.familia, horizontal=True)
    d, bf, tf, tw, filete, perfil = P.d, P.bf, P.tf, P.tw, P.filete, P.perfil
    if familia == pi.FAMILIA_SOLDADO:
        c = st.columns(5)
        d = c_.numero("d (mm)", "d", P.d, c[0], minimo=1.0)
        bf = c_.numero("b_f (mm)", "bf", P.bf, c[1], minimo=1.0)
        tf = c_.numero("t_f (mm)", "tf", P.tf, c[2], minimo=0.5, passo=0.5)
        tw = c_.numero("t_w (mm)", "tw", P.tw, c[3], minimo=0.5, passo=0.5)
        filete = c_.numero("Filete mesa–alma (mm)", "filete", P.filete, c[4], passo=0.5)
    else:
        lista = pi.nomes(familia)
        perfil = c_.escolha("Bitola", "perfil", lista, P.perfil if P.perfil in lista else lista[0],
                            sufixo="_" + familia[:1])  # fmt: skip
    c = st.columns(2)
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[0])
    g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("2. Viga"):
    c_.titulo("2. Viga", "sec_viga")
    c = st.columns(3)
    sistema = c_.escolha("Sistema", "sistema", mo.SISTEMAS, P.sistema, c[0])
    L = c_.numero("Vão ou balanço L (mm)", "L", P.L, c[1], minimo=1.0, passo=100.0, formato="%.0f")
    Lb = c_.numero("Destravado L_b (mm)", "Lb", P.Lb, c[2], minimo=1.0, passo=100.0,
                   formato="%.0f")  # fmt: skip

with st.container(border=True), secao_protegida("3. Talha"):
    c_.titulo("3. Talha", "sec_talha")
    c = st.columns(3)
    cap = c_.numero("Carga içada (kN)", "capacidade", P.capacidade, c[0], minimo=0.1)
    peso = c_.numero("Talha + trole (kN)", "peso_talha", P.peso_talha, c[1], passo=0.5)
    n_roda = c_.numero("Roda → borda da mesa n (mm)", "n_roda", P.n_roda, c[2], passo=1.0)
    c = st.columns(3)
    eixos = c_.inteiro("Eixos", "eixos", P.eixos, c[0], maximo=2)
    rodas = c_.inteiro("Rodas por eixo", "rodas_por_eixo", P.rodas_por_eixo, c[1], maximo=2)
    entre = c_.numero("Entre eixos (mm)", "entre_eixos", P.entre_eixos, c[2], passo=10.0,
                      formato="%.0f")  # fmt: skip

with st.container(border=True), secao_protegida("4. Impacto e coeficientes"):
    c_.titulo("4. Impacto, força lateral e coeficientes", "sec_cargas")
    c = st.columns(5)
    imp_c = c_.numero("Impacto na carga", "impacto_carga", P.impacto_carga, c[0], maximo=2.0,
                      passo=0.05, formato="%.2f")  # fmt: skip
    imp_m = c_.numero("Impacto na talha", "impacto_moveis", P.impacto_moveis, c[1], maximo=2.0,
                      passo=0.05, formato="%.2f")  # fmt: skip
    lat = c_.numero("Força lateral", "lateral", P.lateral, c[2], maximo=1.0, passo=0.05,
                    formato="%.2f")  # fmt: skip
    gg = c_.numero("γg", "gama_g", P.gama_g, c[3], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    gq = c_.numero("γq", "gama_q", P.gama_q, c[4], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("5. Limites"):
    c_.titulo("5. Flechas e ponta da viga", "sec_limites")
    c = st.columns(3)
    fv = c_.numero("Flecha vertical L/…", "flecha_vertical", P.flecha_vertical, c[0], minimo=1.0,
                   passo=50.0, formato="%.0f")  # fmt: skip
    fh = c_.numero("Flecha horizontal L/…", "flecha_horizontal", P.flecha_horizontal, c[1],
                   minimo=1.0, passo=50.0, formato="%.0f")  # fmt: skip
    ponta = c_.chave("Roda junto à ponta sem enrijecedor", "ponta_sem_enrijecedor",
                     P.ponta_sem_enrijecedor, c[2])  # fmt: skip

with st.container(border=True), secao_protegida("6. Apoio"):
    c_.titulo("6. Apoio da viga", "sec_apoio")
    c = st.columns(3)
    apoio = c_.escolha("Apoio", "apoio", mo.APOIOS, P.apoio, c[0])
    ln_ap = c_.numero("Comprimento de apoio (mm)", "ln_apoio", P.ln_apoio, c[1], passo=10.0,
                      formato="%.0f")  # fmt: skip
    larg = c_.numero("Largura de apoio (mm)", "largura_apoio", P.largura_apoio, c[2], passo=10.0,
                     formato="%.0f")  # fmt: skip

entrada = mo.EntradaMonovia(
    familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, filete=filete, aco=aco, gama_a1=g1,
    sistema=sistema, L=L, Lb=Lb, capacidade=cap, peso_talha=peso, rodas_por_eixo=rodas,
    eixos=eixos, entre_eixos=entre, n_roda=n_roda, impacto_carga=imp_c, impacto_moveis=imp_m,
    lateral=lat, gama_g=gg, gama_q=gq, ponta_sem_enrijecedor=ponta, flecha_vertical=fv,
    flecha_horizontal=fh, apoio=apoio, ln_apoio=ln_ap, largura_apoio=larg,
)  # fmt: skip
erros = mo.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = mo.calcular(entrada)
with st.container(border=True):
    st.subheader(
        "Seção e contato das rodas",
        help="Seção do perfil escolhido, com os pontos de contato informados na mesa inferior; o diâmetro das rodas não é modelado.",
    )
    mostrar_figura(svg_da_cena(desenho.secao(entrada)))

with st.container(border=True), secao_protegida("Esforços"):
    c_.titulo("Esforços de cálculo", "sec_esforcos")
    esf = r.esforcos
    c = st.columns(4)
    c[0].metric("M_Sd", f"{pi.numero(esf['M_Sd_kNm'], 2)} kN·m", help=AJUDA["res_momento"])
    c[1].metric("V_Sd", f"{pi.numero(esf['V_Sd_kN'], 2)} kN", help=AJUDA["res_cortante"])
    c[2].metric("Carga por roda", f"{pi.numero(esf['F_roda_calculo_kN'], 2)} kN",
                help=AJUDA["res_roda"])  # fmt: skip
    c[3].metric("Reação de serviço", f"{pi.numero(esf['R_servico_kN'], 2)} kN",
                help=AJUDA["res_reacao"])  # fmt: skip

mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    mo.registro(r),
    prefixo="mo_",
    arquivo="memorial_viga_de_monovia",
    rotulo_registrar="Registrar a monovia no projeto ativo",
)
