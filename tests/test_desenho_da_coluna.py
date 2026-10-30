"""A coluna em pé na Flambagem de colunas (pedido de 30/10/2026: "uma visão frontal para
identificar o perfil em pé e também a mão francesa que pode chegar nele").

As arestas das vistas saem da forma da seção — vistas (cheias) ou escondidas atrás do aço
(tracejadas) —, sem espelhar o perfil; cada vista tem o apoio e os travamentos do seu plano e a
mão-francesa aparece no plano em que age.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core import column_buckling as cb
from core import desenho_da_coluna as dc
from core import desenho_da_secao as ds
from core import section_catalog as sc

I_300 = cb.secao_por_dimensoes("I", soldado=True, d=300.0, bf=150.0, tf=12.5, tw=8.0)
U_152 = cb.secao_por_dimensoes("U", d=152.4, bf=48.8, tf=8.71, tw=5.08)
TUBO = cb.secao_por_dimensoes("tubo_retangular", B=100.0, H=150.0, t=5.0)


def _arestas(secao, horizontal):
    return {round(a.posicao, 2): a.vista for a in dc.arestas_na_vista(ds.forma_da_secao(secao), horizontal)}  # fmt: skip


def test_i_de_frente_mostra_a_mesa_e_esconde_a_alma():
    arestas = _arestas(I_300, "x")
    assert arestas == {-75.0: True, -4.0: False, 4.0: False, 75.0: True}


def test_i_de_lado_mostra_as_faces_internas_das_mesas():
    arestas = _arestas(I_300, "y")
    assert arestas == {-150.0: True, -137.5: True, 137.5: True, 150.0: True}


def test_u_visto_pelo_dorso_da_alma_esconde_as_mesas():
    arestas = _arestas(U_152, "y")  # de lado, olhando o dorso da alma
    assert arestas[-76.2] and arestas[76.2]
    internas = [v for u, v in arestas.items() if abs(u) < 76.2 - 1e-6]
    assert internas and not any(internas)


def test_tubo_tem_as_paredes_internas_escondidas():
    arestas = _arestas(TUBO, "x")
    assert arestas == {-50.0: True, -45.0: False, 45.0: False, 50.0: True}


def test_vista_lateral_nao_espelha_o_perfil():
    # T com a mesa em +y: olhando de x negativo, a direita de quem olha é o y negativo
    t = cb.secao_de_perfil(
        sc.obter_perfil(
            next(n for n in sc.listar_perfis() if sc.obter_perfil(n).familia.startswith("T "))
        )
    )
    forma = ds.forma_da_secao(t)
    topo_da_mesa = max(y for c in forma.cheios for _, y in c)
    assert dc.na_vista("y", 0.0, topo_da_mesa)[0] == pytest.approx(-topo_da_mesa)
    posicoes = [a.posicao for a in dc.arestas_na_vista(forma, "y")]
    assert posicoes[0] == pytest.approx(-topo_da_mesa, abs=1e-3)  # a mesa fica à esquerda


@pytest.mark.parametrize("apoio", [*dc.APOIOS_NAS_PONTAS, "Informar K"])
@pytest.mark.parametrize("secao", [I_300, U_152, TUBO, cb.secao_direta(1000.0, 15.0, 10.0)])
def test_toda_combinacao_de_apoio_e_secao_sai_desenhada(apoio, secao):
    coluna = dc.ColunaEmPe(secao, 3000.0, 1500.0, 3000.0, 1.0, 1.0, apoio, apoio)
    desenho = dc.figura_da_coluna(coluna)
    imagem = Image.open(io.BytesIO(desenho.png))
    assert imagem.format == "PNG" and imagem.size == (desenho.largura_px, desenho.altura_px)
    assert secao.nome in desenho.titulo


@pytest.mark.parametrize("eixo", ["x", "y"])
def test_mao_francesa_entra_no_plano_em_que_age(eixo):
    mf = dc.MaoFrancesaNoDesenho(28.0, 45.0, 2200.0, eixo, 125.0)
    com = dc.figura_da_coluna(
        dc.ColunaEmPe(I_300, 3000.0, 3000.0, 3000.0, 1.0, 1.0, "Biapoiada (pino-pino)",
                      "Biapoiada (pino-pino)", mf)
    )  # fmt: skip
    sem = dc.figura_da_coluna(
        dc.ColunaEmPe(I_300, 3000.0, 3000.0, 3000.0, 1.0, 1.0, "Biapoiada (pino-pino)",
                      "Biapoiada (pino-pino)")
    )  # fmt: skip
    assert com.png != sem.png
    assert "mão-francesa a 2200 mm da base" in com.legenda
    assert "mão-francesa" not in sem.legenda
    # a mão-francesa só aparece numa das vistas: a do plano dela
    imagem_com = Image.open(io.BytesIO(com.png)).convert("RGB")
    imagem_sem = Image.open(io.BytesIO(sem.png)).convert("RGB")
    meio = imagem_com.width * 345 // 980  # a divisa entre as duas vistas
    esquerda = (
        imagem_com.crop((0, 150, meio, 560)).tobytes()
        != imagem_sem.crop((0, 150, meio, 560)).tobytes()
    )
    direita = (
        imagem_com.crop((meio, 150, 640, 560)).tobytes()
        != imagem_sem.crop((meio, 150, 640, 560)).tobytes()
    )
    assert (esquerda, direita) == ((False, True) if eixo == "x" else (True, False))
