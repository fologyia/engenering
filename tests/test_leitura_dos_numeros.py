"""Os números dos arquivos do SolidWorks: o formato sai do próprio arquivo, não do separador.

Um computador com o ponto decimal grava ``sep=;`` do mesmo jeito que um com a vírgula. Lido com
a regra errada, "459.59" virava 45959 — sem aviso nenhum.
"""

from __future__ import annotations

import re

import pytest

from core import apoios_do_modelo as am
from core import esforcos_modelo as em
from tests import portico_3d_teste01 as t

_NUMERO = re.compile(r"[+-]?[\d.,]*\d(?:[eE][+-]?\d+)?")
_TROCA = str.maketrans({".": ",", ",": "."})


def em_ingles(conteudo: bytes) -> bytes:
    """O mesmo arquivo como um computador com o ponto decimal o grava: em cada número, o ponto
    vira vírgula e a vírgula vira ponto ("1.014,4" → "1,014.4"). As colunas continuam com ";"."""
    linhas = []
    for linha in conteudo.decode("cp1252").split("\r\n"):
        campos = []
        for campo in linha.split(";"):
            miolo = campo.strip()
            if miolo and _NUMERO.fullmatch(miolo):
                campo = campo.replace(miolo, miolo.translate(_TROCA))
            campos.append(campo)
        linhas.append(";".join(campos))
    return "\r\n".join(linhas).encode("cp1252")


@pytest.mark.parametrize(
    ("texto", "virgula", "esperado"),
    [
        # O padrão brasileiro, como sempre foi.
        ("78.611", True, 78611.0),
        ("-1.019,1", True, -1019.1),
        ("1,4815E+05", True, 148150.0),
        ("24,805", True, 24.805),
        ("-0,587275", True, -0.587275),
        ("1.234.567", True, 1234567.0),
        ("5663", True, 5663.0),
        # O que não é ambíguo vale pelo próprio número, com qualquer regra.
        ("1,014.4", True, 1014.4),
        ("-1.019,1", False, -1019.1),
        ("461.49", True, 461.49),  # um ponto que não fecha grupo de três não é de milhar
        ("0.632", True, 0.632),  # nem o que vem depois de um zero
        ("0.63235", True, 0.63235),
        ("1059.506836", True, 1059.506836),
        ("8,535000E-01", False, 0.8535),
        (".5", True, 0.5),
        # O ambíguo segue a regra do arquivo.
        ("24.805", False, 24.805),
        ("24.805", True, 24805.0),
        ("1,014", False, 1014.0),
        ("1,014", True, 1.014),
    ],
)
def test_numero_do_csv(texto, virgula, esperado):
    assert em.numero(texto, decimal_virgula=virgula) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["", "-", "—", "abc", "nan", "inf", "1,2,3x", "12 kN", "--5"])
def test_o_que_nao_e_numero_nao_vira_numero(texto):
    assert em.numero(texto) is None


def test_formato_dos_numeros_sai_do_arquivo():
    brasileiro = ["  ;5663  ;1  ;24,805  ;461,49  ;9,486  ;-2,4809  ;14,208  ;0,63235"]
    ingles = ["  ;5663  ;1  ;24.805  ;461.49  ;9.486  ;-2.4809  ;14.208  ;0.63235"]
    assert em.virgula_e_decimal(brasileiro, ";") is True
    assert em.virgula_e_decimal(ingles, ";") is False
    assert em.virgula_e_decimal(["a;1,014.4;b"], ";") is False
    assert em.virgula_e_decimal(["a;1.014,4;b"], ";") is True
    # Sem prova (só inteiros, ou só números com três casas), vale o padrão do separador.
    assert em.virgula_e_decimal(["a;5663;78.611;24,805"], ";") is True
    assert em.virgula_e_decimal(["a,5663,78.611"], ",") is False
    assert em.virgula_e_decimal(["x;12"], ";", padrao=False) is False
    # Provas dos dois lados (arquivo editado à mão): o padrão.
    assert em.virgula_e_decimal(["a;461.49;461,49"], ";") is True
    # O nome do estudo e a data não contam como número.
    assert em.virgula_e_decimal(["Nome do estudo:Análise 1.25", "11:48; 10/11/2026"], ";") is True


