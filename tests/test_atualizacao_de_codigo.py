"""O guarda que descarta módulos velhos quando o código muda debaixo de um servidor no ar.

Reproduz o defeito da versão web: o Streamlit Cloud troca os arquivos num push sem reiniciar o
processo, e o módulo antigo (sem uma função nova) continua em ``sys.modules``. Os testes usam um
programa de mentira — nunca os pacotes reais —, porque descartar ``core`` e ``components`` no meio
da suíte faria os testes seguintes usarem cópias novas dos módulos, sem o isolamento dos fixtures.
"""

from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import atualizacao_de_codigo as ac

PACOTE = "pacote_falso_ac"
RAIZ_REAL = Path(__file__).resolve().parent.parent


def escrever(arquivo: Path, texto: str, *, segundos_a_frente: int) -> None:
    """Grava o arquivo e força uma data de modificação diferente (o relógio do disco é grosso)."""
    arquivo.write_text(texto, encoding="utf-8")
    agora = arquivo.stat().st_mtime_ns + segundos_a_frente * 1_000_000_000
    os.utime(arquivo, ns=(agora, agora))


@pytest.fixture
def programa(tmp_path, monkeypatch):
    pacote = tmp_path / PACOTE
    pacote.mkdir()
    (pacote / "__init__.py").write_text("", encoding="utf-8")
    escrever(pacote / "modulo.py", "VALOR = 1\n", segundos_a_frente=0)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for nome in [n for n in sys.modules if n.split(".")[0] == PACOTE]:
        del sys.modules[nome]


def renovar(programa: Path) -> list[str]:
    return ac.renovar_modulos_desatualizados(programa, pacotes=(PACOTE,))


def valor() -> int:
    return importlib.import_module(f"{PACOTE}.modulo").VALOR


def test_servidor_com_modulo_velho_na_memoria_passa_a_ler_o_codigo_novo(programa):
    assert valor() == 1  # o processo importou a versão antiga...
    escrever(
        programa / PACOTE / "modulo.py", "VALOR = 2\n", segundos_a_frente=10
    )  # ...o push chegou

    descartados = renovar(programa)  # primeira execução do guarda neste processo

    assert f"{PACOTE}.modulo" in descartados and PACOTE in descartados
    assert valor() == 2


def test_funcao_nova_que_o_modulo_velho_nao_tinha_passa_a_existir(programa):
    """O caso exato do erro: ``module has no attribute 'enviar_projetos_ao_espelho'``."""
    modulo = importlib.import_module(f"{PACOTE}.modulo")
    assert not hasattr(modulo, "enviar_tudo")
    escrever(
        programa / PACOTE / "modulo.py", "def enviar_tudo():\n    return 7\n", segundos_a_frente=5
    )

    renovar(programa)

    assert importlib.import_module(f"{PACOTE}.modulo").enviar_tudo() == 7


def test_sem_mudanca_nada_e_descartado_e_o_modulo_continua_o_mesmo(programa):
    renovar(programa)
    modulo = importlib.import_module(f"{PACOTE}.modulo")
    assert renovar(programa) == []
    assert sys.modules[f"{PACOTE}.modulo"] is modulo


def test_mudanca_depois_da_primeira_execucao_tambem_recarrega(programa):
    renovar(programa)
    assert valor() == 1
    escrever(programa / PACOTE / "modulo.py", "VALOR = 3\n", segundos_a_frente=20)

    assert f"{PACOTE}.modulo" in renovar(programa)
    assert valor() == 3
    assert renovar(programa) == []  # e a assinatura nova passa a valer


def test_arquivo_novo_ou_removido_tambem_conta_como_mudanca(programa):
    renovar(programa)
    importlib.import_module(f"{PACOTE}.modulo")
    escrever(programa / PACOTE / "outro.py", "X = 1\n", segundos_a_frente=0)
    assert renovar(programa) != []
    importlib.import_module(f"{PACOTE}.modulo")
    (programa / PACOTE / "outro.py").unlink()
    assert renovar(programa) != []


def test_processo_novo_nao_tem_o_que_descartar(programa):
    assert not any(n.split(".")[0] == PACOTE for n in sys.modules)
    assert renovar(programa) == []


def test_pasta_inexistente_nao_levanta(tmp_path):
    assert ac.renovar_modulos_desatualizados(tmp_path, pacotes=("nao_existe_ac",)) == []
    assert ac.assinatura_do_codigo(tmp_path, ("nao_existe_ac",)) == ()


