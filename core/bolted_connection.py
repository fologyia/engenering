"""Verificação de ligações parafusadas em estruturas de aço.

Portado sem alteração de fórmulas de ``ligacao_parafusada_ref.py`` (módulo de
referência validado). Só mudaram a tipagem, a estrutura de ``GRAUS`` (de dicionário
heterogêneo para dataclass, para o mypy) e as guardas de entrada marcadas "Guarda:".

Normas cobertas (escolha por parâmetro `norma`):

    "NBR8800_2008"  ABNT NBR 8800:2008 (vigente)
    "NBR8800_2024"  ABNT NBR 8800:2025 (vigente; o código interno vem do projeto de 2024)
    "AISC360_LRFD"  AISC 360-10/16, método LRFD (φ)
    "RCSC2004"      RCSC Specification for Structural Joints (2004), LRFD

Critérios de cliente: Anglo American — Critério de Projeto Estruturas Metálicas AA-BR-DPST-DR-0001 (item 9.1).

Validação: as funções reproduzem os exemplos do AISC Design Guide 29 (pág. 157–159 e 185–186)
com diferença ≤ 0,2% e a planilha `calculo_parafuso_revisado.xlsx` (ver tests/test_bolted_connection.py).

Unidades internas: comprimento em mm, tensão em MPa, força em N. Funções públicas devolvem kN e kN·m.
Sem dependências externas.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core.verificacao import Verificacao

KIP_KN = 4.448222  # 1 kip em kN
TF_KN = 9.80665  # 1 tf em kN
NORMAS = ("NBR8800_2008", "NBR8800_2024", "AISC360_LRFD", "RCSC2004")

# Valores da NBR 8800:2008 que o módulo de referência trouxe de memória e que foram conferidos
# no texto da norma (2026-10-17): estão certos.
CONFERIDOS_NBR8800_2008 = (
    "μ = 0,35 nas superfícies das classes A e C (6.3.4.3 a).",
    "f_ub do A325 = 825 MPa (d ≤ 25,4 mm) e 725 MPa (d > 25,4 mm) (Tabela A.3).",
    "C_t limitado a 0,90 (5.2.5 c).",
)


@dataclass(frozen=True)
class GrauParafuso:
    """Resistências de um grau de parafuso, nas duas convenções de tabela."""

    fub: dict[str, tuple[float, float]]  # NBR: (d_b ≤ 25,4 mm, d_b > 25,4 mm)
    Fnv_AISC: tuple[float, float]  # AISC J3.2: (rosca no plano, rosca fora)
    Fn_RCSC: tuple[float, float] | None  # RCSC 5.1; None quando a RCSC não cobre o grau
    protendivel: bool
    Fnt_AISC: float = 0.0  # AISC J3.2 / RCSC 5.1: resistência nominal à tração F_nt (MPa)


# ---------------------------------------------------------------------------------------------
# TABELAS
# ---------------------------------------------------------------------------------------------
# designação: (d_b mm, furo-padrão d_h mm, e_mín à borda mm, F_Tb A325 kN, F_Tb A490 kN)
#   d_h: NBR 8800:2025 Tabela 14 (= AISC 360-16; conferida na foto da norma). A 2008 tem furos
#   menores (d_b + 1,5 mm): ver dimensoes_do_furo. AISC 360-10 usa 1" → 27,0 mm (1 1/16").
#   e_mín: NBR 8800:2025 Tabela 16.   F_Tb: NBR 8800:2025 Tabela 19 (= RCSC Tabela 8.1), conferidas.
PARAFUSOS = {
    '1/2"': (12.7, 14.3, 19, 53, 67),
    '5/8"': (15.9, 17.5, 22, 85, 106),
    "M16": (16.0, 18.0, 22, 91, 114),
    '3/4"': (19.1, 20.6, 25, 125, 157),
    "M20": (20.0, 22.0, 26, 142, 178),
    "M22": (22.0, 24.0, 28, 176, 221),
    '7/8"': (22.2, 23.8, 28, 173, 217),
    "M24": (24.0, 27.0, 30, 205, 257),
    '1"': (25.4, 28.6, 32, 227, 285),
    "M27": (27.0, 30.0, 34, 267, 334),
    '1 1/8"': (28.6, 31.8, 38, 286, 358),
    "M30": (30.0, 33.0, 38, 326, 408),
    '1 1/4"': (31.8, 34.9, 41, 363, 455),
}

# f_ub (MPa) por versão da NBR: (d_b ≤ 25,4 mm, d_b > 25,4 mm)
#   NBR 8800:2008 Tabela A.3 (conferida na norma).
#   NBR 8800:2025 Tabela A.3 (ASTM F3125: resistência única; A325 830 MPa de 16 a 36 mm).
# AISC 360-10 Tabela J3.2 (SI): F_nv rosca no plano (N) / fora (X).  RCSC 2004 Tabela 5.1: F_n (N) / (X).
GRAUS = {
    "A325": GrauParafuso(
        fub={"NBR8800_2008": (825, 725), "NBR8800_2024": (830, 830)},
        Fnv_AISC=(372, 469),
        Fn_RCSC=(331, 414),
        protendivel=True,
        Fnt_AISC=620,
    ),
    "A490": GrauParafuso(
        fub={"NBR8800_2008": (1035, 1035), "NBR8800_2024": (1040, 1040)},
        Fnv_AISC=(469, 579),
        Fn_RCSC=(414, 517),
        protendivel=True,
        Fnt_AISC=780,
    ),
    "A307": GrauParafuso(
        fub={"NBR8800_2008": (415, 415), "NBR8800_2024": (415, 415)},
        Fnv_AISC=(188, 188),
        Fn_RCSC=None,
        protendivel=False,
        Fnt_AISC=310,
    ),
}

# Aços das partes ligadas (NBR 8800 Tabela A.2): (f_y, f_u) em MPa
ACOS = {"ASTM A36": (250, 400), "ASTM A572 Gr 50": (345, 450), "ASTM A588": (345, 485)}

# Coeficiente médio de atrito μ por superfície e norma
#   NBR 2024: item 6.3.4.3 (arquivo de referência).  NBR 2008: 0,35 nas classes A/C (6.3.4.3, conferido).
#   RCSC 2004 §5.4.1: A = 0,33; B = 0,50; C = 0,35; galvanizado sem tratamento não é previsto (None).
SUPERFICIES: dict[str, dict[str, float | None]] = {
    "galvanizada_sem_tratamento": {
        "NBR8800_2008": 0.20,
        "NBR8800_2024": 0.20,
        "AISC360_LRFD": None,
        "RCSC2004": None,
    },
    "classe_C_galv_escovada": {
        "NBR8800_2008": 0.35,
        "NBR8800_2024": 0.30,
        "AISC360_LRFD": 0.30,
        "RCSC2004": 0.35,
    },
    "classe_A_laminada_limpa": {
        "NBR8800_2008": 0.35,
        "NBR8800_2024": 0.30,
        "AISC360_LRFD": 0.30,
        "RCSC2004": 0.33,
    },
    "classe_B_jateada": {
        "NBR8800_2008": 0.50,
        "NBR8800_2024": 0.50,
        "AISC360_LRFD": 0.50,
        "RCSC2004": 0.50,
    },
}

# Parâmetros por norma
_P: dict[str, dict[str, float]] = {
    "NBR8800_2008": dict(alfa_N=0.40, alfa_X=0.50, g_a1=1.10, g_a2=1.35, Ct_max=0.90, folga=2.0),
    "NBR8800_2024": dict(alfa_N=0.45, alfa_X=0.56, g_a1=1.10, g_a2=1.35, Ct_max=1.00, folga=2.0),
    "AISC360_LRFD": dict(phi=0.75, phi_ty=0.90, phi_vy=1.00, Ct_max=1.00, folga=1.5875),
    "RCSC2004": dict(phi=0.75, phi_ty=0.90, phi_vy=1.00, Ct_max=1.00, folga=1.5875),
}


def _nbr(norma: str) -> bool:
    if norma not in NORMAS:
        raise ValueError(f"norma inválida: {norma}. Use uma de {NORMAS}")
    return norma.startswith("NBR")


def _fator_ruptura(norma: str) -> float:
    """1/γ_a2 (NBR) ou φ = 0,75 (AISC/RCSC)."""
    return 1 / _P[norma]["g_a2"] if _nbr(norma) else _P[norma]["phi"]


def _fator_escoamento(norma: str) -> float:
    """1/γ_a1 (NBR) ou φ = 0,90 (AISC/RCSC) — escoamento da seção bruta à tração."""
    return 1 / _P[norma]["g_a1"] if _nbr(norma) else _P[norma]["phi_ty"]


# ---------------------------------------------------------------------------------------------
# PARAFUSO
# ---------------------------------------------------------------------------------------------
def dados_parafuso(designacao: str) -> dict[str, Any]:
    db, dh, emin, ftb325, ftb490 = PARAFUSOS[designacao]
    return dict(d_b=db, d_h=dh, e_min=emin, F_Tb={"A325": ftb325, "A490": ftb490})


def area_bruta(d_b: float) -> float:
    """A_b = π d_b²/4 (mm²). NBR 6.3.2.2."""
    return math.pi * d_b**2 / 4


def fub(grau: str, d_b: float, norma: str) -> float:
    """f_ub (MPa). Para AISC/RCSC use resist_corte (trabalha com F_nv/F_n diretamente)."""
    tab = GRAUS[grau].fub["NBR8800_2008" if norma == "NBR8800_2008" else "NBR8800_2024"]
    return tab[0] if d_b <= 25.4 else tab[1]


def protensao_minima(designacao: str, grau: str) -> float:
    """F_Tb (kN) — NBR Tabela 19 / RCSC Tabela 8.1. ≈ 0,70 · f_ub · A_s (Anglo 9.1: ≥ 70% da ruptura)."""
    if not GRAUS[grau].protendivel:
        raise ValueError(f"{grau} não admite protensão (não usar em ligação por atrito).")
    return dados_parafuso(designacao)["F_Tb"][grau]


def resist_corte(
    d_b: float, grau: str, norma: str, rosca_no_plano: bool = True, n_planos: int = 1
) -> float:
    """Força resistente de cálculo ao corte, por parafuso (kN), somando os planos de corte.

    NBR 6.3.3.2:  F_v,Rd = α_v · A_b · f_ub / γ_a2   (α_v: 2008 0,40/0,50; 2024 0,45/0,56; A307 sempre o 1º)
    AISC J3.6:    φ r_n = 0,75 · F_nv · A_b
    RCSC 5.1:     φ R_n = 0,75 · F_n · A_b          (não cobre A307)
    A área é SEMPRE a bruta (A_b), mesmo com rosca no plano — o efeito da rosca está no coeficiente.
    """
    Ab = area_bruta(d_b)
    N = rosca_no_plano or grau == "A307"
    if _nbr(norma):
        alfa = _P[norma]["alfa_N"] if N else _P[norma]["alfa_X"]
        R = alfa * Ab * fub(grau, d_b, norma) / _P[norma]["g_a2"]
    elif norma == "AISC360_LRFD":
        R = 0.75 * GRAUS[grau].Fnv_AISC[0 if N else 1] * Ab
    else:
        fn_rcsc = GRAUS[grau].Fn_RCSC
        if fn_rcsc is None:
            raise ValueError("RCSC 2004 não cobre A307.")
        R = 0.75 * fn_rcsc[0 if N else 1] * Ab
    return R * n_planos / 1000


def lf_borda(e: float, d_h: float) -> float:
    """Distância livre do furo à borda, na direção da força: ℓ_f = e − d_h/2 (usa o FURO)."""
    return e - d_h / 2


def lf_entre_furos(s: float, d_h: float) -> float:
    """Distância livre entre furos, na direção da força: ℓ_f = s − d_h."""
    return s - d_h


def coeficientes_contato(
    deformacao_limitada: bool = True, furo_muito_alongado_perp: bool = False
) -> tuple[float, float]:
    """(k_1, k_2) do contato: 1,2/2,4 com a deformação do furo limitada, 1,5/3,0 sem limite e
    1,0/2,0 no furo muito alongado perpendicular à força (NBR 6.3.3.3; AISC J3.10). O cálculo e o
    texto do memorial usam esta mesma escolha."""
    if furo_muito_alongado_perp:
        return 1.0, 2.0
    return (1.2, 2.4) if deformacao_limitada else (1.5, 3.0)


def resist_contato(
    d_b: float,
    t: float,
    f_u: float,
    l_f: float | None,
    norma: str,
    deformacao_limitada: bool = True,
    furo_muito_alongado_perp: bool = False,
) -> float:
    """Pressão de contato + rasgamento, por furo, em UMA chapa (kN). NBR 6.3.3.3 / AISC J3.10 / RCSC 5.3.

    min(k_1 · ℓ_f · t · f_u ; k_2 · d_b · t · f_u) × (1/γ_a2 ou φ = 0,75)
      deformação limitada: k_1 = 1,2; k_2 = 2,4   |  não limitada: 1,5 / 3,0  |  muito alongado ⟂: 1,0 / 2,0
    t = espessura da chapa considerada (NUNCA a soma das chapas); f_u = ruptura do aço da CHAPA.
    l_f = None → não há borda/furo na direção da força (só esmagamento; ver DG29 ex. 5.8).
    """
    k1, k2 = coeficientes_contato(deformacao_limitada, furo_muito_alongado_perp)
    esmag = k2 * d_b * t * f_u
    rasg = math.inf if l_f is None else k1 * l_f * t * f_u
    return min(rasg, esmag) * _fator_ruptura(norma) / 1000


def resist_grupo_axial(
    n_lin: int, n_col: int, Fv: float, Fc_ext: float, Fc_int: float | None
) -> float:
    """Resistência do grupo = soma por furo (NBR 6.3.3.3; AISC J3.6 User Note; DG29).
    n_lin = linhas paralelas à força; n_col = parafusos por linha (na direção da força).
    Cada parafuso vale o menor entre corte e contato do seu furo."""
    R = n_lin * min(Fv, Fc_ext)
    if n_col > 1:
        if Fc_int is None:  # Guarda: sem o contato interno o grupo seria superestimado.
            raise ValueError("Fc_int é obrigatório quando n_col > 1.")
        R += n_lin * (n_col - 1) * min(Fv, Fc_int)
    return R


# ---------------------------------------------------------------------------------------------
# DESLIZAMENTO (ligação por atrito)
# ---------------------------------------------------------------------------------------------
def mu_superficie(superficie: str, norma: str) -> float | None:
    return SUPERFICIES[superficie][norma]


def resist_deslizamento(
    F_Tb: float,
    mu: float,
    norma: str,
    n_s: int = 1,
    C_e: float = 1.0,
    nivel: str = "servico",
    F_t: float = 0.0,
    gama_e: float = 1.20,
) -> float:
    """Resistência ao deslizamento por parafuso (kN).

    NBR 6.3.4.4 (serviço, furo-padrão):   F_f,Rk = 0,80 μ C_e F_Tb n_s (1 − F_t,Sk/(0,80 F_Tb))
    NBR 6.3.4.3 (ELU, furo alargado/along.): F_f,Rd = 1,13 μ C_e F_Tb n_s/γ_e (1 − F_t,Sd/(1,13 F_Tb))
    RCSC 5.4.2 (serviço):  R_s = μ D T_m N_s (1 − T/(D T_m)), D = 0,80
    RCSC 5.4.1 / AISC J3.8 (ELU, furo-padrão): φ R_n = 1,0 μ D_u h_f T_m n_s (1 − T_u/(D_u T_m)), D_u = 1,13
    Compare o valor de SERVIÇO com a força característica (combinação rara ≈ 0,70 × força de cálculo).
    """
    if mu is None:
        raise ValueError(
            "Superfície sem μ definido nesta norma (RCSC/AISC exigem ensaio para galvanizado sem tratamento)."
        )
    if _nbr(norma):
        if nivel == "servico":
            return 0.80 * mu * C_e * F_Tb * n_s * (1 - F_t / (0.80 * F_Tb))
        return 1.13 * mu * C_e * F_Tb * n_s / gama_e * (1 - F_t / (1.13 * F_Tb))
    if nivel == "servico":
        return mu * 0.80 * F_Tb * n_s * (1 - F_t / (0.80 * F_Tb))
    return 1.0 * mu * 1.13 * C_e * F_Tb * n_s * (1 - F_t / (1.13 * F_Tb))


# ---------------------------------------------------------------------------------------------
# PEÇA LIGADA: tração, shear lag e colapso por rasgamento
# ---------------------------------------------------------------------------------------------
def area_liquida(A_g: float, n_furos_secao: int, d_h: float, t: float, norma: str) -> float:
    """A_n (mm²) = A_g − n · (d_h + folga) · t. Folga: NBR 2 mm (5.2.4.1); AISC/RCSC 1/16" (B4.3)."""
    return A_g - n_furos_secao * (d_h + _P[norma]["folga"]) * t


