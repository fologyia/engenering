"""A página Cargas do esqueleto pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components.cargas_esqueleto_help import AJUDA
from core import cargas_esqueleto as ce
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/cargas_esqueleto.py"


def abrir() -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
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


def test_sem_projeto_pede_um(banco_isolado):
    t = abrir()
    assert any("Nenhum projeto ativo" in i.value for i in t.info)


def test_pagina_mostra_as_cargas_com_ajuda_em_tudo(banco_com_projeto):
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["PP: gravidade"] == "× 1,07"
    assert metricas["SC"].endswith("kN") and metricas["PE"].endswith("kN")
    assert len(t.get("image")) == 1
    conferencia = next(d.value for d in t.dataframe if "Confere" in d.value.columns)
    assert set(conferencia["Confere"]) == {"sim"}


def test_gravar_e_enviar_ao_plano(banco_com_projeto):
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(
        pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PE", cargas=[pc.CargaDoModelo("x", 1.0)]))
    )
    salvar_projeto(projeto, motivo="teste")
    t = abrir()
    assert any("PE foram informados de outra forma" in w.value for w in t.warning)
    t.button(key="ce_enviar").click().run()
    assert not t.exception
    salvo = obter_projeto_ativo()
    plano = pc.plano_do_projeto(salvo)
    assert {"PP", "PE", "SC"} <= set(plano.codigos)
    assert plano.acao("PE").origem == ce.ORIGEM and plano.fator_peso_proprio > 1
    assert ce.entrada_do_projeto(salvo) is not None
    t.button(key="registrar_cargas_esqueleto").click().run()
    assert not t.exception
    assert any(r["modulo_id"] == ce.MODULO_ID for r in obter_projeto_ativo()["registros_tecnicos"])


def test_eixo_invalido_explica_sem_quebrar(banco_com_projeto):
    t = abrir()
    t.text_input(key="ce_eixos_x_0").input("0; seis").run()
    assert not t.exception
    assert any("não é um número de eixo" in e.value for e in t.error)


def test_guia_tem_o_capitulo_com_o_exemplo_que_o_nucleo_calcula(banco_isolado):
    r = ce.calcular(ce.EntradaEsqueleto())
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Cargas do esqueleto"
    t.run()
    assert "Cargas do esqueleto" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"SC total {ce.resumo_do_caso(r, 'SC'):.1f}".replace(".", ",") in esperado
    assert "2 vigas secundárias em cada vão" in esperado


def test_sem_o_esqueleto_do_modelo_oferece_a_macro(banco_com_projeto):
    t = abrir()
    assert any("Sem o esqueleto do modelo ainda" in c.value for c in t.caption)
    assert "Cargas do piso pelo esqueleto do modelo" in [s.value for s in t.subheader]


def test_cargas_do_piso_pelo_esqueleto_vao_ao_plano(banco_com_projeto):
    from core import cargas_pelo_modelo as cpm
    from core import leitura_do_modelo as ld
    from tests.test_cargas_pelo_modelo import piso_6x3

    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(piso_6x3())
    projeto["plano_de_cargas"] = pc.para_dicionario(
        pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")]),
        )
    )
    salvar_projeto(projeto, motivo="teste")
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["SC no piso"] == "90,0 kN" and metricas["Vigas carregadas"] == "3"
    assert "Cargas nas vigas — SC" in [s.value for s in t.subheader]
    vigas = next(d.value for d in t.dataframe if "Viga (corpo no SolidWorks)" in d.value.columns)
    assert sorted(vigas["Viga (corpo no SolidWorks)"]) == ["V0", "V1", "V2"]
    assert any(
        c.value.endswith("Conferência: 90,00 kN nas vigas = 5,00 kN/m² × 18,000 m² projetados.")
        for c in t.caption
    )
    assert any("SC já tem cargas de outra origem" in w.value for w in t.warning)
    t.button(key="ce_modelo_enviar").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    sc = pc.plano_do_projeto(obter_projeto_ativo()).acao("SC")
    assert sc.origem == cpm.ORIGEM and {c.unidade for c in sc.cargas} == {"kN/m"}
    assert len(sc.cargas) == 3
