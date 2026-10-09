"""A página Contraventamento de estruturas abertas, exercitada pela interface (AppTest).

Contratos: todo texto de ajuda é usado e todo campo tem o seu “?” em cada estado da página; a tela
mostra o que o núcleo calcula; entrada impossível vira erro claro; o botão leva as forças para a
Ligação de contraventamento; o registro grava o cálculo no projeto.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.contraventamento_estrutura_help import AJUDA
from core import contraventamento_barras as cb
from core import contraventamento_plataforma as cp
from core import load_combinations as comb
from core.project_store import obter_projeto_ativo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/contraventamento_estrutura.py"
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "contraventamento_estrutura_ui.py",
    RAIZ / "app_pages" / "contraventamento_estrutura.py",
]
USO = re.compile(r'AJUDA\["([A-Za-z_0-9]+)"\]')


def _chaves_usadas() -> set[str]:
    usadas: set[str] = set()
    for arquivo in ARQUIVOS_COM_AJUDA:
        usadas |= set(USO.findall(arquivo.read_text(encoding="utf-8")))
    return usadas


def test_todo_campo_usa_um_texto_que_existe():
    assert not (_chaves_usadas() - set(AJUDA))


def test_nenhum_texto_de_ajuda_fica_sem_uso():
    assert not (set(AJUDA) - _chaves_usadas())


def test_textos_de_ajuda_sao_curtos_e_sem_marcas_de_rascunho():
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and len(texto) > 15, chave
        assert len(texto) <= 900, chave
        assert "TODO" not in texto and "XXX" not in texto, chave


TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "checkbox",
    "radio",
    "text_input",
    "date_input",
    "button",
    "download_button",
    "metric",
    "subheader",
)
ISENTOS = {("text_input", "Nome do novo projeto")}


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


def abrir(banco_isolado, **estado) -> AppTest:
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
    pytest.param({"ce_n_pisos": 2, "ce_h_andar": 3.0}, id="dois-pisos"),
    pytest.param({"ce_cotas_livres": "3,5; 7,0"}, id="cotas-livres"),
    pytest.param({"ce_mesmo_sistema": False}, id="sistemas-diferentes"),
    pytest.param({"ce_familia_x": cb.FAMILIA_TUBO, "ce_ligacao_x": cb.LIGACAO_SOLDADA}, id="tubo"),
    pytest.param({"ce_familia_x": cb.FAMILIA_BARRA_REDONDA}, id="tirante"),
    pytest.param({"ce_tipo_x": cp.TIPO_X_TRACAO_COMPRESSAO}, id="x-tracao-compressao"),
    pytest.param({"ce_tipo_x": cp.TIPO_V_INVERTIDO}, id="v-invertido"),
    pytest.param({"ce_ligacao_x": cb.LIGACAO_SOLDADA}, id="cantoneira-soldada"),
    pytest.param({"ce_guarda_corpo": False}, id="sem-guarda-corpo"),
    pytest.param({"ce_comb_servico": comb.ELS_FREQUENTE}, id="frequente"),
    pytest.param({"ce_so_atencao": True}, id="so-atencao"),
    pytest.param({"ce_cotas_livres": "abc"}, id="cotas-invalidas"),
    pytest.param(
        {"ce_familia_x": cb.FAMILIA_BARRA_REDONDA, "ce_tipo_x": cp.TIPO_DIAGONAL_SIMPLES},
        id="tirante-sem-x",
    ),
]


@pytest.mark.parametrize("estado", ESTADOS)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    faltam = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - ISENTOS
    assert not faltam, sorted(faltam)


def test_quadro_resumo_bate_com_o_nucleo(banco_isolado):
    from components.contraventamento_estrutura_ui import PILAR_PADRAO, VIGA_PADRAO
    from core import section_catalog as sc

    pilar, viga = sc.obter_perfil(PILAR_PADRAO), sc.obter_perfil(VIGA_PADRAO)
    esperado = cp.calcular(
        cp.EntradaContraventamento(
            largura_pilar_m=max(pilar.altura_mm, pilar.largura_mm) / 1e3,
            altura_viga_m=viga.altura_mm / 1e3,
        )
    )
    t = abrir(banco_isolado)
    assert metrica(t, "Status geral") == esperado.status
    assert metrica(t, "Aproveitamento máximo") == f"{100 * esperado.aproveitamento_maximo:.0f} %"
    x, y = esperado.vento.x.total_kN, esperado.vento.y.total_kN
    assert metrica(t, "Vento X / Y (kN)") == f"{x:.1f} / {y:.1f}".replace(".", ",")
    assert not t.error


def test_cotas_invalidas_viram_erro_claro(banco_isolado):
    t = abrir(banco_isolado, ce_cotas_livres="abc")
    assert any("Cotas dos pisos" in e.value for e in t.error)
    assert not any(m.label == "Status geral" for m in t.metric)


def test_tirante_fora_do_x_so_tracao_vira_erro(banco_isolado):
    t = abrir(
        banco_isolado,
        ce_familia_x=cb.FAMILIA_BARRA_REDONDA,
        ce_tipo_x=cp.TIPO_DIAGONAL_SIMPLES,
    )
    assert any("só serve para X só tração" in e.value for e in t.error)


def test_dois_pisos_mostram_andares_e_interpavimento(banco_isolado):
    t = abrir(banco_isolado, ce_n_pisos=2, ce_h_andar=3.0)
    tabelas = [d.value for d in t.dataframe]
    andares = next(tb for tb in tabelas if "Dir. / andar" in tb.columns)
    assert len(andares) == 4  # 2 direções × 2 andares


def test_botao_leva_as_forcas_para_a_ligacao(banco_isolado):
    t = abrir(banco_isolado)
    t.button(key="ce_levar_ligacao").click().run()
    assert not t.exception
    assert t.session_state["cv_P_tracao"] > 0
    assert 0 < t.session_state["cv_theta"] < 90
    assert t.session_state["cv_metodo"] == "LRFD"


def test_registrar_grava_no_projeto(banco_com_projeto):
    t = abrir(banco_com_projeto, ce_tag="PL-9")
    t.button(key="registrar_contraventamento_estrutura").click().run()
    assert not t.exception
    achados = [
        r
        for r in obter_projeto_ativo()["registros_tecnicos"]
        if r["modulo_id"] == "contraventamento_estrutura"
    ]
    assert len(achados) == 1 and achados[0]["entradas"]["tag"] == "PL-9"
