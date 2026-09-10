from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from components.project_tools import contexto_sessao_projeto
from components.ui import cabecalho_pagina
from core.project_store import criar_item, obter_projeto_ativo, salvar_projeto
from core.standards_library import (
    CATALOGO_PADRAO,
    PASTA_NORMAS_PADRAO,
    ArquivoNorma,
    BibliotecaNormasErro,
    assinatura_biblioteca,
    buscar_nos_indices,
    carregar_catalogo,
    catalogo_por_id,
    duplicidades_por_norma,
    extrair_pdf,
    listar_pdfs,
    normalizar_texto,
    resolver_pasta,
    segmentos_catalogo,
)


@st.cache_data(show_spinner=False, max_entries=8)
def _carregar_catalogo_cache(caminho: str, modificado_ns: int) -> list[dict]:
    del modificado_ns
    return carregar_catalogo(caminho)


@st.cache_data(show_spinner=False, max_entries=256)
def _extrair_pdf_cache(
    caminho: str,
    tamanho_bytes: int,
    modificado_ns: int,
    catalogo_modificado_ns: int,
) -> dict:
    del tamanho_bytes, modificado_ns, catalogo_modificado_ns
    return extrair_pdf(caminho, carregar_catalogo())


def _formatar_tamanho(tamanho: int) -> str:
    if tamanho < 1024:
        return f"{tamanho} B"
    if tamanho < 1024**2:
        return f"{tamanho / 1024:.1f} kB"
    return f"{tamanho / 1024**2:.1f} MB"


def _formatar_data(modificado_ns: int) -> str:
    return datetime.fromtimestamp(modificado_ns / 1_000_000_000).strftime(
        "%d/%m/%Y %H:%M"
    )


def _rotulo_norma(item: dict) -> str:
    return f"{item['codigo']} · {item['titulo']}"


def _indice_atual(arquivo: ArquivoNorma) -> dict | None:
    indice = st.session_state["normas_indices"].get(arquivo.caminho)
    if not indice:
        return None
    if indice.get("_fingerprint") != [arquivo.tamanho_bytes, arquivo.modificado_ns]:
        st.session_state["normas_indices"].pop(arquivo.caminho, None)
        return None
    return indice


def _indexar_arquivo(arquivo: ArquivoNorma, catalogo_mtime: int) -> dict:
    indice = _extrair_pdf_cache(
        arquivo.caminho,
        arquivo.tamanho_bytes,
        arquivo.modificado_ns,
        catalogo_mtime,
    )
    indice["_fingerprint"] = [arquivo.tamanho_bytes, arquivo.modificado_ns]
    st.session_state["normas_indices"][arquivo.caminho] = indice
    return indice


def _mostrar_visualizador(caminho: str, *, chave: str) -> None:
    try:
        st.pdf(caminho, height=780, key=chave)
    except Exception as erro:
        st.warning(
            "O visualizador interno não pôde ser carregado. O arquivo continua "
            f"disponível na pasta local. Detalhe: {erro}",
            icon=":material/visibility_off:",
        )


st.set_page_config(
    page_title="Normas técnicas",
    page_icon=":material/library_books:",
    layout="wide",
)

cabecalho_pagina(
    "Biblioteca de normas técnicas",
    "Catálogo por segmento · PDFs locais · busca por página · rastreabilidade",
    categoria="Referências",
    icone=":material/library_books:",
    cor="violet",
    ajuda_modulo="Normas técnicas",
)

st.info(
    "Use o catálogo para localizar os assuntos aplicáveis e o PDF local para "
    "confirmar texto, edição, emendas, tabelas e limites. Esta área não declara "
    "conformidade e não substitui a norma licenciada.",
    icon=":material/gavel:",
)

catalogo_mtime = CATALOGO_PADRAO.stat().st_mtime_ns
try:
    catalogo = _carregar_catalogo_cache(str(CATALOGO_PADRAO), catalogo_mtime)
except BibliotecaNormasErro as erro:
    st.error(str(erro), icon=":material/error:")
    st.stop()

catalogo_ids = catalogo_por_id(catalogo)
segmentos = segmentos_catalogo(catalogo)

