"""Ligação rígida viga–pilar (4E): linhas de plastificação, pilar, enrijecedores e a página."""

from __future__ import annotations

import math

import pytest

from components.ligacao_rigida_help import AJUDA
from core import bolted_connection as bc
from core import ligacao_rigida as lr
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/ligacao_rigida.py"
P = lr.EntradaRigida()
VIGA = pi.perfil("W 410 x 46,1")
PILAR = pi.perfil("HP 310 x 79,0 (H)")


def linha(r: lr.ResultadoRigida, nome: str):
    return next(v for g in r.grupos for v in g.linhas if v.nome == nome)


def test_braços_dos_parafusos():
    r = lr.calcular(P)
    assert r.geometria["h0"] == pytest.approx(403 - 11.2 / 2 + 45)
    assert r.geometria["h1"] == pytest.approx(403 - 1.5 * 11.2 - 45)


def test_y_p_aisc_358_tabela_6_2():
    bp, g, pfo, pfi = 160.0, 100.0, 45.0, 45.0
    h0, h1 = 442.4, 341.2
    s = 0.5 * math.sqrt(bp * g)
    pfi_ = min(pfi, s)
    esperado = bp / 2 * (h1 * (1 / pfi_ + 1 / s) + h0 / pfo - 0.5) + 2 / g * h1 * (pfi_ + s)
    assert lr.y_p_4e(bp, g, pfo, pfi, h0, h1)[0] == pytest.approx(esperado)


def test_y_c_sem_e_com_enrijecedores():
    bcf, g, h0, h1, c = 306.0, 100.0, 442.4, 341.2, 101.2
    s = 0.5 * math.sqrt(bcf * g)
    sem = (
        bcf / 2 * (h1 / s + h0 / s)
        + 2 / g * (h1 * (s + 3 * c / 4) + h0 * (s + c / 4) + c**2 / 2)
        + g / 2
    )
    assert lr.y_c_4e(bcf, g, h0, h1, c, None, None)[0] == pytest.approx(sem)
    com = lr.y_c_4e(bcf, g, h0, h1, c, 40.0, 40.0)[0]
    assert com > sem


def test_parafusos_tracionados_nbr():
    r = lr.calcular(P)
    Ft = 0.75 * math.pi * 19.1**2 / 4 * 830 / 1.35 / 1000
    assert linha(r, "Parafusos tracionados").resistente == pytest.approx(
        2 * Ft * (r.geometria["h0"] + r.geometria["h1"]) / 1000
    )


def test_chapa_e_mesa_do_pilar():
    r = lr.calcular(P)
    assert linha(r, "Escoamento da chapa (linhas de plastificação)").resistente == pytest.approx(
        250 * 22.4**2 * r.geometria["Yp"] / 1.10 / 1e6
    )
    assert linha(r, "Flexão da mesa do pilar").resistente == pytest.approx(
        345 * PILAR.tf**2 * r.geometria["Yc"] / 1.10 / 1e6
    )
    assert r.situacao == "ATENDE"


def test_chapa_fina_pede_atencao():
    r = lr.calcular(lr.com(P, tp=12.5))
    v = linha(r, "Chapa grossa (sem efeito de alavanca)")
    assert v.status == "ALERTA" and not v.obrigatoria


def test_corte_so_nos_parafusos_comprimidos():
    r = lr.calcular(lr.com(P, parafusos_comprimidos=2))
    assert linha(r, "Corte nos parafusos do lado comprimido").resistente == pytest.approx(
        2 * bc.resist_corte(19.1, "A325", lr.NORMA, True)
    )


def test_painel_de_alma_e_chapa_de_reforco():
    r = lr.calcular(lr.com(P, M=300.0))
    painel = linha(r, "Painel de alma do pilar: cisalhamento")
    assert painel.solicitante == pytest.approx(300e3 / (403 - 11.2))
    sem = painel.resistente
    r2 = lr.calcular(lr.com(P, M=300.0, reforco_alma=8.0))
    com = linha(r2, "Painel de alma do pilar: cisalhamento").resistente
    assert com == pytest.approx(sem + 2 * 0.6 * 345 * PILAR.d * 8 / 1.10 / 1000)


def test_momentos_iguais_dos_dois_lados_zeram_o_painel_e_criam_o_par():
    r = lr.calcular(lr.com(P, outro_lado=True, M2=120.0))
    assert linha(r, "Painel de alma do pilar: cisalhamento").solicitante == pytest.approx(0.0)
    assert linha(r, "Alma do pilar: instabilidade por compressão").status == "OK"


def test_pilar_fraco_pede_enrijecedores_e_eles_resolvem():
    fraco = lr.PerfilEscolhido(pi.FAMILIA_W, "W 250 x 17,9")
    r = lr.calcular(lr.com(P, pilar=fraco, M=60.0, g=70.0, bp=150.0))
    nomes = {v.nome: v.status for v in r.linhas}
    assert nomes.get("Enrijecedores de continuidade necessários") == "NÃO OK"
    r2 = lr.calcular(lr.com(P, pilar=fraco, M=60.0, g=70.0, bp=150.0, enrijecedores=True,
                            ts=8.0, bs=45.0, corte=10.0))  # fmt: skip
    assert any(g.nome == "Enrijecedores de continuidade" for g in r2.grupos)
    assert "Enrijecedores de continuidade necessários" not in {v.nome for v in r2.linhas}


def test_disposicoes():
    r = lr.calcular(lr.com(P, g=50.0, bp=200.0))
    assert linha(r, "Gabarito entre parafusos").status == "NÃO OK"
    assert linha(r, "Largura da chapa").status == "ALERTA"


def test_validacao():
    assert lr.validar(lr.com(P, M=0.0))
    assert lr.validar(lr.com(P, pfi=200.0))
    assert not lr.validar(P)


def test_registro_e_memorial():
    reg = lr.registro(lr.calcular(lr.com(P, enrijecedores=True)))
    ap.conferir_registro_e_memorial(reg, lr.MODULO_ID)
    ap.conferir_entradas_curadas(reg, lr.MODULO_ID)


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA, lr_enrijecedores=True, lr_outro_lado=True, lr_solda_mesa=lr.FILETE)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    t = ap.abrir(PAGINA, lr_familia_viga=pi.FAMILIA_SOLDADO)
    assert not ap.sem_ajuda(t)
    assert "Situação" in ap.metricas(t)
