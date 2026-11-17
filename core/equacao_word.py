"""Equação nativa do Word (OMML) a partir da fórmula em texto do programa.

As contas do programa são escritas em texto linear: ``t_p,min = √(4·F_t·m/(b_eff·f_y/γ_a1))``. No
memorial que vai para o documento oficial elas viram **equações do Word** (o objeto do editor de
equações): índices, frações, raízes, somatórios e parênteses de verdade, editáveis no destino.

O texto que chega dos módulos nem sempre é só a conta. :func:`preparar` separa:

* o **rótulo** do começo ("Corte (rosca no plano de corte): …"), que fica em texto normal;
* a **referência** do fim ("… (NBR 8800:2025, 6.3.3.2)"), também em texto;
* as **várias contas** de uma linha, separadas por ``;`` fora de parênteses — uma equação cada.

Notação aceita na conta:

* ``X_abc`` ou ``X_{a b}`` — índice (vírgulas no meio contam: ``σ_c,Rd``; vírgula seguida de espaço
  encerra); letra grega com letras minúsculas coladas também (``σa`` = σ com índice a, ``ℓx``,
  ``τxy``), e os índices Unicode (``a₁``, ``n₀``);
* ``x^2``, ``x^(n+1)`` ou ``x^{n+1}`` — expoente; ``²`` e ``³`` ficam como estão;
* ``a/b`` — fração: o numerador é o produto à esquerda (itens ligados por ``·``, ``×`` ou lado a
  lado) e o denominador o item à direita; parênteses em volta de um dos lados somem;
* ``√(…)`` — raiz; ``Σ…`` — somatório; ``|x|`` — módulo; ``(…)`` e ``[…]`` — parênteses;
* ``x`` isolado entre espaços, ``*`` e ``=>``, ``<=``, ``>=``, ``!=`` viram ×, ·, ⇒, ≤, ≥, ≠; com
  ``maquina=True`` o ponto decimal vira vírgula ("0.45" → "0,45");
* unidades depois de um valor (``mm``, ``kN``, ``MPa``…), funções (``mín``, ``máx``, ``ln``…) e
  palavras (``fator aplicado``, ``Produto dos fatores``) em letra reta; símbolos em itálico.

Nas contas com resultado, o valor calculado (o que vem antes da comparação, ou o último) sai numa
**caixa**; as contas só com símbolos (:attr:`Equacao.simbolica`) o memorial numera. O que a leitura
não entende é consertado no lugar (parêntese faltando fecha, sobrando vira texto, fração sem lado
vira barra): o memorial nunca cai por causa de uma fórmula.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

from docx.oxml import parse_xml

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

RELACIONAIS = frozenset("=≤≥<>≈≠⇒→")
COMPARACOES = frozenset("≤≥<>")
OPERADORES = frozenset("=≤≥<>+−-·×±≈≠;:→⇒∴")
PRODUTOS = frozenset("·×")
FIM_DE_INDICE = frozenset(" =≤≥<>+−·×±≈≠;:/()[]{}^√|\t→⇒∑Σ-_²³⁴")
SOBRESCRITOS = {"²": "2", "³": "3", "⁴": "4"}
#: Letras gregas que levam o índice colado (σa, τxy, ℓx); Δ, π e Σ não (Δx é "delta x").
GREGAS = frozenset("αβγδεζηθικλμνξρστυφχψωΓΘΛΞΠΦΨΩℓ")
SUBSCRITOS = dict(zip("₀₁₂₃₄₅₆₇₈₉ₐₑₒₓᵢⱼₖₗₘₙₚₛₜᵤᵥ", "0123456789aeoxijklmnpstuv", strict=True))
UNIDADES = frozenset(
    {
        "mm", "cm", "m", "km", "kN", "N", "MN", "MPa", "GPa", "kPa", "Pa", "kg", "t", "s", "Hz",
        "rad", "°", "°C", "°F", "%", "kgf", "tf", "kW", "W", "rpm", "min", "h", "mm²", "mm³",
        "mm⁴", "cm²", "cm³", "cm⁴", "m²", "m³", "ciclos", "dB", "bar", "L",
    }
)  # fmt: skip
#: Unidades de uma letra só valem depois de um número (senão "m" e "N" são símbolos).
UNIDADES_CURTAS = frozenset({"m", "N", "t", "s", "h", "W", "L"})
FUNCOES = frozenset(
    {"mín", "máx", "min", "max", "ln", "log", "exp", "sen", "cos", "tg", "tan", "arctg", "lim"}
)
#: Palavras curtas da língua que, soltas entre dois valores, são texto e não variável.
PALAVRAS_CURTAS = frozenset({"e", "ou", "de", "da", "do", "em", "no", "na", "o", "a"})
_NORMA = re.compile(
    r"\b(NBR|ABNT|ACI|AISC|ASME|ISO|EN|Eurocode|RCSC|Tabela|Tab\.|item|seção|Anexo|cap\.|"
    r"Norton|Shigley|Guide|DG\d)\b",
    re.IGNORECASE,
)


# ============================================================================================
# Texto → partes (rótulo, contas, referência)
# ============================================================================================
def normalizar(texto: str, *, maquina: bool = False) -> str:
    """Notações alternativas para a de sempre (×, ⇒, ≤…), vírgula decimal e índices Unicode."""
    t = str(texto or "")
    for velho, novo in (("=>", "⇒"), ("->", "→"), ("<=", "≤"), (">=", "≥"), ("!=", "≠")):
        t = t.replace(velho, novo)
    t = t.replace("*", "·")
    t = re.sub(r"(?<=\S)\s+x\s+(?=\S)", " × ", t)  # x isolado entre espaços: vezes
    if maquina:
        from core.memorial_verificacoes import decimal_ptbr

        t = decimal_ptbr(t)
    t = re.sub(  # índices Unicode colados: a₁ → a_{1}, n₀ → n_{0}
        "[" + "".join(SUBSCRITOS) + "]+",
        lambda m: "_{" + "".join(SUBSCRITOS[c] for c in m.group(0)) + "}",
        t,
    )
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _profundidades(texto: str) -> list[int]:
    """A profundidade de parênteses antes de cada caractere."""
    nivel, saida = 0, []
    for c in texto:
        saida.append(nivel)
        if c in "([{":
            nivel += 1
        elif c in ")]}" and nivel > 0:
            nivel -= 1
    return saida


def _palavras(texto: str) -> int:
    return len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", texto))


@dataclass(frozen=True)
class Equacao:
    """Uma conta já lida: o texto e a árvore."""

    texto: str
    arvore: tuple

    @property
    def resultado(self) -> bool:
        """Calcula um valor ("… = 7,91 mm", "… = 91,3 MPa ≤ 227,3 MPa"): o valor sai em caixa."""
        return _segmento_do_resultado(list(self.arvore)) is not None

    @property
    def simbolica(self) -> bool:
        """Só símbolos — a fórmula da norma, que o memorial numera."""
        nos = list(self.arvore)
        if not any(no[0] == "op" and no[1] in RELACIONAIS for no in nos):
            return False
        if not all(_tem_simbolo(seg) for seg in _segmentos(nos)):
            return False  # um lado só com números: é resultado, não a fórmula
        return any(
            no[0] in ("sub", "sup", "f", "rad", "nary") or (no[0] == "r" and not no[2])
            for no in _todos(nos)
        )


def preparar(texto: str, *, maquina: bool = False) -> tuple[str, list[Equacao], str]:
    """(rótulo, contas, referência) de um texto de cálculo (ver o docstring do módulo)."""
    t = normalizar(texto, maquina=maquina)
    rotulo, referencia = "", ""
    profundidade = _profundidades(t)
    # rótulo: o texto até o primeiro ": " fora de parênteses, quando ele não é conta
    for i, c in enumerate(t):
        if c == ":" and profundidade[i] == 0 and i + 1 < len(t) and t[i + 1] == " ":
            antes = t[:i]
            fora = "".join(ch for ch, nivel in zip(antes, profundidade, strict=False) if nivel == 0)
            if not any(r in fora for r in RELACIONAIS) and _palavras(antes) >= 1:
                rotulo, t = antes.strip() + ":", t[i + 1 :].strip()
            break
    # referência: o último parêntese, quando cita norma ou é prosa
    if t.endswith(")"):
        profundidade = _profundidades(t)
        inicio = max((i for i, c in enumerate(t) if c == "(" and profundidade[i] == 0), default=-1)
        if inicio > 0:
            dentro = t[inicio + 1 : -1]
            if (_NORMA.search(dentro) or _palavras(dentro) >= 3) and not any(
                r in dentro for r in "=≤≥"
            ):
                referencia, t = dentro.strip(), t[:inicio].strip()
    # várias contas na mesma linha: ";" fora de parênteses
    profundidade = _profundidades(t)
    pedacos, inicio = [], 0
    for i, c in enumerate(t):
        if c == ";" and profundidade[i] == 0:
            pedacos.append(t[inicio:i])
            inicio = i + 1
    pedacos.append(t[inicio:])
    equacoes = [
        Equacao(p.strip(), tuple(_ler_normalizado(p.strip()))) for p in pedacos if p.strip()
    ]
    return rotulo, equacoes, referencia


# ============================================================================================
# Leitura
# ============================================================================================
def _tokens(texto: str) -> list[tuple[str, str]]:
    """(tipo, texto): num, id, texto, op, abre, fecha, barra_vertical, raiz, soma, barra, chapeu,
    sub, sub_chaves, sup_chaves, espaco ou outro."""
    saida: list[tuple[str, str]] = []
    i, n = 0, len(texto)

    def indice_ate_o_fim(j: int) -> tuple[str, int]:
        k = j
        while k < n and texto[k] not in FIM_DE_INDICE:
            if texto[k] == "," and (k + 1 >= n or texto[k + 1] == " "):
                break
            k += 1
        return texto[j:k], k

    def entre_chaves(j: int) -> tuple[str, int]:
        nivel, k = 0, j
        while k < n:
            if texto[k] == "{":
                nivel += 1
            elif texto[k] == "}":
                nivel -= 1
                if nivel == 0:
                    return texto[j + 1 : k], k + 1
            k += 1
        return texto[j + 1 :], n

    while i < n:
        c = texto[i]
        if c.isspace():
            saida.append(("espaco", " "))
            while i < n and texto[i].isspace():
                i += 1
            continue
        if c in SOBRESCRITOS and saida and saida[-1][0] not in ("espaco", "op"):
            saida.append(("sup_chaves", SOBRESCRITOS[c]))  # x_i²: o expoente depois do índice
            i += 1
            continue
        if c.isdigit() and c not in SOBRESCRITOS:
            j = i
            while (
                j < n
                and texto[j] not in SOBRESCRITOS
                and (
                    texto[j].isdigit()
                    or (texto[j] in ",." and j + 1 < n and texto[j + 1].isdigit())
                )
            ):
                j += 1
            saida.append(("num", texto[i:j]))
            i = j
            continue
        if c in "Σ∑":
            saida.append(("soma", c))
            i += 1
            continue
        if c == "°" and i + 1 < n and texto[i + 1] in "CF":
            saida.append(("id", texto[i : i + 2]))  # °C e °F
            i += 2
            continue
        if c in GREGAS and i + 1 < n and texto[i + 1].isascii() and texto[i + 1].islower():
            indice, j = indice_ate_o_fim(i + 1)  # σa, ℓx, τxy, σa,eq
            saida.append(("id", c))
            saida.append(("sub", indice))
            i = j
            continue
        if c.isalpha() or c in "ℓ°%":
            j = i
            while j < n and (texto[j].isalpha() or texto[j] in "ℓ²³⁴'′"):
                if j > i and texto[j] in GREGAS and texto[j - 1] not in GREGAS:
                    break
                j += 1
            j = max(j, i + 1)
            saida.append(("id", texto[i:j]))
            i = j
            continue
        if c == "_":
            if i + 1 < n and texto[i + 1] == "{":
                conteudo, j = entre_chaves(i + 1)
                saida.append(("sub_chaves", conteudo))
            else:
                conteudo, j = indice_ate_o_fim(i + 1)
                saida.append(("sub", conteudo))
            i = j
            continue
        if c == "^":
            if i + 1 < n and texto[i + 1] == "{":
                conteudo, j = entre_chaves(i + 1)
                saida.append(("sup_chaves", conteudo))
                i = j
            else:
                saida.append(("chapeu", c))
                i += 1
            continue
        tipo = {
            "(": "abre", "[": "abre", "{": "abre", ")": "fecha", "]": "fecha", "}": "fecha",
            "√": "raiz", "/": "barra", "|": "barra_vertical", "Σ": "soma", "∑": "soma",
        }.get(c)  # fmt: skip
        if tipo:
            saida.append((tipo, c))
        elif c in OPERADORES:
            saida.append(("op", c))
        else:
            saida.append(("outro", c))
        i += 1
    return _juntar_palavras(saida)


def _e_palavra(texto: str) -> bool:
    letras = sum(1 for c in texto if c.isalpha())
    return letras >= 3 and texto not in FUNCOES and texto not in UNIDADES


def _vizinho(tokens: list[tuple[str, str]], k: int, passo: int) -> tuple[str, str] | None:
    """O token mais perto de k na direção ``passo``, pulando espaços."""
    j = k + passo
    while 0 <= j < len(tokens) and tokens[j][0] == "espaco":
        j += passo
    return tokens[j] if 0 <= j < len(tokens) else None


def _juntar_palavras(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Palavras seguidas ("fator aplicado", "Produto dos fatores") viram um texto só, reto."""
    saida: list[tuple[str, str]] = []
    k = 0
    while k < len(tokens):
        tipo, texto = tokens[k]
        seguinte = tokens[k + 1][0] if k + 1 < len(tokens) else ""
        colado = seguinte in ("sub", "sub_chaves", "chapeu", "sup_chaves")
        palavra = tipo == "id" and not colado and _e_palavra(texto)
        if tipo == "id" and not colado and texto in PALAVRAS_CURTAS:
            # "e" ou "de" só é palavra entre dois valores ("8,5 kN (ELU) e 6,0 kN"): sozinho, ou
            # junto de um operador, é símbolo ("e = M/N")
            antes, depois = _vizinho(tokens, k, -1), _vizinho(tokens, k, 1)
            palavra = (
                antes is not None
                and depois is not None
                and seguinte == "espaco"
                and antes[0] in ("num", "id", "fecha", "texto")
                and depois[0] in ("num", "id", "abre")
            )
        if not palavra:
            saida.append((tipo, texto))
            k += 1
            continue
        partes = [texto]
        k += 1
        while (
            k + 1 < len(tokens)
            and tokens[k][0] == "espaco"
            and tokens[k + 1][0] == "id"
            and (_e_palavra(tokens[k + 1][1]) or tokens[k + 1][1] in PALAVRAS_CURTAS)
            and (k + 2 >= len(tokens) or tokens[k + 2][0] not in ("sub", "sub_chaves"))
        ):
            partes.append(tokens[k + 1][1])
            k += 2
        saida.append(("texto", " ".join(partes)))
    return saida


