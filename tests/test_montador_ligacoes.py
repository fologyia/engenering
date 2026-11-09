"""Itens 5 e 11 do Montador: comparar duas montagens e levar os números a outras análises.

O 11 leva o ponto escolhido à Análise estática e ao Círculo de Mohr, e a fadiga à Análise de fadiga,
pelas mesmas chaves que o Assistente de cargas usa. A página que recebeu avisa quando a montagem
muda depois do envio, e traz os números novos se a pessoa quiser.
"""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from components import repasse_do_montador as rpm
from core import montador as mt
from core import montador_modelos as mm
from core import montador_repasse as rp

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SOLIDOS = mm.PARTE_SOLIDOS


def _modelo(nome: str) -> mm.Modelo:
    return next(m for m in mm.MODELOS if m.nome == nome)


def _conta(nome: str) -> tuple[mt.Montagem, mt.Resposta, dict]:
    modelo = _modelo(nome)
    base = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    valores = dict(base.padroes) | dict(modelo.valores)
    for item in base.grandezas:
        if item.chave not in valores and item.padrao is not None:
            valores[item.chave] = item.padrao
    resposta = mt.isolar(base, modelo.alvo, valores)
    usados = dict(resposta.valores_usados) | {resposta.alvo.chave: resposta.valor}
    numeros = {sp.Symbol(k, positive=True): sp.Float(v) for k, v in usados.items()}
    return base, resposta, numeros


def abrir(pagina: str = "app_pages/montador_formulas.py") -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(pagina).run()
    assert not at.exception
    return at


def _escolher_modelo(at: AppTest, nome: str) -> None:
    at.selectbox(key=SOLIDOS.k("modelo")).set_value(nome).run()
    assert not at.exception


def _levar(at: AppTest, botao: str) -> None:
    """Clica em levar sem trocar de página. No AppTest, a troca no meio da rodada deixa elementos
    da página de antes na árvore, e a navegação seguinte tropeça neles; no navegador não."""
    with mock.patch.object(rpm.st, "switch_page", lambda *_a, **_k: None):
        at.button(key=SOLIDOS.k(botao)).click().run()
    assert not at.exception


# ---------------------------------------------------------------------------
# As contas do repasse, sem tela
# ---------------------------------------------------------------------------


def test_pontos_do_eixo_batem_com_a_conta_de_mao():
    base, resposta, numeros = _conta("Eixo com flexão e torção")
    pontos = {x.nome: x for x in rp.pontos(base, numeros, resposta.manda.condicao.no)}
    d = resposta.valor
    m, t = dict(resposta.valores_usados)["M_x"], dict(resposta.valores_usados)["T"]
    fibra = pontos["fibra externa"]
    assert fibra.sigma_x == pytest.approx(32 * m / (math.pi * d**3))
    assert fibra.tau_xy == pytest.approx(16 * t / (math.pi * d**3))
    assert fibra.sigma_y == 0.0
    assert pontos["linha neutra"].sigma_x == 0.0


def test_tubo_sob_pressao_vai_com_as_duas_tensoes():
    base, resposta, numeros = _conta("Tubo sob pressão")
    (fibra, *_) = rp.pontos(base, numeros)
    assert fibra.sigma_y == pytest.approx(2 * fibra.sigma_x)  # circunferencial é o dobro
    assert fibra.von_mises == pytest.approx(math.sqrt(3) / 2 * fibra.sigma_y)


def test_fadiga_leva_as_parcelas_e_o_d_da_secao_redonda():
    base, resposta, numeros = _conta("Eixo: estática e fadiga")
    fadiga = rp.fadiga(base, numeros)
    assert fadiga is not None
    assert fadiga.d == pytest.approx(resposta.valor)
    assert fadiga.sigma_a > fadiga.sigma_m > 0
    base, _, numeros = _conta("Base conhecida: achar a altura")
    assert rp.fadiga(base, numeros) is None  # sem o bloco Fadiga de eixo


