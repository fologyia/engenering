"""Tanques e linhas no tempo: nível, temperatura, partida da linha e água quente chegando."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest
from scipy import integrate
from streamlit.testing.v1 import AppTest

from components.tanques_e_linhas_help import AJUDA
from core import calor_no_tempo as ct
from core import figuras_no_tempo as fnt
from core import fluidos_cenas as fc
from core import linha_no_tempo as ln
from core import tanque_no_tempo as tq
from core.montador_funcoes import fator_de_atrito
from core.technical_records import avaliar_contrato_registro
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/tanques_e_linhas.py"


# ---------------------------------------------------------------------------------------------
# Nível
# ---------------------------------------------------------------------------------------------
def test_orificio_bate_com_torricelli():
    t = tq.Tanque(
        tq.VERTICAL,
        altura_m=3.0,
        diametro_m=2.0,
        nivel_inicial_m=2.5,
        saida=tq.Saida(tq.ORIFICIO, diametro_mm=50),
    )
    r = tq.calcular_nivel(t)
    assert r.evento == "vazio"
    assert r.duracao == pytest.approx(tq.tempo_de_torricelli(t, 2.5, tq.NIVEL_VAZIO), rel=1e-6)
    assert r.tempo_para(1.0) == pytest.approx(tq.tempo_de_torricelli(t, 2.5, 1.0), rel=1e-5)


def test_entrada_com_orificio_estabiliza_no_equilibrio():
    t = tq.Tanque(
        tq.VERTICAL,
        altura_m=3.0,
        diametro_m=2.0,
        nivel_inicial_m=0.5,
        entrada_L_s=5.0,
        saida=tq.Saida(tq.ORIFICIO, diametro_mm=50),
    )
    r = tq.calcular_nivel(t)
    exato = (0.005 / (0.61 * math.pi * 0.025**2)) ** 2 / (2 * 9.81)
    assert r.evento == "estavel"
    assert r.nivel_de_equilibrio == pytest.approx(exato, rel=1e-8)
    assert abs(r.niveis[-1] - exato) <= 0.005 * abs(0.5 - exato) + 1e-9


def test_sem_saida_enche_no_tempo_do_volume():
    t = tq.Tanque(
        tq.RETANGULAR,
        altura_m=2.0,
        comprimento_m=3,
        largura_m=2,
        nivel_inicial_m=0.2,
        entrada_L_s=10,
        saida=tq.Saida(tq.SEM_SAIDA),
    )
    r = tq.calcular_nivel(t)
    assert r.evento == "cheio"
    assert r.duracao == pytest.approx((2.0 - 0.2) * 6.0 / 0.010, rel=1e-6)
    assert any("transborda" in a for a in r.avisos)


def test_volume_do_tanque_horizontal():
    t = tq.Tanque(tq.HORIZONTAL, altura_m=0.0, diametro_m=2.0, comprimento_m=5.0)
    assert t.volume(2.0) == pytest.approx(math.pi * 5.0)
    assert t.volume(1.0) == pytest.approx(math.pi * 5.0 / 2)
    assert t.nivel(t.volume(0.37)) == pytest.approx(0.37)


def test_saida_por_tubo_bate_com_a_conta_direta():
    saida = tq.Saida(tq.TUBO, diametro_mm=50, comprimento_m=5)
    t = tq.Tanque(tq.VERTICAL, altura_m=3.0, diametro_m=2.0, nivel_inicial_m=2.5, saida=saida)
    r = tq.calcular_nivel(t)
    area = math.pi

    def vazio(_, v):
        return v[0] / area - tq.NIVEL_VAZIO

    vazio.terminal = True
    direto = integrate.solve_ivp(
        lambda _, v: [-tq.vazao_de_saida(t, v[0] / area)],
        (0, 5000),
        [2.5 * area],
        events=vazio,
        rtol=1e-10,
        atol=1e-12,
    )
    assert r.duracao == pytest.approx(float(direto.t_events[0][0]), rel=1e-4)
    # a energia na saída: carga = (1 + f·L/D + ΣK)·v²/2g
    v = float(ln_v := tq.velocidade_no_tubo(2.0, saida))
    re = saida.massa_especifica * v * 0.05 / saida.viscosidade
    f = float(fator_de_atrito(re, saida.rugosidade_mm / saida.diametro_mm))
    assert (1 + saida.k_local + f * 5 / 0.05) * ln_v**2 / (2 * 9.81) == pytest.approx(2.0, rel=1e-9)


def test_tanque_sem_entrada_nem_saida_e_recusado():
    t = tq.Tanque(
        tq.VERTICAL, altura_m=3.0, diametro_m=2.0, nivel_inicial_m=1.0, saida=tq.Saida(tq.SEM_SAIDA)
    )
    assert any("não muda" in e for e in tq.problemas_do_nivel(t))
    assert any(
        "entre 0 e" in e
        for e in tq.problemas_do_nivel(tq.Tanque(tq.VERTICAL, 3.0, 2.0, nivel_inicial_m=4.0))
    )


# ---------------------------------------------------------------------------------------------
# Temperatura
# ---------------------------------------------------------------------------------------------
def _agua(**opcoes) -> tq.TanqueTermico:
    rho, cp = tq.propriedades_da_agua(20.0)
    return tq.TanqueTermico(2.0, rho, cp, 20.0, **opcoes)


def test_temperatura_segue_a_exponencial_exata():
    t = _agua(
        aquecimento=tq.SERPENTINA, ua_serpentina=800, t_serpentina=90, ua_perda=30, vazao_kg_s=0.05
    )
    r = tq.calcular_termico(t)
    mc = t.massa * t.calor_especifico
    b = 800 + 30 + 0.05 * t.calor_especifico
    equilibrio = (800 * 90 + 30 * 20 + 0.05 * t.calor_especifico * 20) / b
    assert r.t_equilibrio == pytest.approx(equilibrio)
    assert r.tau == pytest.approx(mc / b)
    assert r.temperaturas[-1] == pytest.approx(equilibrio + (20 - equilibrio) / 250.0)
    assert r.tempo_para_estabilizar == pytest.approx(math.log(100.0) * mc / b)
    alvo = 0.5 * (20 + equilibrio)
    assert r.tempo_para(alvo) == pytest.approx(mc / b * math.log(2.0))
    # energia: o que entra menos o que sai é o que esquenta o líquido, m·c·dT/dt
    derivada = np.gradient(r.temperaturas, r.tempos)
    sobra = r.calor_aquecimento - r.calor_perda - r.calor_vazao
    assert sobra[1:-1] == pytest.approx(mc * derivada[1:-1] / 1000.0, rel=1e-3)


def test_termostato_segura_a_temperatura():
    t = _agua(aquecimento=tq.POTENCIA, potencia_kW=30, ua_perda=30, termostato=60.0)
    r = tq.calcular_termico(t)
    assert r.tempo_do_termostato == pytest.approx(
        tq.tempo_para_temperatura(_agua(aquecimento=tq.POTENCIA, potencia_kW=30, ua_perda=30), 60.0)
    )
    assert r.temperaturas[-1] == 60.0
    assert r.calor_aquecimento[-1] == pytest.approx(30 * 40 / 1000)
    assert r.tempo_para(70.0) is None and r.tempo_para(50.0) < r.tempo_do_termostato
    assert not r.avisos


def test_agua_que_ferve_para_a_conta():
    r = tq.calcular_termico(_agua(aquecimento=tq.POTENCIA, potencia_kW=30, ua_perda=30))
    assert any("ferve" in a for a in r.avisos)
    assert r.temperaturas[-1] == pytest.approx(100.0)


# ---------------------------------------------------------------------------------------------
# Partida da linha
# ---------------------------------------------------------------------------------------------
LINHA = ln.Linha(500.0, 102.3, 0.045, 2.0, 20.0, tempo_manobra_s=10.0)


def test_vazao_de_regime_fecha_a_energia():
    q = ln.vazao_permanente(LINHA)
    area = LINHA.area
    v = q / area
    re = LINHA.massa_especifica * v * 0.1023 / LINHA.viscosidade
    f = float(fator_de_atrito(re, 0.045 / 102.3))
    perda = (1 + f * 500 / 0.1023 + 2.0 + 0.17) * v * v / (2 * 9.81)
    assert perda == pytest.approx(20.0, rel=1e-9)
    r = ln.calcular_partida(LINHA)
    assert r.vazao_final == pytest.approx(q * 1000)
    assert r.vazoes[-1] == pytest.approx(r.vazao_final, rel=2e-3)
    assert r.tempo_para(0.95) < r.tempo_para(0.99) < r.duracao


def test_abertura_instantanea_com_f_constante_e_a_tangente_hiperbolica(monkeypatch):
    monkeypatch.setattr(ln, "fator_de_atrito", lambda re, rel: 0.02)
    linha = ln.Linha(500.0, 102.3, 0.045, 2.0, 20.0, tempo_manobra_s=0.0)
    r = ln.calcular_partida(linha)
    qf = r.vazao_final / 1000
    escala = 9.81 * linha.area * 20.0 / (500.0 * qf)
    for i in (50, 200, 400):
        assert r.vazoes[i] / 1000 == pytest.approx(qf * math.tanh(escala * r.tempos[i]), rel=1e-5)
    assert any("ida e volta da onda" in a for a in r.avisos)


def test_partida_da_bomba_chega_no_encontro_das_curvas():
    linha = ln.Linha(
        200.0,
        77.9,
        0.045,
        3.0,
        -15.0,
        evento=ln.BOMBA,
        tempo_manobra_s=3.0,
        bomba_h0_m=40.0,
        bomba_qmax_L_s=20.0,
    )
    r = ln.calcular_partida(linha)
    q = r.vazao_final / 1000
    assert ln.altura_da_bomba(linha, q, 1.0) - 15.0 == pytest.approx(
        ln._coeficiente_de_perda(linha, q, 1.0) * q * q / (2 * 9.81 * linha.area**2), rel=1e-8
    )
    assert r.manobra[0] == 0.0 and r.manobra[-1] == 100.0


def test_linha_que_nao_escoa_e_recusada():
    linha = ln.Linha(100.0, 50.0, 0.045, 0.0, -5.0)
    assert any("não escoa" in e for e in ln.problemas_da_partida(linha))


# ---------------------------------------------------------------------------------------------
# Água quente chegando
# ---------------------------------------------------------------------------------------------
ACO = ct.MATERIAIS["Aço carbono comum"]


def test_regime_permanente_do_tubo_bate_com_as_resistencias_em_serie():
    tubo = ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 0.0, 0.04, 10.0, 20.0, 0.1, 20.0, 60.0)
    r = ln.calcular_tubo(tubo, 1800.0)
    assert r.saida[-1] == pytest.approx(r.saida_permanente, abs=0.05)
    assert fc.perfil_permanente(r)[-1] == pytest.approx(r.saida_permanente, abs=0.05)
    assert r.tempo_para(55.0) > 30.0 / r.velocidade  # a parede fria atrasa a água quente
    assert r.volume_ate(55.0) == pytest.approx(r.tempo_para(55.0) * 0.1)


def test_sem_parede_nem_perda_a_frente_chega_no_tempo_de_transito():
    tubo = ln.TuboAquecendo(30.0, 26.6, 0.01, ACO, 0.0, 0.04, 1e-6, 20.0, 0.1, 20.0, 60.0)
    r = ln.calcular_tubo(tubo)
    assert r.tempo_para(40.0) == pytest.approx(30.0 / r.velocidade, rel=0.01)
    assert r.saida_permanente == pytest.approx(60.0, abs=1e-3)


def test_gnielinski_bate_com_a_biblioteca_ht():
    ht = pytest.importorskip("ht")
    tubo = ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 0.0, 0.04, 10.0, 20.0, 0.2, 20.0, 60.0)
    h, re, nome = ln.coeficiente_interno(tubo)
    rho, mu, cp, k = ln.propriedades_da_agua(40.0)
    pr = mu * cp / k
    fd = (0.790 * math.log(re) - 1.64) ** -2
    nu = ht.conv_internal.turbulent_Gnielinski(Re=re, Pr=pr, fd=fd)
    assert "Gnielinski" in nome
    assert h == pytest.approx(nu * k / 0.0266, rel=1e-9)


def test_isolamento_reduz_a_perda():
    sem = ln.calcular_tubo(
        ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 0.0, 0.04, 10.0, 20.0, 0.1, 20.0, 60.0)
    )
    com = ln.calcular_tubo(
        ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 25.0, 0.04, 10.0, 20.0, 0.1, 20.0, 60.0)
    )
    assert com.perda_permanente_W < 0.5 * sem.perda_permanente_W
    assert com.saida_permanente > sem.saida_permanente


# ---------------------------------------------------------------------------------------------
# Cenas e registros
# ---------------------------------------------------------------------------------------------
def test_cenas_e_registros_saem_validos():
    nivel = tq.calcular_nivel(
        tq.Tanque(
            tq.VERTICAL,
            altura_m=3.0,
            diametro_m=2.0,
            nivel_inicial_m=2.5,
            saida=tq.Saida(tq.ORIFICIO, diametro_mm=50),
        )
    )
    termico = tq.calcular_termico(
        _agua(aquecimento=tq.POTENCIA, potencia_kW=30, ua_perda=30, termostato=60.0)
    )
    partida = ln.calcular_partida(LINHA)
    tubo = ln.calcular_tubo(
        ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 0.0, 0.04, 10.0, 20.0, 0.1, 20.0, 60.0)
    )
    cenas = [
        fc.cena_do_nivel(nivel, 1.0),
        fc.cena_termica(termico, 50.0),
        fc.cena_da_partida(partida),
        fc.cena_do_tubo(tubo, 55.0),
    ]
    for cena in cenas:
        assert cena["n_canais"] > 0 and cena["graficos"] and cena["formas"]
    registros = [
        fc.registro_do_nivel(nivel, 1.0),
        fc.registro_termico(termico, 50.0),
        fc.registro_da_partida(partida),
        fc.registro_do_tubo(tubo, 55.0, 60.0),
    ]
    for registro in registros:
        assert avaliar_contrato_registro(registro)["valido"], registro["titulo"]
        assert fnt.figuras_do_registro(registro["resultados"])
    assert registros[3]["status"] == "Não atende"  # 55 °C chega depois de 1 min
    assert "termostato" in registros[1]["resumo"]


# ---------------------------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------------------------
def test_toda_ajuda_e_usada_e_termina_com_ponto():
    usadas = set(
        re.findall(r'AJUDA\["([A-Za-z_0-9]+)"\]', (RAIZ / PAGINA).read_text(encoding="utf-8"))
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and texto[-1] in ".!:", chave


def test_pagina_calcula_as_quatro_abas():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rotulos = [m.label for m in at.metric]
    for esperado in ("Esvazia em", "Estabiliza em", "Vazão de regime", "Saída estabiliza em"):
        assert esperado in rotulos
    assert not at.error
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    }
    sem_ajuda -= {("text_input", "Nome do novo projeto"), ("text_input", "Identificação da peça")}
    assert not sem_ajuda, sorted(sem_ajuda)
    for chave, valor in (
        ("tqn_saida", "Tubo saindo do fundo"),
        ("tqn_forma", "Retangular"),
        ("tqt_aq", "Serpentina ou camisa"),
        ("lnp_evento", "Ligar a bomba"),
    ):
        at.selectbox(key=chave).set_value(valor).run()
        assert not at.exception, chave
    at.number_input(key="lnt_alvo").set_value(55.0).run()
    assert not at.exception
    assert any(m.label == "Água que sai antes" for m in at.metric)
    assert np.isfinite(1.0)


# ---------------------------------------------------------------------------------------------
# Vasos comunicantes
# ---------------------------------------------------------------------------------------------
LIGACAO = tq.Saida(tq.TUBO, diametro_mm=50, comprimento_m=10, k_local=1.5)


def test_vasos_comunicantes_equalizam_guardando_o_volume():
    t1 = tq.Tanque(tq.VERTICAL, 3.0, 2.0, nivel_inicial_m=2.5)
    t2 = tq.Tanque(tq.VERTICAL, 3.0, 1.5, nivel_inicial_m=0.3)
    r = tq.calcular_vasos(tq.Vasos(t1, t2, 0.5, LIGACAO))
    assert r.evento == "equalizou"
    a1, a2 = math.pi * 1.0**2, math.pi * 0.75**2
    z = (a1 * 2.5 + a2 * (0.5 + 0.3)) / (a1 + a2)  # mesma cota, mesmo volume
    assert r.superficie_de_equilibrio == pytest.approx(z, rel=1e-9)
    assert abs(r.diferenca[-1]) == pytest.approx(tq.NIVEL_VAZIO, abs=1e-6)
    assert a1 * r.niveis_1[-1] + a2 * r.niveis_2[-1] == pytest.approx(a1 * 2.5 + a2 * 0.3, rel=1e-9)
    # a vazão do começo fecha a energia do tubo de ligação
    v = r.vazao[0] / 1000 / (math.pi * 0.025**2)
    assert v == pytest.approx(float(tq.velocidade_no_tubo(2.5 - 0.8, LIGACAO)), rel=1e-6)


def test_vasos_com_o_tanque_2_baixo_transborda_e_avisa():
    t1 = tq.Tanque(tq.VERTICAL, 3.0, 2.0, nivel_inicial_m=2.5)
    t2 = tq.Tanque(tq.VERTICAL, 2.0, 2.0, nivel_inicial_m=0.2)
    r = tq.calcular_vasos(tq.Vasos(t1, t2, -1.5, LIGACAO))
    assert r.evento == "cheio_2" and r.superficie_de_equilibrio is None
    assert any("transborda" in a for a in r.avisos)
    assert tq.problemas_dos_vasos(
        tq.Vasos(t1, tq.Tanque(tq.VERTICAL, 3.0, 1.0, nivel_inicial_m=2.5), 0.0, LIGACAO)
    )


def test_cena_e_registro_dos_vasos():
    t1 = tq.Tanque(tq.VERTICAL, 3.0, 2.0, nivel_inicial_m=2.5)
    t2 = tq.Tanque(tq.VERTICAL, 3.0, 1.5, nivel_inicial_m=0.3)
    r = tq.calcular_vasos(tq.Vasos(t1, t2, 0.0, LIGACAO))
    dados = fc.cena_dos_vasos(r)
    assert any(f["tipo"] == "linha" and f.get("setas") for f in dados["formas"])
    assert dados["graficos"][0]["marcos"][0]["nome"] == "equaliza"
    registro = fc.registro_dos_vasos(r)
    assert avaliar_contrato_registro(registro)["valido"]
    assert "ficam iguais" in registro["resumo"]
    assert fnt.figuras_do_registro(registro["resultados"])


def test_marcos_de_estabilizar_do_tanque_e_do_tubo():
    t = _agua(aquecimento=tq.POTENCIA, potencia_kW=30, ua_perda=30, termostato=60.0)
    r = tq.calcular_termico(t)
    assert r.tempo_para_estabilizar == r.tempo_do_termostato
    tubo = ln.calcular_tubo(
        ln.TuboAquecendo(30.0, 26.6, 2.9, ACO, 0.0, 0.04, 10.0, 20.0, 0.1, 20.0, 60.0)
    )
    t_est = tubo.tempo_para_estabilizar()
    assert t_est is not None and 30.0 / tubo.velocidade < t_est < tubo.duracao
    i = int(np.searchsorted(tubo.tempos_saida, t_est))
    assert (
        abs(tubo.saida[i] - tubo.saida_permanente)
        <= 0.01 * abs(tubo.saida_permanente - 20.0) + 1e-9
    )


def test_pagina_mostra_os_vasos_comunicantes():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    at.selectbox(key="tqn_saida").set_value("Tubo para outro tanque (vasos comunicantes)").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Equaliza em"].endswith("min")
    assert metricas["Nível igual (cota)"] == "1,708 m"
