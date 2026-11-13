"""Onde cada bloco do Montador faz sentido: a biblioteca esconde o que não cabe na montagem.

Duas coisas decidem. A primeira é a forma da seção: pressão interna só existe em tubo, e as peças do
eixo pedem seção redonda. A segunda é o tipo de peça: eixo que gira, tubo com pressão e coluna
comprimida são estudos diferentes, e uma engrenagem não entra na conta de uma coluna.

Esconder não proíbe. A biblioteca diz quantos blocos ficaram de fora e mostra todos com um clique, e
o bloco que já está na prancheta nunca some. As seções não escondem umas às outras, porque uma
montagem pode ter duas, como a viga e o pino que a segura. Bloco sem linha em ``USOS`` serve em
qualquer montagem, e por isso um bloco novo nunca fica escondido por engano.

Nas partes de fluidos e de térmica quem decide é o fluido escolhido no bloco Fluido ou no Estado do
fluido: a bomba e o NPSH são de líquido, o gás no tubo é de gás, e o título, o superaquecimento e o
COP só existem em fluido que muda de fase. Com mais de um fluido na montagem, basta um servir.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import montador_blocos as mb
from core import montador_fluidos as mfl
from core import montador_propriedades as mp
from core.montador import CONJUNTO

REDONDA = "redonda"
TUBO = "tubo"
RETANGULAR = "retangular"
PERFIL_I = "perfil_i"
DESENHADA = "desenhada"
_NOME_DA_FORMA = {
    REDONDA: "seção redonda maciça",
    TUBO: "tubo circular",
    RETANGULAR: "seção retangular",
    PERFIL_I: "perfil I",
    DESENHADA: "seção desenhada",
}

EIXO = "eixo"
VASO = "vaso"
COLUNA = "coluna"
_NOME_DA_FAMILIA = {
    EIXO: "eixo que gira",
    VASO: "tubo com pressão",
    COLUNA: "coluna comprimida",
}
#: Estudos que não se misturam. Tubo com pressão e coluna se misturam: é a camisa de um cilindro
#: hidráulico, que tem pressão por dentro e flamba.
NAO_SE_MISTURAM = frozenset({frozenset({EIXO, VASO}), frozenset({EIXO, COLUNA})})
_PROFUNDIDADE = 20

#: O que o fluido da montagem faz: fica líquido, fica gás, ou muda de fase (água, refrigerantes).
SO_LIQUIDO = "liquido"
SO_GAS = "gas"
MUDA_DE_FASE = "muda_de_fase"
_DE_LIQUIDO = frozenset({SO_LIQUIDO, MUDA_DE_FASE})
_DE_GAS = frozenset({SO_GAS, MUDA_DE_FASE})
_DE_MUDANCA = frozenset({MUDA_DE_FASE})
_PARA_QUE = {
    _DE_LIQUIDO: "É de líquido",
    _DE_GAS: "É de gás ou vapor",
    _DE_MUDANCA: "Só existe em fluido que muda de fase, como a água e os refrigerantes",
}
#: Os blocos que só valem com um tipo de fluido.
FLUIDOS_DO_BLOCO: dict[str, frozenset[str]] = {
    # Fluidos
    "altura_bomba": _DE_LIQUIDO,
    "curva_bomba": _DE_LIQUIDO,
    "potencia_bomba": _DE_LIQUIDO,
    "npsh": _DE_LIQUIDO,
    "golpe": _DE_LIQUIDO,
    "valvula_controle": _DE_LIQUIDO,
    "gas_no_tubo": _DE_GAS,
    # Térmico
    "bomba_termica": _DE_LIQUIDO,
    "compressor": _DE_GAS,
    "turbina": _DE_GAS,
    "titulo_minimo": _DE_MUDANCA,
    "superaquecimento_minimo": _DE_MUDANCA,
    "subresfriamento_minimo": _DE_MUDANCA,
    "cop": _DE_MUDANCA,
}


def _do_fluido_da_linha(nome: str) -> str | None:
    """O fluido do bloco Fluido: de tabela ou pela temperatura. Informado não diz nada."""
    pela_temperatura = mfl.POR_TEMPERATURA.get(nome)
    if pela_temperatura is not None:
        return SO_LIQUIDO if pela_temperatura.liquido else SO_GAS
    if nome in mfl.FLUIDOS_TIPICOS:
        return SO_GAS if nome in mfl.GASES_DE_TABELA else SO_LIQUIDO
    return None


def _do_estado(rotulo: str) -> str:
    """O fluido do Estado do fluido e do Circuito, na lista da CoolProp. Sem escolha, é a água."""
    fluido = mp.POR_ROTULO.get(rotulo, mp.POR_ROTULO["Água"])
    if fluido.saturacao:
        return MUDA_DE_FASE
    return SO_LIQUIDO if fluido.liquido else SO_GAS


def fluidos_da_montagem(dados: Mapping[str, Any], profundidade: int = 0) -> dict[str, str]:
    """O que os fluidos escolhidos na montagem fazem, com o nome de cada um para a mensagem."""
    achados: dict[str, str] = {}
    if profundidade > _PROFUNDIDADE:
        return achados
    for no in dados.get("nos") or ():
        if not isinstance(no, Mapping):
            continue
        tipo = str(no.get("tipo"))
        escolhas = no.get("opcoes")
        opcoes: Mapping[str, Any] = escolhas if isinstance(escolhas, Mapping) else {}
        if tipo == CONJUNTO and isinstance(no.get("grafo"), Mapping):
            for classe, nome in fluidos_da_montagem(no["grafo"], profundidade + 1).items():
                achados.setdefault(classe, nome)
        elif tipo == "fluido":
            nome = str(opcoes.get("fluido", "Água a 20 °C"))
            da_linha = _do_fluido_da_linha(nome)
            if da_linha is not None:
                achados.setdefault(da_linha, nome)
        elif tipo in ("estado", "circuito"):
            nome = str(opcoes.get("fluido", "Água"))
            achados.setdefault(_do_estado(nome), nome)
    return achados


def _conflito_de_fluido(chaves: Iterable[str], fluidos: Mapping[str, str]) -> str | None:
    if not fluidos:
        return None
    for chave in chaves:
        servem = FLUIDOS_DO_BLOCO.get(chave)
        if servem is None or servem & set(fluidos):
            continue
        nomes = sorted(set(fluidos.values()))
        qual = "o fluido da montagem é" if len(nomes) == 1 else "os fluidos da montagem são"
        return f"{_PARA_QUE[servem]}, e {qual} {_juntar(nomes)}."
    return None


def _tipos_de(grafo: Mapping[str, Any], profundidade: int = 0) -> list[str]:
    tipos: list[str] = []
    if profundidade > _PROFUNDIDADE:
        return tipos
    for no in grafo.get("nos") or ():
        if not isinstance(no, Mapping):
            continue
        if no.get("tipo") == CONJUNTO and isinstance(no.get("grafo"), Mapping):
            tipos += _tipos_de(no["grafo"], profundidade + 1)
        else:
            tipos.append(str(no.get("tipo")))
    return tipos


@dataclass(frozen=True)
class Uso:
    """``forma``: a que o bloco de seção dá à montagem. ``formas``: as seções com que o bloco vale,
    e vazio quer dizer qualquer. ``familia``: o tipo de peça, quando o bloco é de um só.
    """

    forma: str = ""
    formas: frozenset[str] = frozenset()
    familia: str = ""


_REDONDAS = frozenset({REDONDA, TUBO})
_PECA_DE_EIXO = Uso(formas=_REDONDAS, familia=EIXO)

USOS: dict[str, Uso] = {
    "circular": Uso(forma=REDONDA),
    "tubo_parede": Uso(forma=TUBO),
    "tubo_relacao": Uso(forma=TUBO),
    "retangular": Uso(forma=RETANGULAR),
    "perfil_i": Uso(forma=PERFIL_I),
    "desenhada": Uso(forma=DESENHADA),
    "pressao_interna": Uso(formas=frozenset({TUBO}), familia=VASO),
    "flambagem": Uso(familia=COLUNA),
    # Os entalhes do bloco são os de eixo: ressalto, rasgo de chaveta, canal de anel e cubo prensado.
    "entalhe": Uso(formas=_REDONDAS),
    "potencia": _PECA_DE_EIXO,
    "engrenagem": _PECA_DE_EIXO,
    "polia": _PECA_DE_EIXO,
    "engrenagem_conica": _PECA_DE_EIXO,
    "par_engrenagens": _PECA_DE_EIXO,
    "chaveta": _PECA_DE_EIXO,
    "cubo_prensado": _PECA_DE_EIXO,
    "rolamento": _PECA_DE_EIXO,
    "inclinacao": _PECA_DE_EIXO,
    "rotacao_critica": _PECA_DE_EIXO,
    "fuso": _PECA_DE_EIXO,
    # O eixo com trechos é a própria seção do eixo, redonda.
    "eixo_trechos": Uso(forma=REDONDA, formas=_REDONDAS, familia=EIXO),
}


def _pelas_opcoes(tipo: str, opcoes: Mapping[str, Any]) -> tuple[Uso, str] | None:
    """O que o bloco já posto diz pela escolha dele, com o nome para a mensagem.

    Na biblioteca as escolhas ainda não existem, e por isso isto só vale para quem está na prancheta.
    """
    if tipo == "goodman" and opcoes.get("esforcos") == mb.EIXO_GIRANDO:
        return _PECA_DE_EIXO, "A fadiga com eixo girando"
    return None


@dataclass(frozen=True)
class _Peca:
    nome: str
    uso: Uso


def _na_montagem(dados: Mapping[str, Any], profundidade: int = 0) -> list[_Peca]:
    """Os blocos da montagem que dizem algo do uso, também os de dentro dos conjuntos."""
    pecas: list[_Peca] = []
    if profundidade > _PROFUNDIDADE:
        return pecas
    for no in dados.get("nos") or ():
        if not isinstance(no, Mapping):
            continue
        tipo = str(no.get("tipo"))
        if tipo == CONJUNTO:
            interno = no.get("grafo")
            if isinstance(interno, Mapping):
                pecas += _na_montagem(interno, profundidade + 1)
            continue
        bloco = mb.POR_CHAVE.get(tipo)
        if bloco is None:
            continue
        opcoes = no.get("opcoes")
        escolhido = _pelas_opcoes(tipo, opcoes if isinstance(opcoes, Mapping) else {})
        if escolhido is not None:
            pecas.append(_Peca(escolhido[1], escolhido[0]))
        elif tipo in USOS:
            pecas.append(_Peca(bloco.nome, USOS[tipo]))
    return pecas


def _do_tipo(chave: str) -> list[_Peca]:
    bloco = mb.POR_CHAVE.get(chave)
    uso = USOS.get(chave)
    return [_Peca(bloco.nome, uso)] if bloco is not None and uso is not None else []


def _legivel(formas: frozenset[str]) -> str:
    if formas == _REDONDAS:
        return "seção redonda, maciça ou tubo"
    return " ou ".join(_NOME_DA_FORMA[f] for f in sorted(formas))


def _juntar(nomes: Sequence[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _conflito(candidato: Iterable[_Peca], montagem: Sequence[_Peca]) -> str | None:
    """Por que o candidato não cabe na montagem, ou None quando ele cabe."""
    secoes = [p for p in montagem if p.uso.forma]
    formas_em_uso = {p.uso.forma for p in secoes}
    for peca in candidato:
        uso = peca.uso
        if uso.forma:
            for outra in montagem:
                if outra.uso.formas and uso.forma not in outra.uso.formas:
                    return f"{outra.nome} só vale com {_legivel(outra.uso.formas)}."
        if uso.formas and formas_em_uso and not uso.formas & formas_em_uso:
            nomes = sorted({p.nome for p in secoes})
            qual = "a seção da montagem é" if len(nomes) == 1 else "as seções da montagem são"
            return f"Só vale com {_legivel(uso.formas)}, e {qual} {_juntar(nomes)}."
        if uso.familia:
            for outra in montagem:
                par = frozenset({uso.familia, outra.uso.familia})
                if outra.uso.familia and par in NAO_SE_MISTURAM:
                    return (
                        f"É de {_NOME_DA_FAMILIA[uso.familia]}, e {outra.nome} é de "
                        f"{_NOME_DA_FAMILIA[outra.uso.familia]}."
                    )
    return None


def escondidos(dados: Mapping[str, Any], itens: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Os itens da biblioteca que não cabem na montagem, cada um com o motivo.

    ``itens`` vem no formato da biblioteca: ``chave`` e, nos conjuntos salvos, ``conjunto`` com o
    grafo de dentro. Um conjunto fica de fora quando algum bloco dele não cabe.
    """
    montagem = _na_montagem(dados)
    fluidos = fluidos_da_montagem(dados)
    if not montagem and not fluidos:
        return {}
    fora: dict[str, str] = {}
    for item in itens:
        chave = str(item.get("chave"))
        conjunto = item.get("conjunto")
        if isinstance(conjunto, Mapping):
            grafo = conjunto.get("grafo")
            candidato = _na_montagem(grafo) if isinstance(grafo, Mapping) else []
            tipos = _tipos_de(grafo) if isinstance(grafo, Mapping) else []
        else:
            candidato = _do_tipo(chave)
            tipos = [chave]
        motivo = _conflito(candidato, montagem) or _conflito_de_fluido(tipos, fluidos)
        if motivo:
            fora[chave] = motivo
    return fora


def blocos_escondidos(dados: Mapping[str, Any], chaves: Iterable[str]) -> dict[str, str]:
    """O mesmo, para uma lista de blocos do catálogo."""
    return escondidos(dados, ({"chave": chave} for chave in chaves))
