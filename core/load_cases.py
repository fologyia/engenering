"""Casos, combinações e envelopes de carregamento para projetos industriais.

O módulo combina componentes algébricos preservando os sinais. O envelope é
um resumo por componente; máximos de componentes diferentes não devem ser
interpretados como simultâneos sem consultar a combinação governante.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ComponenteCarga:
    chave: str
    rotulo: str
    unidade: str


COMPONENTES_CARGA = (
    ComponenteCarga("Fx_kN", "Força X", "kN"),
    ComponenteCarga("Fy_kN", "Força Y", "kN"),
    ComponenteCarga("Fz_kN", "Força Z", "kN"),
    ComponenteCarga("Mx_kNm", "Momento X", "kN·m"),
    ComponenteCarga("My_kNm", "Momento Y", "kN·m"),
    ComponenteCarga("Mz_kNm", "Momento Z", "kN·m"),
    ComponenteCarga("pressao_bar", "Pressão relativa", "bar"),
    ComponenteCarga("delta_temperatura_C", "Variação de temperatura", "°C"),
)

CHAVES_CARGA = tuple(item.chave for item in COMPONENTES_CARGA)
ROTULOS_CARGA = {item.chave: item.rotulo for item in COMPONENTES_CARGA}
UNIDADES_CARGA = {item.chave: item.unidade for item in COMPONENTES_CARGA}

CONDICOES_OPERACIONAIS = (
    "Operação normal",
    "Partida",
    "Parada",
    "Emergência",
    "Teste",
    "Manutenção",
    "Transporte",
    "Içamento",
    "Montagem",
    "Outra",
)

NATUREZAS_CARGA = (
    "Permanente",
    "Variável",
    "Pressão",
    "Térmica",
    "Ambiental",
    "Acidental",
    "Montagem",
    "Outra",
)

TIPOS_COMBINACAO = (
    "Operacional",
    "Resistência / ELU",
    "Serviço / ELS",
    "Excepcional",
    "Teste",
    "Transporte / montagem",
)


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _finito(nome: str, valor: Any) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{nome} precisa ser numérico.") from erro
    if not math.isfinite(numero):
        raise ValueError(f"{nome} precisa ser finito.")
    return numero


def normalizar_vetor(cargas: Mapping[str, Any] | None) -> dict[str, float]:
    origem = cargas or {}
    return {chave: _finito(ROTULOS_CARGA[chave], origem.get(chave, 0.0)) for chave in CHAVES_CARGA}


def criar_caso_carga(
    *,
    nome: str,
    codigo: str = "",
    condicao: str = "Operação normal",
    natureza: str = "Permanente",
    tag: str = "",
    origem: str = "",
    referencia: str = "",
    cargas: Mapping[str, Any] | None = None,
    observacoes: str = "",
    ativo: bool = True,
    caso_id: str | None = None,
) -> dict[str, Any]:
    nome_limpo = _texto(nome)
    if not nome_limpo:
        raise ValueError("Informe o nome do caso de carga.")
    return {
        "id": _texto(caso_id) or str(uuid4()),
        "codigo": _texto(codigo) or nome_limpo,
        "nome": nome_limpo,
        "condicao": _texto(condicao) or "Outra",
        "natureza": _texto(natureza) or "Outra",
        "tag": _texto(tag),
        "origem": _texto(origem),
        "referencia": _texto(referencia),
        "cargas": normalizar_vetor(cargas),
        "observacoes": _texto(observacoes),
        "ativo": bool(ativo),
    }


def normalizar_caso_carga(caso: Mapping[str, Any]) -> dict[str, Any]:
    return criar_caso_carga(
        caso_id=_texto(caso.get("id")) or None,
        nome=_texto(caso.get("nome")) or _texto(caso.get("codigo")),
        codigo=_texto(caso.get("codigo")),
        condicao=_texto(caso.get("condicao")),
        natureza=_texto(caso.get("natureza")),
        tag=_texto(caso.get("tag")),
        origem=_texto(caso.get("origem")),
        referencia=_texto(caso.get("referencia")),
        cargas=caso.get("cargas") if isinstance(caso.get("cargas"), Mapping) else {},
        observacoes=_texto(caso.get("observacoes")),
        ativo=bool(caso.get("ativo", True)),
    )


def criar_combinacao_carga(
    *,
    nome: str,
    fatores: Mapping[str, Any],
    tipo: str = "Operacional",
    descricao: str = "",
    ativo: bool = True,
    combinacao_id: str | None = None,
) -> dict[str, Any]:
    nome_limpo = _texto(nome)
    if not nome_limpo:
        raise ValueError("Informe o nome da combinação.")
    fatores_limpos = {
        _texto(caso_id): _finito(f"Fator de {caso_id}", fator)
        for caso_id, fator in fatores.items()
        if _texto(caso_id) and abs(_finito(f"Fator de {caso_id}", fator)) > 1e-15
    }
    if not fatores_limpos:
        raise ValueError("A combinação precisa conter ao menos um caso com fator não nulo.")
    return {
        "id": _texto(combinacao_id) or str(uuid4()),
        "nome": nome_limpo,
        "tipo": _texto(tipo) or "Operacional",
        "descricao": _texto(descricao),
        "fatores": fatores_limpos,
        "ativo": bool(ativo),
    }


def normalizar_combinacao_carga(combinacao: Mapping[str, Any]) -> dict[str, Any]:
    fatores = combinacao.get("fatores") if isinstance(combinacao.get("fatores"), Mapping) else {}
    return criar_combinacao_carga(
        combinacao_id=_texto(combinacao.get("id")) or None,
        nome=_texto(combinacao.get("nome")),
        tipo=_texto(combinacao.get("tipo")),
        descricao=_texto(combinacao.get("descricao")),
        fatores=fatores,
        ativo=bool(combinacao.get("ativo", True)),
    )


def calcular_combinacao(
    casos: Sequence[Mapping[str, Any]], combinacao: Mapping[str, Any]
) -> dict[str, Any]:
    casos_por_id = {
        str(caso.get("id")): normalizar_caso_carga(caso)
        for caso in casos
        if str(caso.get("id") or "").strip()
    }
    fatores = combinacao.get("fatores") if isinstance(combinacao.get("fatores"), Mapping) else {}
    ausentes = sorted(str(caso_id) for caso_id in fatores if str(caso_id) not in casos_por_id)
    if ausentes:
        raise ValueError("Combinação referencia casos inexistentes: " + ", ".join(ausentes))
    vetor = {chave: 0.0 for chave in CHAVES_CARGA}
    parcelas: list[dict[str, Any]] = []
    for caso_id, fator_bruto in fatores.items():
        fator = _finito(f"Fator de {caso_id}", fator_bruto)
        caso = casos_por_id[str(caso_id)]
        if not caso.get("ativo", True):
            continue
        for chave in CHAVES_CARGA:
            vetor[chave] += fator * caso["cargas"][chave]
        parcelas.append(
            {
                "caso_id": str(caso_id),
                "codigo": caso["codigo"],
                "nome": caso["nome"],
                "fator": fator,
            }
        )
    return {
        "id": str(combinacao.get("id") or ""),
        "nome": _texto(combinacao.get("nome")) or "Combinação",
        "tipo": _texto(combinacao.get("tipo")) or "Operacional",
        "vetor": vetor,
        "parcelas": parcelas,
    }


def calcular_combinacoes(
    casos: Sequence[Mapping[str, Any]],
    combinacoes: Sequence[Mapping[str, Any]],
    *,
    somente_ativas: bool = True,
) -> list[dict[str, Any]]:
    resultados = []
    for combinacao in combinacoes:
        if somente_ativas and not bool(combinacao.get("ativo", True)):
            continue
        resultados.append(calcular_combinacao(casos, combinacao))
    return resultados


def _resultados_casos_isolados(casos: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    resultados = []
    for caso_bruto in casos:
        caso = normalizar_caso_carga(caso_bruto)
        if not caso["ativo"]:
            continue
        resultados.append(
            {
                "id": f"caso:{caso['id']}",
                "nome": f"Caso isolado - {caso['codigo']}",
                "tipo": caso["condicao"],
                "vetor": dict(caso["cargas"]),
                "parcelas": [
                    {
                        "caso_id": caso["id"],
                        "codigo": caso["codigo"],
                        "nome": caso["nome"],
                        "fator": 1.0,
                    }
                ],
            }
        )
    return resultados


def calcular_envelope(
    casos: Sequence[Mapping[str, Any]],
    combinacoes: Sequence[Mapping[str, Any]],
    *,
    incluir_casos_isolados: bool = False,
) -> dict[str, Any]:
    resultados = calcular_combinacoes(casos, combinacoes)
    if incluir_casos_isolados or not resultados:
        resultados.extend(_resultados_casos_isolados(casos))
    if not resultados:
        return {"resultados": [], "componentes": {}, "total_cenarios": 0}

    envelope: dict[str, dict[str, Any]] = {}
    for chave in CHAVES_CARGA:
        minimo = min(resultados, key=lambda item: item["vetor"][chave])
        maximo = max(resultados, key=lambda item: item["vetor"][chave])
        max_abs = max(resultados, key=lambda item: abs(item["vetor"][chave]))
        envelope[chave] = {
            "rotulo": ROTULOS_CARGA[chave],
            "unidade": UNIDADES_CARGA[chave],
            "minimo": minimo["vetor"][chave],
            "cenario_minimo": minimo["nome"],
            "maximo": maximo["vetor"][chave],
            "cenario_maximo": maximo["nome"],
            "maximo_absoluto": abs(max_abs["vetor"][chave]),
            "valor_governante": max_abs["vetor"][chave],
            "cenario_governante": max_abs["nome"],
            "cenario_governante_id": max_abs["id"],
        }
    return {
        "resultados": resultados,
        "componentes": envelope,
        "total_cenarios": len(resultados),
        "aviso": (
            "Cada linha do envelope pode ser governada por uma combinação diferente. "
            "Não use máximos independentes como um vetor simultâneo."
        ),
    }


def fatores_legiveis(
    combinacao: Mapping[str, Any], casos: Sequence[Mapping[str, Any]]
) -> str:
    nomes = {
        str(caso.get("id")): _texto(caso.get("codigo")) or _texto(caso.get("nome"))
        for caso in casos
    }
    fatores = combinacao.get("fatores") if isinstance(combinacao.get("fatores"), Mapping) else {}
    parcelas = []
    for caso_id, fator in fatores.items():
        try:
            fator_texto = f"{float(fator):g}"
        except (TypeError, ValueError):
            fator_texto = "fator inválido"
        parcelas.append(f"{fator_texto}×{nomes.get(str(caso_id), str(caso_id))}")
    return " + ".join(parcelas) or "Sem parcelas"
