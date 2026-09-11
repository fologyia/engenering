"""Leitura de carteira: todos os projetos numa mesa só.

A página de projetos mostra um projeto por vez. Quem responde por dez
verificações em andamento precisa da pergunta inversa — *quais* projetos
têm bloqueio, prazo vencido ou cálculo desatualizado hoje — sem abrir um
por um. Este módulo resume cada projeto numa linha comparável e agrega a
carteira; a página do painel só desenha. Também sugere os próximos passos
de um projeto a partir da mesma leitura, para a visão geral e o painel
recomendarem a mesma coisa.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from core.project_checklist import resumo_checklist
from core.project_criteria import avaliar_criterios_projeto
from core.project_dependencies import (
    STATUS_AUSENTE,
    STATUS_CICLO,
    STATUS_DESATUALIZADO,
    sincronizar_estados_dependencias,
)
from core.project_records import registro_superado
from core.project_validation import validar_projeto
from core.project_workflow import EM_VERIFICACAO, EMITIDO, SUSPENSO, situacao_atual

_ESTADOS_DEFASADOS = frozenset({STATUS_DESATUALIZADO, STATUS_AUSENTE, STATUS_CICLO})


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _data(valor: Any) -> date | None:
    texto = _texto(valor)
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        return None


def resumir_projeto(
    projeto: Mapping[str, Any],
    *,
    hoje: date | None = None,
    validacao: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Uma linha de carteira: situação, prontidão, bloqueios, prazos e atualidade."""
    referencia = hoje or date.today()
    resultado = dict(validacao) if validacao is not None else validar_projeto(projeto)
    contagens = resultado.get("contagens", {})
    checklist = resumo_checklist(projeto.get("checklist", []), hoje=referencia)
    sincronizado = sincronizar_estados_dependencias(projeto)
    registros = [
        item
        for item in sincronizado.get("registros_tecnicos", [])
        if isinstance(item, Mapping)
    ]
    vigentes = [item for item in registros if not registro_superado(item)]
    desatualizados = [
        item
        for item in vigentes
        if _texto((item.get("estado_dependencias") or {}).get("status")) in _ESTADOS_DEFASADOS
    ]
    nao_atendem = [
        item
        for item in vigentes
        if any(
            chave in _texto(item.get("status")).casefold()
            for chave in ("não atende", "nao atende", "reprovado")
        )
    ]
    atualizado = _data(projeto.get("atualizado_em"))
    dias_parado = (referencia - atualizado).days if atualizado else None
    return {
        "id": _texto(projeto.get("id")),
        "codigo": _texto(projeto.get("codigo")),
        "nome": _texto(projeto.get("nome")),
        "status": situacao_atual(projeto),
        "revisao": int(projeto.get("revisao", 0) or 0),
        "cliente": _texto(projeto.get("cliente")),
        "unidade": _texto(projeto.get("unidade_industrial")),
        "area": _texto(projeto.get("area")),
        "tag": _texto(projeto.get("tag_equipamento")),
        "responsavel": _texto(projeto.get("responsavel")),
        "prontidao": _texto(resultado.get("prontidao")),
        "indice_documental": int(resultado.get("indice_documental", 0) or 0),
        "bloqueios": int(contagens.get("Bloqueio", 0) or 0),
        "pendencias": int(contagens.get("Pendência", 0) or 0),
        "atencoes": int(contagens.get("Atenção", 0) or 0),
        "componentes": len([c for c in projeto.get("componentes", []) if isinstance(c, Mapping)]),
        "registros": len(vigentes),
        "registros_superados": len(registros) - len(vigentes),
        "registros_desatualizados": len(desatualizados),
        "registros_nao_atendem": len(nao_atendem),
        "checklist_total": checklist["total"],
        "checklist_abertos": checklist["abertos"],
        "checklist_percentual": checklist["percentual_concluido"],
        "checklist_vencidos": len(checklist["vencidos"]),
        "checklist_proximos": len(checklist["proximos"]),
        "criticos_abertos": checklist["criticos_abertos"],
        "vencidos": checklist["vencidos"],
        "proximos": checklist["proximos"],
        "atualizado_em": _texto(projeto.get("atualizado_em")),
        "dias_sem_atualizacao": dias_parado,
        "criterios_definidos": isinstance(projeto.get("criterios_projeto"), Mapping),
    }


