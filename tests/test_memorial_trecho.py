"""O padrão dos memoriais separados: o trecho de uma peça para colar no documento oficial.

Todo botão "Memorial …"/"Gerar o Word" de página sai como trecho (core.memorial_trecho): uma seção
só, A4 em retrato, sem cabeçalho nem rodapé, sem capa, resumo executivo ou aprovações, títulos
nativos sem número, legendas com numeração automática (campo SEQ), tabelas que cabem em 16 cm e
as contas como equações do Word. O relatório geral (Central de relatórios) é outro documento e
não entra aqui.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from docx.shared import Mm

from core import base_de_pilar as bp
from core import bolted_joint_check as chk
from core import column_buckling as cb
from core import degrau_escada as de
from core import equacao_word as eq
from core import ligacoes as lg
from core import ligacoes_soldadas as ls
from core import section_catalog as sc
from core.coluna_word import gerar_word_coluna
from core.degrau_word import gerar_word_degrau
from core.memorial_trecho import LARGURA_UTIL_MM, Trecho, separar_combinacao, texto_de_memorial

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_memorial_ligacao_parafusada import M22  # noqa: E402

FORA_DO_TRECHO = (
    "Resumo executivo", "Controle do documento", "Aprovações", "Elaborado por", "Snapshot",
    "Não informado", "[a preencher]",
)  # fmt: skip
TITULO_NUMERADO = re.compile(r"^\d+(\.\d+)*\.?\s")


def _documento(conteudo: bytes):
    return Document(BytesIO(conteudo))


def conferir_trecho(conteudo: bytes) -> str:
    """As regras do trecho; devolve o texto (parágrafos e tabelas)."""
    d = _documento(conteudo)
    assert len(d.sections) == 1
    secao = d.sections[0]
    assert abs(secao.page_width - Mm(210)) < Mm(1) and secao.page_height > secao.page_width
    assert not any(p.text.strip() for p in secao.header.paragraphs)
    assert not any(p.text.strip() for p in secao.footer.paragraphs)
    titulos = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    assert titulos, "o trecho abre com o título da peça"
    assert not [t for t in titulos if TITULO_NUMERADO.match(t)], titulos
    xml = d.element.body.xml
    assert xml.count("SEQ Tabela") == len(d.tables)  # toda tabela com legenda numerada
    largura_max = Mm(LARGURA_UTIL_MM + 1)
    for tabela in d.tables:
        larguras = [c.width or 0 for c in tabela.rows[0].cells]
        assert sum(larguras) <= largura_max, sum(larguras)
    texto = "\n".join(
        [p.text for p in d.paragraphs]
        + [c.text for t in d.tables for linha in t.rows for c in linha.cells]
    )
    for proibido in FORA_DO_TRECHO:
        assert proibido not in texto, proibido
    return texto


# ------------------------------------------------------------------------------- equações
def test_equacao_vira_omml_com_indice_fracao_e_raiz():
    xml = eq.omml("t_p,min = √(4·F_t·m/(b_eff·f_y/γ_a1)) = 7,91 mm")
    assert "<m:sSub>" in xml and "<m:f>" in xml and "<m:rad>" in xml
    assert '<m:t xml:space="preserve">p,min</m:t>' in xml
    assert '<m:t xml:space="preserve">mm</m:t>' in xml  # unidade em letra reta (sty p)
    arvore = eq.ler("σ = 0,036 kN/mm")
    assert arvore[-1][0] == "f"  # 0,036 kN sobre mm


def test_equacao_que_nao_fecha_vira_texto_sem_erro():
    xml = eq.omml("conta (sem fechar")
    assert "conta (sem fechar" in xml and "<m:oMathPara" in xml


def test_texto_de_memorial_tira_conselho_de_tela_e_separa_a_combinacao():
    assert separar_combinacao("[C16-ELU] σ = 1") == ("C16-ELU", "σ = 1")
    limpo = texto_de_memorial(
        "ℓy = 270 mm (senão, aumente a₂ ou a₁); X ≤ 1 (caso contrário, refazer)"
    )
    assert "senão" not in limpo and "caso contrário" not in limpo and "270 mm" in limpo
    assert texto_de_memorial("ABNT NBR 8800:2025, Subseção 6.7, pela 6.7").count("6.7") == 2


def test_legenda_tem_campo_seq_e_tira_o_numero_do_modulo():
    t = Trecho()
    t.tabela(["a"], [["1"]], legenda="Tabela 1 - Entradas usadas")
    xml = t.doc.element.body.xml
    assert "SEQ Tabela" in xml and "Tabela 1 - " not in xml


# ------------------------------------------------------------------------------- módulos
BASE = bp.EntradaBase(
    perfil="W 200 x 31,3", chumbador='3/4"', a1_mm=45, a2_mm=160, t_placa_mm=16, lx_mm=415,
    ly_mm=270, bloco_x_mm=540, bloco_y_mm=400, e_n_mm=50, h_ef_mm=250, verificar_concreto=True,
    cortante=bp.CORTANTE_ARRUELAS,
    casos=(bp.CasoDeCarga("C08-ELU", 38, 1.6, 0, 4.8), bp.CasoDeCarga("C16-ELU", -18, 1.6, 0, 4.8)),
)  # fmt: skip


def test_placa_de_base_na_sequencia_do_memorial_oficial():
    conteudo = bp.memorial_da_base(bp.calcular(BASE))
    texto = conferir_trecho(conteudo)
    d = _documento(conteudo)
    titulos = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    sequencia = [
        "Normas e critérios", "Materiais e dados de entrada", "Esforços de cálculo", "Desenho",
        "Hipóteses de cálculo", "Verificações", "Resumo das verificações",
        "Detalhamento construtivo", "Conclusão", "Símbolos",
    ]  # fmt: skip
    posicoes = [titulos.index(t) for t in sequencia]
    assert posicoes == sorted(posicoes)
    assert d.element.body.xml.count("<m:oMathPara") >= 8  # as contas como equações do Word
    assert "SEQ Figura" in d.element.body.xml
    assert "[C16-ELU]" not in texto and "combinação que governa: C16-ELU" in texto
    assert "Subseção 6.7" in texto and "Subseção 6,7" not in texto
    assert "Este item apresenta a verificação da base do pilar W 200 x 31,3" in texto


def test_placa_de_base_em_pdf_continua_o_documento_completo():
    assert bp.memorial_da_base(bp.calcular(replace(BASE, casos=())), formato="pdf")[:4] == b"%PDF"


def test_ligacoes_e_parafusos():
    conferir_trecho(lg.memorial_da_ligacao(lg.calcular(ls.EntradaBarraSoldada()), formato="word"))
    texto = conferir_trecho(chk.memorial_da_ligacao(M22, chk.verificar_ligacao(M22), None))
    assert "Resumo das verificações" in texto


def test_flambagem_e_degrau():
    secao = cb.secao_de_perfil(sc.listar_perfis()["W 250 x 32,7"])
    entrada = cb.EntradaColuna(
        secao=secao, fy_MPa=345.0, norma="NBR8800_2008", Lx_mm=4000.0, Ly_mm=2000.0,
        N_Sd_kN=300.0, Mx_kNm=40.0, My_kNm=3.0, razao_m1_m2_x=0.0,
    )  # fmt: skip
    conferir_trecho(gerar_word_coluna(entrada, cb.verificar_coluna(entrada)))
    texto = conferir_trecho(gerar_word_degrau(de.calcular_escada(de.EntradaDegrau()), None))
    assert "Limitações do cálculo" in texto


@pytest.mark.parametrize("modulo", ["fadiga"])
def test_fadiga(modulo):
    from tests.test_memorial_word import MemorialWordTests

    caso = MemorialWordTests()
    caso.setUp()
    from core import memorial_word

    conferir_trecho(memorial_word.gerar_memorial_fadiga_word(caso.dados, caso.linhas))


def test_calculo_de_pecas_e_montador():
    from core import montador_grandezas as g
    from core.elementos_base import calcular_caso
    from core.elementos_word import gerar_word_do_caso
    from tests.test_elementos_catalogo import CASOS
    from tests.test_montador_itens import _word, mm

    caso = CASOS[0]
    valores = caso.padroes()
    conferir_trecho(gerar_word_do_caso(caso, valores, calcular_caso(caso, valores)))
    conferir_trecho(_word(mm.MODELOS[0], g.SISTEMA_SOLIDOS))
