"""O vento barra a barra levado aos níveis da estrutura. Sem Streamlit.

O vento viga a viga, pilar a pilar (:mod:`core.vento_por_barras`) dá a carga de cada barra. Este
módulo deixa à vista o que ela não mostra:

1. **A força do vento em cada nível**, em cada direção, e por onde ela passa em planta;
2. **uma forma simplificada de aplicar no modelo**, com poucas cargas.

Como faz:

* **Níveis**: as cotas onde o esqueleto tem vigas deitadas (vigas a menos de 15 cm uma da outra,
  na vertical, formam um nível), a 0,5 m ou mais do terreno — um patamar de escada é um nível.
  Abaixo disso é a base.
* **Força nas pontas**: cada barra leva o vento dela às duas pontas, metade em cada (barra
  biapoiada); a parcela de um guarda-corpo, escada, painel ou equipamento vai às pontas da barra
  que o apoia. Uma ponta que cai no meio de outra barra (a mão francesa no pilar) passa às pontas
  dessa barra pela regra da alavanca, até chegar a um nível ou à base; a que não cai em nenhuma
  barra vai ao nível que fica a até 35 cm dela (o pé de um lance de escada fica abaixo do patamar
  pela altura do perfil). O que chega à base (o pé dos pilares) vai direto à fundação e não entra
  no modelo.
* **A resultante do nível**: a soma das forças que chegam a ele e a linha por onde passa (a
  componente X passa num y da planta, a componente Y num x).
* **Forma simplificada**: em cada nível, a componente X de cada força vai às linhas de vigas em X
  (vigas deitadas do nível alinhadas a menos de 15 cm) pela regra da alavanca na coordenada y; a
  componente Y vai às linhas em Y pela coordenada x. Cada viga da linha recebe ``q = F/L`` ao
  longo do eixo dela. A força e a torção de cada nível ficam as do cálculo barra a barra; sai do
  modelo só a flexão local de cada barra pelo vento dela (a maior aparece no resultado).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import plano_de_cargas as pc
from core import vento_por_barras as vpb

Ponto = tuple[float, float, float]

#: Vigas deitadas a menos disso uma da outra (na vertical) formam o mesmo nível.
TOLERANCIA_DO_NIVEL_M = 0.15
#: Um nível precisa estar pelo menos isto acima do terreno (vigas de baldrame ficam na base).
NIVEL_MINIMO_M = 0.50
#: Ponta até isto acima do terreno (ou abaixo dele) é o pé: a força vai à fundação.
TOLERANCIA_DA_BASE_M = 0.25
#: Ponta que não cai no meio de outra barra vai ao nível até esta distância (na vertical): o pé
#: de um lance de escada fica abaixo do patamar pela altura do perfil (linhas de centro).
TOLERANCIA_DA_PONTA_M = 0.35
#: Vigas do mesmo nível a menos disso uma da outra (em planta) formam a mesma linha.
TOLERANCIA_DA_LINHA_M = 0.15
SEN_DEITADA = math.sin(math.radians(3.0))
COS_ALINHADA = math.cos(math.radians(10.0))
#: Uma ponta "cai no meio" de outra barra até esta distância do eixo dela (além da meia seção).
DISTANCIA_A_BARRA_M = 0.10
PROFUNDIDADE_MAXIMA = 8
#: Torção que a forma simplificada deixa de fora e vira aviso (kN·m).
TORCAO_RELEVANTE_KNM = 0.05
BASE = -1

FORMA_BARRAS = "Barra a barra: cada barra com a carga dela"
FORMA_SIMPLIFICADA = "Simplificada: a força de cada nível nas vigas na direção do vento"
FORMAS = (FORMA_BARRAS, FORMA_SIMPLIFICADA)


def _n(valor: float, casas: int = 2) -> str:
    if not math.isfinite(valor):
        return "—"
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def _sinal(valor: float, eixo: str) -> str:
    return ("+" if valor >= 0 else "−") + eixo


# ---------------------------------------------------------------------------------------------
# Níveis e linhas de vigas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Nivel:
    numero: int  # 1 = o mais baixo
    cota_m: float  # a partir do terreno
    z_m: float  # cota na planta do programa (a mesma coordenada das barras)
    comprimento_de_vigas_m: float


@dataclass(frozen=True)
class LinhaDeVigas:
    """Vigas deitadas de um nível, alinhadas numa direção (X ou Y da planta)."""

    nivel: int  # índice em :attr:`VentoPorNivel.niveis`
    eixo: str  # "X" ou "Y": a direção das vigas e da carga que elas recebem
    coordenada_m: float  # y da planta (linha em X) ou x (linha em Y)
    barras: tuple[vpb.BarraAoVento, ...]

    @property
    def comprimento_m(self) -> float:
        return sum(b.comprimento_m for b in self.barras)


def _deitada(b: vpb.BarraAoVento) -> bool:
    return b.comprimento_m > 0 and abs(b.fim[2] - b.inicio[2]) <= SEN_DEITADA * b.comprimento_m


def _grupos(
    barras: Sequence[vpb.BarraAoVento], coordenada: int, tolerancia: float
) -> list[list[vpb.BarraAoVento]]:
    """Agrupa as barras pela coordenada do meio, em cadeia: vizinhas a menos de ``tolerancia``."""
    grupos: list[list[vpb.BarraAoVento]] = []
    for b in sorted(barras, key=lambda b: b.meio[coordenada]):
        if grupos and b.meio[coordenada] - grupos[-1][-1].meio[coordenada] <= tolerancia:
            grupos[-1].append(b)
        else:
            grupos.append([b])
    return grupos


def niveis_da_estrutura(barras: Sequence[vpb.BarraAoVento], terreno: float) -> tuple[Nivel, ...]:
    """As cotas com vigas deitadas, de baixo para cima (o patamar de escada também é nível)."""
    niveis: list[Nivel] = []
    for vigas in _grupos([b for b in barras if _deitada(b)], 2, TOLERANCIA_DO_NIVEL_M):
        comprimento = sum(b.comprimento_m for b in vigas)
        z = sum(b.meio[2] * b.comprimento_m for b in vigas) / comprimento
        if z - terreno >= NIVEL_MINIMO_M:
            niveis.append(Nivel(len(niveis) + 1, z - terreno, z, comprimento))
    return tuple(niveis)


def linhas_de_vigas(
    barras: Sequence[vpb.BarraAoVento], niveis: Sequence[Nivel]
) -> tuple[LinhaDeVigas, ...]:
    """As linhas de vigas de cada nível, em X (pela coordenada y) e em Y (pela x)."""
    linhas: list[LinhaDeVigas] = []
    for i, nivel in enumerate(niveis):
        vigas = [
            b for b in barras if _deitada(b) and abs(b.meio[2] - nivel.z_m) <= TOLERANCIA_DO_NIVEL_M
        ]
        for eixo, ao_longo, atravessada in (("X", 0, 1), ("Y", 1, 0)):
            alinhadas = [
                b for b in vigas if abs(b.vetor[ao_longo]) >= COS_ALINHADA * b.comprimento_m
            ]
            for grupo in _grupos(alinhadas, atravessada, TOLERANCIA_DA_LINHA_M):
                membros = tuple(grupo)
                total = sum(b.comprimento_m for b in membros)
                coordenada = sum(b.meio[atravessada] * b.comprimento_m for b in membros) / total
                linhas.append(LinhaDeVigas(i, eixo, coordenada, membros))
    return tuple(linhas)


# ---------------------------------------------------------------------------------------------
# Das barras às pontas, das pontas aos níveis
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Forca:
    ponto: Ponto
    fx: float
    fy: float
    origem: str


def _forcas_nas_pontas(
    d: vpb.VentoNaDirecao, por_nome: dict[str, vpb.BarraAoVento]
) -> list[_Forca]:
    """O vento de cada barra (e o que os elementos mandam a ela), metade em cada ponta."""
    forcas: list[_Forca] = []

    def nas_pontas(b: vpb.BarraAoVento, fx: float, fy: float, origem: str) -> None:
        forcas.append(_Forca(b.inicio, fx / 2.0, fy / 2.0, origem))
        forcas.append(_Forca(b.fim, fx / 2.0, fy / 2.0, origem))

    for f in d.barras:
        b = por_nome.get(f.barra)
        if b is not None:
            nas_pontas(b, f.fx_kN_m * f.comprimento_m, f.fy_kN_m * f.comprimento_m, b.rotulo)
    for el in d.elementos:
        for p in el.parcelas:
            fx, fy = (
                (p.fx * p.comprimento_m, p.fy * p.comprimento_m)
                if p.unidade == "kN/m"
                else (p.fx, p.fy)
            )
            b = por_nome.get(p.barra)
            if b is not None:
                nas_pontas(b, fx, fy, el.elemento)
            else:
                forcas.append(_Forca(el.ponto, fx, fy, el.elemento))
    return forcas


class _Caminho:
    """Leva uma força numa ponta de barra até os níveis e a base."""

    def __init__(
        self, barras: Sequence[vpb.BarraAoVento], niveis: Sequence[Nivel], terreno: float
    ) -> None:
        self.em_pe = [b for b in barras if not _deitada(b) and b.comprimento_m > 0]
        self.niveis = tuple(niveis)
        self.terreno = terreno
        self.aproximados: dict[str, None] = {}

    def _nivel(self, z: float, tolerancia: float = TOLERANCIA_DO_NIVEL_M) -> int | None:
        perto = [
            (abs(z - n.z_m), i) for i, n in enumerate(self.niveis) if abs(z - n.z_m) <= tolerancia
        ]
        return min(perto)[1] if perto else None

    def _barra_que_passa(self, p: Ponto) -> tuple[vpb.BarraAoVento, float] | None:
        """A barra em pé (pilar, diagonal) em cujo meio a ponta ``p`` cai, e onde (0 a 1)."""
        melhor: tuple[float, vpb.BarraAoVento, float] | None = None
        for b in self.em_pe:
            v = b.vetor
            comprimento = b.comprimento_m
            t = sum((p[k] - b.inicio[k]) * v[k] for k in range(3)) / comprimento**2
            if t * comprimento <= TOLERANCIA_DO_NIVEL_M / 3 or (1 - t) * comprimento <= (
                TOLERANCIA_DO_NIVEL_M / 3
            ):
                continue
            no_eixo = [b.inicio[k] + t * v[k] for k in range(3)]
            distancia = math.dist(p, no_eixo)
            if distancia <= DISTANCIA_A_BARRA_M + b.maior_m / 2 and (
                melhor is None or distancia < melhor[0]
            ):
                melhor = (distancia, b, t)
        return None if melhor is None else (melhor[1], melhor[2])

    def _pela_faixa(self, z: float) -> int:
        cotas = [n.cota_m for n in self.niveis]
        cota = z - self.terreno
        if not cotas or cota < cotas[0] / 2.0:
            return BASE
        for i in range(len(cotas) - 1):
            if cota < (cotas[i] + cotas[i + 1]) / 2.0:
                return i
        return len(cotas) - 1

    def destinos(
        self, p: Ponto, origem: str, profundidade: int = 0
    ) -> list[tuple[int, Ponto, float]]:
        """``(nível ou BASE, ponto onde chega, fração)`` da força que está em ``p``."""
        nivel = self._nivel(p[2])
        if nivel is not None:
            return [(nivel, p, 1.0)]
        if p[2] - self.terreno <= TOLERANCIA_DA_BASE_M:
            return [(BASE, p, 1.0)]
        if profundidade < PROFUNDIDADE_MAXIMA:
            achada = self._barra_que_passa(p)
            if achada is not None:
                b, t = achada
                return [
                    *(
                        (i, q, f * (1.0 - t))
                        for i, q, f in self.destinos(b.inicio, origem, profundidade + 1)
                    ),
                    *((i, q, f * t) for i, q, f in self.destinos(b.fim, origem, profundidade + 1)),
                ]
        nivel = self._nivel(p[2], TOLERANCIA_DA_PONTA_M)
        if nivel is not None:
            return [(nivel, p, 1.0)]
        self.aproximados[origem] = None
        return [(self._pela_faixa(p[2]), p, 1.0)]


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CargaNaLinha:
    linha: LinhaDeVigas
    forca_kN: float  # ao longo do eixo da linha, com sinal

    @property
    def q_kN_m(self) -> float:
        return self.forca_kN / self.linha.comprimento_m if self.linha.comprimento_m > 0 else 0.0


@dataclass(frozen=True)
class NivelNaDirecao:
    nivel: Nivel
    fx_kN: float
    fy_kN: float
    y_de_fx_m: float | None  # a componente X passa neste y da planta
    x_de_fy_m: float | None  # a componente Y passa neste x da planta
    cargas: tuple[CargaNaLinha, ...] = ()
    #: Torção do nível que a forma simplificada não consegue pôr (uma linha só numa direção).
    torcao_fora_kNm: float = 0.0
    #: Eixos com força neste nível e sem linha de vigas para recebê-la ("X", "Y").
    sem_linhas: tuple[str, ...] = ()

    @property
    def forca_kN(self) -> float:
        return math.hypot(self.fx_kN, self.fy_kN)


@dataclass(frozen=True)
class DirecaoPorNivel:
    angulo: int
    niveis: tuple[NivelNaDirecao, ...]
    fx_base_kN: float
    fy_base_kN: float
    flexao_local_kNm: float  # a maior flexão de uma barra pelo vento dela (w⊥·ℓ²/8)
    barra_da_flexao: str

    @property
    def codigo(self) -> str:
        return f"W{self.angulo}"

    @property
    def fx_kN(self) -> float:
        return sum(n.fx_kN for n in self.niveis) + self.fx_base_kN

    @property
    def fy_kN(self) -> float:
        return sum(n.fy_kN for n in self.niveis) + self.fy_base_kN


@dataclass(frozen=True)
class VentoPorNivel:
    resultado: vpb.ResultadoPorBarras
    niveis: tuple[Nivel, ...]
    linhas: tuple[LinhaDeVigas, ...]
    direcoes: tuple[DirecaoPorNivel, ...]
    aproximados: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()

    def direcao(self, angulo: int) -> DirecaoPorNivel:
        for d in self.direcoes:
            if d.angulo == angulo:
                return d
        raise KeyError(angulo)

    @property
    def nivel_principal(self) -> int | None:
        """O nível com mais vigas (a plataforma): índice em :attr:`niveis`."""
        if not self.niveis:
            return None
        return max(range(len(self.niveis)), key=lambda i: self.niveis[i].comprimento_de_vigas_m)

    @property
    def simplificada_possivel(self) -> bool:
        return bool(self.niveis) and not any(n.sem_linhas for d in self.direcoes for n in d.niveis)


def _alavanca(s: float, coordenadas: Sequence[float]) -> list[tuple[int, float]]:
    """Frações de uma força em ``s`` entre as linhas (em ordem): as duas vizinhas pela regra da
    alavanca — fora do vão, as duas da ponta (a de longe fica com fração negativa); força e
    momento ficam iguais."""
    if len(coordenadas) == 1:
        return [(0, 1.0)]
    j = 0
    while j < len(coordenadas) - 2 and s > coordenadas[j + 1]:
        j += 1
    a, b = coordenadas[j], coordenadas[j + 1]
    t = (s - a) / (b - a)
    return [(j, 1.0 - t), (j + 1, t)]


def _flexao_local(
    d: vpb.VentoNaDirecao, por_nome: dict[str, vpb.BarraAoVento]
) -> tuple[float, str]:
    """A maior flexão local de uma barra pelo vento dela e pelo que os elementos mandam a ela."""
    w: dict[str, list[float]] = {}
    for f in d.barras:
        w.setdefault(f.barra, [0.0, 0.0])
        w[f.barra][0] += f.fx_kN_m
        w[f.barra][1] += f.fy_kN_m
    for el in d.elementos:
        for p in el.parcelas:
            if p.unidade == "kN/m":
                w.setdefault(p.barra, [0.0, 0.0])
                w[p.barra][0] += p.fx
                w[p.barra][1] += p.fy
    maior, qual = 0.0, ""
    for nome, (wx, wy) in w.items():
        b = por_nome.get(nome)
        if b is None or b.comprimento_m <= 0:
            continue
        u = [c / b.comprimento_m for c in b.vetor]
        ao_longo = wx * u[0] + wy * u[1]
        perpendicular = math.sqrt(max(0.0, wx * wx + wy * wy - ao_longo * ao_longo))
        momento = perpendicular * b.comprimento_m**2 / 8.0
        if momento > maior:
            maior, qual = momento, b.rotulo
    return maior, qual


def vento_por_nivel(r: vpb.ResultadoPorBarras) -> VentoPorNivel:
    """Cada direção do vento barra a barra levada aos níveis, com a forma simplificada."""
    barras = r.entrada.barras
    terreno = r.cota_do_terreno_m
    por_nome = {b.nome: b for b in barras}
    niveis = niveis_da_estrutura(barras, terreno)
    linhas = linhas_de_vigas(barras, niveis)
    caminho = _Caminho(barras, niveis, terreno)
    avisos: list[str] = []
    direcoes: list[DirecaoPorNivel] = []
    for d in r.direcoes:
        nos_niveis: list[list[tuple[Ponto, float, float]]] = [[] for _ in niveis]
        base_x = base_y = 0.0
        for forca in _forcas_nas_pontas(d, por_nome):
            for i, q, fracao in caminho.destinos(forca.ponto, forca.origem):
                fx, fy = forca.fx * fracao, forca.fy * fracao
                if i == BASE:
                    base_x += fx
                    base_y += fy
                else:
                    nos_niveis[i].append((q, fx, fy))
        resultado_niveis = []
        for i, nivel in enumerate(niveis):
            pontos = nos_niveis[i]
            fx = sum(p[1] for p in pontos)
            fy = sum(p[2] for p in pontos)
            y_de_fx = sum(p[0][1] * p[1] for p in pontos) / fx if abs(fx) > 1e-9 else None
            x_de_fy = sum(p[0][0] * p[2] for p in pontos) / fy if abs(fy) > 1e-9 else None
            cargas: list[CargaNaLinha] = []
            torcao_fora = 0.0
            sem_linhas: list[str] = []
            for eixo, coordenada in (("X", 1), ("Y", 0)):
                do_eixo = sorted(
                    (ln for ln in linhas if ln.nivel == i and ln.eixo == eixo),
                    key=lambda ln: ln.coordenada_m,
                )
                total = fx if eixo == "X" else fy
                if not do_eixo:
                    if abs(total) > 1e-6:
                        sem_linhas.append(eixo)
                    continue
                coordenadas = [ln.coordenada_m for ln in do_eixo]
                forcas = [0.0] * len(do_eixo)
                for ponto, fx_p, fy_p in pontos:
                    valor = fx_p if eixo == "X" else fy_p
                    s = ponto[coordenada]
                    for k, fracao in _alavanca(s, coordenadas):
                        forcas[k] += valor * fracao
                    if len(do_eixo) == 1:
                        # T = x·F_y − y·F_x: o que muda ao levar a força para a linha.
                        desvio = coordenadas[0] - s
                        torcao_fora += desvio * valor if eixo == "X" else -desvio * valor
                cargas.extend(CargaNaLinha(ln, f) for ln, f in zip(do_eixo, forcas, strict=True))
            resultado_niveis.append(
                NivelNaDirecao(
                    nivel,
                    fx,
                    fy,
                    y_de_fx,
                    x_de_fy,
                    tuple(cargas),
                    torcao_fora,
                    tuple(sem_linhas),
                )
            )
            if sem_linhas:
                avisos.append(
                    f"{d.codigo}: o nível {nivel.numero} (cota {_n(nivel.cota_m)} m) recebe força "
                    f"em {' e '.join(sem_linhas)} e não tem vigas nessa direção — a forma "
                    "simplificada não serve; use a carga barra a barra."
                )
            elif abs(torcao_fora) >= TORCAO_RELEVANTE_KNM:
                avisos.append(
                    f"{d.codigo}: o nível {nivel.numero} (cota {_n(nivel.cota_m)} m) tem uma linha "
                    f"de vigas só numa direção — na forma simplificada a torção de "
                    f"{_n(abs(torcao_fora))} kN·m desse nível fica de fora."
                )
        flexao, barra = _flexao_local(d, por_nome)
        direcoes.append(
            DirecaoPorNivel(d.angulo, tuple(resultado_niveis), base_x, base_y, flexao, barra)
        )
    if not niveis:
        avisos.insert(
            0,
            "O esqueleto não tem vigas deitadas a 0,5 m ou mais do terreno: sem nível, o vento "
            "vai todo à fundação. Confira o eixo vertical do modelo e a cota do terreno.",
        )
    if caminho.aproximados:
        nomes = list(caminho.aproximados)
        avisos.append(
            "Pontas que não caem num nível, na base nem no meio de outra barra ("
            + ", ".join(nomes[:6])
            + ("…" if len(nomes) > 6 else "")
            + "): a força delas foi ao nível pela faixa de altura (meia altura entre os níveis)."
        )
    return VentoPorNivel(
        resultado=r,
        niveis=niveis,
        linhas=linhas,
        direcoes=tuple(direcoes),
        aproximados=tuple(caminho.aproximados),
        avisos=tuple(dict.fromkeys(avisos)),
    )


# ---------------------------------------------------------------------------------------------
# Coordenadas no modelo (SolidWorks)
# ---------------------------------------------------------------------------------------------
def _coordenada(valor: float) -> str:
    return _n(valor, 3).replace("-", "−")


def cota_no_modelo(nivel: Nivel, eixo_vertical: str) -> str:
    """A cota do nível no eixo vertical do modelo: "Y = 0,100 m"."""
    return f"{'Y' if eixo_vertical == 'Y' else 'Z'} = {_coordenada(nivel.z_m)} m"


def linha_no_modelo(eixo: str, coordenada_m: float, eixo_vertical: str) -> str:
    """Onde fica, no modelo, uma linha paralela a X da planta (em y = coordenada) ou a Y (em x)."""
    if eixo == "Y":
        return f"X = {_coordenada(coordenada_m)} m"
    if eixo_vertical == "Y":  # o Y da planta é o −Z do SolidWorks
        return f"Z = {_coordenada(-coordenada_m)} m"
    return f"Y = {_coordenada(coordenada_m)} m"


def eixo_no_modelo(eixo: str, eixo_vertical: str) -> str:
    """O eixo do modelo ao longo de uma direção da planta: X → X; Y → Z com o Y vertical."""
    if eixo == "X":
        return "X"
    return "Z" if eixo_vertical == "Y" else "Y"


def sentido_no_modelo(valor: float, eixo: str, eixo_vertical: str) -> str:
    """O sentido, nos eixos do modelo, de uma carga ``valor`` no eixo da planta: o +Y da planta é o
    −Z do SolidWorks com o Y vertical."""
    if eixo == "Y" and eixo_vertical == "Y":
        return _sinal(-valor, "Z")
    return _sinal(valor, eixo_no_modelo(eixo, eixo_vertical))


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def _onde_passa(n: NivelNaDirecao, eixo_vertical: str) -> str:
    partes = []
    if n.y_de_fx_m is not None and abs(n.fx_kN) > 1e-6:
        partes.append("F_x em " + linha_no_modelo("X", n.y_de_fx_m, eixo_vertical))
    if n.x_de_fy_m is not None and abs(n.fy_kN) > 1e-6:
        partes.append("F_y em " + linha_no_modelo("Y", n.x_de_fy_m, eixo_vertical))
    return "; ".join(partes) or "—"


def tabela_por_nivel(vn: VentoPorNivel, eixo_vertical: str = "Y") -> list[dict[str, object]]:
    """Uma linha por direção e nível, e a da fundação: a força e por onde passa."""
    linhas: list[dict[str, object]] = []
    for d in vn.direcoes:
        for n in d.niveis:
            linhas.append(
                {
                    "Caso": d.codigo,
                    "Sentido": vpb.SENTIDOS.get(d.angulo, ""),
                    "Nível": f"{n.nivel.numero} ({cota_no_modelo(n.nivel, eixo_vertical)})",
                    "Cota (m)": n.nivel.cota_m,
                    "F_x (kN)": n.fx_kN,
                    "F_y (kN)": n.fy_kN,
                    "F (kN)": n.forca_kN,
                    "Passa em (modelo)": _onde_passa(n, eixo_vertical),
                }
            )
        linhas.append(
            {
                "Caso": d.codigo,
                "Sentido": vpb.SENTIDOS.get(d.angulo, ""),
                "Nível": "base (direto à fundação)",
                "Cota (m)": 0.0,
                "F_x (kN)": d.fx_base_kN,
                "F_y (kN)": d.fy_base_kN,
                "F (kN)": math.hypot(d.fx_base_kN, d.fy_base_kN),
                "Passa em (modelo)": "—",
            }
        )
    return linhas


def linhas_por_nivel_para_memorial(vn: VentoPorNivel, eixo_vertical: str = "Y") -> list[list[str]]:
    """As linhas de :func:`tabela_por_nivel` em texto, para o memorial."""
    linhas = []
    for d in vn.direcoes:
        for n in d.niveis:
            linhas.append(
                [
                    d.codigo,
                    f"{n.nivel.numero} ({cota_no_modelo(n.nivel, eixo_vertical)})",
                    _n(n.nivel.cota_m),
                    _n(n.fx_kN),
                    _n(n.fy_kN),
                    _onde_passa(n, eixo_vertical),
                ]
            )
        linhas.append(
            [d.codigo, "base (direto à fundação)", "—", _n(d.fx_base_kN), _n(d.fy_base_kN), "—"]
        )
    return linhas


def tabela_simplificada(vn: VentoPorNivel, eixo_vertical: str = "Y") -> list[dict[str, object]]:
    """Uma linha por direção, nível e linha de vigas: a força da linha e o q de cada viga."""
    linhas: list[dict[str, object]] = []
    for d in vn.direcoes:
        for n in d.niveis:
            for c in n.cargas:
                if abs(c.forca_kN) <= 1e-9:
                    continue
                ln = c.linha
                linhas.append(
                    {
                        "Caso": d.codigo,
                        "Nível": f"{n.nivel.numero} ({cota_no_modelo(n.nivel, eixo_vertical)})",
                        "Linha": f"vigas em {eixo_no_modelo(ln.eixo, eixo_vertical)}, "
                        + linha_no_modelo(ln.eixo, ln.coordenada_m, eixo_vertical),
                        "Vigas": ", ".join(b.rotulo for b in ln.barras),
                        "L (m)": ln.comprimento_m,
                        "F (kN)": c.forca_kN,
                        "q (kN/m)": c.q_kN_m,
                        "Sentido no modelo": sentido_no_modelo(c.q_kN_m, ln.eixo, eixo_vertical),
                    }
                )
    return linhas


# ---------------------------------------------------------------------------------------------
# Plano de cargas
# ---------------------------------------------------------------------------------------------
def cargas_simplificadas(vn: VentoPorNivel, angulo: int) -> list[pc.CargaDoModelo]:
    """As linhas do plano de uma direção na forma simplificada: em cada viga das linhas de cada
    nível, o q da linha ao longo do eixo dela (componentes nos eixos da planta, como as da carga
    barra a barra)."""
    d = vn.direcao(angulo)
    cargas: list[pc.CargaDoModelo] = []
    for n in d.niveis:
        for c in n.cargas:
            q = c.q_kN_m
            if abs(q) <= 1e-7:
                continue
            ln = c.linha
            observacao = (
                f"{d.codigo}, nível {n.nivel.numero} (cota {_n(n.nivel.cota_m)} m): linha de vigas "
                f"em {ln.eixo} ({'y' if ln.eixo == 'X' else 'x'} = {_n(ln.coordenada_m)} m da "
                f"planta) com {_n(c.forca_kN, 3)} kN em {_n(ln.comprimento_m)} m — forma "
                "simplificada (força e torção do nível iguais às do cálculo barra a barra)"
            )
            for b in ln.barras:
                cargas.append(
                    pc.CargaDoModelo(
                        elemento=b.rotulo,
                        valor=round(q, 5),
                        unidade="kN/m",
                        direcao=_sinal(q, ln.eixo),
                        observacao=observacao,
                        comprimento_m=round(b.comprimento_m, 4),
                    )
                )
    return cargas


def acoes_simplificadas(vn: VentoPorNivel) -> list[pc.Acao]:
    """W0, W90… com a força de cada nível nas vigas na direção do vento."""
    acoes = []
    for d, original in zip(vn.direcoes, vn.resultado.direcoes, strict=True):
        partes = "; ".join(
            f"nível {n.nivel.numero} {_n(n.forca_kN)} kN" for n in d.niveis if n.forca_kN > 1e-9
        )
        resumo = (
            f"Vento barra a barra a {d.angulo}° ({vpb.SENTIDOS.get(d.angulo, '')}), forma "
            f"simplificada: {_n(original.total_kN)} kN — {partes or 'nenhum nível'}; base "
            f"{_n(math.hypot(d.fx_base_kN, d.fy_base_kN))} kN direto à fundação."
        )
        acoes.append(
            pc.nova_acao(
                d.codigo,
                origem=vpb.ORIGEM,
                resumo=resumo,
                cargas=cargas_simplificadas(vn, d.angulo),
            )
        )
    return acoes


def numero_de_cargas_no_estudo(acoes: Sequence[pc.Acao]) -> int:
    """Quantas cargas o estudo do SolidWorks precisa (uma por barra e eixo; cada caso só muda o
    valor) — o que o Gerenciador de casos de carga monta."""
    chaves = {
        (c.elemento.strip().casefold(), c.unidade, c.direcao.strip().lstrip("+−-"))
        for a in acoes
        for c in a.cargas
    }
    return len(chaves)


def csv_simplificado(vn: VentoPorNivel, eixo_vertical: str = "Y") -> bytes:
    linhas = tabela_simplificada(vn, eixo_vertical)
    cabecalho = [
        "Caso",
        "Nível",
        "Linha",
        "Vigas",
        "L (m)",
        "F (kN)",
        "q (kN/m)",
        "Sentido no modelo",
    ]
    return vpb._csv(cabecalho, ([linha[c] for c in cabecalho] for linha in linhas))
