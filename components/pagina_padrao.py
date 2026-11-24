"""Peças de tela comuns às páginas de verificação feitas de grupos de linhas.

:class:`Campos` cria os campos com a chave da sessão (prefixo + nome), o valor guardado entre
páginas e o "?" de ajuda do dicionário da página — o nome do campo é a chave da ajuda, então um
campo sem texto de ajuda quebra na hora. :func:`mostrar_resultado` mostra a situação, as
tabelas por grupo, o memorial (Word e PDF) e o botão de registrar no projeto, todos com ajuda.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import streamlit as st

from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.verification_table import mostrar_verificacoes_resumidas
from core import verificacao_modulo as vm
from core.project_store import obter_projeto_ativo

AJUDA_PADRAO: dict[str, str] = {
    "sec_resultado": (
        "O resumo do cálculo: a situação geral (atende, atende com ressalvas ou não atende), o "
        "maior aproveitamento e a verificação que governa. As tabelas abaixo trazem cada "
        "verificação com o solicitante, o resistente e o item da norma."
    ),
    "res_situacao": (
        "ATENDE quando todas as verificações que se aplicam passam; ATENDE COM RESSALVAS quando "
        "alguma regra de boa prática ou dado a conferir pede atenção; NÃO ATENDE quando alguma "
        "resistência ou limite obrigatório é ultrapassado."
    ),
    "res_utilizacao": (
        "O maior aproveitamento (solicitante ÷ resistente) entre as verificações. Até 100 % "
        "atende; acima de 100 % não atende."
    ),
    "res_governa": (
        "A verificação com o maior aproveitamento: é ela que decide se o elemento passa e o "
        "que mudar para ganhar folga."
    ),
    "sec_memorial": (
        "O memorial só deste cálculo. O Word é um trecho para colar no seu documento oficial "
        "(sem capa, títulos sem número, equações nativas); o PDF segue o padrão do memorial do "
        "projeto."
    ),
    "btn_word": "Baixa o trecho do memorial em Word, para colar no documento oficial.",
    "btn_pdf": "Baixa o memorial deste cálculo em PDF, no padrão do memorial do projeto.",
    "sec_registrar": (
        "Grava este cálculo no projeto ativo. Ele passa a aparecer no Memorial de cálculo do "
        "projeto e na Validação do projeto."
    ),
}


class Campos:
    """Fábrica de campos de uma página: chave = ``prefixo + nome``; ajuda = ``ajuda[nome]``."""

    def __init__(self, prefixo: str, ajuda: Mapping[str, str]) -> None:
        self.prefixo = prefixo
        self.ajuda = ajuda

    def _chave(self, nome: str, sufixo: str = "") -> str:
        return f"{self.prefixo}{nome}{sufixo}"

    @staticmethod
    def _inicial(chave: str, **valor: Any) -> dict[str, Any]:
        """O valor de partida só quando a sessão ainda não tem a chave: outra página pode
        deixar o valor pronto (ex.: Flambagem de colunas → Contenção lateral) sem o aviso do
        Streamlit de valor dado duas vezes."""
        return {} if chave in st.session_state else valor

    def numero(
        self,
        rotulo: str,
        nome: str,
        padrao: float,
        coluna: Any = st,
        *,
        minimo: float | None = 0.0,
        maximo: float | None = 1e7,
        passo: float = 1.0,
        formato: str = "%.1f",
        sufixo: str = "",
    ) -> float:
        return float(
            coluna.number_input(
                rotulo,
                min_value=minimo,
                max_value=maximo,
                **self._inicial(self._chave(nome, sufixo), value=float(padrao)),
                step=passo,
                format=formato,
                key=self._chave(nome, sufixo),
                persist_state="session",
                help=self.ajuda[nome],
            )
        )

    def inteiro(
        self,
        rotulo: str,
        nome: str,
        padrao: int,
        coluna: Any = st,
        *,
        minimo: int = 1,
        maximo: int = 100,
    ) -> int:
        return int(
            coluna.number_input(
                rotulo,
                min_value=minimo,
                max_value=maximo,
                **self._inicial(self._chave(nome), value=int(padrao)),
                step=1,
                key=self._chave(nome),
                persist_state="session",
                help=self.ajuda[nome],
            )
        )

    def escolha(
        self,
        rotulo: str,
        nome: str,
        opcoes: Sequence[str],
        padrao: str,
        coluna: Any = st,
        *,
        sufixo: str = "",
        horizontal: bool = False,
    ) -> str:
        lista = list(opcoes)
        indice = lista.index(padrao) if padrao in lista else 0
        chave = self._chave(nome, sufixo)
        if chave in st.session_state and st.session_state[chave] not in lista:
            del st.session_state[chave]  # valor de outra versão da lista: volta ao padrão
        inicial = self._inicial(chave, index=indice)
        if horizontal:
            return str(
                coluna.radio(
                    rotulo,
                    lista,
                    **inicial,
                    horizontal=True,
                    key=chave,
                    persist_state="session",
                    help=self.ajuda[nome],
                )
            )
        return str(
            coluna.selectbox(
                rotulo,
                lista,
                **inicial,
                key=chave,
                persist_state="session",
                help=self.ajuda[nome],
            )
        )

    def chave(self, rotulo: str, nome: str, padrao: bool, coluna: Any = st) -> bool:
        return bool(
            coluna.toggle(
                rotulo,
                **self._inicial(self._chave(nome), value=padrao),
                key=self._chave(nome),
                persist_state="session",
                help=self.ajuda[nome],
            )
        )

    def texto(self, rotulo: str, nome: str, padrao: str, coluna: Any = st) -> str:
        return str(
            coluna.text_input(
                rotulo,
                **self._inicial(self._chave(nome), value=padrao),
                key=self._chave(nome),
                persist_state="session",
                help=self.ajuda[nome],
            )
        )

    def titulo(self, texto: str, nome: str) -> None:
        st.subheader(texto, help=self.ajuda[nome])


def _formato_pct(valor: float) -> str:
    return f"{100 * valor:.0f} %"


def mostrar_resultado(
    grupos: Sequence[vm.Grupo],
    *,
    avisos: Sequence[str] = (),
    nome: Callable[[Any], str] = lambda v: v.nome,
) -> None:
    """Situação, maior aproveitamento, governante e as tabelas por grupo."""
    linhas = vm.decisivas(grupos)
    with st.container(border=True), secao_protegida("Resultado"):
        st.subheader("Resultado", help=AJUDA_PADRAO["sec_resultado"])
        situacao = vm.situacao(linhas)
        g = vm.governante(linhas)
        c = st.columns(3)
        c[0].metric("Situação", situacao, help=AJUDA_PADRAO["res_situacao"])
        c[1].metric(
            "Maior aproveitamento",
            _formato_pct(vm.utilizacao_maxima(linhas)),
            help=AJUDA_PADRAO["res_utilizacao"],
        )
        c[2].markdown(f"**Governa**  \n{g.nome if g else '—'}", help=AJUDA_PADRAO["res_governa"])
        frase = vm.frase_do_resultado(linhas, "O elemento")
        if situacao == "ATENDE":
            st.success(frase, icon=":material/check_circle:")
        elif situacao == "ATENDE COM RESSALVAS":
            st.warning(frase, icon=":material/warning:")
        else:
            st.error(frase, icon=":material/error:")
        if avisos:
            st.markdown("\n".join(f"- {a}" for a in avisos))
        visiveis = [(g.nome, g.linhas) for g in grupos if g.linhas]
        if visiveis:
            mostrar_verificacoes_resumidas(visiveis, nome=nome)


def memorial_e_registro(
    registro: Mapping[str, Any],
    *,
    prefixo: str,
    arquivo: str,
    rotulo_registrar: str,
) -> None:
    """Os botões do memorial (Word e PDF) e o de registrar no projeto ativo."""
    projeto = obter_projeto_ativo()
    with st.container(border=True), secao_protegida("Memorial"):
        st.subheader("Memorial deste cálculo", help=AJUDA_PADRAO["sec_memorial"])
        c = st.columns(2)
        c[0].download_button(
            "Baixar o memorial (Word)",
            data=lambda: vm.memorial(registro, projeto=projeto),
            file_name=f"{arquivo}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            icon=":material/description:",
            width="stretch",
            on_click="ignore",
            key=f"{prefixo}memorial_word",
            help=AJUDA_PADRAO["btn_word"],
        )
        c[1].download_button(
            "Baixar o memorial (PDF)",
            data=lambda: vm.memorial(registro, projeto=projeto, formato="pdf"),
            file_name=f"{arquivo}.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            width="stretch",
            on_click="ignore",
            key=f"{prefixo}memorial_pdf",
            help=AJUDA_PADRAO["btn_pdf"],
        )
    with st.container(border=True), secao_protegida("Registrar no projeto"):
        st.subheader("Registrar no projeto", help=AJUDA_PADRAO["sec_registrar"])
        botao_registrar_calculo(registro, key=f"{prefixo}registrar", rotulo=rotulo_registrar)
