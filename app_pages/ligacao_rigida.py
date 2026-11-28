"""Ligação rígida viga–pilar com chapa de extremidade estendida (4E)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from components import robot_esforcos_ui as robot_ui
from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.ligacao_rigida_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.rigida_4es_ui import mostrar as mostrar_4es
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import desenho_ligacao_rigida as desenho
from core import ligacao_rigida as lr
from core import perfil_i as pi

configurar_pagina("Ligação rígida viga–pilar", ":material/join_inner:")
cabecalho_pagina(
    "Ligação rígida viga–pilar",
    "Chapa de extremidade estendida • 4E e estudo preliminar do enrijecedor 4ES • "
    "ABNT NBR 8800:2025 • AISC 358",
    categoria="Dimensionamento",
    icone=":material/join_inner:",
    cor="blue",
    ajuda_modulo="Ligação rígida viga–pilar",
    modulo_id=lr.MODULO_ID,
)
tipo = st.selectbox(
    "Configuração da ligação",
    ("4E — sem enrijecedor da chapa", "4ES — enrijecedor (estudo preliminar)"),
    key="lr_configuracao",
    help="A 4E é o cálculo existente. A 4ES reúne verificações preliminares da chapa, dos parafusos, do pilar e do enrijecedor; ainda não dimensiona a ligação completa.",
)
if tipo.startswith("4ES"):
    mostrar_4es()
    st.stop()

st.caption(
    "Verifica a ligação de momento parafusada mais comum dos pórticos: a viga soldada a uma "
    "chapa que avança além da mesa tracionada, parafusada na mesa do pilar."
)

P = lr.EntradaRigida()
c_ = Campos("lr_", AJUDA)


def _perfil(
    lado: str, chave_familia: str, chave_perfil: str, padrao: lr.PerfilEscolhido, coluna: Any
) -> lr.PerfilEscolhido:
    with coluna:
        familia = c_.escolha(f"Família ({lado})", chave_familia, pi.FAMILIAS, padrao.familia)
        if familia == pi.FAMILIA_SOLDADO:
            c = st.columns(5)
            sufixo = "_" + lado
            return lr.PerfilEscolhido(
                familia,
                padrao.nome,
                c_.numero("d (mm)", "d", padrao.d, c[0], minimo=1.0, sufixo=sufixo),
                c_.numero("b_f (mm)", "bf", padrao.bf, c[1], minimo=1.0, sufixo=sufixo),
                c_.numero("t_f (mm)", "tf", padrao.tf, c[2], minimo=0.5, passo=0.5, sufixo=sufixo),
                c_.numero("t_w (mm)", "tw", padrao.tw, c[3], minimo=0.5, passo=0.5, sufixo=sufixo),
                c_.numero("Filete (mm)", "filete", padrao.filete, c[4], passo=0.5, sufixo=sufixo),
            )
        lista = pi.nomes(familia)
        nome = c_.escolha(f"Perfil ({lado})", chave_perfil, lista,
                          padrao.nome if padrao.nome in lista else lista[0],
                          sufixo="_" + familia[:1])  # fmt: skip
        return lr.PerfilEscolhido(familia, nome)


with st.container(border=True), secao_protegida("1. Perfis e aços"):
    c_.titulo("1. Viga, pilar e aços", "sec_perfis")
    lados = st.columns(2)
    viga = _perfil("viga", "familia_viga", "perfil_viga", P.viga, lados[0])
    pilar = _perfil("pilar", "familia_pilar", "perfil_pilar", P.pilar, lados[1])
    c = st.columns(5)
    aco_v = c_.escolha("Aço da viga", "aco_viga", list(pi.ACOS), P.aco_viga, c[0])
    aco_c = c_.escolha("Aço do pilar", "aco_pilar", list(pi.ACOS), P.aco_pilar, c[1])
    aco_p = c_.escolha("Aço da chapa", "aco_chapa", list(pi.ACOS), P.aco_chapa, c[2])
    g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[3], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    g2 = c_.numero("γa2", "gama_a2", P.gama_a2, c[4], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("2. Esforços"):
    c_.titulo("2. Esforços de cálculo", "sec_esforcos")
    robot_ui.ligacao("lr_robot", {"lr_M": "m", "lr_V": "v"})
    c = st.columns(4)
    M = c_.numero("M (kN·m)", "M", P.M, c[0], minimo=0.1, passo=5.0)
    V = c_.numero("V (kN)", "V", P.V, c[1], passo=5.0)
    Np = c_.numero("N no pilar (kN)", "N_pilar", P.N_pilar, c[2], minimo=None, passo=10.0)
    Vp = c_.numero("V no pilar (kN)", "V_pilar", P.V_pilar, c[3], minimo=None, passo=5.0)
    c = st.columns(3)
    outro = c_.chave("Viga do outro lado", "outro_lado", P.outro_lado, c[0])
    M2 = P.M2
    if outro:
        M2 = c_.numero("M₂ (kN·m)", "M2", P.M2, c[1], minimo=None, passo=5.0)
    topo = c_.chave("Ligação no topo do pilar", "topo_do_pilar", P.topo_do_pilar, c[2])

with st.container(border=True), secao_protegida("3. Parafusos e chapa"):
    c_.titulo("3. Parafusos e chapa de extremidade", "sec_parafusos")
    c = st.columns(4)
    diam = c_.escolha("Diâmetro", "diametro", lr.DIAMETROS, P.diametro, c[0])
    grau = c_.escolha("Grau", "grau", lr.GRAUS, P.grau, c[1])
    rosca = c_.chave("Rosca no plano de corte", "rosca_no_plano", P.rosca_no_plano, c[2])
    sim = c_.chave("Chapa estendida dos dois lados", "simetrica", P.simetrica, c[3])
    c = st.columns(4)
    bp = c_.numero("Largura b_p (mm)", "bp", P.bp, c[0], minimo=1.0)
    tp = c_.numero("Espessura t_p (mm)", "tp", P.tp, c[1], minimo=1.0, passo=0.5)
    g = c_.numero("Gabarito g (mm)", "g", P.g, c[2], minimo=1.0)
    nc = c_.inteiro("Parafusos do lado comprimido", "parafusos_comprimidos",
                    P.parafusos_comprimidos, c[3], minimo=2, maximo=8)  # fmt: skip
    c = st.columns(3)
    pfo = c_.numero("p_fo (mm)", "pfo", P.pfo, c[0], minimo=1.0)
    pfi = c_.numero("p_fi (mm)", "pfi", P.pfi, c[1], minimo=1.0)
    de = c_.numero("Borda da chapa (mm)", "de", P.de, c[2], minimo=1.0)

with st.container(border=True), secao_protegida("4. Soldas"):
    c_.titulo("4. Soldas da viga na chapa", "sec_soldas")
    c = st.columns(4)
    solda = c_.escolha("Solda das mesas", "solda_mesa", lr.SOLDAS_DA_MESA, P.solda_mesa, c[0])
    perna_m = P.perna_mesa
    if solda == lr.FILETE:
        perna_m = c_.numero("Filete das mesas (mm)", "perna_mesa", P.perna_mesa, c[1], minimo=1.0,
                            passo=0.5)  # fmt: skip
    perna_a = c_.numero("Filete da alma (mm)", "perna_alma", P.perna_alma, c[2], minimo=1.0,
                        passo=0.5)  # fmt: skip
    eletrodo = c_.escolha("Eletrodo", "eletrodo", list(lr.ELETRODOS), P.eletrodo, c[3])

with st.container(border=True), secao_protegida("5. Reforços do pilar"):
    c_.titulo("5. Reforços do pilar", "sec_reforcos")
    c = st.columns(2)
    enr = c_.chave("Enrijecedores de continuidade", "enrijecedores", P.enrijecedores, c[0])
    ts, bs, corte = P.ts, P.bs, P.corte
    reforco_coluna = c[1]
    if enr:
        c = st.columns(3)
        ts = c_.numero("t_s (mm)", "ts", P.ts, c[0], minimo=1.0, passo=0.5)
        bs = c_.numero("b_s (mm)", "bs", P.bs, c[1], minimo=1.0)
        corte = c_.numero("Recorte (mm)", "corte", P.corte, c[2])
    reforco = c_.numero("Chapa de reforço da alma (mm)", "reforco_alma", P.reforco_alma, reforco_coluna,
                        passo=0.5)  # fmt: skip

entrada = lr.EntradaRigida(
    viga=viga, pilar=pilar, aco_viga=aco_v, aco_pilar=aco_c, aco_chapa=aco_p, gama_a1=g1,
    gama_a2=g2, M=M, V=V, N_pilar=Np, V_pilar=Vp, outro_lado=outro, M2=M2, topo_do_pilar=topo,
    diametro=diam, grau=grau, rosca_no_plano=rosca, bp=bp, tp=tp, g=g, pfo=pfo, pfi=pfi, de=de,
    simetrica=sim, parafusos_comprimidos=nc, solda_mesa=solda, perna_mesa=perna_m,
    perna_alma=perna_a, eletrodo=eletrodo, enrijecedores=enr, ts=ts, bs=bs, corte=corte,
    reforco_alma=reforco,
)  # fmt: skip
erros = lr.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = lr.calcular(entrada)
with st.container(border=True):
    st.subheader(
        "Detalhe da chapa",
        help="Vista frontal proporcional da chapa e das quatro posições dos parafusos tracionados do modelo 4E.",
    )
    mostrar_figura(svg_da_cena(desenho.vista_chapa(entrada)))
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    robot_ui.registro("lr_robot", lr.registro(r), {"lr_M": M, "lr_V": V}),
    prefixo="lr_",
    arquivo="memorial_ligacao_rigida",
    rotulo_registrar="Registrar a ligação no projeto ativo",
)
