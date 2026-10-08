"""O Assistente de projeto e a página inicial conhecem Vento, Degrau e Ligação de contraventamento."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import project_assistant as projetos

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")

NOVAS = [
    ("Calcular as forças do vento em uma edificação", "vento"),
    ("Dimensionar o degrau de uma escada industrial em grade", "degrau"),
    ("Dimensionar a ligação de um contraventamento (chapa de nó)", "contraventamento"),
]


def _abrir(pagina: str, **estado) -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(pagina)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


@pytest.mark.parametrize(("objetivo", "chave"), NOVAS)
@pytest.mark.parametrize("etapa", [1, 2, 3, 4])
def test_roteiro_percorre_as_quatro_etapas_das_novas_rotas(banco_isolado, objetivo, chave, etapa):
    t = _abrir(
        "app_pages/assistente_projeto.py",
        projeto_assistente_etapa=etapa,
        projeto_objetivo=objetivo,
        projeto_nome="Projeto de teste",
    )
    rota = projetos.ROTAS[chave]
    textos = " ".join(
        [
            *(i.value for i in t.info),
            *(s.value for s in t.subheader),
            *(m.value for m in t.markdown),
        ]
    )
    if etapa in (2, 3, 4):
        assert rota.titulo in textos or rota.titulo.lower() in textos


def test_toda_rota_do_assistente_aponta_para_uma_pagina_que_existe():
    for rota in projetos.ROTAS.values():
        assert (RAIZ / rota.pagina).exists(), rota


def test_pagina_inicial_traz_os_tres_cartoes_e_as_tres_rotas_rapidas(banco_isolado):
    t = _abrir("app_pages/inicio.py")
    corpo = " ".join(
        [
            *(m.value for m in t.markdown),
            *(s.value for s in t.subheader),
            *(c.value for c in t.caption),
        ]
    )
    for titulo in (
        "Vento nas estruturas",
        "Degrau de escada em grade",
        "Ligação de contraventamento",
    ):
        assert titulo in corpo, titulo
    opcoes = t.selectbox[0].options
    assert any("vento" in o.lower() for o in opcoes)
    assert any("degrau" in o.lower() for o in opcoes)
    assert any("contraventamento" in o.lower() for o in opcoes)
