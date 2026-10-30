"""Desenho da seção da coluna (Flambagem de colunas), que pode girar.

Mostra a forma em corte (hachurada), os eixos x e y pelo centro geométrico G, o centro de
cisalhamento quando ele não coincide com G, a elipse de giração (semi-eixos r_y ao longo de x e
r_x ao longo de y: o lado "achatado" mostra para onde a barra flamba por flexão mais fácil), as
cotas e uma legenda com as propriedades. ``giro_graus`` gira só o desenho (anti-horário), para a
seção ficar como está na estrutura; o texto fica de pé e as cotas acompanham.

A forma vem da própria seção (``Secao.tipo`` e ``Secao.dims``) ou, nos perfis do catálogo sem
medidas guardadas na seção (T e C enrijecido), do catálogo pelo nome. A seção dada só pelas
propriedades (área e raios, ou genérica) não tem forma conhecida: o desenho mostra os eixos, G e a
elipse de giração e diz isso.
"""

from __future__ import annotations

import io
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw

from core import desenho_girado as dg
from core import section_catalog as sc
from core.beam_charts import ImagemDiagrama, _fonte
from core.column_design import Secao
from core.steel_sections import PerfilAco

ESC = dg.ESC
_ACO = "#dbe3ee"  # o aço cortado
_HACHURA = "#94a3b8"
_EIXO = "#1d4ed8"  # eixos x e y
_ELIPSE = "#7c3aed"  # elipse de giração
_CC = "#b91c1c"  # centro de cisalhamento
_LARGURA_PX, _ALTURA_PX = 940, 540

Ponto = tuple[float, float]


@dataclass(frozen=True)
class Cota:
    """Cota de ``a`` até ``b`` (mm, y para cima), afastada para ``lado``.

    ``afastamento_mm`` soma ao afastamento padrão: no círculo, a cota do diâmetro passa por fora.
    """

    a: Ponto
    b: Ponto
    lado: Ponto
    texto: str
    afastamento_mm: float = 0.0


@dataclass(frozen=True)
class Espessura:
    """Cota de espessura: setas de fora para dentro em ``a`` e ``b`` e o texto depois de ``b``."""

    a: Ponto
    b: Ponto
    texto: str


@dataclass(frozen=True)
class FormaDaSecao:
    """A forma para desenhar, em mm, com a origem no centro geométrico G (x à direita, y para cima)."""

    descricao: str
    cheios: tuple[tuple[Ponto, ...], ...] = ()
    vazados: tuple[tuple[Ponto, ...], ...] = ()
    aneis: tuple[tuple[float, float], ...] = ()  # (raio externo, raio interno), centro em G
    cotas: tuple[Cota, ...] = ()
    espessuras: tuple[Espessura, ...] = ()
    conhecida: bool = True

    def extremos(self) -> tuple[float, float, float, float]:
        """(x mín., x máx., y mín., y máx.) da forma, em mm."""
        xs = [p[0] for c in self.cheios for p in c] + [
            s * r for r, _ in self.aneis for s in (-1, 1)
        ]
        ys = [p[1] for c in self.cheios for p in c] + [
            s * r for r, _ in self.aneis for s in (-1, 1)
        ]
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), max(xs), min(ys), max(ys))


def _n(valor: float, casas: int = 1) -> str:
    """Número em pt-BR, sem casas quando é inteiro: 300; 12,5."""
    if abs(valor - round(valor)) < 1e-6:
        return f"{round(valor):d}"
    return f"{valor:.{casas}f}".replace(".", ",")


def _potencia(valor: float, unidade: str) -> str:
    """Momento de inércia na potência de 10 que couber: 22,91 × 10⁶ mm⁴; 0,30 × 10³ mm⁴."""
    for expoente, sobrescrito in ((6, "⁶"), (3, "³")):
        if abs(valor) >= 10**expoente:
            return f"{_n(valor / 10**expoente, 2)} × 10{sobrescrito} {unidade}"
    return f"{_n(valor, 1)} {unidade}"


