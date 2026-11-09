"""Travamentos informados na Flambagem de colunas: trechos, K de cada trecho e o que governa.

O núcleo (``core/travamentos_da_coluna.py``) é conferido contra a Tabela E.1 da NBR 8800, contra a
flambagem da coluna contínua (que nunca pode dar carga maior que a dos trechos com pino) e contra
as fórmulas da mão-francesa; a página, pela interface (AppTest).
"""

from __future__ import annotations

import io
import math
import random
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from PIL import Image
from streamlit.testing.v1 import AppTest

from components import column_ui as ui
from core import column_buckling as cb
from core import desenho_da_coluna as dc
from core import memorial_verificacoes as mv
from core import section_catalog as sc
from core import travamentos_da_coluna as tc
from core.coluna_word import gerar_word_coluna
from core.project_store import obter_projeto_ativo

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGINA = "app_pages/flambagem_colunas.py"
BALANCO = "Engastada-livre (em balanço)"
BIAPOIADA = "Biapoiada (pino-pino)"
ENGASTADA_PINO = "Engastada-pino"


# ------------------------------------------------------------------ sem travamentos: a Tabela E.1
@pytest.mark.parametrize("apoio", list(tc.PONTAS))
@pytest.mark.parametrize("recomendado", [False, True])
def test_sem_travamento_o_k_e_o_da_tabela(apoio, recomendado):
    tabela = cb.CONDICOES_APOIO_RECOMENDADAS if recomendado else cb.CONDICOES_APOIO
    eixo = tc.trechos_do_eixo("x", 3000.0, (), apoio, tabela[apoio], recomendado)
    assert len(eixo.trechos) == 1
    assert eixo.governa.k == pytest.approx(tabela[apoio])
    assert eixo.governa.comprimento_mm == pytest.approx(3000.0)


@pytest.mark.parametrize("apoio", list(tc.PONTAS))
def test_coluna_continua_sem_travamento_da_o_k_teorico(apoio):
    base, topo = tc.PONTAS[apoio]
    kl = tc.comprimento_de_flambagem(3000.0, (), base, topo)
    assert kl / 3000.0 == pytest.approx(cb.CONDICOES_APOIO[apoio], rel=2e-3)


def test_mola_do_engaste_recomendado_da_2_1_no_balanco():
    mola = tc._mola_do_engaste_recomendado()
    kl = tc.comprimento_de_flambagem(3000.0, (), tc.ENGASTE, tc.LIVRE, mola)
    assert kl / 3000.0 == pytest.approx(2.1, rel=1e-4)


# ------------------------------------------------------------------ com travamentos
def test_biapoiada_com_tres_travamentos_iguais_tem_um_quarto_do_comprimento():
    eixo = tc.trechos_do_eixo("y", 4000.0, (1000.0, 2000.0, 3000.0), BIAPOIADA, 1.0, True)
    assert [t.k for t in eixo.trechos] == [1.0] * 4
    assert eixo.governa.kl_mm == pytest.approx(1000.0)
    kl = tc.comprimento_de_flambagem(4000.0, (1000.0, 2000.0, 3000.0), tc.PINO, tc.PINO)
    assert kl == pytest.approx(1000.0, rel=1e-4)


def test_engaste_na_base_da_0_8_no_primeiro_trecho_e_o_maior_k_l_governa():
    eixo = tc.trechos_do_eixo("x", 6000.0, (3200.0,), ENGASTADA_PINO, 0.8, True)
    baixo, cima = eixo.trechos
    assert (baixo.k, cima.k) == (0.8, 1.0)
    assert "engaste e travamento" in baixo.como and "Tabela E.1 (b)" in baixo.como
    assert eixo.governa is cima  # 1,0 × 2800 > 0,8 × 3200
    assert eixo.maior_trecho_mm == pytest.approx(3200.0)  # o do B₁ e o do L_b


def test_k_informado_vale_em_todos_os_trechos():
    eixo = tc.trechos_do_eixo("x", 5000.0, (2000.0,), ui.APOIO_MANUAL, 1.3, True)
    assert [t.k for t in eixo.trechos] == [1.3, 1.3]
    assert eixo.governa.kl_mm == pytest.approx(1.3 * 3000.0)
    assert all(t.como == "K informado" for t in eixo.trechos)