def coef_Ct(e_c: float, l_c: float, norma: str) -> float | None:
    """C_t = 1 − e_c/ℓ_c (NBR 5.2.5 c; AISC U, Tab. D3.1 caso 2). NBR 2008 limita a 0,90 (5.2.5 c)."""
    if l_c <= 0:
        return None
    return min(_P[norma]["Ct_max"], 1 - e_c / l_c)


def resist_tracao_barra(
    A_g: float, A_n: float, C_t: float | None, f_y: float, f_u: float, norma: str
) -> float:
    """N_t,Rd (kN) = min(A_g f_y · fator_esc ; C_t A_n f_u · fator_rup). NBR 5.2.2 / AISC D2."""
    esc = A_g * f_y * _fator_escoamento(norma)
    rup = math.inf if C_t is None else C_t * A_n * f_u * _fator_ruptura(norma)
    return min(esc, rup) / 1000


def areas_bloco_central(
    e: float,
    s: float,
    g: float,
    n_lin: int,
    n_col: int,
    t: float,
    d_h: float,
    norma: str,
    d_h_tracao: float | None = None,
) -> tuple[float, float, float]:
    """Áreas do bloco entre as linhas externas (n_lin ≥ 2), 2 planos de cisalhamento (mm²).
    Para cantoneiras/peças com 1 linha e tração até a borda livre l_eh: use g = 2·l_eh (equivalente).
    d_h: o furo ao longo da força (planos de cisalhamento); d_h_tracao: atravessando a força (plano
    de tração) — diferentes só nos furos alongados; None = d_h."""
    dhl = d_h + _P[norma]["folga"]
    dht = (d_h if d_h_tracao is None else d_h_tracao) + _P[norma]["folga"]
    L = e + (n_col - 1) * s
    A_gv = 2 * L * t
    A_nv = 2 * (L - (n_col - 0.5) * dhl) * t
    A_nt = (n_lin - 1) * (g - dht) * t
    return A_gv, A_nv, A_nt


