"""Documento Word dos botões "Gerar o Word" das páginas (degrau, flambagem, peças, montador).

É um **memorial separado** e segue o padrão de :mod:`core.memorial_trecho`: o trecho do cálculo de
uma peça para colar no documento oficial — A4 em retrato, títulos nativos sem número (o documento
oficial numera), legendas com numeração automática acima das tabelas e figuras, estilos nativos e
sem cabeçalho, rodapé ou quebra de seção. A interface de antes continua (``titulo``, ``paragrafo``,
``itens``, ``tabela``, ``figura``, ``bytes``), então as páginas não mudam. Sem Streamlit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from docx.shared import Pt

from core.memorial_trecho import LARGURA_FIGURA_MM, SITUACAO, Trecho, barra_texto
from core.memorial_trecho import LARGURA_UTIL_MM as LARGURA_TRECHO_MM

#: Largura em que as tabelas das páginas foram desenhadas (A4 em paisagem); o trecho reduz a escala.
LARGURA_UTIL_MM = 273.0
_NUMERACAO = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
#: Títulos de tela trocados pelo nome que eles têm num memorial.
TITULOS_DE_MEMORIAL = {
    "O que esta página não faz": "Limitações do cálculo",
    "Quadro-resumo": "Resumo",
}


def numero_pt(x: float, casas: int = 2) -> str:
    """Número com vírgula decimal e sem zeros inúteis: 180 → "180", 166,667 → "166,67"."""
    texto = f"{x:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",") or "0"


def celula_texto(valor: Any) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        return numero_pt(valor, 4)
    return str(valor)


def _percentual(texto: str) -> float | None:
    """'56,3', '56,3 %' ou '56%' → 56,3; o que não é número → None."""
    limpo = texto.replace("%", "").replace(",", ".").strip()
    try:
        return float(limpo)
    except ValueError:
        return None


def titulo_de_memorial(texto: str) -> str:
    """'3. Tabela de verificações' → 'Tabela de verificações' (o documento oficial numera)."""
    limpo = _NUMERACAO.sub("", texto).strip()
    return TITULOS_DE_MEMORIAL.get(limpo, limpo)


class DocumentoWord(Trecho):
    """O trecho de memorial com a interface antiga das páginas."""

    def __init__(self) -> None:
        super().__init__()
        self._desloca = 0  # o título de nível 0 vira o 1 e os outros descem um
        self._ultimo_titulo = ""

    def titulo(self, texto: str, nivel: int = 1) -> None:
        if nivel == 0:
            self._desloca = 1
        texto = titulo_de_memorial(texto)
        self._ultimo_titulo = texto
        super().titulo(texto, nivel + self._desloca if nivel else 1)

    def paragrafo(  # type: ignore[override]
        self, texto: str, *, legenda: bool = False, negrito: bool = False
    ) -> Any:
        if legenda:
            self.nota(texto)
            return None
        paragrafo = super().paragrafo(texto)
        for trecho in paragrafo.runs:
            trecho.bold = negrito
        return paragrafo

    def tabela(
        self,
        cabecalhos: Sequence[str],
        linhas: Sequence[Sequence[Any]],
        larguras_mm: Sequence[float] | None = None,
        *,
        status_coluna: int | None = None,
        destacar_linha: int | None = None,
        fonte: float = 8.0,
        legenda: str | None = None,
    ) -> None:
        # a coluna de aproveitamento ganha a barra em texto ("■■■■■□□□□□"), que sobrevive a
        # colar o trecho como texto e se lê em preto e branco
        de_aproveitamento = {k for k, c in enumerate(cabecalhos) if "aprov" in str(c).casefold()}
        textos = []
        for linha in linhas:
            celulas = []
            for coluna, valor in enumerate(linha):
                texto = celula_texto(valor)
                if status_coluna is not None and coluna == status_coluna:
                    texto = SITUACAO.get(texto, texto)
                elif coluna in de_aproveitamento:
                    percentual = _percentual(texto)
                    if percentual is not None:
                        texto = f"{texto}\n{barra_texto(percentual)}"
                celulas.append(texto)
            textos.append(celulas)
        if larguras_mm is not None and sum(larguras_mm) > LARGURA_TRECHO_MM:
            escala = LARGURA_TRECHO_MM / sum(larguras_mm)
            fonte = max(6.5, fonte * max(escala, 0.8))
        super().tabela(
            cabecalhos,
            textos,
            legenda=legenda or self._ultimo_titulo or "Resultados",
            larguras_mm=larguras_mm,
            fonte=fonte,
        )
        if destacar_linha is not None and self.doc.tables:
            tabela = self.doc.tables[-1]
            if destacar_linha + 1 < len(tabela.rows):
                for celula in tabela.rows[destacar_linha + 1].cells:
                    for paragrafo in celula.paragraphs:
                        for corrida in paragrafo.runs:
                            corrida.bold = True
                            corrida.font.size = Pt(fonte)

    def figura(self, png: bytes, legenda: str, largura_mm: float = LARGURA_FIGURA_MM) -> None:
        super().figura(png, legenda, min(largura_mm, LARGURA_FIGURA_MM))
