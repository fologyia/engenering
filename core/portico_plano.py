"""Núcleo de cálculo de pórtico plano (2D): barras em qualquer ângulo, apoios, rótulas e cargas.

É o motor comum das partes do programa que precisam de esforços de uma estrutura plana: longarina
de escada (inclinada), vigas encadeadas, pórticos simples, trechos inclinados. Resolve por rigidez
direta, com o elemento de barra de Euler-Bernoulli (3 graus de liberdade por nó: u, v, θ) e
recupera os esforços **analiticamente** ao longo de cada barra — a carga distribuída (uniforme ou
trapezoidal) e as cargas concentradas entram por estática a partir da ponta inicial, então N, V e
M saem exatos entre os nós, sem depender de quantos pontos se desenha.

Convenções
----------
* Eixos globais: X para a direita, Y para cima. Unidades: kN, m, kN·m; E em kN/m², A em m², I em
  m⁴, W em m³. Cargas positivas no sentido dos eixos (a gravidade é negativa em Y).
* Cada barra vai do nó ``i`` ao nó ``j``; o eixo local x corre de i para j e o local y é x girado
  90° no sentido anti-horário.
* Esforço normal N positivo em **tração**. Cortante V = soma das forças transversais (local y) à
  esquerda da seção. Momento M positivo quando **traciona a face de baixo** (local −y) — numa viga
  horizontal biapoiada com carga para baixo, M > 0 no vão. dM/dx = V.
* Rótula numa ponta da barra: momento nulo ali (a rotação da ponta fica livre, por condensação).
* Os deslocamentos ao longo da barra saem da integração de M/EI e N/EA a partir da ponta i, com a
  rotação da própria barra na ponta (com rótula, a rotação recuperada da condensação).

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

E_ACO_KN_M2 = 200e6  # 200 GPa

#: Direções das cargas distribuídas.
GLOBAL_Y = "global_y"  # vertical, por metro de barra (peso próprio)
GLOBAL_Y_PROJETADA = "global_y_projetada"  # vertical, por metro horizontal (sobrecarga de escada)
GLOBAL_X = "global_x"  # horizontal, por metro de barra
GLOBAL_X_PROJETADA = "global_x_projetada"  # horizontal, por metro vertical (vento num pilar)
LOCAL_Y = "local_y"  # perpendicular à barra
LOCAL_X = "local_x"  # ao longo da barra
DIRECOES = (GLOBAL_Y, GLOBAL_Y_PROJETADA, GLOBAL_X, GLOBAL_X_PROJETADA, LOCAL_Y, LOCAL_X)


class PorticoInvalido(ValueError):
    """Modelo que não dá para resolver; a mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class No:
    nome: str
    x: float
    y: float


@dataclass(frozen=True)
class Secao:
    nome: str
    area_m2: float
    inercia_m4: float
    modulo_w_m3: float | None = None  # para a tensão de flexão; None = sem tensão
    e_kN_m2: float = E_ACO_KN_M2
    peso_kN_m: float = 0.0


@dataclass(frozen=True)
class Barra:
    nome: str
    no_i: str
    no_j: str
    secao: Secao
    rotula_i: bool = False
    rotula_j: bool = False


@dataclass(frozen=True)
class Apoio:
    """Restrições do nó: ``ux``, ``uy`` (translações) e ``rz`` (rotação)."""

    no: str
    ux: bool = True
    uy: bool = True
    rz: bool = False

    @property
    def tipo(self) -> str:
        if self.ux and self.uy and self.rz:
            return "engaste"
        if self.ux and self.uy:
            return "pino"
        if self.uy and not self.ux:
            return "rolete (vertical)"
        if self.ux and not self.uy:
            return "rolete (horizontal)"
        return "outro"


def engaste(no: str) -> Apoio:
    return Apoio(no, True, True, True)


def pino(no: str) -> Apoio:
    return Apoio(no, True, True, False)


def rolete(no: str) -> Apoio:
    """Apoio que só segura na vertical (desliza na horizontal)."""
    return Apoio(no, False, True, False)


@dataclass(frozen=True)
class CargaNodal:
    no: str
    fx: float = 0.0
    fy: float = 0.0
    mz: float = 0.0


@dataclass(frozen=True)
class CargaDistribuida:
    """Carga linear da ponta i (``qi``) à ponta j (``qj``), em kN/m, na direção dada."""

    barra: str
    qi: float
    qj: float | None = None  # None = uniforme (igual a qi)
    direcao: str = GLOBAL_Y
    nome: str = ""


