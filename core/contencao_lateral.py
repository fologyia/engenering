"""Força e rigidez das contenções laterais (travamentos) — ABNT NBR 8800:2025, 4.12.

Um pilar ou uma viga só pode ser calculado com o comprimento destravado entre travamentos se o
travamento for forte e rígido o bastante. A 4.12 dá a força (F_br ou M_br) e a rigidez (S_br ou
S_Tb) mínimas:

* pilar (4.12.2): F_br = 0,01·N_Sd; S_br = 2·(4 − 2/n)·γ_r·N_Sd/L_bc;
* viga, contenção de translação na mesa comprimida (4.12.3.3): F_br = 0,02·M_Sd·C_d/h_o;
  S_br = 10·γ_r·M_Sd·C_d/(L_bb·h_o);
* viga, contenção de torção nodal ou contínua (4.12.3.6 e 4.12.3.7): M_br = 0,024·M_Sd·L/(n·C_b·L_bb);
  S_Tb = S_T/(1 − S_T/S_sec), com a distorção da alma (S_sec) e os enrijecedores.

O programa compara com a barra de travamento (área, comprimento, ângulo, aço, raio de giração e a
flexibilidade da ligação) ou com a rigidez à rotação de uma viga transversal, e diz se o
travamento é efetivo. Várias barras travadas pela mesma contenção somam as forças.

Unidades: mm, MPa, N internamente; kN, kN·m e kN/mm nas entradas e saídas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from core import nbr8800 as nb
from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "contencao_lateral"
MODULO_TITULO = "Contenção lateral (travamentos)"
GAMA_R = 1.35  # NBR 8800:2025, 4.12.2.2 e 4.12.3.3

PILAR = "Pilar ou barra comprimida (translação)"
VIGA_TRANSLACAO = "Viga — contenção de translação (mesa comprimida)"
VIGA_TORCAO = "Viga — contenção de torção (nodal)"
VIGA_TORCAO_CONTINUA = "Viga — contenção de torção contínua"
CASOS = (PILAR, VIGA_TRANSLACAO, VIGA_TORCAO, VIGA_TORCAO_CONTINUA)

TRACAO = "Só tração (tirante, barra redonda)"
COMPRESSAO = "Tração e compressão (cantoneira, tubo, perfil)"
TRABALHOS = (TRACAO, COMPRESSAO)

BETA_INFORMADO = "Rigidez à rotação informada"
BETA_DUPLA = "Viga transversal em curvatura dupla (β = 6·E·I/S)"
BETA_SIMPLES = "Viga transversal em curvatura simples (β = 2·E·I/S)"
BETAS = (BETA_INFORMADO, BETA_DUPLA, BETA_SIMPLES)

REFERENCIAS = (
    "ABNT NBR 8800:2025 — 4.12 Resistência e rigidez das contenções laterais (4.12.2 pilares; "
    "4.12.3 vigas: translação e torção).",
    "AISC 360-16 — Appendix 6, Member Stability Bracing (mesma origem das expressões) e "
    "comentário (rigidez de vigas transversais, 6·E·I/S e 2·E·I/S).",
)


@dataclass(frozen=True)
class EntradaContencao:
    caso: str = VIGA_TRANSLACAO
    familia: str = pi.FAMILIA_W
    perfil: str = "W 410 x 46,1"
    d: float = 400.0
    bf: float = 180.0
    tf: float = 12.5
    tw: float = 8.0
    # esforço da barra travada
    N_Sd: float = 800.0  # kN (pilar)
    M_Sd: float = 180.0  # kN·m (viga)
    barras: int = 1  # barras travadas em série pela mesma contenção
    L_b: float = 2000.0  # distância entre contenções (mm)
    L_q: float = 0.0  # comprimento destravado máximo que ainda resiste (0 = não usar)
    n: int = 2  # número de contenções (pilar) ou de pontos no interior do vão (torção)
    curvatura_reversa: bool = False  # C_d = 2 junto ao ponto de inflexão
    L_vao: float = 6000.0  # vão da viga (torção)
    Cb: float = 1.0
    t_st: float = 8.0  # enrijecedor da alma no ponto de torção (0 = sem)
    b_st: float = 60.0  # largura de um lado (o programa dobra para o par)
    par_de_enrijecedores: bool = True
    # barra de contenção (translação)
    trabalho: str = COMPRESSAO
    A_br: float = 480.0  # mm²
    r_br: float = 9.9  # raio de giração mínimo (mm)
    L_br: float = 1500.0  # comprimento da barra de contenção (mm)
    angulo: float = 0.0  # entre a barra e a direção do deslocamento impedido (graus)
    aco_br: str = "ASTM A36"
    k_ligacao: float = 0.0  # rigidez da ligação (kN/mm); 0 = rígida
    # contenção de torção
    beta_tipo: str = BETA_DUPLA
    beta: float = 500.0  # kN·m/rad (informada)
    I_transversal: float = 10.0e6  # mm⁴ da viga transversal
    S_transversal: float = 2000.0  # vão da viga transversal (mm)
    M_Rd_ligacao: float = 10.0  # kN·m da ligação da contenção de torção
    gama_a1: float = pi.GAMA_A1


def obter_perfil(e: EntradaContencao) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw)
    return pi.perfil(e.perfil)


def validar(e: EntradaContencao) -> list[str]:
    erros: list[str] = []
    try:
        obter_perfil(e)
    except (ValueError, KeyError) as exc:
        erros.append(f"Perfil: {exc}")
    if e.caso not in CASOS:
        erros.append("Escolha o tipo de contenção.")
    if e.L_b <= 0:
        erros.append("A distância entre contenções deve ser positiva.")
    if e.barras < 1 or e.n < 1:
        erros.append("O número de barras e de contenções deve ser pelo menos 1.")
    if e.caso == PILAR and e.N_Sd <= 0:
        erros.append("Informe a força de compressão do pilar.")
    if e.caso != PILAR and e.M_Sd <= 0:
        erros.append("Informe o momento fletor da viga.")
    if e.caso in (PILAR, VIGA_TRANSLACAO):
        if e.A_br <= 0 or e.L_br <= 0 or e.r_br <= 0:
            erros.append("Barra de contenção: área, raio de giração e comprimento positivos.")
        if not 0 <= e.angulo < 90:
            erros.append("O ângulo da barra de contenção deve ficar entre 0° e 90°.")
        if e.aco_br not in pi.ACOS:
            erros.append("Escolha o aço da barra de contenção.")
    if e.caso in (VIGA_TORCAO, VIGA_TORCAO_CONTINUA):
        if e.L_vao <= 0 or e.Cb <= 0:
            erros.append("Vão e C_b devem ser positivos.")
        if e.beta_tipo == BETA_INFORMADO and e.beta <= 0:
            erros.append("Informe a rigidez à rotação da contenção.")
        if e.beta_tipo != BETA_INFORMADO and (e.I_transversal <= 0 or e.S_transversal <= 0):
            erros.append("Viga transversal: inércia e vão positivos.")
    return erros


def _n(valor: float, casas: int = 2) -> str:
    return pi.numero(valor, casas)


# ---------------------------------------------------------------- exigências da norma (N, mm)
def exigencia_pilar(N: float, L: float, n: int) -> tuple[float, float]:
    """4.12.2.2: (F_br em N, S_br em N/mm)."""
    return 0.01 * N, 2 * (4 - 2 / n) * GAMA_R * N / L


def exigencia_translacao(M: float, ho: float, L: float, Cd: float) -> tuple[float, float]:
    """4.12.3.3: (F_br em N, S_br em N/mm)."""
    return 0.02 * M * Cd / ho, 10 * GAMA_R * M * Cd / (L * ho)


def rigidez_da_alma(ho: float, tw: float, t_st: float, b_st: float, E: float = pi.E_ACO) -> float:
    """4.12.3.6: S_sec = 3,3·E/h_o·(1,5·h_o·t_w³/12 + t_st·b_st³/12), em N·mm/rad."""
    return 3.3 * E / ho * (1.5 * ho * tw**3 / 12 + t_st * b_st**3 / 12)


def exigencia_torcao(
    M: float, L: float, n: int, Cb: float, Lbb: float, Iy: float, E: float = pi.E_ACO
) -> tuple[float, float]:
    """4.12.3.6: (M_br em N·mm, S_T em N·mm/rad, sem a distorção da alma)."""
    return 0.024 * M * L / (n * Cb * Lbb), 2.4 * GAMA_R * L * M**2 / (n * E * Iy * Cb**2)


@dataclass
class ResultadoContencao:
    entrada: EntradaContencao
    perfil: pi.PerfilI
    grupos: list[vm.Grupo]
    exigencias: dict[str, float]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def _barra_de_contencao(e: EntradaContencao, F: float, S: float) -> list[Verificacao]:
    """A barra que trava: força ao longo dela e rigidez na direção impedida (com a ligação)."""
    fy = pi.ACOS[e.aco_br][0]
    c = math.cos(math.radians(e.angulo))
    F_barra = F / c
    if e.trabalho == TRACAO:
        N_Rd = e.A_br * fy / e.gama_a1
        texto_rd = "A·f_y/γ_a1 (só tração: em cada sentido trabalha a barra do lado oposto)"
    else:
        lam0 = e.L_br / e.r_br / math.pi * math.sqrt(fy / pi.E_ACO)
        chi = nb.fator_chi(lam0)
        N_Rd = chi * e.A_br * fy / e.gama_a1
        texto_rd = f"χ·A·f_y/γ_a1 com K = 1, λ₀ = {_n(lam0, 3)}, χ = {_n(chi, 3)} (Q = 1)"
    k_barra = pi.E_ACO * e.A_br / e.L_br * c**2  # N/mm na direção impedida
    k = k_barra
    if e.k_ligacao > 0:
        k_lig = e.k_ligacao * 1000 * c**2
        k = 1 / (1 / k_barra + 1 / k_lig)
    linhas = [
        Verificacao(
            "Resistência da barra de contenção",
            F_barra / 1000,
            N_Rd / 1000,
            "kN",
            "ABNT NBR 8800:2025, 4.12.1.1, 5.2 e 5.3",
            f"força ao longo da barra F_br/cos θ (θ = {_n(e.angulo, 0)}°); N_Rd = {texto_rd}",
        ),
        Verificacao(
            "Rigidez da barra de contenção",
            S / 1000,
            k / 1000,
            "kN/mm",
            "ABNT NBR 8800:2025, 4.12.1.1",
            f"k = E·A·cos²θ/L = {_n(k_barra / 1000, 2)} kN/mm"
            + (f", em série com a ligação ({_n(e.k_ligacao, 1)} kN/mm)" if e.k_ligacao > 0 else ""),
        ),
    ]
    if e.trabalho == COMPRESSAO:
        linhas.append(
            vm.linha_limite(
                "Esbeltez da barra de contenção",
                e.L_br / e.r_br,
                200.0,
                "",
                "ABNT NBR 8800:2025, 5.3.7",
                "K·L/r ≤ 200",
            )
        )
    return linhas


def calcular(e: EntradaContencao) -> ResultadoContencao:
    p = obter_perfil(e)
    ho = p.d - p.tf
    avisos: list[str] = []
    ref = "ABNT NBR 8800:2025, "
    L = max(e.L_b, e.L_q) if e.L_q > 0 else e.L_b
    if e.L_q > e.L_b:
        avisos.append(
            f"L_b = {_n(e.L_b, 0)} mm < L_q = {_n(e.L_q, 0)} mm: usado L_q na rigidez exigida "
            "(4.12.2.3 e 4.12.3.4)."
        )
    grupos: list[vm.Grupo] = []
    exig: dict[str, float] = {}
    if e.caso == PILAR:
        N = e.N_Sd * 1000 * e.barras
        F, S = exigencia_pilar(N, L, e.n)
        exig = {"F_br_kN": F / 1000, "S_br_kN_mm": S / 1000}
        grupos.append(
            vm.Grupo(
                "Exigência da norma",
                [
                    vm.linha_info("Força exigida F_br", F / 1000, "kN", ref + "4.12.2.2",
                                  f"0,01·N_Sd, N_Sd = {_n(N / 1000, 1)} kN ({e.barras} barra(s))"),
                    vm.linha_info("Rigidez exigida S_br", S / 1000, "kN/mm", ref + "4.12.2.2",
                                  f"2·(4 − 2/n)·γ_r·N_Sd/L_bc, n = {e.n}, γ_r = 1,35, "
                                  f"L_bc = {_n(L, 0)} mm"),
                ],
            )
        )  # fmt: skip
        grupos.append(vm.Grupo("Barra de contenção", _barra_de_contencao(e, F, S)))
    elif e.caso == VIGA_TRANSLACAO:
        M = e.M_Sd * 1e6 * e.barras
        Cd = 2.0 if e.curvatura_reversa else 1.0
        F, S = exigencia_translacao(M, ho, L, Cd)
        exig = {"F_br_kN": F / 1000, "S_br_kN_mm": S / 1000}
        grupos.append(
            vm.Grupo(
                "Exigência da norma",
                [
                    vm.linha_info("Força exigida F_br", F / 1000, "kN", ref + "4.12.3.3",
                                  f"0,02·M_Sd·C_d/h_o, h_o = d − t_f = {_n(ho, 1)} mm, "
                                  f"C_d = {_n(Cd, 0)}"),
                    vm.linha_info("Rigidez exigida S_br", S / 1000, "kN/mm", ref + "4.12.3.3",
                                  f"10·γ_r·M_Sd·C_d/(L_bb·h_o), L_bb = {_n(L, 0)} mm"),
                ],
            )
        )  # fmt: skip
        grupos.append(vm.Grupo("Barra de contenção", _barra_de_contencao(e, F, S)))
        if e.curvatura_reversa:
            avisos.append(
                "Junto ao ponto de inflexão, a contenção de translação deve ser fixada nas duas "
                "mesas (4.12.3.2)."
            )
    else:
        continua = e.caso == VIGA_TORCAO_CONTINUA
        M = e.M_Sd * 1e6 * e.barras
        n = 1 if continua else e.n
        L_vao = L if continua else e.L_vao  # contínua: L/n = 1 (por unidade de comprimento)
        Mbr, ST = exigencia_torcao(M, L_vao, n, e.Cb, L, p.Iy)
        b_st = (2 if e.par_de_enrijecedores else 1) * e.b_st
        if continua:
            # L/n = 1: momento (N·mm/mm) e rigidez (N·mm/rad/mm) por unidade de comprimento
            Mbr = 0.024 * M / (e.Cb * L)
            ST = 2.4 * GAMA_R * M**2 / (pi.E_ACO * p.Iy * e.Cb**2)
            Ssec = 3.3 * pi.E_ACO * p.tw**3 / (12 * ho)
            unidade_m, unidade_s, fator_s = "kN·m/m", "kN·m/rad/m", 1e3
        else:
            Ssec = rigidez_da_alma(ho, p.tw, e.t_st, b_st)
            unidade_m, unidade_s, fator_s = "kN·m", "kN·m/rad", 1e6
        STb = ST / (1 - ST / Ssec) if Ssec > ST else math.inf
        exig = {"M_br": Mbr / 1e6 * (1e3 if continua else 1), "S_T": ST / fator_s,
                "S_sec": Ssec / fator_s, "S_Tb": STb / fator_s}  # fmt: skip
        if continua:
            beta_cmp = e.beta  # informada por metro (forma de aço, laje, painel)
            texto_beta = "informada, por metro de viga"
        elif e.beta_tipo == BETA_INFORMADO:
            beta_cmp = e.beta
            texto_beta = "informada"
        else:
            c6 = 6.0 if e.beta_tipo == BETA_DUPLA else 2.0
            beta_cmp = c6 * pi.E_ACO * e.I_transversal / e.S_transversal / 1e6
            texto_beta = (
                f"{_n(c6, 0)}·E·I/S, I = {_n(e.I_transversal / 1e6, 2)}×10⁶ mm⁴, "
                f"S = {_n(e.S_transversal, 0)} mm"
            )
        linhas = [
            vm.linha_info(
                "Momento exigido M_br",
                exig["M_br"],
                unidade_m,
                ref + ("4.12.3.7" if continua else "4.12.3.6"),
                f"0,024·M_Sd·L/(n·C_b·L_bb), n = {n}, C_b = {_n(e.Cb, 2)}"
                + (" (por metro: L/n = 1)" if continua else ""),
            ),
            vm.linha_info(
                "Rigidez exigida sem a alma S_T",
                ST / fator_s,
                unidade_s,
                ref + "4.12.3.6",
                f"2,4·γ_r·L·M_Sd²/(n·E·I_y·C_b²), I_y = {_n(p.Iy / 1e6, 2)}×10⁶ mm⁴",
            ),
            vm.linha_info(
                "Rigidez à distorção da alma S_sec",
                Ssec / fator_s,
                unidade_s,
                ref + ("4.12.3.7" if continua else "4.12.3.6"),
                "3,3·E/h_o·(1,5·h_o·t_w³/12 + t_st·b_st³/12)"
                + (f", enrijecedor {_n(e.t_st, 1)} × {_n(b_st, 0)} mm" if e.t_st > 0 else
                   ", sem enrijecedor"),
            ),
        ]  # fmt: skip
        if math.isinf(STb):
            linhas.append(
                Verificacao(
                    "Distorção da alma",
                    ST / fator_s,
                    Ssec / fator_s,
                    unidade_s,
                    ref + "4.12.3.6",
                    "S_sec ≤ S_T: a contenção de torção não é efetiva pela distorção da alma — "
                    "coloque enrijecedor de alma no ponto travado",
                    status="NÃO OK",
                    aproveitamento=ST / Ssec,
                )
            )
        else:
            linhas.append(
                Verificacao(
                    "Rigidez da contenção de torção",
                    STb / fator_s,
                    beta_cmp,
                    unidade_s,
                    ref + "4.12.3.6",
                    f"β ≥ S_Tb = S_T/(1 − S_T/S_sec); β = {texto_beta}",
                )
            )
        linhas.append(
            Verificacao(
                "Momento resistente da ligação da contenção",
                exig["M_br"],
                e.M_Rd_ligacao,
                unidade_m,
                ref + "4.12.3.6",
                "a ligação da contenção com a viga deve resistir a M_br",
            )
        )
        grupos.append(vm.Grupo("Contenção de torção", linhas))
        if e.t_st > 0:
            avisos.append(
                "O enrijecedor deve ir até a altura total da viga e ser fixado à mesa ligada à "
                "contenção; pode parar a 4·t_w da mesa que não recebe a contenção (4.12.3.6)."
            )
    return ResultadoContencao(e, p, grupos, exig, avisos)


def registro(r: ResultadoContencao) -> dict[str, Any]:
    e = r.entrada
    entradas: dict[str, Any] = {
        "caso": e.caso,
        "perfil": r.perfil.descricao,
        "esforco": (f"N_Sd = {_n(e.N_Sd, 1)} kN" if e.caso == PILAR else f"M_Sd = {_n(e.M_Sd, 1)} kN·m")
        + (f" × {e.barras} barras" if e.barras > 1 else ""),
        "distancia_entre_contencoes_mm": e.L_b,
    }  # fmt: skip
    if e.caso in (PILAR, VIGA_TRANSLACAO):
        entradas["barra_de_contencao"] = (
            f"A = {_n(e.A_br, 0)} mm², r = {_n(e.r_br, 1)} mm, L = {_n(e.L_br, 0)} mm, "
            f"θ = {_n(e.angulo, 0)}°, {e.aco_br}, {e.trabalho.split(' (')[0].lower()}"
        )
    else:
        entradas["contencao_de_torcao"] = e.beta_tipo
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Contenção lateral — {r.perfil.nome}",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Resistência e rigidez mínimas das contenções laterais pela ABNT NBR 8800:2025, 4.12, "
            "comparadas com a barra de contenção (rigidez axial com a da ligação em série) ou com "
            "a rigidez à rotação da contenção de torção."
        ),
        premissas=[
            "A força exigida da contenção não se soma às outras ações (4.12.1.1).",
            "Barra inclinada: força ao longo da barra = F_br/cos θ; rigidez útil = E·A·cos²θ/L.",
            "Várias barras travadas pela mesma contenção somam N_Sd (ou M_Sd).",
        ],
        referencias=REFERENCIAS,
        objeto="A contenção lateral",
        alertas=r.avisos,
    )


def com(e: EntradaContencao, **mudancas: Any) -> EntradaContencao:
    return replace(e, **mudancas)
