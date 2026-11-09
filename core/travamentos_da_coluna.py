"""Travamentos ao longo da coluna (Flambagem de colunas): os trechos e o K·L de cada eixo.

O usuário diz a que altura da base a coluna é travada e em que plano. O travamento que trava
**L_x** impede a coluna de andar na direção y naquele ponto (a flexão em torno de x); o que trava
**L_y** impede de andar na direção x. Em cada eixo, os travamentos dividem a coluna em trechos:

* Cada trecho recebe o K da Tabela E.1 da NBR 8800 pelas suas pontas. A ponta da coluna tem a
  condição de apoio escolhida na página; o travamento é um apoio que impede o deslocamento lateral
  e deixa girar (pino). Entre dois travamentos, K = 1,0; da base engastada até o primeiro,
  K = 0,7 (0,8 recomendado). Pôr um pino no travamento despreza a continuidade da coluna, o que
  fica a favor da segurança: soltar um vínculo nunca aumenta a carga crítica.
* Acima do último travamento de uma coluna em balanço, o trecho tem um pino embaixo e o topo livre:
  sozinho, ele não fica de pé. O K desse trecho sai da flambagem elástica da coluna inteira,
  contínua, com os travamentos como apoios laterais rígidos (elementos finitos de viga e o menor
  autovalor). Com o K recomendado, o engaste da base tem a rigidez de mola que dá K = 2,1 à mesma
  coluna sem travamentos, como na Tabela E.1.
* Com o K informado pelo usuário, o mesmo K vale para todos os trechos.

O trecho de maior K·L governa a flambagem por flexão naquele eixo. O maior trecho, sem o K, é o
comprimento do B₁ (que usa K = 1) e, nos travamentos de L_y, o L_b da flambagem lateral com torção.

O travamento é suposto rígido e resistente o bastante para segurar a coluna (AISC 360-16,
Appendix 6); o programa não o dimensiona.

Também aqui: o momento de uma força horizontal (a mão-francesa) na coluna contínua com os
travamentos como apoios.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

PINO, ENGASTE, LIVRE, GUIADO = "pino", "engaste", "livre", "engaste deslocável"

#: O que cada condição de apoio da Tabela E.1 põe na base e no topo da coluna. Na (f), como na
#: figura da tabela, o pino fica embaixo e, em cima, a ponta que não gira mas anda de lado.
PONTAS: dict[str, tuple[str, str]] = {
    "Biapoiada (pino-pino)": (PINO, PINO),
    "Engastada-livre (em balanço)": (ENGASTE, LIVRE),
    "Engastada-pino": (ENGASTE, PINO),
    "Biengastada": (ENGASTE, ENGASTE),
    "Biengastada com translação (deslocável)": (ENGASTE, GUIADO),
    "Engastada-pino com translação (deslocável)": (PINO, GUIADO),
}

# K de um trecho pelas suas duas pontas (Tabela E.1): teórico, recomendado e a letra do caso.
_K_PELAS_PONTAS: dict[frozenset[str], tuple[float, float, str]] = {
    frozenset({ENGASTE}): (0.5, 0.65, "a"),
    frozenset({ENGASTE, PINO}): (0.7, 0.8, "b"),
    frozenset({ENGASTE, GUIADO}): (1.0, 1.2, "c"),
    frozenset({PINO}): (1.0, 1.0, "d"),
    frozenset({ENGASTE, LIVRE}): (2.0, 2.1, "e"),
    frozenset({PINO, GUIADO}): (2.0, 2.0, "f"),
}
K_BALANCO_RECOMENDADO = 2.1  # Tabela E.1 (e): calibra a mola do engaste no K recomendado

TOLERANCIA_MM = 1.0  # alturas mais próximas que isso são o mesmo ponto
_DIVISOES = 12  # elementos de viga em cada trecho da malha


@dataclass(frozen=True)
class Travamento:
    """Um ponto da coluna travado de lado: a altura (mm, da base) e os planos que ele trava."""

    altura_mm: float
    trava_x: bool = True  # impede a flexão em torno de x: entra em L_x
    trava_y: bool = True  # impede a flexão em torno de y: entra em L_y
    descricao: str = ""


@dataclass(frozen=True)
class Trecho:
    """Um trecho entre dois pontos travados (ou uma ponta da coluna): de, até, K e de onde ele veio."""

    de_mm: float
    ate_mm: float
    k: float
    como: str
    pela_coluna_inteira: bool = False  # K da flambagem da coluna contínua (balanço no topo)

    @property
    def comprimento_mm(self) -> float:
        return self.ate_mm - self.de_mm

    @property
    def kl_mm(self) -> float:
        return self.k * self.comprimento_mm


@dataclass(frozen=True)
class EixoTravado:
    """Os trechos de um eixo (``"x"`` ou ``"y"``) e o que governa."""

    eixo: str
    alturas_mm: tuple[float, ...]
    trechos: tuple[Trecho, ...]

    @property
    def indice_que_governa(self) -> int:
        maior = max(t.kl_mm for t in self.trechos)
        return next(i for i, t in enumerate(self.trechos) if t.kl_mm >= maior * (1 - 1e-12))

    @property
    def governa(self) -> Trecho:
        return self.trechos[self.indice_que_governa]

    @property
    def maior_trecho_mm(self) -> float:
        return max(t.comprimento_mm for t in self.trechos)


def _n(valor: float, casas: int = 0) -> str:
    if casas == 0 or abs(valor - round(valor)) < 1e-9:
        return f"{round(valor):d}"
    return f"{valor:.{casas}f}".replace(".", ",")


def aceito(travamento: Travamento, comprimento_mm: float) -> bool:
    """O travamento entra na conta: trava algum plano e fica entre as pontas da coluna."""
    altura = float(travamento.altura_mm)
    return (
        (travamento.trava_x or travamento.trava_y)
        and math.isfinite(altura)
        and TOLERANCIA_MM < altura < float(comprimento_mm) - TOLERANCIA_MM
    )


def organizar(
    travamentos: Iterable[Travamento], comprimento_mm: float
) -> tuple[tuple[float, ...], tuple[float, ...], list[str]]:
    """As alturas que travam L_x e as que travam L_y, em ordem e sem repetir, e o que ficou de
    fora, explicado (travamento na ponta ou fora da coluna, ou que não trava nenhum plano)."""
    comprimento = float(comprimento_mm)
    em_x: list[float] = []
    em_y: list[float] = []
    fora: list[str] = []
    for t in travamentos:
        altura = float(t.altura_mm)
        if not math.isfinite(altura):
            continue
        if not (t.trava_x or t.trava_y):
            fora.append(f"O travamento a {_n(altura)} mm não trava L_x nem L_y: ficou de fora.")
            continue
        if altura <= TOLERANCIA_MM or altura >= comprimento - TOLERANCIA_MM:
            fora.append(
                f"O travamento a {_n(altura)} mm está numa ponta da coluna ou fora dela "
                f"(a coluna vai de 0 a {_n(comprimento)} mm): ficou de fora. Quem diz como a "
                "ponta é presa é a condição de apoio."
            )
            continue
        if t.trava_x:
            em_x.append(altura)
        if t.trava_y:
            em_y.append(altura)
    return _sem_repetir(em_x), _sem_repetir(em_y), fora


def _sem_repetir(alturas: Sequence[float]) -> tuple[float, ...]:
    unicas: list[float] = []
    for altura in sorted(alturas):
        if not unicas or altura - unicas[-1] > TOLERANCIA_MM:
            unicas.append(altura)
    return tuple(unicas)


def _nome_da_ponta(ponta: str, da_coluna: bool) -> str:
    if not da_coluna:
        return "travamento"
    return {PINO: "pino", ENGASTE: "engaste", LIVRE: "ponta livre", GUIADO: "engaste que anda"}[
        ponta
    ]


def trechos_do_eixo(
    eixo: str,
    comprimento_mm: float,
    alturas_mm: Sequence[float],
    apoio: str,
    k_do_apoio: float,
    recomendado: bool,
) -> EixoTravado:
    """Os trechos de um eixo e o K de cada um.

    ``apoio`` é uma condição da Tabela E.1 (:data:`PONTAS`); qualquer outra coisa é o K informado
    (``k_do_apoio``), que vale para todos os trechos. ``alturas_mm`` já vem de :func:`organizar`.
    """
    comprimento = float(comprimento_mm)
    if not math.isfinite(comprimento) or comprimento <= 0:
        raise ValueError("O comprimento da coluna deve ser maior que zero.")
    alturas = _sem_repetir(
        [a for a in alturas_mm if TOLERANCIA_MM < a < comprimento - TOLERANCIA_MM]
    )
    pontos = (0.0, *alturas, comprimento)
    pontas = PONTAS.get(apoio)
    ultimo = len(pontos) - 2
    trechos: list[Trecho] = []
    for i, (de, ate) in enumerate(zip(pontos, pontos[1:], strict=False)):
        if pontas is None:
            trechos.append(Trecho(de, ate, float(k_do_apoio), "K informado"))
            continue
        baixo = pontas[0] if i == 0 else PINO
        cima = pontas[1] if i == ultimo else PINO
        caso = _K_PELAS_PONTAS.get(frozenset({baixo, cima}))
        if caso is not None:
            teorico, de_projeto, letra = caso
            como = (
                f"{_nome_da_ponta(baixo, i == 0)} e {_nome_da_ponta(cima, i == ultimo)}: "
                f"Tabela E.1 ({letra})"
            )
            trechos.append(Trecho(de, ate, de_projeto if recomendado else teorico, como))
            continue
        # Pino embaixo e topo livre: o trecho só fica de pé pela continuidade com o de baixo.
        mola = _mola_do_engaste_recomendado() if recomendado and pontas[0] == ENGASTE else None
        kl = comprimento_de_flambagem(comprimento, alturas, pontas[0], pontas[1], mola)
        trechos.append(
            Trecho(
                de,
                ate,
                kl / (ate - de),
                f"balanço acima do último travamento: K·L = {_n(kl)} mm da coluna inteira, "
                "contínua, com os travamentos como apoios",
                pela_coluna_inteira=True,
            )
        )
    return EixoTravado(eixo, alturas, tuple(trechos))


def _mola_do_engaste_recomendado() -> float:
    """c = k·L/(E·I) do engaste que dá K = 2,1 ao balanço: u·tan u, u = π/K (Timoshenko)."""
    u = math.pi / K_BALANCO_RECOMENDADO
    return u * math.tan(u)


# ---------------------------------------------------------------------------
# A coluna contínua: elementos finitos de viga (v e θ em cada nó), coordenada z/L
# ---------------------------------------------------------------------------


def _malha(alturas: Sequence[float], extras: Sequence[float] = ()) -> np.ndarray:
    """Nós de 0 a 1 (z/L), com nó em cada travamento e em cada ``extras``."""
    pontos = sorted({0.0, 1.0, *alturas, *extras})
    nos: list[float] = []
    for a, b in zip(pontos, pontos[1:], strict=False):
        if b - a > 1e-12:
            nos.extend(np.linspace(a, b, _DIVISOES + 1)[:-1].tolist())
    nos.append(1.0)
    return np.asarray(nos)


def _matrizes(nos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rigidez (E·I = 1) e rigidez geométrica (P = 1) da coluna montadas."""
    n = 2 * len(nos)
    rigidez = np.zeros((n, n))
    geometrica = np.zeros((n, n))
    for i, l in enumerate(np.diff(nos)):
        k = (
            np.array(
                [
                    [12, 6 * l, -12, 6 * l],
                    [6 * l, 4 * l**2, -6 * l, 2 * l**2],
                    [-12, -6 * l, 12, -6 * l],
                    [6 * l, 2 * l**2, -6 * l, 4 * l**2],
                ]
            )
            / l**3
        )
        g = np.array(
            [
                [36, 3 * l, -36, 3 * l],
                [3 * l, 4 * l**2, -3 * l, -(l**2)],
                [-36, -3 * l, 36, -3 * l],
                [3 * l, -(l**2), -3 * l, 4 * l**2],
            ]
        ) / (30 * l)
        graus = slice(2 * i, 2 * i + 4)
        rigidez[graus, graus] += k
        geometrica[graus, graus] += g
    return rigidez, geometrica


