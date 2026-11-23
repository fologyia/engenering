"""Fadiga da estrutura pela categoria do detalhe (NBR 8800:2025, Anexo H)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.fadiga_estrutural_help import AJUDA
from components.pagina_padrao import Campos, memorial_e_registro, mostrar_resultado
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import fadiga_estrutural as fe
from core import perfil_i as pi

configurar_pagina("Fadiga da estrutura", ":material/cyclone:")
cabecalho_pagina(
    "Fadiga da estrutura",
    "Faixa de variação de tensões por categoria de detalhe (A a G, C' e C'') • suportes de "
    "talhas, peneiras, britadores e transportadores • ABNT NBR 8800:2025, Anexo H",
    categoria="Dimensionamento",
    icone=":material/cyclone:",
    cor="blue",
    ajuda_modulo="Fadiga da estrutura",
    modulo_id=fe.MODULO_ID,
)
st.caption(
    "Para estruturas de aço sob carga repetida: compara a variação de tensão em cada detalhe "
    "(solda, furo, recorte, parafuso) com a faixa admissível da categoria dele."
)
P = fe.EntradaFadiga()
c_ = Campos("fe_", AJUDA)

with st.container(border=True), secao_protegida("1. Ciclos"):
    c_.titulo("1. Número de ciclos", "sec_ciclos")
    c = st.columns(5)
    aco = c_.escolha("Aço", "aco", list(pi.ACOS), P.aco, c[0])
    por_dia = c_.numero("Ciclos por dia", "ciclos_por_dia", P.ciclos_por_dia, c[1], passo=10.0,
                        formato="%.0f")  # fmt: skip
    dias = c_.numero("Dias por ano", "dias_por_ano", P.dias_por_ano, c[2], maximo=366.0,
                     passo=10.0, formato="%.0f")  # fmt: skip
    anos = c_.numero("Vida útil (anos)", "anos", P.anos, c[3], maximo=200.0, passo=5.0,
                     formato="%.0f")  # fmt: skip
    informados = c_.numero("Ou N total", "ciclos_informados", P.ciclos_informados, c[4],
                           maximo=1e12, passo=1e5, formato="%.0f")  # fmt: skip

with st.container(border=True), secao_protegida("2. Detalhes"):
    c_.titulo("2. Detalhes e tensões", "sec_detalhes")
    tabela = st.data_editor(
        pd.DataFrame(fe.tabela_dos_detalhes(P.detalhes)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="fe_detalhes",
        column_config={
            "Detalhe": st.column_config.TextColumn(help=AJUDA["tabela_detalhes"]),
            "Caso da Tabela H.1": st.column_config.SelectboxColumn(
                options=list(fe.ROTULOS), default=fe.ROTULOS[0], width="large",
                help=AJUDA["tabela_detalhes"],
            ),
            "σ máx (MPa)": st.column_config.NumberColumn(default=0.0, help=AJUDA["tabela_detalhes"]),
            "σ mín (MPa)": st.column_config.NumberColumn(default=0.0, help=AJUDA["tabela_detalhes"]),
            "t_p (mm)": st.column_config.NumberColumn(min_value=0.0, default=16.0,
                                                      help=AJUDA["tabela_detalhes"]),
            "2a (mm)": st.column_config.NumberColumn(min_value=0.0, default=0.0,
                                                     help=AJUDA["tabela_detalhes"]),
            "w (mm)": st.column_config.NumberColumn(min_value=0.0, default=0.0,
                                                    help=AJUDA["tabela_detalhes"]),
        },
    )  # fmt: skip
    detalhes = fe.detalhes_de_tabela(tabela.to_dict("records"))

entrada = fe.EntradaFadiga(aco=aco, ciclos_por_dia=por_dia, dias_por_ano=dias, anos=anos,
                           ciclos_informados=informados, detalhes=detalhes)  # fmt: skip
erros = fe.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
st.metric("Ciclos na vida útil N", f"{entrada.N:,.0f}".replace(",", "."), help=AJUDA["res_ciclos"])
r = fe.calcular(entrada)
mostrar_resultado(r.grupos, avisos=r.avisos)
memorial_e_registro(
    fe.registro(r),
    prefixo="fe_",
    arquivo="memorial_fadiga_da_estrutura",
    rotulo_registrar="Registrar a fadiga no projeto ativo",
)