@pytest.mark.parametrize("apoio", ["Biengastada", ENGASTADA_PINO, BIAPOIADA])
def test_pino_no_travamento_fica_a_favor_da_seguranca(apoio):
    """Soltar o giro no travamento nunca aumenta a carga crítica: K·L dos trechos ≥ o contínuo."""
    sorteio = random.Random(7)
    base, topo = tc.PONTAS[apoio]
    for _ in range(25):
        alturas = sorted(sorteio.uniform(100.0, 5900.0) for _ in range(sorteio.randint(1, 4)))
        eixo = tc.trechos_do_eixo("x", 6000.0, alturas, apoio, 1.0, False)
        continuo = tc.comprimento_de_flambagem(6000.0, eixo.alturas_mm, base, topo)
        assert eixo.governa.kl_mm >= continuo * (1 - 1e-4), alturas


def test_balanco_acima_do_ultimo_travamento_usa_a_coluna_inteira():
    eixo = tc.trechos_do_eixo("x", 3000.0, (2500.0,), BALANCO, 2.0, False)
    baixo, cima = eixo.trechos
    assert not baixo.pela_coluna_inteira and baixo.k == 0.7
    assert cima.pela_coluna_inteira and "balanço acima do último travamento" in cima.como
    assert cima.kl_mm == pytest.approx(
        tc.comprimento_de_flambagem(3000.0, (2500.0,), "engaste", "livre")
    )
    assert eixo.governa is cima  # o balanço de 500 mm puxa a coluna inteira


@pytest.mark.parametrize("recomendado", [False, True])
def test_balanco_tende_aos_casos_da_tabela_nos_extremos(recomendado):
    """Travamento quase no topo: engaste e pino (0,7); quase na base: o balanço inteiro (2,0)."""
    mola = tc._mola_do_engaste_recomendado() if recomendado else None
    perto_do_topo = tc.comprimento_de_flambagem(3000.0, (2995.0,), tc.ENGASTE, tc.LIVRE, mola)
    perto_da_base = tc.comprimento_de_flambagem(3000.0, (5.0,), tc.ENGASTE, tc.LIVRE, mola)
    # quase no topo vira engaste e pino: 0,70 com o engaste perfeito, 0,73 com a mola
    engaste_e_pino = tc.comprimento_de_flambagem(3000.0, (), tc.ENGASTE, tc.PINO, mola)
    assert perto_do_topo == pytest.approx(engaste_e_pino, rel=5e-3)
    assert 0.69 < engaste_e_pino / 3000.0 < 0.80
    assert perto_da_base / 3000.0 == pytest.approx(2.0, abs=0.01)
    sem_mola = tc.comprimento_de_flambagem(3000.0, (1500.0,), tc.ENGASTE, tc.LIVRE)
    com_mola = tc.comprimento_de_flambagem(
        3000.0, (1500.0,), tc.ENGASTE, tc.LIVRE, tc._mola_do_engaste_recomendado()
    )
    assert com_mola > sem_mola  # o engaste real é mais mole: K·L cresce


def test_organizar_tira_o_que_nao_entra_e_explica():
    travamentos = [
        tc.Travamento(1500.0, True, False, "viga V1"),
        tc.Travamento(0.0),
        tc.Travamento(3200.0),
        tc.Travamento(800.0, False, False),
        tc.Travamento(1500.4, True, True),
        tc.Travamento(2200.0, False, True),
    ]
    em_x, em_y, fora = tc.organizar(travamentos, 3000.0)
    assert em_x == (1500.0,)  # 1500 e 1500,4 são o mesmo ponto
    assert em_y == (1500.4, 2200.0)
    assert len(fora) == 3
    assert sum("numa ponta da coluna ou fora dela" in f for f in fora) == 2
    assert any("não trava L_x nem L_y" in f for f in fora)
    assert [tc.aceito(t, 3000.0) for t in travamentos] == [True, False, False, False, True, True]


def test_textos_para_o_registro():
    travamentos = (tc.Travamento(3000.0, False, True), tc.Travamento(1500.0, True, True, "viga V1"))
    assert tc.texto_dos_travamentos(travamentos) == "1500 mm (L_x e L_y, viga V1); 3000 mm (L_y)"
    eixo = tc.trechos_do_eixo("x", 6000.0, (3200.0,), ENGASTADA_PINO, 0.8, True)
    assert tc.texto_dos_trechos(eixo) == (
        "0–3200 mm: K = 0,80, K·L = 2560 mm; 3200–6000 mm: K = 1,00, K·L = 2800 mm (governa)"
    )


