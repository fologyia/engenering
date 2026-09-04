"""Cálculos de resistência à fadiga em unidades SI (MPa, mm e °C)."""
import math


MATERIAIS_SE_LINHA = {"aco", "ferro", "aluminio", "cobre"}

COEFICIENTES_SUPERFICIE = {
    "retificado": (1.58, -0.085),
    "usinado_ou_estirado_a_frio": (4.51, -0.265),
    "laminado_a_quente": (57.7, -0.718),
    "forjado": (272.0, -0.995),
}

FATORES_CONFIABILIDADE = {
    50: 1.000,
    90: 0.897,
    95: 0.868,
    99: 0.814,
    99.9: 0.753,
    99.99: 0.702,
    99.999: 0.659,
    99.9999: 0.620,
}

_N1_PADRAO = 1.0e3
MODELOS_MARIN = {"norton", "shigley"}
TIPOS_CARGA = {"flexao", "axial", "torcao", "torcao_von_mises"}
NORTON_TEMPERATURA_INICIO_F = 450.0
NORTON_TEMPERATURA_MAX_F = 550.0
NORTON_TEMPERATURA_INICIO_C = (NORTON_TEMPERATURA_INICIO_F - 32.0) / 1.8
NORTON_TEMPERATURA_MAX_C = (NORTON_TEMPERATURA_MAX_F - 32.0) / 1.8
ZERO_ABSOLUTO_C = -273.15
ZERO_ABSOLUTO_F = -459.67
UNIDADES_TEMPERATURA = {"c", "f"}


def celsius_para_fahrenheit(temperatura_celsius: float) -> float:
    """Converte uma temperatura em graus Celsius para graus Fahrenheit."""
    if not math.isfinite(temperatura_celsius):
        raise ValueError("temperatura_celsius deve ser um número finito.")
    return 1.8 * temperatura_celsius + 32.0

def fahrenheit_para_celsius(temperatura_fahrenheit: float) -> float:
    """Converte uma temperatura em graus Fahrenheit para graus Celsius."""
    if not math.isfinite(temperatura_fahrenheit):
        raise ValueError("temperatura_fahrenheit deve ser um numero finito.")
    return (temperatura_fahrenheit - 32.0) / 1.8


def temperatura_para_celsius(valor: float, unidade: str) -> float:
    """Normaliza uma temperatura informada em C ou F para graus Celsius."""
    if not math.isfinite(valor):
        raise ValueError("A temperatura deve ser um numero finito.")
    unidade_normalizada = unidade.strip().lower().replace(chr(176), "")
    if unidade_normalizada not in UNIDADES_TEMPERATURA:
        raise ValueError("Unidade de temperatura invalida. Use C ou F.")
    if unidade_normalizada == "c":
        return valor
    return fahrenheit_para_celsius(valor)


def limites_temperatura_entrada(
    modelo: str,
    unidade: str,
) -> tuple[float, float]:
    """Faixa permitida no campo de temperatura para o modelo e a unidade."""
    modelo = _validar_modelo(modelo)
    unidade_normalizada = unidade.strip().lower().replace(chr(176), "")
    if unidade_normalizada not in UNIDADES_TEMPERATURA:
        raise ValueError("Unidade de temperatura invalida. Use C ou F.")

    if modelo == "norton":
        limites_c = (ZERO_ABSOLUTO_C, NORTON_TEMPERATURA_MAX_C)
    else:
        limites_c = (20.0, 540.0)

    if unidade_normalizada == "c":
        return limites_c
    return tuple(celsius_para_fahrenheit(valor) for valor in limites_c)


def fator_temperatura_na_unidade(
    temperatura: float,
    unidade: str,
    modelo: str = "norton",
) -> float:
    """Calcula o fator apos converter explicitamente C ou F para Celsius."""
    return fator_temperatura(
        temperatura_para_celsius(temperatura, unidade),
        modelo,
    )

FONTES_MARIN = {
    "norton": "Norton, Projeto de Máquinas, 4ª ed., cap. 6",
    "shigley": "Shigley, Elementos de Máquinas, 8ª ed., cap. 6",
}


def _validar_modelo(modelo: str) -> str:
    modelo = modelo.lower()
    if modelo not in MODELOS_MARIN:
        raise ValueError(f"Modelo de Marin não suportado: {modelo}")
    return modelo


