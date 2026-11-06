"""A seção em faixas e a Flexão de uma seção, contra fórmulas fechadas e equilíbrio."""

from __future__ import annotations

import io
import math

import numpy as np
import pytest
from PIL import Image

from components import assistente_cargas_ui as ui
from components.elementos_croquis import croqui_da_flexao
from core import elementos_catalogo as cat
from core import elementos_vigas as ev
from core import geometria_da_secao as gs
from core.beam_charts import so_a_conta
from core.elementos_base import Resultado, calcular_caso

FLEXAO = "flexao_secao"


def rodar(**valores) -> Resultado:
    return calcular_caso(cat.CASOS[FLEXAO], valores)


def metrica(resultado: Resultado, rotulo: str) -> float:
    return next(float(m.valor) for m in resultado.metricas if m.rotulo == rotulo)


def linha(resultado: Resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


RETANGULO = {"tipo_secao": ev.RETANGULAR, "b_mm": 100.0, "h_mm": 200.0}


# ---------------------------------------------------------------------------
# Faixas: propriedades da forma
# ---------------------------------------------------------------------------


def test_retangulo_propriedades_fechadas():
    f = gs.faixas_da_secao(gs.retangulo(100.0, 200.0))
    assert f.area == pytest.approx(20000.0)
    assert f.inercia == pytest.approx(100.0 * 200.0**3 / 12.0)
    assert f.modulo_plastico == pytest.approx(100.0 * 200.0**2 / 4.0)
    assert f.q.max() == pytest.approx(100.0 * 200.0**2 / 8.0)


def test_circulo_propriedades_fechadas():
    f = gs.faixas_da_secao(gs.circulo(80.0))
    assert f.area == pytest.approx(math.pi * 80.0**2 / 4.0, rel=1e-3)
    assert f.inercia == pytest.approx(math.pi * 80.0**4 / 64.0, rel=1e-3)
    assert f.modulo_plastico == pytest.approx(80.0**3 / 6.0, rel=1e-3)


def test_tubo_circular_propriedades_fechadas():
    f = gs.faixas_da_secao(gs.circulo(100.0, 90.0))
    assert f.area == pytest.approx(math.pi * (100.0**2 - 90.0**2) / 4.0, rel=2e-3)
    assert f.inercia == pytest.approx(math.pi * (100.0**4 - 90.0**4) / 64.0, rel=2e-3)


def test_perfil_i_propriedades_a_mao():
    f = gs.faixas_da_secao(gs.perfil_i(200.0, 100.0, 10.0, 6.0))
    assert f.area == pytest.approx(2 * 100 * 10 + 180 * 6)
    assert f.inercia == pytest.approx(100 * 200**3 / 12 - 94 * 180**3 / 12)
    # Q em G: as duas parcelas acima do eixo
    assert f.q.max() == pytest.approx(100 * 10 * 95 + 90 * 6 * 45)


def test_tubo_retangular_propriedades_a_mao():
    f = gs.faixas_da_secao(gs.tubo_retangular(100.0, 150.0, 6.0))
    assert f.area == pytest.approx(100 * 150 - 88 * 138)
    assert f.inercia == pytest.approx((100 * 150**3 - 88 * 138**3) / 12)


def test_perfil_u_tem_a_origem_em_g():
    g = gs.perfil_u(200.0, 75.0, 10.0, 6.0)
    area = 2 * 75 * 10 + 180 * 6
    momento = sum(
        (x1 * y2 - x2 * y1) * (x1 + x2)
        for (x1, y1), (x2, y2) in zip(g.cheios[0], (*g.cheios[0][1:], g.cheios[0][0]), strict=True)
    )
    assert momento / 6.0 / area == pytest.approx(0.0, abs=1e-9)


def test_seca_deitada_troca_altura_e_largura():
    f = gs.faixas_da_secao(gs.retangulo(100.0, 200.0).deitada())
    assert f.y_topo - f.y_base == pytest.approx(100.0)
    assert f.inercia == pytest.approx(200.0 * 100.0**3 / 12.0)


def test_centro_fora_da_origem_e_corrigido():
    """Seção deslocada: o y das faixas é sempre medido de G."""
    r = gs.Geometria((((0.0, 10.0), (20.0, 10.0), (20.0, 50.0), (0.0, 50.0)),))
    f = gs.faixas_da_secao(r)
    assert f.y_centro == pytest.approx(30.0)
    assert f.y_topo == pytest.approx(20.0)
    assert f.inercia == pytest.approx(20.0 * 40.0**3 / 12.0)


# ---------------------------------------------------------------------------
# Cisalhamento
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("geometria", "fator"),
    [
        (gs.retangulo(100.0, 200.0), 1.5),
        (gs.circulo(80.0), 4.0 / 3.0),
        (gs.circulo(100.0, 99.0), 2.0),
    ],
)
def test_tau_maximo_das_formas_conhecidas(geometria, fator):
    f = gs.faixas_da_secao(geometria)
    assert f.tau(1000.0).max() == pytest.approx(fator * 1000.0 / f.area, rel=4e-3)


