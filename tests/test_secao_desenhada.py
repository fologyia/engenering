"""Desenhar seção: contas contra soluções exatas, reconhecimento e uso no resto do programa."""

from __future__ import annotations

import math
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

from core import column_buckling as cb
from core import preferencias_menu as pm
from core import secao_desenhada as sd
from core import secao_relatorio as sr
from core import section_catalog as catalogo
from core import steel_sections as ss
from core.beam_sections import secao_de_perfil_catalogo
from core.desenho_estatica import figura_das_partes, figura_de_tensoes
from core.elementos_word import gerar_word_do_caso

R, C, P = sd.RET, sd.CIRC, sd.POLI
APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGINA = "app_pages/desenhar_secao.py"


def _abrir_pagina() -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=120)
    teste.run()
    teste.switch_page(PAGINA)
    return teste.run()


def _ret(x, y, b, h, **extra):
    return sd.Parte(R, x, y, b, h, **extra)


def _prop(partes):
    return sd.analisar(partes).prop


@pytest.mark.parametrize(
    ("razao", "k"),
    [(1, 0.14058), (2, 0.22873), (5, 0.29157), (10, 0.31233)],
)
def test_retangulo_bate_com_a_serie_de_saint_venant(razao, k):
    b, h = 100.0 * razao, 100.0
    p = _prop([_ret(0, 0, b, h)])
    assert p.area == pytest.approx(b * h)
    assert p.ix == pytest.approx(b * h**3 / 12)
    assert p.iy == pytest.approx(h * b**3 / 12)
    assert p.zx == pytest.approx(b * h**2 / 4)
    assert p.j == pytest.approx(k * b * h**3, rel=0.005)
    assert p.x_s == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("parede", [20.0, 6.0, 3.0])
def test_tubo_redondo_de_parede_fina_ou_grossa(parede):
    d, furo = 200.0, 200.0 - 2 * parede
    p = _prop([sd.Parte(C, 0, 0, d, d), sd.Parte(C, 0, 0, furo, furo, furo=True)])
    assert p.area == pytest.approx(math.pi * (d**2 - furo**2) / 4, rel=0.002)
    assert p.ix == pytest.approx(math.pi * (d**4 - furo**4) / 64, rel=0.002)
    assert p.j == pytest.approx(math.pi * (d**4 - furo**4) / 32, rel=0.002)
    assert p.zx == pytest.approx((d**3 - furo**3) / 6, rel=0.002)
    assert p.cw == 0.0


def test_barra_redonda():
    d = 100.0
    p = _prop([sd.Parte(C, 0, 0, d, d)])
    assert p.j == pytest.approx(math.pi * d**4 / 32, rel=0.001)
    assert p.zx == pytest.approx(d**3 / 6, rel=0.001)


def test_tubo_retangular_fino_bate_com_bredt():
    b, h, t = 300.0, 200.0, 3.0
    p = _prop(sd.partes_do_modelo("tubo_ret", {"b": b, "h": h, "t": t, "r": 0.0}))
    area_media = (b - t) * (h - t)
    perimetro = 2 * ((b - t) + (h - t))
    assert p.j == pytest.approx(4 * area_media**2 * t / perimetro, rel=0.01)


def test_i_bate_com_o_perfil_de_fabrica_do_programa():
    d, bf, tw, tf = 300.0, 150.0, 8.0, 12.0
    p = _prop(sd.partes_do_modelo("i", {"d": d, "bf": bf, "tf": tf, "tw": tw}))
    fabrica = ss.perfil_i_simetrico("I", d, bf, tw, tf)
    assert p.area == pytest.approx(fabrica.area_mm2)
    assert p.ix == pytest.approx(fabrica.ix_mm4)
    assert p.iy == pytest.approx(fabrica.iy_mm4)
    assert p.zx == pytest.approx(fabrica.zx_mm3)
    assert p.cw == pytest.approx(tf * bf**3 / 12 * (d - tf) ** 2 / 2, rel=0.01)
    assert (p.x_s, p.y_s) == pytest.approx((0.0, 0.0), abs=1e-6)


def test_centro_de_cisalhamento_e_cw_do_u_batem_com_a_parede_fina():
    d, bf, tf, tw = 300.0, 100.0, 10.0, 8.0
    p = _prop(sd.partes_do_modelo("u", {"d": d, "bf": bf, "tf": tf, "tw": tw}))
    b_m, h_m = bf - tw / 2, d - tf
    e = 3 * b_m**2 * tf / (6 * b_m * tf + h_m * tw)
    dorso = p.xc - p.x0
    assert p.x_s == pytest.approx(-(e + dorso - tw / 2), abs=1.0)
    cw = tf * b_m**3 * h_m**2 / 12 * (3 * b_m * tf + 2 * h_m * tw) / (6 * b_m * tf + h_m * tw)
    assert p.cw == pytest.approx(cw, rel=0.02)


def test_centro_de_cisalhamento_do_t_fica_no_encontro_da_mesa_com_a_alma():
    d, bf, tf = 200.0, 150.0, 12.0
    p = _prop(sd.partes_do_modelo("t", {"d": d, "bf": bf, "tf": tf, "tw": 8.0}))
    assert p.yc + p.y_s == pytest.approx(d / 2 - tf / 2, abs=1.0)


def test_parte_sobre_parte_conta_uma_vez_e_furo_tira_de_tudo():
    chapa = _ret(0, 0, 100, 10)
    assert _prop([chapa, chapa]).area == pytest.approx(1000.0)
    assert _prop([chapa, _ret(30, 0, 40, 10)]).area == pytest.approx(1000.0)
    assert _prop([chapa, _ret(40, 0, 40, 10)]).area == pytest.approx(1100.0)  # sobra 10 mm fora
    furada = _prop([chapa, _ret(0, 0, 20, 10, furo=True)])
    assert furada.area == pytest.approx(800.0)
    assert furada.ix == pytest.approx(80 * 10**3 / 12)
    assert _prop([chapa, _ret(0, 0, 10, 10, furo=True), _ret(0, 0, 10, 10, furo=True)]).area == (
        pytest.approx(900.0)
    )