@dataclass(frozen=True)
class CargaPontual:
    """Força concentrada numa barra, a ``distancia_m`` da ponta i (ao longo da barra)."""

    barra: str
    distancia_m: float
    fx: float = 0.0
    fy: float = 0.0
    local: bool = False  # True: fx ao longo da barra, fy perpendicular
    nome: str = ""


@dataclass(frozen=True)
class Portico:
    nos: tuple[No, ...]
    barras: tuple[Barra, ...]
    apoios: tuple[Apoio, ...]
    cargas_nodais: tuple[CargaNodal, ...] = ()
    cargas_distribuidas: tuple[CargaDistribuida, ...] = ()
    cargas_pontuais: tuple[CargaPontual, ...] = ()
    peso_proprio: bool = False  # soma o peso de cada seção, para baixo


# ---------------------------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PontoDaBarra:
    x: float  # m, da ponta i
    n: float  # kN (tração +)
    v: float  # kN
    m: float  # kN·m (traciona embaixo +)
    u_local: float  # m, ao longo da barra
    v_local: float  # m, perpendicular
    dx: float  # m, global
    dy: float  # m, global
    flecha: float  # m, perpendicular, em relação à corda entre as pontas deslocadas
    tensao_MPa: float | None  # |N|/A + |M|/W


@dataclass(frozen=True)
class ResultadoBarra:
    barra: Barra
    comprimento_m: float
    angulo_graus: float  # da barra com a horizontal
    pontos: tuple[PontoDaBarra, ...]
    esforcos_nas_pontas: tuple[float, ...]  # locais: N_i, V_i, M_i, N_j, V_j, M_j (forças na barra)

    def _extremo(self, atributo: str) -> PontoDaBarra:
        return max(self.pontos, key=lambda p: abs(getattr(p, atributo) or 0.0))

    @property
    def m_max(self) -> PontoDaBarra:
        return self._extremo("m")

    @property
    def v_max(self) -> PontoDaBarra:
        return self._extremo("v")

    @property
    def n_max(self) -> PontoDaBarra:
        return self._extremo("n")

    @property
    def flecha_max(self) -> PontoDaBarra:
        return self._extremo("flecha")

    @property
    def deslocamento_max(self) -> PontoDaBarra:
        return max(self.pontos, key=lambda p: math.hypot(p.dx, p.dy))

    @property
    def tensao_max(self) -> PontoDaBarra | None:
        com = [p for p in self.pontos if p.tensao_MPa is not None]
        return max(com, key=lambda p: p.tensao_MPa or 0.0) if com else None


@dataclass(frozen=True)
class Reacao:
    no: str
    rx: float
    ry: float
    mz: float


@dataclass(frozen=True)
class ResultadoPortico:
    portico: Portico
    deslocamentos: dict[str, tuple[float, float, float]]  # nó → (dx m, dy m, θ rad)
    reacoes: tuple[Reacao, ...]
    barras: tuple[ResultadoBarra, ...]
    residuo_kN: float  # equilíbrio global (soma das reações + cargas)
    avisos: tuple[str, ...] = field(default_factory=tuple)

    def barra(self, nome: str) -> ResultadoBarra:
        for b in self.barras:
            if b.barra.nome == nome:
                return b
        raise KeyError(nome)

    def reacao(self, no: str) -> Reacao:
        for r in self.reacoes:
            if r.no == no:
                return r
        raise KeyError(no)


# ---------------------------------------------------------------------------------------------
# Elemento
# ---------------------------------------------------------------------------------------------
_GAUSS_X, _GAUSS_W = np.polynomial.legendre.leggauss(8)


def _geometria(ni: No, nj: No) -> tuple[float, float, float]:
    dx, dy = nj.x - ni.x, nj.y - ni.y
    comprimento = math.hypot(dx, dy)
    return comprimento, dx / comprimento, dy / comprimento