@pytest.mark.parametrize(
    "geometria",
    [
        gs.retangulo(100.0, 200.0),
        gs.circulo(80.0),
        gs.circulo(100.0, 80.0),
        gs.perfil_i(250.0, 100.0, 8.0, 6.0),
        gs.perfil_u(200.0, 75.0, 10.0, 6.0),
        gs.tubo_retangular(100.0, 150.0, 6.0),
    ],
)
def test_integral_do_cisalhamento_devolve_a_cortante(geometria):
    f = gs.faixas_da_secao(geometria)
    integral = -np.trapezoid(f.tau(5000.0) * f.b, f.y)
    assert integral == pytest.approx(5000.0, rel=1e-3)


def test_salto_de_tau_na_juncao_alma_mesa():
    """Q é contínuo na junção; quem muda é b. O salto é a razão das larguras."""
    f = gs.faixas_da_secao(gs.perfil_i(200.0, 100.0, 10.0, 6.0))
    tau = f.tau(1000.0)
    i_mesa = int(np.argmin(np.abs(f.y - (90.0 + 1e-3))))
    i_alma = int(np.argmin(np.abs(f.y - (90.0 - 1e-3))))
    assert tau[i_alma] / tau[i_mesa] == pytest.approx(100.0 / 6.0, rel=1e-3)


def test_tubo_retangular_usa_duas_paredes_na_largura():
    f = gs.faixas_da_secao(gs.tubo_retangular(100.0, 150.0, 6.0))
    assert f.tau(1000.0).max() == pytest.approx(1000.0 * f.q.max() / (f.inercia * 12.0))


# ---------------------------------------------------------------------------
# Linha neutra e tensões
# ---------------------------------------------------------------------------


def test_linha_neutra_no_centro_sem_forca_axial():
    assert gs.linha_neutra(-100.0, 100.0, 50.0, -50.0) == pytest.approx(0.0)


def test_linha_neutra_sobe_com_tracao():
    assert gs.linha_neutra(-50.0, 150.0, 50.0, -50.0) == pytest.approx(25.0)


def test_sem_linha_neutra_quando_a_secao_fica_toda_de_um_lado():
    assert gs.linha_neutra(50.0, 150.0, 50.0, -50.0) is None


def test_von_mises_combina_no_mesmo_ponto():
    f = gs.faixas_da_secao(gs.retangulo(100.0, 200.0))
    t = gs.tensoes_ao_longo(f, -30.0, 30.0, 40000.0)
    meio = int(np.argmin(np.abs(t.y)))
    assert t.sigma[meio] == pytest.approx(0.0, abs=1e-3)
    assert t.mises[meio] == pytest.approx(math.sqrt(3.0) * 3.0, rel=1e-3)
    assert t.sigma[0] == pytest.approx(-30.0)
    assert t.sigma[-1] == pytest.approx(30.0)


def test_tau_extra_soma_em_toda_a_altura():
    f = gs.faixas_da_secao(gs.tubo_retangular(100.0, 150.0, 6.0))
    t = gs.tensoes_ao_longo(f, -10.0, 10.0, 0.0, 25.0)
    assert t.tau == pytest.approx(np.full_like(t.tau, 25.0))


# ---------------------------------------------------------------------------
# Caso Flexão de uma seção
# ---------------------------------------------------------------------------


def test_catalogo_passa_a_usar_v_q_sobre_i_t_e_nao_v_sobre_av():
    r = rodar(v_kN=100.0, m_kNm=1.0)
    assert "V·Q/(I·b)" in linha(r, "Tensão de cisalhamento").formula
    assert metrica(r, "Cortante máximo") > 100000.0 / (258.0 * 6.1)


