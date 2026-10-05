"""Cálculos preliminares para projeto de juntas parafusadas métricas.

Unidades internas:
- força: N
- comprimento: mm
- momento/torque: N·mm
- tensão: MPa (N/mm²)

O módulo trata uma junta pré-carregada com parafusos igualmente espaçados
em um círculo ou em qualquer arranjo de coordenadas (grade retangular, por
exemplo). Os resultados não substituem normas de produto, testes de
torque-pré-carga, análise de contato ou qualificação da junta.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core.verificacao import Verificacao


@dataclass(frozen=True)
class RoscaMetrica:
    designacao: str
    diametro_mm: float
    passo_mm: float
    area_tracao_mm2: float


@dataclass(frozen=True)
class ClasseParafuso:
    classe: str
    resistencia_prova_MPa: float
    escoamento_min_MPa: float
    ruptura_min_MPa: float
    observacao: str = ""


@dataclass(frozen=True)
class DistribuicaoGrupo:
    forcas_axiais_N: tuple[float, ...]
    forcas_cisalhantes_N: tuple[float, ...]
    maior_tracao_N: float
    maior_cisalhamento_N: float
    indice_tracao_critico: int
    indice_cisalhamento_critico: int


@dataclass(frozen=True)
class ResultadoJunta:
    carga_prova_N: float
    pre_carga_nominal_N: float
    pre_carga_minima_N: float
    pre_carga_maxima_N: float
    torque_nominal_Nm: float
    carga_maxima_parafuso_N: float
    tensao_axial_MPa: float
    tensao_cisalhante_MPa: float
    tensao_von_mises_MPa: float
    fator_prova: float
    fator_escoamento_vm: float
    fator_ruptura_tracao: float
    fator_separacao: float
    forca_aperto_residual_total_N: float
    fator_deslizamento: float
    tensao_esmagamento_MPa: float
    fator_esmagamento: float
    fator_rasgamento_borda: float
    distribuicao: DistribuicaoGrupo


@dataclass(frozen=True)
class ResultadoFadigaParafuso:
    forca_minima_parafuso_N: float
    forca_maxima_parafuso_N: float
    tensao_alternada_MPa: float
    tensao_media_MPa: float
    fator_goodman: float
    fator_escoamento_maximo: float


# Áreas nominais segundo tabelas de rosca ISO métrica (valores arredondados).
_ROSCAS = (
    ("M3", 3.0, 0.5, 5.03),
    ("M4", 4.0, 0.7, 8.78),
    ("M5", 5.0, 0.8, 14.2),
    ("M6", 6.0, 1.0, 20.1),
    ("M8", 8.0, 1.25, 36.6),
    ("M8 × 1", 8.0, 1.0, 39.2),
    ("M10", 10.0, 1.5, 58.0),
    ("M10 × 1,25", 10.0, 1.25, 61.2),
    ("M10 × 1", 10.0, 1.0, 64.5),
    ("M12", 12.0, 1.75, 84.3),
    ("M12 × 1,5", 12.0, 1.5, 88.1),
    ("M12 × 1,25", 12.0, 1.25, 92.1),
    ("M14", 14.0, 2.0, 115.0),
    ("M14 × 1,5", 14.0, 1.5, 125.0),
    ("M16", 16.0, 2.0, 157.0),
    ("M16 × 1,5", 16.0, 1.5, 167.0),
    ("M18", 18.0, 2.5, 192.0),
    ("M18 × 1,5", 18.0, 1.5, 216.0),
    ("M20", 20.0, 2.5, 245.0),
    ("M20 × 1,5", 20.0, 1.5, 272.0),
    ("M22", 22.0, 2.5, 303.0),
    ("M22 × 1,5", 22.0, 1.5, 333.0),
    ("M24", 24.0, 3.0, 353.0),
    ("M24 × 2", 24.0, 2.0, 384.0),
    ("M27", 27.0, 3.0, 459.0),
    ("M27 × 2", 27.0, 2.0, 496.0),
    ("M30", 30.0, 3.5, 561.0),
    ("M30 × 2", 30.0, 2.0, 621.0),
    ("M33", 33.0, 3.5, 694.0),
    ("M33 × 2", 33.0, 2.0, 761.0),
    ("M36", 36.0, 4.0, 817.0),
    ("M36 × 3", 36.0, 3.0, 865.0),
)

ROSCAS_METRICAS = {item[0]: RoscaMetrica(*item) for item in _ROSCAS}

CLASSES_PARAFUSO = {
    "4.6": ClasseParafuso("4.6", 225.0, 240.0, 400.0),
    "4.8": ClasseParafuso(
        "4.8",
        310.0,
        340.0,
        420.0,
        "Escoamento representado por tensão a 0,0048d.",
    ),
    "5.6": ClasseParafuso("5.6", 280.0, 300.0, 500.0),
    "5.8": ClasseParafuso(
        "5.8",
        380.0,
        420.0,
        520.0,
        "Escoamento representado por tensão a 0,0048d.",
    ),
    "6.8": ClasseParafuso(
        "6.8",
        440.0,
        480.0,
        600.0,
        "Escoamento representado por tensão a 0,0048d.",
    ),
    "8.8": ClasseParafuso("8.8", 580.0, 640.0, 800.0),
    "9.8": ClasseParafuso(
        "9.8",
        650.0,
        720.0,
        900.0,
        "Aplicação da classe limitada a diâmetros até 16 mm nesta base.",
    ),
    "10.9": ClasseParafuso("10.9", 830.0, 940.0, 1040.0),
    "12.9": ClasseParafuso("12.9", 970.0, 1100.0, 1220.0),
}


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser finito.")
    return valor


def _positivo(nome: str, valor: float) -> float:
    valor = _finito(nome, valor)
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = _finito(nome, valor)
    if valor < 0:
        raise ValueError(f"{nome} não pode ser negativo.")
    return valor


def _fator(capacidade: float, demanda: float) -> float:
    if demanda <= 0:
        return math.inf
    return max(0.0, capacidade) / demanda


def obter_rosca(designacao: str) -> RoscaMetrica:
    try:
        return ROSCAS_METRICAS[designacao]
    except KeyError as exc:
        raise ValueError(f"Rosca métrica desconhecida: {designacao}.") from exc


def obter_classe(classe: str, diametro_mm: float) -> ClasseParafuso:
    try:
        dados = CLASSES_PARAFUSO[classe]
    except KeyError as exc:
        raise ValueError(f"Classe de parafuso desconhecida: {classe}.") from exc
    diametro = _positivo("diametro_mm", diametro_mm)
    if classe == "9.8" and diametro > 16.0:
        raise ValueError("A classe 9.8 está limitada a d ≤ 16 mm nesta base.")
    if classe == "8.8" and diametro > 16.0:
        return ClasseParafuso(
            "8.8",
            600.0,
            660.0,
            830.0,
            "Valores mínimos aplicáveis a d > 16 mm.",
        )
    return dados


def area_tensao_aproximada(diametro_mm: float, passo_mm: float) -> float:
    """Aproximação da área resistente de rosca métrica ISO."""
    diametro = _positivo("diametro_mm", diametro_mm)
    passo = _positivo("passo_mm", passo_mm)
    diametro_resistente = diametro - 0.9382 * passo
    if diametro_resistente <= 0:
        raise ValueError("Passo incompatível com o diâmetro.")
    return math.pi * diametro_resistente**2 / 4.0


def torque_para_pre_carga(
    pre_carga_N: float,
    diametro_mm: float,
    fator_porcar_K: float,
) -> float:
    """Estimativa T = K F d, com resultado em N·m."""
    pre_carga = _nao_negativo("pre_carga_N", pre_carga_N)
    diametro = _positivo("diametro_mm", diametro_mm)
    fator = _positivo("fator_porcar_K", fator_porcar_K)
    return fator * pre_carga * diametro / 1_000.0


def coordenadas_circulares(
    numero_parafusos: int, raio_grupo_mm: float
) -> tuple[tuple[float, float], ...]:
    """Coordenadas (x, y) de parafusos igualmente espaçados num círculo centrado na origem."""
    return tuple(
        (
            raio_grupo_mm * math.cos(2.0 * math.pi * i / numero_parafusos),
            raio_grupo_mm * math.sin(2.0 * math.pi * i / numero_parafusos),
        )
        for i in range(numero_parafusos)
    )


def distribuir_cargas_grupo(
    coordenadas_mm: Sequence[tuple[float, float]],
    carga_axial_N: float = 0.0,
    carga_cortante_N: float = 0.0,
    momento_tombamento_Nmm: float = 0.0,
    torque_grupo_Nmm: float = 0.0,
) -> DistribuicaoGrupo:
    """Distribui cargas em um grupo de parafusos de coordenadas quaisquer.

    As coordenadas podem estar em qualquer origem: as forças são medidas a partir
    do centroide. A carga cortante atua no eixo x. O momento de tombamento gera
    tração proporcional à coordenada x (M·x/Σx²). O torque gera cisalhamento
    perpendicular ao raio de cada parafuso (T·r/Σr²).
    """
    if not coordenadas_mm:
        raise ValueError("O grupo precisa de ao menos um parafuso.")
    numero = len(coordenadas_mm)
    axial = _finito("carga_axial_N", carga_axial_N)
    cortante = _finito("carga_cortante_N", carga_cortante_N)
    momento = _finito("momento_tombamento_Nmm", momento_tombamento_Nmm)
    torque = _finito("torque_grupo_Nmm", torque_grupo_Nmm)
    for x, y in coordenadas_mm:
        _finito("coordenada x", x)
        _finito("coordenada y", y)

    xc = sum(x for x, _ in coordenadas_mm) / numero
    yc = sum(y for _, y in coordenadas_mm) / numero
    relativas = tuple((x - xc, y - yc) for x, y in coordenadas_mm)
    soma_x2 = sum(x * x for x, _ in relativas)
    soma_r2 = sum(x * x + y * y for x, y in relativas)
    if momento != 0 and soma_x2 <= 0:
        raise ValueError("O padrão informado não resiste ao momento aplicado.")
    if torque != 0 and soma_r2 <= 0:
        raise ValueError("O padrão informado não resiste ao torque aplicado.")

    axiais = tuple(
        axial / numero + (momento * x / soma_x2 if momento else 0.0) for x, _ in relativas
    )

    cisalhantes = []
    for x, y in relativas:
        direto_x = cortante / numero
        torsao_x = -torque * y / soma_r2 if torque else 0.0
        torsao_y = torque * x / soma_r2 if torque else 0.0
        cisalhantes.append(math.hypot(direto_x + torsao_x, torsao_y))

    indice_axial = max(range(numero), key=lambda i: axiais[i])
    indice_cisalhamento = max(range(numero), key=lambda i: cisalhantes[i])
    return DistribuicaoGrupo(
        forcas_axiais_N=axiais,
        forcas_cisalhantes_N=tuple(cisalhantes),
        maior_tracao_N=max(0.0, axiais[indice_axial]),
        maior_cisalhamento_N=cisalhantes[indice_cisalhamento],
        indice_tracao_critico=indice_axial,
        indice_cisalhamento_critico=indice_cisalhamento,
    )


def distribuir_cargas_grupo_circular(
    numero_parafusos: int,
    raio_grupo_mm: float,
    carga_axial_N: float = 0.0,
    carga_cortante_N: float = 0.0,
    momento_tombamento_Nmm: float = 0.0,
    torque_grupo_Nmm: float = 0.0,
) -> DistribuicaoGrupo:
    """Distribui cargas em parafusos igualmente espaçados num círculo.

    Caso particular de :func:`distribuir_cargas_grupo`: a carga cortante atua no
    eixo x, o momento de tombamento gera tração proporcional à coordenada x e o
    torque gera cisalhamento tangencial.
    """
    if int(numero_parafusos) != numero_parafusos or numero_parafusos < 1:
        raise ValueError("numero_parafusos deve ser um inteiro positivo.")
    numero = int(numero_parafusos)
    raio = _nao_negativo("raio_grupo_mm", raio_grupo_mm)
    momento = _finito("momento_tombamento_Nmm", momento_tombamento_Nmm)
    torque = _finito("torque_grupo_Nmm", torque_grupo_Nmm)
    if raio == 0 and (momento != 0 or torque != 0):
        raise ValueError("O raio do grupo deve ser positivo com momento ou torque.")
    return distribuir_cargas_grupo(
        coordenadas_circulares(numero, raio),
        carga_axial_N,
        carga_cortante_N,
        momento,
        torque,
    )


def avaliar_junta(
    rosca: RoscaMetrica,
    classe: ClasseParafuso,
    numero_parafusos: int,
    raio_grupo_mm: float,
    carga_axial_N: float,
    carga_cortante_N: float,
    momento_tombamento_Nmm: float,
    torque_grupo_Nmm: float,
    fracao_pre_carga_prova: float,
    fator_porcar_K: float,
    incerteza_pre_carga: float,
    perda_pre_carga: float,
    constante_rigidez_C: float,
    rosca_no_plano_corte: bool,
    coeficiente_atrito_junta: float,
    numero_interfaces_atrito: int,
    espessura_chapa_mm: float,
    diametro_furo_mm: float,
    distancia_centro_borda_mm: float,
    limite_esmagamento_MPa: float,
    escoamento_chapa_MPa: float,
    coordenadas_mm: Sequence[tuple[float, float]] | None = None,
) -> ResultadoJunta:
    """Avalia resistência básica do parafuso, aperto e modos da chapa.

    Com ``coordenadas_mm`` o arranjo é livre (grade retangular, por exemplo) e
    ``numero_parafusos`` precisa coincidir com a quantidade de pontos; sem elas,
    vale o círculo de raio ``raio_grupo_mm``.
    """
    numero = int(numero_parafusos)
    if numero != numero_parafusos or numero < 1:
        raise ValueError("numero_parafusos deve ser um inteiro positivo.")
    fracao = _finito("fracao_pre_carga_prova", fracao_pre_carga_prova)
    incerteza = _finito("incerteza_pre_carga", incerteza_pre_carga)
    perda = _finito("perda_pre_carga", perda_pre_carga)
    constante = _finito("constante_rigidez_C", constante_rigidez_C)
    if not 0 < fracao <= 1:
        raise ValueError("A fração de pré-carga deve estar entre 0 e 1.")
    if not 0 <= incerteza < 1:
        raise ValueError("A incerteza de pré-carga deve estar entre 0 e 1.")
    if not 0 <= perda < 1:
        raise ValueError("A perda de pré-carga deve estar entre 0 e 1.")
    if not 0 <= constante <= 1:
        raise ValueError("A constante de rigidez C deve estar entre 0 e 1.")
    atrito = _nao_negativo("coeficiente_atrito_junta", coeficiente_atrito_junta)
    if int(numero_interfaces_atrito) != numero_interfaces_atrito:
        raise ValueError("numero_interfaces_atrito deve ser inteiro.")
    interfaces = int(numero_interfaces_atrito)
    if interfaces < 1:
        raise ValueError("Deve existir pelo menos uma interface de atrito.")
    espessura = _positivo("espessura_chapa_mm", espessura_chapa_mm)
    diametro_furo = _positivo("diametro_furo_mm", diametro_furo_mm)
    distancia_borda = _positivo("distancia_centro_borda_mm", distancia_centro_borda_mm)
    if diametro_furo < rosca.diametro_mm:
        raise ValueError("O diâmetro do furo não pode ser menor que o parafuso.")
    ligamento = distancia_borda - diametro_furo / 2.0
    if ligamento <= 0:
        raise ValueError("A borda do furo ultrapassa a borda da chapa.")
    limite_esmagamento = _positivo("limite_esmagamento_MPa", limite_esmagamento_MPa)
    escoamento_chapa = _positivo("escoamento_chapa_MPa", escoamento_chapa_MPa)

    if coordenadas_mm is None:
        distribuicao = distribuir_cargas_grupo_circular(
            numero,
            raio_grupo_mm,
            carga_axial_N,
            carga_cortante_N,
            momento_tombamento_Nmm,
            torque_grupo_Nmm,
        )
        raios_parafusos = (raio_grupo_mm,) * numero
    else:
        if len(coordenadas_mm) != numero:
            raise ValueError("numero_parafusos deve coincidir com o número de coordenadas.")
        distribuicao = distribuir_cargas_grupo(
            coordenadas_mm,
            carga_axial_N,
            carga_cortante_N,
            momento_tombamento_Nmm,
            torque_grupo_Nmm,
        )
        xc = sum(x for x, _ in coordenadas_mm) / numero
        yc = sum(y for _, y in coordenadas_mm) / numero
        raios_parafusos = tuple(math.hypot(x - xc, y - yc) for x, y in coordenadas_mm)

    carga_prova = classe.resistencia_prova_MPa * rosca.area_tracao_mm2
    pre_carga_nominal = fracao * carga_prova
    pre_carga_minima = pre_carga_nominal * (1.0 - incerteza) * (1.0 - perda)
    pre_carga_maxima = pre_carga_nominal * (1.0 + incerteza)
    torque_nominal = torque_para_pre_carga(pre_carga_nominal, rosca.diametro_mm, fator_porcar_K)

    incremento_maximo = constante * distribuicao.maior_tracao_N
    carga_maxima = pre_carga_maxima + incremento_maximo
    sigma_axial = carga_maxima / rosca.area_tracao_mm2
    area_cisalhamento = (
        rosca.area_tracao_mm2 if rosca_no_plano_corte else math.pi * rosca.diametro_mm**2 / 4.0
    )
    tau = distribuicao.maior_cisalhamento_N / area_cisalhamento
    sigma_vm = math.sqrt(sigma_axial**2 + 3.0 * tau**2)

    demanda_separacao = (1.0 - constante) * distribuicao.maior_tracao_N
    fator_separacao = _fator(pre_carga_minima, demanda_separacao)

    apertos_residuais = tuple(
        max(0.0, pre_carga_minima - (1.0 - constante) * max(0.0, p))
        for p in distribuicao.forcas_axiais_N
    )
    aperto_total = sum(apertos_residuais)
    capacidade_atrito_forca = atrito * interfaces * aperto_total
    capacidade_atrito_torque = (
        atrito
        * interfaces
        * sum(
            aperto * raio for aperto, raio in zip(apertos_residuais, raios_parafusos, strict=True)
        )
    )
    utilizacao_deslizamento = 0.0
    if abs(carga_cortante_N) > 0:
        utilizacao_deslizamento += (
            math.inf
            if capacidade_atrito_forca <= 0
            else abs(carga_cortante_N) / capacidade_atrito_forca
        )
    if abs(torque_grupo_Nmm) > 0:
        utilizacao_deslizamento += (
            math.inf
            if capacidade_atrito_torque <= 0
            else abs(torque_grupo_Nmm) / capacidade_atrito_torque
        )
    fator_deslizamento = math.inf if utilizacao_deslizamento == 0 else 1.0 / utilizacao_deslizamento

    tensao_esmagamento = distribuicao.maior_cisalhamento_N / (rosca.diametro_mm * espessura)
    capacidade_rasgamento = 2.0 * ligamento * espessura * escoamento_chapa / math.sqrt(3.0)

    return ResultadoJunta(
        carga_prova_N=carga_prova,
        pre_carga_nominal_N=pre_carga_nominal,
        pre_carga_minima_N=pre_carga_minima,
        pre_carga_maxima_N=pre_carga_maxima,
        torque_nominal_Nm=torque_nominal,
        carga_maxima_parafuso_N=carga_maxima,
        tensao_axial_MPa=sigma_axial,
        tensao_cisalhante_MPa=tau,
        tensao_von_mises_MPa=sigma_vm,
        fator_prova=_fator(carga_prova, carga_maxima),
        fator_escoamento_vm=_fator(classe.escoamento_min_MPa, sigma_vm),
        fator_ruptura_tracao=_fator(
            classe.ruptura_min_MPa * rosca.area_tracao_mm2,
            carga_maxima,
        ),
        fator_separacao=fator_separacao,
        forca_aperto_residual_total_N=aperto_total,
        fator_deslizamento=fator_deslizamento,
        tensao_esmagamento_MPa=tensao_esmagamento,
        fator_esmagamento=_fator(limite_esmagamento, tensao_esmagamento),
        fator_rasgamento_borda=_fator(capacidade_rasgamento, distribuicao.maior_cisalhamento_N),
        distribuicao=distribuicao,
    )


def avaliar_fadiga_axial(
    rosca: RoscaMetrica,
    classe: ClasseParafuso,
    pre_carga_nominal_N: float,
    constante_rigidez_C: float,
    carga_externa_minima_por_parafuso_N: float,
    carga_externa_maxima_por_parafuso_N: float,
    fator_concentracao_fadiga_Kf: float,
    limite_fadiga_parafuso_MPa: float,
) -> ResultadoFadigaParafuso:
    """Goodman modificado preliminar para variação axial antes da separação."""
    pre_carga = _nao_negativo("pre_carga_nominal_N", pre_carga_nominal_N)
    constante = _finito("constante_rigidez_C", constante_rigidez_C)
    if not 0 <= constante <= 1:
        raise ValueError("A constante de rigidez C deve estar entre 0 e 1.")
    p_min = _finito(
        "carga_externa_minima_por_parafuso_N",
        carga_externa_minima_por_parafuso_N,
    )
    p_max = _finito(
        "carga_externa_maxima_por_parafuso_N",
        carga_externa_maxima_por_parafuso_N,
    )
    if p_max < p_min:
        raise ValueError("A carga externa máxima deve ser maior ou igual à mínima.")
    kf = _positivo("fator_concentracao_fadiga_Kf", fator_concentracao_fadiga_Kf)
    se = _positivo("limite_fadiga_parafuso_MPa", limite_fadiga_parafuso_MPa)

    forca_min = pre_carga + constante * p_min
    forca_max = pre_carga + constante * p_max
    tensao_min = forca_min / rosca.area_tracao_mm2
    tensao_max = forca_max / rosca.area_tracao_mm2
    tensao_alternada = kf * abs(tensao_max - tensao_min) / 2.0
    tensao_media = max(0.0, (tensao_max + tensao_min) / 2.0)
    inverso_goodman = tensao_alternada / se + tensao_media / classe.ruptura_min_MPa
    fator_goodman = math.inf if inverso_goodman == 0 else 1.0 / inverso_goodman
    tensao_maxima_local = tensao_media + tensao_alternada

    return ResultadoFadigaParafuso(
        forca_minima_parafuso_N=forca_min,
        forca_maxima_parafuso_N=forca_max,
        tensao_alternada_MPa=tensao_alternada,
        tensao_media_MPa=tensao_media,
        fator_goodman=fator_goodman,
        fator_escoamento_maximo=_fator(classe.escoamento_min_MPa, tensao_maxima_local),
    )


def _linha_diagnostico(
    nome: str,
    solicitante: float,
    resistente: float,
    unidade: str,
    referencia: str,
    formula: str,
    fator: float,
    fator_minimo: float,
) -> Verificacao:
    """Linha do diagnóstico: o status segue o fator n e a meta, não só n ≥ 1."""
    if math.isinf(fator):
        return Verificacao(
            nome, None, None, unidade, referencia, f"{formula} — sem solicitação neste modo.", "N/A"
        )
    linha = Verificacao(
        nome, solicitante, resistente, unidade, referencia, f"{formula}; n = {fator:.2f}"
    )
    if fator < 1.0:
        linha.status = "NÃO OK"
    elif fator < fator_minimo:
        linha.status = "ALERTA"
        linha.formula += f" (abaixo da meta n = {fator_minimo:.2f})"
    else:
        linha.status = "OK"
    return linha


def diagnostico_junta(
    resultado: ResultadoJunta,
    rosca: RoscaMetrica,
    classe: ClasseParafuso,
    constante_rigidez_C: float,
    fator_minimo: float,
    fadiga: ResultadoFadigaParafuso | None = None,
) -> list[Verificacao]:
    """Diagnóstico de cada modo de falha com solicitante, resistente, status, fórmula e fonte.

    Substitui a tabela "Critério / Fator / Resultado", que perdia as grandezas. Forças em kN
    e tensões em MPa; ``Aproveitamento`` = solicitante/resistente = 1/n. Para o
    deslizamento e a fadiga, que combinam parcelas, o solicitante é a utilização (1/n) e o
    resistente é 1,0.
    """
    kN = 1_000.0
    carga_max = resultado.carga_maxima_parafuso_N
    cisalhamento = resultado.distribuicao.maior_cisalhamento_N
    tracao_externa = resultado.distribuicao.maior_tracao_N
    linhas = [
        _linha_diagnostico(
            "Carga de prova do parafuso",
            carga_max / kN,
            resultado.carga_prova_N / kN,
            "kN",
            "ISO 898-1 (carga de prova S_p·A_t)",
            "F_máx = F_i,máx + C·P_b ≤ S_p·A_t",
            resultado.fator_prova,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Escoamento combinado (von Mises)",
            resultado.tensao_von_mises_MPa,
            classe.escoamento_min_MPa,
            "MPa",
            "NASA-STD-5020 / ISO 898-1",
            "σ_vm = √(σ² + 3τ²) ≤ S_y",
            resultado.fator_escoamento_vm,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Ruptura em tração",
            carga_max / kN,
            classe.ruptura_min_MPa * rosca.area_tracao_mm2 / kN,
            "kN",
            "ISO 898-1 (R_m·A_t)",
            "F_máx ≤ S_ut·A_t",
            resultado.fator_ruptura_tracao,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Separação da junta",
            (1.0 - constante_rigidez_C) * tracao_externa / kN,
            resultado.pre_carga_minima_N / kN,
            "kN",
            "NASA Fastener Design Manual / NASA-STD-5020",
            "(1 − C)·P_b ≤ F_i,mín",
            resultado.fator_separacao,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Deslizamento por atrito",
            0.0 if math.isinf(resultado.fator_deslizamento) else 1.0 / resultado.fator_deslizamento,
            1.0,
            "adim.",
            "NASA Fastener Design Manual",
            "V/(μ·n·ΣF_res) + T/(μ·n·ΣF_res·r) ≤ 1 (aperto residual após a carga externa)",
            resultado.fator_deslizamento,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Esmagamento da chapa",
            resultado.tensao_esmagamento_MPa,
            (
                math.inf
                if math.isinf(resultado.fator_esmagamento)
                else resultado.tensao_esmagamento_MPa * resultado.fator_esmagamento
            ),
            "MPa",
            "NASA Fastener Design Manual",
            "σ_b = F_cis/(d·t) ≤ limite adotado (parte mecânica; a norma estrutural usa f_u)",
            resultado.fator_esmagamento,
            fator_minimo,
        ),
        _linha_diagnostico(
            "Rasgamento até a borda",
            cisalhamento / kN,
            (
                math.inf
                if math.isinf(resultado.fator_rasgamento_borda)
                else cisalhamento * resultado.fator_rasgamento_borda / kN
            ),
            "kN",
            "NASA Fastener Design Manual",
            "F_cis ≤ 2·ℓ·t·S_y/√3 (ℓ = e − d_h/2)",
            resultado.fator_rasgamento_borda,
            fator_minimo,
        ),
    ]
    if fadiga is not None:
        linhas.append(
            _linha_diagnostico(
                "Fadiga axial (Goodman)",
                0.0 if math.isinf(fadiga.fator_goodman) else 1.0 / fadiga.fator_goodman,
                1.0,
                "adim.",
                "Goodman modificado (preliminar)",
                "σ_a/S_e + σ_m/S_ut ≤ 1",
                fadiga.fator_goodman,
                fator_minimo,
            )
        )
    return linhas
