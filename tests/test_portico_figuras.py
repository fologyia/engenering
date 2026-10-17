"""Figuras do pórtico plano (estilo Ftool): imagens válidas e os valores escritos certos."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core import portico_figuras as pf
from core import portico_plano as pp

SECAO = pp.Secao("teste", area_m2=1e-2, inercia_m4=1e-5, modulo_w_m3=1e-4)


def biapoiada(*, distribuidas=(), pontuais=()):
    return pp.resolver(
        pp.Portico(
            nos=(pp.No("A", 0, 0), pp.No("B", 6.0, 0)),
            barras=(pp.Barra("V1", "A", "B", SECAO),),
            apoios=(pp.pino("A"), pp.rolete("B")),
            cargas_distribuidas=tuple(distribuidas),
            cargas_pontuais=tuple(pontuais),
        )
    )


def dobrada():
    """Longarina com trecho horizontal no topo, pino nas duas pontas."""
    return pp.resolver(
        pp.Portico(
            nos=(pp.No("A", 0, 0), pp.No("B", 3.0, 2.0), pp.No("C", 3.3, 2.0)),
            barras=(pp.Barra("L1", "A", "B", SECAO), pp.Barra("L2", "B", "C", SECAO)),
            apoios=(pp.pino("A"), pp.pino("C")),
            cargas_distribuidas=(
                pp.CargaDistribuida("L1", -4.0, direcao=pp.GLOBAL_Y_PROJETADA),
                pp.CargaDistribuida("L2", -4.0),
            ),
        )
    )


def portico_completo():
    """Engaste, rótula, carga nodal com momento, carga horizontal e concentrada local."""
    return pp.resolver(
        pp.Portico(
            nos=(pp.No("A", 0, 0), pp.No("B", 0, 3), pp.No("C", 2.5, 3), pp.No("D", 5, 3)),
            barras=(
                pp.Barra("P1", "A", "B", SECAO),
                pp.Barra("V1", "B", "C", SECAO),
                pp.Barra("V2", "C", "D", SECAO, rotula_i=True),
            ),
            apoios=(pp.engaste("A"), pp.rolete("D")),
            cargas_nodais=(pp.CargaNodal("B", fx=2.0, mz=3.0),),
            cargas_distribuidas=(
                pp.CargaDistribuida("P1", 1.5, direcao=pp.GLOBAL_X),
                pp.CargaDistribuida("V2", -2.0, -4.0),
            ),
            cargas_pontuais=(pp.CargaPontual("V1", 1.0, fy=-5.0, local=True),),
        )
    )


def _png(figura):
    imagem = Image.open(io.BytesIO(figura.png))
    assert imagem.format == "PNG"
    assert imagem.size == (figura.largura_px, figura.altura_px)
    return imagem


def test_numero_em_portugues():
    assert pf.numero(1234.5) == "1.234,50"
    assert pf.numero(-3.456) == "-3,46"
    assert pf.numero(-0.001) == "0,00"
    assert pf.numero(150.0, 0) == "150"


@pytest.mark.parametrize("fabrica", [biapoiada, dobrada, portico_completo])
def test_todas_as_figuras_saem_como_png(fabrica):
    r = fabrica()
    figuras = pf.figuras_do_portico(r, prefixo="Longarina")
    assert [f.titulo.split(" — ")[1].split(" (")[0] for f in figuras] == [
        "Modelo: geometria, apoios e cargas",
        "Reações de apoio",
        "Esforço normal N",
        "Esforço cortante V",
        "Momento fletor M",
        "Tensão normal |N|/A + |M|/W",
        "Deformada",
    ]
    for figura in figuras:
        imagem = _png(figura)
        assert imagem.size[0] == 1000 and 280 <= imagem.size[1] <= 620
        assert figura.legenda


def test_sem_modulo_resistente_nao_ha_figura_de_tensao():
    secao = pp.Secao("sem W", 1e-2, 1e-5)
    r = pp.resolver(
        pp.Portico(
            nos=(pp.No("A", 0, 0), pp.No("B", 4, 0)),
            barras=(pp.Barra("V1", "A", "B", secao),),
            apoios=(pp.pino("A"), pp.rolete("B")),
            cargas_distribuidas=(pp.CargaDistribuida("V1", -1.0),),
        )
    )
    assert len(pf.figuras_do_portico(r)) == 6


def test_desenho_reprodutivel():
    a = pf.figura_diagrama(dobrada(), "M").png
    b = pf.figura_diagrama(dobrada(), "M").png
    assert a == b


def test_momento_do_lado_tracionado_e_valores():
    r = biapoiada(distribuidas=[pp.CargaDistribuida("V1", -10.0)])
    [(nome, eixo, curva)] = pf.curvas_do_diagrama(r, "M")
    meio = len(curva) // 2
    assert nome == "V1" and curva[meio][1] < eixo[meio][1]  # M > 0 desenhado embaixo
    rotulos = pf.rotulos_do_diagrama(r, "M")
    assert [rot.texto for rot in rotulos] == ["45,00"]  # pontas com M = 0 não são escritas
    assert rotulos[0].x == pytest.approx(3.0)
    cortante = [rot.texto for rot in pf.rotulos_do_diagrama(r, "V")]
    assert cortante == ["30,00", "-30,00"]


def test_salto_do_cortante_na_carga_concentrada():
    r = biapoiada(pontuais=[pp.CargaPontual("V1", 2.0, fy=-12.0)])
    textos = [rot.texto for rot in pf.rotulos_do_diagrama(r, "V")]
    assert textos == ["8,00", "8,00", "-4,00", "-4,00"]  # pontas e os dois lados do salto
    assert "16,00" in [rot.texto for rot in pf.rotulos_do_diagrama(r, "M")]


def test_mesmo_valor_no_no_comum_aparece_uma_vez():
    r = dobrada()
    m_no_b = r.barra("L1").pontos[-1].m
    texto = pf.numero(m_no_b)
    rotulos = pf.rotulos_do_diagrama(r, "M")
    assert [rot.texto for rot in rotulos].count(texto) == 1


def test_tensao_sempre_positiva_e_legendas():
    r = dobrada()
    assert all(not rot.texto.startswith("-") for rot in pf.rotulos_do_diagrama(r, "tensao"))
    reacoes = pf.legenda_das_reacoes(r)
    assert "A: Rx = " in reacoes and "C: Rx = " in reacoes
    assert "L1:" in pf.legenda_do_diagrama(r, "M") and "kN·m" in pf.legenda_do_diagrama(r, "M")
    assert "flecha" in pf.legenda_da_deformada(r) and "L/" in pf.legenda_da_deformada(r)


def test_fator_da_deformada_e_numero_redondo():
    fator = pf.fator_da_deformada(dobrada())
    texto = f"{fator:.0e}"
    assert texto[0] in "125"
    sem_carga = biapoiada()
    assert pf.fator_da_deformada(sem_carga) == 0.0
    _png(pf.figura_deformada(sem_carga))
