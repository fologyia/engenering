"""Método das Forças Uniformes (UFM) para ligações de contraventamento em canto.

Distribui a força ``P`` do contraventamento entre a chapa de nó, a viga e a coluna sem produzir
momento nas interfaces (chapa–viga, chapa–coluna, viga–coluna), como no AISC Design Guide 29
(*Vertical Bracing Connections — Analysis and Design*, seção 4.2) e no AISC Steel Construction
Manual, Parte 13.

Caso geral (Fig. 4-4)::

    α̅ − β̅·tanθ = e_b·tanθ − e_c          (4-1)
    r  = √((α̅ + e_c)² + (β̅ + e_b)²)
    H_b = α̅/r·P   V_b = e_b/r·P            (chapa–viga: cisalhante e normal)
    V_c = β̅/r·P   H_c = e_c/r·P            (chapa–coluna: cisalhante e normal)

``θ`` é o ângulo entre o eixo do contraventamento e a **vertical**; ``e_b`` e ``e_c`` são metade da
altura da viga e da coluna (``e_c = 0`` na ligação à alma da coluna); ``α̅`` e ``β̅`` são as posições
ideais dos centroides das ligações chapa–viga (a partir da face da coluna) e chapa–coluna (a partir
da face da mesa da viga). Quando as posições reais ``α`` e ``β`` diferem das ideais, sobram binários
nas bordas da chapa (Eqs. 4-2 e 4-3).

Casos especiais: 1 (ponto de trabalho fora da interseção dos eixos, Eqs. 4-5 a 4-8), 2 (parte da
vertical da viga passada à coluna, Eqs. 4-10 e 4-11) e 3 (sem ligação à coluna, Fig. 4-16). Forças de
distorção do pórtico: Eqs. 4-12 e 4-14 a 4-16.

Módulo puro: mm, kN e graus; momentos em kN·mm (as propriedades ``*_kNm`` convertem). Os sinais são
os do guia para ``P`` em **tração**; em compressão todas as forças das interfaces invertem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

CASO_GERAL = "geral"
CASO_1 = "caso1"
CASO_2 = "caso2"
CASO_3 = "caso3"
CASOS = {
    CASO_GERAL: "Geral (ponto de trabalho no cruzamento dos eixos)",
    CASO_1: "Especial 1 (ponto de trabalho no canto da chapa)",
    CASO_2: "Especial 2 (menos cisalhamento na ligação viga–coluna)",
    CASO_3: "Especial 3 (chapa ligada só à viga)",
}

AJUSTE_BETA = "beta"
AJUSTE_ALFA = "alfa"
AJUSTE_MINIMIZAR = "minimizar"
AJUSTES = {
    AJUSTE_BETA: "Manter β e calcular α ideal (a ligação à coluna é a mais flexível)",
    AJUSTE_ALFA: "Manter α e calcular β ideal (a ligação à viga é a mais flexível)",
    AJUSTE_MINIMIZAR: "Distribuir o binário (minimiza as excentricidades de α e de β)",
}

THETA_MINIMO_CASO_3 = 55.0  # o guia fala em θ > 60° (o exemplo 5.4 tem 59,7°); abaixo disto, avisa


class UFMInvalido(ValueError):
    """Dado que o método não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class EntradaUFM:
    P_kN: float
    theta_graus: float
    eb_mm: float
    ec_mm: float
    alfa_real_mm: float
    beta_real_mm: float
    caso: str = CASO_GERAL
    ajuste: str = AJUSTE_BETA
    reacao_viga_kN: float = 0.0
    transferencia_kN: float = 0.0
    # caso especial 1: posição do ponto de trabalho (a partir do canto da chapa) e módulos plásticos
    x_mm: float = 0.0
    y_mm: float = 0.0
    Zviga_mm3: float = 0.0
    Zcoluna_mm3: float = 0.0
    # caso especial 2: parcela da vertical que sai da ligação viga–coluna
    delta_Vb_kN: float = 0.0
    anular_Vb: bool = False