class _Leitor:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.t = tokens
        self.i = 0
        self.anterior = ""  # o último item: "num", "unidade", "valor" ou "" (depois de operador)

    def olhar(self) -> tuple[str, str] | None:
        while self.i < len(self.t) and self.t[self.i][0] == "espaco":
            self.i += 1
        return self.t[self.i] if self.i < len(self.t) else None

    def sequencia(self, fecha: str | None = None) -> list[tuple]:
        itens: list[tuple] = []
        while True:
            atual = self.olhar()
            if atual is None:
                break  # parêntese sem fechar: fecha aqui
            tipo, texto = atual
            if tipo == "fecha":
                self.i += 1
                if fecha is None or fecha == "|":
                    itens.append(("r", texto, True))  # parêntese sobrando: vira texto
                    continue
                break
            if tipo == "barra_vertical":
                self.i += 1
                if fecha == "|":
                    break
                itens.append(("d", "|", "|", self.sequencia(fecha="|")))
                self.anterior = "valor"
                continue
            if tipo == "op":
                self.i += 1
                itens.append(("op", texto))
                if texto not in PRODUTOS:
                    self.anterior = ""
                continue
            if tipo == "barra":
                self.i += 1
                itens.append(("barra",))
                continue
            itens.append(self.item())
        return _fracoes(itens)

    def item(self) -> tuple:
        tipo, texto = self.olhar()  # type: ignore[misc]
        self.i += 1
        base: tuple
        if tipo == "num":
            base = ("r", texto, True)
            self.anterior = "num"
        elif tipo == "texto":
            base = ("txt", texto)
            self.anterior = ""
        elif tipo == "id":
            curta = texto in UNIDADES_CURTAS
            unidade = texto in UNIDADES and (
                self.anterior in ("num", "unidade") or (not curta and self.anterior == "valor")
            )
            base = ("r", texto, texto in FUNCOES or unidade)
            self.anterior = "unidade" if unidade else "valor"
        elif tipo == "raiz":
            proximo = self.olhar()
            if proximo is not None and proximo[0] == "abre":
                self.i += 1
                base = ("rad", self.sequencia(fecha=proximo[1]))
            elif proximo is not None and proximo[0] not in ("op", "fecha", "barra"):
                base = ("rad", [self.item()])
            else:
                base = ("r", texto, True)
            self.anterior = "valor"
        elif tipo == "soma":
            indice: list[tuple] = []
            proximo = self.t[self.i] if self.i < len(self.t) else None
            if proximo is not None and proximo[0] in ("sub", "sub_chaves"):
                self.i += 1
                indice = [("r", proximo[1], True)]
            corpo: list[tuple] = []
            seguinte = self.olhar()
            if seguinte is not None and seguinte[0] not in ("op", "fecha", "barra"):
                corpo = _sem_parenteses(self.item())
            base = ("nary", "∑", indice, corpo)
            self.anterior = "valor"
        elif tipo == "abre":
            fecha = {"(": ")", "[": "]", "{": "}"}[texto]
            abre = "(" if texto == "{" else texto
            base = ("d", abre, ")" if texto == "{" else fecha, self.sequencia(fecha=fecha))
            self.anterior = "valor"
        else:
            base = ("r", texto, True)
        while True:  # índices e expoentes colados
            proximo = self.t[self.i] if self.i < len(self.t) else None
            if proximo is None or proximo[0] not in ("sub", "sub_chaves", "chapeu", "sup_chaves"):
                break
            tipo2, texto2 = proximo
            self.i += 1
            if tipo2 == "sub":
                base = ("sub", [base], [("r", texto2, True)])
            elif tipo2 == "sub_chaves":
                base = ("sub", [base], _ler_pedaco(texto2, reto=True))
            elif tipo2 == "sup_chaves":
                base = ("sup", [base], _ler_pedaco(texto2))
            else:
                if self.olhar() is None:
                    break  # "x^" no fim: o chapéu some
                anterior = self.anterior
                expoente = self.item()
                self.anterior = anterior
                base = ("sup", [base], _sem_parenteses(expoente))
        return base


