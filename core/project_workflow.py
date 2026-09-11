"""Fluxo de situação do projeto industrial, com portões de passagem.

A situação ("Em elaboração", "Em verificação", "Emitido"...) era um campo
livre do formulário: dava para marcar um projeto como Emitido com três
bloqueios abertos e sem aprovador. Este módulo define quais transições
existem e o que cada uma exige. Os portões são deliberadamente poucos e
objetivos — quem decide continua sendo o engenheiro responsável; o programa
só não deixa a situação contradizer o que o próprio projeto registra.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.project_checklist import resumo_checklist
from core.project_dependencies import (
    STATUS_AUSENTE,
    STATUS_DESATUALIZADO,
    sincronizar_estados_dependencias,
)
from core.project_validation import validar_projeto

EM_ELABORACAO = "Em elaboração"
EM_VERIFICACAO = "Em verificação"
EMITIDO = "Emitido"
SUSPENSO = "Suspenso"
ARQUIVADO = "Arquivado"

SITUACOES: tuple[str, ...] = (EM_ELABORACAO, EM_VERIFICACAO, EMITIDO, SUSPENSO, ARQUIVADO)

# Para onde cada situação pode ir. Não há atalho de "Em elaboração" direto
# para "Emitido": a verificação independente é uma etapa, não um campo.
TRANSICOES: dict[str, tuple[str, ...]] = {
    EM_ELABORACAO: (EM_VERIFICACAO, SUSPENSO, ARQUIVADO),
    EM_VERIFICACAO: (EMITIDO, EM_ELABORACAO, SUSPENSO),
    EMITIDO: (EM_ELABORACAO, ARQUIVADO),
    SUSPENSO: (EM_ELABORACAO, ARQUIVADO),
    ARQUIVADO: (EM_ELABORACAO,),
}

DESCRICOES: dict[str, str] = {
    EM_ELABORACAO: "Dados, cálculos e documentos ainda sendo produzidos.",
    EM_VERIFICACAO: "Conteúdo congelado para verificação independente.",
    EMITIDO: "Memorial liberado na revisão atual; qualquer mudança reabre o projeto.",
    SUSPENSO: "Trabalho interrompido; mantém dados e histórico.",
    ARQUIVADO: "Fora da lista de trabalho; pode ser reaberto.",
}


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def situacao_atual(projeto: Mapping[str, Any]) -> str:
    situacao = _texto(projeto.get("status"))
    return situacao if situacao in SITUACOES else EM_ELABORACAO


def transicoes_possiveis(projeto: Mapping[str, Any]) -> tuple[str, ...]:
    return TRANSICOES.get(situacao_atual(projeto), ())


def _registros_ativos(projeto: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        item
        for item in projeto.get("registros_tecnicos", [])
        if isinstance(item, Mapping) and _texto(item.get("status")).casefold() != "superado"
    ]


def avaliar_transicao(
    projeto: Mapping[str, Any],
    destino: str,
    *,
    validacao: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Diz se a mudança de situação é permitida e o que a impede ou ressalva.

    ``impedimentos`` travam a transição; ``avisos`` não travam, mas aparecem
    ao lado do botão para a decisão ser tomada sabendo. ``cria_revisao``
    indica que a transição deve gerar uma revisão controlada (reabrir um
    projeto emitido, por exemplo, não pode sobrescrever o marco emitido).
    """
    origem = situacao_atual(projeto)
    destino = _texto(destino)
    impedimentos: list[str] = []
    avisos: list[str] = []
    cria_revisao = False
    motivo = f"Situação alterada de {origem} para {destino}"

    if destino not in SITUACOES:
        impedimentos.append(f"Situação desconhecida: {destino or 'vazia'}.")
        return _resultado(origem, destino, impedimentos, avisos, cria_revisao, motivo)
    if destino == origem:
        impedimentos.append(f"O projeto já está em {origem}.")
        return _resultado(origem, destino, impedimentos, avisos, cria_revisao, motivo)
    if destino not in TRANSICOES.get(origem, ()):
        impedimentos.append(
            f"Não há passagem direta de {origem} para {destino}. "
            f"Caminhos possíveis: {', '.join(TRANSICOES.get(origem, ())) or 'nenhum'}."
        )
        return _resultado(origem, destino, impedimentos, avisos, cria_revisao, motivo)

    if destino in {EM_VERIFICACAO, EMITIDO}:
        resultado = dict(validacao) if validacao is not None else validar_projeto(projeto)
        contagens = resultado.get("contagens", {})
        bloqueios = int(contagens.get("Bloqueio", 0) or 0)
        pendencias = int(contagens.get("Pendência", 0) or 0)
        registros = _registros_ativos(projeto)
        if not registros:
            impedimentos.append("Nenhum registro técnico vigente no projeto.")

    if destino == EM_VERIFICACAO:
        if not _texto(projeto.get("verificador")):
            impedimentos.append("Verificador não definido em Identificação e responsáveis.")
        if bloqueios:
            avisos.append(
                f"{bloqueios} bloqueio(s) abertos na validação: a verificação "
                "vai encontrá-los."
            )
        motivo = "Enviado para verificação independente"

    if destino == EMITIDO:
        if not _texto(projeto.get("aprovador")):
            impedimentos.append("Aprovador não definido em Identificação e responsáveis.")
        if not _texto(projeto.get("verificador")):
            impedimentos.append("Verificador não definido em Identificação e responsáveis.")
        if bloqueios:
            impedimentos.append(
                f"{bloqueios} bloqueio(s) abertos na Central de validação."
            )
        if pendencias:
            avisos.append(f"{pendencias} pendência(s) documentais ainda abertas.")
        sincronizado = sincronizar_estados_dependencias(projeto)
        desatualizados = [
            _texto(item.get("titulo")) or "registro"
            for item in sincronizado.get("registros_tecnicos", [])
            if isinstance(item, Mapping)
            and _texto(item.get("status")).casefold() != "superado"
            and _texto((item.get("estado_dependencias") or {}).get("status"))
            in {STATUS_DESATUALIZADO, STATUS_AUSENTE}
        ]
        if desatualizados:
            impedimentos.append(
                "Cálculo(s) desatualizados em relação às fontes do projeto: "
                + "; ".join(desatualizados[:3])
                + ("…" if len(desatualizados) > 3 else ".")
            )
        vencidos = resumo_checklist(projeto.get("checklist", []))["vencidos"]
        if vencidos:
            avisos.append(f"{len(vencidos)} item(ns) do checklist com prazo vencido.")
        cria_revisao = True
        motivo = "Emissão do projeto"

    if destino == EM_ELABORACAO and origem == EMITIDO:
        cria_revisao = True
        avisos.append(
            "Reabrir um projeto emitido cria uma nova revisão controlada; a "
            "revisão emitida continua restaurável."
        )
        motivo = "Reabertura após emissão"

    if destino == SUSPENSO:
        avisos.append("Registre o motivo da suspensão para a linha do tempo.")
        motivo = "Projeto suspenso"

    if destino == ARQUIVADO:
        motivo = "Projeto arquivado"
    if destino == EM_ELABORACAO and origem in {SUSPENSO, ARQUIVADO}:
        motivo = "Projeto reaberto"

    return _resultado(origem, destino, impedimentos, avisos, cria_revisao, motivo)


def _resultado(
    origem: str,
    destino: str,
    impedimentos: list[str],
    avisos: list[str],
    cria_revisao: bool,
    motivo: str,
) -> dict[str, Any]:
    return {
        "origem": origem,
        "destino": destino,
        "permitida": not impedimentos,
        "impedimentos": impedimentos,
        "avisos": avisos,
        "cria_revisao": cria_revisao,
        "motivo": motivo,
    }


def avaliar_todas_transicoes(
    projeto: Mapping[str, Any],
    *,
    validacao: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Uma avaliação por destino possível, na ordem declarada em TRANSICOES."""
    resultado = validacao if validacao is not None else validar_projeto(projeto)
    return [
        avaliar_transicao(projeto, destino, validacao=resultado)
        for destino in transicoes_possiveis(projeto)
    ]
