"""A seção em faixas horizontais: largura b(y), momento estático Q(y) e as tensões ao longo da altura.

Serve a toda seção com contorno conhecido. O eixo y é a direção da flexão, para cima, com a origem
no centro geométrico. Com b(y) em mãos, τ = V·Q/(I·b) deixa de ser fórmula de retângulo: vale para I,
U, T, tubos e círculo, e ∫τ·b dy devolve V, o que os testes usam como conferência.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

Ponto = tuple[float, float]

#: Faixas ao longo da altura. Nas formas retas é exato; no círculo, o erro fica abaixo de 0,1 %.
_FAIXAS = 800


@dataclass(frozen=True)
class Geometria:
    """Contorno da seção. ``aneis`` são (raio externo, raio interno), centrados na origem."""

    cheios: tuple[tuple[Ponto, ...], ...] = ()
    vazados: tuple[tuple[Ponto, ...], ...] = ()
    aneis: tuple[tuple[float, float], ...] = ()

    def _cordas(self, y: np.ndarray, poligonos: Sequence[Sequence[Ponto]]) -> np.ndarray:
        total = np.zeros_like(y)
        for poligono in poligonos:
            soma = np.zeros_like(y)
            for k in range(len(poligono)):
                (x1, y1), (x2, y2) = poligono[k - 1], poligono[k]
                if y1 == y2:
                    continue
                sobe = (y1 <= y) & (y < y2)
                desce = (y2 <= y) & (y < y1)
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                soma += np.where(sobe, x, 0.0) - np.where(desce, x, 0.0)
            total += np.abs(soma)
        return total

    def largura(self, y: np.ndarray) -> np.ndarray:
        """b(y): a soma das cordas, tirando os vazados."""
        b = self._cordas(y, self.cheios) - self._cordas(y, self.vazados)
        for externo, interno in self.aneis:
            b = b + 2.0 * np.sqrt(np.maximum(externo**2 - y**2, 0.0))
            b = b - 2.0 * np.sqrt(np.maximum(interno**2 - y**2, 0.0))
        return np.maximum(b, 0.0)

    def extremos_y(self) -> tuple[float, float]:
        ys = [p[1] for contorno in self.cheios for p in contorno]
        ys += [s * externo for externo, _ in self.aneis for s in (-1.0, 1.0)]
        return min(ys), max(ys)

    def extremos_x(self) -> tuple[float, float]:
        xs = [p[0] for contorno in self.cheios for p in contorno]
        xs += [s * externo for externo, _ in self.aneis for s in (-1.0, 1.0)]
        return min(xs), max(xs)

    def deitada(self) -> Geometria:
        """A mesma seção com flexão em torno do outro eixo: o antigo x vira a altura."""

        def virar(contorno: Sequence[Ponto]) -> tuple[Ponto, ...]:
            return tuple((-y, x) for x, y in contorno)

        return Geometria(
            tuple(virar(c) for c in self.cheios),
            tuple(virar(c) for c in self.vazados),
            self.aneis,
        )


def retangulo(b: float, h: float) -> Geometria:
    return Geometria((((-b / 2, -h / 2), (b / 2, -h / 2), (b / 2, h / 2), (-b / 2, h / 2)),))


def circulo(d: float, d_interno: float = 0.0) -> Geometria:
    return Geometria(aneis=((d / 2.0, d_interno / 2.0),))


def tubo_retangular(b: float, h: float, t: float) -> Geometria:
    externo = retangulo(b, h).cheios
    interno = retangulo(b - 2.0 * t, h - 2.0 * t).cheios
    return Geometria(externo, interno)


def perfil_i(h: float, b: float, tf: float, tw: float) -> Geometria:
    a, c = h / 2.0, b / 2.0
    t = tw / 2.0
    return Geometria(
        (
            (
                (-c, -a), (c, -a), (c, -a + tf), (t, -a + tf), (t, a - tf), (c, a - tf),
                (c, a), (-c, a), (-c, a - tf), (-t, a - tf), (-t, -a + tf), (-c, -a + tf),
            ),
        )
    )  # fmt: skip


def perfil_u(h: float, b: float, tf: float, tw: float) -> Geometria:
    """Com a alma à esquerda e a origem em G: a flexão é em torno do eixo forte."""
    a = h / 2.0
    area = 2.0 * b * tf + (h - 2.0 * tf) * tw
    x = (b**2 * tf + (h - 2.0 * tf) * tw**2 / 2.0) / area
    return Geometria(
        (
            (
                (-x, -a), (b - x, -a), (b - x, -a + tf), (tw - x, -a + tf), (tw - x, a - tf),
                (b - x, a - tf), (b - x, a), (-x, a),
            ),
        )
    )  # fmt: skip


@dataclass(frozen=True)
class Faixas:
    """A seção cortada ao longo da altura, com y medido do centro geométrico e decrescente."""

    y: np.ndarray
    b: np.ndarray
    q: np.ndarray
    area: float
    inercia: float
    modulo_plastico: float
    y_centro: float

    @property
    def y_topo(self) -> float:
        return float(self.y[0])

    @property
    def y_base(self) -> float:
        return float(self.y[-1])

    def tau(self, cortante: float) -> np.ndarray:
        """τ = V·Q/(I·b). Onde não há material, zero."""
        with np.errstate(divide="ignore", invalid="ignore"):
            valor = np.where(self.b > 0, cortante * self.q / (self.inercia * self.b), 0.0)
        return np.abs(valor)


def faixas_da_secao(geometria: Geometria) -> Faixas:
    """Integra por faixas. Cada mudança de largura entra nos dois lados, para o salto ficar nítido."""
    baixo, alto = geometria.extremos_y()
    altura = alto - baixo
    if altura <= 0:
        raise ValueError("A seção não tem altura.")
    folga = altura * 1e-7
    quebras = [p[1] for contorno in (*geometria.cheios, *geometria.vazados) for p in contorno]
    quebras += [s * r for _, r in geometria.aneis if r > 0 for s in (-1.0, 1.0)]
    niveis = np.linspace(baixo, alto, _FAIXAS + 1)
    extras = [v for q in quebras for v in (q - folga, q + folga) if baixo < v < alto]
    if baixo < 0.0 < alto:
        extras.append(0.0)  # o centro é onde τ costuma ter o pico
    y = np.unique(np.concatenate([niveis, np.array(extras, dtype=float)]))[
        ::-1
    ]  # de cima para baixo
    # A largura é lida um fio para dentro: exatamente na borda, a corda da forma é zero.
    b = geometria.largura(np.clip(y, baixo + folga, alto - folga))
    # Em cada faixa, b é a média e as integrais de y e y² são exatas: nas formas retas, tudo fecha.
    media = (b[:-1] + b[1:]) / 2.0
    area_faixas = media * (y[:-1] - y[1:])
    area = float(area_faixas.sum())
    if area <= 0:
        raise ValueError("A seção não tem área.")
    y_centro = float((media * (y[:-1] ** 2 - y[1:] ** 2) / 2.0).sum() / area)
    y_rel = y - y_centro
    primeiro = media * (y_rel[:-1] ** 2 - y_rel[1:] ** 2) / 2.0
    q = np.concatenate([[0.0], np.cumsum(primeiro)])
    inercia = float((media * (y_rel[:-1] ** 3 - y_rel[1:] ** 3) / 3.0).sum())
    # Eixo plástico: a linha que divide a área ao meio. u·|u|/2 é a primitiva de |u|.
    acumulada = np.concatenate([[0.0], np.cumsum(area_faixas)])
    y_plastico = float(np.interp(area / 2.0, acumulada, y_rel))
    u = y_rel - y_plastico
    plastico = float((media * (u[:-1] * np.abs(u[:-1]) - u[1:] * np.abs(u[1:])) / 2.0).sum())
    return Faixas(y_rel, b, q, area, inercia, plastico, y_centro)


@dataclass(frozen=True)
class Tensoes:
    """σ, τ e von Mises ao longo da altura, em MPa, com y em mm."""

    y: np.ndarray
    sigma: np.ndarray
    tau: np.ndarray
    mises: np.ndarray
    tem_tau: bool

    @property
    def tau_max(self) -> float:
        return float(self.tau.max())

    @property
    def y_tau_max(self) -> float:
        return float(self.y[int(np.argmax(self.tau))])

    @property
    def mises_max(self) -> float:
        return float(self.mises.max())

    @property
    def indice_critico(self) -> int:
        return int(np.argmax(self.mises))


def tensoes_ao_longo(
    faixas: Faixas, sigma_sup: float, sigma_inf: float, cortante: float, tau_extra: float = 0.0
) -> Tensoes:
    """σ em linha reta entre as fibras dadas, para os números baterem com os da conta da seção.

    ``tau_extra`` soma um cisalhamento uniforme, como o da torção no caixão.
    """
    y = faixas.y
    fracao = (faixas.y_topo - y) / (faixas.y_topo - faixas.y_base)
    sigma = sigma_sup + (sigma_inf - sigma_sup) * fracao
    tau = faixas.tau(cortante) + abs(tau_extra)
    return Tensoes(y, sigma, tau, np.sqrt(sigma**2 + 3.0 * tau**2), True)


def linha_neutra(sigma_sup: float, sigma_inf: float, y_topo: float, y_base: float) -> float | None:
    """Onde σ zera, ou ``None`` se a seção inteira fica do mesmo lado."""
    if sigma_sup == sigma_inf or sigma_sup * sigma_inf > 0:
        return None
    return y_topo + (y_base - y_topo) * sigma_sup / (sigma_sup - sigma_inf)
