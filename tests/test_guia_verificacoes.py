"""Capítulos do Guia geral das verificações novas: abrem, mostram o exemplo e batem com a página."""

from __future__ import annotations

import re

import pytest

from components.guia_verificacoes import CAPITULOS, resultado_esperado
from core import navegacao as nv
from tests import apoio_paginas as ap


def test_cada_capitulo_aponta_para_uma_pagina_do_menu_com_o_mesmo_nome():
    for nome, capitulo in CAPITULOS.items():
        item = nv.item_da_pagina(capitulo.pagina)
        assert item is not None and item.titulo == nome, nome
        texto = (ap.RAIZ / capitulo.pagina).read_text(encoding="utf-8")
        assert f'ajuda_modulo="{nome}"' in texto, nome


@pytest.mark.parametrize("nome", list(CAPITULOS))
def test_resultado_esperado_tem_situacao(nome):
    assert resultado_esperado(nome).startswith("Resultado esperado: ")


def test_guia_abre_os_capitulos(banco_isolado):
    t = ap.abrir("app_pages/guia_geral.py")
    for nome in CAPITULOS:
        t.session_state["guia_modulo"] = nome
        t.run()
        assert not t.exception, nome
        assert nome in [h.value for h in t.header], nome
        assert any(resultado_esperado(nome) == c.value for c in t.caption), nome


def test_o_exemplo_do_guia_e_o_que_a_pagina_mostra(banco_isolado):
    for nome in ("Viga de monovia", "Forças localizadas na alma"):
        t = ap.abrir(CAPITULOS[nome].pagina)
        pct = ap.metricas(t)["Maior aproveitamento"]
        numero = re.search(r"(\d+) %", pct)
        assert numero and f"{numero.group(1)} %" in resultado_esperado(nome), nome
