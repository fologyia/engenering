"""Emenda de pilar com talas parafusadas: uma tala em cada mesa e duas na alma."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components import emendas_do_modelo_ui as emu
from components.cena_3d_svg import svg_da_cena
from components.emenda_pilar_help import AJUDA
from components.figuras import mostrar_figura
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import COR_STATUS, mostrar_tabela_verificacoes
from core import desenho_emenda_pilar as de
from core import emenda_pilar as ep
from core.project_store import obter_projeto_ativo

configurar_pagina("Emenda de pilar", ":material/vertical_split:")
cabecalho_pagina(
    "Emenda de pilar",
    "Talas parafusadas: uma externa em cada mesa (corte simples) e duas na alma (corte duplo) • "
    "ABNT NBR 8800:2025 • Critério Anglo • AISC Manual Parte 14 • SCI P207",
    categoria="Dimensionamento",
    icone=":material/vertical_split:",
    cor="blue",
    ajuda_modulo="Emenda de pilar",
    modulo_id=ep.MODULO_ID,
)
st.caption(
    "Distribui N, M e V entre as mesas e a alma pelo modelo do SCI P207, acrescenta o esforço "
    "mínimo da NBR 6.1.6.2 e verifica parafusos, talas e pilar pelas resistências da NBR 8800, "
    "com o item da norma em cada linha."
)
P = ep.EntradaEmenda()
emu.aplicar_pendentes()  # o que veio do modelo ou da sugestão das talas


def _numero(rotulo: str, chave: str, padrao: float, ajuda: str, coluna: Any = st, *,
            minimo: float = 0.0, maximo: float = 1e6, passo: float = 1.0,
            formato: str = "%.1f") -> float:  # fmt: skip
    return float(
        coluna.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=float(padrao),
            step=passo,
            format=formato,
            key=chave,
            persist_state="session",
            help=AJUDA[ajuda],
        )  # fmt: skip
    )


def _inteiro(rotulo: str, chave: str, padrao: int, ajuda: str, coluna: Any = st) -> int:
    return int(
        coluna.number_input(
            rotulo,
            min_value=1,
            max_value=20,
            value=padrao,
            step=1,
            key=chave,
            persist_state="session",
            help=AJUDA[ajuda],
        )  # fmt: skip
    )


def _escolha(
    rotulo: str, chave: str, opcoes: Any, padrao: str, ajuda: str, coluna: Any = st
) -> str:
    opcoes = list(opcoes)
    return str(
        coluna.selectbox(
            rotulo,
            opcoes,
            index=opcoes.index(padrao),
            key=chave,
            persist_state="session",
            help=AJUDA[ajuda],
        )  # fmt: skip
    )


projeto_ativo = obter_projeto_ativo()
modelo = emu.ModeloDoProjeto(projeto_ativo)
with st.container(border=True), secao_protegida("Trazer do modelo"):
    emu.secao_trazer_do_modelo(modelo, P)
    emu.mostrar_notas_da_origem()

with st.container(border=True), secao_protegida("1. Perfis e materiais"):
    st.subheader("1. Perfis e materiais", help=AJUDA["sec_perfis"])
    familia = str(
        st.radio(
            "Família",
            ep.FAMILIAS,
            horizontal=True,
            key="emp_familia",
            persist_state="session",
            help=AJUDA["familia"],
        )  # fmt: skip
    )
    eh_u = familia == ep.FAMILIA_U
    # chaves por família: trocar de família não deixa um nome de outra lista na caixa
    lista = ep.perfis_da_familia(familia)
    padrao_perfil = ep.PERFIL_PADRAO_U if eh_u else P.perfil_superior
    sufixo = "_u" if eh_u else ""
    c = st.columns(4)
    perfil_s = _escolha("Pilar superior", "emp_perfil_s" + sufixo, lista, padrao_perfil,
                        "perfil_superior", c[0])  # fmt: skip
    perfil_i = _escolha("Pilar inferior", "emp_perfil_i" + sufixo, lista, padrao_perfil,
                        "perfil_inferior", c[1])  # fmt: skip
    aco_p = _escolha("Aço dos perfis", "emp_aco_p", ep.ACOS, P.aco_perfis, "aco_perfis", c[2])
    aco_t = _escolha("Aço das talas", "emp_aco_t", ep.ACOS, P.aco_talas, "aco_talas", c[3])
    c = st.columns(3)
    E = _numero("E (MPa)", "emp_E", P.E, "E", c[0], minimo=1.0, passo=1000.0, formato="%.0f")
    g1 = _numero("γa1", "emp_g1", P.gama_a1, "gama_a1", c[1], minimo=1.0, maximo=2.0, passo=0.05,
                 formato="%.2f")  # fmt: skip
    g2 = _numero("γa2", "emp_g2", P.gama_a2, "gama_a2", c[2], minimo=1.0, maximo=2.0, passo=0.05,
                 formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("2. Parafusos"):
    st.subheader("2. Parafusos", help=AJUDA["sec_parafusos"])
    c = st.columns(3)
    diametro = _escolha("Diâmetro", "emp_diam", ep.DIAMETROS, P.diametro, "diametro", c[0])
    grau = _escolha("Grau", "emp_grau", ep.GRAUS, P.grau, "grau", c[1])
    rosca = c[2].toggle("Rosca no plano de corte", value=P.rosca_no_plano, key="emp_rosca",
                        persist_state="session", help=AJUDA["rosca"])  # fmt: skip
    c = st.columns(3)
    desliz = c[0].toggle("Verificar deslizamento", value=P.verificar_deslizamento,
                         key="emp_desliz", persist_state="session", help=AJUDA["deslizamento"])  # fmt: skip
    superficie = P.superficie
    fator = P.fator_servico
    if desliz:
        superficie = _escolha("Superfície", "emp_superficie", ep.SUPERFICIES, P.superficie,
                              "superficie", c[1])  # fmt: skip
        fator = _numero("Fator serviço/cálculo", "emp_fator", P.fator_servico, "fator_servico",
                        c[2], minimo=0.1, maximo=1.0, passo=0.05, formato="%.2f")  # fmt: skip

with st.container(border=True), secao_protegida("3. Tipo de emenda"):
    st.subheader("3. Tipo de emenda", help=AJUDA["sec_tipo"])
    c = st.columns(2)
    contato = c[0].toggle("Compressão por contato (extremidades usinadas)", value=P.contato,
                          key="emp_contato", persist_state="session", help=AJUDA["contato"])  # fmt: skip
    gap = _numero("Fresta (mm)", "emp_gap", P.gap, "gap", c[1], maximo=50.0, passo=0.5)

with st.container(border=True), secao_protegida("4. Pilar"):
    st.subheader("4. Pilar", help=AJUDA["sec_pilar"])
    c = st.columns(5)
    Lx = _numero("Lx (mm)", "emp_Lx", P.Lx, "Lx", c[0], minimo=1.0, passo=100.0, formato="%.0f")
    Kx = _numero(
        "Kx", "emp_Kx", P.Kx, "Kx", c[1], minimo=0.1, maximo=5.0, passo=0.05, formato="%.2f"
    )
    Ly = _numero("Ly (mm)", "emp_Ly", P.Ly, "Ly", c[2], minimo=1.0, passo=100.0, formato="%.0f")
    Ky = _numero(
        "Ky", "emp_Ky", P.Ky, "Ky", c[3], minimo=0.1, maximo=5.0, passo=0.05, formato="%.2f"
    )
    a = _numero("Altura da emenda, a (mm)", "emp_a", P.a, "a", c[4], minimo=0.0, passo=100.0,
                formato="%.0f")  # fmt: skip
    c = st.columns(5)
    vao_b = _numero("Vão da situação b (mm)", "emp_vao_b", 0.0, "vao_b", c[4], passo=100.0,
                    formato="%.0f")  # fmt: skip
    usar_nc = c[0].toggle("Informar N_c,Rd", value=False, key="emp_usar_nc",
                          persist_state="session", help=AJUDA["usar_nc"])  # fmt: skip
    nc_informado = None
    if usar_nc:
        nc_informado = _numero("N_c,Rd (kN)", "emp_nc", 1000.0, "nc_rd", c[1], minimo=1.0,
                               passo=10.0)  # fmt: skip
    criterio = _escolha("Esforço mínimo", "emp_criterio", ep.CRITERIOS_MINIMO, P.criterio_minimo,
                        "criterio", c[2])  # fmt: skip
    distribuicao = _escolha("Distribuição de N", "emp_distribuicao", ep.DISTRIBUICOES,
                            P.distribuicao, "distribuicao", c[3])  # fmt: skip

with st.container(border=True), secao_protegida("5. Esforços na emenda"):
    st.subheader("5. Esforços de cálculo na cota da emenda", help=AJUDA["sec_esforcos"])
    padrao_casos = emu.casos_da_tabela(
        [{"Caso": c.nome, "N (kN)": c.N, "M_x (kN·m)": c.Mx, "V (kN)": c.V, "M_y (kN·m)": c.My}
         for c in P.casos]
    )  # fmt: skip
    tabela = st.data_editor(
        padrao_casos,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="emp_casos",
        column_config={
            "Caso": st.column_config.TextColumn(help=AJUDA["casos"]),
            "N (kN)": st.column_config.NumberColumn(help=AJUDA["casos"], default=0.0),
            "M_x (kN·m)": st.column_config.NumberColumn(help=AJUDA["casos"], default=0.0),
            "V (kN)": st.column_config.NumberColumn(help=AJUDA["casos"], default=0.0),
            "M_y (kN·m)": st.column_config.NumberColumn(help=AJUDA["casos"], default=0.0),
        },
    )
    casos = []

    def _v(linha: dict[str, Any], chave: str) -> float:
        valor = linha.get(chave)
        return 0.0 if valor is None or pd.isna(valor) else float(valor)

    for i, linha in enumerate(tabela.to_dict("records")):
        nome = linha.get("Caso")
        if nome is None or pd.isna(nome) or not str(nome).strip():
            nome = f"Caso {i + 1}"
        casos.append(
            ep.CasoEsforco(
                str(nome), _v(linha, "N (kN)"), _v(linha, "M_x (kN·m)"), _v(linha, "V (kN)"),
                _v(linha, "M_y (kN·m)"),
            )
        )  # fmt: skip

with st.container(border=True), secao_protegida("6. Talas das mesas"):
    st.subheader("6. Talas das mesas", help=AJUDA["sec_mesa"])
    # no U a mesa é estreita: valores de partida próprios (uma linha de furos, tala da largura da mesa)
    PM = ep.com(P, bp=75.0, tp=9.5, nl=1, g=50.0) if eh_u else P
    c = st.columns(4)
    bp = _numero("Largura bp (mm)", "emp_bp" + sufixo, PM.bp, "bp", c[0], minimo=1.0)
    tp = _numero("Espessura tp (mm)", "emp_tp" + sufixo, PM.tp, "tp", c[1], minimo=1.0, passo=0.5)
    nl = _inteiro("Linhas na largura nl", "emp_nl" + sufixo, PM.nl, "nl", c[2])
    nr = _inteiro("Fileiras por lado nr", "emp_nr", P.nr, "nr", c[3])
    c = st.columns(4)
    g = _numero("Gabarito g (mm)", "emp_g" + sufixo, PM.g, "g", c[0], minimo=1.0)
    s = _numero("Passo s (mm)", "emp_s", P.s, "s", c[1], minimo=1.0)
    e_p = _numero("Furo → ponta da tala ep (mm)", "emp_ep", P.ep, "ep", c[2], minimo=1.0)
    e_c = _numero("Furo → ponta do pilar ec (mm)", "emp_ec", P.ec, "ec", c[3], minimo=1.0)
    raio_u, x1_u = P.raio_u, P.x1_u
    if eh_u:
        c = st.columns(4)
        x1_u = _numero("Dorso da alma → 1ª linha x1 (mm)", "emp_x1_u", P.x1_u, "x1_u", c[0],
                       minimo=1.0)  # fmt: skip
        raio_u = _numero("Raio de concordância R (mm)", "emp_raio_u", P.raio_u, "raio_u", c[1],
                         maximo=50.0, passo=0.5)  # fmt: skip

with st.container(border=True), secao_protegida("6b. Talas internas das mesas"):
    st.subheader("6b. Talas internas das mesas (corte duplo)", help=AJUDA["sec_internas"])
    c = st.columns(3)
    internas = c[0].toggle("Usar talas internas", value=P.talas_internas, key="emp_internas",
                           persist_state="session", help=AJUDA["talas_internas"])  # fmt: skip
    bi, ti = P.bi, P.ti
    if internas:
        PI = ep.com(P, bi=40.0, ti=9.5) if eh_u else P
        bi = _numero("Largura de cada tala bi (mm)", "emp_bi" + sufixo, PI.bi, "bi", c[1],
                     minimo=1.0)  # fmt: skip
        ti = _numero("Espessura ti (mm)", "emp_ti" + sufixo, PI.ti, "ti", c[2], minimo=1.0,
                     passo=0.5)  # fmt: skip

with st.container(border=True), secao_protegida("7. Talas da alma"):
    st.subheader("7. Talas da alma (2 talas)", help=AJUDA["sec_alma"])
    c = st.columns(4)
    bw = _numero("Largura bw (mm)", "emp_bw", P.bw, "bw", c[0], minimo=1.0)
    twp = _numero("Espessura de cada tala tw,p (mm)", "emp_twp", P.twp, "twp", c[1], minimo=1.0,
                  passo=0.5)  # fmt: skip
    nc = _inteiro("Colunas nc", "emp_nc_alma", P.nc, "nc", c[2])
    m = _inteiro("Fileiras por lado m", "emp_m", P.m, "m", c[3])
    c = st.columns(4)
    sh = _numero("Espaçamento horizontal sh (mm)", "emp_sh", P.sh, "sh", c[0], minimo=1.0)
    sv = _numero("Espaçamento vertical sv (mm)", "emp_sv", P.sv, "sv", c[1], minimo=1.0)
    ewv = _numero("Furo → ponta da tala ewv (mm)", "emp_ewv", P.ewv, "ewv", c[2], minimo=1.0)
    ewc = _numero("Furo → ponta do pilar ewc (mm)", "emp_ewc", P.ewc, "ewc", c[3], minimo=1.0)

entrada = ep.EntradaEmenda(
    perfil_superior=perfil_s, perfil_inferior=perfil_i, aco_perfis=aco_p, aco_talas=aco_t, E=E,
    gama_a1=g1, gama_a2=g2, diametro=diametro, grau=grau, rosca_no_plano=bool(rosca),
    verificar_deslizamento=bool(desliz), superficie=superficie, fator_servico=fator,
    contato=bool(contato), gap=gap, Lx=Lx, Kx=Kx, Ly=Ly, Ky=Ky, a=a, Nc_Rd_informado=nc_informado,
    criterio_minimo=criterio, distribuicao=distribuicao, casos=tuple(casos), bp=bp, tp=tp, nl=nl,
    nr=nr, g=g, s=s, ep=e_p, ec=e_c, bw=bw, twp=twp, nc=nc, m=m, sh=sh, sv=sv, ewv=ewv, ewc=ewc,
    talas_internas=bool(internas), bi=bi, ti=ti, raio_u=raio_u, x1_u=x1_u,
    vao_b=vao_b if vao_b > 0 else None,
)  # fmt: skip
with st.container(border=True), secao_protegida("Sugerir as talas"):
    emu.botao_sugerir_talas(entrada)
erros = ep.validar(entrada)
if erros:
    for erro in erros:
        st.error(erro, icon=":material/error:")
    st.stop()
r = ep.calcular(entrada)
resumo = ep.resumo(r)

st.header("Resultados")
with st.container(border=True), secao_protegida("Resumo"):
    st.subheader("Resumo", help=AJUDA["sec_resumo"])
    c = st.columns(5)
    c[0].metric("Situação geral", r.situacao, help=AJUDA["res_situacao"])
    c[1].metric(
        "Utilização máxima", f"{100 * r.utilizacao_maxima:.0f} %", help=AJUDA["res_utilizacao"]
    )
    c[2].metric("Total de parafusos", r.total_de_parafusos, help=AJUDA["res_parafusos"])
    c[3].metric("N_c,Rd adotado", f"{r.Nc_Rd:.1f} kN".replace(".", ","), help=AJUDA["res_nc"])
    c[4].metric("Situação mínima", r.minimo.adotado or "nenhuma", help=AJUDA["res_minimo"])
    st.markdown("\n".join(f"- **{k}:** {v}" for k, v in resumo.items()))
    if r.situacao == "ATENDE" and not r.itens_a_verificar:
        st.success(r.resumo_da_situacao, icon=":material/check_circle:")
    elif r.situacao == "ATENDE":
        st.warning(r.resumo_da_situacao, icon=":material/warning:")
    else:
        st.error(r.resumo_da_situacao, icon=":material/error:")

with st.container(border=True), secao_protegida("Avisos"):
    st.subheader("Avisos", help=AJUDA["res_avisos"])
    st.markdown("\n".join(f"- {x}" for x in r.avisos))
    if r.notas_de_desenho:
        st.markdown(
            "**Notas de desenho** (SCI P207 5.2.1):\n"
            + "\n".join(f"- {x}" for x in r.notas_de_desenho),
            help=AJUDA["res_notas"],
        )

with st.container(border=True), secao_protegida("Esforços por caso"):
    st.subheader("Esforços por caso", help=AJUDA["sec_casos"])
    st.dataframe(pd.DataFrame(ep.tabela_de_esforcos(r)).round(2), hide_index=True, width="stretch")

with st.container(border=True), secao_protegida("Verificações da mesa"):
    st.subheader("Verificações da mesa", help=AJUDA["sec_mesa_res"])
    mostrar_tabela_verificacoes(r.mesa)

with st.container(border=True), secao_protegida("Verificações da alma"):
    st.subheader("Verificações da alma", help=AJUDA["sec_alma_res"])
    mostrar_tabela_verificacoes(r.alma)

with st.container(border=True), secao_protegida("Disposições construtivas"):
    st.subheader("Disposições construtivas", help=AJUDA["sec_disposicoes"])
    nomes_status = {"OK": "OK", "ALERTA": "VERIFICAR", "N/A": "N/A"}
    disp = pd.DataFrame(
        [{"Item": v.nome,
          "Valor": "—" if v.solicitante is None else f"{ep._n(v.solicitante, 2)} {v.unidade}",
          "Exigência": v.formula, "Status": nomes_status.get(v.status, v.status),
          "Referência": v.referencia} for v in r.disposicoes]
    )  # fmt: skip
    cores = {"VERIFICAR": COR_STATUS["ALERTA"], "OK": COR_STATUS["OK"], "N/A": COR_STATUS["N/A"]}
    estilo = disp.style
    estilo = (getattr(estilo, "map", None) or estilo.applymap)(
        lambda x: cores.get(x, ""), subset=["Status"]
    )
    st.dataframe(estilo, hide_index=True, width="stretch")

with st.container(border=True), secao_protegida("Desenho esquemático"):
    st.subheader("Desenho esquemático", help=AJUDA["sec_desenho"])
    lado = st.columns(2)
    with lado[0]:
        mostrar_figura(svg_da_cena(de.vista_da_mesa(r)))
    with lado[1]:
        mostrar_figura(svg_da_cena(de.vista_da_alma(r)))

with st.container(border=True), secao_protegida("Exportar"):
    st.subheader("Exportar", help=AJUDA["sec_exportar"])
    c = st.columns(2)
    c[0].download_button(
        "Baixar CSV", data=ep.csv_completo(r), file_name="emenda_pilar.csv", mime="text/csv",
        icon=":material/download:", key="emp_csv", help=AJUDA["btn_csv"],
    )  # fmt: skip
    c[1].download_button(
        "Baixar Excel", data=lambda: ep.xlsx_completo(r), file_name="emenda_pilar.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table:", key="emp_xlsx", on_click="ignore", help=AJUDA["btn_xlsx"],
    )  # fmt: skip

with st.container(border=True), secao_protegida("Memorial desta emenda"):
    st.subheader("Memorial desta emenda", help=AJUDA["sec_memorial"])
    figuras = de.figuras_para_o_registro(r)
    botoes = st.columns(2)
    botoes[0].download_button(
        "Baixar o memorial (Word)",
        data=lambda: ep.memorial_da_emenda(r, projeto=projeto_ativo, figuras=figuras),
        file_name="memorial_emenda_de_pilar.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        icon=":material/description:", width="stretch", on_click="ignore",
        key="emp_memorial_word", help=AJUDA["btn_memorial_word"],
    )  # fmt: skip
    botoes[1].download_button(
        "Baixar o memorial (PDF)",
        data=lambda: ep.memorial_da_emenda(r, projeto=projeto_ativo, figuras=figuras, formato="pdf"),
        file_name="memorial_emenda_de_pilar.pdf", mime="application/pdf",
        icon=":material/picture_as_pdf:", width="stretch", on_click="ignore",
        key="emp_memorial_pdf", help=AJUDA["btn_memorial_pdf"],
    )  # fmt: skip

with st.container(border=True), secao_protegida("Registrar no projeto"):
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        ep.registro(r, figuras=figuras),
        key="registrar_emenda_pilar",
        rotulo="Registrar a emenda no projeto ativo",
    )

with st.container(border=True), secao_protegida("Todas as emendas do modelo"):
    emu.secao_todas_as_emendas(modelo, entrada)
