"""Busca em faixas do montador de fórmulas: várias incógnitas ao mesmo tempo.

Uma equação isola uma letra. Com duas ou três incógnitas, ou com equação sem forma fechada, a saída é
testar: a grade varre as faixas com o passo pedido, e o refino aperta em volta da melhor combinação até
parar de andar. Com mais incógnitas que condições não existe um ponto só, e sim uma família inteira que
dá 100 %. Por isso a busca precisa de um objetivo: a menor área, o maior ou o menor valor de uma letra,
ou o ponto em que todas as condições encostam no limite juntas, que é um ponto só quando há tantas
condições quanto incógnitas.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import sympy as sp

from core import montador_grandezas as g
from core.montador import Montagem, conferir_valores, letras_zeradas, remontar
from core.montador_funcoes import FUNCOES

MENOR_AREA = "area"
NO_LIMITE = "limite"
MAIOR = "maior"
MENOR = "menor"
MAX_COMBINACOES = 250_000
_PONTOS_DO_REFINO = 9
_RODADAS = 80
_ENCOLHE = 0.6
_TOLERANCIA = 1e-7
_FOLGA_DO_USO = 1e-9
_LADO_DO_MAPA = 45
_AMOSTRAS_DO_FECHO = 41
_PASSOS_DA_BISSECAO = 45


def _milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


class ErroDeBusca(ValueError):
    """A faixa pedida não dá para testar."""


@dataclass(frozen=True)
class Faixa:
    """Na base N, mm, MPa."""

    chave: str
    de: float
    ate: float
    passo: float

    def valores(self) -> np.ndarray:
        quantos = int(math.floor((self.ate - self.de) / self.passo + 1e-9)) + 1
        return self.de + np.arange(quantos) * self.passo


@dataclass(frozen=True)
class Objetivo:
    rotulo: str
    tipo: str
    chave: str = ""


@dataclass(frozen=True)
class Candidato:
    valores: tuple[tuple[str, float], ...]
    uso: float  # o maior uso entre as condições
    usos: tuple[float, ...]
    area: float | None
    manda: str

    def valor(self, chave: str) -> float:
        return dict(self.valores)[chave]


@dataclass(frozen=True)
class Rodada:
    numero: int
    meia_largura: float  # relativa ao valor, a maior entre as incógnitas
    uso: float
    area: float | None


@dataclass(frozen=True)
class Busca:
    faixas: tuple[Faixa, ...]
    objetivo: Objetivo
    testadas: int
    aprovadas: int
    melhores_da_grade: tuple[Candidato, ...]
    convergido: Candidato | None
    rodadas: tuple[Rodada, ...]
    na_borda: tuple[str, ...]
    alertas: tuple[str, ...]
    nomes: tuple[str, ...]  # das condições, na ordem de ``usos``
    mapa: tuple[tuple[float, ...], ...]  # (x, y, uso) ou (x, uso), para o gráfico


def objetivos(montagem: Montagem, chaves: Sequence[str]) -> tuple[Objetivo, ...]:
    """O que dá para procurar com estas incógnitas."""
    if any(c.igualdade for c in montagem.condicoes):
        # Equação não tem folga: uma combinação fecha ou não fecha, e não dá para escolher a melhor.
        return (Objetivo("Todas as condições no limite", NO_LIMITE),)
    lista = []
    simbolos = {g.simbolo_de(c) for c in chaves}
    if montagem.area is not None and montagem.area.free_symbols & simbolos:
        lista.append(Objetivo("Menor área da seção", MENOR_AREA))
    lista.append(Objetivo("Todas as condições no limite", NO_LIMITE))
    for chave in chaves:
        grandeza = montagem.grandeza(chave)
        texto = grandeza.texto if grandeza else chave
        lista.append(Objetivo(f"Maior {texto}", MAIOR, chave))
        lista.append(Objetivo(f"Menor {texto}", MENOR, chave))
    return tuple(lista)


@dataclass(frozen=True)
class _Conta:
    nomes: tuple[str, ...]
    usos: tuple[Callable[..., np.ndarray], ...]
    dependem: tuple[bool, ...]
    validades: tuple[Callable[..., np.ndarray], ...]
    area: Callable[..., np.ndarray] | None


@lru_cache(maxsize=32)
def _preparar(
    montagem: Montagem, chaves: tuple[str, ...], valores: tuple[tuple[str, float], ...]
) -> _Conta:
    simbolos = [g.simbolo_de(c) for c in chaves]
    numeros = {g.simbolo_de(k): sp.Float(v) for k, v in valores}
    conhecidos = set(simbolos)

    def funcao(expressao: sp.Expr) -> Callable[..., np.ndarray]:
        return sp.lambdify(simbolos, expressao, modules=[FUNCOES, "numpy"])

    usos, dependem, validades = [], [], []
    vistas: set[sp.Expr] = set()
    for condicao in montagem.condicoes:
        uso = (condicao.esquerda / condicao.direita).subs(numeros)
        usos.append(funcao(uso))
        dependem.append(bool(uso.free_symbols & conhecidos))
        for validade in condicao.validade:
            expressao = validade.expressao.subs(numeros)
            if not validade.restringe:
                continue  # só aviso: a combinação continua valendo
            if expressao in vistas or not expressao.free_symbols <= conhecidos:
                continue  # letra sem valor: a hipótese fica sem conferir
            vistas.add(expressao)
            validades.append(funcao(expressao))
    area = None
    if montagem.area is not None:
        expressao = montagem.area.subs(numeros)
        if expressao.free_symbols <= conhecidos:
            area = funcao(expressao)
    return _Conta(
        tuple(c.nome for c in montagem.condicoes),
        tuple(usos),
        tuple(dependem),
        tuple(validades),
        area,
    )


def _avaliar(
    conta: _Conta, pontos: Sequence[np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    forma = pontos[0].shape

    def todos(funcao: Callable[..., np.ndarray]) -> np.ndarray:
        return np.broadcast_to(np.asarray(funcao(*pontos), dtype=float), forma)

    with np.errstate(all="ignore"):
        usos = np.stack([todos(f) for f in conta.usos])
        valido = np.all(np.isfinite(usos), axis=0)
        for validade in conta.validades:
            valido = valido & (todos(validade) >= -1e-9)
        area = todos(conta.area) if conta.area is not None else np.zeros(forma)
    return usos, valido, area


def usos_nos_pontos(
    montagem: Montagem,
    chaves: Sequence[str],
    fixos: tuple[tuple[str, float], ...],
    pontos: Sequence[np.ndarray],
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray]:
    """Para quem já tem a lista do que testar: os nomes, os usos e quem é válido."""
    conta = _preparar(montagem, tuple(chaves), fixos)
    usos, valido, _ = _avaliar(conta, pontos)
    return conta.nomes, usos, valido


def _nota(
    objetivo: Objetivo,
    chaves: Sequence[str],
    pontos: Sequence[np.ndarray],
    usos: np.ndarray,
    area: np.ndarray,
    dependem: np.ndarray,
) -> np.ndarray:
    """Quanto menor, melhor."""
    if objetivo.tipo == MENOR_AREA:
        return area
    if objetivo.tipo == NO_LIMITE:
        return ((usos[dependem] - 1.0) ** 2).sum(axis=0)
    valor = pontos[list(chaves).index(objetivo.chave)]
    return -valor if objetivo.tipo == MAIOR else valor


def _melhores(
    objetivo: Objetivo,
    chaves: Sequence[str],
    pontos: Sequence[np.ndarray],
    usos: np.ndarray,
    valido: np.ndarray,
    area: np.ndarray,
    dependem: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Os índices do melhor para o pior, e quem passou."""
    passou = valido & (usos.max(axis=0) <= 1.0 + _FOLGA_DO_USO)
    disputam = valido if objetivo.tipo == NO_LIMITE else passou
    indices = np.flatnonzero(disputam)
    if indices.size == 0:
        return indices, passou
    nota = _nota(objetivo, chaves, pontos, usos, area, dependem)[indices]
    # Empate é comum (o maior F encosta na faixa em muitas combinações): vale a menor área.
    return indices[np.lexsort((area[indices], nota))], passou


