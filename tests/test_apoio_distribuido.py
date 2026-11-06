"""Apoio distribuído: a peça encostada ou presa ao longo de um trecho."""

from __future__ import annotations

import math

import pytest

from core import equilibrio_corpo as eq
from core.elementos_base import Resultado, calcular_caso
from core.elementos_equilibrio import CASO_EQUILIBRIO as CASO
from core.elementos_equilibrio import calcular_equilibrio, marcas_para_a_tela
from core.equilibrio_modelos import MODELOS, apoio, carga, corte, trecho

SI = eq.Unidades("m", "N")
PECA = (trecho(0, 0, 4, 0),)


def distribuido(x1=0.0, x2=4.0, *, y=0.0, angulo=90.0, mu=None, fixacao=None, nome="A") -> dict:
    return apoio(nome, eq.DISTRIBUIDO, x1, y, angulo, ponta=(x2, y), mu=mu, fixacao=fixacao)


def forca(x: float, f: float = 12.0, angulo: float = -90.0, nome: str = "F1") -> dict:
    return carga(nome, eq.FORCA, x, 0, f, angulo)


def resolver(apoios: list[dict], cargas: list[dict], cortes: tuple = ()) -> eq.Solucao:
    return eq.resolver(eq.problema_das_tabelas(PECA, apoios, cargas, cortes, SI))


def pressao(apoios: list[dict], cargas: list[dict]) -> eq.Pressao:
    return eq.pressao_do_apoio(resolver(apoios, cargas).reacoes[0])


def esforco(apoios: list[dict], cargas: list[dict], x: float) -> eq.Esforco:
    s = resolver(apoios, cargas, (corte("S1", x, 0),))
    return eq.esforco_no_corte(s, s.problema.cortes[0])


def dados(apoios: list[dict], cargas: list[dict], cortes: tuple = ()) -> dict:
    return {
        "comprimento": "m",
        "forca": "kN",
        "trechos": list(PECA),
        "apoios": apoios,
        "cargas": cargas,
        "cortes": list(cortes),
    }


def rodar(apoios: list[dict], cargas: list[dict]) -> Resultado:
    return calcular_caso(CASO, dados(apoios, cargas))


def tabela_da_pressao(r: Resultado) -> dict:
    return next(t for t in r.tabelas if t.titulo == "Pressão nos apoios distribuídos").linhas[0]


def linha(r: Resultado, nome: str):
    return next(v for v in r.verificacoes if v.nome == nome)


# ---------------------------------------------------------------------------
# Pressão
# ---------------------------------------------------------------------------


def test_carga_uniforme_devolve_a_mesma_pressao():
    q = carga("q", eq.DISTRIBUIDA, 0, 0, 5.0, -90.0, ate=(4, 0), valor2=5.0)
    p = pressao([distribuido()], [q])
    assert p.w1 == pytest.approx(5.0)
    assert p.w2 == pytest.approx(5.0)
    assert p.fracao == 1.0


def test_forca_no_meio_da_pressao_constante():
    r = resolver([distribuido()], [forca(2.0, 8.0)]).reacoes[0]
    assert r.n == pytest.approx(8.0)
    assert r.m == pytest.approx(0.0, abs=1e-9)
    assert eq.pressao_do_apoio(r).w1 == pytest.approx(2.0)


def test_forca_excentrica_dentro_do_terco_da_um_trapezio():
    # R = 12, e = 0,5, L = 4: R/L ∓ 6·R·e/L² = 3 ∓ 2,25.
    p = pressao([distribuido()], [forca(2.5)])
    assert p.w1 == pytest.approx(0.75)
    assert p.w2 == pytest.approx(5.25)
    assert p.excentricidade == pytest.approx(0.5)


def test_resultante_no_limite_do_terco_zera_uma_ponta():
    p = pressao([distribuido()], [forca(2.0 + 4.0 / 6.0)])
    assert p.fracao == pytest.approx(1.0)
    assert p.w1 == pytest.approx(0.0, abs=1e-9)
    assert p.w2 == pytest.approx(6.0)


