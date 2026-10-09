"""Combinações de ações (NBR 8800 4.8.7 / NBR 8681): lista explícita e envoltória rigorosa.

Valores conferidos à mão com as equações de 4.8.7.2 e 4.8.7.3 do Projeto NBR 8800:2024 e as
Tabelas 1 e 2.
"""

from __future__ import annotations

import json

import pytest

from core import load_combinations as comb

PP = "Peso próprio de estrutura metálica"
SC = "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas"
VENTO = "Vento (NBR 6123)"
TEMP = "Variação de temperatura"


def acoes_basicas():
    return [
        comb.acao_da_categoria("G", PP, efeitos={"N": 0.0}, n_kN=-100.0),
        comb.acao_da_categoria("Q", SC, n_kN=-50.0),
        comb.acao_da_categoria("W+", VENTO, n_kN=80.0, grupo="Vento"),
        comb.acao_da_categoria("W−", VENTO, n_kN=-30.0, grupo="Vento"),
    ]


# ------------------------------------------------------------------ coeficientes das tabelas
@pytest.mark.parametrize(
    ("rotulo", "normal", "especial", "excepcional"),
    [
        (PP, 1.25, 1.15, 1.10),
        ("Elementos construtivos em geral e equipamentos", 1.50, 1.40, 1.30),
        (VENTO, 1.40, 1.20, 1.00),
        (TEMP, 1.20, 1.00, 1.00),
        (SC, 1.50, 1.30, 1.00),
        ("Ação variável truncada (limitada fisicamente)", 1.20, 1.10, 1.00),
    ],
)
def test_gamma_das_tres_linhas_da_tabela_1(rotulo, normal, especial, excepcional):
    acao = comb.acao_da_categoria("A", rotulo, 1.0)
    assert comb.gamma_desfavoravel(acao, comb.ELU_NORMAL) == normal
    assert comb.gamma_desfavoravel(acao, comb.ELU_ESPECIAL) == especial
    assert comb.gamma_desfavoravel(acao, comb.ELU_EXCEPCIONAL) == excepcional
    assert comb.gamma_desfavoravel(acao, comb.ELS_RARA) == 1.0


def test_truncada_tem_psi_igual_a_1():
    categoria = comb.categoria_nbr("Ação variável truncada (limitada fisicamente)")
    assert (categoria.psi0, categoria.psi1, categoria.psi2) == (1.0, 1.0, 1.0)


# ------------------------------------------------------------------ lista explícita
def test_els_rara_usa_psi1_nas_acompanhantes():
    """4.8.7.3.4: F = ΣG + F_Q1 + Σψ1·F_Qj (antes o programa usava ψ0)."""
    g = comb.acao_da_categoria("G", PP, 10.0)
    q = comb.acao_da_categoria("Q", SC, 5.0)
    t = comb.acao_da_categoria("T", TEMP, 4.0)
    rara_q = next(
        c
        for c in comb.gerar_combinacoes([g, q, t])
        if c.estado_limite == comb.ELS_RARA and c.acao_principal == "Q"
    )
    assert rara_q.n_kN == pytest.approx(10.0 + 5.0 + 0.5 * 4.0)  # ψ1 da temperatura = 0,5


def test_els_frequente_e_quase_permanente():
    g = comb.acao_da_categoria("G", PP, 10.0)
    q = comb.acao_da_categoria("Q", SC, 5.0)
    t = comb.acao_da_categoria("T", TEMP, 4.0)
    lista = comb.gerar_combinacoes([g, q, t])
    freq_q = next(
        c for c in lista if c.estado_limite == comb.ELS_FREQUENTE and c.acao_principal == "Q"
    )
    assert freq_q.n_kN == pytest.approx(10.0 + 0.6 * 5.0 + 0.3 * 4.0)
    qp = next(c for c in lista if c.estado_limite == comb.ELS_QUASE_PERMANENTE)
    assert qp.n_kN == pytest.approx(10.0 + 0.4 * 5.0 + 0.3 * 4.0)


def test_acoes_do_mesmo_grupo_nunca_atuam_juntas():
    lista = comb.gerar_combinacoes(acoes_basicas(), comb.TODOS_OS_ESTADOS)
    for c in lista:
        assert not ("W+" in c.fatores and "W−" in c.fatores), c.nome
    # Sobrecarga principal: uma combinação com W+ e outra com W− (por estado e por permanente).
    elu_q = [
        c
        for c in lista
        if c.estado_limite == comb.ELU_NORMAL
        and c.acao_principal == "Q"
        and "favoráveis" not in c.nome
    ]
    assert sorted(n for c in elu_q for n in c.fatores if n.startswith("W")) == ["W+", "W−"]
    assert all("com W" in c.nome for c in elu_q)


def test_elu_normal_com_vento_principal_e_sobrecarga_acompanhante():
    lista = comb.gerar_combinacoes(acoes_basicas(), [comb.ELU_NORMAL])
    c = next(c for c in lista if c.acao_principal == "W+" and "favoráveis" not in c.nome)
    assert c.fatores == {"G": 1.25, "W+": 1.4, "Q": pytest.approx(1.5 * 0.7)}
    assert c.n_kN == pytest.approx(1.25 * -100 + 1.4 * 80 + 1.05 * -50)
    fav = next(c for c in lista if c.acao_principal == "W+" and "favoráveis" in c.nome)
    assert fav.fatores["G"] == 1.0


