"""Grafo de dependências e detecção de cálculos desatualizados."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

from core.project_criteria import calcular_hash_criterios
from core.technical_records import calcular_hash_registro, normalizar_registro_tecnico


STATUS_ATUAL = "Atual"
STATUS_DESATUALIZADO = "Desatualizado"
STATUS_AUSENTE = "Referência ausente"
STATUS_CICLO = "Ciclo de dependências"
STATUS_SEM_DEPENDENCIAS = "Sem dependências declaradas"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(valor: Any) -> str:
    serializado = json.dumps(
        valor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _texto(valor: Any, padrao: str = "") -> str:
    texto = str(valor or "").strip()
    return texto or padrao


def _fonte(
    chave: str,
    tipo: str,
    origem_id: str,
    rotulo: str,
    hash_origem: str,
) -> dict[str, str]:
    return {
        "chave": chave,
        "tipo": tipo,
        "origem_id": origem_id,
        "rotulo": rotulo,
        "hash_origem": hash_origem,
    }


def catalogar_fontes_projeto(projeto: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Expõe todas as fontes que podem alimentar um registro técnico."""
    fontes: dict[str, dict[str, str]] = {}
    criterios = projeto.get("criterios_projeto")
    fontes["criterios_projeto"] = _fonte(
        "criterios_projeto",
        "criterios",
        "criterios_projeto",
        "Critérios gerais do projeto",
        calcular_hash_criterios(criterios if isinstance(criterios, Mapping) else None),
    )

    colecoes = (
        ("casos_carga", "casos_carga", "Casos de carga"),
        ("combinacoes_carga", "combinacoes_carga", "Combinações de carga"),
        ("componentes", "componentes", "Escopo físico"),
        ("materiais_projeto", "materiais", "Materiais do projeto"),
    )
    for campo, chave, rotulo in colecoes:
        itens = [item for item in projeto.get(campo, []) if isinstance(item, Mapping)]
        fontes[chave] = _fonte(chave, "colecao", chave, rotulo, _hash(itens))

    especificacoes = (
        ("casos_carga", "caso_carga", "Caso de carga", ("codigo", "nome")),
        ("combinacoes_carga", "combinacao_carga", "Combinação", ("nome",)),
        ("componentes", "componente", "Componente", ("tag", "descricao")),
        ("materiais_projeto", "material", "Material", ("nome", "condicao")),
    )
    for campo, tipo, prefixo, nomes in especificacoes:
        for item in projeto.get(campo, []):
            if not isinstance(item, Mapping):
                continue
            origem_id = _texto(item.get("id"))
            if not origem_id:
                continue
            nome = next((_texto(item.get(campo_nome)) for campo_nome in nomes if _texto(item.get(campo_nome))), origem_id)
            chave = f"{tipo}:{origem_id}"
            fontes[chave] = _fonte(chave, tipo, origem_id, f"{prefixo}: {nome}", _hash(item))

    for registro in projeto.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping):
            continue
        origem_id = _texto(registro.get("id"))
        if not origem_id:
            continue
        chave = f"registro:{origem_id}"
        rotulo = f"{_texto(registro.get('modulo'), 'Módulo')} · {_texto(registro.get('titulo'), origem_id)}"
        fontes[chave] = _fonte(
            chave,
            "registro",
            origem_id,
            rotulo,
            calcular_hash_registro(registro),
        )
    return fontes


def _lista_ids(valor: Any) -> list[str]:
    if isinstance(valor, Sequence) and not isinstance(valor, (str, bytes)):
        return [_texto(item) for item in valor if _texto(item)]
    return [_texto(valor)] if _texto(valor) else []


