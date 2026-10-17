"""Escada com lances e patamares: geometria, verificações e o esquemático."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from core import degrau_escada as de
from core import escada_lances as el


@pytest.fixture(scope="module")
def alta() -> de.ResultadoEscada:
    """H = 5400 mm: 30 espelhos de 180 mm, piso 270 mm, dois lances automáticos."""
    return de.calcular_escada(de.EntradaDegrau(H_mm=5400))


def _nomes(esc: el.EscadaComPatamares) -> list[str]:
    return [v.nome for v in esc.verificacoes]


def test_divisao_automatica_igual_a_do_degrau(alta):
    esc = el.montar_escada(alta)
    assert esc.automatica and len(esc.lances) == alta.lances.n_lances == 2
    assert [ln.n_espelhos for ln in esc.lances] == [15, 15]
    primeiro, segundo = esc.lances
    assert primeiro.vao_longarina_mm == 15 * 270 and primeiro.projecao_mm == 14 * 270
    # segue em frente: o primeiro espelho do lance 2 fica no fim do patamar
    assert segundo.x_pe_mm == pytest.approx(15 * 270 + alta.entrada.patamar_mm - 270)
    assert esc.patamares[0].nivel_mm == pytest.approx(2700)
    assert el.aplicar_na_escada(alta, esc) is alta  # nada a trocar


def test_escada_em_u_inverte_o_sentido(alta):
    esc = el.montar_escada(alta, lances_em_u=True)
    assert [ln.sentido for ln in esc.lances] == [1, -1]
    borda = esc.lances[0].x_topo_mm
    assert esc.lances[1].x_pe_mm == pytest.approx(borda + 270)  # um piso antes do 1º espelho
    assert esc.patamares[0].volta and "em U" in el.texto_dos_lances(esc)


def test_patamares_informados_vao_para_o_multiplo_do_espelho(alta):
    esc = el.montar_escada(
        alta, [el.PatamarInformado(3700, 800, None, True), el.PatamarInformado(1500, 1200, 1000)]
    )
    assert [p.nivel_mm for p in esc.patamares] == [1440, 3780]  # ordenados e ajustados
    assert [ln.n_espelhos for ln in esc.lances] == [8, 13, 9]
    assert all(ln.h_mm == pytest.approx(180) for ln in esc.lances)
    linhas = {v.nome: v for v in esc.verificacoes}
    assert linhas["Altura dos patamares ajustada ao espelho"].status == "INFO"
    assert linhas["Espelhos e lances uniformes"].status == "ALERTA"  # 8, 13 e 9 espelhos
    assert linhas["Lance 2: altura ≤ 3000 mm"].status == "OK"
    assert (
        el.texto_dos_lances(esc) == "3 lance(s) (8, 13 e 9 espelhos; 180 mm) e 2 patamar(es), em U"
    )


def test_sem_ajuste_cada_lance_tem_o_seu_espelho(alta):
    esc = el.montar_escada(
        alta,
        [el.PatamarInformado(1500, 1200), el.PatamarInformado(3700, 800)],
        ajustar_ao_espelho=False,
    )
    assert [p.nivel_mm for p in esc.patamares] == [1500, 3700]
    assert len({round(ln.h_mm, 1) for ln in esc.lances}) > 1
    uniforme = next(v for v in esc.verificacoes if v.nome == "Espelhos e lances uniformes")
    assert uniforme.status == "ALERTA" and "múltiplos do espelho" in uniforme.formula


def test_limites_de_lance_e_patamar(alta):
    esc = el.montar_escada(alta, [el.PatamarInformado(5000, 500, 600)])
    linhas = {v.nome: v for v in esc.verificacoes}
    assert linhas["Lance 1: altura ≤ 3000 mm"].status == "NÃO OK"  # 5040 mm num lance só
    assert linhas["Patamar 1: comprimento ≥ 600 mm"].status == "NÃO OK"
    assert linhas["Patamar 1: largura ≥ largura da escada"].status == "NÃO OK"
    aplicado = el.aplicar_na_escada(alta, esc)
    nomes = [v.nome for v in aplicado.verificacoes]
    assert not any(
        nome in nomes for nome in el.SUBSTITUIDAS if nome != "Espelhos e lances uniformes"
    )
    assert "Lance 1: altura ≤ 3000 mm" in nomes and aplicado.status == "NÃO OK"
    assert len(nomes) == len(set(nomes))


@pytest.mark.parametrize(
    "patamares",
    [
        [el.PatamarInformado(0, 900)],
        [el.PatamarInformado(5400, 900)],
        [el.PatamarInformado(2700, 0)],
        [el.PatamarInformado(2700, 900, -5)],
        [el.PatamarInformado(2700, 900), el.PatamarInformado(2710, 900)],  # mesmo nível
        [el.PatamarInformado(60, 900)],  # menos de um espelho do piso
    ],
)
def test_patamares_impossiveis_viram_erro_claro(alta, patamares):
    with pytest.raises(de.EntradaInvalida):
        el.montar_escada(alta, patamares)


def test_esquematico_e_gravacao(alta):
    esc = el.montar_escada(
        alta, [el.PatamarInformado(1500, 1200, 1000), el.PatamarInformado(3700, 800, None, True)]
    )
    figura = el.figura_da_escada(esc)
    imagem = Image.open(io.BytesIO(figura.png))
    assert imagem.format == "PNG" and imagem.size == (figura.largura_px, figura.altura_px)
    assert "α = 33,7°" in figura.legenda and "o lance seguinte volta" in figura.legenda
    H, lances, patamares = el.geometria_do_dicionario(el.para_dicionario(esc))
    assert H == esc.H_mm and lances == esc.lances and patamares == esc.patamares
    assert el.figura_esquematico(H, lances, patamares).png == figura.png
    assert len(el.linhas_dos_lances(esc)) == 3 and len(el.linhas_dos_patamares(esc)) == 2
