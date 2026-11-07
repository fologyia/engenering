"""Conjuntos do montador: vários blocos num bloco só, com entradas e saídas públicas.

Um conjunto guarda um pedaço do desenho dentro de si, e o motor abre ele na hora de calcular. Aqui
ficam as operações sobre o desenho (agrupar, desfazer, escolher as portas públicas) e a biblioteca de
conjuntos salvos, que o usuário reaproveita em outras montagens. O desenho entra e sai como dicionário
simples, o mesmo que a prancheta usa.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import espelho_remoto
from core import montador_blocos as mb
from core.montador import CONJUNTO
from core.section_catalog import PASTA_DADOS

ARQUIVO_USUARIO = PASTA_DADOS / "conjuntos_usuario.json"
GRUPO_CONJUNTOS = "Meus conjuntos"
_FORMATO = "mecanica-toolkit/conjuntos/v1"
_NAO_FICA_SOLTA = (mb.SECAO, mb.LINHA)  # sem isto o conjunto nem calcula
_LARGURA_DO_CARTAO = 176  # a mesma da prancheta
_ALTURA_DO_CARTAO = 120


class ErroDeConjunto(ValueError):
    """O que impede a operação, em palavras de quem está montando."""


def nivel(dados: dict[str, Any], caminho: Sequence[str]) -> dict[str, Any]:
    """O desenho dentro do conjunto aberto: ``caminho`` tem os ids, de fora para dentro."""
    atual = dados
    for id_ in caminho:
        no = next((n for n in atual.get("nos", []) if n.get("id") == id_), None)
        if no is None or no.get("tipo") != CONJUNTO:
            raise ErroDeConjunto("Esse conjunto não existe mais.")
        atual = no["grafo"]
    return atual


def portas_do_no(no: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Entradas e saídas de um bloco, simples ou conjunto, no formato da prancheta."""
    if no.get("tipo") == CONJUNTO:
        portas = no.get("portas") or {}
        return list(portas.get("entradas") or ()), list(portas.get("saidas") or ())
    bloco = mb.POR_CHAVE.get(str(no.get("tipo")))
    if bloco is None:
        return [], []
    na_tela = mb.portas_para_a_tela(bloco.chave, no.get("opcoes") or {})
    entradas, saidas = na_tela["entradas"], na_tela["saidas"]
    if bloco.chave == mb.REFERENCIA:
        dimensao = (no.get("opcoes") or {}).get("dimensao")
        saidas = [{**p, "dimensao": dimensao} for p in saidas]
    return entradas, saidas


def _porta_publica(chave: str, porta: Mapping[str, Any], no: str) -> dict[str, Any]:
    return {
        "chave": chave,
        "rotulo": porta["rotulo"],
        "tipo": porta["tipo"],
        "dimensao": porta.get("dimensao"),
        "varias": bool(porta.get("varias")),
        "no": no,
        "porta": porta["chave"],
    }


def _liga(saida: Mapping[str, Any], entrada: Mapping[str, Any]) -> bool:
    return saida["tipo"] == entrada["tipo"] and saida.get("dimensao") == entrada.get("dimensao")


