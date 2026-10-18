"""Núcleo da cena 3D: câmera, enquadramento, seções, faces, setas, apoios, rótulos, os dois
desenhos (SVG e PNG) e robustez (cena vazia, coordenada inválida, modelo enorme, fuzz)."""

from __future__ import annotations

import io
import math
import random
import time
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from components.cena_3d_svg import svg_da_cena
from core import cena_3d as c3
from core import cena_3d_png


def _todos_os_pontos(desenho: c3.Desenho2D) -> list[tuple[float, float]]:
    pontos: list[tuple[float, float]] = []
    for item in desenho.itens:
        if isinstance(item, c3.Poligono2D):
            pontos.extend(item.pontos)
        elif isinstance(item, (c3.Linha2D, c3.Seta2D)):
            pontos.extend((item.a, item.b))
        elif isinstance(item, c3.Etiqueta2D):
            pontos.append((item.x, item.y))
    return pontos


def coluna(nome="P1", x=0.0, y=0.0, h=4.0, forma=c3.FORMA_I) -> c3.BarraCena:
    return c3.BarraCena(nome, (x, y, 0.0), (x, y, h), c3.Secao(forma, 0.2, 0.15, 0.006, 0.01),
                        (1.0, 0.0, 0.0))  # fmt: skip


def viga(nome="V1", a=(0.0, 0.0, 4.0), b=(6.0, 0.0, 4.0)) -> c3.BarraCena:
    return c3.BarraCena(nome, a, b, c3.Secao(c3.FORMA_U, 0.2, 0.06, 0.006, 0.01),
                        (0.0, 0.0, 1.0))  # fmt: skip


# ------------------------------------------------------------------ câmera e enquadramento
def test_vista_frontal_e_superior_projetam_como_esperado():
    frontal = c3.Camera(*c3.VISTAS[c3.VISTA_FRONTAL])
    assert frontal.tela((1.0, 0.0, 0.0))[0] == pytest.approx(1.0, abs=1e-6)  # X para a direita
    assert frontal.tela((0.0, 0.0, 1.0))[1] < -0.99  # Z para cima (y da tela para baixo)
    superior = c3.Camera(*c3.VISTAS[c3.VISTA_SUPERIOR])
    assert superior.tela((1.0, 0.0, 0.0))[0] == pytest.approx(1.0, abs=1e-6)
    assert superior.tela((0.0, 1.0, 0.0))[1] < -0.99  # Y da planta para cima na tela
    # profundidade cresce para quem olha
    assert frontal.profundidade((0.0, -1.0, 0.0)) > frontal.profundidade((0.0, 1.0, 0.0))


def test_enquadramento_ignora_ponto_invalido_e_aguenta_vazio():
    e = c3.Enquadramento([(float("nan"), 0.0), (0.0, 0.0), (10.0, 5.0)], (0, 0, 100, 100))
    assert math.isfinite(e.escala) and e.escala == pytest.approx(10.0)
    vazio = c3.Enquadramento([], (0, 0, 100, 100))
    assert math.isfinite(vazio.escala) and vazio.escala > 0
    um = c3.Enquadramento([(3.0, 3.0)], (0, 0, 100, 100))
    assert um((3.0, 3.0)) == pytest.approx((50.0, 50.0))


# ------------------------------------------------------------------ seções e faces
@pytest.mark.parametrize("forma", c3.FORMAS)
def test_contorno_de_cada_secao_tem_area_e_cabe_na_caixa(forma):
    s = c3.Secao(forma, 0.2, 0.1, 0.008, 0.012)
    contorno = s.contorno()
    area = abs(
        sum(
            p[0] * q[1] - q[0] * p[1]
            for p, q in zip(contorno, [*contorno[1:], contorno[0]], strict=True)
        )
        / 2
    )
    assert area > 0
    assert all(abs(p[0]) <= 0.2 and abs(p[1]) <= 0.2 for p in contorno)
    if forma == c3.FORMA_I:
        assert area == pytest.approx(2 * 0.1 * 0.012 + (0.2 - 2 * 0.012) * 0.008)


