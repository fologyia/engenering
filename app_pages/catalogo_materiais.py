import pandas as pd
import streamlit as st

from components.ui import cabecalho_pagina, configurar_pagina, fronteira_modelo
from core import material_catalog as catalogo

configurar_pagina("Catálogo de materiais", ":material/science:")

cabecalho_pagina(
    "Catálogo de materiais",
    "Materiais permitidos por critério • cadastro próprio • aplicações",
    categoria="Referências",
    icone=":material/science:",
    cor="violet",
    acoes=(
        ("app_pages/materiais_tecnicos.py", "Materiais do projeto", ":material/verified:"),
        ("app_pages/catalogo_perfis.py", "Catálogo de perfis", ":material/view_in_ar:"),
    ),
)
st.caption(
    "Este catálogo é **global**: alimenta a seleção de material em análise "
    "estática, fadiga, flambagem e vigas. Para qualificar um material com "
    "certificado e lote dentro de um projeto, use **Materiais do projeto**."
)

completo = catalogo.catalogo_dataframe()
resumo = catalogo.resumo_do_catalogo()
criterios = catalogo.criterios_carregados()

# ---------------------------------------------------------------------------
# 1. O que está disponível
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("1. Materiais disponíveis")
    metricas = st.columns(min(len(resumo) + 1, 4))
    metricas[0].metric("Materiais no catálogo", len(completo), border=True)
    for coluna, (origem, quantidade) in zip(metricas[1:], resumo.items(), strict=False):
        coluna.metric(origem.split("—")[0].strip()[:24], quantidade, border=True)

    if criterios:
        st.info(
            "Critérios de projeto carregados: " + "; ".join(criterios),
            icon=":material/gavel:",
        )
    colisoes = catalogo.colisoes_entre_catalogos()
    if colisoes:
        # Dois critérios tabelando a mesma designação com valores diferentes é
        # normal — muda com a forma do produto —, mas precisa ser visível:
        # calado, o projetista veria um número sem saber que existe outro.
        st.warning(
            "Designações definidas por mais de um critério de projeto. Vale a "
            "do último catálogo carregado; confira qual se aplica ao seu caso.",
            icon=":material/rule:",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"Designação": nome, "Definida por": " e ".join(origens)}
                    for nome, origens in colisoes.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )

    colunas_filtro = st.columns([2, 2, 2])
    categorias = sorted(completo["categoria"].unique())
    filtro_categoria = colunas_filtro[0].multiselect(
        "Categoria", categorias, key="materiais_filtro_categoria", persist_state="session"
    )
    aplicacoes = catalogo.aplicacoes_disponiveis()
    filtro_aplicacao = colunas_filtro[1].selectbox(
        "Permitido para a aplicação",
        ["— qualquer —", *aplicacoes],
        key="materiais_filtro_aplicacao",
        persist_state="session",
        help=(
            "Filtra pelos materiais que um critério de projeto autoriza para "
            "aquela aplicação — a pergunta que se faz na hora de especificar."
        ),
    )
    busca = colunas_filtro[2].text_input(
        "Buscar pela designação",
        key="materiais_busca",
        persist_state="session",
        placeholder="A572, A36, 1020…",
    )

    visao = completo
    if filtro_categoria:
        visao = visao[visao["categoria"].isin(filtro_categoria)]
    if filtro_aplicacao != "— qualquer —":
        permitidos = {m.nome for m in catalogo.materiais_para(filtro_aplicacao)}
        visao = visao[visao["nome"].isin(permitidos)]
    if busca.strip():
        visao = visao[visao["nome"].str.contains(busca.strip(), case=False, regex=False)]

    if filtro_aplicacao != "— qualquer —":
        st.success(
            f"{len(visao)} material(is) autorizado(s) para **{filtro_aplicacao}** "
            "pelos critérios carregados.",
            icon=":material/check_circle:",
        )
    st.caption(
        f"{len(visao)} de {len(completo)} materiais. A coluna **editavel** indica "
        "quais podem ser alterados ou excluídos."
    )
    st.dataframe(visao, hide_index=True, width="stretch", height=340)
    st.download_button(
        "Baixar o catálogo em CSV",
        data=completo.to_csv(index=False).encode("utf-8-sig"),
        file_name="catalogo_materiais.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="materiais_baixar",
    )

