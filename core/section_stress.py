"""Tensões combinadas em um ponto de seção de barra.

Este é o núcleo compartilhado entre o assistente de cargas
(:mod:`core.load_to_stress`) e a análise de vigas e eixos
(:mod:`core.beam_analysis`): as duas partes do programa precisam somar
``N/A``, ``M c/I``, ``V Q/(I t)`` e ``T/Wt`` da mesma forma e com a mesma
convenção de sinais. Mantê-las em um único lugar evita o pior tipo de bug
neste programa — duas respostas diferentes para a mesma seção, dependendo
da página em que o usuário entrou.

Convenções (as mesmas de :mod:`core.beam_analysis`):

* ``M`` positivo comprime a fibra superior;
* ``N`` positivo traciona;
* ``y`` é medido do centroide e positivo para cima.

Unidades: N, mm, MPa e N·mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class SecaoTensionavel(Protocol):
    """Propriedades geométricas necessárias para o cálculo das tensões.

    É um protocolo (e não uma classe base) de propósito: tanto a
    :class:`PropriedadesSecao` deste módulo quanto a ``SecaoViga`` da análise
    de vigas o satisfazem sem herança nem importação cruzada.

    As propriedades são declaradas como somente-leitura porque as duas
    implementações são dataclasses congeladas; exigir atributo gravável
    excluiria justamente quem deveria satisfazer o protocolo.
    """

    @property
    def area_mm2(self) -> float: ...

    @property
    def inercia_mm4(self) -> float: ...

    @property
    def c_superior_mm(self) -> float: ...

    @property
    def c_inferior_mm(self) -> float: ...

    @property
    def momento_estatico_mm3(self) -> float: ...

    @property
    def espessura_cisalhamento_mm(self) -> float: ...

    @property
    def modulo_torcao_mm3(self) -> float: ...

    @property
    def area_cisalhamento_mm2(self) -> float: ...


@dataclass(frozen=True, slots=True)
class PropriedadesSecao:
    """Implementação avulsa do protocolo, para quem só tem as dimensões."""

    area_mm2: float
    inercia_mm4: float
    c_superior_mm: float
    c_inferior_mm: float
    momento_estatico_mm3: float = 0.0
    espessura_cisalhamento_mm: float = 0.0
    modulo_torcao_mm3: float = 0.0
    area_cisalhamento_mm2: float = 0.0


@dataclass(frozen=True, slots=True)
class EsforcosSecao:
    """Esforços internos atuando na seção."""

    normal_N: float = 0.0
    momento_Nmm: float = 0.0
    cortante_N: float = 0.0
    torque_Nmm: float = 0.0


@dataclass(frozen=True, slots=True)
class PontoTensao:
    """Estado de um ponto candidato: só ``σ`` e ``τ`` são não nulos."""

    nome: str
    sigma_MPa: float
    tau_MPa: float

    @property
    def von_mises_MPa(self) -> float:
        return math.sqrt(self.sigma_MPa**2 + 3.0 * self.tau_MPa**2)

    @property
    def tresca_MPa(self) -> float:
        return math.sqrt(self.sigma_MPa**2 + 4.0 * self.tau_MPa**2)


@dataclass(frozen=True, slots=True)
class TensoesCombinadas:
    """Parcelas de tensão e os pontos candidatos da seção."""

    axial_MPa: float
    flexao_superior_MPa: float
    flexao_inferior_MPa: float
    cisalhamento_MPa: float
    torcao_MPa: float
    pontos: tuple[PontoTensao, ...]

    @property
    def normal_superior_MPa(self) -> float:
        return self.axial_MPa + self.flexao_superior_MPa

    @property
    def normal_inferior_MPa(self) -> float:
        return self.axial_MPa + self.flexao_inferior_MPa

    @property
    def critico(self) -> PontoTensao:
        """Ponto de maior von Mises; empate fica com o último candidato."""
        melhor = self.pontos[0]
        for ponto in self.pontos[1:]:
            if ponto.von_mises_MPa >= melhor.von_mises_MPa:
                melhor = ponto
        return melhor

    def ponto(self, nome: str) -> PontoTensao:
        procurado = nome.strip().casefold()
        for ponto in self.pontos:
            if ponto.nome.casefold() == procurado:
                return ponto
        disponiveis = ", ".join(ponto.nome for ponto in self.pontos)
        raise KeyError(f"Ponto {nome!r} não existe. Disponíveis: {disponiveis}.")


NOME_SUPERIOR = "Fibra superior"
NOME_INFERIOR = "Fibra inferior"
NOME_NEUTRA = "Linha neutra"


def tensao_cisalhamento(esforcos: EsforcosSecao, secao: SecaoTensionavel) -> float:
    """``V Q/(I t)`` quando ``Q`` é conhecido; ``V/A_v`` como alternativa.

    Perfis de catálogo não trazem ``Q`` tabelado, e inventar um valor seria
    pior do que usar a rota normativa da área de cisalhamento.
    """
    if secao.momento_estatico_mm3 > 0 and secao.espessura_cisalhamento_mm > 0:
        return (
            esforcos.cortante_N
            * secao.momento_estatico_mm3
            / (secao.inercia_mm4 * secao.espessura_cisalhamento_mm)
        )
    if secao.area_cisalhamento_mm2 > 0:
        return esforcos.cortante_N / secao.area_cisalhamento_mm2
    return 0.0


def tensao_torcao(esforcos: EsforcosSecao, secao: SecaoTensionavel) -> float:
    """``T/Wt`` — e não ``T c/J``, que só vale para seção circular."""
    if secao.modulo_torcao_mm3 <= 0:
        return 0.0
    return esforcos.torque_Nmm / secao.modulo_torcao_mm3


def tensao_normal_em(
    esforcos: EsforcosSecao, secao: SecaoTensionavel, y_mm: float
) -> float:
    """Tensão normal a ``y_mm`` do centroide (positivo para cima)."""
    return (
        esforcos.normal_N / secao.area_mm2
        - esforcos.momento_Nmm * y_mm / secao.inercia_mm4
    )


def cisalhamento_na_linha_neutra(cisalhamento_MPa: float, torcao_MPa: float) -> float:
    """``|τ_V| + |τ_T|``, com o sinal da parcela dominante.

    Na linha neutra as duas tensões são paralelas (tangentes ao contorno,
    na direção de ``V``): de um lado da seção elas se somam, do outro se
    subtraem. O ponto que governa é o lado em que somam — e o sinal
    relativo entre ``V`` e ``T`` depende só da convenção de eixos, não da
    física, então não pode reduzir a tensão. Somar com sinal, como se
    fazia antes, subestimava o von Mises sempre que ``V`` e ``T`` tinham
    sinais opostos — o que acontece em metade de qualquer eixo com torque
    e carga transversal.
    """
    magnitude = abs(cisalhamento_MPa) + abs(torcao_MPa)
    dominante = (
        cisalhamento_MPa if abs(cisalhamento_MPa) >= abs(torcao_MPa) else torcao_MPa
    )
    return math.copysign(magnitude, dominante)


def tensoes_combinadas(
    esforcos: EsforcosSecao, secao: SecaoTensionavel
) -> TensoesCombinadas:
    """Parcelas de tensão e os três pontos candidatos da seção.

    Os candidatos são fibra superior, fibra inferior e linha neutra. Avaliar
    os três — em vez de somar a flexão máxima com o cisalhamento máximo —
    evita o erro clássico de superpor tensões que ocorrem em pontos
    diferentes: na fibra extrema o cisalhamento de ``V`` é nulo, e na linha
    neutra a tensão de flexão é nula. Na linha neutra, ``V`` e ``T`` somam
    em módulo (ver :func:`cisalhamento_na_linha_neutra`).
    """
    axial = esforcos.normal_N / secao.area_mm2
    flexao_superior = -esforcos.momento_Nmm * secao.c_superior_mm / secao.inercia_mm4
    flexao_inferior = esforcos.momento_Nmm * secao.c_inferior_mm / secao.inercia_mm4
    cisalhamento = tensao_cisalhamento(esforcos, secao)
    torcao = tensao_torcao(esforcos, secao)

    return TensoesCombinadas(
        axial_MPa=axial,
        flexao_superior_MPa=flexao_superior,
        flexao_inferior_MPa=flexao_inferior,
        cisalhamento_MPa=cisalhamento,
        torcao_MPa=torcao,
        pontos=(
            PontoTensao(NOME_SUPERIOR, axial + flexao_superior, torcao),
            PontoTensao(NOME_INFERIOR, axial + flexao_inferior, torcao),
            PontoTensao(
                NOME_NEUTRA, axial, cisalhamento_na_linha_neutra(cisalhamento, torcao)
            ),
        ),
    )