def test_a_posicao_no_desenho_nao_muda_as_propriedades():
    base = sd.partes_do_modelo("u", {"d": 200, "bf": 80, "tf": 9, "tw": 6})
    p0 = _prop(base)
    p1 = _prop([sd.mover(parte, 137.0, -420.0) for parte in base])
    assert p1.xc == pytest.approx(p0.xc + 137.0)
    assert p1.yc == pytest.approx(p0.yc - 420.0)
    for campo in ("area", "ix", "iy", "zx", "zy", "j", "cw", "x_s", "y_s"):
        assert getattr(p1, campo) == pytest.approx(getattr(p0, campo), rel=1e-6, abs=1e-6), campo


def test_retangulo_inclinado_e_poligono_dao_a_mesma_conta():
    giro = _prop([_ret(0, 0, 200, 20, giro=30.0)])
    assert giro.area == pytest.approx(4000.0, rel=0.003)
    assert giro.i2 == pytest.approx(200 * 20**3 / 12, rel=0.02)
    # O eixo de maior inércia é o que cruza a chapa: 30° − 90°.
    assert giro.angulo == pytest.approx(-60.0, abs=0.5)
    cantoneira = _prop(sd.partes_do_modelo("l", {"a": 100, "b": 100, "t": 10}))
    assert cantoneira.angulo == pytest.approx(45.0, abs=0.01)  # passa pelo canto da cantoneira
    poligono = sd.Parte(P, pontos=((0, 0), (100, 0), (100, 50), (0, 50)))
    assert poligono.reta
    assert _prop([poligono]).ix == pytest.approx(100 * 50**3 / 12)
    triangulo = sd.Parte(P, pontos=((0, 0), (120, 0), (0, 90)))
    assert _prop([triangulo]).ix == pytest.approx(120 * 90**3 / 36, rel=0.005)


def test_medidas_validas_em_todo_modelo_formam_uma_secao():
    for modelo in sd.MODELOS:
        valores = {m.chave: m.padrao for m in modelo.medidas}
        partes = sd.partes_do_modelo(modelo.id, valores)
        analise = sd.analisar(partes)
        esperados = 2 if modelo.id == "dois_l_t" else 1  # 2 L com folga: ligadas por espaçadores
        assert analise.prop.pedacos == esperados, modelo.id
        assert analise.prop.j > 0.0, modelo.id


@pytest.mark.parametrize(
    ("modelo", "tipo", "familia"),
    [
        ("i", "I", "i"),
        ("u", "U", "u"),
        ("t", "T", "t"),
        ("caixao", "caixao", "tubo"),
        ("tubo_circ", "tubo_circ", "tubo"),
        ("barra_circ", "barra_circ", "barra"),
        ("chapa", "barra_ret", "barra"),
        ("c_enrijecido", "c", "c"),
    ],
)
def test_forma_reconhecida_entra_na_familia_certa(modelo, tipo, familia):
    forma = sd.reconhecer(
        sd.partes_do_modelo(modelo, {m.chave: m.padrao for m in _medidas(modelo)})
    )
    assert forma.tipo == tipo
    assert ss.familia_do_perfil(mock.Mock(familia=forma.familia)) == familia


def _medidas(modelo_id):
    return sd.MODELOS_POR_ID[modelo_id].medidas


def test_chapas_soltas_viram_i_e_assimetria_nao_vira():
    d, bf, tf, tw = 300.0, 150.0, 12.0, 8.0
    desenhado = [
        _ret(0, 0, tw, d - 2 * tf),
        _ret(0, (d - tf) / 2, bf, tf),
        _ret(0, -(d - tf) / 2, bf, tf),
    ]
    forma = sd.reconhecer(desenhado)
    assert (forma.tipo, forma.d, forma.bf, forma.tf, forma.tw) == ("I", d, bf, tf, tw)
    # Uma I de mesas diferentes cairia em Wx = Ix/(d/2) e daria M_Rd maior que o real.
    assert (
        sd.reconhecer(
            sd.partes_do_modelo(
                "i_assimetrico", {"d": 300, "bs": 200, "ts": 16, "bi": 120, "ti": 10, "tw": 8}
            )
        ).tipo
        == "livre"
    )
    deslocada = [*desenhado[:1], _ret(10, (d - tf) / 2, bf, tf), desenhado[2]]
    assert sd.reconhecer(deslocada).tipo == "livre"


def test_u_espelhado_e_t_invertido_vao_ao_catalogo_na_posicao_de_referencia():
    u = sd.partes_do_modelo("u", {"d": 200, "bf": 80, "tf": 9, "tw": 6})
    espelhado = [sd.Parte(R, -p.x, p.y, p.b, p.h, grupo=1) for p in u]
    dados_u = sd.perfil_da_secao("U", sd.analisar(u))
    dados_e = sd.perfil_da_secao("E", sd.analisar(espelhado))
    assert dados_e["centroide_x_mm"] == pytest.approx(dados_u["centroide_x_mm"])
    assert dados_e["x0_mm"] == pytest.approx(dados_u["x0_mm"])

    t = sd.partes_do_modelo("t", {"d": 200, "bf": 150, "tf": 12, "tw": 8})
    invertido = [sd.Parte(R, p.x, -p.y, p.b, p.h, grupo=1) for p in t]
    dados_t = sd.perfil_da_secao("T", sd.analisar(t))
    dados_i = sd.perfil_da_secao("I", sd.analisar(invertido))
    assert dados_i["centroide_y_mm"] == pytest.approx(dados_t["centroide_y_mm"])


