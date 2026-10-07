"""Velocidade característica e pressão dinâmica do vento — ABNT NBR 6123:2023, seções 4 e 5 e anexos A e B.

O caminho é o da norma, sem atalhos::

    V_k = V_0 · S_1 · S_2 · S_3          (m/s)
    q   = 0,613 · V_k²                   (N/m²)

``V_0`` é a velocidade básica do mapa de isopletas (rajada de 3 s, a 10 m do terreno, em campo
aberto e plano, excedida em média uma vez em 50 anos) e é dado do projeto. ``S_1`` responde ao
relevo (5.2); ``S_2``, à rugosidade do terreno, às dimensões da peça e à altura (5.3, Tabelas 1 a 3
e Anexo A); ``S_3``, ao grupo da edificação (5.4, Tabela 4) ou à probabilidade e à vida útil
adotadas (Anexo B).

O que a edição de 2023 mudou em relação à de 1988, e que este módulo segue:

* a Tabela 4 de ``S_3`` tem outros valores e outra descrição dos grupos (1,11 · 1,06 · 1,00 ·
  0,95 · 0,83) e permite usar ``0,92 · S_3`` só no projeto das vedações;
* na categoria V, ``S_2`` é constante até 10 m de altura (nas demais, até 5 m);
* ``S_2`` pode ser calculado para qualquer intervalo de tempo de 3 s a 1 h (Anexo A), e o intervalo
  das edificações com mais de 80 m vem de ``t = 7,5·L_t / V_t(h)`` (A.2);
* a velocidade de projeto para a análise dinâmica é ``V_p = 0,69·V_0·S_1·S_3`` (9.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

EDICAO = "ABNT NBR 6123:2023"

#: ρ = 1,226 kg/m³ → ½·ρ = 0,613 (q em N/m², V_k em m/s).
FATOR_PRESSAO_DINAMICA = 0.613

# ---------------------------------------------------------------------------
# Categorias de rugosidade (5.3.1, Tabela 5)
# ---------------------------------------------------------------------------

CATEGORIAS_RUGOSIDADE: dict[str, str] = {
    "I": (
        "Superfícies lisas de grandes dimensões, com mais de 5 km de extensão na direção do "
        "vento (mar calmo, lagos, rios, pântanos sem vegetação)."
    ),
    "II": (
        "Terreno aberto, em nível ou aproximadamente em nível, com poucos obstáculos isolados "
        "(zonas costeiras planas, campos de aviação, pradarias, fazendas sem sebes ou muros). "
        "Topo médio dos obstáculos ≤ 1 m."
    ),
    "III": (
        "Terreno plano ou ondulado com obstáculos, como sebes e muros, poucos quebra-ventos de "
        "árvores, edificações baixas e esparsas (granjas, subúrbios afastados do centro). "
        "Topo médio dos obstáculos ≈ 3 m."
    ),
    "IV": (
        "Terreno coberto por obstáculos numerosos e pouco espaçados, em zona florestal, "
        "industrial ou urbanizada (cidades pequenas e arredores, subúrbios densos, áreas "
        "industriais). Topo médio dos obstáculos ≈ 10 m."
    ),
    "V": (
        "Terreno coberto por obstáculos numerosos, grandes, altos e poucos espaçados (florestas "
        "de árvores altas, centros de grandes cidades, complexos industriais bem desenvolvidos). "
        "Topo médio dos obstáculos ≥ 25 m."
    ),
}

#: Altura da camada limite z_g (m) — Tabela 1 e Tabela 5.
ALTURA_GRADIENTE_M: dict[str, float] = {
    "I": 250.0,
    "II": 300.0,
    "III": 350.0,
    "IV": 420.0,
    "V": 500.0,
}

#: Comprimento de rugosidade z_0 (m) — Tabela 5.
COMPRIMENTO_RUGOSIDADE_M: dict[str, float] = {
    "I": 0.005,
    "II": 0.07,
    "III": 0.30,
    "IV": 1.0,
    "V": 2.5,
}

# ---------------------------------------------------------------------------
# Classes (5.3.2) e intervalo de tempo
# ---------------------------------------------------------------------------

CLASSES_EDIFICACAO: dict[str, str] = {
    "A": (
        "Maior dimensão horizontal ou vertical da superfície frontal até 20 m — rajada de 3 s. "
        "Também vale para os elementos de vedação e suas fixações."
    ),
    "B": "Maior dimensão entre 20 m e 50 m — rajada de 5 s.",
    "C": "Maior dimensão acima de 50 m — rajada de 10 s (acima de 80 m, ver o Anexo A).",
}

#: Intervalo de tempo da velocidade média de cada classe (5.3.2).
INTERVALO_DA_CLASSE_S: dict[str, float] = {"A": 3.0, "B": 5.0, "C": 10.0}

LIMITE_CLASSE_A_M = 20.0
LIMITE_CLASSE_B_M = 50.0
LIMITE_ANEXO_A_M = 80.0

#: Altura mínima para o cálculo de S_2 (Tabela 3 começa em "< 5 m"); na categoria V, 10 m.
ALTURA_MINIMA_S2_M = 5.0
ALTURA_MINIMA_S2_CATEGORIA_V_M = 10.0

# ---------------------------------------------------------------------------
# Anexo A, Tabela A.1 — parâmetros b_m, p e F_r para t de 3 s a 1 h
# ---------------------------------------------------------------------------

ANEXO_A_TEMPOS_S: tuple[float, ...] = (3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 600, 3600)

_ANEXO_A_BM: dict[str, tuple[float, ...]] = {
    "I": (1.10, 1.11, 1.12, 1.13, 1.14, 1.15, 1.16, 1.17, 1.19, 1.21, 1.23, 1.25),
    "II": (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    "III": (0.94, 0.94, 0.93, 0.92, 0.92, 0.91, 0.90, 0.90, 0.89, 0.87, 0.86, 0.85),
    "IV": (0.86, 0.85, 0.84, 0.83, 0.83, 0.82, 0.80, 0.79, 0.76, 0.73, 0.71, 0.68),
    "V": (0.74, 0.73, 0.71, 0.70, 0.69, 0.67, 0.64, 0.62, 0.58, 0.53, 0.50, 0.44),
}
_ANEXO_A_P: dict[str, tuple[float, ...]] = {
    "I": (0.06, 0.065, 0.07, 0.075, 0.075, 0.08, 0.085, 0.085, 0.09, 0.095, 0.095, 0.10),
    "II": (0.085, 0.09, 0.10, 0.105, 0.11, 0.115, 0.12, 0.125, 0.135, 0.145, 0.15, 0.16),
    "III": (0.10, 0.105, 0.115, 0.125, 0.13, 0.14, 0.145, 0.15, 0.16, 0.175, 0.185, 0.20),
    "IV": (0.12, 0.125, 0.135, 0.145, 0.15, 0.16, 0.17, 0.175, 0.195, 0.215, 0.23, 0.25),
    "V": (0.15, 0.16, 0.175, 0.185, 0.19, 0.205, 0.22, 0.23, 0.255, 0.285, 0.31, 0.35),
}
#: Fator de rajada F_r: sempre o da categoria II (5.3.3).
_ANEXO_A_FR: tuple[float, ...] = (
    1.00,
    0.98,
    0.95,
    0.93,
    0.90,
    0.87,
    0.84,
    0.82,
    0.77,
    0.72,
    0.69,
    0.65,
)

#: Tabela 1 — (categoria, classe) → (b_m, p): é a Tabela A.1 em t = 3, 5 e 10 s.
PARAMETROS_S2: dict[tuple[str, str], tuple[float, float]] = {
    (categoria, classe): (
        _ANEXO_A_BM[categoria][ANEXO_A_TEMPOS_S.index(INTERVALO_DA_CLASSE_S[classe])],
        _ANEXO_A_P[categoria][ANEXO_A_TEMPOS_S.index(INTERVALO_DA_CLASSE_S[classe])],
    )
    for categoria in CATEGORIAS_RUGOSIDADE
    for classe in CLASSES_EDIFICACAO
}

#: Tabela 2 — fator de rajada por classe.
FATOR_RAJADA: dict[str, float] = {
    classe: _ANEXO_A_FR[ANEXO_A_TEMPOS_S.index(INTERVALO_DA_CLASSE_S[classe])]
    for classe in CLASSES_EDIFICACAO
}

# ---------------------------------------------------------------------------
# Fator S3 — Tabela 4 e Anexo B
# ---------------------------------------------------------------------------

#: grupo → (S_3, período de recorrência T_p em anos, descrição resumida)
GRUPOS_S3: dict[int, tuple[float, int, str]] = {
    1: (
        1.11,
        100,
        "Ruína que pode afetar a segurança ou o socorro após uma tempestade (hospitais, quartéis "
        "de bombeiros e de forças de segurança, centrais de controle), pontes rodoviárias e "
        "ferroviárias, estruturas com substâncias inflamáveis, tóxicas ou explosivas.",
    ),
    2: (
        1.06,
        75,
        "Ruína com risco substancial à vida, em aglomerações: mais de 300 pessoas num mesmo "
        "ambiente (convenções, ginásios, estádios), creches com mais de 150 pessoas, escolas com "
        "mais de 250 pessoas.",
    ),
    3: (
        1.00,
        50,
        "Residências, hotéis, comércio e indústrias; estruturas desmontáveis para reutilização.",
    ),
    4: (
        0.95,
        37,
        "Edificações sem ocupação humana (depósitos, silos) e sem circulação de pessoas no entorno.",
    ),
    5: (
        0.83,
        15,
        "Edificações temporárias não reutilizáveis; estruturas dos grupos 1 a 4 durante a "
        "construção (no máximo 2 anos).",
    ),
}

#: Só no projeto das vedações a norma permite 0,92·S_3 (nota da Tabela 4).
FATOR_REDUCAO_VEDACOES = 0.92

#: Meia unidade da última casa (0,01) da Tabela B.1.
ARREDONDAMENTO_TABELA_B1 = 0.005


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


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


def _categoria(valor: str) -> str:
    categoria = str(valor).strip().upper()
    if categoria not in CATEGORIAS_RUGOSIDADE:
        raise ValueError("Categoria de rugosidade de I a V (NBR 6123:2023, 5.3.1).")
    return categoria


def _classe(valor: str) -> str:
    classe = str(valor).strip().upper()
    if classe not in CLASSES_EDIFICACAO:
        raise ValueError("Classe A, B ou C (NBR 6123:2023, 5.3.2).")
    return classe


def numero_ptbr(valor: float, casas: int = 2) -> str:
    """``1,23`` — o separador decimal que o texto da memória e da tela usa."""
    return f"{valor:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# S1 — fator topográfico (5.2)
# ---------------------------------------------------------------------------


def fator_s1(
    relevo: str, *, inclinacao_graus: float = 0.0, z_m: float = 0.0, d_m: float = 0.0
) -> float:
    """Fator topográfico S1 (5.2).

    * ``plano``: terreno plano ou fracamente acidentado — 1,0.
    * ``vale``: vales profundos protegidos de ventos de qualquer direção — 0,9.
    * ``talude`` ou ``morro``: ponto B, no topo, com a inclinação média ``θ`` (graus), a altura
      ``z`` do ponto acima do terreno e o desnível ``d`` entre a base e o topo. Para θ ≤ 3° vale
      1,0; entre 6° e 17° ``S1 = 1 + (2,5 − z/d)·tan(θ − 3°) ≥ 1``; para θ ≥ 45°
      ``S1 = 1 + (2,5 − z/d)·0,31 ≥ 1``; nas faixas intermediárias a norma manda interpolar
      linearmente. Nos pontos A e C vale 1,0 e, entre A e B ou B e C, interpola-se linearmente.
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


