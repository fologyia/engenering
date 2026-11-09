"""O que mais pesa na resposta do Montador: cada número sobe e desce 10 %, e a conta é refeita.

Não é derivada: a conta inteira roda de novo, e por isso aparece também quando outra condição passa a
mandar. Só entram as condições que estão perto do limite (uso de 75 % para cima). Uma condição com
folga maior não chega a mandar com 10 % a mais numa letra, e assim a conta fica rápida mesmo no eixo
com trechos, que tem dezenas de condições.

Sem Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core import montador as mt
from core.montador_grandezas import Grandeza

PASSO = 0.10
USO_PERTO_DO_LIMITE = 0.75
QUASE_NADA = 0.001  # menos de 0,1 % na resposta


@dataclass(frozen=True)
class Peso:
    grandeza: Grandeza
    valor: float  # na base
    sobe: float | None  # quanto a resposta muda, em fração, com a letra 10 % acima
    desce: float | None
    manda_depois: str | None  # outra condição que passa a mandar numa das duas pontas

    @property
    def tamanho(self) -> float:
        return max(abs(self.sobe or 0.0), abs(self.desce or 0.0))

    @property
    def quase_nada(self) -> bool:
        return self.tamanho < QUASE_NADA


def _variar(
    conta: mt.Montagem,
    alvo: str,
    valores: dict[str, float],
    chave: str,
    fator: float,
    base: float,
) -> tuple[float | None, str | None]:
    valor = valores[chave] * fator
    grandeza = conta.grandeza(chave)
    if grandeza is None or grandeza.problema_no_valor(valor):
        return None, None  # 10 % abaixo de K_t = 1 não é um número que exista
    try:
        resposta = mt.isolar(conta, alvo, {**valores, chave: valor})
    except mt.ErroDeMontagem:
        return None, None
    if resposta.valor is None or resposta.manda is None:
        return None, None
    return resposta.valor / base - 1.0, resposta.manda.condicao.nome


def pesos(resposta: mt.Resposta, passo: float = PASSO) -> list[Peso]:
    """Do que mais pesa ao que menos pesa. Vazio quando a resposta ainda não tem número."""
    conta = resposta.montagem
    if conta is None or resposta.valor is None or resposta.manda is None or resposta.faltam:
        return []
    usos = {linha.nome: linha.uso for linha in resposta.conferencia}
    manda = resposta.manda.condicao
    perto = tuple(
        c
        for c in conta.condicoes
        if c is manda or c.igualdade or usos.get(c.nome, 0.0) >= USO_PERTO_DO_LIMITE
    )
    reduzida = replace(conta, condicoes=perto)
    alvo = resposta.alvo.chave
    valores = {k: float(v) for k, v in resposta.valores_usados.items()}
    lista = []
    for grandeza in conta.grandezas:
        chave = grandeza.chave
        if chave == alvo or chave not in conta.essenciais or not valores.get(chave):
            continue
        sobe, depois_de_subir = _variar(reduzida, alvo, valores, chave, 1.0 + passo, resposta.valor)
        desce, depois_de_descer = _variar(
            reduzida, alvo, valores, chave, 1.0 - passo, resposta.valor
        )
        outra = next(
            (nome for nome in (depois_de_subir, depois_de_descer) if nome and nome != manda.nome),
            None,
        )
        lista.append(Peso(grandeza, valores[chave], sobe, desce, outra))
    return sorted(lista, key=lambda p: p.tamanho, reverse=True)