def resist_colapso_rasgamento(
    A_gv: float, A_nv: float, A_nt: float, f_y: float, f_u: float, norma: str, C_ts: float = 1.0
) -> float:
    """F_r,Rd (kN) = min(0,6 f_u A_nv + C_ts f_u A_nt ; 0,6 f_y A_gv + C_ts f_u A_nt) × (1/γ_a2 ou φ 0,75).
    NBR 6.5.6 / AISC J4.3."""
    Rn = min(0.6 * f_u * A_nv + C_ts * f_u * A_nt, 0.6 * f_y * A_gv + C_ts * f_u * A_nt)
    return Rn * _fator_ruptura(norma) / 1000


# ---------------------------------------------------------------------------------------------
# GRUPO EXCÊNTRICO (V + N + M no plano) — método elástico (Guide, Kulak et al., Cap. 13)
# ---------------------------------------------------------------------------------------------
def grade_retangular(n_lin: int, n_col: int, s: float, g: float) -> list[tuple[float, float]]:
    """Coordenadas (mm) de uma grade n_col (ao longo de x, passo s) × n_lin (ao longo de y, passo g)."""
    return [(i * s, j * g) for i in range(n_col) for j in range(n_lin)]


def grupo_excentrico_elastico(
    coords: list[tuple[float, float]], V: float, N: float = 0.0, M: float = 0.0
) -> dict[str, Any]:
    """Força em cada parafuso por superposição elástica. V em +y, N em +x (kN); M no plano (kN·m, anti-horário +).
    F_x,i = N/n − M·y_i/J ;  F_y,i = V/n + M·x_i/J ;  J = Σ(x_i² + y_i²), medido do centroide.
    Devolve dict com J (mm²), forças por parafuso e a resultante máxima (parafuso crítico).
    Conservador frente ao centro instantâneo de rotação (AISC Manual, Tab. 7-6 em diante)."""
    n = len(coords)
    xc = sum(x for x, _ in coords) / n
    yc = sum(y for _, y in coords) / n
    rel = [(x - xc, y - yc) for x, y in coords]
    J = sum(x * x + y * y for x, y in rel)
    Mm = M * 1000.0  # kN·m → kN·mm
    forcas = []
    for x, y in rel:
        fx = N / n - (Mm * y / J if J else 0.0)
        fy = V / n + (Mm * x / J if J else 0.0)
        forcas.append((fx, fy, math.hypot(fx, fy)))
    Rmax = max(f[2] for f in forcas)
    return dict(J=J, forcas=forcas, R_max=Rmax, R0=math.hypot(N / n, V / n))


