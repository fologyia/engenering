"""Chumbador fora da Tabela 18: as medidas por fórmula, contra as tabelas das normas e contas de mão."""

from __future__ import annotations

import math
from dataclasses import asdict, replace

import pytest

from core import base_de_pilar as bp
from core.desenho_placa_base import figura_da_base

POR_FORMULA = bp.EntradaBase(por_formula=True)
TRACAO = replace(POR_FORMULA, chumbador="M24", n_sd_kN=-200.0, m_sd_kNm=30.0)
C3_6 = replace(bp.EntradaBase(), n_chumbadores=6, m_sd_kNm=150.0, t_placa_mm=40.0)


def linha(r: bp.ResultadoBase, nome: str):
    return next(v for v in r.verificacoes if v.nome == nome)


# ------------------------------------------------------------------ rosca
@pytest.mark.parametrize(
    ("nome", "area"),
    [
        # ISO 898-1, área resistente nominal (mm²)
        ("M20", 245.0),
        ("M24", 353.0),
        ("M30", 561.0),
        ("M36", 817.0),
        ("M64", 2676.0),
        # ASME B1.1, UNC: 0,334, 0,606 e 2,50 in²
        ('3/4"', 0.334 * 645.16),
        ('1"', 0.606 * 645.16),
        ('2"', 2.50 * 645.16),
    ],
)
def test_area_resistente_da_rosca_bate_com_as_tabelas(nome, area):
    assert bp.ROSCAS[nome].area_resistente == pytest.approx(area, rel=5e-3)


def test_series_comerciais_em_ordem_e_passo_do_digitado():
    polegadas = bp.roscas_da_familia(bp.FAMILIA_POLEGADA)
    metricas = bp.roscas_da_familia(bp.FAMILIA_METRICA)
    assert polegadas[0].nome == '1/2"' and polegadas[-1].nome == '4"'
    assert metricas[0].nome == "M12" and metricas[-1].nome == "M64"
    assert all(a.d_b < b.d_b for a, b in zip(polegadas, polegadas[1:], strict=False))
    assert bp.ROSCAS['2 1/2"'].d_b == pytest.approx(63.5)
    assert bp.passo_iso_mais_perto(29.0) == 3.5  # M30
    livre = bp.rosca_do_chumbador(replace(POR_FORMULA, chumbador=bp.CHUMBADOR_LIVRE, d_b_mm=29.0))
    assert livre.passo == 3.5 and livre.serie == bp.SERIE_ISO
    informado = replace(POR_FORMULA, chumbador=bp.CHUMBADOR_LIVRE, d_b_mm=29.0, passo_mm=3.0)
    assert bp.rosca_do_chumbador(informado).serie == bp.SERIE_INFORMADA


# ------------------------------------------------------------------ medidas
def test_furo_padrao_e_o_da_tabela_18_interpolado():
    for tab in bp.TABELA_18.values():
        assert bp.furo_padrao(tab.d_b) == tab.d_f
    assert bp.furo_padrao(28.5) == pytest.approx(47.5 + 0.5)  # entre 25 (45) e 32 (50), para cima
    assert bp.furo_padrao(16.0) == 16.0 + 14.0  # abaixo de 3/4": a folga de 14 mm
    assert bp.furo_padrao(63.5) == math.ceil(63.5 + 30.0)  # acima de 2": a folga de 30 mm


@pytest.mark.parametrize("polegada", list(bp.TABELA_18))
def test_medidas_por_formula_ficam_perto_da_tabela_18(polegada):
    """Nos diâmetros da tabela, as fórmulas dão as medidas dela (até 5 mm de diferença)."""
    tab = bp.TABELA_18[polegada]
    m = bp.medidas_por_formula(replace(POR_FORMULA, chumbador=polegada)).linha
    assert abs(m.a1 - tab.a1) <= 5 and abs(m.a2 - tab.a2) <= 5 and abs(m.a3 - tab.a3) <= 5
    assert abs(m.d_f - tab.d_f) <= 1.5
    assert 2 * m.d_f - m.d_b <= m.lado_da_arruela <= tab.lado_da_arruela  # cobre o furo
    assert m.t_arruela >= m.d_b / 3 / 1.02  # AISC: ≈ d_b/3 (a NBR usa aço de 345 MPa, mais fina)
    assert m.a2 == 2 * m.a1 or m.a1 > m.a2 / 2  # a proporção da Tabela 18, ou a arruela manda