def inferir_chaves_dependencia(registro: Mapping[str, Any]) -> list[str]:
    """Infere vínculos técnicos explícitos do contrato do registro."""
    chaves = ["criterios_projeto"]
    modulo_id = _texto(registro.get("modulo_id")).casefold()
    if modulo_id == "casos_carga":
        chaves.extend(("casos_carga", "combinacoes_carga"))
    chaves.extend(f"caso_carga:{item}" for item in _lista_ids(registro.get("casos_carga_ids")))
    chaves.extend(f"componente:{item}" for item in _lista_ids(registro.get("componentes_ids")))
    chaves.extend(f"material:{item}" for item in _lista_ids(registro.get("materiais_ids")))
    chaves.extend(f"registro:{item}" for item in _lista_ids(registro.get("dependencias_ids")))
    entradas = registro.get("entradas")
    if isinstance(entradas, Mapping):
        origem = _texto(entradas.get("registro_origem"))
        if origem:
            chaves.append(f"registro:{origem}")
    for dependencia in registro.get("dependencias", []):
        if isinstance(dependencia, Mapping) and _texto(dependencia.get("chave")):
            chaves.append(_texto(dependencia.get("chave")))
    return list(dict.fromkeys(chaves))


def preparar_registro_dependencias(
    projeto: Mapping[str, Any],
    registro: Mapping[str, Any],
    *,
    dependencias_chaves: Iterable[str] = (),
) -> dict[str, Any]:
    """Fotografa as fontes usadas por um novo cálculo."""
    item = deepcopy(dict(registro))
    fontes = catalogar_fontes_projeto(projeto)
    chaves = list(
        dict.fromkeys(
            [*inferir_chaves_dependencia(item), *(_texto(chave) for chave in dependencias_chaves)]
        )
    )
    dependencias = []
    for chave in chaves:
        fonte = fontes.get(chave)
        if fonte:
            dependencias.append(deepcopy(fonte))
        else:
            tipo, _, origem_id = chave.partition(":")
            dependencias.append(
                _fonte(chave, tipo or "fonte", origem_id or chave, chave, "")
            )
    item["dependencias"] = dependencias
    item["dependencias_ids"] = [
        dependencia["origem_id"]
        for dependencia in dependencias
        if dependencia["tipo"] == "registro"
    ]
    item["estado_dependencias"] = {
        "status": STATUS_ATUAL if dependencias else STATUS_SEM_DEPENDENCIAS,
        "motivos": [],
        "avaliado_em": _agora(),
    }
    item.pop("hash_calculo", None)
    return normalizar_registro_tecnico(item)


def _ciclos_registros(registros: Sequence[Mapping[str, Any]]) -> set[str]:
    ids = {_texto(item.get("id")) for item in registros if _texto(item.get("id"))}
    arestas: dict[str, list[str]] = {item_id: [] for item_id in ids}
    for registro in registros:
        destino = _texto(registro.get("id"))
        if destino not in arestas:
            continue
        for dependencia in registro.get("dependencias", []):
            if not isinstance(dependencia, Mapping) or dependencia.get("tipo") != "registro":
                continue
            origem = _texto(dependencia.get("origem_id"))
            if origem in ids:
                arestas[destino].append(origem)

    visitando: set[str] = set()
    visitados: set[str] = set()
    pilha: list[str] = []
    ciclos: set[str] = set()

    def visitar(no: str) -> None:
        if no in visitando:
            if no in pilha:
                ciclos.update(pilha[pilha.index(no) :])
            return
        if no in visitados:
            return
        visitando.add(no)
        pilha.append(no)
        for origem in arestas.get(no, []):
            visitar(origem)
        pilha.pop()
        visitando.remove(no)
        visitados.add(no)

    for item_id in ids:
        visitar(item_id)
    return ciclos