@dataclass(frozen=True)
class ResultadoUFM:
    entrada: EntradaUFM
    alfa_ideal_mm: float
    beta_ideal_mm: float
    r_mm: float
    # UFM puro (sem as parcelas dos casos especiais)
    Hb_kN: float
    Vb_kN: float
    Hc_kN: float
    Vc_kN: float
    # caso especial 1
    excentricidade_mm: float = 0.0
    M_excentrico_kNmm: float = 0.0
    eta: float = 0.0
    H_linha_kN: float = 0.0
    V_linha_kN: float = 0.0
    # forças finais em cada interface
    viga_cisalhamento_kN: float = 0.0  # ao longo da mesa da viga (H_b)
    viga_normal_kN: float = 0.0  # perpendicular à mesa da viga (V_b)
    viga_momento_kNmm: float = 0.0
    coluna_cisalhamento_kN: float = 0.0  # ao longo da face da coluna (V_c)
    coluna_normal_kN: float = 0.0  # perpendicular à face da coluna (H_c)
    coluna_momento_kNmm: float = 0.0
    # ligação viga–coluna
    vc_cisalhamento_kN: float = 0.0
    vc_axial_kN: float = 0.0
    vc_momento_kNmm: float = 0.0
    # momentos extras no elemento (caso 1)
    momento_extra_viga_kNmm: float = 0.0
    momento_extra_coluna_kNmm: float = 0.0
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def componentes_horizontal_vertical(self) -> tuple[float, float]:
        """``P·sinθ`` e ``P·cosθ`` (a soma das forças das interfaces tem de dar isto)."""
        t = math.radians(self.entrada.theta_graus)
        return self.entrada.P_kN * math.sin(t), self.entrada.P_kN * math.cos(t)

    @property
    def viga_momento_kNm(self) -> float:
        return self.viga_momento_kNmm / 1000.0

    @property
    def coluna_momento_kNm(self) -> float:
        return self.coluna_momento_kNmm / 1000.0

    @property
    def vc_momento_kNm(self) -> float:
        return self.vc_momento_kNmm / 1000.0

    @property
    def M_excentrico_kNm(self) -> float:
        return self.M_excentrico_kNmm / 1000.0

    @property
    def momento_extra_viga_kNm(self) -> float:
        return self.momento_extra_viga_kNmm / 1000.0

    @property
    def momento_extra_coluna_kNm(self) -> float:
        return self.momento_extra_coluna_kNmm / 1000.0


# ---------------------------------------------------------------------------------------------
# Geometria ideal (Eq. 4-1 e a minimização da Eq. 4-4)
# ---------------------------------------------------------------------------------------------
def alfa_ideal(beta_mm: float, eb_mm: float, ec_mm: float, theta_graus: float) -> float:
    """``α̅ = (β̅ + e_b)·tanθ − e_c`` (Eq. 4-1 com β̅ conhecido)."""
    return (beta_mm + eb_mm) * math.tan(math.radians(theta_graus)) - ec_mm


def beta_ideal(alfa_mm: float, eb_mm: float, ec_mm: float, theta_graus: float) -> float:
    """``β̅ = (α̅ + e_c)/tanθ − e_b`` (Eq. 4-1 com α̅ conhecido)."""
    return (alfa_mm + ec_mm) / math.tan(math.radians(theta_graus)) - eb_mm


def par_ideal_minimizando_excentricidades(
    alfa_mm: float, beta_mm: float, eb_mm: float, ec_mm: float, theta_graus: float
) -> tuple[float, float]:
    """Par ``(α̅, β̅)`` que cumpre a Eq. 4-1 e fica o mais perto de ``(α, β)`` (Eq. 4-4).

    Minimiza ``((α̅ − α)/α)² + ((β̅ − β)/β)²`` com a restrição ``α̅ − β̅·tanθ = K``, ``K = e_b·tanθ − e_c``;
    o multiplicador de Lagrange dá a solução fechada abaixo.
    """
    tan_t = math.tan(math.radians(theta_graus))
    k = eb_mm * tan_t - ec_mm
    desvio = alfa_mm - beta_mm * tan_t - k
    denominador = alfa_mm**2 + (beta_mm * tan_t) ** 2
    if denominador <= 0:
        raise UFMInvalido("α e β não podem ser ambos nulos para distribuir o binário.")
    a_ideal = alfa_mm - alfa_mm**2 * desvio / denominador
    b_ideal = beta_mm + beta_mm**2 * tan_t * desvio / denominador
    return a_ideal, b_ideal


