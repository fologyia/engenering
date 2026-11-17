"""Nomes das barras: cada peça do modelo com um nome que diz o que ela é e onde está.

A página lê o esqueleto do SolidWorks, monta a grade de eixos (pelos pilares) e os níveis (pelas
vigas e chapas de piso), entende o papel de cada corpo e sugere o nome no padrão de
``core/papel_pelo_nome.py`` (P-A1, V-N1-A1-A2, C-N0-B1-B2, PS-N1-01…), mais o PERFIL de cada item da
lista de corte. A macro ``renomear_corpos.bas`` leva tudo ao SolidWorks, conferindo cada corpo pela
geometria; o relatório dela volta para o projeto.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.base_tecnica_ui import gravar_campos_do_projeto, gravar_plano
from components.figuras import mostrar_figura
from components.nomes_das_barras_help import AJUDA
from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import nomes_das_barras as nb
from core import papel_pelo_nome as pn
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo

configurar_pagina("Nomes das barras", ":material/label:")
cabecalho_pagina(
    "Nomes das barras",
    "Dê a cada pilar, viga, contraventamento e chapa do SolidWorks um nome que diz o que a peça é "
    "e onde está (P-A1, V-N1-A1-A2): o programa passa a ler o papel pelo nome, sem adivinhar pela "
    "posição, e cada resultado fica fácil de achar no modelo.",
    categoria="Modelo SolidWorks",
    icone=":material/label:",
    cor="blue",
    acoes=(
        ("app_pages/esforcos_modelo.py", "Esforços do modelo", ":material/upload_file:"),
        ("app_pages/cargas_esqueleto.py", "Cargas do esqueleto", ":material/grid_view:"),
    ),
)

projeto = obter_projeto_ativo()
if projeto is None:
    st.info(
        "Nenhum projeto ativo. Abra ou crie um em **Projetos**: os nomes, as trocas e o esqueleto "
        "ficam guardados no projeto.",
        icon=":material/folder_off:",
    )
    st.stop()

versao = int(st.session_state.get("nb_versao", 0))
CHAVE_ESCOLHAS = "nb_escolhas"
CHAVE_AVISO = "nb_aviso"
ORIGENS = {
    nb.GERADO: "novo",
    nb.MANTIDO: "já no padrão",
    nb.A_MAO: "à mão",
    nb.SEM_TROCA: "não troca",
}


def _pt(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _texto(valor: Any) -> str:
    """O texto de uma célula da tabela editada (vazio para None e NaN)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ""
    return str(valor).strip()


def _recarregar(aviso: str = "") -> None:
    st.session_state["nb_versao"] = versao + 1
    if aviso:
        st.session_state[CHAVE_AVISO] = aviso
    st.rerun()


def _escolhas() -> nb.Escolhas:
    """As escolhas da página: as do projeto na primeira vez, depois as da tela."""
    identidade = str(projeto.get("id") or "")
    guardadas = st.session_state.get(CHAVE_ESCOLHAS)
    if (
        not isinstance(guardadas, tuple)
        or len(guardadas) != 2
        or guardadas[0] != identidade
        or not isinstance(guardadas[1], nb.Escolhas)
    ):
        guardadas = (identidade, nb.escolhas_do_projeto(projeto))
        st.session_state[CHAVE_ESCOLHAS] = guardadas
    return guardadas[1]


def _trocar_escolhas(novas: nb.Escolhas) -> None:
    st.session_state[CHAVE_ESCOLHAS] = (str(projeto.get("id") or ""), novas)


aviso = st.session_state.pop(CHAVE_AVISO, "")
if aviso:
    st.success(aviso, icon=":material/check_circle:")