def _rigidez_local(s: Secao, comprimento: float) -> np.ndarray:
    ea = s.e_kN_m2 * s.area_m2 / comprimento
    ei = s.e_kN_m2 * s.inercia_m4
    l1, l2, l3 = comprimento, comprimento**2, comprimento**3
    return np.array(
        [
            [ea, 0, 0, -ea, 0, 0],
            [0, 12 * ei / l3, 6 * ei / l2, 0, -12 * ei / l3, 6 * ei / l2],
            [0, 6 * ei / l2, 4 * ei / l1, 0, -6 * ei / l2, 2 * ei / l1],
            [-ea, 0, 0, ea, 0, 0],
            [0, -12 * ei / l3, -6 * ei / l2, 0, 12 * ei / l3, -6 * ei / l2],
            [0, 6 * ei / l2, 2 * ei / l1, 0, -6 * ei / l2, 4 * ei / l1],
        ]
    )


def _transformacao(c: float, s: float) -> np.ndarray:
    t = np.zeros((6, 6))
    bloco = np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])
    t[:3, :3] = bloco
    t[3:, 3:] = bloco
    return t


def _funcoes_de_forma(x: float, comprimento: float) -> np.ndarray:
    """Linha de N(x) com as 6 funções de forma (axial linear, transversal de Hermite)."""
    xi = x / comprimento
    return np.array(
        [
            [1 - xi, 0, 0, xi, 0, 0],
            [
                0,
                1 - 3 * xi**2 + 2 * xi**3,
                comprimento * (xi - 2 * xi**2 + xi**3),
                0,
                3 * xi**2 - 2 * xi**3,
                comprimento * (-(xi**2) + xi**3),
            ],
        ]
    )


@dataclass(frozen=True)
class _CargaLocal:
    """Carga distribuída já em coordenadas locais: p (axial) e q (transversal), lineares."""

    pi: float
    pj: float
    qi: float
    qj: float


@dataclass(frozen=True)
class _PontualLocal:
    a: float
    px: float
    py: float


def _local_da_distribuida(c: CargaDistribuida, cos_a: float, sen_a: float) -> _CargaLocal:
    qi = c.qi
    qj = c.qi if c.qj is None else c.qj
    if c.direcao == LOCAL_Y:
        return _CargaLocal(0.0, 0.0, qi, qj)
    if c.direcao == LOCAL_X:
        return _CargaLocal(qi, qj, 0.0, 0.0)
    if c.direcao in (GLOBAL_Y, GLOBAL_Y_PROJETADA):
        fator = abs(cos_a) if c.direcao == GLOBAL_Y_PROJETADA else 1.0
        # (0, q) global → local: (q·sen, q·cos)
        return _CargaLocal(
            qi * fator * sen_a, qj * fator * sen_a, qi * fator * cos_a, qj * fator * cos_a
        )
    if c.direcao in (GLOBAL_X, GLOBAL_X_PROJETADA):
        fator = abs(sen_a) if c.direcao == GLOBAL_X_PROJETADA else 1.0
        # (q, 0) global → local: (q·cos, −q·sen)
        return _CargaLocal(
            qi * fator * cos_a, qj * fator * cos_a, -qi * fator * sen_a, -qj * fator * sen_a
        )
    raise PorticoInvalido(f"Direção de carga desconhecida: {c.direcao!r}.")


def _local_da_pontual(c: CargaPontual, cos_a: float, sen_a: float) -> _PontualLocal:
    if c.local:
        return _PontualLocal(c.distancia_m, c.fx, c.fy)
    return _PontualLocal(c.distancia_m, c.fx * cos_a + c.fy * sen_a, -c.fx * sen_a + c.fy * cos_a)


def _forcas_de_engaste(
    comprimento: float, distribuidas: Sequence[_CargaLocal], pontuais: Sequence[_PontualLocal]
) -> np.ndarray:
    """Forças nas pontas da barra biengastada sob as cargas (f0 = −∫Nᵀ·carga)."""
    f0 = np.zeros(6)
    for carga in distribuidas:
        for xg, wg in zip(_GAUSS_X, _GAUSS_W, strict=True):
            x = comprimento * (xg + 1) / 2
            peso = wg * comprimento / 2
            p = carga.pi + (carga.pj - carga.pi) * x / comprimento
            q = carga.qi + (carga.qj - carga.qi) * x / comprimento
            f0 -= peso * (_funcoes_de_forma(x, comprimento).T @ np.array([p, q]))
    for ponto in pontuais:
        f0 -= _funcoes_de_forma(ponto.a, comprimento).T @ np.array([ponto.px, ponto.py])
    return f0


