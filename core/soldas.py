"""Soldas pela NBR 8800 (2025 e 2008): resistências, limites e o método do centro instantâneo.

Regras puras, sem Streamlit, usadas pelas ligações soldadas (:mod:`core.ligacoes` e
:mod:`core.ligacoes_soldadas`). Unidades: mm, MPa, kN.

Fontes:

* **NBR 8800:2025** (chave interna ``NBR8800_2024``) — vistos no texto que o usuário mandou
  (fotos de 29/10/2026, os PDFs de 30/10/2026 e as fotos de 5.2.4 e 5.2.5 do mesmo dia): 5.2
  (tração, com a área líquida e o C_t), 5.3 (compressão), 5.7 (forças localizadas), 6.1.5, 6.1.8,
  6.1.9, 6.2.2 (áreas efetivas, β e o teto de 180·d_w do filete longo, Tabela 6 da garganta da
  penetração parcial), 6.2.3, 6.2.4, Tabela 8 (compatibilidade), Tabela 9 com as notas a–j, 6.2.5,
  6.2.6 (limites, Tabelas 10 e 11) e 6.5.3 a 6.5.6. Um item que não esteja nessa lista vai marcado
  "a confirmar" na referência.
* **NBR 8800:2008** — texto conferido: 4.8.2 (Tabela 3), 5.2.5, 5.7.2 a 5.7.4, 6.1.5, 6.1.8,
  6.2.2, 6.2.5, 6.2.6, 6.5 e Tabelas 5, 7, 8, 9, 10 e A.4.

Na 2025 as tabelas mudaram de número (5 → 6, 7 → 8, 8 → 9, 9 → 10, 10 → 11). Regras que mudaram:
o comprimento efetivo do filete longo para em 180·d_w quando L > 300·d_w (6.2.2.2 d); a perna
máxima na borda passa a t − 1,5 mm a partir de 6,3 mm (6,35 na 2008); e o C_t (5.2.5) da seção
aberta perde os limites de 0,90 e 0,60 e não precisa ficar abaixo de A_c/A_g, e o da chapa ligada
só por filetes longitudinais passa a 3ℓ_c²/(3ℓ_c² + b²)·(1 − t/(2ℓ_c)) no lugar dos degraus 1,00,
0,87 e 0,75. Os limites 6,3 (6,35 na 2008),
12,5 e 19 mm das faixas de espessura são as chapas comerciais de 1/4", 1/2" e 3/4": a chapa de
1/2" (12,7 mm) fica na faixa "até 12,5", como no AISC 360 (Tabela J2.4) e no critério Anglo.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from core.verificacao import Verificacao

NBR_2025 = "NBR8800_2024"  # o código interno da NBR 8800:2025
NBR_2008 = "NBR8800_2008"
NORMAS = (NBR_2025, NBR_2008)
NORMAS_ROTULOS = {NBR_2025: "ABNT NBR 8800:2025", NBR_2008: "ABNT NBR 8800:2008"}
E_ACO = 200_000.0  # MPa
ELETRODOS = {"E60": 415.0, "E70": 485.0, "E80": 550.0}  # Tabela A.4
GARGANTA_DO_FILETE = 0.707  # garganta efetiva / perna, pernas iguais (6.2.2.2 b)
COMPRIMENTO_MINIMO_ABSOLUTO = 40.0  # 6.2.6.2.3 e 6.2.6.2.4
COBRIMENTO_MINIMO_ABSOLUTO = 25.0  # 6.2.6.2.5
FORCA_MINIMA_DA_LIGACAO_KN = 45.0  # 6.1.5.2
#: As faixas de espessura das tabelas da perna e da garganta mínimas: 6,3 (1/4"), 12,5 (1/2") e
#: 19 mm (3/4") são as chapas comerciais em polegada, tomadas pela medida exata.
CHAPA_QUARTO_DE_POLEGADA = 6.35
CHAPA_MEIA_POLEGADA = 12.7
CHAPA_TRES_QUARTOS = 19.05

COMBINACAO_NORMAL = "normal"
COMBINACAO_EXCEPCIONAL = "excepcional"
COMBINACOES = {
    COMBINACAO_NORMAL: "Normal, especial ou de construção",
    COMBINACAO_EXCEPCIONAL: "Excepcional",
}

#: Tabelas da NBR 8800 por edição.
TABELAS = {
    NBR_2025: {
        "resistencia": "Tabela 9",
        "garganta": "Tabela 10",
        "perna": "Tabela 11",
        "compatibilidade": "Tabela 8",
        "garganta_efetiva": "Tabela 6",  # garganta efetiva da penetração parcial
        "nota_w1": "nota h",
        "nota_w2": "nota i",
    },
    NBR_2008: {
        "resistencia": "Tabela 8",
        "garganta": "Tabela 9",
        "perna": "Tabela 10",
        "compatibilidade": "Tabela 7",
        "garganta_efetiva": "Tabela 5",
        "nota_w1": "nota j",
        "nota_w2": "nota k",
    },
}


class SoldaInvalida(ValueError):
    """Dado que o cálculo da solda não aceita; a mensagem diz o que corrigir."""


def validar_norma(norma: str) -> None:
    if norma not in NORMAS:
        raise SoldaInvalida(f"Norma desconhecida: {norma!r}.")


def norma_curta(norma: str) -> str:
    return NORMAS_ROTULOS[norma].removeprefix("ABNT ")


#: Itens da NBR 8800:2025 já vistos no texto (um item vale com os subitens: "6.5.5" cobre
#: "6.5.5 a)"). Confirmar mais um item é só acrescentá-lo aqui.
ITENS_VISTOS_NA_2025 = (
    "5.2", "5.3", "5.7",
    "6.1.5", "6.1.8", "6.1.9", "6.2.2", "6.2.3", "6.2.4", "6.2.5", "6.2.6",
    "6.5.3", "6.5.4", "6.5.5", "6.5.6",
)  # fmt: skip
MARCA_A_CONFIRMAR = "(a confirmar)"
_ITEM = re.compile(r"\d+(?:\.\d+)+")


def item_visto_na_2025(texto: str) -> bool:
    """Todos os itens numerados do texto (ex.: "6.5.3 e 6.5.4") já foram vistos na 2025?"""
    itens = _ITEM.findall(texto)
    return bool(itens) and all(
        any(item == visto or item.startswith(visto + ".") for visto in ITENS_VISTOS_NA_2025)
        for item in itens
    )


def ref(norma: str, texto: str, *, vista_na_2025: bool = False) -> str:
    """Referência com a edição; na 2025, o item ainda não visto no texto leva "(a confirmar)"."""
    visto = norma == NBR_2008 or vista_na_2025 or item_visto_na_2025(texto)
    return f"{norma_curta(norma)} {texto}" + ("" if visto else f" {MARCA_A_CONFIRMAR}")


def a_confirmar(referencia: str) -> bool:
    """A referência traz um item da edição atual ainda não visto no texto?"""
    return MARCA_A_CONFIRMAR in referencia


def tabela(norma: str, chave: str) -> str:
    return TABELAS[norma][chave]


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


# =============================================================================================
# Coeficientes de ponderação
# =============================================================================================
@dataclass(frozen=True)
class Coeficientes:
    a1: float  # escoamento, flambagem (Tabela 3)
    a2: float  # ruptura
    w1: float  # metal da solda, penetração parcial sob tração ou compressão normal
    w2: float  # metal da solda ao cisalhamento (filete, penetração parcial, tampão)


def coeficientes(combinacao: str) -> Coeficientes:
    """NBR 8800 Tabela 3 (γ_a1, γ_a2) e notas da tabela das soldas (γ_w1, γ_w2)."""
    if combinacao == COMBINACAO_NORMAL:
        return Coeficientes(1.10, 1.35, 1.25, 1.35)
    if combinacao == COMBINACAO_EXCEPCIONAL:
        return Coeficientes(1.00, 1.15, 1.05, 1.15)
    raise SoldaInvalida(f"Combinação desconhecida: {combinacao!r}.")


def ref_gama_w(norma: str, qual: str) -> str:
    """De onde vem o γ_w1 ou γ_w2 (``qual`` = "w1" ou "w2")."""
    return f"{tabela(norma, 'resistencia')}, {tabela(norma, 'nota_' + qual)}"


# =============================================================================================
# Limites geométricos (6.2.6)
# =============================================================================================
def perna_minima(t_menor_mm: float) -> float:
    """Tabela 11 (2025) / Tabela 10 (2008), pela parte menos espessa; executada num só passe."""
    if t_menor_mm <= CHAPA_QUARTO_DE_POLEGADA + 1e-9:
        return 3.0
    if t_menor_mm <= CHAPA_MEIA_POLEGADA + 1e-9:
        return 5.0
    if t_menor_mm <= CHAPA_TRES_QUARTOS + 1e-9:
        return 6.0
    return 8.0


#: 6.2.6.2.2: espessura a partir da qual a perna máxima na borda é t − 1,5 mm.
LIMITE_DA_PERNA_MAXIMA = {NBR_2025: 6.3, NBR_2008: 6.35}


def perna_maxima(t_borda_mm: float, norma: str = NBR_2025) -> float:
    """6.2.6.2.2: ao longo da borda de uma chapa, t (t < 6,3 mm; 6,35 na 2008) ou t − 1,5 mm."""
    limite = LIMITE_DA_PERNA_MAXIMA[norma]
    return t_borda_mm if t_borda_mm < limite - 1e-9 else t_borda_mm - 1.5


def garganta_minima(t_menor_mm: float, norma: str) -> float:
    """Tabela 10 (2025) / Tabela 9 (2008): garganta efetiva mínima da penetração parcial."""
    faixas = (
        (CHAPA_QUARTO_DE_POLEGADA, 3.0),
        (CHAPA_MEIA_POLEGADA, 5.0),
        (CHAPA_TRES_QUARTOS, 6.0),
        (37.5, 8.0),
        (57.0, 10.0),
        (150.0 if norma == NBR_2025 else 152.0, 13.0),
    )
    for limite, garganta in faixas:
        if t_menor_mm <= limite + 1e-9:
            return garganta
    return 16.0


def comprimento_minimo(perna_mm: float) -> float:
    """6.2.6.2.3 e 6.2.6.2.4: o filete (ou o segmento intermitente) tem L ≥ 4·perna e ≥ 40 mm."""
    return max(4.0 * perna_mm, COMPRIMENTO_MINIMO_ABSOLUTO)


def perna_considerada(perna_mm: float, comprimento_mm: float) -> float:
    """6.2.6.2.3: com L < 4·perna, a perna considerada no cálculo é L/4."""
    return min(perna_mm, comprimento_mm / 4.0)


def cobrimento_minimo(t_menor_mm: float) -> float:
    """6.2.6.2.5: na ligação por superposição, ≥ 5·t da parte menos espessa e ≥ 25 mm."""
    return max(5.0 * t_menor_mm, COBRIMENTO_MINIMO_ABSOLUTO)


def beta_filete_longo(comprimento_mm: float, perna_mm: float) -> float:
    """6.2.2.2 d): filete longitudinal na extremidade de barra axial, β = 1,2 − 0,002·L/d_w ∈ [0,6; 1]."""
    return min(1.0, max(0.6, 1.2 - 0.002 * comprimento_mm / perna_mm))


#: 6.2.2.2 d) da 2025: com L > 300·d_w, o comprimento efetivo é 180·d_w (a 2008 não tem o teto).
RAZAO_DO_FILETE_MUITO_LONGO = 300.0
EFETIVO_DO_FILETE_MUITO_LONGO = 180.0


def comprimento_efetivo_longitudinal(comprimento_mm: float, perna_mm: float, norma: str) -> float:
    """6.2.2.2 d): β·L; na 2025, com L > 300·d_w, 180·d_w (o filete mais longo não rende mais)."""
    if norma == NBR_2025 and comprimento_mm > RAZAO_DO_FILETE_MUITO_LONGO * perna_mm + 1e-9:
        return EFETIVO_DO_FILETE_MUITO_LONGO * perna_mm
    return beta_filete_longo(comprimento_mm, perna_mm) * comprimento_mm


def texto_comprimento_efetivo(comprimento_mm: float, perna_mm: float, norma: str) -> str:
    """O trecho da fórmula que explica o comprimento efetivo ("" quando L inteiro vale)."""
    efetivo = comprimento_efetivo_longitudinal(comprimento_mm, perna_mm, norma)
    if efetivo >= comprimento_mm - 1e-9:
        return ""
    if norma == NBR_2025 and comprimento_mm > RAZAO_DO_FILETE_MUITO_LONGO * perna_mm + 1e-9:
        return (
            f"; L > 300·d_w: comprimento efetivo 180·d_w = {_n(efetivo, 0)} mm (filete longo, "
            "6.2.2.2 d)"
        )
    return f"; β = {_n(efetivo / comprimento_mm, 3)} (filete longo, 6.2.2.2 d)"


def adotar(valor_mm: float, passo_mm: float = 5.0) -> float:
    """O valor arredondado para cima no passo de projeto (5 mm por padrão)."""
    if passo_mm <= 0:
        return valor_mm
    return math.ceil(valor_mm / passo_mm - 1e-9) * passo_mm


# =============================================================================================
# Resistências
# =============================================================================================
def fator_direcao(theta_graus: float) -> float:
    """6.2.5.2 a): 1 + 0,5·sen^1,5 θ, θ entre a resultante e o eixo do filete (0° a 90°)."""
    theta = math.radians(min(90.0, max(0.0, abs(theta_graus))))
    return 1.0 + 0.5 * math.sin(theta) ** 1.5


def resistencia_filete_por_mm(perna_mm: float, f_w: float, gama_w2: float) -> float:
    """Metal da solda, por mm de filete (kN/mm): 0,60·f_w·(0,707·perna)/γ_w2."""
    return 0.60 * f_w * GARGANTA_DO_FILETE * perna_mm / gama_w2 / 1000.0


def metal_base_ao_cisalhamento_por_mm(
    t_mm: float, f_y: float, f_u: float, c: Coeficientes
) -> tuple[float, str]:
    """6.5.5 na espessura t, por mm de linha (kN/mm): o menor entre escoamento e ruptura."""
    escoamento = 0.60 * f_y * t_mm / c.a1 / 1000.0
    ruptura = 0.60 * f_u * t_mm / c.a2 / 1000.0
    if escoamento <= ruptura:
        return escoamento, "escoamento 0,60·f_y·t/γ_a1"
    return ruptura, "ruptura 0,60·f_u·t/γ_a2"


def combinacao_longitudinal_transversal(f_longitudinal: float, f_transversal: float) -> float:
    """6.2.5.2 c): o maior entre F_wl + F_wt e 0,85·F_wl + 1,5·F_wt (valores da tabela, sem 6.2.5.2 a)."""
    return max(f_longitudinal + f_transversal, 0.85 * f_longitudinal + 1.5 * f_transversal)


def forca_minima_da_ligacao(forca_kN: float, aplica: bool) -> float:
    """6.1.5.2: a ligação com força de cálculo < 45 kN é dimensionada para 45 kN (com as exceções)."""
    if not aplica:
        return abs(forca_kN)
    return max(abs(forca_kN), FORCA_MINIMA_DA_LIGACAO_KN)


# =============================================================================================
# Compatibilidade do metal da solda (Tabela 7 da 2008; coluna de compatibilidade da 2025)
# =============================================================================================
#: Classes compatíveis por grupo de metal-base (SMAW: E60XX/E70XX, E70XX, E80XX).
CLASSES_COMPATIVEIS = {"I": ("E60", "E70"), "II": ("E70",), "III": ("E80",)}


def grupo_do_aco(aco: str, t_mm: float) -> str | None:
    """Grupo do metal-base na Tabela 7 (2008); ``None`` quando o aço não está lá."""
    if aco == "ASTM A36":
        return "I" if t_mm <= CHAPA_TRES_QUARTOS + 1e-9 else "II"
    if aco in ("ASTM A572 Gr 50", "ASTM A588", "ASTM A992"):
        return "II"
    if aco.startswith("CF-26"):
        return "I"
    if aco.startswith("CF-28"):
        return "II"
    return None


def eletrodo_compativel(
    aco: str, t_mm: float, eletrodo: str, *, so_a_maior_classe: bool = False
) -> bool | None:
    """O eletrodo serve ao metal-base? ``None`` quando o aço não está na tabela de compatibilidade.

    ``so_a_maior_classe``: penetração total sob tração normal — com duas classes compatíveis no
    grupo, só a de maior resistência (nota e da tabela das soldas).
    """
    grupo = grupo_do_aco(aco, t_mm)
    if grupo is None:
        return None
    classes = CLASSES_COMPATIVEIS[grupo]
    if so_a_maior_classe:
        classes = classes[-1:]
    return eletrodo in classes


def eletrodo_compativel_a_compressao(aco: str, t_mm: float, eletrodo: str) -> bool | None:
    """Penetração total à compressão normal (2025): até 70 MPa abaixo do compatível é permitido."""
    grupo = grupo_do_aco(aco, t_mm)
    if grupo is None:
        return None
    compativel = ELETRODOS[CLASSES_COMPATIVEIS[grupo][-1]]
    return ELETRODOS[eletrodo] >= compativel - 70.0 - 1e-9


# =============================================================================================
# Método do centro instantâneo de rotação (6.2.5.2 b)
# =============================================================================================
@dataclass(frozen=True)
class Segmento:
    """Um filete reto, de (x1, y1) a (x2, y2), em mm."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def comprimento(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass(frozen=True)
