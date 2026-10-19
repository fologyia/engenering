"""Comprimentos de flambagem pelos travamentos do esqueleto do modelo."""

from __future__ import annotations

import math

import pytest

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import travamentos as tv
from tests import dados_solidworks as sw
from tests.test_esforcos_modelo import PILAR, VIGA, importar
from tests.test_leitura_do_modelo import geometria


def corpo(nome, inicio, fim, forma="BARRA", secao=(200.0, 100.0), direcao=None):
    comprimento = math.dist(inicio, fim)
    return ld.CorpoDoModelo(
        nome,
        "",
        "",
        tuple(float(v) for v in inicio),
        tuple(float(v) for v in fim),
        comprimento,
        None,
        forma,
        secao,
        direcao,
    )


def esqueleto(*corpos) -> ld.GeometriaDoModelo:
    return ld.GeometriaDoModelo(corpos=tuple(corpos))


def sugeridos(g, nome, tipo="—"):
    return tv.comprimentos(g, g.corpo(nome), tipo, "Y")


# ------------------------------------------------------------------ geometria
@pytest.mark.parametrize(
    ("p1", "q1", "p2", "q2", "s", "t", "distancia"),
    [
        ((0, 0, 0), (2, 0, 0), (1, -1, 0.5), (1, 1, 0.5), 0.5, 0.5, 0.5),  # cruzam a 0,5
        ((0, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0), 1.0, 0.0, 1.0),  # colineares, separadas
        ((0, 0, 0), (2, 0, 0), (0, 1, 0), (2, 1, 0), None, None, 1.0),  # paralelas
        ((0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 2, 0), 0.0, 0.0, 1.0),  # um ponto
    ],
)
def test_pontos_mais_proximos(p1, q1, p2, q2, s, t, distancia):
    rs, rt, rd = tv.mais_proximos(p1, q1, p2, q2)
    assert rd == pytest.approx(distancia)
    if s is not None:
        assert (rs, rt) == (pytest.approx(s), pytest.approx(t))


# ------------------------------------------------------------------ pilares
def test_portico_do_exemplo():
    g = geometria()
    pilar = sugeridos(g, "Aparar/Estender12[1]", "Pilar")
    assert (pilar.lx_m, pilar.ly_m) == (pytest.approx(4.0), pytest.approx(4.0))
    assert "na direção da alma" in pilar.motivo and not pilar.balanco
    # Esqueleto da macro v4 (sem a orientação da seção): Lx = Ly = o maior, e o motivo diz.
    v4 = ld.ler_esqueleto(sw.csv_esqueleto(versao="v4"), "v4.csv")
    pilar = sugeridos(v4, "Aparar/Estender12[1]", "Pilar")
    assert pilar.lx_m == pilar.ly_m == pytest.approx(4.0)
    assert "sem a orientação da seção" in pilar.motivo
    viga = sugeridos(g, "Canal c C8X13.75(1)[2]", "Viga")
    assert (viga.lx_m, viga.ly_m, viga.lb_m) == (6.0, 6.0, 6.0)


def test_pilar_travado_numa_direcao_so():
    # Pilar de 4 m; uma viga em X chega na metade da altura; vigas nas duas direções no topo.
    g = esqueleto(
        corpo("P", (0, 0, 0), (0, 4, 0)),
        corpo("VX meio", (0, 2, 0), (3, 2, 0)),
        corpo("VX topo", (0, 4, 0), (3, 4, 0)),
        corpo("VZ topo", (0, 4, 0), (0, 4, 3)),
    )
    sem_orientacao = sugeridos(g, "P", "Pilar")
    assert sem_orientacao.lx_m == sem_orientacao.ly_m == pytest.approx(4.0)  # o maior
    assert "2,00 m em X e 4,00 m em Z" in sem_orientacao.motivo
    # Com a orientação (macro v5): a alma em X → Lx na direção X.
    orientado = esqueleto(corpo("P", (0, 0, 0), (0, 4, 0), direcao=(1.0, 0.0, 0.0)), *g.corpos[1:])
    r = sugeridos(orientado, "P", "Pilar")
    assert (r.lx_m, r.ly_m) == (pytest.approx(2.0), pytest.approx(4.0))
    assert "na direção da alma" in r.motivo


def test_pilar_com_topo_livre_e_balanco():
    g = esqueleto(corpo("P", (0, 0, 0), (0, 4, 0)), corpo("Outro", (5, 0, 0), (5, 4, 0)))
    r = sugeridos(g, "P", "Pilar")
    assert r.balanco and r.lx_m == pytest.approx(tv.K_BALANCO * 4.0)


# ------------------------------------------------------------------ vigas
def test_viga_com_secundarias_e_pilar_no_meio():
    g = esqueleto(
        corpo("V", (0, 4, 0), (6, 4, 0)),
        corpo("S1", (2, 4, 0), (2, 4, 3)),  # secundárias chegam de lado
        corpo("S2", (4, 4, 0), (4, 4, 3)),
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (6, 0, 0), (6, 4, 0)),
    )
    r = sugeridos(g, "V", "Viga")
    assert r.lb_m == pytest.approx(2.0) and r.ly_m == pytest.approx(2.0)
    assert r.lx_m == pytest.approx(6.0)  # as secundárias não apoiam a viga na vertical
    com_pilar = esqueleto(*g.corpos, corpo("Pm", (3, 0, 0), (3, 4, 0)))
    assert sugeridos(com_pilar, "V", "Viga").lx_m == pytest.approx(3.0)