def _candidato(
    conta: _Conta,
    chaves: Sequence[str],
    pontos: Sequence[np.ndarray],
    usos: np.ndarray,
    area: np.ndarray,
    i: int,
) -> Candidato:
    daqui = usos[:, i]
    return Candidato(
        tuple((c, float(p[i])) for c, p in zip(chaves, pontos, strict=True)),
        float(daqui.max()),
        tuple(float(u) for u in daqui),
        float(area[i]) if conta.area is not None else None,
        conta.nomes[int(np.argmax(daqui))],
    )


def _grade(faixas: Sequence[Faixa]) -> list[np.ndarray]:
    malha = np.meshgrid(*[f.valores() for f in faixas], indexing="ij")
    return [m.ravel() for m in malha]


def _passa(conta: _Conta, pontos: Sequence[np.ndarray]) -> np.ndarray:
    usos, valido, _ = _avaliar(conta, pontos)
    return valido & (usos.max(axis=0) <= 1.0 + _FOLGA_DO_USO)


def _quem_fecha(
    conta: _Conta, objetivo: Objetivo, faixas: Sequence[Faixa], inicio: Candidato
) -> tuple[int, str] | None:
    """A incógnita que fecha o limite, e de que lado. Sem ela, o refino esbarra na fronteira.

    Quem procura o melhor de uma letra fecha nela mesma. Quem procura a menor área fecha na letra
    que mais alivia por área gasta: é a que tira a folga com menos material.
    """
    if objetivo.tipo == NO_LIMITE:
        return None
    chaves = [f.chave for f in faixas]
    if objetivo.tipo in (MAIOR, MENOR):
        return chaves.index(objetivo.chave), objetivo.tipo
    base = np.array([[inicio.valor(c)] for c in chaves])
    usos, _, area = _avaliar(conta, list(base))
    uso, gasto = float(usos.max()), float(area[0])
    melhor: tuple[float, int] | None = None
    for i in range(len(faixas)):
        acima = base.copy()
        acima[i] *= 1.001
        usos_acima, _, area_acima = _avaliar(conta, list(acima))
        alivio = uso - float(usos_acima.max())
        custo = float(area_acima[0]) - gasto
        if alivio > 0.0 and custo > 0.0 and (melhor is None or alivio / custo > melhor[0]):
            melhor = (alivio / custo, i)
    return None if melhor is None else (melhor[1], MENOR)