@pytest.mark.parametrize("forma", c3.FORMAS)
def test_faces_da_barra_saem_para_fora(forma):
    b = c3.BarraCena("B", (0.0, 0.0, 0.0), (3.0, 1.0, 2.0), c3.Secao(forma, 0.2, 0.1, 0.01, 0.01))
    faces = c3._faces_da_barra(b, pedaco_maximo=10.0)
    eixo = c3._unitario(c3._sub(b.fim, b.inicio))
    assert eixo is not None
    for face, tampa in faces:
        normal = c3.normal_da_face(face)
        assert normal is not None
        centro = tuple(sum(p[k] for p in face) / len(face) for k in range(3))
        if tampa:
            meio = c3._escala(c3._soma(b.inicio, b.fim), 0.5)
            assert c3._dot(normal, c3._sub(centro, meio)) > 0
        elif forma not in (c3.FORMA_U, c3.FORMA_L, c3.FORMA_T, c3.FORMA_I):
            # seção convexa: a normal da face lateral aponta para fora do eixo
            t = c3._dot(c3._sub(centro, b.inicio), eixo)
            perto = c3._soma(b.inicio, c3._escala(eixo, t))
            assert c3._dot(normal, c3._sub(centro, perto)) > 0


def test_barra_comprida_vira_pedacos_e_o_sombreado_muda_com_a_face():
    b = c3.BarraCena("B", (0, 0, 0), (12, 0, 0), c3.Secao(c3.FORMA_CHEIA, 0.2, 0.2))
    assert len(c3._faces_da_barra(b, 2.0)) == 6 * 4 + 2
    desenho = c3.projetar(c3.Cena(barras=(b,)))
    cores = {i.preenchimento for i in desenho.itens if isinstance(i, c3.Poligono2D)}
    assert len(cores) >= 3  # chão + pelo menos duas faces com luz diferente


# ------------------------------------------------------------------ setas, apoios e rótulos
def test_seta_de_carga_chega_no_ponto_e_reacao_sai_dele():
    ponto = (0.0, 0.0, 4.0)
    cena = c3.Cena(
        barras=(coluna(),),
        setas=(
            c3.SetaCena(ponto, (0.0, 0.0, -10.0), "10 kN"),
            c3.SetaCena((0.0, 0.0, 0.0), (0.0, 0.0, 10.0), "N 10 kN", reacao=True),
        ),
        apoios=(c3.ApoioCena((0.0, 0.0, 0.0), c3.APOIO_ARTICULADO),),
    )
    d = c3.projetar(cena, azimute=-90, elevacao=0.5)  # de frente: z para cima na tela
    carga, reacao = [i for i in d.itens if isinstance(i, c3.Seta2D)]
    assert carga.b[1] > carga.a[1]  # a carga desce até o ponto
    assert reacao.b[1] < reacao.a[1]  # a reação sobe do apoio
    textos = [i.texto for i in d.itens if isinstance(i, c3.Etiqueta2D)]
    assert "10 kN" in textos and "N 10 kN" in textos


def test_carga_distribuida_vira_pente():
    cena = c3.Cena(
        barras=(viga(),),
        distribuidas=(c3.CargaDistribuidaCena((0, 0, 4), (6, 0, 4), (0, 0, -2.0), "2 kN/m"),),
    )
    d = c3.projetar(cena)
    assert sum(isinstance(i, c3.Seta2D) for i in d.itens) == 5


def test_rotulos_nao_se_cobrem():
    barras = tuple(viga(f"V{k}", (0, k * 0.01, 4), (6, k * 0.01, 4)) for k in range(8))
    barras = tuple(c3.BarraCena(b.nome, b.inicio, b.fim, b.secao, b.alma, rotulo=f"rótulo {b.nome}")
                   for b in barras)  # fmt: skip
    d = c3.projetar(c3.Cena(barras=barras))
    caixas = []
    for e in (i for i in d.itens if isinstance(i, c3.Etiqueta2D)):
        w = c3.largura_do_texto(e.texto, e.tamanho) + 12
        caixas.append(
            (e.x - w / 2, e.y - (e.tamanho + 9) / 2, e.x + w / 2, e.y + (e.tamanho + 9) / 2)
        )
    for i, a in enumerate(caixas):
        for b in caixas[i + 1 :]:
            assert a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3]


def test_destaque_deixa_as_outras_claras():
    cena = c3.Cena(
        barras=(coluna("P1"), c3.BarraCena("P2", (2, 0, 0), (2, 0, 4), c3.Secao(), destaque=True))
    )
    d = c3.projetar(cena)
    destacadas = [i for i in d.itens if isinstance(i, c3.Poligono2D) and i.contorno == "#ff2d55"]
    assert destacadas


