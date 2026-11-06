"""Placas de base: disposições fora da Figura 21, aço e tipo do chumbador e ancoragem (ACI 318-19)."""

from __future__ import annotations

import io
import math
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from core import base_de_pilar as bp
from core.desenho_placa_base import figura_da_base

PADRAO = bp.EntradaBase()  # W 250 x 32,7, tipo 1, 4 × Ø 1", t_p 25 mm, f_ck 25, N 300 kN, V 20 kN
SIGMA_RD = 25.0 / (1.4 * 1.4)
C3_6 = replace(PADRAO, n_chumbadores=6, m_sd_kNm=150, t_placa_mm=40)  # F_t = 98,1 kN por chumbador
ROTULADA = replace(PADRAO, tipo=bp.TIPO_ROTULADA, n_chumbadores=2)
MISTA = replace(PADRAO, perfil="W 360 x 51,0", tipo=bp.TIPO_INTERNOS_E_EXTERNOS, n_chumbadores=8)


def _linha(r: bp.ResultadoBase, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def _tem(r: bp.ResultadoBase, inicio: str) -> bool:
    return any(v.nome.startswith(inicio) for v in r.verificacoes)


def _equilibrio(r: bp.ResultadoBase) -> tuple[float, float]:
    g = r.geometria
    compressao = momento = 0.0
    if r.l_c is not None and r.caso in ("C3", "T3"):
        compressao = r.sigma_c_rd * r.l_c * g.ly
        momento = compressao * (g.lx / 2 - r.l_c / 2)
    tracao = sum(r.forcas_nos_chumbadores)
    momento -= sum(f * x for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True))
    return compressao - tracao, momento


# ------------------------------------------------------------------ geometria das disposições
def test_rotulada_tem_dois_chumbadores_no_eixo():
    g = bp.calcular(replace(ROTULADA, n_sd_kN=-40, v_sd_kN=0)).geometria
    assert g.posicoes == ((0.0, -50.0), (0.0, 50.0))
    assert g.a == 0 and g.ly == pytest.approx(100 + 2 * 50)
    assert g.l0 == pytest.approx(1.75 * (100 - 6.1))


def test_internos_e_externos_tem_quatro_linhas():
    g = bp.calcular(replace(MISTA, n_sd_kN=-100, v_sd_kN=0)).geometria
    assert sorted({x for x, _ in g.posicoes}) == pytest.approx([-g.a, -50, 50, g.a])
    assert g.a == pytest.approx(g.lx / 2 - 50) and len(g.posicoes) == 8
    assert g.l0 == pytest.approx(100 + 1.75 * (100 - 7.2))


@pytest.mark.parametrize(("tipo", "n"), [(bp.TIPO_ROTULADA, 4), (bp.TIPO_INTERNOS_E_EXTERNOS, 6)])
def test_numero_de_chumbadores_das_novas_disposicoes(tipo, n):
    r = bp.calcular(replace(PADRAO, tipo=tipo, n_chumbadores=n))
    assert _linha(r, "Número de chumbadores").status == "NÃO OK"


def test_rotulada_fora_da_tabela_18_pede_a_ancoragem_no_concreto():
    """Nota a: a Tabela 18 vale de 4 a 8 chumbadores; com 2, o embutimento dela não basta."""
    r = bp.calcular(ROTULADA)
    linha = _linha(r, "Tabela 18 com 2 chumbadores")
    assert linha.status == "ALERTA" and r.status == "ALERTA" and "nota a" in linha.referencia
    verificada = bp.calcular(replace(ROTULADA, verificar_concreto=True))
    assert _linha(verificada, "Tabela 18 com 2 chumbadores").status == "INFO"
    for padrao in (PADRAO, replace(PADRAO, tipo=bp.TIPO_INTERNOS_E_EXTERNOS, n_chumbadores=8)):
        assert not any(v.nome.startswith("Tabela 18 com") for v in bp.calcular(padrao).verificacoes)


def test_disposicao_fora_da_figura_21_avisa_o_metodo():
    r = bp.calcular(ROTULADA)
    assert any("Figura 21" in a for a in r.avisos)
    assert not any("Figura 21" in a for a in bp.calcular(PADRAO).avisos)
    assert "Figura 21" in bp.registro_base(r)["metodo"]


