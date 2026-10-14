"""As macros do SolidWorks (VBA): texto ASCII e nenhum nome repetido.

O VBA não diferencia maiúsculas de minúsculas: uma variável ``vigasDoEstudo`` e uma função
``VigasDoEstudo`` são o mesmo nome, e o editor acusa "Tipos incompatíveis" só quando o usuário roda.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parent.parent / "macros_solidworks"
MACROS = sorted(PASTA.glob("*.bas"))


def _nomes(texto: str) -> dict[str, set[tuple[str, str]]]:
    codigo = re.sub(r"'[^\n]*", "", texto)  # sem os comentários
    codigo = re.sub(r"\s_\r?\n", " ", codigo)  # junta as linhas continuadas
    nomes: dict[str, set[tuple[str, str]]] = {}

    def anotar(tipo: str, nome: str) -> None:
        nomes.setdefault(nome.lower(), set()).add((tipo, nome))

    for nome in re.findall(r"^\s*(?:Public |Private )?(?:Function|Sub) (\w+)", codigo, re.M):
        anotar("procedimento", nome)
    for nome in re.findall(r"^\s*Const (\w+)", codigo, re.M):
        anotar("constante", nome)
    for declaracao in re.findall(r"\bDim ([^\n]+)", codigo):
        for parte in declaracao.split(","):
            anotar("variável", parte.strip().split()[0].split("(")[0])
    for cabecalho in re.findall(r"^\s*(?:Function|Sub) \w+\((.*)\)", codigo, re.M):
        for parte in re.sub(r"\(\)", "", cabecalho).split(","):
            palavras = [p for p in parte.split() if p not in ("ByVal", "ByRef", "Optional")]
            if palavras:
                anotar("parâmetro", palavras[0])
    return nomes


@pytest.mark.parametrize("macro", MACROS, ids=[m.name for m in MACROS])
def test_macro_em_ascii_e_sem_nome_repetido(macro):
    texto = macro.read_bytes().decode("ascii")
    choques = [
        sorted(usos)
        for usos in _nomes(texto).values()
        if len(usos) > 1 and {tipo for tipo, _ in usos} & {"procedimento", "constante"}
    ]
    assert not choques, choques


def test_as_duas_macros_estao_na_pasta():
    assert {m.name for m in MACROS} >= {
        "exportar_lista_de_corte.bas",
        "exportar_casos_de_carga.bas",
    }
