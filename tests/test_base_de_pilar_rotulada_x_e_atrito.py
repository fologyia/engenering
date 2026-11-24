"""Base rotulada em x (2 chumbadores no eixo x, fora das mesas) e o atrito que não basta numa
combinação de compressão (a cortante vai aos chumbadores, como na tração)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import base_de_pilar as bp

PADRAO = bp.EntradaBase()  # W 250 x 32,7, tipo 1, 4 × Ø 1", t_p 25 mm, f_ck 25, N 300 kN, V 20 kN
ROT_X = replace(PADRAO, tipo=bp.TIPO_ROTULADA_X, n_chumbadores=2)
U8 = 'U 8" x 17,10'
ATRITO = "Cortante: atrito na argamassa"
NAO_BASTA = "Cortante: atrito na argamassa não basta"


def _nomes(r: bp.ResultadoBase) -> dict[str, bp.Verificacao]:
    return {v.nome: v for v in r.verificacoes}


# ============================================================================ rotulada em x
def test_rotulada_em_x_tem_dois_chumbadores_no_eixo_x_fora_das_mesas():
    g = bp.geometria(ROT_X)
    assert bp.TIPO_ROTULADA_X in bp.TIPOS and bp.QUANTIDADES[bp.TIPO_ROTULADA_X] == (2,)
    assert g.lx == pytest.approx(g.d + 4 * g.a1)
    assert g.a == pytest.approx(g.lx / 2 - g.a1)
    assert g.posicoes == ((-g.a, 0.0), (g.a, 0.0))
    assert g.ly == pytest.approx(max(2 * g.a1, g.b_f + 25.0))
    assert g.l0 is None and g.a > g.d / 2  # fora das mesas


def test_rotulada_em_x_flexao_pura_sem_contato_pelo_binario():
    """T2: F = |N|/2 + M/(2a) no chumbador tracionado (F_i = N/n − M·x_i/Σx², Σx² = 2a²)."""
    n, m = -40.0, 2.0
    r = bp.calcular(replace(ROT_X, n_sd_kN=n, m_sd_kNm=m, v_sd_kN=0))
    g = r.geometria
    assert r.caso == "T2"
    assert max(r.forcas_nos_chumbadores) == pytest.approx(40e3 / 2 + 2e6 / (2 * g.a))
    assert min(r.forcas_nos_chumbadores) == pytest.approx(40e3 / 2 - 2e6 / (2 * g.a))


def test_rotulada_em_x_c3_equilibra_n_e_m():
    r = bp.calcular(replace(ROT_X, n_sd_kN=30, m_sd_kNm=40, v_sd_kN=0))
    g = r.geometria
    assert r.caso == "C3" and r.l_c is not None
    t = sum(r.forcas_nos_chumbadores)
    compressao = r.sigma_c_rd * r.l_c * g.ly
    assert compressao == pytest.approx(30e3 + t, rel=1e-6)
    resistido = compressao * (g.lx / 2 - r.l_c / 2) - sum(
        f * x for f, (x, _) in zip(r.forcas_nos_chumbadores, g.posicoes, strict=True)
    )
    assert resistido == pytest.approx(40e6, rel=1e-4)


def test_rotulada_em_x_segura_m_com_menos_tracao_que_a_em_y():
    """O mesmo M: a rotulada em x faz binário entre o chumbador e a borda comprimida (braço ~ ℓx);
    a em y tem os chumbadores no eixo, só o concreto faz braço, e a tração total é bem maior."""
    em_x = bp.calcular(replace(ROT_X, n_sd_kN=-20, m_sd_kNm=20, v_sd_kN=0))
    em_y = bp.calcular(
        replace(PADRAO, tipo=bp.TIPO_ROTULADA, n_chumbadores=2, n_sd_kN=-20, m_sd_kNm=20, v_sd_kN=0)
    )
    assert em_x.caso == em_y.caso == "T3"
    assert sum(em_x.forcas_nos_chumbadores) < 0.7 * sum(em_y.forcas_nos_chumbadores)
    # na em x o chumbador do lado comprimido quase não trabalha; na em y os dois puxam igual
    assert em_x.forcas_nos_chumbadores[0] > 5 * em_x.forcas_nos_chumbadores[1]
    assert em_y.forcas_nos_chumbadores[0] == pytest.approx(em_y.forcas_nos_chumbadores[1])


def test_nomes_das_duas_rotuladas():
    assert bp.NOMES_CURTOS[bp.TIPO_ROTULADA] == "rotulada em y"
    assert bp.NOMES_CURTOS[bp.TIPO_ROTULADA_X] == "rotulada em x"
    assert "eixo y" in bp.TIPOS[bp.TIPO_ROTULADA] and "eixo x" in bp.TIPOS[bp.TIPO_ROTULADA_X]


def test_pilar_u_aceita_a_rotulada_em_x():
    assert bp.tipos_do_perfil(U8) == (bp.TIPO_1, bp.TIPO_ROTULADA_X)
    r = bp.calcular(replace(ROT_X, perfil=U8, chumbador='3/4"', n_sd_kN=50, v_sd_kN=5))
    g = r.geometria
    folga = g.ly / 2 - max(-g.faixa_y[0], g.faixa_y[1])
    assert folga >= 12.5 - 1e-9
    assert _nomes(r)["Largura da placa ℓy: 12,5 mm além do U de cada lado"].status == "OK"
    with pytest.raises(bp.BaseInvalida, match="rotulada em x"):
        bp.calcular(replace(PADRAO, perfil=U8, tipo=bp.TIPO_ROTULADA, n_chumbadores=2))


def test_desenho_da_rotulada_em_x():
    from core import desenho_placa_base as dpb

    for perfil in ("W 250 x 32,7", U8):
        r = bp.calcular(replace(ROT_X, perfil=perfil, n_sd_kN=30, m_sd_kNm=15, v_sd_kN=10))
        figura = dpb.figura_da_base(r)
        assert figura.png and "rotulada em x" in figura.titulo


# ============================================================================ atrito
def test_atrito_que_basta_continua_como_antes():
    r = bp.calcular(replace(PADRAO, n_sd_kN=100, v_sd_kN=20))
    linha = _nomes(r)[ATRITO]
    assert linha.resistente == pytest.approx(0.45 * 100 / 1.35)
    assert NAO_BASTA not in _nomes(r)


@pytest.mark.parametrize("n", [30.0, 10.0, 1.0])
def test_atrito_que_nao_basta_manda_a_cortante_aos_chumbadores(n):
    r = bp.calcular(replace(PADRAO, n_sd_kN=n, v_sd_kN=20))
    nomes = _nomes(r)
    assert r.caso == "C1"
    assert ATRITO not in nomes  # sem o NÃO OK de centenas de %
    info = nomes[NAO_BASTA]
    assert info.status == "INFO"
    assert f"N_Sd ≥ {round(20 * 1.35 / 0.45)} kN" in info.formula
    # a mesma verificação das combinações com tração
    assert "Chumbador: aço à cortante (ACI 318-19)" in nomes
    assert bp.LINHA_FLEXAO_NA_ARGAMASSA in nomes
    assert "Chumbadores direto no furo: deslizamento antes do contato" in nomes
    assert any("atrito na argamassa" in a and "compressão desta combinação" in a for a in r.avisos)
    assert r.aproveitamento_maximo < 2.0


def test_atrito_igual_ao_caso_de_tracao_na_cortante_dos_chumbadores():
    """Com o atrito que não basta, a cortante nos chumbadores é a mesma conta da tração."""
    com_pouca_compressao = _nomes(bp.calcular(replace(PADRAO, n_sd_kN=1, v_sd_kN=20)))
    com_tracao = _nomes(bp.calcular(replace(PADRAO, n_sd_kN=-1, v_sd_kN=20)))
    nome = "Chumbador: aço à cortante (ACI 318-19)"
    assert com_pouca_compressao[nome].solicitante == pytest.approx(com_tracao[nome].solicitante)
    assert com_pouca_compressao[nome].resistente == pytest.approx(com_tracao[nome].resistente)


def test_envoltoria_com_uma_combinacao_de_vento():
    casos = (
        bp.CasoDeCarga("ELU1 peso", 300.0, 0.0, 0.0, 20.0),
        bp.CasoDeCarga("ELU2 vento", 5.0, 0.0, 0.0, 25.0),
    )
    r = bp.calcular(replace(PADRAO, casos=casos))
    nomes = _nomes(r)
    assert nomes[ATRITO].status == "OK"  # o da combinação com compressão grande
    assert nomes[NAO_BASTA].status == "INFO"  # o vento foi aos chumbadores
    assert "Chumbador: aço à cortante (ACI 318-19)" in nomes
    assert r.aproveitamento_maximo < 2.0


def test_placa_de_cisalhamento_nao_muda():
    r = bp.calcular(replace(PADRAO, n_sd_kN=5, v_sd_kN=20, cortante=bp.CORTANTE_PLACA))
    nomes = _nomes(r)
    assert "Cortante: placa de cisalhamento" in nomes and NAO_BASTA not in nomes
