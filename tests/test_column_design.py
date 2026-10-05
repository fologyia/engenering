"""
Testes de aceitação — flambagem / flexo-compressão.

Rodar:   pytest -q tests/test_column_design.py

Fontes externas:
  • AISC Design Guide 29: HSS8×8×1/2 (A500 Gr B, F_y = 46 ksi), L = 24 ft, K = 1 → φP_n = 306 kips (AISC Manual Tab. 4-4)
    e F_cre = 41,9 ksi para R_y F_y = 64,4 ksi e KL/r = 67,6 (exemplo sísmico).
  • Programa "Flambagem de colunas" do usuário: barra circular Ø50, L = 2000, K = 1, f_y = 250 →
    N_ex = 151,4 kN, λ0 = 1,801, χ = 0,270, N_c,Rd = 120,71 kN; N_Sd = 1,40·30 + 1,50·20 = 72 kN.
Demais testes: continuidade das fórmulas nos limites de faixa (detectam erro de transcrição) e regras Anglo.
"""

import math

from core import column_design as F

KSI = 6.894757  # MPa
INCH = 25.4
KIP = 4.448222


def close(a, b, rel=0.005):
    return abs(a - b) <= rel * abs(b)


# ------------------------------------------------------------------ fontes externas
def test_dg29_hss8x8x1_2_306kips():
    t = 0.465 * INCH
    A = 13.5 * INCH**2
    r = 3.04 * INCH
    sec = F.secao_generica(
        "HSS8x8x1/2",
        A,
        A * r**2,
        A * r**2,
        torcao_relevante=False,
        elementos=[dict(tipo="AA", grupo=1, b=14.2 * t, t=t, n=4, tubo_ret=True)],
    )
    c = F.resist_compressao(
        sec, 46 * KSI, 24 * 12 * INCH, 24 * 12 * INCH, norma="AISC360_16_LRFD", E=29000 * KSI
    )
    assert c["Q"] == 1.0  # b/t = 14,2 < 1,40√(E/F_y) = 35,2
    assert close(c["Nc_Rd"] / KIP, 306.0)


def test_dg29_curva_chi_Fcre_41_9ksi():
    Fy = 64.4  # R_y F_y (ksi)
    Fe = math.pi**2 * 29000 / 67.6**2
    assert close(Fe, 62.6, 0.002)
    assert close(F.fator_chi(math.sqrt(Fy / Fe)) * Fy, 41.9, 0.002)


def test_programa_usuario_barra_circular_50():
    s = F.secao_circular_macica(50)
    c = F.resist_compressao(s, 250, 2000, 2000, norma="NBR8800_2008")
    assert close(c["Nex"], 151.4, 0.001) and close(c["lambda0"], 1.801, 0.001)
    assert close(c["chi"], 0.270, 0.002) and close(c["Nc_Rd"], 120.71, 0.001)
    assert close(c["esbeltez"], 160.0, 1e-9)
    Nsd = F.combinacao_ultima([(30, 1.40)], (20, 1.50))
    assert Nsd == 72.0
    r = F.verificar_barra(s, 250, 2000, 2000, Nsd)
    assert r["atende"] and close(r["aproveitamento"], 0.596, 0.002)


# ------------------------------------------------------------------ consistência das fórmulas
def test_chi_continuo_em_lambda0_1_5():
    assert close(0.658**2.25, 0.877 / 2.25, 0.001)


def test_Qs_2008_continuo_nos_limites():
    E, fy = 200000, 250
    s = math.sqrt(E / fy)
    for g, a, b in [(3, 0.45, 0.91), (4, 0.56, 1.03), (6, 0.75, 1.03)]:
        el = lambda bt, g=g: dict(tipo="AL", grupo=g, b=bt * s, t=1.0)
        assert close(F.Qs_elemento_2008(el(a + 1e-6), fy), 1.0, 0.01)
        assert close(
            F.Qs_elemento_2008(el(b - 1e-6), fy), F.Qs_elemento_2008(el(b + 1e-6), fy), 0.015
        )
    kc = 0.5
    sk = math.sqrt(E / (fy / kc))
    el = lambda bt: dict(tipo="AL", grupo=5, b=bt * sk, t=1.0, kc=kc)
    assert close(F.Qs_elemento_2008(el(0.64 + 1e-6), fy), 1.0, 0.01)
    assert close(
        F.Qs_elemento_2008(el(1.17 - 1e-6), fy), F.Qs_elemento_2008(el(1.17 + 1e-6), fy), 0.015
    )


