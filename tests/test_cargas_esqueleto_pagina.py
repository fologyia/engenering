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
    titulos = [s.value for s in t.subheader]
    assert "Esqueleto do modelo" in titulos and "1. Eixos e níveis" in titulos
    assert not [tg for tg in t.toggle if tg.key == "ce_usar_grade"]


def _com_o_piso_6x3(plano: pc.PlanoDeCargas | None = None, **extra) -> None:
    from core import leitura_do_modelo as ld
    from tests.test_cargas_pelo_modelo import piso_6x3

    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(piso_6x3())
    if plano is not None:
        projeto["plano_de_cargas"] = pc.para_dicionario(plano)
    projeto.update(extra)
    salvar_projeto(projeto, motivo="teste")


def test_com_o_esqueleto_a_pagina_trabalha_pelo_modelo(banco_com_projeto):
    """A leitura do modelo, a carga por chapa, o 3D e um envio só; a grade fica guardada."""
    from core import cargas_pelo_modelo as cpm
    from core import piso_do_modelo as pm

    _com_o_piso_6x3(
        pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")]),
        )
    )
    t = abrir()
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    titulos = [s.value for s in t.subheader]
    assert titulos[-5:] == [
        "1. O que o programa entendeu do modelo",
        "2. Conferir em 3D",
        "3. Guarda-corpo nas bordas do piso",
        "4. Cargas nas vigas",
        "5. Enviar ao plano de cargas",
    ]
    assert "1. Eixos e níveis" not in titulos  # a grade só aparece a pedido
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Vigas"] == "3" and metricas["Chapas de piso"] == "1"
    assert metricas["Níveis de piso"] == "1"
    assert metricas["SC no piso"] == "90,0 kN" and metricas["Vigas carregadas"] == "3"
    vigas = next(d.value for d in t.dataframe if "Viga (corpo no SolidWorks)" in d.value.columns)
    assert sorted(vigas["Viga (corpo no SolidWorks)"]) == ["V0", "V1", "V2"]
    confere = next(d.value for d in t.dataframe if "Das chapas (kN)" in d.value.columns)
    assert set(confere["Confere"]) == {"sim"}
    muda = next(d.value for d in t.dataframe if "O que muda" in d.value.columns)
    sc = muda[muda["Caso"] == "SC"].iloc[0]
    assert "sai a carga por área" in sc["O que muda"] and sc["Depois (kN)"] == 90.0
    assert len(t.get("image")) >= 2  # o 3D e a planta das bordas
    t.button(key="ce_enviar_tudo").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    salvo = obter_projeto_ativo()
    plano = pc.plano_do_projeto(salvo)
    sc = plano.acao("SC")
    assert sc.origem == cpm.ORIGEM and {c.unidade for c in sc.cargas} == {"kN/m"}
    assert len(sc.cargas) == 3 and all(pm.e_linha_do_piso(c) for c in sc.cargas)
    assert sum(c.resultante for c in sc.cargas) == 90.0
    assert plano.fator_peso_proprio == 1.07 and "PP" in plano.codigos
    assert pm.CHAVE_DO_PROJETO in salvo
    # Reaberta, a página já não tem o que enviar.
    t = abrir()
    assert any("não há o que enviar" in c.value for c in t.caption)


def test_tipo_e_carga_da_chapa_mudam_pela_tabela_gravada(banco_com_projeto):
    """A escolha gravada volta à tela: a chapa sem carga não manda nada às vigas."""
    from core import piso_do_modelo as pm

    escolha = pm.EscolhaDoPiso(chapas={"Piso": pm.EscolhaDaChapa(pm.TIPO_SEM_CARGA, 5.0)})
    _com_o_piso_6x3(**{pm.CHAVE_DO_PROJETO: pm.para_dicionario(escolha)})
    t = abrir()
    assert "SC no piso" not in {m.label for m in t.metric}
    assert any("Nenhuma chapa com carga" in c.value for c in t.caption)
    um_sentido = pm.EscolhaDoPiso(
        chapas={"Piso": pm.EscolhaDaChapa(pm.TIPO_PISO, 2.0, 0.5, "Um sentido")},
        peso=pm.PESO_INFORMADO,
    )
    _com_o_piso_6x3(**{pm.CHAVE_DO_PROJETO: pm.para_dicionario(um_sentido)})
    t = abrir()
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["SC no piso"] == "36,0 kN" and metricas["PE no piso"] == "9,0 kN"


def test_grade_de_exemplo_nao_vai_ao_plano_com_o_esqueleto_no_projeto(banco_com_projeto):
    """O caso do usuário (24/10): com o esqueleto de uma plataforma pequena no projeto, a grade de
    exemplo da seção de eixos mandava 24 vezes a sobrecarga ao plano. Agora a grade fica fechada
    e, aberta, o botão dela trava."""
    _com_o_piso_6x3()
    t = abrir()
    assert not [b for b in t.button if b.key == "ce_enviar"]
    t.toggle(key="ce_usar_grade").set_value(True).run()
    assert not t.exception, [str(e.value) for e in t.exception]
    assert any("as cargas da grade não são as do seu modelo" in e.value for e in t.error)
    assert t.button(key="ce_enviar").disabled


def test_cargas_da_grade_que_sobraram_saem_no_envio(banco_com_projeto):
    grade = pc.CargaDoModelo("N1 · eixo A · 1–2", 0.585, "kN/m", "Z (vertical)", "", 4, 6.0)
    borda = pc.CargaDoModelo("V0", 0.36, "kN/m", "Z (vertical)", "", 1, 6.0)
    _com_o_piso_6x3(pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PE", cargas=[grade, borda])))
    t = abrir()
    chave = next(tg for tg in t.toggle if tg.label.startswith("Tirar do plano as 1 linha(s)"))
    assert chave.value is True and "14,04 kN" in chave.label
    muda = next(d.value for d in t.dataframe if "O que muda" in d.value.columns)
    assert "saem 1 linha(s) da grade de eixos" in muda[muda["Caso"] == "PE"].iloc[0]["O que muda"]
    t.button(key="ce_enviar_tudo").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    pe = pc.plano_do_projeto(obter_projeto_ativo()).acao("PE")
    assert borda in pe.cargas and grade not in pe.cargas  # a lançada à mão fica


def test_esqueleto_sem_chapa_mostra_o_guarda_corpo_e_abre_a_grade(banco_com_projeto):
    from core import leitura_do_modelo as ld
    from tests.test_guarda_corpo_do_modelo import plataforma

    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(
        ld.GeometriaDoModelo(corpos=tuple(plataforma(com_chapa=False)))
    )
    salvar_projeto(projeto, motivo="teste")
    t = abrir()
    assert any("não tem chapa de piso" in i.value for i in t.info)
    titulos = [s.value for s in t.subheader]
    assert "3. Guarda-corpo nas bordas do piso" in titulos and "1. Eixos e níveis" in titulos
