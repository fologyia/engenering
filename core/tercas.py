"""Terças e travessas de fechamento em perfil U enrijecido formado a frio — ABNT NBR 14762:2010.

A terça biapoiada entre pórticos, com linhas de corrente (tirantes) no vão, sob duas combinações:

* gravidade (peso + sobrecarga): mesa de cima comprimida — travada pela telha, se ela for
  parafusada, ou com a FLT entre tirantes;
* sucção do vento: mesa de baixo comprimida e livre — fator R do Anexo F (telha de aço
  parafusada na mesa tracionada) quando as condições valem, ou FLT entre tirantes.

Verificações: momento resistente pelo método da seção efetiva (9.8.2.1, k_ℓ da Tabela 13), FLT
(9.8.2.2 com M_e da 9.7.2.1), flambagem distorcional (dispensa pela Tabela 14 ou M_dist informado,
9.8.2.3), cortante (9.8.3), interação M + V (9.8.4), flexão na menor inércia entre tirantes
(9.9) e as flechas da Tabela A.1 (L/180 na gravidade, L/120 na sucção) com I efetivo (9.8.5).

Unidades: mm, MPa, N internamente; kN/m, kN e kN·m nas entradas e saídas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any

from core import perfil_i as pi
from core import steel_sections as ss
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "tercas_formadas_a_frio"
MODULO_TITULO = "Terças e travessas (perfil formado a frio)"
GAMA = 1.10  # NBR 14762, 9.8
E = 200_000.0
G = 77_000.0
NU = 0.3

ACOS_FRIO: dict[str, tuple[float, float]] = {
    "ZAR 230": (230.0, 310.0),
    "ZAR 250": (250.0, 360.0),
    "ZAR 280": (280.0, 380.0),
    "ZAR 345": (345.0, 430.0),
    "ASTM A36": (250.0, 400.0),
    "SAE 1020": (210.0, 340.0),
}

TERCA = "Terça de cobertura"
TRAVESSA = "Travessa de fechamento"
USOS = (TERCA, TRAVESSA)

REFERENCIAS = (
    "ABNT NBR 14762:2010 — Dimensionamento de estruturas de aço constituídas por perfis formados "
    "a frio: 9.8.2 (momento fletor: seção efetiva, FLT e distorcional; Tabelas 12 a 14), 9.8.3 "
    "(cortante), 9.8.4 (interação), 9.8.5 (deslocamentos), 9.9 (flexão oblíqua), Anexo A "
    "(deslocamentos máximos) e Anexo F (barras com painel conectado à mesa tracionada).",
)

#: Tabela 14: (b_f/b_w, b_w/t) → D/b_w mínimo para dispensar a distorcional
_T14_BW_T = (50.0, 100.0, 125.0, 200.0, 250.0)
_T14 = {
    0.4: (0.25, 0.12, 0.10, 0.06, 0.05),
    0.6: (0.25, 0.12, 0.10, 0.06, 0.05),
    0.8: (0.22, 0.12, 0.09, 0.06, 0.05),
    1.0: (0.22, 0.11, 0.09, 0.06, 0.05),
    1.2: (0.20, 0.11, 0.09, 0.06, 0.05),
    1.4: (0.20, 0.10, 0.09, 0.06, 0.05),
    1.6: (0.20, 0.10, 0.09, 0.06, 0.05),
    1.8: (0.19, 0.10, 0.09, 0.06, 0.05),
    2.0: (0.19, 0.10, 0.09, 0.06, 0.05),
}


@dataclass(frozen=True)
class EntradaTerca:
    uso: str = TERCA
    bw: float = 200.0  # altura nominal da alma
    bf: float = 75.0
    D: float = 20.0
    t: float = 2.65
    aco: str = "ZAR 345"
    L: float = 6000.0
    tirantes: int = 1  # linhas de corrente no vão
    inclinacao: float = 10.0  # graus (só para terça: separa as componentes)
    espacamento: float = 1500.0  # entre terças (largura de influência), mm
    g: float = 0.15  # kN/m² — telha + acessórios
    q: float = 0.25  # kN/m² — sobrecarga de cobertura
    w_succao: float = 0.60  # kN/m² — vento de sucção (perpendicular)
    w_pressao: float = 0.30  # kN/m² — vento de pressão (perpendicular)
    gama_g: float = 1.25
    gama_q: float = 1.50
    gama_w: float = 1.40
    telha_trava: bool = True  # a telha parafusada trava a mesa de cima na gravidade
    usar_anexo_f: bool = True  # sucção com o fator R (telha de aço parafusada)
    M_dist: float = 0.0  # kN·m de análise de estabilidade elástica (0 = não informado)
    flecha_gravidade: float = 180.0
    flecha_succao: float = 120.0


def validar(e: EntradaTerca) -> list[str]:
    erros: list[str] = []
    try:
        secao(e)
    except ValueError as exc:
        erros.append(f"Perfil: {exc}")
    if e.aco not in ACOS_FRIO:
        erros.append("Escolha o aço.")
    if e.L <= 0 or e.espacamento <= 0:
        erros.append("Vão e espaçamento devem ser positivos.")
    if e.tirantes < 0:
        erros.append("O número de linhas de corrente não pode ser negativo.")
    if min(e.g, e.q, e.w_succao, e.w_pressao) < 0:
        erros.append("As cargas são valores absolutos (o sentido vem da combinação).")
    if not 0 <= e.inclinacao < 60:
        erros.append("A inclinação do telhado deve ficar entre 0° e 60°.")
    return erros


def secao(e: EntradaTerca) -> ss.PerfilAco:
    return ss.perfil_c_enrijecido(
        f"Ue {pi.numero(e.bw, 0)} × {pi.numero(e.bf, 0)} × {pi.numero(e.D, 0)} × {pi.numero(e.t, 2)}",
        e.bw, e.bf, e.D, e.t,
    )  # fmt: skip


def _n(valor: float, casas: int = 2) -> str:
    return pi.numero(valor, casas)


#: Tabela 13, caso b (U e Z enrijecidos): η = b_f/b_w → k_ℓ para μ = D/b_w ≤ 0,2; 0,25; 0,3
_T13 = {
    0.2: (32.0, 25.8, 21.2), 0.3: (29.3, 23.8, 19.7), 0.4: (24.8, 20.7, 18.2),
    0.5: (18.7, 17.6, 16.0), 0.6: (13.6, 13.3, 13.0), 0.7: (10.2, 10.1, 10.1),
    0.8: (7.9, 7.9, 7.9), 0.9: (6.2, 6.3, 6.3), 1.0: (5.1, 5.1, 5.1),
}  # fmt: skip


def k_local(eta: float, mu: float) -> float:
    """Tabela 13, caso b, com interpolação linear (η limitado a 0,2–1,0; μ a 0,2–0,3)."""
    eta = min(max(eta, 0.2), 1.0)
    mu = min(max(mu, 0.2), 0.3)
    linhas = sorted(_T13)

    def na_linha(v: tuple[float, float, float]) -> float:
        if mu <= 0.25:
            return v[0] + (v[1] - v[0]) * (mu - 0.2) / 0.05
        return v[1] + (v[2] - v[1]) * (mu - 0.25) / 0.05

    for e0, e1 in pairwise(linhas):
        if e0 <= eta <= e1:
            k0, k1 = na_linha(_T13[e0]), na_linha(_T13[e1])
            return k0 + (k1 - k0) * (eta - e0) / (e1 - e0)
    return na_linha(_T13[linhas[-1]])


def d_bw_minimo(eta: float, bw_t: float) -> float:
    """Tabela 14 com interpolação linear (fora da tabela, o valor da borda)."""
    linhas = sorted(_T14)
    eta = min(max(eta, linhas[0]), linhas[-1])
    bw_t = min(max(bw_t, _T14_BW_T[0]), _T14_BW_T[-1])

    def na_linha(valores: tuple[float, ...]) -> float:
        for (x0, y0), (x1, y1) in pairwise(zip(_T14_BW_T, valores, strict=True)):
            if x0 <= bw_t <= x1:
                return y0 + (y1 - y0) * (bw_t - x0) / (x1 - x0)
        return valores[-1]

    for e0, e1 in pairwise(linhas):
        if e0 <= eta <= e1:
            v0, v1 = na_linha(_T14[e0]), na_linha(_T14[e1])
            return v0 + (v1 - v0) * (eta - e0) / (e1 - e0)
    return na_linha(_T14[linhas[-1]])


def fator_reducao_local(lam: float) -> float:
    """MSE: 1 até 0,673; (1 − 0,22/λ)/λ acima."""
    return 1.0 if lam <= 0.673 else (1 - 0.22 / lam) / lam


def chi_flt(lam0: float) -> float:
    """9.8.2.2."""
    if lam0 <= 0.6:
        return 1.0
    if lam0 < 1.336:
        return 1.11 * (1 - 0.278 * lam0**2)
    return 1 / lam0**2


def fator_r(e: EntradaTerca, fy: float) -> tuple[float | None, str]:
    """Anexo F, Tabela F.1 (biapoiada, seção U) e as condições aplicáveis por geometria."""
    b_plana = e.bf - 2 * e.t
    falhas = []
    if e.bw > 292:
        falhas.append("b_w ≤ 292 mm")
    if not 60 <= e.bw / e.t <= 170:
        falhas.append("60 ≤ b_w/t ≤ 170")
    if not 2.8 <= e.bw / e.bf <= 4.5:
        falhas.append("2,8 ≤ b_w/b_f ≤ 4,5")
    if not 16 <= b_plana / e.t <= 43:
        falhas.append("16 ≤ b/t ≤ 43")
    if e.L >= 10_000:
        falhas.append("vão < 10 m")
    if fy > 410:
        falhas.append("f_y ≤ 410 MPa")
    if falhas:
        return None, "condições do Anexo F não atendidas: " + "; ".join(falhas)
    if e.bw <= 165:
        return 0.70, "b_w ≤ 165 mm: R = 0,70"
    if e.bw <= 216:
        return 0.65, "165 < b_w ≤ 216 mm: R = 0,65"
    return 0.40, "216 < b_w ≤ 292 mm (seção U): R = 0,40"


@dataclass
class ResultadoTerca:
    entrada: EntradaTerca
    perfil: ss.PerfilAco
    fy: float
    grupos: list[vm.Grupo]
    numeros: dict[str, float]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def calcular(e: EntradaTerca) -> ResultadoTerca:
    p = secao(e)
    fy = ACOS_FRIO[e.aco][0]
    W = p.ix_mm4 / (e.bw / 2)
    Wy = p.sy_mm3
    avisos: list[str] = []
    ref = "ABNT NBR 14762:2010, "
    nome_g = "Gravidade" if e.uso == TERCA else "Pressão do vento"
    # componentes por metro (kN/m = N/mm)
    a = math.radians(e.inclinacao if e.uso == TERCA else 0.0)
    s = e.espacamento / 1000
    g_n, g_t = e.g * s * math.cos(a), e.g * s * math.sin(a)
    q_n, q_t = e.q * s * math.cos(a), e.q * s * math.sin(a)
    if e.uso == TRAVESSA:
        # travessa: o peso da telha atua na menor inércia; o vento é perpendicular ao fechamento
        g_n, g_t, q_n, q_t = 0.0, e.g * s, 0.0, 0.0
    peso = p.massa_kg_m * 9.80665e-3
    if e.uso == TERCA:
        g_n += peso * math.cos(a)
        g_t += peso * math.sin(a)
    else:
        g_t += peso
    w_s, w_p = e.w_succao * s, e.w_pressao * s
    # combinações (perpendicular ao plano do fechamento: + empurra a mesa de cima)
    grav = e.gama_g * g_n + max(e.gama_q * q_n, e.gama_w * w_p)
    grav_t = e.gama_g * g_t + e.gama_q * q_t
    succ = abs(1.0 * g_n - e.gama_w * w_s)
    L = e.L
    vao_menor = L / (e.tirantes + 1)
    M_grav = grav * L**2 / 8
    M_succ = succ * L**2 / 8 if e.gama_w * w_s > g_n else 0.0
    V_max = max(grav, succ) * L / 2
    My = grav_t * vao_menor**2 / 8
    # local (MSE)
    k_l = k_local(e.bf / e.bw, e.D / e.bw)
    M_l = k_l * math.pi**2 * E / (12 * (1 - NU**2) * (e.bw / e.t) ** 2) * W
    lam_p = math.sqrt(W * fy / M_l)
    W_ef = W * fator_reducao_local(lam_p)
    M_esc = W_ef * fy / GAMA
    # FLT (9.8.2.2; M_e = C_b·r₀·√(N_ey·N_ez))
    x0, y0 = ss.centro_de_cisalhamento_do_perfil(p)
    Cw = ss.constante_de_empenamento_estimada(p)
    r0 = math.sqrt(p.rx_mm**2 + p.ry_mm**2 + x0**2 + y0**2)

    def m_flt(Lb: float, Cb: float) -> tuple[float, float, float]:
        Ney = math.pi**2 * E * p.iy_mm4 / Lb**2
        Nez = (math.pi**2 * E * Cw / Lb**2 + G * p.j_mm4) / r0**2
        Me = Cb * r0 * math.sqrt(Ney * Nez)
        lam0 = math.sqrt(W * fy / Me)
        chi = chi_flt(lam0)
        lam_pf = math.sqrt(chi * W * fy / M_l)
        return chi * W * fator_reducao_local(lam_pf) * fy / GAMA, lam0, chi

    grupos: list[vm.Grupo] = []
    lg: list[Verificacao] = [
        vm.linha_info("Coeficiente de flambagem local", k_l, "", ref + "Tabela 13 (caso b)",
                      f"η = b_f/b_w = {_n(e.bf / e.bw, 3)}, μ = D/b_w = {_n(e.D / e.bw, 3)}"),
        Verificacao(f"{nome_g}: escoamento da seção efetiva", M_grav / 1e6, M_esc / 1e6, "kN·m",
                    ref + "9.8.2.1 b) (MSE)",
                    f"W_ef·f_y/γ, λ_p = {_n(lam_p, 3)}, W_ef = {_n(W_ef / 1000, 2)} cm³; "
                    f"q_d = {_n(grav, 3)} kN/m"),
    ]  # fmt: skip
    if not (e.telha_trava and e.uso == TERCA):
        Mr, lam0, chi = m_flt(vao_menor, 1.13)
        lg.append(
            Verificacao(f"{nome_g}: flambagem lateral com torção", M_grav / 1e6, Mr / 1e6, "kN·m",
                        ref + "9.8.2.2", f"L_b = {_n(vao_menor, 0)} mm (entre tirantes), C_b = 1,13, "
                        f"λ₀ = {_n(lam0, 3)}, χ_FLT = {_n(chi, 3)}")
        )  # fmt: skip
    else:
        avisos.append("Gravidade: a telha parafusada trava a mesa de cima comprimida (sem FLT).")
    # sucção
    if M_succ > 0:
        R, texto_R = fator_r(e, fy)
        if e.usar_anexo_f and R is not None and e.uso == TERCA:
            lg.append(
                Verificacao("Sucção: mesa comprimida livre (fator R)", M_succ / 1e6,
                            R * W_ef * fy / GAMA / 1e6, "kN·m", ref + "Anexo F",
                            f"R·W_ef·f_y/γ, {texto_R}; q_d = 1,0·g − γ_w·w = {_n(-succ, 3)} kN/m")
            )  # fmt: skip
        else:
            if e.usar_anexo_f and e.uso == TERCA:
                avisos.append(f"Sucção: {texto_R}; usada a FLT entre tirantes.")
            Mr, lam0, chi = m_flt(vao_menor, 1.13)
            lg.append(
                Verificacao("Sucção: flambagem lateral com torção", M_succ / 1e6, Mr / 1e6, "kN·m",
                            ref + "9.8.2.2", f"mesa de baixo comprimida, L_b = {_n(vao_menor, 0)} mm, "
                            f"λ₀ = {_n(lam0, 3)}, χ_FLT = {_n(chi, 3)}")
            )  # fmt: skip
    # distorcional
    dmin = d_bw_minimo(e.bf / e.bw, e.bw / e.t)
    if e.D / e.bw >= dmin:
        lg.append(vm.linha_limite("Flambagem distorcional (dispensa)", e.D / e.bw, dmin, "",
                                  ref + "9.8.2.3 e Tabela 14", "D/b_w ≥ valor da Tabela 14",
                                  minimo=True))  # fmt: skip
    elif e.M_dist > 0:
        lam_d = math.sqrt(W * fy / (e.M_dist * 1e6))
        chi_d = fator_reducao_local(lam_d)
        lg.append(
            Verificacao("Flambagem distorcional", max(M_grav, M_succ) / 1e6,
                        chi_d * W * fy / GAMA / 1e6, "kN·m", ref + "9.8.2.3",
                        f"χ_dist·W·f_y/γ, M_dist = {_n(e.M_dist, 2)} kN·m (análise de estabilidade), "
                        f"λ_dist = {_n(lam_d, 3)}")
        )  # fmt: skip
    else:
        lg.append(
            vm.linha_alerta("Flambagem distorcional", ref + "9.8.2.3 e Tabela 14",
                            f"D/b_w = {_n(e.D / e.bw, 3)} < {_n(dmin, 3)} (Tabela 14): informe M_dist "
                            "de uma análise de estabilidade elástica (ex.: faixas finitas)")
        )  # fmt: skip
    # cortante e interação
    h = e.bw - 2 * e.t
    kv = 5.0
    r1, r2 = 1.08 * math.sqrt(E * kv / fy), 1.4 * math.sqrt(E * kv / fy)
    esb = h / e.t
    if esb <= r1:
        VRd = 0.6 * fy * h * e.t / GAMA
    elif esb <= r2:
        VRd = 0.65 * e.t**2 * math.sqrt(kv * fy * E) / GAMA
    else:
        VRd = 0.905 * E * kv * e.t**3 / h / GAMA
    lg.append(Verificacao("Cortante", V_max / 1000, VRd / 1000, "kN", ref + "9.8.3",
                          f"h/t = {_n(esb, 1)}, k_v = 5"))  # fmt: skip
    M_rd_min = min(v.resistente for v in lg if v.unidade == "kN·m" and v.resistente) * 1e6
    q_int = max(grav, succ)
    M_q, V_q = 3 * q_int * L**2 / 32, q_int * L / 4  # a L/4 do apoio
    lg.append(
        Verificacao("Interação momento × cortante (a L/4)",
                    (M_q / M_rd_min) ** 2 + (V_q / VRd) ** 2, 1.0, "", ref + "9.8.4",
                    "(M/M_Rd)² + (V/V_Rd)²")
    )  # fmt: skip
    # menor inércia entre tirantes (9.9: soma das razões)
    if My > 0:
        MyRd = Wy * fy / GAMA
        lg.append(
            Verificacao("Flexão oblíqua (gravidade)", M_grav / M_esc + My / MyRd, 1.0, "",
                        ref + "9.9", f"M_x/M_x,Rd + M_y/M_y,Rd, M_y = q_t·(L/(n+1))²/8 com "
                        f"{e.tirantes} linha(s) de corrente; M_y,Rd com W_y bruto")
        )  # fmt: skip
    grupos.append(vm.Grupo("Estado-limite último", lg))

    # flechas (serviço) com I efetivo (MSE)
    def i_ef(M_serv: float) -> float:
        lam = math.sqrt(M_serv / M_l) if M_serv > 0 else 0.0
        return p.ix_mm4 * fator_reducao_local(lam)

    serv_g = g_n + max(q_n, w_p)
    d_g = 5 * serv_g * L**4 / (384 * E * i_ef(serv_g * L**2 / 8))
    d_s = 5 * w_s * L**4 / (384 * E * i_ef(w_s * L**2 / 8))
    grupos.append(
        vm.Grupo(
            "Deslocamentos",
            [
                vm.linha_limite(f"Flecha na {nome_g.lower()}", d_g, L / e.flecha_gravidade, "mm",
                                ref + "Anexo A (Tabela A.1) e 9.8.5",
                                f"g + q (ou pressão) característicos; L/{_n(e.flecha_gravidade, 0)}"),
                vm.linha_limite("Flecha na sucção", d_s, L / e.flecha_succao, "mm",
                                ref + "Anexo A (Tabela A.1, nota f)",
                                f"só o vento de sucção característico; L/{_n(e.flecha_succao, 0)}"),
            ],
        )
    )  # fmt: skip
    avisos.append(
        "C_w do perfil U estimado sem os enrijecedores de borda (a favor da segurança na FLT); "
        "dimensões nominais sem os raios de dobra."
    )
    numeros = {"q_grav": grav, "q_succ": succ, "M_grav": M_grav / 1e6, "M_succ": M_succ / 1e6,
               "W": W, "W_ef": W_ef, "k_l": k_l, "lam_p": lam_p}  # fmt: skip
    return ResultadoTerca(e, p, fy, grupos, numeros, avisos)


def registro(r: ResultadoTerca) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "uso": e.uso,
        "perfil": f"{r.perfil.nome} mm, {e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "vao": f"L = {_n(e.L, 0)} mm, {e.tirantes} linha(s) de corrente, espaçamento {_n(e.espacamento, 0)} mm",
        "cargas": (
            f"g = {_n(e.g, 2)}, q = {_n(e.q, 2)}, sucção {_n(e.w_succao, 2)}, pressão "
            f"{_n(e.w_pressao, 2)} kN/m²; inclinação {_n(e.inclinacao, 0)}°"
        ),
        "coeficientes": f"γ_g = {_n(e.gama_g)}, γ_q = {_n(e.gama_q)}, γ_w = {_n(e.gama_w)}",
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"{e.uso} — {r.perfil.nome}, vão {_n(e.L / 1000, 2)} m",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Perfil U enrijecido formado a frio pela ABNT NBR 14762:2010: método da seção "
            "efetiva, FLT, distorcional, cortante, interação, flexão oblíqua entre linhas de "
            "corrente e flechas da Tabela A.1."
        ),
        premissas=[
            "Barra biapoiada com carga uniforme; combinações de gravidade (γ_g·g + γ_q·q ou "
            "vento de pressão) e de sucção (1,0·g − γ_w·w).",
            "As linhas de corrente seguram a componente paralela ao telhado e travam a mesa "
            "comprimida (L_b = vão/(n + 1)).",
            "Sucção com o fator R do Anexo F quando as condições geométricas valem; as de "
            "montagem (parafusos, telha, traspasse) cabem ao projeto.",
        ],
        referencias=REFERENCIAS,
        objeto=f"A {e.uso.lower()}",
        alertas=r.avisos,
    )


def com(e: EntradaTerca, **mudancas: Any) -> EntradaTerca:
    return replace(e, **mudancas)