def test_bef_2024_continuo_no_limite():
    fy, chi = 250, 0.6
    for el in (
        dict(tipo="AA", grupo=2),
        dict(tipo="AA", grupo=1, tubo_ret=True),
        dict(tipo="AL", grupo=4),
    ):
        lim = F.bt_lim(el, fy)
        e = dict(el, t=1.0, b=lim / math.sqrt(chi) * (1 + 1e-6))
        assert close(F.bef_2024(e, fy, chi), e["b"], 0.005)


def test_flexo_torcao_U_menor_que_modos_isolados():
    u = F.secao_U(152.4, 48.8, 8.71, 5.08)
    n = F.forca_flambagem_elastica(u, 3000, 3000, 3000)
    assert n["modos"]["flexo-torção xz"] <= min(n["Nex"], n["Nez"]) + 1e-9
    g = F.secao_generica("quase simétrica", u.A, u.Ix, u.Iy, u.J, u.Cw, x0=1e-6)
    n2 = F.forca_flambagem_elastica(g, 3000, 3000, 3000)
    assert close(n2["modos"]["flexo-torção xz"], min(n2["Nex"], n2["Nez"]), 0.001)


def test_cubica_assimetrica_tende_ao_minimo():
    u = F.secao_U(152.4, 48.8, 8.71, 5.08)
    g = F.secao_generica("assimétrica ~0", u.A, u.Ix, u.Iy, u.J, u.Cw, x0=1e-4, y0=1e-4)
    n = F.forca_flambagem_elastica(g, 3000, 1500, 3000)
    assert close(n["Ne"], min(n["Nex"], n["Ney"], n["Nez"]), 0.001)


def test_U_geometria_vs_catalogo_C6x8_2():
    u = F.secao_U(6.0 * INCH, 1.92 * INCH, 0.343 * INCH, 0.200 * INCH)
    assert close(u.A / INCH**2, 2.39, 0.01) and close(u.Ix / INCH**4, 13.1, 0.01)


def test_FLT_Mcr_igual_Mr_em_lambda_r():
    i = F.secao_I(300, 150, 9.5, 6.3, soldado=True)
    for norma, Cb in (("NBR8800_2008", 1.0), ("NBR8800_2024", 1.0), ("NBR8800_2024", 1.5)):
        m = F.momento_resistente(i, 345, "x", Lb=1000, Cb=Cb, norma=norma)
        Lb = m["aux"]["lr_FLT"] * i.ry * (1 + 1e-7)
        m2 = F.momento_resistente(i, 345, "x", Lb=Lb, Cb=Cb, norma=norma)
        Mcr = m2["estados"]["FLT"] * 1.10 * 1e6
        assert close(Mcr, m2["aux"]["Mr_FLT"], 0.005), (norma, Cb)


def test_MRd_limitado_a_1_5_W_fy():
    s = F.secao_circular_macica(50)
    m = F.momento_resistente(s, 250)
    assert m["governa"].startswith("limite 1,5") and close(
        m["MRd"], 1.5 * s.Wx * 250 / 1.10 / 1e6, 1e-9
    )


def test_secao_compacta_2008_igual_2024_e_aisc_99pct():
    i = F.secao_I(300, 150, 12.5, 8.0)
    a = F.resist_compressao(i, 250, 4000, 4000, 4000, "NBR8800_2008")
    b = F.resist_compressao(i, 250, 4000, 4000, 4000, "NBR8800_2024")
    c = F.resist_compressao(i, 250, 4000, 4000, 4000, "AISC360_16_LRFD")
    assert (
        a["Q"] == 1.0
        and close(a["Nc_Rd"], b["Nc_Rd"], 1e-9)
        and close(c["Nc_Rd"] / a["Nc_Rd"], 0.99, 1e-6)
    )


def test_secao_esbelta_reduz_resistencia():
    i = F.secao_I(600, 200, 6.3, 5.0, soldado=True)  # alma h/t = 117 > 1,49√(E/f_y)
    for norma in ("NBR8800_2008", "NBR8800_2024"):
        c = F.resist_compressao(i, 345, 3000, 3000, 3000, norma)
        assert c["A_ef"] < i.A and c["Nc_Rd"] < c["chi"] * i.A * 345 / 1.10 / 1000


