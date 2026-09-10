import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.ui import cabecalho_pagina, fronteira_modelo
from core import section_catalog as catalogo
from core import steel_sections as secoes

st.set_page_config(
    page_title="Catálogo de perfis",
    page_icon=":material/view_in_ar:",
    layout="wide",
)

CHAVE_EDICAO = "perfis_em_edicao"

cabecalho_pagina(
    "Catálogo de perfis",
    "Perfis de referência • cadastro próprio • importação de tabelas de bitolas",
    categoria="Referências",
    icone=":material/view_in_ar:",
    cor="violet",
    acoes=(
        ("app_pages/vigas_eixos.py", "Vigas e eixos", ":material/linear_scale:"),
        ("app_pages/estruturas_aco.py", "Estruturas de aço", ":material/domain:"),
    ),
)
st.caption(
    "Os perfis cadastrados aqui ficam disponíveis em **todos** os módulos que "
    "usam seção: vigas e eixos, flambagem e estruturas de aço."
)


def tabela_do_catalogo() -> pd.DataFrame:
    return catalogo.catalogo_dataframe()


completo = tabela_do_catalogo()
resumo = catalogo.resumo_do_catalogo()

with st.container(border=True):
    st.subheader("1. O que já está disponível")
    metricas = st.columns(min(len(resumo) + 1, 4))
    metricas[0].metric("Perfis no catálogo", len(completo), border=True)
    for coluna, (origem, quantidade) in zip(metricas[1:], resumo.items(), strict=False):
        coluna.metric(origem.split("—")[0].strip()[:22], quantidade, border=True)

    familias = sorted(completo["familia"].unique())
    escolhidas = st.multiselect(
        "Filtrar por família",
        familias,
        default=[],
        key="perfis_filtro_familia",
        persist_state="session",
    )
    busca = st.text_input(
        "Buscar pelo nome",
        key="perfis_busca",
        persist_state="session",
        placeholder="W 250, HP 310, tubo…",
    )
    visao = completo
    if escolhidas:
        visao = visao[visao["familia"].isin(escolhidas)]
    if busca.strip():
        visao = visao[visao["nome"].str.contains(busca.strip(), case=False, regex=False)]
    st.caption(
        f"{len(visao)} de {len(completo)} perfis. A coluna **editavel** indica "
        "quais podem ser alterados ou excluídos."
    )
    st.dataframe(visao, hide_index=True, width="stretch", height=340)
    st.download_button(
        "Baixar o catálogo em CSV",
        data=completo.to_csv(index=False).encode("utf-8-sig"),
        file_name="catalogo_perfis.csv",
        mime="text/csv",
        icon=":material/download:",
        width="stretch",
        key="perfis_baixar",
    )