def _ler_pedaco(texto: str, *, reto: bool = False) -> list[tuple]:
    """O conteúdo de ``_{…}`` ou ``^{…}``: texto reto simples ou uma conta."""
    if reto and not any(c in texto for c in "+−-·×/^_√()=<>"):
        return [("r", texto, True)]
    return _Leitor(_tokens(texto)).sequencia() or [("r", "", True)]


def _sem_parenteses(no: tuple) -> list[tuple]:
    if no[0] == "d" and no[1] == "(":
        return list(no[3])
    return [no]


def _fracoes(itens: list[tuple]) -> list[tuple]:
    """Junta ``a/b`` em frações: numerador = o produto à esquerda, denominador = o item à direita."""
    saida: list[tuple] = []
    k = 0
    while k < len(itens):
        atual = itens[k]
        if atual[0] != "barra":
            saida.append(atual)
            k += 1
            continue
        inicio = len(saida)
        while inicio > 0:
            anterior = saida[inicio - 1]
            if (anterior[0] == "op" and anterior[1] not in PRODUTOS) or anterior[0] == "txt":
                break
            inicio -= 1
        numerador = saida[inicio:]
        k += 1
        if not numerador or k >= len(itens) or itens[k][0] in ("op", "barra"):
            saida.append(("r", "/", True))  # fração sem um dos lados: a barra fica como texto
            continue
        del saida[inicio:]
        denominador = _sem_parenteses(itens[k])
        if len(numerador) == 1:
            numerador = _sem_parenteses(numerador[0])
        saida.append(("f", numerador, denominador))
        k += 1
    return saida