def raio_circulo_equivalente(s: float, g: float) -> float:
    """Para um 2×2 com passos s e g, os parafusos ficam num círculo de diâmetro √(s² + g²)."""
    return math.hypot(s, g)


# ---------------------------------------------------------------------------------------------
# DISPOSIÇÕES CONSTRUTIVAS (NBR 6.3.7 a 6.3.12; AISC J3.3 a J3.5)
# ---------------------------------------------------------------------------------------------
def disposicoes_construtivas(
    d_b: float,
    d_h: float,
    e_min: float,
    t: float,
    e: float,
    s: float,
    g: float | None = None,
    e_v: float | None = None,
    pega: float | None = None,
    patinavel_sem_pintura: bool = False,
    protendido: bool = True,
) -> list[Verificacao]:
    out: list[Verificacao] = []
    passos = [p for p in (s, g) if p]
    if passos:
        pmin = min(passos)
        ok = pmin >= 2.7 * d_b and (pmin - d_h) >= d_b
        st = ("OK" if pmin >= 3 * d_b else "ALERTA") if ok else "NÃO OK"
        out.append(
            Verificacao(
                "Espaçamento mínimo (≥ 2,7 d_b, pref. 3 d_b; livre ≥ d_b)",
                None,
                None,
                "mm",
                "NBR 6.3.9 / AISC J3.3",
                f"min(s,g) = {pmin:.1f}; 3 d_b = {3 * d_b:.1f}",
                status=st,
            )
        )
        smax = min(14 * t, 180) if patinavel_sem_pintura else min(24 * t, 300)
        out.append(
            Verificacao(
                "Espaçamento máximo",
                max(passos),
                smax,
                "mm",
                "NBR 6.3.10 / AISC J3.5",
                "14t ≤ 180 (patinável) ou 24t ≤ 300",
            )
        )
    emax = min(12 * t, 150)
    for nome, dist in (("na direção da força", e), ("vertical", e_v)):
        if dist is None:
            continue
        out.append(
            Verificacao(
                f"Distância mínima à borda ({nome})",
                e_min,
                dist,
                "mm",
                "NBR 6.3.11 Tab. 16 / AISC J3.4",
                "e ≥ e_mín",
            )
        )
        out.append(
            Verificacao(
                f"Distância máxima à borda ({nome})",
                dist,
                emax,
                "mm",
                "NBR 6.3.12 / AISC J3.5",
                "e ≤ 12t ≤ 150 mm",
            )
        )
    if pega is not None and not protendido:
        st = "OK" if pega <= 5 * d_b else "ALERTA"
        out.append(
            Verificacao(
                "Pega longa (Σt ≤ 5 d_b)",
                pega,
                5 * d_b,
                "mm",
                "NBR 6.3.7",
                "Acima: reduzir F_v,Rd 1% a cada 1,5 mm",
                status=st,
            )
        )
    return out


# ---------------------------------------------------------------------------------------------
# CRITÉRIO ANGLO AA-BR-DPST-DR-0001 (item 9.1 e Tabela 1)
# ---------------------------------------------------------------------------------------------
def criterio_anglo(
    n_parafusos: int,
    grau: str,
    d_b: float,
    ligacao_principal: bool = True,
    revestimento: str = "galvanizado_fogo",
    regra_75: bool = False,
    R_ligacao_tracao: float | None = None,
    N_t_Rd_peca: float | None = None,
    componentes: Sequence[tuple[str, float]] = (),
) -> list[Verificacao]:
    """Critério Anglo (item 9.1). A regra dos 75% vale só para a peça de treliça/contraventamento
    dimensionada pela esbeltez ou sem esforço indicado; ``componentes`` são as parcelas da
    capacidade da ligação (nome, kN) — R_ligacao_tracao é a menor delas."""
    out: list[Verificacao] = [
        Verificacao(
            "Mínimo de 2 parafusos",
            None,
            None,
            "—",
            "Anglo 9.1",
            f"n = {n_parafusos}",
            status="OK" if n_parafusos >= 2 else "NÃO OK",
        )
    ]
    if grau == "A307":
        st, txt = (
            ("OK", "A307 em ligação secundária")
            if not ligacao_principal
            else ("NÃO OK", "A307 só em secundárias")
        )
    elif grau == "A490":
        st = "NÃO OK" if revestimento == "galvanizado_fogo" else "OK"
        txt = "A490 só com Zn/Al (ASTM F1136/Dacromet); nunca galvanizado a fogo (NBR Anexo A)"
    else:
        st, txt = "OK", "A325 (F3125), galvanizado a fogo nas ligações principais"
    out.append(
        Verificacao(
            "Grau e revestimento do parafuso", None, None, "—", "Anglo 9.1 e Tab. 1", txt, status=st
        )
    )
    out.append(
        Verificacao(
            'Diâmetro ≤ 1" (preferência)',
            None,
            None,
            "mm",
            "Anglo 9.1",
            f"d_b = {d_b}",
            status="OK" if d_b <= 25.4 else "ALERTA",
        )
    )
    ref_75 = "Anglo 9.1 (peça por esbeltez ou sem esforço indicado)"
    condicao = (
        "Vale só para a peça de treliça/contraventamento dimensionada pela esbeltez ou sem "
        "esforço indicado."
    )
    if regra_75 and (N_t_Rd_peca is None or R_ligacao_tracao is None):
        # Guarda: sem a resistência da peça (A_g, e_c) a regra não é calculável — não omitir.
        out.append(
            Verificacao(
                "Capacidade ≥ 75% da tração da peça e ≥ 3 tf",
                None,
                None,
                "kN",
                ref_75,
                f"{condicao} Informe A_g e e_c da peça para calcular a regra dos 75%.",
                "ALERTA",
            )
        )
    elif regra_75:
        assert N_t_Rd_peca is not None and R_ligacao_tracao is not None
        req = max(0.75 * N_t_Rd_peca, 3 * TF_KN)
        parcelas = (
            "; ".join(f"{nome} = {valor:.2f}" for nome, valor in componentes)
            if componentes
            else f"grupo e colapso por rasgamento = {R_ligacao_tracao:.2f}"
        )
        out.append(
            Verificacao(
                "Capacidade ≥ 75% da tração da peça e ≥ 3 tf",
                req,
                R_ligacao_tracao,
                "kN",
                ref_75,
                f"{condicao} R_lig = menor entre: {parcelas} → R_lig = {R_ligacao_tracao:.2f} kN "
                f"≥ máx(0,75·N_t,Rd = 0,75·{N_t_Rd_peca:.2f} = {0.75 * N_t_Rd_peca:.2f}; "
                f"3 tf = {3 * TF_KN:.2f}) = {req:.2f} kN",
            )
        )
    return out


