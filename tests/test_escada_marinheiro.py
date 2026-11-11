"""Escada marinheiro: NR-12 (Anexo III, item 13 e 13.1), NBR 6120 e NBR 8800; página e memorial."""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.cena_3d_svg import svg_da_cena
from components.escada_marinheiro_help import AJUDA
from core import desenho_escada_marinheiro as dem
from core import escada_marinheiro as em
from core.navegacao import item_da_pagina
from core.project_store import obter_projeto_ativo
from core.record_charts import imagens_do_registro
from core.technical_modules import listar_modulos
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/escada_marinheiro.py"
PADRAO = em.EntradaMarinheiro()


def linha(r: em.ResultadoMarinheiro, nome: str):
    return next(v for v in r.verificacoes if v.nome == nome)


def status(entrada: em.EntradaMarinheiro, nome: str) -> str:
    return linha(em.calcular(entrada), nome).status


# ------------------------------------------------------------------ NR-12, item 13 e 13.1
@pytest.mark.parametrize(
    ("campo", "nome", "dentro", "fora"),
    [
        ("inclinacao_graus", "Inclinação da escada", (75.0, 90.0), (74.0,)),
        ("largura_mm", "Largura da escada", (400.0, 600.0), (390.0, 610.0)),
        ("passo_mm", "Espaçamento entre as barras", (250.0, 300.0), (240.0, 310.0)),
        ("primeira_barra_mm", "Primeira barra acima do piso", (550.0,), (560.0,)),
        ("afastamento_mm", "Distância das barras à estrutura", (150.0,), (140.0,)),
        ("degrau_mm", "Diâmetro ou espessura da barra", (25.0, 38.0), (24.0, 39.0)),
        ("ultrapassa_mm", "Montantes acima do piso de chegada", (1100.0, 1200.0), (1000.0, 1300.0)),
        ("inicio_gaiola_mm", "Início da gaiola acima do piso", (2000.0, 1800.0), (2100.0,)),
        ("gaiola_ultrapassa_mm", "Gaiola acima do piso de chegada", (1100.0, 1200.0), (1050.0,)),
        ("diametro_gaiola_mm", "Diâmetro da gaiola", (650.0, 800.0), (640.0, 810.0)),
        ("verticais_mm", "Espaçamento das barras verticais", (300.0,), (310.0,)),
        ("arcos_mm", "Distância entre os arcos", (1500.0,), (1510.0,)),
    ],
)
def test_limites_da_nr12_dos_dois_lados(campo, nome, dentro, fora):
    for valor in dentro:
        assert status(replace(PADRAO, **{campo: valor}), nome) == "OK", (campo, valor)
    for valor in fora:
        assert status(replace(PADRAO, **{campo: valor}), nome) == "NÃO OK", (campo, valor)


def test_gaiola_exigida_acima_de_3_5_m():
    assert status(replace(PADRAO, gaiola=False, altura_m=3.5), "Gaiola de proteção") == "OK"
    assert status(replace(PADRAO, gaiola=False, altura_m=3.6), "Gaiola de proteção") == "NÃO OK"


def test_gaiola_de_arcos_proximos():
    e = replace(PADRAO, tipo_gaiola=em.GAIOLA_ARCOS, arcos_mm=300.0)
    nomes = {v.nome: v.status for v in em.calcular(e).verificacoes}
    assert nomes["Vão entre os arcos"] == "OK"
    assert "Espaçamento das barras verticais" not in nomes
    assert status(replace(e, arcos_mm=320.0), "Vão entre os arcos") == "NÃO OK"


def test_lance_unico_ate_10_m_e_varios_lances_ate_6_m():
    assert status(replace(PADRAO, altura_m=10.0), "Altura do lance único") == "OK"
    assert status(replace(PADRAO, altura_m=10.5), "Altura do lance único") == "NÃO OK"
    tres = replace(PADRAO, altura_m=18.0, lances=3, afastamento_entre_lances_mm=700.0)
    assert status(tres, "Altura entre plataformas de descanso") == "OK"
    assert status(replace(tres, altura_m=18.5), "Altura entre plataformas de descanso") == "NÃO OK"
    assert status(tres, "Afastamento entre os lances") == "OK"
    assert (
        status(replace(tres, afastamento_entre_lances_mm=650.0), "Afastamento entre os lances")
        == "NÃO OK"
    )


