"""Ação do vento pela ABNT NBR 6123 — velocidade característica e pressão dinâmica.

O caminho é o da norma, sem atalhos::

    V_k = V_0 · S_1 · S_2 · S_3          (m/s)
    q   = 0,613 · V_k²                   (N/m²)
    F   = C_f · q · A_e                  (força de arrasto numa área efetiva)

``V_0`` é a velocidade básica do mapa de isopletas (rajada de 3 s, 10 m de
altura, campo aberto, 50 anos de período de retorno) — dado do projeto.
``S_1`` responde ao relevo (5.2), ``S_2`` à rugosidade do terreno, às
dimensões da edificação e à altura (5.3, Tabela 1: ``S_2 = b·F_r·(z/10)^p``)
e ``S_3`` ao grupo estatístico da edificação (5.4, Tabela 3). Os parâmetros
tabelados aqui são os da NBR 6123:1988 — a edição de 2023 manteve a
estrutura do cálculo, mas o mapa de isopletas e alguns fatores foram
revisados: confira ``V_0`` e ``S_3`` na edição adotada pelo projeto.

O módulo não substitui a norma nos coeficientes aerodinâmicos: ``C_f`` de
barras, treliças e edificações vem das Tabelas 10 a 14 e das Figuras 4 a 8,
e aqui entra como dado, com uma lista de valores usuais para orientação.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Fator S2 — rugosidade do terreno, dimensões e altura (Tabela 1)
# ---------------------------------------------------------------------------

CATEGORIAS_RUGOSIDADE: dict[str, str] = {
    "I": "Superfícies lisas de grandes dimensões (mar calmo, lagos, rios, pântanos sem vegetação).",
    "II": "Terreno aberto em nível, com poucos obstáculos isolados (campo, fazenda, aeroporto).",
    "III": "Terreno plano ou ondulado com obstáculos (sebes, muros, edificações baixas esparsas).",
    "IV": "Terreno com obstáculos numerosos e pouco espaçados (zona industrial, cidade pequena, subúrbio).",
    "V": "Terreno com obstáculos numerosos, grandes e altos (centro de grande cidade).",
}

CLASSES_EDIFICACAO: dict[str, str] = {
    "A": "Maior dimensão horizontal ou vertical da superfície frontal até 20 m.",
    "B": "Maior dimensão entre 20 m e 50 m.",
    "C": "Maior dimensão acima de 50 m.",
}

# (categoria, classe) -> (b, p); Fr por classe; altura gradiente por categoria.
PARAMETROS_S2: dict[tuple[str, str], tuple[float, float]] = {
    ("I", "A"): (1.10, 0.06),
    ("I", "B"): (1.11, 0.065),
    ("I", "C"): (1.12, 0.07),
    ("II", "A"): (1.00, 0.085),
    ("II", "B"): (1.00, 0.09),
    ("II", "C"): (1.00, 0.10),
    ("III", "A"): (0.94, 0.10),
    ("III", "B"): (0.94, 0.105),
    ("III", "C"): (0.93, 0.115),
    ("IV", "A"): (0.86, 0.12),
    ("IV", "B"): (0.85, 0.125),
    ("IV", "C"): (0.84, 0.135),
    ("V", "A"): (0.74, 0.15),
    ("V", "B"): (0.73, 0.16),
    ("V", "C"): (0.71, 0.175),
}
FATOR_RAJADA: dict[str, float] = {"A": 1.00, "B": 0.98, "C": 0.95}
ALTURA_GRADIENTE_M: dict[str, float] = {
    "I": 250.0,
    "II": 300.0,
    "III": 350.0,
    "IV": 420.0,
    "V": 500.0,
}
# A Tabela 2 começa em "z ≤ 5 m": abaixo disso vale o S2 de 5 m.
ALTURA_MINIMA_S2_M = 5.0

# ---------------------------------------------------------------------------
# Fator S3 — grupo estatístico (Tabela 3)
# ---------------------------------------------------------------------------

GRUPOS_S3: dict[int, tuple[float, str]] = {
    1: (
        1.10,
        "Edificações cuja ruína pode afetar a segurança ou o socorro após a tempestade "
        "(hospitais, quartéis de bombeiros, centrais de comunicação).",
    ),
    2: (
        1.00,
        "Hotéis e residências; comércio e indústria com alto fator de ocupação.",
    ),
    3: (
        0.95,
        "Edificações e instalações industriais com baixo fator de ocupação "
        "(depósitos, silos, construções rurais).",
    ),
    4: (0.88, "Vedações (telhas, vidros, painéis de vedação)."),
    5: (0.83, "Edificações temporárias; estruturas dos grupos 1 a 3 durante a construção."),
}

# ---------------------------------------------------------------------------
# Coeficientes de arrasto usuais — orientação, não substituem as tabelas
# ---------------------------------------------------------------------------

COEFICIENTES_ARRASTO_USUAIS: dict[str, float] = {
    "Perfil aberto isolado (I, U, H, cantoneira), vento normal à face — Tabela 11": 2.0,
    "Barra retangular de cantos vivos, seção quadrada — Tabela 11": 2.0,
    "Tubo circular liso, Re ≥ 4,2×10⁵ — Tabela 10": 0.6,
    "Tubo circular rugoso ou Re < 4,2×10⁵ — Tabela 10": 1.2,
    "Treliça plana de perfis de faces planas, índice de área exposta ≤ 0,3 — Figura 7": 1.8,
    "Edificação paralelepipédica fechada, vento normal à face maior — Figura 4": 1.3,
}

MASSA_ESPECIFICA_AR_FATOR = 0.613  # q = 0,613·Vk² (ar a 15 °C, 1 atm)


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número positivo.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser um número maior ou igual a zero.")
    return valor


def fator_s1(
    relevo: str, *, inclinacao_graus: float = 0.0, z_m: float = 0.0, d_m: float = 0.0
) -> float:
    """Fator topográfico S1 (5.2).

    * ``plano``: terreno plano ou fracamente acidentado — 1,0.
    * ``vale``: vales profundos protegidos de ventos de qualquer direção — 0,9.
    * ``talude`` ou ``morro``: ponto no topo (B) de talude/morro, com a
      inclinação média ``θ`` (graus), a altura ``z`` do ponto acima do terreno
      e a altura ``d`` do talude/morro. Para θ ≤ 3° vale 1,0; entre 6° e 17°
      ``S1 = 1 + (2,5 − z/d)·tan(θ − 3°) ≥ 1``; para θ ≥ 45°
      ``S1 = 1 + (2,5 − z/d)·0,31 ≥ 1``; nas faixas intermediárias a norma
      manda interpolar linearmente.
    """
    chave = str(relevo).strip().casefold()
    if chave in {"plano", "plano ou fracamente acidentado", "fracamente acidentado"}:
        return 1.0
    if chave in {"vale", "vale protegido", "vales profundos"}:
        return 0.9
    if chave not in {"talude", "morro", "talude ou morro"}:
        raise ValueError("Relevo desconhecido: use 'plano', 'vale', 'talude' ou 'morro'.")
    theta = float(inclinacao_graus)
    if not math.isfinite(theta) or theta < 0:
        raise ValueError("A inclinação do talude deve ser um ângulo em graus, ≥ 0.")
    if theta <= 3.0:
        return 1.0
    d = _positivo("altura do talude d", d_m)
    z = _nao_negativo("altura z acima do terreno", z_m)
    razao = 2.5 - z / d

    def s1_em(angulo: float) -> float:
        if angulo <= 3.0:
            return 1.0
        if angulo <= 17.0:
            return max(1.0, 1.0 + razao * math.tan(math.radians(angulo - 3.0)))
        return max(1.0, 1.0 + razao * 0.31)

    if 6.0 <= theta <= 17.0 or theta >= 45.0:
        return s1_em(theta)
    if theta < 6.0:
        # Interpolação linear entre 1,0 (3°) e o valor da fórmula em 6°.
        return 1.0 + (s1_em(6.0) - 1.0) * (theta - 3.0) / 3.0
    # 17° < θ < 45°: entre a fórmula em 17° e a de 45°.
    return s1_em(17.0) + (s1_em(45.0) - s1_em(17.0)) * (theta - 17.0) / 28.0


def fator_s2(altura_m: float, categoria: str, classe: str) -> float:
    """``S2 = b·F_r·(z/10)^p`` (5.3.3), com ``z`` limitado a [5 m, z_g]."""
    categoria = str(categoria).strip().upper()
    classe = str(classe).strip().upper()
    if (categoria, classe) not in PARAMETROS_S2:
        raise ValueError("Categoria de rugosidade I a V e classe A, B ou C (NBR 6123, Tabela 1).")
    z = _nao_negativo("altura", altura_m)
    z = min(max(z, ALTURA_MINIMA_S2_M), ALTURA_GRADIENTE_M[categoria])
    b, p = PARAMETROS_S2[(categoria, classe)]
    return b * FATOR_RAJADA[classe] * (z / 10.0) ** p


def fator_s3(grupo: int) -> float:
    try:
        return GRUPOS_S3[int(grupo)][0]
    except (KeyError, ValueError, TypeError) as erro:
        raise ValueError("Grupo estatístico de 1 a 5 (NBR 6123, Tabela 3).") from erro


def velocidade_caracteristica(v0_m_s: float, s1: float, s2: float, s3: float) -> float:
    return _positivo("V0", v0_m_s) * _positivo("S1", s1) * _positivo("S2", s2) * _positivo("S3", s3)


def pressao_dinamica_N_m2(vk_m_s: float) -> float:
    """``q = 0,613·V_k²`` em N/m² (Vk em m/s)."""
    return MASSA_ESPECIFICA_AR_FATOR * _positivo("Vk", vk_m_s) ** 2


@dataclass(frozen=True, slots=True)
class ResultadoVento:
    v0_m_s: float
    s1: float
    s2: float
    s3: float
    categoria: str
    classe: str
    altura_m: float
    vk_m_s: float
    pressao_N_m2: float
    coeficiente_arrasto: float
    area_efetiva_m2: float | None
    largura_exposta_m: float | None
    forca_kN: float | None
    carga_linear_kN_m: float | None
    memoria: tuple[str, ...] = field(default=())

    @property
    def pressao_kN_m2(self) -> float:
        return self.pressao_N_m2 / 1e3


def calcular_vento(
    v0_m_s: float,
    *,
    s1: float = 1.0,
    categoria: str = "II",
    classe: str = "A",
    altura_m: float = 10.0,
    grupo_s3: int = 2,
    s3: float | None = None,
    coeficiente_arrasto: float = 2.0,
    area_efetiva_m2: float | None = None,
    largura_exposta_m: float | None = None,
) -> ResultadoVento:
    """Velocidade característica, pressão dinâmica e força de arrasto.

    ``area_efetiva_m2`` dá a força total ``F = C_f·q·A_e``; ``largura_exposta_m``
    (altura do perfil ou da faixa exposta, em m) dá a carga por metro
    ``w = C_f·q·d`` para lançar numa barra do modelo. Os dois são opcionais.
    ``s3`` explícito sobrepõe o valor do grupo (para a edição de 2023 ou um
    critério de cliente).
    """
    v0 = _positivo("V0", v0_m_s)
    categoria = str(categoria).strip().upper()
    classe = str(classe).strip().upper()
    s2 = fator_s2(altura_m, categoria, classe)
    fator_3 = _positivo("S3", s3) if s3 is not None else fator_s3(grupo_s3)
    vk = velocidade_caracteristica(v0, s1, s2, fator_3)
    q = pressao_dinamica_N_m2(vk)
    cf = _positivo("Cf", coeficiente_arrasto)
    forca = None
    carga_linear = None
    b, p = PARAMETROS_S2[(categoria, classe)]
    memoria = [
        f"V₀ = {v0:.1f} m/s (mapa de isopletas, NBR 6123 Figura 1)",
        f"S₁ = {s1:.3f} (relevo, 5.2)",
        f"S₂ = b·Fr·(z/10)^p = {b:.2f} × {FATOR_RAJADA[classe]:.2f} × "
        f"({min(max(float(altura_m), ALTURA_MINIMA_S2_M), ALTURA_GRADIENTE_M[categoria]):.1f}/10)^{p:.3f} = {s2:.3f} "
        f"(categoria {categoria}, classe {classe}, Tabela 1)",
        f"S₃ = {fator_3:.2f}"
        + (f" (grupo {int(grupo_s3)}, Tabela 3)" if s3 is None else " (informado)"),
        f"V_k = V₀·S₁·S₂·S₃ = {vk:.2f} m/s",
        f"q = 0,613·V_k² = {q:.1f} N/m² = {q / 1e3:.3f} kN/m²",
    ]
    if area_efetiva_m2 is not None:
        area = _positivo("área efetiva", area_efetiva_m2)
        forca = cf * q * area / 1e3
        memoria.append(
            f"F = C_f·q·A_e = {cf:.2f} × {q / 1e3:.3f} kN/m² × {area:.3f} m² = {forca:.3f} kN"
        )
    if largura_exposta_m is not None:
        largura = _positivo("largura exposta", largura_exposta_m)
        carga_linear = cf * q * largura / 1e3
        memoria.append(
            f"w = C_f·q·d = {cf:.2f} × {q / 1e3:.3f} kN/m² × {largura:.3f} m = {carga_linear:.4f} kN/m"
        )
    return ResultadoVento(
        v0_m_s=v0,
        s1=float(s1),
        s2=s2,
        s3=fator_3,
        categoria=categoria,
        classe=classe,
        altura_m=float(altura_m),
        vk_m_s=vk,
        pressao_N_m2=q,
        coeficiente_arrasto=cf,
        area_efetiva_m2=None if area_efetiva_m2 is None else float(area_efetiva_m2),
        largura_exposta_m=None if largura_exposta_m is None else float(largura_exposta_m),
        forca_kN=forca,
        carga_linear_kN_m=carga_linear,
        memoria=tuple(memoria),
    )