# ---------------------------------------------------------------------------------------------
# TRAÇÃO NO PARAFUSO E INTERAÇÃO COM O CORTE (NBR 6.3.2.2, 6.3.3.1 e 6.3.3.4; AISC J3.6 e J3.7)
# ---------------------------------------------------------------------------------------------
#: Item e tabela da interação tração + corte por versão da NBR (a tabela alternativa mudou de
#: número: 11 na 2008, conferida no texto; 12 na 2025, pelo prompt do usuário).
TABELA_INTERACAO = {"NBR8800_2008": "Tabela 11", "NBR8800_2024": "Tabela 12"}


def area_efetiva(d_b: float) -> float:
    """A_be = 0,75·A_b (mm²): a área efetiva à tração do parafuso. NBR 6.3.2.2."""
    return 0.75 * area_bruta(d_b)


def resist_tracao_parafuso(d_b: float, grau: str, norma: str) -> float:
    """Força de tração resistente de cálculo por parafuso (kN).

    NBR 6.3.3.1:  F_t,Rd = A_be·f_ub/γ_a2, A_be = 0,75·A_b
    AISC J3.6:    φ·F_nt·A_b, φ = 0,75 (F_nt: A325 620, A490 780, A307 310 MPa — Tab. J3.2)
    RCSC 5.1:     φ·F_n·A_b, φ = 0,75 (mesmos F_n à tração; não cobre A307)
    """
    if _nbr(norma):
        return area_efetiva(d_b) * fub(grau, d_b, norma) / _P[norma]["g_a2"] / 1000
    if norma == "RCSC2004" and grau == "A307":
        raise ValueError("RCSC 2004 não cobre A307.")
    return 0.75 * GRAUS[grau].Fnt_AISC * area_bruta(d_b) / 1000


def interacao_tracao_corte(F_t_Sd: float, F_t_Rd: float, F_v_Sd: float, F_v_Rd: float) -> float:
    """(F_t,Sd/F_t,Rd)² + (F_v,Sd/F_v,Rd)² — NBR 6.3.3.4 e RCSC 5.2 (≤ 1,0). Por parafuso."""
    return (F_t_Sd / F_t_Rd) ** 2 + (F_v_Sd / F_v_Rd) ** 2


def coeficiente_tabela_interacao(grau: str, rosca_no_plano: bool) -> float:
    """O fator de F_v,Sd na alternativa tabelada: 1,9 (A307, ou A325/A490 com o plano de corte na
    rosca) e 1,5 (A325/A490 com o plano de corte fora da rosca)."""
    return 1.9 if grau == "A307" or rosca_no_plano else 1.5


def limite_tracao_tabela(
    d_b: float, grau: str, norma: str, rosca_no_plano: bool, F_v_Sd: float
) -> float:
    """Limite da força de tração de cálculo por parafuso com corte (kN), pela tabela alternativa
    da NBR (2008: Tab. 11; 2025: Tab. 12): f_ub·A_b/γ_a2 − k·F_v,Sd — usa A_b, não A_be.
    Exige também as verificações isoladas de tração e de corte."""
    if not _nbr(norma):
        raise ValueError("A tabela alternativa da interação é só da NBR 8800.")
    k = coeficiente_tabela_interacao(grau, rosca_no_plano)
    return fub(grau, d_b, norma) * area_bruta(d_b) / _P[norma]["g_a2"] / 1000 - k * F_v_Sd


def tracao_reduzida_aisc(F_nt: float, F_nv: float, f_rv: float, phi: float = 0.75) -> float:
    """AISC J3.7: F'_nt = 1,3·F_nt − F_nt/(φ·F_nv)·f_rv ≤ F_nt (MPa), f_rv = tensão de corte."""
    return min(F_nt, 1.3 * F_nt - F_nt / (phi * F_nv) * f_rv)


def tracao_nos_parafusos(
    coords: list[tuple[float, float]], N_t: float, M_t: float = 0.0
) -> list[float]:
    """Tração em cada parafuso (kN): F_t,i = N_t/n + M_t·(y_i − ȳ)/Σ(y − ȳ)².

    N_t é a tração do grupo, perpendicular ao plano da ligação; M_t (kN·m) é o momento fora do
    plano que traciona os parafusos de y maior. Eixo neutro no centro do grupo (simplificação: com
    a compressão concentrada numa mesa, o eixo real fica mais baixo e a tração dos de cima é
    menor). Parafuso comprimido fica com 0 — parafuso não trabalha à compressão.
    """
    n = len(coords)
    yc = sum(y for _, y in coords) / n
    soma = sum((y - yc) ** 2 for _, y in coords)
    Mm = M_t * 1000.0
    saida = []
    for _, y in coords:
        f = N_t / n + (Mm * (y - yc) / soma if soma else 0.0)
        saida.append(max(f, 0.0))
    return saida


