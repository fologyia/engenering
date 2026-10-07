"""Pontos do programa conferidos contra as normas e o texto do Projeto NBR 8800:2024.

Cada teste trava um número que a auditoria de 2026-10-07 leu na norma e que o programa usa:

* Tabelas 1 e 2 do Projeto NBR 8800:2024 (γ_f e ψ das ações), no que muda em relação a 2008 —
  o peso próprio de equipamentos passa a valer 1,25 e a sobrecarga de cobertura entra com ψ₀ = 0,8;
* 4.10.4.5: com a rigidez reduzida a 80 %, os limites de deslocabilidade viram 1,13 e 1,55;
* Tabela B.1: H/300 em galpões e edificações de um pavimento, H/400 nas de dois ou mais.
"""

from __future__ import annotations

import math

import pytest

from core import load_combinations as comb
from core import structural_2d as estrutural

# ------------------------------------------------------------------ Tabelas 1 e 2 (combinações)
EQUIPAMENTOS_2024 = "Peso próprio de equipamentos (Projeto NBR 8800:2024)"
COBERTURA_2024 = "Sobrecarga de cobertura (Projeto NBR 8800:2024)"


def test_peso_proprio_de_equipamentos_vale_1_25_no_projeto_2024_e_1_50_em_2008():
    novo = comb.categoria_nbr(EQUIPAMENTOS_2024)
    assert (novo.tipo, novo.gamma, novo.gamma_favoravel) == ("Permanente", 1.25, 1.00)
    assert "Projeto NBR 8800:2024" in novo.referencia
    antigo = comb.categoria_nbr("Elementos construtivos em geral e equipamentos")
    assert (antigo.gamma, antigo.gamma_favoravel) == (1.50, 1.00)  # a edição de 2008 continua


def test_sobrecarga_de_cobertura_do_projeto_2024():
    cobertura = comb.categoria_nbr(COBERTURA_2024)
    assert cobertura.tipo == "Variável" and cobertura.gamma == 1.50
    assert (cobertura.psi0, cobertura.psi1, cobertura.psi2) == (0.8, 0.7, 0.6)


@pytest.mark.parametrize(
    ("rotulo", "gamma", "psis"),
    [
        ("Vento (NBR 6123)", 1.40, (0.6, 0.3, 0.0)),  # Tabela 2: pressão dinâmica do vento
        ("Variação de temperatura", 1.20, (0.6, 0.5, 0.3)),
        ("Peso próprio de estrutura metálica", 1.25, (1.0, 1.0, 1.0)),
        ("Elementos construtivos industrializados com adições in loco", 1.40, (1.0, 1.0, 1.0)),
    ],
)
def test_categorias_que_continuam_como_nas_tabelas_do_projeto_2024(rotulo, gamma, psis):
    categoria = comb.categoria_nbr(rotulo)
    assert categoria.gamma == gamma
    assert (categoria.psi0, categoria.psi1, categoria.psi2) == psis


def test_combinacao_com_vento_usa_1_4_e_o_permanente_favoravel_aliviando():
    peso = comb.acao_da_categoria("PP aço", "Peso próprio de estrutura metálica", 0.0, -100.0, 0.0)
    vento = comb.acao_da_categoria("Vento", "Vento (NBR 6123)", 0.0, 60.0, 0.0)
    combinacoes = comb.gerar_combinacoes([peso, vento])
    elu_vento = [c for c in combinacoes if c.estado_limite == "ELU fundamental"]
    # Vento principal: 1,25·PP + 1,4·W; com o permanente aliviando (sucção): 1,0·PP + 1,4·W.
    normal = next(
        c for c in elu_vento if c.acao_principal == "Vento" and "favoráveis" not in c.nome
    )
    aliviando = next(c for c in elu_vento if "favoráveis" in c.nome)
    assert normal.v_kN == pytest.approx(1.25 * -100.0 + 1.4 * 60.0)
    assert aliviando.v_kN == pytest.approx(1.0 * -100.0 + 1.4 * 60.0)
    rara = next(c for c in combinacoes if c.estado_limite == "ELS rara")
    assert rara.v_kN == pytest.approx(-100.0 + 60.0)  # serviço: γ_f = 1, ψ da principal = 1


