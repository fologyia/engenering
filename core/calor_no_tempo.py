"""Calor no tempo numa parede, num cilindro (maciço ou tubo) ou numa esfera (maciça ou oca).

A peça começa a uma temperatura só e, de repente, cada face passa a ter uma condição: ar ou líquido
em volta (convecção, h e T∞), temperatura fixa, fluxo de calor que entra ou isolada. A conta dá a
temperatura em cada ponto da espessura em cada instante, até quase estabilizar.

Método: volumes finitos na espessura (nós nas faces e entre elas) e Crank–Nicolson no tempo, com os
quatro primeiros passos implícitos (partida de Rannacher), que amortecem o salto do instante zero.
A duração automática sai do modo mais lento da própria malha: o maior tempo de resposta τ, e a peça
fica a 1 % do regime permanente em ln(100)·τ.

Conferência: quando o caso é o dos livros (parede com as duas faces iguais, ou uma isolada e a outra
com convecção; cilindro ou esfera maciços com convecção ou temperatura fixa na superfície), a
página compara com a solução exata em série (Incropera, 6ª ed., seção 5.5; Çengel, cap. 4).

Unidades: SI. Medidas de entrada em mm, temperaturas em °C, tempo em s. Parede: por m² de face;
cilindro: por metro de comprimento; esfera: a peça inteira.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np
from scipy import linalg, optimize, special

PAREDE = "parede"
CILINDRO = "cilindro"
ESFERA = "esfera"
FORMAS = (PAREDE, CILINDRO, ESFERA)

CONVECCAO = "conveccao"
TEMPERATURA = "temperatura"
FLUXO = "fluxo"
ISOLADA = "isolada"
CONDICOES = (CONVECCAO, TEMPERATURA, FLUXO, ISOLADA)

#: Nós na espessura. 81 nós dão erro bem abaixo de 0,1 °C nos casos conferidos.
NOS = 81
PASSOS = 3000
#: Fração do caminho até o regime permanente que a duração automática alcança: ln(250)·τ. Um
#: pouco além de 99 %, porque o primeiro modo começa com amplitude maior que 1 no centro (Heisler:
#: A₁ até 1,6), e assim o instante em que a peça inteira fica a 1 % do regime cabe no gráfico.
ESTABILIZADO = 0.996
BIOT_UNIFORME = 0.1
FONTE_MATERIAIS = "Incropera et al., Fundamentos de Transferência de Calor e de Massa, 6ª ed., Tab. A.1 e A.3 (300 K)"


class ErroDoCalor(ValueError):
    """Dado que impede a conta; a mensagem diz o que corrigir."""


@dataclass(frozen=True, slots=True)
class Material:
    nome: str
    condutividade: float  # k, W/(m·K)
    massa_especifica: float  # ρ, kg/m³
    calor_especifico: float  # c_p, J/(kg·K)
    fonte: str = FONTE_MATERIAIS

    @property
    def difusividade(self) -> float:
        """α = k/(ρ·c_p), m²/s."""
        return self.condutividade / (self.massa_especifica * self.calor_especifico)


def _m(nome: str, rho: float, cp: float, k: float) -> Material:
    return Material(nome, k, rho, cp)


#: Propriedades a 300 K (Incropera, Tab. A.1 metais e A.3 não metálicos).
MATERIAIS: dict[str, Material] = {
    m.nome: m
    for m in (
        _m("Aço carbono comum", 7854.0, 434.0, 60.5),
        _m("Aço AISI 1010", 7832.0, 434.0, 63.9),
        _m("Aço inoxidável AISI 304", 7900.0, 477.0, 14.9),
        _m("Aço inoxidável AISI 316", 8238.0, 468.0, 13.4),
        _m("Alumínio puro", 2702.0, 903.0, 237.0),
        _m("Alumínio 2024-T6", 2770.0, 875.0, 177.0),
        _m("Cobre puro", 8933.0, 385.0, 401.0),
        _m("Latão (70 Cu, 30 Zn)", 8530.0, 380.0, 110.0),
        _m("Titânio Ti-6Al-4V", 4420.0, 610.0, 7.1),
        _m("Concreto (com brita)", 2300.0, 880.0, 1.4),
        _m("Tijolo comum", 1920.0, 835.0, 0.72),
        _m("Vidro (placa)", 2500.0, 750.0, 1.4),
        _m("Madeira de carvalho (transversal)", 545.0, 2385.0, 0.17),
        _m("Madeira de pinho (transversal)", 640.0, 2805.0, 0.15),
    )
}


@dataclass(frozen=True, slots=True)
class Face:
    """Condição numa face a partir do instante zero."""

    tipo: str = ISOLADA
    h: float = 0.0  # W/(m²·K), convecção
    t_fluido: float = 20.0  # °C, convecção
    t_fixa: float = 20.0  # °C, temperatura fixa
    fluxo: float = 0.0  # W/m², positivo entrando na peça

    def descricao(self) -> str:
        if self.tipo == CONVECCAO:
            return (
                f"convecção com h = {_n(self.h, 1)} W/(m²·K) e fluido a {_n(self.t_fluido, 1)} °C"
            )
        if self.tipo == TEMPERATURA:
            return f"temperatura fixa de {_n(self.t_fixa, 1)} °C"
        if self.tipo == FLUXO:
            return f"fluxo de calor de {_n(self.fluxo, 1)} W/m² entrando"
        return "isolada"


@dataclass(frozen=True, slots=True)
class Peca:
    """``forma``: parede, cilindro ou esfera. Parede: ``espessura_mm``; cilindro e esfera:
    ``diametro_mm`` (de fora) e ``diametro_interno_mm`` (0 = maciço).

    ``face_a``: parede, face da esquerda (x = 0); tubo e esfera oca, a face de dentro.
    ``face_b``: parede, face da direita; cilindro e esfera, a face de fora."""

    forma: str
    material: Material
    t_inicial: float
    face_a: Face
    face_b: Face
    espessura_mm: float = 0.0
    diametro_mm: float = 0.0
    diametro_interno_mm: float = 0.0

    @property
    def macica(self) -> bool:
        return self.forma != PAREDE and self.diametro_interno_mm <= 0.0

    @property
    def r0(self) -> float:
        if self.forma == PAREDE:
            return 0.0
        return max(0.0, self.diametro_interno_mm) / 2000.0

    @property
    def r1(self) -> float:
        if self.forma == PAREDE:
            return self.espessura_mm / 1000.0
        return self.diametro_mm / 2000.0

    @property
    def unidade_de_calor(self) -> str:
        return {PAREDE: "J/m²", CILINDRO: "J/m", ESFERA: "J"}[self.forma]


def problemas(p: Peca) -> list[str]:
    erros: list[str] = []
    if p.forma not in FORMAS:
        erros.append("Escolha a forma da peça: parede, cilindro ou esfera.")
        return erros
    mat = p.material
    for valor, rotulo in (
        (mat.condutividade, "a condutividade k"),
        (mat.massa_especifica, "a massa específica ρ"),
        (mat.calor_especifico, "o calor específico c_p"),
    ):
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"Informe {rotulo} do material, maior que zero.")
    if p.forma == PAREDE:
        if not p.espessura_mm > 0:
            erros.append("Informe a espessura da parede, maior que zero.")
    else:
        if not p.diametro_mm > 0:
            erros.append("Informe o diâmetro de fora, maior que zero.")
        elif p.diametro_interno_mm >= p.diametro_mm:
            erros.append("O diâmetro de dentro precisa ser menor que o de fora.")
        elif p.diametro_interno_mm < 0:
            erros.append("O diâmetro de dentro não pode ser negativo (0 = peça maciça).")
    faces = [("da direita" if p.forma == PAREDE else "de fora", p.face_b)]
    if not p.macica:
        faces.insert(0, ("da esquerda" if p.forma == PAREDE else "de dentro", p.face_a))
    for nome, face in faces:
        if face.tipo not in CONDICOES:
            erros.append(f"Escolha o que acontece na face {nome}.")
        elif face.tipo == CONVECCAO and not face.h > 0:
            erros.append(f"Face {nome}: informe o coeficiente h, maior que zero.")
    for valor in (
        p.t_inicial,
        p.face_a.t_fluido,
        p.face_b.t_fluido,
        p.face_a.t_fixa,
        p.face_b.t_fixa,
    ):
        if not math.isfinite(valor) or valor < -273.15:
            erros.append(
                "As temperaturas precisam ser números acima do zero absoluto (−273,15 °C)."
            )
            break
    return erros


# ---------------------------------------------------------------------------------------------
# Malha e matrizes
# ---------------------------------------------------------------------------------------------
def _area(forma: str, r: np.ndarray | float) -> np.ndarray:
    r = np.asarray(r, dtype=float)
    if forma == PAREDE:
        return np.ones_like(r)
    if forma == CILINDRO:
        return 2.0 * np.pi * r
    return 4.0 * np.pi * r**2


def _volume(forma: str, ra: np.ndarray, rb: np.ndarray) -> np.ndarray:
    if forma == PAREDE:
        return rb - ra
    if forma == CILINDRO:
        return np.pi * (rb**2 - ra**2)
    return 4.0 / 3.0 * np.pi * (rb**3 - ra**3)


@dataclass(frozen=True, slots=True)
class _Sistema:
    r: np.ndarray
    capacidade: np.ndarray  # C_i = ρ·c·V_i, J/K
    condutancia: np.ndarray  # G entre i e i+1, W/K
    diagonal_extra: np.ndarray  # h·A nas faces com convecção
    fonte: np.ndarray  # h·A·T∞ + q·A
    fixos: dict[int, float]  # nó → temperatura fixa


def _sistema(p: Peca, nos: int) -> _Sistema:
    r = np.linspace(p.r0, p.r1, nos)
    dr = r[1] - r[0]
    meio = (r[:-1] + r[1:]) / 2.0
    ra = np.concatenate(([r[0]], meio))
    rb = np.concatenate((meio, [r[-1]]))
    mat = p.material
    capacidade = mat.massa_especifica * mat.calor_especifico * _volume(p.forma, ra, rb)
    condutancia = mat.condutividade * _area(p.forma, meio) / dr
    extra = np.zeros(nos)
    fonte = np.zeros(nos)
    fixos: dict[int, float] = {}
    for no, face, raio in ((0, p.face_a, r[0]), (nos - 1, p.face_b, r[-1])):
        area = float(_area(p.forma, raio))
        if area <= 0.0 or (no == 0 and p.macica):
            continue  # centro do cilindro ou da esfera maciços: simetria
        if face.tipo == CONVECCAO:
            extra[no] += face.h * area
            fonte[no] += face.h * area * face.t_fluido
        elif face.tipo == TEMPERATURA:
            fixos[no] = face.t_fixa
        elif face.tipo == FLUXO:
            fonte[no] += face.fluxo * area
    return _Sistema(r, capacidade, condutancia, extra, fonte, fixos)


def _rigidez(s: _Sistema) -> tuple[np.ndarray, np.ndarray]:
    """Diagonal e fora da diagonal de K (simétrica, tridiagonal): C·dT/dt = −K·T + f."""
    n = len(s.r)
    d = np.zeros(n)
    d[:-1] += s.condutancia
    d[1:] += s.condutancia
    d += s.diagonal_extra
    return d, -s.condutancia.copy()


def _regime_permanente(s: _Sistema) -> np.ndarray | None:
    d, e = _rigidez(s)
    n = len(d)
    if not s.fixos and not np.any(s.diagonal_extra > 0):
        return None  # sem convecção nem temperatura fixa: não estabiliza
    banda = np.zeros((3, n))
    banda[0, 1:] = e
    banda[1] = d
    banda[2, :-1] = e
    f = s.fonte.copy()
    for no, t in s.fixos.items():
        banda[1, no] = 1.0
        if no > 0:
            banda[2, no - 1] = 0.0  # linha do nó fixo: só a diagonal
        if no < n - 1:
            banda[0, no + 1] = 0.0
        f[no] = t
    return linalg.solve_banded((1, 1), banda, f)


def constante_de_tempo(s: _Sistema) -> float | None:
    """O maior tempo de resposta da peça (1/λ do modo mais lento), em segundos."""
    d, e = _rigidez(s)
    livres = np.array([i for i in range(len(d)) if i not in s.fixos])
    if len(livres) == 0:
        return None
    # K·v = λ·C·v → C^-1/2·K·C^-1/2, também tridiagonal, só com os nós livres
    escala = 1.0 / np.sqrt(s.capacidade[livres])
    dd = d[livres] * escala**2
    vizinhos = np.diff(livres) == 1
    ee = np.where(vizinhos, e[livres[:-1]] * escala[:-1] * escala[1:], 0.0)
    if len(dd) == 1:
        menor = float(dd[0])
    else:
        menor = float(
            linalg.eigh_tridiagonal(dd, ee, eigvals_only=True, select="i", select_range=(0, 0))[0]
        )
    if menor <= 1e-14 * max(1.0, float(np.max(dd))):
        return None
    return 1.0 / menor


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Ponto:
    nome: str
    indice: int
    posicao_mm: float


@dataclass(frozen=True)
class ResultadoDoCalor:
    peca: Peca
    r: np.ndarray  # posição de cada nó, m
    tempos: np.ndarray  # todos os passos, s
    temperaturas: np.ndarray  # passos × nós, °C
    permanente: np.ndarray | None
    tau: float | None
    duracao: float
    automatica: bool
    capacidade: np.ndarray
    pontos: tuple[Ponto, ...]
    biot: float | None  # Bi com L_c = V/A das faces com convecção
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def posicoes_mm(self) -> np.ndarray:
        return self.r * 1000.0

    @property
    def uniforme(self) -> bool:
        """A peça esquenta por igual (Bi < 0,1): vale a capacitância concentrada."""
        return self.biot is not None and self.biot < BIOT_UNIFORME

    def energia(self) -> np.ndarray:
        """Calor guardado na peça desde o instante zero, por passo (J/m², J/m ou J)."""
        return (self.temperaturas - self.peca.t_inicial) @ self.capacidade

    def energia_final(self) -> float | None:
        if self.permanente is None:
            return None
        return float((self.permanente - self.peca.t_inicial) @ self.capacidade)

    def serie(self, ponto: Ponto) -> np.ndarray:
        return self.temperaturas[:, ponto.indice]

    def ponto(self, nome: str) -> Ponto:
        for p in self.pontos:
            if p.nome == nome:
                return p
        raise KeyError(nome)

    def tempo_para(self, ponto: Ponto, alvo: float) -> float | None:
        """Primeiro instante em que o ponto chega à temperatura pedida; ``None`` se não chega."""
        return primeiro_cruzamento(self.tempos, self.serie(ponto), alvo)


def primeiro_cruzamento(tempos: np.ndarray, valores: np.ndarray, alvo: float) -> float | None:
    v = np.asarray(valores, dtype=float) - alvo
    if v[0] == 0:
        return float(tempos[0])
    troca = np.nonzero(np.sign(v[1:]) != np.sign(v[0]))[0]
    if len(troca) == 0:
        return None
    i = int(troca[0])
    a, b = v[i], v[i + 1]
    fracao = a / (a - b) if a != b else 0.0
    return float(tempos[i] + fracao * (tempos[i + 1] - tempos[i]))


def nomes_dos_pontos(forma: str, macica: bool) -> tuple[str, str, str]:
    """Os três pontos acompanhados: as duas faces e o meio (no maciço, centro, meio raio e face)."""
    if forma == PAREDE:
        return ("Face da esquerda", "Meio da parede", "Face da direita")
    if macica:
        return ("Centro", "Metade do raio", "Superfície")
    return ("Face de dentro", "Meio da parede", "Face de fora")


#: Fração do salto de temperatura que conta como "estável" e como "por igual": 1 %.
TOLERANCIA = 0.01


def primeiro_abaixo_de_vez(tempos: np.ndarray, valores: np.ndarray, limite: float) -> float | None:
    """Instante a partir do qual a série fica abaixo do limite até o fim; ``None`` se no fim ela
    ainda está acima."""
    v = np.asarray(valores, dtype=float)
    acima = np.nonzero(v > limite)[0]
    if len(acima) == 0:
        return float(tempos[0])
    i = int(acima[-1])
    if i >= len(v) - 1:
        return None
    a, b = v[i] - limite, v[i + 1] - limite
    fracao = a / (a - b) if a != b else 1.0
    return float(tempos[i] + fracao * (tempos[i + 1] - tempos[i]))


@dataclass(frozen=True, slots=True)
class Marcos:
    """Os tempos que a página marca: estabilizar, equalizar e a maior diferença dentro da peça."""

    estabiliza: float | None  # toda a peça a 1 % do regime permanente (s)
    equaliza: float | None  # a diferença dentro da peça cai a 1 % do salto e não volta (s)
    gradiente_de_regime: float | None  # diferença dentro da peça no regime permanente (°C)
    maior_diferenca: float  # a maior diferença dentro da peça no tempo mostrado (°C)
    quando_maior: float  # instante dela (s)
    salto: float  # quanto a temperatura muda do começo ao regime (°C)

    @property
    def equaliza_no_regime(self) -> bool:
        """O regime permanente é por igual (a peça termina toda na mesma temperatura)."""
        return (
            self.gradiente_de_regime is not None
            and self.gradiente_de_regime <= TOLERANCIA * max(self.salto, 1e-12)
        )


def marcos_da_serie(
    tempos: np.ndarray,
    maxima: np.ndarray,
    minima: np.ndarray,
    desvio: np.ndarray | None,
    permanente: np.ndarray | None,
    t_inicial: float,
    final: np.ndarray,
) -> Marcos:
    """Marcos a partir da maior e da menor temperatura em cada passo e do desvio para o regime."""
    diferenca = np.asarray(maxima) - np.asarray(minima)
    k = int(np.argmax(diferenca))
    estabiliza = equaliza = gradiente = None
    if permanente is not None:
        salto = float(np.max(np.abs(permanente - t_inicial)))
        gradiente = float(np.max(permanente) - np.min(permanente))
        if desvio is not None and salto > 0:
            estabiliza = primeiro_abaixo_de_vez(tempos, desvio, TOLERANCIA * salto)
        if salto > 0 and gradiente <= TOLERANCIA * salto:
            equaliza = primeiro_abaixo_de_vez(tempos, diferenca, TOLERANCIA * salto)
    else:
        salto = float(np.max(np.abs(final - t_inicial)))
    return Marcos(estabiliza, equaliza, gradiente, float(diferenca[k]), float(tempos[k]), salto)


def marcos(r: ResultadoDoCalor) -> Marcos:
    t = r.temperaturas
    desvio = None if r.permanente is None else np.max(np.abs(t - r.permanente), axis=1)
    return marcos_da_serie(
        r.tempos, t.max(axis=1), t.min(axis=1), desvio, r.permanente, r.peca.t_inicial, t[-1]
    )


def fluxos_nas_faces(r: ResultadoDoCalor) -> tuple[np.ndarray, np.ndarray]:
    """Calor que entra em cada face a cada passo (W/m², positivo entrando): face_a e face_b."""
    p = r.peca
    t = r.temperaturas
    dr = r.r[1] - r.r[0]

    def face(f: Face, no: int, vizinho: int) -> np.ndarray:
        if f.tipo == CONVECCAO:
            return f.h * (f.t_fluido - t[:, no])
        if f.tipo == FLUXO:
            return np.full(len(t), f.fluxo)
        if f.tipo == TEMPERATURA:
            meio = 0.5 * (r.r[no] + r.r[vizinho])
            area = float(_area(p.forma, r.r[no]))
            if area <= 0:
                return np.zeros(len(t))
            g = p.material.condutividade * float(_area(p.forma, meio)) / dr
            # o nó da face fica fixo: o que entra por ela é o que ele conduz para dentro
            return g * (t[:, no] - t[:, vizinho]) / area
        return np.zeros(len(t))

    n = len(r.r)
    q_a = np.zeros(len(t)) if p.macica else face(p.face_a, 0, 1)
    return q_a, face(p.face_b, n - 1, n - 2)


def _pontos(p: Peca, r: np.ndarray) -> tuple[Ponto, ...]:
    n = len(r)
    meio = n // 2
    nomes = nomes_dos_pontos(p.forma, p.macica)
    return tuple(
        Ponto(nome, i, float(r[i] * 1000.0))
        for nome, i in zip(nomes, (0, meio, n - 1), strict=True)
    )


def _biot(p: Peca, s: _Sistema) -> float | None:
    area_h = float(np.sum(s.diagonal_extra))  # Σ h·A
    if area_h <= 0 or s.fixos:
        return None
    areas = [
        float(_area(p.forma, raio))
        for no, face, raio in ((0, p.face_a, p.r0), (len(s.r) - 1, p.face_b, p.r1))
        if face.tipo == CONVECCAO and not (no == 0 and p.macica)
    ]
    area = sum(areas)
    volume = float(_volume(p.forma, np.array([p.r0]), np.array([p.r1]))[0])
    h_medio = area_h / area
    return h_medio * (volume / area) / p.material.condutividade


def calcular(
    p: Peca,
    duracao: float | None = None,
    *,
    nos: int = NOS,
    passos: int = PASSOS,
) -> ResultadoDoCalor:
    """``duracao`` em segundos; ``None`` = até um pouco depois de a peça estabilizar."""
    erros = problemas(p)
    if erros:
        raise ErroDoCalor(" ".join(erros))
    if p.macica:
        p = replace(p, face_a=Face(ISOLADA))
    s = _sistema(p, nos)
    permanente = _regime_permanente(s)
    tau = constante_de_tempo(s)
    avisos: list[str] = []
    automatica = duracao is None
    if duracao is None:
        if tau is not None and permanente is not None:
            duracao = math.log(1.0 / (1.0 - ESTABILIZADO)) * tau
        else:
            espessura = p.r1 - p.r0
            duracao = 2.0 * espessura**2 / p.material.difusividade
            avisos.append(
                "Sem convecção nem temperatura fixa em nenhuma face, a peça não chega a um regime "
                "permanente: com fluxo entrando a temperatura sobe sem parar. A duração mostrada é "
                "a de 2·e²/α."
            )
    if not (math.isfinite(duracao) and duracao > 0):
        raise ErroDoCalor("Informe uma duração maior que zero.")
    if not s.fixos and not np.any(s.diagonal_extra > 0) and not np.any(s.fonte != 0):
        avisos.append("Todas as faces estão isoladas e sem fluxo: a temperatura não muda.")

    d, e = _rigidez(s)
    n = len(d)
    dt = duracao / passos
    c = s.capacidade
    temperaturas = np.empty((passos + 1, n))
    t_atual = np.full(n, float(p.t_inicial))
    temperaturas[0] = t_atual
    bandas: dict[float, np.ndarray] = {}

    def lado_esquerdo(theta: float) -> np.ndarray:
        if theta not in bandas:
            banda = np.zeros((3, n))
            banda[0, 1:] = theta * e
            banda[1] = c / dt + theta * d
            banda[2, :-1] = theta * e
            for no in s.fixos:
                banda[1, no] = 1.0
                if no > 0:
                    banda[2, no - 1] = 0.0
                if no < n - 1:
                    banda[0, no + 1] = 0.0
            bandas[theta] = banda
        return bandas[theta]

    for passo in range(1, passos + 1):
        theta = 1.0 if passo <= 4 else 0.5
        kt = d * t_atual
        kt[:-1] += e * t_atual[1:]
        kt[1:] += e * t_atual[:-1]
        direito = c / dt * t_atual - (1.0 - theta) * kt + s.fonte
        for no, t_fixa in s.fixos.items():
            direito[no] = t_fixa
        t_atual = linalg.solve_banded((1, 1), lado_esquerdo(theta), direito)
        temperaturas[passo] = t_atual
    if not np.all(np.isfinite(temperaturas)):
        raise ErroDoCalor("A conta deu um valor que não é número: confira os dados.")

    biot = _biot(p, s)
    return ResultadoDoCalor(
        peca=p,
        r=s.r,
        tempos=np.linspace(0.0, duracao, passos + 1),
        temperaturas=temperaturas,
        permanente=permanente,
        tau=tau,
        duracao=float(duracao),
        automatica=automatica,
        capacidade=c,
        pontos=_pontos(p, s.r),
        biot=biot,
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------------------------
# Solução exata em série (o caso dos livros), para conferir
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CasoDeLivro:
    forma: str
    meia_espessura: float  # L (parede) ou r_o (cilindro, esfera), m
    biot: float  # h·L/k; math.inf = temperatura fixa na face
    t_inicial: float
    t_fluido: float
    origem_mm: float  # posição do centro na coordenada da peça (parede: o plano de simetria)
    alpha: float


def caso_de_livro(p: Peca) -> CasoDeLivro | None:
    """O caso com solução exata em série, se a peça é um deles."""
    mat = p.material

    def biot_da(face: Face, comprimento: float) -> tuple[float, float] | None:
        if face.tipo == CONVECCAO:
            return face.h * comprimento / mat.condutividade, face.t_fluido
        if face.tipo == TEMPERATURA:
            return math.inf, face.t_fixa
        return None

    if p.forma == PAREDE:
        e = p.espessura_mm / 1000.0
        a, b = p.face_a, p.face_b
        if a == b and a.tipo in (CONVECCAO, TEMPERATURA):
            dados = biot_da(a, e / 2.0)
            centro = p.espessura_mm / 2.0
            meia = e / 2.0
        elif a.tipo == ISOLADA and b.tipo in (CONVECCAO, TEMPERATURA):
            dados, centro, meia = biot_da(b, e), 0.0, e
        elif b.tipo == ISOLADA and a.tipo in (CONVECCAO, TEMPERATURA):
            dados, centro, meia = biot_da(a, e), p.espessura_mm, e
        else:
            return None
    elif p.macica and p.face_b.tipo in (CONVECCAO, TEMPERATURA):
        meia = p.diametro_mm / 2000.0
        dados, centro = biot_da(p.face_b, meia), 0.0
    else:
        return None
    if dados is None:
        return None
    return CasoDeLivro(p.forma, meia, dados[0], p.t_inicial, dados[1], centro, mat.difusividade)


def _equacao_das_raizes(forma: str, biot: float):  # noqa: ANN202
    """Função cujas raízes positivas são os ζ_n; sem polos, para isolar com segurança."""
    if forma == PAREDE:
        if math.isinf(biot):
            return lambda z: np.cos(z)
        return (
            (lambda z: z * np.sin(z) - biot * np.cos(z))
            if biot <= 1
            else (lambda z: z * np.sin(z) / biot - np.cos(z))
        )
    if forma == CILINDRO:
        if math.isinf(biot):
            return lambda z: special.j0(z)
        return (
            (lambda z: z * special.j1(z) - biot * special.j0(z))
            if biot <= 1
            else (lambda z: z * special.j1(z) / biot - special.j0(z))
        )
    if math.isinf(biot):
        return lambda z: np.sin(z)
    return lambda z: (1.0 - biot) * np.sin(z) - z * np.cos(z)


@functools.lru_cache(maxsize=64)
def raizes(forma: str, biot: float, quantas: int = 60) -> np.ndarray:
    """Os primeiros ζ_n (autovalores) do caso de livro."""
    f = _equacao_das_raizes(forma, biot)
    grade = np.linspace(1e-9, (quantas + 1.5) * np.pi, 400 * (quantas + 2))
    valores = f(grade)
    saida: list[float] = []
    for a, b, fa, fb in zip(grade[:-1], grade[1:], valores[:-1], valores[1:], strict=True):
        if fa == 0.0:
            saida.append(float(a))
        elif fa * fb < 0:
            saida.append(float(optimize.brentq(f, a, b, xtol=1e-14, rtol=1e-14)))
        if len(saida) >= quantas:
            break
    if forma == ESFERA and saida and saida[0] < 1e-6:
        saida.pop(0)  # ζ = 0 não é raiz da esfera
    return np.array(saida[:quantas])


def solucao_em_serie(caso: CasoDeLivro, tempo: float, posicao_mm: float) -> float:
    """Temperatura exata no instante e no ponto (posição na coordenada da peça, mm)."""
    if tempo <= 0:
        return caso.t_inicial
    xi = abs(posicao_mm - caso.origem_mm) / 1000.0 / caso.meia_espessura
    fo = caso.alpha * tempo / caso.meia_espessura**2
    z = raizes(caso.forma, caso.biot)
    if caso.forma == PAREDE:
        coef = 4.0 * np.sin(z) / (2.0 * z + np.sin(2.0 * z))
        forma = np.cos(z * xi)
    elif caso.forma == CILINDRO:
        j0, j1 = special.j0(z), special.j1(z)
        coef = 2.0 / z * j1 / (j0**2 + j1**2)
        forma = special.j0(z * xi)
    else:
        coef = 4.0 * (np.sin(z) - z * np.cos(z)) / (2.0 * z - np.sin(2.0 * z))
        forma = np.sinc(z * xi / np.pi) if xi > 0 else np.ones_like(z)
    theta = float(np.sum(coef * np.exp(-(z**2) * fo) * forma))
    return caso.t_fluido + (caso.t_inicial - caso.t_fluido) * theta


@dataclass(frozen=True, slots=True)
class Conferencia:
    tempo: float
    ponto: str
    calculado: float
    exato: float

    @property
    def diferenca(self) -> float:
        return self.calculado - self.exato


def conferencias(
    r: ResultadoDoCalor, fracoes: Sequence[float] = (0.1, 0.3, 1.0)
) -> list[Conferencia]:
    """Calculado × solução exata em alguns instantes, no centro e na face."""
    caso = caso_de_livro(r.peca)
    if caso is None:
        return []
    saida: list[Conferencia] = []
    for fracao in fracoes:
        i = int(round(fracao * (len(r.tempos) - 1)))
        for ponto in (r.pontos[0], r.pontos[-1]):
            if caso.forma == PAREDE and caso.origem_mm == r.peca.espessura_mm / 2.0:
                ponto = r.pontos[1] if ponto is r.pontos[0] else ponto
            calculado = float(r.temperaturas[i, ponto.indice])
            exato = solucao_em_serie(caso, float(r.tempos[i]), ponto.posicao_mm)
            saida.append(Conferencia(float(r.tempos[i]), ponto.nome, calculado, exato))
    return saida


# ---------------------------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------------------------
def _n(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def hipoteses(r: ResultadoDoCalor) -> list[str]:
    p = r.peca
    linhas = [
        "Calor só na espessura (uma dimensão): "
        + {
            PAREDE: "parede larga, sem perda pelas bordas.",
            CILINDRO: "cilindro comprido, sem perda pelas pontas.",
            ESFERA: "a esfera troca calor por igual em toda a superfície.",
        }[p.forma],
        "Propriedades do material constantes (sem variar com a temperatura), sem geração de calor "
        "dentro da peça e sem mudança de fase.",
        "A peça começa toda a uma temperatura só, e as condições das faces mudam no instante zero "
        "e ficam constantes depois.",
        "Convecção com h constante: o h vem de tabela ou de correlação feita fora desta conta. "
        "Radiação, se importa, entra somada no h.",
        f"Volumes finitos com {len(r.r)} nós na espessura e Crank–Nicolson com {len(r.tempos) - 1} "
        "passos no tempo (os 4 primeiros implícitos).",
    ]
    return linhas
