"""Círculo de Mohr e transformação de estados de tensão.

Convenções adotadas
--------------------
- tensões normais de tração são positivas;
- ``tau_xy`` positiva atua na face positiva de x no sentido positivo de y;
- ângulos físicos são positivos no sentido anti-horário;
- no gráfico de Mohr, ``tau`` é desenhada positiva para cima. Assim, uma
  rotação física ``theta`` aparece como uma rotação de ``-2*theta`` no círculo.

Todos os valores de tensão são tratados em uma única unidade coerente. A
interface do projeto usa MPa.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class TransformacaoPlana:
    """Componentes do estado plano após uma rotação física dos eixos."""

    angulo_graus: float
    sigma_x_linha: float
    sigma_y_linha: float
    tau_x_linha_y_linha: float


@dataclass(frozen=True)
class ResultadoEstadoPlano:
    """Resumo completo de um estado plano de tensões."""

    centro: float
    raio: float
    sigma_1_plana: float
    sigma_2_plana: float
    theta_p1_graus: float
    theta_p2_graus: float
    tau_max_plana: float
    theta_tau_positivo_graus: float
    theta_tau_negativo_graus: float
    von_mises: float
    tensoes_principais_3d: tuple[float, float, float]
    tau_max_absoluta: float
    transformacao: TransformacaoPlana


@dataclass(frozen=True)
class TracaoEmPlano:
    """Vetor de tração e sua decomposição em um plano tridimensional."""

    normal_unitaria: np.ndarray
    vetor_tracao: np.ndarray
    sigma_normal: float
    vetor_cisalhamento: np.ndarray
    tau_resultante: float


@dataclass(frozen=True)
class CirculoMohr3D:
    """Centro e raio de um dos três círculos de Mohr tridimensionais."""

    par: str
    sigma_maior: float
    sigma_menor: float
    centro: float
    raio: float


@dataclass(frozen=True)
class ResultadoEstadoTridimensional:
    """Invariantes e direções principais de um tensor de tensões 3D."""

    tensor: np.ndarray
    tensoes_principais: tuple[float, float, float]
    direcoes_principais: np.ndarray
    tensao_media: float
    von_mises: float
    tresca_equivalente: float
    tau_max_absoluta: float
    tau_octaedrica: float
    I1: float
    I2: float
    I3: float
    J2: float
    J3: float
    circulos: tuple[CirculoMohr3D, CirculoMohr3D, CirculoMohr3D]


def _validar_finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser um número finito.")
    return valor


def _normalizar_angulo_180(angulo_graus: float) -> float:
    """Representa uma orientação de plano no intervalo [0°, 180°)."""
    angulo = float(angulo_graus) % 180.0
    return 0.0 if math.isclose(angulo, 180.0, abs_tol=1e-12) else angulo


def transformar_tensoes_planas(
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    theta_graus: float,
) -> TransformacaoPlana:
    """Transforma um estado plano para eixos girados de ``theta_graus``.

    ``theta_graus`` é medido de x para x' no sentido anti-horário. A
    transformação preserva o primeiro invariante:
    ``sigma_x' + sigma_y' = sigma_x + sigma_y``.
    """
    sigma_x = _validar_finito("sigma_x", sigma_x)
    sigma_y = _validar_finito("sigma_y", sigma_y)
    tau_xy = _validar_finito("tau_xy", tau_xy)
    theta_graus = _validar_finito("theta_graus", theta_graus)

    theta_duplo = math.radians(2.0 * theta_graus)
    centro = (sigma_x + sigma_y) / 2.0
    diferenca = (sigma_x - sigma_y) / 2.0
    cosseno = math.cos(theta_duplo)
    seno = math.sin(theta_duplo)

    sigma_x_linha = centro + diferenca * cosseno + tau_xy * seno
    sigma_y_linha = centro - diferenca * cosseno - tau_xy * seno
    tau_linha = -diferenca * seno + tau_xy * cosseno
    return TransformacaoPlana(
        angulo_graus=theta_graus,
        sigma_x_linha=sigma_x_linha,
        sigma_y_linha=sigma_y_linha,
        tau_x_linha_y_linha=tau_linha,
    )


def analisar_estado_plano(
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    theta_graus: float = 0.0,
) -> ResultadoEstadoPlano:
    """Calcula círculo, orientações, equivalentes e transformação 2D."""
    sigma_x = _validar_finito("sigma_x", sigma_x)
    sigma_y = _validar_finito("sigma_y", sigma_y)
    tau_xy = _validar_finito("tau_xy", tau_xy)

    centro = (sigma_x + sigma_y) / 2.0
    diferenca = (sigma_x - sigma_y) / 2.0
    raio = math.hypot(diferenca, tau_xy)
    sigma_1 = centro + raio
    sigma_2 = centro - raio

    theta_p1 = _normalizar_angulo_180(
        math.degrees(0.5 * math.atan2(2.0 * tau_xy, sigma_x - sigma_y))
    )
    theta_p2 = _normalizar_angulo_180(theta_p1 + 90.0)
    theta_tau_positivo = _normalizar_angulo_180(theta_p1 - 45.0)
    theta_tau_negativo = _normalizar_angulo_180(theta_p1 + 45.0)

    von_mises = math.sqrt(
        sigma_x**2 - sigma_x * sigma_y + sigma_y**2 + 3.0 * tau_xy**2
    )
    principais_3d = tuple(sorted((sigma_1, sigma_2, 0.0), reverse=True))
    tau_max_absoluta = (principais_3d[0] - principais_3d[2]) / 2.0

    return ResultadoEstadoPlano(
        centro=centro,
        raio=raio,
        sigma_1_plana=sigma_1,
        sigma_2_plana=sigma_2,
        theta_p1_graus=theta_p1,
        theta_p2_graus=theta_p2,
        tau_max_plana=raio,
        theta_tau_positivo_graus=theta_tau_positivo,
        theta_tau_negativo_graus=theta_tau_negativo,
        von_mises=von_mises,
        tensoes_principais_3d=principais_3d,
        tau_max_absoluta=tau_max_absoluta,
        transformacao=transformar_tensoes_planas(
            sigma_x, sigma_y, tau_xy, theta_graus
        ),
    )


def montar_tensor_tensoes(
    sigma_x: float,
    sigma_y: float,
    sigma_z: float,
    tau_xy: float,
    tau_xz: float,
    tau_yz: float,
) -> np.ndarray:
    """Monta o tensor simétrico de Cauchy a partir das seis componentes."""
    valores = {
        "sigma_x": sigma_x,
        "sigma_y": sigma_y,
        "sigma_z": sigma_z,
        "tau_xy": tau_xy,
        "tau_xz": tau_xz,
        "tau_yz": tau_yz,
    }
    validados = {nome: _validar_finito(nome, valor) for nome, valor in valores.items()}
    return np.array(
        [
            [validados["sigma_x"], validados["tau_xy"], validados["tau_xz"]],
            [validados["tau_xy"], validados["sigma_y"], validados["tau_yz"]],
            [validados["tau_xz"], validados["tau_yz"], validados["sigma_z"]],
        ],
        dtype=float,
    )


def _validar_tensor(tensor: np.ndarray | Iterable[Iterable[float]]) -> np.ndarray:
    matriz = np.asarray(tensor, dtype=float)
    if matriz.shape != (3, 3):
        raise ValueError("O tensor de tensões deve ter dimensão 3 × 3.")
    if not np.isfinite(matriz).all():
        raise ValueError("Todas as componentes do tensor devem ser finitas.")
    if not np.allclose(matriz, matriz.T, rtol=1e-10, atol=1e-10):
        raise ValueError("O tensor de tensões deve ser simétrico.")
    return matriz


def _orientar_autovetores(direcoes: np.ndarray) -> np.ndarray:
    """Escolhe sinais determinísticos sem alterar as direções principais."""
    orientadas = direcoes.copy()
    for coluna in range(orientadas.shape[1]):
        vetor = orientadas[:, coluna]
        indice = int(np.argmax(np.abs(vetor)))
        if vetor[indice] < 0:
            orientadas[:, coluna] *= -1.0
    return orientadas


def circulos_mohr_3d(
    tensoes_principais: Iterable[float],
) -> tuple[CirculoMohr3D, CirculoMohr3D, CirculoMohr3D]:
    """Retorna os círculos σ1–σ3, σ1–σ2 e σ2–σ3."""
    valores = np.asarray(tuple(tensoes_principais), dtype=float)
    if valores.shape != (3,) or not np.isfinite(valores).all():
        raise ValueError("Informe exatamente três tensões principais finitas.")
    sigma_1, sigma_2, sigma_3 = sorted(
        (float(valor) for valor in valores), reverse=True
    )

    def criar(par: str, maior: float, menor: float) -> CirculoMohr3D:
        return CirculoMohr3D(
            par=par,
            sigma_maior=maior,
            sigma_menor=menor,
            centro=(maior + menor) / 2.0,
            raio=(maior - menor) / 2.0,
        )

    return (
        criar("σ1–σ3", sigma_1, sigma_3),
        criar("σ1–σ2", sigma_1, sigma_2),
        criar("σ2–σ3", sigma_2, sigma_3),
    )


def analisar_estado_tridimensional(
    sigma_x: float,
    sigma_y: float,
    sigma_z: float,
    tau_xy: float,
    tau_xz: float,
    tau_yz: float,
) -> ResultadoEstadoTridimensional:
    """Calcula tensões principais, invariantes e equivalentes de um estado 3D."""
    tensor = montar_tensor_tensoes(
        sigma_x, sigma_y, sigma_z, tau_xy, tau_xz, tau_yz
    )
    autovalores, autovetores = np.linalg.eigh(tensor)
    ordem = np.argsort(autovalores)[::-1]
    principais_array = autovalores[ordem]
    direcoes = _orientar_autovetores(autovetores[:, ordem])
    principais = tuple(float(valor) for valor in principais_array)

    I1 = float(np.trace(tensor))
    I2 = float(0.5 * (I1**2 - np.trace(tensor @ tensor)))
    I3 = float(np.linalg.det(tensor))
    tensao_media = I1 / 3.0
    desviador = tensor - tensao_media * np.eye(3)
    J2 = float(0.5 * np.sum(desviador * desviador))
    J3 = float(np.linalg.det(desviador))
    von_mises = math.sqrt(max(0.0, 3.0 * J2))
    tau_max = (principais[0] - principais[2]) / 2.0

    return ResultadoEstadoTridimensional(
        tensor=tensor,
        tensoes_principais=principais,
        direcoes_principais=direcoes,
        tensao_media=tensao_media,
        von_mises=von_mises,
        tresca_equivalente=2.0 * tau_max,
        tau_max_absoluta=tau_max,
        tau_octaedrica=math.sqrt(max(0.0, 2.0 * J2 / 3.0)),
        I1=I1,
        I2=I2,
        I3=I3,
        J2=J2,
        J3=J3,
        circulos=circulos_mohr_3d(principais),
    )


def tracao_em_plano(
    tensor: np.ndarray | Iterable[Iterable[float]],
    normal: Iterable[float],
) -> TracaoEmPlano:
    """Obtém ``t = sigma·n`` e separa tensão normal e cisalhamento no plano."""
    matriz = _validar_tensor(tensor)
    vetor_normal = np.asarray(tuple(normal), dtype=float)
    if vetor_normal.shape != (3,) or not np.isfinite(vetor_normal).all():
        raise ValueError("A normal deve ter três componentes finitas.")
    norma = float(np.linalg.norm(vetor_normal))
    if math.isclose(norma, 0.0, abs_tol=1e-14):
        raise ValueError("O vetor normal não pode ser nulo.")

    normal_unitaria = vetor_normal / norma
    vetor_tracao = matriz @ normal_unitaria
    sigma_normal = float(normal_unitaria @ vetor_tracao)
    vetor_cisalhamento = vetor_tracao - sigma_normal * normal_unitaria
    tau_resultante = float(np.linalg.norm(vetor_cisalhamento))
    return TracaoEmPlano(
        normal_unitaria=normal_unitaria,
        vetor_tracao=vetor_tracao,
        sigma_normal=sigma_normal,
        vetor_cisalhamento=vetor_cisalhamento,
        tau_resultante=tau_resultante,
    )
