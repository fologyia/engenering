"""Base de pilar pela NBR 8800:2025, Subseção 6.7: casos, contas de mão, equilíbrio e desenho."""

from __future__ import annotations

import io
import math
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from core import base_de_pilar as bp
from core import record_charts
from core.desenho_placa_base import figura_da_base

PADRAO = bp.EntradaBase()  # W 250 x 32,7, tipo 1, 4 × Ø 1", t_p 25 mm, f_ck 25, N 300 kN, V 20 kN
SIGMA_RD = 0.85 * 25.0 / 1.4  # 0,85·f_ck/γ_c·√1 (NBR 8800:2025 6.6.5)


def _linha(r: bp.ResultadoBase, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def _equilibrio(r: bp.ResultadoBase) -> tuple[float, float]:
    """Força normal (N, + compressão) e momento (N·mm) que a placa devolve: concreto e chumbadores."""
    g = r.geometria
    compressao = 0.0
    momento = 0.0
    if r.l_c is not None and r.caso in ("C3", "T3"):
        compressao = r.sigma_c_rd * r.l_c * g.ly
        momento += compressao * (g.lx / 2 - r.l_c / 2)  # resultante a ℓ_c/2 da borda comprimida
    tracao = 0.0
    for (x, _), forca in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True):
        tracao += forca
        momento += forca * (
            -x
        )  # tracionados em x < 0: momento no mesmo sentido do concreto em x > 0
    return compressao - tracao, momento


# ------------------------------------------------------------------ geometria e o caso C1 à mão
def test_c1_bate_com_a_conta_de_mao():
    r = bp.calcular(PADRAO)
    g = r.geometria
    assert r.caso == "C1" and r.status == "OK"
    assert (g.d, g.b_f) == (258, 146)
    assert g.lx == pytest.approx(258 + 4 * 50) and g.ly == pytest.approx(100 + 2 * 50)
    assert g.a == pytest.approx(458 / 2 - 50)
    assert r.sigma_c_rd == pytest.approx(SIGMA_RD)
    assert r.sigma_c_sd == pytest.approx(300e3 / (458 * 200))
    m = (458 - 0.95 * 258) / 2
    t_min = m * math.sqrt(2 * r.sigma_c_sd / (250 / 1.10))  # m governa (n = 41,6; λ·n₀ ≈ 25)
    assert r.t_p_min == pytest.approx(t_min, rel=1e-9)
    assert r.t_p_min == pytest.approx(18.07, abs=0.01)
    assert r.v_rd == pytest.approx(0.45 * 300e3 / 1.35)  # μ·N/γ_a2 < τ_c,Rd·ℓx·ℓy
    assert r.d_b_min is None and r.f_t_sd == 0
    assert r.governante is _linha(r, "Placa de base")
    assert r.aproveitamento_maximo == pytest.approx(r.t_p_min / 25.0)


def test_fator_x_e_lambda():
    r = bp.calcular(PADRAO)
    x = 4 * 258 * 146 / (258 + 146) ** 2 * 300e3 / (458 * 200 * SIGMA_RD)
    assert _linha(r, "Fator X").solicitante == pytest.approx(x)


@pytest.mark.parametrize(
    ("n", "m", "caso"),
    [
        (300, 0, "C1"),
        (300, 20, "C2"),
        (300, 80, "C3"),
        (0, 40, "C3"),  # flexão pura cai no caso de grande excentricidade
        (-80, 0, "T1"),
        (-80, 10, "T2"),
        (-50, 60, "T3"),
    ],
)
def test_caso_pela_normal_e_pela_excentricidade(n, m, caso):
    assert bp.calcular(replace(PADRAO, n_sd_kN=n, m_sd_kNm=m)).caso == caso


def test_limite_entre_c2_e_c3():
    """e = ½(ℓx − N/(σ_c,Rd·ℓy)): logo abaixo é C2, logo acima é C3."""
    limite = 0.5 * (458 - 300e3 / (SIGMA_RD * 200))  # mm
    momento = 300 * limite / 1e3  # kN·m
    assert bp.calcular(replace(PADRAO, m_sd_kNm=momento * 0.999)).caso == "C2"
    assert bp.calcular(replace(PADRAO, m_sd_kNm=momento * 1.001)).caso == "C3"


