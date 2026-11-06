"""A seção em escala e, alinhados a ela, os diagramas de σ, τ e von Mises.

Cada diagrama tem a altura da seção: o que está na mesma linha é o mesmo ponto. A seção vem colorida
pela tensão, com vermelho para tração e azul para compressão, as cores dos outros desenhos. Os limites
entram tracejados, para se ver de longe quanto falta.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, desenho_dispensado, figura_final
from core.geometria_da_secao import Geometria, Tensoes, linha_neutra

ESC = dg.ESC
_FUNDO = "#ffffff"
_TEXTO = "#172033"
_FRACO = "#64748b"
_LINHA = "#334155"
_TRACAO = (194, 65, 93)
_COMPRESSAO = (11, 110, 153)
_NEUTRO = (241, 245, 249)
_TAU = "#7c3aed"
_MISES = "#b45309"
_LIMITE = "#475569"
_LN = "#0f172a"

_LARGURA = 540
_TOPO = 58
_ALTURA_MAXIMA = 250
_ALTURA_MINIMA = 130
_LARGURA_DA_SECAO = 132
#: Centro da seção e os três painéis, em px de tela.
_X_SECAO = 86
_PAINEIS = ((196, 288), (306, 394), (412, 500))
_FIM_DA_LINHA_NEUTRA = 506


@dataclass(frozen=True)
class DadosDaFlexao:
    """Os números do desenho. Momento em kN·m, forças em kN, medidas em mm e tensões em MPa."""

    geometria: Geometria | None
    tensoes: Tensoes
    sigma_sup: float
    sigma_inf: float
    limite: float
    momento: float
    cortante: float
    normal: float
    legenda: str
    titulo: str = "Tensões na seção"
    limite_tau: float = 0.0


def _n(valor: float, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto.replace(".", ",").replace("-", "−")


def _texto(
    d: ImageDraw.ImageDraw,
    posicao: tuple[float, float],
    texto: str,
    *,
    cor: str = _TEXTO,
    tamanho: int = 11,
    ancora: str = "mm",
) -> None:
    d.text(posicao, texto, fill=cor, font=_fonte(tamanho * ESC), anchor=ancora)


def _cor_da_tensao(valor: float, referencia: float) -> tuple[int, int, int]:
    """Do neutro ao forte, com vermelho na tração e azul na compressão."""
    fracao = min(abs(valor) / referencia, 1.0) if referencia > 0 else 0.0
    alvo = _TRACAO if valor >= 0 else _COMPRESSAO
    return tuple(round(n + (a - n) * fracao) for n, a in zip(_NEUTRO, alvo, strict=True))  # type: ignore[return-value]


def _hex(cor: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*cor)


@dataclass(frozen=True)
class _Tela:
    x_meio: float
    y_meio: float
    esc_x: float
    esc_y: float

    def px(self, x: float, y: float) -> tuple[float, float]:
        return (self.x_meio + x * self.esc_x, self.y_meio - y * self.esc_y)


def _secao(
    imagem: Image.Image,
    d: ImageDraw.ImageDraw,
    dados: DadosDaFlexao,
    tela: _Tela,
    y_topo: float,
    y_base: float,
) -> None:
    """A seção colorida pela tensão, faixa por faixa, com o contorno por cima."""
    referencia = max(abs(dados.sigma_sup), abs(dados.sigma_inf), 1e-9)
    y0 = tela.px(0.0, y_topo)[1]
    y1 = tela.px(0.0, y_base)[1]
    if dados.geometria is None:
        x0 = tela.x_meio - 62 * ESC
        x1 = tela.x_meio + 62 * ESC
        passos = max(int(y1 - y0), 1)
        for k in range(passos + 1):
            valor = dados.sigma_sup + (dados.sigma_inf - dados.sigma_sup) * k / passos
            d.line([(x0, y0 + k), (x1, y0 + k)], fill=_cor_da_tensao(valor, referencia))
        dg.tracejado(d, (x0, y0), (x1, y0), _LINHA, largura=ESC, traco=5 * ESC)
        dg.tracejado(d, (x0, y1), (x1, y1), _LINHA, largura=ESC, traco=5 * ESC)
        _texto(
            d, (tela.x_meio, y0 + (y1 - y0) * 0.3), "forma não", cor=_LINHA, tamanho=12, ancora="md"
        )
        _texto(
            d, (tela.x_meio, y0 + (y1 - y0) * 0.3), "informada", cor=_LINHA, tamanho=12, ancora="ma"
        )
        return
    g = dados.geometria
    camada = Image.new("RGB", imagem.size, _FUNDO)
    pintura = ImageDraw.Draw(camada)
    passos = max(int(y1 - y0), 1)
    for k in range(passos + 1):
        valor = dados.sigma_sup + (dados.sigma_inf - dados.sigma_sup) * k / passos
        pintura.line([(0, y0 + k), (imagem.width, y0 + k)], fill=_cor_da_tensao(valor, referencia))
    mascara = Image.new("L", imagem.size, 0)
    traco = ImageDraw.Draw(mascara)
    for contorno in g.cheios:
        traco.polygon([tela.px(x, y) for x, y in contorno], fill=255)
    for contorno in g.vazados:
        traco.polygon([tela.px(x, y) for x, y in contorno], fill=0)
    for externo, interno in g.aneis:
        for raio, tom in ((externo, 255), (interno, 0)):
            if raio > 0:
                (xa, ya), (xb, yb) = tela.px(-raio, raio), tela.px(raio, -raio)
                traco.ellipse([xa, ya, xb, yb], fill=tom)
    imagem.paste(camada, (0, 0), mascara)
    for contorno in (*g.cheios, *g.vazados):
        pontos = [tela.px(x, y) for x, y in contorno]
        d.line([*pontos, pontos[0]], fill=_LINHA, width=2 * ESC, joint="curve")
    for externo, interno in g.aneis:
        for raio in (externo, interno):
            if raio > 0:
                (xa, ya), (xb, yb) = tela.px(-raio, raio), tela.px(raio, -raio)
                d.ellipse([xa, ya, xb, yb], outline=_LINHA, width=2 * ESC)
    # G: o centro geométrico.
    gx, gy = tela.px(0.0, 0.0)
    raio = 4 * ESC
    d.ellipse([gx - raio, gy - raio, gx + raio, gy + raio], outline=_LINHA, width=ESC)
    d.line([(gx - raio * 1.8, gy), (gx + raio * 1.8, gy)], fill=_LINHA, width=ESC)
    d.line([(gx, gy - raio * 1.8), (gx, gy + raio * 1.8)], fill=_LINHA, width=ESC)


def _painel(
    d: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    ys: np.ndarray,
    valores: np.ndarray,
    y_tela,
    cor: str,
    titulo: str,
    limite: float,
    texto_max: str,
    indice_max: int,
) -> None:
    """Um diagrama sem sinal, do zero à esquerda, com o limite tracejado."""
    largura = x1 - x0
    escala_maior = max(float(valores.max()), limite, 1e-9) * 1.08
    pontos = [
        (x0 + v / escala_maior * largura, y_tela(y)) for y, v in zip(ys, valores, strict=True)
    ]
    topo, base = y_tela(float(ys[0])), y_tela(float(ys[-1]))
    d.polygon([(x0, topo), *pontos, (x0, base)], fill=_claro(cor))
    d.line(pontos, fill=cor, width=2 * ESC)
    d.line([(x0, topo), (x0, base)], fill=_LINHA, width=ESC)
    _texto(d, ((x0 + x1) / 2, _TOPO * ESC - 26 * ESC), titulo, cor=cor, tamanho=13)
    if limite > 0:
        x_limite = x0 + limite / escala_maior * largura
        dg.tracejado(
            d,
            (x_limite, topo - 6 * ESC),
            (x_limite, base + 6 * ESC),
            _LIMITE,
            largura=ESC,
            traco=4 * ESC,
        )
        _texto(d, (x_limite, base + 30 * ESC), _n(limite, 0), cor=_LIMITE, tamanho=13)
    x_pico, y_pico = pontos[indice_max]
    raio = 3.5 * ESC
    d.ellipse([x_pico - raio, y_pico - raio, x_pico + raio, y_pico + raio], fill=cor)
    _texto(d, ((x0 + x1) / 2, topo - 11 * ESC), texto_max, cor=cor, tamanho=13)


def _claro(cor: str, fracao: float = 0.82) -> str:
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c + (255 - c) * fracao):02x}" for c in (r, g, b))


def _painel_sigma(
    d: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    dados: DadosDaFlexao,
    y_tela,
    y_topo: float,
    y_base: float,
) -> None:
    """σ com sinal: a reta da seção, com tração à direita e compressão à esquerda."""
    meio = (x0 + x1) / 2
    meia = (x1 - x0) / 2
    maior = max(abs(dados.sigma_sup), abs(dados.sigma_inf), dados.limite, 1e-9) * 1.08
    topo, base = y_tela(y_topo), y_tela(y_base)

    def x_de(sigma: float) -> float:
        return meio + sigma / maior * meia

    ln = linha_neutra(dados.sigma_sup, dados.sigma_inf, y_topo, y_base)
    if ln is None:
        cor = _hex(_cor_da_tensao(dados.sigma_sup + dados.sigma_inf, 1e-9))
        d.polygon(
            [
                (meio, topo),
                (x_de(dados.sigma_sup), topo),
                (x_de(dados.sigma_inf), base),
                (meio, base),
            ],
            fill=_claro(cor, 0.55),
        )
    else:
        y_ln = y_tela(ln)
        for sigma, y in ((dados.sigma_sup, topo), (dados.sigma_inf, base)):
            cor = _hex(_cor_da_tensao(sigma, 1e-9))
            d.polygon([(meio, y_ln), (x_de(sigma), y), (meio, y)], fill=_claro(cor, 0.55))
    d.line(
        [(x_de(dados.sigma_sup), topo), (x_de(dados.sigma_inf), base)], fill=_LINHA, width=2 * ESC
    )
    d.line([(meio, topo), (meio, base)], fill=_LINHA, width=ESC)
    _texto(d, (meio, _TOPO * ESC - 26 * ESC), "σ (MPa)", cor=_LINHA, tamanho=13)
    if dados.limite > 0:
        for lado in (-1.0, 1.0):
            x = meio + lado * dados.limite / maior * meia
            dg.tracejado(
                d, (x, topo - 6 * ESC), (x, base + 6 * ESC), _LIMITE, largura=ESC, traco=4 * ESC
            )
        _texto(
            d,
            (x_de(dados.limite), base + 30 * ESC),
            f"±{_n(dados.limite, 0)}",
            cor=_LIMITE,
            tamanho=12,
        )
    for sigma, y, deslocamento in ((dados.sigma_sup, topo, -11), (dados.sigma_inf, base, 11)):
        cor = _hex(_cor_da_tensao(sigma, 1e-9))
        _texto(
            d,
            (min(max(x_de(sigma), x0 + 16 * ESC), x1 - 16 * ESC), y + deslocamento * ESC),
            _n(sigma),
            cor=cor,
            tamanho=13,
        )


def figura_da_flexao(dados: DadosDaFlexao) -> ImagemDiagrama:
    """A seção e os diagramas alinhados. Sem a forma, só a reta de σ e o que dela sai."""
    if desenho_dispensado():
        return ImagemDiagrama(dados.titulo, dados.legenda, b"", 0, 0)
    y_topo = float(dados.tensoes.y[0])
    y_base = float(dados.tensoes.y[-1])
    altura_mm = y_topo - y_base
    if dados.geometria is None:
        largura_mm = 0.0
        esc_natural = _ALTURA_MAXIMA * ESC / altura_mm
        esc_x = esc_y = esc_natural
    else:
        xa, xb = dados.geometria.extremos_x()
        largura_mm = xb - xa
        esc_natural = min(_ALTURA_MAXIMA * ESC / altura_mm, _LARGURA_DA_SECAO * ESC / largura_mm)
        esc_x = esc_natural
        # Chapa deitada: a altura ganha escala própria, para os diagramas não virarem uma linha.
        esc_y = max(esc_natural, _ALTURA_MINIMA * ESC / altura_mm)
    altura_px = altura_mm * esc_y
    imagem = Image.new("RGB", (_LARGURA * ESC, round(_TOPO * ESC + altura_px + 92 * ESC)), _FUNDO)
    d = ImageDraw.Draw(imagem)
    x_secao: float = _X_SECAO * ESC
    if dados.geometria is not None:
        x_secao = _X_SECAO * ESC - (xa + xb) / 2 * esc_x
    y_meio = _TOPO * ESC + y_topo * esc_y
    tela = _Tela(x_secao, y_meio, esc_x, esc_y)

    def y_tela(y: float) -> float:
        return y_meio - y * esc_y

    _secao(imagem, d, dados, tela, y_topo, y_base)
    _texto(d, (_X_SECAO * ESC, _TOPO * ESC - 26 * ESC), "Seção", cor=_LINHA, tamanho=13)
    topo, base = y_tela(y_topo), y_tela(y_base)

    if dados.geometria is not None:
        x_cota = _X_SECAO * ESC + largura_mm / 2 * esc_x + 10 * ESC
        d.line([(x_cota, topo), (x_cota, base)], fill=_FRACO, width=ESC)
        for y in (topo, base):
            d.line([(x_cota - 4 * ESC, y), (x_cota + 4 * ESC, y)], fill=_FRACO, width=ESC)
        _texto(
            d,
            (x_cota + 5 * ESC, topo + 8 * ESC),
            _n(altura_mm),
            cor=_FRACO,
            tamanho=12,
            ancora="lm",
        )
        y_cota = base + 14 * ESC
        xa_px, xb_px = (
            _X_SECAO * ESC - largura_mm / 2 * esc_x,
            _X_SECAO * ESC + largura_mm / 2 * esc_x,
        )
        d.line([(xa_px, y_cota), (xb_px, y_cota)], fill=_FRACO, width=ESC)
        for x in (xa_px, xb_px):
            d.line([(x, y_cota - 4 * ESC), (x, y_cota + 4 * ESC)], fill=_FRACO, width=ESC)
        _texto(d, (_X_SECAO * ESC, y_cota + 10 * ESC), _n(largura_mm), cor=_FRACO, tamanho=13)

    faixas = _PAINEIS if dados.tensoes.tem_tau else ((230, 470), (0, 0), (0, 0))
    x0, x1 = faixas[0][0] * ESC, faixas[0][1] * ESC
    _painel_sigma(d, x0, x1, dados, y_tela, y_topo, y_base)
    t = dados.tensoes
    if t.tem_tau:
        x0, x1 = faixas[1][0] * ESC, faixas[1][1] * ESC
        indice = int(np.argmax(t.tau))
        _painel(
            d,
            x0,
            x1,
            t.y,
            t.tau,
            y_tela,
            _TAU,
            "τ (MPa)",
            dados.limite_tau,
            f"{_n(t.tau_max)}",
            indice,
        )
        x0, x1 = faixas[2][0] * ESC, faixas[2][1] * ESC
        _painel(
            d,
            x0,
            x1,
            t.y,
            t.mises,
            y_tela,
            _MISES,
            "von Mises",
            dados.limite,
            f"{_n(t.mises_max)}",
            t.indice_critico,
        )

    ln = linha_neutra(dados.sigma_sup, dados.sigma_inf, y_topo, y_base)
    fim = (faixas[0][1] if not t.tem_tau else _FIM_DA_LINHA_NEUTRA) * ESC
    if ln is not None:
        y = y_tela(ln)
        dg.tracejado(d, (8 * ESC, y), (fim, y), _LN, largura=ESC, traco=6 * ESC)
        _texto(d, (fim + 4 * ESC, y), "LN", cor=_LN, tamanho=12, ancora="lm")
    esforcos = f"M = {_n(dados.momento, 2)} kN·m   ·   V = {_n(dados.cortante, 2)} kN   ·   N = {_n(dados.normal, 2)} kN"
    _texto(d, (262 * ESC, base + 54 * ESC), esforcos, cor=_TEXTO, tamanho=13)
    return figura_final(imagem, dados.titulo, dados.legenda)
