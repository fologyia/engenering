"""Esboço paramétrico: pontos, linhas, arcos e círculos presos por restrições e cotas.

Funciona como o esboço de um CAD paramétrico. A cota segura o valor: mudar a cota move o desenho, e
o que não está preso por nada fica livre (azul na prancheta) até alguém prender. Uma cota pode ser um
número, uma letra ou uma conta com letras (``d``, ``2*d``, ``L/2 - 10``): as letras são as variáveis
do esboço, e é por elas que o Montador e o teste do desenho mexem na forma.

**Incógnitas.** x e y de cada ponto e o raio de cada círculo. O arco é centro, início e fim, com a
condição de os dois raios serem iguais. O ponto ``O`` é a origem, fixa em (0, 0).

**Equações.** Cada restrição e cada cota dá uma ou duas equações, todas em mm: as de ângulo vêm
multiplicadas pelo tamanho do desenho, para pesar como as outras.

**Solver.** Newton com o passo de menor norma, ``Δ = −Jᵀ(JJᵀ + μI)⁻¹F``: com menos equações que
incógnitas, anda o mínimo para cumprir tudo, e o que está livre fica onde está. A cota que muda muito
é levada aos poucos (continuação), para o desenho não pular para outra forma. A derivada é numérica,
por diferença central. O mesmo método está em ``components/esboco/solver.js``, para a prancheta, e
os testes conferem que os dois dão os mesmos números.

Aqui tudo trabalha com ``k`` conjuntos de valores de uma vez (matrizes ``(k, n)``): o teste do
desenho e a busca do Montador resolvem o mesmo esboço para centenas de valores das letras juntos.

Só usa numpy.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Nomes
# ---------------------------------------------------------------------------

ORIGEM = "O"

LINHA = "linha"
CIRCULO = "circulo"
ARCO = "arco"
CURVAS = (LINHA, CIRCULO, ARCO)

HORIZONTAL = "horizontal"
VERTICAL = "vertical"
PARALELA = "paralela"
PERPENDICULAR = "perpendicular"
TANGENTE = "tangente"
IGUAL = "igual"
NA_CURVA = "na_curva"
PONTO_MEDIO = "ponto_medio"
FIXO = "fixo"
COINCIDENTE = "coincidente"
CONCENTRICO = "concentrico"
SIMETRICO = "simetrico"
RESTRICOES = (
    HORIZONTAL,
    VERTICAL,
    PARALELA,
    PERPENDICULAR,
    TANGENTE,
    IGUAL,
    NA_CURVA,
    PONTO_MEDIO,
    FIXO,
    COINCIDENTE,
    CONCENTRICO,
    SIMETRICO,
)

DISTANCIA = "distancia"
PONTO_LINHA = "ponto_linha"
DIAMETRO = "diametro"
RAIO = "raio"
ANGULO = "angulo"
COTAS = (DISTANCIA, PONTO_LINHA, DIAMETRO, RAIO, ANGULO)

MODO_H = "h"
MODO_V = "v"
MODO_DIRETO = "d"
MODOS = (MODO_H, MODO_V, MODO_DIRETO)

#: Tangência entre dois círculos: um por fora do outro, ou um por dentro.
EXTERNA = "externa"
INTERNA = "interna"

NOME_DA_RESTRICAO = {
    HORIZONTAL: "horizontal",
    VERTICAL: "vertical",
    PARALELA: "paralelas",
    PERPENDICULAR: "perpendiculares",
    TANGENTE: "tangentes",
    IGUAL: "iguais",
    NA_CURVA: "ponto na curva",
    PONTO_MEDIO: "ponto no meio",
    FIXO: "ponto fixo",
    COINCIDENTE: "pontos juntos",
    CONCENTRICO: "mesmo centro",
    SIMETRICO: "simétricos",
}
NOME_DA_COTA = {
    DISTANCIA: "distância",
    PONTO_LINHA: "distância à linha",
    DIAMETRO: "diâmetro",
    RAIO: "raio",
    ANGULO: "ângulo",
}

# Os números do solver. Os mesmos de ``components/esboco/solver.js``: mudar lá e cá juntos.
MAX_ITERACOES = 30
MAX_CORTES = 10  # meias do passo quando o erro não cai
PASSO_DA_CONTINUACAO = 0.25  # fração da medida que a cota anda por vez
MAX_PASSOS = 40
TOLERANCIA = 1e-9  # vezes o tamanho do desenho, em mm
DERIVADA = 1e-6  # passo da derivada numérica, vezes o tamanho do desenho
AMORTECIMENTO = 1e-10  # μ, vezes a maior diagonal de JJᵀ
PASSO_MAXIMO = 0.5  # o maior passo de Newton, vezes o tamanho do desenho
PERDIDO = 1e3  # resíduo, vezes a tolerância, em que a continuação desiste
_ANGULO_DE_ESCALA = 15.0  # graus: a cota de ângulo anda em passos desta ordem


class ErroDeEsboco(ValueError):
    """O esboço não pode ser lido ou calculado: a mensagem diz o que corrigir."""


# ---------------------------------------------------------------------------
# Contas com letras
# ---------------------------------------------------------------------------

_NOME = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ_][A-Za-zÀ-ÖØ-öø-ÿ0-9_]*")
_NUMERO = re.compile(r"\d+(?:[.,]\d*)?(?:[eE][+-]?\d+)?|[.,]\d+(?:[eE][+-]?\d+)?")
RESERVADAS = frozenset({"pi"})
MAX_CARACTERES = 120


@dataclass(frozen=True)
class No:
    """Um pedaço da conta: número, letra, operação ou troca de sinal."""

    tipo: str  # "n", "v", "+", "-", "*", "/", "^", "neg"
    valor: float = 0.0
    nome: str = ""
    filhos: tuple[No, ...] = ()


def _fichas(texto: str) -> list[tuple[str, str, int]]:
    fichas: list[tuple[str, str, int]] = []
    i = 0
    while i < len(texto):
        c = texto[i]
        if c.isspace():
            i += 1
            continue
        if c in "+-*/^()":
            fichas.append(("op", c, i))
            i += 1
            continue
        numero = _NUMERO.match(texto, i)
        if numero:
            fichas.append(("n", numero.group(0).replace(",", "."), i))
            i = numero.end()
            continue
        nome = _NOME.match(texto, i)
        if nome:
            fichas.append(("v", nome.group(0), i))
            i = nome.end()
            continue
        raise ErroDeEsboco(f"Não entendi “{c}” na conta “{texto}”.")
    return fichas


class _Leitor:
    def __init__(self, texto: str) -> None:
        self.texto = texto
        self.fichas = _fichas(texto)
        self.i = 0

    def _olhar(self) -> tuple[str, str, int] | None:
        return self.fichas[self.i] if self.i < len(self.fichas) else None

    def _op(self, *ops: str) -> str | None:
        ficha = self._olhar()
        if ficha is not None and ficha[0] == "op" and ficha[1] in ops:
            self.i += 1
            return ficha[1]
        return None

    def ler(self) -> No:
        if not self.fichas:
            raise ErroDeEsboco("A conta está vazia.")
        no = self._soma()
        sobra = self._olhar()
        if sobra is not None:
            raise ErroDeEsboco(f"Sobrou “{sobra[1]}” no fim da conta “{self.texto}”.")
        return no

    def _soma(self) -> No:
        no = self._termo()
        while (op := self._op("+", "-")) is not None:
            no = No(op, filhos=(no, self._termo()))
        return no

    def _termo(self) -> No:
        no = self._unario()
        while (op := self._op("*", "/")) is not None:
            no = No(op, filhos=(no, self._unario()))
        return no

    def _unario(self) -> No:
        if self._op("-") is not None:
            return No("neg", filhos=(self._unario(),))
        if self._op("+") is not None:
            return self._unario()
        return self._potencia()

    def _potencia(self) -> No:
        base = self._atomo()
        if self._op("^") is not None:
            return No("^", filhos=(base, self._unario()))
        return base

    def _atomo(self) -> No:
        ficha = self._olhar()
        if ficha is None:
            raise ErroDeEsboco(f"A conta “{self.texto}” termina no meio.")
        tipo, texto, _ = ficha
        self.i += 1
        if tipo == "n":
            return No("n", valor=float(texto))
        if tipo == "v":
            if texto == "pi":
                return No("n", valor=math.pi)
            return No("v", nome=texto)
        if texto == "(":
            no = self._soma()
            if self._op(")") is None:
                raise ErroDeEsboco(f"Falta fechar o parêntese em “{self.texto}”.")
            return no
        raise ErroDeEsboco(f"“{texto}” fora do lugar na conta “{self.texto}”.")


def ler_conta(texto: str) -> No:
    """Lê ``2*d + 5``, ``L/2``, ``2,5*b``. Sem ``eval``: só números, letras e + − × ÷ ^."""
    texto = str(texto).strip()
    if len(texto) > MAX_CARACTERES:
        raise ErroDeEsboco(f"A conta passa de {MAX_CARACTERES} caracteres.")
    return _Leitor(texto).ler()


def letras_da_conta(no: No) -> set[str]:
    if no.tipo == "v":
        return {no.nome}
    saida: set[str] = set()
    for filho in no.filhos:
        saida |= letras_da_conta(filho)
    return saida


def avaliar_conta(no: No, valores: Mapping[str, Any]) -> Any:
    """O número da conta. ``valores`` pode trazer vetores: a conta sai vetor do mesmo tamanho."""
    if no.tipo == "n":
        return no.valor
    if no.tipo == "v":
        if no.nome not in valores:
            raise ErroDeEsboco(f"A letra {no.nome} não tem valor: crie a variável {no.nome}.")
        return valores[no.nome]
    if no.tipo == "neg":
        return -avaliar_conta(no.filhos[0], valores)
    a = avaliar_conta(no.filhos[0], valores)
    b = avaliar_conta(no.filhos[1], valores)
    with np.errstate(all="ignore"):
        if no.tipo == "+":
            return a + b
        if no.tipo == "-":
            return a - b
        if no.tipo == "*":
            return a * b
        if no.tipo == "/":
            return (
                np.divide(a, b)
                if isinstance(b, np.ndarray) or isinstance(a, np.ndarray)
                else (a / b if b != 0 else math.nan)
            )
        return (
            np.power(a, b)
            if isinstance(a, np.ndarray) or isinstance(b, np.ndarray)
            else (_potencia(a, b))
        )


def _potencia(a: float, b: float) -> float:
    try:
        valor = a**b
    except (OverflowError, ZeroDivisionError):
        return math.nan
    return valor if isinstance(valor, float | int) else math.nan


#: O que uma regra de projeto pode medir no desenho, além das letras.
MEDIDAS_DA_REGRA = {
    "parede": "a menor distância entre contornos (furo até a borda, furo até furo)",
    "area": "a área da seção, em mm²",
    "largura": "a largura total, em x",
    "altura": "a altura total, em y",
}
_COMPARACOES = (">=", "<=", ">", "<")


@dataclass(frozen=True)
class Regra:
    texto: str
    esquerda: No
    comparacao: str  # ">=" ou "<="
    direita: No


def ler_regra(texto: str) -> Regra:
    """``parede >= 1,5*d``, ``d <= 0,6*h``: duas contas e uma comparação."""
    texto = str(texto).strip()
    for comparacao in _COMPARACOES:
        if comparacao in texto:
            esquerda, direita = texto.split(comparacao, 1)
            if any(c in direita for c in "<>"):
                break
            normal = ">=" if comparacao.startswith(">") else "<="
            return Regra(texto, ler_conta(esquerda), normal, ler_conta(direita))
    raise ErroDeEsboco(f"A regra “{texto}” precisa de >= ou <=, como parede >= 1,5*d.")


def letras_da_regra(regra: Regra) -> set[str]:
    return letras_da_conta(regra.esquerda) | letras_da_conta(regra.direita)


def folga_da_regra(regra: Regra, valores: Mapping[str, Any]) -> Any:
    """Positiva (ou zero) quando a regra vale: esquerda − direita, ou o contrário."""
    a = avaliar_conta(regra.esquerda, valores)
    b = avaliar_conta(regra.direita, valores)
    return a - b if regra.comparacao == ">=" else b - a


def nome_valido(nome: str) -> bool:
    return bool(_NOME.fullmatch(nome)) and nome not in RESERVADAS and nome not in MEDIDAS_DA_REGRA


# ---------------------------------------------------------------------------
# O esboço
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Curva:
    """``pontos``: (a, b) na linha, (centro,) no círculo, (centro, início, fim) no arco anti-horário."""

    id: str
    tipo: str
    pontos: tuple[str, ...]
    raio: float = 0.0  # só no círculo
    construcao: bool = False


@dataclass(frozen=True)
class Restricao:
    id: str
    tipo: str
    pontos: tuple[str, ...] = ()
    curvas: tuple[str, ...] = ()
    #: fixo: (x, y); tangente linha-círculo: (lado,); tangente de círculos: (±1,) com ``modo``.
    valores: tuple[float, ...] = ()
    modo: str = ""


@dataclass(frozen=True)
class Cota:
    """A cota que manda. ``referencia`` só mede, sem prender nada (aparece entre parênteses)."""

    id: str
    tipo: str
    pontos: tuple[str, ...] = ()
    curvas: tuple[str, ...] = ()
    modo: str = MODO_DIRETO
    sinal: float = 0.0  # 0 = ainda não decidido: sai da forma de agora
    expressao: str = "0"
    referencia: bool = False
    lugar: tuple[float, float] | None = None
    oculta: bool = False  # as repetidas de um padrão: prendem, mas não se desenham


@dataclass(frozen=True)
class Variavel:
    nome: str
    valor: float
    #: O que a letra é: "comprimento" (mm) ou "angulo" (graus). Sai da cota que a usa.
    tipo: str = "comprimento"
    #: A faixa em que a letra vai ser testada (no teste do desenho e na busca do Montador).
    de: float | None = None
    ate: float | None = None
    passo: float | None = None


@dataclass(frozen=True)
class Esboco:
    pontos: Mapping[str, tuple[float, float]]
    curvas: tuple[Curva, ...] = ()
    restricoes: tuple[Restricao, ...] = ()
    cotas: tuple[Cota, ...] = ()
    variaveis: tuple[Variavel, ...] = ()
    #: Regras de projeto: desigualdades que limitam o teste, como ``parede >= 1,5*d``.
    regras: tuple[str, ...] = ()

    def curva(self, cid: str) -> Curva:
        for curva in self.curvas:
            if curva.id == cid:
                return curva
        raise ErroDeEsboco(f"A curva {cid} não existe no esboço.")

    def valores(self) -> dict[str, float]:
        return {v.nome: v.valor for v in self.variaveis}

    def letras_usadas(self) -> list[str]:
        """As letras que as cotas usam, na ordem da tabela de variáveis."""
        usadas: set[str] = set()
        for cota in self.cotas:
            if not cota.referencia:
                usadas |= letras_da_conta(ler_conta(cota.expressao))
        return [v.nome for v in self.variaveis if v.nome in usadas]

    def com_valores(self, valores: Mapping[str, float]) -> Esboco:
        return replace(
            self,
            variaveis=tuple(
                replace(v, valor=float(valores[v.nome])) if v.nome in valores else v
                for v in self.variaveis
            ),
        )

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "versao": 1,
            "pontos": {pid: [x, y] for pid, (x, y) in self.pontos.items()},
            "curvas": [
                {
                    "id": c.id,
                    "tipo": c.tipo,
                    "pontos": list(c.pontos),
                    **({"raio": c.raio} if c.tipo == CIRCULO else {}),
                    **({"construcao": True} if c.construcao else {}),
                }
                for c in self.curvas
            ],
            "restricoes": [
                {
                    "id": r.id,
                    "tipo": r.tipo,
                    **({"pontos": list(r.pontos)} if r.pontos else {}),
                    **({"curvas": list(r.curvas)} if r.curvas else {}),
                    **({"valores": list(r.valores)} if r.valores else {}),
                    **({"modo": r.modo} if r.modo else {}),
                }
                for r in self.restricoes
            ],
            "cotas": [
                {
                    "id": c.id,
                    "tipo": c.tipo,
                    **({"pontos": list(c.pontos)} if c.pontos else {}),
                    **({"curvas": list(c.curvas)} if c.curvas else {}),
                    "modo": c.modo,
                    "sinal": c.sinal,
                    "expressao": c.expressao,
                    **({"referencia": True} if c.referencia else {}),
                    **({"lugar": list(c.lugar)} if c.lugar is not None else {}),
                    **({"oculta": True} if c.oculta else {}),
                }
                for c in self.cotas
            ],
            "variaveis": [
                {
                    "nome": v.nome,
                    "valor": v.valor,
                    "tipo": v.tipo,
                    **{
                        k: getattr(v, k)
                        for k in ("de", "ate", "passo")
                        if getattr(v, k) is not None
                    },
                }
                for v in self.variaveis
            ],
            **({"regras": list(self.regras)} if self.regras else {}),
        }


def _numero(valor: Any, rotulo: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroDeEsboco(f"{rotulo}: {valor!r} não é número.") from None
    if not math.isfinite(numero):
        raise ErroDeEsboco(f"{rotulo}: o valor não é um número finito.")
    return numero


def _textos(valor: Any) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        return (valor,)
    return tuple(str(v) for v in valor)


def esboco_de_dicionario(dados: Mapping[str, Any]) -> Esboco:
    """Valida o esboço que vem da prancheta ou do catálogo. Dado ruim vira mensagem, não exceção solta."""
    if not isinstance(dados, Mapping):
        raise ErroDeEsboco("O esboço não veio no formato esperado.")
    brutos = dados.get("pontos") or {}
    if isinstance(brutos, Mapping):
        itens = list(brutos.items())
    else:
        itens = [(p.get("id"), (p.get("x"), p.get("y"))) for p in brutos if isinstance(p, Mapping)]
    pontos: dict[str, tuple[float, float]] = {ORIGEM: (0.0, 0.0)}
    for pid, xy in itens:
        pid = str(pid)
        if pid == ORIGEM:
            continue
        if not isinstance(xy, Sequence) or len(xy) != 2:
            raise ErroDeEsboco(f"O ponto {pid} está sem x e y.")
        pontos[pid] = (_numero(xy[0], f"O ponto {pid}"), _numero(xy[1], f"O ponto {pid}"))

    def exigir_pontos(ids: tuple[str, ...], quem: str) -> None:
        for pid in ids:
            if pid not in pontos:
                raise ErroDeEsboco(f"{quem} usa o ponto {pid}, que não existe.")

    curvas: list[Curva] = []
    vistas: set[str] = set()
    for bruta in dados.get("curvas") or ():
        cid = str(bruta.get("id", ""))
        tipo = str(bruta.get("tipo", ""))
        if not cid or cid in vistas:
            raise ErroDeEsboco("Há curva sem nome ou com nome repetido.")
        vistas.add(cid)
        ids = _textos(bruta.get("pontos"))
        precisa = {LINHA: 2, CIRCULO: 1, ARCO: 3}.get(tipo)
        if precisa is None:
            raise ErroDeEsboco(f"Tipo de curva desconhecido: {tipo!r}.")
        if len(ids) != precisa:
            raise ErroDeEsboco(f"A curva {cid} precisa de {precisa} pontos.")
        exigir_pontos(ids, f"A curva {cid}")
        if len(set(ids)) != len(ids):
            raise ErroDeEsboco(f"A curva {cid} usa o mesmo ponto duas vezes.")
        raio = 0.0
        if tipo == CIRCULO:
            raio = _numero(bruta.get("raio"), f"O raio do círculo {cid}")
            if raio <= 0.0:
                raise ErroDeEsboco(f"O círculo {cid} precisa de raio maior que zero.")
        curvas.append(Curva(cid, tipo, ids, raio, bool(bruta.get("construcao", False))))
    por_id = {c.id: c for c in curvas}

    def exigir_curvas(ids: tuple[str, ...], quem: str) -> None:
        for cid in ids:
            if cid not in por_id:
                raise ErroDeEsboco(f"{quem} usa a curva {cid}, que não existe.")

    restricoes: list[Restricao] = []
    for bruta in dados.get("restricoes") or ():
        tipo = str(bruta.get("tipo", ""))
        if tipo not in RESTRICOES:
            raise ErroDeEsboco(f"Restrição desconhecida: {tipo!r}.")
        rid = str(bruta.get("id", f"r{len(restricoes) + 1}"))
        ids_p, ids_c = _textos(bruta.get("pontos")), _textos(bruta.get("curvas"))
        exigir_pontos(ids_p, f"A restrição {rid}")
        exigir_curvas(ids_c, f"A restrição {rid}")
        valores = tuple(_numero(v, f"A restrição {rid}") for v in bruta.get("valores") or ())
        restricoes.append(Restricao(rid, tipo, ids_p, ids_c, valores, str(bruta.get("modo", ""))))

    cotas: list[Cota] = []
    for bruta in dados.get("cotas") or ():
        tipo = str(bruta.get("tipo", ""))
        if tipo not in COTAS:
            raise ErroDeEsboco(f"Cota desconhecida: {tipo!r}.")
        did = str(bruta.get("id", f"d{len(cotas) + 1}"))
        ids_p, ids_c = _textos(bruta.get("pontos")), _textos(bruta.get("curvas"))
        exigir_pontos(ids_p, f"A cota {did}")
        exigir_curvas(ids_c, f"A cota {did}")
        modo = str(bruta.get("modo", MODO_DIRETO))
        if modo not in MODOS:
            modo = MODO_DIRETO
        expressao = str(bruta.get("expressao", "0")).strip() or "0"
        ler_conta(expressao)  # conta ruim para aqui, com a mensagem certa
        lugar = bruta.get("lugar")
        lugar_xy = (
            (_numero(lugar[0], "O lugar da cota"), _numero(lugar[1], "O lugar da cota"))
            if isinstance(lugar, Sequence) and len(lugar) == 2
            else None
        )
        cotas.append(
            Cota(
                did,
                tipo,
                ids_p,
                ids_c,
                modo,
                _numero(bruta.get("sinal", 0.0), f"A cota {did}"),
                expressao,
                bool(bruta.get("referencia", False)),
                lugar_xy,
                bool(bruta.get("oculta", False)),
            )
        )

    variaveis: list[Variavel] = []
    nomes: set[str] = set()
    for bruta in dados.get("variaveis") or ():
        nome = str(bruta.get("nome", "")).strip()
        if not nome_valido(nome):
            raise ErroDeEsboco(f"“{nome}” não serve de letra: comece por letra, sem espaço.")
        if nome in nomes:
            raise ErroDeEsboco(f"A letra {nome} aparece duas vezes na tabela.")
        nomes.add(nome)
        tipo = "angulo" if bruta.get("tipo") == "angulo" else "comprimento"
        faixa = {
            k: _numero(bruta[k], f"A faixa de {nome}")
            for k in ("de", "ate", "passo")
            if bruta.get(k) is not None
        }
        variaveis.append(
            Variavel(nome, _numero(bruta.get("valor"), f"A letra {nome}"), tipo, **faixa)
        )
    for cota in cotas:
        if cota.referencia:
            continue
        faltam = letras_da_conta(ler_conta(cota.expressao)) - nomes
        if faltam:
            raise ErroDeEsboco(
                f"A cota {cota.id} usa {', '.join(sorted(faltam))}, que não está na tabela de letras."
            )
    regras = tuple(str(r).strip() for r in dados.get("regras") or () if str(r).strip())
    for regra in regras:
        faltam = letras_da_regra(ler_regra(regra)) - nomes - set(MEDIDAS_DA_REGRA)
        if faltam:
            raise ErroDeEsboco(
                f"A regra “{regra}” usa {', '.join(sorted(faltam))}, que não é letra do esboço "
                f"nem medida ({', '.join(MEDIDAS_DA_REGRA)})."
            )
    return Esboco(pontos, tuple(curvas), tuple(restricoes), tuple(cotas), tuple(variaveis), regras)


# ---------------------------------------------------------------------------
# Sistema de equações
# ---------------------------------------------------------------------------

#: (V de (k, colunas), alvo de (k,)) → (k,); as de cota levam parâmetros fixos por padrão.
Funcao = Callable[..., np.ndarray]


@dataclass(frozen=True)
class Equacao:
    origem: str  # id da restrição ou da cota
    colunas: tuple[int, ...]
    f: Funcao  # (V de (k, colunas), alvo de (k,)) → (k,)
    conta: No | None = None  # a cota que manda: o alvo sai dela
    angulo: bool = False  # alvo em graus


def _hyp(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    return np.sqrt(dx * dx + dy * dy)


def _distancia_com_sinal(px, py, ax, ay, bx, by):
    """Distância do ponto à reta AB, positiva à esquerda de quem vai de A para B."""
    dx, dy = bx - ax, by - ay
    return (dx * (py - ay) - dy * (px - ax)) / _hyp(dx, dy)


def _girar(angulo: np.ndarray) -> np.ndarray:
    """O ângulo levado para (−π, π]."""
    return angulo - 2.0 * math.pi * np.round(angulo / (2.0 * math.pi))


class Sistema:
    """As incógnitas e as equações de um esboço. As colunas: x e y de cada ponto, raio de cada círculo."""

    def __init__(self, esboco: Esboco) -> None:
        self.esboco = esboco
        self.colunas: dict[str, int] = {}
        valores: list[float] = []
        for pid, (x, y) in esboco.pontos.items():
            self.colunas[pid] = len(valores)
            valores.extend((x, y))
        self.raios: dict[str, int] = {}
        for curva in esboco.curvas:
            if curva.tipo == CIRCULO:
                self.raios[curva.id] = len(valores)
                valores.append(curva.raio)
        self.q0 = np.array(valores, dtype=float)
        self.n = len(valores)
        self.tamanho = _tamanho(esboco)
        self._por_id = {c.id: c for c in esboco.curvas}
        self.equacoes: list[Equacao] = []
        self._montar()
        self.m = len(self.equacoes)

    # -- acesso -------------------------------------------------------------------------------------

    def _ponto(self, pid: str) -> tuple[int, int]:
        i = self.colunas[pid]
        return i, i + 1

    def _linha(self, cid: str) -> tuple[int, ...]:
        curva = self._por_id[cid]
        if curva.tipo != LINHA:
            raise ErroDeEsboco(f"{cid} precisa ser uma linha.")
        return (*self._ponto(curva.pontos[0]), *self._ponto(curva.pontos[1]))

    def _circular(self, cid: str) -> tuple[tuple[int, ...], Callable, Callable]:
        """Colunas, e como tirar delas o centro e o raio: (cx, cy, r) no círculo, (cx, cy, ax, ay) no arco."""
        curva = self._por_id[cid]
        if curva.tipo == CIRCULO:
            colunas: tuple[int, ...] = (*self._ponto(curva.pontos[0]), self.raios[cid])

            def raio_c(v: np.ndarray, o: int) -> np.ndarray:
                return v[:, o + 2]

            return colunas, raio_c, _centro
        if curva.tipo == ARCO:
            colunas = (*self._ponto(curva.pontos[0]), *self._ponto(curva.pontos[1]))

            def raio_a(v: np.ndarray, o: int) -> np.ndarray:
                return _hyp(v[:, o + 2] - v[:, o], v[:, o + 3] - v[:, o + 1])

            return colunas, raio_a, _centro
        raise ErroDeEsboco(f"{cid} precisa ser círculo ou arco.")

    def _juntar(self, origem: str, colunas: Iterable[int], f: Funcao, **extra: Any) -> None:
        self.equacoes.append(Equacao(origem, tuple(colunas), f, **extra))

    # -- montagem -----------------------------------------------------------------------------------

    def _montar(self) -> None:
        e = self.esboco
        tamanho = self.tamanho
        o = self._ponto(ORIGEM)
        self._juntar("origem", o[:1], lambda v, a: v[:, 0])
        self._juntar("origem", o[1:], lambda v, a: v[:, 0])
        for curva in e.curvas:
            if curva.tipo == ARCO:
                c, ini, fim = (self._ponto(p) for p in curva.pontos)
                self._juntar(
                    curva.id,
                    (*c, *ini, *fim),
                    lambda v, a: (
                        _hyp(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1])
                        - _hyp(v[:, 4] - v[:, 0], v[:, 5] - v[:, 1])
                    ),
                )
        for r in e.restricoes:
            self._restricao(r, tamanho)
        for cota in e.cotas:
            if not cota.referencia:
                self._cota(cota)

    def _restricao(self, r: Restricao, tamanho: float) -> None:
        t = r.tipo
        if t in (HORIZONTAL, VERTICAL):
            for cid in r.curvas:
                cols = self._linha(cid)
                if t == HORIZONTAL:
                    self._juntar(r.id, cols, lambda v, a: v[:, 3] - v[:, 1])
                else:
                    self._juntar(r.id, cols, lambda v, a: v[:, 2] - v[:, 0])
            if not r.curvas and len(r.pontos) == 2:  # dois pontos na mesma horizontal (vertical)
                cols = (*self._ponto(r.pontos[0]), *self._ponto(r.pontos[1]))
                k = 1 if t == HORIZONTAL else 0
                self._juntar(r.id, cols, lambda v, a, k=k: v[:, 2 + k] - v[:, k])
        elif t in (COINCIDENTE, CONCENTRICO):
            if t == CONCENTRICO:
                centros = [self._por_id[c].pontos[0] for c in r.curvas]
            else:
                centros = list(r.pontos)
            for outro in centros[1:]:
                cols = (*self._ponto(centros[0]), *self._ponto(outro))
                self._juntar(r.id, cols, lambda v, a: v[:, 2] - v[:, 0])
                self._juntar(r.id, cols, lambda v, a: v[:, 3] - v[:, 1])
        elif t == NA_CURVA:
            p = self._ponto(r.pontos[0])
            curva = self._por_id[r.curvas[0]]
            if curva.tipo == LINHA:
                self._juntar(
                    r.id,
                    (*p, *self._linha(curva.id)),
                    lambda v, a: _distancia_com_sinal(*(v[:, i] for i in range(6))),
                )
            else:
                cols, raio, centro = self._circular(curva.id)

                def na_circ(v: np.ndarray, a: np.ndarray, raio=raio) -> np.ndarray:
                    cx, cy = v[:, 2], v[:, 3]
                    return _hyp(v[:, 0] - cx, v[:, 1] - cy) - raio(v, 2)

                self._juntar(r.id, (*p, *cols), na_circ)
        elif t == PONTO_MEDIO:
            cols = (*self._ponto(r.pontos[0]), *self._linha(r.curvas[0]))
            self._juntar(r.id, cols, lambda v, a: v[:, 0] - (v[:, 2] + v[:, 4]) / 2.0)
            self._juntar(r.id, cols, lambda v, a: v[:, 1] - (v[:, 3] + v[:, 5]) / 2.0)
        elif t == FIXO:
            x0, y0 = (r.valores + (0.0, 0.0))[:2] if r.valores else self.esboco.pontos[r.pontos[0]]
            p = self._ponto(r.pontos[0])
            self._juntar(r.id, p[:1], lambda v, a, x0=x0: v[:, 0] - x0)
            self._juntar(r.id, p[1:], lambda v, a, y0=y0: v[:, 0] - y0)
        elif t in (PARALELA, PERPENDICULAR):
            base = self._linha(r.curvas[0])
            for outra in r.curvas[1:]:
                cols = (*base, *self._linha(outra))
                if t == PARALELA:

                    def f(v: np.ndarray, a: np.ndarray) -> np.ndarray:
                        d1x, d1y = v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]
                        d2x, d2y = v[:, 6] - v[:, 4], v[:, 7] - v[:, 5]
                        return tamanho * (d1x * d2y - d1y * d2x) / (_hyp(d1x, d1y) * _hyp(d2x, d2y))

                else:

                    def f(v: np.ndarray, a: np.ndarray) -> np.ndarray:
                        d1x, d1y = v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]
                        d2x, d2y = v[:, 6] - v[:, 4], v[:, 7] - v[:, 5]
                        return tamanho * (d1x * d2x + d1y * d2y) / (_hyp(d1x, d1y) * _hyp(d2x, d2y))

                self._juntar(r.id, cols, f)
        elif t == IGUAL:
            primeira = self._por_id[r.curvas[0]]
            for cid in r.curvas[1:]:
                segunda = self._por_id[cid]
                if primeira.tipo == LINHA and segunda.tipo == LINHA:
                    cols = (*self._linha(primeira.id), *self._linha(cid))
                    self._juntar(
                        r.id,
                        cols,
                        lambda v, a: (
                            _hyp(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1])
                            - _hyp(v[:, 6] - v[:, 4], v[:, 7] - v[:, 5])
                        ),
                    )
                elif primeira.tipo != LINHA and segunda.tipo != LINHA:
                    c1, r1, _ = self._circular(primeira.id)
                    c2, r2, _ = self._circular(cid)
                    n1 = len(c1)
                    self._juntar(
                        r.id, (*c1, *c2), lambda v, a, r1=r1, r2=r2, n1=n1: r1(v, 0) - r2(v, n1)
                    )
                else:
                    raise ErroDeEsboco("Iguais: duas linhas, ou dois círculos e arcos.")
        elif t == TANGENTE:
            self._tangente(r)
        elif t == SIMETRICO:
            cols = (*self._ponto(r.pontos[0]), *self._ponto(r.pontos[1]), *self._linha(r.curvas[0]))

            def meio_na_linha(v: np.ndarray, a: np.ndarray) -> np.ndarray:
                mx, my = (v[:, 0] + v[:, 2]) / 2.0, (v[:, 1] + v[:, 3]) / 2.0
                return _distancia_com_sinal(mx, my, v[:, 4], v[:, 5], v[:, 6], v[:, 7])

            def de_lado(v: np.ndarray, a: np.ndarray) -> np.ndarray:
                dx, dy = v[:, 6] - v[:, 4], v[:, 7] - v[:, 5]
                return ((v[:, 2] - v[:, 0]) * dx + (v[:, 3] - v[:, 1]) * dy) / _hyp(dx, dy)

            self._juntar(r.id, cols, meio_na_linha)
            self._juntar(r.id, cols, de_lado)

    def _tangente(self, r: Restricao) -> None:
        c1, c2 = (self._por_id[c] for c in r.curvas[:2])
        if c1.tipo == LINHA and c2.tipo == LINHA:
            raise ErroDeEsboco("Tangente: uma linha e um círculo, ou dois círculos.")
        if c1.tipo != LINHA and c2.tipo == LINHA:
            c1, c2 = c2, c1
        if c1.tipo == LINHA:
            linha = self._linha(c1.id)
            cols, raio, _ = self._circular(c2.id)
            comum = [
                i for i, p in enumerate(c1.pontos[:2]) if c2.tipo == ARCO and p in c2.pontos[1:]
            ]
            if comum:
                # Ponta comum: o raio até ela fica de pé sobre a reta. "Distância ao centro = raio"
                # dá a mesma tangente, mas tem derivada zero ao longo da reta e deixaria a ponta
                # solta para a contagem de graus de liberdade.
                k = 2 * comum[0]

                def em_pe(v: np.ndarray, a: np.ndarray, k=k) -> np.ndarray:
                    dx, dy = v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]
                    return ((v[:, k] - v[:, 4]) * dx + (v[:, k + 1] - v[:, 5]) * dy) / _hyp(dx, dy)

                self._juntar(r.id, (*linha, *cols), em_pe)
                return
            lado = r.valores[0] if r.valores else self._lado_da_tangente(linha, cols, raio)

            def f(v: np.ndarray, a: np.ndarray, raio=raio, lado=lado) -> np.ndarray:
                d = _distancia_com_sinal(v[:, 4], v[:, 5], v[:, 0], v[:, 1], v[:, 2], v[:, 3])
                return lado * d - raio(v, 4)

            self._juntar(r.id, (*linha, *cols), f)
            return
        cols1, raio1, _ = self._circular(c1.id)
        cols2, raio2, _ = self._circular(c2.id)
        n1 = len(cols1)
        q = self.q0[list((*cols1, *cols2))][None, :]
        distancia = float(_hyp(q[:, n1] - q[:, 0], q[:, n1 + 1] - q[:, 1])[0])
        ra, rb = float(raio1(q, 0)[0]), float(raio2(q, n1)[0])
        modo = r.modo or (
            EXTERNA if abs(distancia - ra - rb) <= abs(distancia - abs(ra - rb)) else INTERNA
        )
        sinal = r.valores[0] if r.valores else (1.0 if ra >= rb else -1.0)

        def g(v: np.ndarray, a: np.ndarray) -> np.ndarray:
            d = _hyp(v[:, n1] - v[:, 0], v[:, n1 + 1] - v[:, 1])
            if modo == EXTERNA:
                return d - raio1(v, 0) - raio2(v, n1)
            return d - sinal * (raio1(v, 0) - raio2(v, n1))

        self._juntar(r.id, (*cols1, *cols2), g)

    def _lado_da_tangente(
        self, linha: tuple[int, ...], cols: tuple[int, ...], raio: Callable
    ) -> float:
        q = self.q0
        d = _distancia_com_sinal(q[cols[0]], q[cols[1]], *(q[i] for i in linha))
        return 1.0 if d >= 0.0 else -1.0

    def _cota(self, cota: Cota) -> None:
        conta = ler_conta(cota.expressao)
        t = cota.tipo
        q = self.q0
        cols: tuple[int, ...]
        if t == DISTANCIA:
            ids = list(cota.pontos)
            if len(ids) < 2 and cota.curvas:  # comprimento de uma linha
                ids = list(self._por_id[cota.curvas[0]].pontos[:2])
            if len(ids) != 2:
                raise ErroDeEsboco(f"A cota {cota.id} precisa de dois pontos.")
            cols = (*self._ponto(ids[0]), *self._ponto(ids[1]))
            if cota.modo in (MODO_H, MODO_V):
                k = 0 if cota.modo == MODO_H else 1
                sinal = cota.sinal or (1.0 if q[cols[2 + k]] - q[cols[k]] >= 0.0 else -1.0)
                self._juntar(
                    cota.id,
                    cols,
                    lambda v, a, k=k, s=sinal: (v[:, 2 + k] - v[:, k]) - s * a,
                    conta=conta,
                )
            else:
                self._juntar(
                    cota.id,
                    cols,
                    lambda v, a: _hyp(v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]) - a,
                    conta=conta,
                )
        elif t == PONTO_LINHA:
            cols = (*self._ponto(cota.pontos[0]), *self._linha(cota.curvas[0]))
            d0 = _distancia_com_sinal(*(q[i] for i in cols))
            sinal = cota.sinal or (1.0 if d0 >= 0.0 else -1.0)
            self._juntar(
                cota.id,
                cols,
                lambda v, a, s=sinal: s * _distancia_com_sinal(*(v[:, i] for i in range(6))) - a,
                conta=conta,
            )
        elif t in (DIAMETRO, RAIO):
            cols, raio, _ = self._circular(cota.curvas[0])
            fator = 2.0 if t == DIAMETRO else 1.0
            self._juntar(
                cota.id,
                cols,
                lambda v, a, raio=raio, fator=fator: fator * raio(v, 0) - a,
                conta=conta,
            )
        elif t == ANGULO:
            cols = (*self._linha(cota.curvas[0]), *self._linha(cota.curvas[1]))
            tamanho = self.tamanho
            v0 = q[list(cols)][None, :]
            a0 = float(_angulo_entre(v0)[0])
            sinal = cota.sinal or (1.0 if a0 >= 0.0 else -1.0)
            self._juntar(
                cota.id,
                cols,
                lambda v, a, s=sinal: tamanho * _girar(_angulo_entre(v) - s * np.radians(a)),
                conta=conta,
                angulo=True,
            )

    # -- contas -------------------------------------------------------------------------------------

    def alvos(self, valores: Mapping[str, Any], k: int) -> np.ndarray:
        """(k, m): o valor que cada cota pede; zero nas restrições."""
        saida = np.zeros((k, self.m))
        for i, eq in enumerate(self.equacoes):
            if eq.conta is not None:
                saida[:, i] = np.broadcast_to(
                    np.asarray(avaliar_conta(eq.conta, valores), float), (k,)
                )
        return saida

    def residuos(self, q: np.ndarray, alvos: np.ndarray) -> np.ndarray:
        saida = np.empty((q.shape[0], self.m))
        with np.errstate(all="ignore"):
            for i, eq in enumerate(self.equacoes):
                saida[:, i] = eq.f(q[:, eq.colunas], alvos[:, i])
        return saida

    def jacobiano(self, q: np.ndarray, alvos: np.ndarray) -> np.ndarray:
        k = q.shape[0]
        saida = np.zeros((k, self.m, self.n))
        h = DERIVADA * self.tamanho
        with np.errstate(all="ignore"):
            for i, eq in enumerate(self.equacoes):
                v = q[:, eq.colunas]
                alvo = alvos[:, i]
                for j, coluna in enumerate(eq.colunas):
                    mais, menos = v.copy(), v.copy()
                    mais[:, j] += h
                    menos[:, j] -= h
                    saida[:, i, coluna] += (eq.f(mais, alvo) - eq.f(menos, alvo)) / (2.0 * h)
        return saida


def _centro(v: np.ndarray, o: int) -> tuple[np.ndarray, np.ndarray]:
    return v[:, o], v[:, o + 1]


def _angulo_entre(v: np.ndarray) -> np.ndarray:
    d1x, d1y = v[:, 2] - v[:, 0], v[:, 3] - v[:, 1]
    d2x, d2y = v[:, 6] - v[:, 4], v[:, 7] - v[:, 5]
    return np.arctan2(d1x * d2y - d1y * d2x, d1x * d2x + d1y * d2y)


def _tamanho(esboco: Esboco) -> float:
    """O tamanho do desenho, em mm: a diagonal da caixa de tudo, ou 100 sem nada."""
    xs = [x for x, _ in esboco.pontos.values()]
    ys = [y for _, y in esboco.pontos.values()]
    for curva in esboco.curvas:
        if curva.tipo == CIRCULO:
            cx, cy = esboco.pontos[curva.pontos[0]]
            xs += [cx - curva.raio, cx + curva.raio]
            ys += [cy - curva.raio, cy + curva.raio]
    diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return diagonal if diagonal > 1e-9 else 100.0


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Solucao:
    q: np.ndarray  # (k, n)
    convergiu: np.ndarray  # (k,) bool
    erro: np.ndarray  # (k,) o maior resíduo, em mm


def newton(sistema: Sistema, q: np.ndarray, alvos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Passos de menor norma até as equações fecharem. Devolve (q, maior resíduo)."""
    q = np.array(q, dtype=float)
    k = q.shape[0]
    if sistema.m == 0:
        return q, np.zeros(k)
    tolerancia = TOLERANCIA * sistema.tamanho
    limite = PASSO_MAXIMO * sistema.tamanho
    identidade = np.eye(sistema.m)
    f = sistema.residuos(q, alvos)
    ativo = np.ones(k, dtype=bool)  # quem parou de melhorar não tenta de novo
    for _ in range(MAX_ITERACOES):
        erro = np.max(np.abs(f), axis=1)
        erro = np.where(np.isfinite(erro), erro, np.inf)
        falta = (erro > tolerancia) & ativo
        if not falta.any():
            break
        idx = np.flatnonzero(falta & np.isfinite(erro))
        if not len(idx):
            break
        qa, fa = q[idx], f[idx]
        j = sistema.jacobiano(qa, alvos[idx])
        jjt = j @ np.transpose(j, (0, 2, 1))
        diagonal = np.max(np.diagonal(jjt, axis1=1, axis2=2), axis=1)
        mu = AMORTECIMENTO * np.where(diagonal > 0.0, diagonal, 1.0)
        try:
            y = np.linalg.solve(jjt + mu[:, None, None] * identidade, fa[:, :, None])[:, :, 0]
        except np.linalg.LinAlgError:
            break
        passo = -(np.transpose(j, (0, 2, 1)) @ y[:, :, None])[:, :, 0]
        maior = np.max(np.abs(passo), axis=1)
        t = np.where(maior > limite, limite / np.where(maior > 0, maior, 1.0), 1.0)
        norma = np.sqrt(np.sum(fa * fa, axis=1))
        nova_q = qa + t[:, None] * passo
        nova_f = sistema.residuos(nova_q, alvos[idx])
        for _ in range(MAX_CORTES):
            nova_norma = np.sqrt(np.sum(nova_f * nova_f, axis=1))
            ruim = ~(nova_norma < norma)  # nan também é ruim
            if not ruim.any():
                break
            t = np.where(ruim, t / 2.0, t)
            refazer = np.flatnonzero(ruim)
            nova_q[refazer] = qa[refazer] + t[refazer, None] * passo[refazer]
            nova_f[refazer] = sistema.residuos(nova_q[refazer], alvos[idx][refazer])
        nova_norma = np.sqrt(np.sum(nova_f * nova_f, axis=1))
        melhorou = nova_norma < norma
        q[idx] = np.where(melhorou[:, None], nova_q, qa)
        f[idx] = np.where(melhorou[:, None], nova_f, fa)
        ativo[idx[~melhorou]] = False
        if not melhorou.any():
            break
    erro = np.max(np.abs(f), axis=1)
    return q, np.where(np.isfinite(erro), erro, np.inf)