# ============================================================ 1. o esqueleto
def _enviar_esqueleto(rotulo: str) -> None:
    enviado = st.file_uploader(
        rotulo, type=["csv"], key=f"nb_esqueleto_{versao}", help=AJUDA["arquivo_esqueleto"]
    )
    if enviado is None:
        return
    try:
        novo = ld.ler_esqueleto(enviado.getvalue(), enviado.name)
    except ld.GeometriaInvalida as erro:
        st.error(f"{enviado.name}: {erro}", icon=":material/error:")
        return
    st.success(
        f"{novo.arquivo}: {len(novo.corpos)} corpos" + (f" ({novo.origem})" if novo.origem else ""),
        icon=":material/account_tree:",
    )
    for texto in novo.avisos:
        st.warning(texto, icon=":material/warning:")
    if st.button(
        "Gravar o esqueleto no projeto",
        type="primary",
        icon=":material/save:",
        key="nb_gravar_esqueleto",
        help=AJUDA["btn_gravar_esqueleto"],
    ) and gravar_campos_do_projeto(
        {"geometria_do_modelo": ld.para_dicionario(novo)}, "Esqueleto do modelo gravado"
    ):
        _recarregar("Esqueleto gravado no projeto.")


geometria = ld.geometria_do_projeto(projeto)

with st.container(border=True), secao_protegida("1. Esqueleto do modelo"):
    st.subheader("1. Esqueleto do modelo", help=AJUDA["sec_esqueleto"])
    if not geometria.corpos:
        _enviar_esqueleto("Esqueleto do modelo (…_esqueleto.csv da macro)")
        st.caption(
            ":material/account_tree: Sem o esqueleto do modelo ainda. No SolidWorks, rode a macro "
            "exportar_lista_de_corte (botão abaixo) com a peça aberta e envie o …_esqueleto.csv "
            "que ela grava ao lado da peça."
        )
    else:
        st.caption(
            f":material/account_tree: {geometria.arquivo}"
            + (f" — {geometria.origem}" if geometria.origem else "")
            + f" · {len(geometria.corpos)} corpos"
        )
        if geometria.versao_da_macro and geometria.versao_da_macro != ld.VERSAO_ATUAL_DA_MACRO:
            st.caption(
                f":material/info: Esqueleto da macro {geometria.versao_da_macro}: os nomes saem "
                "iguais, mas o PERFIL que a página grava só volta ao programa pela macro "
                f"{ld.VERSAO_ATUAL_DA_MACRO} (baixe-a abaixo e rode de novo depois da troca)."
            )
        with st.expander("Trocar o esqueleto (o modelo mudou no SolidWorks)"):
            _enviar_esqueleto("Novo …_esqueleto.csv da macro")
    st.download_button(
        f"Macro da lista de corte ({ld.VERSAO_ATUAL_DA_MACRO})",
        data=lm.macro_da_lista_de_corte(),
        file_name="exportar_lista_de_corte.bas",
        mime="text/plain",
        icon=":material/code:",
        key="nb_macro_lista",
        help=AJUDA["btn_macro_lista"],
    )

if not geometria.corpos:
    st.stop()

# ============================================================ 2. como o programa lê
escolhas = _escolhas()
eixo_padrao = escolhas.eixo_vertical or em.esforcos_do_projeto(projeto).eixo_vertical or "Y"
plano_de_nomes: nb.PlanoDeNomes | None = None

