"""Busca em faixas do montador: várias incógnitas, contra contas de mão."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_blocos as mb
from core import montador_busca as bs

APP = str(Path(__file__).resolve().parents[1] / "app.py")
LIMITE = bs.Objetivo("Todas as condições no limite", bs.NO_LIMITE)
AREA = bs.Objetivo("Menor área da seção", bs.MENOR_AREA)


def montar(*itens) -> mt.Montagem:
    nos = []
    for i, item in enumerate(itens):
        tipo, opcoes = item if isinstance(item, tuple) else (item, {})
        nos.append({"id": f"n{i}", "tipo": tipo, "opcoes": opcoes})
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(
            {"de": a["id"], "saida": saida.chave, "para": b["id"], "entrada": entrada.chave}
        )
    return mt.montar(mt.grafo_de_dados({"nos": nos, "fios": fios}))


RET = ("retangular", "flexao", "cortante", "von_mises", mb.RESULTADO)
SO_FLEXAO = ("retangular", "flexao", "von_mises", mb.RESULTADO)
VALORES = {"M_x": 2e6, "V_y": 1e5, "S_y": 250.0, "n": 1.0}


def test_todas_as_condicoes_no_limite_e_um_ponto_so():
    """Duas incógnitas e duas condições: fibra e linha neutra em 100 % ao mesmo tempo."""
    b = bs.procurar(
        montar(*RET),
        [bs.Faixa("b", 5.0, 200.0, 5.0), bs.Faixa("h", 5.0, 300.0, 5.0)],
        LIMITE,
        VALORES,
    )
    s = 250.0
    # 6·M/(b·h²) = S e √3·1,5·V/(b·h) = S.
    area = 1.5 * math.sqrt(3) * 1e5 / s
    h = (6 * 2e6 / s) / area
    assert b.convergido.valor("h") == pytest.approx(h, rel=1e-3)
    assert b.convergido.valor("b") == pytest.approx(area / h, rel=1e-3)
    assert all(u == pytest.approx(1.0, abs=2e-3) for u in b.convergido.usos)
    assert b.rodadas[-1].meia_largura < 1e-6


def test_menor_area_com_duas_incognitas_vai_para_a_borda_da_altura():
    """Só flexão: área = b·h com b·h² fixo, então a maior altura ganha."""
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("b", 1.0, 100.0, 1.0), bs.Faixa("h", 10.0, 200.0, 10.0)],
        AREA,
        {"M_x": 2e6, "S_y": 250.0, "n": 1.0},
    )
    k = 6 * 2e6 / 250
    assert b.convergido.valor("h") == pytest.approx(200.0)
    assert b.convergido.valor("b") == pytest.approx(k / 200**2, rel=1e-4)
    assert b.convergido.uso == pytest.approx(1.0, abs=1e-4)
    assert b.na_borda == ("h",)


def test_grade_respeita_o_passo_e_o_refino_sai_dele():
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("b", 10.0, 100.0, 10.0), bs.Faixa("h", 10.0, 200.0, 10.0)],
        AREA,
        {"M_x": 2e6, "S_y": 250.0, "n": 1.0},
    )
    grade = b.melhores_da_grade[0]
    assert grade.valor("b") % 10 == pytest.approx(0.0)
    assert grade.valor("h") % 10 == pytest.approx(0.0)
    assert grade.uso <= 1.0
    assert b.convergido.area <= grade.area


def test_tres_incognitas_no_perfil_i():
    m = montar("perfil_i", "flexao", "cortante", "von_mises", mb.RESULTADO)
    b = bs.procurar(
        m,
        [
            bs.Faixa("b_f", 50.0, 200.0, 10.0),
            bs.Faixa("h", 100.0, 400.0, 20.0),
            bs.Faixa("t_w", 4.0, 16.0, 2.0),
        ],
        AREA,
        {"t_f": 10.0, "M_x": 5e7, "V_y": 1e5, "S_y": 250.0, "n": 1.5},
    )
    final = b.convergido
    assert final.uso == pytest.approx(1.0, abs=1e-3)
    assert final.area <= b.melhores_da_grade[0].area
    assert len(final.valores) == 3
    # Confere com o motor de uma letra só: com b_f e t_w achados, a altura fecha a mesma conta.
    r = mt.isolar(
        m,
        "h",
        {
            "b_f": final.valor("b_f"),
            "t_w": final.valor("t_w"),
            "t_f": 10.0,
            "M_x": 5e7,
            "V_y": 1e5,
            "S_y": 250.0,
            "n": 1.5,
        },
    )
    assert r.valor == pytest.approx(final.valor("h"), rel=1e-3)


def test_maior_forca_com_as_medidas_na_faixa():
    m = montar("retangular", ("flexao", {"entrada": mb.FORCA_BRACO}), "von_mises", mb.RESULTADO)
    objetivo = bs.Objetivo("Maior F_xx", bs.MAIOR, "F_xx")
    b = bs.procurar(
        m,
        [
            bs.Faixa("F_xx", 1e3, 5e4, 1e3),
            bs.Faixa("b", 20.0, 50.0, 5.0),
            bs.Faixa("h", 40.0, 100.0, 10.0),
        ],
        objetivo,
        {"d_xx": 500.0, "S_y": 250.0, "n": 1.0},
    )
    # Maior seção da faixa: b = 50, h = 100.
    esperado = 250 * 50 * 100**2 / 6 / 500
    assert b.convergido.valor("F_xx") == pytest.approx(esperado, rel=1e-3)
    assert b.convergido.valor("h") == pytest.approx(100.0)


def test_menor_valor_de_uma_letra():
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("h", 10.0, 200.0, 10.0)],
        bs.Objetivo("Menor h", bs.MENOR, "h"),
        {"b": 50.0, "M_x": 2e6, "S_y": 250.0, "n": 1.0},
    )
    assert b.convergido.valor("h") == pytest.approx(math.sqrt(6 * 2e6 / (50 * 250)), rel=1e-5)


def test_uma_incognita_bate_com_o_isolamento():
    m = montar("circular", "flexao", "normal", "torcao", "von_mises", mb.RESULTADO)
    valores = {"M_x": 1e6, "N": 1e5, "T": 5e5, "S_y": 300.0, "n": 2.0}
    direto = mt.isolar(m, "d", valores).valor
    b = bs.procurar(
        m, [bs.Faixa("d", 5.0, 200.0, 5.0)], bs.Objetivo("Menor d", bs.MENOR, "d"), valores
    )
    assert b.convergido.valor("d") == pytest.approx(direto, rel=1e-5)


def test_nenhuma_combinacao_passa_diz_a_melhor():
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("b", 2.0, 4.0, 1.0), bs.Faixa("h", 2.0, 4.0, 1.0)],
        AREA,
        {"M_x": 2e8, "S_y": 250.0, "n": 1.0},
    )
    assert b.convergido is None
    assert b.aprovadas == 0
    assert any("Amplie a faixa" in a for a in b.alertas)


def test_mais_incognitas_que_condicoes_avisa():
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("b", 10.0, 100.0, 10.0), bs.Faixa("h", 10.0, 200.0, 10.0)],
        LIMITE,
        {"M_x": 2e6, "S_y": 250.0, "n": 1.0},
    )
    assert any("família" in a for a in b.alertas)


def test_validade_da_secao_tira_a_combinacao_impossivel():
    """Tubo com parede maior que o raio não existe: fica de fora, sem dar erro."""
    m = montar("tubo_parede", "flexao", "von_mises", mb.RESULTADO)
    b = bs.procurar(
        m,
        [bs.Faixa("d", 10.0, 100.0, 5.0), bs.Faixa("t", 1.0, 60.0, 1.0)],
        AREA,
        {"M_x": 1e6, "S_y": 250.0, "n": 1.0},
    )
    assert b.convergido.valor("d") > 2 * b.convergido.valor("t")


def test_condicao_que_nao_depende_e_nao_passa_avisa():
    b = bs.procurar(
        montar(*RET),
        [bs.Faixa("M_x", 1e5, 1e6, 1e5)],
        bs.Objetivo("Maior M_x", bs.MAIOR, "M_x"),
        {"b": 1.0, "h": 2.0, "V_y": 1e6, "S_y": 250.0, "n": 1.0},
    )
    assert any("não mudam isso" in a for a in b.alertas)


def test_faltando_valor_diz_qual():
    with pytest.raises(bs.ErroDeBusca, match="Preencha V_y"):
        bs.procurar(
            montar(*RET),
            [bs.Faixa("b", 10.0, 100.0, 10.0)],
            bs.Objetivo("Menor b", bs.MENOR, "b"),
            {"M_x": 2e6, "h": 100.0, "S_y": 250.0, "n": 1.0},
        )


def test_faixa_grande_demais_pede_passo_maior():
    with pytest.raises(bs.ErroDeBusca, match="aumente o passo"):
        bs.procurar(
            montar(*SO_FLEXAO),
            [bs.Faixa("b", 1.0, 1000.0, 1.0), bs.Faixa("h", 1.0, 1000.0, 1.0)],
            AREA,
            {"M_x": 2e6, "S_y": 250.0, "n": 1.0},
        )


def test_faixa_ao_contrario_explica():
    with pytest.raises(bs.ErroDeBusca, match="precisa subir"):
        bs.Faixa("b", 10.0, 5.0, 1.0)
        bs.procurar(
            montar(*SO_FLEXAO),
            [bs.Faixa("b", 10.0, 5.0, 1.0)],
            bs.Objetivo("Menor b", bs.MENOR, "b"),
            {"h": 10.0, "M_x": 2e6, "S_y": 250.0, "n": 1.0},
        )


def test_objetivos_dependem_das_incognitas():
    m = montar(*SO_FLEXAO)
    so_carga = bs.objetivos(m, ["M_x"])
    assert all(o.tipo != bs.MENOR_AREA for o in so_carga)
    com_medida = bs.objetivos(m, ["b", "h"])
    assert com_medida[0].tipo == bs.MENOR_AREA
    assert any(o.rotulo == "Maior h" for o in com_medida)


def test_mapa_tem_duas_incognitas_e_uso():
    b = bs.procurar(
        montar(*SO_FLEXAO),
        [bs.Faixa("b", 10.0, 100.0, 10.0), bs.Faixa("h", 10.0, 200.0, 10.0)],
        AREA,
        {"M_x": 2e6, "S_y": 250.0, "n": 1.0},
    )
    assert len(b.mapa[0]) == 3
    assert len(b.mapa) > 1000


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page("app_pages/montador_formulas.py").run()
    at.toggle(key="mf_busca_ligada").set_value(True).run()
    assert not at.exception
    return at


def test_ligar_a_busca_acha_o_ponto():
    at = abrir()
    assert any("Ponto de convergência" in s.value for s in at.success)


def test_duas_incognitas_na_tela():
    at = abrir()
    at.multiselect(key="mf_busca_letras").set_value(["b", "h"]).run()
    assert not at.exception
    assert any("Ponto de convergência" in s.value for s in at.success)
    assert any(s.value.count("mm") >= 2 for s in at.success)


def test_textos_da_busca_em_portugues():
    at = abrir()
    assert any(", e " in c.value and "passaram" in c.value for c in at.caption)
    assert any("Uso de 100 %" in s.value for s in at.success)


def test_trocar_o_objetivo_na_tela():
    at = abrir()
    at.multiselect(key="mf_busca_letras").set_value(["b", "h"]).run()
    at.selectbox(key="mf_busca_objetivo").set_value("Todas as condições no limite").run()
    assert not at.exception
    assert any("Ponto de convergência" in s.value for s in at.success)
