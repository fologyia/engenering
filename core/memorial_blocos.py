"""Blocos de uma seção do memorial: a lista ordenada que o Word e o PDF desenham.

Uma seção do memorial é um dicionário com ``titulo``, ``nivel`` e o conteúdo. Até aqui o conteúdo
era um conjunto de chaves soltas (``paragrafos``, ``nota``, ``bullets``, ``formulas``, ``imagens``,
``tabelas``, ``paragrafos_finais``) desenhadas **numa ordem fixa**: tabelas sempre depois de figuras,
conclusão sempre por último. Um capítulo que precisa terminar por "o que não passou" não cabe nessa
ordem. A chave ``blocos`` resolve: quando presente, é uma lista ordenada de blocos, e o renderizador
a segue; sem ela, :func:`blocos_da_secao` converte as chaves antigas na mesma ordem de antes, então
as seções que já existem (e os provedores de extensão) saem exatamente como saíam.

Tipos de bloco (o campo ``tipo``):

* ``paragrafo`` — ``texto``; ``manter_com_proximo`` cola o parágrafo no bloco seguinte;
* ``subtitulo`` — ``texto`` e ``tom``: rótulo curto, sem numeração, de um trecho do capítulo;
* ``destaque`` — ``rotulo``, ``texto`` e ``tom``: caixa de resultado (o rótulo carrega a palavra
  que o tom representa, para o documento impresso em preto e branco continuar legível);
* ``nota``, ``bullets`` (``itens``), ``passos`` (``itens``), ``formula`` (``texto``);
* ``imagem`` — os campos de sempre (``png``, ``legenda``, ``largura_pol``…);
* ``tabela`` — ``cabecalhos``, ``linhas``, ``larguras`` (somam 9 360), ``fonte``, ``legenda`` e,
  opcionalmente, ``tom`` (cor do cabeçalho) e ``zebra``. Uma célula pode ser ``(principal,
  detalhe)``: o detalhe vai numa segunda linha, menor e em cinza.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TONS = ("ok", "erro", "atencao", "neutro")

#: Cores por tom, em hexadecimal sem ``#``: ``fundo`` (caixas e cabeçalhos claros do Word),
#: ``borda`` e ``texto``. A paleta é a do memorial — azul-marinho para o que atende, vermelho
#: escuro para o que reprova, âmbar escuro para a atenção — e não verde/vermelho de semáforo.
PALETA_TONS: dict[str, dict[str, str]] = {
    "ok": {"fundo": "E8EEF5", "borda": "1F3A5F", "texto": "1F3A5F"},
    "erro": {"fundo": "FBEAEA", "borda": "9B1C1C", "texto": "9B1C1C"},
    "atencao": {"fundo": "FFF6DD", "borda": "7A5A00", "texto": "7A5A00"},
    "neutro": {"fundo": "F4F6F9", "borda": "C9D4DE", "texto": "26323D"},
}


def tom_valido(tom: Any) -> str:
    """O tom pedido, ou ``neutro`` quando ele não existe."""
    return tom if tom in PALETA_TONS else "neutro"


def blocos_da_secao(secao: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Blocos de uma seção, na ordem em que devem ser desenhados."""
    explicitos = secao.get("blocos")
    if explicitos is not None:
        return [dict(bloco) for bloco in explicitos if isinstance(bloco, Mapping)]

    blocos: list[dict[str, Any]] = []
    paragrafos = list(secao.get("paragrafos", []))
    tem_tabelas = bool(secao.get("tabelas"))
    for indice, texto in enumerate(paragrafos):
        blocos.append(
            {
                "tipo": "paragrafo",
                "texto": texto,
                # O último parágrafo antes de uma tabela fica na mesma página dela.
                "manter_com_proximo": tem_tabelas and indice == len(paragrafos) - 1,
            }
        )
    if secao.get("nota"):
        blocos.append({"tipo": "nota", "texto": secao["nota"]})
    if secao.get("bullets"):
        blocos.append({"tipo": "bullets", "itens": list(secao["bullets"])})
    if secao.get("passos"):
        blocos.append({"tipo": "passos", "itens": list(secao["passos"])})
    for formula in secao.get("formulas", []):
        blocos.append({"tipo": "formula", "texto": formula})
    for imagem in secao.get("imagens", []):
        blocos.append({"tipo": "imagem", **imagem})
    for tabela in secao.get("tabelas", []):
        blocos.append({"tipo": "tabela", **tabela})
    for texto in secao.get("paragrafos_finais", []):
        blocos.append({"tipo": "paragrafo", "texto": texto})
    return blocos


def contar_imagens(secoes: Sequence[Mapping[str, Any]]) -> int:
    """Quantas figuras as seções levam, estejam elas em ``imagens`` ou em blocos."""
    return sum(
        1 for secao in secoes for bloco in blocos_da_secao(secao) if bloco["tipo"] == "imagem"
    )
