"""Linha no tempo: a vazão subindo na partida e a água quente chegando num tubo frio.

**Partida (coluna rígida).** Um reservatório alimenta um tubo que descarrega livre; no instante zero
a válvula começa a abrir (ou a bomba começa a girar) e a coluna de líquido acelera:

    (L/(g·A))·dQ/dt = Δz + H_b(Q, s) − (1 + f·L/D + ΣK + K_v(t))·Q·|Q|/(2·g·A²)

com f de Darcy pela mesma conta do Montador de fluidos. A válvula abre em linha reta na área de
passagem, s = t/t_a, com K_v = K_aberta/s². A bomba segue a lei de semelhança com a rotação s:
H_b = s²·H_0 − (H_0/Q_máx²)·Q². A coluna rígida (Wylie e Streeter, cap. 2) despreza a
compressibilidade: vale quando a manobra é bem mais lenta que a ida e volta da onda, 2·L/a.

**Água quente chegando.** Água a outra temperatura entra num tubo parado: o fluido anda com a
velocidade média (transporte), troca calor com a parede pela película de dentro, e a parede guarda
calor e perde para fora pelo isolamento e pela película de fora. A cada passo de tempo o fluido anda
uma célula (Δt = Δx/v, transporte exato) e a troca de calor da célula com a parede é resolvida
exata no passo. h de dentro por Gnielinski (turbulento) ou Nu = 3,66 (laminar desenvolvido),
Incropera cap. 8. Em regime permanente a saída fica T_s = T_amb + (T_e − T_amb)·e^(−L/(ṁ·c·R')),
com R' das resistências em série (a mesma conta do tubo isolado do Montador térmico, mais a película
de dentro).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np
from scipy import integrate, linalg, optimize

from core.calor_no_tempo import Material, primeiro_cruzamento
from core.montador_funcoes import fator_de_atrito

GRAVIDADE = 9.81
VALVULA = "valvula"
BOMBA = "bomba"
EVENTOS = (VALVULA, BOMBA)
PONTOS = 1201


class ErroDaLinha(ValueError):
    """Dado que impede a conta; a mensagem diz o que corrigir."""


def _n(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


# =============================================================================================
# Partida
# =============================================================================================
@dataclass(frozen=True, slots=True)
class Linha:
    comprimento_m: float
    diametro_mm: float
    rugosidade_mm: float
    k_local: float  # ΣK das peças, sem a válvula que manobra
    desnivel_m: float  # nível do reservatório acima da saída (negativo: a saída fica acima)
    massa_especifica: float = 998.2
    viscosidade: float = 1.0016e-3
    evento: str = VALVULA
    tempo_manobra_s: float = 5.0  # abertura da válvula ou partida da bomba
    k_valvula: float = 0.17  # válvula aberta (gaveta)
    bomba_h0_m: float = 0.0  # altura a vazão zero; 0 = sem bomba
    bomba_qmax_L_s: float = 0.0  # vazão com altura zero
    celeridade_m_s: float = 1000.0  # só para conferir se a coluna rígida vale

    @property
    def area(self) -> float:
        return math.pi * (self.diametro_mm / 1000.0) ** 2 / 4.0

    @property
    def tem_bomba(self) -> bool:
        return self.bomba_h0_m > 0 and self.bomba_qmax_L_s > 0


def _abertura(linha: Linha, t: float) -> float:
    if linha.tempo_manobra_s <= 0:
        return 1.0
    return min(1.0, max(0.0, t / linha.tempo_manobra_s))


def altura_da_bomba(linha: Linha, q: float, s: float) -> float:
    if not linha.tem_bomba:
        return 0.0
    qmax = linha.bomba_qmax_L_s / 1000.0
    return linha.bomba_h0_m * s * s - linha.bomba_h0_m * q * abs(q) / (qmax * qmax)


def _coeficiente_de_perda(linha: Linha, q: float, s_valvula: float) -> float:
    """1 + f·L/D + ΣK + K_v: multiplica v²/(2g)."""
    d = linha.diametro_mm / 1000.0
    v = abs(q) / linha.area
    re = max(linha.massa_especifica * v * d / linha.viscosidade, 1e-9)
    f = float(fator_de_atrito(re, linha.rugosidade_mm / linha.diametro_mm))
    k_v = linha.k_valvula / max(s_valvula, 1e-6) ** 2
    return 1.0 + f * linha.comprimento_m / d + linha.k_local + k_v


def _residuo(linha: Linha, q: float, t: float) -> float:
    """Carga que sobra para acelerar a coluna (m)."""
    s_v = _abertura(linha, t) if linha.evento == VALVULA else 1.0
    s_b = _abertura(linha, t) if linha.evento == BOMBA else 1.0
    perda = _coeficiente_de_perda(linha, q, s_v) * q * abs(q) / (2.0 * GRAVIDADE * linha.area**2)
    return linha.desnivel_m + altura_da_bomba(linha, q, s_b) - perda


def vazao_permanente(linha: Linha) -> float | None:
    """Vazão com a manobra completa (m³/s); ``None`` se não escoa para a frente."""
    if _residuo(linha, 0.0, math.inf) <= 0:
        return None
    alto = 0.001
    while _residuo(linha, alto, math.inf) > 0:
        alto *= 2.0
        if alto > 1e4:
            return None
    return float(optimize.brentq(lambda q: _residuo(linha, q, math.inf), 0.0, alto, xtol=1e-12))


def problemas_da_partida(linha: Linha) -> list[str]:
    erros: list[str] = []
    for valor, nome in (
        (linha.comprimento_m, "o comprimento do tubo"),
        (linha.diametro_mm, "o diâmetro do tubo"),
        (linha.massa_especifica, "a massa específica do fluido"),
        (linha.viscosidade, "a viscosidade do fluido"),
        (linha.celeridade_m_s, "a velocidade da onda no tubo"),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {nome}, maior que zero.")
    if linha.evento not in EVENTOS:
        erros.append("Escolha o que acontece no instante zero: abrir a válvula ou ligar a bomba.")
    if linha.tempo_manobra_s < 0:
        erros.append("O tempo da manobra não pode ser negativo.")
    if linha.evento == BOMBA and not linha.tem_bomba:
        erros.append(
            "Para ligar a bomba, informe a altura com vazão zero e a vazão com altura zero."
        )
    if linha.k_local < 0 or linha.k_valvula < 0 or linha.rugosidade_mm < 0:
        erros.append("K e rugosidade não podem ser negativos.")
    if not erros and vazao_permanente(linha) is None:
        erros.append(
            "Com a manobra completa o líquido não escoa: o desnível mais a bomba não vencem nem a "
            "própria saída. Confira o desnível e a bomba."
        )
    return erros


@dataclass(frozen=True)
class ResultadoDaPartida:
    linha: Linha
    tempos: np.ndarray
    vazoes: np.ndarray  # L/s
    velocidades: np.ndarray  # m/s
    manobra: np.ndarray  # abertura da válvula ou rotação da bomba, %
    vazao_final: float  # L/s
    tempo_da_onda: float  # 2·L/a, s
    duracao: float
    avisos: tuple[str, ...] = ()

    def tempo_para(self, fracao: float) -> float | None:
        return primeiro_cruzamento(self.tempos, self.vazoes, fracao * self.vazao_final)


def calcular_partida(linha: Linha, duracao: float | None = None) -> ResultadoDaPartida:
    erros = problemas_da_partida(linha)
    if erros:
        raise ErroDaLinha(" ".join(erros))
    q_final = vazao_permanente(linha)
    assert q_final is not None
    inercia = linha.comprimento_m / (GRAVIDADE * linha.area)  # s/m²
    carga = linha.desnivel_m + (linha.bomba_h0_m if linha.tem_bomba else 0.0)
    tempo_coluna = inercia * q_final / max(carga, 1e-9)  # tempo de acelerar a coluna, s
    if duracao is None:
        limite = linha.tempo_manobra_s + 12.0 * tempo_coluna
    else:
        if not (math.isfinite(duracao) and duracao > 0):
            raise ErroDaLinha("Informe uma duração maior que zero.")
        limite = duracao

    def derivada(t: float, y: np.ndarray) -> list[float]:
        return [_residuo(linha, float(y[0]), t) / inercia]

    solucao = integrate.solve_ivp(
        derivada,
        (0.0, limite),
        [0.0],
        method="LSODA",
        rtol=1e-9,
        atol=1e-12,
        dense_output=True,
        max_step=max(limite / 400.0, 1e-6),
    )
    if not solucao.success:
        raise ErroDaLinha("A conta da partida não fechou: confira os dados da linha.")
    tempos = np.linspace(0.0, limite, PONTOS)
    vazoes = np.maximum(solucao.sol(tempos)[0], 0.0) * 1000.0
    if duracao is None:
        # corta quando a vazão já está a 0,1 % da final e a manobra acabou
        perto = np.nonzero(
            (np.abs(vazoes - q_final * 1000.0) < 1e-3 * q_final * 1000.0)
            & (tempos >= linha.tempo_manobra_s)
        )[0]
        if len(perto):
            fim = float(tempos[perto[0]]) * 1.15
            tempos = np.linspace(0.0, min(fim, limite), PONTOS)
            vazoes = np.maximum(solucao.sol(tempos)[0], 0.0) * 1000.0
    manobra = np.array([_abertura(linha, t) * 100.0 for t in tempos])
    onda = 2.0 * linha.comprimento_m / linha.celeridade_m_s
    avisos: list[str] = []
    if linha.tempo_manobra_s < 10.0 * onda:
        avisos.append(
            f"A manobra ({_n(linha.tempo_manobra_s, 1)} s) não é bem mais lenta que a ida e volta "
            f"da onda de pressão (2·L/a = {_n(onda, 2)} s). A coluna rígida não vê as ondas de "
            "pressão (golpe de aríete): as vazões valem, mas as pressões durante a manobra "
            "precisam da conta com a onda."
        )
    return ResultadoDaPartida(
        linha=linha,
        tempos=tempos,
        vazoes=vazoes,
        velocidades=vazoes / 1000.0 / linha.area,
        manobra=manobra,
        vazao_final=q_final * 1000.0,
        tempo_da_onda=onda,
        duracao=float(tempos[-1]),
        avisos=tuple(avisos),
    )


def hipoteses_da_partida(r: ResultadoDaPartida) -> list[str]:
    linha = r.linha
    linhas = [
        "Coluna rígida: o líquido é incompressível e o tubo não estica; toda a coluna acelera junta "
        "(Wylie e Streeter, cap. 2).",
        "Reservatório de nível constante e saída livre (a energia da velocidade sai no jato).",
        "Atrito de Darcy-Weisbach com o f do regime permanente na velocidade de cada instante.",
    ]
    if linha.evento == VALVULA:
        linhas.append(
            "A válvula abre em linha reta na área de passagem durante o tempo de abertura; a perda "
            "dela é K_aberta/s², com s a fração aberta."
        )
    else:
        linhas.append(
            "A bomba sobe a rotação em linha reta durante a partida; a curva dela segue a lei de "
            "semelhança (H ∝ n²), a partir de H_0 e Q_máx."
        )
    return linhas


# =============================================================================================
# Água quente chegando
# =============================================================================================
@cache
def propriedades_da_agua(t_c: float) -> tuple[float, float, float, float]:
    """ρ (kg/m³), μ (Pa·s), c_p (J/(kg·K)) e k (W/(m·K)) da água líquida a 1 atm (CoolProp)."""
    import CoolProp.CoolProp as cp  # noqa: N813

    t = min(max(t_c, 0.5), 99.0) + 273.15
    return tuple(  # type: ignore[return-value]
        float(cp.PropsSI(nome, "T", t, "P", 101325.0, "Water")) for nome in ("D", "V", "C", "L")
    )


@dataclass(frozen=True, slots=True)
class TuboAquecendo:
    comprimento_m: float
    diametro_mm: float  # interno
    parede_mm: float
    material: Material
    isolamento_mm: float
    k_isolamento: float
    h_externo: float
    t_ambiente: float
    vazao_L_s: float
    t_inicial: float  # tubo e água parada
    t_entrada: float  # água que passa a entrar no instante zero


def coeficiente_interno(tubo: TuboAquecendo) -> tuple[float, float, str]:
    """h de dentro (W/(m²·K)), Re e a correlação usada."""
    rho, mu, cp, k = propriedades_da_agua(0.5 * (tubo.t_entrada + tubo.t_inicial))
    d = tubo.diametro_mm / 1000.0
    v = tubo.vazao_L_s / 1000.0 / (math.pi * d * d / 4.0)
    re = rho * v * d / mu
    pr = mu * cp / k
    if re >= 3000.0:
        f = (0.790 * math.log(re) - 1.64) ** -2
        nu = (
            (f / 8.0)
            * (re - 1000.0)
            * pr
            / (1.0 + 12.7 * math.sqrt(f / 8.0) * (pr ** (2.0 / 3.0) - 1.0))
        )
        nome = "Gnielinski (Incropera, eq. 8.62)"
    else:
        nu = 3.66
        nome = "laminar desenvolvido, Nu = 3,66 (Incropera, eq. 8.55)"
    return nu * k / d, re, nome


@dataclass(frozen=True)
class ResultadoDoTubo:
    tubo: TuboAquecendo
    x: np.ndarray  # posição do meio de cada célula, m
    tempos: np.ndarray  # dos quadros, s
    fluido: np.ndarray  # quadros × células, °C
    parede: np.ndarray
    tempos_saida: np.ndarray  # todos os passos
    saida: np.ndarray  # temperatura na saída, todos os passos
    saida_permanente: float
    perda_permanente_W: float
    h_interno: float
    reynolds: float
    correlacao: str
    velocidade: float
    duracao: float
    avisos: tuple[str, ...] = ()

    def tempo_para(self, alvo: float) -> float | None:
        return primeiro_cruzamento(self.tempos_saida, self.saida, alvo)

    def tempo_para_estabilizar(self) -> float | None:
        """Quando a saída fica a 1 % do regime permanente e não sai mais dali."""
        from core.calor_no_tempo import TOLERANCIA, primeiro_abaixo_de_vez

        salto = abs(self.saida_permanente - self.tubo.t_inicial)
        if salto <= 0:
            return 0.0
        desvio = np.abs(self.saida - self.saida_permanente)
        return primeiro_abaixo_de_vez(self.tempos_saida, desvio, TOLERANCIA * salto)

    def volume_ate(self, alvo: float) -> float | None:
        """Litros que saem até a saída chegar à temperatura pedida."""
        t = self.tempo_para(alvo)
        return None if t is None else t * self.tubo.vazao_L_s


def problemas_do_tubo(tubo: TuboAquecendo) -> list[str]:
    erros: list[str] = []
    for valor, nome in (
        (tubo.comprimento_m, "o comprimento do tubo"),
        (tubo.diametro_mm, "o diâmetro interno"),
        (tubo.parede_mm, "a espessura da parede"),
        (tubo.vazao_L_s, "a vazão"),
        (tubo.h_externo, "o h de fora"),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {nome}, maior que zero.")
    if tubo.isolamento_mm < 0:
        erros.append("A espessura do isolamento não pode ser negativa (0 = sem isolamento).")
    if tubo.isolamento_mm > 0 and not tubo.k_isolamento > 0:
        erros.append("Informe a condutividade do isolamento, maior que zero.")
    for valor in (tubo.t_inicial, tubo.t_entrada):
        if not 0 < valor < 100:
            erros.append("A água a 1 atm é líquida entre 0 e 100 °C: confira as temperaturas.")
            break
    return erros


def resistencia_de_fora(tubo: TuboAquecendo) -> float:
    """R' da parede para o ar, por metro (m·K/W): isolamento + película de fora."""
    r_e = (tubo.diametro_mm / 2.0 + tubo.parede_mm) / 1000.0
    r_iso = r_e + tubo.isolamento_mm / 1000.0
    isolamento = (
        math.log(r_iso / r_e) / (2.0 * math.pi * tubo.k_isolamento)
        if tubo.isolamento_mm > 0
        else 0.0
    )
    return isolamento + 1.0 / (2.0 * math.pi * r_iso * tubo.h_externo)


