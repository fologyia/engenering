"""Equação nativa do Word (OMML) a partir da fórmula em texto do programa.

As contas do programa são escritas em texto linear: ``t_p,min = √(4·F_t·m/(b_eff·f_y/γ_a1))``. No
memorial que vai para o documento oficial elas viram **equações do Word** (o objeto que o editor de
equações cria): índices, frações, raízes e parênteses de verdade, editáveis no destino.

A notação aceita:

* ``X_abc`` — índice: o que vem depois do ``_`` até um espaço ou operador (vírgulas no meio contam:
  ``σ_c,Rd``; vírgula seguida de espaço encerra);
* ``x^2`` ou ``x^(n+1)`` — expoente; ``²`` e ``³`` ficam como estão;
* ``a/b`` — fração: o numerador é o produto à esquerda (itens ligados por ``·``, ``×`` ou lado a
  lado) e o denominador o item à direita; parênteses em volta de um dos lados somem;
* ``√(…)`` — raiz quadrada; ``(…)`` e ``[…]`` — parênteses que crescem com o conteúdo;
* unidades depois de número (``mm``, ``kN``, ``MPa``…) e funções (``mín``, ``máx``, ``ln``…) em
  letra reta; variáveis em itálico, como no editor do Word.

O que a leitura não entende vira texto da equação, sem erro: o memorial nunca cai por causa de uma
fórmula.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from docx.oxml import parse_xml

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

OPERADORES = set("=≤≥<>+−-·×±≈≠;:|→")
FIM_DE_INDICE = set(" =≤≥<>+−·×±≈≠;:/()[]^√{}|\t→") | {"-"}
UNIDADES = {
    "mm", "cm", "m", "km", "kN", "N", "MN", "MPa", "GPa", "kPa", "Pa", "kg", "t", "s", "Hz",
    "rad", "°", "%", "kgf", "tf", "kW", "W", "rpm", "min", "h", "mm²", "mm³", "mm⁴", "cm²",
    "cm³", "cm⁴", "m²", "m³", "kN·m", "N·mm",
}  # fmt: skip
FUNCOES = {"mín", "máx", "min", "max", "ln", "log", "exp", "sen", "cos", "tg", "tan", "arctg"}


# ------------------------------------------------------------------------------- leitura
def _tokens(texto: str) -> list[tuple[str, str]]:
    """(tipo, texto): num, id, op, abre, fecha, raiz, barra, chapeu, sub, outro."""
    saida: list[tuple[str, str]] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c.isspace():
            saida.append(("espaco", " "))
            while i < n and texto[i].isspace():
                i += 1
            continue
        if c.isdigit():
            j = i
            while j < n and (
                texto[j].isdigit() or (texto[j] in ",." and j + 1 < n and texto[j + 1].isdigit())
            ):
                j += 1
            saida.append(("num", texto[i:j]))
            i = j
            continue
        if c.isalpha() or c in "ℓ°%":
            j = i
            while j < n and (texto[j].isalpha() or texto[j] in "ℓ²³⁴'′"):
                j += 1
            j = max(j, i + 1)
            saida.append(("id", texto[i:j]))
            i = j
            continue
        if c == "_":
            j = i + 1
            while j < n and texto[j] not in FIM_DE_INDICE:
                if texto[j] == "," and (j + 1 >= n or texto[j + 1] == " "):
                    break
                j += 1
            saida.append(("sub", texto[i + 1 : j]))
            i = j
            continue
        if c in "([":
            saida.append(("abre", c))
        elif c in ")]":
            saida.append(("fecha", c))
        elif c == "√":
            saida.append(("raiz", c))
        elif c == "/":
            saida.append(("barra", c))
        elif c == "^":
            saida.append(("chapeu", c))
        elif c in OPERADORES:
            saida.append(("op", c))
        else:
            saida.append(("outro", c))
        i += 1
    return saida


class _Leitor:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.t = tokens
        self.i = 0
        self.anterior = ""  # o tipo do último item: "num", "unidade" ou ""

    def olhar(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def sequencia(self, fecha: str | None = None) -> list[tuple]:
        itens: list[tuple] = []
        while True:
            atual = self.olhar()
            if atual is None:
                if fecha is not None:
                    raise ValueError("parêntese sem fechar")
                break
            tipo, texto = atual
            if tipo == "fecha":
                if fecha is None:
                    raise ValueError("parêntese sobrando")
                self.i += 1
                break
            if tipo == "espaco":  # o Word espaça os operadores sozinho
                self.i += 1
                continue
            if tipo == "op":
                self.i += 1
                itens.append(("op", texto))
                if texto not in "·×":
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
        if tipo == "num":
            base: tuple = ("r", texto, True)
            self.anterior = "num"
        elif tipo == "id":
            reto = texto in FUNCOES or (self.anterior in ("num", "unidade") and texto in UNIDADES)
            base = ("r", texto, reto)
            self.anterior = "unidade" if reto and texto in UNIDADES else ""
        elif tipo == "raiz":
            if self.olhar() and self.olhar()[0] == "abre":  # type: ignore[index]
                self.i += 1
                base = ("rad", self.sequencia(fecha=")"))
            else:
                base = ("rad", [self.item()])
            self.anterior = ""
        elif tipo == "abre":
            fecha = ")" if texto == "(" else "]"
            base = ("d", texto, fecha, self.sequencia(fecha=fecha))
            self.anterior = ""
        else:
            base = ("r", texto, True)
        # índices e expoentes colados
        while self.olhar() is not None and self.olhar()[0] in ("sub", "chapeu"):  # type: ignore[index]
            tipo2, texto2 = self.olhar()  # type: ignore[misc]
            self.i += 1
            if tipo2 == "sub":
                base = ("sub", [base], [("r", texto2, True)])
            else:
                if self.olhar() is None:
                    raise ValueError("expoente vazio")
                expoente = self.item()
                if expoente[0] == "d":
                    expoente_nos = expoente[3]
                else:
                    expoente_nos = [expoente]
                base = ("sup", [base], expoente_nos)
        return base


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
        # numerador: volta enquanto houver itens ligados por produto (ou lado a lado)
        inicio = len(saida)
        while inicio > 0:
            anterior = saida[inicio - 1]
            if anterior[0] == "op" and anterior[1] not in "·×":
                break
            inicio -= 1
        numerador = saida[inicio:]
        del saida[inicio:]
        k += 1
        if not numerador or k >= len(itens) or itens[k][0] in ("op", "barra"):
            raise ValueError("fração incompleta")
        denominador = _sem_parenteses(itens[k])
        if len(numerador) == 1:
            numerador = _sem_parenteses(numerador[0])
        saida.append(("f", numerador, denominador))
        k += 1
    return saida


def ler(texto: str) -> list[tuple]:
    """A árvore da equação (levanta ``ValueError`` se a notação não fechar)."""
    return _Leitor(_tokens(texto.strip())).sequencia()


# ------------------------------------------------------------------------------- OMML
def _r(texto: str, reto: bool) -> str:
    estilo = '<m:rPr><m:sty m:val="p"/></m:rPr>' if reto else ""
    return f'<m:r>{estilo}<m:t xml:space="preserve">{escape(texto)}</m:t></m:r>'


def _xml(nos: list[tuple]) -> str:
    partes: list[str] = []
    for no in nos:
        tipo = no[0]
        if tipo == "r":
            partes.append(_r(no[1], no[2]))
        elif tipo == "op":
            simbolo = {"-": "−"}.get(no[1], no[1])
            partes.append(_r(simbolo, True))
        elif tipo == "espaco":
            continue  # o Word espaça os operadores sozinho
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
        elif tipo == "d":
            delimitadores = (
                ""
                if no[1] == "("
                else f'<m:dPr><m:begChr m:val="{escape(no[1])}"/><m:endChr m:val="{escape(no[2])}"/></m:dPr>'
            )
            partes.append(f"<m:d>{delimitadores}<m:e>{_xml(no[3])}</m:e></m:d>")
    return "".join(partes)


def omml(texto: str) -> str:
    """O XML ``<m:oMathPara>`` da fórmula (texto da equação se a notação não fechar)."""
    try:
        corpo = _xml(ler(texto))
    except (ValueError, TypeError, IndexError):
        corpo = _r(texto, False)
    return f'<m:oMathPara xmlns:m="{M}" xmlns:w="{W}"><m:oMath>{corpo}</m:oMath></m:oMathPara>'


def omml_em_linha(texto: str) -> str:
    """O ``<m:oMath>`` da fórmula, para ir no meio de um parágrafo."""
    try:
        corpo = _xml(ler(texto))
    except (ValueError, TypeError, IndexError):
        corpo = _r(texto, False)
    return f'<m:oMath xmlns:m="{M}" xmlns:w="{W}">{corpo}</m:oMath>'


def acrescentar_equacao(paragrafo: object, texto: str) -> None:
    """Põe a equação (em destaque, centrada) num parágrafo do python-docx."""
    paragrafo._p.append(parse_xml(omml(texto)))  # type: ignore[attr-defined]


def texto_simples(texto: str) -> str:
    """A fórmula em texto corrido, sem a marcação de índice (para o PDF e a tela)."""
    return texto.replace("_", "")