# ---------------------------------------------------------------------------
# S2 — rugosidade, dimensões e altura (5.3, Tabelas 1 a 3, Anexo A)
# ---------------------------------------------------------------------------


def classe_da_edificacao(maior_dimensao_m: float) -> str:
    """Classe A, B ou C pela maior dimensão horizontal ou vertical da superfície frontal (5.3.2)."""
    dimensao = _positivo("maior dimensão da superfície frontal", maior_dimensao_m)
    if dimensao <= LIMITE_CLASSE_A_M:
        return "A"
    if dimensao <= LIMITE_CLASSE_B_M:
        return "B"
    return "C"


def _interpolar_em_t(tabela: tuple[float, ...], t_s: float) -> float:
    """Valor da Tabela A.1 para um intervalo de tempo qualquer (interpolação linear em ln t)."""
    tempos = ANEXO_A_TEMPOS_S
    if t_s <= tempos[0]:
        return tabela[0]
    if t_s >= tempos[-1]:
        return tabela[-1]
    for i in range(len(tempos) - 1):
        if tempos[i] <= t_s <= tempos[i + 1]:
            fracao = (math.log(t_s) - math.log(tempos[i])) / (
                math.log(tempos[i + 1]) - math.log(tempos[i])
            )
            return tabela[i] + fracao * (tabela[i + 1] - tabela[i])
    return tabela[-1]  # pragma: no cover - a varredura acima cobre todo o intervalo