def _validar_positivo(nome: str, valor: float) -> None:
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")


def se_linha(Sut_MPa: float, material: str = "aco") -> tuple[float, bool]:
    """
    Calcula Se' ou Sf' de referência.

    Retorna (valor_MPa, e_vida_infinita). Para alumínio e cobre, o valor
    representa a resistência em 5e8 ciclos, e não um limite de vida infinita.
    """
    _validar_positivo("Sut_MPa", Sut_MPa)
    material = material.lower()
    if material not in MATERIAIS_SE_LINHA:
        raise ValueError(
            f"Material '{material}' não suportado: {sorted(MATERIAIS_SE_LINHA)}"
        )
    if material == "aco":
        return (0.5 * Sut_MPa if Sut_MPa < 1400 else 700.0), True
    if material == "ferro":
        return (0.4 * Sut_MPa if Sut_MPa < 400 else 160.0), True
    if material == "aluminio":
        return (0.4 * Sut_MPa if Sut_MPa < 330 else 130.0), False
    return (0.4 * Sut_MPa if Sut_MPa < 280 else 100.0), False


def fator_carregamento(tipo: str = "flexao", modelo: str = "norton") -> float:
    """Fator de carregamento segundo Norton ou Shigley."""
    modelo = _validar_modelo(modelo)
    valores = {
        "norton": {
            "flexao": 1.0,
            "axial": 0.70,
            "torcao": 0.577,
            "torcao_von_mises": 1.0,
        },
        "shigley": {
            "flexao": 1.0,
            "axial": 0.85,
            "torcao": 0.59,
            "torcao_von_mises": 1.0,
        },
    }
    tipo = tipo.lower()
    if tipo not in valores[modelo]:
        raise ValueError(f"Tipo de carregamento não suportado: {tipo}")
    return valores[modelo][tipo]


def fator_tamanho(
    d_mm: float,
    tipo_carga: str = "flexao",
    modelo: str = "norton",
) -> float:
    """Fator de tamanho para diâmetro equivalente em milímetros."""
    _validar_positivo("d_mm", d_mm)
    modelo = _validar_modelo(modelo)
    tipo_carga = tipo_carga.lower()
    if tipo_carga not in TIPOS_CARGA:
        raise ValueError(f"Tipo de carregamento não suportado: {tipo_carga}")
    if tipo_carga == "axial":
        return 1.0

    if modelo == "norton":
        if d_mm <= 8:
            return 1.0
        if d_mm <= 250:
            return 1.189 * d_mm ** (-0.097)
        return 0.6

    if d_mm < 2.79:
        raise ValueError(
            "d_mm fora da faixa da correlacao de Shigley (2,79 a 254 mm)."
        )
    if d_mm <= 51:
        return 1.24 * d_mm ** (-0.107)
    if d_mm <= 254:
        return 1.51 * d_mm ** (-0.157)
    raise ValueError("d_mm fora da faixa da correlação de Shigley (até 254 mm).")


def fator_superficie(
    Sut_MPa: float,
    acabamento: str,
    material: str | None = None,
) -> float:
    """Fator de superfície, com Sut em MPa."""
    _validar_positivo("Sut_MPa", Sut_MPa)
    if material and material.lower() == "ferro":
        return 1.0
    acabamento = acabamento.lower()
    if acabamento not in COEFICIENTES_SUPERFICIE:
        raise ValueError(f"Acabamento não suportado: {acabamento}")
    A, b = COEFICIENTES_SUPERFICIE[acabamento]
    return min(A * Sut_MPa**b, 1.0)


def fator_temperatura(
    T_celsius: float,
    modelo: str = "norton",
) -> float:
    """Fator de temperatura segundo Norton ou Shigley."""
    if not math.isfinite(T_celsius):
        raise ValueError("T_celsius deve ser um número finito.")
    modelo = _validar_modelo(modelo)

    if modelo == "norton":
        T_fahrenheit = celsius_para_fahrenheit(T_celsius)
        if T_fahrenheit <= NORTON_TEMPERATURA_INICIO_F:
            return 1.0
        if T_fahrenheit <= NORTON_TEMPERATURA_MAX_F:
            return 1 - 0.0058 * (T_fahrenheit - NORTON_TEMPERATURA_INICIO_F)
        raise ValueError(
            "Norton: correlação válida até 550 °F (287,8 °C)."
        )

    if T_celsius < 20 or T_celsius > 540:
        raise ValueError("Shigley: use temperatura entre 20 °C e 540 °C.")
    if T_celsius < 37:
        return 1 + (T_celsius - 20) * (0.01 / 30)
    return (
        0.9877
        + 0.6507e-3 * T_celsius
        - 0.3414e-5 * T_celsius**2
        + 0.5621e-8 * T_celsius**3
        - 6.246e-12 * T_celsius**4
    )


