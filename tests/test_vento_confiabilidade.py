"""Confiabilidade do vento (NBR 6123:2023): contas que se conferem por dois caminhos, regras da norma
que o programa já errou e os desenhos que mostram exatamente o que foi calculado.

* classe A, B ou C pela superfície frontal **de cada direção** (5.3.2) — na estrutura aberta e no
  barra a barra a maior dimensão da planta valia para as duas e subestimava o q da direção estreita;
* arrasto global com a **área de sombra** de verdade (empena e telhado inteiros, 4.3.3);
* força do contraventamento = a maior das duas contas (C_a ou zonas) + atrito (6.1.5);
* V₀ fora do mapa de isopletas (30 a 50 m/s) vira alerta;
* as zonas desenhadas em 3D têm a mesma área das zonas do cálculo;
* o pórtico resolvido por dois núcleos diferentes dá as mesmas reações;
* os dois métodos da estrutura aberta (grade de pórticos e barra a barra) concordam.
"""

from __future__ import annotations

import math
from collections import defaultdict

import pytest

from core import cena_3d as c3
from core import portico_figuras as pf
from core import portico_plano as pp
from core import vento_edificio as ve
from core import vento_edificio_desenho as vd
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb
from core import vento_por_barras as vpb
from core import vento_portico as vp
from core import vento_registro as vr
from core.record_charts import imagens_do_registro

GEOMETRIAS = [
    (ve.COBERTURA_PLANA, 40.0, 20.0, 10.0, 0.0),
    (ve.COBERTURA_DUAS_AGUAS, 48.0, 20.0, 8.0, 10.0),
    (ve.COBERTURA_DUAS_AGUAS, 20.0, 20.0, 4.0, 25.0),
    (ve.COBERTURA_DUAS_AGUAS, 60.0, 12.0, 15.0, 45.0),
    (ve.COBERTURA_UMA_AGUA, 30.0, 12.0, 6.0, 10.0),
    (ve.COBERTURA_UMA_AGUA, 30.0, 29.0, 3.0, 20.0),
]


def edificio(
    cobertura: str, a: float, b: float, h: float, theta: float, **mais
) -> ve.EntradaEdificio:
    return ve.EntradaEdificio(
        v0_m_s=35.0, comprimento_a_m=a, largura_b_m=b, altura_h_m=h, cobertura=cobertura,
        theta_graus=theta, categoria="III", **mais,
    )  # fmt: skip


# ------------------------------------------------------------------ classe por direção (5.3.2)
def test_estrutura_aberta_tem_a_classe_da_superficie_frontal_de_cada_direcao():
    """Plataforma de 30 × 6 m e 6 m de altura: o vento em X vê 6 m de largura (classe A); o em Y vê
    30 m (classe B). Com uma classe só (a de 30 m), o q em X saía uns 5 % menor."""
    g = va.GeometriaAberta(comprimento_x_m=30.0, largura_y_m=6.0, cotas_m=(3.0, 6.0), vaos_x=5,
                           guarda_corpo=False)  # fmt: skip
    p = va.ParametrosVento(v0_m_s=35.0, categoria="II")
    r = va.calcular_vento_aberto(g, p)
    assert (r.x.classe, r.y.classe) == ("A", "B")
    for direcao, classe in (("X", "A"), ("Y", "B")):
        nivel = r.direcao(direcao).niveis[-1]
        q = vb.calcular_vento_no_local(35.0, categoria="II", classe=classe,
                                       altura_m=nivel.faixa_m[1]).q_N_m2  # fmt: skip
        assert nivel.q_N_m2 == pytest.approx(q)
    q_a = vb.calcular_vento_no_local(35.0, categoria="II", classe="A", altura_m=6.0).q_N_m2
    q_b = vb.calcular_vento_no_local(35.0, categoria="II", classe="B", altura_m=6.0).q_N_m2
    assert q_b < 0.96 * q_a  # o erro que havia
    assert r.vento_no_topo.classe == "A"  # a mais severa