def parametros_de_s2(
    categoria: str, *, classe: str | None = "A", t_s: float | None = None
) -> tuple[float, float, float, float]:
    """``(b_m, p, F_r, t)`` da categoria e da classe (Tabelas 1 e 2) ou do intervalo ``t_s`` (A.1)."""
    categoria = _categoria(categoria)
    if t_s is not None:
        tempo = _positivo("intervalo de tempo t", t_s)
        if tempo < ANEXO_A_TEMPOS_S[0] or tempo > ANEXO_A_TEMPOS_S[-1]:
            raise ValueError("O Anexo A cobre intervalos de tempo de 3 s a 3 600 s.")
        return (
            _interpolar_em_t(_ANEXO_A_BM[categoria], tempo),
            _interpolar_em_t(_ANEXO_A_P[categoria], tempo),
            _interpolar_em_t(_ANEXO_A_FR, tempo),
            tempo,
        )
    classe = _classe(classe or "A")
    b_m, p = PARAMETROS_S2[(categoria, classe)]
    return b_m, p, FATOR_RAJADA[classe], INTERVALO_DA_CLASSE_S[classe]


@dataclass(frozen=True, slots=True)
class DetalheS2:
    """``S_2`` com os parâmetros usados e as ressalvas de aplicação."""

    s2: float
    categoria: str
    classe: str | None
    t_s: float
    b_m: float
    p: float
    fr: float
    altura_pedida_m: float
    altura_usada_m: float
    avisos: tuple[str, ...] = ()

    @property
    def formula(self) -> str:
        return (
            f"S₂ = b_m·F_r·(z/10)^p = {numero_ptbr(self.b_m)} × {numero_ptbr(self.fr)} × "
            f"({numero_ptbr(self.altura_usada_m, 1)}/10)^{numero_ptbr(self.p, 3)} = "
            f"{numero_ptbr(self.s2, 3)}"
        )