def _escala_dos_alvos(sistema: Sistema, alvos: np.ndarray) -> np.ndarray:
    escala = np.maximum(np.abs(alvos), 0.05 * sistema.tamanho)
    for i, eq in enumerate(sistema.equacoes):
        if eq.angulo:
            escala[:, i] = np.maximum(np.abs(alvos[:, i]), _ANGULO_DE_ESCALA)
    return escala


def resolver(
    sistema: Sistema,
    valores: Mapping[str, Any] | None = None,
    *,
    k: int | None = None,
    q_inicial: np.ndarray | None = None,
    valores_iniciais: Mapping[str, Any] | None = None,
) -> Solucao:
    """O esboço com as letras em ``valores`` (números ou vetores de tamanho ``k``).

    Parte do desenho como está (``q_inicial``, com as letras em ``valores_iniciais``) e leva as cotas
    aos poucos até o valor pedido: assim o desenho não pula para outra forma no caminho.
    """
    base = sistema.esboco.valores()
    valores = {**base, **(valores or {})}
    if k is None:
        tamanhos = [np.size(v) for v in valores.values() if np.ndim(v) > 0]
        k = max(tamanhos, default=1)
    inicio = {**base, **(valores_iniciais or {})}
    alvos_0 = sistema.alvos(inicio, k)
    alvos_1 = sistema.alvos(valores, k)
    q = (
        np.tile(sistema.q0, (k, 1))
        if q_inicial is None
        else np.array(np.broadcast_to(q_inicial, (k, sistema.n)), dtype=float)
    )
    # O desenho de partida pode não fechar as próprias cotas (acabou de ganhar uma): fecha antes.
    q, _ = newton(sistema, q, alvos_0)
    delta = alvos_1 - alvos_0
    with np.errstate(all="ignore"):
        fracao = np.max(np.abs(delta) / _escala_dos_alvos(sistema, alvos_0), axis=1, initial=0.0)
    fracao = np.where(np.isfinite(fracao), fracao, 0.0)
    passos = np.clip(np.ceil(fracao / PASSO_DA_CONTINUACAO), 1, MAX_PASSOS).astype(int)
    erro = np.zeros(k)
    # Quem se perde no caminho (resíduo mil vezes acima da tolerância) já não chega: para ali.
    perdido = np.zeros(k, dtype=bool)
    longe = TOLERANCIA * sistema.tamanho * PERDIDO
    for passo in range(1, int(passos.max()) + 1):
        vivos = np.flatnonzero(~perdido & (passo <= passos))
        if not len(vivos):
            break
        t = (passo / passos[vivos])[:, None]
        q[vivos], erro[vivos] = newton(sistema, q[vivos], alvos_0[vivos] + t * delta[vivos])
        perdido[vivos] |= ~(erro[vivos] <= longe)
    convergiu = (erro <= TOLERANCIA * sistema.tamanho * 10.0) & ~perdido
    return Solucao(q, convergiu, erro)