class ResultadoCentroInstantaneo:
    """``fator``: quantas vezes a carga (P, M) cabe no grupo; aproveitamento = 1/fator."""

    fator: float
    x_mm: float  # centro instantâneo, medido do centro geométrico do grupo
    y_mm: float
    convergiu: bool
    capacidade_kN: float  # fator·|P| (ou fator·|M| em kN·m quando P = 0)


def centroide(segmentos: Sequence[Segmento]) -> tuple[float, float, float]:
    """(x̄, ȳ, L total) do grupo de linhas."""
    total = sum(s.comprimento for s in segmentos)
    if total <= 0:
        raise SoldaInvalida("O grupo de filetes precisa de comprimento.")
    xc = sum((s.x1 + s.x2) / 2 * s.comprimento for s in segmentos) / total
    yc = sum((s.y1 + s.y2) / 2 * s.comprimento for s in segmentos) / total
    return xc, yc, total


def momento_polar(segmentos: Sequence[Segmento]) -> float:
    """J do grupo de linhas (mm³ por mm de garganta unitária), em torno do centro geométrico."""
    xc, yc, _ = centroide(segmentos)
    j = 0.0
    for s in segmentos:
        c = s.comprimento
        mx, my = (s.x1 + s.x2) / 2 - xc, (s.y1 + s.y2) / 2 - yc
        j += c * (mx**2 + my**2) + c**3 / 12
    return j