def _ler_normalizado(texto: str) -> list[tuple]:
    return _Leitor(_tokens(texto)).sequencia()


def ler(texto: str, *, maquina: bool = False) -> list[tuple]:
    """A árvore de UMA conta (nunca levanta erro: o que não fecha é consertado no lugar)."""
    return _ler_normalizado(normalizar(texto, maquina=maquina))


def _todos(nos: list[tuple]) -> list[tuple]:
    saida: list[tuple] = []
    for no in nos:
        saida.append(no)
        for parte in no[1:]:
            if isinstance(parte, list):
                saida.extend(_todos(parte))
    return saida


# ============================================================================================
# O valor calculado (caixa)
# ============================================================================================
def _valor_puro(nos: list[tuple]) -> bool:
    """Número com unidade (e potência de 10), sem símbolo: "7,91 mm", "1,2 × 10³ kN"."""
    if not nos or nos[0][0] != "r" or not str(nos[0][1])[:1].isdigit():
        return False
    for no in nos:
        if no[0] == "r" and no[2]:
            continue
        if no[0] == "op" and no[1] in PRODUTOS:
            continue
        if no[0] == "sup" and all(x[0] == "r" and x[2] for x in no[1] + no[2]):
            continue
        return False
    return True


def _tem_simbolo(nos: list[tuple]) -> bool:
    """Há uma variável (letra em itálico) no trecho."""
    return any(no[0] == "r" and not no[2] for no in _todos(nos))