def test_arruela_interna_que_bate_na_mesa_reprova():
    pequeno = bp.calcular(replace(PADRAO, perfil="W 150 x 13,0", tipo=bp.TIPO_2, n_sd_kN=-20))
    assert _linha(pequeno, "Chumbadores internos: arruela").status == "NÃO OK"
    grande = bp.calcular(replace(MISTA, n_sd_kN=-100, v_sd_kN=0))
    assert _linha(grande, "Chumbadores internos: arruela").status == "OK"


# ------------------------------------------------------------------ método geral
def test_metodo_geral_reproduz_a_norma_com_uma_linha_tracionada():
    """No tipo 1, a regra geral (placa rígida) dá o mesmo ℓ_c e as mesmas forças da 6.7.2.2 c)."""
    r = bp.calcular(C3_6)
    sigma = r.sigma_c_rd
    solucao = bp.equilibrio_geral(r.geometria, sigma, 300e3, 150e6)
    assert solucao is not None
    l_c, forcas = solucao
    assert l_c == pytest.approx(r.l_c, rel=1e-6)
    assert forcas == pytest.approx(r.forcas_nos_chumbadores, rel=1e-6)


def test_braco_sem_contato_e_o_a_nos_tipos_da_norma():
    g = bp.calcular(PADRAO).geometria
    assert bp.braco_sem_contato(g) == pytest.approx(g.a)
    assert bp.braco_sem_contato(bp.calcular(ROTULADA).geometria) == 0


@pytest.mark.parametrize(
    "entrada",
    [
        replace(ROTULADA, m_sd_kNm=60),  # C3: 51 < M < 66,9 kN·m (o máximo da rotulada)
        replace(ROTULADA, n_sd_kN=-50, m_sd_kNm=5, v_sd_kN=0),
        replace(ROTULADA, n_sd_kN=0, m_sd_kNm=10),
        replace(MISTA, m_sd_kNm=120, t_placa_mm=38),
        replace(MISTA, n_sd_kN=-100, m_sd_kNm=5, v_sd_kN=0),
        replace(MISTA, n_sd_kN=-100, m_sd_kNm=60, v_sd_kN=0),
        replace(MISTA, n_sd_kN=0, m_sd_kNm=90),
    ],
)
def test_metodo_geral_equilibra_n_e_m(entrada):
    r = bp.calcular(entrada)
    normal, momento = _equilibrio(r)
    assert normal == pytest.approx(entrada.n_sd_kN * 1e3, abs=1e-2)
    assert momento == pytest.approx(entrada.m_sd_kNm * 1e6, rel=1e-6, abs=1.0)


def test_t2_geral_distribui_linear():
    r = bp.calcular(replace(MISTA, n_sd_kN=-100, m_sd_kNm=5, v_sd_kN=0))
    g = r.geometria
    assert r.caso == "T2"
    soma = sum(x * x for x, _ in g.posicoes)
    for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True):
        assert f == pytest.approx(100e3 / 8 - 5e6 * x / soma)


def test_rotulada_com_momento_e_tracao_vai_a_t3():
    r = bp.calcular(replace(ROTULADA, n_sd_kN=-50, m_sd_kNm=5, v_sd_kN=0))
    assert r.caso == "T3" and r.l_c is not None and r.l_c > 0


def test_rotulada_nao_segura_momento_grande():
    """Com os chumbadores no eixo, só o concreto faz braço: M_máx = σ·ℓy·(ℓx/2)²/2 ≈ 66,9 kN·m."""
    r = bp.calcular(replace(ROTULADA, m_sd_kNm=80))
    assert r.caso == "C3" and r.l_c is None
    assert _linha(r, "Equilíbrio possível").status == "NÃO OK"


def test_espessura_dos_internos_da_rotulada_bate_com_a_conta_de_mao():
    r = bp.calcular(replace(ROTULADA, n_sd_kN=-40, v_sd_kN=0))
    f = 20e3
    l0 = 1.75 * (100 - 6.1)
    assert r.t_p_min == pytest.approx(math.sqrt(2 * f * (100 - 6.1) / (l0 * 250 / 1.10)))


def test_externos_da_mista_usam_a_conta_do_tipo_1():
    r = bp.calcular(replace(MISTA, n_sd_kN=-100, m_sd_kNm=5, v_sd_kN=0))
    g = r.geometria
    linha = [f for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True) if x == -g.a]
    t_ext = math.sqrt(4 * sum(linha) * (g.a - 0.475 * g.d) / (g.ly * 250 / 1.10))
    assert r.t_p_min >= t_ext - 1e-9