def _centroide(poligono: Sequence[Ponto]) -> Ponto:
    """O centro geométrico do polígono (fórmula da área com sinal)."""
    area = cx = cy = 0.0
    for i in range(len(poligono)):
        (x1, y1), (x2, y2) = poligono[i - 1], poligono[i]
        cruz = x1 * y2 - x2 * y1
        area += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz
    if abs(area) < 1e-12:
        return (0.0, 0.0)
    return (cx / (3 * area), cy / (3 * area))


def _perfil_do_catalogo(secao: Secao) -> PerfilAco | None:
    try:
        return sc.obter_perfil(secao.nome)
    except (sc.ErroDeCatalogo, KeyError, ValueError):
        return None


# ------------------------------------------------------------------ as formas
def _forma_I(d: float, bf: float, tf: float, tw: float, soldado: bool) -> FormaDaSecao:
    h, w = d / 2, bf / 2
    contorno = (
        (-w, -h), (w, -h), (w, -h + tf), (tw / 2, -h + tf), (tw / 2, h - tf), (w, h - tf),
        (w, h), (-w, h), (-w, h - tf), (-tw / 2, h - tf), (-tw / 2, -h + tf), (-w, -h + tf),
    )  # fmt: skip
    x_tf = w - 0.2 * bf
    y_tw = -(h - tf) / 2
    return FormaDaSecao(
        "Perfil I " + ("soldado" if soldado else "laminado (sem os raios de concordância)"),
        cheios=(contorno,),
        cotas=(
            Cota((-w, -h), (-w, h), (-1.0, 0.0), f"d = {_n(d)}"),
            Cota((-w, h), (w, h), (0.0, 1.0), f"b_f = {_n(bf)}"),
        ),
        espessuras=(
            Espessura((x_tf, -h + tf), (x_tf, -h), f"t_f = {_n(tf)}"),
            Espessura((-tw / 2, y_tw), (tw / 2, y_tw), f"t_w = {_n(tw)}"),
        ),
    )


def _forma_U(d: float, bf: float, tf: float, tw: float, xb: float) -> FormaDaSecao:
    """U com a alma à esquerda e as mesas para a direita; G a ``xb`` do dorso da alma."""
    h = d / 2
    x0, x1 = -xb, bf - xb
    contorno = (
        (x0, -h), (x1, -h), (x1, -h + tf), (x0 + tw, -h + tf), (x0 + tw, h - tf), (x1, h - tf),
        (x1, h), (x0, h),
    )  # fmt: skip
    x_tf = x1 - 0.2 * bf
    y_tw = -(h - tf) / 2
    return FormaDaSecao(
        "Perfil U (mesas de espessura constante)",
        cheios=(contorno,),
        cotas=(
            Cota((x1, -h), (x1, h), (1.0, 0.0), f"d = {_n(d)}"),
            Cota((x0, h), (x1, h), (0.0, 1.0), f"b_f = {_n(bf)}"),
        ),
        espessuras=(
            Espessura((x_tf, -h + tf), (x_tf, -h), f"t_f = {_n(tf)}"),
            Espessura((x0, y_tw), (x0 + tw, y_tw), f"t_w = {_n(tw)}"),
        ),
    )


def _forma_T(d: float, bf: float, tf: float, tw: float, yb: float) -> FormaDaSecao:
    """T com a mesa em cima e o talão para baixo; G a ``yb`` da ponta do talão."""
    y0, y1 = -yb, d - yb
    w = bf / 2
    contorno = (
        (-tw / 2, y0), (tw / 2, y0), (tw / 2, y1 - tf), (w, y1 - tf), (w, y1), (-w, y1),
        (-w, y1 - tf), (-tw / 2, y1 - tf),
    )  # fmt: skip
    x_tf = w - 0.2 * bf
    y_tw = y0 + 0.3 * (d - tf)
    return FormaDaSecao(
        "Perfil T (mesa em cima)",
        cheios=(contorno,),
        cotas=(
            Cota((-w, y0), (-w, y1), (-1.0, 0.0), f"d = {_n(d)}"),
            Cota((-w, y1), (w, y1), (0.0, 1.0), f"b_f = {_n(bf)}"),
        ),
        espessuras=(
            Espessura((x_tf, y1), (x_tf, y1 - tf), f"t_f = {_n(tf)}"),
            Espessura((-tw / 2, y_tw), (tw / 2, y_tw), f"t_w = {_n(tw)}"),
        ),
    )