def _presos(nos: np.ndarray, alturas: Sequence[float], base: str, topo: str) -> set[int]:
    """Os graus de liberdade presos: v nos travamentos e o que cada ponta segura."""
    presos: set[int] = set()
    for altura in alturas:
        presos.add(2 * int(np.argmin(np.abs(nos - altura))))
    ultimo = 2 * (len(nos) - 1)
    for inicio, ponta in ((0, base), (ultimo, topo)):
        if ponta in (PINO, ENGASTE):
            presos.add(inicio)  # não anda de lado
        if ponta in (ENGASTE, GUIADO):
            presos.add(inicio + 1)  # não gira
    return presos


@lru_cache(maxsize=512)
def _kl_relativo(
    alturas: tuple[float, ...], base: str, topo: str, mola_da_base: float | None
) -> float:
    nos = _malha(alturas)
    rigidez, geometrica = _matrizes(nos)
    presos = _presos(nos, alturas, base, topo)
    if mola_da_base is not None and base == ENGASTE:
        presos.discard(1)  # o giro da base fica numa mola, não preso
        rigidez[1, 1] += mola_da_base
    livres = [g for g in range(rigidez.shape[0]) if g not in presos]
    k = rigidez[np.ix_(livres, livres)]
    g = geometrica[np.ix_(livres, livres)]
    try:
        fator = np.linalg.cholesky(k)
    except np.linalg.LinAlgError as erro:
        raise ValueError("A coluna com estes apoios e travamentos não fica de pé.") from erro
    inversa = np.linalg.inv(fator)
    mu = np.linalg.eigvalsh(inversa @ g @ inversa.T)
    maior = float(mu[-1])
    if maior <= 0:
        raise ValueError("A coluna com estes apoios e travamentos não flamba por compressão.")
    return math.pi * math.sqrt(maior)  # P = π²EI/(K·L)², com E·I = 1 e L = 1: K·L = π/√P