def sincronizar_estados_dependencias(projeto: Mapping[str, Any]) -> dict[str, Any]:
    """Reavalia o grafo sem alterar as fotografias que originaram os cálculos."""
    documento = deepcopy(dict(projeto))
    registros = [
        item for item in documento.get("registros_tecnicos", []) if isinstance(item, Mapping)
    ]
    fontes = catalogar_fontes_projeto(documento)
    ciclos = _ciclos_registros(registros)
    estados: dict[str, dict[str, Any]] = {}

    for registro in registros:
        registro_id = _texto(registro.get("id"))
        dependencias = [
            item for item in registro.get("dependencias", []) if isinstance(item, Mapping)
        ]
        motivos: list[str] = []
        status = STATUS_ATUAL
        if registro_id in ciclos:
            status = STATUS_CICLO
            motivos.append("O registro participa de um ciclo e não possui uma ordem de atualização válida.")
        elif not dependencias:
            status = STATUS_SEM_DEPENDENCIAS
        else:
            ausentes = []
            divergentes = []
            for dependencia in dependencias:
                chave = _texto(dependencia.get("chave"))
                fonte_atual = fontes.get(chave)
                if fonte_atual is None:
                    ausentes.append(_texto(dependencia.get("rotulo"), chave))
                elif _texto(dependencia.get("hash_origem")) != fonte_atual["hash_origem"]:
                    divergentes.append(_texto(dependencia.get("rotulo"), chave))
            if ausentes:
                status = STATUS_AUSENTE
                motivos.append("Fontes removidas: " + "; ".join(ausentes) + ".")
            if divergentes:
                status = STATUS_DESATUALIZADO
                motivos.append("Fontes alteradas: " + "; ".join(divergentes) + ".")
        estados[registro_id] = {"status": status, "motivos": motivos}

    # Propaga a defasagem: um resultado baseado em outro cálculo defasado também
    # fica defasado, mesmo que o hash técnico do resultado de origem não tenha mudado.
    alterou = True
    while alterou:
        alterou = False
        for registro in registros:
            registro_id = _texto(registro.get("id"))
            estado = estados.get(registro_id, {})
            if estado.get("status") in {STATUS_CICLO, STATUS_AUSENTE}:
                continue
            for dependencia in registro.get("dependencias", []):
                if not isinstance(dependencia, Mapping) or dependencia.get("tipo") != "registro":
                    continue
                origem_id = _texto(dependencia.get("origem_id"))
                origem_estado = estados.get(origem_id, {}).get("status")
                if origem_estado in {STATUS_DESATUALIZADO, STATUS_AUSENTE, STATUS_CICLO}:
                    if estado.get("status") != STATUS_DESATUALIZADO:
                        estado["status"] = STATUS_DESATUALIZADO
                        alterou = True
                    motivo = (
                        f"O cálculo de origem {_texto(dependencia.get('rotulo'), origem_id)} "
                        f"está em estado '{origem_estado}'."
                    )
                    if motivo not in estado.setdefault("motivos", []):
                        estado["motivos"].append(motivo)

    contagens: dict[str, int] = {}
    atualizados = []
    instante = _agora()
    for registro in registros:
        item = deepcopy(dict(registro))
        estado = estados.get(_texto(item.get("id")), {"status": STATUS_SEM_DEPENDENCIAS, "motivos": []})
        anterior = item.get("estado_dependencias", {}) if isinstance(item.get("estado_dependencias"), Mapping) else {}
        mudou = anterior.get("status") != estado["status"] or list(anterior.get("motivos", [])) != estado["motivos"]
        item["estado_dependencias"] = {
            "status": estado["status"],
            "motivos": estado["motivos"],
            "avaliado_em": instante if mudou else _texto(anterior.get("avaliado_em"), instante),
        }
        contagens[estado["status"]] = contagens.get(estado["status"], 0) + 1
        atualizados.append(item)
    documento["registros_tecnicos"] = atualizados
    documento["resumo_dependencias"] = {
        "total_registros": len(atualizados),
        "atuais": contagens.get(STATUS_ATUAL, 0),
        "desatualizados": contagens.get(STATUS_DESATUALIZADO, 0),
        "referencias_ausentes": contagens.get(STATUS_AUSENTE, 0),
        "ciclos": contagens.get(STATUS_CICLO, 0),
        "sem_dependencias": contagens.get(STATUS_SEM_DEPENDENCIAS, 0),
        "avaliado_em": instante,
    }
    return documento