def test_c2_pressao_no_trecho_reduzido():
    r = bp.calcular(replace(PADRAO, m_sd_kNm=20))
    e = 20e6 / 300e3
    assert r.l_c == pytest.approx(458 - 2 * e)
    assert r.sigma_c_sd == pytest.approx(300e3 / ((458 - 2 * e) * 200))
    assert r.f_t_sd == 0


# ------------------------------------------------------------------ equilíbrio nos casos com tração
@pytest.mark.parametrize(
    "entrada",
    [
        replace(PADRAO, n_chumbadores=6, m_sd_kNm=150, t_placa_mm=40),
        replace(PADRAO, n_sd_kN=100, m_sd_kNm=30),
        replace(PADRAO, n_sd_kN=0, m_sd_kNm=40),
        replace(PADRAO, n_sd_kN=-50, m_sd_kNm=60),
        replace(PADRAO, n_sd_kN=-80, m_sd_kNm=10),
        replace(PADRAO, n_sd_kN=-80, m_sd_kNm=0),
    ],
)
def test_concreto_e_chumbadores_equilibram_n_e_m(entrada):
    r = bp.calcular(entrada)
    normal, momento = _equilibrio(r)
    assert normal == pytest.approx(entrada.n_sd_kN * 1e3, abs=1e-3)
    assert momento == pytest.approx(entrada.m_sd_kNm * 1e6, rel=1e-9, abs=1e-3)


def test_c3_com_seis_chumbadores_bate_com_a_conta_de_mao():
    r = bp.calcular(replace(PADRAO, n_chumbadores=6, m_sd_kNm=150, t_placa_mm=40))
    base = 229 + 179
    l_c = base - math.sqrt(base**2 - 2 * (150e6 + 300e3 * 179) / (SIGMA_RD * 300))
    assert r.caso == "C3" and r.l_c == pytest.approx(l_c)
    assert r.f_t_sd == pytest.approx(2 * (SIGMA_RD * l_c * 300 - 300e3) / 6)
    assert r.f_t_sd / 1e3 == pytest.approx(98.1, abs=0.05)  # ℓ_c = 130,5 mm
    d_min = math.sqrt(4 * r.f_t_sd / (0.75 * math.pi * 400 / 1.35))
    assert r.d_b_min == pytest.approx(d_min)
    assert sum(f > 0 for f in r.forcas_nos_chumbadores) == 3  # uma linha inteira tracionada


def test_t2_forcas_diferentes_nas_duas_linhas():
    r = bp.calcular(replace(PADRAO, n_sd_kN=-80, m_sd_kNm=10))
    a = 179.0
    assert r.f_t_sd == pytest.approx(80e3 / 4 + 10e6 / (a * 4))
    menores = [f for (x, _), f in zip(r.geometria.posicoes, r.forcas_nos_chumbadores, strict=True) if x > 0]  # fmt: skip
    assert menores == pytest.approx([80e3 / 4 - 10e6 / (a * 4)] * 2)
    assert r.sigma_c_sd is None and r.l_c is None


def test_sem_raiz_de_l_c_reprova_sem_quebrar():
    r = bp.calcular(replace(PADRAO, m_sd_kNm=2000))
    linha = _linha(r, "Equilíbrio possível")
    assert linha.status == "NÃO OK" and r.l_c is None and r.status == "NÃO OK"


# ------------------------------------------------------------------ tipo 2 e limites
def test_tipo_2_usa_l0_e_chumbadores_internos():
    r = bp.calcular(replace(PADRAO, perfil="W 360 x 51,0", tipo=bp.TIPO_2, n_sd_kN=-40, v_sd_kN=0))
    g = r.geometria
    assert r.caso == "T1" and r.status == "OK"
    assert g.a == pytest.approx(50) and g.l0 == pytest.approx(100 + 1.75 * (100 - 7.2))
    assert r.t_p_min == pytest.approx(math.sqrt(4 * 10e3 * (100 - 7.2) / (g.l0 * 250 / 1.10)))
    assert all(abs(x) < g.d / 2 - g.t_f for x, _ in g.posicoes)
    assert _linha(r, "ℓ₀ ≤ d").status == "OK"