def test_fora_do_terco_a_peca_descola_e_a_pressao_vira_triangulo():
    # e = 1, L = 4: contato c = 3·(2 − 1) = 3 e pico 2·R/c = 8.
    p = pressao([distribuido()], [forca(3.0)])
    assert p.fracao == pytest.approx(0.75)
    assert (p.x1, p.x2) == (pytest.approx(1.0), pytest.approx(4.0))
    assert p.w1 == pytest.approx(0.0)
    assert p.w2 == pytest.approx(8.0)
    assert p.nas_pontas() == (pytest.approx(0.0), pytest.approx(8.0))


def test_triangulo_do_outro_lado():
    p = pressao([distribuido()], [forca(1.0)])
    assert (p.x1, p.x2) == (pytest.approx(0.0), pytest.approx(3.0))
    assert p.w1 == pytest.approx(8.0)
    assert p.w2 == pytest.approx(0.0)
    assert p.nas_pontas() == (pytest.approx(8.0), pytest.approx(0.0))


@pytest.mark.parametrize("x", [1.0, 1.7, 2.5, 3.0])
def test_a_pressao_devolve_a_resultante_e_o_lugar_dela(x):
    p = pressao([distribuido()], [forca(x)])
    l = p.x2 - p.x1
    assert (p.w1 + p.w2) * l / 2.0 == pytest.approx(12.0)
    assert p.x1 + l / 3.0 * (p.w1 + 2.0 * p.w2) / (p.w1 + p.w2) == pytest.approx(x)


def test_apoio_por_cima_da_a_mesma_ponta_carregada():
    """Trocar o lado do apoio e o da força não pode trocar qual ponta aperta."""
    p = pressao([distribuido(angulo=-90.0)], [forca(3.0, angulo=90.0)])
    assert p.w2 == pytest.approx(8.0)
    assert p.x1 == pytest.approx(1.0)


def test_trecho_desenhado_de_tras_para_frente_da_o_mesmo_resultado():
    p = pressao([distribuido(4.0, 0.0)], [forca(3.0)])
    assert p.w1 == pytest.approx(8.0)
    assert p.x1 == pytest.approx(4.0)
    assert p.x2 == pytest.approx(1.0)
    assert p.nas_pontas() == (pytest.approx(8.0), pytest.approx(0.0))


def test_trecho_inclinado_com_forca_perpendicular():
    c, s = math.cos(math.radians(30.0)), math.sin(math.radians(30.0))
    a = apoio("A", eq.DISTRIBUIDO, 0, 0, 120.0, ponta=(4 * c, 4 * s))
    f = carga("F1", eq.FORCA, 2 * c, 2 * s, 8.0, -60.0)
    r = resolver([a], [f]).reacoes[0]
    assert r.n == pytest.approx(8.0)
    assert eq.pressao_do_apoio(r).w1 == pytest.approx(2.0)


def test_angulo_so_escolhe_o_lado_a_reacao_e_perpendicular_ao_trecho():
    a = eq.Apoio("A", eq.DISTRIBUIDO, 0.0, 0.0, 60.0, 4.0, 0.0)
    assert a.direcao == (pytest.approx(0.0), pytest.approx(1.0))
    b = eq.Apoio("A", eq.DISTRIBUIDO, 0.0, 0.0, -60.0, 4.0, 0.0)
    assert b.direcao == (pytest.approx(0.0), pytest.approx(-1.0))


# ---------------------------------------------------------------------------
# Tombamento, puxão e atrito
# ---------------------------------------------------------------------------


def test_carga_fora_do_trecho_tomba():
    p = pressao([distribuido(0.0, 2.0)], [forca(3.0)])
    assert p.tomba


def test_carga_para_cima_nao_e_segurada_por_quem_so_encosta():
    p = pressao([distribuido()], [forca(2.0, 10.0, 90.0)])
    assert p.tomba


def test_preso_segura_puxao():
    r = resolver([distribuido(fixacao=eq.PRESO)], [forca(2.0, 10.0, 90.0)]).reacoes[0]
    assert r.n == pytest.approx(-10.0)
    p = eq.pressao_do_apoio(r)
    assert not p.tomba
    assert p.w1 == pytest.approx(-2.5)


def test_preso_com_carga_fora_do_terco_mantem_a_reta_inteira():
    p = pressao([distribuido(fixacao=eq.PRESO)], [forca(4.0, 8.0)])
    assert p.fracao == 1.0
    assert p.w1 == pytest.approx(2.0 - 6.0)
    assert p.w2 == pytest.approx(2.0 + 6.0)