def test_interacao_biaxial_reprova_o_que_eixo_a_eixo_aprovaria():
    assert F.interacao_NM(30, 100, 5, 10) <= 1.0  # só x: 0,3 + 8/9·0,5 = 0,744
    assert F.interacao_NM(30, 100, 0, 1e9, 4, 10) <= 1.0  # só y: 0,3 + 8/9·0,4 = 0,656
    assert close(F.interacao_NM(30, 100, 5, 10, 4, 10), 1.1, 1e-9)  # juntos: 1,10 → NÃO OK


def test_B1_e_Cm():
    assert F.coef_Cm(-50, 50) == 1.0 and close(F.coef_Cm(50, 50), 0.2, 1e-9)
    Ne = math.pi**2 * 200000 * 1e7 / 4000**2 / 1000
    assert close(F.coef_B1(100, 1e7, 4000, 1.0), 1 / (1 - 100 / Ne), 1e-9)
    assert F.coef_B1(100, 1e7, 4000, 0.2) == 1.0
    assert F.coef_B1(100, 1e7, 4000, 1.0, tracao=True) == 1.0


def test_criterio_anglo():
    assert F.criterio_anglo(201)[0].status == "NÃO OK" and F.criterio_anglo(200)[0].status == "OK"
    assert F.criterio_anglo(299, comprimida=False)[0].status == "OK"
    v = F.criterio_anglo(
        100, espessuras={"perfil_laminado_L_U": 4.5, "chapa_ligacao_enrijecedor": 8.0}
    )
    assert v[1].status == "NÃO OK" and v[2].status == "OK"


def test_tabela_K_e_mao_francesa():
    assert F.K_recomendado("rotula-rotula") == 1.0 and F.K_recomendado("engaste-livre") == 2.1
    assert F.momento_mao_francesa(10, 300) == 3.0


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


# ------------------------------------------------------------------ correções e acréscimos do porte
def test_bef_2008_igual_ao_original_quando_sigma_e_fy():
    el = dict(tipo="AA", grupo=2, b=60.0, t=1.0)  # b/t = 60 > 1,49√(E/f_y) = 42,1
    fy, E = 250.0, 200000.0
    r = math.sqrt(E / fy)
    esperado = 1.92 * 1.0 * r * (1 - 0.34 / 60.0 * r)
    assert close(F.bef_AA_2008(el, fy, fy), esperado, 1e-12)
    assert F.bef_AA_2008(dict(el, b=40.0), fy, fy) == 40.0  # abaixo do limite: sem redução


def test_bef_2008_nunca_negativo_em_coluna_muito_esbelta():
    # Antes da correção: σ = χ·f_y minúsculo + limite pela Tabela F.1 → b_ef negativo e raiz de negativo.
    u = F.secao_U(254, 66, 11.1, 6.1)  # alma b/t = 38 logo acima do limite 35,9 com f_y = 345
    for kxlx, kyly, kzlz in ((6277, 8111, None), (1389, 8940, 5853), (9000, 9000, 9000)):
        c = F.resist_compressao(u, 345.0, kxlx, kyly, kzlz, "NBR8800_2008")
        assert 0 < c["Q"] <= 1.0 and c["Nc_Rd"] > 0 and c["chi"] > 0
    el = u.elementos[1]
    assert F.bef_AA_2008(el, 345.0, 0.001 * 345.0) == el["b"]  # σ ≈ 0: nada a reduzir


def test_bef_2008_continuo_no_limite_com_sigma_menor_que_fy():
    chi, fy = 0.4, 345.0
    el = dict(tipo="AA", grupo=2, t=1.0)
    lim_sigma = F.bt_lim(el, fy) / math.sqrt(chi)
    abaixo = F.bef_AA_2008(dict(el, b=lim_sigma * (1 - 1e-9)), fy, chi * fy)
    acima = F.bef_AA_2008(dict(el, b=lim_sigma * (1 + 1e-9)), fy, chi * fy)
    assert close(abaixo, lim_sigma, 1e-6) and close(acima, abaixo, 0.01)


