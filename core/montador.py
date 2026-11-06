"""O motor do montador de fórmulas: lê os blocos ligados e isola a grandeza escolhida.

``montar`` percorre o desenho na ordem dos fios e devolve as condições "isto ≤ aquilo". ``isolar``
resolve cada uma para a grandeza pedida. Equações que viram polinômio de até grau 2 em x^k saem em
forma fechada; as outras ficam como equação, com a raiz achada por número. A resposta final junta as
condições: quem pede um mínimo manda pelo maior, quem pede um máximo manda pelo menor.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Any

import numpy as np
import sympy as sp

from core import material_catalog as mc
from core import montador_blocos as mb
from core import montador_grandezas as g
from core.montador_blocos import Condicao, Contexto, ErroDeBloco
from core.montador_grandezas import Grandeza
from core.montador_secoes import Validade

MINIMO = "mínimo"
MAXIMO = "máximo"
_GRADE_LOG = np.logspace(-6.0, 15.0, 841)  # na base N, mm: de um nanômetro a um momento enorme
_LIMITE_DE_OPERACOES = 400  # acima disso, simplificar custa mais do que ajuda
_FOLGA = 1e-9


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


def grafo_de_dados(dados: Mapping[str, Any]) -> Grafo:
    """Do formato da prancheta. Bloco desconhecido e fio solto ficam de fora, sem quebrar a tela."""
    nos = []
    for linha in dados.get("nos") or ():
        if not isinstance(linha, Mapping) or linha.get("tipo") not in mb.POR_CHAVE:
            continue
        opcoes = linha.get("opcoes") or {}
        nos.append(
            No(
                str(linha.get("id")),
                str(linha["tipo"]),
                tuple(sorted((str(k), str(v)) for k, v in opcoes.items())),
            )
        )
    por_id = {no.id: no for no in nos}
    fios: list[Fio] = []
    ocupadas: dict[tuple[str, str], int] = {}
    for linha in dados.get("fios") or ():
        if not isinstance(linha, Mapping):
            continue
        fio = Fio(
            str(linha.get("de")),
            str(linha.get("saida")),
            str(linha.get("para")),
            str(linha.get("entrada")),
        )
        if not _fio_valido(fio, por_id):
            continue
        destino = next(
            p for p in mb.POR_CHAVE[por_id[fio.para].tipo].entradas if p.chave == fio.entrada
        )
        chave = (fio.para, fio.entrada)
        if destino.varias or chave not in ocupadas:
            ocupadas[chave] = len(fios)
            fios.append(fio)
        else:
            fios[ocupadas[chave]] = fio  # porta de um fio só: vale o último
    return Grafo(tuple(nos), tuple(fios))


def _fio_valido(fio: Fio, por_id: Mapping[str, No]) -> bool:
    if fio.de not in por_id or fio.para not in por_id or fio.de == fio.para:
        return False
    saida = next(
        (p for p in mb.POR_CHAVE[por_id[fio.de].tipo].saidas if p.chave == fio.saida), None
    )
    entrada = next(
        (p for p in mb.POR_CHAVE[por_id[fio.para].tipo].entradas if p.chave == fio.entrada), None
    )
    if saida is None or entrada is None or saida.tipo != entrada.tipo:
        return False
    return saida.dimensao == entrada.dimensao


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

    def grandeza(self, chave: str) -> Grandeza | None:
        return next((item for item in self.grandezas if item.chave == chave), None)


@lru_cache(maxsize=128)
def montar(grafo: Grafo) -> Montagem:
    ordem, laco = _ordem(grafo)
    erros = {no.id: "Este bloco está num laço: desfaça um dos fios." for no in laco}
    grandezas: dict[str, Grandeza] = {}
    padroes: dict[str, float] = {}
    alertas: list[str] = []
    hipoteses: list[str] = []
    marcas: set[str] = set()
    saidas: dict[str, Mapping[str, Any]] = {}
    contagem: dict[str, int] = {}
    condicoes: list[Condicao] = []
    tem_resultado = False
    for no in ordem:
        bloco = mb.POR_CHAVE[no.tipo]
        contagem[no.tipo] = contagem.get(no.tipo, 0) + 1
        ligados: dict[str, Any] = {}
        for fio in grafo.fios:
            if fio.para != no.id:
                continue
            valor = saidas.get(fio.de, {}).get(fio.saida)
            if valor is None:
                continue
            porta = next(p for p in bloco.entradas if p.chave == fio.entrada)
            if porta.varias:
                ligados.setdefault(fio.entrada, []).extend(valor)
            else:
                ligados[fio.entrada] = valor
        contexto = Contexto(
            contagem[no.tipo], dict(no.opcoes), ligados, bloco.numerar, grandezas, padroes, alertas
        )
        contexto.hipoteses = hipoteses
        contexto.marcas = marcas
        try:
            saidas[no.id] = bloco.calcular(contexto)
        except ValueError as erro:
            erros[no.id] = str(erro)
            continue
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
    )


# ---------------------------------------------------------------------------
# Forma fechada
# ---------------------------------------------------------------------------


def limpar(expressao: sp.Expr, positiva: bool = True) -> sp.Expr:
    """Simplifica o que dá para simplificar logo: a seção de perfil I já chega grande.

    ``positiva``: a sympy não sabe que h − t_f é positivo e deixa √(x²) como |x|, o que trava o
    isolamento. Dentro da faixa válida da seção, o sinal de cada módulo é sempre o mesmo.
    """
    if sp.count_ops(expressao) > _LIMITE_DE_OPERACOES:
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
        boas = [r for r in raizes if float(r.subs(amostra)) > 0]
        if not boas:
            return None
        y = limpar(max(boas, key=lambda r: float(r.subs(amostra))))
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


def _funcao(expressao: sp.Expr, x: sp.Symbol) -> Callable[[float], float]:
    bruta = sp.lambdify(x, expressao, "math")

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
    return [_funcao(v.expressao, x) for v in validades if v.expressao.free_symbols <= {x}]


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


@dataclass(frozen=True)
class Resposta:
    alvo: Grandeza
    isoladas: tuple[Isolada, ...]
    valor: float | None
    sentido: str | None  # x ≥ valor (mínimo) ou x ≤ valor (máximo)
    manda: Isolada | None
    faltam: tuple[Grandeza, ...]
    conferencia: tuple[LinhaConferida, ...]
    alertas: tuple[str, ...]
    materiais: tuple[str, ...]


def _numeros(valores: Mapping[str, float], x: sp.Symbol) -> dict[sp.Symbol, sp.Float]:
    return {
        sp.Symbol(chave, positive=True): sp.Float(valor)
        for chave, valor in valores.items()
        if chave != x.name
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
            passa = float((esquerda - direita).subs(numeros)) <= _FOLGA
        return Isolada(condicao, None, equacao, tensao, "", None, None, True, passa)
    forma = forma_fechada(esquerda, direita, x, condicao.positiva)
    com_numeros = _com_numeros(forma, numeros) if forma else ""
    if resto:
        return Isolada(condicao, forma, equacao, tensao, com_numeros, None, None, False, None)
    diferenca = (esquerda - direita).subs(numeros)
    f = _funcao(diferenca, x)
    dominio = _dentro(
        [Validade(v.expressao.subs(numeros), v.mensagem) for v in condicao.validade], x
    )
    if forma is not None:
        valor = float(forma.expressao.subs(numeros))
        if not math.isfinite(valor) or valor <= 0.0:
            return Isolada(condicao, forma, equacao, tensao, com_numeros, None, None, False, None)
        return Isolada(
            condicao, forma, equacao, tensao, com_numeros, valor, _lado(f, valor), False, None
        )
    raizes = _raizes(f, dominio)
    if not raizes:
        return Isolada(condicao, None, equacao, tensao, "", None, None, False, None)
    lados = [_lado(f, r) for r in raizes]
    minimos = [r for r, lado in zip(raizes, lados, strict=True) if lado == MINIMO]
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
        esquerda = float(c.esquerda.subs(tudo))
        direita = float(c.direita.subs(tudo))
        linhas.append(
            LinhaConferida(c.nome, esquerda, direita, esquerda / direita if direita else math.inf)
        )
    return tuple(linhas)


def _alertas_da_validade(
    isoladas: Sequence[Isolada], valores: Mapping[str, float], x: sp.Symbol, final: float
) -> list[str]:
    tudo = {**_numeros(valores, x), x: sp.Float(final)}
    alertas: list[str] = []
    for item in isoladas:
        for v in item.condicao.validade:
            expressao = v.expressao.subs(tudo)
            if (
                not expressao.free_symbols
                and float(expressao) < -_FOLGA
                and v.mensagem not in alertas
            ):
                alertas.append(v.mensagem)
    return alertas


def _materiais_que_servem(alvo: Grandeza, valor: float, sentido: str | None) -> tuple[str, ...]:
    if sentido != MINIMO or alvo.chave not in (g.SY.chave, g.SUT.chave):
        return ()
    limite = (lambda m: m.sy_MPa) if alvo.chave == g.SY.chave else (lambda m: m.sut_MPa)
    bons = [m for m in mc.listar_cadastrados().values() if limite(m) >= valor]
    return tuple(m.nome for m in sorted(bons, key=limite)[:8])


def isolar(montagem: Montagem, alvo: str, valores: Mapping[str, float]) -> Resposta:
    """``valores`` na base N, mm, MPa. Letra sem valor fica na fórmula."""
    grandeza = montagem.grandeza(alvo)
    if grandeza is None:
        raise ErroDeMontagem("Escolha uma grandeza que esteja no desenho.")
    x = grandeza.simbolo
    usados = {
        k: float(v)
        for k, v in valores.items()
        if v is not None and montagem.grandeza(k) is not None
    }
    numeros = _numeros(usados, x)
    faltam = tuple(
        item
        for item in montagem.grandezas
        if item.chave in montagem.essenciais and item.chave != alvo and item.chave not in usados
    )
    isoladas = tuple(_isolar_uma(c, x, numeros) for c in montagem.condicoes)
    minimos = [i for i in isoladas if i.lado == MINIMO and i.valor is not None]
    maximos = [i for i in isoladas if i.lado == MAXIMO and i.valor is not None]
    alertas: list[str] = []
    manda: Isolada | None = None
    valor: float | None = None
    sentido: str | None = None
    if not faltam and (minimos or maximos):
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
    )


def valor_final(montagem: Montagem, alvo: str, valores: Mapping[str, float]) -> float | None:
    """Só o número: para as varreduras do gráfico."""
    return isolar(montagem, alvo, valores).valor


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
    numeros = _numeros(valores, x)
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


__all__ = [
    "ErroDeBloco",
    "ErroDeMontagem",
    "Fio",
    "Grafo",
    "Isolada",
    "MAXIMO",
    "MINIMO",
    "Montagem",
    "No",
    "Resposta",
    "curvas",
    "forma_fechada",
    "grafo_de_dados",
    "isolar",
    "limpar",
    "montar",
    "valor_final",
    "varrer",
]
