"""Vigas de piso: combinações, flexão, cortante, flecha, critério Anglo e o perfil mais leve."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from components.figuras_estrutura import svg_viga_de_piso
from core import section_catalog as sc
from core import viga_de_piso as vp
from core.project_report import montar_modelo_relatorio
from core.project_store import novo_projeto_documento
from core.technical_records import avaliar_contrato_registro

PADRAO = vp.EntradaVigaDePiso()


def _linha(r: vp.ResultadoVigaDePiso, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def test_exemplo_padrao_confere_com_a_conta_a_mao():
    """W 200 x 15,0, 4 m, faixa de 1 m, piso 0,45 e sobrecarga 5 kN/m² (exemplo do guia)."""
    r = vp.calcular(PADRAO)
    perfil = sc.obter_perfil(PADRAO.perfil)
    pp = perfil.massa_kg_m * vp.G / 1e3
    q_d = 1.25 * pp + 1.35 * 0.45 + 1.5 * 5.0  # PP do aço, piso industrializado, sobrecarga
    assert r.momento_sd_kNm == pytest.approx(q_d * 4.0**2 / 8, rel=1e-6)
    assert r.cortante_sd_kN == pytest.approx(q_d * 4.0 / 2, rel=1e-6)
    # Alma compacta (h/t_w ≈ 44 < λ_p ≈ 59): V_Rd = 0,6·d·t_w·f_y/γ_a1.
    assert r.cortante_rd_kN == pytest.approx(0.6 * 200 * 4.3 * 345 / 1.10 / 1e3, rel=1e-3)
    q_k = pp + 0.45 + 5.0
    assert r.flecha_mm == pytest.approx(5 * q_k * 4000**4 / (384 * 200_000 * perfil.ix_mm4))
    assert r.cb == pytest.approx(vp.cb_biapoiada(q_k, 0.0, 4.0))
    assert r.status == "OK" and r.aproveitamento_maximo == pytest.approx(
        r.momento_sd_kNm / r.momento_rd_kNm
    )
    assert r.reacao_caracteristica_kN == pytest.approx(q_k * 2.0)


@pytest.mark.parametrize(
    ("q", "p", "esperado"),
    [(1.0, 0.0, 12.5 / 11.0), (0.0, 10.0, 12.5 / 9.5), (0.0, 0.0, 1.0)],
)
def test_cb_da_viga_biapoiada(q, p, esperado):
    # Uniforme: M_A = M_C = 0,75·M_máx → 12,5/(2,5 + 2,25 + 4 + 2,25) = 1,136.
    # Concentrada no meio: M_A = M_C = M_máx/2 → 12,5/(2,5 + 1,5 + 4 + 1,5) = 1,316.
    assert vp.cb_biapoiada(q, p, 4.0) == pytest.approx(esperado, rel=1e-6)


def test_mesa_travada_pela_grade_aumenta_o_momento_resistente():
    solta = vp.calcular(PADRAO)
    travada = vp.calcular(replace(PADRAO, lb_m=0.5))
    assert travada.cb == 1.0 and travada.lb_m == 0.5
    assert travada.momento_rd_kNm > solta.momento_rd_kNm


def test_criterio_anglo_flecha_espessura_e_ligacao_minima():
    principal = vp.calcular(replace(PADRAO, anglo=True))
    assert _linha(principal, "Flecha (serviço) ≤ L/350 — viga de piso principal")
    assert _linha(principal, "Anglo: espessura mínima do perfil").status == "NÃO OK"  # alma 4,3
    assert principal.status == "NÃO OK"
    secundaria = vp.calcular(replace(PADRAO, anglo=True, tipo=vp.TIPO_SECUNDARIA))
    assert _linha(secundaria, "Flecha (serviço) ≤ L/300")
    w_rd = 8 * principal.momento_rd_kNm / 4.0
    assert principal.reacao_minima_ligacao_kN == pytest.approx(
        max(0.75 * w_rd / 2, principal.reacao_calculo_kN)
    )
    assert vp.calcular(PADRAO).reacao_minima_ligacao_kN is None
    assert "9.1" in _linha(principal, "Reação de apoio").formula


def test_carga_concentrada_entra_no_momento_na_flecha_e_no_desenho():
    sem = vp.calcular(PADRAO)
    com = vp.calcular(replace(PADRAO, concentrada_kN=10.0))
    assert com.momento_sd_kNm > sem.momento_sd_kNm + 10.0 * 4.0 / 4  # γ > 1 no equipamento
    perfil = sc.obter_perfil(PADRAO.perfil)
    assert com.flecha_mm - sem.flecha_mm == pytest.approx(
        10e3 * 4000**3 / (48 * 200_000 * perfil.ix_mm4)
    )
    assert "P = 10,0 kN" in svg_viga_de_piso(4.0, 5.6, 10.0, com.flecha_mm, 16.0)
    assert "P = " not in svg_viga_de_piso(4.0, 5.6, 0.0, sem.flecha_mm, 11.0)


def test_perfil_mais_leve_da_mesma_familia():
    nome, r = vp.perfil_mais_leve(PADRAO)
    assert nome == PADRAO.perfil and r.status == "OK"
    nome_anglo, r_anglo = vp.perfil_mais_leve(replace(PADRAO, anglo=True))
    assert vp.familia(nome_anglo) == vp.familia(PADRAO.perfil)
    assert r_anglo.status in ("OK", "ALERTA")
    assert sc.obter_perfil(nome_anglo).massa_kg_m > sc.obter_perfil(PADRAO.perfil).massa_kg_m
    impossivel = replace(PADRAO, vao_m=30.0, largura_influencia_m=15.0, sc_kN_m2=100.0)
    assert vp.perfil_mais_leve(impossivel) is None


def test_entrada_invalida_e_recusada():
    ruim = replace(PADRAO, perfil="X 1", vao_m=0.1, sc_kN_m2=-1.0, lb_m=9.0)
    erros = " ".join(vp.validar(ruim))
    for trecho in ("Perfil fora do catálogo", "vão", "sobrecarga", "sem travamento"):
        assert trecho in erros, trecho
    with pytest.raises(vp.VigaInvalida):
        vp.calcular(ruim)


def test_registro_e_capitulo_do_memorial():
    r = vp.calcular(replace(PADRAO, anglo=True, perfil="W 250 x 17,9"))
    registro = vp.registro_viga(r)
    assert avaliar_contrato_registro(registro)["valido"]
    json.dumps(registro)
    assert registro["modulo_id"] == vp.MODULO_ID
    projeto = novo_projeto_documento("Plataforma", codigo="MC-01")
    projeto["registros_tecnicos"] = [registro]
    modelo = json.dumps(montar_modelo_relatorio(projeto), ensure_ascii=False)
    assert "Largura de influência" in modelo or "largura" in modelo.lower()
    assert "W 250 x 17,9" in modelo
