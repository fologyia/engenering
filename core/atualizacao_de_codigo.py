"""Recarrega os módulos do programa quando o código em disco muda debaixo de um servidor no ar.

Por que existe
--------------
O Streamlit Community Cloud atualiza os arquivos a cada ``git push`` **sem reiniciar o
processo**. Os arquivos das páginas (``app.py`` e ``app_pages/``) são lidos de novo a cada
execução, mas os módulos de ``core/`` e ``components/`` que já tinham sido importados continuam na
memória, na versão antiga. O resultado são erros que parecem defeito do código novo —
``AttributeError: module 'core.project_store' has no attribute 'enviar_projetos_ao_espelho'`` — e,
pior, módulos velhos que seguem gravando sem as correções novas: com o espelho do GitHub, projetos
salvos sem cópia. Só um "Reboot app" resolvia, e o reinício apaga o disco do servidor. O mesmo vale
para quem deixa um ``streamlit run`` aberto enquanto edita o código.

O que faz
---------
A cada execução, ``app.py`` chama :func:`renovar_modulos_desatualizados` antes de importar qualquer
módulo do programa. A função compara a *assinatura* dos arquivos (nome, data de modificação e
tamanho) com a da execução anterior neste processo. Se mudou — ou se é a primeira vez que ela roda,
porque o processo pode ter módulos de antes de o guarda existir —, retira os módulos do programa de
``sys.modules``, e o próximo ``import`` lê a versão nova do disco. Num processo recém-iniciado ainda
não há nada importado, então a primeira chamada não tem o que descartar.

O estado fica em ``sys`` (e não neste módulo) de propósito: este módulo também é descartado e
reimportado, e a assinatura anterior e a trava precisam sobreviver a isso.
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

PACOTES_DO_PROGRAMA = ("core", "components")
_ATRIBUTO = "_mecanica_toolkit_assinaturas_do_codigo"

Assinatura = tuple[tuple[str, int, int], ...]
_Chave = tuple[str, tuple[str, ...]]


class _Estado:
    """Trava e assinaturas já vistas, uma por (pasta do programa, pacotes)."""

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.assinaturas: dict[_Chave, Assinatura] = {}


def _estado() -> _Estado:
    # setdefault no __dict__ do módulo sys é atômico: duas sessões na primeira chamada não criam
    # duas travas.
    estado: _Estado = sys.__dict__.setdefault(_ATRIBUTO, _Estado())
    return estado


def assinatura_do_codigo(raiz: Path, pacotes: Sequence[str] = PACOTES_DO_PROGRAMA) -> Assinatura:
    """``(arquivo, data de modificação em ns, tamanho)`` de cada ``.py`` dos pacotes, em ordem."""
    itens: list[tuple[str, int, int]] = []
    for pacote in pacotes:
        try:
            with os.scandir(raiz / pacote) as entradas:
                for entrada in entradas:
                    if entrada.name.endswith(".py"):
                        info = entrada.stat()
                        itens.append((f"{pacote}/{entrada.name}", info.st_mtime_ns, info.st_size))
        except OSError:
            continue
    return tuple(sorted(itens))


def _chave(raiz: Path, pacotes: Sequence[str]) -> _Chave:
    return str(raiz.resolve()), tuple(pacotes)


def registrar_codigo_atual(
    raiz: Path | None = None, pacotes: Sequence[str] = PACOTES_DO_PROGRAMA
) -> None:
    """Declara que os módulos já importados correspondem ao código que está em disco agora.

    Os testes chamam isto antes de abrir o aplicativo: sem a declaração, a primeira execução do
    ``app.py`` trataria os módulos da própria suíte como velhos e os descartaria, e o que os
    testes isolaram (banco temporário, espelho falso) deixaria de valer.
    """
    raiz = raiz or Path(__file__).resolve().parents[1]
    estado = _estado()
    with estado.trava:
        estado.assinaturas[_chave(raiz, pacotes)] = assinatura_do_codigo(raiz, pacotes)


def renovar_modulos_desatualizados(
    raiz: Path | None = None, pacotes: Sequence[str] = PACOTES_DO_PROGRAMA
) -> list[str]:
    """Descarta de ``sys.modules`` os módulos do programa se o código em disco mudou.

    Devolve os nomes descartados (vazio quando nada mudou). Nunca levanta: se os arquivos não
    puderem ser lidos, o aplicativo segue com o que já está na memória.
    """
    raiz = raiz or Path(__file__).resolve().parents[1]
    try:
        atual = assinatura_do_codigo(raiz, pacotes)
        chave = _chave(raiz, pacotes)
    except OSError:
        return []
    estado = _estado()
    with estado.trava:
        anterior = estado.assinaturas.get(chave)
        estado.assinaturas[chave] = atual
        if anterior == atual:
            return []
        descartados = sorted(nome for nome in sys.modules if nome.split(".")[0] in pacotes)
        for nome in descartados:
            sys.modules.pop(nome, None)
    return descartados
