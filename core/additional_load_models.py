"""Modelos adicionais para converter carregamentos em tensões planas.

As entradas usam N e mm; as tensões resultam em N/mm² = MPa.
"""

from __future__ import annotations

import math

from core.load_to_stress import EstadoPlanoCalculado


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


def eixo_circular_vazado(
    diametro_externo_mm: float,
    diametro_interno_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
    torque_Nmm: float,
    face_flexao: str = "tracionada",
) -> EstadoPlanoCalculado:
    """Estado na superfície externa de um eixo circular vazado."""
    de = _positivo("diametro_externo_mm", diametro_externo_mm)
    di = _finito("diametro_interno_mm", diametro_interno_mm)
    if di < 0:
        raise ValueError("O diâmetro interno não pode ser negativo.")
    if di >= de:
        raise ValueError(
            "O diâmetro interno deve ser menor que o diâmetro externo."
        )
    forca = _finito("forca_axial_N", forca_axial_N)
    momento = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    torque = _finito("torque_Nmm", torque_Nmm)
    if face_flexao not in {"tracionada", "comprimida"}:
        raise ValueError("face_flexao deve ser 'tracionada' ou 'comprimida'.")

    area = math.pi * (de**2 - di**2) / 4.0
    inercia = math.pi * (de**4 - di**4) / 64.0
    momento_polar = 2.0 * inercia
    raio = de / 2.0
    sinal = 1.0 if face_flexao == "tracionada" else -1.0

    return EstadoPlanoCalculado(
        sigma_x=forca / area + sinal * abs(momento) * raio / inercia,
        sigma_y=0.0,
        tau_xy=torque * raio / momento_polar,
        descricao=f"Superfície {face_flexao} de eixo circular vazado",
        hipoteses=(
            "Seção circular vazada concêntrica e comportamento elástico linear.",
            "Resultado avaliado na superfície externa.",
            "Momento informado como magnitude; o lado define seu sinal.",
            "Concentrações de tensão nas extremidades não incluídas.",
        ),
    )


