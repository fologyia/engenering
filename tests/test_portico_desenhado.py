"""Peça desenhada lida como pórtico: N, V e M nas barras e as reações com apoio de sobra.

As contas de mão vêm das tabelas clássicas de vigas e pórticos (viga contínua de dois vãos, pórtico
biengastado com carga uniforme) e, nas peças isostáticas, da própria estática.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import elementos_catalogo as cat
from core import equilibrio_corpo as eq
from core import portico_desenhado as pdes
from core import portico_figuras as pf
from core import portico_plano as pp
from core.elementos_base import calcular_caso
from core.elementos_equilibrio import (
    CASO_EQUILIBRIO,
    ROTULAS,
    marcas_para_a_tela,
    motivo_sem_barras,
)
from core.equilibrio_modelos import MODELOS, POR_NOME

APP = str(Path(__file__).resolve().parents[1] / "app.py")
T, A, C = eq.Trecho, eq.Apoio, eq.Carga


def _valores(nome: str, **mais) -> dict:
    m = POR_NOME[nome]
    return {
        **CASO_EQUILIBRIO.padroes(),
        "comprimento": m.comprimento,
        "forca": m.forca,
        **m.dados(),
        **mais,
    }


def _problema(nome: str) -> tuple[eq.Problema, eq.Unidades]:
    m = POR_NOME[nome]
    d = m.dados()
    u = eq.Unidades(m.comprimento, m.forca)
    return eq.problema_das_tabelas(d["trechos"], d["apoios"], d["cargas"], d["cortes"], u), u


# ---------------------------------------------------------------------------
# Apoio inclinado no núcleo do pórtico
# ---------------------------------------------------------------------------


def _viga_com_rolete(giro: float) -> pp.Portico:
    s = pp.Secao("s", 2e-3, 8e-6)
    return pp.Portico(
        (pp.No("A", 0, 0), pp.No("M", 2, 0), pp.No("B", 4, 0)),
        (pp.Barra("b1", "A", "M", s), pp.Barra("b2", "M", "B", s)),
        (pp.pino("A"), pp.Apoio("B", True, False, False, giro)),
        (pp.CargaNodal("M", fy=-10.0),),
    )


def test_rolete_inclinado_empurra_so_na_direcao_dele():
    r = pp.resolver(_viga_com_rolete(60.0))
    b = r.reacao("B")
    assert b.ry == pytest.approx(5.0)
    assert b.rx == pytest.approx(5.0 / math.tan(math.radians(60.0)))
    assert r.reacao("A").rx == pytest.approx(-b.rx)
    # O nó B só anda de lado em relação ao apoio: nada na direção de 60°.
    dx, dy, _ = r.deslocamentos["B"]
    assert dx * math.cos(math.radians(60)) + dy * math.sin(math.radians(60)) == pytest.approx(
        0.0, abs=1e-12
    )
    assert r.residuo_kN < 1e-9


def test_rolete_a_90_graus_e_o_rolete_de_sempre():
    inclinado = pp.resolver(_viga_com_rolete(90.0))
    reto = pp.resolver(
        pp.Portico(
            _viga_com_rolete(0).nos,
            _viga_com_rolete(0).barras,
            (pp.pino("A"), pp.rolete("B")),
            _viga_com_rolete(0).cargas_nodais,
        )
    )
    assert inclinado.reacao("B").ry == pytest.approx(reto.reacao("B").ry)
    assert inclinado.barra("b1").m_max.m == pytest.approx(reto.barra("b1").m_max.m)


def test_apoio_inclinado_vai_e_volta_do_registro():
    p = _viga_com_rolete(35.0)
    dados = pp.para_dicionario(p)
    assert pp.de_dicionario(dados).apoios == p.apoios
    # Registro antigo, sem o ângulo: apoio reto.
    dados["apoios"] = [a[:4] for a in dados["apoios"]]
    assert pp.de_dicionario(dados).apoios[1].giro_graus == 0.0


def test_dois_apoios_inclinados_diferentes_no_mesmo_no_sao_recusados():
    p = _viga_com_rolete(30.0)
    p = pp.Portico(
        p.nos, p.barras, (*p.apoios, pp.Apoio("B", True, False, False, 80.0)), p.cargas_nodais
    )
    with pytest.raises(pp.PorticoInvalido, match="inclinados"):
        pp.resolver(p)


# ---------------------------------------------------------------------------
# Do desenho para o pórtico
# ---------------------------------------------------------------------------

ISOSTATICOS = [
    m.nome for m in MODELOS if m.nome not in ("Tampa com duas dobradiças", "Máquina sobre dois pés")
]


@pytest.mark.parametrize("nome", ISOSTATICOS)
def test_modelos_isostaticos_dao_as_reacoes_da_estatica(nome):
    problema, u = _problema(nome)
    solucao = eq.resolver(problema)
    if not solucao.isostatica:
        pytest.skip("apoio de sobra: a estática não define")
    analise = pdes.analisar(problema, solucao, newton=u.newton)
    tolerancia = 1e-7 * solucao.referencia
    for do_portico, da_estatica in zip(analise.reacoes, solucao.reacoes, strict=True):
        assert do_portico.fx == pytest.approx(da_estatica.fx, abs=tolerancia)
        assert do_portico.fy == pytest.approx(da_estatica.fy, abs=tolerancia)
        assert do_portico.m == pytest.approx(da_estatica.m, abs=tolerancia)


def test_viga_continua_de_dois_vaos_iguais():
    """Tabela: R_A = 3qL/8, R_B = 10qL/8 e M_B = −qL²/8."""
    problema, u = _problema("Viga contínua em três apoios")
    analise = pdes.analisar(problema, eq.resolver(problema), newton=u.newton)
    q, vao = 5000.0, 3.0
    a, b, c = analise.reacoes
    assert a.fy == pytest.approx(3 * q * vao / 8)
    assert b.fy == pytest.approx(10 * q * vao / 8)
    assert c.fy == pytest.approx(3 * q * vao / 8)
    assert pdes.hiperestatica(analise) == 1
    momentos = [rb.m_max.m for rb in analise.resultado.barras]
    assert min(momentos) * u.newton == pytest.approx(-q * vao**2 / 8)


def test_portico_biengastado_com_carga_uniforme_na_viga():
    """Tabela (sem deformação axial): H = wL²/(4h(k+2)) e M_base = wL²/(12(k+2)), k = h/L."""
    w, vao, h = 8000.0, 5.0, 3.0
    problema = eq.Problema(
        (A("A", eq.ENGASTE, 0, 0), A("B", eq.ENGASTE, vao, 0)),
        (C("q1", eq.DISTRIBUIDA, 0, h, w, -90.0, vao, h, w),),
        (T(0, 0, 0, h), T(0, h, vao, h), T(vao, h, vao, 0)),
    )
    rigida_no_eixo = pdes.Rigidez("s", area_m2=50.0)
    analise = pdes.analisar(problema, None, padrao=rigida_no_eixo)
    k = h / vao
    a, b = analise.reacoes
    assert a.fy == pytest.approx(w * vao / 2)
    assert a.fx == pytest.approx(w * vao**2 / (4 * h * (k + 2)), rel=1e-4)
    assert b.fx == pytest.approx(-a.fx)
    assert abs(a.m) == pytest.approx(w * vao**2 / (12 * (k + 2)), rel=1e-4)
    assert pdes.hiperestatica(analise) == 3


def test_trecho_com_apoio_e_carga_no_meio_vira_varias_barras():
    problema, u = _problema("Viga com dois apoios")
    analise = pdes.analisar(problema, None, newton=u.newton)
    nomes = [rb.barra.nome for rb in analise.resultado.barras]
    assert nomes == ["B1a", "B1b", "B1c"]
    assert set(analise.trecho_da_barra.values()) == {1}


def test_esforco_na_secao_bate_com_o_do_corpo_rigido():
    """Apoio distribuído: as reações entram como carga e o M no meio da barra é o do corte."""
    problema = eq.Problema(
        (A("A", eq.DISTRIBUIDO, 0, 0, 90.0, 4.0, 0.0, 0.3),),
        (C("F1", eq.FORCA, 2.4, 0, 20e3, -90.0),),
        (T(0, 0, 4, 0),),
        (eq.Corte("S1", 1.2, 0.0),),
    )
    solucao = eq.resolver(problema)
    analise = pdes.analisar(problema, solucao)
    assert analise.caminho == pdes.PELAS_REACOES
    corte = eq.esforco_no_corte(solucao, problema.cortes[0])
    meio = analise.resultado.barras[0].pontos[20]
    assert meio.x == pytest.approx(1.2)
    assert meio.m * 1000 == pytest.approx(corte.m, rel=1e-9)
    assert meio.v * 1000 == pytest.approx(corte.v, rel=1e-9)


def test_apoio_simples_que_descola_sai_da_conta():
    problema = eq.Problema(
        (A("A", eq.PINO, 0, 0), A("B", eq.SIMPLES, 2, 0, 90.0), A("C", eq.ROLETE, 4, 0, 90.0)),
        (C("F1", eq.FORCA, 2.5, 0, 10e3, 90.0),),
        (T(0, 0, 4, 0),),
    )
    analise = pdes.analisar(problema, None)
    a, b, c = analise.reacoes
    assert b.solto and b.modulo == 0.0
    assert a.fy == pytest.approx(-3750.0)
    assert c.fy == pytest.approx(-6250.0)
    assert any("não trabalha" in aviso for aviso in analise.avisos)


def test_apoio_simples_que_empurra_continua_na_conta():
    problema = eq.Problema(
        (A("A", eq.PINO, 0, 0), A("B", eq.SIMPLES, 2, 0, 90.0), A("C", eq.ROLETE, 4, 0, 90.0)),
        (C("F1", eq.FORCA, 2.5, 0, 10e3, -90.0),),
        (T(0, 0, 4, 0),),
    )
    analise = pdes.analisar(problema, None)
    assert not any(r.solto for r in analise.reacoes)
    assert sum(r.fy for r in analise.reacoes) == pytest.approx(10e3)
    assert analise.reacoes[1].fy > 0.0


def test_cabo_e_rolete_no_mesmo_ponto_repartem_a_reacao():
    problema, u = _problema("Peça em rampa")
    solucao = eq.resolver(problema)
    analise = pdes.analisar(problema, solucao, newton=u.newton)
    for do_portico, da_estatica in zip(analise.reacoes, solucao.reacoes, strict=True):
        assert do_portico.fx == pytest.approx(da_estatica.fx, abs=1e-6)
        assert do_portico.fy == pytest.approx(da_estatica.fy, abs=1e-6)


def test_rotula_na_ponta_tira_o_momento_do_engaste():
    """Biengastada com rótula no fim vira engastada-apoiada: R_B = 5P/16 com a carga no meio."""
    problema = eq.Problema(
        (A("A", eq.ENGASTE, 0, 0), A("B", eq.ENGASTE, 4, 0)),
        (C("F1", eq.FORCA, 2, 0, 16e3, -90.0),),
        (T(0, 0, 4, 0),),
    )
    com_rotula = pdes.analisar(problema, None, rigidezes=[pdes.Rigidez(rotula_fim=True)])
    assert com_rotula.resultado.barras[-1].pontos[-1].m == pytest.approx(0.0, abs=1e-9)
    assert com_rotula.reacoes[1].fy == pytest.approx(5 * 16e3 / 16)
    sem_rotula = pdes.analisar(problema, None)
    assert sem_rotula.reacoes[1].fy == pytest.approx(8e3)
    assert abs(sem_rotula.reacoes[0].m) == pytest.approx(16e3 * 4 / 8)


@pytest.mark.parametrize(
    ("problema", "trecho_da_mensagem"),
    [
        (
            eq.Problema((A("A", eq.PINO, 0, 0),), (C("F1", eq.FORCA, 1, 0, 1.0),)),
            "Desenhe a peça com trechos",
        ),
        (
            eq.Problema(
                (A("A", eq.ENGASTE, 0, 0),),
                (C("F1", eq.FORCA, 1, 1, 1.0),),
                (T(0, 0, 2, 0),),
            ),
            "não está sobre nenhum trecho",
        ),
        (
            eq.Problema(
                (A("A", eq.ENGASTE, 0, 0),),
                (C("F1", eq.FORCA, 5, 0, 1.0),),
                (T(0, 0, 2, 0), T(4, 0, 6, 0)),
            ),
            "2 partes que não se tocam",
        ),
        (
            eq.Problema(
                (A("A", eq.ENGASTE, 0, 0),),
                (C("q1", eq.DISTRIBUIDA, 1, 0, 1.0, -90.0, 3, 0, 1.0),),
                (T(0, 0, 2, 0), T(3, 0, 3, 1), T(2, 0, 2, 1), T(2, 1, 3, 1)),
            ),
            "fora dos trechos",
        ),
        (
            eq.Problema(
                (A("A", eq.PINO, 0, 0), A("B", eq.PINO, 0, 0)),
                (C("F1", eq.FORCA, 2, 0, 1.0),),
                (T(0, 0, 2, 0),),
            ),
            "mesmo ponto",
        ),
        (
            eq.Problema(
                (A("A", eq.ROLETE, 0, 0), A("B", eq.ROLETE, 2, 0)),
                (C("F1", eq.FORCA, 1, 0, 1.0, 0.0),),
                (T(0, 0, 2, 0),),
            ),
            "hipostática",
        ),
    ],
)
def test_desenho_que_nao_vira_portico_diz_o_que_falta(problema, trecho_da_mensagem):
    with pytest.raises(pdes.SemDiagramas, match=trecho_da_mensagem):
        pdes.analisar(problema, None)


def test_trechos_que_so_se_cruzam_nao_se_ligam():
    cruz = eq.Problema(
        (A("A", eq.ENGASTE, 0, 1),),
        (C("F1", eq.FORCA, 1, 2, 1.0),),
        (T(0, 1, 2, 1), T(1, 0, 1, 2)),
    )
    with pytest.raises(pdes.SemDiagramas, match="partes que não se tocam"):
        pdes.analisar(cruz, None)


def test_ponta_no_meio_de_outro_trecho_liga():
    te = eq.Problema(
        (A("A", eq.ENGASTE, 0, 1),),
        (C("F1", eq.FORCA, 1, 2, 100.0, 0.0),),
        (T(0, 1, 2, 1), T(1, 1, 1, 2)),
    )
    analise = pdes.analisar(te, None)
    assert analise.reacoes[0].fx == pytest.approx(-100.0)
    assert analise.reacoes[0].m == pytest.approx(100.0)  # 100 N a 1 m acima do engaste


# ---------------------------------------------------------------------------
# O caso e a tela
# ---------------------------------------------------------------------------


def test_figuras_saem_na_unidade_da_tela():
    problema, u = _problema("Alavanca")
    analise = pdes.analisar(problema, None, newton=u.newton)
    with pf.unidade_de_forca(u.forca):
        figuras = pf.figuras_do_portico(analise.resultado, tensao=False, apenas=["reacoes", "M"])
    assert all("kN" not in f.legenda for f in figuras)
    assert "N·m" in figuras[1].legenda
    # Fora do bloco, o padrão volta.
    assert "kN" in pf.figura_reacoes(analise.resultado).legenda


def test_caso_do_portico_traz_tabelas_figuras_e_reacoes_pela_rigidez():
    v = _valores("Pórtico com as bases engastadas")
    r = calcular_caso(CASO_EQUILIBRIO, v)
    titulos = [t.titulo for t in r.tabelas]
    assert titulos[0] == "Reações com a rigidez das barras"
    assert "Reações nos apoios" not in titulos
    assert "Esforços nas barras" in titulos
    assert [f.titulo for f in r.figuras] == [
        "Peça",
        "Momento fletor",
        "Esforço cortante",
        "Esforço normal",
        "Reações",
        "Deformada",
    ]
    linhas = r.tabelas[0].linhas
    assert sum(l["Rx (kN)"] for l in linhas) == pytest.approx(-12.0)
    assert sum(l["Ry (kN)"] for l in linhas) == pytest.approx(40.0)
    assert any("rigidez das barras" in a for a in r.alertas)
    assert motivo_sem_barras(v) == ""
    marcas = marcas_para_a_tela(v)
    assert [m["fy"] for m in marcas["reacoes"]] == pytest.approx([l["Ry (kN)"] for l in linhas])


def test_perfil_muda_a_divisao_no_portico_e_nao_na_peca_isostatica():
    base = _valores("Pórtico com as bases em pino")
    rigido = [{"trecho": 2, "perfil": "", "rotulas": ROTULAS[3]}]
    com_rotulas = calcular_caso(CASO_EQUILIBRIO, {**base, "barras": rigido})
    sem = calcular_caso(CASO_EQUILIBRIO, base)

    def empuxo(resultado):
        tabela = next(t for t in resultado.tabelas if "rigidez" in t.titulo)
        return tabela.linhas[1]["Rx (kN)"]

    # Viga rotulada nas duas pontas com colunas em pino embaixo: mecanismo.
    assert "Esforços nas barras" not in [t.titulo for t in com_rotulas.tabelas]
    assert motivo_sem_barras({**base, "barras": rigido})
    assert empuxo(sem) == pytest.approx(-9.965, abs=2e-3)


def test_perfil_desconhecido_vira_mensagem():
    v = _valores(
        "Viga com dois apoios",
        barras=[{"trecho": 1, "perfil": "Perfil que não existe", "rotulas": ROTULAS[0]}],
    )
    with pytest.raises(ValueError, match="não está no catálogo"):
        calcular_caso(CASO_EQUILIBRIO, v)


@pytest.mark.parametrize("modelo", MODELOS, ids=lambda m: m.nome)
def test_todo_modelo_calcula_e_explica_quando_nao_ha_barras(modelo):
    v = _valores(modelo.nome)
    r = calcular_caso(CASO_EQUILIBRIO, v)
    tem = "Esforços nas barras" in [t.titulo for t in r.tabelas]
    assert tem == (motivo_sem_barras(v) == "")
    assert tem == (len(r.figuras) > 1)


def test_caso_saiu_do_painel_e_o_atalho_antigo_sabe_para_onde_ir():
    assert "equilibrio_peca" not in cat.CASOS
    assert not cat.existe("equilibrio_peca")
    assert cat.MUDARAM_DE_PAGINA["equilibrio_peca"] == "app_pages/vigas_eixos.py"
    for grupos in cat.GRUPOS.values():
        assert all("equilibrio_peca" not in ids for ids in grupos.values())


def _abrir() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.session_state["vigas_abrir_peca"] = True
    at.switch_page("app_pages/vigas_eixos.py")
    return at.run()


def test_tela_mostra_os_diagramas_do_portico():
    at = _abrir()
    at.selectbox(key="eq_modelo").set_value("Pórtico com as bases engastadas").run()
    assert not at.exception
    assert any("Esforços nas barras" in m.value for m in at.markdown)
    assert at.session_state["eq_diagrama"] == "Momento fletor"
    assert any("rigidez das barras" in w.value for w in at.warning)
    assert at.selectbox(key="eq_perfil").help


def test_tela_diz_por_que_nao_ha_diagramas():
    at = _abrir()
    at.selectbox(key="eq_modelo").set_value("Máquina sobre dois pés").run()
    assert not at.exception
    assert any("não está sobre nenhum trecho" in i.value for i in at.info)


def test_rotula_escolhida_na_tela_entra_na_conta():
    at = _abrir()
    at.selectbox(key="eq_modelo").set_value("Pórtico com as bases engastadas").run()
    at.session_state["eq_barras"] = [{"trecho": 2, "perfil": "", "rotulas": ROTULAS[3]}]
    at.run()
    assert not at.exception
    # Viga rotulada nas duas pontas: carga uniforme dá qL²/8 no meio dela.
    quadro = next(d.value for d in at.dataframe if "M maior (kN·m)" in d.value.columns)
    assert quadro["M maior (kN·m)"].abs().max() == pytest.approx(8 * 5**2 / 8)