# ------------------------------------------------------------------ aço do chumbador
def test_aco_mais_resistente_reduz_d_b_min_e_alerta_a_ancoragem():
    a36 = bp.calcular(C3_6)
    gr55 = bp.calcular(replace(C3_6, aco_chumbador="ASTM F1554 Gr 55"))
    d36, d55 = _linha(a36, "Chumbador: diâmetro").solicitante, _linha(gr55, "Chumbador: diâmetro").solicitante  # fmt: skip
    assert d55 == pytest.approx(d36 * math.sqrt(400 / 517))
    assert gr55.status == "ALERTA" and _linha(gr55, "Aço do chumbador").status == "ALERTA"
    assert not _tem(
        bp.calcular(replace(C3_6, aco_chumbador="ASTM F1554 Gr 36")), "Aço do chumbador"
    )


def test_com_a_ancoragem_verificada_o_aco_vira_informacao():
    r = bp.calcular(replace(C3_6, aco_chumbador="ASTM A193 B7", verificar_concreto=True))
    assert _linha(r, "Aço do chumbador").status == "INFO"


# ------------------------------------------------------------------ tipos de chumbador (ACI 318-19)
def test_reto_com_porca_so_verifica_o_concreto_quando_pedido():
    assert not _tem(bp.calcular(C3_6), "Arrancamento da cabeça")
    r = bp.calcular(replace(C3_6, verificar_concreto=True))
    a_brg = math.sqrt(3) / 2 * (1.5 * 25 + 3.2) ** 2 - math.pi * 25**2 / 4
    assert bp.area_de_apoio_da_ponta(r.entrada, bp.TABELA_18['1"']) == pytest.approx(a_brg)
    linha = _linha(r, "Arrancamento da cabeça")
    assert linha.resistente == pytest.approx(0.70 * 8 * a_brg * 25 / 1e3)
    assert linha.solicitante == pytest.approx(r.f_t_sd / 1e3)


def test_chapa_na_ponta_aumenta_a_area_de_apoio():
    e = replace(C3_6, verificar_concreto=True, chapa_na_ponta_mm=100)
    assert bp.area_de_apoio_da_ponta(e, bp.TABELA_18['1"']) == pytest.approx(100**2 - math.pi * 25**2 / 4)  # fmt: skip


def test_cone_de_concreto_bate_com_a_conta_de_mao():
    """Linha tracionada x = −179, y = −100/0/100; h_ef = 465 → 419,3.

    Bloco mínimo da nota e da Tabela 18: N_b = máx(900; 458 + 220) = 900 e B_b = 300 + 220 = 520.
    """
    r = bp.calcular(replace(C3_6, verificar_concreto=True))
    h = (450 + 179) / 1.5  # perto das 4 bordas: h_ef' = c_a,máx/1,5 (17.6.2.1.2)
    a_nc, a_nco = 900 * 520, 9 * h * h
    psi_ed = 0.7 + 0.3 * (260 - 100) / (1.5 * h)  # a borda mais perto é a de y
    n_b = 3.9 * 5 * h ** (5 / 3)
    esperado = 0.70 * a_nc / a_nco * psi_ed * n_b
    linha = _linha(r, "Cone de concreto")
    assert linha.resistente == pytest.approx(esperado / 1e3, rel=1e-6)
    assert linha.solicitante == pytest.approx(3 * r.f_t_sd / 1e3)
    assert linha.status == "NÃO OK"  # o bloco mínimo sem armadura não segura 324 kN
    assert any("cone de concreto" in a for a in r.avisos)


def test_armadura_de_ancoragem_tira_o_cone_da_conta():
    r = bp.calcular(replace(C3_6, verificar_concreto=True, armadura_de_ancoragem=True))
    linha = _linha(r, "Cone de concreto")
    assert linha.status == "INFO" and "armadura" in linha.formula
    assert r.status == "OK"


def test_bloco_maior_passa_no_cone():
    r = bp.calcular(replace(C3_6, verificar_concreto=True, bloco_x_mm=1500, bloco_y_mm=1200))
    assert _linha(r, "Cone de concreto").status == "OK"


