"""Emendas dos pilares do modelo: onde ficam, os esforços no ponto da emenda, a entrada da Emenda de
pilar, a verificação de todas e as duas páginas (Esforços do modelo e Emenda de pilar)."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import colunas_do_modelo as cdm
from core import emenda_pilar as ep
from core import emendas_do_modelo as edm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests import portico_3d_teste01 as t
from tests.test_colunas_do_modelo import corpo
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_nucleo_esforcos_ponta_a_ponta import montar

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PILAR = "Viga-1(Pilar[1])"
ELU = [comb.ELU_NORMAL]


@pytest.fixture(scope="module")
def portico():
    dados, _, geometria = montar()
    plano = t.plano()
    leituras = ld.ler_barras(dados, geometria, plano)
    return dados, geometria, plano, leituras


# ------------------------------------------------------------------ onde ficam
def _leitura(barra, c):
    return ld.LeituraDaBarra(barra, c, ld.TIPO_PILAR, "", "", "", c.comprimento_m, 4, ("", ""), "")


def test_dois_pilares_em_pe_que_se_encontram_sao_uma_emenda():
    baixo = corpo("PB", (0, 0, 0), (0, 3, 0), (1.0, 0.0, 0.0))
    cima = corpo("PC", (0, 3.02, 0), (0, 6, 0), (1.0, 0.0, 0.0))  # 2 cm de folga no esqueleto
    longe = corpo("PL", (5, 3.2, 0), (5, 6, 0), (1.0, 0.0, 0.0))
    dados = em.com_membros(
        em.EsforcosDoModelo(),
        {
            "PB": em.ConfiguracaoDoMembro(perfil="W 200 x 46,1 (H)", tipo=ld.TIPO_PILAR),
            "PC": em.ConfiguracaoDoMembro(perfil="W 200 x 35,9 (H)", tipo=ld.TIPO_PILAR),
            "PL": em.ConfiguracaoDoMembro(perfil="W 200 x 35,9 (H)", tipo=ld.TIPO_PILAR),
        },
    )
    leituras = [_leitura("PB", baixo), _leitura("PC", cima), _leitura("PL", longe)]
    (emenda,) = edm.achar_emendas(dados, leituras)
    assert (emenda.barra, emenda.barra_inferior, emenda.altura_m) == ("PC", "PB", 0.0)
    assert emenda.origem == edm.ORIGEM_TROCA
    assert (emenda.perfil_superior, emenda.perfil_inferior) == ("W 200 x 35,9 (H)",
                                                                "W 200 x 46,1 (H)")  # fmt: skip
    assert emenda.cota_m == pytest.approx(3.02) and "cota 3,02 m" in emenda.nome
    # tirada pelo usuário, some; a informada aparece com a altura a partir do pé
    dados = edm.com_informadas_e_tiradas(dados, [("PL", 1.2)], [emenda.chave])
    (informada,) = edm.achar_emendas(dados, leituras)
    assert informada.origem == edm.ORIGEM_INFORMADA and informada.cota_m == pytest.approx(4.4)
    assert len(edm.achar_emendas(dados, leituras, com_as_tiradas=True)) == 2
    # gravado e lido de volta no projeto
    volta = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados))))
    assert edm.emendas_informadas(volta) == [("PL", 1.2)]
    assert edm.emendas_tiradas(volta) == {emenda.chave}


def test_posicoes_dos_pontos_pela_ordem_dos_elementos():
    pontos = [em.PontoDeEsforco(e, f, 0, 0, 0, 0, 0, 0)
              for e, f in (("7", "1"), ("7", "2"), ("8", "1"), ("8", "2"), ("9", "1"))]  # fmt: skip
    assert edm.posicoes_dos_pontos(pontos, 3.0) == pytest.approx([0.0, 1.0, 1.0, 2.0, 2.5])


# ------------------------------------------------------------------ esforços no ponto da emenda
def _esperado(dados, plano, j):
    """A combinação do ponto j da lista, à mão: Σ fator·caso, com o B₂ do tipo Pilar."""
    preparo = edm.preparar(dados, plano, ELU)
    b2 = dados.parametros_do_tipo(ld.TIPO_PILAR).b2
    saida = []
    for fatores in preparo.fatores:
        v = [sum(f * caso.membros[PILAR][j].vetor()[c] for f, caso in
                 zip(fatores, preparo.casos, strict=True)) * b2 for c in range(6)]  # fmt: skip
        saida.append(v)
    return saida


def test_no_pe_e_o_ponto_do_arquivo_e_no_meio_interpola(portico):
    dados, _, plano, leituras = portico
    barra = next(b for b in t.BARRAS if b.viga == PILAR)
    assert barra.inicio[1] < barra.fim[1]  # a lista começa no pé
    dados = edm.com_informadas_e_tiradas(dados, [(PILAR, 0.0), (PILAR, 0.25), (PILAR, 0.5)], [])
    emendas = edm.achar_emendas(dados, leituras)
    preparo = edm.preparar(dados, plano, ELU)
    no_pe, quarto, meio = edm.ler_esforcos(dados, leituras, preparo, emendas)
    cfg = dados.membros[PILAR]
    forte_v, forte_m, fraco_m = (1, 4, 3) if cfg.eixo_forte == em.EIXO_M2 else (2, 3, 4)
    pe, j1, j2 = _esperado(dados, plano, 0), _esperado(dados, plano, 1), _esperado(dados, plano, 2)
    for caso, v in zip(no_pe.casos, pe, strict=True):
        assert caso.N == pytest.approx(-v[0]) and caso.V == pytest.approx(v[forte_v])
        assert caso.Mx == pytest.approx(v[forte_m]) and caso.My == pytest.approx(v[fraco_m])
    assert "no pé do pilar" in no_pe.como and "B₂ = 1,10" in no_pe.como
    # 0,25 m: entre o pé (0) e o fim do 1º elemento (0,5 m, 4 elementos em 2 m)
    for caso, a, b in zip(quarto.casos, pe, j1, strict=True):
        assert caso.Mx == pytest.approx((a[forte_m] + b[forte_m]) / 2)
    assert "interpolado entre 0,00 e 0,50" in quarto.como
    # 0,5 m é um nó: vale o ponto de cima (o começo do 2º elemento)
    for caso, v in zip(meio.casos, j2, strict=True):
        assert caso.Mx == pytest.approx(v[forte_m])


def test_emenda_acima_do_pilar_e_recusada(portico):
    dados, _, plano, leituras = portico
    dados = edm.com_informadas_e_tiradas(dados, [(PILAR, 2.5)], [])
    (lido,) = edm.ler_esforcos(dados, leituras, edm.preparar(dados, plano, ELU),
                               edm.achar_emendas(dados, leituras))  # fmt: skip
    assert not lido.lidos and "passa do comprimento" in lido.motivo


# ------------------------------------------------------------------ a entrada da Emenda de pilar
def test_entrada_montada_pelo_esqueleto_e_pela_flambagem(portico):
    dados, geometria, plano, leituras = portico
    dados = edm.com_informadas_e_tiradas(dados, [(PILAR, 0.8)], [])
    (lido,) = edm.ler_esforcos(dados, leituras, edm.preparar(dados, plano, ELU),
                               edm.achar_emendas(dados, leituras))  # fmt: skip
    m = edm.montar_entrada(lido, dados, geometria, leituras, ep.EntradaEmenda())
    e = m.entrada
    assert e is not None and e.perfil_superior == t.PILAR == e.perfil_inferior
    pilar = cdm.ler_pilar(geometria, next(x for x in leituras if x.barra == PILAR).corpo, "Y",
                          "pino")  # fmt: skip
    x, y = cdm.trechos_do_pilar(pilar)
    assert e.Lx == pytest.approx(x.governa.kl_mm) and e.Ly == pytest.approx(y.governa.kl_mm)
    assert e.a == pytest.approx(800.0) and e.vao_b == pytest.approx(2000.0)
    esperado = edm.nc_rd_do_pilar(t.PILAR, ep.ACOS[e.aco_perfis][0], e.Lx, e.Ly, dados.norma)
    assert e.Nc_Rd_informado == pytest.approx(esperado) and esperado > 0
    assert len(e.casos) == len(lido.casos)
    # o vão próprio entra na situação b: M_b = H·a·(L − a)/L com L = 2000 mm
    r = ep.calcular(replace(e, criterio_minimo=ep.MINIMO_SO_B, diametro='1/2"', bp=100.0, nl=2,
                            g=50.0, bw=100.0, sh=40.0, sv=40.0))  # fmt: skip
    H = 0.02 * esperado
    assert r.minimo.Mb == pytest.approx(H * 800 * 1200 / 2000 / 1000)


def test_perfil_fora_das_familias_fica_pendente(portico):
    dados, geometria, plano, leituras = portico
    dados = edm.com_informadas_e_tiradas(dados, [(PILAR, 0.8)], [])
    membros = dict(dados.membros)
    membros[PILAR] = replace(membros[PILAR], perfil='L 3" x 1/4"')
    dados = replace(dados, membros=membros)
    (lido,) = edm.ler_esforcos(dados, leituras, edm.preparar(dados, plano, ELU),
                               edm.achar_emendas(dados, leituras))  # fmt: skip
    m = edm.montar_entrada(lido, dados, geometria, leituras, ep.EntradaEmenda())
    assert m.entrada is None and "fora das famílias" in m.motivo


# ------------------------------------------------------------------ sugerir as talas
def test_sugerir_as_talas_atende_o_caso_de_validacao():
    s = ep.sugerir_talas(ep.EntradaEmenda())
    assert s.cabe and s.atende and not s.resultado.itens_a_verificar
    e = s.entrada
    assert (e.bp, e.tp, e.nl, e.s, e.ep, e.ec) == (200.0, 12.5, 2, 60.0, 40.0, 40.0)
    assert e.ec + (e.nr - 1) * e.s + e.ep >= 225  # a continuidade do SCI P207 5.2.4


def test_sugerir_sobe_as_fileiras_e_avisa_o_que_e_do_pilar():
    forte = ep.com(ep.EntradaEmenda(), casos=(ep.CasoEsforco("c", -300.0, 60.0, 120.0),))
    s = ep.sugerir_talas(forte)
    assert s.atende and s.entrada.nr >= 4
    contato = ep.com(ep.EntradaEmenda(), casos=(ep.CasoEsforco("c", 1500.0, 120.0, 90.0),))
    s = ep.sugerir_talas(contato)
    assert not s.atende and any("próprio pilar (12)" in n for n in s.notas)
    assert s.entrada.tp == 12.5  # não engrossou a tala à toa


def test_sugerir_recusa_o_parafuso_que_nao_cabe():
    estreito = ep.com(ep.EntradaEmenda(), perfil_superior="W 200 x 15,0",
                      perfil_inferior="W 200 x 15,0")  # fmt: skip
    s = ep.sugerir_talas(estreito)
    assert not s.cabe and s.resultado is None and "parafuso menor" in s.notas[0]


# ------------------------------------------------------------------ todas as emendas
def test_verificar_todas_e_registrar(portico):
    dados, geometria, plano, _ = portico
    dados = edm.com_informadas_e_tiradas(dados, [(PILAR, 0.0), ("Viga-2(Pilar[2])", 1.0)], [])
    padrao = ep.EntradaEmenda(diametro='1/2"')
    verificadas, _ = edm.verificar_emendas(dados, geometria, plano, ELU, padrao)
    assert len(verificadas) == 2
    assert all(v.status in ("OK", "ALERTA") for v in verificadas), [v.motivo for v in verificadas]
    # 1/2" é menor que o mínimo do critério Anglo: atende, mas fica a verificar
    assert all(v.status == "ALERTA" for v in verificadas)
    linhas = edm.linhas_da_tabela(verificadas)
    assert len(linhas) == 2 and all(isinstance(x[8], float) for x in linhas)
    registro = json.loads(json.dumps(edm.registro_das_emendas(verificadas, padrao, ELU)))
    assert registro["modulo_id"] == ep.MODULO_ID and registro["status"] == "Atenção"
    assert registro["resultados"]["tabelas_memorial"][0]["cabecalhos"] == list(edm.COLUNAS)
    # com 5/8" a mesa de 100 mm do W 150 x 13,0 não comporta duas linhas: sem dados, com o porquê
    verificadas, _ = edm.verificar_emendas(dados, geometria, plano, ELU, ep.EntradaEmenda())
    assert all(v.status == edm.STATUS_PENDENTE and "parafuso menor" in v.motivo
               for v in verificadas)  # fmt: skip


# ------------------------------------------------------------------ páginas
def _projeto_com_o_portico(emendas):
    dados, _, geometria = montar()
    dados = edm.com_informadas_e_tiradas(dados, emendas, [])
    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(t.plano())
    projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    projeto["geometria_do_modelo"] = ld.para_dicionario(geometria)
    salvar_projeto(projeto, motivo="teste")


def _abrir(pagina, **estado) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    at.switch_page(pagina)
    for chave, valor in estado.items():
        at.session_state[chave] = valor
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def test_esforcos_do_modelo_mostra_as_emendas(banco_com_projeto):
    _projeto_com_o_portico([(PILAR, 1.0)])
    at = _abrir("app_pages/esforcos_modelo.py")
    assert "9. Emendas dos pilares" in [s.value for s in at.subheader]
    tabela = next(d.value for d in at.dataframe if "Como foi lido" in d.value.columns)
    assert set(tabela["Emenda"]) == {f"{PILAR} a 1,00 m do pé"}
    assert not math.isnan(float(tabela["N (kN)"].iloc[0]))


def test_emenda_de_pilar_traz_do_modelo_sugere_e_verifica_todas(banco_com_projeto):
    _projeto_com_o_portico([(PILAR, 1.0)])
    at = _abrir("app_pages/emenda_pilar.py", emp_diam='1/2"')
    at.button(key="emp_trazer").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["emp_perfil_s"] == t.PILAR
    assert at.session_state["emp_vao_b"] == pytest.approx(2000.0)
    assert any("Trazido do modelo" in i.value for i in at.info)
    at.button(key="emp_sugerir").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["emp_bp"] == 100.0 and at.session_state["emp_nl"] == 2
    at.toggle(key="emp_verificar_todas").set_value(True).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    tabela = next(d.value for d in at.dataframe if "Talas da mesa" in d.value.columns)
    assert len(tabela) == 1
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in at.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
