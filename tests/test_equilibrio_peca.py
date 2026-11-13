"""Equilíbrio de uma peça: contas de mão, apoios que faltam ou sobram, unidades e a tela."""

from __future__ import annotations

import math
import random
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from core import elementos_catalogo as cat
from core import equilibrio_corpo as eq
from core.elementos_base import calcular_caso
from core.elementos_equilibrio import CASO_EQUILIBRIO as CASO
from core.elementos_equilibrio import marcas_para_a_tela
from core.equilibrio_modelos import MODELOS, apoio, carga, corte, trecho

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SI = eq.Unidades("m", "N")


def _resolver(apoios, cargas, cortes=(), trechos=(), unidades=SI):
    problema = eq.problema_das_tabelas(trechos, apoios, cargas, cortes, unidades)
    return eq.resolver(problema)


def _reacao(solucao, nome):
    return next(r for r in solucao.reacoes if r.apoio.nome == nome)


def _caso(apoios, cargas, cortes=(), trechos=(), comprimento="m", forca="kN"):
    return calcular_caso(
        CASO,
        {
            "comprimento": comprimento,
            "forca": forca,
            "apoios": apoios,
            "cargas": cargas,
            "cortes": cortes,
            "trechos": trechos,
        },
    )


def _linha(resultado, trecho_do_nome):
    return next(v for v in resultado.verificacoes if trecho_do_nome in v.nome)


# ---------------------------------------------------------------------------
# Contas de mão
# ---------------------------------------------------------------------------


def test_viga_com_forca_inclinada():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("F", eq.FORCA, 1, 0, 10, -90), carga("H", eq.FORCA, 1, 0, 3, 0)],
    )
    assert s.isostatica and s.para
    assert _reacao(s, "B").fy == pytest.approx(2.5)
    assert _reacao(s, "A").fy == pytest.approx(7.5)
    assert _reacao(s, "A").fx == pytest.approx(-3.0)


def test_rolete_que_segura_na_horizontal_com_braco_vertical():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 0, 2, 0)],
        [carga("F", eq.FORCA, 3, 0, 10)],
    )
    assert _reacao(s, "B").fx == pytest.approx(-15.0)
    assert _reacao(s, "A").fx == pytest.approx(15.0)
    assert _reacao(s, "A").fy == pytest.approx(10.0)


def test_engaste_devolve_o_momento():
    s = _resolver(
        [apoio("A", eq.ENGASTE, 0, 0, 0)],
        [
            carga("V", eq.FORCA, 2, 1, 10, -90),
            carga("H", eq.FORCA, 2, 1, 5, 0),
            carga("M", eq.MOMENTO, 2, 1, 1),
        ],
    )
    a = _reacao(s, "A")
    assert (a.fx, a.fy) == (pytest.approx(-5.0), pytest.approx(10.0))
    assert a.m == pytest.approx(-(2 * -10 - 1 * 5 + 1))


def test_carga_triangular_tem_a_resultante_a_dois_tercos():
    """Triângulo de 0 a 6 N/m em 3 m: 9 N a 2 m do início."""
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 3, 0)],
        [carga("q", eq.DISTRIBUIDA, 0, 0, 0, ate=(3, 0), valor2=6)],
    )
    assert s.acoes[0].x == pytest.approx(2.0)
    assert _reacao(s, "B").fy == pytest.approx(6.0)
    assert _reacao(s, "A").fy == pytest.approx(3.0)


def test_distribuida_antissimetrica_vira_binario_puro():
    """De +w a −w: nenhuma força sobra e o momento é w·L²/6."""
    s = _resolver(
        [apoio("A", eq.ENGASTE, 0, 0, 0)],
        [carga("q", eq.DISTRIBUIDA, 0, 0, 6, ate=(3, 0), valor2=-6)],
    )
    a = _reacao(s, "A")
    assert a.modulo == pytest.approx(0.0, abs=1e-9)
    assert abs(a.m) == pytest.approx(6 * 9 / 6)


def test_peso_usa_a_massa_e_o_g():
    s = _resolver([apoio("A", eq.ENGASTE, 0, 0, 0)], [carga("P", eq.PESO, 2, 0, 100)])
    assert _reacao(s, "A").fy == pytest.approx(100 * eq.G)
    assert _reacao(s, "A").m == pytest.approx(200 * eq.G)


