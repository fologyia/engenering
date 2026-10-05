"""Verificação de ligações parafusadas em estruturas de aço.

Portado sem alteração de fórmulas de ``ligacao_parafusada_ref.py`` (módulo de
referência validado). Só mudaram a tipagem, a estrutura de ``GRAUS`` (de dicionário
heterogêneo para dataclass, para o mypy) e as guardas de entrada marcadas "Guarda:".

Normas cobertas (escolha por parâmetro `norma`):

    "NBR8800_2008"  ABNT NBR 8800:2008 (vigente)
    "NBR8800_2024"  Projeto de revisão ABNT NBR 8800 (maio/2024, Rev6)
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
from dataclasses import dataclass
from typing import Any

KIP_KN = 4.448222  # 1 kip em kN
TF_KN = 9.80665  # 1 tf em kN
NORMAS = ("NBR8800_2008", "NBR8800_2024", "AISC360_LRFD", "RCSC2004")

# Valores da NBR 8800:2008 que o módulo de referência trouxe de memória, porque a norma
# vigente não estava disponível. Confirmar na norma antes de liberar a versão.
CONFERIR_NBR8800_2008 = (
    "μ = 0,35 nas superfícies das classes A e C.",
    "f_ub do A325 = 825 MPa (d ≤ 25,4 mm) e 725 MPa (d > 25,4 mm) (Tab. A.3).",
    "C_t limitado a 0,90 (item 5.2.5).",
)


@dataclass(frozen=True)
class GrauParafuso:
    """Resistências de um grau de parafuso, nas duas convenções de tabela."""

    fub: dict[str, tuple[float, float]]  # NBR: (d_b ≤ 25,4 mm, d_b > 25,4 mm)
    Fnv_AISC: tuple[float, float]  # AISC J3.2: (rosca no plano, rosca fora)
    Fn_RCSC: tuple[float, float] | None  # RCSC 5.1; None quando a RCSC não cobre o grau
    protendivel: bool


# ---------------------------------------------------------------------------------------------
# TABELAS
# ---------------------------------------------------------------------------------------------
# designação: (d_b mm, furo-padrão d_h mm, e_mín à borda mm, F_Tb A325 kN, F_Tb A490 kN)
#   d_h: Projeto NBR 8800:2024 Tabela 14 (= AISC 360-16). ATENÇÃO: AISC 360-10 usa 1" → 27,0 mm (1 1/16").
#   e_mín: Projeto NBR 8800:2024 Tabela 16.   F_Tb: Projeto NBR 8800:2024 Tabela 19 (= RCSC Tabela 8.1).
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
#   NBR 8800:2008 Tabela A.3 — CONFERIR NA NORMA (não estava nos arquivos de referência).
#   Projeto NBR 8800:2024 Tabela A.3 (ASTM F3125: resistência única).
# AISC 360-10 Tabela J3.2 (SI): F_nv rosca no plano (N) / fora (X).  RCSC 2004 Tabela 5.1: F_n (N) / (X).
GRAUS = {
    "A325": GrauParafuso(
        fub={"NBR8800_2008": (825, 725), "NBR8800_2024": (830, 830)},
        Fnv_AISC=(372, 469),
        Fn_RCSC=(331, 414),
        protendivel=True,
    ),
    "A490": GrauParafuso(
        fub={"NBR8800_2008": (1035, 1035), "NBR8800_2024": (1040, 1040)},
        Fnv_AISC=(469, 579),
        Fn_RCSC=(414, 517),
        protendivel=True,
    ),
    "A307": GrauParafuso(
        fub={"NBR8800_2008": (415, 415), "NBR8800_2024": (415, 415)},
        Fnv_AISC=(188, 188),
        Fn_RCSC=None,
        protendivel=False,
    ),
}

# Aços das partes ligadas (NBR 8800 Tabela A.2): (f_y, f_u) em MPa
ACOS = {"ASTM A36": (250, 400), "ASTM A572 Gr 50": (345, 450), "ASTM A588": (345, 485)}

# Coeficiente médio de atrito μ por superfície e norma
#   NBR 2024: item 6.3.4.3 (arquivo de referência).  NBR 2008: 0,35 nas classes A/C — CONFERIR NA NORMA.
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


@dataclass
class Verificacao:
    nome: str
    solicitante: float | None
    resistente: float | None
    unidade: str
    referencia: str
    formula: str = ""
    status: str = ""  # "OK", "NÃO OK", "ALERTA", "N/A", "INFO"
    aproveitamento: float | None = None

    def __post_init__(self) -> None:
        if not self.status:
            if self.solicitante is None or self.resistente is None:
                self.status = "N/A"
            else:
                # Guarda: resistência nula OU NEGATIVA (ℓ_f ≤ 0) reprova; a divisão devolveria
                # um aproveitamento negativo, que o teste "<= 1" aceitaria como OK.
                self.aproveitamento = (
                    self.solicitante / self.resistente if self.resistente > 0 else math.inf
                )
                self.status = "OK" if self.aproveitamento <= 1.0 else "NÃO OK"


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
    k1, k2 = (
        (1.0, 2.0)
        if furo_muito_alongado_perp
        else ((1.2, 2.4) if deformacao_limitada else (1.5, 3.0))
    )
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
    """C_t = 1 − e_c/ℓ_c (NBR 5.2.5 c; AISC U, Tab. D3.1 caso 2). NBR 2008 limita a 0,90 — CONFERIR."""
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
    e: float, s: float, g: float, n_lin: int, n_col: int, t: float, d_h: float, norma: str
) -> tuple[float, float, float]:
    """Áreas do bloco entre as linhas externas (n_lin ≥ 2), 2 planos de cisalhamento (mm²).
    Para cantoneiras/peças com 1 linha e tração até a borda livre l_eh: use g = 2·l_eh (equivalente)."""
    dhl = d_h + _P[norma]["folga"]
    L = e + (n_col - 1) * s
    A_gv = 2 * L * t
    A_nv = 2 * (L - (n_col - 0.5) * dhl) * t
    A_nt = (n_lin - 1) * (g - dhl) * t
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
) -> list[Verificacao]:
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
    if regra_75 and (N_t_Rd_peca is None or R_ligacao_tracao is None):
        # Guarda: sem a resistência da peça (A_g, e_c) a regra não é calculável — não omitir.
        out.append(
            Verificacao(
                "Capacidade ≥ 75% da tração da peça e ≥ 3 tf",
                None,
                None,
                "kN",
                "Anglo 9.1 (treliças/contraventamentos por esbeltez)",
                "Informe A_g e e_c da peça para calcular a regra dos 75%.",
                "ALERTA",
            )
        )
    elif regra_75:
        assert N_t_Rd_peca is not None and R_ligacao_tracao is not None
        req = max(0.75 * N_t_Rd_peca, 3 * TF_KN)
        out.append(
            Verificacao(
                "Capacidade ≥ 75% da tração da peça e ≥ 3 tf",
                req,
                R_ligacao_tracao,
                "kN",
                "Anglo 9.1 (treliças/contraventamentos por esbeltez)",
                "R_lig = min(grupo, colapso por rasgamento) ≥ max(0,75 N_t,Rd ; 29,42 kN)",
            )
        )
    return out