# ---------------------------------------------------------------------------
# 2. Cadastrar ou editar
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("2. Cadastrar ou editar um material")

    editaveis = sorted(completo.loc[completo["editavel"], "nome"])
    alvo = st.selectbox(
        "Partir de",
        ["— novo material —", *editaveis],
        key="materiais_edicao_alvo",
        help="Escolha um material já cadastrado para editá-lo, ou crie um novo.",
    )
    base = catalogo.obter(alvo) if alvo != "— novo material —" else None

    modelo = st.selectbox(
        "Copiar as propriedades de um material existente (opcional)",
        ["— não copiar —", *completo["nome"]],
        key="materiais_modelo",
    )
    if modelo != "— não copiar —" and st.button(
        "Copiar propriedades para os campos",
        icon=":material/content_copy:",
        key="materiais_copiar",
    ):
        copiado = catalogo.obter(modelo)
        st.session_state["materiais_form_nome"] = f"{copiado.nome} (cópia)"
        st.session_state["materiais_form_categoria"] = copiado.categoria
        st.session_state["materiais_form_sy"] = float(copiado.sy_MPa)
        st.session_state["materiais_form_sut"] = float(copiado.sut_MPa)
        st.session_state["materiais_form_origem_prop"] = copiado.origem_propriedades
        st.session_state["materiais_form_criterio"] = copiado.criterio
        st.session_state["materiais_form_aplicacoes"] = "; ".join(copiado.aplicacoes)
        st.session_state["materiais_form_protecao"] = copiado.protecao
        st.session_state["materiais_form_alongamento"] = float(copiado.alongamento_pct)
        st.session_state["materiais_form_observacao"] = copiado.observacao
        st.rerun()

    with st.form("materiais_form", border=False):
        identidade = st.columns([3, 2])
        nome = identidade[0].text_input(
            "Designação",
            value=(base.nome if base else ""),
            key="materiais_form_nome",
            placeholder="ASTM A572 Gr. 50",
        )
        categoria = identidade[1].selectbox(
            "Categoria",
            catalogo.CATEGORIAS,
            index=(
                catalogo.CATEGORIAS.index(base.categoria)
                if base and base.categoria in catalogo.CATEGORIAS
                else 0
            ),
            key="materiais_form_categoria",
        )

        propriedades = st.columns(2)
        sy = propriedades[0].number_input(
            "Limite de escoamento Sy (MPa)",
            min_value=0.0,
            value=float(base.sy_MPa) if base else 250.0,
            step=5.0,
            key="materiais_form_sy",
            help=(
                "Zero significa **sem escoamento definido** — é o caso de "
                "materiais frágeis como o ferro fundido cinzento, que rompe sem "
                "patamar de escoamento."
            ),
        )
        sut = propriedades[1].number_input(
            "Resistência à tração Sut (MPa)",
            min_value=0.001,
            value=float(base.sut_MPa) if base else 400.0,
            step=5.0,
            key="materiais_form_sut",
        )

        alongamento = st.number_input(
            "Alongamento após ruptura (%)",
            min_value=0.0,
            value=float(base.alongamento_pct) if base else 0.0,
            step=1.0,
            key="materiais_form_alongamento",
            help=(
                "Critério usual de ductilidade. Zero significa não informado; "
                "o programa não usa este valor no cálculo, ele acompanha o "
                "material na documentação."
            ),
        )
        origem_propriedades = st.text_input(
            "De onde vêm estas propriedades",
            value=(base.origem_propriedades if base else ""),
            key="materiais_form_origem_prop",
            placeholder="ASTM A572/A572M Gr. 50 — mínimos especificados",
            help=(
                "Norma, certificado ou ensaio. É o que torna o cálculo "
                "rastreável — sem isso o número não tem procedência."
            ),
        )
        criterio = st.text_input(
            "Critério de projeto que autoriza o material (opcional)",
            value=(base.criterio if base else ""),
            key="materiais_form_criterio",
            placeholder="AA-BR-DPST-DR-0001 rev. 1, Tabela 1",
        )
        aplicacoes_texto = st.text_input(
            "Aplicações permitidas (separadas por ponto e vírgula)",
            value=("; ".join(base.aplicacoes) if base else ""),
            key="materiais_form_aplicacoes",
            placeholder="Perfis laminados; Chapas e perfis soldados",
        )
        protecao = st.text_input(
            "Proteção exigida (opcional)",
            value=(base.protecao if base else ""),
            key="materiais_form_protecao",
            placeholder="Galvanização a fogo ASTM A153",
        )
        observacao = st.text_area(
            "Observações",
            value=(base.observacao if base else ""),
            key="materiais_form_observacao",
            height=70,
        )
        gravar = st.form_submit_button(
            "Salvar material",
            type="primary",
            icon=":material/save:",
            width="stretch",
        )

    if gravar:
        try:
            salvo = catalogo.salvar_material(
                {
                    "nome": nome,
                    "categoria": categoria,
                    "Sy_MPa": sy,
                    "Sut_MPa": sut,
                    "alongamento_pct": alongamento,
                    "origem_propriedades": origem_propriedades,
                    "criterio": criterio,
                    "aplicacoes": aplicacoes_texto,
                    "protecao": protecao,
                    "observacao": observacao,
                }
            )
        except catalogo.ErroDeMaterial as erro:
            st.error(str(erro), icon=":material/error:")
        else:
            st.success(
                f"Material **{salvo.nome}** salvo e já disponível nos módulos de "
                "cálculo.",
                icon=":material/check_circle:",
            )
            for aviso in catalogo.conferir_coerencia(salvo):
                st.warning(aviso, icon=":material/warning:")

