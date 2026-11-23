"""Barras de aço em situação de incêndio — método simplificado da ABNT NBR 14323.

* Temperatura dos gases pela curva-padrão ISO 834: θ_g = 20 + 345·log₁₀(8·t + 1) (t em minutos).
* Temperatura do aço, passo a passo (Δt ≤ 5 s), com distribuição uniforme na seção (8.5.1):
  sem proteção, Δθ_a = (u/A)·φ·Δt/(ρ_a·c_a), φ = α_c·(θ_g − θ_a) + 5,67×10⁻⁸·ε_res·[(θ_g + 273)⁴ −
  (θ_a + 273)⁴], α_c = 25 W/m²·°C, ε_res = 0,5; com proteção, a expressão de 8.5.1.2.2 com
  ξ = c_m·ρ_m·t_m·(u_m/A)/(c_a·ρ_a). Calor específico do aço pelo Anexo E.
* Fatores de redução k_y,θ e k_E,θ da Tabela 1 (aços laminados), com interpolação linear.
* Resistências (8.4): tração k_y·A_g·f_y; compressão χ_fi·k_y·A_g·f_y (χ_fi de 8.4.2.2.2); flexão de
  perfil I compacto com κ₁·κ₂ e a FLT do método simplificado (8.4.3.2.3).
* Combinação excepcional (6.2.1): γ_g·G + ψ·Q, com ψ = 0,21, 0,28 ou 0,42 pela ocupação.

O tempo requerido de resistência ao fogo (TRRF) vem da ABNT NBR 14432, pela ocupação e altura;
o programa só o recebe.

Unidades: mm, MPa, N internamente; kN e kN·m nas entradas e saídas; temperaturas em °C.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any

from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "incendio"
MODULO_TITULO = "Estrutura em situação de incêndio"

#: NBR 14323 Tabela 1 (aços laminados): θ → (k_y,θ, k_E,θ)
TABELA_1: tuple[tuple[float, float, float], ...] = (
    (20, 1.000, 1.0000), (100, 1.000, 1.0000), (200, 1.000, 0.9000), (300, 1.000, 0.8000),
    (400, 1.000, 0.7000), (500, 0.780, 0.6000), (600, 0.470, 0.3100), (700, 0.230, 0.1300),
    (800, 0.110, 0.0900), (900, 0.060, 0.0675), (1000, 0.040, 0.0450), (1100, 0.020, 0.0225),
    (1200, 0.000, 0.0000),
)  # fmt: skip

PILAR = "Pilar (compressão)"
TIRANTE = "Tirante (tração)"
VIGA = "Viga (flexão)"
ELEMENTOS = (PILAR, TIRANTE, VIGA)

CONTORNO_4 = "Contorno, 4 lados expostos"
CONTORNO_3 = "Contorno, 3 lados (mesa de cima sob laje)"
CAIXAO_4 = "Caixão, 4 lados"
CAIXAO_3 = "Caixão, 3 lados (sob laje)"
EXPOSICOES = (CONTORNO_4, CONTORNO_3, CAIXAO_4, CAIXAO_3)

#: ψ da ação variável na combinação excepcional (6.2.1)
OCUPACOES = {
    "Residencial ou de acesso restrito (ψ = 0,21)": 0.21,
    "Comercial, escritório, acesso público (ψ = 0,28)": 0.28,
    "Depósito, oficina, garagem, biblioteca (ψ = 0,42)": 0.42,
}

#: valores típicos de materiais de proteção (confira no catálogo do fabricante)
PROTECOES: dict[str, tuple[float, float, float]] = {
    # nome: (λ_m W/m·°C, ρ_m kg/m³, c_m J/kg·°C)
    "Sem proteção": (0.0, 0.0, 0.0),
    "Argamassa projetada (vermiculita/cimento)": (0.12, 350.0, 1200.0),
    "Fibra mineral projetada": (0.12, 300.0, 1200.0),
    "Placa de gesso": (0.20, 800.0, 1700.0),
    "Placa de lã de rocha": (0.20, 150.0, 1200.0),
    "Informar as propriedades": (0.10, 300.0, 1000.0),
}

REFERENCIAS = (
    "ABNT NBR 14323 — Projeto de estruturas de aço e de estruturas mistas de aço e concreto em "
    "situação de incêndio: 5.1 (Tabela 1 e Anexo E), 6.2 (combinações), 8.4 (resistências) e "
    "8.5 (elevação da temperatura do aço).",
    "ABNT NBR 14432 — Exigências de resistência ao fogo de elementos construtivos (TRRF).",
    "ABNT NBR 5628 / ISO 834 — curva-padrão de incêndio.",
)


@dataclass(frozen=True)
class EntradaIncendio:
    elemento: str = PILAR
    familia: str = pi.FAMILIA_W
    perfil: str = "HP 250 x 62,0"
    d: float = 300.0
    bf: float = 200.0
    tf: float = 12.5
    tw: float = 8.0
    aco: str = "ASTM A572 Gr 50"
    L: float = 4000.0  # comprimento de flambagem (pilar) ou destravado (viga)
    K: float = 1.0
    Cb: float = 1.0
    exposicao: str = CONTORNO_4
    trrf: float = 60.0  # minutos
    protecao: str = "Argamassa projetada (vermiculita/cimento)"
    tm: float = 20.0  # espessura da proteção (mm)
    lambda_m: float = 0.12
    rho_m: float = 350.0
    c_m: float = 1200.0
    temperatura_informada: float = 0.0  # °C (0 = calcular)
    G_k: float = 400.0  # esforço característico permanente (kN ou kN·m)
    Q_k: float = 300.0  # esforço característico variável de uso
    gama_g: float = 1.20
    ocupacao: str = "Depósito, oficina, garagem, biblioteca (ψ = 0,42)"
    viga_hiperestatica: bool = False  # κ₂ = 1,15 nos apoios


def obter_perfil(e: EntradaIncendio) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw)
    return pi.perfil(e.perfil)


def validar(e: EntradaIncendio) -> list[str]:
    erros: list[str] = []
    try:
        obter_perfil(e)
    except (ValueError, KeyError) as exc:
        erros.append(f"Perfil: {exc}")
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço.")
    if e.trrf <= 0 or e.trrf > 240:
        erros.append("O TRRF fica entre 1 e 240 minutos.")
    if e.L <= 0 or e.K <= 0 or e.Cb <= 0:
        erros.append("Comprimento, K e C_b devem ser positivos.")
    if e.protecao != "Sem proteção" and (
        e.tm <= 0 or e.lambda_m <= 0 or e.rho_m <= 0 or e.c_m <= 0
    ):
        erros.append("Proteção: espessura e propriedades do material devem ser positivas.")
    if e.G_k < 0 or e.Q_k < 0:
        erros.append("Os esforços característicos são valores absolutos.")
    if not 0 <= e.temperatura_informada <= 1200:
        erros.append("A temperatura informada fica entre 0 (calcular) e 1200 °C.")
    return erros


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def temperatura_dos_gases(t_min: float) -> float:
    """Curva-padrão: θ_g = 20 + 345·log₁₀(8·t + 1), t em minutos."""
    return 20 + 345 * math.log10(8 * t_min + 1)


def calor_especifico(theta: float) -> float:
    """NBR 14323, Anexo E (J/kg·°C)."""
    if theta < 600:
        return 425 + 0.773 * theta - 1.69e-3 * theta**2 + 2.22e-6 * theta**3
    if theta < 735:
        return 666 + 13002 / (738 - theta)
    if theta < 900:
        return 545 + 17820 / (theta - 731)
    return 650.0


def fatores(theta: float) -> tuple[float, float]:
    """(k_y,θ, k_E,θ) da Tabela 1, interpolados."""
    if theta <= TABELA_1[0][0]:
        return TABELA_1[0][1], TABELA_1[0][2]
    for (t0, y0, e0), (t1, y1, e1) in pairwise(TABELA_1):
        if theta <= t1:
            f = (theta - t0) / (t1 - t0)
            return y0 + (y1 - y0) * f, e0 + (e1 - e0) * f
    return 0.0, 0.0


def perimetro(p: pi.PerfilI, exposicao: str) -> float:
    """Perímetro exposto (mm) do contorno ou do caixão."""
    return {
        CONTORNO_4: 2 * p.d + 4 * p.bf - 2 * p.tw,
        CONTORNO_3: 2 * p.d + 3 * p.bf - 2 * p.tw,
        CAIXAO_4: 2 * (p.d + p.bf),
        CAIXAO_3: 2 * p.d + p.bf,
    }[exposicao]


def temperatura_do_aco(
    u_A: float,
    t_min: float,
    *,
    protegido: bool = False,
    tm: float = 0.0,
    lam: float = 0.0,
    rho_m: float = 0.0,
    c_m: float = 0.0,
) -> tuple[float, list[tuple[float, float, float]]]:
    """Integração no tempo (8.5.1.1 ou 8.5.1.2). ``u_A`` em m⁻¹, ``tm`` em m.

    Devolve a temperatura final e a curva [(t em min, θ_g, θ_a)] a cada minuto.
    """
    rho_a = 7850.0
    dt = min(5.0, 25000.0 / max(u_A, 10.0))
    passos = int(math.ceil(t_min * 60 / dt))
    dt = t_min * 60 / passos if passos else dt
    theta_a = 20.0
    theta_g_ant = 20.0
    curva = [(0.0, 20.0, 20.0)]
    proximo = 1.0
    for i in range(1, passos + 1):
        t = i * dt / 60
        theta_g = temperatura_dos_gases(t)
        ca = calor_especifico(theta_a)
        if not protegido:
            u = max(u_A, 10.0)
            phi = 25 * (theta_g - theta_a) + 5.67e-8 * 0.5 * (
                (theta_g + 273) ** 4 - (theta_a + 273) ** 4
            )
            d = u * phi * dt / (rho_a * ca)
        else:
            xi = c_m * rho_m * tm * u_A / (ca * rho_a)
            d = lam * u_A * (theta_g - theta_a) * dt / (tm * ca * rho_a * (1 + xi / 4)) - (
                theta_g - theta_g_ant
            ) / (4 / xi + 1)
            d = max(d, 0.0)
        theta_a += d
        theta_g_ant = theta_g
        if t >= proximo - 1e-9:
            curva.append((round(t, 3), theta_g, theta_a))
            proximo += 1.0
    return theta_a, curva


@dataclass
class ResultadoIncendio:
    entrada: EntradaIncendio
    perfil: pi.PerfilI
    fy: float
    theta: float
    ky: float
    kE: float
    u_A: float
    curva: list[tuple[float, float, float]]
    grupos: list[vm.Grupo]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def chi_incendio(lam0: float, ky: float, kE: float, fy: float) -> tuple[float, float]:
    """8.4.2.2.2: χ_fi e λ_0,θ."""
    if kE <= 0 or ky <= 0:
        return 0.0, math.inf
    lam_t = lam0 * math.sqrt(ky / kE)
    alfa = 0.022 * math.sqrt(pi.E_ACO / fy)
    beta = 0.5 * (1 + alfa * lam_t + lam_t**2)
    return 1 / (beta + math.sqrt(beta**2 - lam_t**2)), lam_t


def _flt_ambiente(
    p: pi.PerfilI, fy: float, Lb: float, Cb: float
) -> tuple[float, float, float, float, float]:
    """NBR 8800 (Anexo G) para I duplamente simétrico: λ, λ_p, λ_r, M_r e M_cr (N·mm)."""
    E = pi.E_ACO
    sigma_r = 0.3 * fy
    W = p.Wx
    lam = Lb / p.ry
    lam_p = 1.76 * math.sqrt(E / fy)
    beta1 = (fy - sigma_r) * W / (E * p.J)
    lam_r = (
        1.38
        * math.sqrt(p.Iy * p.J)
        / (p.ry * p.J * beta1)
        * math.sqrt(1 + math.sqrt(1 + 27 * p.Cw * beta1**2 / p.Iy))
    )
    Mr = (fy - sigma_r) * W
    Mcr = (
        Cb
        * math.pi**2
        * E
        * p.Iy
        / Lb**2
        * math.sqrt(p.Cw / p.Iy * (1 + 0.039 * p.J * Lb**2 / p.Cw))
    )
    return lam, lam_p, lam_r, Mr, Mcr


def calcular(e: EntradaIncendio) -> ResultadoIncendio:
    p = obter_perfil(e)
    fy = pi.ACOS[e.aco][0]
    avisos = list(pi.avisos_do_perfil(p))
    u = perimetro(p, e.exposicao)
    u_A = u / p.A * 1000  # m⁻¹
    protegido = e.protecao != "Sem proteção"
    ref = "ABNT NBR 14323, "
    curva: list[tuple[float, float, float]] = []
    if e.temperatura_informada > 0:
        theta = e.temperatura_informada
        origem = "informada"
    else:
        theta, curva = temperatura_do_aco(
            u_A, e.trrf, protegido=protegido, tm=e.tm / 1000, lam=e.lambda_m, rho_m=e.rho_m,
            c_m=e.c_m,
        )  # fmt: skip
        origem = f"curva-padrão até {_n(e.trrf, 0)} min, " + (
            f"protegido com {e.protecao.lower()} de {_n(e.tm, 0)} mm"
            if protegido
            else "sem proteção"
        )
    ky, kE = fatores(theta)
    psi = OCUPACOES.get(e.ocupacao, 0.42)
    S = e.gama_g * e.G_k + psi * e.Q_k
    termicas = [
        vm.linha_info("Fator de massividade", u_A, "m⁻¹", ref + "6.4 e 8.5.1.1.4",
                      f"u/A = {_n(u, 0)} mm / {_n(p.A, 0)} mm² ({e.exposicao.lower()})"),
        vm.linha_info("Temperatura do aço", theta, "°C", ref + "8.5.1", origem),
        vm.linha_info("Fatores de redução", ky, "", ref + "5.1.1.1 (Tabela 1)",
                      f"k_y,θ = {_n(ky, 3)}, k_E,θ = {_n(kE, 4)}"),
        vm.linha_info("Esforço de cálculo em incêndio", S, "kN·m" if e.elemento == VIGA else "kN",
                      ref + "6.2.1", f"γ_g·G + ψ·Q = {_n(e.gama_g, 2)}·{_n(e.G_k, 1)} + "
                      f"{_n(psi, 2)}·{_n(e.Q_k, 1)}"),
    ]  # fmt: skip
    if protegido and e.temperatura_informada <= 0 and u_A < 10:
        avisos.append("u/A abaixo de 10 m⁻¹.")
    linhas: list[Verificacao] = []
    if e.elemento == TIRANTE:
        rd = ky * p.A * fy / 1000
        linhas.append(Verificacao("Tração em incêndio", S, rd, "kN", ref + "8.4.1.1",
                                  "N_fi,Rd = k_y,θ·A_g·f_y"))  # fmt: skip
    elif e.elemento == PILAR:
        L = e.K * e.L
        Ne = min(math.pi**2 * pi.E_ACO * p.Ix / L**2, math.pi**2 * pi.E_ACO * p.Iy / L**2)
        lam0 = math.sqrt(p.A * fy / Ne)
        chi, lam_t = chi_incendio(lam0, ky, kE, fy)
        rd = chi * ky * p.A * fy / 1000
        linhas.append(
            Verificacao("Compressão em incêndio", S, rd, "kN", ref + "8.4.2.2",
                        f"χ_fi·k_y,θ·A_g·f_y, λ₀ = {_n(lam0, 3)} (menor inércia, K·L = {_n(L, 0)} mm), "
                        f"λ₀,θ = {_n(lam_t, 3)}, χ_fi = {_n(chi, 3)}")
        )  # fmt: skip
        raiz = math.sqrt(pi.E_ACO / fy)
        if p.bf / (2 * p.tf) > 0.56 * raiz or p.h_interna / p.tw > 1.49 * raiz:
            avisos.append("Seção com elemento esbelto à compressão: a NBR 14323 (8.4.2.3) pede Q_fi; "
                          "o programa usa a seção compacta — confira.")  # fmt: skip
    else:
        k1 = {CONTORNO_4: 1.0, CAIXAO_4: 1.0}.get(e.exposicao, 1.40 if protegido else 1.15)
        k2 = 1.15 if e.viga_hiperestatica else 1.0
        Mpl = p.Zx * fy
        raiz = math.sqrt(pi.E_ACO / fy)
        compacta = p.bf / (2 * p.tf) <= 0.38 * raiz and p.h_interna / p.tw <= 3.76 * raiz
        if not compacta:
            avisos.append("Mesa ou alma não compacta: o programa considera só a FLT (8.4.3.2.3 para "
                          "FLM/FLA não aplicado) — confira.")  # fmt: skip
        lam, lam_p, lam_r, Mr, Mcr = _flt_ambiente(p, fy, e.L, e.Cb)
        teto = k1 * k2 * ky * Mpl
        if lam <= lam_p:
            M = teto
            faixa = "λ ≤ λ_p"
        elif lam <= lam_r:
            M = min(e.Cb * ky * (Mpl - (Mpl - Mr) * (lam - lam_p) / (lam_r - lam_p)), teto)
            faixa = "λ_p < λ ≤ λ_r"
        else:
            M = min(kE * Mcr, teto)
            faixa = "λ > λ_r (k_E,θ·M_cr)"
        linhas.append(
            Verificacao("Flexão em incêndio", S, M / 1e6, "kN·m", ref + "8.4.3.2.3",
                        f"FLT: {faixa}, λ = L_b/r_y = {_n(lam, 1)}, λ_p = {_n(lam_p, 1)}, "
                        f"λ_r = {_n(lam_r, 1)}; κ₁ = {_n(k1, 2)}, κ₂ = {_n(k2, 2)}")
        )  # fmt: skip
        avisos.append(
            "Viga: só o momento fletor; o cortante e a interação com força normal ficam fora."
        )
    grupos = [
        vm.Grupo("Temperatura e combinação", termicas),
        vm.Grupo("Resistência a quente", linhas),
    ]
    return ResultadoIncendio(e, p, fy, theta, ky, kE, u_A, curva, grupos, avisos)


def registro(r: ResultadoIncendio) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "elemento": e.elemento,
        "perfil": f"{r.perfil.descricao}; {e.aco}",
        "comprimento": f"L = {_n(e.L, 0)} mm, K = {_n(e.K, 2)}, C_b = {_n(e.Cb, 2)}",
        "exposicao": e.exposicao,
        "trrf_min": e.trrf,
        "protecao": (
            "sem proteção"
            if e.protecao == "Sem proteção"
            else f"{e.protecao}, {_n(e.tm, 0)} mm (λ = {_n(e.lambda_m, 3)} W/m·°C, ρ = "
            f"{_n(e.rho_m, 0)} kg/m³, c = {_n(e.c_m, 0)} J/kg·°C)"
        ),
        "esforcos": f"G_k = {_n(e.G_k, 1)}, Q_k = {_n(e.Q_k, 1)}; {e.ocupacao}",
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Incêndio — {e.elemento.split(' (')[0]} {r.perfil.nome}, TRRF {_n(e.trrf, 0)} min",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Método simplificado da ABNT NBR 14323: temperatura uniforme do aço pela curva-padrão "
            "(8.5.1), fatores de redução da Tabela 1 e resistências de 8.4 na combinação "
            "excepcional de 6.2.1."
        ),
        premissas=[
            "Elemento interno, temperatura uniforme na seção e ao longo do comprimento.",
            "Esforços de restrição térmica desprezados (8.2.2).",
            "Propriedades da proteção típicas, a confirmar com o fabricante.",
            "Na FLT entre λ_p e λ_r, k_y,θ aplicado à interpolação entre M_pl e M_r.",
        ],
        referencias=REFERENCIAS,
        objeto=f"O elemento {r.perfil.nome}",
        alertas=r.avisos,
    )


def com(e: EntradaIncendio, **mudancas: Any) -> EntradaIncendio:
    return replace(e, **mudancas)