def test_conta_com_letra_sem_numero_nao_leva_nada():
    base, resposta, _ = _conta("Eixo com flexão e torção")
    assert rp.pontos(base, {}) == []


def test_aviso_lista_so_o_que_mudou():
    assert rpm.mudancas({"sigma_x": 120.0, "tau_xy": 40.0}, {"sigma_x": 135.0, "tau_xy": 40.0}) == [
        "σx foi de 120 para 135 MPa"
    ]


# ---------------------------------------------------------------------------
# Levar para outras análises, na página
# ---------------------------------------------------------------------------


def test_leva_o_ponto_para_o_circulo_de_mohr_com_a_origem_do_montador():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    assert any(b.label == "Círculo de Mohr" for b in at.button)
    at.button(key=SOLIDOS.k("levar_mohr")).click().run()
    assert not at.exception
    estado = at.session_state["mohr_assistente_2d"]
    assert estado["origem"] == rpm.ORIGEM and estado["descricao"].endswith("fibra externa")
    assert estado["sigma_x"] == pytest.approx(155.29, abs=0.01)
    assert estado["tau_xy"] == pytest.approx(46.59, abs=0.01)
    # Já está no Círculo de Mohr, com o estado do Montador escolhido.
    rotulos = " ".join(o for s in at.selectbox for o in s.options)
    assert "Montador de fórmulas — " in rotulos
    assert not at.warning or not any("mudou depois do envio" in w.value for w in at.warning)


def test_leva_o_ponto_escolhido_para_a_analise_estatica():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    at.selectbox(key=SOLIDOS.k("ponto_levado")).set_value("linha neutra").run()
    at.button(key=SOLIDOS.k("levar_estatica")).click().run()
    assert not at.exception
    assert at.session_state["estatica_sigma_x"] == pytest.approx(0.0)
    assert at.session_state["estatica_tau_xy"] == pytest.approx(46.59, abs=0.01)


def test_fadiga_so_vai_com_o_bloco_de_fadiga_e_leva_o_d():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    assert at.button(key=SOLIDOS.k("levar_fadiga")).disabled
    _escolher_modelo(at, "Eixo: estática e fadiga")
    botao = at.button(key=SOLIDOS.k("levar_fadiga"))
    assert not botao.disabled
    botao.click().run()
    assert not at.exception
    estado = at.session_state
    assert estado["fadiga_sigma_alternada_nominal"] == pytest.approx(83.21, abs=0.01)
    assert estado["fadiga_sigma_media"] == pytest.approx(24.72, abs=0.01)
    assert estado["modo_entalhe"] == "Sem entalhe"  # K_f já está nos números
    assert estado["diametro_norton_flexao"] == pytest.approx(41.48, abs=0.01)


def test_pagina_que_recebeu_avisa_quando_o_montador_muda_e_traz_os_numeros_novos():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    _levar(at, "levar_estatica")
    enviado = at.session_state["estatica_sigma_x"]
    # Ainda no Montador, o momento muda: a conta muda, e o envio fica para trás.
    campo = next(n for n in at.number_input if n.label.startswith("M_x"))
    campo.set_value(campo.value * 2).run()
    at.switch_page("app_pages/analise_estatica.py").run()
    assert not at.exception
    assert any("mudou depois do envio" in w.value for w in at.warning)
    at.button(key="montador_trazer_estatica").click().run()
    assert not at.exception
    assert at.session_state["estatica_sigma_x"] != pytest.approx(enviado)
    assert not any("mudou depois do envio" in w.value for w in at.warning)


def test_manter_os_de_antes_cala_o_aviso_ate_mudar_de_novo():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    _levar(at, "levar_mohr")
    campo = next(n for n in at.number_input if n.label.startswith("T:"))
    campo.set_value(campo.value * 2).run()
    at.switch_page("app_pages/circulo_mohr.py").run()
    assert any("mudou depois do envio" in w.value for w in at.warning)
    at.button(key="montador_manter_mohr").click().run()
    assert not any("mudou depois do envio" in w.value for w in at.warning)


