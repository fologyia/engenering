"""Esquema do modelo de Vigas e eixos: a barra, os apoios, as rótulas, as cargas e as cotas.

Desenho técnico, na escala do comprimento: cada apoio com o seu símbolo (pino, rolete, engaste,
engaste deslizante, apoio horizontal, mola), as rótulas internas, as cargas distribuídas
(uniformes ou trapezoidais), as concentradas, os momentos, as axiais e os torques, todas com o
valor, e a cadeia de cotas dos pontos que importam. Convenção do modelo: força positiva para
cima, momento positivo anti-horário, axial positiva para a direita.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PIL import Image, ImageDraw

from core import beam_model as bm
from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, figura_final

ESC = dg.ESC
_BARRA = "#cbd5e1"
_CARGA = "#b45309"
_DISTRIBUIDA = "#d97706"
_MOMENTO = "#7c3aed"
_AXIAL = "#0f766e"
_ROTULA = "#b91c1c"
_LARGURA_PX, _ALTURA_PX = 1000, 470

Ponto = tuple[float, float]


def _n(valor: float, casas: int = 2) -> str:
    """Número em pt-BR sem zeros à direita: 1,5; 12; 0,25."""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto.replace(".", ",")


def _kn(valor_N: float) -> str:
    return f"{_n(abs(valor_N) / 1e3)} kN"


def _caso(caso: str) -> str:
    return "" if caso == bm.CASO_PADRAO else f" ({caso})"


def _hachura(dr: ImageDraw.ImageDraw, a: Ponto, b: Ponto, normal: Ponto) -> None:
    """Hachura de apoio ao longo de a–b, com os traços para o lado ``normal`` (px)."""
    comprimento = math.hypot(b[0] - a[0], b[1] - a[1])
    passos = max(int(comprimento / (6 * ESC)), 2)
    for k in range(passos + 1):
        p = (a[0] + (b[0] - a[0]) * k / passos, a[1] + (b[1] - a[1]) * k / passos)
        fim = (
            p[0] + normal[0] * 7 * ESC - normal[1] * 5 * ESC,
            p[1] + normal[1] * 7 * ESC + normal[0] * 5 * ESC,
        )
        dr.line([p, fim], fill=dg.COR_LINHA, width=ESC)


def _apoio(
    dr: ImageDraw.ImageDraw, apoio: bm.Apoio, x: float, y: float, meia: float, ponta: str
) -> None:
    """O símbolo do apoio em (x, y) na face de baixo da barra (``meia``: meia altura da barra)."""
    base = y + meia
    tipo = apoio.tipo
    if tipo in ("pino", "rolete"):
        altura, abre = 16 * ESC, 12 * ESC
        dr.polygon([(x, base), (x - abre, base + altura), (x + abre, base + altura)], fill="#ffffff", outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
        chao = base + altura
        if tipo == "rolete":
            r = 3 * ESC
            for dx in (-7 * ESC, 0.0, 7 * ESC):
                dr.ellipse(
                    [x + dx - r, chao, x + dx + r, chao + 2 * r], outline=dg.COR_LINHA, width=ESC
                )
            chao += 2 * r
        dr.line(
            [(x - abre - 6 * ESC, chao), (x + abre + 6 * ESC, chao)],
            fill=dg.COR_LINHA,
            width=2 * ESC,
        )
        _hachura(dr, (x - abre - 4 * ESC, chao), (x + abre + 6 * ESC, chao), (0.0, 1.0))
    elif tipo in ("engaste", "engaste deslizante"):
        # parede do lado de fora da barra (à esquerda na ponta inicial, à direita na final)
        lado = -1.0 if ponta == "inicio" else 1.0
        parede = x + lado * (2 * ESC if tipo == "engaste" else 10 * ESC)
        dr.line([(parede, y - 30 * ESC), (parede, y + 30 * ESC)], fill=dg.COR_LINHA, width=3 * ESC)
        _hachura(dr, (parede, y - 28 * ESC), (parede, y + 30 * ESC), (lado, 0.0))
        if tipo == "engaste deslizante":
            r = 3 * ESC
            for dy in (-8 * ESC, 8 * ESC):
                cx = x + lado * 5 * ESC
                dr.ellipse(
                    [cx - r, y + dy - r, cx + r, y + dy + r], outline=dg.COR_LINHA, width=ESC
                )
    elif tipo == "apoio horizontal":
        lado = -1.0 if ponta == "inicio" else 1.0
        topo = x + lado * 2 * ESC
        dr.polygon([(topo, y), (topo + lado * 16 * ESC, y - 12 * ESC), (topo + lado * 16 * ESC, y + 12 * ESC)], fill="#ffffff", outline=dg.COR_LINHA, width=2 * ESC)  # fmt: skip
        parede = topo + lado * 16 * ESC
        dr.line([(parede, y - 18 * ESC), (parede, y + 18 * ESC)], fill=dg.COR_LINHA, width=2 * ESC)
        _hachura(dr, (parede, y - 16 * ESC), (parede, y + 18 * ESC), (lado, 0.0))
    elif tipo == "mola":
        topo, fundo = base, base + 30 * ESC
        pontos = [(x, topo)]
        voltas = 6
        for k in range(1, voltas * 2):
            pontos.append(
                (x + (8 * ESC if k % 2 else -8 * ESC), topo + (fundo - topo) * k / (voltas * 2))
            )
        pontos.append((x, fundo))
        dr.line(pontos, fill=dg.COR_LINHA, width=2 * ESC, joint="curve")
        dr.line([(x - 16 * ESC, fundo), (x + 16 * ESC, fundo)], fill=dg.COR_LINHA, width=2 * ESC)
        _hachura(dr, (x - 14 * ESC, fundo), (x + 16 * ESC, fundo), (0.0, 1.0))
    if apoio.rotulo:
        dr.text(
            (x, base + 44 * ESC),
            apoio.rotulo,
            fill=dg.COR_TEXTO,
            font=_fonte(11 * ESC),
            anchor="mt",
        )


def _seta_curva(
    dr: ImageDraw.ImageDraw, centro: Ponto, raio: float, anti_horario: bool, cor: str
) -> None:
    """Momento: arco de 270° com a ponta no sentido do giro (tela com y para baixo)."""
    cx, cy = centro
    inicio = 200.0
    dr.arc(
        [cx - raio, cy - raio, cx + raio, cy + raio], inicio, inicio + 270, fill=cor, width=3 * ESC
    )
    t = math.radians(inicio if anti_horario else inicio + 270)
    ponta = (cx + raio * math.cos(t), cy + raio * math.sin(t))
    tangente = (math.sin(t), -math.cos(t)) if anti_horario else (-math.sin(t), math.cos(t))
    dg.seta(dr, dg.mais(ponta, tangente, -10 * ESC), ponta, cor, largura=3 * ESC, ponta_px=11 * ESC)


def _cadeia_de_cotas(dr: ImageDraw.ImageDraw, posicoes: Sequence[float], px, y: float) -> None:
    """Cotas entre os pontos que importam (m), numa linha, e o comprimento total embaixo."""
    unicos: list[float] = []
    for x in sorted(posicoes):
        if not unicos or x - unicos[-1] > 1e-6:
            unicos.append(x)
    for a, b in zip(unicos, unicos[1:], strict=False):
        dg.cota_alinhada(
            dr, (px(a), y), (px(b), y), (0.0, 1.0), f"{_n((b - a) / 1e3)} m", 0.0, fundo=True
        )


def figura_da_viga(v: bm.Viga) -> ImagemDiagrama:
    """O esquema do modelo, com a legenda dos símbolos que aparecem nele."""
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    comprimento = v.comprimento_mm
    x0, x1 = 110 * ESC, 830 * ESC
    y = 230 * ESC
    meia = 7 * ESC

    def px(x_mm: float) -> float:
        return x0 + (x1 - x0) * x_mm / comprimento

    fonte = _fonte(11 * ESC)
    presentes: set[str] = set()
    # ------------------------------------------------------------------ cargas distribuídas
    maior_w = max(
        [abs(c.w_inicial_N_mm) for c in v.cargas_distribuidas]
        + [abs(c.w_final_N_mm or c.w_inicial_N_mm) for c in v.cargas_distribuidas]
        + [1e-9]
    )
    for c in v.cargas_distribuidas:
        w0 = c.w_inicial_N_mm
        w1 = c.w_final_N_mm if c.w_final_N_mm is not None else w0
        if w0 == 0 and w1 == 0:
            continue
        presentes.add("distribuida")
        para_baixo = (w0 + w1) <= 0
        a, b = px(c.x_inicial_mm), px(c.x_final_mm)
        passos = max(int((b - a) / (20 * ESC)), 1)
        caudas: list[Ponto] = []
        for k in range(passos + 1):
            t = k / passos
            w = w0 + (w1 - w0) * t
            xa = a + (b - a) * t
            altura = 14 * ESC + 46 * ESC * abs(w) / maior_w
            if para_baixo:
                ponta, cauda = (xa, y - meia - 2 * ESC), (xa, y - meia - 2 * ESC - altura)
            else:
                ponta, cauda = (xa, y + meia + 2 * ESC), (xa, y + meia + 2 * ESC + altura)
            if abs(w) > 1e-12:
                dg.seta(dr, cauda, ponta, _DISTRIBUIDA, largura=ESC, ponta_px=7 * ESC)
            caudas.append(cauda)
        dr.line(caudas, fill=_DISTRIBUIDA, width=2 * ESC)
        valor = (
            f"q = {_n(abs(w0))} kN/m"
            if abs(w1 - w0) < 1e-12
            else f"q = {_n(abs(w0))} → {_n(abs(w1))} kN/m"
        )  # N/mm = kN/m
        # o valor no começo da carga, por cima (ou por baixo) da linha das caudas
        extremo = min(q[1] for q in caudas) if para_baixo else max(q[1] for q in caudas)
        borda = extremo + (-6 * ESC if para_baixo else 6 * ESC)
        dr.text(
            (a + 2 * ESC, borda), valor + _caso(c.caso), fill=_DISTRIBUIDA, font=fonte,
            anchor="lb" if para_baixo else "lt",
        )  # fmt: skip
    # ------------------------------------------------------------------ a barra
    dr.rectangle([x0, y - meia, x1, y + meia], fill=_BARRA, outline=dg.COR_LINHA, width=2 * ESC)
    dg.traco_ponto(dr, (x0 - 20 * ESC, y), (x1 + 20 * ESC, y), dg.COR_COTA)
    # ------------------------------------------------------------------ apoios e rótulas
    for apoio in v.apoios:
        presentes.add(f"apoio:{apoio.tipo}")
        extremidade = (
            "inicio"
            if apoio.x_mm <= 1e-6
            else ("fim" if apoio.x_mm >= comprimento - 1e-6 else "meio")
        )
        _apoio(dr, apoio, px(apoio.x_mm), y, meia, extremidade)
    for rotula in v.rotulas:
        presentes.add("rotula")
        r = 6 * ESC
        x = px(rotula.x_mm)
        dr.ellipse([x - r, y - r, x + r, y + r], fill="#ffffff", outline=_ROTULA, width=2 * ESC)
    # ------------------------------------------------------------------ cargas concentradas
    for cp in v.cargas_pontuais:
        if cp.fy_N == 0:
            continue
        presentes.add("pontual")
        x = px(cp.x_mm)
        if cp.fy_N < 0:
            ponta, cauda = (x, y - meia - 2 * ESC), (x, y - meia - 2 * ESC - 82 * ESC)
            lado = (0.0, -1.0)
        else:
            ponta, cauda = (x, y + meia + 2 * ESC), (x, y + meia + 2 * ESC + 82 * ESC)
            lado = (0.0, 1.0)
        dg.seta(dr, cauda, ponta, _CARGA, largura=3 * ESC, ponta_px=13 * ESC)
        texto = f"P = {_kn(cp.fy_N)}{_caso(cp.caso)}"
        dg.rotulo(dr, cauda, lado, 4 * ESC, texto, _CARGA, fonte, fundo=True)
    for m in v.momentos:
        if m.mz_Nmm == 0:
            continue
        presentes.add("momento")
        x = px(m.x_mm)
        _seta_curva(dr, (x, y), 22 * ESC, m.mz_Nmm > 0, _MOMENTO)
        texto = f"M = {_n(abs(m.mz_Nmm) / 1e6)} kN·m{_caso(m.caso)}"
        dg.rotulo(dr, (x, y), (0.0, 1.0), 30 * ESC, texto, _MOMENTO, fonte, fundo=True)
    for ca in v.cargas_axiais:
        if ca.fx_N == 0:
            continue
        presentes.add("axial")
        x = px(ca.x_mm)
        s = 1.0 if ca.fx_N > 0 else -1.0
        # nas pontas a seta fica do lado de fora da barra (puxando ou empurrando a ponta)
        if ca.x_mm >= comprimento - 1e-6:
            perto, longe = x + 6 * ESC, x + 52 * ESC
        elif ca.x_mm <= 1e-6:
            perto, longe = x - 6 * ESC, x - 52 * ESC
        else:
            perto, longe = x, x + s * 50 * ESC
        para_fora = (longe - perto) * s > 0  # a seta aponta para longe do ponto
        inicio_x, fim_x = (perto, longe) if para_fora else (longe, perto)
        dg.seta(dr, (inicio_x, y), (fim_x, y), _AXIAL, largura=3 * ESC, ponta_px=12 * ESC)
        lado = (1.0 if longe > perto else -1.0, -1.0)
        texto = f"N = {_kn(ca.fx_N)}{_caso(ca.caso)}"
        dg.rotulo(dr, (longe, y), lado, 6 * ESC, texto, _AXIAL, fonte, fundo=True)
    for tq in v.torques:
        if tq.t_Nmm == 0:
            continue
        presentes.add("torque")
        x = px(tq.x_mm)
        s = 1.0 if tq.t_Nmm > 0 else -1.0
        # vetor de torque ao longo do eixo (regra da mão direita): seta de ponta dupla
        nivel = y - 26 * ESC
        dr.line([(x, y - meia), (x, nivel)], fill=_MOMENTO, width=ESC)
        p_a, p_b = (x, nivel), (x + s * 46 * ESC, nivel)
        dg.seta(dr, p_a, p_b, _MOMENTO, largura=2 * ESC, ponta_px=10 * ESC)
        dg.seta(
            dr, p_a, (p_b[0] - s * 11 * ESC, nivel), _MOMENTO, largura=2 * ESC, ponta_px=10 * ESC
        )
        texto = f"T = {_n(abs(tq.t_Nmm) / 1e6)} kN·m{_caso(tq.caso)}"
        dg.rotulo(dr, p_b, (s, -1.0), 4 * ESC, texto, _MOMENTO, fonte, fundo=True)
    # ------------------------------------------------------------------ cotas
    posicoes = [0.0, comprimento]
    posicoes += [a.x_mm for a in v.apoios] + [r.x_mm for r in v.rotulas]
    posicoes += [c.x_mm for c in v.cargas_pontuais] + [m.x_mm for m in v.momentos]
    posicoes += [c.x_inicial_mm for c in v.cargas_distribuidas] + [
        c.x_final_mm for c in v.cargas_distribuidas
    ]
    y_cotas = y + 112 * ESC  # abaixo dos apoios e das cargas que sobem
    _cadeia_de_cotas(dr, [p for p in posicoes if 0 <= p <= comprimento], px, y_cotas)
    dg.cota_alinhada(
        dr, (px(0.0), y_cotas + 34 * ESC), (px(comprimento), y_cotas + 34 * ESC), (0.0, 1.0),
        f"L = {_n(comprimento / 1e3)} m", 0.0, fundo=True,
    )  # fmt: skip
    # ------------------------------------------------------------------ legenda e título
    nomes = {
        "apoio:pino": "pino (Δ = 0)", "apoio:rolete": "rolete (só vertical)",
        "apoio:engaste": "engaste (Δ = 0, θ = 0)", "apoio:engaste deslizante": "engaste deslizante",
        "apoio:apoio horizontal": "apoio horizontal", "apoio:mola": "mola",
    }  # fmt: skip
    itens: list[tuple[str, str, str]] = []
    apoios = [nomes[p] for p in sorted(presentes) if p in nomes]
    if apoios:
        itens.append(("", dg.COR_TEXTO, "Apoios: " + ", ".join(apoios)))
    if "rotula" in presentes:
        itens.append(("ponto", _ROTULA, "Rótula interna (M = 0)"))
    if "distribuida" in presentes:
        itens.append(("seta", _DISTRIBUIDA, "Carga distribuída (kN/m)"))
    if "pontual" in presentes:
        itens.append(("seta", _CARGA, "Carga concentrada (kN)"))
    if "momento" in presentes or "torque" in presentes:
        itens.append(("seta", _MOMENTO, "Momento ou torque (kN·m)"))
    if "axial" in presentes:
        itens.append(("seta", _AXIAL, "Força axial (kN)"))
    # a legenda numa linha, embaixo
    x_legenda = 18.0
    for item in itens:
        dg.legenda(dr, x_legenda * ESC, (_ALTURA_PX - 22) * ESC, [item])
        x_legenda += 26 + 18 + 6.1 * len(item[2])
    titulo = f"Esquema do modelo — {v.nome}"
    dr.text((18 * ESC, 14 * ESC), titulo, fill=dg.COR_TEXTO, font=_fonte(16 * ESC))
    dr.text(
        (18 * ESC, 38 * ESC),
        f"Seção {v.secao.nome}; {v.material.nome}. Forças positivas para cima, momentos "
        "anti-horários; distâncias em m.",
        fill=dg.COR_COTA,
        font=_fonte(11 * ESC),
    )
    legenda = (
        f"{v.nome}: L = {_n(comprimento / 1e3)} m, {len(v.apoios)} apoio(s), "
        f"{len(v.cargas_pontuais)} carga(s) concentrada(s), {len(v.cargas_distribuidas)} "
        "distribuída(s)."
    )
    return figura_final(imagem, titulo, legenda)
