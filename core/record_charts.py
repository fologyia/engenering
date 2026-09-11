"""Gráficos dos registros técnicos, redesenhados na emissão do memorial.

O registro guarda só as entradas e os resultados numéricos; o gráfico é
reconstruído a partir deles na hora de emitir, como já acontece com os
diagramas de viga em :mod:`core.report_plugins`. Isso mantém o banco
enxuto e garante que a figura nunca contradiz a tabela ao lado — as duas
saem dos mesmos números.

Tudo é desenhado com Pillow, sem depender de navegador ou de conversores
externos, para que o memorial saia igual no Windows do usuário e no CI.
"""

from __future__ import annotations

import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageDraw

from core.beam_charts import ImagemDiagrama, _fonte

COR_EIXO = "#475569"
COR_GRADE = "#e2e8f0"
COR_TEXTO = "#1e293b"
COR_PRINCIPAL = "#2563eb"
COR_SECUNDARIA = "#0f766e"
COR_DESTAQUE = "#dc2626"
COR_APOIO = "#7c3aed"
COR_NEUTRA = "#64748b"
COR_TORQUE_SEGURA = "#ea580c"
_FUNDO = "#ffffff"
_ESCALA = 2


@dataclass(frozen=True, slots=True)
class Curva:
    """Polilinha no plano do gráfico."""

    pontos: Sequence[tuple[float, float]]
    cor: str = COR_PRINCIPAL
    espessura: int = 2
    tracejada: bool = False
    rotulo: str = ""


@dataclass(frozen=True, slots=True)
class Marcador:
    """Ponto de interesse com etiqueta."""

    x: float
    y: float
    rotulo: str
    cor: str = COR_DESTAQUE
    deslocamento: tuple[int, int] = (8, -14)


@dataclass(frozen=True, slots=True)
class GraficoXY:
    titulo: str
    eixo_x: str
    eixo_y: str
    curvas: Sequence[Curva] = ()
    marcadores: Sequence[Marcador] = ()
    escalas_iguais: bool = False
    dominio_x: tuple[float, float] | None = None
    dominio_y: tuple[float, float] | None = None
    notas: Sequence[str] = field(default_factory=tuple)


def _passo(intervalo: float, alvo: int = 6) -> float:
    if intervalo <= 0 or not math.isfinite(intervalo):
        return 1.0
    bruto = intervalo / alvo
    expoente = math.floor(math.log10(bruto))
    base = bruto / 10**expoente
    for candidato in (1.0, 2.0, 2.5, 5.0, 10.0):
        if base <= candidato:
            return candidato * 10**expoente
    return 10.0 * 10**expoente


def _formatar(valor: float, passo: float) -> str:
    if passo >= 1:
        return f"{valor:.0f}"
    casas = min(4, max(1, -math.floor(math.log10(passo))))
    return f"{valor:.{casas}f}"


def _dominio(valores: Sequence[float], forcado: tuple[float, float] | None) -> tuple[float, float]:
    if forcado is not None:
        return forcado
    finitos = [valor for valor in valores if math.isfinite(valor)]
    if not finitos:
        return (0.0, 1.0)
    minimo, maximo = min(finitos), max(finitos)
    if maximo - minimo < 1e-9:
        folga = max(abs(maximo) * 0.1, 1.0)
        return (minimo - folga, maximo + folga)
    folga = (maximo - minimo) * 0.08
    return (minimo - folga, maximo + folga)