def test_arrancamento_lateral_perto_da_borda():
    r = bp.calcular(replace(C3_6, verificar_concreto=True, bloco_x_mm=700, bloco_y_mm=1000))
    linha = _linha(r, "Arrancamento lateral")  # c_a1 = 350 − 179 = 171 < 0,4·h_ef = 186
    a_brg = bp.area_de_apoio_da_ponta(r.entrada, bp.TABELA_18['1"'])
    n_sb = 13 * 171 * math.sqrt(a_brg) * 5
    fator_c2 = (1 + min(max((500 - 100) / 171, 1.0), 3.0)) / 4 if 500 - 100 < 3 * 171 else 1.0
    esperado = 0.70 * (1 + 200 / (6 * 171)) * n_sb * fator_c2
    assert linha.resistente == pytest.approx(esperado / 1e3, rel=1e-6)


def test_guarda_chuva_arranca_pelo_gancho():
    r = bp.calcular(replace(C3_6, ancoragem=bp.ANCORAGEM_GANCHO))
    linha = _linha(r, "Guarda-chuva: arrancamento")
    assert linha.resistente == pytest.approx(0.70 * 0.9 * 25 * 4.5 * 25 * 25 / 1e3)
    assert linha.status == "NÃO OK" and r.status == "NÃO OK"
    assert _linha(r, "Guarda-chuva: comprimento").status == "OK"
    assert any("guarda-chuva" in a for a in r.avisos)
    curto = bp.calcular(replace(C3_6, ancoragem=bp.ANCORAGEM_GANCHO, e_h_mm=60))
    assert _linha(curto, "Guarda-chuva: comprimento").status == "NÃO OK"
    longo = bp.calcular(replace(C3_6, ancoragem=bp.ANCORAGEM_GANCHO, e_h_mm=400))
    assert _linha(longo, "Guarda-chuva: arrancamento").resistente == pytest.approx(linha.resistente)  # fmt: skip


@pytest.mark.parametrize("tipo", [bp.ANCORAGEM_QUIMICO, bp.ANCORAGEM_EXPANSAO])
def test_pos_instalado_usa_o_fabricante_e_o_cone_com_k_7(tipo):
    sem = bp.calcular(replace(C3_6, ancoragem=tipo))
    assert _linha(sem, "Pós-instalado").status == "ALERTA"
    com = bp.calcular(replace(C3_6, ancoragem=tipo, n_rd_fabricante_kN=120))
    linha = _linha(com, "Pós-instalado")
    assert linha.status == "OK" and linha.resistente == 120
    assert "7·√f_c" in _linha(com, "Cone de concreto").formula
    assert "h_ef = " in _linha(com, "Cone de concreto").formula
    assert bp.embutimento(com.entrada, bp.TABELA_18['1"']) == 12 * 25


def test_base_mais_leve_nao_troca_o_diametro_do_pos_instalado_com_n_rd():
    """O N_Rd do fabricante é do diâmetro informado: trocar o chumbador o invalidaria."""
    e = replace(
        C3_6, ancoragem=bp.ANCORAGEM_QUIMICO, n_rd_fabricante_kN=150, armadura_de_ancoragem=True
    )
    leve = bp.base_mais_leve(e)
    assert leve is not None and leve.entrada.chumbador == e.chumbador
    sem_n_rd = bp.base_mais_leve(replace(C3_6, verificar_concreto=True, armadura_de_ancoragem=True))
    assert sem_n_rd is not None  # o reto com porca pode trocar de diâmetro


def test_sem_tracao_a_ancoragem_nao_se_aplica():
    r = bp.calcular(replace(PADRAO, ancoragem=bp.ANCORAGEM_EXPANSAO))
    assert r.status == "OK" and _linha(r, "Ancoragem no concreto").status == "INFO"


def test_momento_no_eixo_fraco_entra_pela_flexao_obliqua():
    r = bp.calcular(replace(PADRAO, m_sd_y_kNm=5))
    assert r.status == "OK" and _linha(r, "Flexão oblíqua").status == "INFO"
    assert r.zona_comprimida and any("Flexão oblíqua" in a for a in r.avisos)
    assert bp.registro_base(r)["entradas"]["M_Sd_y_kNm"] == 5


