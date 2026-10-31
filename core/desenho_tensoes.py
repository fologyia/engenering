"""Elementos de tensão do estado plano (Análise estática e Círculo de Mohr).

Lado a lado: o elemento nos eixos x e y; girado do ângulo pedido (quando há); nas direções
principais (σ1 e σ2, sem cisalhamento) e no cisalhamento máximo (τmax com a tensão média nas
faces). Cada face leva a sua seta — tração para fora (azul), compressão para dentro (vermelho),
cisalhamento ao longo da face (roxo) — com o valor em MPa, e o ângulo é medido do eixo x no
sentido anti-horário. Convenção: τxy positivo puxa a face +x para +y.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from core import desenho_girado as dg
from core import mohr_analysis as mohr
from core.beam_charts import ImagemDiagrama, _fonte

ESC = dg.ESC
_TRACAO = "#1d4ed8"
_COMPRESSAO = "#b91c1c"
_CISALHAMENTO = "#7c3aed"
_ELEMENTO = "#e2e8f0"
_ALTURA_PX = 400

Ponto = tuple[float, float]


@dataclass(frozen=True)
class Elemento:
    titulo: str
    angulo_graus: float
    sigma_x: float  # na face x' (normal a 0° + ângulo)
    sigma_y: float
    tau: float
    nomes: tuple[str, str, str] = ("σx", "σy", "τxy")


def _n(valor: float) -> str:
    texto = f"{valor:.1f}".replace(".", ",")
    return "0,0" if texto == "-0,0" else texto


def _direcao(angulo_graus: float) -> Ponto:
    """A direção do ângulo (anti-horário a partir de x) na tela, com y para baixo."""
    a = math.radians(angulo_graus)
    return (math.cos(a), -math.sin(a))


def _elemento(dr: ImageDraw.ImageDraw, e: Elemento, centro: Ponto, maior: float) -> None:
    lado = 46 * ESC
    cx, cy = centro
    ux, vy = _direcao(e.angulo_graus), _direcao(e.angulo_graus + 90.0)
    cantos = [
        (cx + s * ux[0] * lado + t * vy[0] * lado, cy + s * ux[1] * lado + t * vy[1] * lado)
        for s, t in ((1, 1), (-1, 1), (-1, -1), (1, -1))
    ]
    dr.polygon(cantos, fill=_ELEMENTO, outline=dg.COR_LINHA, width=2 * ESC)
    fonte = _fonte(11 * ESC)
    # eixos do elemento
    for direcao, nome in (
        (ux, "x'" if e.angulo_graus else "x"),
        (vy, "y'" if e.angulo_graus else "y"),
    ):
        dg.tracejado(
            dr,
            centro,
            dg.mais(centro, direcao, lado * 0.8),
            dg.COR_COTA,
            largura=ESC,
            traco=3 * ESC,
        )
        dg.rotulo(
            dr,
            dg.mais(centro, direcao, lado * 0.8),
            direcao,
            3 * ESC,
            nome,
            dg.COR_COTA,
            _fonte(10 * ESC),
        )

    def comprimento(valor: float) -> float:
        return 12 * ESC + 34 * ESC * abs(valor) / maior if maior > 0 else 12 * ESC

    def normal(direcao: Ponto, valor: float, nome: str, rotular: bool) -> None:
        if abs(valor) < 1e-9:
            return
        face = dg.mais(centro, direcao, lado)
        tamanho = comprimento(valor)
        if valor > 0:  # tração: para fora da face
            a, b, cor = (
                dg.mais(face, direcao, 4 * ESC),
                dg.mais(face, direcao, 4 * ESC + tamanho),
                _TRACAO,
            )
        else:  # compressão: chegando na face
            a, b, cor = (
                dg.mais(face, direcao, 4 * ESC + tamanho),
                dg.mais(face, direcao, 4 * ESC),
                _COMPRESSAO,
            )
        dg.seta(dr, a, b, cor, largura=3 * ESC, ponta_px=11 * ESC)
        if rotular:
            ponta_de_fora = a if valor < 0 else b
            dg.rotulo(
                dr, ponta_de_fora, direcao, 5 * ESC, f"{nome} = {_n(valor)}", cor, fonte, fundo=True
            )

    def cisalhamento(direcao: Ponto, ao_longo: Ponto, valor: float, rotular: bool) -> None:
        if abs(valor) < 1e-9:
            return
        # na metade da face para onde aponta, com a ponta indo para o canto (como nos livros)
        sentido = ao_longo if valor > 0 else (-ao_longo[0], -ao_longo[1])
        meio = dg.mais(dg.mais(centro, direcao, lado + 7 * ESC), sentido, lado * 0.5)
        tamanho = min(comprimento(valor) * 0.9, lado * 0.9)
        a, b = dg.mais(meio, sentido, -tamanho / 2), dg.mais(meio, sentido, tamanho / 2)
        dg.seta(dr, a, b, _CISALHAMENTO, largura=2 * ESC, ponta_px=9 * ESC)
        if rotular:
            dg.rotulo(
                dr,
                b,
                sentido,
                4 * ESC,
                f"{e.nomes[2]} = {_n(abs(valor))}",
                _CISALHAMENTO,
                fonte,
                fundo=True,
            )

    menos_u, menos_v = (-ux[0], -ux[1]), (-vy[0], -vy[1])
    normal(ux, e.sigma_x, e.nomes[0], True)
    normal(menos_u, e.sigma_x, e.nomes[0], False)
    normal(vy, e.sigma_y, e.nomes[1], True)
    normal(menos_v, e.sigma_y, e.nomes[1], False)
    # τ positivo: na face +x' aponta para +y'; na +y', para +x' (e o contrário nas opostas)
    cisalhamento(ux, vy, e.tau, True)
    cisalhamento(menos_u, menos_v, e.tau, False)
    cisalhamento(vy, ux, e.tau, False)
    cisalhamento(menos_v, menos_u, e.tau, False)
    # o ângulo a partir do eixo x
    if abs(e.angulo_graus) > 0.05:
        dg.traco_ponto(dr, centro, dg.mais(centro, (1.0, 0.0), lado * 1.25), dg.COR_COTA)
        meio = dg.arco_entre(dr, centro, lado * 1.05, (1.0, 0.0), ux, dg.COR_COTA)
        texto = f"{_n(e.angulo_graus)}°"
        dg.rotulo(
            dr,
            dg.mais(centro, meio, lado * 1.05),
            meio,
            4 * ESC,
            texto,
            dg.COR_TEXTO,
            fonte,
            fundo=True,
        )


def _no_intervalo(angulo_graus: float) -> float:
    """O mesmo elemento com o ângulo em (−90°, 90°]: girar 180° não muda o elemento."""
    angulo = (angulo_graus + 90.0) % 180.0 - 90.0
    return 90.0 if angulo == -90.0 else angulo


def elementos(
    sigma_x: float, sigma_y: float, tau_xy: float, theta_graus: float = 0.0
) -> list[Elemento]:
    """Os elementos a desenhar: original, girado (se θ ≠ 0), principal e de cisalhamento máximo."""
    r = mohr.analisar_estado_plano(sigma_x, sigma_y, tau_xy, theta_graus)
    saida = [Elemento("Nos eixos x e y", 0.0, sigma_x, sigma_y, tau_xy)]
    if abs(theta_graus) > 0.05:
        t = r.transformacao
        saida.append(
            Elemento(
                f"Girado {_n(theta_graus)}°",
                theta_graus,
                t.sigma_x_linha,
                t.sigma_y_linha,
                t.tau_x_linha_y_linha,
                ("σx'", "σy'", "τx'y'"),
            )  # fmt: skip
        )
    saida.append(
        Elemento(
            "Direções principais",
            _no_intervalo(r.theta_p1_graus),
            r.sigma_1_plana,
            r.sigma_2_plana,
            0.0,
            ("σ1", "σ2", "τ"),
        )  # fmt: skip
    )
    saida.append(
        Elemento(
            "Cisalhamento máximo",
            _no_intervalo(r.theta_tau_positivo_graus),
            r.centro,
            r.centro,
            r.tau_max_plana,
            ("σméd", "σméd", "τmáx"),
        )  # fmt: skip
    )
    return saida


def figura_dos_elementos(
    sigma_x: float, sigma_y: float, tau_xy: float, theta_graus: float = 0.0
) -> ImagemDiagrama:
    """Os elementos de tensão lado a lado, em MPa."""
    lista = elementos(sigma_x, sigma_y, tau_xy, theta_graus)
    largura_painel = 270
    largura_px = largura_painel * len(lista) + 40
    imagem = Image.new("RGB", (largura_px * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    maior = max(abs(v) for e in lista for v in (e.sigma_x, e.sigma_y, e.tau)) or 1.0
    for k, e in enumerate(lista):
        x0 = (20 + k * largura_painel) * ESC
        centro = (x0 + largura_painel / 2 * ESC, 205 * ESC)
        dr.text(
            (centro[0], 74 * ESC), e.titulo, fill=dg.COR_TEXTO, font=_fonte(13 * ESC), anchor="mm"
        )
        _elemento(dr, e, centro, maior)
        if k:
            dr.line([(x0, 70 * ESC), (x0, 340 * ESC)], fill="#e2e8f0", width=ESC)
    itens: list[tuple[str, str, str]] = [
        ("seta", _TRACAO, "tração (para fora da face)"),
        ("seta", _COMPRESSAO, "compressão (para dentro)"),
        ("seta", _CISALHAMENTO, "cisalhamento (ao longo da face)"),
    ]
    x_legenda = 20.0
    for item in itens:
        dg.legenda(dr, x_legenda * ESC, (_ALTURA_PX - 26) * ESC, [item])
        x_legenda += 26 + 18 + 6.2 * len(item[2])
    titulo = "Elementos de tensão"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        "Tensões em MPa; ângulos a partir do eixo x, no sentido anti-horário.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"σx = {_n(sigma_x)}, σy = {_n(sigma_y)} e τxy = {_n(tau_xy)} MPa: o elemento nos eixos, "
        + ("girado, " if abs(theta_graus) > 0.05 else "")
        + "nas direções principais e no cisalhamento máximo."
    )
    final = imagem.resize((largura_px, _ALTURA_PX), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(titulo, legenda, buffer.getvalue(), largura_px, _ALTURA_PX)