def fator_confiabilidade(confiabilidade_pct: float) -> float:
    """Fator tabelado de confiabilidade."""
    if confiabilidade_pct not in FATORES_CONFIABILIDADE:
        raise ValueError(
            f"Confiabilidade não tabelada. Use: {list(FATORES_CONFIABILIDADE)}"
        )
    return FATORES_CONFIABILIDADE[confiabilidade_pct]


def calcular_se(
    Se_linha_MPa: float,
    Ccarreg: float,
    Ctamanho: float,
    Csuperf: float,
    Ctemp: float,
    Cconf: float,
) -> float:
    """Se corrigido pelo produto dos fatores de Marin."""
    valores = {
        "Se_linha_MPa": Se_linha_MPa,
        "Ccarreg": Ccarreg,
        "Ctamanho": Ctamanho,
        "Csuperf": Csuperf,
        "Ctemp": Ctemp,
        "Cconf": Cconf,
    }
    for nome, valor in valores.items():
        _validar_positivo(nome, valor)
    return math.prod(valores.values())


def _validar_estado_flutuante(
    sigma_a_MPa: float,
    sigma_m_MPa: float,
    resistencia_fadiga_MPa: float,
    resistencia_media_MPa: float,
) -> None:
    for nome, valor in (
        ("sigma_a_MPa", sigma_a_MPa),
        ("sigma_m_MPa", sigma_m_MPa),
    ):
        if not math.isfinite(valor) or valor < 0:
            raise ValueError(f"{nome} deve ser finito e não negativo.")
    _validar_positivo("resistencia_fadiga_MPa", resistencia_fadiga_MPa)
    _validar_positivo("resistencia_media_MPa", resistencia_media_MPa)


def fator_seguranca_goodman(
    sigma_a_MPa: float,
    sigma_m_MPa: float,
    Se_MPa: float,
    Sut_MPa: float,
) -> float:
    """
    Fator de segurança pela reta de Goodman modificada.

    Considera tensão média de tração e carregamento proporcional:
    1/n = sigma_a/Se + sigma_m/Sut.
    """
    _validar_estado_flutuante(sigma_a_MPa, sigma_m_MPa, Se_MPa, Sut_MPa)
    inverso_n = sigma_a_MPa / Se_MPa + sigma_m_MPa / Sut_MPa
    return math.inf if inverso_n == 0 else 1 / inverso_n


def fator_seguranca_soderberg(
    sigma_a_MPa: float,
    sigma_m_MPa: float,
    Se_MPa: float,
    Sy_MPa: float,
) -> float:
    """
    Fator de segurança pela reta de Soderberg.

    Considera tensão média de tração e carregamento proporcional:
    1/n = sigma_a/Se + sigma_m/Sy.
    """
    _validar_estado_flutuante(sigma_a_MPa, sigma_m_MPa, Se_MPa, Sy_MPa)
    inverso_n = sigma_a_MPa / Se_MPa + sigma_m_MPa / Sy_MPa
    return math.inf if inverso_n == 0 else 1 / inverso_n


def fator_seguranca_escoamento_flutuante(
    sigma_a_MPa: float,
    sigma_m_MPa: float,
    Sy_MPa: float,
) -> float:
    """Verificação de escoamento no primeiro ciclo: n = Sy/(sigma_a + sigma_m)."""
    _validar_estado_flutuante(sigma_a_MPa, sigma_m_MPa, Sy_MPa, Sy_MPa)
    sigma_maxima = sigma_a_MPa + sigma_m_MPa
    return math.inf if sigma_maxima == 0 else Sy_MPa / sigma_maxima