def test_cabo_da_lanca_contra_a_conta_de_mao():
    """Pino em (0,0), carga de 8 em (3,2), cabo até (0;3,5): ΣM_A dá a tração."""
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.CABO, 3, 2, ponta=(0, 3.5))],
        [carga("F", eq.FORCA, 3, 2, 8)],
    )
    l = math.hypot(3, 1.5)
    # Momento da tração em A: 3·(1,5/L)·T + 2·(3/L)·T.
    esperado = 8 * 3 / (3 * 1.5 / l + 2 * 3 / l)
    assert _reacao(s, "B").n == pytest.approx(esperado)


def test_escada_com_atrito_contra_a_conta_de_mao():
    s = _resolver(
        [
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.4),
            apoio("B", eq.SIMPLES, 1.5, 4, 180),
        ],
        [carga("P", eq.FORCA, 0.75, 2, 100)],
    )
    assert _reacao(s, "B").n == pytest.approx(100 * 0.75 / 4)
    assert _reacao(s, "A").n == pytest.approx(100)
    assert abs(_reacao(s, "A").t) == pytest.approx(100 * 0.75 / 4)


def test_guia_segura_o_giro_e_deixa_correr():
    s = _resolver(
        [apoio("A", eq.GUIA, 0, 0, 90), apoio("B", eq.ROLETE, 2, 0, 0)],
        [carga("F", eq.FORCA, 1, 0, 6)],
    )
    a = _reacao(s, "A")
    assert a.fy == pytest.approx(6.0)
    assert a.fx == pytest.approx(0.0)
    assert a.m == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Apoios que faltam
# ---------------------------------------------------------------------------


def test_so_um_pino_gira_em_torno_dele():
    s = _resolver([apoio("A", eq.PINO, 1, 2)], [carga("F", eq.FORCA, 3, 2, 5)])
    assert not s.para
    assert s.movimento.giro
    assert (s.movimento.x, s.movimento.y) == (pytest.approx(1.0), pytest.approx(2.0))
    assert s.movimento.sentido == -1  # força para baixo à direita do pino: horário


def test_dois_roletes_verticais_correm_de_lado_com_forca_horizontal():
    s = _resolver(
        [apoio("A", eq.ROLETE, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("H", eq.FORCA, 2, 0, 5, 0)],
    )
    assert not s.para
    assert not s.movimento.giro
    assert s.movimento.angulo == pytest.approx(0.0)


def test_tres_linhas_concorrentes_nao_seguram_o_giro():
    """Três reações que passam por um ponto só: conta três incógnitas e ainda assim gira."""
    s = _resolver(
        [
            apoio("A", eq.ROLETE, 0, 0, 90),
            apoio("B", eq.ROLETE, 2, 0, 90),
            apoio("C", eq.ROLETE, 1, 3, 0),
        ],
        [carga("F", eq.FORCA, 1, 1, 5, 45)],
    )
    # A e B são paralelas: C segura a horizontal. Esta combinação é boa.
    assert s.para
    giro = _resolver(
        [
            apoio("A", eq.ROLETE, 0, 0, 0),
            apoio("B", eq.ROLETE, 0, 2, 0),
            apoio("C", eq.ROLETE, 0, 4, 0),
        ],
        [carga("F", eq.FORCA, 3, 1, 5)],
    )
    assert not giro.para
    assert giro.incognitas == 3 and giro.posto == 2
    assert not giro.movimento.giro  # três horizontais: corre na vertical


def test_rolete_alinhado_com_o_pino_nao_segura():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 0, 3, 90)],
        [carga("F", eq.FORCA, 2, 0, 5)],
    )
    assert not s.para
    assert s.movimento.giro
    assert (s.movimento.x, s.movimento.y) == (pytest.approx(0.0), pytest.approx(0.0))


