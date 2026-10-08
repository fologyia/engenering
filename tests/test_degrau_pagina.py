"""A página Degrau de escada em grade, exercitada pela interface (AppTest), e os seus “?”.

Três contratos: (1) todo texto de ``components/degrau_help.py`` é usado por algum campo e todo
campo usa um texto que existe; (2) todo campo da página — em cada estado que muda os campos — tem
o seu “?”; (3) a tela mostra o que o núcleo calcula (quadro-resumo, 38 verificações, 64 modelos),
trata entrada impossível com erro claro e o registro leva a tabela inteira para o projeto.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components.degrau_help import AJUDA
from core import degrau_escada as de
from core.project_store import obter_projeto_ativo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/degrau_escada.py"
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "degrau_ui.py",
    RAIZ / "app_pages" / "degrau_escada.py",
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
        ("enquadramento", ("NR-12", "NR-22", "22.10.6")),
        ("espelho_fechado", ("espelho", "item 11", "item 12")),
        ("uso", ("800", "1.100", "3.700")),
        ("n_imposto", ("Vazio", "automático")),
        ("b_imposto", ("630", "640", "múltiplo de 5")),
        ("C_padronizado", ("175", "300", "furação F")),
        ("reducao_largura", ("largura útil", "corrimão")),
        ("altura_max_lance", ("lance", "3.000", "3.600", "limite legal")),
        ("malha", ("30 mm", "25 mm", "35 mm", "41 mm", "GS-A4")),
        ("ligacao", ("100 mm", "50 mm", "L_b")),
        ("modelo_manual", ("DS-A4-35/3",)),
        ("lado_barra", ("só", "peso")),
        ("parafuso", ("5/8", "11/16")),
        ("P", ("6120", "2019")),
        ("b_c", ("Simplificação", "n_ef")),
        ("cb", ("conservador", "FLT")),
        ("gc_sup", ("1.100", "1.200", "1.300")),
        ("res_status", ("OK", "NÃO OK", "ALERTA", "INFO")),
        ("res_catalogo", ("Atende", "Na preferência", "adotado")),
        ("res_conflitos", ("3.1",)),
        ("sec_3", ("ordem de prioridade", "norma legal", "Anglo", "catálogo")),
    ],
)
def test_dicas_para_quem_nao_conhece_o_termo_explicam_o_termo(chave, deve_citar):
    for trecho in deve_citar:
        assert trecho in AJUDA[chave], (chave, trecho)


# ------------------------------------------------------------------ a página na tela
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


def tem_metrica(teste: AppTest, rotulo: str) -> bool:
    return any(m.label == rotulo for m in teste.metric)


def tabela(teste: AppTest, coluna: str) -> pd.DataFrame:
    achadas = [d.value for d in teste.dataframe if coluna in d.value.columns]
    assert achadas, f"nenhuma tabela com a coluna {coluna!r}"
    return achadas[0]


ESTADOS = [
    pytest.param({}, id="padrao"),
    pytest.param({"dg_enquadramento": de.NR22}, id="nr22"),
    pytest.param({"dg_espelho_fechado": True}, id="espelho-fechado"),
    pytest.param({"dg_uso": de.USO_PERMANENTE, "dg_L": 1200.0}, id="permanencia"),
    pytest.param({"dg_selecao": de.SELECAO_MANUAL, "dg_modelo": "DS-F2-40/5"}, id="manual"),
    pytest.param({"dg_malha": de.QUALQUER, "dg_ligacao": de.QUALQUER}, id="qualquer"),
    pytest.param({"dg_material": "AISI 316L", "dg_acabamento": "passivado"}, id="inox"),
    pytest.param({"dg_H": 2000.0}, id="fora-do-catalogo"),
    pytest.param({"dg_n": 21, "dg_b": 280.0, "dg_C": 310.0}, id="impostos"),
    pytest.param({"dg_so_atencao": True}, id="so-atencao"),
    pytest.param({"dg_H": 0.0}, id="entrada-invalida"),
]


@pytest.mark.parametrize("estado", ESTADOS)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    faltam = sem_ajuda(t)
    assert not faltam, f"campos sem “?”: {sorted(faltam)}"


def test_colunas_da_tabela_de_verificacoes_explicam_o_que_mostram(banco_isolado):
    import json

    t = abrir(banco_isolado)
    achada = next(d for d in t.dataframe if "Norma/item" in d.value.columns)
    colunas = json.loads(achada.proto.columns)
    esperado = {
        "Verificação": "col_verificacao",
        "Norma/item": "col_norma",
        "Valor": "col_valor",
        "Limite": "col_limite",
        "Aproveitamento (%)": "col_aproveitamento",
        "Status": "col_status",
        "Observação": "col_observacao",
    }
    for coluna, chave in esperado.items():
        assert colunas[coluna]["help"] == AJUDA[chave], coluna


# ------------------------------------------------------------------ o que a tela mostra
def test_quadro_resumo_do_caso_1_bate_com_o_nucleo(banco_isolado):
    esperado = de.calcular_escada(de.EntradaDegrau())
    t = abrir(banco_isolado)
    assert metrica(t, "Modelo adotado") == "DS-A4-35/3"
    assert metrica(t, "Espelho h × piso b (mm)") == "180 × 270"
    assert metrica(t, "Profundidade C × L (mm)") == "300 × 800"
    assert metrica(t, "Espelhos / degraus em grade") == "20 / 18"
    assert metrica(t, "Aproveitamento máximo") == f"{100 * esperado.aproveitamento_maximo:.0f} %"
    assert metrica(t, "Situação da geometria") == "Nível 1 de 4"
    assert metrica(t, "Status geral") == "ALERTA"
    legendas = " ".join(c.value for c in t.caption)
    assert "35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A" in legendas
    assert "2h + b = 630 mm" in legendas and "F = 135 mm" in legendas
    assert "2 lance(s) de 10 espelhos" in legendas


def test_tabela_das_38_verificacoes_traz_as_colunas_e_os_status_do_caso_1(banco_isolado):
    t = abrir(banco_isolado)
    verificacoes = tabela(t, "Norma/item")
    assert len(verificacoes) == 38
    assert list(verificacoes.columns) == [
        "Verificação",
        "Norma/item",
        "Valor",
        "Limite",
        "Aproveitamento (%)",
        "Status",
        "Observação",
    ]
    status = verificacoes["Status"].tolist()
    assert status.count("ALERTA") == 2 and status.count("INFO") == 1
    assert (
        verificacoes.loc[30, "Status"] == "ALERTA" and "Furo" in verificacoes.loc[30, "Verificação"]
    )
    assert (verificacoes["Norma/item"].str.len() > 0).all()


def test_so_atencao_filtra_a_tabela(banco_isolado):
    t = abrir(banco_isolado, dg_so_atencao=True)
    verificacoes = tabela(t, "Norma/item")
    assert set(verificacoes["Status"]) == {"ALERTA"} and len(verificacoes) == 2


def test_tabela_dos_64_modelos_destaca_o_adotado(banco_isolado):
    t = abrir(banco_isolado)
    modelos = tabela(t, "Na preferência")
    assert len(modelos) == 64
    adotado = modelos[modelos["Adotado"] == "ADOTADO"]
    assert adotado["Modelo"].tolist() == ["DS-A4-35/3"]
    assert modelos.loc[modelos["Modelo"] == "DS-A4-30/3", "Atende"].iloc[0] == "NÃO"


def test_texto_da_requisicao_e_o_do_nucleo(banco_isolado):
    t = abrir(banco_isolado)
    codigos = [c.value for c in t.get("code")]
    assert de.calcular_escada(de.EntradaDegrau()).especificacao in codigos


def test_memorial_mostra_a_flt_do_modelo_adotado(banco_isolado):
    t = abrir(banco_isolado)
    memoriais = [d.value for d in t.dataframe if "Cálculo" in d.value.columns]
    assert len(memoriais) == 2  # a geometria da escada e o memorial do modelo
    grandezas = {g for tabela_ in memoriais for g in tabela_["Grandeza"]}
    assert {"Esbeltez λ", "Esbeltez limite λp", "Esbeltez limite λr", "M_Rd por barra"} <= grandezas
    assert {"Espelho h", "Piso b", "Furação F da chapa lateral"} <= grandezas
    assert any("Memorial do modelo adotado" in s.proto.body for s in t.get("subheader"))


def test_trocar_enquadramento_para_nr22_muda_os_lances_e_os_nao_se_aplica(banco_isolado):
    t = abrir(banco_isolado, dg_enquadramento=de.NR22)
    assert metrica(t, "Espelhos / degraus em grade") == "20 / 19"
    verificacoes = tabela(t, "Norma/item")
    assert (verificacoes["Status"] == "N/A").sum() == 4


def test_seleção_manual_reprova_o_modelo_que_nao_atende(banco_isolado):
    t = abrir(banco_isolado, dg_selecao=de.SELECAO_MANUAL, dg_modelo="DS-A4-25/3", dg_L=700.0)
    assert metrica(t, "Modelo adotado") == "DS-A4-25/3"
    assert metrica(t, "Status geral") == "NÃO OK"


def test_avisos_fixos_e_conflitos_aparecem_sempre(banco_isolado):
    t = abrir(banco_isolado)
    avisos = " ".join(w.value for w in t.warning)
    assert "O que esta página não faz" in avisos and "Longarina" in avisos
    assert "NR-22 (espelho de 180 a 200 mm)" in avisos  # conflitos entre normas
    assert "Conferir antes de emitir" in avisos and "carga-base" in avisos
    assert "inoxidável" in avisos  # os avisos são fixos: o do inox vale para qualquer material
    inox = abrir(banco_isolado, dg_material="AISI 304", dg_acabamento="passivado")
    assert "inoxidável" in " ".join(w.value for w in inox.warning)


def test_desnivel_zero_vira_erro_claro_e_nao_calcula(banco_isolado):
    t = abrir(banco_isolado, dg_H=0.0)
    assert any("desnível total H" in e.value for e in t.error)
    assert not tem_metrica(t, "Modelo adotado")


def test_altura_por_lance_menor_que_um_espelho_vira_erro_claro(banco_isolado):
    t = abrir(banco_isolado, dg_altura_lance=100.0)
    assert any("menor que um espelho" in e.value for e in t.error)


def test_piso_imposto_nao_e_corrigido_em_silencio(banco_isolado):
    t = abrir(banco_isolado, dg_b=100.0)  # 2h + b = 460 mm: fora do Blondel e da NR-12
    verificacoes = tabela(t, "Norma/item")
    nao_ok = verificacoes[verificacoes["Status"] == "NÃO OK"]["Verificação"].tolist()
    assert any("Blondel" in v for v in nao_ok)
    assert metrica(t, "Espelho h × piso b (mm)") == "180 × 100"


def test_baixar_tem_tres_arquivos_com_ajuda(banco_isolado):
    t = abrir(banco_isolado)
    botoes = list(t.get("download_button"))
    rotulos = {b.proto.label for b in botoes}
    assert rotulos == {"Verificações em CSV", "Os 64 modelos em CSV", "Relatório em PDF"}
    assert all(b.proto.help for b in botoes)


# ------------------------------------------------------------------ registro no projeto
def test_registrar_grava_o_calculo_com_as_38_verificacoes_e_as_tabelas(banco_com_projeto):
    t = abrir(banco_com_projeto)
    t.button(key="registrar_degrau_escada").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == "degrau_escada"
    ]
    assert len(registros) == 1
    registro = registros[0]
    assert registro["entradas"]["desnivel_H_mm"] == 3600.0
    assert registro["resultados"]["status_geral"] == "ALERTA"
    assert len(registro["resultados"]["verificações"]) == 38
    assert len(registro["resultados"]["tabelas_memorial"]) == 4
    assert registro["resultados"]["modelo_adotado"] == "DS-A4-35/3"
    assert registro["status"] == "Atenção"
    assert "DS-A4-35/3" in registro["titulo"]


def test_identificacao_vai_para_o_registro(banco_com_projeto):
    t = abrir(banco_com_projeto, dg_obra="Obra X", dg_tag="ESC-01", dg_responsavel="Eng. Y")
    t.button(key="registrar_degrau_escada").click().run()
    registro = next(
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == "degrau_escada"
    )
    assert registro["entradas"]["obra"] == "Obra X" and registro["entradas"]["tag"] == "ESC-01"
    assert registro["responsavel"] == "Eng. Y"
    assert "ESC-01" in registro["titulo"]


# ------------------------------------------------------------------ o guia
def test_guia_tem_o_capitulo_do_degrau_com_exemplo_calculado_pelo_nucleo(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Degrau de escada em grade"
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    assert any(h.value == "Degrau de escada em grade" for h in t.header)
    exemplo = de.calcular_escada(de.EntradaDegrau())
    textos = " ".join(m.value for m in t.markdown) + " ".join(c.value for c in t.caption)
    assert f"{exemplo.geometria.n} espelhos de 180 mm e piso de 270 mm" in textos
    assert exemplo.adotado.modelo.nome in textos
    assert "35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A" in textos
