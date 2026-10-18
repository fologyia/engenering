"""Ligações: chapa simples (NBR 8800), perfil formado a frio (NBR 14762) e solda de filete."""

from __future__ import annotations

import io
import json
import math
from dataclasses import replace

import pytest
from PIL import Image

from core import bolted_connection as bc
from core import ligacoes as lg
from core import section_catalog as sc
from core.record_charts import imagens_do_registro


def linha(r: lg.ResultadoLigacao, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


# ------------------------------------------------------------------ chapa simples
def test_chapa_simples_parafusos_com_o_momento_v_a():
    e = lg.EntradaChapaSimples()
    r = lg.calcular(e)
    # 3 parafusos a 70 mm: J = 2·70², momento 40·60 = 2400 kN·mm
    esperado = math.hypot(40 / 3, 2400 * 70 / (2 * 70**2))
    v = linha(r, "Parafuso mais solicitado")
    assert v.solicitante == pytest.approx(esperado)
    d = bc.dados_parafuso('3/4"')
    ab = math.pi * d["d_b"] ** 2 / 4
    fv_2024 = 0.45 * ab * 830 / 1.35 / 1000
    tw = sc.obter_perfil(e.perfil).espessura_alma_mm
    contato_alma = 1.2 * (35 - d["d_h"] / 2) * tw * 450 / 1.35 / 1000
    assert v.resistente == pytest.approx(min(fv_2024, contato_alma))
    r_2008 = lg.calcular(
        replace(e, norma="NBR8800_2008", t_chapa_mm=20, borda_alma_mm=80, topo_alma_mm=80)
    )
    fv_2008 = 0.40 * ab * 825 / 1.35 / 1000
    assert "corte" in linha(r_2008, "Parafuso").formula
    assert linha(r_2008, "Parafuso").resistente <= fv_2008 + 1e-9


def test_chapa_e_alma_pelas_formulas_da_6_5():
    e = lg.EntradaChapaSimples()
    r = lg.calcular(e)
    hp = e.altura_chapa_mm
    assert hp == 2 * 35 + 2 * 70
    assert linha(r, "Chapa: escoamento").resistente == pytest.approx(
        0.6 * 250 * hp * 8 / 1.1 / 1000
    )
    dhl = bc.dados_parafuso('3/4"')["d_h"] + 2
    assert linha(r, "Chapa: ruptura").resistente == pytest.approx(
        0.6 * 400 * (hp - 3 * dhl) * 8 / 1.35 / 1000
    )
    assert linha(r, "Chapa: flexão").solicitante == pytest.approx(40 * 0.060)
    perfil = sc.obter_perfil(e.perfil)
    h = perfil.altura_mm - e.recorte_altura_mm
    assert linha(r, "Alma da viga: escoamento").resistente == pytest.approx(
        0.6 * 345 * h * perfil.espessura_alma_mm / 1.1 / 1000
    )
    assert linha(r, "Alma recortada: flexão").solicitante == pytest.approx(40 * 0.100)
    assert r.status == "OK"


def test_solda_da_chapa_pelo_metodo_elastico():
    e = lg.EntradaChapaSimples()
    r = lg.calcular(e)
    comprimento = e.altura_chapa_mm
    f = math.hypot(3 * 2400 / comprimento**2, 40 / (2 * comprimento))
    v = linha(r, "Solda da chapa no apoio")
    assert v.solicitante == pytest.approx(f * 10)
    assert v.resistente == pytest.approx(0.6 * 485 * 0.707 * 6 / 1.35 / 1000 * 10)
    assert linha(r, "Solda: perna mínima").solicitante == 3.0  # t ≤ 6,35 mm (Tabela 10)
    assert lg.perna_minima(10) == 5 and lg.perna_minima(15) == 6 and lg.perna_minima(25) == 8
    assert lg.perna_maxima(5) == 5 and lg.perna_maxima(8) == 6.5


def test_sem_recorte_e_com_cortante_alta():
    r = lg.calcular(lg.EntradaChapaSimples(recorte=False, apoio=lg.APOIO_PILAR_MESA))
    assert linha(r, "Alma recortada: colapso").status == "N/A"
    assert not any(v.nome.startswith("Alma recortada: flexão") for v in r.verificacoes)
    forte = lg.calcular(lg.EntradaChapaSimples(v_sd_kN=300))
    assert forte.status == "NÃO OK" and forte.aproveitamento_maximo > 1
    assert forte.governante is not None


def test_normal_na_chapa_e_criterio_anglo():
    tracao = lg.calcular(lg.EntradaChapaSimples(n_sd_kN=30, anglo=True, grau="A307"))
    assert linha(tracao, "Chapa: tração").solicitante == 30
    assert linha(tracao, "Chapa: interação").solicitante > 0
    assert linha(tracao, "Grau e revestimento").status == "NÃO OK"  # A307 só em secundárias
    compressao = lg.calcular(lg.EntradaChapaSimples(n_sd_kN=-30))
    assert linha(compressao, "Chapa: compressão").solicitante == 30


@pytest.mark.parametrize(
    "alteracao",
    [
        {"n_parafusos": 0},
        {"t_chapa_mm": 0},
        {"v_sd_kN": -1},
        {"perfil": "perfil que não existe"},
        {"aco_chapa": "aço que não existe"},
        {"norma": "AISC360_LRFD"},
        {"recorte": True, "recorte_altura_mm": 0},
    ],
)
def test_chapa_simples_entradas_invalidas(alteracao):
    with pytest.raises(lg.LigacaoInvalida):
        lg.calcular(replace(lg.EntradaChapaSimples(), **alteracao))


# ------------------------------------------------------------------ perfil formado a frio
def test_acos_e_parafusos_da_nbr_14762():
    assert lg.ACOS["ZAR 250 (NBR 7008)"] == (250, 360)
    assert lg.ACOS["CF-26 (NBR 6649)"] == (260, 400)
    assert lg.ACOS["Sem qualificação estrutural (NBR 14762 4.2)"] == (180, 300)
    assert lg.fub_frio("ASTM A325", 19.1) == 825 and lg.fub_frio("ASTM A325", 28.6) == 725
    assert lg.fub_frio(lg.SEM_QUALIFICACAO, 12.7) == 300
    assert lg.furo_padrao_frio(10) == pytest.approx(10.8)
    assert lg.furo_padrao_frio(12.7) == pytest.approx(14.2)


def test_perfil_frio_formulas_da_10_3():
    e = lg.EntradaPerfilFrio()
    r = lg.calcular(e)
    d = 12.7
    t = sc.obter_perfil(e.perfil).espessura_alma_mm
    por_parafuso = 15.0 / 2
    assert linha(r, "Parafuso: cisalhamento").resistente == pytest.approx(
        0.4 * math.pi * d**2 / 4 * 415 / 1.35 / 1000
    )
    assert linha(r, "Esmagamento no perfil").resistente == pytest.approx(
        (0.183 * t + 1.53) * d * t * 360 / 1.55 / 1000
    )
    assert linha(r, "Rasgamento no perfil").resistente == pytest.approx(t * 30 * 360 / 1.45 / 1000)
    assert linha(r, "Esmagamento no perfil").solicitante == pytest.approx(por_parafuso)
    # chapa de 6,35 mm > 4,75: pela NBR 8800
    assert "NBR 8800" in linha(r, "Pressão de contato e rasgamento na chapa").referencia


def test_perfil_frio_tracao_com_ct_e_regra_dos_50():
    e = lg.EntradaPerfilFrio()
    r = lg.calcular(e)
    perfil = sc.obter_perfil(e.perfil)
    t, area, x = perfil.espessura_alma_mm, perfil.area_mm2, perfil.centroide_x_mm
    ct = min(1 - 1.2 * x / 50, 0.9)
    an = area - 14.2 * t
    esperado = min(area * 250 / 1.10, ct * an * 360 / 1.65) / 1000
    assert linha(r, "Perfil: tração").resistente == pytest.approx(esperado)
    regra = linha(r, "Ligação ≥ 50 %")
    assert regra.solicitante == pytest.approx(0.5 * esperado) and regra.status == "NÃO OK"
    viga = lg.calcular(replace(e, barra_axial=False))
    assert not any(v.nome.startswith("Ligação ≥ 50 %") for v in viga.verificacoes)
    comprimida = lg.calcular(replace(e, n_sd_kN=-15))
    assert linha(comprimida, "Ligação ≥ 50 %").status == "ALERTA"  # falta o N_c,Rd da barra
    informada = lg.calcular(replace(e, n_sd_kN=-15, n_rd_barra_kN=40))
    assert linha(informada, "Ligação ≥ 50 %").solicitante == 20


def test_ligacao_curta_demais_e_duas_linhas():
    curta = lg.calcular(lg.EntradaPerfilFrio(passo_mm=20, n_sd_kN=5))
    assert linha(curta, "Perfil: C_t ≥ 0,4").status == "NÃO OK"
    assert linha(curta, "Distância livre entre furos (passo)").status == "NÃO OK"
    duas = lg.calcular(
        lg.EntradaPerfilFrio(
            perfil="C ideal 200×75×20×3",
            n_linhas=2,
            n_por_linha=3,
            passo_mm=60,
            gabarito_mm=70,
            borda_mm=35,
            borda_lateral_mm=35,
            parafuso='5/8"',
            especificacao="ASTM A325",
            n_sd_kN=40,
        )
    )
    assert linha(duas, "Perfil: colapso por rasgamento").status == "OK"
    assert duas.status == "OK"


def test_perfil_a_mao_e_perfil_grosso():
    with pytest.raises(lg.LigacaoInvalida, match="à mão"):
        lg.calcular(lg.EntradaPerfilFrio(perfil=lg.PERFIL_A_MAO))
    mao = lg.calcular(
        lg.EntradaPerfilFrio(
            perfil=lg.PERFIL_A_MAO, t_perfil_mm=3.0, area_perfil_mm2=600, excentricidade_mm=12
        )
    )
    assert mao.grandezas["area_mm2"] == 600
    grosso = lg.calcular(
        lg.EntradaPerfilFrio(
            perfil=lg.PERFIL_A_MAO, t_perfil_mm=6.0, area_perfil_mm2=900, excentricidade_mm=12
        )
    )
    assert grosso.avisos and "NBR 8800" in grosso.avisos[0]


# ------------------------------------------------------------------ solda
def test_solda_dois_filetes_paralelos():
    r = lg.calcular(lg.EntradaSolda())
    v = linha(r, "Solda: metal da solda")
    assert v.solicitante == pytest.approx(40 / 300 * 10)  # V/(2·L) por cm
    assert v.resistente == pytest.approx(0.6 * 485 * 0.707 * 6 / 1.35 / 1000 * 10)
    assert linha(r, "Metal-base").resistente == pytest.approx(0.6 * 250 * 8 / 1.1 / 1000 * 10)


def test_solda_com_momento_e_chapa_fina():
    contorno = lg.EntradaSolda(arranjo=lg.ARRANJO_CONTORNO, m_sd_kNm=2.0, v_sd_kN=0)
    f, _longitudinal, total = lg.forca_por_mm_na_solda(contorno)
    assert total == pytest.approx(2 * 150 + 2 * 100)
    # canto do retângulo: r = √(75² + 50²); J das linhas
    j = 2 * 150**3 / 12 + 2 * 150 * 50**2 + 2 * 100**3 / 12 + 2 * 100 * 75**2
    assert f == pytest.approx(2e3 * math.hypot(75, 50) / j)
    fina = lg.calcular(lg.EntradaSolda(t1_mm=3.0, arranjo=lg.ARRANJO_UM))
    metal_base = linha(fina, "Metal-base fino")
    assert "NBR 14762" in metal_base.referencia
    assert metal_base.resistente == pytest.approx(0.75 * 3 * 400 / 2.0 / 1000 * 10)  # L/t = 50
    assert linha(fina, "Solda: perna máxima").status == "NÃO OK"  # 6 mm numa chapa de 3 mm


# ------------------------------------------------------------------ figuras e registro
@pytest.mark.parametrize(
    "entrada",
    [
        lg.EntradaChapaSimples(),
        lg.EntradaChapaSimples(recorte=False, n_parafusos=1, n_sd_kN=10),
        lg.EntradaPerfilFrio(n_linhas=2),
        lg.EntradaSolda(arranjo=lg.ARRANJO_UM),
    ],
)
def test_figura_e_registro_com_a_figura_no_memorial(entrada):
    r = lg.calcular(entrada)
    figura = lg.figura(r)
    imagem = Image.open(io.BytesIO(figura.png))
    assert imagem.format == "PNG" and imagem.size == (figura.largura_px, figura.altura_px)
    registro = lg.registro_ligacao(r, contexto={"tag": "LG-01"})
    gravado = json.loads(json.dumps(registro))
    assert gravado["modulo_id"] == lg.MODULO_ID
    assert len(gravado["resultados"]["verificações"]) == len(r.verificacoes)
    assert gravado["entradas"]["tag"] == "LG-01"
    imagens, aviso = imagens_do_registro(gravado, {})
    assert aviso == "" and len(imagens) == 1 and imagens[0]["png"] == figura.png


def test_limite_geometrico_nao_define_o_aproveitamento():
    r = lg.calcular(lg.EntradaChapaSimples())
    assert all(
        v.tipo == "limite"
        for v in r.verificacoes
        if v.nome.startswith(("Distância", "Espaçamento"))
    )
    assert r.governante is not None and not r.governante.nome.startswith(
        ("Distância", "Espaçamento")
    )


# ------------------------------------------------------------------ reações dos cálculos registrados
def _registros_de_exemplo() -> dict:
    from core import degrau_escada as de
    from core import degrau_registro as dreg
    from core import longarina_escada as le
    from core import viga_de_piso as vp

    viga = vp.calcular(vp.EntradaVigaDePiso(anglo=True))
    escada = de.calcular_escada(de.EntradaDegrau())
    longarina = le.calcular_longarina(escada, le.EntradaLongarina(trecho_topo_m=0.3))
    registros = [
        vp.registro_viga(viga),
        dreg.registro_degrau(escada, longarina=longarina),
        {"modulo_id": "viga_de_piso", "resultados": {"reacao_de_calculo_kN": "estragado"}},
    ]
    return {"registros_tecnicos": json.loads(json.dumps(registros))}, viga, longarina


def test_reacoes_dos_calculos_registrados():
    from core import longarina_escada as le

    projeto, viga, longarina = _registros_de_exemplo()
    reacoes = lg.reacoes_do_projeto(projeto)
    rotulos = [r.rotulo for r in reacoes]
    assert any(r.endswith("reação de cálculo") for r in rotulos)
    de_calculo = next(r for r in reacoes if r.rotulo.endswith("reação de cálculo"))
    assert de_calculo.v_kN == pytest.approx(viga.reacao_calculo_kN, rel=1e-3)
    if viga.reacao_minima_ligacao_kN and viga.reacao_minima_ligacao_kN > viga.reacao_calculo_kN:
        assert any("Anglo 9.1" in r for r in rotulos)
    apoios = [r for r in reacoes if "(ELU)" in r.rotulo]
    esperadas = longarina.longarinas[0].reacoes(le.ELU)
    assert len(apoios) == 2
    assert apoios[0].v_kN == pytest.approx(abs(esperadas[0].ry), rel=1e-3)
    assert apoios[0].n_kN == pytest.approx(esperadas[0].rx, rel=1e-3, abs=1e-6)
    assert lg.reacoes_do_projeto(None) == [] and lg.reacoes_do_projeto({}) == []