def comprimento_de_flambagem(
    comprimento_mm: float,
    alturas_mm: Sequence[float],
    base: str,
    topo: str,
    mola_da_base: float | None = None,
) -> float:
    """K·L (mm) da coluna inteira, contínua, com apoios laterais rígidos nos travamentos.

    ``base`` e ``topo`` são :data:`PINO`, :data:`ENGASTE`, :data:`LIVRE` ou :data:`GUIADO`.
    ``mola_da_base``, se dada, troca o engaste da base por uma mola de giro k = c·E·I/L.
    """
    comprimento = float(comprimento_mm)
    relativas = tuple(round(a / comprimento, 12) for a in sorted(alturas_mm))
    return comprimento * _kl_relativo(relativas, base, topo, mola_da_base)


def momento_da_forca_horizontal(
    comprimento_mm: float,
    alturas_mm: Sequence[float],
    base: str,
    topo: str,
    altura_da_forca_mm: float,
) -> tuple[float, float]:
    """O maior momento (por unidade de força: mm) de uma força lateral na coluna contínua com os
    travamentos como apoios, e a altura (mm, da base) em que ele acontece."""
    comprimento = float(comprimento_mm)
    alturas = [a / comprimento for a in alturas_mm]
    a = float(altura_da_forca_mm) / comprimento
    nos = _malha(alturas, (a,))
    rigidez, _ = _matrizes(nos)
    presos = _presos(nos, alturas, base, topo)
    livres = [g for g in range(rigidez.shape[0]) if g not in presos]
    forca = np.zeros(rigidez.shape[0])
    forca[2 * int(np.argmin(np.abs(nos - a)))] = 1.0
    deslocamentos = np.zeros(rigidez.shape[0])
    try:
        deslocamentos[livres] = np.linalg.solve(rigidez[np.ix_(livres, livres)], forca[livres])
    except np.linalg.LinAlgError as erro:
        raise ValueError("A coluna com estes apoios e travamentos não fica de pé.") from erro
    maior, onde = 0.0, 0.0
    for i, l in enumerate(np.diff(nos)):
        u = deslocamentos[2 * i : 2 * i + 4]
        m1 = (6 * l * u[0] + 4 * l**2 * u[1] - 6 * l * u[2] + 2 * l**2 * u[3]) / l**3
        m2 = (6 * l * u[0] + 2 * l**2 * u[1] - 6 * l * u[2] + 4 * l**2 * u[3]) / l**3
        for momento, z in ((abs(m1), nos[i]), (abs(m2), nos[i + 1])):
            if momento > maior + 1e-12:
                maior, onde = momento, float(z)
    return maior * comprimento, onde * comprimento