def test_entrada_invalida_dos_novos_campos():
    for mudanca in ({"aco_chumbador": "X"}, {"ancoragem": "Y"}, {"h_ef_mm": -1}):
        with pytest.raises(bp.BaseInvalida):
            bp.calcular(replace(PADRAO, **mudanca))


def test_registro_leva_o_tipo_e_o_aco_do_chumbador():
    r = bp.calcular(replace(C3_6, ancoragem=bp.ANCORAGEM_QUIMICO, aco_chumbador="ASTM F1554 Gr 55"))
    entradas = bp.registro_base(r)["entradas"]
    assert "Gr 55" in entradas["chumbadores"]
    assert entradas["ancoragem"] == bp.ANCORAGENS[bp.ANCORAGEM_QUIMICO]
    assert entradas["ancoragem_no_concreto"] == "ACI 318-19, Capítulo 17"
    gravada = bp.entrada_de_dicionario(bp.registro_base(r)["resultados"]["figura_base_de_pilar"]["entrada"])  # fmt: skip
    assert gravada == r.entrada


# ------------------------------------------------------------------ desenho
VERMELHO = (0xB9, 0x1C, 0x1C)
RESINA = (0xFB, 0xBF, 0x24)


def _contar(png: bytes, cor: tuple[int, int, int], tolerancia: int = 18) -> int:
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)
    # em pixels de tela: o arquivo tem o dobro em cada direção
    return int((np.abs(pixels - np.array(cor)).max(axis=2) <= tolerancia).sum()) // 4


@pytest.mark.parametrize(
    "entrada",
    [
        replace(ROTULADA, n_sd_kN=-50, m_sd_kNm=5, v_sd_kN=0),
        replace(MISTA, n_sd_kN=-100, m_sd_kNm=5, v_sd_kN=0),
        replace(MISTA, m_sd_kNm=120, t_placa_mm=38),
        replace(C3_6, ancoragem=bp.ANCORAGEM_GANCHO),
        replace(C3_6, ancoragem=bp.ANCORAGEM_EXPANSAO),
        replace(C3_6, verificar_concreto=True, chapa_na_ponta_mm=100),
    ],
)
def test_desenho_das_disposicoes_e_tipos(entrada):
    figura = figura_da_base(bp.calcular(entrada))
    assert figura.largura_px <= 1100 and figura.altura_px <= 660
    assert _contar(figura.png, VERMELHO) > 200  # chumbadores tracionados
    assert bp.NOMES_CURTOS[entrada.tipo] in figura.titulo


CONE = (0xDC, 0x26, 0x26)
HACHURA = (0x60, 0xA5, 0xFA)
ARMADURA = (0x6B, 0x72, 0x80)


def test_desenho_mostra_cone_hachura_e_armadura_so_quando_existem():
    sem = figura_da_base(bp.calcular(C3_6)).png
    cone = figura_da_base(bp.calcular(replace(C3_6, verificar_concreto=True))).png
    armado = figura_da_base(
        bp.calcular(replace(C3_6, verificar_concreto=True, armadura_de_ancoragem=True))
    ).png
    compressao = figura_da_base(bp.calcular(PADRAO)).png  # C1: sem hachura, sem cone
    assert _contar(cone, CONE, 12) > _contar(sem, CONE, 12) + 60  # linhas finas tracejadas
    assert _contar(armado, ARMADURA, 10) > _contar(cone, ARMADURA, 10) + 60
    assert _contar(sem, HACHURA, 12) > _contar(compressao, HACHURA, 12) + 60


def test_desenho_usa_o_mesmo_bloco_da_verificacao_do_cone():
    from core.desenho_placa_base import _texto_do_bloco

    r = bp.calcular(C3_6)
    assert _texto_do_bloco(r.entrada, r.geometria).startswith("Bloco 900 × 520 mm (mín.")
    informado = replace(C3_6, bloco_x_mm=1500, bloco_y_mm=1200)
    assert _texto_do_bloco(informado, bp.calcular(informado).geometria).startswith("Bloco 1500 × 1200 mm,")  # fmt: skip


def test_desenho_do_quimico_mostra_a_resina():
    sem = figura_da_base(bp.calcular(C3_6))
    com = figura_da_base(bp.calcular(replace(C3_6, ancoragem=bp.ANCORAGEM_QUIMICO)))
    assert _contar(com.png, RESINA) > _contar(sem.png, RESINA) + 500