pasta_ambiente = os.environ.get("MECANICA_TOOLKIT_NORMAS_DIR")
pasta_inicial = str(Path(pasta_ambiente).expanduser()) if pasta_ambiente else str(PASTA_NORMAS_PADRAO)
st.session_state.setdefault("normas_pasta", pasta_inicial)
st.session_state.setdefault("normas_pasta_digitada", st.session_state["normas_pasta"])
st.session_state.setdefault("normas_indices", {})
st.session_state.setdefault("normas_resultados_busca", [])

with st.container(horizontal=True, vertical_alignment="bottom"):
    with st.container(border=True):
        st.caption("Pasta monitorada")
        st.code(st.session_state["normas_pasta"], language=None)
    with st.popover("Configurar pasta", icon=":material/folder_open:"):
        st.text_input(
            "Caminho da pasta",
            key="normas_pasta_digitada",
            help="A busca inclui todas as subpastas. Também é possível definir "
            "MECANICA_TOOLKIT_NORMAS_DIR antes de iniciar o aplicativo.",
        )
        with st.container(horizontal=True):
            if st.button(
                "Usar pasta",
                type="primary",
                icon=":material/check:",
                key="normas_aplicar_pasta",
            ):
                try:
                    pasta_validada = resolver_pasta(
                        st.session_state["normas_pasta_digitada"]
                    )
                except BibliotecaNormasErro as erro:
                    st.error(str(erro), icon=":material/error:")
                else:
                    st.session_state["normas_pasta"] = str(pasta_validada)
                    st.session_state["normas_indices"] = {}
                    st.session_state["normas_resultados_busca"] = []
                    st.rerun()
            if st.button(
                "Restaurar padrão",
                icon=":material/restart_alt:",
                key="normas_restaurar_pasta",
            ):
                st.session_state["normas_pasta"] = str(PASTA_NORMAS_PADRAO)
                st.session_state["normas_pasta_digitada"] = str(PASTA_NORMAS_PADRAO)
                st.session_state["normas_indices"] = {}
                st.session_state["normas_resultados_busca"] = []
                st.rerun()
    if st.button(
        "Verificar arquivos",
        icon=":material/refresh:",
        key="normas_verificar_arquivos",
        help="Refaz a varredura da pasta. PDFs alterados são reindexados quando necessário.",
    ):
        st.rerun()

try:
    pasta_normas = resolver_pasta(st.session_state["normas_pasta"])
    arquivos = listar_pdfs(pasta_normas, catalogo)
except BibliotecaNormasErro as erro:
    st.error(str(erro), icon=":material/error:")
    st.stop()

assinatura_atual = assinatura_biblioteca(arquivos)
caminhos_atuais = {arquivo.caminho for arquivo in arquivos}
for caminho_indexado in list(st.session_state["normas_indices"]):
    if caminho_indexado not in caminhos_atuais:
        st.session_state["normas_indices"].pop(caminho_indexado, None)

indexados = sum(_indice_atual(arquivo) is not None for arquivo in arquivos)
identificados = sum(arquivo.norma_id is not None for arquivo in arquivos)

with st.container(horizontal=True):
    st.metric(
        ":material/menu_book: Referências-base",
        len(catalogo),
        border=True,
        help="Entradas informativas organizadas por segmento.",
    )
    st.metric(
        ":material/category: Segmentos",
        len(segmentos),
        border=True,
    )
    st.metric(
        ":material/picture_as_pdf: PDFs encontrados",
        len(arquivos),
        border=True,
    )
    st.metric(
        ":material/manage_search: PDFs indexados",
        f"{indexados}/{len(arquivos)}",
        border=True,
        help="Um PDF é indexado quando seu texto foi extraído página a página.",
    )

visao = st.segmented_control(
    "Área da biblioteca",
    ["Catálogo por segmento", "Meus PDFs", "Pesquisar nos PDFs", "Como organizar"],
    default="Catálogo por segmento",
    required=True,
    width="stretch",
    key="normas_visao",
)