def test_Zy_do_U_bate_com_o_catalogo_geometrico():
    from core import steel_sections as ss

    for d, bf, tf, tw in [
        (152.4, 48.8, 8.71, 5.08),
        (254, 66, 11.1, 6.1),
        (100, 50, 8, 5),
        (76.2, 35.8, 6.9, 4.3),
    ]:
        u = F.secao_U(d, bf, tf, tw)
        perfil = ss.perfil_u("U", d, bf, tw, tf)
        assert u.Zy is not None and close(u.Zy, perfil.zy_mm3, 1e-9)
        assert u.Zy > u.Wy  # módulo plástico acima do elástico


def test_U_no_eixo_y_agora_tem_MRd_pela_FLM():
    m = F.momento_resistente(F.secao_U(152.4, 48.8, 8.71, 5.08), 250, "y")
    assert m["MRd"] > 0 and "FLM" in m["estados"]


def test_FLT_do_tubo_retangular_reduz_MRd_no_eixo_de_maior_inercia():
    t = F.secao_tubo_retangular(100, 200, 6)  # B=100 (x), H=200 (y): Ix > Iy
    curto = F.momento_resistente(t, 250, "x", Lb=0.0)
    assert curto["governa"] == "plastificação" and "FLT" not in curto["estados"]
    longo = F.momento_resistente(t, 250, "x", Lb=12000.0)
    assert "FLT" in longo["estados"] and longo["MRd"] < curto["MRd"]
    assert longo["governa"] == "FLT"
    # eixo y e tubo quadrado: sem FLT
    assert "FLT" not in F.momento_resistente(t, 250, "y", Lb=12000.0)["estados"]
    quadrado = F.secao_tubo_retangular(150, 150, 6)
    assert "FLT" not in F.momento_resistente(quadrado, 250, "x", Lb=12000.0)["estados"]


def test_FLT_do_tubo_retangular_continua_em_lambda_p_e_lambda_r():
    t = F.secao_tubo_retangular(100, 200, 6)
    fy, E = 250.0, 200000.0
    sja = math.sqrt(t.J * t.A)
    mpl = t.Zx * fy
    lp = 0.13 * E * sja / mpl * t.ry
    assert close(
        F.momento_resistente(t, fy, "x", Lb=lp * (1 + 1e-9))["MRd"], mpl * 1e-6 / 1.1, 1e-4
    )
    lr = 2.0 * E * sja / (fy * t.Wx) * t.ry
    abaixo = F.momento_resistente(t, fy, "x", Lb=lr * (1 - 1e-9))["MRd"]
    acima = F.momento_resistente(t, fy, "x", Lb=lr * (1 + 1e-9))["MRd"]
    assert close(abaixo, acima, 1e-4)


def test_barra_retangular_maciça_mantem_a_FLT_do_original():
    b = F.secao_retangular_macica(30, 80)
    m = F.momento_resistente(b, 250, "x", Lb=1000.0)
    assert close(m["MRd"], 10.832, 0.001) and m["governa"] == "FLT"


def test_blocos_levantam_erro_em_vez_de_estimar():
    import pytest

    esbelto = F.secao_circular_macica(10)
    esbelto.tipo = "tubo_circ"  # sem D/t
    with pytest.raises(ValueError):
        F.resist_compressao(esbelto, 250, 1000, 1000)
    with pytest.raises(ValueError, match="D/t > 0,45"):
        F.resist_compressao(F.secao_tubo_circular(200, 0.5), 250, 1000, 1000)  # D/t = 400
    with pytest.raises(NotImplementedError, match="não compacto"):
        F.momento_resistente(F.secao_tubo_circular(200, 2.5), 250)
    with pytest.raises(NotImplementedError, match="não compacto"):
        F.momento_resistente(F.secao_tubo_retangular(200, 200, 3), 250)
    with pytest.raises(NotImplementedError, match="Alma esbelta"):
        F.momento_resistente(F.secao_I(900, 200, 8, 4, soldado=True), 345)
    with pytest.raises(ValueError, match="Z"):
        F.momento_resistente(F.secao_generica("sem Z", 1000, 1e6, 1e6, Wx=1e4, Wy=1e4), 250)
    with pytest.raises(NotImplementedError, match="sem rotina"):
        F.momento_resistente(
            F.secao_generica("g", 1000, 1e6, 1e6, Wx=1e4, Wy=1e4, Zx=1.1e4, Zy=1.1e4), 250
        )
    with pytest.raises(ValueError, match="N_Sd1"):
        F.coef_B1(1e6, 1e7, 4000, 1.0)
