"""Forças localizadas na alma de perfis I e H e os enrijecedores (NBR 8800:2025, 5.7)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.forcas_localizadas_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import desenho_forcas_localizadas as desenho
from core import forcas_localizadas as fl
from core import perfil_i as pi

configurar_pagina("Forças localizadas na alma", ":material/vertical_align_bottom:")
cabecalho_pagina(
    "Forças localizadas na alma",
    "Reações de apoio, pés de equipamento e vigas que apoiam na mesa • flexão local da mesa, "
    "escoamento, enrugamento e flambagem da alma • enrijecedores • ABNT NBR 8800:2025, 5.7",
    categoria="Dimensionamento",
    icone=":material/vertical_align_bottom:",
    cor="blue",
    ajuda_modulo="Forças localizadas na alma",
    modulo_id=fl.MODULO_ID,
)
st.caption(
    "Verifica a mesa e a alma do perfil I ou H onde uma força concentrada entra — a verificação "
    "que a flexão e o cortante da viga não pegam — e, quando preciso, os enrijecedores."
)

P = fl.EntradaForcas()
S = P.enrijecedor
c_ = Campos("fl_", AJUDA)

with st.container(border=True), secao_protegida("1. Perfil e aço"):
    c_.titulo("1. Perfil e aço", "sec_perfil")
    familia = c_.escolha("Perfil", "familia", pi.FAMILIAS, P.familia, horizontal=True)
    d, bf, tf, tw, filete = P.d, P.bf, P.tf, P.tw, P.filete
    perfil = P.perfil
    if familia == pi.FAMILIA_SOLDADO:
        c = st.columns(5)
        d = c_.numero("d (mm)", "d", P.d, c[0], minimo=1.0)
        bf = c_.numero("b_f (mm)", "bf", P.bf, c[1], minimo=1.0)
        tf = c_.numero("t_f (mm)", "tf", P.tf, c[2], minimo=0.5, passo=0.5)
        tw = c_.numero("t_w (mm)", "tw", P.tw, c[3], minimo=0.5, passo=0.5)
        filete = c_.numero("Filete mesa–alma (mm)", "filete", P.filete, c[4], passo=0.5)
    else:
        lista = pi.nomes(familia)
        padrao = P.perfil if P.perfil in lista else lista[0]
        perfil = c_.escolha("Bitola", "perfil", lista, padrao, sufixo="_" + familia[:1])
    c = st.columns(3)
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[0])
    g1 = c_.numero("γa1", "gama_a1", P.gama_a1, c[1], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip
    g2 = c_.numero("γa2", "gama_a2", P.gama_a2, c[2], minimo=1.0, maximo=2.0, passo=0.05,
                   formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("2. Forças"):
    c_.titulo("2. Forças na mesa", "sec_forcas")
    tabela = st.data_editor(
        pd.DataFrame(fl.tabela_das_forcas(P.forcas)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="fl_forcas",
        column_config={
            "Força": st.column_config.TextColumn(help=AJUDA["tabela_forcas"]),
            "F_Sd (kN)": st.column_config.NumberColumn(min_value=0.0, default=0.0,
                                                       help=AJUDA["tabela_forcas"]),
            "Tipo": st.column_config.SelectboxColumn(options=list(fl.TIPOS), default=fl.COMPRESSAO,
                                                     help=AJUDA["tabela_forcas"], width="medium"),
            "ℓn (mm)": st.column_config.NumberColumn(min_value=0.0, default=100.0,
                                                     help=AJUDA["tabela_forcas"]),
            "Largura (mm)": st.column_config.NumberColumn(min_value=0.0, default=100.0,
                                                          help=AJUDA["tabela_forcas"]),
            "Dist. à ponta (mm)": st.column_config.NumberColumn(min_value=0.0, default=0.0,
                                                                help=AJUDA["tabela_forcas"]),
            "Mesa comprimida": st.column_config.CheckboxColumn(default=False,
                                                               help=AJUDA["tabela_forcas"]),
            "M_Sd (kN·m)": st.column_config.NumberColumn(default=0.0, help=AJUDA["tabela_forcas"]),
        },
    )  # fmt: skip
    forcas = fl.forcas_de_tabela(tabela.to_dict("records"))
    c = st.columns(4)
    ell = c_.numero("ℓ destravado (mm)", "comprimento_destravado", P.comprimento_destravado, c[0],
                    minimo=1.0, passo=100.0, formato="%.0f")  # fmt: skip
    rot = c_.chave("Rotação da mesa carregada impedida", "rotacao_impedida", P.rotacao_impedida,
                   c[1])  # fmt: skip
    desl = c_.chave("Deslocamento lateral entre mesas impedido", "deslocamento_lateral_impedido",
                    P.deslocamento_lateral_impedido, c[2])  # fmt: skip
    livre = c_.chave("Apoio sem restrição à rotação (alma livre)", "extremidade_livre",
                     P.extremidade_livre, c[3])  # fmt: skip

with st.container(border=True), secao_protegida("3. Enrijecedores"):
    c_.titulo("3. Enrijecedores", "sec_enrijecedor")
    usar = c_.chave("Verificar enrijecedores", "usar_enrijecedor", P.usar_enrijecedor)
    enr = S
    if usar:
        c = st.columns(4)
        bs = c_.numero("Largura b_s (mm)", "bs", S.bs, c[0], minimo=1.0)
        ts = c_.numero("Espessura t_s (mm)", "ts", S.ts, c[1], minimo=0.5, passo=0.5)
        corte = c_.numero("Recorte (mm)", "corte", S.corte, c[2], passo=1.0)
        aco_s = c_.escolha("Aço", "aco_enrijecedor", list(pi.ACOS), S.aco, c[3])
        c = st.columns(4)
        dois = c_.chave("Dos dois lados da alma", "dois_lados", S.dois_lados, c[0])
        ajust = c_.chave("Ponta ajustada (contato)", "ajustado", S.ajustado, c[1])
        total = c_.chave("Toda a altura da alma", "altura_total", S.altura_total, c[2])
        posicao = c_.escolha("Posição", "posicao", fl.POSICOES, S.posicao, c[3])
        c = st.columns(3)
        perna_a = c_.numero("Filete na alma (mm)", "perna_alma", S.perna_alma, c[0], minimo=1.0,
                            passo=0.5)  # fmt: skip
        perna_m = c_.numero("Filete na mesa (mm)", "perna_mesa", S.perna_mesa, c[1], minimo=1.0,
                            passo=0.5)  # fmt: skip
        eletrodo = c_.escolha("Eletrodo", "eletrodo", list(fl.ELETRODOS), S.eletrodo, c[2])
        enr = fl.Enrijecedor(bs, ts, dois, posicao, corte, ajust, aco_s, perna_a, perna_m,
                             eletrodo, total)  # fmt: skip

entrada = fl.EntradaForcas(
    familia=familia, perfil=perfil, d=d, bf=bf, tf=tf, tw=tw, filete=filete, aco=aco,
    gama_a1=g1, gama_a2=g2, forcas=forcas, comprimento_destravado=ell, rotacao_impedida=rot,
    deslocamento_lateral_impedido=desl, extremidade_livre=livre, usar_enrijecedor=usar,
    enrijecedor=enr,
)  # fmt: skip
erros = fl.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = fl.calcular(entrada)
with st.container(border=True):
    st.subheader(
        "Detalhes das forças",
        help="Vista local de cada força e do enrijecedor, quando sua geometria está definida.",
    )
    for forca in entrada.forcas:
        mostrar_figura(svg_da_cena(desenho.detalhe(entrada, forca)))
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    fl.registro(r),
    prefixo="fl_",
    arquivo="memorial_forcas_localizadas",
    rotulo_registrar="Registrar a verificação no projeto ativo",
)
