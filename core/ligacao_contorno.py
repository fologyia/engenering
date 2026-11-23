"""Perfil soldado em todo o contorno: W/HP/I, U ou cantoneira numa chapa (NBR 8800, 2025 e 2008).

A ponta do perfil encosta numa chapa (chapa de extremidade, chapa de base, chapa de topo, mesa de
outra peça) e um filete de pernas iguais corre por **todo o contorno** da seção: as faces externas,
as pontas das mesas (ou das abas) e as faces internas, descontado o raio de concordância — que o
catálogo não traz e é estimado na espessura da mesa (na da aba, na cantoneira); o trecho do raio
fica fora da conta (a favor da segurança).

**Método elástico** com os filetes como linhas (espessura unitária). Os esforços de cálculo são
dados no centro geométrico da seção do perfil e levados ao centro geométrico do grupo de solda
(no U e na cantoneira os dois não coincidem). Num ponto (x, y) do contorno, medido do centro do
grupo, a força por milímetro é

* normal à chapa (tração +): f_n = N/L + a·x + b·y, com a e b pela flexão oblíqua das linhas
  (∫f_n·y·ds = M_x, ∫f_n·x·ds = M_y, usando I_x = ∫y²ds, I_y = ∫x²ds e I_xy = ∫xy·ds — o
  produto de inércia não é nulo na cantoneira);
* no plano da chapa: f_vx = V_x/L − T·y/J e f_vy = V_y/L + T·x/J, J = I_x + I_y;

e a resultante √(f_n² + f_vx² + f_vy²) — máxima numa das pontas dos trechos, porque os campos são
lineares — fica abaixo da resistência do filete por mm, 0,60·f_w·(0,707·d_w)/γ_w2 (tabela das
soldas), sem o aumento pela direção (a favor da segurança). Com a ponta do perfil faceada e a
compressão passando por contato (AISC 360-22 J1.4 a), só a parte tracionada de f_n vai à solda.

Completam o metal-base do perfil (as duas faces de cada parede soldadas: normal pelo escoamento
f_y·t/γ_a1 e cortante pela 6.5.5), o metal-base da chapa ao cisalhamento (6.5.5) e os limites de
6.2.6 (perna mínima pela parte menos espessa, perna máxima nas pontas e comprimento mínimo do
filete, que é contínuo em volta da seção). Perna 0 = automática: a menor perna comercial que passa.

Convenções: x paralelo às mesas (no W e no U; na cantoneira, à aba horizontal), y paralelo à alma;
M_x positivo traciona o lado +y, M_y positivo traciona o lado +x, T positivo anti-horário visto de
fora da chapa (do lado do perfil). Unidades: mm, MPa, kN e kN·m. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from PIL import Image, ImageDraw

from core import cantoneiras as ct
from core import section_catalog as sc
from core import soldas as sd
from core.beam_charts import ImagemDiagrama, _fonte, figura_final
from core.desenho_girado import Tela as _Tela
from core.desenho_girado import cota_alinhada as _cota_alinhada
from core.desenho_girado import legenda as _legenda
from core.desenho_girado import rotulo as _rotulo
from core.ligacoes import (
    _BARRA,
    _CHAPA_AZUL,
    _COTA,
    _ESC,
    _FORCA,
    _LINHA,
    _SOLDA,
    _TEXTO,
    ACOS,
    ELETRODOS,
    LigacaoInvalida,
    ResultadoLigacao,
)
from core.verificacao import Verificacao

PERFIL_NO_CONTORNO = "perfil_no_contorno"

FORMA_I = "i_h"
FORMA_U = "u"
FORMA_L = "cantoneira"
FORMAS = {
    FORMA_I: "W, HP ou I (perfil I ou H)",
    FORMA_U: "U (canal laminado)",
    FORMA_L: "Cantoneira de abas iguais",
}
FAMILIAS_I = ("W (mesa larga)", "HP (perfil de estaca)", "I duplamente simétrico")
FAMILIAS_U = ("U (canal laminado)",)

#: Pernas de filete usuais (mm), para a perna automática.
PERNAS_COMERCIAIS: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0)  # fmt: skip
AISC_CONTATO = "AISC 360-22 J1.4 a)"

MESA = "mesa"
ALMA = "alma"
ABA = "aba"


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def perfis_da_forma(forma: str) -> list[str]:
    """Os perfis do catálogo que servem para a forma escolhida."""
    if forma == FORMA_L:
        return list(ct.CATALOGO_CANTONEIRAS)
    familias = FAMILIAS_I if forma == FORMA_I else FAMILIAS_U
    return [n for n, p in sc.listar_perfis().items() if p.familia in familias]


# =============================================================================================
# Entrada
# =============================================================================================
@dataclass(frozen=True)
class EntradaPerfilNoContorno:
    norma: str = sd.NBR_2025
    combinacao: str = sd.COMBINACAO_NORMAL
    forma: str = FORMA_I
    perfil: str = "W 250 x 32,7"
    aco_perfil: str = "ASTM A572 Gr 50"
    t_chapa_mm: float = 16.0
    aco_chapa: str = "ASTM A36"
    eletrodo: str = "E70"
    perna_mm: float = 0.0  # 0 = automática
    n_sd_kN: float = 80.0  # tração +
    vx_sd_kN: float = 0.0
    vy_sd_kN: float = 60.0
    mx_sd_kNm: float = 15.0
    my_sd_kNm: float = 0.0
    t_sd_kNm: float = 0.0
    contato: bool = False  # ponta faceada: a compressão passa por contato


# =============================================================================================
# Geometria do contorno
# =============================================================================================
@dataclass(frozen=True)
class Trecho:
    """Um filete reto do contorno, de (x1, y1) a (x2, y2), em mm a partir do centro do perfil."""

    nome: str
    x1: float
    y1: float
    x2: float
    y2: float
    elemento: str  # MESA, ALMA ou ABA: de qual parede do perfil é o metal-base
    espessura: float  # da parede (mm)

    @property
    def comprimento(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    def movido(self, dx: float, dy: float) -> Trecho:
        return replace(self, x1=self.x1 + dx, y1=self.y1 + dy, x2=self.x2 + dx, y2=self.y2 + dy)

    def pontas(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (self.x1, self.y1), (self.x2, self.y2)


@dataclass(frozen=True)
class Secao:
    """A seção do perfil: o contorno de solda, o polígono para o desenho e as medidas."""

    nome: str
    forma: str
    trechos: tuple[Trecho, ...]
    poligono: tuple[tuple[float, float], ...]
    altura: float  # d (no W e no U) ou b (na cantoneira)
    largura: float  # b_f (no W e no U) ou b (na cantoneira)
    t_mesa: float  # na cantoneira, a espessura da aba
    t_alma: float
    raio: float  # raio de concordância estimado


def _secao_i(nome: str, d: float, b_f: float, t_w: float, t_f: float) -> Secao:
    r = t_f  # raio de concordância estimado (o catálogo não traz)
    h, b = d / 2, b_f / 2
    trechos: list[Trecho] = []
    for s in (1.0, -1.0):
        y_ext, y_int = s * h, s * (h - t_f)
        trechos.append(Trecho("mesa, face externa", -b, y_ext, b, y_ext, MESA, t_f))
        for lado in (1.0, -1.0):
            trechos.append(Trecho("ponta da mesa", lado * b, y_int, lado * b, y_ext, MESA, t_f))
            inicio = t_w / 2 + r
            if b > inicio:
                trechos.append(
                    Trecho("mesa, face interna", lado * inicio, y_int, lado * b, y_int, MESA, t_f)
                )
    meio = h - t_f - r
    if meio > 0:
        for lado in (1.0, -1.0):
            x = lado * t_w / 2
            trechos.append(Trecho("alma", x, -meio, x, meio, ALMA, t_w))
    w = t_w / 2
    poligono = (
        (-b, h), (b, h), (b, h - t_f), (w, h - t_f), (w, -(h - t_f)), (b, -(h - t_f)),
        (b, -h), (-b, -h), (-b, -(h - t_f)), (-w, -(h - t_f)), (-w, h - t_f), (-b, h - t_f),
    )  # fmt: skip
    return Secao(nome, FORMA_I, tuple(trechos), poligono, d, b_f, t_f, t_w, r)


def _secao_u(nome: str, d: float, b_f: float, t_w: float, t_f: float) -> Secao:
    """O U com o dorso da alma à esquerda e as mesas para +x; origem no centro geométrico."""
    r = t_f
    h = d / 2
    a_alma = d * t_w
    a_mesas = 2 * (b_f - t_w) * t_f
    x_barra = (a_alma * t_w / 2 + a_mesas * (t_w + (b_f - t_w) / 2)) / (a_alma + a_mesas)
    trechos: list[Trecho] = [Trecho("dorso da alma", 0.0, -h, 0.0, h, ALMA, t_w)]
    for s in (1.0, -1.0):
        y_ext, y_int = s * h, s * (h - t_f)
        trechos.append(Trecho("mesa, face externa", 0.0, y_ext, b_f, y_ext, MESA, t_f))
        trechos.append(Trecho("ponta da mesa", b_f, y_int, b_f, y_ext, MESA, t_f))
        if b_f > t_w + r:
            trechos.append(Trecho("mesa, face interna", t_w + r, y_int, b_f, y_int, MESA, t_f))
    meio = h - t_f - r
    if meio > 0:
        trechos.append(Trecho("alma, face interna", t_w, -meio, t_w, meio, ALMA, t_w))
    poligono = (
        (0.0, h), (b_f, h), (b_f, h - t_f), (t_w, h - t_f), (t_w, -(h - t_f)),
        (b_f, -(h - t_f)), (b_f, -h), (0.0, -h),
    )  # fmt: skip
    return Secao(
        nome,
        FORMA_U,
        tuple(t.movido(-x_barra, 0.0) for t in trechos),
        tuple((x - x_barra, y) for x, y in poligono),
        d,
        b_f,
        t_f,
        t_w,
        r,
    )


def _secao_l(cant: ct.Cantoneira) -> Secao:
    """A cantoneira com o canto em baixo à esquerda: aba horizontal em +x, vertical em +y."""
    b, t = cant.b_mm, cant.t_mm
    r = t
    trechos: list[Trecho] = [
        Trecho("aba horizontal, face externa", 0.0, 0.0, b, 0.0, ABA, t),
        Trecho("ponta da aba horizontal", b, 0.0, b, t, ABA, t),
        Trecho("aba vertical, face externa", 0.0, 0.0, 0.0, b, ABA, t),
        Trecho("ponta da aba vertical", 0.0, b, t, b, ABA, t),
    ]
    if b > t + r:
        trechos.append(Trecho("aba horizontal, face interna", t + r, t, b, t, ABA, t))
        trechos.append(Trecho("aba vertical, face interna", t, t + r, t, b, ABA, t))
    poligono = ((0.0, 0.0), (b, 0.0), (b, t), (t, t), (t, b), (0.0, b))
    xb = cant.x_barra_mm
    return Secao(
        cant.nome,
        FORMA_L,
        tuple(tr.movido(-xb, -xb) for tr in trechos),
        tuple((x - xb, y - xb) for x, y in poligono),
        b,
        b,
        t,
        t,
        r,
    )


def secao(e: EntradaPerfilNoContorno) -> Secao:
    """A seção e o contorno de solda do perfil escolhido."""
    if e.forma not in FORMAS:
        raise LigacaoInvalida(f"Forma de perfil desconhecida: {e.forma!r}.")
    if e.forma == FORMA_L:
        if e.perfil not in ct.CATALOGO_CANTONEIRAS:
            raise LigacaoInvalida(f"Cantoneira fora do catálogo: {e.perfil!r}.")
        return _secao_l(ct.CATALOGO_CANTONEIRAS[e.perfil])
    perfis = sc.listar_perfis()
    if e.perfil not in perfis or e.perfil not in perfis_da_forma(e.forma):
        raise LigacaoInvalida(f"Perfil {e.perfil!r} não é um {FORMAS[e.forma]} do catálogo.")
    p = perfis[e.perfil]
    medidas = (p.altura_mm, p.largura_mm, p.espessura_alma_mm, p.espessura_mesa_mm)
    if min(medidas) <= 0:
        raise LigacaoInvalida(f"O perfil {e.perfil!r} não tem as medidas da seção no catálogo.")
    if e.forma == FORMA_I:
        return _secao_i(p.nome, *medidas)
    return _secao_u(p.nome, *medidas)


# =============================================================================================
# Propriedades do grupo de solda (linhas) e forças por mm
# =============================================================================================
@dataclass(frozen=True)
class GrupoDeLinhas:
    comprimento: float  # L = Σ comprimentos (mm)
    x_c: float  # centro geométrico do grupo, medido do centro da seção (mm)
    y_c: float
    i_x: float  # ∫y²ds pelo centro do grupo (mm³)
    i_y: float  # ∫x²ds
    i_xy: float  # ∫xy·ds

    @property
    def j(self) -> float:
        return self.i_x + self.i_y


def propriedades(trechos: Sequence[Trecho]) -> GrupoDeLinhas:
    total = sum(t.comprimento for t in trechos)
    if total <= 0:
        raise LigacaoInvalida("O contorno de solda ficou sem comprimento.")
    x_c = sum(t.comprimento * (t.x1 + t.x2) / 2 for t in trechos) / total
    y_c = sum(t.comprimento * (t.y1 + t.y2) / 2 for t in trechos) / total
    i_x = i_y = i_xy = 0.0
    for t in trechos:
        x1, y1, x2, y2 = t.x1 - x_c, t.y1 - y_c, t.x2 - x_c, t.y2 - y_c
        c = t.comprimento
        i_x += c * (y1 * y1 + y1 * y2 + y2 * y2) / 3
        i_y += c * (x1 * x1 + x1 * x2 + x2 * x2) / 3
        i_xy += c * (2 * x1 * y1 + x1 * y2 + x2 * y1 + 2 * x2 * y2) / 6
    return GrupoDeLinhas(total, x_c, y_c, i_x, i_y, i_xy)


@dataclass(frozen=True)
class EsforcosNoGrupo:
    """Os esforços (N, N·mm) levados ao centro geométrico do grupo de solda."""

    n: float
    vx: float
    vy: float
    mx: float
    my: float
    t: float


def esforcos_no_grupo(e: EntradaPerfilNoContorno, g: GrupoDeLinhas) -> EsforcosNoGrupo:
    n = e.n_sd_kN * 1e3
    vx, vy = e.vx_sd_kN * 1e3, e.vy_sd_kN * 1e3
    # aplicados no centro da seção, que fica em (−x_c; −y_c) visto do centro do grupo
    mx = e.mx_sd_kNm * 1e6 - n * g.y_c
    my = e.my_sd_kNm * 1e6 - n * g.x_c
    t = e.t_sd_kNm * 1e6 - g.x_c * vy + g.y_c * vx
    return EsforcosNoGrupo(n, vx, vy, mx, my, t)


@dataclass(frozen=True)
class ForcaNoPonto:
    x: float  # do centro da seção (mm)
    y: float
    f_n: float  # N/mm, tração +, a parte que vai à solda (com contato, só a tração)
    f_vx: float
    f_vy: float
    trecho: Trecho

    @property
    def f_v(self) -> float:
        return math.hypot(self.f_vx, self.f_vy)

    @property
    def resultante(self) -> float:
        return math.sqrt(self.f_n**2 + self.f_vx**2 + self.f_vy**2)


def forca_no_ponto(
    g: GrupoDeLinhas,
    f: EsforcosNoGrupo,
    x: float,
    y: float,
    trecho: Trecho,
    *,
    contato: bool,
) -> ForcaNoPonto:
    xr, yr = x - g.x_c, y - g.y_c
    det = g.i_x * g.i_y - g.i_xy**2
    a = (f.my * g.i_x - f.mx * g.i_xy) / det
    b = (f.mx * g.i_y - f.my * g.i_xy) / det
    f_n = f.n / g.comprimento + a * xr + b * yr
    usado = max(f_n, 0.0) if contato else abs(f_n)
    f_vx = f.vx / g.comprimento - f.t * yr / g.j
    f_vy = f.vy / g.comprimento + f.t * xr / g.j
    return ForcaNoPonto(x, y, usado, f_vx, f_vy, trecho)


def forcas_nas_pontas(
    trechos: Sequence[Trecho], g: GrupoDeLinhas, f: EsforcosNoGrupo, *, contato: bool
) -> list[ForcaNoPonto]:
    """A força por mm nas duas pontas de cada trecho (onde ficam os máximos)."""
    return [forca_no_ponto(g, f, x, y, t, contato=contato) for t in trechos for x, y in t.pontas()]


# =============================================================================================
# Cálculo
# =============================================================================================
def _validar(e: EntradaPerfilNoContorno) -> None:
    sd.validar_norma(e.norma)
    sd.coeficientes(e.combinacao)
    for aco, oque in ((e.aco_perfil, "perfil"), (e.aco_chapa, "chapa")):
        if aco not in ACOS:
            raise LigacaoInvalida(f"Aço desconhecido ({oque}): {aco!r}.")
    if e.eletrodo not in ELETRODOS:
        raise LigacaoInvalida(f"Eletrodo desconhecido: {e.eletrodo!r}.")
    if e.t_chapa_mm <= 0:
        raise LigacaoInvalida("A espessura da chapa precisa ser positiva.")
    if e.perna_mm < 0:
        raise LigacaoInvalida("A perna não pode ser negativa (0 = automática).")


def _resistencia_por_mm(perna: float, f_w: float, c: sd.Coeficientes) -> float:
    """N/mm de filete: 0,60·f_w·0,707·d_w/γ_w2."""
    return sd.resistencia_filete_por_mm(perna, f_w, c.w2) * 1000.0


def _perna_automatica(demanda: float, f_w: float, c: sd.Coeficientes, minima: float, maxima: float) -> float:  # fmt: skip
    validas = [p for p in PERNAS_COMERCIAIS if minima - 1e-9 <= p <= maxima + 1e-9]
    for perna in validas:
        if demanda <= _resistencia_por_mm(perna, f_w, c) + 1e-9:
            return perna
    return validas[-1] if validas else max(minima, PERNAS_COMERCIAIS[0])


def _nome_das_paredes(s: Secao) -> str:
    if s.forma == FORMA_L:
        return f"abas t = {_n(s.t_mesa, 2)}"
    return f"mesas t_f = {_n(s.t_mesa, 2)}, alma t_w = {_n(s.t_alma, 2)}"


def calcular(e: EntradaPerfilNoContorno) -> ResultadoLigacao:
    _validar(e)
    norma = e.norma
    c = sd.coeficientes(e.combinacao)
    s = secao(e)
    g = propriedades(s.trechos)
    f = esforcos_no_grupo(e, g)
    pontos = forcas_nas_pontas(s.trechos, g, f, contato=e.contato)
    critico = max(pontos, key=lambda p: p.resultante)
    f_w = ELETRODOS[e.eletrodo]
    fy_p, fu_p = ACOS[e.aco_perfil]
    fy_c, fu_c = ACOS[e.aco_chapa]
    t_paredes = min(s.t_mesa, s.t_alma)
    t_menor = min(t_paredes, e.t_chapa_mm)
    minima = sd.perna_minima(t_menor)
    maxima = sd.perna_maxima(s.t_mesa, norma)  # o filete contorna a ponta da mesa (ou da aba)
    perna = e.perna_mm or _perna_automatica(critico.resultante, f_w, c, minima, maxima)
    r_w = _resistencia_por_mm(perna, f_w, c)
    estimada = critico.resultante / _resistencia_por_mm(1.0, f_w, c)

    linhas: list[Verificacao] = []
    ref_w = sd.ref(norma, f"6.2.5.1, {sd.tabela(norma, 'resistencia')}", vista_na_2025=True)
    contato_txt = (
        f"; ponta faceada, compressão por contato ({AISC_CONTATO}): só a tração vai à solda"
        if e.contato
        else "; sem contato garantido, a solda leva também a compressão"
    )
    texto_perna = (
        f"d_w = {_n(perna, 0)} mm (informada)"
        if e.perna_mm > 0
        else f"d_w = {_n(perna, 0)} mm (automática: a menor perna comercial que passa)"
    )
    linhas.append(
        Verificacao(
            "Solda: filete no ponto mais solicitado do contorno",
            critico.resultante / 1000.0,
            r_w / 1000.0,
            "kN/mm",
            f"{ref_w}; método elástico",
            f"f_r = √(f_n² + f_vx² + f_vy²) em (x; y) = ({_n(critico.x, 1)}; {_n(critico.y, 1)}) mm "
            f"({critico.trecho.nome}): f_n = {_n(critico.f_n / 1000, 3)}, f_vx = "
            f"{_n(critico.f_vx / 1000, 3)}, f_vy = {_n(critico.f_vy / 1000, 3)} kN/mm; "
            f"L = {_n(g.comprimento, 0)} mm de filete em {len(s.trechos)} trechos; "
            f"F_w,Rd = 0,60·f_w·0,707·d_w/γ_w2 = 0,60 × {_n(f_w, 0)} × 0,707 × {_n(perna, 0)}/"
            f"{_n(c.w2)}; {texto_perna}{contato_txt}",
        )
    )
    # metal-base do perfil: cada parede tem filete nas duas faces, que descarregam na mesma chapa
    pior_mb: tuple[float, str] | None = None
    for p in pontos:
        t_el = p.trecho.espessura
        r_n = fy_p * t_el / c.a1
        r_v, modo = sd.metal_base_ao_cisalhamento_por_mm(t_el, fy_p, fu_p, c)
        n_el, v_el = 2 * p.f_n, 2 * p.f_v
        razao = math.hypot(n_el / r_n, v_el / (r_v * 1000.0))
        if pior_mb is None or razao > pior_mb[0]:
            pior_mb = (
                razao,
                f"na {p.trecho.elemento} (t = {_n(t_el, 2)} mm), em ({_n(p.x, 1)}; {_n(p.y, 1)}) "
                f"mm, filetes nas duas faces: normal 2·f_n = {_n(n_el / 1000, 3)} kN/mm frente a "
                f"f_y·t/γ_a1 = {_n(r_n / 1000, 3)} kN/mm e cortante 2·f_v = {_n(v_el / 1000, 3)} "
                f"kN/mm frente a {modo} = {_n(r_v, 3)} kN/mm; √((n/R_n)² + (v/R_v)²) ≤ 1 "
                f"(f_y = {_n(fy_p, 0)} MPa, f_u = {_n(fu_p, 0)} MPa)",
            )
    assert pior_mb is not None
    linhas.append(
        Verificacao(
            "Perfil: metal-base junto à solda",
            pior_mb[0],
            1.0,
            "—",
            sd.ref(norma, "6.5.5"),
            pior_mb[1],
        )  # fmt: skip
    )
    f_v_max = max(p.f_v for p in pontos)
    if f_v_max > 0:
        r_v_c, modo_c = sd.metal_base_ao_cisalhamento_por_mm(e.t_chapa_mm, fy_c, fu_c, c)
        linhas.append(
            Verificacao(
                "Chapa: metal-base junto à solda (cisalhamento)",
                f_v_max / 1000.0,
                r_v_c,
                "kN/mm",
                sd.ref(norma, "6.5.5"),
                f"a maior força no plano da chapa, f_v = √(f_vx² + f_vy²), descarrega na espessura "
                f"t = {_n(e.t_chapa_mm, 2)} mm; {modo_c}",
            )
        )
    ref_perna = sd.ref(norma, f"6.2.6.2.1, {sd.tabela(norma, 'perna')}", vista_na_2025=True)
    linhas.append(
        sd.linha_minimo(
            "Solda: perna mínima",
            minima,
            perna,
            "mm",
            ref_perna,
            f"pela parte menos espessa ({_nome_das_paredes(s)} e chapa {_n(e.t_chapa_mm, 2)} mm); "
            "filete de um passe",
        )
    )
    linhas.append(
        sd.linha_maximo(
            "Solda: perna máxima na ponta da mesa"
            if s.forma != FORMA_L
            else "Solda: perna máxima na ponta da aba",
            perna,
            maxima,
            "mm",
            sd.ref(norma, "6.2.6.2.2"),
            f"o filete contorna a ponta, uma borda de {_n(s.t_mesa, 2)} mm: t < "
            f"{_n(sd.LIMITE_DA_PERNA_MAXIMA[norma])} mm → perna ≤ t; senão perna ≤ t − 1,5 mm",
        )  # fmt: skip
    )
    linhas.append(
        sd.linha_minimo(
            "Solda: comprimento mínimo",
            sd.comprimento_minimo(perna),
            g.comprimento,
            "mm",
            sd.ref(norma, "6.2.6.2.3"),
            "o filete é contínuo em volta da seção (contorna as pontas e os cantos): L ≥ "
            "máx(4·d_w; 40 mm) vale para o contorno inteiro",
        )
    )
    linhas.append(
        Verificacao(
            "Contorno de solda adotado",
            g.comprimento,
            None,
            "mm",
            "geometria do perfil",
            f"{len(s.trechos)} trechos ({', '.join(sorted({t.nome for t in s.trechos}))}); centro "
            f"do grupo em (x; y) = ({_n(g.x_c, 1)}; {_n(g.y_c, 1)}) mm do centro da seção; I_x = "
            f"{_n(g.i_x / 1e3, 1)}·10³ mm³, I_y = {_n(g.i_y / 1e3, 1)}·10³ mm³, I_xy = "
            f"{_n(g.i_xy / 1e3, 1)}·10³ mm³ (linhas)",
            status="INFO",
            tipo="informativo",
        )
    )
    avisos: list[str] = []
    if e.n_sd_kN > 0 or abs(e.mx_sd_kNm) > 0 or abs(e.my_sd_kNm) > 0:
        avisos.append(
            "A chapa onde o perfil é soldado fica tracionada ou fletida pela solda: a flexão "
            "dela (chapa de extremidade, de base ou de topo) não é verificada aqui."
        )
    grandezas = {
        "comprimento_total_mm": g.comprimento,
        "perna_mm": perna,
        "perna_estimada_mm": estimada,
        "f_r_kN_mm": critico.resultante / 1000.0,
        "x_critico_mm": critico.x,
        "y_critico_mm": critico.y,
        "x_grupo_mm": g.x_c,
        "y_grupo_mm": g.y_c,
    }
    titulo = f"{s.nome} soldado em todo o contorno — filete de {_n(perna, 0)} mm"
    return ResultadoLigacao(
        PERFIL_NO_CONTORNO,
        titulo,
        e,
        tuple(linhas),
        grandezas,
        tuple(avisos),
        replace(e, perna_mm=perna),
    )


# =============================================================================================
# Desenho
# =============================================================================================
def _forcas_em_texto(e: EntradaPerfilNoContorno) -> list[str]:
    itens = []
    if e.n_sd_kN:
        itens.append(f"N = {_n(e.n_sd_kN, 1)} kN ({'tração' if e.n_sd_kN > 0 else 'compressão'})")
    for nome, valor, un in (
        ("V_x", e.vx_sd_kN, "kN"), ("V_y", e.vy_sd_kN, "kN"), ("M_x", e.mx_sd_kNm, "kN·m"),
        ("M_y", e.my_sd_kNm, "kN·m"), ("T", e.t_sd_kNm, "kN·m"),
    ):  # fmt: skip
        if valor:
            itens.append(f"{nome} = {_n(valor, 2 if un == 'kN·m' else 1)} {un}")
    return itens or ["sem esforços"]


def figura(e: EntradaPerfilNoContorno, giro_graus: float = 0.0) -> ImagemDiagrama:
    """A seção do perfil vista de frente, o filete no contorno e o ponto mais solicitado."""
    del giro_graus  # a seção não gira (os eixos x e y são os do perfil)
    s = secao(e)
    largura_px, altura_px = 900, 520
    imagem = Image.new("RGB", (largura_px * _ESC, altura_px * _ESC), "#ffffff")
    dr = ImageDraw.Draw(imagem)
    xs = [x for x, _ in s.poligono]
    ys = [y for _, y in s.poligono]
    folga = 0.12 * max(max(xs) - min(xs), max(ys) - min(ys))
    tela = _Tela(
        [(min(xs) - folga, -(max(ys) + folga)), (max(xs) + folga, -(min(ys) - folga))],
        (110, 90, 560, 470),
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return tela(x, -y)

    margem = [
        p(min(xs) - folga * 0.6, max(ys) + folga * 0.6),
        p(max(xs) + folga * 0.6, max(ys) + folga * 0.6),
        p(max(xs) + folga * 0.6, min(ys) - folga * 0.6),
        p(min(xs) - folga * 0.6, min(ys) - folga * 0.6),
    ]
    dr.polygon(margem, fill=_CHAPA_AZUL, outline=_LINHA, width=2 * _ESC)
    dr.polygon([p(x, y) for x, y in s.poligono], fill=_BARRA, outline=_LINHA, width=2 * _ESC)
    for t in s.trechos:
        dr.line([p(t.x1, t.y1), p(t.x2, t.y2)], fill=_SOLDA, width=5 * _ESC)
    fonte = _fonte(12 * _ESC)
    # eixos pelo centro da seção
    centro = p(0.0, 0.0)
    for dx, dy, nome in ((1.0, 0.0, "x"), (0.0, 1.0, "y")):
        # os eixos acabam na borda da chapa
        fim = p(dx * (max(xs) + folga * 0.45), dy * (max(ys) + folga * 0.45))
        dr.line([centro, fim], fill=_TEXTO, width=_ESC)
        _rotulo(dr, fim, tela.direcao(dx, -dy), 6 * _ESC, nome, _TEXTO, fonte)
    raio = 5 * _ESC
    dr.ellipse([centro[0] - raio, centro[1] - raio, centro[0] + raio, centro[1] + raio], outline=_TEXTO, width=2 * _ESC)  # fmt: skip
    itens_ponto: list[tuple[str, str, str]] = []
    try:
        r = calcular(e)
    except LigacaoInvalida:
        r = None
    if r is not None:
        g = r.grandezas
        grupo = p(g["x_grupo_mm"], g["y_grupo_mm"])
        if math.dist(grupo, centro) > 3 * _ESC:
            dr.rectangle([grupo[0] - 4 * _ESC, grupo[1] - 4 * _ESC, grupo[0] + 4 * _ESC, grupo[1] + 4 * _ESC], outline=_COTA, width=2 * _ESC)  # fmt: skip
            itens_ponto.append(("", _COTA, "Quadrado cinza: centro do grupo de solda"))
        pc = p(g["x_critico_mm"], g["y_critico_mm"])
        dr.ellipse([pc[0] - 9 * _ESC, pc[1] - 9 * _ESC, pc[0] + 9 * _ESC, pc[1] + 9 * _ESC], outline=_FORCA, width=3 * _ESC)  # fmt: skip
        itens_ponto.append(("", _FORCA, "Círculo laranja: ponto mais solicitado"))
    # cotas
    abaixo, esquerda = tela.direcao(0.0, 1.0), tela.direcao(-1.0, 0.0)
    fora = folga * 0.6 * tela.esc + 16 * _ESC  # as cotas ficam fora da chapa
    _cota_alinhada(dr, p(min(xs), min(ys)), p(max(xs), min(ys)), abaixo, f"{'b' if s.forma == FORMA_L else 'b_f'} = {_n(s.largura, 1)}", fora)  # fmt: skip
    _cota_alinhada(dr, p(min(xs), min(ys)), p(min(xs), max(ys)), esquerda, f"{'b' if s.forma == FORMA_L else 'd'} = {_n(s.altura, 1)}", fora)  # fmt: skip
    perna = r.grandezas["perna_mm"] if r is not None else e.perna_mm
    titulo = "Perfil soldado em todo o contorno"
    dr.text((18 * _ESC, 14 * _ESC), titulo, fill=_TEXTO, font=_fonte(16 * _ESC))
    dr.text(
        (18 * _ESC, 38 * _ESC),
        f"{s.nome} na chapa de {_n(e.t_chapa_mm, 1)} mm; filete de {_n(perna, 0)} mm "
        f"({e.eletrodo}). Vista de frente, do lado do perfil. Cotas em mm.",
        fill=_COTA,
        font=_fonte(11 * _ESC),
    )
    _legenda(
        dr,
        600 * _ESC,
        110 * _ESC,
        [
            ("linha", _SOLDA, f"Filete no contorno (perna {_n(perna, 0)} mm)"),
            ("area", _BARRA, "Seção do perfil"),
            ("area", _CHAPA_AZUL, "Chapa onde o perfil é soldado"),
            ("ponto", _TEXTO, "Centro da seção (esforços aplicados)"),
            *itens_ponto,
            ("", _FORCA, "Esforços de cálculo:"),
            *(("", _FORCA, f"   {texto}") for texto in _forcas_em_texto(e)),
        ],
    )
    legenda = (
        f"{s.nome} soldado em todo o contorno: {len(s.trechos)} trechos de filete de "
        f"{_n(perna, 0)} mm; esforços no centro da seção ({'; '.join(_forcas_em_texto(e))})."
    )
    return figura_final(imagem, titulo, legenda)


# =============================================================================================
# Registro
# =============================================================================================
_ROTULOS: dict[str, dict[str, str]] = {"forma": FORMAS, "combinacao": sd.COMBINACOES}


def campos_do_registro(e: EntradaPerfilNoContorno) -> dict[str, Any]:
    """Os dados de entrada para o memorial, com os códigos em texto."""
    dados: dict[str, Any] = {k: getattr(e, k) for k in e.__dataclass_fields__}
    for chave, rotulos in _ROTULOS.items():
        dados[chave] = rotulos.get(str(dados[chave]), dados[chave])
    if e.perna_mm <= 0:
        dados["perna_mm"] = "automática"
    return dados


METODO = (
    "Perfil (W, HP, I, U ou cantoneira) soldado numa chapa por filete em todo o contorno da "
    "seção — faces externas, pontas e faces internas. Método elástico com os filetes como linhas: "
    "os esforços dados no centro da seção (N, V_x, V_y, M_x, M_y e T) são levados ao centro do "
    "grupo de solda; a força normal por mm vem da flexão oblíqua das linhas (com o produto de "
    "inércia, que existe na cantoneira) e a do plano da chapa da cortante direta mais a torção. A "
    "resultante no ponto mais solicitado fica abaixo da resistência do filete (tabela das soldas "
    "da NBR 8800, sem o aumento pela direção); metal-base do perfil e da chapa pela 6.5.5; limites "
    "de perna e de comprimento pela 6.2.6."
)
PREMISSAS = [
    "Raio de concordância estimado na espessura da mesa (na da aba, na cantoneira); o trecho do "
    "raio fica fora da conta da solda (a favor da segurança).",
    "Forças por mm pelo método elástico, sem o aumento 1 + 0,5·sen^1,5 θ (a favor da segurança).",
    "Esforços aplicados no centro geométrico da seção; no U e na cantoneira eles são levados ao "
    "centro do grupo de solda (aparecem momentos e torção de transporte).",
    "Metal-base do perfil: as duas faces de cada parede soldadas, com a força dos dois filetes na "
    "mesma parede.",
    "No U laminado, a mesa com a espessura média do catálogo.",
    "A flexão da chapa onde o perfil é soldado e o perfil fora da ligação ficam com o projetista.",
]
