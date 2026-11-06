"""Sensores do modelo: o quadro da Vista de resultados do gerenciador de casos de carga do
SolidWorks lido, conferido contra o plano de cargas e verificado para o memorial."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from components.base_tecnica_ui import gravar_campo_do_projeto
from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.sensores_do_modelo_help import AJUDA
from components.ui import cabecalho_pagina, configurar_pagina
from components.verification_table import mostrar_verificacoes_resumidas, texto_markdown
from core import desenho_dos_sensores as dds
from core import lista_de_material as lm
from core import plano_de_cargas as pc
from core import sensores_do_modelo as sm
from core import sensores_recomendados as sr
from core.project_store import obter_projeto_ativo

configurar_pagina("Sensores do modelo", ":material/sensors:")
cabecalho_pagina(
    "Sensores do modelo",
    "O quadro dos sensores do gerenciador de casos de carga do SolidWorks (tensão, deslocamento, "
    "fator de segurança…) conferido contra o plano de cargas e verificado para o memorial.",
    categoria="Modelo SolidWorks",
    icone=":material/sensors:",
    cor="blue",
    acoes=(("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),),
)
projeto = obter_projeto_ativo()
guardado = sm.quadro_do_projeto(projeto)
plano = pc.plano_do_projeto(projeto) if projeto is not None else None
ICONES = {
    sm.NIVEL_ERRO: ":material/error:",
    sm.NIVEL_ATENCAO: ":material/warning:",
    sm.NIVEL_OK: ":material/check_circle:",
    sm.NIVEL_INFO: ":material/info:",
}
MOSTRAR = {sm.NIVEL_ERRO: st.error, sm.NIVEL_ATENCAO: st.warning, sm.NIVEL_INFO: st.info}
CORES_DO_NIVEL = {
    sr.MINIMO: "red",
    sr.RECOMENDADO: "blue",
    sr.SE_HOUVER: "orange",
    sr.NAO_PRECISA: "gray",
    sr.E_ESTE: "green",
}


def _selo(nivel: str) -> str:
    return f":{CORES_DO_NIVEL.get(nivel, 'gray')}-badge[{texto_markdown(nivel)}]"


def _mostrar_recomendados(estudo: str) -> None:
    for r in sr.recomendados(estudo):
        condicao = f" — {r.condicao}" if r.condicao else ""
        onde = " · ".join(
            x
            for x in (
                f"critério: {r.criterio}" if r.criterio != "—" else "",
                f"onde: {r.onde}",
                f"unidade: {r.unidade}" if r.unidade != "—" else "",
            )
            if x
        )
        partes = [
            f"{_selo(r.nivel)} **{texto_markdown(r.titulo)}**{texto_markdown(condicao)}",
            f"Nome no SolidWorks: **{texto_markdown(r.nome)}** · {texto_markdown(r.caminho)}",
            texto_markdown(onde[:1].upper() + onde[1:]),
        ]
        if r.alerta != "—":
            partes.append(f"Alerta do sensor: {texto_markdown(r.alerta)}")
        partes.append(f":gray[{texto_markdown(r.para_que)}]")
        st.markdown("  \n".join(partes))


def _assinatura(q: sm.QuadroDeSensores) -> str:
    """Muda com o conteúdo do quadro (não com a hora da leitura): as escolhas da seção 2 ficam."""
    texto = f"{q.arquivo}|{q.estudo}|{[s.nome for s in q.sensores]}|{q.linhas}"
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]


# ============================================================ os sensores de cada estudo
with (
    st.expander(
        "Sensores mínimos de cada estudo (o que criar no SolidWorks)",
        icon=":material/checklist:",
        expanded=guardado.vazio,
    ),
    secao_protegida("Sensores mínimos de cada estudo"),
):
    abas = st.tabs(["Estático", "Flambagem", "Frequência", "As opções do SolidWorks"])
    with abas[0]:
        st.caption(
            "O estudo com o gerenciador de casos de carga: é ele que vira o quadro desta página. "
            "Use os nomes sugeridos (o programa reconhece o que cada sensor mede) e ligue o Alerta "
            "do sensor com o valor indicado: o SolidWorks avisa na árvore quando passar."
        )
        _mostrar_recomendados(sr.ESTATICO)
    with abas[1]:
        st.caption(
            "Um estudo de flambagem à parte, com as cargas da combinação ELU que governa. O "
            "gerenciador de casos de carga é só do estático: este valor não vem no quadro."
        )
        _mostrar_recomendados(sr.FLAMBAGEM)
    with abas[2]:
        st.caption(
            "Um estudo de frequência à parte. O gerenciador de casos de carga é só do estático: "
            "estes valores não vêm no quadro."
        )
        _mostrar_recomendados(sr.FREQUENCIA)
    with abas[3]:
        for grupo in (sr.TIPO_DE_SENSOR, sr.QUANTIDADE_DE_DADOS):
            st.markdown(f"**{grupo}**")
            st.markdown(
                "\n".join(
                    f"- {_selo(o.uso)} **{texto_markdown(o.nome)}** — {texto_markdown(o.porque)}"
                    for o in sr.OPCOES_DO_SOLIDWORKS
                    if o.grupo == grupo
                )
            )

# ============================================================ 1. o quadro
quadro = guardado
with st.container(border=True), secao_protegida("1. O quadro dos sensores"):
    st.subheader("1. O quadro dos sensores", help=AJUDA["sec_quadro"])
    if projeto is None:
        st.info(
            "Nenhum projeto ativo: o quadro é lido e verificado, mas sem o plano de cargas (as "
            "combinações não são conferidas) e sem registrar no memorial. Abra um projeto em "
            "**Projetos permanentes**.",
            icon=":material/folder_off:",
        )
    enviado = st.file_uploader(
        "Quadro dos sensores (<estudo>-gerenciador-resultados.csv)",
        type=["csv", "txt"],
        key="sm_arquivo",
        help=AJUDA["arquivo"],
    )
    if enviado is not None:
        try:
            lido = sm.ler_quadro(enviado.getvalue(), enviado.name)
        except sm.QuadroInvalido as erro:
            st.error(f"{enviado.name}: {erro}", icon=":material/error:")
        else:
            quadro = sm.manter_ajustes(lido, guardado)
    if quadro.vazio:
        st.caption(
            "Nenhum quadro ainda. No SolidWorks, rode o gerenciador de casos de carga (Executar) e "
            "a macro exportar_casos_de_carga (baixe-a em Esforços do modelo): ela grava o "
            "…-gerenciador-resultados.csv com todos os sensores da Vista de resultados."
        )
        st.page_link(
            "app_pages/esforcos_modelo.py",
            label="Esforços do modelo (macro e os outros arquivos)",
            icon=":material/upload_file:",
        )
        st.stop()
    origem = "enviado agora" if quadro is not guardado else "gravado no projeto"
    st.caption(
        f"Estudo **{texto_markdown(quadro.estudo or '—')}** · arquivo "
        f"{texto_markdown(quadro.arquivo or '—')} · lido em {quadro.lido_em or '—'} ({origem})"
    )

# ============================================================ 2. o que cada sensor mede
with st.container(border=True), secao_protegida("2. O que cada sensor mede"):
    st.subheader("2. O que cada sensor mede", help=AJUDA["sec_sensores"])
    assinatura = _assinatura(quadro)
    editado = st.data_editor(
        pd.DataFrame(
            [
                {
                    "Sensor": s.nome,
                    "O que mede": sm.ROTULOS_GRANDEZA.get(s.grandeza, s.grandeza),
                    "Unidade no SolidWorks": s.unidade,
                }
                for s in quadro.sensores
            ]
        ),
        hide_index=True,
        width="stretch",
        disabled=["Sensor"],
        key=f"sm_sensores_{assinatura}",
        column_config={
            "O que mede": st.column_config.SelectboxColumn(
                options=list(sm.ROTULOS_GRANDEZA.values()), required=True, help=AJUDA["col_mede"]
            ),
            "Unidade no SolidWorks": st.column_config.SelectboxColumn(
                options=list(sm.TODAS_AS_UNIDADES), required=True, help=AJUDA["col_unidade"]
            ),
        },
    )
    sensores: list[sm.Sensor] = []
    for s, (_, linha) in zip(quadro.sensores, editado.iterrows(), strict=False):
        grandeza = sm.GRANDEZA_DO_ROTULO.get(str(linha["O que mede"]), s.grandeza)
        unidade = str(linha["Unidade no SolidWorks"])
        if unidade not in sm.UNIDADES[grandeza]:
            padrao = sm.unidade_padrao(grandeza)
            st.warning(
                f"{texto_markdown(s.nome)}: {unidade} não é unidade de {grandeza} — ficou {padrao}. "
                "Escolha na coluna Unidade uma que sirva.",
                icon=":material/warning:",
            )
            unidade = padrao
        sensores.append(sm.Sensor(s.nome, grandeza, unidade, s.limite))

    k_fs = any(s.grandeza == sm.FATOR_DE_SEGURANCA for s in sensores)
    k_tensao = any(s.grandeza == sm.TENSAO for s in sensores)
    fy_informado: float | None = quadro.fy_MPa
    if k_tensao:
        colunas = st.columns(2)
        automatico = colunas[0].toggle(
            "f_y pelo fator de segurança do SolidWorks",
            value=quadro.fy_MPa is None and k_fs,
            key=f"sm_fy_auto_{assinatura}",
            help=AJUDA["fy_automatico"],
            disabled=not k_fs,
        )
        if automatico:
            fy_informado = None
        else:
            fy_informado = colunas[1].number_input(
                "f_y do aço (MPa)",
                min_value=100.0,
                max_value=1500.0,
                value=float(quadro.fy_MPa or 250.0),
                step=5.0,
                key=f"sm_fy_{assinatura}",
                help=AJUDA["fy"],
            )

    for k, s in enumerate(sensores):
        if s.grandeza != sm.DESLOCAMENTO:
            continue
        st.markdown(f"**Limite do deslocamento — {texto_markdown(s.nome)}**")
        colunas = st.columns([3, 1, 1])
        opcoes = list(sm.OPCOES_DE_LIMITE)
        opcao = colunas[0].selectbox(
            f"Limite de {s.nome}",
            opcoes,
            index=opcoes.index(s.limite.opcao) if s.limite.opcao in opcoes else 0,
            key=f"sm_lim_{assinatura}_{k}",
            help=AJUDA["limite"],
        )
        comprimento, divisor, maximo = s.limite.comprimento_m, s.limite.divisor, s.limite.maximo_mm
        base = sm.LimiteDoDeslocamento(opcao).base
        if opcao in sm.LIMITES_ANGLO or opcao == sm.L_SOBRE_X:
            comprimento = colunas[1].number_input(
                f"{base} (m)",
                min_value=0.0,
                max_value=500.0,
                value=float(s.limite.comprimento_m or 0.0),
                step=0.1,
                key=f"sm_comp_{assinatura}_{k}",
                help=AJUDA["comprimento"],
            )
        if opcao == sm.L_SOBRE_X:
            divisor = colunas[2].number_input(
                "x de L/x",
                min_value=1.0,
                max_value=5000.0,
                value=float(s.limite.divisor or 350.0),
                step=50.0,
                key=f"sm_div_{assinatura}_{k}",
                help=AJUDA["divisor"],
            )
        if opcao == sm.EM_MM:
            maximo = colunas[1].number_input(
                "Limite (mm)",
                min_value=0.0,
                max_value=10000.0,
                value=float(s.limite.maximo_mm or 0.0),
                step=1.0,
                key=f"sm_max_{assinatura}_{k}",
                help=AJUDA["maximo_mm"],
            )
        limite = sm.LimiteDoDeslocamento(opcao, comprimento or None, divisor, maximo or None)
        sensores[k] = sm.Sensor(s.nome, s.grandeza, s.unidade, limite)
        if limite.falta():
            st.caption(f":material/edit: Falta {limite.falta()} para verificar este deslocamento.")
        elif limite.limite_mm() is not None:
            st.caption(f"Limite: {texto_markdown(limite.texto())}")

    quadro = sm.com_ajustes(quadro, sensores, fy_MPa=fy_informado)
    mudou = sm.para_dicionario(quadro) != sm.para_dicionario(guardado)
    if (
        projeto is not None
        and mudou
        and st.button(
            "Gravar no projeto",
            type="primary",
            icon=":material/save:",
            key="sm_gravar",
            help=AJUDA["btn_gravar"],
        )
    ):
        if gravar_campo_do_projeto(
            sm.CAMPO_DO_PROJETO, sm.para_dicionario(quadro), "Sensores do modelo (SolidWorks)"
        ):
            st.rerun()

massa_da_lista = (
    lm.resumir(lm.lista_do_projeto(projeto)).massa_itens_kg if projeto is not None else None
)
analise = sm.analisar(quadro, plano, massa_da_lista_kg=massa_da_lista)

# ============================================================ 3. conferência
with st.container(border=True), secao_protegida("3. Conferência do quadro"):
    st.subheader("3. Conferência do quadro", help=AJUDA["sec_conferencia"])
    colunas = st.columns(4)
    colunas[0].metric("Sensores", len(quadro.sensores), help=AJUDA["res_sensores"])
    colunas[1].metric("Casos", len(quadro.casos), help=AJUDA["res_casos"])
    colunas[2].metric("Combinações", len(quadro.combinacoes), help=AJUDA["res_combinacoes"])
    colunas[3].metric("Fora da verificação", len(analise.fora), help=AJUDA["res_fora"])
    if not analise.achados:
        st.success(
            "O quadro confere com o plano de cargas: nenhum caso ou combinação faltando, nada "
            "repetido e a superposição fecha.",
            icon=":material/verified:",
        )
    for achado in analise.achados:
        MOSTRAR.get(achado.nivel, st.success)(
            f"**{texto_markdown(achado.titulo)}** — {texto_markdown(achado.texto)}",
            icon=ICONES.get(achado.nivel, ":material/info:"),
        )
    st.markdown("**Sensores mínimos do estudo estático**", help=AJUDA["minimos"])
    st.dataframe(
        pd.DataFrame(sm.linhas_dos_minimos(analise), columns=list(sm.COLUNAS_MINIMOS)),
        hide_index=True,
        width="stretch",
    )

# ============================================================ 4. resultados
with st.container(border=True), secao_protegida("4. Resultados"):
    st.subheader("4. Resultados", help=AJUDA["sec_resultados"])
    colunas = st.columns(5)
    colunas[0].metric("Status", analise.status, help=AJUDA["res_status"])
    aproveitamento = analise.aproveitamento_maximo
    colunas[1].metric(
        "Aproveitamento",
        "—" if aproveitamento is None else f"{100 * aproveitamento:.0f} %",
        help=AJUDA["res_aproveitamento"],
    )
    metricas = (
        (sm.TENSAO, sm.GRUPO_ELU, "Tensão máx. ELU (MPa)", AJUDA["res_tensao"]),
        (sm.FATOR_DE_SEGURANCA, sm.GRUPO_ELU, "FS mín. ELU", AJUDA["res_fs"]),
        (sm.DESLOCAMENTO, sm.GRUPO_ELS, "Desloc. máx. ELS (mm)", AJUDA["res_deslocamento"]),
    )
    for coluna, (grandeza, grupo, rotulo, ajuda) in zip(colunas[2:], metricas, strict=True):
        k = next((i for i, s in enumerate(quadro.sensores) if s.grandeza == grandeza), None)
        e = analise.extremo(k, grupo) if k is not None else None
        coluna.metric(
            rotulo,
            "—" if e is None else sm.formatar(abs(e.valor), grandeza),
            None if e is None else e.linha,
            delta_color="off",
            delta_arrow="off",
            help=ajuda,
        )
    mostrar_verificacoes_resumidas([("Verificações", analise.verificacoes)])
    st.caption(
        ":material/info: A tensão elástica do modelo verifica só o escoamento: flambagem, "
        "flambagem lateral com torção e a interação N + M da NBR 8800 são a verificação barra a "
        "barra, em Esforços do modelo."
    )
    st.markdown("**O pior de cada sensor**")
    st.dataframe(
        pd.DataFrame(sm.linhas_do_resumo(analise), columns=list(sm.COLUNAS_RESUMO)),
        hide_index=True,
        width="stretch",
    )
    paineis = dds.paineis_da_analise(analise)
    if paineis:
        mostrar_figura(svg_da_cena(dds.desenho_dos_sensores(paineis)))
    with st.expander("O quadro inteiro e as combinações que governam", icon=":material/table:"):
        st.dataframe(
            pd.DataFrame(sm.linhas_do_quadro(analise), columns=sm.colunas_do_quadro(analise)),
            hide_index=True,
            width="stretch",
        )
        governam = sm.combinacoes_que_governam(analise)
        if governam:
            st.dataframe(
                pd.DataFrame(
                    governam, columns=["Combinação", "Estado-limite", "Expressão no modelo"]
                ),
                hide_index=True,
                width="stretch",
            )
    st.download_button(
        "Baixar o quadro organizado (CSV para o Excel)",
        data=sm.csv_do_quadro(analise),
        file_name=f"sensores_{quadro.estudo or 'estudo'}.csv".replace(" ", "_"),
        mime="text/csv",
        icon=":material/table_view:",
        key="sm_csv",
        help=AJUDA["btn_csv"],
    )

# ============================================================ 5. registrar
with st.container(border=True), secao_protegida("5. Registrar no memorial"):
    st.subheader("5. Registrar no memorial", help=AJUDA["sec_registrar"])
    responsavel = str((projeto or {}).get("responsavel") or "")
    botao_registrar_calculo(
        sm.registro_sensores(analise, responsavel=responsavel),
        key="registrar_sensores_do_modelo",
        identificar_peca=False,
    )
