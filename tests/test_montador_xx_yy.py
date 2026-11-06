"""Montador de fórmulas: momento em XX e YY, e momento por força vezes distância."""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from core import elementos_vigas as ev
from core import montador as mt
from core import montador_blocos as mb
from core import montador_modelos as mm
from core import secao_desenhada as sd
from core import section_catalog as catalogo

APP = str(Path(__file__).resolve().parents[1] / "app.py")
BRACO = {"entrada": mb.FORCA_BRACO}
BRACO_V = {"entrada": mb.FORCA_COM_CORTANTE}
SY_N = {"S_y": 240.0, "n": 1.0}


def montar(*itens) -> mt.Montagem:
    """Cada item é o tipo do bloco, ou (tipo, opções)."""
    nos = []
    for i, item in enumerate(itens):
        tipo, opcoes = item if isinstance(item, tuple) else (item, {})
        nos.append({"id": f"n{i}", "tipo": tipo, "opcoes": opcoes})
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(
            {"de": a["id"], "saida": saida.chave, "para": b["id"], "entrada": entrada.chave}
        )
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


def letras(m: mt.Montagem) -> set[str]:
    return {item.chave for item in m.grandezas}


def isolada(r: mt.Resposta, ponto: str) -> mt.Isolada:
    return next(i for i in r.isoladas if ponto in i.condicao.ponto)


# ---------------------------------------------------------------------------
# Momento em XX e YY
# ---------------------------------------------------------------------------


def test_retangular_em_yy_troca_a_base_pela_altura():
    m = montar("retangular", "flexao_y", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "M_y", {"b": 40.0, "h": 90.0, **SY_N})
    assert r.valor == pytest.approx(240 * 90 * 40**2 / 6)
    assert "fibra externa em YY" in r.manda.condicao.nome


def test_canto_soma_os_dois_momentos():
    m = montar("retangular", "flexao", "flexao_y", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "M_y", {"b": 50.0, "h": 100.0, "M_x": 5e6, **SY_N})
    assert "canto" in r.manda.condicao.nome
    wx, wy = 50 * 100**2 / 6, 100 * 50**2 / 6
    assert r.valor == pytest.approx((240 - 5e6 / wx) * wy)


def test_sem_o_segundo_momento_nao_aparece_canto():
    m = montar("retangular", "flexao", "von_mises", mb.RESULTADO)
    assert not any("canto" in c.ponto for c in m.condicoes)


def test_altura_com_os_dois_momentos_fecha():
    m = montar("retangular", "flexao", "flexao_y", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "h", {"b": 50.0, "M_x": 5e6, "M_y": 1e6, **SY_N})
    h = r.valor
    assert 6 * 5e6 / (50 * h**2) + 6 * 1e6 / (h * 50**2) == pytest.approx(240.0)


def test_seccao_redonda_compoe_os_momentos():
    m = montar("circular", "flexao", "flexao_y", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {})
    x, y, s, n = [sp.Symbol(k, positive=True) for k in ("M_x", "M_y", "S_y", "n")]
    esperado = (32 * n * sp.sqrt(x**2 + y**2) / (sp.pi * s)) ** sp.Rational(1, 3)
    trocas = {x: 3.0, y: 4.0, s: 7.0, n: 2.0}
    forma = isolada(r, "fibra").formula.expressao
    assert float(forma.subs(trocas)) == pytest.approx(float(esperado.subs(trocas)))