def test_faltando_apoio_mas_a_carga_nao_empurra_para_o_lado_livre():
    """Dois roletes e carga vertical: para, mas só com esta carga."""
    s = _resolver(
        [apoio("A", eq.ROLETE, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("F", eq.FORCA, 1, 0, 8)],
    )
    assert s.para and s.livres == 1
    assert _reacao(s, "B").fy == pytest.approx(2.0)
    r = _caso(
        [apoio("A", eq.ROLETE, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("F", eq.FORCA, 1, 0, 8)],
    )
    assert r.status == "ALERTA"
    assert any("Faltam apoios" in a for a in r.alertas)


def test_peca_sem_apoio_suficiente_vira_resultado_e_nao_erro():
    r = _caso([apoio("A", eq.PINO, 0, 0)], [carga("F", eq.FORCA, 2, 0, 5)])
    assert r.status == "NÃO OK"
    assert "não fica parada" in r.resumo
    assert r.figuras
    assert "gira em torno do ponto (0; 0) m" in r.alertas[0]


# ---------------------------------------------------------------------------
# Apoios que sobram
# ---------------------------------------------------------------------------


def test_duas_dobradicas_separam_a_horizontal_mas_nao_o_peso():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 700), apoio("B", eq.PINO, 0, 100)],
        [carga("P", eq.FORCA, 300, 400, 400)],
    )
    assert s.grau_hiperestatico == 1
    a, b = _reacao(s, "A"), _reacao(s, "B")
    assert a.soltas == ("y",) and b.soltas == ("y",)
    # ΣM: 400 × 300 = H × 600. A horizontal tem valor único, e a soma das verticais também.
    assert abs(a.fx) == pytest.approx(200.0)
    assert a.fx == pytest.approx(-b.fx)
    assert a.fy + b.fy == pytest.approx(400.0)


def test_viga_com_dois_pinos_nao_separa_a_horizontal():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.PINO, 4, 0)],
        [carga("H", eq.FORCA, 1, 0, 6, 0), carga("V", eq.FORCA, 1, 0, 8)],
    )
    assert s.grau_hiperestatico == 1
    a, b = _reacao(s, "A"), _reacao(s, "B")
    assert a.soltas == ("x",)
    assert b.fy == pytest.approx(2.0)
    assert a.fy == pytest.approx(6.0)
    assert a.fx + b.fx == pytest.approx(-6.0)


def test_hiperestatica_avisa_e_nao_reprova():
    r = _caso(
        [apoio("A", eq.ENGASTE, 0, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("V", eq.FORCA, 2, 0, 8)],
        trechos=[trecho(0, 0, 4, 0)],
    )
    assert r.status == "ALERTA"
    assert any("não separa" in a for a in r.alertas)
    assert _linha(r, "Reações que a estática define").resistente == 4.0


def test_escada_com_atrito_nas_duas_pontas_acha_uma_divisao_que_serve():
    s = _resolver(
        [
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.4),
            apoio("B", eq.ATRITO, 1.5, 4, 180, mu=0.4),
        ],
        [carga("P", eq.FORCA, 0.75, 2, 100)],
    )
    assert s.grau_hiperestatico == 1 and s.divisao_viavel
    a, b = _reacao(s, "A"), _reacao(s, "B")
    assert a.n >= 0.0 and b.n >= 0.0
    assert abs(a.t) <= 0.4 * a.n + 1e-9
    assert abs(b.t) <= 0.4 * b.n + 1e-9


def test_atrito_pequeno_demais_nas_duas_pontas_nao_tem_divisao():
    s = _resolver(
        [
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.01),
            apoio("B", eq.ATRITO, 3, 4, 180, mu=0.01),
        ],
        [carga("P", eq.FORCA, 3, 4, 100)],
    )
    assert not s.divisao_viavel


# ---------------------------------------------------------------------------
# Apoio de um lado só
# ---------------------------------------------------------------------------


def test_pe_levanta_e_o_programa_reprova():
    r = _caso(
        [apoio("A", eq.SIMPLES, 0, 0), apoio("B", eq.ROLETE, 1, 0)],
        [carga("F", eq.FORCA, 2, 0, 10)],
    )
    assert r.status == "NÃO OK"
    assert _linha(r, "Apoio A encostado").status == "NÃO OK"
    assert "descola" in r.tabelas[0].linhas[0]["Como trabalha"]


def test_cabo_que_precisaria_empurrar_reprova():
    r = _caso(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.CABO, 2, 0, ponta=(2, -2))],
        [carga("F", eq.FORCA, 3, 0, 10)],
    )
    assert _linha(r, "Cabo B tracionado").status == "NÃO OK"
    assert "afrouxa" in r.tabelas[0].linhas[1]["Como trabalha"]