def texto_dos_travamentos(travamentos: Iterable[Travamento]) -> str:
    """“1500 mm (L_x e L_y, viga V1); 3000 mm (L_y)”, para o registro e o memorial."""
    partes: list[str] = []
    for t in sorted(travamentos, key=lambda t: t.altura_mm):
        planos = " e ".join(p for p, sim in (("L_x", t.trava_x), ("L_y", t.trava_y)) if sim)
        detalhe = ", ".join(p for p in (planos or "nenhum plano", t.descricao.strip()) if p)
        partes.append(f"{_n(t.altura_mm, 1)} mm ({detalhe})")
    return "; ".join(partes)


def texto_dos_trechos(eixo: EixoTravado) -> str:
    """“0–1500 mm: K = 0,80, K·L = 1200 mm; 1500–3000 mm: K = 1,00, K·L = 1500 mm (governa)”."""
    governa = eixo.indice_que_governa
    partes = []
    for i, t in enumerate(eixo.trechos):
        k = f"{t.k:.2f}".replace(".", ",")
        partes.append(
            f"{_n(t.de_mm, 1)}–{_n(t.ate_mm, 1)} mm: K = {k}, K·L = {_n(t.kl_mm)} mm"
            + (" (governa)" if i == governa else "")
        )
    return "; ".join(partes)
