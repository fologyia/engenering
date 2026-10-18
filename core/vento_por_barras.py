"""Vento barra a barra — viga a viga, pilar a pilar — pela ABNT NBR 6123:2023, capítulo 8.

Para as estruturas abertas que não são uma grade regular de pórticos (duas colunas com a plataforma
em balanço, escadas, passarelas, estruturas assimétricas), o vento é calculado em cada barra do
esqueleto do modelo e em cada direção, sem supor a forma da estrutura:

* **toda estrutura de barras retas é um reticulado** (8.3): a força de arrasto é ``F = C_a·q·A_e``
  e se distribui pelas barras proporcionalmente à **área de sombra** de cada uma — a projeção
  ortogonal da barra num plano perpendicular ao vento (8.3, último parágrafo);
* a área de sombra de uma barra é ``ℓ·sen θ·c``: ``θ`` é o ângulo entre o vento e o eixo da barra
  e ``c`` a largura da seção vista pelo vento, pelas duas medidas da seção e pela direção da maior
  (a alma de um I ou de um U), que a macro do SolidWorks lê; sem a direção, ``c`` é a maior medida;
* **vento perpendicular às faces** (0°, 90°, 180° e 270° — o que a NBR 6123 pede em 8.5): as
  barras perpendiculares ao vento são agrupadas nos planos (reticulados) em que estão; cada plano
  tem o seu índice ``φ = A_e/A_contorno`` e o ``C_a`` da Figura 12; a parte de cada barra que fica
  atrás do contorno do plano imediatamente a barlavento é multiplicada pelo fator de proteção ``η``
  da Figura 14 (8.4). As barras fora desses planos (ao longo do vento ou inclinadas em planta) ficam
  com ``C_a = 2,0`` e sem proteção;
* **vento a 45°, 135°, 225° e 315°** (opcional): verificação a mais, a favor da segurança — cada
  barra com ``C_a = 2,0`` (o maior valor da Figura 12) e sem proteção;
* ``q`` de cada barra é o da cota do seu ponto mais alto, medida a partir do terreno;
* guarda-corpos, escadas e painéis que não estão no esqueleto entram como reticulados planos com o
  seu ``φ`` (sem proteção); equipamentos como caixa (``C_a = 2,0``) ou cilindro vertical (Tabelas
  27 e 28). A força de cada um vai para as barras que o apoiam.

A força de cada barra sai na direção do vento (arrasto) como carga distribuída uniforme na barra
(kN/m), com as componentes nos eixos X e Y da planta (Z para cima): o vento a θ sopra para
``(cos θ, sen θ)`` — W0 para +X, W90 para +Y. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb

Ponto = tuple[float, float, float]

DIRECOES_PERPENDICULARES: tuple[int, ...] = (0, 90, 180, 270)
DIRECOES_COM_DIAGONAIS: tuple[int, ...] = (0, 45, 90, 135, 180, 225, 270, 315)
#: Direção da planta para onde cada vento sopra (o código do caso no plano de cargas).
SENTIDOS: dict[int, str] = {
    0: "+X",
    45: "+X +Y",
    90: "+Y",
    135: "−X +Y",
    180: "−X",
    225: "−X −Y",
    270: "−Y",
    315: "+X −Y",
}

CA_SEM_PLANO = 2.0  # o maior C_a da Figura 12: barras fora dos planos e vento diagonal
#: Uma barra é "perpendicular ao vento" (cabe num reticulado plano) com |cos| até este valor (3°).
COS_PERPENDICULAR = 0.05
#: Barras perpendiculares ao vento a menos desta distância, ao longo do vento, ficam no mesmo plano.
TOLERANCIA_DO_PLANO_M = 0.25
#: Elementos sobre vigas: a viga que apoia fica até esta distância da linha do elemento.
TOLERANCIA_DO_APOIO_M = 0.35
SEN_PARALELA = math.sin(math.radians(10.0))
ORIGEM = "Vento barra a barra"

TIPO_GUARDA_CORPO = "Guarda-corpo"
TIPO_ESCADA = "Escada (lateral)"
TIPO_PAINEL = "Painel ou chapa cheia"
TIPO_CAIXA = "Equipamento (caixa)"
TIPO_CILINDRO = "Equipamento (cilindro vertical)"
TIPOS_DE_ELEMENTO: tuple[str, ...] = (
    TIPO_GUARDA_CORPO,
    TIPO_ESCADA,
    TIPO_PAINEL,
    TIPO_CAIXA,
    TIPO_CILINDRO,
)
TIPOS_EM_LINHA = frozenset({TIPO_GUARDA_CORPO, TIPO_ESCADA, TIPO_PAINEL})
#: Índice de área exposta de referência: guarda-corpo com rodapé, lateral de escada com guarda-corpo
#: e degraus, painel fechado.
PHI_PADRAO: dict[str, float] = {TIPO_GUARDA_CORPO: 0.30, TIPO_ESCADA: 0.50, TIPO_PAINEL: 1.0}


class VentoPorBarrasInvalido(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------------------------
# Vetores
# ---------------------------------------------------------------------------------------------
def _sub(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norma(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unitario(a: Sequence[float]) -> Ponto | None:
    n = _norma(a)
    if n <= 1e-12:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def vento(angulo_graus: float) -> Ponto:
    """Vetor unitário para onde o vento sopra (horizontal)."""
    a = math.radians(angulo_graus)
    return (math.cos(a), math.sin(a), 0.0)


def _lateral(angulo_graus: float) -> Ponto:
    """Horizontal, perpendicular ao vento (à esquerda de quem olha para onde ele sopra)."""
    a = math.radians(angulo_graus)
    return (-math.sin(a), math.cos(a), 0.0)


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0  # sem "−0,0"
    return f"{valor:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BarraAoVento:
    """Uma barra do esqueleto, nos eixos da planta (m; X e Y horizontais, Z para cima)."""

    nome: str
    inicio: Ponto
    fim: Ponto
    maior_m: float  # a maior medida da seção (altura de um I ou de um U; diâmetro de um tubo)
    menor_m: float
    direcao_maior: Ponto | None = None  # direção da maior medida (a alma); None: não se sabe
    perfil: str = ""
    nome_no_modelo: str = ""  # como o Simulation chama a viga ("Viga-3"), quando se sabe

    @property
    def vetor(self) -> Ponto:
        return _sub(self.fim, self.inicio)

    @property
    def comprimento_m(self) -> float:
        return _norma(self.vetor)

    @property
    def meio(self) -> Ponto:
        return tuple((a + b) / 2.0 for a, b in zip(self.inicio, self.fim, strict=True))  # type: ignore[return-value]

    @property
    def rotulo(self) -> str:
        return f"{self.nome} ({self.nome_no_modelo})" if self.nome_no_modelo else self.nome


@dataclass(frozen=True)
class ElementoAoVento:
    """O que recebe vento e não está no esqueleto: guarda-corpo, lateral de escada, painel,
    equipamento. Coordenadas na planta (m), como as das barras."""

    nome: str
    tipo: str
    ponto_1: Ponto  # guarda-corpo, escada, painel: uma ponta da linha da base; equipamento: o
    # centro da base
    ponto_2: Ponto | None = None  # a outra ponta da linha da base (guarda-corpo, escada, painel)
    altura_m: float = 1.1
    largura_x_m: float = 1.0  # equipamento: a medida em X da planta (o diâmetro, no cilindro)
    largura_y_m: float = 1.0  # equipamento: a medida em Y da planta
    phi: float | None = None  # índice de área exposta (None: o de referência do tipo)
    ca: float | None = None  # C_a informado (None: o da norma)
    barra: str = ""  # a barra que recebe a força; vazio: o programa escolhe

    @property
    def em_linha(self) -> bool:
        return self.tipo in TIPOS_EM_LINHA

    @property
    def indice(self) -> float:
        return self.phi if self.phi is not None else PHI_PADRAO.get(self.tipo, 1.0)


@dataclass(frozen=True)
class EntradaPorBarras:
    barras: tuple[BarraAoVento, ...]
    parametros: va.ParametrosVento = field(default_factory=va.ParametrosVento)
    elementos: tuple[ElementoAoVento, ...] = ()
    direcoes: tuple[int, ...] = DIRECOES_PERPENDICULARES
    cota_do_terreno_m: float | None = None  # None: o ponto mais baixo das barras
    protecao: bool = True  # fator η da Figura 14 entre planos (8.4)


def validar_entrada(e: EntradaPorBarras) -> list[str]:
    erros: list[str] = []
    if not e.barras:
        erros.append("Informe ao menos uma barra (o esqueleto do modelo ou a tabela de barras).")
    nomes = [b.nome for b in e.barras]
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    if repetidos:
        erros.append("Nomes de barra repetidos: " + ", ".join(repetidos[:6]) + ".")
    for b in e.barras:
        valores = (*b.inicio, *b.fim, b.maior_m, b.menor_m)
        if not all(math.isfinite(v) for v in valores):
            erros.append(f"{b.nome}: coordenada ou medida inválida.")
            continue
        if b.comprimento_m <= 1e-6:
            erros.append(f"{b.nome}: as duas pontas são o mesmo ponto.")
        if b.maior_m <= 0 or b.menor_m <= 0:
            erros.append(f"{b.nome}: as medidas da seção precisam ser maiores que zero.")
    if not e.direcoes:
        erros.append("Escolha ao menos uma direção do vento.")
    for d in e.direcoes:
        if d % 45 != 0 or not 0 <= d < 360:
            erros.append(f"Direção {d}°: use 0°, 45°, 90° … 315°.")
    existentes = set(nomes)
    for el in e.elementos:
        if el.tipo not in TIPOS_DE_ELEMENTO:
            erros.append(f"{el.nome}: tipo desconhecido ({el.tipo!r}).")
            continue
        if not el.altura_m > 0:
            erros.append(f"{el.nome}: a altura precisa ser maior que zero.")
        if el.em_linha:
            if el.ponto_2 is None:
                erros.append(f"{el.nome}: informe as duas pontas da linha da base.")
            elif math.hypot(el.ponto_2[0] - el.ponto_1[0], el.ponto_2[1] - el.ponto_1[1]) <= 1e-6:
                erros.append(f"{el.nome}: a linha da base não tem comprimento em planta.")
            if not 0.0 < el.indice <= 1.0:
                erros.append(f"{el.nome}: o índice de área exposta φ vai de 0 a 1.")
        elif not (el.largura_x_m > 0 and el.largura_y_m > 0):
            erros.append(f"{el.nome}: as medidas em planta precisam ser maiores que zero.")
        if el.ca is not None and not el.ca > 0:
            erros.append(f"{el.nome}: C_a precisa ser maior que zero.")
        if el.barra and el.barra not in existentes:
            erros.append(f"{el.nome}: a barra {el.barra!r} não está na lista de barras.")
    return erros


# ---------------------------------------------------------------------------------------------
# Do esqueleto do SolidWorks para a planta
# ---------------------------------------------------------------------------------------------
def para_a_planta(ponto: Sequence[float], eixo_vertical: str) -> Ponto:
    """Ponto ou vetor nos eixos do modelo → planta (Z para cima). Com o Y vertical do SolidWorks,
    (X, Y, Z) vira (X, −Z, Y): na vista Superior o desenho fica igual à planta do programa."""
    x, y, z = (float(v) for v in ponto)
    if eixo_vertical == "Y":
        return (x + 0.0, -z + 0.0, y + 0.0)
    return (x + 0.0, y + 0.0, z + 0.0)


def do_modelo(ponto: Sequence[float], eixo_vertical: str) -> Ponto:
    """Planta → eixos do modelo (inverso de :func:`para_a_planta`)."""
    x, y, z = (float(v) for v in ponto)
    if eixo_vertical == "Y":
        return (x + 0.0, z + 0.0, -y + 0.0)
    return (x + 0.0, y + 0.0, z + 0.0)


def barras_do_esqueleto(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> list[BarraAoVento]:
    """As barras (e os blocos) do esqueleto da macro, na planta, com a seção e a direção da alma.

    As chapas ficam de fora: piso deitado não recebe vento e chapa em pé pode ser só um apoio de
    carga do modelo — quando for uma superfície de verdade, entre com ela como painel.
    """
    perfis = ld.perfis_do_esqueleto(g)
    nomes = nomes_no_simulation or {}
    barras: list[BarraAoVento] = []
    for corpo in g.corpos:
        if corpo.forma == ld.FORMA_CHAPA or corpo.comprimento_m <= 0:
            continue
        if corpo.secao_mm:
            maior, menor = (max(corpo.secao_mm) / 1000.0, min(corpo.secao_mm) / 1000.0)
        else:
            maior = menor = 0.1
        direcao = (
            _unitario(para_a_planta(corpo.direcao_secao, eixo_vertical))
            if corpo.direcao_secao
            else None
        )
        barras.append(
            BarraAoVento(
                nome=corpo.nome,
                inicio=para_a_planta(corpo.inicio, eixo_vertical),
                fim=para_a_planta(corpo.fim, eixo_vertical),
                maior_m=maior,
                menor_m=max(menor, 1e-3),
                direcao_maior=direcao,
                perfil=perfis.get(corpo.nome, ("", ""))[0],
                nome_no_modelo=nomes.get(corpo.nome, ""),
            )
        )
    return barras


def chapas_em_pe(g: ld.GeometriaDoModelo, eixo_vertical: str) -> list[str]:
    """As chapas do esqueleto que estão em pé (podem receber vento): o programa não as carrega
    sozinho — só o engenheiro sabe se são superfície real ou apoio de carga do modelo."""
    cima = (0.0, 1.0, 0.0) if eixo_vertical == "Y" else (0.0, 0.0, 1.0)
    nomes = []
    for corpo in g.corpos:
        if corpo.forma != ld.FORMA_CHAPA:
            continue
        normal = None
        if len(corpo.contorno) >= 3:
            soma = [0.0, 0.0, 0.0]
            pontos = corpo.contorno
            for i, p in enumerate(pontos):
                q = pontos[(i + 1) % len(pontos)]
                soma[0] += (p[1] - q[1]) * (p[2] + q[2])
                soma[1] += (p[2] - q[2]) * (p[0] + q[0])
                soma[2] += (p[0] - q[0]) * (p[1] + q[1])
            normal = _unitario(soma)
        elif corpo.direcao_secao:
            normal = _unitario(corpo.direcao_secao)
        if normal is not None and abs(_dot(normal, cima)) < 0.5:
            nomes.append(corpo.nome)
    return nomes


# ---------------------------------------------------------------------------------------------
# Área de sombra
# ---------------------------------------------------------------------------------------------
def largura_vista(barra: BarraAoVento, angulo_graus: float) -> tuple[float, float]:
    """``(sen θ, c)``: o seno do ângulo entre o vento e o eixo da barra e a largura da seção vista
    pelo vento (a extensão da seção na direção perpendicular ao vento e ao eixo)."""
    u = _unitario(barra.vetor)
    if u is None:
        return 0.0, 0.0
    w = vento(angulo_graus)
    cos = _dot(w, u)
    normal = _sub(w, (cos * u[0], cos * u[1], cos * u[2]))
    sen = _norma(normal)
    if sen <= 1e-9:
        return 0.0, 0.0
    n = (normal[0] / sen, normal[1] / sen, normal[2] / sen)
    v = _cross(u, n)  # perpendicular ao vento e ao eixo: a direção da largura vista
    if barra.direcao_maior is None:
        return sen, barra.maior_m
    d = barra.direcao_maior
    projecao = _dot(d, u)
    s = _unitario(_sub(d, (projecao * u[0], projecao * u[1], projecao * u[2])))
    if s is None:
        return sen, barra.maior_m
    t = _cross(u, s)
    return sen, barra.maior_m * abs(_dot(s, v)) + barra.menor_m * abs(_dot(t, v))


def area_de_sombra(barra: BarraAoVento, angulo_graus: float) -> float:
    """Projeção ortogonal da barra num plano perpendicular ao vento: ``ℓ·sen θ·c`` (m²)."""
    sen, c = largura_vista(barra, angulo_graus)
    return barra.comprimento_m * sen * c


def _fracao_dentro(
    a: tuple[float, float], b: tuple[float, float], retangulo: tuple[float, float, float, float]
) -> float:
    """Fração do segmento a–b (no plano perpendicular ao vento) dentro do retângulo (Liang–Barsky).
    Segmento de um ponto só (barra ao longo do vento): 1 ou 0."""
    v0, v1, z0, z1 = retangulo
    dx, dz = b[0] - a[0], b[1] - a[1]
    if abs(dx) <= 1e-12 and abs(dz) <= 1e-12:
        return 1.0 if v0 <= a[0] <= v1 and z0 <= a[1] <= z1 else 0.0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - v0), (dx, v1 - a[0]), (-dz, a[1] - z0), (dz, z1 - a[1])):
        if abs(p) <= 1e-12:
            if q < -1e-9:
                return 0.0
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return 0.0
    return max(0.0, t1 - t0)


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PlanoDoVento:
    """Um reticulado plano perpendicular ao vento: as barras dele, φ, C_a e a proteção."""

    nome: str  # R1 = barlavento, R2, R3…
    coordenada_m: float  # posição ao longo do vento
    barras: tuple[str, ...]
    area_m2: float
    retangulo: tuple[float, float, float, float]  # (lateral mín., lateral máx., z mín., z máx.)
    phi: float
    ca: float
    eta: float  # da parte protegida pelo plano anterior (1,0 no de barlavento)
    afastamento_m: float = 0.0  # do plano anterior

    @property
    def largura_m(self) -> float:
        return self.retangulo[1] - self.retangulo[0]

    @property
    def altura_m(self) -> float:
        return self.retangulo[3] - self.retangulo[2]

    @property
    def contorno_m2(self) -> float:
        return self.largura_m * self.altura_m


@dataclass(frozen=True)
class ForcaNaBarra:
    barra: str
    rotulo: str
    comprimento_m: float
    sen: float
    largura_vista_m: float
    area_m2: float
    plano: str  # "R1"… ou "—" (fora dos planos)
    ca: float
    eta: float  # efetivo (com a fração protegida)
    fracao_protegida: float
    cota_m: float  # do ponto mais alto, a partir do terreno
    q_N_m2: float
    forca_kN: float
    fx_kN_m: float
    fy_kN_m: float

    @property
    def kN_m(self) -> float:
        return self.forca_kN / self.comprimento_m if self.comprimento_m > 0 else 0.0

    @property
    def calculo(self) -> str:
        return (
            f"F = C_a·η·q·A = {_n(self.ca)} × {_n(self.eta, 3)} × {_n(self.q_N_m2 / 1e3, 3)} × "
            f"{_n(self.area_m2, 3)} = {_n(self.forca_kN, 3)} kN; A = ℓ·sen θ·c = "
            f"{_n(self.comprimento_m)} × {_n(self.sen, 3)} × {_n(self.largura_vista_m, 3)}"
        )


@dataclass(frozen=True)
class ParcelaNaBarra:
    """O que um elemento manda para uma barra: kN/m na barra inteira ou a força total (kN)."""

    barra: str
    rotulo: str
    unidade: str  # "kN/m" ou "kN"
    fx: float
    fy: float
    comprimento_m: float


@dataclass(frozen=True)
class ForcaNoElemento:
    elemento: str
    tipo: str
    area_m2: float
    phi: float | None
    ca: float
    cota_m: float
    q_N_m2: float
    forca_kN: float
    fx_kN: float
    fy_kN: float
    ponto: Ponto  # onde a resultante passa (planta e cota do centro)
    parcelas: tuple[ParcelaNaBarra, ...]
    calculo: str
    aviso: str = ""


@dataclass(frozen=True)
class VentoNaDirecao:
    angulo: int
    perpendicular: bool
    barras: tuple[ForcaNaBarra, ...]
    elementos: tuple[ForcaNoElemento, ...]
    planos: tuple[PlanoDoVento, ...]
    momento_tombamento_kNm: float
    torcao_kNm: float  # em torno do eixo vertical pelo centro da planta

    @property
    def codigo(self) -> str:
        return f"W{self.angulo}"

    @property
    def fx_kN(self) -> float:
        return sum(b.fx_kN_m * b.comprimento_m for b in self.barras) + sum(
            e.fx_kN for e in self.elementos
        )

    @property
    def fy_kN(self) -> float:
        return sum(b.fy_kN_m * b.comprimento_m for b in self.barras) + sum(
            e.fy_kN for e in self.elementos
        )

    @property
    def estrutura_kN(self) -> float:
        return sum(b.forca_kN for b in self.barras)

    @property
    def elementos_kN(self) -> float:
        return sum(e.forca_kN for e in self.elementos)

    @property
    def total_kN(self) -> float:
        return self.estrutura_kN + self.elementos_kN

    def da_barra(self, nome: str) -> ForcaNaBarra | None:
        return next((b for b in self.barras if b.barra == nome), None)


@dataclass(frozen=True)
class ResultadoPorBarras:
    entrada: EntradaPorBarras
    cota_do_terreno_m: float
    altura_m: float  # do terreno ao ponto mais alto
    classe: str
    centro_m: tuple[float, float]
    direcoes: tuple[VentoNaDirecao, ...]
    vento_no_topo: vb.VentoNoLocal
    avisos: tuple[str, ...] = ()

    def direcao(self, angulo: int) -> VentoNaDirecao:
        for d in self.direcoes:
            if d.angulo == angulo:
                return d
        raise KeyError(angulo)

    @property
    def governante(self) -> VentoNaDirecao:
        return max(self.direcoes, key=lambda d: d.total_kN)


# ---------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------
class _PressaoPorCota:
    """q de cada cota, calculado uma vez."""

    def __init__(self, p: va.ParametrosVento, classe: str) -> None:
        self.p = p
        self.classe = classe
        self._cache: dict[float, vb.VentoNoLocal] = {}

    def __call__(self, cota_m: float) -> vb.VentoNoLocal:
        z = round(max(cota_m, 0.1), 3)
        if z not in self._cache:
            self._cache[z] = vb.calcular_vento_no_local(
                self.p.v0_m_s,
                s1=self.p.s1,
                categoria=self.p.categoria,
                classe=self.classe,
                altura_m=z,
                grupo_s3=self.p.grupo_s3,
                s3=self.p.s3,
            )
        return self._cache[z]


def _projecao(ponto: Sequence[float], angulo: int) -> tuple[float, float]:
    """(lateral, z) do ponto no plano perpendicular ao vento."""
    return (_dot(ponto, _lateral(angulo)), float(ponto[2]))


def _planos(
    barras: Sequence[BarraAoVento],
    angulo: int,
    larguras: Mapping[str, float],
    areas: Mapping[str, float],
    protecao: bool,
) -> tuple[list[PlanoDoVento], dict[str, tuple[str, float, float, float]]]:
    """Os reticulados perpendiculares ao vento e, por barra: (plano, C_a, η efetivo, fração)."""
    w = vento(angulo)
    candidatas = []
    for b in barras:
        u = _unitario(b.vetor)
        if u is None or areas[b.nome] <= 0:
            continue
        if abs(_dot(u, w)) <= COS_PERPENDICULAR:
            candidatas.append((_dot(b.meio, w), b))
    candidatas.sort(key=lambda item: item[0])
    grupos: list[list[tuple[float, BarraAoVento]]] = []
    for item in candidatas:
        if grupos and item[0] - grupos[-1][-1][0] <= TOLERANCIA_DO_PLANO_M:
            grupos[-1].append(item)
        else:
            grupos.append([item])
    planos: list[PlanoDoVento] = []
    por_barra: dict[str, tuple[str, float, float, float]] = {}
    for k, grupo in enumerate(grupos):
        nome = f"R{k + 1}"
        coordenada = sum(s for s, _ in grupo) / len(grupo)
        laterais: list[float] = []
        cotas: list[float] = []
        for _, b in grupo:
            meia = larguras[b.nome] / 2.0
            for ponta in (b.inicio, b.fim):
                lateral, z = _projecao(ponta, angulo)
                laterais.extend((lateral - meia, lateral + meia))
                cotas.extend((z - meia, z + meia))
        retangulo = (min(laterais), max(laterais), min(cotas), max(cotas))
        area = sum(areas[b.nome] for _, b in grupo)
        contorno = (retangulo[1] - retangulo[0]) * (retangulo[3] - retangulo[2])
        phi = min(1.0, area / contorno) if contorno > 0 else 1.0
        ca = va.ca_reticulado_plano(phi)
        eta = 1.0
        afastamento = 0.0
        anterior = planos[-1] if planos else None
        if anterior is not None and protecao:
            afastamento = coordenada - anterior.coordenada_m
            hb = min(anterior.largura_m, anterior.altura_m)
            if afastamento > 0 and hb > 0:
                eta = va.fator_de_protecao(anterior.phi, afastamento / hb)
        planos.append(
            PlanoDoVento(
                nome=nome,
                coordenada_m=coordenada,
                barras=tuple(b.nome for _, b in grupo),
                area_m2=area,
                retangulo=retangulo,
                phi=phi,
                ca=ca,
                eta=eta,
                afastamento_m=afastamento,
            )
        )
        for _, b in grupo:
            fracao = 0.0
            if anterior is not None and eta < 1.0:
                fracao = _fracao_dentro(
                    _projecao(b.inicio, angulo), _projecao(b.fim, angulo), anterior.retangulo
                )
            por_barra[b.nome] = (nome, ca, 1.0 - fracao * (1.0 - eta), fracao)
    return planos, por_barra


def _distancia_ponto_barra(p: Sequence[float], b: BarraAoVento) -> float:
    ab = b.vetor
    comprimento2 = _dot(ab, ab)
    t = 0.0 if comprimento2 <= 0 else max(0.0, min(1.0, _dot(_sub(p, b.inicio), ab) / comprimento2))
    perto = (b.inicio[0] + t * ab[0], b.inicio[1] + t * ab[1], b.inicio[2] + t * ab[2])
    return _norma(_sub(p, perto))


def _apoios_da_linha(
    el: ElementoAoVento, barras: Sequence[BarraAoVento]
) -> list[tuple[BarraAoVento, float]]:
    """Vigas sob a linha do elemento: horizontais, na cota da base, paralelas e ao lado da linha;
    cada uma com o trecho que apoia (m)."""
    assert el.ponto_2 is not None
    base = min(el.ponto_1[2], el.ponto_2[2])
    linha = (el.ponto_2[0] - el.ponto_1[0], el.ponto_2[1] - el.ponto_1[1], 0.0)
    comprimento = _norma(linha)
    direcao = (linha[0] / comprimento, linha[1] / comprimento, 0.0)
    apoios = []
    for b in barras:
        u = _unitario(b.vetor)
        if u is None or abs(u[2]) > 0.1:
            continue
        if abs(b.meio[2] - base) > TOLERANCIA_DO_APOIO_M:
            continue
        horizontal = _unitario((u[0], u[1], 0.0))
        if horizontal is None or abs(_cross(horizontal, direcao)[2]) > SEN_PARALELA:
            continue
        rel = _sub(b.meio, el.ponto_1)
        distancia = abs(rel[0] * direcao[1] - rel[1] * direcao[0])
        if distancia > TOLERANCIA_DO_APOIO_M:
            continue
        t1 = _dot(_sub(b.inicio, el.ponto_1), direcao)
        t2 = _dot(_sub(b.fim, el.ponto_1), direcao)
        trecho = min(max(t1, t2), comprimento) - max(min(t1, t2), 0.0)
        if trecho > 0.05:
            apoios.append((b, trecho))
    return apoios


def _forca_do_elemento(
    el: ElementoAoVento,
    angulo: int,
    perpendicular: bool,
    pressao: _PressaoPorCota,
    terreno: float,
    barras: Sequence[BarraAoVento],
    por_nome: Mapping[str, BarraAoVento],
) -> ForcaNoElemento:
    w = vento(angulo)
    base = el.ponto_1[2] if el.ponto_2 is None else min(el.ponto_1[2], el.ponto_2[2])
    # q do ponto mais alto do elemento (no guarda-corpo de escada, o da ponta de cima).
    topo = (
        el.ponto_1[2] if el.ponto_2 is None else max(el.ponto_1[2], el.ponto_2[2])
    ) + el.altura_m
    local = pressao(topo - terreno)
    q = local.q_N_m2 / 1e3
    phi: float | None = None
    if el.em_linha:
        assert el.ponto_2 is not None
        dx, dy = el.ponto_2[0] - el.ponto_1[0], el.ponto_2[1] - el.ponto_1[1]
        comprimento = math.hypot(dx, dy)
        sen = abs(dx * w[1] - dy * w[0]) / comprimento
        phi = el.indice
        area = phi * el.altura_m * comprimento * sen
        if el.ca is not None:
            ca, origem = el.ca, "informado"
        elif perpendicular:
            ca, origem = va.ca_reticulado_plano(phi), f"Figura 12 com φ = {_n(phi)}"
        else:
            ca, origem = CA_SEM_PLANO, "2,0 (vento diagonal: o maior da Figura 12)"
        calculo = (
            f"F = C_a·q·φ·h·L·sen θ = {_n(ca)} × {_n(q, 3)} × {_n(phi)} × {_n(el.altura_m)} × "
            f"{_n(comprimento)} × {_n(sen, 3)}; C_a {origem}"
        )
        centro = ((el.ponto_1[0] + el.ponto_2[0]) / 2, (el.ponto_1[1] + el.ponto_2[1]) / 2, base)
    elif el.tipo == TIPO_CILINDRO:
        d = el.largura_x_m
        area = d * el.altura_m
        if el.ca is not None:
            ca, origem = el.ca, "informado"
        else:
            re = va.numero_de_reynolds(local.vk_m_s, d)
            tipo = "circular_subcritico" if re < 4.2e5 else "circular_acima_do_critico"
            k = va.fator_k_comprimento(2.0 * el.altura_m / d, tipo)
            ca = va.ca_cilindro(re) * k
            origem = f"Tab. 27 (Re = {re:.2g}) × K = {_n(k)} (Tab. 28, 2ℓ/d: base apoiada)"
        calculo = (
            f"F = C_a·q·d·h = {_n(ca)} × {_n(q, 3)} × {_n(d)} × {_n(el.altura_m)}; C_a {origem}"
        )
        centro = (el.ponto_1[0], el.ponto_1[1], base)
    else:
        largura = el.largura_x_m * abs(w[1]) + el.largura_y_m * abs(w[0])
        area = largura * el.altura_m
        ca = el.ca if el.ca is not None else CA_SEM_PLANO
        origem = "informado" if el.ca is not None else "2,0 (a favor da segurança)"
        calculo = (
            f"F = C_a·q·b·h = {_n(ca)} × {_n(q, 3)} × {_n(largura, 3)} × {_n(el.altura_m)}; "
            f"b = largura vista; C_a {origem}"
        )
        centro = (el.ponto_1[0], el.ponto_1[1], base)
    forca = ca * q * area
    fx, fy = forca * w[0], forca * w[1]
    ponto = (centro[0], centro[1], base + el.altura_m / 2.0)
    parcelas: list[ParcelaNaBarra] = []
    aviso = ""
    if el.barra:
        destino = [(por_nome[el.barra], 1.0)]
    elif el.em_linha:
        apoios = _apoios_da_linha(el, barras)
        total = sum(t for _, t in apoios)
        destino = [(b, t / total) for b, t in apoios] if total > 0 else []
    else:
        destino = []
    if not destino and barras:
        mais_perto = min(barras, key=lambda b: _distancia_ponto_barra(centro, b))
        destino = [(mais_perto, 1.0)]
        if el.em_linha:
            aviso = (
                f"{el.nome}: nenhuma viga na cota da base ao longo da linha — a força foi para a "
                f"barra mais próxima ({mais_perto.nome}). Confira ou escolha a barra."
            )
    for b, fracao in destino:
        if el.em_linha:
            parcelas.append(
                ParcelaNaBarra(
                    b.nome,
                    b.rotulo,
                    "kN/m",
                    fx * fracao / b.comprimento_m,
                    fy * fracao / b.comprimento_m,
                    b.comprimento_m,
                )
            )
        else:
            parcelas.append(
                ParcelaNaBarra(b.nome, b.rotulo, "kN", fx * fracao, fy * fracao, b.comprimento_m)
            )
    return ForcaNoElemento(
        elemento=el.nome,
        tipo=el.tipo,
        area_m2=area,
        phi=phi,
        ca=ca,
        cota_m=topo - terreno,
        q_N_m2=local.q_N_m2,
        forca_kN=forca,
        fx_kN=fx,
        fy_kN=fy,
        ponto=ponto,
        parcelas=tuple(parcelas),
        calculo=calculo,
        aviso=aviso,
    )


def _limites(e: EntradaPorBarras) -> tuple[float, float, float, float, float, float]:
    xs, ys, zs = [], [], []
    for b in e.barras:
        for p in (b.inicio, b.fim):
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
    for el in e.elementos:
        for ponto in (el.ponto_1, el.ponto_2):
            if ponto is None:
                continue
            p = ponto
            xs.append(p[0])
            ys.append(p[1])
            zs.append(p[2])
        base = el.ponto_1[2] if el.ponto_2 is None else min(el.ponto_1[2], el.ponto_2[2])
        zs.append(base + el.altura_m)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def calcular(e: EntradaPorBarras) -> ResultadoPorBarras:
    """O vento em cada barra e elemento, em cada direção pedida."""
    erros = validar_entrada(e)
    if erros:
        raise VentoPorBarrasInvalido(" ".join(erros))
    if not (math.isfinite(e.parametros.v0_m_s) and e.parametros.v0_m_s > 0):
        raise VentoPorBarrasInvalido("V₀ precisa ser maior que zero.")
    x0, x1, y0, y1, z0, z1 = _limites(e)
    terreno = z0 if e.cota_do_terreno_m is None else float(e.cota_do_terreno_m)
    altura = z1 - terreno
    if altura <= 0:
        raise VentoPorBarrasInvalido(
            "A cota do terreno está acima de toda a estrutura: confira o valor (no modelo, a cota "
            "do pé dos pilares)."
        )
    classe = vb.classe_da_edificacao(max(x1 - x0, y1 - y0, altura, 0.1))
    pressao = _PressaoPorCota(e.parametros, classe)
    centro = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    por_nome = {b.nome: b for b in e.barras}
    direcoes: list[VentoNaDirecao] = []
    for angulo in sorted(set(e.direcoes)):
        w = vento(angulo)
        perpendicular = angulo % 90 == 0
        larguras: dict[str, float] = {}
        areas: dict[str, float] = {}
        senos: dict[str, float] = {}
        for b in e.barras:
            sen, c = largura_vista(b, angulo)
            senos[b.nome], larguras[b.nome] = sen, c
            areas[b.nome] = b.comprimento_m * sen * c
        planos: list[PlanoDoVento] = []
        por_barra: dict[str, tuple[str, float, float, float]] = {}
        if perpendicular:
            planos, por_barra = _planos(e.barras, angulo, larguras, areas, e.protecao)
        forcas: list[ForcaNaBarra] = []
        tombamento = 0.0
        torcao = 0.0
        for b in e.barras:
            area = areas[b.nome]
            plano, ca, eta, fracao = por_barra.get(b.nome, ("—", CA_SEM_PLANO, 1.0, 0.0))
            cota = max(b.inicio[2], b.fim[2]) - terreno
            local = pressao(cota)
            forca = ca * eta * local.q_N_m2 / 1e3 * area
            por_metro = forca / b.comprimento_m
            forcas.append(
                ForcaNaBarra(
                    barra=b.nome,
                    rotulo=b.rotulo,
                    comprimento_m=b.comprimento_m,
                    sen=senos[b.nome],
                    largura_vista_m=larguras[b.nome],
                    area_m2=area,
                    plano=plano,
                    ca=ca,
                    eta=eta,
                    fracao_protegida=fracao,
                    cota_m=cota,
                    q_N_m2=local.q_N_m2,
                    forca_kN=forca,
                    fx_kN_m=por_metro * w[0],
                    fy_kN_m=por_metro * w[1],
                )
            )
            meio = b.meio
            tombamento += forca * (meio[2] - terreno)
            torcao += (meio[0] - centro[0]) * forca * w[1] - (meio[1] - centro[1]) * forca * w[0]
        elementos = []
        for el in e.elementos:
            f = _forca_do_elemento(el, angulo, perpendicular, pressao, terreno, e.barras, por_nome)
            elementos.append(f)
            tombamento += f.forca_kN * (f.ponto[2] - terreno)
            torcao += (f.ponto[0] - centro[0]) * f.fy_kN - (f.ponto[1] - centro[1]) * f.fx_kN
        direcoes.append(
            VentoNaDirecao(
                angulo=angulo,
                perpendicular=perpendicular,
                barras=tuple(forcas),
                elementos=tuple(elementos),
                planos=tuple(planos),
                momento_tombamento_kNm=tombamento,
                torcao_kNm=torcao,
            )
        )
    topo = pressao(altura)
    avisos: list[str] = list(topo.avisos)
    for d in direcoes:
        avisos.extend(f.aviso for f in d.elementos if f.aviso)
    # Plano de uma barra só tem φ ≈ 1 por definição: o aviso é para painéis de verdade (> 1 m).
    fechados = sorted(
        {
            p.nome
            for d in direcoes
            for p in d.planos
            if p.phi > 0.6 and len(p.barras) >= 3 and min(p.largura_m, p.altura_m) > 1.0
        }
    )
    if fechados:
        avisos.append(
            "Há plano com índice de área exposta φ > 0,6 (quase fechado): confira se não é o caso "
            "de tratá-lo como placa ou edificação."
        )
    menor = min(x1 - x0, y1 - y0)
    if menor > 0 and altura / menor > 6:
        avisos.append(
            "Estrutura esbelta (altura maior que 6 vezes a menor dimensão em planta): avalie os "
            "efeitos dinâmicos do vento (NBR 6123, capítulo 9)."
        )
    return ResultadoPorBarras(
        entrada=e,
        cota_do_terreno_m=terreno,
        altura_m=altura,
        classe=classe,
        centro_m=centro,
        direcoes=tuple(direcoes),
        vento_no_topo=topo,
        avisos=tuple(dict.fromkeys(avisos)),
    )


# ---------------------------------------------------------------------------------------------
# Plano de cargas e arquivos
# ---------------------------------------------------------------------------------------------
def _sinal(valor: float, eixo: str) -> str:
    return ("+" if valor >= 0 else "−") + eixo


def cargas_da_direcao(d: VentoNaDirecao) -> list[pc.CargaDoModelo]:
    """As linhas do plano de uma direção: kN/m em cada barra (componentes X e Y) e as parcelas dos
    elementos nas barras que os apoiam."""
    linhas: list[pc.CargaDoModelo] = []
    for f in d.barras:
        if f.forca_kN <= 1e-9:
            continue
        observacao = (
            f"vento {d.angulo}°: {_n(f.forca_kN, 3)} kN (C_a {_n(f.ca)}, η {_n(f.eta, 3)}, "
            f"q {_n(f.q_N_m2 / 1e3, 3)} kN/m², A {_n(f.area_m2, 3)} m², plano {f.plano})"
        )
        for valor, eixo in ((f.fx_kN_m, "X"), (f.fy_kN_m, "Y")):
            if abs(valor) > 1e-7:
                linhas.append(
                    pc.CargaDoModelo(
                        elemento=f.rotulo,
                        valor=round(valor, 5),
                        unidade="kN/m",
                        direcao=_sinal(valor, eixo),
                        observacao=observacao,
                        comprimento_m=round(f.comprimento_m, 4),
                    )
                )
    for el in d.elementos:
        for p in el.parcelas:
            for valor, eixo in ((p.fx, "X"), (p.fy, "Y")):
                if abs(valor) > 1e-7:
                    linhas.append(
                        pc.CargaDoModelo(
                            elemento=p.rotulo,
                            valor=round(valor, 5),
                            unidade=p.unidade,
                            direcao=_sinal(valor, eixo),
                            observacao=(
                                f"{el.elemento} ({el.tipo.lower()}): {_n(el.forca_kN, 3)} kN"
                                + (
                                    " — força total na barra (no SolidWorks: Força › Por item)"
                                    if p.unidade == "kN"
                                    else ""
                                )
                            ),
                            comprimento_m=round(p.comprimento_m, 4) if p.unidade == "kN/m" else 0.0,
                        )
                    )
    return linhas


def acoes_para_o_plano(r: ResultadoPorBarras) -> list[pc.Acao]:
    """W0, W45 … W315 (as direções calculadas) com as cargas em cada barra."""
    acoes = []
    for d in r.direcoes:
        resumo = (
            f"Vento barra a barra a {d.angulo}° ({SENTIDOS[d.angulo]}): {_n(d.total_kN)} kN "
            f"({_n(d.estrutura_kN)} kN nas barras, {_n(d.elementos_kN)} kN em guarda-corpos, "
            f"escadas e equipamentos); tombamento {_n(d.momento_tombamento_kNm)} kN·m; torção "
            f"{_n(d.torcao_kNm)} kN·m."
        )
        acoes.append(
            pc.nova_acao(d.codigo, origem=ORIGEM, resumo=resumo, cargas=cargas_da_direcao(d))
        )
    return acoes


def plano_com_o_vento(plano: pc.PlanoDeCargas, r: ResultadoPorBarras) -> pc.PlanoDeCargas:
    """O plano com o vento barra a barra: as direções calculadas entram (ou substituem) e as
    diagonais de um envio anterior saem quando agora só as perpendiculares foram calculadas."""
    calculadas = {d.codigo for d in r.direcoes}
    for codigo in pc.CODIGOS_DE_VENTO:
        if codigo not in calculadas and codigo not in pc.CODIGOS_DE_VENTO_PERPENDICULARES:
            plano = pc.sem_acao(plano, codigo)
    for acao in acoes_para_o_plano(r):
        plano = pc.com_acao(plano, acao)
    return plano


def _csv(cabecalho: Sequence[str], linhas: Iterable[Sequence[object]]) -> bytes:
    def campo(v: object) -> str:
        if isinstance(v, float):
            return f"{v:.4f}".replace(".", ",")
        return str(v).replace(";", ",")

    texto = [";".join(cabecalho)]
    texto.extend(";".join(campo(v) for v in linha) for linha in linhas)
    return ("﻿" + "\r\n".join(texto) + "\r\n").encode("utf-8")


def csv_das_cargas(r: ResultadoPorBarras) -> bytes:
    """Uma linha por barra (ou parcela de elemento) e direção, com kN/m e as componentes."""
    linhas: list[list[object]] = []
    for d in r.direcoes:
        for f in d.barras:
            linhas.append(
                [
                    d.codigo,
                    f.rotulo,
                    "barra",
                    f.plano,
                    f.area_m2,
                    f.ca,
                    f.eta,
                    f.q_N_m2 / 1e3,
                    f.forca_kN,
                    "kN/m",
                    f.kN_m,
                    f.fx_kN_m,
                    f.fy_kN_m,
                ]
            )
        for el in d.elementos:
            for p in el.parcelas:
                linhas.append(
                    [
                        d.codigo,
                        p.rotulo,
                        f"{el.elemento} ({el.tipo})",
                        "—",
                        el.area_m2,
                        el.ca,
                        1.0,
                        el.q_N_m2 / 1e3,
                        el.forca_kN,
                        p.unidade,
                        math.hypot(p.fx, p.fy),
                        p.fx,
                        p.fy,
                    ]
                )
    return _csv(
        (
            "Caso",
            "Barra",
            "Origem",
            "Plano",
            "Área de sombra (m²)",
            "C_a",
            "η",
            "q (kN/m²)",
            "Força (kN)",
            "Unidade",
            "Valor",
            "Componente X",
            "Componente Y",
        ),
        linhas,
    )


def com_nomes_do_simulation(
    barras: Sequence[BarraAoVento], nomes: Mapping[str, str]
) -> list[BarraAoVento]:
    return [replace(b, nome_no_modelo=nomes.get(b.nome, b.nome_no_modelo)) for b in barras]
