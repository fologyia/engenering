"""Cargas do piso pelo esqueleto do modelo: a área de influência de cada viga sob as chapas."""

from __future__ import annotations

import math

import pytest

from core import cargas_pelo_modelo as cpm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc

ALTURA = 0.30  # vigas de 300 mm, linha de centro 0,15 m abaixo do topo


def barra(nome, inicio, fim, secao=(300.0, 150.0)):
    return ld.CorpoDoModelo(
        nome,
        "",
        "",
        tuple(float(v) for v in inicio),
        tuple(float(v) for v in fim),
        math.dist(inicio, fim),
        None,
        "BARRA",
        secao,
    )


def chapa(nome, contorno, aberturas=(), espessura=0.00635):
    """Chapa com o contorno da macro v5 (face de baixo no nível do topo das vigas)."""
    xs = [p[0] for p in contorno]
    return ld.CorpoDoModelo(
        nome,
        "Item da lista de corte48",
        "Item da lista de corte48",
        (min(xs), contorno[0][1], contorno[0][2]),
        (max(xs), contorno[0][1], contorno[0][2]),
        max(xs) - min(xs),
        None,
        "CHAPA",
        (1000.0, espessura * 1e3),
        None,
        tuple(tuple(float(v) for v in p) for p in contorno),
        tuple(tuple(tuple(float(v) for v in p) for p in a) for a in aberturas),
    )


def piso_6x3(*extras, aberturas=()) -> ld.GeometriaDoModelo:
    """Chapa de 6 × 3 m sobre três vigas em X (z = 0; 1,5; 3) no topo y = 0."""
    y = -ALTURA / 2
    return ld.GeometriaDoModelo(
        corpos=(
            barra("V0", (0, y, 0), (6, y, 0)),
            barra("V1", (0, y, 1.5), (6, y, 1.5)),
            barra("V2", (0, y, 3), (6, y, 3)),
            chapa("Piso", [(0, 0, 0), (6, 0, 0), (6, 0, 3), (0, 0, 3)], aberturas),
            *extras,
        )
    )


def kn_m(d: cpm.DistribuicaoDoPiso, caso: str) -> dict[str, float]:
    return {c.viga: c.kN_m for c in d.do_caso(caso)}


# ------------------------------------------------------------------ geometria plana
def test_area_e_ponto_dentro():
    quadrado = [(0, 0), (2, 0), (2, 2), (0, 2)]
    assert cpm.area_do_poligono(quadrado) == pytest.approx(4.0)
    assert cpm.area_do_poligono([(0, 0), (4, 0), (0, 3)]) == pytest.approx(6.0)
    assert cpm.dentro((1, 1), quadrado) and not cpm.dentro((3, 1), quadrado)
    assert cpm.distancia_ao_segmento((1, 1), (0, 0), (2, 0)) == (pytest.approx(1.0), 0.5)


# ------------------------------------------------------------------ distribuição
def test_chapa_sobre_vigas_paralelas_divide_meio_vao():
    d = cpm.distribuir(piso_6x3(), {"SC": 5.0}, "Y")
    cargas = kn_m(d, "SC")
    # Larguras de influência: 0,75 / 1,50 / 0,75 m → 3,75 / 7,50 / 3,75 kN/m.
    assert cargas["V0"] == pytest.approx(3.75, rel=0.03)
    assert cargas["V1"] == pytest.approx(7.50, rel=0.03)
    assert cargas["V2"] == pytest.approx(3.75, rel=0.03)
    assert d.total("SC") == pytest.approx(5.0 * 18.0)  # a conferência fecha
    assert not d.avisos and d.chapas[0].fonte == "contorno"


def test_abertura_tira_a_area_dela():
    furo = [(2, 0, 1), (3, 0, 1), (3, 0, 2), (2, 0, 2)]
    d = cpm.distribuir(piso_6x3(aberturas=[furo]), {"SC": 5.0}, "Y")
    assert d.chapas[0].area_m2 == pytest.approx(17.0)
    assert d.total("SC") == pytest.approx(5.0 * 17.0)
    # O buraco fica sobre a viga do meio: ela perde a carga dele.
    assert kn_m(d, "SC")["V1"] < 7.5 * 0.9