def test_pedacos_soltos_sao_avisados_e_nao_vao_ao_catalogo():
    analise = sd.analisar([_ret(0, 0, 100, 10), _ret(0, 20, 100, 10)])
    assert analise.prop.pedacos == 2
    alertas = " ".join(sd.alertas_da_secao(analise, sd.reconhecer(analise.partes)))
    assert "soltos" in alertas
    with pytest.raises(sd.ErroDeSecao, match="soltos"):
        sd.perfil_da_secao("x", analise)


def test_catalogo_leva_as_propriedades_para_as_rotinas_de_norma(tmp_path):
    partes = sd.partes_do_modelo("i", {"d": 300, "bf": 150, "tf": 12, "tw": 8})
    dados = sd.perfil_da_secao("Minha I", sd.analisar(partes))
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(dados, desenho=tuple(p.como_dicionario() for p in partes))
        item = catalogo.obter("Minha I")
        perfil = catalogo.obter_perfil("Minha I")
        assert len(item.desenho) == 3
        assert sd.partes_de_lista(item.desenho) == partes
    secao = cb.secao_de_perfil(perfil, soldado=True)
    assert secao.tipo == "I"
    assert secao.Zx == pytest.approx(ss.perfil_i_simetrico("I", 300, 150, 8, 12).zx_mm3)
    assert secao.J == pytest.approx(dados["j_mm4"])


def test_secao_livre_assimetrica_nao_engana_a_verificacao(tmp_path):
    partes = sd.partes_do_modelo("l", {"a": 100, "b": 100, "t": 10})
    analise = sd.analisar(partes)
    dados = sd.perfil_da_secao("Minha L", analise)
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(dados)
        perfil = catalogo.obter_perfil("Minha L")
    p = analise.prop
    secao = cb.secao_de_perfil(perfil)
    # A cantoneira flamba no eixo principal menor, não em x nem em y.
    assert min(secao.Ix, secao.Iy) == pytest.approx(p.i2)
    # O W é o da fibra mais afastada, não Ix/(d/2).
    assert secao.Wx == pytest.approx(p.ix / max(p.y0 + p.altura - p.yc, p.yc - p.y0))
    assert secao.x0 == pytest.approx(abs(p.x_s))
    assert secao.y0 == pytest.approx(abs(p.y_s))


def test_viga_usa_as_fibras_da_secao_assimetrica(tmp_path):
    partes = sd.partes_do_modelo(
        "i_assimetrico", {"d": 300, "bs": 200, "ts": 16, "bi": 120, "ti": 10, "tw": 8}
    )
    analise = sd.analisar(partes)
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(sd.perfil_da_secao("Assim", analise))
        perfil = catalogo.obter_perfil("Assim")
    viga = secao_de_perfil_catalogo(perfil)
    assert viga.c_superior_mm == pytest.approx(analise.prop.y0 + 300 - analise.prop.yc)
    assert viga.c_inferior_mm == pytest.approx(analise.prop.yc - analise.prop.y0)


def test_perfil_do_catalogo_vira_chapas_e_encosta():
    perfil = ss.perfil_i_simetrico("I", 300, 150, 8, 12)
    novas = sd.partes_do_perfil(perfil, grupo=3)
    assert {p.grupo for p in novas} == {3}
    assert sd.analisar(novas).prop.area == pytest.approx(perfil.area_mm2)
    chapa = [_ret(0, 0, 180, 12)]
    encostadas = sd.encostar(chapa, novas, "Em cima")
    assert encostadas[0].caixa()[1] == pytest.approx(150.0)
    assert sd.analisar([*novas, *encostadas]).prop.pedacos == 1
    u = sd.partes_do_perfil(ss.perfil_u("U", 200, 80, 6, 9), grupo=1)
    assert sd.caixa_das_partes(u)[0] == pytest.approx(-40.0)
    assert sd.caixa_das_partes(u)[2] == pytest.approx(40.0)
    assert sd.reconhecer(u).tipo == "U"


def test_tensoes_bate_com_navier_e_com_a_flexao_obliqua():
    b, h = 100.0, 200.0
    analise = sd.analisar([_ret(0, 0, b, h)])
    w = b * h**2 / 6
    mapa = sd.tensoes(analise, 100.0, 10.0, 0.0)
    assert mapa.sigma_max == pytest.approx(100e3 / (b * h) + 10e6 / w)
    assert mapa.sigma_min == pytest.approx(100e3 / (b * h) - 10e6 / w)
    # Mx positivo traciona a base, e My positivo traciona a direita.
    assert mapa.c < 0.0
    assert sd.tensoes(analise, 0.0, 0.0, 5.0).b > 0.0
    # Cantoneira: momento em torno de x puro gera σ pela fórmula com Ixy, resultante nula.
    cantoneira = sd.analisar(sd.partes_do_modelo("l", {"a": 100, "b": 100, "t": 10}))
    obliqua = sd.tensoes(cantoneira, 0.0, 5.0, 0.0)
    p, m = cantoneira.prop, cantoneira.malha
    sigma = obliqua.a + obliqua.b * (m.ponto_x - p.xc) + obliqua.c * (m.ponto_y - p.yc)
    assert float((sigma * m.ponto_peso).sum()) == pytest.approx(0.0, abs=1e-3)
    assert float((sigma * m.ponto_peso * (m.ponto_y - p.yc)).sum()) == pytest.approx(-5e6, rel=1e-9)
    assert float((sigma * m.ponto_peso * (m.ponto_x - p.xc)).sum()) == pytest.approx(0.0, abs=1.0)