def esboco_resolvido(esboco: Esboco, valores: Mapping[str, float] | None = None) -> Esboco:
    """O esboço com os pontos no lugar que as cotas pedem. Sem fechar, explica o motivo."""
    if valores:
        esboco = esboco.com_valores(valores)
    sistema = Sistema(esboco)
    solucao = resolver(sistema)
    if not bool(solucao.convergiu[0]):
        conflitos = conflitantes(sistema, solucao.q[0])
        raise ErroDeEsboco(_mensagem_de_conflito(esboco, conflitos))
    return com_q(esboco, sistema, solucao.q[0])


def com_q(esboco: Esboco, sistema: Sistema, q: np.ndarray) -> Esboco:
    pontos = {pid: (float(q[i]), float(q[i + 1])) for pid, i in sistema.colunas.items()}
    curvas = tuple(
        replace(c, raio=float(q[sistema.raios[c.id]])) if c.id in sistema.raios else c
        for c in esboco.curvas
    )
    return replace(esboco, pontos=pontos, curvas=curvas)


# ---------------------------------------------------------------------------
# Graus de liberdade
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Graus:
    """O que está preso e o que sobra, pelo desenho de agora."""

    livres: int  # graus de liberdade que faltam prender
    colunas_livres: frozenset[int]
    redundantes: tuple[int, ...]  # equações que repetem outras (índice em ``Sistema.equacoes``)
    pontos_livres: frozenset[str]
    curvas_livres: frozenset[str]

    @property
    def definido(self) -> bool:
        return self.livres == 0


