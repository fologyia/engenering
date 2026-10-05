"""
Testes de aceitação do módulo `core.bolted_connection` (portado do módulo de referência).

Rodar:   pytest -q tests/test_bolted_connection.py

Fontes dos valores esperados:
  • AISC Design Guide 29 (Vertical Bracing Connections), exemplo da pág. 157–159 (10 × 1" A325-N,
    2L4×4×3/8, A36, e = 1 1/4", s = 3") e exemplo da pág. 185–186 (7/8" A325-N, mesmas chapas). LRFD.
  • Planilha calculo_parafuso_revisado.xlsx (validada contra o DG29), caso real: emenda de perfis U,
    t = 5,08 mm, A36, 2 × 2 parafusos, e = s = g = 70 mm, 32 kN característico, γ_f = 1,4.
"""

import math

from core import bolted_connection as L

KIP = L.KIP_KN


def close(a, b, rel=0.01):
    return abs(a - b) <= rel * abs(b)


# ------------------------------------------------------------------ DG29, exemplo pág. 157–159 (1")
T, FU, FY = 9.525, 400.0, 250.0  # 3/8", 58 ksi, 36 ksi
E, S = 31.75, 76.2  # 1 1/4", 3"
DB1, DH1 = 25.4, 27.0  # 1"; furo 1 1/16" do AISC 360-10 (a tabela do módulo usa 28,6 do 360-16)


def test_dg29_1pol_corte():
    assert close(L.resist_corte(DB1, "A325", "AISC360_LRFD") / KIP, 31.8)


def test_dg29_1pol_contato_interno():
    assert close(L.resist_contato(DB1, T, FU, L.lf_entre_furos(S, DH1), "AISC360_LRFD") / KIP, 38.0)


def test_dg29_1pol_contato_extremidade():
    assert close(L.resist_contato(DB1, T, FU, L.lf_borda(E, DH1), "AISC360_LRFD") / KIP, 14.1)


def test_dg29_1pol_grupo_283kips():
    Fv = L.resist_corte(DB1, "A325", "AISC360_LRFD")
    Fe = L.resist_contato(DB1, T, FU, L.lf_borda(E, DH1), "AISC360_LRFD")
    Fi = L.resist_contato(DB1, T, FU, L.lf_entre_furos(S, DH1), "AISC360_LRFD")
    assert close(L.resist_grupo_axial(2, 5, Fv, Fe, Fi) / KIP, 283.0)


def test_dg29_1pol_colapso_rasgamento_187kips():
    # g = 70,3 mm reproduz o A_nt do livro (furo alongado 1 5/16" na direção da tração)
    Agv, Anv, Ant = L.areas_bloco_central(E, S, 70.3, 2, 5, T, DH1, "AISC360_LRFD")
    assert close(Agv / 645.16, 9.94, 0.005) and close(Anv / 645.16, 6.14, 0.005)
    assert close(L.resist_colapso_rasgamento(Agv, Anv, Ant, FY, FU, "AISC360_LRFD") / KIP, 187.0)


# ------------------------------------------------------------------ DG29, exemplo pág. 185–186 (7/8")
def test_dg29_7_8_por_parafuso():
    p = L.dados_parafuso('7/8"')
    assert close(L.resist_corte(p["d_b"], "A325", "AISC360_LRFD") / KIP, 24.3)
    assert close(
        L.resist_contato(p["d_b"], T, FU, L.lf_entre_furos(S, p["d_h"]), "AISC360_LRFD") / KIP, 34.3
    )
    assert close(
        L.resist_contato(p["d_b"], T, FU, L.lf_borda(E, p["d_h"]), "AISC360_LRFD") / KIP, 15.3
    )


# ------------------------------------------------------------------ Caso real (planilha), NBR 8800:2008
t, e, s, g = 5.08, 70.0, 70.0, 70.0
N_k, gf = 32.0, 1.4
N_Sd = N_k * gf  # 44,8 kN


def test_planilha_M16_axial():
    p = L.dados_parafuso("M16")
    Fv = L.resist_corte(p["d_b"], "A325", "NBR8800_2008")
    assert close(Fv, 49.15, 0.002)
    Fe = L.resist_contato(p["d_b"], t, FU, L.lf_borda(e, p["d_h"]), "NBR8800_2008")
    Fi = L.resist_contato(p["d_b"], t, FU, L.lf_entre_furos(s, p["d_h"]), "NBR8800_2008")
    assert close(Fe, 57.80, 0.002) and close(Fi, 57.80, 0.002)
    assert close(L.resist_grupo_axial(2, 2, Fv, Fe, Fi), 196.6, 0.002)


def test_planilha_projeto2024_M16():
    assert close(L.resist_corte(16.0, "A325", "NBR8800_2024"), 55.63, 0.002)


def test_planilha_deslizamento():
    assert close(
        L.resist_deslizamento(
            91, L.mu_superficie("galvanizada_sem_tratamento", "NBR8800_2008"), "NBR8800_2008"
        ),
        14.56,
        0.002,
    )