def test_preso_segura_carga_ao_longo_do_trecho():
    s = resolver([distribuido(fixacao=eq.PRESO)], [forca(2.0, 10.0, 0.0)])
    assert s.para
    assert abs(s.reacoes[0].t) == pytest.approx(10.0)


def test_so_encostado_sem_atrito_nao_segura_carga_ao_longo():
    assert not resolver([distribuido()], [forca(2.0, 10.0, -45.0)]).para


def test_atrito_dentro_do_limite_passa():
    r = rodar([distribuido(mu=0.5)], [forca(2.0, 10.0), forca(2.0, 3.0, 0.0, "F2")])
    assert linha(r, "Atrito em A").status == "OK"


def test_atrito_alem_do_limite_reprova():
    r = rodar([distribuido(mu=0.2)], [forca(2.0, 10.0), forca(2.0, 3.0, 0.0, "F2")])
    assert linha(r, "Atrito em A").status == "NÃO OK"


def test_verificacao_reprova_a_resultante_fora_do_trecho():
    r = rodar([distribuido(0.0, 2.0)], [forca(3.0)])
    assert linha(r, "Resultante dentro do apoio A").status == "NÃO OK"
    assert any("tomba" in a for a in r.alertas)


def test_puxar_quem_so_encosta_reprova():
    r = rodar([distribuido()], [forca(2.0, 10.0, 90.0)])
    assert linha(r, "Apoio A encostado").status == "NÃO OK"


def test_preso_nao_tem_verificacao_de_contato():
    r = rodar([distribuido(fixacao=eq.PRESO)], [forca(2.0, 10.0, 90.0)])
    assert not any("encostado" in v.nome for v in r.verificacoes)
    assert not any("tomba" in a for a in r.alertas)


# ---------------------------------------------------------------------------
# Corte dentro do trecho
# ---------------------------------------------------------------------------


def test_corte_dentro_do_trecho_com_pressao_uniforme():
    """Força de 8 no meio de um trecho de 4: pressão 2 N/m, conta de mão à esquerda de x = 1."""
    e = esforco([distribuido()], [forca(2.0, 8.0)], 1.0)
    assert abs(e.v) == pytest.approx(2.0)
    assert abs(e.m) == pytest.approx(1.0)


def test_corte_no_meio_bate_com_a_conta_de_mao():
    e = esforco([distribuido()], [forca(1.999999, 8.0)], 2.0)
    assert abs(e.m) == pytest.approx(4.0, rel=1e-4)


def test_corte_dentro_da_pressao_triangular():
    # Pressão de 0 em x = 1 a 8 em x = 4. À direita de x = 3: trapézio de 16/3 a 8 por 1 m.
    e = esforco([distribuido()], [forca(3.5, 12.0)], 3.0)
    p = pressao([distribuido()], [forca(3.5, 12.0)])
    # e = 1,5: contato 1,5 m e pico 16.
    assert p.w2 == pytest.approx(16.0)
    assert p.x1 == pytest.approx(2.5)
    w = 16.0 / 1.5 * 0.5  # no corte
    v_dir = (w + 16.0) / 2.0 * 1.0 - 12.0
    braco = 1.0 / 3.0 * (w + 2.0 * 16.0) / (w + 16.0)
    m_dir = (w + 16.0) / 2.0 * braco - 12.0 * 0.5
    assert abs(e.v) == pytest.approx(abs(v_dir))
    assert abs(e.m) == pytest.approx(abs(m_dir))


def test_corte_fora_do_trecho_nao_recebe_a_reacao():
    """Trecho de 0 a 2 e nada à direita de x = 3: esforço nenhum."""
    e = esforco([distribuido(0.0, 2.0)], [forca(1.5, 6.0)], 3.0)
    assert e.v == pytest.approx(0.0, abs=1e-9)
    assert e.m == pytest.approx(0.0, abs=1e-9)


def test_corte_no_balanco_recebe_so_a_forca_da_ponta():
    e = esforco([distribuido(0.0, 2.0, fixacao=eq.PRESO)], [forca(4.0, 6.0)], 3.0)
    assert abs(e.v) == pytest.approx(6.0)
    assert abs(e.m) == pytest.approx(6.0)


def test_atrito_entra_ao_longo_do_trecho_no_corte():
    e = esforco([distribuido(fixacao=eq.PRESO)], [forca(4.0, 8.0, 0.0)], 1.0)
    assert abs(e.n) == pytest.approx(2.0)


