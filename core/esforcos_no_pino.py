"""O pino como viga: as chapas ou o engaste carregam o pino, e saem o cortante e o momento.

Cada chapa empurra o pino com a força distribuída por igual na espessura dela. Com isso, os dois
planos da articulação caem na fórmula F/8·(b + 4c + 2a) da EN 1993-1-8, que o teste confere. Sem
Streamlit e sem desenho: quem precisa é o cálculo, a tela e o Word.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

#: Pontos de cada trecho do diagrama. Dentro de uma chapa o cortante é reta e o momento é parábola.
_PONTOS_POR_TRECHO = 16


@dataclass(frozen=True)
class Chapa:
    """Uma chapa atravessada pelo pino. Medidas em mm e força em N, com sinal."""

    inicio: float
    espessura: float
    forca: float

    @property
    def fim(self) -> float:
        return self.inicio + self.espessura


def chapas_alternadas(planos: int, forca: float, a: float, b: float, c: float) -> tuple[Chapa, ...]:
    """As chapas de um pino com ``planos`` planos de corte, alternando o lado para onde puxam.

    Cada plano leva F/n. Por isso a chapa de dentro, com um plano de cada lado, recebe o dobro da
    de fora. ``a`` é a espessura das duas chapas das pontas, ``b`` a das de dentro e ``c`` a folga.
    """
    if planos < 1:
        raise ValueError("Um pino tem ao menos um plano de corte.")
    por_plano = forca / planos
    chapas: list[Chapa] = []
    posicao = 0.0
    for k in range(planos + 1):
        ponta = k in (0, planos)
        espessura = a if ponta else b
        intensidade = por_plano if ponta else 2.0 * por_plano
        chapas.append(Chapa(posicao, espessura, intensidade if k % 2 == 0 else -intensidade))
        posicao += espessura + c
    return tuple(chapas)


def planos_de_corte(chapas: Sequence[Chapa]) -> tuple[float, ...]:
    """A posição de cada plano de corte: no meio da folga entre duas chapas."""
    return tuple(
        (esquerda.fim + direita.inicio) / 2.0
        for esquerda, direita in zip(chapas, chapas[1:], strict=False)
    )


@dataclass(frozen=True)
class Diagrama:
    """Cortante e momento ao longo do pino. Posição em mm, cortante em N e momento em N·mm."""

    x: tuple[float, ...]
    cortante: tuple[float, ...]
    momento: tuple[float, ...]

    @property
    def cortante_max(self) -> float:
        return max(abs(v) for v in self.cortante)

    @property
    def momento_max(self) -> float:
        return max(abs(m) for m in self.momento)

    @property
    def x_do_momento_max(self) -> float:
        return max(zip(self.x, self.momento, strict=True), key=lambda par: abs(par[1]))[0]


def diagrama_das_chapas(chapas: Sequence[Chapa]) -> Diagrama:
    """Integra o carregamento das chapas ao longo do pino.

    Com número ímpar de planos, as forças formam um binário que as chapas não equilibram: ele fica
    dividido entre as duas pontas, na cabeça e na porca. Em corte simples isso dá F·(t₁ + t₂)/4.
    """
    if abs(sum(chapa.forca for chapa in chapas)) > 1e-6 * max(abs(c.forca) for c in chapas):
        raise ValueError("As forças das chapas precisam se equilibrar.")
    x: list[float] = [chapas[0].inicio]
    cortante: list[float] = [0.0]
    momento: list[float] = [0.0]
    v, m = 0.0, 0.0
    for chapa in chapas:
        folga = chapa.inicio - x[-1]
        if folga > 0:
            m += v * folga
            x.append(chapa.inicio)
            cortante.append(v)
            momento.append(m)
        carga = chapa.forca / chapa.espessura
        passos = [
            chapa.espessura * i / _PONTOS_POR_TRECHO for i in range(1, _PONTOS_POR_TRECHO + 1)
        ]
        if carga != 0.0 and 0.0 < -v / carga < chapa.espessura:
            passos = sorted({*passos, -v / carga})  # o pico do momento fica onde o cortante zera
        for s in passos:
            x.append(chapa.inicio + s)
            cortante.append(v + carga * s)
            momento.append(m + v * s + carga * s**2 / 2.0)
        s = chapa.espessura
        m += v * s + carga * s**2 / 2.0
        v += chapa.forca
    binario = momento[-1] / 2.0
    return Diagrama(tuple(x), tuple(cortante), tuple(valor - binario for valor in momento))


@dataclass(frozen=True)
class PinoEmBalanco:
    """Pino engastado num furo, com pressão linear ao longo do engaste.

    ``braco`` vai da face do furo até a linha da força, e ``engaste`` é o comprimento dentro do furo.
    """

    forca: float
    braco: float
    engaste: float
    d: float

    @property
    def _excentricidade(self) -> float:
        return self.braco + self.engaste / 2.0

    @property
    def _pressao_na_face(self) -> float:
        return (
            self.forca / (self.d * self.engaste) * (1.0 + 6.0 * self._excentricidade / self.engaste)
        )

    @property
    def _queda_da_pressao(self) -> float:
        return 12.0 * self.forca * self._excentricidade / (self.d * self.engaste**3)

    @property
    def pressao_max(self) -> float:
        """Na boca do furo. É (F/(d·L))·(4 + 6·a/L)."""
        return self._pressao_na_face

    @property
    def pressao_no_fundo(self) -> float:
        """No fundo do furo, em módulo. Sai do outro lado do pino."""
        return abs(self._pressao_na_face - self._queda_da_pressao * self.engaste)

    def _cortante(self, z: float) -> float:
        a, b = self._pressao_na_face, self._queda_da_pressao
        return self.forca - self.d * (a * z - b * z**2 / 2.0)

    def _momento(self, z: float) -> float:
        a, b = self._pressao_na_face, self._queda_da_pressao
        return self.forca * (self.braco + z) - self.d * (a * z**2 / 2.0 - b * z**3 / 6.0)

    @property
    def profundidade_do_momento_max(self) -> float:
        """O cortante zera dentro do furo, e é ali que está o maior momento, não na boca."""
        a, b = self._pressao_na_face, self._queda_da_pressao
        return (a - math.sqrt(a**2 - 2.0 * b * self.forca / self.d)) / b

    @property
    def momento_max(self) -> float:
        return self._momento(self.profundidade_do_momento_max)

    def diagrama(self) -> Diagrama:
        """De onde a força entra até o fundo do furo. O zero de x é a linha da força."""
        z_pico = self.profundidade_do_momento_max
        dentro = sorted(
            {z_pico, *(self.engaste * i / (2 * _PONTOS_POR_TRECHO) for i in range(1, 33))}
        )
        x = [0.0, self.braco, *(self.braco + z for z in dentro)]
        cortante = [self.forca, self.forca, *(self._cortante(z) for z in dentro)]
        momento = [0.0, self.forca * self.braco, *(self._momento(z) for z in dentro)]
        return Diagrama(tuple(x), tuple(cortante), tuple(momento))


def engaste_minimo(forca: float, braco: float, d: float, pressao_adm: float) -> float:
    """O menor engaste com pressão na boca até ``pressao_adm``: raiz de p·d·L² − 4FL − 6Fa = 0."""
    return (4.0 * forca + math.sqrt(16.0 * forca**2 + 24.0 * forca * braco * pressao_adm * d)) / (
        2.0 * pressao_adm * d
    )
