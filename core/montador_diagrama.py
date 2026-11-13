"""O diagrama do ciclo, T-s ou p-h, com a curva de saturação do fluido.

Cada saída de corrente do desenho é um ponto. Cada fio de corrente liga o estado que entra num bloco
ao que sai dele, e o caminho entre os dois é feito com a pressão e a entalpia andando em linha reta:
numa troca de calor, que é a pressão quase constante, isso dá a isobárica de verdade, que entra e sai
da curva de saturação, e na válvula, que não muda a entalpia, também. Na bomba, no compressor e na
turbina, a figura só liga a entrada à saída: o caminho de dentro delas não é esse.

O que a figura mostra de relance é o estado que não faz sentido: a bomba que recebe vapor, o
compressor que recebe mistura, a turbina que termina muito dentro da curva.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

import sympy as sp

from core import montador as mt
from core import montador_blocos as mb
from core import montador_propriedades as mp
from core import montador_termico as mte

LIQUIDO = "Líquido"
MISTURA = "Mistura"
VAPOR = "Vapor ou gás"
_PASSOS = 40
#: As máquinas: o caminho de dentro delas não é o da pressão e da entalpia em reta, e a figura liga
#: só a entrada e a saída. Na válvula, a entalpia não muda, e o caminho calculado é o de verdade.
_MAQUINAS = frozenset({"bomba_termica", "compressor", "turbina"})
_FOLGA_DO_TITULO = 1e-4
#: Quanto de vapor (ou de líquido) já conta como problema na entrada da bomba (ou do compressor).
_TITULO_QUE_PREOCUPA = 1e-3
_PASSOS_DA_CURVA = 60


@dataclass(frozen=True)
class Ponto:
    """Um estado do desenho, na base do SI: Pa, J/kg, K e J/(kg·K)."""

    numero: int
    nome: str
    no: str
    porta: str
    fluido: int
    p: float
    h: float
    t: float | None
    s: float | None
    titulo: float | None

    @property
    def fase(self) -> str:
        if self.titulo is None or not mp.FLUIDOS[self.fluido].saturacao:
            return LIQUIDO if mp.FLUIDOS[self.fluido].liquido else VAPOR
        # Saturado na saída do condensador dá x = 0 com o erro do número: conta como líquido.
        if self.titulo <= _FOLGA_DO_TITULO:
            return LIQUIDO
        return MISTURA if self.titulo < 1.0 - _FOLGA_DO_TITULO else VAPOR


@dataclass(frozen=True)
class Caminho:
    """O processo de um bloco: de ``de`` até ``para``, com os pontos do meio já calculados."""

    de: int
    para: int
    bloco: str
    fluido: int
    p: tuple[float, ...]
    h: tuple[float, ...]
    t: tuple[float | None, ...]
    s: tuple[float | None, ...]


@dataclass(frozen=True)
class Diagrama:
    pontos: tuple[Ponto, ...]
    caminhos: tuple[Caminho, ...]
    sem_numero: tuple[str, ...]  # os pontos que não fecham com os números de agora

    @property
    def fluidos(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(p.fluido for p in self.pontos))


def _numero(expressao: sp.Expr, numeros: Mapping[sp.Symbol, sp.Float]) -> float | None:
    valor = mt.numero_de(expressao, numeros)
    return float(valor) if valor is not None and math.isfinite(valor) else None


@lru_cache(maxsize=8192)
def _ts(fluido: int, p: float, h: float) -> tuple[float | None, float | None]:
    try:
        cp = mp._coolprop()
        nome = mp.FLUIDOS[fluido].coolprop
        t = float(cp.PropsSI("T", "P", p, "H", h, nome))
        s = float(cp.PropsSI("S", "P", p, "H", h, nome))
    except (ValueError, RuntimeError):
        return None, None
    if not (math.isfinite(t) and math.isfinite(s)):
        return None, None
    return t, s


def _nomes(montagem: mt.Montagem) -> dict[str, str]:
    contagem: dict[str, int] = {}
    nomes = {}
    for no in montagem.grafo.nos:
        bloco = mb.POR_CHAVE[no.tipo]
        contagem[no.tipo] = contagem.get(no.tipo, 0) + 1
        nomes[no.id] = bloco.nome if contagem[no.tipo] == 1 else f"{bloco.nome} {contagem[no.tipo]}"
    return nomes


def montar(montagem: mt.Montagem, numeros: Mapping[sp.Symbol, sp.Float]) -> Diagrama:
    """Os pontos e os processos da montagem com os números da conta."""
    nomes = _nomes(montagem)
    pontos: list[Ponto] = []
    por_porta: dict[tuple[str, str], Ponto] = {}
    sem_numero: list[str] = []
    for no in montagem.grafo.nos:
        for porta in mb.portas_de(no.tipo, dict(no.opcoes))[1]:
            if porta.tipo != mb.CORRENTE:
                continue
            corrente = montagem.saidas.get(no.id, {}).get(porta.chave)
            if not isinstance(corrente, mte.Corrente) or corrente.fluido < 0:
                continue
            onde = (
                nomes[no.id]
                if porta.chave == "saida"
                else f"{nomes[no.id]}, {porta.rotulo.lower()}"
            )
            p, h = _numero(corrente.p, numeros), _numero(corrente.h, numeros)
            if p is None or h is None or p <= 0.0:
                sem_numero.append(onde)
                continue
            t, s = _ts(corrente.fluido, p, h)
            titulo = _numero(corrente.titulo(), numeros) if corrente.do_fluido.saturacao else None
            ponto = Ponto(
                len(pontos) + 1, onde, no.id, porta.chave, corrente.fluido, p, h, t, s, titulo
            )
            pontos.append(ponto)
            por_porta[(no.id, porta.chave)] = ponto
    caminhos: list[Caminho] = []
    for fio in montagem.grafo.fios:
        de = por_porta.get((fio.de, fio.saida))
        if de is None:
            continue
        destino = next((n for n in montagem.grafo.nos if n.id == fio.para), None)
        if destino is None:
            continue
        for porta in mb.portas_de(destino.tipo, dict(destino.opcoes))[1]:
            para = por_porta.get((destino.id, porta.chave))
            if para is None or para.fluido != de.fluido:
                continue
            caminhos.append(_caminho(de, para, nomes[destino.id], destino.tipo in _MAQUINAS))
    return Diagrama(tuple(pontos), tuple(caminhos), tuple(sem_numero))


def _caminho(de: Ponto, para: Ponto, bloco: str, reto: bool = False) -> Caminho:
    ps, hs, ts, ss = [], [], [], []
    passos = 1 if reto else _PASSOS
    for i in range(passos + 1):
        f = i / passos
        p = de.p + (para.p - de.p) * f
        h = de.h + (para.h - de.h) * f
        t, s = (de.t, de.s) if i == 0 else (para.t, para.s) if i == passos else _ts(de.fluido, p, h)
        ps.append(p)
        hs.append(h)
        ts.append(t)
        ss.append(s)
    return Caminho(
        de.numero, para.numero, bloco, de.fluido, tuple(ps), tuple(hs), tuple(ts), tuple(ss)
    )


@dataclass(frozen=True)
class Saturacao:
    """A curva de saturação: líquido do triplo ao crítico e vapor do crítico de volta ao triplo."""

    t: tuple[float, ...]
    s: tuple[float, ...]
    p: tuple[float, ...]
    h: tuple[float, ...]


@lru_cache(maxsize=32)
def saturacao(fluido: int) -> Saturacao | None:
    """None quando o fluido não tem estado de vapor na tabela (os líquidos INCOMP e o ar seco)."""
    item = mp.FLUIDOS[fluido]
    if not item.saturacao:
        return None
    cp = mp._coolprop()
    try:
        minima = max(
            float(cp.PropsSI("Ttriple", item.coolprop)), float(cp.PropsSI("Tmin", item.coolprop))
        )
        critica = float(cp.PropsSI("Tcrit", item.coolprop))
    except (ValueError, RuntimeError):
        return None
    temperaturas = [
        minima + (critica - minima) * (1.0 - (1.0 - i / _PASSOS_DA_CURVA) ** 2) * 0.9995
        for i in range(_PASSOS_DA_CURVA + 1)
    ]
    lados: list[list[tuple[float, float, float, float]]] = [[], []]
    for titulo, lado in ((0, 0), (1, 1)):
        for t in temperaturas:
            try:
                lados[lado].append(
                    (
                        t,
                        float(cp.PropsSI("S", "T", t, "Q", titulo, item.coolprop)),
                        float(cp.PropsSI("P", "T", t, "Q", titulo, item.coolprop)),
                        float(cp.PropsSI("H", "T", t, "Q", titulo, item.coolprop)),
                    )
                )
            except (ValueError, RuntimeError):
                continue
    curva = lados[0] + lados[1][::-1]
    if len(curva) < 4:
        return None
    colunas = tuple(tuple(x) for x in zip(*curva, strict=True))
    return Saturacao(*colunas)


def estranhos(pontos: Sequence[Ponto], montagem: mt.Montagem) -> list[str]:
    """Os estados que o diagrama deixa ver de relance, ditos em palavras."""
    tipos = {no.id: no.tipo for no in montagem.grafo.nos}
    entra: dict[str, list[Ponto]] = {}
    por_porta = {(p.no, p.porta): p for p in pontos}
    for fio in montagem.grafo.fios:
        ponto = por_porta.get((fio.de, fio.saida))
        if ponto is not None:
            entra.setdefault(fio.para, []).append(ponto)
    avisos = []
    for no, recebidos in entra.items():
        for ponto in recebidos:
            if not mp.FLUIDOS[ponto.fluido].saturacao or ponto.titulo is None:
                continue
            if tipos.get(no) == "bomba_termica" and ponto.titulo > _TITULO_QUE_PREOCUPA:
                avisos.append(f"O ponto {ponto.numero} entra na bomba com vapor.")
            if tipos.get(no) == "compressor" and ponto.titulo < 1.0 - _TITULO_QUE_PREOCUPA:
                avisos.append(f"O ponto {ponto.numero} entra no compressor com líquido.")
    return avisos