def test_escada_inclinada_usa_a_projecao_horizontal():
    angulo = math.radians(30)
    comprimento, largura = 4.0, 1.0
    dx, dy = comprimento * math.cos(angulo), comprimento * math.sin(angulo)
    baixo = (-ALTURA / 2) * math.cos(angulo)
    banzos = (
        barra("B1", (0, baixo, 0), (dx, dy + baixo, 0)),
        barra("B2", (0, baixo, largura), (dx, dy + baixo, largura)),
    )
    placa = chapa("Degraus", [(0, 0, 0), (dx, dy, 0), (dx, dy, largura), (0, 0, largura)])
    d = cpm.distribuir(ld.GeometriaDoModelo(corpos=(*banzos, placa)), {"SC": 3.0}, "Y")
    assert d.chapas[0].inclinacao_graus == pytest.approx(30.0, abs=0.1)
    assert d.total("SC") == pytest.approx(3.0 * comprimento * largura * math.cos(angulo))
    assert kn_m(d, "SC")["B1"] == pytest.approx(kn_m(d, "SC")["B2"], rel=0.02)


def test_chapa_em_pe_nao_e_piso():
    gusset = chapa("Gusset", [(0, -0.5, 0), (0.4, -0.5, 0), (0.4, 0, 0), (0, 0, 0)])
    d = cpm.distribuir(piso_6x3(gusset), {"SC": 5.0}, "Y")
    assert [c.nome for c in d.chapas] == ["Piso"]


def test_chapa_sem_viga_embaixo_avisa():
    solta = chapa("Solta", [(10, 0, 0), (11, 0, 0), (11, 0, 1), (10, 0, 1)])
    d = cpm.distribuir(piso_6x3(solta), {"SC": 5.0}, "Y")
    assert any("Solta: nenhuma viga logo abaixo" in a for a in d.avisos)
    assert d.total("SC") == pytest.approx(90.0)  # a dela fica de fora, e o aviso diz


def test_balanco_da_chapa_avisa():
    y = -ALTURA / 2
    g = ld.GeometriaDoModelo(
        corpos=(
            barra("V0", (0, y, 0), (6, y, 0)),
            barra("V1", (0, y, 1.5), (6, y, 1.5)),
            chapa("Piso", [(0, 0, 0), (6, 0, 0), (6, 0, 2.5), (0, 0, 2.5)]),
        )
    )
    d = cpm.distribuir(g, {"SC": 5.0}, "Y")
    assert any("balanço da chapa" in a for a in d.avisos)


def test_viga_mais_comprida_que_a_chapa_avisa_o_trecho():
    y = -ALTURA / 2
    g = ld.GeometriaDoModelo(
        corpos=(
            barra("V0", (0, y, 0), (6, y, 0)),
            barra("V1", (0, y, 1.0), (6, y, 1.0)),
            chapa("Piso", [(0, 0, 0), (3, 0, 0), (3, 0, 1), (0, 0, 1)]),
        )
    )
    d = cpm.distribuir(g, {"SC": 5.0}, "Y")
    carga = next(c for c in d.do_caso("SC") if c.viga == "V0")
    assert carga.trecho_m == pytest.approx(3.0, abs=0.1) and carga.comprimento_m == 6.0
    assert carga.kN_m == pytest.approx(carga.total_kN / 6.0)
    assert any("Carga só em parte da viga" in a for a in d.avisos)


# ------------------------------------------------------------------ esqueleto da macro v4
def test_chapa_retangular_da_v4_entra_e_a_recortada_fica_de_fora():
    y = -ALTURA / 2
    vigas = (barra("V0", (0, y, 0), (4, y, 0)), barra("V1", (0, y, 2), (4, y, 2)))
    espessura = 0.00635

    def chapa_v4(volume_relativo: float) -> ld.CorpoDoModelo:
        return ld.CorpoDoModelo(
            "Piso",
            "",
            "",
            (0.0, espessura / 2, 1.0),
            (4.0, espessura / 2, 1.0),
            4.0,
            4.0 * 2.0 * espessura * volume_relativo,
            "CHAPA",
            (2000.0, espessura * 1e3),
        )

    cheia = cpm.distribuir(ld.GeometriaDoModelo(corpos=(*vigas, chapa_v4(1.0))), {"SC": 5}, "Y")
    assert cheia.chapas[0].fonte == "retângulo" and cheia.total("SC") == pytest.approx(40.0)
    recortada = cpm.distribuir(
        ld.GeometriaDoModelo(corpos=(*vigas, chapa_v4(0.65))), {"SC": 5}, "Y"
    )
    assert not recortada.chapas and recortada.total("SC") == 0
    assert any("recortada (a chapa ocupa 65 % da caixa" in a for a in recortada.avisos)


