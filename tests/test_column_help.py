"""Os “?” da página Flambagem de colunas.

Dois contratos, o primeiro sem abrir o Streamlit:

* todo texto de ``components/column_help.py`` é usado por algum campo, e todo campo usa um texto
  que existe (nada de “?” vazio nem de texto órfão);
* todo campo da página, em cada estado que muda os campos, tem o seu “?” — e os termos que o
  usuário pode não conhecer (eixo x e y, K, C_b, M₁/M₂, tipo AL/AA…) são explicados lá.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components import column_ui as ui
from components.column_help import AJUDA
from core import column_buckling as cb

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "column_ui.py",
    RAIZ / "app_pages" / "flambagem_colunas.py",
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
        ("Lx", ("em torno de x", "eixo forte")),  # quem não sabe o que é o eixo x
        ("Ly", ("em torno de y", "eixo fraco")),
        ("apoio_x", ("Biapoiada", "engastada", "Tabela E.1")),
        ("k_recomendado", ("0,65", "0,80", "2,1")),
        ("kz_ativar", ("torção", "K_z")),
        ("cb", ("1,0", "conservador", "3,0")),
        ("cb_modo", ("momento", "quatro pontos")),
        ("razao_x", ("M₁", "curvatura reversa", "curvatura simples")),
        ("diagrama_x", ("C_m = 1,0", "M₁/M₂", "Força transversal")),
        ("par_tipo", ("AA", "AL", "grupo")),
        ("confirma_compacta", ("ALERTA", "nunca em OK")),
        ("mrd_x_ativar", ("não tem rotina", "informa")),
        ("res_status", ("OK", "NÃO OK", "ALERTA")),
        ("res_q", ("Q_s·Q_a", "A_ef")),
        ("res_interacao", ("mesma", "N/N_Rd")),
        ("norma", ("NBR 8800:2008", "Projeto NBR 8800:2024", "AISC 360-16")),
        ("sec_2", ("Simplificação",)),
        ("sec_3", ("Simplificação", "análise direta")),
        ("sec_4", ("Simplificação", "B₁", "B₂")),
        ("dim_t_tr", ("Simplificação", "cantos vivos")),
    ],
)
def test_dicas_para_quem_nao_conhece_o_termo_explicam_o_termo(chave, deve_citar):
    for trecho in deve_citar:
        assert trecho in AJUDA[chave], (chave, trecho)


def test_espessuras_minimas_da_dica_seguem_a_tabela_da_anglo():
    from core.column_design import ESPESSURA_MIN_ANGLO

    for chave, categoria in (
        ("anglo_chapa", "chapa_ligacao_enrijecedor"),
        ("anglo_cantoneira", "cantoneira"),
        ("anglo_placa", "placa_base"),
    ):
        minimo = f"{ESPESSURA_MIN_ANGLO[categoria]:g}".replace(".", ",")
        assert f"{minimo} mm" in AJUDA[chave], chave


# ------------------------------------------------------------------ “?” em todos os campos na tela
PAGINA = "app_pages/flambagem_colunas.py"
TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "checkbox",
    "radio",
    "text_input",
    "button_group",
    "button",
    "download_button",
    "metric",
    "subheader",
)
# Isentos: o título que já é o convite para abrir o Guia e o campo de nome do botão de registro
# (componente compartilhado, com o rótulo escondido — o botão ao lado tem o “?”).
ISENTOS_DE_AJUDA = {
    ("subheader", "Precisa de ajuda para preencher ou interpretar?"),
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


def _abrir(banco_isolado, **estado) -> AppTest:
    teste = AppTest.from_file("app.py", default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


DIMENSOES_I = {"col_tipo_secao": ui.SEC_I}
MAO_FRANCESA = {"col_mf_incluir": True, "col_mf_eixo": "y"}
GENERICA = {
    "col_tipo_secao": ui.SEC_GENERICA,
    "col_gen_npar": 3,
    "col_par_tipo_1": "AL · grupo 5 — mesa de perfil soldado",
    "col_par_tipo_2": "AA · grupo 2 — alma",
}


@pytest.mark.parametrize(
    "estado",
    [
        pytest.param({}, id="padrao-barra-circular"),
        pytest.param({"col_tipo_secao": ui.SEC_CATALOGO}, id="catalogo"),
        pytest.param({"col_tipo_secao": ui.SEC_RET}, id="retangular-macica"),
        pytest.param({"col_tipo_secao": ui.SEC_TUBO_C}, id="tubo-circular"),
        pytest.param({"col_tipo_secao": ui.SEC_TUBO_R}, id="tubo-retangular"),
        pytest.param(DIMENSOES_I, id="i-por-dimensoes"),
        pytest.param({"col_tipo_secao": ui.SEC_U, "col_soldado_U": True}, id="u-soldado"),
        pytest.param(
            {"col_tipo_secao": ui.SEC_DIRETA, "col_direta_mesmo_raio": False},
            id="area-e-raio-ry-diferente",
        ),
        pytest.param(GENERICA, id="generica-com-paredes"),
        pytest.param(
            {
                "col_norma": "AISC360_16_LRFD",
                "col_modo_carga": ui.MODO_CALCULO,
                "col_mesmo_L": False,
                "col_apoio_x": ui.APOIO_MANUAL,
                "col_apoio_y": ui.APOIO_MANUAL,
                "col_kz_ativar": True,
            },
            id="aisc-n-de-calculo-k-manual-torcao",
        ),
        pytest.param(
            {
                **DIMENSOES_I,
                "col_Mx": 10.0,
                "col_My": 2.0,
                "col_diag_x": ui.DIAG_PONTAS,
                "col_diag_y": ui.DIAG_TRANSVERSAL,
                "col_cb_modo": ui.CB_DIAGRAMA,
                "col_mrd_x_ativar": True,
                "col_mrd_y_ativar": True,
            },
            id="flexao-biaxial-cb-por-diagrama-mrd-informado",
        ),
        pytest.param({**DIMENSOES_I, **MAO_FRANCESA, "col_Mx": 5.0}, id="mao-francesa"),
    ],
)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = _abrir(banco_isolado, **estado)
    faltam = sem_ajuda(t)
    assert not faltam, f"campos sem “?”: {sorted(faltam)}"


def test_comparacao_de_normas_aberta_tambem_tem_interrogacao(banco_isolado):
    t = _abrir(banco_isolado, **DIMENSOES_I)
    t.button(key="col_btn_comparar").click().run()
    assert not sem_ajuda(t)
    assert any(cb.NORMAS_ROTULOS["AISC360_16_LRFD"] in str(d.value) for d in t.dataframe)


def test_colunas_da_tabela_explicam_o_que_mostram(banco_isolado):
    import json

    from components.verification_table import AJUDA_COLUNAS

    t = _abrir(banco_isolado)
    tabela = next(d for d in t.dataframe if "Verificação" in d.value.columns)
    colunas = json.loads(tabela.proto.columns)
    for coluna, texto in AJUDA_COLUNAS.items():
        assert colunas[coluna]["help"] == texto, coluna


def test_planos_de_dicas_aparecem_na_tela(banco_isolado):
    t = _abrir(banco_isolado)
    lx = next(n for n in t.number_input if n.label == "Comprimento total da coluna L (mm)")
    assert "B₁" in lx.help
    secao_3 = next(s for s in t.subheader if s.value.startswith("3. Comprimentos"))
    assert "análise direta" in secao_3.help and "Simplificação" in secao_3.help
    fy = next(n for n in t.number_input if n.label.startswith("Resistência ao escoamento"))
    assert "A36 = 250 MPa" in fy.help


# ------------------------------------------------------------------ sem o aviso de “valor normativo”
FRASES_PROIBIDAS = ("sem valor normativo", "não tem valor normativo", "nao tem valor normativo")


def test_textos_da_flambagem_nao_falam_em_valor_normativo():
    textos = [
        *AJUDA.values(),
        *cb.NORMAS_ROTULOS.values(),
        *cb.REFERENCIAS_NORMA.values(),
        *cb.EXPLICACAO_FLT.values(),
        *cb.FORA_DO_ESCOPO,
        *cb.CONFERIR_NBR8800_2008,
        *cb.REGRAS_B1,
        cb.__doc__ or "",
    ]
    for texto in textos:
        for frase in FRASES_PROIBIDAS:
            assert frase not in texto.lower(), texto
