"""Formas que se sobrepõem viram um esboço de contornos limpos.

As partes da prancheta antiga (retângulo, círculo, polígono, cheias ou furo) se sobrepõem à vontade:
o I é feito de três chapas encostadas. O esboço quer contornos que não se cruzam nem se encostam.
Aqui as bordas são partidas onde se encontram e fica só o trecho que separa aço de vazio — aço é
estar dentro de alguma forma cheia e fora de todo furo. Sai um esboço de linhas, arcos e círculos,
com deitada e em pé nas retas que já eram assim, e sem cotas (as medidas antigas não eram cotas).

É a mesma ideia do "Unir" da prancheta (``components/esboco/edicao.js``), com a diferença de que aqui
cada forma já diz se é aço ou furo.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from core import esboco as eb

Ponto = tuple[float, float]
_DOIS_PI = 2.0 * math.pi


@dataclass(frozen=True)
class Forma:
    """Um contorno fechado: polígono (``pontos``) ou círculo (``centro`` e ``raio``)."""

    pontos: tuple[Ponto, ...] = ()
    centro: Ponto | None = None
    raio: float = 0.0
    furo: bool = False

    def contem(self, x: float, y: float) -> bool:
        if self.centro is not None:
            return math.hypot(x - self.centro[0], y - self.centro[1]) < self.raio
        dentro = False
        pts = self.pontos
        j = len(pts) - 1
        for i, (xi, yi) in enumerate(pts):
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
        return dentro


@dataclass(frozen=True)
class _Borda:
    """Uma reta de a a b (t de 0 a 1) ou um círculo inteiro (t = ângulo de 0 a 2π)."""

    forma: int
    a: Ponto = (0.0, 0.0)
    b: Ponto = (0.0, 0.0)
    centro: Ponto | None = None
    raio: float = 0.0

    @property
    def circulo(self) -> bool:
        return self.centro is not None

    def no(self, t: float) -> Ponto:
        if self.centro is not None:
            return (
                self.centro[0] + self.raio * math.cos(t),
                self.centro[1] + self.raio * math.sin(t),
            )
        return (self.a[0] + t * (self.b[0] - self.a[0]), self.a[1] + t * (self.b[1] - self.a[1]))

    def param(self, x: float, y: float) -> float:
        if self.centro is not None:
            return math.atan2(y - self.centro[1], x - self.centro[0]) % _DOIS_PI
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        return ((x - self.a[0]) * dx + (y - self.a[1]) * dy) / (dx * dx + dy * dy or 1.0)

    def distancia(self, x: float, y: float) -> float:
        if self.centro is not None:
            return abs(math.hypot(x - self.centro[0], y - self.centro[1]) - self.raio)
        t = min(max(self.param(x, y), 0.0), 1.0)
        px, py = self.no(t)
        return math.hypot(px - x, py - y)


def _encontros(g: _Borda, h: _Borda) -> list[Ponto]:
    """Onde as duas bordas se cruzam (a reta e o círculo inteiros: quem chama filtra)."""
    if g.circulo and not h.circulo:
        return _encontros(h, g)
    if not g.circulo and not h.circulo:
        d1 = (g.b[0] - g.a[0], g.b[1] - g.a[1])
        d2 = (h.b[0] - h.a[0], h.b[1] - h.a[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12 * math.hypot(*d1) * math.hypot(*d2):
            return []  # paralelas: as pontas em cima da outra entram à parte
        t = ((h.a[0] - g.a[0]) * d2[1] - (h.a[1] - g.a[1]) * d2[0]) / den
        return [g.no(t)]
    if not g.circulo:
        assert h.centro is not None
        d = (g.b[0] - g.a[0], g.b[1] - g.a[1])
        f = (g.a[0] - h.centro[0], g.a[1] - h.centro[1])
        a = d[0] * d[0] + d[1] * d[1]
        b = 2.0 * (f[0] * d[0] + f[1] * d[1])
        c = f[0] * f[0] + f[1] * f[1] - h.raio * h.raio
        disc = b * b - 4.0 * a * c
        if disc < -1e-12 * b * b or a == 0.0:
            return []
        raiz = math.sqrt(max(disc, 0.0))
        ts = (
            [-b / (2 * a)]
            if raiz < 1e-12 * abs(b)
            else [(-b - raiz) / (2 * a), (-b + raiz) / (2 * a)]
        )
        return [g.no(t) for t in ts]
    assert g.centro is not None and h.centro is not None
    dx, dy = h.centro[0] - g.centro[0], h.centro[1] - g.centro[1]
    dist = math.hypot(dx, dy)
    soma = g.raio + h.raio
    if dist < 1e-12 or dist > soma * (1 + 1e-9) or dist < abs(g.raio - h.raio) - 1e-9 * soma:
        return []
    ao_longo = (g.raio * g.raio - h.raio * h.raio + dist * dist) / (2 * dist)
    altura = math.sqrt(max(g.raio * g.raio - ao_longo * ao_longo, 0.0))
    mx, my = g.centro[0] + ao_longo * dx / dist, g.centro[1] + ao_longo * dy / dist
    if altura < 1e-12 * g.raio:
        return [(mx, my)]
    return [
        (mx - altura * dy / dist, my + altura * dx / dist),
        (mx + altura * dy / dist, my - altura * dx / dist),
    ]


@dataclass
class _Trecho:
    borda: _Borda
    t0: float
    t1: float

    def ponta(self, fim: bool) -> Ponto:
        return self.borda.no(self.t1 if fim else self.t0)


@dataclass
class _Construtor:
    """Junta pontos iguais (pela tolerância) e escreve o esboço."""

    tolerancia: float
    pontos: dict[str, Ponto] = field(default_factory=lambda: {eb.ORIGEM: (0.0, 0.0)})
    curvas: list[eb.Curva] = field(default_factory=list)
    restricoes: list[eb.Restricao] = field(default_factory=list)

    def ponto(self, xy: Ponto, *, juntar: bool = True) -> str:
        if juntar:
            for pid, (x, y) in self.pontos.items():
                if pid != eb.ORIGEM and math.hypot(x - xy[0], y - xy[1]) <= self.tolerancia:
                    return pid
        pid = f"p{len(self.pontos)}"
        self.pontos[pid] = (float(xy[0]), float(xy[1]))
        return pid

    def curva(self, tipo: str, pontos: tuple[str, ...], raio: float = 0.0) -> str:
        cid = f"c{len(self.curvas) + 1}"
        self.curvas.append(eb.Curva(cid, tipo, pontos, raio))
        return cid

    def restricao(self, tipo: str, curvas: tuple[str, ...]) -> None:
        self.restricoes.append(eb.Restricao(f"r{len(self.restricoes) + 1}", tipo, curvas=curvas))


def _tamanho(formas: Sequence[Forma]) -> float:
    xs: list[float] = []
    ys: list[float] = []
    for f in formas:
        if f.centro is not None:
            xs += [f.centro[0] - f.raio, f.centro[0] + f.raio]
            ys += [f.centro[1] - f.raio, f.centro[1] + f.raio]
        else:
            xs += [p[0] for p in f.pontos]
            ys += [p[1] for p in f.pontos]
    if not xs:
        return 100.0
    d = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return d if d > 1e-9 else 100.0


def _bordas(formas: Sequence[Forma]) -> list[_Borda]:
    bordas: list[_Borda] = []
    for k, f in enumerate(formas):
        if f.centro is not None:
            if f.raio > 0:
                bordas.append(_Borda(k, centro=f.centro, raio=f.raio))
            continue
        pts = list(f.pontos)
        for a, b in zip(pts, (*pts[1:], pts[0]), strict=True):
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 0:
                bordas.append(_Borda(k, a=a, b=b))
    return bordas


def _cortes(bordas: list[_Borda], tolerancia: float) -> list[list[float]]:
    """Os parâmetros em que cada borda é partida: encontros e pontas de outras em cima dela."""
    cortes: list[list[float]] = [[] for _ in bordas]
    folga = 1e-9
    for i, g in enumerate(bordas):
        for j, h in enumerate(bordas):
            if i == j:
                continue
            achados = []
            for x, y in _encontros(g, h):
                tg, th = g.param(x, y), h.param(x, y)
                dentro_g = g.circulo or -folga <= tg <= 1 + folga
                dentro_h = h.circulo or -folga <= th <= 1 + folga
                if dentro_g and dentro_h:
                    achados.append((x, y))
            if not h.circulo:
                for x, y in (h.a, h.b):
                    t = g.param(x, y)
                    if (g.circulo or -folga <= t <= 1 + folga) and g.distancia(x, y) <= tolerancia:
                        achados.append((x, y))
            cortes[i] += [g.param(x, y) for x, y in achados]
    return cortes


def _trechos(bordas: list[_Borda], cortes: list[list[float]]) -> list[_Trecho]:
    trechos: list[_Trecho] = []
    for borda, ts in zip(bordas, cortes, strict=True):
        if borda.circulo:
            marcas = sorted({round(t % _DOIS_PI, 12) for t in ts})
            if not marcas:
                trechos.append(_Trecho(borda, 0.0, _DOIS_PI))
                continue
            for k, t in enumerate(marcas):
                fim = marcas[k + 1] if k + 1 < len(marcas) else marcas[0] + _DOIS_PI
                if fim - t > 1e-12:
                    trechos.append(_Trecho(borda, t, fim))
            continue
        marcas = sorted({0.0, 1.0, *(round(t, 12) for t in ts if 1e-9 < t < 1 - 1e-9)})
        for t0, t1 in zip(marcas, marcas[1:], strict=False):
            trechos.append(_Trecho(borda, t0, t1))
    return trechos


def esboco_unido(formas: Sequence[Forma]) -> eb.Esboco:
    """O esboço com o contorno do aço das formas: cheias somam, furos tiram."""
    tamanho = _tamanho(formas)
    tolerancia = 1e-7 * tamanho
    cheias = [f for f in formas if not f.furo]
    furos = [f for f in formas if f.furo]

    def aco(x: float, y: float) -> bool:
        return any(f.contem(x, y) for f in cheias) and not any(f.contem(x, y) for f in furos)

    bordas = _bordas(formas)
    ficam: list[_Trecho] = []
    meios: list[Ponto] = []
    eps = 1e-6 * tamanho
    for trecho in _trechos(bordas, _cortes(bordas, tolerancia)):
        tm = 0.5 * (trecho.t0 + trecho.t1)
        dt = 1e-4 * (trecho.t1 - trecho.t0)
        (x0, y0), (x1, y1) = trecho.borda.no(tm - dt), trecho.borda.no(tm + dt)
        comprimento = math.hypot(x1 - x0, y1 - y0) or 1.0
        nx, ny = -(y1 - y0) / comprimento * eps, (x1 - x0) / comprimento * eps
        mx, my = trecho.borda.no(tm)
        if aco(mx + nx, my + ny) == aco(mx - nx, my - ny):
            continue  # aço dos dois lados (de dentro) ou de nenhum
        if any(math.hypot(px - mx, py - my) <= 10 * tolerancia for px, py in meios):
            continue  # a borda comum de duas formas alinhadas: fica uma só
        ficam.append(trecho)
        meios.append((mx, my))
    return _escrever(_juntar_retas(ficam, tolerancia), tolerancia)


def _juntar_retas(trechos: list[_Trecho], tolerancia: float) -> list[_Trecho]:
    """Duas retas em fila que só se encontram uma na outra viram uma (o corte que sobrou some)."""
    retas = [t for t in trechos if not t.borda.circulo]
    arcos = [t for t in trechos if t.borda.circulo]

    def perto(p: Ponto, q: Ponto) -> bool:
        return math.hypot(p[0] - q[0], p[1] - q[1]) <= tolerancia

    def juntar_uma() -> bool:
        nonlocal retas
        for reta in retas:
            for fim in (False, True):
                xy = reta.ponta(fim)
                donos = [
                    (j, f)
                    for j, t in enumerate(retas)
                    for f in (False, True)
                    if perto(t.ponta(f), xy)
                ]
                if len(donos) != 2 or donos[0][0] == donos[1][0]:
                    continue
                if any(perto(t.ponta(f), xy) for t in arcos for f in (False, True)):
                    continue
                (j1, f1), (j2, f2) = donos
                a, b = retas[j1].ponta(not f1), retas[j2].ponta(not f2)
                u, v = _menos(xy, a), _menos(b, xy)
                cruz = u[0] * v[1] - u[1] * v[0]
                if (
                    abs(cruz) > 1e-9 * math.hypot(*u) * math.hypot(*v)
                    or u[0] * v[0] + u[1] * v[1] <= 0
                ):
                    continue
                nova = _Trecho(_Borda(retas[j1].borda.forma, a=a, b=b), 0.0, 1.0)
                retas = [t for n, t in enumerate(retas) if n not in (j1, j2)] + [nova]
                return True
        return False

    while juntar_uma():
        pass
    return retas + arcos


def _menos(p: Ponto, q: Ponto) -> Ponto:
    return (p[0] - q[0], p[1] - q[1])


def _escrever(trechos: list[_Trecho], tolerancia: float) -> eb.Esboco:
    c = _Construtor(tolerancia)
    centros: dict[tuple[int, float, float], str] = {}
    for t in trechos:
        borda = t.borda
        if borda.centro is None:
            a, b = c.ponto(t.ponta(False)), c.ponto(t.ponta(True))
            if a == b:
                continue
            cid = c.curva(eb.LINHA, (a, b))
            (xa, ya), (xb, yb) = c.pontos[a], c.pontos[b]
            escala = max(abs(xb - xa), abs(yb - ya))
            if abs(ya - yb) <= 1e-9 * escala:
                c.restricao(eb.HORIZONTAL, (cid,))
            elif abs(xa - xb) <= 1e-9 * escala:
                c.restricao(eb.VERTICAL, (cid,))
            continue
        chave = (borda.forma, borda.centro[0], borda.centro[1])
        if chave not in centros:
            centros[chave] = c.ponto(borda.centro, juntar=False)
        centro = centros[chave]
        if t.t1 - t.t0 >= _DOIS_PI - 1e-12:
            c.curva(eb.CIRCULO, (centro,), borda.raio)
            continue
        inicio, fim = c.ponto(t.ponta(False)), c.ponto(t.ponta(True))
        if inicio != fim:
            c.curva(eb.ARCO, (centro, inicio, fim))
    return eb.Esboco(c.pontos, tuple(c.curvas), tuple(c.restricoes))


def formas_das_partes(partes: Sequence[object]) -> list[Forma]:
    """As partes da prancheta antiga (``core.secao_desenhada.Parte``) como formas."""
    from core import secao_desenhada as sd

    formas: list[Forma] = []
    for parte in partes:
        assert isinstance(parte, sd.Parte)
        if parte.forma == sd.CIRC:
            formas.append(Forma(centro=(parte.x, parte.y), raio=parte.b / 2.0, furo=parte.furo))
        else:
            cantos = tuple((float(x), float(y)) for x, y in parte.cantos)
            formas.append(Forma(pontos=cantos, furo=parte.furo))
    return formas


def anexar(base: dict, outro: dict) -> dict:
    """``outro`` (um esboço em dicionário) entra em ``base`` com nomes novos, sem mexer em ``base``."""
    import copy

    novo = copy.deepcopy(base)
    for chave in ("pontos", "curvas", "restricoes", "cotas", "variaveis"):
        novo.setdefault(chave, {} if chave == "pontos" else [])

    def proximo(prefixo: str, existentes: list[str]) -> int:
        maior = 0
        for nome in existentes:
            if nome.startswith(prefixo) and nome[len(prefixo) :].isdigit():
                maior = max(maior, int(nome[len(prefixo) :]))
        return maior + 1

    n_p = proximo("p", list(novo["pontos"]))
    n_c = proximo("c", [c["id"] for c in novo["curvas"]])
    n_r = proximo("r", [r["id"] for r in novo["restricoes"]])
    n_d = proximo("d", [d["id"] for d in novo["cotas"]])
    mapa_p: dict[str, str] = {eb.ORIGEM: eb.ORIGEM}
    for k, (pid, xy) in enumerate(p for p in outro.get("pontos", {}).items() if p[0] != eb.ORIGEM):
        mapa_p[pid] = f"p{n_p + k}"
        novo["pontos"][mapa_p[pid]] = list(xy)
    mapa_c: dict[str, str] = {}
    for k, curva in enumerate(outro.get("curvas", [])):
        mapa_c[curva["id"]] = f"c{n_c + k}"
        novo["curvas"].append(
            {**curva, "id": mapa_c[curva["id"]], "pontos": [mapa_p[p] for p in curva["pontos"]]}
        )
    for k, r in enumerate(outro.get("restricoes", [])):
        novo["restricoes"].append(
            {
                **r,
                "id": f"r{n_r + k}",
                "pontos": [mapa_p[p] for p in r.get("pontos", [])],
                "curvas": [mapa_c[x] for x in r.get("curvas", [])],
            }
        )
    for k, d in enumerate(outro.get("cotas", [])):
        novo["cotas"].append(
            {
                **d,
                "id": f"d{n_d + k}",
                "pontos": [mapa_p[p] for p in d.get("pontos", [])],
                "curvas": [mapa_c[x] for x in d.get("curvas", [])],
            }
        )
    conhecidas = {v["nome"] for v in novo["variaveis"]}
    novo["variaveis"] += [v for v in outro.get("variaveis", []) if v["nome"] not in conhecidas]
    return novo