# ------------------------------------------------------------------ mão-francesa
@pytest.mark.parametrize("a", [500.0, 1500.0, 2800.0])
def test_forca_horizontal_sem_travamento_da_as_formulas_da_pagina(a):
    for vinculo, (base, topo) in cb._PONTAS_DO_VINCULO.items():
        esperado, _ = cb._momento_forca_horizontal(1.0, a, 3000.0, vinculo)
        braco, _ = tc.momento_da_forca_horizontal(3000.0, (), base, topo, a)
        assert braco == pytest.approx(esperado, rel=1e-6), vinculo


def test_forca_horizontal_com_travamento():
    # balanço travado a 1500 e força a 2800: o trecho de cima é isostático, M = H·(2800 − 1500)
    braco, onde = tc.momento_da_forca_horizontal(3000.0, (1500.0,), tc.ENGASTE, tc.LIVRE, 2800.0)
    assert (braco, onde) == (pytest.approx(1300.0, rel=1e-6), pytest.approx(1500.0))
    # força bem no travamento: ele a segura e a coluna não flete
    braco, _ = tc.momento_da_forca_horizontal(3000.0, (1500.0,), tc.PINO, tc.PINO, 1500.0)
    assert braco == pytest.approx(0.0, abs=1e-6)


def test_mao_francesa_com_travamento_usa_a_coluna_continua():
    sem = cb.esforcos_mao_francesa(20e3, 45.0, 2800.0, 3000.0, cb.VINCULOS_MAO_FRANCESA[0])
    com = cb.esforcos_mao_francesa(
        20e3, 45.0, 2800.0, 3000.0, cb.VINCULOS_MAO_FRANCESA[0], travamentos_mm=(1500.0,),
        pontas=tc.PONTAS[BALANCO],
    )  # fmt: skip
    h = 20e3 * math.sin(math.radians(45.0))
    assert sem.momento_horizontal_Nmm == pytest.approx(h * 2800.0)
    assert com.momento_horizontal_Nmm == pytest.approx(h * 1300.0, rel=1e-6)
    assert "coluna contínua com 1 travamento como apoio" in com.expressao


# ------------------------------------------------------------------ na verificação da coluna
W250 = cb.secao_de_perfil(sc.listar_perfis()["W 250 x 32,7"])


def _entrada(**extra) -> cb.EntradaColuna:
    base = dict(
        secao=W250, fy_MPa=345.0, Lx_mm=2800.0, Ly_mm=2800.0, N_Sd_kN=300.0, Mx_kNm=40.0,
    )  # fmt: skip
    return cb.EntradaColuna(**{**base, **extra})


def test_b1_usa_o_maior_trecho_entre_travamentos():
    sem = cb.verificar_coluna(_entrada())
    com = cb.verificar_coluna(_entrada(Lx_B1_mm=3200.0))
    assert com.b1_x > sem.b1_x
    b1 = next(v for v in com.verificacoes if v.nome.startswith("B₁x"))
    assert "o maior trecho entre travamentos, 3200 mm" in b1.formula


def test_k_da_coluna_continua_nao_vira_aviso_de_digitacao():
    texto = "fora da faixa física usual"
    assert any(texto in a for a in cb.verificar_coluna(_entrada(kx=4.9, Lx_mm=500.0)).avisos)
    calculado = cb.verificar_coluna(_entrada(kx=4.9, Lx_mm=500.0, k_pela_coluna_continua=("x",)))
    assert not any(texto in a for a in calculado.avisos)


# ------------------------------------------------------------------ desenho e Word
def test_desenho_mostra_os_travamentos_nas_alturas_informadas():
    base = (W250, 3000.0, 1500.0, 3000.0, 1.0, 1.0, BIAPOIADA, BIAPOIADA)
    a_cada_l = dc.figura_da_coluna(dc.ColunaEmPe(*base))
    informados = dc.figura_da_coluna(
        dc.ColunaEmPe(*base, travas_x_mm=(700.0, 2100.0), travas_y_mm=())
    )
    assert a_cada_l.png != informados.png
    imagem = Image.open(io.BytesIO(informados.png))
    assert imagem.format == "PNG"


def test_balanco_da_tabela_f_tem_pino_embaixo():
    assert dc.APOIOS_NAS_PONTAS["Engastada-pino com translação (deslocável)"] == (
        tc.PINO,
        tc.GUIADO,
    )


