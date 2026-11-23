"""O que o esboço da seção leva ao Montador além da seção: o limite num ponto e as medidas com nome.

* **Limite num ponto:** um ponto de análise marcado no esboço (A, B…) ganha um limite só dele, como
  numa solda ou na borda de um furo: σ, τ ou von Mises até o valor dado. As tensões são as que a
  seção já calcula no ponto (``core/montador_secoes.py``), com todos os esforços da fila.
* **Medida do desenho:** uma cota de referência com nome (``e``, a distância do furo ao centro de
  gravidade) vira um valor que sai do desenho: não é incógnita, e muda junto quando as letras do
  esboço mudam. É o braço do momento saindo do próprio desenho.

Os blocos entram no catálogo por ``montador_blocos.registrar``, como os de pinos e chapas.
"""

from __future__ import annotations

import re
from typing import Any

import sympy as sp

from core import elementos_vigas as ev
from core import esboco_secao as es
from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_secoes as ms
from core.montador_blocos import (
    CONDICAO,
    GRUPO_CRITERIO,
    GRUPO_SECAO,
    SECAO,
    VALOR,
    Bloco,
    Condicao,
    Contexto,
    ErroDeBloco,
    Opcao,
    Porta,
)
from core.montador_grandezas import MEDIDA, TENSAO, Grandeza

SEM_PONTO = "Escolha o ponto"
SEM_MEDIDA = "Escolha a medida"
VON_MISES = "von Mises"
NORMAL = "σ normal"
CISALHAMENTO = "τ"
TENSOES = (VON_MISES, NORMAL, CISALHAMENTO)
PREFIXO = "ponto "

LIMITE_NO_PONTO = Grandeza(
    "sigma_lp",
    "σ_lp",
    "Limite no ponto",
    TENSAO,
    "A tensão que este ponto aguenta, já com o fator de segurança, se houver: numa solda, a "
    "resistência do cordão; na borda de um furo, o limite que você adota ali.",
)


def _pontos() -> tuple[str, ...]:
    return (SEM_PONTO, *ev.pontos_dos_desenhos())


def rotulo_da_medida(medida: str, secao: str) -> str:
    return f"{medida} ({secao})"


_ROTULO = re.compile(r"^(?P<medida>\S+) \((?P<secao>.*)\)$")


def _medidas() -> tuple[str, ...]:
    return (SEM_MEDIDA, *(rotulo_da_medida(m, s) for m, s in ev.medidas_dos_desenhos()))


def _limite_no_ponto(c: Contexto) -> dict[str, Any]:
    nome = c.opcoes.get("ponto", SEM_PONTO)
    if nome == SEM_PONTO:
        raise ErroDeBloco(
            "Escolha o ponto. Os pontos de análise são marcados no esboço da Desenhar seção, com a "
            "ferramenta Ponto de análise."
        )
    estado = c.estado()
    marcados = [t for t in estado.tensoes if t.ponto.startswith(PREFIXO)]
    tensao = next((t for t in marcados if t.ponto == PREFIXO + nome), None)
    if tensao is None:
        if not estado.tensoes:
            raise ErroDeBloco("Ponha ao menos um esforço antes deste bloco.")
        outros = ", ".join(t.ponto[len(PREFIXO) :] for t in marcados) or "nenhum"
        raise ErroDeBloco(
            f"A seção ligada não tem o ponto {nome}. Pontos de análise dela: {outros}."
        )
    tipo = c.opcoes.get("tensao", VON_MISES)
    limite = c.letra(LIMITE_NO_PONTO)
    tensoes = [("\\sigma_{x}", tensao.sx), ("\\tau", tensao.tau)]
    if tipo == NORMAL:
        esquerda, letra = tensao.sx, "\\sigma"
    elif tipo == CISALHAMENTO:
        esquerda, letra = tensao.tau, "\\tau"
    else:
        sx, sy, tau = tensao.sx, tensao.sy, tensao.tau
        esquerda, letra = sp.sqrt(sx**2 - sx * sy + sy**2 + 3 * tau**2), "\\sigma_{eq}"
    c.hipoteses.append(
        f"No ponto {nome}, o limite é o que foi dado ({tipo} ≤ σ_lp), além do critério da seção."
    )
    condicao = Condicao(
        f"{tipo} no ponto {nome} (limite próprio)",
        f"Limite no ponto {nome}",
        esquerda,
        limite,
        letra,
        tensao.ponto,
        tuple(tensoes),
        estado.validade,
        tensao.sy == 0,
    )
    return {"condicao": [condicao]}


