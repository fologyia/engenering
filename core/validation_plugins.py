"""Regras plugáveis consumidas pela Central de Validação."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from core.load_cases import CHAVES_CARGA, calcular_envelope
from core.technical_records import avaliar_contrato_registro


@dataclass(frozen=True, slots=True)
class AchadoRegra:
    severidade: str
    categoria: str
    titulo: str
    detalhe: str
    recomendacao: str
    modulo: str = "Projeto"
    evidencia: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoRegra:
    achados: tuple[AchadoRegra, ...] = ()
    pontos_preenchidos: int = 0
    pontos_totais: int = 0


ExecutorRegra = Callable[[Mapping[str, Any]], ResultadoRegra]


@dataclass(frozen=True, slots=True)
class RegraValidacao:
    id: str
    titulo: str
    versao: str
    executar: ExecutorRegra


_REGRAS: dict[str, RegraValidacao] = {}


def registrar_regra(regra: RegraValidacao, *, substituir: bool = False) -> None:
    chave = regra.id.strip().casefold()
    if chave in _REGRAS and not substituir:
        raise ValueError(f"Regra de validação já registrada: {regra.id}.")
    _REGRAS[chave] = regra


def listar_regras() -> list[RegraValidacao]:
    return sorted(_REGRAS.values(), key=lambda item: item.id)


def executar_regras(projeto: Mapping[str, Any]) -> list[tuple[RegraValidacao, ResultadoRegra]]:
    return [(regra, regra.executar(projeto)) for regra in listar_regras()]


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _vetor_nao_nulo(vetor: Mapping[str, Any]) -> bool:
    for chave in CHAVES_CARGA:
        try:
            valor = float(vetor.get(chave, 0) or 0)
        except (TypeError, ValueError):
            return False
        if abs(valor) > 1e-12:
            return True
    return False


def _regra_contratos(projeto: Mapping[str, Any]) -> ResultadoRegra:
    achados: list[AchadoRegra] = []
    registros = [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
    ]
    for indice, registro in enumerate(registros, start=1):
        avaliacao = avaliar_contrato_registro(registro)
        titulo = _texto(registro.get("titulo")) or f"Registro {indice}"
        modulo = _texto(registro.get("modulo")) or "Registro técnico"
        if avaliacao["assinatura_presente"] and not avaliacao["assinatura_valida"]:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Integridade do cálculo",
                    f"{titulo}: assinatura do cálculo divergente",
                    "Entradas, resultados ou critérios diferem do conteúdo que originou o hash armazenado.",
                    "Regere o registro pelo módulo de origem ou documente uma nova revisão controlada.",
                    modulo=modulo,
                    evidencia=_texto(registro.get("hash_calculo")),
                )
            )
        elif not avaliacao["assinatura_presente"]:
            achados.append(
                AchadoRegra(
                    "Informação",
                    "Contrato técnico",
                    f"{titulo}: registro anterior ao contrato versionado",
                    "O conteúdo permanece legível, mas não possui assinatura técnica do esquema v2.",
                    "Ao revisar este cálculo, registre-o novamente pelo módulo correspondente.",
                    modulo=modulo,
                )
            )
        if avaliacao["faltantes"] and registro.get("schema_registro"):
            achados.append(
                AchadoRegra(
                    "Pendência",
                    "Contrato técnico",
                    f"{titulo}: contrato incompleto",
                    "Campos ausentes: " + ", ".join(avaliacao["faltantes"]) + ".",
                    "Complete o registro pelo módulo de origem antes da emissão.",
                    modulo=modulo,
                )
            )
    return ResultadoRegra(achados=tuple(achados))


def _regra_casos_carga(projeto: Mapping[str, Any]) -> ResultadoRegra:
    achados: list[AchadoRegra] = []
    casos = [item for item in projeto.get("casos_carga", []) if isinstance(item, Mapping)]
    combinacoes = [
        item
        for item in projeto.get("combinacoes_carga", [])
        if isinstance(item, Mapping)
    ]
    if not casos:
        return ResultadoRegra(
            achados=(
                AchadoRegra(
                    "Informação",
                    "Carregamentos",
                    "Casos de carga ainda não estruturados",
                    "A base de carregamentos pode existir em texto, mas não há cenários vetoriais permanentes.",
                    "Use Casos e combinações de carga quando o projeto exigir envelope e rastreabilidade por cenário.",
                    modulo="Casos de carga",
                ),
            )
        )

    preenchidos = 0
    total = 0
    ids = {str(item.get("id")) for item in casos if _texto(item.get("id"))}
    ativos = 0
    for indice, caso in enumerate(casos, start=1):
        nome = _texto(caso.get("codigo")) or _texto(caso.get("nome")) or f"Caso {indice}"
        vetor = caso.get("cargas") if isinstance(caso.get("cargas"), Mapping) else {}
        if bool(caso.get("ativo", True)):
            ativos += 1
        for valor, rotulo in (
            (_texto(caso.get("nome")), "nome"),
            (_texto(caso.get("tag")), "TAG"),
            (_texto(caso.get("origem")) or _texto(caso.get("referencia")), "origem ou referência"),
            (_vetor_nao_nulo(vetor), "vetor não nulo"),
        ):
            total += 1
            if valor:
                preenchidos += 1
            else:
                severidade = "Bloqueio" if rotulo == "vetor não nulo" else "Pendência"
                achados.append(
                    AchadoRegra(
                        severidade,
                        "Carregamentos",
                        f"{nome}: {rotulo} ausente",
                        "O caso não possui informação suficiente para uso rastreável no envelope.",
                        f"Complete {rotulo} na Central de casos de carga.",
                        modulo="Casos de carga",
                    )
                )

    if ativos >= 2 and not combinacoes:
        achados.append(
            AchadoRegra(
                "Pendência",
                "Carregamentos",
                "Casos ativos sem combinações cadastradas",
                f"Há {ativos} casos ativos, mas o envelope considera somente casos isolados.",
                "Cadastre combinações e confirme os fatores na base normativa do projeto.",
                modulo="Casos de carga",
            )
        )
    for combinacao in combinacoes:
        fatores = combinacao.get("fatores") if isinstance(combinacao.get("fatores"), Mapping) else {}
        ausentes = sorted(str(caso_id) for caso_id in fatores if str(caso_id) not in ids)
        if ausentes:
            achados.append(
                AchadoRegra(
                    "Bloqueio",
                    "Carregamentos",
                    f"{_texto(combinacao.get('nome')) or 'Combinação'}: referência inválida",
                    "Casos inexistentes: " + ", ".join(ausentes) + ".",
                    "Edite ou recrie a combinação antes de emitir o memorial.",
                    modulo="Casos de carga",
                )
            )
    try:
        calcular_envelope(casos, combinacoes, incluir_casos_isolados=not bool(combinacoes))
    except (TypeError, ValueError) as erro:
        achados.append(
            AchadoRegra(
                "Bloqueio",
                "Carregamentos",
                "Envelope de cargas inconsistente",
                str(erro),
                "Revise fatores, referências e valores numéricos dos casos.",
                modulo="Casos de carga",
            )
        )
    return ResultadoRegra(tuple(achados), preenchidos, total)


registrar_regra(RegraValidacao("contrato-registro", "Contrato dos registros técnicos", "1.0", _regra_contratos))
registrar_regra(RegraValidacao("casos-carga", "Casos e combinações de carga", "1.0", _regra_casos_carga))