def test_contas_das_medidas_de_um_m30():
    m = bp.medidas_por_formula(replace(POR_FORMULA, chumbador="M30", t_placa_mm=25.0), 400.0)
    lin = m.linha
    assert m.lado_da_porca == pytest.approx(1.5 * 30 + 3.2)
    assert lin.d_f == 49.0  # 45 + (50 − 45)·(30 − 25)/(32 − 25) = 48,6 → 49
    assert lin.arruela == "70 × 70"  # 2·49 − 30 = 68 → 70
    assert lin.t_arruela == 12.5  # 30/3 = 10 → 12,5
    assert lin.a2 == 120.0 and lin.a1 == 60.0 and lin.a3 == 180.0  # 4·d, a₂/2, 6·d
    assert lin.e_n == 60.0  # 30 + 12,5 + 15 = 57,5 → 60
    assert lin.h2 == 140.0  # 60 + 25 + 12,5 + 30 + 3·3,5 = 138 → 140
    assert lin.r1 == 165.0 and lin.r2 == 50.0
    assert lin.h1 == 400.0
    assert m.comprimento == pytest.approx(400 + 140 + 30 + 10.5)
    assert m.massa_kg == pytest.approx(math.pi * 15**2 * m.comprimento * 1e-9 * 7850)
    assert {nome for nome, _, _ in m.contas} >= {"Rosca", "Furo na placa d_f", "Embutimento h_ef"}


def test_pos_instalado_usa_as_distancias_da_aci_sem_dados_do_produto():
    m = bp.medidas_por_formula(
        replace(POR_FORMULA, chumbador="M20", ancoragem=bp.ANCORAGEM_EXPANSAO)
    )
    assert m.linha.a2 == 120.0  # 6·d_a
    assert m.linha.a3 == 160.0  # 8·d_a (expansão controlada por torque)
    q = bp.medidas_por_formula(
        replace(POR_FORMULA, chumbador="M20", ancoragem=bp.ANCORAGEM_QUIMICO)
    )
    assert q.linha.a3 == 120.0  # 6·d_a


# ------------------------------------------------------------------ o cálculo da base
def test_mesma_geometria_da_tabela_da_os_mesmos_esforcos_e_a_mesma_placa():
    """Com d_b, a₁, a₂, e_n e arruela iguais aos do Ø 1", a placa e os chumbadores não mudam."""
    tabela = bp.calcular(C3_6)
    formula = bp.calcular(
        replace(
            C3_6, por_formula=True, chumbador=bp.CHUMBADOR_LIVRE, d_b_mm=25.0, a1_mm=50.0,
            a2_mm=100.0, e_n_mm=60.0, t_arruela_mm=8.0,
        )
    )  # fmt: skip
    assert formula.caso == tabela.caso == "C3"
    assert formula.t_p_min == pytest.approx(tabela.t_p_min)
    assert formula.forcas_nos_chumbadores == pytest.approx(tabela.forcas_nos_chumbadores)
    assert formula.d_b_min == pytest.approx(tabela.d_b_min)


def test_por_formula_a_ancoragem_e_sempre_verificada():
    r = bp.calcular(TRACAO)
    nomes = [v.nome for v in r.verificacoes]
    assert "Chumbador fora da Tabela 18 (por fórmula)" in nomes
    assert bp.LINHA_DO_CONE in nomes and "Arrancamento da cabeça (porca ou chapa na ponta)" in nomes
    assert not any("Tabela 18 com" in n for n in nomes)  # a nota a não se aplica
    assert r.grupos[-1][0] == bp.GRUPO_CONSTRUTIVAS_FORMULA
    assert linha(r, "Concreto: f_ck ≥ 20 MPa").status == "OK"
    assert linha(r, "Argamassa: cabem a porca de nivelamento e a arruela").status == "OK"