def _fechar(
    conta: _Conta,
    livres: Sequence[np.ndarray],
    indice: int,
    faixa: Faixa,
    lado: str,
) -> np.ndarray:
    """O valor da letra ``indice`` que encosta no limite, para cada combinação das outras.

    As amostras acham a fronteira mesmo com a faixa cortada pela validade da seção, e a bisseção
    fecha. Combinação sem nenhum valor que passe sai com nan.
    """
    quantas = livres[0].size if livres else 1
    amostras = np.linspace(faixa.de, faixa.ate, _AMOSTRAS_DO_FECHO)

    def teste(valores: np.ndarray) -> np.ndarray:
        pontos = [np.asarray(p) for p in livres]
        pontos.insert(indice, valores)
        return _passa(conta, pontos)

    if livres:
        repetidos = [np.repeat(p, amostras.size) for p in livres]
        pontos = list(repetidos)
        pontos.insert(indice, np.tile(amostras, quantas))
        passou = _passa(conta, pontos).reshape(quantas, amostras.size)
    else:
        passou = _passa(conta, [amostras]).reshape(1, amostras.size)
    existe = passou.any(axis=1)
    if lado == MENOR:
        limite = passou.argmax(axis=1)
        bom = amostras[limite]
        ruim = amostras[np.maximum(limite - 1, 0)]
    else:
        limite = amostras.size - 1 - passou[:, ::-1].argmax(axis=1)
        bom = amostras[limite]
        ruim = amostras[np.minimum(limite + 1, amostras.size - 1)]
    for _ in range(_PASSOS_DA_BISSECAO):
        meio = (bom + ruim) / 2.0
        ok = teste(meio)
        bom = np.where(ok, meio, bom)
        ruim = np.where(ok, ruim, meio)
    return np.where(existe, bom, np.nan)


