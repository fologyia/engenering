"""Solda de filete sob carga excêntrica e carga de impacto, contra as contas de mão."""

from __future__ import annotations

import math

import pytest

from core import elementos_catalogo as cat
from core import elementos_impacto as ei
from core import elementos_soldas as es
from core.elementos_base import calcular_caso

B, D = 100.0, 150.0


def rodar(caso_id: str, **valores):
    return calcular_caso(cat.CASOS[caso_id], valores)


def linha(resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


def metrica(resultado, rotulo: str):
    return next(m.valor for m in resultado.metricas if m.rotulo == rotulo)


# Shigley, Tabelas 9-1 e 9-2: J_u e I_u fechados de cada desenho.
@pytest.mark.parametrize(
    ("padrao", "j_u", "i_u"),
    [
        (es.UM_VERTICAL, D**3 / 12, D**3 / 12),
        (es.DOIS_VERTICAIS, D * (3 * B * B + D * D) / 6, D**3 / 6),
        (es.DOIS_HORIZONTAIS, B * (B * B + 3 * D * D) / 6, B * D * D / 2),
        (es.EM_C, (8 * B**3 + 6 * B * D * D + D**3) / 12 - B**4 / (2 * B + D), None),
        (es.EM_L, ((B + D) ** 4 - 6 * B * B * D * D) / (12 * (B + D)), None),
        (es.RETANGULO, (B + D) ** 3 / 6, D * D * (3 * B + D) / 6),
    ],
)
def test_propriedades_batem_com_a_tabela_de_shigley(padrao, j_u, i_u):
    prop = es.propriedades(es.trechos_do_padrao({"padrao": padrao, "b_mm": B, "d_mm": D}))
    assert prop.j_u == pytest.approx(j_u, rel=1e-9)
    if i_u is not None:
        assert prop.i_ux == pytest.approx(i_u, rel=1e-9)


def test_anel_fica_perto_do_circulo():
    raio = 50.0
    prop = es.propriedades(
        es.trechos_do_padrao({"padrao": es.ANEL, "b_mm": B, "d_mm": D, "d_anel_mm": 2 * raio})
    )
    assert prop.j_u == pytest.approx(2 * math.pi * raio**3, rel=2e-3)
    assert prop.comprimento == pytest.approx(2 * math.pi * raio, rel=1e-3)


def test_console_em_c_a_mao():
    # b = 75, d = 150: x̄ = b²/(2b + d) = 18,75 mm; canto de cima à direita: r = (56,25; 75).
    r = rodar("solda_filete")
    j_u = (8 * 75**3 + 6 * 75 * 150**2 + 150**3) / 12 - 75**4 / 300
    fx = 6e6 * 75 / j_u
    fy = -40_000 / 300 - 6e6 * 56.25 / j_u
    esperado = math.hypot(fx, fy)
    assert metrica(r, "Força no ponto crítico") == pytest.approx(esperado, rel=1e-6)
    assert esperado == pytest.approx(523.4, abs=0.1)
    # NBR 8800: 0,60·485·(0,707·8)/1,35
    assert linha(r, "Metal da solda no ponto mais carregado").resistente == pytest.approx(
        0.60 * 485 * 0.707 * 8 / 1.35
    )


def test_aisc_asd_usa_030_fexx_na_garganta():
    r = rodar("solda_filete", criterio=es.ASD)
    assert linha(r, "Metal da solda no ponto mais carregado").resistente == pytest.approx(
        0.30 * 485 * 0.707 * 8
    )
    # Metal-base: min(0,40·S_y; 0,30·S_ut)·t = min(100; 120)·12,5
    assert linha(r, "Metal-base junto à solda (cisalhamento)").resistente == pytest.approx(1250.0)


def test_flexao_fora_do_plano_devolve_as_cargas():
    """No L os eixos não são principais: a força por mm precisa refazer N, Mx e My."""
    trechos = es.trechos_do_padrao({"padrao": es.EM_L, "b_mm": 80.0, "d_mm": 200.0})
    prop = es.propriedades(trechos)
    n, mx, my = 10_000.0, 3e6, -1e6
    a, b = es._coeficientes_da_flexao(prop, trechos, mx, my)
    soma_n = soma_mx = soma_my = 0.0
    passos = 2000
    for t in trechos:
        for i in range(passos):
            s = (i + 0.5) / passos
            x = t.x1 + s * (t.x2 - t.x1) - prop.xc
            y = t.y1 + s * (t.y2 - t.y1) - prop.yc
            f = n / prop.comprimento + a * y + b * x
            ds = t.comprimento / passos
            soma_n += f * ds
            soma_mx += f * y * ds
            soma_my += f * x * ds
    assert soma_n == pytest.approx(n, rel=1e-6)
    assert soma_mx == pytest.approx(mx, rel=1e-4)
    assert soma_my == pytest.approx(my, rel=1e-4)


def test_cordao_unico_nao_resiste_ao_momento_em_torno_dele():
    with pytest.raises(ValueError, match="reta só"):
        rodar("solda_filete", padrao=es.UM_VERTICAL, my_kNm=1.0, vy_kN=0.0, t_kNm=0.0)
    # Em torno do eixo x ele dobra e resiste: f = M·c/I_u = 1e6·75/(150³/12).
    r = rodar("solda_filete", padrao=es.UM_VERTICAL, mx_kNm=1.0, vy_kN=0.0, t_kNm=0.0)
    assert metrica(r, "Força no ponto crítico") == pytest.approx(1e6 * 75 / (150**3 / 12))


def test_cordao_curto_usa_perna_de_um_quarto_do_comprimento():
    r = rodar("solda_filete", b_mm=24.0, perna_mm=8.0, t_kNm=0.0, vy_kN=-5.0)
    assert any("L/4" in a for a in r.alertas)
    assert linha(r, "Metal da solda no ponto mais carregado").resistente == pytest.approx(
        0.60 * 485 * 0.707 * 6 / 1.35
    )
    assert linha(r, "Solda: comprimento do menor cordão").status == "NÃO OK"


def test_perna_abaixo_da_minima_reprova():
    r = rodar("solda_filete", perna_mm=4.0, t_mm=16.0)
    assert linha(r, "Solda: perna mínima").status == "NÃO OK"


def test_sem_carga_vira_mensagem():
    with pytest.raises(ValueError, match="força ou um momento"):
        rodar("solda_filete", vy_kN=0.0, t_kNm=0.0)


# ---------------------------------------------------------------------------
# Impacto
# ---------------------------------------------------------------------------


def test_queda_sobre_viga_biapoiada_a_mao():
    r = rodar("impacto", altura_mm=50.0)
    k = 48 * 200e3 * 26e6 / 2000**3
    estatica = 2000 / k
    maxima = estatica * (1 + math.sqrt(1 + 2 * 50 / estatica))
    assert metrica(r, "Rigidez k") == pytest.approx(k)
    assert metrica(r, "Deslocamento máximo") == pytest.approx(maxima)
    assert metrica(r, "Força máxima") == pytest.approx(k * maxima / 1000)
    assert metrica(r, "Tensão máxima") == pytest.approx(k * maxima * 2000 / 4 / 252e3)


def test_peso_solto_de_repente_dobra_o_efeito():
    r = rodar("impacto", altura_mm=0.0)
    assert metrica(r, "Fator de impacto n") == pytest.approx(2.0)
    assert any("n = 2" in a for a in r.alertas)


def test_batida_horizontal_conserva_a_energia():
    r = rodar("impacto", peca=ei.MOLA, modo=ei.BATIDA, velocidade_m_s=1.5, k_N_mm=800.0)
    massa = 2000 / ei.G
    delta_m = metrica(r, "Deslocamento máximo") / 1000
    assert 0.5 * 800e3 * delta_m**2 == pytest.approx(0.5 * massa * 1.5**2)
    assert metrica(r, "Energia absorvida") == pytest.approx(0.5 * massa * 1.5**2)


def test_barra_e_balanco_usam_a_rigidez_certa():
    barra = rodar("impacto", peca=ei.BARRA, area_mm2=500.0, l_mm=1000.0)
    assert metrica(barra, "Rigidez k") == pytest.approx(200e3 * 500 / 1000)
    balanco = rodar("impacto", peca=ei.BALANCO)
    assert metrica(balanco, "Rigidez k") == pytest.approx(3 * 200e3 * 26e6 / 2000**3)


def test_os_casos_novos_estao_no_painel_e_na_busca():
    assert "solda_filete" in cat.procurar("solda")
    assert "impacto" in cat.procurar("choque")
    assert cat.CASOS["solda_filete"].grupo == "Pinos, chapas e soldas"
    assert cat.area_do_caso("solda_filete") == cat.AREA_FIXACAO


def test_impacto_leva_a_forca_ao_proximo_caso():
    barra = rodar("impacto", peca=ei.BARRA)
    envio = next(e for e in barra.envios if e.destino == "coluna_simples")
    assert envio.valores["p_kN"] == pytest.approx(metrica(barra, "Força máxima"))
    assert envio.valores["l_m"] == pytest.approx(2.0)
    mola = rodar("impacto", peca=ei.MOLA)
    envio = next(e for e in mola.envios if e.destino == "mola_compressao")
    assert envio.valores["f_max_N"] == pytest.approx(metrica(mola, "Força máxima") * 1000)