@pytest.mark.parametrize(
    ("partes", "exato"),
    [
        ([sd.Parte(C, 0, 0, 100, 100)], 1e6 * 50.0 / (math.pi * 100**4 / 32)),
        ([sd.Parte(R, 0, 0, 100, 100)], 1e6 / (0.20788 * 100**3)),
        ([sd.Parte(R, 0, 0, 200, 100)], 1e6 / (0.24580 * 200 * 100**2)),
        ([sd.Parte(R, 0, 0, 500, 50)], 1e6 / (0.31233 * 500 * 50**2)),
    ],
    ids=["circulo", "quadrado", "2 por 1", "10 por 1"],
)
def test_tensao_de_torcao_fica_perto_da_exata(partes, exato):
    tau = sd.tensoes(sd.analisar(partes), 0, 0, 0, 1.0).tau_torcao
    assert tau == pytest.approx(exato, rel=0.05)


def test_dados_invalidos_viram_mensagem():
    with pytest.raises(sd.ErroDeSecao, match="cheia"):
        sd.montar_malha([_ret(0, 0, 10, 10, furo=True)])
    with pytest.raises(sd.ErroDeSecao):
        sd.parte_de_dicionario({"forma": "ret", "b": -1, "h": 2})
    with pytest.raises(sd.ErroDeSecao, match="polígono"):
        sd.parte_de_dicionario({"forma": "poli", "pontos": [[0, 0], [1, 1]]})
    with pytest.raises(sd.ErroDeSecao, match="área"):
        sd.parte_de_dicionario({"forma": "poli", "pontos": [[0, 0], [1, 1], [2, 2]]})
    with pytest.raises(sd.ErroDeSecao, match="número"):
        sd.parte_de_dicionario({"forma": "ret", "b": "x", "h": 2})
    with pytest.raises(sd.ErroDeSecao):
        sd.partes_do_modelo("i", {"d": 10, "bf": 100, "tf": 8, "tw": 6})
    with pytest.raises(sd.ErroDeSecao):
        sd.analisar([_ret(0, 0, 10, 10), _ret(0, 0, 10, 10, furo=True)])


def test_giro_de_90_troca_b_por_h_e_a_parte_continua_reta():
    parte = sd.parte_de_dicionario({"forma": "ret", "x": 1, "y": 2, "b": 10, "h": 40, "giro": 90})
    assert (parte.b, parte.h, parte.giro) == (40.0, 10.0, 0.0)
    assert parte.reta


def test_tabela_vai_e_volta_sem_perder_nada():
    partes = [
        _ret(1.5, 2.5, 30, 40, giro=15.0, grupo=2),
        sd.Parte(C, 3, 4, 20, 20, furo=True),
        sd.Parte(P, pontos=((0, 0), (10.5, 0), (10.5, 8))),
    ]
    linhas = [sr.linha_da_parte(p.como_dicionario()) for p in partes]
    assert sd.partes_de_lista(sr.parte_da_linha(linha) for linha in linhas) == partes
    assert sr.pontos_do_texto("0 0; 10,5 0; 10,5 8") == [(0.0, 0.0), (10.5, 0.0), (10.5, 8.0)]
    with pytest.raises(sd.ErroDeSecao, match="Ponto"):
        sr.pontos_do_texto("1 2 3")


def test_figuras_e_word_saem_para_qualquer_forma():
    for modelo in sd.MODELOS:
        partes = sd.partes_do_modelo(modelo.id, {m.chave: m.padrao for m in modelo.medidas})
        analise = sd.analisar(partes)
        assert figura_das_partes(partes, analise.prop).png
        assert figura_de_tensoes(analise, sd.tensoes(analise, 10, 5, 1)).png
    linhas = tuple(sr.linha_da_parte(p.como_dicionario()) for p in partes)
    valores = {"partes": linhas, "densidade_kg_m3": 7850.0}
    resultado = sr.resultado_da_secao(analise, 7850.0)
    assert gerar_word_do_caso(sr.CASO, valores, resultado)[:2] == b"PK"