def test_trazer_os_numeros_novos_no_mohr_poe_o_numero_no_proprio_campo():
    """Achado nos cliques: só apagar o campo fazia o navegador seguir mostrando o número velho,
    com a conta já no novo. O número novo tem de ir direto no campo."""
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    _levar(at, "levar_mohr")
    campo = next(n for n in at.number_input if n.label.startswith("M_x"))
    campo.set_value(campo.value * 2).run()
    at.switch_page("app_pages/circulo_mohr.py").run()
    at.button(key="montador_trazer_mohr").click().run()
    assert not at.exception
    novo = at.session_state["mohr_assistente_2d"]["sigma_x"]
    # O d é a resposta: com o dobro do momento ele cresce, e a fibra volta ao limite com outro σx.
    assert novo != pytest.approx(155.29, abs=0.05)
    assert at.session_state["mohr_2d_sigma_x_assistente"] == pytest.approx(novo)
    sigma_x = next(n for n in at.number_input if n.label == "σx (MPa)")
    assert sigma_x.value == pytest.approx(novo)


def test_numeros_mudados_na_pagina_de_destino_nao_recebem_aviso():
    at = abrir()
    _escolher_modelo(at, "Eixo com flexão e torção")
    _levar(at, "levar_estatica")
    at.session_state["estatica_sigma_x"] = 1.0  # a pessoa digitou outro número lá
    campo = next(n for n in at.number_input if n.label.startswith("M_x"))
    campo.set_value(campo.value * 2).run()
    at.switch_page("app_pages/analise_estatica.py").run()
    assert not any("mudou depois do envio" in w.value for w in at.warning)


# ---------------------------------------------------------------------------
# Comparar duas montagens
# ---------------------------------------------------------------------------


def _comparacao(at: AppTest) -> dict[str, dict[str, str]]:
    quadro = next(d.value for d in at.dataframe if "Diferença" in d.value.columns)
    return {linha[""]: dict(linha) for linha in quadro.to_dict("records")}


def test_compara_a_guardada_com_a_de_agora():
    at = abrir()
    at.button(key=SOLIDOS.k("guardar_a")).click().run()
    assert not at.exception
    campo = next(n for n in at.number_input if n.label.startswith("S_y"))
    campo.set_value(350.0).run()
    linhas = _comparacao(at)
    assert linhas["Resposta"]["A"] == "h ≥ 37,95 mm"
    assert linhas["Resposta"]["Agora"] != "h ≥ 37,95 mm"
    assert linhas["Resposta"]["Diferença"].startswith("-")  # mais resistente, seção menor
    assert linhas["S_y"]["A"] == "250 MPa" and linhas["S_y"]["Agora"] == "350 MPa"
    assert linhas["S_y"]["Diferença"] == "+40 %"
    assert "Área da seção" in linhas


def test_voltar_para_a_e_desfazer_com_ctrl_z():
    at = abrir()
    at.button(key=SOLIDOS.k("guardar_a")).click().run()
    next(n for n in at.number_input if n.label.startswith("S_y")).set_value(350.0).run()
    at.button(key=SOLIDOS.k("voltar_a")).click().run()
    assert not at.exception
    assert at.session_state[SOLIDOS.k("valores")]["S_y"] == 250.0
    at.button(key=SOLIDOS.k("esquecer_a")).click().run()
    assert SOLIDOS.k("comparar_a") not in at.session_state
    assert not any("Diferença" in d.value.columns for d in at.dataframe)


def test_comparar_mostra_blocos_que_so_uma_tem():
    at = abrir()
    at.button(key=SOLIDOS.k("guardar_a")).click().run()
    _escolher_modelo(at, "Eixo com flexão e torção")
    linhas = _comparacao(at)
    assert "Blocos só em A" in linhas and "Blocos só na de agora" in linhas
    assert "Retangular" in linhas["Blocos só em A"]["A"]
    assert "Circular maciça" in linhas["Blocos só na de agora"]["Agora"]
