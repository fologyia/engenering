"""A página Sensores do modelo pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.sensores_do_modelo_help import AJUDA
from core import plano_de_cargas as pc
from core import sensores_do_modelo as sm
from core.project_store import obter_projeto_ativo, salvar_projeto
from core.technical_modules import listar_modulos
from tests.dados_sensores import CODIGOS_DO_PLANO_REAL, QUADRO_REAL
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/sensores_do_modelo.py"


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def gravar_no_projeto(quadro: sm.QuadroDeSensores) -> None:
    projeto = obter_projeto_ativo()
    plano = pc.PlanoDeCargas()
    for codigo in CODIGOS_DO_PLANO_REAL:
        plano = pc.com_acao(plano, pc.nova_acao(codigo))
    projeto["plano_de_cargas"] = pc.para_dicionario(plano)
    projeto[sm.CAMPO_DO_PROJETO] = sm.para_dicionario(quadro)
    salvar_projeto(projeto, motivo="teste dos sensores")


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def test_modulo_registrado_no_grupo_do_modelo():
    modulo = next(m for m in listar_modulos() if m.id == sm.MODULO_ID)
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Modelo SolidWorks"


def test_sem_quadro_a_pagina_explica_de_onde_vem(banco_com_projeto):
    t = abrir()
    assert any("exportar_casos_de_carga" in c.value for c in t.caption)


def test_quadro_gravado_mostra_a_conferencia_e_registra(banco_com_projeto):
    limite = sm.LimiteDoDeslocamento(sm.L_SOBRE_X, 6.0, 350.0)
    quadro = sm.ler_quadro(QUADRO_REAL, "Análise estática 1-gerenciador-resultados.csv")
    quadro = sm.com_ajustes(quadro, [sm.Sensor("Deslocamento1", sm.DESLOCAMENTO, "mm", limite)])
    gravar_no_projeto(quadro)
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Sensores"] == "4" and metricas["Casos"] == "7"
    assert metricas["Combinações"] == "71" and metricas["Fora da verificação"] == "22"
    assert metricas["Status"] == "ALERTA"
    assert metricas["Tensão máx. ELU (MPa)"] == "39,12"
    assert metricas["Desloc. máx. ELS (mm)"] == "1,176"
    erros = " ".join(e.value for e in t.error)
    assert "C50-ELSR, C52-ELSR a C72-ELSR" in erros
    limite_do_sensor = next(s for s in t.selectbox if str(s.key).startswith("sm_lim_"))
    assert limite_do_sensor.value == sm.L_SOBRE_X
    assert len(t.get("image")) == 1  # o gráfico
    assert not [b for b in t.button if b.key == "sm_gravar"]  # nada mudou: nada a gravar
    t.button(key="registrar_sensores_do_modelo").click().run()
    assert not t.exception
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == sm.MODULO_ID
    ]
    assert len(registros) == 1 and registros[0]["status"] == "Atenção"


def test_trocar_o_que_o_sensor_mede_e_gravar(banco_com_projeto):
    gravar_no_projeto(sm.ler_quadro(QUADRO_REAL, "real.csv"))
    t = abrir()
    next(w for w in t.toggle if str(w.key).startswith("sm_fy_auto_")).set_value(False).run()
    next(w for w in t.number_input if str(w.key).startswith("sm_fy_")).set_value(345.0).run()
    assert not t.exception
    t.button(key="sm_gravar").click().run()
    assert not t.exception
    assert sm.quadro_do_projeto(obter_projeto_ativo()).fy_MPa == 345.0
