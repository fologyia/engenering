"""Torção nas barras do modelo pela ABNT NBR 8800:2008, 5.5.2.

Os esforços vêm de :mod:`core.verificacao_barras`, em kN e kN·m, um por combinação e ponto da barra.

* **Tubos redondos e retangulares** (5.5.2.1 e 5.5.2.2): momento de torção resistente T_Rd, com
  escoamento e flambagem por torção. Até 20 % de T_Rd a torção pode ser desprezada; acima disso vale
  (N/N_Rd + M/M_Rd) + (V/V_Rd + T/T_Rd)² ≤ 1,0. A norma escreve a interação para um eixo; aqui os dois
  momentos e os dois cortantes entram somados, a favor da segurança.
* **Seções quaisquer** (5.5.2.3, I, U, T, cantoneira, barra maciça): tensões pela teoria da
  elasticidade, σ_Sd ≤ f_y/γ_a1 e τ_Sd ≤ 0,6·f_y/γ_a1. O τ da torção é o de Saint-Venant,
  τ = T·t/J, com t a parede mais grossa (empenamento livre); o do cortante é a média na alma ou nas
  mesas; os dois somam, a favor da segurança. Para não reprovar barra por um torque que é só ruído
  do modelo, a página usa nos perfis abertos o mesmo corte dos tubos: τ da torção até 20 % de
  0,6·f_y/γ_a1 fica como informação.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core.verificacao import Verificacao

E_ACO = 200_000.0  # MPa
GAMMA_A1 = 1.10
FRACAO_DESPREZIVEL = 0.20
REFERENCIA_TUBOS = "NBR 8800:2008 5.5.2.1 e 5.5.2.2"
REFERENCIA_SECOES = "NBR 8800:2008 5.5.2.3"
INFORMATIVO = "Torção (informativo)"
_ZERO = 1e-9  # kN·m


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


@dataclass(frozen=True)
class EsforcoDeTorcao:
    """Esforços de cálculo num ponto (kN e kN·m), já com o B₂. Tração positiva."""

    combinacao: str
    ponto: str
    n: float
    m_forte: float
    m_fraco: float
    v_forte: float
    v_fraco: float
    t: float


@dataclass(frozen=True)
class Resistencias:
    """As resistências que a verificação da barra já calculou (kN e kN·m)."""

    nc_rd: float | None
    nt_rd: float | None
    mx_rd: float | None
    my_rd: float | None
    v_alma_rd: float | None
    v_mesas_rd: float | None


def _razao(solicitante: float, resistente: float | None) -> float:
    if not resistente or resistente <= 0:
        return 0.0 if abs(solicitante) < 1e-12 else math.inf
    return abs(solicitante) / resistente


# ---------------------------------------------------------------------------------------------
# Tubos: 5.5.2.1
# ---------------------------------------------------------------------------------------------


def momento_resistente_tubo_circular(
    d_mm: float, t_mm: float, comprimento_mm: float, fy: float
) -> tuple[float, str]:
    """T_Rd (kN·m) pela 5.5.2.1.2: o maior dos dois, cada um limitado a 0,6·W_T·f_y/γ_a1."""
    if d_mm <= 0 or t_mm <= 0 or t_mm * 2 >= d_mm:
        raise ValueError("Tubo circular sem diâmetro e espessura coerentes.")
    wt = math.pi * (d_mm - t_mm) ** 2 * t_mm / 2.0
    escoamento = 0.60 * wt * fy / GAMMA_A1
    d_t = d_mm / t_mm
    longo = 1.23 * wt * E_ACO / (d_t**1.25 * math.sqrt(max(comprimento_mm, 1.0) / d_mm)) / GAMMA_A1
    curto = 0.60 * wt * E_ACO / d_t**1.5 / GAMMA_A1
    t_rd = max(min(longo, escoamento), min(curto, escoamento))
    texto = (
        f"W_T = π(D−t)²t/2 = {_n(wt / 1e3, 1)}·10³ mm³; D/t = {_n(d_t, 1)}; "
        f"T_Rd = {_n(t_rd / 1e6, 3)} kN·m"
        + (" (escoamento)" if t_rd >= escoamento - 1e-9 else " (flambagem por torção)")
    )
    return t_rd / 1e6, texto


def momento_resistente_tubo_retangular(
    h_mm: float, b_mm: float, t_mm: float, fy: float
) -> tuple[float, str]:
    """T_Rd (kN·m) pela 5.5.2.1.3, com h = parte plana do lado maior (lado − 3t)."""
    if min(h_mm, b_mm, t_mm) <= 0 or 2 * t_mm >= min(h_mm, b_mm):
        raise ValueError("Tubo retangular sem lados e espessura coerentes.")
    wt = 2 * (b_mm - t_mm) * (h_mm - t_mm) * t_mm - 4.5 * (4 - math.pi) * t_mm**3
    plano = max(h_mm, b_mm) - 3 * t_mm
    esbeltez = plano / t_mm
    raiz = math.sqrt(E_ACO / fy)
    if esbeltez <= 2.45 * raiz:
        t_rd, regime = 0.60 * wt * fy / GAMMA_A1, "escoamento"
    elif esbeltez <= 3.07 * raiz:
        t_rd = 0.60 * wt * fy * (2.45 * raiz) / esbeltez / GAMMA_A1
        regime = "flambagem inelástica"
    elif esbeltez <= 260:
        t_rd = 0.46 * math.pi**2 * wt * E_ACO / esbeltez**2 / GAMMA_A1
        regime = "flambagem elástica"
    else:
        raise ValueError(f"h/t = {_n(esbeltez, 0)} passa de 260, o limite da 5.5.2.1.3.")
    texto = (
        f"W_T = {_n(wt / 1e3, 1)}·10³ mm³; h/t = {_n(esbeltez, 1)} ({regime}); "
        f"T_Rd = {_n(t_rd / 1e6, 3)} kN·m"
    )
    return t_rd / 1e6, texto


def _linhas_do_tubo(
    t_rd: float, texto: str, esforcos: Sequence[EsforcoDeTorcao], r: Resistencias
) -> list[Verificacao]:
    maior = max(esforcos, key=lambda e: abs(e.t))
    linhas = [
        Verificacao(
            "Torção ≤ T_Rd",
            abs(maior.t),
            t_rd,
            "kN·m",
            REFERENCIA_TUBOS,
            f"{maior.combinacao}, {maior.ponto}; {texto}",
        )
    ]
    relevantes = [e for e in esforcos if abs(e.t) > FRACAO_DESPREZIVEL * t_rd]
    if not relevantes:
        linhas.append(
            _informativo(
                f"maior torque {_n(abs(maior.t), 3)} kN·m, até 20 % de T_Rd: pela 5.5.2.2 a torção "
                "pode ser desprezada, e vale a interação de 5.5.1"
            )
        )
        return linhas

    def indice(e: EsforcoDeTorcao) -> float:
        n_rd = r.nc_rd if e.n < 0 else r.nt_rd
        flexao = _razao(e.n, n_rd) + _razao(e.m_forte, r.mx_rd) + _razao(e.m_fraco, r.my_rd)
        corte = _razao(e.v_forte, r.v_alma_rd) + _razao(e.v_fraco, r.v_mesas_rd)
        return flexao + (corte + _razao(e.t, t_rd)) ** 2

    pior = max(relevantes, key=indice)
    linhas.append(
        Verificacao(
            "Torção: interação N + M + V + T",
            indice(pior),
            1.0,
            "—",
            REFERENCIA_TUBOS,
            f"{pior.combinacao}, {pior.ponto}: (N/N_Rd + Mx/Mx,Rd + My/My,Rd) + "
            f"(V/V_Rd + T/T_Rd)² com T = {_n(abs(pior.t), 3)} kN·m; os dois eixos somados, a "
            "favor da segurança",
        )
    )
    return linhas


# ---------------------------------------------------------------------------------------------
# Seções quaisquer: 5.5.2.3
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SecaoAberta:
    """O que a tensão elástica precisa saber da seção (mm)."""

    j_mm4: float
    espessura_mm: float  # a parede onde τ da torção é maior (a mais grossa)
    area_mm2: float
    wx_mm3: float | None
    wy_mm3: float | None
    area_alma_mm2: float | None  # cortante no plano da alma
    area_mesas_mm2: float | None  # cortante nas mesas
    empenamento: bool  # I, U, T: com empenamento impedido o σ cresce, e aqui não entra


def _informativo(texto: str) -> Verificacao:
    return Verificacao(INFORMATIVO, None, None, "—", "—", texto, status="INFO", tipo="informativo")


def _linhas_da_secao_aberta(
    s: SecaoAberta, fy: float, esforcos: Sequence[EsforcoDeTorcao]
) -> list[Verificacao]:
    if s.j_mm4 <= 0:
        maior = max(esforcos, key=lambda e: abs(e.t))
        return [
            Verificacao(
                "Torção",
                None,
                None,
                "—",
                REFERENCIA_SECOES,
                f"maior torque {_n(abs(maior.t), 3)} kN·m, mas o perfil não tem a constante de "
                "torção J no catálogo: cadastre o J para a verificação",
                status="ALERTA",
                tipo="informativo",
            )
        ]
    tau_rd = 0.60 * fy / GAMMA_A1
    sigma_rd = fy / GAMMA_A1

    def tau_torcao(e: EsforcoDeTorcao) -> float:
        return abs(e.t) * 1e6 * s.espessura_mm / s.j_mm4

    def tau_cortante(e: EsforcoDeTorcao) -> float:
        alma = abs(e.v_forte) * 1e3 / s.area_alma_mm2 if s.area_alma_mm2 else 0.0
        mesas = abs(e.v_fraco) * 1e3 / s.area_mesas_mm2 if s.area_mesas_mm2 else 0.0
        return max(alma, mesas)

    def sigma(e: EsforcoDeTorcao) -> float:
        valor = abs(e.n) * 1e3 / s.area_mm2
        if s.wx_mm3:
            valor += abs(e.m_forte) * 1e6 / s.wx_mm3
        if s.wy_mm3:
            valor += abs(e.m_fraco) * 1e6 / s.wy_mm3
        return valor

    maior = max(esforcos, key=tau_torcao)
    tau_maior = tau_torcao(maior)
    if tau_maior <= FRACAO_DESPREZIVEL * tau_rd:
        return [
            _informativo(
                f"maior torque {_n(abs(maior.t), 3)} kN·m ({maior.combinacao}, {maior.ponto}) dá "
                f"τ = T·t/J = {_n(tau_maior, 1)} MPa, até 20 % de 0,6·f_y/γ_a1 = {_n(tau_rd, 0)} "
                "MPa: desprezado, como nos tubos (5.5.2.2)"
            )
        ]
    relevantes = [e for e in esforcos if tau_torcao(e) > FRACAO_DESPREZIVEL * tau_rd]
    pior_tau = max(relevantes, key=lambda e: tau_torcao(e) + tau_cortante(e))
    pior_sigma = max(relevantes, key=sigma)
    aviso = (
        "; empenamento livre: com as pontas impedidas de empenar (ligação rígida nas mesas), a "
        "tensão normal do empenamento soma, e a barra pede análise própria"
        if s.empenamento
        else ""
    )
    return [
        Verificacao(
            "Torção: cisalhamento τ_T + τ_V ≤ 0,6·f_y/γ_a1",
            tau_torcao(pior_tau) + tau_cortante(pior_tau),
            tau_rd,
            "MPa",
            REFERENCIA_SECOES + " b)",
            f"{pior_tau.combinacao}, {pior_tau.ponto}: τ_T = T·t/J = {_n(abs(pior_tau.t), 3)} kN·m "
            f"× {_n(s.espessura_mm, 1)} mm / {_n(s.j_mm4 / 1e4, 2)}·10⁴ mm⁴ = "
            f"{_n(tau_torcao(pior_tau), 1)} MPa; τ_V = {_n(tau_cortante(pior_tau), 1)} MPa{aviso}",
        ),
        Verificacao(
            "Torção: tensão normal elástica ≤ f_y/γ_a1",
            sigma(pior_sigma),
            sigma_rd,
            "MPa",
            REFERENCIA_SECOES + " a)",
            f"{pior_sigma.combinacao}, {pior_sigma.ponto}: σ = N/A + Mx/Wx + My/Wy, com a barra "
            "em torção, pela teoria da elasticidade",
        ),
    ]


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------


def linhas_de_torcao(
    tipo: str,
    dims: dict[str, float],
    secao: SecaoAberta | None,
    fy: float,
    esforcos: Sequence[EsforcoDeTorcao],
    resistencias: Resistencias,
    comprimento_mm: float,
) -> list[Verificacao]:
    """As linhas da torção da barra. ``tipo`` é o da seção do módulo de normas (tubo_circ, …)."""
    if not esforcos or max(abs(e.t) for e in esforcos) < _ZERO:
        return [_informativo("a barra não tem momento de torção no modelo")]
    if tipo == "tubo_circ":
        t_rd, texto = momento_resistente_tubo_circular(dims["D"], dims["t"], comprimento_mm, fy)
        return _linhas_do_tubo(t_rd, texto, esforcos, resistencias)
    if tipo == "tubo_ret":
        t_rd, texto = momento_resistente_tubo_retangular(dims["H"], dims["B"], dims["t"], fy)
        return _linhas_do_tubo(t_rd, texto, esforcos, resistencias)
    if secao is None:
        return [_informativo("seção sem dados para a torção")]
    return _linhas_da_secao_aberta(secao, fy, esforcos)
