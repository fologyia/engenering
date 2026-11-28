"""Extrai as células das tabelas emitidas pelo Robot, em HTML e RTF."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

Linhas = tuple[tuple[str, ...], ...]


def _texto(texto: str) -> str:
    return " ".join(texto.replace("\xad", "").replace("\u200b", "").split())


def _inteiro_span(valor: str | None) -> int:
    return min(100, max(1, int(valor))) if valor and valor.isascii() and valor.isdigit() else 1


@dataclass
class _TabelaHtml:
    linhas: list[tuple[str, ...]] = field(default_factory=list)
    linha: dict[int, str] = field(default_factory=dict)
    spans: dict[int, tuple[int, str]] = field(default_factory=dict)
    celula: list[str] | None = None
    largura: int = 1
    altura: int = 1
    titulo: str = ""

    def iniciar_linha(self) -> None:
        self.fechar_linha()
        self.linha = {i: texto for i, (_, texto) in self.spans.items()}
        self.spans = {i: (n - 1, texto) for i, (n, texto) in self.spans.items() if n > 1}

    def fechar_celula(self) -> None:
        if self.celula is None:
            return
        valor = _texto("".join(self.celula))
        indice = next(i for i in range(len(self.linha) + 1) if i not in self.linha)
        self.linha[indice] = valor
        for i in range(indice, indice + self.largura):
            self.linha.setdefault(i, "")
            if self.altura > 1:
                self.spans[i] = (self.altura - 1, self.linha[i])
        self.celula = None

    def fechar_linha(self) -> None:
        self.fechar_celula()
        if self.linha:
            linha = tuple(self.linha.get(i, "") for i in range(max(self.linha) + 1))
            if any(linha):
                self.linhas.append(linha)
        self.linha = {}


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[_TabelaHtml] = []
        self.tabelas: list[tuple[str, Linhas]] = []
        self.ignorar = ""
        self.captura: list[str] | None = None
        self.titulo = ""
        self.framework = False
        self.autodesk = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.ignorar:
            return
        campos = dict(attrs)
        if tag == "meta" and (campos.get("name") or "").casefold() == "generator":
            produtor = (campos.get("content") or "").casefold()
            self.framework |= "robot framework" in produtor
            self.autodesk |= "autodesk" in produtor or "rohtml" in produtor
        if tag in {"script", "style", "object", "iframe"}:
            self.ignorar = tag
        elif tag == "table":
            self.pilha.append(_TabelaHtml(titulo=self.titulo))
        elif tag in {"caption", "title", "h1", "h2", "h3", "h4"}:
            self.captura = []
        elif self.pilha:
            tabela = self.pilha[-1]
            if tag == "tr":
                tabela.iniciar_linha()
            elif tag in {"td", "th"}:
                tabela.fechar_celula()
                tabela.celula = []
                tabela.largura = _inteiro_span(campos.get("colspan"))
                tabela.altura = _inteiro_span(campos.get("rowspan"))
            elif tag == "br" and tabela.celula is not None:
                tabela.celula.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.ignorar:
            if tag == self.ignorar:
                self.ignorar = ""
            return
        if tag in {"caption", "title", "h1", "h2", "h3", "h4"} and self.captura is not None:
            titulo = _texto("".join(self.captura))
            if titulo:
                self.titulo = titulo
                if tag == "caption" and self.pilha:
                    self.pilha[-1].titulo = titulo
            self.captura = None
        if not self.pilha:
            return
        tabela = self.pilha[-1]
        if tag in {"td", "th"}:
            tabela.fechar_celula()
        elif tag == "tr":
            tabela.fechar_linha()
        elif tag == "table":
            tabela.fechar_linha()
            self.pilha.pop()
            if tabela.linhas and len(tabela.linhas[0]) > 1:
                self.tabelas.append((tabela.titulo, tuple(tabela.linhas)))

    def handle_data(self, data: str) -> None:
        if self.ignorar:
            return
        if self.captura is not None:
            self.captura.append(data)
        if self.pilha and self.pilha[-1].celula is not None:
            self.pilha[-1].celula.append(data)


def _juntar_colunas(a: Linhas, b: Linhas) -> Linhas | None:
    """O ROHTML quebra tabelas largas e repete o identificador em cada parte."""
    if len(a) != len(b) or a[0][0] != b[0][0] or set(a[0][1:]) & set(b[0][1:]):
        return None
    if all(x[0] and x[0] == y[0] for x, y in zip(a, b, strict=True)):
        return tuple((*x, *y[1:]) for x, y in zip(a, b, strict=True))
    return None


def ler_html(texto: str) -> list[tuple[str, Linhas]]:
    leitor = _Html()
    leitor.feed(texto)
    leitor.close()
    if leitor.framework or (
        not leitor.autodesk
        and "robot framework" in texto.casefold()
        and ("test statistics" in texto.casefold() or "window.output" in texto.casefold())
    ):
        raise ValueError("arquivo de resultados de testes do Robot Framework")
    tabelas: list[tuple[str, Linhas]] = []
    for titulo, linhas in leitor.tabelas:
        if leitor.autodesk and tabelas and titulo == tabelas[-1][0]:
            unida = _juntar_colunas(tabelas[-1][1], linhas)
            if unida is not None:
                tabelas[-1] = (titulo, unida)
                continue
        tabelas.append((titulo, linhas))
    return tabelas


_RTF = re.compile(r"\\([A-Za-z]+)(-?\d+)? ?|\\'([\da-fA-F]{2})|\\([^\r\n])|([{}])|([^\\{}\r\n]+)")
_DESTINOS_RTF = frozenset(
    {
        "fonttbl",
        "colortbl",
        "stylesheet",
        "info",
        "pict",
        "object",
        "objdata",
        "filetbl",
        "generator",
        "header",
        "footer",
        "field",
        "xmlopen",
        "datastore",
        "themedata",
    }
)


def ler_rtf(texto: str) -> list[tuple[str, Linhas]]:
    if not texto.lstrip().startswith(r"{\rtf"):
        raise ValueError("cabeçalho RTF inválido")
    tabelas: list[tuple[str, Linhas]] = []
    linhas: list[tuple[str, ...]] = []
    linha: list[str] | None = None
    celula: list[str] = []
    titulo: list[str] = []
    pilha: list[tuple[bool, int, str]] = []
    ignorar, uc, codigo = False, 1, "cp1252"
    restante = indice = 0
    while (token := _RTF.search(texto, indice)) is not None:
        indice = token.end()
        palavra, parametro, hex_, especial, grupo, literal = token.groups()
        if grupo == "{":
            pilha.append((ignorar, uc, codigo))
            continue
        if grupo == "}":
            if not pilha:
                raise ValueError("grupos RTF desequilibrados")
            ignorar, uc, codigo = pilha.pop()
            continue
        if palavra == "bin":
            indice += max(0, int(parametro or 0))
            continue
        if especial == "*" or palavra in _DESTINOS_RTF:
            ignorar = True
        if ignorar:
            continue
        if palavra == "uc":
            uc = max(0, int(parametro or 0))
        elif palavra == "ansicpg" and parametro:
            codigo = f"cp{int(parametro)}"
        elif palavra == "trowd":
            if linha is None:
                if linhas and _texto("".join(titulo)):
                    tabelas.append(("", tuple(linhas)))
                    linhas = []
                titulo = []
                linha, celula = [], []
        elif palavra in {"cell", "nestcell"} and linha is not None:
            linha.append(_texto("".join(celula)))
            celula = []
        elif palavra in {"row", "nestrow"} and linha is not None:
            if any(linha):
                linhas.append(tuple(linha))
            linha, celula = None, []
        elif palavra == "u" and parametro is not None:
            (celula if linha is not None else titulo).append(chr(int(parametro) & 0xFFFF))
            restante = uc
        else:
            trecho = literal or ""
            if hex_:
                try:
                    trecho = bytes.fromhex(hex_).decode(codigo)
                except (LookupError, UnicodeError) as erro:
                    raise ValueError("codificação de caractere RTF inválida") from erro
            elif especial in {"{", "}", "\\"}:
                trecho = especial
            elif palavra in {"tab", "par", "line"} or especial == "~":
                trecho = " "
            if trecho and restante:
                removidos = min(restante, len(trecho))
                trecho = trecho[removidos:]
                restante -= removidos
            (celula if linha is not None else titulo).append(trecho)
    if pilha or linha is not None:
        raise ValueError("arquivo RTF incompleto")
    if linhas:
        tabelas.append(("", tuple(linhas)))
    return tabelas