def _elementos(
    segmentos: Sequence[Segmento], por_segmento: int
) -> list[tuple[float, float, float, float, float]]:
    """(x, y, comprimento, eixo_x, eixo_y) de cada elemento, com o centro geométrico na origem."""
    xc, yc, _ = centroide(segmentos)
    saida = []
    for s in segmentos:
        c = s.comprimento
        if c <= 0:
            continue
        ax, ay = (s.x2 - s.x1) / c, (s.y2 - s.y1) / c
        for k in range(por_segmento):
            f = (k + 0.5) / por_segmento
            saida.append(
                (
                    s.x1 + (s.x2 - s.x1) * f - xc,
                    s.y1 + (s.y2 - s.y1) * f - yc,
                    c / por_segmento,
                    ax,
                    ay,
                )
            )
    return saida


def deformacao_ultima(theta_graus: float, perna_mm: float) -> float:
    """Δu = 1,087·(θ + 6)^−0,65·d_w ≤ 0,17·d_w (6.2.5.2 b)."""
    return min(1.087 * (theta_graus + 6.0) ** -0.65, 0.17) * perna_mm


def deformacao_na_tensao_maxima(theta_graus: float, perna_mm: float) -> float:
    """Δm = 0,209·(θ + 2)^−0,32·d_w (6.2.5.2 b; igual ao AISC 360-16 J2.4)."""
    return 0.209 * (theta_graus + 2.0) ** -0.32 * perna_mm


