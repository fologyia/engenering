"""Cargas do esqueleto → Plano de cargas: o envio se confirma e o plano não perde nada.

Queixa de 17/11/2026 ("não está gravando no plano"): o envio gravava, mas a página recarregava
sem aviso, a troca de nomes não se explicava, T± apagadas voltavam, o plano avisava "duas vezes"
em piso + guarda-corpo e o "Editar" do plano apagava o trecho das cargas.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from core import piso_do_modelo as pm
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_cargas_esqueleto_pagina import _com_o_piso_6x3

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
ESQUELETO = "app_pages/cargas_esqueleto.py"
PLANO = "app_pages/plano_cargas.py"

PISO = "Piso do modelo: 3,00 kN de C1; uniforme na viga de 6,00 m"
GC = "Guarda-corpo nas bordas: 0,360 kN/m × 6,00 m (B1) = 2,160 kN, uniforme"


def abrir(pagina: str) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(pagina)
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


# ------------------------------------------------------------------ núcleo
def test_piso_e_guarda_corpo_na_mesma_viga_nao_e_repeticao():
    def plano(*obs: str, inicio: tuple[float, ...] = (0.0, 0.0)) -> pc.PlanoDeCargas:
        return pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao(
                "PE",
                cargas=[
                    pc.CargaDoModelo("V1", 0.5, "kN/m", "Z (vertical)", o, 1, 6.0, i)
                    for o, i in zip(obs, inicio, strict=True)
                ],
            ),
        )

    def repete(p: pc.PlanoDeCargas) -> bool:
        return any("duas vezes" in i.texto for i in pc.conferir_plano(p))

    assert not repete(plano(PISO, GC))  # origens diferentes
    assert not repete(plano(PISO, PISO, inicio=(0.0, 2.0)))  # trechos diferentes
    assert repete(plano(PISO, PISO))  # a mesma linha duas vezes continua suspeita
    assert repete(plano("", ""))


def test_comparar_explica_a_troca_do_nome_do_corpo_pelo_da_barra():
    def com(nome: str) -> pc.PlanoDeCargas:
        return pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao(
                "SC", cargas=[pc.CargaDoModelo(nome, 1.0, "kN/m", "Z (vertical)", PISO, 1, 6.0)]
            ),
        )

    # As Cargas do esqueleto escrevem "corpo (barra)"; outra página pode escrever só a barra.
    for novo in ("Corpo[1] (Viga-1)", "Viga-1"):
        linhas = pm.comparar(com("Corpo[1]"), com(novo), {"Corpo[1]": "Viga-1"})
        assert len(linhas) == 1
        assert "1 viga(s) ganham o nome da barra no Simulation" in linhas[0]["O que muda"]
        assert "Corpo[1] → Viga-1" in linhas[0]["O que muda"]
    # Sem o mapa (ou com nomes iguais), nada de troca de nome.
    assert "nome da barra" not in pm.comparar(com("A"), com("B"))[0]["O que muda"]


def test_resumo_do_envio():
    assert "nada mudou" in pm.resumo_do_envio([])
    texto = pm.resumo_do_envio(
        [
            {"Caso": "PE", "Antes (kN)": 0.0, "Depois (kN)": 18.294, "Linhas": "0 → 42"},
            {"Caso": "T+", "Antes (kN)": None, "Depois (kN)": 0.0, "Linhas": "0 → 1"},
            {"Caso": "W0", "Antes (kN)": 3.0, "Depois (kN)": None, "Linhas": "4 → 0"},
        ]
    )
    assert texto.startswith("Enviado ao plano de cargas")
    assert "PE: 42 linha(s), 18,29 kN" in texto
    assert "T+: 1 linha(s)" in texto and "W0 saiu do plano" in texto


def test_campos_sem_a_temperatura():
    projeto = {pm.CHAVE_DO_PROJETO: {"temperatura": True, "peso": "x"}}
    assert pm.campos_sem_a_temperatura(projeto, pm.ORIGEM) == {
        pm.CHAVE_DO_PROJETO: {"temperatura": False, "peso": "x"}
    }
    assert pm.campos_sem_a_temperatura({}, "Cargas do esqueleto") == {
        "cargas_do_esqueleto": {"temperatura": False}
    }
    assert pm.campos_sem_a_temperatura(projeto, "Informada") == {}


# ------------------------------------------------------------------ páginas
def test_envio_confirma_na_tela_e_aponta_o_plano(banco_com_projeto):
    _com_o_piso_6x3(
        pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")]),
        )
    )
    t = abrir(ESQUELETO)
    assert not t.success
    t.button(key="ce_enviar_tudo").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    avisos = [s.value for s in t.success]
    assert any(a.startswith("Enviado ao plano de cargas") and "SC: 3 linha(s)" in a for a in avisos)
    assert "Abrir o Plano de cargas" in [str(p.proto.label) for p in t.get("page_link")]
    # A confirmação é de uma vez: a próxima execução não a repete.
    t.run()
    assert not any("Enviado ao plano" in s.value for s in t.success)

    t.button(key="ce_gravar_escolhas").click().run()
    assert any("Escolhas gravadas" in s.value for s in t.success)


def test_remover_temperatura_no_plano_desliga_a_do_esqueleto(banco_com_projeto):
    _com_o_piso_6x3(pc.PlanoDeCargas(), **{pm.CHAVE_DO_PROJETO: {"temperatura": True}})
    t = abrir(ESQUELETO)
    t.button(key="ce_enviar_tudo").click().run()
    assert {"T+", "T−"} <= set(pc.plano_do_projeto(obter_projeto_ativo()).codigos)

    t = abrir(PLANO)
    t.button(key="pc_remover_T+").click().run()
    assert not t.exception
    assert any("foi desligada" in i.value for i in t.info)
    projeto = obter_projeto_ativo()
    assert projeto[pm.CHAVE_DO_PROJETO]["temperatura"] is False

    # O envio seguinte não devolve T+ (e tira a T− que veio de lá).
    t = abrir(ESQUELETO)
    t.button(key="ce_enviar_tudo").click().run()
    codigos = pc.plano_do_projeto(obter_projeto_ativo()).codigos
    assert "T+" not in codigos and "T−" not in codigos


def test_editar_no_plano_mantem_o_trecho(banco_com_projeto):
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(
        pc.com_acao(
            pc.PlanoDeCargas(),
            pc.nova_acao(
                "PE",
                cargas=[pc.CargaDoModelo("V1", 0.5, "kN/m", "Z (vertical)", PISO, 1, 2.5, 1.5)],
            ),
        )
    )
    salvar_projeto(projeto, motivo="teste")
    t = abrir(PLANO)
    tabela = next(d.value for d in t.dataframe if "Início (m)" in d.value.columns)
    assert tabela["Comprimento (m)"][0] == 2.5 and tabela["Início (m)"][0] == 1.5
    assert tabela["Total (kN)"][0] == 1.25
    t.button(key="pc_editar_PE").click().run()
    next(b for b in t.button if b.label == "Gravar a ação").click()
    t.run()
    assert not t.exception and not t.error
    carga = pc.plano_do_projeto(obter_projeto_ativo()).acao("PE").cargas[0]
    assert (carga.comprimento_m, carga.inicio_m) == (2.5, 1.5)