def _segmentos(nos: list[tuple]) -> list[list[tuple]]:
    """A conta cortada nos sinais de relação (=, ≤, ⇒…)."""
    partes: list[list[tuple]] = [[]]
    for no in nos:
        if no[0] == "op" and no[1] in RELACIONAIS:
            partes.append([])
        else:
            partes[-1].append(no)
    return partes


def _segmento_do_resultado(nos: list[tuple]) -> tuple[int, int] | None:
    """(início, fim) do valor que a conta calcula: o que vem antes da primeira comparação ou, sem
    ela, o último — e só quando há conta antes dele (dois sinais de igual ou uma comparação)."""
    cortes = [i for i, no in enumerate(nos) if no[0] == "op" and no[1] in RELACIONAIS]
    iguais = sum(1 for i in cortes if nos[i][1] in "=⇒")
    if iguais < 2 and not any(nos[i][1] in COMPARACOES for i in cortes):
        return None
    limites = [(-1, "")] + [(i, nos[i][1]) for i in cortes] + [(len(nos), "")]
    trechos = [
        (limites[k][0] + 1, limites[k + 1][0], limites[k + 1][1]) for k in range(len(limites) - 1)
    ]
    posicao = next((k for k, (_, _, depois) in enumerate(trechos) if depois in COMPARACOES), None)
    if posicao is None:
        posicao = len(trechos) - 1
    if posicao < 2:  # "T = 500 °F ≤ 450 °F": um dado comparado, sem conta antes
        return None
    a, b, _ = trechos[posicao]
    if not _valor_puro(nos[a:b]):
        return None
    return a, b