def test_biela_comprime_sem_reprovar():
    r = _caso(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.BIELA, 2, 0, ponta=(2, -2))],
        [carga("F", eq.FORCA, 3, 0, 10)],
    )
    assert r.status != "NÃO OK"
    assert r.tabelas[0].linhas[1]["Como trabalha"] == "Comprimida"


def test_atrito_que_nao_segura_reprova():
    r = _caso(
        [
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.1),
            apoio("B", eq.SIMPLES, 1.5, 4, 180),
        ],
        [carga("P", eq.FORCA, 0.75, 2, 100)],
    )
    assert _linha(r, "Atrito em A").status == "NÃO OK"


def test_atrito_zero_com_tangente_zero_nao_reprova_a_toa():
    r = _caso(
        [
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.0),
            apoio("B", eq.ATRITO, 4, 0, 90, mu=0.0),
        ],
        [carga("P", eq.FORCA, 2, 0, 100)],
    )
    assert _linha(r, "Atrito em A").status == "OK"


# ---------------------------------------------------------------------------
# Corte
# ---------------------------------------------------------------------------


def test_corte_de_viga_com_carga_no_meio():
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("F", eq.FORCA, 2, 0, 10)],
        cortes=[corte("S", 1, 0)],
    )
    e = eq.esforco_no_corte(s, s.problema.cortes[0])
    assert e.v == pytest.approx(5.0)
    assert e.m == pytest.approx(5.0)  # tração embaixo: positivo
    assert e.n == pytest.approx(0.0)


def test_corte_dentro_da_carga_distribuida():
    """Viga de 4 m com 3 N/m: em x = 1, V = 6 − 3 = 3 e M = 6 − 1,5 = 4,5."""
    s = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)],
        [carga("q", eq.DISTRIBUIDA, 0, 0, 3, ate=(4, 0), valor2=3)],
        cortes=[corte("S", 1, 0)],
    )
    e = eq.esforco_no_corte(s, s.problema.cortes[0])
    assert e.v == pytest.approx(3.0)
    assert e.m == pytest.approx(4.5)


def test_corte_de_barra_tracionada_e_de_barra_em_pe():
    s = _resolver(
        [apoio("A", eq.ENGASTE, 0, 0, 90)],
        [carga("F", eq.FORCA, 0, 2, 7, 90), carga("H", eq.FORCA, 0, 2, 3, 0)],
        cortes=[corte("S", 0, 1, 90)],
    )
    e = eq.esforco_no_corte(s, s.problema.cortes[0])
    assert e.n == pytest.approx(7.0)
    assert abs(e.v) == pytest.approx(3.0)
    assert abs(e.m) == pytest.approx(3.0)


def test_corte_nao_depende_do_lado_de_quem_desenhou():
    apoios = [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)]
    cargas = [carga("F", eq.FORCA, 3, 0, 10)]
    ida = _resolver(apoios, cargas, cortes=[corte("S", 1, 0, 0)])
    volta = _resolver(apoios, cargas, cortes=[corte("S", 1, 0, 180)])
    a = eq.esforco_no_corte(ida, ida.problema.cortes[0])
    b = eq.esforco_no_corte(volta, volta.problema.cortes[0])
    assert (a.n, a.v, a.m) == pytest.approx((b.n, b.v, b.m))


