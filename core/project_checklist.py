"""Prazos e situação do checklist do projeto industrial.

O checklist sempre teve um campo ``prazo``, mas como texto livre: o programa
não sabia se "15/03" já tinha passado, e um item vencido só aparecia como
"aberto" — igual a um item com prazo daqui a seis meses. Este módulo lê o
prazo com tolerância (ISO, dd/mm/aaaa, dd-mm-aaaa), classifica cada item em
relação a uma data de referência e resume o que está vencido ou perto de
vencer, para a página do projeto, o painel de carteira e a validação usarem
a mesma leitura.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

ESTADOS_FECHADOS = frozenset(
    {"concluído", "concluido", "fechado", "não aplicável", "nao aplicavel"}
)
ESTADOS_CHECKLIST = ("Aberto", "Em andamento", "Concluído", "Não aplicável")

# Do mais específico para o mais solto: um texto "2026-03-15" não pode ser
# lido como "dd/mm/aaaa", e "15/03/2026" não pode ser lido como ISO.
_FORMATOS_PRAZO = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)

SITUACAO_VENCIDO = "Vencido"
SITUACAO_HOJE = "Vence hoje"
SITUACAO_PROXIMO = "Próximo do prazo"
SITUACAO_NO_PRAZO = "No prazo"
SITUACAO_SEM_PRAZO = "Sem prazo"
SITUACAO_ILEGIVEL = "Prazo ilegível"
SITUACAO_FECHADO = "Encerrado"


def item_fechado(item: Mapping[str, Any]) -> bool:
    """Concluído ou não aplicável: o prazo deixa de importar."""
    estado = str(item.get("estado") or "Aberto").strip().casefold()
    return estado in ESTADOS_FECHADOS


def interpretar_prazo(valor: Any) -> date | None:
    """Converte o prazo gravado em data, ou ``None`` quando não dá para ler.

    Aceita ``date``/``datetime``, strings ISO (com ou sem hora) e os formatos
    brasileiros usuais. Um texto como "após a parada" continua guardado no
    item — só não vira data, e a interface avisa que não conseguiu lê-lo.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        pass
    for formato in _FORMATOS_PRAZO:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def formatar_prazo(valor: Any) -> str:
    """Prazo em dd/mm/aaaa para tabelas; texto original quando ilegível."""
    prazo = interpretar_prazo(valor)
    if prazo is not None:
        return prazo.strftime("%d/%m/%Y")
    return str(valor or "").strip()


def situacao_prazo(
    item: Mapping[str, Any],
    *,
    hoje: date | None = None,
    janela_dias: int = 7,
) -> dict[str, Any]:
    """Classifica um item do checklist em relação ao prazo.

    Devolve ``prazo`` (data ou ``None``), ``dias`` (negativo quando já passou)
    e ``situacao`` com um dos rótulos ``SITUACAO_*``. Itens encerrados nunca
    aparecem como vencidos, mesmo com prazo antigo: o prazo era para
    concluir, e concluir foi o que aconteceu.
    """
    referencia = hoje or date.today()
    bruto = item.get("prazo")
    prazo = interpretar_prazo(bruto)
    if item_fechado(item):
        return {"prazo": prazo, "dias": None, "situacao": SITUACAO_FECHADO}
    if prazo is None:
        texto = str(bruto or "").strip()
        return {
            "prazo": None,
            "dias": None,
            "situacao": SITUACAO_ILEGIVEL if texto else SITUACAO_SEM_PRAZO,
        }
    dias = (prazo - referencia).days
    if dias < 0:
        situacao = SITUACAO_VENCIDO
    elif dias == 0:
        situacao = SITUACAO_HOJE
    elif dias <= janela_dias:
        situacao = SITUACAO_PROXIMO
    else:
        situacao = SITUACAO_NO_PRAZO
    return {"prazo": prazo, "dias": dias, "situacao": situacao}


def _rotulo_item(item: Mapping[str, Any], indice: int) -> str:
    return str(item.get("item") or "").strip() or f"Item {indice}"


def resumo_checklist(
    checklist: Sequence[Mapping[str, Any]],
    *,
    hoje: date | None = None,
    janela_dias: int = 7,
) -> dict[str, Any]:
    """Números e listas que a página do projeto e o painel mostram.

    ``vencidos`` e ``proximos`` vêm ordenados do mais urgente para o menos,
    cada um com item, responsável, prazo, dias e criticidade — o suficiente
    para uma tabela de cobrança sem reler o checklist inteiro.
    """
    itens = [item for item in checklist if isinstance(item, Mapping)]
    abertos: list[dict[str, Any]] = []
    vencidos: list[dict[str, Any]] = []
    proximos: list[dict[str, Any]] = []
    ilegiveis: list[dict[str, Any]] = []
    concluidos = 0
    criticos_abertos = 0
    for indice, item in enumerate(itens, start=1):
        avaliacao = situacao_prazo(item, hoje=hoje, janela_dias=janela_dias)
        if avaliacao["situacao"] == SITUACAO_FECHADO:
            concluidos += 1
            continue
        linha = {
            "id": str(item.get("id") or ""),
            "item": _rotulo_item(item, indice),
            "responsavel": str(item.get("responsavel") or "").strip(),
            "estado": str(item.get("estado") or "Aberto").strip() or "Aberto",
            "critico": bool(item.get("critico", False)),
            "prazo": avaliacao["prazo"],
            "prazo_texto": formatar_prazo(item.get("prazo")),
            "dias": avaliacao["dias"],
            "situacao": avaliacao["situacao"],
        }
        abertos.append(linha)
        if linha["critico"]:
            criticos_abertos += 1
        if avaliacao["situacao"] == SITUACAO_VENCIDO:
            vencidos.append(linha)
        elif avaliacao["situacao"] in {SITUACAO_HOJE, SITUACAO_PROXIMO}:
            proximos.append(linha)
        elif avaliacao["situacao"] == SITUACAO_ILEGIVEL:
            ilegiveis.append(linha)
    def urgencia(linha: Mapping[str, Any]) -> tuple[int, bool]:
        # Mais atrasado primeiro; entre iguais, o crítico vem antes.
        return (linha["dias"] if linha["dias"] is not None else 0, not linha["critico"])

    vencidos.sort(key=urgencia)
    proximos.sort(key=urgencia)
    total = len(itens)
    return {
        "total": total,
        "abertos": len(abertos),
        "concluidos": concluidos,
        "criticos_abertos": criticos_abertos,
        "percentual_concluido": round(100 * concluidos / total) if total else 0,
        "vencidos": vencidos,
        "proximos": proximos,
        "ilegiveis": ilegiveis,
        "itens_abertos": abertos,
    }
