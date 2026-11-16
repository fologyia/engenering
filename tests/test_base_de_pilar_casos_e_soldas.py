"""Placa de base: várias combinações (envoltória), soldas e a cortante no concreto (ACI 318-19)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import base_de_pilar as bp
from core import base_de_pilar_soldas as bs
from core import placa_base_pilares as pbp
from core import record_charts
from core.verificacao import ORDEM_STATUS
from tests.test_esforcos_modelo import PILAR, plano_do_portico
from tests.test_quadro_fundacoes import PILAR_2, portico

PADRAO = bp.EntradaBase()  # W 250 x 32,7 (d 258, b_f 146, t_w 6,1, t_f 9,1), tipo 1, 4 × Ø 1"
CASOS = (
    bp.CasoDeCarga("compressão", 600.0, 15.0, 0.0, 25.0),
    bp.CasoDeCarga("vento", -80.0, 25.0, 0.0, 40.0),
    bp.CasoDeCarga("momento", 200.0, 40.0, 0.0, 35.0),
)
VARIAS = replace(PADRAO, casos=CASOS)
E70 = 485.0


def _linha(r: bp.ResultadoBase, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def _tem(r: bp.ResultadoBase, inicio: str) -> bool:
    return any(v.nome.startswith(inicio) for v in r.verificacoes)


def _sozinho(e: bp.EntradaBase, caso: bp.CasoDeCarga, **mais) -> bp.ResultadoBase:
    return bp.calcular(
        replace(
            e,
            casos=(),
            n_sd_kN=caso.n_sd_kN,
            m_sd_kNm=caso.m_sd_kNm,
            m_sd_y_kNm=caso.m_sd_y_kNm,
            v_sd_kN=caso.v_sd_kN,
            **mais,
        )
    )


# ============================================================================ envoltória
def test_envoltoria_e_o_pior_de_cada_combinacao_sozinha():
    r = bp.calcular(VARIAS)
    perna = r.perna_do_pilar  # a mesma perna em todas (a solda é uma só)
    sozinhos = {c.nome: _sozinho(VARIAS, c, perna_pilar_mm=perna) for c in CASOS}
    assert {i.caso.nome for i in r.casos} == set(sozinhos)
    for v in r.verificacoes:
        if v.aproveitamento is None:
            continue
        valores = [
            s_v.aproveitamento
            for s in sozinhos.values()
            for s_v in s.verificacoes
            if s_v.nome == v.nome and s_v.aproveitamento is not None
        ]
        assert v.aproveitamento == pytest.approx(max(valores)), v.nome
    # o caso de cada combinação sai dela: compressão C1/C2, vento T2/T3, momento C2/C3
    casos = {i.caso.nome: i.resultado.caso for i in r.casos}
    assert casos["compressão"].startswith("C") and casos["vento"].startswith("T")
    assert r.t_p_min == pytest.approx(max(s.t_p_min for s in sozinhos.values()))
    assert r.status == max((s.status for s in sozinhos.values()), key=ORDEM_STATUS.get)


def test_a_combinacao_que_manda_vem_entre_colchetes_e_a_que_governa_e_desenhada():
    r = bp.calcular(VARIAS)
    pior = max(r.casos, key=lambda i: (ORDEM_STATUS[i.resultado.status], i.resultado.aproveitamento_maximo))  # fmt: skip
    assert r.combinacao_governante == pior.caso.nome
    assert r.entrada.n_sd_kN == pior.caso.n_sd_kN and r.entrada.casos == CASOS
    assert r.caso == pior.resultado.caso
    placa = _linha(r, "Placa de base: espessura")
    assert placa.formula.startswith("[")
    # o que não muda de uma combinação para outra fica sem o nome
    assert not _linha(r, "Número de chumbadores").formula.startswith("[")
    assert any("compressão" in a and "tração" in a for a in r.avisos)


def test_uma_combinacao_so_e_igual_ao_calculo_direto():
    caso = CASOS[2]
    direto = _sozinho(PADRAO, caso)
    envoltoria = bp.calcular(replace(PADRAO, casos=(caso,)))
    pares = list(zip(direto.verificacoes, envoltoria.verificacoes, strict=True))
    assert all(
        a.nome == b.nome and a.formula == b.formula and a.status == b.status for a, b in pares
    )
    assert envoltoria.combinacao_governante == caso.nome


def test_ancoragem_sem_tracao_de_uma_combinacao_nao_aparece_quando_outra_traciona():
    e = replace(VARIAS, verificar_concreto=True)
    r = bp.calcular(e)
    assert not _tem(r, "Ancoragem no concreto")
    assert _tem(r, "Cone de concreto dos chumbadores tracionados")


def test_registro_guarda_as_combinacoes_e_a_figura_volta():
    r = bp.calcular(VARIAS)
    registro = bp.registro_base(r)
    resultados = registro["resultados"]
    entrada = bp.entrada_de_dicionario(resultados["figura_base_de_pilar"]["entrada"])
    assert entrada.casos == CASOS
    assert len(resultados["combinacoes"]) == 3
    assert "vento" in registro["entradas"]["combinacoes"]
    assert registro["entradas"]["combinacao_governante"] == r.combinacao_governante
    assert any("Envoltória de 3 combinações" in p for p in registro["premissas"])
    assert "envoltória de 3 combinações" in bp.destaque(r)
    figuras = record_charts.imagens_gravadas(resultados)
    assert len(figuras) == 1 and figuras[0][0].png[:8] == b"\x89PNG\r\n\x1a\n"


def test_combinacoes_invalidas():
    with pytest.raises(bp.BaseInvalida, match="nome"):
        bp.calcular(replace(PADRAO, casos=(bp.CasoDeCarga("", 100.0),)))
    with pytest.raises(bp.BaseInvalida, match="mesmo nome"):
        bp.calcular(replace(PADRAO, casos=(bp.CasoDeCarga("a", 1.0), bp.CasoDeCarga("a", 2.0))))
    with pytest.raises(bp.BaseInvalida, match="cortante"):
        bp.calcular(replace(PADRAO, casos=(bp.CasoDeCarga("a", 1.0, v_sd_kN=-1.0),)))


def test_por_formula_usa_o_mesmo_embutimento_em_todas_as_combinacoes():
    e = replace(VARIAS, por_formula=True, chumbador="M24")
    r = bp.calcular(e)
    embutimentos = {i.resultado.linha.h1 for i in r.casos}
    assert len(embutimentos) == 1


def test_atrito_nao_serve_na_combinacao_tracionada():
    r = bp.calcular(VARIAS)
    atrito = _linha(r, "Cortante: atrito")
    assert atrito.status == "NÃO OK" and atrito.formula.startswith("[vento]")


def test_base_mais_leve_atende_todas_as_combinacoes():
    e = replace(VARIAS, cortante=bp.CORTANTE_ARRUELAS)
    leve = bp.base_mais_leve(e)
    assert leve is not None and leve.envoltoria
    assert bp.passa_fora_a_solda_do_pilar(leve)
    for item in leve.casos:
        assert bp.passa_fora_a_solda_do_pilar(item.resultado), item.caso.nome


def test_combinacoes_dos_pilares_do_modelo():
    pilares = pbp.combinacoes_dos_pilares(portico(PILAR, PILAR_2), plano_do_portico())
    assert {p.pilar for p in pilares} == {PILAR, PILAR_2}
    primeiro = next(p for p in pilares if p.pilar == PILAR)
    assert primeiro.combinacoes and all(len(c) == 5 for c in primeiro.combinacoes)
    # as mesmas que a verificação das placas do modelo usa
    r = next(
        x
        for x in pbp.verificar_placas(
            portico(PILAR, PILAR_2), plano_do_portico(), pbp.ParametrosDaPlaca()
        )
        if x.pilar == PILAR
    )
    nome = next(c for c in primeiro.combinacoes if c[0] == r.combinacao)
    assert nome[1] == pytest.approx(r.n)


# ============================================================================ solda do pilar
def _contorno():
    return bs.contorno_do_pilar(258.0, 146.0, 6.1, 9.1, mesas_por_dentro=True, alma=True)


def test_contorno_do_perfil_i_a_mao():
    trechos = _contorno()
    p = bs.propriedades(trechos)
    interno = 146 / 2 - (6.1 / 2 + 9.1)  # da alma (com o raio ≈ t_f) à ponta da mesa
    alma = 2 * (258 / 2 - 9.1 - 9.1)
    assert len(trechos) == 2 + 4 + 2
    assert p.comprimento == pytest.approx(2 * 146 + 4 * interno + 2 * alma)
    i_x = 2 * 146 * 129**2 + 4 * interno * (129 - 9.1) ** 2 + 2 * alma**3 / 12
    assert p.i_x == pytest.approx(i_x)


def test_solda_do_pilar_compressao_pura_e_contato():
    c = bp.sd.coeficientes(bp.sd.COMBINACAO_NORMAL)
    p = bs.propriedades(_contorno())
    comum = dict(d=258.0, b_f=146.0, t_w=6.1, t_f=9.1, t_placa=25.0, aco_pilar=(345.0, 450.0),
                 momento=0.0, momento_y=0.0, perna_informada=6.0, eletrodo="E70",
                 mesas_por_dentro=True, alma=True, c=c)  # fmt: skip
    sem = bs.solda_do_pilar(axial=300e3, cortante=20e3, contato=False, **comum)
    filete = sem.linhas[0]
    assert filete.solicitante == pytest.approx(math.hypot(300e3, 20e3) / p.comprimento / 1e3)
    assert filete.resistente == pytest.approx(0.60 * E70 * 0.707 * 6 / 1.35 / 1e3)
    com = bs.solda_do_pilar(axial=300e3, cortante=20e3, contato=True, **comum)
    assert com.linhas[0].solicitante == pytest.approx(20e3 / p.comprimento / 1e3)


def test_solda_do_pilar_momento_pela_inercia_do_contorno():
    c = bp.sd.coeficientes(bp.sd.COMBINACAO_NORMAL)
    p = bs.propriedades(_contorno())
    r = bs.solda_do_pilar(
        d=258.0, b_f=146.0, t_w=6.1, t_f=9.1, t_placa=25.0, aco_pilar=(345.0, 450.0),
        axial=0.0, momento=30e6, momento_y=0.0, cortante=0.0, perna_informada=8.0,
        eletrodo="E70", mesas_por_dentro=True, alma=True, contato=False, c=c,
    )  # fmt: skip
    assert r.linhas[0].solicitante == pytest.approx(30e6 * 129 / p.i_x / 1e3)


def test_perna_automatica_e_a_menor_que_passa():
    r = bp.calcular(replace(PADRAO, m_sd_kNm=30.0))
    perna = r.perna_do_pilar
    assert _linha(r, "Solda do pilar na placa: filete").status == "OK"
    menores = [p for p in bs.PERNAS_COMERCIAIS if p < perna and p >= 5.0]  # 5 = a mínima
    for p in menores:
        menor = bp.calcular(replace(PADRAO, m_sd_kNm=30.0, perna_pilar_mm=p))
        assert _linha(menor, "Solda do pilar na placa: filete").status == "NÃO OK"
    assert perna <= bp.sd.perna_maxima(9.1)


def test_solda_do_pilar_limites():
    r = bp.calcular(replace(PADRAO, perna_pilar_mm=3.0))
    assert _linha(r, "Solda do pilar na placa: perna mínima").status == "NÃO OK"  # mín 5 (t 9,1)
    r = bp.calcular(replace(PADRAO, perna_pilar_mm=10.0))
    assert _linha(r, "Solda do pilar na placa: perna máxima").status == "NÃO OK"  # 9,1 − 1,5
    r = bp.calcular(replace(PADRAO, solda_mesas_por_dentro=False))
    assert not _tem(r, "Solda do pilar na placa: comprimento dos trechos internos")


def test_momento_alem_do_perfil_reprova_a_solda_e_avisa():
    r = bp.calcular(replace(PADRAO, n_chumbadores=6, m_sd_kNm=150.0, t_placa_mm=40.0))
    assert bp.solda_do_pilar_reprova(r)
    assert any("penetração total" in a for a in r.avisos)


# ============================================================================ outras soldas
def test_solda_da_placa_de_cisalhamento_a_mao_e_penetracao_total():
    e = replace(PADRAO, cortante=bp.CORTANTE_PLACA, b_v_mm=100.0, b_h_mm=150.0, t_pv_mm=16.0,
                perna_cisalhamento_mm=10.0)  # fmt: skip
    r = bp.calcular(e)
    sigma4 = 1.7 * 25 / 1.4
    e_n = 60.0  # Tabela 18, Ø 1"
    v_rd = sigma4 * (100 - e_n) * 150
    m = 0.5 * sigma4 * 150 * (100**2 - e_n**2)
    braco = 16 + 2 * 10 / 3
    esperado = math.hypot(m / braco / 150, v_rd / 300) / 1e3
    filete = _linha(r, "Solda da placa de cisalhamento: filetes")
    assert filete.solicitante == pytest.approx(esperado)
    assert filete.resistente == pytest.approx(0.60 * E70 * 0.707 * 10 / 1.35 / 1e3)
    cjp = bp.calcular(replace(e, cisalhamento_penetracao_total=True))
    assert _linha(cjp, "Solda da placa de cisalhamento: penetração total").status == "INFO"
    assert not _tem(cjp, "Solda da placa de cisalhamento: filetes")


def test_solda_das_arruelas_limites():
    e = replace(PADRAO, cortante=bp.CORTANTE_ARRUELAS)
    r = bp.calcular(e)
    assert _linha(r, "Solda das arruelas na placa: filete").status == "OK"
    grossa = bp.calcular(replace(e, perna_arruela_mm=8.0))  # arruela de 8 mm: máx 6,5
    assert _linha(grossa, "Solda das arruelas na placa: perna máxima").status == "NÃO OK"


# ============================================================================ cortante no concreto
ARRUELAS_ACI = replace(
    PADRAO, cortante=bp.CORTANTE_ARRUELAS, verificar_concreto=True, bloco_x_mm=700.0,
    bloco_y_mm=700.0, bloco_z_mm=600.0, v_sd_kN=40.0,
)  # fmt: skip


def test_ruptura_da_borda_a_mao():
    """4 × Ø 1" em (±179; ±50) mm, bloco 700 × 700 × 600, h_ef = 465 mm (Tabela 18)."""
    r = bp.calcular(ARRUELAS_ACI)
    linha = _linha(r, bp.LINHA_RUPTURA_DA_BORDA)
    raiz = 5.0  # √25
    l_e = min(465, 8 * 25)

    def v_cbg(c1, c2, fila_y):
        largura = min(max(fila_y) + 1.5 * c1, 350) - max(min(fila_y) - 1.5 * c1, -350)
        a_vc = min(largura * min(1.5 * c1, 600), len(fila_y) * 4.5 * c1**2)
        psi_ed = 1.0 if c2 >= 1.5 * c1 else 0.7 + 0.3 * c2 / (1.5 * c1)
        psi_h = max(1.0, math.sqrt(1.5 * c1 / 600))
        v_b = min(0.6 * (l_e / 25) ** 0.2 * math.sqrt(25) * raiz * c1**1.5, 3.7 * raiz * c1**1.5)
        return 0.70 * a_vc / (4.5 * c1**2) * psi_ed * psi_h * v_b

    em_x = v_cbg(350 - 179, 350 - 50, [-50, 50])
    em_y = v_cbg(350 - 50, 350 - 179, [-179, 179])
    assert linha.resistente == pytest.approx(min(em_x, em_y) / 1e3)
    assert linha.solicitante == pytest.approx(40.0)


