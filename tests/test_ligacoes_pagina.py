"""A página Ligações estruturais pela interface (AppTest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.ligacoes_help import AJUDA
from core import ligacoes as lg
from core import ligacoes_soldadas as ls
from core.project_store import obter_projeto_ativo
from core.technical_modules import listar_modulos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/ligacoes_estruturais.py"
SOLDADAS = (lg.SOLDA, lg.BARRA_SOLDADA, lg.CHAPA_NO_APOIO)
PARAFUSADAS = (lg.CHAPA_SIMPLES, lg.CANTONEIRA_DUPLA, lg.PERFIL_FRIO)


def _escolher(tipo: str) -> dict[str, str]:
    """O estado que escolhe o tipo: a parte (parafusadas ou soldadas) e o tipo dentro dela."""
    if tipo in SOLDADAS:
        return {"lig_parte": "soldadas", "lig_tipo_solda": tipo}
    return {"lig_parte": "parafusadas", "lig_tipo_parafuso": tipo}


def abrir(tipo: str | None = None, **estado) -> AppTest:
    if tipo is not None:
        estado = {**_escolher(tipo), **estado}
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
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Ligações e bases"


@pytest.mark.parametrize(
    "estado",
    [
        {"tipo": lg.CHAPA_SIMPLES},
        {"tipo": lg.PERFIL_FRIO, "lig_f_perfil": lg.PERFIL_A_MAO},
        {"tipo": lg.SOLDA},
        {"tipo": lg.SOLDA, "lig_s_m": 2.0, "lig_s_arranjo": lg.ARRANJO_TRES_LADOS},
        {"tipo": lg.CANTONEIRA_DUPLA},
        {"tipo": lg.BARRA_SOLDADA},
        {"tipo": lg.BARRA_SOLDADA, "lig_b_nc": 60.0, "lig_b_apoio": ls.APOIO_PERFIL},
        {"tipo": lg.CHAPA_NO_APOIO},
        {"tipo": lg.CHAPA_NO_APOIO, "lig_c2_tipo": ls.TIPO_PARCIAL},
        {"tipo": lg.CHAPA_NO_APOIO, "lig_c2_tipo": ls.TIPO_TOTAL},
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


def test_parafusadas_e_soldadas_separadas(banco_isolado):
    t = abrir()
    assert t.segmented_control(key="lig_parte").value == "parafusadas"
    tipos = t.segmented_control(key="lig_tipo_parafuso")
    assert len(tipos.options) == len(PARAFUSADAS)
    assert all("lig_tipo_solda" not in s.id for s in t.segmented_control)
    t.segmented_control(key="lig_tipo_parafuso").set_value(lg.CANTONEIRA_DUPLA).run()
    t.segmented_control(key="lig_parte").set_value("soldadas").run()
    assert not t.exception
    assert len(t.segmented_control(key="lig_tipo_solda").options) == len(SOLDADAS)
    assert all("lig_tipo_parafuso" not in s.id for s in t.segmented_control)
    assert t.selectbox(key="lig_s_metodo").value in lg.METODOS_SOLDA
    t.segmented_control(key="lig_parte").set_value("parafusadas").run()
    assert t.segmented_control(key="lig_tipo_parafuso").value == lg.CANTONEIRA_DUPLA


def test_numeros_da_chapa_simples_iguais_ao_nucleo(banco_isolado):
    t = abrir()
    r = lg.calcular(lg.EntradaChapaSimples())
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] == r.status
    assert metricas["Aproveitamento"] == f"{100 * r.aproveitamento_maximo:.0f} %"


def test_entrada_impossivel_vira_erro_claro(banco_isolado):
    t = abrir(tipo=lg.PERFIL_FRIO, lig_f_perfil=lg.PERFIL_A_MAO, lig_f_x=500.0)
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


def _detalhamento(t: AppTest) -> dict[str, str]:
    tabela = t.table[0].value
    return {
        str(item): str(valor) for item, valor in zip(tabela.index, tabela["Valor"], strict=True)
    }


def test_dimensionar_a_barra_mostra_os_filetes_adotados(banco_isolado):
    t = abrir(tipo=lg.BARRA_SOLDADA)
    r = lg.calcular(ls.EntradaBarraSoldada())
    detalhes = _detalhamento(t)
    assert detalhes == dict(lg.detalhamento_adotado(r))
    assert detalhes["Filete do dorso"] == f"{r.grandezas['l_dorso_mm']:.0f} mm"
    assert detalhes["Solda da chapa de nó no apoio"].startswith("dois filetes de")
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] == r.status
    assert metricas["Margem restante"] == f"{100 * (1 - r.aproveitamento_maximo):.0f} %"
    assert any(m.value.startswith("Atende às verificações executadas") for m in t.success)


def _chaves_na_tela(t: AppTest) -> set[str]:
    return {
        e.key
        for tipo in ("number_input", "selectbox", "toggle")
        for e in t.get(tipo)
        if getattr(e, "key", None)
    }


def test_barra_mostra_so_os_campos_que_se_aplicam(banco_isolado):
    t = abrir(tipo=lg.BARRA_SOLDADA)  # cantoneira, dimensionar, sem compressão, com apoio
    chaves = _chaves_na_tela(t)
    assert {"lig_b_cant", "lig_b_dist", "lig_b_passo", "lig_b_theta"} <= chaves
    assert not {"lig_b_larg", "lig_b_t", "lig_b_la", "lig_b_lb", "lig_b_k", "lig_b_lliv"} & chaves
    assert "lig_b_t_apoio" in chaves and "lig_b_perfil_apoio" not in chaves
    t.selectbox(key="lig_b_peca").set_value(ls.PECA_CHAPA).run()
    t.selectbox(key="lig_b_modo").set_value(ls.MODO_VERIFICAR).run()
    t.number_input(key="lig_b_nc").set_value(50.0).run()
    t.toggle(key="lig_b_com_apoio").set_value(False).run()
    assert not t.exception
    chaves = _chaves_na_tela(t)
    assert {"lig_b_larg", "lig_b_t", "lig_b_la", "lig_b_lb", "lig_b_k", "lig_b_lliv"} <= chaves
    assert not {"lig_b_cant", "lig_b_dist", "lig_b_passo", "lig_b_theta", "lig_b_apoio"} & chaves


def test_campo_escondido_guarda_o_valor(banco_isolado):
    t = abrir(tipo=lg.BARRA_SOLDADA, lig_b_peca=ls.PECA_CHAPA)
    t.number_input(key="lig_b_larg").set_value(77.0).run()
    t.selectbox(key="lig_b_peca").set_value(ls.PECA_CANTONEIRA).run()
    assert "lig_b_larg" not in _chaves_na_tela(t)
    t.selectbox(key="lig_b_peca").set_value(ls.PECA_CHAPA).run()
    assert t.number_input(key="lig_b_larg").value == 77.0


@pytest.mark.parametrize(
    "estado, aparecem, somem",
    [
        ({}, {"lig_c2_lados", "lig_c2_perna", "lig_c2_inter", "lig_c2_seg", "lig_c2_passo"},
         {"lig_c2_prof", "lig_c2_menos3", "lig_c2_nseg"}),
        ({"lig_c2_tipo": ls.TIPO_TOTAL}, {"lig_c2_eletrodo"},
         {"lig_c2_lados", "lig_c2_perna", "lig_c2_prof", "lig_c2_inter", "lig_c2_seg"}),
        ({"lig_c2_tipo": ls.TIPO_PARCIAL, "lig_c2_modo": ls.MODO_VERIFICAR},
         {"lig_c2_lados", "lig_c2_prof", "lig_c2_menos3"},
         {"lig_c2_perna", "lig_c2_inter", "lig_c2_passo"}),
        ({"lig_c2_apoio": ls.APOIO_PERFIL}, {"lig_c2_perfil_apoio", "lig_c2_orient", "lig_c2_perto"},
         {"lig_c2_t_apoio"}),
    ],
)  # fmt: skip
def test_chapa_no_apoio_mostra_so_os_campos_que_se_aplicam(banco_isolado, estado, aparecem, somem):
    t = abrir(tipo=lg.CHAPA_NO_APOIO, **estado)
    chaves = _chaves_na_tela(t)
    assert aparecem <= chaves and not somem & chaves


def test_tabela_resumida_e_detalhes_das_verificacoes(banco_isolado):
    t = abrir(tipo=lg.BARRA_SOLDADA)
    r = lg.calcular(ls.EntradaBarraSoldada())
    grupos = lg.verificacoes_por_grupo(r)
    tabelas = t.dataframe
    assert len(tabelas) == len(grupos)
    for tabela, (_, linhas) in zip(tabelas, grupos, strict=True):
        assert list(tabela.value.columns) == [
            "Verificação", "Solicitante", "Resistente / limite", "Aproveitamento", "Status",
        ]  # fmt: skip
        assert len(tabela.value) == len(linhas)
    # o AppTest lista o expansor com ícone como "status"
    rotulos = [e.label for e in (*t.expander, *t.status)]
    assert any(r.startswith("Fórmulas e itens da norma") for r in rotulos), rotulos
    assert any(r.startswith("Escopo, premissas") for r in rotulos), rotulos


def test_memorial_da_ligacao_na_pagina(banco_isolado):
    t = abrir(tipo=lg.CHAPA_NO_APOIO)
    chaves = {b.proto.id.split("-")[-1] for b in t.get("download_button")}
    assert any("lig_memorial_word" in b.proto.id for b in t.get("download_button")), chaves
    assert any("lig_memorial_pdf" in b.proto.id for b in t.get("download_button")), chaves