def test_corte_avisa_quando_atravessa_mais_de_um_trecho():
    r = _caso(
        [apoio("A", eq.ENGASTE, 0, 0, 0)],
        [carga("F", eq.FORCA, 1, 2, 10)],
        cortes=[corte("S", 0.5, 1, 90)],
        trechos=[trecho(0, 0, 0, 2), trecho(0, 2, 1, 2), trecho(1, 2, 1, 0)],
    )
    assert any("atravessa 2 trechos" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# Propriedades que valem para qualquer peça
# ---------------------------------------------------------------------------


def _sorteio_isostatico(sorteio: random.Random):
    """Pino + rolete ou engaste, com cargas de todos os tipos em lugares quaisquer."""
    numero = lambda: round(sorteio.uniform(-5, 5), 3)  # noqa: E731
    if sorteio.random() < 0.5:
        apoios = [apoio("A", eq.ENGASTE, numero(), numero(), 0)]
    else:
        apoios = [
            apoio("A", eq.PINO, numero(), numero()),
            apoio("B", eq.ROLETE, numero(), numero(), sorteio.uniform(-180, 180)),
        ]
    cargas = []
    for i in range(sorteio.randint(1, 5)):
        tipo = sorteio.choice(eq.TIPOS_DE_CARGA)
        if tipo == eq.DISTRIBUIDA:
            ate = (numero() + 6.0, numero())
            cargas.append(
                carga(
                    f"C{i}",
                    tipo,
                    numero(),
                    numero(),
                    numero(),
                    numero() * 30,
                    ate=ate,
                    valor2=numero(),
                )
            )
        else:
            valor = abs(numero()) if tipo == eq.PESO else numero()
            cargas.append(carga(f"C{i}", tipo, numero(), numero(), valor, numero() * 30))
    return apoios, cargas


def test_equilibrio_fecha_em_qualquer_peca_isostatica():
    sorteio = random.Random(20261105)
    fechados = 0
    for _ in range(400):
        apoios, cargas = _sorteio_isostatico(sorteio)
        try:
            s = _resolver(apoios, cargas)
        except eq.ErroDeEquilibrio:
            continue
        if not s.para:
            continue
        forca, momento = eq.residuos(s)
        assert forca < 1e-7 * max(s.referencia, 1.0)
        assert momento < 1e-6 * max(s.referencia, 1.0) * 20
        fechados += 1
    assert fechados > 300


def test_corte_pelos_dois_lados_da_o_mesmo_valor():
    """O que está à frente do corte equilibra o que está atrás: conta feita por dois caminhos."""
    sorteio = random.Random(7)
    for _ in range(120):
        apoios, cargas = _sorteio_isostatico(sorteio)
        try:
            s = _resolver(apoios, cargas)
        except eq.ErroDeEquilibrio:
            continue
        if not s.para:
            continue
        c = eq.Corte("S", sorteio.uniform(-3, 3), sorteio.uniform(-3, 3), 0.0)
        tx, ty = eq.eixo_do_corte(c.angulo)
        frente = eq.esforco_no_corte(s, c)
        # Atrás: tudo que sobra, somado à mão e levado ao ponto do corte.
        fx = fy = m = 0.0
        for carga_ in s.problema.cargas:
            completa = eq.acao_da_carga(carga_)
            na_frente = eq._acoes_do_lado(carga_, c.x, c.y, tx, ty)
            fx += completa.fx - sum(a.fx for a in na_frente)
            fy += completa.fy - sum(a.fy for a in na_frente)
            m += eq._momento(completa, c.x, c.y) - sum(eq._momento(a, c.x, c.y) for a in na_frente)
        for r in s.reacoes:
            if (r.apoio.x - c.x) * tx + (r.apoio.y - c.y) * ty <= 0.0:
                fx += r.fx
                fy += r.fy
                m += eq._momento(eq.Acao("", r.apoio.x, r.apoio.y, r.fx, r.fy, r.m), c.x, c.y)
        assert frente.n == pytest.approx(-(fx * tx + fy * ty), abs=1e-6)
        assert frente.m == pytest.approx(-m, abs=1e-5)


def test_girar_e_mudar_de_lugar_a_peca_nao_muda_as_reacoes():
    def montar(angulo: float, dx: float, dy: float):
        c, s_ = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
        girar = lambda x, y: (x * c - y * s_ + dx, x * s_ + y * c + dy)  # noqa: E731
        pa, pb, pf = girar(0, 0), girar(3, 1), girar(1, 2)
        return _resolver(
            [
                apoio("A", eq.PINO, *pa),
                apoio("B", eq.ROLETE, *pb, 80 + angulo),
            ],
            [carga("F", eq.FORCA, *pf, 12, -70 + angulo), carga("M", eq.MOMENTO, *pf, 4)],
        )

    base = montar(0, 0, 0)
    for angulo, dx, dy in ((30, 1, 2), (217, -5, 3), (90, 0, 0)):
        outra = montar(angulo, dx, dy)
        assert _reacao(outra, "A").modulo == pytest.approx(_reacao(base, "A").modulo)
        assert _reacao(outra, "B").modulo == pytest.approx(_reacao(base, "B").modulo)


def test_unidades_nao_mudam_a_peca():
    em_si = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 3, 0)],
        [
            carga("F", eq.FORCA, 1, 0, 2000),
            carga("q", eq.DISTRIBUIDA, 0, 0, 500, ate=(3, 0), valor2=500),
            carga("M", eq.MOMENTO, 2, 0, 300),
        ],
    )
    em_mm = _resolver(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 3000, 0)],
        [
            carga("F", eq.FORCA, 1000, 0, 2),
            carga("q", eq.DISTRIBUIDA, 0, 0, 0.0005, ate=(3000, 0), valor2=0.0005),
            carga("M", eq.MOMENTO, 2000, 0, 0.3),
        ],
        unidades=eq.Unidades("mm", "kN"),
    )
    assert _reacao(em_mm, "B").fy == pytest.approx(_reacao(em_si, "B").fy)
    assert _reacao(em_mm, "A").fy == pytest.approx(_reacao(em_si, "A").fy)


