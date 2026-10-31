"""A página Placas de base pela interface (AppTest)."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.placa_de_base_help import AJUDA
from core import base_de_pilar as bp
from core import navegacao as nv
from core.project_store import obter_projeto_ativo
from core.technical_modules import listar_modulos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/placa_de_base.py"
PROIBIDAS = ("bloqueio", "Snapshot", "Apêndice", "Não informado", "sem valor normativo")


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def _metricas(t: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in t.metric}


def test_todo_texto_de_ajuda_e_usado_e_simples():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave
        assert not any(p.lower() in texto.lower() for p in PROIBIDAS), chave


def test_no_menu_e_registrada_em_ligacoes_e_bases():
    modulo = next(m for m in listar_modulos() if m.id == bp.MODULO_ID)
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Ligações e bases"
    assert nv.grupo_da_pagina(PAGINA).nome == "Ligações e bases"


def test_pagina_padrao_tem_ajuda_em_tudo_e_os_numeros_do_nucleo(banco_isolado):
    t = abrir(pb_tab18=False, pb_bloco=True)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    t = abrir()
    r = bp.calcular(bp.EntradaBase())
    metricas = _metricas(t)
    assert metricas["Status"] == "OK"
    assert metricas["Caso"] == "C1"
    assert metricas["Aproveitamento"] == f"{100 * r.aproveitamento_maximo:.0f} %"
    assert metricas["t_p,min (mm)"] == f"{r.t_p_min:.1f}".replace(".", ",")
    assert len(t.get("image")) == 1
    assert any("Governa" in m.value for m in t.markdown)


def test_ajuda_dos_campos_da_placa_de_cisalhamento_e_das_arruelas(banco_isolado):
    for cortante in (bp.CORTANTE_PLACA, bp.CORTANTE_ARRUELAS):
        t = abrir(pb_cortante=cortante)
        sem_ajuda = [_rotulo(e) for e in t.number_input if not _ajuda(e)]
        assert not sem_ajuda, sem_ajuda


def test_ajuda_dos_campos_de_cada_tipo_de_chumbador(banco_isolado):
    estados = [
        {"pb_ancoragem": bp.ANCORAGEM_PORCA, "pb_aci": True},
        {"pb_ancoragem": bp.ANCORAGEM_GANCHO},
        {"pb_ancoragem": bp.ANCORAGEM_QUIMICO},
        {"pb_ancoragem": bp.ANCORAGEM_EXPANSAO},
    ]
    for estado in estados:
        t = abrir(**estado)
        sem_ajuda = {
            (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
        } - {("text_input", "Nome do novo projeto")}
        assert not sem_ajuda, (estado, sorted(sem_ajuda))


def test_guarda_chuva_tracionado_mostra_o_arrancamento(banco_isolado):
    t = abrir(pb_m_sd=150.0, pb_n=6, pb_t=38.0, pb_ancoragem=bp.ANCORAGEM_GANCHO)
    assert _metricas(t)["Status"] == "NÃO OK"
    assert any("Guarda-chuva: arrancamento" in e.value for e in t.error)
    assert t.number_input(key="pb_eh").value == 0.0
    assert any("sempre" in c.value for c in t.caption)


def test_quimico_com_a_resistencia_do_fabricante(banco_isolado):
    t = abrir(pb_m_sd=150.0, pb_n=6, pb_t=40.0, pb_ancoragem=bp.ANCORAGEM_QUIMICO)
    assert _metricas(t)["Status"] == "NÃO OK"  # cone sem armadura e sem o N_Rd do fabricante
    t.number_input(key="pb_nrd_fab").set_value(150.0).run()
    t.toggle(key="pb_armadura").set_value(True).run()
    assert not t.exception
    assert _metricas(t)["Status"] == "OK"


def test_disposicoes_novas_e_momento_no_eixo_fraco(banco_isolado):
    t = abrir()
    t.radio(key="pb_tipo").set_value(bp.TIPO_ROTULADA).run()
    assert t.selectbox(key="pb_n").value == 2
    assert any("método geral" in c.value for c in t.caption)
    t.radio(key="pb_tipo").set_value(bp.TIPO_INTERNOS_E_EXTERNOS).run()
    assert t.selectbox(key="pb_n").value == 8
    t.selectbox(key="pb_perfil").set_value("W 360 x 51,0").run()
    t.number_input(key="pb_m_sd_y").set_value(5.0).run()
    assert not t.exception
    assert _metricas(t)["Status"] != "ALERTA"  # o M_y agora é calculado (flexão oblíqua)
    assert any("Flexão oblíqua" in w.value for w in t.warning)
    assert any("flexão oblíqua" in c.value for c in t.caption)


def test_tipo_2_volta_para_quatro_chumbadores(banco_isolado):
    t = abrir(pb_n=8)
    assert t.selectbox(key="pb_n").value == 8
    t.radio(key="pb_tipo").set_value(bp.TIPO_2).run()
    assert not t.exception
    assert t.selectbox(key="pb_n").value == 4
    assert t.selectbox(key="pb_n").options == ["4"]


def test_momento_grande_mostra_c3_e_a_tracao(banco_isolado):
    t = abrir(pb_n_sd=300.0, pb_m_sd=150.0, pb_n=6, pb_t=38.0)
    entrada = replace(bp.EntradaBase(), n_chumbadores=6, m_sd_kNm=150.0, t_placa_mm=38.0)
    r = bp.calcular(entrada)
    assert _metricas(t)["Caso"] == "C3" and r.caso == "C3"
    textos = " ".join(m.value for m in t.markdown)
    assert "Chumbadores" in textos  # o grupo dos chumbadores aparece


def test_tracao_sem_dispositivo_explica_e_adotar_nao_aparece(banco_isolado):
    t = abrir(pb_n_sd=-80.0, pb_m_sd=10.0)
    assert _metricas(t)["Status"] == "NÃO OK"
    assert any("placa de cisalhamento" in w.value for w in t.warning)
    assert any("Não passou" in e.value for e in t.error)
    assert not [b for b in t.button if b.key == "pb_adotar"]


def test_adotar_a_base_mais_leve_e_registrar(banco_com_projeto):
    t = abrir(pb_n_sd=100.0, pb_m_sd=30.0, pb_v_sd=60.0, pb_cortante=bp.CORTANTE_ARRUELAS)
    assert _metricas(t)["Status"] == "NÃO OK"
    t.button(key="pb_adotar").click().run()
    assert not t.exception
    assert _metricas(t)["Status"] == "OK"
    assert t.number_input(key="pb_t").value in bp.ESPESSURAS_COMERCIAIS
    t.button(key="registrar_placa_de_base").click().run()
    assert not t.exception
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == bp.MODULO_ID
    ]
    assert len(registros) == 1 and registros[0]["status"] == "Atende"
    assert "figura_base_de_pilar" in registros[0]["resultados"]


def test_entrada_invalida_mostra_o_erro_sem_quebrar(banco_isolado):
    t = abrir(pb_perfil="W 310 x 97,0(H)")
    assert _metricas(t)["Status"] == "NÃO OK"  # placa mais estreita que a mesa: limite reprova
    assert any("Largura da placa" in e.value for e in t.error)


def test_guia_tem_o_capitulo_com_o_exemplo_que_o_nucleo_calcula(banco_isolado):
    r = bp.calcular(bp.EntradaBase())
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Placas de base"
    t.run()
    assert not t.exception
    assert "Placas de base" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"t_p,min = {r.t_p_min:.1f}".replace(".", ",") in esperado
    assert "passa a C3" in esperado


def test_tipo_2_tem_o_a1_da_direcao_lx_da_nota_f(banco_isolado):
    t = abrir(pb_perfil="W 360 x 51,0", pb_tipo=bp.TIPO_2, pb_tab18=False)
    assert t.number_input(key="pb_a1_x").value == 50.0  # o da Tabela 18 para Ø 1"
    t.number_input(key="pb_a1_x").set_value(10.0).run()
    assert not t.exception
    placa = t.table[0].value.loc["Placa"].iloc[0]
    assert placa.startswith("395 × ")  # ℓx = d + 4·a₁ = 355 + 40
    t.radio(key="pb_tipo").set_value(bp.TIPO_1).run()
    assert not [w for w in t.number_input if w.key == "pb_a1_x"]  # só o tipo 2 tem
