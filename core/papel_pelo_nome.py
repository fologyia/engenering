"""O papel de cada peça pelo nome dela no SolidWorks: pilar, viga, contraventamento, chapa de piso…

O programa entende a estrutura pela posição de cada corpo (vertical é pilar, horizontal é viga,
inclinada é contraventamento) e pelos esforços. Isso erra onde a posição engana: a longarina da
escada é inclinada e trabalha fletida, o montante do guarda-corpo é vertical e não é pilar, a
chapa de ligação deitada não é piso. O nome do corpo no SolidWorks resolve: ele diz o papel.

**O padrão** (o que a página Nomes das barras sugere e a macro ``renomear_corpos.bas`` grava):
``PREFIXO-LOCAL``. O prefixo diz o papel (:data:`PAPEIS`); o resto diz onde a peça está, só para
quem lê: ``P-A1`` é o pilar do cruzamento A1, ``V-N1-A1-A2`` a viga do nível 1 entre A1 e A2. O
programa também entende o papel escrito por extenso (``W200x31,3 - Pilar``, ``Viga de borda``) e a
forma curta de costume (``P1``, ``V101``).

**O nome não manda sozinho.** Um nome que contradiz a geometria (pilar deitado, viga em pé, chapa
chamada de barra) é tratado como engano: vale a posição, e o programa avisa (:func:`avaliar`).

O projeto guarda as trocas de nome feitas pela página (:class:`Renomeacao`): com elas, os
resultados de um estudo rodado antes da troca ainda acham o corpo certo no esqueleto novo.

Sem dependências do resto do programa: o núcleo inteiro pode importar daqui.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Os tipos de barra da verificação (os mesmos de ``core.esforcos_modelo.TIPOS_DE_BARRA``).
TIPO_PILAR, TIPO_VIGA, TIPO_CONTRAVENTAMENTO, TIPO_OUTRO = (
    "Pilar",
    "Viga",
    "Contraventamento",
    "Outro",
)
#: As formas do esqueleto (as mesmas de ``core.leitura_do_modelo``).
FORMA_BARRA, FORMA_CHAPA, FORMA_BLOCO = "BARRA", "CHAPA", "BLOCO"

TAMANHO_MAXIMO = 60  # caracteres de um nome novo
CHAVE_DO_PROJETO = "nomes_das_barras"


@dataclass(frozen=True)
class Papel:
    """O que a peça é, pelo prefixo do nome."""

    prefixo: str
    nome: str
    #: O tipo da barra na verificação (Pilar, Viga, Contraventamento, Outro); vazio quando o nome
    #: não muda o tipo (chapa, outra peça).
    tipo: str
    #: A forma que o papel exige (BARRA ou CHAPA); vazio: qualquer uma.
    forma: str
    explicacao: str

    @property
    def rotulo(self) -> str:
        """ "P — Pilar": o que aparece na lista de escolha da página."""
        return f"{self.prefixo} — {self.nome}"


PILAR = Papel(
    "P",
    "Pilar",
    TIPO_PILAR,
    FORMA_BARRA,
    "barra em pé que leva as cargas até a base (ou a outra barra)",
)
VIGA = Papel(
    "V", "Viga", TIPO_VIGA, FORMA_BARRA, "barra deitada que trabalha à flexão: principal ou de piso"
)
LONGARINA = Papel(
    "LG",
    "Longarina de escada",
    TIPO_VIGA,
    FORMA_BARRA,
    "a viga inclinada que leva os degraus: trabalha fletida, não é contraventamento",
)
DEGRAU = Papel("DG", "Degrau", TIPO_VIGA, FORMA_BARRA, "a barra do degrau, entre as longarinas")
CONTRAVENTAMENTO = Papel(
    "C",
    "Contraventamento",
    TIPO_CONTRAVENTAMENTO,
    FORMA_BARRA,
    "diagonal ou escora que trava a estrutura: trabalha à força normal",
)
MAO_FRANCESA = Papel(
    "MF",
    "Mão-francesa",
    TIPO_CONTRAVENTAMENTO,
    FORMA_BARRA,
    "a escora inclinada entre o pilar e a viga (ou o balanço) que ela segura",
)
GUARDA_CORPO = Papel(
    "GC",
    "Guarda-corpo",
    TIPO_OUTRO,
    FORMA_BARRA,
    "montante, travessa ou corrimão do guarda-corpo: não é pilar nem viga da estrutura",
)
PISO = Papel("PS", "Piso", "", FORMA_CHAPA, "chapa de piso: recebe o peso do piso e a sobrecarga")
PATAMAR = Papel(
    "PT", "Patamar", "", FORMA_CHAPA, "chapa do patamar da escada: sobrecarga de escada"
)
LANCE = Papel("ES", "Lance de escada", "", FORMA_CHAPA, "chapa inclinada do lance da escada")
CHAPA = Papel(
    "CH",
    "Chapa sem carga",
    "",
    FORMA_CHAPA,
    "chapa de ligação, de base ou enrijecedor: não recebe carga de piso",
)
PECA = Papel(
    "PC",
    "Outra peça",
    "",
    "",
    "toco, calço, espaçador: o nome só identifica, o programa segue a geometria",
)

PAPEIS: tuple[Papel, ...] = (
    PILAR,
    VIGA,
    LONGARINA,
    DEGRAU,
    CONTRAVENTAMENTO,
    MAO_FRANCESA,
    GUARDA_CORPO,
    PISO,
    PATAMAR,
    LANCE,
    CHAPA,
    PECA,
)
POR_PREFIXO: dict[str, Papel] = {p.prefixo: p for p in PAPEIS}
POR_ROTULO: dict[str, Papel] = {p.rotulo: p for p in PAPEIS}
DE_BARRA = tuple(p for p in PAPEIS if p.forma == FORMA_BARRA)
DE_CHAPA = tuple(p for p in PAPEIS if p.forma == FORMA_CHAPA)

# Os prefixos mais longos primeiro: "PS-1" é piso, não pilar.
_PREFIXOS = sorted(POR_PREFIXO, key=len, reverse=True)
# O prefixo, um hífen e alguma coisa depois: "P-A1". A letra sozinha ("C", "P[2]") não basta —
# muita peça de teste e de biblioteca se chama assim.
_CODIGO = re.compile(rf"^({'|'.join(_PREFIXOS)})-(.+)$", re.IGNORECASE)
_CURTO = re.compile(r"^(P|V)(\d{1,4}[A-Z]?)$", re.IGNORECASE)  # P1, P12A, V101
_INDICE = re.compile(r"\s*(?:\[\d+\]|<\d+>)\s*$")  # o [n] dos corpos de um membro, o <n> da lista
_PARECE_PERFIL = re.compile(r"\d\s*[xX×]\s*\d")  # C-8X11.5 é um perfil, não um contraventamento
_PERMITIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
#: O nome da viga no Simulation: "Viga-12(<corpo>)" (em inglês, "Beam-12(<corpo>)").
_VIGA_DO_SIMULATION = re.compile(
    r"^\s*(?:viga|beam)\s*-?\s*\d+\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL
)

#: O papel escrito por extenso (sem acento, minúsculas, hífens como espaço).
_PALAVRAS: tuple[tuple[re.Pattern[str], Papel], ...] = tuple(
    (re.compile(rf"\b(?:{padrao})\b"), papel)
    for padrao, papel in (
        (r"pilar|pilares|coluna|colunas", PILAR),
        (r"viga|vigas", VIGA),
        (r"longarina|longarinas", LONGARINA),
        (r"degrau|degraus", DEGRAU),
        (r"contraventamento|contraventamentos|diagonal|diagonais", CONTRAVENTAMENTO),
        (r"mao francesa|maos francesas", MAO_FRANCESA),
        (r"guarda corpo|guarda corpos|corrimao|corrimaos", GUARDA_CORPO),
    )
)


@dataclass(frozen=True)
class NomeLido:
    papel: Papel
    #: Pelo prefixo do padrão (P-A1, PS-N1-01, P1, V101) ou pela palavra por extenso.
    pelo_codigo: bool

    @property
    def como(self) -> str:
        return "prefixo do nome" if self.pelo_codigo else "palavra no nome"


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


def sem_indice(nome: str) -> str:
    """'P-A1[2]' → 'P-A1'; 'C8x13.75<1>' → 'C8x13.75'."""
    return _INDICE.sub("", str(nome)).strip()


def corpo_do_nome(nome: str) -> str:
    """O nome do corpo: 'Viga-12(P-A1)' → 'P-A1'; um nome de corpo passa direto
    ('Canal c C8X13.75(1)' continua o mesmo)."""
    m = _VIGA_DO_SIMULATION.match(str(nome))
    return m.group(1).strip() if m else str(nome).strip()


def _pelo_codigo(texto: str) -> Papel | None:
    m = _CODIGO.match(texto)
    if m is not None:
        resto = m.group(2) or ""
        if not _PARECE_PERFIL.search(resto):
            return POR_PREFIXO[m.group(1).upper()]
    m = _CURTO.match(texto)
    if m is not None:
        return POR_PREFIXO[m.group(1).upper()]
    return None


def papel_do_nome(nome: str) -> NomeLido | None:
    """O papel que o nome do corpo diz, ou ``None`` se não diz.

    Primeiro o padrão do programa (``P-A1``, ``V-N1-01``, ``PS-N1-02``, ``P-A1[3]``) e a forma curta
    de costume (``P1``, ``V101``); depois a palavra por extenso (``W200x31,3 - Pilar``), a primeira
    que aparecer. Os nomes que o SolidWorks dá sozinho (``Membro estrutural1[1]``,
    ``Aparar/Estender12[1]``, ``Canal c C8X13.75(1)``) e a letra sozinha (``C``) não dizem papel.
    """
    texto = sem_indice(nome)
    if not texto:
        return None
    pelo_codigo = _pelo_codigo(texto)
    if pelo_codigo is not None:
        return NomeLido(pelo_codigo, True)
    normal = " ".join(re.sub(r"[-_/]", " ", _sem_acento(texto)).split())
    achados = [(m.start(), papel) for padrao, papel in _PALAVRAS if (m := padrao.search(normal))]
    if not achados:
        return None
    return NomeLido(min(achados, key=lambda par: par[0])[1], False)


def e_nome_codificado(nome: str) -> bool:
    """O nome segue o padrão de prefixo (``P-A1``, ``V-N1-01``, ``P1``)? Aceita o nome da viga do
    Simulation (``Viga-3(P-A1)``) e o ``[n]`` dos membros. Esses nomes não dizem o perfil."""
    return _pelo_codigo(sem_indice(corpo_do_nome(nome))) is not None


# ---------------------------------------------------------------------------------------------
# O nome contra a geometria
# ---------------------------------------------------------------------------------------------
ANGULO_PILAR_MINIMO = 45.0  # graus com a horizontal: abaixo disso, "pilar" é engano
ANGULO_VIGA_MAXIMO = 45.0  # acima disso, "viga" é engano
ANGULO_DEGRAU_MAXIMO = 15.0
ANGULO_PILAR_PRUMO = 76.0  # a partir daqui o pilar está a prumo (o mesmo da leitura do modelo)
ANGULO_INCLINADA = 10.0  # acima disso a barra (ou a chapa) é inclinada
ANGULO_PISO_MAXIMO = 60.0  # chapa mais em pé que isso não é piso


@dataclass(frozen=True)
class Avaliacao:
    #: O nome pode valer: a geometria não o contradiz.
    vale: bool
    #: O que chama a atenção (contradição, ou um uso pouco comum que o nome confirma).
    nota: str = ""


def avaliar(papel: Papel, angulo_graus: float | None, forma: str = "") -> Avaliacao:
    """O papel do nome contra a geometria: ``angulo_graus`` com a horizontal (de uma barra, pela
    linha de centro; de uma chapa, pelo plano dela) e a forma medida pela macro (BARRA, CHAPA,
    BLOCO; vazia nas versões antigas). Sem a medida, o nome vale.

    Contradição (não vale): papel de chapa numa barra e vice-versa; pilar a menos de 45° da
    horizontal; viga a mais de 45°; degrau inclinado; piso em pé; lance de escada em nível. O
    resto vale, com uma nota quando é pouco comum (pilar inclinado, viga inclinada, rampa).
    """
    if papel.forma == FORMA_CHAPA and forma in (FORMA_BARRA, FORMA_BLOCO):
        return Avaliacao(False, f"a peça é uma {forma.lower()}, não uma chapa")
    if papel.forma == FORMA_BARRA and forma == FORMA_CHAPA:
        return Avaliacao(False, "a peça é uma chapa, não uma barra")
    if angulo_graus is None or not math.isfinite(angulo_graus):
        return Avaliacao(True)
    angulo = abs(angulo_graus)
    graus = f"{angulo:.0f}°"
    if papel is PILAR:
        if angulo < ANGULO_PILAR_MINIMO:
            return Avaliacao(False, f"a barra está a {graus} da horizontal")
        if angulo < ANGULO_PILAR_PRUMO:
            return Avaliacao(True, f"pilar inclinado ({graus} com a horizontal)")
    elif papel is VIGA:
        if angulo > ANGULO_VIGA_MAXIMO:
            return Avaliacao(False, f"a barra está a {graus} da horizontal")
        if angulo > ANGULO_INCLINADA:
            return Avaliacao(True, f"viga inclinada ({graus} com a horizontal)")
    elif papel is DEGRAU:
        if angulo > ANGULO_DEGRAU_MAXIMO:
            return Avaliacao(False, f"a barra está a {graus} da horizontal")
    elif papel is LONGARINA:
        if angulo <= ANGULO_INCLINADA:
            return Avaliacao(True, f"longarina em nível ({graus}): é a viga do patamar?")
    elif papel in (PISO, PATAMAR):
        if angulo > ANGULO_PISO_MAXIMO:
            return Avaliacao(False, f"a chapa está a {graus} da horizontal (em pé)")
        if angulo > ANGULO_INCLINADA:
            return Avaliacao(True, f"rampa ({graus} com a horizontal)")
    elif papel is LANCE:
        if angulo <= ANGULO_INCLINADA:
            return Avaliacao(False, f"a chapa está em nível ({graus})")
        if angulo > ANGULO_PISO_MAXIMO:
            return Avaliacao(False, f"a chapa está a {graus} da horizontal (em pé)")
    return Avaliacao(True)


def problema_do_nome(nome: str) -> str:
    """O que impede ``nome`` de ser um nome novo no padrão; vazio se está bom."""
    texto = str(nome).strip()
    if not texto:
        return "nome vazio"
    if len(texto) > TAMANHO_MAXIMO:
        return f"mais de {TAMANHO_MAXIMO} caracteres"
    if not _PERMITIDO.match(texto):
        return (
            "use só letras sem acento, números, hífen, ponto e sublinhado (sem espaço, aspas, "
            "parênteses, colchetes, @ ou ponto e vírgula)"
        )
    if _pelo_codigo(texto) is None:
        prefixos = ", ".join(p.prefixo for p in PAPEIS)
        return f"comece pelo prefixo do papel e um hífen ({prefixos})"
    return ""


# ---------------------------------------------------------------------------------------------
# As trocas de nome guardadas no projeto
# ---------------------------------------------------------------------------------------------
Ponto3 = tuple[float, float, float]
DISTANCIA_DA_TROCA_M = 0.05  # o corpo não se mexeu desde a troca: o meio dele está a até 5 cm
FOLGA_DO_COMPRIMENTO = 0.02


@dataclass(frozen=True)
class Renomeacao:
    """Um corpo que mudou de nome pela página Nomes das barras, com onde ele estava."""

    antigo: str
    novo: str
    centro: Ponto3  # m: o meio da linha de centro no esqueleto de quando o nome foi trocado
    comprimento_m: float
    quando: str = ""
    #: Confirmada pelo relatório da macro (``_nomes_aplicados.csv``) ou só pedida pela página.
    confirmada: bool = False

    def confere(self, inicio: Sequence[float], fim: Sequence[float], comprimento_m: float) -> bool:
        """O corpo de pontas ``inicio``/``fim`` é o mesmo de quando o nome foi trocado?"""
        meio = [(float(a) + float(b)) / 2 for a, b in zip(inicio, fim, strict=True)]
        if math.dist(meio, self.centro) > DISTANCIA_DA_TROCA_M:
            return False
        return abs(comprimento_m - self.comprimento_m) <= max(
            0.01, FOLGA_DO_COMPRIMENTO * self.comprimento_m
        )


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def renomeacao_para_dicionario(r: Renomeacao) -> dict[str, Any]:
    return {
        "antigo": r.antigo,
        "novo": r.novo,
        "centro": [round(v, 4) for v in r.centro],
        "comprimento_m": round(r.comprimento_m, 4),
        "quando": r.quando,
        "confirmada": r.confirmada,
    }


def renomeacoes_de_lista(valor: Any) -> tuple[Renomeacao, ...]:
    """As trocas gravadas; linha fora do formato é pulada."""
    saida: list[Renomeacao] = []
    for item in valor if isinstance(valor, list | tuple) else ():
        if not isinstance(item, Mapping):
            continue
        antigo, novo = item.get("antigo"), item.get("novo")
        centro = item.get("centro")
        comprimento = _numero(item.get("comprimento_m"))
        if not (isinstance(antigo, str) and isinstance(novo, str) and antigo and novo):
            continue
        if antigo == novo or comprimento is None or comprimento <= 0:
            continue
        if not isinstance(centro, list | tuple) or len(centro) != 3:
            continue
        numeros = [_numero(v) for v in centro]
        if any(n is None for n in numeros):
            continue
        saida.append(
            Renomeacao(
                antigo,
                novo,
                (numeros[0] or 0.0, numeros[1] or 0.0, numeros[2] or 0.0),
                comprimento,
                str(item.get("quando") or ""),
                bool(item.get("confirmada")),
            )
        )
    return tuple(saida)


def dados_do_projeto(projeto: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """O que a página Nomes das barras grava no projeto (vazio se nada)."""
    if not isinstance(projeto, Mapping):
        return {}
    dados = projeto.get(CHAVE_DO_PROJETO)
    return dados if isinstance(dados, Mapping) else {}


def renomeacoes_do_projeto(projeto: Mapping[str, Any] | None) -> tuple[Renomeacao, ...]:
    return renomeacoes_de_lista(dados_do_projeto(projeto).get("renomeacoes"))


def nomes_equivalentes(
    nome: str, renomeacoes: Sequence[Renomeacao]
) -> list[tuple[str, Renomeacao]]:
    """Os outros nomes que o mesmo corpo teve, pelas trocas (nos dois sentidos, em cadeia), com a
    troca que chegou a cada um — a mais recente primeiro."""
    vistos = {nome}
    fila = [nome]
    saida: list[tuple[str, Renomeacao]] = []
    ordenadas = sorted(renomeacoes, key=lambda r: r.quando, reverse=True)
    while fila:
        atual = fila.pop(0)
        for r in ordenadas:
            for de, para in ((r.antigo, r.novo), (r.novo, r.antigo)):
                if de == atual and para not in vistos:
                    vistos.add(para)
                    fila.append(para)
                    saida.append((para, r))
    return saida