def test_tipo_2_em_perfil_baixo_reprova_l0():
    """W 250: ℓ₀ = 100 + 1,75·(100 − 6,1) = 264 mm > d = 258 mm com os mínimos do Ø 1"."""
    r = bp.calcular(replace(PADRAO, tipo=bp.TIPO_2, n_sd_kN=-40))
    assert _linha(r, "ℓ₀ ≤ d").status == "NÃO OK"


def test_tipo_2_nao_cobre_c3():
    r = bp.calcular(replace(PADRAO, tipo=bp.TIPO_2, m_sd_kNm=80))
    assert r.caso == "C3" and _linha(r, "Caso previsto").status == "NÃO OK"


@pytest.mark.parametrize(("tipo", "n", "passa"), [(bp.TIPO_1, 8, True), (bp.TIPO_1, 10, False), (bp.TIPO_2, 6, False)])  # fmt: skip
def test_numero_de_chumbadores(tipo, n, passa):
    r = bp.calcular(replace(PADRAO, tipo=tipo, n_chumbadores=n))
    assert (_linha(r, "Número de chumbadores").status == "OK") is passa


def test_placa_mais_estreita_que_a_mesa_reprova_e_a2_maior_resolve():
    largo = replace(PADRAO, perfil="W 310 x 97,0(H)")
    assert _linha(bp.calcular(largo), "Largura da placa").status == "NÃO OK"
    assert _linha(bp.calcular(replace(largo, a2_mm=250)), "Largura da placa").status == "OK"


def test_tabela_18_distancias_menores_que_o_minimo_reprovam():
    r = bp.calcular(replace(PADRAO, a1_mm=40, fck_MPa=20))
    assert _linha(r, "Distância a₁").status == "NÃO OK"
    assert _linha(r, "Concreto: f_ck").status == "NÃO OK"
    assert r.status == "NÃO OK"


def test_bloco_informado_da_a2_a1_e_confere_as_medidas_da_nota_e():
    r = bp.calcular(replace(PADRAO, bloco_x_mm=687, bloco_y_mm=300))
    assert r.sigma_c_rd == pytest.approx(SIGMA_RD * 1.5)  # A₂/A₁ = 2,25 (bloco 1,5× a placa)
    # N_b ≥ máx(900; 458 + 2·60; 458 + 2·(160 − 50)) = 900; B_b ≥ máx(200 + 120; 200 + 220) = 420
    assert _linha(r, "Bloco: N_b").status == "NÃO OK"
    assert _linha(r, "Bloco: B_b").status == "NÃO OK"
    justo = bp.calcular(replace(PADRAO, bloco_x_mm=900, bloco_y_mm=420))
    assert _linha(justo, "Bloco: N_b").status == "OK"
    assert _linha(justo, "Bloco: B_b").status == "OK"  # o chumbador fica a a₃ = 160 da face
    assert bp.calcular(replace(PADRAO, bloco_x_mm=899, bloco_y_mm=420)).status == "NÃO OK"
    assert bp.calcular(replace(PADRAO, bloco_x_mm=900, bloco_y_mm=419)).status == "NÃO OK"


def test_bloco_minimo_da_nota_e_vai_ao_cone_e_ao_detalhamento():
    r = bp.calcular(PADRAO)
    tab = bp.TABELA_18['1"']
    assert bp.bloco_minimo(PADRAO, r.geometria, tab) == pytest.approx((900, 420, 900))
    assert bp.bloco_para_o_cone(PADRAO, r.geometria, tab) == (900, 420, False)
    detalhes = dict(r.detalhamento)
    assert "N_b ≥ 900 mm" in detalhes["Bloco mínimo"] and "B_b ≥ 420 mm" in detalhes["Bloco mínimo"]
    # nota h: d_a ≤ ½·[h₁ − 0,5·(r₂ + d_b)] = ½·(465 − 37,5) = 213,75 mm
    assert "d_a = ½·[h₁ − 0,5·(r₂ + d_b)] = 214 mm" in detalhes["Armadura mínima do bloco"]
    assert "f_y = 345 MPa" in detalhes["Arruelas especiais"]
    assert "d_b + 1,5 = 26,5 mm" in detalhes["Arruelas especiais"]
    assert "soltas" in detalhes["Arruelas especiais"]
    soldadas = dict(bp.calcular(replace(PADRAO, cortante=bp.CORTANTE_ARRUELAS)).detalhamento)
    assert "soldadas à placa" in soldadas["Arruelas especiais"]