def test_barra_a_barra_tem_a_classe_de_cada_direcao_e_a_largura_frontal():
    pilares = [
        vpb.BarraAoVento(f"P{i}{j}", (x, y, 0.0), (x, y, 6.0), 0.25, 0.25)
        for i, x in enumerate((0.0, 15.0, 30.0))
        for j, y in enumerate((0.0, 4.0))
    ]
    r = vpb.calcular(
        vpb.EntradaPorBarras(barras=tuple(pilares), direcoes=vpb.DIRECOES_COM_DIAGONAIS)
    )
    assert r.direcao(0).largura_frontal_m == pytest.approx(4.0)
    assert r.direcao(90).largura_frontal_m == pytest.approx(30.0)
    assert r.direcao(45).largura_frontal_m == pytest.approx((30.0 + 4.0) / math.sqrt(2))
    assert r.direcao(0).classe == r.direcao(180).classe == "A"
    assert r.direcao(90).classe == r.direcao(45).classe == "B"
    assert r.classe == "A"
    # O pilar da frente ao vento em X carrega com o q da classe A.
    forca = r.direcao(0).da_barra("P00")
    q = vb.calcular_vento_no_local(35.0, categoria="III", classe="A", altura_m=6.0).q_N_m2
    assert forca.q_N_m2 == pytest.approx(q)


# ------------------------------------------------------------------ arrasto e contraventamento
@pytest.mark.parametrize(("cobertura", "a", "b", "h", "theta"), GEOMETRIAS)
def test_area_de_sombra_do_arrasto_e_a_projecao_da_edificacao_inteira(cobertura, a, b, h, theta):
    r = ve.calcular_edificacao(edificio(cobertura, a, b, h, theta))
    tan = math.tan(math.radians(theta))
    if cobertura == ve.COBERTURA_DUAS_AGUAS:
        empena, topo = b * h + b * b * tan / 4.0, h + b * tan / 2.0
    elif cobertura == ve.COBERTURA_UMA_AGUA:
        empena, topo = b * (h + b * tan / 2.0), h + b * tan
    else:
        empena, topo = b * h, h
    assert r.arrasto[0].area_frontal_m2 == pytest.approx(empena)
    assert r.arrasto[90].area_frontal_m2 == pytest.approx(a * topo)
    for alpha in (0, 90):
        arrasto = r.arrasto[alpha]
        q = r.vento_por_alpha[alpha].q_kN_m2
        assert arrasto.forca_kN == pytest.approx(q * arrasto.ca.valor * arrasto.area_frontal_m2)


def test_contraventamento_leva_a_maior_conta_mais_o_atrito():
    # Galpão comprido (a/h > 4): há atrito a 0°.
    r = ve.calcular_edificacao(edificio(ve.COBERTURA_DUAS_AGUAS, 80.0, 16.0, 6.0, 10.0))
    a0 = r.arrasto[0]
    assert a0.atrito.aplica and a0.atrito.total_kN > 0
    assert a0.forca_horizontal_kN == max(a0.forca_kN, a0.soma_das_zonas_kN)
    assert a0.forca_para_contraventamento_kN == pytest.approx(
        a0.forca_horizontal_kN + a0.atrito.total_kN
    )
    assert a0.torsor_kNm == pytest.approx(a0.forca_horizontal_kN * a0.excentricidade_m)
    linha = next(
        v
        for v in r.verificacoes
        if v.nome == "Força horizontal para o contraventamento, vento a 0°"
    )
    assert linha.resistente == pytest.approx(a0.forca_para_contraventamento_kN)
    assert "atrito" in linha.formula
    registro = vr.registro_edificacao(r)
    assert registro["resultados"]["arrasto_global"]["0"][
        "forca_para_contraventamento_kN"
    ] == pytest.approx(round(a0.forca_para_contraventamento_kN, 4))


