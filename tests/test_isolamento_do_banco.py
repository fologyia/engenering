"""A suíte nunca grava no banco de trabalho do usuário, nem quando os módulos são reimportados.

O ``app.py`` descarta os módulos do programa quando o código em disco muda
(``core/atualizacao_de_codigo.py``). Se isso acontecesse no meio da suíte, o ``core.project_store``
reimportado perderia o ``BANCO_PADRAO`` redirecionado pelo ``conftest`` — e foi assim que rodadas
completas, com o código editado durante a execução, gravaram registros de teste no banco real.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from core import project_store

PACOTES = ("core", "components")


def test_variavel_do_banco_aponta_para_o_banco_temporario_da_suite():
    configurado = Path(os.environ[project_store.VARIAVEL_BANCO])
    real = project_store.pasta_dados_usuario() / project_store.NOME_BANCO
    assert configurado.resolve() != real.resolve()
    assert configurado.name == "projetos_sessao.sqlite3"


def test_reimportar_o_programa_no_meio_da_suite_nao_aponta_para_o_banco_real():
    real = (project_store.pasta_dados_usuario() / project_store.NOME_BANCO).resolve()
    guardados = {n: m for n, m in sys.modules.items() if n.split(".")[0] in PACOTES}
    try:
        for nome in guardados:
            sys.modules.pop(nome, None)  # o que o guarda do app.py faz quando o código muda
        reimportado = importlib.import_module("core.project_store")
        assert reimportado is not project_store
        assert Path(reimportado.BANCO_PADRAO).resolve() != real
        assert (
            Path(reimportado.BANCO_PADRAO).resolve()
            == Path(os.environ[project_store.VARIAVEL_BANCO]).resolve()
        )
    finally:
        for nome in [n for n in sys.modules if n.split(".")[0] in PACOTES]:
            sys.modules.pop(nome, None)
        sys.modules.update(guardados)