def detalhar_s2(
    altura_m: float, categoria: str, classe: str | None = "A", *, t_s: float | None = None
) -> DetalheS2:
    """``S_2 = b_m·F_r·(z/10)^p`` (5.3.3) para a altura ``z`` acima do terreno.

    Abaixo de 5 m vale o S_2 de 5 m (Tabela 3 começa em "< 5 m") e, na categoria V, o de 10 m,
    porque o vento defletido para baixo pelas edificações maiores aumenta a pressão junto ao solo.
    A equação só vale até a altura da camada limite ``z_g``: acima dela o valor é o de ``z_g`` e
    sai um aviso — a norma não cobre alturas maiores.
    """
    categoria = _categoria(categoria)
    z = _nao_negativo("altura", altura_m)
    avisos: list[str] = []
    minima = ALTURA_MINIMA_S2_CATEGORIA_V_M if categoria == "V" else ALTURA_MINIMA_S2_M
    z_usada = z
    if z < minima:
        z_usada = minima
        avisos.append(
            f"z = {numero_ptbr(z, 1)} m < {numero_ptbr(minima, 0)} m: vale o S₂ de "
            f"{numero_ptbr(minima, 0)} m (Tabela 3, categoria {categoria})."
        )
    zg = ALTURA_GRADIENTE_M[categoria]
    if z > zg:
        z_usada = zg
        avisos.append(
            f"z = {numero_ptbr(z, 0)} m acima de z_g = {numero_ptbr(zg, 0)} m (categoria "
            f"{categoria}): a norma não define S₂ acima da camada limite; usado o de z_g."
        )
    b_m, p, fr, tempo = parametros_de_s2(categoria, classe=classe, t_s=t_s)
    s2 = b_m * fr * (z_usada / 10.0) ** p
    return DetalheS2(
        s2=s2,
        categoria=categoria,
        classe=None if t_s is not None else _classe(classe or "A"),
        t_s=tempo,
        b_m=b_m,
        p=p,
        fr=fr,
        altura_pedida_m=z,
        altura_usada_m=z_usada,
        avisos=tuple(avisos),
    )


