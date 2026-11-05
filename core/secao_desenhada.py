"""Desenhar uma seção: partes → malha → propriedades → perfil do catálogo.

A seção é uma lista de partes (retângulo, círculo, polígono; cheias ou furos), em mm. Parte por cima
de parte conta uma vez só e o furo tira de tudo o que estiver embaixo, porque a conta é feita sobre
a figura final e não parte a parte.

**Malha.** Uma grade cartesiana com linhas sobre as arestas das partes: seção de retângulos fica
exata, sem aproximação de contorno. Aresta curva ou inclinada corta as células, e a célula cortada é
integrada por dentro (subpontos): é o método das células finitas. Como o problema de torção só tem
condição natural no contorno, ele dispensa uma malha que acompanhe a forma, inclusive em seção
fechada, com vários furos ou em mais de uma célula.

**Torção.** Elementos Q4 resolvem a função de empenamento ω (∇²ω = 0):

* ``J = Ix + Iy − ωᵀ f``, a constante de torção de Saint-Venant;
* centro de cisalhamento pela condição ∫ω_s·x = ∫ω_s·y = 0 (Trefftz/Vlasov);
* ``Cw = ∫ω_s² dA``.

Só usa numpy. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from core.steel_sections import DENSIDADE_ACO_KG_M3, PerfilAco, familia_do_perfil

RET = "ret"
CIRC = "circ"
POLI = "poli"
FORMAS = (RET, CIRC, POLI)

FAMILIA_LIVRE = "Personalizado (desenhada)"

_GAUSS = (0.5 - 0.5 / math.sqrt(3.0), 0.5 + 0.5 / math.sqrt(3.0))


class ErroDeSecao(ValueError):
    """A seção não pode ser calculada: a mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------
# Partes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Parte:
    """Uma parte da seção. ``x, y`` é o centro; no círculo, ``b`` é o diâmetro."""

    forma: str
    x: float = 0.0
    y: float = 0.0
    b: float = 0.0
    h: float = 0.0
    giro: float = 0.0
    furo: bool = False
    pontos: tuple[tuple[float, float], ...] = ()
    grupo: int = 0

    @property
    def cantos(self) -> list[tuple[float, float]]:
        """Vértices do retângulo girado ou do polígono."""
        if self.forma == POLI:
            return list(self.pontos)
        c, s = math.cos(math.radians(self.giro)), math.sin(math.radians(self.giro))
        meio_b, meio_h = self.b / 2.0, self.h / 2.0
        return [
            (self.x + dx * c - dy * s, self.y + dx * s + dy * c)
            for dx, dy in (
                (-meio_b, -meio_h),
                (meio_b, -meio_h),
                (meio_b, meio_h),
                (-meio_b, meio_h),
            )
        ]

    def caixa(self) -> tuple[float, float, float, float]:
        """(x mínimo, y mínimo, x máximo, y máximo)."""
        if self.forma == CIRC:
            r = self.b / 2.0
            return self.x - r, self.y - r, self.x + r, self.y + r
        xs, ys = zip(*self.cantos, strict=True)
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def reta(self) -> bool:
        """Só arestas horizontais e verticais: a grade acompanha a parte sem aproximação."""
        if self.forma == RET:
            return self.giro == 0.0
        if self.forma == CIRC:
            return False
        anel = [*self.pontos, self.pontos[0]]
        return all(
            abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
            for a, b in zip(anel, anel[1:], strict=False)
        )

    def contem(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        if self.forma == CIRC:
            return (x - self.x) ** 2 + (y - self.y) ** 2 <= (self.b / 2.0) ** 2
        if self.forma == RET:
            c, s = math.cos(math.radians(self.giro)), math.sin(math.radians(self.giro))
            dx, dy = x - self.x, y - self.y
            return (np.abs(dx * c + dy * s) <= self.b / 2.0) & (
                np.abs(-dx * s + dy * c) <= self.h / 2.0
            )
        dentro = np.zeros(np.broadcast(x, y).shape, dtype=bool)
        anel = [*self.pontos, self.pontos[0]]
        for (x1, y1), (x2, y2) in zip(anel, anel[1:], strict=False):
            if y1 == y2:
                continue
            cruza = (y1 > y) != (y2 > y)
            dentro ^= cruza & (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1)
        return dentro

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "forma": self.forma,
            "x": self.x,
            "y": self.y,
            "b": self.b,
            "h": self.h,
            "giro": self.giro,
            "furo": self.furo,
            "pontos": [list(p) for p in self.pontos],
            "grupo": self.grupo,
        }


