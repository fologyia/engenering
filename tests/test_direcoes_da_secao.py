"""Para que lado o Simulation virou a seção de cada pilar: a linha da direção 1 (macro v6 ou
perfil), o axial pela base e pelo peso próprio, o sentido pela carga do vento dentro dos elementos
e a reação horizontal na base no espaço — num pilar em balanço sintético, em que a resposta é
conhecida (a reação é −q·L), para várias orientações da seção e as duas ordens dos elementos."""

from __future__ import annotations

import math

import pytest

from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import direcoes_da_secao as ds
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf

L, N_ELEMENTOS, PESO = 3.0, 6, 0.4  # m, elementos, kN/m
VIGA = "Viga-1(Pilar[1])"
VENTO = (0.8, 0.3, 0.0)  # kN/m na planta, no W0


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def pontos(q, d1, para_cima=True):
    """Esforço interno nas pontas de cada elemento de um pilar em balanço (topo livre) com a carga
    distribuída ``q`` (kN/m, planta), nos eixos do Simulation (axial, d1, d2 = axial × d1)."""
    axial = (0.0, 0.0, 1.0) if para_cima else (0.0, 0.0, -1.0)
    d2 = _cross(axial, d1)
    w = (_dot(q, axial), _dot(q, d1), _dot(q, d2))

    def interno(x):  # o topo (livre) em x = L subindo, em x = 0 descendo
        return [wi * (L - x) if para_cima else -wi * x for wi in w]

    def momentos(x):  # dM1/dx = V2 e dM2/dx = −V1 (conferido nos arquivos reais), topo livre
        resto = (L - x) ** 2 / 2 if para_cima else x**2 / 2
        return -w[2] * resto, w[1] * resto

    lista = []
    ell = L / N_ELEMENTOS
    for i in range(N_ELEMENTOS):
        for fim, x in (("1", i * ell), ("2", (i + 1) * ell)):
            n, v1, v2 = interno(x)
            m1, m2 = momentos(x)
            lista.append(em.PontoDeEsforco(str(i + 1), fim, n, v1, v2, m1, m2, 0.0))
    return tuple(lista)


def dados(d1, para_cima=True, casos=("PP", "W0")):
    cargas = {"PP": (0.0, 0.0, -PESO), "W0": VENTO, "SC": (0.0, 0.0, -1.0)}
    importados = {
        c: em.CasoImportado(c, c, f"{c}.csv", "", c, {VIGA: pontos(cargas[c], d1, para_cima)})
        for c in casos
    }
    return em.EsforcosDoModelo(
        casos=importados,
        membros={VIGA: em.ConfiguracaoDoMembro(tipo="Pilar")},
        eixo_vertical="Z",
    )


def corpo(direcao_1=None, folga=10.0, direcao_secao=None, perfil="W 310 x 32,7"):
    return ld.CorpoDoModelo(
        "Pilar[1]", "W<1>", perfil, (0.0, 0.0, 0.0), (0.0, 0.0, L), L, forma=ld.FORMA_BARRA,
        secao_mm=(313.0, 102.0), direcao_secao=direcao_secao, direcao_1=direcao_1,
        folga_da_direcao_1_mm=folga if direcao_1 else None,
    )  # fmt: skip


def calcular(d, c, aplicada=VENTO, secao=None):
    quadro = qf.montar_quadro(d)
    total = {"W0": {"Pilar[1]": tuple(v * L for v in aplicada)}}
    r = ds.direcoes_dos_pilares(quadro, d, {VIGA: c}, "Z", total,
                                {"Pilar[1]": secao} if secao else None)  # fmt: skip
    return quadro, r.pilares[VIGA], r


ORIENTACOES = [0.0, 30.0, 90.0, 145.0, -120.0]


@pytest.mark.parametrize("graus", ORIENTACOES)
@pytest.mark.parametrize("para_cima", [True, False], ids=["fim1-na-base", "fim2-na-base"])
@pytest.mark.parametrize("linha", ["macro-mesmo-sentido", "macro-sentido-oposto", "sem-linha"])
def test_a_reacao_horizontal_e_menos_q_vezes_l(graus, para_cima, linha):
    a = math.radians(graus)
    d1 = (math.cos(a), math.sin(a), 0.0)
    direcao_1 = {
        "macro-mesmo-sentido": d1,
        "macro-sentido-oposto": tuple(-v for v in d1),
        "sem-linha": None,
    }[linha]
    quadro, d, _ = calcular(dados(d1, para_cima), corpo(direcao_1))
    assert d.sabida, d.sentido
    assert d.d1 == pytest.approx(d1, abs=1e-9)  # o sentido certo, qualquer que fosse o da macro
    assert d.sentido == "W0"
    assert d.linha == (ds.LINHA_RESULTADOS if direcao_1 is None else ds.LINHA_MACRO)
    carga = next(c for c in quadro.pilares[0].cargas if c.caso == "W0")
    horizontal = d.horizontal(carga)
    assert horizontal == pytest.approx((-VENTO[0] * L, -VENTO[1] * L, 0.0), abs=1e-9)
    # No PP, a reação inteira é o peso para cima.
    pp = next(c for c in quadro.pilares[0].cargas if c.caso == "PP")
    assert d.reacao(pp) == pytest.approx((0.0, 0.0, PESO * L), abs=1e-9)


