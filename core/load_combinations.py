"""Gerador editável de combinações de ações por estados-limite."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class AcaoEstrutural:
    nome: str
    tipo: str
    n_kN: float
    v_kN: float
    m_kNm: float
    gamma: float
    psi0: float = 1.0
    psi1: float = 1.0
    psi2: float = 1.0


@dataclass(frozen=True)
class Combinacao:
    nome: str
    estado_limite: str
    acao_principal: str
    n_kN: float
    v_kN: float
    m_kNm: float
    expressao: str


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser finito.")
    return valor


def _validar(acoes: Iterable[AcaoEstrutural]) -> list[AcaoEstrutural]:
    itens = list(acoes)
    if not itens:
        raise ValueError("Informe pelo menos uma ação.")
    nomes = [acao.nome.strip() for acao in itens]
    if any(not nome for nome in nomes):
        raise ValueError("Toda ação deve possuir um nome.")
    if len(set(nomes)) != len(nomes):
        raise ValueError("Os nomes das ações devem ser únicos.")
    for acao in itens:
        if acao.tipo not in {"Permanente", "Variável"}:
            raise ValueError("O tipo deve ser Permanente ou Variável.")
        _finito("n_kN", acao.n_kN)
        _finito("v_kN", acao.v_kN)
        _finito("m_kNm", acao.m_kNm)
        if acao.gamma < 0:
            raise ValueError("gamma não pode ser negativo.")
        for nome, valor in (
            ("psi0", acao.psi0),
            ("psi1", acao.psi1),
            ("psi2", acao.psi2),
        ):
            if not 0 <= valor <= 1:
                raise ValueError(f"{nome} deve estar entre 0 e 1.")
    return itens


def _somar(
    acoes: list[AcaoEstrutural],
    fatores: dict[str, float],
) -> tuple[float, float, float]:
    n = sum(fatores[acao.nome] * acao.n_kN for acao in acoes)
    v = sum(fatores[acao.nome] * acao.v_kN for acao in acoes)
    m = sum(fatores[acao.nome] * acao.m_kNm for acao in acoes)
    return n, v, m


def gerar_combinacoes(acoes: Iterable[AcaoEstrutural]) -> list[Combinacao]:
    """Gera ELU fundamental e ELS rara, frequente e quase permanente.

    Os coeficientes ``gamma`` e ``psi`` são fornecidos pelo usuário para manter
    o gerador aplicável às categorias específicas da norma e do projeto.
    """
    itens = _validar(acoes)
    variaveis = [acao for acao in itens if acao.tipo == "Variável"]
    combinacoes: list[Combinacao] = []

    principais = variaveis or [None]
    for principal in principais:
        fatores_elu = {}
        termos_elu = []
        for acao in itens:
            if acao.tipo == "Permanente":
                fator = acao.gamma
            elif acao is principal:
                fator = acao.gamma
            else:
                fator = acao.gamma * acao.psi0
            fatores_elu[acao.nome] = fator
            termos_elu.append(f"{fator:.3g}·{acao.nome}")
        n, v, m = _somar(itens, fatores_elu)
        principal_nome = principal.nome if principal else "Sem variável"
        combinacoes.append(
            Combinacao(
                nome=f"ELU — {principal_nome} principal",
                estado_limite="ELU fundamental",
                acao_principal=principal_nome,
                n_kN=n,
                v_kN=v,
                m_kNm=m,
                expressao=" + ".join(termos_elu),
            )
        )

        if principal is None:
            continue
        for estado, psi_principal, psi_acompanhante, rotulo in (
            ("ELS rara", 1.0, "psi0", "rara"),
            ("ELS frequente", principal.psi1, "psi2", "frequente"),
        ):
            fatores_els = {}
            termos_els = []
            for acao in itens:
                if acao.tipo == "Permanente":
                    fator = 1.0
                elif acao is principal:
                    fator = float(psi_principal)
                else:
                    fator = float(getattr(acao, psi_acompanhante))
                fatores_els[acao.nome] = fator
                termos_els.append(f"{fator:.3g}·{acao.nome}")
            n, v, m = _somar(itens, fatores_els)
            combinacoes.append(
                Combinacao(
                    nome=f"ELS {rotulo} — {principal.nome} principal",
                    estado_limite=estado,
                    acao_principal=principal.nome,
                    n_kN=n,
                    v_kN=v,
                    m_kNm=m,
                    expressao=" + ".join(termos_els),
                )
            )

    fatores_qp = {
        acao.nome: 1.0 if acao.tipo == "Permanente" else acao.psi2
        for acao in itens
    }
    n, v, m = _somar(itens, fatores_qp)
    combinacoes.append(
        Combinacao(
            nome="ELS quase permanente",
            estado_limite="ELS quase permanente",
            acao_principal="—",
            n_kN=n,
            v_kN=v,
            m_kNm=m,
            expressao=" + ".join(
                f"{fatores_qp[acao.nome]:.3g}·{acao.nome}"
                for acao in itens
            ),
        )
    )
    return combinacoes