def test_so_as_chapas_escolhidas_e_casos_sem_carga():
    d = cpm.distribuir(piso_6x3(), {"SC": 5.0, "PE": 0.0}, "Y", chapas_escolhidas=[])
    assert not d.cargas
    d = cpm.distribuir(piso_6x3(), {"SC": 5.0, "PE": 0.0, "X": float("nan")}, "Y")
    assert d.casos == ("SC",)


# ------------------------------------------------------------------ plano de cargas
def test_envia_ao_plano_e_a_conferencia_das_reacoes_fecha():
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao("SC", cargas=[pc.CargaDoModelo("Piso", 5.0, "kN/m²", "Z (vertical)")]),
    )
    assert cpm.cargas_por_area_do_plano(plano) == {"SC": 5.0}
    d = cpm.distribuir(piso_6x3(), cpm.cargas_por_area_do_plano(plano), "Y")
    novo = cpm.aplicar_no_plano(d, plano, {"SC": 5.0}, {"V1": "Viga-7(V1)"})
    acao = novo.acao("SC")
    assert acao.origem == cpm.ORIGEM and len(acao.cargas) == 3
    assert {c.unidade for c in acao.cargas} == {"kN/m"}
    assert any(c.elemento == "V1 (Viga-7(V1))" for c in acao.cargas)
    # As reações do estudo SC passam a ter com o que comparar: 90 kN para baixo.
    assert -em.total_esperado(acao)[2] == pytest.approx(90.0, rel=1e-3)
    # Caso que não estava no plano é criado.
    criado = cpm.aplicar_no_plano(d, pc.PlanoDeCargas(), {"SC": 5.0})
    assert criado.acao("SC") is not None and criado.acao("SC").origem == cpm.ORIGEM


def test_csv_das_cargas():
    d = cpm.distribuir(piso_6x3(), {"SC": 5.0}, "Y")
    texto = cpm.csv_das_cargas(d, {"V0": "Viga-1(V0)"}).decode("utf-8-sig")
    assert texto.startswith("Caso;Viga (corpo no SolidWorks);Viga no Simulation;kN/m")
    assert "SC;V0;Viga-1(V0);" in texto and texto.count("\r\n") == 4


# ------------------------------------------------------------------ grade × esqueleto
def test_grade_de_eixos_diferente_do_piso_do_esqueleto_trava_o_envio():
    """A grade de exemplo (12 × 3 m) contra o piso de 6 × 3 m do esqueleto: o dobro da área — o
    envio das cargas da grade fica travado; a grade com a planta do modelo passa."""
    chapas = cpm.chapas_do_piso(piso_6x3(), "Y")[0]
    motivo = cpm.grade_confere_com_o_modelo(36.0, 1, chapas)
    assert "36,00 m²" in motivo and "18,00 m²" in motivo and "chapas do esqueleto" in motivo
    assert cpm.grade_confere_com_o_modelo(18.0, 1, chapas) == ""
    assert cpm.grade_confere_com_o_modelo(9.0, 2, chapas) == ""  # dois níveis de 9 m²
    assert (
        cpm.grade_confere_com_o_modelo(36.0, 1, []) == ""
    )  # sem chapa de piso: não há com o que comparar


def test_linhas_da_grade_que_sobraram_no_plano_saem_e_as_outras_ficam():
    """O PE do usuário (24/10): as linhas da grade de exemplo (21,6 kN em barras "N1 · eixo A…")
    ficaram no plano e o guarda-corpo das bordas foi somado em cima. Tirar a grade deixa só o resto."""
    grade = pc.CargaDoModelo(
        "N1 · eixo A · 1–2; N1 · eixo B · 1–2", 0.585, "kN/m", "Z (vertical)", "", 4, 6.0
    )
    borda = pc.CargaDoModelo(
        "Gerenciamento de cantos1[5]", 0.36, "kN/m", "Z (vertical)", "", 1, 1.0
    )
    plano = pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PE", cargas=[grade, borda]))
    plano = pc.com_acao(plano, pc.nova_acao("SC", cargas=[borda]))
    assert cpm.cargas_da_grade_no_plano(plano) == [("PE", grade)]
    limpo = cpm.sem_cargas_da_grade(plano)
    assert limpo.acao("PE").cargas == (borda,) and limpo.acao("SC").cargas == (borda,)
    assert cpm.cargas_da_grade_no_plano(limpo) == []