def test_pagina_abre_num_modelo_e_mostra_as_propriedades(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        at = _abrir_pagina()
        assert not at.exception
        assert at.session_state["secao_modelo"] == "I"
        assert any("Usar esta seção" in m.value for m in at.markdown)
        assert any("Área" in c.value for c in at.caption)
        campos = [*at.number_input, *at.text_input]
        assert all(
            c.help for c in campos if str(c.key).startswith(("secao_m_", "secao_n", "secao_fy"))
        )


def test_trocar_modelo_e_medida_na_pagina(tmp_path):
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        at = _abrir_pagina()
        at.number_input(key="secao_m_i_d").set_value(400.0).run()
        assert not at.exception
        assert sd.partes_de_lista(at.session_state["secao_partes"])[0].y == pytest.approx(194.0)
        at.number_input(key="secao_m_i_tf").set_value(250.0).run()
        assert not at.exception
        assert any("cabem" in e.value for e in at.error)
        at.number_input(key="secao_m_i_tf").set_value(12.0).run()
        at.button(key="secao_limpar").click().run()
        assert not at.exception
        assert at.session_state["secao_partes"] == []
        assert any("Desenhe uma chapa" in i.value for i in at.info)


def test_salvar_na_pagina_grava_e_recusa_nome_de_referencia(tmp_path):
    arquivo = tmp_path / "perfis.json"
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", arquivo):
        at = _abrir_pagina()
        at.button(key="secao_salvar").click().run()
        assert not at.exception
        assert "I soldado 300×150" in catalogo.listar_perfis()
        assert catalogo.obter("I soldado 300×150").desenho
        assert at.button(key="secao_salvar").disabled

        referencia = next(n for n, i in catalogo.listar_cadastrados().items() if not i.editavel)
        at.text_input(key="secao_nome").set_value(referencia).run()
        at.button(key="secao_salvar").click().run()
        assert not at.exception
        assert any("referência" in w.value for w in at.warning)
        assert catalogo.listar_cadastrados()[referencia].editavel is False


def test_preferencias_do_menu_guardam_e_ignoram_arquivo_ruim(tmp_path):
    arquivo = tmp_path / "preferencias_menu.json"
    with mock.patch.object(pm, "_arquivo", return_value=arquivo):
        assert pm.fixados() == [] and pm.recentes() == []
        pm.alternar_fixado("a.py")
        pm.alternar_fixado("b.py")
        pm.alternar_fixado("a.py")
        assert pm.fixados() == ["b.py"]
        for pagina in ("a", "b", "a"):
            pm.anotar_recente(pagina)
        assert pm.recentes() == ["a", "b"]
        arquivo.write_text("{nada", encoding="utf-8")
        assert pm.fixados() == []
        pm.alternar_fixado("c.py")
        assert pm.fixados() == ["c.py"]


def test_menu_abre_o_grupo_da_pagina_e_busca_leva_ao_caso(tmp_path):
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    rotulos = {c.label for c in at.sidebar.children.values() if hasattr(c, "label")}
    assert {"Projeto", "Seções e materiais", "Referências e ajuda"} <= rotulos
    opcoes = at.sidebar.selectbox(key="menu_busca").options
    assert any(o.startswith("Desenhar seção") for o in opcoes)
    assert any("Parafuso" in o and "Assistente" in o for o in opcoes)


def test_cada_destino_da_pagina_tem_os_campos_e_calcula_com_a_secao_salva(tmp_path):
    from components.desenhar_secao_ui import DESTINOS
    from core import elementos_catalogo as cat
    from core.elementos_base import calcular_caso
    from core.elementos_vigas import CATALOGO

    modelos = {
        "Minha I": ("i", {"d": 300, "bf": 150, "tf": 12, "tw": 8}),
        "Minha U": ("u", {"d": 300, "bf": 100, "tf": 10, "tw": 8}),
        "Minha L": ("l", {"a": 100, "b": 75, "t": 8}),
    }
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        for nome, (modelo, medidas) in modelos.items():
            analise = sd.analisar(sd.partes_do_modelo(modelo, medidas))
            catalogo.salvar_perfil(sd.perfil_da_secao(nome, analise))
        for nome in modelos:
            for destino, _, _, so_perfil in DESTINOS:
                caso = cat.CASOS[destino]
                valores = (
                    {"perfil": nome} if so_perfil else {"tipo_secao": CATALOGO, "perfil": nome}
                )
                assert set(valores) <= {c.chave for c in caso.campos}, destino
                resultado = calcular_caso(caso, {**caso.padroes(), **valores})
                assert resultado.verificacoes, destino
                assert "inf" not in resultado.resumo, destino


def test_forma_livre_nao_mostra_aproveitamento_infinito(tmp_path):
    from core import elementos_catalogo as cat
    from core.elementos_base import calcular_caso

    analise = sd.analisar(sd.partes_do_modelo("l", {"a": 100, "b": 75, "t": 8}))
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(sd.perfil_da_secao("Livre", analise))
        caso = cat.CASOS["perfil_nbr8800"]
        resultado = calcular_caso(caso, {**caso.padroes(), "perfil": "Livre"})
    assert "não tem rotina" in resultado.resumo


def _estado_da_tela(partes):
    from components import desenhar_secao_ui as ui

    dicionarios = [p.como_dicionario() for p in partes]
    return {
        ui.PARTES: dicionarios,
        ui.VERSAO: 5,
        ui.AJUSTE: 0,
        ui.REVISAO_TABELA: 2,
        ui.BASE_TABELA: [sr.linha_da_parte(p) for p in dicionarios],
        ui.MODELO: "I",
        ui.ERRO_TABELA: "",
    }


def test_edicao_da_tabela_vale_sobre_a_base_e_acumula():
    from components import desenhar_secao_ui as ui

    estado = _estado_da_tela([_ret(0, 0, 100, 10), _ret(0, 20, 50, 10), _ret(0, 40, 30, 10)])
    estado["secao_tabela_2"] = {
        "edited_rows": {"0": {"b": 200.0}, "2": {"tipo": sr.FURO}},
        "deleted_rows": [1],
        "added_rows": [{"forma": "Círculo", "x": 5.0, "y": 6.0, "b": 8.0}],
    }
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_tabela()
    partes = sd.partes_de_lista(estado[ui.PARTES])
    assert [p.forma for p in partes] == [R, R, C]
    assert partes[0].b == 200.0
    assert partes[1].furo
    assert (partes[2].x, partes[2].b) == (5.0, 8.0)
    # A base e a chave ficam: o editor guarda as mudanças sobre elas.
    assert estado[ui.REVISAO_TABELA] == 2
    assert estado[ui.VERSAO] == 6
    assert estado[ui.MODELO] is None


def test_tabela_com_medida_ruim_avisa_e_nao_mexe_no_desenho():
    from components import desenhar_secao_ui as ui

    original = [_ret(0, 0, 100, 10)]
    estado = _estado_da_tela(original)
    estado["secao_tabela_2"] = {"edited_rows": {"0": {"b": -5.0}}}
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_tabela()
    assert estado[ui.ERRO_TABELA]
    assert sd.partes_de_lista(estado[ui.PARTES]) == original
    assert estado[ui.MODELO] == "I"


def test_gesto_na_prancheta_entra_e_gesto_invalido_nao_derruba():
    from components import desenhar_secao_ui as ui

    estado = _estado_da_tela([_ret(0, 0, 100, 10)])
    boa = _ret(0, 50, 80, 8).como_dicionario()
    ruim = {"forma": "poli", "pontos": [[0, 0], [1, 1]]}
    estado[ui.CHAVE_PRANCHETA] = mock.Mock(edicao={"partes": [boa, ruim], "versao": 9})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_na_prancheta()
    assert sd.partes_de_lista(estado[ui.PARTES]) == [_ret(0, 50, 80, 8)]
    assert estado[ui.VERSAO] == 9
    assert estado[ui.REVISAO_TABELA] == 3  # a tabela ganha uma base nova
    assert estado[ui.MODELO] is None


def test_botao_usar_salva_e_abre_o_caso_preenchido(tmp_path):
    from components.assistente_cargas_ui import chave_do_campo

    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        at = _abrir_pagina()
        at.button(key="secao_usar_viga_reacoes").click().run()
        assert not at.exception
        assert "I soldado 300×150" in catalogo.listar_perfis()
        assert at.session_state["assistente_geometria"] == "viga_reacoes"
        assert at.session_state[chave_do_campo("viga_reacoes", "perfil")] == "I soldado 300×150"


def test_word_da_secao_traz_o_desenho_e_as_propriedades():
    import io

    from docx import Document

    partes = sd.partes_do_modelo("i_chapa", {m.chave: m.padrao for m in _medidas("i_chapa")})
    analise = sd.analisar(partes)
    linhas = tuple(sr.linha_da_parte(p.como_dicionario()) for p in partes)
    valores = {"partes": linhas, "densidade_kg_m3": 7850.0}
    bruto = gerar_word_do_caso(sr.CASO, valores, sr.resultado_da_secao(analise, 7850.0))
    documento = Document(io.BytesIO(bruto))
    assert len(documento.inline_shapes) == 1
    texto = " ".join(c.text for t in documento.tables for ln in t.rows for c in ln.cells)
    assert "Constante de torção J" in texto
    assert "Retângulo" in texto


def test_csv_do_catalogo_nao_perde_os_dados_da_secao_desenhada(tmp_path):
    analise = sd.analisar(sd.partes_do_modelo("l", {"a": 100, "b": 75, "t": 8}))
    dados = sd.perfil_da_secao("Livre", analise)
    assert dados["x0_mm"] and dados["y0_mm"] and dados["i_min_mm4"]
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "perfis.json"):
        catalogo.salvar_perfil(dados)
        tabela = catalogo.catalogo_dataframe()
        linha = tabela[tabela["nome"] == "Livre"].iloc[0].to_dict()
    with mock.patch.object(catalogo, "ARQUIVO_USUARIO", tmp_path / "outro.json"):
        cadastrados, rejeitados = catalogo.importar_lote([linha], origem="CSV")
        assert not rejeitados and cadastrados
        perfil = catalogo.obter_perfil("Livre")
    assert perfil.x0_mm == pytest.approx(dados["x0_mm"])
    assert perfil.y0_mm == pytest.approx(dados["y0_mm"])
    assert perfil.i_min_mm4 == pytest.approx(dados["i_min_mm4"])


