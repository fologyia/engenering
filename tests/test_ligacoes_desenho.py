"""Desenhos das ligações soldadas: a chapa de nó bem formada e o giro do desenho (30/10/2026).

O usuário pediu para poder girar o desenho — a força nem sempre está para cima: às vezes vai na
diagonal ou deitada — e achou o desenho da chapa de nó mal feito: com ângulo pequeno a chapa
atravessava o apoio. O giro é só do desenho (o cálculo não muda) e vai junto para o registro e o
memorial.
"""

from __future__ import annotations

import json
import math

import pytest

from core import desenho_girado as dg
from core import ligacoes as lg
from core import ligacoes_soldadas as ls
from core.record_charts import imagens_do_registro

SOLDADAS = [
    lg.EntradaSolda(m_sd_kNm=2.0, n_sd_kN=-10.0, v_sd_kN=-30.0),
    ls.EntradaBarraSoldada(),
    ls.EntradaBarraSoldada(peca=ls.PECA_CHAPA, com_apoio=False, solda_na_ponta=True),
    ls.EntradaChapaNoApoio(),
]


# ------------------------------------------------------------------ a chapa de nó
@pytest.mark.parametrize("theta", [15.0, 30.0, 45.0, 60.0, 90.0])
@pytest.mark.parametrize("excentricidade", [0.0, 40.0, -60.0])
@pytest.mark.parametrize("peca", [ls.PECA_CANTONEIRA, ls.PECA_CHAPA])
def test_chapa_de_no_so_encosta_no_apoio_no_trecho_soldado(theta, excentricidade, peca):
    e = ls.EntradaBarraSoldada(
        peca=peca, theta_graus=theta, excentricidade_mm=excentricidade, modo=ls.MODO_VERIFICAR
    )
    g = ls._desenho_da_barra(e)
    assert min(x for x, _ in g.chapa) >= -1e-9  # não atravessa o apoio
    na_face = [y for x, y in g.chapa if abs(x) < 1e-6]
    assert na_face and min(na_face) >= -1e-6 and max(na_face) <= e.l_apoio_mm + 1e-6
    assert min(x for x, _ in g.contorno_da_barra) >= g.folga - 1e-6  # ponta longe da face
    # o eixo da barra sai do ponto de trabalho, na face, a θ dela (a x̄ do dorso)
    x0, y0 = g.mm(0.0, g.barra.x_barra)
    assert (x0, y0) == pytest.approx((0.0, e.l_apoio_mm / 2 + excentricidade))
    x1, y1 = g.mm(100.0, g.barra.x_barra)
    assert math.degrees(math.atan2(x1 - x0, y1 - y0)) == pytest.approx(theta)


def test_chapa_de_no_cabe_a_secao_de_whitmore_e_os_filetes():
    e = ls.EntradaBarraSoldada(theta_graus=30.0, modo=ls.MODO_VERIFICAR)
    g = ls._desenho_da_barra(e)
    a, b = e.l_dorso_mm, e.l_borda_mm
    c_ = g.barra.largura
    pontos = [
        g.mm(g.s_ponta, -a * ls.TAN_30), g.mm(g.s_ponta, c_ + b * ls.TAN_30),  # Whitmore
        g.mm(g.s_ponta + a, 0.0), g.mm(g.s_ponta + b, c_),  # fim dos filetes
    ]  # fmt: skip
    for p in pontos:
        assert dg.dentro(p, g.chapa), p


# ------------------------------------------------------------------ o giro
@pytest.mark.parametrize(
    ("giro", "esperado"),
    [(0, 0), (90, 90), (270, -90), (-180, 180), (540, 180), (-450, -90)],
)
def test_giro_fica_entre_menos_180_e_180(giro, esperado):
    assert dg.angulo_do_giro(giro) == pytest.approx(esperado)


def test_giro_positivo_e_anti_horario():
    tela = dg.Tela([(0.0, 0.0), (100.0, 100.0)], (0, 0, 100, 100), 90.0)
    assert tela.direcao(1.0, 0.0) == pytest.approx((0.0, -1.0))  # o +x da peça vai para cima
    assert lg.texto_do_giro(90) == "90° no sentido anti-horário"
    assert lg.texto_do_giro(-45) == "45° no sentido horário"


@pytest.mark.parametrize("entrada", SOLDADAS)
def test_girar_muda_so_o_desenho(entrada):
    r = lg.calcular(entrada)
    parado, girado = lg.figura(r), lg.figura(r, giro_graus=90)
    assert (girado.largura_px, girado.altura_px) == (parado.largura_px, parado.altura_px)
    assert girado.png != parado.png
    assert lg.figura(r, giro_graus=360).png == parado.png  # uma volta inteira
    assert lg.figura(r, giro_graus=-270).png == girado.png
    assert lg.calcular(entrada).verificacoes == r.verificacoes


@pytest.mark.parametrize("giro", [-135, -30, 45, 180])
@pytest.mark.parametrize("entrada", SOLDADAS)
def test_desenho_girado_sai_em_qualquer_angulo(entrada, giro):
    desenho = lg.figura(lg.calcular(entrada), giro_graus=giro)
    assert desenho.png.startswith(b"\x89PNG")


@pytest.mark.parametrize("entrada", SOLDADAS)
def test_registro_e_memorial_levam_o_desenho_girado(entrada):
    r = lg.calcular(entrada)
    registro = json.loads(json.dumps(lg.registro_ligacao(r, giro_graus=45)))
    assert registro["resultados"]["figura_ligacao"]["giro_graus"] == 45
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == "" and imagens[0]["png"] == lg.figura(r, giro_graus=45).png
    assert "giro_graus" not in lg.registro_ligacao(r)["resultados"]["figura_ligacao"]


def test_ligacao_parafusada_nao_gira():
    r = lg.calcular(lg.EntradaChapaSimples())
    assert r.tipo not in lg.TIPOS_QUE_GIRAM
    assert lg.figura(r, giro_graus=90).png == lg.figura(r).png
    figura = lg.registro_ligacao(r, giro_graus=90)["resultados"]["figura_ligacao"]
    assert "giro_graus" not in figura
