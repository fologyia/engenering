"""A página Ligação de contraventamento, exercitada pela interface (AppTest), e os seus “?”.

Três contratos: (1) todo texto de ``components/contraventamento_help.py`` é usado por algum campo e
todo campo usa um texto que existe; (2) todo campo da página — em cada estado que muda os campos —
tem o seu “?”; (3) a tela mostra o que o núcleo calcula, trata entrada impossível com erro claro e
o registro leva a tabela inteira para o projeto.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.contraventamento_help import AJUDA
from components.contraventamento_ui import MODO_COMPLETO, MODO_SIMPLES
from core import contraventamento_ufm as ufm
from core.project_store import obter_projeto_ativo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/ligacao_contraventamento.py"
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "contraventamento_ui.py",
    RAIZ / "app_pages" / "ligacao_contraventamento.py",
]
USO = re.compile(r'AJUDA\["([A-Za-z_0-9]+)"\]')


def _chaves_usadas() -> set[str]:
    usadas: set[str] = set()
    for arquivo in ARQUIVOS_COM_AJUDA:
        usadas |= set(USO.findall(arquivo.read_text(encoding="utf-8")))
    return usadas


def test_todo_campo_usa_um_texto_que_existe():
    inexistentes = _chaves_usadas() - set(AJUDA)
    assert not inexistentes, f"chaves sem texto em AJUDA: {sorted(inexistentes)}"


def test_nenhum_texto_de_ajuda_fica_sem_uso():
    orfaos = set(AJUDA) - _chaves_usadas()
    assert not orfaos, f"textos de ajuda que nenhum campo usa: {sorted(orfaos)}"


def test_textos_de_ajuda_sao_curtos_e_sem_marcas_de_rascunho():
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and len(texto) > 15, chave
        assert len(texto) <= 900, f"{chave}: dica longa demais ({len(texto)} caracteres)"
        assert "TODO" not in texto and "XXX" not in texto, chave


@pytest.mark.parametrize(
    ("chave", "deve_citar"),
    [
        ("metodo", ("LRFD", "ASD", "φ·R_n")),
        ("theta", ("vertical", "45°")),
        ("k", ("raio", "alma")),
        ("caso", ("Geral", "Especial 1", "Especial 3")),
        ("calc_P", ("sen θ",)),
        ("L_flamb", ("flambagem", "metade")),
        ("FEXX", ("482,6", "E70XX")),
        ("res_status", ("OK", "NÃO OK", "ALERTA", "INFO")),
    ],
)
def test_dicas_para_quem_nao_conhece_o_termo_explicam_o_termo(chave, deve_citar):
    for trecho in deve_citar:
        assert trecho in AJUDA[chave], (chave, trecho)


TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "checkbox",
    "radio",
    "text_input",
    "date_input",
    "button_group",
    "button",
    "download_button",
    "metric",
    "subheader",
)
ISENTOS_DE_AJUDA = {
    ("text_input", "Nome do novo projeto"),
}


def _ajuda_de(elemento) -> str | None:
    proto = getattr(elemento, "proto", None)
    for campo in ("help", "tooltip"):
        for origem in (elemento, proto):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return None


def _rotulo_de(elemento) -> str:
    proto = getattr(elemento, "proto", None)
    for origem in (elemento, proto):
        for campo in ("label", "body"):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return repr(elemento)[:60]


def sem_ajuda(teste: AppTest) -> set[tuple[str, str]]:
    faltam = set()
    for tipo in TIPOS_COM_AJUDA:
        for elemento in teste.get(tipo):
            if not _ajuda_de(elemento):
                faltam.add((tipo, _rotulo_de(elemento)))
    return faltam - ISENTOS_DE_AJUDA


def abrir(banco_isolado, **estado) -> AppTest:
    """Abre a página; sem ``cv_modo``, no modo completo (o das medidas informadas)."""
    estado.setdefault("cv_modo", MODO_COMPLETO)
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def metrica(teste: AppTest, rotulo: str) -> str:
    return next(m.value for m in teste.metric if m.label == rotulo)


ESTADOS = [
    pytest.param({}, id="padrao"),
    pytest.param({"cv_metodo": "ASD"}, id="asd"),
    pytest.param({"cv_caso": ufm.CASO_1}, id="caso-1"),
    pytest.param({"cv_caso": ufm.CASO_2}, id="caso-2"),
    pytest.param({"cv_caso": ufm.CASO_2, "cv_anular_Vb": True}, id="caso-2-anula"),
    pytest.param({"cv_caso": ufm.CASO_3, "cv_theta": 62.0}, id="caso-3"),
    pytest.param({"cv_viga_origem": "Catálogo do programa"}, id="viga-do-catalogo"),
    pytest.param({"cv_coluna_origem": "Catálogo do programa"}, id="coluna-do-catalogo"),
    pytest.param({"cv_distorcao": True}, id="distorcao"),
    pytest.param({"cv_H_horizontal": 500.0}, id="forca-pela-horizontal"),
    pytest.param({"cv_so_atencao": True}, id="so-atencao"),
    pytest.param({"cv_t_chapa": 6.0}, id="chapa-fina"),
    pytest.param({"cv_corte_h": 5000.0}, id="entrada-invalida"),
    pytest.param({"cv_modo": MODO_SIMPLES}, id="simplificado"),
    pytest.param(
        {"cv_modo": MODO_SIMPLES, "cv_P_tracao": 50.0, "cv_P_compressao": 0.0},
        id="simplificado-pequeno",
    ),
]


@pytest.mark.parametrize("estado", ESTADOS)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    faltam = sem_ajuda(t)
    assert not faltam, f"campos sem “?”: {sorted(faltam)}"


def test_quadro_resumo_do_exemplo_padrao_fecha(banco_isolado):
    t = abrir(banco_isolado)
    assert metrica(t, "Status geral") in ("OK", "ALERTA")
    assert metrica(t, "Aproveitamento máximo").endswith(" %")
    assert metrica(t, "Parafusos (mínimo necessário)").startswith("10 (")
    assert not t.error


def test_chapa_fina_reprova_e_a_tela_diz(banco_isolado):
    t = abrir(banco_isolado, cv_t_chapa=6.0)
    assert metrica(t, "Status geral") == "NÃO OK"


def test_entrada_impossivel_vira_erro_claro_e_nao_calcula(banco_isolado):
    t = abrir(banco_isolado, cv_corte_h=5000.0)
    assert any("corte" in e.value.lower() for e in t.error)
    assert not t.metric or all(m.label != "Status geral" for m in t.metric)


def test_forca_pela_horizontal_calcula_p_sobre_sen_theta(banco_isolado):
    t = abrir(banco_isolado, cv_H_horizontal=500.0, cv_theta=30.0)
    assert metrica(t, "P = H / sen θ [kN]") == "1000,0"


def test_registrar_leva_a_ligacao_para_o_projeto(banco_com_projeto):
    t = abrir(banco_com_projeto, cv_tag="LC-7")
    t.button(key="registrar_ligacao_contraventamento").click().run()
    assert not t.exception
    achados = [
        r
        for r in obter_projeto_ativo()["registros_tecnicos"]
        if r["modulo_id"] == "ligacao_contraventamento"
    ]
    assert len(achados) == 1
    assert achados[0]["entradas"]["tag"] == "LC-7"
    assert len(achados[0]["resultados"]["verificações"]) >= 20


# ------------------------------------------------------------------ modo simplificado
def test_modo_simplificado_dimensiona_e_fecha(banco_isolado):
    t = abrir(banco_isolado, cv_modo=MODO_SIMPLES)
    texto = " ".join(m.value for m in t.markdown)
    assert "Parafusos: 2 fileiras" in texto and "Espessura da chapa" in texto
    assert metrica(t, "Status geral") in ("OK", "ALERTA")
    assert not t.error
    # O simplificado não pede as medidas da chapa.
    assert not [n for n in t.number_input if n.key in ("cv_t_chapa", "cv_lh", "cv_lv")]


def test_modo_simplificado_usa_o_k_do_catalogo_gerdau(banco_isolado):
    t = abrir(banco_isolado, cv_modo=MODO_SIMPLES)
    legendas = " ".join(c.value for c in t.caption)
    assert "k = 28,5 mm (catálogo Gerdau)" in legendas  # W 530 × 85: 16,5 + (502 − 478)/2


def test_forca_que_chega_da_pagina_de_contraventamento_e_usada(banco_isolado):
    t = abrir(
        banco_isolado, cv_modo=MODO_SIMPLES, cv_P_tracao=123.4, cv_P_compressao=0.0, cv_theta=56.31
    )
    numeros = {n.key: n.value for n in t.number_input}
    assert numeros["cv_P_tracao"] == 123.4 and numeros["cv_theta"] == 56.31
