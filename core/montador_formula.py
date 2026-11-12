"""A fórmula própria do Montador: o que a pessoa digita vira uma conta, sem passar por ``eval``.

O texto vem do usuário e fica guardado em arquivos que circulam, então não pode virar código: nada de
``sympify``, que usa ``eval``. Aqui há um leitor próprio, que só conhece números, letras, operadores,
parênteses e uma lista curta de funções. Tudo o mais é recusado com uma mensagem dizendo onde parou.

Três formas de escrever:

- ``q*L^2/8``: um valor, que sai por uma bolinha para outro bloco.
- ``M = q*L^2/8``: o mesmo valor, com nome, e também uma equação para o bloco Em função de.
- ``M*c/I <= S_y/n``: uma condição.

Letra igual à do programa usa o mesmo valor e a mesma unidade. Letra nova é uma medida que a pessoa
diz o que é. As unidades são conferidas pelas potências de força, comprimento e tempo.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from core import montador_grandezas as g
from core.montador_grandezas import Grandeza

MENOR_IGUAL = "<="
MAIOR_IGUAL = ">="
IGUAL = "="
MAX_CARACTERES = 300
_MAX_FICHAS = 200
_MAX_PROFUNDIDADE = 30
_MAX_EXPOENTE = 64
_MAX_NUMERO = sp.Integer(10) ** 30

_GREGAS = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "varepsilon",
    "ζ": "zeta",
    "η": "eta",
    "θ": "theta",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ν": "nu",
    "ξ": "xi",
    "ρ": "rho",
    "σ": "sigma",
    "τ": "tau",
    "φ": "phi",
    "χ": "chi",
    "ψ": "psi",
    "ω": "omega",
    "Δ": "Delta",
    "Σ": "Sigma",
    "Φ": "Phi",
    "Ω": "Omega",
}
_FUNCOES: dict[str, Callable[[sp.Expr], sp.Expr]] = {
    "sqrt": sp.sqrt,
    "raiz": sp.sqrt,
    "sin": sp.sin,
    "sen": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "tg": sp.tan,
    "asin": sp.asin,
    "asen": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "exp": sp.exp,
    "ln": sp.log,
    "log10": lambda x: sp.log(x) / sp.log(10),
    "abs": sp.Abs,
}


#: Letras que quase sempre querem dizer a mesma coisa em cada parte do programa.
_SUGESTOES: dict[str, dict[str, str]] = {
    g.SISTEMA_SOLIDOS.chave: {
        "M": g.MOMENTO,
        "V": g.FORCA,
        "W": g.FORCA,
        "P": g.FORCA,
        "I": g.INERCIA,
        "J": g.INERCIA,
        "A": g.AREA,
        "Q": g.VOLUME,
        "c": g.MEDIDA,
        "r": g.MEDIDA,
        "e": g.MEDIDA,
        "a": g.COMPRIMENTO,
        "sigma": g.TENSAO,
        "tau": g.TENSAO,
    },
    g.SISTEMA_FLUIDOS.chave: {
        "V": g.VELOCIDADE,
        "v": g.VELOCIDADE,
        "A": g.AREA,
        "P": g.POTENCIA,
        "p": g.PRESSAO,
        "H": g.ALTURA,
        "z": g.ALTURA,
        "F": g.FORCA,
    },
    g.SISTEMA_TERMICO.chave: {
        "c_p": g.CALOR_ESPECIFICO,
        "c_v": g.CALOR_ESPECIFICO,
        "c": g.CALOR_ESPECIFICO,
        "dT": g.DIF_TEMPERATURA,
        "DT": g.DIF_TEMPERATURA,
        "Q": g.POTENCIA,
        "W": g.POTENCIA,
        "P": g.POTENCIA,
        "h": g.ENERGIA_ESPECIFICA,
        "s": g.ENTROPIA_ESPECIFICA,
        "rho": g.MASSA_ESPECIFICA,
    },
}


class ErroDeFormula(ValueError):
    """O que impede de ler a fórmula, em palavras de quem digitou."""


class ErroDeUnidade(ValueError):
    """Os dois lados, ou duas parcelas, não têm a mesma unidade."""


@dataclass(frozen=True)
class Ficha:
    tipo: str  # numero, nome, sinal ou fim
    valor: str
    posicao: int


@dataclass(frozen=True)
class Formula:
    texto: str
    direita: sp.Expr  # o valor, ou o lado direito da condição
    esquerda: sp.Expr | None = None
    sinal: str = ""
    nome: str = ""  # em "M = q*L^2/8", o nome da saída
    letras: tuple[str, ...] = ()  # na ordem do texto, sem o nome da saída

    @property
    def tem_valor(self) -> bool:
        return not self.sinal or bool(self.nome)

    @property
    def tem_condicao(self) -> bool:
        return bool(self.sinal)


def _sem_grega(nome: str) -> str:
    return "".join(_GREGAS.get(letra, letra) for letra in nome)


def _ler_numero(texto: str, inicio: int) -> tuple[str, int]:
    i = inicio
    while i < len(texto) and texto[i].isdigit():
        i += 1
    if i + 1 < len(texto) and texto[i] in ".," and texto[i + 1].isdigit():
        i += 1
        while i < len(texto) and texto[i].isdigit():
            i += 1
    elif i < len(texto) and texto[i] in ".,":
        i += 1
    if i < len(texto) and texto[i] in "eE":
        j = i + 1
        if j < len(texto) and texto[j] in "+-":
            j += 1
        if j < len(texto) and texto[j].isdigit():
            while j < len(texto) and texto[j].isdigit():
                j += 1
            i = j
    return texto[inicio:i].replace(",", "."), i


def _fichas(texto: str) -> list[Ficha]:
    fichas: list[Ficha] = []
    i = 0
    trocas = {"×": "*", "·": "*", "÷": "/", "−": "-", "≤": MENOR_IGUAL, "≥": MAIOR_IGUAL}
    while i < len(texto):
        letra = texto[i]
        if letra.isspace():
            i += 1
        elif letra.isdigit() or (letra in ".," and i + 1 < len(texto) and texto[i + 1].isdigit()):
            valor, fim = _ler_numero(texto, i)
            fichas.append(Ficha("numero", valor, i))
            i = fim
        elif letra.isalpha() or letra == "_":
            fim = i + 1
            while fim < len(texto) and (texto[fim].isalnum() or texto[fim] == "_"):
                fim += 1
            fichas.append(Ficha("nome", texto[i:fim], i))
            i = fim
        elif letra == "√":
            fichas.append(Ficha("nome", "sqrt", i))
            i += 1
        elif texto[i : i + 2] in (MENOR_IGUAL, MAIOR_IGUAL):
            fichas.append(Ficha("sinal", texto[i : i + 2], i))
            i += 2
        elif texto[i : i + 2] == "**":
            fichas.append(Ficha("sinal", "^", i))
            i += 2
        elif letra in trocas:
            fichas.append(Ficha("sinal", trocas[letra], i))
            i += 1
        elif letra in "+-*/^()=":
            fichas.append(Ficha("sinal", letra, i))
            i += 1
        elif letra in "<>":
            raise ErroDeFormula(f"Use {letra}= em vez de {letra}.")
        else:
            raise ErroDeFormula(f"Não sei ler o sinal {letra}.")
    if len(fichas) > _MAX_FICHAS:
        raise ErroDeFormula("A fórmula está grande demais: quebre em dois blocos.")
    fichas.append(Ficha("fim", "", len(texto)))
    return fichas


class _Leitor:
    """Leitura de cima para baixo: cada nível da conta é uma função."""

    def __init__(self, fichas: list[Ficha]) -> None:
        self.fichas = fichas
        self.i = 0
        self.profundidade = 0
        self.letras: list[str] = []

    @property
    def atual(self) -> Ficha:
        return self.fichas[self.i]

    def andar(self) -> Ficha:
        ficha = self.atual
        self.i += 1
        return ficha

    def e_sinal(self, *sinais: str) -> bool:
        return self.atual.tipo == "sinal" and self.atual.valor in sinais

    def soma(self) -> sp.Expr:
        self.profundidade += 1
        if self.profundidade > _MAX_PROFUNDIDADE:
            raise ErroDeFormula("Parênteses demais, um dentro do outro.")
        valor = self.termo()
        while self.e_sinal("+", "-"):
            sinal = self.andar().valor
            direita = self.termo()
            valor = valor + direita if sinal == "+" else valor - direita
        self.profundidade -= 1
        return valor

    def termo(self) -> sp.Expr:
        valor = self.unario()
        while True:
            if self.e_sinal("*", "/"):
                sinal = self.andar().valor
                direita = self.unario()
                if sinal == "/" and direita == 0:
                    raise ErroDeFormula("Divisão por zero.")
                valor = valor * direita if sinal == "*" else valor / direita
            elif self.atual.tipo in ("numero", "nome") or self.e_sinal("("):
                raise ErroDeFormula(
                    f"Falta o sinal de vezes antes de {self.atual.valor}: escreva 2*q, e não 2q."
                )
            else:
                return valor

    def unario(self) -> sp.Expr:
        if self.e_sinal("-"):
            self.andar()
            return -self.unario()
        if self.e_sinal("+"):
            self.andar()
            return self.unario()
        return self.potencia()

    def potencia(self) -> sp.Expr:
        base = self.atomo()
        if not self.e_sinal("^"):
            return base
        self.andar()
        expoente = self.unario()
        if expoente.is_number:
            if abs(expoente) > _MAX_EXPOENTE:
                raise ErroDeFormula(f"Expoente grande demais: o limite é {_MAX_EXPOENTE}.")
            if base.is_number and abs(base) > 10**6 and abs(expoente) > 6:
                raise ErroDeFormula("Esse número passa do que dá para calcular.")
        return base**expoente

    def atomo(self) -> sp.Expr:
        ficha = self.andar()
        if ficha.tipo == "numero":
            numero = sp.Rational(ficha.valor)
            if abs(numero) > _MAX_NUMERO:
                raise ErroDeFormula("Esse número passa do que dá para calcular.")
            return numero
        if ficha.tipo == "nome":
            return self.nome(ficha)
        if ficha.tipo == "sinal" and ficha.valor == "(":
            valor = self.soma()
            if not self.e_sinal(")"):
                raise ErroDeFormula("Falta fechar um parêntese.")
            self.andar()
            return valor
        if ficha.tipo == "fim":
            raise ErroDeFormula("A fórmula terminou antes da hora.")
        raise ErroDeFormula(f"Não esperava {ficha.valor} aqui.")

    def nome(self, ficha: Ficha) -> sp.Expr:
        nome = ficha.valor
        if self.e_sinal("("):
            if nome in ("log", "Log", "LOG"):
                raise ErroDeFormula("Use ln para o logaritmo natural, ou log10 para a base 10.")
            funcao = _FUNCOES.get(nome.lower())
            if funcao is None:
                raise ErroDeFormula(f"Não conheço a função {nome}.")
            self.andar()
            dentro = self.soma()
            if not self.e_sinal(")"):
                raise ErroDeFormula(f"Falta fechar o parêntese de {nome}.")
            self.andar()
            return funcao(dentro)
        if nome in ("pi", "π"):
            return sp.pi
        letra = _sem_grega(nome)
        if letra not in self.letras:
            self.letras.append(letra)
        return g.simbolo_de(letra)


@lru_cache(maxsize=256)
def ler(texto: str) -> Formula:
    """Do texto para a fórmula. Levanta ``ErroDeFormula`` dizendo o que está errado."""
    texto = texto.strip()
    if not texto:
        raise ErroDeFormula("Digite a fórmula.")
    if len(texto) > MAX_CARACTERES:
        raise ErroDeFormula(f"A fórmula passa de {MAX_CARACTERES} letras: quebre em dois blocos.")
    leitor = _Leitor(_fichas(texto))
    try:
        esquerda = leitor.soma()
        if not leitor.e_sinal(MENOR_IGUAL, MAIOR_IGUAL, IGUAL):
            if leitor.atual.tipo != "fim":
                raise ErroDeFormula(f"Não esperava {leitor.atual.valor} aqui.")
            if esquerda.has(sp.I, sp.zoo, sp.nan, sp.oo):
                raise ErroDeFormula("Essa conta não dá um número.")
            return Formula(texto, esquerda, letras=tuple(leitor.letras))
        sinal = leitor.andar().valor
        direita = leitor.soma()
        if leitor.atual.tipo != "fim":
            raise ErroDeFormula("Só cabe um sinal de comparação em cada fórmula.")
    except (ZeroDivisionError, TypeError, ValueError, OverflowError) as erro:
        if isinstance(erro, ErroDeFormula):
            raise
        raise ErroDeFormula("Essa conta não dá um número.") from erro
    if esquerda.has(sp.I, sp.zoo, sp.nan, sp.oo) or direita.has(sp.I, sp.zoo, sp.nan, sp.oo):
        raise ErroDeFormula("Essa conta não dá um número.")
    if sinal == IGUAL and esquerda.is_Symbol and esquerda not in direita.free_symbols:
        letras = tuple(x for x in leitor.letras if x != esquerda.name)
        return Formula(texto, direita, esquerda, sinal, esquerda.name, letras)
    return Formula(texto, direita, esquerda, sinal, letras=tuple(leitor.letras))


# ---------------------------------------------------------------------------
# Letras
# ---------------------------------------------------------------------------


def dimensoes_das_letras(texto: str | None) -> dict[str, str]:
    """O que a pessoa disse sobre as letras novas. Dado ruim vira nada, sem quebrar a tela."""
    try:
        dados = json.loads(texto or "{}")
    except ValueError:
        return {}
    if not isinstance(dados, Mapping):
        return {}
    return {str(k): str(v) for k, v in dados.items() if str(v) in g.EXPOENTES}


def dimensao_sugerida(nome: str, sistema: str) -> str:
    """O que uma letra costuma ser. Quem discordar troca no inspetor."""
    return _SUGESTOES.get(sistema, {}).get(nome, g.PURO)


def grandeza_da_letra(nome: str, sistema: str, dimensoes: Mapping[str, str]) -> Grandeza:
    conhecida = g.letras_conhecidas(sistema).get(nome)
    if conhecida is not None:
        return conhecida
    return Grandeza(
        nome,
        nome,
        f"Letra {nome} da fórmula",
        dimensoes.get(nome) or dimensao_sugerida(nome, sistema),
        "Letra da sua fórmula. Diga o que ela é no inspetor, para conferir as unidades.",
        zero_ok=True,
    )


def e_letra_nova(nome: str, sistema: str) -> bool:
    return nome not in g.letras_conhecidas(sistema)


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

Expoentes = tuple[Fraction, Fraction, Fraction, Fraction]
_PURO: Expoentes = (Fraction(0), Fraction(0), Fraction(0), Fraction(0))


def _expoentes(dimensao: str) -> Expoentes:
    a, b, c, d = g.EXPOENTES.get(dimensao, g.EXPOENTES[g.PURO])
    return Fraction(a), Fraction(b), Fraction(c), Fraction(d)


def texto_da_unidade(expoentes: Expoentes, sistema: str) -> str:
    """Pelo nome da grandeza, quando ela existe; senão pelas potências."""
    for dimensao in g.dimensoes_do_sistema(sistema):
        if _expoentes(dimensao) == expoentes:
            return g.ROTULOS_DAS_DIMENSOES[dimensao]
    partes = [
        f"{letra}^{e}" if e != 1 else letra
        for letra, e in zip("FLTΘ", expoentes, strict=True)
        if e != 0
    ]
    return "·".join(partes) if partes else "sem unidade"


def medir(expressao: sp.Expr, medidas: Mapping[str, Expoentes], sistema: str) -> Expoentes:
    """As potências de força, comprimento e tempo de uma conta."""
    if expressao.is_number:
        return _PURO
    if expressao.is_Symbol:
        return medidas.get(expressao.name, _PURO)
    if expressao.is_Add:
        partes = [medir(a, medidas, sistema) for a in expressao.args]
        for parte in partes[1:]:
            if parte != partes[0]:
                raise ErroDeUnidade(
                    f"As parcelas somadas não têm a mesma unidade: uma é "
                    f"{texto_da_unidade(partes[0], sistema)}, outra é "
                    f"{texto_da_unidade(parte, sistema)}."
                )
        return partes[0]
    if expressao.is_Mul:
        total = _PURO
        for a in expressao.args:
            parte = medir(a, medidas, sistema)
            total = (
                total[0] + parte[0],
                total[1] + parte[1],
                total[2] + parte[2],
                total[3] + parte[3],
            )
        return total
    if expressao.is_Pow:
        base = medir(expressao.base, medidas, sistema)
        if base == _PURO:
            if medir(expressao.exp, medidas, sistema) != _PURO:
                raise ErroDeUnidade("O expoente precisa ser um número puro.")
            return _PURO
        if not expressao.exp.is_number:
            raise ErroDeUnidade("Base com unidade pede expoente numérico.")
        expoente = Fraction(float(expressao.exp)).limit_denominator(1000)
        return (base[0] * expoente, base[1] * expoente, base[2] * expoente, base[3] * expoente)
    if isinstance(expressao, sp.Abs):
        return medir(expressao.args[0], medidas, sistema)
    if isinstance(expressao, sp.Function):
        for argumento in expressao.args:
            if medir(argumento, medidas, sistema) != _PURO:
                raise ErroDeUnidade(
                    f"{expressao.func.__name__} pede um número puro dentro do parêntese."
                )
        return _PURO
    return _PURO


def _medidas(formula: Formula, sistema: str, dimensoes: Mapping[str, str]) -> dict[str, Expoentes]:
    nomes = list(formula.letras)
    if formula.nome:
        nomes.append(formula.nome)
    return {
        nome: _expoentes(grandeza_da_letra(nome, sistema, dimensoes).dimensao) for nome in nomes
    }


def dimensoes_possiveis(formula: Formula, sistema: str, dimensoes: Mapping[str, str]) -> list[str]:
    """As grandezas do sistema que têm a unidade do resultado: medida e altura são metros iguais."""
    try:
        medida = medir(formula.direita, _medidas(formula, sistema, dimensoes), sistema)
    except ErroDeUnidade:
        return list(g.dimensoes_do_sistema(sistema))
    iguais = [d for d in g.dimensoes_do_sistema(sistema) if _expoentes(d) == medida]
    return iguais or [g.PURO]


def dimensao_da_saida(
    formula: Formula, sistema: str, dimensoes: Mapping[str, str], escolhida: str | None
) -> str:
    """A grandeza da bolinha de saída: a do nome, a escolhida, ou a que a conta dá."""
    if formula.nome and not e_letra_nova(formula.nome, sistema):
        return grandeza_da_letra(formula.nome, sistema, dimensoes).dimensao
    possiveis = dimensoes_possiveis(formula, sistema, dimensoes)
    return escolhida if escolhida in possiveis else possiveis[0]


def problemas_de_unidade(formula: Formula, sistema: str, dimensoes: Mapping[str, str]) -> list[str]:
    """O que não fecha. Lista vazia quer dizer que as unidades conferem."""
    medidas = _medidas(formula, sistema, dimensoes)
    try:
        direita = medir(formula.direita, medidas, sistema)
        # Saída com nome novo: a unidade dela é a que a conta der.
        nome_novo = bool(formula.nome) and e_letra_nova(formula.nome, sistema)
        if formula.esquerda is None or nome_novo:
            return []
        esquerda = medir(formula.esquerda, medidas, sistema)
    except ErroDeUnidade as erro:
        return [str(erro)]
    if esquerda != direita:
        return [
            f"Os dois lados não têm a mesma unidade: à esquerda {texto_da_unidade(esquerda, sistema)}, "
            f"à direita {texto_da_unidade(direita, sistema)}."
        ]
    return []
