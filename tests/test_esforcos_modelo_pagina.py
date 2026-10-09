"""A página Esforços do modelo pela interface (AppTest), com casos já importados no projeto."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.esforcos_modelo_help import AJUDA
from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_esforcos_modelo import PILAR, importar, plano_do_portico

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/esforcos_modelo.py"
TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "multiselect",
    "toggle",
    "radio",
    "text_input",
    "button",
    "download_button",
    "metric",
    "subheader",
)
ISENTOS = {("text_input", "Nome do novo projeto")}


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def _ajuda(elemento) -> str | None:
    proto = getattr(elemento, "proto", None)
    for campo in ("help", "tooltip"):
        for origem in (elemento, proto):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return None


def _rotulo(elemento) -> str:
    proto = getattr(elemento, "proto", None)
    for origem in (elemento, proto):
        for campo in ("label", "body"):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return repr(elemento)[:60]


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def gravar_no_projeto(dados: em.EsforcosDoModelo | None = None) -> None:
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(plano_do_portico())
    if dados is not None:
        projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    salvar_projeto(projeto, motivo="teste")


def sem_ajuda(t: AppTest) -> set[tuple[str, str]]:
    return {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - ISENTOS


def test_sem_projeto_pede_um(banco_isolado):
    t = abrir()
    assert any("Nenhum projeto ativo" in i.value for i in t.info)


def test_projeto_sem_casos_explica_o_que_exportar(banco_com_projeto):
    gravar_no_projeto()
    t = abrir()
    assert any("Nenhum caso importado" in c.value for c in t.caption)
    assert not sem_ajuda(t), sorted(sem_ajuda(t))


@pytest.mark.parametrize("estado", [{}, {"em_estados": ["ELU normal", "ELS rara"]}])
def test_com_casos_mostra_conferencia_barras_e_envoltoria(banco_com_projeto, estado):
    gravar_no_projeto(importar("PP", "SC", "W0", "W180"))
    t = abrir(**estado)
    assert not sem_ajuda(t), sorted(sem_ajuda(t))
    subtitulos = " ".join(s.value for s in t.subheader)
    for trecho in (
        "2. Casos importados (4)",
        "3. Conferência das reações",
        "4. Barras do modelo (3)",
        "5. Pior caso de cada barra",
    ):
        assert trecho in subtitulos, trecho
    assert any("as reações equilibram" in s.value for s in t.success)
    envoltoria = next(d.value for d in t.dataframe if "Compressão máx. (kN)" in d.value.columns)
    pilar = envoltoria[envoltoria["Barra"] == PILAR].iloc[0]
    assert pilar["Compressão máx. (kN)"] == pytest.approx(-52.6, abs=0.05)


def test_gravar_a_tabela_das_barras_e_remover_um_caso(banco_com_projeto):
    gravar_no_projeto(importar("PP", "SC"))
    t = abrir()
    t.button(key="em_gravar_barras").click().run()
    assert not t.exception
    salvo = em.esforcos_do_projeto(obter_projeto_ativo())
    assert set(salvo.membros) == set(salvo.nomes_dos_membros)
    t.selectbox(key="em_caso_remover").set_value("SC")
    t.button(key="em_remover").click().run()
    assert not t.exception
    assert set(em.esforcos_do_projeto(obter_projeto_ativo()).casos) == {"PP"}


def test_guia_tem_o_capitulo_com_o_exemplo_que_o_nucleo_calcula(banco_isolado):
    from core import load_combinations as comb

    r = em.envoltoria(importar("PP", "SC", "W0", "W180"), plano_do_portico(), [comb.ELU_NORMAL])
    pilar = next(m for m in r.membros if m.membro == PILAR)
    viga = next(m for m in r.membros if m.membro.startswith("Viga-2"))
    t = abrir(guia_modulo="Esforços do modelo")
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Esforços do modelo"
    t.run()
    assert "Esforços do modelo" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"{pilar.compressao.valor:.1f}".replace(".", ",").replace("-", "−") in esperado
    assert f"{pilar.m2.valor:.1f}".replace(".", ",") in esperado
    assert f"{viga.m2.valor:.1f}".replace(".", ",") in esperado