# ------------------------------------------------------------------ V₀ do mapa
@pytest.mark.parametrize(("v0", "alerta"), [(25.0, True), (30.0, False), (42.5, False), (50.0, False),
                                            (55.0, True), (120.0, True)])  # fmt: skip
def test_v0_fora_do_mapa_de_isopletas_vira_alerta(v0, alerta):
    assert (vb.aviso_do_v0(v0) is not None) == alerta
    r = ve.calcular_edificacao(
        ve.EntradaEdificio(v0_m_s=v0, comprimento_a_m=40.0, largura_b_m=20.0, altura_h_m=6.0)
    )
    linha = next(v for v in r.verificacoes if v.nome.startswith("V₀ dentro do mapa"))
    assert linha.status == ("ALERTA" if alerta else "OK")
    aberta = va.calcular_vento_aberto(va.GeometriaAberta(), va.ParametrosVento(v0_m_s=v0))
    assert any("mapa de isopletas" in a for a in aberta.avisos) == alerta
    if alerta:
        assert "km/h" in linha.formula


# ------------------------------------------------------------------ desenho = cálculo
@pytest.mark.parametrize(("cobertura", "a", "b", "h", "theta"), GEOMETRIAS)
def test_zonas_desenhadas_tem_a_area_das_zonas_do_calculo(cobertura, a, b, h, theta):
    r = ve.calcular_edificacao(edificio(cobertura, a, b, h, theta))
    for alpha in r.alphas:
        areas: dict[str, float] = defaultdict(float)
        for face in vd.faces_das_zonas(r.geometria, alpha):
            areas[face.zona] += face.area_m2
            # A normal gravada é a da face (Newell) e aponta para fora da edificação.
            centro = face.centro
            dentro = (r.geometria.a_m / 2, r.geometria.b_m / 2, r.geometria.h_m / 2)
            para_fora = tuple(c - d for c, d in zip(centro, dentro, strict=True))
            assert sum(n * f for n, f in zip(face.normal, para_fora, strict=True)) > 0
        zonas = {p.zona.id: p.zona for p in r.casos_do_angulo(alpha)[0].pressoes}
        assert set(areas) == set(zonas)
        for id_, zona in zonas.items():
            assert areas[id_] == pytest.approx(zona.area_m2, rel=1e-12), (alpha, id_)


def test_vista_3d_mostra_so_as_faces_de_frente_com_rotulo_e_seta():
    r = ve.calcular_edificacao(edificio(ve.COBERTURA_DUAS_AGUAS, 48.0, 20.0, 8.0, 10.0))
    for caso in (r.casos_do_angulo(0)[0], r.casos_do_angulo(90)[0]):
        cena = vd.cena_das_zonas(r, caso)
        assert cena.paineis and all(not p.sombra for p in cena.paineis)
        # Do lado de barlavento: a parede que recebe o vento aparece (C a 0°, A a 90°).
        assert any(p.nome.startswith(("C:", "A:")) for p in cena.paineis)
        assert not any(p.nome.startswith(("D:", "B:")) for p in cena.paineis)
        assert len(cena.setas) == 1 and cena.setas[0].larga
        assert all("C_e" in t.texto and "kN/m²" in t.texto for t in cena.textos)
        desenho = c3.projetar(cena, azimute=vd.vista_do_caso(caso.alpha)[0])
        assert not desenho.vazio and not desenho.eixos  # sem o triedro do SolidWorks
    uma = ve.calcular_edificacao(edificio(ve.COBERTURA_UMA_AGUA, 30.0, 12.0, 6.0, 10.0))
    cena = vd.cena_das_zonas(uma, uma.casos_do_angulo(-90)[0])
    # A −90° o barlavento é a parede de y = b (a parede A), vista do outro lado.
    assert any(p.nome == "A:A" for p in cena.paineis)