def _condensar(
    k: np.ndarray, f0: np.ndarray, liberados: Sequence[int]
) -> tuple[np.ndarray, np.ndarray]:
    if not liberados:
        return k, f0
    retidos = [i for i in range(6) if i not in liberados]
    khh = k[np.ix_(liberados, liberados)]
    khr = k[np.ix_(liberados, retidos)]
    krh = k[np.ix_(retidos, liberados)]
    inv = np.linalg.inv(khh)
    kc = np.zeros((6, 6))
    fc = np.zeros(6)
    kc[np.ix_(retidos, retidos)] = k[np.ix_(retidos, retidos)] - krh @ inv @ khr
    fc[retidos] = f0[retidos] - krh @ inv @ f0[liberados]
    return kc, fc


# ---------------------------------------------------------------------------------------------
# Solução
# ---------------------------------------------------------------------------------------------
def resolver(p: Portico, pontos_por_barra: int = 41) -> ResultadoPortico:
    """Resolve o pórtico: deslocamentos, reações e esforços ao longo de cada barra."""
    nos = {n.nome: n for n in p.nos}
    if len(nos) != len(p.nos):
        raise PorticoInvalido("Há nós com o mesmo nome.")
    if not p.barras:
        raise PorticoInvalido("O pórtico não tem barras.")
    indice = {nome: k for k, nome in enumerate(nos)}
    nomes_barras = [b.nome for b in p.barras]
    if len(set(nomes_barras)) != len(nomes_barras):
        raise PorticoInvalido("Há barras com o mesmo nome.")
    for b in p.barras:
        if b.no_i not in nos or b.no_j not in nos:
            raise PorticoInvalido(f"A barra {b.nome} liga um nó que não existe.")
        if b.secao.area_m2 <= 0 or b.secao.inercia_m4 <= 0 or b.secao.e_kN_m2 <= 0:
            raise PorticoInvalido(f"A seção da barra {b.nome} precisa de A, I e E positivos.")
        if _geometria(nos[b.no_i], nos[b.no_j])[0] <= 1e-9:
            raise PorticoInvalido(f"A barra {b.nome} tem comprimento zero.")
    for a in p.apoios:
        if a.no not in nos:
            raise PorticoInvalido(f"O apoio está num nó que não existe ({a.no}).")
    barras_por_nome = {b.nome: b for b in p.barras}
    for nome_da_barra in [c.barra for c in p.cargas_distribuidas] + [
        c.barra for c in p.cargas_pontuais
    ]:
        if nome_da_barra not in barras_por_nome:
            raise PorticoInvalido(f"A carga está numa barra que não existe ({nome_da_barra}).")

    total = 3 * len(nos)
    k_global = np.zeros((total, total))
    f_global = np.zeros(total)
    for c in p.cargas_nodais:
        if c.no not in nos:
            raise PorticoInvalido(f"A carga está num nó que não existe ({c.no}).")
        base = 3 * indice[c.no]
        f_global[base : base + 3] += (c.fx, c.fy, c.mz)

    elementos = []
    for b in p.barras:
        comprimento, cos_a, sen_a = _geometria(nos[b.no_i], nos[b.no_j])
        distribuidas = [
            _local_da_distribuida(c, cos_a, sen_a)
            for c in p.cargas_distribuidas
            if c.barra == b.nome
        ]
        if p.peso_proprio and b.secao.peso_kN_m > 0:
            distribuidas.append(
                _local_da_distribuida(CargaDistribuida(b.nome, -b.secao.peso_kN_m), cos_a, sen_a)
            )
        pontuais = [
            _local_da_pontual(c, cos_a, sen_a) for c in p.cargas_pontuais if c.barra == b.nome
        ]
        for ponto in pontuais:
            if not -1e-9 <= ponto.a <= comprimento + 1e-9:
                raise PorticoInvalido(f"A carga concentrada na barra {b.nome} está fora dela.")
        k = _rigidez_local(b.secao, comprimento)
        f0 = _forcas_de_engaste(comprimento, distribuidas, pontuais)
        liberados = [i for i, solto in ((2, b.rotula_i), (5, b.rotula_j)) if solto]
        kc, fc = _condensar(k, f0, liberados)
        t = _transformacao(cos_a, sen_a)
        dofs = [3 * indice[b.no_i] + d for d in range(3)] + [
            3 * indice[b.no_j] + d for d in range(3)
        ]
        k_global[np.ix_(dofs, dofs)] += t.T @ kc @ t
        f_global[dofs] -= t.T @ fc
        elementos.append(
            (b, comprimento, cos_a, sen_a, k, f0, liberados, t, dofs, distribuidas, pontuais)
        )

    restritos = np.zeros(total, dtype=bool)
    for a in p.apoios:
        base = 3 * indice[a.no]
        restritos[base] |= a.ux
        restritos[base + 1] |= a.uy
        restritos[base + 2] |= a.rz
    avisos: list[str] = []
    # Nó em que todas as barras chegam rotuladas: a rotação dele não tem rigidez — fica presa
    # (não muda nada: nenhuma barra transmite momento a ele).
    for nome, posicao in indice.items():
        dof = 3 * posicao + 2
        if not restritos[dof] and abs(k_global[dof, dof]) < 1e-9:
            if abs(f_global[dof]) > 1e-9:
                raise PorticoInvalido(
                    f"O nó {nome} recebe momento, mas todas as barras chegam nele rotuladas."
                )
            restritos[dof] = True
    livres = ~restritos
    u = np.zeros(total)
    if livres.any():
        kll = k_global[np.ix_(livres, livres)]
        try:
            if np.linalg.cond(kll) > 1e13:
                raise np.linalg.LinAlgError
            u[livres] = np.linalg.solve(kll, f_global[livres])
        except np.linalg.LinAlgError as erro:
            raise PorticoInvalido(
                "A estrutura é hipostática (pode se mover sem deformar): confira os apoios e as "
                "rótulas."
            ) from erro
    reacoes_vetor = k_global @ u - f_global
    reacoes = []
    for a in p.apoios:
        base = 3 * indice[a.no]
        reacoes.append(
            Reacao(
                a.no,
                float(reacoes_vetor[base]) if a.ux else 0.0,
                float(reacoes_vetor[base + 1]) if a.uy else 0.0,
                float(reacoes_vetor[base + 2]) if a.rz else 0.0,
            )
        )

    resultados_barras = []
    for (
        b,
        comprimento,
        cos_a,
        sen_a,
        k,
        f0,
        liberados,
        t,
        dofs,
        distribuidas,
        pontuais,
    ) in elementos:
        u_local = t @ u[dofs]
        if liberados:
            retidos = [i for i in range(6) if i not in liberados]
            khh = k[np.ix_(liberados, liberados)]
            khr = k[np.ix_(liberados, retidos)]
            u_local[liberados] = -np.linalg.solve(khh, khr @ u_local[retidos] + f0[liberados])
        pontas = k @ u_local + f0
        resultados_barras.append(
            _ao_longo_da_barra(
                b,
                comprimento,
                cos_a,
                sen_a,
                u_local,
                pontas,
                distribuidas,
                pontuais,
                pontos_por_barra,
            )  # fmt: skip
        )

    soma = np.zeros(3)
    for c in p.cargas_nodais:
        soma[:2] += (c.fx, c.fy)
    for r in reacoes:
        soma[:2] += (r.rx, r.ry)
    for _b, _comprimento, cos_a, sen_a, *_resto, distribuidas, pontuais in elementos:
        comprimento = _comprimento
        for carga in distribuidas:
            px = (carga.pi + carga.pj) / 2 * comprimento
            qy = (carga.qi + carga.qj) / 2 * comprimento
            soma[:2] += (px * cos_a - qy * sen_a, px * sen_a + qy * cos_a)
        for ponto in pontuais:
            soma[:2] += (ponto.px * cos_a - ponto.py * sen_a, ponto.px * sen_a + ponto.py * cos_a)
    residuo = float(math.hypot(soma[0], soma[1]))
    if residuo > 1e-6 * max(1.0, max((abs(r.ry) + abs(r.rx) for r in reacoes), default=1.0)):
        avisos.append(f"Equilíbrio global com resíduo de {residuo:.2e} kN.")
    deslocamentos = {
        nome: (float(u[3 * k]), float(u[3 * k + 1]), float(u[3 * k + 2]))
        for nome, k in indice.items()
    }
    return ResultadoPortico(
        p, deslocamentos, tuple(reacoes), tuple(resultados_barras), residuo, tuple(avisos)
    )