# ---------------------------------------------------------------------------
# Cotas de um ponto a outro
# ---------------------------------------------------------------------------

_COTA = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 0, "t": "v", "k": 1}, "modo": "h", "folga": 20}


def _estado_com_cotas() -> dict:
    from components import desenhar_secao_ui as ui

    return {
        ui.PARTES: [],
        ui.COTAS: [_COTA],
        ui.VERSAO: 0,
        ui.AJUSTE: 0,
        ui.REVISAO_TABELA: 0,
        ui.BASE_TABELA: [],
    }


def test_cotas_vem_junto_com_o_gesto_na_prancheta():
    from components import desenhar_secao_ui as ui

    estado = _estado_com_cotas()
    parte = {"forma": "ret", "x": 0, "y": 0, "b": 100, "h": 10, "giro": 0, "pontos": [], "grupo": 0}
    estado[ui.CHAVE_PRANCHETA] = mock.Mock(
        edicao={"partes": [parte], "cotas": [_COTA], "versao": 3}
    )
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_na_prancheta()
    assert estado[ui.COTAS] == [_COTA]


def test_gesto_antigo_sem_cotas_nao_quebra():
    from components import desenhar_secao_ui as ui

    estado = _estado_com_cotas()
    estado[ui.CHAVE_PRANCHETA] = mock.Mock(edicao={"partes": [], "versao": 3})
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_na_prancheta()
    assert estado[ui.COTAS] == []


def test_secao_nova_tira_as_cotas_da_antiga():
    from components import desenhar_secao_ui as ui

    estado = _estado_com_cotas()
    with mock.patch.object(ui.st, "session_state", estado):
        ui._limpar()
    assert estado[ui.COTAS] == []


def test_editar_a_tabela_nao_apaga_as_cotas():
    from components import desenhar_secao_ui as ui

    estado = _estado_com_cotas()
    estado[ui.ERRO_TABELA] = ""
    with mock.patch.object(ui.st, "session_state", estado):
        ui._ao_editar_tabela()
    assert estado[ui.COTAS] == [_COTA]


# ---------------------------------------------------------------------------
# Cortante na seção
# ---------------------------------------------------------------------------

V_KN = 100.0


def _r(x, y, b, h, **extras):
    return sd.Parte(R, x=x, y=y, b=b, h=h, **extras)


def _i_soldado():
    return [
        _r(0, 145, 200, 10, grupo=1),
        _r(0, 0, 8, 280, grupo=1),
        _r(0, -145, 200, 10, grupo=1),
    ]


def _u_soldado():
    return [
        _r(100, 145, 200, 10, grupo=1),
        _r(4, 0, 8, 280, grupo=1),
        _r(100, -145, 200, 10, grupo=1),
    ]


def _cantoneira():
    return [_r(50, 5, 100, 10, grupo=1), _r(5, 45, 10, 70, grupo=1)]


def _cortante(partes, **extras):
    analise = sd.analisar(partes)
    return analise, sd.tensoes(analise, 0, 0, 0, 0, 0, V_KN, **extras)


def test_retangulo_alto_da_a_parabola_classica():
    analise, mapa = _cortante([_r(0, 0, 10, 100)])
    assert mapa.tau_max == pytest.approx(1.5 * V_KN * 1e3 / analise.prop.area, rel=0.005)


