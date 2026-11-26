"""Placas de base, rodada de 26/11/2026: status com ressalvas, busca de diâmetro com o bloco fora,
e′_V da fila de um chumbador só, avisos agrupados na envoltória e desenho do corte."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import base_de_pilar as bp
from core.desenho_placa_base import figura_da_base

PADRAO = bp.EntradaBase()


def test_alerta_que_e_ressalva_aprova_com_ressalvas():
    # tração: a cortante vai aos chumbadores direto no furo, com o alerta do deslizamento
    r = bp.calcular(replace(PADRAO, n_sd_kN=-20, v_sd_kN=5))
    assert r.status == "ALERTA"
    assert not any(bp.falta_dado(v) for v in r.verificacoes if v.status == "ALERTA")
    assert r.situacao == bp.APROVADO_COM_RESSALVAS


def test_alerta_que_pede_dado_continua_inconclusivo():
    r = bp.calcular(replace(PADRAO, modo_bloco="verificacao"))
    assert r.situacao == bp.INCONCLUSIVO


def test_busca_do_diametro_por_formula_nao_conta_o_que_depende_do_bloco():
    # bloco mínimo sem armadura: o cone reprova, mas o diâmetro não resolve o cone
    e = bp.EntradaBase(por_formula=True, chumbador="M24", n_sd_kN=-200.0, m_sd_kNm=30.0)
    sem = bp.calcular(e)
    assert any(v.nome == bp.LINHA_DO_CONE and v.status == "NÃO OK" for v in sem.verificacoes)
    assert bp.menor_diametro_que_atende(e) is not None
    com = bp.menor_diametro_que_atende(replace(e, armadura_de_ancoragem=True))
    assert com is not None and bp.chumbadores_passam(com)


@pytest.mark.parametrize("sinal", [-1, 1])
def test_borda_com_um_chumbador_na_fila_nao_tem_excentricidade(sinal):
    e = replace(
        PADRAO,
        n_sd_kN=-20,
        v_sd_kN=0,
        vx_kN=6 * sinal,
        vy_kN=0,
        cortante=bp.CORTANTE_DIRETOS,
        bloco_x_mm=1200,
        bloco_y_mm=900,
        bloco_z_mm=900,
    )
    r = bp.calcular(e)
    borda = next(v for v in r.verificacoes if v.nome == bp.LINHA_RUPTURA_DA_BORDA)
    if "(1 chumbador(es))" in borda.formula:
        assert "e′_V = 0 mm" in borda.formula


def test_avisos_iguais_das_combinacoes_saem_uma_vez():
    casos = tuple(bp.CasoDeCarga(f"C{i}", -10.0 - i, 0, 0, 5.0 + i) for i in range(6))
    r = bp.calcular(replace(PADRAO, casos=casos))
    sem_atrito = [a for a in r.avisos if "não há atrito" in a]
    assert len(sem_atrito) == 1 and "o mesmo em 6 combinações" in sem_atrito[0]


def test_detalhamento_diz_a_distancia_real_do_chumbador_a_face_do_bloco():
    r = bp.calcular(PADRAO)
    bloco = dict(r.detalhamento)["Bloco mínimo"]
    n_b, b_b, _ = bp.bloco_minimo(PADRAO, r.geometria, r.linha)
    c_x = n_b / 2 - max(abs(x) for x, _ in r.geometria.posicoes)
    assert f"a {c_x:.0f} mm da face em ℓx" in bloco and "c_a1 e c_a2" in bloco
    arruelas = dict(r.detalhamento)["Arruelas especiais"]
    assert "soltas, sem solda" in arruelas
    soldadas = bp.calcular(replace(PADRAO, cortante=bp.CORTANTE_ARRUELAS))
    assert "soldadas à placa com filete" in dict(soldadas.detalhamento)["Arruelas especiais"]


@pytest.mark.parametrize("m", [30.0, -30.0])
def test_desenho_sai_com_momento_dos_dois_sinais(m):
    r = bp.calcular(replace(PADRAO, n_sd_kN=50, m_sd_kNm=m))
    assert figura_da_base(r).png.startswith(b"\x89PNG")


def test_pdf_do_memorial_escreve_raiz_e_nome_da_combinacao():
    pytest.importorskip("pypdfium2")
    import pypdfium2 as pdfium

    casos = (
        bp.CasoDeCarga("C45-ELU", 300, 30, 5, 20),
        bp.CasoDeCarga("C46-ELU", 250, 20, 3, 10),
    )
    pdf = bp.memorial_da_base(bp.calcular(replace(PADRAO, casos=casos)), formato="pdf")
    doc = pdfium.PdfDocument(pdf)
    texto = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    from core.pdf_fonts import fonte_pdf

    if fonte_pdf().unicode:
        assert "√(A" in texto and "v(A" not in texto
    assert "C45-ELU" in texto