def test_preso_com_pressao_trocando_de_sinal_na_secao():
    # Reta de −4 a 8 N/m: à esquerda de x = 1 fica de −4 a −1.
    e = esforco([distribuido(fixacao=eq.PRESO)], [forca(4.0, 8.0)], 1.0)
    assert abs(e.v) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Soma de tudo
# ---------------------------------------------------------------------------


def test_residuos_fecham():
    s = resolver([distribuido(fixacao=eq.PRESO)], [forca(3.0, 12.0), forca(1.0, 5.0, 30.0, "F2")])
    f, m = eq.residuos(s)
    assert f == pytest.approx(0.0, abs=1e-9)
    assert m == pytest.approx(0.0, abs=1e-9)


def test_reacao_como_cargas_devolve_a_mesma_reacao():
    r = resolver([distribuido(mu=0.8)], [forca(3.0), forca(1.0, 2.0, 0.0, "F2")]).reacoes[0]
    acoes = [eq.acao_da_carga(c) for c in eq.cargas_da_reacao(r)]
    assert sum(a.fx for a in acoes) == pytest.approx(r.fx)
    assert sum(a.fy for a in acoes) == pytest.approx(r.fy)
    xo, yo = r.apoio.ponto
    assert sum(eq._momento(a, xo, yo) for a in acoes) == pytest.approx(r.m)


def test_com_outro_apoio_a_estatica_nao_separa_mas_respeita_o_contato():
    s = resolver([distribuido(0.0, 3.0), apoio("B", eq.PINO, 4, 0)], [forca(2.0, 10.0)])
    assert s.grau_hiperestatico == 1
    assert s.divisao_viavel
    assert s.reacoes[0].n >= 0.0
    assert abs(s.reacoes[0].m) <= s.reacoes[0].n * 1.5 + 1e-9


def test_divisao_prefere_o_trecho_inteiro_encostado():
    s = resolver([distribuido(0.0, 3.0), apoio("B", eq.PINO, 4, 0)], [forca(2.9, 10.0)])
    p = eq.pressao_do_apoio(s.reacoes[0])
    assert p.fracao == 1.0
    assert abs(p.excentricidade) <= 0.5 + 1e-9


def test_varios_graus_nao_acusam_tombamento_de_uma_divisao_qualquer():
    """A divisão é só uma das possíveis: a linha pede atenção, sem reprovar."""
    apoios = [distribuido(0.0, 1.0), distribuido(3.0, 4.0, nome="B")]
    r = rodar(apoios, [forca(3.9)])
    assert all(v.status != "NÃO OK" for v in r.verificacoes)
    assert not any("tomba" in a for a in r.alertas)


def test_dois_apoios_distribuidos_dao_alerta_de_estatica():
    r = rodar([distribuido(0.0, 1.0), distribuido(3.0, 4.0, nome="B")], [forca(2.0, 10.0)])
    assert any("não separa" in a for a in r.alertas)


def test_unidade_da_tela():
    r = rodar([distribuido(0.5, 3.5)], [forca(2.0)])
    assert tabela_da_pressao(r)["Maior (kN/m)"] == pytest.approx(4.0)


def test_mudar_a_unidade_nao_muda_a_peca():
    em_metros = calcular_equilibrio(dados([distribuido(0.5, 3.5)], [forca(2.0)]))
    linhas = {**dados([distribuido(500, 3500)], [carga("F1", eq.FORCA, 2000, 0, 12.0)])}
    linhas["trechos"] = [trecho(0, 0, 4000, 0)]
    linhas["comprimento"] = "mm"
    em_mm = calcular_equilibrio(linhas)
    assert tabela_da_pressao(em_mm)["Maior (kN/mm)"] == pytest.approx(
        tabela_da_pressao(em_metros)["Maior (kN/m)"] / 1000.0
    )


def test_conversao_de_unidade_leva_as_duas_pontas():
    convertido = eq.converter_dados(
        {"apoios": [distribuido(0.5, 3.5)], "cargas": [], "trechos": [], "cortes": []},
        eq.Unidades("m", "kN"),
        eq.Unidades("mm", "kN"),
    )
    assert convertido["apoios"][0]["x2"] == pytest.approx(3500.0)


# ---------------------------------------------------------------------------
# Tabela, entrada, figura
# ---------------------------------------------------------------------------


