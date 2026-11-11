"""Desenho da ligação parafusada (Projeto de parafusos): a planta e o corte.

* **Planta**: a chapa com a borda livre à esquerda (a peça continua à direita, com a linha de
  interrupção), os furos com a cabeça sextavada de cada parafuso numerada como na tabela, as cotas
  (passos s e g, bordas e e e_v), a força de cálculo em cada parafuso (método elástico, ELU) — o
  mais carregado em destaque — e N, V e M no centro do grupo, com as convenções do cálculo
  (N positivo para a direita, V para cima, M anti-horário).
* **Corte**: as chapas, o parafuso com a arruela e a porca, e todos os planos de corte.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from PIL import Image, ImageDraw

from core import bolted_connection as bc
from core import bolted_joint_check as chk
from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, figura_final

ESC = dg.ESC
_CHAPA = "#bfdbfe"
_CHAPA_2 = "#dbeafe"  # a outra chapa, no corte
_PARAFUSO = "#cbd5e1"
_PORCA = "#94a3b8"
_FORCA = "#b45309"
_CRITICO = "#b91c1c"
_CORTE = "#b91c1c"  # plano de corte
_CI = "#7c3aed"  # centro instantâneo de rotação
_LARGURA_PX, _ALTURA_PX = 1000, 580

Ponto = tuple[float, float]


def _n(valor: float, casas: int = 1) -> str:
    if abs(valor - round(valor)) < 1e-6:
        return f"{round(valor):d}"
    return f"{valor:.{casas}f}".replace(".", ",")


def _sextavado(
    dr: ImageDraw.ImageDraw, centro: Ponto, raio: float, contorno: str, giro: float
) -> None:
    """A cabeça sextavada vista de cima (``raio`` até o canto, px)."""
    cx, cy = centro
    cantos = [
        (cx + raio * math.cos(math.radians(30 + 60 * k - giro)), cy + raio * math.sin(math.radians(30 + 60 * k - giro)))
        for k in range(6)
    ]  # fmt: skip
    dr.polygon(cantos, fill=_PARAFUSO, outline=contorno, width=2 * ESC)


def _planta(
    dr: ImageDraw.ImageDraw, r: chk.ResultadoLigacao, caixa: tuple[int, int, int, int]
) -> tuple[int, float]:
    """A planta da ligação; devolve o parafuso mais carregado (índice) e a força nele (kN)."""
    e = r.entrada
    coords = list(r.coordenadas)
    n = len(coords)
    xc = sum(x for x, _ in coords) / n
    yc = sum(y for _, y in coords) / n
    rel = [(x - xc, y - yc) for x, y in coords]
    d_b = float(bc.dados_parafuso(e.designacao)["d_b"])
    d_h = e.d_h_mm if e.d_h_mm is not None else bc.furo_na_direcao_da_forca(e.designacao, e.tipo_furo, e.norma)  # fmt: skip
    borda_x = e.e
    borda_y = e.e_v if e.e_v is not None else e.e
    xs, ys = [x for x, _ in rel], [y for _, y in rel]
    x0, x1 = min(xs) - borda_x, max(xs) + borda_x
    y0, y1 = min(ys) - borda_y, max(ys) + borda_y
    vao = max(x1 - x0, y1 - y0, 4 * d_b)
    x_fim = x1 + 0.35 * vao + 20.0  # a peça continua à direita
    sobra = 0.32 * vao + 20.0  # cotas e setas fora da chapa
    tela = dg.Tela([(x0 - sobra, -(y1 + sobra)), (x_fim + 0.1 * vao, -(y0 - sobra))], caixa, 0.0)

    def p(x: float, y: float) -> Ponto:
        return tela(x, -y)

    # ------------------------------------------------------------------ a chapa, com a interrupção
    k = 0.06 * (y1 - y0)
    contorno = [
        p(x0, y0), p(x_fim, y0), p(x_fim, y0 + 0.40 * (y1 - y0)), p(x_fim + k, y0 + 0.47 * (y1 - y0)),
        p(x_fim - k, y0 + 0.53 * (y1 - y0)), p(x_fim, y0 + 0.60 * (y1 - y0)), p(x_fim, y1), p(x0, y1),
    ]  # fmt: skip
    dr.polygon(contorno, fill=_CHAPA, outline=dg.COR_LINHA, width=2 * ESC)
    # ------------------------------------------------------------------ cotas
    colunas = sorted({round(x, 6) for x in xs})
    linhas_y = sorted({round(y, 6) for y in ys})
    baixo, esquerda = (0.0, 1.0), (-1.0, 0.0)
    if len(colunas) >= 2:
        dg.cota_alinhada(
            dr, p(colunas[0], y0), p(colunas[1], y0), baixo, f"s = {_n(colunas[1] - colunas[0])}",
            22 * ESC, fundo=True,
        )  # fmt: skip
    dg.cota_alinhada(
        dr, p(x0, y0), p(colunas[0], y0), baixo, f"e = {_n(borda_x)}", 22 * ESC, fundo=True
    )
    if len(linhas_y) >= 2:
        dg.cota_alinhada(
            dr, p(x0, linhas_y[0]), p(x0, linhas_y[1]), esquerda,
            f"g = {_n(linhas_y[1] - linhas_y[0])}", 22 * ESC, fundo=True,
        )  # fmt: skip
    dg.cota_alinhada(
        dr, p(x0, y0), p(x0, linhas_y[0]), esquerda, f"e_v = {_n(borda_y)}", 22 * ESC,
        posicao=0.5, fundo=True,
    )  # fmt: skip
    # ------------------------------------------------------------------ furos e parafusos
    raio_furo = d_h / 2 * tela.esc
    raio_cabeca = max(0.75 * d_b * tela.esc / math.cos(math.radians(30)), raio_furo * 1.25)
    forcas = list(r.forcas_parafusos)
    critico = max(range(n), key=lambda i: forcas[i][2]) if forcas else -1
    fonte = _fonte(11 * ESC)
    for i, (x, y) in enumerate(rel):
        c = p(x, y)
        cor = _CRITICO if i == critico else dg.COR_LINHA
        _sextavado(dr, c, raio_cabeca, cor, 0.0)
        dr.ellipse(
            [c[0] - raio_furo * 0.62, c[1] - raio_furo * 0.62, c[0] + raio_furo * 0.62, c[1] + raio_furo * 0.62],
            outline=cor, width=ESC,
        )  # fmt: skip
        dr.text(c, str(i + 1), fill=cor, font=_fonte(10 * ESC), anchor="mm")
    # ------------------------------------------------------------------ força em cada parafuso
    if forcas:
        maior = max(f[2] for f in forcas) or 1.0
        passo_px = (
            min(
                [abs(b - a) for a, b in zip(colunas, colunas[1:], strict=False)]
                + [abs(b - a) for a, b in zip(linhas_y, linhas_y[1:], strict=False)]
                + [2.5 * d_b]
            )
            * tela.esc
        )
        comprimento_max = max(0.85 * passo_px, raio_cabeca * 2.6)
        for i, ((x, y), (fx, fy, fr)) in enumerate(zip(rel, forcas, strict=True)):
            if fr <= 0:
                continue
            c = p(x, y)
            direcao = (fx, -fy)  # y para cima na seção, para baixo na tela
            inicio = dg.mais(c, direcao, raio_cabeca + 2 * ESC)
            fim = dg.mais(c, direcao, raio_cabeca + 2 * ESC + comprimento_max * fr / maior)
            cor = _CRITICO if i == critico else _FORCA
            dg.seta(dr, inicio, fim, cor, largura=2 * ESC, ponta_px=9 * ESC)
            if i == critico:
                dg.rotulo(dr, fim, direcao, 5 * ESC, f"{_n(fr, 1)} kN", _CRITICO, fonte, fundo=True)
    # ------------------------------------------------------------------ N, V e M no centro do grupo
    g = p(0.0, 0.0)
    rc = 6 * ESC
    dr.ellipse(
        [g[0] - rc, g[1] - rc, g[0] + rc, g[1] + rc],
        fill="#ffffff",
        outline=dg.COR_TEXTO,
        width=2 * ESC,
    )
    dr.line([(g[0] - 10 * ESC, g[1]), (g[0] + 10 * ESC, g[1])], fill=dg.COR_TEXTO, width=ESC)
    dr.line([(g[0], g[1] - 10 * ESC), (g[0], g[1] + 10 * ESC)], fill=dg.COR_TEXTO, width=ESC)
    n_sd, v_sd, m_sd = (r.forcas.get(chave, 0.0) for chave in ("N_Sd_kN", "V_Sd_kN", "M_Sd_kNm"))
    grande = _fonte(12 * ESC)
    if n_sd:
        s = 1 if n_sd > 0 else -1
        a, b = (g[0] + s * 12 * ESC, g[1]), (g[0] + s * 50 * ESC, g[1])
        dg.seta(dr, a, b, _FORCA, largura=3 * ESC)
        dg.rotulo(dr, b, (0.0, -1.0), 6 * ESC, "N", _FORCA, grande, fundo=True)
    if v_sd:
        s = 1 if v_sd > 0 else -1
        a, b = (g[0], g[1] - s * 12 * ESC), (g[0], g[1] - s * 50 * ESC)
        dg.seta(dr, a, b, _FORCA, largura=3 * ESC)
        dg.rotulo(dr, b, (1.0, 0.0), 6 * ESC, "V", _FORCA, grande, fundo=True)
    if m_sd:
        raio = 20 * ESC
        angulo0 = 200.0
        dr.arc([g[0] - raio, g[1] - raio, g[0] + raio, g[1] + raio], angulo0, angulo0 + 250, fill=_FORCA, width=3 * ESC)  # fmt: skip
        t = math.radians(angulo0 if m_sd > 0 else angulo0 + 250)
        ponta = (g[0] + raio * math.cos(t), g[1] + raio * math.sin(t))
        tangente = (math.sin(t), -math.cos(t)) if m_sd > 0 else (-math.sin(t), math.cos(t))
        dg.seta(
            dr,
            dg.mais(ponta, tangente, -10 * ESC),
            ponta,
            _FORCA,
            largura=3 * ESC,
            ponta_px=11 * ESC,
        )
        dg.rotulo(dr, g, (-1.0, -1.0), 28 * ESC, "M", _FORCA, grande, fundo=True)
    # ------------------------------------------------------------------ centro instantâneo
    if "CI_x_mm" in r.forcas and "CI_y_mm" in r.forcas:
        cx, cy = r.forcas["CI_x_mm"], r.forcas["CI_y_mm"]
        if x0 - sobra <= cx <= x_fim and y0 - sobra <= cy <= y1 + sobra:
            c = p(cx, cy)
            braco = 9 * ESC
            dr.line([(c[0] - braco, c[1] - braco), (c[0] + braco, c[1] + braco)], fill=_CI, width=2 * ESC)  # fmt: skip
            dr.line([(c[0] - braco, c[1] + braco), (c[0] + braco, c[1] - braco)], fill=_CI, width=2 * ESC)  # fmt: skip
            dg.rotulo(dr, c, (1.0, -1.0), 10 * ESC, "CI", _CI, fonte, fundo=True)
    canto = p(x0, y1)
    dr.text((canto[0], canto[1] - 8 * ESC), "Planta", fill=dg.COR_COTA, font=fonte, anchor="lb")
    return critico, (forcas[critico][2] if critico >= 0 else 0.0)


def _corte(
    dr: ImageDraw.ImageDraw, r: chk.ResultadoLigacao, origem: Ponto, largura_px: float
) -> None:
    """O corte: chapas empilhadas, o parafuso com arruela e porca e os planos de corte."""
    e = r.entrada
    d_b = float(bc.dados_parafuso(e.designacao)["d_b"])
    planos = max(1, int(e.n_planos))
    n_chapas = planos + 1
    t = e.t
    pega = e.pega if e.pega else n_chapas * t
    espessura = pega / n_chapas
    altura_mm = pega + 1.5 * d_b + 1.2 * d_b  # cabeça e porca
    esc = min(largura_px / (4.2 * d_b + 2 * 3 * d_b), 150 * ESC / altura_mm)
    x0, y0 = origem
    meio = x0 + largura_px / 2
    topo = y0 + 0.7 * d_b * esc
    meia_chapa = 3.0 * d_b * esc
    fonte = _fonte(10 * ESC)
    for k in range(n_chapas):
        cima = topo + k * espessura * esc
        baixo = cima + espessura * esc
        deslocada = (1 if k % 2 == 0 else -1) * 0.8 * d_b * esc  # as chapas se sobrepõem
        dr.rectangle(
            [meio - meia_chapa + deslocada, cima, meio + meia_chapa + deslocada, baixo],
            fill=_CHAPA if k % 2 == 0 else _CHAPA_2, outline=dg.COR_LINHA, width=2 * ESC,
        )  # fmt: skip
        # a força em cada chapa: a de cima para um lado, a de baixo para o outro
        lado = 1 if k % 2 == 0 else -1
        y = (cima + baixo) / 2
        borda = meio + lado * (meia_chapa + deslocada * lado + 4 * ESC)
        dg.seta(
            dr, (borda, y), (borda + lado * 22 * ESC, y), _FORCA, largura=2 * ESC, ponta_px=8 * ESC
        )
    fundo = topo + pega * esc
    # o parafuso: haste, cabeça em cima, arruela e porca embaixo
    meio_d = d_b / 2 * esc
    dr.rectangle([meio - meio_d, topo - 2, meio + meio_d, fundo + 2], fill=_PARAFUSO, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    cabeca = 0.65 * d_b * esc
    dr.rectangle([meio - 0.85 * d_b * esc, topo - cabeca, meio + 0.85 * d_b * esc, topo], fill=_PORCA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
    arruela = 0.15 * d_b * esc
    dr.rectangle([meio - d_b * esc, fundo, meio + d_b * esc, fundo + arruela], fill="#e2e8f0", outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    porca = 0.8 * d_b * esc
    dr.rectangle([meio - 0.85 * d_b * esc, fundo + arruela, meio + 0.85 * d_b * esc, fundo + arruela + porca], fill=_PORCA, outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
    ponta = fundo + arruela + porca
    dr.rectangle([meio - meio_d, ponta, meio + meio_d, ponta + 0.3 * d_b * esc], fill=_PARAFUSO, outline=dg.COR_LINHA, width=ESC)  # fmt: skip
    # os planos de corte
    for k in range(1, n_chapas):
        y = topo + k * espessura * esc
        dg.tracejado(dr, (meio - meia_chapa - 1.2 * d_b * esc, y), (meio + meia_chapa + 1.2 * d_b * esc, y), _CORTE, largura=2 * ESC, traco=4 * ESC)  # fmt: skip
    dr.text((x0, y0 - 16 * ESC), "Corte", fill=dg.COR_COTA, font=fonte)
    texto = f"{planos} plano{'s' if planos > 1 else ''} de corte · t = {_n(t, 2)} mm"
    if e.pega:
        texto += f" · pega {_n(e.pega)} mm"
    dr.text(
        (meio, ponta + 0.3 * d_b * esc + 10 * ESC), texto, fill=dg.COR_COTA, font=fonte, anchor="mt"
    )


def figura_parafusos(r: chk.ResultadoLigacao) -> ImagemDiagrama | None:
    """A planta e o corte da ligação, com a legenda; ``None`` sem parafusos."""
    if not r.coordenadas:
        return None
    e = r.entrada
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    critico, forca_critica = _planta(dr, r, (60, 96, 600, 540))
    _corte(dr, r, (680 * ESC, 380 * ESC), 250 * ESC)
    n = len(r.coordenadas)
    d_h = e.d_h_mm if e.d_h_mm is not None else bc.furo_na_direcao_da_forca(e.designacao, e.tipo_furo, e.norma)  # fmt: skip
    n_sd, v_sd, m_sd = (r.forcas.get(chave, 0.0) for chave in ("N_Sd_kN", "V_Sd_kN", "M_Sd_kNm"))
    itens: list[tuple[str, str, str]] = [
        ("area", _CHAPA, f"Chapa ligada (t = {_n(e.t, 2)} mm, {e.aco})"),
        ("area", _PARAFUSO, f"{n} × {e.designacao} {e.grau}, furo {_n(d_h, 1)} mm"),
        (
            "seta",
            _FORCA,
            "Força de cálculo em cada parafuso (ELU, método elástico)"
            if "CI_x_mm" in r.forcas
            else "Força de cálculo em cada parafuso (ELU)",
        ),
    ]
    if critico >= 0:
        itens.append(
            ("seta", _CRITICO, f"Mais carregado: nº {critico + 1}, {_n(forca_critica, 2)} kN")
        )
    itens += [
        ("ponto", dg.COR_TEXTO, "Centro do grupo, com os esforços de cálculo:"),
        ("", _FORCA, f"   N = {_n(n_sd, 2)} kN · V = {_n(v_sd, 2)} kN · M = {_n(m_sd, 2)} kN·m"),
        ("tracejado", _CORTE, "Plano de corte do parafuso"),
    ]
    if "CI_x_mm" in r.forcas and "CI_y_mm" in r.forcas:
        ci_x, ci_y = r.forcas["CI_x_mm"], r.forcas["CI_y_mm"]
        c_texto = (
            f", C = {_n(r.forcas['C_centro_instantaneo'], 2)}"
            if "C_centro_instantaneo" in r.forcas
            else ""
        )
        itens += [
            ("", _CI, f"CI: centro instantâneo de rotação{c_texto}"),
            ("", _CI, f"   a ({_n(ci_x, 0)}; {_n(ci_y, 0)}) mm do centro do grupo"),
        ]
    dg.legenda(dr, 668 * ESC, 96 * ESC, itens)
    titulo = f"Ligação parafusada — {n} × {e.designacao} {e.grau}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        "Planta: forças nos parafusos pelo método elástico (ELU), N para a direita, V para cima e "
        "M anti-horário positivos. Cotas em mm.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"{n} parafusos {e.designacao} {e.grau} em chapa de {_n(e.t, 2)} mm; o mais carregado é o "
        f"nº {critico + 1}, com {_n(forca_critica, 2)} kN (ELU)."
    )
    return figura_final(imagem, titulo, legenda)


# ---------------------------------------------------------------------------------------------
# A ligação gravada no registro (o memorial refaz o cálculo e desenha de novo)
# ---------------------------------------------------------------------------------------------
def figura_do_registro(
    dados: Mapping[str, Any], utilizacao_registrada: float | None = None
) -> ImagemDiagrama | None:
    """Refaz a ligação gravada e a desenha. Se o aproveitamento de agora não bater com o
    registrado, o cálculo mudou desde o registro: levanta ``ValueError`` (o memorial omite a
    figura em vez de mostrar forças que não são as da tabela)."""
    r = chk.verificar_ligacao(chk.entrada_de_dicionario(dados["entrada"]))
    agora = r.aproveitamento_max
    if utilizacao_registrada is not None and agora is not None and math.isfinite(agora):
        referencia = max(abs(utilizacao_registrada), 1e-9)
        if abs(agora - utilizacao_registrada) > 1e-6 * referencia:
            raise ValueError(
                "o desenho da ligação não foi refeito porque o cálculo de agora dá aproveitamento "
                f"{agora:.4f} e o registro, {utilizacao_registrada:.4f}; registre a ligação de novo "
                "antes de emitir"
            )
    return figura_parafusos(r)