def test_trocar_a_unidade_converte_e_a_resposta_fica_igual():
    modelo = MODELOS[0]
    dados = modelo.dados()
    de = eq.Unidades(modelo.comprimento, modelo.forca)
    para = eq.Unidades("mm", "N")
    convertidos = eq.converter_dados(dados, de, para)
    assert convertidos["apoios"][1]["x"] == pytest.approx(4000.0)
    assert convertidos["cargas"][0]["valor"] == pytest.approx(10000.0)
    a = calcular_caso(CASO, {"comprimento": "m", "forca": "kN", **dados})
    b = calcular_caso(CASO, {"comprimento": "mm", "forca": "N", **convertidos})
    ra = next(m.valor for m in a.metricas if m.rotulo == "Reação em A")
    rb = next(m.valor for m in b.metricas if m.rotulo == "Reação em A")
    assert rb == pytest.approx(ra * 1000.0)


# ---------------------------------------------------------------------------
# Caso e modelos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modelo", MODELOS, ids=lambda m: m.nome)
def test_todo_modelo_abre_parado_e_com_figura(modelo):
    r = calcular_caso(
        CASO, {"comprimento": modelo.comprimento, "forca": modelo.forca, **modelo.dados()}
    )
    assert r.status != "NÃO OK", r.resumo
    assert r.figuras and len(r.figuras[0].png) > 1000
    for envio in r.envios:
        chaves = {c.chave for c in cat.CASOS[envio.destino].campos}
        assert set(envio.valores) <= chaves


@pytest.mark.parametrize("modelo", MODELOS, ids=lambda m: m.nome)
def test_todo_modelo_desenha_as_reacoes_na_prancheta(modelo):
    marcas = marcas_para_a_tela(
        {"comprimento": modelo.comprimento, "forca": modelo.forca, **modelo.dados()}
    )
    assert marcas["para"]
    assert len(marcas["reacoes"]) == len(modelo.apoios)
    assert len(marcas["cortes"]) == len(modelo.cortes)
    assert all(r["texto"] for r in marcas["reacoes"])


def test_conta_passo_a_passo_soma_zero():
    modelo = MODELOS[0]
    r = calcular_caso(CASO, {"comprimento": "m", "forca": "kN", **modelo.dados()})
    linhas = next(t for t in r.tabelas if t.titulo == "Conta passo a passo").linhas
    soma = linhas[-1]
    assert soma["Item"].startswith("Soma")
    assert all(abs(v) < 1e-6 for v in soma.values() if isinstance(v, float))
    assert any(linha["Item"] == "Carga q1" for linha in linhas)


