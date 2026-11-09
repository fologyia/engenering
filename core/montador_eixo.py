"""Eixo com trechos no Montador: vários diâmetros, ombros, rasgos e canais, numa conta só.

O arranjo vem em duas tabelas: os trechos, da esquerda para a direita, cada um com o diâmetro como
múltiplo de ``d``, e os elementos, com mancais, engrenagens, polias e o lugar por onde entra o
torque. As posições e as relações são números; as forças e o ``d`` ficam em letra. Assim a conta
acha o ``d`` que faz o eixo inteiro passar e diz em qual seção ele quebraria primeiro.

Por que isso fecha em letra: com todos os diâmetros proporcionais a ``d``, a rigidez é E·π·(k·d)⁴/64.
A inclinação sai como (64/(π·E·d⁴)) vezes uma integral que só depende do arranjo, e o momento em
cada seção é uma soma das forças com pesos que também só dependem dele. Esses pesos são calculados
uma vez por arranjo, com a integração exata de M/k⁴ trecho a trecho.

Seções conferidas: o ombro do lado fino, onde o raio de concordância concentra a tensão, e o
entalhe de cada trecho onde há carga. Entre dois pontos de carga o momento em cada plano é uma reta
e o torque é constante: o pior de cada trecho fica sempre num desses pontos. Fadiga e escoamento no
primeiro ciclo em cada seção, como em Shigley, exemplo 7-2.

Sem Streamlit.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import sympy as sp

from core import elementos_eixos as ee
from core import fatigue as ft
from core import montador_blocos as mb
from core import montador_grandezas as g
from core.montador_blocos import (
    CONDICAO,
    GRUPO_PECAS,
    MATERIAL,
    VALOR,
    Bloco,
    Condicao,
    Contexto,
    ErroDeBloco,
    Opcao,
    Porta,
)
from core.montador_funcoes import (
    MATERIAIS_DE_FADIGA,
    FatorSuperficie,
    FatorTamanho,
    LimiteBase,
    SensibilidadeNeuber,
)
from core.montador_grandezas import Grandeza

TIPO = "eixo_trechos"

MANCAL_A = "Mancal A"
MANCAL_B = "Mancal B"
CARGA = "Carga"
FUNCOES = (MANCAL_A, MANCAL_B, CARGA)
MAIS = "+"
MENOS = "−"
NENHUMA = "—"
SENTIDOS = (MAIS, MENOS, NENHUMA)
ENTRA = "Entra"
SAI = "Sai"
TORQUES = (ENTRA, SAI, NENHUMA)
LISO = ee.ENTALHE_LISO
#: O ressalto entra sozinho nas bordas entre trechos de diâmetros diferentes.
ENTALHES_DO_TRECHO = (
    ee.ENTALHE_LISO,
    ee.ENTALHE_CHAVETA,
    ee.ENTALHE_ANEL,
    ee.ENTALHE_FURO,
    ee.ENTALHE_PRENSADO,
)
_CURTO = {
    ee.ENTALHE_LISO: "liso",
    ee.ENTALHE_CHAVETA: "rasgo de chaveta",
    ee.ENTALHE_ANEL: "canal de anel",
    ee.ENTALHE_FURO: "furo transversal",
    ee.ENTALHE_PRENSADO: "cubo prensado",
    ee.ENTALHE_RESSALTO: "ressalto",
}
NAO_CONFERIR = "Não conferir"
MANCAIS = (*ee.INCLINACAO_MANCAL, NAO_CONFERIR)
CONFERIR = "Conferir"
INCLINACAO_DA_ENGRENAGEM = 0.0005  # rad, engrenagem reta sem abaulamento (Shigley, Tabela 7-2)
_CELULAS = 120  # pedaços do eixo para a massa dele na rotação crítica
_LADO = 1e-9  # um pouco à esquerda ou à direita de um ponto, em fração do comprimento

TRECHOS_PADRAO: tuple[dict[str, Any], ...] = (
    {
        "nome": "Assento do mancal A",
        "comprimento": 30.0,
        "relacao": 1.0,
        "entalhe": LISO,
        "raio": 0.02,
    },
    {
        "nome": "Assento da engrenagem",
        "comprimento": 60.0,
        "relacao": 1.2,
        "entalhe": ee.ENTALHE_CHAVETA,
        "raio": 0.05,
    },
    {"nome": "Encosto", "comprimento": 15.0, "relacao": 1.4, "entalhe": LISO, "raio": 0.05},
    {"nome": "Corpo", "comprimento": 135.0, "relacao": 1.2, "entalhe": LISO, "raio": 0.02},
    {
        "nome": "Assento do mancal B",
        "comprimento": 30.0,
        "relacao": 1.0,
        "entalhe": LISO,
        "raio": 0.02,
    },
    {
        "nome": "Ponta do acoplamento",
        "comprimento": 40.0,
        "relacao": 0.9,
        "entalhe": ee.ENTALHE_CHAVETA,
        "raio": 0.02,
    },
)
ELEMENTOS_PADRAO: tuple[dict[str, Any], ...] = (
    {"nome": "Mancal A", "x": 15.0, "funcao": MANCAL_A},
    {
        "nome": "Engrenagem",
        "x": 60.0,
        "funcao": CARGA,
        "vertical": MAIS,
        "horizontal": MAIS,
        "torque": SAI,
        "massa": 3.0,
        "engrenagem": True,
    },
    {"nome": "Mancal B", "x": 255.0, "funcao": MANCAL_B},
    {"nome": "Acoplamento", "x": 290.0, "funcao": CARGA, "torque": ENTRA, "massa": 1.0},
)


# ---------------------------------------------------------------------------
# Arranjo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Trecho:
    nome: str
    comprimento: float  # mm
    relacao: float  # diâmetro do trecho dividido por d
    entalhe: str
    raio: float  # raio de concordância no fim do trecho, dividido pelo diâmetro menor


@dataclass(frozen=True)
class Elemento:
    nome: str
    x: float  # mm, da ponta esquerda
    funcao: str
    vertical: str = NENHUMA
    horizontal: str = NENHUMA
    torque: str = NENHUMA
    axial: bool = False
    raio: float = 0.0  # mm, onde a força axial age: dá o binário F_a·r no plano vertical
    binario: str = MAIS
    massa: float = 0.0  # kg
    engrenagem: bool = False  # confere a inclinação ali


@dataclass(frozen=True)
class Arranjo:
    trechos: tuple[Trecho, ...]
    elementos: tuple[Elemento, ...]

    @property
    def comprimento(self) -> float:
        return sum(t.comprimento for t in self.trechos)

    def bordas(self) -> list[tuple[float, float]]:
        inicio, saida = 0.0, []
        for t in self.trechos:
            saida.append((inicio, inicio + t.comprimento))
            inicio += t.comprimento
        return saida

    @property
    def cargas(self) -> tuple[Elemento, ...]:
        return tuple(e for e in self.elementos if e.funcao == CARGA)

    def mancal(self, funcao: str) -> Elemento | None:
        return next((e for e in self.elementos if e.funcao == funcao), None)


def _numero(valor: Any, padrao: float = 0.0) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) else padrao


def _lista(bruto: Any, padrao: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if bruto is None:
        return [dict(x) for x in padrao]
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto)
        except ValueError:
            return []
    if not isinstance(bruto, list):
        return []
    return [x for x in bruto if isinstance(x, Mapping)]


def _escolha(valor: Any, opcoes: Sequence[str], padrao: str) -> str:
    return valor if valor in opcoes else padrao


def ler_arranjo(opcoes: Mapping[str, Any]) -> Arranjo:
    """Do que fica guardado no bloco. Linha ruim vira o padrão de cada campo, e não um erro."""
    trechos = []
    for i, linha in enumerate(_lista(opcoes.get("trechos"), TRECHOS_PADRAO), start=1):
        trechos.append(
            Trecho(
                str(linha.get("nome") or f"Trecho {i}"),
                _numero(linha.get("comprimento")),
                _numero(linha.get("relacao"), 1.0),
                _escolha(linha.get("entalhe"), ENTALHES_DO_TRECHO, LISO),
                max(_numero(linha.get("raio"), 0.02), 0.0),
            )
        )
    elementos = []
    for i, linha in enumerate(_lista(opcoes.get("elementos"), ELEMENTOS_PADRAO), start=1):
        elementos.append(
            Elemento(
                str(linha.get("nome") or f"Elemento {i}"),
                _numero(linha.get("x")),
                _escolha(linha.get("funcao"), FUNCOES, CARGA),
                _escolha(linha.get("vertical"), SENTIDOS, NENHUMA),
                _escolha(linha.get("horizontal"), SENTIDOS, NENHUMA),
                _escolha(linha.get("torque"), TORQUES, NENHUMA),
                bool(linha.get("axial")),
                max(_numero(linha.get("raio")), 0.0),
                _escolha(linha.get("binario"), (MAIS, MENOS), MAIS),
                max(_numero(linha.get("massa")), 0.0),
                bool(linha.get("engrenagem")),
            )
        )
    return Arranjo(tuple(trechos), tuple(elementos))


def problemas(arranjo: Arranjo) -> list[str]:
    """O que impede a conta, em palavras de quem preencheu as tabelas."""
    erros = []
    if not arranjo.trechos:
        erros.append("Ponha ao menos um trecho no eixo.")
    if any(t.comprimento <= 0 for t in arranjo.trechos):
        erros.append("Todo trecho precisa de comprimento maior que zero.")
    if any(t.relacao <= 0 for t in arranjo.trechos):
        erros.append("A relação do diâmetro de cada trecho com d precisa ser maior que zero.")
    for funcao in (MANCAL_A, MANCAL_B):
        quantos = sum(e.funcao == funcao for e in arranjo.elementos)
        if quantos != 1:
            erros.append(f"O eixo precisa de um {funcao.lower()}, e só um: há {quantos}.")
    a, b = arranjo.mancal(MANCAL_A), arranjo.mancal(MANCAL_B)
    if a is not None and b is not None and abs(a.x - b.x) <= 1e-9:
        erros.append("Os dois mancais estão no mesmo lugar.")
    total = arranjo.comprimento
    fora = [e.nome for e in arranjo.elementos if not 0.0 <= e.x <= total + 1e-9]
    if fora:
        erros.append(f"Fora do eixo, que tem {total:g} mm: {', '.join(fora)}.")
    entradas = [e for e in arranjo.cargas if e.torque == ENTRA]
    saidas = [e for e in arranjo.cargas if e.torque == SAI]
    if len(entradas) > 1:
        erros.append(
            "Só um elemento pode ter o torque entrando: com duas entradas, o torque em cada trecho "
            "depende do sinal de cada uma."
        )
    if saidas and not entradas:
        erros.append("Diga por onde o torque entra: marque Entra em um elemento.")
    if entradas and not saidas:
        erros.append("O torque entra e não sai: marque Sai nos elementos que recebem o torque.")
    return erros


# ---------------------------------------------------------------------------
# A viga de cada carga unitária
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Unitaria:
    """Uma força ou um binário unitário num ponto: o que ele faz em cada nó do eixo."""

    esquerda: np.ndarray  # momento logo antes de cada nó
    direita: np.ndarray  # momento logo depois
    giro: np.ndarray  # inclinação reduzida: vezes 64/(π·E·d⁴) dá a de verdade
    flecha: np.ndarray
    reacao_a: float
    reacao_b: float


def _viga(
    nos: np.ndarray,
    pesos: np.ndarray,
    xa: float,
    xb: float,
    posicao: float,
    binario: bool,
) -> Unitaria:
    """Integração exata de M/k⁴: em cada intervalo o momento é uma reta e o diâmetro, um só."""
    vao = xb - xa
    forcas: tuple[tuple[float, float], ...]
    if binario:
        rb = -1.0 / vao
        ra = -rb
        forcas = ((xa, ra), (xb, rb))
    else:
        rb = -(posicao - xa) / vao
        ra = -1.0 - rb
        forcas = ((posicao, 1.0), (xa, ra), (xb, rb))

    def momento(x: np.ndarray, incluir_o_ponto: np.ndarray) -> np.ndarray:
        total = np.zeros_like(x)
        for xp, f in forcas:
            total = total + np.where(xp <= x, f * (x - xp), 0.0)
        if binario:
            total = total + np.where(incluir_o_ponto, 1.0, 0.0)
        return total

    depois = momento(nos, posicao <= nos)
    antes = momento(nos, posicao < nos)
    h = np.diff(nos)
    ka = depois[:-1] * pesos
    kb = antes[1:] * pesos
    giro = np.concatenate(([0.0], np.cumsum((ka + kb) / 2.0 * h)))
    passo = giro[:-1] * h + ka * h**2 / 2.0 + (kb - ka) * h**2 / 6.0
    flecha = np.concatenate(([0.0], np.cumsum(passo)))
    ya = float(np.interp(xa, nos, flecha))
    yb = float(np.interp(xb, nos, flecha))
    inclinacao = (yb - ya) / vao
    return Unitaria(
        antes,
        depois,
        giro - inclinacao,
        flecha - ya - inclinacao * (nos - xa),
        ra,
        rb,
    )


@dataclass(frozen=True)
class Analise:
    nos: np.ndarray
    forcas: tuple[Unitaria, ...]  # uma por carga, na ordem de ``Arranjo.cargas``
    binarios: tuple[Unitaria | None, ...]
    massa_do_eixo: float  # Σ k²·Δx·|y| das células: vezes 16·ρ/(E·d²) dá a parcela do eixo em 1/ω²
    massa_das_pecas: float  # Σ m·|y| das peças, em t·mm³: vezes 64/(π·E·d⁴)


def relacao_em(arranjo: Arranjo, x: float) -> float:
    for (x0, x1), trecho in zip(arranjo.bordas(), arranjo.trechos, strict=True):
        if x0 <= x <= x1:
            return trecho.relacao
    return arranjo.trechos[-1].relacao


@lru_cache(maxsize=64)
def analisar(arranjo: Arranjo) -> Analise:
    """Os pesos de cada força no momento, na inclinação e na flecha. Só depende do arranjo."""
    xa = arranjo.mancal(MANCAL_A).x  # type: ignore[union-attr]
    xb = arranjo.mancal(MANCAL_B).x  # type: ignore[union-attr]
    total = arranjo.comprimento
    celulas: list[tuple[float, float, float]] = []  # centro, largura e k
    for (x0, x1), trecho in zip(arranjo.bordas(), arranjo.trechos, strict=True):
        partes = max(1, round(_CELULAS * (x1 - x0) / total))
        largura = (x1 - x0) / partes
        celulas += [(x0 + (i + 0.5) * largura, largura, trecho.relacao) for i in range(partes)]
    pontos = {0.0, total, xa, xb, *(e.x for e in arranjo.elementos)}
    pontos |= {x1 for _, x1 in arranjo.bordas()}
    pontos |= {c[0] for c in celulas}
    nos = np.array(sorted(pontos))
    meios = (nos[:-1] + nos[1:]) / 2.0
    pesos = np.array([relacao_em(arranjo, float(x)) ** -4 for x in meios])
    forcas = tuple(_viga(nos, pesos, xa, xb, e.x, False) for e in arranjo.cargas)
    binarios = tuple(
        _viga(nos, pesos, xa, xb, e.x, True) if e.axial and e.raio > 0 else None
        for e in arranjo.cargas
    )

    def propria(x: float) -> float:
        i = int(np.searchsorted(nos, x))
        return abs(float(_viga(nos, pesos, xa, xb, x, False).flecha[i]))

    massa_do_eixo = sum(k**2 * largura * propria(centro) for centro, largura, k in celulas)
    massa_das_pecas = sum(
        e.massa * 1e-3 * abs(float(f.flecha[int(np.searchsorted(nos, e.x))]))
        for e, f in zip(arranjo.cargas, forcas, strict=True)
        if e.massa > 0
    )
    return Analise(nos, forcas, binarios, massa_do_eixo, massa_das_pecas)


# ---------------------------------------------------------------------------
# Seções conferidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Secao:
    rotulo: str  # S1, S2...
    x: float
    lado: int  # −1 logo antes do ponto, +1 logo depois
    trecho: int
    relacao: float
    entalhe: str
    maior: float = 0.0  # no ressalto: a relação do trecho grosso
    raio: float = 0.0  # no ressalto: r dividido pelo diâmetro fino

    @property
    def descricao(self) -> str:
        return _CURTO.get(self.entalhe, self.entalhe)


def secoes(arranjo: Arranjo) -> tuple[Secao, ...]:
    """Ombros do lado fino e o entalhe de cada trecho nos pontos de carga. Sem repetir."""
    bordas = arranjo.bordas()
    posicoes = sorted({e.x for e in arranjo.elementos})
    candidatas: list[Secao] = []
    for i, ((x0, x1), trecho) in enumerate(zip(bordas, arranjo.trechos, strict=True)):
        antes = arranjo.trechos[i - 1] if i > 0 else None
        depois = arranjo.trechos[i + 1] if i + 1 < len(arranjo.trechos) else None
        ombro_no_inicio = antes is not None and antes.relacao > trecho.relacao
        ombro_no_fim = depois is not None and depois.relacao > trecho.relacao
        degrau_no_inicio = antes is not None and antes.relacao < trecho.relacao
        degrau_no_fim = depois is not None and depois.relacao < trecho.relacao
        if ombro_no_inicio and antes is not None:
            candidatas.append(
                Secao("", x0, 1, i, trecho.relacao, ee.ENTALHE_RESSALTO, antes.relacao, antes.raio)
            )
        if ombro_no_fim and depois is not None:
            candidatas.append(
                Secao(
                    "", x1, -1, i, trecho.relacao, ee.ENTALHE_RESSALTO, depois.relacao, trecho.raio
                )
            )
        dentro = [x for x in posicoes if x0 < x < x1]
        pontas: list[tuple[float, int]] = []
        if not ombro_no_inicio and not degrau_no_inicio:
            pontas.append((x0, 1))
        if not ombro_no_fim and not degrau_no_fim:
            pontas.append((x1, -1))
        if trecho.entalhe != LISO and not dentro:
            # Rasgo sem carga dentro: o pior fica numa das pontas, mesmo junto de um ombro.
            pontas = [(x0, 1), (x1, -1)]
        for x in dentro:
            for lado in (-1, 1):
                candidatas.append(Secao("", x, lado, i, trecho.relacao, trecho.entalhe))
        for x, lado in pontas:
            candidatas.append(Secao("", x, lado, i, trecho.relacao, trecho.entalhe))
    vistas: dict[tuple[float, int, int, str], Secao] = {}
    for s in candidatas:
        vistas.setdefault((round(s.x, 9), s.lado, s.trecho, s.entalhe), s)
    return tuple(sorted(vistas.values(), key=lambda s: (s.x, s.lado)))


# ---------------------------------------------------------------------------
# Letras de cada elemento
# ---------------------------------------------------------------------------


def _letra_vertical(k: int, nome: str) -> Grandeza:
    return Grandeza(
        f"F_v{k}",
        f"F_v{k}",
        f"Força vertical em {nome}",
        g.FORCA,
        "Componente no plano vertical.",
        zero_ok=True,
    )


def _letra_horizontal(k: int, nome: str) -> Grandeza:
    return Grandeza(
        f"F_h{k}",
        f"F_h{k}",
        f"Força horizontal em {nome}",
        g.FORCA,
        "Componente no plano horizontal.",
        zero_ok=True,
    )


def _letra_torque(k: int, nome: str) -> Grandeza:
    return Grandeza(
        f"T_e{k}",
        f"T_e{k}",
        f"Torque que sai em {nome}",
        g.MOMENTO,
        "O torque que este elemento leva.",
        zero_ok=True,
    )


def _letra_axial(k: int, nome: str) -> Grandeza:
    return Grandeza(
        f"F_a{k}",
        f"F_a{k}",
        f"Força axial em {nome}",
        g.FORCA,
        "Força ao longo do eixo, que vai até o mancal que a segura.",
        zero_ok=True,
    )


def portas_do_arranjo(arranjo: Arranjo) -> tuple[tuple[Porta, ...], tuple[Porta, ...]]:
    """Uma bolinha por força de cada elemento: a engrenagem pode mandar F_r, F_t e T por fio."""
    entradas: list[Porta] = [Porta("material", "Material", MATERIAL)]
    for k, e in enumerate(arranjo.cargas, start=1):
        if e.vertical != NENHUMA:
            entradas.append(Porta(f"v{k}", f"F_v{k}", VALOR, g.FORCA))
        if e.horizontal != NENHUMA:
            entradas.append(Porta(f"h{k}", f"F_h{k}", VALOR, g.FORCA))
        if e.torque == SAI:
            entradas.append(Porta(f"t{k}", f"T_e{k}", VALOR, g.MOMENTO))
        if e.axial:
            entradas.append(Porta(f"a{k}", f"F_a{k}", VALOR, g.FORCA))
    saidas = (
        Porta("condicao", "Condição", CONDICAO),
        Porta("R_A", "R_A", VALOR, g.FORCA),
        Porta("R_B", "R_B", VALOR, g.FORCA),
    )
    return tuple(entradas), saidas


@lru_cache(maxsize=64)
def _portas_guardadas(trechos: str, elementos: str) -> tuple[tuple[Porta, ...], tuple[Porta, ...]]:
    return portas_do_arranjo(ler_arranjo({"trechos": trechos, "elementos": elementos}))


def portas(opcoes: Mapping[str, Any]) -> tuple[tuple[Porta, ...], tuple[Porta, ...]]:
    return _portas_guardadas(
        json.dumps(_lista(opcoes.get("trechos"), TRECHOS_PADRAO), sort_keys=True),
        json.dumps(_lista(opcoes.get("elementos"), ELEMENTOS_PADRAO), sort_keys=True),
    )


# ---------------------------------------------------------------------------
# A conta
# ---------------------------------------------------------------------------


@dataclass
class _Forcas:
    vertical: list[tuple[int, sp.Expr]]  # índice da carga e força já com o sinal
    horizontal: list[tuple[int, sp.Expr]]
    binarios: list[tuple[int, sp.Expr]]
    torques: dict[int, sp.Expr]
    axiais: dict[int, sp.Expr]


def _forcas(c: Contexto, arranjo: Arranjo) -> _Forcas:
    forcas = _Forcas([], [], [], {}, {})
    for k, e in enumerate(arranjo.cargas, start=1):
        i = k - 1
        if e.vertical != NENHUMA:
            sinal = 1 if e.vertical == MAIS else -1
            forcas.vertical.append((i, sinal * c.letra(_letra_vertical(k, e.nome), f"v{k}")))
        if e.horizontal != NENHUMA:
            sinal = 1 if e.horizontal == MAIS else -1
            forcas.horizontal.append((i, sinal * c.letra(_letra_horizontal(k, e.nome), f"h{k}")))
        if e.torque == SAI:
            forcas.torques[i] = c.letra(_letra_torque(k, e.nome), f"t{k}")
        if e.axial:
            axial = c.letra(_letra_axial(k, e.nome), f"a{k}")
            forcas.axiais[i] = axial
            if e.raio > 0:
                sinal = 1 if e.binario == MAIS else -1
                forcas.binarios.append((i, sinal * axial * sp.Float(e.raio)))
    return forcas


def _no(analise: Analise, x: float) -> int:
    return int(np.argmin(np.abs(analise.nos - x)))


def _momento_no_plano(
    analise: Analise, termos: Sequence[tuple[int, sp.Expr]], binarios: bool, i: int, lado: int
) -> sp.Expr:
    total = sp.S.Zero
    for indice, forca in termos:
        unitaria = analise.binarios[indice] if binarios else analise.forcas[indice]
        if unitaria is None:
            continue
        valor = float((unitaria.direita if lado > 0 else unitaria.esquerda)[i])
        if abs(valor) > 1e-12:
            total += forca * sp.Float(valor, 12)
    return total


def _giro_no_plano(
    analise: Analise, termos: Sequence[tuple[int, sp.Expr]], binarios: bool, i: int
) -> sp.Expr:
    total = sp.S.Zero
    for indice, forca in termos:
        unitaria = analise.binarios[indice] if binarios else analise.forcas[indice]
        if unitaria is not None and abs(float(unitaria.giro[i])) > 1e-15:
            total += forca * sp.Float(float(unitaria.giro[i]), 12)
    return total


def _entre(x: float, a: float, b: float) -> bool:
    return min(a, b) < x < max(a, b)


def _torque_em(arranjo: Arranjo, forcas: _Forcas, x: float) -> sp.Expr:
    entrada = next((e for e in arranjo.cargas if e.torque == ENTRA), None)
    if entrada is None:
        return sp.S.Zero
    return sum(
        (t for i, t in forcas.torques.items() if _entre(x, entrada.x, arranjo.cargas[i].x)),
        sp.S.Zero,
    )


def _axial_em(arranjo: Arranjo, forcas: _Forcas, x: float, encosto: float) -> sp.Expr:
    return sum(
        (f for i, f in forcas.axiais.items() if _entre(x, arranjo.cargas[i].x, encosto)),
        sp.S.Zero,
    )


def _entalhe(
    secao: Secao, sut: sp.Expr, diametro: sp.Expr
) -> tuple[sp.Expr, sp.Expr, sp.Expr, tuple[float, float, float]]:
    """K_f na flexão, na torção e no normal, com os K_t para a tabela."""
    if secao.entalhe == ee.ENTALHE_RESSALTO:
        relacao_d = secao.maior / secao.relacao
        raio = max(secao.raio, 1e-3)
        kt = tuple(
            ee.kt_ressalto(relacao_d, 1.0, raio, carga) for carga in ("flexao", "torcao", "axial")
        )
        raio_real = raio * diametro
        q = SensibilidadeNeuber(sut, raio_real, 0)
        qs = SensibilidadeNeuber(sut, raio_real, 1)
    else:
        kt = ee.KT_FIXOS[secao.entalhe]
        if secao.entalhe == ee.ENTALHE_CHAVETA:
            q = SensibilidadeNeuber(sut, diametro / 50, 0)
            qs = SensibilidadeNeuber(sut, diametro / 50, 1)
        else:
            q = qs = sp.S.One  # lado seguro: sem raio definido, não há sensibilidade
    flexao, torcao, axial = (sp.Float(k) for k in kt)
    return (
        1 + q * (flexao - 1),
        1 + qs * (torcao - 1),
        1 + q * (axial - 1),
        (float(kt[0]), float(kt[1]), float(kt[2])),
    )


@dataclass(frozen=True)
class Conferida:
    """O que a tela mostra de uma seção, além das condições."""

    secao: Secao
    momento: sp.Expr
    torque: sp.Expr
    normal: sp.Expr
    kt: tuple[float, float, float]


def _minuscula(texto: str) -> str:
    """Só a primeira letra: o nome do trecho pode ter "mancal A", e o A fica."""
    return texto[:1].lower() + texto[1:]


def _categoria(c: Contexto) -> str:
    achada = next(
        (m.split(":", 1)[1] for m in c.marcas if m.startswith("categoria:")),
        MATERIAIS_DE_FADIGA[0],
    )
    return achada if achada in MATERIAIS_DE_FADIGA else MATERIAIS_DE_FADIGA[0]


def _calcular(c: Contexto) -> dict[str, Any]:
    arranjo = ler_arranjo(c.opcoes)
    erros = problemas(arranjo)
    if erros:
        raise ErroDeBloco(erros[0])
    analise = analisar(arranjo)
    forcas = _forcas(c, arranjo)
    material = c.material()
    sy = material.sy if material else c.letra(g.SY)
    sut = material.sut if material else c.letra(g.SUT)
    e = material.e if material else c.letra(g.E)
    d = c.letra(g.D)
    n = c.letra(g.FS)
    xa = arranjo.mancal(MANCAL_A).x  # type: ignore[union-attr]
    xb = arranjo.mancal(MANCAL_B).x  # type: ignore[union-attr]
    encosto = xa if c.opcoes.get("encosto", MANCAL_A) == MANCAL_A else xb

    # S_e de cada seção, com o k_b do diâmetro dela: o fator de tamanho muda de trecho para trecho.
    categoria = _categoria(c)
    a, b = ft.COEFICIENTES_SUPERFICIE[
        ee.ACABAMENTOS[c.opcoes.get("acabamento", mb.ACABAMENTO_PADRAO)]
    ]
    ka = sp.S.One if categoria == "ferro_fundido" else FatorSuperficie(sut, a, b)
    confianca = c.opcoes.get("confiabilidade", mb.CONFIABILIDADE_PADRAO)
    c.padrao(
        g.K_CONFIANCA,
        ft.fator_confiabilidade(ee.CONFIABILIDADES.get(confianca, 50)),
        f"Tabela: confiabilidade de {confianca}",
    )
    fatores = c.letra(g.K_TEMPERATURA) * c.letra(g.K_CONFIANCA) * c.letra(g.K_DIVERSOS)
    base = LimiteBase(sut, MATERIAIS_DE_FADIGA.index(categoria))
    criterio = c.opcoes.get("criterio", mb.GOODMAN)
    curto = criterio.removeprefix("DE-").removeprefix("ASME ")

    condicoes: list[Condicao] = []
    conferidas: list[Conferida] = []
    contas_feitas: set[tuple[sp.Expr, sp.Expr]] = set()
    for s in secoes(arranjo):
        i = _no(analise, s.x)
        x = s.x + s.lado * _LADO * arranjo.comprimento
        vertical = _momento_no_plano(analise, forcas.vertical, False, i, s.lado)
        horizontal = _momento_no_plano(analise, forcas.horizontal, False, i, s.lado)
        binario = _momento_no_plano(analise, forcas.binarios, True, i, s.lado)
        momento = sp.sqrt((vertical + binario) ** 2 + horizontal**2)
        torque = _torque_em(arranjo, forcas, x)
        normal = _axial_em(arranjo, forcas, x, encosto)
        if momento == 0 and torque == 0 and normal == 0:
            continue
        diametro = s.relacao * d
        kf, kfs, kf_axial, kt = _entalhe(s, sut, diametro)
        assinatura = (sp.expand(momento**2), sp.expand(torque + normal + kf + kfs + diametro))
        if assinatura in contas_feitas:
            continue  # a mesma conta em outro ponto, como os dois lados de um mancal sem balanço
        contas_feitas.add(assinatura)
        s = Secao(
            f"S{len(conferidas) + 1}", s.x, s.lado, s.trecho, s.relacao, s.entalhe, s.maior, s.raio
        )
        alternada = kf * 32 * momento / (sp.pi * diametro**3)
        normal_media = kf_axial * 4 * normal / (sp.pi * diametro**2)
        tau = kfs * 16 * torque / (sp.pi * diametro**3)
        media = sp.sqrt(normal_media**2 + 3 * tau**2)
        resistencia = base * ka * FatorTamanho(diametro) * fatores
        esquerda, direita, letra = mb._criterio_de_fadiga(
            criterio, alternada, media, resistencia, c
        )
        onde = f"{s.rotulo} ({_minuscula(arranjo.trechos[s.trecho].nome)}, {s.descricao})"
        condicoes.append(
            Condicao(
                f"Fadiga ({curto}) em {onde}",
                curto.capitalize(),
                esquerda,
                direita,
                letra,
                s.rotulo,
                (("\\sigma_{a}'", alternada), ("\\sigma_{m}'", media)),
            )
        )
        maxima = sp.sqrt((alternada + normal_media) ** 2 + 3 * tau**2)
        condicoes.append(
            Condicao(
                f"Escoamento em {onde}",
                "Escoamento",
                maxima,
                sy / n,
                "\\sigma_{max}'",
                s.rotulo,
                (("\\sigma_{max}'", maxima),),
            )
        )
        conferidas.append(Conferida(s, momento, torque, normal, kt))

    reduzida = 64 / (sp.pi * e * d**4)
    pontos_de_giro: list[tuple[str, float, float]] = []
    for funcao, opcao in ((MANCAL_A, "mancal_a"), (MANCAL_B, "mancal_b")):
        tipo = c.opcoes.get(opcao, next(iter(ee.INCLINACAO_MANCAL)))
        if tipo in ee.INCLINACAO_MANCAL:
            pontos_de_giro.append(
                (
                    f"Inclinação no {funcao[0].lower()}{funcao[1:]}",
                    xa if funcao == MANCAL_A else xb,
                    ee.INCLINACAO_MANCAL[tipo],
                )
            )
    for elemento in arranjo.cargas:
        if elemento.engrenagem:
            pontos_de_giro.append(
                (f"Inclinação em {_minuscula(elemento.nome)}", elemento.x, INCLINACAO_DA_ENGRENAGEM)
            )
    for nome, x, limite in pontos_de_giro:
        i = _no(analise, x)
        vertical = _giro_no_plano(analise, forcas.vertical, False, i) + _giro_no_plano(
            analise, forcas.binarios, True, i
        )
        horizontal = _giro_no_plano(analise, forcas.horizontal, False, i)
        giro = reduzida * sp.sqrt(vertical**2 + horizontal**2)
        if giro != 0:
            condicoes.append(Condicao(nome, "Inclinação", giro, sp.Float(limite), "\\theta"))

    if c.opcoes.get("critica", CONFERIR) == CONFERIR:
        densidade = c.letra(g.RHO_EIXO, fixa=True)
        inverso = 16 * densidade * sp.Float(analise.massa_do_eixo, 12) / (e * d**2)
        if analise.massa_das_pecas > 0:
            inverso += 64 * sp.Float(analise.massa_das_pecas, 12) / (sp.pi * e * d**4)
        critica = 30 / (sp.pi * sp.sqrt(inverso))
        condicoes.append(
            Condicao(
                "Rotação crítica do eixo",
                "Rotação crítica",
                c.letra(g.F_CRITICA, fixa=True) * c.letra(g.ROT, fixa=True),
                critica,
                "f_{cr} \\cdot n",
                "",
                (("n_{cr}", critica),),
            )
        )

    reacoes: dict[str, sp.Expr] = {}
    for chave, campo in (("R_A", "reacao_a"), ("R_B", "reacao_b")):
        vertical = sum(
            (f * sp.Float(getattr(analise.forcas[i], campo), 12) for i, f in forcas.vertical),
            sp.S.Zero,
        ) + sum(
            (
                f * sp.Float(getattr(analise.binarios[i], campo), 12)
                for i, f in forcas.binarios
                if analise.binarios[i] is not None
            ),
            sp.S.Zero,
        )
        horizontal = sum(
            (f * sp.Float(getattr(analise.forcas[i], campo), 12) for i, f in forcas.horizontal),
            sp.S.Zero,
        )
        reacoes[chave] = sp.sqrt(vertical**2 + horizontal**2)

    if not condicoes:
        raise ErroDeBloco("Ponha ao menos uma força ou um torque num elemento.")
    c.hipoteses += [
        "Eixo com trechos: momentos nos dois planos somados como vetores, porque o eixo gira e "
        "cada fibra passa pelo pior lado. Flexão alternada por inteiro e torque constante.",
        "Mancais como apoios simples nas posições da tabela. A força axial vai até o mancal que "
        "a segura, e o binário F_a·r fica no plano vertical, com o sentido da tabela.",
        "K_t do ressalto pelas curvas de Peterson (Norton, apêndice E), com D/d e r/d da tabela; "
        "q de Neuber pelo raio de verdade. Rasgo de chaveta com r = d/50; anel, furo e cubo "
        "prensado com q = 1, a favor.",
        "S_e pelos fatores de Marin de cada seção: o k_b muda com o diâmetro do trecho.",
        "Inclinação pela integração de M/(E·I) trecho a trecho, com os limites da Tabela 7-2 de "
        "Shigley. Rotação crítica por Dunkerley com a massa do eixo e das peças: fica abaixo da "
        "real, a favor.",
    ]
    if forcas.axiais:
        c.hipoteses.append(
            "Na força axial o K_f é o do normal, e a tensão entra inteira na parcela média."
        )
    torques = [e for e in arranjo.cargas if e.torque == SAI]
    if torques:
        c.hipoteses.append(
            "O torque que entra é a soma dos que saem: no trecho entre a entrada e cada saída "
            "passa o torque dessa saída."
        )
    c.marcas.add("ductil")
    return {"condicao": condicoes, **reacoes, "secoes": tuple(conferidas)}


_BLOCO = Bloco(
    TIPO,
    "Eixo com trechos",
    GRUPO_PECAS,
    "O eixo inteiro: vários diâmetros, ombros, rasgos, mancais e engrenagens. As tabelas ficam "
    "logo abaixo da prancheta.",
    "d_i = k_i·d · σ_a'/S_e + σ_m'/S_ut ≤ 1/n",
    *portas({}),
    _calcular,
    (
        Opcao(
            "criterio",
            "Critério de fadiga",
            "Goodman é o usual e fica a favor da segurança. Gerber segue melhor os ensaios. "
            "Soderberg e ASME elíptico usam S_y no lugar de S_ut.",
            mb.CRITERIOS_DE_FADIGA,
            mb.GOODMAN,
        ),
        Opcao(
            "acabamento",
            "Acabamento",
            "Superfície mais grossa rende menos em fadiga. Dá o k_a de todas as seções.",
            tuple(ee.ACABAMENTOS),
            mb.ACABAMENTO_PADRAO,
        ),
        Opcao(
            "confiabilidade",
            "Confiabilidade",
            "Dá o k_e. 50 % é o valor médio do ensaio; projeto costuma pedir de 90 a 99 %.",
            tuple(ee.CONFIABILIDADES),
            mb.CONFIABILIDADE_PADRAO,
        ),
        Opcao(
            "mancal_a",
            "Rolamento do mancal A",
            "Dá a inclinação que o mancal aceita. Não conferir tira a condição.",
            MANCAIS,
            next(iter(ee.INCLINACAO_MANCAL)),
        ),
        Opcao(
            "mancal_b",
            "Rolamento do mancal B",
            "Dá a inclinação que o mancal aceita. Não conferir tira a condição.",
            MANCAIS,
            next(iter(ee.INCLINACAO_MANCAL)),
        ),
        Opcao(
            "encosto",
            "Mancal que segura a força axial",
            "A força axial passa pelo eixo até este mancal: só os trechos entre a peça e ele "
            "ficam com o normal.",
            (MANCAL_A, MANCAL_B),
            MANCAL_A,
        ),
        Opcao(
            "critica",
            "Rotação crítica",
            "Confere se a rotação de trabalho fica longe da rotação crítica, com a massa do eixo "
            "e das peças da tabela.",
            (CONFERIR, NAO_CONFERIR),
            CONFERIR,
        ),
    ),
    numerar=True,
)

mb.registrar((_BLOCO,))
mb.PORTAS_VARIAVEIS[TIPO] = portas
