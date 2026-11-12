"""Letras do meio: as que nenhum campo dá, mas que as igualdades da montagem fecham.

No térmico quase nunca se dá tudo: o estado 2 sai do 1 pela compressão, a vazão sai do calor, e o
laço de um ciclo fecha nele mesmo. A letra pedida continua sendo quem dá a resposta, como antes. Aqui
só se acham, antes dela, as letras que as igualdades determinam. É o jeito do EES: cada letra do meio
ganha a sua equação (um emparelhamento), as equações que se amarram em ciclo viram um grupo só, e os
grupos se resolvem por número, na ordem em que um depende do outro.

Quando as letras do meio dependem da letra pedida, a conta de cada condição passa a ser uma função
dela que, a cada valor, resolve as letras do meio de novo, partindo da solução do valor vizinho.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import sympy as sp

from core.montador_blocos import Condicao
from core.montador_funcoes import DA_BIBLIOTECA, FUNCOES

#: Resíduo relativo que conta como equação fechada.
FOLGA = 1e-9
_GRADE_POSITIVA = np.logspace(-9.0, 15.0, 961)
_GRADE_COM_SINAL = np.concatenate([-_GRADE_POSITIVA[::-1], [0.0], _GRADE_POSITIVA])


@dataclass(frozen=True)
class Grupo:
    """Equações que se resolvem juntas, e as letras que elas dão."""

    equacoes: tuple[int, ...]  # índices em ``DoMeio.equacoes``
    letras: tuple[sp.Symbol, ...]


@dataclass(frozen=True)
class DoMeio:
    letras: tuple[sp.Symbol, ...]
    equacoes: tuple[Condicao, ...]  # as igualdades gastas com as letras do meio
    grupos: tuple[Grupo, ...]  # na ordem de resolver
    depende_do_alvo: bool


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------


def _emparelhar(
    ligacoes: Sequence[set[int]], quantas: int, com_alvo: frozenset[int] = frozenset()
) -> dict[int, int] | None:
    """Cada letra (índice da lista) ganha uma equação só sua. None se alguma ficar sem.

    As equações com a letra pedida (``com_alvo``) ficam por último: elas são dela. Dar a equação do
    rendimento a uma letra do meio deixava a pedida sem a sua, e a conta ficava lenta ou sem saída.
    """
    dono: dict[int, int] = {}  # equação → letra

    def tentar(letra: int, vistas: set[int]) -> bool:
        for equacao in sorted(ligacoes[letra], key=lambda e: (e in com_alvo, e)):
            if equacao in vistas:
                continue
            vistas.add(equacao)
            if equacao not in dono or tentar(dono[equacao], vistas):
                dono[equacao] = letra
                return True
        return False

    for letra in range(quantas):
        if not tentar(letra, set()):
            return None
    return {letra: equacao for equacao, letra in dono.items()}


def _componentes(vizinhos: Mapping[int, set[int]]) -> list[list[int]]:
    """Tarjan: os grupos que se amarram, já na ordem de resolver (quem é dependido sai antes)."""
    indice: dict[int, int] = {}
    baixo: dict[int, int] = {}
    pilha: list[int] = []
    na_pilha: set[int] = set()
    saida: list[list[int]] = []
    contador = [0]

    def visitar(v: int) -> None:
        indice[v] = baixo[v] = contador[0]
        contador[0] += 1
        pilha.append(v)
        na_pilha.add(v)
        for w in sorted(vizinhos.get(v, ())):
            if w not in indice:
                visitar(w)
                baixo[v] = min(baixo[v], baixo[w])
            elif w in na_pilha:
                baixo[v] = min(baixo[v], indice[w])
        if baixo[v] == indice[v]:
            grupo = []
            while True:
                w = pilha.pop()
                na_pilha.discard(w)
                grupo.append(w)
                if w == v:
                    break
            saida.append(sorted(grupo))

    for v in sorted(vizinhos):
        if v not in indice:
            visitar(v)
    return saida


def analisar(
    condicoes: Sequence[Condicao], alvo: sp.Symbol, conhecidas: frozenset[sp.Symbol]
) -> DoMeio | None:
    """As letras do meio e a ordem de resolver. None quando as igualdades não fecham todas.

    Toda letra sem valor, fora a pedida, precisa de uma igualdade só dela. E precisa sobrar ao menos
    uma condição para a letra pedida: senão quem falta é ela, e a tela pede o valor como antes.
    """
    iguais = [c for c in condicoes if c.igualdade]
    if not iguais:
        return None
    desconhecidas = sorted(
        {s for c in condicoes for s in c.letras} - set(conhecidas) - {alvo}, key=lambda s: s.name
    )
    if not desconhecidas:
        return None
    ligacoes = [{i for i, c in enumerate(iguais) if letra in c.letras} for letra in desconhecidas]
    da_pedida = frozenset(i for i, c in enumerate(iguais) if alvo in c.letras)
    par = _emparelhar(ligacoes, len(desconhecidas), da_pedida)
    if par is None:
        return None
    usadas = set(par.values())
    sobram = [c for i, c in enumerate(iguais) if i not in usadas]
    sobram += [c for c in condicoes if not c.igualdade]
    if not sobram:
        return None
    # A equação de cada letra só se resolve depois das outras letras do meio que aparecem nela.
    posicao = {s: i for i, s in enumerate(desconhecidas)}
    gastas = tuple(iguais[par[letra]] for letra in range(len(desconhecidas)))
    por_letra = {
        letra: {posicao[s] for s in gastas[letra].letras if s in posicao} - {letra}
        for letra in range(len(desconhecidas))
    }
    componentes = _componentes(por_letra)
    grupos = tuple(
        Grupo(tuple(letras), tuple(desconhecidas[letra] for letra in letras))
        for letras in componentes
    )
    # Grupo com a letra pedida dentro, ou que depende de um grupo assim, muda com ela.
    com_alvo: set[int] = set()
    for letras in componentes:
        if any(alvo in gastas[letra].letras for letra in letras) or any(
            vizinho in com_alvo for letra in letras for vizinho in por_letra[letra]
        ):
            com_alvo.update(letras)
    return DoMeio(tuple(desconhecidas), gastas, grupos, bool(com_alvo))


# ---------------------------------------------------------------------------
# Número
# ---------------------------------------------------------------------------


@lru_cache(maxsize=2048)
def _compilada(expressao: sp.Expr, simbolos: tuple[sp.Symbol, ...]) -> Any:
    # Com propriedades da CoolProp, as partes repetidas da fórmula se calculam uma vez só.
    return sp.lambdify(simbolos, expressao, [FUNCOES, "numpy"], cse=expressao.has(*DA_BIBLIOTECA))


def _residuo(condicao: Condicao) -> sp.Expr:
    return condicao.esquerda - condicao.direita


def _escala(condicao: Condicao) -> sp.Expr:
    return sp.Abs(condicao.esquerda) + sp.Abs(condicao.direita)


def _avaliar(
    expressao: sp.Expr,
    letras: tuple[sp.Symbol, ...],
    valores: Sequence[Any],
    fixos: Mapping[sp.Symbol, float],
) -> Any:
    outros = tuple(
        sorted((s for s in expressao.free_symbols if s not in letras), key=lambda s: s.name)
    )
    if any(s not in fixos for s in outros):
        return math.nan
    funcao = _compilada(expressao, (*letras, *outros))
    with np.errstate(all="ignore"):
        try:
            return funcao(*valores, *(fixos[s] for s in outros))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return math.nan


def _real(valor: Any) -> float:
    try:
        numero = complex(valor)
    except (TypeError, ValueError):
        return math.nan
    if abs(numero.imag) > 1e-12 * max(abs(numero.real), 1.0):
        return math.nan
    return numero.real if math.isfinite(numero.real) else math.nan


def _relativos(
    grupo: Sequence[Condicao], letras: tuple[sp.Symbol, ...], fixos: Mapping[sp.Symbol, float]
) -> Callable[[Sequence[float]], np.ndarray]:
    """Os resíduos de um grupo divididos pelo tamanho de cada equação: h em J/kg e T em K pesam igual."""

    def residuos(valores: Sequence[float]) -> np.ndarray:
        saida = []
        for condicao in grupo:
            r = _real(_avaliar(_residuo(condicao), letras, valores, fixos))
            tamanho = _real(_avaliar(_escala(condicao), letras, valores, fixos))
            saida.append(r / max(tamanho, 1e-300) if math.isfinite(tamanho) else math.nan)
        return np.array(saida, dtype=float)

    return residuos


def _secante(
    condicao: Condicao, letra: sp.Symbol, fixos: Mapping[sp.Symbol, float], chute: float
) -> float | None:
    """Atalho a partir de uma solução vizinha. Só serve se fechar de verdade, e no lado certo."""
    residuos = _relativos([condicao], (letra,), fixos)

    def f(v: float) -> float:
        return float(residuos([v])[0])

    passo = 1e-4 * abs(chute) if chute else 1e-6
    a, b = chute, chute + passo
    fa, fb = f(a), f(b)
    for _ in range(60):
        if not (math.isfinite(fa) and math.isfinite(fb)):
            return None
        if fb == 0.0 or fb == fa:
            break
        c = b - fb * (b - a) / (fb - fa)
        if letra.is_positive and c <= 0.0:
            return None
        a, fa, b, fb = b, fb, c, f(c)
        # Vai até não andar mais: parar no primeiro resíduo pequeno deixava 1e-9 de erro.
        if abs(b - a) <= 1e-15 * max(abs(a), abs(b)) or (math.isfinite(fb) and abs(fb) <= 1e-15):
            break
    return b if math.isfinite(fb) and abs(fb) <= FOLGA else None


def _uma_letra(
    condicao: Condicao,
    letra: sp.Symbol,
    fixos: Mapping[sp.Symbol, float],
    chute: float,
    local: bool = False,
) -> float | None:
    """Uma equação, uma letra: varre a grade, refina cada troca de sinal e fica com a mais perto do
    chute. Assim a conta não foge para uma raiz sem sentido, como a do infinito. Com ``local``, o
    chute é a solução de um valor vizinho, e a secante tenta antes, porque é muito mais rápida."""
    if local:
        perto = _secante(condicao, letra, fixos, chute)
        if perto is not None:
            return perto
    grade = _GRADE_POSITIVA if letra.is_positive else _GRADE_COM_SINAL
    valores = np.asarray(_avaliar(_residuo(condicao), (letra,), (grade,), fixos), dtype=complex)
    valores = np.broadcast_to(valores, grade.shape)
    reais = np.where(
        np.abs(valores.imag) <= 1e-12 * np.maximum(np.abs(valores.real), 1.0), valores.real, np.nan
    )
    reais = np.where(np.isfinite(reais), reais, np.nan)

    def f(v: float) -> float:
        return _real(_avaliar(_residuo(condicao), (letra,), (v,), fixos))

    raizes: list[float] = []
    for i in range(len(grade) - 1):
        a, b, fa, fb = grade[i], grade[i + 1], reais[i], reais[i + 1]
        if not (math.isfinite(fa) and math.isfinite(fb)):
            continue
        if fa == 0.0:
            raizes.append(float(a))
            continue
        if fa * fb > 0.0:
            continue
        for _ in range(200):
            meio = (a + b) / 2.0
            fm = f(meio)
            if not math.isfinite(fm):
                break
            if fa * fm <= 0.0:
                b = meio
            else:
                a, fa = meio, fm
            if abs(b - a) <= 1e-13 * max(abs(a), abs(b)) or a == b:
                break
        raizes.append(float((a + b) / 2.0))
    if not raizes:
        return None

    def distancia(r: float) -> float:
        if letra.is_positive and r > 0.0 and chute > 0.0:
            return abs(math.log(r / chute))
        return abs(r - chute)

    return min(raizes, key=distancia)


def _varias_letras(
    grupo: Sequence[Condicao],
    letras: tuple[sp.Symbol, ...],
    fixos: Mapping[sp.Symbol, float],
    chutes: Sequence[float],
) -> tuple[float, ...] | None:
    """Newton do MINPACK (scipy), com as letras positivas em logaritmo: elas não viram negativas."""
    from scipy.optimize import root  # importa só quando precisa: a scipy demora a carregar

    positivas = [s.is_positive is True for s in letras]

    def de_z(z: np.ndarray) -> list[float]:
        return [math.exp(v) if p else float(v) for v, p in zip(z, positivas, strict=True)]

    def para_z(valores: Sequence[float]) -> np.ndarray:
        return np.array(
            [math.log(v) if p else v for v, p in zip(valores, positivas, strict=True)], dtype=float
        )

    residuos = _relativos(grupo, letras, fixos)

    def funcao(z: np.ndarray) -> np.ndarray:
        try:
            valores = de_z(z)
        except OverflowError:
            return np.full(len(letras), 1e6)
        r = residuos(valores)
        return np.where(np.isfinite(r), r, 1e6)

    iniciais = [max(c, 1e-12) if p else c for c, p in zip(chutes, positivas, strict=True)]
    for metodo in ("hybr", "lm"):
        try:
            resultado = root(funcao, para_z(iniciais), method=metodo)
        except (ValueError, OverflowError, FloatingPointError):
            continue
        valores = de_z(resultado.x)
        if np.all(np.abs(residuos(valores)) <= 1e-7):
            return tuple(valores)
    return None


def resolver(
    meio: DoMeio,
    numeros: Mapping[sp.Symbol, float],
    chutes: Mapping[sp.Symbol, float] | None = None,
    local: bool = False,
) -> dict[sp.Symbol, float] | None:
    """As letras do meio em número, grupo a grupo. ``numeros`` já tem a letra pedida, se ela entra."""
    fixos = {s: float(v) for s, v in numeros.items()}
    achadas: dict[sp.Symbol, float] = {}
    chutes = chutes or {}
    for grupo in meio.grupos:
        equacoes = [meio.equacoes[i] for i in grupo.equacoes]
        if len(grupo.letras) == 1:
            letra = grupo.letras[0]
            valor = _uma_letra(equacoes[0], letra, fixos, chutes.get(letra, 1.0), local)
            if valor is None:
                return None
            valores: tuple[float, ...] = (valor,)
        else:
            resolvidos = _varias_letras(
                equacoes, grupo.letras, fixos, [chutes.get(s, 1.0) for s in grupo.letras]
            )
            if resolvidos is None:
                return None
            valores = resolvidos
        for letra, valor in zip(grupo.letras, valores, strict=True):
            fixos[letra] = valor
            achadas[letra] = valor
    return achadas


class Acompanhar:
    """A conta de uma condição como função da letra pedida, com as letras do meio dentro.

    Guarda a última solução para começar a próxima dela: na grade, os valores vizinhos têm letras do
    meio vizinhas, e a conta fica rápida e sem saltos.
    """

    def __init__(
        self,
        meio: DoMeio,
        alvo: sp.Symbol,
        numeros: Mapping[sp.Symbol, float],
        chutes: Mapping[sp.Symbol, float] | None = None,
    ) -> None:
        self.meio = meio
        self.alvo = alvo
        self.numeros = {s: float(v) for s, v in numeros.items()}
        self.chutes = dict(chutes or {})
        self.vizinha = False  # há uma solução de um valor vizinho para começar dela

    def letras(self, valor: float) -> dict[sp.Symbol, float] | None:
        achadas = resolver(
            self.meio, {**self.numeros, self.alvo: valor}, self.chutes, local=self.vizinha
        )
        if achadas is None and self.vizinha:
            achadas = resolver(self.meio, {**self.numeros, self.alvo: valor}, self.chutes)
        self.vizinha = achadas is not None
        if achadas is not None:
            self.chutes.update(achadas)
        return achadas

    def diferenca(self, condicao: Condicao) -> Callable[[float], float]:
        def f(valor: float) -> float:
            achadas = self.letras(valor)
            if achadas is None:
                return math.nan
            fixos = {**self.numeros, **achadas, self.alvo: valor}
            return _real(_avaliar(_residuo(condicao), (), (), fixos))

        return f


__all__ = ["Acompanhar", "DoMeio", "FOLGA", "Grupo", "analisar", "resolver"]
