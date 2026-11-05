"""Peças prontas para começar o equilíbrio: clica no modelo, troca os números e pronto.

Cada modelo traz a própria unidade e as mesmas quatro tabelas que a tela e o cálculo usam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core import equilibrio_corpo as eq

Linha = dict[str, Any]


def trecho(x1: float, y1: float, x2: float, y2: float) -> Linha:
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def apoio(
    nome: str,
    tipo: str,
    x: float,
    y: float,
    angulo: float = 90.0,
    *,
    ponta: tuple[float, float] | None = None,
    mu: float | None = None,
) -> Linha:
    return {
        "nome": nome,
        "tipo": tipo,
        "x": x,
        "y": y,
        "angulo": angulo,
        "x2": ponta[0] if ponta else None,
        "y2": ponta[1] if ponta else None,
        "mu": mu,
    }


def carga(
    nome: str,
    tipo: str,
    x: float,
    y: float,
    valor: float,
    angulo: float = -90.0,
    *,
    ate: tuple[float, float] | None = None,
    valor2: float | None = None,
) -> Linha:
    return {
        "nome": nome,
        "tipo": tipo,
        "x": x,
        "y": y,
        "valor": valor,
        "angulo": angulo,
        "x2": ate[0] if ate else None,
        "y2": ate[1] if ate else None,
        "valor2": valor2,
    }


def corte(nome: str, x: float, y: float, angulo: float = 0.0) -> Linha:
    return {"nome": nome, "x": x, "y": y, "angulo": angulo}


@dataclass(frozen=True)
class ModeloDePeca:
    nome: str
    dica: str
    comprimento: str
    forca: str
    trechos: tuple[Linha, ...]
    apoios: tuple[Linha, ...]
    cargas: tuple[Linha, ...]
    cortes: tuple[Linha, ...] = ()

    def dados(self) -> dict[str, list[Linha]]:
        return {
            "trechos": [dict(linha) for linha in self.trechos],
            "apoios": [dict(linha) for linha in self.apoios],
            "cargas": [dict(linha) for linha in self.cargas],
            "cortes": [dict(linha) for linha in self.cortes],
        }


MODELOS: tuple[ModeloDePeca, ...] = (
    ModeloDePeca(
        "Viga com dois apoios",
        "Pino de um lado, rolete do outro.",
        "m",
        "kN",
        (trecho(0, 0, 4, 0),),
        (apoio("A", eq.PINO, 0, 0), apoio("B", eq.ROLETE, 4, 0)),
        (
            carga("F1", eq.FORCA, 1.5, 0, 10, -60),
            carga("q1", eq.DISTRIBUIDA, 2.5, 0, 4, ate=(4, 0), valor2=4),
        ),
        (corte("S1", 2, 0),),
    ),
    ModeloDePeca(
        "Viga em balanço",
        "Presa em um lado só, como um suporte soldado.",
        "m",
        "kN",
        (trecho(0, 0, 2.5, 0),),
        (apoio("A", eq.ENGASTE, 0, 0, 0),),
        (
            carga("q1", eq.DISTRIBUIDA, 0, 0, 3, ate=(2.5, 0), valor2=3),
            carga("F1", eq.FORCA, 2.5, 0, 5),
        ),
        (corte("S1", 0.5, 0),),
    ),
    ModeloDePeca(
        "Alavanca",
        "Fulcro em pino, a força do braço de um lado e a carga do outro, segura por uma biela.",
        "mm",
        "N",
        (trecho(0, 0, 800, 0),),
        (
            apoio("A", eq.PINO, 200, 0),
            apoio("B", eq.BIELA, 0, 0, -90, ponta=(0, -250)),
        ),
        (carga("F1", eq.FORCA, 800, 0, 150),),
    ),
    ModeloDePeca(
        "Suporte em L",
        "Braço soldado à parede, com a carga na ponta.",
        "mm",
        "N",
        (trecho(0, 0, 0, 300), trecho(0, 300, 450, 300)),
        (apoio("A", eq.ENGASTE, 0, 0, 90),),
        (carga("F1", eq.FORCA, 450, 300, 2000), carga("F2", eq.FORCA, 450, 300, 400, 180)),
        (corte("S1", 0, 150, 90), corte("S2", 225, 300)),
    ),
    ModeloDePeca(
        "Mão-francesa",
        "Braço articulado na parede, escorado por uma diagonal.",
        "m",
        "kN",
        (trecho(0, 0, 1.2, 0),),
        (
            apoio("A", eq.PINO, 0, 0),
            apoio("B", eq.BIELA, 0.8, 0, 225, ponta=(0, -0.8)),
        ),
        (carga("q1", eq.DISTRIBUIDA, 0, 0, 2, ate=(1.2, 0), valor2=2),),
        (corte("S1", 0.4, 0),),
    ),
    ModeloDePeca(
        "Lança com cabo",
        "Braço articulado embaixo e seguro por um cabo no alto.",
        "m",
        "kN",
        (trecho(0, 0, 3, 2),),
        (
            apoio("A", eq.PINO, 0, 0),
            apoio("B", eq.CABO, 3, 2, 150, ponta=(0, 3.5)),
        ),
        (carga("F1", eq.FORCA, 3, 2, 8),),
    ),
    ModeloDePeca(
        "Tampa com duas dobradiças",
        "Dois pinos na mesma linha: a estática não separa o peso entre eles.",
        "mm",
        "kgf",
        (trecho(0, 0, 0, 800), trecho(0, 800, 600, 800), trecho(600, 800, 600, 0)),
        (apoio("A", eq.PINO, 0, 700), apoio("B", eq.PINO, 0, 100)),
        (carga("P1", eq.PESO, 300, 400, 40),),
    ),
    ModeloDePeca(
        "Escada apoiada",
        "Pé no chão com atrito e topo encostado na parede lisa.",
        "m",
        "N",
        (trecho(0, 0, 1.5, 4),),
        (
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.4),
            apoio("B", eq.SIMPLES, 1.5, 4, 180),
        ),
        (
            carga("P1", eq.PESO, 0.75, 2, 15),
            carga("P2", eq.PESO, 0.45, 1.2, 80),
        ),
    ),
    ModeloDePeca(
        "Máquina sobre dois pés",
        "Peso no centro e uma força no alto. Mostra quando um pé levanta.",
        "mm",
        "N",
        (
            trecho(0, 0, 1000, 0),
            trecho(1000, 0, 1000, 900),
            trecho(1000, 900, 0, 900),
            trecho(0, 900, 0, 0),
        ),
        (
            apoio("A", eq.ATRITO, 0, 0, 90, mu=0.5),
            apoio("B", eq.SIMPLES, 1000, 0, 90),
        ),
        (
            carga("P1", eq.PESO, 500, 400, 300),
            carga("F1", eq.FORCA, 0, 900, 400, 0),
        ),
    ),
    ModeloDePeca(
        "Peça em rampa",
        "Bloco sobre roletes numa superfície inclinada, seguro por um cabo.",
        "m",
        "kN",
        (trecho(0, 0, 2, 1),),
        (
            apoio("A", eq.ROLETE, 0, 0, 116.57),
            apoio("B", eq.ROLETE, 2, 1, 116.57),
            apoio("C", eq.CABO, 2, 1, 26.57, ponta=(3, 1.5)),
        ),
        (carga("P1", eq.FORCA, 1, 0.5, 5),),
    ),
)

MODELO_INICIAL = MODELOS[0]
POR_NOME = {modelo.nome: modelo for modelo in MODELOS}
