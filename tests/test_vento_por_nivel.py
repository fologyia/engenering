"""O vento barra a barra levado aos níveis (força de cada nível e por onde passa) e a forma
simplificada de aplicar no modelo (a força de cada nível nas linhas de vigas)."""

from __future__ import annotations

import random

import pytest

from core import plano_de_cargas as pc
from core import vento_por_barras as vpb
from core import vento_por_barras_registro as vbr
from core import vento_por_nivel as vpn
from tests.test_vento_por_barras import VENTO, _grade, pilar, viga


def _calcular(barras, elementos=(), direcoes=vpb.DIRECOES_PERPENDICULARES):
    return vpb.calcular(
        vpb.EntradaPorBarras(tuple(barras), VENTO, elementos=tuple(elementos), direcoes=direcoes)
    )


def _forca(r: vpb.ResultadoPorBarras, angulo: int, nome: str) -> tuple[float, float]:
    f = r.direcao(angulo).da_barra(nome)
    assert f is not None
    return f.fx_kN_m * f.comprimento_m, f.fy_kN_m * f.comprimento_m


# ------------------------------------------------------------------ níveis
def test_niveis_pelas_vigas_deitadas_com_o_patamar_e_sem_o_baldrame():
    barras = [
        *_grade(),
        viga("Patamar", (14.0, 0.0, 2.0), (14.8, 0.0, 2.0)),  # 0,8 m: um patamar é nível
        viga("Baldrame", (0.0, 0.0, 0.2), (6.0, 0.0, 0.2)),  # abaixo de 0,5 m: base
    ]
    niveis = vpn.niveis_da_estrutura(barras, 0.0)
    assert [round(n.cota_m, 3) for n in niveis] == [2.0, 4.0]
    assert niveis[1].comprimento_de_vigas_m == pytest.approx(3 * 6.0 + 4 * 6.0)


def test_linhas_de_vigas_em_x_e_em_y():
    linhas = vpn.linhas_de_vigas(_grade(), vpn.niveis_da_estrutura(_grade(), 0.0))
    em_x = sorted((ln.coordenada_m, ln.comprimento_m) for ln in linhas if ln.eixo == "X")
    em_y = sorted((ln.coordenada_m, ln.comprimento_m) for ln in linhas if ln.eixo == "Y")
    assert em_x == [pytest.approx((0.0, 12.0)), pytest.approx((6.0, 12.0))]
    assert em_y == [pytest.approx((x, 6.0)) for x in (0.0, 6.0, 12.0)]


# ------------------------------------------------------------------ da barra às pontas e aos níveis
def test_portico_metade_de_cada_barra_em_cada_ponta():
    barras = [pilar("P1", 0.0, 0.0), pilar("P2", 6.0, 0.0), viga("V", (0, 0, 4), (6, 0, 4))]
    r = _calcular(barras)
    vn = vpn.vento_por_nivel(r)
    assert len(vn.niveis) == 1 and vn.niveis[0].cota_m == pytest.approx(4.0)
    d = vn.direcao(90)
    pilares = _forca(r, 90, "P1")[1] + _forca(r, 90, "P2")[1]
    assert d.niveis[0].fy_kN == pytest.approx(pilares / 2 + _forca(r, 90, "V")[1])
    assert d.fy_base_kN == pytest.approx(pilares / 2)
    assert d.niveis[0].x_de_fy_m == pytest.approx(3.0)  # simétrico: passa no meio
    assert not vn.aproximados


def test_mao_francesa_no_meio_do_pilar_passa_pela_regra_da_alavanca():
    """A ponta de baixo da mão francesa fica a 3/4 da altura do pilar: 3/4 da força dela vai ao
    topo do pilar (o nível) e 1/4 ao pé (a fundação)."""
    barras = [
        pilar("P", 0.0, 0.0),
        viga("V", (0, 0, 4), (2, 0, 4)),
        vpb.BarraAoVento("MF", (0.0, 0.0, 3.0), (1.0, 0.0, 4.0), 0.10, 0.10),
    ]
    r = _calcular(barras)
    vn = vpn.vento_por_nivel(r)
    d = vn.direcao(90)
    pilar_y, mao_y, viga_y = (_forca(r, 90, n)[1] for n in ("P", "MF", "V"))
    assert d.niveis[0].fy_kN == pytest.approx(pilar_y / 2 + mao_y / 2 + mao_y / 2 * 0.75 + viga_y)
    assert d.fy_base_kN == pytest.approx(pilar_y / 2 + mao_y / 2 * 0.25)
    assert not vn.aproximados


