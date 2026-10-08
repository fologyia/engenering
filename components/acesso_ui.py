"""Tela de senha do aplicativo e avisos de acesso (a regra está em :mod:`core.acesso`)."""

from __future__ import annotations

import time

import streamlit as st

from components.armazenamento_ui import exportar_segredos_para_ambiente
from core import acesso, armazenamento

_MARCA = "acesso_marca"
_FALHAS = "acesso_falhas"
_LIBERA_EM = "acesso_libera_em"

AJUDA_SENHA = (
    "A senha de acesso ao aplicativo, definida por quem o publicou no segredo "
    f"{acesso.VARIAVEL_SENHA}. Maiúsculas e minúsculas contam."
)
AJUDA_ENTRAR = "Confere a senha. Depois de algumas tentativas erradas o programa pede para esperar."
AJUDA_SAIR = "Encerra o acesso nesta aba. Para entrar de novo será preciso digitar a senha."


def exigir_acesso() -> None:
    """Para a execução na tela de senha, se o acesso estiver fechado e a sessão ainda não entrou.

    Vem antes de tudo que lê o banco: sem a senha nenhum dado de projeto chega à tela.
    """
    exportar_segredos_para_ambiente()
    if not acesso.acesso_exigido():
        return
    if acesso.sessao_liberada(st.session_state.get(_MARCA)):
        return
    _tela_de_senha()
    st.stop()


def _tela_de_senha() -> None:
    _, centro, _ = st.columns([1, 2, 1])
    with centro, st.container(border=True):
        st.subheader("Mecânica Toolkit", help="Aplicativo de acesso restrito.")
        st.caption("Este aplicativo é de acesso restrito. Digite a senha para continuar.")
        falhas = int(st.session_state.get(_FALHAS, 0))
        espera = max(0.0, float(st.session_state.get(_LIBERA_EM, 0.0)) - time.time())
        with st.form("acesso_formulario", border=False):
            tentativa = st.text_input(
                "Senha",
                type="password",
                key="acesso_campo_senha",
                help=AJUDA_SENHA,
                autocomplete="current-password",
            )
            enviar = st.form_submit_button(
                "Entrar", icon=":material/lock_open:", help=AJUDA_ENTRAR, width="stretch"
            )
        if enviar:
            if espera > 0:
                st.warning(
                    f"Aguarde {espera:.0f} s antes de tentar de novo.", icon=":material/timer:"
                )
            elif acesso.senha_confere(tentativa):
                st.session_state[_MARCA] = acesso.marca_da_sessao()
                st.session_state[_FALHAS] = 0
                st.session_state[_LIBERA_EM] = 0.0
                st.session_state.pop("acesso_campo_senha", None)
                st.rerun()
            else:
                falhas += 1
                st.session_state[_FALHAS] = falhas
                st.session_state[_LIBERA_EM] = time.time() + acesso.espera_apos_falhas(falhas)
                time.sleep(acesso.PAUSA_APOS_ERRO_S)
                st.error("Senha incorreta.", icon=":material/error:")
        elif espera > 0:
            st.warning(f"Aguarde {espera:.0f} s antes de tentar de novo.", icon=":material/timer:")


def acesso_na_lateral() -> None:
    """Botão de sair (com senha) ou aviso de endereço aberto (na nuvem, sem senha)."""
    if acesso.acesso_exigido():
        with st.sidebar:
            if st.button("Sair", icon=":material/logout:", key="acesso_sair", help=AJUDA_SAIR):
                st.session_state.pop(_MARCA, None)
                st.rerun()
        return
    if armazenamento.ambiente() == armazenamento.AMBIENTE_NUVEM:
        with st.sidebar:
            st.caption(
                ":material/lock_open: **Acesso aberto.** Qualquer pessoa com o link vê os "
                f"projetos. Para fechar, defina o segredo **{acesso.VARIAVEL_SENHA}** em "
                "*Settings → Secrets* e restrinja quem pode ver o aplicativo em *Settings → "
                "Sharing*."
            )