def test_embutimento_e_o_menor_que_passa_no_cone():
    e = replace(TRACAO, chumbador="M30", n_sd_kN=-400.0, bloco_x_mm=2500.0, bloco_y_mm=2500.0)
    r = bp.calcular(e)
    h = bp.embutimento(e, r.linha)
    assert linha(r, bp.LINHA_DO_CONE).status == "OK"
    assert h % 25 == 0 and h > bp._acima(12 * 30, 25.0)  # passou do piso de 12·d_b
    menor = bp.calcular(replace(e, h_ef_mm=h - 25.0))
    assert linha(menor, bp.LINHA_DO_CONE).status == "NÃO OK"


def test_sem_tracao_ou_com_armadura_o_embutimento_fica_no_piso():
    assert bp.calcular(replace(POR_FORMULA, chumbador="M24")).linha.h1 == 300.0  # 12·24 → 300
    armado = bp.calcular(replace(TRACAO, armadura_de_ancoragem=True))
    assert armado.linha.h1 == 300.0
    assert linha(armado, "Cone de concreto: armadura de ancoragem no bloco").status == "INFO"


def test_cone_que_nao_passa_avisa_que_o_diametro_nao_resolve():
    r = bp.calcular(TRACAO)  # bloco não informado: o mínimo por fórmula, pequeno
    assert linha(r, bp.LINHA_DO_CONE).status == "NÃO OK"
    assert any("Trocar o diâmetro não resolve o cone" in a for a in r.avisos)


def test_diametro_que_cada_criterio_pede():
    e = replace(TRACAO, cortante=bp.CORTANTE_ARRUELAS, v_sd_kN=40.0)
    r = bp.calcular(e)
    criterios = {nome: d for nome, d, _ in r.diametros}
    assert criterios["Tração no aço"] == pytest.approx(r.d_b_min)
    d = criterios["Arrancamento da porca da ponta"]
    a_brg = math.sqrt(3) / 2 * (1.5 * d + 3.2) ** 2 - math.pi * d**2 / 4
    assert 0.70 * 8 * a_brg * e.fck_MPa == pytest.approx(r.f_t_sd, rel=1e-6)
    assert criterios["Cortante pelas arruelas soldadas"] is not None


def test_menor_diametro_comercial_que_atende_e_o_menor():
    r = bp.menor_diametro_que_atende(TRACAO)
    assert r is not None and bp.chumbadores_passam(r)
    serie = [x.nome for x in bp.roscas_da_familia(bp.FAMILIA_METRICA)]
    anterior = serie[serie.index(r.entrada.chumbador) - 1]
    assert not bp.chumbadores_passam(bp.calcular(replace(TRACAO, chumbador=anterior)))
    assert bp.menor_diametro_que_atende(bp.EntradaBase()) is None  # só no modo por fórmula


def test_tracao_alta_passa_do_maior_diametro_da_tabela_18():
    alta = replace(bp.EntradaBase(), n_sd_kN=-2000.0, v_sd_kN=0.0, chumbador='2"')
    tabela = bp.calcular(alta)
    assert linha(tabela, "Chumbador: diâmetro d_b ≥ d_b,min").status == "NÃO OK"
    r = bp.menor_diametro_que_atende(replace(alta, por_formula=True))
    assert r is not None and r.entrada.chumbador == '2 1/4"'
    assert linha(r, "Chumbador: diâmetro d_b ≥ d_b,min").status == "OK"


def test_rosca_pequena_confere_a_area_resistente():
    """No 5/8" UNC, A_s = 146 mm² fica abaixo dos 0,75·A_b = 148 mm² da fórmula de d_b,min."""
    e = replace(POR_FORMULA, chumbador='5/8"', n_sd_kN=-60.0, v_sd_kN=0.0)
    r = bp.calcular(e)
    rosca = linha(r, "Rosca: tração na área resistente A_s")
    assert rosca.resistente == pytest.approx(bp.ROSCAS['5/8"'].area_resistente * 400 / 1.35 / 1e3)
    m24 = bp.calcular(replace(e, chumbador="M24"))
    assert not any(v.nome.startswith("Rosca:") for v in m24.verificacoes)  # A_s > 0,75·A_b


