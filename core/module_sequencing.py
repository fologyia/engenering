"""Sequenciamento sugerido dos módulos técnicos, exibido no cabeçalho.

O objetivo é mostrar, em cada página de cálculo, onde ela se encaixa em um
fluxo típico — sem nunca impedir o uso isolado de um módulo. Um "caso
específico" (o usuário entra direto em Fadiga, por exemplo, sem ter passado
por Casos de carga) continua funcionando normalmente: os passos anteriores
aparecem como pendentes, nunca como bloqueio.

A situação de cada passo já concluído reaproveita o motor de dependências
(:mod:`core.project_dependencies`): um cálculo cuja fonte mudou aparece aqui
com o mesmo status ("Desatualizado") mostrado na Central de Validação.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core.project_dependencies import STATUS_ATUAL, STATUS_SEM_DEPENDENCIAS, sincronizar_estados_dependencias
from core.technical_modules import obter_modulo


# Cada fluxo é uma sequência típica de módulos, do primeiro ao último. Um
# módulo pode pertencer a mais de um fluxo (ex.: Análise estática participa
# do fluxo estático e do fluxo de fadiga); a página escolhe o fluxo mais
# aderente ao progresso já feito no projeto.
FLUXOS: dict[str, tuple[str, ...]] = {
    "estatico": (
        "casos_carga",
        "assistente_cargas",
        "circulo_mohr",
        "analise_estatica",
        "analise_sensibilidade",
    ),
    "fadiga": (
        "casos_carga",
        "assistente_cargas",
        "analise_estatica",
        "analise_fadiga",
        "analise_sensibilidade",
    ),
    "compressao": (
        "casos_carga",
        "assistente_cargas",
        "flambagem_colunas",
        "analise_sensibilidade",
    ),
    "parafusos": ("casos_carga", "projeto_parafusos"),
    "aco": ("casos_carga", "estruturas_aco", "flambagem_colunas"),
}

SITUACOES = ("concluida", "atencao", "atual", "pendente")


@dataclass(frozen=True, slots=True)
class EtapaSequencia:
    modulo_id: str
    titulo: str
    pagina: str
    icone: str
    situacao: str
    detalhe: str = ""


def fluxos_do_modulo(modulo_id: str) -> list[str]:
    """Lista, em ordem de declaração, os fluxos que contêm o módulo."""
    chave = str(modulo_id or "").strip().casefold()
    return [nome for nome, sequencia in FLUXOS.items() if chave in sequencia]


def _ultimo_registro_por_modulo(
    projeto_sincronizado: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    por_modulo: dict[str, dict[str, Any]] = {}
    for registro in projeto_sincronizado.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping):
            continue
        modulo_id = str(registro.get("modulo_id") or "").strip().casefold()
        if not modulo_id:
            continue
        atual = str(registro.get("criado_em") or "")
        anterior = por_modulo.get(modulo_id)
        if anterior is None or atual >= str(anterior.get("criado_em") or ""):
            por_modulo[modulo_id] = dict(registro)
    return por_modulo


def _situacao_do_registro(registro: Mapping[str, Any]) -> tuple[str, str]:
    estado = registro.get("estado_dependencias", {})
    estado = estado if isinstance(estado, Mapping) else {}
    status = str(estado.get("status") or "")
    if status in ("", STATUS_ATUAL, STATUS_SEM_DEPENDENCIAS):
        return "concluida", ""
    motivos = estado.get("motivos", [])
    motivos = [
        str(motivo)
        for motivo in motivos
        if isinstance(motivos, Sequence) and not isinstance(motivos, (str, bytes))
    ]
    return "atencao", " ".join(motivos[:2])


def montar_sequencia(
    projeto: Mapping[str, Any] | None,
    modulo_id_atual: str,
    *,
    fluxo: str | None = None,
) -> list[EtapaSequencia] | None:
    """Monta a sequência sugerida em torno do módulo atual.

    Retorna ``None`` quando o módulo não participa de nenhum fluxo conhecido
    (ferramentas, referências e páginas de gestão) — nesse caso a página não
    deve mostrar nenhuma barra de progresso.
    """
    candidatos = [fluxo] if fluxo else fluxos_do_modulo(modulo_id_atual)
    if not candidatos:
        return None

    registros_por_modulo: dict[str, dict[str, Any]] = {}
    if projeto is not None:
        sincronizado = sincronizar_estados_dependencias(projeto)
        registros_por_modulo = _ultimo_registro_por_modulo(sincronizado)

    def concluidos(nome_fluxo: str) -> int:
        return sum(
            1 for passo in FLUXOS[nome_fluxo] if passo.casefold() in registros_por_modulo
        )

    nome_fluxo = max(candidatos, key=concluidos)
    chave_atual = str(modulo_id_atual or "").strip().casefold()

    etapas: list[EtapaSequencia] = []
    for passo_id in FLUXOS[nome_fluxo]:
        modulo = obter_modulo(passo_id)
        registro = registros_por_modulo.get(passo_id.casefold())
        if passo_id.casefold() == chave_atual:
            situacao, detalhe = "atual", ""
        elif registro is not None:
            situacao, detalhe = _situacao_do_registro(registro)
        else:
            situacao, detalhe = "pendente", ""
        etapas.append(
            EtapaSequencia(
                modulo_id=passo_id,
                titulo=modulo.titulo,
                pagina=modulo.pagina,
                icone=modulo.icone,
                situacao=situacao,
                detalhe=detalhe,
            )
        )
    return etapas


def proximo_passo(etapas: Sequence[EtapaSequencia] | None) -> EtapaSequencia | None:
    """Primeiro passo ainda não concluído depois do módulo atual."""
    if not etapas:
        return None
    indice_atual = next((i for i, item in enumerate(etapas) if item.situacao == "atual"), None)
    if indice_atual is None:
        return None
    for etapa in etapas[indice_atual + 1 :]:
        if etapa.situacao != "concluida":
            return etapa
    return None