def test_word_e_memorial_levam_os_travamentos():
    entrada = _entrada(Lx_B1_mm=3200.0)
    resultado = cb.verificar_coluna(entrada)
    eixo = tc.trechos_do_eixo("x", 6000.0, (3200.0,), ENGASTADA_PINO, 0.8, True)
    contexto = {
        "travamentos": "3200 mm (L_x e L_y, viga V1)",
        "trechos_em_x": tc.texto_dos_trechos(eixo),
    }
    documento = Document(BytesIO(gerar_word_coluna(entrada, resultado, contexto=contexto)))
    partes = [p.text for p in documento.paragraphs]
    partes += [c.text for t in documento.tables for linha in t.rows for c in linha.cells]
    cheio = "\n".join(partes)
    assert "Travamentos ao longo da coluna (altura da base)" in cheio
    assert "3200 mm (L_x e L_y, viga V1)" in cheio
    assert "Trechos entre travamentos em x (L_x)" in cheio
    assert "Maior trecho em x, para o B₁ [mm]" in cheio
    registro = cb.registro_coluna(entrada, resultado, contexto=contexto)
    rotulos = [r for r, _ in mv.pares_de_entrada(registro, str, str)]
    assert "Travamentos ao longo da coluna (altura da base)" in rotulos


# ------------------------------------------------------------------ a página
def _abrir(banco, linhas, **estado) -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=240)
    teste.run()
    teste.switch_page(PAGINA)
    teste.session_state["col_trav_ativar"] = True
    teste.session_state["col_trav_linhas"] = linhas
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def _metrica(teste: AppTest, rotulo: str) -> str:
    return next(m.value for m in teste.metric if m.label == rotulo)


def _linha(altura, x=True, y=True, que=""):
    return {"Altura da base (mm)": altura, "Trava L_x": x, "Trava L_y": y, "O que trava": que}


def test_pagina_divide_a_coluna_nos_travamentos(banco_isolado):
    # barra Ø50 (r = 12,5 mm), L = 2000: um travamento no meio só de L_y
    t = _abrir(banco_isolado, [_linha(1000.0, x=False), _linha(None)])
    assert _metrica(t, "λx = Kx·Lx/rx") == "160.0"
    assert _metrica(t, "λy = Ky·Ly/ry") == "80.0"
    trechos = next(d.value for d in t.dataframe if "De onde vem o K" in d.value.columns)
    assert len(trechos) == 3 and list(trechos["Governa"]).count("sim") == 2
    assert any("no trecho que governa em cada eixo" in c.value for c in t.caption)


def test_pagina_avisa_travamento_fora_da_coluna(banco_isolado):
    t = _abrir(banco_isolado, [_linha(2500.0)])
    assert any("numa ponta da coluna ou fora dela" in w.value for w in t.warning)
    assert _metrica(t, "λx = Kx·Lx/rx") == "160.0"


def test_pagina_em_balanco_com_travamento(banco_isolado):
    t = _abrir(
        banco_isolado,
        [_linha(1500.0, y=False)],
        col_apoio_x=BALANCO,
        col_k_recomendado=False,
    )
    kl = tc.comprimento_de_flambagem(2000.0, (1500.0,), tc.ENGASTE, tc.LIVRE)
    assert float(_metrica(t, "λx = Kx·Lx/rx")) == pytest.approx(kl / 12.5, abs=0.06)
    assert any("Acima do último travamento" in c.value for c in t.caption)
    assert not any("fora da faixa física usual" in w.value for w in t.warning)


def test_pagina_registra_os_travamentos(banco_com_projeto):
    t = _abrir(banco_com_projeto, [_linha(1000.0, que="viga V1")])
    t.button(key="registrar_flambagem_colunas").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    projeto = obter_projeto_ativo()
    registro = next(
        r for r in projeto["registros_tecnicos"] if r["modulo_id"] == "flambagem_colunas"
    )
    entradas = registro["entradas"]
    assert entradas["travamentos"] == "1000 mm (L_x e L_y, viga V1)"
    assert "(governa)" in entradas["trechos_em_x"]
    assert entradas["comprimento_B1_x_mm"] == pytest.approx(1000.0)


def test_editar_a_tabela_guarda_as_linhas(banco_isolado):
    t = _abrir(banco_isolado, [_linha(1000.0)])
    chave = "col_trav_tabela_0"
    assert chave in t.session_state  # a tabela da revisão 0 está na tela
    edicao = {
        "edited_rows": {0: {"Altura da base (mm)": 600.0}},
        "added_rows": [{"Altura da base (mm)": 1400.0, "Trava L_x": False}],
        "deleted_rows": [],
    }
    linhas = ui.com_edicoes(t.session_state["col_trav_linhas"], edicao)
    limpas = [ui._linha_de_travamento(linha) for linha in linhas]
    assert limpas == [_linha(600.0), _linha(1400.0, x=False)]  # a linha nova trava L_y