def _com_caixa(nos: list[tuple]) -> list[tuple]:
    alvo = _segmento_do_resultado(nos)
    if alvo is None:
        return nos
    a, b = alvo
    return [*nos[:a], ("caixa", nos[a:b]), *nos[b:]]


# ============================================================================================
# OMML
# ============================================================================================
def _r(texto: str, reto: bool) -> str:
    estilo = '<m:rPr><m:sty m:val="p"/></m:rPr>' if reto else ""
    return f'<m:r>{estilo}<m:t xml:space="preserve">{escape(str(texto))}</m:t></m:r>'


def _texto_normal(texto: str) -> str:
    """Texto comum dentro da equação: reto e com os espaços em volta."""
    return f'<m:r><m:rPr><m:nor/></m:rPr><m:t xml:space="preserve"> {escape(texto)} </m:t></m:r>'


def _xml(nos: list[tuple]) -> str:
    partes: list[str] = []
    for no in nos:
        tipo = no[0]
        if tipo == "r":
            partes.append(_r(no[1], no[2]))
        elif tipo == "txt":
            partes.append(_texto_normal(no[1]))
        elif tipo == "op":
            partes.append(_r({"-": "−"}.get(no[1], no[1]), True))
        elif tipo == "sub":
            partes.append(f"<m:sSub><m:e>{_xml(no[1])}</m:e><m:sub>{_xml(no[2])}</m:sub></m:sSub>")
        elif tipo == "sup":
            partes.append(f"<m:sSup><m:e>{_xml(no[1])}</m:e><m:sup>{_xml(no[2])}</m:sup></m:sSup>")
        elif tipo == "f":
            partes.append(f"<m:f><m:num>{_xml(no[1])}</m:num><m:den>{_xml(no[2])}</m:den></m:f>")
        elif tipo == "rad":
            partes.append(
                '<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>'
                f"<m:e>{_xml(no[1])}</m:e></m:rad>"
            )
        elif tipo == "nary":
            esconde = "" if no[2] else '<m:subHide m:val="1"/>'
            partes.append(
                f'<m:nary><m:naryPr><m:chr m:val="{no[1]}"/><m:limLoc m:val="undOvr"/>{esconde}'
                f'<m:supHide m:val="1"/></m:naryPr><m:sub>{_xml(no[2])}</m:sub><m:sup/>'
                f"<m:e>{_xml(no[3])}</m:e></m:nary>"
            )
        elif tipo == "d":
            if (no[1], no[2]) == ("(", ")"):
                propriedades = ""
            else:
                propriedades = (
                    f'<m:dPr><m:begChr m:val="{escape(no[1])}"/>'
                    f'<m:endChr m:val="{escape(no[2])}"/></m:dPr>'
                )
            partes.append(f"<m:d>{propriedades}<m:e>{_xml(no[3])}</m:e></m:d>")
        elif tipo == "caixa":
            partes.append(f"<m:borderBox><m:e>{_xml(no[1])}</m:e></m:borderBox>")
    return "".join(partes)


