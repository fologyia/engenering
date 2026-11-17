"""Cargas do esqueleto: o que não está no modelo vira carga nas barras, caso a caso.

Com o esqueleto da macro do SolidWorks no projeto, a página trabalha a partir dele: mostra o que
entendeu (chapas de piso, patamares, lances de escada, níveis, vigas que apoiam cada chapa), deixa
conferir em 3D, dá a carga de cada chapa às vigas e envia tudo ao plano de cargas de uma vez. Sem
o esqueleto (ou a pedido), a forma pela grade de eixos.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.base_tecnica_help import AJUDA as AJUDA_BASE
from components.base_tecnica_ui import base_ativa, gravar_campos_do_projeto, mapa_do_projeto
from components.cargas_esqueleto_help import AJUDA
from components.cena_3d_svg import svg_guardado
from components.figuras import mostrar_figura
from components.figuras_estrutura import svg_planta_do_esqueleto
from components.guarda_corpo_ui import mostrar_guarda_corpo_do_modelo
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import cargas_esqueleto as ce
from core import cargas_pelo_modelo as cpm
from core import cena_3d as c3
from core import cena_do_piso as cp
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import piso_do_modelo as pm
from core import plano_de_cargas as pc
from core import section_catalog
from core import tratamento_do_modelo as tm
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
        "Nenhum projeto ativo. Abra ou crie um em **Projetos**: as cargas ficam "
        "guardadas no projeto e vão para o plano de cargas dele.",
        icon=":material/folder_off:",
    )
    st.stop()

base = base_ativa()
versao = int(st.session_state.get("ce_versao", 0))


def _pt(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _recarregar(confirmacao: str = "") -> None:
    """Recarrega a página; com ``confirmacao``, ela aparece na volta (o rerun apagaria o aviso)."""
    st.session_state["ce_versao"] = versao + 1
    if confirmacao:
        st.session_state[CHAVE_CONFIRMACAO] = confirmacao
    st.rerun()


CHAVE_CONFIRMACAO = "ce_enviado"


def _mostrar_confirmacao() -> None:
    """O aviso do envio que acabou de gravar, com o caminho para o plano de cargas."""
    texto = st.session_state.pop(CHAVE_CONFIRMACAO, "")
    if not texto:
        return
    st.toast(texto, icon=":material/check_circle:")
    st.success(texto, icon=":material/check_circle:")
    st.page_link(
        "app_pages/plano_cargas.py",
        label="Abrir o Plano de cargas",
        icon=":material/table_chart:",
        help=AJUDA["btn_abrir_plano"],
    )


# ============================================================ o esqueleto do modelo
def _enviar_esqueleto(rotulo: str) -> None:
    enviado = st.file_uploader(
        rotulo,
        type=["csv"],
        key=f"ce_esqueleto_{versao}",
        help=AJUDA["arquivo_esqueleto"],
    )
    if enviado is None:
        return
    try:
        novo_esqueleto = ld.ler_esqueleto(enviado.getvalue(), enviado.name)
    except ld.GeometriaInvalida as erro:
        st.error(f"{enviado.name}: {erro}", icon=":material/error:")
        return
    st.success(
        f"{novo_esqueleto.arquivo}: {len(novo_esqueleto.corpos)} corpos"
        + (f" ({novo_esqueleto.origem})" if novo_esqueleto.origem else "")
        + ".",
        icon=":material/account_tree:",
    )
    for aviso in novo_esqueleto.avisos:
        st.warning(aviso, icon=":material/warning:")
    if st.button(
        "Gravar o esqueleto no projeto",
        type="primary",
        icon=":material/save:",
        key="ce_gravar_esqueleto",
        help=AJUDA["btn_gravar_esqueleto"],
    ) and gravar_campos_do_projeto(
        {"geometria_do_modelo": ld.para_dicionario(novo_esqueleto)},
        "Esqueleto do modelo gravado",
    ):
        _recarregar()


geometria = ld.geometria_do_projeto(projeto)
esforcos = tm.do_projeto(projeto).dados
eixo = esforcos.eixo_vertical
leitura = pm.ler(geometria, eixo) if geometria.corpos else None

with st.container(border=True), secao_protegida("Esqueleto do modelo"):
    st.subheader("Esqueleto do modelo", help=AJUDA["sec_modelo"])
    if not geometria.corpos:
        _enviar_esqueleto("Esqueleto do modelo (…_esqueleto.csv da macro)")
        st.caption(
            ":material/account_tree: Sem o esqueleto do modelo ainda. Rode a macro do SolidWorks e "
            "envie o …_esqueleto.csv aqui: o programa lê as chapas de piso, as escadas e as vigas "
            "e monta as cargas sozinho. Sem o modelo, use a grade de eixos, abaixo."
        )
        st.download_button(
            "Macro do SolidWorks",
            data=lm.macro_da_lista_de_corte(),
            file_name="exportar_lista_de_corte.bas",
            mime="text/plain",
            icon=":material/code:",
            key="ce_macro",
            help=AJUDA["btn_macro_modelo"],
        )
    else:
        st.caption(
            f":material/account_tree: {geometria.arquivo}"
            + (f" — {geometria.origem}" if geometria.origem else "")
        )
        with st.expander("Trocar o esqueleto (o modelo mudou no SolidWorks)"):
            _enviar_esqueleto("Novo …_esqueleto.csv da macro")

pelo_modelo = leitura is not None


# ============================================================ pelo modelo
COLUNAS_DAS_CHAPAS = (
    "Chapa",
    "Corpo no SolidWorks",
    "Tipo",
    "Onde",
    "Área (m²)",
    "SC (kN/m²)",
    "Peso informado (kN/m²)",
    "Peso pelo volume (kN/m²)",
    "Apoio",
    "Vigas embaixo",
    "Por quê",
)


@st.fragment
def _conferir_em_3d(
    leitura: pm.LeituraDoPiso,
    escolha: pm.EscolhaDoPiso,
    distribuicao: cpm.DistribuicaoDoPiso,
) -> None:
    """A vista 3D num fragmento: mudar a vista ou a cor não refaz o resto da página."""
    colunas = st.columns([3, 2, 2])
    cor_por = (
        colunas[0].segmented_control(
            "Mostrar",
            list(cp.CORES),
            default=cp.COR_POR_PAPEL,
            key="ce_3d_cor",
            help=AJUDA["cor_3d"],
        )
        or cp.COR_POR_PAPEL
    )
    vista = colunas[1].selectbox(
        "Vista", list(c3.VISTAS), key="ce_3d_vista", help=AJUDA["vista_3d"]
    )
    giro = colunas[2].slider("Girar (°)", -180, 180, 0, 15, key="ce_3d_giro", help=AJUDA["giro_3d"])
    caso = ""
    if cor_por == cp.COR_POR_CARGA:
        if not distribuicao.casos:
            st.info("Nenhuma chapa com carga ainda.", icon=":material/info:")
            return
        caso = str(
            st.selectbox("Caso", list(distribuicao.casos), key="ce_3d_caso", help=AJUDA["caso_3d"])
        )
    with section_catalog.catalogo_estavel():
        cena = cp.cena_do_piso(
            geometria, eixo, leitura, escolha, distribuicao, cor_por=str(cor_por), caso=caso
        )
    azimute, elevacao = c3.VISTAS[str(vista)]
    mostrar_figura(svg_guardado(cena, azimute + float(giro), elevacao))
    st.caption(
        "Confira: cada chapa com o tipo certo (piso, patamar, escada), as vigas que recebem piso "
        "em laranja e nenhuma viga de piso esquecida em cinza. Em “Área que cada viga recebe”, "
        "a cor da faixa é a da viga para onde ela vai."
    )


def _pelo_modelo(leitura: pm.LeituraDoPiso) -> None:
    plano = pc.plano_do_projeto(projeto)
    nomes_no_simulation = {
        corpo.nome: barra
        for barra, corpo in ld.correspondencia(
            geometria, esforcos.nomes_dos_membros, esforcos
        ).corpos.items()
    }
    da_grade = ce.entrada_do_projeto(projeto)
    conta_as_chapas = pm.pp_conta_as_chapas(geometria, esforcos, plano)
    sc_do_piso = cpm.cargas_por_area_do_plano(plano).get("SC") or (
        float(base.sobrecarga_kN_m2) if base else 5.0
    )
    inicial = pm.escolha_inicial(
        leitura,
        pm.escolha_do_projeto(projeto),
        sc_do_piso=sc_do_piso,
        sc_da_escada=pm.sobrecarga_da_escada(bool(base and base.anglo), sc_do_piso),
        peso=pm.PESO_NO_PP if conta_as_chapas else pm.PESO_PELO_VOLUME,
        acrescimo_ligacoes_pct=da_grade.acrescimo_ligacoes_pct if da_grade else 7.0,
        temperatura=da_grade.temperatura if da_grade else bool(base and base.anglo),
    )

    # -------------------------------------------------------- 1. o que o programa entendeu
    with st.container(border=True), secao_protegida("1. O que o programa entendeu do modelo"):
        st.subheader("1. O que o programa entendeu do modelo", help=AJUDA["sec_entendeu"])
        barras = dict(leitura.barras)
        com_piso = len(leitura.vigas_com_piso)
        colunas = st.columns(5)
        colunas[0].metric("Pilares", barras.get(ld.TIPO_PILAR, 0), help=AJUDA["res_barras_modelo"])
        colunas[1].metric(
            "Vigas",
            barras.get(ld.TIPO_VIGA, 0),
            f"{com_piso} barras com piso",
            delta_color="off",
            delta_arrow="off",
            help=AJUDA["res_barras_modelo"],
        )
        colunas[2].metric(
            "Diagonais e longarinas",
            barras.get(ld.TIPO_CONTRAVENTAMENTO, 0) + barras.get(pm.PAPEL_LONGARINA, 0),
            f"{barras.get(pm.PAPEL_LONGARINA, 0)} longarinas",
            delta_color="off",
            delta_arrow="off",
            help=AJUDA["res_barras_modelo"],
        )
        colunas[3].metric(
            "Níveis de piso",
            len(leitura.niveis),
            " · ".join(f"+{_pt(n)} m" for n in leitura.niveis) or "—",
            delta_color="off",
            delta_arrow="off",
            help=AJUDA["res_niveis"],
        )
        colunas[4].metric(
            "Chapas de piso",
            len(leitura.chapas),
            f"{_pt(sum(c.area_projetada_m2 for c in leitura.chapas))} m²",
            delta_color="off",
            delta_arrow="off",
            help=AJUDA["res_niveis"],
        )
        for aviso in leitura.avisos:
            st.warning(aviso, icon=":material/warning:")

        if not leitura.chapas:
            st.info(
                "O esqueleto não tem chapa de piso (forma CHAPA, até 60° com a horizontal) que dê "
                "para distribuir: modele as chapas no SolidWorks ou use a grade de eixos, no fim "
                "da página. O guarda-corpo e o desenho 3D seguem pelo esqueleto.",
                icon=":material/info:",
            )
            for fora in leitura.fora:
                st.caption(f":material/info: {fora.nome}: {fora.motivo}.")
        st.caption("Carga de cada chapa", help=AJUDA["res_chapas"])
        linhas = []
        for chapa in leitura.chapas:
            da_chapa = inicial.da_chapa(chapa.nome)
            linhas.append(
                {
                    "Chapa": chapa.codigo,
                    "Corpo no SolidWorks": chapa.nome,
                    "Tipo": da_chapa.tipo,
                    "Onde": (
                        f"lance a {_pt(chapa.inclinacao_graus, 0)}°"
                        if chapa.nivel == 0
                        else f"nível {chapa.nivel} · +{_pt(chapa.cota_m)} m"
                    ),
                    "Área (m²)": chapa.area_m2,
                    "SC (kN/m²)": da_chapa.sc_kN_m2,
                    "Peso informado (kN/m²)": da_chapa.pe_kN_m2,
                    "Peso pelo volume (kN/m²)": chapa.peso_kN_m2,
                    "Apoio": da_chapa.sentido,
                    "Vigas embaixo": len(chapa.vigas),
                    "Por quê": chapa.motivo,
                }
            )
        tabela = st.data_editor(
            pd.DataFrame(linhas, columns=list(COLUNAS_DAS_CHAPAS)),
            hide_index=True,
            width="stretch",
            key=f"ce_chapas_{versao}",
            disabled=[
                "Chapa",
                "Corpo no SolidWorks",
                "Onde",
                "Área (m²)",
                "Peso pelo volume (kN/m²)",
                "Vigas embaixo",
                "Por quê",
            ],
            column_config={
                "Tipo": st.column_config.SelectboxColumn(options=list(pm.TIPOS), required=True),
                "Área (m²)": st.column_config.NumberColumn(format="%.2f"),
                "SC (kN/m²)": st.column_config.NumberColumn(
                    min_value=0.0, max_value=100.0, format="%.2f", required=True
                ),
                "Peso informado (kN/m²)": st.column_config.NumberColumn(
                    min_value=0.0, max_value=100.0, format="%.2f", required=True
                ),
                "Peso pelo volume (kN/m²)": st.column_config.NumberColumn(format="%.2f"),
                "Apoio": st.column_config.SelectboxColumn(
                    options=list(cpm.SENTIDOS), required=True
                ),
            },
        )
        chapas: dict[str, pm.EscolhaDaChapa] = {}
        for linha in tabela.to_dict("records"):
            nome = str(linha["Corpo no SolidWorks"])
            antes = inicial.da_chapa(nome)

            def numero(valor: Any, padrao: float) -> float:
                return padrao if valor is None or pd.isna(valor) else float(valor)

            tipo, sentido = str(linha.get("Tipo") or ""), str(linha.get("Apoio") or "")
            chapas[nome] = pm.EscolhaDaChapa(
                tipo=tipo if tipo in pm.TIPOS else antes.tipo,
                sc_kN_m2=numero(linha.get("SC (kN/m²)"), antes.sc_kN_m2),
                pe_kN_m2=numero(linha.get("Peso informado (kN/m²)"), antes.pe_kN_m2),
                sentido=sentido if sentido in cpm.SENTIDOS else antes.sentido,
            )

        colunas = st.columns([3, 2, 2])
        peso = colunas[0].selectbox(
            "Peso do piso (PE)",
            list(pm.PESOS),
            index=pm.PESOS.index(inicial.peso),
            key=f"ce_peso_{versao}",
            help=AJUDA["peso_do_piso"],
        )
        acrescimo = colunas[1].number_input(
            "Ligações, chapas e parafusos (%)",
            0.0,
            30.0,
            float(inicial.acrescimo_ligacoes_pct),
            0.5,
            format="%.1f",
            key=f"ce_m_acrescimo_{versao}",
            help=AJUDA["acrescimo"],
        )
        temperatura = colunas[2].toggle(
            "Temperatura ±10 °C",
            value=inicial.temperatura,
            key=f"ce_m_temperatura_{versao}",
            help=AJUDA["temperatura"],
        )
        if conta_as_chapas is True:
            st.caption(
                ":material/check_circle: O PP importado do estudo já conta o peso das chapas (a "
                "reação do PP bate com o aço de todos os corpos): o peso do piso não entra de novo "
                "no PE."
            )
        elif conta_as_chapas is False:
            st.caption(
                ":material/info: O PP importado do estudo não conta as chapas (a reação do PP bate "
                "só com o aço das barras): o peso delas vai no PE, pelo volume."
            )
        else:
            st.caption(
                ":material/help: Não deu para saber, pelos resultados importados, se o PP do "
                "estudo já conta as chapas. Se as chapas entram na gravidade do seu estudo, "
                "escolha “Já está no peso próprio do estudo (PP)” para não somar duas vezes."
            )
        so_no_trecho = st.toggle(
            "Carga só no trecho sob a chapa (viga coberta em parte)",
            value=inicial.so_no_trecho,
            key=f"ce_trecho_{versao}",
            help=AJUDA["so_no_trecho"],
        )
        with st.expander("Outros casos por área", expanded=bool(inicial.outros)):
            st.caption(
                "Um caso a mais em kN/m² (projeção horizontal), em todas as chapas com carga.",
                help=AJUDA["outros_casos"],
            )
            tabela_outros = st.data_editor(
                pd.DataFrame(
                    [{"Caso": c, "kN/m²": v} for c, v in inicial.outros],
                    columns=["Caso", "kN/m²"],
                ),
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                key=f"ce_outros_{versao}",
                column_config={
                    "Caso": st.column_config.SelectboxColumn(
                        options=[
                            c
                            for c in dict.fromkeys(
                                [*plano.codigos, *(c.codigo for c in pc.CODIGOS)]
                            )
                            if c not in ("PP", "PE", "SC", "T+", "T−")
                        ]
                    ),
                    "kN/m²": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                },
            )
        outros = tuple(
            (str(linha["Caso"]), float(linha["kN/m²"]))
            for linha in tabela_outros.to_dict("records")
            if linha.get("Caso") and not pd.isna(linha.get("kN/m²")) and linha.get("kN/m²")
        )

    com_grade_no_plano = cpm.cargas_da_grade_no_plano(plano)
    escolha = pm.EscolhaDoPiso(
        chapas=chapas,
        peso=str(peso),
        so_no_trecho=bool(so_no_trecho),
        outros=outros,
        acrescimo_ligacoes_pct=float(acrescimo),
        temperatura=bool(temperatura),
        tirar_a_grade=bool(st.session_state.get(f"ce_tirar_{versao}", inicial.tirar_a_grade)),
    )
    problemas = pm.validar(escolha)
    for problema in problemas:
        st.error(problema, icon=":material/error:")
    if problemas:
        return
    distribuicao = pm.distribuir(geometria, leitura, escolha)

    # -------------------------------------------------------- 2. conferir em 3D
    with st.container(border=True), secao_protegida("2. Conferir em 3D"):
        st.subheader("2. Conferir em 3D", help=AJUDA["sec_3d"])
        _conferir_em_3d(leitura, escolha, distribuicao)

    # -------------------------------------------------------- 3. guarda-corpo
    guarda_corpo = mostrar_guarda_corpo_do_modelo(
        projeto,
        geometria,
        eixo,
        nomes_no_simulation,
        titulo="3. Guarda-corpo nas bordas do piso",
    )

    # -------------------------------------------------------- 4. cargas nas vigas
    with st.container(border=True), secao_protegida("4. Cargas nas vigas"):
        st.subheader("4. Cargas nas vigas", help=AJUDA["sec_vigas"])
        for aviso in distribuicao.avisos:
            st.warning(aviso, icon=":material/warning:")
        if not distribuicao.cargas:
            st.caption(
                ":material/info: Nenhuma chapa com carga: o envio leva só o guarda-corpo, as "
                "ligações e a temperatura."
            )
        else:
            colunas = st.columns(2 + len(distribuicao.casos))
            colunas[0].metric(
                "Área carregada",
                f"{_pt(distribuicao.area_distribuida_m2)} m²",
                help=AJUDA["res_modelo"],
            )
            colunas[1].metric(
                "Vigas carregadas",
                len({c.viga for c in distribuicao.cargas}),
                help=AJUDA["res_modelo"],
            )
            for coluna, caso in zip(colunas[2:], distribuicao.casos, strict=False):
                coluna.metric(
                    f"{caso} no piso",
                    f"{_pt(distribuicao.total(caso), 1)} kN",
                    help=AJUDA["res_modelo"],
                )
            caso_do_piso = st.selectbox(
                "Caso", list(distribuicao.casos), key="ce_modelo_caso", help=AJUDA["caso_modelo"]
            )
            st.caption(f"Cargas nas vigas — {caso_do_piso}", help=AJUDA["res_vigas_modelo"])
            st.dataframe(
                pd.DataFrame(pm.linhas_das_vigas(distribuicao, caso_do_piso, nomes_no_simulation)),
                hide_index=True,
                width="stretch",
                column_config={
                    "kN/m": st.column_config.NumberColumn(format="%.3f"),
                    "Total (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "Trecho sob a chapa (m)": st.column_config.NumberColumn(format="%.2f"),
                    "Comprimento (m)": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            st.caption("Conferência", help=AJUDA["res_conferencia_modelo"])
            st.dataframe(
                pd.DataFrame(pm.conferencia(leitura, escolha, distribuicao)),
                hide_index=True,
                width="stretch",
                column_config={
                    "Das chapas (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "Nas vigas (kN)": st.column_config.NumberColumn(format="%.2f"),
                },
            )

    # -------------------------------------------------------- 5. enviar
    with st.container(border=True), secao_protegida("5. Enviar ao plano de cargas"):
        st.subheader("5. Enviar ao plano de cargas", help=AJUDA["sec_enviar_tudo"])
        _mostrar_confirmacao()
        if com_grade_no_plano:
            total_da_grade = sum(abs(c.resultante or 0.0) for _, c in com_grade_no_plano)
            st.toggle(
                f"Tirar do plano as {len(com_grade_no_plano)} linha(s) da grade de eixos "
                f"({_pt(total_da_grade)} kN em barras que o modelo não tem)",
                value=inicial.tirar_a_grade,
                key=f"ce_tirar_{versao}",
                help=AJUDA["tirar_grade"],
            )
        depois = pm.aplicar_no_plano(plano, leitura, escolha, distribuicao, nomes_no_simulation)
        if guarda_corpo is not None:
            depois = guarda_corpo.no_plano(depois)
        mudancas = pm.comparar(plano, depois, nomes_no_simulation)
        if mudancas:
            st.caption("O que muda no plano de cargas", help=AJUDA["res_muda"])
            st.dataframe(
                pd.DataFrame(mudancas),
                hide_index=True,
                width="stretch",
                column_config={
                    "Antes (kN)": st.column_config.NumberColumn(format="%.2f"),
                    "Depois (kN)": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        else:
            st.caption(
                ":material/check_circle: O plano de cargas já está com estas cargas: não há o "
                "que enviar."
            )
        campos: dict[str, Any] = {pm.CHAVE_DO_PROJETO: pm.para_dicionario(escolha)}
        if guarda_corpo is not None:
            campos[gm.CHAVE_DO_PROJETO] = guarda_corpo.dados
        colunas = st.columns(3)
        if colunas[0].button(
            "Gravar e enviar tudo ao plano",
            type="primary",
            icon=":material/send:",
            key="ce_enviar_tudo",
            help=AJUDA["btn_enviar_tudo"],
            width="stretch",
        ) and gravar_campos_do_projeto(
            {**campos, "plano_de_cargas": pc.para_dicionario(depois)},
            "Cargas do esqueleto pelo modelo enviadas ao plano de cargas",
        ):
            _recarregar(pm.resumo_do_envio(mudancas))
        if colunas[1].button(
            "Gravar só as escolhas",
            icon=":material/save:",
            key="ce_gravar_escolhas",
            help=AJUDA["btn_gravar_escolhas"],
            width="stretch",
        ) and gravar_campos_do_projeto(campos, "Cargas do esqueleto: escolhas gravadas"):
            _recarregar(
                "Escolhas gravadas no projeto. O plano de cargas não mudou: use “Gravar e enviar "
                "tudo ao plano” para levar as cargas."
            )
        colunas[2].download_button(
            "Cargas nas vigas (CSV)",
            data=pm.csv_das_cargas(distribuicao, nomes_no_simulation),
            file_name=f"cargas_do_piso_{projeto.get('codigo') or 'projeto'}.csv",
            mime="text/csv",
            icon=":material/download:",
            key="ce_modelo_csv",
            help=AJUDA["btn_csv_modelo"],
            width="stretch",
        )
        st.caption(
            ":material/info: Equipamentos, tubulações e outras cargas pontuais entram direto no "
            "Plano de cargas, na viga do modelo: este envio não mexe nelas."
        )


# ============================================================ pela grade de eixos
def _pela_grade() -> None:
    salva = ce.entrada_do_projeto(projeto)
    inicial = salva or ce.EntradaEsqueleto(
        niveis=(ce.Nivel(sobrecarga_kN_m2=float(base.sobrecarga_kN_m2) if base else 5.0),),
        temperatura=bool(base and base.anglo),
    )
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
                "Trecho": st.column_config.NumberColumn(
                    min_value=1, step=1, format="%d", default=1
                ),
                "Largura (m)": st.column_config.NumberColumn(
                    min_value=0.0, format="%.2f", default=0.8
                ),
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
            pd.DataFrame(
                ce.tabela_dos_equipamentos(inicial), columns=list(ce.COLUNAS_EQUIPAMENTOS)
            ),
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
                "Apoios": st.column_config.NumberColumn(
                    min_value=1, step=1, format="%d", default=4
                ),
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
                "Caso": st.column_config.SelectboxColumn(
                    options=list(ce.CASOS_DE_LINHA), default="PE"
                ),
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
        mostrar_figura(svg_planta_do_esqueleto(resultado, int(nivel), caso_escolhido))
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
        # Com o esqueleto no projeto, a grade só vale se for a mesma planta (correto acima do
        # jeito: a grade de exemplo mandava 24 vezes a sobrecarga de uma plataforma pequena).
        grade_diferente = ""
        if geometria.corpos:
            grade_diferente = cpm.grade_confere_com_o_modelo(
                entrada.area_planta_m2,
                len(entrada.niveis),
                cpm.chapas_do_piso(geometria, esforcos.eixo_vertical)[0],
            )
        if grade_diferente:
            st.error(grade_diferente, icon=":material/block:")
        da_grade = cpm.cargas_da_grade_no_plano(plano) if geometria.corpos else []
        if da_grade:
            casos_da_grade = sorted({codigo for codigo, _ in da_grade})
            total_da_grade = sum(abs(c.resultante or 0.0) for _, c in da_grade)
            texto_total = f"{total_da_grade:.2f}".replace(".", ",")
            st.warning(
                f"O plano de cargas ainda tem {len(da_grade)} linha(s) da grade de eixos em "
                f"{', '.join(casos_da_grade)} ({texto_total} kN), em barras que o esqueleto "
                'do modelo não tem ("N1 · eixo A…"): sobra de um envio antigo, carga que o modelo '
                "não recebe.",
                icon=":material/warning:",
            )
            if st.button(
                "Tirar do plano as cargas da grade",
                icon=":material/delete_sweep:",
                key="ce_tirar_grade",
                help=AJUDA["btn_tirar_grade"],
            ) and gravar_campos_do_projeto(
                {"plano_de_cargas": pc.para_dicionario(cpm.sem_cargas_da_grade(plano))},
                "Cargas da grade de eixos tiradas do plano de cargas",
            ):
                st.session_state["ce_versao"] = versao + 1
                st.rerun()
        if not pelo_modelo:
            _mostrar_confirmacao()  # pelo modelo, a seção 5 já mostrou
        colunas = st.columns(3)
        novo_plano = ce.aplicar_no_plano(resultado, plano)
        if colunas[0].button(
            "Gravar e enviar ao plano",
            type="primary",
            icon=":material/send:",
            key="ce_enviar",
            help=AJUDA["btn_enviar"],
            width="stretch",
            disabled=bool(grade_diferente),
        ) and gravar_campos_do_projeto(
            {
                "cargas_do_esqueleto": ce.para_dicionario(entrada),
                "plano_de_cargas": pc.para_dicionario(novo_plano),
            },
            "Cargas do esqueleto enviadas ao plano de cargas",
        ):
            _recarregar(pm.resumo_do_envio(pm.comparar(plano, novo_plano)))
        if colunas[1].button(
            "Gravar só os dados",
            icon=":material/save:",
            key="ce_gravar",
            help=AJUDA["btn_gravar"],
            width="stretch",
        ) and gravar_campos_do_projeto(
            {"cargas_do_esqueleto": ce.para_dicionario(entrada)}, "Cargas do esqueleto gravadas"
        ):
            _recarregar(
                "Dados gravados no projeto. O plano de cargas não mudou: use “Gravar e enviar ao "
                "plano” para levar as cargas."
            )
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


if pelo_modelo and leitura is not None:
    _pelo_modelo(leitura)
    usar_a_grade = st.toggle(
        "Usar também a grade de eixos (a forma sem o modelo)",
        value=not leitura.chapas,
        key="ce_usar_grade",
        help=AJUDA["usar_grade"],
    )
else:
    usar_a_grade = True
if usar_a_grade:
    _pela_grade()