def _forma_C(d: float, bf: float, enrijecedor: float, t: float, xb: float) -> FormaDaSecao:
    """C enrijecido (chapa dobrada, cantos vivos): alma à esquerda, enrijecedores para dentro."""
    h = d / 2
    x0, x1 = -xb, bf - xb
    c = min(max(enrijecedor, t), h)
    contorno = (
        (x0, -h), (x1, -h), (x1, -h + c), (x1 - t, -h + c), (x1 - t, -h + t), (x0 + t, -h + t),
        (x0 + t, h - t), (x1 - t, h - t), (x1 - t, h - c), (x1, h - c), (x1, h), (x0, h),
    )  # fmt: skip
    return FormaDaSecao(
        f"Perfil C enrijecido (enrijecedor D = {_n(enrijecedor)} mm, sem os raios das dobras)",
        cheios=(contorno,),
        cotas=(
            Cota((x1, -h), (x1, h), (1.0, 0.0), f"d = {_n(d)}"),
            Cota((x0, h), (x1, h), (0.0, 1.0), f"b_f = {_n(bf)}"),
        ),
        espessuras=(Espessura((x0 + 0.45 * bf, -h + t), (x0 + 0.45 * bf, -h), f"t = {_n(t, 2)}"),),
    )


def _forma_tubo_retangular(largura: float, altura: float, t: float) -> FormaDaSecao:
    w, h = largura / 2, altura / 2
    y_t = -h / 2
    return FormaDaSecao(
        "Tubo retangular (cantos vivos)",
        cheios=(((-w, -h), (w, -h), (w, h), (-w, h)),),
        vazados=(((-w + t, -h + t), (w - t, -h + t), (w - t, h - t), (-w + t, h - t)),),
        cotas=(
            Cota((-w, -h), (-w, h), (-1.0, 0.0), f"H = {_n(altura)}"),
            Cota((-w, h), (w, h), (0.0, 1.0), f"B = {_n(largura)}"),
        ),
        espessuras=(Espessura((w - t, y_t), (w, y_t), f"t = {_n(t, 2)}"),),
    )


def _forma_circular(diametro: float, t: float | None) -> FormaDaSecao:
    r = diametro / 2
    interno = max(r - t, 0.0) if t else 0.0
    nome = "D" if t else "d"
    espessuras: tuple[Espessura, ...] = ()
    if t:
        c, s = math.cos(math.radians(-40.0)), math.sin(math.radians(-40.0))
        espessuras = (Espessura((interno * c, interno * s), (r * c, r * s), f"t = {_n(t, 2)}"),)
    return FormaDaSecao(
        "Tubo circular" if t else "Barra circular maciça",
        aneis=((r, interno),),
        cotas=(Cota((-r, 0.0), (r, 0.0), (0.0, 1.0), f"{nome} = {_n(diametro)}", r),),
        espessuras=espessuras,
    )


def _forma_retangular(largura: float, altura: float) -> FormaDaSecao:
    w, h = largura / 2, altura / 2
    return FormaDaSecao(
        "Barra retangular maciça",
        cheios=(((-w, -h), (w, -h), (w, h), (-w, h)),),
        cotas=(
            Cota((-w, -h), (-w, h), (-1.0, 0.0), f"h = {_n(altura)}"),
            Cota((-w, h), (w, h), (0.0, 1.0), f"b = {_n(largura)}"),
        ),
    )


