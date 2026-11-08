"""Desfazer e refazer do Montador, e os números que acompanham cada bloco.

O histórico guarda a montagem inteira a cada mudança: blocos, fios e valores juntos. Por isso um Ctrl+Z
só desfaz na ordem em que as coisas foram feitas, seja um fio ligado na prancheta, seja um número
digitado no inspetor ou no próprio cartão. Tudo aqui é dado simples, que cabe no ``st.session_state``:
a tela é quem decide quando guardar e quando voltar.

O segundo bloco igual usa outra letra (L₂, D₂), e a letra sai da ordem dos fios. Apagar o primeiro
trecho faz o segundo virar L: sem acompanhar, ele passaria a mostrar os números do trecho apagado.
Aqui o número segue o bloco, e não a letra. A cópia de um bloco nasce com os números do original,
marcados com a procedência até alguém mexer neles.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import montador as mt

LIMITE = 60  # passos guardados para trás
COPIADO = "Copiado de "

# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------


def novo(atual: Mapping[str, Any]) -> dict[str, Any]:
    return {"passado": [], "futuro": [], "atual": atual}


def registrar(historico: dict[str, Any], atual: Mapping[str, Any], *, juntar: bool = False) -> bool:
    """Guarda a montagem de antes, se ela mudou. Devolve se mudou.

    ``juntar`` troca a montagem guardada sem abrir outro passo: a prancheta se arrumando sozinha,
    logo depois de abrir um modelo, não é algo que alguém queira desfazer.
    """
    if historico["atual"] == atual:
        return False
    if not juntar:
        historico["passado"].append(historico["atual"])
        del historico["passado"][:-LIMITE]
        historico["futuro"].clear()
    historico["atual"] = atual
    return True


def desfazer(historico: dict[str, Any]) -> Mapping[str, Any] | None:
    if not historico["passado"]:
        return None
    historico["futuro"].append(historico["atual"])
    historico["atual"] = historico["passado"].pop()
    return historico["atual"]


def refazer(historico: dict[str, Any]) -> Mapping[str, Any] | None:
    if not historico["futuro"]:
        return None
    historico["passado"].append(historico["atual"])
    historico["atual"] = historico["futuro"].pop()
    return historico["atual"]


def blocos(dados: Mapping[str, Any], prefixo: str = "") -> dict[str, Mapping[str, Any]]:
    """Todos os blocos, também os de dentro dos conjuntos, pelo id completo."""
    achados: dict[str, Mapping[str, Any]] = {}
    for no in dados.get("nos") or ():
        if not isinstance(no, Mapping):
            continue
        id_ = f"{prefixo}{no.get('id')}"
        achados[id_] = no
        interno = no.get("grafo")
        if isinstance(interno, Mapping):
            achados |= blocos(interno, f"{id_}/")
    return achados


def _fios(dados: Mapping[str, Any], prefixo: str = "") -> set[tuple[str, ...]]:
    achados: set[tuple[str, ...]] = {
        (prefixo, str(f.get("de")), str(f.get("saida")), str(f.get("para")), str(f.get("entrada")))
        for f in dados.get("fios") or ()
        if isinstance(f, Mapping)
    }
    for no in dados.get("nos") or ():
        if isinstance(no, Mapping) and isinstance(no.get("grafo"), Mapping):
            achados |= _fios(no["grafo"], f"{prefixo}{no.get('id')}/")
    return achados


@dataclass(frozen=True)
class Mudanca:
    """O que mudou de uma montagem para a outra, para dizer em palavras o que o Ctrl+Z fez."""

    entraram: tuple[str, ...] = ()  # ids dos blocos
    sairam: tuple[str, ...] = ()
    fios: bool = False
    opcoes: tuple[str, ...] = ()
    lugares: bool = False
    valores: tuple[str, ...] = ()  # letras com outro número
    origens: tuple[str, ...] = ()  # mesmas letras e números, outra procedência
    alvo: bool = False
    adotado: bool = False
    tipos: bool = False  # um bloco virou outro com o mesmo id: é outra montagem, como num modelo


def mudanca(de: Mapping[str, Any], para: Mapping[str, Any]) -> Mudanca:
    nos_de, nos_para = blocos(de.get("grafo") or {}), blocos(para.get("grafo") or {})
    comuns = [id_ for id_ in nos_para if id_ in nos_de]

    def sem(no: Mapping[str, Any], *fora: str) -> dict[str, Any]:
        return {k: v for k, v in no.items() if k not in ("grafo", *fora)}

    valores_de, valores_para = de.get("valores") or {}, para.get("valores") or {}
    origens_de, origens_para = de.get("origens") or {}, para.get("origens") or {}
    letras = sorted(set(valores_de) | set(valores_para))
    outros = tuple(c for c in letras if valores_de.get(c) != valores_para.get(c))
    procedencias = sorted(set(origens_de) | set(origens_para))
    return Mudanca(
        entraram=tuple(id_ for id_ in nos_para if id_ not in nos_de),
        sairam=tuple(id_ for id_ in nos_de if id_ not in nos_para),
        fios=_fios(de.get("grafo") or {}) != _fios(para.get("grafo") or {}),
        opcoes=tuple(
            id_ for id_ in comuns if sem(nos_de[id_], "x", "y") != sem(nos_para[id_], "x", "y")
        ),
        lugares=any(
            (nos_de[id_].get("x"), nos_de[id_].get("y"))
            != (nos_para[id_].get("x"), nos_para[id_].get("y"))
            for id_ in comuns
        ),
        valores=outros,
        origens=tuple(
            c for c in procedencias if c not in outros and origens_de.get(c) != origens_para.get(c)
        ),
        alvo=de.get("alvo") != para.get("alvo"),
        adotado=de.get("adotado") != para.get("adotado"),
        tipos=any(nos_de[id_].get("tipo") != nos_para[id_].get("tipo") for id_ in comuns),
    )


# ---------------------------------------------------------------------------
# O número segue o bloco
# ---------------------------------------------------------------------------


def letras_por_no(montagem: mt.Montagem) -> dict[str, list[Any]]:
    """Cada bloco com o tipo, a posição entre os iguais e as letras dele. Cabe num JSON."""
    tipos = {no.id: no.tipo for no in montagem.grafo.nos}
    indices = dict(montagem.indices)
    return {
        id_: [tipos.get(id_, ""), indices.get(id_, 1), list(letras)]
        for id_, letras in montagem.letras_do_bloco
    }


def _base(chave: str, indice: int) -> str:
    """A letra sem o número do bloco: L_2, do segundo trecho, é L."""
    sufixo = f"_{indice}"
    return chave[: -len(sufixo)] if indice > 1 and chave.endswith(sufixo) else chave


def _anterior(
    id_: str, tipo: str, antes: Mapping[str, Sequence[Any]], depois: Mapping[str, Sequence[Any]]
) -> Sequence[Any] | None:
    """O mesmo bloco na rodada de antes. Agrupar muda o id de n2 para c1/n2, e desfazer o conjunto
    volta: vale o bloco do mesmo tipo com o mesmo fim de id, se só houver um."""
    if id_ in antes:
        return antes[id_] if antes[id_][0] == tipo else None
    fim = id_.rsplit("/", 1)[-1]
    achados = [
        dados
        for velho, dados in antes.items()
        if velho not in depois and velho.rsplit("/", 1)[-1] == fim and dados[0] == tipo
    ]
    return achados[0] if len(achados) == 1 else None


def renomes(
    antes: Mapping[str, Sequence[Any]], depois: Mapping[str, Sequence[Any]]
) -> dict[str, str]:
    """Letra de antes → letra de agora, nos blocos que mudaram de posição entre os iguais.

    Letra que outro bloco continua usando com o mesmo nome fica como está: seria a mesma letra nos
    dois, e trazer o número de um mudaria o outro também.
    """
    fixas: set[str] = set()
    for id_, (tipo, indice, letras) in depois.items():
        anterior = _anterior(id_, tipo, antes, depois)
        if anterior is not None and anterior[1] == indice:
            fixas |= set(letras) & set(anterior[2])
    trocas: dict[str, str] = {}
    for id_, (tipo, indice, letras) in depois.items():
        anterior = _anterior(id_, tipo, antes, depois)
        if anterior is None or anterior[1] == indice:
            continue
        velhas = {_base(chave, anterior[1]): chave for chave in anterior[2]}
        for chave in letras:
            velha = velhas.get(_base(chave, indice))
            if velha is not None and velha != chave and chave not in fixas:
                trocas[velha] = chave
    return trocas


def aplicar_renomes(
    trocas: Mapping[str, str],
    depois: Mapping[str, Sequence[Any]],
    *dicionarios: MutableMapping[str, Any],
) -> None:
    """Muda as chaves de uma vez só: o L₂ vira L enquanto o L vira L₂, sem um apagar o outro."""
    em_uso = {chave for _, _, letras in depois.values() for chave in letras}
    for dados in dicionarios:
        antes = dict(dados)
        for velha in trocas:
            if velha not in em_uso:
                dados.pop(velha, None)
        for velha, nova in trocas.items():
            if velha in antes:
                dados[nova] = antes[velha]
            else:
                dados.pop(nova, None)


# ---------------------------------------------------------------------------
# Cópia
# ---------------------------------------------------------------------------


def letras_da_copia(montagem: mt.Montagem, colados: Mapping[str, str]) -> list[tuple[str, str]]:
    """(letra da cópia, letra do original) dos blocos colados, também dentro de um conjunto copiado.

    ``colados`` vai do id completo da cópia ao do original. A letra se acha pelo nome sem o número:
    o L₂ da cópia vem do L, mesmo que um fio tire outra letra de um dos dois.
    """
    por_no = letras_por_no(montagem)
    pares: list[tuple[str, str]] = []
    for novo, original in colados.items():
        for id_, (tipo, indice, letras) in por_no.items():
            if id_ == novo:
                fonte = original
            elif id_.startswith(f"{novo}/"):
                fonte = f"{original}{id_[len(novo) :]}"
            else:
                continue
            dele = por_no.get(fonte)
            if dele is None or dele[0] != tipo:
                continue
            bases = {_base(chave, dele[1]): chave for chave in dele[2]}
            for chave in letras:
                velha = bases.get(_base(chave, indice))
                if velha is not None and velha != chave:
                    pares.append((chave, velha))
    return list(dict.fromkeys(pares))


def copiar_valores(
    pares: Sequence[tuple[str, str]],
    valores: MutableMapping[str, float | None],
    origens: MutableMapping[str, str],
    padroes: MutableMapping[str, float],
    padroes_do_bloco: Mapping[str, float],
    padrao: Callable[[str], float | None],
    texto: Callable[[str], str],
) -> list[str]:
    """Os números do original na cópia, com "Copiado de L" de procedência. Devolve as letras copiadas.

    O que a cópia já traria sozinha, o padrão do programa ou o da tabela, fica com a procedência de
    lá: não é número digitado por alguém, e não precisa de conferência.
    """
    copiadas = []
    for chave, fonte in pares:
        if chave in padroes_do_bloco:
            padroes[chave] = padroes_do_bloco[
                chave
            ]  # sem isto, o padrão passaria por cima da cópia
        if fonte not in valores:
            continue
        valor = valores[fonte]
        if valor is not None and valor == padrao(chave):
            valores.pop(chave, None)  # a tela põe o padrão de novo, com a procedência dele
            continue
        valores[chave] = valor
        origens[chave] = f"{COPIADO}{texto(fonte)}"
        copiadas.append(chave)
    return copiadas


def copiada(origem: str | None) -> str:
    """A letra de onde o número veio, se ele foi copiado de outro bloco; senão, vazio."""
    return origem[len(COPIADO) :] if origem and origem.startswith(COPIADO) else ""