def test_cena_gravada_guarda_a_cor_exata_e_le_registros_antigos():
    r = ve.calcular_edificacao(edificio(ve.COBERTURA_DUAS_AGUAS, 48.0, 20.0, 8.0, 10.0))
    cena = vd.cena_das_zonas(r, r.casos_do_angulo(0)[0])
    lida = c3.cena_de_dicionario(c3.cena_para_dicionario(cena))
    assert [p.sombra for p in lida.paineis] == [False] * len(cena.paineis)
    assert lida.eixo_vertical_do_modelo == "" and lida.escala == cena.escala
    antigo = c3.cena_para_dicionario(cena)
    antigo["paineis"] = [p[:5] for p in antigo["paineis"]]  # registro de antes (sem a sombra)
    del antigo["eixo_vertical"]
    velha = c3.cena_de_dicionario(antigo)
    assert all(p.sombra for p in velha.paineis) and velha.eixo_vertical_do_modelo == "Y"


@pytest.mark.parametrize(("cobertura", "a", "b", "h", "theta"), GEOMETRIAS)
def test_faixas_das_vedacoes_ficam_no_telhado_sem_se_sobrepor(cobertura, a, b, h, theta):
    r = ve.calcular_edificacao(edificio(cobertura, a, b, h, theta))
    faixas = vd.faixas_de_vedacao(r)
    ids = {f.id for f in faixas}
    assert ids <= {linha.id for linha in r.vedacoes}
    assert "parede-cpe-medio" in ids
    retangulos = [ret for f in faixas for ret in f.retangulos]
    for x0, x1, y0, y1 in retangulos:
        assert -1e-9 <= x0 < x1 <= a + 1e-9 and -1e-9 <= y0 < y1 <= b + 1e-9
    for i, (ax0, ax1, ay0, ay1) in enumerate(retangulos):
        for bx0, bx1, by0, by1 in retangulos[i + 1 :]:
            sobra = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(
                0.0, min(ay1, by1) - max(ay0, by0)
            )
            assert sobra < 1e-9
    g = r.geometria
    paredes = next(f for f in faixas if f.id == "parede-cpe-medio")
    assert len(paredes.trechos_de_parede) == 8  # dois cantos em cada uma das 4 paredes
    assert all(
        s1 - s0 <= g.faixa_cpe_medio_parede_m + 1e-9 for _, s0, s1 in paredes.trechos_de_parede
    )
    if cobertura == ve.COBERTURA_DUAS_AGUAS and theta == 10.0:
        empena = next(f for f in faixas if f.id == "telhado-empena")
        y = g.y_telhado_m
        assert sum((x1 - x0) * (y1 - y0) for x0, x1, y0, y1 in empena.retangulos) == pytest.approx(
            2 * y * b
        )
        cumeeira = next(f for f in faixas if f.id == "telhado-cumeeira")
        assert cumeeira.retangulos == ((y, a - y, b / 2 - y, b / 2 + y),)
    for f in faixas:
        linha = next(v for v in r.vedacoes if v.id == f.id)
        assert f.pior_kN_m2 == linha.mais_desfavoravel_kN_m2


# ------------------------------------------------------------------ pórtico por dois núcleos
@pytest.mark.parametrize(("cobertura", "a", "b", "h", "theta"), GEOMETRIAS)
@pytest.mark.parametrize("engastadas", [True, False])
def test_portico_resolvido_pelos_dois_nucleos_da_as_mesmas_reacoes(
    cobertura, a, b, h, theta, engastadas
):
    r = ve.calcular_edificacao(edificio(cobertura, a, b, h, theta))
    geometria = vp.geometria_do_portico(r.geometria)
    pilar, rafter = vp.SecaoDoElemento(60e2, 8000e4), vp.SecaoDoElemento(45e2, 6000e4)
    for caso in vp.casos_do_portico(r)[:6]:
        rapido = vp.resolver_portico(geometria, caso, pilar=pilar, rafter=rafter,
                                     bases_engastadas=engastadas)  # fmt: skip
        modelo = vd.modelo_do_portico(
            geometria, caso, pilar=vd.secao_do_portico("Pilar", pilar),
            rafter=vd.secao_do_portico("Viga", rafter), bases_engastadas=engastadas,
        )  # fmt: skip
        plano = pp.resolver(modelo)
        assert plano.residuo_kN < 1e-6
        for reacao in rapido.reacoes:
            outra = plano.reacao(str(reacao["no"]))
            assert outra.rx == pytest.approx(reacao["Rh (kN)"], abs=1e-6)
            assert outra.ry == pytest.approx(reacao["Rv (kN)"], abs=1e-6)
            assert outra.mz == pytest.approx(reacao["M (kN·m)"], abs=1e-6)
        # Equilíbrio: as reações horizontais equilibram a soma das cargas.
        assert sum(x.rx for x in plano.reacoes) == pytest.approx(
            -rapido.soma_cargas_horizontais_kN, abs=1e-6
        )


