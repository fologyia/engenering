"""Viga mista de aço e concreto biapoiada, com conectores tipo pino com cabeça (stud).

ABNT NBR 8800:2025, Anexo L, para a viga de mezanino ou de piso com laje de concreto (maciça ou
com fôrma de aço incorporada de nervuras perpendiculares à viga):

* largura efetiva (L.2.2.1), η_c, f_cd e o módulo do concreto (4.6.3.1);
* força resistente de um conector (L.4.2.1), ΣQ_Rd entre o meio do vão e o apoio;
* momento resistente plástico: interação completa com a linha neutra na laje ou no perfil, ou
  interação parcial (L.2.3.1.1.1 a) a c)); alma esbelta pelo método elástico (L.2.3.1.2);
* grau de interação mínimo (L.2.3.1.1.2);
* cortante só no perfil (L.3.1);
* construção não escorada: o perfil sozinho na concretagem e a tensão em serviço (L.2.3.2);
* flecha com o momento de inércia efetivo (L.1.2.2) e a fluência (α_E × 3 nas permanentes);
* espaçamentos e diâmetro dos conectores (L.4.3 e L.4.4).

Carga uniforme. Unidades: mm, MPa, N internamente; kN, kN/m e kN·m nas entradas e saídas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from core import nbr8800 as nb
from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "viga_mista"
MODULO_TITULO = "Viga mista"
GAMA_C = 1.40
GAMA_CS = 1.25  # L.4.2.1.1

#: posição do conector → (R_g, R_p, rótulo) — L.4.2.1.2 e L.4.2.1.3
POSICOES: dict[str, tuple[float, float]] = {
    "Soldado no perfil (laje maciça)": (1.00, 0.75),
    "Fôrma perpendicular, 1 por nervura, e_mh ≥ 50 mm": (1.00, 0.75),
    "Fôrma perpendicular, 1 por nervura, e_mh < 50 mm": (1.00, 0.60),
    "Fôrma perpendicular, 2 por nervura, e_mh ≥ 50 mm": (0.85, 0.75),
    "Fôrma perpendicular, 2 por nervura, e_mh < 50 mm": (0.85, 0.60),
    "Fôrma perpendicular, 3 ou mais por nervura": (0.70, 0.60),
}
BRITAS = {"Basalto ou diabásio (α_e = 1,2)": 1.2, "Granito ou gnaisse (α_e = 1,0)": 1.0,
          "Calcário (α_e = 0,9)": 0.9, "Arenito (α_e = 0,7)": 0.7}  # fmt: skip

REFERENCIAS = (
    "ABNT NBR 8800:2025 — Anexo L (normativo) Vigas mistas de aço e concreto: L.1.2 "
    "(deslocamentos), L.2.2 (largura efetiva), L.2.3 (momento positivo, construção escorada e "
    "não escorada), L.3 (cortante) e L.4 (conectores).",
    "ABNT NBR 8800:2025 — 4.6.3 (concreto), 5.4 (perfil isolado na construção) e Anexo B "
    "(deslocamentos).",
)


@dataclass(frozen=True)
class EntradaMista:
    familia: str = pi.FAMILIA_W
    perfil: str = "W 410 x 38,8"
    d: float = 400.0
    bf: float = 180.0
    tf: float = 12.5
    tw: float = 8.0
    aco: str = "ASTM A572 Gr 50"
    gama_a1: float = pi.GAMA_A1
    L: float = 8000.0
    s_esquerda: float = 2500.0  # até a viga vizinha (0 = borda de laje)
    s_direita: float = 2500.0
    balanco_esquerda: float = 0.0  # quando borda: distância do eixo à borda da laje
    balanco_direita: float = 0.0
    tc: float = 100.0  # concreto acima da fôrma (ou laje maciça)
    hF: float = 0.0  # altura da fôrma de aço (0 = laje maciça)
    fck: float = 25.0
    brita: str = "Granito ou gnaisse (α_e = 1,0)"
    diametro_conector: float = 19.0
    fu_conector: float = 415.0
    posicao: str = "Soldado no perfil (laje maciça)"
    conectores: int = 24  # entre o meio do vão e cada apoio
    por_linha: int = 1
    # cargas características (kN/m)
    g1: float = 7.0  # antes da cura: perfil, laje fresca, fôrma
    q_construcao: float = 2.5  # sobrecarga de construção (×largura de influência)
    g2: float = 2.5  # depois da cura: revestimento, forro, paredes leves
    q: float = 12.5  # sobrecarga de uso
    gama_g: float = 1.35
    gama_q: float = 1.50
    gama_construcao: float = 1.30
    escorada: bool = False
    Lb_construcao: float = 0.0  # destravado na concretagem (0 = contido pela fôrma de aço)
    flecha_limite: float = 350.0
    contraflecha: float = 15.0


def obter_perfil(e: EntradaMista) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw)
    return pi.perfil(e.perfil)


def validar(e: EntradaMista) -> list[str]:
    erros: list[str] = []
    try:
        obter_perfil(e)
    except (ValueError, KeyError) as exc:
        erros.append(f"Perfil: {exc}")
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço.")
    if e.L <= 0 or e.tc <= 0:
        erros.append("Vão e espessura da laje devem ser positivos.")
    if not 20 <= e.fck <= 50:
        erros.append("A NBR 8800 vale para f_ck de 20 a 50 MPa (4.6.3.1).")
    if e.s_esquerda < 0 or e.s_direita < 0 or e.hF < 0:
        erros.append("Distâncias não podem ser negativas.")
    if (e.s_esquerda == 0 and e.balanco_esquerda <= 0) or (
        e.s_direita == 0 and e.balanco_direita <= 0
    ):
        erros.append("Na borda (viga vizinha = 0), informe a distância do eixo à borda da laje.")
    if e.conectores < 1 or e.por_linha < 1:
        erros.append("Informe pelo menos um conector.")
    if e.diametro_conector <= 0 or e.fu_conector <= 0:
        erros.append("Conector: diâmetro e f_u positivos.")
    if e.posicao not in POSICOES:
        erros.append("Escolha a posição do conector.")
    if min(e.g1, e.g2, e.q, e.q_construcao) < 0:
        erros.append("As cargas não podem ser negativas.")
    return erros


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def largura_efetiva(e: EntradaMista) -> tuple[float, str]:
    """L.2.2.1.1: soma dos dois lados, cada um o menor de L/8, metade da distância à vizinha e
    a distância à borda."""
    partes: list[float] = []
    for s, borda in ((e.s_esquerda, e.balanco_esquerda), (e.s_direita, e.balanco_direita)):
        lado = e.L / 8
        lado = min(lado, s / 2) if s > 0 else min(lado, borda)
        partes.append(lado)
    return sum(partes), f"{_n(partes[0], 0)} + {_n(partes[1], 0)} mm (L/8 = {_n(e.L / 8, 0)} mm)"


def modulo_do_concreto(fck: float, alfa_e: float) -> float:
    """4.6.3.1: E_c = 0,85·α_e·5600·√f_ck (secante)."""
    return 0.85 * alfa_e * 5600 * math.sqrt(fck)


def resistencia_conector(e: EntradaMista) -> tuple[float, str]:
    """L.4.2.1.1: o menor de ½·A_cs·√(f_ck·E_c)/γ_cs e R_g·R_p·A_cs·f_ucs/γ_cs (N)."""
    Acs = math.pi * e.diametro_conector**2 / 4
    Ec = modulo_do_concreto(e.fck, BRITAS.get(e.brita, 1.0))
    Rg, Rp = POSICOES[e.posicao]
    concreto = 0.5 * Acs * math.sqrt(e.fck * Ec) / GAMA_CS
    aco = Rg * Rp * Acs * e.fu_conector / GAMA_CS
    if concreto <= aco:
        return concreto, f"½·A_cs·√(f_ck·E_c)/γ_cs (concreto governa), E_c = {_n(Ec, 0)} MPa"
    return aco, f"R_g·R_p·A_cs·f_ucs/γ_cs (aço governa), R_g = {_n(Rg, 2)}, R_p = {_n(Rp, 2)}"


@dataclass
class SecaoPlastica:
    caso: str
    M_Rd: float  # N·mm
    a: float
    yp: float
    Ccd: float
    Cad: float
    Tad: float


def momento_plastico(
    p: pi.PerfilI,
    fyd: float,
    Ccd_max: float,
    somaQ: float,
    tc: float,
    hF: float,
    b: float,
    fcd_ef: float,
) -> SecaoPlastica:
    """L.2.3.1.1.1 a) a c) para o perfil I duplamente simétrico (áreas sem os raios)."""
    Aaf = p.bf * p.tf
    hw = p.d - 2 * p.tf
    Aaw = hw * p.tw
    Aa = 2 * Aaf + Aaw
    Aa_fyd = Aa * fyd
    if somaQ >= Aa_fyd and Ccd_max >= Aa_fyd:
        Tad = Aa_fyd
        a = Tad / (fcd_ef * b)
        M = Tad * (p.d / 2 + hF + tc - a / 2)
        return SecaoPlastica(
            "a) interação completa, linha neutra na laje", M, a, 0.0, Tad, 0.0, Tad
        )
    completa = somaQ >= Ccd_max
    Ccd = Ccd_max if completa else somaQ
    Cad = 0.5 * (Aa_fyd - Ccd)
    if Cad <= Aaf * fyd:
        yp = Cad / (Aaf * fyd) * p.tf
        A_c = p.bf * yp
        yc = yp / 2
    else:
        yp = p.tf + hw * (Cad - Aaf * fyd) / (Aaw * fyd)
        alma = p.tw * (yp - p.tf)
        A_c = Aaf + alma
        yc = (Aaf * p.tf / 2 + alma * (p.tf + (yp - p.tf) / 2)) / A_c
    A_t = Aa - A_c
    # momento estático da parte tracionada em relação à face inferior
    yt = (Aa * p.d / 2 - A_c * (p.d - yc)) / A_t
    Tad = Ccd + Cad
    if completa:
        a = tc
        M = Cad * (p.d - yt - yc) + Ccd * (tc / 2 + hF + p.d - yt)
        caso = "b) interação completa, linha neutra no perfil"
    else:
        a = Ccd / (fcd_ef * b)
        M = Cad * (p.d - yt - yc) + Ccd * (tc - a / 2 + hF + p.d - yt)
        caso = "c) interação parcial"
    return SecaoPlastica(caso, M, a, yp, Ccd, Cad, Tad)


def secao_homogeneizada(
    p: pi.PerfilI, b: float, tc: float, hF: float, alfa: float
) -> tuple[float, float, float]:
    """L.1.2.1: (I_tr, distância da linha neutra à face inferior do perfil, distância ao topo da
    laje), sem o concreto tracionado."""
    bt = b / alfa
    H = p.d + hF + tc
    Aa = p.A
    Ac = bt * tc
    y = (Aa * p.d / 2 + Ac * (p.d + hF + tc / 2)) / (Aa + Ac)
    if y <= p.d + hF:
        Itr = p.Ix + Aa * (y - p.d / 2) ** 2 + bt * tc**3 / 12 + Ac * (p.d + hF + tc / 2 - y) ** 2
        return Itr, y, H - y
    # linha neutra na laje: (bt/2)·x² + Aa·x − Aa·(H − d/2) = 0
    x = (-Aa + math.sqrt(Aa**2 + 2 * bt * Aa * (H - p.d / 2))) / bt
    Itr = p.Ix + Aa * (H - x - p.d / 2) ** 2 + bt * x**3 / 3
    return Itr, H - x, x


@dataclass
class ResultadoMista:
    entrada: EntradaMista
    perfil: pi.PerfilI
    fy: float
    b: float
    QRd: float  # N, por conector
    eta_i: float
    secao: SecaoPlastica | None
    grupos: list[vm.Grupo]
    numeros: dict[str, float]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)

    @property
    def utilizacao_maxima(self) -> float:
        return vm.utilizacao_maxima(self.linhas)


def calcular(e: EntradaMista) -> ResultadoMista:
    p = obter_perfil(e)
    fy = pi.ACOS[e.aco][0]
    E, g1 = pi.E_ACO, e.gama_a1
    fyd = fy / g1
    fcd = e.fck / GAMA_C
    eta_c = min((40 / e.fck) ** (1 / 3), 1.0)
    fcd_ef = 0.85 * eta_c * fcd
    b, texto_b = largura_efetiva(e)
    Ec = modulo_do_concreto(e.fck, BRITAS.get(e.brita, 1.0))
    alfa = E / Ec
    QRd, texto_q = resistencia_conector(e)
    somaQ = e.conectores * QRd
    Aa_id = 2 * p.bf * p.tf + (p.d - 2 * p.tf) * p.tw
    Ccd_max = fcd_ef * b * e.tc
    Fhd = min(Aa_id * fyd, Ccd_max)
    eta_i = min(somaQ / Fhd, 1.0)
    L = e.L
    ref = "ABNT NBR 8800:2025, "
    avisos = list(pi.avisos_do_perfil(p))
    # esforços (kN/m = N/mm)
    qd = e.gama_g * (e.g1 + e.g2) + e.gama_q * e.q
    MSd = qd * L**2 / 8
    VSd = qd * L / 2
    grupos: list[vm.Grupo] = []
    compacta = p.h_interna / p.tw <= 3.76 * math.sqrt(E / fy)
    linhas: list[Verificacao] = [
        vm.linha_info("Largura efetiva da laje", b, "mm", ref + "L.2.2.1.1", texto_b),
        vm.linha_info(
            "Força resistente de um conector",
            QRd / 1000,
            "kN",
            ref + "L.4.2.1.1",
            f"pino Ø {_n(e.diametro_conector, 1)} mm, " + texto_q,
        ),  # fmt: skip
        vm.linha_info(
            "Grau de interação",
            eta_i,
            "",
            ref + "L.2.3.1.1.2",
            f"η_i = ΣQ_Rd/F_hd = {_n(somaQ / 1000, 1)}/{_n(Fhd / 1000, 1)} kN "
            f"({e.conectores} conectores do apoio ao meio do vão)",
        ),  # fmt: skip
    ]
    secao: SecaoPlastica | None = None
    if compacta:
        secao = momento_plastico(p, fyd, Ccd_max, somaQ, e.tc, e.hF, b, fcd_ef)
        MRd = secao.M_Rd
        linhas.append(
            Verificacao(
                "Momento fletor (viga mista)",
                MSd / 1e6,
                MRd / 1e6,
                "kN·m",
                ref + "L.2.3.1.1.1 " + secao.caso[:2],
                f"{secao.caso}; f_cd·0,85·η_c = {_n(fcd_ef, 2)} MPa, a = {_n(secao.a, 1)} mm"
                + (f", y_p = {_n(secao.yp, 1)} mm" if secao.yp else ""),
            )
        )
        # grau de interação mínimo
        cr = max(MSd / MRd, 0.7) if MRd > 0 else 1.0
        Le = L / 1000
        eta0 = 1 - E / (580 * fy) * (0.75 - (0.030) * Le)
        cp = 1.0 if e.escorada else 0.85
        eta_lim = 0.4 * cr
        eta_min = min(max(cp * cr**2 * eta0, eta_lim), 1.0)
        if eta_i < 1.0:
            linhas.append(
                vm.linha_limite(
                    "Grau de interação mínimo",
                    eta_i,
                    eta_min,
                    "",
                    ref + "L.2.3.1.1.2",
                    f"η_i ≥ c_p·c_r²·η₀ ≥ η_lim, η₀ = {_n(eta0, 3)}, c_p = {_n(cp, 2)}, "
                    f"c_r = {_n(cr, 3)}, η_lim = {_n(eta_lim, 3)} (perfil simétrico, ρ = 0)",
                    minimo=True,
                )
            )
    else:
        Itr, y_inf, y_sup = secao_homogeneizada(p, b, e.tc, e.hF, alfa)
        Wtr_i = Itr / y_inf
        Wtr_s = Itr / y_sup
        Wa = p.Wx
        Wef = Wa + math.sqrt(eta_i) * (Wtr_i - Wa)
        linhas.append(
            Verificacao("Tensão de tração na mesa inferior", MSd / Wef, fyd, "MPa",
                        ref + "L.2.3.1.2", "alma esbelta: método elástico, σ_td = M_Sd/W_ef")
        )  # fmt: skip
        linhas.append(
            Verificacao("Tensão no topo da laje", MSd / (alfa * Wtr_s), 0.85 * fcd, "MPa",
                        ref + "L.2.3.1.2", "σ_cd = M_Sd/(α_E·(W_tr)_s) ≤ 0,85·f_cd")
        )  # fmt: skip
        avisos.append(
            "Alma com h/t_w > 3,76·√(E/f_y): o momento foi verificado pelo método elástico."
        )
    perfil_aco = p.perfil_aco()
    cis = nb.verificar_cisalhamento(perfil_aco, fy, E, VSd)
    linhas.append(
        Verificacao("Cortante (só o perfil)", VSd / 1000, cis.resistencia_N / 1000, "kN",
                    ref + "L.3.1 e 5.4.3", f"V_Rd do perfil, {cis.regime}")
    )  # fmt: skip
    grupos.append(vm.Grupo("Viga mista (estado-limite último)", linhas))
    # construção não escorada
    if not e.escorada:
        q_c = e.gama_g * e.g1 + e.gama_construcao * e.q_construcao
        Mc = q_c * L**2 / 8
        Lb = e.Lb_construcao if e.Lb_construcao > 0 else None
        flex = nb.verificar_flexao(perfil_aco, fy, E, pi.G_ACO, Mc, eixo="x",
                                   comprimento_destravado_mm=Lb, cb=1.13, soldado=p.soldado)  # fmt: skip
        Itr, y_inf, _ = secao_homogeneizada(p, b, e.tc, e.hF, alfa)
        Wef = p.Wx + math.sqrt(eta_i) * (Itr / y_inf - p.Wx)
        sigma = (e.g1 * L**2 / 8) / p.Wx + ((e.g2 + e.q) * L**2 / 8) / Wef
        grupos.append(
            vm.Grupo(
                "Construção não escorada",
                [
                    Verificacao(
                        "Perfil sozinho na concretagem",
                        Mc / 1e6,
                        flex.resistencia_Nmm / 1e6,
                        "kN·m",
                        ref + "L.2.3.2 a) e 5.4",
                        f"γ_g·g₁ + γ·q_constr; {flex.modo_governante}"
                        + (f", L_b = {_n(e.Lb_construcao, 0)} mm, C_b = 1,13" if Lb else
                           ", contido pela fôrma de aço"),
                    ),
                    Verificacao(
                        "Tensão em serviço na mesa inferior",
                        sigma,
                        fy,
                        "MPa",
                        ref + "L.2.3.2 b)",
                        "M_Ga/W_a + M_L/W_ef ≤ f_y (combinação rara, ações antes e depois da cura)",
                    ),
                ],
            )
        )  # fmt: skip
    # flechas
    Ief = p.Ix + math.sqrt(eta_i) * (secao_homogeneizada(p, b, e.tc, e.hF, alfa)[0] - p.Ix)
    Ief_lp = p.Ix + math.sqrt(eta_i) * (secao_homogeneizada(p, b, e.tc, e.hF, 3 * alfa)[0] - p.Ix)

    def flecha(qk: float, inercia: float) -> float:
        return 5 * qk * L**4 / (384 * E * inercia)

    if e.escorada:
        d_perm = flecha(e.g1 + e.g2, Ief_lp)
    else:
        d_perm = flecha(e.g1, p.Ix) + flecha(e.g2, Ief_lp)
    d_q = flecha(e.q, Ief)
    total = d_perm + d_q - e.contraflecha
    grupos.append(
        vm.Grupo(
            "Deslocamentos",
            [
                vm.linha_info("Momento de inércia efetivo", Ief / 1e6, "×10⁶ mm⁴", ref + "L.1.2.2.1",
                              f"I_a + √η_i·(I_tr − I_a), α_E = {_n(alfa, 2)} (×3 nas permanentes)"),
                vm.linha_limite("Flecha total", total, L / e.flecha_limite, "mm",
                                ref + "Anexo B (Tabela B.1) e L.1.2.3",
                                f"permanentes {_n(d_perm, 1)} + sobrecarga {_n(d_q, 1)} − "
                                f"contraflecha {_n(e.contraflecha, 1)} mm; L/{_n(e.flecha_limite, 0)}"),
            ],
        )
    )  # fmt: skip
    # conectores
    linhas_c = []
    passo = (L / 2) / (e.conectores / e.por_linha)
    total_laje = e.tc + e.hF
    maximo = min(8 * total_laje, 915.0 if e.hF > 0 else math.inf)
    minimo = (4 if e.hF > 0 else 6) * e.diametro_conector
    linhas_c.append(
        vm.linha_limite(
            "Espaçamento máximo dos conectores",
            passo,
            maximo,
            "mm",
            ref + "L.4.3.3",
            f"8·(t_c + h_F){' e 915 mm' if e.hF > 0 else ''}",
        )
    )
    linhas_c.append(
        vm.linha_limite(
            "Espaçamento mínimo dos conectores",
            passo,
            minimo,
            "mm",
            ref + "L.4.3.4",
            f"{'4' if e.hF > 0 else '6'}·d ao longo do vão",
            minimo=True,
        )
    )
    if e.por_linha > 1:
        linhas_c.append(
            vm.linha_limite(
                "Espaço transversal disponível",
                p.bf / e.por_linha,
                4 * e.diametro_conector,
                "mm",
                ref + "L.4.3.4",
                "b_f/n por linha ≥ 4·d",
                minimo=True,
            )
        )
    linhas_c.append(
        vm.linha_limite(
            "Diâmetro do conector",
            e.diametro_conector,
            2.5 * p.tf,
            "mm",
            ref + "L.4.4.1",
            "d ≤ 2,5·t_f (fora da linha da alma)",
        )
    )
    grupos.append(vm.Grupo("Conectores", linhas_c))  # fmt: skip
    numeros = {"b": b, "QRd_kN": QRd / 1000, "somaQ_kN": somaQ / 1000, "Fhd_kN": Fhd / 1000,
               "MSd_kNm": MSd / 1e6, "VSd_kN": VSd / 1000, "alfa_E": alfa, "eta_c": eta_c,
               "Ief": Ief}  # fmt: skip
    avisos.append(
        "Armadura de costura (L.1.3.4) e fissuração (L.5) não são verificadas aqui: confira no "
        "projeto da laje."
    )
    return ResultadoMista(e, p, fy, b, QRd, eta_i, secao, grupos, numeros, avisos)


def registro(r: ResultadoMista) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "perfil": r.perfil.descricao,
        "aco": f"{e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "vao_mm": e.L,
        "laje": (
            f"t_c = {_n(e.tc, 0)} mm"
            + (f" sobre fôrma de {_n(e.hF, 0)} mm" if e.hF else " (maciça)")
            + f", f_ck = {_n(e.fck, 0)} MPa, {e.brita.split(' (')[0].lower()}"
        ),
        "largura_efetiva_mm": round(r.b, 1),
        "conectores": (
            f"{e.conectores} pinos Ø {_n(e.diametro_conector, 1)} mm do apoio ao meio do vão, "
            f"{e.por_linha} por linha, f_u = {_n(e.fu_conector, 0)} MPa; {e.posicao.lower()}"
        ),
        "cargas": (
            f"g₁ = {_n(e.g1, 2)}, q_constr = {_n(e.q_construcao, 2)}, g₂ = {_n(e.g2, 2)}, "
            f"q = {_n(e.q, 2)} kN/m; γ_g = {_n(e.gama_g, 2)}, γ_q = {_n(e.gama_q, 2)}"
        ),
        "construcao": "escorada" if e.escorada else "não escorada",
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Viga mista — {r.perfil.nome}, vão {_n(e.L / 1000, 2)} m",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Viga mista biapoiada com conectores tipo pino com cabeça pela ABNT NBR 8800:2025, "
            "Anexo L: momento resistente plástico (interação completa ou parcial), grau de "
            "interação mínimo, cortante no perfil, construção não escorada e flecha com o momento "
            "de inércia efetivo."
        ),
        premissas=[
            "Carga uniforme; perfil I duplamente simétrico; áreas do perfil sem os raios de "
            "concordância no cálculo plástico (a favor da segurança).",
            "Fluência simplificada: razão modular × 3 nas ações permanentes (L.1.2.1).",
            "Concreto de densidade normal, E_c = 0,85·α_e·5600·√f_ck (4.6.3.1).",
        ],
        referencias=REFERENCIAS,
        objeto=f"A viga mista {r.perfil.nome}",
        alertas=r.avisos,
    )


def com(e: EntradaMista, **mudancas: Any) -> EntradaMista:
    return replace(e, **mudancas)
