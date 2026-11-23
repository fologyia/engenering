"""Regiões do esboço: os contornos fechados, o que é aço e o que é furo, e as contas exatas.

**Contornos.** Linhas e arcos que dividem pontas formam um contorno; um círculo é um contorno sozinho.
Linha de construção não conta. Cada ponta precisa de exatamente duas curvas: com uma só o contorno
está aberto, com três ele se divide, e o programa diz onde.

**Aço e furo.** Como numa região de CAD: contorno dentro de contorno é furo, dentro do furo volta a
ser aço. Contornos não podem se cruzar nem encostar; a mensagem diz quais.

**Contas exatas.** Área, centro e inércias saem do contorno pelo teorema de Green, com os arcos
exatos (Gauss-Legendre de 16 pontos em cada arco; nas retas, a conta é polinômio e fecha exata).

**Teste.** Tudo aqui recebe ``k`` desenhos de uma vez, todos com a forma de partida: a mesma
sequência de pedaços e o mesmo furo dentro do mesmo contorno. ``validade`` diz, para cada um, se a
forma continua a mesma, e a folga, a menor distância entre contornos que não se tocam (a parede mais
fina). Quando a folga chega a zero, o furo encostou na borda: lá o desenho deixa de existir.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from core import esboco as eb
from core import geometria_da_secao as gs

N_VOLTA = 144  # segmentos numa volta inteira, quando o contorno vira polígono
_ENCOSTA = 1e-7  # folga abaixo disto, vezes o tamanho do desenho, é encostar
_DOIS_PI = 2.0 * math.pi

_GL16_X, _GL16_W = np.polynomial.legendre.leggauss(16)
_GL16_T = (_GL16_X + 1.0) / 2.0
_GL16_W = _GL16_W / 2.0
_GL3_X, _GL3_W = np.polynomial.legendre.leggauss(3)
_GL3_T = (_GL3_X + 1.0) / 2.0
_GL3_W = _GL3_W / 2.0

# Motivos de um desenho não existir
OK = ""
NAO_FECHOU = "nao_fechou"
DEGENEROU = "degenerou"
AVESSO = "avesso"
ENCOSTOU = "encostou"
SAIU = "saiu"
MOTIVOS = {
    NAO_FECHOU: "as cotas deixam de caber juntas",
    DEGENEROU: "uma linha ou um arco some (fica com tamanho zero)",
    AVESSO: "um contorno vira do avesso",
    ENCOSTOU: "dois contornos encostam (um furo chega na borda ou em outro furo)",
    SAIU: "um furo sai de dentro do contorno",
}


REGRA = "regra:"  # o motivo traz o texto da regra: "regra:parede >= 1,5*d"


def motivo_em_texto(motivo: str) -> str:
    """O motivo de um desenho não existir, em palavras."""
    if motivo.startswith(REGRA):
        return f"a regra de projeto “{motivo[len(REGRA) :]}” deixa de valer"
    return MOTIVOS.get(motivo, motivo)


class ErroDeRegiao(ValueError):
    """O esboço não forma uma seção: a mensagem diz onde."""


@dataclass(frozen=True)
class Pedaco:
    """Um trecho do contorno. ``sentido`` −1: percorrido do fim para o início da curva."""

    curva: str
    tipo: str
    sentido: int
    inicio: str
    fim: str


@dataclass(frozen=True)
class Laco:
    pedacos: tuple[Pedaco, ...] = ()
    circulo: str = ""  # contorno feito de um círculo só


@dataclass(frozen=True)
class Problema:
    tipo: str
    mensagem: str
    onde: tuple[float, float] | None = None
    curvas: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Contornos pela ligação das pontas
# ---------------------------------------------------------------------------


def _uniao(esboco: eb.Esboco) -> dict[str, str]:
    """Pontos ligados por "pontos juntos" contam como um só."""
    pai = {pid: pid for pid in esboco.pontos}

    def raiz(p: str) -> str:
        while pai[p] != p:
            pai[p] = pai[pai[p]]
            p = pai[p]
        return p

    for r in esboco.restricoes:
        if r.tipo == eb.COINCIDENTE:
            for outro in r.pontos[1:]:
                pai[raiz(outro)] = raiz(r.pontos[0])
    return {p: raiz(p) for p in pai}


def _pontas(curva: eb.Curva) -> tuple[str, str]:
    if curva.tipo == eb.LINHA:
        return curva.pontos[0], curva.pontos[1]
    return curva.pontos[1], curva.pontos[2]


def contornos(esboco: eb.Esboco) -> tuple[list[Laco], list[Problema]]:
    """Os contornos fechados e o que impede de fechar (ponta solta, ponta com três curvas)."""
    junto = _uniao(esboco)
    lacos: list[Laco] = []
    problemas: list[Problema] = []
    abertas = [c for c in esboco.curvas if not c.construcao and c.tipo != eb.CIRCULO]
    for curva in esboco.curvas:
        if curva.tipo == eb.CIRCULO and not curva.construcao:
            lacos.append(Laco(circulo=curva.id))
    vizinhos: dict[str, list[tuple[eb.Curva, int]]] = {}
    for curva in abertas:
        a, b = (junto[p] for p in _pontas(curva))
        vizinhos.setdefault(a, []).append((curva, 1))
        vizinhos.setdefault(b, []).append((curva, -1))
    ruins = set()
    for no, lista in vizinhos.items():
        if len(lista) != 2:
            ruins.add(no)
            onde = esboco.pontos[no]
            if len(lista) == 1:
                problemas.append(
                    Problema(
                        "ponta",
                        "O contorno está aberto neste ponto: ligue a ponta a outra curva.",
                        onde,
                        (lista[0][0].id,),
                    )
                )
            else:
                problemas.append(
                    Problema(
                        "bifurcacao",
                        f"{len(lista)} curvas saem do mesmo ponto: um contorno só pode ter duas.",
                        onde,
                        tuple(c.id for c, _ in lista),
                    )
                )
    usadas: set[str] = set()
    for curva in abertas:
        if curva.id in usadas:
            continue
        a, b = (junto[p] for p in _pontas(curva))
        if a in ruins or b in ruins:
            usadas.add(curva.id)
            continue
        pedacos: list[Pedaco] = []
        atual, sentido, inicio = curva, 1, a
        fechou = True
        while True:
            usadas.add(atual.id)
            pa, pb = (junto[p] for p in _pontas(atual))
            de, para = (pa, pb) if sentido == 1 else (pb, pa)
            pedacos.append(Pedaco(atual.id, atual.tipo, sentido, de, para))
            if para == inicio:
                break
            if para in ruins:
                fechou = False
                break
            seguinte = [(c, s) for c, s in vizinhos[para] if c.id != atual.id]
            if not seguinte:
                fechou = False
                break
            atual, s = seguinte[0]
            sentido = s  # s = 1: a curva começa em ``para``
        if fechou:
            lacos.append(Laco(tuple(pedacos)))
    return lacos, problemas


# ---------------------------------------------------------------------------
# A geometria de k desenhos
# ---------------------------------------------------------------------------


def _xy(q: np.ndarray, sistema: eb.Sistema, pid: str) -> np.ndarray:
    i = sistema.colunas[pid]
    return q[:, i : i + 2]


@dataclass
class _Trecho:
    """Um pedaço já com números, de k desenhos: reta de P a Q, ou arco de centro C."""

    tipo: str  # "s" reta, "a" arco
    inicio: str = ""
    fim: str = ""
    p: Any = None
    q: Any = None
    c: Any = None
    r: Any = None
    ta: Any = None  # ângulo de partida, no sentido anti-horário natural
    sw: Any = None  # varredura anti-horária natural, de 0 a 2π
    t0: Any = None  # ângulo de partida no sentido do contorno
    dt: Any = None  # varredura com sinal, no sentido do contorno


def _trechos(q: np.ndarray, sistema: eb.Sistema, laco: Laco) -> list[_Trecho]:
    esboco = sistema.esboco
    k = q.shape[0]
    if laco.circulo:
        curva = esboco.curva(laco.circulo)
        c = _xy(q, sistema, curva.pontos[0])
        r = q[:, sistema.raios[curva.id]]
        zero = np.zeros(k)
        volta = np.full(k, _DOIS_PI)
        return [_Trecho("a", c=c, r=r, ta=zero, sw=volta, t0=zero, dt=volta)]
    saida = []
    for pedaco in laco.pedacos:
        curva = esboco.curva(pedaco.curva)
        if curva.tipo == eb.LINHA:
            a, b = (_xy(q, sistema, p) for p in curva.pontos)
            p, fim = (a, b) if pedaco.sentido == 1 else (b, a)
            saida.append(_Trecho("s", pedaco.inicio, pedaco.fim, p=p, q=fim))
            continue
        c, a, b = (_xy(q, sistema, p) for p in curva.pontos)
        r = np.hypot(a[:, 0] - c[:, 0], a[:, 1] - c[:, 1])
        ta = np.arctan2(a[:, 1] - c[:, 1], a[:, 0] - c[:, 0])
        tb = np.arctan2(b[:, 1] - c[:, 1], b[:, 0] - c[:, 0])
        sw = np.mod(tb - ta, _DOIS_PI)
        if pedaco.sentido == 1:
            t0, dt = ta, sw
        else:
            t0, dt = ta + sw, -sw
        saida.append(_Trecho("a", pedaco.inicio, pedaco.fim, c=c, r=r, ta=ta, sw=sw, t0=t0, dt=dt))
    return saida


def _ponto_do_arco(t: _Trecho, angulo: np.ndarray) -> np.ndarray:
    return np.stack((t.c[:, 0] + t.r * np.cos(angulo), t.c[:, 1] + t.r * np.sin(angulo)), axis=-1)


def _ponta_a(t: _Trecho) -> np.ndarray:
    return t.p if t.tipo == "s" else _ponto_do_arco(t, t.t0)


def _ponta_b(t: _Trecho) -> np.ndarray:
    return t.q if t.tipo == "s" else _ponto_do_arco(t, t.t0 + t.dt)


# ---------------------------------------------------------------------------
# Integrais de Green
# ---------------------------------------------------------------------------


def _integrais(trechos: Sequence[_Trecho], origem: np.ndarray) -> np.ndarray:
    """(k, 6): A, ∫x dA, ∫y dA, ∫y² dA, ∫x² dA, ∫xy dA, no sentido do contorno."""
    k = origem.shape[0]
    total = np.zeros((k, 6))
    for t in trechos:
        if t.tipo == "s":
            nos, pesos = _GL3_T, _GL3_W
            d = t.q - t.p
            x = (t.p[:, 0:1] - origem[:, 0:1]) + nos[None, :] * d[:, 0:1]
            y = (t.p[:, 1:2] - origem[:, 1:2]) + nos[None, :] * d[:, 1:2]
            dx = np.broadcast_to(d[:, 0:1], x.shape)
            dy = np.broadcast_to(d[:, 1:2], x.shape)
        else:
            nos, pesos = _GL16_T, _GL16_W
            angulo = t.t0[:, None] + nos[None, :] * t.dt[:, None]
            cos, sen = np.cos(angulo), np.sin(angulo)
            r = t.r[:, None]
            x = (t.c[:, 0:1] - origem[:, 0:1]) + r * cos
            y = (t.c[:, 1:2] - origem[:, 1:2]) + r * sen
            dx = -r * sen * t.dt[:, None]
            dy = r * cos * t.dt[:, None]
        termos = (
            0.5 * (x * dy - y * dx),
            0.5 * x * x * dy,
            -0.5 * y * y * dx,
            -(y**3) * dx / 3.0,
            x**3 * dy / 3.0,
            0.5 * x * x * y * dy,
        )
        for i, termo in enumerate(termos):
            total[:, i] += termo @ pesos
    return total


@dataclass(frozen=True)
class Exatas:
    """Propriedades da seção de k desenhos, do contorno. Eixos pelo centro de gravidade."""

    area: np.ndarray
    xc: np.ndarray
    yc: np.ndarray
    ix: np.ndarray
    iy: np.ndarray
    ixy: np.ndarray
    x_min: np.ndarray
    x_max: np.ndarray
    y_min: np.ndarray
    y_max: np.ndarray

    @property
    def i1(self) -> np.ndarray:
        return (self.ix + self.iy) / 2.0 + np.hypot((self.ix - self.iy) / 2.0, self.ixy)

    @property
    def i2(self) -> np.ndarray:
        return (self.ix + self.iy) / 2.0 - np.hypot((self.ix - self.iy) / 2.0, self.ixy)


def _no_arco(
    angulo: np.ndarray, ta: np.ndarray, sw: np.ndarray, folga: float = 1e-12
) -> np.ndarray:
    return (np.mod(angulo - ta, _DOIS_PI) <= sw + folga) | (sw >= _DOIS_PI - 1e-12)


# ---------------------------------------------------------------------------
# Distâncias e cruzamentos
# ---------------------------------------------------------------------------


def _dist_ponto_reta(x: np.ndarray, p: np.ndarray, q: np.ndarray) -> np.ndarray:
    d = q - p
    comprimento = np.sum(d * d, axis=1)
    t = np.clip(np.sum((x - p) * d, axis=1) / np.where(comprimento > 0, comprimento, 1.0), 0.0, 1.0)
    perto = p + t[:, None] * d
    return np.hypot(x[:, 0] - perto[:, 0], x[:, 1] - perto[:, 1])


def _dist_ponto_arco(x: np.ndarray, t: _Trecho) -> np.ndarray:
    v = x - t.c
    angulo = np.arctan2(v[:, 1], v[:, 0])
    no_arco = np.abs(np.hypot(v[:, 0], v[:, 1]) - t.r)
    a = _ponto_do_arco(t, t.ta)
    b = _ponto_do_arco(t, t.ta + t.sw)
    pontas = np.minimum(
        np.hypot(x[:, 0] - a[:, 0], x[:, 1] - a[:, 1]),
        np.hypot(x[:, 0] - b[:, 0], x[:, 1] - b[:, 1]),
    )
    return np.where(_no_arco(angulo, t.ta, t.sw), no_arco, pontas)


def _cruz(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]


def _longe_de(x: np.ndarray, nos: Sequence[np.ndarray], tolerancia: float) -> np.ndarray:
    longe = np.ones(x.shape[0], dtype=bool)
    for no in nos:
        longe &= np.hypot(x[:, 0] - no[:, 0], x[:, 1] - no[:, 1]) > tolerancia
    return longe


def _par(
    t1: _Trecho, t2: _Trecho, comuns: Sequence[np.ndarray], tolerancia: float
) -> tuple[np.ndarray, np.ndarray]:
    """(cruza, distância): cruza fora das pontas em comum, e a menor distância quando não há ponta comum."""
    k = (t1.p if t1.tipo == "s" else t1.c).shape[0]
    infinito = np.full(k, np.inf)
    if t1.tipo == "a" and t2.tipo == "s":
        t1, t2 = t2, t1
    with np.errstate(all="ignore"):
        if t1.tipo == "s" and t2.tipo == "s":
            p, q, r, s = t1.p, t1.q, t2.p, t2.q
            d1, d2 = _cruz(q - p, r - p), _cruz(q - p, s - p)
            d3, d4 = _cruz(s - r, p - r), _cruz(s - r, q - r)
            if comuns:
                # Ponta comum: só cruza se uma andar por cima da outra (as duas na mesma direção).
                no = comuns[0]
                u = np.where(_longe_de(p, [no], tolerancia)[:, None], p, q) - no
                w = np.where(_longe_de(r, [no], tolerancia)[:, None], r, s) - no
                alinhadas = np.abs(_cruz(u, w)) <= 1e-9 * np.hypot(*u.T) * np.hypot(*w.T)
                cruza = alinhadas & (np.sum(u * w, axis=1) > 0.0)
                return cruza, infinito
            cruza = (d1 * d2 < 0.0) & (d3 * d4 < 0.0)
            distancia = np.minimum.reduce(
                [
                    _dist_ponto_reta(p, r, s),
                    _dist_ponto_reta(q, r, s),
                    _dist_ponto_reta(r, p, q),
                    _dist_ponto_reta(s, p, q),
                ]
            )
            return cruza, np.where(cruza, 0.0, distancia)
        if t1.tipo == "s":  # reta e arco
            p, q, arco = t1.p, t1.q, t2
            d = q - p
            f = p - arco.c
            a = np.sum(d * d, axis=1)
            b = 2.0 * np.sum(f * d, axis=1)
            c = np.sum(f * f, axis=1) - arco.r**2
            cruza = np.zeros(k, dtype=bool)
            if comuns:
                # A ponta comum é uma raiz: a outra sai da soma das raízes, sem raiz quadrada, e a
                # emenda tangente (raiz dupla) não vira cruzamento por arredondamento.
                no = comuns[0]
                na_ponta_p = ~_longe_de(p, [no], tolerancia)
                t_no = np.where(na_ponta_p, 0.0, 1.0)
                t = -b / a - t_no
                x = p + t[:, None] * d
                ang = np.arctan2(x[:, 1] - arco.c[:, 1], x[:, 0] - arco.c[:, 0])
                cruza = (
                    (t >= -1e-12)
                    & (t <= 1.0 + 1e-12)
                    & _no_arco(ang, arco.ta, arco.sw)
                    & _longe_de(x, comuns, tolerancia)
                )
                return cruza, infinito
            disc = b * b - 4.0 * a * c
            raiz = np.sqrt(np.maximum(disc, 0.0))
            for sinal in (-1.0, 1.0):
                t = (-b + sinal * raiz) / (2.0 * a)
                x = p + t[:, None] * d
                ang = np.arctan2(x[:, 1] - arco.c[:, 1], x[:, 0] - arco.c[:, 0])
                cruza |= (
                    (disc >= 0.0)
                    & (t >= -1e-12)
                    & (t <= 1.0 + 1e-12)
                    & _no_arco(ang, arco.ta, arco.sw)
                )
            pe = np.clip(-np.sum(f * d, axis=1) / np.where(a > 0, a, 1.0), 0.0, 1.0)
            perto = p + pe[:, None] * d
            v = perto - arco.c
            distancia_c = np.hypot(v[:, 0], v[:, 1])
            ang = np.arctan2(v[:, 1], v[:, 0])
            pelo_pe = np.where(
                (distancia_c >= arco.r) & _no_arco(ang, arco.ta, arco.sw),
                distancia_c - arco.r,
                np.inf,
            )
            distancia = np.minimum.reduce(
                [
                    _dist_ponto_arco(p, arco),
                    _dist_ponto_arco(q, arco),
                    _dist_ponto_reta(_ponto_do_arco(arco, arco.ta), p, q),
                    _dist_ponto_reta(_ponto_do_arco(arco, arco.ta + arco.sw), p, q),
                    pelo_pe,
                ]
            )
            return cruza, np.where(cruza, 0.0, distancia)
        # dois arcos
        v = t2.c - t1.c
        d = np.hypot(v[:, 0], v[:, 1])
        mesmo_centro = d <= 1e-12 * np.maximum(t1.r, 1.0)
        u = v / np.where(mesmo_centro, 1.0, d)[:, None]
        cruza = np.zeros(k, dtype=bool)
        if comuns:
            # Os dois círculos passam pela ponta comum: o outro encontro é o espelho dela na reta dos
            # centros. Na emenda tangente ele cai em cima da ponta, e não conta.
            for no in comuns:
                w = no - t1.c
                projecao = t1.c + np.sum(w * u, axis=1)[:, None] * u
                x = 2.0 * projecao - no
                a1 = np.arctan2(x[:, 1] - t1.c[:, 1], x[:, 0] - t1.c[:, 0])
                a2 = np.arctan2(x[:, 1] - t2.c[:, 1], x[:, 0] - t2.c[:, 0])
                cruza |= (
                    ~mesmo_centro
                    & _no_arco(a1, t1.ta, t1.sw)
                    & _no_arco(a2, t2.ta, t2.sw)
                    & _longe_de(x, comuns, tolerancia)
                )
        else:
            a = (t1.r**2 - t2.r**2 + d * d) / (2.0 * np.where(mesmo_centro, 1.0, d))
            h2 = t1.r**2 - a * a
            normal = np.stack((-u[:, 1], u[:, 0]), axis=1)
            base = t1.c + a[:, None] * u
            for sinal in (-1.0, 1.0):
                x = base + sinal * np.sqrt(np.maximum(h2, 0.0))[:, None] * normal
                a1 = np.arctan2(x[:, 1] - t1.c[:, 1], x[:, 0] - t1.c[:, 0])
                a2 = np.arctan2(x[:, 1] - t2.c[:, 1], x[:, 0] - t2.c[:, 0])
                cruza |= (
                    ~mesmo_centro
                    & (h2 >= 0.0)
                    & _no_arco(a1, t1.ta, t1.sw)
                    & _no_arco(a2, t2.ta, t2.sw)
                )
        # No mesmo círculo, os dois arcos não podem andar um por cima do outro.
        mesmo_circulo = mesmo_centro & (np.abs(t1.r - t2.r) <= 1e-9 * np.maximum(t1.r, 1.0))
        meio2 = t2.ta + t2.sw / 2.0
        meio1 = t1.ta + t1.sw / 2.0
        sobrepoe = mesmo_circulo & (
            _no_arco(meio2, t1.ta, t1.sw, -1e-9) | _no_arco(meio1, t2.ta, t2.sw, -1e-9)
        )
        cruza |= sobrepoe
        if comuns:
            return cruza, infinito
        candidatos = [
            _dist_ponto_arco(_ponto_do_arco(t1, t1.ta), t2),
            _dist_ponto_arco(_ponto_do_arco(t1, t1.ta + t1.sw), t2),
            _dist_ponto_arco(_ponto_do_arco(t2, t2.ta), t1),
            _dist_ponto_arco(_ponto_do_arco(t2, t2.ta + t2.sw), t1),
        ]
        for s1 in (-1.0, 1.0):
            for s2 in (-1.0, 1.0):
                x1 = t1.c + (s1 * t1.r)[:, None] * u
                x2 = t2.c + (s2 * t2.r)[:, None] * u
                a1 = np.arctan2(s1 * u[:, 1], s1 * u[:, 0])
                a2 = np.arctan2(s2 * u[:, 1], s2 * u[:, 0])
                serve = ~mesmo_centro & _no_arco(a1, t1.ta, t1.sw) & _no_arco(a2, t2.ta, t2.sw)
                candidatos.append(
                    np.where(serve, np.hypot(x1[:, 0] - x2[:, 0], x1[:, 1] - x2[:, 1]), np.inf)
                )
        concentricos = mesmo_centro & ~mesmo_circulo
        candidatos.append(np.where(concentricos, np.abs(t1.r - t2.r), np.inf))
        distancia = np.minimum.reduce(candidatos)
        return cruza, np.where(cruza, 0.0, distancia)


# ---------------------------------------------------------------------------
# Polígonos
# ---------------------------------------------------------------------------


def _poligono(trechos: Sequence[_Trecho], divisoes: Sequence[int]) -> np.ndarray:
    """(k, V, 2): os vértices do contorno, com cada arco em ``divisoes`` segmentos."""
    blocos = []
    for t, n in zip(trechos, divisoes, strict=True):
        if t.tipo == "s":
            blocos.append(t.p[:, None, :])
            continue
        fracoes = np.arange(n) / n
        angulo = t.t0[:, None] + fracoes[None, :] * t.dt[:, None]
        blocos.append(
            np.stack(
                (
                    t.c[:, 0:1] + t.r[:, None] * np.cos(angulo),
                    t.c[:, 1:2] + t.r[:, None] * np.sin(angulo),
                ),
                axis=-1,
            )
        )
    return np.concatenate(blocos, axis=1)


def _dentro(ponto: np.ndarray, poligono: np.ndarray) -> np.ndarray:
    """(k,): o ponto está dentro do polígono (regra par-ímpar)."""
    x, y = ponto[:, 0:1], ponto[:, 1:2]
    a = poligono
    b = np.roll(poligono, -1, axis=1)
    cruza = (a[:, :, 1] > y) != (b[:, :, 1] > y)
    with np.errstate(all="ignore"):
        xi = (b[:, :, 0] - a[:, :, 0]) * (y - a[:, :, 1]) / (b[:, :, 1] - a[:, :, 1]) + a[:, :, 0]
    return (np.sum(cruza & (x < xi), axis=1) % 2) == 1


# ---------------------------------------------------------------------------
# Regiões
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Avaliacao:
    """k desenhos: se existem, por que não, a folga e as contas exatas."""

    valido: np.ndarray
    motivo: tuple[str, ...]
    folga: np.ndarray
    exatas: Exatas


class Regioes:
    """A forma de partida do esboço: contornos, quem é furo, e como avaliar k desenhos de uma vez."""

    def __init__(self, sistema: eb.Sistema, q_base: np.ndarray | None = None) -> None:
        self.sistema = sistema
        self.esboco = sistema.esboco
        self.tamanho = sistema.tamanho
        lacos, problemas = contornos(self.esboco)
        self.lacos = lacos
        self.problemas = list(problemas)
        q = (sistema.q0 if q_base is None else np.asarray(q_base, float))[None, :]
        self.q_base = q[0]
        if not lacos:
            if not self.problemas:
                self.problemas.append(
                    Problema("vazio", "Desenhe um contorno fechado: ele vira a seção.")
                )
            self.profundidade: tuple[int, ...] = ()
            self.orientacao: tuple[float, ...] = ()
            self.divisoes: tuple[tuple[int, ...], ...] = ()
            self._dentro_base = np.zeros((0, 0), dtype=bool)
            return
        trechos = [_trechos(q, sistema, laco) for laco in lacos]
        self.divisoes = tuple(
            tuple(
                0 if t.tipo == "s" else max(2, math.ceil(float(abs(t.dt[0])) / _DOIS_PI * N_VOLTA))
                for t in lista
            )
            for lista in trechos
        )
        self._varredura_base = [
            [None if t.tipo == "s" else float(t.sw[0]) for t in lista] for lista in trechos
        ]
        areas = [float(_integrais(lista, np.zeros((1, 2)))[0, 0]) for lista in trechos]
        self.orientacao = tuple(1.0 if a >= 0.0 else -1.0 for a in areas)
        poligonos = [_poligono(lista, n) for lista, n in zip(trechos, self.divisoes, strict=True)]
        dentro = np.zeros((len(lacos), len(lacos)), dtype=bool)
        for i, lista in enumerate(trechos):
            ponto = _ponta_a(lista[0])
            for j, poligono in enumerate(poligonos):
                if i != j:
                    dentro[i, j] = bool(_dentro(ponto, poligono)[0])
        self._dentro_base = dentro
        self.profundidade = tuple(int(dentro[i].sum()) for i in range(len(lacos)))
        for i, profundidade in enumerate(self.profundidade):
            if profundidade >= 2 and profundidade % 2 == 0:
                self.problemas.append(
                    Problema(
                        "ilha",
                        "Há uma peça solta dentro de um furo: a seção precisa ser uma peça só.",
                        _onde(_ponta_a(trechos[i][0])[0]),
                    )
                )
        avaliacao = self.avaliar(q, np.ones(1, dtype=bool))
        if not bool(avaliacao.valido[0]):
            self.problemas.extend(self._onde_cruza(trechos))
            if not any(p.tipo in ("cruzam", "avesso") for p in self.problemas):
                motivo = avaliacao.motivo[0]
                self.problemas.append(
                    Problema(
                        "forma", f"O desenho não forma uma seção: {MOTIVOS.get(motivo, motivo)}."
                    )
                )

    @property
    def ok(self) -> bool:
        return not self.problemas

    def exigir(self) -> None:
        if self.problemas:
            raise ErroDeRegiao(self.problemas[0].mensagem)

    def _onde_cruza(self, trechos: list[list[_Trecho]]) -> list[Problema]:
        q = self.q_base[None, :]
        tolerancia = _ENCOSTA * self.tamanho
        for (i, a), (j, b), comuns_ids in self._pares_ids(trechos):
            comuns = [self._no(q, pid) for pid in comuns_ids]
            cruza, distancia = _par(a, b, comuns, tolerancia)
            if bool(cruza[0]) or (not comuns and float(distancia[0]) <= tolerancia):
                onde = _ponta_a(a)[0]
                nomes = tuple(
                    p.curva for p in (self._pedaco(i, a), self._pedaco(j, b)) if p is not None
                )
                return [
                    Problema(
                        "cruzam",
                        "Dois contornos se cruzam ou encostam: use Unir (U, no menu do Aparar) "
                        "para virar uma peça só, ou separe.",
                        (float(onde[0]), float(onde[1])),
                        nomes,
                    )
                ]
        return []

    def _pedaco(self, laco: int, trecho: _Trecho) -> Pedaco | None:
        lista = self.lacos[laco]
        if lista.circulo:
            return Pedaco(lista.circulo, eb.CIRCULO, 1, "", "")
        for pedaco in lista.pedacos:
            if pedaco.inicio == trecho.inicio and pedaco.fim == trecho.fim:
                return pedaco
        return None

    # -- avaliar k desenhos ------------------------------------------------------------------------

    def trechos(self, q: np.ndarray) -> list[list[_Trecho]]:
        return [_trechos(q, self.sistema, laco) for laco in self.lacos]

    def avaliar(self, q: np.ndarray, convergiu: np.ndarray) -> Avaliacao:
        q = np.atleast_2d(q)
        k = q.shape[0]
        motivo = np.full(k, OK, dtype=object)
        motivo[~convergiu] = NAO_FECHOU
        trechos = self.trechos(q)
        tamanho = self.tamanho
        with np.errstate(all="ignore"):
            # Pedaços que somem, arcos que viram do outro lado
            for lista, base in zip(trechos, self._varredura_base, strict=True):
                for t, sw0 in zip(lista, base, strict=True):
                    if t.tipo == "s":
                        ruim = np.hypot(*(t.q - t.p).T) <= _ENCOSTA * tamanho
                    else:
                        ruim = ~(t.r > _ENCOSTA * tamanho)
                        if sw0 is not None and sw0 < _DOIS_PI - 1e-9:
                            ruim |= (t.sw <= 1e-9) | (np.abs(t.sw - sw0) >= math.pi)
                    motivo[(motivo == OK) & ruim] = DEGENEROU
            origem = self._origem(trechos)
            parciais = [_integrais(lista, origem) for lista in trechos]
            for parcial, sinal in zip(parciais, self.orientacao, strict=True):
                avesso = ~(parcial[:, 0] * sinal > (_ENCOSTA * tamanho) ** 2)
                motivo[(motivo == OK) & avesso] = AVESSO
            folga = np.full(k, np.inf)
            cruza_algum = np.zeros(k, dtype=bool)
            for (_, a), (_, b), comuns_ids in self._pares_ids(trechos):
                comuns = [self._no(q, pid) for pid in comuns_ids]
                cruza, distancia = _par(a, b, comuns, _ENCOSTA * tamanho)
                cruza_algum |= cruza
                folga = np.minimum(folga, distancia)
            encostou = cruza_algum | ~(folga > _ENCOSTA * tamanho)
            motivo[(motivo == OK) & encostou] = ENCOSTOU
            if len(self.lacos) > 1:
                poligonos = [
                    _poligono(lista, n) for lista, n in zip(trechos, self.divisoes, strict=True)
                ]
                for i, lista in enumerate(trechos):
                    ponto = _ponta_a(lista[0])
                    for j, poligono in enumerate(poligonos):
                        if i != j:
                            mudou = _dentro(ponto, poligono) != self._dentro_base[i, j]
                            motivo[(motivo == OK) & mudou] = SAIU
            total = np.zeros((k, 6))
            for parcial, sinal, profundidade in zip(
                parciais, self.orientacao, self.profundidade, strict=True
            ):
                total += parcial * (sinal * (-1.0) ** profundidade)
            area = total[:, 0]
            xc_rel = total[:, 1] / area
            yc_rel = total[:, 2] / area
            ix = total[:, 3] - area * yc_rel**2
            iy = total[:, 4] - area * xc_rel**2
            ixy = total[:, 5] - area * xc_rel * yc_rel
            x_min, x_max, y_min, y_max = _extremos(trechos)
        valido = motivo == OK
        exatas = Exatas(
            area,
            xc_rel + origem[:, 0],
            yc_rel + origem[:, 1],
            ix,
            iy,
            ixy,
            x_min,
            x_max,
            y_min,
            y_max,
        )
        folga = np.where(valido, np.where(np.isfinite(folga), folga, np.inf), -1.0)
        return Avaliacao(valido, tuple(str(m) for m in motivo), folga, exatas)

    def _pares_ids(self, trechos: list[list[_Trecho]]):
        todos = [(i, t) for i, lista in enumerate(trechos) for t in lista]
        for x in range(len(todos)):
            for y in range(x + 1, len(todos)):
                (i, a), (j, b) = todos[x], todos[y]
                comuns = sorted(({a.inicio, a.fim} - {""}) & ({b.inicio, b.fim} - {""}))
                yield (i, a), (j, b), comuns

    def _no(self, q: np.ndarray, pid: str) -> np.ndarray:
        return _xy(q, self.sistema, pid)

    def _origem(self, trechos: list[list[_Trecho]]) -> np.ndarray:
        """Um ponto perto do desenho: as integrais ficam sem números enormes que se cancelam."""
        pontas = [_ponta_a(t) for lista in trechos for t in lista]
        return np.mean(np.stack(pontas, axis=0), axis=0)

    # -- saídas ------------------------------------------------------------------------------------

    def poligonos(self, q: np.ndarray) -> list[np.ndarray]:
        return [
            _poligono(lista, n)
            for lista, n in zip(self.trechos(np.atleast_2d(q)), self.divisoes, strict=True)
        ]

    def partes(self, q: np.ndarray) -> list:
        """As partes da malha de um desenho: contorno de aço e furos. Círculo inteiro fica círculo."""
        from core import secao_desenhada as sd

        q = np.atleast_2d(q)[:1]
        partes = []
        trechos = self.trechos(q)
        for laco, lista, n, profundidade in zip(
            self.lacos, trechos, self.divisoes, self.profundidade, strict=True
        ):
            furo = profundidade % 2 == 1
            if laco.circulo:
                t = lista[0]
                partes.append(
                    sd.Parte(
                        sd.CIRC,
                        float(t.c[0, 0]),
                        float(t.c[0, 1]),
                        float(2.0 * t.r[0]),
                        float(2.0 * t.r[0]),
                        furo=furo,
                    )
                )
                continue
            vertices = _poligono(lista, n)[0]
            partes.append(
                sd.Parte(
                    sd.POLI, furo=furo, pontos=tuple((float(x), float(y)) for x, y in vertices)
                )
            )
        return partes

    def geometria(self, q: np.ndarray, i: int, xc: float, yc: float) -> gs.Geometria:
        """O contorno de um desenho para as faixas, com a origem no centro de gravidade.

        Círculo inteiro vai exato (a corda 2·√(r² − y²)); o resto, como polígono.
        """
        um = np.atleast_2d(q)[i : i + 1]
        trechos = self.trechos(um)
        cheios: list[Any] = []
        vazados: list[Any] = []
        circulos: list[tuple[float, float, float, bool]] = []
        for laco, lista, n, profundidade in zip(
            self.lacos, trechos, self.divisoes, self.profundidade, strict=True
        ):
            furo = profundidade % 2 == 1
            if laco.circulo:
                t = lista[0]
                circulos.append((float(t.c[0, 0]) - xc, float(t.c[0, 1]) - yc, float(t.r[0]), furo))
                continue
            contorno = _poligono(lista, n)[0] - np.array([xc, yc])
            (vazados if furo else cheios).append(contorno)
        return gs.Geometria(tuple(cheios), tuple(vazados), (), tuple(circulos))


def _onde(ponto: np.ndarray) -> tuple[float, float]:
    return float(ponto[0]), float(ponto[1])


def _extremos(trechos: list[list[_Trecho]]) -> tuple[np.ndarray, ...]:
    """x e y mínimos e máximos do contorno, com os arcos que passam pelo topo ou pelo lado."""
    xs, ys = [], []
    for lista in trechos:
        for t in lista:
            if t.tipo == "s":
                xs += [t.p[:, 0], t.q[:, 0]]
                ys += [t.p[:, 1], t.q[:, 1]]
                continue
            a, b = _ponto_do_arco(t, t.ta), _ponto_do_arco(t, t.ta + t.sw)
            xs += [a[:, 0], b[:, 0]]
            ys += [a[:, 1], b[:, 1]]
            for angulo, lista_eixo, eixo, sinal in (
                (0.0, xs, 0, 1.0),
                (math.pi, xs, 0, -1.0),
                (math.pi / 2.0, ys, 1, 1.0),
                (-math.pi / 2.0, ys, 1, -1.0),
            ):
                passa = _no_arco(np.full_like(t.ta, angulo), t.ta, t.sw)
                valor = t.c[:, eixo] + sinal * t.r
                lista_eixo.append(np.where(passa, valor, np.nan))
    x, y = np.stack(xs), np.stack(ys)
    return np.nanmin(x, 0), np.nanmax(x, 0), np.nanmin(y, 0), np.nanmax(y, 0)