def secao_retangular_flexao_biaxial(
    largura_mm: float,
    altura_mm: float,
    coordenada_y_mm: float,
    coordenada_z_mm: float,
    forca_axial_N: float,
    momento_y_Nmm: float,
    momento_z_Nmm: float,
) -> EstadoPlanoCalculado:
    """Tensão normal em seção retangular sob axial e flexão biaxial."""
    largura = _positivo("largura_mm", largura_mm)
    altura = _positivo("altura_mm", altura_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    z = _finito("coordenada_z_mm", coordenada_z_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento_y = _finito("momento_y_Nmm", momento_y_Nmm)
    momento_z = _finito("momento_z_Nmm", momento_z_Nmm)
    if abs(y) > altura / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura.")
    if abs(z) > largura / 2.0:
        raise ValueError("A coordenada z deve estar dentro da largura.")

    area = largura * altura
    inercia_y = altura * largura**3 / 12.0
    inercia_z = largura * altura**3 / 12.0
    sigma = (
        forca / area
        + momento_y * z / inercia_y
        - momento_z * y / inercia_z
    )
    return EstadoPlanoCalculado(
        sigma_x=sigma,
        sigma_y=0.0,
        tau_xy=0.0,
        descricao="Seção retangular sob força axial e flexão biaxial",
        hipoteses=(
            "Flexão composta em seção retangular prismática.",
            "Eixos y e z são centroidais e principais de inércia.",
            "y é positivo para cima e z para a direita.",
            "Cisalhamento e torção não incluídos neste modelo.",
        ),
    )


def secao_i_flexao(
    altura_total_mm: float,
    largura_mesa_mm: float,
    espessura_mesa_mm: float,
    espessura_alma_mm: float,
    coordenada_y_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
) -> EstadoPlanoCalculado:
    """Tensão normal em seção I duplamente simétrica sob N e M."""
    altura = _positivo("altura_total_mm", altura_total_mm)
    mesa = _positivo("largura_mesa_mm", largura_mesa_mm)
    t_mesa = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    t_alma = _positivo("espessura_alma_mm", espessura_alma_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    if 2.0 * t_mesa >= altura:
        raise ValueError("A soma das mesas deve ser menor que a altura total.")
    if t_alma >= mesa:
        raise ValueError("A espessura da alma deve ser menor que a mesa.")
    if abs(y) > altura / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura.")

    altura_alma = altura - 2.0 * t_mesa
    area = 2.0 * mesa * t_mesa + t_alma * altura_alma
    inercia = (
        mesa * altura**3 - (mesa - t_alma) * altura_alma**3
    ) / 12.0
    return EstadoPlanoCalculado(
        sigma_x=forca / area - momento * y / inercia,
        sigma_y=0.0,
        tau_xy=0.0,
        descricao="Seção I duplamente simétrica sob força axial e flexão",
        hipoteses=(
            "Seção I idealizada, duplamente simétrica e sem concordâncias.",
            "Flexão em torno do eixo centroidal forte.",
            "Cisalhamento, flambagem local e lateral não incluídos.",
            "Comportamento elástico linear.",
        ),
    )


def pino_cisalhamento(
    forca_N: float,
    diametro_mm: float,
    numero_pinos: int = 1,
    numero_planos_corte: int = 1,
) -> EstadoPlanoCalculado:
    """Cisalhamento médio em pinos ou parafusos igualmente carregados."""
    forca = _finito("forca_N", forca_N)
    diametro = _positivo("diametro_mm", diametro_mm)
    if int(numero_pinos) != numero_pinos or numero_pinos < 1:
        raise ValueError("O número de pinos deve ser um inteiro positivo.")
    if numero_planos_corte not in {1, 2}:
        raise ValueError("O número de planos de corte deve ser 1 ou 2.")

    area = math.pi * diametro**2 / 4.0
    tau = forca / (int(numero_pinos) * numero_planos_corte * area)
    return EstadoPlanoCalculado(
        sigma_x=0.0,
        sigma_y=0.0,
        tau_xy=tau,
        descricao=(
            f"{int(numero_pinos)} pino(s) em cisalhamento "
            f"{'duplo' if numero_planos_corte == 2 else 'simples'}"
        ),
        hipoteses=(
            "Carga dividida igualmente entre os pinos.",
            "Tensão de cisalhamento média na seção resistente.",
            "Flexão do pino, esmagamento e concentração não incluídos.",
            "Use a área resistente da rosca se o corte cruzar a rosca.",
        ),
    )


def tubo_fino_pressao_axial_torcao(
    pressao_MPa: float,
    diametro_medio_mm: float,
    espessura_mm: float,
    extremidades_fechadas: bool = True,
    forca_axial_N: float = 0.0,
    torque_Nmm: float = 0.0,
) -> EstadoPlanoCalculado:
    """Estado em tubo fino sob pressão, carga axial e torque."""
    pressao = _finito("pressao_MPa", pressao_MPa)
    diametro = _positivo("diametro_medio_mm", diametro_medio_mm)
    espessura = _positivo("espessura_mm", espessura_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    torque = _finito("torque_Nmm", torque_Nmm)
    if pressao < 0:
        raise ValueError("A pressão não pode ser negativa neste modelo.")

    sigma_circunferencial = pressao * diametro / (2.0 * espessura)
    sigma_pressao_longitudinal = (
        pressao * diametro / (4.0 * espessura)
        if extremidades_fechadas
        else 0.0
    )
    area_parede = math.pi * diametro * espessura
    sigma_longitudinal = sigma_pressao_longitudinal + forca / area_parede
    tau = 2.0 * torque / (math.pi * diametro**2 * espessura)
    return EstadoPlanoCalculado(
        sigma_x=sigma_longitudinal,
        sigma_y=sigma_circunferencial,
        tau_xy=tau,
        descricao="Tubo fino sob pressão, força axial e torção",
        hipoteses=(
            "Tensões de membrana longe de tampas, bocais e descontinuidades.",
            "Tensão radial desprezada frente às tensões de membrana.",
            "Força axial e torque distribuídos uniformemente na parede.",
            "Verifique D/t; abaixo de 20, use um modelo de parede espessa.",
        ),
    )


def vaso_esferico_parede_fina(
    pressao_MPa: float,
    diametro_medio_mm: float,
    espessura_mm: float,
) -> EstadoPlanoCalculado:
    """Tensões de membrana em vaso esférico fino sob pressão interna."""
    pressao = _finito("pressao_MPa", pressao_MPa)
    diametro = _positivo("diametro_medio_mm", diametro_medio_mm)
    espessura = _positivo("espessura_mm", espessura_mm)
    if pressao < 0:
        raise ValueError("A pressão não pode ser negativa neste modelo.")
    sigma = pressao * diametro / (4.0 * espessura)
    return EstadoPlanoCalculado(
        sigma_x=sigma,
        sigma_y=sigma,
        tau_xy=0.0,
        descricao="Parede de vaso esférico fino sob pressão interna",
        hipoteses=(
            "Casca esférica fina, íntegra e sob pressão interna uniforme.",
            "Tensões de membrana iguais nas duas direções tangenciais.",
            "Tensão radial e efeitos de bocais e suportes desprezados.",
            "Verifique D/t; abaixo de 20, use um modelo de parede espessa.",
        ),
    )