def fator_s2(
    altura_m: float, categoria: str, classe: str = "A", *, t_s: float | None = None
) -> float:
    """``S_2`` (5.3.3). Com ``t_s``, o Anexo A substitui a classe."""
    return detalhar_s2(altura_m, categoria, classe, t_s=t_s).s2


def intervalo_de_tempo_anexo_a(
    lt_m: float, v0_m_s: float, s1: float, categoria: str, altura_topo_m: float
) -> float:
    """Intervalo de tempo ``t = 7,5·L_t / V_t(h)`` das superfícies frontais com mais de 80 m (A.2).

    ``V_t(h) = S_1·S_2·V_0`` no topo; ``S_2`` depende de ``t``, então o cálculo é iterado.
    O resultado é limitado a [3 s, 3 600 s], o campo da Tabela A.1.
    """
    lt = _positivo("L_t", lt_m)
    v0 = _positivo("V0", v0_m_s)
    s1 = _positivo("S1", s1)
    tempo = 10.0
    for _ in range(100):
        s2 = fator_s2(altura_topo_m, categoria, t_s=tempo)
        novo = 7.5 * lt / (v0 * s1 * s2)
        novo = min(max(novo, ANEXO_A_TEMPOS_S[0]), ANEXO_A_TEMPOS_S[-1])
        if abs(novo - tempo) < 1e-6:
            return novo
        tempo = novo
    return tempo


# ---------------------------------------------------------------------------
# S3 — fator estatístico (5.4, Tabela 4, Anexo B)
# ---------------------------------------------------------------------------


def fator_s3(grupo: int, *, vedacao: bool = False) -> float:
    """``S_3`` mínimo do grupo (Tabela 4); ``vedacao`` aplica ``0,92·S_3`` (nota da Tabela 4)."""
    try:
        s3 = GRUPOS_S3[int(grupo)][0]
    except (KeyError, ValueError, TypeError) as erro:
        raise ValueError("Grupo estatístico de 1 a 5 (NBR 6123:2023, Tabela 4).") from erro
    return s3 * FATOR_REDUCAO_VEDACOES if vedacao else s3


def fator_s3_estatistico(probabilidade: float, vida_util_anos: float) -> float:
    """``S_3 = 0,54·[−ln(1 − P_m)/m_a]^(−0,157)`` (Anexo B).

    ``P_m`` é a probabilidade de a velocidade ser excedida pelo menos uma vez em ``m_a`` anos. A
    norma proíbe usar valor menor do que o mínimo do grupo da edificação (Tabela 4).
    """
    pm = float(probabilidade)
    if not 0.0 < pm < 1.0:
        raise ValueError("A probabilidade P_m deve estar entre 0 e 1 (exclusive).")
    ma = _positivo("vida útil m_a (anos)", vida_util_anos)
    return 0.54 * (-math.log(1.0 - pm) / ma) ** (-0.157)


def fator_s3_do_projeto(
    grupo: int, probabilidade: float | None = None, vida_util_anos: float | None = None
) -> tuple[float, str | None]:
    """``S_3`` a adotar e o aviso, se houver.

    Sem ``probabilidade`` e ``vida_util_anos`` vale o do grupo (Tabela 4). Com os dois, vale o do
    Anexo B, mas nunca menor do que o do grupo: a norma proíbe. Quando o do Anexo B fica abaixo,
    devolve o do grupo e o aviso que explica.
    """
    minimo = fator_s3(grupo)
    if probabilidade is None or vida_util_anos is None:
        return minimo, None
    calculado = fator_s3_estatistico(probabilidade, vida_util_anos)
    if calculado < minimo - ARREDONDAMENTO_TABELA_B1:
        return minimo, (
            f"S₃ do Anexo B = {numero_ptbr(calculado, 3)} ficou abaixo do mínimo do grupo "
            f"{int(grupo)} ({numero_ptbr(minimo, 2)}, Tabela 4): a norma não permite valor menor; "
            "usado o do grupo."
        )
    # Até meia unidade da última casa da Tabela B.1 abaixo do mínimo é arredondamento da norma
    # (0,54·[−ln 0,37/50]^−0,157 = 0,999 para o grupo 3): vale o do grupo, sem aviso.
    return max(calculado, minimo), None


# ---------------------------------------------------------------------------
# Velocidade característica e pressão dinâmica
# ---------------------------------------------------------------------------