def renderizar_xy(
    grafico: GraficoXY,
    *,
    largura_px: int = 900,
    altura_px: int = 520,
    legenda: str = "",
) -> ImagemDiagrama:
    """Desenha um gráfico cartesiano simples e devolve o PNG."""
    escala = _ESCALA
    largura, altura = largura_px * escala, altura_px * escala
    imagem = Image.new("RGB", (largura, altura), _FUNDO)
    desenho = ImageDraw.Draw(imagem)
    fonte_titulo = _fonte(15 * escala)
    fonte_eixo = _fonte(11 * escala)
    fonte_rotulo = _fonte(11 * escala)

    margem_esq, margem_dir = 84 * escala, 22 * escala
    margem_topo = 36 * escala
    margem_base = (44 + 14 * len(grafico.notas)) * escala
    area_largura = largura - margem_esq - margem_dir
    area_altura = altura - margem_topo - margem_base

    xs = [p[0] for curva in grafico.curvas for p in curva.pontos] + [m.x for m in grafico.marcadores]
    ys = [p[1] for curva in grafico.curvas for p in curva.pontos] + [m.y for m in grafico.marcadores]
    x0, x1 = _dominio(xs, grafico.dominio_x)
    y0, y1 = _dominio(ys, grafico.dominio_y)
    if grafico.escalas_iguais:
        # Um círculo só parece círculo se 1 MPa mede o mesmo nos dois eixos.
        escala_x = area_largura / (x1 - x0)
        escala_y = area_altura / (y1 - y0)
        comum = min(escala_x, escala_y)
        centro_x, centro_y = (x0 + x1) / 2, (y0 + y1) / 2
        meia_x, meia_y = area_largura / comum / 2, area_altura / comum / 2
        x0, x1 = centro_x - meia_x, centro_x + meia_x
        y0, y1 = centro_y - meia_y, centro_y + meia_y

    def px(x: float) -> float:
        return margem_esq + (x - x0) / (x1 - x0) * area_largura

    def py(y: float) -> float:
        return margem_topo + (y1 - y) / (y1 - y0) * area_altura

    # Grade e eixos
    passo_x, passo_y = _passo(x1 - x0), _passo(y1 - y0)
    tick = math.ceil(x0 / passo_x) * passo_x
    while tick <= x1 + 1e-9:
        desenho.line([(px(tick), margem_topo), (px(tick), margem_topo + area_altura)], fill=COR_GRADE, width=escala)
        texto = _formatar(tick, passo_x)
        desenho.text((px(tick) - desenho.textlength(texto, font=fonte_eixo) / 2, margem_topo + area_altura + 6 * escala), texto, fill=COR_TEXTO, font=fonte_eixo)
        tick += passo_x
    tick = math.ceil(y0 / passo_y) * passo_y
    while tick <= y1 + 1e-9:
        desenho.line([(margem_esq, py(tick)), (margem_esq + area_largura, py(tick))], fill=COR_GRADE, width=escala)
        texto = _formatar(tick, passo_y)
        desenho.text((margem_esq - desenho.textlength(texto, font=fonte_eixo) - 8 * escala, py(tick) - 7 * escala), texto, fill=COR_TEXTO, font=fonte_eixo)
        tick += passo_y
    if x0 < 0 < x1:
        desenho.line([(px(0), margem_topo), (px(0), margem_topo + area_altura)], fill=COR_EIXO, width=escala)
    if y0 < 0 < y1:
        desenho.line([(margem_esq, py(0)), (margem_esq + area_largura, py(0))], fill=COR_EIXO, width=escala)
    desenho.rectangle([margem_esq, margem_topo, margem_esq + area_largura, margem_topo + area_altura], outline=COR_EIXO, width=escala)

    # Curvas
    for curva in grafico.curvas:
        pontos = [(px(x), py(y)) for x, y in curva.pontos if math.isfinite(x) and math.isfinite(y)]
        if len(pontos) < 2:
            continue
        if curva.tracejada:
            for inicio, fim in zip(pontos, pontos[1:]):
                comprimento = math.hypot(fim[0] - inicio[0], fim[1] - inicio[1])
                segmentos = max(1, int(comprimento / (8 * escala)))
                for indice in range(0, segmentos, 2):
                    t0, t1 = indice / segmentos, min(1.0, (indice + 1) / segmentos)
                    desenho.line(
                        [
                            (inicio[0] + (fim[0] - inicio[0]) * t0, inicio[1] + (fim[1] - inicio[1]) * t0),
                            (inicio[0] + (fim[0] - inicio[0]) * t1, inicio[1] + (fim[1] - inicio[1]) * t1),
                        ],
                        fill=curva.cor,
                        width=curva.espessura * escala,
                    )
        else:
            desenho.line(pontos, fill=curva.cor, width=curva.espessura * escala, joint="curve")

    # Marcadores
    raio = 4 * escala
    for marcador in grafico.marcadores:
        cx, cy = px(marcador.x), py(marcador.y)
        desenho.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=marcador.cor, outline=_FUNDO, width=escala)
        dx, dy = marcador.deslocamento
        desenho.text((cx + dx * escala, cy + dy * escala), marcador.rotulo, fill=marcador.cor, font=fonte_rotulo)

    # Legenda das curvas (canto superior direito da área)
    rotuladas = [curva for curva in grafico.curvas if curva.rotulo]
    if rotuladas:
        linha_y = margem_topo + 8 * escala
        for curva in rotuladas:
            texto = curva.rotulo
            largura_texto = desenho.textlength(texto, font=fonte_rotulo)
            x_texto = margem_esq + area_largura - largura_texto - 12 * escala
            desenho.line([(x_texto - 26 * escala, linha_y + 7 * escala), (x_texto - 8 * escala, linha_y + 7 * escala)], fill=curva.cor, width=curva.espessura * escala)
            desenho.text((x_texto, linha_y), texto, fill=COR_TEXTO, font=fonte_rotulo)
            linha_y += 16 * escala

    # Títulos
    desenho.text((margem_esq, 10 * escala), grafico.titulo, fill=COR_TEXTO, font=fonte_titulo)
    desenho.text(
        (margem_esq + area_largura / 2 - desenho.textlength(grafico.eixo_x, font=fonte_eixo) / 2, margem_topo + area_altura + 22 * escala),
        grafico.eixo_x,
        fill=COR_TEXTO,
        font=fonte_eixo,
    )
    rotulo_y = Image.new("RGBA", (int(desenho.textlength(grafico.eixo_y, font=fonte_eixo)) + 4, 16 * escala), (255, 255, 255, 0))
    ImageDraw.Draw(rotulo_y).text((0, 0), grafico.eixo_y, fill=COR_TEXTO, font=fonte_eixo)
    rotulo_y = rotulo_y.rotate(90, expand=True)
    imagem.paste(rotulo_y, (6 * escala, int(margem_topo + area_altura / 2 - rotulo_y.height / 2)), rotulo_y)
    for indice, nota in enumerate(grafico.notas):
        desenho.text((margem_esq, margem_topo + area_altura + (40 + 14 * indice) * escala), nota, fill=COR_NEUTRA, font=fonte_rotulo)

    imagem = imagem.resize((largura_px, altura_px), Image.LANCZOS)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return ImagemDiagrama(
        titulo=grafico.titulo,
        legenda=legenda or grafico.titulo,
        png=buffer.getvalue(),
        largura_px=largura_px,
        altura_px=altura_px,
    )


