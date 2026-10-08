"""Verificações da chapa de nó (gusset) de contraventamento pelo AISC 360-16 e pelo Design Guide 29.

Funções puras, em mm, kN e MPa, com os estados-limites que o Exemplo 5.1 do guia percorre:

* ligação contraventamento–chapa: parafusos (cisalhamento J3.6 e contato J3.10, soma por furo),
  seção de Whitmore (escoamento J4.1 e flambagem J4.4/E3) e cisalhamento de bloco (J4.3);
* interfaces da chapa com a viga e com a coluna: escoamento por cisalhamento (J4.2), escoamento
  normal (J4.1), flexão (F2) e a interação (M/M_n)² + (N/N_n)² + (V/V_n)⁴ ≤ 1 de Neal/Astaneh-Asl;
* solda de filete com o aumento por ângulo de carga (J2.4) e o fator de ductilidade de 1,25;
* escoamento local (J10.2) e enrugamento (J10.3) da alma da viga e da coluna.

LRFD e ASD: cada estado-limite tem o seu par ``(φ, Ω)`` em :data:`FATORES`; ``disponivel`` devolve
``φ·R_n`` ou ``R_n/Ω``, e o esforço solicitante tem de vir na mesma base (``P_u`` ou ``P_a``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import bolted_connection as bc

METODO_LRFD = "LRFD"
METODO_ASD = "ASD"
METODOS = {
    METODO_LRFD: "LRFD (esforços majorados; φ·R_n)",
    METODO_ASD: "ASD (esforços de serviço; R_n/Ω)",
}

#: ``(φ, Ω)`` por estado-limite — AISC 360-16.
FATORES: dict[str, tuple[float, float]] = {
    "parafuso_cisalhamento": (0.75, 2.00),  # J3.6
    "contato": (0.75, 2.00),  # J3.10
    "escoamento_tracao": (0.90, 1.67),  # J4.1(a), D2(a)
    "escoamento_cisalhamento": (1.00, 1.50),  # J4.2(a)
    "bloco_cisalhamento": (0.75, 2.00),  # J4.3
    "compressao": (0.90, 1.67),  # J4.4 e E1
    "flexao": (0.90, 1.67),  # F2
    "escoamento_local": (1.00, 1.50),  # J10.2
    "enrugamento": (0.75, 2.00),  # J10.3
    "flexao_local_mesa": (0.90, 1.67),  # J10.1
    "solda": (0.75, 2.00),  # J2.4
}

E_ACO_MPA = 200_000.0
ELETRODO_E70_MPA = 482.6  # F_EXX do E70XX (70 ksi)
FATOR_DE_DUCTILIDADE_DA_SOLDA = 1.25  # Manual Parte 13: sobrerresistência para redistribuir tensão
FOLGA_FURO_EFETIVO_MM = 1.5875  # B4.3: o furo efetivo é d_h + 1/16"


class ChapaInvalida(ValueError):
    """Dado que a verificação não aceita; a mensagem diz o que corrigir."""


def disponivel(resistencia_nominal_kN: float, estado: str, metodo: str) -> float:
    """``φ·R_n`` (LRFD) ou ``R_n/Ω`` (ASD) do estado-limite."""
    if metodo not in METODOS:
        raise ChapaInvalida(f"Método desconhecido: {metodo!r}.")
    phi, omega = FATORES[estado]
    return resistencia_nominal_kN * phi if metodo == METODO_LRFD else resistencia_nominal_kN / omega


def _positivo(valor: float, nome: str) -> None:
    if not valor > 0:
        raise ChapaInvalida(f"{nome} precisa ser maior que zero.")


# ---------------------------------------------------------------------------------------------
# Parafusos da ligação contraventamento–chapa
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DisposicaoDosParafusos:
    """Arranjo do grupo na direção da força: ``fileiras`` paralelas ao eixo do contraventamento."""

    fileiras: int
    por_fileira: int
    passo_mm: float
    gabarito_mm: float  # distância transversal entre fileiras
    extremidade_mm: float  # do último parafuso à borda, na direção da força

    @property
    def comprimento_do_grupo_mm(self) -> float:
        return (self.por_fileira - 1) * self.passo_mm

    @property
    def largura_do_grupo_mm(self) -> float:
        return (self.fileiras - 1) * self.gabarito_mm

    @property
    def numero_de_parafusos(self) -> int:
        return self.fileiras * self.por_fileira


@dataclass(frozen=True)
class ResistenciaDoGrupo:
    por_parafuso_cisalhamento_kN: float
    contato_interno_kN: float
    contato_extremo_kN: float
    parafuso_interno_kN: float  # o menor entre cisalhamento e contato
    parafuso_extremo_kN: float
    grupo_kN: float
    controle_interno: str
    controle_extremo: str


def resistencia_do_grupo(
    d_mm: float,
    grau: str,
    rosca_no_plano: bool,
    planos_de_corte: int,
    arranjo: DisposicaoDosParafusos,
    t_chapa_mm: float,
    Fu_chapa_MPa: float,
    metodo: str,
    *,
    designacao: str | None = None,
    t_barra_mm: float = 0.0,
    Fu_barra_MPa: float = 0.0,
    extremidade_barra_mm: float = 0.0,
) -> ResistenciaDoGrupo:
    """Soma do menor valor entre corte e contato de cada parafuso (J3.6, nota do usuário; DG29 p. 50).

    O parafuso da extremidade tem ``ℓ_c = e − d_h/2``; os demais, ``ℓ_c = s − d_h``. Com
    ``t_barra_mm`` informado, o contato também é conferido na barra do contraventamento (espessura
    total que apoia o parafuso e a sua distância à ponta ``extremidade_barra_mm``).
    """
    _positivo(d_mm, "O diâmetro do parafuso")
    _positivo(t_chapa_mm, "A espessura da chapa de nó")
    if arranjo.fileiras < 1 or arranjo.por_fileira < 1:
        raise ChapaInvalida("O grupo precisa de pelo menos uma fileira com um parafuso.")
    if arranjo.por_fileira > 1:
        _positivo(arranjo.passo_mm, "O passo dos parafusos")
    if arranjo.fileiras > 1:
        _positivo(arranjo.gabarito_mm, "O gabarito entre fileiras")
    d_h = bc.PARAFUSOS[designacao][1] if designacao in bc.PARAFUSOS else d_mm + 1.6
    cisalhamento_nominal = (
        bc.GRAUS[grau].Fnv_AISC[0 if (rosca_no_plano or grau == "A307") else 1]
        * bc.area_bruta(d_mm)
        * planos_de_corte
        / 1000.0
    )
    cisalhamento = disponivel(cisalhamento_nominal, "parafuso_cisalhamento", metodo)

    def contato(l_c: float, t: float, fu: float) -> float:
        nominal = min(1.2 * l_c * t * fu, 2.4 * d_mm * t * fu) / 1000.0
        return disponivel(max(nominal, 0.0), "contato", metodo)

    interno = contato(arranjo.passo_mm - d_h, t_chapa_mm, Fu_chapa_MPa)
    extremo = contato(arranjo.extremidade_mm - d_h / 2.0, t_chapa_mm, Fu_chapa_MPa)
    if t_barra_mm > 0 and Fu_barra_MPa > 0:
        interno = min(interno, contato(arranjo.passo_mm - d_h, t_barra_mm, Fu_barra_MPa))
        ext_barra = extremidade_barra_mm if extremidade_barra_mm > 0 else arranjo.extremidade_mm
        extremo = min(extremo, contato(ext_barra - d_h / 2.0, t_barra_mm, Fu_barra_MPa))
    p_interno = min(cisalhamento, interno)
    p_extremo = min(cisalhamento, extremo)
    n_extremos = arranjo.fileiras
    n_internos = arranjo.numero_de_parafusos - n_extremos
    return ResistenciaDoGrupo(
        por_parafuso_cisalhamento_kN=cisalhamento,
        contato_interno_kN=interno,
        contato_extremo_kN=extremo,
        parafuso_interno_kN=p_interno,
        parafuso_extremo_kN=p_extremo,
        grupo_kN=n_extremos * p_extremo + n_internos * p_interno,
        controle_interno="cisalhamento" if cisalhamento <= interno else "contato",
        controle_extremo="cisalhamento" if cisalhamento <= extremo else "contato",
    )


def numero_minimo_de_parafusos(forca_kN: float, resistencia_por_parafuso_kN: float) -> float:
    """``N = P/(φ·r_n)`` (guia p. 46); o inteiro seguinte é o mínimo do arranjo."""
    _positivo(resistencia_por_parafuso_kN, "A resistência por parafuso")
    return forca_kN / resistencia_por_parafuso_kN


# ---------------------------------------------------------------------------------------------
# Seção de Whitmore, flambagem e cisalhamento de bloco
# ---------------------------------------------------------------------------------------------
def largura_de_whitmore(arranjo: DisposicaoDosParafusos, angulo_graus: float = 30.0) -> float:
    """``l_w = (fileiras − 1)·g + 2·L·tan30°`` (Manual Parte 9)."""
    return arranjo.largura_do_grupo_mm + 2.0 * arranjo.comprimento_do_grupo_mm * math.tan(
        math.radians(angulo_graus)
    )


def area_de_whitmore(
    lw_mm: float, t_chapa_mm: float, trecho_na_alma_mm: float = 0.0, t_alma_mm: float = 0.0
) -> float:
    """Área efetiva da seção de Whitmore; o trecho que entra na alma da viga conta com a alma."""
    trecho = min(max(trecho_na_alma_mm, 0.0), lw_mm)
    return (lw_mm - trecho) * t_chapa_mm + trecho * (t_alma_mm if trecho > 0 else t_chapa_mm)


def tensao_critica_de_flambagem(esbeltez: float, Fy_MPa: float, E_MPa: float = E_ACO_MPA) -> float:
    """``F_cr`` da seção E3: curva inelástica até ``4,71·√(E/F_y)``, elástica depois."""
    if esbeltez <= 0:
        return Fy_MPa
    fe = math.pi**2 * E_MPa / esbeltez**2
    if esbeltez <= 4.71 * math.sqrt(E_MPa / Fy_MPa):
        return Fy_MPa * 0.658 ** (Fy_MPa / fe)
    return 0.877 * fe


def compressao_da_chapa(
    area_mm2: float,
    espessura_mm: float,
    comprimento_mm: float,
    K: float,
    Fy_MPa: float,
    E_MPa: float = E_ACO_MPA,
) -> tuple[float, float, float]:
    """``(R_n em kN, KL/r, F_cr)`` da chapa comprimida: J4.4 até ``KL/r = 25`` e E3 acima."""
    _positivo(area_mm2, "A área da seção de Whitmore")
    _positivo(espessura_mm, "A espessura da chapa")
    r = espessura_mm / math.sqrt(12.0)
    esbeltez = K * comprimento_mm / r
    fcr = Fy_MPa if esbeltez <= 25.0 else tensao_critica_de_flambagem(esbeltez, Fy_MPa, E_MPa)
    return fcr * area_mm2 / 1000.0, esbeltez, fcr


@dataclass(frozen=True)
class BlocoDeCisalhamento:
    Agv_mm2: float
    Anv_mm2: float
    Ant_mm2: float
    ruptura_do_cisalhamento_kN: float  # 0,60·F_u·A_nv
    escoamento_do_cisalhamento_kN: float  # 0,60·F_y·A_gv
    ruptura_da_tracao_kN: float  # U_bs·F_u·A_nt
    nominal_kN: float


def bloco_de_cisalhamento(
    Agv_mm2: float, Anv_mm2: float, Ant_mm2: float, Fy_MPa: float, Fu_MPa: float, Ubs: float = 1.0
) -> BlocoDeCisalhamento:
    """``R_n = 0,60·F_u·A_nv + U_bs·F_u·A_nt ≤ 0,60·F_y·A_gv + U_bs·F_u·A_nt`` (J4-5)."""
    ruptura = 0.60 * Fu_MPa * Anv_mm2 / 1000.0
    escoamento = 0.60 * Fy_MPa * Agv_mm2 / 1000.0
    tracao = Ubs * Fu_MPa * max(Ant_mm2, 0.0) / 1000.0
    return BlocoDeCisalhamento(
        Agv_mm2, Anv_mm2, Ant_mm2, ruptura, escoamento, tracao, min(ruptura, escoamento) + tracao
    )


def bloco_de_cisalhamento_da_chapa(
    arranjo: DisposicaoDosParafusos,
    t_chapa_mm: float,
    d_furo_mm: float,
    Fy_MPa: float,
    Fu_MPa: float,
) -> BlocoDeCisalhamento:
    """Cisalhamento de bloco da chapa de nó: dois planos ao longo das fileiras externas e o plano
    de tração entre elas, na ponta do grupo (guia p. 48: ``A_gv = 2·t·(L + e)``)."""
    d_ef = d_furo_mm + FOLGA_FURO_EFETIVO_MM
    comprimento_cisalhado = arranjo.comprimento_do_grupo_mm + arranjo.extremidade_mm
    agv = 2.0 * t_chapa_mm * comprimento_cisalhado
    anv = agv - 2.0 * t_chapa_mm * (arranjo.por_fileira - 0.5) * d_ef
    ant = t_chapa_mm * (arranjo.largura_do_grupo_mm - (arranjo.fileiras - 1) * d_ef)
    return bloco_de_cisalhamento(agv, anv, ant, Fy_MPa, Fu_MPa)


# ---------------------------------------------------------------------------------------------
# Interface da chapa com a viga ou a coluna
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResistenciaDaInterface:
    cisalhamento_kN: float  # φ·0,60·F_y·t·l
    normal_kN: float  # φ·F_y·t·l
    flexao_kNmm: float  # φ·F_y·t·l²/4
    interacao: float  # (M/M_n)² + (N/N_n)² + (V/V_n)⁴


def resistencia_da_interface(
    comprimento_mm: float,
    t_chapa_mm: float,
    Fy_MPa: float,
    cisalhante_kN: float,
    normal_kN: float,
    momento_kNmm: float,
    metodo: str,
) -> ResistenciaDaInterface:
    """Escoamento por cisalhamento (J4-3), normal (J4-1) e flexão plástica (F2-1) da borda da chapa,
    com a interação de Neal (1977) / Astaneh-Asl (1998) usada no guia (p. 56)."""
    _positivo(comprimento_mm, "O comprimento da interface")
    _positivo(t_chapa_mm, "A espessura da chapa")
    area = t_chapa_mm * comprimento_mm
    vn = disponivel(0.60 * Fy_MPa * area / 1000.0, "escoamento_cisalhamento", metodo)
    nn = disponivel(Fy_MPa * area / 1000.0, "escoamento_tracao", metodo)
    mn = disponivel(Fy_MPa * t_chapa_mm * comprimento_mm**2 / 4.0 / 1000.0, "flexao", metodo)
    interacao = (
        (abs(momento_kNmm) / mn) ** 2 + (abs(normal_kN) / nn) ** 2 + (abs(cisalhante_kN) / vn) ** 4
    )
    return ResistenciaDaInterface(vn, nn, mn, interacao)


# ---------------------------------------------------------------------------------------------
# Solda de filete da interface
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SoldaNecessaria:
    f_normal_kN_mm: float
    f_cisalhante_kN_mm: float
    f_flexao_kN_mm: float
    f_media_kN_mm: float
    f_pico_kN_mm: float
    f_projeto_kN_mm: float
    angulo_graus: float
    perna_necessaria_mm: float
    perna_minima_mm: float


def perna_minima_da_solda(t_parte_mais_fina_mm: float) -> float:
    """Tabela J2.4: 3 mm até 6,35 mm; 5 mm até 12,7; 6 mm até 19,1; 8 mm acima."""
    if t_parte_mais_fina_mm <= 6.35:
        return 3.0
    if t_parte_mais_fina_mm <= 12.7:
        return 5.0
    if t_parte_mais_fina_mm <= 19.05:
        return 6.0
    return 8.0


def resistencia_da_solda_por_mm_de_perna(FEXX_MPa: float, metodo: str) -> float:
    """kN/mm por mm de perna, de **um** filete (força por comprimento): ``φ·0,60·F_EXX·0,707``."""
    nominal = 0.60 * FEXX_MPa * math.sqrt(0.5) / 1000.0
    return disponivel(nominal, "solda", metodo)


def solda_necessaria(
    normal_kN: float,
    cisalhante_kN: float,
    momento_kNmm: float,
    comprimento_mm: float,
    FEXX_MPa: float,
    metodo: str,
    t_parte_mais_fina_mm: float,
    fator_de_ductilidade: float = FATOR_DE_DUCTILIDADE_DA_SOLDA,
) -> SoldaNecessaria:
    """Perna do filete duplo da interface (DG29 p. 57 e 58).

    ``f`` por unidade de comprimento: ``f_a = N/l`` (normal), ``f_v = V/l`` (ao longo da solda) e
    ``f_b = 6M/l²``; ``f_pico = √((f_a + f_b)² + f_v²)`` e a média das duas bordas; o filete resiste
    a ``2·φ·0,60·F_EXX·0,707·D·(1 + 0,50·sen^1,5 θ)`` (J2-5), com ``θ = atan(f_a/f_v)``. A solda ligada
    direto à viga ou à coluna usa o maior entre o pico e ``fator·f_média`` (1,25).
    """
    _positivo(comprimento_mm, "O comprimento da solda")
    fa = abs(normal_kN) / comprimento_mm
    fv = abs(cisalhante_kN) / comprimento_mm
    fb = 6.0 * abs(momento_kNmm) / comprimento_mm**2
    pico = math.hypot(fa + fb, fv)
    media = 0.5 * (math.hypot(fa - fb, fv) + pico)
    projeto = max(pico, fator_de_ductilidade * media)
    angulo = math.degrees(math.atan2(fa, fv)) if fv > 0 else 90.0
    capacidade_unitaria = 2.0 * resistencia_da_solda_por_mm_de_perna(FEXX_MPa, metodo)
    aumento = 1.0 + 0.50 * math.sin(math.radians(angulo)) ** 1.5
    perna = projeto / (capacidade_unitaria * aumento)
    return SoldaNecessaria(
        fa, fv, fb, media, pico, projeto, angulo, perna, perna_minima_da_solda(t_parte_mais_fina_mm)
    )


def perna_para_forca_resultante(
    normal_kN: float,
    cisalhante_kN: float,
    comprimento_mm: float,
    FEXX_MPa: float,
    metodo: str,
    t_parte_mais_fina_mm: float,
) -> SoldaNecessaria:
    """Solda da chapa de topo (DG29 p. 62): resultante ``R`` e o ângulo com a vertical, sem o fator
    de ductilidade — a flexibilidade da chapa de topo redistribui a tensão."""
    return solda_necessaria(
        normal_kN,
        cisalhante_kN,
        0.0,
        comprimento_mm,
        FEXX_MPa,
        metodo,
        t_parte_mais_fina_mm,
        fator_de_ductilidade=1.0,
    )


# ---------------------------------------------------------------------------------------------
# Alma da viga e da coluna sob força concentrada de compressão (J10)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PerfilDoNo:
    """Perfil I da viga ou da coluna: dimensões em mm, ``k`` da face externa da mesa ao pé do raio."""

    nome: str
    d_mm: float
    tw_mm: float
    tf_mm: float
    bf_mm: float
    k_mm: float
    Fy_MPa: float
    Zx_mm3: float
    Ix_mm4: float
    Fu_MPa: float = 450.0


def escoamento_local_da_alma(
    perfil: PerfilDoNo,
    comprimento_de_apoio_mm: float,
    distancia_da_extremidade_mm: float,
    metodo: str,
) -> float:
    """``R_n = F_yw·t_w·(5k + l_b)`` (J10-2) ou ``F_yw·t_w·(2,5k + l_b)`` (J10-3) a até ``d`` da ponta."""
    fator = 5.0 if distancia_da_extremidade_mm > perfil.d_mm else 2.5
    nominal = (
        perfil.Fy_MPa * perfil.tw_mm * (fator * perfil.k_mm + comprimento_de_apoio_mm) / 1000.0
    )
    return disponivel(nominal, "escoamento_local", metodo)


def enrugamento_da_alma(
    perfil: PerfilDoNo,
    comprimento_de_apoio_mm: float,
    distancia_da_extremidade_mm: float,
    metodo: str,
    E_MPa: float = E_ACO_MPA,
) -> float:
    """Enrugamento da alma (J10-4, J10-5a e J10-5b), conforme a distância à ponta do elemento."""
    tw, tf, d, lb = perfil.tw_mm, perfil.tf_mm, perfil.d_mm, comprimento_de_apoio_mm
    raiz = math.sqrt(E_MPa * perfil.Fy_MPa * tf / tw)
    razao = (tw / tf) ** 1.5
    if distancia_da_extremidade_mm >= d / 2.0:
        nominal = 0.80 * tw**2 * (1.0 + 3.0 * (lb / d) * razao) * raiz
    elif lb / d <= 0.2:
        nominal = 0.40 * tw**2 * (1.0 + 3.0 * (lb / d) * razao) * raiz
    else:
        nominal = 0.40 * tw**2 * (1.0 + (4.0 * lb / d - 0.2) * razao) * raiz
    return disponivel(nominal / 1000.0, "enrugamento", metodo)


def flexao_local_da_mesa(perfil: PerfilDoNo, metodo: str) -> float:
    """``R_n = 6,25·t_f²·F_yf`` (J10-1): vale para força concentrada de tração; a chapa de nó é linear."""
    return disponivel(6.25 * perfil.tf_mm**2 * perfil.Fy_MPa / 1000.0, "flexao_local_mesa", metodo)


def cisalhamento_da_alma(perfil: PerfilDoNo, metodo: str) -> float:
    """``φ·0,60·F_y·d·t_w`` (J4-3): cisalhamento da alma da viga ou da coluna."""
    return disponivel(
        0.60 * perfil.Fy_MPa * perfil.d_mm * perfil.tw_mm / 1000.0,
        "escoamento_cisalhamento",
        metodo,
    )


def momento_plastico_disponivel(perfil: PerfilDoNo, metodo: str) -> float:
    """``φ_b·M_p`` ou ``M_p/Ω_b`` em kN·mm (viga contida lateralmente)."""
    return disponivel(perfil.Fy_MPa * perfil.Zx_mm3 / 1000.0, "flexao", metodo)