def test_barras_antiderrapantes_e_corrosao():
    assert status(replace(PADRAO, antiderrapante=False), "Barras antiderrapantes") == "NÃO OK"
    nomes = {v.nome for v in em.calcular(PADRAO).verificacoes}
    assert "Material resistente a intempéries e corrosão" not in nomes
    agressivo = replace(PADRAO, ambiente_agressivo=True, protecao_contra_corrosao=False)
    assert status(agressivo, "Material resistente a intempéries e corrosão") == "NÃO OK"


def test_barras_ficam_abaixo_do_piso_de_chegada():
    # 6 m, primeira a 300 e passo 300: o piso cai numa posição de barra e faz o papel dela.
    r = em.calcular(PADRAO)
    assert r.barras_por_lance == 19 and r.ultima_barra_ao_piso_mm == pytest.approx(300.0)
    r = em.calcular(replace(PADRAO, altura_m=6.2))
    assert r.barras_por_lance == 20 and r.ultima_barra_ao_piso_mm == pytest.approx(200.0)
    # Passar do espaçamento máximo até o piso só pede atenção (boa prática, não a NR-12).
    alto = em.calcular(replace(PADRAO, altura_m=6.0, primeira_barra_mm=250.0, passo_mm=250.0))
    assert linha(alto, "Última barra até o piso de chegada").status in ("OK", "ALERTA")


# ------------------------------------------------------------------ NBR 8800
def test_degrau_conta_a_mao():
    r = em.calcular(PADRAO)
    vao = 450.0 + 9.53
    assert r.momento_degrau_kNm == pytest.approx(1.5 * 2.5 * vao / 4 / 1000)
    w = math.pi * 25.4**3 / 32
    assert r.momento_resistente_degrau_kNm == pytest.approx(1.5 * w * 250 / 1.10 / 1e6)
    quadrada = em.calcular(replace(PADRAO, forma_do_degrau=em.QUADRADA))
    assert quadrada.momento_resistente_degrau_kNm == pytest.approx(25.4**3 / 4 * 250 / 1.10 / 1e6)


def test_montante_pelos_dois_eixos():
    r = em.calcular(PADRAO)
    peso_lance = em.peso_por_metro(PADRAO) * 6.0 * em.G / 1000
    assert r.normal_montante_kN == pytest.approx((1.25 * peso_lance + 1.5 * 2.5) / 2)
    # para a estrutura: 2000/(50,8/√12) = 136,4; entre barras: 300/(9,53/√12) = 109,1
    assert r.esbeltez_montante == pytest.approx(2000 / (50.8 / math.sqrt(12)))
    lambda0 = r.esbeltez_montante / math.pi * math.sqrt(250 / 200_000)
    chi = 0.877 / lambda0**2
    assert r.resistencia_montante_kN == pytest.approx(chi * 50.8 * 9.53 * 250 / 1.10 / 1000)
    # Com suportes próximos, o eixo que manda é o de entre barras.
    perto = em.calcular(replace(PADRAO, fixacoes_mm=1000.0))
    assert perto.esbeltez_montante == pytest.approx(300 / (9.53 / math.sqrt(12)))
    longe = em.calcular(replace(PADRAO, fixacoes_mm=3500.0))
    assert linha(longe, "Montante: esbeltez").status == "NÃO OK"


def test_peso_com_e_sem_gaiola():
    sem = em.peso_por_metro(replace(PADRAO, gaiola=False))
    montantes = 2 * 50.8 * 9.53 * 1000 * 1e-9 * 7850
    barras = math.pi * 25.4**2 / 4 * (450 + 2 * 9.53) * 1000 / 300 * 1e-9 * 7850
    assert sem == pytest.approx(montantes + barras)
    assert em.peso_por_metro(PADRAO) > sem
    assert em.barras_verticais_da_gaiola(PADRAO) == math.ceil((math.pi * 700 - 450) / 300)


def test_padrao_atende_e_avisa_nr12_e_nr35():
    r = em.calcular(PADRAO)
    assert r.status == "OK" and r.aproveitamento_maximo < 1
    avisos = " ".join(r.avisos)
    assert "1.3" in avisos and "NR-35" in avisos and "critério do programa" in avisos


