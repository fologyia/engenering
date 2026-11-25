"""As soldas da base de pilar: o pilar na placa, a placa de cisalhamento e as arruelas especiais.

Regras puras (sem Streamlit), chamadas por :mod:`core.base_de_pilar` em cada combinação.
Unidades: mm, N e MPa na entrada; as linhas de verificação saem em kN/mm, mm e kN.

**Solda de contorno do pilar na placa.** Filetes de pernas iguais em volta do perfil: as faces
externas das mesas, as faces internas (de cada lado da alma, descontado o raio de concordância,
estimado em t_f porque o catálogo não o traz) e os dois lados da alma. O grupo é tratado pelo
**método elástico** com os filetes como linhas (espessura unitária): a força por milímetro num
ponto (x, y) do contorno é

* normal (tração +): f_n = −N/L − M·x/I_x,L − M_y·y/I_y,L, com L = Σ comprimentos,
  I_x,L = Σ∫x²·ds e I_y,L = Σ∫y²·ds (M comprime x > 0 e M_y comprime y > 0, como na placa);
* cortante: f_v = V/L, a mesma em todos os filetes (V_Sd é a resultante, em qualquer direção);

e a resultante √(f_n² + f_v²) no ponto mais solicitado (as pontas dos trechos, porque o campo é
linear) fica abaixo da resistência do filete por milímetro, 0,60·f_w·(0,707·d_w)/γ_w2 (NBR 8800
6.2.5, Tabela 9), sem o fator 1 + 0,5·sen^1,5 θ (a favor da segurança). Com a extremidade do pilar
faceada e a compressão passando por contato (AISC 360-22 J1.4 a), só a parte tracionada de f_n vai
para a solda. O metal-base do pilar ao cisalhamento (6.5.5) e os limites de 6.2.6 (perna mínima da
Tabela 11, máxima na ponta da mesa e comprimento mínimo dos trechos internos) completam.

**Placa de cisalhamento.** Dois filetes ao longo de b_h, um de cada face, levam a cortante V_Rd e o
momento ½·σ_c,Rd·b_h·(b_v² − e_n²) da 6.7.2.4 (a solda é dimensionada pela resistência da placa,
não pela solicitação): o momento vira um binário entre os dois filetes, com braço t_pv + 2·d_w/3
(entre os centros das gargantas).

**Arruelas especiais soldadas (6.7.2.5).** Filete no contorno da arruela (4 lados) para a força
F_v,Rd,i do chumbador.

**Pilar U.** O contorno é o dorso da alma, as faces externas das mesas, as faces internas (da alma,
descontado o raio, até a ponta) e a face interna da alma. O grupo não é simétrico em y: o centro
dele (y_c) não coincide com o centro geométrico do U, onde atuam os esforços, e a força normal vai
com N levado ao centro do grupo, f_n = −N/L − M·x/I_x,L − (M_y − N·y_c)·(y − y_c)/I_y,L, com I_y,L
pelo centro do grupo.

Perna 0 = automática: a menor perna comercial que passa, de 3 a 25 mm.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import soldas as sd
from core.verificacao import Verificacao

#: Pernas de filete usuais (mm), para a perna automática.
PERNAS_COMERCIAIS: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 25.0)  # fmt: skip
ELETRODO_PADRAO = "E70"
AISC_CONTATO = "AISC 360-22 J1.4 a)"
GRUPO_SOLDAS = "Soldas"


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor + 0.0:.{casas}f}".replace(".", ",")


def _ref(texto: str) -> str:
    return sd.ref(sd.NBR_2025, texto)


@dataclass(frozen=True)
class Trecho:
    """Um filete reto do contorno, de (x1, y1) a (x2, y2), em mm a partir do centro do pilar."""

    nome: str
    x1: float
    y1: float
    x2: float
    y2: float
    elemento: str  # "mesa" ou "alma": de qual chapa do pilar é o metal-base

    @property
    def comprimento(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    def integral_x2(self) -> float:
        return self.comprimento * (self.x1**2 + self.x1 * self.x2 + self.x2**2) / 3

    def integral_y2(self) -> float:
        return self.comprimento * (self.y1**2 + self.y1 * self.y2 + self.y2**2) / 3

    def integral_y(self) -> float:
        return self.comprimento * (self.y1 + self.y2) / 2


def contorno_do_pilar(
    d: float,
    b_f: float,
    t_w: float,
    t_f: float,
    *,
    mesas_por_dentro: bool,
    alma: bool,
    y_dorso: float | None = None,
) -> list[Trecho]:
    """Os filetes do contorno do perfil I (as faces das mesas e os dois lados da alma).

    Com ``y_dorso``, o perfil é um U com o dorso da alma em y = y_dorso e as mesas abertas para o
    lado do centro (y_dorso ≤ 0: para +y); o dorso é sempre soldado e ``alma`` liga a face interna.
    """
    r = t_f  # raio de concordância estimado (o catálogo não traz)
    if y_dorso is not None:
        return _contorno_do_u(d, b_f, t_w, t_f, r, y_dorso, mesas_por_dentro, alma)
    trechos: list[Trecho] = []
    for lado in (1.0, -1.0):
        x = lado * d / 2
        trechos.append(Trecho("mesa, face externa", x, -b_f / 2, x, b_f / 2, "mesa"))
        if mesas_por_dentro:
            x_i = lado * (d / 2 - t_f)
            inicio = t_w / 2 + r
            if b_f / 2 > inicio:
                for s in (1.0, -1.0):
                    trechos.append(
                        Trecho("mesa, face interna", x_i, s * inicio, x_i, s * b_f / 2, "mesa")
                    )
    if alma:
        meio = d / 2 - t_f - r
        if meio > 0:
            for s in (1.0, -1.0):
                y = s * t_w / 2
                trechos.append(Trecho("alma", -meio, y, meio, y, "alma"))
    return trechos


def _contorno_do_u(
    d: float,
    b_f: float,
    t_w: float,
    t_f: float,
    r: float,
    y_dorso: float,
    mesas_por_dentro: bool,
    alma: bool,
) -> list[Trecho]:
    s = 1.0 if y_dorso <= 0 else -1.0  # para onde as mesas abrem
    ponta = y_dorso + s * b_f
    trechos = [Trecho("dorso da alma", -d / 2, y_dorso, d / 2, y_dorso, "alma")]
    for lado in (1.0, -1.0):
        x = lado * d / 2
        trechos.append(Trecho("mesa, face externa", x, y_dorso, x, ponta, "mesa"))
        if mesas_por_dentro and b_f > t_w + r:
            x_i = lado * (d / 2 - t_f)
            trechos.append(
                Trecho("mesa, face interna", x_i, y_dorso + s * (t_w + r), x_i, ponta, "mesa")
            )
    meio = d / 2 - t_f - r
    if alma and meio > 0:
        y = y_dorso + s * t_w
        trechos.append(Trecho("alma, face interna", -meio, y, meio, y, "alma"))
    return trechos


@dataclass(frozen=True)
class GrupoDeSolda:
    comprimento: float  # mm
    i_x: float  # Σ∫x² ds (mm³)
    i_y: float  # Σ∫(y − y_c)² ds, pelo centro do grupo
    y_c: float = 0.0  # centro do grupo em y (0 na I, que é simétrica)


def propriedades(trechos: Sequence[Trecho]) -> GrupoDeSolda:
    comprimento = sum(t.comprimento for t in trechos)
    y_c = sum(t.integral_y() for t in trechos) / comprimento if comprimento > 0 else 0.0
    if abs(y_c) < 1e-9:
        y_c = 0.0
    return GrupoDeSolda(
        comprimento,
        sum(t.integral_x2() for t in trechos),
        sum(t.integral_y2() for t in trechos) - comprimento * y_c**2,
        y_c,
    )


@dataclass(frozen=True)
class PontoCritico:
    x: float
    y: float
    f_n: float  # N/mm, tração +, a parte que vai para a solda
    f_v: float  # N/mm
    elemento: str

    @property
    def resultante(self) -> float:
        return math.hypot(self.f_n, self.f_v)


def _normal_no_ponto(
    p: GrupoDeSolda,
    axial: float,
    momento: float,
    momento_y: float,
    x: float,
    y: float,
    contato: bool,
) -> float:
    """A força normal por mm que vai à solda no ponto (x, y): com contato, só a tração."""
    f_n = -axial / p.comprimento
    if p.i_x > 0:
        f_n -= momento * x / p.i_x
    if p.i_y > 0:  # N e M_y levados ao centro do grupo (no U ele não é o centro do perfil)
        f_n -= (momento_y - axial * p.y_c) * (y - p.y_c) / p.i_y
    return max(f_n, 0.0) if contato else abs(f_n)


def pontos_do_grupo(
    trechos, axial, momento, momento_y, cortante, contato, vx=None, vy=None, mz=0.0
):
    p = propriedades(trechos)
    j = p.i_x + p.i_y
    for t in trechos:
        for x, y in ((t.x1, t.y1), (t.x2, t.y2)):
            normal = _normal_no_ponto(p, axial, momento, momento_y, x, y, contato)
            if vx is None and vy is None:
                # V sem direção: limite superior sobre todas as orientações.
                fv = (
                    cortante / p.comprimento
                    + (abs(mz) + abs(p.y_c) * cortante) * math.hypot(x, y - p.y_c) / j
                )
            else:
                vx0, vy0 = vx or 0.0, vy or 0.0
                torque = mz + p.y_c * vx0
                fv = math.hypot(
                    vx0 / p.comprimento - torque * (y - p.y_c) / j,
                    vy0 / p.comprimento + torque * x / j,
                )
            yield PontoCritico(x, y, normal, fv, t.elemento)


def ponto_critico(
    trechos: Sequence[Trecho],
    axial: float,
    momento: float,
    momento_y: float,
    cortante: float,
    *,
    contato: bool,
    vx=None,
    vy=None,
    mz=0.0,
) -> PontoCritico:
    return max(
        pontos_do_grupo(trechos, axial, momento, momento_y, cortante, contato, vx, vy, mz),
        key=lambda ponto: ponto.resultante,
    )


def _perna_automatica(passa: object, minima: float, maxima: float) -> float:
    """A menor perna comercial entre a mínima e a máxima que passa; sem nenhuma, a maior possível."""
    validas = [p for p in PERNAS_COMERCIAIS if minima - 1e-9 <= p <= maxima + 1e-9]
    for perna in validas:
        if passa(perna):  # type: ignore[operator]
            return perna
    return validas[-1] if validas else max(minima, PERNAS_COMERCIAIS[0])


def _texto_perna(informada: float, adotada: float) -> str:
    return (
        f"d_w = {_n(adotada, 0)} mm (informada)"
        if informada > 0
        else f"d_w = {_n(adotada, 0)} mm (automática: a menor perna comercial que passa)"
    )


def _resistencia_por_mm(perna: float, f_w: float, c: sd.Coeficientes) -> float:
    """N/mm de filete: 0,60·f_w·0,707·d_w/γ_w2."""
    return sd.resistencia_filete_por_mm(perna, f_w, c.w2) * 1000.0


# =============================================================================================
# Pilar na placa
# =============================================================================================
@dataclass(frozen=True)
class SoldaDoPilar:
    perna: float
    linhas: tuple[Verificacao, ...]


def solda_do_pilar(
    *,
    d: float,
    b_f: float,
    t_w: float,
    t_f: float,
    t_placa: float,
    aco_pilar: tuple[float, float],
    axial: float,
    momento: float,
    momento_y: float,
    cortante: float,
    perna_informada: float,
    eletrodo: str,
    mesas_por_dentro: bool,
    alma: bool,
    contato: bool,
    c: sd.Coeficientes,
    y_dorso: float | None = None,
    vx: float | None = None,
    vy: float | None = None,
    mz: float = 0.0,
    aco_placa: tuple[float, float] = (250.0, 400.0),
) -> SoldaDoPilar:
    """As verificações da solda de contorno do pilar na placa (forças em N e N·mm).

    ``y_dorso``: pilar U (ver :func:`contorno_do_pilar`)."""
    trechos = contorno_do_pilar(
        d, b_f, t_w, t_f, mesas_por_dentro=mesas_por_dentro, alma=alma, y_dorso=y_dorso
    )
    e_u = y_dorso is not None
    f_w = sd.ELETRODOS[eletrodo]
    fy, fu = aco_pilar
    minima = max(
        sd.perna_minima(min(t_f, t_placa)),
        sd.perna_minima(min(t_w, t_placa)) if alma or e_u else 0.0,  # no U, o dorso sempre
    )
    maxima = sd.perna_maxima(t_f)
    internos = [t for t in trechos if t.nome == "mesa, face interna"]

    def passa(perna: float) -> bool:
        uteis = [t for t in trechos if t.comprimento + 1e-9 >= sd.comprimento_minimo(perna)]
        if not uteis:
            return False
        ponto = ponto_critico(
            uteis, axial, momento, momento_y, cortante, contato=contato, vx=vx, vy=vy, mz=mz
        )
        return ponto.resultante <= _resistencia_por_mm(perna, f_w, c) + 1e-9

    perna = perna_informada or _perna_automatica(passa, minima, maxima)
    descartados = [t for t in trechos if t.comprimento + 1e-9 < sd.comprimento_minimo(perna)]
    trechos = [t for t in trechos if t not in descartados]
    if not trechos:
        return SoldaDoPilar(
            perna,
            (
                Verificacao(
                    "Solda do pilar na placa: comprimento efetivo",
                    None,
                    None,
                    "mm",
                    _ref("6.2.6.2.3"),
                    "Todos os segmentos ficam abaixo do mínimo.",
                    status="NÃO OK",
                ),
            ),
        )
    p = propriedades(trechos)
    pontos = list(
        pontos_do_grupo(trechos, axial, momento, momento_y, cortante, contato, vx, vy, mz)
    )
    critico = max(pontos, key=lambda ponto: ponto.resultante)
    r_w = _resistencia_por_mm(perna, f_w, c)
    linhas: list[Verificacao] = []
    ref_w = _ref("6.2.5")
    contato_txt = (
        f"; compressão por contato na extremidade faceada ({AISC_CONTATO}): só a tração vai à solda"
        if contato
        else "; sem contato garantido, a solda leva também a compressão"
    )
    linhas.append(
        Verificacao(
            "Solda do pilar na placa: filete no ponto mais solicitado",
            critico.resultante / 1000.0,
            r_w / 1000.0,
            "kN/mm",
            f"{ref_w} ({sd.tabela(sd.NBR_2025, 'resistencia')}); método elástico",
            "f_r = √(f_n² + f_v²), "
            + (
                f"f_n = −N/L − M·x/I_x − (M_y − N·y_c)·(y − y_c)/I_y (U: N levado ao centro do "
                f"grupo, y_c = {_n(p.y_c, 1)} mm do centro do perfil) = "
                if e_u
                else "f_n = −N/L − M·x/I_x − M_y·y/I_y = "
            )
            + f"{_n(critico.f_n / 1000, 3)} "
            f"kN/mm em (x; y) = ({_n(critico.x, 0)}; {_n(critico.y, 0)}) mm. "
            f"J_w = {_n(p.i_x + p.i_y)} mm³, y_c = {_n(p.y_c)} mm, M_z = {_n(mz / 1e6)} kN·m. "
            "Cortante direto e torção em relação ao centro do grupo, f_v = "
            f"{_n(critico.f_v / 1000, 3)} kN/mm; L = {_n(p.comprimento, 0)} mm de filete "
            f"({len(trechos)} trechos efetivos: {', '.join(dict.fromkeys(t.nome for t in trechos))}. {len(descartados)} excluídos por comprimento). "
            f"A_w = {_n(0.707 * perna * p.comprimento, 1)} mm², I_x = {_n(p.i_x, 1)}, I_y = {_n(p.i_y, 1)} mm³. "
            f"F_w,Rd = 0,60·f_w·0,707·d_w/γ_w2 = 0,60 × {_n(f_w, 0)} × 0,707 × {_n(perna, 0)}"
            f"/{_n(c.w2)}; {_texto_perna(perna_informada, perna)}{contato_txt}",
        )
    )
    # metal-base do pilar: os filetes das duas faces (ou o de uma só) descarregam na mesma chapa —
    # a força normal escoa a chapa à tração (f_y·t/γ_a1) e a cortante a cisalha (6.5.5)
    pior_mb: tuple[float, str] | None = None
    for elemento in sorted({t.elemento for t in trechos}):
        do_elemento = [t for t in trechos if t.elemento == elemento]
        t_el = t_w if elemento == "alma" else t_f
        r_n = fy * t_el / c.a1
        r_v, modo = sd.metal_base_ao_cisalhamento_por_mm(t_el, fy, fu, c)
        # as duas faces da chapa soldadas (I: os dois lados da alma; U: dorso e face interna;
        # mesas por fora e por dentro) ou só uma
        faces = (
            2 if len({t.nome for t in do_elemento}) > 1 or (not e_u and elemento == "alma") else 1
        )
        local = max(
            (pt for pt in pontos if pt.elemento == elemento),
            key=lambda pt: math.hypot(pt.f_n / r_n, pt.f_v / (r_v * 1000)),
        )
        n_el, v_el = faces * local.f_n, faces * local.f_v
        razao = math.hypot(n_el / r_n, v_el / (r_v * 1000.0))
        k = "2·" if faces == 2 else ""
        texto = (
            f"na {elemento} (t = {_n(t_el, 1)} mm), "
            + ("dois filetes, um de cada face" if faces == 2 else "um filete, numa face só")
            + f": normal {k}f_n = "
            f"{_n(n_el / 1000, 3)} kN/mm frente a f_y·t/γ_a1 = {_n(r_n / 1000, 3)} kN/mm (escoamento "
            f"à tração) e cortante {k}f_v = {_n(v_el / 1000, 3)} kN/mm frente a {modo} = "
            f"{_n(r_v, 3)} kN/mm (6.5.5); √((n/R_n)² + (v/R_v)²) ≤ 1 (f_y = {_n(fy, 0)} MPa, "
            f"f_u = {_n(fu, 0)} MPa)"
        )
        if pior_mb is None or razao > pior_mb[0]:
            pior_mb = (razao, texto)
    assert pior_mb is not None
    linhas.append(
        Verificacao(
            "Solda do pilar na placa: metal-base do pilar",
            pior_mb[0],
            1.0,
            "—",
            _ref("6.5.5"),
            pior_mb[1],
        )
    )
    fy_p, fu_p = aco_placa
    r_vp, _ = sd.metal_base_ao_cisalhamento_por_mm(t_placa, fy_p, fu_p, c)
    uc = max(math.hypot(pt.f_n / (fy_p * t_placa / c.a1), pt.f_v / (1000 * r_vp)) for pt in pontos)
    linhas.append(
        Verificacao(
            "Solda do pilar na placa: metal-base da placa",
            uc,
            1.0,
            "—",
            _ref("6.5.5"),
            f"Maior interação normal/cisalhamento nos extremos dos filetes, placa de {_n(t_placa)} mm.",
        )
    )
    if any(t not in internos for t in descartados):
        linhas.append(
            Verificacao(
                "Solda do pilar na placa: trechos curtos excluídos",
                None,
                None,
                "mm",
                _ref("6.2.6.2.3"),
                ", ".join(t.nome for t in descartados),
                status="NÃO OK",
            )
        )
    tabela_perna = sd.tabela(sd.NBR_2025, "perna")
    linhas.append(
        Verificacao(
            "Solda do pilar na placa: perna mínima",
            minima,
            perna,
            "mm",
            f"{_ref('6.2.6.2.1')} ({tabela_perna})",
            f"d_w ≥ {_n(minima, 0)} mm pela parte menos espessa (mesa {_n(t_f, 1)}"
            + (f", alma {_n(t_w, 1)}" if alma or e_u else "")
            + f" e placa {_n(t_placa, 1)} mm). Mesa/placa: {_n(sd.perna_minima(min(t_f, t_placa)), 0)} mm"
            + (
                f", alma/placa: {_n(sd.perna_minima(min(t_w, t_placa)), 0)} mm"
                if alma or e_u
                else ""
            ),
            status="OK" if perna >= minima - 1e-9 else "NÃO OK",
            tipo="limite",
        )
    )
    linhas.append(
        Verificacao(
            "Solda do pilar na placa: perna máxima na ponta da mesa",
            perna,
            maxima,
            "mm",
            _ref("6.2.6.2.2"),
            f"o filete que contorna a ponta da mesa corre ao longo de uma borda de t_f = "
            f"{_n(t_f, 1)} mm: d_w ≤ {'t_f' if t_f < 6.3 else 't_f − 1,5 mm'} = {_n(maxima, 1)} mm",
            status="OK" if perna <= maxima + 1e-9 else "NÃO OK",
            tipo="limite",
        )
    )
    if internos:
        menor = min(t.comprimento for t in internos)
        minimo = sd.comprimento_minimo(perna)
        linhas.append(
            Verificacao(
                "Solda do pilar na placa: comprimento dos trechos internos da mesa",
                minimo,
                menor,
                "mm",
                _ref("6.2.6.2.3"),
                f"disponível: cada trecho entre a alma e a ponta da mesa tem {_n(menor, 1)} mm ("
                + ("b_f − t_w − r" if e_u else "b_f/2 − t_w/2 − r")
                + f", com o raio r estimado em t_f); exigido: máx(4·d_w; 40 mm) = "
                f"{_n(minimo, 0)} mm (o mínimo de 40 mm é da NBR; o AISC pede só 4·d_w); senão, "
                "solde só por fora das mesas",
                status="OK" if menor >= minimo - 1e-9 else "NÃO OK",
                tipo="limite",
            )
        )
    return SoldaDoPilar(perna, tuple(linhas))


# =============================================================================================
# Placa de cisalhamento e arruelas
# =============================================================================================
def solda_da_placa_de_cisalhamento(
    *,
    v_rd: float,
    momento: float,
    t_pv: float,
    b_h: float,
    t_placa: float,
    perna_informada: float,
    eletrodo: str,
    c: sd.Coeficientes,
    penetracao_total: bool = False,
) -> tuple[float, tuple[Verificacao, ...]]:
    """(perna, linhas) dos dois filetes da placa de cisalhamento (V_Rd e o momento, em N e N·mm).

    Com penetração total, a solda tem a resistência da própria placa de cisalhamento (já
    verificada pela t_pv,min) e dispensa a conta: uma linha informativa (perna 0).
    """
    if penetracao_total:
        return 0.0, (
            Verificacao(
                "Solda da placa de cisalhamento: penetração total",
                None,
                None,
                "—",
                f"NBR 8800:2025 6.7.2.4 e {_ref('6.2.5')}",
                "solda de penetração total com metal compatível: resiste como a própria placa de "
                f"cisalhamento (t_pv = {_n(t_pv, 1)} mm, já verificada), sem conta própria",
                "INFO",
                tipo="informativo",
            ),
        )
    f_w = sd.ELETRODOS[eletrodo]
    minima = sd.perna_minima(min(t_pv, t_placa))

    def forca(perna: float) -> tuple[float, float, float]:
        braco = t_pv + 2 * perna / 3
        f_n = momento / braco / b_h
        f_v = v_rd / (2 * b_h)
        return math.hypot(f_n, f_v), f_n, braco

    def passa(perna: float) -> bool:
        return forca(perna)[0] <= _resistencia_por_mm(perna, f_w, c) + 1e-9

    perna = perna_informada or _perna_automatica(passa, minima, PERNAS_COMERCIAIS[-1])
    resultante, f_n, braco = forca(perna)
    r_w = _resistencia_por_mm(perna, f_w, c)
    ref_p = f"NBR 8800:2025 6.7.2.4 e {_ref('6.2.5')}"
    linhas = (
        Verificacao(
            "Solda da placa de cisalhamento: filetes",
            resultante / 1000.0,
            r_w / 1000.0,
            "kN/mm",
            ref_p,
            f"dois filetes de {_n(b_h, 0)} mm, um de cada face: f_n = M/(braço·b_h) = "
            f"{_n(f_n / 1000, 3)} kN/mm (braço t_pv + 2·d_w/3 = {_n(braco, 1)} mm), f_v = "
            f"V_Rd/(2·b_h) = {_n(v_rd / (2 * b_h) / 1000, 3)} kN/mm, com V_Rd = "
            f"{_n(v_rd / 1000, 1)} kN e M = {_n(momento / 1e6, 2)} kN·m (a solda acompanha a "
            f"resistência da placa); F_w,Rd = 0,60·f_w·0,707·d_w/γ_w2 = {_n(r_w / 1000, 3)} kN/mm; "
            f"{_texto_perna(perna_informada, perna)}",
        ),
        Verificacao(
            "Solda da placa de cisalhamento: perna mínima",
            minima,
            perna,
            "mm",
            f"{_ref('6.2.6.2.1')} ({sd.tabela(sd.NBR_2025, 'perna')})",
            f"d_w ≥ {_n(minima, 0)} mm pela parte menos espessa (t_pv = {_n(t_pv, 1)} mm, "
            f"placa {_n(t_placa, 1)} mm)",
            status="OK" if perna >= minima - 1e-9 else "NÃO OK",
            tipo="limite",
        ),
    )
    return perna, linhas


def solda_das_arruelas(
    *,
    f_v: float,
    lado: float,
    t_arruela: float,
    t_placa: float,
    perna_informada: float,
    eletrodo: str,
    c: sd.Coeficientes,
) -> tuple[float, tuple[Verificacao, ...]]:
    """(perna, linhas) do filete no contorno de cada arruela soldada (F_v,Rd,i em N)."""
    f_w = sd.ELETRODOS[eletrodo]
    minima = sd.perna_minima(min(t_arruela, t_placa))
    maxima = sd.perna_maxima(t_arruela)
    comprimento = 4 * lado
    demanda = f_v / comprimento

    def passa(perna: float) -> bool:
        return demanda <= _resistencia_por_mm(perna, f_w, c) + 1e-9

    perna = perna_informada or _perna_automatica(passa, minima, maxima)
    r_w = _resistencia_por_mm(perna, f_w, c)
    linhas = (
        Verificacao(
            "Solda das arruelas na placa: filete no contorno",
            demanda / 1000.0,
            r_w / 1000.0,
            "kN/mm",
            f"NBR 8800:2025 6.7.2.5 e {_ref('6.2.5')}",
            f"F_v,Rd,i/(4·lado) = {_n(f_v / 1000, 1)} kN/(4 × {_n(lado, 0)} mm) = "
            f"{_n(demanda / 1000, 3)} kN/mm ≤ 0,60·f_w·0,707·d_w/γ_w2 = {_n(r_w / 1000, 3)} kN/mm "
            f"({eletrodo}); {_texto_perna(perna_informada, perna)}",
        ),
        Verificacao(
            "Solda das arruelas na placa: perna mínima",
            minima,
            perna,
            "mm",
            f"{_ref('6.2.6.2.1')} ({sd.tabela(sd.NBR_2025, 'perna')})",
            f"d_w ≥ {_n(minima, 0)} mm pela parte menos espessa (arruela {_n(t_arruela, 1)} mm, "
            f"placa {_n(t_placa, 1)} mm)",
            status="OK" if perna >= minima - 1e-9 else "NÃO OK",
            tipo="limite",
        ),
        Verificacao(
            "Solda das arruelas na placa: perna máxima na borda da arruela",
            perna,
            maxima,
            "mm",
            _ref("6.2.6.2.2"),
            f"o filete corre ao longo da borda da arruela de {_n(t_arruela, 1)} mm: d_w ≤ "
            f"{_n(maxima, 1)} mm",
            status="OK" if perna <= maxima + 1e-9 else "NÃO OK",
            tipo="limite",
        ),
    )
    return perna, linhas