if visao == "Catálogo por segmento":
    with st.container(border=True):
        st.badge("Base orientativa", icon=":material/account_tree:", color="blue")
        st.subheader("Localize a família normativa antes de calcular")
        st.caption(
            "Os resumos indicam onde começar. A aplicabilidade depende do contrato, "
            "produto, local de instalação, edição e autoridade competente."
        )
        with st.container(horizontal=True, vertical_alignment="bottom"):
            filtro_segmentos = st.multiselect(
                "Segmentos",
                segmentos,
                placeholder="Todos os segmentos",
                key="normas_filtro_segmentos",
            )
            filtro_catalogo = st.text_input(
                "Buscar no catálogo",
                placeholder="Ex.: fadiga, parafuso, vento, soldagem",
                icon=":material/search:",
                key="normas_filtro_catalogo",
            )

    termo_catalogo = normalizar_texto(filtro_catalogo)
    catalogo_filtrado = []
    for item in catalogo:
        if filtro_segmentos and item["segmento"] not in filtro_segmentos:
            continue
        campos = " ".join(
            [
                item["codigo"],
                item["titulo"],
                item["segmento"],
                item["aplicacao"],
                " ".join(item["palavras_chave"]),
            ]
        )
        if termo_catalogo and termo_catalogo not in normalizar_texto(campos):
            continue
        catalogo_filtrado.append(item)

    if not catalogo_filtrado:
        st.warning(
            "Nenhuma referência corresponde aos filtros atuais.",
            icon=":material/search_off:",
        )
    else:
        tabela_catalogo = pd.DataFrame(
            [
                {
                    "Código": item["codigo"],
                    "Segmento": item["segmento"],
                    "Assunto principal": item["titulo"],
                    "Módulos relacionados": ", ".join(item["modulos"]),
                    "Fonte oficial": item["fonte_url"],
                }
                for item in catalogo_filtrado
            ]
        )
        st.dataframe(
            tabela_catalogo,
            hide_index=True,
            column_config={
                "Código": st.column_config.TextColumn("Código", pinned=True),
                "Fonte oficial": st.column_config.LinkColumn(
                    "Fonte oficial",
                    display_text="Consultar",
                    help="Página do organismo emissor ou catálogo oficial.",
                ),
            },
        )

        norma_escolhida = st.selectbox(
            "Abrir ficha da referência",
            catalogo_filtrado,
            format_func=_rotulo_norma,
            key="normas_catalogo_selecionada",
        )
        with st.container(border=True):
            with st.container(horizontal=True):
                st.badge(
                    norma_escolhida["segmento"],
                    icon=":material/category:",
                    color="violet",
                )
                for modulo in norma_escolhida["modulos"][:3]:
                    st.badge(modulo, color="gray")
            st.subheader(norma_escolhida["codigo"])
            st.markdown(f"**{norma_escolhida['titulo']}**")
            st.markdown(norma_escolhida["aplicacao"])
            consulta, conferencia = st.columns(2)
            with consulta:
                st.markdown("**Quando consultar**")
                st.write(norma_escolhida["quando_consultar"])
            with conferencia:
                st.markdown("**Pontos que merecem conferência**")
                st.markdown(
                    "\n".join(
                        f"- {ponto}" for ponto in norma_escolhida["pontos_chave"]
                    )
                )
            st.warning(
                norma_escolhida.get(
                    "nota_edicao",
                    "Confirme a edição e as emendas aplicáveis.",
                ),
                icon=":material/history_edu:",
            )
            st.link_button(
                "Abrir fonte oficial",
                norma_escolhida["fonte_url"],
                icon=":material/open_in_new:",
            )
            projeto_ativo = obter_projeto_ativo()
            if projeto_ativo is not None:
                ja_vinculada = any(
                    str(item.get("codigo", "")).strip().lower()
                    == norma_escolhida["codigo"].strip().lower()
                    for item in projeto_ativo.get("normas", [])
                )
                if ja_vinculada:
                    st.caption(
                        f":material/check_circle: Referência já vinculada a {projeto_ativo['codigo']}."
                    )
                elif st.button(
                    "Adicionar à matriz normativa do projeto ativo",
                    icon=":material/playlist_add:",
                    key=f"vincular_norma_{norma_escolhida['id']}",
                ):
                    projeto_ativo["normas"].append(
                        criar_item(
                            codigo=norma_escolhida["codigo"],
                            edicao="",
                            escopo=norma_escolhida["aplicacao"],
                            obrigatoria=False,
                            conferida=False,
                            fonte=norma_escolhida["fonte_url"],
                        )
                    )
                    salvo = salvar_projeto(
                        projeto_ativo,
                        motivo=f"Referência {norma_escolhida['codigo']} adicionada à matriz normativa",
                    )
                    st.session_state["projeto_ativo"] = contexto_sessao_projeto(salvo)
                    st.rerun()
            else:
                st.caption("Abra um projeto permanente para vincular esta referência à matriz normativa.")