# ---------------------------------------------------------------------------------------------
# EFEITO DE ALAVANCA (NBR 6.3.5)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Alavanca:
    """Efeito de alavanca numa chapa tracionada pelos parafusos (por parafuso, de cálculo)."""

    metodo: str  # "2025: placa rígida/flexível" ou "2008: 6.3.5.2"
    t_rigida_mm: float  # espessura para não haver alavanca
    t_requerida_mm: float  # a espessura exigida pelo método
    rigida: bool  # t ≥ t_rígida: F_t,Sd = F_t,0,Sd
    beta: float | None = None
    alfa: float | None = None
    delta: float | None = None
    a_calculo_mm: float | None = None  # a limitado a 1,25·b
    F_t_Rd_reduzida_kN: float | None = None  # 2008: F_t,Rd × 0,67 ou × 0,75
    aviso: str = ""


def largura_tributaria_alavanca(
    b: float, e_ext: float | None = None, e_int: float | None = None, extremo: bool = True
) -> float:
    """p de um parafuso (mm): extremo p_ext = mín(e_ext; 1,75b) + mín(0,5·e_int; 1,75b); interno
    p_int = mín(e_int; 3,5b). e_ext: do parafuso à borda; e_int: entre parafusos."""
    if extremo:
        if e_ext is None or e_int is None:
            raise ValueError("p_ext precisa de e_ext e e_int.")
        return min(e_ext, 1.75 * b) + min(0.5 * e_int, 1.75 * b)
    if e_int is None:
        raise ValueError("p_int precisa de e_int.")
    return min(e_int, 3.5 * b)


def alavanca_2025(
    *,
    a: float,
    b: float,
    p: float,
    d_b: float,
    d_f: float,
    t: float,
    f_u: float,
    F_t0_Sd: float,
    F_t_Rd: float,
    gama_a1: float = 1.10,
) -> Alavanca:
    """NBR 8800:2025, 6.3.5 (pelo prompt do usuário; texto a confirmar).

    Placa rígida (sem alavanca): t ≥ √[4·(b − 0,5·d_b)·F_t,0,Sd·γ_a1/(p·f_u)].
    Placa flexível: δ = 1 − d_f/p; β = [(a + 0,5·d_b)/(b − 0,5·d_b)]·(F_t,Rd/F_t,0,Sd − 1);
    α = 1 se β ≥ 1; mín[1; (1/δ)·β/(1 − β)] se 0 < β < 1; t_req = t_rígida/√(1 + δ·α).
    a entra limitado a 1,25·b. β < 0: o parafuso não aguenta nem sem alavanca.
    """
    if min(a, b, p, d_b, t, f_u, F_t_Rd) <= 0 or F_t0_Sd <= 0:
        raise ValueError("Alavanca: a, b, p, d_b, t, f_u, F_t,0,Sd e F_t,Rd devem ser > 0.")
    if b <= 0.5 * d_b:
        raise ValueError("Alavanca: b tem de ser maior que d_b/2 (o parafuso encosta na alma).")
    if not 0 <= d_f < p:
        raise ValueError("Alavanca: o furo d_f tem de ser menor que a largura p.")
    a_c = min(a, 1.25 * b)
    b_l = b - 0.5 * d_b
    a_l = a_c + 0.5 * d_b
    t_rigida = math.sqrt(4 * b_l * F_t0_Sd * 1000 * gama_a1 / (p * f_u))
    delta = 1 - d_f / p
    beta = (a_l / b_l) * (F_t_Rd / F_t0_Sd - 1)
    if beta < 0:
        return Alavanca(
            "NBR 8800:2025, 6.3.5",
            t_rigida,
            t_rigida,
            t >= t_rigida,
            beta,
            None,
            delta,
            a_c,
            aviso="β < 0: a tração sem alavanca passa a resistência do parafuso — altere o parafuso.",
        )
    alfa = 1.0 if beta >= 1 else min(1.0, beta / (delta * (1 - beta))) if beta > 0 else 0.0
    t_req = t_rigida / math.sqrt(1 + delta * alfa)
    return Alavanca("NBR 8800:2025, 6.3.5", t_rigida, t_req, t >= t_rigida, beta, alfa, delta, a_c)


def alavanca_2008(
    *,
    a: float,
    b: float,
    p: float,
    t: float,
    f_y: float,
    F_t_Sd: float,
    F_t_Rd: float,
    plastico: bool = True,
    gama_a1: float = 1.10,
) -> Alavanca:
    """NBR 8800:2008, 6.3.5.2 (texto conferido): a alavanca está coberta se as chapas forem
    dimensionadas com o momento M_Sd = F_t,Sd·b na largura p — plástico (Z = p·t²/4) com a tração
    resistente dos parafusos reduzida em 33 %, ou elástico (W = p·t²/6) com redução de 25 % — e
    a ≥ b. Devolve a espessura exigida e a resistência reduzida."""
    if min(a, b, p, t, f_y, F_t_Rd) <= 0 or F_t_Sd < 0:
        raise ValueError("Alavanca: a, b, p, t, f_y e F_t,Rd devem ser > 0.")
    k, reducao = (4.0, 0.67) if plastico else (6.0, 0.75)
    t_req = math.sqrt(k * F_t_Sd * 1000 * b * gama_a1 / (p * f_y)) if F_t_Sd > 0 else 0.0
    return Alavanca(
        "NBR 8800:2008, 6.3.5.2 " + ("a) momento plástico" if plastico else "b) momento elástico"),
        t_req,
        t_req,
        t >= t_req,
        F_t_Rd_reduzida_kN=reducao * F_t_Rd,
        aviso="" if a >= b else "a < b: a NBR 8800:2008 (6.3.5.2) exige a ≥ b.",
    )


# ---------------------------------------------------------------------------------------------
# FUROS ALARGADOS E ALONGADOS (NBR 2008: Tab. 12, 13, 6.3.11.2; 2025: Tab. 14, 15, 17)
# ---------------------------------------------------------------------------------------------
FURO_PADRAO = "padrao"
FURO_ALARGADO = "alargado"
FURO_POUCO_PARALELO = "pouco_alongado_paralelo"
FURO_POUCO_TRANSVERSAL = "pouco_alongado_transversal"
FURO_MUITO_PARALELO = "muito_alongado_paralelo"
FURO_MUITO_TRANSVERSAL = "muito_alongado_transversal"
TIPOS_DE_FURO = (
    FURO_PADRAO,
    FURO_ALARGADO,
    FURO_POUCO_PARALELO,
    FURO_POUCO_TRANSVERSAL,
    FURO_MUITO_PARALELO,
    FURO_MUITO_TRANSVERSAL,
)
ROTULOS_DE_FURO = {
    FURO_PADRAO: "Padrão",
    FURO_ALARGADO: "Alargado",
    FURO_POUCO_PARALELO: "Pouco alongado, paralelo à força",
    FURO_POUCO_TRANSVERSAL: "Pouco alongado, transversal à força",
    FURO_MUITO_PARALELO: "Muito alongado, paralelo à força",
    FURO_MUITO_TRANSVERSAL: "Muito alongado, transversal à força",
}
POL_MM = 25.4


