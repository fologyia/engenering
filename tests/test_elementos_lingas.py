"""Linga de corrente pela NBR 15516-2:2013, Anexo A, contra o texto e as tabelas da norma."""

from __future__ import annotations

import pytest

from core import elementos_catalogo as cat
from core import elementos_lingas as el
from core.elementos_base import calcular_caso


def rodar(**valores):
    return calcular_caso(cat.CASOS["linga_corrente"], valores)


def linha(resultado, nome: str):
    return next(v for v in resultado.verificacoes if v.nome == nome)


def metrica(resultado, rotulo: str):
    return next(m.valor for m in resultado.metricas if m.rotulo == rotulo)


@pytest.mark.parametrize(
    ("beta", "toneladas"), [(45.0, 7.0), (60.0, 10.0), (75.0, 20.0), (80.0, 30.0)]
)
def test_forca_na_perna_bate_com_a_figura_a1(beta, toneladas):
    """Figura A.1: carga de 10 t em duas pernas; a norma escreve o valor arredondado."""
    r = rodar(massa_t=10.0, cmt_t=1000.0, beta_max=beta, beta_min=beta, faixa=el.FAIXAS[1])
    em_t = metrica(r, "Força por perna") / el.G
    assert em_t == pytest.approx(toneladas, rel=0.05)


def test_exemplo_sem_reducao():
    r = rodar()
    assert metrica(r, "CMT ajustada") == pytest.approx(6.7)
    assert r.status == "OK"


@pytest.mark.parametrize(
    ("grau", "temperatura", "fator"),
    [
        ("Grau 4", 250.0, 1.00),
        ("Grau 4", 350.0, 0.75),
        ("Grau 4", 450.0, 0.50),
        ("Grau 8", 200.0, 1.00),
        ("Grau 8", 250.0, 0.90),
        ("Grau 8", 380.0, 0.75),
    ],
)
def test_tabela_a1_temperatura(grau, temperatura, fator):
    assert el.fator_de_temperatura(grau, temperatura) == fator


def test_acima_da_tabela_a1_nao_e_permissivel():
    assert el.fator_de_temperatura("Grau 8", 401.0) is None
    with pytest.raises(ValueError, match="não é permissível"):
        rodar(grau="Grau 8", temperatura_C=420.0)
    with pytest.raises(ValueError, match="não é permissível"):
        rodar(grau="Grau 4", temperatura_C=480.0)


def test_tabela_a2_menos_pernas():
    assert el.MENOS_PERNAS == {
        (2, 1): 1 / 2,
        (3, 2): 2 / 3,
        (4, 2): 2 / 3,
        (3, 1): 1 / 3,
        (4, 1): 1 / 3,
    }
    r = rodar(pernas="4 pernas", pernas_usadas=2, cmt_t=12.0, massa_t=3.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(12.0 * 2 / 3)
    # Três e quatro pernas estão na mesma linha da tabela: quatro usando três não reduz.
    r = rodar(pernas="4 pernas", pernas_usadas=3, cmt_t=12.0, massa_t=3.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(12.0)


def test_metodo_forca_80_e_olhal_pequeno_50():
    r = rodar(metodo=el.FORCA, olhal_pequeno=True, cmt_t=10.0, massa_t=2.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(10.0 * 0.8 * 0.5)


def test_assimetria_corta_a_cmt_pela_metade():
    # A.1.3.5 c): ângulos a mais de 15° um do outro
    r = rodar(beta_max=50.0, beta_min=30.0, faixa=el.FAIXAS[1], cmt_t=10.0, massa_t=2.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(5.0)
    # A.1.3.5 a): carga de 80 % da CMT ou mais
    r = rodar(cmt_t=10.0, massa_t=8.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(5.0)
    assert linha(r, "Massa içada contra a CMT ajustada").status == "NÃO OK"
    # A.1.3.5 b): todos os ângulos abaixo de 15°
    r = rodar(beta_max=10.0, beta_min=10.0, cmt_t=10.0, massa_t=2.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(5.0)
    assert linha(r, "Ângulo mínimo com a vertical").status == "ALERTA"


def test_angulo_acima_de_60_ou_da_faixa_reprova():
    r = rodar(beta_max=62.0, beta_min=60.0, faixa=el.FAIXAS[1])
    assert linha(r, "Ângulo das pernas com a vertical").status == "NÃO OK"
    r = rodar(beta_max=50.0, beta_min=45.0, faixa=el.FAIXAS[0])
    assert linha(r, "Ângulo das pernas com a vertical").status == "NÃO OK"


def test_acido_grau_4_metade_e_grau_8_proibido():
    r = rodar(grau="Grau 4", acido=True, cmt_t=10.0, massa_t=2.0)
    assert metrica(r, "CMT ajustada") == pytest.approx(5.0)
    with pytest.raises(ValueError, match="grau 8"):
        rodar(grau="Grau 8", acido=True)


def test_pernas_usadas_nao_passam_do_total():
    with pytest.raises(ValueError, match="pernas usadas"):
        rodar(pernas="2 pernas", pernas_usadas=3)


def test_uma_perna_ignora_os_angulos():
    r = rodar(pernas="1 perna", cmt_t=2.0, massa_t=1.5, beta_max=80.0)
    assert metrica(r, "Força por perna") == pytest.approx(1.5 * el.G)
    assert metrica(r, "CMT ajustada") == pytest.approx(2.0)
