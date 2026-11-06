"""Pinos e parafusos ao corte, conferidos à mão, por fórmula fechada ou por equilíbrio."""

from __future__ import annotations

import io
import math

import pytest
from PIL import Image

from components import assistente_cargas_ui as ui
from components.elementos_croquis import croqui_do_pino
from core import elementos_catalogo as cat
from core import elementos_pinos as pn
from core import esforcos_no_pino as ep
from core.bolt_design import ROSCAS_METRICAS
from core.elementos_base import Resultado, calcular_caso

CISALHAMENTO = "Pinos ou parafusos sob cisalhamento"


def rodar(caso_id: str = CISALHAMENTO, **valores) -> Resultado:
    return calcular_caso(cat.CASOS[caso_id], valores)


def metrica(resultado: Resultado, rotulo: str) -> float:
    return next(float(m.valor) for m in resultado.metricas if m.rotulo == rotulo)


def linha(resultado: Resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


def tabela(resultado: Resultado, titulo: str):
    return next(t for t in resultado.tabelas if t.titulo == titulo)


# ---------------------------------------------------------------------------
# O pino como viga
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("planos", [1, 2, 3, 4, 5, 8])
def test_cada_plano_leva_a_mesma_forca(planos):
    chapas = ep.chapas_alternadas(planos, 12000.0, 8.0, 12.0, 1.0)
    assert len(chapas) == planos + 1
    assert sum(c.forca for c in chapas) == pytest.approx(0.0, abs=1e-6)
    acumulado = 0.0
    for chapa in chapas[:-1]:
        acumulado += chapa.forca
        assert abs(acumulado) == pytest.approx(12000.0 / planos)


@pytest.mark.parametrize("planos", [2, 3, 4, 5])
def test_chapa_de_dentro_leva_o_dobro_da_ponta(planos):
    chapas = ep.chapas_alternadas(planos, 12000.0, 8.0, 12.0, 0.0)
    v = 12000.0 / planos
    assert abs(chapas[0].forca) == pytest.approx(v)
    assert abs(chapas[-1].forca) == pytest.approx(v)
    assert all(abs(c.forca) == pytest.approx(2 * v) for c in chapas[1:-1])


def test_as_chapas_de_um_lado_somam_a_forca_toda():
    chapas = ep.chapas_alternadas(4, 12000.0, 8.0, 12.0, 0.0)
    assert sum(c.forca for c in chapas if c.forca > 0) == pytest.approx(12000.0)


@pytest.mark.parametrize(("a", "b", "c"), [(20.0, 40.0, 2.0), (8.0, 12.0, 1.0), (10.0, 10.0, 0.0)])
def test_dois_planos_dao_a_formula_da_en_1993(a, b, c):
    forca = 100000.0
    diagrama = ep.diagrama_das_chapas(ep.chapas_alternadas(2, forca, a, b, c))
    assert diagrama.momento_max == pytest.approx(forca / 8.0 * (b + 4.0 * c + 2.0 * a))


def test_corte_simples_divide_o_binario_entre_as_pontas():
    diagrama = ep.diagrama_das_chapas(ep.chapas_alternadas(1, 8000.0, 10.0, 0.0, 0.0))
    assert diagrama.momento_max == pytest.approx(8000.0 * (10.0 + 10.0) / 4.0)
    # no plano de corte o momento é zero, e os picos ficam na cabeça e na porca
    meio = len(diagrama.x) // 2
    assert diagrama.momento[0] == pytest.approx(-diagrama.momento[-1])
    assert diagrama.x[meio] == pytest.approx(10.0)
    assert diagrama.momento[meio] == pytest.approx(0.0, abs=1e-6)


def test_corte_simples_acompanha_a_espessura_da_chapa():
    diagrama = ep.diagrama_das_chapas(ep.chapas_alternadas(1, 6000.0, 12.0, 0.0, 0.0))
    assert diagrama.momento_max == pytest.approx(6000.0 * 24.0 / 4.0)


@pytest.mark.parametrize("planos", [1, 2, 3, 4, 6])
def test_momento_e_a_integral_do_cortante(planos):
    """Segundo caminho: integra V no trapézio e compara com o momento fechado por parábola."""
    d = ep.diagrama_das_chapas(ep.chapas_alternadas(planos, 9000.0, 8.0, 12.0, 1.5))
    integral = d.momento[0]
    for k in range(1, len(d.x)):
        integral += (d.cortante[k] + d.cortante[k - 1]) / 2.0 * (d.x[k] - d.x[k - 1])
        assert integral == pytest.approx(d.momento[k], rel=2e-2, abs=50.0)


def test_cortante_fecha_em_zero_no_fim_do_pino():
    d = ep.diagrama_das_chapas(ep.chapas_alternadas(3, 9000.0, 8.0, 12.0, 1.0))
    assert d.cortante[0] == 0.0
    assert d.cortante[-1] == pytest.approx(0.0, abs=1e-6)
    assert d.cortante_max == pytest.approx(3000.0)


def test_forcas_desequilibradas_sao_recusadas():
    with pytest.raises(ValueError, match="equilibrar"):
        ep.diagrama_das_chapas((ep.Chapa(0.0, 5.0, 100.0), ep.Chapa(5.0, 5.0, -50.0)))


def test_planos_ficam_no_meio_da_folga():
    chapas = ep.chapas_alternadas(2, 1000.0, 8.0, 12.0, 2.0)
    assert ep.planos_de_corte(chapas) == pytest.approx((9.0, 23.0))


# ---------------------------------------------------------------------------
# Caso de n planos
# ---------------------------------------------------------------------------


def test_area_cai_quando_o_corte_pega_a_rosca():
    fuste = rodar(elemento=pn.PARAFUSO_FUSTE, rosca="M16")
    rosca = rodar(elemento=pn.PARAFUSO_ROSCA, rosca="M16")
    area_fuste = math.pi * 16.0**2 / 4.0
    assert metrica(rosca, "τ médio") / metrica(fuste, "τ médio") == pytest.approx(
        area_fuste / ROSCAS_METRICAS["M16"].area_tracao_mm2
    )


def test_corte_duplo_a_mao():
    r = rodar(forca_kN=20.0, pinos=1, planos=2, d_mm=16.0, a_mm=8.0, b_mm=12.0, c_mm=1.0)
    area = math.pi * 16.0**2 / 4.0
    assert metrica(r, "Força por plano V") == pytest.approx(10.0)
    assert metrica(r, "τ médio") == pytest.approx(10000.0 / area, rel=1e-3)
    assert metrica(r, "τ máximo") == pytest.approx(4.0 / 3.0 * 10000.0 / area, rel=1e-3)
    assert metrica(r, "Momento no pino") == pytest.approx(20.0 / 8.0 * (12 + 4 + 16), rel=1e-6)
    assert metrica(r, "Esmagamento na ponta") == pytest.approx(10000.0 / (16 * 8), rel=1e-3)
    assert metrica(r, "Esmagamento dentro") == pytest.approx(20000.0 / (16 * 12), rel=1e-3)


def test_mais_pinos_dividem_a_forca():
    um = rodar(forca_kN=20.0, pinos=1)
    quatro = rodar(forca_kN=20.0, pinos=4)
    assert metrica(quatro, "τ médio") == pytest.approx(metrica(um, "τ médio") / 4, rel=1e-3)


def test_tubo_fino_dobra_o_tau_medio():
    """Na parede fina, τ_máx → 2·V/A; a fórmula do tubo tem de chegar lá."""
    s = pn.secao_do_pino({"elemento": pn.PINO_VAZADO, "d_mm": 20.0, "d_i_mm": 19.99})
    assert s.fator_tau == pytest.approx(2.0, rel=1e-3)


def test_pino_vazado_guarda_a_flexao_melhor_que_a_area():
    macico = pn.secao_do_pino({"elemento": pn.PINO_MACICO, "d_mm": 20.0, "d_i_mm": 0.0})
    vazado = pn.secao_do_pino({"elemento": pn.PINO_VAZADO, "d_mm": 20.0, "d_i_mm": 10.0})
    assert vazado.area / macico.area == pytest.approx(0.75)
    assert vazado.modulo / macico.modulo == pytest.approx(1.0 - 0.5**4)


def test_rasgamento_e_secao_liquida_a_mao():
    r = rodar(
        forca_kN=20.0, planos=1, d_mm=16.0, a_mm=8.0, c_mm=0.0, w_mm=60.0, e_mm=30.0,
    )  # fmt: skip
    assert linha(r, "Rasgamento até a borda").solicitante == pytest.approx(
        20000.0 / (2 * 8 * (30 - 8))
    )
    assert linha(r, "Seção líquida da chapa").solicitante == pytest.approx(
        20000.0 / ((60 - 16) * 8)
    )


def test_quem_manda_muda_com_a_folga():
    """Com folga grande, a flexão passa o corte: é por isso que a tensão média sozinha engana."""
    justa = rodar(c_mm=0.0, forca_kN=30.0, planos=2)
    folgada = rodar(c_mm=30.0, forca_kN=30.0, planos=2)
    assert linha(justa, "Flexão no pino").status == "OK"
    assert linha(folgada, "Flexão no pino").status == "NÃO OK"
    assert linha(folgada, "Cisalhamento no pino").status == "OK"


def test_capacidade_leva_o_criterio_que_governa_a_100_por_cento():
    r = rodar()
    capacidade = metrica(r, "Força que a ligação aguenta")
    no_limite = rodar(forca_kN=capacidade)
    maior = max(v.aproveitamento for v in no_limite.verificacoes if v.aproveitamento is not None)
    assert maior == pytest.approx(1.0, rel=1e-2)


def test_tabela_de_chapas_tem_uma_linha_por_chapa():
    r = rodar(planos=3)
    linhas = tabela(r, "Força em cada chapa").linhas
    assert len(linhas) == 4
    assert [lin["Força por pino (kN)"] for lin in linhas] == pytest.approx(
        [6.67, 13.33, 13.33, 6.67]
    )


def test_estudo_compara_os_planos_e_marca_o_atual():
    r = rodar(planos=2)
    linhas = tabela(r, "Com outro número de planos").linhas
    assert [lin["Planos"] for lin in linhas] == [1, 2, 3, 4, 5, 6]
    assert [lin["Planos"] for lin in linhas if lin["Situação"]] == [2]
    cortes = [lin["V por plano (kN)"] for lin in linhas]
    assert cortes == sorted(cortes, reverse=True)


def test_estudo_inclui_o_numero_de_planos_escolhido():
    linhas = tabela(rodar(planos=8), "Com outro número de planos").linhas
    assert linhas[-1]["Planos"] == 8


def test_planos_impares_em_pino_sem_cabeca_avisam():
    assert any("binário" in a for a in rodar(planos=3).alertas)
    assert not any("binário" in a for a in rodar(planos=2).alertas)
    assert not any("binário" in a for a in rodar(planos=1, elemento=pn.PARAFUSO_FUSTE).alertas)


def test_tres_planos_avisam_que_a_divisao_depende_do_ajuste():
    assert any("divisão igual" in a for a in rodar(planos=3).alertas)
    assert not any("divisão igual" in a for a in rodar(planos=2).alertas)


def test_parafuso_aponta_para_a_pagina_da_norma():
    assert any("Projeto de parafusos" in a for a in rodar(elemento=pn.PARAFUSO_FUSTE).alertas)


@pytest.mark.parametrize(
    ("valores", "mensagem"),
    [
        ({"w_mm": 10.0}, "largura"),
        ({"e_mm": 5.0}, "dentro da chapa"),
        ({"elemento": pn.PINO_VAZADO, "d_i_mm": 20.0}, "furo do pino"),
    ],
)
def test_geometria_impossivel_e_recusada(valores, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        rodar(**valores)


# ---------------------------------------------------------------------------
# Desenho que muda com o caso
# ---------------------------------------------------------------------------


def _png(resultado: Resultado) -> bytes:
    return resultado.figuras[0].png


@pytest.mark.parametrize("planos", range(1, 9))
def test_figura_sai_para_todo_numero_de_planos(planos):
    imagem = Image.open(io.BytesIO(_png(rodar(planos=planos))))
    assert imagem.format == "PNG" and imagem.width > 400


def test_figura_muda_com_os_planos_e_com_o_elemento():
    figuras = {
        _png(rodar(planos=1)),
        _png(rodar(planos=2)),
        _png(rodar(planos=3)),
        _png(rodar(planos=2, elemento=pn.PINO_VAZADO)),
        _png(rodar(planos=2, elemento=pn.PARAFUSO_FUSTE)),
        _png(rodar(planos=2, elemento=pn.PARAFUSO_ROSCA)),
    }
    assert len(figuras) == 6


@pytest.mark.parametrize("planos", [1, 2, 4, 8])
def test_croqui_desenha_uma_chapa_para_cada_plano_a_mais(planos):
    svg = croqui_do_pino({"planos": planos, "elemento": pn.PINO_MACICO})
    assert svg.count("<rect") == planos + 2  # as chapas e o pino
    assert svg.count("stroke-dasharray") == planos


def test_croqui_do_parafuso_tem_cabeca_e_porca():
    pino = croqui_do_pino({"planos": 2, "elemento": pn.PINO_MACICO})
    parafuso = croqui_do_pino({"planos": 2, "elemento": pn.PARAFUSO_FUSTE})
    assert parafuso.count("<rect") == pino.count("<rect") + 2


def test_corte_simples_nao_desenha_chapa_de_dentro():
    assert ">b<" not in croqui_do_pino({"planos": 1})
    assert ">b<" in croqui_do_pino({"planos": 2})


def test_tela_entrega_o_desenho_dos_valores():
    caso = cat.CASOS[CISALHAMENTO]
    assert ui._croqui(caso, {"planos": 4}) != ui._croqui(caso, {"planos": 1})


# ---------------------------------------------------------------------------
# Pino de articulação
# ---------------------------------------------------------------------------


def test_articulacao_ganha_figura_com_o_mesmo_momento_do_calculo():
    r = calcular_caso(cat.CASOS["pino_articulacao"], {})
    assert r.figuras
    forca = 100000.0 * 1.25
    chapas = ep.chapas_alternadas(2, forca, 20.0, 40.0, 2.0)
    assert ep.diagrama_das_chapas(chapas).momento_max / 1000.0 == pytest.approx(
        metrica(r, "Momento no pino")
    )


# ---------------------------------------------------------------------------
# Pino em balanço
# ---------------------------------------------------------------------------


def test_balanco_a_pressao_equilibra_a_forca_e_o_momento():
    """Integra a pressão linear: a resultante é F e o momento fecha em zero no fundo do furo."""
    p = ep.PinoEmBalanco(5000.0, 15.0, 40.0, 25.0)
    d = p.diagrama()
    assert d.cortante[-1] == pytest.approx(0.0, abs=1e-6)
    assert d.momento[-1] == pytest.approx(0.0, abs=1e-6)


def test_balanco_pressao_na_boca_a_mao():
    p = ep.PinoEmBalanco(5000.0, 15.0, 40.0, 25.0)
    assert p.pressao_max == pytest.approx(5000.0 / (25 * 40) * (4 + 6 * 15 / 40))


def test_balanco_sem_braco_cai_na_pressao_de_quatro_vezes_a_media():
    p = ep.PinoEmBalanco(5000.0, 0.0, 40.0, 25.0)
    assert p.pressao_max == pytest.approx(4 * 5000.0 / (25 * 40))
    assert p.pressao_no_fundo == pytest.approx(2 * 5000.0 / (25 * 40))


def test_balanco_maior_momento_fica_dentro_do_furo():
    p = ep.PinoEmBalanco(5000.0, 15.0, 40.0, 25.0)
    assert p.profundidade_do_momento_max > 0
    assert p.momento_max > 5000.0 * 15.0
    d = p.diagrama()
    assert d.momento_max == pytest.approx(p.momento_max)


@pytest.mark.parametrize(("braco", "pressao"), [(15.0, 166.0), (40.0, 90.0), (0.0, 200.0)])
def test_engaste_minimo_leva_a_pressao_exatamente_ao_limite(braco, pressao):
    forca, d = 5000.0, 25.0
    engaste = ep.engaste_minimo(forca, braco, d, pressao)
    assert ep.PinoEmBalanco(forca, braco, engaste, d).pressao_max == pytest.approx(pressao)


def test_balanco_engaste_curto_reprova_na_pressao():
    curto = rodar("pino_balanco", forca_kN=20.0, engaste_mm=10.0)
    assert linha(curto, "Pressão na boca do furo").status == "NÃO OK"
    longo = rodar("pino_balanco", forca_kN=20.0, engaste_mm=60.0)
    assert linha(longo, "Pressão na boca do furo").status == "OK"


def test_balanco_chapa_nao_entra_no_furo():
    with pytest.raises(ValueError, match="não pode entrar no furo"):
        rodar("pino_balanco", braco_mm=3.0, t_chapa_mm=12.0)


# ---------------------------------------------------------------------------
# Pino transversal
# ---------------------------------------------------------------------------


def test_transversal_corte_a_mao():
    r = rodar("pino_transversal", torque_Nm=200.0, d_eixo_mm=40.0, d_cubo_mm=70.0, d_mm=10.0)
    assert metrica(r, "Força em cada plano") == pytest.approx(200000.0 / 40.0 / 1000.0)
    assert metrica(r, "τ máximo no pino") == pytest.approx(
        4 / 3 * 4 * 200000.0 / (math.pi * 100 * 40), rel=1e-3
    )


def test_transversal_pressao_no_eixo_devolve_o_torque():
    """Integra a pressão triangular dos dois lados do pino: o torque tem de voltar."""
    torque, d, eixo = 200000.0, 10.0, 40.0
    r = rodar("pino_transversal", torque_Nm=200.0, d_eixo_mm=eixo, d_mm=d)
    pico = metrica(r, "Pressão no eixo")
    assert pico == pytest.approx(6.0 * torque / (d * eixo**2), rel=1e-3)
    passos = 2000
    dr = (eixo / 2.0) / passos
    soma = 0.0
    for i in range(passos):
        raio = (i + 0.5) * dr
        soma += 2.0 * pico * (raio / (eixo / 2.0)) * d * dr * raio
    assert soma == pytest.approx(torque, rel=1e-3)


def test_transversal_pressao_no_cubo_devolve_o_torque():
    torque, d, eixo, cubo = 200000.0, 10.0, 40.0, 70.0
    r = rodar("pino_transversal", torque_Nm=200.0, d_eixo_mm=eixo, d_cubo_mm=cubo, d_mm=d)
    pressao = metrica(r, "Pressão no cubo")
    # Dois lados, parede (D_c − D)/2, com braço no raio médio (D_c + D)/4.
    forca_em_cada_lado = pressao * d * (cubo - eixo) / 2.0
    assert 2.0 * forca_em_cada_lado * (cubo + eixo) / 4.0 == pytest.approx(torque, rel=1e-3)


def test_transversal_furo_grande_pede_atencao():
    assert linha(rodar("pino_transversal", d_mm=16.0), "Pino em relação ao eixo").status == "ALERTA"
    assert linha(rodar("pino_transversal", d_mm=10.0), "Pino em relação ao eixo").status == "OK"


def test_transversal_concentracao_multiplica_a_torcao_no_eixo():
    sem = rodar("pino_transversal", kts=1.0)
    com = rodar("pino_transversal", kts=2.0)
    assert metrica(com, "τ no eixo com o furo") == pytest.approx(
        2 * metrica(sem, "τ no eixo com o furo"), rel=1e-3
    )


def test_transversal_medidas_impossiveis_sao_recusadas():
    with pytest.raises(ValueError, match="cubo"):
        rodar("pino_transversal", d_cubo_mm=30.0)
    with pytest.raises(ValueError, match="mais fino"):
        rodar("pino_transversal", d_mm=50.0)