def medida_do_desenho(rotulo: str) -> tuple[sp.Expr, tuple[Grandeza, ...]]:
    """A medida com nome, como fórmula das letras do esboço, e as letras de que ela depende."""
    achado = _ROTULO.match(rotulo)
    if achado is None:
        raise ErroDeBloco("Escolha a medida: uma cota de referência com nome, no esboço.")
    medida, secao = achado["medida"], achado["secao"]
    esboco = ev.esboco_salvo(secao)
    if esboco is None:
        raise ErroDeBloco(f"A seção {secao} não está mais salva, ou não tem esboço.")
    modelo, indice = es.registrar(esboco, secao)
    j = next((i for i, cota in enumerate(modelo.medidas) if cota.nome == medida), None)
    if j is None:
        raise ErroDeBloco(f"A seção {secao} não tem mais a medida {medida}.")
    if modelo.letras:
        _, simbolos, grandezas = ms.letras_do_desenho(secao, modelo)
        valor = es.DoDesenho(sp.Integer(indice), sp.Integer(es.MEDIDA + j), *simbolos)
        return valor, grandezas
    numero = float(modelo.numero(es.MEDIDA + j, {})[0])
    return sp.Float(numero, 6) * g.ESCALA.simbolo, (g.ESCALA,)


def _medida(c: Contexto) -> dict[str, Any]:
    rotulo = c.opcoes.get("medida", SEM_MEDIDA)
    if rotulo == SEM_MEDIDA:
        raise ErroDeBloco(
            "Escolha a medida. Ela é uma cota de referência com nome, no esboço da Desenhar seção "
            "(clique na cota de referência e em Dar nome)."
        )
    valor, grandezas = medida_do_desenho(rotulo)
    for grandeza in grandezas:
        c.grandezas.setdefault(grandeza.chave, grandeza)
        c.proprias.append(grandeza.chave)
    c.hipoteses.append(
        f"A medida {rotulo} sai do desenho: muda junto quando as letras do esboço mudam."
    )
    return {"medida": valor}


BLOCOS_DO_DESENHO: tuple[Bloco, ...] = (
    Bloco(
        "limite_no_ponto",
        "Limite num ponto",
        GRUPO_CRITERIO,
        "Um limite só para um ponto de análise do esboço (A, B…): σ, τ ou von Mises até o valor "
        "dado, como numa solda ou na borda de um furo.",
        "σ no ponto ≤ σ_lp",
        (Porta("entrada", "Seção", SECAO),),
        (Porta("condicao", "Condição", CONDICAO),),
        _limite_no_ponto,
        (
            Opcao(
                "ponto",
                "Ponto",
                "Os pontos de análise marcados nos esboços salvos. A seção ligada precisa ter o "
                "ponto com este nome.",
                _pontos,
                SEM_PONTO,
            ),
            Opcao(
                "tensao",
                "Tensão",
                "Qual tensão do ponto fica abaixo do limite: von Mises (σ e τ juntos), só a normal "
                "ou só a de cisalhamento.",
                TENSOES,
                VON_MISES,
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "medida_do_desenho",
        "Medida do desenho",
        GRUPO_SECAO,
        "Uma cota de referência com nome no esboço, como o braço e: ligue no lugar de uma "
        "distância, e ela muda junto com as letras do desenho.",
        "e = medida do esboço",
        (),
        (Porta("medida", "Medida", VALOR, MEDIDA),),
        _medida,
        (
            Opcao(
                "medida",
                "Medida",
                "As cotas de referência com nome nos esboços salvos, com a seção entre parênteses.",
                _medidas,
                SEM_MEDIDA,
            ),
        ),
    ),
)

mb.registrar(BLOCOS_DO_DESENHO)
