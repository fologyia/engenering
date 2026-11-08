"""O motor do montador de fórmulas: lê os blocos ligados e isola a grandeza escolhida.

``montar`` percorre o desenho na ordem dos fios e devolve as condições "isto ≤ aquilo". ``isolar``
resolve cada uma para a grandeza pedida. Equações que viram polinômio de até grau 2 em x^k saem em
forma fechada; as outras ficam como equação, com a raiz achada por número. A resposta final junta as
condições: quem pede um mínimo manda pelo maior, quem pede um máximo manda pelo menor, e uma igualdade
fixa o valor.

Conjunto é um bloco com outros blocos dentro. ``grafo_de_dados`` abre os conjuntos e devolve só blocos
simples, com o id do conjunto na frente (``c1/n2``): o motor não precisa saber que eles existem.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import lru_cache
from typing import Any

import numpy as np
import sympy as sp

from core import material_catalog as mc
from core import montador_blocos as mb
from core import montador_fluidos as mfl
from core import montador_grandezas as g
from core.montador_blocos import Condicao, Contexto, ErroDeBloco
from core.montador_funcoes import FUNCOES, NUMERICAS
from core.montador_grandezas import Grandeza
from core.montador_secoes import Estado, Validade

MINIMO = "mínimo"
MAXIMO = "máximo"
IGUAL = "igual"
CONJUNTO = "conjunto"
_PROFUNDIDADE_MAXIMA = 8  # conjunto dentro de conjunto: além disso é dado corrompido
_GRADE_LOG = np.logspace(-9.0, 15.0, 961)  # cobre de um tubo em metros a um momento em N·mm
_LIMITE_DE_OPERACOES = 400  # acima disso, simplificar custa mais do que ajuda
_FOLGA = 1e-9
_FOLGA_DA_IGUALDADE = 1e-6


class ErroDeMontagem(ValueError):
    """O desenho ainda não forma uma conta."""


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class No:
    id: str
    tipo: str
    opcoes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Fio:
    de: str
    saida: str
    para: str
    entrada: str


@dataclass(frozen=True)
class Grafo:
    nos: tuple[No, ...]
    fios: tuple[Fio, ...]


def _abrir(
    dados: Mapping[str, Any],
    prefixo: str,
    nos: list[No],
    fios: list[Fio],
    origens: dict[tuple[str, str], tuple[str, str]],
    destinos: dict[tuple[str, str], tuple[str, str]],
    profundidade: int = 0,
) -> None:
    """Junta os blocos simples, e anota por onde cada porta de conjunto entra e sai."""
    if profundidade > _PROFUNDIDADE_MAXIMA:
        return
    for linha in dados.get("nos") or ():
        if not isinstance(linha, Mapping):
            continue
        id_ = f"{prefixo}{linha.get('id')}"
        tipo = linha.get("tipo")
        if tipo == CONJUNTO:
            interno = linha.get("grafo")
            if isinstance(interno, Mapping):
                _abrir(interno, f"{id_}/", nos, fios, origens, destinos, profundidade + 1)
            portas = linha.get("portas") or {}
            for porta in portas.get("entradas") or ():
                destinos[(id_, str(porta.get("chave")))] = (
                    f"{id_}/{porta.get('no')}",
                    str(porta.get("porta")),
                )
            for porta in portas.get("saidas") or ():
                origens[(id_, str(porta.get("chave")))] = (
                    f"{id_}/{porta.get('no')}",
                    str(porta.get("porta")),
                )
        elif tipo in mb.POR_CHAVE:
            opcoes = linha.get("opcoes") or {}
            nos.append(
                No(id_, str(tipo), tuple(sorted((str(k), str(v)) for k, v in opcoes.items())))
            )
    for linha in dados.get("fios") or ():
        if isinstance(linha, Mapping):
            fios.append(
                Fio(
                    f"{prefixo}{linha.get('de')}",
                    str(linha.get("saida")),
                    f"{prefixo}{linha.get('para')}",
                    str(linha.get("entrada")),
                )
            )


def grafo_de_dados(dados: Mapping[str, Any]) -> Grafo:
    """Do formato da prancheta. Bloco desconhecido e fio solto ficam de fora, sem quebrar a tela."""
    nos: list[No] = []
    brutos: list[Fio] = []
    origens: dict[tuple[str, str], tuple[str, str]] = {}
    destinos: dict[tuple[str, str], tuple[str, str]] = {}
    _abrir(dados, "", nos, brutos, origens, destinos)
    por_id = {no.id: no for no in nos}
    fios: list[Fio] = []
    ocupadas: dict[tuple[str, str], int] = {}
    for bruto in brutos:
        de, saida = bruto.de, bruto.saida
        for _ in range(_PROFUNDIDADE_MAXIMA + 1):
            if (de, saida) not in origens:
                break
            de, saida = origens[(de, saida)]
        para, entrada = bruto.para, bruto.entrada
        for _ in range(_PROFUNDIDADE_MAXIMA + 1):
            if (para, entrada) not in destinos:
                break
            para, entrada = destinos[(para, entrada)]
        fio = Fio(de, saida, para, entrada)
        if not _fio_valido(fio, por_id):
            continue
        para_no = por_id[fio.para]
        destino = next(
            p for p in mb.portas_de(para_no.tipo, dict(para_no.opcoes))[0] if p.chave == fio.entrada
        )
        chave = (fio.para, fio.entrada)
        if destino.varias or chave not in ocupadas:
            ocupadas[chave] = len(fios)
            fios.append(fio)
        else:
            fios[ocupadas[chave]] = fio  # porta de um fio só: vale o último
    return Grafo(tuple(nos), tuple(fios))


def resolver_saida(dados: Mapping[str, Any], fio: Mapping[str, Any]) -> tuple[str, str]:
    """De um fio da prancheta para o bloco simples que está por trás dele, dentro dos conjuntos."""
    nos: list[No] = []
    brutos: list[Fio] = []
    origens: dict[tuple[str, str], tuple[str, str]] = {}
    destinos: dict[tuple[str, str], tuple[str, str]] = {}
    _abrir(dados, "", nos, brutos, origens, destinos)
    prefixo = "/".join(str(id_) for id_ in fio.get("caminho") or ())
    de = f"{prefixo}/{fio.get('de')}" if prefixo else str(fio.get("de"))
    saida = str(fio.get("saida"))
    for _ in range(_PROFUNDIDADE_MAXIMA + 1):
        if (de, saida) not in origens:
            break
        de, saida = origens[(de, saida)]
    return de, saida


def _dimensao_da_saida(no: No, porta: mb.Porta) -> str | None:
    """A referência tem a dimensão do resultado escolhido, e não uma fixa."""
    return dict(no.opcoes).get("dimensao") if no.tipo == mb.REFERENCIA else porta.dimensao


def _fio_valido(fio: Fio, por_id: Mapping[str, No]) -> bool:
    if fio.de not in por_id or fio.para not in por_id or fio.de == fio.para:
        return False
    origem = por_id[fio.de]
    destino = por_id[fio.para]
    saida = next(
        (p for p in mb.portas_de(origem.tipo, dict(origem.opcoes))[1] if p.chave == fio.saida),
        None,
    )
    entrada = next(
        (p for p in mb.portas_de(destino.tipo, dict(destino.opcoes))[0] if p.chave == fio.entrada),
        None,
    )
    if saida is None or entrada is None or saida.tipo != entrada.tipo:
        return False
    return _dimensao_da_saida(origem, saida) == entrada.dimensao


def _ordem(grafo: Grafo) -> tuple[list[No], list[No]]:
    """A ordem dos fios. O que sobra está num laço."""
    faltam = {no.id: 0 for no in grafo.nos}
    saem: dict[str, list[str]] = {no.id: [] for no in grafo.nos}
    for fio in grafo.fios:
        faltam[fio.para] += 1
        saem[fio.de].append(fio.para)
    por_id = {no.id: no for no in grafo.nos}
    prontos = [no.id for no in grafo.nos if faltam[no.id] == 0]
    ordem = []
    while prontos:
        atual = prontos.pop(0)
        ordem.append(por_id[atual])
        for seguinte in saem[atual]:
            faltam[seguinte] -= 1
            if faltam[seguinte] == 0:
                prontos.append(seguinte)
    feitos = {no.id for no in ordem}
    return ordem, [no for no in grafo.nos if no.id not in feitos]


@dataclass(frozen=True)
class Montagem:
    condicoes: tuple[Condicao, ...]
    grandezas: tuple[Grandeza, ...]  # as letras que ficaram na conta
    essenciais: frozenset[str]  # as que a conta precisa; as outras só conferem uma hipótese
    padroes: tuple[tuple[str, float], ...]
    erros: tuple[tuple[str, str], ...]  # por bloco
    alertas: tuple[str, ...]
    hipoteses: tuple[str, ...]
    tem_resultado: bool
    area: sp.Expr | None = None  # da seção, para a busca pela menor área
    grafo: Grafo = Grafo((), ())
    origens: tuple[tuple[str, str], ...] = ()  # de onde veio o padrão de cada letra
    letras_do_bloco: tuple[tuple[str, tuple[str, ...]], ...] = ()
    saidas: Mapping[str, Mapping[str, Any]] = field(default_factory=dict, compare=False, hash=False)
    #: Dos blocos que numeram a letra: 2 é o segundo trecho, o de L₂. Sai da ordem dos fios.
    indices: tuple[tuple[str, int], ...] = ()

    def grandeza(self, chave: str) -> Grandeza | None:
        return next((item for item in self.grandezas if item.chave == chave), None)


@lru_cache(maxsize=256)
def montar(grafo: Grafo, zeros: frozenset[str] = frozenset()) -> Montagem:
    """``zeros``: letras com valor zero, que somem da conta em vez de virar 0/0 depois."""
    ordem, laco = _ordem(grafo)
    erros = {no.id: "Este bloco está num laço: desfaça um dos fios." for no in laco}
    grandezas: dict[str, Grandeza] = {}
    padroes: dict[str, float] = {}
    origens: dict[str, str] = {}
    alertas: list[str] = []
    hipoteses: list[str] = []
    marcas: set[str] = set()
    saidas: dict[str, Mapping[str, Any]] = {}
    contagem: dict[str, int] = {}
    indices: dict[str, int] = {}
    condicoes: list[Condicao] = []
    letras_do_bloco: dict[str, tuple[str, ...]] = {}
    tem_resultado = False
    area: sp.Expr | None = None
    for no in ordem:
        bloco = mb.POR_CHAVE[no.tipo]
        entradas, _ = mb.portas_de(no.tipo, dict(no.opcoes))
        contagem[no.tipo] = contagem.get(no.tipo, 0) + 1
        if bloco.numerar:
            indices[no.id] = contagem[no.tipo]
        ligados: dict[str, Any] = {}
        for fio in grafo.fios:
            if fio.para != no.id:
                continue
            valor = saidas.get(fio.de, {}).get(fio.saida)
            if valor is None:
                continue
            porta = next(p for p in entradas if p.chave == fio.entrada)
            if porta.varias:
                ligados.setdefault(fio.entrada, []).extend(valor)
            else:
                ligados[fio.entrada] = valor
        contexto = Contexto(
            contagem[no.tipo],
            dict(no.opcoes),
            ligados,
            bloco.numerar,
            zeros,
            grandezas,
            padroes,
            origens,
            alertas,
            hipoteses,
            marcas,
        )
        try:
            calculado = dict(bloco.calcular(contexto))
        except ValueError as erro:
            erros[no.id] = str(erro)
            letras_do_bloco[no.id] = tuple(dict.fromkeys(contexto.proprias))
            continue
        if "condicao" in calculado:
            calculado["condicao"] = [replace(c, no=no.id) for c in calculado["condicao"]]
        saidas[no.id] = calculado
        letras_do_bloco[no.id] = tuple(dict.fromkeys(contexto.proprias))
        if bloco.grupo == mb.GRUPO_SECAO and area is None:
            area = calculado["saida"].secao.area
        if no.tipo == mb.RESULTADO and not tem_resultado:
            tem_resultado = True
            condicoes = list(ligados.get("condicoes") or ())
            if not condicoes:
                erros[no.id] = "Ligue aqui ao menos um critério."
    if "fragil" in marcas and "ductil" in marcas:
        alertas.append(
            "O material escolhido não tem escoamento: von Mises e Tresca são para material dúctil. "
            "Use o bloco Maior principal."
        )
    essenciais = {s.name for condicao in condicoes for s in condicao.letras}
    nomes = set(essenciais)
    for condicao in condicoes:
        for validade in condicao.validade:
            nomes |= {s.name for s in validade.expressao.free_symbols}
    usadas = tuple(item for chave, item in grandezas.items() if chave in nomes)
    return Montagem(
        tuple(condicoes),
        usadas,
        frozenset(essenciais),
        tuple(padroes.items()),
        tuple(erros.items()),
        tuple(dict.fromkeys(alertas)),
        tuple(dict.fromkeys(hipoteses)),
        tem_resultado,
        area,
        grafo,
        tuple(origens.items()),
        tuple(letras_do_bloco.items()),
        saidas,
        tuple(indices.items()),
    )


# ---------------------------------------------------------------------------
# Forma fechada
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1024)
def limpar(expressao: sp.Expr, positiva: bool = True) -> sp.Expr:
    """Simplifica o que dá para simplificar logo: a seção de perfil I já chega grande.

    ``positiva``: a sympy não sabe que h − t_f é positivo e deixa √(x²) como |x|, o que trava o
    isolamento. Dentro da faixa válida da seção, o sinal de cada módulo é sempre o mesmo.
    """
    if sp.count_ops(expressao) > _LIMITE_DE_OPERACOES or expressao.has(*NUMERICAS):
        return expressao
    simples = sp.simplify(expressao)
    return _sem_modulo(simples) if positiva else simples


@dataclass(frozen=True)
class FormaFechada:
    expressao: sp.Expr
    latex: str


#: Uma seção válida, para decidir sinais: 1 − k tem de dar positivo, e h − 2·t_f também.
_SECAO_DE_AMOSTRA = {
    g.D.chave: 100.0,
    g.PAREDE.chave: 5.0,
    g.RELACAO.chave: 0.5,
    g.B.chave: 50.0,
    g.H.chave: 200.0,
    g.BF.chave: 100.0,
    g.TF.chave: 10.0,
    g.TW.chave: 6.0,
    g.ESCALA.chave: 1.0,
}


def _amostra(simbolos: Iterable[sp.Symbol]) -> dict[sp.Symbol, float]:
    """Números que respeitam a seção, para escolher a raiz certa e o sinal de cada módulo."""
    ordem = sorted(simbolos, key=lambda s: s.name)
    return {s: _SECAO_DE_AMOSTRA.get(s.name, 1.3 + 0.37 * i) for i, s in enumerate(ordem)}


def _sem_modulo(expressao: sp.Expr) -> sp.Expr:
    def trocar(dentro: sp.Expr) -> sp.Expr:
        return dentro if float(dentro.subs(_amostra(dentro.free_symbols))) >= 0.0 else -dentro

    return expressao.replace(sp.Abs, trocar)


def _radicais(expressao: sp.Expr) -> int:
    return sum(1 for p in expressao.atoms(sp.Pow) if p.exp.is_Rational and not p.exp.is_Integer)


def _raiz_de_ordem(base: sp.Expr, ordem: int) -> tuple[sp.Expr, str]:
    """base^(1/ordem) escrita como se escreve à mão: a raiz cúbica de uma expressão só."""
    valor = base ** sp.Rational(1, ordem)
    if ordem == 1:
        return base, sp.latex(base)
    if ordem % 2 == 0:
        dentro = _sem_modulo(sp.sqrt(base))
        if _radicais(dentro) <= 1:  # a base era um quadrado: √(a²·x) sai como a·√x
            metade = ordem // 2
            if metade == 1:
                return valor, sp.latex(dentro)
            return valor, f"\\sqrt[{metade}]{{{sp.latex(dentro)}}}"
    return valor, f"\\sqrt[{ordem}]{{{sp.latex(base)}}}".replace("\\sqrt[2]", "\\sqrt")


def _do_polinomio(expressao: sp.Expr, x: sp.Symbol) -> FormaFechada | None:
    numerador = sp.numer(sp.together(expressao))
    try:
        polinomio = sp.Poly(numerador, x)
    except sp.PolynomialError:
        return None
    termos = polinomio.terms()
    expoentes = [t[0][0] for t in termos]
    menor = min(expoentes)
    relativos = [e - menor for e in expoentes]
    passo = 0
    for e in relativos:
        passo = math.gcd(passo, e)
    if passo == 0:
        return None
    grau = max(relativos) // passo
    coeficientes = {e // passo: c for e, (_, c) in zip(relativos, termos, strict=True)}
    if any(c.has(x) for c in coeficientes.values()):
        return None
    if grau == 1:
        y = sp.factor(-coeficientes.get(0, sp.S.Zero) / coeficientes[1])
    elif grau == 2:
        a = coeficientes[2]
        b = coeficientes.get(1, sp.S.Zero)
        c = coeficientes.get(0, sp.S.Zero)
        delta = sp.factor(b**2 - 4 * a * c)
        raizes = [
            (-b + delta ** sp.Rational(1, 2)) / (2 * a),
            (-b - delta ** sp.Rational(1, 2)) / (2 * a),
        ]
        simbolos = list(set().union(*(r.free_symbols for r in raizes)))
        amostra = _amostra(simbolos)
        positivas = [(r, _real(r.subs(amostra))) for r in raizes]
        boas = [(r, v) for r, v in positivas if v is not None and v > 0]
        if not boas:
            return None
        y = limpar(max(boas, key=lambda par: par[1])[0])
    else:
        return None
    valor, latex = _raiz_de_ordem(y, passo)
    return FormaFechada(valor, latex)


@lru_cache(maxsize=512)
def forma_fechada(
    esquerda: sp.Expr, direita: sp.Expr, x: sp.Symbol, positiva: bool = True
) -> FormaFechada | None:
    """x em função do resto, se a equação vira polinômio de até grau 2 em x^k."""
    for candidata in (
        limpar(esquerda, positiva) - direita,
        limpar(esquerda**2, positiva) - direita**2,
    ):
        forma = _do_polinomio(candidata, x)
        if forma is not None:
            return forma
    return None


# ---------------------------------------------------------------------------
# Número
# ---------------------------------------------------------------------------


def _real(expressao: sp.Expr) -> float | None:
    """O número, ou nada: raiz de negativo e divisão por zero não são resposta."""
    try:
        valor = complex(sp.N(expressao))
    except (TypeError, ValueError, OverflowError):
        return None
    if abs(valor.imag) > 1e-12 * max(abs(valor.real), 1.0) or not math.isfinite(valor.real):
        return None
    return valor.real


def _funcao(expressao: sp.Expr, x: sp.Symbol) -> Callable[[float], float]:
    bruta = sp.lambdify(x, expressao, [FUNCOES, "math"])

    def chamar(valor: float) -> float:
        try:
            resultado = bruta(valor)
        except (ValueError, ZeroDivisionError, OverflowError):
            return math.nan
        if isinstance(resultado, complex):
            return math.nan
        return float(resultado)

    return chamar


def _dentro(validades: Sequence[Validade], x: sp.Symbol) -> list[Callable[[float], float]]:
    return [
        _funcao(v.expressao, x)
        for v in validades
        if v.restringe and v.expressao.free_symbols <= {x}
    ]


def _raizes(
    f: Callable[[float], float], dominio: Sequence[Callable[[float], float]]
) -> list[float]:
    """Toda troca de sinal na grade, refinada por bisseção."""
    achadas = []
    anterior: tuple[float, float] | None = None
    for atual in _GRADE_LOG.tolist():
        valor = f(atual) if all(c(atual) >= 0 for c in dominio) else math.nan
        if not math.isfinite(valor):
            anterior = None
            continue
        if anterior is not None and anterior[1] * valor < 0.0:
            a, b, fa = anterior[0], atual, anterior[1]
            for _ in range(200):
                meio = (a + b) / 2.0
                fm = f(meio)
                if not math.isfinite(fm):
                    break
                if fa * fm <= 0.0:
                    b = meio
                else:
                    a, fa = meio, fm
                if abs(b - a) <= 1e-12 * abs(b):
                    break
            achadas.append((a + b) / 2.0)
        anterior = (atual, valor)
    return achadas


def _lado(f: Callable[[float], float], raiz: float) -> str:
    """Quem passa da raiz para cima pede mínimo: é o caso da medida da seção."""
    depois = f(raiz * (1.0 + 1e-4))
    antes = f(raiz * (1.0 - 1e-4))
    if math.isfinite(depois) and math.isfinite(antes):
        return MINIMO if depois < antes else MAXIMO
    return MINIMO if math.isfinite(depois) and depois < 0.0 else MAXIMO


# ---------------------------------------------------------------------------
# Resposta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Isolada:
    """Uma condição resolvida para a grandeza pedida."""

    condicao: Condicao
    formula: FormaFechada | None
    equacao: str  # LaTeX de "esquerda = direita"
    tensao: str  # LaTeX da tensão equivalente simplificada
    com_numeros: str  # LaTeX da fórmula com os números já postos; vazio se não couber
    valor: float | None
    lado: str | None
    independente: bool  # a condição não tem a grandeza pedida
    passa: bool | None  # só na condição independente


@dataclass(frozen=True)
class LinhaConferida:
    nome: str
    esquerda: float
    direita: float
    uso: float
    no: str = ""
    igualdade: bool = False


@dataclass(frozen=True)
class Resposta:
    alvo: Grandeza
    isoladas: tuple[Isolada, ...]
    valor: float | None
    sentido: str | None  # x ≥ valor (mínimo), x ≤ valor (máximo) ou x = valor
    manda: Isolada | None
    faltam: tuple[Grandeza, ...]
    conferencia: tuple[LinhaConferida, ...]
    alertas: tuple[str, ...]
    materiais: tuple[str, ...]
    invalidos: tuple[str, ...] = ()
    adotado: float | None = None
    conferencia_adotada: tuple[LinhaConferida, ...] = ()
    montagem: Montagem | None = None
    valores_usados: Mapping[str, float] = field(default_factory=dict, compare=False, hash=False)


def _numeros(valores: Mapping[str, float], x: sp.Symbol | None) -> dict[sp.Symbol, sp.Float]:
    return {
        sp.Symbol(chave, positive=True): sp.Float(valor)
        for chave, valor in valores.items()
        if x is None or chave != x.name
    }


def _com_numeros(forma: FormaFechada, numeros: Mapping[sp.Symbol, sp.Float]) -> str:
    if not numeros:
        return ""
    parcial = sp.N(forma.expressao.subs(numeros), 4)
    # sp.N também arredonda os expoentes: M^0,5 volta a ser √M.
    parcial = parcial.replace(
        lambda e: e.is_Pow and e.exp.is_Float,
        lambda e: sp.Pow(e.base, sp.Rational(str(Fraction(float(e.exp)).limit_denominator(24)))),
    )
    return sp.latex(parcial).replace(".", "{,}")


def _isolar_uma(
    condicao: Condicao,
    x: sp.Symbol,
    numeros: Mapping[sp.Symbol, sp.Float],
) -> Isolada:
    esquerda, direita = condicao.esquerda, condicao.direita
    tensao = sp.latex(limpar(esquerda, condicao.positiva))
    equacao = f"{tensao} = {sp.latex(direita)}"
    livres = esquerda.free_symbols | direita.free_symbols
    resto = livres - set(numeros) - {x}
    if x not in livres:
        passa: bool | None = None
        if not resto:
            lado_e, lado_d = _real(esquerda.subs(numeros)), _real(direita.subs(numeros))
            if lado_e is not None and lado_d is not None:
                if condicao.igualdade:
                    passa = abs(lado_e - lado_d) <= _FOLGA_DA_IGUALDADE * max(abs(lado_d), 1.0)
                else:
                    passa = lado_e <= lado_d + _FOLGA
        return Isolada(condicao, None, equacao, tensao, "", None, None, True, passa)
    forma = forma_fechada(esquerda, direita, x, condicao.positiva)
    com_numeros = _com_numeros(forma, numeros) if forma else ""
    if resto:
        return Isolada(condicao, forma, equacao, tensao, com_numeros, None, None, False, None)
    diferenca = (esquerda - direita).subs(numeros)
    f = _funcao(diferenca, x)
    dominio = _dentro(
        [Validade(v.expressao.subs(numeros), v.mensagem, v.restringe) for v in condicao.validade],
        x,
    )
    if forma is not None:
        valor = _real(forma.expressao.subs(numeros))
        if valor is None or valor <= 0.0:
            return Isolada(condicao, forma, equacao, tensao, com_numeros, None, None, False, None)
        lado = IGUAL if condicao.igualdade else _lado(f, valor)
        return Isolada(condicao, forma, equacao, tensao, com_numeros, valor, lado, False, None)
    raizes = _raizes(f, dominio)
    if not raizes:
        return Isolada(condicao, None, equacao, tensao, "", None, None, False, None)
    lados = [_lado(f, r) for r in raizes]
    minimos = [r for r, lado in zip(raizes, lados, strict=True) if lado == MINIMO]
    if condicao.igualdade:
        return Isolada(condicao, None, equacao, tensao, "", raizes[0], IGUAL, False, None)
    valor = max(minimos) if minimos else min(raizes)
    lado = MINIMO if minimos else MAXIMO
    return Isolada(condicao, None, equacao, tensao, "", valor, lado, False, None)


def _conferir(
    isoladas: Sequence[Isolada], valores: Mapping[str, float], x: sp.Symbol, final: float
) -> tuple[LinhaConferida, ...]:
    tudo = {**_numeros(valores, x), x: sp.Float(final)}
    linhas = []
    for item in isoladas:
        c = item.condicao
        esquerda = _real(c.esquerda.subs(tudo))
        direita = _real(c.direita.subs(tudo))
        if esquerda is None or direita is None:
            continue
        uso = esquerda / direita if direita else math.inf
        linhas.append(LinhaConferida(c.nome, esquerda, direita, uso, c.no, c.igualdade))
    return tuple(linhas)


def _alertas_da_validade(
    isoladas: Sequence[Isolada], valores: Mapping[str, float], x: sp.Symbol, final: float
) -> list[str]:
    tudo = {**_numeros(valores, x), x: sp.Float(final)}
    alertas: list[str] = []
    for item in isoladas:
        for v in item.condicao.validade:
            expressao = v.expressao.subs(tudo)
            if expressao.free_symbols:
                continue
            numero = _real(expressao)
            if numero is not None and numero < -_FOLGA and v.mensagem not in alertas:
                alertas.append(v.mensagem)
    return alertas


def _materiais_que_servem(alvo: Grandeza, valor: float, sentido: str | None) -> tuple[str, ...]:
    if sentido != MINIMO or alvo.chave not in (g.SY.chave, g.SUT.chave):
        return ()
    limite = (lambda m: m.sy_MPa) if alvo.chave == g.SY.chave else (lambda m: m.sut_MPa)
    bons = [m for m in mc.listar_cadastrados().values() if limite(m) >= valor]
    return tuple(m.nome for m in sorted(bons, key=limite)[:8])


def conferir_valores(
    montagem: Montagem, valores: Mapping[str, float | None]
) -> tuple[dict[str, float], list[str]]:
    """Separa os valores bons das mensagens. Letra com valor ruim volta a ser letra."""
    limpos: dict[str, float] = {}
    problemas: list[str] = []
    for chave, valor in valores.items():
        grandeza = montagem.grandeza(chave)
        if valor is None or grandeza is None:
            continue
        problema = grandeza.problema_no_valor(float(valor))
        if problema:
            problemas.append(problema)
        else:
            limpos[chave] = float(valor)
    return limpos, problemas


def letras_zeradas(
    montagem: Montagem, valores: Mapping[str, float], alvo: str | None = None
) -> frozenset[str]:
    """Esforço em zero sai da conta: fica mais simples, e M_x/√(M_x²) não vira 0/0."""
    return frozenset(chave for chave, valor in valores.items() if valor == 0.0 and chave != alvo)


def isolar(
    montagem: Montagem,
    alvo: str,
    valores: Mapping[str, float | None],
    adotado: float | None = None,
) -> Resposta:
    """``valores`` na base do sistema. Letra sem valor fica na fórmula."""
    grandeza = montagem.grandeza(alvo)
    if grandeza is None:
        raise ErroDeMontagem("Escolha uma grandeza que esteja no desenho.")
    limpos, invalidos = conferir_valores(montagem, {k: v for k, v in valores.items() if k != alvo})
    zeros = letras_zeradas(montagem, limpos, alvo)
    conta = montar(montagem.grafo, zeros) if zeros else montagem
    if conta.grandeza(alvo) is None or not conta.condicoes:
        raise ErroDeMontagem(
            f"Com esses valores em zero, {grandeza.texto} não entra mais na conta. "
            "Preencha ao menos um esforço."
        )
    x = grandeza.simbolo
    usados = {k: v for k, v in limpos.items() if conta.grandeza(k) is not None}
    numeros = _numeros(usados, x)
    faltam = tuple(
        item
        for item in conta.grandezas
        if item.chave in conta.essenciais and item.chave != alvo and item.chave not in usados
    )
    isoladas = tuple(_isolar_uma(c, x, numeros) for c in conta.condicoes)
    iguais = [i for i in isoladas if i.lado == IGUAL and i.valor is not None]
    minimos = [i for i in isoladas if i.lado == MINIMO and i.valor is not None]
    maximos = [i for i in isoladas if i.lado == MAXIMO and i.valor is not None]
    alertas: list[str] = []
    manda: Isolada | None = None
    valor: float | None = None
    sentido: str | None = None
    if not faltam and iguais:
        manda, valor, sentido = iguais[0], iguais[0].valor, IGUAL
        for outra in iguais[1:]:
            if abs((outra.valor or 0.0) - (valor or 0.0)) > 1e-6 * abs(valor or 1.0):
                alertas.append(
                    f"{manda.condicao.nome} e {outra.condicao.nome} dão valores diferentes de "
                    f"{grandeza.texto}: as duas equações não fecham juntas."
                )
    elif not faltam and (minimos or maximos):
        de_baixo = max(minimos, key=lambda i: i.valor or 0.0) if minimos else None
        de_cima = min(maximos, key=lambda i: i.valor or 0.0) if maximos else None
        if de_baixo and de_cima and (de_baixo.valor or 0.0) > (de_cima.valor or 0.0):
            alertas.append(
                f"Nenhum valor de {grandeza.texto} atende: {de_baixo.condicao.nome} pede mais, e "
                f"{de_cima.condicao.nome} pede menos."
            )
        manda = de_baixo or de_cima
        if manda is not None:
            valor = manda.valor
            sentido = MINIMO if de_baixo else MAXIMO
    if not faltam:
        for item in isoladas:
            if item.independente and item.passa is False:
                alertas.append(
                    f"{item.condicao.nome} não passa, e {grandeza.texto} não muda isso: essa "
                    "condição não depende dela."
                )
            if not item.independente and item.valor is None:
                alertas.append(
                    f"{item.condicao.nome}: nenhum valor positivo de {grandeza.texto} fecha essa "
                    "equação."
                )
    conferencia: tuple[LinhaConferida, ...] = ()
    materiais: tuple[str, ...] = ()
    if valor is not None:
        conferencia = _conferir(isoladas, usados, x, valor)
        alertas += _alertas_da_validade(isoladas, usados, x, valor)
        materiais = _materiais_que_servem(grandeza, valor, sentido)
    medida: float | None = None
    conferencia_adotada: tuple[LinhaConferida, ...] = ()
    if adotado is not None and adotado > 0.0 and not faltam:
        medida = float(adotado)
        conferencia_adotada = _conferir(isoladas, usados, x, medida)
        alertas += [
            a for a in _alertas_da_validade(isoladas, usados, x, medida) if a not in alertas
        ]
    return Resposta(
        grandeza,
        isoladas,
        valor,
        sentido,
        manda,
        faltam,
        conferencia,
        tuple(dict.fromkeys(alertas)),
        materiais,
        tuple(invalidos),
        medida,
        conferencia_adotada,
        conta,
        usados,
    )


def valor_final(montagem: Montagem, alvo: str, valores: Mapping[str, float]) -> float | None:
    """Só o número: para as varreduras do gráfico."""
    try:
        return isolar(montagem, alvo, valores).valor
    except ErroDeMontagem:
        return None


def varrer(
    montagem: Montagem,
    alvo: str,
    valores: Mapping[str, float],
    letra: str,
    pontos: int = 25,
) -> list[tuple[float, float]]:
    """Como a resposta anda com outra letra, de metade ao dobro do valor dela."""
    centro = valores.get(letra)
    if not centro or centro <= 0.0:
        return []
    linhas = []
    for fator in np.geomspace(0.5, 2.0, pontos).tolist():
        valor = valor_final(montagem, alvo, {**valores, letra: centro * fator})
        if valor is not None:
            linhas.append((centro * fator, valor))
    return linhas


def curvas(
    resposta: Resposta, valores: Mapping[str, float], pontos: int = 61
) -> list[tuple[str, float, float]]:
    """Uso de cada condição em volta da resposta: 1 é o limite."""
    if resposta.valor is None:
        return []
    x = resposta.alvo.simbolo
    numeros = _numeros(resposta.valores_usados or valores, x)
    linhas: list[tuple[str, float, float]] = []
    for item in resposta.isoladas:
        c = item.condicao
        if item.independente:
            continue
        uso = _funcao((c.esquerda / c.direita).subs(numeros), x)
        for valor in np.geomspace(resposta.valor * 0.5, resposta.valor * 2.0, pontos).tolist():
            calculado = uso(valor)
            if math.isfinite(calculado):
                linhas.append((c.nome, valor, calculado))
    return linhas


def curvas_da_bomba(
    resposta: Resposta, valores: Mapping[str, float], pontos: int = 61
) -> list[tuple[float, float, float]]:
    """Vazão, altura do sistema e altura da bomba em volta do ponto de operação."""
    x = resposta.alvo.simbolo
    if resposta.valor is None or x.name != g.VAZAO_Q.chave:
        return []
    numeros = _numeros(resposta.valores_usados or valores, x)
    item = next(
        (i for i in resposta.isoladas if i.condicao.criterio == mfl.PONTO_DE_OPERACAO), None
    )
    if item is None:
        return []
    sistema = _funcao(item.condicao.esquerda.subs(numeros), x)
    bomba = _funcao(item.condicao.direita.subs(numeros), x)
    linhas = []
    for valor in np.linspace(resposta.valor * 0.02, resposta.valor * 1.5, pontos).tolist():
        alto, baixo = sistema(valor), bomba(valor)
        if math.isfinite(alto) and math.isfinite(baixo) and baixo > 0.0:
            linhas.append((valor, alto, baixo))
    return linhas


# ---------------------------------------------------------------------------
# O que passa num fio
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Transportado:
    """Os dados de um fio, para o inspetor. Número na base, ou None se ainda tem letra."""

    objeto: str
    colunas: tuple[tuple[str, str], ...]  # título e dimensão
    linhas: tuple[tuple[str, tuple[float | None, ...]], ...]
    esforcos: tuple[tuple[str, float | None, str], ...] = ()  # o que já foi somado na fila


def numero_de(expressao: Any, numeros: Mapping[sp.Symbol, sp.Float]) -> float | None:
    valor = sp.sympify(expressao).subs(numeros)
    return None if valor.free_symbols else _real(valor)


def transportado(
    valor: Any, numeros: Mapping[sp.Symbol, sp.Float], dimensao: str | None = None
) -> Transportado | None:
    """Traduz o que sai de uma porta: tensões por ponto, trechos da linha, ou um número."""
    if isinstance(valor, Estado):
        return Transportado(
            "EstadoTensao",
            (("σ", g.TENSAO), ("τ", g.TENSAO)),
            tuple(
                (t.ponto, (numero_de(t.sx, numeros), numero_de(t.tau, numeros)))
                for t in valor.tensoes
            ),
            tuple(
                (rotulo, numero_de(esforco, numeros), dimensao)
                for rotulo, esforco, dimensao in (
                    ("M_x", valor.mx, g.MOMENTO),
                    ("M_y", valor.my, g.MOMENTO),
                    ("T", valor.t, g.MOMENTO),
                    ("N", valor.n, g.FORCA),
                    ("V_y", valor.vy, g.FORCA),
                    ("V_x", valor.vx, g.FORCA),
                )
                if esforco != 0
            ),
        )
    if isinstance(valor, mfl.Linha):
        return Transportado(
            "LinhaDeFluido",
            (
                ("V", g.VELOCIDADE),
                ("Re", g.PURO),
                ("f", g.PURO),
                ("h_f", g.ALTURA),
            ),
            tuple(
                (
                    t.rotulo,
                    (
                        numero_de(t.velocidade, numeros),
                        numero_de(t.reynolds, numeros),
                        numero_de(t.atrito, numeros),
                        numero_de(t.perda, numeros),
                    ),
                )
                for t in valor.trechos
            ),
        )
    if isinstance(valor, mb.Material):
        return Transportado(
            "Material",
            (("Valor", g.TENSAO),),
            (
                ("S_y", (numero_de(valor.sy, numeros),)),
                ("S_ut", (numero_de(valor.sut, numeros),)),
                ("E", (numero_de(valor.e, numeros),)),
                ("G", (numero_de(valor.g, numeros),)),
            ),
        )
    if isinstance(valor, list):
        return None
    return Transportado(
        "Valor",
        (("Valor", dimensao or g.PURO),),
        (("", (numero_de(valor, numeros),)),),
    )


def ids_ate_o_inicio(grafo: Grafo, ids: Iterable[str]) -> set[str]:
    """Todos os blocos de que estes dependem: é o caminho do rastreio."""
    vistos: set[str] = set()
    fila = list(ids)
    while fila:
        atual = fila.pop()
        if atual in vistos:
            continue
        vistos.add(atual)
        fila.extend(f.de for f in grafo.fios if f.para == atual)
    return vistos


__all__ = [
    "CONJUNTO",
    "ErroDeBloco",
    "ErroDeMontagem",
    "Fio",
    "Grafo",
    "IGUAL",
    "Isolada",
    "LinhaConferida",
    "MAXIMO",
    "MINIMO",
    "Montagem",
    "No",
    "Resposta",
    "Transportado",
    "conferir_valores",
    "curvas",
    "curvas_da_bomba",
    "forma_fechada",
    "grafo_de_dados",
    "ids_ate_o_inicio",
    "isolar",
    "letras_zeradas",
    "limpar",
    "montar",
    "numero_de",
    "resolver_saida",
    "transportado",
    "valor_final",
    "varrer",
]