def test_sem_caso_com_carga_no_pilar_fica_no_rotulo_com_o_motivo():
    _, d, r = calcular(dados((1.0, 0.0, 0.0), casos=("PP", "SC")), corpo((1.0, 0.0, 0.0)))
    assert not d.sabida and d.linha == ds.LINHA_MACRO and "sem caso com carga" in d.sentido
    assert r.sabidas == 0 and "V₁ e V₂ ficam no rótulo" in r.avisos[0]


def test_carga_do_plano_diferente_da_do_simulation_nao_vale():
    _, d, _ = calcular(dados((1.0, 0.0, 0.0)), corpo(), aplicada=tuple(3 * v for v in VENTO))
    assert not d.sabida and "não bate com o plano" in d.sentido


def test_linha_da_secao_e_resultados_que_nao_concordam():
    # A macro diz a direção 1 em Y; os resultados dizem X.
    _, d, _ = calcular(dados((1.0, 0.0, 0.0)), corpo((0.0, 1.0, 0.0)))
    assert not d.sabida and "diferem 90,0°" in d.sentido and d.diferenca_graus == pytest.approx(90)


def test_empate_na_macro_usa_os_resultados():
    _, d, _ = calcular(dados((0.0, 1.0, 0.0)), corpo((1.0, 0.0, 0.0), folga=0.2))
    assert d.sabida and d.linha == ds.LINHA_RESULTADOS and d.d1 == pytest.approx((0, 1, 0))


def test_cantoneira_de_abas_iguais_e_empate_mesmo_com_folga_na_macro():
    # No modelo real (macro v6), cantoneiras L 2½" aparadas saíram com folga de 2,6 a 4,9 mm só
    # porque o eixo da barra fica levemente torto: o perfil é simétrico e o Simulation escolhe.
    cantoneira = c3.Secao(c3.FORMA_L, 0.0635, 0.0635, 0.00635, 0.00635)
    assert ds.empate_pelo_perfil(cantoneira)
    assert ds.empate_pelo_perfil(c3.Secao(c3.FORMA_TUBO_CIRCULAR, 0.1, 0.1))
    assert ds.empate_pelo_perfil(c3.Secao(c3.FORMA_TUBO_RETANGULAR, 0.1, 0.1))
    assert not ds.empate_pelo_perfil(c3.Secao(c3.FORMA_TUBO_RETANGULAR, 0.15, 0.1))
    assert not ds.empate_pelo_perfil(c3.Secao(c3.FORMA_I, 0.21, 0.134, 0.0064, 0.0102))
    assert not ds.empate_pelo_perfil(None)
    _, d, _ = calcular(dados((0.0, 1.0, 0.0)), corpo((1.0, 0.0, 0.0), folga=4.9), secao=cantoneira)
    assert d.sabida and d.linha == ds.LINHA_RESULTADOS and d.d1 == pytest.approx((0, 1, 0))


def test_ordem_dos_elementos_contra_o_peso_proprio():
    d = dados((1.0, 0.0, 0.0))
    # A base escolhida à mão no topo: o PP aponta para cima ao longo do "axial".
    d = em.EsforcosDoModelo(
        casos=d.casos,
        membros={VIGA: em.ConfiguracaoDoMembro(tipo="Pilar", base=em.BASE_FIM)},
        eixo_vertical="Z",
    )
    _, pilar, _ = calcular(d, corpo((1.0, 0.0, 0.0)))
    assert not pilar.sabida and "não confere com o peso próprio" in pilar.sentido


def test_linha_pelo_perfil_da_v5():
    # U/I com a alma reta bem mais alta que a mesa: a direção 1 é a alma (a direção A da v5).
    secao = c3.Secao(c3.FORMA_I, 0.313, 0.102, 0.0066, 0.0108)
    alma = (math.cos(0.4), math.sin(0.4), 0.0)
    _, d, _ = calcular(dados(alma), corpo(direcao_secao=alma), secao=secao)
    assert (
        d.sabida and d.linha == ds.LINHA_PERFIL and d.diferenca_graus == pytest.approx(0, abs=1e-6)
    )
    # H quase quadrado: a v5 não diz qual é a alma — fica para os resultados.
    quadrado = c3.Secao(c3.FORMA_I, 0.203, 0.203, 0.0072, 0.011)
    _, d, _ = calcular(dados(alma), corpo(direcao_secao=alma), secao=quadrado)
    assert d.sabida and d.linha == ds.LINHA_RESULTADOS


