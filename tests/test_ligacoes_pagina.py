"""A página Ligações estruturais pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.ligacoes_help import AJUDA
from core import ligacoes as lg
from core.project_store import obter_projeto_ativo
from core.technical_modules import listar_modulos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/ligacoes_estruturais.py"


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def test_modulo_registrado_em_dimensionamento_complementar():
    modulo = next(m for m in listar_modulos() if m.id == lg.MODULO_ID)
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Dimensionamento complementar"


@pytest.mark.parametrize(
    "estado",
    [
        {"lig_tipo": lg.CHAPA_SIMPLES},
        {"lig_tipo": lg.PERFIL_FRIO, "lig_f_perfil": lg.PERFIL_A_MAO},
        {"lig_tipo": lg.SOLDA},
        {"lig_tipo": lg.CANTONEIRA_DUPLA},
    ],
)
def test_cada_tipo_abre_com_ajuda_em_tudo_e_figura(banco_isolado, estado):
    t = abrir(**estado)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] in ("OK", "NÃO OK", "ALERTA")
    assert len(t.get("image")) == 1


def test_numeros_da_chapa_simples_iguais_ao_nucleo(banco_isolado):
    t = abrir()
    r = lg.calcular(lg.EntradaChapaSimples())
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] == r.status
    assert metricas["Aproveitamento"] == f"{100 * r.aproveitamento_maximo:.0f} %"


def test_entrada_impossivel_vira_erro_claro(banco_isolado):
    t = abrir(lig_tipo=lg.PERFIL_FRIO, lig_f_perfil=lg.PERFIL_A_MAO, lig_f_x=500.0)
    assert not t.exception


def test_registrar_a_ligacao(banco_com_projeto):
    t = abrir()
    t.button(key="registrar_ligacao").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == lg.MODULO_ID
    ]
    assert len(registros) == 1
    assert registros[0]["resultados"]["figura_ligacao"]["tipo"] == lg.CHAPA_SIMPLES


def test_guia_tem_o_capitulo(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Ligações estruturais"
    t.run()
    assert not t.exception
    assert "Ligações estruturais" in [h.value for h in t.header]


def test_trazer_a_reacao_de_um_calculo_registrado(banco_com_projeto):
    from core import viga_de_piso as vp
    from core.project_store import adicionar_registro_tecnico

    viga = vp.calcular(vp.EntradaVigaDePiso())
    adicionar_registro_tecnico(obter_projeto_ativo()["id"], vp.registro_viga(viga))
    t = abrir()
    assert t.selectbox(key="lig_origem").value.endswith("reação de cálculo")
    t.button(key="lig_usar_reacao").click().run()
    assert not t.exception
    assert t.number_input(key="lig_v").value == pytest.approx(round(viga.reacao_calculo_kN, 2))
