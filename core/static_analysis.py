"""
Análise estática — verificação de falha por escoamento/ruptura sob
carregamento estático, usando tensão equivalente de von Mises.

Convenção: estado plano de tensões (sigma_x, sigma_y, tau_xy).
"""
import math


def _validar_finito(nome: str, valor: float) -> None:
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser um número finito.")


def tensao_von_mises_plana(
    sigma_x: float, sigma_y: float = 0.0, tau_xy: float = 0.0
) -> float:
    """Tensão equivalente de von Mises para estado plano, em MPa."""
    for nome, valor in (
        ("sigma_x", sigma_x),
        ("sigma_y", sigma_y),
        ("tau_xy", tau_xy),
    ):
        _validar_finito(nome, valor)
    return math.sqrt(
        sigma_x**2 - sigma_x * sigma_y + sigma_y**2 + 3 * tau_xy**2
    )


def tensoes_principais_planas(
    sigma_x: float, sigma_y: float, tau_xy: float
) -> tuple[float, float]:
    """Retorna (sigma_1, sigma_2) para o estado plano de tensões."""
    for nome, valor in (
        ("sigma_x", sigma_x),
        ("sigma_y", sigma_y),
        ("tau_xy", tau_xy),
    ):
        _validar_finito(nome, valor)
    centro = (sigma_x + sigma_y) / 2
    raio = math.sqrt(((sigma_x - sigma_y) / 2) ** 2 + tau_xy**2)
    return centro + raio, centro - raio


def fator_seguranca_escoamento(sigma_vm: float, Sy: float) -> float:
    """Fator de segurança contra escoamento (critério de von Mises)."""
    _validar_finito("sigma_vm", sigma_vm)
    _validar_finito("Sy", Sy)
    if sigma_vm < 0:
        raise ValueError("sigma_vm não pode ser negativo.")
    if Sy <= 0:
        raise ValueError("Sy deve ser maior que zero.")
    return math.inf if sigma_vm == 0 else Sy / sigma_vm


def fator_seguranca_ruptura(sigma_vm: float, Sut: float) -> float:
    """Fator de segurança contra ruptura estática."""
    _validar_finito("sigma_vm", sigma_vm)
    _validar_finito("Sut", Sut)
    if sigma_vm < 0:
        raise ValueError("sigma_vm não pode ser negativo.")
    if Sut <= 0:
        raise ValueError("Sut deve ser maior que zero.")
    return math.inf if sigma_vm == 0 else Sut / sigma_vm