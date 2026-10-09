"""A página Vigas de piso pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.viga_de_piso_help import AJUDA
from core import viga_de_piso as vp
from core.project_store import obter_projeto_ativo
from core.technical_modules import listar_modulos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/viga_de_piso.py"


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
    modulo = next(m for m in listar_modulos() if m.id == vp.MODULO_ID)
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Dimensionamento complementar"


def test_pagina_padrao_tem_ajuda_em_tudo_e_os_numeros_do_nucleo(banco_isolado):
    t = abrir(vp_travada=True)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    t = abrir()
    r = vp.calcular(vp.EntradaVigaDePiso())
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] == "OK"
    assert metricas["Aproveitamento"] == f"{100 * r.aproveitamento_maximo:.0f} %"
    assert metricas["M_Sd / M_Rd (kN·m)"] == (
        f"{r.momento_sd_kNm:.1f} / {r.momento_rd_kNm:.1f}".replace(".", ",")
    )
    assert len(t.get("image")) == 1


def test_adotar_o_perfil_mais_leve_e_registrar(banco_com_projeto):
    t = abrir(vp_concentrada=10.0, vp_anglo=True)
    assert {m.label: m.value for m in t.metric}["Status"] == "NÃO OK"
    t.button(key="vp_adotar").click().run()
    assert not t.exception
    adotado = t.selectbox(key="vp_perfil").value
    assert adotado != vp.EntradaVigaDePiso().perfil
    assert {m.label: m.value for m in t.metric}["Status"] == "OK"
    t.button(key="registrar_viga_de_piso").click().run()
    assert not t.exception
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == vp.MODULO_ID
    ]
    assert len(registros) == 1 and adotado in registros[0]["titulo"]


def test_guia_tem_o_capitulo_com_o_exemplo_que_o_nucleo_calcula(banco_isolado):
    r = vp.calcular(vp.EntradaVigaDePiso())
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Vigas de piso"
    t.run()
    assert "Vigas de piso" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"{r.momento_sd_kNm:.1f}".replace(".", ",") in esperado
    assert f"{r.flecha_mm:.1f}".replace(".", ",") in esperado
    assert "item 8.8" in esperado