def test_envio_do_corte_e_do_pino_em_kn_mesmo_com_a_tela_em_newton():
    r = _caso(
        [apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4000, 0)],
        [carga("F", eq.FORCA, 2000, 0, 10000)],
        cortes=[corte("S", 2000, 0)],
        comprimento="mm",
        forca="N",
    )
    flexao = next(e for e in r.envios if e.destino == "flexao_secao")
    pino = next(e for e in r.envios if e.destino == "pino_articulacao")
    assert flexao.valores["m_kNm"] == pytest.approx(10.0)
    assert pino.valores["forca_kN"] == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("apoios", "cargas", "texto"),
    [
        ([], [carga("F", eq.FORCA, 0, 0, 1)], "ao menos um apoio"),
        ([apoio("A", eq.PINO, 0, 0)], [], "ao menos uma carga"),
        ([apoio("A", eq.ENGASTE, 0, 0)], [carga("F", eq.FORCA, 0, 0, 0)], "todas valem zero"),
        (
            [apoio("A", eq.ENGASTE, 0, 0)],
            [carga("q", eq.DISTRIBUIDA, 1, 0, 1)],
            "onde a carga distribuída termina",
        ),
        (
            [apoio("A", eq.ENGASTE, 0, 0)],
            [carga("q", eq.DISTRIBUIDA, 1, 0, 1, ate=(1, 0))],
            "mesmo ponto",
        ),
        (
            [apoio("A", eq.CABO, 1, 1, ponta=(1, 1))],
            [carga("F", eq.FORCA, 0, 0, 1)],
            "mesmo lugar",
        ),
        (
            [apoio("A", eq.ATRITO, 0, 0)],
            [carga("F", eq.FORCA, 0, 0, 1)],
            "coeficiente de atrito",
        ),
        (
            [apoio("A", eq.ENGASTE, 0, 0)],
            [carga("P", eq.PESO, 0, 0, -5)],
            "massa não pode ser negativa",
        ),
    ],
)
def test_dado_ruim_vira_mensagem_clara(apoios, cargas, texto):
    with pytest.raises(ValueError, match=texto):
        _caso(apoios, cargas)


def test_nomes_em_branco_seguem_a_sequencia():
    linhas = [
        carga("", eq.FORCA, 0, 0, 1),
        carga("", eq.FORCA, 0, 0, 1),
        carga("", eq.MOMENTO, 0, 0, 1),
    ]
    assert [c["nome"] for c in eq.nomear("cargas", linhas)] == ["F1", "F2", "M1"]
    assert [a["nome"] for a in eq.nomear("apoios", [apoio("", eq.PINO, 0, 0)])] == ["A"]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def _abrir_tela() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.session_state["vigas_abrir_peca"] = True
    at.switch_page("app_pages/vigas_eixos.py")
    return at.run()


def test_atalho_antigo_do_calculo_de_pecas_leva_para_vigas_e_eixos():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.session_state["assistente_geometria"] = "equilibrio_peca"
    at.switch_page("app_pages/assistente_cargas.py")
    at.run()
    assert not at.exception
    assert at.session_state["vigas_tipo"] == "Peça ou pórtico desenhado"
    assert at.session_state["eq_modelo"] == MODELOS[0].nome
    assert at.session_state["assistente_geometria"] is None


def test_viga_reta_continua_sendo_o_que_abre_primeiro():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.switch_page("app_pages/vigas_eixos.py")
    at.run()
    assert not at.exception
    assert at.session_state["vigas_tipo"] == "Viga ou eixo reto"
    assert "eq_dados" not in at.session_state


def test_tela_abre_com_o_modelo_e_mostra_a_resposta():
    at = _abrir_tela()
    assert not at.exception
    assert at.session_state["eq_modelo"] == MODELOS[0].nome
    assert any("Reações nos apoios" in m.value for m in at.markdown)
    assert any("Conta passo a passo" in m.value for m in at.markdown)


def test_trocar_o_modelo_na_tela_troca_unidade_e_dados():
    at = _abrir_tela()
    at.selectbox(key="eq_modelo").set_value("Alavanca").run()
    assert not at.exception
    assert at.session_state["eq_comprimento"] == "mm"
    assert at.session_state["eq_forca"] == "N"
    assert len(at.session_state["eq_dados"]["apoios"]) == 2


def test_trocar_a_unidade_na_tela_converte_o_desenho():
    at = _abrir_tela()
    at.selectbox(key="eq_comprimento").set_value("mm").run()
    assert not at.exception
    assert at.session_state["eq_dados"]["apoios"][1]["x"] == pytest.approx(4000.0)