def test_planilha_tracao_perfil_e_bloco_e_regra75():
    p = L.dados_parafuso("M16")
    An = L.area_liquida(1542.0, 2, p["d_h"], t, "NBR8800_2008")
    Ct = L.coef_Ct(13.0, s, "NBR8800_2008")
    Nt = L.resist_tracao_barra(1542.0, An, Ct, FY, FU, "NBR8800_2008")
    assert close(Nt, 323.0, 0.002)
    Agv, Anv, Ant = L.areas_bloco_central(e, s, g, 2, 2, t, p["d_h"], "NBR8800_2008")
    Fr = L.resist_colapso_rasgamento(Agv, Anv, Ant, FY, FU, "NBR8800_2008")
    assert close(Fr, 233.3, 0.002)
    R_lig = min(196.6, Fr)
    v = L.criterio_anglo(4, "A325", 16.0, regra_75=True, R_ligacao_tracao=R_lig, N_t_Rd_peca=Nt)[-1]
    assert v.status == "NÃO OK" and close(v.solicitante, 242.3, 0.002)


def test_planilha_cortante_excentrica_M22():
    coords = L.grade_retangular(2, 2, s, g)
    a = e + s / 2  # 105 mm: momento nulo na ponta da sobreposição
    ELU = L.grupo_excentrico_elastico(coords, V=N_k * gf, M=N_k * gf * a / 1000)
    ELS = L.grupo_excentrico_elastico(coords, V=N_k, M=N_k * a / 1000)
    assert (
        close(ELU["J"], 9800, 1e-6)
        and close(ELU["R_max"], 32.65, 0.002)
        and close(ELS["R_max"], 23.32, 0.002)
    )
    p = L.dados_parafuso("M22")
    Fv = L.resist_corte(p["d_b"], "A325", "NBR8800_2008")
    lf_min = min(
        L.lf_borda(e, p["d_h"]), L.lf_entre_furos(s, p["d_h"]), L.lf_entre_furos(g, p["d_h"])
    )
    Fc = L.resist_contato(p["d_b"], t, FU, lf_min, "NBR8800_2008")
    assert close(min(Fv, Fc), 79.47, 0.002)  # 41% de aproveitamento
    Ff = L.resist_deslizamento(L.protensao_minima("M22", "A325"), 0.20, "NBR8800_2008")
    assert close(Ff, 28.16, 0.002) and ELS["R_max"] / Ff < 1.0  # 83%
    Ff16 = L.resist_deslizamento(L.protensao_minima("M16", "A325"), 0.20, "NBR8800_2008")
    assert ELS["R_max"] / Ff16 > 1.0  # M16 não passa no deslizamento


def test_circulo_equivalente_2x2():
    assert close(L.raio_circulo_equivalente(70, 70), 98.99, 0.001)  # diâmetro do círculo, não 70


def test_disposicoes_borda_70mm_reprova():
    p = L.dados_parafuso("M22")
    v = {x.nome: x for x in L.disposicoes_construtivas(p["d_b"], p["d_h"], p["e_min"], t, e, s, g)}
    assert (
        v["Distância máxima à borda (na direção da força)"].status == "NÃO OK"
    )  # 70 > 12t = 60,96
    v60 = {
        x.nome: x for x in L.disposicoes_construtivas(p["d_b"], p["d_h"], p["e_min"], t, 60, s, g)
    }
    assert v60["Distância máxima à borda (na direção da força)"].status == "OK"


def test_regras_anglo_e_erros_esperados():
    assert L.criterio_anglo(4, "A490", 22, revestimento="galvanizado_fogo")[1].status == "NÃO OK"
    assert L.criterio_anglo(4, "A307", 16, ligacao_principal=True)[1].status == "NÃO OK"
    assert L.criterio_anglo(1, "A325", 16)[0].status == "NÃO OK"
    for f in (
        lambda: L.protensao_minima("M16", "A307"),
        lambda: L.resist_corte(16, "A307", "RCSC2004"),
        lambda: L.resist_deslizamento(
            91, L.mu_superficie("galvanizada_sem_tratamento", "RCSC2004"), "RCSC2004"
        ),
    ):
        try:
            f()
            raise AssertionError("deveria ter levantado erro")
        except ValueError:
            pass


def test_espessura_e_a_da_chapa_mais_fina_nao_a_soma():
    # erro do programa original: t = 10,16 (soma) dobra o contato
    p = L.dados_parafuso("M22")
    c1 = L.resist_contato(p["d_b"], 5.08, FU, 46, "NBR8800_2008")
    c2 = L.resist_contato(p["d_b"], 10.16, FU, 46, "NBR8800_2008")
    assert math.isclose(c2 / c1, 2.0, rel_tol=1e-9)


if __name__ == "__main__":
    falhas = 0
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print("OK   ", nome)
            except AssertionError as ex:
                falhas += 1
                print("FALHA", nome, ex)
    print(f"\n{falhas} falha(s)")
    raise SystemExit(1 if falhas else 0)