def test_especial_usa_os_gamma_da_linha_especial_e_psi2_se_curta():
    lista = comb.gerar_combinacoes(
        acoes_basicas(), [comb.ELU_ESPECIAL], especial_curta_duracao=True
    )
    c = next(c for c in lista if c.acao_principal == "Q" and "W+" in c.fatores)
    assert c.fatores["G"] == 1.15 and c.fatores["Q"] == 1.30
    assert c.fatores["W+"] == pytest.approx(1.20 * 0.0)  # ψ2 do vento = 0


def test_excepcional_so_existe_com_acao_excepcional():
    assert comb.gerar_combinacoes(acoes_basicas(), [comb.ELU_EXCEPCIONAL]) == []
    assert comb.extremo(acoes_basicas(), "N", comb.ELU_EXCEPCIONAL) is None
    impacto = comb.acao_da_categoria(
        "Impacto", "Ação excepcional (impacto, explosão, incêndio)", 200.0
    )
    lista = comb.gerar_combinacoes([*acoes_basicas(), impacto], [comb.ELU_EXCEPCIONAL])
    assert lista and all(c.acao_principal == "Impacto" for c in lista)
    c = next(c for c in lista if "favoráveis" not in c.nome and "W+" in c.fatores)
    assert c.fatores["Impacto"] == 1.0 and c.fatores["G"] == 1.10
    assert c.fatores["Q"] == pytest.approx(0.4)  # γ = 1,0 × ψ2 = 0,4
    # A ação excepcional não entra em nenhuma combinação normal.
    normais = comb.gerar_combinacoes([*acoes_basicas(), impacto], [comb.ELU_NORMAL])
    assert all("Impacto" not in c.fatores for c in normais)


def test_limite_de_combinacoes_pede_agrupamento():
    muitas = [comb.acao_da_categoria(f"Q{i}", SC, 1.0, grupo=f"g{i % 6}") for i in range(30)]
    with pytest.raises(ValueError, match="agrupe"):
        comb.gerar_combinacoes(muitas, limite=200)


def test_permanente_nao_pode_ter_grupo():
    with pytest.raises(ValueError, match="grupo exclusivo"):
        comb.gerar_combinacoes([comb.acao_da_categoria("G", PP, 1.0, grupo="x")])


# ------------------------------------------------------------------ envoltória rigorosa
def test_maximo_de_tracao_usa_permanente_favoravel_e_deixa_a_sobrecarga_de_fora():
    """Vento de sucção (N > 0) contra peso (N < 0): G com 1,0, Q fora (aliviaria)."""
    maximo = comb.extremo(acoes_basicas(), "N", comb.ELU_NORMAL, 1)
    assert maximo.acao_principal == "W+"
    assert maximo.fatores == {"G": 1.0, "W+": 1.4}
    assert maximo.valor == pytest.approx(-100 + 1.4 * 80)


def test_minimo_de_compressao_soma_tudo_o_que_agrava():
    minimo = comb.extremo(acoes_basicas(), "N", comb.ELU_NORMAL, -1)
    # Q principal (1,5·50) com W− acompanhante (1,4·0,6·30) e G desfavorável.
    assert minimo.valor == pytest.approx(-1.25 * 100 - 1.5 * 50 - 1.4 * 0.6 * 30)
    assert minimo.acao_principal == "Q" and minimo.fatores["W−"] == pytest.approx(0.84)
    assert "W+" not in minimo.fatores


def test_lista_explicita_nunca_passa_da_envoltoria_rigorosa():
    acoes = acoes_basicas()
    lista = comb.gerar_combinacoes(acoes, [comb.ELU_NORMAL])
    maximo = comb.extremo(acoes, "N", comb.ELU_NORMAL, 1)
    minimo = comb.extremo(acoes, "N", comb.ELU_NORMAL, -1)
    assert max(c.n_kN for c in lista) <= maximo.valor + 1e-9
    assert min(c.n_kN for c in lista) >= minimo.valor - 1e-9


def test_efeito_reversivel_entra_sempre_desfavoravel():
    """Força nocional: 0,3 % do peso, no sentido que agrava (4.10.7.1.1)."""
    g = comb.acao_da_categoria("G", PP, efeitos={"H": 3.0}, efeitos_reversiveis={"H"})
    w = comb.acao_da_categoria("W", VENTO, efeitos={"H": 20.0}, grupo="Vento")
    w2 = comb.acao_da_categoria("W−", VENTO, efeitos={"H": -20.0}, grupo="Vento")
    maximo = comb.extremo([g, w, w2], "H", comb.ELU_NORMAL, 1)
    minimo = comb.extremo([g, w, w2], "H", comb.ELU_NORMAL, -1)
    assert maximo.valor == pytest.approx(1.25 * 3 + 1.4 * 20)
    assert minimo.valor == pytest.approx(-(1.25 * 3 + 1.4 * 20))
    assert comb.maior_modulo([g, w, w2], "H").valor == pytest.approx(31.75)


def test_servico_nao_usa_gamma_favoravel_nem_majoracao():
    rara = comb.extremo(acoes_basicas(), "N", comb.ELS_RARA, 1)
    assert rara.fatores == {"G": 1.0, "W+": 1.0}
    assert rara.valor == pytest.approx(-100 + 80)


def test_envoltoria_traz_maximo_e_minimo_de_cada_estado():
    extremos = comb.envoltoria(acoes_basicas(), ["N"], comb.ESTADOS_PADRAO)
    assert len(extremos) == 2 * len(comb.ESTADOS_PADRAO)
    assert {e.estado_limite for e in extremos} == set(comb.ESTADOS_PADRAO)


def test_acao_para_dicionario_e_serializavel():
    g = comb.acao_da_categoria("G", PP, efeitos={"H": 3.0}, efeitos_reversiveis={"H"})
    json.dumps(comb.acao_para_dicionario(g))
