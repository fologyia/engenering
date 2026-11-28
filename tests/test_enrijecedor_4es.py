"""Critérios individuais do enrijecedor 4ES; não são aprovação da ligação."""

import math
from dataclasses import replace

import pytest

from core.enrijecedor_4es import EntradaEnrijecedor, verificar


def test_equacoes_do_enrijecedor():
    e = EntradaEnrijecedor(8, 345, 250, 12, 100)
    a, b, pendente = verificar(e)
    assert a.solicitante == pytest.approx(8 * 345 / 250)
    assert b.solicitante == pytest.approx(100 / 12)
    assert b.resistente == pytest.approx(0.56 * math.sqrt(200000 / 250))
    assert pendente.status == "ALERTA"


def test_reprova_dimensoes_insuficientes_e_invalidez():
    e = EntradaEnrijecedor(8, 345, 250, 5, 100)
    assert verificar(e)[0].status == "NÃO OK"
    assert verificar(e)[1].status == "NÃO OK"
    for invalido in (replace(e, fy_enrijecedor=0), replace(e, altura=float("nan"))):
        with pytest.raises(ValueError):
            verificar(invalido)


def test_chapa_4es_casos_da_tabela_6_3():
    from core.enrijecedor_4es import Chapa4ES, verificar_chapa

    # s=50 mm, h1=345 mm e h2=225 mm; pfi é limitado a s.
    e = Chapa4ES(100, 99, 50, 60, 25, 300, 10, 20, 250, 80)
    e = replace(e, largura=10000 / 99)
    caso1 = verificar_chapa(e)
    yp1 = (e.largura / 2) * (225 * (1 / 50 + 1 / 50) + 345 * (1 / 50 + 1 / 50)) + (
        2 / e.gabarito
    ) * (225 * 100 + 345 * 75)
    assert caso1.resistente == pytest.approx(0.9 * 250 * 20**2 * yp1 / 1e6)
    assert "caso 1" in caso1.formula
    caso2 = verificar_chapa(replace(e, borda=60))
    yp2 = (e.largura / 2) * (225 * (1 / 50 + 1 / 50) + 345 * (1 / 50 + 1 / 50)) + (
        2 / e.gabarito
    ) * (225 * 100 + 345 * 100)
    assert caso2.resistente == pytest.approx(0.9 * 250 * 20**2 * yp2 / 1e6)
    assert "caso 2" in caso2.formula


def test_chapa_4es_recusa_fileira_abaixo_da_meia_altura():
    from core.enrijecedor_4es import Chapa4ES, verificar_chapa

    e = Chapa4ES(100, 100, 50, 60, 25, 300, 10, 20, 250, 80)
    with pytest.raises(ValueError):
        verificar_chapa(replace(e, gabarito=100))
    with pytest.raises(ValueError):
        verificar_chapa(replace(e, largura=200, distancia_interna=200))


def test_parafusos_4es_e_condicao_chapa_grossa():
    from core import bolted_connection as bc
    from core.enrijecedor_4es import Chapa4ES, verificar_chapa, verificar_parafusos

    e = Chapa4ES(200, 100, 45, 45, 40, 300, 10, 20, 250, 80)
    tracao, condicao, corte, pendente = verificar_parafusos(e, '3/4"', "A325", 40)
    db = bc.dados_parafuso('3/4"')["d_b"]
    ft = bc.resist_tracao_parafuso(db, "A325", "AISC360_LRFD")
    fv = bc.resist_corte(db, "A325", "AISC360_LRFD", True)
    assert tracao.resistente == pytest.approx(2 * ft * (340 + 240) / 1000)
    assert condicao.solicitante == pytest.approx(1.11 * 80)
    assert condicao.resistente == pytest.approx(verificar_chapa(e).resistente)
    assert corte.resistente == pytest.approx(4 * fv)
    assert pendente.status == "ALERTA"
    with pytest.raises(ValueError):
        verificar_parafusos(e, '3/4"', "A307", 40)