# ------------------------------------------------------------------ desenhos
def _cena_exemplo() -> c3.Cena:
    return c3.Cena(
        barras=(coluna("P1"), coluna("P2", x=6.0), viga()),
        paineis=(c3.PainelCena("piso", ((0, 0, 4), (6, 0, 4), (6, 2, 4), (0, 2, 4))),),
        setas=(c3.SetaCena((3.0, 0.0, 4.0), (0.0, 0.0, -5.0), "5 kN"),),
        apoios=(c3.ApoioCena((0, 0, 0), c3.APOIO_ENGASTE), c3.ApoioCena((6, 0, 0))),
        titulo="Exemplo",
        legenda=(("#3f6fb5", "pilar"),),
        escala=c3.EscalaDeCor(0, 1, "kN/m", "carga"),
    )


@pytest.mark.parametrize("vista", list(c3.VISTAS))
def test_svg_e_png_saem_em_todas_as_vistas(vista):
    d = c3.projetar(_cena_exemplo(), azimute=c3.VISTAS[vista][0], elevacao=c3.VISTAS[vista][1])
    raiz = ET.fromstring(svg_da_cena(d))
    assert raiz.tag.endswith("svg")
    texto = " ".join("".join(t.itertext()) for t in raiz.iter("{http://www.w3.org/2000/svg}text"))
    assert "Exemplo" in texto and "5 kN" in texto
    png = cena_3d_png.png_da_cena(d, escala=1.0)
    imagem = Image.open(io.BytesIO(png))
    assert imagem.size == (1100, 720) and imagem.format == "PNG"


def test_eixos_do_solidworks_com_y_para_cima():
    assert dict(c3.eixos_do_modelo("Y"))["Y"] == (0.0, 0.0, 1.0)
    d = c3.projetar(_cena_exemplo())
    assert {n for n, _ in d.eixos} == {"X", "Y", "Z"}


# ------------------------------------------------------------------ robustez
def test_cena_vazia_e_coordenada_invalida():
    vazio = c3.projetar(c3.Cena())
    assert vazio.vazio and "Nada para desenhar" in vazio.itens[0].texto
    ruim = c3.Cena(barras=(c3.BarraCena("X", (0, float("nan"), 0), (1, 1, 1)), coluna()))
    d = c3.projetar(ruim)
    assert any("X" in a for a in d.avisos)
    assert all(math.isfinite(v) for p in _todos_os_pontos(d) for v in p)


def test_modelo_enorme_vira_linhas_e_e_rapido():
    barras = tuple(coluna(f"P{i}", x=(i % 50) * 1.0, y=(i // 50) * 1.0) for i in range(2500))
    inicio = time.perf_counter()
    d = c3.projetar(c3.Cena(barras=barras))
    assert time.perf_counter() - inicio < 8.0
    assert any("Modelo grande" in a for a in d.avisos)
    assert sum(isinstance(i, c3.Linha2D) for i in d.itens) >= 2500


@pytest.mark.parametrize("semente", range(30))
def test_cena_aleatoria_nunca_derruba(semente):
    r = random.Random(semente)

    def ponto():
        p = [r.uniform(-5, 5) for _ in range(3)]
        if r.random() < 0.05:
            p[r.randrange(3)] = r.choice((float("nan"), float("inf")))
        return tuple(p)

    barras = []
    for k in range(r.randint(0, 25)):
        a = ponto()
        b = a if r.random() < 0.05 else ponto()
        secao = r.choice((None, c3.Secao(r.choice(c3.FORMAS), r.uniform(-0.1, 0.4), r.uniform(0, 0.3),
                                         r.uniform(0, 0.02), r.uniform(0, 0.02))))  # fmt: skip
        barras.append(c3.BarraCena(f"B{k}", a, b, secao, r.choice((None, ponto())),
                                   rotulo=r.choice(("", "x"))))  # fmt: skip
    cena = c3.Cena(
        barras=tuple(barras),
        paineis=tuple(
            c3.PainelCena("P", tuple(ponto() for _ in range(r.randint(0, 5)))) for _ in range(3)
        ),
        setas=tuple(c3.SetaCena(ponto(), ponto(), "s", reacao=r.random() < 0.5) for _ in range(4)),
        distribuidas=tuple(
            c3.CargaDistribuidaCena(ponto(), ponto(), ponto(), "q") for _ in range(3)
        ),
        apoios=tuple(c3.ApoioCena(ponto(), r.choice(c3.TIPOS_DE_APOIO)) for _ in range(3)),
    )
    for vista in c3.VISTAS.values():
        d = c3.projetar(cena, azimute=vista[0] + r.uniform(-180, 180), elevacao=vista[1],
                        perfil_real=r.random() < 0.8)  # fmt: skip
        assert all(math.isfinite(v) for p in _todos_os_pontos(d) for v in p)
        ET.fromstring(svg_da_cena(d))
    cena_3d_png.png_da_cena(d, escala=0.5)