def test_figuras_do_portico_escolhidas_e_no_memorial():
    r = ve.calcular_edificacao(edificio(ve.COBERTURA_DUAS_AGUAS, 48.0, 20.0, 8.0, 10.0))
    geometria = vp.geometria_do_portico(r.geometria)
    casos = vp.casos_do_portico(r)
    caso = vd.pior_caso_do_portico(casos)
    secao = vp.SecaoDoElemento(60e2, 8000e4)
    modelo = vd.modelo_do_portico(geometria, caso, pilar=vd.secao_do_portico("P", secao),
                                  rafter=vd.secao_do_portico("V", secao))  # fmt: skip
    resolvido = pp.resolver(modelo)
    todas = pf.figuras_do_portico(resolvido, tensao=False)
    tres = pf.figuras_do_portico(resolvido, tensao=False, apenas=["deformada", "estrutura", "M"])
    assert len(todas) == 6 and len(tres) == 3
    assert [f.titulo for f in tres] == [todas[0].titulo, todas[4].titulo, todas[5].titulo]
    solucao = vp.resolver_portico(geometria, caso, pilar=secao, rafter=secao)
    registro = vr.registro_edificacao(r, casos_do_portico=casos, solucao=solucao,
                                      modelo_do_portico=modelo)  # fmt: skip
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == ""
    titulos = [i["titulo"] for i in imagens]
    assert sum("Zonas do vento" in t for t in titulos) == 2  # 0° e 90°
    assert sum("Pórtico transversal" in t for t in titulos) == 3
    assert all(i["png"][:8] == b"\x89PNG\r\n\x1a\n" for i in imagens)


# ------------------------------------------------------------------ os dois métodos da estrutura aberta
def _plataforma_em_barras(
    lx: float, ly: float, cotas: tuple[float, ...], nx: int, ny: int
) -> list[vpb.BarraAoVento]:
    """A mesma plataforma da grade, barra a barra: pilares, vigas e as diagonais em X das linhas
    das pontas (um painel por andar), como a grade supõe."""
    xs = [lx * i / nx for i in range(nx + 1)]
    ys = [ly * j / ny for j in range(ny + 1)]
    barras = [
        vpb.BarraAoVento(f"P{x}_{y}", (x, y, 0.0), (x, y, cotas[-1]), 0.25, 0.25)
        for x in xs
        for y in ys
    ]
    for z in cotas:
        barras += [vpb.BarraAoVento(f"VX{z}_{y}_{i}", (xs[i], y, z), (xs[i + 1], y, z), 0.30, 0.15,
                                    (0.0, 0.0, 1.0)) for y in ys for i in range(nx)]  # fmt: skip
        barras += [vpb.BarraAoVento(f"VY{z}_{x}_{j}", (x, ys[j], z), (x, ys[j + 1], z), 0.30, 0.15,
                                    (0.0, 0.0, 1.0)) for x in xs for j in range(ny)]  # fmt: skip
    baixo = 0.0
    for z in cotas:
        for x in (xs[0], xs[-1]):
            barras.append(
                vpb.BarraAoVento(f"DY{z}_{x}a", (x, ys[0], baixo), (x, ys[1], z), 0.076, 0.076)
            )
            barras.append(
                vpb.BarraAoVento(f"DY{z}_{x}b", (x, ys[0], z), (x, ys[1], baixo), 0.076, 0.076)
            )
        for y in (ys[0], ys[-1]):
            barras.append(
                vpb.BarraAoVento(f"DX{z}_{y}a", (xs[0], y, baixo), (xs[1], y, z), 0.076, 0.076)
            )
            barras.append(
                vpb.BarraAoVento(f"DX{z}_{y}b", (xs[0], y, z), (xs[1], y, baixo), 0.076, 0.076)
            )
        baixo = z
    return barras


