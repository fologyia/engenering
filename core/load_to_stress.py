"""Conversão de carregamentos elementares em estados planos de tensão.

As funções trabalham em N e mm, portanto as tensões resultam em N/mm² = MPa.
Elas representam modelos clássicos de resistência dos materiais e não incluem
concentrações de tensão, efeitos de apoio ou distribuições tridimensionais.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EstadoPlanoCalculado:
    """Componentes planas calculadas no mesmo ponto da seção."""

    sigma_x: float
    sigma_y: float
    tau_xy: float
    descricao: str
    hipoteses: tuple[str, ...]


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser um número finito.")
    return valor


def _positivo(nome: str, valor: float) -> float:
    valor = _finito(nome, valor)
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def barra_axial(forca_N: float, area_mm2: float) -> EstadoPlanoCalculado:
    """Tensão uniforme em barra prismática: sigma_x = F/A."""
    forca_N = _finito("forca_N", forca_N)
    area_mm2 = _positivo("area_mm2", area_mm2)
    return EstadoPlanoCalculado(
        sigma_x=forca_N / area_mm2,
        sigma_y=0.0,
        tau_xy=0.0,
        descricao="Barra sob carga axial",
        hipoteses=(
            "Carga aplicada pelo centroide da seção.",
            "Tensão uniforme longe das regiões de aplicação da carga.",
            "Concentrações de tensão não incluídas.",
        ),
    )


def eixo_circular_macico(
    diametro_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
    torque_Nmm: float,
    face_flexao: str = "tracionada",
) -> EstadoPlanoCalculado:
    """Estado na superfície de eixo maciço sob axial, flexão e torção."""
    diametro_mm = _positivo("diametro_mm", diametro_mm)
    forca_axial_N = _finito("forca_axial_N", forca_axial_N)
    momento_fletor_Nmm = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    torque_Nmm = _finito("torque_Nmm", torque_Nmm)
    if face_flexao not in {"tracionada", "comprimida"}:
        raise ValueError("face_flexao deve ser 'tracionada' ou 'comprimida'.")

    area = math.pi * diametro_mm**2 / 4.0
    sigma_axial = forca_axial_N / area
    sigma_flexao_modulo = 32.0 * abs(momento_fletor_Nmm) / (
        math.pi * diametro_mm**3
    )
    sinal_flexao = 1.0 if face_flexao == "tracionada" else -1.0
    tau_torcao = 16.0 * torque_Nmm / (math.pi * diametro_mm**3)
    return EstadoPlanoCalculado(
        sigma_x=sigma_axial + sinal_flexao * sigma_flexao_modulo,
        sigma_y=0.0,
        tau_xy=tau_torcao,
        descricao=f"Superfície {face_flexao} de eixo circular maciço",
        hipoteses=(
            "Seção circular maciça e comportamento elástico linear.",
            "Resultado avaliado na superfície externa.",
            "Momento fletor informado como magnitude; o lado define seu sinal.",
            "Torque positivo segue a convenção de tau_xy positiva.",
        ),
    )


def viga_retangular(
    largura_mm: float,
    altura_mm: float,
    coordenada_y_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
    forca_cortante_N: float,
) -> EstadoPlanoCalculado:
    """Estado em um ponto de seção retangular sob N, M e V.

    ``coordenada_y_mm`` é medida a partir do centroide e positiva para a fibra
    superior. Momento positivo comprime a região de y positivo.
    """
    largura_mm = _positivo("largura_mm", largura_mm)
    altura_mm = _positivo("altura_mm", altura_mm)
    coordenada_y_mm = _finito("coordenada_y_mm", coordenada_y_mm)
    forca_axial_N = _finito("forca_axial_N", forca_axial_N)
    momento_fletor_Nmm = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    forca_cortante_N = _finito("forca_cortante_N", forca_cortante_N)
    if abs(coordenada_y_mm) > altura_mm / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura da seção.")

    area = largura_mm * altura_mm
    inercia = largura_mm * altura_mm**3 / 12.0
    sigma_x = (
        forca_axial_N / area
        - momento_fletor_Nmm * coordenada_y_mm / inercia
    )
    fator_posicao = 1.0 - (2.0 * coordenada_y_mm / altura_mm) ** 2
    tau_xy = 1.5 * forca_cortante_N / area * max(0.0, fator_posicao)
    return EstadoPlanoCalculado(
        sigma_x=sigma_x,
        sigma_y=0.0,
        tau_xy=tau_xy,
        descricao="Ponto de seção retangular sob força axial, flexão e cortante",
        hipoteses=(
            "Teoria de vigas esbeltas e comportamento elástico linear.",
            "Seção retangular constante.",
            "y é medido do centroide e positivo para a fibra superior.",
            "Momento positivo comprime a região de y positivo.",
        ),
    )


def vaso_cilindrico_parede_fina(
    pressao_MPa: float,
    diametro_medio_mm: float,
    espessura_mm: float,
    extremidades_fechadas: bool = True,
) -> EstadoPlanoCalculado:
    """Estado de membrana em vaso cilíndrico fino sob pressão interna."""
    pressao_MPa = _finito("pressao_MPa", pressao_MPa)
    diametro_medio_mm = _positivo("diametro_medio_mm", diametro_medio_mm)
    espessura_mm = _positivo("espessura_mm", espessura_mm)
    if pressao_MPa < 0:
        raise ValueError("pressao_MPa não pode ser negativa neste modelo.")

    sigma_circunferencial = (
        pressao_MPa * diametro_medio_mm / (2.0 * espessura_mm)
    )
    sigma_longitudinal = (
        pressao_MPa * diametro_medio_mm / (4.0 * espessura_mm)
        if extremidades_fechadas
        else 0.0
    )
    return EstadoPlanoCalculado(
        sigma_x=sigma_longitudinal,
        sigma_y=sigma_circunferencial,
        tau_xy=0.0,
        descricao="Parede de vaso cilíndrico fino sob pressão interna",
        hipoteses=(
            "Tensões de membrana longe de tampas, bocais e descontinuidades.",
            "Pressão externa desprezada.",
            "Tensão radial desprezada em comparação às tensões de membrana.",
            "Verifique D/t; valores abaixo de 20 exigem modelo de parede espessa.",
        ),
    )


def relacao_diametro_espessura(
    diametro_medio_mm: float, espessura_mm: float
) -> float:
    """Retorna D/t para avaliar a hipótese de parede fina."""
    return _positivo("diametro_medio_mm", diametro_medio_mm) / _positivo(
        "espessura_mm", espessura_mm
    )