def test_circulo_macico_bate_com_a_solucao_exata_com_poisson():
    """Timoshenko: no centro, τ = (3 + 2ν)/(2(1 + ν))·V/A. Sem o termo de ν, daria 1,5."""
    analise, mapa = _cortante([sd.Parte(C, x=0, y=0, b=100, h=100)])
    centro = int((mapa.no_x**2 + mapa.no_y**2).argmin())
    exato = (3 + 2 * 0.3) / (2 * 1.3) * V_KN * 1e3 / analise.prop.area
    assert mapa.no_tau_y[centro] == pytest.approx(exato, rel=0.002)


def test_alma_do_i_bate_com_vq_sobre_it():
    analise, mapa = _cortante(_i_soldado())
    q = 200 * 10 * 145 + 8 * 140 * 70
    assert mapa.tau_max == pytest.approx(V_KN * 1e3 * q / (analise.prop.ix * 8), rel=0.005)


def test_tubo_fino_da_o_dobro_da_media():
    partes = [sd.Parte(C, x=0, y=0, b=200, h=200), sd.Parte(C, x=0, y=0, b=180, h=180, furo=True)]
    analise, mapa = _cortante(partes)
    assert mapa.tau_max == pytest.approx(2 * V_KN * 1e3 / analise.prop.area, rel=0.03)


@pytest.mark.parametrize("montar", [_i_soldado, _u_soldado, _cantoneira])
def test_integral_das_tensoes_devolve_o_cortante(montar):
    """Inclui a cantoneira, com Ixy diferente de zero, onde V·Q/(I·b) nem se aplica."""
    campos = sd.campos_de_cortante(sd.analisar(montar()))
    assert campos.resultante == pytest.approx((1.0, 0.0, 0.0, 1.0), abs=2e-5)
    assert campos.erro < 2e-5


@pytest.mark.parametrize("montar", [_u_soldado, _cantoneira])
def test_centro_de_cisalhamento_sai_igual_pelos_dois_caminhos(montar):
    """Um vem do empenamento e o outro do momento das tensões de cortante."""
    analise = sd.analisar(montar())
    campos = sd.campos_de_cortante(analise)
    # Em milímetros, e não relativo: o y_s do U é zero, e erro relativo em torno de zero não existe.
    assert campos.momento_vy == pytest.approx(analise.prop.x_s, abs=0.05)
    assert -campos.momento_vx == pytest.approx(analise.prop.y_s, abs=0.05)


def test_carga_pelo_centro_de_gravidade_soma_a_torcao_da_excentricidade():
    analise = sd.analisar(_u_soldado())
    campos = sd.campos_de_cortante(analise)
    no_cc = sd.tensoes(analise, 0, 0, 0, 0, 0, V_KN, campos=campos)
    no_cg = sd.tensoes(analise, 0, 0, 0, 0, 0, V_KN, campos=campos, pelo_centro_de_gravidade=True)
    assert no_cc.torcao_extra == 0.0
    assert no_cg.torcao_extra == pytest.approx(-V_KN * analise.prop.x_s / 1e3, rel=0.001)
    assert no_cg.tau_max > 5 * no_cc.tau_max


def test_v_e_t_somam_como_vetores_e_nao_como_modulos():
    """Num tubo, V e T se somam num lado e se subtraem no outro: a soma dos maiores valores é o teto."""
    partes = [sd.Parte(C, x=0, y=0, b=200, h=200), sd.Parte(C, x=0, y=0, b=180, h=180, furo=True)]
    analise = sd.analisar(partes)
    so_v = sd.tensoes(analise, 0, 0, 0, 0, 0, V_KN)
    so_t = sd.tensoes(analise, 0, 0, 0, 5.0)
    junto = sd.tensoes(analise, 0, 0, 0, 5.0, 0, V_KN)
    assert junto.tau_max > max(so_v.tau_max, so_t.tau_max)
    assert junto.tau_max == pytest.approx(so_v.tau_max + so_t.tau_max, rel=0.03)
    direita = int(((junto.no_x - 95) ** 2 + junto.no_y**2).argmin())
    esquerda = int(((junto.no_x + 95) ** 2 + junto.no_y**2).argmin())
    assert so_t.no_tau_y[direita] > 0 > so_t.no_tau_y[esquerda]
    assert junto.no_tau_y[direita] == pytest.approx(so_v.no_tau_y[direita] + so_t.no_tau_y[direita])
    assert junto.no_tau_y[esquerda] == pytest.approx(
        so_v.no_tau_y[esquerda] + so_t.no_tau_y[esquerda]
    )
    assert junto.no_tau_y[esquerda] < so_v.no_tau_y[esquerda]


def test_torcao_sozinha_continua_dando_t_sobre_wt():
    analise = sd.analisar(_i_soldado())
    mapa = sd.tensoes(analise, 0, 0, 0, 2.0)
    assert mapa.tau_max == pytest.approx(2e6 / analise.prop.w_torcao)
    assert mapa.tau_max == pytest.approx(mapa.tau_torcao)
    assert mapa.tau_cortante == 0.0


def test_von_mises_junta_sigma_e_tau_no_mesmo_ponto():
    """Na emenda da mesa com a alma, σ e τ são altos juntos: é lá que o I costuma governar."""
    analise = sd.analisar(_i_soldado())
    mapa = sd.tensoes(analise, 0, 300.0, 0, 0, 0, 800.0)
    sigma_mesa = max(abs(mapa.sigma_max), abs(mapa.sigma_min))
    assert mapa.mises >= sigma_mesa
    assert mapa.mises > mapa.tau_max * math.sqrt(3)
    assert mapa.sigma_no_ponto**2 + 3 * mapa.tau_no_ponto**2 == pytest.approx(mapa.mises**2)


def test_secao_em_pedacos_nao_finge_cortante():
    analise = sd.analisar([_r(0, 0, 50, 50), _r(200, 0, 50, 50)])
    with pytest.raises(sd.ErroDeSecao, match="pedaços soltos"):
        sd.campos_de_cortante(analise)