def test_mao_francesa_apoia_a_viga_na_vertical():
    g = esqueleto(
        corpo("V", (0, 4, 0), (6, 4, 0)),
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (6, 0, 0), (6, 4, 0)),
        corpo("MF", (0, 3, 0), (1, 4, 0)),  # 45°, chega na viga a 1 m
    )
    assert sugeridos(g, "V", "Viga").lx_m == pytest.approx(5.0)


def test_sobra_curta_alem_do_apoio_nao_e_balanco():
    g = esqueleto(
        corpo("V", (-0.3, 4, 0), (6, 4, 0)),  # passa 0,3 m do pilar
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (6, 0, 0), (6, 4, 0)),
    )
    r = sugeridos(g, "V", "Viga")
    assert not r.balanco and r.lx_m == pytest.approx(6.0)
    longa = esqueleto(corpo("V", (-1.5, 4, 0), (6, 4, 0)), *g.corpos[1:])
    r = sugeridos(longa, "V", "Viga")
    assert r.balanco and r.lx_m == pytest.approx(6.0)  # 2,1 × 1,5 = 3,15 < 6
    assert "balanço" in r.motivo


def test_paralelas_lado_a_lado_nao_se_travam():
    g = esqueleto(
        corpo("V", (0, 4, 0), (6, 4, 0)),
        corpo("Vizinha", (0, 4, 0.2), (6, 4, 0.2)),  # paralela, a 0,2 m
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (6, 0, 0), (6, 4, 0)),
    )
    assert sugeridos(g, "V", "Viga").lb_m == pytest.approx(6.0)


def test_chapa_sobre_a_viga_fica_no_motivo():
    g = esqueleto(
        corpo("V", (0, 4, 0), (6, 4, 0)),
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (6, 0, 0), (6, 4, 0)),
        corpo("Chapa", (0, 4.105, -0.5), (6, 4.105, -0.5), forma="CHAPA", secao=(2000.0, 6.35)),
    )
    r = sugeridos(g, "V", "Viga")
    assert "a chapa Chapa apoia na mesa superior" in r.motivo
    assert r.lb_m == pytest.approx(6.0)  # o sugerido não conta com a chapa


def test_contraventamento_em_x_ligado_no_cruzamento():
    g = esqueleto(
        corpo("D1", (0, 0, 0), (4, 4, 0)),
        corpo("D2", (0, 4, 0), (4, 0, 0)),
        corpo("Pa", (0, 0, 0), (0, 4, 0)),
        corpo("Pb", (4, 0, 0), (4, 4, 0)),
    )
    r = sugeridos(g, "D1", ld.TIPO_CONTRAVENTAMENTO)
    meia = math.dist((0, 0, 0), (4, 4, 0))
    # No plano, travada no cruzamento (metade); fora do plano, a barra inteira: vale o maior.
    assert "no plano" in r.motivo and r.lx_m == r.ly_m == pytest.approx(meia)
    assert f"{meia / 2:.2f}".replace(".", ",") in r.motivo


# ------------------------------------------------------------------ na leitura e nas sugestões
def test_leitura_e_sugestoes_usam_os_travamentos():
    corpos = {
        **sw.CORPOS,
        "Secundaria[1]": ("x", "x", (2000, 4000, 0), (2000, 4000, 3000), "W 310 x 32,7"),
        "Secundaria[2]": ("x", "x", (4000, 4000, 0), (4000, 4000, 3000), "W 310 x 32,7"),
    }
    g = geometria(corpos=corpos)
    dados = importar("PP", "W0")
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, g)}
    assert leituras[VIGA].lb_m == pytest.approx(2.0) and leituras[VIGA].lx_m == pytest.approx(6.0)
    assert ld.comprimentos_em_texto(leituras[VIGA]) == "6,00 / 2,00 / 2,00"
    sugerido, _ = ld.aplicar_sugestoes(dados, list(leituras.values()))
    assert (sugerido.membros[VIGA].lx_m, sugerido.membros[VIGA].lb_m) == (6.0, 2.0)
    # O que já foi escolhido à mão fica.
    escolhido = em.com_membros(dados, {VIGA: em.ConfiguracaoDoMembro(lb_m=1.0)})
    sugerido, _ = ld.aplicar_sugestoes(escolhido, list(leituras.values()))
    assert sugerido.membros[VIGA].lb_m == 1.0
    assert leituras[PILAR].lx_m == pytest.approx(4.0)
    linha = dict(zip(ld.COLUNAS_LEITURA, ld.linhas_da_leitura([leituras[VIGA]])[0], strict=True))
    assert linha["Lx / Ly / Lb (m)"] == "6,00 / 2,00 / 2,00"
    assert "travamentos laterais" in linha["Comprimentos de flambagem"]


def test_sem_esqueleto_nao_ha_sugestao_de_comprimento():
    (leitura, *_) = ld.ler_barras(importar("PP"))
    assert leitura.lx_m is None and ld.comprimentos_em_texto(leitura) == "—"