def adicionar_dependencia(
    projeto: Mapping[str, Any],
    registro_destino_id: str,
    fonte_chave: str,
) -> dict[str, Any]:
    documento = deepcopy(dict(projeto))
    fontes = catalogar_fontes_projeto(documento)
    fonte = fontes.get(_texto(fonte_chave))
    if fonte is None:
        raise ValueError("A fonte selecionada não existe no projeto.")
    if fonte["chave"] == f"registro:{registro_destino_id}":
        raise ValueError("Um registro não pode depender de si próprio.")
    encontrado = False
    for indice, registro in enumerate(documento.get("registros_tecnicos", [])):
        if not isinstance(registro, Mapping) or _texto(registro.get("id")) != _texto(registro_destino_id):
            continue
        encontrado = True
        item = deepcopy(dict(registro))
        dependencias = [
            deepcopy(dict(dep))
            for dep in item.get("dependencias", [])
            if isinstance(dep, Mapping) and _texto(dep.get("chave")) != fonte["chave"]
        ]
        dependencias.append(deepcopy(fonte))
        item["dependencias"] = dependencias
        item["dependencias_ids"] = [
            dep["origem_id"] for dep in dependencias if dep.get("tipo") == "registro"
        ]
        item.pop("hash_calculo", None)
        documento["registros_tecnicos"][indice] = normalizar_registro_tecnico(item)
        break
    if not encontrado:
        raise ValueError("Registro de destino não encontrado.")
    return sincronizar_estados_dependencias(documento)


def remover_dependencia(
    projeto: Mapping[str, Any],
    registro_destino_id: str,
    fonte_chave: str,
) -> dict[str, Any]:
    documento = deepcopy(dict(projeto))
    for indice, registro in enumerate(documento.get("registros_tecnicos", [])):
        if not isinstance(registro, Mapping) or _texto(registro.get("id")) != _texto(registro_destino_id):
            continue
        item = deepcopy(dict(registro))
        item["dependencias"] = [
            deepcopy(dict(dep))
            for dep in item.get("dependencias", [])
            if isinstance(dep, Mapping) and _texto(dep.get("chave")) != _texto(fonte_chave)
        ]
        item["dependencias_ids"] = [
            dep["origem_id"] for dep in item["dependencias"] if dep.get("tipo") == "registro"
        ]
        item.pop("hash_calculo", None)
        documento["registros_tecnicos"][indice] = normalizar_registro_tecnico(item)
        return sincronizar_estados_dependencias(documento)
    raise ValueError("Registro de destino não encontrado.")


def linhas_grafo_dependencias(projeto: Mapping[str, Any]) -> list[dict[str, str]]:
    linhas: list[dict[str, str]] = []
    for registro in projeto.get("registros_tecnicos", []):
        if not isinstance(registro, Mapping):
            continue
        destino = f"{_texto(registro.get('modulo'), 'Módulo')} · {_texto(registro.get('titulo'), 'Registro')}"
        estado = registro.get("estado_dependencias", {}) if isinstance(registro.get("estado_dependencias"), Mapping) else {}
        for dependencia in registro.get("dependencias", []):
            if not isinstance(dependencia, Mapping):
                continue
            linhas.append(
                {
                    "origem_chave": _texto(dependencia.get("chave")),
                    "Origem": _texto(dependencia.get("rotulo"), dependencia.get("chave")),
                    "Destino ID": _texto(registro.get("id")),
                    "Destino": destino,
                    "Tipo": _texto(dependencia.get("tipo")),
                    "Estado do destino": _texto(estado.get("status"), STATUS_SEM_DEPENDENCIAS),
                }
            )
    return linhas
