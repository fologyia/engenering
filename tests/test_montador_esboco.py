"""A seção desenhada no esboço com letras, dentro do Montador de fórmulas.

O exemplo é o pedido do usuário: uma chapa com furos, e o maior furo que a seção aguenta. A letra do
esboço vira a incógnita; o Montador acha a raiz pela resistência ou para onde a forma acaba.
"""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from core import elementos_vigas as ev
from core import esboco as eb
from core import esboco_secao as es
from core import montador as mt
from core import montador_blocos as mb
from core import montador_busca as busca
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from tests.test_esboco import chapa_com_furos

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SY = {"S_y": 250.0, "n": 1.0}


@pytest.fixture
def catalogo_vazio(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield
        ev._analisar_desenho.cache_clear()


def _salvar(nome: str, dados: dict) -> None:
    modelo = es.Modelo(eb.esboco_de_dicionario(dados))
    partes = modelo.regioes.partes(modelo.sistema.q0[None, :])
    catalogo.salvar_perfil(
        sd.perfil_da_secao(nome, sd.analisar(partes)),
        desenho=tuple(p.como_dicionario() for p in partes),
        esboco=dados,
    )


def _montar(nome: str, *tipos: str) -> mt.Montagem:
    tipos = ("desenhada", *tipos, mb.RESULTADO)
    nos = [
        {"id": f"n{i}", "tipo": t, "opcoes": {"desenho": nome} if t == "desenhada" else {}}
        for i, t in enumerate(tipos)
    ]
    fios = [
        {
            "de": a["id"],
            "saida": mb.POR_CHAVE[a["tipo"]].saidas[0].chave,
            "para": b["id"],
            "entrada": mb.POR_CHAVE[b["tipo"]].entradas[0].chave,
        }
        for a, b in zip(nos, nos[1:], strict=False)
    ]
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


def test_a_letra_do_esboco_vira_a_incognita(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    m = _montar("Chapa furada", "flexao", "von_mises")
    assert not m.erros
    letra = m.grandeza("d")
    assert letra is not None and letra.padrao == pytest.approx(10.0)


def test_maior_furo_pela_resistencia_bate_com_a_conta_de_mao(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    r = mt.isolar(_montar("Chapa furada", "flexao", "von_mises"), "d", {"M_x": 1.5e6, **SY})
    # σ = M·c/I com c = 10: I precisa dar 1,5e6·10/250 = 60 000 mm⁴.
    exato = ((100 * 20**3 / 12 - 60000.0) * 64 / (2 * math.pi)) ** 0.25
    assert r.valor == pytest.approx(exato, rel=1e-6)
    assert r.sentido == mt.MAXIMO
    assert not any("pela forma" in a for a in r.alertas)


def test_maior_furo_pela_forma_quando_a_resistencia_sobra(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    r = mt.isolar(_montar("Chapa furada", "flexao", "von_mises"), "d", {"M_x": 1.0e6, **SY})
    assert r.valor == pytest.approx(20.0, abs=1e-3)
    assert r.manda is not None and r.manda.pela_forma
    assert any("pela forma do desenho" in a and "encostam" in a for a in r.alertas)


def test_com_cortante_a_linha_neutra_entra_na_conta(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    m = _montar("Chapa furada", "flexao", "cortante", "von_mises")
    assert any("linha neutra" in c.ponto for c in m.condicoes)
    r = mt.isolar(m, "d", {"M_x": 1.0e5, "V_y": 2.0e5, **SY})
    assert r.valor is not None and 0.0 < r.valor < 20.0


def test_busca_com_duas_letras_acha_a_menor_area(catalogo_vazio):
    _salvar("Chapa dh", chapa_com_furos(letra_h=True))
    m = _montar("Chapa dh", "flexao", "von_mises")
    faixas = [busca.Faixa("d", 2.0, 18.0, 0.5), busca.Faixa("h", 12.0, 40.0, 1.0)]
    objetivo = next(o for o in busca.objetivos(m, ["d", "h"]) if o.tipo == busca.MENOR_AREA)
    b = busca.procurar(m, faixas, objetivo, {"M_x": 1.5e6, **SY})
    assert b.convergido is not None
    d, h = b.convergido.valor("d"), b.convergido.valor("h")
    assert d == pytest.approx(18.0)
    # Com d = 18, a altura que dá σ = 250: 100·h³/12 − 2·π·18⁴/64 = 1,5e6·(h/2)/250.
    furos = 2 * math.pi * 18**4 / 64
    assert 100 * h**3 / 12 - furos == pytest.approx(1.5e6 * (h / 2) / 250, rel=1e-4)


def test_busca_grande_demais_para_a_secao_desenhada(catalogo_vazio):
    _salvar("Chapa dh", chapa_com_furos(letra_h=True))
    m = _montar("Chapa dh", "flexao", "von_mises")
    faixas = [busca.Faixa("d", 1.0, 18.0, 0.01), busca.Faixa("h", 12.0, 40.0, 0.1)]
    objetivo = busca.objetivos(m, ["d", "h"])[0]
    with pytest.raises(busca.ErroDeBusca, match="refaz o esboço"):
        busca.procurar(m, faixas, objetivo, {"M_x": 1.5e6, **SY})


def test_esboco_sem_letras_continua_com_a_escala(catalogo_vazio):
    dados = chapa_com_furos()
    for cota in dados["cotas"]:
        if cota["expressao"] == "d":
            cota["expressao"] = "10"
    dados["variaveis"] = []
    _salvar("Chapa fixa", dados)
    m = _montar("Chapa fixa", "flexao", "von_mises")
    assert m.grandeza("s") is not None and m.grandeza("d") is None


def _pagina() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/desenhar_secao.py")
    return at.run()


def test_pagina_abre_no_esboco_vazio(catalogo_vazio):
    at = _pagina()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["secao_modo"] == "Esboço com cotas"
    assert any("contorno fechado" in i.value for i in at.info)


def test_pagina_abre_o_esboco_salvo_e_testa_a_letra(catalogo_vazio):
    _salvar("Chapa furada", chapa_com_furos())
    at = _pagina()
    at.selectbox(key="secao_abrir").set_value("Chapa furada").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["secao_esboco_partes"]
    textos = " ".join(m.value for m in at.markdown)
    assert "Testar o desenho" in textos
    assert "de quase zero, até 20 mm" in textos
    assert any("Parede mais fina agora" in c.value for c in at.caption)


def test_do_montador_ao_esboco_e_de_volta_com_a_letra(catalogo_vazio):
    """O caminho do pedido: o bloco Seção desenhada abre o esboço, e a letra volta como incógnita."""
    import copy

    from components import desenhar_secao_ui as ui
    from components import volta_da_secao as vs
    from core import montador_modelos as mm

    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    grafo = copy.deepcopy(mm.POR_NOME["Força máxima num braço"].grafo())
    no = next(n for n in grafo["nos"] if n["tipo"] == "retangular")
    no["tipo"], no["opcoes"] = "desenhada", {}
    at.session_state["mf_grafo"] = grafo
    at.session_state["mf_alvo"] = None
    at.run()
    at.button(key=f"mf_desenhar_{no['id']}").click().run()
    at.switch_page(vs.PAGINA_DESENHAR)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # O que a prancheta mandaria ao fim do desenho: o esboço da chapa com o furo em d.
    modelo = es.Modelo(eb.esboco_de_dicionario(chapa_com_furos()))
    at.session_state[ui.ESBOCO] = chapa_com_furos()
    at.session_state[ui.PARTES_ESBOCO] = [
        p.como_dicionario() for p in modelo.regioes.partes(modelo.sistema.q0[None, :])
    ]
    at.run()
    at.text_input(key="secao_nome").set_value("Chapa do braço").run()
    at.button(key="secao_salvar_e_voltar").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert catalogo.obter("Chapa do braço").esboco == chapa_com_furos()
    bloco = next(n for n in at.session_state["mf_grafo"]["nos"] if n["id"] == no["id"])
    assert bloco["opcoes"]["desenho"] == "Chapa do braço"
    montagem = mt.montar(mt.grafo_de_dados(at.session_state["mf_grafo"]))
    assert montagem.grandeza("d") is not None


def test_letra_do_esboco_com_nome_do_montador_ganha_sobrenome(catalogo_vazio):
    """Um n no esboço não pode virar o fator de segurança: vira n_sec, com aviso."""
    dados = chapa_com_furos()
    for cota in dados["cotas"]:
        if cota["expressao"] == "d":
            cota["expressao"] = "n"
    dados["variaveis"] = [{"nome": "n", "valor": 10.0}]
    _salvar("Chapa n", dados)
    m = _montar("Chapa n", "flexao", "von_mises")
    assert m.grandeza("n_sec") is not None and m.grandeza("n_sec").texto == "n (desenho)"
    assert m.grandeza("n").dimensao != m.grandeza("n_sec").dimensao
    r = mt.isolar(m, "n_sec", {"M_x": 1.5e6, "S_y": 250.0, "n": 1.0})
    exato = ((100 * 20**3 / 12 - 60000.0) * 64 / (2 * math.pi)) ** 0.25
    assert r.valor == pytest.approx(exato, rel=1e-6)
