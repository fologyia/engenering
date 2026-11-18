"""Circuito fechado de fluido (resfriamento ou aquecimento): o desenho, a hidráulica e as peças.

O circuito é desenhado como uma rede: **nós** (pontos com cota) e **elementos** ligando dois nós
(trecho de tubo, bomba, fonte de calor, dry cooler, chiller, válvula, filtro, tanque). Pode ter
ramais em paralelo. Um nó leva o **vaso de expansão**, que fixa a pressão do circuito (num circuito
fechado, sem ele a pressão fica indefinida).

Hidráulica: em cada elemento, a energia (H_de − H_para + H_bomba(Q) = perda(Q)) e, em cada nó, a
continuidade; tudo resolvido junto pelo método de Newton nas vazões e nas cargas (o mesmo método da
Rede de tubos), com a carga do nó do vaso fixa. Perda nos tubos por Darcy-Weisbach (f do Montador de
fluidos: 64/Re no laminar, Colebrook no turbulento) mais ΣK; nas peças, pela perda de carga do
catálogo na vazão do catálogo (Δp ∝ Q²). Bomba pela curva H = s²·H₀ − (H₀/Q_máx²)·Q·|Q|.

A parte térmica fica em :mod:`core.circuito_termico`. Unidades: SI na conta; na entrada, mm, m³/h,
kPa, bar (manométrica), kW e °C, como nos catálogos.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from functools import cache
from typing import Any

import numpy as np

from core.montador_funcoes import fator_de_atrito

GRAVIDADE = 9.81
ATMOSFERA = 101325.0  # Pa

TUBO = "tubo"
BOMBA = "bomba"
FONTE = "fonte"
DRY_COOLER = "dry_cooler"
CHILLER = "chiller"
VALVULA = "valvula"
FILTRO = "filtro"
TANQUE = "tanque"
TIPOS = (TUBO, BOMBA, FONTE, DRY_COOLER, CHILLER, VALVULA, FILTRO, TANQUE)
NOMES = {
    TUBO: "Trecho de tubo",
    BOMBA: "Bomba",
    FONTE: "Fonte de calor",
    DRY_COOLER: "Dry cooler",
    CHILLER: "Chiller",
    VALVULA: "Válvula",
    FILTRO: "Filtro",
    TANQUE: "Tanque pulmão",
}
#: Peças cuja perda de carga vem do catálogo (Δp na vazão do catálogo).
COM_PERDA_DE_CATALOGO = (FONTE, DRY_COOLER, CHILLER, FILTRO)

SEMPRE = "sempre"
LIGA_DESLIGA = "liga_desliga"
PROPORCIONAL = "proporcional"
CONTROLES = (SEMPRE, LIGA_DESLIGA, PROPORCIONAL)

#: Fluidos do circuito (rótulo → nome na CoolProp). A pressão de vapor é a da água: nas misturas
#: com glicol ela é menor, e usar a da água fica a favor da segurança no NPSH.
FLUIDOS: dict[str, str] = {
    "Água": "Water",
    "Etilenoglicol a 30 % em água": "INCOMP::MEG-30%",
    "Etilenoglicol a 40 % em água": "INCOMP::MEG-40%",
    "Propilenoglicol a 30 % em água": "INCOMP::MPG-30%",
    "Propilenoglicol a 40 % em água": "INCOMP::MPG-40%",
}

_ITERACOES = 200
_LINEAR = 1e-4  # m de perda por m³/s: mantém a derivada positiva em vazão zero (ramal parado)


class ErroDoCircuito(ValueError):
    """O que impede a conta, em palavras de quem desenhou o circuito."""


def _n(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


# ---------------------------------------------------------------------------------------------
# Fluido
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Propriedades:
    massa_especifica: float  # kg/m³
    viscosidade: float  # Pa·s
    calor_especifico: float  # J/(kg·K)
    pressao_de_vapor: float  # Pa (da água)


@cache
def propriedades(fluido: str, temperatura: float) -> Propriedades:
    """Propriedades do fluido do circuito a 2 bar (CoolProp)."""
    import CoolProp.CoolProp as cp  # noqa: N813

    nome = FLUIDOS.get(fluido, fluido)
    t = min(max(temperatura, 1.0), 99.0) + 273.15
    p = 2.0e5
    rho = float(cp.PropsSI("D", "T", t, "P", p, nome))
    mu = float(cp.PropsSI("V", "T", t, "P", p, nome))
    c = float(cp.PropsSI("C", "T", t, "P", p, nome))
    pv = float(cp.PropsSI("P", "T", t, "Q", 0, "Water"))
    return Propriedades(rho, mu, c, pv)


# ---------------------------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Vaso:
    """Vaso de expansão com membrana: volume total, pré-carga do ar, pressão de enchimento a frio
    (no nó dele) e a pressão da válvula de segurança, em bar manométrico."""

    volume_L: float = 50.0
    precarga_bar: float = 1.0
    enchimento_bar: float = 1.5
    maxima_bar: float = 3.0


@dataclass(frozen=True, slots=True)
class No:
    id: str
    nome: str
    x: float = 0.0
    y: float = 0.0
    cota: float = 0.0  # m
    vaso: Vaso | None = None


@dataclass(frozen=True, slots=True)
class Elemento:
    """Um elemento entre dois nós. Os campos que não são do tipo ficam no padrão."""

    id: str
    nome: str
    tipo: str
    de: str  # id do nó
    para: str
    comprimento_m: float = 1.0  # tubo: o real ou o desenhado
    diametro_mm: float = 52.5  # tubo e diâmetro de ligação das peças
    rugosidade_mm: float = 0.045
    k_local: float = 0.0  # ΣK do tubo ou K da válvula
    perde_calor: bool = False  # tubo: troca com o ar
    isolamento_mm: float = 0.0
    k_isolamento: float = 0.04
    h_externo: float = 10.0
    # bomba
    h0_m: float = 30.0
    qmax_m3h: float = 40.0
    rendimento: float = 0.6
    npsh_requerido_m: float = 0.0
    ligada: bool = True
    # peças com perda de catálogo
    dp_kPa: float = 30.0
    q_nominal_m3h: float = 10.0
    volume_L: float = 20.0
    # fonte de calor
    potencia_kW: float = 50.0
    massa_kg: float = 0.0
    calor_especifico_massa: float = 500.0
    t_maxima: float = 45.0
    # dry cooler (ponto do catálogo) e controle do ventilador
    q_catalogo_kW: float = 60.0
    t_entrada_catalogo: float = 40.0
    t_ar_catalogo: float = 25.0
    vazao_liquido_catalogo_m3h: float = 10.0
    vazao_ar_catalogo_m3h: float = 30000.0
    potencia_ventilador_kW: float = 2.0
    controle: str = SEMPRE
    t_ajuste: float = 30.0  # °C: saída que o controle do ventilador ou o chiller segura
    # chiller
    capacidade_kW: float = 50.0
    cop: float = 3.5
    # tanque
    ua_W_K: float = 0.0

    @property
    def area(self) -> float:
        return math.pi * (self.diametro_mm / 1000.0) ** 2 / 4.0

    @property
    def volume_m3(self) -> float:
        if self.tipo == TUBO:
            return self.area * self.comprimento_m
        if self.tipo in (BOMBA, VALVULA, FILTRO):
            return max(self.volume_L, 0.0) / 1000.0 if self.tipo == FILTRO else 0.002
        return max(self.volume_L, 0.1) / 1000.0


@dataclass(frozen=True)
class Circuito:
    nos: tuple[No, ...]
    elementos: tuple[Elemento, ...]
    fluido: str = "Água"

    def no(self, id_: str) -> No:
        for n in self.nos:
            if n.id == id_:
                return n
        raise KeyError(id_)

    @property
    def vaso(self) -> No | None:
        return next((n for n in self.nos if n.vaso is not None), None)

    @property
    def volume_m3(self) -> float:
        return float(sum(e.volume_m3 for e in self.elementos))


# ---------------------------------------------------------------------------------------------
# Conferência
# ---------------------------------------------------------------------------------------------
def problemas(c: Circuito) -> list[str]:
    erros: list[str] = []
    ids = {n.id for n in c.nos}
    if not c.elementos:
        return ["Desenhe o circuito: trechos de tubo e as peças em cima deles."]
    for e in c.elementos:
        if e.tipo not in TIPOS:
            erros.append(f"{e.nome}: tipo de peça desconhecido.")
        if e.de not in ids or e.para not in ids:
            erros.append(f"{e.nome}: está ligado a um ponto que não existe.")
        elif e.de == e.para:
            erros.append(f"{e.nome}: começa e termina no mesmo ponto.")
        if e.tipo == TUBO:
            if not e.diametro_mm > 0:
                erros.append(f"{e.nome}: informe o diâmetro interno do tubo.")
            if not e.comprimento_m > 0:
                erros.append(f"{e.nome}: o tubo tem comprimento zero; afaste os pontos.")
        if e.tipo == BOMBA and (not e.h0_m > 0 or not e.qmax_m3h > 0):
            erros.append(f"{e.nome}: informe a altura com vazão zero e a vazão com altura zero.")
        if e.tipo in COM_PERDA_DE_CATALOGO and (e.dp_kPa < 0 or not e.q_nominal_m3h > 0):
            erros.append(
                f"{e.nome}: informe a perda de carga do catálogo e a vazão em que ela vale."
            )
        if e.tipo == DRY_COOLER and (
            not e.q_catalogo_kW > 0
            or not e.vazao_ar_catalogo_m3h > 0
            or not e.vazao_liquido_catalogo_m3h > 0
            or not e.t_entrada_catalogo > e.t_ar_catalogo
        ):
            erros.append(
                f"{e.nome}: informe o ponto do catálogo (capacidade, vazões de líquido e de ar e a "
                "entrada do líquido mais quente que o ar)."
            )
        if e.tipo == CHILLER and (not e.capacidade_kW > 0 or not e.cop > 0):
            erros.append(f"{e.nome}: informe a capacidade e o COP do catálogo.")
    vasos = [n for n in c.nos if n.vaso is not None]
    if not vasos:
        erros.append(
            "Ponha o vaso de expansão num ponto do circuito: num circuito fechado é ele que fixa "
            "a pressão, e sem ele a pressão fica indefinida."
        )
    elif len(vasos) > 1:
        erros.append(
            "Use um vaso de expansão só: dois vasos no mesmo circuito brigam pela pressão."
        )
    else:
        v = vasos[0].vaso
        assert v is not None
        if not v.volume_L > 0:
            erros.append("Informe o volume do vaso de expansão.")
        if not v.precarga_bar < v.enchimento_bar < v.maxima_bar:
            erros.append(
                "No vaso: a pré-carga precisa ficar abaixo da pressão de enchimento, e esta abaixo "
                "da pressão da válvula de segurança."
            )
    if not any(e.tipo == BOMBA and e.ligada for e in c.elementos):
        erros.append("Ponha ao menos uma bomba ligada: sem ela a água não circula.")
    if not erros:
        soltos = _pontos_soltos(c)
        if soltos:
            erros.append(
                "O circuito não está todo ligado: estes pontos não chegam ao resto: "
                + ", ".join(soltos)
                + "."
            )
    return erros


def _pontos_soltos(c: Circuito) -> list[str]:
    vizinhos: dict[str, set[str]] = {n.id: set() for n in c.nos}
    for e in c.elementos:
        vizinhos[e.de].add(e.para)
        vizinhos[e.para].add(e.de)
    usados = {n.id for n in c.nos if vizinhos[n.id]}
    if not usados:
        return []
    inicio = next(iter(usados))
    vistos = {inicio}
    pilha = [inicio]
    while pilha:
        atual = pilha.pop()
        for v in vizinhos[atual]:
            if v not in vistos:
                vistos.add(v)
                pilha.append(v)
    return [n.nome for n in c.nos if n.id in usados and n.id not in vistos]


def sem_volta(c: Circuito) -> list[str]:
    """Elementos que não estão em nenhuma volta (ramal sem saída): ali a água fica parada."""
    restantes = list(c.elementos)
    mudou = True
    while mudou:
        mudou = False
        grau: dict[str, int] = {}
        for e in restantes:
            grau[e.de] = grau.get(e.de, 0) + 1
            grau[e.para] = grau.get(e.para, 0) + 1
        novos = [e for e in restantes if grau[e.de] > 1 and grau[e.para] > 1]
        if len(novos) != len(restantes):
            restantes = novos
            mudou = True
    dentro = {e.id for e in restantes}
    return [e.nome for e in c.elementos if e.id not in dentro]


# ---------------------------------------------------------------------------------------------
# Hidráulica
# ---------------------------------------------------------------------------------------------
def perda(e: Elemento, q: float, p: Propriedades) -> tuple[float, float]:
    """Perda de carga (m) e a derivada em relação a Q (m por m³/s), no sentido de → para."""
    linear = _LINEAR * q
    if e.tipo == TUBO:
        d = e.diametro_mm / 1000.0
        v = q / e.area
        re = p.massa_especifica * abs(v) * d / p.viscosidade
        if re < 1.0:
            # Hagen-Poiseuille: h = 32·μ·L·v/(ρ·g·D²), reta na vazão
            r = (
                32.0
                * p.viscosidade
                * e.comprimento_m
                / (p.massa_especifica * GRAVIDADE * d * d)
                / e.area
            )
            return r * q + linear, r + _LINEAR
        f = float(fator_de_atrito(re, e.rugosidade_mm / e.diametro_mm))
        coef = (f * e.comprimento_m / d + e.k_local) / (2.0 * GRAVIDADE * e.area**2)
        h = coef * q * abs(q)
        # derivada numérica: f muda com Re
        dq = max(abs(q) * 1e-6, 1e-10)
        re2 = p.massa_especifica * abs(q + dq) / e.area * d / p.viscosidade
        f2 = float(fator_de_atrito(max(re2, 1.0), e.rugosidade_mm / e.diametro_mm))
        h2 = (
            (f2 * e.comprimento_m / d + e.k_local)
            / (2.0 * GRAVIDADE * e.area**2)
            * (q + dq)
            * abs(q + dq)
        )
        return h + linear, (h2 - h) / dq + _LINEAR
    if e.tipo in COM_PERDA_DE_CATALOGO:
        qn = e.q_nominal_m3h / 3600.0
        hn = e.dp_kPa * 1000.0 / (p.massa_especifica * GRAVIDADE)
        r = hn / (qn * qn)
        return r * q * abs(q) + linear, 2.0 * r * abs(q) + _LINEAR
    if e.tipo == VALVULA:
        r = e.k_local / (2.0 * GRAVIDADE * e.area**2)
        return r * q * abs(q) + linear, 2.0 * r * abs(q) + _LINEAR
    if e.tipo == TANQUE:
        r = 1.0 / (2.0 * GRAVIDADE * e.area**2)  # uma altura de velocidade na entrada
        return r * q * abs(q) + linear, 2.0 * r * abs(q) + _LINEAR
    if e.tipo == BOMBA and not e.ligada:
        r = 1e7  # bomba parada com retenção: a água não passa
        return r * q, r
    return linear, _LINEAR


def altura_da_bomba(e: Elemento, q: float, rotacao: float = 1.0) -> tuple[float, float]:
    """H = s²·H₀ − (H₀/Q_máx²)·Q·|Q| (m) e a derivada; zero se não é bomba ou está parada."""
    if e.tipo != BOMBA or not e.ligada:
        return 0.0, 0.0
    qmax = e.qmax_m3h / 3600.0
    a = e.h0_m / (qmax * qmax)
    return e.h0_m * rotacao * rotacao - a * q * abs(q), -2.0 * a * abs(q)


@dataclass(frozen=True)
class Hidraulica:
    vazoes: dict[str, float]  # id do elemento → m³/s (positiva de → para)
    cargas: dict[str, float]  # id do nó → carga H (m)
    pressoes: dict[str, float]  # id do nó → pressão manométrica (Pa)
    iteracoes: int
    avisos: tuple[str, ...] = field(default_factory=tuple)

    def vazao_m3h(self, id_: str) -> float:
        return self.vazoes[id_] * 3600.0

    def pressao_bar(self, id_: str) -> float:
        return self.pressoes[id_] / 1e5


def resolver_hidraulica(
    c: Circuito, temperatura: float = 20.0, pressao_do_vaso_bar: float | None = None
) -> Hidraulica:
    """Vazões e pressões com o fluido na temperatura dada e o vaso na pressão dada (bar man.; por
    padrão, a de enchimento a frio)."""
    erros = problemas(c)
    if erros:
        raise ErroDoCircuito(" ".join(erros))
    p = propriedades(c.fluido, temperatura)
    vaso = c.vaso
    assert vaso is not None and vaso.vaso is not None
    pv = vaso.vaso.enchimento_bar if pressao_do_vaso_bar is None else pressao_do_vaso_bar
    carga_fixa = vaso.cota + pv * 1e5 / (p.massa_especifica * GRAVIDADE)
    livres = [n.id for n in c.nos if n.id != vaso.id and _ligado(c, n.id)]
    indice = {id_: i for i, id_ in enumerate(livres)}
    m, k = len(c.elementos), len(livres)
    # chute: 1 m/s no sentido do desenho nos elementos que estão numa volta
    parados = set(sem_volta(c))
    q = np.array([0.0 if e.nome in parados else e.area * 1.0 for e in c.elementos])
    h = np.full(k, carga_fixa)

    def carga(id_: str, hv: np.ndarray) -> float:
        return carga_fixa if id_ not in indice else float(hv[indice[id_]])

    def residuos(qv: np.ndarray, hv: np.ndarray) -> np.ndarray:
        r = np.zeros(m + k)
        for i, e in enumerate(c.elementos):
            hb, _ = altura_da_bomba(e, qv[i])
            r[i] = carga(e.de, hv) - carga(e.para, hv) + hb - perda(e, qv[i], p)[0]
            if e.para in indice:
                r[m + indice[e.para]] += qv[i]
            if e.de in indice:
                r[m + indice[e.de]] -= qv[i]
        return r

    def norma(r: np.ndarray) -> float:
        return max(float(np.max(np.abs(r[:m]))), float(np.max(np.abs(r[m:]), initial=0.0)) * 1e3)

    atual = residuos(q, h)
    iteracoes = 0
    for volta in range(1, _ITERACOES + 1):
        iteracoes = volta
        jac = np.zeros((m + k, m + k))
        for i, e in enumerate(c.elementos):
            _, dhb = altura_da_bomba(e, q[i])
            jac[i, i] = dhb - perda(e, q[i], p)[1]
            if e.de in indice:
                jac[i, m + indice[e.de]] = 1.0
                jac[m + indice[e.de], i] = -1.0
            if e.para in indice:
                jac[i, m + indice[e.para]] = -1.0
                jac[m + indice[e.para], i] = 1.0
        try:
            passo = np.linalg.solve(jac, -atual)
        except np.linalg.LinAlgError as erro:
            raise ErroDoCircuito(
                "A hidráulica não tem solução única: confira se há ponto ligado só por uma bomba "
                "parada ou trecho fechado."
            ) from erro
        fator = 1.0
        for _ in range(40):
            q_novo, h_novo = q + fator * passo[:m], h + fator * passo[m:]
            novo = residuos(q_novo, h_novo)
            if norma(novo) < norma(atual) or fator < 1e-7:
                break
            fator /= 2.0
        q, h, atual = q_novo, h_novo, novo
        if np.max(np.abs(fator * passo[:m])) < 1e-11 and np.max(np.abs(atual[:m])) < 1e-8:
            break
    else:
        raise ErroDoCircuito(
            "A hidráulica não convergiu: confira as bombas (altura e vazão) e os diâmetros."
        )
    cargas = {n.id: carga(n.id, h) for n in c.nos if _ligado(c, n.id)}
    pressoes = {
        id_: (hv - c.no(id_).cota) * p.massa_especifica * GRAVIDADE for id_, hv in cargas.items()
    }
    vazoes = {e.id: float(q[i]) for i, e in enumerate(c.elementos)}
    avisos: list[str] = []
    for e in c.elementos:
        if e.tipo == BOMBA and e.ligada and vazoes[e.id] < -1e-9:
            avisos.append(
                f"A água atravessa a {e.nome} ao contrário: ponha uma válvula de retenção ou "
                "confira o sentido da bomba."
            )
    if parados:
        avisos.append(
            "Trechos que não fecham volta (a água fica parada neles): "
            + ", ".join(sorted(parados))
            + "."
        )
    return Hidraulica(vazoes, cargas, pressoes, iteracoes, tuple(avisos))


def _ligado(c: Circuito, id_: str) -> bool:
    return any(e.de == id_ or e.para == id_ for e in c.elementos)


# ---------------------------------------------------------------------------------------------
# O circuito desenhado na prancheta
# ---------------------------------------------------------------------------------------------
OUTRO_MATERIAL = "Outro"


def _numero(valor: Any, padrao: float) -> float:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return padrao
    return v if math.isfinite(v) else padrao


def comprimento_desenhado(desenho: Mapping[str, Any], trecho: Mapping[str, Any]) -> float:
    pos = {
        str(n.get("id")): (float(n.get("x") or 0.0), float(n.get("y") or 0.0))
        for n in desenho.get("nos") or ()
    }
    a, b = pos.get(str(trecho.get("de"))), pos.get(str(trecho.get("para")))
    if a is None or b is None:
        return 0.0
    return math.hypot(b[0] - a[0], b[1] - a[1])


_CAMPOS = {f.name: f for f in Elemento.__dataclass_fields__.values()}


def circuito_do_desenho(
    desenho: Mapping[str, Any], rugosidades: Mapping[str, float], fluido: str = "Água"
) -> Circuito:
    """Os nós e os elementos da conta a partir do desenho (dicionários da prancheta)."""
    nos: list[No] = []
    for bruto in desenho.get("nos") or ():
        vaso = None
        if bruto.get("vaso"):
            vaso = Vaso(
                _numero(bruto.get("vaso_volume_L"), 50.0),
                _numero(bruto.get("vaso_precarga_bar"), 1.0),
                _numero(bruto.get("vaso_enchimento_bar"), 1.5),
                _numero(bruto.get("vaso_maxima_bar"), 3.0),
            )
        nos.append(
            No(
                str(bruto.get("id")),
                str(bruto.get("nome") or bruto.get("id")),
                _numero(bruto.get("x"), 0.0),
                _numero(bruto.get("y"), 0.0),
                _numero(bruto.get("cota"), 0.0),
                vaso,
            )
        )
    elementos: list[Elemento] = []
    padrao = Elemento("", "", TUBO, "", "")
    for bruto in desenho.get("trechos") or ():
        tipo = str(bruto.get("tipo") or TUBO)
        valores: dict[str, Any] = {}
        for nome in _CAMPOS:
            if (
                nome in ("id", "nome", "tipo", "de", "para")
                or nome not in bruto
                or bruto[nome] is None
            ):
                continue
            atual = getattr(padrao, nome)
            if isinstance(atual, bool):
                valores[nome] = bool(bruto[nome])
            elif isinstance(atual, str):
                valores[nome] = str(bruto[nome])
            else:
                valores[nome] = _numero(bruto[nome], float(atual))
        if tipo == TUBO:
            material = str(bruto.get("material") or "Aço comercial")
            if material in rugosidades:
                valores["rugosidade_mm"] = rugosidades[material] * 1000.0
            real = bruto.get("comprimento")
            valores["comprimento_m"] = (
                _numero(real, 0.0)
                if real not in (None, "") and _numero(real, 0.0) > 0
                else comprimento_desenhado(desenho, bruto)
            )
        elementos.append(
            replace(
                padrao,
                id=str(bruto.get("id")),
                nome=str(bruto.get("nome") or bruto.get("id")),
                tipo=tipo,
                de=str(bruto.get("de")),
                para=str(bruto.get("para")),
                **valores,
            )
        )
    return Circuito(tuple(nos), tuple(elementos), fluido)


def _no(id_: str, nome: str, x: float, y: float, cota: float = 0.0, **extra: Any) -> dict[str, Any]:
    return {"id": id_, "nome": nome, "x": x, "y": y, "cota": cota, **extra}


def _peca(id_: str, nome: str, tipo: str, de: str, para: str, **dados: Any) -> dict[str, Any]:
    return {"id": id_, "nome": nome, "tipo": tipo, "de": de, "para": para, **dados}


def exemplo_desenhado() -> dict[str, Any]:
    """Duas máquinas em paralelo resfriadas por um dry cooler, com bomba, filtro e vaso.

    Valores de exemplo (ilustrativos): troque pelos do seu projeto e dos catálogos."""
    tubo = {"diametro_mm": 52.5, "material": "Aço comercial", "k_local": 1.5}
    ramal = {"diametro_mm": 40.9, "material": "Aço comercial", "k_local": 2.0}
    return {
        "nos": [
            _no(
                "n1",
                "A",
                0.0,
                0.0,
                vaso=True,
                vaso_volume_L=35.0,
                vaso_precarga_bar=1.0,
                vaso_enchimento_bar=1.5,
                vaso_maxima_bar=3.0,
            ),
            _no("n2", "B", 6.0, 0.0),
            _no("n3", "C", 10.0, 0.0),
            _no("n4", "D", 14.0, 4.0),
            _no("n5", "E", 18.0, 4.0),
            _no("n6", "F", 14.0, -4.0),
            _no("n7", "G", 18.0, -4.0),
            _no("n8", "H", 22.0, 0.0),
            _no("n9", "I", 22.0, 10.0, cota=6.0),
            _no("n10", "J", 10.0, 10.0, cota=6.0),
            _no("n11", "K", 4.0, 10.0, cota=6.0),
            _no("n12", "L", 0.0, 6.0),
        ],
        "trechos": [
            _peca(
                "t1",
                "Bomba 1",
                BOMBA,
                "n1",
                "n2",
                h0_m=28.0,
                qmax_m3h=35.0,
                rendimento=0.6,
                npsh_requerido_m=3.0,
            ),
            _peca("t2", "1", TUBO, "n2", "n3", **tubo),
            _peca("t3", "2", TUBO, "n3", "n4", **ramal),
            _peca(
                "t4",
                "Máquina 1",
                FONTE,
                "n4",
                "n5",
                potencia_kW=40.0,
                massa_kg=300.0,
                volume_L=15.0,
                dp_kPa=25.0,
                q_nominal_m3h=6.0,
                t_maxima=45.0,
            ),
            _peca("t5", "3", TUBO, "n5", "n8", **ramal),
            _peca("t6", "4", TUBO, "n3", "n6", **ramal),
            _peca(
                "t7",
                "Máquina 2",
                FONTE,
                "n6",
                "n7",
                potencia_kW=25.0,
                massa_kg=200.0,
                volume_L=10.0,
                dp_kPa=20.0,
                q_nominal_m3h=4.0,
                t_maxima=45.0,
            ),
            _peca("t8", "5", TUBO, "n7", "n8", **ramal),
            _peca("t9", "6", TUBO, "n8", "n9", **tubo),
            _peca(
                "t10",
                "Dry cooler",
                DRY_COOLER,
                "n9",
                "n10",
                q_catalogo_kW=80.0,
                t_entrada_catalogo=40.0,
                t_ar_catalogo=30.0,
                vazao_liquido_catalogo_m3h=12.0,
                vazao_ar_catalogo_m3h=36000.0,
                potencia_ventilador_kW=2.2,
                volume_L=40.0,
                dp_kPa=35.0,
                q_nominal_m3h=12.0,
                controle=PROPORCIONAL,
                t_ajuste=35.0,
            ),  # fmt: skip
            _peca("t11", "7", TUBO, "n10", "n11", **tubo),
            _peca(
                "t12", "Filtro", FILTRO, "n11", "n12", dp_kPa=8.0, q_nominal_m3h=12.0, volume_L=5.0
            ),
            _peca("t13", "8", TUBO, "n12", "n1", **tubo),
        ],
    }
