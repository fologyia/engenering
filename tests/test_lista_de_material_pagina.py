"""A página Lista de material pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.lista_de_material_help import AJUDA
from core import esforcos_modelo as em
from core import lista_de_material as lm
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_esforcos_modelo import PILAR
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_quadro_fundacoes import PILAR_2, portico

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/lista_de_material.py"
LISTA = lm.ListaDeMaterial(
    itens=(
        lm.ItemDaLista("P1", lm.TIPO_PERFIL, "W 200 x 35,9 (H)", 2, 4.0),
        lm.ItemDaLista("V1", lm.TIPO_PERFIL, "W 310 x 32,7", 1, 6.0),
        lm.ItemDaLista("X", lm.TIPO_PERFIL, "PERFIL ESQUISITO", 1, 3.0),
        lm.ItemDaLista("CH", lm.TIPO_CHAPA, "Chapa de ligação", 4, 0.2, 150, 9.5),
    )
)


def abrir() -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def gravar_no_projeto(lista: lm.ListaDeMaterial | None, dados: em.EsforcosDoModelo | None) -> None:
    projeto = obter_projeto_ativo()
    if lista is not None:
        projeto["lista_de_material"] = lm.para_dicionario(lista)
    if dados is not None:
        projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    salvar_projeto(projeto, motivo="teste")


def sem_ajuda(t: AppTest) -> set[tuple[str, str]]:
    return {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def test_sem_projeto_pede_um(banco_isolado):
    t = abrir()
    assert any("Nenhum projeto ativo" in i.value for i in t.info)


def test_lista_gravada_mostra_resumo_pendencias_e_conferencia(banco_com_projeto):
    gravar_no_projeto(LISTA, portico(PILAR, PILAR_2))
    t = abrir()
    assert not sem_ajuda(t), sorted(sem_ajuda(t))
    r = lm.resumir(LISTA)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Massa total"] == f"{r.massa_total_kg:,.0f} kg".replace(",", " ")
    assert metricas["Itens sem massa"] == "1"
    assert any("PERFIL ESQUISITO" in w.value for w in t.warning)
    subtitulos = [s.value for s in t.subheader]
    assert "Por perfil" in subtitulos and "Chapas por espessura" in subtitulos
    conferencia = " ".join(x.value for x in [*t.success, *t.warning])
    assert "Caso PP do modelo" in conferencia


def test_incluir_as_placas_de_base_e_gravar(banco_com_projeto):
    gravar_no_projeto(LISTA, portico(PILAR, PILAR_2))
    t = abrir()
    t.button(key="lm_placas").click().run()
    assert not t.exception
    salva = lm.lista_do_projeto(obter_projeto_ativo())
    placas = [i for i in salva.itens if i.marca == lm.MARCA_PLACA_DE_BASE]
    assert len(placas) == 1 and placas[0].quantidade == 2
    t.number_input(key="lm_acrescimo_1").set_value(8.0)
    t.button(key="lm_gravar").click().run()
    assert not t.exception
    assert lm.lista_do_projeto(obter_projeto_ativo()).acrescimo_pct == 8.0


def test_sem_pilares_o_botao_das_placas_fica_desligado(banco_com_projeto):
    gravar_no_projeto(lm.ListaDeMaterial(), None)
    t = abrir()
    assert t.button(key="lm_placas").disabled
    assert any("importe em Esforços do modelo o caso PP" in w.value for w in t.warning)


def test_guia_tem_o_capitulo_com_o_exemplo_que_o_nucleo_calcula(banco_isolado):
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Lista de material"
    t.run()
    assert "Lista de material" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert "514,7 kg de itens" in esperado and "540,5 kg com o acréscimo" in esperado