def _finito(valor: Any, rotulo: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroDeSecao(f"{rotulo} precisa ser um número.") from None
    if not math.isfinite(numero):
        raise ErroDeSecao(f"{rotulo} precisa ser um número finito.")
    return numero


def parte_de_dicionario(dados: Mapping[str, Any]) -> Parte:
    """Valida uma parte vinda da prancheta, da tabela ou de um desenho salvo."""
    forma = str(dados.get("forma", RET))
    if forma not in FORMAS:
        raise ErroDeSecao(f"Forma desconhecida: {forma!r}.")
    furo = bool(dados.get("furo", False))
    grupo = int(_finito(dados.get("grupo") or 0, "O grupo"))
    if forma == POLI:
        pontos = tuple(
            (_finito(p[0], "O ponto x"), _finito(p[1], "O ponto y"))
            for p in dados.get("pontos") or ()
        )
        if len(pontos) < 3:
            raise ErroDeSecao("O polígono precisa de ao menos 3 pontos.")
        soma = sum(
            a[0] * b[1] - b[0] * a[1] for a, b in zip(pontos, (*pontos[1:], pontos[0]), strict=True)
        )
        if abs(soma) < 1e-9:
            raise ErroDeSecao("O polígono não tem área: confira os pontos.")
        return Parte(POLI, furo=furo, pontos=pontos, grupo=grupo)
    x = _finito(dados.get("x", 0.0), "A posição x")
    y = _finito(dados.get("y", 0.0), "A posição y")
    b = _finito(dados.get("b", 0.0), "A largura")
    if b <= 0.0:
        raise ErroDeSecao("A largura (ou diâmetro) de cada parte precisa ser maior que zero.")
    if forma == CIRC:
        return Parte(CIRC, x, y, b, b, furo=furo, grupo=grupo)
    h = _finito(dados.get("h", 0.0), "A altura")
    if h <= 0.0:
        raise ErroDeSecao("A altura de cada parte precisa ser maior que zero.")
    giro = _finito(dados.get("giro") or 0.0, "O giro") % 180.0
    if abs(giro - 90.0) < 1e-9:  # virar a parte é trocar b por h: continua reta
        b, h, giro = h, b, 0.0
    return Parte(RET, x, y, b, h, 0.0 if abs(giro) < 1e-9 else giro, furo, grupo=grupo)


def partes_de_lista(lista: Iterable[Mapping[str, Any]]) -> list[Parte]:
    return [parte_de_dicionario(item) for item in lista]


def caixa_das_partes(partes: Sequence[Parte]) -> tuple[float, float, float, float]:
    caixas = [p.caixa() for p in partes]
    return (
        min(c[0] for c in caixas),
        min(c[1] for c in caixas),
        max(c[2] for c in caixas),
        max(c[3] for c in caixas),
    )


# ---------------------------------------------------------------------------
# Malha
# ---------------------------------------------------------------------------


def _linhas(cortes: Iterable[float], passo: float, minimo: int, tamanho: float) -> np.ndarray:
    """Linhas da grade: passam em todos os cortes e nenhuma célula fica maior que o passo."""
    tolerancia = tamanho * 1e-7
    limpos: list[float] = []
    for corte in sorted(cortes):
        if not limpos or corte - limpos[-1] > tolerancia:
            limpos.append(float(corte))
    saida = [limpos[0]]
    for a, b in zip(limpos, limpos[1:], strict=False):
        n = max(minimo, math.ceil((b - a) / passo))
        saida.extend(np.linspace(a, b, n + 1)[1:].tolist())
    return np.array(saida)


def _ocupacao(partes: Sequence[Parte], xs: np.ndarray, ys: np.ndarray, n: int) -> np.ndarray:
    """Quais subpontos de cada célula têm aço: (células x, células y, n, n)."""
    fracao = (np.arange(n) + 0.5) / n
    px = (xs[:-1, None] + np.diff(xs)[:, None] * fracao).reshape(len(xs) - 1, 1, n, 1)
    py = (ys[:-1, None] + np.diff(ys)[:, None] * fracao).reshape(1, len(ys) - 1, 1, n)
    cheio = np.zeros((len(xs) - 1, len(ys) - 1, n, n), dtype=bool)
    for parte in partes:
        if not parte.furo:
            cheio |= parte.contem(px, py)
    for parte in partes:
        if parte.furo:
            cheio &= ~parte.contem(px, py)
    return cheio


def _pedacos(ativo: np.ndarray) -> int:
    """Quantos pedaços soltos a seção tem (células ligadas por um lado, não por um canto)."""
    faltam = ativo.copy()
    pedacos = 0
    nx, ny = ativo.shape
    while faltam.any():
        pedacos += 1
        pilha = [tuple(int(v) for v in np.argwhere(faltam)[0])]
        faltam[pilha[0]] = False
        while pilha:
            i, j = pilha.pop()
            for k, m in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= k < nx and 0 <= m < ny and faltam[k, m]:
                    faltam[k, m] = False
                    pilha.append((k, m))
    return pedacos


@dataclass(slots=True)
class Malha:
    xs: np.ndarray
    ys: np.ndarray
    ativo: np.ndarray  # (células x, células y): tem aço
    conexao: np.ndarray  # (células ativas, 4): nó global de cada canto
    no_x: np.ndarray
    no_y: np.ndarray
    ponto_celula: np.ndarray  # pontos de integração
    ponto_x: np.ndarray
    ponto_y: np.ndarray
    ponto_peso: np.ndarray
    ponto_n: np.ndarray  # (pontos, 4)
    ponto_dx: np.ndarray
    ponto_dy: np.ndarray
    faixas: np.ndarray  # (retângulos, 4): x0, x1, y0, y1 da seção em pedaços inteiros
    curvas: bool
    cheia: np.ndarray  # células ativas sem corte


def _pontos_da_celula(
    xi: np.ndarray, eta: np.ndarray, dx: np.ndarray, dy: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Funções de forma Q4 e derivadas (nós: base esq., base dir., topo dir., topo esq.)."""
    n = np.stack(((1 - xi) * (1 - eta), xi * (1 - eta), xi * eta, (1 - xi) * eta), axis=1)
    d_x = np.stack((eta - 1, 1 - eta, eta, -eta), axis=1) / dx[:, None]
    d_y = np.stack((xi - 1, -xi, xi, 1 - xi), axis=1) / dy[:, None]
    return n, d_x, d_y


def montar_malha(partes: Sequence[Parte]) -> Malha:
    cheias = [p for p in partes if not p.furo]
    if not cheias:
        raise ErroDeSecao("Desenhe ao menos uma parte cheia: só furo não forma uma seção.")
    x0, y0, x1, y1 = caixa_das_partes(cheias)
    tamanho = max(x1 - x0, y1 - y0)
    curvas = not all(p.reta for p in partes)

    cortes_x = {x0, x1}
    cortes_y = {y0, y1}
    for parte in partes:
        a, b, c, d = parte.caixa()
        for valor, conjunto in ((a, cortes_x), (c, cortes_x), (b, cortes_y), (d, cortes_y)):
            limite = (x0, x1) if conjunto is cortes_x else (y0, y1)
            if limite[0] < valor < limite[1]:
                conjunto.add(valor)
        if parte.forma == POLI:
            for px, py in parte.pontos:
                if x0 < px < x1:
                    cortes_x.add(px)
                if y0 < py < y1:
                    cortes_y.add(py)

    if curvas:
        # O passo sai da espessura média (2A/perímetro): parede fina curva pede célula pequena.
        piloto = tamanho / 110.0
        xs = _linhas(cortes_x, piloto, 1, tamanho)
        ys = _linhas(cortes_y, piloto, 1, tamanho)
        fino = _ocupacao(partes, xs, ys, 4)
        parcial = fino.mean(axis=(2, 3))
        area = float((parcial * np.outer(np.diff(xs), np.diff(ys))).sum())
        cortadas = int(((parcial > 0) & (parcial < 1)).sum())
        perimetro = max(cortadas * piloto, 1e-9)
        passo = float(np.clip(2.0 * area / perimetro / 3.0, tamanho / 230.0, tamanho / 70.0))
        xs = _linhas(cortes_x, passo, 1, tamanho)
        ys = _linhas(cortes_y, passo, 1, tamanho)
        subdivisoes = 6
    else:
        passo = tamanho / 42.0
        xs = _linhas(cortes_x, passo, 3, tamanho)
        ys = _linhas(cortes_y, passo, 3, tamanho)
        subdivisoes = 1

    ocupado = _ocupacao(partes, xs, ys, subdivisoes)
    contagem = ocupado.sum(axis=(2, 3))
    total = subdivisoes**2
    ativo = contagem > 0
    if not ativo.any():
        raise ErroDeSecao("Os furos tiraram toda a seção.")

    i, j = np.nonzero(ativo)
    dx_cel, dy_cel = np.diff(xs)[i], np.diff(ys)[j]
    nos = len(ys)
    brutos = np.stack(
        (i * nos + j, (i + 1) * nos + j, (i + 1) * nos + j + 1, i * nos + j + 1), axis=1
    )
    unicos, inverso = np.unique(brutos, return_inverse=True)
    conexao = inverso.reshape(brutos.shape)
    no_x, no_y = xs[unicos // nos], ys[unicos % nos]

    cheia = contagem[i, j] == total
    celulas_cheias = np.nonzero(cheia)[0]
    g0, g1 = _GAUSS
    gx = np.array([g0, g1, g0, g1])
    gy = np.array([g0, g0, g1, g1])
    cel = [np.repeat(celulas_cheias, 4)]
    xi = [np.tile(gx, len(celulas_cheias))]
    eta = [np.tile(gy, len(celulas_cheias))]
    peso = [np.repeat(dx_cel[cheia] * dy_cel[cheia] / 4.0, 4)]

    faixas = [
        np.stack(
            (xs[i[cheia]], xs[i[cheia] + 1], ys[j[cheia]], ys[j[cheia] + 1]),
            axis=1,
        )
    ]
    cortadas_idx = np.nonzero(~cheia)[0]
    if len(cortadas_idx):
        fracao = (np.arange(subdivisoes) + 0.5) / subdivisoes
        sub = ocupado[i[cortadas_idx], j[cortadas_idx]]
        c, a, b = np.nonzero(sub)
        locais = cortadas_idx[c]
        cel.append(locais)
        xi.append(fracao[a])
        eta.append(fracao[b])
        area_sub = dx_cel[locais] * dy_cel[locais] / total
        peso.append(area_sub)
        ex = xs[i[locais]] + fracao[a] * dx_cel[locais]
        ey = ys[j[locais]] + fracao[b] * dy_cel[locais]
        mx, my = dx_cel[locais] / subdivisoes / 2.0, dy_cel[locais] / subdivisoes / 2.0
        faixas.append(np.stack((ex - mx, ex + mx, ey - my, ey + my), axis=1))

    ponto_celula = np.concatenate(cel)
    ponto_xi, ponto_eta = np.concatenate(xi), np.concatenate(eta)
    d_x, d_y = dx_cel[ponto_celula], dy_cel[ponto_celula]
    ponto_n, ponto_dx, ponto_dy = _pontos_da_celula(ponto_xi, ponto_eta, d_x, d_y)
    return Malha(
        xs=xs,
        ys=ys,
        ativo=ativo,
        conexao=conexao,
        no_x=no_x,
        no_y=no_y,
        ponto_celula=ponto_celula,
        ponto_x=xs[i[ponto_celula]] + ponto_xi * d_x,
        ponto_y=ys[j[ponto_celula]] + ponto_eta * d_y,
        ponto_peso=np.concatenate(peso),
        ponto_n=ponto_n,
        ponto_dx=ponto_dx,
        ponto_dy=ponto_dy,
        faixas=np.concatenate(faixas),
        curvas=curvas,
        cheia=cheia,
    )


# ---------------------------------------------------------------------------
# Empenamento
# ---------------------------------------------------------------------------


def _resolver_empenamento(malha: Malha, f: np.ndarray) -> np.ndarray:
    """Resolve K ω = f por gradiente conjugado. A constante de ω é livre: a média sai a cada passo."""
    celulas = len(malha.conexao)
    k_el = np.zeros((celulas, 4, 4))
    for a in range(4):
        for b in range(a, 4):
            termo = malha.ponto_peso * (
                malha.ponto_dx[:, a] * malha.ponto_dx[:, b]
                + malha.ponto_dy[:, a] * malha.ponto_dy[:, b]
            )
            soma = np.bincount(malha.ponto_celula, termo, minlength=celulas)
            k_el[:, a, b] = soma
            k_el[:, b, a] = soma
    # Célula com fiapo de aço: uma rigidez mínima evita nó quase solto.
    k_el += 1e-9 * k_el.max() * np.eye(4)

    n = len(f)
    conexao = malha.conexao
    planos = conexao.ravel()
    diagonal = np.bincount(planos, np.einsum("eii->ei", k_el).ravel(), minlength=n)

    def aplicar(u: np.ndarray) -> np.ndarray:
        locais = np.einsum("eij,ej->ei", k_el, u[conexao])
        return np.bincount(planos, locais.ravel(), minlength=n)

    u = np.zeros(n)
    r = f - f.mean()
    z = r / diagonal
    p = z.copy()
    rz = float(r @ z)
    alvo = 1e-20 * max(rz, 1e-300)
    for _ in range(6 * n):
        ap = aplicar(p)
        alfa = rz / float(p @ ap)
        u += alfa * p
        r -= alfa * ap
        r -= r.mean()
        z = r / diagonal
        novo = float(r @ z)
        if novo < alvo:
            break
        p = z + (novo / rz) * p
        rz = novo
    return u


# ---------------------------------------------------------------------------
# Propriedades
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Propriedades:
    area: float
    xc: float  # centro de gravidade, nas coordenadas do desenho
    yc: float
    ix: float
    iy: float
    ixy: float
    i1: float  # inércias principais
    i2: float
    angulo: float  # graus, do eixo x até o eixo principal maior
    wx_topo: float
    wx_base: float
    wy_direita: float
    wy_esquerda: float
    zx: float
    zy: float
    j: float
    cw: float
    x_s: float  # centro de cisalhamento medido do centro de gravidade
    y_s: float
    w_torcao: float
    qx: float  # momento estático na linha do centro de gravidade
    qy: float
    bx: float  # largura de aço na linha do centro de gravidade
    by: float
    largura: float
    altura: float
    x0: float  # canto da caixa envolvente
    y0: float
    espessura_media: float
    pedacos: int

    @property
    def rx(self) -> float:
        return math.sqrt(self.ix / self.area)

    @property
    def ry(self) -> float:
        return math.sqrt(self.iy / self.area)

    @property
    def r_min(self) -> float:
        return math.sqrt(self.i2 / self.area)

    @property
    def wx(self) -> float:
        return min(self.wx_topo, self.wx_base)

    @property
    def wy(self) -> float:
        return min(self.wy_direita, self.wy_esquerda)

    @property
    def area_cortante_x(self) -> float:
        """Área de cortante vertical que dá o τ máximo da fórmula V·Q/(I·b)."""
        return self.ix * self.bx / self.qx if self.qx > 0 else 0.0

    @property
    def eixos_girados(self) -> bool:
        return abs(self.ixy) > 1e-4 * math.sqrt(self.ix * self.iy)

    def massa(self, densidade: float = DENSIDADE_ACO_KG_M3) -> float:
        return self.area * densidade * 1e-6


def _modulo_plastico(a: np.ndarray, b: np.ndarray, largura: np.ndarray) -> float:
    """Z de faixas [a, b] na direção da flexão: acha a linha de áreas iguais e soma os braços."""
    area_faixa = (b - a) * largura
    meio = float(area_faixa.sum()) / 2.0
    baixo, alto = float(a.min()), float(b.max())
    for _ in range(60):
        p = (baixo + alto) / 2.0
        if float((np.clip(p - a, 0.0, b - a) * largura).sum()) < meio:
            baixo = p
        else:
            alto = p
    cruza = (a < p) & (p < b)
    braco = np.where(
        cruza, ((b - p) ** 2 + (p - a) ** 2) / 2.0, (b - a) * np.abs((a + b) / 2.0 - p)
    )
    return float((braco * largura).sum())


def _momento_estatico(a: np.ndarray, b: np.ndarray, largura: np.ndarray, c: float) -> float:
    """Q da parte acima de ``c``."""
    baixo = np.maximum(a, c)
    alto = np.maximum(b, c)
    return float((((alto - c) ** 2 - (baixo - c) ** 2) / 2.0 * largura).sum())


def _largura_na_linha(a: np.ndarray, b: np.ndarray, largura: np.ndarray, c: float) -> float:
    """Aço que uma linha em ``c`` atravessa. Em cima de uma emenda de células, conta o lado menor."""
    folga = float((b - a).min()) * 1e-3
    return min(
        float(largura[(a <= c + s * folga) & (c + s * folga < b)].sum()) for s in (-1.0, 1.0)
    )


def _derivadas_nos_nos(
    malha: Malha, valores: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """∂/∂x e ∂/∂y nos nós das células cheias: (d_x, d_y, índices dos nós).

    A tensão de torção é máxima na superfície, e os pontos de integração ficam para dentro dela: lá
    uma chapa com 3 células na espessura mostra 9 % a menos. No nó, a média das células vizinhas
    chega à superfície. Sem células cheias (parede curva muito fina), a resposta sai vazia, e quem
    chama fica com os pontos de integração.
    """
    i, j = np.nonzero(malha.ativo)
    indices = np.nonzero(malha.cheia)[0]
    if len(indices) < 20:
        return np.zeros(0), np.zeros(0), np.zeros(0, dtype=int)
    dx, dy = np.diff(malha.xs)[i[indices]], np.diff(malha.ys)[j[indices]]
    conexao = malha.conexao[indices]
    nos = len(malha.no_x)
    soma_x, soma_y = np.zeros(nos), np.zeros(nos)
    contagem = np.bincount(conexao.ravel(), minlength=nos)
    for canto, (xi, eta) in enumerate(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        _, d_x, d_y = _pontos_da_celula(
            np.full(len(indices), xi), np.full(len(indices), eta), dx, dy
        )
        locais = valores[conexao]
        no = conexao[:, canto]
        soma_x += np.bincount(no, (d_x * locais).sum(axis=1), minlength=nos)
        soma_y += np.bincount(no, (d_y * locais).sum(axis=1), minlength=nos)
    usados = np.nonzero(contagem)[0]
    return soma_x[usados] / contagem[usados], soma_y[usados] / contagem[usados], usados


@dataclass(slots=True)
class Analise:
    """As propriedades e o que os mapas de tensão precisam da malha."""

    partes: tuple[Parte, ...]
    prop: Propriedades
    malha: Malha
    gradiente: np.ndarray  # |∇ω + (−y, x)| nos pontos de ``gradiente_x``, ``gradiente_y``
    gradiente_x: np.ndarray
    gradiente_y: np.ndarray
    gradiente_max: float  # sem os cantos vivos reentrantes, onde a teoria dá infinito
    torcao_x: np.ndarray  # o vetor ∇ω + (−y, x): torção e cortante se somam ponto a ponto
    torcao_y: np.ndarray


def analisar(partes: Sequence[Parte]) -> Analise:
    """Todas as propriedades da seção desenhada."""
    malha = montar_malha(partes)
    w, x, y = malha.ponto_peso, malha.ponto_x, malha.ponto_y
    area = float(w.sum())
    if area <= 0.0:
        raise ErroDeSecao("A seção ficou sem área.")
    xc, yc = float((w * x).sum()) / area, float((w * y).sum()) / area
    u, v = x - xc, y - yc
    ix, iy = float((w * v * v).sum()), float((w * u * u).sum())
    ixy = float((w * u * v).sum())
    if ix <= 0.0 or iy <= 0.0:
        raise ErroDeSecao("A seção resultou em inércia nula: confira as partes.")
    media = (ix + iy) / 2.0
    raio = math.hypot((ix - iy) / 2.0, ixy)
    angulo = 0.5 * math.degrees(math.atan2(-2.0 * ixy, ix - iy)) if raio > 1e-9 * media else 0.0

    rx0, rx1, ry0, ry1 = malha.faixas.T
    largura_x, largura_y = rx1 - rx0, ry1 - ry0
    x_min, x_max, y_min, y_max = rx0.min(), rx1.max(), ry0.min(), ry1.max()

    # f = ∫(∂N/∂x·y − ∂N/∂y·x); os termos ficam sobre o centro de gravidade.
    celulas = malha.conexao[malha.ponto_celula]
    nos = len(malha.no_x)
    termo = (malha.ponto_dx * v[:, None] - malha.ponto_dy * u[:, None]) * w[:, None]
    f = np.bincount(celulas.ravel(), termo.ravel(), minlength=nos)
    omega = _resolver_empenamento(malha, f)
    constante = max(ix + iy - float(omega @ f), 0.0)

    no_valor = omega[celulas]
    omega_p = (malha.ponto_n * no_valor).sum(axis=1)
    media_omega = float((w * omega_p).sum()) / area
    omega_p = omega_p - media_omega
    s_x, s_y = float((w * omega_p * u).sum()), float((w * omega_p * v).sum())
    delta = ix * iy - ixy**2
    x_s = (s_x * ixy - s_y * iy) / delta
    y_s = (s_x * ix - s_y * ixy) / delta
    omega_s = omega_p - y_s * u + x_s * v
    omega_s -= float((w * omega_s).sum()) / area
    empenamento = float((w * omega_s**2).sum())

    # Tensão de torção por unidade de T/J.
    d_x, d_y, nos_usados = _derivadas_nos_nos(malha, omega)
    gradiente_x, gradiente_y = malha.no_x[nos_usados], malha.no_y[nos_usados]
    torcao_x, torcao_y = d_x - (gradiente_y - yc), d_y + (gradiente_x - xc)
    if not len(nos_usados):
        torcao_x = (malha.ponto_dx * no_valor).sum(axis=1) - v
        torcao_y = (malha.ponto_dy * no_valor).sum(axis=1) + u
        gradiente_x, gradiente_y = x, y
    gradiente = np.hypot(torcao_x, torcao_y)
    gradiente_max = float(np.percentile(gradiente, 98.5))
    w_torcao = constante / gradiente_max

    cortadas = malha.ativo.sum()
    espessura = 2.0 * area / max(_perimetro(malha), 1e-9)
    prop = Propriedades(
        area=area,
        xc=xc,
        yc=yc,
        ix=ix,
        iy=iy,
        ixy=ixy,
        i1=media + raio,
        i2=media - raio,
        angulo=angulo,
        wx_topo=ix / (y_max - yc),
        wx_base=ix / (yc - y_min),
        wy_direita=iy / (x_max - xc),
        wy_esquerda=iy / (xc - x_min),
        zx=_modulo_plastico(ry0, ry1, largura_x),
        zy=_modulo_plastico(rx0, rx1, largura_y),
        j=constante,
        cw=empenamento if empenamento > 1e-6 * ix * ix / area else 0.0,
        x_s=x_s,
        y_s=y_s,
        w_torcao=w_torcao,
        qx=_momento_estatico(ry0, ry1, largura_x, yc),
        qy=_momento_estatico(rx0, rx1, largura_y, xc),
        bx=_largura_na_linha(ry0, ry1, largura_x, yc),
        by=_largura_na_linha(rx0, rx1, largura_y, xc),
        largura=float(x_max - x_min),
        altura=float(y_max - y_min),
        x0=float(x_min),
        y0=float(y_min),
        espessura_media=espessura,
        pedacos=_pedacos(malha.ativo) if cortadas else 0,
    )
    return Analise(
        tuple(partes),
        prop,
        malha,
        gradiente,
        gradiente_x,
        gradiente_y,
        gradiente_max,
        torcao_x,
        torcao_y,
    )


def _perimetro(malha: Malha) -> float:
    ativo = malha.ativo
    borda = np.pad(ativo, 1)
    dx, dy = np.diff(malha.xs), np.diff(malha.ys)
    verticais = (borda[1:, 1:-1] != borda[:-1, 1:-1]).sum(axis=0) * dy
    horizontais = (borda[1:-1, 1:] != borda[1:-1, :-1]).sum(axis=1) * dx
    total = float(verticais.sum() + horizontais.sum())
    # Em curva a grade conta o contorno em escada (4/π maior, na média de todas as direções).
    return total * (math.pi / 4.0 if malha.curvas else 1.0)


# ---------------------------------------------------------------------------
# Reconhecer a forma
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Forma:
    """O que a seção é para as rotinas de norma do programa."""

    tipo: str  # I, U, T, L, caixao, barra_ret, barra_circ, tubo_circ, livre
    nome: str
    familia: str
    d: float = 0.0
    bf: float = 0.0
    tw: float = 0.0
    tf: float = 0.0
    espelhada_x: bool = False  # U com a alma à direita
    espelhada_y: bool = False  # T com a mesa embaixo


_LIVRE = Forma("livre", "Seção livre", FAMILIA_LIVRE)


def _padrao(partes: Sequence[Parte]) -> tuple[list[float], list[float], list[list[bool]]] | None:
    """A figura reduzida às faixas que importam: lados x, lados y e a grade, de cima para baixo."""
    if not all(p.reta for p in partes):
        return None
    xs = sorted({round(v, 6) for p in partes for v in (p.caixa()[0], p.caixa()[2])})
    ys = sorted({round(v, 6) for p in partes for v in (p.caixa()[1], p.caixa()[3])})
    for parte in partes:
        for px, py in parte.pontos:
            xs.append(round(px, 6))
            ys.append(round(py, 6))
    xs, ys = sorted(set(xs)), sorted(set(ys))
    if len(xs) < 2 or len(ys) < 2:
        return None
    grade = _ocupacao(partes, np.array(xs), np.array(ys), 1)[:, :, 0, 0]
    colunas = [c for c in range(grade.shape[0]) if grade[c].any()]
    linhas = [ln for ln in range(grade.shape[1]) if grade[:, ln].any()]
    if not colunas or not linhas:
        return None

    def unir(indices: list[int], assinatura: Callable[[int], tuple[bool, ...]], lado: list[float]):
        grupos: list[tuple[tuple[bool, ...], float]] = []
        for k in indices:
            tira = assinatura(k)
            medida = lado[k + 1] - lado[k]
            if grupos and grupos[-1][0] == tira:
                grupos[-1] = (tira, grupos[-1][1] + medida)
            else:
                grupos.append((tira, medida))
        return grupos

    col = unir(colunas, lambda c: tuple(bool(v) for v in grade[c, linhas]), xs)
    lin = unir(linhas, lambda ln: tuple(bool(v) for v in grade[colunas, ln]), ys)
    # Depois de unir, cada tira representa as vizinhas iguais: a grade reduzida sai delas.
    larguras = [m for _, m in col]
    alturas = [m for _, m in lin]
    x_lim = np.cumsum([xs[colunas[0]], *larguras])
    y_lim = np.cumsum([ys[linhas[0]], *alturas])
    reduzida = _ocupacao(partes, x_lim, y_lim, 1)[:, :, 0, 0]
    de_cima = [
        [bool(reduzida[c, ln]) for c in range(len(larguras))]
        for ln in range(len(alturas) - 1, -1, -1)
    ]
    return larguras, list(reversed(alturas)), de_cima


def _iguais(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(abs(a), abs(b), 1.0)


def reconhecer(partes: Sequence[Parte]) -> Forma:
    """Reconhece a forma pelo desenho, venha ela de um modelo ou de chapas soltas.

    Só a figura de dupla simetria (ou de um eixo, no U e no T) entra na família de norma: uma I de
    mesas diferentes cairia nas fórmulas de dupla simetria e daria W e M_Rd errados.
    """
    cheias = [p for p in partes if not p.furo]
    furos = [p for p in partes if p.furo]
    if len(cheias) == 1 and cheias[0].forma == CIRC:
        c = cheias[0]
        if not furos:
            return Forma(
                "barra_circ", "Barra redonda", "Barra circular", c.b, c.b, c.b / 2, c.b / 2
            )
        if len(furos) == 1 and furos[0].forma == CIRC and furos[0].b < c.b:
            f = furos[0]
            if _iguais(f.x, c.x) and _iguais(f.y, c.y):
                t = (c.b - f.b) / 2.0
                return Forma("tubo_circ", "Tubo redondo", "Tubo circular", c.b, c.b, t, t)
        return _LIVRE
    padrao = _padrao(partes)
    if padrao is None:
        return _LIVRE
    x, y, m = padrao
    a = [[1 if v else 0 for v in linha] for linha in m]
    if a == [[1]]:
        tf = min(x[0], y[0]) / 2.0
        return Forma(
            "barra_ret", "Chapa ou barra retangular", "Barra retangular", y[0], x[0], tf, tf
        )
    if a == [[1, 1, 1], [0, 1, 0], [1, 1, 1]] and _iguais(x[0], x[2]) and _iguais(y[0], y[2]):
        return Forma("I", "I soldado", "I soldado", sum(y), sum(x), x[1], y[0])
    if a in ([[1, 1], [1, 0], [1, 1]], [[1, 1], [0, 1], [1, 1]]) and _iguais(y[0], y[2]):
        alma_direita = a[1] == [0, 1]
        tw = x[1] if alma_direita else x[0]
        return Forma(
            "U", "U soldado", "U soldado", sum(y), sum(x), tw, y[0], espelhada_x=alma_direita
        )
    if a in ([[1, 1, 1], [0, 1, 0]], [[0, 1, 0], [1, 1, 1]]) and _iguais(x[0], x[2]):
        mesa_embaixo = a[0] == [0, 1, 0]
        tf = y[1] if mesa_embaixo else y[0]
        return Forma(
            "T", "T soldado", "T soldado", sum(y), sum(x), x[1], tf, espelhada_y=mesa_embaixo
        )
    if a == [[1, 1, 1], [1, 0, 1], [1, 1, 1]] and _iguais(x[0], x[2]) and _iguais(y[0], y[2]):
        return Forma(
            "caixao", "Caixão ou tubo retangular", "Tubo retangular", sum(y), sum(x), x[0], y[0]
        )
    borda = [[1, 1, 1], [1, 0, 1], [1, 0, 0], [1, 0, 1], [1, 1, 1]]
    if a == borda or a == [linha[::-1] for linha in borda]:
        t = y[0]
        if _iguais(y[0], y[4]) and _iguais(y[1], y[3]) and _iguais(x[0], t) and _iguais(x[2], t):
            return Forma(
                "c",
                "C enrijecido",
                "C enrijecido (chapa dobrada)",
                sum(y),
                sum(x),
                t,
                t,
                espelhada_x=a != borda,
            )
    if a in ([[1, 0], [1, 1]], [[0, 1], [1, 1]], [[1, 1], [1, 0]], [[1, 1], [0, 1]]):
        return Forma("L", "Cantoneira", FAMILIA_LIVRE, sum(y), sum(x))
    return _LIVRE


def alertas_da_secao(analise: Analise, forma: Forma) -> list[str]:
    """O que a pessoa precisa saber antes de usar a seção."""
    p = analise.prop
    saida: list[str] = []
    if p.pedacos > 1:
        saida.append(
            f"A seção tem {p.pedacos} pedaços soltos, e sem ligação eles não trabalham juntos. "
            "Encoste as partes ou desenhe a chapa que as liga. Para peças ligadas por espaçadores, "
            "use Perfis compostos na Flambagem de colunas."
        )
    if p.eixos_girados:
        saida.append(
            f"Os eixos principais estão girados {p.angulo:.1f}° em relação a x e y. A flambagem "
            "acontece no eixo de menor inércia, que não é x nem y."
        )
    if forma.tipo == "livre":
        saida.append(
            "Forma sem classe de flambagem local na norma: compressão e flexão pela NBR 8800 ficam "
            "em alerta nas páginas de verificação."
        )
    return saida


# ---------------------------------------------------------------------------
# Levar ao catálogo
# ---------------------------------------------------------------------------


def perfil_da_secao(
    nome: str,
    analise: Analise,
    *,
    densidade: float = DENSIDADE_ACO_KG_M3,
    observacao: str = "",
) -> dict[str, Any]:
    """Os dados de :func:`core.section_catalog.salvar_perfil` para a seção desenhada."""
    p = analise.prop
    forma = reconhecer(analise.partes)
    if p.pedacos > 1:
        raise ErroDeSecao(
            "A seção tem pedaços soltos: ligue as partes antes de usá-la. Para peças ligadas por "
            "espaçadores, use Perfis compostos na Flambagem de colunas."
        )
    d, bf = p.altura, p.largura
    tw, tf = forma.tw, forma.tf
    if tw <= 0.0 or tf <= 0.0:
        tw = tf = min(p.espessura_media, 0.24 * min(d, bf))
    if forma.tipo == "barra_ret":
        tw = tf = min(d, bf) * 0.24  # só para o cadastro: a família não usa estas medidas
    x_c, y_c = p.xc - p.x0, p.yc - p.y0
    x_s, y_s = p.x_s, p.y_s
    if forma.espelhada_x:
        x_c, x_s = bf - x_c, -x_s
    if forma.espelhada_y:
        y_c, y_s = d - y_c, -y_s
    area_cortante = d * tw if forma.tipo == "I" else p.area_cortante_x
    descricao = f"Desenhada no programa: {forma.nome.lower()}, {len(analise.partes)} parte(s)."
    return {
        "nome": nome,
        "familia": forma.familia,
        "area_mm2": p.area,
        "ix_mm4": p.ix,
        "iy_mm4": p.iy,
        "zx_mm3": p.zx,
        "zy_mm3": p.zy,
        "j_mm4": p.j,
        "cw_mm6": p.cw,
        "altura_mm": d,
        "largura_mm": bf,
        "espessura_alma_mm": tw,
        "espessura_mesa_mm": tf,
        "area_cisalhamento_mm2": area_cortante,
        "massa_kg_m": p.massa(densidade),
        "descricao": (descricao + (f" {observacao}" if observacao else "")),
        "centroide_x_mm": x_c,
        "centroide_y_mm": y_c,
        "x0_mm": 0.0 if abs(x_s) < 1e-3 * max(d, bf) else x_s,
        "y0_mm": 0.0 if abs(y_s) < 1e-3 * max(d, bf) else y_s,
        "i_min_mm4": p.i2 if p.eixos_girados else 0.0,
    }


# ---------------------------------------------------------------------------
# Tensões
# ---------------------------------------------------------------------------


#: Fração dos pontos que define o maior τ: o resto são os cantos vivos reentrantes, onde a teoria dá
#: infinito. É a mesma fração do módulo de torção, e assim τ de T continua igual a T/Wt.
PERCENTIL_DO_TAU = 98.5
POISSON_ACO = 0.3


@dataclass(frozen=True, slots=True)
class CamposDeCortante:
    """τ por unidade de cortante (1/mm²), nos mesmos pontos de ``Analise.gradiente_x``.

    Pelo cálculo, V passa pelo centro de cisalhamento e não torce a seção.
    """

    vx_x: np.ndarray  # τ_zx de Vx = 1
    vx_y: np.ndarray  # τ_zy de Vx = 1
    vy_x: np.ndarray
    vy_y: np.ndarray
    resultante: tuple[float, float, float, float]  # ∫τ dA: as duas de Vx e as duas de Vy
    momento_vx: float  # ∫(u·τ_zy − v·τ_zx) dA em volta do centro de gravidade, por V unitário
    momento_vy: float

    @property
    def erro(self) -> float:
        """Quanto a integral das tensões se afasta do cortante aplicado."""
        rxx, ryx, rxy, ryy = self.resultante
        return max(abs(rxx - 1.0), abs(ryy - 1.0), abs(rxy), abs(ryx))


def campos_de_cortante(analise: Analise, nu: float = POISSON_ACO) -> CamposDeCortante:
    """Flexão de Saint-Venant: dois problemas de Poisson na mesma malha da torção.

    V·Q/(I·b) só vale quando o τ é uniforme na largura: serve numa alma, mas não numa mesa, numa
    cantoneira ou num polígono qualquer. Aqui ∇²Ψ e ∇²Φ são resolvidos com a mesma rigidez do
    empenamento, e vale para qualquer forma, inclusive com Ixy diferente de zero. A integral das
    tensões precisa devolver o cortante aplicado, e isso fica guardado em ``resultante``.
    """
    p = analise.prop
    if p.pedacos > 1:
        raise ErroDeSecao(
            "A seção tem pedaços soltos: o cortante não passa de um para o outro. "
            "Ligue as partes para calcular o cisalhamento."
        )
    m = analise.malha
    u, v, w = m.ponto_x - p.xc, m.ponto_y - p.yc, m.ponto_peso
    d1, d2, h1, h2 = _termos_do_cortante(u, v, p)
    celulas = m.conexao[m.ponto_celula]
    nos = len(m.no_x)

    def carga(a: np.ndarray, b: np.ndarray, fonte: np.ndarray) -> np.ndarray:
        termo = (nu / 2.0) * (m.ponto_dx * a[:, None] + m.ponto_dy * b[:, None])
        termo = (termo + 2.0 * (1.0 + nu) * m.ponto_n * fonte[:, None]) * w[:, None]
        return np.bincount(celulas.ravel(), termo.ravel(), minlength=nos)

    psi = _resolver_empenamento(m, carga(d1, d2, p.ix * u - p.ixy * v))
    phi = _resolver_empenamento(m, carga(h1, h2, p.iy * v - p.ixy * u))
    delta = 2.0 * (1.0 + nu) * (p.ix * p.iy - p.ixy**2)

    def no_ponto(campo: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        locais = campo[celulas]
        return (
            ((m.ponto_dx * locais).sum(axis=1) - nu / 2.0 * a) / delta,
            ((m.ponto_dy * locais).sum(axis=1) - nu / 2.0 * b) / delta,
        )

    vx_x, vx_y = no_ponto(psi, d1, d2)
    vy_x, vy_y = no_ponto(phi, h1, h2)
    resultante = (
        float((w * vx_x).sum()),
        float((w * vx_y).sum()),
        float((w * vy_x).sum()),
        float((w * vy_y).sum()),
    )
    momento_vx = float((w * (u * vx_y - v * vx_x)).sum())
    momento_vy = float((w * (u * vy_y - v * vy_x)).sum())

    def nos_nos(campo: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d_x, d_y, usados = _derivadas_nos_nos(m, campo)
        return (d_x - nu / 2.0 * a[usados]) / delta, (d_y - nu / 2.0 * b[usados]) / delta

    if len(_derivadas_nos_nos(m, psi)[2]):
        no_d1, no_d2, no_h1, no_h2 = _termos_do_cortante(m.no_x - p.xc, m.no_y - p.yc, p)
        vx_x, vx_y = nos_nos(psi, no_d1, no_d2)
        vy_x, vy_y = nos_nos(phi, no_h1, no_h2)
    return CamposDeCortante(vx_x, vx_y, vy_x, vy_y, resultante, momento_vx, momento_vy)


def _termos_do_cortante(
    u: np.ndarray, v: np.ndarray, p: Propriedades
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    r, q = u * u - v * v, 2.0 * u * v
    return (
        p.ix * r - p.ixy * q,
        p.ixy * r + p.ix * q,
        -p.ixy * r + p.iy * q,
        -p.iy * r - p.ixy * q,
    )


@dataclass(frozen=True, slots=True)
class MapaDeTensoes:
    sigma_max: float
    sigma_min: float
    tau_torcao: float
    mises: float
    a: float  # σ = a + b·(x − xc) + c·(y − yc), em MPa
    b: float
    c: float
    tau_cortante: float = 0.0  # só o de V
    tau_max: float = 0.0  # V e T somados como vetores, ponto a ponto
    torcao_extra: float = 0.0  # kN·m: o que V soma por não passar pelo centro de cisalhamento
    ponto_tau: tuple[float, float] = (0.0, 0.0)
    ponto_mises: tuple[float, float] = (0.0, 0.0)
    sigma_no_ponto: float = 0.0  # no ponto de von Mises
    tau_no_ponto: float = 0.0
    erro_cortante: float = 0.0
    no_x: np.ndarray = field(default_factory=lambda: np.zeros(0))
    no_y: np.ndarray = field(default_factory=lambda: np.zeros(0))
    no_tau_x: np.ndarray = field(default_factory=lambda: np.zeros(0))
    no_tau_y: np.ndarray = field(default_factory=lambda: np.zeros(0))
    no_mises: np.ndarray = field(default_factory=lambda: np.zeros(0))


def tensoes(
    analise: Analise,
    n_kn: float,
    mx_knm: float,
    my_knm: float,
    t_knm: float = 0.0,
    vx_kn: float = 0.0,
    vy_kn: float = 0.0,
    *,
    campos: CamposDeCortante | None = None,
    pelo_centro_de_gravidade: bool = False,
) -> MapaDeTensoes:
    """Tração positiva. Mx positivo traciona a base; My positivo traciona a direita.

    Com eixos girados vale a flexão oblíqua completa, pelo sistema das inércias (Ixy entra). Vx para
    a direita e Vy para cima. V passa pelo centro de cisalhamento; com ``pelo_centro_de_gravidade``,
    a excentricidade vira torção, que é o que um U sofre com a carga fora da alma.
    """
    p = analise.prop
    m = analise.malha
    mxx, myy = -mx_knm * 1e6, my_knm * 1e6
    delta = p.ix * p.iy - p.ixy**2
    a = n_kn * 1e3 / p.area
    b = (myy * p.ix - mxx * p.ixy) / delta
    c = (mxx * p.iy - myy * p.ixy) / delta
    cantos_x = m.xs[np.nonzero(m.ativo)[0]][:, None] + np.diff(m.xs)[np.nonzero(m.ativo)[0]][
        :, None
    ] * np.array([0.0, 1.0, 1.0, 0.0])
    cantos_y = m.ys[np.nonzero(m.ativo)[1]][:, None] + np.diff(m.ys)[np.nonzero(m.ativo)[1]][
        :, None
    ] * np.array([0.0, 0.0, 1.0, 1.0])
    sigma = a + b * (cantos_x - p.xc) + c * (cantos_y - p.yc)

    vx, vy = vx_kn * 1e3, vy_kn * 1e3
    corta = bool(vx or vy)
    if corta and campos is None:
        campos = campos_de_cortante(analise)
    extra = 0.0
    if campos is not None and corta and pelo_centro_de_gravidade:
        extra = -(vx * campos.momento_vx + vy * campos.momento_vy)
    torque = t_knm * 1e6 + extra
    tau = abs(torque) / p.w_torcao if p.w_torcao > 0 else 0.0
    por_j = torque / p.j if p.j > 0 else 0.0
    tau_x = por_j * analise.torcao_x
    tau_y = por_j * analise.torcao_y
    tau_cortante = 0.0
    if campos is not None and corta:
        v_x = vx * campos.vx_x + vy * campos.vy_x
        v_y = vx * campos.vx_y + vy * campos.vy_y
        tau_cortante = float(np.percentile(np.hypot(v_x, v_y), PERCENTIL_DO_TAU))
        tau_x, tau_y = tau_x + v_x, tau_y + v_y
    modulo = np.hypot(tau_x, tau_y)
    tau_max = float(np.percentile(modulo, PERCENTIL_DO_TAU))
    x_no, y_no = analise.gradiente_x, analise.gradiente_y
    no_sigma = a + b * (x_no - p.xc) + c * (y_no - p.yc)
    no_mises = np.sqrt(no_sigma**2 + 3.0 * np.minimum(modulo, tau_max) ** 2)

    k_mises = int(np.argmax(no_mises))
    mises = float(no_mises[k_mises])
    ponto_mises = (float(x_no[k_mises]), float(y_no[k_mises]))
    sigma_no_ponto, tau_no_ponto = float(no_sigma[k_mises]), min(float(modulo[k_mises]), tau_max)
    maior_sigma = float(np.abs(sigma).max())
    if maior_sigma > mises:
        # O canto extremo pode não ser nó de célula cheia: ali só há σ.
        linha, canto = np.unravel_index(int(np.argmax(np.abs(sigma))), sigma.shape)
        mises, sigma_no_ponto, tau_no_ponto = maior_sigma, float(sigma[linha, canto]), 0.0
        ponto_mises = (float(cantos_x[linha, canto]), float(cantos_y[linha, canto]))
    # O maior τ fica no ponto que atinge o teto: acima dele sobram só os cantos reentrantes.
    k_tau = int(np.argmin(np.abs(modulo - tau_max)))
    return MapaDeTensoes(
        float(sigma.max()),
        float(sigma.min()),
        tau,
        mises,
        a,
        b,
        c,
        tau_cortante,
        tau_max,
        extra / 1e6,
        (float(x_no[k_tau]), float(y_no[k_tau])),
        ponto_mises,
        sigma_no_ponto,
        tau_no_ponto,
        campos.erro if campos is not None and corta else 0.0,
        x_no,
        y_no,
        tau_x,
        tau_y,
        no_mises,
    )


@dataclass(frozen=True, slots=True)
class FluxoNaLigacao:
    """Cisalhamento longitudinal na emenda de duas chapas: é o que a solda precisa levar."""

    parte_a: int  # posição em ``Analise.partes``
    parte_b: int
    comprimento: float  # mm de contato na seção
    q: float  # N/mm de barra


def _fluxo_na_linha(
    mapa: MapaDeTensoes, normal: str, posicao: float, trecho: tuple[float, float], folga: float
) -> float | None:
    """∫τ ds numa linha da malha. Sem nós bastantes na linha, não há resposta."""
    coordenada = mapa.no_y if normal == "y" else mapa.no_x
    caminho = mapa.no_x if normal == "y" else mapa.no_y
    tau = mapa.no_tau_y if normal == "y" else mapa.no_tau_x
    nos = np.nonzero(
        (np.abs(coordenada - posicao) < folga)
        & (caminho >= trecho[0] - folga)
        & (caminho <= trecho[1] + folga)
    )[0]
    if len(nos) < 2:
        return None
    ordem = nos[np.argsort(caminho[nos])]
    return float(((tau[ordem][1:] + tau[ordem][:-1]) / 2.0 * np.diff(caminho[ordem])).sum())


def _fluxo_na_emenda(
    analise: Analise,
    mapa: MapaDeTensoes,
    emenda: tuple[float, tuple[float, float], str],
    dentro: tuple[float, float],
    folga: float,
) -> float | None:
    """O fluxo medido dentro da chapa estreita e levado até a emenda.

    Na própria emenda a média dos nós mistura a alma com a mesa, onde o τ despenca, e dá 27 % a menos
    num I. Duas linhas da malha dentro da chapa dão o valor e a variação até lá. ``dentro`` é a faixa
    da chapa estreita na direção da normal.
    """
    posicao, trecho, normal = emenda
    grade = analise.malha.ys if normal == "y" else analise.malha.xs
    linhas = [float(v) for v in grade if dentro[0] + folga < v < dentro[1] - folga]
    linhas.sort(key=lambda v: abs(v - posicao))
    lidas = [
        (abs(v - posicao), _fluxo_na_linha(mapa, normal, v, trecho, folga)) for v in linhas[:2]
    ]
    validas = [(d, q) for d, q in lidas if q is not None]
    if len(validas) == 2:
        (d1, q1), (d2, q2) = validas
        return q1 + (q1 - q2) * d1 / (d2 - d1)
    if validas:
        return validas[0][1]
    return _fluxo_na_linha(mapa, normal, posicao, trecho, folga)


def fluxos_nas_ligacoes(analise: Analise, mapa: MapaDeTensoes) -> list[FluxoNaLigacao]:
    """q em cada emenda entre chapas retas que se encostam, em N por mm de barra."""
    tamanho = max(analise.prop.largura, analise.prop.altura)
    folga = 1e-6 * tamanho
    chapas = [(i, p.caixa()) for i, p in enumerate(analise.partes) if p.reta and not p.furo]
    fluxos: list[FluxoNaLigacao] = []
    for posicao, (i, a) in enumerate(chapas):
        for j, b in chapas[posicao + 1 :]:
            emenda = _emenda(a, b, folga)
            if emenda is None:
                continue
            _, trecho, normal = emenda
            comprimento = trecho[1] - trecho[0]
            # Mede na chapa que a emenda atravessa de lado a lado: é a alma, e não a mesa.
            lados = (0, 2) if normal == "y" else (1, 3)
            normais = (1, 3) if normal == "y" else (0, 2)
            estreita = min((a, b), key=lambda c: abs((c[lados[1]] - c[lados[0]]) - comprimento))
            q = _fluxo_na_emenda(
                analise, mapa, emenda, (estreita[normais[0]], estreita[normais[1]]), folga
            )
            if q is not None:
                fluxos.append(FluxoNaLigacao(i, j, comprimento, abs(q)))
    return fluxos


def _emenda(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float], folga: float
) -> tuple[float, tuple[float, float], str] | None:
    """A linha onde duas caixas se encostam: (posição, trecho, direção da normal)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    for y in (ay1, ay0):
        if abs(y - (by0 if y == ay1 else by1)) < folga:
            trecho = (max(ax0, bx0), min(ax1, bx1))
            if trecho[1] - trecho[0] > folga:
                return y, trecho, "y"
    for x in (ax1, ax0):
        if abs(x - (bx0 if x == ax1 else bx1)) < folga:
            trecho = (max(ay0, by0), min(ay1, by1))
            if trecho[1] - trecho[0] > folga:
                return x, trecho, "x"
    return None


# ---------------------------------------------------------------------------
# Modelos prontos
# ---------------------------------------------------------------------------


def _ret(x: float, y: float, b: float, h: float, *, furo: bool = False, grupo: int = 1) -> Parte:
    return Parte(RET, x, y, b, h, furo=furo, grupo=grupo)


def _circ(d: float, *, x: float = 0.0, y: float = 0.0, furo: bool = False, grupo: int = 1) -> Parte:
    return Parte(CIRC, x, y, d, d, furo=furo, grupo=grupo)


def _ret_arredondado(b: float, h: float, r: float, *, furo: bool = False) -> Parte:
    if r <= 0.0:
        return _ret(0.0, 0.0, b, h, furo=furo)
    r = min(r, min(b, h) / 2.0)
    pontos: list[tuple[float, float]] = []
    for cx, cy, inicio in (
        (b / 2 - r, h / 2 - r, 0.0),
        (-b / 2 + r, h / 2 - r, 90.0),
        (-b / 2 + r, -h / 2 + r, 180.0),
        (b / 2 - r, -h / 2 + r, 270.0),
    ):
        for k in range(9):
            ang = math.radians(inicio + k * 90.0 / 8.0)
            pontos.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return Parte(POLI, furo=furo, pontos=tuple(pontos), grupo=1)


def _i(v: Mapping[str, float]) -> list[Parte]:
    d, bf, tf, tw = v["d"], v["bf"], v["tf"], v["tw"]
    _exigir(2 * tf < d and tw < bf, "As mesas e a alma não cabem nessas medidas.")
    return [
        _ret(0.0, (d - tf) / 2, bf, tf),
        _ret(0.0, 0.0, tw, d - 2 * tf),
        _ret(0.0, -(d - tf) / 2, bf, tf),
    ]


def _i_assimetrico(v: Mapping[str, float]) -> list[Parte]:
    d, bs, ts, bi, ti, tw = v["d"], v["bs"], v["ts"], v["bi"], v["ti"], v["tw"]
    _exigir(ts + ti < d and tw < min(bs, bi), "As mesas e a alma não cabem nessas medidas.")
    alma = d - ts - ti
    return [
        _ret(0.0, d / 2 - ts / 2, bs, ts),
        _ret(0.0, -d / 2 + ti + alma / 2, tw, alma),
        _ret(0.0, -d / 2 + ti / 2, bi, ti),
    ]


def _u(v: Mapping[str, float], *, x: float = 0.0, lado: float = 1.0, grupo: int = 1) -> list[Parte]:
    d, bf, tf, tw = v["d"], v["bf"], v["tf"], v["tw"]
    _exigir(2 * tf < d and tw < bf, "As mesas e a alma não cabem nessas medidas.")
    mesa_x = x + lado * (bf - tw) / 2.0
    return [
        _ret(x, 0.0, tw, d - 2 * tf, grupo=grupo),
        _ret(mesa_x, (d - tf) / 2, bf, tf, grupo=grupo),
        _ret(mesa_x, -(d - tf) / 2, bf, tf, grupo=grupo),
    ]


def _t(v: Mapping[str, float]) -> list[Parte]:
    d, bf, tf, tw = v["d"], v["bf"], v["tf"], v["tw"]
    _exigir(tf < d and tw < bf, "A mesa e a alma não cabem nessas medidas.")
    return [_ret(0.0, d / 2 - tf / 2, bf, tf), _ret(0.0, -tf / 2, tw, d - tf)]


def _l(
    a: float,
    b: float,
    t: float,
    *,
    x: float = 0.0,
    y: float = 0.0,
    lado: float = 1.0,
    grupo: int = 1,
) -> list[Parte]:
    _exigir(t < min(a, b), "A espessura precisa ser menor que as abas.")
    return [
        _ret(x + lado * t / 2, y + a / 2, t, a, grupo=grupo),
        _ret(x + lado * (t + (b - t) / 2), y + t / 2, b - t, t, grupo=grupo),
    ]


def _caixao(v: Mapping[str, float]) -> list[Parte]:
    b, h, tf, tw = v["b"], v["h"], v["tf"], v["tw"]
    _exigir(2 * tf < h and 2 * tw < b, "As chapas não cabem nessas medidas.")
    return [
        _ret(0.0, (h - tf) / 2, b, tf),
        _ret(0.0, -(h - tf) / 2, b, tf),
        _ret(-(b - tw) / 2, 0.0, tw, h - 2 * tf),
        _ret((b - tw) / 2, 0.0, tw, h - 2 * tf),
    ]


def _tubo_ret(v: Mapping[str, float]) -> list[Parte]:
    b, h, t, r = v["b"], v["h"], v["t"], v["r"]
    _exigir(2 * t < min(b, h), "A parede não cabe nessas medidas.")
    return [
        _ret_arredondado(b, h, r),
        _ret_arredondado(b - 2 * t, h - 2 * t, max(r - t, 0.0), furo=True),
    ]


def _tubo_circ(v: Mapping[str, float]) -> list[Parte]:
    _exigir(2 * v["t"] < v["d"], "A parede não cabe nesse diâmetro.")
    return [_circ(v["d"]), _circ(v["d"] - 2 * v["t"], furo=True)]


def _dois_u_caixa(v: Mapping[str, float]) -> list[Parte]:
    meio = v["bf"] + v["folga"] / 2.0 - v["tw"] / 2.0
    return [*_u(v, x=-meio, grupo=1), *_u(v, x=meio, lado=-1.0, grupo=2)]


def _dois_u_costas(v: Mapping[str, float]) -> list[Parte]:
    meio = (v["tw"] + v["folga"]) / 2.0
    return [*_u(v, x=meio, grupo=1), *_u(v, x=-meio, lado=-1.0, grupo=2)]


def _dois_l_t(v: Mapping[str, float]) -> list[Parte]:
    meio = v["folga"] / 2.0
    return [
        *_l(v["a"], v["b"], v["t"], x=meio, grupo=1),
        *_l(v["a"], v["b"], v["t"], x=-meio, lado=-1.0, grupo=2),
    ]


def _c_enrijecido(v: Mapping[str, float]) -> list[Parte]:
    d, bf, c, t = v["d"], v["bf"], v["c"], v["t"]
    _exigir(2 * t < d and t < bf and c < d / 2 and t < c, "As medidas não formam um C enrijecido.")
    return [
        _ret(-(bf - t) / 2, 0.0, t, d),
        _ret(t / 2, (d - t) / 2, bf - t, t),
        _ret(t / 2, -(d - t) / 2, bf - t, t),
        _ret(bf / 2 - t / 2, d / 2 - t - (c - t) / 2, t, c - t),
        _ret(bf / 2 - t / 2, -d / 2 + t + (c - t) / 2, t, c - t),
    ]


def _z(v: Mapping[str, float]) -> list[Parte]:
    d, bf, tf, tw = v["d"], v["bf"], v["tf"], v["tw"]
    _exigir(2 * tf < d and tw < bf, "As mesas e a alma não cabem nessas medidas.")
    return [
        _ret(0.0, 0.0, tw, d - 2 * tf),
        _ret((bf - tw) / 2, (d - tf) / 2, bf, tf),
        _ret(-(bf - tw) / 2, -(d - tf) / 2, bf, tf),
    ]


def _i_com_chapa(v: Mapping[str, float]) -> list[Parte]:
    base = {k: v[k] for k in ("d", "bf", "tf", "tw")}
    return [
        *_i(base),
        Parte(RET, 0.0, v["d"] / 2 + v["tc"] / 2, v["bc"], v["tc"], grupo=2),
    ]


def _eixo_chaveta(v: Mapping[str, float]) -> list[Parte]:
    d, b, t = v["d"], v["b"], v["t"]
    _exigir(b < d and t < d / 2, "O rasgo não cabe nesse eixo.")
    return [_circ(d), _ret(0.0, d / 2 - t / 2 + d * 0.05, b, t + d * 0.1, furo=True)]


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ErroDeSecao(mensagem)


@dataclass(frozen=True, slots=True)
class Medida:
    chave: str
    rotulo: str
    ajuda: str
    padrao: float


@dataclass(frozen=True, slots=True)
class Modelo:
    id: str
    nome: str
    medidas: tuple[Medida, ...]
    gerar: Callable[[Mapping[str, float]], list[Parte]]


_D = Medida("d", "Altura d", "Altura total da seção.", 300.0)
_BF = Medida("bf", "Largura da mesa b", "Largura de cada mesa.", 150.0)
_TF = Medida("tf", "Mesa t_f", "Espessura da mesa.", 12.0)
_TW = Medida("tw", "Alma t_w", "Espessura da alma.", 8.0)
_FOLGA = Medida("folga", "Folga", "Distância entre as duas peças. Zero = encostadas.", 0.0)

MODELOS: tuple[Modelo, ...] = (
    Modelo("i", "I", (_D, _BF, _TF, _TW), _i),
    Modelo(
        "i_assimetrico",
        "I de mesas diferentes",
        (
            _D,
            Medida("bs", "Mesa de cima b", "Largura da mesa de cima.", 200.0),
            Medida("ts", "Mesa de cima t", "Espessura da mesa de cima.", 16.0),
            Medida("bi", "Mesa de baixo b", "Largura da mesa de baixo.", 120.0),
            Medida("ti", "Mesa de baixo t", "Espessura da mesa de baixo.", 10.0),
            _TW,
        ),
        _i_assimetrico,
    ),
    Modelo("u", "U", (_D, _BF, _TF, _TW), _u),
    Modelo("t", "T", (_D, _BF, _TF, _TW), _t),
    Modelo(
        "l",
        "Cantoneira",
        (
            Medida("a", "Aba vertical", "Comprimento da aba vertical.", 100.0),
            Medida("b", "Aba horizontal", "Comprimento da aba horizontal.", 100.0),
            Medida("t", "Espessura", "Espessura das abas.", 8.0),
        ),
        lambda v: _l(v["a"], v["b"], v["t"]),
    ),
    Modelo(
        "caixao",
        "Caixão soldado",
        (
            Medida("b", "Largura", "Largura total.", 200.0),
            Medida("h", "Altura", "Altura total.", 300.0),
            _TF,
            _TW,
        ),
        _caixao,
    ),
    Modelo(
        "tubo_ret",
        "Tubo retangular",
        (
            Medida("b", "Largura", "Largura externa.", 150.0),
            Medida("h", "Altura", "Altura externa.", 200.0),
            Medida("t", "Parede", "Espessura da parede.", 6.0),
            Medida("r", "Raio externo", "Raio do canto. Zero = canto vivo.", 0.0),
        ),
        _tubo_ret,
    ),
    Modelo(
        "tubo_circ",
        "Tubo redondo",
        (
            Medida("d", "Diâmetro externo", "Diâmetro externo do tubo.", 168.3),
            Medida("t", "Parede", "Espessura da parede.", 6.0),
        ),
        _tubo_circ,
    ),
    Modelo(
        "barra_circ",
        "Barra redonda",
        (Medida("d", "Diâmetro", "Diâmetro da barra.", 50.0),),
        lambda v: [_circ(v["d"])],
    ),
    Modelo(
        "chapa",
        "Chapa",
        (
            Medida("b", "Largura", "Largura da chapa.", 200.0),
            Medida("h", "Espessura", "Altura da chapa na seção.", 12.0),
        ),
        lambda v: [_ret(0.0, 0.0, v["b"], v["h"])],
    ),
    Modelo(
        "i_chapa",
        "I com chapa na mesa",
        (
            _D,
            _BF,
            _TF,
            _TW,
            Medida("bc", "Largura da chapa", "Largura da chapa de reforço.", 180.0),
            Medida("tc", "Espessura da chapa", "Espessura da chapa de reforço.", 12.0),
        ),
        _i_com_chapa,
    ),
    Modelo("dois_u_caixa", "2 U em caixa", (_D, _BF, _TF, _TW, _FOLGA), _dois_u_caixa),
    Modelo("dois_u_costas", "2 U de costas", (_D, _BF, _TF, _TW, _FOLGA), _dois_u_costas),
    Modelo(
        "dois_l_t",
        "2 cantoneiras em T",
        (
            Medida("a", "Aba vertical", "Comprimento da aba vertical.", 75.0),
            Medida("b", "Aba horizontal", "Comprimento da aba horizontal.", 75.0),
            Medida("t", "Espessura", "Espessura das abas.", 6.0),
            Medida("folga", "Folga", "Espaço da chapa de nó entre as cantoneiras.", 8.0),
        ),
        _dois_l_t,
    ),
    Modelo(
        "c_enrijecido",
        "C enrijecido",
        (
            Medida("d", "Altura", "Altura total.", 150.0),
            Medida("bf", "Mesa", "Largura da mesa.", 60.0),
            Medida("c", "Enrijecedor", "Altura da borda dobrada.", 20.0),
            Medida("t", "Espessura", "Espessura da chapa.", 2.65),
        ),
        _c_enrijecido,
    ),
    Modelo("z", "Z", (_D, _BF, _TF, _TW), _z),
    Modelo(
        "eixo_chaveta",
        "Eixo com chaveta",
        (
            Medida("d", "Diâmetro", "Diâmetro do eixo.", 60.0),
            Medida("b", "Largura do rasgo", "Largura do rasgo de chaveta.", 18.0),
            Medida("t", "Profundidade", "Profundidade do rasgo no eixo.", 7.0),
        ),
        _eixo_chaveta,
    ),
)

MODELOS_POR_ID = {modelo.id: modelo for modelo in MODELOS}


def partes_do_modelo(modelo_id: str, valores: Mapping[str, float]) -> list[Parte]:
    modelo = MODELOS_POR_ID[modelo_id]
    for medida in modelo.medidas:
        minimo = 0.0 if medida.chave in {"folga", "r"} else 1e-6
        if not float(valores.get(medida.chave, 0.0)) >= minimo:
            raise ErroDeSecao(f"{medida.rotulo}: informe um valor positivo.")
    return modelo.gerar({k: float(v) for k, v in valores.items()})


# ---------------------------------------------------------------------------
# Perfil do catálogo como partes
# ---------------------------------------------------------------------------


def partes_do_perfil(perfil: PerfilAco, *, grupo: int = 1) -> list[Parte]:
    """Um perfil do catálogo como chapas, pelo centro da caixa.

    Os raios de concordância do laminado não entram: a figura tem um pouco menos de aço que o
    catálogo, a favor da segurança. A página mostra a diferença.
    """
    d, bf = perfil.altura_mm, perfil.largura_mm
    tw, tf = perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    familia = str(perfil.familia).casefold()
    tipo = familia_do_perfil(perfil)
    v = {"d": d, "bf": bf, "tf": tf, "tw": tw}
    if "tubo" in familia and ("circ" in familia or "redond" in familia):
        return [replace(p, grupo=grupo) for p in _tubo_circ({"d": d, "t": tw})]
    if "tubo" in familia:
        t = min(tw, tf)
        return [replace(p, grupo=grupo) for p in _tubo_ret({"b": bf, "h": d, "t": t, "r": 0.0})]
    if "barra" in familia:
        if "circ" in familia:
            return [_circ(d, grupo=grupo)]
        return [_ret(0.0, 0.0, bf, d, grupo=grupo)]
    if tipo == "c":
        raise ErroDeSecao("C enrijecido: use o modelo pronto, com as medidas da dobra.")
    if tipo in {"u", "upn"}:
        return [replace(p, grupo=grupo) for p in _u(v, x=-(bf - tw) / 2)]
    if tipo == "t":
        return [replace(p, grupo=grupo) for p in _t(v)]
    if tipo in {"i", "w", "hea", "hem", "ipe", "heb", "hp", "ipn"}:
        return [replace(p, grupo=grupo) for p in _i(v)]
    raise ErroDeSecao(f"Não sei desenhar a família {perfil.familia!r}: use as chapas.")


LADOS = ("Em cima", "Embaixo", "À direita", "À esquerda")


def encostar(novas: Sequence[Parte], existentes: Sequence[Parte], lado: str) -> list[Parte]:
    """Leva ``novas`` a encostar no desenho, centradas no lado escolhido."""
    if not existentes:
        return list(novas)
    ax0, ay0, ax1, ay1 = caixa_das_partes([p for p in existentes if not p.furo] or existentes)
    bx0, by0, bx1, by1 = caixa_das_partes(novas)
    dx = (ax0 + ax1) / 2 - (bx0 + bx1) / 2
    dy = (ay0 + ay1) / 2 - (by0 + by1) / 2
    if lado == "Em cima":
        dy = ay1 - by0
    elif lado == "Embaixo":
        dy = ay0 - by1
    elif lado == "À direita":
        dx = ax1 - bx0
    elif lado == "À esquerda":
        dx = ax0 - bx1
    else:
        raise ErroDeSecao(f"Lado desconhecido: {lado!r}.")
    return [mover(p, dx, dy) for p in novas]


def mover(parte: Parte, dx: float, dy: float) -> Parte:
    return replace(
        parte,
        x=parte.x + dx,
        y=parte.y + dy,
        pontos=tuple((px + dx, py + dy) for px, py in parte.pontos),
    )
