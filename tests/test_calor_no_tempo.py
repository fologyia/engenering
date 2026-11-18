"""Calor no tempo: parede, cilindro, esfera (1D) e a seção desenhada (2D), cenas e página."""

from __future__ import annotations

import base64
import math
import re
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from components.calor_no_tempo_help import AJUDA
from core import calor_cenas as cc
from core import calor_na_secao as cs
from core import calor_no_tempo as ct
from core import figuras_no_tempo as fnt
from core import secao_desenhada as sd
from core.technical_records import avaliar_contrato_registro
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/calor_no_tempo.py"
ACO = ct.MATERIAIS["Aço AISI 1010"]
AR = ct.Face(ct.CONVECCAO, h=500.0, t_fluido=20.0)


# ---------------------------------------------------------------------------------------------
# Uma dimensão
# ---------------------------------------------------------------------------------------------
def test_raizes_batem_com_a_tabela_do_cengel():
    # Çengel, Tab. 4-2, Bi = 1: λ1 = 0,8603 (parede), 1,2558 (cilindro), 1,5708 (esfera)
    assert ct.raizes(ct.PAREDE, 1.0)[0] == pytest.approx(0.8603, abs=1e-4)
    assert ct.raizes(ct.CILINDRO, 1.0)[0] == pytest.approx(1.2558, abs=1e-4)
    assert ct.raizes(ct.ESFERA, 1.0)[0] == pytest.approx(1.5708, abs=1e-4)
    # Bi infinito: cos, J0 e sen
    assert ct.raizes(ct.PAREDE, math.inf)[0] == pytest.approx(math.pi / 2)
    assert ct.raizes(ct.CILINDRO, math.inf)[0] == pytest.approx(2.404826, abs=1e-6)
    assert ct.raizes(ct.ESFERA, math.inf)[0] == pytest.approx(math.pi)


@pytest.mark.parametrize(
    ("forma", "medidas"),
    [
        (ct.PAREDE, {"espessura_mm": 40.0}),
        (ct.CILINDRO, {"diametro_mm": 80.0}),
        (ct.ESFERA, {"diametro_mm": 80.0}),
    ],
)
def test_conta_bate_com_a_solucao_exata_em_serie(forma, medidas):
    peca = ct.Peca(forma, ACO, 300.0, AR, AR, **medidas)
    r = ct.calcular(peca)
    conferencias = ct.conferencias(r)
    assert len(conferencias) == 6
    for c in conferencias:
        assert c.diferenca == pytest.approx(0.0, abs=0.01), c
    # automático: um pouco além do instante em que a peça inteira fica a 1 % do regime
    assert r.automatica
    assert r.duracao == pytest.approx(math.log(250.0) * r.tau)
    m = ct.marcos(r)
    assert m.estabiliza is not None and m.estabiliza < r.duracao
    assert m.equaliza is not None and m.equaliza <= m.estabiliza
    queda = (r.temperaturas[-1] - 20.0) / (300.0 - 20.0)
    assert np.all(queda < 0.01)


