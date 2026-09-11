"""Modelos de checklist por tipo de projeto.

Todo projeto novo nascia com o checklist vazio, e a lista de verificação de
uma estrutura metálica era redigitada a cada vez — ou não era feita. Os
modelos ficam em ``data/modelos_checklist.json`` (e, opcionalmente, em
``data/modelos_checklist_usuario.json``, que acrescenta ou sobrepõe modelos
pelo ``id``). Cada tipo de projeto aponta para um modelo; a página de
projetos semeia o checklist na criação e permite aplicar um modelo depois,
sem duplicar itens que já vieram dele.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_MODELOS = PASTA_DADOS / "modelos_checklist.json"
ARQUIVO_USUARIO = PASTA_DADOS / "modelos_checklist_usuario.json"
SCHEMA_MODELOS = "mecanica-toolkit/modelos-checklist/v1"

TIPO_PROJETO_PADRAO = "Projeto industrial"
PAPEIS = ("responsavel", "verificador", "aprovador")


class ModeloChecklistErro(ValueError):
    """Arquivo de modelos ausente, ilegível ou fora do formato."""


@dataclass(frozen=True, slots=True)
class ItemModelo:
    chave: str
    item: str
    categoria: str = ""
    critico: bool = False
    papel: str = ""
    prazo_dias: int | None = None


@dataclass(frozen=True, slots=True)
class ModeloChecklist:
    id: str
    nome: str
    tipo_projeto: str
    descricao: str = ""
    editavel: bool = False
    itens: tuple[ItemModelo, ...] = field(default_factory=tuple)


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _ler_arquivo(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ModeloChecklistErro(f"Não foi possível ler {caminho.name}: {erro}") from erro
    if not isinstance(dados, Mapping):
        raise ModeloChecklistErro(f"{caminho.name} precisa conter um objeto JSON.")
    return dict(dados)


def _item_de(bruto: Mapping[str, Any], *, modelo_id: str, posicao: int) -> ItemModelo:
    texto = _texto(bruto.get("item"))
    if not texto:
        raise ModeloChecklistErro(f"Modelo {modelo_id}: o item {posicao} não tem texto.")
    papel = _texto(bruto.get("papel")).casefold()
    if papel and papel not in PAPEIS:
        raise ModeloChecklistErro(
            f"Modelo {modelo_id}: papel desconhecido '{papel}' no item {posicao} "
            f"(use {', '.join(PAPEIS)} ou vazio)."
        )
    prazo = bruto.get("prazo_dias")
    prazo_dias: int | None
    if prazo in (None, ""):
        prazo_dias = None
    else:
        try:
            prazo_dias = int(prazo)
        except (TypeError, ValueError) as erro:
            raise ModeloChecklistErro(
                f"Modelo {modelo_id}: prazo_dias inválido no item {posicao}."
            ) from erro
    return ItemModelo(
        chave=_texto(bruto.get("chave")) or f"item-{posicao}",
        item=texto,
        categoria=_texto(bruto.get("categoria")),
        critico=bool(bruto.get("critico", False)),
        papel=papel,
        prazo_dias=prazo_dias,
    )


def _modelos_de(dados: Mapping[str, Any], *, editavel: bool, origem: str) -> list[ModeloChecklist]:
    if not dados:
        return []
    brutos = dados.get("modelos")
    if not isinstance(brutos, Sequence) or isinstance(brutos, (str, bytes)):
        raise ModeloChecklistErro(f"{origem}: o campo 'modelos' precisa ser uma lista.")
    modelos: list[ModeloChecklist] = []
    for posicao, bruto in enumerate(brutos, start=1):
        if not isinstance(bruto, Mapping):
            raise ModeloChecklistErro(f"{origem}: o modelo {posicao} não é um objeto.")
        modelo_id = _texto(bruto.get("id"))
        nome = _texto(bruto.get("nome"))
        if not modelo_id or not nome:
            raise ModeloChecklistErro(f"{origem}: o modelo {posicao} precisa de 'id' e 'nome'.")
        itens_brutos = bruto.get("itens")
        if not isinstance(itens_brutos, Sequence) or isinstance(itens_brutos, (str, bytes)):
            raise ModeloChecklistErro(f"{origem}: o modelo {modelo_id} precisa de uma lista 'itens'.")
        itens = tuple(
            _item_de(item, modelo_id=modelo_id, posicao=indice)
            for indice, item in enumerate(itens_brutos, start=1)
            if isinstance(item, Mapping)
        )
        chaves = [item.chave for item in itens]
        if len(chaves) != len(set(chaves)):
            raise ModeloChecklistErro(f"{origem}: o modelo {modelo_id} repete a chave de um item.")
        modelos.append(
            ModeloChecklist(
                id=modelo_id,
                nome=nome,
                tipo_projeto=_texto(bruto.get("tipo_projeto")) or TIPO_PROJETO_PADRAO,
                descricao=_texto(bruto.get("descricao")),
                editavel=editavel,
                itens=itens,
            )
        )
    return modelos


def listar_modelos(
    *,
    arquivo: Path | None = None,
    arquivo_usuario: Path | None = None,
) -> list[ModeloChecklist]:
    """Modelos distribuídos com o programa, sobrepostos pelos do usuário.

    Um modelo do usuário com o mesmo ``id`` de um modelo embutido substitui
    o embutido por inteiro — é a forma de adaptar a lista ao procedimento
    da empresa sem editar o arquivo que vem com o programa.
    """
    embutidos = _modelos_de(
        _ler_arquivo(arquivo or ARQUIVO_MODELOS), editavel=False, origem="modelos embutidos"
    )
    proprios = _modelos_de(
        _ler_arquivo(arquivo_usuario or ARQUIVO_USUARIO), editavel=True, origem="modelos do usuário"
    )
    por_id: dict[str, ModeloChecklist] = {modelo.id: modelo for modelo in embutidos}
    for modelo in proprios:
        por_id[modelo.id] = modelo
    return list(por_id.values())


def obter_modelo(modelo_id: str, **opcoes: Any) -> ModeloChecklist | None:
    alvo = _texto(modelo_id).casefold()
    for modelo in listar_modelos(**opcoes):
        if modelo.id.casefold() == alvo:
            return modelo
    return None


def tipos_de_projeto(**opcoes: Any) -> list[str]:
    """Tipos oferecidos na criação: um por modelo, o padrão sempre primeiro."""
    tipos = [TIPO_PROJETO_PADRAO]
    for modelo in listar_modelos(**opcoes):
        if modelo.tipo_projeto not in tipos:
            tipos.append(modelo.tipo_projeto)
    return tipos


def modelo_para_tipo(tipo_projeto: str, **opcoes: Any) -> ModeloChecklist | None:
    """Modelo sugerido para um tipo de projeto; o genérico quando não há um específico."""
    alvo = _texto(tipo_projeto).casefold()
    modelos = listar_modelos(**opcoes)
    for modelo in modelos:
        if modelo.tipo_projeto.casefold() == alvo:
            return modelo
    for modelo in modelos:
        if modelo.tipo_projeto.casefold() == TIPO_PROJETO_PADRAO.casefold():
            return modelo
    return None


def origem_item(modelo: ModeloChecklist, item: ItemModelo) -> str:
    return f"{modelo.id}:{item.chave}"


def instanciar_modelo(
    modelo: ModeloChecklist,
    projeto: Mapping[str, Any] | None = None,
    *,
    hoje: date | None = None,
) -> list[dict[str, Any]]:
    """Itens de checklist prontos para entrar no projeto.

    O responsável vem do papel declarado no modelo, lido do cadastro do
    projeto; se o nome ainda não foi informado, o campo fica vazio para ser
    preenchido depois — o modelo nunca inventa um nome. ``origem_modelo``
    identifica de qual modelo e de qual item a linha veio, para uma segunda
    aplicação não duplicar o que já existe.
    """
    dados = projeto or {}
    referencia = hoje or date.today()
    linhas: list[dict[str, Any]] = []
    for item in modelo.itens:
        responsavel = _texto(dados.get(item.papel)) if item.papel else ""
        prazo = (
            (referencia + timedelta(days=item.prazo_dias)).isoformat()
            if item.prazo_dias is not None
            else ""
        )
        linhas.append(
            {
                "id": str(uuid4()),
                "item": item.item,
                "categoria": item.categoria,
                "responsavel": responsavel,
                "prazo": prazo,
                "estado": "Aberto",
                "evidencia": "",
                "critico": item.critico,
                "origem_modelo": origem_item(modelo, item),
            }
        )
    return linhas


def itens_ja_aplicados(
    projeto: Mapping[str, Any], modelo: ModeloChecklist
) -> set[str]:
    """Chaves do modelo que já estão no checklist (por origem ou por texto igual)."""
    origens = {
        _texto(item.get("origem_modelo"))
        for item in projeto.get("checklist", [])
        if isinstance(item, Mapping)
    }
    textos = {
        _texto(item.get("item")).casefold()
        for item in projeto.get("checklist", [])
        if isinstance(item, Mapping)
    }
    return {
        item.chave
        for item in modelo.itens
        if origem_item(modelo, item) in origens or item.item.casefold() in textos
    }


def aplicar_modelo(
    projeto: Mapping[str, Any],
    modelo: ModeloChecklist,
    *,
    hoje: date | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Acrescenta ao checklist os itens do modelo que ainda não estão lá.

    Devolve ``(documento, adicionados, ignorados)``: o projeto com o
    checklist estendido, as linhas novas e as chaves puladas por já
    existirem. Nada é removido nem alterado — o checklist é do projeto; o
    modelo só oferece o que falta.
    """
    documento = deepcopy(dict(projeto))
    existentes = itens_ja_aplicados(documento, modelo)
    novos = [
        linha
        for item, linha in zip(modelo.itens, instanciar_modelo(modelo, documento, hoje=hoje), strict=True)
        if item.chave not in existentes
    ]
    checklist = [item for item in documento.get("checklist", []) if isinstance(item, Mapping)]
    documento["checklist"] = [*checklist, *novos]
    ignorados = [item.chave for item in modelo.itens if item.chave in existentes]
    return documento, novos, ignorados