def test_tabela_da_pressao_com_contato_parcial():
    r = rodar([distribuido(0.5, 3.5)], [forca(3.0)])
    t = tabela_da_pressao(r)
    assert t["Resultante (kN)"] == pytest.approx(12.0)
    assert t["Posição da resultante (m)"] == "2,5"
    assert t["Em contato (%)"] == pytest.approx(50.0)
    assert t["No início (kN/m)"] == pytest.approx(0.0)
    assert t["No fim (kN/m)"] == pytest.approx(16.0)
    assert any("terço central" in a for a in r.alertas)


def test_sem_apoio_distribuido_nao_aparece_a_tabela():
    r = rodar([apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)], [forca(2.0)])
    assert all(t.titulo != "Pressão nos apoios distribuídos" for t in r.tabelas)


def test_trecho_sem_fim_explica_o_que_falta():
    linha_apoio = {**distribuido(), "x2": None}
    with pytest.raises(eq.ErroDeEquilibrio, match="x₂, y₂"):
        calcular_equilibrio(dados([linha_apoio], [forca(2.0)]))


def test_trecho_de_comprimento_zero_nao_passa():
    with pytest.raises(eq.ErroDeEquilibrio, match="mesmo lugar"):
        calcular_equilibrio(dados([distribuido(1.0, 1.0)], [forca(2.0)]))


def test_linha_sem_a_coluna_de_fixacao_continua_abrindo():
    """Projeto salvo antes de existir a coluna: vale só encostar."""
    linha_apoio = distribuido()
    del linha_apoio["fixacao"]
    s = resolver([linha_apoio], [forca(2.0)])
    assert not s.problema.apoios[0].preso


def test_figura_sai_com_os_tres_jeitos_de_trabalhar():
    for fixacao, x in ((None, 2.5), (None, 3.0), (eq.PRESO, 3.8)):
        r = rodar([distribuido(0.5, 3.5, fixacao=fixacao)], [forca(x)])
        assert r.figuras and r.figuras[0].png


def test_figura_sai_com_apoio_de_pe_e_inclinado():
    a = apoio("A", eq.DISTRIBUIDO, 4, 0, 180.0, ponta=(4, 3), fixacao=eq.PRESO)
    r = calcular_equilibrio(
        {
            **dados([a], [carga("F1", eq.FORCA, 0, 1.5, 6.0, 0.0)]),
            "trechos": [trecho(0, 1.5, 4, 1.5)],
        }
    )
    assert r.figuras[0].png


def test_marcas_da_prancheta_levam_a_pressao():
    marcas = marcas_para_a_tela(dados([distribuido(0.5, 3.5)], [forca(3.0)]))
    r = marcas["reacoes"][0]
    assert r["x"] == pytest.approx(2.0)
    assert r["pressao"]["x1"] == pytest.approx(2.0)
    assert r["pressao"]["x2"] == pytest.approx(3.5)
    assert r["pressao"]["w2"] == pytest.approx(16.0)
    assert not r["ruim"]


def test_marcas_avisam_quando_tomba():
    marcas = marcas_para_a_tela(dados([distribuido(0.0, 2.0)], [forca(3.0)]))
    assert marcas["reacoes"][0]["ruim"]
    assert marcas["reacoes"][0]["pressao"]["tomba"]


def test_outros_apoios_nao_levam_pressao():
    marcas = marcas_para_a_tela(dados([apoio("A", eq.ENGASTE, 0, 0, 0.0)], [forca(2.0)]))
    assert marcas["reacoes"][0]["pressao"] is None


def test_modelo_pronto_calcula_e_passa():
    modelo = next(m for m in MODELOS if m.nome == "Peça apoiada ao longo")
    r = calcular_caso(
        CASO, {"comprimento": modelo.comprimento, "forca": modelo.forca, **modelo.dados()}
    )
    assert r.verificacoes
    assert all(v.status in ("OK", "INFO") for v in r.verificacoes)


def test_tabela_do_caso_tem_o_tipo_e_a_fixacao():
    campos = {c.chave: c for c in CASO.campos}
    tipo = next(c for c in campos["apoios"].colunas if c.chave == "tipo")
    assert eq.DISTRIBUIDO in tipo.opcoes
    fixacao = next(c for c in campos["apoios"].colunas if c.chave == "fixacao")
    assert fixacao.opcoes == eq.FIXACOES
