"""A Central de relatórios com análises de flambagem e parafusos: o memorial que sai da tela."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.project_store import adicionar_registro_tecnico, obter_projeto_ativo, salvar_projeto
from tests.test_memorial_verificacoes import registro_flambagem, registro_ligacao, texto_word

# Caminho absoluto: o AppTest resolve um relativo contra a pasta do arquivo de teste nas versões
# novas do Streamlit (ver test_flambagem_pagina.py).
APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGINA = "app_pages/central_relatorios.py"
PERFIL_INCLUSAO = "Para incluir em outro documento"


def abrir() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def registrar_analises() -> str:
    projeto = obter_projeto_ativo()
    adicionar_registro_tecnico(projeto["id"], registro_flambagem(3000.0, 150.0, Mx_kNm=20.0))
    adicionar_registro_tecnico(projeto["id"], registro_flambagem(6500.0, 700.0, Mx_kNm=35.0))
    adicionar_registro_tecnico(projeto["id"], registro_ligacao())
    return projeto["id"]


def gerar_rapido(teste: AppTest, projeto_id: str) -> dict:
    teste.button(key="gerar_rapido").click().run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste.session_state[f"relatorio_rapido_{projeto_id}"]


def test_memorial_padrao_traz_o_que_passou_e_o_que_nao_passou(banco_com_projeto):
    projeto_id = registrar_analises()
    gerado = gerar_rapido(abrir(), projeto_id)
    texto = texto_word(gerado["word"])
    for esperado in (
        "Resumo executivo",
        "Aprovações",
        "Resultado: NÃO ATENDE.",
        "Resultado: ATENDE.",
        "O que passou (",
        "Não passou (",
        "O que não passou, por cálculo.",
    ):
        assert esperado in texto, esperado
    assert gerado["pdf"].startswith(b"%PDF")


def test_perfil_para_incluir_em_outro_documento_gera_so_os_capitulos(banco_com_projeto):
    projeto_id = registrar_analises()
    projeto = obter_projeto_ativo()
    projeto["configuracao_relatorio"] = {"perfil": PERFIL_INCLUSAO}
    salvar_projeto(projeto)

    teste = abrir()
    gerado = gerar_rapido(teste, projeto_id)
    texto = texto_word(gerado["word"])
    for ausente in ("Resumo executivo", "Controle do documento", "Aprovações", "Data de aprovação"):
        assert ausente not in texto, ausente
    assert "MEMÓRIA DE CÁLCULO · " in texto
    assert "1. Quadro-resumo dos cálculos" in texto and "2. Memória de cálculo" in texto
    assert "O que passou (" in texto and "Não passou (" in texto
    assert gerado["pdf"].startswith(b"%PDF")


def test_a_pagina_mostra_o_perfil_novo_e_explica_o_que_ele_faz(banco_com_projeto):
    registrar_analises()
    projeto = obter_projeto_ativo()
    projeto["configuracao_relatorio"] = {"perfil": PERFIL_INCLUSAO}
    salvar_projeto(projeto)
    teste = abrir()
    legendas = " ".join(str(c.value) for c in teste.caption)
    assert "só os capítulos numerados" in legendas
    sumario = " ".join(str(m.value) for m in teste.markdown)
    assert "Aprovações" not in sumario  # o sumário planejado não promete o que o modo não gera