def test_grade_e_barra_a_barra_concordam_na_mesma_plataforma():
    """Mesmos φ, C_a e η nos reticulados; o barra a barra fica um pouco acima porque conta, com
    C_a = 2,0, as diagonais das faces paralelas ao vento (a grade as zera, 8.5) e usa o q do topo
    de cada barra (a grade, o do topo de cada faixa): a favor da segurança e perto da grade."""
    g = va.GeometriaAberta(comprimento_x_m=12.0, largura_y_m=6.0, cotas_m=(3.0, 6.0), vaos_x=2,
                           vaos_y=1, largura_diagonal_x_m=0.076, largura_diagonal_y_m=0.076,
                           guarda_corpo=False)  # fmt: skip
    p = va.ParametrosVento(v0_m_s=35.0, categoria="II")
    grade = va.calcular_vento_aberto(g, p)
    barras = vpb.calcular(
        vpb.EntradaPorBarras(
            barras=tuple(_plataforma_em_barras(12.0, 6.0, (3.0, 6.0), 2, 1)), parametros=p
        )  # fmt: skip
    )
    for direcao, angulo in (("X", 0), ("Y", 90)):
        d_grade, d_barras = grade.direcao(direcao), barras.direcao(angulo)
        assert len(d_grade.planos) == len(d_barras.planos)
        for pg, pb in zip(d_grade.planos, d_barras.planos, strict=True):
            assert pb.ca == pytest.approx(pg.ca, abs=0.04)
            assert pb.eta == pytest.approx(pg.eta, abs=0.04)
        razao = d_barras.total_kN / d_grade.total_kN
        assert 1.0 <= razao <= 1.18, (direcao, razao)
        # Tirando as diagonais das faces paralelas ao vento, sobra só a diferença do q (< 5 %).
        paralelas = sum(
            f.forca_kN for f in d_barras.barras if f.plano == "—" and f.barra.startswith("D")
        )
        assert 1.0 <= (d_barras.total_kN - paralelas) / d_grade.total_kN <= 1.05