def test_sigma_rd_da_6_6_5_limitado_a_1_7_fck_sobre_gama_c():
    assert bp.tensao_resistente_do_concreto(25, 2.25, "normal") == pytest.approx(SIGMA_RD * 1.5)
    teto = 1.7 * 25 / 1.4  # √(A₂/A₁) = 2 já chega ao teto
    assert bp.tensao_resistente_do_concreto(25, 4.0, "normal") == pytest.approx(teto)
    assert bp.tensao_resistente_do_concreto(25, 9.0, "normal") == pytest.approx(teto)
    assert bp.tensao_resistente_do_concreto(25, 1.0, "excepcional") == pytest.approx(
        0.85 * 25 / 1.2
    )
    assert bp.tensao_resistente_do_concreto(25, 0.5, "normal") == pytest.approx(SIGMA_RD)
    linha = _linha(bp.calcular(PADRAO), "Concreto")
    assert "0,85·f_ck/γ_c·√(A₂/A₁) ≤ 1,7·f_ck/γ_c" in linha.formula
    assert linha.referencia == "NBR 8800:2025 6.6.5"


# ------------------------------------------------------------------ cortante
def test_sem_contato_o_atrito_reprova_sem_aproveitamento_infinito():
    r = bp.calcular(replace(PADRAO, n_sd_kN=-80, m_sd_kNm=10))
    linha = _linha(r, "Cortante: atrito")
    assert linha.tipo == "limite" and linha.status == "NÃO OK"
    assert math.isfinite(r.aproveitamento_maximo)
    assert any("placa de cisalhamento" in a for a in r.avisos)
    sem_cortante = bp.calcular(replace(PADRAO, n_sd_kN=-80, v_sd_kN=0))
    assert _linha(sem_cortante, "Cortante: atrito").status == "OK"


def test_placa_de_cisalhamento():
    r = bp.calcular(replace(PADRAO, n_sd_kN=-80, v_sd_kN=40, cortante=bp.CORTANTE_PLACA))
    v_rd = 1.7 * 25.0 / 1.4 * (150 - 60) * 150  # σ_c,Rd com A₂/A₁ = 4: 1,7·f_ck/γ_c
    assert r.v_rd == pytest.approx(v_rd)
    t_min = math.sqrt(2 * 40e3 * (150 + 60) / (150 * 250 / 1.10))
    assert _linha(r, "Placa de cisalhamento: espessura").solicitante == pytest.approx(t_min)
    assert _linha(r, "Placa de cisalhamento não mais espessa").status == "OK"


def test_arruelas_soldadas_sem_tracao():
    r = bp.calcular(replace(PADRAO, cortante=bp.CORTANTE_ARRUELAS))
    d_b, t_a = 25.0, 8.0
    corte = 0.45 * math.pi * d_b**2 / 4 * 400 / 1.35  # 6.3.3.2 a): 65,4 kN
    l_f = (75 - (25 + 1.5)) / 2  # do furo da arruela (d_b + 1,5) à borda dela
    contato = min(1.2 * l_f, 2.4 * d_b) * t_a * 450 / 1.35  # 6.3.3.3: 77,6 kN
    f_v = min(corte, contato)
    assert f_v == pytest.approx(corte)
    alfa = 1.45 * (25 + 0.5 * t_a) / d_b * (400 / 250) * (1.10 / 1.35)
    por_chumbador = min(f_v / math.sqrt(1 + alfa**2), 5 * d_b**2 * SIGMA_RD)
    assert r.v_rd == pytest.approx(4 * por_chumbador)
    solda = _linha(r, "Solda das arruelas de cima")
    assert solda.status == "INFO" and f"{corte / 1e3:.1f}".replace(".", ",") in solda.formula


