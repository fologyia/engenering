"""A parte térmica do circuito fechado: as peças, o regime permanente e a conta no tempo.

**Peças.** Fonte de calor: põe a potência no fluido, com a massa dela (aço do equipamento) e o
fluido de dentro esquentando juntos. Dry cooler: troca com o ar pelo ε-NTU de fluxo cruzado (os dois
lados não misturados, Incropera eq. 11.33); o UA sai do ponto do catálogo do fabricante (capacidade,
vazões de líquido e de ar e as temperaturas de entrada), e com o ventilador mais lento o lado do ar
manda: C_ar ∝ rotação e UA ∝ rotação^0,6. Chiller: tira o calor que for preciso para a saída ficar
na temperatura ajustada, até a capacidade do catálogo, com a potência elétrica pelo COP. Tubo: perda
para o ar pelo isolamento e pela película de fora, se marcada. Tanque pulmão: volume bem misturado.

**Regime permanente.** Com as vazões da hidráulica, cada elemento leva a temperatura da entrada
à da saída por uma reta, T_s = a·T_e + b (exata para o tubo, a fonte e o dry cooler numa rotação
fixa); nos nós, a mistura pela vazão. Fica um sistema linear nas temperaturas dos nós, resolvido de
uma vez; o chiller (ajuste ou limite) e a rotação dos ventiladores são acertados por iteração.

**No tempo.** Cada tubo vira células que o fluido atravessa (transporte), cada peça um volume bem
misturado, e os nós a mistura; implícito no tempo (Euler), com as fontes, o dry cooler e o chiller
explícitos. O vaso de expansão recebe a dilatação do fluido: o ar do vaso se comprime à temperatura
constante, p·V = constante.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache

import numpy as np
from scipy import optimize, sparse
from scipy.sparse import linalg as splinalg

from core import circuito as ci
from core.calor_no_tempo import TOLERANCIA, primeiro_abaixo_de_vez

EXPOENTE_DO_AR = 0.6
CALOR_ESPECIFICO_DO_AR = 1006.0  # J/(kg·K)


class ErroTermico(ValueError):
    """O que impede a conta térmica, em palavras simples."""


# ---------------------------------------------------------------------------------------------
# Dry cooler e chiller
# ---------------------------------------------------------------------------------------------
@cache
def massa_especifica_do_ar(temperatura: float) -> float:
    import CoolProp.CoolProp as cp  # noqa: N813

    return float(cp.PropsSI("D", "T", temperatura + 273.15, "P", ci.ATMOSFERA, "Air"))


def eficacia_cruzada(ntu: float, razao: float) -> float:
    """ε do trocador de fluxo cruzado com os dois fluidos não misturados (Incropera eq. 11.33)."""
    if ntu <= 0:
        return 0.0
    if razao < 1e-9:
        return 1.0 - math.exp(-ntu)
    return 1.0 - math.exp((1.0 / razao) * ntu**0.22 * (math.exp(-razao * ntu**0.78) - 1.0))


@dataclass(frozen=True, slots=True)
class DryCooler:
    ua: float  # W/K com o ventilador em 100 %
    c_ar: float  # W/K com o ventilador em 100 %
    eficacia_do_catalogo: float

    def calor(self, c_liquido: float, t_entrada: float, t_ar: float, rotacao: float = 1.0) -> float:
        """Calor tirado do líquido (W; negativo se o ar está mais quente que o líquido)."""
        if rotacao <= 0 or c_liquido <= 0:
            return 0.0
        c_ar = self.c_ar * rotacao
        ua = self.ua * rotacao**EXPOENTE_DO_AR
        c_min, c_max = min(c_ar, c_liquido), max(c_ar, c_liquido)
        return eficacia_cruzada(ua / c_min, c_min / c_max) * c_min * (t_entrada - t_ar)

    def rotacao_para(
        self, c_liquido: float, t_entrada: float, t_ar: float, t_saida: float
    ) -> float:
        """Rotação (0 a 1) que deixa a saída na temperatura pedida; 1 se nem em 100 % chega."""
        pedido = c_liquido * (t_entrada - t_saida)
        if pedido <= 0:
            return 0.0
        if self.calor(c_liquido, t_entrada, t_ar, 1.0) <= pedido:
            return 1.0
        return float(
            optimize.brentq(
                lambda s: self.calor(c_liquido, t_entrada, t_ar, s) - pedido, 1e-6, 1.0, xtol=1e-10
            )
        )


def dry_cooler(e: ci.Elemento, fluido: str) -> DryCooler:
    """UA do dry cooler pelo ponto do catálogo (ε-NTU de fluxo cruzado)."""
    p = ci.propriedades(fluido, 0.5 * (e.t_entrada_catalogo + e.t_ar_catalogo))
    c_liq = p.massa_especifica * e.vazao_liquido_catalogo_m3h / 3600.0 * p.calor_especifico
    c_ar = (
        massa_especifica_do_ar(e.t_ar_catalogo)
        * e.vazao_ar_catalogo_m3h
        / 3600.0
        * CALOR_ESPECIFICO_DO_AR
    )
    c_min, c_max = min(c_liq, c_ar), max(c_liq, c_ar)
    eps = e.q_catalogo_kW * 1000.0 / (c_min * (e.t_entrada_catalogo - e.t_ar_catalogo))
    limite = eficacia_cruzada(60.0, c_min / c_max)
    if not 0 < eps < limite:
        raise ErroTermico(
            f"{e.nome}: o ponto do catálogo pede eficácia de {eps:.2f}, impossível com essas vazões "
            "(o máximo é perto de 1). Confira a capacidade, as vazões e as temperaturas do catálogo."
        )
    ntu = float(
        optimize.brentq(lambda n: eficacia_cruzada(n, c_min / c_max) - eps, 1e-9, 60.0, xtol=1e-12)
    )
    return DryCooler(ntu * c_min, c_ar, eps)


def calor_do_chiller(e: ci.Elemento, c_liquido: float, t_entrada: float) -> float:
    """Calor tirado pelo chiller (W): o que leva a saída ao ajuste, até a capacidade."""
    return min(max(c_liquido * (t_entrada - e.t_ajuste), 0.0), e.capacidade_kW * 1000.0)


def condutancia_do_tubo(e: ci.Elemento) -> float:
    """UA do tubo para o ar (W/K): isolamento e película de fora (parede metálica desprezada)."""
    if e.tipo == ci.TANQUE:
        return max(e.ua_W_K, 0.0)
    if e.tipo != ci.TUBO or not e.perde_calor or e.h_externo <= 0:
        return 0.0
    r_e = e.diametro_mm / 2000.0
    r_iso = r_e + max(e.isolamento_mm, 0.0) / 1000.0
    resistencia = 1.0 / (2.0 * math.pi * r_iso * e.h_externo)
    if e.isolamento_mm > 0 and e.k_isolamento > 0:
        resistencia += math.log(r_iso / r_e) / (2.0 * math.pi * e.k_isolamento)
    return e.comprimento_m / resistencia


# ---------------------------------------------------------------------------------------------
# Condições
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Condicoes:
    t_ar: float = 30.0  # °C: ar do dry cooler e em volta dos tubos
    t_inicial: float = 25.0  # °C: o circuito todo no instante zero (e no enchimento)
    perfil_ar: tuple[float, ...] = ()  # 24 temperaturas do ar, uma por hora (vazio: constante)
    perfil_carga: tuple[float, ...] = ()  # 24 multiplicadores da potência das fontes
    pressao_minima_bar: float = 0.0  # a menor pressão manométrica aceita nos pontos
    velocidade_maxima: float = 3.0  # m/s nos tubos

    def ar(self, t: float) -> float:
        return (
            self.perfil_ar[int(t // 3600.0) % len(self.perfil_ar)] if self.perfil_ar else self.t_ar
        )

    def carga(self, t: float) -> float:
        return (
            self.perfil_carga[int(t // 3600.0) % len(self.perfil_carga)]
            if self.perfil_carga
            else 1.0
        )


# ---------------------------------------------------------------------------------------------
# Regime permanente
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Regime:
    temperaturas: dict[str, float]  # nó → °C (nós sem vazão ficam fora)
    entradas: dict[str, float]  # elemento → °C
    saidas: dict[str, float]
    calores: dict[str, float]  # elemento → W para o fluido (negativo: tira)
    rotacoes: dict[str, float]  # dry cooler → 0 a 1
    chiller_no_limite: tuple[str, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)


def _sentido(c: ci.Circuito, h: ci.Hidraulica) -> list[tuple[ci.Elemento, str, str, float]]:
    """(elemento, nó de entrada, nó de saída, vazão em módulo) dos elementos com vazão."""
    saida = []
    for e in c.elementos:
        q = h.vazoes[e.id]
        if abs(q) < 1e-9:
            continue
        saida.append((e, e.de, e.para, q) if q > 0 else (e, e.para, e.de, -q))
    return saida


def _mapa(
    e: ci.Elemento,
    t_in: float,
    cap: float,
    t_ar: float,
    carga: float,
    coolers: dict[str, DryCooler],
) -> tuple[float, float, float]:
    """A temperatura na saída do elemento, a derivada em relação à da entrada e a rotação do
    ventilador (dry cooler), com o controle ideal. Contínuas e crescentes: o Newton anda bem."""
    if e.tipo == ci.FONTE:
        return t_in + e.potencia_kW * 1000.0 * carga / cap, 1.0, 0.0
    if e.tipo == ci.DRY_COOLER:
        dc = coolers[e.id]
        fator = dc.calor(cap, 1.0, 0.0, 1.0) / cap  # ε·C_min/C em 100 %
        livre = t_in - fator * (t_in - t_ar)
        if e.controle == ci.SEMPRE:
            return livre, 1.0 - fator, 1.0
        if t_in <= e.t_ajuste:
            return t_in, 1.0, 0.0  # já chega abaixo do ajuste: ventilador parado
        if livre >= e.t_ajuste:
            return livre, 1.0 - fator, 1.0  # nem em 100 % chega ao ajuste
        return e.t_ajuste, 0.0, dc.rotacao_para(cap, t_in, t_ar, e.t_ajuste)
    if e.tipo == ci.CHILLER:
        if t_in <= e.t_ajuste:
            return t_in, 1.0, 0.0
        limite = t_in - e.capacidade_kW * 1000.0 / cap
        if limite > e.t_ajuste:
            return limite, 1.0, 1.0  # na capacidade máxima
        return e.t_ajuste, 0.0, 0.0
    ua = condutancia_do_tubo(e)
    fator = math.exp(-ua / cap) if ua > 0 else 1.0
    return t_ar + (t_in - t_ar) * fator, fator, 0.0


def regime_permanente(
    c: ci.Circuito,
    h: ci.Hidraulica,
    t_ar: float,
    *,
    carga: float = 1.0,
    temperatura_media: float | None = None,
) -> Regime:
    """Temperaturas em regime pelo método de Newton (amortecido) nas temperaturas dos nós: em cada
    nó, a mistura do que chega; em cada elemento, a curva dele (com o controle do ventilador e do
    chiller, que satura). Fecha com o balanço de energia: o que as fontes põem, as peças tiram."""
    p = ci.propriedades(
        c.fluido, temperatura_media if temperatura_media is not None else t_ar + 5.0
    )
    caminhos = _sentido(c, h)
    nos = sorted({u for _, u, _, _ in caminhos} | {d for _, _, d, _ in caminhos})
    indice = {n: i for i, n in enumerate(nos)}
    coolers = {e.id: dry_cooler(e, c.fluido) for e, *_ in caminhos if e.tipo == ci.DRY_COOLER}
    massa = {e.id: p.massa_especifica * q for e, _, _, q in caminhos}
    cap = {e.id: massa[e.id] * p.calor_especifico for e, *_ in caminhos}
    total = np.zeros(len(nos))
    for e, _, d, _ in caminhos:
        total[indice[d]] += massa[e.id]

    def residuo(temps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        r = -total * temps
        jac = np.diag(-total)
        for e, u, d, _ in caminhos:
            saida, inclinacao, _ = _mapa(
                e, float(temps[indice[u]]), cap[e.id], t_ar, carga, coolers
            )
            r[indice[d]] += massa[e.id] * saida
            jac[indice[d], indice[u]] += massa[e.id] * inclinacao
        return r, jac

    temps = np.full(len(nos), float(t_ar))
    escala = float(total.sum()) or 1.0
    r, jac = residuo(temps)
    for _ in range(200):
        passo = None
        for fuga in (0.0, 1e-6, 1e-3):
            try:
                tentativa = np.linalg.solve(jac - fuga * np.diag(total), -r)
            except np.linalg.LinAlgError:
                continue
            if np.all(np.isfinite(tentativa)) and np.max(np.abs(tentativa)) < 1e6:
                passo = tentativa
                break
        if passo is None:
            raise ErroTermico(_sem_regime(c, caminhos))
        norma = float(np.max(np.abs(r)))
        fator = 1.0
        while True:
            novas = temps + fator * passo
            r_novo, jac_novo = residuo(novas)
            if float(np.max(np.abs(r_novo))) < norma or fator < 1e-6:
                break
            fator /= 2.0
        temps, r, jac = novas, r_novo, jac_novo
        if float(np.max(np.abs(r))) < 1e-9 * escala:
            break
    if float(np.max(np.abs(r))) > 1e-5 * escala or not all(-80.0 < t < 400.0 for t in temps):
        raise ErroTermico(_sem_regime(c, caminhos))
    entradas, saidas, calores, rotacoes = {}, {}, {}, {id_: 1.0 for id_ in coolers}
    limite: list[str] = []
    for e, u, _, _ in caminhos:
        t_in = float(temps[indice[u]])
        saida, inclinacao, rotacao = _mapa(e, t_in, cap[e.id], t_ar, carga, coolers)
        entradas[e.id], saidas[e.id] = t_in, saida
        calores[e.id] = cap[e.id] * (saida - t_in)
        if e.tipo == ci.DRY_COOLER:
            rotacoes[e.id] = rotacao
        if e.tipo == ci.CHILLER and rotacao == 1.0 and inclinacao == 1.0:
            limite.append(e.nome)
    avisos = [
        f"O {nome} trabalha na capacidade máxima e não chega à temperatura ajustada."
        for nome in limite
    ]
    return Regime(
        {n: float(temps[indice[n]]) for n in nos},
        entradas,
        saidas,
        calores,
        rotacoes,
        tuple(limite),
        tuple(avisos),
    )


def _sem_regime(c: ci.Circuito, caminhos: Sequence[tuple[ci.Elemento, str, str, float]]) -> str:
    entra = sum(e.potencia_kW for e, *_ in caminhos if e.tipo == ci.FONTE)
    tira = [
        e
        for e, *_ in caminhos
        if e.tipo in (ci.DRY_COOLER, ci.CHILLER) or condutancia_do_tubo(e) > 0
    ]
    if entra > 0 and not tira:
        return (
            "Não há regime permanente: o calor das fontes entra e não tem por onde sair. Ponha um "
            "dry cooler, um chiller ou deixe os tubos perderem calor para o ar."
        )
    return "Não há regime permanente: confira as peças que tiram e põem calor no circuito."


# ---------------------------------------------------------------------------------------------
# Vaso de expansão
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class EstadoDoVaso:
    dilatacao_L: float  # quanto o fluido cresceu desde o enchimento
    pressao_bar: float  # manométrica no nó do vaso
    ar_L: float  # volume de ar que sobra no vaso
    cheio: bool  # o ar do vaso acabou: a pressão dispara


def volume_minimo_do_vaso(v: ci.Vaso, dilatacao_L: float) -> float:
    """Volume do vaso para a dilatação dada não passar da pressão máxima (ASHRAE, HVAC Systems,
    vaso de membrana): V = ΔV·p_máx·p_ench/(p₀·(p_máx − p_ench)), pressões absolutas."""
    p0 = v.precarga_bar * 1e5 + ci.ATMOSFERA
    pf = v.enchimento_bar * 1e5 + ci.ATMOSFERA
    pm = v.maxima_bar * 1e5 + ci.ATMOSFERA
    return max(dilatacao_L, 0.0) * pm * pf / (p0 * (pm - pf))


def estado_do_vaso(v: ci.Vaso, dilatacao_L: float) -> EstadoDoVaso:
    p0 = v.precarga_bar * 1e5 + ci.ATMOSFERA
    pf = v.enchimento_bar * 1e5 + ci.ATMOSFERA
    ar_no_enchimento = v.volume_L * p0 / pf  # o ar da pré-carga comprimido até o enchimento
    ar = min(ar_no_enchimento - dilatacao_L, v.volume_L)
    cheio = ar <= 0.02 * v.volume_L
    ar_efetivo = max(ar, 0.02 * v.volume_L)
    p = pf * ar_no_enchimento / ar_efetivo if ar < v.volume_L else p0
    return EstadoDoVaso(dilatacao_L, (p - ci.ATMOSFERA) / 1e5, ar, cheio)


def tabela_de_massa_especifica(
    fluido: str, t_min: float, t_max: float
) -> tuple[np.ndarray, np.ndarray]:
    ts = np.linspace(min(t_min, t_max) - 1.0, max(t_min, t_max) + 1.0, 41)
    return ts, np.array([ci.propriedades(fluido, float(t)).massa_especifica for t in ts])


def dilatacao(
    volumes_m3: np.ndarray,
    temperaturas: np.ndarray,
    t_inicial: float,
    tabela: tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    """Quanto o fluido cresce desde o enchimento (L), quadro a quadro: V·(ρ₀/ρ − 1), sem a
    dilatação dos tubos (a favor da segurança no vaso)."""
    ts, rhos = tabela
    rho0 = float(np.interp(t_inicial, ts, rhos))
    rho = np.interp(temperaturas, ts, rhos)
    return (np.asarray(volumes_m3) * (rho0 / rho - 1.0)).sum(axis=-1) * 1000.0


# ---------------------------------------------------------------------------------------------
# No tempo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Celulas:
    elemento: np.ndarray  # índice do elemento de cada célula
    volume: np.ndarray  # m³
    capacidade: np.ndarray  # J/K (fluido + massa da peça)
    perda: np.ndarray  # W/K para o ar
    montante: list[tuple[str, int]]  # de onde vem o fluido: ("celula", i) ou ("no", j)
    posicao: np.ndarray  # fração ao longo do elemento (0 a 1, no sentido do desenho)


@dataclass(frozen=True)
class NoTempo:
    tempos: np.ndarray  # quadros, s
    celulas: Celulas
    quadros: np.ndarray  # quadros × células, °C
    nos: tuple[str, ...]  # ids dos nós com vazão
    temperaturas_dos_nos: np.ndarray  # quadros × nós
    saidas: dict[str, np.ndarray]  # elemento → °C na saída, por quadro
    calores: dict[str, np.ndarray]  # elemento → W para o fluido, por quadro
    rotacoes: dict[str, np.ndarray]  # dry cooler → 0 a 1, por quadro
    potencia_eletrica: dict[str, np.ndarray]  # chiller e ventilador → W
    vaso: list[EstadoDoVaso]
    duracao: float
    estabiliza: float | None
    avisos: tuple[str, ...] = field(default_factory=tuple)


def simular(
    c: ci.Circuito,
    h: ci.Hidraulica,
    cond: Condicoes,
    duracao: float | None = None,
    *,
    quadros: int = 151,
    celulas_alvo: int = 300,
) -> NoTempo:
    """O circuito no tempo. Sem duração, a conta cresce (2,5× por vez, até 48 h) até o circuito
    estabilizar com folga dentro do tempo mostrado."""
    if duracao is not None or cond.perfil_ar or cond.perfil_carga:
        return _simular(c, h, cond, duracao, quadros=quadros, celulas_alvo=celulas_alvo)
    tentativa = _simular(c, h, cond, None, quadros=quadros, celulas_alvo=celulas_alvo)
    for _ in range(5):
        if tentativa.estabiliza is not None and tentativa.estabiliza <= 0.7 * tentativa.duracao:
            return tentativa
        if tentativa.duracao >= 48 * 3600.0:
            break
        tentativa = _simular(
            c,
            h,
            cond,
            min(tentativa.duracao * 2.5, 48 * 3600.0),
            quadros=quadros,
            celulas_alvo=celulas_alvo,
        )
    return tentativa


def _simular(
    c: ci.Circuito,
    h: ci.Hidraulica,
    cond: Condicoes,
    duracao: float | None = None,
    *,
    quadros: int = 151,
    celulas_alvo: int = 300,
) -> NoTempo:
    p = ci.propriedades(c.fluido, cond.t_inicial + 10.0)
    rho_c = p.massa_especifica * p.calor_especifico
    caminhos = {e.id: (u, d, q) for e, u, d, q in _sentido(c, h)}
    nos = tuple(sorted({u for u, _, _ in caminhos.values()} | {d for _, d, _ in caminhos.values()}))
    indice_no = {n: i for i, n in enumerate(nos)}
    v_total = max(c.volume_m3, 1e-6)
    v_celula = v_total / celulas_alvo
    elementos = list(c.elementos)
    ids: list[int] = []
    vols: list[float] = []
    caps: list[float] = []
    perdas: list[float] = []
    montante: list[tuple[str, int]] = []
    posicoes: list[float] = []
    primeira: dict[str, int] = {}
    ultima: dict[str, int] = {}
    for k, e in enumerate(elementos):
        n = max(1, min(80, round(e.volume_m3 / v_celula))) if e.tipo == ci.TUBO else 1
        ua = condutancia_do_tubo(e)
        para_frente = e.id not in caminhos or h.vazoes[e.id] >= 0
        inicio = len(ids)
        for j in range(n):
            ids.append(k)
            vols.append(e.volume_m3 / n)
            extra = e.massa_kg * e.calor_especifico_massa if e.tipo == ci.FONTE else 0.0
            caps.append(rho_c * e.volume_m3 / n + extra / n)
            perdas.append(ua / n)
            frac = (j + 0.5) / n
            posicoes.append(frac if para_frente else 1.0 - frac)
            if e.id in caminhos:
                montante.append(
                    ("no", indice_no[caminhos[e.id][0]]) if j == 0 else ("celula", len(ids) - 2)
                )
            else:
                montante.append(("nada", -1))
        primeira[e.id], ultima[e.id] = inicio, len(ids) - 1
    n_cel, n_nos = len(ids), len(nos)
    total = n_cel + n_nos
    capacidade = np.array(caps)
    perda_ar = np.array(perdas)
    # vazão (capacidade térmica, W/K) que entra em cada célula
    fluxo = np.zeros(n_cel)
    for e in elementos:
        if e.id in caminhos:
            fluxo[primeira[e.id] : ultima[e.id] + 1] = rho_c * caminhos[e.id][2]
    q_total = sum(q for _, _, q in caminhos.values())
    t_volta = v_total / max(q_total, 1e-9)
    # duração: o tempo do circuito pesado pelo que tira calor
    coolers = {e.id: dry_cooler(e, c.fluido) for e in elementos if e.tipo == ci.DRY_COOLER}
    tira = (
        sum(dc.ua for dc in coolers.values())
        + sum(
            rho_c * caminhos[e.id][2]
            for e in elementos
            if e.tipo == ci.CHILLER and e.id in caminhos
        )
        + float(perda_ar.sum())
    )
    if duracao is None:
        if cond.perfil_ar or cond.perfil_carga:
            duracao = 24 * 3600.0
        else:
            tau = capacidade.sum() / max(tira, 1e-9)
            duracao = min(max(8.0 * tau, 30.0 * t_volta, 600.0), 48 * 3600.0)
    if not (math.isfinite(duracao) and duracao > 0):
        raise ErroTermico("Informe uma duração maior que zero.")
    passos = int(min(max(duracao / (t_volta / 150.0), 600), 6000))
    dt = duracao / passos
    # matriz implícita: (C/dt + fluxo + perda)·T − fluxo·T_montante = C/dt·T⁰ + perda·T_ar + fonte
    linhas, colunas, valores = [], [], []
    for i in range(n_cel):
        linhas.append(i)
        colunas.append(i)
        valores.append(capacidade[i] / dt + fluxo[i] + perda_ar[i])
        tipo, j = montante[i]
        if tipo != "nada" and fluxo[i] > 0:
            linhas.append(i)
            colunas.append(j if tipo == "celula" else n_cel + j)
            valores.append(-fluxo[i])
    for e in elementos:
        if e.id not in caminhos:
            continue
        _, d, q = caminhos[e.id]
        linha = n_cel + indice_no[d]
        linhas += [linha, linha]
        colunas += [ultima[e.id], linha]
        valores += [rho_c * q, -rho_c * q]
    matriz = sparse.csc_matrix((valores, (linhas, colunas)), shape=(total, total))
    try:
        fatorada = splinalg.splu(matriz)
    except RuntimeError as erro:
        raise ErroTermico("A conta no tempo não fechou: confira as vazões do circuito.") from erro
    x = np.full(total, float(cond.t_inicial))
    guardar = np.unique(np.linspace(0, passos, quadros).round().astype(int))
    q_cel = np.zeros((len(guardar), n_cel))
    q_nos = np.zeros((len(guardar), n_nos))
    calores = {
        e.id: np.zeros(len(guardar))
        for e in elementos
        if e.tipo in (ci.FONTE, ci.DRY_COOLER, ci.CHILLER)
    }
    rotacoes = {id_: np.zeros(len(guardar)) for id_ in coolers}
    eletrica = {
        e.id: np.zeros(len(guardar)) for e in elementos if e.tipo in (ci.DRY_COOLER, ci.CHILLER)
    }
    rotacao_atual = {id_: 1.0 for id_ in coolers}
    ligado = {id_: True for id_ in coolers}

    def entrada(e: ci.Elemento, estado: np.ndarray) -> float:
        tipo, j = montante[primeira[e.id]]
        return float(estado[n_cel + j]) if tipo == "no" else float(estado[j])

    k_quadro = 0
    fonte = np.zeros(total)
    instantaneos: dict[str, float] = {}
    for passo in range(passos + 1):
        t = passo * dt
        t_ar = cond.ar(t)
        fonte[:] = 0.0
        fonte[:n_cel] = perda_ar * t_ar
        for e in elementos:
            if e.id not in caminhos:
                continue
            i = primeira[e.id]
            cap = rho_c * caminhos[e.id][2]
            if e.tipo == ci.FONTE:
                valor = e.potencia_kW * 1000.0 * cond.carga(t)
            elif e.tipo == ci.DRY_COOLER:
                t_in = entrada(e, x)
                dc = coolers[e.id]
                if e.controle == ci.PROPORCIONAL:
                    rotacao_atual[e.id] = dc.rotacao_para(cap, t_in, t_ar, e.t_ajuste)
                elif e.controle == ci.LIGA_DESLIGA:
                    t_out = float(x[i])
                    if t_out > e.t_ajuste + 1.0:
                        ligado[e.id] = True
                    elif t_out < e.t_ajuste - 1.0:
                        ligado[e.id] = False
                    rotacao_atual[e.id] = 1.0 if ligado[e.id] else 0.0
                valor = -dc.calor(cap, t_in, t_ar, rotacao_atual[e.id])
            elif e.tipo == ci.CHILLER:
                valor = -calor_do_chiller(e, cap, entrada(e, x))
            else:
                continue
            fonte[i] += valor
            instantaneos[e.id] = valor
        if passo in guardar:
            q_cel[k_quadro] = x[:n_cel]
            q_nos[k_quadro] = x[n_cel:]
            for id_, serie in calores.items():
                serie[k_quadro] = instantaneos.get(id_, 0.0)
            for id_ in coolers:
                rotacoes[id_][k_quadro] = rotacao_atual[id_]
            for e in elementos:
                if e.tipo == ci.DRY_COOLER:
                    eletrica[e.id][k_quadro] = (
                        e.potencia_ventilador_kW * 1000.0 * rotacao_atual[e.id] ** 3
                    )
                elif e.tipo == ci.CHILLER:
                    eletrica[e.id][k_quadro] = -instantaneos.get(e.id, 0.0) / e.cop
            k_quadro += 1
        if passo == passos:
            break
        lado = np.zeros(total)
        lado[:n_cel] = capacidade / dt * x[:n_cel]
        lado += fonte
        x = fatorada.solve(lado)
        if not np.all(np.isfinite(x)):
            raise ErroTermico("A conta no tempo deu um valor que não é número: confira os dados.")
    tempos = guardar * dt
    saidas = {e.id: q_cel[:, ultima[e.id]] for e in elementos}
    # vaso de expansão
    vaso_no = c.vaso
    estados: list[EstadoDoVaso] = []
    avisos: list[str] = []
    if vaso_no is not None and vaso_no.vaso is not None:
        tabela = tabela_de_massa_especifica(c.fluido, float(np.min(q_cel)), float(np.max(q_cel)))
        dil = dilatacao(np.array(vols), q_cel, cond.t_inicial, tabela)
        estados = [estado_do_vaso(vaso_no.vaso, float(v)) for v in dil]
        if any(s.cheio for s in estados):
            avisos.append(
                "O ar do vaso de expansão acaba: o vaso é pequeno para a dilatação do fluido e a "
                "pressão dispara. Aumente o vaso."
            )
    # estabiliza: todas as temperaturas a 1 % do caminho até o fim e sem sair mais dali
    estabiliza = None
    if not (cond.perfil_ar or cond.perfil_carga):
        final = q_cel[-1]
        salto = float(np.max(np.abs(final - cond.t_inicial)))
        if salto > 0:
            desvio = np.max(np.abs(q_cel - final), axis=1)
            estabiliza = primeiro_abaixo_de_vez(tempos, desvio, TOLERANCIA * salto)
            if estabiliza is not None and estabiliza > 0.95 * tempos[-1]:
                estabiliza = None
            if estabiliza is None and duracao >= 48 * 3600.0 - 1.0:
                avisos.append("O circuito ainda muda no fim da conta: informe uma duração maior.")
    return NoTempo(
        tempos=tempos,
        celulas=Celulas(
            np.array(ids), np.array(vols), capacidade, perda_ar, montante, np.array(posicoes)
        ),
        quadros=q_cel,
        nos=nos,
        temperaturas_dos_nos=q_nos,
        saidas=saidas,
        calores=calores,
        rotacoes=rotacoes,
        potencia_eletrica=eletrica,
        vaso=estados,
        duracao=float(duracao),
        estabiliza=estabiliza,
        avisos=tuple(avisos),
    )
