"""Avisos e controles de armazenamento: a verdade sobre onde o projeto fica salvo.

O texto "salvo no banco local" é verdadeiro no computador do usuário e falso no
Streamlit Cloud, onde o disco é apagado a cada reinício. Aqui a tela passa a
dizer o que acontece de fato, oferece a cópia de segurança em um clique e
mostra o estado do espelho no GitHub (:mod:`core.espelho_remoto`).
"""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from core import acesso, armazenamento, espelho_remoto
from core.armazenamento import (
    NIVEL_FALHA,
    NIVEL_LOCAL,
    NIVEL_PROTEGIDO,
    NIVEL_TEMPORARIO,
    SituacaoArmazenamento,
)
from core.project_store import exportar_carteira

# Resultado da última ação do painel (enviar tudo, testar a conexão, recarregar): sobrevive ao
# st.rerun() que atualiza o estado mostrado acima dos botões, o que um st.toast não faria.
_RESULTADO = "armazenamento_resultado"

_RESUMO_LATERAL = {
    NIVEL_TEMPORARIO: "Os projetos somem quando o aplicativo reinicia. Baixe a carteira ao terminar.",
    NIVEL_FALHA: "",
}

EXEMPLO_DE_SEGREDOS = f"""\
{espelho_remoto.VARIAVEL_REPOSITORIO} = "seu-usuario/mecanica-toolkit-dados"
{espelho_remoto.VARIAVEL_TOKEN} = "github_pat_..."
"""

PASSOS_PARA_LIGAR = (
    "No GitHub, crie um repositório **privado** só para os dados (marque «Add a README file»). "
    "Não use o repositório do próprio aplicativo: cada gravação seria um commit e reiniciaria o "
    "servidor.",
    "Em *Settings → Developer settings → Personal access tokens → Fine-grained tokens*, gere um "
    "token que enxergue **só esse repositório** e tenha *Contents: Read and write*.",
    "No Streamlit Cloud, abra o aplicativo → *Settings → Secrets* e cole as duas linhas abaixo, "
    "com o seu repositório e o token.",
    "Reinicie o aplicativo (*Reboot*). Na próxima abertura, aqui no painel, use «Testar conexão» "
    "e «Enviar todos os projetos ao GitHub agora».",
)


def exportar_segredos_para_ambiente() -> None:
    """Passa os segredos do Streamlit para as variáveis de ambiente que o núcleo lê.

    O núcleo (``core/``) não conhece o Streamlit e lê só o ambiente. No Cloud os
    segredos de primeiro nível já viram variáveis de ambiente; isto cobre o
    ``.streamlit/secrets.toml`` de quem roda o programa por conta própria. Uma
    variável já definida no ambiente tem prioridade.
    """
    try:
        segredos = {str(chave): valor for chave, valor in st.secrets.items()}
    except Exception:  # sem arquivo de segredos o Streamlit levanta; é o caso normal
        return
    for nome in (*espelho_remoto.VARIAVEIS, armazenamento.VARIAVEL_AMBIENTE, acesso.VARIAVEL_SENHA):
        valor = segredos.get(nome)
        if valor is not None and not os.environ.get(nome):
            os.environ[nome] = str(valor)


def preparar_armazenamento() -> None:
    """Primeira coisa que o aplicativo faz a cada execução, antes de ler o banco.

    Lê os segredos, traz do espelho o que o disco perdeu (uma vez por processo)
    e reenvia o que ficou pendente.
    """
    exportar_segredos_para_ambiente()
    if armazenamento.restauracao_pendente():
        with st.spinner("Carregando seus projetos do GitHub…"):
            resultado = armazenamento.restaurar_do_espelho()
        if resultado is not None and (resultado.projetos or resultado.catalogos):
            st.toast(
                f"{len(resultado.projetos)} projeto(s) e {len(resultado.catalogos)} catálogo(s) "
                "carregado(s) do GitHub.",
                icon=":material/cloud_download:",
            )
    armazenamento.reenviar_pendencias()


def _botao_baixar_carteira(*, chave: str, rotulo: str = "Baixar meus projetos (JSON)") -> None:
    st.download_button(
        rotulo,
        data=exportar_carteira,
        file_name=f"carteira_{date.today().isoformat()}.json",
        mime="application/json",
        icon=":material/download:",
        key=chave,
        help=(
            "Todos os projetos, com revisões e linha do tempo, num arquivo. Para trazê-los de "
            "volta depois, use «Restaurar uma carteira exportada» no Painel industrial."
        ),
    )


