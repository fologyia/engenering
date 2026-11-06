"""Molas de tração, de torção e prato, conferidas à mão ou por um segundo caminho."""

from __future__ import annotations

import math

import pytest

from core import elementos_catalogo as cat
from core import elementos_molas as ml
from core.elementos_base import Resultado, calcular_caso

ACO_DURO = "ASTM A227 trefilado duro"
CORDA = "ASTM A228 corda de piano"


def rodar(caso_id: str, **valores) -> Resultado:
    return calcular_caso(cat.CASOS[caso_id], valores)


def metrica(resultado: Resultado, rotulo: str) -> float:
    return next(float(m.valor) for m in resultado.metricas if m.rotulo == rotulo)


def linha(resultado: Resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


# ---------------------------------------------------------------------------
# Tração
# ---------------------------------------------------------------------------


def test_tracao_rigidez_e_comprimento_a_mao():
    # C = 8; N_a = 12 + 80/197,9 = 12,404; k = 80000·81/(8·13824·12,404)
    r = rodar("mola_tracao", d_mm=3.0, D_mm=24.0, espiras=12.0, fio=ACO_DURO)
    assert metrica(r, "Rigidez k") == pytest.approx(4.7238, rel=1e-3)
    assert metrica(r, "Comprimento livre") == pytest.approx((2 * 8 - 1 + 12) * 3)  # eq. 10-39
    assert metrica(r, "Abertura na força máxima") == pytest.approx((150 - 45) / 4.7238, rel=1e-3)


def test_tracao_tensoes_no_corpo_e_no_gancho_a_mao():
    r = rodar("mola_tracao", d_mm=3.0, D_mm=24.0, r2_mm=6.0, f_max_N=150.0, fio=ACO_DURO)
    base = 8 * 150 * 24 / (math.pi * 27)
    assert metrica(r, "Tensão no corpo") == pytest.approx(34 / 29 * base, rel=1e-6)  # K_B
    assert metrica(r, "Torção no gancho") == pytest.approx(15 / 12 * base, rel=1e-6)  # C₂ = 4
    flexao = 150 * (247 / 224 * 16 * 24 / (math.pi * 27) + 4 / (math.pi * 9))  # C₁ = 8
    assert metrica(r, "Flexão no gancho") == pytest.approx(flexao, rel=1e-6)


def test_tracao_tabela_10_7_sai_nas_tres_verificacoes():
    r = rodar("mola_tracao", fio=ACO_DURO)
    sut = 1783.0 / 3.0**0.190
    assert linha(r, "Tensão no corpo").resistente == pytest.approx(
        0.45 * sut / metrica(r, "Tensão no corpo")
    )
    assert linha(r, "Torção no gancho (ponto B)").resistente == pytest.approx(
        0.40 * sut / metrica(r, "Torção no gancho")
    )
    assert linha(r, "Flexão no gancho (ponto A)").resistente == pytest.approx(
        0.75 * sut / metrica(r, "Flexão no gancho")
    )


def test_tracao_dobra_fechada_no_gancho_e_o_que_reprova():
    aberta = rodar("mola_tracao", f_max_N=170.0, r2_mm=6.0)
    fechada = rodar("mola_tracao", f_max_N=170.0, r2_mm=2.0)
    assert linha(aberta, "Torção no gancho (ponto B)").status == "OK"
    assert linha(fechada, "Torção no gancho (ponto B)").status == "NÃO OK"


def test_tensao_inicial_faixa_da_equacao_10_41():
    baixo, alto = ml.faixa_da_tensao_inicial(8.0)
    meio = 231.0 / math.exp(0.84)
    largura = 6.9 * (4 - 5 / 6.5)
    assert (baixo, alto) == pytest.approx((meio - largura, meio + largura))
    assert 75 < baixo < 80 and 120 < alto < 125


def test_tracao_tensao_inicial_alta_baixa_o_limite_do_corpo():
    """Nota da Tabela 10-7: com tensão inicial alta, o corpo usa o percentual da ponta."""
    normal = rodar("mola_tracao", f_inicial_N=45.0)
    alta = rodar("mola_tracao", f_inicial_N=100.0)
    assert linha(alta, "Tensão inicial").status == "ALERTA"
    assert linha(alta, "Tensão no corpo").resistente == pytest.approx(
        linha(normal, "Tensão no corpo").resistente * 0.40 / 0.45
    )


def test_tracao_fadiga_de_zimmerli_a_mao():
    r = rodar("mola_tracao", f_max_N=150.0, f_min_N=60.0, fio=ACO_DURO, ciclica=True)
    sut = 1783.0 / 3.0**0.190
    sse = 241.0 / (1.0 - 379.0 / (0.67 * sut))
    flexao = 247 / 224 * 16 * 24 / (math.pi * 27) + 4 / (math.pi * 9)
    esperado = 1.0 / (45 * flexao / (sse / 0.577) + 105 * flexao / sut)
    assert linha(r, "Fadiga no gancho (ponto A)").resistente == pytest.approx(esperado, rel=1e-6)


def test_tracao_forca_menor_que_a_inicial_e_recusada():
    with pytest.raises(ValueError, match="nem abre"):
        rodar("mola_tracao", f_max_N=40.0, f_inicial_N=45.0, f_min_N=10.0)


def test_tracao_forca_minima_abaixo_da_inicial_avisa():
    r = rodar("mola_tracao", f_min_N=20.0, f_inicial_N=45.0)
    assert any("mola está fechada" in a for a in r.alertas)


def test_tracao_dobra_menor_que_o_raio_do_fio_e_recusada():
    with pytest.raises(ValueError, match="dobra do gancho"):
        rodar("mola_tracao", r2_mm=1.0, d_mm=3.0)


# ---------------------------------------------------------------------------
# Torção
# ---------------------------------------------------------------------------


def test_torcao_rigidez_confere_com_castigliano():
    """Sem pernas, θ = M·L/(E·I) em radianos; o 10,8 é o 10,19 teórico mais o atrito."""
    d, diametro, corpo, e = 3.0, 20.0, 8.0, 196_500.0
    r = rodar(
        "mola_torcao",
        fio=CORDA,
        d_mm=d,
        D_mm=diametro,
        espiras=corpo,
        l1_mm=0.0,
        l2_mm=0.0,
        d_pino_mm=0.0,
        f_max_N=40.0,
        braco_mm=40.0,
    )
    momento = 1600.0
    inercia = math.pi * d**4 / 64
    teorico_graus = math.degrees(momento * math.pi * diametro * corpo / (e * inercia))
    teorico_por_volta = 64.0 / (2.0 * math.pi)  # o 10,19 do livro
    assert metrica(r, "Giro na força máxima") == pytest.approx(
        teorico_graus * 10.8 / teorico_por_volta, rel=1e-3
    )


def test_torcao_pernas_somam_espiras_equivalentes():
    r = rodar("mola_torcao", D_mm=20.0, espiras=8.0, l1_mm=30.0, l2_mm=30.0)
    assert metrica(r, "Espiras ativas equivalentes") == pytest.approx(
        8 + 60 / (3 * math.pi * 20), rel=1e-3
    )


def test_torcao_tensao_com_fator_de_fibra_interna_a_mao():
    r = rodar("mola_torcao", d_mm=3.0, D_mm=24.0, f_max_N=40.0, braco_mm=40.0)
    k_i = (4 * 64 - 8 - 1) / (4 * 8 * 7)
    assert metrica(r, "Tensão na força máxima") == pytest.approx(
        k_i * 32 * 1600 / (math.pi * 27), rel=1e-6
    )


@pytest.mark.parametrize(
    ("fio", "fracao"),
    [(CORDA, 0.78), (ACO_DURO, 0.78), ("ASTM A229 óleo-temperado", 0.87)],
)
def test_torcao_limite_em_flexao_e_o_do_livro(fio, fracao):
    r = rodar("mola_torcao", fio=fio)
    assert metrica(r, "Limite S_y em flexão") / metrica(
        r, "Resistência S_ut do fio"
    ) == pytest.approx(fracao, abs=0.005)


def test_torcao_mola_fecha_sobre_o_pino():
    folgada = rodar("mola_torcao", d_pino_mm=14.0)
    interno = metrica(folgada, "Diâmetro interno sob carga")
    assert interno < 20.0 - 3.0
    assert linha(folgada, "Diâmetro do pino").status == "OK"
    # O pino cabe na mola parada, mas não com a mola fechada.
    presa = rodar("mola_torcao", d_pino_mm=16.9)
    assert linha(presa, "Diâmetro do pino").status == "NÃO OK"


def test_torcao_sem_pino_nao_verifica_folga():
    r = rodar("mola_torcao", d_pino_mm=0.0)
    assert all(v.nome != "Diâmetro do pino" for v in r.verificacoes)


def test_diametro_sob_carga_usa_so_o_giro_do_corpo():
    """Eq. 10-53: as pernas giram, mas não fecham a hélice."""
    curtas = rodar("mola_torcao", l1_mm=0.0, l2_mm=0.0)
    longas = rodar("mola_torcao", l1_mm=60.0, l2_mm=60.0)
    assert metrica(curtas, "Diâmetro interno sob carga") == pytest.approx(
        metrica(longas, "Diâmetro interno sob carga")
    )
    assert metrica(longas, "Giro na força máxima") > metrica(curtas, "Giro na força máxima")


def test_gerber_com_carga_repetida_devolve_a_tensao_recomendada():
    """Com σ_m = σ_a, que é R = 0, a amplitude admissível é S_r/2."""
    assert ml.amplitude_de_gerber(1.0, 900.0, 1800.0) == pytest.approx(450.0)


def test_gerber_com_media_zero_devolve_o_limite_de_fadiga():
    s_r, sut = 900.0, 1800.0
    assert ml.amplitude_de_gerber(0.0, s_r, sut) == pytest.approx(450.0 / (1 - 0.25**2))


@pytest.mark.parametrize(
    ("fio", "vida", "superficie", "fracao"),
    [
        (CORDA, ml.VIDA_100_MIL, ml.SEM_JATEAMENTO, 0.53),
        (CORDA, ml.VIDA_1_MILHAO, ml.JATEADA, 0.60),
        (ml.FIO_A232, ml.VIDA_100_MIL, ml.JATEADA, 0.64),
        (ml.FIO_A232, ml.VIDA_1_MILHAO, ml.JATEADA, 0.62),
        (ml.FIO_A232, ml.VIDA_1_MILHAO, ml.SEM_JATEAMENTO, 0.53),
        (ACO_DURO, ml.VIDA_1_MILHAO, ml.SEM_JATEAMENTO, 0.50),  # fora da tabela: coluna do A228
    ],
)
def test_torcao_fadiga_usa_a_tabela_10_10(fio, vida, superficie, fracao):
    r = rodar("mola_torcao", fio=fio, vida=vida, superficie=superficie, ciclica=True)
    assert f"S_r = {fracao * 100:.0f} % de S_ut" in linha(r, "Fadiga da mola").formula


def test_torcao_exemplo_abre_com_a_fadiga_aprovada():
    assert linha(rodar("mola_torcao"), "Fadiga da mola").status == "OK"


# ---------------------------------------------------------------------------
# Prato
# ---------------------------------------------------------------------------

A40 = ml.Disco(40.0, 20.4, 2.25, 0.9)


def test_prato_coeficientes_publicados_para_razao_2():
    disco = ml.Disco(40.0, 20.0, 2.0, 1.0)
    assert disco.k1 == pytest.approx(0.694, abs=0.001)
    assert disco.k2 == pytest.approx(1.220, abs=0.001)
    assert disco.k3 == pytest.approx(1.378, abs=0.001)


def test_prato_disco_a40_da_a_forca_de_catalogo():
    """Série A, 40 × 20,4 × 2,25: conta à mão com K₁ = 0,6866 dá 6,50 kN a 0,75·h₀."""
    assert A40.forca(0.75 * 0.9) == pytest.approx(6497.0, rel=2e-3)


def test_prato_sigma_om_nao_depende_da_altura_do_cone():
    baixo = ml.Disco(40.0, 20.4, 2.25, 0.5).tensoes(0.3)["OM"]
    alto = ml.Disco(40.0, 20.4, 2.25, 1.2).tensoes(0.3)["OM"]
    assert baixo == pytest.approx(alto)


def test_prato_sinais_das_tensoes():
    t = A40.tensoes(0.675)
    assert t["OM"] < 0 and t["I"] < 0 and t["IV"] < 0
    assert t["II"] > 0 and t["III"] > 0
    assert abs(t["I"]) > abs(t["OM"])


def test_prato_tensoes_nulas_sem_deflexao():
    assert all(valor == 0.0 for valor in A40.tensoes(0.0).values())


@pytest.mark.parametrize("s", [0.1, 0.45, 0.8])
def test_prato_rigidez_confere_com_derivada_numerica(s):
    passo = 1e-5
    numerica = (A40.forca(s + passo) - A40.forca(s - passo)) / (2 * passo)
    assert A40.rigidez(s) == pytest.approx(numerica, rel=1e-5)


def test_prato_deflexao_e_o_inverso_da_forca():
    assert A40.deflexao(A40.forca(0.42)) == pytest.approx(0.42, abs=1e-9)


def test_prato_curva_so_tem_pico_acima_de_raiz_de_dois():
    assert ml.Disco(40.0, 20.4, 2.0, 2.0).curso == pytest.approx(2.0)  # h/t = 1
    assert ml.Disco(40.0, 20.4, 1.0, 1.41).curso == pytest.approx(1.41)  # ainda sem pico
    disco = ml.Disco(40.0, 20.4, 1.0, 2.0)  # h/t = 2
    assert disco.curso == pytest.approx(2.0 - math.sqrt(6.0) / 3.0)
    assert disco.rigidez(disco.curso) == pytest.approx(0.0, abs=1e-6)
    assert disco.rigidez(disco.curso + 0.1) < 0


def test_prato_pilha_em_serie_e_paralelo():
    um = rodar("mola_prato", grupos=1, por_grupo=1, f_max_N=3000.0, f_min_N=1000.0)
    pilha = rodar("mola_prato", grupos=4, por_grupo=2, f_max_N=6000.0, f_min_N=2000.0)
    assert metrica(pilha, "Deflexão da pilha") == pytest.approx(
        4 * metrica(um, "Deflexão da pilha")
    )
    assert metrica(pilha, "Rigidez na força máxima") == pytest.approx(
        metrica(um, "Rigidez na força máxima") * 2 / 4
    )
    assert metrica(pilha, "Altura livre da pilha") == pytest.approx(4 * (0.9 + 2 * 2.25))
    assert metrica(pilha, "Discos na pilha") == 8


def test_prato_forca_alem_do_disco_plano_e_recusada():
    with pytest.raises(ValueError, match="só chega a"):
        rodar("mola_prato", f_max_N=20000.0)


def test_prato_curso_alem_de_75_por_cento_pede_atencao():
    assert linha(rodar("mola_prato", f_max_N=7500.0), "Curso de trabalho").status == "ALERTA"
    assert linha(rodar("mola_prato", f_max_N=5000.0), "Curso de trabalho").status == "OK"


def test_prato_limite_de_tensao_e_um_dado_e_reprova():
    assert linha(rodar("mola_prato"), "Compressão na parede (σ_OM)").status == "OK"
    apertado = rodar("mola_prato", limite_MPa=500.0)
    assert linha(apertado, "Compressão na parede (σ_OM)").status == "NÃO OK"


def test_prato_sem_precarga_pede_atencao_e_fadiga_nao_e_inventada():
    r = rodar("mola_prato", f_min_N=100.0, ciclica=True)
    assert linha(r, "Pré-carga mínima").status == "ALERTA"
    assert any("diagrama da DIN EN 16984" in a for a in r.alertas)
    assert not [v for v in r.verificacoes if v.nome.startswith("Fadiga")]


def test_prato_tensoes_de_fadiga_saem_como_informacao():
    r = rodar("mola_prato", f_max_N=5000.0, f_min_N=1500.0, ciclica=True)
    superior = next(v for v in r.verificacoes if v.nome.startswith("σ_o no ponto"))
    inferior = next(v for v in r.verificacoes if v.nome.startswith("σ_u no ponto"))
    variacao = linha(r, "Variação de tensão σ_h")
    assert superior.status == inferior.status == "INFO"
    assert variacao.solicitante == pytest.approx(superior.solicitante - inferior.solicitante)
    assert superior.solicitante > inferior.solicitante > 0


def test_prato_acima_de_raiz_de_dois_avisa_do_salto():
    r = rodar("mola_prato", t_mm=1.0, h0_mm=1.6, f_max_N=500.0, f_min_N=200.0)
    assert any("mecanismo de salto" in a for a in r.alertas)


def test_prato_curva_vai_ate_o_disco_plano_e_marca_o_ponto_de_trabalho():
    r = rodar("mola_prato", grupos=2, por_grupo=1)
    grafico = r.graficos[0]
    assert grafico.pontos[0][:2] == (0.0, 0.0)
    assert grafico.pontos[-1][0] == pytest.approx(2 * 0.9)
    assert grafico.destaques[0][1] == pytest.approx(5000.0)