def calcular_tubo(
    tubo: TuboAquecendo, duracao: float | None = None, *, celulas: int = 240
) -> ResultadoDoTubo:
    erros = problemas_do_tubo(tubo)
    if erros:
        raise ErroDaLinha(" ".join(erros))
    rho, _, cp, _ = propriedades_da_agua(0.5 * (tubo.t_entrada + tubo.t_inicial))
    d = tubo.diametro_mm / 1000.0
    area = math.pi * d * d / 4.0
    v = tubo.vazao_L_s / 1000.0 / area
    h_i, re, correlacao = coeficiente_interno(tubo)
    g_i = h_i * math.pi * d  # W/(m·K)
    g_e = 1.0 / resistencia_de_fora(tubo)
    r_e = d / 2.0 + tubo.parede_mm / 1000.0
    c_f = rho * cp * area  # J/(m·K)
    c_w = (
        tubo.material.massa_especifica
        * tubo.material.calor_especifico
        * math.pi
        * (r_e**2 - (d / 2.0) ** 2)
    )
    dx = tubo.comprimento_m / celulas
    dt = dx / v
    m = np.array([[-g_i / c_f, g_i / c_f], [g_i / c_w, -(g_i + g_e) / c_w]])
    passo = linalg.expm(m * dt)
    transito = tubo.comprimento_m / v
    tau_parede = c_w / (g_i + g_e)
    if duracao is None:
        duracao = 2.0 * transito + 8.0 * tau_parede
    if not (math.isfinite(duracao) and duracao > 0):
        raise ErroDaLinha("Informe uma duração maior que zero.")
    passos = max(1, math.ceil(duracao / dt))
    avisos: list[str] = []
    if passos > 200_000:
        passos = 200_000
        avisos.append("Duração longa demais para o passo da conta: o tempo mostrado foi encurtado.")
    quadros = 151
    guardar = np.unique(np.linspace(0, passos, quadros).round().astype(int))
    fluido = np.full(celulas, tubo.t_inicial) - tubo.t_ambiente
    parede = np.full(celulas, tubo.t_inicial) - tubo.t_ambiente
    entrada = tubo.t_entrada - tubo.t_ambiente
    saida = np.empty(passos + 1)
    saida[0] = tubo.t_inicial
    q_fluido = np.empty((len(guardar), celulas))
    q_parede = np.empty((len(guardar), celulas))
    k = 0
    if guardar[0] == 0:
        q_fluido[0], q_parede[0] = fluido + tubo.t_ambiente, parede + tubo.t_ambiente
        k = 1
    for i in range(1, passos + 1):
        fluido = np.concatenate(([entrada], fluido[:-1]))  # anda uma célula
        novo_f = passo[0, 0] * fluido + passo[0, 1] * parede
        parede = passo[1, 0] * fluido + passo[1, 1] * parede
        fluido = novo_f
        saida[i] = fluido[-1] + tubo.t_ambiente
        if k < len(guardar) and guardar[k] == i:
            q_fluido[k], q_parede[k] = fluido + tubo.t_ambiente, parede + tubo.t_ambiente
            k += 1
    massa = rho * tubo.vazao_L_s / 1000.0
    r_total = 1.0 / g_i + 1.0 / g_e
    permanente = tubo.t_ambiente + entrada * math.exp(-tubo.comprimento_m / (massa * cp * r_total))
    perda = massa * cp * (tubo.t_entrada - permanente)
    if 2300.0 <= re < 3000.0:
        avisos.append(
            f"Re = {re:.0f}: o escoamento está na transição entre laminar e turbulento, onde o h "
            "de dentro não é bem definido."
        )
    return ResultadoDoTubo(
        tubo=tubo,
        x=(np.arange(celulas) + 0.5) * dx,
        tempos=guardar * dt,
        fluido=q_fluido,
        parede=q_parede,
        tempos_saida=np.arange(passos + 1) * dt,
        saida=saida,
        saida_permanente=permanente,
        perda_permanente_W=perda,
        h_interno=h_i,
        reynolds=re,
        correlacao=correlacao,
        velocidade=v,
        duracao=passos * dt,
        avisos=tuple(avisos),
    )


def hipoteses_do_tubo(r: ResultadoDoTubo) -> list[str]:
    return [
        "Água com a velocidade média em toda a seção (sem perfil de velocidade nem mistura ao longo "
        "do tubo); propriedades da CoolProp na média das duas temperaturas.",
        f"Película de dentro por {r.correlacao}, com Re = {r.reynolds:.0f}.",
        "Parede do tubo com a temperatura igual na espessura (metal fino) e capacidade de calor; o "
        "isolamento só resiste, sem guardar calor.",
        "Ar de fora a temperatura constante, com h de fora constante.",
    ]
