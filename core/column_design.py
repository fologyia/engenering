"""Barras de aço comprimidas e flexo-comprimidas: fórmulas de norma (sem Streamlit).

Portado de ``flambagem_ref.py`` (módulo de referência validado) **sem alterar fórmulas**. Mudaram
só a tipagem, a ``Verificacao`` (agora a classe compartilhada de :mod:`core.verificacao`), as
guardas de entrada marcadas "Guarda:" e as lacunas marcadas "Acréscimo:" (cada uma coberta por
teste em ``tests/test_column_design.py``).

Seções: I/H (laminado ou soldado), U, tubo retangular, tubo circular, barra maciça circular e
retangular, e seção genérica de catálogo. Normas (parâmetro ``norma``):

    "NBR8800_2008"     ABNT NBR 8800:2008 (vigente) — flambagem local pelo fator Q = Qs·Qa (Anexo F)
    "NBR8800_2024"     Projeto de revisão ABNT NBR 8800 (maio/2024, Rev6) — área efetiva A_ef (5.3.4)
    "AISC360_16_LRFD"  AISC 360-16, LRFD (φ_c = φ_b = 0,90) — mesmas equações do Projeto 2024

Critério de cliente: Anglo American AA-BR-DPST-DR-0001 (8.3 esbeltez limite; 8.8 espessuras mínimas;
5.9 combinações pela NBR 8800 e/ou AISC 360-16).

Validação (ver tests/test_column_design.py): AISC Design Guide 29 (HSS8×8×1/2, 24 ft: φP_n = 306 kips;
F_cre = 41,9 ksi) e o programa "Flambagem de colunas" (barra circular Ø50: N_c,Rd = 120,71 kN).

Unidades internas: mm, MPa, N. Funções públicas devolvem kN e kN·m.
Itens marcados "CONFERIR" vieram da NBR 8800:2008, que não estava nos arquivos de referência.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from core.verificacao import Verificacao

E_ACO = 200000.0
G_ACO = 77000.0
NORMAS = ("NBR8800_2008", "NBR8800_2024", "AISC360_16_LRFD")
PI2 = math.pi**2


def _check(norma: str) -> None:
    if norma not in NORMAS:
        raise ValueError(f"norma inválida: {norma}. Use uma de {NORMAS}")


def fator_resistencia(norma: str, gama_a1: float = 1.10) -> float:
    """1/γ_a1 (NBR, Tabela 3) ou φ = 0,90 (AISC E1/F1)."""
    _check(norma)
    return 0.90 if norma == "AISC360_16_LRFD" else 1 / gama_a1


# ---------------------------------------------------------------------------------------------
# SEÇÕES
# ---------------------------------------------------------------------------------------------
@dataclass
class Secao:
    """Propriedades em mm, mm², mm⁴, mm⁶. x = eixo de maior inércia (perpendicular à alma em I e U).
    x0, y0 = coordenadas do centro de cisalhamento em relação ao centroide.
    elementos: lista de dicts para flambagem local, cada um com
        tipo 'AA' ou 'AL', grupo (Tabela 4 / Tabela F.1), b, t, n (quantidade), kc (grupo 5), tubo_ret (bool).
    Para perfis laminados de catálogo, prefira `secao_generica` com A, I, J, C_w, x0 do catálogo
    (mesas inclinadas e raios de concordância mudam I_y, J e C_w)."""

    nome: str
    A: float
    Ix: float
    Iy: float
    J: float = 0.0
    Cw: float = 0.0
    x0: float = 0.0
    y0: float = 0.0
    Wx: float | None = None
    Wy: float | None = None
    Zx: float | None = None
    Zy: float | None = None
    tipo: str = "generica"
    elementos: list[dict[str, Any]] = field(default_factory=list)
    torcao_relevante: bool = True
    D_t: float | None = None
    dims: dict[str, Any] = field(default_factory=dict)

    @property
    def rx(self) -> float:
        return math.sqrt(self.Ix / self.A)

    @property
    def ry(self) -> float:
        return math.sqrt(self.Iy / self.A)

    @property
    def r0(self) -> float:
        return math.sqrt(self.rx**2 + self.ry**2 + self.x0**2 + self.y0**2)


def secao_generica(
    nome: str,
    A: float,
    Ix: float,
    Iy: float,
    J: float = 0.0,
    Cw: float = 0.0,
    x0: float = 0.0,
    y0: float = 0.0,
    Wx: float | None = None,
    Wy: float | None = None,
    Zx: float | None = None,
    Zy: float | None = None,
    elementos: list[dict[str, Any]] | None = None,
    torcao_relevante: bool = True,
    tipo: str = "generica",
) -> Secao:
    return Secao(
        nome, A, Ix, Iy, J, Cw, x0, y0, Wx, Wy, Zx, Zy, tipo, elementos or [], torcao_relevante
    )


def secao_circular_macica(d: float) -> Secao:
    A = math.pi * d**2 / 4
    I = math.pi * d**4 / 64
    W = math.pi * d**3 / 32
    Z = d**3 / 6
    return Secao(
        f"Circular maciça Ø{d:g}",
        A,
        I,
        I,
        J=2 * I,
        Wx=W,
        Wy=W,
        Zx=Z,
        Zy=Z,
        tipo="circ_macica",
        torcao_relevante=False,
        dims=dict(d=d),
    )


def secao_retangular_macica(b: float, h: float) -> Secao:
    """b ao longo de x, h ao longo de y (eixo x = maior inércia se h > b)."""
    A = b * h
    t_, b_ = min(b, h), max(b, h)
    J = b_ * t_**3 / 3 * (1 - 0.63 * t_ / b_)
    return Secao(
        f"Retangular maciça {b:g}×{h:g}",
        A,
        b * h**3 / 12,
        h * b**3 / 12,
        J=J,
        Wx=b * h**2 / 6,
        Wy=h * b**2 / 6,
        Zx=b * h**2 / 4,
        Zy=h * b**2 / 4,
        tipo="ret_macica",
        torcao_relevante=False,
        dims=dict(b=b, h=h),
    )


def secao_tubo_circular(D: float, t: float) -> Secao:
    Di = D - 2 * t
    A = math.pi * (D**2 - Di**2) / 4
    I = math.pi * (D**4 - Di**4) / 64
    return Secao(
        f"Tubo circular Ø{D:g}×{t:g}",
        A,
        I,
        I,
        J=2 * I,
        Wx=2 * I / D,
        Wy=2 * I / D,
        Zx=(D**3 - Di**3) / 6,
        Zy=(D**3 - Di**3) / 6,
        tipo="tubo_circ",
        torcao_relevante=False,
        D_t=D / t,
        dims=dict(D=D, t=t),
    )


def secao_tubo_retangular(
    B: float, H: float, t: float, b_plano: float | None = None, h_plano: float | None = None
) -> Secao:
    """Cantos vivos (propriedades aproximadas). Larguras planas padrão = lado − 3t (AISC B4.1b; sem raio informado)."""
    Bi, Hi = B - 2 * t, H - 2 * t
    A = B * H - Bi * Hi
    Ix = (B * H**3 - Bi * Hi**3) / 12
    Iy = (H * B**3 - Hi * Bi**3) / 12
    J = 2 * t * (B - t) ** 2 * (H - t) ** 2 / ((B - t) + (H - t))
    bp = b_plano if b_plano is not None else B - 3 * t
    hp = h_plano if h_plano is not None else H - 3 * t
    el: list[dict[str, Any]] = [
        dict(tipo="AA", grupo=1, b=bp, t=t, n=2, tubo_ret=True),
        dict(tipo="AA", grupo=1, b=hp, t=t, n=2, tubo_ret=True),
    ]
    return Secao(
        f"Tubo retangular {B:g}×{H:g}×{t:g}",
        A,
        Ix,
        Iy,
        J=J,
        Wx=2 * Ix / H,
        Wy=2 * Iy / B,
        Zx=(B * H**2 - Bi * Hi**2) / 4,
        Zy=(H * B**2 - Hi * Bi**2) / 4,
        tipo="tubo_ret",
        elementos=el,
        torcao_relevante=False,
        dims=dict(B=B, H=H, t=t, b=bp, h=hp),
    )


def secao_I(
    d: float, bf: float, tf: float, tw: float, soldado: bool = False, h: float | None = None
) -> Secao:
    """I/H duplamente simétrico. h = altura plana da alma (laminado: d − 2(tf + raio); padrão d − 2tf)."""
    hw = d - 2 * tf
    h = h if h is not None else hw
    A = 2 * bf * tf + hw * tw
    Ix = (bf * d**3 - (bf - tw) * hw**3) / 12
    Iy = 2 * tf * bf**3 / 12 + hw * tw**3 / 12
    J = (2 * bf * tf**3 + hw * tw**3) / 3
    Cw = Iy * (d - tf) ** 2 / 4  # Projeto NBR D.2.8 a)
    kc = min(0.76, max(0.35, 4 / math.sqrt(h / tw)))
    grupo_mesa = 5 if soldado else 4
    el: list[dict[str, Any]] = [
        dict(tipo="AL", grupo=grupo_mesa, b=bf / 2, t=tf, n=4, kc=kc),
        dict(tipo="AA", grupo=2, b=h, t=tw, n=1),
    ]
    return Secao(
        f"I {d:g}×{bf:g}×{tf:g}×{tw:g}{' (soldado)' if soldado else ''}",
        A,
        Ix,
        Iy,
        J,
        Cw,
        Wx=2 * Ix / d,
        Wy=2 * Iy / bf,
        Zx=bf * tf * (d - tf) + tw * hw**2 / 4,
        Zy=bf**2 * tf / 2 + hw * tw**2 / 4,
        tipo="I",
        elementos=el,
        dims=dict(d=d, bf=bf, tf=tf, tw=tw, h=h, soldado=soldado, kc=kc),
    )


def _zy_do_U(bf: float, tf: float, tw: float, hw: float) -> float:
    """Acréscimo: Z_y do U (eixo paralelo à alma). A LNP divide a área ao meio; Z = ∫|x − x_p| dA."""
    area = 2 * bf * tf + hw * tw
    if (2 * tf + hw) * tw >= area / 2:  # LNP dentro da espessura da alma
        xp = (area / 2) / (2 * tf + hw)
    else:  # LNP na região das mesas
        xp = (area / 2 - hw * tw) / (2 * tf)

    def integral(w: float) -> float:  # ∫_0^w |x − x_p| dx
        return xp * w - w * w / 2 if xp >= w else (xp**2 + (w - xp) ** 2) / 2

    return 2 * tf * integral(bf) + hw * integral(tw)


def secao_U(
    d: float, bf: float, tf: float, tw: float, soldado: bool = False, h: float | None = None
) -> Secao:
    """U com alma vertical (eixo de simetria = x). Mesas de espessura constante (idealizado)."""
    hw = d - 2 * tf
    h = h if h is not None else hw
    A = 2 * bf * tf + hw * tw
    xb = (2 * bf * tf * bf / 2 + hw * tw * tw / 2) / A  # centroide medido do dorso da alma
    Ix = (bf * d**3 - (bf - tw) * hw**3) / 12
    Iy = (
        2 * (tf * bf**3 / 12 + bf * tf * (bf / 2 - xb) ** 2)
        + hw * tw**3 / 12
        + hw * tw * (tw / 2 - xb) ** 2
    )
    J = (2 * bf * tf**3 + hw * tw**3) / 3
    b_, h_ = bf - 0.5 * tw, d - tf
    Cw = (
        tf * b_**3 * h_**2 / 12 * (3 * b_ * tf + 2 * h_ * tw) / (6 * b_ * tf + h_ * tw)
    )  # Projeto NBR D.2.8 a)
    e0 = (
        3 * tf * b_**2 / (6 * b_ * tf + h_ * tw)
    )  # CC a partir do eixo da alma (lado oposto às mesas)
    x0 = e0 + (xb - tw / 2)
    kc = min(0.76, max(0.35, 4 / math.sqrt(h / tw)))
    el: list[dict[str, Any]] = [
        dict(tipo="AL", grupo=5 if soldado else 4, b=bf, t=tf, n=2, kc=kc),
        dict(tipo="AA", grupo=2, b=h, t=tw, n=1),
    ]
    Zy_plastico = _zy_do_U(bf, tf, tw, hw)
    return Secao(
        f"U {d:g}×{bf:g}×{tf:g}×{tw:g}",
        A,
        Ix,
        Iy,
        J,
        Cw,
        x0=x0,
        y0=0.0,
        Wx=2 * Ix / d,
        Wy=Iy / (bf - xb),
        Zx=bf * tf * (d - tf) + tw * hw**2 / 4,
        Zy=Zy_plastico,
        tipo="U",
        elementos=el,
        dims=dict(d=d, bf=bf, tf=tf, tw=tw, h=h, xb=xb, soldado=soldado, kc=kc),
    )


# ---------------------------------------------------------------------------------------------
# COEFICIENTE DE FLAMBAGEM K (NBR 8800:2008 Tabela E.1 — CONFERIR)
# ---------------------------------------------------------------------------------------------
K_TABELA_E1: dict[str, tuple[float, float]] = {
    "engaste-engaste": (0.5, 0.65),
    "engaste-rotula": (0.7, 0.80),
    "engaste-engaste_translacao_livre": (1.0, 1.2),
    "rotula-rotula": (1.0, 1.0),
    "engaste-livre": (2.0, 2.1),
    "rotula-engaste_translacao_livre": (2.0, 2.0),
}


def K_recomendado(condicao: str) -> float:
    return K_TABELA_E1[condicao][1]


# ---------------------------------------------------------------------------------------------
# FLAMBAGEM GLOBAL (NBR 5.3.5 / Anexo E de 2008; AISC E3/E4)
# ---------------------------------------------------------------------------------------------
def _flexo_torcao_mono(Na: float, Nz: float, razao: float) -> float:
    H = 1 - razao**2
    return (Na + Nz) / (2 * H) * (1 - math.sqrt(max(0.0, 1 - 4 * Na * Nz * H / (Na + Nz) ** 2)))


def forca_flambagem_elastica(
    sec: Secao,
    KxLx: float,
    KyLy: float,
    KzLz: float | None = None,
    E: float = E_ACO,
    G: float = G_ACO,
) -> dict[str, Any]:
    """N_e (kN) e o modo que governa. Dupla simetria: min(N_ex, N_ey, N_ez). Monossimétrica: modo acoplado
    flexo-torção (5.3.5.2). Assimétrica: menor raiz da equação cúbica. KzLz padrão = max(KxLx, KyLy)."""
    Nex = PI2 * E * sec.Ix / KxLx**2
    Ney = PI2 * E * sec.Iy / KyLy**2
    if not sec.torcao_relevante or (sec.J <= 0 and sec.Cw <= 0):
        Nez = math.inf
    else:
        KzLz = KzLz if KzLz else max(KxLx, KyLy)
        Nez = (PI2 * E * sec.Cw / KzLz**2 + G * sec.J) / sec.r0**2
    x0, y0, r0 = sec.x0, sec.y0, sec.r0
    modos: dict[str, float] = {}
    if Nez == math.inf:
        modos = {"flexão x": Nex, "flexão y": Ney}
    elif abs(x0) < 1e-9 and abs(y0) < 1e-9:
        modos = {"flexão x": Nex, "flexão y": Ney, "torção": Nez}
    elif abs(y0) < 1e-9:  # x é o eixo de simetria (ex.: U)
        modos = {"flexão y": Ney, "flexo-torção xz": _flexo_torcao_mono(Nex, Nez, x0 / r0)}
    elif abs(x0) < 1e-9:  # y é o eixo de simetria (ex.: T)
        modos = {"flexão x": Nex, "flexo-torção yz": _flexo_torcao_mono(Ney, Nez, y0 / r0)}
    else:

        def f(N: float) -> float:
            return (
                r0**2 * (N - Nex) * (N - Ney) * (N - Nez)
                - N**2 * (N - Ney) * x0**2
                - N**2 * (N - Nex) * y0**2
            )

        lo, hi = 0.0, min(Nex, Ney, Nez)
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        modos = {"flexo-torção (assimétrica)": (lo + hi) / 2}
    modo = min(modos, key=lambda nome: modos[nome])
    return dict(
        Nex=Nex / 1000,
        Ney=Ney / 1000,
        Nez=Nez / 1000 if Nez != math.inf else math.inf,
        modos={k: v / 1000 for k, v in modos.items()},
        Ne=modos[modo] / 1000,
        modo=modo,
    )


def fator_chi(lambda0: float) -> float:
    """NBR 5.3.3 / AISC E3: χ = 0,658^(λ0²) para λ0 ≤ 1,5; 0,877/λ0² acima."""
    return 0.658 ** (lambda0**2) if lambda0 <= 1.5 else 0.877 / lambda0**2


# ---------------------------------------------------------------------------------------------
# FLAMBAGEM LOCAL
# ---------------------------------------------------------------------------------------------
def bt_lim(el: dict[str, Any], fy: float, E: float = E_ACO) -> float:
    """(b/t)_lim — Projeto NBR Tabela 4 (= NBR 2008 Tabela F.1)."""
    g = el["grupo"]
    if g == 5:
        return 0.64 * math.sqrt(E / (fy / el["kc"]))
    return {1: 1.40, 2: 1.49, 3: 0.45, 4: 0.56, 6: 0.75}[g] * math.sqrt(E / fy)


def Qs_elemento_2008(el: dict[str, Any], fy: float, E: float = E_ACO) -> float:
    """NBR 8800:2008 Anexo F.2 (elementos AL) — CONFERIR. Mesmos valores do AISC 360-05 E7.1."""
    bt = el["b"] / el["t"]
    s = math.sqrt(E / fy)
    g = el["grupo"]
    if g == 3:
        if bt <= 0.45 * s:
            return 1.0
        if bt <= 0.91 * s:
            return 1.340 - 0.76 * bt / s
        return 0.53 * E / (fy * bt**2)
    if g == 4:
        if bt <= 0.56 * s:
            return 1.0
        if bt <= 1.03 * s:
            return 1.415 - 0.74 * bt / s
        return 0.69 * E / (fy * bt**2)
    if g == 5:
        kc = el["kc"]
        sk = math.sqrt(E / (fy / kc))
        if bt <= 0.64 * sk:
            return 1.0
        if bt <= 1.17 * sk:
            return 1.415 - 0.65 * bt / sk
        return 0.90 * E * kc / (fy * bt**2)
    if g == 6:
        if bt <= 0.75 * s:
            return 1.0
        if bt <= 1.03 * s:
            return 1.908 - 1.22 * bt / s
        return 0.69 * E / (fy * bt**2)
    raise ValueError("grupo AL inválido")


def bef_AA_2008(el: dict[str, Any], fy: float, sigma: float, E: float = E_ACO) -> float:
    """NBR 8800:2008 F.3.2 — CONFERIR: b_ef = 1,92 t √(E/σ)[1 − (c_a/(b/t))√(E/σ)] ≤ b;
    c_a = 0,38 (tubos retangulares) ou 0,34; σ = χ f_y com χ calculado para Q = 1 (ou σ = f_y, conservador).

    Correção (verificada por teste): o original decidia a redução pelo limite da Tabela F.1 (com f_y)
    mas aplicava a fórmula com σ < f_y. Em colunas muito esbeltas (χ pequeno) a largura efetiva
    saía NEGATIVA e ``resist_compressao`` quebrava com raiz de número negativo. Como na F.3.2 (e
    no AISC E7.2, e em :func:`bef_2024`), a redução só vale quando b/t > (b/t)_lim·√(f_y/σ), isto é,
    1,49·√(E/σ) (1,40 nos tubos retangulares). Com σ = f_y o resultado é idêntico ao original."""
    b, t = el["b"], el["t"]
    if b / t <= bt_lim(el, fy, E) * math.sqrt(fy / sigma):
        return b
    ca = 0.38 if el.get("tubo_ret") else 0.34
    r = math.sqrt(E / sigma)
    return min(b, 1.92 * t * r * (1 - ca / (b / t) * r))


def Q_tubo_circular(D_t: float, fy: float, E: float = E_ACO) -> float:
    """NBR 2008 F / Projeto 5.3.4.3: Q (ou A_ef/A_g) do tubo circular."""
    if D_t <= 0.11 * E / fy:
        return 1.0
    if D_t <= 0.45 * E / fy:
        return 0.038 * E / (fy * D_t) + 2 / 3
    raise ValueError("D/t > 0,45 E/f_y: tubo circular não previsto pela norma.")


def fator_Q_2008(sec: Secao, fy: float, chi_Q1: float, E: float = E_ACO) -> dict[str, float]:
    if sec.tipo == "tubo_circ":
        if sec.D_t is None:  # Guarda
            raise ValueError("D/t não informado para o tubo circular.")
        Q = Q_tubo_circular(sec.D_t, fy, E)
        return dict(Q=Q, Qs=1.0, Qa=Q)
    Qs = min([Qs_elemento_2008(e, fy, E) for e in sec.elementos if e["tipo"] == "AL"] or [1.0])
    perda = sum(
        (e["b"] - bef_AA_2008(e, fy, chi_Q1 * fy, E)) * e["t"] * e.get("n", 1)
        for e in sec.elementos
        if e["tipo"] == "AA"
    )
    Qa = (sec.A - perda) / sec.A
    return dict(Q=Qs * Qa, Qs=Qs, Qa=Qa)


def bef_2024(el: dict[str, Any], fy: float, chi: float, E: float = E_ACO) -> float:
    """Projeto NBR 8800:2024 5.3.4.2 (= AISC 360-16 E7.1): c1/c2 da Tabela 5."""
    b, t = el["b"], el["t"]
    lim = bt_lim(el, fy, E)
    if b / t <= lim / math.sqrt(chi):
        return b
    if el["tipo"] == "AL":
        c1, c2 = 0.22, 1.49
    elif el.get("tubo_ret"):
        c1, c2 = 0.20, 1.38
    else:
        c1, c2 = 0.18, 1.31
    sig_el = (c2 * lim / (b / t)) ** 2 * fy
    r = math.sqrt(sig_el / (chi * fy))
    return b * (1 - c1 * r) * r


def area_efetiva_2024(sec: Secao, fy: float, chi: float, E: float = E_ACO) -> float:
    if sec.tipo == "tubo_circ":
        if sec.D_t is None:  # Guarda
            raise ValueError("D/t não informado para o tubo circular.")
        return Q_tubo_circular(sec.D_t, fy, E) * sec.A
    perda = sum((e["b"] - bef_2024(e, fy, chi, E)) * e["t"] * e.get("n", 1) for e in sec.elementos)
    return sec.A - perda


# ---------------------------------------------------------------------------------------------
# COMPRESSÃO
# ---------------------------------------------------------------------------------------------
def resist_compressao(
    sec: Secao,
    fy: float,
    KxLx: float,
    KyLy: float,
    KzLz: float | None = None,
    norma: str = "NBR8800_2008",
    E: float = E_ACO,
    G: float = G_ACO,
    gama_a1: float = 1.10,
) -> dict[str, Any]:
    """N_c,Rd (kN) com TODOS os modos (x, y, torção/flexo-torção) e flambagem local.
    2008:  λ0 = √(Q A_g f_y/N_e);  N_c,Rd = χ Q A_g f_y/γ_a1.
    2024 / AISC-16:  λ0 = √(A_g f_y/N_e);  N_c,Rd = χ A_ef f_y × (1/γ_a1 ou 0,90)."""
    _check(norma)
    ne = forca_flambagem_elastica(sec, KxLx, KyLy, KzLz, E, G)
    Ne = ne["Ne"] * 1000
    out = dict(ne)
    if norma == "NBR8800_2008":
        chi_Q1 = fator_chi(math.sqrt(sec.A * fy / Ne))
        q = fator_Q_2008(sec, fy, chi_Q1, E)
        lam0 = math.sqrt(q["Q"] * sec.A * fy / Ne)
        chi = fator_chi(lam0)
        N = chi * q["Q"] * sec.A * fy * fator_resistencia(norma, gama_a1)
        out.update(q, A_ef=q["Q"] * sec.A)
    else:
        lam0 = math.sqrt(sec.A * fy / Ne)
        chi = fator_chi(lam0)
        Aef = area_efetiva_2024(sec, fy, chi, E)
        N = chi * Aef * fy * fator_resistencia(norma, gama_a1)
        out.update(A_ef=Aef, Q=Aef / sec.A)
    out.update(
        lambda0=lam0,
        chi=chi,
        Nc_Rd=N / 1000,
        esbeltez_x=KxLx / sec.rx,
        esbeltez_y=KyLy / sec.ry,
        esbeltez=max(KxLx / sec.rx, KyLy / sec.ry),
    )
    return out


# ---------------------------------------------------------------------------------------------
# FLEXÃO (Projeto NBR Anexo D, Tabela D.1; NBR 2008 Anexo G — CONFERIR; AISC F2/F3/F6/F11)
# ---------------------------------------------------------------------------------------------
def _interp(Mpl: float, Mr: float, lam: float, lp: float, lr: float) -> float:
    return Mpl - (Mpl - Mr) * (lam - lp) / (lr - lp)


def _flt_retangular(
    sec: Secao, fy: float, W: float, Mpl: float, Lb: float, Cb: float, E: float, nova: bool
) -> float:
    """FLT de barras retangulares maciças e tubos retangulares fletidos em torno do eixo de maior
    inércia: λ_p = 0,13 E √(JA)/M_pl, λ_r = 2,00 E √(JA)/M_r, M_cr = 2,00 C_b E √(JA)/λ (NBR Tab. G.1 /
    AISC F11 e F7.4)."""
    sJA = math.sqrt(sec.J * sec.A)
    lam = Lb / min(
        sec.rx, sec.ry
    )  # raio de giração em torno do eixo MENOR (o da flambagem lateral)
    Mr = fy * W
    lp = 0.13 * E * sJA / Mpl
    lr = 2.00 * E * (Cb if nova else 1.0) * sJA / Mr
    Mcr = 2.00 * Cb * E * sJA / lam
    if lam <= lp:
        M = Mpl
    elif lam <= lr:
        M = _interp(Mpl, Mr, lam, lp, lr) * (1.0 if nova else Cb)
    else:
        M = Mcr
    return min(M, Mpl)


def momento_resistente(
    sec: Secao,
    fy: float,
    eixo: str = "x",
    Lb: float = 0.0,
    Cb: float = 1.0,
    norma: str = "NBR8800_2008",
    E: float = E_ACO,
    gama_a1: float = 1.10,
) -> dict[str, Any]:
    """M_Rd (kN·m) e o estado-limite que governa. Implementado para:
      I/H duplamente simétricos e U: eixo x (FLT, FLM, FLA) e eixo y (FLM);
      barras maciças circulares (plastificação) e retangulares (FLT no eixo de maior inércia);
      tubos compactos (plastificação; FLT do tubo retangular — acréscimo, ver abaixo). Tubo não compacto
      → erro (implementar D.2.7).
    Limite: M_Rd ≤ 1,50 W f_y/γ_a1 (5.4.2.2)."""
    _check(norma)
    fat = fator_resistencia(norma, gama_a1)
    sig_r = 0.3 * fy
    res: dict[str, float] = {}
    W = sec.Wx if eixo == "x" else sec.Wy
    Z = sec.Zx if eixo == "x" else sec.Zy
    if Z is None:
        raise ValueError("Z (módulo plástico) não informado para este eixo.")
    if W is None:  # Guarda
        raise ValueError("W (módulo elástico) não informado para este eixo.")
    Mpl = Z * fy
    nova = norma == "NBR8800_2024"

    if sec.tipo in ("I", "U"):
        d = sec.dims
        laminado = not d["soldado"]
        bt = d["bf"] / (2 * d["tf"]) if sec.tipo == "I" else d["bf"] / d["tf"]
        lp_m = 0.38 * math.sqrt(E / fy)
        if laminado:
            lr_m = 0.83 * math.sqrt(E / (fy - sig_r))
            Mcr_m = 0.69 * E * W / bt**2 if bt > 0 else math.inf
        else:
            kc = d["kc"]
            lr_m = 0.95 * math.sqrt(E / ((fy - sig_r) / kc))
            Mcr_m = 0.90 * E * kc * W / bt**2
        Mr_m = (fy - sig_r) * W
        res["FLM"] = (
            Mpl if bt <= lp_m else (_interp(Mpl, Mr_m, bt, lp_m, lr_m) if bt <= lr_m else Mcr_m)
        )
        if eixo == "x":
            hw = d["h"] / d["tw"]
            lp_a, lr_a = 3.76 * math.sqrt(E / fy), 5.70 * math.sqrt(E / fy)
            if hw > lr_a:
                raise NotImplementedError(
                    "Alma esbelta (h/t_w > 5,70√(E/f_y)): vigas de alma esbelta — Anexo E (2024) / H (2008)."
                )
            res["FLA"] = Mpl if hw <= lp_a else _interp(Mpl, fy * W, hw, lp_a, lr_a)
            # FLT
            Iy, J, Cw, ry = sec.Iy, sec.J, sec.Cw, sec.ry
            if J <= 0 or Cw <= 0:  # Guarda: a FLT usa J e C_w (divisões por J e por C_w)
                raise ValueError("J e C_w devem ser positivos para a FLT de perfis I e U.")
            lam = Lb / ry if Lb > 0 else 0.0
            lp = 1.76 * math.sqrt(E / fy)
            Mr = (fy - sig_r) * W
            b1 = (fy - sig_r) * W / (E * J)
            cb_r = Cb if nova else 1.0  # Projeto 2024: λr e M_cr com C_b (D.2.8 a)
            lr = (
                1.38
                * cb_r
                * math.sqrt(Iy * J)
                / (ry * J * b1)
                * math.sqrt(1 + math.sqrt(1 + 27 * Cw * b1**2 / (cb_r**2 * Iy)))
            )
            if lam <= lp:
                Mflt = Mpl
            elif lam <= lr:
                Mflt = _interp(Mpl, Mr, lam, lp, lr) * (1.0 if nova else Cb)
            else:
                Mflt = Cb * PI2 * E * Iy / Lb**2 * math.sqrt(Cw / Iy * (1 + 0.039 * J * Lb**2 / Cw))
            res["FLT"] = min(Mflt, Mpl)
            res.update(_lambda_FLT=lam, _lp_FLT=lp, _lr_FLT=lr, _Mr_FLT=Mr)
    elif sec.tipo == "circ_macica":
        res["plastificação"] = Mpl
    elif sec.tipo == "ret_macica":
        res["plastificação"] = Mpl
        if Lb > 0 and (sec.Ix > sec.Iy if eixo == "x" else sec.Iy > sec.Ix):
            res["FLT"] = _flt_retangular(sec, fy, W, Mpl, Lb, Cb, E, nova)
    elif sec.tipo == "tubo_circ":
        if sec.D_t is None:  # Guarda
            raise ValueError("D/t não informado para o tubo circular.")
        if sec.D_t > 0.07 * E / fy:  # CONFERIR (λp da parede, 2008 Tab. G.1 / AISC F8)
            raise NotImplementedError(
                "Tubo circular não compacto à flexão: implementar a verificação da parede (norma)."
            )
        res["plastificação"] = Mpl
    elif sec.tipo == "tubo_ret":
        d = sec.dims
        bt_f = (d["b"] if eixo == "x" else d["h"]) / d["t"]
        bt_w = (d["h"] if eixo == "x" else d["b"]) / d["t"]
        if bt_f > 1.12 * math.sqrt(E / fy) or bt_w > 2.42 * math.sqrt(
            E / fy
        ):  # CONFERIR (λp FLM/FLA de tubos)
            raise NotImplementedError(
                "Tubo retangular não compacto: implementar FLM/FLA conforme D.2.7."
            )
        res["plastificação"] = Mpl
        # Acréscimo: a docstring prometia a FLT do tubo retangular, que faltava no código. Vale só
        # para o eixo de maior inércia (x numa seção em pé, y numa deitada) e seção não quadrada,
        # com as mesmas expressões da barra.
        if Lb > 0 and (sec.Ix > sec.Iy if eixo == "x" else sec.Iy > sec.Ix):
            res["FLT"] = _flt_retangular(sec, fy, W, Mpl, Lb, Cb, E, nova)
    else:
        raise NotImplementedError(
            "Tipo de seção sem rotina de M_Rd: informe M_Rd ou use I, U, tubo ou maciça."
        )
    gov = min((k for k in res if not k.startswith("_")), key=lambda k: res[k])
    M = min(res[gov], 1.5 * W * fy)
    if M < res[gov]:
        gov = "limite 1,5 W f_y (5.4.2.2)"
    estados = {k: v * fat / 1e6 for k, v in res.items() if not k.startswith("_")}
    aux = {k[1:]: v for k, v in res.items() if k.startswith("_")}
    return dict(MRd=M * fat / 1e6, governa=gov, Mpl=Mpl / 1e6, estados=estados, aux=aux)


def fator_Cb(M_max: float, M_A: float, M_B: float, M_C: float, Rm: float = 1.0) -> float:
    """NBR 5.4.2.3 a): C_b = 12,5 M_max R_m/(2,5 M_max + 3 M_A + 4 M_B + 3 M_C) (valores em módulo)."""
    M_max, M_A, M_B, M_C = map(abs, (M_max, M_A, M_B, M_C))
    return 12.5 * M_max * Rm / (2.5 * M_max + 3 * M_A + 4 * M_B + 3 * M_C)


# ---------------------------------------------------------------------------------------------
# AMPLIFICAÇÃO (B1) E INTERAÇÃO
# ---------------------------------------------------------------------------------------------
def coef_Cm(M1: float = 0.0, M2: float = 0.0, forcas_transversais: bool = False) -> float:
    """C_m = 0,60 − 0,40 M1/M2 (M1/M2 > 0 em curvatura reversa); 1,0 com forças transversais (Projeto C.2.2)."""
    if forcas_transversais or M2 == 0:
        return 1.0
    return 0.60 - 0.40 * (M1 / M2)


def coef_B1(
    N_Sd1: float, I: float, L: float, Cm: float, E: float = E_ACO, tracao: bool = False
) -> float:
    """B1 = C_m/(1 − N_Sd1/N_e) ≥ 1,0, N_e com o COMPRIMENTO REAL da barra no plano de flexão (K = 1).
    N_Sd1 em kN; I em mm⁴; L em mm. Tração → B1 = 1."""
    if tracao:
        return 1.0
    Ne = PI2 * E * I / L**2 / 1000
    if N_Sd1 >= Ne:
        raise ValueError("N_Sd1 ≥ N_e: barra instável no plano de flexão.")
    return max(1.0, Cm / (1 - N_Sd1 / Ne))


def interacao_NM(
    N_Sd: float,
    N_Rd: float,
    Mx_Sd: float,
    Mx_Rd: float,
    My_Sd: float = 0.0,
    My_Rd: float = math.inf,
) -> float:
    """NBR 5.5.1.2 / AISC H1-1 — UMA equação com os DOIS eixos (M_x e M_y já amplificados por B1/B2)."""
    n = abs(N_Sd) / N_Rd
    m = abs(Mx_Sd) / Mx_Rd + (abs(My_Sd) / My_Rd if My_Rd not in (0, math.inf) else 0.0)
    return n + 8 / 9 * m if n >= 0.2 else n / 2 + m


def momento_mao_francesa(H: float, braco: float) -> float:
    """M = H × braço (kN × mm → kN·m). Some no eixo que a mão-francesa flete."""
    return H * braco / 1000


def combinacao_ultima(
    permanentes: Sequence[tuple[float, float]],
    variavel_principal: tuple[float, float] | None = None,
    variaveis_secundarias: Sequence[tuple[float, float, float]] = (),
) -> float:
    """F_d = Σ γ_g G + γ_q1 Q1 + Σ γ_qj ψ0j Qj. Entradas: [(valor, γ)], (valor, γ), [(valor, γ, ψ0)]."""
    F = sum(v * g for v, g in permanentes)
    if variavel_principal:
        F += variavel_principal[0] * variavel_principal[1]
    F += sum(v * g * p for v, g, p in variaveis_secundarias)
    return F


# ---------------------------------------------------------------------------------------------
# CRITÉRIO ANGLO AA-BR-DPST-DR-0001
# ---------------------------------------------------------------------------------------------
ESPESSURA_MIN_ANGLO: dict[str, float] = {  # item 8.8 (mm)
    "perfil_soldado": 4.75,
    "perfil_laminado_H_W": 4.80,
    "perfil_laminado_L_U": 4.80,
    "chapa_ligacao_enrijecedor": 8.00,
    "cantoneira": 4.75,
    "placa_base": 16.0,
}


def criterio_anglo(
    esbeltez: float, comprimida: bool = True, espessuras: dict[str, float] | None = None
) -> list[Verificacao]:
    """8.3: λ_c ≤ 200 (compressão), λ_t ≤ 300 (tração, exceto barras redondas pré-tensionadas).
    8.8: espessuras mínimas. espessuras = {categoria: espessura_mm}."""
    lim = 200 if comprimida else 300
    out = [
        Verificacao(
            f"Esbeltez limite ({'compressão' if comprimida else 'tração'})",
            esbeltez,
            lim,
            "—",
            "Anglo 8.3; NBR 5.3.7 (recomendação)" if comprimida else "Anglo 8.3; NBR 5.2.8",
            "max(K L / r)",
            tipo="limite",
        )
    ]
    for cat, t in (espessuras or {}).items():
        tmin = ESPESSURA_MIN_ANGLO[cat]
        out.append(
            Verificacao(
                f"Espessura mínima — {cat}",
                None,
                None,
                "mm",
                "Anglo 8.8",
                f"t = {t} ≥ {tmin}",
                status="OK" if t >= tmin - 1e-9 else "NÃO OK",
                tipo="limite",
            )
        )
    return out


# ---------------------------------------------------------------------------------------------
# VERIFICAÇÃO COMPLETA DE UMA BARRA (os dois eixos ao mesmo tempo)
# ---------------------------------------------------------------------------------------------
def verificar_barra(
    sec: Secao,
    fy: float,
    KxLx: float,
    KyLy: float,
    N_Sd: float,
    KzLz: float | None = None,
    Mx_Sd: float = 0.0,
    My_Sd: float = 0.0,
    Lb: float | None = None,
    Cb: float = 1.0,
    norma: str = "NBR8800_2008",
    espessuras_anglo: dict[str, float] | None = None,
) -> dict[str, Any]:
    """N_Sd (kN, compressão +), M_Sd (kN·m) JÁ amplificados (B1/B2). Devolve verificações e resumo.

    Caminho do módulo de referência, mantido para os testes de aceite. O app usa
    :func:`core.column_buckling.verificar_coluna`, que difere em dois padrões: L_b = L_y (aqui,
    K_y·L_y) e B1 calculado dentro da própria verificação."""
    c = resist_compressao(sec, fy, KxLx, KyLy, KzLz, norma)
    v = [
        Verificacao(
            "Compressão — todos os modos",
            N_Sd,
            c["Nc_Rd"],
            "kN",
            "NBR 5.3 / AISC E",
            f"modo: {c['modo']}; λ0 = {c['lambda0']:.3f}; χ = {c['chi']:.3f}; Q = {c['Q']:.3f}",
        )
    ]
    Mrx = Mry = None
    if Mx_Sd:
        Mrx = momento_resistente(sec, fy, "x", Lb if Lb is not None else KyLy, Cb, norma)
        v.append(
            Verificacao(
                "Flexão em x", abs(Mx_Sd), Mrx["MRd"], "kN·m", "NBR 5.4.2 / AISC F", Mrx["governa"]
            )
        )
    if My_Sd:
        Mry = momento_resistente(sec, fy, "y", 0.0, 1.0, norma)
        v.append(
            Verificacao(
                "Flexão em y", abs(My_Sd), Mry["MRd"], "kN·m", "NBR 5.4.2 / AISC F", Mry["governa"]
            )
        )
    if Mx_Sd or My_Sd:
        val = interacao_NM(
            N_Sd,
            c["Nc_Rd"],
            Mx_Sd,
            Mrx["MRd"] if Mrx else math.inf,
            My_Sd,
            Mry["MRd"] if Mry else math.inf,
        )
        v.append(
            Verificacao(
                "Interação N + Mx + My (uma equação)", val, 1.0, "—", "NBR 5.5.1.2 / AISC H1-1"
            )
        )
    v += criterio_anglo(c["esbeltez"], True, espessuras_anglo)
    pior = max(
        (x for x in v if x.aproveitamento is not None and x.tipo == "resistencia"),
        key=lambda x: x.aproveitamento or 0.0,
    )
    return dict(
        verificacoes=v,
        compressao=c,
        governa=pior.nome,
        aproveitamento=pior.aproveitamento,
        atende=all(x.status != "NÃO OK" for x in v),
    )