with st.container(border=True), secao_protegida("2. Como o programa lê o modelo"):
    st.subheader("2. Como o programa lê o modelo", help=AJUDA["sec_leitura"])
    colunas = st.columns([1, 2])
    eixo = str(
        colunas[0].radio(
            "Eixo vertical do modelo",
            ("Y", "Z"),
            index=0 if eixo_padrao == "Y" else 1,
            horizontal=True,
            key=f"nb_eixo_{versao}",
            help=AJUDA["eixo_vertical"],
        )
    )
    refazer = colunas[1].toggle(
        "Refazer também os nomes que já estão no padrão",
        value=escolhas.refazer,
        key=f"nb_refazer_{versao}",
        help=AJUDA["refazer"],
    )
    if eixo != escolhas.eixo_vertical or refazer != escolhas.refazer:
        escolhas = replace(escolhas, eixo_vertical=eixo, refazer=bool(refazer))
        _trocar_escolhas(escolhas)
    plano_de_nomes = nb.sugerir(
        geometria,
        eixo,
        escolhidos=escolhas.papeis,
        a_mao=escolhas.a_mao,
        sem_troca=escolhas.sem_troca,
        refazer=escolhas.refazer,
    )
    grade = plano_de_nomes.grade
    metricas = st.columns(4)
    metricas[0].metric("Corpos", len(plano_de_nomes.sugestoes), help=AJUDA["res_corpos"])
    metricas[1].metric("Já dizem o papel", plano_de_nomes.no_padrao, help=AJUDA["res_no_padrao"])
    metricas[2].metric("Mudam de nome", len(plano_de_nomes.trocas), help=AJUDA["res_mudam"])
    metricas[3].metric(
        "Nome contradiz a posição",
        sum(1 for s in plano_de_nomes.sugestoes if s.nota),
        help=AJUDA["res_contradizem"],
    )
    for texto in plano_de_nomes.avisos:
        st.info(texto, icon=":material/info:")
    if grade.tem_eixos:
        st.caption(
            f":material/grid_on: Eixos: {grade.numeros[0][0]} a {grade.numeros[-1][0]} "
            f"(da esquerda para a direita) e {grade.letras[0][0]} a {grade.letras[-1][0]} (de "
            "baixo para cima), como na vista Superior do SolidWorks · Níveis: N0 +0,00 m"
            + "".join(f" · N{i} +{_pt(cota)} m" for i, cota in enumerate(grade.niveis, start=1))
        )
    opcoes_de_nivel = ["Todos", *(f"N{i}" for i in range(len(grade.niveis) + 1))]
    nivel_escolhido = st.selectbox(
        "Nível na planta",
        opcoes_de_nivel,
        index=2 if len(opcoes_de_nivel) > 2 else 0,
        # Outro esqueleto, outros níveis: a chave muda junto e uma escolha velha não fica presa.
        key=f"nb_nivel_planta_{len(opcoes_de_nivel)}",
        help=AJUDA["nivel_planta"],
    )
    nivel = None if nivel_escolhido == "Todos" else int(str(nivel_escolhido)[1:])
    desenho = nb.svg_da_planta(plano_de_nomes, geometria, nivel)
    if desenho:
        mostrar_figura(
            desenho,
            "Planta (vista Superior): pilares em azul, vigas em cinza, contraventamentos em "
            "laranja, longarinas e degraus em verde, chapas com fundo claro.",
        )

if plano_de_nomes is None:
    st.stop()

# ============================================================ 3. a tabela dos nomes
COLUNAS = (
    "Corpo no SolidWorks",
    "Forma",
    "Papel",
    "Nome",
    "De onde vem o nome",
    "Nome à mão",
    "Trocar",
    "Onde",
    "Por quê",
    "Atenção",
)
problemas = nb.conferir(plano_de_nomes, geometria)

