"""A página Modelo em 3D pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.modelo_3d_help import AJUDA
from core import cena_do_modelo as cm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_cena_do_modelo import _esforcos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_guarda_corpo_do_modelo import plataforma

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/modelo_3d.py"


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(
            r'AJUDA\["([A-Za-z_0-9]+)"\]',
            (RAIZ / "components/modelo_3d_ui.py").read_text(encoding="utf-8"),
        )
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def _projeto_com_modelo(com_esforcos: bool = False) -> None:
    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(
        ld.GeometriaDoModelo(corpos=tuple(plataforma()), arquivo="plataforma_esqueleto.csv")
    )
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao(
            "PE",
            cargas=[pc.CargaDoModelo("Borda z0", 0.4, "kN/m", "Z (vertical)", comprimento_m=6)],
        ),
    )
    projeto["plano_de_cargas"] = pc.para_dicionario(plano)
    if com_esforcos:
        projeto["esforcos_do_modelo"] = em.para_dicionario(_esforcos(2.0))
    salvar_projeto(projeto, motivo="teste")


def test_sem_esqueleto_aponta_para_cargas_do_esqueleto(banco_com_projeto):
    t = abrir()
    assert any("ainda não tem o esqueleto" in i.value for i in t.info)


def test_modelo_aparece_com_ajuda_em_tudo(banco_com_projeto):
    _projeto_com_modelo()
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    assert len(t.get("imgs")) + len(t.get("image")) >= 1


@pytest.mark.parametrize(
    "estado",
    [
        {"m3_cor": cm.COR_POR_PERFIL, "m3_vista": "Superior", "m3_giro": 45},
        {"m3_cor": cm.COR_POR_VENTO, "m3_desenho": "Só eixos"},
        {"m3_cargas": "PE", "m3_barra": "Borda z0"},
        {"m3_cor": cm.COR_POR_NORMAL},
        {"m3_cor": cm.COR_POR_APROVEITAMENTO},
        {"m3_modo": "Casca translúcida", "m3_vista": "Lateral"},
    ],
)
def test_cada_opcao_abre_sem_erro(banco_com_projeto, estado):
    _projeto_com_modelo(com_esforcos=True)
    t = abrir(**estado)
    if estado.get("m3_cargas") == "PE":
        metricas = {m.label: m.value for m in t.metric}
        assert metricas["Cargas desenhadas (vertical)"] == "2,40 kN"
        assert metricas["Reações verticais"] == "100,00 kN"


def test_reacao_horizontal_com_a_direcao_da_secao(banco_com_projeto):
    from tests import test_direcoes_da_secao as tds

    d1 = (0.0, 1.0, 0.0)
    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(
        ld.GeometriaDoModelo(corpos=(tds.corpo(d1),), arquivo="pilar_esqueleto.csv")
    )
    projeto["esforcos_do_modelo"] = em.para_dicionario(tds.dados(d1))
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao(
            "W0",
            cargas=[
                pc.CargaDoModelo(tds.VIGA, tds.VENTO[0], "kN/m", "+X", comprimento_m=tds.L),
                pc.CargaDoModelo(tds.VIGA, tds.VENTO[1], "kN/m", "+Y", comprimento_m=tds.L),
            ],
        ),
    )
    projeto["plano_de_cargas"] = pc.para_dicionario(plano)
    salvar_projeto(projeto, motivo="teste")
    t = abrir(m3_caso_reacoes="W0", m3_cargas="W0")
    metricas = {m.label: m.value for m in t.metric}
    x, y = (-v * tds.L for v in tds.VENTO[:2])
    assert metricas["Reações horizontais (X / Y)"] == f"{x:.2f} / {y:.2f} kN".replace(".", ",")
    assert metricas["Cargas desenhadas (X / Y)"] == f"{-x:.2f} / {-y:.2f} kN".replace(".", ",")
    tabela = next(d.value for d in t.dataframe if "Direção 1" in d.value.columns)
    assert list(tabela["Direção 1"]) == ["+Y"] and list(tabela["Sentido pelo caso"]) == ["W0"]
