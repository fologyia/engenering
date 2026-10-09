"""Lista de material: massa, peso, pintura e barras para o orçamento, e o peso próprio do modelo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import gravar_campo_do_projeto, mapa_do_projeto
from components.lista_de_material_help import AJUDA
from components.ui import cabecalho_pagina, configurar_pagina
from core import esforcos_modelo as em
from core import lista_de_material as lm
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo

configurar_pagina("Lista de material", ":material/inventory_2:")
cabecalho_pagina(
    "Lista de material",
    "Perfis, chapas e demais itens da estrutura: massa, peso, área de pintura e barras para o "
    "orçamento, com a conferência do peso próprio do modelo.",
    categoria="Gestão industrial",
    icone=":material/inventory_2:",
    cor="violet",
    ajuda_modulo="Lista de material",
    acoes=(("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),),
)
mapa_do_projeto(AJUDA_BASE["sec_mapa"])

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos permanentes**: a lista fica guardada "
        "no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()

lista = lm.lista_do_projeto(projeto)
dados = em.esforcos_do_projeto(projeto)
versao = int(st.session_state.get("lm_versao", 0))
ICONES = {
    pc.NIVEL_ERRO: ":material/error:",
    pc.NIVEL_ATENCAO: ":material/warning:",
    pc.NIVEL_OK: ":material/check_circle:",
}
MOSTRAR = {pc.NIVEL_ERRO: st.error, pc.NIVEL_ATENCAO: st.warning}


def gravar(nova: lm.ListaDeMaterial, motivo: str) -> bool:
    if gravar_campo_do_projeto("lista_de_material", lm.para_dicionario(nova), motivo):
        st.session_state["lm_versao"] = versao + 1
        return True
    return False


def _kg(valor: float) -> str:
    return f"{valor:,.0f} kg".replace(",", " ")


# ============================================================ 1. importar
with st.container(border=True):
    st.subheader("1. Importar a lista de corte do SolidWorks", help=AJUDA["sec_importar"])
    colunas = st.columns([3, 1])
    colunas[0].caption(
        "Pelo jeito mais simples: rode no SolidWorks, com a peça aberta, a macro abaixo — ela lê "
        "a lista de corte direto da árvore da peça e salva o CSV na pasta da peça. Uso: "
        "Ferramentas › Macro › Nova, apague o texto do editor, cole o da macro e tecle F5."
    )
    colunas[1].download_button(
        "Macro do SolidWorks",
        data=lm.macro_da_lista_de_corte(),
        file_name="exportar_lista_de_corte.bas",
        mime="text/plain",
        icon=":material/code:",
        key="lm_macro",
        help=AJUDA["btn_macro"],
        width="stretch",
    )
    colunas = st.columns([3, 1])
    arquivo = colunas[0].file_uploader(
        "Lista de corte (CSV ou Excel)",
        type=["csv", "txt", "xlsx", "xls"],
        key=f"lm_arquivo_{versao}",
        help=AJUDA["arquivo"],
    )
    unidade = colunas[1].radio(
        "Comprimentos sem unidade em", ["mm", "m"], key="lm_unidade", help=AJUDA["unidade"]
    )
    if arquivo is not None:
        try:
            lidos, avisos = lm.ler_lista_de_corte(arquivo.getvalue(), arquivo.name, unidade=unidade)
        except ValueError as erro:
            lidos, avisos = [], [str(erro)]
        for aviso in avisos:
            st.warning(aviso, icon=":material/warning:")
        if lidos:
            previa = lm.resumir(lm.ListaDeMaterial(itens=tuple(lidos)))
            st.caption(
                f"{len(lidos)} linha(s) lidas de {arquivo.name} — {_kg(previa.massa_itens_kg)} "
                "sem o acréscimo."
            )
            st.dataframe(
                pd.DataFrame(lm.linhas_da_tabela(previa), columns=list(lm.COLUNAS)).replace(
                    "", None
                ),
                hide_index=True,
                width="stretch",
            )
            colunas = st.columns(2)
            if colunas[0].button(
                "Acrescentar à lista",
                type="primary",
                icon=":material/playlist_add:",
                key="lm_acrescentar",
                help=AJUDA["btn_acrescentar"],
                width="stretch",
            ) and gravar(
                lm.com_itens(lista, [*lista.itens, *lidos]), "Lista de material: lista de corte"
            ):
                st.rerun()
            if colunas[1].button(
                "Substituir a lista",
                icon=":material/swap_horiz:",
                key="lm_substituir",
                help=AJUDA["btn_substituir"],
                width="stretch",
            ) and gravar(lm.com_itens(lista, lidos), "Lista de material: lista de corte"):
                st.rerun()

# ============================================================ 2. itens
with st.container(border=True):
    st.subheader(f"2. Itens da lista ({len(lista.itens)})", help=AJUDA["sec_itens"])
    editada = st.data_editor(
        pd.DataFrame(lm.tabela_editavel(lista), columns=list(lm.COLUNAS_EDITAVEIS)),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=f"lm_itens_{versao}",
        column_config={
            "Marca": st.column_config.TextColumn(help="Marca ou posição no desenho."),
            "Tipo": st.column_config.SelectboxColumn(
                options=list(lm.TIPOS),
                default=lm.TIPO_PERFIL,
                required=True,
                help="Perfil, chapa, grade ou piso, ou outro item.",
            ),
            "Descrição": st.column_config.TextColumn(
                help=(
                    'Perfil do catálogo (W 200 x 35,9 (H), U 8" x 20,50, L 2" × 1/4"), o nome do '
                    "SolidWorks (W8X31, C8X13.75) ou as medidas (TUBO QUADRADO 50 X 50 X 3)."
                ),
                width="large",
            ),
            "Qtd": st.column_config.NumberColumn(min_value=0, step=1, format="%d", default=1),
            "Comprimento (m)": st.column_config.NumberColumn(
                min_value=0.0, format="%.3f", help="Comprimento de cada peça."
            ),
            "Largura (mm)": st.column_config.NumberColumn(
                min_value=0.0, format="%.0f", help="Chapa e grade."
            ),
            "Espessura (mm)": st.column_config.NumberColumn(
                min_value=0.0, format="%.2f", help="Chapa."
            ),
            "Massa unitária": st.column_config.NumberColumn(
                min_value=0.0,
                format="%.2f",
                help=(
                    "kg/m no perfil fora do catálogo, kg/m² na grade, kg por unidade em Outro. "
                    "Vazio no perfil do catálogo e na chapa (o programa calcula)."
                ),
            ),
            lm.COLUNA_GEOMETRIA: st.column_config.NumberColumn(
                format="%.2f",
                help=(
                    "Massa de uma peça pelo volume do modelo, como aço (vem da macro do "
                    "SolidWorks). Vale quando falta o dado do catálogo."
                ),
            ),
        },
        disabled=[lm.COLUNA_GEOMETRIA],
    )
    colunas = st.columns(2)
    acrescimo = colunas[0].number_input(
        "Acréscimo de ligações, parafusos e soldas (%)",
        0.0,
        50.0,
        float(lista.acrescimo_pct),
        0.5,
        format="%.1f",
        key=f"lm_acrescimo_{versao}",
        help=AJUDA["acrescimo"],
    )
    barra = colunas[1].number_input(
        "Barra comercial (m)",
        1.0,
        24.0,
        float(lista.comprimento_barra_m),
        1.0,
        format="%.1f",
        key=f"lm_barra_{versao}",
        help=AJUDA["barra"],
    )
    atual = lm.ListaDeMaterial(
        itens=tuple(lm.itens_da_tabela(editada.to_dict("records"))),
        acrescimo_pct=float(acrescimo),
        comprimento_barra_m=float(barra),
    )
    if atual != lista:
        st.caption(
            ":material/edit: Há alterações ainda não gravadas — o resumo abaixo já as considera."
        )
    colunas = st.columns(2)
    if colunas[0].button(
        "Gravar a lista",
        type="primary",
        icon=":material/save:",
        key="lm_gravar",
        help=AJUDA["btn_gravar"],
        width="stretch",
    ) and gravar(atual, "Lista de material atualizada"):
        st.rerun()
    pilares = sum(m.tipo == "Pilar" for m in dados.membros.values())
    if colunas[1].button(
        f"Incluir as placas de base ({pilares} pilar(es))",
        icon=":material/crop_square:",
        key="lm_placas",
        help=AJUDA["btn_placas"],
        disabled=pilares == 0,
        width="stretch",
    ) and gravar(lm.com_placas_de_base(atual, dados), "Lista de material: placas de base"):
        st.rerun()

# ============================================================ 3. resumo
resumo = lm.resumir(atual)
with st.container(border=True):
    st.subheader("3. Resumo", help=AJUDA["sec_resumo"])
    colunas = st.columns(4)
    colunas[0].metric(
        "Massa total",
        _kg(resumo.massa_total_kg),
        help=AJUDA["res_massa"],
    )
    colunas[1].metric(
        "Peso", f"{resumo.peso_total_kN:.2f} kN".replace(".", ","), help=AJUDA["res_peso"]
    )
    colunas[2].metric(
        "Área de pintura",
        f"{resumo.area_pintura_m2:.1f} m²".replace(".", ","),
        help=AJUDA["res_pintura"],
    )
    colunas[3].metric("Itens sem massa", len(resumo.pendentes), help=AJUDA["res_pendentes"])
    st.caption(
        " · ".join(f"{rotulo}: {valor}" for rotulo, valor in lm.totais(resumo)[:3])
        + " · "
        + " · ".join(f"{tipo}: {_kg(massa)}" for tipo, massa in resumo.por_tipo.items() if massa)
        + (
            f" · pela geometria do modelo (aço): {_kg(resumo.massa_geometria_kg)}"
            if resumo.massa_geometria_kg
            else ""
        )
    )
    for linha in resumo.pendentes[:10]:
        st.warning(
            f"{linha.item.marca or '—'} · {linha.item.descricao or linha.item.tipo}: "
            f"{linha.pendencia}.",
            icon=":material/warning:",
        )
    if resumo.perfis:
        st.subheader("Por perfil", help=AJUDA["sec_perfis"])
        st.dataframe(
            pd.DataFrame(lm.linhas_dos_perfis(resumo), columns=list(lm.COLUNAS_PERFIS)),
            hide_index=True,
            width="stretch",
            column_config={
                "Comprimento total (m)": st.column_config.NumberColumn(format="%.2f"),
                "kg/m": st.column_config.NumberColumn(format="%.2f"),
                "Massa (kg)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
    if resumo.chapas:
        st.subheader("Chapas por espessura", help=AJUDA["sec_chapas"])
        st.dataframe(
            pd.DataFrame(lm.linhas_das_chapas(resumo), columns=list(lm.COLUNAS_CHAPAS)),
            hide_index=True,
            width="stretch",
            column_config={
                "Área (m²)": st.column_config.NumberColumn(format="%.2f"),
                "Massa (kg)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

# ============================================================ 4. conferência
with st.container(border=True):
    st.subheader("4. Conferência com o peso próprio do modelo", help=AJUDA["sec_conferencia"])
    for item in lm.conferir_com_o_modelo(resumo, dados):
        MOSTRAR.get(item.nivel, st.success)(item.texto, icon=ICONES[item.nivel])

# ============================================================ 5. exportar
with st.container(border=True):
    st.subheader("5. Exportar", help=AJUDA["sec_exportar"])
    colunas = st.columns(2)
    colunas[0].download_button(
        "Lista de material (Excel)",
        data=lm.xlsx_da_lista(
            resumo, titulo=f"{projeto.get('nome', '')} ({projeto.get('codigo', '')})"
        ),
        file_name=f"lista_de_material_{projeto.get('codigo') or 'projeto'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table_view:",
        key="lm_xlsx",
        help=AJUDA["btn_xlsx"],
        width="stretch",
    )
    colunas[1].download_button(
        "Itens (CSV)",
        data=lm.csv_da_lista(resumo),
        file_name=f"lista_de_material_{projeto.get('codigo') or 'projeto'}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="lm_csv",
        help=AJUDA["btn_csv"],
        width="stretch",
    )