def _refinar(
    conta: _Conta,
    objetivo: Objetivo,
    faixas: Sequence[Faixa],
    inicio: Candidato,
    dependem: np.ndarray,
) -> tuple[Candidato, tuple[Rodada, ...]]:
    """Grade pequena em volta do melhor. Só encolhe quando o melhor fica por dentro dela."""
    chaves = [f.chave for f in faixas]
    plano = _quem_fecha(conta, objetivo, faixas, inicio)
    fechada = plano[0] if plano else None
    soltas = [i for i in range(len(faixas)) if i != fechada]
    centro = np.array([inicio.valor(c) for c in chaves])
    meia = np.array([f.passo for f in faixas], dtype=float)
    atual = inicio
    rodadas: list[Rodada] = []
    for numero in range(1, _RODADAS + 1):
        eixos = [
            np.unique(
                np.clip(
                    np.linspace(centro[i] - meia[i], centro[i] + meia[i], _PONTOS_DO_REFINO),
                    faixas[i].de,
                    faixas[i].ate,
                )
            )
            for i in soltas
        ]
        livres = [m.ravel() for m in np.meshgrid(*eixos, indexing="ij")] if eixos else []
        pontos = list(livres)
        if plano is not None:
            valor = _fechar(conta, livres, plano[0], faixas[plano[0]], plano[1])
            pontos.insert(plano[0], valor)
            aceitos = np.isfinite(valor)
            pontos = [p[aceitos] for p in pontos]
            if pontos[0].size == 0:
                meia = meia * _ENCOLHE
                continue
        usos, valido, area = _avaliar(conta, pontos)
        ordem, _ = _melhores(objetivo, chaves, pontos, usos, valido, area, dependem)
        if ordem.size == 0:
            meia = meia * _ENCOLHE
            continue
        i = int(ordem[0])
        novo = np.array([p[i] for p in pontos])
        no_canto = np.abs(novo - centro) >= meia * (1.0 - 1e-9)
        dentro_da_faixa = np.array(
            [f.de < n < f.ate for n, f in zip(novo, faixas, strict=True)], dtype=bool
        )
        centro = novo
        atual = _candidato(conta, chaves, pontos, usos, area, i)
        meia = np.where(no_canto & dentro_da_faixa, meia, meia * _ENCOLHE)
        relativa = (
            float(np.max(meia[soltas] / np.maximum(np.abs(centro[soltas]), 1e-12)))
            if soltas
            else 0.0  # uma incógnita só: a bisseção já fechou
        )
        rodadas.append(Rodada(numero, relativa, atual.uso, atual.area))
        if relativa < _TOLERANCIA:
            break
    return atual, tuple(rodadas)


def _mapa(conta: _Conta, faixas: Sequence[Faixa], base: Candidato) -> tuple[tuple[float, ...], ...]:
    """O uso nas duas primeiras incógnitas, com a terceira no melhor valor."""
    x = np.linspace(faixas[0].de, faixas[0].ate, _LADO_DO_MAPA)
    if len(faixas) == 1:
        usos, _, _ = _avaliar(conta, [x])
        return tuple((float(a), float(b)) for a, b in zip(x, usos.max(axis=0), strict=True))
    y = np.linspace(faixas[1].de, faixas[1].ate, _LADO_DO_MAPA)
    malha = [m.ravel() for m in np.meshgrid(x, y, indexing="ij")]
    pontos = malha + [np.full(malha[0].shape, base.valor(f.chave)) for f in faixas[2:]]
    usos, valido, _ = _avaliar(conta, pontos)
    maior = usos.max(axis=0)
    return tuple(
        (float(a), float(b), float(u))
        for a, b, u, ok in zip(pontos[0], pontos[1], maior, valido, strict=True)
        if ok
    )