def graus_de_liberdade(sistema: Sistema, q: np.ndarray | None = None) -> Graus:
    """Gram-Schmidt nas linhas do jacobiano, na ordem das equações.

    Linha que não acrescenta direção nova repete o que outras já prendem (redundante). Uma coordenada
    está presa quando o vetor dela cabe todo no espaço das linhas: nenhum movimento que cumpra as
    equações mexe nela.
    """
    q = sistema.q0 if q is None else np.asarray(q, dtype=float)
    alvos = sistema.alvos(sistema.esboco.valores(), 1)
    j = sistema.jacobiano(q[None, :], alvos)[0]
    base: list[np.ndarray] = []
    redundantes: list[int] = []
    for i, linha in enumerate(j):
        v = linha.copy()
        for _ in range(2):
            for b in base:
                v -= (v @ b) * b
        norma = float(np.linalg.norm(v))
        if norma <= 1e-7 * max(float(np.linalg.norm(linha)), 1e-300):
            redundantes.append(i)
        else:
            base.append(v / norma)
    if base:
        presa = np.sum(np.array(base) ** 2, axis=0)
    else:
        presa = np.zeros(sistema.n)
    livres = frozenset(int(i) for i in np.flatnonzero(presa < 1.0 - 1e-6))
    pontos = frozenset(pid for pid, i in sistema.colunas.items() if i in livres or i + 1 in livres)
    curvas = frozenset(
        c.id
        for c in sistema.esboco.curvas
        if any(p in pontos for p in c.pontos) or sistema.raios.get(c.id, -1) in livres
    )
    return Graus(sistema.n - len(base), livres, tuple(redundantes), pontos, curvas)


