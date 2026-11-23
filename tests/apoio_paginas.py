"""Apoio comum aos testes das páginas de verificação (abrir, ajuda em tudo, memorial, registro)."""

from __future__ import annotations

import io
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
ISENTOS = {("text_input", "Nome do novo projeto")}


def abrir(pagina: str, **estado: Any) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=240)
    t.run()
    t.switch_page(pagina)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def sem_ajuda(t: AppTest) -> set[tuple[str, str]]:
    return {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - ISENTOS


def conferir_textos_de_ajuda(pagina: str, ajuda: Mapping[str, str]) -> None:
    """Todo texto é usado pela página (como chave entre aspas) e termina com pontuação."""
    usadas = set(re.findall(r'"([A-Za-z_0-9]+)"', (RAIZ / pagina).read_text(encoding="utf-8")))
    assert set(ajuda) <= usadas, sorted(set(ajuda) - usadas)
    for chave, texto in ajuda.items():
        assert texto.strip() == texto and texto[-1] in ".!:)" and 10 < len(texto) <= 900, chave


def metricas(t: AppTest) -> dict[str, str]:
    return {m.label: str(m.value) for m in t.metric}


def conferir_registro_e_memorial(registro: Mapping[str, Any], modulo_id: str) -> None:
    """O registro passa pelo JSON, não leva linhas N/A e gera o memorial em Word e em PDF."""
    import docx

    from core import verificacao_modulo as vm

    reg = json.loads(json.dumps(registro))
    assert reg["modulo_id"] == modulo_id
    assert not [v for v in reg["resultados"]["verificações"] if v["status"] == "N/A"]
    w = vm.memorial(reg)
    d = docx.Document(io.BytesIO(w))
    titulos = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    assert titulos and "Conclusão" in titulos, titulos
    texto = " ".join(p.text for p in d.paragraphs).lower()
    assert "valor normativo" not in texto and "página" not in texto
    pdf = vm.memorial(reg, formato="pdf")
    assert pdf[:4] == b"%PDF"


def conferir_entradas_curadas(registro: Mapping[str, Any], modulo_id: str) -> None:
    from core import memorial_verificacoes as mv

    curadas = {c for c, *_ in mv.ENTRADAS_CURADAS[modulo_id]}
    assert set(registro["entradas"]) <= curadas, set(registro["entradas"]) - curadas
