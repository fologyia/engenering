"""Nomes das barras: o nome de cada peça do modelo no padrão que o programa entende.

A página Nomes das barras lê o esqueleto do SolidWorks e sugere, para cada corpo, o papel e um nome
no padrão de :mod:`core.papel_pelo_nome`:

* a **grade** sai dos pilares: as posições em planta viram eixos — números da esquerda para a
  direita, letras de baixo para cima, como na vista Superior do SolidWorks (sem I e O, que se
  confundem com 1 e 0);
* os **níveis** saem das vigas deitadas e das chapas de piso: N0 é o pé da estrutura, N1, N2…
  para cima;
* o **papel** é o que o programa já entende do modelo (pilar, viga, contraventamento, longarina,
  chapa de piso, patamar, lance de escada) mais duas leituras próprias: a mão-francesa (escora
  inclinada entre o fuste de um pilar e o vão de uma viga) e o degrau (barra deitada entre duas
  longarinas, encostada no vão delas — a viga do patamar, que liga as pontas, continua viga).
  O nome atual que já diz o papel, sem contradizer a geometria, vale;
* o **nome**: ``P-A1`` (o pilar do cruzamento A1; ``P-A1-N1`` quando o pilar tem um trecho por
  nível), ``V-N1-A1-A2`` (barra cujas pontas caem em cruzamentos da grade), ``V-N1-07`` (as outras,
  numeradas na ordem da planta) e ``PS-N1-01`` (chapas).

Nome que já está no padrão e confere com a geometria fica como está: rodar de novo depois de mexer
no modelo não troca o nome do que não mudou.

O arquivo para a macro (:func:`arquivo_para_a_macro`) leva, de cada corpo que muda de nome, o nome
atual, o novo e onde o corpo está (pontas e volume): a macro ``renomear_corpos.bas`` confere a
geometria antes de trocar e, se o nome atual não existe mais, acha o corpo pela geometria. O
relatório da macro (``…_nomes_aplicados.csv``, :func:`ler_relatorio_da_macro`) confirma as trocas no
projeto, e o plano de cargas pode passar para os nomes novos (:func:`plano_com_os_nomes_novos`).

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from core import cantoneiras as ct
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import papel_pelo_nome as pn
from core import piso_do_modelo as pm
from core import plano_de_cargas as pc
from core import section_catalog as sc

TOLERANCIA_DA_GRADE_M = 0.20  # posições de pilar mais perto que isso são o mesmo eixo
TOLERANCIA_DO_CRUZAMENTO_M = 0.35  # a ponta da barra cai no cruzamento se estiver a até isso
TOLERANCIA_DO_NIVEL_M = pm.TOLERANCIA_DO_NIVEL_M
ANGULO_DEITADA = pn.ANGULO_INCLINADA  # graus: até aqui a barra está em nível
#: As letras dos eixos: sem I e O, que se confundem com 1 e 0.
LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
#: A mão-francesa: escora inclinada curta, do fuste do pilar ao vão da viga.
MAO_FRANCESA_ANGULO = (15.0, 75.0)
MAO_FRANCESA_COMPRIMENTO_M = 3.0
LONGE_DA_PONTA_M = 0.30  # a ligação no "fuste" ou no "vão" fica a mais que isso das pontas
DEGRAU_COMPRIMENTO_M = 2.0
VERSAO_DO_ARQUIVO = "v1"
MACRO = Path(__file__).resolve().parent.parent / "macros_solidworks" / "renomear_corpos.bas"
ARQUIVO_DA_MACRO = "renomear_corpos.bas"
#: As colunas das linhas de corpo e de perfil no arquivo para a macro (a macro lê nesta ordem).
COLUNAS_DOS_CORPOS = (
    "CORPOS",
    "ATUAL",
    "NOVO",
    "PAPEL",
    "FORMA",
    "X1 (mm)",
    "Y1 (mm)",
    "Z1 (mm)",
    "X2 (mm)",
    "Y2 (mm)",
    "Z2 (mm)",
    "COMPRIMENTO (mm)",
    "VOLUME (cm3)",
)
COLUNAS_DOS_PERFIS = ("PERFIS", "ITEM", "PERFIL", "CORPO DO ITEM")
LIMITE_DO_HISTORICO = 3000  # trocas guardadas no projeto (as mais recentes)


def macro_de_renomear() -> bytes:
    """O texto da macro ``renomear_corpos.bas``: ASCII com CRLF, para colar no editor do VBA."""
    texto = MACRO.read_text(encoding="ascii")
    return texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------------------------
# Planta, níveis e grade
# ---------------------------------------------------------------------------------------------
Ponto3 = tuple[float, float, float]


def planta(ponto: Sequence[float], eixo_vertical: str) -> tuple[float, float]:
    """O ponto na planta (vista Superior): com o Y vertical do SolidWorks, (X, −Z); com Z, (X, Y).
    É a mesma planta de ``core.vento_por_barras.para_a_planta``."""
    x, y, z = (float(v) for v in ponto)
    return (x + 0.0, -z + 0.0) if eixo_vertical == "Y" else (x + 0.0, y + 0.0)


def altura(ponto: Sequence[float], eixo_vertical: str) -> float:
    return float(ponto[1] if eixo_vertical == "Y" else ponto[2])


def _agrupar(valores: Iterable[float], tolerancia: float) -> list[float]:
    """Os valores em grupos (vizinhos a até ``tolerancia``): a média de cada grupo, em ordem."""
    grupos: list[list[float]] = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [sum(g) / len(g) for g in grupos]


def letra_do_eixo(indice: int) -> str:
    """0 → A, 23 → Z (sem I e O), 24 → AA, 25 → AB…"""
    base = len(LETRAS)
    if indice < base:
        return LETRAS[indice]
    return letra_do_eixo(indice // base - 1) + LETRAS[indice % base]


def _mais_perto(eixos: Sequence[tuple[str, float]], valor: float, tolerancia: float) -> str | None:
    if not eixos:
        return None
    rotulo, coordenada = min(eixos, key=lambda e: abs(e[1] - valor))
    return rotulo if abs(coordenada - valor) <= tolerancia else None


@dataclass(frozen=True)
class Grade:
    """Os eixos da planta (pelos pilares) e os níveis (pelas vigas e chapas de piso)."""

    eixo_vertical: str
    numeros: tuple[tuple[str, float], ...] = ()  # x constante na planta, da esquerda à direita
    letras: tuple[tuple[str, float], ...] = ()  # y constante na planta, de baixo para cima
    chao: float = 0.0  # a altura do ponto mais baixo do modelo (m, no eixo vertical)
    niveis: tuple[float, ...] = ()  # N1, N2…: m acima do chão (N0 é o chão)

    def nivel(self, altura_m: float) -> int:
        """O nível mais perto da altura (no eixo vertical do modelo): 0 é o chão."""
        todas = (0.0, *self.niveis)
        cota = altura_m - self.chao
        return min(range(len(todas)), key=lambda i: abs(todas[i] - cota))

    def cota(self, nivel: int) -> float:
        return 0.0 if nivel <= 0 or nivel > len(self.niveis) else self.niveis[nivel - 1]

    def cruzamento(self, x: float, y: float) -> str | None:
        """O cruzamento da grade nesse ponto da planta ("A1"), se ele cai num."""
        numero = _mais_perto(self.numeros, x, TOLERANCIA_DO_CRUZAMENTO_M)
        letra = _mais_perto(self.letras, y, TOLERANCIA_DO_CRUZAMENTO_M)
        return f"{letra}{numero}" if numero and letra else None

    def ordem(self, cruzamento: str) -> tuple[int, int]:
        """Para ordenar cruzamentos: pela letra, depois pelo número."""
        letras = [r for r, _ in self.letras]
        numeros = [r for r, _ in self.numeros]
        letra = cruzamento.rstrip("0123456789")
        numero = cruzamento[len(letra) :]
        return (
            letras.index(letra) if letra in letras else len(letras),
            numeros.index(numero) if numero in numeros else len(numeros),
        )

    @property
    def tem_eixos(self) -> bool:
        return bool(self.numeros and self.letras)


# ---------------------------------------------------------------------------------------------
# O papel de cada corpo
# ---------------------------------------------------------------------------------------------
_DO_PISO: dict[str, pn.Papel] = {
    ld.TIPO_PILAR: pn.PILAR,
    ld.TIPO_VIGA: pn.VIGA,
    ld.TIPO_CONTRAVENTAMENTO: pn.CONTRAVENTAMENTO,
    pm.PAPEL_LONGARINA: pn.LONGARINA,
    pm.PAPEL_PECA_CURTA: pn.PECA,
    pn.TIPO_OUTRO: pn.GUARDA_CORPO,
}
_CHAPA_DO_PISO: dict[str, pn.Papel] = {
    pm.TIPO_PISO: pn.PISO,
    pm.TIPO_PATAMAR: pn.PATAMAR,
    pm.TIPO_ESCADA: pn.LANCE,
    pm.TIPO_SEM_CARGA: pn.CHAPA,
}
ESCOLHIDO = "escolhido na tabela"


@dataclass(frozen=True)
class PapelSugerido:
    papel: pn.Papel
    motivo: str
    #: O nome atual já dizia esse papel (e a geometria deixou).
    pelo_nome: bool = False
    #: O nome atual diz outro papel, que a geometria contradiz.
    nota: str = ""


def _distancia(p: Sequence[float], a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """(distância do ponto ao segmento ab, parâmetro t do ponto mais perto, de 0 a 1)."""
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    l2 = sum(v * v for v in ab)
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / l2))
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)]), t


def _no_meio(p: Sequence[float], corpo: ld.CorpoDoModelo) -> bool:
    """O ponto encosta na barra longe das pontas dela (no fuste do pilar, no vão da viga)?"""
    distancia, t = _distancia(p, corpo.inicio, corpo.fim)
    folga = LONGE_DA_PONTA_M / corpo.comprimento_m if corpo.comprimento_m > 0 else 1.0
    return distancia <= ld.TOLERANCIA_LIGACAO_M and folga < t < 1 - folga


def _encosta(p: Sequence[float], corpo: ld.CorpoDoModelo) -> bool:
    return _distancia(p, corpo.inicio, corpo.fim)[0] <= ld.TOLERANCIA_LIGACAO_M


def _angulo(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> float:
    comprimento = math.dist(corpo.inicio, corpo.fim)
    if comprimento <= 0:
        return 0.0
    subida = abs(altura(corpo.fim, eixo_vertical) - altura(corpo.inicio, eixo_vertical))
    return math.degrees(math.asin(min(1.0, subida / comprimento)))


def _pontas_por_altura(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> tuple[Ponto3, Ponto3]:
    """(a ponta de baixo, a de cima); na barra deitada, a de início primeiro."""
    if altura(corpo.fim, eixo_vertical) < altura(corpo.inicio, eixo_vertical) - 1e-6:
        return corpo.fim, corpo.inicio
    return corpo.inicio, corpo.fim


def _e_mao_francesa(
    corpo: ld.CorpoDoModelo,
    eixo_vertical: str,
    pilares: Sequence[ld.CorpoDoModelo],
    vigas: Sequence[ld.CorpoDoModelo],
) -> bool:
    angulo = _angulo(corpo, eixo_vertical)
    if not (MAO_FRANCESA_ANGULO[0] <= angulo <= MAO_FRANCESA_ANGULO[1]):
        return False
    if corpo.comprimento_m > MAO_FRANCESA_COMPRIMENTO_M:
        return False
    baixa, alta = _pontas_por_altura(corpo, eixo_vertical)
    return any(_no_meio(baixa, p) for p in pilares) and any(_no_meio(alta, v) for v in vigas)


def _e_degrau(
    corpo: ld.CorpoDoModelo, eixo_vertical: str, longarinas: Sequence[ld.CorpoDoModelo]
) -> bool:
    if _angulo(corpo, eixo_vertical) > ANGULO_DEITADA:
        return False
    if corpo.comprimento_m > DEGRAU_COMPRIMENTO_M:
        return False
    # No vão das longarinas: a barra que liga as pontas delas é a viga do patamar, não degrau.
    numa = [lg.nome for lg in longarinas if _no_meio(corpo.inicio, lg)]
    noutra = [lg.nome for lg in longarinas if _no_meio(corpo.fim, lg)]
    return any(a != b for a in numa for b in noutra)


def inclinacao_da_chapa(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> float | None:
    """Graus do plano da chapa com a horizontal, pelo contorno (normal de Newell); ``None`` sem
    o contorno (macro antiga) ou com ele degenerado."""
    pontos = corpo.contorno
    if len(pontos) < 3:
        return None
    nx = ny = nz = 0.0
    for i, p in enumerate(pontos):
        q = pontos[(i + 1) % len(pontos)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    norma = math.sqrt(nx * nx + ny * ny + nz * nz)
    if norma < 1e-12:
        return None
    vertical = ny if eixo_vertical == "Y" else nz
    return math.degrees(math.acos(min(1.0, abs(vertical) / norma)))


def _declarado(
    corpo: ld.CorpoDoModelo, eixo_vertical: str, inclinacao: float | None
) -> ld.PapelDeclarado | None:
    if corpo.forma == ld.FORMA_CHAPA:
        lido = pn.papel_do_nome(corpo.nome)
        if lido is None:
            return None
        if inclinacao is None:
            inclinacao = inclinacao_da_chapa(corpo, eixo_vertical)
        return ld.PapelDeclarado(lido, pn.avaliar(lido.papel, inclinacao, corpo.forma))
    return ld.papel_declarado(corpo, eixo_vertical)


def papeis_sugeridos(
    g: ld.GeometriaDoModelo, eixo_vertical: str, escolhidos: Mapping[str, str] | None = None
) -> dict[str, PapelSugerido]:
    """O papel de cada corpo: o escolhido na tabela (``escolhidos``: corpo → prefixo); senão o que o
    nome atual diz, quando a geometria deixa; senão o que o programa entende do modelo."""
    leitura = pm.ler(g, eixo_vertical)
    papel_do_piso = leitura.papel
    chapas = {c.nome: c for c in leitura.chapas}
    fora = {f.nome: f.motivo for f in leitura.fora}
    escolhas = escolhidos or {}
    sugeridos: dict[str, PapelSugerido] = {}
    pendentes: list[ld.CorpoDoModelo] = []
    for corpo in g.corpos:
        prefixo = escolhas.get(corpo.nome, "")
        if prefixo in pn.POR_PREFIXO:
            sugeridos[corpo.nome] = PapelSugerido(pn.POR_PREFIXO[prefixo], ESCOLHIDO)
            continue
        chapa = chapas.get(corpo.nome)
        declarado = _declarado(corpo, eixo_vertical, chapa.inclinacao_graus if chapa else None)
        nota = declarado.contradicao if declarado is not None else ""
        if declarado is not None and declarado.vale:
            sugeridos[corpo.nome] = PapelSugerido(
                declarado.papel, f"pelo nome atual ({declarado.lido.como})", True
            )
            continue
        if corpo.forma == ld.FORMA_CHAPA:
            if chapa is not None and not chapa.vigas:
                papel = pn.CHAPA
                motivo = "nenhuma viga logo abaixo: chapa de base, de ligação ou enrijecedor"
            elif chapa is not None:
                papel = _CHAPA_DO_PISO.get(chapa.tipo, pn.PISO)
                motivo = chapa.motivo
            else:
                papel = pn.CHAPA
                inclinacao = inclinacao_da_chapa(corpo, eixo_vertical)
                if corpo.nome in fora:
                    motivo = fora[corpo.nome]
                elif inclinacao is not None and inclinacao > pn.ANGULO_PISO_MAXIMO:
                    motivo = "chapa em pé (ligação, nervura, enrijecedor)"
                else:
                    motivo = "chapa pequena ou fora do piso (base, ligação, enrijecedor)"
            sugeridos[corpo.nome] = PapelSugerido(papel, motivo, nota=nota)
            continue
        if corpo.forma == ld.FORMA_BLOCO:
            sugeridos[corpo.nome] = PapelSugerido(
                pn.PECA, "peça curta (toco, calço): a posição não diz o papel", nota=nota
            )
            continue
        papel_lido = papel_do_piso.get(corpo.nome, "")
        papel = _DO_PISO.get(papel_lido, pn.VIGA)
        motivo = ld.tipo_pela_posicao(corpo, eixo_vertical)[1]
        if papel is pn.LONGARINA:
            motivo = "inclinada, sob o lance da escada"
        sugeridos[corpo.nome] = PapelSugerido(papel, motivo, nota=nota)
        pendentes.append(corpo)
    # Leituras próprias: mão-francesa e degrau (só onde nem a tabela nem o nome disseram).
    por_papel: dict[pn.Papel, list[ld.CorpoDoModelo]] = {}
    for corpo in g.corpos:
        por_papel.setdefault(sugeridos[corpo.nome].papel, []).append(corpo)
    pilares = por_papel.get(pn.PILAR, [])
    vigas = por_papel.get(pn.VIGA, [])
    longarinas = por_papel.get(pn.LONGARINA, [])
    for corpo in pendentes:
        atual = sugeridos[corpo.nome]
        if atual.papel is pn.CONTRAVENTAMENTO and _e_mao_francesa(
            corpo, eixo_vertical, pilares, vigas
        ):
            sugeridos[corpo.nome] = replace(
                atual,
                papel=pn.MAO_FRANCESA,
                motivo="escora inclinada do fuste de um pilar ao vão de uma viga",
            )
        elif atual.papel is pn.VIGA and _e_degrau(corpo, eixo_vertical, longarinas):
            sugeridos[corpo.nome] = replace(
                atual, papel=pn.DEGRAU, motivo="deitada, no vão de duas longarinas de escada"
            )
    return sugeridos


def grade_do_modelo(
    g: ld.GeometriaDoModelo, eixo_vertical: str, papeis: Mapping[str, PapelSugerido]
) -> Grade:
    """Os eixos pelos pés dos pilares e os níveis pelas vigas deitadas e chapas de piso."""
    alturas = [altura(p, eixo_vertical) for c in g.corpos for p in (c.inicio, c.fim)]
    alturas += [altura(p, eixo_vertical) for c in g.corpos for p in c.contorno]
    chao = min(alturas, default=0.0)
    pes = [
        planta(_pontas_por_altura(c, eixo_vertical)[0], eixo_vertical)
        for c in g.corpos
        if (s := papeis.get(c.nome)) is not None and s.papel is pn.PILAR
    ]
    xs = _agrupar((p[0] for p in pes), TOLERANCIA_DA_GRADE_M)
    ys = _agrupar((p[1] for p in pes), TOLERANCIA_DA_GRADE_M)
    cotas: list[float] = []
    for c in g.corpos:
        s = papeis.get(c.nome)
        if s is None:
            continue
        if s.papel in (pn.VIGA, pn.DEGRAU) and _angulo(c, eixo_vertical) <= ANGULO_DEITADA:
            meio = (altura(c.inicio, eixo_vertical) + altura(c.fim, eixo_vertical)) / 2
            cotas.append(meio - chao)
        elif s.papel in (pn.PISO, pn.PATAMAR) and c.contorno:
            cotas.append(sum(altura(p, eixo_vertical) for p in c.contorno) / len(c.contorno) - chao)
    niveis = [n for n in _agrupar(cotas, TOLERANCIA_DO_NIVEL_M) if n > TOLERANCIA_DO_NIVEL_M]
    return Grade(
        eixo_vertical,
        tuple((str(i + 1), x) for i, x in enumerate(xs)),
        tuple((letra_do_eixo(i), y) for i, y in enumerate(ys)),
        chao,
        tuple(niveis),
    )


# ---------------------------------------------------------------------------------------------
# Os nomes
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Sugestao:
    corpo: str  # o nome atual no SolidWorks
    forma: str
    papel: pn.Papel
    motivo: str
    nome: str  # o nome novo (igual ao atual quando fica)
    onde: str
    nivel: int
    #: De onde veio o nome: "gerado", "mantido" (já estava no padrão), "à mão", "sem troca".
    origem_do_nome: str
    nota: str
    comprimento_m: float
    angulo_graus: float | None

    @property
    def muda(self) -> bool:
        return self.nome != self.corpo


@dataclass(frozen=True)
class PlanoDeNomes:
    grade: Grade
    sugestoes: tuple[Sugestao, ...]
    avisos: tuple[str, ...] = ()

    def da(self, corpo: str) -> Sugestao | None:
        return next((s for s in self.sugestoes if s.corpo == corpo), None)

    @property
    def trocas(self) -> dict[str, str]:
        """Corpo atual → nome novo, só dos que mudam."""
        return {s.corpo: s.nome for s in self.sugestoes if s.muda}

    @property
    def no_padrao(self) -> int:
        """Quantos corpos já têm hoje um nome que diz o papel (prefixo ou palavra)."""
        return sum(1 for s in self.sugestoes if pn.papel_do_nome(s.corpo) is not None)


GERADO, MANTIDO, A_MAO, SEM_TROCA = "gerado", "mantido", "à mão", "sem troca"


def _onde(
    corpo: ld.CorpoDoModelo, s: PapelSugerido, grade: Grade, nivel: int, eixo_vertical: str
) -> str:
    cota = f"N{nivel} (+{_n(grade.cota(nivel))} m)"
    if corpo.forma == ld.FORMA_CHAPA or s.papel.forma == pn.FORMA_CHAPA:
        return cota
    baixa, alta = _pontas_por_altura(corpo, eixo_vertical)
    a = grade.cruzamento(*planta(baixa, eixo_vertical))
    b = grade.cruzamento(*planta(alta, eixo_vertical))
    if s.papel is pn.PILAR:
        topo = grade.nivel(altura(alta, eixo_vertical))
        return f"cruzamento {a or '—'}, do N{nivel} ao N{topo}"
    if a and b and a != b:
        if _angulo(corpo, eixo_vertical) <= ANGULO_DEITADA:
            a, b = sorted((a, b), key=grade.ordem)
        return f"{cota}, de {a} a {b}"
    if a or b:
        return f"{cota}, ponta em {a or b}"
    return cota


def _nome_mantido(corpo: ld.CorpoDoModelo, papel: pn.Papel) -> bool:
    """O nome atual já está no padrão, limpo, e diz o mesmo papel: fica."""
    lido = pn.papel_do_nome(corpo.nome)
    return (
        lido is not None
        and lido.pelo_codigo
        and lido.papel is papel
        and pn.problema_do_nome(corpo.nome) == ""
    )


def _livre(base: str, usados: set[str]) -> str:
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def sugerir(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    *,
    escolhidos: Mapping[str, str] | None = None,
    a_mao: Mapping[str, str] | None = None,
    sem_troca: Iterable[str] = (),
    refazer: bool = False,
) -> PlanoDeNomes:
    """O papel e o nome de cada corpo do esqueleto.

    ``escolhidos`` (corpo → prefixo) troca o papel; ``a_mao`` (corpo → nome) dá o nome direto
    (conferido por :func:`conferir`); ``sem_troca`` são os corpos que ficam com o nome atual.
    ``refazer`` gera de novo também os nomes que já estão no padrão (a grade mudou, por exemplo).
    """
    papeis = papeis_sugeridos(g, eixo_vertical, escolhidos)
    grade = grade_do_modelo(g, eixo_vertical, papeis)
    fixos = set(sem_troca)
    mao = {k: str(v).strip() for k, v in (a_mao or {}).items() if str(v).strip()}
    nomes: dict[str, tuple[str, str]] = {}  # corpo → (nome, origem)
    for corpo in g.corpos:
        papel = papeis[corpo.nome].papel
        if corpo.nome in fixos:
            nomes[corpo.nome] = (corpo.nome, SEM_TROCA)
        elif corpo.nome in mao:
            nomes[corpo.nome] = (mao[corpo.nome], A_MAO)
        elif not refazer and _nome_mantido(corpo, papel):
            nomes[corpo.nome] = (corpo.nome, MANTIDO)
    usados = {nome for nome, _ in nomes.values()}
    niveis: dict[str, int] = {}
    for corpo in g.corpos:
        baixa, alta = _pontas_por_altura(corpo, eixo_vertical)
        if corpo.forma == ld.FORMA_CHAPA and corpo.contorno:
            alturas_da_chapa = [altura(p, eixo_vertical) for p in corpo.contorno]
            inclinacao = inclinacao_da_chapa(corpo, eixo_vertical)
            if inclinacao is not None and inclinacao > ANGULO_DEITADA:
                # O lance de escada é do nível onde ele começa (o ponto mais baixo).
                niveis[corpo.nome] = grade.nivel(min(alturas_da_chapa))
            else:
                niveis[corpo.nome] = grade.nivel(sum(alturas_da_chapa) / len(alturas_da_chapa))
        elif papeis[corpo.nome].papel is pn.PILAR or _angulo(corpo, eixo_vertical) > ANGULO_DEITADA:
            niveis[corpo.nome] = grade.nivel(altura(baixa, eixo_vertical))
        else:
            meio = (altura(baixa, eixo_vertical) + altura(alta, eixo_vertical)) / 2
            niveis[corpo.nome] = grade.nivel(meio)

    def ordem_na_planta(corpo: ld.CorpoDoModelo) -> tuple[float, float, str]:
        meio = [(a + b) / 2 for a, b in zip(corpo.inicio, corpo.fim, strict=True)]
        x, y = planta(meio, eixo_vertical)
        return (round(y, 2), round(x, 2), corpo.nome)

    # Pilares: pelo cruzamento do pé; um por cruzamento, ou um por nível de pé.
    pilares = [c for c in g.corpos if c.nome not in nomes and papeis[c.nome].papel is pn.PILAR]
    por_cruzamento: dict[str, list[ld.CorpoDoModelo]] = {}
    for c in sorted(pilares, key=ordem_na_planta):
        rotulo = grade.cruzamento(*planta(_pontas_por_altura(c, eixo_vertical)[0], eixo_vertical))
        if rotulo:  # sem cruzamento (sem grade), o pilar sai numerado com as outras barras
            por_cruzamento.setdefault(rotulo, []).append(c)
    for rotulo in sorted(por_cruzamento, key=grade.ordem):
        grupo = sorted(
            por_cruzamento[rotulo],
            key=lambda c: (altura(_pontas_por_altura(c, eixo_vertical)[0], eixo_vertical), c.nome),
        )
        for c in grupo:
            base = f"P-{rotulo}" if len(grupo) == 1 else f"P-{rotulo}-N{niveis[c.nome]}"
            nome = _livre(base, usados)
            usados.add(nome)
            nomes[c.nome] = (nome, GERADO)
    # As outras barras: pelos cruzamentos das pontas; senão numeradas na ordem da planta.
    numerar: dict[tuple[str, int], list[ld.CorpoDoModelo]] = {}
    for c in sorted(g.corpos, key=ordem_na_planta):
        if c.nome in nomes:
            continue
        papel = papeis[c.nome].papel
        if c.forma != ld.FORMA_CHAPA and papel.forma != pn.FORMA_CHAPA and papel is not pn.PECA:
            baixa, alta = _pontas_por_altura(c, eixo_vertical)
            a = grade.cruzamento(*planta(baixa, eixo_vertical))
            b = grade.cruzamento(*planta(alta, eixo_vertical))
            if papel is not pn.PILAR and a and b and a != b:
                if _angulo(c, eixo_vertical) <= ANGULO_DEITADA:
                    a, b = sorted((a, b), key=grade.ordem)
                nome = _livre(f"{papel.prefixo}-N{niveis[c.nome]}-{a}-{b}", usados)
                usados.add(nome)
                nomes[c.nome] = (nome, GERADO)
                continue
        numerar.setdefault((papel.prefixo, niveis[c.nome]), []).append(c)
    for (prefixo, nivel), grupo in sorted(numerar.items()):
        sequencia = 0
        for c in grupo:  # já na ordem da planta
            while True:
                sequencia += 1
                nome = (
                    f"{prefixo}-{sequencia:02d}"
                    if prefixo == "P"
                    else (f"{prefixo}-N{nivel}-{sequencia:02d}")
                )
                if nome not in usados:
                    break
            usados.add(nome)
            nomes[c.nome] = (nome, GERADO)
    sugestoes = []
    for corpo in g.corpos:
        s = papeis[corpo.nome]
        nome, origem = nomes[corpo.nome]
        if corpo.forma == ld.FORMA_CHAPA:
            angulo = inclinacao_da_chapa(corpo, eixo_vertical)
        elif corpo.forma == ld.FORMA_BLOCO:
            angulo = None  # na peça curta a medida maior pode ser a da seção
        else:
            angulo = _angulo(corpo, eixo_vertical)
        sugestoes.append(
            Sugestao(
                corpo=corpo.nome,
                forma=corpo.forma,
                papel=s.papel,
                motivo=s.motivo,
                nome=nome,
                onde=_onde(corpo, s, grade, niveis[corpo.nome], eixo_vertical),
                nivel=niveis[corpo.nome],
                origem_do_nome=origem,
                nota=s.nota,
                comprimento_m=corpo.comprimento_m,
                angulo_graus=angulo,
            )
        )
    avisos: list[str] = []
    if not grade.tem_eixos:
        avisos.append(
            "Sem pilares no esqueleto: a grade de eixos não foi montada e os nomes saem numerados "
            "na ordem da planta. Marque os pilares na tabela (papel P) para os nomes dizerem o "
            "cruzamento de cada um."
        )
    if not grade.niveis:
        avisos.append(
            "Nenhum nível de piso achado (vigas deitadas ou chapas de piso): todas as barras ficam "
            "no N0."
        )
    return PlanoDeNomes(grade, tuple(sugestoes), tuple(avisos))


def conferir(plano: PlanoDeNomes, g: ld.GeometriaDoModelo) -> list[str]:
    """O que impede de levar os nomes ao SolidWorks: nome fora do padrão, prefixo que não é o do
    papel escolhido, dois corpos com o mesmo nome."""
    problemas: list[str] = []
    contagem = Counter(s.nome for s in plano.sugestoes)
    for s in plano.sugestoes:
        if s.origem_do_nome == SEM_TROCA:
            continue
        problema = pn.problema_do_nome(s.nome)
        if problema:
            problemas.append(f"{s.corpo} → “{s.nome}”: {problema}.")
            continue
        lido = pn.papel_do_nome(s.nome)
        if lido is not None and lido.papel is not s.papel:
            problemas.append(
                f"{s.corpo} → “{s.nome}”: o nome começa com {lido.papel.prefixo} "
                f"({lido.papel.nome.lower()}), mas o papel escolhido é {s.papel.prefixo} "
                f"({s.papel.nome.lower()})."
            )
            continue
        # O papel tem de servir à peça: o programa não aceita depois um nome que a geometria
        # contradiz (pilar deitado, viga em pé, chapa chamada de barra).
        avaliacao = pn.avaliar(s.papel, s.angulo_graus, s.forma)
        if not avaliacao.vale:
            problemas.append(
                f"{s.corpo} → {s.papel.nome.lower()}: {avaliacao.nota}. Escolha o papel que a "
                "peça tem no modelo."
            )
    for nome, vezes in sorted(contagem.items()):
        if vezes > 1:
            corpos = [s.corpo for s in plano.sugestoes if s.nome == nome]
            problemas.append(
                f"“{nome}” para {vezes} corpos ({', '.join(corpos[:4])}"
                + (" …" if len(corpos) > 4 else "")
                + "): cada corpo precisa de um nome só dele."
            )
    nomes_do_modelo = {c.nome for c in g.corpos}
    faltam = [s.corpo for s in plano.sugestoes if s.corpo not in nomes_do_modelo]
    if faltam:
        problemas.append(
            f"{len(faltam)} corpo(s) da tabela não estão no esqueleto: envie o esqueleto de novo."
        )
    return problemas


# ---------------------------------------------------------------------------------------------
# Os perfis dos itens da lista de corte
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ItemDaLista:
    item: str  # o item da lista de corte (a pasta no SolidWorks)
    descricao: str
    corpos: tuple[str, ...]
    area_cm2: float | None  # a maior área de seção medida entre os corpos (peça mais reta)
    perfil_lido: str  # o que o programa lê do modelo
    origem: str
    declarado: str  # o PERFIL que o item já tem no SolidWorks (macro v7)
    #: A leitura não deixa dúvida: a descrição e o desenho dizem o mesmo perfil.
    certo: bool

    @property
    def sugerido(self) -> str:
        """O perfil que a página põe para gravar: o declarado, ou o lido sem dúvida."""
        return self.declarado or (self.perfil_lido if self.certo else "")


#: O desenho contradiz a descrição. A peça curta não entra: nela a área não diz nada, mas a
#: descrição já diz o perfil.
_SINAIS_DE_DUVIDA = (ld.PELA_AREA, ld.DESENHO_MAIS_PESADO, "não confere")


def perfis_dos_itens(g: ld.GeometriaDoModelo) -> list[ItemDaLista]:
    """Um item da lista de corte por linha, com o perfil que o programa lê dele."""
    perfis = ld.perfis_do_esqueleto(g)
    por_item: dict[str, list[ld.CorpoDoModelo]] = {}
    for c in g.corpos:
        if c.item and c.forma != ld.FORMA_CHAPA:
            por_item.setdefault(c.item, []).append(c)
    itens = []
    for item, corpos in por_item.items():
        lidos = Counter(perfis[c.nome][0] for c in corpos if perfis.get(c.nome, ("", ""))[0])
        perfil_lido = lidos.most_common(1)[0][0] if lidos else ""
        origem = next(
            (perfis[c.nome][1] for c in corpos if perfis.get(c.nome, ("", ""))[0] == perfil_lido),
            "",
        )
        declarados = Counter(c.perfil_declarado for c in corpos if c.perfil_declarado)
        declarado = declarados.most_common(1)[0][0] if declarados else ""
        descricao = corpos[0].descricao
        conhecido = lm.perfil_conhecido(descricao) if descricao else None
        certo = (
            bool(perfil_lido)
            and conhecido is not None
            and conhecido.nome == perfil_lido
            and not any(sinal in origem for sinal in _SINAIS_DE_DUVIDA)
            and len(lidos) == 1
        )
        areas = [c.area_mm2 for c in corpos if c.area_mm2]
        itens.append(
            ItemDaLista(
                item=item,
                descricao=descricao,
                corpos=tuple(c.nome for c in corpos),
                area_cm2=max(areas) / 100 if areas else None,
                perfil_lido=perfil_lido,
                origem=origem,
                declarado=declarado,
                certo=certo,
            )
        )
    return sorted(itens, key=lambda i: (i.descricao, i.item))


def perfis_do_catalogo() -> list[str]:
    """Os nomes que o programa conhece (perfis e cantoneiras), para a escolha do PERFIL."""
    nomes = set(sc.listar_perfis()) | set(ct.CATALOGO_CANTONEIRAS)
    return sorted(nomes)


def conferir_perfis(escolhidos: Mapping[str, str]) -> list[str]:
    """Perfil escolhido que o programa não reconhece (vazio = o item fica sem PERFIL)."""
    return [
        f"{item}: “{perfil}” não é um perfil do catálogo do programa."
        for item, perfil in escolhidos.items()
        if perfil and lm.perfil_conhecido(perfil) is None
    ]


# ---------------------------------------------------------------------------------------------
# O arquivo para a macro e o relatório dela
# ---------------------------------------------------------------------------------------------
def _campo(texto: str) -> str:
    limpo = str(texto).replace("\r", " ").replace("\n", " ")
    return '"' + limpo.replace('"', '""') + '"'


def _mm(valor: float) -> str:
    return f"{valor * 1000.0:.1f}"


def arquivo_para_a_macro(
    plano: PlanoDeNomes,
    g: ld.GeometriaDoModelo,
    *,
    perfis: Mapping[str, str] | None = None,
    quando: str = "",
) -> bytes:
    """O ``<peça>_nomes.csv`` que a macro ``renomear_corpos.bas`` lê (cp1252, ponto e vírgula).

    Números com ponto decimal, sem milhar (a macro lê com ``Val``, igual em qualquer Windows). Só
    os corpos que mudam de nome; ``perfis`` (item → perfil) acrescenta as linhas do PERFIL de cada
    item da lista de corte (vazio apaga o PERFIL do item).
    """
    linhas = [
        f"ARQUIVO;{_campo('Mecanica Toolkit - nomes das barras ' + VERSAO_DO_ARQUIVO)}",
        f"PECA;{_campo(g.peca)}",
        f"CONFIGURACAO;{_campo(g.configuracao)}",
        f"ESQUELETO;{_campo(g.gerado_em)}",
        f"DATA;{_campo(quando)}",
        ";".join(COLUNAS_DOS_CORPOS),
    ]
    for s in plano.sugestoes:
        corpo = g.corpo(s.corpo)
        if corpo is None or not s.muda:
            continue
        volume = f"{corpo.volume_m3 * 1e6:.1f}" if corpo.volume_m3 else ""
        linhas.append(
            ";".join(
                [
                    "CORPO",
                    _campo(corpo.nome),
                    _campo(s.nome),
                    s.papel.prefixo,
                    corpo.forma,
                    *(_mm(v) for v in (*corpo.inicio, *corpo.fim)),
                    _mm(corpo.comprimento_m),
                    volume,
                ]
            )
        )
    if perfis:
        linhas.append(";".join(COLUNAS_DOS_PERFIS))
        corpos_do_item: dict[str, str] = {}
        for c in g.corpos:
            if c.item:
                corpos_do_item.setdefault(c.item, c.nome)
        for item, perfil in sorted(perfis.items()):
            if item not in corpos_do_item:
                continue
            linhas.append(
                ";".join(["PERFIL", _campo(item), _campo(perfil), _campo(corpos_do_item[item])])
            )
    return ("\r\n".join(linhas) + "\r\n").encode("cp1252", errors="replace")


def nome_do_arquivo(g: ld.GeometriaDoModelo) -> str:
    """'portico.SLDPRT' → 'portico_nomes.csv' (a macro procura esse nome ao lado da peça)."""
    peca = g.peca or Path(g.arquivo).stem.removesuffix("_esqueleto") or "modelo"
    base = peca.rsplit(".", 1)[0] if peca.lower().endswith((".sldprt", ".sldasm")) else peca
    return f"{base}_nomes.csv"


SITUACAO_RENOMEADO = "RENOMEADO"
SITUACAO_PELA_GEOMETRIA = "RENOMEADO PELA GEOMETRIA"
SITUACAO_JA_TINHA = "JA TINHA O NOME"
SITUACAO_PULADO = "PULADO"
SITUACOES_TROCADAS = (SITUACAO_RENOMEADO, SITUACAO_PELA_GEOMETRIA)


@dataclass(frozen=True)
class LinhaDoRelatorio:
    tipo: str  # CORPO ou PERFIL
    antigo: str
    novo: str
    situacao: str
    motivo: str = ""

    @property
    def trocou(self) -> bool:
        return self.situacao in SITUACOES_TROCADAS


@dataclass(frozen=True)
class RelatorioDaMacro:
    peca: str
    data: str
    linhas: tuple[LinhaDoRelatorio, ...]
    avisos: tuple[str, ...] = ()

    @property
    def corpos(self) -> list[LinhaDoRelatorio]:
        return [linha for linha in self.linhas if linha.tipo == "CORPO"]

    @property
    def perfis(self) -> list[LinhaDoRelatorio]:
        return [linha for linha in self.linhas if linha.tipo == "PERFIL"]

    @property
    def trocados(self) -> list[LinhaDoRelatorio]:
        return [linha for linha in self.corpos if linha.trocou]

    @property
    def pulados(self) -> list[LinhaDoRelatorio]:
        return [linha for linha in self.linhas if linha.situacao == SITUACAO_PULADO]


class RelatorioInvalido(ValueError):
    """O arquivo não é o relatório da macro renomear_corpos."""


def ler_relatorio_da_macro(conteudo: bytes, nome_arquivo: str = "") -> RelatorioDaMacro:
    """O ``<peça>_nomes_aplicados.csv`` que a macro grava: uma linha por corpo e por item."""
    try:
        linhas = lm._celulas_do_arquivo(conteudo, nome_arquivo or "relatorio.csv")
    except ValueError as erro:
        raise RelatorioInvalido(str(erro)) from erro
    peca = data = ""
    saida: list[LinhaDoRelatorio] = []
    reconhecido = False
    for linha in linhas:
        celulas = [str(c).strip() for c in linha]
        if not celulas or not celulas[0]:
            continue
        chave = celulas[0].upper()
        if chave == "RELATORIO":
            reconhecido = True
        elif chave == "PECA" and len(celulas) > 1:
            peca = celulas[1]
        elif chave == "DATA" and len(celulas) > 1:
            data = celulas[1]
        elif chave in ("CORPO", "PERFIL") and len(celulas) >= 4:
            saida.append(
                LinhaDoRelatorio(
                    chave,
                    celulas[1],
                    celulas[2],
                    celulas[3].upper(),
                    celulas[4] if len(celulas) > 4 else "",
                )
            )
    if not reconhecido:
        raise RelatorioInvalido(
            "Este não é o relatório da macro renomear_corpos (o …_nomes_aplicados.csv que ela "
            "grava ao lado da peça)."
        )
    return RelatorioDaMacro(peca, data, tuple(saida))


# ---------------------------------------------------------------------------------------------
# As trocas guardadas no projeto
# ---------------------------------------------------------------------------------------------
def _renomeacao(
    antigo: str, novo: str, corpo: ld.CorpoDoModelo, quando: str, confirmada: bool
) -> pn.Renomeacao:
    meio = tuple((a + b) / 2 for a, b in zip(corpo.inicio, corpo.fim, strict=True))
    return pn.Renomeacao(
        antigo, novo, (meio[0], meio[1], meio[2]), corpo.comprimento_m, quando, confirmada
    )


def renomeacoes_do_plano(
    plano: PlanoDeNomes, g: ld.GeometriaDoModelo, quando: str
) -> tuple[pn.Renomeacao, ...]:
    """As trocas que o arquivo da macro pede, com a posição de cada corpo (ainda não confirmadas)."""
    saida = []
    for s in plano.sugestoes:
        corpo = g.corpo(s.corpo)
        if corpo is not None and s.muda:
            saida.append(_renomeacao(s.corpo, s.nome, corpo, quando, False))
    return tuple(saida)


def renomeacoes_do_relatorio(
    relatorio: RelatorioDaMacro, g: ld.GeometriaDoModelo, quando: str
) -> tuple[pn.Renomeacao, ...]:
    """As trocas que a macro fez, com a posição do corpo no esqueleto (pelo nome antigo ou pelo
    novo, conforme o esqueleto do projeto seja de antes ou de depois da troca)."""
    saida = []
    for linha in relatorio.trocados:
        corpo = g.corpo(linha.antigo) or g.corpo(linha.novo)
        if corpo is not None and linha.antigo != linha.novo:
            saida.append(_renomeacao(linha.antigo, linha.novo, corpo, quando, True))
    return tuple(saida)


def juntar_renomeacoes(
    antigas: Sequence[pn.Renomeacao], novas: Sequence[pn.Renomeacao]
) -> tuple[pn.Renomeacao, ...]:
    """O histórico com as trocas novas: a mesma troca (antigo → novo) fica uma vez só, a mais
    recente, e confirmada se alguma das duas foi; só as últimas :data:`LIMITE_DO_HISTORICO`."""
    por_par: dict[tuple[str, str], pn.Renomeacao] = {}
    for r in [*antigas, *novas]:
        anterior = por_par.get((r.antigo, r.novo))
        if anterior is not None and anterior.confirmada and not r.confirmada:
            r = replace(r, confirmada=True)
        por_par[(r.antigo, r.novo)] = r
    ordenadas = sorted(por_par.values(), key=lambda r: r.quando)
    return tuple(ordenadas[-LIMITE_DO_HISTORICO:])


@dataclass(frozen=True)
class Escolhas:
    """O que a página guarda no projeto além das trocas: as escolhas da tabela."""

    eixo_vertical: str = ""
    papeis: Mapping[str, str] = field(default_factory=dict)  # corpo → prefixo
    a_mao: Mapping[str, str] = field(default_factory=dict)  # corpo → nome
    sem_troca: tuple[str, ...] = ()
    perfis: Mapping[str, str] = field(default_factory=dict)  # item → perfil
    refazer: bool = False


def _texto(valor: Any) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _mapa(valor: Any) -> dict[str, str]:
    if not isinstance(valor, Mapping):
        return {}
    return {str(k): _texto(v) for k, v in valor.items() if isinstance(k, str) and _texto(v)}


def escolhas_do_projeto(projeto: Mapping[str, Any] | None) -> Escolhas:
    dados = pn.dados_do_projeto(projeto)
    eixo = _texto(dados.get("eixo_vertical"))
    papeis = {k: v for k, v in _mapa(dados.get("papeis")).items() if v in pn.POR_PREFIXO}
    sem_troca = dados.get("sem_troca")
    perfis = dados.get("perfis")
    return Escolhas(
        eixo_vertical=eixo if eixo in ("Y", "Z") else "",
        papeis=papeis,
        a_mao=_mapa(dados.get("a_mao")),
        sem_troca=tuple(s for s in sem_troca if isinstance(s, str))
        if isinstance(sem_troca, list | tuple)
        else (),
        # Vazio também é escolha: "não gravar" (ou apagar o PERFIL que o item já tinha).
        perfis={k: _texto(v) for k, v in perfis.items() if isinstance(k, str)}
        if isinstance(perfis, Mapping)
        else {},
        refazer=bool(dados.get("refazer")),
    )


def perfil_escolhido(item: ItemDaLista, escolhas: Escolhas) -> str:
    """O perfil a gravar no item: o escolhido na tabela, senão o sugerido."""
    return escolhas.perfis.get(item.item, item.sugerido)


def perfis_a_gravar(itens: Sequence[ItemDaLista], escolhas: Escolhas) -> dict[str, str]:
    """Item → perfil, só onde o escolhido é diferente do PERFIL que o item já tem (vazio apaga)."""
    return {
        item.item: escolhido
        for item in itens
        if (escolhido := perfil_escolhido(item, escolhas)) != item.declarado
    }


def trocas_feitas(renomeacoes: Sequence[pn.Renomeacao], g: ld.GeometriaDoModelo) -> dict[str, str]:
    """Nome antigo → nome de hoje, só das trocas que aconteceram: confirmadas pelo relatório da
    macro, com o nome novo já no esqueleto, ou cujo nome novo trocou de novo numa troca que
    aconteceu (A → B só se prova por B → C). As cadeias (A → B → C) vão direto ao último."""
    ordenadas = sorted(renomeacoes, key=lambda r: r.quando)
    provadas = {i for i, r in enumerate(ordenadas) if r.confirmada or g.corpo(r.novo) is not None}
    mudou = True
    while mudou:
        mudou = False
        antigos_provados = {ordenadas[i].antigo for i in provadas}
        for i, r in enumerate(ordenadas):
            if i not in provadas and r.novo in antigos_provados:
                provadas.add(i)
                mudou = True
    passos: dict[str, str] = {}
    for i, r in enumerate(ordenadas):
        if i in provadas:
            passos[r.antigo] = r.novo
    finais: dict[str, str] = {}
    for antigo in passos:
        atual, vistos = antigo, {antigo}
        while atual in passos and passos[atual] not in vistos:
            atual = passos[atual]
            vistos.add(atual)
        if atual != antigo:
            finais[antigo] = atual
    return finais


def campos_do_projeto(
    projeto: Mapping[str, Any] | None,
    escolhas: Escolhas,
    novas_renomeacoes: Sequence[pn.Renomeacao] = (),
    relatorio: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """O campo ``nomes_das_barras`` do projeto, pronto para gravar (as trocas de antes ficam)."""
    anteriores = pn.dados_do_projeto(projeto)
    historico = juntar_renomeacoes(pn.renomeacoes_do_projeto(projeto), novas_renomeacoes)
    relatorios = anteriores.get("relatorios")
    lista_relatorios = (
        [r for r in relatorios if isinstance(r, Mapping)] if isinstance(relatorios, list) else []
    )
    if relatorio:
        lista_relatorios = [*lista_relatorios, dict(relatorio)][-20:]
    return {
        pn.CHAVE_DO_PROJETO: {
            "eixo_vertical": escolhas.eixo_vertical,
            "papeis": dict(escolhas.papeis),
            "a_mao": dict(escolhas.a_mao),
            "sem_troca": list(escolhas.sem_troca),
            "perfis": dict(escolhas.perfis),
            "refazer": escolhas.refazer,
            "renomeacoes": [pn.renomeacao_para_dicionario(r) for r in historico],
            "relatorios": lista_relatorios,
        }
    }


# ---------------------------------------------------------------------------------------------
# O plano de cargas com os nomes novos
# ---------------------------------------------------------------------------------------------
def _elemento_novo(elemento: str, trocas: Mapping[str, str]) -> str:
    texto = elemento.strip()
    if texto in trocas:
        return trocas[texto]
    for antigo, novo in trocas.items():
        if texto.startswith(antigo + " ("):
            return novo + texto[len(antigo) :]
    return elemento


def plano_com_os_nomes_novos(
    plano: pc.PlanoDeCargas, trocas: Mapping[str, str]
) -> tuple[pc.PlanoDeCargas, int]:
    """O plano de cargas com as linhas que citam um corpo pelo nome antigo passadas ao novo
    ("Aparar/Estender12[1] (Viga-3(…))" → "P-A1 (Viga-3(…))"); devolve quantas linhas mudaram."""
    if not trocas:
        return plano, 0
    mudaram = 0
    acoes = []
    for acao in plano.acoes:
        cargas = []
        for carga in acao.cargas:
            elemento = _elemento_novo(carga.elemento, trocas)
            if elemento != carga.elemento:
                mudaram += 1
                carga = replace(carga, elemento=elemento)
            cargas.append(carga)
        acoes.append(replace(acao, cargas=tuple(cargas)))
    if not mudaram:
        return plano, 0
    return replace(plano, acoes=tuple(acoes)), mudaram


def linhas_com_nome_antigo(plano: pc.PlanoDeCargas, antigos: Iterable[str]) -> int:
    """Quantas linhas do plano ainda citam um desses nomes."""
    conjunto = set(antigos)
    return sum(
        1
        for acao in plano.acoes
        for carga in acao.cargas
        if carga.elemento.strip() in conjunto
        or any(carga.elemento.strip().startswith(a + " (") for a in conjunto)
    )


# ---------------------------------------------------------------------------------------------
# A planta com os nomes
# ---------------------------------------------------------------------------------------------
CORES_DO_PAPEL: dict[str, str] = {
    "P": "#3f6fb5",
    "V": "#6b7280",
    "LG": "#2e7d32",
    "DG": "#558b2f",
    "C": "#d4760a",
    "MF": "#b45309",
    "GC": "#7b5ea7",
    "PS": "#f8b46a",
    "PT": "#9ccc65",
    "ES": "#66bb6a",
    "CH": "#bdbdbd",
    "PC": "#a1887f",
}


def _xml(texto: str) -> str:
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_da_planta(
    plano: PlanoDeNomes, g: ld.GeometriaDoModelo, nivel: int | None = None, *, largura: int = 760
) -> str:
    """A planta do nível (ou de tudo, com ``None``): eixos da grade, pilares, barras e chapas com o
    nome novo. Vista Superior: X para a direita."""
    eixo = plano.grade.eixo_vertical
    sugestoes = {s.corpo: s for s in plano.sugestoes}
    corpos = [c for c in g.corpos if c.nome in sugestoes]
    if nivel is not None:
        corpos = [
            c
            for c in corpos
            if sugestoes[c.nome].nivel == nivel or sugestoes[c.nome].papel is pn.PILAR
        ]
    pontos = [planta(p, eixo) for c in corpos for p in (c.inicio, c.fim, *c.contorno)]
    pontos += [(x, y) for _, x in plano.grade.numeros for _, y in plano.grade.letras]
    if not pontos:
        return ""
    xmin = min(p[0] for p in pontos)
    xmax = max(p[0] for p in pontos)
    ymin = min(p[1] for p in pontos)
    ymax = max(p[1] for p in pontos)
    margem = 60.0
    vao_x, vao_y = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)
    escala = min((largura - 2 * margem) / vao_x, 520.0 / vao_y)
    altura_svg = int(vao_y * escala + 2 * margem)

    def px(x: float) -> float:
        return margem + (x - xmin) * escala

    def py(y: float) -> float:
        return margem + (ymax - y) * escala

    partes: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura_svg}" '
        f'viewBox="0 0 {largura} {altura_svg}" font-family="sans-serif">',
        f'<rect width="{largura}" height="{altura_svg}" fill="#ffffff"/>',
    ]
    for rotulo, x in plano.grade.numeros:
        partes.append(
            f'<line x1="{px(x):.1f}" y1="{margem - 30:.1f}" x2="{px(x):.1f}" '
            f'y2="{altura_svg - margem + 20:.1f}" stroke="#9ca3af" stroke-dasharray="6 4"/>'
            f'<circle cx="{px(x):.1f}" cy="{margem - 40:.1f}" r="11" fill="#ffffff" '
            f'stroke="#4b5563"/><text x="{px(x):.1f}" y="{margem - 36:.1f}" font-size="12" '
            f'text-anchor="middle" fill="#111827">{_xml(rotulo)}</text>'
        )
    for rotulo, y in plano.grade.letras:
        partes.append(
            f'<line x1="{margem - 30:.1f}" y1="{py(y):.1f}" x2="{largura - margem + 20:.1f}" '
            f'y2="{py(y):.1f}" stroke="#9ca3af" stroke-dasharray="6 4"/>'
            f'<circle cx="{margem - 40:.1f}" cy="{py(y):.1f}" r="11" fill="#ffffff" '
            f'stroke="#4b5563"/><text x="{margem - 40:.1f}" y="{py(y) + 4:.1f}" font-size="12" '
            f'text-anchor="middle" fill="#111827">{_xml(rotulo)}</text>'
        )
    textos: list[str] = []
    for c in sorted(corpos, key=lambda c: sugestoes[c.nome].papel is pn.PILAR):
        s = sugestoes[c.nome]
        cor = CORES_DO_PAPEL.get(s.papel.prefixo, "#6b7280")
        if c.forma == ld.FORMA_CHAPA and len(c.contorno) >= 3:
            caminho = " ".join(
                f"{px(x):.1f},{py(y):.1f}" for x, y in (planta(p, eixo) for p in c.contorno)
            )
            partes.append(
                f'<polygon points="{caminho}" fill="{cor}" fill-opacity="0.25" stroke="{cor}"/>'
            )
            cx = sum(planta(p, eixo)[0] for p in c.contorno) / len(c.contorno)
            cy = sum(planta(p, eixo)[1] for p in c.contorno) / len(c.contorno)
            textos.append(
                f'<text x="{px(cx):.1f}" y="{py(cy):.1f}" font-size="10" text-anchor="middle" '
                f'fill="#374151">{_xml(s.nome)}</text>'
            )
            continue
        (x1, y1), (x2, y2) = planta(c.inicio, eixo), planta(c.fim, eixo)
        # Peça curta e chapa sem carga com letra menor: não disputam espaço com as barras.
        fonte = 8 if s.papel in (pn.PECA, pn.CHAPA) else 10
        if s.papel is pn.PILAR or math.hypot(x2 - x1, y2 - y1) * escala < 4:
            x, y = planta(_pontas_por_altura(c, eixo)[0], eixo)
            lado = 5 if s.papel is pn.PILAR else 3
            partes.append(
                f'<rect x="{px(x) - lado:.1f}" y="{py(y) - lado:.1f}" width="{2 * lado}" '
                f'height="{2 * lado}" fill="{cor}"/>'
            )
            textos.append(
                f'<text x="{px(x) + 8:.1f}" y="{py(y) - 8:.1f}" font-size="{fonte}" '
                f'fill="{cor}">{_xml(s.nome)}</text>'
            )
            continue
        partes.append(
            f'<line x1="{px(x1):.1f}" y1="{py(y1):.1f}" x2="{px(x2):.1f}" y2="{py(y2):.1f}" '
            f'stroke="{cor}" stroke-width="3" stroke-linecap="round"/>'
        )
        # O nome ao longo da barra (sem ficar de cabeça para baixo): as barras que correm em
        # direções diferentes não empilham os nomes umas sobre as outras.
        cx, cy = px((x1 + x2) / 2), py((y1 + y2) / 2)
        giro = math.degrees(math.atan2(py(y2) - py(y1), px(x2) - px(x1)))
        if giro > 90:
            giro -= 180
        elif giro <= -90:
            giro += 180
        textos.append(
            f'<text x="{cx:.1f}" y="{cy - 5:.1f}" font-size="{fonte}" text-anchor="middle" '
            f'transform="rotate({giro:.1f} {cx:.1f} {cy:.1f})" fill="#111827" stroke="#ffffff" '
            f'stroke-width="3" paint-order="stroke">{_xml(s.nome)}</text>'
        )
    partes.extend(textos)
    partes.append("</svg>")
    return "".join(partes)