# ---------------------------------------------------------------------------
# Ligações entre as chapas
# ---------------------------------------------------------------------------


def test_fluxo_na_solda_da_mesa_bate_com_vq_sobre_i():
    analise, mapa = _cortante(_i_soldado())
    fluxos = sd.fluxos_nas_ligacoes(analise, mapa)
    assert len(fluxos) == 2
    esperado = V_KN * 1e3 * (200 * 10 * 145) / analise.prop.ix
    for fluxo in fluxos:
        assert fluxo.comprimento == pytest.approx(8.0)
        assert fluxo.q == pytest.approx(esperado, rel=0.01)


def test_fluxo_no_u_tambem_vem_pela_mesa():
    analise, mapa = _cortante(_u_soldado())
    fluxos = sd.fluxos_nas_ligacoes(analise, mapa)
    q_mesa = (200 * 10) * 145
    assert len(fluxos) == 2
    for fluxo in fluxos:
        assert fluxo.q == pytest.approx(V_KN * 1e3 * q_mesa / analise.prop.ix, rel=0.02)


def test_sem_emenda_nao_ha_linha_na_tabela():
    analise, mapa = _cortante([_r(0, 0, 10, 100)])
    assert sd.fluxos_nas_ligacoes(analise, mapa) == []


# ---------------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------------


def _linhas(partes, vy=V_KN, vx=0.0, fy=250.0, fs=1.5):
    analise = sd.analisar(partes)
    mapa = sd.tensoes(analise, 0, 0, 0, 0, vx, vy)
    return sr.verificacoes_de_tensao(analise, mapa, fy, fs, vx, vy), mapa


def test_escoamento_por_cisalhamento_e_fy_sobre_raiz_de_3():
    (linhas, _), mapa = _linhas(_i_soldado())
    tau = next(v for v in linhas if v.nome == "Cisalhamento")
    assert tau.solicitante == pytest.approx(mapa.tau_max)
    assert tau.resistente == pytest.approx(250.0 / 1.5 / math.sqrt(3))


def test_alma_robusta_passa_pela_norma_sem_aviso():
    (linhas, avisos), _ = _linhas(_i_soldado())
    norma = next(v for v in linhas if "pela norma" in v.nome)
    assert norma.nome == "Cortante na alma pela norma"
    assert norma.referencia == "NBR 8800, 5.4.3"
    assert norma.solicitante == V_KN
    assert avisos == []


def test_alma_esbelta_avisa_que_quem_manda_e_a_norma():
    """A tensão passa folgada, e mesmo assim a alma flambaria: a tensão sozinha daria falsa segurança."""
    partes = [
        _r(0, 505, 200, 10, grupo=1),
        _r(0, 0, 5, 1000, grupo=1),
        _r(0, -505, 200, 10, grupo=1),
    ]
    (linhas, avisos), _ = _linhas(partes, vy=50.0)
    assert next(v for v in linhas if v.nome == "Cisalhamento").status == "OK"
    assert len(avisos) == 1
    assert "flamba por cisalhamento" in avisos[0]


def test_seccao_livre_fica_so_nas_tensoes():
    poligono = sd.Parte(P, pontos=((0, 0), (120, 0), (0, 90)))
    (linhas, avisos), _ = _linhas([poligono])
    assert [v.nome for v in linhas] == ["Tensão normal", "Cisalhamento", "Tensão combinada"]
    assert avisos == []


def test_sem_cortante_nao_entra_a_linha_da_norma():
    analise = sd.analisar(_i_soldado())
    mapa = sd.tensoes(analise, 0, 10.0, 0)
    linhas, _ = sr.verificacoes_de_tensao(analise, mapa, 250.0, 1.5)
    assert len(linhas) == 3


# ---------------------------------------------------------------------------
# Desenho e tela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["sigma", "tau", "mises"])
def test_todos_os_mapas_saem(campo):
    analise = sd.analisar(_u_soldado())
    mapa = sd.tensoes(analise, 10.0, 20.0, 0, 1.0, 0, V_KN)
    desenho = figura_de_tensoes(analise, mapa, campo)
    assert desenho.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert desenho.legenda


def test_mapa_sem_tensao_nenhuma_tambem_sai():
    analise = sd.analisar(_i_soldado())
    mapa = sd.tensoes(analise, 0, 0, 0)
    for campo in ("sigma", "tau", "mises"):
        assert figura_de_tensoes(analise, mapa, campo).png


def test_tela_de_tensoes_mostra_o_cortante_e_a_norma():
    pagina = _abrir_pagina()
    pagina.number_input(key="secao_vy").set_value(100.0).run()
    assert not pagina.exception
    quadro = next(d.value for d in pagina.dataframe if "Aproveitamento" in d.value.columns)
    assert "Cortante na alma pela norma" in set(quadro["Verificação"])
    assert any("q (kN/m)" in d.value.columns for d in pagina.dataframe)


def test_tela_avisa_a_torcao_da_carga_fora_do_centro_de_cisalhamento():
    pagina = _abrir_pagina()
    pagina.session_state["secao_modelo"] = "U"
    pagina.number_input(key="secao_vy").set_value(100.0)
    pagina.selectbox(key="secao_pelo").set_value("Centro de gravidade").run()
    assert not pagina.exception


def test_tela_com_pedacos_soltos_avisa_e_nao_quebra():
    from components import desenhar_secao_ui as ui

    pagina = _abrir_pagina()
    pagina.session_state[ui.PARTES] = [
        _r(0, 0, 50, 50).como_dicionario(),
        _r(200, 0, 50, 50).como_dicionario(),
    ]
    pagina.number_input(key="secao_vy").set_value(50.0).run()
    assert not pagina.exception
    assert any("pedaços soltos" in w.value for w in pagina.warning)