def test_patamar_da_escada_recebe_os_montantes_e_metade_dos_lances():
    """Plataforma a 4 m (pilares em x = 0 e 6) e patamar a 2 m em x = 10: o vento dos montantes do
    patamar e metade de cada lance vão ao patamar, na posição dele, não à plataforma."""
    barras = [
        pilar("P1", 0.0, 0.0),
        pilar("P2", 6.0, 0.0),
        viga("V", (0, 0, 4), (6, 0, 4)),
        pilar("M1", 10.0, 0.0, 2.0),
        pilar("M2", 11.0, 0.0, 2.0),
        viga("VP", (10, 0, 2), (11, 0, 2)),
        vpb.BarraAoVento("Lance1", (14.0, 0.0, 0.0), (11.0, 0.0, 2.0), 0.20, 0.08),
        vpb.BarraAoVento("Lance2", (10.0, 0.0, 2.0), (6.0, 0.0, 4.0), 0.20, 0.08),
    ]
    r = _calcular(barras)
    vn = vpn.vento_por_nivel(r)
    assert [round(n.cota_m, 3) for n in vn.niveis] == [2.0, 4.0]
    d = vn.direcao(90)
    f = {n: _forca(r, 90, n)[1] for n in ("M1", "M2", "VP", "Lance1", "Lance2")}
    patamar = d.niveis[0]
    esperado = f["M1"] / 2 + f["M2"] / 2 + f["VP"] + f["Lance1"] / 2 + f["Lance2"] / 2
    assert patamar.fy_kN == pytest.approx(esperado)
    assert 10.0 <= patamar.x_de_fy_m <= 14.0  # passa no patamar
    assert not vn.aproximados


def test_pe_do_lance_abaixo_do_patamar_pela_altura_do_perfil_vai_ao_patamar():
    """Pelas linhas de centro, o pé do lance fica 18 cm abaixo do patamar (o eixo da longarina
    abaixo do da viga): vai ao patamar, sem aviso — a 40 cm já não é dele."""
    base = [
        pilar("M1", 10.0, 0.0, 2.0),
        pilar("M2", 11.0, 0.0, 2.0),
        viga("VP", (10, 0, 2), (11, 0, 2)),
    ]
    perto = vpb.BarraAoVento("Lance", (6.0, 0.0, 4.0), (10.5, 0.0, 1.82), 0.20, 0.08)
    vn = vpn.vento_por_nivel(_calcular([*_grade(), *base, perto]))
    assert not vn.aproximados
    longe = vpb.BarraAoVento("Lance", (6.0, 0.0, 4.0), (10.5, 0.0, 1.60), 0.20, 0.08)
    assert vpn.vento_por_nivel(_calcular([*_grade(), *base, longe])).aproximados == ("Lance",)


def test_ponta_solta_vai_pela_faixa_de_altura_com_aviso():
    barras = [*_grade(), pilar("Poste", 20.0, 0.0, 3.0)]  # topo a 3 m, sem nada ligado
    vn = vpn.vento_por_nivel(_calcular(barras))
    assert vn.aproximados == ("Poste",)
    assert any("faixa de altura" in a for a in vn.avisos)


def test_sem_vigas_deitadas_tudo_vai_a_fundacao_com_aviso():
    vn = vpn.vento_por_nivel(_calcular([pilar("P1", 0, 0), pilar("P2", 6, 0)]))
    assert vn.niveis == () and vn.nivel_principal is None and not vn.simplificada_possivel
    assert "sem nível" in vn.avisos[0]


