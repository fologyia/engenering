"""Ligações: referências conferidas na NBR 8800:2025, perna sugerida, resumo da tela e casos de borda.

Completa :mod:`tests.test_soldas` e :mod:`tests.test_ligacoes_soldadas` com o que a revisão de
30/10/2026 acrescentou: os itens vistos no texto da 2025 (Tabela 9 e notas, 6.1.5, 6.1.8, 6.2.5.2 a
c, 6.5.3 a 6.5.6), o metal-base da penetração parcial, a perna comercial sugerida, o detalhamento e
os grupos da tabela resumida, e os casos de borda do grupo de filetes.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import bolted_joint_check as chk
from core import cantoneiras as ct
from core import ligacoes as lg
from core import ligacoes_soldadas as ls
from core import soldas as sd


def linha(r: lg.ResultadoLigacao, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


# ------------------------------------------------------------------ referências da 2025
@pytest.mark.parametrize(
    "texto",
    [
        "6.1.5.2", "6.1.8.2", "6.2.5.2 c)", "6.5.3 a)", "6.5.3 e 6.5.4", "6.5.5 b)", "6.5.6",
        # parte 2 do texto (30/10/2026)
        "6.2.2.2 d)", "6.2.6.2.2", "6.2.6.2.5", "5.2.2 a)", "5.3", "5.7.2.1", "6.5.4 b) e item 5.3",
        # fotos de 5.2.4 e 5.2.5 (30/10/2026)
        "5.2.5", "5.2.4 a)", "5.2.2 b), 5.2.4.2 e 5.2.5",
    ],
)  # fmt: skip
def test_itens_vistos_no_texto_da_2025_saem_sem_marca(texto):
    assert not sd.a_confirmar(sd.ref(sd.NBR_2025, texto))


@pytest.mark.parametrize(
    "texto",
    ["Tabela 8", "6.3.5", "5.4.2.1"],  # tabela sem marca explícita e itens que não vieram
)
def test_itens_ainda_nao_vistos_ficam_a_confirmar(texto):
    assert sd.a_confirmar(sd.ref(sd.NBR_2025, texto))
    assert not sd.a_confirmar(sd.ref(sd.NBR_2008, texto))  # a 2008 foi conferida


def test_deformacao_na_tensao_maxima_e_da_propria_nbr():
    # 6.2.5.2 b) da 2025: Δm = 0,209·(θ + 2)^−0,32·d_w (antes vinha do AISC J2.4)
    assert sd.deformacao_na_tensao_maxima(0.0, 6.0) == pytest.approx(0.209 * 2**-0.32 * 6.0)
    r = lg.calcular(lg.EntradaSolda(m_sd_kNm=2.0))
    assert "AISC" not in r.verificacoes[0].formula and "6.2.5.2 b)" in r.verificacoes[0].referencia


def test_compatibilidade_aponta_a_tabela_8_da_2025():
    r = lg.calcular(ls.EntradaChapaNoApoio(tipo_solda=ls.TIPO_TOTAL, modo=ls.MODO_VERIFICAR))
    ref = linha(r, "Penetração total: metal da solda compatível").referencia
    assert ref == "NBR 8800:2025 Tabela 9, compatibilidade, e Tabela 8"  # Tabela 8 vista
    antiga = lg.calcular(
        ls.EntradaChapaNoApoio(tipo_solda=ls.TIPO_TOTAL, modo=ls.MODO_VERIFICAR, norma=sd.NBR_2008)
    )
    assert linha(antiga, "Penetração total: metal da solda compatível").referencia == (
        "NBR 8800:2008 Tabela 7"
    )


def test_chapa_de_ligacao_parafusada_cita_a_6_5_3_sem_marca():
    from tests.test_memorial_ligacao_parafusada import M22

    r = chk.verificar_ligacao(M22)
    escoamento = linha_parafusada(r, "Chapa de ligação — escoamento da seção bruta")
    assert escoamento.referencia == "NBR 8800:2025, 6.5.3"


def linha_parafusada(r, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


# ------------------------------------------------------------------ penetração parcial
def test_penetracao_parcial_verifica_o_metal_base_da_tabela_9():
    # Tabela 9: tração normal na parcial = o menor entre A_MB·f_y/γ_a1 e 0,6·A_w·f_w/γ_w1
    e = ls.EntradaChapaNoApoio(
        tipo_solda=ls.TIPO_PARCIAL, modo=ls.MODO_VERIFICAR, intermitente=False,
        t_chapa_mm=6.35, t_apoio_mm=6.35, profundidade_mm=2.5, comprimento_mm=100.0,
        n_sd_kN=120.0,
    )  # fmt: skip
    r = lg.calcular(e)
    mb = linha(r, "Penetração parcial: tração normal (metal-base)")
    assert mb.resistente == pytest.approx(6.35 * 100 * 250 / 1.10 / 1000)
    assert mb.status == "OK" and mb.solicitante == pytest.approx(120.0)
    com_momento = lg.calcular(replace(e, m_sd_kNm=1.0))
    assert linha(com_momento, "Penetração parcial: tração normal e momento").unidade == "—"


# ------------------------------------------------------------------ perna estimada e sugerida
def test_perna_sugerida_e_a_menor_comercial_que_passa_em_tudo():
    e = lg.EntradaSolda(v_sd_kN=180.0, perna_mm=5.0, t1_mm=12.5, t2_mm=12.5)
    r = lg.calcular(e)
    estimada, sugerida = r.grandezas["perna_estimada_mm"], r.grandezas["perna_sugerida_mm"]
    assert estimada == pytest.approx(5.0 * r.verificacoes[0].aproveitamento)
    assert sugerida in lg.PERNAS_COMERCIAIS and sugerida >= estimada
    refeito = lg.calcular(replace(e, perna_mm=sugerida))
    assert all(v.status == "OK" for v in refeito.verificacoes)
    menor = [p for p in lg.PERNAS_COMERCIAIS if estimada <= p < sugerida]
    for perna in menor:  # nenhuma perna comercial menor atende
        assert lg.calcular(replace(e, perna_mm=perna)).status != "OK"


def test_perna_sugerida_respeita_a_perna_minima():
    # carga pequena: a resistência pede < 1 mm, mas a perna mínima da chapa de 8 mm é 5 mm
    r = lg.calcular(lg.EntradaSolda())
    assert r.grandezas["perna_estimada_mm"] < 1.0 and r.grandezas["perna_sugerida_mm"] == 5.0


def test_sem_perna_que_atenda_quando_o_metal_base_reprova():
    r = lg.calcular(lg.EntradaSolda(v_sd_kN=400.0, perna_mm=4.0))
    assert linha(r, "Metal-base junto à solda").status == "NÃO OK"
    assert "perna_sugerida_mm" not in r.grandezas
    texto = dict(lg.detalhamento_adotado(r))["Perna comercial que atende"]
    assert texto.startswith("nenhuma")


def test_chapa_fina_nao_estima_perna():
    r = lg.calcular(lg.EntradaSolda(t1_mm=3.0, perna_mm=3.0))
    assert "perna_estimada_mm" not in r.grandezas


# ------------------------------------------------------------------ grupo de filetes: casos de borda
def test_momento_troca_o_metodo_para_o_centro_instantaneo():
    sem = lg.calcular(lg.EntradaSolda(n_sd_kN=20.0))
    com = lg.calcular(lg.EntradaSolda(n_sd_kN=20.0, m_sd_kNm=1.5))
    assert "6.2.5.2 a)" in sem.verificacoes[0].referencia
    assert "6.2.5.2 b)" in com.verificacoes[0].referencia


def test_centro_instantaneo_que_nao_converge_volta_ao_elastico(monkeypatch):
    def nao_converge(*_args, **_kwargs):
        return sd.ResultadoCentroInstantaneo(0.0, 0.0, 0.0, False, 0.0)

    monkeypatch.setattr(sd, "centro_instantaneo", nao_converge)
    e = lg.EntradaSolda(m_sd_kNm=2.0)
    r = lg.calcular(e)
    elastico = lg.calcular(replace(e, metodo=lg.METODO_ELASTICO))
    assert r.verificacoes[0].resistente == pytest.approx(elastico.verificacoes[0].resistente)
    assert any("não convergiu" in a for a in r.avisos)


def test_momento_puro_no_contorno_tem_capacidade_em_kN_m():
    r = lg.calcular(lg.EntradaSolda(arranjo=lg.ARRANJO_CONTORNO, v_sd_kN=0.0, m_sd_kNm=3.0))
    metal = r.verificacoes[0]
    assert metal.unidade == "kN·m" and metal.solicitante == 3.0 and metal.resistente > 3.0


def test_limites_de_perna_minima_e_maxima_no_grupo():
    grossa = lg.calcular(lg.EntradaSolda(perna_mm=8.0, t1_mm=8.0))  # máx. 8 − 1,5 = 6,5 mm
    assert linha(grossa, "Solda: perna máxima").status == "NÃO OK"
    fina = lg.calcular(lg.EntradaSolda(perna_mm=3.0, t1_mm=16.0, t2_mm=16.0))  # mín. 6 mm
    assert linha(fina, "Solda: perna mínima").status == "NÃO OK"


def test_intermitente_so_quando_a_continua_de_perna_minima_sobra():
    e = ls.EntradaChapaNoApoio(modo=ls.MODO_VERIFICAR, n_sd_kN=600.0, comprimento_mm=100.0)
    assert linha(lg.calcular(e), "Solda intermitente: permitida").status == "NÃO OK"
    leve = replace(e, n_sd_kN=40.0)
    assert linha(lg.calcular(leve), "Solda intermitente: permitida").status == "OK"


def test_filete_longo_reduz_com_beta_na_barra():
    curta = lg.calcular(
        ls.EntradaBarraSoldada(
            modo=ls.MODO_VERIFICAR, com_apoio=False, l_dorso_mm=120.0, l_borda_mm=120.0
        )
    )
    longa = lg.calcular(
        ls.EntradaBarraSoldada(
            modo=ls.MODO_VERIFICAR, com_apoio=False, l_dorso_mm=600.0, l_borda_mm=600.0
        )
    )
    beta = sd.beta_filete_longo(600.0, 4.0)
    assert beta < 1.0
    dorso_curto = linha(curta, "Filete do dorso").resistente / 120.0
    dorso_longo = linha(longa, "Filete do dorso").resistente / 600.0
    assert dorso_longo == pytest.approx(dorso_curto * beta, rel=1e-6)


def test_chapa_de_no_a_tracao_e_a_compressao():
    r = lg.calcular(ls.EntradaBarraSoldada(n_c_sd_kN=80.0, com_apoio=False))
    nomes = [v.nome for v in r.verificacoes]
    assert any(n.startswith("Chapa de nó: tração na seção de Whitmore") for n in nomes)
    assert any(n.startswith("Chapa de nó: compressão") for n in nomes)


# ------------------------------------------------------------------ resumo da tela
def test_detalhamento_da_barra_em_texto_completo():
    r = lg.calcular(ls.EntradaBarraSoldada())
    d = dict(lg.detalhamento_adotado(r))
    assert d["Filete do dorso"] == f"{r.grandezas['l_dorso_mm']:.0f} mm"
    assert d["Filete da borda"] == f"{r.grandezas['l_borda_mm']:.0f} mm"
    assert d["Solda da chapa de nó no apoio"].startswith("dois filetes de 6 mm × 50 mm")
    assert "Filetes adotados" not in d  # a linha informativa não se repete


def test_grupos_da_tabela_resumida_na_ordem_do_calculo():
    r = lg.calcular(ls.EntradaBarraSoldada())
    grupos = [g for g, _ in lg.verificacoes_por_grupo(r)]
    assert grupos == [
        lg.GRUPO_SOLDA, lg.GRUPO_BARRA, lg.GRUPO_CHAPA_DE_NO, lg.GRUPO_SOLDA_NO_APOIO,
        lg.GRUPO_LIMITES,
    ]  # fmt: skip
    total = sum(len(linhas) for _, linhas in lg.verificacoes_por_grupo(r))
    assert total == sum(1 for v in r.verificacoes if v.tipo != "informativo")
    no_apoio = dict(lg.verificacoes_por_grupo(r))[lg.GRUPO_SOLDA_NO_APOIO]
    assert all(not lg.nome_no_grupo(v).startswith("Chapa de nó no apoio") for v in no_apoio)


def test_frase_e_referencias_pendentes():
    ok = lg.calcular(lg.EntradaSolda())
    assert lg.frase_do_resultado(ok).startswith("Atende às verificações executadas")
    assert all("(a confirmar)" in ref for ref in lg.referencias_pendentes(ok))
    ruim = lg.calcular(lg.EntradaSolda(v_sd_kN=400.0, perna_mm=4.0))
    assert lg.frase_do_resultado(ruim).startswith("Não atende")
    antiga = lg.calcular(lg.EntradaSolda(norma=sd.NBR_2008))
    assert lg.referencias_pendentes(antiga) == []


@pytest.mark.parametrize(
    "entrada",
    [
        lg.EntradaSolda(m_sd_kNm=2.0, n_sd_kN=-10.0, v_sd_kN=-30.0),
        ls.EntradaBarraSoldada(peca=ls.PECA_CHAPA, solda_na_ponta=True, theta_graus=90.0),
        ls.EntradaChapaNoApoio(apoio=ls.APOIO_PERFIL, perfil_apoio=ls.perfis_de_apoio()[0]),
    ],
)
def test_figuras_com_legenda_saem_em_png(entrada):
    desenho = lg.figura(lg.calcular(entrada))
    assert desenho.png.startswith(b"\x89PNG") and desenho.largura_px >= 900


# ------------------------------------------------------------------ parte 2 do texto da 2025
def test_perna_maxima_na_borda_a_partir_de_6_3_mm_na_2025():
    # 6.2.6.2.2: "inferior a 6,3 mm" na 2025 (6,35 na 2008)
    assert sd.perna_maxima(6.3) == pytest.approx(4.8)
    assert sd.perna_maxima(6.3, sd.NBR_2008) == 6.3
    assert sd.perna_maxima(6.0) == 6.0 and sd.perna_maxima(6.35) == pytest.approx(4.85)
    r = lg.calcular(lg.EntradaSolda(perna_mm=5.0, t1_mm=6.3, t2_mm=6.3))
    assert linha(r, "Solda: perna máxima").status == "NÃO OK"
    antiga = lg.calcular(lg.EntradaSolda(perna_mm=5.0, t1_mm=6.3, t2_mm=6.3, norma=sd.NBR_2008))
    assert linha(antiga, "Solda: perna máxima").status == "OK"


def test_filete_muito_longo_para_em_180_pernas_na_2025():
    # 6.2.2.2 d) da 2025: L > 300·d_w → comprimento efetivo 180·d_w (a 2008 fica em 0,6·L)
    assert sd.comprimento_efetivo_longitudinal(1200.0, 4.0, sd.NBR_2025) == pytest.approx(720.0)
    assert sd.comprimento_efetivo_longitudinal(2000.0, 4.0, sd.NBR_2025) == pytest.approx(720.0)
    assert sd.comprimento_efetivo_longitudinal(2000.0, 4.0, sd.NBR_2008) == pytest.approx(1200.0)
    e = ls.EntradaBarraSoldada(
        modo=ls.MODO_VERIFICAR, com_apoio=False, l_dorso_mm=2000.0, l_borda_mm=2000.0
    )
    r = lg.calcular(e)
    dorso = linha(r, "Filete do dorso")
    q = dorso.resistente / 720.0  # resistência por mm no comprimento efetivo
    assert "180·d_w" in dorso.formula
    antiga = linha(lg.calcular(replace(e, norma=sd.NBR_2008)), "Filete do dorso")
    assert antiga.resistente == pytest.approx(q * 1200.0)


def test_dimensionar_nao_passa_de_300_pernas_quando_nem_180_bastam():
    e = ls.EntradaBarraSoldada(n_t_sd_kN=1500.0, com_apoio=False, perna_mm=4.0, t_no_mm=25.0)
    r = lg.calcular(e)
    assert r.grandezas["l_dorso_mm"] <= 300 * 4.0 + 5.0
    assert linha(r, "Filete do dorso").status == "NÃO OK"


def test_garganta_da_penetracao_parcial_pela_tabela_6_da_2025():
    e = ls.EntradaChapaNoApoio(tipo_solda=ls.TIPO_PARCIAL, modo=ls.MODO_VERIFICAR)
    nova = linha(lg.calcular(e), "Solda: metal da solda (penetração parcial)")
    antiga = linha(
        lg.calcular(replace(e, norma=sd.NBR_2008)), "Solda: metal da solda (penetração parcial)"
    )
    assert "Tabela 6" in nova.formula and "Tabela 5" in antiga.formula


# ------------------------------------------------------------------ 5.2.4 e 5.2.5 da 2025 (fotos)
FU_A36 = 400.0


def _sem_linha(r: lg.ResultadoLigacao, inicio: str) -> bool:
    return not any(v.nome.startswith(inicio) for v in r.verificacoes)


@pytest.mark.parametrize(
    "entrada",
    [ls.EntradaBarraSoldada(), ls.EntradaBarraSoldada(peca=ls.PECA_CHAPA, com_apoio=False)],
)
def test_barra_soldada_sem_referencia_pendente(entrada):
    r = lg.calcular(entrada)
    assert lg.referencias_pendentes(r) == []
    ruptura = linha(r, "Barra: tração (ruptura")
    assert ruptura.referencia == "NBR 8800:2025 5.2.2 b), 5.2.4.2 e 5.2.5"
    assert "A_n = A_g (sem furos, 5.2.4.2)" in ruptura.formula


def test_ct_da_chapa_so_com_filetes_longitudinais_pela_formula_da_2025():
    # 5.2.5 d) da 2025: C_t = 3ℓ_c²/(3ℓ_c² + b²)·(1 − t/(2ℓ_c)), ℓ_c = média dos dois filetes
    e = ls.EntradaBarraSoldada(
        peca=ls.PECA_CHAPA, largura_mm=50.0, t_peca_mm=9.525, com_apoio=False,
        modo=ls.MODO_VERIFICAR, l_dorso_mm=60.0, l_borda_mm=80.0,
    )  # fmt: skip
    area, lc = 50.0 * 9.525, 70.0
    ct_ = 3 * lc**2 / (3 * lc**2 + 50.0**2) * (1 - 9.525 / (2 * lc))
    nova = linha(lg.calcular(e), "Barra: tração (ruptura")
    assert nova.resistente == pytest.approx(ct_ * area * FU_A36 / 1.35 / 1000)
    # a 2008 fica nos degraus, pelo menor filete: 1,5b > 60 ≥ b → 0,75
    antiga = linha(lg.calcular(replace(e, norma=sd.NBR_2008)), "Barra: tração (ruptura")
    assert antiga.resistente == pytest.approx(0.75 * area * FU_A36 / 1.35 / 1000)


def test_chapa_com_filete_menor_que_a_largura_reprova_por_6_2_6_2_3():
    e = ls.EntradaBarraSoldada(
        peca=ls.PECA_CHAPA, largura_mm=50.0, t_peca_mm=9.525, com_apoio=False,
        modo=ls.MODO_VERIFICAR, l_dorso_mm=40.0, l_borda_mm=40.0,
    )  # fmt: skip
    nova = lg.calcular(e)
    assert linha(nova, "Solda: cada filete").status == "NÃO OK"
    assert _sem_linha(nova, "Barra: ligação permitida")  # a 2025 não proíbe pelo C_t
    antiga = lg.calcular(replace(e, norma=sd.NBR_2008))
    assert linha(antiga, "Barra: ligação permitida").status == "NÃO OK"  # 5.2.5 d) da 2008


def test_ct_da_cantoneira_sem_o_teto_de_0_90_na_2025():
    cant = ct.obter_cantoneira('L 2" × 1/4"')
    e = ls.EntradaBarraSoldada(
        modo=ls.MODO_VERIFICAR, com_apoio=False, l_dorso_mm=300.0, l_borda_mm=300.0
    )
    bruto = 1 - cant.x_barra_mm / 300.0
    assert bruto > 0.90
    nova = linha(lg.calcular(e), "Barra: tração (ruptura")
    assert nova.resistente == pytest.approx(bruto * cant.area_mm2 * FU_A36 / 1.35 / 1000)
    antiga = linha(lg.calcular(replace(e, norma=sd.NBR_2008)), "Barra: tração (ruptura")
    assert antiga.resistente == pytest.approx(0.90 * cant.area_mm2 * FU_A36 / 1.35 / 1000)


def test_ct_da_cantoneira_curta_fica_em_ac_sobre_ag_na_2025():
    # "não precisa ser considerado menor que A_c/A_g" (seções abertas); a 2008 proíbe C_t < 0,60
    cant = ct.obter_cantoneira('L 2" × 1/4"')
    e = ls.EntradaBarraSoldada(
        modo=ls.MODO_VERIFICAR, com_apoio=False, l_dorso_mm=30.0, l_borda_mm=30.0
    )
    piso = cant.area_aba_mm2 / cant.area_mm2
    assert 1 - cant.x_barra_mm / 30.0 < piso
    nova = lg.calcular(e)
    resistente = piso * cant.area_mm2 * FU_A36 / 1.35 / 1000
    assert linha(nova, "Barra: tração (ruptura").resistente == pytest.approx(resistente)
    assert _sem_linha(nova, "Barra: ligação permitida")
    antiga = lg.calcular(replace(e, norma=sd.NBR_2008))
    assert linha(antiga, "Barra: ligação permitida").status == "NÃO OK"


def test_parafusos_com_ct_abaixo_de_0_60_so_e_proibido_na_2008():
    base = chk.EntradaLigacao(designacao="M16", N=44.8, valores_sao_de_calculo=True, A_g=1542.0)
    l_c = (base.n_col - 1) * base.s
    curta = replace(base, e_c=0.5 * l_c, norma="NBR8800_2008")
    antiga = chk.verificar_ligacao(curta)
    proibida = next(v for v in antiga.verificacoes if v.nome.endswith("permitida pelo C_t"))
    assert proibida.status == "NÃO OK" and proibida.tipo == "limite"
    nova = chk.verificar_ligacao(replace(curta, norma="NBR8800_2024"))
    assert not any(v.nome.endswith("permitida pelo C_t") for v in nova.verificacoes)
    # o teto de 0,90 da 2008 aparece na fórmula quando corta
    longa = chk.verificar_ligacao(replace(base, e_c=1.0, norma="NBR8800_2008"))
    tracao = next(v for v in longa.verificacoes if v.nome == "Tração da peça (N_t,Rd)")
    assert "limitado a 0,90" in tracao.formula
