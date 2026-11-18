"""Tanque no tempo: o nível enchendo ou esvaziando e a temperatura do líquido subindo ou descendo.

**Nível.** Balanço de volume: dV/dt = Q_entrada − Q_saída(h). A saída é por um orifício no fundo
(Torricelli: Q = C_d·A·√(2·g·h)), por um tubo que descarrega livre (energia: h + z = (1 + f·L/D +
ΣK)·v²/(2·g), com o f de Darcy do Montador de fluidos) ou por uma bomba de vazão fixa. A conta anda
no volume, e não na altura, para o tanque horizontal (área que muda com a altura) não ter
singularidade no fundo e no topo.

**Temperatura.** Tanque bem misturado, de massa constante: m·c·dT/dt = P + UA_s·(T_s − T) +
ṁ·c·(T_e − T) − UA_p·(T − T_amb). Com tudo constante a equação é linear e tem solução exata:
T = T_eq + (T_0 − T_eq)·e^(−t/τ), τ = m·c/(UA_s + ṁ·c + UA_p).

Unidades: SI na conta; vazões de entrada e saída em L/s, medidas em m e mm, temperatura em °C.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import cache

import numpy as np
from scipy import integrate, optimize

from core.montador_funcoes import fator_de_atrito

GRAVIDADE = 9.81
VERTICAL = "vertical"
RETANGULAR = "retangular"
HORIZONTAL = "horizontal"
FORMAS = (VERTICAL, RETANGULAR, HORIZONTAL)

SEM_SAIDA = "nenhuma"
ORIFICIO = "orificio"
TUBO = "tubo"
BOMBA = "bomba"
SAIDAS = (SEM_SAIDA, ORIFICIO, TUBO, BOMBA)
#: Coeficiente de descarga de orifício de borda viva (Çengel e Cimbala, Mecânica dos Fluidos, cap. 8).
CD_ORIFICIO = 0.61
PONTOS = 1201
#: Nível em que o tanque conta como vazio (m).
NIVEL_VAZIO = 0.001


class ErroDoTanque(ValueError):
    """Dado que impede a conta; a mensagem diz o que corrigir."""


def _n(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


# =============================================================================================
# Nível
# =============================================================================================
@dataclass(frozen=True, slots=True)
class Saida:
    tipo: str = ORIFICIO
    diametro_mm: float = 50.0  # orifício ou tubo (interno)
    cd: float = CD_ORIFICIO
    comprimento_m: float = 10.0  # tubo
    rugosidade_mm: float = 0.045
    k_local: float = 0.5  # entrada do tubo e peças
    desnivel_m: float = 0.0  # quanto a ponta do tubo fica abaixo do fundo do tanque
    vazao_bomba_L_s: float = 5.0
    massa_especifica: float = 998.2
    viscosidade: float = 1.0016e-3


@dataclass(frozen=True, slots=True)
class Tanque:
    forma: str
    altura_m: float  # vertical e retangular; no horizontal é o diâmetro
    diametro_m: float = 2.0  # vertical e horizontal
    comprimento_m: float = 3.0  # retangular e horizontal
    largura_m: float = 2.0  # retangular
    nivel_inicial_m: float = 1.0
    entrada_L_s: float = 0.0
    saida: Saida = field(default_factory=Saida)

    @property
    def altura_util(self) -> float:
        return self.diametro_m if self.forma == HORIZONTAL else self.altura_m

    def volume(self, h: float) -> float:
        """Volume de líquido com o nível ``h`` (m³)."""
        h = min(max(h, 0.0), self.altura_util)
        if self.forma == VERTICAL:
            return math.pi * self.diametro_m**2 / 4.0 * h
        if self.forma == RETANGULAR:
            return self.comprimento_m * self.largura_m * h
        r = self.diametro_m / 2.0
        segmento = r * r * math.acos((r - h) / r) - (r - h) * math.sqrt(max(0.0, 2 * r * h - h * h))
        return self.comprimento_m * segmento

    @property
    def volume_total(self) -> float:
        return self.volume(self.altura_util)

    def nivel(self, volume: float) -> float:
        """Nível com o volume dado (inversa de :meth:`volume`)."""
        if volume <= 0:
            return 0.0
        if volume >= self.volume_total:
            return self.altura_util
        if self.forma == VERTICAL:
            return volume / (math.pi * self.diametro_m**2 / 4.0)
        if self.forma == RETANGULAR:
            return volume / (self.comprimento_m * self.largura_m)
        return float(
            optimize.brentq(lambda h: self.volume(h) - volume, 0.0, self.altura_util, xtol=1e-12)
        )


def vazao_de_saida(tanque: Tanque, h: float) -> float:
    """Vazão que sai com o nível ``h`` (m³/s)."""
    s = tanque.saida
    if h <= 0 or s.tipo == SEM_SAIDA:
        return 0.0
    if s.tipo == BOMBA:
        return s.vazao_bomba_L_s / 1000.0
    area = math.pi * (s.diametro_mm / 1000.0) ** 2 / 4.0
    if s.tipo == ORIFICIO:
        return s.cd * area * math.sqrt(2.0 * GRAVIDADE * h)
    carga = h + s.desnivel_m
    if carga <= 0:
        return 0.0
    return area * float(velocidade_no_tubo(carga, s))


def velocidade_no_tubo(carga: float | np.ndarray, s: Saida) -> np.ndarray:
    """v na energia: carga = (1 + f·L/D + ΣK)·v²/(2g), com f(Re) de Darcy (vale para várias
    cargas de uma vez)."""
    d = s.diametro_mm / 1000.0
    relativa = s.rugosidade_mm / s.diametro_mm
    h = np.maximum(np.asarray(carga, dtype=float), 0.0)
    v = np.sqrt(2.0 * GRAVIDADE * h / (1.0 + s.k_local + 0.02 * s.comprimento_m / d))
    for _ in range(200):
        re = np.maximum(s.massa_especifica * v * d / s.viscosidade, 1e-9)
        f = fator_de_atrito(re, relativa)
        novo = np.sqrt(2.0 * GRAVIDADE * h / (1.0 + s.k_local + f * s.comprimento_m / d))
        if np.all(np.abs(novo - v) <= 1e-11 * np.maximum(1.0, v)):
            return novo
        v = 0.5 * (v + novo)
    return v


def problemas_do_nivel(t: Tanque) -> list[str]:
    erros: list[str] = []
    if t.forma not in FORMAS:
        return ["Escolha a forma do tanque."]
    medidas = [("a altura", t.altura_m)] if t.forma != HORIZONTAL else []
    if t.forma in (VERTICAL, HORIZONTAL):
        medidas.append(("o diâmetro", t.diametro_m))
    if t.forma in (RETANGULAR, HORIZONTAL):
        medidas.append(("o comprimento", t.comprimento_m))
    if t.forma == RETANGULAR:
        medidas.append(("a largura", t.largura_m))
    for nome, valor in medidas:
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {nome} do tanque, maior que zero.")
    if erros:
        return erros
    if not 0 <= t.nivel_inicial_m <= t.altura_util:
        erros.append(f"O nível inicial precisa ficar entre 0 e {_n(t.altura_util)} m.")
    if t.entrada_L_s < 0:
        erros.append("A vazão de entrada não pode ser negativa: use a saída para tirar líquido.")
    s = t.saida
    if s.tipo in (ORIFICIO, TUBO) and not s.diametro_mm > 0:
        erros.append("Informe o diâmetro da saída, maior que zero.")
    if s.tipo == ORIFICIO and not 0 < s.cd <= 1:
        erros.append("O coeficiente de descarga fica entre 0 e 1 (borda viva: 0,61).")
    if s.tipo == TUBO and not s.comprimento_m > 0:
        erros.append("Informe o comprimento do tubo de saída, maior que zero.")
    if s.tipo == BOMBA and s.vazao_bomba_L_s < 0:
        erros.append("A vazão da bomba não pode ser negativa.")
    if t.entrada_L_s == 0 and (s.tipo == SEM_SAIDA or vazao_de_saida(t, t.nivel_inicial_m) == 0):
        erros.append("Sem entrada e sem saída o nível não muda: informe uma das duas.")
    return erros


@dataclass(frozen=True)
class ResultadoDoNivel:
    tanque: Tanque
    tempos: np.ndarray  # s
    niveis: np.ndarray  # m
    volumes: np.ndarray  # m³
    entrada: np.ndarray  # L/s
    saida: np.ndarray  # L/s
    duracao: float
    evento: str  # "vazio", "cheio", "estavel", "" (duração informada)
    nivel_de_equilibrio: float | None
    avisos: tuple[str, ...] = ()

    def tempo_para(self, nivel: float) -> float | None:
        from core.calor_no_tempo import primeiro_cruzamento

        return primeiro_cruzamento(self.tempos, self.niveis, nivel)


def nivel_de_equilibrio(t: Tanque) -> float | None:
    """Nível em que a saída iguala a entrada; ``None`` se não há (ou se passa do topo)."""
    q = t.entrada_L_s / 1000.0
    if q <= 0 or t.saida.tipo in (SEM_SAIDA, BOMBA):
        return None
    topo = t.altura_util
    if vazao_de_saida(t, topo) < q:
        return None
    if t.saida.tipo == TUBO and vazao_de_saida(t, 1e-12) > q:
        return None  # o tubo tira mais que a entrada mesmo com o tanque quase vazio
    return float(optimize.brentq(lambda h: vazao_de_saida(t, h) - q, 1e-12, topo, xtol=1e-10))


def calcular_nivel(t: Tanque, duracao: float | None = None) -> ResultadoDoNivel:
    erros = problemas_do_nivel(t)
    if erros:
        raise ErroDoTanque(" ".join(erros))
    entrada = t.entrada_L_s / 1000.0
    topo = t.volume_total
    equilibrio = nivel_de_equilibrio(t)
    avisos: list[str] = []

    # Tabelas da altura pelo volume (tanque horizontal) e da vazão do tubo pela altura: a conta do
    # tubo itera o f a cada nível, e a integração pede milhares de níveis.
    alturas = t.altura_util * np.linspace(0.0, 1.0, 2001) ** 2
    volumes_t = np.array([t.volume(h) for h in alturas]) if t.forma == HORIZONTAL else None
    vazoes_t = None
    if t.saida.tipo == TUBO:
        area_tubo = math.pi * (t.saida.diametro_mm / 1000.0) ** 2 / 4.0
        vazoes_t = area_tubo * velocidade_no_tubo(alturas + t.saida.desnivel_m, t.saida)

    def nivel_do_volume(vol: float) -> float:
        if volumes_t is not None:
            return float(np.interp(vol, volumes_t, alturas))
        return t.nivel(vol)

    def saida_no_nivel(h: float) -> float:
        if vazoes_t is not None:
            return float(np.interp(h, alturas, vazoes_t)) if h > 0 else 0.0
        return vazao_de_saida(t, h)

    def derivada(_: float, v: np.ndarray) -> list[float]:
        vol = float(min(max(v[0], 0.0), topo))
        return [entrada - saida_no_nivel(nivel_do_volume(vol))]

    # Vazio = 1 mm de líquido: pelo tubo, no fim o escoamento fica laminar, a vazão cai com o nível
    # e o último milímetro levaria um tempo sem fim.
    volume_vazio = t.volume(min(NIVEL_VAZIO, 0.5 * t.altura_util))

    def vazio(_: float, v: np.ndarray) -> float:
        return float(v[0]) - volume_vazio

    def cheio(_: float, v: np.ndarray) -> float:
        return topo - float(v[0])

    vazio.terminal, vazio.direction = True, -1  # type: ignore[attr-defined]
    cheio.terminal, cheio.direction = True, -1  # type: ignore[attr-defined]
    eventos: list[Callable[..., float]] = [vazio, cheio]
    v0 = t.volume(t.nivel_inicial_m)
    if duracao is None and equilibrio is not None and abs(t.nivel_inicial_m - equilibrio) < 1e-6:
        duracao = 3600.0
        avisos.append("O nível já começa no equilíbrio: a entrada iguala a saída e nada muda.")
    if duracao is None:
        saida_0 = vazao_de_saida(t, t.nivel_inicial_m)
        liquido = abs(entrada - saida_0)
        escala = (topo / max(liquido, 1e-12)) if liquido > 0 else 3600.0
        limite = 200.0 * escala
        if equilibrio is not None:
            alvo = t.volume(equilibrio)
            desvio = abs(v0 - alvo)

            def estavel(_: float, v: np.ndarray) -> float:
                return abs(float(v[0]) - alvo) - 0.005 * max(desvio, 1e-9 * topo)

            estavel.terminal, estavel.direction = True, -1  # type: ignore[attr-defined]
            eventos.append(estavel)
    else:
        if not (math.isfinite(duracao) and duracao > 0):
            raise ErroDoTanque("Informe uma duração maior que zero.")
        limite = duracao
    solucao = integrate.solve_ivp(
        derivada,
        (0.0, limite),
        [v0],
        events=eventos,
        rtol=1e-9,
        atol=1e-10 * max(topo, 1e-9),
        dense_output=True,
        max_step=limite / 200.0,
    )
    if not solucao.success:
        raise ErroDoTanque("A conta do nível não fechou: confira os dados do tanque e da saída.")
    fim = float(solucao.t[-1])
    evento = ""
    for nome, ocorridos in zip(("vazio", "cheio", "estavel"), solucao.t_events, strict=False):
        if len(ocorridos):
            evento = nome
            fim = float(ocorridos[0])
            break
    if duracao is None and not evento:
        avisos.append("O nível ainda muda no fim da conta: informe uma duração maior.")
    if fim <= 0:
        fim = limite
    tempos = np.linspace(0.0, fim, PONTOS)
    volumes = np.clip(solucao.sol(tempos)[0], 0.0, topo)
    niveis = np.array([nivel_do_volume(v) for v in volumes])
    saida = np.array([saida_no_nivel(h) for h in niveis]) * 1000.0
    if evento == "vazio":
        saida[-1] = 0.0 if t.saida.tipo != BOMBA else saida[-1]
    if t.saida.tipo == BOMBA and evento == "vazio":
        avisos.append(
            "A bomba esvazia o tanque: na prática ela perde a sucção antes (NPSH), e o nível "
            "mínimo de operação fica acima do fundo."
        )
    if evento == "cheio":
        avisos.append(
            f"O tanque enche até o topo ({_n(t.altura_util)} m) e transborda neste instante."
        )
    return ResultadoDoNivel(
        tanque=t,
        tempos=tempos,
        niveis=niveis,
        volumes=volumes,
        entrada=np.full(len(tempos), t.entrada_L_s),
        saida=saida,
        duracao=fim,
        evento=evento,
        nivel_de_equilibrio=equilibrio,
        avisos=tuple(avisos),
    )


def tempo_de_torricelli(t: Tanque, h0: float, h1: float) -> float:
    """Tempo exato para baixar de h0 a h1 por orifício, sem entrada, em tanque de área constante:
    t = (A_t/(C_d·A_o))·√(2/g)·(√h0 − √h1)."""
    if t.forma == VERTICAL:
        area = math.pi * t.diametro_m**2 / 4.0
    elif t.forma == RETANGULAR:
        area = t.comprimento_m * t.largura_m
    else:
        raise ValueError("Torricelli exato só para área constante.")
    a_o = math.pi * (t.saida.diametro_mm / 1000.0) ** 2 / 4.0
    return area / (t.saida.cd * a_o) * math.sqrt(2.0 / GRAVIDADE) * (math.sqrt(h0) - math.sqrt(h1))


def hipoteses_do_nivel(r: ResultadoDoNivel) -> list[str]:
    s = r.tanque.saida
    linhas = [
        "Líquido incompressível; o nível é o mesmo em todo o tanque (sem onda), e a pressão em cima "
        "do líquido é a atmosférica.",
        "Escoamento quase permanente na saída: a cada instante vale a conta de regime com o nível "
        "daquele instante.",
        "O tanque conta como vazio com 1 mm de líquido.",
    ]
    if s.tipo == ORIFICIO:
        linhas.append(
            f"Orifício no fundo com C_d = {_n(s.cd, 2)} (borda viva: 0,61, Çengel e Cimbala, cap. 8)."
        )
    elif s.tipo == TUBO:
        linhas.append(
            "Tubo de saída descarregando livre: a energia do nível vira velocidade na ponta e perda "
            "no tubo (Darcy-Weisbach, f por Colebrook) e nas peças (ΣK)."
        )
    elif s.tipo == BOMBA:
        linhas.append("Bomba de vazão constante, sem conferir NPSH nem a curva da bomba.")
    return linhas


# =============================================================================================
# Temperatura
# =============================================================================================
NENHUM = "nenhum"
POTENCIA = "potencia"
SERPENTINA = "serpentina"
AQUECIMENTOS = (NENHUM, POTENCIA, SERPENTINA)


@cache
def propriedades_da_agua(t_c: float) -> tuple[float, float]:
    """ρ (kg/m³) e c_p (J/(kg·K)) da água líquida a 1 atm (CoolProp)."""
    import CoolProp.CoolProp as cp  # noqa: N813

    t = min(max(t_c, 0.5), 99.0) + 273.15
    return float(cp.PropsSI("D", "T", t, "P", 101325.0, "Water")), float(
        cp.PropsSI("C", "T", t, "P", 101325.0, "Water")
    )


@dataclass(frozen=True, slots=True)
class TanqueTermico:
    volume_m3: float
    massa_especifica: float
    calor_especifico: float
    t_inicial: float
    aquecimento: str = POTENCIA
    potencia_kW: float = 10.0  # negativa = resfriamento
    ua_serpentina: float = 500.0  # W/K
    t_serpentina: float = 120.0  # °C, do vapor ou do fluido da serpentina (constante)
    ua_perda: float = 0.0  # W/K, para o ambiente
    t_ambiente: float = 20.0
    vazao_kg_s: float = 0.0  # entra e sai a mesma vazão (massa constante)
    t_entrada: float = 20.0
    agua: bool = True  # o líquido é água (ferve a 100 °C a 1 atm)
    termostato: float | None = None  # °C: o aquecimento passa a só repor as perdas ao chegar aqui

    @property
    def massa(self) -> float:
        return self.volume_m3 * self.massa_especifica


@dataclass(frozen=True)
class ResultadoTermico:
    tanque: TanqueTermico
    tempos: np.ndarray
    temperaturas: np.ndarray
    calor_aquecimento: np.ndarray  # kW, a cada instante
    calor_perda: np.ndarray  # kW (positivo: sai)
    calor_vazao: np.ndarray  # kW (positivo: o que a vazão tira)
    t_equilibrio: float | None
    tau: float | None
    duracao: float
    avisos: tuple[str, ...] = ()

    tempo_do_termostato: float | None = None

    @property
    def tempo_para_estabilizar(self) -> float | None:
        """Quando o líquido fica a 1 % do equilíbrio (ln(100)·τ), ou quando o termostato segura."""
        if self.tempo_do_termostato is not None:
            return self.tempo_do_termostato
        if self.tau is None:
            return None
        t = math.log(100.0) * self.tau
        return t if t <= self.duracao else None

    def tempo_para(self, alvo: float) -> float | None:
        from core.calor_no_tempo import primeiro_cruzamento

        exato = tempo_para_temperatura(self.tanque, alvo)
        if self.tempo_do_termostato is None or exato is None or exato <= self.tempo_do_termostato:
            return exato if exato is None or exato <= self.duracao else None
        return primeiro_cruzamento(self.tempos, self.temperaturas, alvo)


def _coeficientes(t: TanqueTermico) -> tuple[float, float]:
    """a e b em m·c·dT/dt = a − b·T (W e W/K)."""
    c = t.calor_especifico
    a = t.ua_perda * t.t_ambiente + t.vazao_kg_s * c * t.t_entrada
    b = t.ua_perda + t.vazao_kg_s * c
    if t.aquecimento == POTENCIA:
        a += t.potencia_kW * 1000.0
    elif t.aquecimento == SERPENTINA:
        a += t.ua_serpentina * t.t_serpentina
        b += t.ua_serpentina
    return a, b


def temperatura_exata(t: TanqueTermico, tempo: np.ndarray | float) -> np.ndarray:
    a, b = _coeficientes(t)
    mc = t.massa * t.calor_especifico
    tempo = np.asarray(tempo, dtype=float)
    if b <= 0:
        return t.t_inicial + a / mc * tempo
    equilibrio = a / b
    return equilibrio + (t.t_inicial - equilibrio) * np.exp(-b * tempo / mc)


def tempo_para_temperatura(t: TanqueTermico, alvo: float) -> float | None:
    a, b = _coeficientes(t)
    mc = t.massa * t.calor_especifico
    if alvo == t.t_inicial:
        return 0.0
    if b <= 0:
        if a == 0:
            return None
        tempo = (alvo - t.t_inicial) * mc / a
        return tempo if tempo > 0 else None
    equilibrio = a / b
    razao = (alvo - equilibrio) / (t.t_inicial - equilibrio) if t.t_inicial != equilibrio else -1.0
    if not 0 < razao < 1:
        return None
    return -mc / b * math.log(razao)


def problemas_termicos(t: TanqueTermico) -> list[str]:
    erros: list[str] = []
    for valor, nome in (
        (t.volume_m3, "o volume de líquido"),
        (t.massa_especifica, "a massa específica"),
        (t.calor_especifico, "o calor específico"),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {nome}, maior que zero.")
    if t.ua_perda < 0 or t.ua_serpentina < 0 or t.vazao_kg_s < 0:
        erros.append("UA e vazão não podem ser negativos.")
    if t.agua and not 0 < t.t_inicial < 100:
        erros.append("A água a 1 atm é líquida entre 0 e 100 °C: confira a temperatura inicial.")
    if t.termostato is not None and t.aquecimento == NENHUM:
        erros.append("O termostato comanda o aquecimento: escolha a resistência ou a serpentina.")
    a, b = _coeficientes(t)
    if b <= 0 and a == 0:
        erros.append("Sem aquecimento, perda nem vazão a temperatura não muda.")
    return erros


def calcular_termico(t: TanqueTermico, duracao: float | None = None) -> ResultadoTermico:
    erros = problemas_termicos(t)
    if erros:
        raise ErroDoTanque(" ".join(erros))
    a, b = _coeficientes(t)
    mc = t.massa * t.calor_especifico
    tau = mc / b if b > 0 else None
    equilibrio = a / b if b > 0 else None
    avisos: list[str] = []
    # Termostato ideal: ao chegar à temperatura dele, o aquecimento só repõe o que sai.
    t_termostato = None
    if t.termostato is not None and t.aquecimento != NENHUM:
        t_termostato = tempo_para_temperatura(t, t.termostato)
    if duracao is None and t_termostato is not None:
        duracao = 1.4 * t_termostato
    if duracao is None:
        # um pouco além de chegar a 1 % do equilíbrio (ln 100·τ): o instante cabe no gráfico
        duracao = math.log(250.0) * tau if tau is not None else 3600.0
        if tau is None:
            avisos.append(
                "Só com potência e sem perda nem vazão, a temperatura sobe sem parar (em linha "
                "reta): a duração mostrada é de 1 h."
            )
    if not (math.isfinite(duracao) and duracao > 0):
        raise ErroDoTanque("Informe uma duração maior que zero.")
    tempos = np.linspace(0.0, duracao, PONTOS)
    temperaturas = temperatura_exata(t, tempos)
    segurando = np.zeros(len(tempos), dtype=bool)
    if t_termostato is not None and t.termostato is not None:
        segurando = tempos >= t_termostato
        temperaturas = np.where(segurando, t.termostato, temperaturas)
    if t.agua and not segurando.any():
        for limite, texto in ((100.0, "ferve"), (0.0, "congela")):
            cruzou = tempo_para_temperatura(t, limite)
            if cruzou is not None and cruzou <= duracao:
                avisos.append(
                    f"A água chega a {_n(limite, 0)} °C em {_n(cruzou / 60.0, 1)} min e {texto} (a "
                    "1 atm): a conta vale só até ali, e a animação para nesse instante."
                )
                duracao = cruzou
                tempos = np.linspace(0.0, duracao, PONTOS)
                temperaturas = temperatura_exata(t, tempos)
                break
    c = t.calor_especifico
    if t.aquecimento == POTENCIA:
        aquecimento = np.full(len(tempos), t.potencia_kW)
    elif t.aquecimento == SERPENTINA:
        aquecimento = t.ua_serpentina * (t.t_serpentina - temperaturas) / 1000.0
    else:
        aquecimento = np.zeros(len(tempos))
    reposicao = (
        t.ua_perda * (temperaturas - t.t_ambiente) + t.vazao_kg_s * c * (temperaturas - t.t_entrada)
    ) / 1000.0
    aquecimento = np.where(segurando, reposicao, aquecimento)
    if equilibrio is not None and t.aquecimento == SERPENTINA and t.t_serpentina < t.t_inicial:
        avisos.append("A serpentina está mais fria que o líquido: ela resfria o tanque.")
    return ResultadoTermico(
        tanque=t,
        tempos=tempos,
        temperaturas=temperaturas,
        calor_aquecimento=aquecimento,
        calor_perda=t.ua_perda * (temperaturas - t.t_ambiente) / 1000.0,
        calor_vazao=t.vazao_kg_s * c * (temperaturas - t.t_entrada) / 1000.0,
        t_equilibrio=equilibrio,
        tau=tau,
        duracao=float(duracao),
        avisos=tuple(avisos),
        tempo_do_termostato=t_termostato,
    )


def hipoteses_termicas(r: ResultadoTermico) -> list[str]:
    t = r.tanque
    linhas = [
        "Tanque bem misturado: a temperatura é a mesma em todo o líquido (agitador ou circulação).",
        "Massa constante: a vazão que entra é a que sai. ρ e c_p constantes, pela temperatura "
        "inicial.",
        "Parede do tanque sem capacidade térmica própria; perda para o ambiente por UA constante.",
    ]
    if t.aquecimento == SERPENTINA:
        linhas.append(
            "Serpentina ou camisa com UA constante e a fonte a temperatura constante (vapor "
            "condensando ou fluido com vazão grande)."
        )
    if t.termostato is not None:
        linhas.append(
            "Termostato ideal: ao chegar à temperatura dele, o aquecimento passa a repor só o que "
            "sai pela parede e pela vazão, e a temperatura fica parada (sem liga e desliga)."
        )
    if t.agua:
        linhas.append("Água líquida a 1 atm, sem ferver nem congelar.")
    return linhas


# =============================================================================================
# Vasos comunicantes: dois tanques ligados por um tubo no fundo
# =============================================================================================
@dataclass(frozen=True, slots=True)
class Vasos:
    """O tanque 1 (com a entrada, se houver) e o tanque 2, ligados por um tubo entre os fundos.

    ``cota_fundo_2``: quanto o fundo do tanque 2 fica acima do fundo do tanque 1 (m; negativo,
    abaixo). A ``ligacao`` é o tubo (diâmetro, comprimento, rugosidade, ΣK e o fluido)."""

    tanque_1: Tanque
    tanque_2: Tanque
    cota_fundo_2: float
    ligacao: Saida


@dataclass(frozen=True)
class ResultadoDosVasos:
    vasos: Vasos
    tempos: np.ndarray
    niveis_1: np.ndarray  # m, do fundo de cada tanque
    niveis_2: np.ndarray
    vazao: np.ndarray  # L/s, positiva do tanque 1 para o 2
    duracao: float
    evento: str  # "equalizou", "vazio_1", "vazio_2", "cheio_1", "cheio_2", "" (duração informada)
    superficie_de_equilibrio: float | None  # cota da água igual nos dois (m, do fundo do tanque 1)
    avisos: tuple[str, ...] = ()

    @property
    def diferenca(self) -> np.ndarray:
        """Desnível entre as superfícies da água (m): tanque 1 menos tanque 2."""
        return self.niveis_1 - (self.vasos.cota_fundo_2 + self.niveis_2)

    def tempo_para_diferenca(self, desnivel: float) -> float | None:
        from core.calor_no_tempo import primeiro_cruzamento

        return primeiro_cruzamento(self.tempos, np.abs(self.diferenca), desnivel)


def problemas_dos_vasos(v: Vasos) -> list[str]:
    erros = [
        f"Tanque 1: {e}"
        for e in problemas_do_nivel(replace(v.tanque_1, saida=Saida(SEM_SAIDA), entrada_L_s=1.0))
    ]
    erros += [
        f"Tanque 2: {e}"
        for e in problemas_do_nivel(replace(v.tanque_2, saida=Saida(SEM_SAIDA), entrada_L_s=1.0))
    ]
    s = v.ligacao
    if not s.diametro_mm > 0:
        erros.append("Informe o diâmetro do tubo de ligação, maior que zero.")
    if not s.comprimento_m > 0:
        erros.append("Informe o comprimento do tubo de ligação, maior que zero.")
    if not math.isfinite(v.cota_fundo_2):
        erros.append("Informe a cota do fundo do tanque 2.")
    if not erros:
        d0 = v.tanque_1.nivel_inicial_m - (v.cota_fundo_2 + v.tanque_2.nivel_inicial_m)
        if abs(d0) <= NIVEL_VAZIO and v.tanque_1.entrada_L_s == 0:
            erros.append("Os dois níveis já começam iguais: não há o que equalizar.")
    return erros


def superficie_de_equilibrio(v: Vasos) -> float | None:
    """Cota da água igual nos dois tanques, guardando o volume total; ``None`` se um esvazia ou
    transborda antes."""
    t1, t2 = v.tanque_1, v.tanque_2
    total = t1.volume(t1.nivel_inicial_m) + t2.volume(t2.nivel_inicial_m)
    baixo = max(0.0, v.cota_fundo_2)
    alto = min(t1.altura_util, v.cota_fundo_2 + t2.altura_util)
    if alto <= baixo:
        return None

    def sobra(z: float) -> float:
        return t1.volume(z) + t2.volume(z - v.cota_fundo_2) - total

    if sobra(baixo) > 0 or sobra(alto) < 0:
        return None
    return float(optimize.brentq(sobra, baixo, alto, xtol=1e-12))


def calcular_vasos(v: Vasos, duracao: float | None = None) -> ResultadoDosVasos:
    erros = problemas_dos_vasos(v)
    if erros:
        raise ErroDoTanque(" ".join(erros))
    t1, t2 = v.tanque_1, v.tanque_2
    z2 = v.cota_fundo_2
    entrada = t1.entrada_L_s / 1000.0
    area_tubo = math.pi * (v.ligacao.diametro_mm / 1000.0) ** 2 / 4.0
    d0 = t1.nivel_inicial_m - (z2 + t2.nivel_inicial_m)
    maior = max(abs(d0), t1.altura_util + abs(z2) + t2.altura_util)
    desniveis = maior * np.linspace(0.0, 1.0, 2001) ** 2
    vazoes = area_tubo * velocidade_no_tubo(desniveis, v.ligacao)
    topo_1, topo_2 = t1.volume_total, t2.volume_total

    def niveis(y: np.ndarray) -> tuple[float, float]:
        return t1.nivel(float(min(max(y[0], 0.0), topo_1))), t2.nivel(
            float(min(max(y[1], 0.0), topo_2))
        )

    def vazao(h1: float, h2: float) -> float:
        d = h1 - (z2 + h2)
        if d > 0 and h1 <= 0:
            return 0.0
        if d < 0 and h2 <= 0:
            return 0.0
        return math.copysign(float(np.interp(abs(d), desniveis, vazoes)), d)

    def derivada(_: float, y: np.ndarray) -> list[float]:
        h1, h2 = niveis(y)
        q = vazao(h1, h2)
        return [entrada - q, q]

    v_vazio_1 = t1.volume(min(NIVEL_VAZIO, 0.5 * t1.altura_util))
    v_vazio_2 = t2.volume(min(NIVEL_VAZIO, 0.5 * t2.altura_util))

    def equalizou(_: float, y: np.ndarray) -> float:
        h1, h2 = niveis(y)
        return abs(h1 - (z2 + h2)) - NIVEL_VAZIO

    def vazio_1(_: float, y: np.ndarray) -> float:
        return float(y[0]) - v_vazio_1

    def vazio_2(_: float, y: np.ndarray) -> float:
        return float(y[1]) - v_vazio_2

    def cheio_1(_: float, y: np.ndarray) -> float:
        return topo_1 - float(y[0])

    def cheio_2(_: float, y: np.ndarray) -> float:
        return topo_2 - float(y[1])

    eventos = [equalizou, vazio_1, vazio_2, cheio_1, cheio_2]
    for evento in eventos:
        evento.terminal, evento.direction = True, -1  # type: ignore[attr-defined]
    y0 = [t1.volume(t1.nivel_inicial_m), t2.volume(t2.nivel_inicial_m)]
    if duracao is None:
        q0 = abs(vazao(t1.nivel_inicial_m, t2.nivel_inicial_m)) + entrada
        limite = 400.0 * (min(topo_1, topo_2) / max(q0, 1e-9))
    else:
        if not (math.isfinite(duracao) and duracao > 0):
            raise ErroDoTanque("Informe uma duração maior que zero.")
        limite = duracao
    solucao = integrate.solve_ivp(
        derivada,
        (0.0, limite),
        y0,
        events=eventos,
        rtol=1e-9,
        atol=1e-10 * max(topo_1, topo_2),
        dense_output=True,
        max_step=limite / 400.0,
    )
    if not solucao.success:
        raise ErroDoTanque("A conta dos dois tanques não fechou: confira os dados.")
    fim = float(solucao.t[-1])
    nome_do_evento = ""
    nomes = ("equalizou", "vazio_1", "vazio_2", "cheio_1", "cheio_2")
    primeiro = math.inf
    for nome, ocorridos in zip(nomes, solucao.t_events, strict=True):
        if len(ocorridos) and float(ocorridos[0]) < primeiro and float(ocorridos[0]) > 0:
            primeiro, nome_do_evento = float(ocorridos[0]), nome
    if nome_do_evento:
        fim = primeiro
    avisos: list[str] = []
    if duracao is None and not nome_do_evento:
        avisos.append("Os níveis ainda mudam no fim da conta: informe uma duração maior.")
    if nome_do_evento.startswith("cheio"):
        avisos.append(
            f"O tanque {nome_do_evento[-1]} enche até o topo e transborda neste instante."
        )
    if nome_do_evento.startswith("vazio"):
        avisos.append(f"O tanque {nome_do_evento[-1]} esvazia antes de os níveis ficarem iguais.")
    tempos = np.linspace(0.0, fim, PONTOS)
    y = solucao.sol(tempos)
    h1 = np.array([t1.nivel(float(min(max(a, 0.0), topo_1))) for a in y[0]])
    h2 = np.array([t2.nivel(float(min(max(b, 0.0), topo_2))) for b in y[1]])
    q = np.array([vazao(a, b) for a, b in zip(h1, h2, strict=True)]) * 1000.0
    return ResultadoDosVasos(
        vasos=v,
        tempos=tempos,
        niveis_1=h1,
        niveis_2=h2,
        vazao=q,
        duracao=fim,
        evento=nome_do_evento,
        superficie_de_equilibrio=superficie_de_equilibrio(v) if entrada == 0 else None,
        avisos=tuple(avisos),
    )


def hipoteses_dos_vasos(r: ResultadoDosVasos) -> list[str]:
    return [
        "Líquido incompressível; a superfície de cada tanque fica plana e na pressão atmosférica.",
        "Escoamento quase permanente no tubo de ligação: a cada instante, o desnível entre as "
        "superfícies vira perda no tubo (Darcy-Weisbach, f por Colebrook), nas peças (ΣK) e na "
        "saída para o outro tanque; a inércia da água no tubo fica de fora.",
        "Os níveis contam como iguais com 1 mm de diferença: perto do fim o escoamento fica "
        "laminar, a vazão cai com o desnível e o último milímetro levaria um tempo sem fim.",
    ]