def test_arruela_soldada_o_contato_no_furo_limita_o_chumbador_forte():
    """F1554 Gr 105: o corte da barra (141 kN) passa do contato no furo da arruela (77,6 kN)."""
    e = replace(PADRAO, cortante=bp.CORTANTE_ARRUELAS, aco_chumbador="ASTM F1554 Gr 105")
    r = bp.calcular(e)
    d_b, t_a = 25.0, 8.0
    corte = 0.45 * math.pi * d_b**2 / 4 * 862 / 1.35
    contato = 1.2 * 24.25 * t_a * 450 / 1.35
    assert contato < corte
    alfa = 1.45 * (25 + 0.5 * t_a) / d_b * (862 / 250) * (1.10 / 1.35)
    por_chumbador = min(contato / math.sqrt(1 + alfa**2), 5 * d_b**2 * SIGMA_RD)
    assert r.v_rd == pytest.approx(4 * por_chumbador)
    linha = _linha(r, "Cortante: arruelas")
    assert "6.3.3.3" in linha.formula and "6.3.3.2 a" in linha.formula
    assert bp.contato_no_furo_da_arruela(bp.TABELA_18['1"'], t_a, 1.35) == pytest.approx(
        (contato, 24.25)
    )


def test_tipo_2_a1_na_direcao_lx_pela_nota_f():
    tipo_2 = replace(PADRAO, tipo=bp.TIPO_2)
    padrao = bp.calcular(tipo_2)
    assert padrao.geometria.lx == pytest.approx(258 + 4 * 50)  # sem informar: o da tabela
    assert _linha(padrao, "Tipo 2: a₁ na direção ℓx").status == "OK"
    curto = bp.calcular(replace(tipo_2, a1_x_mm=10))
    assert curto.geometria.lx == pytest.approx(258 + 40) and curto.geometria.a1 == 50
    assert _linha(curto, "Tipo 2: a₁ na direção ℓx").status == "OK"
    assert curto.geometria.ly == padrao.geometria.ly  # o a₁ de ℓy continua o da tabela
    for fora in (5, 60):
        r = bp.calcular(replace(tipo_2, a1_x_mm=fora))
        assert _linha(r, "Tipo 2: a₁ na direção ℓx").status == "NÃO OK"
    tipo_1 = bp.calcular(replace(PADRAO, a1_x_mm=10))  # só o tipo 2 usa
    assert tipo_1.geometria.lx == pytest.approx(258 + 4 * 50)
    assert not any(v.nome.startswith("Tipo 2") for v in tipo_1.verificacoes)


def test_f_ck_minimo_da_nota_b_so_no_reto_com_porca():
    fraco = replace(PADRAO, fck_MPa=20)
    assert _linha(bp.calcular(fraco), "Concreto: f_ck").status == "NÃO OK"
    gancho = bp.calcular(replace(fraco, ancoragem=bp.ANCORAGEM_GANCHO))
    assert not any(v.nome.startswith("Concreto: f_ck") for v in gancho.verificacoes)


def test_com_dispositivo_so_ele_resiste():
    r = bp.calcular(replace(PADRAO, cortante=bp.CORTANTE_PLACA))
    nomes = [v.nome for v in r.verificacoes]
    assert not any(n.startswith("Cortante: atrito") for n in nomes)


# ------------------------------------------------------------------ entradas inválidas
@pytest.mark.parametrize(
    "mudanca",
    [
        {"perfil": "nao existe"},
        {"perfil": 'U 10" x 22,77'},
        {"chumbador": '5/8"'},
        {"aco_placa": "ZAR 250 (NBR 7008)"},
        {"t_placa_mm": 0},
        {"v_sd_kN": -1},
        {"a1_mm": -5},
        {"cortante": "outra"},
    ],
)
def test_entrada_invalida_explica(mudanca):
    with pytest.raises(bp.BaseInvalida):
        bp.calcular(replace(PADRAO, **mudanca))


# ------------------------------------------------------------------ grupos, base mais leve, registro
def test_grupos_cobrem_todas_as_linhas_na_ordem():
    for entrada in (PADRAO, replace(PADRAO, n_sd_kN=-50, m_sd_kNm=60, cortante=bp.CORTANTE_PLACA)):
        r = bp.calcular(entrada)
        juntas = [v for _, linhas in r.grupos for v in linhas]
        assert juntas == list(r.verificacoes)
        assert r.grupos[0][0] == bp.GRUPO_GEOMETRIA and r.grupos[-1][0] == bp.GRUPO_CONSTRUTIVAS