def test_so_arquivos_py_entram_na_assinatura(programa):
    antes = ac.assinatura_do_codigo(programa, (PACOTE,))
    (programa / PACOTE / "leia-me.txt").write_text("nada a ver", encoding="utf-8")
    assert ac.assinatura_do_codigo(programa, (PACOTE,)) == antes


def test_estado_de_um_programa_nao_interfere_no_de_outro(programa, tmp_path_factory):
    outro = tmp_path_factory.mktemp("outro_programa")
    (outro / PACOTE).mkdir()
    (outro / PACOTE / "__init__.py").write_text("", encoding="utf-8")
    renovar(programa)
    assert ac.renovar_modulos_desatualizados(outro, pacotes=(PACOTE,)) == []  # primeira vez dele
    assert renovar(programa) == []  # o do primeiro segue estável


def test_o_estado_sobrevive_a_reimportacao_do_proprio_modulo(programa):
    renovar(programa)
    recarregado = importlib.reload(ac)
    try:
        assert recarregado.renovar_modulos_desatualizados(programa, pacotes=(PACOTE,)) == []
    finally:
        importlib.reload(ac)


def test_a_suite_declara_o_codigo_real_como_atual_e_o_guarda_nao_o_toca():
    """A fixture da sessão registra a assinatura real; o app.py não descarta os módulos dos testes."""
    projeto = sys.modules["core.project_store"]
    assert ac.renovar_modulos_desatualizados() == []
    assert sys.modules["core.project_store"] is projeto


def test_app_chama_o_guarda_antes_de_importar_qualquer_modulo_do_programa():
    """Se alguém reordenar o app.py, o guarda perde o sentido: a ordem precisa estar travada."""
    arvore = ast.parse((RAIZ_REAL / "app.py").read_text(encoding="utf-8"))
    chamada = next(
        no.lineno
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "renovar_modulos_desatualizados"
    )
    importacoes = [
        no.lineno
        for no in arvore.body
        if isinstance(no, ast.ImportFrom)
        and (no.module or "").split(".")[0] in ("core", "components")
        and no.module != "core.atualizacao_de_codigo"
    ]
    assert importacoes and all(chamada < linha for linha in importacoes)


def test_app_real_com_modulo_velho_na_memoria_carrega_o_codigo_novo(tmp_path):
    """O incidente da versão web, de ponta a ponta, num processo à parte.

    O processo importa o ``core.project_store`` real e apaga dele a função que o push acrescentou
    (é o que o Streamlit Cloud deixa na memória depois de um push sem reinício); em seguida roda o
    ``app.py`` de verdade. O guarda precisa trocar o módulo velho pelo do disco, e o painel de
    armazenamento — que chama essa função — precisa abrir sem exceção.
    """
    roteiro = f"""
import sys
sys.path.insert(0, {str(RAIZ_REAL)!r})
import core.project_store as armazem

del armazem.enviar_projetos_ao_espelho
del armazem.restaurar_projetos_do_espelho
velho = armazem

from streamlit.testing.v1 import AppTest

teste = AppTest.from_file({str(RAIZ_REAL / "app.py")!r}, default_timeout=180)
teste.run()
assert not teste.exception, [str(e.value) for e in teste.exception]
teste.switch_page("app_pages/painel_industrial.py")
teste.run()
assert not teste.exception, [str(e.value) for e in teste.exception]

novo = sys.modules["core.project_store"]
assert novo is not velho, "o módulo velho continuou na memória"
assert hasattr(novo, "enviar_projetos_ao_espelho") and hasattr(novo, "restaurar_projetos_do_espelho")
print("OK")
"""
    ambiente = {
        **os.environ,
        "MECANICA_TOOLKIT_DB": str(tmp_path / "projetos.sqlite3"),
        "PYTHONIOENCODING": "utf-8",
    }
    for variavel in ("MECANICA_TOOLKIT_AMBIENTE", *(v for v in ambiente if "GITHUB" in v)):
        ambiente.pop(variavel, None)
    resultado = subprocess.run(
        [sys.executable, "-c", roteiro],
        cwd=RAIZ_REAL,
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert resultado.returncode == 0 and "OK" in resultado.stdout, (
        resultado.stdout[-2000:] + resultado.stderr[-3000:]
    )