def test_momento_e_cortante_admissiveis_levam_ao_limite():
    r = rodar(**RETANGULO, m_kNm=20.0, v_kN=40.0)
    no_limite_m = rodar(**RETANGULO, m_kNm=metrica(r, "Momento admissível"), v_kN=0.0)
    assert linha(no_limite_m, "Tensão normal").aproveitamento == pytest.approx(1.0, rel=1e-2)
    no_limite_v = rodar(**RETANGULO, m_kNm=0.0, v_kN=metrica(r, "Cortante admissível"))
    assert linha(no_limite_v, "Tensão de cisalhamento").aproveitamento == pytest.approx(
        1.0, rel=1e-2
    )


def test_fator_de_forma_do_retangulo_e_do_circulo():
    assert metrica(rodar(**RETANGULO), "Fator de forma Z/W") == pytest.approx(1.5, rel=1e-3)
    circulo = rodar(tipo_secao=ev.CIRCULAR, d_mm=80.0, m_kNm=1.0)
    assert metrica(circulo, "Fator de forma Z/W") == pytest.approx(16 / (3 * math.pi), rel=2e-3)


def test_inicio_de_escoamento_e_plastificacao_do_retangulo():
    r = rodar(**RETANGULO, sy_MPa=250.0)
    w = 100.0 * 200.0**2 / 6.0
    assert metrica(r, "Início do escoamento M_y") == pytest.approx(250.0 * w / 1e6, rel=1e-3)
    assert metrica(r, "Seção toda escoada M_p") == pytest.approx(1.5 * 250.0 * w / 1e6, rel=1e-3)


def test_juncao_alma_mesa_governa_com_cortante_alto():
    """As fibras passam, e a junção, onde σ ainda é alto e τ já é grande, reprova."""
    r = rodar(perfil="W 250 x 28,4", m_kNm=50.0, v_kN=100.0, sy_MPa=250.0, fs=1.5)
    assert linha(r, "Tensão normal").status == "OK"
    assert linha(r, "von Mises na seção").status == "NÃO OK"
    assert any("junção da alma com a mesa" in a for a in r.alertas)


def test_ponto_mais_solicitado_vai_para_o_circulo_de_mohr():
    r = rodar(perfil="W 250 x 28,4", m_kNm=50.0, v_kN=100.0)
    ponto = next(p for p in r.pontos if p.nome.startswith("Mais solicitado"))
    assert ponto.sigma_x != 0.0 and ponto.tau_xy > 0.0
    assert r.ponto_critico == ponto


def test_retangulo_nao_cria_ponto_a_mais_quando_a_fibra_governa():
    r = rodar(**RETANGULO, m_kNm=20.0, v_kN=1.0)
    assert [p.nome for p in r.pontos] == ["Fibra de cima", "Fibra de baixo", "Centro da seção"]


def test_forca_axial_desloca_a_linha_neutra_e_avisa():
    r = rodar(**RETANGULO, m_kNm=10.0, n_kN=100.0, v_kN=0.0)
    w = 100.0 * 200.0**2 / 6.0
    deslocamento = (100000.0 / 20000.0) / (10e6 / w) * 100.0
    assert any(f"{deslocamento:.1f} mm de G" in a for a in r.alertas)
    assert any("acima" in a for a in r.alertas)


def test_tabela_compara_os_dois_eixos_do_perfil():
    r = rodar(perfil="W 250 x 28,4", m_kNm=10.0)
    tabela = next(t for t in r.tabelas if t.titulo == "O mesmo perfil no outro eixo")
    assert [lin["Situação"] for lin in tabela.linhas] == ["atual", ""]
    assert tabela.linhas[1]["σ máx (MPa)"] > 4 * tabela.linhas[0]["σ máx (MPa)"]


def test_eixo_fraco_gira_a_secao():
    forte = rodar(perfil="W 250 x 28,4", m_kNm=1.0)
    fraco = rodar(perfil="W 250 x 28,4", m_kNm=1.0, eixo=ev.EIXO_FRACO)
    assert metrica(fraco, "W da seção") < metrica(forte, "W da seção")


def test_propriedades_informadas_sem_forma_saem_sem_tau_ao_longo():
    r = rodar(tipo_secao=ev.INFORMAR, a_mm2=6000.0, i_mm4=2e7, w_mm3=3e5, m_kNm=20.0)
    assert "V/A_v" in linha(r, "Tensão de cisalhamento").formula
    assert all(v.nome != "von Mises na seção" for v in r.verificacoes)
    assert r.figuras