# ---------------------------------------------------------------------------
# 3. Excluir
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("3. Excluir um material cadastrado")
    if not editaveis:
        st.caption(
            "Ainda não há materiais cadastrados por você. Os da base e os de "
            "critério de projeto não podem ser excluídos — para ajustar um "
            "deles, cadastre um material com a mesma designação, que passa a "
            "valer no seu uso."
        )
    else:
        escolhido = st.selectbox(
            "Material a excluir", editaveis, key="materiais_excluir_alvo"
        )
        detalhe = catalogo.obter(escolhido)
        st.caption(
            f"{detalhe.origem}"
            + (f" · atualizado em {detalhe.atualizado_em}" if detalhe.atualizado_em else "")
        )
        confirmado = st.checkbox(
            f"Confirmo excluir **{escolhido}** do catálogo",
            key="materiais_excluir_confirma",
        )
        if st.button(
            "Excluir material",
            icon=":material/delete:",
            disabled=not confirmado,
            width="stretch",
            key="materiais_excluir",
        ):
            try:
                catalogo.remover_material(escolhido)
            except catalogo.ErroDeMaterial as erro:
                st.error(str(erro), icon=":material/error:")
            else:
                st.session_state.pop("materiais_excluir_confirma", None)
                st.success(
                    f"Material **{escolhido}** excluído.",
                    icon=":material/check_circle:",
                )
                st.rerun()

# ---------------------------------------------------------------------------
# 4. Importar em lote
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("4. Importar uma tabela de materiais")
    st.markdown(
        "Cole a tabela de materiais de um critério de projeto ou de um catálogo. "
        "A primeira linha precisa ter os nomes das colunas."
    )
    colunas = [
        "nome",
        "categoria",
        "Sy_MPa",
        "Sut_MPa",
        "origem_propriedades",
        "criterio",
        "aplicacoes",
        "protecao",
        "alongamento_pct",
        "observacao",
    ]
    st.code("\t".join(colunas), language="text")
    texto = st.text_area(
        "Tabela colada",
        key="materiais_importar_texto",
        height=140,
        placeholder=(
            "nome\tcategoria\tSy_MPa\tSut_MPa\torigem_propriedades\n"
            "ASTM A992\taco\t345\t450\tASTM A992/A992M — mínimos especificados"
        ),
    )
    origem_lote = st.text_input(
        "Origem destes materiais",
        value="Tabela importada",
        key="materiais_importar_origem",
    )
    if st.button(
        "Importar materiais da tabela",
        icon=":material/upload:",
        width="stretch",
        disabled=not texto.strip(),
        key="materiais_importar",
    ):
        try:
            from io import StringIO

            primeira = texto.splitlines()[0]
            separador = "\t" if "\t" in primeira else ";" if ";" in primeira else ","
            tabela = pd.read_csv(StringIO(texto), sep=separador)
        except Exception as erro:  # noqa: BLE001 - erro de formato do usuário
            st.error(f"Não foi possível ler a tabela: {erro}", icon=":material/error:")
        else:
            aceitos, rejeitados = catalogo.importar_lote(
                tabela.to_dict("records"), origem=origem_lote
            )
            if aceitos:
                st.success(
                    f"{len(aceitos)} material(is) cadastrado(s): "
                    + ", ".join(aceitos[:8])
                    + ("…" if len(aceitos) > 8 else ""),
                    icon=":material/check_circle:",
                )
            if rejeitados:
                st.error(
                    f"{len(rejeitados)} linha(s) recusada(s).", icon=":material/error:"
                )
                st.dataframe(
                    pd.DataFrame(rejeitados, columns=["Material", "Motivo"]),
                    hide_index=True,
                    width="stretch",
                )
            if aceitos:
                st.rerun()


fronteira_modelo(
    [
        "Um critério de projeto especifica a designação e a norma, não as propriedades: os valores de Sy e Sut vêm da norma citada e precisam ser confirmados na edição vigente.",
        "As propriedades são valores de referência, não do lote: para rastreabilidade com certificado, qualifique o material em Materiais do projeto.",
        "Efeito de espessura, condição de fornecimento, temperatura de serviço e direção de laminação não são considerados.",
        "Compatibilidade galvânica entre materiais da mesma ligação não é verificada pelo programa.",
    ],
    titulo="O que o catálogo de materiais não garante",
)
