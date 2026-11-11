"""Ajustes e tolerâncias: os números da NBR 6158 e a página."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import ajustes_e_tolerancias as at
from core import elementos_eixos as ee

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGINA = "app_pages/ajustes_e_tolerancias.py"


# ---------------------------------------------------------------------------
# Tabela 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("grau", "d", "it"),
    [
        (7, 25, 21),
        (6, 50, 16),
        (11, 40, 160),
        (1, 2, 0.8),
        (18, 500, 9700),
        (12, 18, 180),  # a norma dá IT12 a IT18 em mm: 0,18 mm
        (8, 3, 14),  # 3 mm ainda é a primeira faixa ("até e inclusive")
        (8, 3.01, 18),
    ],
)
def test_graus_de_tolerancia_da_tabela_1(grau, d, it):
    assert at.tolerancia(grau, d) == it


def test_delta_e_a_diferenca_de_dois_graus_e_zero_ate_3_mm():
    # Tabela 3, faixa 18 a 30: IT3 1,5; IT4 2; IT5 3; IT6 4; IT7 8; IT8 12.
    assert [at.delta(g, 25) for g in range(3, 9)] == [1.5, 2, 3, 4, 8, 12]
    assert at.delta(7, 2) == 0.0


# ---------------------------------------------------------------------------
# Tabelas 2 e 3, conferidas nas tabelas de afastamentos limites
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "d", "superior", "inferior"),
    [
        ("H7", 25, 21, 0),
        ("h6", 40, 0, -16),
        ("g6", 25, -7, -20),
        ("f7", 25, -20, -41),
        ("e8", 40, -50, -89),
        ("d9", 50, -80, -142),
        ("c11", 40, -120, -280),
        ("k6", 25, 15, 2),
        ("k6", 2, 6, 0),
        ("n6", 25, 28, 15),
        ("p6", 25, 35, 22),
        ("s6", 25, 48, 35),
        ("t6", 50, 70, 54),
        ("u6", 25, 61, 48),
        ("js7", 25, 10.5, -10.5),  # Tabela 32: sem arredondar
        ("H11", 40, 160, 0),
        ("C11", 40, 280, 120),
        ("D9", 50, 142, 80),
        ("F8", 40, 64, 25),
        ("G7", 40, 34, 9),
        ("JS7", 25, 10.5, -10.5),
        ("K6", 40, 3, -13),
        ("K7", 25, 6, -15),  # exemplo da nota C da Tabela 3
        ("M7", 40, 0, -25),
        ("M8", 3, -2, -16),
        ("M6", 280, -9, -41),  # caso especial da nota D da Tabela 3
        ("N7", 25, -7, -28),
        ("N9", 40, 0, -62),
        ("P7", 25, -14, -35),
        ("S6", 25, -31, -44),  # exemplo da nota C da Tabela 3
        ("S7", 25, -27, -48),
        ("T7", 50, -45, -70),
        ("U7", 40, -51, -76),
        ("U7", 45, -61, -86),
        # Tabela 18 (M e N, 3 a 6 mm), Tabela 22 (U) e Tabela 37 (s), lidas no PDF da norma.
        ("M3", 5, -3, -5.5),
        ("M4", 5, -2.5, -6.5),
        ("M6", 5, -1, -9),
        ("M9", 5, -4, -34),
        ("N3", 5, -7, -9.5),
        ("N10", 5, 0, -48),
        ("U5", 2, -18, -22),
        ("U6", 5, -20, -28),
        ("U8", 5, -23, -41),
        ("s3", 5, 21.5, 19),
    ],
)
def test_afastamentos_limites(nome, d, superior, inferior):
    z = at.zona(nome, d)
    assert (z.superior, z.inferior) == (superior, inferior)


@pytest.mark.parametrize("d", [1, 3, 4, 10, 14, 18, 30, 50, 65, 100, 180, 250, 315, 400, 500])
def test_h_do_furo_e_do_eixo_sao_o_it(d):
    for grau in at.GRAUS:
        if grau >= 14 and d <= 1:
            continue
        assert at.zona(f"H{grau}", d).inferior == 0
        assert at.zona(f"H{grau}", d).tolerancia == at.tolerancia(grau, d)
        assert at.zona(f"h{grau}", d).superior == 0


@pytest.mark.parametrize("letra", ["p", "r", "s", "u"])
def test_mesmos_numeros_que_o_assistente_de_cargas(letra):
    nome = next(n for n in ee.AJUSTES if n.startswith(f"H7/{letra}6"))
    for d in (2, 3, 6, 10, 14, 16, 18, 24, 30, 45, 65, 100, 140, 200, 280, 355, 450, 500):
        a = at.ajuste(d, "H7", f"{letra}6")
        assert (a.interferencia_minima, a.interferencia_maxima) == ee.interferencia_do_ajuste(
            d, nome
        )


def test_zero_sem_sinal():
    assert str(at.zona("H7", 25).inferior) == "0.0"
    assert at.cota_do_desenho(at.zona("H7", 50)) == "Ø50 H7 (+0,025 / 0)"
    assert at.cota_do_desenho(at.zona("s6", 50)) == "Ø50 s6 (+0,059 / +0,043)"


# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------


def test_tipos_de_ajuste():
    assert at.ajuste_pelo_nome(30, "H7/g6").tipo == at.COM_FOLGA
    assert at.ajuste_pelo_nome(30, "H7/k6").tipo == at.INCERTO
    assert at.ajuste_pelo_nome(30, "H7/s6").tipo == at.COM_INTERFERENCIA
    h7h6 = at.ajuste_pelo_nome(30, "H7/h6")
    assert h7h6.tipo == at.COM_FOLGA and h7h6.folga_minima == 0


def test_folga_e_interferencia():
    a = at.ajuste_pelo_nome(50, "H7/s6")
    assert (a.interferencia_minima, a.interferencia_maxima) == (18, 59)
    assert a.sistema == "Furo-base"
    assert at.ajuste_pelo_nome(50, "S7/h6").sistema == "Eixo-base"


@pytest.mark.parametrize(
    ("entrada", "trecho"),
    [
        ("H7/zz6", "não está nesta página"),
        ("H7", "furo/eixo"),
        ("h7/s6", "letra maiúscula"),
        ("H7/S6", "letra minúscula"),
        ("H19/s6", "IT1 a IT18"),
        ("H7/t6", "acima de 24 mm"),
    ],
)
def test_entrada_ruim_explica(entrada, trecho):
    with pytest.raises(at.ErroDeAjuste, match=trecho):
        at.ajuste_pelo_nome(20, entrada)


@pytest.mark.parametrize("d", [0, -5, 600, float("nan"), float("inf")])
def test_diametro_fora_explica(d):
    with pytest.raises(at.ErroDeAjuste):
        at.zona("H7", d)


def test_k_acima_de_it8_nao_existe_acima_de_3_mm():
    with pytest.raises(at.ErroDeAjuste, match="até IT8"):
        at.zona("K9", 20)
    assert at.zona("K9", 2).superior == 0


def test_recomendados_sem_t_abaixo_de_24_mm():
    assert len(at.recomendados(50)) == len(at.RECOMENDADOS)
    assert all(a.tipo for a in at.recomendados(10))


def test_toda_classe_da_pagina_tem_numero_em_toda_faixa():
    """Nenhuma combinação da tela quebra: ou dá número, ou explica com ErroDeAjuste."""
    for d in (0.5, 1, 2, 3, 5, 8, 12, 15, 20, 26, 35, 45, 60, 75, 90, 110, 130, 150, 170, 190,
              210, 240, 260, 300, 340, 380, 420, 480, 500):  # fmt: skip
        for letra in (*at.LETRAS_DE_FURO, *at.LETRAS_DE_EIXO):
            for grau in at.GRAUS:
                try:
                    z = at.zona(f"{letra}{grau}", d)
                except at.ErroDeAjuste:
                    continue
                assert z.superior > z.inferior
                assert z.tolerancia == pytest.approx(at.tolerancia(grau, d))


# ---------------------------------------------------------------------------
# Aperto e escolha
# ---------------------------------------------------------------------------


def test_aperto_usa_a_interferencia_do_ajuste():
    a = at.ajuste_pelo_nome(50, "H7/u6")
    r = at.aperto(a, {})
    interferencia = {m.rotulo: m.valor for m in r.metricas}
    assert interferencia["Interferência mínima"] == a.interferencia_minima
    assert interferencia["Interferência máxima"] == a.interferencia_maxima


def test_aperto_de_ajuste_com_folga_ou_incerto_explica():
    with pytest.raises(at.ErroDeAjuste, match="não tem interferência"):
        at.aperto(at.ajuste_pelo_nome(50, "H7/g6"), {})
    with pytest.raises(at.ErroDeAjuste, match="incerto"):
        at.aperto(at.ajuste_pelo_nome(50, "H7/n6"), {})


def test_escolher_acha_o_mais_leve_que_segura():
    escolhas = at.escolher(50, {"torque_Nm": 300.0})
    melhor = at.melhor_que_segura(escolhas)
    assert melhor is not None
    leves = [
        e
        for e in escolhas
        if e.transmite
        and e.escoa is False
        and e.ajuste.interferencia_maxima < melhor.ajuste.interferencia_maxima
    ]
    assert not leves
    # Com folga não se aplica.
    assert next(e for e in escolhas if e.ajuste.nome == "H7/g6").transmite is None


def test_escolher_sem_dados_do_aperto_so_lista():
    escolhas = at.escolher(50)
    assert all(e.transmite is None for e in escolhas)
    assert at.melhor_que_segura(escolhas) is None


def test_registro_tem_o_ajuste_e_o_aperto():
    a = at.ajuste_pelo_nome(50, "H7/u6")
    r = at.aperto(a, {})
    registro = at.registro(a, r, at.PADROES_DO_APERTO)
    assert registro["titulo"] == "Ajuste Ø50 H7/u6"
    assert "45 a 86 µm" in registro["resumo"]
    assert "." not in registro["resumo"].split("pressão de ")[1].split(" MPa")[0]
    so_ajuste = at.registro(at.ajuste_pelo_nome(30, "H7/g6"))
    assert so_ajuste["status"] == "Atende"


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------


def abrir() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA).run()
    assert not teste.exception, [e.value for e in teste.exception]
    return teste


def test_pagina_abre_com_o_ajuste_padrao():
    t = abrir()
    assert any("Ø50 H7/s6: ajuste com interferência, de 18 a 59 µm." in i.value for i in t.info)
    rotulos = [tab.label for tab in t.tabs]
    assert {
        "Furo e eixo",
        "Cadeia de cotas",
        "Ajuste",
        "Aperto e montagem",
        "Escolher o ajuste",
    } <= set(rotulos)
    for widget in (*t.number_input, *t.selectbox, *t.radio, *t.toggle):
        assert widget.help and widget.help.strip()[-1] in ".!:", widget.label


def test_pagina_com_classes_a_mao_e_ajuste_com_folga():
    t = abrir()
    t.radio(key="aj_modo").set_value("Escolher as classes").run()
    t.selectbox(key="aj_eixo_letra").set_value("g").run()
    assert not t.exception
    assert any("ajuste com folga" in s.value for s in t.success)
    assert any("não tem interferência garantida" in i.value for i in t.info)


def test_pagina_com_classe_que_nao_existe_explica():
    t = abrir()
    t.radio(key="aj_modo").set_value("Escolher as classes").run()
    t.selectbox(key="aj_eixo_letra").set_value("t").run()
    t.number_input(key="aj_d").set_value(10.0).run()
    assert not t.exception
    assert any("acima de 24 mm" in w.value for w in t.warning)


def test_usar_o_ajuste_que_segura():
    t = abrir()
    t.number_input(key="aj_ap_torque_Nm").set_value(300.0).run()
    botao = t.button(key="aj_usar_melhor")
    nome = botao.label.removeprefix("Usar ")
    botao.click().run()
    assert not t.exception
    assert t.session_state["aj_recomendado"] == nome


@pytest.mark.parametrize(
    ("valor", "casas", "texto"),
    [
        (190.0, 0, "190"),
        (189.6, 0, "190"),
        (100.0, 1, "100"),
        (50.025, 4, "50,025"),
        (-0.0, 1, "0"),
    ],
)
def test_numero_sem_comer_os_zeros_do_inteiro(valor, casas, texto):
    assert at.numero(valor, casas) == texto