def situacao_na_lateral() -> None:
    """Aviso curto na barra lateral de toda página, só quando os dados correm risco."""
    estado = armazenamento.situacao()
    with st.sidebar:
        if estado.nivel == NIVEL_PROTEGIDO:
            st.caption(f":material/cloud_done: {estado.titulo}.")
            return
        if not estado.exige_atencao:
            return
        corpo = _RESUMO_LATERAL.get(estado.nivel) or estado.detalhe
        st.warning(f"**{estado.titulo}.** {corpo}", icon=":material/cloud_off:")
        _botao_baixar_carteira(chave="lateral_baixar_carteira")
        st.page_link(
            "app_pages/painel_industrial.py",
            label="Como guardar os projetos",
            icon=":material/help:",
        )


def aviso_de_armazenamento() -> None:
    """Aviso completo no corpo da página, nas telas onde o usuário cria e salva projetos."""
    estado = armazenamento.situacao()
    if estado.exige_atencao:
        st.warning(f"**{estado.titulo}.** {estado.detalhe}", icon=":material/cloud_off:")


def _situacao_do_espelho(estado: SituacaoArmazenamento) -> None:
    espelho = estado.espelho
    if estado.nivel == NIVEL_PROTEGIDO:
        st.success(f"**{estado.titulo}.** {estado.detalhe}", icon=":material/cloud_done:")
    elif estado.nivel == NIVEL_FALHA:
        st.error(f"**{estado.titulo}.** {estado.detalhe}", icon=":material/cloud_off:")
    elif estado.nivel == NIVEL_TEMPORARIO:
        st.warning(f"**{estado.titulo}.** {estado.detalhe}", icon=":material/cloud_off:")
    else:
        st.caption(f":material/computer: {estado.titulo}. {estado.detalhe}")
    if not espelho.configurado:
        return
    with st.container(horizontal=True):
        if st.button(
            "Enviar todos os projetos ao GitHub agora",
            icon=":material/cloud_upload:",
            key="armazenamento_enviar_tudo",
            help=(
                "Copia para o GitHub todos os projetos e catálogos que estão neste disco. Use "
                "depois de ligar o espelho, ou para conferir que nada ficou para trás."
            ),
        ):
            with st.spinner("Enviando ao GitHub…"):
                resumo = armazenamento.enviar_tudo()
            st.session_state[_RESULTADO] = (
                not resumo["pendentes"],
                f"{resumo['projetos']} projeto(s) e {resumo['catalogos']} catálogo(s) enviados "
                f"ao GitHub; {resumo['pendentes']} pendente(s).",
            )
            st.rerun()
        if st.button(
            "Testar conexão",
            icon=":material/wifi_tethering:",
            key="armazenamento_testar",
            help="Confere o repositório, o ramo e se o token pode gravar nele.",
        ):
            try:
                st.session_state[_RESULTADO] = (True, espelho_remoto.testar_conexao())
            except espelho_remoto.EspelhoErro as erro:
                st.session_state[_RESULTADO] = (False, str(erro))
        if st.button(
            "Recarregar do GitHub",
            icon=":material/cloud_download:",
            key="armazenamento_recarregar",
            help=(
                "Traz do GitHub os projetos que este disco não tem. Nunca sobrescreve um projeto "
                "que já está aqui."
            ),
        ):
            with st.spinner("Lendo o GitHub…"):
                resultado = armazenamento.restaurar_do_espelho(forcar=True)
            if resultado is not None:
                st.session_state[_RESULTADO] = (
                    resultado.ok,
                    f"{len(resultado.projetos)} projeto(s) trazido(s) do GitHub."
                    if resultado.ok
                    else "A leitura do GitHub teve problemas: veja o aviso acima.",
                )
            st.rerun()
    resultado_da_acao = st.session_state.get(_RESULTADO)
    if resultado_da_acao:
        (st.success if resultado_da_acao[0] else st.error)(resultado_da_acao[1])


def painel_de_armazenamento() -> None:
    """Estado do armazenamento, os controles do espelho e o passo a passo para ligá-lo."""
    estado = armazenamento.situacao()
    _situacao_do_espelho(estado)
    if estado.nivel == NIVEL_LOCAL and not estado.espelho.configurado:
        return
    if not estado.espelho.configurado:
        with st.expander("Como guardar os projetos de forma permanente (GitHub)", expanded=False):
            st.markdown("\n".join(f"{n}. {passo}" for n, passo in enumerate(PASSOS_PARA_LIGAR, 1)))
            st.code(EXEMPLO_DE_SEGREDOS, language="toml")
            st.caption(
                "Os projetos continuam sendo gravados primeiro no disco do servidor; o GitHub "
                "recebe uma cópia a cada salvamento e devolve tudo quando o aplicativo reinicia. "
                "Detalhes em docs/armazenamento_na_nuvem.md."
            )
