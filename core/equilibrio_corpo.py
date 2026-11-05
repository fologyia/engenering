"""Equilíbrio de uma peça rígida no plano, com qualquer número de apoios e de cargas.

Cada apoio entra com as forças que ele consegue fazer, e as três equações do plano viram uma matriz
3 × n. A decomposição em valores singulares responde tudo de uma vez, sem caso especial:

- quantas das reações a estática determina (posto da matriz);
- o que sobra indeterminado numa peça hiperestática (espaço nulo): reação com componente zero nesse
  espaço tem valor único mesmo assim, como a força horizontal nas duas dobradiças de uma porta;
- para onde a peça foge quando faltam apoios (espaço nulo da transposta), que é um giro em torno de
  um ponto ou uma translação, e se a carga empurra para esse lado.

As contas são em N e m. As linhas de maiúscula em ``Unidades`` traduzem da tela e para a tela.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

G = 9.80665

PINO = "Pino"
ROLETE = "Rolete"
SIMPLES = "Apoio simples"
ATRITO = "Apoio com atrito"
ENGASTE = "Engaste"
GUIA = "Guia"
CABO = "Cabo"
BIELA = "Biela"
TIPOS_DE_APOIO = (PINO, ROLETE, SIMPLES, ATRITO, ENGASTE, GUIA, CABO, BIELA)
#: Apoios que só trabalham para um lado: o cabo puxa e o apoio simples empurra.
SO_UM_LADO = (SIMPLES, ATRITO, CABO)
#: A ponta de lá é o que define a direção destes.
COM_PONTA = (CABO, BIELA)

FORCA = "Força"
MOMENTO = "Momento"
DISTRIBUIDA = "Distribuída"
PESO = "Peso"
TIPOS_DE_CARGA = (FORCA, MOMENTO, DISTRIBUIDA, PESO)

COMPRIMENTOS = {"mm": 0.001, "cm": 0.01, "m": 1.0}
FORCAS = {"N": 1.0, "kN": 1000.0, "kgf": G}

_TOL_POSTO = 1e-10
_TOL_ZERO = 1e-9


class ErroDeEquilibrio(ValueError):
    """Dado que o cálculo não aceita. A mensagem vai direto para a tela."""


@dataclass(frozen=True)
class Unidades:
    comprimento: str = "m"
    forca: str = "kN"

    @property
    def metro(self) -> float:
        return COMPRIMENTOS[self.comprimento]

    @property
    def newton(self) -> float:
        return FORCAS[self.forca]

    @property
    def momento(self) -> str:
        return f"{self.forca}·m"

    @property
    def distribuida(self) -> str:
        return f"{self.forca}/{self.comprimento}"


def eixo(graus: float) -> tuple[float, float]:
    """(cos, sen), exatos nos múltiplos de 90°: reação de 1e-13 kN só atrapalha a leitura."""
    quartos = graus / 90.0
    if abs(quartos - round(quartos)) < 1e-12:
        return ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[int(round(quartos)) % 4]
    radianos = math.radians(graus)
    return math.cos(radianos), math.sin(radianos)


def angulo_de(x: float, y: float) -> float:
    """Ângulo em graus, de −180 a 180. Vetor nulo dá 0."""
    return math.degrees(math.atan2(y, x)) if x or y else 0.0


@dataclass(frozen=True)
class Apoio:
    nome: str
    tipo: str
    x: float
    y: float
    angulo: float = 90.0
    x2: float | None = None
    y2: float | None = None
    mu: float = 0.0

    @property
    def direcao(self) -> tuple[float, float]:
        """Para onde a reação principal aponta quando é positiva."""
        if self.x2 is not None and self.y2 is not None:
            dx, dy = self.x2 - self.x, self.y2 - self.y
            comprimento = math.hypot(dx, dy)
            if comprimento > 0.0:
                return dx / comprimento, dy / comprimento
        return eixo(self.angulo)


@dataclass(frozen=True)
class Carga:
    """Em N, N·m e N/m. A distribuída vai de (x, y) a (x2, y2), de ``valor`` a ``valor2``."""

    nome: str
    tipo: str
    x: float
    y: float
    valor: float
    angulo: float = -90.0
    x2: float = 0.0
    y2: float = 0.0
    valor2: float = 0.0


@dataclass(frozen=True)
class Corte:
    nome: str
    x: float
    y: float
    angulo: float = 0.0


@dataclass(frozen=True)
class Trecho:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Problema:
    apoios: tuple[Apoio, ...]
    cargas: tuple[Carga, ...]
    trechos: tuple[Trecho, ...] = ()
    cortes: tuple[Corte, ...] = ()


@dataclass(frozen=True)
class Acao:
    """A carga reduzida: uma força no ponto (x, y) e um momento."""

    nome: str
    x: float
    y: float
    fx: float
    fy: float
    m: float = 0.0


def _resultante_distribuida(
    nome: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    w1: float,
    w2: float,
    angulo: float,
) -> Acao:
    comprimento = math.hypot(x2 - x1, y2 - y1)
    tx, ty = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    ux, uy = eixo(angulo)
    forca = (w1 + w2) * comprimento / 2.0
    # ∫ w(s)·s ds, de 0 a L: o braço do início até o centro da carga, vezes a força.
    primeiro_momento = comprimento**2 * (w1 + 2.0 * w2) / 6.0
    if abs(w1 + w2) > 1e-12 * max(abs(w1), abs(w2), 1e-300):
        braco = primeiro_momento / forca
        return Acao(nome, x1 + tx * braco, y1 + ty * braco, forca * ux, forca * uy)
    # w₁ = −w₂: a força some e sobra um binário.
    return Acao(nome, x1, y1, 0.0, 0.0, primeiro_momento * (tx * uy - ty * ux))


def acao_da_carga(carga: Carga) -> Acao:
    if carga.tipo == MOMENTO:
        return Acao(carga.nome, carga.x, carga.y, 0.0, 0.0, carga.valor)
    if carga.tipo == PESO:
        return Acao(carga.nome, carga.x, carga.y, 0.0, -carga.valor * G)
    if carga.tipo == DISTRIBUIDA:
        return _resultante_distribuida(
            carga.nome,
            carga.x,
            carga.y,
            carga.x2,
            carga.y2,
            carga.valor,
            carga.valor2,
            carga.angulo,
        )
    ux, uy = eixo(carga.angulo)
    return Acao(carga.nome, carga.x, carga.y, carga.valor * ux, carga.valor * uy)


def _momento(acao: Acao, xo: float, yo: float) -> float:
    return (acao.x - xo) * acao.fy - (acao.y - yo) * acao.fx + acao.m


# ---------------------------------------------------------------------------
# Solução
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Incognita:
    apoio: int
    papel: str  # "x", "y", "n" (principal), "t" (tangente) ou "m"
    ux: float = 0.0
    uy: float = 0.0
    um: float = 0.0


def _incognitas(indice: int, apoio: Apoio) -> list[Incognita]:
    cx, cy = apoio.direcao
    if apoio.tipo == PINO:
        return [Incognita(indice, "x", 1.0, 0.0), Incognita(indice, "y", 0.0, 1.0)]
    if apoio.tipo == ENGASTE:
        return [
            Incognita(indice, "x", 1.0, 0.0),
            Incognita(indice, "y", 0.0, 1.0),
            Incognita(indice, "m", um=1.0),
        ]
    if apoio.tipo == ATRITO:
        return [Incognita(indice, "n", cx, cy), Incognita(indice, "t", -cy, cx)]
    if apoio.tipo == GUIA:
        return [Incognita(indice, "n", cx, cy), Incognita(indice, "m", um=1.0)]
    return [Incognita(indice, "n", cx, cy)]


@dataclass(frozen=True)
class Reacao:
    apoio: Apoio
    fx: float
    fy: float
    m: float
    n: float  # no eixo do apoio: cabo tracionado, apoio empurrando
    t: float  # atrito, ao longo da superfície
    soltas: tuple[str, ...] = ()  # componentes que a estática não separa (x, y, n, t, m)

    @property
    def determinada(self) -> bool:
        return not self.soltas

    @property
    def modulo(self) -> float:
        return math.hypot(self.fx, self.fy)

    @property
    def angulo(self) -> float:
        return angulo_de(self.fx, self.fy)


@dataclass(frozen=True)
class Movimento:
    """Para onde a peça foge: giro em torno de (x, y) ou translação na direção ``angulo``."""

    giro: bool
    x: float
    y: float
    angulo: float
    sentido: int  # +1 anti-horário, −1 horário, 0 sem carga empurrando para esse lado

    def texto(self, unidades: Unidades) -> str:
        if self.giro:
            x = f"{self.x / unidades.metro:.4g}".replace(".", ",")
            y = f"{self.y / unidades.metro:.4g}".replace(".", ",")
            ponto = f"({x}; {y}) {unidades.comprimento}"
            lado = {1: " no sentido anti-horário", -1: " no sentido horário"}.get(self.sentido, "")
            return f"gira em torno do ponto {ponto}{lado}"
        return f"corre na direção de {self.angulo:.1f}°"


@dataclass(frozen=True)
class Solucao:
    problema: Problema
    acoes: tuple[Acao, ...]
    reacoes: tuple[Reacao, ...]
    incognitas: int
    posto: int
    para: bool  # False: a carga empurra a peça para um lado que os apoios não seguram
    movimento: Movimento | None
    divisao_viavel: bool  # peça hiperestática: existe divisão que respeita cabo, contato e atrito
    referencia: float  # maior carga, para as tolerâncias

    @property
    def grau_hiperestatico(self) -> int:
        return self.incognitas - self.posto

    @property
    def livres(self) -> int:
        return 3 - self.posto

    @property
    def isostatica(self) -> bool:
        return self.grau_hiperestatico == 0 and self.livres == 0


def _pontos(problema: Problema, acoes: Iterable[Acao]) -> list[tuple[float, float]]:
    pontos = [(a.x, a.y) for a in problema.apoios]
    pontos += [(a.x, a.y) for a in acoes]
    pontos += [(c.x2, c.y2) for c in problema.cargas if c.tipo == DISTRIBUIDA]
    return pontos


def _matriz(
    incognitas: Sequence[Incognita], apoios: Sequence[Apoio], xo: float, yo: float, l: float
) -> np.ndarray:
    """Linhas ΣFx, ΣFy e ΣM/L: as três na mesma ordem de grandeza. O momento entra como M/L."""
    colunas = []
    for inc in incognitas:
        apoio = apoios[inc.apoio]
        braco = ((apoio.x - xo) * inc.uy - (apoio.y - yo) * inc.ux) / l
        colunas.append((inc.ux, inc.uy, braco + inc.um))
    return np.array(colunas, dtype=float).T


def _restricoes(incognitas: Sequence[Incognita], apoios: Sequence[Apoio]) -> list[np.ndarray]:
    """Cada vetor c diz c·x ≥ 0: cabo não empurra, contato não puxa, atrito tem limite."""
    n = len(incognitas)
    saida: list[np.ndarray] = []
    normais = {inc.apoio: i for i, inc in enumerate(incognitas) if inc.papel == "n"}
    for i, inc in enumerate(incognitas):
        apoio = apoios[inc.apoio]
        if apoio.tipo not in SO_UM_LADO:
            continue
        if inc.papel == "n":
            vetor = np.zeros(n)
            vetor[i] = 1.0
            saida.append(vetor)
        elif inc.papel == "t":
            normal = normais[inc.apoio]
            for sinal in (1.0, -1.0):
                vetor = np.zeros(n)
                vetor[normal] = apoio.mu
                vetor[i] = sinal
                saida.append(vetor)
    return saida


def _procurar_divisao(
    x: np.ndarray, nulo: np.ndarray, restricoes: Sequence[np.ndarray], tolerancia: float
) -> tuple[np.ndarray, bool]:
    """Com um grau hiperestático, o intervalo de λ em x + λ·n que respeita todas as restrições.

    Escolhe o λ viável mais perto de zero, que é a divisão mais próxima da de menor esforço.
    """
    baixo, alto = -math.inf, math.inf
    direcao = nulo[:, 0]
    for c in restricoes:
        a, b = float(c @ x), float(c @ direcao)
        if abs(b) < 1e-12:
            if a < -tolerancia:
                return x, False
            continue
        limite = -a / b
        if b > 0.0:
            baixo = max(baixo, limite)
        else:
            alto = min(alto, limite)
    if baixo > alto + tolerancia:
        return x, False
    return x + min(max(0.0, baixo), alto) * direcao, True


def _movimento(
    livre: np.ndarray, b: np.ndarray, empurrada: bool, l: float, xo: float, yo: float
) -> Movimento:
    """A carga projetada no que os apoios não seguram diz para onde a peça vai."""
    y = livre @ (livre.T @ (-b)) if empurrada else livre[:, 0]
    dx, dy, dt = float(y[0]), float(y[1]), float(y[2]) / l
    deslocamento = math.hypot(dx, dy)
    if abs(dt) * l > 1e-7 * deslocamento:
        x, yc = xo - dy / dt, yo + dx / dt
        if math.hypot(x - xo, yc - yo) < 1e4 * l:
            # Sem o arredondamento, o ponto de giro em zero sai como −2,2e−16.
            x, yc = round(x / l, 9) * l + 0.0, round(yc / l, 9) * l + 0.0
            return Movimento(True, x, yc, 0.0, (1 if dt > 0 else -1) if empurrada else 0)
    return Movimento(False, 0.0, 0.0, angulo_de(dx, dy), 0)


def resolver(problema: Problema) -> Solucao:
    if not problema.apoios:
        raise ErroDeEquilibrio("Coloque ao menos um apoio na peça.")
    acoes = tuple(acao_da_carga(c) for c in problema.cargas)
    if not acoes:
        raise ErroDeEquilibrio("Coloque ao menos uma carga na peça.")
    pontos = _pontos(problema, acoes)
    xo = sum(p[0] for p in pontos) / len(pontos)
    yo = sum(p[1] for p in pontos) / len(pontos)
    l = max(max(abs(p[0] - xo), abs(p[1] - yo)) for p in pontos) or 1.0

    referencia = max(max(abs(a.fx), abs(a.fy), abs(_momento(a, xo, yo)) / l) for a in acoes)
    if referencia <= 0.0:
        raise ErroDeEquilibrio("Preencha o valor de ao menos uma carga: todas valem zero.")

    incognitas = [inc for i, a in enumerate(problema.apoios) for inc in _incognitas(i, a)]
    matriz = _matriz(incognitas, problema.apoios, xo, yo, l)
    b = -np.array(
        [
            sum(a.fx for a in acoes),
            sum(a.fy for a in acoes),
            sum(_momento(a, xo, yo) for a in acoes) / l,
        ]
    )
    u, s, vt = np.linalg.svd(matriz, full_matrices=True)
    posto = int(np.count_nonzero(s > _TOL_POSTO * max(float(s[0]), 1e-300)))
    x = vt[:posto].T @ ((u[:, :posto].T @ b) / s[:posto])
    nulo = vt[posto:].T

    livre = u[:, posto:]
    empurrada = bool(livre.shape[1]) and float(np.linalg.norm(livre.T @ b)) > (
        _TOL_ZERO * referencia
    )
    movimento = _movimento(livre, b, empurrada, l, xo, yo) if livre.shape[1] else None

    restricoes = _restricoes(incognitas, problema.apoios)
    viavel = True
    if nulo.shape[1] == 1 and restricoes:
        x, viavel = _procurar_divisao(x, nulo, restricoes, _TOL_ZERO * referencia)

    valores: dict[int, dict[str, float]] = {}
    soltas: dict[int, list[str]] = {}
    for i, inc in enumerate(incognitas):
        escala = l if inc.papel == "m" else 1.0
        valor = float(x[i]) * escala
        if abs(valor) < 1e-11 * referencia * escala:
            valor = 0.0
        valores.setdefault(inc.apoio, {})[inc.papel] = valor
        if nulo.shape[1] and float(np.linalg.norm(nulo[i])) >= 1e-9:
            soltas.setdefault(inc.apoio, []).append(inc.papel)

    reacoes = []
    for i, apoio in enumerate(problema.apoios):
        fx = sum(valores[i][inc.papel] * inc.ux for inc in incognitas if inc.apoio == i)
        fy = sum(valores[i][inc.papel] * inc.uy for inc in incognitas if inc.apoio == i)
        reacoes.append(
            Reacao(
                apoio,
                fx,
                fy,
                valores[i].get("m", 0.0),
                valores[i].get("n", 0.0),
                valores[i].get("t", 0.0),
                tuple(soltas.get(i, ())),
            )
        )
    return Solucao(
        problema,
        acoes,
        tuple(reacoes),
        len(incognitas),
        posto,
        not empurrada,
        movimento,
        viavel,
        referencia,
    )


def residuos(solucao: Solucao) -> tuple[float, float]:
    """ΣF e ΣM em torno do primeiro apoio, somados de novo, sem passar pela matriz."""
    xo, yo = solucao.reacoes[0].apoio.x, solucao.reacoes[0].apoio.y
    fx = sum(a.fx for a in solucao.acoes) + sum(r.fx for r in solucao.reacoes)
    fy = sum(a.fy for a in solucao.acoes) + sum(r.fy for r in solucao.reacoes)
    momento = sum(_momento(a, xo, yo) for a in solucao.acoes) + sum(
        (r.apoio.x - xo) * r.fy - (r.apoio.y - yo) * r.fx + r.m for r in solucao.reacoes
    )
    return math.hypot(fx, fy), abs(momento)


# ---------------------------------------------------------------------------
# Esforços numa seção
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Esforco:
    corte: Corte
    n: float  # tração positiva
    v: float
    m: float  # traciona a fibra de baixo (barra deitada) ou a da direita (barra em pé)
    trechos_cortados: int
    carga_na_linha: bool


def eixo_do_corte(angulo: float) -> tuple[float, float]:
    """O eixo da barra, sempre para a direita (ou para cima): o sinal de M não depende do desenho."""
    tx, ty = eixo(angulo)
    if tx < -1e-12 or (abs(tx) <= 1e-12 and ty < 0.0):
        return -tx, -ty
    return tx, ty


def _acoes_do_lado(carga: Carga, xc: float, yc: float, tx: float, ty: float) -> list[Acao]:
    """A parte da carga à frente do corte. Só a distribuída pode ficar dividida."""
    if carga.tipo != DISTRIBUIDA:
        acao = acao_da_carga(carga)
        return [acao] if (acao.x - xc) * tx + (acao.y - yc) * ty > 0.0 else []
    d1 = (carga.x - xc) * tx + (carga.y - yc) * ty
    d2 = (carga.x2 - xc) * tx + (carga.y2 - yc) * ty
    if d1 <= 0.0 and d2 <= 0.0:
        return []
    if d1 >= 0.0 and d2 >= 0.0:
        return [acao_da_carga(carga)]
    s = d1 / (d1 - d2)
    xm = carga.x + (carga.x2 - carga.x) * s
    ym = carga.y + (carga.y2 - carga.y) * s
    wm = carga.valor + (carga.valor2 - carga.valor) * s
    if d1 > 0.0:
        return [
            _resultante_distribuida(
                carga.nome, carga.x, carga.y, xm, ym, carga.valor, wm, carga.angulo
            )
        ]
    return [
        _resultante_distribuida(
            carga.nome, xm, ym, carga.x2, carga.y2, wm, carga.valor2, carga.angulo
        )
    ]


def _trechos_cortados(problema: Problema, corte: Corte, tx: float, ty: float) -> int:
    def distancia(x: float, y: float) -> float:
        return (x - corte.x) * tx + (y - corte.y) * ty

    return sum(
        1
        for t in problema.trechos
        if distancia(t.x1, t.y1) * distancia(t.x2, t.y2) <= 0.0
        and (distancia(t.x1, t.y1) != 0.0 or distancia(t.x2, t.y2) != 0.0)
    )


def esforco_no_corte(solucao: Solucao, corte: Corte) -> Esforco:
    """N, V e M vêm do equilíbrio do pedaço que fica à frente do corte.

    Quem está exatamente na linha fica no pedaço de trás, e por isso o valor é o de logo depois da
    carga. Convenção: V e M positivos como numa viga deitada, com N positivo na tração.
    """
    tx, ty = eixo_do_corte(corte.angulo)
    xc, yc = corte.x, corte.y
    acoes = [a for carga in solucao.problema.cargas for a in _acoes_do_lado(carga, xc, yc, tx, ty)]
    for reacao in solucao.reacoes:
        apoio = reacao.apoio
        if (apoio.x - xc) * tx + (apoio.y - yc) * ty > 0.0:
            acoes.append(Acao(apoio.nome, apoio.x, apoio.y, reacao.fx, reacao.fy, reacao.m))
    fx = sum(a.fx for a in acoes)
    fy = sum(a.fy for a in acoes)
    momento = sum(_momento(a, xc, yc) for a in acoes)
    na_linha = any(
        abs((p[0] - xc) * tx + (p[1] - yc) * ty) < 1e-9
        for p in [(a.x, a.y) for a in solucao.acoes]
        + [(r.apoio.x, r.apoio.y) for r in solucao.reacoes]
    )
    return Esforco(
        corte,
        fx * tx + fy * ty,
        -(-fx * ty + fy * tx),
        momento,
        _trechos_cortados(solucao.problema, corte, tx, ty),
        na_linha,
    )


# ---------------------------------------------------------------------------
# Da tabela para o problema
# ---------------------------------------------------------------------------


def _numero(linha: Mapping[str, Any], chave: str, padrao: float | None = None) -> float | None:
    valor = linha.get(chave)
    return padrao if valor is None else float(valor)


def _apoio_da_linha(linha: Mapping[str, Any], nome: str, u: Unidades) -> Apoio:
    tipo = str(linha["tipo"])
    x2 = _numero(linha, "x2")
    y2 = _numero(linha, "y2")
    com_ponta = tipo in COM_PONTA and x2 is not None and y2 is not None
    mu = _numero(linha, "mu")
    if tipo == ATRITO and mu is None:
        raise ErroDeEquilibrio(f"Apoio {nome}: informe o coeficiente de atrito μ.")
    x = float(linha["x"]) * u.metro
    y = float(linha["y"]) * u.metro
    if com_ponta and x2 * u.metro == x and y2 * u.metro == y:  # type: ignore[operator]
        raise ErroDeEquilibrio(f"{tipo} {nome}: as duas pontas estão no mesmo lugar.")
    return Apoio(
        nome,
        tipo,
        x,
        y,
        float(linha["angulo"]),
        x2 * u.metro if com_ponta else None,  # type: ignore[operator]
        y2 * u.metro if com_ponta else None,  # type: ignore[operator]
        mu or 0.0,
    )


def _carga_da_linha(linha: Mapping[str, Any], nome: str, u: Unidades) -> Carga:
    tipo = str(linha["tipo"])
    x = float(linha["x"]) * u.metro
    y = float(linha["y"]) * u.metro
    valor = float(linha["valor"])
    angulo = float(linha["angulo"])
    if tipo == PESO:
        if valor < 0.0:
            raise ErroDeEquilibrio(f"{nome}: a massa não pode ser negativa.")
        return Carga(nome, tipo, x, y, valor)
    if tipo == MOMENTO:
        return Carga(nome, tipo, x, y, valor * u.newton)
    if tipo == FORCA:
        return Carga(nome, tipo, x, y, valor * u.newton, angulo)
    x2 = _numero(linha, "x2")
    y2 = _numero(linha, "y2")
    if x2 is None or y2 is None:
        raise ErroDeEquilibrio(f"{nome}: informe onde a carga distribuída termina (x₂ e y₂).")
    if x2 * u.metro == x and y2 * u.metro == y:
        raise ErroDeEquilibrio(f"{nome}: a carga distribuída começa e termina no mesmo ponto.")
    final = _numero(linha, "valor2", valor)
    fator = u.newton / u.metro
    return Carga(
        nome,
        tipo,
        x,
        y,
        valor * fator,
        angulo,
        x2 * u.metro,
        y2 * u.metro,
        final * fator,  # type: ignore[operator]
    )


def _nomes(linhas: Sequence[Mapping[str, Any]], base: Mapping[str, str] | None) -> list[str]:
    """O nome digitado, ou o próximo da sequência: A, B, C nos apoios e F1, M1, q1 nas cargas."""
    usados: list[str] = []
    contagem: dict[str, int] = {}
    for i, linha in enumerate(linhas):
        nome = str(linha.get("nome") or "").strip()
        if not nome:
            if base is None:
                nome = _letra(i)
            else:
                prefixo = base[str(linha["tipo"])]
                contagem[prefixo] = contagem.get(prefixo, 0) + 1
                nome = f"{prefixo}{contagem[prefixo]}"
        usados.append(nome)
    return usados


def nomear(tabela: str, linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """As linhas com nome: quem acrescenta uma linha na tabela não precisa batizar."""
    if tabela == "apoios":
        nomes = _nomes(linhas, None)
    elif tabela == "cargas":
        nomes = _nomes(linhas, _PREFIXOS)
    elif tabela == "cortes":
        nomes = [str(c.get("nome") or "").strip() or f"S{i}" for i, c in enumerate(linhas, 1)]
    else:
        return [dict(linha) for linha in linhas]
    return [{**linha, "nome": nome} for linha, nome in zip(linhas, nomes, strict=True)]


def _letra(indice: int) -> str:
    return chr(ord("A") + indice % 26) + ("" if indice < 26 else str(indice // 26))


_PREFIXOS = {FORCA: "F", MOMENTO: "M", DISTRIBUIDA: "q", PESO: "P"}


def problema_das_tabelas(
    trechos: Sequence[Mapping[str, Any]],
    apoios: Sequence[Mapping[str, Any]],
    cargas: Sequence[Mapping[str, Any]],
    cortes: Sequence[Mapping[str, Any]],
    unidades: Unidades,
) -> Problema:
    u = unidades
    return Problema(
        tuple(
            _apoio_da_linha(linha, nome, u)
            for linha, nome in zip(apoios, _nomes(apoios, None), strict=True)
        ),
        tuple(
            _carga_da_linha(linha, nome, u)
            for linha, nome in zip(cargas, _nomes(cargas, _PREFIXOS), strict=True)
        ),
        tuple(Trecho(*(float(t[k]) * u.metro for k in ("x1", "y1", "x2", "y2"))) for t in trechos),
        tuple(
            Corte(
                str(c.get("nome") or "").strip() or f"S{i}",
                float(c["x"]) * u.metro,
                float(c["y"]) * u.metro,
                float(c["angulo"]),
            )
            for i, c in enumerate(cortes, start=1)
        ),
    )


def converter_dados(dados: Mapping[str, Any], de: Unidades, para: Unidades) -> dict[str, Any]:
    """Mesma peça em outra unidade: as medidas e as cargas mudam de número, a peça não muda."""
    k = de.metro / para.metro
    f = de.newton / para.newton
    fw = f / k

    def ponto(valor: Any) -> Any:
        return None if valor is None else round(float(valor) * k, 9)

    def apoio(linha: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **linha,
            "x": ponto(linha["x"]),
            "y": ponto(linha["y"]),
            "x2": ponto(linha.get("x2")),
            "y2": ponto(linha.get("y2")),
        }

    def carga(linha: Mapping[str, Any]) -> dict[str, Any]:
        tipo = linha["tipo"]
        fator = {FORCA: f, MOMENTO: f, DISTRIBUIDA: fw}.get(tipo, 1.0)
        final = linha.get("valor2")
        return {
            **apoio(linha),
            "valor": round(float(linha["valor"]) * fator, 9),
            "valor2": None if final is None else round(float(final) * fator, 9),
        }

    return {
        "trechos": [
            {chave: ponto(t[chave]) for chave in ("x1", "y1", "x2", "y2")} for t in dados["trechos"]
        ],
        "apoios": [apoio(a) for a in dados["apoios"]],
        "cargas": [carga(c) for c in dados["cargas"]],
        "cortes": [{**c, "x": ponto(c["x"]), "y": ponto(c["y"])} for c in dados["cortes"]],
    }
