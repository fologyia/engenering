"""Contenção de falhas na interface: a página continua e um aviso discreto aparece no fim.

* :func:`executar_pagina` — a página inteira (``app.py``);
* :func:`secao_protegida` — uma seção: se ela falhar, as outras continuam;
* :func:`conferir_valores` — NaN ou infinito num resultado vira ocorrência de conferência;
* :func:`aviso_final` — no fim da página, uma linha discreta com as referências.

Nada técnico aparece na tela: o detalhe (traceback) vai para o arquivo de diagnóstico
(``core/diagnostico.py``). Os sinais de controle do Streamlit (``st.stop``, ``st.rerun``,
``st.switch_page``) derivam de ``BaseException`` e passam direto. Com
``MECANICA_TOOLKIT_ERROS=levantar`` (os testes ligam), a falha sobe em vez de ser contida.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import streamlit as st

from core import diagnostico as dg

CHAVE_OCORRENCIAS = "_ocorrencias_desta_execucao"
CHAVE_PAGINA = "_pagina_em_execucao"


def iniciar_execucao() -> None:
    """Zera as ocorrências no começo de cada execução do script (topo do ``app.py``)."""
    st.session_state[CHAVE_OCORRENCIAS] = []
    st.session_state[CHAVE_PAGINA] = ""


def ocorrencias() -> list[dg.Ocorrencia]:
    return list(st.session_state.get(CHAVE_OCORRENCIAS) or [])


def _origem(nome: str) -> str:
    pagina = str(st.session_state.get(CHAVE_PAGINA) or "Programa")
    return f"{pagina} › {nome}" if nome else pagina


def _anotar(ocorrencia: dg.Ocorrencia) -> None:
    lista = st.session_state.setdefault(CHAVE_OCORRENCIAS, [])
    if all(o.referencia != ocorrencia.referencia for o in lista):
        lista.append(ocorrencia)
        dg.gravar(ocorrencia)


def registrar_falha(nome: str, erro: BaseException) -> None:
    _anotar(dg.ocorrencia_de_falha(_origem(nome), erro))


@contextmanager
def secao_protegida(nome: str = "") -> Iterator[None]:
    """O que falhar aqui dentro fica aqui dentro: anota a ocorrência e o resto da página segue.

    Use junto do contêiner da seção, sem reindentar nada::

        with st.container(border=True), secao_protegida("3. Conferência"):
            ...
    """
    try:
        yield
    except Exception as erro:
        if dg.levantar_erros():
            raise
        registrar_falha(nome, erro)


def executar_pagina(pagina: Any) -> None:
    """Roda a página de ``st.navigation`` contida; o aviso sai no fim mesmo com ``st.stop()``."""
    st.session_state[CHAVE_PAGINA] = str(getattr(pagina, "title", "") or "")
    try:
        with secao_protegida():
            pagina.run()
    finally:
        aviso_final()


def conferir_valores(nome: str, valor: Any) -> bool:
    """Anota (sem mostrar) NaN ou infinito num resultado; devolve se está tudo finito."""
    achados = dg.numeros_invalidos(valor)
    if not achados:
        return True
    _anotar(
        dg.ocorrencia_de_conferencia(_origem(nome), "valor não finito em " + ", ".join(achados[:5]))
    )
    return False


def aviso_final() -> None:
    """Uma linha discreta no fim da página, só quando houve ocorrência nesta execução."""
    lista = ocorrencias()
    if not lista:
        return
    referencias = dg.resumo_das_ocorrencias(lista)
    if any(o.tipo == dg.TIPO_FALHA for o in lista):
        texto = "Uma parte desta página não pôde ser exibida"
    else:
        texto = "Um valor desta página não passou na conferência interna e foi omitido"
    st.caption(f":material/info: {texto} (ref. {referencias}). Se repetir, informe a referência.")
