"""Pontos da auditoria de 24/11/2026 (U 6" × 12,20, rotulada em x, 2 × 3/4", químico)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import base_de_pilar as bp

U6 = bp.EntradaBase(
    perfil='U 6" x 12,20', tipo=bp.TIPO_ROTULADA_X, n_chumbadores=2, chumbador='3/4"',
    t_placa_mm=12.7, ancoragem=bp.ANCORAGEM_QUIMICO, h_ef_mm=200, e_n_mm=50,
    n_rd_fabricante_kN=106, perna_pilar_mm=5, cortante=bp.CORTANTE_DIRETOS,
    n_sd_kN=3.99, m_sd_kNm=0.59, m_sd_y_kNm=0.46, v_sd_kN=4.65,
)  # fmt: skip


def _nomes(r: bp.ResultadoBase) -> dict[str, bp.Verificacao]:
    return {v.nome: v for v in r.verificacoes}


@pytest.mark.parametrize("m_y", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0])
def test_equilibrio_elastico_vale_pelos_residuos(m_y):
    """Antes, M_y = 3, 5 e 8 saíam "sem equilíbrio" com o equilíbrio satisfeito (parada do Newton
    por arredondamento). Agora vale o resíduo: ∫σ − ΣF = N, ∫σx − ΣFx = M, ∫σy − ΣFy = M_y."""
    e = replace(U6, m_sd_y_kNm=m_y)
    g = bp.geometria(e)
    a_se = bp.area_resistente(e, bp.disposicoes(e))
    d = bp.distribuicao_elastica(g, 3990.0, 0.59e6, m_y * 1e6, 25.0, a_se)
    assert d.equilibrio
    w0, ax, ay = d.plano
    a, sx, sy, ixx, ixy, iyy = bp._momentos_do_poligono(list(d.zona))
    f = d.forcas
    pos = g.posicoes
    assert w0 * a + ax * sx + ay * sy - sum(f) == pytest.approx(3990.0, rel=1e-6)
    assert w0 * sx + ax * ixx + ay * ixy - sum(
        fi * x for fi, (x, _) in zip(f, pos, strict=True)
    ) == pytest.approx(0.59e6, rel=1e-6)
    assert w0 * sy + ax * ixy + ay * iyy - sum(
        fi * y for fi, (_, y) in zip(f, pos, strict=True)
    ) == pytest.approx(m_y * 1e6, rel=1e-6)
    r = bp.calcular(replace(e, distribuicao=bp.DISTRIBUICAO_ELASTICA))
    assert _nomes(r)["Equilíbrio elástico da placa"].status == "OK"


def test_sem_equilibrio_nao_mostra_espessura_nem_forcas():
    """Bloco uniforme sem solução (M_y = 10 kN·m): antes a espessura saía "OK" com t_p,min = 0."""
    r = bp.calcular(replace(U6, m_sd_y_kNm=10.0))
    nomes = _nomes(r)
    assert nomes["Equilíbrio possível com a placa (flexão oblíqua)"].status == "NÃO OK"
    placa = nomes["Placa de base: espessura t_p ≥ t_p,min"]
    assert placa.status == "NÃO OK" and placa.solicitante is None
    assert placa.formula.startswith(bp.SEM_EQUILIBRIO)
    assert nomes["Ancoragem no concreto"].status == "NÃO OK"
    # o que só usa N, V ou a geometria continua valendo
    assert nomes["Chumbador: aço à cortante (ACI 318-19)"].solicitante == pytest.approx(4.65)
    assert any("Sem equilíbrio" in a for a in r.avisos)


def test_com_equilibrio_nada_e_invalidado():
    r = bp.calcular(U6)
    assert not any(v.formula.startswith(bp.SEM_EQUILIBRIO) for v in r.verificacoes)


@pytest.mark.parametrize(("n_b", "engatados"), [(2, 1), (4, 2), (6, 2), (8, 2)])
def test_direto_no_furo_conta_metade_dos_chumbadores(n_b, engatados):
    assert bp.engatados_sem_arruela(n_b) == engatados


def test_base_de_dois_chumbadores_direto_no_furo_um_leva_a_cortante():
    linha = _nomes(bp.calcular(U6))["Chumbador: aço à cortante (ACI 318-19)"]
    assert linha.solicitante == pytest.approx(4.65)  # V_Sd inteiro, não V/2
    assert "só 1 de 2" in linha.formula


def test_trecho_interno_curto_da_solda_nao_cria_reprovacao_separada():
    e = replace(U6, solda_mesas_por_dentro=True)
    r, so_externa = bp.calcular(e), bp.calcular(replace(e, solda_mesas_por_dentro=False))
    nomes = _nomes(r)
    assert "Solda do pilar na placa: comprimento dos trechos internos da mesa" not in nomes
    # O trecho curto não entra na resistência; a solda restante continua verificada no grupo.
    nome_filete = "Solda do pilar na placa: filete no ponto mais solicitado"
    assert nomes[nome_filete].solicitante == pytest.approx(
        _nomes(so_externa)[nome_filete].solicitante
    )


def test_espessura_mostra_a_razao_em_t_e_em_t_ao_quadrado():
    r = bp.calcular(U6)
    linha = _nomes(r)["Placa de base: espessura t_p ≥ t_p,min"]
    razao = r.t_p_min / 12.7
    assert f"{100 * razao:.0f} %" in linha.formula
    assert f"{100 * razao**2:.0f} %" in linha.formula
