"""Nós soldados de treliças tubulares (banzo e diagonais em tubo) — EN 1993-1-8:2005, capítulo 7.

A ABNT NBR 16239 (estruturas de aço com perfis tubulares) adota as expressões do EN 1993-1-8 para a
resistência das ligações soldadas entre tubos, com o coeficiente γ_a1 = 1,10 no lugar de γ_M5 = 1,0.
O programa faz o mesmo e cobre os casos comuns de treliça, só com forças axiais nas diagonais:

* banzo e diagonais circulares (CHS), nós T/Y, X e K/N com afastamento (Tabela 7.2): plastificação
  da face do banzo e punção; validade pela Tabela 7.1;
* banzo e diagonais retangulares ou quadrados (RHS), nós T/Y, X e K/N com afastamento (Tabela 7.11):
  plastificação da face, parede lateral (β ≥ 0,85), ruptura da diagonal com largura efetiva, punção
  e, no nó K, cisalhamento do banzo no afastamento; validade pela Tabela 7.8.

Fora da faixa de validade, a norma pede todos os modos de falha e os momentos secundários: o
programa reprova a linha de validade e diz isso. Nós com sobreposição, multiplanares e momentos
nas diagonais ficam fora.

Unidades: mm, MPa, N internamente; kN nas entradas e saídas (tração +, compressão −).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from core import nbr8800 as nb
from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "nos_tubulares"
MODULO_TITULO = "Nós de treliça tubular"

CIRCULAR = "Tubo circular (CHS)"
RETANGULAR = "Tubo retangular ou quadrado (RHS)"
FORMAS = (CIRCULAR, RETANGULAR)
NO_T = "T ou Y (uma diagonal)"
NO_X = "X (duas diagonais opostas)"
NO_K = "K ou N com afastamento"
TIPOS = (NO_T, NO_X, NO_K)

ACOS_TUBOS: dict[str, tuple[float, float]] = {
    "VMB 250": (250.0, 400.0),
    "VMB 300": (300.0, 415.0),
    "VMB 350": (350.0, 485.0),
    "ASTM A500 Gr B (circular)": (290.0, 400.0),
    "ASTM A500 Gr B (retangular)": (315.0, 400.0),
    "ASTM A500 Gr C (circular)": (317.0, 427.0),
    "ASTM A500 Gr C (retangular)": (345.0, 427.0),
    "ASTM A36": (250.0, 400.0),
}

REFERENCIAS = (
    "EN 1993-1-8:2005 — Eurocode 3, Part 1-8: Design of joints, capítulo 7 (Hollow section "
    "joints): 7.4 e Tabelas 7.1 e 7.2 (banzo circular); 7.5 e Tabelas 7.8 e 7.11 (banzo "
    "retangular).",
    "ABNT NBR 16239:2013 — Projeto de estruturas de aço e de estruturas mistas de aço e concreto "
    "de edificações com perfis tubulares (mesmas expressões, com γ_a1 = 1,10).",
)


@dataclass(frozen=True)
class Tubo:
    """Circular: ``b`` = diâmetro e ``h`` ignorado. Retangular: ``b`` largura (no plano do banzo,
    transversal), ``h`` altura (no plano da treliça)."""

    b: float
    h: float
    t: float

    def area(self, forma: str) -> float:
        if forma == CIRCULAR:
            return math.pi * (self.b - self.t) * self.t
        return 2 * (self.b + self.h - 2 * self.t) * self.t

    def modulo(self, forma: str) -> float:
        if forma == CIRCULAR:
            d, di = self.b, self.b - 2 * self.t
            return math.pi * (d**4 - di**4) / (32 * d)
        bi, hi = self.b - 2 * self.t, self.h - 2 * self.t
        return (self.b * self.h**3 - bi * hi**3) / (6 * self.h)


@dataclass(frozen=True)
class EntradaNo:
    forma: str = CIRCULAR
    tipo: str = NO_K
    banzo: Tubo = Tubo(168.3, 168.3, 6.4)
    diagonal1: Tubo = Tubo(88.9, 88.9, 4.0)
    diagonal2: Tubo = Tubo(88.9, 88.9, 4.0)
    theta1: float = 45.0
    theta2: float = 45.0
    N1: float = -150.0  # kN (compressão)
    N2: float = 150.0  # kN (tração)
    g: float = 30.0  # afastamento entre as diagonais no nó K (mm)
    N0: float = -400.0  # kN no banzo (lado mais comprimido)
    M0: float = 0.0  # kN·m no banzo
    aco_banzo: str = "VMB 350"
    aco_diagonais: str = "VMB 350"
    gama: float = pi.GAMA_A1


def validar(e: EntradaNo) -> list[str]:
    erros: list[str] = []
    tubos = [e.banzo, e.diagonal1] + ([e.diagonal2] if e.tipo == NO_K else [])
    for t in tubos:
        if min(t.b, t.t) <= 0 or (e.forma == RETANGULAR and t.h <= 0):
            erros.append("As medidas dos tubos devem ser positivas.")
            break
        if 2 * t.t >= min(t.b, t.h if e.forma == RETANGULAR else t.b):
            erros.append("A espessura do tubo é grande demais para a medida externa.")
            break
    for th in (e.theta1, e.theta2):
        if not 0 < th <= 90:
            erros.append("Os ângulos das diagonais ficam entre 0° e 90°.")
            break
    if e.aco_banzo not in ACOS_TUBOS or e.aco_diagonais not in ACOS_TUBOS:
        erros.append("Escolha os aços.")
    if e.tipo == NO_K and e.g <= 0:
        erros.append("No nó K com afastamento, o afastamento g deve ser positivo.")
    if e.diagonal1.b > e.banzo.b or (e.tipo == NO_K and e.diagonal2.b > e.banzo.b):
        erros.append("A diagonal não pode ser mais larga que o banzo.")
    return erros


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def fator_kp(np_: float) -> float:
    """Tabela 7.2: k_p = 1 − 0,3·n_p·(1 + n_p) ≤ 1 com o banzo comprimido; 1 tracionado."""
    if np_ <= 0:
        return 1.0
    return min(1 - 0.3 * np_ * (1 + np_), 1.0)


def fator_kg(gama: float, g: float, t0: float) -> float:
    """Tabela 7.2 (nó K): k_g = γ^0,2·[1 + 0,024·γ^1,2/(1 + exp(0,5·g/t₀ − 1,33))]."""
    return gama**0.2 * (1 + 0.024 * gama**1.2 / (1 + math.exp(0.5 * g / t0 - 1.33)))


def fator_kn(n: float, beta: float) -> float:
    """Tabela 7.10/7.11: k_n = 1,3 − 0,4·n/β ≤ 1 com o banzo comprimido; 1 tracionado."""
    if n <= 0:
        return 1.0
    return min(1.3 - 0.4 * n / beta, 1.0)


@dataclass
class ResultadoNo:
    entrada: EntradaNo
    grupos: list[vm.Grupo]
    parametros: dict[str, float]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def _sin(graus: float) -> float:
    return math.sin(math.radians(graus))


def _validade_chs(e: EntradaNo) -> list[Verificacao]:
    ref = "EN 1993-1-8:2005, Tabela 7.1"
    b0 = e.banzo
    linhas = [
        vm.linha_limite("Validade: d₀/t₀", b0.b / b0.t, 40.0 if e.tipo == NO_X else 50.0, "",
                        ref, f"10 ≤ d₀/t₀ ≤ {'40 (nó X)' if e.tipo == NO_X else '50'}"),
        vm.linha_limite("Validade: d₀/t₀ mínimo", b0.b / b0.t, 10.0, "", ref, "d₀/t₀ ≥ 10",
                        minimo=True),
    ]  # fmt: skip
    diagonais = [(1, e.diagonal1, e.theta1)] + (
        [(2, e.diagonal2, e.theta2)] if e.tipo == NO_K else []
    )
    for i, d, th in diagonais:
        linhas += [
            vm.linha_limite(f"Validade: d{i}/d₀", d.b / b0.b, 0.2, "", ref, "0,2 ≤ d_i/d₀ ≤ 1,0",
                            minimo=True),
            vm.linha_limite(f"Validade: d{i}/t{i}", d.b / d.t, 50.0, "", ref, "d_i/t_i ≤ 50"),
            vm.linha_limite(f"Validade: ângulo θ{i}", th, 30.0, "°", "EN 1993-1-8:2005, 7.1.2(5)",
                            "θ_i ≥ 30°", minimo=True),
        ]  # fmt: skip
    if e.tipo == NO_K:
        linhas.append(
            vm.linha_limite("Validade: afastamento", e.g, e.diagonal1.t + e.diagonal2.t, "mm",
                            ref, "g ≥ t₁ + t₂", minimo=True)
        )  # fmt: skip
    return linhas


def _validade_rhs(e: EntradaNo) -> list[Verificacao]:
    ref = "EN 1993-1-8:2005, Tabela 7.8"
    b0 = e.banzo
    linhas = [
        vm.linha_limite("Validade: b₀/t₀", b0.b / b0.t, 35.0, "", ref, "b₀/t₀ ≤ 35"),
        vm.linha_limite("Validade: h₀/t₀", b0.h / b0.t, 35.0, "", ref, "h₀/t₀ ≤ 35"),
        vm.linha_limite("Validade: h₀/b₀", max(b0.h / b0.b, b0.b / b0.h), 2.0, "", ref,
                        "0,5 ≤ h₀/b₀ ≤ 2,0"),
    ]  # fmt: skip
    diagonais = [(1, e.diagonal1, e.theta1)] + (
        [(2, e.diagonal2, e.theta2)] if e.tipo == NO_K else []
    )
    minimo = 0.25 if e.tipo != NO_K else max(0.35, 0.1 + 0.01 * b0.b / b0.t)
    for i, d, th in diagonais:
        linhas += [
            vm.linha_limite(f"Validade: b{i}/b₀", d.b / b0.b, minimo, "", ref,
                            f"b_i/b₀ ≥ {_n(minimo, 3)}", minimo=True),
            vm.linha_limite(f"Validade: b{i}/t{i} e h{i}/t{i}", max(d.b, d.h) / d.t, 35.0, "",
                            ref, "b_i/t_i e h_i/t_i ≤ 35"),
            vm.linha_limite(f"Validade: h{i}/b{i}", max(d.h / d.b, d.b / d.h), 2.0, "", ref,
                            "0,5 ≤ h_i/b_i ≤ 2,0"),
            vm.linha_limite(f"Validade: ângulo θ{i}", th, 30.0, "°", "EN 1993-1-8:2005, 7.1.2(5)",
                            "θ_i ≥ 30°", minimo=True),
        ]  # fmt: skip
    if e.tipo == NO_K:
        beta = (e.diagonal1.b + e.diagonal2.b + e.diagonal1.h + e.diagonal2.h) / (4 * b0.b)
        linhas += [
            vm.linha_limite("Validade: afastamento mínimo", e.g,
                            max(0.5 * (1 - beta) * b0.b, e.diagonal1.t + e.diagonal2.t), "mm",
                            ref, "g ≥ 0,5·(1 − β)·b₀ e g ≥ t₁ + t₂", minimo=True),
            vm.linha_limite("Validade: afastamento máximo", e.g, 1.5 * (1 - beta) * b0.b, "mm",
                            ref, "g ≤ 1,5·(1 − β)·b₀ (acima, tratar como dois nós T)"),
        ]  # fmt: skip
    return linhas


def _chs(
    e: EntradaNo, fy0: float, fyi: float, np_: float
) -> tuple[list[Verificacao], dict[str, float]]:
    b0 = e.banzo
    d0, t0 = b0.b, b0.t
    g = d0 / (2 * t0)
    kp = fator_kp(np_)
    G = e.gama
    linhas: list[Verificacao] = []
    ref = "EN 1993-1-8:2005, Tabela 7.2"
    par: dict[str, float] = {"gama": g, "kp": kp}
    if e.tipo == NO_K:
        beta = (e.diagonal1.b + e.diagonal2.b) / (2 * d0)
        kg = fator_kg(g, e.g, t0)
        par.update(beta=beta, kg=kg)
        N1 = kg * kp * fy0 * t0**2 / _sin(e.theta1) * (1.8 + 10.2 * e.diagonal1.b / d0) / G
        N2 = _sin(e.theta1) / _sin(e.theta2) * N1
        resist = {1: N1, 2: N2}
        texto = (f"k_g·k_p·f_y0·t₀²/sen θ₁·(1,8 + 10,2·d₁/d₀)/γ_a1, k_g = {_n(kg, 3)}, "
                 f"k_p = {_n(kp, 3)}; N₂,Rd = (sen θ₁/sen θ₂)·N₁,Rd")  # fmt: skip
    else:
        beta = e.diagonal1.b / d0
        par.update(beta=beta)
        if e.tipo == NO_T:
            N1 = g**0.2 * kp * fy0 * t0**2 / _sin(e.theta1) * (2.8 + 14.2 * beta**2) / G
            texto = f"γ^0,2·k_p·f_y0·t₀²/sen θ₁·(2,8 + 14,2·β²)/γ_a1, β = {_n(beta, 3)}"
        else:
            N1 = kp * fy0 * t0**2 / _sin(e.theta1) * 5.2 / (1 - 0.81 * beta) / G
            texto = f"k_p·f_y0·t₀²/sen θ₁·5,2/(1 − 0,81·β)/γ_a1, β = {_n(beta, 3)}"
        resist = {1: N1}
    diagonais = [(1, e.diagonal1, e.theta1, e.N1)] + (
        [(2, e.diagonal2, e.theta2, e.N2)] if e.tipo == NO_K else []
    )
    for i, d, th, N in diagonais:
        linhas.append(
            Verificacao(f"Diagonal {i}: plastificação da face do banzo", abs(N), resist[i] / 1000,
                        "kN", ref, texto)
        )  # fmt: skip
        if d.b <= d0 - 2 * t0:
            puncao = (
                fy0 / math.sqrt(3) * t0 * math.pi * d.b * (1 + _sin(th)) / (2 * _sin(th) ** 2) / G
            )
            linhas.append(
                Verificacao(f"Diagonal {i}: punção do banzo", abs(N), puncao / 1000, "kN", ref,
                            "f_y0/√3·t₀·π·d_i·(1 + sen θ_i)/(2·sen²θ_i)/γ_a1")
            )  # fmt: skip
        # escoamento da própria diagonal (barra)
        linhas.append(
            Verificacao(f"Diagonal {i}: escoamento da seção", abs(N), d.area(CIRCULAR) * fyi / G / 1000,
                        "kN", "ABNT NBR 8800:2025, 5.2.2 a)", "A·f_y/γ_a1 (a flambagem da diagonal "
                        "é verificada à parte)")
        )  # fmt: skip
    return linhas, par


def _rhs(
    e: EntradaNo, fy0: float, fyi: float, n0: float
) -> tuple[list[Verificacao], dict[str, float]]:
    b0 = e.banzo
    t0 = b0.t
    G = e.gama
    ref = "EN 1993-1-8:2005, Tabela 7.11"
    linhas: list[Verificacao] = []
    E = pi.E_ACO
    if e.tipo == NO_K:
        d1, d2 = e.diagonal1, e.diagonal2
        beta = (d1.b + d2.b + d1.h + d2.h) / (4 * b0.b)
        gama = b0.b / (2 * t0)
        kn = fator_kn(n0, beta)
        par = {"beta": beta, "gama": gama, "kn": kn}
        face_k = (
            8.9 * kn * fy0 * t0**2 * math.sqrt(gama) * (d1.b + d2.b + d1.h + d2.h) / (4 * b0.b) / G
        )
        alfa = 1 / math.sqrt(1 + 4 * e.g**2 / (3 * t0**2))
        Av = (2 * b0.h + alfa * b0.b) * t0
        cis = fy0 * Av / math.sqrt(3) / G
        for i, d, th, N in ((1, d1, e.theta1, e.N1), (2, d2, e.theta2, e.N2)):
            beff = min(10 / (b0.b / t0) * fy0 * t0 / (fyi * d.t) * d.b, d.b)
            bep = min(10 / (b0.b / t0) * d.b, d.b)
            linhas += [
                Verificacao(f"Diagonal {i}: plastificação da face do banzo", abs(N),
                            face_k / _sin(th) / 1000, "kN", ref,
                            f"8,9·k_n·f_y0·t₀²·√γ/sen θ·(b₁ + b₂ + h₁ + h₂)/(4·b₀)/γ_a1, "
                            f"k_n = {_n(kn, 3)}, β = {_n(beta, 3)}"),
                Verificacao(f"Diagonal {i}: cisalhamento do banzo no afastamento", abs(N),
                            cis / _sin(th) / 1000, "kN", ref,
                            f"f_y0·A_v/(√3·sen θ)/γ_a1, A_v = (2·h₀ + α·b₀)·t₀ = {_n(Av, 0)} mm², "
                            f"α = {_n(alfa, 3)}"),
                Verificacao(f"Diagonal {i}: ruptura da diagonal", abs(N),
                            fyi * d.t * (2 * d.h - 4 * d.t + d.b + beff) / G / 1000, "kN", ref,
                            f"f_yi·t_i·(2·h_i − 4·t_i + b_i + b_eff)/γ_a1, b_eff = {_n(beff, 1)} mm"),
            ]  # fmt: skip
            if beta <= 1 - 1 / gama:
                linhas.append(
                    Verificacao(f"Diagonal {i}: punção do banzo", abs(N),
                                fy0 * t0 / (math.sqrt(3) * _sin(th))
                                * (2 * d.h / _sin(th) + d.b + bep) / G / 1000, "kN", ref,
                                f"f_y0·t₀/(√3·sen θ)·(2·h_i/sen θ + b_i + b_e,p)/γ_a1, "
                                f"b_e,p = {_n(bep, 1)} mm")
                )  # fmt: skip
        # banzo no afastamento: força normal com o cortante
        V = max(abs(e.N1) * _sin(e.theta1), abs(e.N2) * _sin(e.theta2)) * 1000
        Vpl = fy0 * Av / math.sqrt(3) / G
        A0 = b0.area(RETANGULAR)
        red = math.sqrt(max(1 - (V / Vpl) ** 2, 0.0)) if Vpl > 0 else 0.0
        N0_Rd = ((A0 - Av) * fy0 + Av * fy0 * red) / G
        N_gap = abs(e.N0) * 1000 + 0.0
        linhas.append(
            Verificacao("Banzo no afastamento: força normal com cortante", N_gap / 1000,
                        N0_Rd / 1000, "kN", ref,
                        "[(A₀ − A_v)·f_y0 + A_v·f_y0·√(1 − (V/V_pl)²)]/γ_a1; N₀ do lado mais "
                        "solicitado (a favor da segurança)")
        )  # fmt: skip
        return linhas, par
    d = e.diagonal1
    beta = d.b / b0.b
    eta = d.h / b0.b
    gama = b0.b / (2 * t0)
    kn = fator_kn(n0, beta)
    th = e.theta1
    par = {"beta": beta, "gama": gama, "kn": kn, "eta": eta}

    def face(b: float) -> float:
        return (
            kn
            * fy0
            * t0**2
            / ((1 - b) * _sin(th))
            * (2 * eta / _sin(th) + 4 * math.sqrt(1 - b))
            / G
        )

    def lateral() -> tuple[float, str]:
        if e.N1 >= 0:
            fb = fy0
            texto = "f_b = f_y0 (diagonal tracionada)"
        else:
            lam = 3.46 * (b0.h / t0 - 2) * math.sqrt(1 / _sin(th)) / (math.pi * math.sqrt(E / fy0))
            chi = nb.fator_chi(lam)
            fb = chi * fy0 * (0.8 * _sin(th) if e.tipo == NO_X else 1.0)
            texto = f"f_b = {'0,8·χ·f_y0·sen θ' if e.tipo == NO_X else 'χ·f_y0'}, λ = {_n(lam, 3)}, χ = {_n(chi, 3)}"
        return kn * fb * t0 / _sin(th) * (2 * d.h / _sin(th) + 10 * t0) / G, texto

    if beta <= 0.85:
        linhas.append(
            Verificacao("Diagonal 1: plastificação da face do banzo", abs(e.N1), face(beta) / 1000,
                        "kN", ref, f"k_n·f_y0·t₀²/((1 − β)·sen θ)·(2·η/sen θ + 4·√(1 − β))/γ_a1, "
                        f"β = {_n(beta, 3)}, η = {_n(eta, 3)}, k_n = {_n(kn, 3)}")
        )  # fmt: skip
    else:
        lat, texto = lateral()
        f85 = face(0.85)
        valor = f85 + (lat - f85) * (beta - 0.85) / 0.15 if beta < 1.0 else lat
        linhas.append(
            Verificacao("Diagonal 1: parede lateral do banzo", abs(e.N1), valor / 1000, "kN", ref,
                        f"β = {_n(beta, 3)} > 0,85: interpolação linear entre a plastificação da "
                        f"face (β = 0,85) e a parede lateral (β = 1); {texto}")
        )  # fmt: skip
        beff = min(10 / (b0.b / t0) * fy0 * t0 / (fyi * d.t) * d.b, d.b)
        linhas.append(
            Verificacao("Diagonal 1: ruptura da diagonal", abs(e.N1),
                        fyi * d.t * (2 * d.h - 4 * d.t + 2 * beff) / G / 1000, "kN", ref,
                        f"f_yi·t_i·(2·h_i − 4·t_i + 2·b_eff)/γ_a1, b_eff = {_n(beff, 1)} mm")
        )  # fmt: skip
        if beta <= 1 - 1 / gama:
            bep = min(10 / (b0.b / t0) * d.b, d.b)
            linhas.append(
                Verificacao("Diagonal 1: punção do banzo", abs(e.N1),
                            fy0 * t0 / (math.sqrt(3) * _sin(th)) * (2 * d.h / _sin(th) + 2 * bep)
                            / G / 1000, "kN", ref, f"b_e,p = {_n(bep, 1)} mm")
            )  # fmt: skip
    return linhas, par


def calcular(e: EntradaNo) -> ResultadoNo:
    fy0 = ACOS_TUBOS[e.aco_banzo][0]
    fyi = ACOS_TUBOS[e.aco_diagonais][0]
    A0 = e.banzo.area(e.forma)
    W0 = e.banzo.modulo(e.forma)
    # maior tensão de compressão no banzo (positiva); n_p = σ/f_y0 (γ_M5 = 1 na definição)
    sigma = -e.N0 * 1000 / A0 + abs(e.M0) * 1e6 / W0
    n_rel = sigma / fy0
    avisos: list[str] = []
    if e.forma == CIRCULAR:
        validade = _validade_chs(e)
        linhas, par = _chs(e, fy0, fyi, n_rel)
    else:
        validade = _validade_rhs(e)
        linhas, par = _rhs(e, fy0, fyi, n_rel)
    par["n"] = n_rel
    if e.tipo == NO_K and e.N1 * e.N2 > 0:
        avisos.append(
            "No nó K as duas diagonais costumam ter sinais opostos (uma tracionada, outra "
            "comprimida); com o mesmo sinal, confira o equilíbrio do nó."
        )
    avisos.append(
        "Só forças axiais nas diagonais; a flambagem das barras e os momentos secundários fora da "
        "faixa de validade são verificados à parte."
    )
    grupos = [
        vm.Grupo("Faixa de validade", validade),
        vm.Grupo("Resistência do nó", linhas),
    ]
    return ResultadoNo(e, grupos, par, avisos)


def registro(r: ResultadoNo) -> dict[str, Any]:
    e = r.entrada

    def tubo(t: Tubo) -> str:
        if e.forma == CIRCULAR:
            return f"Ø {_n(t.b, 1)} × {_n(t.t, 2)} mm"
        return f"{_n(t.h, 0)} × {_n(t.b, 0)} × {_n(t.t, 2)} mm"

    entradas = {
        "forma": e.forma,
        "tipo": e.tipo,
        "banzo": f"{tubo(e.banzo)}, {e.aco_banzo}; N₀ = {_n(e.N0, 1)} kN, M₀ = {_n(e.M0, 2)} kN·m",
        "diagonal_1": f"{tubo(e.diagonal1)}, θ₁ = {_n(e.theta1, 0)}°, N₁ = {_n(e.N1, 1)} kN",
        "diagonal_2": (
            f"{tubo(e.diagonal2)}, θ₂ = {_n(e.theta2, 0)}°, N₂ = {_n(e.N2, 1)} kN, g = {_n(e.g, 0)} mm"
            if e.tipo == NO_K
            else ""
        ),
        "aco_das_diagonais": e.aco_diagonais,
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Nó de treliça tubular — {e.tipo.split(' (')[0]}, banzo {tubo(e.banzo)}",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Resistência de ligação soldada entre perfis tubulares pelo EN 1993-1-8:2005, "
            "capítulo 7 (as mesmas expressões da ABNT NBR 16239), com γ_a1 = 1,10."
        ),
        premissas=[
            "Diagonais só com força axial; nó plano (uniplanar), sem sobreposição.",
            "n_p (ou n) com a força normal e o momento do banzo do lado mais comprimido, a favor "
            "da segurança.",
            "Fora da faixa de validade o nó não é aceito: a norma pede todos os modos de falha e "
            "os momentos secundários.",
        ],
        referencias=REFERENCIAS,
        objeto="O nó",
        alertas=r.avisos,
    )


def com(e: EntradaNo, **mudancas: Any) -> EntradaNo:
    return replace(e, **mudancas)