# ------------------------------------------------------------------ varredura de geometrias
def test_varredura_de_edificacoes_fechadas_nao_quebra_e_fecha_as_contas():
    """200 edificações sorteadas (semente fixa): números finitos, simetria das resultantes, zonas
    desenhadas com a área do cálculo e os três desenhos válidos."""
    import random
    import re
    import xml.etree.ElementTree as ET

    from components.cena_3d_svg import svg_da_cena
    from components.wind_figures import svg_planta, svg_vedacoes

    sorteio = random.Random(6123)
    for _ in range(200):
        cobertura = sorteio.choice(list(ve.COBERTURAS))
        a = sorteio.uniform(5.0, 120.0)
        b = sorteio.uniform(4.0, a)
        h = sorteio.uniform(2.5, min(40.0, 5.5 * b))
        theta = {
            ve.COBERTURA_PLANA: 0.0,
            ve.COBERTURA_DUAS_AGUAS: sorteio.uniform(1.0, 45.0),
            ve.COBERTURA_UMA_AGUA: sorteio.uniform(5.0, 30.0),
        }[cobertura]
        entrada = ve.EntradaEdificio(
            v0_m_s=sorteio.choice((30.0, 35.0, 40.0, 45.0, 50.0)), comprimento_a_m=a,
            largura_b_m=b, altura_h_m=h, cobertura=cobertura, theta_graus=theta,
            categoria=sorteio.choice(("I", "II", "III", "IV", "V")),
            cenario_permeabilidade=sorteio.choice(("quatro_faces", "duas_faces_longas", "estanque")),
        )  # fmt: skip
        r = ve.calcular_edificacao(entrada)
        rotulo = (cobertura, round(a, 2), round(b, 2), round(h, 2), round(theta, 1))
        for caso in r.casos:
            assert all(math.isfinite(v) for v in (caso.fx_kN, caso.fy_kN, caso.fz_telhado_kN))
            if cobertura == ve.COBERTURA_UMA_AGUA:
                # Paredes longas de alturas diferentes e telhado inclinado: a 0° há força de lado.
                continue
            if caso.alpha == 0:  # simétrica: o vento ao longo de a não empurra de lado
                assert abs(caso.fy_kN) < 1e-6 * max(1.0, abs(caso.fx_kN)), rotulo
            else:  # a 90° as empenas se anulam
                assert abs(caso.fx_kN) < 1e-6 * max(1.0, abs(caso.fy_kN)), rotulo
        for alpha in r.alphas:
            areas: dict[str, float] = defaultdict(float)
            for face in vd.faces_das_zonas(r.geometria, alpha):
                areas[face.zona] += face.area_m2
            for p in r.casos_do_angulo(alpha)[0].pressoes:
                assert areas[p.zona.id] == pytest.approx(p.zona.area_m2, rel=1e-9), rotulo
        for arrasto in r.arrasto.values():
            assert arrasto.forca_para_contraventamento_kN >= arrasto.forca_kN > 0, rotulo
        caso = r.casos[-1]
        ET.fromstring(svg_planta(r, caso.alpha, caso))
        ET.fromstring(svg_vedacoes(r))
        desenho = c3.projetar(vd.cena_das_zonas(r, caso), azimute=vd.vista_do_caso(caso.alpha)[0])
        svg = svg_da_cena(desenho)
        ET.fromstring(svg)
        assert not re.search(r"(?<![a-z])(nan|inf)(?![a-z])", svg.lower()), rotulo


def test_varredura_de_estruturas_abertas_tem_classe_por_direcao_e_forcas_finitas():
    import random

    sorteio = random.Random(8)
    for _ in range(120):
        nx, ny = sorteio.randint(1, 6), sorteio.randint(1, 4)
        cotas = tuple(
            round(3.0 * k + sorteio.uniform(0, 1.5), 2) for k in range(1, sorteio.randint(1, 5) + 1)
        )
        g = va.GeometriaAberta(
            comprimento_x_m=sorteio.uniform(3.0, 70.0), largura_y_m=sorteio.uniform(2.0, 40.0),
            cotas_m=cotas, vaos_x=nx, vaos_y=ny, linhas_contraventadas_x=sorteio.randint(1, ny + 1),
            linhas_contraventadas_y=sorteio.randint(1, nx + 1),
            guarda_corpo=sorteio.random() < 0.7,
        )  # fmt: skip
        r = va.calcular_vento_aberto(g, va.ParametrosVento(v0_m_s=40.0, categoria="III"))
        for direcao in ("X", "Y"):
            d = r.direcao(direcao)
            assert d.classe == va.classe_da_direcao(g, direcao)
            assert math.isfinite(d.total_kN) and d.total_kN > 0
            assert all(0.0 < p.eta <= 1.0 and 1.6 - 1e-9 <= p.ca <= 2.0 for p in d.planos)
        # q no topo pela classe mais severa: nunca menor que o de cada direção no topo.
        for direcao in ("X", "Y"):
            q = vb.calcular_vento_no_local(
                40.0, categoria="III", classe=r.direcao(direcao).classe, altura_m=g.altura_total_m
            ).q_N_m2
            assert r.vento_no_topo.q_N_m2 >= q - 1e-9
