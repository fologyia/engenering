"""Barras compostas: a seção, os espaçadores, N_e,m e a verificação da coluna.

Caso de aceite: exemplo E.5 do AISC (Design Examples): 2L4×3½×3/8 LLBB, 3/4 pol. de separação, A36,
L = 8 pés, biapoiada. φP_n = 127 kips e duas ligações a cada 32 pol. As propriedades e os F_e
de referência são os da verificação do mesmo exemplo publicada pela Bentley (STAAD.Pro).
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from core import cantoneiras as ct
from core import column_buckling as cb
from core import column_design as cd
from core import memorial_verificacoes as mv
from core import perfis_compostos as pc
from core import section_catalog as sc

POL = 25.4
KSI = 6.89476
KIP = 4.44822
E, G = cd.E_ACO, cd.G_ACO
U_6 = 'U 6" x 12,20'


def secao_do_exemplo() -> cd.Secao:
    peca = pc.cantoneira(4 * POL, 3.5 * POL, 0.375 * POL)
    return pc.duas_cantoneiras(peca, pc.ARRANJO_2L_T, 0.75 * POL)


def entrada_do_exemplo(norma: str = "AISC360_16_LRFD", **campos) -> cb.EntradaColuna:
    ligacoes = pc.LigacoesDaComposta(96 * POL, pc.LIGACAO_RIGIDA)
    padrao = dict(
        secao=secao_do_exemplo(), fy_MPa=36 * KSI, norma=norma, Lx_mm=96 * POL, Ly_mm=96 * POL,
        N_Sd_kN=120 * KIP, ligacoes=ligacoes,
    )  # fmt: skip
    return cb.EntradaColuna(**{**padrao, **campos})


def duas_L(arranjo: str = pc.ARRANJO_2L_T, nome: str = 'L 3" × 1/4"', s: float = 8.0) -> cd.Secao:
    medida = ct.obter_cantoneira(nome)
    return pc.duas_cantoneiras(
        pc.cantoneira(medida.b_mm, medida.b_mm, medida.t_mm, nome), arranjo, s
    )


def dois_u(arranjo: str = pc.ARRANJO_2U_I, s: float = 8.0) -> cd.Secao:
    return pc.dois_U(cb.secao_de_perfil(sc.obter_perfil(U_6)), arranjo, s, U_6)


def coluna(secao: cd.Secao, norma: str = "NBR8800_2024", **campos) -> cb.EntradaColuna:
    padrao = dict(
        secao=secao, fy_MPa=250.0, norma=norma, Lx_mm=3000.0, Ly_mm=3000.0, N_Sd_kN=50.0,
        ligacoes=pc.LigacoesDaComposta(3000.0),
    )  # fmt: skip
    return cb.EntradaColuna(**{**padrao, **campos})


def linha(resultado: cb.ResultadoColuna, trecho: str):
    return next(v for v in resultado.verificacoes if trecho in v.nome)


def inercias_dos_contornos(secao: cd.Secao) -> tuple[float, float, float, float]:
    """(A, I_x, I_y, I_xy) integrados nos contornos, por G: confere o desenho contra a conta."""
    totais = [0.0, 0.0, 0.0, 0.0]
    for contorno in secao.dims["contornos"]:
        area = ix = iy = ixy = 0.0
        for k in range(len(contorno)):
            x1, y1 = contorno[k - 1]
            x2, y2 = contorno[k]
            c = x1 * y2 - x2 * y1
            area += c / 2
            ix += c * (y1**2 + y1 * y2 + y2**2) / 12
            iy += c * (x1**2 + x1 * x2 + x2**2) / 12
            ixy += c * (x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) / 24
        sinal = 1.0 if area > 0 else -1.0  # um dos contornos é espelhado: gira ao contrário
        for i, valor in enumerate((area, ix, iy, ixy)):
            totais[i] += sinal * valor
    return totais[0], totais[1], totais[2], totais[3]


# ------------------------------------------------------------------ a cantoneira
def test_abas_iguais_batem_com_o_catalogo_de_cantoneiras():
    catalogo = ct.obter_cantoneira('L 2" × 3/16"')
    peca = pc.cantoneira(catalogo.b_mm, catalogo.b_mm, catalogo.t_mm)
    assert peca.area_mm2 == pytest.approx(catalogo.area_mm2)
    assert peca.i_x_mm4 == pytest.approx(catalogo.i_x_mm4)
    assert peca.i_y_mm4 == pytest.approx(catalogo.i_x_mm4)
    assert peca.r_min_mm == pytest.approx(catalogo.r_z_mm)
    assert peca.j_mm4 == pytest.approx(catalogo.j_mm4)
    assert peca.x_b_mm == pytest.approx(catalogo.x_barra_mm)


@pytest.mark.parametrize(
    ("a", "b", "t", "s", "mensagem"),
    [
        (50.0, 50.0, 60.0, 0.0, "menor que as duas abas"),
        (50.0, 5.0, 6.0, 0.0, "menor que as duas abas"),
        (0.0, 50.0, 6.0, 0.0, "aba a"),
        (50.0, 50.0, 6.0, -1.0, "negativo"),
    ],
)
def test_medidas_impossiveis_sao_recusadas(a, b, t, s, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        pc.duas_cantoneiras(pc.cantoneira(a, b, t), pc.ARRANJO_2L_T, s)


def test_arranjo_errado_e_recusado():
    peca = pc.cantoneira(50.0, 50.0, 6.0)
    with pytest.raises(ValueError, match="cantoneiras desconhecido"):
        pc.duas_cantoneiras(peca, pc.ARRANJO_2U_I)
    with pytest.raises(ValueError, match="perfis U desconhecido"):
        pc.dois_U(cb.secao_de_perfil(sc.obter_perfil(U_6)), pc.ARRANJO_2L_T)
    with pytest.raises(ValueError, match="pede um perfil U"):
        pc.dois_U(cd.secao_circular_macica(50.0), pc.ARRANJO_2U_I)


# ------------------------------------------------------------------ exemplo E.5 do AISC
def test_propriedades_do_exemplo_batem_com_a_tabela():
    s = secao_do_exemplo()
    assert s.A / POL**2 == pytest.approx(5.36, rel=0.005)
    assert s.Ix / POL**4 == pytest.approx(8.35, rel=0.005)
    assert s.Iy / POL**4 == pytest.approx(15.41, rel=0.005)
    assert s.J / POL**4 == pytest.approx(0.2512, rel=0.005)
    assert s.y0 / POL == pytest.approx(1.014, rel=0.005)
    assert 1 - (s.y0 / s.r0) ** 2 == pytest.approx(0.81177, rel=0.002)
    assert s.dims["r_min"] / POL == pytest.approx(0.72, rel=0.02)
    assert s.x0 == 0.0 and s.Cw == 0.0


def test_flexo_torcao_do_exemplo_bate_com_a_referencia():
    s = secao_do_exemplo()
    ne = cd.forca_flambagem_elastica(s, 96 * POL, 96 * POL)
    tensao = {nome: valor * 1e3 / s.A / KSI for nome, valor in ne["modos"].items()}
    assert tensao["flexão x"] == pytest.approx(48.38, rel=0.005)
    assert tensao["flexo-torção yz"] == pytest.approx(64.52, rel=0.005)
    assert ne["Nez"] * 1e3 / s.A / KSI == pytest.approx(96.13, rel=0.01)


def test_resistencia_e_ligacoes_do_exemplo():
    r = cb.verificar_coluna(entrada_do_exemplo())
    assert r.compressao["Nc_Rd"] / KIP == pytest.approx(127.0, rel=0.01)
    assert r.compressao["modo"] == "flexão x"
    assert r.composta.quantidade == 2  # duas ligações intermediárias
    assert r.composta.espacamento_mm / POL == pytest.approx(32.0)
    assert r.composta.esbeltez_da_peca <= r.composta.limite_da_peca
    assert r.status_geral == "OK"


# ------------------------------------------------------------------ a redução N_e,m
@pytest.mark.parametrize(
    ("ligacao", "lam_y", "ell_r", "k_i", "esperado"),
    [
        (pc.LIGACAO_APERTO_NORMAL, 100.0, 30.0, 0.50, 100**2 / (100**2 + 30**2)),
        (pc.LIGACAO_RIGIDA, 100.0, 40.0, 0.50, 1.0),
        (pc.LIGACAO_RIGIDA, 100.0, 60.0, 0.50, 100**2 / (100**2 + 30**2)),
        (pc.LIGACAO_RIGIDA, 100.0, 60.0, 0.75, 100**2 / (100**2 + 45**2)),
        (pc.LIGACAO_RIGIDA, 100.0, 60.0, 0.86, 100**2 / (100**2 + 51.6**2)),
    ],
)
def test_formula_de_n_e_m(ligacao, lam_y, ell_r, k_i, esperado):
    for norma in ("NBR8800_2024", "AISC360_16_LRFD"):
        assert pc.fator_de_reducao(norma, ligacao, lam_y, ell_r, k_i) == pytest.approx(esperado)
    assert pc.fator_de_reducao("NBR8800_2008", ligacao, lam_y, ell_r, k_i) == 1.0


def test_ki_de_cada_arranjo():
    assert duas_L().dims["k_i"] == 0.50
    assert duas_L(pc.ARRANJO_2L_CRUZ).dims["k_i"] == 0.86
    assert dois_u(pc.ARRANJO_2U_I).dims["k_i"] == 0.75
    assert dois_u(pc.ARRANJO_2U_CAIXA).dims["k_i"] == 0.86


def test_n_ey_reduzido_entra_na_flexo_torcao():
    """A conta de 5.3.5.2 à mão, com o N_ey já reduzido por 5.3.6.3."""
    s = duas_L()
    ligacoes = pc.LigacoesDaComposta(3000.0, quantidade=3)
    r = cb.verificar_coluna(coluna(s, Lx_mm=1500.0, Ly_mm=3000.0, ligacoes=ligacoes))
    lam_y = 3000.0 / s.ry
    ell_r = 750.0 / s.dims["r_min"]
    fator = lam_y**2 / (lam_y**2 + ell_r**2)
    ney = math.pi**2 * E * s.Iy / 3000.0**2 * fator
    nez = G * s.J / s.r0**2
    h = 1 - (s.y0 / s.r0) ** 2
    neyz = (ney + nez) / (2 * h) * (1 - math.sqrt(1 - 4 * ney * nez * h / (ney + nez) ** 2))
    comp = r.compressao
    assert comp["Ney"] * 1e3 == pytest.approx(ney)
    assert comp["Ney0"] * 1e3 == pytest.approx(ney / fator)
    assert comp["modos"]["flexo-torção yz"] * 1e3 == pytest.approx(neyz)
    assert comp["modo"] == "flexo-torção yz"
    assert comp["Ne"] * 1e3 == pytest.approx(neyz)


def test_a_reducao_nao_mexe_na_flexao_em_x():
    s = duas_L()
    com = cd.forca_flambagem_elastica(s, 3000.0, 3000.0, fator_Ney=0.5)
    sem = cd.forca_flambagem_elastica(s, 3000.0, 3000.0)
    assert com["Nex"] == sem["Nex"] and com["Ney"] == pytest.approx(0.5 * sem["Ney"])
    assert com["Ney0"] == sem["Ney"]


def test_sem_fator_o_calculo_das_outras_secoes_nao_muda():
    u = cd.secao_U(152.4, 48.8, 8.71, 5.08)
    base = cd.resist_compressao(u, 250.0, 3000.0, 1500.0, 3000.0, "NBR8800_2008")
    assert base["Ney0"] == base["Ney"]
    assert base["Nc_Rd"] == pytest.approx(207.3, abs=0.1)  # caso de aceite do módulo


# ------------------------------------------------------------------ distância e quantidade
def test_limite_de_cada_norma():
    s = duas_L()
    lam = 3000.0 / s.rx
    for norma, fracao in (
        ("NBR8800_2008", 0.5), ("NBR8800_2024", 0.75), ("AISC360_16_LRFD", 0.75),
    ):  # fmt: skip
        a = cb.avaliar_ligacoes(coluna(s, norma))
        assert a.limite_da_peca == pytest.approx(fracao * lam)
        assert a.espacamento_maximo_mm == pytest.approx(fracao * lam * s.dims["r_min"])


def test_o_limite_usa_a_maior_esbeltez_do_conjunto():
    s = duas_L()
    a = cb.avaliar_ligacoes(coluna(s, Lx_mm=1500.0, Ly_mm=3000.0))
    assert a.esbeltez_do_conjunto == pytest.approx(max(1500.0 / s.rx, 3000.0 / s.ry))
    assert a.esbeltez_em_y == pytest.approx(3000.0 / s.ry)


def test_k_entra_na_esbeltez_do_conjunto():
    s = duas_L()
    a = cb.avaliar_ligacoes(coluna(s, kx=2.0, ky=2.0, Lx_mm=1500.0, Ly_mm=1500.0))
    b = cb.avaliar_ligacoes(coluna(s))
    assert a.esbeltez_do_conjunto == pytest.approx(b.esbeltez_do_conjunto)


def test_barra_curta_ainda_pede_dois_espacadores():
    ligacoes = pc.LigacoesDaComposta(600.0)
    a = cb.avaliar_ligacoes(coluna(duas_L(), Lx_mm=600.0, Ly_mm=600.0, ligacoes=ligacoes))
    assert a.quantidade_minima == pc.ESPACADORES_MINIMOS == 2
    assert a.quantidade == 2
    assert a.espacamento_mm == pytest.approx(200.0)


def test_quantidade_minima_e_a_primeira_que_atende():
    s = duas_L()
    for norma in cb.NORMAS:
        for comprimento in (2000.0, 3500.0, 5000.0, 7000.0):
            e = coluna(s, norma, Lx_mm=comprimento, Ly_mm=comprimento)
            lig = pc.LigacoesDaComposta(comprimento * 3)  # mais comprido que o destravado
            a = cb.avaliar_ligacoes(replace(e, ligacoes=lig))
            n = a.quantidade_minima
            assert a.atende_o_limite
            if n > pc.ESPACADORES_MINIMOS:
                menos = cb.avaliar_ligacoes(replace(e, ligacoes=replace(lig, quantidade=n - 1)))
                assert not menos.atende_o_limite


def test_conta_exata_nao_pede_espacador_a_mais():
    s = duas_L()
    a = cb.avaliar_ligacoes(coluna(s))
    lig = pc.LigacoesDaComposta(a.espacamento_maximo_mm * 4)
    assert cb.avaliar_ligacoes(coluna(s, ligacoes=lig)).quantidade_minima == 3


def test_posicoes_igualmente_espacadas():
    a = cb.avaliar_ligacoes(coluna(duas_L(), ligacoes=pc.LigacoesDaComposta(3000.0, quantidade=3)))
    assert a.espacamento_mm == 750.0
    assert a.posicoes_mm == (750.0, 1500.0, 2250.0)


def test_sem_ligacoes_informadas_vale_o_minimo_da_norma():
    r = cb.verificar_coluna(coluna(duas_L(), ligacoes=None))
    assert r.composta.comprimento_mm == 3000.0
    assert r.composta.quantidade == r.composta.quantidade_minima


# ------------------------------------------------------------------ a tabela de verificações
def test_espacadores_de_menos_reprovam():
    r = cb.verificar_coluna(
        coluna(
            duas_L(),
            Lx_mm=2000.0,
            Ly_mm=2000.0,
            ligacoes=pc.LigacoesDaComposta(6000.0, quantidade=2),
        )
    )
    assert linha(r, "Distância entre espaçadores").status == "NÃO OK"
    assert r.status_geral == "NÃO OK"


def test_um_so_espacador_reprova_mesmo_em_barra_curta():
    r = cb.verificar_coluna(
        coluna(
            duas_L(), Lx_mm=600.0, Ly_mm=600.0, ligacoes=pc.LigacoesDaComposta(600.0, quantidade=1)
        )
    )
    assert linha(r, "Quantidade de espaçadores").status == "NÃO OK"


@pytest.mark.parametrize("norma", ["NBR8800_2024", "AISC360_16_LRFD"])
def test_pontas_de_aperto_normal_ficam_fora_da_norma(norma):
    lig = pc.LigacoesDaComposta(3000.0, pontas_rigidas=False)
    r = cb.verificar_coluna(coluna(duas_L(), norma, ligacoes=lig))
    assert linha(r, "Ligações das pontas").status == "NÃO OK"
    assert r.status_geral == "NÃO OK"
    assert any("Ligações das pontas" in b for b in r.bloqueios)
    assert r.compressao is not None


def test_a_nbr_2008_nao_exige_pontas_nem_reduz_n_e():
    lig = pc.LigacoesDaComposta(3000.0, pontas_rigidas=False)
    r = cb.verificar_coluna(coluna(duas_L(), "NBR8800_2008", ligacoes=lig))
    assert not any("pontas" in v.nome for v in r.verificacoes)
    assert r.composta.fator_de_reducao == 1.0
    assert "não reduz" in linha(r, "N_e,m").formula
    assert r.compressao["Ney"] == r.compressao["Ney0"]


def test_as_linhas_trazem_a_conta():
    r = cb.verificar_coluna(coluna(duas_L()))
    assert "(ℓ/r_mín)²" in linha(r, "N_e,m").formula
    assert linha(r, "Distância entre espaçadores").referencia == "ABNT NBR 8800:2025 5.3.6.1"
    r = cb.verificar_coluna(entrada_do_exemplo())
    assert "K_i·ℓ/r_mín" in linha(r, "N_e,m").formula
    assert linha(r, "Distância entre espaçadores").referencia == "AISC 360-16 E6.2"
    assert "(com N_e,m)" in linha(r, "flexo-torção").formula


def test_comparar_normas_acha_o_minimo_de_cada_uma():
    linhas = cb.comparar_normas(coluna(duas_L()))
    assert [item["status"] for item in linhas] == ["OK", "OK", "OK"]


def test_flambagem_local_das_abas_usa_o_grupo_3():
    s = pc.duas_cantoneiras(pc.cantoneira(76.2, 76.2, 2.5), pc.ARRANJO_2L_T, 8.0)
    r = cb.verificar_coluna(coluna(s, "NBR8800_2008"))
    b_t = 76.2 / 2.5
    raiz = math.sqrt(E / 250.0)
    assert r.compressao["Qs"] == pytest.approx(0.53 * E / (250.0 * b_t**2))
    assert b_t > 0.91 * raiz
    elementos = cb.tabela_elementos(s, 250.0, "NBR8800_2008", r.compressao)
    assert [e["Grupo (Tabela 4)"] for e in elementos] == [3]
    assert s.elementos[0]["n"] == 4


def test_abas_desiguais_viram_dois_elementos():
    s = pc.duas_cantoneiras(pc.cantoneira(100.0, 75.0, 8.0), pc.ARRANJO_2L_T, 8.0)
    assert [(e["b"], e["n"]) for e in s.elementos] == [(100.0, 2), (75.0, 2)]


def test_espessura_minima_da_anglo():
    assert cb.categoria_espessura_anglo(duas_L()) == ("cantoneira", pytest.approx(6.35))
    assert cb.categoria_espessura_anglo(dois_u()) == ("perfil_laminado_L_U", 5.08)
    s = duas_L(nome='L 2" × 1/8"')
    categoria, t = cb.categoria_espessura_anglo(s)
    r = cb.verificar_coluna(coluna(s, espessuras_anglo={categoria: t}))
    assert linha(r, "Espessura mínima").status == "NÃO OK"


def test_momento_em_barra_composta_pede_m_rd_informado():
    s = duas_L()
    r = cb.verificar_coluna(coluna(s, Mx_kNm=1.0))
    assert any("Barra composta sem rotina de M_Rd" in b for b in r.bloqueios)
    r = cb.verificar_coluna(coluna(s, Mx_kNm=1.0, MRd_x_informado_kNm=5.0))
    assert not r.bloqueios and r.indice_interacao is not None


# ------------------------------------------------------------------ outras geometrias
@pytest.mark.parametrize("arranjo", pc.ARRANJOS_DE_CANTONEIRA)
def test_as_contas_batem_com_o_desenho(arranjo):
    s = duas_L(arranjo)
    area, ix, iy, ixy = inercias_dos_contornos(s)
    assert area == pytest.approx(s.A)
    assert ix == pytest.approx(s.Ix)
    assert iy == pytest.approx(s.Iy)
    assert ixy == pytest.approx(0.0, abs=1e-3 * s.Ix)  # x e y são eixos principais


def test_y_passa_pelo_centro_geometrico_das_cantoneiras_em_t():
    s = pc.duas_cantoneiras(pc.cantoneira(100.0, 75.0, 8.0), pc.ARRANJO_2L_T, 10.0)
    area, ix, iy, _ = inercias_dos_contornos(s)
    assert (area, ix, iy) == pytest.approx((s.A, s.Ix, s.Iy))
    pontos = [p for c in s.dims["contornos"] for p in c]
    assert max(p[1] for p in pontos) - min(p[1] for p in pontos) == pytest.approx(100.0)


def test_u_em_i_e_em_caixa_batem_com_o_desenho():
    for arranjo in (pc.ARRANJO_2U_I, pc.ARRANJO_2U_CAIXA):
        s = dois_u(arranjo)
        area, ix, *_, ixy = inercias_dos_contornos(s)
        # o catálogo tem mesas inclinadas e raios: o desenho é idealizado, a diferença é pequena
        assert area == pytest.approx(s.A, rel=0.1)
        assert ix == pytest.approx(s.Ix, rel=0.1)
        assert ixy == pytest.approx(0.0, abs=1e-6 * s.Ix)


def test_wy_das_cantoneiras_em_t():
    s = duas_L()
    pontos = [p for c in s.dims["contornos"] for p in c]
    assert max(abs(p[0]) for p in pontos) == pytest.approx(4 + 76.2)
    assert s.Wy == pytest.approx(s.Iy / (4 + 76.2))


def test_2l_em_cruz_tem_os_eixos_principais():
    medida = ct.obter_cantoneira('L 3" × 1/4"')
    s = duas_L(pc.ARRANJO_2L_CRUZ)
    # a soma I_x + I_y não muda com o giro e o produto de inércia zera nos eixos da seção
    a = medida.area_mm2
    centro = (4 + medida.x_barra_mm, medida.x_barra_mm)
    assert s.Ix + s.Iy == pytest.approx(
        2 * (2 * medida.i_x_mm4 + a * (centro[0] ** 2 + centro[1] ** 2))
    )
    assert s.x0 == 0.0 and s.y0 == 0.0 and s.Cw == 0.0
    # x passa pelos centros das cantoneiras: a flexão em y é a que tem o termo de Steiner
    direita = s.dims["contornos"][1]
    assert abs(direita[0][1]) < abs(direita[0][0]) + medida.b_mm
    assert s.Iy > s.Ix
    assert s.Ix == pytest.approx(2 * medida.i_w_mm4, rel=0.03)


def test_2l_em_cruz_sem_afastamento_fica_a_45_graus():
    s = duas_L(pc.ARRANJO_2L_CRUZ, s=0.0)
    medida = ct.obter_cantoneira('L 3" × 1/4"')
    assert s.Ix == pytest.approx(2 * medida.i_w_mm4)
    assert s.Iy == pytest.approx(2 * (medida.i_z_mm4 + 2 * medida.area_mm2 * medida.x_barra_mm**2))


@pytest.mark.parametrize(
    ("arranjo", "distancia"),
    [
        (pc.ARRANJO_2U_I, lambda d: d["xb"] + 4.0),
        (pc.ARRANJO_2U_CAIXA, lambda d: d["bf"] - d["xb"] + 4.0),
    ],
)
def test_2u_pela_regra_de_steiner(arranjo, distancia):
    u = cb.secao_de_perfil(sc.obter_perfil(U_6))
    s = pc.dois_U(u, arranjo, 8.0, U_6)
    assert s.A == 2 * u.A and s.Ix == 2 * u.Ix and s.J == 2 * u.J and s.Cw == 2 * u.Cw
    assert s.Iy == pytest.approx(2 * (u.Iy + u.A * distancia(u.dims) ** 2))
    assert s.x0 == 0.0 and s.y0 == 0.0
    assert s.dims["r_min"] == pytest.approx(u.ry)
    assert sum(e["n"] for e in s.elementos) == 2 * sum(e["n"] for e in u.elementos)


def test_torcao_do_par_de_u_nao_governa_com_a_hipotese_conservadora():
    for nome in cb.nomes_de_perfis_U(sc.listar_perfis()):
        s = pc.dois_U(cb.secao_de_perfil(sc.obter_perfil(nome)), pc.ARRANJO_2U_I, 8.0, nome)
        ne = cd.forca_flambagem_elastica(s, 3000.0, 3000.0)
        assert ne["modo"] != "torção", nome


def test_nomes_de_u_nao_trazem_perfil_dobrado():
    nomes = cb.nomes_de_perfis_U(sc.listar_perfis())
    assert U_6 in nomes and not any(nome.startswith("C ideal") for nome in nomes)


# ------------------------------------------------------------------ as opções e o registro
def test_opcoes_sobem_e_param_quando_nao_ha_ganho():
    s = duas_L(pc.ARRANJO_2L_CRUZ)
    opcoes = cb.opcoes_de_espacadores(coluna(s))
    assert opcoes[0]["Espaçadores"] == 2
    resistencias = [o["N_c,Rd (kN)"] for o in opcoes]
    assert resistencias == sorted(resistencias) and resistencias[0] < resistencias[-1]
    assert resistencias[-1] == pytest.approx(resistencias[-2])  # a última já não muda nada
    assert all(o["ℓ (mm)"] == 3000.0 / (o["Espaçadores"] + 1) for o in opcoes)


def test_opcoes_com_solda_param_em_ell_r_40():
    lig = pc.LigacoesDaComposta(3000.0, pc.LIGACAO_RIGIDA)
    opcoes = cb.opcoes_de_espacadores(coluna(duas_L(), Lx_mm=1500.0, ligacoes=lig))
    assert opcoes[-1]["N_e,m/N_e,o"] == 1.0
    assert opcoes[-1]["ℓ/r_mín"] <= 40.0
    assert all(o["N_e,m/N_e,o"] < 1.0 for o in opcoes[:-1])


def test_opcoes_das_outras_secoes_e_da_2008():
    circular = cb.EntradaColuna(secao=cd.secao_circular_macica(50.0), fy_MPa=250.0, N_Sd_kN=10.0)
    assert cb.opcoes_de_espacadores(circular) == []
    assert len(cb.opcoes_de_espacadores(coluna(duas_L(), "NBR8800_2008"))) == 1


def test_registro_guarda_as_ligacoes():
    entrada = coluna(duas_L())
    registro = cb.registro_coluna(entrada, cb.verificar_coluna(entrada))
    json.dumps(registro, ensure_ascii=False, allow_nan=False)
    entradas, resultados = registro["entradas"], registro["resultados"]
    assert entradas["arranjo_da_composta"] == pc.ARRANJO_2L_T
    assert entradas["afastamento_s_mm"] == 8.0
    assert entradas["quantidade_de_espacadores"] == 2
    assert resultados["espacamento_adotado_mm"] == 1000.0
    assert resultados["K_i"] == 0.50
    assert "Barra composta" in registro["metodo"]
    assert any("cada perfil trabalhando sozinho" in p for p in registro["premissas"])
    pares = dict(
        mv.pares_de_entrada(
            {"modulo_id": "flambagem_colunas", "entradas": entradas}, str, lambda c: c
        )
    )
    assert pares["Quantidade de espaçadores"] == "2"
    assert pares["Barra composta: arranjo"] == pc.ARRANJO_2L_T


def test_registro_das_outras_secoes_nao_ganha_campos():
    entrada = cb.EntradaColuna(secao=cd.secao_circular_macica(50.0), fy_MPa=250.0, N_Sd_kN=10.0)
    registro = cb.registro_coluna(entrada, cb.verificar_coluna(entrada))
    assert "arranjo_da_composta" not in registro["entradas"]
    assert "espacamento_adotado_mm" not in registro["resultados"]