def fator_deformacao(p: float) -> float:
    """f(p) = [p·(1,9 − 0,9·p)]^0,3 (6.2.5.2 b)."""
    base = p * (1.9 - 0.9 * p)
    return base**0.3 if base > 0 else 0.0


def _forcas_no_centro(
    elementos: Sequence[tuple[float, float, float, float, float]],
    x0: float,
    y0: float,
    sentido: float,
    perna_mm: float,
    q_por_mm: float,
) -> tuple[float, float, float, float]:
    """(ΣR·dx, ΣR·dy, ΣR·ρ, ΣR) dos elementos girando em torno de (x0, y0) no sentido dado.

    A deformação última limita o elemento pela ponta dele mais distante do centro (a ponta do
    filete), não pelo meio: com elementos finitos o resultado fica do lado da segurança.
    """
    dados = []
    for x, y, comp, ax, ay in elementos:
        rx, ry = x - x0, y - y0
        rho = math.hypot(rx, ry)
        if rho < 1e-9:
            continue
        dx, dy = -sentido * ry / rho, sentido * rx / rho  # deslocamento do elemento
        cos_t = min(1.0, abs(dx * ax + dy * ay))
        theta = math.degrees(math.acos(cos_t))
        meio = comp / 2
        ponta = max(math.hypot(rx + s * meio * ax, ry + s * meio * ay) for s in (-1.0, 1.0))
        dados.append((rho, ponta, dx, dy, comp, theta, deformacao_ultima(theta, perna_mm)))
    if not dados:
        return 0.0, 0.0, 0.0, 0.0
    k = min(du / ponta for _rho, ponta, _dx, _dy, _c, _t, du in dados)  # Δu_crit / r_crit
    sx = sy = sm = st = 0.0
    for rho, _ponta, dx, dy, comp, theta, _du in dados:
        p = rho * k / deformacao_na_tensao_maxima(theta, perna_mm)
        r = q_por_mm * comp * fator_direcao(theta) * fator_deformacao(p)
        sx += r * dx
        sy += r * dy
        sm += r * rho
        st += r
    return sx, sy, sm, st


