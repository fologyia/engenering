"""Verificação de barras de aço pela ABNT NBR 8800:2008.

Este módulo implementa os estados-limites últimos de barras prismáticas com
as equações **da norma**, e não um pré-dimensionamento genérico com φ:

* tração (5.2): escoamento da seção bruta e ruptura da seção líquida;
* compressão (5.3): ``N_c,Rd = χ·Q·A_g·f_y/γ_a1`` com ``λ_0`` e a curva
  única de ``χ`` (5.3.3), forças de flambagem elástica do Anexo E — por
  flexão, torção e flexo-torção — e o fator ``Q`` de flambagem local do
  Anexo F calculado das esbeltezes das paredes;
* flexão (5.4.2 + Anexo G): ``M_Rd`` como o menor entre FLT, FLM e FLA,
  com ``M_pl``, ``M_r``, ``M_cr`` e os limites ``λ_p``/``λ_r`` explícitos;
* cisalhamento (5.4.3): ``V_Rd`` a partir de ``V_pl`` e da esbeltez da alma;
* interação força axial + momentos (5.5.1.2);
* limites de esbeltez (5.3.4.1: ``KL/r ≤ 200``; 5.2.8: ``L/r ≤ 300``).

Coeficientes de ponderação da resistência (Tabela 3): ``γ_a1 = 1,10``
(escoamento, flambagem, instabilidade) e ``γ_a2 = 1,35`` (ruptura). Os
esforços solicitantes de cálculo já devem vir majorados pelas combinações
(NBR 8681 / NBR 8800 4.7); ver :mod:`core.load_combinations`.

Cada resultado guarda os valores intermediários (esbeltezes, limites,
momentos ``M_pl``/``M_r``/``M_cr``, regime governante) para o memorial poder
mostrar a ordem de substituição, e uma lista de **avisos** para o que a
norma cobre mas este módulo não calcula (viga esbelta do Anexo H, tubos
circulares ao cisalhamento, perfis fora das famílias tratadas).

Unidades: N, mm, MPa e N·mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.steel_sections import (
    PerfilAco,
    centro_de_cisalhamento_do_perfil,
    constante_de_empenamento_estimada,
    e_tubo_circular,
    e_tubo_retangular,
    familia_do_perfil,
)

GAMMA_A1 = 1.10  # escoamento, flambagem e instabilidade (Tabela 3)
GAMMA_A2 = 1.35  # ruptura (Tabela 3)
ESBELTEZ_MAXIMA_COMPRESSAO = 200.0  # 5.3.4.1
ESBELTEZ_MAXIMA_TRACAO = 300.0  # 5.2.8

_FAMILIAS_I = frozenset({"i", "w", "hp", "hea", "heb", "hem", "ipe", "ipn"})
_FAMILIAS_U = frozenset({"u", "c", "upn"})


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElementoDePlaca:
    """Uma parede da seção com a esbeltez ``b/t`` e os limites que a classificam."""

    nome: str
    tipo: str  # "AL" (não enrijecido) ou "AA" (enrijecido)
    razao: float
    limite_r: float
    grupo: str
    fator_q: float = 1.0
    largura_efetiva_mm: float | None = None


@dataclass(frozen=True)
class ResultadoTracaoNBR:
    resistencia_escoamento_N: float
    resistencia_ruptura_N: float
    resistencia_N: float
    modo_governante: str
    utilizacao: float
    esbeltez: float
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoCompressaoNBR:
    esbeltez_x: float
    esbeltez_y: float
    ne_x_N: float
    ne_y_N: float
    ne_z_N: float | None
    ne_acoplada_N: float | None
    ne_N: float
    modo_flambagem: str
    fator_q: float
    elementos: tuple[ElementoDePlaca, ...]
    lambda_0: float
    chi: float
    resistencia_N: float
    utilizacao: float
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class EstadoLimiteFlexao:
    """Um dos modos de flexão (FLT, FLM ou FLA) com os seus parâmetros."""

    nome: str
    esbeltez: float
    lambda_p: float
    lambda_r: float
    momento_pl_Nmm: float
    momento_r_Nmm: float
    momento_cr_Nmm: float | None
    resistencia_Nmm: float
    regime: str


@dataclass(frozen=True)
class ResultadoFlexaoNBR:
    eixo: str
    momento_pl_Nmm: float
    modos: tuple[EstadoLimiteFlexao, ...]
    modo_governante: str
    resistencia_Nmm: float
    utilizacao: float
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoCisalhamentoNBR:
    esbeltez_alma: float
    lambda_p: float
    lambda_r: float
    kv: float
    area_cisalhamento_mm2: float
    vpl_N: float
    resistencia_N: float
    regime: str
    utilizacao: float
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoInteracaoNBR:
    razao_axial: float
    razao_momento_x: float
    razao_momento_y: float
    indice: float
    expressao: str
    atende: bool


@dataclass(frozen=True)
class VerificacaoBarraNBR:
    """Conjunto completo de uma barra: o pior índice governa."""

    compressao: ResultadoCompressaoNBR | None
    tracao: ResultadoTracaoNBR | None
    flexao_x: ResultadoFlexaoNBR
    flexao_y: ResultadoFlexaoNBR | None
    cisalhamento: ResultadoCisalhamentoNBR
    interacao: ResultadoInteracaoNBR
    utilizacao_governante: float
    modo_governante: str
    avisos: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} não pode ser negativo.")
    return valor


def _utilizacao(solicitante: float, resistencia: float) -> float:
    return solicitante / resistencia if resistencia > 0 else math.inf


def _dimensoes(perfil: PerfilAco) -> tuple[float, float, float, float]:
    return (
        _positivo("altura_mm", perfil.altura_mm),
        _positivo("largura_mm", perfil.largura_mm),
        _positivo("espessura_alma_mm", perfil.espessura_alma_mm),
        _positivo("espessura_mesa_mm", perfil.espessura_mesa_mm),
    )


def _kc(perfil: PerfilAco) -> float:
    """``k_c = 4/√(h/t_w)``, entre 0,35 e 0,76 (perfis soldados)."""
    h, _, tw, tf = _dimensoes(perfil)
    return min(0.76, max(0.35, 4.0 / math.sqrt((h - 2.0 * tf) / tw)))


# ---------------------------------------------------------------------------
# Anexo F — flambagem local de barras comprimidas (fator Q)
# ---------------------------------------------------------------------------


def _qs_grupo(razao: float, fy: float, e: float, grupo: str, kc: float = 1.0) -> float:
    """``Q_s`` de um elemento não enrijecido (AL), F.2, por grupo da Tabela F.1."""
    raiz = math.sqrt(e / fy)
    if grupo == "3":  # abas de cantoneiras
        if razao <= 0.45 * raiz:
            return 1.0
        if razao <= 0.91 * raiz:
            return 1.340 - 0.76 * razao / raiz
        return 0.53 * e / (fy * razao**2)
    if grupo == "4":  # mesas de I, H, T, U laminados
        if razao <= 0.56 * raiz:
            return 1.0
        if razao <= 1.03 * raiz:
            return 1.415 - 0.74 * razao / raiz
        return 0.69 * e / (fy * razao**2)
    if grupo == "5":  # mesas de I e H soldados
        raiz_kc = math.sqrt(kc * e / fy)
        if razao <= 0.64 * raiz_kc:
            return 1.0
        if razao <= 1.17 * raiz_kc:
            return 1.415 - 0.65 * razao / raiz_kc
        return 0.90 * e * kc / (fy * razao**2)
    if grupo == "6":  # almas (talões) de seções T
        if razao <= 0.75 * raiz:
            return 1.0
        if razao <= 1.03 * raiz:
            return 1.908 - 1.22 * razao / raiz
        return 0.69 * e / (fy * razao**2)
    raise ValueError(f"Grupo de elemento AL desconhecido: {grupo!r}.")


def _largura_efetiva(b: float, t: float, sigma: float, e: float, ca: float) -> float:
    """``b_ef = 1,92·t·√(E/σ)·[1 − (c_a/(b/t))·√(E/σ)] ≤ b`` (F.3.2)."""
    razao = b / t
    raiz = math.sqrt(e / sigma)
    b_ef = 1.92 * t * raiz * (1.0 - (ca / razao) * raiz)
    return min(b, max(0.0, b_ef))


def _chi_de(lambda_0: float) -> float:
    """Curva única de flambagem (5.3.3.1)."""
    if lambda_0 <= 1.5:
        return 0.658 ** (lambda_0**2)
    return 0.877 / lambda_0**2


def fator_q(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    *,
    soldado: bool = False,
    chi_para_sigma: float = 1.0,
) -> tuple[float, tuple[ElementoDePlaca, ...], tuple[str, ...]]:
    """``Q = Q_s·Q_a`` do Anexo F, com a classificação de cada parede.

    ``chi_para_sigma`` é o ``χ`` usado na tensão ``σ = χ·f_y`` das larguras
    efetivas dos elementos enrijecidos (F.3.2, obtido com Q = 1); com o
    valor padrão 1,0 a norma permite o resultado conservador ``σ = f_y``.
    """
    fy = _positivo("fy_MPa", fy_MPa)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    chi = min(1.0, max(0.0, float(chi_para_sigma))) or 1.0
    sigma = chi * fy
    raiz = math.sqrt(e / fy)
    avisos: list[str] = []
    elementos: list[ElementoDePlaca] = []
    familia = familia_do_perfil(perfil)
    area = _positivo("area_mm2", perfil.area_mm2)

    if e_tubo_circular(perfil):
        # F.4: seção tubular circular.
        d, _, t, _ = _dimensoes(perfil)
        razao = d / t
        limite = 0.11 * e / fy
        if razao <= limite:
            q = 1.0
        elif razao <= 0.45 * e / fy:
            q = 0.038 * e / (fy * razao) + 2.0 / 3.0
        else:
            q = 0.038 * e / (fy * razao) + 2.0 / 3.0
            avisos.append(
                f"D/t = {razao:.1f} supera 0,45·E/f_y = {0.45 * e / fy:.1f}: fora do campo "
                "de aplicação do Anexo F (F.4); o Q calculado não é válido."
            )
        elementos.append(ElementoDePlaca("parede do tubo (D/t)", "AA", razao, limite, "F.4", q))
        return q, tuple(elementos), tuple(avisos)

    h, b, tw, tf = _dimensoes(perfil)
    qs = 1.0
    area_ineficaz = 0.0

    if e_tubo_retangular(perfil):
        # Grupo 1: paredes enrijecidas de tubos retangulares (c_a = 0,38).
        t = min(tw, tf)
        limite = 1.40 * raiz
        for nome, largura in (
            ("parede maior (b/t)", max(h, b) - 2.0 * t),
            ("parede menor (b/t)", min(h, b) - 2.0 * t),
        ):
            b_ef = _largura_efetiva(largura, t, sigma, e, 0.38)
            razao = largura / t
            elementos.append(ElementoDePlaca(nome, "AA", razao, limite, "1", 1.0, b_ef))
            if razao > limite:
                area_ineficaz += 2.0 * (largura - b_ef) * t
    elif familia in _FAMILIAS_I or familia in _FAMILIAS_U:
        grupo_mesa = "5" if soldado and familia in _FAMILIAS_I else "4"
        kc = _kc(perfil) if grupo_mesa == "5" else 1.0
        razao_mesa = (b / 2.0) / tf if familia in _FAMILIAS_I else b / tf
        limite_mesa = 0.64 * math.sqrt(kc * e / fy) if grupo_mesa == "5" else 0.56 * raiz
        q_mesa = _qs_grupo(razao_mesa, fy, e, grupo_mesa, kc)
        elementos.append(ElementoDePlaca("mesa", "AL", razao_mesa, limite_mesa, grupo_mesa, q_mesa))
        qs = q_mesa
        # Grupo 2: alma enrijecida (c_a = 0,34).
        hw = h - 2.0 * tf
        razao_alma = hw / tw
        limite_alma = 1.49 * raiz
        b_ef = _largura_efetiva(hw, tw, sigma, e, 0.34)
        elementos.append(ElementoDePlaca("alma", "AA", razao_alma, limite_alma, "2", 1.0, b_ef))
        if razao_alma > limite_alma:
            area_ineficaz += (hw - b_ef) * tw
    elif familia == "t":
        razao_mesa = (b / 2.0) / tf
        q_mesa = _qs_grupo(razao_mesa, fy, e, "4")
        elementos.append(ElementoDePlaca("mesa", "AL", razao_mesa, 0.56 * raiz, "4", q_mesa))
        razao_talao = h / tw
        q_talao = _qs_grupo(razao_talao, fy, e, "6")
        elementos.append(
            ElementoDePlaca("talão (alma do T)", "AL", razao_talao, 0.75 * raiz, "6", q_talao)
        )
        # Dois elementos AL: vale o menor Q_s (F.2.1).
        qs = min(q_mesa, q_talao)
    elif familia == "barra" or "barra" in str(perfil.familia).casefold():
        return 1.0, (), ()
    else:
        avisos.append(
            f"Família {perfil.familia!r} sem classificação de paredes no Anexo F: "
            "Q adotado igual a 1,0 — confira a flambagem local à parte."
        )
        return 1.0, (), tuple(avisos)

    qa = (area - area_ineficaz) / area
    return qs * qa, tuple(elementos), tuple(avisos)


# ---------------------------------------------------------------------------
# 5.2 — tração
# ---------------------------------------------------------------------------


def verificar_tracao(
    perfil: PerfilAco,
    fy_MPa: float,
    fu_MPa: float,
    forca_solicitante_N: float,
    *,
    area_liquida_mm2: float | None = None,
    coeficiente_ct: float = 1.0,
    comprimento_mm: float | None = None,
) -> ResultadoTracaoNBR:
    """``N_t,Rd = min(A_g·f_y/γ_a1, A_e·f_u/γ_a2)``, com ``A_e = C_t·A_n``."""
    fy = _positivo("fy_MPa", fy_MPa)
    fu = _positivo("fu_MPa", fu_MPa)
    if fu < fy:
        raise ValueError("f_u deve ser maior ou igual a f_y.")
    solicitante = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    area = _positivo("area_mm2", perfil.area_mm2)
    an = area if area_liquida_mm2 is None else _positivo("area_liquida_mm2", area_liquida_mm2)
    if an > area * (1.0 + 1e-9):
        raise ValueError("A área líquida não pode superar a área bruta.")
    ct = float(coeficiente_ct)
    if not 0.0 < ct <= 1.0:
        raise ValueError("C_t deve estar em (0, 1].")
    escoamento = area * fy / GAMMA_A1
    ruptura = ct * an * fu / GAMMA_A2
    if escoamento <= ruptura:
        resistencia, modo = escoamento, "Escoamento da seção bruta (5.2.2 a)"
    else:
        resistencia, modo = ruptura, "Ruptura da seção líquida efetiva (5.2.2 b)"
    avisos: list[str] = []
    esbeltez = 0.0
    if comprimento_mm:
        raio_minimo = min(perfil.rx_mm, perfil.ry_mm)
        esbeltez = _positivo("comprimento_mm", comprimento_mm) / raio_minimo
        if esbeltez > ESBELTEZ_MAXIMA_TRACAO:
            avisos.append(
                f"L/r = {esbeltez:.0f} supera o limite de {ESBELTEZ_MAXIMA_TRACAO:.0f} "
                "para barras tracionadas (5.2.8)."
            )
    return ResultadoTracaoNBR(
        resistencia_escoamento_N=escoamento,
        resistencia_ruptura_N=ruptura,
        resistencia_N=resistencia,
        modo_governante=modo,
        utilizacao=_utilizacao(solicitante, resistencia),
        esbeltez=esbeltez,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# 5.3 + Anexos E e F — compressão
# ---------------------------------------------------------------------------


def forcas_de_flambagem_elastica(
    perfil: PerfilAco,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    comprimento_efetivo_x_mm: float,
    comprimento_efetivo_y_mm: float,
    comprimento_efetivo_z_mm: float | None = None,
) -> tuple[float, float, float | None, float | None, float, str]:
    """``(N_ex, N_ey, N_ez, N_e,acoplada, N_e, modo)`` pelo Anexo E.

    Seções com dois eixos de simetria: ``N_e = min(N_ex, N_ey, N_ez)`` (E.1.1).
    Monossimétricas (U/C com eixo x de simetria; T com eixo y): a flexão em
    torno do eixo de simetria se acopla à torção (E.1.2) e o modo puro é o
    outro. ``K_z·L_z`` é o comprimento de flambagem por torção; sem ele,
    usa-se o maior dos dois de flexão.
    """
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    g = _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
    lx = _positivo("comprimento_efetivo_x_mm", comprimento_efetivo_x_mm)
    ly = _positivo("comprimento_efetivo_y_mm", comprimento_efetivo_y_mm)
    lz = (
        _positivo("comprimento_efetivo_z_mm", comprimento_efetivo_z_mm)
        if comprimento_efetivo_z_mm
        else max(lx, ly)
    )
    nex = math.pi**2 * e * perfil.ix_mm4 / lx**2
    ney = math.pi**2 * e * perfil.iy_mm4 / ly**2
    familia = familia_do_perfil(perfil)
    if "barra" in str(perfil.familia).casefold() or e_tubo_circular(perfil):
        # Maciças e tubos circulares: torção não governa (J alto, Cw ≈ 0).
        return nex, ney, None, None, min(nex, ney), ("x" if nex <= ney else "y")
    x0, y0 = centro_de_cisalhamento_do_perfil(perfil)
    cw = constante_de_empenamento_estimada(perfil)
    r0_quadrado = perfil.rx_mm**2 + perfil.ry_mm**2 + x0**2 + y0**2
    nez = (math.pi**2 * e * cw / lz**2 + g * perfil.j_mm4) / r0_quadrado
    if familia in _FAMILIAS_U and abs(x0) > 0:
        # Eixo x de simetria: flexão em torno de x acopla com a torção (E.1.2).
        fator = 1.0 - (x0**2) / r0_quadrado
        soma = nex + nez
        acoplada = (soma / (2.0 * fator)) * (
            1.0 - math.sqrt(max(0.0, 1.0 - 4.0 * nex * nez * fator / soma**2))
        )
        candidatos = {"y": ney, "xz (flexo-torção)": acoplada}
    elif familia == "t" and abs(y0) > 0:
        # Eixo y de simetria: flexão em torno de y acopla com a torção.
        fator = 1.0 - (y0**2) / r0_quadrado
        soma = ney + nez
        acoplada = (soma / (2.0 * fator)) * (
            1.0 - math.sqrt(max(0.0, 1.0 - 4.0 * ney * nez * fator / soma**2))
        )
        candidatos = {"x": nex, "yz (flexo-torção)": acoplada}
    else:
        acoplada = None
        candidatos = {"x": nex, "y": ney, "z (torção)": nez}
    modo = min(candidatos, key=lambda chave: candidatos[chave])
    return nex, ney, nez, acoplada, candidatos[modo], modo


def verificar_compressao(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    comprimento_mm: float,
    kx: float,
    ky: float,
    forca_solicitante_N: float,
    *,
    kz: float | None = None,
    soldado: bool = False,
) -> ResultadoCompressaoNBR:
    """``N_c,Rd = χ·Q·A_g·f_y/γ_a1`` (5.3.2) com ``Q`` do Anexo F e ``N_e`` do Anexo E."""
    fy = _positivo("fy_MPa", fy_MPa)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    g = _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
    l = _positivo("comprimento_mm", comprimento_mm)
    kx = _positivo("kx", kx)
    ky = _positivo("ky", ky)
    solicitante = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    area = _positivo("area_mm2", perfil.area_mm2)
    lx, ly = kx * l, ky * l
    lz = _positivo("kz", kz) * l if kz else None

    nex, ney, nez, acoplada, ne, modo = forcas_de_flambagem_elastica(perfil, e, g, lx, ly, lz)
    esbeltez_x = lx / perfil.rx_mm
    esbeltez_y = ly / perfil.ry_mm
    avisos: list[str] = []
    if max(esbeltez_x, esbeltez_y) > ESBELTEZ_MAXIMA_COMPRESSAO:
        avisos.append(
            f"KL/r = {max(esbeltez_x, esbeltez_y):.0f} supera o limite de "
            f"{ESBELTEZ_MAXIMA_COMPRESSAO:.0f} para barras comprimidas (5.3.4.1): "
            "a barra não atende independentemente da resistência calculada."
        )

    # σ das larguras efetivas: χ obtido com Q = 1 (F.3.2).
    chi_q1 = _chi_de(math.sqrt(area * fy / ne))
    q, elementos, avisos_q = fator_q(perfil, fy, e, soldado=soldado, chi_para_sigma=chi_q1)
    avisos.extend(avisos_q)
    lambda_0 = math.sqrt(q * area * fy / ne)
    chi = _chi_de(lambda_0)
    resistencia = chi * q * area * fy / GAMMA_A1
    return ResultadoCompressaoNBR(
        esbeltez_x=esbeltez_x,
        esbeltez_y=esbeltez_y,
        ne_x_N=nex,
        ne_y_N=ney,
        ne_z_N=nez,
        ne_acoplada_N=acoplada,
        ne_N=ne,
        modo_flambagem=modo,
        fator_q=q,
        elementos=elementos,
        lambda_0=lambda_0,
        chi=chi,
        resistencia_N=resistencia,
        utilizacao=_utilizacao(solicitante, resistencia),
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# 5.4.2 + Anexo G — flexão
# ---------------------------------------------------------------------------


def _modo(
    nome: str,
    esbeltez: float,
    lambda_p: float,
    lambda_r: float,
    mpl: float,
    mr: float,
    mcr: float | None,
    cb: float = 1.0,
) -> EstadoLimiteFlexao:
    """Regra geral do Anexo G: plástico, inelástico (interpolação) ou elástico."""
    teto = mpl / GAMMA_A1
    if esbeltez <= lambda_p:
        resistencia, regime = teto, "plástico (λ ≤ λp)"
    elif esbeltez <= lambda_r:
        interpolado = (
            cb * (mpl - (mpl - mr) * (esbeltez - lambda_p) / (lambda_r - lambda_p)) / GAMMA_A1
        )
        resistencia, regime = min(teto, interpolado), "inelástico (λp < λ ≤ λr)"
    else:
        if mcr is None:
            raise ValueError(f"{nome}: λ > λr sem M_cr definido.")
        resistencia, regime = min(teto, mcr / GAMMA_A1), "elástico (λ > λr)"
    return EstadoLimiteFlexao(nome, esbeltez, lambda_p, lambda_r, mpl, mr, mcr, resistencia, regime)


def verificar_flexao(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    momento_solicitante_Nmm: float,
    *,
    eixo: str = "x",
    comprimento_destravado_mm: float | None = None,
    cb: float = 1.0,
    soldado: bool = False,
) -> ResultadoFlexaoNBR:
    """``M_Rd`` pelo Anexo G: menor entre FLT, FLM e FLA, limitado a ``1,5·W·f_y/γ_a1``.

    Cobre I/H com dois eixos de simetria e U fletidos em torno de x (G.2),
    I/H fletidos em torno de y (G.5: só FLM), tubos retangulares (G.3) e
    circulares (G.4). T e barras maciças recebem só o limite de escoamento,
    com aviso.
    """
    fy = _positivo("fy_MPa", fy_MPa)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    g = _positivo("modulo_cisalhamento_MPa", modulo_cisalhamento_MPa)
    momento = _nao_negativo("momento_solicitante_Nmm", momento_solicitante_Nmm)
    cb = _positivo("cb", cb)
    eixo = str(eixo).strip().lower()
    if eixo not in {"x", "y"}:
        raise ValueError("eixo deve ser 'x' ou 'y'.")
    familia = familia_do_perfil(perfil)
    avisos: list[str] = []
    modos: list[EstadoLimiteFlexao] = []
    sigma_r = 0.30 * fy  # tensão residual (G.2.1)
    raiz = math.sqrt(e / fy)

    if eixo == "x":
        w, z, inercia_fraca, raio_fraco = perfil.sx_mm3, perfil.zx_mm3, perfil.iy_mm4, perfil.ry_mm
    else:
        w, z, inercia_fraca, raio_fraco = perfil.sy_mm3, perfil.zy_mm3, perfil.ix_mm4, perfil.rx_mm
    w = _positivo("modulo_elastico", w)
    z = _positivo("modulo_plastico", z) if z > 0 else w
    mpl = min(z * fy, 1.5 * w * fy)
    teto_norma = 1.5 * w * fy / GAMMA_A1

    if e_tubo_circular(perfil):
        d, _, t, _ = _dimensoes(perfil)
        esb = d / t
        mr = (0.021 * e / esb + fy) * w
        mcr = 0.33 * e * w / esb
        modos.append(
            _modo(
                "FLM/FLA (tubo circular, G.4)",
                esb,
                0.07 * e / fy,
                0.31 * e / fy,
                mpl,
                min(mr, mpl),
                mcr,
            )
        )
    elif e_tubo_retangular(perfil):
        h, b, tw, tf = _dimensoes(perfil)
        t = min(tw, tf)
        mesa = (b if eixo == "x" else h) - 2.0 * t
        alma = (h if eixo == "x" else b) - 2.0 * t
        modos.append(
            _modo(
                "FLM (G.3)",
                mesa / t,
                1.12 * raiz,
                1.40 * raiz,
                mpl,
                fy * w,
                None if mesa / t <= 1.40 * raiz else fy * w,
            )
        )
        modos.append(
            _modo(
                "FLA (G.3)",
                alma / t,
                2.42 * raiz,
                5.70 * raiz,
                mpl,
                fy * w,
                None if alma / t <= 5.70 * raiz else fy * w,
            )
        )
        if mesa / t > 1.40 * raiz:
            avisos.append(
                "Mesa do tubo com λ > λr: a norma exige largura efetiva (G.3); M_r foi tomado com W bruto — conservador só se W_ef ≈ W."
            )
    elif familia in _FAMILIAS_I or familia in _FAMILIAS_U:
        h, b, tw, tf = _dimensoes(perfil)
        hw = h - 2.0 * tf
        razao_mesa = (b / 2.0) / tf if familia in _FAMILIAS_I else b / tf
        if soldado and familia in _FAMILIAS_I:
            kc = _kc(perfil)
            lambda_r_flm = 0.95 * math.sqrt(e / ((fy - sigma_r) / kc))
            mcr_flm = 0.90 * e * kc * w / razao_mesa**2
        else:
            lambda_r_flm = 0.83 * math.sqrt(e / (fy - sigma_r))
            mcr_flm = 0.69 * e * w / razao_mesa**2
        modos.append(
            _modo(
                "FLM (G.2)", razao_mesa, 0.38 * raiz, lambda_r_flm, mpl, (fy - sigma_r) * w, mcr_flm
            )
        )
        if eixo == "x":
            razao_alma = hw / tw
            lambda_r_fla = 5.70 * raiz
            if razao_alma > lambda_r_fla:
                avisos.append(
                    f"Alma com h/t_w = {razao_alma:.1f} > λr = {lambda_r_fla:.1f}: viga de alma "
                    "esbelta, fora do Anexo G — a resistência exige o Anexo H, não calculado aqui."
                )
            modos.append(
                _modo(
                    "FLA (G.2)",
                    razao_alma,
                    3.76 * raiz,
                    lambda_r_fla,
                    mpl,
                    fy * w,
                    fy * w if razao_alma > lambda_r_fla else None,
                )
            )
            # FLT — flambagem lateral com torção.
            if comprimento_destravado_mm is None:
                avisos.append("FLT não verificada: informe o comprimento destravado L_b.")
            else:
                lb = _positivo("comprimento_destravado_mm", comprimento_destravado_mm)
                cw = constante_de_empenamento_estimada(perfil)
                j = _positivo("j_mm4", perfil.j_mm4)
                lambda_flt = lb / raio_fraco
                lambda_p = 1.76 * raiz
                beta1 = (fy - sigma_r) * w / (e * j)
                lambda_r = (
                    1.38 * math.sqrt(inercia_fraca * j) / (raio_fraco * j * beta1)
                ) * math.sqrt(1.0 + math.sqrt(1.0 + 27.0 * cw * beta1**2 / inercia_fraca))
                mcr = (
                    (cb * math.pi**2 * e * inercia_fraca / lb**2)
                    * math.sqrt((cw / inercia_fraca) * (1.0 + 0.039 * j * lb**2 / cw))
                    if cw > 0
                    else (cb * math.pi / lb) * math.sqrt(e * inercia_fraca * g * j)
                )
                cb_usado = cb
                if familia in _FAMILIAS_U and cb != 1.0:
                    # G.2 nota: para seções U, C_b deve ser tomado igual a 1,0.
                    avisos.append("Seção U: C_b tomado igual a 1,0 na FLT, conforme o Anexo G.")
                    cb_usado = 1.0
                    mcr *= 1.0 / cb
                modos.append(
                    _modo(
                        "FLT (G.2)",
                        lambda_flt,
                        lambda_p,
                        lambda_r,
                        mpl,
                        (fy - sigma_r) * w,
                        mcr,
                        cb_usado,
                    )
                )
    elif familia == "t":
        avisos.append(
            "Perfil T: o Anexo G (G.6) exige a verificação com o momento crítico próprio da "
            "seção T; aqui M_Rd é limitado ao escoamento da fibra extrema (W·f_y/γ_a1)."
        )
        modos.append(
            EstadoLimiteFlexao(
                "Escoamento (fibra extrema)",
                0.0,
                0.0,
                0.0,
                mpl,
                w * fy,
                None,
                w * fy / GAMMA_A1,
                "escoamento",
            )
        )
    else:
        modos.append(
            EstadoLimiteFlexao(
                "Plastificação total", 0.0, 0.0, 0.0, mpl, mpl, None, mpl / GAMMA_A1, "plástico"
            )
        )

    resistencia = min(teto_norma, min(modo.resistencia_Nmm for modo in modos))
    governante = min(modos, key=lambda modo: modo.resistencia_Nmm).nome
    if resistencia >= teto_norma * (1.0 - 1e-12):
        governante = "limite 1,5·W·f_y (5.4.2.2)"
    return ResultadoFlexaoNBR(
        eixo=eixo,
        momento_pl_Nmm=mpl,
        modos=tuple(modos),
        modo_governante=governante,
        resistencia_Nmm=resistencia,
        utilizacao=_utilizacao(momento, resistencia),
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# 5.4.3 — cisalhamento
# ---------------------------------------------------------------------------


def verificar_cisalhamento(
    perfil: PerfilAco,
    fy_MPa: float,
    modulo_elasticidade_MPa: float,
    cortante_solicitante_N: float,
    *,
    eixo: str = "x",
    distancia_enrijecedores_mm: float | None = None,
) -> ResultadoCisalhamentoNBR:
    """``V_Rd`` de 5.4.3.1: ``V_pl/γ_a1`` reduzido pela esbeltez da alma.

    ``eixo="x"`` é o cortante paralelo à alma (flexão em x); ``"y"`` é o
    cortante nas mesas (5.4.3.5: ``k_v = 1,2`` e ``A_w = 2·b_f·t_f``).
    """
    fy = _positivo("fy_MPa", fy_MPa)
    e = _positivo("modulo_elasticidade_MPa", modulo_elasticidade_MPa)
    cortante = _nao_negativo("cortante_solicitante_N", cortante_solicitante_N)
    familia = familia_do_perfil(perfil)
    avisos: list[str] = []
    if e_tubo_circular(perfil):
        # 5.4.3.6: tubos circulares — τ_cr depende de L/D; usa-se o piso 0,6·f_y·A_g/2.
        area_w = 0.5 * perfil.area_mm2
        vpl = 0.60 * fy * area_w
        avisos.append(
            "Tubo circular: V_Rd tomado como 0,6·f_y·(A_g/2)/γ_a1 (5.4.3.6, sem a redução por L/D)."
        )
        return ResultadoCisalhamentoNBR(
            0.0,
            0.0,
            0.0,
            0.0,
            area_w,
            vpl,
            vpl / GAMMA_A1,
            "plástico",
            _utilizacao(cortante, vpl / GAMMA_A1),
            tuple(avisos),
        )
    h, b, tw, tf = _dimensoes(perfil)
    if "barra" in str(perfil.familia).casefold():
        area_w = perfil.area_cisalhamento_mm2 or perfil.area_mm2
        vpl = 0.60 * fy * area_w
        return ResultadoCisalhamentoNBR(
            0.0,
            0.0,
            0.0,
            0.0,
            area_w,
            vpl,
            vpl / GAMMA_A1,
            "plástico",
            _utilizacao(cortante, vpl / GAMMA_A1),
            (),
        )
    if e_tubo_retangular(perfil):
        t = min(tw, tf)
        altura = h if eixo == "x" else b
        esbeltez = (altura - 2.0 * t) / t
        area_w = 2.0 * altura * t
        kv = 5.0
    elif eixo == "y":
        esbeltez = (b / 2.0) / tf if familia in _FAMILIAS_I else b / tf
        area_w = 2.0 * b * tf if familia != "t" else b * tf
        kv = 1.2
    else:
        esbeltez = (h - 2.0 * tf) / tw if familia != "t" else h / tw
        area_w = h * tw
        if distancia_enrijecedores_mm and 0 < distancia_enrijecedores_mm / (h - 2.0 * tf) <= 3.0:
            razao_a_h = distancia_enrijecedores_mm / (h - 2.0 * tf)
            kv = 5.0 + 5.0 / razao_a_h**2
        else:
            kv = 5.0
    lambda_p = 1.10 * math.sqrt(kv * e / fy)
    lambda_r = 1.37 * math.sqrt(kv * e / fy)
    vpl = 0.60 * fy * area_w
    if esbeltez <= lambda_p:
        resistencia, regime = vpl / GAMMA_A1, "plástico (λ ≤ λp)"
    elif esbeltez <= lambda_r:
        resistencia, regime = (lambda_p / esbeltez) * vpl / GAMMA_A1, "inelástico (λp < λ ≤ λr)"
    else:
        resistencia, regime = (
            1.24 * (lambda_p / esbeltez) ** 2 * vpl / GAMMA_A1,
            "elástico (λ > λr)",
        )
    return ResultadoCisalhamentoNBR(
        esbeltez_alma=esbeltez,
        lambda_p=lambda_p,
        lambda_r=lambda_r,
        kv=kv,
        area_cisalhamento_mm2=area_w,
        vpl_N=vpl,
        resistencia_N=resistencia,
        regime=regime,
        utilizacao=_utilizacao(cortante, resistencia),
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# 5.5.1.2 — interação
# ---------------------------------------------------------------------------


def verificar_interacao(
    forca_solicitante_N: float,
    resistencia_axial_N: float,
    momento_x_Nmm: float,
    resistencia_momento_x_Nmm: float,
    momento_y_Nmm: float = 0.0,
    resistencia_momento_y_Nmm: float | None = None,
) -> ResultadoInteracaoNBR:
    n = _nao_negativo("forca_solicitante_N", forca_solicitante_N)
    nr = _positivo("resistencia_axial_N", resistencia_axial_N)
    mx = _nao_negativo("momento_x_Nmm", momento_x_Nmm)
    mrx = _positivo("resistencia_momento_x_Nmm", resistencia_momento_x_Nmm)
    my = _nao_negativo("momento_y_Nmm", momento_y_Nmm)
    if my > 0 and not resistencia_momento_y_Nmm:
        raise ValueError("Informe a resistência à flexão em torno de y.")
    mry = (
        _positivo("resistencia_momento_y_Nmm", resistencia_momento_y_Nmm)
        if resistencia_momento_y_Nmm
        else 1.0
    )
    rn, rmx, rmy = n / nr, mx / mrx, my / mry
    if rn >= 0.2:
        indice = rn + (8.0 / 9.0) * (rmx + rmy)
        expressao = "N_Sd/N_Rd + 8/9·(M_x,Sd/M_x,Rd + M_y,Sd/M_y,Rd) ≤ 1,0"
    else:
        indice = rn / 2.0 + rmx + rmy
        expressao = "N_Sd/(2·N_Rd) + M_x,Sd/M_x,Rd + M_y,Sd/M_y,Rd ≤ 1,0"
    return ResultadoInteracaoNBR(rn, rmx, rmy, indice, expressao, indice <= 1.0)


# ---------------------------------------------------------------------------
# Verificação completa de uma barra
# ---------------------------------------------------------------------------


def verificar_barra(
    perfil: PerfilAco,
    *,
    fy_MPa: float,
    fu_MPa: float,
    modulo_elasticidade_MPa: float,
    modulo_cisalhamento_MPa: float,
    comprimento_mm: float,
    kx: float,
    ky: float,
    forca_axial_N: float,
    momento_x_Nmm: float = 0.0,
    momento_y_Nmm: float = 0.0,
    cortante_N: float = 0.0,
    comprimento_destravado_mm: float | None = None,
    cb: float = 1.0,
    kz: float | None = None,
    soldado: bool = False,
    area_liquida_mm2: float | None = None,
    coeficiente_ct: float = 1.0,
) -> VerificacaoBarraNBR:
    """Barra sob ``N`` (positivo = tração, negativo = compressão), ``M_x``, ``M_y`` e ``V``."""
    n = float(forca_axial_N)
    if not math.isfinite(n):
        raise ValueError("forca_axial_N deve ser finita.")
    avisos: list[str] = []
    compressao: ResultadoCompressaoNBR | None = None
    tracao: ResultadoTracaoNBR | None = None
    if n < 0:
        compressao = verificar_compressao(
            perfil,
            fy_MPa,
            modulo_elasticidade_MPa,
            modulo_cisalhamento_MPa,
            comprimento_mm,
            kx,
            ky,
            -n,
            kz=kz,
            soldado=soldado,
        )
        resistencia_axial = compressao.resistencia_N
        avisos.extend(compressao.avisos)
    else:
        tracao = verificar_tracao(
            perfil,
            fy_MPa,
            fu_MPa,
            n,
            area_liquida_mm2=area_liquida_mm2,
            coeficiente_ct=coeficiente_ct,
            comprimento_mm=comprimento_mm,
        )
        resistencia_axial = tracao.resistencia_N
        avisos.extend(tracao.avisos)
    flexao_x = verificar_flexao(
        perfil,
        fy_MPa,
        modulo_elasticidade_MPa,
        modulo_cisalhamento_MPa,
        abs(momento_x_Nmm),
        eixo="x",
        comprimento_destravado_mm=comprimento_destravado_mm,
        cb=cb,
        soldado=soldado,
    )
    avisos.extend(flexao_x.avisos)
    flexao_y: ResultadoFlexaoNBR | None = None
    if abs(momento_y_Nmm) > 0:
        flexao_y = verificar_flexao(
            perfil,
            fy_MPa,
            modulo_elasticidade_MPa,
            modulo_cisalhamento_MPa,
            abs(momento_y_Nmm),
            eixo="y",
            soldado=soldado,
        )
        avisos.extend(flexao_y.avisos)
    cisalhamento = verificar_cisalhamento(perfil, fy_MPa, modulo_elasticidade_MPa, abs(cortante_N))
    avisos.extend(cisalhamento.avisos)
    interacao = verificar_interacao(
        abs(n),
        resistencia_axial,
        abs(momento_x_Nmm),
        flexao_x.resistencia_Nmm,
        abs(momento_y_Nmm),
        flexao_y.resistencia_Nmm if flexao_y else None,
    )
    if compressao is not None:
        utilizacao_axial, rotulo_axial = compressao.utilizacao, "Compressão (5.3)"
    else:
        assert tracao is not None
        utilizacao_axial, rotulo_axial = tracao.utilizacao, "Tração (5.2)"
    candidatos = {
        rotulo_axial: utilizacao_axial,
        f"Flexão em x — {flexao_x.modo_governante}": flexao_x.utilizacao,
        "Cisalhamento (5.4.3)": cisalhamento.utilizacao,
        "Interação N + M (5.5.1.2)": interacao.indice,
    }
    if flexao_y:
        candidatos[f"Flexão em y — {flexao_y.modo_governante}"] = flexao_y.utilizacao
    if (
        compressao
        and max(compressao.esbeltez_x, compressao.esbeltez_y) > ESBELTEZ_MAXIMA_COMPRESSAO
    ):
        candidatos["Esbeltez KL/r > 200 (5.3.4.1)"] = math.inf
    governante = max(candidatos, key=lambda chave: candidatos[chave])
    return VerificacaoBarraNBR(
        compressao=compressao,
        tracao=tracao,
        flexao_x=flexao_x,
        flexao_y=flexao_y,
        cisalhamento=cisalhamento,
        interacao=interacao,
        utilizacao_governante=candidatos[governante],
        modo_governante=governante,
        avisos=tuple(dict.fromkeys(avisos)),
    )
