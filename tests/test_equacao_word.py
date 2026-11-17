"""As equações do Word (core.equacao_word): leitura robusta, caixa no resultado, numeração.

Além dos casos escolhidos, dois testes de robustez: milhares de fórmulas aleatórias e todas as
fórmulas reais do programa (placa de base, ligações, parafusos, fadiga) saem sempre em XML válido,
sem exceção, e nenhuma deixa um "_" de índice cru na equação.
"""

from __future__ import annotations

import random
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from core import equacao_word as eq

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _xml(texto: str, **kw) -> str:
    xml = eq.omml(texto, **kw)
    etree.fromstring(xml)  # bem formado
    return xml


def _textos(xml: str) -> list[str]:
    return re.findall(r"<m:t[^>]*>([^<]*)</m:t>", xml)


# ------------------------------------------------------------------------------- partes do texto
def test_rotulo_referencia_e_varias_contas():
    rotulo, contas, referencia = eq.preparar(
        "Grupo excêntrico (método elástico): F_x,i = N/n − M·y_i/J; F_y,i = V/n + M·x_i/J; "
        "J = Σ(x_i² + y_i²) = 1800 mm² (Kulak, Fisher & Struik, cap. 13)"
    )
    assert rotulo == "Grupo excêntrico (método elástico):"
    assert [c.texto.split(" =")[0] for c in contas] == ["F_x,i", "F_y,i", "J"]
    assert referencia.startswith("Kulak")


def test_rotulo_com_conta_dentro_do_parentese():
    rotulo, contas, _ = eq.preparar(
        "Contato (ℓ_f crítico = 23 mm; t da parte mais fina): F_c,Rd = 1,5·ℓ_f·t·f_u/γ_a2"
    )
    assert rotulo.startswith("Contato") and len(contas) == 1


def test_ponto_decimal_de_maquina_e_notacoes_alternativas():
    xml = _xml("Se = 2.5 x 3 * k => n >= 1.0", maquina=True)
    textos = _textos(xml)
    assert "2,5" in textos and "×" in textos and "·" in textos and "⇒" in textos and "≥" in textos


@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        (
            "σa,eq = σa/2",
            '<m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">a,eq',
        ),
        ("ℓx = 300 mm", '<m:sub><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">x'),
        ("a₁ = 45", "<m:sSub>"),
        ("x^{n+1}", "<m:sSup>"),
        ("F_{t,Sd} = 1", "t,Sd"),
        ("|a − b|", 'm:begChr m:val="|"'),
        ("J = Σ(x_i²)", '<m:chr m:val="∑"/>'),
        ("√(a + b) = 3 mm", "<m:rad>"),
        ("T = 500 °F", "°F"),
    ],
)
def test_notacao(texto, trecho):
    assert trecho in _xml(texto)


def test_palavras_ficam_em_texto_reto_e_variaveis_em_italico():
    xml = _xml("Produto dos fatores = k_a·k_b")
    assert "<m:nor/>" in xml and "Produto dos fatores" in xml
    # "e" entre dois valores é palavra; "e = M/N" é a excentricidade
    assert "<m:nor/>" in _xml("R = 11,90 kN (ELU) e 8,50 kN (serviço)")
    assert "<m:nor/>" not in _xml("e = M/N")


def test_unidade_depois_de_parentese_em_letra_reta():
    xml = _xml("t = √(4·F·m/(b·f)) = 7,91 mm")
    assert '<m:sty m:val="p"/></m:rPr><m:t xml:space="preserve">mm' in xml


def test_caixa_no_valor_calculado():
    assert "<m:borderBox>" in _xml("t = √(4·F·m) = 7,91 mm")
    xml = _xml("σ = 39600/(1,5 × 447) + 6962/216 = 91,3 MPa ≤ 227,3 MPa")
    caixa = re.search(r"<m:borderBox>(.*?)</m:borderBox>", xml).group(1)
    assert "91,3" in caixa and "227,3" not in caixa  # o calculado, não o limite
    assert "<m:borderBox>" not in _xml("t_p = 16,00 mm")  # dado, não conta
    assert "<m:borderBox>" not in _xml("T_F = 500 °F ≤ 450 °F ⇒ C = 1")  # dado comparado


def test_simbolica_e_resultado():
    simbolica = eq.preparar("σ_c,Rd = 0,85·f_ck/γ_c·√(A_2/A_1) ≤ 1,7·f_ck/γ_c")[1][0]
    assert simbolica.simbolica and not simbolica.resultado
    conta = eq.preparar("σ = 1200/(2 × 3) = 200 MPa")[1][0]
    assert conta.resultado and not conta.simbolica
    assert not eq.preparar("t_p = 16,00 mm")[1][0].simbolica
    assert eq.preparar("N_b = 10·√f_c·h_ef^1,5")[1][0].simbolica


# ------------------------------------------------------------------------------- robustez
_PEDACOS = [
    "a", "σ", "F_t", "x_{n+1}", "γ_a1", "ℓ_c", "M", "N", "e", "mm", "kN", "MPa", "²", "₁",
    "1", "0,85", "2.5", "1000", " ", " ", "=", "≤", "≥", "+", "−", "-", "·", "×", "/", "^", "_",
    "(", ")", "[", "]", "{", "}", "|", "√", "Σ", ";", ":", ",", "=>", " x ", "mín(", "fator",
    "Produto dos", "°F", "'", "*", "<=",
]  # fmt: skip


def test_mil_formulas_aleatorias_nunca_quebram():
    sorteio = random.Random(20261117)
    for _ in range(3000):
        texto = "".join(sorteio.choice(_PEDACOS) for _ in range(sorteio.randint(1, 25)))
        rotulo, contas, referencia = eq.preparar(texto, maquina=sorteio.random() < 0.5)
        for conta in contas:
            etree.fromstring(eq.omml_da_equacao(conta))
        etree.fromstring(eq.omml(texto))


def _formulas_do_programa() -> list[tuple[str, bool]]:
    from test_memorial_ligacao_parafusada import M22
    from test_memorial_trecho import BASE

    from core import base_de_pilar as bp
    from core import bolted_joint_check as chk
    from core import ligacoes as lg
    from core import ligacoes_soldadas as ls

    formulas: list[tuple[str, bool]] = []
    for e in (BASE, replace(BASE, casos=(), n_sd_kN=10.5, m_sd_kNm=2.0, m_sd_y_kNm=0.7,
                            distribuicao=bp.DISTRIBUICAO_ELASTICA, cortante=bp.CORTANTE_DIRETOS)):  # fmt: skip
        r = bp.calcular(e)
        formulas += [(x, False) for v in r.verificacoes for x in v.equacoes]
    registro = chk.registro_ligacao(M22, chk.verificar_ligacao(M22), None)
    formulas += [(x, True) for x in registro.get("equacoes") or []]
    r = lg.calcular(ls.EntradaBarraSoldada())
    formulas += [(v.formula, True) for v in r.verificacoes if v.formula]
    return formulas


def test_todas_as_formulas_do_programa_saem_validas_e_sem_indice_cru():
    formulas = _formulas_do_programa()
    assert len(formulas) > 30
    for texto, maquina in formulas:
        _, contas, _ = eq.preparar(texto, maquina=maquina)
        for conta in contas:
            xml = eq.omml_da_equacao(conta)
            etree.fromstring(xml)
            crus = [t for t in _textos(xml) if "_" in t]
            assert not crus, (texto, crus)