def _corpo(arvore: list[tuple], texto: str, *, caixa: bool) -> str:
    try:
        return _xml(_com_caixa(arvore) if caixa else arvore)
    except Exception:  # noqa: BLE001 - o memorial nunca cai por causa de uma fórmula
        return _r(texto, False)


def omml_da_equacao(equacao: Equacao, *, caixa: bool = True, em_linha: bool = False) -> str:
    """O XML de uma conta já lida: ``<m:oMathPara>`` (em destaque) ou ``<m:oMath>``."""
    corpo = _corpo(list(equacao.arvore), equacao.texto, caixa=caixa)
    if em_linha:
        return f'<m:oMath xmlns:m="{M}" xmlns:w="{W}">{corpo}</m:oMath>'
    return f'<m:oMathPara xmlns:m="{M}" xmlns:w="{W}"><m:oMath>{corpo}</m:oMath></m:oMathPara>'


def omml(texto: str, *, maquina: bool = False, caixa: bool = True) -> str:
    """O XML ``<m:oMathPara>`` de UMA conta (o valor calculado em caixa)."""
    texto_n = normalizar(texto, maquina=maquina)
    try:
        arvore = tuple(_ler_normalizado(texto_n))
    except Exception:  # noqa: BLE001
        arvore = (("r", texto_n, False),)
    return omml_da_equacao(Equacao(texto_n, arvore), caixa=caixa)


def omml_em_linha(texto: str, *, maquina: bool = False, caixa: bool = False) -> str:
    """O ``<m:oMath>`` de uma conta, para ir no meio de um parágrafo."""
    texto_n = normalizar(texto, maquina=maquina)
    return omml_da_equacao(
        Equacao(texto_n, tuple(_ler_normalizado(texto_n))), caixa=caixa, em_linha=True
    )


def acrescentar_equacao(paragrafo: object, texto: str, *, maquina: bool = False) -> None:
    """Põe a conta (em destaque, centrada) num parágrafo do python-docx."""
    paragrafo._p.append(parse_xml(omml(texto, maquina=maquina)))  # type: ignore[attr-defined]


def acrescentar(paragrafo: object, equacao: Equacao, *, em_linha: bool = False) -> None:
    """Põe uma conta já lida num parágrafo do python-docx."""
    paragrafo._p.append(parse_xml(omml_da_equacao(equacao, em_linha=em_linha)))  # type: ignore[attr-defined]


def texto_simples(texto: str) -> str:
    """A fórmula em texto corrido, sem a marcação de índice (para o PDF e a tela)."""
    return texto.replace("_{", "").replace("^{", "^").replace("}", "").replace("_", "")