def conflitantes(sistema: Sistema, q: np.ndarray) -> list[str]:
    """As restrições e cotas que ficaram sem fechar: quem briga com quem."""
    alvos = sistema.alvos(sistema.esboco.valores(), 1)
    f = sistema.residuos(q[None, :], alvos)[0]
    tolerancia = TOLERANCIA * sistema.tamanho * 10.0
    vistos: list[str] = []
    for eq, valor in zip(sistema.equacoes, f, strict=True):
        if not (abs(valor) <= tolerancia) and eq.origem not in vistos:
            vistos.append(eq.origem)
    return vistos


def descrever(esboco: Esboco, origem: str) -> str:
    for r in esboco.restricoes:
        if r.id == origem:
            return f"a restrição “{NOME_DA_RESTRICAO.get(r.tipo, r.tipo)}” ({r.id})"
    for cota in esboco.cotas:
        if cota.id == origem:
            return (
                f"a cota de {NOME_DA_COTA.get(cota.tipo, cota.tipo)} {cota.expressao} ({cota.id})"
            )
    for curva in esboco.curvas:
        if curva.id == origem:
            return f"o arco {curva.id}"
    return origem


def _mensagem_de_conflito(esboco: Esboco, conflitos: Sequence[str]) -> str:
    if not conflitos:
        return "O esboço não fechou com estas medidas."
    nomes = [descrever(esboco, c) for c in conflitos[:3]]
    return "O esboço não fecha: " + "; ".join(nomes) + " não cabem juntas. Mude uma delas."