@pytest.mark.parametrize("semente", range(25))
def test_niveis_mais_base_dao_a_forca_total(semente):
    """Estruturas sorteadas (pilares, vigas, diagonais, guarda-corpos): nada se perde."""
    sorteio = random.Random(semente)
    barras = list(_grade())
    for k in range(sorteio.randint(1, 8)):
        a = (sorteio.uniform(-2, 14), sorteio.uniform(-2, 8), sorteio.uniform(0, 4))
        b = (sorteio.uniform(-2, 14), sorteio.uniform(-2, 8), sorteio.uniform(0, 6))
        barras.append(vpb.BarraAoVento(f"S{k}", a, b, 0.15, 0.10))
    elementos = [
        vpb.ElementoAoVento("GC", vpb.TIPO_GUARDA_CORPO, (0.0, 0.0, 4.0), (6.0, 0.0, 4.0)),
        vpb.ElementoAoVento("Vaso", vpb.TIPO_CILINDRO, (3.0, 3.0, 4.0), altura_m=1.5),
    ]
    r = _calcular(barras, elementos, vpb.DIRECOES_COM_DIAGONAIS)
    vn = vpn.vento_por_nivel(r)
    for d, original in zip(vn.direcoes, r.direcoes, strict=True):
        assert d.fx_kN == pytest.approx(original.fx_kN, abs=1e-9)
        assert d.fy_kN == pytest.approx(original.fy_kN, abs=1e-9)


# ------------------------------------------------------------------ forma simplificada
def _plataforma_assimetrica():
    """A grade com um painel cheio perto de x = 12: a resultante do vento em Y sai do meio."""
    elementos = [
        vpb.ElementoAoVento(
            "Painel", vpb.TIPO_PAINEL, (9.0, 0.0, 4.0), (12.0, 0.0, 4.0), altura_m=1.5
        ),
    ]
    return _calcular(_grade(), elementos, vpb.DIRECOES_COM_DIAGONAIS)


def test_simplificada_conserva_a_forca_e_a_torcao_de_cada_nivel():
    vn = vpn.vento_por_nivel(_plataforma_assimetrica())
    assert vn.simplificada_possivel
    for d in vn.direcoes:
        for n in d.niveis:
            em_x = [c for c in n.cargas if c.linha.eixo == "X"]
            em_y = [c for c in n.cargas if c.linha.eixo == "Y"]
            assert sum(c.forca_kN for c in em_x) == pytest.approx(n.fx_kN, abs=1e-9)
            assert sum(c.forca_kN for c in em_y) == pytest.approx(n.fy_kN, abs=1e-9)
            if abs(n.fy_kN) > 1e-9:
                momento = sum(c.forca_kN * c.linha.coordenada_m for c in em_y)
                assert momento == pytest.approx(n.x_de_fy_m * n.fy_kN, abs=1e-9)
            if abs(n.fx_kN) > 1e-9:
                momento = sum(c.forca_kN * c.linha.coordenada_m for c in em_x)
                assert momento == pytest.approx(n.y_de_fx_m * n.fx_kN, abs=1e-9)
            assert n.torcao_fora_kNm == pytest.approx(0.0)
    w90 = vn.direcao(90).niveis[0]
    assert w90.x_de_fy_m > 6.0  # o painel puxa a resultante para o lado dele


def test_simplificada_vai_ao_plano_com_poucas_cargas_e_a_mesma_soma():
    r = _plataforma_assimetrica()
    vn = vpn.vento_por_nivel(r)
    acoes = vpn.acoes_simplificadas(vn)
    assert [a.codigo for a in acoes] == list(pc.CODIGOS_DE_VENTO)
    for acao, d in zip(acoes, vn.direcoes, strict=True):
        assert acao.origem == vpb.ORIGEM and not pc.validar_acao(acao)
        fx = sum(c.valor * c.comprimento_m for c in acao.cargas if c.direcao.endswith("X"))
        fy = sum(c.valor * c.comprimento_m for c in acao.cargas if c.direcao.endswith("Y"))
        assert fx == pytest.approx(d.fx_kN - d.fx_base_kN, abs=1e-3)
        assert fy == pytest.approx(d.fy_kN - d.fy_base_kN, abs=1e-3)
        assert all(c.unidade == "kN/m" for c in acao.cargas)
        assert "forma simplificada" in acao.resumo
    barra_a_barra = vpn.numero_de_cargas_no_estudo(vpb.acoes_para_o_plano(r))
    assert vpn.numero_de_cargas_no_estudo(acoes) < barra_a_barra
    plano = vpb.plano_com_o_vento(pc.PlanoDeCargas(), r, acoes)
    assert not any("aparece duas vezes" in i.texto for i in pc.conferir_plano(plano))