elif visao == "Meus PDFs":
    st.subheader("Arquivos encontrados na pasta monitorada")
    if not arquivos:
        with st.container(border=True):
            st.badge("Biblioteca vazia", icon=":material/folder_off:", color="orange")
            st.subheader("Adicione seus PDFs para começar")
            st.markdown(
                "Copie os arquivos para a pasta indicada acima. A varredura é "
                "recursiva, então você pode criar subpastas por segmento."
            )
            st.code(str(pasta_normas), language=None)
            st.caption(
                "Depois clique em **Verificar arquivos**. O catálogo por segmento "
                "continua disponível mesmo sem PDFs."
            )
    else:
        tabela_arquivos = pd.DataFrame(
            [
                {
                    "Arquivo": arquivo.caminho_relativo,
                    "Norma provável": arquivo.codigo,
                    "Segmento": arquivo.segmento,
                    "Tamanho": _formatar_tamanho(arquivo.tamanho_bytes),
                    "Modificado": _formatar_data(arquivo.modificado_ns),
                    "Indexado": "Sim" if _indice_atual(arquivo) else "Não",
                }
                for arquivo in arquivos
            ]
        )
        st.dataframe(
            tabela_arquivos,
            hide_index=True,
            column_config={
                "Arquivo": st.column_config.TextColumn("Arquivo", pinned=True),
            },
        )
        if identificados < len(arquivos):
            st.caption(
                f"{len(arquivos) - identificados} arquivo(s) ainda não foram "
                "associados ao catálogo pelo nome. A leitura das primeiras páginas "
                "faz uma segunda tentativa."
            )

        duplicidades = duplicidades_por_norma(arquivos)
        if duplicidades:
            with st.expander(
                f"Possíveis edições duplicadas ({len(duplicidades)})",
                icon=":material/content_copy:",
            ):
                for norma_id, nomes in duplicidades.items():
                    codigo = catalogo_ids.get(norma_id, {}).get("codigo", norma_id)
                    st.markdown(f"**{codigo}**")
                    st.markdown("\n".join(f"- `{nome}`" for nome in nomes))
                st.caption(
                    "Mantenha a edição contratual claramente identificada. Não apague "
                    "edições antigas sem verificar a rastreabilidade do projeto."
                )

        arquivo_escolhido = st.selectbox(
            "Selecione um PDF",
            arquivos,
            format_func=lambda item: f"{item.caminho_relativo} · {item.codigo}",
            key="normas_pdf_selecionado",
        )
        indice = _indice_atual(arquivo_escolhido)
        with st.container(horizontal=True):
            if st.button(
                "Ler e indexar este PDF",
                type="primary",
                icon=":material/document_scanner:",
                key="normas_indexar_selecionado",
            ):
                try:
                    with st.spinner("Extraindo texto página a página…"):
                        indice = _indexar_arquivo(arquivo_escolhido, catalogo_mtime)
                except BibliotecaNormasErro as erro:
                    st.error(str(erro), icon=":material/error:")
                else:
                    st.success(
                        f"{arquivo_escolhido.nome} foi indexado.",
                        icon=":material/check_circle:",
                    )
            mostrar_pdf = st.toggle(
                "Mostrar PDF",
                value=False,
                key=f"normas_mostrar_pdf_{arquivo_escolhido.modificado_ns}",
            )

        if indice:
            with st.container(horizontal=True):
                st.metric("Páginas", indice["numero_paginas"], border=True)
                st.metric(
                    "Páginas com texto",
                    indice["paginas_com_texto"],
                    border=True,
                )
                st.metric(
                    "Cobertura extraível",
                    f"{indice['cobertura_texto']:.0%}",
                    border=True,
                )
                st.metric("Norma identificada", indice["codigo"], border=True)
            with st.container(border=True):
                st.caption(
                    f"SHA-256: `{indice['sha256']}` · "
                    f"Título interno: {indice['titulo_pdf'] or 'não informado'}"
                )
                if indice["necessita_ocr"]:
                    st.warning(
                        "Grande parte do PDF parece ser imagem digitalizada. A busca "
                        "pode ficar incompleta até que o arquivo receba OCR.",
                        icon=":material/document_scanner:",
                    )
                if indice["erros_paginas"]:
                    st.warning(
                        f"{len(indice['erros_paginas'])} página(s) tiveram falha de "
                        "extração. Consulte o visualizador e o arquivo original.",
                        icon=":material/warning:",
                    )
        else:
            st.caption(
                "O PDF ainda não foi lido. A indexação guarda texto, página, hash e "
                "diagnóstico de OCR na sessão atual."
            )

        if mostrar_pdf:
            _mostrar_visualizador(
                arquivo_escolhido.caminho,
                chave=f"normas_viewer_{arquivo_escolhido.modificado_ns}",
            )