# ---------------------------------------------------------------------------
# Esboço a partir das partes antigas
# ---------------------------------------------------------------------------


@dataclass
class _Montador:
    pontos: dict[str, tuple[float, float]] = field(default_factory=lambda: {ORIGEM: (0.0, 0.0)})
    curvas: list[Curva] = field(default_factory=list)
    restricoes: list[Restricao] = field(default_factory=list)

    def ponto(self, x: float, y: float) -> str:
        pid = f"p{len(self.pontos)}"
        self.pontos[pid] = (float(x), float(y))
        return pid

    def curva(self, tipo: str, pontos: tuple[str, ...], raio: float = 0.0) -> str:
        cid = f"c{len(self.curvas) + 1}"
        self.curvas.append(Curva(cid, tipo, pontos, raio))
        return cid

    def restricao(self, tipo: str, curvas: tuple[str, ...]) -> None:
        self.restricoes.append(Restricao(f"r{len(self.restricoes) + 1}", tipo, curvas=curvas))

    def contorno(self, cantos: Sequence[tuple[float, float]]) -> list[str]:
        ids = [self.ponto(x, y) for x, y in cantos]
        linhas = []
        for a, b in zip(ids, (*ids[1:], ids[0]), strict=True):
            cid = self.curva(LINHA, (a, b))
            (xa, ya), (xb, yb) = self.pontos[a], self.pontos[b]
            if abs(ya - yb) < 1e-9:
                self.restricao(HORIZONTAL, (cid,))
            elif abs(xa - xb) < 1e-9:
                self.restricao(VERTICAL, (cid,))
            linhas.append(cid)
        return linhas


def esboco_das_partes(partes: Sequence[Any]) -> Esboco:
    """As partes da prancheta antiga (retângulo, círculo, polígono) viram curvas do esboço.

    Vira geometria solta, só com horizontal e vertical: as medidas antigas não eram cotas. Partes que
    se sobrepõem continuam se sobrepondo, e o esboço avisa onde.
    """
    from core import secao_desenhada as sd

    m = _Montador()
    for parte in partes:
        if parte.forma == sd.CIRC:
            centro = m.ponto(parte.x, parte.y)
            m.curva(CIRCULO, (centro,), parte.b / 2.0)
        else:
            m.contorno(parte.cantos)
    return Esboco(m.pontos, tuple(m.curvas), tuple(m.restricoes))
