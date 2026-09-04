"""Critérios de falha estática baseados em tensões principais."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class ResultadoRankine:
    """Resultado do critério da máxima tensão normal."""

    fator_seguranca: float | None
    fator_tracao: float
    fator_compressao: float | None
    modo_critico: str
    completo: bool


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser finito e maior que zero.")
    return valor


def _equivalente(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser finito e não negativo.")
    return valor


def _principais(tensoes_principais: Iterable[float]) -> tuple[float, float, float]:
    valores = tuple(float(valor) for valor in tensoes_principais)
    if len(valores) != 3 or not all(math.isfinite(valor) for valor in valores):
        raise ValueError("Informe exatamente três tensões principais finitas.")
    return tuple(sorted(valores, reverse=True))


def fator_seguranca_von_mises(
    tensao_von_mises_MPa: float, Sy_MPa: float
) -> float:
    """Fator de segurança ao escoamento por von Mises."""
    equivalente = _equivalente("tensao_von_mises_MPa", tensao_von_mises_MPa)
    Sy_MPa = _positivo("Sy_MPa", Sy_MPa)
    return math.inf if equivalente == 0 else Sy_MPa / equivalente


def tensao_equivalente_tresca(
    tensoes_principais: Iterable[float],
) -> float:
    """Equivalente de Tresca: maior diferença entre tensões principais."""
    sigma_1, _, sigma_3 = _principais(tensoes_principais)
    return sigma_1 - sigma_3


def fator_seguranca_tresca(
    tensoes_principais: Iterable[float], Sy_MPa: float
) -> float:
    """Fator de segurança ao escoamento pelo critério de Tresca."""
    Sy_MPa = _positivo("Sy_MPa", Sy_MPa)
    equivalente = tensao_equivalente_tresca(tensoes_principais)
    return math.inf if equivalente == 0 else Sy_MPa / equivalente


def fator_seguranca_rankine(
    tensoes_principais: Iterable[float],
    Sut_MPa: float,
    Suc_MPa: float | None = None,
) -> ResultadoRankine:
    """Máxima tensão normal com resistências distintas à tração/compressão.

    Quando há tensão principal compressiva e ``Suc_MPa`` não foi informada, o
    fator global fica indisponível para evitar uma conclusão incompleta.
    """
    sigma_1, _, sigma_3 = _principais(tensoes_principais)
    Sut_MPa = _positivo("Sut_MPa", Sut_MPa)
    if Suc_MPa is not None:
        Suc_MPa = _positivo("Suc_MPa", Suc_MPa)

    fator_tracao = math.inf if sigma_1 <= 0 else Sut_MPa / sigma_1
    existe_compressao = sigma_3 < 0
    if existe_compressao and Suc_MPa is None:
        return ResultadoRankine(
            fator_seguranca=None,
            fator_tracao=fator_tracao,
            fator_compressao=None,
            modo_critico="resistência à compressão ausente",
            completo=False,
        )

    fator_compressao = (
        Suc_MPa / abs(sigma_3)
        if existe_compressao and Suc_MPa is not None
        else math.inf
    )
    if fator_tracao <= fator_compressao:
        modo = "tração"
        fator_global = fator_tracao
    else:
        modo = "compressão"
        fator_global = fator_compressao
    if math.isinf(fator_global):
        modo = "sem tensão normal solicitante"
    return ResultadoRankine(
        fator_seguranca=fator_global,
        fator_tracao=fator_tracao,
        fator_compressao=fator_compressao,
        modo_critico=modo,
        completo=True,
    )
