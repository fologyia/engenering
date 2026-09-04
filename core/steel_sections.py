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


def perfil_i_simetrico(
    nome: str,
    altura_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
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
        familia="I duplamente simétrico",
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