def test_comprimento_minimo_e_desenho_4es():
    from core import cena_3d as c3
    from core.desenho_4es import vista_lateral
    from core.enrijecedor_4es import verificar_comprimento

    limite = 85 / math.tan(math.radians(30))
    assert verificar_comprimento(85, limite).status == "OK"
    assert verificar_comprimento(85, limite - 1).status == "NÃO OK"
    desenho = vista_lateral(85, 160, 25, 12)
    textos = " ".join(i.texto for i in desenho.itens if isinstance(i, c3.Etiqueta2D))
    assert "85 mm" in textos and "160 mm" in textos
    assert "sem recortes" in textos


def test_pilar_reutiliza_apenas_estados_comuns_sem_reforco():
    from core import ligacao_rigida as lr
    from core.enrijecedor_4es import verificar_pilar_sem_continuidade

    e = lr.EntradaRigida()
    grupos = lr.calcular(e).grupos
    esperado = next(g.linhas for g in grupos if g.nome == "Pilar")
    linhas = verificar_pilar_sem_continuidade(e)
    assert [v.nome for v in linhas] == [v.nome for v in esperado]
    assert all(not v.nome.startswith("Chapa:") for v in linhas)
    with pytest.raises(ValueError):
        verificar_pilar_sem_continuidade(replace(e, enrijecedores=True))


def test_contato_chapa_simetrica_cada_fileira():
    from core import bolted_connection as bc
    from core.enrijecedor_4es import Chapa4ES, verificar_contato_chapa_simetrica

    e = Chapa4ES(200, 100, 45, 45, 40, 300, 10, 20, 250, 80)
    db, dh = (bc.dados_parafuso('3/4"')[k] for k in ("d_b", "d_h"))
    externo = bc.resist_contato(db, 20, 400, 40 - dh / 2, "AISC360_LRFD")
    interno = bc.resist_contato(db, 20, 400, 45 + 10 + 45 - dh, "AISC360_LRFD")
    linha = verificar_contato_chapa_simetrica(e, '3/4"', 400, 90)
    assert linha.resistente == pytest.approx(2 * (externo + interno))
    assert linha.solicitante == 90
    with pytest.raises(ValueError):
        verificar_contato_chapa_simetrica(replace(e, borda=5), '3/4"', 400, 90)


def test_contato_pilar_respeita_distancia_ao_extremo():
    from core import bolted_connection as bc
    from core.enrijecedor_4es import Chapa4ES, verificar_contato_pilar

    e = Chapa4ES(200, 100, 45, 45, 40, 300, 10, 20, 250, 80)
    dados = bc.dados_parafuso('3/4"')
    db, dh = dados["d_b"], dados["d_h"]
    esperado = 2 * (
        bc.resist_contato(db, 15, 450, 30 - dh / 2, "AISC360_LRFD")
        + bc.resist_contato(db, 15, 450, 45 + 10 + 45 - dh, "AISC360_LRFD")
    )
    linha = verificar_contato_pilar(e, '3/4"', 15, 450, 30, 100)
    assert linha.resistente == pytest.approx(esperado)
    assert verificar_contato_pilar(e, '3/4"', 15, 450, 100, 100).resistente > linha.resistente
    with pytest.raises(ValueError):
        verificar_contato_pilar(e, '3/4"', 15, 450, 5, 100)


def test_soldas_viga_nao_incluem_aprovacao_do_enrijecedor():
    from core import ligacao_rigida as lr
    from core.enrijecedor_4es import verificar_soldas_viga

    e = lr.EntradaRigida(solda_mesa=lr.PENETRACAO)
    linhas = verificar_soldas_viga(e)
    esperado = next(g.linhas for g in lr.calcular(e).grupos if g.nome == "Soldas da viga na chapa")
    assert [v.nome for v in linhas[:-1]] == [v.nome for v in esperado]
    assert linhas[-1].status == "ALERTA"
    with pytest.raises(ValueError):
        verificar_soldas_viga(replace(e, solda_mesa=lr.FILETE))
