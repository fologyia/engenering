"""Comparação legível entre duas versões de um projeto industrial.

As revisões controladas guardam o documento inteiro, mas até aqui só dava
para restaurá-las — não para saber **o que** mudou entre a revisão emitida e
a atual. Este módulo compara dois documentos e devolve uma lista plana de
diferenças com seção, item, campo, valor anterior e valor novo, ignorando
os campos administrativos (datas, hashes, estados recalculados) que mudam
sozinhos e não representam uma decisão de engenharia.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TIPO_ALTERADO = "Alterado"
TIPO_INCLUIDO = "Incluído"
TIPO_REMOVIDO = "Removido"

# Campos de primeiro nível que descrevem o projeto; a ordem é a de exibição.
_CAMPOS_PROJETO: tuple[tuple[str, str], ...] = (
    ("nome", "Nome"),
    ("codigo", "Código"),
    ("status", "Situação"),
    ("tipo_projeto", "Tipo de projeto"),
    ("cliente", "Cliente"),
    ("unidade_industrial", "Unidade industrial"),
    ("area", "Área"),
    ("tag_equipamento", "TAG principal"),
    ("descricao", "Descrição"),
    ("objetivo", "Objetivo"),
    ("processo", "Processo"),
    ("regime_operacao", "Regime de operação"),
    ("responsavel", "Responsável técnico"),
    ("verificador", "Verificador"),
    ("aprovador", "Aprovador"),
)

_CAMPOS_BASE: tuple[tuple[str, str], ...] = (
    ("referencias_desenho", "Desenhos e documentos"),
    ("base_carregamentos", "Base dos carregamentos"),
    ("condicoes_operacao", "Condições de operação"),
    ("criterio_aceitacao", "Critérios de aceitação"),
    ("vida_requerida", "Vida requerida"),
    ("limitacoes", "Limitações e exclusões"),
)

# Coleções identificadas por ``id``: (campo, seção, campos que nomeiam o item).
_COLECOES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("componentes", "Escopo físico", ("tag", "descricao")),
    ("materiais_projeto", "Materiais do projeto", ("nome", "condicao")),
    ("casos_carga", "Casos de carga", ("codigo", "nome")),
    ("combinacoes_carga", "Combinações de carga", ("nome",)),
    ("normas", "Matriz normativa", ("codigo", "edicao")),
    ("anexos", "Documentos de entrada", ("codigo", "titulo")),
    ("registros_tecnicos", "Registros técnicos", ("titulo", "modulo")),
    ("checklist", "Checklist", ("item",)),
)

# O que muda sozinho a cada salvamento e não é decisão de ninguém.
_IGNORAR_EM_ITENS = frozenset(
    {
        "id",
        "criado_em",
        "atualizado_em",
        "hash_calculo",
        "estado_dependencias",
        "dependencias",
        "dependencias_ids",
        "avaliado_em",
    }
)
_IGNORAR_EM_CRITERIOS = frozenset({"atualizado_em", "schema_criterios"})

LIMITE_TEXTO = 160


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        return f"{valor:.6g}"
    if isinstance(valor, Mapping):
        partes = [f"{chave}={_texto(item)}" for chave, item in valor.items()]
        return "; ".join(partes)
    if isinstance(valor, Sequence) and not isinstance(valor, (str, bytes)):
        return "; ".join(_texto(item) for item in valor)
    return str(valor).strip()


def _abreviar(texto: str) -> str:
    texto = " ".join(texto.split())
    if len(texto) <= LIMITE_TEXTO:
        return texto
    return texto[: LIMITE_TEXTO - 1].rstrip() + "…"


def _iguais(antes: Any, depois: Any) -> bool:
    if isinstance(antes, Mapping) and isinstance(depois, Mapping):
        chaves = set(antes) | set(depois)
        return all(_iguais(antes.get(chave), depois.get(chave)) for chave in chaves)
    if (
        isinstance(antes, Sequence)
        and isinstance(depois, Sequence)
        and not isinstance(antes, (str, bytes))
        and not isinstance(depois, (str, bytes))
    ):
        return len(antes) == len(depois) and all(
            _iguais(a, b) for a, b in zip(antes, depois, strict=True)
        )
    if isinstance(antes, bool) or isinstance(depois, bool):
        return antes == depois
    if isinstance(antes, (int, float)) and isinstance(depois, (int, float)):
        return float(antes) == float(depois)
    return _texto(antes) == _texto(depois)


def _diferenca(
    secao: str, item: str, campo: str, tipo: str, antes: Any, depois: Any
) -> dict[str, str]:
    return {
        "secao": secao,
        "item": item,
        "campo": campo,
        "tipo": tipo,
        "antes": _abreviar(_texto(antes)),
        "depois": _abreviar(_texto(depois)),
    }


def _mapeamento(valor: Any) -> Mapping[str, Any]:
    return valor if isinstance(valor, Mapping) else {}


def _sequencia(valor: Any) -> Sequence[Any]:
    if isinstance(valor, Sequence) and not isinstance(valor, (str, bytes)):
        return valor
    return []


def _rotulo_item(item: Mapping[str, Any], nomes: Sequence[str], posicao: int) -> str:
    partes = [_texto(item.get(nome)) for nome in nomes if _texto(item.get(nome))]
    return " · ".join(partes) or f"item {posicao}"


def _comparar_mapeamentos(
    secao: str,
    item: str,
    antes: Mapping[str, Any],
    depois: Mapping[str, Any],
    *,
    ignorar: frozenset[str] = frozenset(),
    prefixo: str = "",
) -> list[dict[str, str]]:
    """Compara campo a campo; dicionários aninhados viram ``grupo.campo``."""
    diferencas: list[dict[str, str]] = []
    chaves = list(dict.fromkeys([*antes.keys(), *depois.keys()]))
    for chave in chaves:
        if chave in ignorar:
            continue
        valor_antes = antes.get(chave)
        valor_depois = depois.get(chave)
        nome = f"{prefixo}{chave}"
        # Um grupo que só existe de um lado (critérios recém-criados, por
        # exemplo) é comparado campo a campo contra o vazio, para a lista
        # dizer "fator mínimo incluído: 2" e não "seguranca incluído: {...}".
        um_mapeamento = isinstance(valor_antes, Mapping) or isinstance(valor_depois, Mapping)
        outro_vazio = valor_antes in (None, {}) or valor_depois in (None, {})
        if um_mapeamento and (
            (isinstance(valor_antes, Mapping) and isinstance(valor_depois, Mapping)) or outro_vazio
        ):
            diferencas.extend(
                _comparar_mapeamentos(
                    secao,
                    item,
                    valor_antes if isinstance(valor_antes, Mapping) else {},
                    valor_depois if isinstance(valor_depois, Mapping) else {},
                    ignorar=ignorar,
                    prefixo=f"{nome}.",
                )
            )
            continue
        if _iguais(valor_antes, valor_depois):
            continue
        if chave not in antes:
            tipo = TIPO_INCLUIDO
        elif chave not in depois:
            tipo = TIPO_REMOVIDO
        else:
            tipo = TIPO_ALTERADO
        diferencas.append(_diferenca(secao, item, nome, tipo, valor_antes, valor_depois))
    return diferencas


def _comparar_colecao(
    secao: str,
    nomes: Sequence[str],
    antes: Sequence[Any],
    depois: Sequence[Any],
) -> list[dict[str, str]]:
    """Casa os itens pelo ``id``; sem id, pela posição na lista."""
    diferencas: list[dict[str, str]] = []

    def indexar(lista: Sequence[Any]) -> dict[str, tuple[int, Mapping[str, Any]]]:
        indice: dict[str, tuple[int, Mapping[str, Any]]] = {}
        for posicao, item in enumerate(lista, start=1):
            if not isinstance(item, Mapping):
                continue
            chave = _texto(item.get("id")) or f"#{posicao}"
            indice[chave] = (posicao, item)
        return indice

    mapa_antes = indexar(antes)
    mapa_depois = indexar(depois)
    for chave, (posicao, item) in mapa_antes.items():
        rotulo = _rotulo_item(item, nomes, posicao)
        if chave not in mapa_depois:
            diferencas.append(_diferenca(secao, rotulo, "", TIPO_REMOVIDO, rotulo, ""))
            continue
        _, novo = mapa_depois[chave]
        rotulo_novo = _rotulo_item(novo, nomes, posicao)
        diferencas.extend(
            _comparar_mapeamentos(
                secao, rotulo_novo, item, novo, ignorar=_IGNORAR_EM_ITENS
            )
        )
    for chave, (posicao, item) in mapa_depois.items():
        if chave in mapa_antes:
            continue
        rotulo = _rotulo_item(item, nomes, posicao)
        diferencas.append(_diferenca(secao, rotulo, "", TIPO_INCLUIDO, "", rotulo))
    return diferencas


def comparar_documentos(
    antes: Mapping[str, Any], depois: Mapping[str, Any]
) -> list[dict[str, str]]:
    """Lista as diferenças de ``antes`` para ``depois``, por seção.

    Cada linha traz ``secao``, ``item``, ``campo``, ``tipo`` (Alterado,
    Incluído ou Removido), ``antes`` e ``depois`` já formatados para
    exibição. Uma lista vazia significa que nada de engenharia mudou — o que
    não impede ``atualizado_em`` ou hashes recalculados de serem diferentes.
    """
    diferencas: list[dict[str, str]] = []
    for campo, rotulo in _CAMPOS_PROJETO:
        if not _iguais(antes.get(campo), depois.get(campo)):
            diferencas.append(
                _diferenca(
                    "Identificação", "", rotulo, TIPO_ALTERADO, antes.get(campo), depois.get(campo)
                )
            )

    base_antes = _mapeamento(antes.get("base_projeto"))
    base_depois = _mapeamento(depois.get("base_projeto"))
    for campo, rotulo in _CAMPOS_BASE:
        if not _iguais(base_antes.get(campo), base_depois.get(campo)):
            diferencas.append(
                _diferenca(
                    "Base de projeto", "", rotulo, TIPO_ALTERADO,
                    base_antes.get(campo), base_depois.get(campo),
                )
            )

    diferencas.extend(
        _comparar_mapeamentos(
            "Critérios do projeto",
            "",
            _mapeamento(antes.get("criterios_projeto")),
            _mapeamento(depois.get("criterios_projeto")),
            ignorar=_IGNORAR_EM_CRITERIOS,
        )
    )

    for campo, secao, nomes in _COLECOES:
        diferencas.extend(
            _comparar_colecao(secao, nomes, _sequencia(antes.get(campo)), _sequencia(depois.get(campo)))
        )
    return diferencas


def resumir_diferencas(diferencas: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """Contagens por tipo e por seção, para o cabeçalho da comparação."""
    por_tipo = {TIPO_ALTERADO: 0, TIPO_INCLUIDO: 0, TIPO_REMOVIDO: 0}
    por_secao: dict[str, int] = {}
    for item in diferencas:
        por_tipo[item["tipo"]] = por_tipo.get(item["tipo"], 0) + 1
        por_secao[item["secao"]] = por_secao.get(item["secao"], 0) + 1
    return {"total": len(diferencas), "por_tipo": por_tipo, "por_secao": por_secao}