def test_pryout_e_duas_vezes_o_cone_do_grupo():
    r = bp.calcular(ARRUELAS_ACI)
    g = bp.geometria(ARRUELAS_ACI)
    tab = bp.disposicoes(ARRUELAS_ACI)
    _, cone, _ = bp.cone_de_concreto(ARRUELAS_ACI, g, tab, (1.0,) * 4)
    assert _linha(r, bp.LINHA_ALAVANCA).resistente == pytest.approx(0.70 * 2 * cone / 0.70 / 1e3)


def test_interacao_dispensada_ou_somada():
    sem_tracao = bp.calcular(ARRUELAS_ACI)  # C1: sem chumbador tracionado
    assert not _tem(sem_tracao, bp.LINHA_INTERACAO)
    tracao = bp.calcular(replace(ARRUELAS_ACI, n_sd_kN=-120.0, v_sd_kN=60.0))
    linha = _linha(tracao, bp.LINHA_INTERACAO)
    assert linha.resistente == pytest.approx(1.2) and linha.solicitante > 0.4
    pouca = bp.interacao_tracao_cortante(0.15, 0.9, "aço", "17.7.2")
    assert pouca.status == "OK" and pouca.aproveitamento is None and "dispensada" in pouca.formula


def test_ruptura_a_frente_da_placa_de_cisalhamento():
    e = replace(PADRAO, cortante=bp.CORTANTE_PLACA, verificar_concreto=True, bloco_x_mm=900.0,
                bloco_y_mm=900.0, bloco_z_mm=800.0, b_v_mm=150.0, b_h_mm=150.0)  # fmt: skip
    r = bp.calcular(e)
    linha = _linha(r, bp.LINHA_FRENTE_DA_PLACA)
    c1 = 450 - 19 / 2
    h_sl = 150 - 60
    largura = 2 * min(75 + 1.5 * c1, 450)
    a_vc = largura * min(h_sl + 1.5 * c1, 800) - 150 * h_sl
    psi_ed = 0.7 + 0.3 * (450 - 75) / (1.5 * c1)
    esperado = 0.70 * a_vc / (4.5 * c1**2) * psi_ed * 3.7 * 5 * c1**1.5
    assert linha.resistente == pytest.approx(esperado / 1e3)
    assert "a confirmar" in linha.referencia


def test_cortante_no_concreto_so_com_a_ancoragem_verificada():
    r = bp.calcular(replace(ARRUELAS_ACI, verificar_concreto=False))
    assert not _tem(r, "Cortante no concreto")
