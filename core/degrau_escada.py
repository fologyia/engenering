"""Degrau de escada industrial em grade de piso eletrofundida (catálogo Selmec "Degraus", DS).

Define o espelho, o piso e a profundidade do degrau, divide a escada em lances, avalia os 64
modelos do catálogo, dimensiona o degrau (flexão com flambagem lateral por torção, cisalhamento,
flechas, reações e parafusos) e fecha numa tabela de 38 verificações com o item da norma em cada
uma. Verifica a NR-12 (Anexo III), a NR-22, o Critério de Projeto Anglo American
AA-BR-DPST-DR-0001 Rev.1, a NBR 8800:2008, a NBR 6120 e a ISO 14122-3.

Módulo puro, sem Streamlit. Unidades internas: mm, MPa e N; as saídas de esforço, em kN, kN·m,
kN/m², kg e graus. A fonte das fórmulas e dos valores de aceite é a planilha validada
``Degrau_Escada_Grade_NR12_Anglo_Selmec.xlsx`` (ver ``docs/degrau_escada.md``).

Não faz: longarina, patamar e ligações da longarina; guarda-corpo (só confere as dimensões); a
pressão de contato do parafuso na chapa lateral (o catálogo não informa a espessura).

Nada é "corrigido em silêncio": entrada impossível levanta :class:`EntradaInvalida` com a causa.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core.verificacao import Verificacao, status_geral

# ---------------------------------------------------------------------------------------------
# Constantes normativas e do catálogo (cada uma com a fonte)
# ---------------------------------------------------------------------------------------------
#: Tolerância das comparações de faixa, em mm.
TOL_MM = 0.01
_EPS = 1e-9

K: dict[str, float] = dict(
    A_hmin=160, A_hmax=180,  # Anglo 10.2 – espelho
    A_bl_min=630, A_bl_max=640,  # Anglo 10.2 – Blondel 2h + b
    A_sobrep=20,  # Anglo 10.2 – profundidade do degrau ≥ b + 20
    A_lmin_ger=800, A_lmin_perm=1100, A_cab_h=3700,  # Anglo 10.2 – largura
    A_gc=1300, A_gc_esp=150,  # Anglo 10.2 – guarda-corpo
    A_tbar=2.00,  # Anglo 8.8 – barra chata de grade
    A_par_min=15.875,  # Anglo 8.8 – parafuso mínimo 5/8"
    A_npar_min=2,  # Anglo 9.1
    N12_hmax=250,  # NR-12 Anexo III 11 d) e 12 d)
    N12CE_hmin=200,  # NR-12 Anexo III 12 d) (com espelho)
    N12_gmin=150, N12CE_gmin=200,  # NR-12 Anexo III 11 b) / 12 b)
    N12_bl_min=600, N12_bl_max=660,  # NR-12 Anexo III 11 g): 600 ≤ g + 2h ≤ 660
    N12_lmin=600, N12_lmin_red=500, N12_hred=1500,  # NR-12 Anexo III 11 a), 11.1
    N12_lance=3000,  # NR-12 Anexo III 11 e) / 12 e)
    pat_min=600,  # NR-12 11 e); NR-22 22.9.3
    N22_hmin=180, N22_hmax=200,  # NR-22 22.10.1.1 a)
    N22_lance=3600,  # NR-22 22.10.1.1 b)
    N22_lmin=600,  # NR-22 22.9.3 (Portaria MTE 105/2026)
    N22_amin=20, N22_amax=50,  # NR-22 22.10.1.1
    ISO_amin=20, ISO_amax=45,  # NR-12 Anexo III item 2 / Fig. 1 (fonte ISO 14122-1)
    ISO_pmin=30, ISO_pmax=38,  # ISO 14122-3 (recomendação)
    gc_min=1100, gc_max=1200, gc_int=700, gc_rod=200,  # NR-12 Anexo III 7 c), e); NR-22 22.6.5
    Cat_Cmin=175, Cat_Cmax=300, Cat_Lmin=500, Cat_Lmax=1500,  # Selmec nota 2
    Cat_peso=1.20,  # Selmec nota 4: grade equivalente + 20 %
    Cat_furo=14.2875,  # Selmec: furo oblongo 9/16" × 25 mm
    fub_A307=415,  # NBR 8800:2008 Tab. A.3
)  # fmt: skip

# Enquadramento legal, uso, superfície, acabamento e seleção.
NR12 = "NR12"
NR22 = "NR22"
ENQUADRAMENTOS = {
    NR12: "NR-12 – acesso a máquina/equipamento",
    NR22: "NR-22 – acesso a local de trabalho (mineração)",
}
USO_GERAL = "geral"
USO_PERMANENTE = "permanente"
USO_CABINE = "cabine"
USOS = {
    USO_GERAL: "Geral / inspeção e manutenção",
    USO_PERMANENTE: "Permanência constante (rota de emergência)",
    USO_CABINE: "Cabine no 1º andar (até 3.700 mm)",
}
SUPERFICIE_SERRILHADA = "serrilhada"
SUPERFICIE_LISA = "lisa"
SUPERFICIES = {SUPERFICIE_SERRILHADA: "Serrilhada", SUPERFICIE_LISA: "Lisa"}
ACABAMENTO_GALVANIZADO = "galvanizado"
ACABAMENTO_NATURAL = "natural"
ACABAMENTO_PASSIVADO = "passivado"
ACABAMENTOS = {
    ACABAMENTO_GALVANIZADO: "Galvanizado a fogo",
    ACABAMENTO_NATURAL: "Natural (sem proteção)",
    ACABAMENTO_PASSIVADO: "Passivado (aço inox)",
}
SELECAO_AUTOMATICA = "automatica"
SELECAO_MANUAL = "manual"
QUALQUER = "Qualquer"
MALHAS = {
    "A": "A – 30 mm",
    "B": "B – 25 mm",
    "C": "C – 35 mm",
    "F": "F – 41 mm",
}
LIGACOES = {"4": "100 mm – tipo 4", "2": "50 mm – tipo 2"}


@dataclass(frozen=True)
class Material:
    """Aço da grade: ``fy`` e ``fu`` em MPa, ``E`` em MPa e ``rho`` em kg/m³."""

    nome: str
    fy: float
    fu: float
    E: float
    rho: float
    observacao: str


#: Anglo 4.5 Tab. 1 (ASTM A36); inox: ASTM A276/A240 — a NBR 8800 não cobre inox (indicativo).
MATERIAIS: dict[str, Material] = {
    "ASTM A36": Material("ASTM A36", 250.0, 400.0, 200_000.0, 7850.0, "Anglo 4.5 Tab. 1"),
    "AISI 304": Material(
        "AISI 304", 205.0, 515.0, 193_000.0, 8000.0, "ASTM A276/A240; NBR 8800 não cobre inox"
    ),
    "AISI 304L": Material(
        "AISI 304L", 170.0, 485.0, 193_000.0, 8000.0, "ASTM A276/A240; NBR 8800 não cobre inox"
    ),
    "AISI 316": Material(
        "AISI 316", 205.0, 515.0, 193_000.0, 8000.0, "ASTM A276/A240; NBR 8800 não cobre inox"
    ),
    "AISI 316L": Material(
        "AISI 316L", 170.0, 485.0, 193_000.0, 8000.0, "ASTM A276/A240; NBR 8800 não cobre inox"
    ),
}
MATERIAL_PADRAO = "ASTM A36"

#: Parafuso A307: designação → (diâmetro d, furo-padrão d + 1/16") em mm.
PARAFUSOS: dict[str, tuple[float, float]] = {
    '1/2"': (12.70, 14.2875),
    '5/8"': (15.875, 17.4625),
}
PARAFUSO_PADRAO = '5/8"'

#: Selmec – C (profundidade do degrau) → F (furação da chapa lateral), em mm.
FURACAO_POR_C: dict[int, int] = {175: 85, 200: 85, 225: 110, 250: 110, 275: 135, 300: 135}
SERIE_C = tuple(sorted(FURACAO_POR_C))

# Selmec – 64 modelos: DS-{T}{k}-{h_b}/{tt}.
TIPOS_MALHA = ("A", "B", "C", "F")
PASSO_BARRAS_PORTANTES = {"A": 30.0, "B": 25.0, "C": 35.0, "F": 41.0}  # p, mm
LIGACOES_K = ("4", "2")
PASSO_BARRAS_LIGACAO = {"4": 100.0, "2": 50.0}  # s, mm
ALTURAS_BARRA = (25, 30, 35, 40)  # h_b, mm
ESPESSURAS = {"3": 3.00, "5": 4.76}  # tt → t_b, mm

#: L máx recomendado (mm) — maior largura com quadrado azul na tabela do catálogo; igual para
#: k = 4 e k = 2. Chave: (h_b, tt) → (A, B, C, F).
L_MAX_RECOMENDADO: dict[tuple[int, str], tuple[int, int, int, int]] = {
    (25, "3"): (700, 800, 600, 500),
    (30, "3"): (800, 900, 700, 600),
    (35, "3"): (900, 1000, 800, 700),
    (40, "3"): (1000, 1100, 1000, 800),
    (25, "5"): (1000, 1000, 1000, 800),
    (30, "5"): (1100, 1100, 1000, 900),
    (35, "5"): (1200, 1200, 1100, 1000),
    (40, "5"): (1500, 1500, 1400, 1200),
}

GRAVIDADE = 9.81  # m/s²
MODELO_MANUAL_PADRAO = "DS-A4-30/3"


@dataclass
class VerificacaoDegrau(Verificacao):
    """Linha da tabela do degrau: a :class:`~core.verificacao.Verificacao` do programa mais o
    ``valor`` adotado (ou que atua) e o ``limite`` (ou a resistência) das colunas Valor e Limite."""

    valor: float | None = None
    limite: float | None = None


class EntradaInvalida(ValueError):
    """Entrada impossível de calcular; a mensagem diz o que corrigir (nada é ajustado)."""


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EntradaDegrau:
    """Todas as entradas da página, com os padrões da especificação."""

    # enquadramento
    enquadramento: str = NR12
    espelho_fechado: bool = False
    uso: str = USO_GERAL
    # geometria
    H_mm: float = 3600.0
    h_alvo_mm: float = 175.0
    n_imposto: int | None = None
    b_imposto_mm: float | None = None
    C_imposto_mm: float | None = None
    C_padronizado: bool = True
    L_mm: float = 800.0
    reducao_largura_mm: float = 0.0
    altura_max_lance_imposta_mm: float | None = None
    patamar_mm: float = 900.0
    # degrau
    selecao: str = SELECAO_AUTOMATICA
    malha_preferida: str = "A"
    ligacao_preferida: str = "4"
    modelo_manual: str = MODELO_MANUAL_PADRAO
    superficie: str = SUPERFICIE_SERRILHADA
    chapa_xadrez: bool = True
    acabamento: str = ACABAMENTO_GALVANIZADO
    material: str = MATERIAL_PADRAO
    lado_barra_ligacao_mm: float = 6.0
    parafuso: str = PARAFUSO_PADRAO
    n_parafusos_por_lado: int = 2
    # cargas, coeficientes e limites
    q_kN_m2: float = 3.00
    P_kN: float = 2.50
    P_iso_kN: float = 1.50
    b_c_mm: float = 100.0
    n_ef_imposto: int | None = None
    gamma_g: float = 1.25
    gamma_q: float = 1.50
    gamma_a1: float = 1.10
    gamma_a2: float = 1.35
    Cb: float = 1.00
    flecha_div: float = 300.0
    flecha_iso_div: float = 300.0
    flecha_iso_max_mm: float = 6.0
    # guarda-corpo (só conferência)
    gc_superior_mm: float = 1200.0
    gc_intermediario_mm: float = 700.0
    gc_rodape_mm: float = 200.0
    gc_espacamento_mm: float = 150.0


def _inteiro(valor: Any) -> bool:
    return isinstance(valor, int) or (isinstance(valor, float) and float(valor).is_integer())


def validar_entrada(e: EntradaDegrau) -> list[str]:
    """Mensagens de erro de uma entrada que não dá para calcular (lista vazia = pode calcular)."""
    erros: list[str] = []
    if e.enquadramento not in ENQUADRAMENTOS:
        erros.append(f"Enquadramento desconhecido: {e.enquadramento!r}.")
    if e.uso not in USOS:
        erros.append(f"Uso desconhecido: {e.uso!r}.")
    if not e.H_mm > 0:
        erros.append("O desnível total H precisa ser maior que zero.")
    if not e.L_mm > 0:
        erros.append("O comprimento do degrau L precisa ser maior que zero.")
    if not e.h_alvo_mm > 0:
        erros.append("O espelho alvo precisa ser maior que zero.")
    if e.n_imposto is not None and (not _inteiro(e.n_imposto) or e.n_imposto < 1):
        erros.append("O nº de espelhos imposto precisa ser um inteiro maior ou igual a 1.")
    if e.b_imposto_mm is not None and not e.b_imposto_mm > 0:
        erros.append("O piso b imposto precisa ser maior que zero.")
    if e.C_imposto_mm is not None and not e.C_imposto_mm > 0:
        erros.append("A profundidade C imposta precisa ser maior que zero.")
    if e.reducao_largura_mm < 0 or e.reducao_largura_mm >= e.L_mm > 0:
        erros.append("A redução da largura útil precisa estar entre 0 e o comprimento L.")
    if e.altura_max_lance_imposta_mm is not None and not e.altura_max_lance_imposta_mm > 0:
        erros.append("A altura máxima por lance imposta precisa ser maior que zero.")
    if e.patamar_mm < 0:
        erros.append("O comprimento do patamar não pode ser negativo.")
    if e.selecao not in (SELECAO_AUTOMATICA, SELECAO_MANUAL):
        erros.append(f"Seleção desconhecida: {e.selecao!r}.")
    if e.selecao == SELECAO_MANUAL and e.modelo_manual not in {m.nome for m in catalogo()}:
        erros.append(f"O modelo manual {e.modelo_manual!r} não existe no catálogo.")
    if e.material not in MATERIAIS:
        erros.append(f"Material desconhecido: {e.material!r}.")
    if e.parafuso not in PARAFUSOS:
        erros.append(f"Parafuso desconhecido: {e.parafuso!r}.")
    if e.superficie not in SUPERFICIES:
        erros.append(f"Superfície desconhecida: {e.superficie!r}.")
    if e.acabamento not in ACABAMENTOS:
        erros.append(f"Acabamento desconhecido: {e.acabamento!r}.")
    if not e.lado_barra_ligacao_mm > 0:
        erros.append("O lado da barra de ligação precisa ser maior que zero.")
    if not _inteiro(e.n_parafusos_por_lado) or e.n_parafusos_por_lado < 1:
        erros.append("O nº de parafusos por lado precisa ser um inteiro maior ou igual a 1.")
    if e.n_ef_imposto is not None and (not _inteiro(e.n_ef_imposto) or e.n_ef_imposto < 1):
        erros.append("O n_ef imposto precisa ser um inteiro maior ou igual a 1.")
    for nome, valor in (
        ("q", e.q_kN_m2),
        ("P", e.P_kN),
        ("P_ISO", e.P_iso_kN),
        ("b_c", e.b_c_mm),
        ("γg", e.gamma_g),
        ("γq", e.gamma_q),
        ("γa1", e.gamma_a1),
        ("γa2", e.gamma_a2),
        ("Cb", e.Cb),
        ("a flecha L/…", e.flecha_div),
        ("a flecha ISO L/…", e.flecha_iso_div),
        ("a flecha ISO máxima", e.flecha_iso_max_mm),
    ):
        if not valor > 0:
            erros.append(f"{nome} precisa ser maior que zero.")
    return erros


# ---------------------------------------------------------------------------------------------
# Utilidades numéricas
# ---------------------------------------------------------------------------------------------
def _ceil(x: float) -> int:
    """Teto que ignora o ruído de ponto flutuante (20,000000000000004 → 20)."""
    return math.ceil(x - _EPS)


def _floor(x: float) -> int:
    return math.floor(x + _EPS)


def _arredonda(x: float) -> int:
    """Arredondamento do Excel (metade para cima), não o do Python (metade para par)."""
    return math.floor(x + 0.5 + _EPS)


def _ge(a: float, b: float) -> bool:
    return a >= b - TOL_MM


def _le(a: float, b: float) -> bool:
    return a <= b + TOL_MM


def numero_pt(x: float, casas: int = 2) -> str:
    """Número com vírgula decimal e sem zeros inúteis: 180 → "180", 166,667 → "166,67"."""
    texto = f"{x:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") or "0"


def numero_pt_fixo(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------------------------
# 5.1 Espelho h e nº de espelhos n
# ---------------------------------------------------------------------------------------------
MENSAGENS_NIVEL = {
    1: "Atende NR, Critério Anglo e catálogo (C ≤ 300 mm)",
    2: "Atende NR e Anglo, mas C > 300 mm (fora do catálogo)",
    3: "CONFLITO: atende só a NR (prevalece – Anglo 3.1); h fora da faixa Anglo",
    4: "Nenhuma faixa atendida – rever o desnível",
}


@dataclass(frozen=True)
class FaixaEspelho:
    """Resultado de 5.1: faixa legal, nível atingido e nº de espelhos."""

    hL_min: float
    hL_max: float
    hCat_min: float
    nivel: int
    h_min_nivel: float
    h_max_nivel: float
    h_alvo_ef: float
    n_lo: int
    n_hi: float  # pode ser infinito (nível 3 sem mínimo legal)
    n_auto: int
    mensagem: str


def faixa_legal_espelho(enquadramento: str, espelho_fechado: bool) -> tuple[float, float]:
    """``(hL_min, hL_max)``: NR-22 180–200; NR-12 com espelho 200–250; NR-12 sem espelho ≤ 250."""
    if enquadramento == NR22:
        return float(K["N22_hmin"]), float(K["N22_hmax"])
    return (float(K["N12CE_hmin"]) if espelho_fechado else 0.0), float(K["N12_hmax"])


def _nivel_viavel(H: float, h_min: float, h_max: float) -> bool:
    if h_min > h_max + TOL_MM:
        return False
    n_min = _ceil(H / h_max)
    n_max = math.inf if h_min <= 0 else _floor(H / h_min)
    return n_min <= n_max


def faixa_espelho(
    H_mm: float, h_alvo_mm: float, enquadramento: str, espelho_fechado: bool
) -> FaixaEspelho:
    """Escolhe o nível (1 a 4) e o nº de espelhos automático, na ordem de prioridade da 5.1."""
    hL_min, hL_max = faixa_legal_espelho(enquadramento, espelho_fechado)
    # h mínimo para o degrau caber no catálogo: C ≤ 300 com C ≥ b + 20 e 2h + b ≥ 630 → h ≥ 175.
    h_cat_min = (K["A_bl_min"] - (K["Cat_Cmax"] - K["A_sobrep"])) / 2
    niveis = (
        (max(hL_min, K["A_hmin"], h_cat_min), min(hL_max, K["A_hmax"])),
        (max(hL_min, K["A_hmin"]), min(hL_max, K["A_hmax"])),
        (hL_min, hL_max),
    )
    nivel = 4
    for indice, (h_min, h_max) in enumerate(niveis, start=1):
        if _nivel_viavel(H_mm, h_min, h_max):
            nivel = indice
            break
    if nivel <= 3:
        h_min_n, h_max_n = niveis[nivel - 1]
        n_lo = max(1, _ceil(H_mm / h_max_n))
        n_hi: float = max(n_lo, math.inf if h_min_n <= 0 else _floor(H_mm / h_min_n))
    else:
        h_min_n, h_max_n = hL_min, hL_max
        n_lo = max(1, _ceil(H_mm / hL_max))
        n_hi = n_lo
    if nivel == 3:
        if hL_min >= 180:
            h_alvo_ef = hL_min
        elif hL_max <= 160:
            h_alvo_ef = hL_max
        else:
            h_alvo_ef = h_alvo_mm
    else:
        h_alvo_ef = h_alvo_mm
    n_auto = max(1, int(min(max(_arredonda(H_mm / h_alvo_ef), n_lo), n_hi)))
    return FaixaEspelho(
        hL_min=hL_min,
        hL_max=hL_max,
        hCat_min=h_cat_min,
        nivel=nivel,
        h_min_nivel=h_min_n,
        h_max_nivel=h_max_n,
        h_alvo_ef=h_alvo_ef,
        n_lo=n_lo,
        n_hi=n_hi,
        n_auto=n_auto,
        mensagem=MENSAGENS_NIVEL[nivel],
    )


def escolher_n(faixa: FaixaEspelho, n_imposto: int | None) -> int:
    """``n`` = o imposto, se informado; senão o automático."""
    return int(n_imposto) if n_imposto is not None else faixa.n_auto


# ---------------------------------------------------------------------------------------------
# 5.2 Piso b
# ---------------------------------------------------------------------------------------------
def faixa_piso_legal(h_mm: float, enquadramento: str, espelho_fechado: bool) -> tuple[float, float]:
    """``(bN_min, bN_max)``: NR-22 sem limite; espelho fechado ≥ 200; NR-12 sem espelho 11 g)."""
    if enquadramento == NR22:
        return 0.0, math.inf
    if espelho_fechado:
        return float(K["N12CE_gmin"]), math.inf
    return (
        max(float(K["N12_gmin"]), K["N12_bl_min"] - 2 * h_mm),
        K["N12_bl_max"] - 2 * h_mm,
    )


def piso_b(
    h_mm: float, enquadramento: str, espelho_fechado: bool, b_imposto_mm: float | None
) -> float:
    """Piso do degrau: o imposto, ou o menor múltiplo de 5 mm que cumpre Anglo e a norma legal."""
    if b_imposto_mm is not None:
        return float(b_imposto_mm)
    bA_min = K["A_bl_min"] - 2 * h_mm
    bA_max = K["A_bl_max"] - 2 * h_mm
    bN_min, bN_max = faixa_piso_legal(h_mm, enquadramento, espelho_fechado)
    b_min = max(bA_min, bN_min)
    b_max = min(bA_max, bN_max)
    if b_min <= b_max + TOL_MM:
        multiplo_de_5 = _ceil(b_min / 5) * 5
        # O menor múltiplo de 5 reduz a profundidade C.
        return float(multiplo_de_5 if multiplo_de_5 <= b_max + TOL_MM else _ceil(b_min))
    # Sem interseção: o requisito legal prevalece (Anglo 3.1).
    return float(min(_ceil(bN_min / 5) * 5, bN_max))


# ---------------------------------------------------------------------------------------------
# 5.3 Profundidade do degrau C e furação F
# ---------------------------------------------------------------------------------------------
def profundidade_C(b_mm: float, C_imposto_mm: float | None, padronizado: bool) -> float:
    """C = o imposto; senão a série 175, 200, … 300 (e 325, 350…) ou o múltiplo de 5 mm."""
    if C_imposto_mm is not None:
        return float(C_imposto_mm)
    c_min_anglo = b_mm + K["A_sobrep"]
    c_min_norma = b_mm  # NR-12: projeção r ≥ 0
    c_req = max(c_min_anglo, c_min_norma, K["Cat_Cmin"])
    if padronizado:
        return float(K["Cat_Cmin"] + _ceil(max(0.0, c_req - K["Cat_Cmin"]) / 25) * 25)
    return float(_ceil(c_req / 5) * 5)


def c_na_serie(C_mm: float) -> bool:
    return any(abs(C_mm - c) <= TOL_MM for c in SERIE_C)


def furacao_F(C_mm: float) -> int:
    """F do maior C padrão que não passa de ``min(max(C, 175), 300)``."""
    c_ref = min(max(C_mm, K["Cat_Cmin"]), K["Cat_Cmax"])
    c_padrao = max(c for c in SERIE_C if c <= c_ref + TOL_MM)
    return FURACAO_POR_C[c_padrao]


# ---------------------------------------------------------------------------------------------
# 5.4 Lances
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Lances:
    altura_max_lance_mm: float  # a usada para dividir (a imposta ou a legal)
    altura_max_legal_mm: float
    k_max: int
    n_lances: int
    k: int  # espelhos do lance maior
    k_min: int
    texto: str
    altura_lance_maior_mm: float
    n_degraus_grade: int
    n_patamares: int
    projecao_lance_maior_mm: float
    projecao_total_mm: float
    comprimento_inclinado_mm: float


def altura_max_legal_lance(enquadramento: str) -> float:
    return float(K["N22_lance"] if enquadramento == NR22 else K["N12_lance"])


def lances(
    n: int,
    h_mm: float,
    b_mm: float,
    patamar_mm: float,
    enquadramento: str,
    imposta_mm: float | None,
) -> Lances:
    legal = altura_max_legal_lance(enquadramento)
    altura_max = float(imposta_mm) if imposta_mm is not None else legal
    k_max = _floor(altura_max / h_mm)
    if k_max < 1:
        raise EntradaInvalida(
            f"A altura máxima por lance ({numero_pt(altura_max, 0)} mm) é menor que um espelho "
            f"({numero_pt(h_mm, 1)} mm): aumente a altura máxima por lance ou reduza o espelho."
        )
    n_lances = _ceil(n / k_max)
    k = _ceil(n / n_lances)
    k_min = _floor(n / n_lances)
    if k == k_min:
        texto = f"{n_lances} lance(s) de {k} espelhos"
    else:
        com_k = n - n_lances * k_min
        texto = f"{com_k} lance(s) de {k} + {n_lances - com_k} lance(s) de {k_min} espelhos"
    degraus = n - n_lances
    return Lances(
        altura_max_lance_mm=altura_max,
        altura_max_legal_mm=legal,
        k_max=k_max,
        n_lances=n_lances,
        k=k,
        k_min=k_min,
        texto=texto,
        altura_lance_maior_mm=k * h_mm,
        n_degraus_grade=degraus,
        n_patamares=n_lances - 1,
        projecao_lance_maior_mm=(k - 1) * b_mm,
        projecao_total_mm=degraus * b_mm + (n_lances - 1) * patamar_mm,
        comprimento_inclinado_mm=math.hypot(k * h_mm, (k - 1) * b_mm),
    )


# ---------------------------------------------------------------------------------------------
# 5.5 Largura
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Larguras:
    util_mm: float
    minima_legal_mm: float
    minima_anglo_mm: float


def larguras(
    L_mm: float, reducao_mm: float, enquadramento: str, n_lances: int, H_mm: float, uso: str
) -> Larguras:
    if enquadramento == NR22:
        legal = float(K["N22_lmin"])
    elif n_lances == 1 and H_mm < K["N12_hred"]:
        legal = float(K["N12_lmin_red"])
    else:
        legal = float(K["N12_lmin"])
    if uso == USO_PERMANENTE:
        anglo = float(K["A_lmin_perm"])
    elif uso == USO_CABINE:
        anglo = float(K["A_lmin_ger"] if H_mm <= K["A_cab_h"] else K["A_lmin_perm"])
    else:
        anglo = float(K["A_lmin_ger"])
    return Larguras(util_mm=L_mm - reducao_mm, minima_legal_mm=legal, minima_anglo_mm=anglo)


# ---------------------------------------------------------------------------------------------
# 4.5 Catálogo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ModeloDS:
    """Um modelo do catálogo: ``DS-{T}{k}-{h_b}/{tt}``."""

    nome: str
    tipo: str  # A, B, C ou F
    k: str  # "4" ou "2"
    h_b_mm: int
    tt: str  # "3" ou "5"
    p_mm: float  # passo das barras portantes
    s_mm: float  # passo das barras de ligação
    t_b_mm: float  # espessura da barra portante
    h_chapa_mm: int  # dimensão H da chapa lateral = h_b + 15
    L_max_mm: int  # L máx recomendado


def catalogo() -> tuple[ModeloDS, ...]:
    """Os 64 modelos, na ordem T, k, h_b, tt (a do desempate da seleção)."""
    modelos: list[ModeloDS] = []
    for t_indice, tipo in enumerate(TIPOS_MALHA):
        for k in LIGACOES_K:
            for h_b in ALTURAS_BARRA:
                for tt in ESPESSURAS:
                    modelos.append(
                        ModeloDS(
                            nome=f"DS-{tipo}{k}-{h_b}/{tt}",
                            tipo=tipo,
                            k=k,
                            h_b_mm=h_b,
                            tt=tt,
                            p_mm=PASSO_BARRAS_PORTANTES[tipo],
                            s_mm=PASSO_BARRAS_LIGACAO[k],
                            t_b_mm=ESPESSURAS[tt],
                            h_chapa_mm=h_b + 15,
                            L_max_mm=L_MAX_RECOMENDADO[(h_b, tt)][t_indice],
                        )
                    )
    return tuple(modelos)


def obter_modelo(nome: str) -> ModeloDS:
    for modelo in catalogo():
        if modelo.nome == nome:
            return modelo
    raise EntradaInvalida(f"O modelo {nome!r} não existe no catálogo.")


# ---------------------------------------------------------------------------------------------
# 5.6 Cálculo de um modelo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoModelo:
    """Tudo o que se calcula de um modelo, para a tabela dos 64 e para o memorial do adotado."""

    modelo: ModeloDS
    C_mm: float
    L_mm: float
    n_bb: int
    n_ef: int
    area_mm2: float
    inercia_mm4: float
    W_mm3: float
    Z_mm3: float
    J_mm4: float
    r_y_mm: float
    lam: float
    Mpl_Nmm: float
    Mr_Nmm: float
    lam_p: float
    lam_r: float
    Mcr_Nmm: float
    MRk_Nmm: float
    regime_flt: str
    MRd_kNm: float  # por barra
    VRd_kN: float  # por barra
    peso_grade_kg_m2: float
    peso_degrau_kg: float
    g_kN_m2: float
    # ELU – distribuída
    w_d_kN_m: float
    M_sd_d_kNm: float
    u_flex_d: float
    # ELU – concentrada
    P_d_kN: float
    M_sd_c_kNm: float
    u_flex_c: float
    # ELU – cisalhamento
    V_sd_kN: float
    u_cis: float
    # ELS
    delta_d_mm: float
    limite_d_mm: float
    u_fl_d: float
    delta_iso_mm: float
    limite_iso_mm: float
    u_fl_i: float
    u_max: float
    atende: bool
    na_preferencia: bool

    @property
    def usos(self) -> dict[str, float]:
        return {
            "u_flex_d": self.u_flex_d,
            "u_flex_c": self.u_flex_c,
            "u_cis": self.u_cis,
            "u_fl_d": self.u_fl_d,
            "u_fl_i": self.u_fl_i,
        }


def _na_preferencia(modelo: ModeloDS, malha: str, ligacao: str) -> bool:
    malha_ok = malha == QUALQUER or modelo.tipo == malha
    ligacao_ok = ligacao == QUALQUER or modelo.k == ligacao
    return malha_ok and ligacao_ok


def calcular_modelo(modelo: ModeloDS, C_mm: float, e: EntradaDegrau) -> ResultadoModelo:
    """Dimensiona o degrau com as barras do ``modelo``; vão = L, biapoiado nas chapas laterais."""
    mat = MATERIAIS[e.material]
    p, s, t_b, h_b = modelo.p_mm, modelo.s_mm, modelo.t_b_mm, float(modelo.h_b_mm)
    L, C = float(e.L_mm), float(C_mm)
    # n_ef = floor(b_c/p) + 1 vem de um modelo de grelha (barras portantes + barras de ligação,
    # carga de 100 × 100 mm na borda): 4,0 a 4,9 barras efetivas na malha 30 e 3,0 a 3,2 na malha
    # 41. O valor adotado fica igual ou abaixo, a favor da segurança.
    n_bb = _floor((C - t_b) / p) + 1  # barras na profundidade C
    n_ef_base = e.n_ef_imposto if e.n_ef_imposto is not None else _floor(e.b_c_mm / p) + 1
    n_ef = min(n_bb, int(n_ef_base))
    area = h_b * t_b
    inercia = t_b * h_b**3 / 12
    W = t_b * h_b**2 / 6
    Z = t_b * h_b**2 / 4
    J = h_b * t_b**3 / 3 * (1 - 0.63 * t_b / h_b)
    r_y = t_b / math.sqrt(12)
    lam = s / r_y  # Lb = passo das barras de ligação (travam o bordo comprimido)
    Mpl = Z * mat.fy
    Mr = W * mat.fy
    raiz_ja = math.sqrt(J * area)
    lam_p = 0.13 * mat.E * raiz_ja / Mpl
    lam_r = 2.00 * mat.E * raiz_ja / Mr
    Mcr = 2.00 * e.Cb * mat.E * raiz_ja / lam  # NBR 8800 Tab. G.1, seção sólida retangular
    if lam <= lam_p:
        MRk = Mpl
        regime = "plástica (λ ≤ λp)"
    elif lam <= lam_r:
        MRk = min(Mpl, e.Cb * (Mpl - (Mpl - Mr) * (lam - lam_p) / (lam_r - lam_p)))
        regime = "inelástica (λp < λ ≤ λr)"
    else:
        MRk = min(Mpl, Mcr)
        regime = "elástica (λ > λr)"
    MRd = MRk / e.gamma_a1 / 1e6  # kN·m por barra
    VRd = 0.60 * area * mat.fy / e.gamma_a1 / 1000  # kN por barra (NBR 8800 5.4.3)
    peso_grade = (h_b * t_b / p + e.lado_barra_ligacao_mm**2 / s) * mat.rho / 1000
    peso_degrau = peso_grade * K["Cat_peso"] * C * L / 1e6
    g = peso_grade * K["Cat_peso"] * GRAVIDADE / 1000
    Lm = L / 1000
    # ELU – carga distribuída em todas as barras
    w_d = (e.gamma_g * g + e.gamma_q * e.q_kN_m2) * C / 1000
    M_d = w_d * Lm**2 / 8
    u_flex_d = M_d / (n_bb * MRd)
    # ELU – concentrada no meio do vão, junto ao bocel (n_ef barras); não se soma à distribuída
    P_d = e.gamma_q * e.P_kN
    peso_barras_kN_m = e.gamma_g * g * C / 1000
    M_c = P_d * Lm / 4 + peso_barras_kN_m * Lm**2 / 8 * n_ef / n_bb
    u_flex_c = M_c / (n_ef * MRd)
    # ELU – cisalhamento (carga junto ao apoio)
    V_sd = P_d / n_ef + peso_barras_kN_m * Lm / 2 / n_bb
    u_cis = V_sd / VRd
    # ELS – flechas (valores característicos); (g + q)·C/1000 sai em N/mm
    delta_d = 5 * (g + e.q_kN_m2) * (C / 1000) * L**4 / (384 * mat.E * n_bb * inercia)
    limite_d = L / e.flecha_div
    u_fl_d = delta_d / limite_d
    delta_iso = e.P_iso_kN * 1000 * L**3 / (48 * mat.E * n_ef * inercia)
    limite_iso = min(L / e.flecha_iso_div, e.flecha_iso_max_mm)
    u_fl_i = delta_iso / limite_iso
    u_max = max(u_flex_d, u_flex_c, u_cis, u_fl_d, u_fl_i)
    atende = (
        u_max <= 1 + _EPS
        and _le(L, modelo.L_max_mm)
        and _ge(L, K["Cat_Lmin"])
        and t_b >= K["A_tbar"] - _EPS
    )
    return ResultadoModelo(
        modelo=modelo,
        C_mm=C,
        L_mm=L,
        n_bb=n_bb,
        n_ef=n_ef,
        area_mm2=area,
        inercia_mm4=inercia,
        W_mm3=W,
        Z_mm3=Z,
        J_mm4=J,
        r_y_mm=r_y,
        lam=lam,
        Mpl_Nmm=Mpl,
        Mr_Nmm=Mr,
        lam_p=lam_p,
        lam_r=lam_r,
        Mcr_Nmm=Mcr,
        MRk_Nmm=MRk,
        regime_flt=regime,
        MRd_kNm=MRd,
        VRd_kN=VRd,
        peso_grade_kg_m2=peso_grade,
        peso_degrau_kg=peso_degrau,
        g_kN_m2=g,
        w_d_kN_m=w_d,
        M_sd_d_kNm=M_d,
        u_flex_d=u_flex_d,
        P_d_kN=P_d,
        M_sd_c_kNm=M_c,
        u_flex_c=u_flex_c,
        V_sd_kN=V_sd,
        u_cis=u_cis,
        delta_d_mm=delta_d,
        limite_d_mm=limite_d,
        u_fl_d=u_fl_d,
        delta_iso_mm=delta_iso,
        limite_iso_mm=limite_iso,
        u_fl_i=u_fl_i,
        u_max=u_max,
        atende=atende,
        na_preferencia=_na_preferencia(modelo, e.malha_preferida, e.ligacao_preferida),
    )


def avaliar_catalogo(C_mm: float, e: EntradaDegrau) -> tuple[ResultadoModelo, ...]:
    """Os 64 modelos calculados com a geometria e as cargas da entrada."""
    return tuple(calcular_modelo(modelo, C_mm, e) for modelo in catalogo())


# ---------------------------------------------------------------------------------------------
# 5.7 Seleção do modelo
# ---------------------------------------------------------------------------------------------
SELECIONADO_MANUAL = "manual"
SELECIONADO_PREFERENCIA = "preferencia"
SELECIONADO_FORA_DA_PREFERENCIA = "fora_da_preferencia"
SELECIONADO_NENHUM = "nenhum"


@dataclass(frozen=True)
class Selecao:
    adotado: ResultadoModelo
    situacao: str
    mensagem: str
    avisos: tuple[str, ...]


def _preferencia_texto(e: EntradaDegrau) -> str:
    malha = "qualquer malha" if e.malha_preferida == QUALQUER else f"malha {e.malha_preferida}"
    ligacao = (
        "qualquer barra de ligação"
        if e.ligacao_preferida == QUALQUER
        else f"barras de ligação tipo {e.ligacao_preferida}"
    )
    return f"{malha}, {ligacao}"


def selecionar_modelo(tabela: tuple[ResultadoModelo, ...], e: EntradaDegrau) -> Selecao:
    """Manual; senão o mais leve que atende e está na preferência; senão o mais leve que atende;
    senão o de menor aproveitamento máximo. Desempate: ordem do catálogo."""
    indice = {r.modelo.nome: i for i, r in enumerate(tabela)}

    def mais_leve(candidatos: list[ResultadoModelo]) -> ResultadoModelo:
        return min(candidatos, key=lambda r: (round(r.peso_degrau_kg, 9), indice[r.modelo.nome]))

    if e.selecao == SELECAO_MANUAL:
        escolhido = next(r for r in tabela if r.modelo.nome == e.modelo_manual)
        return Selecao(
            escolhido,
            SELECIONADO_MANUAL,
            f"Modelo escolhido manualmente: {escolhido.modelo.nome}.",
            (),
        )
    preferidos = [r for r in tabela if r.atende and r.na_preferencia]
    if preferidos:
        escolhido = mais_leve(preferidos)
        return Selecao(
            escolhido,
            SELECIONADO_PREFERENCIA,
            "O mais leve que atende ao cálculo e à largura recomendada do catálogo, dentro da "
            f"preferência ({_preferencia_texto(e)}).",
            (),
        )
    atendem = [r for r in tabela if r.atende]
    if atendem:
        escolhido = mais_leve(atendem)
        aviso = (
            f"Nenhum modelo da preferência ({_preferencia_texto(e)}) atende; adotado o mais leve "
            "do catálogo inteiro que atende."
        )
        return Selecao(escolhido, SELECIONADO_FORA_DA_PREFERENCIA, aviso, (aviso,))
    escolhido = min(tabela, key=lambda r: (r.u_max, indice[r.modelo.nome]))
    aviso = (
        "NENHUM modelo do catálogo atende ao cálculo e à largura recomendada; adotado o de menor "
        "aproveitamento máximo, que NÃO atende."
    )
    return Selecao(escolhido, SELECIONADO_NENHUM, aviso, (aviso,))


# ---------------------------------------------------------------------------------------------
# 5.8 Reações e parafusos
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ReacoesParafusos:
    R_g_kN: float
    R_q_kN: float
    R_P_kN: float
    R_d_kN: float
    parafuso: str
    d_mm: float
    furo_padrao_mm: float
    A_b_mm2: float
    F_vRd_kN: float
    n_parafusos: int
    forca_por_parafuso_kN: float
    u_par: float


def reacoes_parafusos(r: ResultadoModelo, e: EntradaDegrau) -> ReacoesParafusos:
    """Reação do degrau em cada chapa lateral e o cortante nos parafusos A307 (rosca no corte)."""
    R_g = r.g_kN_m2 * r.C_mm * r.L_mm / 2 / 1e6
    R_q = e.q_kN_m2 * r.C_mm * r.L_mm / 2 / 1e6
    R_P = e.P_kN
    R_d = max(e.gamma_g * R_g + e.gamma_q * R_q, e.gamma_g * R_g + e.gamma_q * R_P)
    d, furo = PARAFUSOS[e.parafuso]
    A_b = math.pi * d**2 / 4
    # NBR 8800:2008 6.3.3.2, rosca no plano de corte: Fv,Rd = 0,40·Ab·fub/γa2.
    F_v = 0.40 * A_b * K["fub_A307"] / e.gamma_a2 / 1000
    por_parafuso = R_d / e.n_parafusos_por_lado
    return ReacoesParafusos(
        R_g_kN=R_g,
        R_q_kN=R_q,
        R_P_kN=R_P,
        R_d_kN=R_d,
        parafuso=e.parafuso,
        d_mm=d,
        furo_padrao_mm=furo,
        A_b_mm2=A_b,
        F_vRd_kN=F_v,
        n_parafusos=int(e.n_parafusos_por_lado),
        forca_por_parafuso_kN=por_parafuso,
        u_par=por_parafuso / F_v,
    )


# ---------------------------------------------------------------------------------------------
# 5.9 Texto para a requisição
# ---------------------------------------------------------------------------------------------
def _mm(valor: float) -> str:
    return numero_pt(valor, 1)


def especificacao(
    r: ResultadoModelo, F_mm: int, e: EntradaDegrau, quantidade: int, furo_padrao_mm: float
) -> str:
    """Linha de requisição do degrau (nota 1 do catálogo), com o furo conforme o parafuso."""
    m = r.modelo
    if furo_padrao_mm <= K["Cat_furo"] + _EPS:
        furo = '9/16" x 25 mm (padrão)'
    else:
        furo = f'11/16" x 25 mm (especial, p/ parafuso {e.parafuso})'
    xadrez = "chapa xadrez no bocel" if e.chapa_xadrez else "sem chapa xadrez no bocel"
    return (
        f"Degrau Selmec {m.nome} – malha {_mm(m.p_mm)} x {_mm(m.s_mm)} mm – barra portante "
        f"{m.h_b_mm} x {numero_pt_fixo(m.t_b_mm)} mm – C = {_mm(r.C_mm)} mm × L = {_mm(r.L_mm)} mm – "
        f"{e.material} – {ACABAMENTOS[e.acabamento]} – superfície {SUPERFICIES[e.superficie].lower()} – "
        f"{xadrez} – furos oblongos {furo} a F = {F_mm} mm – qtd. {quantidade}"
    )


# ---------------------------------------------------------------------------------------------
# Resultado completo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Geometria:
    faixa: FaixaEspelho
    n: int
    h_mm: float
    b_mm: float
    blondel_mm: float
    alfa_graus: float
    C_mm: float
    F_mm: int
    r_mm: float
    C_na_serie: bool


@dataclass(frozen=True)
class ResultadoEscada:
    entrada: EntradaDegrau
    material: Material
    geometria: Geometria
    lances: Lances
    larguras: Larguras
    tabela_modelos: tuple[ResultadoModelo, ...]
    selecao: Selecao
    reacoes: ReacoesParafusos
    verificacoes: tuple[VerificacaoDegrau, ...]
    especificacao: str
    peso_unitario_kg: float
    peso_total_kg: float
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def adotado(self) -> ResultadoModelo:
        return self.selecao.adotado

    @property
    def status(self) -> str:
        return status_geral(self.verificacoes)

    @property
    def contagem(self) -> dict[str, int]:
        return contagem_status(self.verificacoes)

    @property
    def aproveitamento_maximo(self) -> float:
        valores = [
            v.aproveitamento
            for v in self.verificacoes
            if v.tipo == "resistencia" and v.aproveitamento is not None
        ]
        return max(valores) if valores else 0.0


def contagem_status(
    verificacoes: Sequence[Verificacao],
) -> dict[str, int]:
    contagem = {"OK": 0, "NÃO OK": 0, "ALERTA": 0, "N/A": 0, "INFO": 0}
    for v in verificacoes:
        contagem[v.status] = contagem.get(v.status, 0) + 1
    return contagem


def texto_da_contagem(contagem: dict[str, int]) -> str:
    """``35 OK · 0 NÃO OK · 2 ALERTA · 0 N/A`` (as linhas INFO não entram na conta)."""
    return (
        f"{contagem['OK']} OK · {contagem['NÃO OK']} NÃO OK · "
        f"{contagem['ALERTA']} ALERTA · {contagem['N/A']} N/A"
    )


# ---------------------------------------------------------------------------------------------
# 6. As 38 verificações
# ---------------------------------------------------------------------------------------------
def _status(atende: bool, *, alerta: bool = False) -> str:
    return "OK" if atende else ("ALERTA" if alerta else "NÃO OK")


def _razao(solicitante: float | None, resistente: float | None) -> float | None:
    if solicitante is None or resistente is None or not resistente > 0:
        return None
    return solicitante / resistente


def _linha(
    nome: str,
    referencia: str,
    status: str,
    texto: str,
    *,
    unidade: str = "—",
    valor: float | None = None,
    limite: float | None = None,
    minimo: bool = False,
) -> VerificacaoDegrau:
    """Linha de limite (só OK/NÃO OK, sem aproveitamento: não entra no máximo).

    ``valor`` é o adotado e ``limite`` o exigido. Nas colunas "solicitante" e "resistente" do
    registro o menor vem primeiro quando a linha passa (mínimos: exigido, adotado; máximos:
    adotado, limite). Faixas com dois limites mostram só o adotado, e a faixa vai no texto.
    """
    if limite is None:
        solicitante, resistente = None, valor
    elif minimo:
        solicitante, resistente = limite, valor
    else:
        solicitante, resistente = valor, limite
    return VerificacaoDegrau(
        nome=nome,
        solicitante=solicitante,
        resistente=resistente,
        unidade=unidade,
        referencia=referencia,
        formula=texto,
        status=status,
        tipo="limite",
        valor=valor,
        limite=limite,
    )


def _nao_se_aplica(nome: str, referencia: str, motivo: str) -> VerificacaoDegrau:
    return VerificacaoDegrau(nome, None, None, "—", referencia, motivo, status="N/A", tipo="limite")


def _uso(
    nome: str,
    referencia: str,
    solicitante: float,
    resistente: float,
    unidade: str,
    texto: str,
) -> VerificacaoDegrau:
    razao = _razao(solicitante, resistente)
    atende = razao is not None and razao <= 1 + _EPS
    return VerificacaoDegrau(
        nome=nome,
        solicitante=solicitante,
        resistente=resistente,
        unidade=unidade,
        referencia=referencia,
        formula=texto,
        status="OK" if atende else "NÃO OK",
        aproveitamento=math.inf if razao is None else razao,
        tipo="resistencia",
        valor=solicitante,
        limite=resistente,
    )


def montar_verificacoes(
    e: EntradaDegrau,
    g: Geometria,
    ln: Lances,
    lg: Larguras,
    sel: Selecao,
    tabela: tuple[ResultadoModelo, ...],
    rp: ReacoesParafusos,
) -> list[VerificacaoDegrau]:
    """As 38 verificações, na ordem da especificação (a posição na lista é o número do item)."""
    r = sel.adotado
    m = r.modelo
    mat = MATERIAIS[e.material]
    nr22 = e.enquadramento == NR22
    ce = e.espelho_fechado
    nr12se = not nr22 and not ce
    f = g.faixa
    h, b, C, alfa = g.h_mm, g.b_mm, g.C_mm, g.alfa_graus
    L = e.L_mm
    linhas: list[VerificacaoDegrau] = []

    # ------------------------------------------------------------------ geometria
    # 1. Espelho – faixa legal
    if nr22:
        ref1 = "NR-22 22.10.1.1 a)"
    elif ce:
        ref1 = "NR-12 Anexo III 12 d)"
    else:
        ref1 = "NR-12 Anexo III 11 d)"
    ok1 = _ge(h, f.hL_min) and _le(h, f.hL_max)
    if f.hL_min > 0:
        linhas.append(
            _linha(
                "Espelho h – faixa legal",
                ref1,
                _status(ok1),
                f"{numero_pt(f.hL_min, 0)} ≤ h = {numero_pt(h)} ≤ {numero_pt(f.hL_max, 0)} mm",
                unidade="mm",
                valor=h,
            )
        )
    else:
        linhas.append(
            _linha(
                "Espelho h – faixa legal",
                ref1,
                _status(ok1),
                f"h = {numero_pt(h)} ≤ {numero_pt(f.hL_max, 0)} mm",
                unidade="mm",
                valor=h,
                limite=f.hL_max,
            )
        )
    # 2. Espelho – Anglo 10.2
    ok2 = _ge(h, K["A_hmin"]) and _le(h, K["A_hmax"])
    obs2 = f"{numero_pt(K['A_hmin'], 0)} ≤ h = {numero_pt(h)} ≤ {numero_pt(K['A_hmax'], 0)} mm"
    if not ok2:
        if f.nivel == 3:
            obs2 += (
                ". Sem interseção com a faixa legal: prevalece a NR (Anglo 3.1). Registrar "
                "consulta técnica (PRO.BRA.DPR.017)."
            )
        else:
            obs2 += ". Fora da faixa do Critério Anglo."
    linhas.append(
        _linha(
            "Espelho h – Anglo 10.2",
            "Anglo 10.2",
            _status(ok2, alerta=f.nivel == 3),
            obs2,
            unidade="mm",
            valor=h,
        )
    )
    # 3. Blondel
    bl = g.blondel_mm
    ok3 = _ge(bl, K["A_bl_min"]) and _le(bl, K["A_bl_max"])
    linhas.append(
        _linha(
            "Blondel 2h + b – Anglo 10.2",
            "Anglo 10.2",
            _status(ok3),
            f"{numero_pt(K['A_bl_min'], 0)} ≤ 2·{numero_pt(h)} + {numero_pt(b)} = {numero_pt(bl)} ≤ "
            f"{numero_pt(K['A_bl_max'], 0)} mm",
            unidade="mm",
            valor=bl,
        )
    )
    # 4. g + 2h – NR-12 11 g)
    if nr12se:
        ok4 = _ge(bl, K["N12_bl_min"]) and _le(bl, K["N12_bl_max"])
        linhas.append(
            _linha(
                "g + 2h – NR-12 11 g)",
                "NR-12 Anexo III 11 g)",
                _status(ok4),
                f"{numero_pt(K['N12_bl_min'], 0)} ≤ {numero_pt(b)} + 2·{numero_pt(h)} = {numero_pt(bl)} ≤ "
                f"{numero_pt(K['N12_bl_max'], 0)} mm",
                unidade="mm",
                valor=bl,
            )
        )
    else:
        linhas.append(
            _nao_se_aplica(
                "g + 2h – NR-12 11 g)",
                "NR-12 Anexo III 11 g)",
                "Vale só para NR-12 com degrau sem espelho.",
            )
        )
    # 5. Profundidade livre g = b
    if nr22:
        linhas.append(
            _nao_se_aplica(
                "Profundidade livre g = b – NR-12 11 b)/12 b)",
                "NR-12 Anexo III 11 b) / 12 b)",
                "Vale só para o enquadramento NR-12.",
            )
        )
    else:
        gmin = K["N12CE_gmin"] if ce else K["N12_gmin"]
        linhas.append(
            _linha(
                "Profundidade livre g = b – NR-12 11 b)/12 b)",
                "NR-12 Anexo III 12 b)" if ce else "NR-12 Anexo III 11 b)",
                _status(_ge(b, gmin)),
                f"g = b = {numero_pt(b)} ≥ {numero_pt(gmin, 0)} mm",
                unidade="mm",
                valor=b,
                limite=gmin,
                minimo=True,
            )
        )
    # 6. Projeção r
    if nr12se:
        linhas.append(
            _linha(
                "Projeção r = C − b – NR-12 11 f)",
                "NR-12 Anexo III 11 f)",
                _status(_ge(g.r_mm, 0)),
                f"r = {numero_pt(C)} − {numero_pt(b)} = {numero_pt(g.r_mm)} ≥ 0 mm",
                unidade="mm",
                valor=g.r_mm,
                limite=0.0,
                minimo=True,
            )
        )
    else:
        linhas.append(
            _nao_se_aplica(
                "Projeção r = C − b – NR-12 11 f)",
                "NR-12 Anexo III 11 f)",
                "Vale só para NR-12 com degrau sem espelho.",
            )
        )
    # 7. C ≥ b + 20
    linhas.append(
        _linha(
            "Profundidade C ≥ b + 20 – Anglo 10.2",
            "Anglo 10.2",
            _status(_ge(C, b + K["A_sobrep"])),
            f"C = {numero_pt(C)} ≥ {numero_pt(b)} + {numero_pt(K['A_sobrep'], 0)} = {numero_pt(b + K['A_sobrep'])} mm",
            unidade="mm",
            valor=C,
            limite=b + K["A_sobrep"],
            minimo=True,
        )
    )
    # 8. C entre 175 e 300
    ok8 = _ge(C, K["Cat_Cmin"]) and _le(C, K["Cat_Cmax"])
    obs8 = f"{numero_pt(K['Cat_Cmin'], 0)} ≤ C = {numero_pt(C)} ≤ {numero_pt(K['Cat_Cmax'], 0)} mm"
    if not ok8:
        obs8 += (
            ". Para este desnível não há nº de espelhos com 175 ≤ h ≤ 180 mm. Alternativas: "
            "ajustar a cota, impor n (aceitando desvio), degrau especial (fabricante) ou "
            "consulta técnica Anglo."
        )
    linhas.append(
        _linha(
            "Profundidade C entre 175 e 300 mm – Selmec nota 2",
            "Selmec, nota 2",
            _status(ok8),
            obs8,
            unidade="mm",
            valor=C,
        )
    )
    # 9. C da série padrão
    linhas.append(
        _linha(
            "C da série padrão (175, 200, … 300)",
            "Selmec, tabela C × F",
            _status(g.C_na_serie, alerta=True),
            (
                f"C = {numero_pt(C)} mm está na série; F = {g.F_mm} mm."
                if g.C_na_serie
                else f"C = {numero_pt(C)} mm fora da série: confirmar a furação F ({g.F_mm} mm) com o "
                "fabricante."
            ),
            unidade="mm",
            valor=C,
        )
    )
    # 10. Inclinação α – faixa
    if nr22:
        a_min, a_max, ref10 = K["N22_amin"], K["N22_amax"], "NR-22 22.10.1.1"
    else:
        a_min, a_max, ref10 = K["ISO_amin"], K["ISO_amax"], "NR-12 Anexo III item 2 / Fig. 1"
    ok10 = alfa > a_min + _EPS and alfa < a_max - _EPS
    linhas.append(
        _linha(
            "Inclinação α – faixa legal",
            ref10,
            _status(ok10),
            f"{numero_pt(a_min, 0)}° < α = {numero_pt(alfa, 3)}° < {numero_pt(a_max, 0)}°",
            unidade="°",
            valor=alfa,
        )
    )
    # 11. Inclinação preferencial
    ok11 = alfa >= K["ISO_pmin"] - _EPS and alfa <= K["ISO_pmax"] + _EPS
    linhas.append(
        _linha(
            "Inclinação preferencial 30° a 38°",
            "ISO 14122-3",
            _status(ok11, alerta=True),
            f"{numero_pt(K['ISO_pmin'], 0)}° ≤ α = {numero_pt(alfa, 3)}° ≤ {numero_pt(K['ISO_pmax'], 0)}°"
            + ("" if ok11 else ". Recomendação, não exigência."),
            unidade="°",
            valor=alfa,
        )
    )
    # 12. Altura do lance maior (contra o limite LEGAL: a altura imposta é meta de projeto)
    ref12 = (
        "NR-22 22.10.1.1 b)"
        if nr22
        else ("NR-12 Anexo III 12 e)" if ce else "NR-12 Anexo III 11 e)")
    )
    ok12 = _le(ln.altura_lance_maior_mm, ln.altura_max_legal_mm)
    obs12 = (
        f"{ln.k} espelhos × {numero_pt(h)} = {numero_pt(ln.altura_lance_maior_mm)} ≤ "
        f"{numero_pt(ln.altura_max_legal_mm, 0)} mm"
    )
    if ln.altura_max_lance_mm < ln.altura_max_legal_mm - TOL_MM:
        obs12 += f" (lances divididos para no máximo {numero_pt(ln.altura_max_lance_mm, 0)} mm)"
    linhas.append(
        _linha(
            "Altura do lance maior ≤ altura máxima por lance",
            ref12,
            _status(ok12),
            obs12,
            unidade="mm",
            valor=ln.altura_lance_maior_mm,
            limite=ln.altura_max_legal_mm,
        )
    )
    # 13. Lances uniformes
    uniforme = ln.k == ln.k_min
    ref13 = (
        "NR-22 22.10.1 e)" if nr22 else ("NR-12 Anexo III 12 c)" if ce else "NR-12 Anexo III 11 c)")
    )
    linhas.append(
        _linha(
            "Espelhos e lances uniformes",
            ref13,
            _status(uniforme, alerta=True),
            (
                f"{ln.texto}; espelhos todos iguais a {numero_pt(h)} mm"
                if uniforme
                else f"{ln.texto}. Espelhos iguais, mas lances com nº diferente de espelhos."
            ),
        )
    )
    # 14. Largura útil ≥ mínimo legal
    ref14 = "NR-22 22.9.3" if nr22 else "NR-12 Anexo III 11 a) / 11.1"
    linhas.append(
        _linha(
            "Largura útil ≥ mínimo legal",
            ref14,
            _status(_ge(lg.util_mm, lg.minima_legal_mm)),
            f"largura útil = {numero_pt(L)} − {numero_pt(e.reducao_largura_mm, 0)} = {numero_pt(lg.util_mm)} ≥ "
            f"{numero_pt(lg.minima_legal_mm, 0)} mm",
            unidade="mm",
            valor=lg.util_mm,
            limite=lg.minima_legal_mm,
            minimo=True,
        )
    )
    # 15. Largura útil ≥ mínimo Anglo
    obs15 = f"largura útil = {numero_pt(lg.util_mm)} ≥ {numero_pt(lg.minima_anglo_mm, 0)} mm"
    if e.uso == USO_PERMANENTE:
        obs15 += ". Escada de emergência: NBR 9077 / IT do Corpo de Bombeiros (Anglo 10.3)."
    linhas.append(
        _linha(
            "Largura útil ≥ mínimo Anglo",
            "Anglo 10.2",
            _status(_ge(lg.util_mm, lg.minima_anglo_mm)),
            obs15,
            unidade="mm",
            valor=lg.util_mm,
            limite=lg.minima_anglo_mm,
            minimo=True,
        )
    )
    # 16. Patamar
    if ln.n_lances == 1:
        linhas.append(
            _nao_se_aplica(
                "Patamar intermediário ≥ 600 mm",
                "NR-22 22.9.3 / NR-12 Anexo III 11 e)",
                "Escada de um só lance, sem patamar intermediário.",
            )
        )
    else:
        linhas.append(
            _linha(
                "Patamar intermediário ≥ 600 mm",
                "NR-22 22.9.3" if nr22 else "NR-12 Anexo III 11 e)",
                _status(_ge(e.patamar_mm, K["pat_min"])),
                f"patamar = {numero_pt(e.patamar_mm, 0)} ≥ {numero_pt(K['pat_min'], 0)} mm",
                unidade="mm",
                valor=e.patamar_mm,
                limite=K["pat_min"],
                minimo=True,
            )
        )

    # ------------------------------------------------------------------ degrau
    # 17. Modelo adotado
    linhas.append(
        VerificacaoDegrau(
            f"Modelo adotado: {m.nome}",
            None,
            None,
            "—",
            "Selmec, catálogo Degraus (DS)",
            sel.mensagem,
            status="INFO",
            tipo="informativo",
        )
    )
    # 18. L entre 500 e 1500
    ok18 = _ge(L, K["Cat_Lmin"]) and _le(L, K["Cat_Lmax"])
    linhas.append(
        _linha(
            "Comprimento L entre 500 e 1500 mm – Selmec nota 2",
            "Selmec, nota 2",
            _status(ok18),
            f"{numero_pt(K['Cat_Lmin'], 0)} ≤ L = {numero_pt(L)} ≤ {numero_pt(K['Cat_Lmax'], 0)} mm",
            unidade="mm",
            valor=L,
        )
    )
    # 19. L ≤ L máx recomendado
    linhas.append(
        _linha(
            "L ≤ L máx recomendado do modelo",
            "Selmec, dimensões recomendadas",
            _status(_le(L, m.L_max_mm)),
            f"L = {numero_pt(L)} ≤ {m.L_max_mm} mm ({m.nome})",
            unidade="mm",
            valor=L,
            limite=m.L_max_mm,
        )
    )
    # 20. t_b ≥ 2,00
    linhas.append(
        _linha(
            "Espessura da barra portante t ≥ 2,00 mm",
            "Anglo 8.8",
            _status(m.t_b_mm >= K["A_tbar"] - _EPS),
            f"t = {numero_pt_fixo(m.t_b_mm)} ≥ {numero_pt_fixo(K['A_tbar'])} mm",
            unidade="mm",
            valor=m.t_b_mm,
            limite=K["A_tbar"],
            minimo=True,
        )
    )
    # 21–25. Resistência e serviço
    linhas.append(
        _uso(
            "Flexão – carga distribuída (ELU)",
            "NBR 8800:2008 5.4.2 / Anexo G; Anglo Tab. 2",
            r.M_sd_d_kNm,
            r.n_bb * r.MRd_kNm,
            "kN·m",
            f"M_Sd = w·L²/8 = {numero_pt(r.w_d_kN_m, 3)}·{numero_pt(L / 1000, 3)}²/8 = {numero_pt(r.M_sd_d_kNm, 4)} kN·m; "
            f"{r.n_bb} barras × M_Rd = {numero_pt(r.MRd_kNm, 4)} kN·m",
        )
    )
    linhas.append(
        _uso(
            "Flexão – carga concentrada junto ao bocel (ELU)",
            "NBR 6120 (degraus isolados); NBR 8800:2008 5.4.2",
            r.M_sd_c_kNm,
            r.n_ef * r.MRd_kNm,
            "kN·m",
            f"P = {numero_pt(e.P_kN, 2)} kN sobre n_ef = {r.n_ef} barras (largura b_c = "
            f"{numero_pt(e.b_c_mm, 0)} mm); M_Sd = {numero_pt(r.M_sd_c_kNm, 4)} kN·m",
        )
    )
    linhas.append(
        _uso(
            "Cisalhamento por barra (ELU)",
            "NBR 8800:2008 5.4.3",
            r.V_sd_kN,
            r.VRd_kN,
            "kN",
            f"V_Sd = {numero_pt(r.V_sd_kN, 3)} kN; V_Rd = 0,60·A·fy/γa1 = {numero_pt(r.VRd_kN, 3)} kN",
        )
    )
    linhas.append(
        _uso(
            f"Flecha – carga distribuída (L/{numero_pt(e.flecha_div, 0)})",
            "Anglo Tab. 3",
            r.delta_d_mm,
            r.limite_d_mm,
            "mm",
            f"δ = {numero_pt(r.delta_d_mm, 3)} mm; limite L/{numero_pt(e.flecha_div, 0)} = "
            f"{numero_pt(r.limite_d_mm, 3)} mm",
        )
    )
    linhas.append(
        _uso(
            "Flecha – carga concentrada ISO (ELS)",
            "ISO 14122-3 4.7.1",
            r.delta_iso_mm,
            r.limite_iso_mm,
            "mm",
            f"δ = {numero_pt(r.delta_iso_mm, 3)} mm sob {numero_pt(e.P_iso_kN, 2)} kN; limite "
            f"min(L/{numero_pt(e.flecha_iso_div, 0)}; {numero_pt(e.flecha_iso_max_mm, 1)}) = "
            f"{numero_pt(r.limite_iso_mm, 3)} mm",
        )
    )
    # 26. Controle interno
    da_tabela = next(x for x in tabela if x.modelo.nome == m.nome)
    diferenca = abs(da_tabela.u_max - r.u_max)
    linhas.append(
        _linha(
            "Controle interno: u máx do adotado = u máx da tabela dos 64 modelos",
            "Conferência interna",
            _status(diferenca < 1e-4),
            f"u máx = {numero_pt(r.u_max, 4)}; tabela = {numero_pt(da_tabela.u_max, 4)}; diferença "
            f"{diferenca:.1e}",
            valor=r.u_max,
            limite=da_tabela.u_max,
        )
    )
    # 27. Superfície antiderrapante
    ref27 = "NR-22 22.10.1.1 d); NR-12 Anexo III 5 b); Anglo 8.6"
    serrilhada = e.superficie == SUPERFICIE_SERRILHADA
    linhas.append(
        _linha(
            "Superfície antiderrapante",
            ref27,
            _status(serrilhada, alerta=True),
            "Superfície serrilhada."
            if serrilhada
            else "Superfície lisa: não é antiderrapante; usar serrilhada ou outro tratamento.",
        )
    )
    # 28. Acabamento
    inox = e.material != MATERIAL_PADRAO
    if e.acabamento == ACABAMENTO_GALVANIZADO:
        s28 = _status(not inox, alerta=True)
        t28 = (
            "Galvanizado a fogo sobre aço-carbono."
            if not inox
            else "Galvanização não se aplica a inox: usar passivação."
        )
    elif e.acabamento == ACABAMENTO_PASSIVADO:
        s28 = _status(inox)
        t28 = (
            "Passivado sobre aço inox."
            if inox
            else "Passivação só serve ao inox: o aço-carbono ASTM A36 precisa de galvanização."
        )
    else:
        s28 = "NÃO OK"
        t28 = "Sem proteção: o Critério Anglo exige galvanização a fogo ou passivação."
    linhas.append(_linha("Acabamento", "Anglo 4.5, nota 2", s28, t28))
    # 29. Material
    linhas.append(
        _linha(
            "Material",
            "Anglo 4.5 Tab. 1 (ASTM A36); NBR 16696",
            _status(not inox, alerta=True),
            f"{mat.nome}: fy = {numero_pt(mat.fy, 0)} MPa, fu = {numero_pt(mat.fu, 0)} MPa."
            if not inox
            else f"{mat.nome}: aço especial, requer aprovação Anglo; a NBR 8800 não cobre inox "
            f"(fy = {numero_pt(mat.fy, 0)} MPa, indicativo).",
        )
    )

    # ------------------------------------------------------------------ fixação
    # 30. Parafuso ≥ 5/8"
    d = rp.d_mm
    linhas.append(
        _linha(
            'Parafuso A307 ≥ 5/8"',
            "Anglo 8.8",
            _status(d >= K["A_par_min"] - _EPS),
            f"d = {numero_pt(d, 3)} mm ({rp.parafuso}) ≥ {numero_pt(K['A_par_min'], 3)} mm",
            unidade="mm",
            valor=d,
            limite=K["A_par_min"],
            minimo=True,
        )
    )
    # 31. Furo compatível
    furo_ok = rp.furo_padrao_mm <= K["Cat_furo"] + _EPS
    linhas.append(
        _linha(
            "Furo do catálogo compatível com o parafuso",
            'Selmec (furo 9/16" × 25 mm); Anglo 8.8',
            _status(furo_ok, alerta=True),
            (
                f"Furo-padrão do parafuso {rp.parafuso} = {numero_pt(rp.furo_padrao_mm, 4)} mm ≤ "
                f"{numero_pt(K['Cat_furo'], 4)} mm."
                if furo_ok
                else f"Furo-padrão do parafuso {rp.parafuso} = {numero_pt(rp.furo_padrao_mm, 4)} mm > "
                f'{numero_pt(K["Cat_furo"], 4)} mm. Especificar ao fabricante furo oblongo 11/16" × 25 '
                f"mm para parafuso {rp.parafuso}."
            ),
            unidade="mm",
            valor=rp.furo_padrao_mm,
            limite=K["Cat_furo"],
        )
    )
    # 32. Nº de parafusos
    linhas.append(
        _linha(
            "Nº de parafusos por lado ≥ 2",
            "Anglo 9.1",
            _status(rp.n_parafusos >= K["A_npar_min"]),
            f"{rp.n_parafusos} parafuso(s) por chapa lateral",
            valor=float(rp.n_parafusos),
            limite=K["A_npar_min"],
            minimo=True,
        )
    )
    # 33. Cortante no parafuso
    linhas.append(
        _uso(
            "Cortante no parafuso A307 (ELU)",
            "NBR 8800:2008 6.3.3.2",
            rp.forca_por_parafuso_kN,
            rp.F_vRd_kN,
            "kN",
            f"R_d = {numero_pt(rp.R_d_kN, 4)} kN por chapa lateral (reação do degrau) ÷ {rp.n_parafusos} "
            f"parafuso(s); F_v,Rd = 0,40·A_b·f_ub/γa2 = {numero_pt(rp.F_vRd_kN, 3)} kN",
        )
    )

    # ------------------------------------------------------------------ guarda-corpo
    # 34. Travessão superior
    ref34 = "NR-22 22.6.5 c); NR-12 Anexo III 7 c)"
    linhas.append(
        _linha(
            "Guarda-corpo – travessão superior entre 1100 e 1200 mm",
            ref34,
            _status(_ge(e.gc_superior_mm, K["gc_min"]) and _le(e.gc_superior_mm, K["gc_max"])),
            f"{numero_pt(K['gc_min'], 0)} ≤ {numero_pt(e.gc_superior_mm, 0)} ≤ {numero_pt(K['gc_max'], 0)} mm",
            unidade="mm",
            valor=e.gc_superior_mm,
        )
    )
    # 35. Guarda-corpo Anglo
    ok35 = _ge(e.gc_superior_mm, K["A_gc"])
    linhas.append(
        _linha(
            "Guarda-corpo ≥ 1300 mm – Anglo 10.2",
            "Anglo 10.2",
            _status(ok35, alerta=True),
            f"travessão superior = {numero_pt(e.gc_superior_mm, 0)} ≥ {numero_pt(K['A_gc'], 0)} mm"
            + (
                ""
                if ok35
                else ". Conflito: NR limita a 1200 mm e Anglo pede 1300 mm. Definir em consulta "
                "técnica."
            ),
            unidade="mm",
            valor=e.gc_superior_mm,
            limite=K["A_gc"],
            minimo=True,
        )
    )
    # 36. Travessão intermediário
    linhas.append(
        _linha(
            "Guarda-corpo – travessão intermediário a 700 mm",
            "NR-12 Anexo III 7 e); NR-22 22.6.5 e)",
            _status(abs(e.gc_intermediario_mm - K["gc_int"]) <= 0.5 + _EPS),
            f"{numero_pt(e.gc_intermediario_mm, 0)} mm (esperado {numero_pt(K['gc_int'], 0)} ± 0,5 mm)",
            unidade="mm",
            valor=e.gc_intermediario_mm,
        )
    )
    # 37. Rodapé
    linhas.append(
        _linha(
            "Guarda-corpo – rodapé ≥ 200 mm",
            "NR-12 Anexo III 7; NR-22 22.6.5",
            _status(_ge(e.gc_rodape_mm, K["gc_rod"])),
            f"rodapé = {numero_pt(e.gc_rodape_mm, 0)} ≥ {numero_pt(K['gc_rod'], 0)} mm",
            unidade="mm",
            valor=e.gc_rodape_mm,
            limite=K["gc_rod"],
            minimo=True,
        )
    )
    # 38. Espaçamento entre barras
    linhas.append(
        _linha(
            "Guarda-corpo – espaçamento entre barras ≤ 150 mm",
            "Anglo 10.2",
            _status(_le(e.gc_espacamento_mm, K["A_gc_esp"])),
            f"espaçamento = {numero_pt(e.gc_espacamento_mm, 0)} ≤ {numero_pt(K['A_gc_esp'], 0)} mm",
            unidade="mm",
            valor=e.gc_espacamento_mm,
            limite=K["A_gc_esp"],
        )
    )
    # Numera as linhas para cruzar com a especificação ("itens 31 e 35").
    return [replace(v, nome=f"{i}. {v.nome}") for i, v in enumerate(linhas, start=1)]


# ---------------------------------------------------------------------------------------------
# Cálculo completo
# ---------------------------------------------------------------------------------------------
def geometria_da_escada(e: EntradaDegrau) -> Geometria:
    faixa = faixa_espelho(e.H_mm, e.h_alvo_mm, e.enquadramento, e.espelho_fechado)
    n = escolher_n(faixa, e.n_imposto)
    h = e.H_mm / n
    b = piso_b(h, e.enquadramento, e.espelho_fechado, e.b_imposto_mm)
    if not b > 0:
        raise EntradaInvalida(
            f"O piso b resultou em {numero_pt(b)} mm (não positivo): o espelho h = {numero_pt(h)} mm é alto "
            "demais para a fórmula 2h + b. Revise o desnível, o nº de espelhos ou imponha b."
        )
    C = profundidade_C(b, e.C_imposto_mm, e.C_padronizado)
    if C <= b:
        raise EntradaInvalida(
            f"A profundidade C = {numero_pt(C)} mm precisa ser maior que o piso b = {numero_pt(b)} mm."
        )
    return Geometria(
        faixa=faixa,
        n=n,
        h_mm=h,
        b_mm=b,
        blondel_mm=2 * h + b,
        alfa_graus=math.degrees(math.atan(h / b)),
        C_mm=C,
        F_mm=furacao_F(C),
        r_mm=C - b,
        C_na_serie=c_na_serie(C),
    )


def calcular_escada(e: EntradaDegrau) -> ResultadoEscada:
    """Calcula tudo: geometria, lances, larguras, os 64 modelos, a seleção, reações e verificações.

    Levanta :class:`EntradaInvalida` quando a entrada não permite calcular (nada é corrigido).
    """
    erros = validar_entrada(e)
    if erros:
        raise EntradaInvalida(" ".join(erros))
    geo = geometria_da_escada(e)
    ln = lances(
        geo.n, geo.h_mm, geo.b_mm, e.patamar_mm, e.enquadramento, e.altura_max_lance_imposta_mm
    )
    lg = larguras(e.L_mm, e.reducao_largura_mm, e.enquadramento, ln.n_lances, e.H_mm, e.uso)
    tabela = avaliar_catalogo(geo.C_mm, e)
    sel = selecionar_modelo(tabela, e)
    # O adotado é recalculado à parte: a verificação 26 compara com a linha da tabela.
    adotado = calcular_modelo(sel.adotado.modelo, geo.C_mm, e)
    sel = replace(sel, adotado=adotado)
    rp = reacoes_parafusos(adotado, e)
    verificacoes = montar_verificacoes(e, geo, ln, lg, sel, tabela, rp)
    quantidade = ln.n_degraus_grade
    texto = especificacao(adotado, geo.F_mm, e, quantidade, rp.furo_padrao_mm)
    avisos = list(sel.avisos)
    if geo.faixa.nivel >= 3:
        avisos.append(geo.faixa.mensagem)
    return ResultadoEscada(
        entrada=e,
        material=MATERIAIS[e.material],
        geometria=geo,
        lances=ln,
        larguras=lg,
        tabela_modelos=tabela,
        selecao=sel,
        reacoes=rp,
        verificacoes=tuple(verificacoes),
        especificacao=texto,
        peso_unitario_kg=adotado.peso_degrau_kg,
        peso_total_kg=adotado.peso_degrau_kg * quantidade,
        avisos=tuple(avisos),
    )