with st.container(border=True), secao_protegida("3. Papel e nome de cada peça"):
    st.subheader("3. Papel e nome de cada peça", help=AJUDA["sec_tabela"])
    repetidos = {
        s.nome
        for s in plano_de_nomes.sugestoes
        if sum(1 for o in plano_de_nomes.sugestoes if o.nome == s.nome) > 1
    }
    linhas = []
    for s in plano_de_nomes.sugestoes:
        atencao = [s.nota] if s.nota else []
        if s.nome in repetidos:
            atencao.append("nome repetido")
        if s.origem_do_nome == nb.A_MAO and pn.problema_do_nome(s.nome):
            atencao.append(pn.problema_do_nome(s.nome))
        linhas.append(
            {
                "Corpo no SolidWorks": s.corpo,
                "Forma": s.forma.lower() or "—",
                "Papel": s.papel.rotulo,
                "Nome": s.nome,
                "De onde vem o nome": ORIGENS.get(s.origem_do_nome, s.origem_do_nome),
                "Nome à mão": escolhas.a_mao.get(s.corpo, ""),
                "Trocar": s.corpo not in escolhas.sem_troca,
                "Onde": s.onde,
                "Por quê": s.motivo,
                "Atenção": "; ".join(atencao),
            }
        )
    st.caption("Troque o papel onde ele estiver errado: o nome se refaz.", help=AJUDA["tabela"])
    editado = st.data_editor(
        pd.DataFrame(linhas, columns=list(COLUNAS)),
        hide_index=True,
        width="stretch",
        key=f"nb_tabela_{versao}",
        disabled=[c for c in COLUNAS if c not in ("Papel", "Nome à mão", "Trocar")],
        column_config={
            "Papel": st.column_config.SelectboxColumn(
                "Papel", options=[p.rotulo for p in pn.PAPEIS], required=True
            ),
            "Nome à mão": st.column_config.TextColumn("Nome à mão", max_chars=pn.TAMANHO_MAXIMO),
            "Trocar": st.column_config.CheckboxColumn("Trocar"),
        },
    )
    papeis = dict(escolhas.papeis)
    a_mao = dict(escolhas.a_mao)
    sem_troca = set(escolhas.sem_troca)
    mudou = False
    for antes, depois in zip(linhas, editado.to_dict("records"), strict=False):
        corpo = antes["Corpo no SolidWorks"]
        papel = pn.POR_ROTULO.get(_texto(depois.get("Papel")))
        if papel is not None and papel.rotulo != antes["Papel"]:
            papeis[corpo] = papel.prefixo
            a_mao.pop(corpo, None)  # o nome à mão era do papel antigo
            mudou = True
        nome = _texto(depois.get("Nome à mão"))
        if nome != _texto(antes["Nome à mão"]):
            if nome:
                a_mao[corpo] = nome
            else:
                a_mao.pop(corpo, None)
            mudou = True
        trocar = bool(depois.get("Trocar"))
        if trocar != bool(antes["Trocar"]):
            if trocar:
                sem_troca.discard(corpo)
            else:
                sem_troca.add(corpo)
            mudou = True
    if mudou:
        _trocar_escolhas(
            replace(escolhas, papeis=papeis, a_mao=a_mao, sem_troca=tuple(sorted(sem_troca)))
        )
        _recarregar()
    if escolhas.papeis or escolhas.a_mao or escolhas.sem_troca:
        if st.button(
            "Voltar às sugestões do programa",
            icon=":material/restart_alt:",
            key="nb_voltar",
            help=AJUDA["btn_sugestoes"],
        ):
            _trocar_escolhas(replace(escolhas, papeis={}, a_mao={}, sem_troca=()))
            _recarregar()
    if problemas:
        st.error(
            "Corrija antes de levar ao SolidWorks:\n\n" + "\n".join(f"- {p}" for p in problemas),
            icon=":material/error:",
        )
    else:
        st.success(
            f"{len(plano_de_nomes.trocas)} corpo(s) mudam de nome; cada nome é único e começa pelo "
            "prefixo do papel.",
            icon=":material/check_circle:",
        )

# ============================================================ 4. os perfis
itens = nb.perfis_dos_itens(geometria)
a_gravar: dict[str, str] = {}

with st.container(border=True), secao_protegida("4. Perfil de cada item da lista de corte"):
    st.subheader("4. Perfil de cada item da lista de corte", help=AJUDA["sec_perfis"])
    if not itens:
        st.caption(
            ":material/info: O esqueleto não tem itens de lista de corte com barras (peça sem "
            "soldagens, ou esqueleto de uma macro antiga)."
        )
    else:
        colunas_perfis = (
            "Item",
            "Descrição",
            "Corpos",
            "Área medida (cm²)",
            "Perfil lido",
            "De onde",
            "PERFIL hoje",
            "Perfil a gravar",
        )
        linhas_perfis = [
            {
                "Item": item.item,
                "Descrição": item.descricao,
                "Corpos": len(item.corpos),
                "Área medida (cm²)": round(item.area_cm2, 1) if item.area_cm2 else None,
                "Perfil lido": item.perfil_lido or "—",
                "De onde": item.origem or "—",
                "PERFIL hoje": item.declarado or "—",
                "Perfil a gravar": nb.perfil_escolhido(item, escolhas),
            }
            for item in itens
        ]
        st.caption(
            "Escolha o perfil da obra onde ficou vazio; o resto já vem conferido.",
            help=AJUDA["tabela_perfis"],
        )
        editado_perfis = st.data_editor(
            pd.DataFrame(linhas_perfis, columns=list(colunas_perfis)),
            hide_index=True,
            width="stretch",
            key=f"nb_perfis_{versao}",
            disabled=[c for c in colunas_perfis if c != "Perfil a gravar"],
            column_config={
                "Perfil a gravar": st.column_config.SelectboxColumn(
                    "Perfil a gravar", options=["", *nb.perfis_do_catalogo()]
                ),
            },
        )
        perfis = dict(escolhas.perfis)
        mudou_perfil = False
        for antes, depois in zip(linhas_perfis, editado_perfis.to_dict("records"), strict=False):
            escolhido = _texto(depois.get("Perfil a gravar"))
            if escolhido != _texto(antes["Perfil a gravar"]):
                perfis[str(antes["Item"])] = escolhido
                mudou_perfil = True
        if mudou_perfil:
            _trocar_escolhas(replace(escolhas, perfis=perfis))
            _recarregar()
        a_gravar = nb.perfis_a_gravar(itens, escolhas)
        problemas += nb.conferir_perfis(a_gravar)
        st.caption(
            f":material/sell: {len(a_gravar)} item(ns) recebem o PERFIL; "
            f"{sum(1 for i in itens if not nb.perfil_escolhido(i, escolhas))} sem perfil escolhido."
        )


