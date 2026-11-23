"""Registro técnico e memorial das páginas de verificação feitas de grupos de linhas.

As páginas de forças localizadas, monovia, ligação rígida, contenção lateral, fadiga, viga mista,
nós de tubos, aberturas na alma, terças e incêndio fecham o cálculo do mesmo jeito: grupos de
:class:`~core.verificacao.Verificacao` (o título do grupo vira um subtítulo no memorial), dados de
entrada, método, premissas e referências. Este módulo monta o registro do projeto e o memorial
separado (trecho em Word ou o PDF do padrão) a partir disso, sem repetir o código em cada módulo.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)


@dataclass
class Grupo:
    """Um bloco de verificações com o seu título (no memorial, um subtítulo)."""

    nome: str
    linhas: list[Verificacao] = field(default_factory=list)


def decisivas(grupos: Sequence[Grupo]) -> list[Verificacao]:
    """As linhas que se aplicam (sem as N/A), na ordem dos grupos."""
    return [v for g in grupos for v in g.linhas if v.status != "N/A"]


def utilizacao_maxima(linhas: Sequence[Verificacao]) -> float:
    """O maior aproveitamento das linhas de resistência (0 sem nenhuma).

    As regras geométricas (``tipo="limite"``) só aprovam ou reprovam: a razão delas não é um
    aproveitamento de resistência (a convenção de :class:`core.verificacao.Verificacao`).
    """
    valores = [
        v.aproveitamento
        for v in linhas
        if v.aproveitamento is not None and v.tipo == "resistencia" and v.status in ("OK", "NÃO OK")
    ]
    return max(valores, default=0.0)


def governante(linhas: Sequence[Verificacao]) -> Verificacao | None:
    candidatas = [
        v
        for v in linhas
        if v.aproveitamento is not None and v.tipo == "resistencia" and v.status in ("OK", "NÃO OK")
    ]
    return max(candidatas, key=lambda v: v.aproveitamento or 0.0, default=None)


def situacao(linhas: Sequence[Verificacao]) -> str:
    """ "ATENDE", "ATENDE COM RESSALVAS" ou "NÃO ATENDE" pelas linhas que se aplicam."""
    geral = status_geral(linhas)
    return {"NÃO OK": "NÃO ATENDE", "ALERTA": "ATENDE COM RESSALVAS"}.get(geral, "ATENDE")


def frase_do_resultado(linhas: Sequence[Verificacao], objeto: str) -> str:
    """Uma frase de memorial com a situação e a verificação que governa."""
    g = governante(linhas)
    reprovadas = [v.nome for v in linhas if v.status == "NÃO OK"]
    alertas = [v.nome for v in linhas if v.status == "ALERTA"]
    if reprovadas:
        texto = f"{objeto} não atende: " + "; ".join(reprovadas) + "."
    else:
        texto = f"{objeto} atende a todas as verificações aplicáveis"
        if g is not None and g.aproveitamento is not None:
            texto += f"; governa {g.nome.lower()} ({100 * g.aproveitamento:.0f} %)"
        texto += "."
    if alertas:
        texto += " Pedem atenção: " + "; ".join(alertas) + "."
    return texto


def registro_padrao(
    *,
    modulo_id: str,
    modulo_titulo: str,
    titulo: str,
    grupos: Sequence[Grupo],
    entradas: Mapping[str, Any],
    metodo: str,
    premissas: Sequence[str],
    referencias: Sequence[str],
    objeto: str,
    alertas: Sequence[str] = (),
    figuras: list[dict[str, object]] | None = None,
    tabelas: Sequence[Mapping[str, Any]] = (),
    resultados_extras: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """O registro técnico do projeto (e do memorial) com as linhas que se aplicam."""
    linhas = decisivas(grupos)
    geral = status_geral(linhas)
    destaque = frase_do_resultado(linhas, objeto)
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(linhas),
        "grupos": [
            {"nome": g.nome, "verificacoes": [v.nome for v in g.linhas if v.status != "N/A"]}
            for g in grupos
            if any(v.status != "N/A" for v in g.linhas)
        ],
        "utilizacao_maxima": numero_json(utilizacao_maxima(linhas), 4),
        "destaque_memorial": destaque,
    }
    if tabelas:
        resultados["tabelas_memorial"] = [dict(t) for t in tabelas]
    if figuras:
        resultados["figuras_2d"] = list(figuras)
    if resultados_extras:
        resultados.update(dict(resultados_extras))
    todas_alertas = [f"{v.nome}: {v.formula}" for v in linhas if v.status in ("NÃO OK", "ALERTA")]
    todas_alertas += [a for a in alertas if a not in todas_alertas]
    return criar_registro_tecnico(
        modulo=modulo_titulo,
        modulo_id=modulo_id,
        titulo=titulo,
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=dict(entradas),
        resultados=resultados,
        metodo=metodo,
        premissas=list(premissas),
        alertas=todas_alertas,
        referencias=list(referencias),
        conclusao=destaque,
    )


def memorial(
    registro: Mapping[str, Any],
    *,
    projeto: Mapping[str, Any] | None = None,
    formato: str = "word",
    nome_padrao: str = "Memorial",
) -> bytes:
    """O memorial só deste cálculo: em Word, o trecho para colar no documento oficial
    (:mod:`core.memorial_trecho`); em PDF, o documento do padrão do memorial do projeto."""
    from core.technical_records import normalizar_registro_tecnico

    reg = normalizar_registro_tecnico(dict(registro))
    if formato != "pdf":
        from core.memorial_trecho import trecho_de_registro

        return trecho_de_registro(reg, projeto=projeto)
    # o gerador do memorial está fora da lista do mypy: importado pelo nome
    relatorio = importlib.import_module("core.project_report")
    base: dict[str, Any] = dict(projeto) if projeto else {"nome": nome_padrao}
    base["registros_tecnicos"] = [reg]
    conteudo: bytes = relatorio.gerar_relatorio_industrial_pdf(base, secoes_incluidas=["registros"])
    return conteudo


def linha_info(
    nome: str, valor: float | None, unidade: str, referencia: str, formula: str
) -> Verificacao:
    """Uma grandeza mostrada sem critério (status INFO)."""
    return Verificacao(
        nome, valor, None, unidade, referencia, formula, status="INFO", tipo="informativo"
    )


def linha_na(nome: str, unidade: str, referencia: str, motivo: str) -> Verificacao:
    return Verificacao(nome, None, None, unidade, referencia, motivo, status="N/A")


def linha_alerta(nome: str, referencia: str, texto: str, unidade: str = "") -> Verificacao:
    return Verificacao(nome, None, None, unidade, referencia, texto, status="ALERTA", tipo="limite")


def linha_limite(
    nome: str,
    valor: float,
    limite: float,
    unidade: str,
    referencia: str,
    formula: str,
    *,
    minimo: bool = False,
    obrigatoria: bool = True,
) -> Verificacao:
    """Regra geométrica: ``valor ≤ limite`` (ou ``valor ≥ limite`` com ``minimo``).

    O aproveitamento fica como a razão que cresce até 1 no limite, para o resumo ordenar.
    """
    if minimo:
        ok = valor >= limite - 1e-9
        aprov = limite / valor if valor > 0 else float("inf")
    else:
        ok = valor <= limite + 1e-9
        aprov = valor / limite if limite > 0 else float("inf")
    status = "OK" if ok else ("NÃO OK" if obrigatoria else "ALERTA")
    return Verificacao(
        nome, valor, limite, unidade, referencia, formula, status=status, aproveitamento=aprov,
        tipo="limite", obrigatoria=obrigatoria,
    )  # fmt: skip