def _do_catalogo(secao: Secao) -> FormaDaSecao | None:
    """T e C enrijecido do catálogo: a seção não guarda as medidas, o catálogo sim."""
    perfil = _perfil_do_catalogo(secao)
    if perfil is None:
        return None
    familia = str(perfil.familia).casefold()
    d, bf = perfil.altura_mm, perfil.largura_mm
    tw, tf = perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    if familia.startswith("t "):
        forma = _forma_T(d, bf, tf, tw, d / 2)
        yb = perfil.centroide_y_mm if 0 < perfil.centroide_y_mm < d else None
        if yb is None:  # o centro geométrico do próprio desenho
            yb = d / 2 + _centroide(forma.cheios[0])[1]
        return _forma_T(d, bf, tf, tw, yb)
    if "enrijecido" in familia:
        numeros = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", perfil.nome)]
        enrijecedor = numeros[2] if len(numeros) >= 4 else 0.0
        forma = _forma_C(d, bf, enrijecedor, tw, 0.0)
        xb = perfil.centroide_x_mm if 0 < perfil.centroide_x_mm < bf else None
        if xb is None:
            xb = _centroide(forma.cheios[0])[0]
        return _forma_C(d, bf, enrijecedor, tw, xb)
    return None


def forma_da_secao(secao: Secao) -> FormaDaSecao:
    """A forma da seção para o desenho, com G na origem."""
    dims, tipo = secao.dims, secao.tipo
    if tipo == "I":
        return _forma_I(dims["d"], dims["bf"], dims["tf"], dims["tw"], bool(dims.get("soldado")))
    if tipo == "U":
        return _forma_U(dims["d"], dims["bf"], dims["tf"], dims["tw"], dims["xb"])
    if tipo == "tubo_circ":
        return _forma_circular(dims["D"], dims["t"])
    if tipo == "tubo_ret":
        return _forma_tubo_retangular(dims["B"], dims["H"], dims["t"])
    if tipo == "circ_macica":
        return _forma_circular(dims["d"], None)
    if tipo == "ret_macica":
        return _forma_retangular(dims["b"], dims["h"])
    forma = _do_catalogo(secao)
    if forma is not None:
        return forma
    return FormaDaSecao("Seção dada pelas propriedades: a forma não é conhecida", conhecida=False)


# ------------------------------------------------------------------ o desenho
def _hachurar(imagem: Image.Image, mascara: Image.Image) -> None:
    """Pinta o aço e a hachura de corte (45°) só dentro da máscara."""
    imagem.paste(_ACO, mask=mascara)
    linhas = Image.new("L", imagem.size, 0)
    traco = ImageDraw.Draw(linhas)
    largura, altura = imagem.size
    passo = 8 * ESC
    for k in range(-altura, largura, passo):
        traco.line([(k, altura), (k + altura, 0)], fill=255, width=ESC)
    imagem.paste(_HACHURA, mask=ImageChops.multiply(mascara, linhas))


def _seta_de_espessura(dr: ImageDraw.ImageDraw, a: Ponto, b: Ponto, texto: str) -> None:
    """Duas setas de fora para dentro, nas faces ``a`` e ``b`` (px), e o texto depois de ``b``."""
    direcao = (b[0] - a[0], b[1] - a[1])
    comprimento = 16 * ESC
    dg.seta(dr, dg.mais(a, direcao, -comprimento), a, dg.COR_COTA, largura=ESC, ponta_px=7 * ESC)
    dg.seta(dr, dg.mais(b, direcao, comprimento), b, dg.COR_COTA, largura=ESC, ponta_px=7 * ESC)
    dg.rotulo(
        dr, b, direcao, comprimento + 3 * ESC, texto, dg.COR_COTA, _fonte(11 * ESC), fundo=True
    )


def _centro_geometrico(dr: ImageDraw.ImageDraw, centro: Ponto, giro: float) -> None:
    """O símbolo do centro geométrico: círculo com dois quadrantes cheios (giram com a peça)."""
    r = 8 * ESC
    caixa = [centro[0] - r, centro[1] - r, centro[0] + r, centro[1] + r]
    dr.ellipse(caixa, fill="#ffffff", outline=dg.COR_TEXTO, width=ESC)
    for inicio in (0.0, 180.0):
        dr.pieslice(caixa, inicio - giro, inicio - giro + 90.0, fill=dg.COR_TEXTO)


def _elipse(tela: dg.Tela, rx: float, ry: float) -> list[Ponto]:
    """A elipse de giração (px): semi-eixo r_y ao longo de x e r_x ao longo de y."""
    return [
        tela(ry * math.cos(2 * math.pi * k / 96), -rx * math.sin(2 * math.pi * k / 96))
        for k in range(96)
    ]


