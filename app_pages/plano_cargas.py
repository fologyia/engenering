"""Plano de cargas do projeto: ações com código padrão, cargas para o modelo e combinações."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA
from components.base_tecnica_ui import (
    gravar_acoes_no_plano,
    gravar_plano,
    mapa_do_projeto,
)
from components.ui import cabecalho_pagina, configurar_pagina
from core import base_tecnica as bt
from core import criterio_anglo as ca
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core.memorial_verificacoes import decimal_ptbr
from core.project_store import obter_projeto_ativo

configurar_pagina("Plano de cargas", ":material/table_chart:")
cabecalho_pagina(
    "Plano de cargas",
    "As ações do projeto com código padrão, de onde vieram, as cargas que vão para o modelo "
    "(SolidWorks, Robot) e as combinações ELU e ELS.",
    categoria="Gestão industrial",
    icone=":material/table_chart:",
    cor="violet",
    ajuda_modulo="Plano de cargas",
    acoes=(
        ("app_pages/base_tecnica.py", "Base técnica", ":material/tune:"),
        ("app_pages/vento_estrutura_aberta.py", "Vento em estruturas abertas", ":material/air:"),
    ),
)
mapa_do_projeto(AJUDA["sec_mapa"])

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: o plano de cargas fica "
        "guardado no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()

plano = pc.plano_do_projeto(projeto)
base = bt.base_do_projeto(projeto)

# ============================================================ ações
with st.container(border=True):
    st.subheader(f"Ações ({len(plano.acoes)})", help=AJUDA["sec_plano"])
    if plano.acoes:
        linhas = []
        for a in plano.acoes:
            cat = comb.categoria_nbr(a.categoria)
            linhas.append(
                {
                    "Código": a.codigo,
                    "Nome": a.nome,
                    "Tipo": cat.tipo,
                    "Categoria NBR 8800": a.categoria,
                    "Grupo": a.grupo or "—",
                    "γ": cat.gamma,
                    "ψ0": cat.psi0,
                    "ψ1": cat.psi1,
                    "ψ2": cat.psi2,
                    "Origem": a.origem,
                    "Cargas": len(a.cargas),
                    "Resumo": a.resumo,
                }
            )
        st.dataframe(
            pd.DataFrame(linhas),
            hide_index=True,
            width="stretch",
            column_config={
                c: st.column_config.NumberColumn(format="%.2f") for c in ("γ", "ψ0", "ψ1", "ψ2")
            },
        )
        for a in plano.acoes:
            with st.expander(f"{a.codigo} — {a.nome} ({len(a.cargas)} carga(s))"):
                if a.descricao:
                    st.caption(a.descricao)
                if a.cargas:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Elemento": c.elemento,
                                    "Direção": c.direcao,
                                    "Valor": c.valor,
                                    "Unidade": c.unidade,
                                    "Observação": c.observacao,
                                }
                                for c in a.cargas
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                        column_config={"Valor": st.column_config.NumberColumn(format="%.3f")},
                    )
                if st.button(
                    f"Remover {a.codigo}",
                    icon=":material/delete:",
                    key=f"pc_remover_{a.codigo}",
                    help=AJUDA["btn_remover"],
                ):
                    if gravar_plano(
                        pc.sem_acao(plano, a.codigo), f"Plano de cargas: {a.codigo} removida"
                    ):
                        st.rerun()
    else:
        st.caption(
            "Plano vazio. Gere o vento nas páginas de vento (botão “Enviar ao plano de cargas”) e "
            "inclua aqui os pesos, a sobrecarga e as demais ações."
        )
    colunas = st.columns(2)
    if (
        colunas[0].button(
            "Incluir a sobrecarga da base técnica",
            icon=":material/add:",
            key="pc_incluir_sobrecarga",
            help=AJUDA["btn_sobrecarga"],
            disabled=base is None,
        )
        and base is not None
    ):
        acao = pc.nova_acao(
            "SC",
            origem="Base técnica do projeto",
            descricao=f"{base.sobrecarga_local} ({base.rotulo_cliente}).",
            resumo=f"{bt.numero(base.sobrecarga_kN_m2, 2)} kN/m² em todos os pisos",
            cargas=[
                pc.CargaDoModelo(
                    "Todos os pisos",
                    base.sobrecarga_kN_m2,
                    "kN/m²",
                    "Z (vertical)",
                    base.sobrecarga_local,
                )
            ],
        )
        if gravar_acoes_no_plano([acao], origem="Base técnica"):
            st.rerun()
    if colunas[1].button(
        "Incluir temperatura ±10 °C (Anglo 5.8)",
        icon=":material/thermostat:",
        key="pc_incluir_temperatura",
        help=AJUDA["btn_temperatura"],
    ):
        acoes = [
            pc.nova_acao(
                codigo,
                origem=ca.item("5.8"),
                resumo=f"{sinal}{ca.TEMPERATURA_VARIACAO_C:g} °C uniforme",
                cargas=[
                    pc.CargaDoModelo(
                        "Toda a estrutura", sinal_valor * ca.TEMPERATURA_VARIACAO_C, "°C", "—"
                    )
                ],
            )
            for codigo, sinal, sinal_valor in (("T+", "+", 1.0), ("T−", "−", -1.0))
        ]
        if gravar_acoes_no_plano(acoes, origem="critério Anglo 5.8"):
            st.rerun()

# ============================================================ adicionar
with st.container(border=True):
    st.subheader("Adicionar ou substituir uma ação", help=AJUDA["sec_adicionar"])
    with st.form("pc_formulario_acao", border=False):
        colunas = st.columns([1, 2, 3])
        codigos = [c.codigo for c in pc.CODIGOS]
        codigo = colunas[0].selectbox(
            "Código",
            codigos,
            format_func=lambda c: f"{c} — {pc.CODIGOS_POR_NOME[c].nome}",
            help=AJUDA["codigo"],
        )
        nome = colunas[1].text_input("Nome", help=AJUDA["nome"], placeholder="vazio = nome padrão")
        categorias = [c.rotulo for c in comb.CATEGORIAS_NBR8800]
        categoria = colunas[2].selectbox(
            "Categoria (vazio = a do código)",
            ["", *categorias],
            format_func=lambda c: c or "a padrão do código",
            help=AJUDA["categoria_nbr"],
        )
        descricao = st.text_input("Descrição", help=AJUDA["descricao"])
        st.markdown("**Cargas para o modelo** (opcional)", help=AJUDA["cargas_tabela"])
        tabela = st.data_editor(
            pd.DataFrame(columns=["Elemento", "Valor", "Unidade", "Direção", "Observação"]),
            num_rows="dynamic",
            hide_index=True,
            key="pc_cargas_novas",
            column_config={
                "Elemento": st.column_config.TextColumn(help="Onde a carga é aplicada."),
                "Valor": st.column_config.NumberColumn(help="Valor característico."),
                "Unidade": st.column_config.SelectboxColumn(
                    options=list(pc.UNIDADES), help="Unidade do valor."
                ),
                "Direção": st.column_config.SelectboxColumn(
                    options=list(pc.DIRECOES), help="Direção da carga."
                ),
                "Observação": st.column_config.TextColumn(help="Nota livre."),
            },
        )
        adicionar = st.form_submit_button(
            "Gravar a ação", type="primary", icon=":material/save:", help=AJUDA["btn_adicionar"]
        )
    if adicionar:
        cargas = []
        for _, linha in tabela.iterrows():
            if pd.isna(linha.get("Valor")) or not str(linha.get("Elemento") or "").strip():
                continue
            cargas.append(
                pc.CargaDoModelo(
                    str(linha["Elemento"]).strip(),
                    float(linha["Valor"]),
                    str(linha.get("Unidade") or "kN"),
                    str(linha.get("Direção") or "—"),
                    str(linha.get("Observação") or ""),
                )
            )
        acao = pc.nova_acao(
            codigo, nome=nome, categoria=categoria, descricao=descricao, cargas=cargas
        )
        erros = pc.validar_acao(acao)
        if erros:
            for erro in erros:
                st.error(erro, icon=":material/error:")
        elif gravar_acoes_no_plano([acao], origem="informada"):
            st.rerun()

if not plano.acoes:
    st.stop()

# ============================================================ combinações
with st.container(border=True):
    st.subheader("Combinações", help=AJUDA["res_combinacoes"])
    estados = st.multiselect(
        "Estados-limite",
        list(comb.TODOS_OS_ESTADOS),
        default=list(comb.ESTADOS_PADRAO),
        key="pc_estados",
        help=AJUDA["estados"],
    )
    lista = pc.combinacoes(plano, estados) if estados else []
    st.caption(
        f"{len(lista)} combinações. Fatores das Tabelas 1 e 2 da NBR 8800; o vento nas quatro "
        "direções é um grupo exclusivo. Valores característicos no modelo, combinações aqui."
    )
    if lista:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nº": c.numero,
                        "Estado-limite": c.estado_limite,
                        "Combinação": c.nome,
                        "Expressão": decimal_ptbr(c.expressao),
                    }
                    for c in lista
                ]
            ),
            hide_index=True,
            width="stretch",
            height=min(420, 40 + 35 * len(lista)),
        )
    if base is not None and base.anglo:
        st.subheader("Combinações mínimas do critério Anglo (5.9)", help=AJUDA["res_anglo"])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Combinação mínima": c.combinacao,
                        "Situação": "pode ser formada" if c.coberta else "faltam ações",
                        "Faltam": ", ".join(c.faltantes) or "—",
                        "Só se houver o equipamento": ", ".join(c.opcionais_ausentes) or "—",
                    }
                    for c in pc.cobertura_das_combinacoes_anglo(plano)
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(f"{ca.LEGENDA_COMBINACOES} {ca.QUADRO_DE_CARGAS_FUNDACOES}")

# ============================================================ exportar
with st.container(border=True):
    st.subheader("Exportar", help=AJUDA["res_exportar"])
    colunas = st.columns(3)
    colunas[0].download_button(
        "Ações (CSV)",
        data=pc.csv_das_acoes(plano),
        file_name=f"plano_de_cargas_acoes_{projeto['codigo']}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="pc_csv_acoes",
        help=AJUDA["btn_csv_acoes"],
        width="stretch",
    )
    colunas[1].download_button(
        "Cargas para o modelo (CSV)",
        data=pc.csv_das_cargas(plano),
        file_name=f"plano_de_cargas_modelo_{projeto['codigo']}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="pc_csv_cargas",
        help=AJUDA["btn_csv_cargas"],
        width="stretch",
    )
    colunas[2].download_button(
        "Combinações (CSV)",
        data=pc.csv_das_combinacoes(plano, estados or comb.ESTADOS_PADRAO),
        file_name=f"plano_de_cargas_combinacoes_{projeto['codigo']}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="pc_csv_comb",
        help=AJUDA["btn_csv_comb"],
        width="stretch",
    )