# ============================================================ 5. levar ao SolidWorks
def _guardar_o_plano(quando: str) -> None:
    """Ao baixar o arquivo: guarda as escolhas e as trocas pedidas (ainda não confirmadas)."""
    atual = obter_projeto_ativo()
    if atual is None or plano_de_nomes is None:
        return
    novas = nb.renomeacoes_do_plano(plano_de_nomes, geometria, quando)
    gravar_campos_do_projeto(
        nb.campos_do_projeto(atual, escolhas, novas), "Nomes das barras: arquivo para a macro"
    )


with st.container(border=True), secao_protegida("5. Levar ao SolidWorks"):
    st.subheader("5. Levar ao SolidWorks", help=AJUDA["sec_levar"])
    if problemas:
        st.error(
            "O arquivo de nomes só sai sem problemas na tabela (seção 3 e 4).",
            icon=":material/block:",
        )
    elif not plano_de_nomes.trocas and not a_gravar:
        st.success(
            "Nada a levar ao SolidWorks: todos os corpos já têm o nome no padrão e os perfis "
            "escolhidos já estão gravados.",
            icon=":material/check_circle:",
        )
    else:
        agora = datetime.now().isoformat(timespec="seconds")
        st.download_button(
            f"Arquivo de nomes ({nb.nome_do_arquivo(geometria)})",
            data=nb.arquivo_para_a_macro(plano_de_nomes, geometria, perfis=a_gravar, quando=agora),
            file_name=nb.nome_do_arquivo(geometria),
            mime="text/csv",
            type="primary",
            icon=":material/download:",
            key="nb_baixar",
            on_click=_guardar_o_plano,
            args=(agora,),
            help=AJUDA["btn_arquivo"],
        )
    st.download_button(
        "Macro renomear_corpos.bas",
        data=nb.macro_de_renomear(),
        file_name=nb.ARQUIVO_DA_MACRO,
        mime="text/plain",
        icon=":material/code:",
        key="nb_macro",
        help=AJUDA["btn_macro"],
    )
    st.markdown(
        f"1. Salve o **{nb.nome_do_arquivo(geometria)}** na pasta da peça, ao lado do .SLDPRT "
        "(ou deixe em Downloads).\n"
        "2. No SolidWorks, com a peça aberta: **Ferramentas › Macro › Executar** e escolha a "
        "renomear_corpos (na primeira vez: Nova…, cole o texto da macro e tecle F5).\n"
        "3. Confira a lista que a macro mostra e confirme. Ela troca os nomes, grava o PERFIL dos "
        "itens e deixa ao lado da peça o relatório (…_nomes_aplicados.csv) e o arquivo para "
        "desfazer (…_nomes_desfazer.csv).\n"
        "4. **Salve a peça** e rode a **exportar_lista_de_corte** de novo: envie o esqueleto novo "
        "na seção 1 e a lista de corte na Lista de material.\n"
        "5. Estudos do Simulation já rodados guardam os nomes antigos até refazer a malha: o "
        "programa acha cada corpo mesmo assim, mas o certo é refazer a malha e rodar de novo."
    )

