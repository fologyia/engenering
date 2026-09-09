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
    forca_cortante_N: float = 0.0,
) -> EstadoPlanoCalculado:
    """Tensão normal e cisalhante em seção I duplamente simétrica."""
    altura = _positivo("altura_total_mm", altura_total_mm)
    mesa = _positivo("largura_mesa_mm", largura_mesa_mm)
    t_mesa = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    t_alma = _positivo("espessura_alma_mm", espessura_alma_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    cortante = _finito("forca_cortante_N", forca_cortante_N)
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

    # Fluxo de cisalhamento de Jourawski: o momento estático e a largura
    # resistente mudam conforme o ponto caia na mesa ou na alma.
    meia_alma = altura_alma / 2.0
    if abs(y) >= meia_alma:
        largura_resistente = mesa
        momento_estatico = mesa * (altura**2 / 4.0 - y**2) / 2.0
    else:
        largura_resistente = t_alma
        momento_estatico = (
            mesa * t_mesa * (altura - t_mesa) / 2.0
            + t_alma * (meia_alma**2 - y**2) / 2.0
        )
    tau = cortante * momento_estatico / (inercia * largura_resistente)

    return EstadoPlanoCalculado(
        sigma_x=forca / area - momento * y / inercia,
        sigma_y=0.0,
        tau_xy=tau,
        descricao=(
            "Seção I duplamente simétrica sob força axial, flexão e cortante"
        ),
        hipoteses=(
            "Seção I idealizada, duplamente simétrica e sem concordâncias.",
            "Flexão em torno do eixo centroidal forte.",
            "Cisalhamento pela fórmula de Jourawski (τ = VQ/It).",
            "Flambagem local, flambagem lateral e torção não incluídas.",
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


def fator_nucleo_central(
    largura_b_mm: float,
    altura_h_mm: float,
    excentricidade_y_mm: float,
    excentricidade_z_mm: float,
) -> float:
    """Posição da carga em relação ao núcleo central da seção retangular.

    Retorna |e_y|/(h/6) + |e_z|/(b/6). Valores até 1,0 mantêm a seção
    inteiramente comprimida (ou inteiramente tracionada); acima disso há
    inversão de sinal e parte da seção passa a trabalhar ao contrário.
    """
    largura = _positivo("largura_b_mm", largura_b_mm)
    altura = _positivo("altura_h_mm", altura_h_mm)
    ey = _finito("excentricidade_y_mm", excentricidade_y_mm)
    ez = _finito("excentricidade_z_mm", excentricidade_z_mm)
    return abs(ey) / (altura / 6.0) + abs(ez) / (largura / 6.0)


def barra_axial_excentrica(
    forca_N: float,
    largura_b_mm: float,
    altura_h_mm: float,
    excentricidade_y_mm: float,
    excentricidade_z_mm: float,
    coordenada_y_mm: float,
    coordenada_z_mm: float,
) -> EstadoPlanoCalculado:
    """Carga axial aplicada fora do centroide de uma seção retangular."""
    forca = _finito("forca_N", forca_N)
    largura = _positivo("largura_b_mm", largura_b_mm)
    altura = _positivo("altura_h_mm", altura_h_mm)
    ey = _finito("excentricidade_y_mm", excentricidade_y_mm)
    ez = _finito("excentricidade_z_mm", excentricidade_z_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    z = _finito("coordenada_z_mm", coordenada_z_mm)
    if abs(y) > altura / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura.")
    if abs(z) > largura / 2.0:
        raise ValueError("A coordenada z deve estar dentro da largura.")

    area = largura * altura
    sigma = (forca / area) * (
        1.0
        + 12.0 * ey * y / altura**2
        + 12.0 * ez * z / largura**2
    )
    return EstadoPlanoCalculado(
        sigma_x=sigma,
        sigma_y=0.0,
        tau_xy=0.0,
        descricao="Barra retangular sob carga axial excêntrica",
        hipoteses=(
            "Seção retangular cheia e material elástico linear.",
            "Excentricidade constante ao longo do comprimento.",
            "Efeitos de segunda ordem e flambagem não incluídos — "
            "críticos se a barra for esbelta e estiver comprimida.",
            "Concentrações de tensão junto ao ponto de aplicação ignoradas.",
        ),
    )


def secao_tubular_retangular(
    largura_b_mm: float,
    altura_h_mm: float,
    espessura_mm: float,
    coordenada_y_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
    torque_Nmm: float,
) -> EstadoPlanoCalculado:
    """Perfil tubular retangular (caixão) sob força axial, flexão e torção."""
    largura = _positivo("largura_b_mm", largura_b_mm)
    altura = _positivo("altura_h_mm", altura_h_mm)
    espessura = _positivo("espessura_mm", espessura_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    torque = _finito("torque_Nmm", torque_Nmm)
    if 2.0 * espessura >= min(largura, altura):
        raise ValueError(
            "A espessura deve ser menor que metade do menor lado da seção."
        )
    if abs(y) > altura / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura.")

    largura_interna = largura - 2.0 * espessura
    altura_interna = altura - 2.0 * espessura
    area = largura * altura - largura_interna * altura_interna
    inercia = (
        largura * altura**3 - largura_interna * altura_interna**3
    ) / 12.0
    # Torção de tubo fechado de parede fina (fórmula de Bredt), com a área
    # delimitada pela linha média da parede.
    area_media = (largura - espessura) * (altura - espessura)
    tau = torque / (2.0 * area_media * espessura)
    return EstadoPlanoCalculado(
        sigma_x=forca / area - momento * y / inercia,
        sigma_y=0.0,
        tau_xy=tau,
        descricao="Perfil tubular retangular sob força axial, flexão e torção",
        hipoteses=(
            "Seção fechada de parede fina e espessura constante.",
            "Torção uniforme pela fórmula de Bredt (tau = T / 2·Am·t).",
            "Cisalhamento transversal e empenamento não incluídos.",
            "Cantos vivos idealizados; concentração nos raios não incluída.",
            "Flambagem local da parede não verificada.",
        ),
    )


def tensoes_lame(
    pressao_interna_MPa: float,
    pressao_externa_MPa: float,
    raio_interno_mm: float,
    raio_externo_mm: float,
    raio_avaliado_mm: float,
    extremidades_fechadas: bool = True,
) -> tuple[float, float, float]:
    """Tensões radial, circunferencial e longitudinal de Lamé, em MPa."""
    pressao_interna = _finito("pressao_interna_MPa", pressao_interna_MPa)
    pressao_externa = _finito("pressao_externa_MPa", pressao_externa_MPa)
    raio_interno = _positivo("raio_interno_mm", raio_interno_mm)
    raio_externo = _positivo("raio_externo_mm", raio_externo_mm)
    raio = _positivo("raio_avaliado_mm", raio_avaliado_mm)
    if raio_externo <= raio_interno:
        raise ValueError("O raio externo deve ser maior que o interno.")
    if not raio_interno <= raio <= raio_externo:
        raise ValueError("O raio avaliado deve estar dentro da parede.")

    denominador = raio_externo**2 - raio_interno**2
    uniforme = (
        pressao_interna * raio_interno**2 - pressao_externa * raio_externo**2
    ) / denominador
    variavel = (
        (pressao_interna - pressao_externa)
        * raio_interno**2
        * raio_externo**2
        / denominador
    )
    sigma_radial = uniforme - variavel / raio**2
    sigma_circunferencial = uniforme + variavel / raio**2
    sigma_longitudinal = uniforme if extremidades_fechadas else 0.0
    return sigma_radial, sigma_circunferencial, sigma_longitudinal


def cilindro_parede_espessa(
    pressao_interna_MPa: float,
    pressao_externa_MPa: float,
    raio_interno_mm: float,
    raio_externo_mm: float,
    raio_avaliado_mm: float,
    extremidades_fechadas: bool = True,
    plano: str = "radial-circunferencial",
) -> EstadoPlanoCalculado:
    """Cilindro de parede espessa pela solução de Lamé.

    O estado real é triaxial. Como o restante do programa trabalha com um
    estado plano, ``plano`` escolhe quais duas das três tensões principais
    seguem adiante; a terceira fica registrada nas hipóteses.
    """
    sigma_radial, sigma_circunferencial, sigma_longitudinal = tensoes_lame(
        pressao_interna_MPa,
        pressao_externa_MPa,
        raio_interno_mm,
        raio_externo_mm,
        raio_avaliado_mm,
        extremidades_fechadas,
    )
    if plano == "radial-circunferencial":
        sigma_x = sigma_radial
        omitida = f"longitudinal (sigma_l = {sigma_longitudinal:.3f} MPa)"
        rotulo_plano = "plano radial-circunferencial"
    elif plano == "longitudinal-circunferencial":
        sigma_x = sigma_longitudinal
        omitida = f"radial (sigma_r = {sigma_radial:.3f} MPa)"
        rotulo_plano = "plano longitudinal-circunferencial"
    else:
        raise ValueError(
            "plano deve ser 'radial-circunferencial' ou "
            "'longitudinal-circunferencial'."
        )

    return EstadoPlanoCalculado(
        sigma_x=sigma_x,
        sigma_y=sigma_circunferencial,
        tau_xy=0.0,
        descricao=f"Cilindro de parede espessa (Lamé) no {rotulo_plano}",
        hipoteses=(
            "Cilindro longo, de parede espessa, material elástico linear.",
            "Pressões interna e externa uniformes; sem gradiente térmico.",
            f"O estado é triaxial: a tensão {omitida} não segue adiante "
            "neste plano — troque o plano para verificá-la.",
            "As direções radial, circunferencial e longitudinal já são "
            "principais, portanto tau_xy = 0 neste ponto.",
            "Descontinuidades, bocais e tampas não incluídos.",
        ),
    )


def indice_mola(diametro_medio_mm: float, diametro_fio_mm: float) -> float:
    """Índice de mola C = D/d; a faixa usual de projeto é 4 a 12."""
    diametro_medio = _positivo("diametro_medio_mm", diametro_medio_mm)
    diametro_fio = _positivo("diametro_fio_mm", diametro_fio_mm)
    if diametro_medio <= diametro_fio:
        raise ValueError(
            "O diâmetro médio da mola deve ser maior que o do fio."
        )
    return diametro_medio / diametro_fio


def fator_wahl(indice: float) -> float:
    """Fator de Wahl, que corrige curvatura e cisalhamento direto."""
    indice = _finito("indice", indice)
    if indice <= 1.0:
        raise ValueError("O índice de mola deve ser maior que 1.")
    return (4.0 * indice - 1.0) / (4.0 * indice - 4.0) + 0.615 / indice


def mola_helicoidal(
    forca_N: float,
    diametro_medio_mm: float,
    diametro_fio_mm: float,
    usar_fator_wahl: bool = True,
) -> EstadoPlanoCalculado:
    """Cisalhamento na fibra interna do fio de uma mola helicoidal."""
    forca = _finito("forca_N", forca_N)
    indice = indice_mola(diametro_medio_mm, diametro_fio_mm)
    diametro_medio = float(diametro_medio_mm)
    diametro_fio = float(diametro_fio_mm)
    fator = fator_wahl(indice) if usar_fator_wahl else 1.0
    tau = fator * 8.0 * forca * diametro_medio / (math.pi * diametro_fio**3)
    correcao = (
        f"fator de Wahl K = {fator:.3f}"
        if usar_fator_wahl
        else "sem fator de correção"
    )
    return EstadoPlanoCalculado(
        sigma_x=0.0,
        sigma_y=0.0,
        tau_xy=tau,
        descricao=(
            f"Mola helicoidal de espiras circulares, C = {indice:.2f}, "
            f"{correcao}"
        ),
        hipoteses=(
            "Espiras circulares de seção cheia e passo pequeno.",
            "Tensão avaliada na fibra interna da espira, onde é máxima.",
            "Flambagem da mola, atrito entre espiras e efeitos das "
            "extremidades não incluídos.",
            "Para carga variável, trate a parcela alternada em Fadiga.",
        ),
    )


def tensao_flexao_assimetrica(
    forca_axial_N: float,
    area_mm2: float,
    momento_y_Nmm: float,
    momento_z_Nmm: float,
    inercia_y_mm4: float,
    inercia_z_mm4: float,
    produto_inercia_mm4: float,
    coordenada_y_mm: float,
    coordenada_z_mm: float,
) -> float:
    """Flexão composta em eixos centroidais que não são principais.

    Vale para qualquer seção: quando o produto de inércia é nulo a expressão
    recai em sigma = N/A + My·z/Iy - Mz·y/Iz, a mesma usada nos modelos de
    seção simétrica. Com Iyz != 0 — cantoneira, por exemplo — os dois momentos
    se acoplam e a linha neutra deixa de ser paralela ao eixo do momento.
    """
    determinante = (
        inercia_y_mm4 * inercia_z_mm4 - produto_inercia_mm4**2
    )
    if determinante <= 0:
        raise ValueError(
            "Iy·Iz deve ser maior que Iyz²; verifique as propriedades da seção."
        )
    coeficiente_z = (
        momento_y_Nmm * inercia_z_mm4 + momento_z_Nmm * produto_inercia_mm4
    ) / determinante
    coeficiente_y = -(
        momento_y_Nmm * produto_inercia_mm4 + momento_z_Nmm * inercia_y_mm4
    ) / determinante
    return (
        forca_axial_N / area_mm2
        + coeficiente_y * coordenada_y_mm
        + coeficiente_z * coordenada_z_mm
    )


def angulo_linha_neutra(
    momento_y_Nmm: float,
    momento_z_Nmm: float,
    inercia_y_mm4: float,
    inercia_z_mm4: float,
    produto_inercia_mm4: float,
) -> float:
    """Inclinação da linha neutra em graus, medida a partir do eixo z.

    Em seção simétrica sob Mz puro o resultado é 0°: a linha neutra é o
    próprio eixo z. Um valor diferente de zero indica que a peça flexiona
    fora do plano de carregamento.
    """
    determinante = (
        inercia_y_mm4 * inercia_z_mm4 - produto_inercia_mm4**2
    )
    if determinante <= 0:
        raise ValueError(
            "Iy·Iz deve ser maior que Iyz²; verifique as propriedades da seção."
        )
    coeficiente_z = (
        momento_y_Nmm * inercia_z_mm4 + momento_z_Nmm * produto_inercia_mm4
    ) / determinante
    coeficiente_y = -(
        momento_y_Nmm * produto_inercia_mm4 + momento_z_Nmm * inercia_y_mm4
    ) / determinante
    if coeficiente_y == 0.0 and coeficiente_z == 0.0:
        return 0.0
    angulo = math.degrees(math.atan2(-coeficiente_z, coeficiente_y))
    # A linha neutra é uma reta, não um vetor: -100° e 80° são a mesma
    # inclinação. Normaliza para o intervalo (-90°, 90°].
    while angulo > 90.0:
        angulo -= 180.0
    while angulo <= -90.0:
        angulo += 180.0
    return angulo


def propriedades_perfil_u(
    altura_total_mm: float,
    largura_mesa_mm: float,
    espessura_mesa_mm: float,
    espessura_alma_mm: float,
) -> dict[str, float]:
    """Área, centroide e inércias de um perfil U de espessura constante.

    A alma é medida a partir da face externa (z = 0); ``z_centroide`` é a
    distância dessa face até o centroide. Os eixos geométricos já são
    principais, porque o perfil é simétrico em relação ao eixo horizontal.
    """
    altura = _positivo("altura_total_mm", altura_total_mm)
    mesa = _positivo("largura_mesa_mm", largura_mesa_mm)
    t_mesa = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    t_alma = _positivo("espessura_alma_mm", espessura_alma_mm)
    if 2.0 * t_mesa >= altura:
        raise ValueError("A soma das mesas deve ser menor que a altura total.")
    if t_alma >= mesa:
        raise ValueError("A espessura da alma deve ser menor que a mesa.")

    aba = mesa - t_alma
    area = altura * t_alma + 2.0 * aba * t_mesa
    z_centroide = (
        altura * t_alma * (t_alma / 2.0)
        + 2.0 * aba * t_mesa * ((mesa + t_alma) / 2.0)
    ) / area
    inercia_z = t_alma * altura**3 / 12.0 + 2.0 * (
        aba * t_mesa**3 / 12.0
        + aba * t_mesa * ((altura - t_mesa) / 2.0) ** 2
    )
    inercia_y = (
        altura * t_alma**3 / 12.0
        + altura * t_alma * (t_alma / 2.0 - z_centroide) ** 2
        + 2.0
        * (
            t_mesa * aba**3 / 12.0
            + aba * t_mesa * ((mesa + t_alma) / 2.0 - z_centroide) ** 2
        )
    )
    # Centro de cisalhamento pela teoria de parede fina, medido a partir da
    # linha média da alma e para o lado oposto ao das mesas.
    mesa_media = mesa - t_alma / 2.0
    altura_media = altura - t_mesa
    excentricidade = (
        3.0 * mesa_media**2 * t_mesa
        / (altura_media * t_alma + 6.0 * mesa_media * t_mesa)
    )
    return {
        "area": area,
        "z_centroide": z_centroide,
        "inercia_z": inercia_z,
        "inercia_y": inercia_y,
        "excentricidade_centro_cisalhamento": excentricidade,
    }


def secao_u_flexao(
    altura_total_mm: float,
    largura_mesa_mm: float,
    espessura_mesa_mm: float,
    espessura_alma_mm: float,
    coordenada_y_mm: float,
    forca_axial_N: float,
    momento_fletor_Nmm: float,
    forca_cortante_N: float = 0.0,
) -> EstadoPlanoCalculado:
    """Perfil U fletido em torno do eixo forte, com cortante na alma."""
    propriedades = propriedades_perfil_u(
        altura_total_mm, largura_mesa_mm, espessura_mesa_mm, espessura_alma_mm
    )
    altura = float(altura_total_mm)
    mesa = float(largura_mesa_mm)
    t_mesa = float(espessura_mesa_mm)
    t_alma = float(espessura_alma_mm)
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento = _finito("momento_fletor_Nmm", momento_fletor_Nmm)
    cortante = _finito("forca_cortante_N", forca_cortante_N)
    if abs(y) > altura / 2.0:
        raise ValueError("A coordenada y deve estar dentro da altura.")

    area = propriedades["area"]
    inercia = propriedades["inercia_z"]
    meia_alma = altura / 2.0 - t_mesa
    if abs(y) >= meia_alma:
        largura_resistente = mesa
        momento_estatico = mesa * (altura**2 / 4.0 - y**2) / 2.0
    else:
        largura_resistente = t_alma
        momento_estatico = (
            t_alma * (altura**2 / 4.0 - y**2) / 2.0
            + (mesa - t_alma) * t_mesa * (altura - t_mesa) / 2.0
        )
    tau = cortante * momento_estatico / (inercia * largura_resistente)

    return EstadoPlanoCalculado(
        sigma_x=forca / area - momento * y / inercia,
        sigma_y=0.0,
        tau_xy=tau,
        descricao="Perfil U sob força axial, flexão no eixo forte e cortante",
        hipoteses=(
            "Perfil U idealizado, de espessura constante e sem concordâncias.",
            "Flexão em torno do eixo forte, que é o eixo de simetria.",
            "Cisalhamento pela fórmula de Jourawski (tau = VQ/It).",
            "O centro de cisalhamento fica fora da alma: um cortante que não "
            "passe por ele torce o perfil, e essa torção não está incluída.",
            "Flambagem local, flambagem lateral e empenamento não incluídos.",
        ),
    )


def propriedades_cantoneira_abas_iguais(
    aba_mm: float,
    espessura_mm: float,
) -> dict[str, float]:
    """Propriedades de uma cantoneira de abas iguais, cantos vivos.

    A origem fica no canto externo, com as abas ao longo de +y e +z. Como a
    seção só é simétrica em relação à diagonal, o produto de inércia nos
    eixos paralelos às abas não é nulo — é ele que inclina a linha neutra.
    """
    aba = _positivo("aba_mm", aba_mm)
    espessura = _positivo("espessura_mm", espessura_mm)
    if espessura >= aba:
        raise ValueError("A espessura deve ser menor que o comprimento da aba.")

    area_vertical = espessura * aba
    area_horizontal = (aba - espessura) * espessura
    area = area_vertical + area_horizontal
    centroide = (
        area_vertical * (aba / 2.0) + area_horizontal * (espessura / 2.0)
    ) / area

    distancia_v_y = aba / 2.0 - centroide
    distancia_h_y = espessura / 2.0 - centroide
    distancia_v_z = espessura / 2.0 - centroide
    distancia_h_z = (aba + espessura) / 2.0 - centroide

    inercia_z = (
        espessura * aba**3 / 12.0
        + area_vertical * distancia_v_y**2
        + (aba - espessura) * espessura**3 / 12.0
        + area_horizontal * distancia_h_y**2
    )
    inercia_y = (
        aba * espessura**3 / 12.0
        + area_vertical * distancia_v_z**2
        + espessura * (aba - espessura) ** 3 / 12.0
        + area_horizontal * distancia_h_z**2
    )
    produto_inercia = (
        area_vertical * distancia_v_y * distancia_v_z
        + area_horizontal * distancia_h_y * distancia_h_z
    )
    media = (inercia_y + inercia_z) / 2.0
    amplitude = math.hypot((inercia_y - inercia_z) / 2.0, produto_inercia)
    return {
        "area": area,
        "centroide": centroide,
        "inercia_y": inercia_y,
        "inercia_z": inercia_z,
        "produto_inercia": produto_inercia,
        "inercia_maxima": media + amplitude,
        "inercia_minima": media - amplitude,
    }


def cantoneira_abas_iguais(
    aba_mm: float,
    espessura_mm: float,
    coordenada_y_mm: float,
    coordenada_z_mm: float,
    forca_axial_N: float,
    momento_y_Nmm: float,
    momento_z_Nmm: float,
) -> EstadoPlanoCalculado:
    """Cantoneira de abas iguais sob força axial e flexão nos eixos das abas."""
    propriedades = propriedades_cantoneira_abas_iguais(aba_mm, espessura_mm)
    aba = float(aba_mm)
    centroide = propriedades["centroide"]
    y = _finito("coordenada_y_mm", coordenada_y_mm)
    z = _finito("coordenada_z_mm", coordenada_z_mm)
    forca = _finito("forca_axial_N", forca_axial_N)
    momento_y = _finito("momento_y_Nmm", momento_y_Nmm)
    momento_z = _finito("momento_z_Nmm", momento_z_Nmm)
    if not -centroide <= y <= aba - centroide:
        raise ValueError("A coordenada y deve estar dentro da seção.")
    if not -centroide <= z <= aba - centroide:
        raise ValueError("A coordenada z deve estar dentro da seção.")

    sigma = tensao_flexao_assimetrica(
        forca,
        propriedades["area"],
        momento_y,
        momento_z,
        propriedades["inercia_y"],
        propriedades["inercia_z"],
        propriedades["produto_inercia"],
        y,
        z,
    )
    inclinacao = angulo_linha_neutra(
        momento_y,
        momento_z,
        propriedades["inercia_y"],
        propriedades["inercia_z"],
        propriedades["produto_inercia"],
    )
    return EstadoPlanoCalculado(
        sigma_x=sigma,
        sigma_y=0.0,
        tau_xy=0.0,
        descricao=(
            "Cantoneira de abas iguais sob força axial e flexão, com linha "
            f"neutra a {inclinacao:.1f}° do eixo z"
        ),
        hipoteses=(
            "Cantoneira de abas iguais idealizada, com cantos vivos: sem o "
            "raio de concordância, a área fica alguns por cento abaixo da "
            "tabelada e a inércia, um pouco acima.",
            "Eixos y e z paralelos às abas — eles NÃO são principais, então "
            "um momento isolado já produz flexão oblíqua.",
            "Cisalhamento e torção não incluídos; o centro de cisalhamento "
            "fica no encontro das linhas médias das abas, fora do centroide.",
            "Flambagem local da aba e flambagem por flexo-torção, típicas de "
            "cantoneira comprimida, não são verificadas aqui.",
        ),
    )