def _mesmo_fio(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return all(a.get(k) == b.get(k) for k in ("de", "saida", "para", "entrada"))


def _pontas_do_fio(
    atual: Mapping[str, Any], fio: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Os dois blocos e as duas portas de uma ligação."""
    por_id = {n.get("id"): n for n in atual["nos"]}
    de, para = por_id.get(fio.get("de")), por_id.get(fio.get("para"))
    if de is None or para is None:
        raise ErroDeConjunto("Essa ligação não existe mais.")
    saida = next((p for p in portas_do_no(de)[1] if p["chave"] == fio.get("saida")), None)
    entrada = next((p for p in portas_do_no(para)[0] if p["chave"] == fio.get("entrada")), None)
    if saida is None or entrada is None:
        raise ErroDeConjunto("Essa ligação não existe mais.")
    return de, para, saida, entrada


def _tem_laco(atual: Mapping[str, Any]) -> bool:
    vizinhos: dict[str, list[str]] = {}
    for fio in atual["fios"]:
        vizinhos.setdefault(fio["de"], []).append(fio["para"])

    def volta(inicio: str) -> bool:
        vistos: set[str] = set()
        pilha = list(vizinhos.get(inicio, ()))
        while pilha:
            id_ = pilha.pop()
            if id_ == inicio:
                return True
            if id_ not in vistos:
                vistos.add(id_)
                pilha.extend(vizinhos.get(id_, ()))
        return False

    return any(volta(id_) for id_ in vizinhos)


def fio_existe(dados: dict[str, Any], fio: Mapping[str, Any], caminho: Sequence[str] = ()) -> bool:
    """A seleção chega depois do desenho: por um instante ela pode apontar para um fio apagado."""
    try:
        atual = nivel(dados, caminho)
    except ErroDeConjunto:
        return False
    return any(_mesmo_fio(f, fio) for f in atual["fios"])


def tirar_fios_soltos(dados: Mapping[str, Any], caminho: Sequence[str] = ()) -> dict[str, Any]:
    """Tira os fios cuja bolinha sumiu: mudar a fórmula pode tirar uma letra."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    portas = {str(n.get("id")): portas_do_no(n) for n in atual["nos"]}

    def vale(fio: Mapping[str, Any]) -> bool:
        de, para = portas.get(str(fio.get("de"))), portas.get(str(fio.get("para")))
        if de is None or para is None:
            return False
        return any(p["chave"] == fio.get("saida") for p in de[1]) and any(
            p["chave"] == fio.get("entrada") for p in para[0]
        )

    atual["fios"] = [f for f in atual["fios"] if vale(f)]
    return novo


def conferir_fio(
    dados: dict[str, Any], fio: Mapping[str, Any], caminho: Sequence[str] = ()
) -> list[tuple[str, bool]]:
    """O que o inspetor mostra de uma ligação: tudo medido aqui, nada de texto fixo."""
    atual = nivel(dados, caminho)
    _, _, saida, entrada = _pontas_do_fio(atual, fio)
    return [
        ("Mesmo tipo nas duas pontas", saida["tipo"] == entrada["tipo"]),
        ("Mesma grandeza nas duas pontas", saida.get("dimensao") == entrada.get("dimensao")),
        ("Sem laço na montagem", not _tem_laco(atual)),
    ]


def compativeis(
    dados: dict[str, Any], fio: Mapping[str, Any], dominio: str, caminho: Sequence[str] = ()
) -> list[str]:
    """Os blocos que cabem no meio de uma ligação: recebem e devolvem o que passa nela."""
    _, _, saida, entrada = _pontas_do_fio(nivel(dados, caminho), fio)
    boas = []
    for bloco in mb.POR_CHAVE.values():
        if bloco.dominio not in (dominio, mb.COMUM):
            continue
        entradas, saidas = portas_do_no({"tipo": bloco.chave})
        if any(_liga(saida, p) for p in entradas) and any(_liga(p, entrada) for p in saidas):
            boas.append(bloco.chave)
    return boas


def inserir_no_fio(
    dados: Mapping[str, Any], fio: Mapping[str, Any], chave: str, caminho: Sequence[str] = ()
) -> tuple[dict[str, Any], str]:
    """A ligação vira origem → novo → destino: um bloco e dois fios, e o resto não anda."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    de, para, saida, entrada = _pontas_do_fio(atual, fio)
    entradas, saidas = portas_do_no({"tipo": chave})
    recebe = next((p for p in entradas if _liga(saida, p)), None)
    devolve = next((p for p in saidas if _liga(p, entrada)), None)
    if recebe is None or devolve is None:
        raise ErroDeConjunto("Esse bloco não cabe nesta ligação.")
    id_ = _id_novo(atual["nos"], "n")
    x = round((float(de.get("x", 0)) + float(para.get("x", 0))) / 2.0)
    y = round((float(de.get("y", 0)) + float(para.get("y", 0))) / 2.0)
    while any(
        abs(float(n.get("x", 0)) - x) < _LARGURA_DO_CARTAO
        and abs(float(n.get("y", 0)) - y) < _ALTURA_DO_CARTAO
        for n in atual["nos"]
    ):
        y += _ALTURA_DO_CARTAO
    atual["nos"].append({"id": id_, "tipo": chave, "x": x, "y": y, "opcoes": {}})
    atual["fios"] = [f for f in atual["fios"] if not _mesmo_fio(f, fio)]
    atual["fios"].append(
        {"de": fio["de"], "saida": fio["saida"], "para": id_, "entrada": recebe["chave"]}
    )
    atual["fios"].append(
        {"de": id_, "saida": devolve["chave"], "para": fio["para"], "entrada": fio["entrada"]}
    )
    return novo, id_


def tirar_fio(
    dados: Mapping[str, Any], fio: Mapping[str, Any], caminho: Sequence[str] = ()
) -> dict[str, Any]:
    """Apaga uma ligação. Os blocos ficam onde estão."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    atual["fios"] = [f for f in atual["fios"] if not _mesmo_fio(f, fio)]
    return novo


def _id_novo(nos: Iterable[Mapping[str, Any]], prefixo: str = "c") -> str:
    usados = {str(n.get("id")) for n in nos}
    k = 1
    while f"{prefixo}{k}" in usados:
        k += 1
    return f"{prefixo}{k}"


def _portas_soltas(
    internos: Sequence[Mapping[str, Any]],
    fios: Sequence[Mapping[str, Any]],
    ja_entradas: set[tuple[str, str]],
    ja_saidas: set[tuple[str, str]],
) -> tuple[list[tuple[str, dict[str, Any]]], list[tuple[str, dict[str, Any]]]]:
    """O que fica sem fio dentro do conjunto e precisa aparecer do lado de fora."""
    entradas, saidas = [], []
    for no in internos:
        id_ = str(no["id"])
        de_entrada, de_saida = portas_do_no(no)
        for porta in de_entrada:
            chave = (id_, porta["chave"])
            ligada = any(f["para"] == id_ and f["entrada"] == porta["chave"] for f in fios)
            if not ligada and chave not in ja_entradas and porta["tipo"] in _NAO_FICA_SOLTA:
                entradas.append((id_, porta))
        for porta in de_saida:
            chave = (id_, porta["chave"])
            ligada = any(f["de"] == id_ and f["saida"] == porta["chave"] for f in fios)
            if not ligada and chave not in ja_saidas:
                saidas.append((id_, porta))
    return entradas, saidas


def agrupar(
    dados: Mapping[str, Any],
    ids: Sequence[str],
    nome: str = "",
    caminho: Sequence[str] = (),
) -> dict[str, Any]:
    """Troca os blocos ``ids`` por um conjunto. Os fios que cruzam a borda viram portas públicas."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    selecionados = set(ids)
    internos = [n for n in atual["nos"] if n["id"] in selecionados]
    if len(internos) < 2:
        raise ErroDeConjunto("Selecione ao menos dois blocos para agrupar.")
    if any(n["tipo"] == mb.RESULTADO for n in internos):
        raise ErroDeConjunto("O bloco Em função de fica fora do conjunto: é ele quem responde.")
    id_conjunto = _id_novo(atual["nos"])
    fios_internos = [
        f for f in atual["fios"] if f["de"] in selecionados and f["para"] in selecionados
    ]
    por_id = {n["id"]: n for n in internos}
    entradas: list[dict[str, Any]] = []
    saidas: list[dict[str, Any]] = []
    chaves_de_entrada: dict[tuple[str, str], str] = {}
    chaves_de_saida: dict[tuple[str, str], str] = {}
    fios_fora: list[dict[str, Any]] = []
    for fio in atual["fios"]:
        entra = fio["para"] in selecionados
        sai = fio["de"] in selecionados
        if entra and sai:
            continue
        if entra:
            alvo = (fio["para"], fio["entrada"])
            if alvo not in chaves_de_entrada:
                chave = f"e{len(entradas) + 1}"
                chaves_de_entrada[alvo] = chave
                porta = next(
                    p for p in portas_do_no(por_id[fio["para"]])[0] if p["chave"] == fio["entrada"]
                )
                entradas.append(_porta_publica(chave, porta, fio["para"]))
            fios_fora.append({**fio, "para": id_conjunto, "entrada": chaves_de_entrada[alvo]})
        elif sai:
            alvo = (fio["de"], fio["saida"])
            if alvo not in chaves_de_saida:
                chave = f"s{len(saidas) + 1}"
                chaves_de_saida[alvo] = chave
                porta = next(
                    p for p in portas_do_no(por_id[fio["de"]])[1] if p["chave"] == fio["saida"]
                )
                saidas.append(_porta_publica(chave, porta, fio["de"]))
            fios_fora.append({**fio, "de": id_conjunto, "saida": chaves_de_saida[alvo]})
        else:
            fios_fora.append(fio)
    soltas_e, soltas_s = _portas_soltas(
        internos, fios_internos, set(chaves_de_entrada), set(chaves_de_saida)
    )
    for id_, porta in soltas_e:
        entradas.append(_porta_publica(f"e{len(entradas) + 1}", porta, id_))
    for id_, porta in soltas_s:
        saidas.append(_porta_publica(f"s{len(saidas) + 1}", porta, id_))
    # No lugar do primeiro bloco: x e y mínimos separados podem cair em cima de outro bloco.
    primeiro = min(internos, key=lambda n: (float(n.get("y", 0)), float(n.get("x", 0))))
    x, y = float(primeiro.get("x", 0)), float(primeiro.get("y", 0))
    conjunto = {
        "id": id_conjunto,
        "tipo": CONJUNTO,
        "nome": nome.strip() or f"Conjunto {id_conjunto[1:]}",
        "x": x,
        "y": y,
        "opcoes": {},
        "grafo": {"nos": internos, "fios": fios_internos},
        "portas": {"entradas": entradas, "saidas": saidas},
    }
    atual["nos"] = [n for n in atual["nos"] if n["id"] not in selecionados] + [conjunto]
    atual["fios"] = fios_fora
    return novo


def desagrupar(
    dados: Mapping[str, Any], id_conjunto: str, caminho: Sequence[str] = ()
) -> dict[str, Any]:
    """Põe os blocos de volta no desenho e religa os fios da borda."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    conjunto = next((n for n in atual["nos"] if n["id"] == id_conjunto), None)
    if conjunto is None or conjunto.get("tipo") != CONJUNTO:
        raise ErroDeConjunto("Esse conjunto não existe mais.")
    ocupados = {str(n["id"]) for n in atual["nos"]}
    troca: dict[str, str] = {}
    internos = []
    for no in conjunto["grafo"]["nos"]:
        id_ = str(no["id"])
        if id_ in ocupados:
            k = 1
            while f"{id_}_{k}" in ocupados:
                k += 1
            id_novo = f"{id_}_{k}"
        else:
            id_novo = id_
        ocupados.add(id_novo)
        troca[id_] = id_novo
        internos.append({**no, "id": id_novo})
    entradas = {p["chave"]: p for p in conjunto["portas"]["entradas"]}
    saidas = {p["chave"]: p for p in conjunto["portas"]["saidas"]}
    fios = [
        {
            **f,
            "de": troca[f["de"]],
            "para": troca[f["para"]],
        }
        for f in conjunto["grafo"]["fios"]
    ]
    for fio in atual["fios"]:
        item = dict(fio)
        if fio["para"] == id_conjunto:
            porta = entradas.get(fio["entrada"])
            if porta is None:
                continue
            item.update({"para": troca[porta["no"]], "entrada": porta["porta"]})
        if fio["de"] == id_conjunto:
            porta = saidas.get(fio["saida"])
            if porta is None:
                continue
            item.update({"de": troca[porta["no"]], "saida": porta["porta"]})
        fios.append(item)
    atual["nos"] = [n for n in atual["nos"] if n["id"] != id_conjunto] + internos
    atual["fios"] = fios
    return novo


def candidatas(conjunto: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Todas as portas de dentro que podem virar públicas: as que não têm fio lá dentro."""
    interno = conjunto["grafo"]
    entradas, saidas = [], []
    for no in interno["nos"]:
        id_ = str(no["id"])
        de_entrada, de_saida = portas_do_no(no)
        for porta in de_entrada:
            if not any(
                f["para"] == id_ and f["entrada"] == porta["chave"] for f in interno["fios"]
            ):
                entradas.append({"no": id_, "porta": porta["chave"], "rotulo": porta["rotulo"]})
        for porta in de_saida:
            saidas.append({"no": id_, "porta": porta["chave"], "rotulo": porta["rotulo"]})
    return entradas, saidas


def definir_portas(
    dados: Mapping[str, Any],
    id_conjunto: str,
    entradas: Sequence[tuple[str, str]],
    saidas: Sequence[tuple[str, str]],
    caminho: Sequence[str] = (),
) -> dict[str, Any]:
    """Escolhe as portas públicas. Fio ligado numa porta que saiu é retirado."""
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    conjunto = next(n for n in atual["nos"] if n["id"] == id_conjunto)
    por_id = {str(n["id"]): n for n in conjunto["grafo"]["nos"]}

    def publicas(
        pedidas: Sequence[tuple[str, str]],
        antigas: Sequence[Mapping[str, Any]],
        lado: int,
        letra: str,
    ) -> list[dict[str, Any]]:
        conhecidas = {(p["no"], p["porta"]): p for p in antigas}
        lista = []
        for no, porta in pedidas:
            if (no, porta) in conhecidas:
                lista.append(dict(conhecidas[(no, porta)]))
                continue
            usados = {p["chave"] for p in antigas} | {p["chave"] for p in lista}
            k = 1
            while f"{letra}{k}" in usados:
                k += 1
            original = next(
                (p for p in portas_do_no(por_id[no])[lado] if p["chave"] == porta), None
            )
            if original is not None:
                lista.append(_porta_publica(f"{letra}{k}", original, no))
        return lista

    portas = conjunto["portas"]
    portas["entradas"] = publicas(entradas, portas["entradas"], 0, "e")
    portas["saidas"] = publicas(saidas, portas["saidas"], 1, "s")
    chaves_e = {p["chave"] for p in portas["entradas"]}
    chaves_s = {p["chave"] for p in portas["saidas"]}
    atual["fios"] = [
        f
        for f in atual["fios"]
        if not (f["para"] == id_conjunto and f["entrada"] not in chaves_e)
        and not (f["de"] == id_conjunto and f["saida"] not in chaves_s)
    ]
    return novo


def renomear(
    dados: Mapping[str, Any], id_conjunto: str, nome: str, caminho: Sequence[str] = ()
) -> dict[str, Any]:
    novo = deepcopy(dict(dados))
    atual = nivel(novo, caminho)
    for no in atual["nos"]:
        if no["id"] == id_conjunto:
            no["nome"] = nome.strip() or no.get("nome", "Conjunto")
    return novo


def tirar_portas_mortas(dados: Mapping[str, Any]) -> dict[str, Any]:
    """Apagar um bloco dentro do conjunto não pode deixar porta pública apontando para o nada."""
    novo = deepcopy(dict(dados))

    def limpar(atual: dict[str, Any]) -> None:
        for no in atual.get("nos", []):
            if no.get("tipo") != CONJUNTO:
                continue
            interno = no["grafo"]
            limpar(interno)
            ids = {str(n["id"]) for n in interno["nos"]}
            portas = no["portas"]
            portas["entradas"] = [p for p in portas["entradas"] if p["no"] in ids]
            portas["saidas"] = [p for p in portas["saidas"] if p["no"] in ids]
            chaves_e = {p["chave"] for p in portas["entradas"]}
            chaves_s = {p["chave"] for p in portas["saidas"]}
            atual["fios"] = [
                f
                for f in atual["fios"]
                if not (f["para"] == no["id"] and f["entrada"] not in chaves_e)
                and not (f["de"] == no["id"] and f["saida"] not in chaves_s)
            ]

    limpar(novo)
    return novo


# ---------------------------------------------------------------------------
# Biblioteca
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConjuntoSalvo:
    nome: str
    dominio: str
    grafo: Mapping[str, Any]
    portas: Mapping[str, Any]
    valores: Mapping[str, float]


def _ler() -> dict[str, Any]:
    if not ARQUIVO_USUARIO.exists():
        return {"formato": _FORMATO, "conjuntos": []}
    try:
        documento = json.loads(ARQUIVO_USUARIO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ErroDeConjunto(f"A biblioteca de conjuntos não pôde ser lida: {erro}") from erro
    if not isinstance(documento, Mapping) or not isinstance(documento.get("conjuntos"), list):
        raise ErroDeConjunto("A biblioteca de conjuntos está em formato desconhecido.")
    return dict(documento)


def _gravar(documento: Mapping[str, Any], arquivo: Path | None = None) -> None:
    caminho = arquivo or ARQUIVO_USUARIO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    texto = json.dumps(documento, ensure_ascii=False, indent=2)
    temporario.write_text(texto, encoding="utf-8")
    temporario.replace(caminho)
    espelho_remoto.enviar(
        f"catalogos/{caminho.name}", texto.encode("utf-8"), f"Conjuntos do usuário: {caminho.name}"
    )


def listar(dominio: str) -> list[ConjuntoSalvo]:
    try:
        documento = _ler()
    except ErroDeConjunto:
        return []
    salvos = []
    for item in documento["conjuntos"]:
        if isinstance(item, Mapping) and item.get("dominio") == dominio:
            salvos.append(
                ConjuntoSalvo(
                    str(item.get("nome")),
                    dominio,
                    item.get("grafo") or {},
                    item.get("portas") or {},
                    item.get("valores") or {},
                )
            )
    return salvos


def salvar(
    nome: str,
    dominio: str,
    conjunto: Mapping[str, Any],
    valores: Mapping[str, float] | None = None,
) -> None:
    """Guarda na biblioteca. Mesmo nome na mesma parte do Montador substitui."""
    nome = nome.strip()
    if not nome:
        raise ErroDeConjunto("Dê um nome ao conjunto antes de salvar.")
    documento = _ler()
    lista = [
        item
        for item in documento["conjuntos"]
        if not (item.get("nome") == nome and item.get("dominio") == dominio)
    ]
    lista.append(
        {
            "nome": nome,
            "dominio": dominio,
            "grafo": deepcopy(conjunto["grafo"]),
            "portas": deepcopy(conjunto["portas"]),
            "valores": dict(valores or {}),
        }
    )
    documento["conjuntos"] = lista
    _gravar(documento)


def remover(nome: str, dominio: str) -> None:
    documento = _ler()
    documento["conjuntos"] = [
        item
        for item in documento["conjuntos"]
        if not (item.get("nome") == nome and item.get("dominio") == dominio)
    ]
    _gravar(documento)


def catalogo_de_conjuntos(dominio: str) -> list[dict[str, Any]]:
    """Os conjuntos salvos, no mesmo formato dos blocos da biblioteca."""
    itens = []
    for salvo in listar(dominio):
        quantos = len(salvo.grafo.get("nos") or ())
        itens.append(
            {
                "chave": f"conjunto:{salvo.nome}",
                "nome": salvo.nome,
                "grupo": GRUPO_CONJUNTOS,
                "classe": "g-conjunto",
                "dica": f"Conjunto salvo, com {quantos} blocos.",
                "formula": f"{quantos} blocos",
                "entradas": list(salvo.portas.get("entradas") or ()),
                "saidas": list(salvo.portas.get("saidas") or ()),
                "conjunto": {"grafo": salvo.grafo, "portas": salvo.portas, "nome": salvo.nome},
            }
        )
    return itens


def blocos_de_dentro(conjunto: Mapping[str, Any]) -> list[str]:
    """Os nomes dos blocos, para o inspetor mostrar o conteúdo sem abrir o conjunto."""
    nomes = []
    for no in conjunto["grafo"]["nos"]:
        if no.get("tipo") == CONJUNTO:
            nomes.append(str(no.get("nome")))
        else:
            bloco = mb.POR_CHAVE.get(str(no.get("tipo")))
            nomes.append(bloco.nome if bloco else str(no.get("tipo")))
    return nomes