def test_uma_linha_so_avisa_a_torcao_que_fica_de_fora():
    barras = [
        pilar("P1", 0.0, 0.0),
        pilar("P2", 6.0, 0.0),
        pilar("P3", 0.0, 4.0),
        viga("VX", (0, 0, 4), (6, 0, 4)),  # a única viga em X, em y = 0
        viga("VY1", (0, 0, 4), (0, 4, 4)),
        viga("VY2", (6, 0, 4), (6, 4, 4)),
    ]
    vn = vpn.vento_por_nivel(_calcular(barras))
    n = vn.direcao(0).niveis[0]
    assert len([c for c in n.cargas if c.linha.eixo == "X"]) == 1
    assert n.torcao_fora_kNm != pytest.approx(0.0)  # o pilar em y = 4 vai para y = 0
    if abs(n.torcao_fora_kNm) >= vpn.TORCAO_RELEVANTE_KNM:
        assert any("torção" in a and "W0" in a for a in vn.avisos)


def test_nivel_sem_vigas_na_direcao_do_vento_nao_aceita_a_simplificada():
    barras = [pilar("P1", 0.0, 0.0), pilar("P2", 6.0, 0.0), viga("VX", (0, 0, 4), (6, 0, 4))]
    vn = vpn.vento_por_nivel(_calcular(barras))
    assert vn.direcao(90).niveis[0].sem_linhas == ("Y",)
    assert not vn.simplificada_possivel
    assert any("W90" in a and "não serve" in a for a in vn.avisos)


def test_flexao_local_que_fica_de_fora():
    r = _calcular([pilar("P1", 0.0, 0.0), pilar("P2", 6.0, 0.0), viga("V", (0, 0, 4), (6, 0, 4))])
    d = vpn.vento_por_nivel(r).direcao(90)
    f = r.direcao(90).da_barra("V")
    assert f is not None
    assert d.flexao_local_kNm == pytest.approx(f.kN_m * 6.0**2 / 8)
    assert d.barra_da_flexao == "V"


# ------------------------------------------------------------------ coordenadas e tabelas
def test_coordenadas_no_modelo_do_solidworks():
    assert vpn.linha_no_modelo("X", 0.97, "Y") == "Z = −0,970 m"  # o Y da planta é o −Z
    assert vpn.linha_no_modelo("X", 0.97, "Z") == "Y = 0,970 m"
    assert vpn.linha_no_modelo("Y", 1.5, "Y") == "X = 1,500 m"
    assert vpn.sentido_no_modelo(0.4, "Y", "Y") == "−Z"
    assert vpn.sentido_no_modelo(0.4, "Y", "Z") == "+Y"
    assert vpn.sentido_no_modelo(-0.4, "X", "Y") == "−X"


def test_tabelas_e_registro_trazem_a_forca_de_cada_nivel():
    r = _plataforma_assimetrica()
    vn = vpn.vento_por_nivel(r)
    tabela = vpn.tabela_por_nivel(vn)
    assert len(tabela) == len(r.direcoes) * (len(vn.niveis) + 1)
    assert {t["Caso"] for t in tabela} == {d.codigo for d in r.direcoes}
    assert len(vpn.tabela_simplificada(vn)) >= len(r.direcoes)
    assert vpn.csv_simplificado(vn).decode("utf-8-sig").startswith("Caso;Nível;Linha")
    registro = vbr.registro_vento_por_barras(r)
    legendas = [t["legenda"] for t in registro["resultados"]["tabelas_memorial"]]
    assert any(legenda.startswith("Força do vento em cada nível") for legenda in legendas)