def _familia(tipo: str) -> str:
    """padrao, alargado, pouco_alongado ou muito_alongado."""
    return tipo.rsplit("_", 1)[0] if tipo.endswith(("paralelo", "transversal")) else tipo


def _dados_tabelas() -> dict[str, Any]:
    import json
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / "data" / "normas_parafusos.json"
    dados: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
    return dados


def fonte_da_tabela(tabela: str, norma: str) -> str:
    """A fonte gravada em data/normas_parafusos.json (norma, item, de onde veio)."""
    chave = "NBR8800_2025" if norma == "NBR8800_2024" else norma
    return str(_dados_tabelas().get(tabela, {}).get(chave, {}).get("fonte", ""))


def _furo_2008(d_b: float, familia: str, polegada: bool) -> tuple[float, float]:
    """NBR 8800:2008, Tabela 12: (largura, comprimento) do furo em mm."""
    if polegada:
        folga = POL_MM / 16
        if familia == "padrao":
            return d_b + folga, d_b + folga
        if math.isclose(d_b, POL_MM, abs_tol=0.05):  # a linha de 1": alargado 1 1/4"
            alargado, pouco = 1.25 * POL_MM, (1 + 5 / 16) * POL_MM
        elif d_b <= 7 / 8 * POL_MM + 0.05:
            alargado, pouco = d_b + 3 / 16 * POL_MM, d_b + 1 / 4 * POL_MM
        else:
            alargado, pouco = d_b + 5 / 16 * POL_MM, d_b + 3 / 8 * POL_MM
    else:
        folga = 1.5
        if familia == "padrao":
            return d_b + folga, d_b + folga
        if math.isclose(d_b, 27.0):
            alargado, pouco = 33.0, 35.0
        elif d_b <= 24:
            alargado, pouco = d_b + 5, d_b + 6
        else:
            alargado, pouco = d_b + 8, d_b + 9.5
    largura = d_b + folga
    if familia == "alargado":
        return alargado, alargado
    if familia == "pouco_alongado":
        return largura, pouco
    return largura, 2.5 * d_b


def _furo_2025(d_b: float, familia: str, polegada: bool) -> tuple[float, float]:
    """NBR 8800:2025, Tabela 14 (= AISC 360-16, Tab. J3.3M): (largura, comprimento) em mm."""
    tabela = _dados_tabelas()["furos"]["NBR8800_2025"]
    if not polegada and str(round(d_b)) in tabela["mm"] and math.isclose(d_b, round(d_b)):
        linha = tabela["mm"][str(round(d_b))]
        valor = linha[familia]
        return (float(valor[0]), float(valor[1])) if isinstance(valor, list) else (valor, valor)
    if polegada:
        chave = _polegadas_do_nome(d_b)
        if chave in tabela["pol"]:
            valor = tabela["pol"][chave][familia]
            par = valor if isinstance(valor, list) else [valor, valor]
            larg, comp = (_fracao(v) * POL_MM for v in par)
            return larg, comp
        folga, alargado, pouco = POL_MM / 8, d_b + 5 / 16 * POL_MM, d_b + 3 / 8 * POL_MM
    else:
        folga, alargado, pouco = 3.0, d_b + 8, d_b + 10
    largura = d_b + folga
    if familia == "padrao":
        return largura, largura
    if familia == "alargado":
        return alargado, alargado
    if familia == "pouco_alongado":
        return largura, pouco
    return largura, 2.5 * d_b


def _polegadas_do_nome(d_b: float) -> str:
    """'5/8' para d_b = 15,875 mm (o nome da linha da tabela em polegadas)."""
    for nome in ("1/2", "5/8", "3/4", "7/8", "1"):
        if math.isclose(d_b, _fracao(nome) * POL_MM, abs_tol=0.01):
            return nome
    return ""


def _fracao(texto: str) -> float:
    """'1 1/16' → 1,0625 (polegadas)."""
    total = 0.0
    for parte in texto.split():
        if "/" in parte:
            num, den = parte.split("/")
            total += float(num) / float(den)
        else:
            total += float(parte)
    return total


def dimensoes_do_furo(designacao: str, tipo: str, norma: str) -> tuple[float, float]:
    """(largura, comprimento) do furo em mm, pela tabela da versão da norma (a AISC/RCSC usa a
    mesma da NBR 2025, que é a da AISC 360-16). Furo redondo: as duas iguais."""
    if tipo not in TIPOS_DE_FURO:
        raise ValueError(f"Tipo de furo desconhecido: {tipo}.")
    polegada = '"' in designacao
    # Em polegadas, o diâmetro exato do nome (5/8" = 15,875 mm; a tabela guarda 15,9).
    d_b = _fracao(designacao.rstrip('"')) * POL_MM if polegada else PARAFUSOS[designacao][0]
    familia = _familia(tipo)
    if norma == "NBR8800_2008":
        return _furo_2008(d_b, familia, polegada)
    return _furo_2025(d_b, familia, polegada)


def furo_na_direcao_da_forca(designacao: str, tipo: str, norma: str) -> float:
    """A dimensão do furo ao longo da força (para ℓ_f): o comprimento se o alongamento é paralelo."""
    largura, comprimento = dimensoes_do_furo(designacao, tipo, norma)
    return comprimento if tipo.endswith("paralelo") else largura


def furo_atravessando_a_forca(designacao: str, tipo: str, norma: str) -> float:
    """A dimensão do furo atravessada pela seção líquida (perpendicular à força)."""
    largura, comprimento = dimensoes_do_furo(designacao, tipo, norma)
    return comprimento if tipo.endswith("transversal") else largura


def furo_permitido(tipo: str, por_atrito: bool) -> tuple[bool, str]:
    """NBR 8800:2008, Tabela 13 (conferida): furo alargado só em ligação por atrito; alongado por
    contato só com a maior dimensão normal à força. (2025: Tabela 15 — a confirmar.)"""
    if tipo == FURO_PADRAO or por_atrito:
        return True, "permitido"
    if tipo == FURO_ALARGADO:
        return False, "furo alargado só em ligação por atrito"
    if tipo.endswith("paralelo"):
        return False, "furo alongado na direção da força só em ligação por atrito"
    return True, "alongado com a maior dimensão normal à força: permitido por contato"


