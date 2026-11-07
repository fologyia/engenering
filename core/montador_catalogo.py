"""Escolher do catálogo: testa cada peça comercial na montagem e diz a mais leve que passa.

A busca em faixas anda por uma grade de números; aqui a lista é o que existe para comprar. Cada bloco
de seção sabe quais famílias do catálogo cabem nas letras dele, e o trecho de tubo usa a tabela de
tubos comerciais. A conta é a mesma da busca: troca as letras da peça e confere todas as condições.

Perfil I entra pelas quatro medidas, sem os raios de concordância. Isso deixa a inércia um pouco
abaixo da real, a favor da segurança.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from core import montador as mt
from core import montador_blocos as mb
from core import montador_busca as bs
from core import montador_fluidos as fl
from core import montador_grandezas as g
from core import montador_secoes as ms
from core import section_catalog as sc

_FAMILIAS_DO_I = ("W (mesa larga)", "HP (perfil de estaca)", "I duplamente simétrico")
_FAMILIA_DO_TUBO = "Tubo circular"
_FAMILIA_DA_BARRA_REDONDA = "Barra circular"
_FAMILIA_DA_BARRA_CHATA = "Barra retangular"
_FOLGA = 1e-9


class ErroDoCatalogo(ValueError):
    """O que impede de testar, em palavras de quem está montando."""


@dataclass(frozen=True)
class Peca:
    nome: str
    familia: str
    valores: tuple[tuple[str, float], ...]  # letra e valor, na base do sistema
    massa: float | None  # kg/m


@dataclass(frozen=True)
class Fonte:
    """Um bloco da montagem que pode vir do catálogo."""

    no: str
    rotulo: str
    familias: tuple[str, ...]
    pecas: tuple[Peca, ...]


@dataclass(frozen=True)
class Linha:
    peca: Peca
    uso: float
    manda: str
    passa: bool


@dataclass(frozen=True)
class Escolha:
    linhas: tuple[Linha, ...]  # quem passa primeiro, do mais leve ao mais pesado
    aprovadas: int
    testadas: int
    alertas: tuple[str, ...] = ()

    @property
    def melhor(self) -> Linha | None:
        return self.linhas[0] if self.linhas and self.linhas[0].passa else None


def _letra(base: mt.Montagem, id_: str, grandeza: g.Grandeza) -> str | None:
    """A letra deste bloco: o segundo trecho usa D_2, e não D."""
    for chave in dict(base.letras_do_bloco).get(id_, ()):
        if chave == grandeza.chave or chave.startswith(f"{grandeza.chave}_"):
            return chave
    return None


def _do_perfil(perfil: Any, chaves: Mapping[str, float]) -> Peca:
    return Peca(perfil.nome, perfil.familia, tuple(chaves.items()), perfil.massa_kg_m)


def _pecas_da_secao(tipo: str, opcoes: Mapping[str, str]) -> tuple[Peca, ...]:
    perfis = sc.listar_perfis().values()
    if tipo == "perfil_i":
        return tuple(
            _do_perfil(
                p,
                {
                    g.BF.chave: p.largura_mm,
                    g.H.chave: p.altura_mm,
                    g.TF.chave: p.espessura_mesa_mm,
                    g.TW.chave: p.espessura_alma_mm,
                },
            )
            for p in perfis
            if p.familia in _FAMILIAS_DO_I
        )
    if tipo == "tubo_parede":
        return tuple(
            _do_perfil(p, {g.D.chave: p.altura_mm, g.PAREDE.chave: p.espessura_alma_mm})
            for p in perfis
            if p.familia == _FAMILIA_DO_TUBO
        )
    if tipo == "circular":
        return tuple(
            _do_perfil(p, {g.D.chave: p.altura_mm})
            for p in perfis
            if p.familia == _FAMILIA_DA_BARRA_REDONDA
        )
    if tipo == "retangular":
        lado_h = opcoes.get("lado_maior", ms.LADO_H) == ms.LADO_H
        return tuple(
            _do_perfil(
                p,
                {
                    g.H.chave: p.altura_mm if lado_h else p.largura_mm,
                    g.B.chave: p.largura_mm if lado_h else p.altura_mm,
                },
            )
            for p in perfis
            if p.familia == _FAMILIA_DA_BARRA_CHATA
        )
    return ()


def _pecas_do_trecho(base: mt.Montagem, id_: str) -> tuple[Peca, ...]:
    chave = _letra(base, id_, g.D_TUBO)
    if chave is None:
        return ()
    return tuple(
        Peca(t.rotulo, t.familia, ((chave, t.interno_m),), None)
        for t in fl.TUBOS_COMERCIAIS.values()
    )


def fontes(base: mt.Montagem) -> tuple[Fonte, ...]:
    """Os blocos desta montagem que têm catálogo."""
    achadas = []
    for no in base.grafo.nos:
        if no.tipo == "trecho":
            pecas = _pecas_do_trecho(base, no.id)
        else:
            pecas = _pecas_da_secao(no.tipo, dict(no.opcoes))
        if pecas:
            familias = tuple(dict.fromkeys(p.familia for p in pecas))
            achadas.append(Fonte(no.id, mb.POR_CHAVE[no.tipo].nome, familias, pecas))
    return tuple(achadas)


def testar(
    base: mt.Montagem,
    fonte: Fonte,
    valores: Mapping[str, float | None],
    familias: Sequence[str] | None = None,
) -> Escolha:
    """``valores`` na base do sistema. As letras da peça são trocadas pelas de cada item da lista."""
    if any(c.igualdade for c in base.condicoes):
        raise ErroDoCatalogo(
            "Com equação na montagem, cada peça dá um resultado, e não um passa ou não passa: "
            "escolha a peça no bloco e leia o resultado."
        )
    pecas = [p for p in fonte.pecas if familias is None or p.familia in familias]
    if not pecas:
        raise ErroDoCatalogo("Escolha ao menos uma família.")
    chaves = tuple(chave for chave, _ in pecas[0].valores)
    bons, problemas = mt.conferir_valores(
        base, {k: v for k, v in valores.items() if k not in chaves}
    )
    if problemas:
        raise ErroDoCatalogo(problemas[0])
    zeros = mt.letras_zeradas(base, bons)
    conta = mt.montar(base.grafo, zeros) if zeros else base
    faltam = [
        item.texto
        for item in conta.grandezas
        if item.chave in conta.essenciais and item.chave not in chaves and item.chave not in bons
    ]
    if faltam:
        raise ErroDoCatalogo(f"Para testar, preencha {', '.join(faltam)}.")
    fixos = tuple(sorted((k, float(v)) for k, v in bons.items() if k not in chaves))
    pontos = [np.array([dict(p.valores)[c] for p in pecas], dtype=float) for c in chaves]
    nomes, usos, valido = bs.usos_nos_pontos(conta, chaves, fixos, pontos)
    linhas = []
    for i, peca in enumerate(pecas):
        daqui = usos[:, i]
        pior = float(daqui.max())
        passa = bool(valido[i]) and pior <= 1.0 + _FOLGA
        linhas.append(Linha(peca, pior, nomes[int(np.argmax(daqui))], passa))
    aprovadas = sum(linha.passa for linha in linhas)

    def ordem(linha: Linha) -> tuple[bool, float, float]:
        peso = linha.peca.massa
        if peso is None:
            peso = dict(linha.peca.valores)[chaves[0]]  # tubo: o menor diâmetro que passa
        return (not linha.passa, peso if linha.passa else 0.0, linha.uso)

    return Escolha(tuple(sorted(linhas, key=ordem)), aprovadas, len(linhas))