# ---------------------------------------------------------------------------
# 2. Cadastrar ou editar
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("2. Cadastrar ou editar um perfil")

    editaveis = sorted(completo.loc[completo["editavel"], "nome"])
    opcoes = ["— novo perfil —", *editaveis]
    if st.session_state.get(CHAVE_EDICAO) not in opcoes:
        st.session_state[CHAVE_EDICAO] = "— novo perfil —"
    alvo = st.selectbox(
        "Partir de",
        opcoes,
        key=CHAVE_EDICAO,
        help="Escolha um perfil já cadastrado para editá-lo, ou crie um novo.",
    )
    base = None
    if alvo != "— novo perfil —":
        base = catalogo.obter(alvo)

    modelo = st.selectbox(
        "Copiar as medidas de um perfil existente (opcional)",
        ["— não copiar —", *completo["nome"]],
        key="perfis_modelo",
        help=(
            "Preenche os campos com os valores de um perfil do catálogo, para "
            "você ajustar só o que muda."
        ),
    )
    if modelo != "— não copiar —" and st.button(
        "Copiar medidas para os campos",
        icon=":material/content_copy:",
        key="perfis_copiar",
    ):
        copiado = catalogo.obter(modelo).perfil
        st.session_state["perfis_form_nome"] = f"{copiado.nome} (cópia)"
        st.session_state["perfis_form_familia"] = copiado.familia
        st.session_state["perfis_form_descricao"] = copiado.descricao
        for campo, _rotulo, _unidade in catalogo.CAMPOS_NUMERICOS:
            st.session_state[f"perfis_form_{campo}"] = float(getattr(copiado, campo))
        st.rerun()

    if base is not None:
        st.session_state.setdefault("perfis_form_nome", base.perfil.nome)

    with st.form("perfis_form", border=False):
        colunas_identidade = st.columns([2, 2, 1])
        nome = colunas_identidade[0].text_input(
            "Nome do perfil",
            value=(base.perfil.nome if base else ""),
            key="perfis_form_nome",
            placeholder="W 200 x 22,5",
        )
        familia = colunas_identidade[1].text_input(
            "Família",
            value=(base.perfil.familia if base else "Personalizado"),
            key="perfis_form_familia",
            placeholder="W (mesa larga)",
        )
        origem = colunas_identidade[2].text_input(
            "Origem",
            value=(base.origem if base else catalogo.ORIGEM_USUARIO),
            key="perfis_form_origem",
        )

        valores: dict[str, float] = {}
        grade = st.columns(3)
        for indice, (campo, rotulo, unidade) in enumerate(catalogo.CAMPOS_NUMERICOS):
            padrao = float(getattr(base.perfil, campo)) if base else 0.0
            valores[campo] = grade[indice % 3].number_input(
                f"{rotulo} ({unidade})",
                min_value=0.0,
                value=padrao,
                step=1.0,
                format="%.4f",
                key=f"perfis_form_{campo}",
            )

        descricao = st.text_input(
            "Descrição",
            value=(base.perfil.descricao if base else ""),
            key="perfis_form_descricao",
            placeholder="Como o perfil é identificado no desenho ou na compra",
        )
        observacoes = st.text_area(
            "Observações (catálogo, edição, data de conferência)",
            value=(base.observacoes if base else ""),
            key="perfis_form_observacoes",
            height=70,
        )
        gravar = st.form_submit_button(
            "Salvar perfil",
            type="primary",
            icon=":material/save:",
            width="stretch",
        )

    if gravar:
        dados = {"nome": nome, "familia": familia, "descricao": descricao, **valores}
        try:
            salvo = catalogo.salvar_perfil(
                dados, origem=origem, observacoes=observacoes
            )
        except catalogo.ErroDeCatalogo as erro:
            st.error(str(erro), icon=":material/error:")
        else:
            avisos = catalogo.conferir_coerencia(salvo.perfil)
            st.success(
                f"Perfil **{salvo.perfil.nome}** salvo e já disponível nos módulos "
                "de cálculo.",
                icon=":material/check_circle:",
            )
            for aviso in avisos:
                st.warning(aviso, icon=":material/warning:")
            if not avisos:
                st.caption(
                    ":material/verified: As relações internas do perfil "
                    "(Z/W, massa e área, eixos) são coerentes."
                )


# ---------------------------------------------------------------------------
# 3. Excluir
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("3. Excluir um perfil cadastrado")
    if not editaveis:
        st.caption(
            "Ainda não há perfis cadastrados por você. Perfis de referência e do "
            "catálogo embutido não podem ser excluídos — para ajustar um deles, "
            "cadastre um perfil com o mesmo nome, que passa a valer no seu uso."
        )
    else:
        escolhido = st.selectbox(
            "Perfil a excluir",
            editaveis,
            key="perfis_excluir_alvo",
        )
        detalhe = catalogo.obter(escolhido)
        st.caption(
            f"{detalhe.origem}"
            + (f" · atualizado em {detalhe.atualizado_em}" if detalhe.atualizado_em else "")
        )
        confirmado = st.checkbox(
            f"Confirmo excluir **{escolhido}** do catálogo",
            key="perfis_excluir_confirma",
        )
        if st.button(
            "Excluir perfil",
            icon=":material/delete:",
            disabled=not confirmado,
            width="stretch",
            key="perfis_excluir",
        ):
            try:
                catalogo.remover_perfil(escolhido)
            except catalogo.ErroDeCatalogo as erro:
                st.error(str(erro), icon=":material/error:")
            else:
                st.session_state.pop("perfis_excluir_confirma", None)
                st.success(
                    f"Perfil **{escolhido}** excluído.", icon=":material/check_circle:"
                )
                st.rerun()