def test_parede_com_uma_face_isolada_e_meia_parede_simetrica():
    isolada = ct.Peca(ct.PAREDE, ACO, 300.0, ct.Face(ct.ISOLADA), AR, espessura_mm=20.0)
    simetrica = ct.Peca(ct.PAREDE, ACO, 300.0, AR, AR, espessura_mm=40.0)
    a = ct.calcular(isolada, 120.0)
    b = ct.calcular(simetrica, 120.0)
    # a face isolada é o plano de simetria da parede com o dobro da espessura
    assert a.temperaturas[-1, 0] == pytest.approx(b.temperaturas[-1, len(b.r) // 2], abs=0.02)
    assert a.temperaturas[-1, -1] == pytest.approx(b.temperaturas[-1, -1], abs=0.02)
    assert all(abs(c.diferenca) < 0.01 for c in ct.conferencias(a))


def test_temperatura_fixa_nas_duas_faces():
    fixa = ct.Face(ct.TEMPERATURA, t_fixa=100.0)
    r = ct.calcular(ct.Peca(ct.PAREDE, ACO, 20.0, fixa, fixa, espessura_mm=50.0))
    assert r.temperaturas[-1, 0] == pytest.approx(100.0) and r.temperaturas[
        -1, -1
    ] == pytest.approx(100.0)
    assert all(abs(c.diferenca) < 0.02 for c in ct.conferencias(r))


def test_regime_permanente_de_duas_conveccoes_e_resistencias_em_serie():
    quente = ct.Face(ct.CONVECCAO, h=200.0, t_fluido=150.0)
    frio = ct.Face(ct.CONVECCAO, h=10.0, t_fluido=20.0)
    tijolo = ct.MATERIAIS["Tijolo comum"]
    r = ct.calcular(ct.Peca(ct.PAREDE, tijolo, 20.0, quente, frio, espessura_mm=200.0))
    q = (150.0 - 20.0) / (1 / 200.0 + 0.2 / tijolo.condutividade + 1 / 10.0)
    assert r.permanente[0] == pytest.approx(150.0 - q / 200.0, rel=1e-9)
    assert r.permanente[-1] == pytest.approx(20.0 + q / 10.0, rel=1e-9)


def test_fluxo_com_a_outra_face_isolada_sobe_sem_parar_e_conserva_energia():
    fluxo = ct.Face(ct.FLUXO, fluxo=5000.0)
    r = ct.calcular(ct.Peca(ct.PAREDE, ACO, 20.0, fluxo, ct.Face(ct.ISOLADA), espessura_mm=30.0))
    assert r.permanente is None and r.tau is None
    assert any("sobe sem parar" in a for a in r.avisos)
    # toda a energia que entra fica na peça
    assert r.energia()[-1] == pytest.approx(5000.0 * r.duracao, rel=1e-9)


def test_peca_que_esquenta_por_igual_segue_a_capacitancia_concentrada():
    cobre = ct.MATERIAIS["Cobre puro"]
    ar = ct.Face(ct.CONVECCAO, h=25.0, t_fluido=20.0)
    r = ct.calcular(ct.Peca(ct.ESFERA, cobre, 200.0, ar, ar, diametro_mm=30.0))
    assert r.uniforme and r.biot < 0.01
    tau = cobre.massa_especifica * cobre.calor_especifico * 0.030 / 6.0 / 25.0
    t = r.tempos[1500]
    assert r.temperaturas[1500, 0] == pytest.approx(20.0 + 180.0 * math.exp(-t / tau), rel=2e-3)


def test_tempo_para_um_ponto_chegar():
    r = ct.calcular(
        ct.Peca(
            ct.CILINDRO,
            ACO,
            20.0,
            ct.Face(),
            ct.Face(ct.CONVECCAO, h=100.0, t_fluido=500.0),
            diametro_mm=100.0,
        )
    )
    centro = r.ponto("Centro")
    t = r.tempo_para(centro, 450.0)
    assert t is not None
    i = int(np.searchsorted(r.tempos, t))
    assert r.temperaturas[i - 1, centro.indice] < 450.0 <= r.temperaturas[i, centro.indice]
    assert r.tempo_para(centro, 600.0) is None
    assert (
        ct.primeiro_cruzamento(np.array([0.0, 1.0, 2.0]), np.array([0.0, 10.0, 20.0]), 15.0) == 1.5
    )


def test_dados_ruins_dao_mensagem():
    ruim = ct.Peca(
        ct.CILINDRO,
        ct.Material("x", 0.0, 1.0, 1.0),
        20.0,
        AR,
        ct.Face(ct.CONVECCAO, h=0.0),
        diametro_mm=50.0,
        diametro_interno_mm=60.0,
    )
    erros = ct.problemas(ruim)
    assert any("condutividade" in e for e in erros)
    assert any("diâmetro de dentro" in e for e in erros)
    assert any("coeficiente h" in e for e in erros)
    with pytest.raises(ct.ErroDoCalor):
        ct.calcular(ruim)


# ---------------------------------------------------------------------------------------------
# Duas dimensões
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("partes", "area", "fora", "furos"),
    [
        ([sd._circ(100)], math.pi * 2500, math.pi * 100, 0.0),
        ([sd._ret(0, 0, 120, 60)], 7200.0, 360.0, 0.0),
        (
            [sd._circ(100), sd._circ(96, furo=True)],
            math.pi * (2500 - 48**2),
            math.pi * 100,
            math.pi * 96,
        ),
        ([sd.Parte(sd.RET, 0, 0, 120, 60, giro=30)], 7200.0, 360.0, 0.0),
        (
            [sd._ret(0, 0, 200, 100), sd._circ(40, furo=True)],
            20000 - math.pi * 400,
            600.0,
            math.pi * 40,
        ),
    ],
)
def test_grade_guarda_a_area_e_o_contorno_de_verdade(partes, area, fora, furos):
    g = cs.montar_grade(partes)
    assert g.area_mm2 == pytest.approx(area, rel=3e-3)
    assert g.contorno_fora_mm == pytest.approx(fora, rel=2e-3)
    assert g.contorno_furos_mm == pytest.approx(furos, rel=2e-3, abs=1e-9)
    assert g.ativa.sum() <= cs.LIMITE_DE_CELULAS


def test_retangulo_e_o_produto_das_duas_paredes():
    h = ct.Face(ct.CONVECCAO, h=400.0, t_fluido=20.0)
    r = cs.calcular([sd._ret(0, 0, 80, 40)], ACO, 300.0, h)
    caso_a = ct.CasoDeLivro(
        ct.PAREDE, 0.040, 400 * 0.040 / ACO.condutividade, 300.0, 20.0, 0.0, ACO.difusividade
    )
    caso_b = ct.CasoDeLivro(
        ct.PAREDE, 0.020, 400 * 0.020 / ACO.condutividade, 300.0, 20.0, 0.0, ACO.difusividade
    )
    g = r.grade
    i, j = np.nonzero(g.ativa)
    cx, cy = (g.xs[i] + g.xs[i + 1]) / 2, (g.ys[j] + g.ys[j + 1]) / 2
    for k in (12, 40, 120):
        t = r.tempos_dos_quadros[k]
        for x, y in ((0.0, 0.0), (39.6, 19.8)):
            c = int(np.argmin((cx - x) ** 2 + (cy - y) ** 2))
            exato = 20.0 + 280.0 * ((ct.solucao_em_serie(caso_a, t, cx[c]) - 20.0) / 280.0) * (
                (ct.solucao_em_serie(caso_b, t, cy[c]) - 20.0) / 280.0
            )
            assert r.quadros[k, c] == pytest.approx(exato, abs=0.1)


def test_circulo_fino_de_cobre_segue_a_capacitancia_concentrada():
    cobre = ct.MATERIAIS["Cobre puro"]
    r = cs.calcular([sd._circ(20)], cobre, 100.0, ct.Face(ct.CONVECCAO, h=20.0, t_fluido=20.0))
    tau = cobre.massa_especifica * cobre.calor_especifico * 0.020 / (4 * 20.0)
    assert r.tau == pytest.approx(tau, rel=2e-3)


def test_tubo_em_regime_permanente_e_resistencias_em_serie():
    inox = ct.MATERIAIS["Aço inoxidável AISI 304"]
    r = cs.calcular(
        [sd._circ(100), sd._circ(60, furo=True)],
        inox,
        20.0,
        ct.Face(ct.CONVECCAO, h=15.0, t_fluido=20.0),
        ct.Face(ct.TEMPERATURA, t_fixa=200.0),
    )
    g = r.grade
    fora = ~g.face_furo
    comp, dist = g.face_comprimento[fora] / 1000, g.face_distancia[fora] / 1000
    q = np.sum(
        comp / (dist / inox.condutividade + 1 / 15.0) * (r.permanente[g.face_celula[fora]] - 20.0)
    )
    exato = 180.0 / (
        math.log(50 / 30) / (2 * math.pi * inox.condutividade) + 1 / (2 * math.pi * 0.05 * 15.0)
    )
    assert q == pytest.approx(exato, rel=2e-3)
    assert r.tempo_para("min", 150.0) is not None


# ---------------------------------------------------------------------------------------------
# Cena, figuras e registro
# ---------------------------------------------------------------------------------------------
def test_cena_da_peca_leva_os_canais_e_os_graficos():
    r = ct.calcular(
        ct.Peca(
            ct.CILINDRO,
            ACO,
            20.0,
            AR,
            ct.Face(ct.CONVECCAO, h=500.0, t_fluido=150.0),
            diametro_mm=80.0,
            diametro_interno_mm=40.0,
        )
    )
    dados = cc.cena_da_peca(r, alvo=100.0)
    canais = np.frombuffer(base64.b64decode(dados["canais_b64"]), dtype="<f4")
    assert canais.size == dados["n_canais"] * len(dados["tempos"])
    assert [g["tipo"] for g in dados["graficos"]] == ["tempo", "perfil", "tempo", "tempo"]
    # 20 °C por dentro e 150 °C por fora: em regime fica um gradiente, e a peça não equaliza
    assert [m["nome"] for m in dados["graficos"][0]["marcos"]] == ["estabiliza"]
    assert ct.marcos(r).gradiente_de_regime > 5.0  # 8,8 °C de gradiente: maior que 1 % do salto
    tipos = [f["tipo"] for f in dados["formas"]]
    assert tipos.count("seta") == 6 + 4  # seis na face de fora e quatro na de dentro
    assert "cota" in tipos
    assert dados["graficos"][0]["limites"] == [{"nome": "alvo", "valor": 100.0}]
    assert dados["escalas"][0]["unidade"] == "°C"
    # o mesmo cálculo dá a mesma cena (o tocador não volta ao começo à toa)
    assert cc.cena_da_peca(r, alvo=100.0)["id"] == dados["id"]


def test_registro_da_peca_e_valido_e_tem_as_figuras():
    r = ct.calcular(ct.Peca(ct.PAREDE, ACO, 300.0, ct.Face(ct.ISOLADA), AR, espessura_mm=20.0))
    ponto = r.ponto("Face da esquerda")
    registro = cc.registro_da_peca(r, alvo=100.0, ponto=ponto, prazo=60.0)
    assert avaliar_contrato_registro(registro)["valido"]
    assert registro["status"] == "Não atende"  # o centro leva mais de 1 min para chegar a 100 °C
    figuras = fnt.figuras_do_registro(registro["resultados"])
    assert [f.titulo for f in figuras] == [
        "Temperatura nos pontos da peça",
        "Diferença dentro da peça",
        "Temperatura ao longo da espessura",
    ]
    assert all(f.png.startswith(b"\x89PNG") for f in figuras)


def test_registro_da_secao_tem_os_mapas():
    partes = [sd._circ(60), sd._circ(30, furo=True)]
    r = cs.calcular(
        partes,
        ACO,
        20.0,
        ct.Face(ct.CONVECCAO, h=10.0, t_fluido=20.0),
        ct.Face(ct.CONVECCAO, h=1000.0, t_fluido=150.0),
    )
    registro = cc.registro_da_secao(r, "tubo 60 × 15", alvo=120.0)
    assert avaliar_contrato_registro(registro)["valido"]
    figuras = fnt.figuras_do_registro(registro["resultados"])
    assert [f.titulo for f in figuras] == [
        "Temperatura na seção",
        "Temperatura na seção em alguns instantes",
    ]
    dados = cc.cena_da_secao(r, partes, 120.0, identificador="x")
    assert dados["grade"]["escala"] == 0 and dados["id"] == "x"


def test_figura_estragada_e_pulada():
    assert (
        fnt.figuras_do_registro(
            {fnt.CHAVE: [{"tipo": "linhas", "series": [{"x": [1], "y": "a"}]}, 3, None]}
        )
        == []
    )
    assert fnt.figuras_do_registro({fnt.CHAVE: "nada"}) == []


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


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(PAGINA).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_pagina_calcula_e_todo_campo_tem_ajuda():
    at = _abrir()
    metricas = [(m.label, m.value) for m in at.metric]
    assert metricas[0][0] == "Tempo mostrado" and metricas[0][1].endswith("min")
    assert "Média no fim" in dict(metricas)  # a aba da seção também calcula
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    }
    sem_ajuda -= {("text_input", "Nome do novo projeto"), ("text_input", "Identificação da peça")}
    assert not sem_ajuda, sorted(sem_ajuda)
    at.number_input(key="cnt_alvo").set_value(140.0).run()
    assert not at.exception
    assert any(m.label == "Centro a 140,0 °C" for m in at.metric)
    at.selectbox(key="cnt_forma").set_value("Parede plana").run()
    assert not at.exception
    at.selectbox(key="cnt_fa_tipo").set_value("Fluxo de calor que entra").run()
    assert not at.exception
    at.selectbox(key="cns_origem").set_value("I").run()
    assert not at.exception
