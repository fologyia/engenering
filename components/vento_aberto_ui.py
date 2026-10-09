"""Interface da página Vento em estruturas abertas (só o vento, para anotar e lançar no modelo).

Usa os mesmos campos da página Contraventamento de estruturas abertas (mesmas chaves de sessão): o
que se digita numa aparece na outra. O cálculo está em :mod:`core.vento_estrutura_aberta` e o
registro, as ações do plano e os CSV em :mod:`core.vento_aberto_registro`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components import contraventamento_estrutura_ui as ce
from components.base_tecnica_ui import base_ativa, gravar_acoes_no_plano, legenda_da_base
from components.figuras_estrutura import svg_vento_elevacao
from components.project_tools import botao_registrar_calculo
from components.ui import fronteira_modelo
from core import base_tecnica as bt
from core import contraventamento_plataforma as cp
from core import vento_aberto_registro as var
from core import vento_estrutura_aberta as va

AJUDA: dict[str, str] = {
    "sec_equipamentos": (
        "Vasos, painéis, motores e outros volumes apoiados nos pisos: recebem vento como "
        "cilindro (Tabelas 27 e 28 da NBR 6123) ou como caixa (C_a = 2,0)."
    ),
    "res_total": "Força total do vento na direção (característica), somando todos os níveis e a base.",
    "res_momento": "Momento de tombamento na base: Σ força do nível × cota.",
    "res_q": "Pressão dinâmica no topo da estrutura (com o guarda-corpo).",
    "res_desenho": (
        "Os pórticos vistos de lado: o vento entra pela esquerda, o pórtico de barlavento recebe a "
        "força cheia e os de trás são protegidos (η). As setas são as forças por nível."
    ),
    "res_niveis": "Força em cada nível: pórticos, guarda-corpos e equipamentos, com o q da faixa.",
    "res_nos": (
        "O que lançar no modelo como carga nodal: a força de cada pórtico em cada nível e a "
        "parcela de cada nó pilar–viga."
    ),
    "res_barras": (
        "Para quem prefere carga distribuída: kN/m em cada pilar, viga e guarda-corpo de cada "
        "pórtico. As diagonais ficam de fora (já estão nas forças nos nós)."
    ),
    "res_coef": "φ, C_a e η de cada pórtico, a memória de V_k e q, e o cálculo dos equipamentos.",
    "res_exportar": (
        "CSV com ponto e vírgula e vírgula decimal (abre no Excel): forças nos nós (com a faixa da "
        "base) e cargas distribuídas, das duas direções."
    ),
    "btn_csv_nos": "Forças nos nós por pórtico e nível, nas duas direções.",
    "btn_csv_barras": "Carga por metro em pilares, vigas e guarda-corpos de cada pórtico.",
    "btn_plano": (
        "Grava W0, W90, W180 e W270 no plano de cargas do projeto, com a força em cada nó: as "
        "combinações saem de lá. Se já existirem, são substituídas."
    ),
    "reg_registrar": "Grava o cálculo no projeto ativo: o memorial passa a trazer as três tabelas.",
    "direcao": "Qual direção do vento mostrar.",
}

FORA_DO_ESCOPO = (
    "Vento oblíquo (entre 0° e 90°) e efeitos dinâmicos (capítulo 9 da NBR 6123).",
    "Coberturas isoladas e placas (Tabelas 24 e 25 e 7.1): use o módulo Vento nas estruturas.",
    "Barras de seção circular com o C_a menor da Figura 13: o programa usa a Figura 12 (a favor da "
    "segurança).",
    "As combinações: estas são forças características — as combinações saem do plano de cargas.",
)


def _pt(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _tabela(dados: dict[str, Any]) -> None:
    st.dataframe(
        pd.DataFrame(dados["linhas"], columns=dados["cabecalhos"]), hide_index=True, width="stretch"
    )
    st.caption(dados["legenda"])


def mostrar_vento_em_estrutura_aberta() -> None:
    fronteira_modelo(list(FORA_DO_ESCOPO), titulo="O que esta página não faz")
    base = base_ativa()
    legenda_da_base(base)
    erros: list[str] = []
    ident = ce.formulario_identificacao()
    estrutura = ce.formulario_estrutura(erros)
    vento = ce.formulario_vento(base, titulo="3. Vento (NBR 6123:2023)")
    sx, sy = ce.formulario_contraventamento(
        com_ligacao=False, titulo="4. Contraventamento (só para a área exposta ao vento)"
    )
    with st.container(border=True):
        st.subheader("5. Equipamentos", help=AJUDA["sec_equipamentos"])
        equipamentos = ce.tabela_equipamentos(erros)
    if erros:
        for erro in erros:
            st.error(erro, icon=":material/error:")
        st.stop()
    entrada = cp.EntradaContraventamento(
        comprimento_x_m=estrutura.comprimento_x,
        largura_y_m=estrutura.largura_y,
        cotas_m=estrutura.cotas,
        vaos_x=estrutura.vaos_x,
        vaos_y=estrutura.vaos_y,
        largura_pilar_m=estrutura.largura_pilar_m,
        altura_viga_m=estrutura.altura_viga_m,
        guarda_corpo=estrutura.guarda_corpo,
        altura_guarda_corpo_m=estrutura.altura_gc,
        indice_guarda_corpo=estrutura.phi_gc,
        equipamentos=equipamentos,
        vento=vento,
        contraventamento_x=sx,
        contraventamento_y=sy,
    )
    problemas = cp.validar_entrada(entrada)
    if problemas:
        for erro in problemas:
            st.error(erro, icon=":material/error:")
        st.stop()
    geometria = cp.geometria_do_vento(entrada)
    try:
        resultado = va.calcular_vento_aberto(geometria, vento)
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()

    st.header("Resultados")
    colunas = st.columns(5)
    colunas[0].metric("Vento em X", f"{_pt(resultado.x.total_kN)} kN", help=AJUDA["res_total"])
    colunas[1].metric("Vento em Y", f"{_pt(resultado.y.total_kN)} kN", help=AJUDA["res_total"])
    colunas[2].metric(
        "Momento na base X",
        f"{_pt(resultado.x.momento_na_base_kNm)} kN·m",
        help=AJUDA["res_momento"],
    )
    colunas[3].metric(
        "Momento na base Y",
        f"{_pt(resultado.y.momento_na_base_kNm)} kN·m",
        help=AJUDA["res_momento"],
    )
    colunas[4].metric(
        "q no topo (kN/m²)", _pt(resultado.vento_no_topo.q_N_m2 / 1e3, 3), help=AJUDA["res_q"]
    )
    for aviso in resultado.avisos:
        st.warning(aviso, icon=":material/warning:")
    tabelas = var.tabelas_para_memorial(resultado)
    abas = st.tabs(
        ["Desenhos", "Forças por nível", "Forças nos nós", "Cargas nas barras", "Coeficientes"]
    )
    with abas[0]:
        direcao = st.radio(
            "Direção do vento", ["X", "Y"], horizontal=True, key="va_direcao", help=AJUDA["direcao"]
        )
        st.subheader(f"Vento em {direcao}", help=AJUDA["res_desenho"])
        st.image(svg_vento_elevacao(geometria, resultado.direcao(direcao)), width="stretch")
    with abas[1]:
        st.subheader("Forças por nível", help=AJUDA["res_niveis"])
        _tabela(tabelas[0])
    with abas[2]:
        st.subheader("Forças nos nós", help=AJUDA["res_nos"])
        _tabela(tabelas[2])
    with abas[3]:
        st.subheader("Cargas nas barras", help=AJUDA["res_barras"])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Direção": c.direcao,
                        "Pórtico": f"P{c.portico}",
                        "Elemento": c.elemento,
                        "Trecho": c.trecho,
                        "w (kN/m)": c.w_kN_m,
                        "Cálculo": c.calculo,
                    }
                    for d in (resultado.x, resultado.y)
                    for c in va.cargas_distribuidas(geometria, d)
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={"w (kN/m)": st.column_config.NumberColumn(format="%.3f")},
        )
    with abas[4]:
        st.subheader("Pórticos e coeficientes", help=AJUDA["res_coef"])
        _tabela(tabelas[1])
        st.caption(" · ".join(resultado.vento_no_topo.memoria))
        detalhes = [*resultado.x.detalhes_equipamentos, *resultado.y.detalhes_equipamentos]
        if detalhes:
            st.caption("\n".join(f"- {t}" for t in detalhes))

    with st.container(border=True):
        st.subheader("Exportar e levar ao projeto", help=AJUDA["res_exportar"])
        colunas = st.columns(3)
        colunas[0].download_button(
            "Forças nos nós (CSV)",
            data=var.csv_nos_nos(resultado),
            file_name="vento_estrutura_aberta_nos.csv",
            mime="text/csv",
            icon=":material/download:",
            key="va_csv_nos",
            help=AJUDA["btn_csv_nos"],
            width="stretch",
        )
        colunas[1].download_button(
            "Cargas nas barras (CSV)",
            data=var.csv_distribuidas(geometria, resultado),
            file_name="vento_estrutura_aberta_barras.csv",
            mime="text/csv",
            icon=":material/download:",
            key="va_csv_barras",
            help=AJUDA["btn_csv_barras"],
            width="stretch",
        )
        if colunas[2].button(
            "Enviar ao plano de cargas",
            icon=":material/table_chart:",
            key="va_para_plano",
            help=AJUDA["btn_plano"],
            width="stretch",
        ) and gravar_acoes_no_plano(
            var.acoes_para_o_plano(resultado), origem="Vento em estruturas abertas"
        ):
            st.success(
                "W0, W90, W180 e W270 gravados no plano de cargas.", icon=":material/check_circle:"
            )

    contexto: dict[str, Any] = {"data_do_calculo": ident.data.isoformat()}
    if ident.obra:
        contexto["obra"] = ident.obra
    if ident.tag:
        contexto["tag"] = ident.tag
    registro = var.registro_vento_aberto(
        resultado,
        contexto=contexto,
        responsavel=ident.responsavel,
        avisos_da_base=bt.avisos(base) if base else None,
    )
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_vento_estrutura_aberta",
            rotulo="Registrar o vento no projeto ativo",
        )
