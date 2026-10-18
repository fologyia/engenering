"""Núcleo da cena 3D: o modelo visto de qualquer lado — barras com o perfil de verdade, chapas,
setas de força, cargas distribuídas, reações, apoios e rótulos — com luz, profundidade e
enquadramento. Não sabe de onde vêm os dados nem como serão desenhados.

* **Entrada**: uma :class:`Cena` com primitivas em coordenadas da **planta** (X e Y horizontais,
  Z para cima, em metros). As fábricas que montam a cena a partir do esqueleto do SolidWorks, do
  plano de cargas e dos esforços ficam em :mod:`core.cena_do_modelo`.
* **Saída**: :func:`projetar` devolve um :class:`Desenho2D` — polígonos, linhas, setas e etiquetas já
  na tela, na ordem de desenho —, que vira SVG (:mod:`components.cena_3d_svg`, nas páginas) ou PNG
  (:mod:`core.cena_3d_png`, no memorial). Os dois lados desenham a mesma coisa.

Como desenha:

* cada barra é a **seção do perfil** (I, U, L, T, tubo, barra) varrida ao longo da linha de centro,
  com a alma na direção que a macro leu; barras compridas são cortadas em pedaços para a ordem de
  desenho sair certa; acima de ``LIMITE_DE_FACES`` faces (modelo enorme) as barras viram linhas;
* faces de trás de cada sólido não são desenhadas; as outras vão do fundo para a frente (pintor),
  com luz difusa vinda de cima e da esquerda de quem olha;
* setas, cargas e rótulos vão por cima de tudo (para serem lidos), com os rótulos sem se cobrirem.

Robustez: ponto com coordenada inválida, barra de comprimento zero e polígono degenerado ficam de
fora com aviso; cena vazia sai com a mensagem no lugar do desenho. Nada aqui levanta exceção por
geometria. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

Ponto = tuple[float, float, float]
Ponto2 = tuple[float, float]

FORMA_I = "I"
FORMA_U = "U"
FORMA_L = "L"
FORMA_T = "T"
FORMA_TUBO_RETANGULAR = "tubo retangular"
FORMA_TUBO_CIRCULAR = "tubo circular"
FORMA_CHEIA = "cheia"
FORMAS = (
    FORMA_I,
    FORMA_U,
    FORMA_L,
    FORMA_T,
    FORMA_TUBO_RETANGULAR,
    FORMA_TUBO_CIRCULAR,
    FORMA_CHEIA,
)

APOIO_ENGASTE = "engastado"
APOIO_ARTICULADO = "articulado"
APOIO_DESCONHECIDO = "apoio"
TIPOS_DE_APOIO = (APOIO_ENGASTE, APOIO_ARTICULADO, APOIO_DESCONHECIDO)

#: Vistas padrão: (azimute de onde se olha, elevação), em graus, na planta.
VISTA_ISOMETRICA = "Isométrica"
VISTA_SUPERIOR = "Superior"
VISTA_FRONTAL = "Frontal"
VISTA_LATERAL = "Lateral"
VISTAS: dict[str, tuple[float, float]] = {
    VISTA_ISOMETRICA: (-125.0, 27.0),
    VISTA_SUPERIOR: (-90.0, 89.5),
    VISTA_FRONTAL: (-90.0, 0.5),
    VISTA_LATERAL: (0.0, 0.5),
}

LIMITE_DE_FACES = 60_000  # acima disso, barras como linhas
PEDACO_MAXIMO_RELATIVO = 1 / 10  # da maior dimensão da cena (para a ordem de desenho)
PEDACOS_POR_BARRA_MAXIMO = 8
COR_PADRAO = "#8a929c"
COR_CONTORNO = "#2b2f36"
COR_SUAVE = "#6b7280"


# ---------------------------------------------------------------------------------------------
# Vetores
# ---------------------------------------------------------------------------------------------
def _sub(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _soma(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _escala(a: Sequence[float], k: float) -> Ponto:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Ponto:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norma(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unitario(a: Sequence[float]) -> Ponto | None:
    n = _norma(a)
    if not math.isfinite(n) or n < 1e-12:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def normal_da_face(face: Sequence[Sequence[float]]) -> Ponto | None:
    """Normal unitária pelo método de Newell (vale para polígono côncavo, como a tampa de um I)."""
    nx = ny = nz = 0.0
    n = len(face)
    for i in range(n):
        x1, y1, z1 = face[i]
        x2, y2, z2 = face[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return _unitario((nx, ny, nz))


def finito(*valores: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in valores)


def _ponto_ok(p: Sequence[float] | None) -> bool:
    return p is not None and len(p) == 3 and finito(*p)


# ---------------------------------------------------------------------------------------------
# Câmera, enquadramento e rótulos (também usados pelos desenhos 2D das páginas)
# ---------------------------------------------------------------------------------------------
class Camera:
    """Vista axonométrica (paralela) de um ponto de vista no alto: azimute e elevação em graus.

    ``tela(p)`` dá (x, y) na tela antes do enquadramento (y para baixo); ``profundidade(p)``
    cresce para perto de quem olha (para desenhar do fundo para a frente).
    """

    def __init__(self, azimute_graus: float, elevacao_graus: float = 28.0) -> None:
        elevacao_graus = max(-89.9, min(89.9, elevacao_graus))
        a, e = math.radians(azimute_graus), math.radians(elevacao_graus)
        self.olho = (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))
        self.direita = (-math.sin(a), math.cos(a), 0.0)
        frente = (-self.olho[0], -self.olho[1], -self.olho[2])
        self.cima = _cross(self.direita, frente)

    def tela(self, p: Sequence[float]) -> tuple[float, float]:
        return _dot(p, self.direita), -_dot(p, self.cima)

    def profundidade(self, p: Sequence[float]) -> float:
        return _dot(p, self.olho)

    def luz(self) -> Ponto:
        """De cima e da esquerda de quem olha (sombreado que lê bem em qualquer vista)."""
        return _unitario(
            _soma(_soma(self.olho, _escala(self.cima, 0.9)), _escala(self.direita, -0.6))
        ) or (0.0, 0.0, 1.0)


class Enquadramento:
    """Leva coordenadas da tela para a área útil, na mesma escala em x e y. Pontos inválidos não
    entram na conta; sem pontos, fica a identidade no centro da área."""

    def __init__(
        self,
        pontos: Sequence[tuple[float, float]],
        area: tuple[float, float, float, float],
        *,
        escala_maxima: float = math.inf,
    ) -> None:
        x0, y0, x1, y1 = area
        validos = [p for p in pontos if finito(p[0], p[1])]
        if not validos:
            validos = [(0.0, 0.0)]
        xs = [p[0] for p in validos]
        ys = [p[1] for p in validos]
        self.xmin, self.xmax, self.ymin, self.ymax = min(xs), max(xs), min(ys), max(ys)
        largura = max(self.xmax - self.xmin, 1e-6)
        altura = max(self.ymax - self.ymin, 1e-6)
        escala = min((x1 - x0) / largura, (y1 - y0) / altura, escala_maxima)
        if not math.isfinite(escala) or escala <= 0:
            escala = 1.0
        if len(validos) == 1 or (self.xmax - self.xmin < 1e-6 and self.ymax - self.ymin < 1e-6):
            escala = min(escala, 1.0)
        self.escala = escala
        self.dx = x0 + ((x1 - x0) - largura * escala) / 2 - self.xmin * escala
        self.dy = y0 + ((y1 - y0) - altura * escala) / 2 - self.ymin * escala

    def __call__(self, p: tuple[float, float]) -> tuple[float, float]:
        return p[0] * self.escala + self.dx, p[1] * self.escala + self.dy


def largura_do_texto(conteudo: str, tamanho: float) -> float:
    """Largura aproximada do texto (fonte sem serifa): estreitas e largas contam diferente."""
    estreitas = sum(1 for c in conteudo if c in "il.,:;|'!()[]/ ·")
    largas = sum(1 for c in conteudo if c in "mwMWÇ")
    return tamanho * (0.53 * (len(conteudo) - estreitas - largas) + 0.3 * estreitas + 0.8 * largas)


class Rotulos:
    """Coloca etiquetas sem que uma cubra a outra: se bater, sobe (ou desce) até achar lugar."""

    def __init__(self, limites: tuple[float, float, float, float] | None = None) -> None:
        self.caixas: list[tuple[float, float, float, float]] = []
        self.limites = limites

    def lugar(self, x: float, y: float, conteudo: str, tamanho: float) -> tuple[float, float]:
        largura = largura_do_texto(conteudo, tamanho) + 12
        altura = tamanho + 9
        if self.limites is not None:
            x0, _, x1, _ = self.limites
            x = max(x0 + largura / 2, min(x1 - largura / 2, x))
        for tentativa in range(16):
            deslocamento = (tentativa + 1) // 2 * altura * (1 if tentativa % 2 else -1)
            yy = y + deslocamento
            caixa = (x - largura / 2, yy - altura / 2, x + largura / 2, yy + altura / 2)
            if all(
                caixa[2] <= c[0] or caixa[0] >= c[2] or caixa[3] <= c[1] or caixa[1] >= c[3]
                for c in self.caixas
            ):
                self.caixas.append(caixa)
                return x, yy
        self.caixas.append((x - largura / 2, y - altura / 2, x + largura / 2, y + altura / 2))
        return x, y

    def ocupar(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.caixas.append((x0, y0, x1, y1))


# ---------------------------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------------------------
PALETA_CARGA: tuple[str, ...] = ("#fde7c8", "#f8b46a", "#e5781c", "#b54708", "#7a2e0e")
PALETA_APROVEITAMENTO: tuple[str, ...] = ("#2e7d32", "#9ccc65", "#fdd835", "#fb8c00", "#c62828")
PALETA_SINAL: tuple[str, ...] = ("#c62828", "#ef9a9a", "#eceff1", "#90caf9", "#1565c0")  # − a +
PALETA_CATEGORIAS: tuple[str, ...] = (
    "#3f6fb5",
    "#d4760a",
    "#2e7d32",
    "#8e44ad",
    "#c0392b",
    "#16a085",
    "#7f8c8d",
    "#b8860b",
    "#1abc9c",
    "#e67e22",
)


def _rgb(cor: str) -> tuple[int, int, int]:
    cor = cor.lstrip("#")
    if len(cor) != 6:
        return (138, 146, 156)
    try:
        return int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16)
    except ValueError:
        return (138, 146, 156)


def _hex(rgb: Sequence[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def cor_da_escala(fracao: float, paleta: Sequence[str] = PALETA_CARGA) -> str:
    """Cor da paleta para uma fração de 0 a 1 (interpolação linear entre as cores)."""
    f = max(0.0, min(1.0, fracao if finito(fracao) else 0.0))
    posicao = f * (len(paleta) - 1)
    i = min(int(posicao), len(paleta) - 2)
    t = posicao - i
    a, b = _rgb(paleta[i]), _rgb(paleta[i + 1])
    return _hex([a[k] + (b[k] - a[k]) * t for k in range(3)])


def sombrear(cor: str, intensidade: float) -> str:
    r, g, b = _rgb(cor)
    f = 0.45 + 0.55 * max(0.0, min(1.0, intensidade))
    return _hex((r * f, g * f, b * f))


# ---------------------------------------------------------------------------------------------
# Primitivas da cena
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Secao:
    """A seção para desenhar (m): ``d`` ao longo da alma, ``b`` ao longo da mesa."""

    forma: str = FORMA_CHEIA
    d: float = 0.10
    b: float = 0.10
    tw: float = 0.008
    tf: float = 0.010

    def contorno(self) -> list[Ponto2]:
        """(t, s) no plano da seção: t ao longo da mesa, s ao longo da alma, centro na origem."""
        d = max(self.d, 1e-3)
        b = max(self.b, 1e-3)
        tw = max(min(self.tw, b / 2), 1e-3)
        tf = max(min(self.tf, d / 3), 1e-3)
        h, w = d / 2, b / 2
        if self.forma == FORMA_I:
            return [
                (-w, -h), (w, -h), (w, -h + tf), (tw / 2, -h + tf), (tw / 2, h - tf),
                (w, h - tf), (w, h), (-w, h), (-w, h - tf), (-tw / 2, h - tf),
                (-tw / 2, -h + tf), (-w, -h + tf),
            ]  # fmt: skip
        if self.forma == FORMA_U:
            return [
                (-w, -h), (w, -h), (w, -h + tf), (-w + tw, -h + tf), (-w + tw, h - tf),
                (w, h - tf), (w, h), (-w, h),
            ]  # fmt: skip
        if self.forma == FORMA_L:
            c = d / 3.4
            t = tw
            return [
                (-c, -c),
                (b - c, -c),
                (b - c, t - c),
                (t - c, t - c),
                (t - c, d - c),
                (-c, d - c),
            ]
        if self.forma == FORMA_T:
            return [
                (-w, h), (-w, h - tf), (-tw / 2, h - tf), (-tw / 2, -h), (tw / 2, -h),
                (tw / 2, h - tf), (w, h - tf), (w, h),
            ]  # fmt: skip
        if self.forma == FORMA_TUBO_CIRCULAR:
            r = d / 2
            return [
                (r * math.cos(2 * math.pi * k / 12), r * math.sin(2 * math.pi * k / 12))
                for k in range(12)
            ]
        return [(-w, -h), (w, -h), (w, h), (-w, h)]


@dataclass(frozen=True)
class BarraCena:
    nome: str
    inicio: Ponto
    fim: Ponto
    secao: Secao | None = None  # None: só a linha
    alma: Ponto | None = None  # direção da alma (medida d); None: a vertical (ou X na barra em pé)
    cor: str = COR_PADRAO
    rotulo: str = ""  # escrito no desenho (as barras com rótulo têm prioridade)
    destaque: bool = False  # a barra selecionada: as outras ficam claras
    grupo: str = ""


@dataclass(frozen=True)
class PainelCena:
    nome: str
    pontos: tuple[Ponto, ...]
    cor: str = "#c9d6e6"
    opacidade: float = 0.35
    grupo: str = ""


@dataclass(frozen=True)
class SetaCena:
    """Força concentrada: ``vetor`` (kN) com a ponta no ``ponto`` (força aplicada) ou saindo dele
    (reação)."""

    ponto: Ponto
    vetor: Ponto
    rotulo: str = ""
    cor: str = "#d4760a"
    reacao: bool = False
    grupo: str = ""
    larga: bool = False  # seta cheia e larga (a direção do vento)
    comprimento_relativo: float | None = None  # fixa o tamanho (fração da cena), sem escalar


@dataclass(frozen=True)
class CargaDistribuidaCena:
    """Carga por metro ao longo de uma barra: uma fileira de setas (o pente)."""

    inicio: Ponto
    fim: Ponto
    vetor_por_metro: Ponto  # kN/m
    rotulo: str = ""
    cor: str = "#d4760a"
    grupo: str = ""


@dataclass(frozen=True)
class ApoioCena:
    ponto: Ponto
    tipo: str = APOIO_DESCONHECIDO
    rotulo: str = ""
    grupo: str = ""


@dataclass(frozen=True)
class TextoCena:
    ponto: Ponto
    texto: str
    cor: str = "#1f2328"


@dataclass(frozen=True)
class EscalaDeCor:
    minimo: float
    maximo: float
    unidade: str
    titulo: str
    paleta: tuple[str, ...] = PALETA_CARGA


@dataclass(frozen=True)
class Cena:
    barras: tuple[BarraCena, ...] = ()
    paineis: tuple[PainelCena, ...] = ()
    setas: tuple[SetaCena, ...] = ()
    distribuidas: tuple[CargaDistribuidaCena, ...] = ()
    apoios: tuple[ApoioCena, ...] = ()
    textos: tuple[TextoCena, ...] = ()
    titulo: str = ""
    subtitulo: str = ""
    legenda: tuple[tuple[str, str], ...] = ()  # (cor, texto)
    escala: EscalaDeCor | None = None
    eixo_vertical_do_modelo: str = "Y"  # para escrever os eixos como no SolidWorks
    avisos: tuple[str, ...] = ()


# ---------------------------------------------------------------------------------------------
# Desenho 2D (saída)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Poligono2D:
    pontos: tuple[Ponto2, ...]
    preenchimento: str
    contorno: str = COR_CONTORNO
    largura: float = 0.3
    opacidade: float = 1.0


@dataclass(frozen=True)
class Linha2D:
    a: Ponto2
    b: Ponto2
    cor: str
    largura: float = 1.0
    tracejado: str = ""
    opacidade: float = 1.0


@dataclass(frozen=True)
class Seta2D:
    a: Ponto2
    b: Ponto2
    cor: str
    largura: float = 2.0
    cabeca: float = 9.0
    larga: bool = False


@dataclass(frozen=True)
class Etiqueta2D:
    x: float
    y: float
    texto: str
    cor: str = "#1f2328"
    tamanho: float = 10.0
    peso: str = "normal"
    fundo: bool = True


@dataclass(frozen=True)
class Desenho2D:
    largura: float
    altura: float
    itens: tuple[Poligono2D | Linha2D | Seta2D | Etiqueta2D, ...]
    titulo: str = ""
    subtitulo: str = ""
    legenda: tuple[tuple[str, str], ...] = ()
    escala: EscalaDeCor | None = None
    eixos: tuple[tuple[str, Ponto2], ...] = ()  # (nome, direção na tela) para o triedro
    avisos: tuple[str, ...] = ()
    vazio: bool = False

    @property
    def poligonos(self) -> int:
        return sum(1 for i in self.itens if isinstance(i, Poligono2D))


# ---------------------------------------------------------------------------------------------
# Geometria das primitivas
# ---------------------------------------------------------------------------------------------
def _base_da_secao(u: Ponto, alma: Ponto | None) -> tuple[Ponto, Ponto]:
    """(t, s): s ao longo da alma (perpendicular ao eixo u), t = u × s."""
    candidatos = [alma] if alma is not None else []
    candidatos += [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for c in candidatos:
        if c is None or not _ponto_ok(c):
            continue
        s = _unitario(_sub(c, _escala(u, _dot(c, u))))
        if s is not None:
            return _cross(u, s), s
    return (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)


def _faces_da_barra(b: BarraCena, pedaco_maximo: float) -> list[tuple[list[Ponto], bool]]:
    """(face, é tampa) da barra extrudada, em pedaços; as faces de cada pedaço são fechadas."""
    eixo = _sub(b.fim, b.inicio)
    comprimento = _norma(eixo)
    u = _unitario(eixo)
    if u is None or b.secao is None:
        return []
    t, s = _base_da_secao(u, b.alma)
    contorno = b.secao.contorno()
    # Com o contorno no sentido horário em (t, s) (t × s = −u), as faces saem com a normal para fora.
    area = sum(
        p[0] * q[1] - q[0] * p[1]
        for p, q in zip(contorno, [*contorno[1:], contorno[0]], strict=True)
    )
    if area > 0:
        contorno = list(reversed(contorno))
    pedacos = max(
        1, min(PEDACOS_POR_BARRA_MAXIMO, math.ceil(comprimento / max(pedaco_maximo, 1e-3)))
    )
    faces: list[tuple[list[Ponto], bool]] = []
    for k in range(pedacos):
        a = _soma(b.inicio, _escala(u, comprimento * k / pedacos))
        c = _soma(b.inicio, _escala(u, comprimento * (k + 1) / pedacos))
        ini = [_soma(a, _soma(_escala(t, q[0]), _escala(s, q[1]))) for q in contorno]
        fim = [_soma(c, _soma(_escala(t, q[0]), _escala(s, q[1]))) for q in contorno]
        n = len(contorno)
        for i in range(n):
            j = (i + 1) % n
            faces.append(([ini[i], ini[j], fim[j], fim[i]], False))
        if k == 0:
            faces.append((list(reversed(ini)), True))
        if k == pedacos - 1:
            faces.append((fim, True))
    return faces


def _faces_do_apoio(a: ApoioCena, tamanho: float) -> list[list[Ponto]]:
    """O símbolo do apoio embaixo do ponto: pirâmide (articulado), placa (engastado), cubo (?)."""
    x, y, z = a.ponto
    h = tamanho
    if a.tipo == APOIO_ARTICULADO:
        base = [(x - h, y - h, z - 1.4 * h), (x + h, y - h, z - 1.4 * h),
                (x + h, y + h, z - 1.4 * h), (x - h, y + h, z - 1.4 * h)]  # fmt: skip
        topo = (x, y, z)
        return [[base[i], base[(i + 1) % 4], topo] for i in range(4)] + [list(reversed(base))]
    e = 0.35 * h if a.tipo == APOIO_ENGASTE else h
    lado = 1.4 * h if a.tipo == APOIO_ENGASTE else 0.8 * h
    cima = [
        (x - lado, y - lado, z),
        (x + lado, y - lado, z),
        (x + lado, y + lado, z),
        (x - lado, y + lado, z),
    ]
    baixo = [(p[0], p[1], z - e) for p in cima]
    faces = [list(reversed(baixo)), cima]
    for i in range(4):
        j = (i + 1) % 4
        faces.append([baixo[i], baixo[j], cima[j], cima[i]])
    return faces


# ---------------------------------------------------------------------------------------------
# Projeção
# ---------------------------------------------------------------------------------------------
def _limpar(cena: Cena) -> tuple[Cena, list[str]]:
    avisos: list[str] = list(cena.avisos)
    barras = []
    ruins = []
    for b in cena.barras:
        if _ponto_ok(b.inicio) and _ponto_ok(b.fim) and _norma(_sub(b.fim, b.inicio)) > 1e-6:
            alma = b.alma if _ponto_ok(b.alma) else None
            secao = b.secao
            if secao is not None and not finito(secao.d, secao.b, secao.tw, secao.tf):
                secao = Secao()
            barras.append(BarraCena(b.nome, b.inicio, b.fim, secao, alma, b.cor, b.rotulo,
                                    b.destaque, b.grupo))  # fmt: skip
        else:
            ruins.append(b.nome)
    if ruins:
        avisos.append(
            "Barras com coordenada inválida ou comprimento zero não aparecem: "
            + ", ".join(ruins[:6])
            + ("…" if len(ruins) > 6 else "")
            + "."
        )
    paineis = tuple(
        p for p in cena.paineis if len(p.pontos) >= 3 and all(_ponto_ok(q) for q in p.pontos)
    )
    if len(paineis) < len(cena.paineis):
        avisos.append(
            f"{len(cena.paineis) - len(paineis)} chapa(s) com contorno inválido não aparecem."
        )
    setas = tuple(s for s in cena.setas if _ponto_ok(s.ponto) and _ponto_ok(s.vetor))
    distribuidas = tuple(
        c
        for c in cena.distribuidas
        if _ponto_ok(c.inicio) and _ponto_ok(c.fim) and _ponto_ok(c.vetor_por_metro)
    )
    apoios = tuple(a for a in cena.apoios if _ponto_ok(a.ponto))
    textos = tuple(t for t in cena.textos if _ponto_ok(t.ponto))
    limpa = Cena(
        tuple(barras), paineis, setas, distribuidas, apoios, textos, cena.titulo, cena.subtitulo,
        cena.legenda, cena.escala, cena.eixo_vertical_do_modelo, tuple(avisos),
    )  # fmt: skip
    return limpa, avisos


def _pontos_da_cena(cena: Cena) -> list[Ponto]:
    pontos: list[Ponto] = []
    for b in cena.barras:
        pontos.extend((b.inicio, b.fim))
    for p in cena.paineis:
        pontos.extend(p.pontos)
    for a in cena.apoios:
        pontos.append(a.ponto)
    for c in cena.distribuidas:
        pontos.extend((c.inicio, c.fim))
    for s in cena.setas:
        pontos.append(s.ponto)
    return pontos


def eixos_do_modelo(eixo_vertical: str) -> tuple[tuple[str, Ponto], ...]:
    """Os eixos do SolidWorks na planta (para o triedro): com o Y para cima, Z do modelo = −Y."""
    if eixo_vertical == "Y":
        return (("X", (1.0, 0.0, 0.0)), ("Y", (0.0, 0.0, 1.0)), ("Z", (0.0, -1.0, 0.0)))
    return (("X", (1.0, 0.0, 0.0)), ("Y", (0.0, 1.0, 0.0)), ("Z", (0.0, 0.0, 1.0)))


def projetar(
    cena: Cena,
    *,
    azimute: float = VISTAS[VISTA_ISOMETRICA][0],
    elevacao: float = VISTAS[VISTA_ISOMETRICA][1],
    largura: float = 1100.0,
    altura: float = 720.0,
    perfil_real: bool = True,
    chao: bool = True,
    rotulos_maximos: int = 12,
) -> Desenho2D:
    """A cena vista do azimute e da elevação dados, pronta para desenhar."""
    cena, avisos = _limpar(cena)
    pontos = _pontos_da_cena(cena)
    area = (40.0, 80.0, largura - 40.0, altura - 64.0)
    if not pontos:
        return Desenho2D(
            largura,
            altura,
            (
                Etiqueta2D(
                    largura / 2,
                    altura / 2,
                    "Nada para desenhar: sem barras válidas na cena.",
                    COR_SUAVE,
                    13,
                    fundo=False,
                ),
            ),  # fmt: skip
            cena.titulo,
            cena.subtitulo,
            avisos=tuple(avisos),
            vazio=True,
        )
    camera = Camera(azimute, elevacao)
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    zs = [p[2] for p in pontos]
    tamanho = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.5)
    margem = 0.08 * tamanho
    z0 = min(zs)
    piso = [
        (min(xs) - margem, min(ys) - margem, z0),
        (max(xs) + margem, min(ys) - margem, z0),
        (max(xs) + margem, max(ys) + margem, z0),
        (min(xs) - margem, max(ys) + margem, z0),
    ]
    # Setas: comprimento de referência (a maior força) e as pontas, para o enquadramento.
    referencia = 0.16 * tamanho
    maior_forca = (
        max((_norma(s.vetor) for s in cena.setas if s.comprimento_relativo is None), default=0.0)
        or 1.0
    )
    maior_q = max((_norma(c.vetor_por_metro) for c in cena.distribuidas), default=0.0) or 1.0
    extras: list[Ponto] = []

    def comprimento_da_seta(s: SetaCena) -> float:
        if s.comprimento_relativo is not None:
            return s.comprimento_relativo * tamanho
        return referencia * (0.35 + 0.65 * _norma(s.vetor) / maior_forca)

    for s in cena.setas:
        direcao = _unitario(s.vetor)
        if direcao is None:
            continue
        comprimento = comprimento_da_seta(s)
        outra = _soma(s.ponto, _escala(direcao, comprimento if s.reacao else -comprimento))
        extras.append(outra)
    enquadrar = [camera.tela(p) for p in [*pontos, *extras, *(piso if chao else [])]]
    enq = Enquadramento(enquadrar, area)

    def t(p: Sequence[float]) -> Ponto2:
        return enq(camera.tela(p))

    itens: list[Poligono2D | Linha2D | Seta2D | Etiqueta2D] = []
    if chao:
        itens.append(Poligono2D(tuple(t(p) for p in piso), "#eef1f5", "#d5dae1", 0.8))
        passo = 10 ** math.floor(math.log10(max(tamanho / 8, 0.1)))
        if tamanho / passo > 30:
            passo *= 2
        for eixo in (0, 1):
            lo = piso[0][eixo]
            hi = piso[2][eixo]
            valor = math.ceil(lo / passo) * passo
            linhas = 0
            while valor <= hi and linhas < 80:
                if eixo == 0:
                    g0, g1 = (valor, piso[0][1], z0), (valor, piso[2][1], z0)
                else:
                    g0, g1 = (piso[0][0], valor, z0), (piso[2][0], valor, z0)
                itens.append(Linha2D(t(g0), t(g1), "#e1e5ea", 0.5))
                valor += passo
                linhas += 1
    luz = camera.luz()
    algum_destaque = any(b.destaque for b in cena.barras)
    faces: list[tuple[float, Poligono2D | Linha2D]] = []
    linhas_das_barras: list[tuple[float, Poligono2D | Linha2D]] = []
    pedaco = max(tamanho * PEDACO_MAXIMO_RELATIVO, 0.25)
    total_de_faces = sum(
        (len(b.secao.contorno()) + 2) * 3 if b.secao is not None else 0 for b in cena.barras
    )
    como_linhas = not perfil_real or total_de_faces > LIMITE_DE_FACES
    if perfil_real and total_de_faces > LIMITE_DE_FACES:
        avisos.append(
            f"Modelo grande ({len(cena.barras)} barras): as barras saem como linhas para o "
            "desenho não pesar."
        )
    for b in cena.barras:
        cor = b.cor
        opacidade = 1.0
        if algum_destaque and not b.destaque:
            cor = _hex([v + (235 - v) * 0.65 for v in _rgb(cor)])
        if como_linhas or b.secao is None:
            meio = _escala(_soma(b.inicio, b.fim), 0.5)
            espessura = 4.0 if b.destaque else 2.4
            linhas_das_barras.append(
                (camera.profundidade(meio), Linha2D(t(b.inicio), t(b.fim), cor, espessura))
            )
            continue
        for face, _tampa in _faces_da_barra(b, pedaco):
            normal = normal_da_face(face)
            if normal is None or _dot(normal, camera.olho) <= 1e-9:
                continue  # face de trás (sólido fechado)
            centro = _escala(_soma(_soma(face[0], face[1]), _soma(face[2], face[-1])), 0.25)
            preenchimento = sombrear(cor, _dot(normal, luz))
            # Contorno num tom mais escuro da própria face: o tubo fino não fica preto de linhas.
            contorno = "#ff2d55" if b.destaque else _hex([v * 0.72 for v in _rgb(preenchimento)])
            faces.append(
                (
                    camera.profundidade(centro),
                    Poligono2D(
                        tuple(t(q) for q in face),
                        preenchimento,
                        contorno,
                        0.9 if b.destaque else 0.35,
                        opacidade,
                    ),
                )
            )
    for p in cena.paineis:
        normal = normal_da_face(p.pontos)
        if normal is None:
            continue
        centro = _escala(
            (sum(q[0] for q in p.pontos), sum(q[1] for q in p.pontos), sum(q[2] for q in p.pontos)),
            1 / len(p.pontos),
        )
        faces.append(
            (
                camera.profundidade(centro),
                Poligono2D(
                    tuple(t(q) for q in p.pontos),
                    sombrear(p.cor, abs(_dot(normal, luz))),
                    "#7d8fa6",
                    0.4,
                    max(0.05, min(1.0, p.opacidade)),
                ),
            )
        )
    tamanho_do_apoio = 0.035 * tamanho
    for a in cena.apoios:
        cor = {"engastado": "#5d6b7a", "articulado": "#7a8a9a"}.get(a.tipo, "#9aa7b8")
        for face in _faces_do_apoio(a, tamanho_do_apoio):
            normal = normal_da_face(face)
            if normal is None or _dot(normal, camera.olho) <= 1e-9:
                continue
            centro = _escala(
                (sum(q[0] for q in face), sum(q[1] for q in face), sum(q[2] for q in face)),
                1 / len(face),
            )
            faces.append(
                (
                    camera.profundidade(centro),
                    Poligono2D(
                        tuple(t(q) for q in face),
                        sombrear(cor, _dot(normal, luz)),
                        COR_CONTORNO,
                        0.4,
                    ),  # fmt: skip
                )
            )
    itens.extend(f for _, f in sorted(faces + linhas_das_barras, key=lambda item: item[0]))
    rotulos = Rotulos((10.0, 60.0, largura - 10.0, altura - 40.0))
    # Cargas distribuídas: pente de setas ao longo da barra.
    for c in cena.distribuidas:
        direcao = _unitario(c.vetor_por_metro)
        if direcao is None:
            continue
        comprimento = 0.32 * referencia * (0.4 + 0.6 * _norma(c.vetor_por_metro) / maior_q)
        n = 5 if _norma(_sub(c.fim, c.inicio)) > 0.3 * tamanho else 3
        caudas = []
        for k in range(n):
            s_ = (k + 0.5) / n
            ponta = _soma(c.inicio, _escala(_sub(c.fim, c.inicio), s_))
            cauda = _soma(ponta, _escala(direcao, -comprimento))
            caudas.append(t(cauda))
            itens.append(Seta2D(t(cauda), t(ponta), c.cor, 1.4, 6.0))
        for cauda_a, cauda_b in zip(caudas, caudas[1:], strict=False):
            itens.append(Linha2D(cauda_a, cauda_b, c.cor, 1.1))
        if c.rotulo:
            x, y = caudas[len(caudas) // 2]
            itens.append(Etiqueta2D(*rotulos.lugar(x, y - 12, c.rotulo, 9.5), c.rotulo, c.cor, 9.5))
    # Setas concentradas e reações.
    for s in cena.setas:
        direcao = _unitario(s.vetor)
        if direcao is None:
            continue
        comprimento = comprimento_da_seta(s)
        if s.reacao:  # sai do apoio sem cobrir o símbolo
            cauda = _soma(s.ponto, _escala(direcao, 0.04 * tamanho))
            ponta = _soma(s.ponto, _escala(direcao, comprimento))
        else:
            cauda, ponta = _soma(s.ponto, _escala(direcao, -comprimento)), s.ponto
        itens.append(
            Seta2D(
                t(cauda),
                t(ponta),
                s.cor,
                2.6 if s.reacao else 2.2,
                11.0 if s.reacao else 9.0,
                s.larga,
            )  # fmt: skip
        )
        if s.rotulo:
            x, y = t(ponta if s.reacao else cauda)
            itens.append(
                Etiqueta2D(*rotulos.lugar(x, y - 12, s.rotulo, 10), s.rotulo, s.cor, 10, "bold")
            )
    for a in cena.apoios:
        if a.rotulo:
            x, y = t(a.ponto)
            itens.append(Etiqueta2D(*rotulos.lugar(x, y + 18, a.rotulo, 9), a.rotulo, COR_SUAVE, 9))
    # Rótulos das barras (os destacados primeiro).
    com_rotulo = sorted((b for b in cena.barras if b.rotulo), key=lambda b: not b.destaque)
    for b in com_rotulo[:rotulos_maximos]:
        x, y = t(_escala(_soma(b.inicio, b.fim), 0.5))
        lx, ly = rotulos.lugar(x, y - 16, b.rotulo, 10)
        if abs(ly - (y - 16)) > 1:
            itens.append(Linha2D((x, y), (lx, ly), COR_SUAVE, 0.7, opacidade=0.6))
        itens.append(Etiqueta2D(lx, ly, b.rotulo, "#c62828" if b.destaque else "#1f2328", 10,
                                "bold" if b.destaque else "normal"))  # fmt: skip
    for texto in cena.textos:
        x, y = t(texto.ponto)
        itens.append(Etiqueta2D(*rotulos.lugar(x, y, texto.texto, 10), texto.texto, texto.cor, 10))
    eixos = []
    for nome, vetor in eixos_do_modelo(cena.eixo_vertical_do_modelo):
        px, py = camera.tela(vetor)
        norma = math.hypot(px, py)
        if norma > 0.15:  # eixo que aponta para quem olha some
            eixos.append((nome, (px / norma, py / norma)))
    return Desenho2D(
        largura,
        altura,
        tuple(itens),
        cena.titulo,
        cena.subtitulo,
        cena.legenda,
        cena.escala,
        tuple(eixos),
        tuple(dict.fromkeys(avisos)),
    )


def contar(itens: Iterable[object], tipo: type) -> int:
    return sum(1 for i in itens if isinstance(i, tipo))


@dataclass(frozen=True)
class Opcoes:
    """Para as páginas guardarem a vista escolhida."""

    vista: str = VISTA_ISOMETRICA
    giro_graus: float = 0.0
    perfil_real: bool = True
    extras: dict[str, bool] = field(default_factory=dict)

    @property
    def azimute(self) -> float:
        return VISTAS.get(self.vista, VISTAS[VISTA_ISOMETRICA])[0] + self.giro_graus

    @property
    def elevacao(self) -> float:
        return VISTAS.get(self.vista, VISTAS[VISTA_ISOMETRICA])[1]


# ---------------------------------------------------------------------------------------------
# A cena gravada (registro do memorial)
# ---------------------------------------------------------------------------------------------
def _r(valor: float) -> float:
    return round(float(valor), 4)


def _p(p: Sequence[float] | None) -> list[float] | None:
    return None if p is None else [_r(v) for v in p]


def cena_para_dicionario(cena: Cena) -> dict[str, object]:
    """A cena em dicionário (JSON) para o registro: o memorial a desenha de novo."""

    def secao(s: Secao | None) -> list[object] | None:
        return None if s is None else [s.forma, _r(s.d), _r(s.b), _r(s.tw), _r(s.tf)]

    return {
        "barras": [
            [b.nome, _p(b.inicio), _p(b.fim), secao(b.secao), _p(b.alma), b.cor, b.rotulo,
             b.destaque, b.grupo]
            for b in cena.barras
        ],
        "paineis": [[p.nome, [_p(q) for q in p.pontos], p.cor, _r(p.opacidade), p.grupo]
                    for p in cena.paineis],
        "setas": [[_p(s.ponto), _p(s.vetor), s.rotulo, s.cor, s.reacao, s.grupo, s.larga,
                   s.comprimento_relativo] for s in cena.setas],
        "distribuidas": [[_p(c.inicio), _p(c.fim), _p(c.vetor_por_metro), c.rotulo, c.cor, c.grupo]
                         for c in cena.distribuidas],
        "apoios": [[_p(a.ponto), a.tipo, a.rotulo, a.grupo] for a in cena.apoios],
        "textos": [[_p(t.ponto), t.texto, t.cor] for t in cena.textos],
        "titulo": cena.titulo,
        "subtitulo": cena.subtitulo,
        "legenda": [list(item) for item in cena.legenda],
        "escala": None
        if cena.escala is None
        else [_r(cena.escala.minimo), _r(cena.escala.maximo), cena.escala.unidade,
              cena.escala.titulo, list(cena.escala.paleta)],
        "eixo_vertical": cena.eixo_vertical_do_modelo,
    }  # fmt: skip


def _ponto_lido(valor: object) -> Ponto | None:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        return None
    try:
        p = (float(valor[0]), float(valor[1]), float(valor[2]))
    except (TypeError, ValueError):
        return None
    return p if finito(*p) else None


def cena_de_dicionario(dados: object) -> Cena:
    """O inverso de :func:`cena_para_dicionario`; o que vier estragado fica de fora (não levanta)."""
    if not isinstance(dados, dict):
        return Cena()

    def lista(chave: str) -> list[Any]:
        valor = dados.get(chave)
        return list(valor) if isinstance(valor, (list, tuple)) else []

    barras = []
    for item in lista("barras"):
        try:
            nome, ini, fim, sec, alma, cor, rotulo, destaque, grupo = item
            a, b = _ponto_lido(ini), _ponto_lido(fim)
            if a is None or b is None:
                continue
            secao = None
            if isinstance(sec, (list, tuple)) and len(sec) == 5:
                secao = Secao(
                    str(sec[0]), float(sec[1]), float(sec[2]), float(sec[3]), float(sec[4])
                )
            barras.append(BarraCena(str(nome), a, b, secao, _ponto_lido(alma), str(cor),
                                    str(rotulo), bool(destaque), str(grupo)))  # fmt: skip
        except (TypeError, ValueError):
            continue
    paineis = []
    for item in lista("paineis"):
        try:
            nome, pontos, cor, opacidade, grupo = item
            lidos = [q for q in (_ponto_lido(q) for q in pontos) if q is not None]
            if len(lidos) >= 3 and len(lidos) == len(pontos):
                paineis.append(PainelCena(str(nome), tuple(lidos), str(cor), float(opacidade),
                                          str(grupo)))  # fmt: skip
        except (TypeError, ValueError):
            continue
    setas = []
    for item in lista("setas"):
        try:
            ponto, vetor, rotulo, cor, reacao, grupo, larga, relativo = item
            p, v = _ponto_lido(ponto), _ponto_lido(vetor)
            if p is not None and v is not None:
                setas.append(SetaCena(p, v, str(rotulo), str(cor), bool(reacao), str(grupo),
                                      bool(larga), None if relativo is None else float(relativo)))  # fmt: skip
        except (TypeError, ValueError):
            continue
    distribuidas = []
    for item in lista("distribuidas"):
        try:
            ini, fim, vetor, rotulo, cor, grupo = item
            a, b, v = _ponto_lido(ini), _ponto_lido(fim), _ponto_lido(vetor)
            if a is not None and b is not None and v is not None:
                distribuidas.append(
                    CargaDistribuidaCena(a, b, v, str(rotulo), str(cor), str(grupo))
                )
        except (TypeError, ValueError):
            continue
    apoios = []
    for item in lista("apoios"):
        try:
            ponto, tipo, rotulo, grupo = item
            p = _ponto_lido(ponto)
            if p is not None:
                apoios.append(ApoioCena(p, str(tipo), str(rotulo), str(grupo)))
        except (TypeError, ValueError):
            continue
    textos = []
    for item in lista("textos"):
        try:
            ponto, texto, cor = item
            p = _ponto_lido(ponto)
            if p is not None:
                textos.append(TextoCena(p, str(texto), str(cor)))
        except (TypeError, ValueError):
            continue
    escala = None
    bruto = dados.get("escala")
    if isinstance(bruto, (list, tuple)) and len(bruto) == 5:
        try:
            escala = EscalaDeCor(float(bruto[0]), float(bruto[1]), str(bruto[2]), str(bruto[3]),
                                 tuple(str(c) for c in bruto[4]) or PALETA_CARGA)  # fmt: skip
        except (TypeError, ValueError):
            escala = None
    legenda = tuple(
        (str(item[0]), str(item[1]))
        for item in lista("legenda")
        if isinstance(item, (list, tuple)) and len(item) == 2
    )
    return Cena(
        tuple(barras), tuple(paineis), tuple(setas), tuple(distribuidas), tuple(apoios),
        tuple(textos), str(dados.get("titulo") or ""), str(dados.get("subtitulo") or ""),
        legenda, escala, str(dados.get("eixo_vertical") or "Y"),
    )  # fmt: skip
