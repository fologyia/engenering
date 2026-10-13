"""Cargas do esqueleto: o que não está no modelo vira carga nas barras, caso a caso."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import base_ativa, gravar_campos_do_projeto, mapa_do_projeto
from components.cargas_esqueleto_help import AJUDA
from components.figuras_estrutura import svg_planta_do_esqueleto
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import cargas_esqueleto as ce
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo

configurar_pagina("Cargas do esqueleto", ":material/grid_view:")
cabecalho_pagina(
    "Cargas do esqueleto",
    "Modele só o esqueleto (pilares, vigas e contraventamento): piso, guarda-corpo, escadas, "
    "equipamentos, tubulações, ligações e a sobrecarga viram cargas nas barras, caso a caso, e vão "
    "para o Plano de cargas.",
    categoria="Gestão industrial",
    icone=":material/grid_view:",
    cor="violet",
    ajuda_modulo="Cargas do esqueleto",
    acoes=(("app_pages/plano_cargas.py", "Plano de cargas", ":material/table_chart:"),),
)
mapa_do_projeto(AJUDA_BASE["sec_mapa"])

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: as cargas ficam "
        "guardadas no projeto e vão para o plano de cargas dele.",
        icon=":material/folder_off:",
    )
    st.stop()

base = base_ativa()
salva = ce.entrada_do_projeto(projeto)
inicial = salva or ce.EntradaEsqueleto(
    niveis=(ce.Nivel(sobrecarga_kN_m2=float(base.sobrecarga_kN_m2) if base else 5.0),),
    temperatura=bool(base and base.anglo),
)
versao = int(st.session_state.get("ce_versao", 0))
problemas: list[str] = []

# ============================================================ 1. eixos e níveis
with st.container(border=True), secao_protegida("1. Eixos e níveis"):
    st.subheader("1. Eixos e níveis", help=AJUDA["sec_eixos"])
    colunas = st.columns(2)
    texto_x = colunas[0].text_input(
        "Eixos em X (m) — 1, 2, 3…",
        ce.texto_dos_eixos(inicial.eixos_x_m),
        key=f"ce_eixos_x_{versao}",
        help=AJUDA["eixos_x"],
    )
    texto_y = colunas[1].text_input(
        "Eixos em Y (m) — A, B, C…",
        ce.texto_dos_eixos(inicial.eixos_y_m),
        key=f"ce_eixos_y_{versao}",
        help=AJUDA["eixos_y"],
    )
    try:
        eixos_x, eixos_y = ce.ler_eixos(texto_x), ce.ler_eixos(texto_y)
    except ce.EsqueletoInvalido as erro:
        problemas.append(str(erro))
        eixos_x, eixos_y = inicial.eixos_x_m, inicial.eixos_y_m
    st.caption("Níveis de piso", help=AJUDA["niveis"])
    tabela_niveis = st.data_editor(
        pd.DataFrame(ce.tabela_dos_niveis(inicial), columns=list(ce.COLUNAS_NIVEIS)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"ce_niveis_{versao}",
        column_config={
            "Cota (m)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Vigas paralelas a": st.column_config.SelectboxColumn(
                options=list(ce.DIRECOES), default=ce.DIRECAO_X, required=True
            ),
            "Vão máx. do piso (m)": st.column_config.NumberColumn(
                min_value=0.2, max_value=10.0, format="%.2f", default=1.2
            ),
            "Piso (kN/m²)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Sobrecarga (kN/m²)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            **{f"GC {b}": st.column_config.CheckboxColumn(default=True) for b in ce.BORDAS},
        },
    )

# ============================================================ 2. fora do modelo
with st.container(border=True), secao_protegida("2. O que não está no modelo"):
    st.subheader("2. O que não está no modelo", help=AJUDA["sec_fora_do_modelo"])
    colunas = st.columns(3)
    guarda_corpo = colunas[0].number_input(
        "Guarda-corpo e rodapé (kN/m)",
        0.0,
        5.0,
        float(inicial.guarda_corpo_kN_m),
        0.05,
        format="%.2f",
        key=f"ce_guarda_corpo_{versao}",
        help=AJUDA["guarda_corpo"],
    )
    acrescimo = colunas[1].number_input(
        "Ligações, chapas e parafusos (%)",
        0.0,
        30.0,
        float(inicial.acrescimo_ligacoes_pct),
        0.5,
        format="%.1f",
        key=f"ce_acrescimo_{versao}",
        help=AJUDA["acrescimo"],
    )
    temperatura = colunas[2].toggle(
        "Temperatura ±10 °C",
        value=inicial.temperatura,
        key=f"ce_temperatura_{versao}",
        help=AJUDA["temperatura"],
    )
    st.caption("Escadas", help=AJUDA["escadas"])
    tabela_escadas = st.data_editor(
        pd.DataFrame(ce.tabela_das_escadas(inicial), columns=list(ce.COLUNAS_ESCADAS)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"ce_escadas_{versao}",
        column_config={
            "Nível": st.column_config.NumberColumn(min_value=1, step=1, format="%d", default=1),
            "Borda": st.column_config.SelectboxColumn(
                options=list(ce.BORDAS), default=ce.BORDA_X_MENOS
            ),
            "Trecho": st.column_config.NumberColumn(min_value=1, step=1, format="%d", default=1),
            "Largura (m)": st.column_config.NumberColumn(min_value=0.0, format="%.2f", default=0.8),
            "Projeção (m)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Peso (kN/m²)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", default=0.7
            ),
            "Sobrecarga (kN/m²)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", default=3.0
            ),
        },
    )
    st.caption("Equipamentos", help=AJUDA["equipamentos"])
    tabela_equipamentos = st.data_editor(
        pd.DataFrame(ce.tabela_dos_equipamentos(inicial), columns=list(ce.COLUNAS_EQUIPAMENTOS)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"ce_equipamentos_{versao}",
        column_config={
            "Nível": st.column_config.NumberColumn(min_value=1, step=1, format="%d", default=1),
            "Peso vazio (kN)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Conteúdo (kN)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", default=0.0
            ),
            "Apoios": st.column_config.NumberColumn(min_value=1, step=1, format="%d", default=4),
            "Impacto vertical (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=200.0, format="%.0f", default=0.0
            ),
            "Impacto horizontal (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=100.0, format="%.0f", default=0.0
            ),
        },
    )
    st.caption("Tubulações e bandejas", help=AJUDA["tubulacoes"])
    tabela_tubulacoes = st.data_editor(
        pd.DataFrame(ce.tabela_das_tubulacoes(inicial), columns=list(ce.COLUNAS_TUBULACOES)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"ce_tubulacoes_{versao}",
        column_config={
            "Nível": st.column_config.NumberColumn(min_value=1, step=1, format="%d", default=1),
            "kN/m": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Caso": st.column_config.SelectboxColumn(options=list(ce.CASOS_DE_LINHA), default="PE"),
        },
    )

entrada = ce.EntradaEsqueleto(
    eixos_x_m=eixos_x,
    eixos_y_m=eixos_y,
    niveis=ce.niveis_da_tabela(tabela_niveis.to_dict("records")),
    guarda_corpo_kN_m=float(guarda_corpo),
    acrescimo_ligacoes_pct=float(acrescimo),
    temperatura=bool(temperatura),
    escadas=ce.escadas_da_tabela(tabela_escadas.to_dict("records")),
    equipamentos=ce.equipamentos_da_tabela(tabela_equipamentos.to_dict("records")),
    cargas_lineares=ce.tubulacoes_da_tabela(tabela_tubulacoes.to_dict("records")),
)
problemas += ce.validar(entrada)
if problemas:
    for problema in problemas:
        st.error(problema, icon=":material/error:")
    st.stop()
resultado = ce.calcular(entrada)

# ============================================================ 3. cargas
with st.container(border=True), secao_protegida("3. Cargas nas barras"):
    st.subheader("3. Cargas nas barras", help=AJUDA["sec_cargas"])
    casos = resultado.casos
    colunas = st.columns(max(len(casos), 1) + 1)
    colunas[0].metric(
        "PP: gravidade",
        f"× {entrada.fator_peso_proprio:.2f}".replace(".", ","),
        help=AJUDA["acrescimo"],
    )
    for coluna, caso in zip(colunas[1:], casos, strict=False):
        coluna.metric(
            caso,
            f"{ce.resumo_do_caso(resultado, caso):.1f} kN".replace(".", ","),
            help=AJUDA["res_casos"],
        )
    colunas = st.columns(2)
    nivel = colunas[0].selectbox(
        "Nível",
        list(range(1, len(entrada.niveis) + 1)),
        format_func=lambda k: f"Nível {k} (+{entrada.niveis[k - 1].cota_m:.2f} m)".replace(
            ".", ","
        ),
        key="ce_nivel",
        help=AJUDA["nivel_desenho"],
    )
    caso_escolhido = colunas[1].selectbox(
        "Caso", list(casos) or ["PE"], key="ce_caso", help=AJUDA["caso_desenho"]
    )
    st.subheader("Planta do nível", help=AJUDA["res_desenho"])
    st.image(svg_planta_do_esqueleto(resultado, int(nivel), caso_escolhido), width="stretch")
    st.subheader(f"Cargas distribuídas — {caso_escolhido}", help=AJUDA["res_barras"])
    st.dataframe(
        pd.DataFrame(
            ce.linhas_por_barra(resultado, caso_escolhido), columns=list(ce.COLUNAS_POR_BARRA)
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "kN/m": st.column_config.NumberColumn(format="%.3f"),
            "Comprimento (m)": st.column_config.NumberColumn(format="%.2f"),
            "Resultante (kN)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    forcas = ce.linhas_das_forcas(resultado, caso_escolhido)
    if forcas:
        st.subheader(f"Forças concentradas — {caso_escolhido}", help=AJUDA["res_forcas"])
        st.dataframe(
            pd.DataFrame(forcas, columns=list(ce.COLUNAS_FORCAS)),
            hide_index=True,
            width="stretch",
            column_config={"kN (cada)": st.column_config.NumberColumn(format="%.2f")},
        )
    st.subheader("Conferência", help=AJUDA["res_conferencia"])
    st.dataframe(
        pd.DataFrame(ce.linhas_da_conferencia(resultado), columns=list(ce.COLUNAS_CONFERENCIA)),
        hide_index=True,
        width="stretch",
        column_config={
            "Entrou (kN)": st.column_config.NumberColumn(format="%.2f"),
            "Aplicado (kN)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    for texto in resultado.fundacao:
        st.caption(f":material/foundation: {texto}")

# ============================================================ 4. enviar
with st.container(border=True), secao_protegida("4. Gravar e enviar ao plano de cargas"):
    st.subheader("4. Gravar e enviar ao plano de cargas", help=AJUDA["sec_enviar"])
    plano = pc.plano_do_projeto(projeto)
    gerados = {a.codigo for a in ce.acoes_para_o_plano(resultado)}
    manuais = [a.codigo for a in plano.acoes if a.codigo in gerados and a.origem != ce.ORIGEM]
    if manuais:
        st.warning(
            f"No plano de cargas, {', '.join(manuais)} foram informados de outra forma: ao enviar, "
            "esta página os substitui.",
            icon=":material/warning:",
        )
    colunas = st.columns(3)
    if colunas[0].button(
        "Gravar e enviar ao plano",
        type="primary",
        icon=":material/send:",
        key="ce_enviar",
        help=AJUDA["btn_enviar"],
        width="stretch",
    ) and gravar_campos_do_projeto(
        {
            "cargas_do_esqueleto": ce.para_dicionario(entrada),
            "plano_de_cargas": pc.para_dicionario(ce.aplicar_no_plano(resultado, plano)),
        },
        "Cargas do esqueleto enviadas ao plano de cargas",
    ):
        st.session_state["ce_versao"] = versao + 1
        st.rerun()
    if colunas[1].button(
        "Gravar só os dados",
        icon=":material/save:",
        key="ce_gravar",
        help=AJUDA["btn_gravar"],
        width="stretch",
    ) and gravar_campos_do_projeto(
        {"cargas_do_esqueleto": ce.para_dicionario(entrada)}, "Cargas do esqueleto gravadas"
    ):
        st.session_state["ce_versao"] = versao + 1
        st.rerun()
    colunas[2].download_button(
        "Cargas (CSV)",
        data=ce.csv_das_cargas(resultado),
        file_name=f"cargas_do_esqueleto_{projeto.get('codigo') or 'projeto'}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="ce_csv",
        help=AJUDA["btn_csv"],
        width="stretch",
    )
    st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
    botao_registrar_calculo(
        ce.registro_esqueleto(resultado),
        key="registrar_cargas_esqueleto",
        rotulo="Registrar as cargas do esqueleto no projeto ativo",
        identificar_peca=False,
    )
