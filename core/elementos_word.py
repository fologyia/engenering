"""Documento Word (editável) de um caso do Cálculo de peças."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core import memorial_verificacoes as mv
from core.beam_charts import COR_CORTANTE, SerieDiagrama, renderizar_diagrama
from core.elementos_base import (
    Caso,
    Grafico,
    Metrica,
    Resultado,
    Valores,
    entradas_legiveis,
    tabelas_de_entrada,
)
from core.verificacao import formatar_percentual
from core.word_documento import DocumentoWord, numero_pt

_pt = mv.decimal_ptbr


def _numero(valor: Any, casas: int = 3) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, (int, float)):
        if math.isinf(valor):
            return "∞"
        return numero_pt(float(valor), casas)
    return str(valor)


def _metrica(metrica: Metrica) -> str:
    texto = _numero(metrica.valor, metrica.casas)
    return f"{texto} {metrica.unidade}".strip()


def _desenhos_do_grafico(grafico: Grafico) -> list[tuple[bytes, str]]:
    """Cada curva do gráfico vira um diagrama: o Word não tem o gráfico interativo da tela."""
    curvas: dict[str, list[tuple[float, float]]] = {}
    for x, y, nome in grafico.pontos:
        curvas.setdefault(nome, []).append((x, y))
    desenhos: list[tuple[bytes, str]] = []
    for nome, pontos in curvas.items():
        rotulo = grafico.titulo if len(curvas) == 1 else f"{grafico.titulo}: {nome}"
        imagem = renderizar_diagrama(
            SerieDiagrama(
                titulo=rotulo,
                unidade=grafico.rotulo_y,
                pontos=tuple(pontos),
                cor=grafico.cor or COR_CORTANTE,
                descricao=rotulo,
                rotulo_x=grafico.rotulo_x,
            )
        )
        desenhos.append((imagem.png, rotulo))
    return desenhos


def gerar_word_do_caso(
    caso: Caso,
    valores: Valores,
    resultado: Resultado,
    *,
    projeto: Mapping[str, Any] | None = None,
) -> bytes:
    documento = DocumentoWord()
    documento.titulo(f"Cálculo de peças: {caso.titulo}")
    if projeto:
        documento.paragrafo(f"Projeto: {projeto.get('nome') or ''}", legenda=True)
    documento.paragrafo(caso.descricao)
    documento.paragrafo(_pt(resultado.resumo), negrito=True)

    documento.titulo("Dados de entrada", 2)
    documento.tabela(
        ["Dado", "Valor"],
        [[rotulo, _numero(valor)] for rotulo, valor in entradas_legiveis(caso, valores).items()],
        [150, 90],
    )

    for rotulo, (campo, linhas) in tabelas_de_entrada(caso, valores).items():
        if not linhas:
            continue
        documento.titulo(rotulo, 2)
        documento.tabela(
            [coluna.rotulo_completo for coluna in campo.colunas],
            [[_numero(linha.get(coluna.chave)) for coluna in campo.colunas] for linha in linhas],
        )

    for figura in resultado.figuras:
        documento.figura(figura.png, figura.legenda or figura.titulo, largura_mm=170)

    if resultado.metricas:
        documento.titulo("Resultados", 2)
        documento.tabela(
            ["Grandeza", "Valor"],
            [[m.rotulo, _metrica(m)] for m in resultado.metricas],
            [150, 90],
        )

    if resultado.verificacoes:
        documento.titulo("Verificações", 2)
        documento.tabela(
            [
                "Verificação",
                "Solicitante",
                "Limite",
                "Un.",
                "Aprov.",
                "Status",
                "Cálculo e referência",
            ],
            [
                [
                    v.nome,
                    _numero(v.solicitante),
                    _numero(v.resistente),
                    v.unidade,
                    formatar_percentual(v.aproveitamento),
                    v.status,
                    _pt(f"{v.formula} — {v.referencia}"),
                ]
                for v in resultado.verificacoes
            ],
            [56, 20, 20, 16, 16, 18, 127],
            status_coluna=5,
        )

    if resultado.pontos:
        documento.titulo("Tensões nos pontos avaliados", 2)
        documento.tabela(
            ["Ponto", "σx (MPa)", "σy (MPa)", "σz (MPa)", "τxy (MPa)", "von Mises (MPa)"],
            [
                [
                    p.nome,
                    _numero(p.sigma_x, 2),
                    _numero(p.sigma_y, 2),
                    _numero(p.sigma_z, 2),
                    _numero(p.tau_xy, 2),
                    _numero(p.von_mises, 2),
                ]
                for p in resultado.pontos
            ],
            [90, 30, 30, 30, 30, 30],
        )

    for tabela in resultado.tabelas:
        if not tabela.linhas:
            continue
        documento.titulo(tabela.titulo, 2)
        colunas = list(tabela.linhas[0])
        documento.tabela(
            colunas, [[_numero(linha.get(c)) for c in colunas] for linha in tabela.linhas]
        )
        if tabela.legenda:
            documento.paragrafo(tabela.legenda, legenda=True)

    for grafico in resultado.graficos:
        for png, legenda in _desenhos_do_grafico(grafico):
            documento.figura(png, legenda, largura_mm=170)

    if resultado.alertas:
        documento.titulo("Atenção", 2)
        documento.itens([_pt(texto) for texto in resultado.alertas])
    documento.titulo("Hipóteses do cálculo", 2)
    documento.itens(list(resultado.hipoteses))
    documento.titulo("Referências", 2)
    documento.itens(list(resultado.referencias))
    return documento.bytes()
