"""O que o Montador de fórmulas leva para as outras análises: as tensões de um ponto e a fadiga.

Tudo sai da montagem e dos números da conta (os valores e a resposta da letra pedida). O estado de
tensão é o que chega ao critério de quem manda: depois de todos os esforços da fila, e com a
concentração de tensão, se houver. A fadiga leva σa' e σm' como o bloco Fadiga de eixo calculou, já
com K_f e K_fs, e o d da seção redonda para o fator de tamanho.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import sympy as sp

from core import montador as mt
from core import montador_blocos as mb
from core.montador_secoes import Estado

FADIGA = "goodman"  # o bloco Fadiga de eixo
_ALTERNADA = "\\sigma_{a}'"
_MEDIA = "\\sigma_{m}'"


@dataclass(frozen=True)
class PontoDaSecao:
    """Um ponto da seção com as tensões em número, na base do sistema (MPa)."""

    nome: str
    sigma_x: float
    sigma_y: float
    tau_xy: float

    @property
    def von_mises(self) -> float:
        sx, sy, t = self.sigma_x, self.sigma_y, self.tau_xy
        return math.sqrt(max(sx * sx - sx * sy + sy * sy + 3 * t * t, 0.0))


@dataclass(frozen=True)
class Fadiga:
    """σa' e σm' de von Mises com K_f e K_fs, e o d da seção redonda (None se não for redonda)."""

    sigma_a: float
    sigma_m: float
    d: float | None


def estado_na_entrada(base: mt.Montagem, no_id: str) -> Estado | None:
    """O estado de tensão que chega a um bloco pelo fio da seção."""
    for fio in base.grafo.fios:
        if fio.para == no_id:
            valor = base.saidas.get(fio.de, {}).get(fio.saida)
            if isinstance(valor, Estado):
                return valor
    return None


def _criterios(base: mt.Montagem, preferido: str | None) -> list[str]:
    ids = [no.id for no in base.grafo.nos if mb.POR_CHAVE[no.tipo].grupo == mb.GRUPO_CRITERIO]
    return list(dict.fromkeys([*([preferido] if preferido else []), *ids]))


def pontos(
    base: mt.Montagem, numeros: Mapping[sp.Symbol, sp.Float], preferido: str | None = None
) -> list[PontoDaSecao]:
    """Os pontos da seção que chega ao critério ``preferido`` (o de quem manda) ou ao primeiro
    critério com seção. Vazio se ainda sobrar letra sem número."""
    for no_id in _criterios(base, preferido):
        estado = estado_na_entrada(base, no_id)
        if estado is None:
            continue
        achados = []
        for t in estado.tensoes:
            sx, sy, tau = (mt.numero_de(x, numeros) for x in (t.sx, t.sy, t.tau))
            if sx is None or sy is None or tau is None:
                return []
            achados.append(PontoDaSecao(t.ponto, sx, sy, tau))
        return achados
    return []


def fadiga(base: mt.Montagem, numeros: Mapping[sp.Symbol, sp.Float]) -> Fadiga | None:
    """As parcelas da fadiga em número, se a montagem tiver o bloco Fadiga de eixo ligado."""
    no = next((n for n in base.grafo.nos if n.tipo == FADIGA), None)
    if no is None:
        return None
    condicao = next(
        (c for c in base.condicoes if c.no == no.id and _ALTERNADA in dict(c.tensoes)), None
    )
    if condicao is None:
        return None
    parcelas = dict(condicao.tensoes)
    sigma_a = mt.numero_de(parcelas[_ALTERNADA], numeros)
    sigma_m = mt.numero_de(parcelas[_MEDIA], numeros)
    if sigma_a is None or sigma_m is None:
        return None
    estado = estado_na_entrada(base, no.id)
    d = None
    if estado is not None and estado.secao.redonda:
        d = mt.numero_de(2 * estado.secao.fibra, numeros)
    return Fadiga(sigma_a, sigma_m, d)