def centro_instantaneo(
    segmentos: Sequence[Segmento],
    perna_mm: float,
    q_por_mm: float,
    px_kN: float,
    py_kN: float,
    m_kNmm: float,
    *,
    por_segmento: int = 40,
) -> ResultadoCentroInstantaneo:
    """Capacidade do grupo de filetes no plano pelo centro instantâneo de rotação (6.2.5.2 b).

    A carga é (P_x, P_y) pelo centro geométrico mais o momento M (anti-horário positivo).
    ``q_por_mm`` é 0,60·f_w·(0,707·d_w)/γ_w2 em kN/mm. O centro instantâneo (x0, y0) sai do
    equilíbrio: ΣR_i·d_i = λ·P e ΣR_i·ρ_i = λ·M_CI, com o elemento mais distante na deformação
    última; λ é o fator de capacidade.
    """
    if abs(m_kNmm) < 1e-9:
        raise SoldaInvalida("Sem momento a carga passa pelo centro: use 6.2.5.2 a) ou c).")
    elementos = _elementos(segmentos, por_segmento)
    _, _, total = centroide(segmentos)
    j = momento_polar(segmentos)
    p = math.hypot(px_kN, py_kN)
    escala = max(math.sqrt(j / total), 1.0)
    if p > 0:
        x_el, y_el = -py_kN * j / (m_kNmm * total), px_kN * j / (m_kNmm * total)  # CI elástico
        escala = max(escala, math.hypot(x_el, y_el))
    else:
        x_el, y_el = 0.0, 0.0

    def residuo(xi: float, eta: float) -> tuple[float, float, float]:
        x0, y0 = xi * escala, eta * escala
        m_ci = m_kNmm - x0 * py_kN + y0 * px_kN
        if abs(m_ci) < 1e-12:
            return 1e6, 1e6, 0.0
        sentido = 1.0 if m_ci > 0 else -1.0
        sx, sy, sm, st = _forcas_no_centro(elementos, x0, y0, sentido, perna_mm, q_por_mm)
        lam = sm / abs(m_ci)
        norma = max(st, 1e-12)  # a soma das forças dos elementos: vale também sem P
        return (sx - lam * px_kN) / norma, (sy - lam * py_kN) / norma, lam

    xi, eta = x_el / escala, y_el / escala
    r1, r2, lam = residuo(xi, eta)
    convergiu = False
    for _ in range(80):
        erro = math.hypot(r1, r2)
        if erro < 1e-7:
            convergiu = True
            break
        h = 1e-6
        a1, a2, _ = residuo(xi + h, eta)
        b1, b2, _ = residuo(xi, eta + h)
        j11, j21 = (a1 - r1) / h, (a2 - r2) / h
        j12, j22 = (b1 - r1) / h, (b2 - r2) / h
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-14:
            break
        dxi = -(r1 * j22 - r2 * j12) / det
        deta = -(j11 * r2 - j21 * r1) / det
        passo = 1.0
        for _ in range(30):  # Newton amortecido: só aceita o passo que reduz o resíduo
            n1, n2, nlam = residuo(xi + passo * dxi, eta + passo * deta)
            if math.hypot(n1, n2) < erro:
                xi, eta, r1, r2, lam = xi + passo * dxi, eta + passo * deta, n1, n2, nlam
                break
            passo /= 2
        else:
            break
    capacidade = lam * p if p > 0 else lam * abs(m_kNmm) / 1000.0
    return ResultadoCentroInstantaneo(lam, xi * escala, eta * escala, convergiu, capacidade)