def resumir_carteira(resumos: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Totais da carteira a partir das linhas de :func:`resumir_projeto`."""
    por_situacao: dict[str, int] = {}
    for item in resumos:
        por_situacao[item["status"]] = por_situacao.get(item["status"], 0) + 1
    return {
        "total": len(resumos),
        "por_situacao": por_situacao,
        "com_bloqueio": sum(1 for item in resumos if item["bloqueios"]),
        "prontos": sum(
            1 for item in resumos if item["prontidao"] in {"Pronto para revisão", "Pronto com ressalvas"}
        ),
        "emitidos": sum(1 for item in resumos if item["status"] == EMITIDO),
        "em_verificacao": sum(1 for item in resumos if item["status"] == EM_VERIFICACAO),
        "checklist_vencidos": sum(item["checklist_vencidos"] for item in resumos),
        "checklist_proximos": sum(item["checklist_proximos"] for item in resumos),
        "registros_desatualizados": sum(item["registros_desatualizados"] for item in resumos),
        "registros_nao_atendem": sum(item["registros_nao_atendem"] for item in resumos),
        "bloqueios": sum(item["bloqueios"] for item in resumos),
        "indice_medio": (
            round(sum(item["indice_documental"] for item in resumos) / len(resumos))
            if resumos
            else 0
        ),
    }


def vencimentos_da_carteira(
    resumos: Sequence[Mapping[str, Any]],
    *,
    incluir_proximos: bool = True,
) -> list[dict[str, Any]]:
    """Itens vencidos (e, se pedido, a vencer) de todos os projetos, por urgência."""
    linhas: list[dict[str, Any]] = []
    for resumo in resumos:
        fontes = list(resumo.get("vencidos", []))
        if incluir_proximos:
            fontes.extend(resumo.get("proximos", []))
        for item in fontes:
            linhas.append(
                {
                    "projeto_id": resumo["id"],
                    "projeto": f"{resumo['codigo']} · {resumo['nome']}",
                    **dict(item),
                }
            )
    linhas.sort(key=lambda linha: (linha["dias"] if linha["dias"] is not None else 0, not linha["critico"]))
    return linhas


def proximos_passos(
    projeto: Mapping[str, Any],
    *,
    resumo: Mapping[str, Any] | None = None,
    validacao: Mapping[str, Any] | None = None,
    limite: int = 5,
) -> list[dict[str, str]]:
    """Ordem de trabalho sugerida, da ação que mais destrava para a que menos.

    Cada passo tem ``titulo``, ``detalhe`` e ``pagina`` (destino no
    aplicativo). A lista nasce do mesmo resumo e da mesma validação que o
    painel mostra — não de uma heurística separada que pudesse discordar.
    """
    resultado = dict(validacao) if validacao is not None else validar_projeto(projeto)
    linha = dict(resumo) if resumo is not None else resumir_projeto(projeto, validacao=resultado)
    passos: list[dict[str, str]] = []
    situacao = linha["status"]

    def passo(titulo: str, detalhe: str, pagina: str) -> None:
        if len(passos) < limite:
            passos.append({"titulo": titulo, "detalhe": detalhe, "pagina": pagina})

    if situacao == SUSPENSO:
        passo(
            "Retomar ou arquivar o projeto",
            "O projeto está suspenso: nenhuma ação técnica é cobrada enquanto isso.",
            "app_pages/gestao_projetos.py",
        )
        return passos

    if linha["registros_nao_atendem"]:
        passo(
            "Tratar resultado que não atende",
            f"{linha['registros_nao_atendem']} registro(s) concluíram que a verificação não é atendida.",
            "app_pages/central_validacao.py",
        )
    if linha["registros_desatualizados"]:
        passo(
            "Refazer cálculos desatualizados",
            f"{linha['registros_desatualizados']} registro(s) usam fontes que mudaram depois do cálculo.",
            "app_pages/gestao_projetos.py",
        )
    if linha["checklist_vencidos"]:
        passo(
            "Cobrar itens vencidos do checklist",
            f"{linha['checklist_vencidos']} item(ns) com prazo vencido"
            + (f", {linha['criticos_abertos']} crítico(s) em aberto." if linha["criticos_abertos"] else "."),
            "app_pages/gestao_projetos.py",
        )
    bloqueios = [
        achado
        for achado in resultado.get("achados", [])
        if achado.get("severidade") == "Bloqueio"
    ]
    categorias = list(dict.fromkeys(achado.get("categoria", "") for achado in bloqueios))
    if bloqueios:
        passo(
            "Resolver bloqueios da validação",
            f"{len(bloqueios)} bloqueio(s) em: " + ", ".join(categorias[:4]) + ".",
            "app_pages/central_validacao.py",
        )
    if not linha["criterios_definidos"]:
        passo(
            "Definir os critérios técnicos do projeto",
            "Fator de segurança mínimo, utilização máxima e norma principal ainda usam o padrão do programa.",
            "app_pages/gestao_projetos.py",
        )
    else:
        avaliacao = avaliar_criterios_projeto(projeto.get("criterios_projeto"))
        if avaliacao["faltantes"]:
            passo(
                "Completar os critérios técnicos",
                "Faltam: " + "; ".join(avaliacao["faltantes"][:3]) + ".",
                "app_pages/gestao_projetos.py",
            )
    if not bloqueios and situacao not in {EM_VERIFICACAO, EMITIDO}:
        if linha["pendencias"]:
            passo(
                "Fechar pendências documentais",
                f"{linha['pendencias']} pendência(s) não travam a emissão, mas ficam sinalizadas no memorial.",
                "app_pages/central_validacao.py",
            )
        if _texto(projeto.get("verificador")):
            passo(
                "Enviar para verificação",
                "Sem bloqueios abertos: a situação pode avançar para Em verificação.",
                "app_pages/gestao_projetos.py",
            )
        else:
            passo(
                "Definir o verificador",
                "A passagem para verificação exige um verificador nomeado.",
                "app_pages/gestao_projetos.py",
            )
    if situacao == EM_VERIFICACAO and not bloqueios:
        passo(
            "Emitir o memorial",
            "Gere Word e PDF na Central de relatórios e mude a situação para Emitido.",
            "app_pages/central_relatorios.py",
        )
    if not passos:
        passo(
            "Manter o projeto atualizado",
            "Nenhuma ação pendente foi detectada pelas regras do programa.",
            "app_pages/gestao_projetos.py",
        )
    return passos