elif visao == "Pesquisar nos PDFs":
    st.subheader("Busca rastreável no conteúdo das normas")
    st.caption(
        "Os resultados mostram o arquivo e a página física do PDF. Confira o "
        "contexto completo, as definições e as exceções antes de usar um requisito."
    )

    faltantes = [arquivo for arquivo in arquivos if _indice_atual(arquivo) is None]
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(
                "Índice local",
                icon=":material/manage_search:",
                color="green" if not faltantes and arquivos else "orange",
            )
            st.caption(
                f"{indexados} de {len(arquivos)} PDF(s) prontos para pesquisa."
            )
        if arquivos and st.button(
            "Indexar ou atualizar toda a biblioteca",
            type="primary",
            icon=":material/sync:",
            key="normas_indexar_todos",
        ):
            falhas: list[str] = []
            barra = st.progress(0, text="Preparando a biblioteca…")
            with st.status(
                "Lendo os PDFs",
                expanded=True,
            ) as estado:
                for posicao, arquivo in enumerate(arquivos, start=1):
                    estado.write(f"{posicao}/{len(arquivos)} · {arquivo.caminho_relativo}")
                    try:
                        _indexar_arquivo(arquivo, catalogo_mtime)
                    except BibliotecaNormasErro as erro:
                        falhas.append(f"{arquivo.caminho_relativo}: {erro}")
                    barra.progress(
                        posicao / len(arquivos),
                        text=f"Indexados {posicao}/{len(arquivos)} arquivos",
                    )
                if falhas:
                    estado.update(
                        label="Índice concluído com pendências",
                        state="error",
                        expanded=True,
                    )
                    for falha in falhas:
                        estado.write(f"- {falha}")
                else:
                    estado.update(
                        label="Biblioteca indexada",
                        state="complete",
                        expanded=False,
                    )
            st.session_state["normas_assinatura_indexada"] = assinatura_atual
            st.rerun()

    if not arquivos:
        st.warning(
            "Adicione PDFs à pasta monitorada para pesquisar o conteúdo.",
            icon=":material/folder_off:",
        )
    elif faltantes:
        st.warning(
            f"A pesquisa usará somente {indexados} PDF(s). Ainda faltam "
            f"{len(faltantes)} arquivo(s) no índice.",
            icon=":material/pending:",
        )

    with st.form("normas_form_busca"):
        consulta = st.text_input(
            "Termos de busca",
            placeholder="Ex.: tensão admissível, parafuso crítico, inspeção visual",
            icon=":material/search:",
        )
        segmentos_busca = st.multiselect(
            "Restringir aos segmentos",
            segmentos + ["A classificar"],
            placeholder="Todos os segmentos indexados",
        )
        limite = st.slider("Máximo de resultados", 10, 200, 50, step=10)
        pesquisar = st.form_submit_button(
            "Pesquisar",
            type="primary",
            icon=":material/manage_search:",
        )

    if pesquisar:
        indices_validos = [
            indice
            for arquivo in arquivos
            if (indice := _indice_atual(arquivo)) is not None
        ]
        if len(normalizar_texto(consulta)) < 2:
            st.warning("Informe pelo menos dois caracteres para pesquisar.")
        elif not indices_validos:
            st.warning(
                "Indexe pelo menos um PDF antes de pesquisar.",
                icon=":material/pending:",
            )
        else:
            st.session_state["normas_resultados_busca"] = buscar_nos_indices(
                indices_validos,
                consulta,
                segmentos=segmentos_busca,
                limite=limite,
            )

    resultados = st.session_state["normas_resultados_busca"]
    if resultados:
        st.success(
            f"{len(resultados)} resultado(s) rastreado(s) por arquivo e página.",
            icon=":material/check_circle:",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Norma": item["codigo"],
                        "Arquivo": item["arquivo"],
                        "Página PDF": item["pagina"],
                        "Ocorrências": item["ocorrencias"],
                        "Trecho": item["trecho"],
                    }
                    for item in resultados
                ]
            ),
            hide_index=True,
            column_config={
                "Norma": st.column_config.TextColumn("Norma", pinned=True),
                "Página PDF": st.column_config.NumberColumn(format="%d"),
                "Ocorrências": st.column_config.NumberColumn(format="%d"),
            },
        )

        resultado_escolhido = st.selectbox(
            "Inspecionar resultado",
            resultados,
            format_func=lambda item: (
                f"{item['codigo']} · {item['arquivo']} · página {item['pagina']}"
            ),
            key="normas_resultado_selecionado",
        )
        with st.container(border=True):
            st.badge(
                resultado_escolhido["segmento"],
                icon=":material/category:",
                color="violet",
            )
            st.subheader(
                f"{resultado_escolhido['codigo']} · página "
                f"{resultado_escolhido['pagina']}"
            )
            st.write(resultado_escolhido["trecho"])
            st.caption(
                "A página indicada é a posição física no PDF e pode ser diferente "
                "da numeração impressa no rodapé da norma."
            )
            if st.toggle(
                "Abrir o PDF deste resultado",
                key=(
                    "normas_abrir_resultado_"
                    f"{resultado_escolhido['pagina']}_"
                    f"{Path(resultado_escolhido['caminho']).stat().st_mtime_ns}"
                ),
            ):
                _mostrar_visualizador(
                    resultado_escolhido["caminho"],
                    chave=(
                        "normas_viewer_resultado_"
                        f"{resultado_escolhido['pagina']}_"
                        f"{Path(resultado_escolhido['caminho']).stat().st_mtime_ns}"
                    ),
                )
    elif pesquisar:
        st.info(
            "Nenhuma página indexada contém todos os termos informados.",
            icon=":material/search_off:",
        )

