"""Senha de acesso opcional ao aplicativo (sem Streamlit).

O Streamlit Cloud publica o aplicativo num endereço aberto: quem tiver o link vê os projetos. Para
fechá-lo basta definir o segredo ``MECANICA_TOOLKIT_SENHA`` (em *Settings → Secrets* do Cloud, ou
como variável de ambiente). Sem o segredo o programa abre livre, como sempre foi no computador do
usuário.

Este módulo só decide: a senha confere? quanto falta para a próxima tentativa? A tela fica em
:mod:`components.acesso_ui`. A senha nunca é gravada, registrada ou mostrada: o que vai para a
sessão é uma marca derivada, que deixa de valer se a senha for trocada.
"""

from __future__ import annotations

import hashlib
import hmac
import os

VARIAVEL_SENHA = "MECANICA_TOOLKIT_SENHA"

#: Falhas seguidas permitidas na sessão antes de a espera começar.
FALHAS_SEM_ESPERA = 2
#: Espera máxima entre tentativas, em segundos.
ESPERA_MAXIMA_S = 60.0
#: Pausa fixa depois de cada senha errada (freia quem abre sessões novas em série).
PAUSA_APOS_ERRO_S = 1.0

_SAL_DA_MARCA = b"mecanica-toolkit/acesso/v1"


def senha_configurada() -> str:
    """A senha do ambiente, sem espaços nas pontas; vazia quando o acesso é livre."""
    return os.environ.get(VARIAVEL_SENHA, "").strip()


def acesso_exigido() -> bool:
    return bool(senha_configurada())


def _resumo(texto: str) -> bytes:
    return hashlib.sha256(texto.encode("utf-8")).digest()


def senha_confere(tentativa: str, senha: str | None = None) -> bool:
    """Compara em tempo constante (resumos de mesmo tamanho); vazio nunca confere."""
    esperada = senha_configurada() if senha is None else senha.strip()
    if not esperada or not tentativa:
        return False
    return hmac.compare_digest(_resumo(tentativa.strip()), _resumo(esperada))


def marca_da_sessao(senha: str | None = None) -> str:
    """Valor guardado na sessão ao entrar. Muda quando a senha muda e não revela a senha."""
    esperada = senha_configurada() if senha is None else senha.strip()
    if not esperada:
        return ""
    return hmac.new(_SAL_DA_MARCA, esperada.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def sessao_liberada(marca_guardada: object) -> bool:
    """A sessão já entrou com a senha que vale agora?"""
    atual = marca_da_sessao()
    return (
        bool(atual)
        and isinstance(marca_guardada, str)
        and hmac.compare_digest(marca_guardada.encode("utf-8"), atual.encode("utf-8"))
    )


def espera_apos_falhas(falhas: int) -> float:
    """Segundos de espera depois de ``falhas`` senhas erradas seguidas na sessão.

    Zero até ``FALHAS_SEM_ESPERA``; depois 2, 4, 8… até ``ESPERA_MAXIMA_S``.
    """
    if falhas <= FALHAS_SEM_ESPERA:
        return 0.0
    return min(ESPERA_MAXIMA_S, float(2 ** (falhas - FALHAS_SEM_ESPERA)))
