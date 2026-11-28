"""Importação de remessas do Robot e verificações do modelo ativo."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import pandas as pd
import streamlit as st

from components.base_tecnica_ui import gravar_campos_do_projeto
from components.project_tools import botao_registrar_calculo
from components.verification_table import mostrar_tabela_verificacoes
from core import apoios_do_modelo as am
from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import reacoes_nas_bases as rb
from core import robot
from core import robot_integracao as ri
from core import section_catalog as sc
from core import verificacao_barras as vb
from core.column_buckling import NORMAS
from core.project_store import CAMPO_GRAVACAO, obter_projeto_ativo
from core.technical_records import criar_registro_tecnico


@st.cache_data(ttl=600, max_entries=12, show_spinner=False)
def _ler_tabelas(nome: str, conteudo: bytes) -> list[robot.Tabela]:
    return robot.ler_tabelas(nome, conteudo)


def _gravar(
    projeto: Mapping[str, Any],
    campos: Mapping[str, Any],
    motivo: str,
    *,
    criar_revisao: bool = False,
) -> None:
    atual = obter_projeto_ativo()
    if atual is None or atual["id"] != projeto["id"]:
        st.error("O projeto ativo mudou. Abra novamente a importação no projeto de destino.")
        return
    if gravar_campos_do_projeto(
        campos, motivo, gravacao_esperada=projeto.get(CAMPO_GRAVACAO), criar_revisao=criar_revisao
    ):
        st.rerun()


def ativar_solidworks(projeto: Mapping[str, Any]) -> None:
    st.info(
        "O Robot é o modelo ativo. Ative o SolidWorks para usar a importação e as verificações do Simulation."
    )
    if st.button("Ativar SolidWorks", icon=":material/swap_horiz:"):
        _gravar(projeto, {robot.CAMPO_ORIGEM: robot.SOLIDWORKS}, "Modelo ativo: SolidWorks")


def _cabecalho(tabela: robot.Tabela, linha: int) -> list[str]:
    return [str(c or "").strip().casefold() for c in tabela.linhas[linha - 1]]


def _selecionar_tabelas(
    tabelas: Sequence[robot.Tabela],
    chave: str,
    anterior: Mapping[str, Any],
) -> dict[str, robot.Selecao]:
    selecionadas = {}
    for tipo, esquema in robot.ESQUEMAS.items():
        notas = [robot.sugerir_cabecalho(tipo, tabela) for tabela in tabelas]
        perfil = anterior.get(tipo, {})
        candidatas = [
            i for i, nota in enumerate(notas) if nota[0] == len(robot.campos_obrigatorios(tipo))
        ]
        if tipo == "Casos":
            candidatas = [
                i
                for i in candidatas
                if not {"definicao", "definition", "tipodecombinacao", "combinationtype"}
                & {robot._cabecalho(c) for c in tabelas[i].linhas[-notas[i][1] - 1]}
            ]
        if tipo == "Combinações":
            candidatas = [
                i
                for i in candidatas
                if "combin" in tabelas[i].nome.casefold()
                or {
                    "Definição",
                    "Estado-limite",
                    "Fator",
                }
                & robot.colunas_sugeridas(tipo, tabelas[i].linhas[-notas[i][1] - 1]).keys()
            ]
        correspondentes = (
            {
                i: next(
                    (
                        n
                        for n in range(1, min(len(t.linhas), 30) + 1)
                        if _cabecalho(t, n) == perfil.get("cabecalho")
                    ),
                    None,
                )
                for i, t in enumerate(tabelas)
            }
            if perfil
            else {}
        )
        candidatas = list(
            dict.fromkeys([*candidatas, *(i for i, n in correspondentes.items() if n)])
        )
        variacoes = {}
        for i in candidatas:
            inicio = correspondentes.get(i) or -notas[i][1]
            linhas = tuple(
                tuple(str(c or "").strip() for c in r)
                for r in tabelas[i].linhas[inicio - 1 :]
                if any(r)
            )
            variacoes.setdefault(linhas, i)
        conflito = len(variacoes) > 1
        sugestao = candidatas[0] if candidatas and not conflito else None
        if conflito:
            st.warning(
                f"Há tabelas de {tipo.lower()} com conteúdo ou colunas diferentes. Escolha a fonte."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tabela": tabelas[i].nome,
                            "Linhas": len(linhas) - 1,
                            "Primeira diferença": " / ".join(proxima),
                        }
                        for linhas, i in variacoes.items()
                        for proxima in (
                            next(
                                (
                                    r
                                    for j, r in enumerate(linhas)
                                    if any(j >= len(outra) or outra[j] != r for outra in variacoes)
                                ),
                                (),
                            ),
                        )
                    ]
                ),
                hide_index=True,
            )
        indice = st.selectbox(
            f"Tabela de {tipo.lower()}",
            [None, *range(len(tabelas))],
            index=0 if sugestao is None else sugestao + 1,
            format_func=lambda i: "Selecione" if i is None else tabelas[i].nome,
            key=f"{chave}_{tipo}",
        )
        if indice is None:
            continue
        tabela = tabelas[indice]
        if not tabela.linhas:
            st.warning(f"{tabela.nome} está vazia.")
            continue
        with st.expander(f"Colunas de {tipo.lower()}"):
            id_tabela = f"{chave}_{tipo}_{indice}"
            cabecalho = st.number_input(
                "Linha dos cabeçalhos",
                min_value=1,
                max_value=len(tabela.linhas),
                value=correspondentes.get(indice) or -notas[indice][1],
                key=f"{id_tabela}_cabecalho",
            )
            linha = tabela.linhas[cabecalho - 1]
            colunas = (
                dict(perfil["colunas"])
                if _cabecalho(tabela, cabecalho) == perfil.get("cabecalho")
                else robot.colunas_sugeridas(tipo, linha)
            )
            for coluna in esquema:
                indice_coluna = st.selectbox(
                    coluna.nome,
                    [None, *range(len(linha))],
                    index=colunas[coluna.nome] + 1 if coluna.nome in colunas else 0,
                    format_func=lambda i, linha=linha: (
                        "Sem coluna" if i is None else f"{i + 1} · {linha[i] or 'Sem título'}"
                    ),
                    key=f"{id_tabela}_{cabecalho}_{coluna.nome}",
                )
                if indice_coluna is None:
                    colunas.pop(coluna.nome, None)
                else:
                    colunas[coluna.nome] = indice_coluna
        selecionadas[tipo] = robot.Selecao(tabela, cabecalho, colunas)
    return selecionadas


def _prever(modelo: Mapping[str, Any]) -> None:
    dados = robot.dados_do_modelo(modelo)
    reacoes = rb.montar_do_robot(modelo)
    st.dataframe(
        pd.DataFrame(
            [{"Tipo": tipo, "Tabela usada": a["tabela"]} for tipo, a in modelo["arquivos"].items()]
        ),
        hide_index=True,
    )
    st.write(
        f"{len(modelo['nos'])} nós · {len(modelo['barras'])} barras · {len(modelo['casos'])} casos e "
        f"combinações · {sum(len(p) for c in dados.casos.values() for p in c.membros.values())} pontos "
        f"de esforço · {len(reacoes.pes)} nós de apoio"
    )
    amostra = []
    for caso in dados.casos.values():
        for barra, pontos in caso.membros.items():
            amostra.extend(
                [[barra, caso.codigo, p.elemento, p.fim, *p.vetor()] for p in pontos[:8]]
            )
            if len(amostra) >= 8:
                break
        if len(amostra) >= 8:
            break
    st.dataframe(
        pd.DataFrame(
            amostra[:8],
            columns=[
                "Barra",
                "Caso",
                "x/L",
                "Lado",
                "N (kN)",
                "Vy (kN)",
                "Vz (kN)",
                "My (kN·m)",
                "Mz (kN·m)",
                "T (kN·m)",
            ],
        ),
        hide_index=True,
    )
    apoios = am.de_dicionario(modelo["reacoes"])
    reacoes_brutas = [
        [n.no, codigo, *(v / 1000 for v in (*n.forca_N, *n.momento_Nm))]
        for codigo, caso in apoios.casos.items()
        for n in caso.nos[:8]
    ][:8]
    st.dataframe(
        pd.DataFrame(
            reacoes_brutas,
            columns=[
                "Nó",
                "Caso",
                "FX global (kN)",
                "FY global (kN)",
                "FZ global (kN)",
                "MX global (kN·m)",
                "MY global (kN·m)",
                "MZ global (kN·m)",
            ],
        ),
        hide_index=True,
    )
    pendentes = sum(
        not c.perfil or not c.eixo_forte or c.aco not in vb.ACOS for c in dados.membros.values()
    )
    if pendentes:
        st.warning(
            f"{pendentes} barra(s) precisam de confirmação de perfil, material ou eixo forte."
        )
    for aviso in reacoes.faltam:
        st.warning(aviso)


def _importacao(projeto: Mapping[str, Any], anterior: Mapping[str, Any], chave: str) -> None:
    with st.expander("Importar tabelas do Robot", expanded=not anterior):
        st.markdown(
            "No Robot, exporte **Nós**, **Barras**, **Casos**, **Combinações**, **Forças** e **Reações** "
            "da mesma rodada. Os casos saem da aba **Info** da tabela de cargas. Em Forças e Reações, "
            "use a aba **Valores**. Selecione as seis componentes, "
            "as extremidades e os pontos críticos ao longo das barras. Nas reações, escolha **eixos globais** "
            "e inclua todos os nós apoiados e os casos simples."
        )
        st.caption("Envie as tabelas ou a nota de cálculo em HTML ou RTF da mesma revisão.")
        arquivos = st.file_uploader(
            "Tabelas do Robot",
            type=["xlsx", "csv", "txt", "tsv", "html", "htm", "rtf", "xml"],
            accept_multiple_files=True,
            key=f"{chave}_arquivos",
        )
        coladas = {}
        with st.expander("Colar tabelas"):
            for tipo in robot.ESQUEMAS:
                texto = st.text_area(
                    f"Colar {tipo.lower()}", key=f"{chave}_colar_{tipo}", height=76
                )
                if texto.strip():
                    coladas[f"{tipo} colada.tsv"] = texto.encode("utf-8")
        entradas = [(a.name, a.getvalue()) for a in arquivos] + list(coladas.items())
        if not entradas:
            return
        tabelas = []
        for nome, conteudo in entradas:
            try:
                lidas = _ler_tabelas(nome, conteudo)
            except robot.ImportacaoRobotInvalida as erro:
                st.error(str(erro))
                continue
            if not lidas:
                st.warning(
                    f"{nome} sem tabelas estruturadas. Vincule o documento na referência do memorial."
                )
            tabelas.extend(lidas)
        if not tabelas:
            return
        chave_arquivos = hashlib.sha256(
            "\n".join(f"{t.nome}:{t.assinatura}" for t in tabelas).encode()
        ).hexdigest()[:20]
        selecoes = _selecionar_tabelas(
            tabelas, f"{chave}_{chave_arquivos}", anterior.get("mapeamento", {})
        )
        col = st.columns(2)
        nome = col[0].text_input(
            "Nome do modelo no Robot", value=anterior.get("nome", ""), key=f"{chave}_nome"
        )
        revisao = col[1].text_input("Revisão do modelo no Robot", key=f"{chave}_revisao")
        with st.expander("Unidades e formato dos números"):
            st.caption(
                "Os cabeçalhos com unidade têm prioridade. Confira as unidades das demais colunas."
            )
            col = st.columns(3)
            anterior_unidades = anterior.get("unidades", {})

            def indice(campo: str, opcoes: Sequence[str]) -> int:
                usada = anterior_unidades.get(campo)
                return opcoes.index(usada) if usada in opcoes else 0

            unidades = robot.Unidades(
                comprimento=col[0].selectbox(
                    "Coordenadas dos nós",
                    list(robot.COMPRIMENTOS),
                    index=indice("comprimento", list(robot.COMPRIMENTOS)),
                    key=f"{chave}_un",
                ),
                posicao=col[1].selectbox(
                    "Posição nas barras",
                    robot.POSICOES,
                    index=indice("posicao", robot.POSICOES),
                    key=f"{chave}_up",
                ),
                decimal_virgula=col[2].selectbox(
                    "Separador decimal em texto",
                    [",", "."],
                    index=int(not anterior_unidades.get("decimal_virgula", True)),
                    key=f"{chave}_ud",
                )
                == ",",
                forca_esforco=col[0].selectbox(
                    "Forças nas barras",
                    list(robot.FORCAS),
                    index=indice("forca_esforco", list(robot.FORCAS)),
                    key=f"{chave}_uf",
                ),
                momento_esforco=col[1].selectbox(
                    "Momentos nas barras",
                    list(robot.MOMENTOS),
                    index=indice("momento_esforco", list(robot.MOMENTOS)),
                    key=f"{chave}_um",
                ),
                forca_reacao=col[0].selectbox(
                    "Forças de reação",
                    list(robot.FORCAS),
                    index=indice("forca_reacao", list(robot.FORCAS)),
                    key=f"{chave}_ur",
                ),
                momento_reacao=col[1].selectbox(
                    "Momentos de reação",
                    list(robot.MOMENTOS),
                    index=indice("momento_reacao", list(robot.MOMENTOS)),
                    key=f"{chave}_urm",
                ),
            )
        confirmado = st.checkbox(
            "Os esforços vieram da aba Valores e as reações estão nos eixos globais (Z para cima)",
            key=f"{chave}_confirmado",
            help="Confira se todas as tabelas correspondem ao modelo e à revisão informados.",
        )
        assinatura = robot.assinatura_da_remessa(selecoes, unidades, nome.strip(), revisao.strip())
        chave_previa = f"{chave}_previa"
        versao = projeto.get(CAMPO_GRAVACAO)
        if st.button("Conferir tabelas", disabled=not confirmado, icon=":material/fact_check:"):
            st.session_state.pop(chave_previa, None)
            try:
                modelo = robot.importar(selecoes, unidades, nome, revisao, anterior=anterior)
            except robot.ImportacaoRobotInvalida as erro:
                st.error(str(erro))
            else:
                modelo["mapeamento"] = {
                    tipo: {
                        "cabecalho": _cabecalho(s.tabela, s.cabecalho),
                        "colunas": dict(s.colunas),
                    }
                    for tipo, s in selecoes.items()
                }
                st.session_state[chave_previa] = (assinatura, versao, modelo)
        previa = st.session_state.get(chave_previa)
        if previa is None or previa[:2] != (assinatura, versao) or not confirmado:
            return
        modelo = previa[2]
        _prever(modelo)
        mesma = robot.ativo(projeto) and modelo["assinatura"] == anterior.get("assinatura")
        if mesma:
            st.info("Esta remessa já está gravada neste projeto.")
        if st.button(
            "Salvar remessa e ativar Robot", type="primary", disabled=mesma, icon=":material/save:"
        ):
            _gravar(
                projeto,
                {robot.CAMPO: modelo, robot.CAMPO_ORIGEM: robot.ROBOT},
                f"Modelo Robot · {modelo['nome']} · revisão {modelo['revisao']}",
                criar_revisao=True,
            )


def _casos(
    projeto: Mapping[str, Any], modelo: Mapping[str, Any], plano: pc.PlanoDeCargas, chave: str
) -> None:
    with st.expander("Casos e combinações", expanded=True):
        origem = st.radio(
            "Origem das combinações para verificar as barras",
            [robot.ROBOT, robot.TOOLKIT],
            index=0 if modelo["origem_combinacoes"] == robot.ROBOT else 1,
            horizontal=True,
            key=f"{chave}_origem",
        )
        st.caption(
            "Classifique as combinações do Robot pelo estado-limite. Para o Toolkit, "
            "associe cada caso simples à ação correspondente do Plano de cargas."
        )
        tabela = pd.DataFrame(
            [
                {
                    "ID Robot": codigo,
                    "Tipo": c["tipo"],
                    "Nome": c["nome"],
                    "Análise no Robot": c.get("analise_robot", ""),
                    "Análise": c["analise"],
                    "Estado-limite": c["estado"],
                    "Ação no plano": c["codigo_plano"],
                    "Definição no Robot": c.get("definicao", ""),
                    "Fatores confirmados": "; ".join(
                        f"{id_}:{fator:g}" for id_, fator in c.get("componentes", {}).items()
                    ),
                }
                for codigo, c in modelo["casos"].items()
            ]
        )
        editada = st.data_editor(
            tabela,
            hide_index=True,
            disabled=["ID Robot", "Tipo", "Nome", "Análise no Robot", "Definição no Robot"],
            key=f"{chave}_casos",
            column_config={
                "Análise": st.column_config.SelectboxColumn(options=list(robot.ANALISES)),
                "Estado-limite": st.column_config.SelectboxColumn(
                    options=["", *comb.TODOS_OS_ESTADOS]
                ),
                "Ação no plano": st.column_config.SelectboxColumn(options=["", *plano.codigos]),
                "Fatores confirmados": st.column_config.TextColumn(
                    help="Em cada combinação, informe os IDs dos casos simples e os fatores. Exemplo 1:1,25; 2:1,5."
                ),
            },
        )
        if st.button(
            "Salvar classificação dos casos", icon=":material/save:", key=f"{chave}_casos_salvar"
        ):
            ajustes = {
                r["ID Robot"]: {
                    "analise": r["Análise"] or "",
                    "estado": r["Estado-limite"] or "",
                    "codigo_plano": r["Ação no plano"] or "",
                }
                for r in editada.to_dict("records")
            }
            try:
                novo = robot.atualizar_casos(modelo, ajustes, origem)
                for r in editada.to_dict("records"):
                    if r["Tipo"] == "Combinações":
                        novo["casos"][r["ID Robot"]]["componentes"] = ri.ler_fatores(
                            r["Fatores confirmados"] or "",
                            modelo["casos"],
                        )
            except robot.ImportacaoRobotInvalida as erro:
                st.error(str(erro))
            else:
                if novo != modelo:
                    _gravar(
                        projeto,
                        {robot.CAMPO: novo},
                        "Robot: classificação dos casos e origem das combinações",
                    )


def _barras(
    projeto: Mapping[str, Any], modelo: Mapping[str, Any], dados: em.EsforcosDoModelo, chave: str
) -> None:
    with st.expander("Perfis e parâmetros de verificação"):
        linhas = []
        for barra, ficha in modelo["barras"].items():
            cfg = dados.membros[barra]
            n1, n2 = ficha["nos"]
            linhas.append(
                {
                    "Barra": barra,
                    "Seção no Robot": ficha["secao"],
                    "Material no Robot": ficha["material"],
                    "L (m)": math.dist(modelo["nos"][str(n1)], modelo["nos"][str(n2)]),
                    "Perfil": cfg.perfil,
                    "Aço": cfg.aco if cfg.aco in vb.ACOS else "",
                    "Tipo": cfg.tipo,
                    "Eixo forte": cfg.eixo_forte,
                    "Lx (m)": cfg.lx_m,
                    "Ly (m)": cfg.ly_m,
                    "Lb (m)": cfg.lb_m,
                }
            )
        st.caption(
            "Confirme o eixo forte nos eixos locais do Robot. Momento 1 corresponde a MY e Momento 2 a MZ."
        )
        comprimentos = ("Lx (m)", "Ly (m)", "Lb (m)")
        editadas = st.data_editor(
            pd.DataFrame(linhas).astype(dict.fromkeys(comprimentos, "Float64")),
            hide_index=True,
            disabled=["Barra", "Seção no Robot", "Material no Robot", "L (m)"],
            key=f"{chave}_barras",
            column_config={
                "Perfil": st.column_config.SelectboxColumn(options=["", *sc.listar_perfis()]),
                "Aço": st.column_config.SelectboxColumn(options=["", *vb.ACOS]),
                "Tipo": st.column_config.SelectboxColumn(options=list(em.TIPOS_DE_BARRA)),
                "Eixo forte": st.column_config.SelectboxColumn(
                    options=["", em.EIXO_M1, em.EIXO_M2]
                ),
                **{
                    c: st.column_config.NumberColumn(min_value=0.001, format="%.3f")
                    for c in comprimentos
                },
            },
        )
        norma = st.selectbox(
            "Norma", list(NORMAS), index=list(NORMAS).index(dados.norma), key=f"{chave}_norma"
        )
        st.caption(
            "Parâmetros por tipo aplicados quando o comprimento correspondente da barra fica vazio."
        )
        parametros = st.data_editor(
            pd.DataFrame(
                [
                    {
                        "Tipo": t,
                        "Lx (m)": p.lx_m,
                        "Ly (m)": p.ly_m,
                        "Lb (m)": p.lb_m,
                        "Cb": p.cb,
                        "B₂": p.b2,
                    }
                    for t in em.TIPOS_DE_BARRA
                    for p in (dados.parametros_do_tipo(t),)
                ]
            ).astype(dict.fromkeys(comprimentos, "Float64")),
            hide_index=True,
            disabled=["Tipo"],
            key=f"{chave}_params",
            column_config={
                c: st.column_config.NumberColumn(min_value=0.001, format="%.3f")
                for c in ("Lx (m)", "Ly (m)", "Lb (m)", "Cb", "B₂")
            },
        )

        def comprimento(valor: Any) -> float | None:
            return None if pd.isna(valor) else float(valor)

        if st.button(
            "Salvar parâmetros das barras", icon=":material/save:", key=f"{chave}_barras_salvar"
        ):
            membros = {
                r["Barra"]: em.ConfiguracaoDoMembro(
                    perfil=r["Perfil"] or "",
                    tipo=r["Tipo"] or "—",
                    eixo_forte=r["Eixo forte"] or "",
                    aco=r["Aço"] or modelo["barras"][r["Barra"]]["material"],
                    lx_m=comprimento(r["Lx (m)"]),
                    ly_m=comprimento(r["Ly (m)"]),
                    lb_m=comprimento(r["Lb (m)"]),
                )
                for r in editadas.to_dict("records")
            }
            novos = {
                r["Tipo"]: replace(
                    dados.parametros_do_tipo(r["Tipo"]),
                    lx_m=comprimento(r["Lx (m)"]),
                    ly_m=comprimento(r["Ly (m)"]),
                    lb_m=comprimento(r["Lb (m)"]),
                    cb=comprimento(r["Cb"]) or 1.0,
                    b2=comprimento(r["B₂"]) or 1.0,
                )
                for r in parametros.to_dict("records")
            }
            novo = robot.com_configuracao(
                modelo, replace(dados, membros=membros, parametros=novos, norma=norma)
            )
            if novo != modelo:
                _gravar(projeto, {robot.CAMPO: novo}, "Robot: parâmetros das barras")


def _relatorio(projeto: Mapping[str, Any], modelo: Mapping[str, Any], chave: str) -> None:
    with st.expander("Relatório do Robot no memorial"):
        atual = modelo.get("relatorio", {})
        documentos = [
            {c: str(doc[c]) for c in ("codigo", "titulo", "revisao")}
            for doc in projeto.get("anexos", [])
            if all(doc.get(c) for c in ("codigo", "titulo", "revisao"))
        ]
        opcoes = [{}] + documentos
        if atual and atual not in documentos:
            opcoes.append(atual)
        i = st.selectbox(
            "Documento de entrada da revisão",
            list(range(len(opcoes))),
            index=opcoes.index(atual),
            format_func=lambda i: (
                f"{opcoes[i]['codigo']} · {opcoes[i]['titulo']} · revisão {opcoes[i]['revisao']}"
                if i
                else "Selecione um documento"
            ),
            key=f"{chave}_relatorio",
        )
        st.page_link(
            "app_pages/gestao_projetos.py",
            label="Cadastrar documento de entrada",
            icon=":material/description:",
        )
        if st.button("Salvar referência", disabled=opcoes[i] == atual, icon=":material/link:"):
            _gravar(
                projeto,
                {robot.CAMPO: {**modelo, "relatorio": opcoes[i]}},
                "Robot: referência do relatório",
            )


def _comparacao(
    projeto: Mapping[str, Any],
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    chave: str,
) -> None:
    painel = st.expander("Comparar Robot e Toolkit", on_change="rerun", key=f"{chave}_comparar")
    if not painel.open:
        return
    with painel:
        estados = st.multiselect(
            "Estados-limite a comparar",
            list(comb.TODOS_OS_ESTADOS),
            default=[comb.ELU_NORMAL],
            key=f"{chave}_estados_comparar",
        )
        if not estados:
            return
        c = ri.comparar(modelo, dados, plano, estados)
        st.write(
            f"{len(c.pares)} pares de combinações · {c.pontos} pontos comparados · "
            f"{len(c.divergencias)} divergências · {c.sem_ponto} pontos sem correspondência"
        )
        for aviso in c.sem_par:
            st.caption(aviso)
        if not c.pares:
            st.info("Confirme os fatores e vincule os casos simples ao Plano de cargas.")
            return
        colunas = [
            "Robot",
            "Toolkit",
            "Barra",
            "Posição",
            "Componente",
            "Valor Robot",
            "Valor Toolkit",
            "Diferença",
            "Tolerância",
        ]
        df = pd.DataFrame(c.divergencias, columns=colunas)
        if c.maior:
            st.dataframe(pd.DataFrame([c.maior], columns=colunas), hide_index=True)
        if c.divergencias:
            st.dataframe(df.head(100), hide_index=True)
            st.download_button(
                "Baixar divergências (CSV)", df.to_csv(index=False), "comparacao_robot_toolkit.csv"
            )
        if c.pontos_sem_par:
            faltantes = pd.DataFrame(c.pontos_sem_par, columns=colunas[:4])
            st.dataframe(faltantes.head(100), hide_index=True)
            st.download_button(
                "Baixar pontos sem par (CSV)",
                faltantes.to_csv(index=False),
                "pontos_sem_par_robot_toolkit.csv",
            )
        registro = criar_registro_tecnico(
            modulo="Comparação Robot e Toolkit",
            modulo_id="comparacao_robot",
            titulo="Comparação dos esforços Robot e Toolkit",
            status="Atenção" if c.divergencias or c.sem_par or c.sem_ponto else "Calculado",
            resumo=f"{len(c.pares)} pares, {len(c.divergencias)} diferenças acima da tolerância.",
            entradas={"estados_limites": ", ".join(estados)},
            resultados={
                "comparacao_robot": c.resumo(),
                "tabelas_memorial": [
                    {
                        "legenda": "Maiores diferenças entre combinações equivalentes.",
                        "cabecalhos": colunas,
                        "linhas": [
                            [str(x) for x in linha]
                            for linha in (c.divergencias[:12] or ((c.maior,) if c.maior else ()))
                        ],
                    }
                ],
            },
            metodo="Comparação por estado-limite, fatores, barra, posição e lado do corte, antes do B₂.",
            alertas=list(c.sem_par),
        )
        botao_registrar_calculo(
            ri.registrar(
                registro, ri.fonte(projeto, finalidade="comparacao", origem="Robot e Toolkit")
            ),
            key=f"{chave}_registrar_comparacao",
            identificar_peca=False,
        )


def _verificacoes(
    projeto: Mapping[str, Any],
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    chave: str,
) -> None:
    st.subheader("Envoltória e verificação das barras")
    st.caption(f"Origem das combinações gravada no projeto · {modelo['origem_combinacoes']}")
    estados = st.multiselect(
        "Estados-limite",
        list(comb.TODOS_OS_ESTADOS),
        default=[comb.ELU_NORMAL],
        key=f"{chave}_estados",
    )
    ultimos = [e for e in estados if e in comb.COMBINACOES_ULTIMAS]
    try:
        preparo = robot.preparar_combinacoes(modelo, dados, plano, estados)
    except robot.ImportacaoRobotInvalida as erro:
        st.warning(str(erro))
        return
    resultado = em.envoltoria(dados, plano, estados, preparo=preparo)
    st.dataframe(
        pd.DataFrame(em.linhas_da_envoltoria(dados, resultado), columns=em.COLUNAS_ENVOLTORIA),
        hide_index=True,
    )
    st.download_button(
        "Baixar envoltória (CSV)", em.csv_da_envoltoria(dados, resultado), "envoltoria_robot.csv"
    )
    if not ultimos:
        st.info("Selecione um ELU para verificar a resistência das barras.")
        return
    preparo_elu = (
        preparo if ultimos == estados else robot.preparar_combinacoes(modelo, dados, plano, ultimos)
    )
    barras, avisos = vb.verificar_barras(dados, plano, ultimos, preparo=preparo_elu)
    for aviso in avisos:
        st.warning(aviso)
    st.dataframe(pd.DataFrame(vb.linhas_da_tabela(barras), columns=vb.COLUNAS), hide_index=True)
    st.download_button(
        "Baixar verificação das barras (CSV)", vb.csv_das_barras(barras), "barras_robot.csv"
    )
    verificadas = {r.membro: r for r in barras if r.linhas}
    if verificadas:
        barra = st.selectbox("Ver o cálculo da barra", list(verificadas), key=f"{chave}_detalhe")
        mostrar_tabela_verificacoes(list(verificadas[barra].linhas))
    origem = ri.fonte(projeto)
    governantes = []
    for barra in barras:
        for nome, ponto, vetor in (preparo_elu.resultados or {}).get(barra.membro, ()):
            if (nome, ponto) == (barra.combinacao, barra.ponto):
                b2 = (
                    1.0
                    if nome in preparo_elu.segunda_ordem
                    else dados.parametros_do_tipo(
                        dados.membros[barra.membro].tipo,
                    ).b2
                )
                governantes.append(
                    {
                        "combinacao": nome,
                        "posicao": f"Barra {barra.membro} · {ponto}",
                        "b2": b2,
                        "vetor": [b2 * v for v in vetor],
                    }
                )
                break
    origem["esforcos"] = governantes
    botao_registrar_calculo(
        ri.registrar(vb.registro_das_barras(barras, dados, ultimos, preparo=preparo_elu), origem),
        key=f"{chave}_registrar",
        identificar_peca=False,
    )


def mostrar_esforcos(projeto: Mapping[str, Any]) -> None:
    chave = f"robot_{projeto['id']}"
    modelo = robot.modelo_do_projeto(projeto)
    _importacao(projeto, modelo, chave)
    if not modelo:
        return
    if not robot.ativo(projeto):
        if st.button("Ativar remessa Robot gravada", icon=":material/swap_horiz:"):
            _gravar(projeto, {robot.CAMPO_ORIGEM: robot.ROBOT}, "Modelo ativo: Autodesk Robot")
        return
    st.subheader(f"{modelo['nome']} · revisão {modelo['revisao']}")
    dados = robot.dados_do_modelo(modelo)
    plano = pc.plano_do_projeto(projeto)
    chave = f"{chave}_{projeto.get(CAMPO_GRAVACAO)}"
    _casos(projeto, modelo, plano, chave)
    _barras(projeto, modelo, dados, chave)
    _relatorio(projeto, modelo, chave)
    _comparacao(projeto, modelo, dados, plano, chave)
    st.page_link(
        "app_pages/reacoes_nas_bases.py",
        label="Quadro de cargas para as fundações",
        icon=":material/foundation:",
    )
    _verificacoes(projeto, modelo, dados, plano, chave)


def mostrar_fundacoes(projeto: Mapping[str, Any]) -> None:
    modelo = robot.modelo_do_projeto(projeto)
    plano = pc.plano_do_projeto(projeto)
    reacoes = rb.montar_do_robot(modelo)
    st.subheader(f"{modelo['nome']} · revisão {modelo['revisao']}")
    st.caption(rb.convencao(reacoes, rb.EIXOS_FUNDACAO))
    for aviso in reacoes.faltam:
        st.warning(aviso)
    if not reacoes.acoes:
        st.info(
            "Importe as reações e confirme o tipo de análise dos casos simples em Esforços do modelo."
        )
        return
    st.dataframe(
        pd.DataFrame(rb.linhas(reacoes, plano), columns=rb.colunas(reacoes)), hide_index=True
    )
    with st.expander("Locação dos apoios e identificação dos casos"):
        st.dataframe(
            pd.DataFrame(rb.linhas_da_locacao(reacoes), columns=rb.COLUNAS_LOCACAO), hide_index=True
        )
        st.dataframe(
            pd.DataFrame(rb.linhas_dos_casos(reacoes, plano), columns=rb.COLUNAS_CASOS),
            hide_index=True,
        )
    st.download_button(
        "Baixar quadro de fundações (Excel)" + (" · preliminar" if reacoes.faltam else ""),
        data=lambda: rb.xlsx(
            reacoes,
            plano,
            projeto=str(projeto["nome"]),
            responsavel=str(projeto.get("responsavel", "")),
        ),
        file_name=rb.nome_do_arquivo(str(projeto["codigo"])),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    botao_registrar_calculo(
        ri.registrar(
            rb.registro_das_reacoes(reacoes, plano),
            ri.fonte(
                projeto,
                finalidade="apoios",
                origem="Casos simples do Robot",
                tipos=("Reações",),
            ),
        ),
        key=f"robot_registrar_fundacoes_{projeto['id']}",
        identificar_peca=False,
    )