else:
    st.subheader("Organização, atualização e uso responsável")
    organizacao, rotina = st.columns(2)
    with organizacao:
        with st.container(border=True, height="stretch"):
            st.badge("Pastas", icon=":material/folder_copy:", color="blue")
            st.subheader("Estrutura recomendada")
            st.code(
                """normas_pdf/
├── estruturas_aco/
├── fadiga_materiais/
├── parafusos/
├── seguranca_maquinas/
├── soldagem/
└── vasos_tubulacoes/""",
                language=None,
            )
            st.caption("A varredura inclui automaticamente todas as subpastas.")
    with rotina:
        with st.container(border=True, height="stretch"):
            st.badge("Rastreabilidade", icon=":material/fact_check:", color="green")
            st.subheader("Nomeie cada edição")
            st.code(
                "ORGAO_CODIGO_ANO_TITULO_CURTO.pdf",
                language=None,
            )
            st.markdown(
                """
                - mantenha o ano e a emenda no nome;
                - registre qual edição foi usada no memorial;
                - preserve a fonte oficial e a licença;
                - separe documentos cancelados ou substituídos;
                - não confunda norma, regulamento, manual e especificação interna.
                """
            )

    with st.container(border=True):
        st.badge("Fluxo de conferência", icon=":material/checklist:", color="violet")
        st.subheader("Antes de usar um requisito")
        st.markdown(
            """
            1. Confirme se a norma está citada no contrato, desenho ou especificação.
            2. Verifique edição, emendas, erratas e data de vigência.
            3. Leia escopo, exclusões, definições e documentos referenciados.
            4. Identifique a situação de projeto, classe, categoria e coeficientes.
            5. Registre arquivo, página, item, hipótese e responsável pela decisão.
            6. Revise possíveis conflitos com legislação e requisitos do cliente.
            """
        )

    st.warning(
        "A extração automática pode perder fórmulas, símbolos, notas de tabela, "
        "figuras e páginas digitalizadas. Sempre faça a conferência visual no PDF.",
        icon=":material/warning:",
    )

st.caption(
    "Os PDFs permanecem na sua pasta local. O aplicativo guarda o índice apenas "
    "na sessão e usa o hash SHA-256 para ajudar na rastreabilidade do arquivo lido."
)