def test_conferencia_com_o_arquivo_de_reacoes():
    quadro, _, r = calcular(dados((1.0, 0.0, 0.0)), corpo((1.0, 0.0, 0.0)))
    fecha = ds.conferir_horizontais(r, quadro, "W0", (-VENTO[0] * L, -VENTO[1] * L, PESO * L))
    assert fecha.startswith("As reações horizontais dos pilares") and "fecham" in fecha
    nao = ds.conferir_horizontais(r, quadro, "W0", (-5.0, 0.0, 0.0))
    assert "confira" in nao
    assert ds.conferir_horizontais(r, quadro, "W0", None) == ""


# ------------------------------------------------------------------ na cena 3D
def test_cena_desenha_a_seta_horizontal_na_base():
    d1 = (math.cos(0.7), math.sin(0.7), 0.0)
    d = dados(d1)
    g = ld.GeometriaDoModelo(corpos=(corpo(d1),))
    nomes = cm.Nomes({"Pilar[1]": VIGA})
    plano = pc.com_acao(
        pc.PlanoDeCargas(),
        pc.nova_acao(
            "W0",
            cargas=[
                pc.CargaDoModelo(VIGA, VENTO[0], "kN/m", "+X", comprimento_m=L),
                pc.CargaDoModelo(VIGA, VENTO[1], "kN/m", "+Y", comprimento_m=L),
            ],
        ),
    )
    apoios = cm.apoios_e_reacoes(g, "Z", d, nomes, "W0", plano=plano)
    horizontais = [s for s in apoios.reacoes if abs(s.vetor[2]) < 1e-9]
    (seta,) = horizontais
    assert seta.vetor == pytest.approx((-VENTO[0] * L, -VENTO[1] * L, 0.0))
    assert seta.rotulo == f"H {math.hypot(*VENTO[:2]) * L:.1f} kN".replace(".", ",")
    assert apoios.horizontais == 1
    assert apoios.soma_horizontal_kN == pytest.approx((-VENTO[0] * L, -VENTO[1] * L))
    # Sem o plano (sem saber a carga do pilar): nenhuma seta horizontal, e o aviso diz por quê.
    sem = cm.apoios_e_reacoes(g, "Z", d, nomes, "W0")
    assert not [s for s in sem.reacoes if abs(s.vetor[2]) < 1e-9] and sem.horizontais == 0
    assert any("V₁ e V₂ ficam no rótulo" in a for a in sem.avisos)


# ------------------------------------------------------------------ a fundação nos eixos do modelo
@pytest.mark.parametrize("para_cima", [True, False], ids=["fim1-na-base", "fim2-na-base"])
def test_forca_e_momento_na_fundacao_nos_eixos_do_modelo(para_cima):
    a = math.radians(30.0)
    d1 = (math.cos(a), math.sin(a), 0.0)
    quadro, d, r = calcular(dados(d1, para_cima), corpo(d1))
    assert ds.eixos_horizontais("Z") == ("X", "Y") and ds.eixos_horizontais("Y") == ("X", "Z")
    no_modelo = ds.na_fundacao_no_modelo(r, quadro, "Z")
    qx, qy = VENTO[0], VENTO[1]
    # Balanço com q uniforme: a fundação recebe q·L e o momento (L²/2)·(ẑ × q).
    fx, fy, mx, my = no_modelo[(VIGA, "W0")]
    assert (fx, fy) == pytest.approx((qx * L, qy * L), abs=1e-9)
    assert (mx, my) == pytest.approx((-qy * L**2 / 2, qx * L**2 / 2), abs=1e-9)
    assert no_modelo[(VIGA, "PP")] == pytest.approx((0.0, 0.0, 0.0, 0.0), abs=1e-9)
    # No quadro: quatro colunas a mais, e o registro com a tabela nos eixos do modelo.
    linhas = qf.linhas_do_quadro(quadro, pc.PlanoDeCargas(), no_modelo)
    colunas = qf.colunas(no_modelo, ("X", "Y"))
    assert colunas[-4:] == ("FX (kN)", "FY (kN)", "MX (kN·m)", "MY (kN·m)")
    assert all(len(linha) == len(colunas) for linha in linhas)
    assert b"FX (kN)" in qf.csv_do_quadro(quadro, pc.PlanoDeCargas(), no_modelo, ("X", "Y"))
    registro = qf.registro_do_quadro(quadro, pc.PlanoDeCargas(), no_modelo=no_modelo,
                                     eixos=("X", "Y"))  # fmt: skip
    legendas = [t["legenda"] for t in registro["resultados"]["tabelas_memorial"]]
    assert any("eixos do modelo" in x for x in legendas)
    assert qf.xlsx_do_quadro(quadro, pc.PlanoDeCargas(), no_modelo=no_modelo)[:2] == b"PK"


def test_pilar_sem_direcao_fica_vazio_no_quadro():
    quadro, _, r = calcular(dados((1.0, 0.0, 0.0), casos=("PP", "SC")), corpo((1.0, 0.0, 0.0)))
    assert ds.na_fundacao_no_modelo(r, quadro, "Z") == {}
    assert qf.colunas({}, ("X", "Y")) == qf.COLUNAS  # sem nada nos eixos do modelo, sem colunas
