"""Roteiro do projeto: a sequência de sempre, do projeto ativo ao memorial, com o SolidWorks."""

from __future__ import annotations

import streamlit as st

from components.robustez import secao_protegida
from components.ui import cabecalho_pagina, configurar_pagina
from core import roteiro as rt
from core import verificacoes_do_projeto as vdp
from core.project_store import obter_projeto_ativo

AJUDA = {
    "proximo": "O primeiro passo que ainda falta no projeto ativo: continue por ele.",
    "fase": (
        "Os passos desta fase, na ordem. Verde: feito no projeto ativo. Cinza: pendente. "
        "Azul: feito no SolidWorks (o programa só vê quando o passo seguinte acontece)."
    ),
    "complementares": (
        "As verificações de estrutura metálica que não estão no fluxo do modelo: forças na alma, "
        "monovia, travamentos, viga mista, furos na alma, terças, ligação rígida, nós de tubos, "
        "fadiga e incêndio. O programa olha o plano de cargas, a lista de material e os "
        "registros do projeto e diz quais o projeto pede, por quê, e quais já estão registradas."
    ),
    "situacao_complementares": (
        "Registrada: já há cálculo dela no projeto. Indicada pelo projeto: os dados do projeto "
        "mostram que ela se aplica (o motivo está ao lado). Quando houver: só se a obra tiver o "
        "caso descrito."
    ),
}

configurar_pagina("Roteiro do projeto", ":material/format_list_numbered:")
cabecalho_pagina(
    "Roteiro do projeto",
    "A sequência de sempre, do projeto ativo ao memorial: o que fazer em cada passo, onde (página "
    "do programa ou SolidWorks), que arquivo entra e que arquivo sai.",
    categoria="Gestão industrial",
    icone=":material/format_list_numbered:",
    cor="blue",
)

projeto = obter_projeto_ativo()
situacoes = rt.situacoes(projeto)
proximo = rt.proximo_passo(situacoes)

with secao_protegida("Próximo passo"):
    if proximo is not None:
        passo = rt.PASSOS[proximo - 1]
        st.info(
            f"**Próximo passo: {passo.numero}. {passo.titulo}** — {passo.onde}.",
            icon=":material/arrow_forward:",
        )
        if passo.pagina:
            st.page_link(passo.pagina, label=f"Abrir {passo.onde}", icon=":material/open_in_new:")
    else:
        st.success(
            "Todos os passos com rastro no projeto estão feitos: limpe os registros e gere o "
            "memorial (passos 13 e 14).",
            icon=":material/check_circle:",
        )


def _complementares() -> None:
    sugestoes = vdp.sugestoes(projeto)
    contagem = vdp.resumo(sugestoes)
    with st.container(border=True), secao_protegida("Verificações complementares"):
        st.subheader("Verificações complementares de estrutura metálica",
                     help=AJUDA["complementares"])  # fmt: skip
        st.caption(
            f"{contagem[vdp.REGISTRADA]} registrada(s) · {contagem[vdp.INDICADA]} indicada(s) "
            f"pelo projeto · {contagem[vdp.SE_HOUVER]} só quando houver o caso."
        )
        cores = {vdp.REGISTRADA: "green", vdp.INDICADA: "orange", vdp.SE_HOUVER: "gray"}
        icones = {vdp.REGISTRADA: ":material/check_circle:", vdp.INDICADA: ":material/flag:",
                  vdp.SE_HOUVER: ":material/radio_button_unchecked:"}  # fmt: skip
        ordem = {vdp.INDICADA: 0, vdp.REGISTRADA: 1, vdp.SE_HOUVER: 2}
        for sug in sorted(sugestoes, key=lambda x: ordem[x.situacao]):
            v = sug.verificacao
            linha = st.columns([2, 3])
            with linha[0]:
                st.page_link(v.pagina, label=v.titulo, icon=":material/open_in_new:")
                st.badge(
                    sug.situacao + (f" ({sug.registros})" if sug.registros else ""),
                    icon=icones[sug.situacao],
                    color=cores[sug.situacao],
                )
            linha[1].markdown(
                (f"**No projeto:** {sug.motivo}.  \n" if sug.motivo else "")
                + f"**Quando se aplica:** {v.quando}."
            )
        st.caption(
            "Situação de cada uma pela cor: verde registrada, laranja indicada pelo projeto, "
            "cinza só quando houver o caso.",
            help=AJUDA["situacao_complementares"],
        )


aba_roteiro, aba_complementares = st.tabs(["Passo a passo", "Verificações complementares"])
with aba_complementares:
    _complementares()
with aba_roteiro:
    for fase in rt.FASES:
        with st.container(border=True), secao_protegida(fase):
            st.subheader(fase, help=AJUDA["fase"])
            for passo, situacao in zip(rt.PASSOS, situacoes, strict=True):
                if passo.fase != fase:
                    continue
                if situacao.feito is True:
                    cor, icone = "green", ":material/check_circle:"
                elif situacao.feito is False:
                    cor, icone = "gray", ":material/radio_button_unchecked:"
                else:
                    cor, icone = "blue", ":material/info:"
                destaque = " ← continue aqui" if passo.numero == proximo else ""
                st.markdown(f"#### {passo.numero}. {passo.titulo}{destaque}")
                st.badge(situacao.texto, icon=icone, color=cor)
                linha = st.columns(2)
                with linha[0]:
                    if passo.pagina and passo.onde != "páginas de cálculo":
                        st.page_link(passo.pagina, label=passo.onde, icon=":material/open_in_new:")
                    else:
                        st.markdown(f"**Onde:** {passo.onde}")
                    st.markdown(f"**Entra:** {passo.entra}  \n**Sai:** {passo.sai}")
                linha[1].markdown("\n".join(f"- {item}" for item in passo.fazer))
                st.caption(f"Conferir: {passo.conferir}")
                st.divider()
