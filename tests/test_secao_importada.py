"""Seção da prancheta nos casos do Assistente: a forma real, com furos e partes sobrepostas."""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from components.assistente_cargas_ui import chave_do_campo
from components.elementos_croquis import croqui_da_flexao
from core import elementos_catalogo as cat
from core import elementos_vigas as ev
from core import secao_desenhada as sd
from core import section_catalog as catalogo
from core.elementos_base import Resultado, calcular_caso

APP = str(Path(__file__).resolve().parents[1] / "app.py")
FLEXAO = "flexao_secao"


def _ret(x: float, y: float, b: float, h: float, **extra) -> sd.Parte:
    return sd.Parte(sd.RET, x, y, b, h, **extra)


CHAPA_COM_FURO = [_ret(0, 0, 100, 200), sd.Parte(sd.CIRC, 0, 0, 40, furo=True)]
SOBREPOSTAS = [_ret(0, 0, 100, 100), _ret(0, 0, 100, 100)]
I_MONTADO = [_ret(0, 95, 100, 10), _ret(0, 0, 6, 180), _ret(0, -95, 100, 10)]
CANTONEIRA = [_ret(0, 50, 10, 100), _ret(45, 5, 80, 10)]


def _salvar(nome: str, partes: list[sd.Parte]) -> None:
    analise = sd.analisar(partes)
    catalogo.salvar_perfil(
        sd.perfil_da_secao(nome, analise), desenho=tuple(p.como_dicionario() for p in partes)
    )


