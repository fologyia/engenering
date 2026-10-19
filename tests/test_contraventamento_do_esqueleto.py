"""O contraventamento lido do esqueleto: pilares (só os que chegam ao piso), vãos e medidas entre
eixos, cotas, área de piso pelas chapas, diagonais em X e em Y (mão-francesa e longarina não
contam), tipo (X, V invertido, simples), barras sobrepostas, direção sem contraventamento e a
conferência com a página."""

from __future__ import annotations

import pytest

from core import contraventamento_do_esqueleto as cesq
from core import contraventamento_plataforma as cp
from core import leitura_do_modelo as ld
from tests.test_guarda_corpo_do_modelo import LINHA, barra, plataforma

# Modelo com Y vertical: planta (x, −z, y). Plataforma 6 × 4 m, pilares nos cantos.


def com_x_nas_bordas():
    corpos = plataforma()
    for z in (0.0, 4.0):  # duas linhas paralelas a X (z = 0 e 4 → y = 0 e −4 na planta)
        corpos.append(barra(f"Diag A z{z:g}", (0, 0, z), (6, LINHA, z)))
        corpos.append(barra(f"Diag B z{z:g}", (6, 0, z), (0, LINHA, z)))
    return corpos


def ler(corpos):
    return cesq.ler_esqueleto(ld.GeometriaDoModelo(corpos=tuple(corpos)), "Y")


def test_planta_vaos_cotas_area_e_perfis():
    e = ler(com_x_nas_bordas())
    assert (e.lx_m, e.ly_m, e.vaos_x, e.vaos_y) == (6.0, 4.0, 1, 1)
    assert e.cotas_m == (round(LINHA, 2),)
    assert e.area_de_piso_m2 == pytest.approx(24.0)
    assert e.pilar == e.viga == 'U 8" x 17,10'
    assert len(e.pilares) == 4


def test_x_em_duas_linhas_e_aviso_sem_contraventamento_em_y():
    e = ler(com_x_nas_bordas())
    s = e.sistema("X")
    assert s is not None and (s.tipo, s.linhas, s.paineis_por_linha) == (cp.TIPO_X_TRACAO, 2, 1)
    assert e.sistema("Y") is None
    assert any(a.startswith("Sem contraventamento em Y") for a in e.avisos)
    assert any("Diagonais em X" in a for a in e.avisos)  # U não é família de diagonal da página


def test_v_invertido_e_diagonal_simples():
    corpos = plataforma()
    corpos += [barra("V1", (0, 0, 0), (3, LINHA, 0)), barra("V2", (6, 0, 0), (3, LINHA, 0))]
    corpos += [barra("S", (0, 0, 0), (0, LINHA, 4))]
    e = ler(corpos)
    assert e.sistema("X").tipo == cp.TIPO_V_INVERTIDO
    assert e.sistema("Y").tipo == cp.TIPO_DIAGONAL_SIMPLES


def test_mao_francesa_longarina_e_poste_nao_contam():
    corpos = plataforma()
    corpos.append(barra("Mão", (0, LINHA - 0.8, 0), (0.8, LINHA, 0)))  # curta, no topo do pilar
    corpos.append(barra("Longarina", (8, 0, 1), (6.2, LINHA, 1)))  # não sai de pilar
    corpos.append(barra("Poste", (9, 0, 1), (9, 1.8, 1)))  # patamar: não chega ao piso
    e = ler(corpos)
    assert not e.sistemas and e.maos_francesas == 1
    assert "Poste" not in e.pilares
    assert any("Poste" in a and "não conta como pilar" in a for a in e.avisos)


def test_barras_sobrepostas_contam_uma_vez_com_aviso():
    corpos = com_x_nas_bordas()
    corpos.append(barra("Diag A z0 (cópia)", (0.03, 0, 0.02), (6.0, LINHA - 0.02, 0.0)))
    e = ler(corpos)
    assert e.sistema("X").linhas == 2
    assert any("estão no mesmo lugar" in a for a in e.avisos)


def test_pilares_numa_linha_so_avisam_do_balanco():
    corpos = [c for c in plataforma() if c.nome not in ("Pilar 2", "Pilar 4")]  # só em x = 0
    e = ler(corpos)
    assert e.vaos_x == 1 and e.lx_m == pytest.approx(6.0)  # a medida do piso
    assert any("numa linha só na direção X" in a for a in e.avisos)


def test_conferir_com_a_pagina():
    e = ler(com_x_nas_bordas())
    pagina = cp.EntradaContraventamento()  # 12 × 6 m, 2 × 1 vãos, piso a 4 m
    diferencas = cesq.conferir_com_a_pagina(e, pagina)
    assert any(d.startswith("L_x × L_y") for d in diferencas)
    assert any(d.startswith("vãos") for d in diferencas)
    igual = cp.EntradaContraventamento(
        comprimento_x_m=6.0, largura_y_m=4.0, cotas_m=e.cotas_m, vaos_x=1, vaos_y=1,
        contraventamento_x=cp.SistemaDeContraventamento(cp.TIPO_X_TRACAO, linhas=2),
    )  # fmt: skip
    assert cesq.conferir_com_a_pagina(e, igual) == []


def test_area_de_piso_entra_no_peso():
    a = cp.calcular(cp.EntradaContraventamento())
    b = cp.calcular(cp.EntradaContraventamento(area_de_piso_m2=36.0))  # metade de 12 × 6
    pa = next(x for x in a.acoes if x.nome == "Sobrecarga").valor("P_1")
    pb = next(x for x in b.acoes if x.nome == "Sobrecarga").valor("P_1")
    assert pb == pytest.approx(pa / 2)
    assert any("área de piso" in m for m in cp.validar_entrada(
        cp.EntradaContraventamento(area_de_piso_m2=-1.0)))  # fmt: skip


def test_sem_barras_e_none():
    assert cesq.ler_esqueleto(ld.GeometriaDoModelo(), "Y") is None