def comprimento_horizontal_para_alfa(
    alfa_mm: float, espessura_chapa_de_topo_mm: float, corte_mm: float
) -> float:
    """``l_h`` que faz o centroide da solda coincidir com ``α̅``: ``α = t_p + (w + l_h)/2``."""
    return 2.0 * (alfa_mm - espessura_chapa_de_topo_mm) - corte_mm


def centroide_da_solda_na_viga(
    comprimento_horizontal_mm: float, corte_mm: float, espessura_chapa_de_topo_mm: float
) -> float:
    """``α`` real: solda de ``w`` a ``l_h`` a partir da chapa de topo (ou da face da coluna)."""
    return espessura_chapa_de_topo_mm + (corte_mm + comprimento_horizontal_mm) / 2.0


def centroide_da_solda_na_coluna(comprimento_vertical_mm: float, corte_mm: float) -> float:
    """``β`` real: solda de ``w`` a ``l_v`` a partir da face da mesa da viga."""
    return (corte_mm + comprimento_vertical_mm) / 2.0


# ---------------------------------------------------------------------------------------------
# Distribuição das forças
# ---------------------------------------------------------------------------------------------
def _validar(e: EntradaUFM) -> None:
    if e.caso not in CASOS:
        raise UFMInvalido(f"Caso do UFM desconhecido: {e.caso!r}.")
    if e.ajuste not in AJUSTES:
        raise UFMInvalido(f"Ajuste de α e β desconhecido: {e.ajuste!r}.")
    if not e.P_kN > 0:
        raise UFMInvalido("A força do contraventamento P precisa ser maior que zero.")
    if not 0.0 < e.theta_graus < 90.0:
        raise UFMInvalido(
            "O ângulo θ (do eixo do contraventamento com a vertical) precisa estar entre 0° e 90°."
        )
    if not e.eb_mm > 0:
        raise UFMInvalido("A metade da altura da viga e_b precisa ser maior que zero.")
    if e.ec_mm < 0:
        raise UFMInvalido(
            "A metade da altura da coluna e_c não pode ser negativa (use 0 na ligação à alma)."
        )
    if e.alfa_real_mm < 0 or e.beta_real_mm < 0:
        raise UFMInvalido("α e β reais não podem ser negativos.")
    if e.caso == CASO_1 and not (e.Zviga_mm3 > 0 and e.Zcoluna_mm3 > 0):
        raise UFMInvalido("O caso especial 1 precisa dos módulos plásticos da viga e da coluna.")
    if e.caso == CASO_2 and not e.anular_Vb and e.delta_Vb_kN < 0:
        raise UFMInvalido("ΔV_b não pode ser negativo.")


