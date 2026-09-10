"""Registro de provedores independentes de seções do memorial industrial."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.load_cases import (
    CHAVES_CARGA,
    ROTULOS_CARGA,
    UNIDADES_CARGA,
    calcular_envelope,
    fatores_legiveis,
)

ConstrutorSecao = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ProvedorSecaoRelatorio:
    id: str
    titulo: str
    apos: str
    ordem: int
    construir: ConstrutorSecao


_PROVEDORES: dict[str, ProvedorSecaoRelatorio] = {}


def registrar_provedor(
    provedor: ProvedorSecaoRelatorio, *, substituir: bool = False
) -> None:
    chave = provedor.id.strip().casefold()
    if chave in _PROVEDORES and not substituir:
        raise ValueError(f"Provedor de relatório já registrado: {provedor.id}.")
    _PROVEDORES[chave] = provedor


def listar_provedores(*, apos: str | None = None) -> list[ProvedorSecaoRelatorio]:
    provedores = list(_PROVEDORES.values())
    if apos is not None:
        alvo = apos.strip().casefold()
        provedores = [item for item in provedores if item.apos.strip().casefold() == alvo]
    return sorted(provedores, key=lambda item: (item.ordem, item.id))


def titulos_secoes_extensao() -> dict[str, str]:
    return {item.id: item.titulo for item in listar_provedores()}


def _texto(valor: Any, padrao: str = "Não informado") -> str:
    texto = str(valor).strip() if valor is not None else ""
    return texto or padrao


def _numero(valor: Any) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return _texto(valor)
    if not math.isfinite(numero):
        return "Não finito"
    return f"{numero:.5g}".replace(".", ",")


def _float_seguro(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _secao_carregamentos(
    projeto: Mapping[str, Any], contexto: Mapping[str, Any]
) -> dict[str, Any]:
    casos = [
        item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)
    ]
    combinacoes = [
        item
        for item in projeto.get("combinacoes_carga", [])
        if isinstance(item, Mapping)
    ]
    try:
        envelope = calcular_envelope(
            casos,
            combinacoes,
            incluir_casos_isolados=not bool(combinacoes),
        )
        erro = ""
    except ValueError as exc:
        envelope = {"componentes": {}, "total_cenarios": 0}
        erro = str(exc)

    linhas_casos = []
    for caso in casos:
        vetor = caso.get("cargas", {}) if isinstance(caso.get("cargas"), Mapping) else {}
        ativos = []
        for chave in CHAVES_CARGA:
            valor = _float_seguro(vetor.get(chave, 0))
            if valor is None:
                ativos.append(f"{ROTULOS_CARGA[chave]}=valor inválido")
            elif abs(valor) > 1e-12:
                ativos.append(
                    f"{ROTULOS_CARGA[chave]}={_numero(valor)} {UNIDADES_CARGA[chave]}"
                )
        linhas_casos.append(
            [
                _texto(caso.get("codigo")),
                _texto(caso.get("nome")),
                f"{_texto(caso.get('condicao'))}\n{_texto(caso.get('natureza'))}",
                _texto(caso.get("tag")),
                "; ".join(ativos) or "Vetor nulo",
                f"{_texto(caso.get('origem'))}\n{_texto(caso.get('referencia'), '')}",
            ]
        )

    linhas_combinacoes = []
    for combinacao in combinacoes:
        linhas_combinacoes.append(
            [
                _texto(combinacao.get("nome")),
                _texto(combinacao.get("tipo")),
                fatores_legiveis(combinacao, casos),
                "Ativa" if bool(combinacao.get("ativo", True)) else "Inativa",
                _texto(combinacao.get("descricao"), ""),
            ]
        )

    linhas_envelope = []
    for chave in CHAVES_CARGA:
        item = envelope.get("componentes", {}).get(chave)
        if not item:
            continue
        linhas_envelope.append(
            [
                item["rotulo"],
                _numero(item["minimo"]),
                _numero(item["maximo"]),
                _numero(item["valor_governante"]),
                item["unidade"],
                _texto(item["cenario_governante"]),
            ]
        )

    paragrafos = [
        "Os casos preservam a origem física dos carregamentos. As combinações somam componentes algébricos e mantêm o cenário governante de cada grandeza.",
        f"Foram cadastrados {len(casos)} caso(s), {len(combinacoes)} combinação(ões) e avaliados {envelope.get('total_cenarios', 0)} cenário(s).",
    ]
    if erro:
        paragrafos.append(f"Falha de consistência detectada no conjunto de cargas: {erro}")
    return {
        "paragrafos": paragrafos,
        "tabelas": [
            {
                "legenda": "Casos de carga permanentes do projeto.",
                "cabecalhos": ["Código", "Caso", "Condição / natureza", "TAG", "Vetor não nulo", "Origem / referência"],
                "linhas": linhas_casos or [["-", "Nenhum caso cadastrado", "-", "-", "-", "-"]],
                "larguras": [1000, 1600, 1500, 900, 2600, 1760],
                "fonte": 6.8,
            },
            {
                "legenda": "Combinações registradas; os fatores não são definidos automaticamente como normativos.",
                "cabecalhos": ["Combinação", "Tipo", "Parcelas e fatores", "Estado", "Descrição"],
                "linhas": linhas_combinacoes or [["-", "-", "Nenhuma combinação cadastrada", "-", "-"]],
                "larguras": [1800, 1400, 3000, 1000, 2160],
                "fonte": 7.0,
            },
            {
                "legenda": "Envelope algébrico por componente.",
                "cabecalhos": ["Componente", "Mínimo", "Máximo", "Governante", "Unidade", "Cenário governante"],
                "linhas": linhas_envelope or [["-", "-", "-", "-", "-", "Sem cenários válidos"]],
                "larguras": [1700, 1100, 1100, 1200, 900, 3360],
                "fonte": 7.2,
            },
        ],
        "nota": (
            "O envelope não representa simultaneidade entre máximos de linhas diferentes. "
            "Confirme os fatores nas normas, especificações e bases de carregamento aplicáveis."
        ),
    }


registrar_provedor(
    ProvedorSecaoRelatorio(
        id="carregamentos",
        titulo="Casos, combinações e envelopes de carga",
        apos="base",
        ordem=10,
        construir=_secao_carregamentos,
    )
)