# =============================================================================================
# Linhas de verificação comuns
# =============================================================================================
def linha_minimo(
    nome: str, exigido: float, adotado: float, unidade: str, referencia: str, formula: str
) -> Verificacao:
    """Limite inferior: passa com adotado ≥ exigido."""
    status = "OK" if adotado >= exigido - 1e-9 else "NÃO OK"
    return Verificacao(
        nome, exigido, adotado, unidade, referencia, formula, status=status, tipo="limite"
    )


def linha_maximo(
    nome: str, valor: float, limite: float, unidade: str, referencia: str, formula: str
) -> Verificacao:
    status = "OK" if valor <= limite + 1e-9 else "NÃO OK"
    return Verificacao(
        nome, valor, limite, unidade, referencia, formula, status=status, tipo="limite"
    )


def limites_do_filete(
    norma: str,
    perna_mm: float,
    t_menor_mm: float,
    t_borda_mm: float | None,
    comprimento_mm: float,
    rotulo: str = "",
    *,
    nome_do_comprimento: str = "comprimento mínimo",
) -> list[Verificacao]:
    """Perna mínima (Tabela 11/10), perna máxima na borda (6.2.6.2.2) e comprimento (6.2.6.2.3)."""
    sufixo = f" ({rotulo})" if rotulo else ""
    linhas = [
        linha_minimo(
            f"Solda: perna mínima{sufixo}",
            perna_minima(t_menor_mm),
            perna_mm,
            "mm",
            ref(norma, f"6.2.6.2.1, {tabela(norma, 'perna')}", vista_na_2025=True),
            f"parte menos espessa t = {_n(t_menor_mm, 2)} mm; filete de um passe",
        )
    ]
    if t_borda_mm is not None:
        linhas.append(
            linha_maximo(
                f"Solda: perna máxima na borda da chapa{sufixo}",
                perna_mm,
                perna_maxima(t_borda_mm, norma),
                "mm",
                ref(norma, "6.2.6.2.2"),
                f"t = {_n(t_borda_mm, 2)} mm: t < {_n(LIMITE_DA_PERNA_MAXIMA[norma])} mm → perna ≤ t; "
                "senão perna ≤ t − 1,5 mm",
            )
        )
    linhas.append(
        linha_minimo(
            f"Solda: {nome_do_comprimento}{sufixo}",
            comprimento_minimo(perna_mm),
            comprimento_mm,
            "mm",
            ref(norma, "6.2.6.2.3" if "segmento" not in nome_do_comprimento else "6.2.6.2.4"),
            "L ≥ 4·perna e ≥ 40 mm",
        )
    )
    return linhas