def _tracejado_fechado(dr: ImageDraw.ImageDraw, pontos: Sequence[Ponto], cor: str) -> None:
    for i in range(0, len(pontos), 2):
        dr.line([pontos[i], pontos[(i + 1) % len(pontos)]], fill=cor, width=ESC)


def figura_da_secao(secao: Secao, *, giro_graus: float = 0.0) -> ImagemDiagrama:
    """O desenho da seção (PNG) com a legenda; ``giro_graus`` gira só o desenho."""
    giro = dg.angulo_do_giro(giro_graus)
    forma = forma_da_secao(secao)
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    rx, ry = secao.rx, secao.ry
    if forma.conhecida:
        xmin, xmax, ymin, ymax = forma.extremos()
    else:
        xmin, xmax, ymin, ymax = -ry, ry, -rx, rx
    tamanho = max(xmax - xmin, ymax - ymin, 1.0)
    sobra = 0.26 * tamanho + 8.0  # os eixos passam da peça (e das cotas)
    ex0, ex1 = min(xmin, -ry) - sobra, max(xmax, ry) + sobra
    ey0, ey1 = min(ymin, -rx) - sobra, max(ymax, rx) + sobra
    # y para cima na seção; na tela, para baixo
    tela = dg.Tela([(ex0, -ey1), (ex1, -ey0), (ex0, -ey0), (ex1, -ey1)], (70, 90, 540, 500), giro)

    def p(x: float, y: float) -> Ponto:
        return tela(x, -y)

    # ------------------------------------------------------------------ o aço, em corte
    if forma.conhecida:
        mascara = Image.new("L", imagem.size, 0)
        traco = ImageDraw.Draw(mascara)
        for contorno in forma.cheios:
            traco.polygon([p(*q) for q in contorno], fill=255)
        for contorno in forma.vazados:
            traco.polygon([p(*q) for q in contorno], fill=0)
        for externo, interno in forma.aneis:
            g = p(0.0, 0.0)
            for raio, cor in ((externo, 255), (interno, 0)):
                if raio > 0:
                    r = raio * tela.esc
                    traco.ellipse([g[0] - r, g[1] - r, g[0] + r, g[1] + r], fill=cor)
        _hachurar(imagem, mascara)
        for contorno in (*forma.cheios, *forma.vazados):
            dr.polygon([p(*q) for q in contorno], outline=dg.COR_LINHA, width=2 * ESC)
        for externo, interno in forma.aneis:
            g = p(0.0, 0.0)
            for raio in (externo, interno):
                if raio > 0:
                    r = raio * tela.esc
                    dr.ellipse(
                        [g[0] - r, g[1] - r, g[0] + r, g[1] + r],
                        outline=dg.COR_LINHA,
                        width=2 * ESC,
                    )
    # ------------------------------------------------------------------ elipse e eixos
    _tracejado_fechado(dr, _elipse(tela, rx, ry), _ELIPSE)
    fonte = _fonte(13 * ESC)
    for nome, a, b, direcao in (
        ("x", p(ex0, 0.0), p(ex1, 0.0), tela.direcao(1.0, 0.0)),
        ("y", p(0.0, ey0), p(0.0, ey1), tela.direcao(0.0, -1.0)),
    ):
        dg.traco_ponto(dr, a, b, _EIXO, largura=ESC)
        dg.seta(dr, dg.mais(b, direcao, -14 * ESC), b, _EIXO, largura=ESC, ponta_px=10 * ESC)
        dg.rotulo(dr, b, direcao, 5 * ESC, nome, _EIXO, fonte)
    # ------------------------------------------------------------------ cotas
    for cota in forma.cotas:
        lado = tela.direcao(cota.lado[0], -cota.lado[1])
        # o texto fora do cruzamento com os eixos: embaixo nas cotas em pé, à direita nas deitadas
        vertical = abs(cota.a[0] - cota.b[0]) < 1e-9
        afastamento = cota.afastamento_mm * tela.esc + 18 * ESC
        dg.cota_alinhada(
            dr, p(*cota.a), p(*cota.b), lado, cota.texto, afastamento,
            posicao=0.22 if vertical else 0.78, fundo=True,
        )  # fmt: skip
    for espessura in forma.espessuras:
        _seta_de_espessura(dr, p(*espessura.a), p(*espessura.b), espessura.texto)
    # ------------------------------------------------------------------ G e o centro de cisalhamento
    g = p(0.0, 0.0)
    _centro_geometrico(dr, g, giro)
    canto = tela.direcao(1.0, 1.0)  # acima e à direita de G, na peça
    dg.rotulo(dr, g, canto, 12 * ESC, "G", dg.COR_TEXTO, fonte, fundo=True)
    cc = (secao.x0, secao.y0)
    tem_cc = math.hypot(*cc) > 0.5
    if tem_cc:
        # U e C: o centro de cisalhamento fica do lado de fora da alma (x negativo); T: em cima
        ponto_cc = p(-abs(cc[0]), abs(cc[1]))
        r = 5 * ESC
        dr.ellipse(
            [ponto_cc[0] - r, ponto_cc[1] - r, ponto_cc[0] + r, ponto_cc[1] + r],
            fill=_CC,
            outline="#ffffff",
            width=ESC,
        )
        lado_cc = tela.direcao(-1.0, -1.0) if cc[0] else tela.direcao(1.0, -1.0)
        dg.rotulo(dr, ponto_cc, lado_cc, 10 * ESC, "CC", _CC, fonte, fundo=True)
    # ------------------------------------------------------------------ legenda
    eixo_fraco = "y" if ry < rx - 1e-9 else ("x" if rx < ry - 1e-9 else "")
    itens: list[tuple[str, str, str]] = [("area", _ACO, "Aço da seção (em corte)")]
    if not forma.conhecida:
        itens = []
    itens += [
        ("eixo", _EIXO, "Eixos x e y pelo centro geométrico G"),
        ("ponto", dg.COR_TEXTO, "G: centro geométrico"),
    ]
    if tem_cc:
        itens.append(
            ("ponto", _CC, f"CC: centro de cisalhamento (a {_n(math.hypot(*cc), 1)} mm de G)")
        )
    itens += [
        ("tracejado", _ELIPSE, "Elipse de giração (semi-eixos r_y e r_x)"),
        ("", dg.COR_TEXTO, f"   r_x = {_n(rx, 1)} mm · r_y = {_n(ry, 1)} mm"),
    ]
    if eixo_fraco:
        itens.append(("", dg.COR_TEXTO, f"   menor raio de giração: em torno de {eixo_fraco}"))
    itens += [
        ("", dg.COR_TEXTO, ""),
        ("", dg.COR_TEXTO, f"A = {_n(secao.A, 0)} mm²"),
        ("", dg.COR_TEXTO, f"I_x = {_potencia(secao.Ix, 'mm⁴')}"),
        ("", dg.COR_TEXTO, f"I_y = {_potencia(secao.Iy, 'mm⁴')}"),
    ]
    if secao.J:
        itens.append(("", dg.COR_TEXTO, f"J = {_potencia(secao.J, 'mm⁴')}"))
    if giro:
        itens.append(("", dg.COR_COTA, f"Desenho girado {dg.texto_do_giro(giro)}"))
    if not forma.conhecida:
        itens.append(("", dg.COR_COTA, "Sem a forma: só os eixos, G e a elipse de giração"))
    dg.legenda(dr, 575 * ESC, 96 * ESC, itens)
    titulo = f"Seção da coluna — {secao.nome}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        f"{forma.descricao}." + (" Cotas em mm." if forma.conhecida else ""),
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"{secao.nome}: {forma.descricao[:1].lower()}{forma.descricao[1:]}; eixos x e y por G"
        + ("; CC = centro de cisalhamento" if tem_cc else "")
        + (f"; desenho girado {dg.texto_do_giro(giro)}" if giro else "")
        + "."
    )
    final = imagem.resize((_LARGURA_PX, _ALTURA_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, buffer.getvalue(), _LARGURA_PX, _ALTURA_PX)