@pytest.fixture(autouse=True)
def _catalogo_limpo(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        ev._analisar_desenho.cache_clear()
        yield


def rodar(nome: str, caso: str = FLEXAO, **valores) -> Resultado:
    base = {"tipo_secao": ev.DESENHADA, "desenho": nome, **valores}
    return calcular_caso(cat.CASOS[caso], base)


def metrica(resultado: Resultado, rotulo: str) -> float:
    return next(float(m.valor) for m in resultado.metricas if m.rotulo == rotulo)


def linha(resultado: Resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


# ---------------------------------------------------------------------------
# Lista de seções
# ---------------------------------------------------------------------------


def test_lista_so_traz_as_secoes_com_desenho():
    assert ev.nomes_dos_desenhos() == (ev.SEM_DESENHO,)
    _salvar("Minha chapa", CHAPA_COM_FURO)
    analise = sd.analisar(I_MONTADO)
    catalogo.salvar_perfil(sd.perfil_da_secao("Sem desenho", analise))
    assert ev.nomes_dos_desenhos() == (ev.SEM_DESENHO, "Minha chapa")


def test_sem_escolher_a_secao_a_mensagem_diz_o_que_fazer():
    with pytest.raises(ValueError, match="Escolha uma seção salva"):
        rodar(ev.SEM_DESENHO)


@pytest.mark.parametrize("caso", ["viga_reacoes", FLEXAO, "coluna_simples"])
def test_tipo_desenhado_existe_nos_casos_que_usam_a_secao(caso):
    campos = {c.chave: c for c in cat.CASOS[caso].campos}
    assert ev.DESENHADA in campos["tipo_secao"].opcoes
    assert "desenho" in campos


# ---------------------------------------------------------------------------
# A forma real na conta
# ---------------------------------------------------------------------------


def test_furo_entra_na_inercia_e_no_cisalhamento():
    _salvar("Chapa", CHAPA_COM_FURO)
    r = rodar("Chapa", m_kNm=20.0, v_kN=10.0)
    i = 100 * 200**3 / 12 - math.pi * 40**4 / 64
    assert metrica(r, "Tensão na fibra de baixo") == pytest.approx(20e6 * 100 / i, rel=2e-3)
    # No centro, a largura cai de 100 para 60: o τ sobe acima de 1,5·V/A.
    area = 100 * 200 - math.pi * 40**2 / 4
    assert metrica(r, "Cortante máximo") > 1.5 * 10000.0 / area * 1.2


def test_partes_sobrepostas_nao_contam_duas_vezes():
    _salvar("Dobrada", SOBREPOSTAS)
    r = rodar("Dobrada", m_kNm=1.0, v_kN=0.0)
    w = 100.0 * 100.0**2 / 6.0
    assert metrica(r, "W da seção") == pytest.approx(w / 1000.0, rel=1e-3)
    assert metrica(r, "Fator de forma Z/W") == pytest.approx(1.5, rel=1e-2)


def test_i_desenhado_bate_com_a_forma_fechada():
    _salvar("I montado", I_MONTADO)
    r = rodar("I montado", m_kNm=10.0, v_kN=30.0)
    i = 100 * 200**3 / 12 - 94 * 180**3 / 12
    q = 100 * 10 * 95 + 90 * 6 * 45
    assert metrica(r, "Tensão na fibra de baixo") == pytest.approx(10e6 * 100 / i, rel=1e-3)
    assert metrica(r, "Cortante máximo") == pytest.approx(30000 * q / (i * 6), rel=1e-3)
    assert "V·Q/(I·b)" in linha(r, "Tensão de cisalhamento").formula


def test_integral_do_cisalhamento_devolve_a_cortante_com_furo():
    _salvar("Chapa", CHAPA_COM_FURO)
    secao = ev.secao_do_caso({"tipo_secao": ev.DESENHADA, "desenho": "Chapa"})
    f = secao.faixas
    assert -np.trapezoid(f.tau(5000.0) * f.b, f.y) == pytest.approx(5000.0, rel=2e-3)


def test_eixo_fraco_usa_a_outra_direcao_do_desenho():
    _salvar("I montado", I_MONTADO)
    forte = rodar("I montado", m_kNm=1.0, v_kN=0.0)
    fraco = rodar("I montado", m_kNm=1.0, v_kN=0.0, eixo=ev.EIXO_FRACO)
    iy = 2 * 10 * 100**3 / 12 + 180 * 6**3 / 12
    assert metrica(fraco, "W da seção") == pytest.approx(iy / 50 / 1000.0, rel=1e-3)
    assert metrica(fraco, "W da seção") < metrica(forte, "W da seção")


def test_secao_assimetrica_avisa_que_m_sobre_w_nao_basta():
    _salvar("L", CANTONEIRA)
    r = rodar("L", m_kNm=0.5, v_kN=1.0)
    assert any("eixos principais" in a for a in r.alertas)


def test_secao_simetrica_nao_recebe_esse_aviso():
    _salvar("I montado", I_MONTADO)
    assert not any("eixos principais" in a for a in rodar("I montado").alertas)


def test_perfil_do_catalogo_vindo_da_prancheta_tambem_usa_a_forma_real():
    """Quem já escolheu o perfil salvo na lista do catálogo não perde o furo do desenho."""
    _salvar("Chapa", CHAPA_COM_FURO)
    r = calcular_caso(cat.CASOS[FLEXAO], {"tipo_secao": ev.CATALOGO, "perfil": "Chapa"})
    assert "V·Q/(I·b)" in linha(r, "Tensão de cisalhamento").formula


def test_viga_e_coluna_calculam_com_a_secao_desenhada():
    _salvar("I montado", I_MONTADO)
    assert rodar("I montado", "viga_reacoes").verificacoes
    assert rodar("I montado", "coluna_simples").verificacoes


def test_analise_e_guardada_entre_as_rodadas():
    _salvar("I montado", I_MONTADO)
    rodar("I montado")
    antes = ev._analisar_desenho.cache_info().hits
    rodar("I montado", m_kNm=12.0)
    assert ev._analisar_desenho.cache_info().hits > antes


# ---------------------------------------------------------------------------
# Desenhos
# ---------------------------------------------------------------------------


def test_figura_sai_com_a_forma_desenhada():
    _salvar("Chapa", CHAPA_COM_FURO)
    r = rodar("Chapa")
    assert r.figuras and r.figuras[0].png


def test_croqui_mostra_a_secao_escolhida():
    _salvar("Chapa", CHAPA_COM_FURO)
    _salvar("I montado", I_MONTADO)
    base = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    chapa = croqui_da_flexao({**base, "tipo_secao": ev.DESENHADA, "desenho": "Chapa"})
    perfil = croqui_da_flexao({**base, "tipo_secao": ev.DESENHADA, "desenho": "I montado"})
    assert chapa != perfil


def test_croqui_sem_secao_escolhida_nao_quebra():
    base = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    assert "<rect" in croqui_da_flexao({**base, "tipo_secao": ev.DESENHADA})


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _abrir_flexao(partes: list[sd.Parte] | None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/assistente_cargas.py")
    if partes is not None:
        at.session_state["secao_partes"] = [p.como_dicionario() for p in partes]
        at.session_state["secao_nome"] = "Da prancheta"
    at.session_state["assistente_geometria"] = FLEXAO
    at.session_state[chave_do_campo(FLEXAO, "tipo_secao")] = ev.DESENHADA
    at.run()
    assert not at.exception
    return at


def test_botao_traz_a_secao_aberta_e_escolhe_ela():
    at = _abrir_flexao(I_MONTADO)
    at.button(key=f"assistente_trazer::{FLEXAO}").click().run()
    assert not at.exception
    assert "Da prancheta" in ev.nomes_dos_desenhos()
    assert at.session_state[chave_do_campo(FLEXAO, "desenho")] == "Da prancheta"


def test_sem_secao_aberta_nao_aparece_o_botao():
    at = _abrir_flexao(None)
    assert f"assistente_trazer::{FLEXAO}" not in [b.key for b in at.button]


def test_secao_em_pedacos_avisa_em_vez_de_quebrar():
    soltas = [_ret(0, 0, 50, 50), _ret(200, 0, 50, 50)]
    at = _abrir_flexao(soltas)
    at.button(key=f"assistente_trazer::{FLEXAO}").click().run()
    assert not at.exception
    assert any("pedaços soltos" in w.value for w in at.warning)


def test_botao_da_pagina_de_desenho_abre_a_flexao_com_a_forma_real():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/desenhar_secao.py").run()
    at.button(key=f"secao_usar_{FLEXAO}").click().run()
    assert not at.exception
    assert at.session_state["assistente_geometria"] == FLEXAO
    assert at.session_state[chave_do_campo(FLEXAO, "tipo_secao")] == ev.DESENHADA
    assert at.session_state[chave_do_campo(FLEXAO, "desenho")] in ev.nomes_dos_desenhos()