# ------------------------------------------------------------------ 4.10.4.5 (deslocabilidade)
def test_limites_de_deslocabilidade_sem_e_com_rigidez_reduzida():
    assert estrutural.limites_de_deslocabilidade() == (1.10, 1.40)
    assert estrutural.limites_de_deslocabilidade(1.0) == (1.10, 1.40)
    assert estrutural.limites_de_deslocabilidade(0.8) == (1.13, 1.55)


def test_limites_para_outra_reducao_seguem_a_mesma_amplificacao():
    # A conta que a norma arredonda para 1,13 e 1,55: 1/(1 − (1 − 1/L)/0,8).
    pequena, media = estrutural.limites_de_deslocabilidade(0.8 + 1e-3)
    assert pequena == pytest.approx(1.128, abs=2e-3) and media == pytest.approx(1.556, abs=5e-3)
    mais_flexivel = estrutural.limites_de_deslocabilidade(0.6)
    assert mais_flexivel[0] > pequena and mais_flexivel[1] > media
    # Redução muito forte: o limite de grande deslocabilidade some (denominador ≤ 0).
    assert math.isinf(estrutural.limites_de_deslocabilidade(0.2)[1])


@pytest.mark.parametrize(
    ("razao", "reducao", "esperado"),
    [
        (1.05, 1.0, "pequena deslocabilidade"),
        (1.12, 1.0, "média deslocabilidade"),
        (1.12, 0.8, "pequena deslocabilidade"),
        (1.14, 0.8, "média deslocabilidade"),
        (1.45, 1.0, "grande deslocabilidade"),
        (1.45, 0.8, "média deslocabilidade"),
        (1.56, 0.8, "grande deslocabilidade"),
    ],
)
def test_classificacao_usa_os_limites_da_rigidez_considerada(razao, reducao, esperado):
    assert estrutural.classificar_deslocabilidade(razao, reducao) == esperado


def portal(compressao_N: float, horizontal_N: float):
    nos = [
        estrutural.NoPortico(1, 0.0, 0.0, True, True, True),
        estrutural.NoPortico(2, 0.0, 4_000.0, fx_N=horizontal_N, fy_N=-compressao_N),
        estrutural.NoPortico(3, 5_000.0, 4_000.0, fy_N=-compressao_N),
        estrutural.NoPortico(4, 5_000.0, 0.0, True, True, True),
    ]
    elementos = [
        estrutural.ElementoPortico(1, 1, 2, 5_000.0, 2.0e7, 200_000.0),
        estrutural.ElementoPortico(2, 2, 3, 5_000.0, 8.0e7, 200_000.0),
        estrutural.ElementoPortico(3, 3, 4, 5_000.0, 2.0e7, 200_000.0),
    ]
    return nos, elementos


def test_pórtico_com_rigidez_reduzida_e_classificado_pelos_limites_novos():
    nos, elementos = portal(200_000.0, 5_000.0)
    reduzida = estrutural.analisar_portico(nos, elementos, segunda_ordem=True, reducao_rigidez=0.8)
    razao = reduzida.razao_delta2_delta1
    assert razao is not None
    assert reduzida.classificacao_deslocabilidade == estrutural.classificar_deslocabilidade(
        razao, 0.8
    )
    # Uma razão entre 1,10 e 1,13 é média sem a redução e pequena com ela.
    assert estrutural.classificar_deslocabilidade(
        1.12, 0.8
    ) != estrutural.classificar_deslocabilidade(1.12)


# ------------------------------------------------------------------ Tabela B.1 (deslocamentos)
def test_verificacao_de_h_sobre_300_para_galpao_e_h_sobre_400_para_edificio():
    nos, elementos = portal(100_000.0, 20_000.0)
    resultado = estrutural.analisar_portico(nos, elementos)
    galpao = estrutural.verificar_deslocamento_horizontal(
        resultado, altura_mm=4_000.0, divisor=300.0
    )
    edificio = estrutural.verificar_deslocamento_horizontal(
        resultado, altura_mm=4_000.0, divisor=400.0
    )
    assert galpao["criterio"] == "H/300" and edificio["criterio"] == "H/400"
    assert galpao["limite_mm"] == pytest.approx(4_000.0 / 300.0)
    assert edificio["limite_mm"] == pytest.approx(4_000.0 / 400.0)
    assert galpao["utilizacao"] < edificio["utilizacao"]  # o limite do galpão é mais folgado
