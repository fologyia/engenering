"""Propriedades geométricas de perfis de aço para pré-dimensionamento.

Os perfis do catálogo são geométricos e não representam uma marca comercial.
Raios de concordância e tolerâncias de fabricação são desprezados.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import pandas as pd


DENSIDADE_ACO_KG_M3 = 7_850.0


@dataclass(frozen=True)
class PerfilAco:
    nome: str
    familia: str
    area_mm2: float
    ix_mm4: float
    iy_mm4: float
    zx_mm3: float
    zy_mm3: float
    j_mm4: float
    cw_mm6: float
    altura_mm: float
    largura_mm: float
    espessura_alma_mm: float
    espessura_mesa_mm: float
    area_cisalhamento_mm2: float
    massa_kg_m: float
    descricao: str

    @property
    def rx_mm(self) -> float:
        return math.sqrt(self.ix_mm4 / self.area_mm2)

    @property
    def ry_mm(self) -> float:
        return math.sqrt(self.iy_mm4 / self.area_mm2)

    @property
    def sx_mm3(self) -> float:
        return self.ix_mm4 / (self.altura_mm / 2.0)

    @property
    def sy_mm3(self) -> float:
        return self.iy_mm4 / (self.largura_mm / 2.0)


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _massa(area_mm2: float) -> float:
    return area_mm2 * DENSIDADE_ACO_KG_M3 / 1_000_000.0


def _retangulo(cx: float, cy: float, largura: float, altura: float) -> tuple[float, float, float, float, float]:
    """Retângulo axialmente alinhado: (área, cx, cy, Ix próprio, Iy próprio)."""
    area = largura * altura
    ix_proprio = largura * altura**3 / 12.0
    iy_proprio = altura * largura**3 / 12.0
    return area, cx, cy, ix_proprio, iy_proprio


def _combinar(pecas: list[tuple[float, float, float, float, float]]) -> tuple[float, float, float, float, float]:
    """Compõe retângulos pelo teorema dos eixos paralelos.

    Retorna (área total, x̄, ȳ, Ix em torno de ȳ, Iy em torno de x̄).
    """
    area_total = sum(p[0] for p in pecas)
    xbar = sum(p[0] * p[1] for p in pecas) / area_total
    ybar = sum(p[0] * p[2] for p in pecas) / area_total
    ix = sum(p[3] + p[0] * (p[2] - ybar) ** 2 for p in pecas)
    iy = sum(p[4] + p[0] * (p[1] - xbar) ** 2 for p in pecas)
    return area_total, xbar, ybar, ix, iy


def _modulo_plastico(retangulos: list[tuple[float, float, float, float]], eixo: str) -> float:
    """Módulo plástico exato de uma seção formada por retângulos alinhados.

    ``retangulos`` é uma lista de ``(x0, x1, y0, y1)``. Para ``eixo="x"``
    (flexão em torno do eixo horizontal), varre faixas de y somando a largura
    de material em cada faixa; para ``eixo="y"`` faz o mesmo varrendo x. Acha
    a linha neutra plástica (área igual dos dois lados) e soma a distância de
    cada faixa até ela — válido mesmo quando a seção não é simétrica no eixo
    de flexão (canal, T, cantoneira, perfil enrijecido).
    """
    if eixo == "x":
        cortes = sorted({r[2] for r in retangulos} | {r[3] for r in retangulos})
        largura_em = lambda meio: sum(r[1] - r[0] for r in retangulos if r[2] <= meio <= r[3])
    else:
        cortes = sorted({r[0] for r in retangulos} | {r[1] for r in retangulos})
        largura_em = lambda meio: sum(r[3] - r[2] for r in retangulos if r[0] <= meio <= r[1])

    segmentos = []
    for c0, c1 in zip(cortes, cortes[1:]):
        largura = largura_em((c0 + c1) / 2.0)
        segmentos.append((c0, c1, largura))

    area_total = sum((c1 - c0) * largura for c0, c1, largura in segmentos)
    metade = area_total / 2.0
    acumulado = 0.0
    pna = cortes[-1]
    for c0, c1, largura in segmentos:
        area_segmento = (c1 - c0) * largura
        if acumulado + area_segmento >= metade and largura > 0:
            pna = c0 + (metade - acumulado) / largura
            break
        acumulado += area_segmento

    modulo = 0.0
    for c0, c1, largura in segmentos:
        if c1 <= pna or c0 >= pna:
            centro = (c0 + c1) / 2.0
            modulo += (c1 - c0) * largura * abs(centro - pna)
        else:
            modulo += (pna - c0) * largura * abs((c0 + pna) / 2.0 - pna)
            modulo += (c1 - pna) * largura * abs((pna + c1) / 2.0 - pna)
    return modulo


def perfil_i_simetrico(
    nome: str,
    altura_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
    familia: str = "I duplamente simétrico",
) -> PerfilAco:
    h = _positivo("altura_mm", altura_mm)
    b = _positivo("largura_mesa_mm", largura_mesa_mm)
    tw = _positivo("espessura_alma_mm", espessura_alma_mm)
    tf = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    if 2.0 * tf >= h:
        raise ValueError("As mesas ocupam toda a altura do perfil.")
    if tw >= b:
        raise ValueError("A alma deve ser mais estreita que a mesa.")
    hw = h - 2.0 * tf
    area = 2.0 * b * tf + hw * tw
    ix = (
        b * h**3 - (b - tw) * hw**3
    ) / 12.0
    iy = 2.0 * tf * b**3 / 12.0 + hw * tw**3 / 12.0
    zx = 2.0 * (
        b * tf * (h / 2.0 - tf / 2.0)
        + tw * (h / 2.0 - tf) ** 2 / 2.0
    )
    zy = tf * b**2 / 2.0 + hw * tw**2 / 4.0
    j = (2.0 * b * tf**3 + hw * tw**3) / 3.0
    cw = tf * b**3 * (h - tf) ** 2 / 24.0
    return PerfilAco(
        nome=nome,
        familia=familia,
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=zx,
        zy_mm3=zy,
        j_mm4=j,
        cw_mm6=cw,
        altura_mm=h,
        largura_mm=b,
        espessura_alma_mm=tw,
        espessura_mesa_mm=tf,
        area_cisalhamento_mm2=hw * tw,
        massa_kg_m=_massa(area),
        descricao="Perfil I idealizado, sem raios de concordância.",
    )


def perfil_w_mesa_larga(
    nome: str,
    altura_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
) -> PerfilAco:
    """Perfil W (mesa larga): mesma geometria do I, com mesas proporcionalmente

    mais largas e robustas. Reaproveita as mesmas equações de área e inércia
    do :func:`perfil_i_simetrico` — a diferença é só a proporção h/b típica
    de catálogo, tratada aqui pela família atribuída.
    """
    perfil = perfil_i_simetrico(
        nome, altura_mm, largura_mesa_mm, espessura_alma_mm, espessura_mesa_mm,
        familia="W (mesa larga)",
    )
    return PerfilAco(**{**perfil.__dict__, "descricao": "Perfil W idealizado, sem raios de concordância."})


def perfil_u(
    nome: str,
    altura_mm: float,
    largura_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
) -> PerfilAco:
    """Perfil U (canal laminado): simétrico só em torno do eixo x (forte)."""
    h = _positivo("altura_mm", altura_mm)
    b = _positivo("largura_mm", largura_mm)
    tw = _positivo("espessura_alma_mm", espessura_alma_mm)
    tf = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    if 2.0 * tf >= h:
        raise ValueError("As mesas ocupam toda a altura do perfil.")
    if tw >= b:
        raise ValueError("A alma deve ser mais estreita que a mesa.")

    pecas = [
        _retangulo(tw / 2.0, h / 2.0, tw, h),
        _retangulo(tw + (b - tw) / 2.0, tf / 2.0, b - tw, tf),
        _retangulo(tw + (b - tw) / 2.0, h - tf / 2.0, b - tw, tf),
    ]
    area, _xbar, ybar, ix, iy = _combinar(pecas)
    retangulos_abs = [
        (0.0, tw, 0.0, h),
        (tw, b, 0.0, tf),
        (tw, b, h - tf, h),
    ]
    zx = _modulo_plastico(retangulos_abs, "x")
    zy = _modulo_plastico(retangulos_abs, "y")
    hw = h - 2.0 * tf
    j = (2.0 * b * tf**3 + hw * tw**3) / 3.0
    return PerfilAco(
        nome=nome,
        familia="U (canal laminado)",
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=zx,
        zy_mm3=zy,
        j_mm4=j,
        cw_mm6=0.0,
        altura_mm=h,
        largura_mm=b,
        espessura_alma_mm=tw,
        espessura_mesa_mm=tf,
        area_cisalhamento_mm2=hw * tw,
        massa_kg_m=_massa(area),
        descricao=(
            "Perfil U idealizado, sem raios de concordância. Iy e Zy já "
            "consideram o centroide deslocado (seção monossimétrica); "
            f"centroide a {ybar - h / 2.0:+.2f} mm do meio da alma em y "
            "(deve ser ~0, pois é simétrico em x)."
        ),
    )


def perfil_c_enrijecido(
    nome: str,
    altura_mm: float,
    largura_mesa_mm: float,
    aba_enrijecedora_mm: float,
    espessura_mm: float,
) -> PerfilAco:
    """Perfil C enrijecido (chapa dobrada a frio), com abas nas pontas das mesas."""
    h = _positivo("altura_mm", altura_mm)
    b = _positivo("largura_mesa_mm", largura_mesa_mm)
    d = _positivo("aba_enrijecedora_mm", aba_enrijecedora_mm)
    t = _positivo("espessura_mm", espessura_mm)
    if 2.0 * t >= h:
        raise ValueError("As mesas ocupam toda a altura do perfil.")
    if t >= b:
        raise ValueError("A alma deve ser mais estreita que a mesa.")
    if d >= h / 2.0 - t:
        raise ValueError("A aba enrijecedora é grande demais para a altura do perfil.")

    pecas = [
        _retangulo(t / 2.0, h / 2.0, t, h),
        _retangulo(t + (b - t) / 2.0, t / 2.0, b - t, t),
        _retangulo(t + (b - t) / 2.0, h - t / 2.0, b - t, t),
        _retangulo(b - t / 2.0, t + d / 2.0, t, d),
        _retangulo(b - t / 2.0, h - t - d / 2.0, t, d),
    ]
    area, _xbar, ybar, ix, iy = _combinar(pecas)
    retangulos_abs = [
        (0.0, t, 0.0, h),
        (t, b, 0.0, t),
        (t, b, h - t, h),
        (b - t, b, t, t + d),
        (b - t, b, h - t - d, h - t),
    ]
    zx = _modulo_plastico(retangulos_abs, "x")
    zy = _modulo_plastico(retangulos_abs, "y")
    j = (t**3 / 3.0) * (h + 2.0 * b + 2.0 * d)
    hw = h - 2.0 * t
    return PerfilAco(
        nome=nome,
        familia="C enrijecido (chapa dobrada)",
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=zx,
        zy_mm3=zy,
        j_mm4=j,
        cw_mm6=0.0,
        altura_mm=h,
        largura_mm=b,
        espessura_alma_mm=t,
        espessura_mesa_mm=t,
        area_cisalhamento_mm2=hw * t,
        massa_kg_m=_massa(area),
        descricao=(
            "Perfil C enrijecido idealizado (chapa dobrada, espessura única, "
            f"sem raios de dobra); centroide em y = {ybar:.2f} mm."
        ),
    )


def perfil_t(
    nome: str,
    altura_total_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
) -> PerfilAco:
    """Perfil T: simétrico em y (mesa), monossimétrico em x (alma para um lado)."""
    d = _positivo("altura_total_mm", altura_total_mm)
    b = _positivo("largura_mesa_mm", largura_mesa_mm)
    tw = _positivo("espessura_alma_mm", espessura_alma_mm)
    tf = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    if tf >= d:
        raise ValueError("A mesa ocupa toda a altura do perfil.")
    if tw >= b:
        raise ValueError("A alma deve ser mais estreita que a mesa.")
    hw = d - tf

    pecas = [
        _retangulo(b / 2.0, hw / 2.0, tw, hw),
        _retangulo(b / 2.0, hw + tf / 2.0, b, tf),
    ]
    area, xbar, ybar, ix, iy = _combinar(pecas)
    retangulos_abs = [
        (b / 2.0 - tw / 2.0, b / 2.0 + tw / 2.0, 0.0, hw),
        (0.0, b, hw, hw + tf),
    ]
    zx = _modulo_plastico(retangulos_abs, "x")
    zy = _modulo_plastico(retangulos_abs, "y")
    j = (b * tf**3 + hw * tw**3) / 3.0
    return PerfilAco(
        nome=nome,
        familia="T (perfil tê)",
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=zx,
        zy_mm3=zy,
        j_mm4=j,
        cw_mm6=0.0,
        altura_mm=d,
        largura_mm=b,
        espessura_alma_mm=tw,
        espessura_mesa_mm=tf,
        area_cisalhamento_mm2=hw * tw,
        massa_kg_m=_massa(area),
        descricao=(
            "Perfil T idealizado, sem raios de concordância; centroide a "
            f"{ybar:.2f} mm da base do talão (x̄ = {xbar:.2f} mm, no eixo de simetria)."
        ),
    )


def barra_circular(nome: str, diametro_mm: float) -> PerfilAco:
    d = _positivo("diametro_mm", diametro_mm)
    area = math.pi * d**2 / 4.0
    inercia = math.pi * d**4 / 64.0
    z = d**3 / 6.0
    return PerfilAco(
        nome=nome,
        familia="Barra circular",
        area_mm2=area,
        ix_mm4=inercia,
        iy_mm4=inercia,
        zx_mm3=z,
        zy_mm3=z,
        j_mm4=math.pi * d**4 / 32.0,
        cw_mm6=0.0,
        altura_mm=d,
        largura_mm=d,
        espessura_alma_mm=d,
        espessura_mesa_mm=d,
        area_cisalhamento_mm2=0.9 * area,
        massa_kg_m=_massa(area),
        descricao="Barra maciça circular.",
    )


def tubo_retangular(
    nome: str,
    altura_mm: float,
    largura_mm: float,
    espessura_mm: float,
) -> PerfilAco:
    h = _positivo("altura_mm", altura_mm)
    b = _positivo("largura_mm", largura_mm)
    t = _positivo("espessura_mm", espessura_mm)
    if 2.0 * t >= min(h, b):
        raise ValueError("A espessura é incompatível com as dimensões externas.")
    hi = h - 2.0 * t
    bi = b - 2.0 * t
    area = b * h - bi * hi
    ix = (b * h**3 - bi * hi**3) / 12.0
    iy = (h * b**3 - hi * bi**3) / 12.0
    zx = (b * h**2 - bi * hi**2) / 4.0
    zy = (h * b**2 - hi * bi**2) / 4.0
    bm = b - t
    hm = h - t
    j = 2.0 * t * (bm * hm) ** 2 / (bm + hm)
    return PerfilAco(
        nome=nome,
        familia="Tubo retangular",
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=zx,
        zy_mm3=zy,
        j_mm4=j,
        cw_mm6=0.0,
        altura_mm=h,
        largura_mm=b,
        espessura_alma_mm=t,
        espessura_mesa_mm=t,
        area_cisalhamento_mm2=2.0 * t * (h - 2.0 * t),
        massa_kg_m=_massa(area),
        descricao="Tubo retangular idealizado, sem raios nos cantos.",
    )


def tubo_circular(
    nome: str,
    diametro_externo_mm: float,
    espessura_mm: float,
) -> PerfilAco:
    d = _positivo("diametro_externo_mm", diametro_externo_mm)
    t = _positivo("espessura_mm", espessura_mm)
    if 2.0 * t >= d:
        raise ValueError("A espessura é incompatível com o diâmetro.")
    di = d - 2.0 * t
    area = math.pi * (d**2 - di**2) / 4.0
    inercia = math.pi * (d**4 - di**4) / 64.0
    z = (d**3 - di**3) / 6.0
    return PerfilAco(
        nome=nome,
        familia="Tubo circular",
        area_mm2=area,
        ix_mm4=inercia,
        iy_mm4=inercia,
        zx_mm3=z,
        zy_mm3=z,
        j_mm4=2.0 * inercia,
        cw_mm6=0.0,
        altura_mm=d,
        largura_mm=d,
        espessura_alma_mm=t,
        espessura_mesa_mm=t,
        area_cisalhamento_mm2=0.5 * area,
        massa_kg_m=_massa(area),
        descricao="Tubo circular idealizado com espessura uniforme.",
    )


def barra_retangular(
    nome: str,
    altura_mm: float,
    largura_mm: float,
) -> PerfilAco:
    h = _positivo("altura_mm", altura_mm)
    b = _positivo("largura_mm", largura_mm)
    area = b * h
    ix = b * h**3 / 12.0
    iy = h * b**3 / 12.0
    maior, menor = max(h, b), min(h, b)
    j = maior * menor**3 * (
        1.0 / 3.0
        - 0.21 * menor / maior * (1.0 - menor**4 / (12.0 * maior**4))
    )
    return PerfilAco(
        nome=nome,
        familia="Barra retangular",
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        zx_mm3=b * h**2 / 4.0,
        zy_mm3=h * b**2 / 4.0,
        j_mm4=j,
        cw_mm6=0.0,
        altura_mm=h,
        largura_mm=b,
        espessura_alma_mm=b,
        espessura_mesa_mm=h,
        area_cisalhamento_mm2=5.0 * area / 6.0,
        massa_kg_m=_massa(area),
        descricao="Barra maciça retangular.",
    )


def _criar_catalogo() -> dict[str, PerfilAco]:
    perfis: list[PerfilAco] = []
    for h, b, tw, tf in (
        (100, 55, 4.1, 5.7),
        (150, 75, 5.0, 7.0),
        (200, 100, 5.5, 8.0),
        (250, 125, 6.0, 9.0),
        (300, 150, 6.5, 10.0),
        (350, 175, 7.0, 11.0),
        (400, 200, 8.0, 13.0),
        (500, 200, 10.0, 16.0),
    ):
        nome = f"I ideal {h}×{b}×{tw:g}×{tf:g}"
        perfis.append(perfil_i_simetrico(nome, h, b, tw, tf))
    for h, b, tw, tf in (
        (100, 100, 6.0, 8.0),
        (150, 150, 7.0, 10.0),
        (200, 200, 8.0, 12.0),
        (250, 250, 9.0, 14.0),
        (300, 300, 10.0, 15.0),
        (350, 350, 12.0, 19.0),
    ):
        nome = f"W ideal {h}×{b}×{tw:g}×{tf:g}"
        perfis.append(perfil_w_mesa_larga(nome, h, b, tw, tf))
    for h, b, tw, tf in (
        (75, 40, 5.0, 7.0),
        (100, 50, 5.0, 7.5),
        (150, 75, 6.5, 9.5),
        (200, 75, 7.0, 11.0),
        (250, 90, 8.0, 12.5),
        (300, 95, 9.0, 13.5),
    ):
        nome = f"U ideal {h}×{b}×{tw:g}×{tf:g}"
        perfis.append(perfil_u(nome, h, b, tw, tf))
    for h, b, d, t in (
        (75, 40, 15.0, 2.0),
        (100, 40, 15.0, 2.0),
        (100, 50, 17.0, 2.65),
        (150, 50, 17.0, 3.0),
        (200, 75, 20.0, 3.0),
        (250, 85, 25.0, 3.35),
    ):
        nome = f"C ideal {h}×{b}×{d:g}×{t:g}"
        perfis.append(perfil_c_enrijecido(nome, h, b, d, t))
    for d, b, tw, tf in (
        (50, 50, 5.0, 7.0),
        (75, 75, 5.5, 8.0),
        (100, 100, 6.0, 9.0),
        (150, 150, 7.5, 10.5),
        (200, 200, 9.0, 13.0),
    ):
        nome = f"T ideal {d}×{b}×{tw:g}×{tf:g}"
        perfis.append(perfil_t(nome, d, b, tw, tf))
    for diametro in (12.5, 16.0, 19.0, 25.0, 32.0, 38.0, 50.0):
        nome = f"Barra circular Ø{diametro:g}"
        perfis.append(barra_circular(nome, diametro))
    for h, b, t in (
        (40, 20, 2.0),
        (50, 30, 2.0),
        (60, 40, 2.0),
        (80, 40, 3.0),
        (100, 50, 3.0),
        (120, 60, 4.0),
        (150, 100, 4.0),
        (200, 100, 6.0),
        (250, 150, 6.0),
    ):
        nome = f"TR ideal {h}×{b}×{t:g}"
        perfis.append(tubo_retangular(nome, h, b, t))
    for d, t in (
        (33.7, 2.65),
        (42.4, 3.0),
        (48.3, 3.0),
        (60.3, 3.0),
        (76.1, 3.6),
        (88.9, 4.0),
        (114.3, 4.5),
        (139.7, 5.0),
        (168.3, 6.3),
        (219.1, 8.0),
    ):
        nome = f"TC ideal Ø{d:g}×{t:g}"
        perfis.append(tubo_circular(nome, d, t))
    for h, b in ((40, 10), (50, 10), (80, 12), (100, 16), (150, 20)):
        nome = f"Barra {h}×{b}"
        perfis.append(barra_retangular(nome, h, b))
    return {perfil.nome: perfil for perfil in perfis}


CATALOGO_PERFIS = _criar_catalogo()


def obter_perfil(nome: str) -> PerfilAco:
    try:
        return CATALOGO_PERFIS[nome]
    except KeyError as exc:
        raise ValueError(f"Perfil não encontrado: {nome}.") from exc


def catalogo_dataframe() -> pd.DataFrame:
    linhas = []
    for perfil in CATALOGO_PERFIS.values():
        item = asdict(perfil)
        item.update(
            {
                "rx_mm": perfil.rx_mm,
                "ry_mm": perfil.ry_mm,
                "sx_mm3": perfil.sx_mm3,
                "sy_mm3": perfil.sy_mm3,
            }
        )
        linhas.append(item)
    return pd.DataFrame(linhas)
