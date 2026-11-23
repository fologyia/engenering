"""Forças localizadas na alma (NBR 8800:2025, 5.7): contas de mão, enrijecedores e a página."""

from __future__ import annotations

import math

import pytest

from components.forcas_localizadas_help import AJUDA
from core import forcas_localizadas as fl
from core import perfil_i as pi
from tests import apoio_paginas as ap

PAGINA = "app_pages/forcas_localizadas.py"
P = fl.EntradaForcas()
W410 = pi.perfil("W 410 x 46,1")
FY = 345.0


def linha(r: fl.ResultadoForcas, forca: int, nome: str):
    return next(v for v in r.forcas[forca].linhas if v.nome == nome)


def test_perfil_do_catalogo_tem_raio_e_k():
    assert (W410.d, W410.bf, W410.tf, W410.tw) == (403.0, 140.0, 11.2, 7.0)
    assert W410.raio == pytest.approx(12.0) and W410.k == pytest.approx(23.2)
    assert W410.h == pytest.approx(403 - 2 * 11.2 - 24)


def test_escoamento_local_e_enrugamento_na_ponta_conta_de_mao():
    r = fl.calcular(P)
    # 5.7.3.2 b): 1,10·(2,5·23,2 + 100)·345·7/1,10
    assert linha(r, 0, "Escoamento local da alma").resistente == pytest.approx(
        1.10 * (2.5 * 23.2 + 100) * 345 * 7 / 1.10 / 1000
    )
    # 5.7.4.2 b), ℓn/d = 100/403 > 0,2
    esperado = (
        0.33 * 7**2 / 1.10 * (1 + (4 * 100 / 403 - 0.2) * (7 / 11.2) ** 1.5)
        * math.sqrt(200_000 * 345 * 11.2 / 7) / 1000
    )  # fmt: skip
    assert linha(r, 0, "Enrugamento da alma").resistente == pytest.approx(esperado)
    assert esperado == pytest.approx(214.9, abs=0.1)


def test_no_vao_usa_5k_e_066_e_flambagem_dispensada_pela_esbeltez():
    r = fl.calcular(P)
    assert linha(r, 1, "Escoamento local da alma").resistente == pytest.approx(
        (5 * 23.2 + 150) * 345 * 7 / 1000
    )
    assert linha(r, 1, "Enrugamento da alma").referencia.endswith("5.7.4.2 a)")
    fl_alma = linha(r, 1, "Flambagem lateral da alma")
    assert fl_alma.status == "N/A" and "5.7.5.3" in fl_alma.referencia
    assert r.situacao == "ATENDE"


def test_flambagem_lateral_da_alma_com_rotacao_impedida():
    e = fl.com(P, comprimento_destravado=6000.0)
    r = fl.calcular(e)
    v = linha(r, 1, "Flambagem lateral da alma")
    rel = (W410.h / 7) / (6000 / 140)
    Cr = 32 * 200_000  # M_Sd = 180 kN·m < M_r = W·f_y
    assert pi.mr_x(W410, FY) > 180e6
    esperado = Cr * 7**3 * 11.2 / (1.10 * W410.h**2) * (0.94 + 0.37 * rel**3) / 1000
    assert v.resistente == pytest.approx(esperado)


def test_flambagem_lateral_sem_rotacao_impedida_e_cr_16e():
    f = fl.ForcaLocalizada("Carga", 60.0, fl.COMPRESSAO, 100, 100, 3000, True, 300.0)
    e = fl.com(P, forcas=(f,), comprimento_destravado=8000.0, rotacao_impedida=False)
    v = linha(fl.calcular(e), 0, "Flambagem lateral da alma")
    rel = (W410.h / 7) / (8000 / 140)
    assert pi.mr_x(W410, FY) < 300e6
    assert v.resistente == pytest.approx(
        16 * 200_000 * 7**3 * 11.2 / (1.10 * W410.h**2) * 0.37 * rel**3 / 1000
    )


def test_deslocamento_lateral_impedido_dispensa_5_7_5():
    e = fl.com(P, comprimento_destravado=6000.0, deslocamento_lateral_impedido=True)
    v = linha(fl.calcular(e), 1, "Flambagem lateral da alma")
    assert v.status == "N/A" and "5.7.5.1" in v.referencia


def test_tracao_flexao_local_da_mesa_e_dispensa_pela_largura():
    f = fl.ForcaLocalizada("Tirante", 100.0, fl.TRACAO, 50, 80, 2000)
    r = fl.calcular(fl.com(P, forcas=(f,)))
    v = linha(r, 0, "Flexão local da mesa")
    assert v.resistente == pytest.approx(6.25 * 11.2**2 * 345 / 1.10 / 1000)
    assert not any(x.nome == "Enrugamento da alma" for x in r.forcas[0].linhas)
    perto = fl.com(P, forcas=(fl.ForcaLocalizada("T", 100.0, fl.TRACAO, 50, 80, 50),))
    assert linha(fl.calcular(perto), 0, "Flexão local da mesa").resistente == pytest.approx(
        v.resistente / 2
    )
    estreita = fl.com(P, forcas=(fl.ForcaLocalizada("T", 100.0, fl.TRACAO, 50, 15, 2000),))
    assert linha(fl.calcular(estreita), 0, "Flexão local da mesa").status == "N/A"


def test_par_de_forcas_instabilidade_por_compressao():
    f = fl.ForcaLocalizada("Vigas dos dois lados", 200.0, fl.PAR, 12.5, 140, 1500)
    r = fl.calcular(fl.com(P, forcas=(f,)))
    v = linha(r, 0, "Instabilidade da alma por compressão")
    assert v.resistente == pytest.approx(
        24 * 7**3 * math.sqrt(200_000 * 345) / (1.10 * W410.h) / 1000
    )