# ============================================================ 6. depois da macro
with st.container(border=True), secao_protegida("6. Depois de rodar a macro"):
    st.subheader("6. Depois de rodar a macro", help=AJUDA["sec_depois"])
    enviado = st.file_uploader(
        "Relatório da macro (…_nomes_aplicados.csv)",
        type=["csv"],
        key=f"nb_relatorio_{versao}",
        help=AJUDA["arquivo_relatorio"],
    )
    if enviado is not None:
        try:
            relatorio = nb.ler_relatorio_da_macro(enviado.getvalue(), enviado.name)
        except nb.RelatorioInvalido as erro:
            st.error(f"{enviado.name}: {erro}", icon=":material/error:")
        else:
            trocados = relatorio.trocados
            pela_geometria = [
                linha for linha in trocados if linha.situacao == nb.SITUACAO_PELA_GEOMETRIA
            ]
            colunas = st.columns(3)
            colunas[0].metric("Renomeados", len(trocados), help=AJUDA["res_renomeados"])
            colunas[1].metric(
                "Achados pela geometria", len(pela_geometria), help=AJUDA["res_pela_geometria"]
            )
            colunas[2].metric("Pulados", len(relatorio.pulados), help=AJUDA["res_pulados"])
            if relatorio.peca and geometria.peca and relatorio.peca != geometria.peca:
                st.warning(
                    f"O relatório é da peça {relatorio.peca}; o esqueleto do projeto é de "
                    f"{geometria.peca}.",
                    icon=":material/warning:",
                )
            if relatorio.pulados:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Tipo": p.tipo, "Nome": p.antigo, "Pedido": p.novo, "Motivo": p.motivo}
                            for p in relatorio.pulados
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            if st.button(
                "Guardar as trocas no projeto",
                type="primary",
                icon=":material/save:",
                key="nb_guardar_relatorio",
                help=AJUDA["btn_guardar_relatorio"],
            ):
                agora = datetime.now().isoformat(timespec="seconds")
                atual = obter_projeto_ativo()
                novas = nb.renomeacoes_do_relatorio(relatorio, geometria, agora)
                resumo = {
                    "data": relatorio.data,
                    "peca": relatorio.peca,
                    "renomeados": len(trocados),
                    "pela_geometria": len(pela_geometria),
                    "pulados": len(relatorio.pulados),
                    "guardado_em": agora,
                }
                if atual is not None and gravar_campos_do_projeto(
                    nb.campos_do_projeto(atual, escolhas, novas, resumo),
                    "Nomes das barras: relatório da macro",
                ):
                    _recarregar(
                        f"{len(novas)} troca(s) confirmadas guardadas no projeto. Gere o esqueleto "
                        "de novo (macro exportar_lista_de_corte) e envie-o na seção 1."
                    )
    historico = pn.renomeacoes_do_projeto(projeto)
    feitas = nb.trocas_feitas(historico, geometria)
    if historico:
        confirmadas = sum(1 for r in historico if r.confirmada)
        st.caption(
            f":material/history: {len(historico)} troca(s) de nome guardadas no projeto "
            f"({confirmadas} confirmadas pelo relatório da macro). Com elas, os estudos rodados "
            "antes da troca continuam achando cada corpo no esqueleto."
        )
    plano_de_cargas = pc.plano_do_projeto(projeto)
    citam = nb.linhas_com_nome_antigo(plano_de_cargas, feitas)
    if citam:
        st.info(
            f"{citam} linha(s) do plano de cargas citam corpos pelo nome antigo.",
            icon=":material/table_chart:",
        )
        if st.button(
            "Trocar os nomes no plano de cargas",
            icon=":material/sync:",
            key="nb_plano",
            help=AJUDA["btn_plano"],
        ):
            novo_plano, mudaram = nb.plano_com_os_nomes_novos(plano_de_cargas, feitas)
            if mudaram and gravar_plano(
                novo_plano, "Plano de cargas com os nomes novos das barras"
            ):
                _recarregar(f"{mudaram} linha(s) do plano de cargas com os nomes novos.")