def _ao_longo_da_barra(
    b: Barra,
    comprimento: float,
    cos_a: float,
    sen_a: float,
    u_local: np.ndarray,
    pontas: np.ndarray,
    distribuidas: Sequence[_CargaLocal],
    pontuais: Sequence[_PontualLocal],
    n_pontos: int,
) -> ResultadoBarra:
    """N, V, M por estática a partir da ponta i; u e v pela integração de N/EA e M/EI."""
    xs = set(np.linspace(0.0, comprimento, max(n_pontos, 5)).tolist())
    for ponto in pontuais:  # o salto do cortante aparece dos dois lados da carga
        for desvio in (-1e-7, 1e-7):
            if 0 < ponto.a + desvio < comprimento:
                xs.add(ponto.a + desvio)
    grade = np.array(sorted(xs))
    f_xi, f_yi, m_i = pontas[0], pontas[1], pontas[2]

    def integrais(x: float) -> tuple[float, float, float]:
        axial = transversal = momento = 0.0
        for c in distribuidas:
            dp = (c.pj - c.pi) / comprimento
            dq = (c.qj - c.qi) / comprimento
            axial += c.pi * x + dp * x**2 / 2
            transversal += c.qi * x + dq * x**2 / 2
            momento += c.qi * x**2 / 2 + dq * x**3 / 6
        for ponto in pontuais:
            if x > ponto.a:
                axial += ponto.px
                transversal += ponto.py
                momento += ponto.py * (x - ponto.a)
        return axial, transversal, momento

    n = np.empty_like(grade)
    v = np.empty_like(grade)
    m = np.empty_like(grade)
    for k, x in enumerate(grade):
        axial, transversal, momento = integrais(float(x))
        n[k] = -f_xi - axial
        v[k] = f_yi + transversal
        m[k] = -m_i + f_yi * x + momento
    ea = b.secao.e_kN_m2 * b.secao.area_m2
    ei = b.secao.e_kN_m2 * b.secao.inercia_m4
    # Deslocamentos: N/EA e duas vezes M/EI integrados numa malha fina (2 000 trechos, erro da
    # ordem de 1e-7 da flecha), depois lidos nos pontos de saída. O resto numérico vai linear,
    # para a ponta j bater exatamente com o deslocamento da solução.
    fina = np.union1d(np.linspace(0.0, comprimento, 2001), grade)
    n_fina = np.empty_like(fina)
    m_fina = np.empty_like(fina)
    for k, x in enumerate(fina):
        axial, _transversal, momento = integrais(float(x))
        n_fina[k] = -f_xi - axial
        m_fina[k] = -m_i + f_yi * x + momento
    passos = np.diff(fina)
    du = np.concatenate(([0.0], np.cumsum(passos * (n_fina[1:] + n_fina[:-1]) / 2))) / ea
    curvatura = m_fina / ei
    theta = np.concatenate(([0.0], np.cumsum(passos * (curvatura[1:] + curvatura[:-1]) / 2)))
    vv = np.concatenate(([0.0], np.cumsum(passos * (theta[1:] + theta[:-1]) / 2)))
    u_fino = u_local[0] + du
    v_fino = u_local[1] + u_local[2] * fina + vv
    u_fino += (u_local[3] - u_fino[-1]) * fina / comprimento
    v_fino += (u_local[4] - v_fino[-1]) * fina / comprimento
    u_ao_longo = np.interp(grade, fina, u_fino)
    v_ao_longo = np.interp(grade, fina, v_fino)
    corda = u_local[1] + (u_local[4] - u_local[1]) * grade / comprimento
    flecha = v_ao_longo - corda
    pontos = []
    for k, x in enumerate(grade):
        dx = cos_a * u_ao_longo[k] - sen_a * v_ao_longo[k]
        dy = sen_a * u_ao_longo[k] + cos_a * v_ao_longo[k]
        tensao = None
        if b.secao.modulo_w_m3:
            tensao = (abs(n[k]) / b.secao.area_m2 + abs(m[k]) / b.secao.modulo_w_m3) / 1e3
        pontos.append(
            PontoDaBarra(
                float(x),
                float(n[k]) + 0.0,
                float(v[k]) + 0.0,
                float(m[k]) + 0.0,
                float(u_ao_longo[k]),
                float(v_ao_longo[k]),
                float(dx),
                float(dy),
                float(flecha[k]),
                tensao,
            )  # fmt: skip
        )
    angulo = math.degrees(math.atan2(sen_a, cos_a))
    if angulo > 90:
        angulo -= 180
    elif angulo < -90:
        angulo += 180
    return ResultadoBarra(b, comprimento, angulo, tuple(pontos), tuple(float(x) for x in pontas))