def test_sem_enrijecedor_reprova_e_sugere_medidas():
    f = fl.ForcaLocalizada("Reação", 400.0, fl.COMPRESSAO, 100, 100, 0)
    r = fl.calcular(fl.com(P, forcas=(f,)))
    assert r.situacao == "NÃO ATENDE"
    aviso = linha(r, 0, "Enrijecedores necessários")
    assert aviso.status == "NÃO OK" and "45 × 6,3" in aviso.formula


def test_com_enrijecedor_a_alma_vira_informativa_e_o_enrijecedor_e_verificado():
    f = fl.ForcaLocalizada("Reação", 400.0, fl.COMPRESSAO, 100, 100, 0)
    r = fl.calcular(fl.com(P, forcas=(f,), usar_enrijecedor=True))
    assert linha(r, 0, "Enrugamento da alma").status == "INFO"
    enr = {v.nome: v for v in r.forcas[0].enrijecedor}
    barra = enr["Enrijecedor como barra comprimida"]
    # 2 × 80 × 9,5 + 12·7 × 7; I = 9,5·(2·80 + 7)³/12 + (84 − 9,5)·7³/12
    A = 2 * 80 * 9.5 + 84 * 7
    inercia = 9.5 * 167**3 / 12 + (84 - 9.5) * 7**3 / 12
    lam0 = 0.75 * W410.h / math.sqrt(inercia / A) / math.pi * math.sqrt(250 / 200_000)
    assert barra.resistente == pytest.approx(0.658 ** (lam0**2) * A * 250 / 1.10 / 1000)
    assert barra.solicitante == 400.0  # força total da seção
    menor = linha(r, 0, "Enrugamento da alma").resistente
    assert enr["Esmagamento da ponta ajustada"].solicitante == pytest.approx(400 - menor)
    assert enr["Esmagamento da ponta ajustada"].resistente == pytest.approx(
        1.8 * 2 * 60 * 9.5 * 250 / 1.35 / 1000
    )
    assert r.situacao == "ATENDE"


def test_proporcoes_do_enrijecedor_5_7_9_5():
    f = fl.ForcaLocalizada("Reação", 400.0, fl.COMPRESSAO, 100, 100, 0)
    fino = fl.Enrijecedor(bs=40.0, ts=4.0, corte=10.0)
    r = fl.calcular(fl.com(P, forcas=(f,), usar_enrijecedor=True, enrijecedor=fino))
    enr = {v.nome: v for v in r.forcas[0].enrijecedor}
    assert enr["Largura do enrijecedor"].status == "NÃO OK"  # 40 + 3,5 < 140/3
    assert enr["Espessura do enrijecedor"].status == "NÃO OK"  # 4 < 11,2/2


def test_extremidade_livre_exige_enrijecedor_de_altura_total():
    r = fl.calcular(fl.com(P, extremidade_livre=True))
    assert r.gerais[0].status == "NÃO OK"
    r = fl.calcular(fl.com(P, extremidade_livre=True, usar_enrijecedor=True))
    assert r.gerais[0].status == "OK"


def test_i_laminado_sem_raio_usa_k_tf_e_avisa():
    p = pi.perfil(pi.nomes(pi.FAMILIA_I)[3])
    assert p.k == p.tf and p.h == p.d - 2 * p.tf
    assert pi.avisos_do_perfil(p)


def test_perfil_soldado_propriedades():
    p = pi.soldado(500, 200, 12.5, 6.3, 5.0)
    assert p.A == pytest.approx(2 * 200 * 12.5 + 475 * 6.3)
    assert p.Ix == pytest.approx((200 * 500**3 - (200 - 6.3) * 475**3) / 12)
    assert p.k == pytest.approx(17.5) and p.h == pytest.approx(475)


def test_validacao_e_tabela():
    assert fl.validar(fl.com(P, forcas=()))
    assert fl.validar(fl.com(P, familia=pi.FAMILIA_SOLDADO, tf=300.0))
    tabela = fl.tabela_das_forcas(P.forcas)
    assert fl.forcas_de_tabela(tabela) == P.forcas
    assert fl.forcas_de_tabela([{"F_Sd (kN)": None, "Tipo": "x"}])[0].tipo == fl.COMPRESSAO


def test_registro_e_memorial():
    f = fl.ForcaLocalizada("Reação", 400.0, fl.COMPRESSAO, 100, 100, 0)
    r = fl.calcular(fl.com(P, forcas=(f,), usar_enrijecedor=True))
    reg = fl.registro(r)
    ap.conferir_registro_e_memorial(reg, fl.MODULO_ID)
    ap.conferir_entradas_curadas(reg, fl.MODULO_ID)
    assert [g["nome"] for g in reg["resultados"]["grupos"]] == [
        "Força: Reação",
        "Enrijecedores: Reação",
    ]


def test_textos_de_ajuda():
    ap.conferir_textos_de_ajuda(PAGINA, AJUDA)


def test_pagina(banco_isolado):
    t = ap.abrir(PAGINA, fl_usar_enrijecedor=True)
    assert not ap.sem_ajuda(t), ap.sem_ajuda(t)
    assert ap.metricas(t)["Situação"] == "ATENDE"
    t = ap.abrir(PAGINA, fl_familia=pi.FAMILIA_SOLDADO)
    assert not ap.sem_ajuda(t)
    assert {b.label for b in t.get("download_button")} >= {
        "Baixar o memorial (Word)",
        "Baixar o memorial (PDF)",
    }