def test_entrada_invalida_por_formula():
    with pytest.raises(bp.BaseInvalida, match="entre 6 e 150"):
        bp.calcular(replace(POR_FORMULA, chumbador=bp.CHUMBADOR_LIVRE, d_b_mm=4.0))
    with pytest.raises(bp.BaseInvalida, match="maior que o diâmetro"):
        bp.calcular(replace(POR_FORMULA, chumbador="M30", d_f_mm=30.0))
    with pytest.raises(bp.BaseInvalida, match="desconhecido"):
        bp.calcular(replace(POR_FORMULA, chumbador="M31"))
    with pytest.raises(bp.BaseInvalida, match="Passo"):
        bp.calcular(replace(POR_FORMULA, chumbador=bp.CHUMBADOR_LIVRE, d_b_mm=30.0, passo_mm=20.0))
    with pytest.raises(bp.BaseInvalida, match="Tabela 18"):
        bp.calcular(replace(bp.EntradaBase(), chumbador="M30"))  # na Tabela 18, só os dela


def test_base_mais_leve_fica_na_serie_e_o_digitado_fica():
    leve = bp.base_mais_leve(replace(TRACAO, cortante=bp.CORTANTE_ARRUELAS, v_sd_kN=40.0))
    assert leve is not None and leve.entrada.chumbador in {r.nome for r in bp.roscas_da_familia(bp.FAMILIA_METRICA)}  # fmt: skip
    assert bp.passa_fora_o_cone(leve)
    livre = replace(
        TRACAO,
        chumbador=bp.CHUMBADOR_LIVRE,
        d_b_mm=27.0,
        # sem cortante: com 200 kN de tração, o Ø 27 mm não leva também a flexão da cortante na
        # argamassa (ACI 318-19 17.7.1 e DG1) e a busca, que não troca o digitado, não acharia base
        cortante=bp.CORTANTE_ARRUELAS,
        v_sd_kN=0.0,
    )
    leve_livre = bp.base_mais_leve(livre)
    assert leve_livre is not None and leve_livre.entrada.chumbador == bp.CHUMBADOR_LIVRE


# ------------------------------------------------------------------ registro, memorial e desenho
def test_registro_figura_e_volta_do_dicionario():
    r = bp.calcular(replace(TRACAO, chumbador='2 1/2"', n_sd_kN=-900.0))
    registro = bp.registro_base(r)
    assert "fora da Tabela 18" in registro["entradas"]["chumbadores"]
    assert "A_s" in registro["entradas"]["rosca"]
    assert bp.NOTA_POR_FORMULA in registro["premissas"]
    assert any("17.9.2" in ref for ref in registro["referencias"])
    assert "fora da Tabela 18" in bp.destaque(r)
    figura = figura_da_base(r)
    assert figura.png and 'Ø 2 1/2"' in figura.legenda
    de_volta = bp.calcular(bp.entrada_de_dicionario(asdict(r.entrada)))
    assert de_volta.t_p_min == pytest.approx(r.t_p_min)
    assert de_volta.linha == r.linha


def test_memorial_word_do_modo_por_formula():
    r = bp.calcular(replace(POR_FORMULA, chumbador="M30"))
    conteudo = bp.memorial_da_base(r)
    assert conteudo[:2] == b"PK"  # .docx


def test_memorial_mostra_as_entradas_novas_com_rotulo_proprio():
    from core.memorial_verificacoes import pares_de_entrada
    from core.technical_records import normalizar_registro_tecnico

    def pares(resultado: bp.ResultadoBase) -> dict[str, str]:
        registro = normalizar_registro_tecnico(bp.registro_base(resultado))
        return dict(pares_de_entrada(registro, str, str))

    rotulos = pares(bp.calcular(replace(TRACAO, chumbador="M30", n_sd_kN=-400.0)))
    assert "A_s = 561 mm²" in rotulos["Rosca do chumbador (por fórmula)"]
    assert rotulos["Furo na placa e arruela"].startswith("d_f = 49 mm")
    assert "Embutimento h_ef [mm]" in rotulos and "a₃, do chumbador à face do bloco [mm]" in rotulos
    assert "Rosca do chumbador (por fórmula)" not in pares(bp.calcular(C3_6))  # Tabela 18