@pytest.mark.parametrize(
    "troca",
    [{"altura_m": 0.0}, {"lances": 0}, {"largura_mm": -1.0}, {"aco": "XYZ"},
     {"forma_do_degrau": "oval"}, {"montante_t_mm": 80.0}, {"pessoas_por_lance": 11}],
)  # fmt: skip
def test_entrada_impossivel_e_recusada(troca):
    with pytest.raises(em.EscadaInvalida):
        em.calcular(replace(PADRAO, **troca))


# ------------------------------------------------------------------ desenhos e memorial
def textos(svg: str) -> str:
    return " ".join(re.findall(r">([^<>]+)</text>", svg))


@pytest.mark.parametrize(
    "entrada",
    [PADRAO, replace(PADRAO, altura_m=14.0, lances=3, afastamento_entre_lances_mm=800.0),
     replace(PADRAO, altura_m=3.0, gaiola=False)],
)  # fmt: skip
def test_desenhos_trazem_as_cotas(entrada):
    r = em.calcular(entrada)
    frente = textos(svg_da_cena(dem.frente(r)))
    assert f"H = {entrada.altura_m:.2f} m".replace(".", ",") in frente
    assert "piso de chegada" in frente
    planta = textos(svg_da_cena(dem.planta(r)))
    assert f"{entrada.afastamento_mm:.0f}" in planta
    assert ("Ø 700" in planta) is entrada.gaiola


def test_registro_e_memorial():
    r = em.calcular(PADRAO)
    registro = json.loads(json.dumps(em.registro(r, figuras=dem.figuras_para_o_registro(r))))
    assert registro["modulo_id"] == em.MODULO_ID
    assert registro["status"] == "Atende"
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == "" and [i["titulo"] for i in imagens] == [
        "Escada marinheiro — vista de frente",
        "Escada marinheiro — planta",
    ]
    assert any("NR-12, Anexo III" in ref for ref in registro["referencias"])
    assert any("critério do programa" in p for p in registro["premissas"])


def test_menu_modulo_e_juntar_o_projeto():
    item = item_da_pagina(PAGINA)
    assert item is not None and item.titulo == "Escada marinheiro"
    modulo = next(m for m in listar_modulos() if m.id == em.MODULO_ID)
    assert modulo.pagina == PAGINA and modulo.grupo_navegacao == "Estrutura metálica"
    from core import memorial_do_projeto as mp

    registro = {"modulo_id": em.MODULO_ID, "titulo": "Escada marinheiro — H = 6,00 m"}
    assert mp.ETAPAS[mp.indice_da_etapa(registro)].nome == "Escadas e acessos"


# ------------------------------------------------------------------ página
def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def test_todo_texto_de_ajuda_e_usado_e_termina_com_ponto():
    usadas = set(re.findall(r'"([a-z_0-9]+)"', (RAIZ / PAGINA).read_text(encoding="utf-8"))) & set(
        AJUDA
    )
    assert usadas == set(AJUDA), set(AJUDA) - usadas
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and texto[-1] in ".!:", chave


def test_pagina_tem_ajuda_em_tudo_e_os_numeros_do_nucleo(banco_isolado):
    t = abrir(em_lances=2, em_ambiente=True)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    t = abrir()
    r = em.calcular(PADRAO)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Status"] == "OK"
    assert metricas["Aproveitamento"] == f"{100 * r.aproveitamento_maximo:.0f} %"
    assert str(metricas["Barras por lance"]) == str(r.barras_por_lance)
    assert len(t.get("image")) == 2


def test_sem_gaiola_acima_de_3_5_m_avisa_e_registra(banco_com_projeto):
    t = abrir(em_gaiola=False)
    assert any("exige gaiola" in w.value for w in t.warning)
    assert {m.label: m.value for m in t.metric}["Status"] == "NÃO OK"
    t.button(key="registrar_escada_marinheiro").click().run()
    assert not t.exception
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == em.MODULO_ID
    ]
    assert len(registros) == 1 and registros[0]["status"] == "Não atende"


def test_guia_tem_o_capitulo_com_o_exemplo(banco_isolado):
    r = em.calcular(PADRAO)
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Escada marinheiro"
    t.run()
    assert "Escada marinheiro" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"{r.barras_por_lance} barras" in esperado