def test_eixo_com_os_dois_momentos_e_torque():
    m = montar("circular", "flexao", "flexao_y", "torcao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"M_x": 3e5, "M_y": 4e5, "T": 2e5, "S_y": 350.0, "n": 2.0})
    # M_r = 5e5: fórmula clássica com a resultante.
    esperado = (16 * 2 / (math.pi * 350) * math.sqrt(4 * 25e10 + 3 * 4e10)) ** (1 / 3)
    assert r.valor == pytest.approx(esperado)


def test_perfil_i_tem_a_ponta_da_mesa_em_yy():
    m = montar("perfil_i", "flexao", "flexao_y", "von_mises", mb.RESULTADO)
    r = mt.isolar(
        m,
        "S_y",
        {"b_f": 100.0, "h": 200.0, "t_f": 10.0, "t_w": 6.0, "M_x": 2e7, "M_y": 1e6, "n": 1.0},
    )
    assert "ponta da mesa" in r.manda.condicao.nome
    ix = (100 * 200**3 - 94 * 180**3) / 12
    iy = (2 * 10 * 100**3 + 180 * 6**3) / 12
    assert r.valor == pytest.approx(2e7 * 100 / ix + 1e6 * 50 / iy)


def test_kt_multiplica_os_dois_momentos():
    m = montar("retangular", "flexao", "flexao_y", "concentracao", "von_mises", mb.RESULTADO)
    r = mt.isolar(
        m,
        "S_y",
        {"b": 50.0, "h": 100.0, "M_x": 1e6, "M_y": 1e6, "K_t": 2.0, "K_ts": 1.0, "n": 1.0},
    )
    assert r.valor == pytest.approx(2 * (1e6 / (50 * 100**2 / 6) + 1e6 / (100 * 50**2 / 6)))


def test_flecha_em_yy_usa_a_inercia_de_yy():
    nos = [
        {"id": "s", "tipo": "retangular"},
        {"id": "v", "tipo": "balanco_ponta"},
        {"id": "d", "tipo": "flecha", "opcoes": {"eixo": "YY"}},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "d", "entrada": "entrada"},
        {"de": "v", "saida": "flecha", "para": "d", "entrada": "flecha"},
        {"de": "d", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    valores = {"h": 100.0, "F": 100.0, "L": 2000.0, "E": 200000.0, "r_delta": 200.0}
    i = 100 * 2000**3 / (3 * 200000 * 10.0)
    assert mt.isolar(m, "b", valores).valor == pytest.approx((12 * i / 100) ** (1 / 3))


# ---------------------------------------------------------------------------
# Força vezes distância
# ---------------------------------------------------------------------------


def test_forca_maxima():
    m = montar("retangular", ("flexao", BRACO), "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "F_xx", {"b": 40.0, "h": 80.0, "d_xx": 500.0, **SY_N})
    assert r.sentido == mt.MAXIMO
    assert r.valor == pytest.approx(240 * 40 * 80**2 / 6 / 500)


def test_distancia_maxima():
    m = montar("retangular", ("flexao", BRACO), "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d_xx", {"b": 40.0, "h": 80.0, "F_xx": 5e3, **SY_N})
    assert r.sentido == mt.MAXIMO
    assert r.valor == pytest.approx(240 * 40 * 80**2 / 6 / 5e3)


def test_valor_direto_nao_pede_forca_nem_distancia():
    m = montar("retangular", "flexao", "von_mises", mb.RESULTADO)
    assert "M_x" in letras(m)
    assert not {"F_xx", "d_xx"} & letras(m)


def test_forca_em_xx_e_em_yy_sao_letras_diferentes():
    m = montar("retangular", ("flexao", BRACO), ("flexao_y", BRACO), "von_mises", mb.RESULTADO)
    assert {"F_xx", "d_xx", "F_yy", "d_yy"} <= letras(m)


def test_forca_em_yy_usa_o_modulo_de_yy():
    m = montar("retangular", ("flexao_y", BRACO), "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "F_yy", {"b": 40.0, "h": 80.0, "d_yy": 500.0, **SY_N})
    assert r.valor == pytest.approx(240 * 80 * 40**2 / 6 / 500)


def test_forca_sem_a_cortante_avisa():
    m = montar("retangular", ("flexao", BRACO), "von_mises", mb.RESULTADO)
    assert any("também corta a seção" in a for a in m.alertas)


def test_bloco_de_cortante_tira_o_aviso():
    m = montar("retangular", ("flexao", BRACO), "cortante", "von_mises", mb.RESULTADO)
    assert not any("também corta a seção" in a for a in m.alertas)


def test_opcao_com_cortante_tira_o_aviso_e_soma_em_v():
    m = montar("retangular", ("flexao", BRACO_V), "von_mises", mb.RESULTADO)
    assert not m.alertas
    assert "F_xx" in letras(m)
    assert "V_y" not in letras(m)


def test_com_braco_curto_a_cortante_da_forca_manda():
    m = montar("retangular", ("flexao", BRACO_V), "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "F_xx", {"b": 40.0, "h": 80.0, "d_xx": 2.0, **SY_N})
    assert "linha neutra" in r.manda.condicao.nome
    assert r.valor == pytest.approx(240 / math.sqrt(3) * 40 * 80 / 1.5)


def test_com_braco_longo_a_flexao_manda():
    m = montar("retangular", ("flexao", BRACO_V), "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "F_xx", {"b": 40.0, "h": 80.0, "d_xx": 500.0, **SY_N})
    assert "fibra" in r.manda.condicao.nome


def test_viga_ligada_manda_na_escolha():
    """Fio na porta M: o momento é o do bloco, e a escolha do modo não entra."""
    nos = [
        {"id": "s", "tipo": "retangular"},
        {"id": "v", "tipo": "balanco_ponta"},
        {"id": "f", "tipo": "flexao", "opcoes": BRACO},
        {"id": "e", "tipo": "von_mises"},
        {"id": "r", "tipo": mb.RESULTADO},
    ]
    fios = [
        {"de": "s", "saida": "saida", "para": "f", "entrada": "entrada"},
        {"de": "v", "saida": "M", "para": "f", "entrada": "valor"},
        {"de": "f", "saida": "saida", "para": "e", "entrada": "entrada"},
        {"de": "e", "saida": "condicao", "para": "r", "entrada": "condicoes"},
    ]
    m = mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))
    assert "F" in letras(m) and "F_xx" not in letras(m)


def test_face_do_bloco_mostra_como_o_momento_entra():
    face = mb.POR_CHAVE["flexao_y"].face
    assert face({}) == "σ = M_y·c/I"
    assert face(BRACO) == "M = F_yy·d_yy"
    assert "V = F" in face(BRACO_V)


# ---------------------------------------------------------------------------
# Cortante nos dois eixos
# ---------------------------------------------------------------------------


def test_cortante_horizontal_na_retangular():
    m = montar("retangular", "cortante_x", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "V_x", {"b": 40.0, "h": 80.0, **SY_N})
    assert r.valor == pytest.approx(240 / math.sqrt(3) * 40 * 80 / 1.5)


def test_centro_compoe_as_duas_cortantes():
    m = montar("retangular", "cortante", "cortante_x", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "S_y", {"b": 40.0, "h": 80.0, "V_y": 3e4, "V_x": 4e4, "n": 1.0})
    assert "centro" in r.manda.condicao.nome
    assert r.valor == pytest.approx(math.sqrt(3) * 1.5 * 5e4 / (40 * 80))


def test_eixo_com_momento_e_cortante_no_mesmo_plano_nao_soma():
    """M_x com V_y: a fibra não tem cortante, como na conta clássica."""
    m = montar("circular", "flexao", "cortante", "von_mises", mb.RESULTADO)
    fibra = next(c for c in m.condicoes if "fibra" in c.ponto)
    assert sp.Symbol("V_y", positive=True) not in fibra.esquerda.free_symbols


def test_eixo_com_momento_e_cortante_em_planos_diferentes_soma_na_fibra():
    """M_x com V_x: a tangente da fibra é a direção de V_x, e τ vale 4·V/(3·A) ali."""
    m = montar("circular", "flexao", "cortante_x", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "S_y", {"d": 30.0, "M_x": 1e5, "V_x": 2e4, "n": 1.0})
    a = math.pi * 30**2 / 4
    sigma = 32 * 1e5 / (math.pi * 30**3)
    tau = 4 * 2e4 / (3 * a)
    assert r.valor == pytest.approx(math.sqrt(sigma**2 + 3 * tau**2))


# ---------------------------------------------------------------------------
# Seção desenhada
# ---------------------------------------------------------------------------


@pytest.fixture
def chapa_salva(tmp_path):
    partes = [sd.Parte(sd.RET, 0, 0, 50, 100)]
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        catalogo.salvar_perfil(
            sd.perfil_da_secao("Chapa", sd.analisar(partes)),
            desenho=tuple(p.como_dicionario() for p in partes),
        )
        yield


def desenhada(*tipos) -> mt.Montagem:
    return montar(("desenhada", {"desenho": "Chapa"}), *tipos, mb.RESULTADO)


def test_desenhada_em_yy_bate_com_a_retangular(chapa_salva):
    r = mt.isolar(desenhada("flexao_y", "von_mises"), "M_y", {"s": 1.0, **SY_N})
    assert r.valor == pytest.approx(240 * 100 * 50**2 / 6, rel=1e-3)


def test_desenhada_com_os_dois_momentos_acha_o_canto(chapa_salva):
    m = desenhada("flexao", "flexao_y", "von_mises")
    r = mt.isolar(m, "M_y", {"s": 1.0, "M_x": 5e6, **SY_N})
    assert "canto" in r.manda.condicao.nome
    assert r.valor == pytest.approx((240 - 5e6 / (50 * 100**2 / 6)) * (100 * 50**2 / 6), rel=2e-3)


def test_desenhada_com_cortante_na_fibra_de_yy_usa_a_altura_certa(chapa_salva):
    m = desenhada("flexao_y", "cortante", "von_mises")
    r = mt.isolar(m, "S_y", {"s": 1.0, "M_y": 2e6, "V_y": 1e4, "n": 1.0})
    sigma = 2e6 / (100 * 50**2 / 6)
    tau = 1.5 * 1e4 / (50 * 100)
    assert r.valor == pytest.approx(math.sqrt(sigma**2 + 3 * tau**2), rel=2e-3)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def abrir(modelo: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    at.selectbox(key="mf_modelo").set_value(modelo).run()
    assert not at.exception
    return at


def test_modelo_da_forca_maxima_diz_quanto_aguenta():
    at = abrir("Força máxima num braço")
    assert any(s.value.startswith("**F_xx ≤") for s in at.success)
    assert any(c.label.startswith("d_xx") for c in at.number_input)
    assert not any(c.label.startswith("M_x") for c in at.number_input)


def test_trocar_para_valor_do_momento_na_tela():
    at = abrir("Força máxima num braço")
    chave = "mf_op_n2_entrada"
    assert at.selectbox(key=chave).value == mb.FORCA_COM_CORTANTE
    at.selectbox(key=chave).set_value(mb.MOMENTO_DIRETO).run()
    assert not at.exception
    # F_xx saiu do desenho: o momento passa a ser a letra que falta.
    assert at.session_state["mf_alvo"] == "M_x"
    assert not any(c.label.startswith(("F_xx", "d_xx")) for c in at.number_input)


def test_modelos_novos_estao_na_lista():
    nomes = {m.nome for m in mm.MODELOS}
    assert {"Flexão em XX e YY", "Distância máxima de uma força"} <= nomes
