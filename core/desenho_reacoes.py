"""Planta de locação dos pés com as reações de um caso de carga (Reações nas bases).

Nos eixos da fundação (X e Y na planta, Z para cima): cada pé no seu lugar, com o rótulo, as
linhas de eixo e as distâncias entre elas; a força vertical N de um caso como um círculo de área
proporcional a ela (compressão em azul, arrancamento em vermelho), a horizontal H como seta e o
momento, quando há. São as ações da estrutura na fundação, características, sem combinar.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core import reacoes_nas_bases as rb
from core.beam_charts import ImagemDiagrama, _fonte, figura_final

ESC = dg.ESC
_COMPRESSAO = "#93c5fd"
_COMPRESSAO_BORDA = "#1d4ed8"
_ARRANCAMENTO = "#fca5a5"
_ARRANCAMENTO_BORDA = "#b91c1c"
_HORIZONTAL = "#b45309"
_EIXO = "#94a3b8"
_PLACA = "#475569"
_LARGURA_PX, _ALTURA_PX = 1000, 620

Ponto = tuple[float, float]


def _n(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",").replace("-0,0", "0,0")


def _distintos(valores: list[float], tolerancia: float) -> list[float]:
    saida: list[float] = []
    for v in sorted(valores):
        if not saida or v - saida[-1] > tolerancia:
            saida.append(v)
    return saida


def figura_das_reacoes(r: rb.ReacoesNasBases, caso: str) -> ImagemDiagrama | None:
    """A planta com as reações do ``caso``; ``None`` quando nenhum pé tem posição."""
    pes = [
        (pe, rb.nos_eixos(pe.ponto, r.eixo_vertical, rb.EIXOS_FUNDACAO))
        for pe in r.pes
        if pe.ponto is not None
    ]
    if not pes:
        return None
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    xs = [p[0] for _, p in pes]
    ys = [p[1] for _, p in pes]
    vao = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    sobra = 0.22 * vao + 0.4
    tela = dg.Tela(
        [(min(xs) - sobra, -(max(ys) + sobra)), (max(xs) + sobra, -(min(ys) - sobra))],
        (90, 110, 640, 570),
        0.0,
    )

    def p(x: float, y: float) -> Ponto:
        return tela(x, -y)

    fonte = _fonte(11 * ESC)
    negrito = _fonte(13 * ESC)
    # ------------------------------------------------------------------ linhas de eixo e cotas
    tolerancia = 0.02 * vao
    eixos_x = _distintos(xs, tolerancia)
    eixos_y = _distintos(ys, tolerancia)
    y_baixo, y_cima = min(ys) - sobra * 0.75, max(ys) + sobra * 0.75
    x_esq, x_dir = min(xs) - sobra * 0.75, max(xs) + sobra * 0.75
    for x in eixos_x:
        dg.traco_ponto(dr, p(x, y_baixo), p(x, y_cima), _EIXO)
    for y in eixos_y:
        dg.traco_ponto(dr, p(x_esq, y), p(x_dir, y), _EIXO)
    for a, b in zip(eixos_x, eixos_x[1:], strict=False):
        dg.cota_alinhada(
            dr, p(a, y_cima), p(b, y_cima), (0.0, -1.0), f"{_n(b - a, 2)} m", 6 * ESC, fundo=True
        )
    for a, b in zip(eixos_y, eixos_y[1:], strict=False):
        dg.cota_alinhada(
            dr, p(x_esq, a), p(x_esq, b), (-1.0, 0.0), f"{_n(b - a, 2)} m", 6 * ESC, fundo=True
        )
    # ------------------------------------------------------------------ as reações do caso
    acoes = {pe.rotulo: r.acao(pe.rotulo, caso) for pe, _ in pes}
    vetores = {}
    for rotulo, acao in acoes.items():
        if acao is None:
            continue
        f = rb.nos_eixos(acao.forca_kN, r.eixo_vertical, rb.EIXOS_FUNDACAO)
        mom = rb.nos_eixos(acao.momento_kNm, r.eixo_vertical, rb.EIXOS_FUNDACAO)
        vetores[rotulo] = (-f[2], (f[0], f[1]), math.hypot(mom[0], mom[1]))
    maior_n = max((abs(v[0]) for v in vetores.values()), default=0.0) or 1.0
    maior_h = max((math.hypot(*v[1]) for v in vetores.values()), default=0.0) or 1.0
    raio_max = 30 * ESC
    for pe, (x, y, _z) in pes:
        c = p(x, y)
        valores = vetores.get(pe.rotulo)
        if valores is not None:
            n, (hx, hy), m = valores
            raio = max(raio_max * math.sqrt(abs(n) / maior_n), 6 * ESC)
            cor, borda = (
                (_COMPRESSAO, _COMPRESSAO_BORDA) if n >= 0 else (_ARRANCAMENTO, _ARRANCAMENTO_BORDA)
            )
            dr.ellipse(
                [c[0] - raio, c[1] - raio, c[0] + raio, c[1] + raio],
                fill=cor, outline=borda, width=2 * ESC,
            )  # fmt: skip
        # a placa de base
        lado = 7 * ESC
        dr.rectangle([c[0] - lado, c[1] - lado, c[0] + lado, c[1] + lado], fill="#ffffff", outline=_PLACA, width=2 * ESC)  # fmt: skip
        dr.line([(c[0] - lado, c[1]), (c[0] + lado, c[1])], fill=_PLACA, width=ESC)
        dr.line([(c[0], c[1] - lado), (c[0], c[1] + lado)], fill=_PLACA, width=ESC)
        dg.rotulo(dr, c, (-1.0, -1.0), 22 * ESC, pe.rotulo, dg.COR_TEXTO, negrito, fundo=True)
        if valores is None:
            dg.rotulo(dr, c, (0.0, 1.0), 14 * ESC, "sem valor", dg.COR_COTA, fonte, fundo=True)
            continue
        n, (hx, hy), m = valores
        h = math.hypot(hx, hy)
        if h > 1e-6:
            direcao = (hx, -hy)
            inicio = dg.mais(c, direcao, 9 * ESC)
            fim = dg.mais(c, direcao, 9 * ESC + 46 * ESC * h / maior_h)
            dg.seta(dr, inicio, fim, _HORIZONTAL, largura=3 * ESC, ponta_px=11 * ESC)
            dg.rotulo(dr, fim, direcao, 4 * ESC, f"H {_n(h)}", _HORIZONTAL, fonte, fundo=True)
        texto = f"N {_n(n)}" + (f"\nM {_n(m, 2)}" if m > 0.005 else "")
        dg.rotulo(
            dr, c, (0.0, 1.0), raio_max * 0.4 + 18 * ESC, texto, dg.COR_TEXTO, fonte, fundo=True
        )
    # ------------------------------------------------------------------ eixos da fundação
    origem = (40 * ESC, 560 * ESC)
    dg.eixos_da_peca(dr, origem, tela, ("X", "Y"))
    # ------------------------------------------------------------------ legenda
    itens: list[tuple[str, str, str]] = [
        ("ponto", _COMPRESSAO_BORDA, "N de compressão (a área do círculo cresce com N)"),
        ("ponto", _ARRANCAMENTO_BORDA, "N de arrancamento (puxa a fundação)"),
        ("seta", _HORIZONTAL, "H: força horizontal na fundação"),
        ("eixo", _EIXO, "Linhas de eixo dos pés"),
        ("", dg.COR_TEXTO, ""),
        ("", dg.COR_TEXTO, f"Caso: {caso}"),
        ("", dg.COR_COTA, "Valores característicos, sem combinar:"),
        ("", dg.COR_COTA, "N e H em kN; M (horizontal) em kN·m."),
        ("", dg.COR_COTA, "Ação da estrutura na fundação."),
    ]
    if not vetores:
        itens.append(("", dg.COR_COTA, "Este caso não tem valor em nenhum pé."))
    dg.legenda(dr, 680 * ESC, 110 * ESC, itens)
    titulo = f"Reações nas bases — {caso}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        f"Planta de locação dos {len(pes)} pés nos eixos da fundação (X e Y na planta, Z para "
        "cima). Distâncias entre eixos em m.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = f"Planta dos pés com as reações do caso {caso} (características, sem combinar)."
    return figura_final(imagem, titulo, legenda)