def incremento_de_borda_2008(d_b: float, tipo: str, borda_perpendicular_a_forca: bool) -> float:
    """NBR 8800:2008, 6.3.11.2: β·d_b (mm) a somar à distância mínima da Tabela 14.
    Alongado paralelo à borda: β = 0. A borda e (na direção da força) é perpendicular aos furos
    alongados paralelos à força; a borda e_v, aos transversais."""
    familia = _familia(tipo)
    if familia == "padrao":
        return 0.0
    if familia == "alargado":
        return 0.12 * d_b
    perpendicular = tipo.endswith("paralelo") == borda_perpendicular_a_forca
    if not perpendicular:
        return 0.0
    return (0.20 if familia == "pouco_alongado" else 0.75) * d_b


def deslizamento_e_elu(tipo: str, norma: str) -> bool:
    """O deslizamento é estado-limite último? NBR 6.3.4.2 (2008, conferido): sim com furo alargado
    e alongado paralelo à força; não (serviço) com o padrão e o alongado transversal. Pelo prompt
    da 2025: o muito alongado transversal também é ELU (γ_e 1,40)."""
    if tipo in (FURO_PADRAO, FURO_POUCO_TRANSVERSAL):
        return False
    if tipo == FURO_MUITO_TRANSVERSAL:
        return norma != "NBR8800_2008"
    return True


def gama_e_deslizamento(tipo: str, norma: str, excepcional: bool = False) -> float:
    """γ_e do deslizamento no ELU. 2008 (6.3.4.3): 1,20 / 1,00 excepcional. 2025 (Tab. 13, pelo
    prompt): 1,20 alargado e pouco alongado paralelo, 1,40 muito alongado; 1,00 / 1,15 excepcionais."""
    if norma == "NBR8800_2008":
        return 1.00 if excepcional else 1.20
    if _familia(tipo) == "muito_alongado":
        return 1.15 if excepcional else 1.40
    return 1.00 if excepcional else 1.20


def fator_de_furo_2008(tipo: str) -> float:
    """C_h da NBR 8800:2008 (6.3.4.3): 1,00 padrão; 0,85 alargado ou pouco alongado; 0,70 muito."""
    return {"padrao": 1.00, "alargado": 0.85, "pouco_alongado": 0.85, "muito_alongado": 0.70}[
        _familia(tipo)
    ]


def fi_deslizamento_aisc(tipo: str) -> float:
    """AISC 360-16 J3.8: φ = 1,00 furo-padrão e pouco alongado transversal; 0,85 alargado e pouco
    alongado paralelo; 0,70 muito alongado."""
    if tipo in (FURO_PADRAO, FURO_POUCO_TRANSVERSAL):
        return 1.00
    if _familia(tipo) == "muito_alongado":
        return 0.70
    return 0.85


# ---------------------------------------------------------------------------------------------
# CHAPA DE LIGAÇÃO TRACIONADA (gusset) — NBR 6.5.3; AISC J4.1
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ChapaDeLigacao:
    A_g: float  # mm²
    A_n: float
    A_e: float  # mín(A_n; 0,85·A_g)
    escoamento_kN: float  # A_g·f_y/γ_a1 (φ 0,90)
    ruptura_kN: float  # A_e·f_u/γ_a2 (φ 0,75)
    t_min_escoamento_mm: float  # espessura que a força exige no escoamento
    t_min_ruptura_mm: float


def chapa_de_ligacao(
    largura: float,
    t: float,
    n_furos: int,
    d_furo: float,
    f_y: float,
    f_u: float,
    norma: str,
    F_Sd: float = 0.0,
) -> ChapaDeLigacao:
    """Chapa de ligação tracionada: escoamento da seção bruta e ruptura da seção líquida efetiva,
    com A_e = A_n ≤ 0,85·A_g (NBR 8800:2008, 6.5.3, conferido; AISC J4.1 b). A_n desconta
    (d_furo + 2 mm)·t por furo (1/16" na AISC). C_t não se aplica à chapa de ligação.
    As espessuras mínimas saem em mm: t = F·γ/(largura·f) (escoamento) e a de ruptura com os furos.
    """
    if largura <= 0 or t <= 0 or n_furos < 0:
        raise ValueError("Chapa de ligação: largura e espessura > 0.")
    A_g = largura * t
    folga = _P[norma]["folga"]
    A_n = A_g - n_furos * (d_furo + folga) * t
    A_e = min(A_n, 0.85 * A_g)
    escoamento = A_g * f_y * _fator_escoamento(norma) / 1000
    ruptura = max(A_e, 0.0) * f_u * _fator_ruptura(norma) / 1000
    F = abs(F_Sd) * 1000
    t_esc = F / (largura * f_y * _fator_escoamento(norma))
    # Ruptura: F ≤ mín(A_n, 0,85·A_g)·f_u/γ → t ≥ F·γ/(f_u·mín(largura − n·(d+folga); 0,85·largura)).
    util = min(largura - n_furos * (d_furo + folga), 0.85 * largura)
    t_rup = math.inf if util <= 0 else F / (util * f_u * _fator_ruptura(norma))
    return ChapaDeLigacao(A_g, A_n, A_e, escoamento, ruptura, t_esc, t_rup)


@dataclass(frozen=True)
class ChapaAoCisalhamento:
    A_gv: float  # mm²: comprimento da seção × t
    A_nv: float  # A_gv − n·(d_furo + folga)·t
    escoamento_kN: float  # 0,60·A_gv·f_y/γ_a1 (AISC J4.2: φ = 1,00)
    ruptura_kN: float  # 0,60·A_nv·f_u/γ_a2 (AISC J4.2: φ = 0,75)


def chapa_ao_cisalhamento(
    comprimento: float,
    t: float,
    n_furos: int,
    d_furo: float,
    f_y: float,
    f_u: float,
    norma: str,
) -> ChapaAoCisalhamento:
    """Elemento de ligação ao cisalhamento (NBR 8800:2008, 6.5.5, conferido; AISC J4.2):
    escoamento 0,60·A_g·f_y/γ_a1 e ruptura 0,60·A_nv·f_u/γ_a2, A_nv descontando (d_furo + 2 mm)·t
    por furo da seção (1/16" na AISC). A norma não traz interação com a tração: N e V separados."""
    if comprimento <= 0 or t <= 0 or n_furos < 0:
        raise ValueError("Cisalhamento da chapa: comprimento e espessura > 0.")
    A_gv = comprimento * t
    A_nv = A_gv - n_furos * (d_furo + _P[norma]["folga"]) * t
    if _nbr(norma):
        f_esc, f_rup = 1 / _P[norma]["g_a1"], 1 / _P[norma]["g_a2"]
    else:
        f_esc, f_rup = _P[norma]["phi_vy"], _P[norma]["phi"]
    escoamento = 0.60 * A_gv * f_y * f_esc / 1000
    ruptura = 0.60 * max(A_nv, 0.0) * f_u * f_rup / 1000
    return ChapaAoCisalhamento(A_gv, A_nv, escoamento, ruptura)