def distribuir_forcas(e: EntradaUFM) -> ResultadoUFM:
    """Forças em cada interface pelo UFM (caso geral e casos especiais 1, 2 e 3)."""
    _validar(e)
    avisos: list[str] = []
    theta = e.theta_graus
    tan_t = math.tan(math.radians(theta))
    P = e.P_kN

    if e.caso == CASO_3:
        a_i = e.eb_mm * tan_t - e.ec_mm
        b_i = 0.0
        if a_i <= 0:
            raise UFMInvalido(
                "No caso especial 3, α = e_b·tanθ − e_c resultou não positivo: a chapa ligada só à viga "
                "não cabe com este ângulo."
            )
        if theta < THETA_MINIMO_CASO_3:
            avisos.append(
                f"O caso especial 3 vale para contraventamento 'deitado' (θ acima de uns 60°); com "
                f"θ = {theta:.1f}° prefira o caso geral."
            )
        Hb = P * math.sin(math.radians(theta))
        Vb = P * math.cos(math.radians(theta))
        r = math.hypot(a_i + e.ec_mm, e.eb_mm)
        Mb = Vb * (e.alfa_real_mm - a_i)
        return ResultadoUFM(
            entrada=e,
            alfa_ideal_mm=a_i,
            beta_ideal_mm=b_i,
            r_mm=r,
            Hb_kN=Hb,
            Vb_kN=Vb,
            Hc_kN=0.0,
            Vc_kN=0.0,
            viga_cisalhamento_kN=Hb,
            viga_normal_kN=Vb,
            viga_momento_kNmm=Mb,
            vc_cisalhamento_kN=Vb + e.reacao_viga_kN,
            vc_axial_kN=e.transferencia_kN,
            vc_momento_kNmm=Vb * e.ec_mm,
            avisos=tuple(avisos),
        )

    if e.ajuste == AJUSTE_BETA:
        b_i = e.beta_real_mm
        a_i = alfa_ideal(b_i, e.eb_mm, e.ec_mm, theta)
    elif e.ajuste == AJUSTE_ALFA:
        a_i = e.alfa_real_mm
        b_i = beta_ideal(a_i, e.eb_mm, e.ec_mm, theta)
    else:
        a_i, b_i = par_ideal_minimizando_excentricidades(
            e.alfa_real_mm, e.beta_real_mm, e.eb_mm, e.ec_mm, theta
        )
    if a_i < 0 or b_i < 0:
        raise UFMInvalido(
            f"A geometria ideal ficou com α̅ = {a_i:.1f} mm e β̅ = {b_i:.1f} mm: algum é negativo. "
            "Aumente a chapa, mude qual dos dois mantém ou use outro caso."
        )
    r = math.hypot(a_i + e.ec_mm, b_i + e.eb_mm)
    Hb = a_i / r * P
    Vb = e.eb_mm / r * P
    Vc = b_i / r * P
    Hc = e.ec_mm / r * P

    Mb = Vb * (e.alfa_real_mm - a_i)  # Eq. 4-2 (a Eq. 4-10 soma ΔV_b·α no caso 2)
    Mc = Hc * (e.beta_real_mm - b_i)  # Eq. 4-3
    if abs(e.alfa_real_mm - a_i) > 0.5 and e.ajuste == AJUSTE_BETA:
        avisos.append(
            f"α real ({e.alfa_real_mm:.1f} mm) difere de α̅ ({a_i:.1f} mm): há binário de "
            f"{abs(Mb) / 1000:.2f} kN·m na interface chapa–viga."
        )
    if abs(e.beta_real_mm - b_i) > 0.5 and e.ajuste == AJUSTE_ALFA:
        avisos.append(
            f"β real ({e.beta_real_mm:.1f} mm) difere de β̅ ({b_i:.1f} mm): há binário de "
            f"{abs(Mc) / 1000:.2f} kN·m na interface chapa–coluna."
        )

    viga_cis, viga_norm = Hb, Vb
    col_cis, col_norm = Vc, Hc
    momento_viga, momento_coluna = Mb, Mc
    vc_cis = Vb + e.reacao_viga_kN
    ecc = 0.0
    m_exc = 0.0
    eta = 0.0
    h_linha = 0.0
    v_linha = 0.0
    extra_viga = 0.0
    extra_coluna = 0.0

    if e.caso == CASO_1:
        ecc = (e.eb_mm - e.y_mm) * math.sin(math.radians(theta)) - (e.ec_mm - e.x_mm) * math.cos(
            math.radians(theta)
        )
        m_exc = P * ecc  # Eq. 4-7
        eta = e.Zviga_mm3 / (e.Zviga_mm3 + 2.0 * e.Zcoluna_mm3)  # Eq. 4-8 (coluna acima e abaixo)
        h_linha = (1.0 - eta) * m_exc / (b_i + e.eb_mm)  # Eq. 4-5
        v_linha = (m_exc - h_linha * b_i) / a_i if a_i > 0 else 0.0  # Eq. 4-6
        # superposição às forças do UFM na mesma interface (Fig. 4-14, P em tração, e positivo)
        col_norm = Hc + h_linha
        col_cis = Vc + v_linha
        viga_cis = Hb - h_linha
        viga_norm = Vb - v_linha
        extra_viga = eta * m_exc
        extra_coluna = (1.0 - eta) / 2.0 * m_exc
        vc_cis = viga_norm + e.reacao_viga_kN
        if e.ec_mm == 0.0:
            avisos.append(
                "Na ligação à alma da coluna η = 1 (todo o momento vai para a viga, DG29 4.2.2); "
                "o programa usa η pelos módulos informados — confira."
            )

    if e.caso == CASO_2:
        dvb = Vb if e.anular_Vb else e.delta_Vb_kN
        if dvb > Vb + 1e-9:
            raise UFMInvalido(
                f"ΔV_b = {dvb:.1f} kN passa de V_b = {Vb:.1f} kN: não há vertical suficiente para retirar."
            )
        viga_norm = Vb - dvb
        col_cis = Vc + dvb
        momento_viga = Mb + dvb * e.alfa_real_mm  # Eq. 4-10
        vc_cis = Vb - dvb + e.reacao_viga_kN

    return ResultadoUFM(
        entrada=e,
        alfa_ideal_mm=a_i,
        beta_ideal_mm=b_i,
        r_mm=r,
        Hb_kN=Hb,
        Vb_kN=Vb,
        Hc_kN=Hc,
        Vc_kN=Vc,
        excentricidade_mm=ecc,
        M_excentrico_kNmm=m_exc,
        eta=eta,
        H_linha_kN=h_linha,
        V_linha_kN=v_linha,
        viga_cisalhamento_kN=viga_cis,
        viga_normal_kN=viga_norm,
        viga_momento_kNmm=momento_viga,
        coluna_cisalhamento_kN=col_cis,
        coluna_normal_kN=col_norm,
        coluna_momento_kNmm=momento_coluna,
        vc_cisalhamento_kN=vc_cis,
        vc_axial_kN=col_norm + e.transferencia_kN,
        vc_momento_kNmm=0.0,
        momento_extra_viga_kNmm=extra_viga,
        momento_extra_coluna_kNmm=extra_coluna,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------------------------
# Distorção do pórtico (Eqs. 4-12, 4-14 a 4-16)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ForcasDeDistorcao:
    MD_kNmm: float
    HD_kN: float
    VD_kN: float
    FD_kN: float

    @property
    def MD_kNm(self) -> float:
        return self.MD_kNmm / 1000.0


def forcas_de_distorcao(
    P_kN: float,
    area_contraventamento_mm2: float,
    inercia_viga_mm4: float,
    inercia_coluna_mm4: float,
    b_mm: float,
    c_mm: float,
    beta_mm: float,
    alfa_mm: float,
    eb_mm: float,
) -> ForcasDeDistorcao:
    """Momento de distorção na viga (Tamboli, Eq. 4-12) e as forças admissíveis da Fig. 4-18.

    ``b``: comprimento da viga até o ponto de inflexão (meio do vão); ``c``: da coluna (meio da
    altura). Vale para arranjos de uma viga e duas colunas (Fig. 2-1 do guia); outros arranjos
    pedem análise do pórtico.
    """
    for nome, valor in (
        ("a área do contraventamento", area_contraventamento_mm2),
        ("a inércia da viga", inercia_viga_mm4),
        ("a inércia da coluna", inercia_coluna_mm4),
        ("o comprimento b da viga", b_mm),
        ("o comprimento c da coluna", c_mm),
    ):
        if not valor > 0:
            raise UFMInvalido(f"{nome[0].upper() + nome[1:]} precisa ser maior que zero.")
    md = (
        6.0
        * (P_kN / (area_contraventamento_mm2 * b_mm * c_mm))
        * (
            inercia_viga_mm4
            * inercia_coluna_mm4
            / (inercia_viga_mm4 / b_mm + 2.0 * inercia_coluna_mm4 / c_mm)
        )
        * ((b_mm**2 + c_mm**2) / (b_mm * c_mm))
    )
    hd = md / (beta_mm + eb_mm)
    vd = hd * beta_mm / alfa_mm if alfa_mm > 0 else 0.0
    return ForcasDeDistorcao(md, hd, vd, math.hypot(hd, vd))


def forca_no_contraventamento(forca_horizontal_kN: float, theta_graus: float) -> float:
    """``P = H/sinθ`` (θ da vertical): a força no contraventamento que equilibra ``H`` horizontal."""
    if not forca_horizontal_kN > 0:
        raise UFMInvalido("A força horizontal do painel precisa ser maior que zero.")
    if not 0.0 < theta_graus < 90.0:
        raise UFMInvalido("O ângulo θ precisa estar entre 0° e 90°.")
    return forca_horizontal_kN / math.sin(math.radians(theta_graus))


def theta_da_geometria(deslocamento_horizontal_mm: float, deslocamento_vertical_mm: float) -> float:
    """``θ = atan(Δx/Δy)`` entre o eixo do contraventamento e a vertical, em graus."""
    if not (deslocamento_horizontal_mm > 0 and deslocamento_vertical_mm > 0):
        raise UFMInvalido(
            "Os deslocamentos horizontal e vertical do contraventamento precisam ser positivos."
        )
    return math.degrees(math.atan2(deslocamento_horizontal_mm, deslocamento_vertical_mm))
