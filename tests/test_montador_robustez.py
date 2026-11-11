"""Montador: o que vem estragado não derruba a prancheta, e a resposta fica à vista."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest import mock

import pytest

from core import diagnostico as dg
from core import montador as mt
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_registro as rg
from tests.test_montador_pacotes import BASE, RET, _dados, _resposta, _tela, abrir

PAGINA = "app_pages/montador_formulas.py"


# ---------------------------------------------------------------------------
# Escolha que o bloco não conhece
# ---------------------------------------------------------------------------


def _com_opcao_estranha(valor: str) -> dict:
    dados = _dados(*RET)
    for no in dados["nos"]:
        bloco = mb.POR_CHAVE[no["tipo"]]
        no["opcoes"] = {opcao.chave: valor for opcao in bloco.opcoes}
    return dados


def test_escolha_desconhecida_vale_o_padrao_do_bloco():
    """Arquivo de outra versão, ou mexido à mão: o inspetor já mostrava o padrão; a conta também."""
    certa = mt.isolar(mt.montar(mt.grafo_de_dados(_dados(*RET))), "h", BASE)
    estranha = mt.montar(mt.grafo_de_dados(_com_opcao_estranha("???")))
    assert not estranha.erros
    assert mt.isolar(estranha, "h", BASE).valor == pytest.approx(certa.valor)


def test_escolha_desconhecida_nao_quebra_nenhum_bloco():
    for bloco in mb.BLOCOS:
        if not bloco.opcoes:
            continue
        dados = {
            "nos": [
                {
                    "id": "a",
                    "tipo": bloco.chave,
                    "opcoes": {opcao.chave: "não existe" for opcao in bloco.opcoes},
                }
            ],
            "fios": [],
        }
        grafo = mt.grafo_de_dados(dados)
        assert dict(grafo.nos[0].opcoes) == {}, bloco.chave
        mt.montar(grafo)  # pode faltar ligação (ValueError vira erro do bloco), mas não quebra


def test_opcoes_que_nao_sao_um_dicionario_ficam_de_fora():
    dados = _dados(*RET)
    dados["nos"][0]["opcoes"] = ["lixo"]
    assert not mt.montar(mt.grafo_de_dados(dados)).erros


# ---------------------------------------------------------------------------
# Bloco que quebra
# ---------------------------------------------------------------------------


def _quebrar(*_: object) -> dict:
    raise RuntimeError("defeito de dentro do bloco")


def test_bloco_que_quebra_vira_erro_do_bloco_e_os_outros_seguem(monkeypatch):
    monkeypatch.setenv(dg.VARIAVEL_MODO, "")
    dados = _dados(*RET)
    dados["nos"][0]["id"] = "unico_deste_teste"
    dados["fios"][0]["de"] = "unico_deste_teste"
    quebrado = replace(mb.POR_CHAVE["cortante"], calcular=_quebrar)
    with mock.patch.dict(mb.POR_CHAVE, {"cortante": quebrado}):
        montagem = mt.montar(mt.grafo_de_dados(dados))
    mt.montar.cache_clear()
    erros = dict(montagem.erros)
    assert "não conseguiu fazer a conta" in erros["n2"]
    assert "ref." in erros["n2"]
    assert "unico_deste_teste" in montagem.saidas  # a seção antes dele foi calculada


def test_bloco_que_quebra_sobe_no_modo_dos_testes():
    dados = _dados(*RET)
    dados["nos"][0]["id"] = "outro_unico"
    dados["fios"][0]["de"] = "outro_unico"
    quebrado = replace(mb.POR_CHAVE["cortante"], calcular=_quebrar)
    with mock.patch.dict(mb.POR_CHAVE, {"cortante": quebrado}), pytest.raises(RuntimeError):
        mt.montar(mt.grafo_de_dados(dados))


# ---------------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adotado", [float("nan"), float("inf"), True, -40.0, 0.0, "40"])
def test_valor_adotado_ruim_no_arquivo_fica_de_fora(adotado):
    _, _, doc = _resposta()
    bruto = json.loads(rg.em_json(doc))
    bruto["adotado"] = adotado
    lido = rg.ler_documento(json.dumps(bruto), mb.SOLIDOS, g.SISTEMA_SOLIDOS)
    assert lido["adotado"] is None


def test_valor_adotado_bom_no_arquivo_continua():
    _, _, doc = _resposta()
    bruto = json.loads(rg.em_json(doc))
    bruto["adotado"] = 40.0
    assert rg.ler_documento(json.dumps(bruto), mb.SOLIDOS, g.SISTEMA_SOLIDOS)["adotado"] == 40.0


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def test_resposta_fica_no_topo_do_inspetor():
    at = abrir(PAGINA)
    texto = _tela(at)
    assert "mi-resposta" in texto
    assert "h ≥ 37,95 mm" in texto
    assert "Quem manda: von Mises na fibra externa." in texto


def test_resposta_do_inspetor_diz_o_que_falta():
    at = abrir(PAGINA)
    valores = dict(at.session_state["mf_valores"])
    valores["b"] = None
    at.session_state["mf_valores"] = valores
    at.run()
    assert not at.exception
    texto = _tela(at)
    assert "h em letras" in texto
    assert "Para sair o número, preencha b." in texto


def test_resposta_do_inspetor_com_valor_adotado():
    at = abrir(PAGINA)
    at.session_state["mf_adotado"] = 30.0
    at.run()
    assert "Com h = 30 mm: não passa" in _tela(at)
    at.session_state["mf_adotado"] = 45.0
    at.run()
    assert "Com h = 45 mm: passa" in _tela(at)


def test_como_usar_esta_na_pagina():
    at = abrir(PAGINA)
    assert any("Ctrl+Z" in m.value for m in at.markdown)


def test_quadro_das_condicoes_em_portugues():
    at = abrir(PAGINA)
    quadro = next(d.value for d in at.dataframe if "Atua" in d.value.columns)
    assert list(quadro["Atua"]) == ["166,7", "13,69"]
    assert list(quadro["Limite"]) == ["166,7", "166,7"]


def test_parte_que_falha_nao_leva_o_resto_da_pagina(monkeypatch):
    monkeypatch.setenv(dg.VARIAVEL_MODO, "")
    with mock.patch("components.montador_ui._comparar", side_effect=RuntimeError("defeito")):
        at = abrir(PAGINA)
    assert not at.exception
    assert any("“Comparar duas montagens” não pôde ser mostrada" in c.value for c in at.caption)
    # O que vem antes e o que vem depois continuam na tela.
    assert any(s.value.startswith("**h ≥") for s in at.success)
    assert "Levar para outras análises" in _tela(at)
    assert any(b.key == "mf_baixar" for b in at.get("download_button"))


def test_conta_que_quebra_vira_aviso_e_a_prancheta_fica(monkeypatch):
    monkeypatch.setenv(dg.VARIAVEL_MODO, "")
    with mock.patch("core.montador.isolar", side_effect=ZeroDivisionError("defeito")):
        at = abrir(PAGINA)
    assert not at.exception
    assert any("não conseguiu fechar esta conta" in e.value for e in at.error)
    assert "Sem resposta" in _tela(at)