# ---------------------------------------------------------------------------
# Desenhos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valores",
    [
        {},
        {"eixo": ev.EIXO_FRACO},
        {"perfil": 'U 6" x 12,20'},
        RETANGULO,
        {"tipo_secao": ev.CIRCULAR, "d_mm": 80.0},
        {"tipo_secao": ev.TUBO_CIRCULAR, "d_mm": 100.0, "t_mm": 5.0},
        {"tipo_secao": ev.TUBO_RETANGULAR, "b_mm": 100.0, "h_mm": 150.0, "t_mm": 6.0},
        {"tipo_secao": ev.INFORMAR, "a_mm2": 6000.0, "i_mm4": 2e7, "w_mm3": 3e5},
    ],
)
def test_figura_sai_para_toda_forma_e_cabe_na_coluna(valores):
    imagem = Image.open(io.BytesIO(rodar(**valores).figuras[0].png))
    assert imagem.format == "PNG"
    assert imagem.width / 2 <= 640


def test_chapa_deitada_nao_vira_uma_linha():
    r = rodar(tipo_secao=ev.RETANGULAR, b_mm=300.0, h_mm=8.0, m_kNm=0.1, v_kN=1.0)
    assert Image.open(io.BytesIO(r.figuras[0].png)).height / 2 > 180


def test_figura_muda_com_o_sinal_do_momento():
    assert rodar(m_kNm=30.0).figuras[0].png != rodar(m_kNm=-30.0).figuras[0].png


def test_varredura_de_medidas_nao_gasta_tempo_com_a_figura():
    with so_a_conta():
        assert rodar().figuras[0].png == b""


def test_croqui_mostra_a_forma_escolhida():
    padrao = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    perfil = croqui_da_flexao(padrao)
    retangular = croqui_da_flexao({**padrao, **RETANGULO})
    circular = croqui_da_flexao({**padrao, "tipo_secao": ev.CIRCULAR, "d_mm": 80.0})
    assert perfil != retangular != circular
    assert " A " in circular  # arco do círculo


def test_croqui_acompanha_o_sinal_do_momento():
    padrao = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    assert croqui_da_flexao({**padrao, "m_kNm": 30.0}) != croqui_da_flexao(
        {**padrao, "m_kNm": -30.0}
    )


def test_croqui_com_dado_que_nao_fecha_nao_quebra_a_pagina():
    padrao = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    tubo = {**padrao, "tipo_secao": ev.TUBO_CIRCULAR, "d_mm": 10.0, "t_mm": 8.0}
    assert "<rect" in croqui_da_flexao(tubo)


def test_tela_entrega_o_desenho_dos_valores():
    caso = cat.CASOS[FLEXAO]
    padrao = {c.chave: c.padrao for c in ev.CAMPOS_FLEXAO}
    assert ui._croqui(caso, {**padrao, **RETANGULO}) != ui._croqui(caso, padrao)


# ---------------------------------------------------------------------------
# Casos irmãos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "caso_id",
    [
        "Viga de seção retangular",
        "Seção I sob força axial, flexão e cortante",
        "Perfil U sob força axial, flexão e cortante",
        "Perfil tubular retangular (caixão)",
    ],
)
def test_casos_de_secao_ganham_o_mesmo_desenho(caso_id):
    r = calcular_caso(cat.CASOS[caso_id], {})
    assert r.figuras
    assert Image.open(io.BytesIO(r.figuras[0].png)).width / 2 <= 640


def test_tau_da_figura_bate_com_o_ponto_do_caso_no_perfil_i():
    """Dois caminhos para o τ no centro: a fórmula do caso e a integração por faixas."""
    r = calcular_caso(
        cat.CASOS["Seção I sob força axial, flexão e cortante"],
        {"h_mm": 200.0, "b_mm": 100.0, "tf_mm": 10.0, "tw_mm": 6.0, "cortante_kN": 50.0},
    )
    centro = next(p for p in r.pontos if p.nome == "Centroide")
    f = gs.faixas_da_secao(gs.perfil_i(200.0, 100.0, 10.0, 6.0))
    assert f.tau(50000.0).max() == pytest.approx(abs(centro.tau_xy), rel=1e-3)