def test_sair_para_outro_caso_e_voltar_nao_troca_a_unidade():
    """O seletor não desenhado perde o estado: 1,5 m não pode virar 1,5 mm na volta."""
    at = _abrir_tela()
    assert at.session_state["eq_comprimento"] == "m"
    reacoes = [m.value for m in at.markdown if "Maior reação" in m.value]
    at.switch_page("app_pages/assistente_cargas.py")
    at.run()
    at.switch_page("app_pages/vigas_eixos.py")
    at.run()
    assert not at.exception
    assert at.selectbox(key="eq_comprimento").value == "m"
    assert at.selectbox(key="eq_forca").value == "kN"
    assert at.selectbox(key="eq_modelo").value == MODELOS[0].nome
    assert at.session_state["eq_dados"]["apoios"][1]["x"] == pytest.approx(4.0)
    assert reacoes == [m.value for m in at.markdown if "Maior reação" in m.value]


def test_unidade_trocada_continua_valendo_na_volta():
    at = _abrir_tela()
    at.selectbox(key="eq_comprimento").set_value("mm").run()
    at.switch_page("app_pages/assistente_cargas.py")
    at.run()
    at.switch_page("app_pages/vigas_eixos.py")
    at.run()
    assert at.selectbox(key="eq_comprimento").value == "mm"
    assert at.session_state["eq_dados"]["apoios"][1]["x"] == pytest.approx(4000.0)


def test_limpar_avisa_o_que_falta_sem_quebrar():
    at = _abrir_tela()
    at.button(key="eq_limpar").click().run()
    assert not at.exception
    assert any("apoio" in i.value for i in at.info)


def test_todo_campo_da_tela_tem_ajuda():
    at = _abrir_tela()
    for chave in ("eq_modelo", "eq_comprimento", "eq_forca"):
        assert at.selectbox(key=chave).help


def _estado(dados):
    from components import equilibrio_ui as ui

    return {
        ui.DADOS: dados,
        ui.VERSAO: 3,
        ui.AJUSTE: 0,
        ui.REVISAO: 2,
        ui.BASES: {nome: [dict(x) for x in dados[nome]] for nome, _ in ui.TABELAS},
        ui.MODELO_ATUAL: MODELOS[0].nome,
        ui.ERRO_TABELA: "",
    }


def test_edicao_na_tabela_vale_sobre_a_base_e_da_nome():
    from components import equilibrio_ui as ui

    estado = _estado(MODELOS[0].dados())
    estado["eq_tabela_apoios_2"] = {
        "edited_rows": {"1": {"x": 5.0}},
        "added_rows": [{"tipo": eq.ROLETE, "x": 2.0, "y": 0.0, "angulo": 90.0}],
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_tabela(CASO, "apoios")
    apoios = estado[ui.DADOS]["apoios"]
    assert apoios[1]["x"] == 5.0
    assert apoios[2]["nome"] == "C"
    assert estado[ui.REVISAO] == 2  # a chave fica: o editor guarda as mudanças sobre ela
    assert estado[ui.MODELO_ATUAL] is None


def test_edicao_ruim_na_tabela_avisa_e_nao_mexe_no_desenho():
    from components import equilibrio_ui as ui

    estado = _estado(MODELOS[0].dados())
    antes = [dict(a) for a in estado[ui.DADOS]["apoios"]]
    estado["eq_tabela_apoios_2"] = {"edited_rows": {"1": {"tipo": "Parafuso"}}}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_tabela(CASO, "apoios")
    assert estado[ui.ERRO_TABELA]
    assert estado[ui.DADOS]["apoios"] == antes


def test_gesto_na_prancheta_entra_e_troca_a_base_das_tabelas():
    from components import equilibrio_ui as ui

    estado = _estado(MODELOS[0].dados())
    novos = MODELOS[1].dados()
    estado[ui.CHAVE_PRANCHETA] = mock.Mock(edicao={"dados": novos, "versao": 9})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_na_prancheta()
    assert estado[ui.DADOS]["apoios"] == novos["apoios"]
    assert estado[ui.VERSAO] == 9
    assert estado[ui.REVISAO] == 3


def test_gesto_incompleto_nao_derruba():
    from components import equilibrio_ui as ui

    dados = MODELOS[0].dados()
    estado = _estado(dados)
    estado[ui.CHAVE_PRANCHETA] = mock.Mock(edicao={"dados": {"apoios": []}, "versao": 9})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_na_prancheta()
    assert estado[ui.DADOS] == dados