# ---------------------------------------------------------------------------
# Desenhistas por módulo
# ---------------------------------------------------------------------------


def _numero(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _circulo(centro: float, raio: float, *, passos: int = 181) -> list[tuple[float, float]]:
    return [
        (centro + raio * math.cos(2 * math.pi * indice / (passos - 1)), raio * math.sin(2 * math.pi * indice / (passos - 1)))
        for indice in range(passos)
    ]


def imagens_mohr(entradas: Mapping[str, Any], resultados: Mapping[str, Any]) -> list[ImagemDiagrama]:
    """Círculo de Mohr a partir do que o módulo registrou.

    Registros 2D trazem ``sigma_x/sigma_y/tau_xy`` e o estado transformado;
    registros 3D trazem ``sigma_1/2/3`` e ganham os três círculos.
    """
    s1, s2, s3 = (_numero(resultados.get(chave)) for chave in ("sigma_1_MPa", "sigma_2_MPa", "sigma_3_MPa"))
    if s3 is not None and s1 is not None and s2 is not None:
        maior, medio, menor = sorted((s1, s2, s3), reverse=True)
        curvas = [
            Curva(_circulo((maior + menor) / 2, (maior - menor) / 2), cor=COR_PRINCIPAL, rotulo="σ1–σ3"),
            Curva(_circulo((maior + medio) / 2, (maior - medio) / 2), cor=COR_SECUNDARIA, rotulo="σ1–σ2"),
            Curva(_circulo((medio + menor) / 2, (medio - menor) / 2), cor=COR_APOIO, rotulo="σ2–σ3"),
        ]
        marcadores = [
            Marcador(maior, 0.0, f"σ1 = {maior:.1f}", deslocamento=(8, 6)),
            Marcador(medio, 0.0, f"σ2 = {medio:.1f}", deslocamento=(-28, -22)),
            Marcador(menor, 0.0, f"σ3 = {menor:.1f}", deslocamento=(-70, 6)),
            Marcador((maior + menor) / 2, (maior - menor) / 2, f"τmáx = {(maior - menor) / 2:.1f}", cor=COR_DESTAQUE),
        ]
        plano = _numero(resultados.get("sigma_normal_plano_MPa")), _numero(resultados.get("tau_resultante_plano_MPa"))
        if plano[0] is not None and plano[1] is not None:
            marcadores.append(Marcador(plano[0], plano[1], "plano de interesse", cor=COR_TORQUE_SEGURA))
        grafico = GraficoXY(
            titulo="Círculos de Mohr — estado tridimensional",
            eixo_x="Tensão normal σ (MPa)",
            eixo_y="Tensão de cisalhamento τ (MPa)",
            curvas=curvas,
            marcadores=marcadores,
            escalas_iguais=True,
            notas=[f"von Mises = {_numero(resultados.get('von_mises_MPa')) or 0:.1f} MPa; Tresca = {_numero(resultados.get('tresca_equivalente_MPa')) or 0:.1f} MPa."],
        )
        return [renderizar_xy(grafico, legenda="Círculos de Mohr do tensor registrado (σ1 ≥ σ2 ≥ σ3).")]

    sx, sy, txy = (_numero(entradas.get(chave)) for chave in ("sigma_x_MPa", "sigma_y_MPa", "tau_xy_MPa"))
    if sx is None or sy is None or txy is None:
        return []
    centro = (sx + sy) / 2
    raio = math.hypot((sx - sy) / 2, txy)
    curvas = [
        Curva(_circulo(centro, raio), cor=COR_PRINCIPAL),
        Curva([(sx, txy), (sy, -txy)], cor=COR_NEUTRA, espessura=1, rotulo="Estado original"),
    ]
    marcadores = [
        Marcador(sx, txy, f"x ({sx:.1f}, {txy:.1f})", cor=COR_NEUTRA),
        Marcador(sy, -txy, f"y ({sy:.1f}, {-txy:.1f})", cor=COR_NEUTRA),
        Marcador(centro + raio, 0.0, f"σ1 = {centro + raio:.1f}", deslocamento=(8, 6)),
        Marcador(centro - raio, 0.0, f"σ2 = {centro - raio:.1f}", deslocamento=(-64, 6)),
        Marcador(centro, raio, f"τmáx = {raio:.1f}", cor=COR_DESTAQUE),
    ]
    sxl, syl, txl = (
        _numero(resultados.get(chave))
        for chave in ("sigma_x_transformada_MPa", "sigma_y_transformada_MPa", "tau_transformada_MPa")
    )
    if sxl is not None and syl is not None and txl is not None:
        curvas.append(Curva([(sxl, txl), (syl, -txl)], cor=COR_SECUNDARIA, espessura=1, tracejada=True, rotulo=f"Transformado (θ = {_numero(entradas.get('theta_graus')) or 0:g}°)"))
        marcadores.append(Marcador(sxl, txl, "x'", cor=COR_SECUNDARIA))
        marcadores.append(Marcador(syl, -txl, "y'", cor=COR_SECUNDARIA))
    grafico = GraficoXY(
        titulo="Círculo de Mohr — estado plano de tensões",
        eixo_x="Tensão normal σ (MPa)",
        eixo_y="Tensão de cisalhamento τ (MPa)",
        curvas=curvas,
        marcadores=marcadores,
        escalas_iguais=True,
        notas=[f"Centro = {centro:.1f} MPa; raio = {raio:.1f} MPa; von Mises = {_numero(resultados.get('von_mises_MPa')) or 0:.1f} MPa."],
    )
    return [renderizar_xy(grafico, legenda="Círculo de Mohr do estado plano registrado, com o estado transformado no plano escolhido.")]



def imagens_flambagem(entradas: Mapping[str, Any], resultados: Mapping[str, Any]) -> list[ImagemDiagrama]:
    """Curva σcr × λ (Euler + Johnson) com a coluna registrada marcada."""
    modulo_e = _numero(entradas.get("modulo_elasticidade_MPa"))
    escoamento = _numero(entradas.get("escoamento_MPa"))
    area = _numero(entradas.get("area_mm2"))
    esbeltez = _numero(resultados.get("esbeltez_governante"))
    transicao = _numero(resultados.get("esbeltez_transicao"))
    if not all(valor and valor > 0 for valor in (modulo_e, escoamento, area, esbeltez, transicao)):
        return []
    assert modulo_e and escoamento and area and esbeltez and transicao

    lambda_max = max(esbeltez * 1.25, transicao * 1.6, 60.0)
    passos = 200
    johnson = [
        (lam, escoamento - (escoamento * lam / (2 * math.pi)) ** 2 / modulo_e)
        for lam in (transicao * indice / passos for indice in range(passos + 1))
    ]
    euler = [
        (lam, math.pi**2 * modulo_e / lam**2)
        for lam in (transicao + (lambda_max - transicao) * indice / passos for indice in range(passos + 1))
    ]
    euler_estendida = [
        (lam, math.pi**2 * modulo_e / lam**2)
        for lam in (max(transicao * 0.45, 1.0) + (transicao - max(transicao * 0.45, 1.0)) * indice / 60 for indice in range(61))
    ]
    euler_estendida = [(lam, sigma) for lam, sigma in euler_estendida if sigma <= escoamento * 1.6]

    carga_critica = _numero(resultados.get("carga_critica_kN"))
    forca = _numero(entradas.get("forca_solicitante_kN"))
    sigma_cr = (carga_critica * 1_000.0 / area) if carga_critica else None
    sigma_atuante = (forca * 1_000.0 / area) if forca else None

    curvas = [
        Curva(johnson, cor=COR_SECUNDARIA, rotulo="Johnson (coluna curta/intermediária)"),
        Curva(euler, cor=COR_PRINCIPAL, rotulo="Euler (coluna longa)"),
        Curva(euler_estendida, cor=COR_PRINCIPAL, espessura=1, tracejada=True),
        Curva([(0.0, escoamento), (lambda_max, escoamento)], cor=COR_NEUTRA, espessura=1, tracejada=True, rotulo=f"Sy = {escoamento:.0f} MPa"),
        Curva([(transicao, 0.0), (transicao, escoamento * 1.05)], cor=COR_NEUTRA, espessura=1, tracejada=True),
    ]
    marcadores = [Marcador(transicao, escoamento / 2, f"λt = {transicao:.1f}", cor=COR_NEUTRA, deslocamento=(6, -8))]
    if sigma_cr is not None:
        marcadores.append(Marcador(esbeltez, sigma_cr, f"σcr = {sigma_cr:.1f} MPa (λ = {esbeltez:.1f})", cor=COR_DESTAQUE))
    if sigma_atuante is not None:
        curvas.append(Curva([(0.0, sigma_atuante), (lambda_max, sigma_atuante)], cor=COR_TORQUE_SEGURA, espessura=1, rotulo=f"σ atuante = P/A = {sigma_atuante:.1f} MPa"))
        marcadores.append(Marcador(esbeltez, sigma_atuante, "coluna", cor=COR_TORQUE_SEGURA, deslocamento=(8, 4)))
    notas = []
    fator = _numero(resultados.get("fator_seguranca"))
    if fator is not None:
        notas.append(f"Regime: {resultados.get('regime', '-')}; fator de segurança real = {fator:.2f}.")
    grafico = GraficoXY(
        titulo="Tensão crítica de flambagem × índice de esbeltez",
        eixo_x="Índice de esbeltez λ = KL/r",
        eixo_y="Tensão crítica σcr (MPa)",
        curvas=curvas,
        marcadores=marcadores,
        dominio_x=(0.0, lambda_max),
        dominio_y=(0.0, escoamento * 1.15),
        notas=notas,
    )
    return [renderizar_xy(grafico, legenda="Curva de Euler/Johnson do material registrado, com a esbeltez governante da coluna e a tensão atuante.")]


def imagens_do_registro(
    registro: Mapping[str, Any], projeto: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], str]:
    """Figuras do capítulo de um registro, no formato que Word e PDF consomem.

    Devolve ``(imagens, aviso)``; o aviso é vazio quando não há o que dizer.
    Módulos sem desenhista simplesmente não têm figura — o memorial não
    inventa gráfico para um cálculo que não o produziu.
    """
    modulo_id = str(registro.get("modulo_id") or "")
    entradas = registro.get("entradas") if isinstance(registro.get("entradas"), Mapping) else {}
    resultados = registro.get("resultados") if isinstance(registro.get("resultados"), Mapping) else {}
    try:
        if modulo_id == "vigas_eixos":
            from core.report_plugins import _diagramas_do_registro

            return _diagramas_do_registro(registro, projeto)
        if modulo_id == "circulo_mohr":
            desenhos = imagens_mohr(entradas, resultados)
        elif modulo_id == "flambagem_colunas":
            desenhos = imagens_flambagem(entradas, resultados)
        else:
            return [], ""
    except Exception as erro:  # noqa: BLE001 - o memorial não pode cair por causa de um gráfico
        return [], f"Gráfico omitido: {erro}"
    return [
        {
            "titulo": imagem.titulo,
            "legenda": imagem.legenda,
            "png": imagem.png,
            "largura_px": imagem.largura_px,
            "altura_px": imagem.altura_px,
        }
        for imagem in desenhos
    ], ""