def fator_concentracao_fadiga(Kt: float, q: float) -> float:
    """Calcula Kf = 1 + q (Kt - 1)."""
    if not math.isfinite(Kt) or Kt < 1:
        raise ValueError("Kt deve ser finito e maior ou igual a 1.")
    if not math.isfinite(q) or not 0 <= q <= 1:
        raise ValueError("q deve estar entre 0 e 1.")
    return 1 + q * (Kt - 1)


def sensibilidade_entalhe_neuber(a_neuber_in: float, r_in: float) -> float:
    """Sensibilidade ao entalhe de Neuber, com a e r em polegadas."""
    _validar_positivo("a_neuber_in", a_neuber_in)
    _validar_positivo("r_in", r_in)
    return 1 / (1 + math.sqrt(a_neuber_in) / math.sqrt(r_in))


def tensao_com_concentracao(sigma_nominal_MPa: float, Kf: float) -> float:
    """Tensão dinâmica real = Kf vezes tensão nominal."""
    if not math.isfinite(sigma_nominal_MPa) or sigma_nominal_MPa < 0:
        raise ValueError("sigma_nominal_MPa deve ser finita e não negativa.")
    if not math.isfinite(Kf) or Kf < 1:
        raise ValueError("Kf deve ser finito e maior ou igual a 1.")
    return Kf * sigma_nominal_MPa


def resistencia_em_1e3_ciclos(
    Sut_MPa: float,
    tipo_carga: str = "flexao",
    modelo: str = "norton",
) -> float:
    """Estimativa de Sm em N=10³ ciclos para construir a curva S–N."""
    _validar_positivo("Sut_MPa", Sut_MPa)
    modelo = _validar_modelo(modelo)
    tipo_carga = tipo_carga.lower()
    if tipo_carga not in TIPOS_CARGA:
        raise ValueError(f"Tipo de carregamento não suportado: {tipo_carga}")
    if modelo == "norton" and tipo_carga == "axial":
        return 0.75 * Sut_MPa
    return 0.90 * Sut_MPa


def tensao_alternada_equivalente_goodman(
    sigma_a_MPa: float,
    sigma_m_MPa: float,
    Sut_MPa: float,
) -> float:
    """
    Converte tensão média de tração em amplitude totalmente reversa equivalente.

    Da reta de Goodman: sigma_a_eq = sigma_a / (1 - sigma_m/Sut).
    Retorna infinito quando sigma_m >= Sut, pois não há margem de tração.
    """
    _validar_estado_flutuante(
        sigma_a_MPa,
        sigma_m_MPa,
        Sut_MPa,
        Sut_MPa,
    )
    if sigma_m_MPa >= Sut_MPa:
        return math.inf
    return sigma_a_MPa / (1 - sigma_m_MPa / Sut_MPa)


def parametros_curva_sn(
    Sm_MPa: float, Se_MPa: float, N2: float, N1: float = _N1_PADRAO
) -> tuple[float, float]:
    """Parâmetros a e b da curva S(N) = a N^b entre N1 e N2."""
    valores = {"Sm_MPa": Sm_MPa, "Se_MPa": Se_MPa, "N1": N1, "N2": N2}
    for nome, valor in valores.items():
        _validar_positivo(nome, valor)
    if N2 <= N1:
        raise ValueError("N2 deve ser maior que N1.")
    if Sm_MPa <= Se_MPa:
        raise ValueError("Sm_MPa deve ser maior que Se_MPa.")
    z = math.log10(N1) - math.log10(N2)
    b = math.log10(Sm_MPa / Se_MPa) / z
    a = 10 ** (math.log10(Sm_MPa) - b * math.log10(N1))
    return a, b


def resistencia_para_N(N: float, a: float, b: float) -> float:
    """Resistência à fadiga para N ciclos."""
    _validar_positivo("N", N)
    _validar_positivo("a", a)
    if not math.isfinite(b) or b >= 0:
        raise ValueError("b deve ser finito e negativo.")
    return a * N**b


def ciclos_para_S(S_MPa: float, a: float, b: float) -> float:
    """Número de ciclos correspondente a uma amplitude S."""
    _validar_positivo("S_MPa", S_MPa)
    _validar_positivo("a", a)
    if not math.isfinite(b) or b >= 0:
        raise ValueError("b deve ser finito e negativo.")
    return (S_MPa / a) ** (1 / b)