@pytest.mark.parametrize("caso", t.CASOS)
def test_arquivos_com_ponto_decimal_dao_os_mesmos_esforcos(caso):
    forcas = em.ler_arquivo(t.csv_forcas(caso), f"{caso}-forcas.csv")
    em_en = em.ler_arquivo(em_ingles(t.csv_forcas(caso)), f"{caso}-forcas.csv")
    assert set(em_en.membros) == set(forcas.membros)
    for barra, pontos in forcas.membros.items():
        for p, q in zip(pontos, em_en.membros[barra], strict=True):
            assert q.chave == p.chave and q.vetor() == pytest.approx(p.vetor(), abs=1e-12)
    # O arquivo de reações tem meia dúzia de números: o formato vem da remessa (os arquivos
    # enviados juntos saem do mesmo computador).
    remessa = [em_ingles(f(caso)) for f in (t.csv_forcas, t.csv_reacoes, t.csv_apoios)]
    formato = em.formato_do_lote(remessa)
    assert formato is False
    reacoes = em.ler_arquivo(t.csv_reacoes(caso), f"{caso}-reacoes.csv").reacoes
    reacoes_en = em.ler_arquivo(
        em_ingles(t.csv_reacoes(caso)), f"{caso}-reacoes.csv", virgula_decimal=formato
    ).reacoes
    assert reacoes_en.modelo == pytest.approx(reacoes.modelo, abs=1e-12)
    apoios = am.ler_apoios(t.csv_apoios(caso), f"{caso}-apoios.csv")
    apoios_en = am.ler_apoios(
        em_ingles(t.csv_apoios(caso)), f"{caso}-apoios.csv", virgula_decimal=formato
    )
    for no, no_en in zip(apoios.nos, apoios_en.nos, strict=True):
        assert no_en.no == no.no and no_en.ponto == pytest.approx(no.ponto, abs=1e-12)
        assert no_en.forca_N == pytest.approx(no.forca_N, abs=1e-9)
        assert no_en.momento_Nm == pytest.approx(no.momento_Nm, abs=1e-9)


def test_fixacoes_com_ponto_decimal():
    fixacoes = am.ler_fixacoes(t.csv_fixacoes(), "fixacoes.csv")
    em_en = am.ler_fixacoes(em_ingles(t.csv_fixacoes()), "fixacoes.csv")
    assert [e.ponto for e in em_en.entidades] == [e.ponto for e in fixacoes.entidades]
    assert [e.tipo for e in em_en.entidades] == [e.tipo for e in fixacoes.entidades]


def test_formato_do_lote():
    brasileira = [f(caso) for caso in ("PP", "SC") for f in (t.csv_forcas, t.csv_reacoes)]
    assert em.formato_do_lote(brasileira) is True
    assert em.formato_do_lote([em_ingles(c) for c in brasileira]) is False
    assert em.formato_do_lote([]) is None
    assert em.formato_do_lote([b"sep=;\r\nSoma Y:;7.500;7.500\r\n"]) is None  # sem prova
    # Remessa misturada (arquivos de dois computadores): cada arquivo decide por si.
    assert em.formato_do_lote([brasileira[0], em_ingles(brasileira[0])]) is None


def test_reacoes_sozinhas_com_ponto_decimal_sao_o_caso_ambiguo():
    """Enviado sozinho, o arquivo de reações de um computador com o ponto decimal não tem como
    provar o formato: "7,500" (7500 N) é lido como 7,5 N. O tratamento automático conserta
    depois, contra os apoios ou as bases (tests/test_tratamento_do_modelo.py)."""
    certo = em.ler_arquivo(t.csv_reacoes("SC"), "SC-reacoes.csv").reacoes
    sozinho = em.ler_arquivo(em_ingles(t.csv_reacoes("SC")), "SC-reacoes.csv").reacoes
    assert sozinho.modelo[1] == pytest.approx(certo.modelo[1] / 1000)