def velocidade_caracteristica(v0_m_s: float, s1: float, s2: float, s3: float) -> float:
    """``V_k = V_0·S_1·S_2·S_3`` (4.2-b)."""
    return _positivo("V0", v0_m_s) * _positivo("S1", s1) * _positivo("S2", s2) * _positivo("S3", s3)


def pressao_dinamica_N_m2(vk_m_s: float) -> float:
    """``q = 0,613·V_k²`` em N/m² (V_k em m/s) — 4.2-c."""
    return FATOR_PRESSAO_DINAMICA * _positivo("Vk", vk_m_s) ** 2


def velocidade_de_projeto_dinamica(v0_m_s: float, s1: float, s3: float) -> float:
    """``V_p = 0,69·V_0·S_1·S_3``: média de 10 min a 10 m, categoria II (9.2)."""
    return 0.69 * _positivo("V0", v0_m_s) * _positivo("S1", s1) * _positivo("S3", s3)


@dataclass(frozen=True, slots=True)
class VentoNoLocal:
    """Velocidade e pressão dinâmica num ponto, com a memória do cálculo."""

    v0_m_s: float
    s1: float
    s2: float
    s3: float
    vk_m_s: float
    q_N_m2: float
    categoria: str
    classe: str | None
    t_s: float
    altura_m: float
    vedacao: bool
    grupo_s3: int | None
    avisos: tuple[str, ...] = ()
    memoria: tuple[str, ...] = field(default=())

    @property
    def q_kN_m2(self) -> float:
        return self.q_N_m2 / 1e3


def calcular_vento_no_local(
    v0_m_s: float,
    *,
    s1: float = 1.0,
    categoria: str = "II",
    classe: str | None = "A",
    t_s: float | None = None,
    altura_m: float = 10.0,
    grupo_s3: int = 3,
    s3: float | None = None,
    vedacao: bool = False,
) -> VentoNoLocal:
    """Cadeia completa ``V_k = V_0·S_1·S_2·S_3`` e ``q = 0,613·V_k²``.

    ``s3`` informado sobrepõe o do grupo (por exemplo, o do Anexo B); ``vedacao`` aplica
    ``0,92·S_3`` ao S_3 do grupo e só vale no projeto de telhas, vidros e painéis de vedação.
    """
    v0 = _positivo("V0", v0_m_s)
    fator_1 = _positivo("S1", s1)
    detalhe = detalhar_s2(altura_m, categoria, classe, t_s=t_s)
    if s3 is not None:
        fator_3 = _positivo("S3", s3)
        origem_s3 = "informado"
        grupo_usado: int | None = None
    else:
        fator_3 = fator_s3(grupo_s3, vedacao=vedacao)
        origem_s3 = f"grupo {int(grupo_s3)}, Tabela 4" + (
            ", × 0,92 das vedações" if vedacao else ""
        )
        grupo_usado = int(grupo_s3)
    vk = velocidade_caracteristica(v0, fator_1, detalhe.s2, fator_3)
    q = pressao_dinamica_N_m2(vk)
    classe_texto = (
        f"classe {detalhe.classe}, t = {numero_ptbr(detalhe.t_s, 0)} s"
        if detalhe.classe
        else f"t = {numero_ptbr(detalhe.t_s, 1)} s (Anexo A)"
    )
    memoria = (
        f"V₀ = {numero_ptbr(v0, 1)} m/s (isopletas, NBR 6123:2023, Figura 1)",
        f"S₁ = {numero_ptbr(fator_1, 3)} (relevo, 5.2)",
        f"{detalhe.formula} (categoria {detalhe.categoria}, {classe_texto}; Tabelas 1 e 2)",
        f"S₃ = {numero_ptbr(fator_3, 3)} ({origem_s3})",
        f"V_k = V₀·S₁·S₂·S₃ = {numero_ptbr(vk, 2)} m/s",
        f"q = 0,613·V_k² = {numero_ptbr(q, 1)} N/m² = {numero_ptbr(q / 1e3, 3)} kN/m²",
    )
    return VentoNoLocal(
        v0_m_s=v0,
        s1=fator_1,
        s2=detalhe.s2,
        s3=fator_3,
        vk_m_s=vk,
        q_N_m2=q,
        categoria=detalhe.categoria,
        classe=detalhe.classe,
        t_s=detalhe.t_s,
        altura_m=detalhe.altura_usada_m,
        vedacao=vedacao,
        grupo_s3=grupo_usado,
        avisos=detalhe.avisos,
        memoria=memoria,
    )