# ---------------------------------------------------------------------------
# 4. Importar em lote
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader("4. Importar uma tabela de bitolas")
    st.markdown(
        "Cole uma tabela (do Excel, de um catálogo ou de um CSV) para cadastrar "
        "vários perfis de uma vez. A primeira linha precisa conter os nomes das "
        "colunas; as unidades são as internas do programa (mm, mm², mm⁴)."
    )
    colunas_aceitas = ["nome", "familia", "descricao"] + [
        campo for campo, _r, _u in catalogo.CAMPOS_NUMERICOS
    ]
    st.code("\t".join(colunas_aceitas), language="text")

    exemplo = (
        "nome\tfamilia\tarea_mm2\tix_mm4\tiy_mm4\taltura_mm\tlargura_mm\t"
        "espessura_alma_mm\tespessura_mesa_mm\tmassa_kg_m\n"
        "W 200 x 19,3\tW (mesa larga)\t2510\t16500000\t1140000\t203\t102\t5.8\t6.5\t19.3"
    )
    texto = st.text_area(
        "Tabela colada",
        key="perfis_importar_texto",
        height=150,
        placeholder=exemplo,
    )
    origem_lote = st.text_input(
        "Origem destes perfis",
        value="Tabela importada",
        key="perfis_importar_origem",
        help="Fica gravada em cada perfil e aparece no catálogo.",
    )
    if st.button(
        "Importar perfis da tabela",
        icon=":material/upload:",
        width="stretch",
        disabled=not texto.strip(),
        key="perfis_importar",
    ):
        try:
            from io import StringIO

            separador = "\t" if "\t" in texto.splitlines()[0] else ";" if ";" in texto.splitlines()[0] else ","
            tabela = pd.read_csv(StringIO(texto), sep=separador)
        except Exception as erro:  # noqa: BLE001 - erro de formato do usuário
            st.error(f"Não foi possível ler a tabela: {erro}", icon=":material/error:")
        else:
            desconhecidas = [c for c in tabela.columns if c not in colunas_aceitas]
            if desconhecidas:
                st.warning(
                    "Colunas ignoradas por não fazerem parte do perfil: "
                    + ", ".join(desconhecidas),
                    icon=":material/warning:",
                )
            aceitos, rejeitados = catalogo.importar_lote(
                tabela.to_dict("records"), origem=origem_lote
            )
            if aceitos:
                st.success(
                    f"{len(aceitos)} perfil(is) cadastrado(s): "
                    + ", ".join(aceitos[:8])
                    + ("…" if len(aceitos) > 8 else ""),
                    icon=":material/check_circle:",
                )
            if rejeitados:
                st.error(
                    f"{len(rejeitados)} linha(s) recusada(s).", icon=":material/error:"
                )
                st.dataframe(
                    pd.DataFrame(rejeitados, columns=["Perfil", "Motivo"]),
                    hide_index=True,
                    width="stretch",
                )
            if aceitos:
                st.rerun()


fronteira_modelo(
    [
        "As propriedades cadastradas são usadas como informadas: o programa confere a coerência interna, mas não substitui a tabela do fabricante.",
        "Raios de concordância, tolerâncias de laminação e variações entre fabricantes não são modelados.",
        "Perfis de referência distribuídos com o programa são orientativos — confirme a bitola no catálogo vigente antes de comprar ou detalhar.",
    ],
    titulo="O que o cadastro de perfis não garante",
)

st.caption(
    f"Catálogo embutido: {len(secoes.CATALOGO_PERFIS)} perfis geométricos. "
    "Catálogos de referência e perfis próprios ficam na pasta `data/`."
)
