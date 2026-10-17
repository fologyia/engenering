"""Figuras do pórtico plano no estilo do Ftool, para a página e para o memorial.

Cada figura é um PNG desenhado com o Pillow a partir de um :class:`ResultadoPortico`:

* **Estrutura**: barras, nós, apoios, rótulas e as cargas com os valores;
* **Reações**: as forças dos apoios, com sentido e valor;
* **Diagramas de N, V e M** desenhados sobre as próprias barras, como no Ftool — o momento do
  lado tracionado —, com os valores nas pontas e no extremo de cada barra;
* **Tensão** |N|/A + |M|/W ao longo das barras;
* **Deformada** ampliada sobre a estrutura original, com o maior deslocamento e a flecha de cada
  barra em mm.

O desenho é feito no dobro do tamanho e reduzido no fim (traço suavizado), com a fonte, a paleta e
o formato de imagem (:class:`ImagemDiagrama`) de :mod:`core.beam_charts`. Sem Streamlit.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from PIL import Image, ImageDraw, ImageFont

from core import portico_plano as pp
from core.beam_charts import (
    COR_CORTANTE,
    COR_FLECHA,
    COR_MOMENTO,
    COR_NORMAL,
    COR_TORQUE,
    ImagemDiagrama,
    _fonte,
    _rgba,
)

_ESC = 2  # desenho no dobro do tamanho, reduzido no fim
_FUNDO = "#ffffff"
_BARRA = "#1e293b"
_BARRA_FRACA = "#94a3b8"
_TEXTO = "#0f172a"
_TEXTO_FRACO = "#64748b"
_CARGA = "#b91c1c"
_REACAO = "#15803d"
_APOIO = "#334155"
_APOIO_FUNDO = "#e2e8f0"

Ponto = tuple[float, float]


@dataclass(frozen=True)
class TipoDiagrama:
    chave: str
    titulo: str
    unidade: str
    atributo: str  # campo de PontoDaBarra
    cor: str
    lado: float  # +1: valor positivo para o lado local +y; −1: para o lado local −y
    nota: str


DIAGRAMAS = {
    "N": TipoDiagrama("N", "Esforço normal N", "kN", "n", COR_NORMAL, 1.0, "N positivo = tração."),
    "V": TipoDiagrama("V", "Esforço cortante V", "kN", "v", COR_CORTANTE, 1.0, ""),
    "M": TipoDiagrama(
        "M",
        "Momento fletor M",
        "kN·m",
        "m",
        COR_MOMENTO,
        -1.0,
        "Momento desenhado do lado tracionado da barra.",
    ),
    "tensao": TipoDiagrama(
        "tensao",
        "Tensão normal |N|/A + |M|/W",
        "MPa",
        "tensao_MPa",
        COR_TORQUE,
        1.0,
        "Soma da tensão do normal e da flexão, na fibra mais solicitada (sem flambagem).",
    ),
}


def numero(valor: float, casas: int = 2) -> str:
    """Vírgula decimal e ponto no milhar: 1234.5 → "1.234,50"; −0,00 vira "0,00"."""
    texto = f"{valor + 0.0:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return "0," + "0" * casas if texto.lstrip("-").strip("0,.") == "" else texto


# ---------------------------------------------------------------------------------------------
# Geometria auxiliar
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _GeoBarra:
    resultado: pp.ResultadoBarra
    xi: float
    yi: float
    c: float
    s: float

    def ponto(self, x: float, desvio: float = 0.0) -> Ponto:
        """Ponto a ``x`` da ponta i, deslocado ``desvio`` no sentido local +y (mundo, m)."""
        return (self.xi + x * self.c - desvio * self.s, self.yi + x * self.s + desvio * self.c)


def _geometrias(r: pp.ResultadoPortico) -> list[_GeoBarra]:
    nos = {n.nome: n for n in r.portico.nos}
    saida = []
    for rb in r.barras:
        ni, nj = nos[rb.barra.no_i], nos[rb.barra.no_j]
        saida.append(
            _GeoBarra(
                rb,
                ni.x,
                ni.y,
                (nj.x - ni.x) / rb.comprimento_m,
                (nj.y - ni.y) / rb.comprimento_m,
            )
        )
    return saida


def _tamanho_de_referencia(r: pp.ResultadoPortico) -> float:
    xs = [n.x for n in r.portico.nos]
    ys = [n.y for n in r.portico.nos]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-3)


# ---------------------------------------------------------------------------------------------
# Tela: mundo (m, y para cima) → pixel (y para baixo), já na escala de superamostragem
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Tela:
    escala: float  # pixel por metro
    x_min: float
    y_max: float
    esquerda: float
    topo: float
    largura_px: int
    altura_px: int

    def p(self, x: float, y: float) -> Ponto:
        return (
            self.esquerda + (x - self.x_min) * self.escala,
            self.topo + (self.y_max - y) * self.escala,
        )


def _nova_tela(
    pontos: Sequence[Ponto],
    largura_px: int,
    altura_max_px: int,
    *,
    topo: int = 120,
    base: int = 100,
    lados: int = 110,
) -> tuple[Image.Image, _Tela]:
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
    largura_util = (largura_px - 2 * lados) * _ESC
    altura_util = max(altura_max_px - topo - base, 60) * _ESC
    escalas = []
    if x_max - x_min > 1e-9:
        escalas.append(largura_util / (x_max - x_min))
    if y_max - y_min > 1e-9:
        escalas.append(altura_util / (y_max - y_min))
    escala = min(escalas) if escalas else 1.0
    conteudo_l = (x_max - x_min) * escala
    conteudo_a = (y_max - y_min) * escala
    altura_px = max(int(round(conteudo_a / _ESC)) + topo + base, 280)
    tela = _Tela(
        escala,
        x_min,
        y_max,
        (largura_px * _ESC - conteudo_l) / 2,
        topo * _ESC + ((altura_px - topo - base) * _ESC - conteudo_a) / 2,
        largura_px,
        altura_px,
    )
    return Image.new("RGBA", (largura_px * _ESC, altura_px * _ESC), _FUNDO), tela


def _finalizar(imagem: Image.Image, tela: _Tela, titulo: str, legenda: str) -> ImagemDiagrama:
    final = imagem.convert("RGB").resize(
        (tela.largura_px, tela.altura_px), Image.Resampling.LANCZOS
    )
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, buffer.getvalue(), tela.largura_px, tela.altura_px)


def _cabecalho(d: ImageDraw.ImageDraw, tela: _Tela, titulo: str, nota: str = "") -> None:
    d.text((18 * _ESC, 12 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    if nota:
        d.text((18 * _ESC, 34 * _ESC), nota, fill=_TEXTO_FRACO, font=_fonte(11 * _ESC))


# ---------------------------------------------------------------------------------------------
# Primitivas de desenho (em pixel)
# ---------------------------------------------------------------------------------------------
def _unitario(v: Ponto) -> Ponto:
    norma = math.hypot(*v)
    return (v[0] / norma, v[1] / norma) if norma > 1e-12 else (0.0, 0.0)


def _seta(
    d: ImageDraw.ImageDraw, cauda: Ponto, ponta: Ponto, cor: str, largura: int = 2, cabeca: int = 9
) -> None:
    d.line([cauda, ponta], fill=cor, width=largura * _ESC)
    ang = math.atan2(ponta[1] - cauda[1], ponta[0] - cauda[0])
    tamanho = cabeca * _ESC
    lados = [
        (
            ponta[0] - tamanho * math.cos(ang + k * 0.42),
            ponta[1] - tamanho * math.sin(ang + k * 0.42),
        )
        for k in (-1, 1)
    ]
    d.polygon([ponta, *lados], fill=cor)


def _caixa_do_texto(
    d: ImageDraw.ImageDraw,
    centro: Ponto,
    texto: str,
    fonte: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = d.textbbox(centro, texto, font=fonte, anchor="mm")
    folga = 3 * _ESC
    return (x0 - folga, y0 - folga, x1 + folga, y1 + folga)


def _sobrepoe(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class _Rotulos:
    """Escreve rótulos com fundo branco, afastando-os quando caem uns sobre os outros."""

    def __init__(self, d: ImageDraw.ImageDraw) -> None:
        self.d = d
        self.caixas: list[tuple[float, float, float, float]] = []

    def escrever(
        self,
        centro: Ponto,
        texto: str,
        cor: str = _TEXTO,
        afastar: Ponto = (0.0, -1.0),
        tamanho: int = 12,
    ) -> None:
        fonte = _fonte(tamanho * _ESC)
        passo = _unitario(afastar)
        if passo == (0.0, 0.0):
            passo = (0.0, -1.0)
        caixa = _caixa_do_texto(self.d, centro, texto, fonte)
        for _tentativa in range(6):
            if not any(_sobrepoe(caixa, outra) for outra in self.caixas):
                break
            altura = caixa[3] - caixa[1]
            centro = (centro[0] + passo[0] * altura, centro[1] + passo[1] * altura)
            caixa = _caixa_do_texto(self.d, centro, texto, fonte)
        self.caixas.append(caixa)
        self.d.rectangle(caixa, fill=_FUNDO)
        self.d.text(centro, texto, fill=cor, font=fonte, anchor="mm")


def _direcao_das_barras(r: pp.ResultadoPortico, tela: _Tela) -> dict[str, Ponto]:
    """Para cada nó, a média (pixel) dos sentidos do nó para as barras que chegam nele."""
    nos = {n.nome: n for n in r.portico.nos}
    soma: dict[str, list[float]] = {nome: [0.0, 0.0] for nome in nos}
    for b in r.portico.barras:
        for de, para in ((b.no_i, b.no_j), (b.no_j, b.no_i)):
            a, z = tela.p(nos[de].x, nos[de].y), tela.p(nos[para].x, nos[para].y)
            u = _unitario((z[0] - a[0], z[1] - a[1]))
            soma[de][0] += u[0]
            soma[de][1] += u[1]
    return {nome: (v[0], v[1]) for nome, v in soma.items()}


def _desenhar_barras(
    d: ImageDraw.ImageDraw,
    r: pp.ResultadoPortico,
    tela: _Tela,
    cor: str = _BARRA,
    largura: int = 3,
    rotulos: _Rotulos | None = None,
) -> None:
    for g in _geometrias(r):
        a = tela.p(*g.ponto(0.0))
        z = tela.p(*g.ponto(g.resultado.comprimento_m))
        d.line([a, z], fill=cor, width=largura * _ESC)
        if rotulos is not None:  # nome da barra embaixo dela (à direita, se for vertical)
            meio = ((a[0] + z[0]) / 2, (a[1] + z[1]) / 2)
            normal = _unitario((z[1] - a[1], -(z[0] - a[0])))
            if (normal[1] < 0) if abs(normal[1]) > 0.1 else (normal[0] < 0):
                normal = (-normal[0], -normal[1])
            centro = (meio[0] + normal[0] * 14 * _ESC, meio[1] + normal[1] * 14 * _ESC)
            rotulos.escrever(centro, g.resultado.barra.nome, _TEXTO_FRACO, normal, 10)


def _desenhar_rotulas(d: ImageDraw.ImageDraw, r: pp.ResultadoPortico, tela: _Tela) -> None:
    for g in _geometrias(r):
        a = tela.p(*g.ponto(0.0))
        z = tela.p(*g.ponto(g.resultado.comprimento_m))
        u = _unitario((z[0] - a[0], z[1] - a[1]))
        raio = 4.5 * _ESC
        for solta, ponta, sentido in (
            (g.resultado.barra.rotula_i, a, 1.0),
            (g.resultado.barra.rotula_j, z, -1.0),
        ):
            if solta:
                c = (ponta[0] + sentido * u[0] * 8 * _ESC, ponta[1] + sentido * u[1] * 8 * _ESC)
                d.ellipse(
                    [c[0] - raio, c[1] - raio, c[0] + raio, c[1] + raio],
                    fill=_FUNDO,
                    outline=_BARRA,
                    width=2 * _ESC,
                )


def _tipo_do_apoio(a: pp.Apoio) -> str:
    if a.ux and a.uy and a.rz:
        return "engaste"
    if a.ux and a.uy:
        return "pino"
    if (a.ux or a.uy) and not a.rz:
        return "rolete"
    return "outro"


def _sentido_do_apoio(a: pp.Apoio, media: Ponto) -> Ponto:
    """Para onde fica o "chão" do símbolo (pixel): embaixo, ou do lado de fora da estrutura."""
    tipo = _tipo_do_apoio(a)
    fora = _unitario((-media[0], -media[1]))
    if tipo == "engaste":
        if fora == (0.0, 0.0):
            return (0.0, 1.0)
        return (
            (math.copysign(1.0, fora[0]), 0.0)
            if abs(fora[0]) > abs(fora[1])
            else (
                0.0,
                math.copysign(1.0, fora[1]),
            )
        )
    if tipo == "rolete" and a.ux and not a.uy:  # só segura na horizontal: símbolo de lado
        return (-1.0, 0.0) if media[0] >= 0 else (1.0, 0.0)
    return (0.0, 1.0)


def _desenhar_apoios(
    d: ImageDraw.ImageDraw, r: pp.ResultadoPortico, tela: _Tela, cor: str = _APOIO
) -> None:
    nos = {n.nome: n for n in r.portico.nos}
    medias = _direcao_das_barras(r, tela)
    for a in r.portico.apoios:
        centro = tela.p(nos[a.no].x, nos[a.no].y)
        ux, uy = _sentido_do_apoio(a, medias[a.no])
        vx, vy = -uy, ux

        def q(ao_longo: float, atravessado: float, ux=ux, uy=uy, vx=vx, vy=vy, c=centro) -> Ponto:
            return (
                c[0] + (ux * ao_longo + vx * atravessado) * _ESC,
                c[1] + (uy * ao_longo + vy * atravessado) * _ESC,
            )

        tipo = _tipo_do_apoio(a)
        if tipo == "outro":
            lado = 7 * _ESC
            d.rectangle(
                [centro[0] - lado, centro[1] - lado, centro[0] + lado, centro[1] + lado],
                outline=cor,
                width=2 * _ESC,
            )
            continue
        if tipo == "engaste":
            chao = 2.0
            d.line([q(chao, -18), q(chao, 18)], fill=cor, width=3 * _ESC)
        else:
            d.polygon(
                [q(0, 0), q(19, -12), q(19, 12)], fill=_APOIO_FUNDO, outline=cor, width=2 * _ESC
            )
            chao = 19.0
            if tipo == "rolete":
                chao = 25.0
            d.line([q(chao, -18), q(chao, 18)], fill=cor, width=2 * _ESC)
        for b in range(-18, 19, 6):
            d.line([q(chao, b), q(chao + 7, b - 6)], fill=cor, width=_ESC)


def _desenhar_nos(
    d: ImageDraw.ImageDraw, r: pp.ResultadoPortico, tela: _Tela, rotulos: _Rotulos | None = None
) -> None:
    medias = _direcao_das_barras(r, tela)
    raio = 3 * _ESC
    for n in r.portico.nos:
        c = tela.p(n.x, n.y)
        d.ellipse([c[0] - raio, c[1] - raio, c[0] + raio, c[1] + raio], fill=_BARRA)
        if rotulos is not None:
            fora = _unitario((-medias[n.nome][0], -medias[n.nome][1]))
            if math.hypot(*medias[n.nome]) < 0.3:
                fora = (-0.6, -0.8)
            centro = (c[0] + fora[0] * 20 * _ESC, c[1] + fora[1] * 20 * _ESC)
            if any(a.no == n.nome for a in r.portico.apoios) and fora[1] > 0.3:
                centro = (c[0] - 24 * _ESC, c[1] - 14 * _ESC)  # não cobre o símbolo do apoio
            rotulos.escrever(centro, n.nome, _BARRA, fora, 11)


def _seta_curva(
    d: ImageDraw.ImageDraw, centro: Ponto, momento: float, cor: str, raio: int = 24
) -> None:
    """Momento: arco de 270° com a ponta no sentido do giro (anti-horário quando > 0)."""
    rr = raio * _ESC
    caixa = [centro[0] - rr, centro[1] - rr, centro[0] + rr, centro[1] + rr]
    inicio, fim = 30.0, 300.0  # graus na tela (horário, a partir das 3 h)
    d.arc(caixa, inicio, fim, fill=cor, width=2 * _ESC)
    if momento > 0:  # anti-horário na tela: anda de "fim" para "inicio"
        th = math.radians(inicio)
        tangente = (math.sin(th), -math.cos(th))
    else:
        th = math.radians(fim)
        tangente = (-math.sin(th), math.cos(th))
    ponta = (centro[0] + rr * math.cos(th), centro[1] + rr * math.sin(th))
    cauda = (ponta[0] - tangente[0] * 10 * _ESC, ponta[1] - tangente[1] * 10 * _ESC)
    _seta(d, cauda, ponta, cor, 2, 9)


# ---------------------------------------------------------------------------------------------
# Figura 1: estrutura, apoios e cargas
# ---------------------------------------------------------------------------------------------
def _direcao_da_distribuida(carga: pp.CargaDistribuida, g: _GeoBarra) -> Ponto:
    """Sentido da força no mundo (unitário) para q positivo."""
    if carga.direcao in (pp.GLOBAL_Y, pp.GLOBAL_Y_PROJETADA):
        return (0.0, 1.0)
    if carga.direcao in (pp.GLOBAL_X, pp.GLOBAL_X_PROJETADA):
        return (1.0, 0.0)
    if carga.direcao == pp.LOCAL_Y:
        return (-g.s, g.c)
    return (g.c, g.s)


def _texto_da_distribuida(carga: pp.CargaDistribuida) -> str:
    qj = carga.qi if carga.qj is None else carga.qj
    valor = (
        f"{numero(abs(carga.qi))} kN/m"
        if math.isclose(carga.qi, qj)
        else f"{numero(abs(carga.qi))} a {numero(abs(qj))} kN/m"
    )
    if carga.direcao in (pp.GLOBAL_Y_PROJETADA, pp.GLOBAL_X_PROJETADA):
        valor += " proj."
    return f"{carga.nome}: {valor}" if carga.nome else valor


def _desenhar_distribuidas(
    d: ImageDraw.ImageDraw, r: pp.ResultadoPortico, tela: _Tela, rotulos: _Rotulos
) -> None:
    cargas = r.portico.cargas_distribuidas
    q_max = max((max(abs(c.qi), abs(c.qi if c.qj is None else c.qj)) for c in cargas), default=0.0)
    if q_max <= 0:
        return
    geos = {g.resultado.barra.nome: g for g in _geometrias(r)}
    nivel_da_barra: dict[str, int] = {}
    h_min, h_max = 12.0, 36.0
    for carga in cargas:
        g = geos[carga.barra]
        nivel = nivel_da_barra.get(carga.barra, 0)
        nivel_da_barra[carga.barra] = nivel + 1
        qj = carga.qi if carga.qj is None else carga.qj
        if abs(carga.qi) < 1e-12 and abs(qj) < 1e-12:
            continue
        sinal = 1.0 if carga.qi + qj >= 0 else -1.0
        fw = _direcao_da_distribuida(carga, g)
        f = _unitario((fw[0] * sinal, -fw[1] * sinal))  # sentido da força, na tela
        a = tela.p(*g.ponto(0.0))
        z = tela.p(*g.ponto(g.resultado.comprimento_m))
        eixo = _unitario((z[0] - a[0], z[1] - a[1]))
        paralela = abs(f[0] * eixo[1] - f[1] * eixo[0]) < 0.25
        comprimento_tela = math.hypot(z[0] - a[0], z[1] - a[1])
        n_setas = max(5, int(comprimento_tela / (34 * _ESC)) + 1)
        caudas: list[Ponto] = []
        for k in range(n_setas):
            t = k / (n_setas - 1)
            base = (a[0] + (z[0] - a[0]) * t, a[1] + (z[1] - a[1]) * t)
            intensidade = abs(carga.qi + (qj - carga.qi) * t) / q_max
            if paralela:  # carga ao longo da barra: setas curtas ao lado dela
                normal = (-eixo[1], eixo[0]) if -eixo[1] * 0 + eixo[0] >= 0 else (eixo[1], -eixo[0])
                desvio = (10 + 18 * nivel) * _ESC
                ponta = (base[0] + normal[0] * desvio, base[1] + normal[1] * desvio)
                cauda = (ponta[0] - f[0] * 14 * _ESC, ponta[1] - f[1] * 14 * _ESC)
            else:
                folga = (2 + nivel * (h_max + 22)) * _ESC
                altura = (h_min + (h_max - h_min) * intensidade) * _ESC
                ponta = (base[0] - f[0] * folga, base[1] - f[1] * folga)
                cauda = (ponta[0] - f[0] * altura, ponta[1] - f[1] * altura)
            caudas.append(cauda)
            if intensidade > 1e-9 or paralela:
                _seta(d, cauda, ponta, _CARGA, 1, 7)
        d.line(caudas, fill=_CARGA, width=2 * _ESC)
        meio = caudas[len(caudas) // 2]
        fora = (-f[0], -f[1]) if not paralela else (0.0, -1.0)
        rotulos.escrever(
            (meio[0] + fora[0] * 14 * _ESC, meio[1] + fora[1] * 14 * _ESC),
            _texto_da_distribuida(carga),
            _CARGA,
            fora,
        )


def _forca_concentrada(
    d: ImageDraw.ImageDraw,
    rotulos: _Rotulos,
    ponto: Ponto,
    fx: float,
    fy: float,
    cor: str,
    texto: str,
    comprimento: int = 52,
    folga: int = 3,
) -> None:
    f = _unitario((fx, -fy))
    if f == (0.0, 0.0):
        return
    ponta = (ponto[0] - f[0] * folga * _ESC, ponto[1] - f[1] * folga * _ESC)
    cauda = (ponta[0] - f[0] * comprimento * _ESC, ponta[1] - f[1] * comprimento * _ESC)
    _seta(d, cauda, ponta, cor, 2, 10)
    rotulos.escrever(
        (cauda[0] - f[0] * 14 * _ESC, cauda[1] - f[1] * 14 * _ESC), texto, cor, (-f[0], -f[1])
    )


def figura_estrutura(
    r: pp.ResultadoPortico,
    *,
    titulo: str = "Modelo: geometria, apoios e cargas",
    largura_px: int = 1000,
    altura_max_px: int = 620,
) -> ImagemDiagrama:
    """Barras, nós, apoios, rótulas e cargas, com os valores (como a tela do Ftool)."""
    pontos = [(n.x, n.y) for n in r.portico.nos]
    imagem, tela = _nova_tela(pontos, largura_px, altura_max_px, topo=150)
    d = ImageDraw.Draw(imagem)
    rotulos = _Rotulos(d)
    _desenhar_barras(d, r, tela, rotulos=rotulos)
    _desenhar_rotulas(d, r, tela)
    _desenhar_apoios(d, r, tela)
    _desenhar_nos(d, r, tela, rotulos)
    _desenhar_distribuidas(d, r, tela, rotulos)
    geos = {g.resultado.barra.nome: g for g in _geometrias(r)}
    for c in r.portico.cargas_pontuais:
        g = geos[c.barra]
        fx, fy = (c.fx * g.c - c.fy * g.s, c.fx * g.s + c.fy * g.c) if c.local else (c.fx, c.fy)
        texto = f"{numero(math.hypot(fx, fy))} kN"
        _forca_concentrada(
            d,
            rotulos,
            tela.p(*g.ponto(c.distancia_m)),
            fx,
            fy,
            _CARGA,
            (f"{c.nome}: " if c.nome else "") + texto,
        )
    nos = {n.nome: n for n in r.portico.nos}
    for nodal in r.portico.cargas_nodais:
        centro = tela.p(nos[nodal.no].x, nos[nodal.no].y)
        if abs(nodal.fx) > 1e-12 or abs(nodal.fy) > 1e-12:
            texto = f"{numero(math.hypot(nodal.fx, nodal.fy))} kN"
            _forca_concentrada(d, rotulos, centro, nodal.fx, nodal.fy, _CARGA, texto)
        if abs(nodal.mz) > 1e-12:
            _seta_curva(d, centro, nodal.mz, _CARGA)
            rotulos.escrever(
                (centro[0] + 34 * _ESC, centro[1] - 30 * _ESC),
                f"{numero(abs(nodal.mz))} kN·m",
                _CARGA,
            )
    nota = 'Cargas em kN e kN/m; "proj." = por metro da projeção (horizontal ou vertical).'
    if r.portico.peso_proprio:
        nota += " Peso próprio das barras incluído (não desenhado)."
    _cabecalho(d, tela, titulo, nota)
    return _finalizar(imagem, tela, titulo, _legenda_da_estrutura(r))


def _legenda_da_estrutura(r: pp.ResultadoPortico) -> str:
    partes = []
    for rb in r.barras:
        b = rb.barra
        partes.append(
            f"{b.nome} ({b.no_i}–{b.no_j}): {numero(rb.comprimento_m)} m a "
            f"{numero(rb.angulo_graus, 1)}°, {b.secao.nome}"
        )
    apoios = ", ".join(f"{a.no} ({a.tipo})" for a in r.portico.apoios)
    return "Barras: " + "; ".join(partes) + f". Apoios: {apoios}."


# ---------------------------------------------------------------------------------------------
# Figura 2: reações
# ---------------------------------------------------------------------------------------------
def figura_reacoes(
    r: pp.ResultadoPortico,
    *,
    titulo: str = "Reações de apoio",
    largura_px: int = 1000,
    altura_max_px: int = 620,
) -> ImagemDiagrama:
    pontos = [(n.x, n.y) for n in r.portico.nos]
    imagem, tela = _nova_tela(pontos, largura_px, altura_max_px, base=150, lados=150)
    d = ImageDraw.Draw(imagem)
    rotulos = _Rotulos(d)
    _desenhar_barras(d, r, tela, cor=_BARRA_FRACA)
    _desenhar_rotulas(d, r, tela)
    _desenhar_apoios(d, r, tela)
    _desenhar_nos(d, r, tela, rotulos)
    nos = {n.nome: n for n in r.portico.nos}
    medias = _direcao_das_barras(r, tela)
    limite = 0.005
    for reacao in r.reacoes:
        c = tela.p(nos[reacao.no].x, nos[reacao.no].y)
        if abs(reacao.ry) >= limite:
            perto, longe = c[1] + 40 * _ESC, c[1] + 92 * _ESC
            cauda, ponta = (
                ((c[0], longe), (c[0], perto)) if reacao.ry > 0 else ((c[0], perto), (c[0], longe))
            )
            _seta(d, cauda, ponta, _REACAO, 3, 11)
            rotulos.escrever(
                (c[0] + 46 * _ESC, c[1] + 70 * _ESC),
                f"{numero(abs(reacao.ry))} kN",
                _REACAO,
                (1.0, 0.0),
            )
        if abs(reacao.rx) >= limite:
            lado = -1.0 if medias[reacao.no][0] >= 0 else 1.0  # do lado de fora da estrutura
            recuo = 44 if abs(reacao.mz) >= limite else 24  # fora do arco do momento
            perto, longe = c[0] + lado * recuo * _ESC, c[0] + lado * (recuo + 72) * _ESC
            y = c[1] + 8 * _ESC
            de_fora_para_dentro = (reacao.rx > 0) == (lado < 0)
            cauda, ponta = (
                ((longe, y), (perto, y)) if de_fora_para_dentro else ((perto, y), (longe, y))
            )
            _seta(d, cauda, ponta, _REACAO, 3, 11)
            rotulos.escrever(
                ((perto + longe) / 2, y - 16 * _ESC),
                f"{numero(abs(reacao.rx))} kN",
                _REACAO,
                (0.0, -1.0),
            )
        if abs(reacao.mz) >= limite:
            _seta_curva(d, c, reacao.mz, _REACAO, 32)
            rotulos.escrever(
                (c[0] + 30 * _ESC, c[1] - 44 * _ESC),
                f"{numero(abs(reacao.mz))} kN·m",
                _REACAO,
                (0.0, -1.0),
            )
    _cabecalho(d, tela, titulo, "Forças que os apoios fazem na estrutura (sentido real das setas).")
    return _finalizar(imagem, tela, titulo, legenda_das_reacoes(r))


def legenda_das_reacoes(r: pp.ResultadoPortico) -> str:
    partes = []
    for reacao in r.reacoes:
        itens = [
            f"{rotulo} = {numero(valor)} {unidade}"
            for rotulo, valor, unidade, existe in (
                ("Rx", reacao.rx, "kN", True),
                ("Ry", reacao.ry, "kN", True),
                ("Mz", reacao.mz, "kN·m", abs(reacao.mz) > 1e-9),
            )
            if existe
        ]
        partes.append(f"{reacao.no}: " + ", ".join(itens))
    return (
        "Reações (x para a direita, y para cima, momento anti-horário positivo) — "
        + "; ".join(partes)
        + "."
    )


# ---------------------------------------------------------------------------------------------
# Figuras 3 a 6: diagramas sobre as barras
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RotuloDiagrama:
    """Um valor escrito no diagrama: barra, posição ao longo dela e onde fica no desenho."""

    barra: str
    x: float  # m, da ponta i
    valor: float
    texto: str
    base: Ponto  # ponto no eixo da barra (mundo)
    ponta: Ponto  # ponto na curva do diagrama (mundo)


def _valor(ponto: pp.PontoDaBarra, atributo: str) -> float:
    return float(getattr(ponto, atributo) or 0.0)


def curvas_do_diagrama(
    r: pp.ResultadoPortico, esforco: str
) -> list[tuple[str, list[Ponto], list[Ponto]]]:
    """Para cada barra: (nome, pontos do eixo, pontos da curva), no mundo (m).

    A ordenada máxima vale 12 % do tamanho da estrutura; o momento vai para o lado tracionado.
    """
    tipo = DIAGRAMAS[esforco]
    geos = _geometrias(r)
    maior = max(
        (abs(_valor(p, tipo.atributo)) for g in geos for p in g.resultado.pontos), default=0.0
    )
    fator = 0.12 * _tamanho_de_referencia(r) / maior if maior > 0 else 0.0
    saida = []
    for g in geos:
        eixo = [g.ponto(p.x) for p in g.resultado.pontos]
        curva = [
            g.ponto(p.x, tipo.lado * _valor(p, tipo.atributo) * fator) for p in g.resultado.pontos
        ]
        saida.append((g.resultado.barra.nome, eixo, curva))
    return saida


def rotulos_do_diagrama(r: pp.ResultadoPortico, esforco: str) -> list[RotuloDiagrama]:
    """Valores a escrever: pontas de cada barra, extremos internos e os saltos (cargas concentradas)."""
    tipo = DIAGRAMAS[esforco]
    curvas = {nome: (eixo, curva) for nome, eixo, curva in curvas_do_diagrama(r, esforco)}
    maior = max((abs(_valor(p, tipo.atributo)) for rb in r.barras for p in rb.pontos), default=0.0)
    tolerancia = max(1e-4 * maior, 0.005)
    saida: list[RotuloDiagrama] = []
    vistos: list[tuple[str, Ponto]] = []
    for rb in r.barras:
        valores = [_valor(p, tipo.atributo) for p in rb.pontos]
        ultimo = len(valores) - 1
        indices = {0, ultimo}
        k_max = max(range(len(valores)), key=lambda k: valores[k])
        k_min = min(range(len(valores)), key=lambda k: valores[k])
        indices.update(k for k in (k_max, k_min) if 0 < k < ultimo)
        for k in range(ultimo):
            salto = rb.pontos[k + 1].x - rb.pontos[k].x < 1e-6
            if salto and abs(valores[k + 1] - valores[k]) > tolerancia:
                indices.update((k, k + 1))
        eixo, curva = curvas[rb.barra.nome]
        for k in sorted(indices):
            if abs(valores[k]) < tolerancia:
                continue
            texto = numero(valores[k] if tipo.chave != "tensao" else abs(valores[k]))
            if any(t == texto and math.dist(b, eixo[k]) < 1e-6 for t, b in vistos):
                continue  # mesmo valor no mesmo nó, vindo da outra barra
            vistos.append((texto, eixo[k]))
            saida.append(
                RotuloDiagrama(rb.barra.nome, rb.pontos[k].x, valores[k], texto, eixo[k], curva[k])
            )
    return saida


def figura_diagrama(
    r: pp.ResultadoPortico,
    esforco: str,
    *,
    titulo: str | None = None,
    largura_px: int = 1000,
    altura_max_px: int = 620,
) -> ImagemDiagrama:
    """Diagrama de N, V, M ou tensão desenhado sobre as barras, com os valores (como no Ftool)."""
    tipo = DIAGRAMAS[esforco]
    titulo = titulo or f"{tipo.titulo} ({tipo.unidade})"
    curvas = curvas_do_diagrama(r, esforco)
    pontos = [p for _nome, eixo, curva in curvas for p in (*eixo, *curva)]
    imagem, tela = _nova_tela(pontos, largura_px, altura_max_px)
    camada = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(camada)
    for _nome, eixo, curva in curvas:
        poligono = [tela.p(*p) for p in (*curva, *reversed(eixo))]
        if len(poligono) >= 3:
            dc.polygon(poligono, fill=_rgba(tipo.cor, 55))
        for pe, pc in zip(eixo, curva, strict=True):  # hachura perpendicular, como no Ftool
            a, z = tela.p(*pe), tela.p(*pc)
            if math.dist(a, z) > 2 * _ESC:
                dc.line([a, z], fill=_rgba(tipo.cor, 130), width=_ESC)
    imagem.alpha_composite(camada)
    d = ImageDraw.Draw(imagem)
    _desenhar_barras(d, r, tela)
    _desenhar_rotulas(d, r, tela)
    _desenhar_apoios(d, r, tela, cor=_BARRA_FRACA)
    for _nome, _eixo, curva in curvas:
        d.line([tela.p(*p) for p in curva], fill=tipo.cor, width=2 * _ESC, joint="curve")
    rotulos = _Rotulos(d)
    for rot in rotulos_do_diagrama(r, esforco):
        base, ponta = tela.p(*rot.base), tela.p(*rot.ponta)
        fora = _unitario((ponta[0] - base[0], ponta[1] - base[1]))
        if fora == (0.0, 0.0):
            fora = (0.0, -1.0)
        centro = (ponta[0] + fora[0] * 16 * _ESC, ponta[1] + fora[1] * 16 * _ESC)
        rotulos.escrever(centro, rot.texto, tipo.cor, fora)
    _cabecalho(d, tela, titulo, tipo.nota)
    return _finalizar(imagem, tela, titulo, legenda_do_diagrama(r, esforco))


def legenda_do_diagrama(r: pp.ResultadoPortico, esforco: str) -> str:
    tipo = DIAGRAMAS[esforco]
    partes = []
    for rb in r.barras:
        if esforco == "tensao":
            p = rb.tensao_max
            if p is None:
                continue
        else:
            p = max(rb.pontos, key=lambda q: abs(_valor(q, tipo.atributo)))
        valor = _valor(p, tipo.atributo)
        partes.append(
            f"{rb.barra.nome}: {numero(valor)} {tipo.unidade} a {numero(p.x)} m da ponta "
            f"{rb.barra.no_i}"
        )
    rotulo = "máximo" if esforco == "tensao" else "maior valor absoluto"
    texto = f"{tipo.titulo}, {rotulo} por barra — " + "; ".join(partes) + "."
    return f"{texto} {tipo.nota}".strip()


# ---------------------------------------------------------------------------------------------
# Deformada
# ---------------------------------------------------------------------------------------------
def _fator_agradavel(bruto: float) -> float:
    """Arredonda para baixo em 1, 2 ou 5 vezes uma potência de dez."""
    if bruto <= 0:
        return 0.0
    expoente = math.floor(math.log10(bruto))
    base = 10.0**expoente
    for multiplo in (5.0, 2.0, 1.0):
        if multiplo * base <= bruto:
            return multiplo * base
    return base


def fator_da_deformada(r: pp.ResultadoPortico) -> float:
    """Ampliação do desenho: o maior deslocamento vira ~8 % do tamanho da estrutura."""
    maior = max((math.hypot(p.dx, p.dy) for rb in r.barras for p in rb.pontos), default=0.0)
    return _fator_agradavel(0.08 * _tamanho_de_referencia(r) / maior) if maior > 1e-15 else 0.0


def figura_deformada(
    r: pp.ResultadoPortico,
    *,
    titulo: str = "Deformada (deslocamentos em mm)",
    largura_px: int = 1000,
    altura_max_px: int = 620,
) -> ImagemDiagrama:
    fator = fator_da_deformada(r)
    geos = _geometrias(r)
    deformadas = [
        [
            (px + p.dx * fator, py + p.dy * fator)
            for p, (px, py) in ((p, g.ponto(p.x)) for p in g.resultado.pontos)
        ]
        for g in geos
    ]
    originais = [(n.x, n.y) for n in r.portico.nos]
    imagem, tela = _nova_tela(
        [*originais, *(p for linha in deformadas for p in linha)], largura_px, altura_max_px
    )
    d = ImageDraw.Draw(imagem)
    for g in geos:  # estrutura original tracejada
        a = tela.p(*g.ponto(0.0))
        z = tela.p(*g.ponto(g.resultado.comprimento_m))
        partes = max(int(math.dist(a, z) / (8 * _ESC)), 1)
        for k in range(0, partes, 2):
            t0, t1 = k / partes, min((k + 1) / partes, 1.0)
            d.line(
                [
                    (a[0] + (z[0] - a[0]) * t0, a[1] + (z[1] - a[1]) * t0),
                    (a[0] + (z[0] - a[0]) * t1, a[1] + (z[1] - a[1]) * t1),
                ],
                fill=_BARRA_FRACA,
                width=2 * _ESC,
            )
    _desenhar_apoios(d, r, tela, cor=_BARRA_FRACA)
    for linha in deformadas:
        d.line([tela.p(*p) for p in linha], fill=COR_FLECHA, width=3 * _ESC, joint="curve")
    rotulos = _Rotulos(d)
    if fator > 0:
        geo_max, p_max = max(
            ((g, p) for g in geos for p in g.resultado.pontos),
            key=lambda gp: math.hypot(gp[1].dx, gp[1].dy),
        )
        bx, by = geo_max.ponto(p_max.x)
        alvo = tela.p(bx + p_max.dx * fator, by + p_max.dy * fator)
        raio = 4 * _ESC
        d.ellipse([alvo[0] - raio, alvo[1] - raio, alvo[0] + raio, alvo[1] + raio], fill=COR_FLECHA)
        fora = _unitario((p_max.dx, -p_max.dy))
        rotulos.escrever(
            (alvo[0] + fora[0] * 22 * _ESC, alvo[1] + fora[1] * 22 * _ESC),
            f"δ = {numero(math.hypot(p_max.dx, p_max.dy) * 1e3)} mm",
            COR_FLECHA,
            fora,
        )
        for g in geos:
            pf = g.resultado.flecha_max
            if abs(pf.flecha) * 1e3 < 0.01 or 0 in (pf.x, g.resultado.comprimento_m - pf.x):
                continue
            bx, by = g.ponto(pf.x)
            alvo = tela.p(bx + pf.dx * fator, by + pf.dy * fator)
            normal = _unitario((-g.s * pf.flecha, -g.c * pf.flecha))  # lado para onde a barra cede
            rotulos.escrever(
                (alvo[0] + normal[0] * 26 * _ESC, alvo[1] + normal[1] * 26 * _ESC),
                f"f = {numero(abs(pf.flecha) * 1e3)} mm",
                _TEXTO,
                normal,
            )
    nota = (
        f"Desenho ampliado {numero(fator, 0)}×; os valores são os reais. δ = deslocamento total; "
        "f = flecha da barra em relação à reta entre as suas pontas."
        if fator > 0
        else "Sem deslocamentos."
    )
    _cabecalho(d, tela, titulo, nota)
    return _finalizar(imagem, tela, titulo, legenda_da_deformada(r))


def legenda_da_deformada(r: pp.ResultadoPortico) -> str:
    partes = []
    for rb in r.barras:
        pd = rb.deslocamento_max
        pf = rb.flecha_max
        partes.append(
            f"{rb.barra.nome}: deslocamento máximo {numero(math.hypot(pd.dx, pd.dy) * 1e3)} mm, "
            f"flecha {numero(abs(pf.flecha) * 1e3)} mm (L/{_l_sobre(rb.comprimento_m, pf.flecha)})"
        )
    return "Deformada — " + "; ".join(partes) + "."


def _l_sobre(comprimento: float, flecha: float) -> str:
    return "∞" if abs(flecha) < 1e-12 else numero(comprimento / abs(flecha), 0)


# ---------------------------------------------------------------------------------------------
# Conjunto
# ---------------------------------------------------------------------------------------------
def figuras_do_portico(
    r: pp.ResultadoPortico,
    *,
    prefixo: str = "",
    tensao: bool = True,
    caso: str = "",
    deformada: pp.ResultadoPortico | None = None,
    caso_deformada: str = "",
) -> list[ImagemDiagrama]:
    """Estrutura, reações, N, V, M, tensão (se a seção tiver W) e deformada, nessa ordem.

    ``caso`` (por exemplo "ELU") vai no título e na legenda de cada figura; com ``deformada``, a
    deformada sai desse outro resultado (o de serviço, ``caso_deformada``).
    """
    antes = f"{prefixo} — " if prefixo else ""

    def titulo(texto: str, rotulo: str) -> str:
        return f"{antes}{texto}" + (f", {rotulo}" if rotulo else "")

    def com_caso(figura: ImagemDiagrama, rotulo: str) -> ImagemDiagrama:
        return replace(figura, legenda=f"{rotulo}. {figura.legenda}") if rotulo else figura

    figuras = [
        figura_estrutura(r, titulo=titulo("Modelo: geometria, apoios e cargas", caso)),
        figura_reacoes(r, titulo=titulo("Reações de apoio", caso)),
    ]
    chaves = ["N", "V", "M"]
    if tensao and any(rb.tensao_max is not None for rb in r.barras):
        chaves.append("tensao")
    for chave in chaves:
        tipo = DIAGRAMAS[chave]
        figuras.append(
            figura_diagrama(r, chave, titulo=titulo(f"{tipo.titulo} ({tipo.unidade})", caso))
        )
    rotulo_def = caso_deformada if deformada is not None else caso
    figuras.append(
        figura_deformada(
            deformada or r, titulo=titulo("Deformada (deslocamentos em mm)", rotulo_def)
        )
    )
    return [
        com_caso(f, rotulo_def if k == len(figuras) - 1 else caso) for k, f in enumerate(figuras)
    ]