# ---------------------------------------------------------------------------------------------
# Atalhos
# ---------------------------------------------------------------------------------------------
def secao_de_perfil(nome_do_perfil: str, *, eixo: str = "x") -> Secao:
    """A seção de um perfil do catálogo (A, I e W no eixo dado, peso por metro)."""
    from core import section_catalog as sc

    perfil = sc.obter_perfil(nome_do_perfil)
    if eixo == "x":
        inercia_mm4, w_mm3 = perfil.ix_mm4, perfil.sx_mm3
    else:
        inercia_mm4, w_mm3 = perfil.iy_mm4, perfil.sy_mm3
    return Secao(
        nome=nome_do_perfil,
        area_m2=perfil.area_mm2 * 1e-6,
        inercia_m4=inercia_mm4 * 1e-12,
        modulo_w_m3=w_mm3 * 1e-9,
        peso_kN_m=perfil.massa_kg_m * 9.80665 / 1e3,
    )


# ---------------------------------------------------------------------------------------------
# Gravação (JSON): o registro guarda o modelo e o memorial o resolve de novo para as figuras
# ---------------------------------------------------------------------------------------------
def para_dicionario(p: Portico) -> dict[str, Any]:
    """O modelo em tipos simples (JSON), sem perder nada do que :func:`resolver` usa."""
    secoes = {b.secao.nome: b.secao for b in p.barras}
    return {
        "nos": [[n.nome, n.x, n.y] for n in p.nos],
        "secoes": [
            [s.nome, s.area_m2, s.inercia_m4, s.modulo_w_m3, s.e_kN_m2, s.peso_kN_m]
            for s in secoes.values()
        ],
        "barras": [
            [b.nome, b.no_i, b.no_j, b.secao.nome, b.rotula_i, b.rotula_j] for b in p.barras
        ],
        "apoios": [[a.no, a.ux, a.uy, a.rz] for a in p.apoios],
        "cargas_nodais": [[c.no, c.fx, c.fy, c.mz] for c in p.cargas_nodais],
        "cargas_distribuidas": [
            [c.barra, c.qi, c.qj, c.direcao, c.nome] for c in p.cargas_distribuidas
        ],
        "cargas_pontuais": [
            [c.barra, c.distancia_m, c.fx, c.fy, c.local, c.nome] for c in p.cargas_pontuais
        ],
        "peso_proprio": p.peso_proprio,
    }