def procurar(
    montagem: Montagem,
    faixas: Sequence[Faixa],
    objetivo: Objetivo,
    valores: Mapping[str, float],
) -> Busca:
    """``valores`` na base N, mm, MPa, sem as incógnitas."""
    if not faixas:
        raise ErroDeBusca("Escolha ao menos uma incógnita.")
    chaves = tuple(f.chave for f in faixas)
    for f in faixas:
        if f.de <= 0.0 or f.ate <= f.de or f.passo <= 0.0:
            raise ErroDeBusca(f"Em {f.chave}, a faixa precisa subir, com valores acima de zero.")
    bons, problemas = conferir_valores(
        montagem, {k: v for k, v in valores.items() if k not in chaves}
    )
    if problemas:
        raise ErroDeBusca(problemas[0])
    zeros = letras_zeradas(montagem, bons)
    if zeros:
        montagem = remontar(montagem, zeros)
    valores = bons
    faltam = [
        item.texto
        for item in montagem.grandezas
        if item.chave in montagem.essenciais and item.chave not in chaves + tuple(valores)
    ]
    if faltam:
        raise ErroDeBusca(f"Preencha {', '.join(faltam)}, ou ponha como incógnita.")
    combinacoes = math.prod(len(f.valores()) for f in faixas)
    if combinacoes > MAX_COMBINACOES:
        raise ErroDeBusca(
            f"São {_milhar(combinacoes)} combinações, e o limite é {_milhar(MAX_COMBINACOES)}: "
            "aumente o passo."
        )
    fixos = tuple(sorted((k, float(v)) for k, v in valores.items() if k not in chaves))
    conta = _preparar(montagem, chaves, fixos)
    if objetivo.tipo == MENOR_AREA and conta.area is None:
        raise ErroDeBusca("Preencha as medidas da seção que não são incógnitas.")
    dependem = np.array(conta.dependem, dtype=bool)
    if not dependem.any():
        raise ErroDeBusca("Nenhuma condição depende destas incógnitas.")
    pontos = _grade(faixas)
    usos, valido, area = _avaliar(conta, pontos)
    ordem, passou = _melhores(objetivo, chaves, pontos, usos, valido, area, dependem)
    alertas: list[str] = []
    for nome, depende, uso in zip(conta.nomes, conta.dependem, usos[:, 0], strict=True):
        if not depende and uso > 1.0 + _FOLGA_DO_USO:
            alertas.append(f"{nome} não passa, e estas incógnitas não mudam isso.")
    if objetivo.tipo == NO_LIMITE and int(dependem.sum()) < len(faixas):
        alertas.append(
            f"São {len(faixas)} incógnitas e {int(dependem.sum())} condições: não existe um ponto "
            "só, e sim uma família de soluções. Esta é uma delas. Para escolher, peça a menor área."
        )
    melhores = tuple(_candidato(conta, chaves, pontos, usos, area, int(i)) for i in ordem[:8])
    if not melhores:
        validos = np.flatnonzero(valido)
        if validos.size == 0:
            alertas.append("Nenhuma combinação da faixa é válida para esta seção.")
            return Busca(
                tuple(faixas),
                objetivo,
                combinacoes,
                0,
                (),
                None,
                (),
                (),
                tuple(alertas),
                conta.nomes,
                (),
            )
        i = int(validos[np.argmin(usos[:, validos].max(axis=0))])
        perto = _candidato(conta, chaves, pontos, usos, area, i)
        alertas.append(
            f"Nenhuma combinação passou: a melhor ficou com uso de {perto.uso * 100:.0f} %, por "
            f"{perto.manda}. Amplie a faixa."
        )
        return Busca(
            tuple(faixas),
            objetivo,
            combinacoes,
            0,
            (perto,),
            None,
            (),
            (),
            tuple(alertas),
            conta.nomes,
            _mapa(conta, faixas, perto),
        )
    final, rodadas = _refinar(conta, objetivo, faixas, melhores[0], dependem)
    borda: tuple[str, ...] = ()
    if objetivo.tipo != NO_LIMITE:
        borda = tuple(
            f.chave
            for f in faixas
            if min(abs(final.valor(f.chave) - f.de), abs(f.ate - final.valor(f.chave)))
            <= 1e-6 * (f.ate - f.de)
        )
    return Busca(
        tuple(faixas),
        objetivo,
        combinacoes,
        int(passou.sum()),
        melhores,
        final,
        rodadas,
        borda,
        tuple(alertas),
        conta.nomes,
        _mapa(conta, faixas, final),
    )