def test_base_mais_leve_atende_e_nao_ha_outra_mais_leve():
    entrada = replace(PADRAO, n_sd_kN=100, m_sd_kNm=30, v_sd_kN=60, cortante=bp.CORTANTE_ARRUELAS)
    assert bp.calcular(entrada).status == "NÃO OK"
    leve = bp.base_mais_leve(entrada)
    assert leve is not None and leve.status != "NÃO OK"
    assert leve.entrada.t_placa_mm in bp.ESPESSURAS_COMERCIAIS
    for chumbador in bp.TABELA_18:
        for t in bp.ESPESSURAS_COMERCIAIS:
            r = bp.calcular(replace(entrada, chumbador=chumbador, t_placa_mm=t))
            if r.status != "NÃO OK":
                assert r.massa_da_placa_kg >= leve.massa_da_placa_kg - 1e-9


def test_sem_base_que_atenda_quando_a_falha_nao_e_da_placa():
    entrada = replace(PADRAO, n_sd_kN=-80, m_sd_kNm=10)  # cortante sem contato e sem dispositivo
    assert bp.base_mais_leve(entrada) is None


def test_registro_e_figura_no_memorial():
    r = bp.calcular(replace(PADRAO, n_chumbadores=6, m_sd_kNm=150, t_placa_mm=40))
    registro = bp.registro_base(r)
    assert registro["modulo_id"] == bp.MODULO_ID and registro["status"] == "Atende"
    resultados = registro["resultados"]
    assert resultados["caso"] == "C3"
    assert bp.entrada_de_dicionario(resultados["figura_base_de_pilar"]["entrada"]) == r.entrada
    assert bp.NOTA_TABELA_18 in registro["premissas"]
    assert bp.NOTA_TABELA_18 not in registro["alertas"]
    assert not any("a confirmar" in texto for texto in registro["premissas"])
    assert not any("a confirmar" in texto for texto in registro["referencias"])
    figuras = record_charts.imagens_gravadas(resultados)
    assert len(figuras) == 1 and figuras[0][0].png[:8] == b"\x89PNG\r\n\x1a\n"


def test_memorial_word_desta_base():
    conteudo = bp.memorial_da_base(bp.calcular(PADRAO))
    assert conteudo[:2] == b"PK" and len(conteudo) > 20_000


# ------------------------------------------------------------------ desenho
def _contar(png: bytes, cor: tuple[int, int, int], tolerancia: int = 18) -> int:
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)
    return int((np.abs(pixels - np.array(cor)).max(axis=2) <= tolerancia).sum())


VERMELHO = (0xB9, 0x1C, 0x1C)
AZUL = (0x1D, 0x4E, 0xD8)


@pytest.mark.parametrize(
    ("entrada", "tracao", "pressao"),
    [
        (PADRAO, False, True),
        (replace(PADRAO, n_chumbadores=6, m_sd_kNm=150, t_placa_mm=40), True, True),
        (replace(PADRAO, n_sd_kN=-80, m_sd_kNm=10, cortante=bp.CORTANTE_PLACA), True, False),
        (replace(PADRAO, perfil="W 360 x 51,0", tipo=bp.TIPO_2, n_sd_kN=-40), True, False),
        (replace(PADRAO, n_sd_kN=-50, m_sd_kNm=60), True, True),
        (replace(PADRAO, m_sd_kNm=20), False, True),
        (replace(PADRAO, n_chumbadores=8, chumbador='3/4"', n_sd_kN=0, m_sd_kNm=40), True, True),
    ],
)
def test_desenho_mostra_tracao_e_pressao_so_quando_existem(entrada, tracao, pressao):
    figura = figura_da_base(bp.calcular(entrada))
    imagem = Image.open(io.BytesIO(figura.png))
    assert imagem.size == (figura.largura_px, figura.altura_px) == (1100, 660)
    # a legenda tem sempre uma seta de cada cor (uns 90 px); o desenho soma mais quando existe
    assert (_contar(figura.png, VERMELHO) > 200) is tracao
    assert (_contar(figura.png, AZUL) > 115) is pressao
    assert entrada.perfil in figura.titulo