def de_dicionario(dados: Mapping[str, Any]) -> Portico:
    """O inverso de :func:`para_dicionario` (levanta :class:`PorticoInvalido` se faltar algo)."""
    try:
        secoes = {
            s[0]: Secao(
                str(s[0]),
                float(s[1]),
                float(s[2]),
                None if s[3] is None else float(s[3]),
                float(s[4]),
                float(s[5]),
            )
            for s in dados["secoes"]
        }
        return Portico(
            nos=tuple(No(str(n[0]), float(n[1]), float(n[2])) for n in dados["nos"]),
            barras=tuple(
                Barra(str(b[0]), str(b[1]), str(b[2]), secoes[b[3]], bool(b[4]), bool(b[5]))
                for b in dados["barras"]
            ),
            apoios=tuple(
                Apoio(str(a[0]), bool(a[1]), bool(a[2]), bool(a[3])) for a in dados["apoios"]
            ),
            cargas_nodais=tuple(
                CargaNodal(str(c[0]), float(c[1]), float(c[2]), float(c[3]))
                for c in dados.get("cargas_nodais", [])
            ),
            cargas_distribuidas=tuple(
                CargaDistribuida(
                    str(c[0]),
                    float(c[1]),
                    None if c[2] is None else float(c[2]),
                    str(c[3]),
                    str(c[4]),
                )
                for c in dados.get("cargas_distribuidas", [])
            ),
            cargas_pontuais=tuple(
                CargaPontual(
                    str(c[0]), float(c[1]), float(c[2]), float(c[3]), bool(c[4]), str(c[5])
                )
                for c in dados.get("cargas_pontuais", [])
            ),
            peso_proprio=bool(dados.get("peso_proprio", False)),
        )
    except (KeyError, IndexError, TypeError, ValueError) as erro:
        raise PorticoInvalido(f"Modelo gravado incompleto: {erro}") from erro
